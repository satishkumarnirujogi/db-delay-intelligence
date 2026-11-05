"""Entry point.
    python -m ingestion.run changes   # every run: fchg for all stations
    python -m ingestion.run hourly    # plan (current + next hour) + weather, only if due
"""
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ingestion import loader, meteo_client, parser, storage
from ingestion.db_client import DBClient

BERLIN = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")
SEED = Path(__file__).resolve().parent.parent / "transform" / "seeds" / "stations.csv"


def stations() -> list[dict]:
    with SEED.open(encoding="utf-8") as f:
        return [{**r, "eva": int(r["eva"])} for r in csv.DictReader(f)]


def run_changes(conn, client: DBClient) -> int:
    now = datetime.now(UTC)
    rows = []
    for st in stations():
        raw = client.fchg(st["eva"])
        storage.upload_raw(f"db/fchg/date={now:%Y-%m-%d}/eva={st['eva']}/{now:%H%M%S}.xml.gz", raw)
        rows += parser.parse_changes(raw, st["eva"], now)
    with conn.transaction():
        return loader.insert(conn, loader.INSERT_CHANGES, rows)


def run_hourly(conn, client: DBClient) -> int:
    now = datetime.now(UTC)
    sts = stations()
    plan_rows = []
    for st in sts:
        for local in (now.astimezone(BERLIN), (now + timedelta(hours=1)).astimezone(BERLIN)):
            raw = client.plan(st["eva"], f"{local:%y%m%d}", f"{local:%H}")
            storage.upload_raw(
                f"db/plan/date={now:%Y-%m-%d}/eva={st['eva']}/{now:%H%M%S}_h{local:%H}.xml.gz", raw)
            plan_rows += parser.parse_plan(raw, st["eva"], now)
    raw_weather = meteo_client.fetch(sts)
    storage.upload_raw(f"meteo/date={now:%Y-%m-%d}/{now:%H%M%S}.json.gz", raw_weather)
    weather_rows = list(parser.parse_weather(raw_weather, [s["eva"] for s in sts], now))
    with conn.transaction():
        return (loader.insert(conn, loader.UPSERT_PLAN, plan_rows)
                + loader.insert(conn, loader.UPSERT_WEATHER, weather_rows))


def main(mode: str) -> None:
    jobs = {"changes": ("changes", run_changes), "hourly": ("plan", run_hourly)}
    if mode not in jobs:
        sys.exit(f"usage: python -m ingestion.run [{'|'.join(jobs)}]")
    job, fn = jobs[mode]
    with loader.connect() as conn:
        if mode == "hourly" and not loader.plan_due(conn):
            print("plan: not due yet, skipping")
            return
        run_id = loader.start_run(conn, job)
        client = DBClient()
        try:
            n = fn(conn, client)
        except Exception as e:
            loader.finish_run(conn, run_id, "failed", client.calls, 0, repr(e))
            raise  # non-zero exit -> the Actions run fails and GitHub emails you
        loader.finish_run(conn, run_id, "success", client.calls, n)
        print(f"{job}: {client.calls} API calls, {n} rows written")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
