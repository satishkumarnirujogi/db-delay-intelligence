"""Every ~30 min (self-gated):
  1. label logged departures that have left (actual delay -> ml.feature_log)
  2. log point-in-time features for departures 25-65 min ahead (ml.feature_log)
  3. if a champion model exists: predict every departure in the next 2 h (ml.predictions) and
     store the prediction made at logging time next to the logged features (for honest evaluation)
    python -m ml.score
"""
import pandas as pd

from ingestion import loader

DUE = """
select coalesce(max(finished_at) < now() - interval '25 minutes', true)
from ops.ingestion_runs where job = 'score' and status = 'success'
"""

# Final delay once the train has left (changes are accepted up to 15 min after departure).
LABEL = """
update ml.feature_log l
set actual_delay_min = f.dep_delay_min, actual_cancelled = f.is_cancelled, labeled_at = now()
from marts.fact_stop_event f
where f.stop_id = l.stop_id
  and l.labeled_at is null
  and l.planned_dep < now() - interval '30 minutes'
  and coalesce(f.actual_dep, f.planned_dep) < now() - interval '15 minutes'
"""

# All in SQL inside the database: nothing is pulled into Python, so egress stays ~0.
LOG_FEATURES = """
insert into ml.feature_log (stop_id, eva, train_category, line, planned_dep, minutes_to_departure,
  current_delay_min, has_realtime, station_avg_delay_30m, station_cancellations_60m,
  upstream_delay_min, hour_of_day, iso_weekday, temperature_c, precipitation_mm, snowfall_cm,
  wind_gust_kmh)
select stop_id, eva, train_category, line, planned_dep, minutes_to_departure,
  current_delay_min, has_realtime, station_avg_delay_30m, station_cancellations_60m,
  upstream_delay_min, hour_of_day, iso_weekday, temperature_c, precipitation_mm, snowfall_cm,
  wind_gust_kmh
from ml.ml_features_upcoming
where minutes_to_departure between 25 and 65   -- 40-min window > 30-min cadence: every stop gets logged once
on conflict (stop_id) do nothing
"""

UPSERT_PREDICTION = """
insert into ml.predictions (stop_id, scored_at, pred_delay_min, p_late, model_version)
values (%(stop_id)s, now(), %(pred_delay_min)s, %(p_late)s, %(model_version)s)
on conflict (stop_id) do update set scored_at = now(), pred_delay_min = excluded.pred_delay_min,
  p_late = excluded.p_late, model_version = excluded.model_version
"""

# Only the first prediction (made at logging time) is kept in the log: that is what evaluation scores.
LOG_PREDICTION = """
update ml.feature_log set pred_delay_min = %(pred_delay_min)s, p_late = %(p_late)s,
  model_version = %(model_version)s
where stop_id = %(stop_id)s and model_version is null
  and logged_at > now() - interval '10 minutes'   -- logged in this run, not a later, easier forecast
"""

# Departed trains drop out of ml_features_upcoming; their predictions are no longer needed.
PRUNE = "delete from ml.predictions where scored_at < now() - interval '6 hours'"


def predict(conn) -> int:
    from ml.model import FEATURES, load_champion, prepare  # lightgbm import only when scoring

    champion = load_champion()
    if champion is None:
        return 0
    reg, clf, meta = champion
    cur = conn.execute(f"select stop_id, {', '.join(FEATURES)} from ml.ml_features_upcoming")
    df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
    if df.empty:
        return 0
    x = prepare(df)
    rows = [{"stop_id": s, "pred_delay_min": round(float(d), 1), "p_late": round(float(p), 3),
             "model_version": meta["model_version"]}
            for s, d, p in zip(df["stop_id"], reg.predict(x), clf.predict(x), strict=True)]
    with conn.transaction():
        loader.insert(conn, UPSERT_PREDICTION, rows)
        loader.insert(conn, LOG_PREDICTION, rows)
        conn.execute(PRUNE)
    return len(rows)


def main() -> None:
    with loader.connect() as conn:
        if not conn.execute(DUE).fetchone()[0]:
            print("score: not due yet, skipping")
            return
        run_id = loader.start_run(conn, "score")
        try:
            with conn.transaction():
                labeled = conn.execute(LABEL).rowcount
                logged = conn.execute(LOG_FEATURES).rowcount
            predicted = predict(conn)
        except Exception as e:
            loader.finish_run(conn, run_id, "failed", 0, 0, repr(e))
            raise
        loader.finish_run(conn, run_id, "success", 0, logged + predicted)
        print(f"score: labeled {labeled}, logged {logged}, predicted {predicted}"
              + ("" if predicted else " (no champion model yet)"))


if __name__ == "__main__":
    main()
