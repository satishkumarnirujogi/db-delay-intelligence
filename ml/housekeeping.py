"""Daily: export history to Parquet, trim old rows and raw files, log platform usage.
    python -m ml.housekeeping

Retention is sized from week-1 measurements (2026-11-05) to stay under Supabase's free
500 MB database / 1 GB storage: stop_changes ~15 MB/day, fact ~4 MB/day, raw fchg ~70 MB/day.
Rows are deleted only for days whose Parquet export exists, so nothing is lost.
"""
import io
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pyarrow as pa
import pyarrow.parquet as pq

from ingestion import loader, storage

STAGING_DAYS = 3    # fact_stop_event is incremental with a 3 h lookback, so it needs no more
WEATHER_DAYS = 7
FACT_DAYS = 30      # older detail lives in Parquet + marts.agg_station_hour
FEATURE_DAYS = 60   # older features live in Parquet (training reads both)
RAW_DAYS = 3
EXPORT_LOOKBACK = 3  # re-export the last few days, so one failed night is caught up

EXPORTS = {
    # name: (query for one Berlin service date, Parquet path prefix)
    "fact_stop_event": "select * from marts.fact_stop_event where service_date = %s",
    "feature_log": """select * from ml.feature_log
                      where (planned_dep at time zone 'Europe/Berlin')::date = %s""",
}


def parquet_path(name: str, day: date) -> str:
    return f"history/{name}/service_date={day:%Y-%m-%d}/data.parquet"


def export_day(conn, name: str, day: date) -> int:
    cur = conn.execute(EXPORTS[name], (day,))
    cols = [d.name for d in cur.description]
    rows = cur.fetchall()
    if not rows:
        return 0
    # Decimal -> float: pyarrow would infer decimal precision per day, giving files mixed schemas
    records = [{c: float(v) if isinstance(v, Decimal) else v for c, v in zip(cols, r)} for r in rows]
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(records), buf, compression="zstd")
    storage.upload(parquet_path(name, day), buf.getvalue(), "application/vnd.apache.parquet")
    return len(rows)


EXPORTED_DATES = """
select distinct substring(name from 'service_date=([0-9-]+)')::date
from storage.objects where bucket_id = 'bronze' and name like %s
"""

DELETES = [
    ("staging.stop_changes", f"delete from staging.stop_changes where fetched_at < now() - interval '{STAGING_DAYS} days'", None),
    ("staging.plan_stops", f"""delete from staging.plan_stops
        where coalesce(planned_dep, planned_arr) < now() - interval '{STAGING_DAYS} days'""", None),
    ("staging.weather_hourly", f"delete from staging.weather_hourly where observed_hour < now() - interval '{WEATHER_DAYS} days'", None),
    ("marts.fact_stop_event", """delete from marts.fact_stop_event
        where service_date < (now() at time zone 'Europe/Berlin')::date - %(days)s and service_date = any(%(exported)s)""",
     ("fact_stop_event", FACT_DAYS)),
    ("ml.feature_log", """delete from ml.feature_log
        where (planned_dep at time zone 'Europe/Berlin')::date < (now() at time zone 'Europe/Berlin')::date - %(days)s
          and (planned_dep at time zone 'Europe/Berlin')::date = any(%(exported)s)""",
     ("feature_log", FEATURE_DAYS)),
]

OLD_RAW = f"""
select name from storage.objects
where bucket_id = 'bronze' and (name like 'db/%' or name like 'meteo/%')
  and created_at < now() - interval '{RAW_DAYS} days'
"""

USAGE = """
insert into ops.platform_usage (db_mb, storage_mb, fact_rows, staging_rows, feature_rows)
select
  round(pg_database_size(current_database()) / 1048576.0, 1),
  round(coalesce((select sum((metadata->>'size')::bigint) from storage.objects), 0) / 1048576.0, 1),
  (select count(*) from marts.fact_stop_event),
  (select count(*) from staging.stop_changes) + (select count(*) from staging.plan_stops),
  (select count(*) from ml.feature_log)
returning db_mb, storage_mb
"""


def main() -> None:
    today = datetime.now(ZoneInfo("Europe/Berlin")).date()
    with loader.connect() as conn:
        run_id = loader.start_run(conn, "housekeeping")
        done = 0
        try:
            # 1. export: must succeed before anything is deleted (an exception stops the run)
            for name in EXPORTS:
                for back in range(EXPORT_LOOKBACK, 0, -1):
                    day = today - timedelta(days=back)
                    n = export_day(conn, name, day)
                    print(f"export {name} {day}: {n} rows")

            # 2. trim rows (fact/features only for exported days)
            for table, sql, guard in DELETES:
                params = None
                if guard:
                    name, days = guard
                    exported = [r[0] for r in conn.execute(EXPORTED_DATES, (f"history/{name}/%",))]
                    params = {"days": days, "exported": exported}
                with conn.transaction():
                    n = conn.execute(sql, params).rowcount
                done += n
                print(f"delete {table}: {n} rows")

            # 3. old raw files
            old = [r[0] for r in conn.execute(OLD_RAW)]
            print(f"delete raw files: {storage.delete(old) if old else 0}")

            # 4. usage snapshot
            with conn.transaction():
                db_mb, st_mb = conn.execute(USAGE).fetchone()
            print(f"usage: database {db_mb} MB, storage {st_mb} MB")
        except Exception as e:
            loader.finish_run(conn, run_id, "failed", 0, done, repr(e))
            raise
        loader.finish_run(conn, run_id, "success", 0, done)


if __name__ == "__main__":
    main()
