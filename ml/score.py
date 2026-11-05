"""Every ~30 min (self-gated): log point-in-time features into ml.feature_log.
    python -m ml.score

shortcut: no model exists yet, so this only logs features. Prediction (load the champion
model, write ml.predictions) is added with ml/train.py once 2-3 weeks of logs exist.
"""
from ingestion import loader

DUE = """
select coalesce(max(finished_at) < now() - interval '25 minutes', true)
from ops.ingestion_runs where job = 'score' and status = 'success'
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


def main() -> None:
    with loader.connect() as conn:
        if not conn.execute(DUE).fetchone()[0]:
            print("score: not due yet, skipping")
            return
        run_id = loader.start_run(conn, "score")
        try:
            with conn.transaction():
                n = conn.execute(LOG_FEATURES).rowcount
        except Exception as e:
            loader.finish_run(conn, run_id, "failed", 0, 0, repr(e))
            raise
        loader.finish_run(conn, run_id, "success", 0, n)
        print(f"score: logged features for {n} stops (no model yet)")


if __name__ == "__main__":
    main()
