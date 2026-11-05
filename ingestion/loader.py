"""Idempotent inserts into staging.* and run logging into ops.ingestion_runs."""
import os

import psycopg

from ingestion.settings import env

INSERT_CHANGES = """
insert into staging.stop_changes
  (stop_id, eva, changed_arr, changed_dep, changed_platform, is_cancelled, content_hash, fetched_at)
values (%(stop_id)s, %(eva)s, %(changed_arr)s, %(changed_dep)s, %(changed_platform)s,
        %(is_cancelled)s, %(content_hash)s, %(fetched_at)s)
on conflict (stop_id, content_hash) do update
  set fetched_at = excluded.fetched_at, loaded_at = now()
  -- a state that comes back (delay 5 -> 10 -> 5) must become the latest again;
  -- unchanged trains (already the latest state) are left alone, so no write per run
  where stop_changes.fetched_at < (select max(s.fetched_at) from staging.stop_changes s
                                   where s.stop_id = excluded.stop_id)
"""

UPSERT_PLAN = """
insert into staging.plan_stops (stop_id, eva, train_category, train_number, line,
  planned_arr, planned_dep, planned_platform, route_ppth, fetched_at)
values (%(stop_id)s, %(eva)s, %(train_category)s, %(train_number)s, %(line)s,
  %(planned_arr)s, %(planned_dep)s, %(planned_platform)s, %(route_ppth)s, %(fetched_at)s)
on conflict (stop_id) do update set
  planned_arr = excluded.planned_arr, planned_dep = excluded.planned_dep,
  planned_platform = excluded.planned_platform, fetched_at = excluded.fetched_at,
  loaded_at = now()
"""

UPSERT_WEATHER = """
insert into staging.weather_hourly (eva, observed_hour, temperature_c, precipitation_mm,
  snowfall_cm, wind_gust_kmh, fetched_at)
values (%(eva)s, %(observed_hour)s, %(temperature_c)s, %(precipitation_mm)s,
  %(snowfall_cm)s, %(wind_gust_kmh)s, %(fetched_at)s)
on conflict (eva, observed_hour) do update set
  temperature_c = excluded.temperature_c, precipitation_mm = excluded.precipitation_mm,
  snowfall_cm = excluded.snowfall_cm, wind_gust_kmh = excluded.wind_gust_kmh,
  fetched_at = excluded.fetched_at, loaded_at = now()
"""

PLAN_DUE = """
select coalesce(max(finished_at) < now() - interval '50 minutes', true)
from ops.ingestion_runs where job = 'plan' and status = 'success'
"""


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=env("PG_HOST"), port=env("PG_PORT"), dbname=env("PG_DB"),
        user=env("PG_USER"), password=env("PG_PASSWORD"),
        sslmode=os.getenv("PG_SSLMODE", "require"),  # CI's local Postgres container has no SSL
        connect_timeout=20,
        autocommit=True,  # each conn.transaction() commits on its own, so a failed run is still logged
        prepare_threshold=None,  # the Supabase pooler may not keep prepared statements
    )


def insert(conn: psycopg.Connection, sql: str, rows: list[dict]) -> int:
    """Executes inside the caller's transaction; returns rows actually inserted/updated."""
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
        return cur.rowcount


def plan_due(conn: psycopg.Connection) -> bool:
    return conn.execute(PLAN_DUE).fetchone()[0]


def start_run(conn: psycopg.Connection, job: str) -> str:
    with conn.transaction():
        return conn.execute(
            "insert into ops.ingestion_runs (job, started_at, status) values (%s, now(), 'running') returning run_id",
            (job,)).fetchone()[0]


def finish_run(conn, run_id, status: str, api_calls: int, rows: int, error: str | None = None) -> None:
    with conn.transaction():
        conn.execute(
            """update ops.ingestion_runs set finished_at = now(), status = %s, api_calls = %s,
               rows_inserted = %s, error = %s where run_id = %s""",
            (status, api_calls, rows, (error or "")[:2000] or None, run_id))
