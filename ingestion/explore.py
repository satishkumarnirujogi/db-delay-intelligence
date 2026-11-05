"""Step 1: run once locally.  python -m ingestion.explore

1. Looks up the 15 stations -> transform/seeds/stations.csv
2. Saves real plan / fchg / weather responses -> ingestion/tests/fixtures/
3. Lists every XML element + attribute seen -> docs/api_notes.md
"""
import csv
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from lxml import etree

from ingestion.settings import env

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "ingestion" / "tests" / "fixtures"
BERLIN = ZoneInfo("Europe/Berlin")

# Search name -> approx. coordinates (station building, 4 decimals). The Timetables API
# returns no coordinates; these are only used to pick a weather grid cell.
STATIONS = {
    "Berlin Hbf": (52.5251, 13.3694),
    "Berlin Südkreuz": (52.4752, 13.3655),
    "Berlin Ostbahnhof": (52.5103, 13.4348),
    "Berlin Gesundbrunnen": (52.5486, 13.3885),
    "Berlin-Spandau": (52.5344, 13.1975),
    "Hamburg Hbf": (53.5530, 10.0067),
    "Hannover Hbf": (52.3767, 9.7410),
    "Leipzig Hbf": (51.3455, 12.3821),
    "Frankfurt(Main)Hbf": (50.1071, 8.6638),
    "Köln Hbf": (50.9430, 6.9589),
    "Düsseldorf Hbf": (51.2199, 6.7942),
    "München Hbf": (48.1402, 11.5600),
    "Nürnberg Hbf": (49.4458, 11.0823),
    "Stuttgart Hbf": (48.7843, 9.1817),
    "Dresden Hbf": (51.0405, 13.7320),
}

# Berlin Hbf's own EVA (8011160) returns an empty timetable; its ICE/RE trains are listed under
# the "tief" level, one of its meta EVAs. Other stations' S-Bahn/bus meta EVAs are left out on purpose.
EVA_OVERRIDE = {"Berlin Hbf": 8098160}


def db_get(path: str) -> bytes:
    resp = requests.get(
        f"{env('DB_BASE_URL').rstrip('/')}/{path}",
        headers={
            "DB-Client-Id": env("DB_CLIENT_ID"),
            "DB-Api-Key": env("DB_API_KEY"),
            "Accept": "application/xml",
        },
        timeout=30,
    )
    if resp.status_code in (401, 403):
        raise SystemExit(f"{resp.status_code} from DB API: check keys and the Timetables subscription")
    resp.raise_for_status()
    time.sleep(1.2)  # stay well under 60 calls/min
    return resp.content


def lookup_stations() -> list[dict]:
    rows = []
    for name, (lat, lon) in STATIONS.items():
        root = etree.fromstring(db_get(f"station/{quote(name)}"))
        matches = root.findall("station")
        if not matches:
            raise SystemExit(f"No station found for {name!r}")
        exact = [m for m in matches if m.get("name") == name]
        pick = (exact or matches)[0]
        if not exact:
            print(f"  ! {name!r}: no exact match, took {pick.get('name')!r} — check it. "
                  f"All: {[m.get('name') for m in matches]}")
        if name in EVA_OVERRIDE:
            assert str(EVA_OVERRIDE[name]) in (pick.get("meta") or "").split("|"), f"{name} meta changed"
        rows.append({
            "eva": EVA_OVERRIDE.get(name, int(pick.get("eva"))),
            "station_name": pick.get("name"),
            "lat": lat,
            "lon": lon,
            "is_berlin": name.startswith("Berlin"),
        })
        print(f"  {rows[-1]['eva']}  {pick.get('name')}")
    return rows


def collect_schema(xml: bytes, seen: dict) -> None:
    for el in etree.fromstring(xml).iter():
        seen[el.tag].update(el.attrib.keys())


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)

    print("1/3 Stations")
    stations = lookup_stations()
    seed = ROOT / "transform" / "seeds" / "stations.csv"
    seed.parent.mkdir(parents=True, exist_ok=True)
    with seed.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(stations[0]))
        w.writeheader()
        w.writerows(stations)

    print("2/3 Fixtures (plan + fchg for Berlin Hbf and Frankfurt, weather for all)")
    now = datetime.now(BERLIN)
    seen: dict[str, set] = defaultdict(set)
    for eva in (8098160, next(s["eva"] for s in stations if s["station_name"].startswith("Frankfurt"))):
        plan = db_get(f"plan/{eva}/{now:%y%m%d}/{now:%H}")
        fchg = db_get(f"fchg/{eva}")
        (FIXTURES / f"plan_{eva}_{now:%y%m%d%H}.xml").write_bytes(plan)
        (FIXTURES / f"fchg_{eva}.xml").write_bytes(fchg)
        collect_schema(plan, seen)
        collect_schema(fchg, seen)

    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": ",".join(str(s["lat"]) for s in stations),
            "longitude": ",".join(str(s["lon"]) for s in stations),
            "hourly": "temperature_2m,precipitation,snowfall,wind_gusts_10m",
            "past_days": 1,
            "forecast_days": 1,
            "timezone": "UTC",
        },
        timeout=30,
    )
    weather.raise_for_status()
    (FIXTURES / "weather.json").write_text(json.dumps(weather.json(), indent=1), encoding="utf-8")

    print("3/3 docs/api_notes.md")
    lines = ["# API notes (generated by ingestion/explore.py from real responses)", "",
             f"Fetched {now:%Y-%m-%d %H:%M} Berlin time.", "",
             "| Element | Attributes seen |", "|---|---|"]
    lines += [f"| `{tag}` | {', '.join(f'`{a}`' for a in sorted(attrs)) or '—'} |"
              for tag, attrs in sorted(seen.items())]
    lines += ["", "Weather: Open-Meteo returns a list (one object per station, same order as the seed)."]
    (ROOT / "docs" / "api_notes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Done.")


if __name__ == "__main__":
    main()
