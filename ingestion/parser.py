"""Raw API responses -> rows for the staging tables. All timestamps become aware UTC datetimes."""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from lxml import etree

BERLIN = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")


def parse_db_time(value: str | None) -> datetime | None:
    """'2611051405' (yyMMddHHmm, German local time) -> aware UTC datetime.
    On the DST-end night the repeated hour resolves to its first (CEST) occurrence."""
    if not value:
        return None
    local = datetime.strptime(value, "%y%m%d%H%M").replace(tzinfo=BERLIN)
    return local.astimezone(UTC)


def _attr(el, name):
    return el.get(name) if el is not None else None


def parse_plan(xml_bytes: bytes, eva: int, fetched_at: datetime):
    root = etree.fromstring(xml_bytes)
    for s in root.findall("s"):
        tl, ar, dp = s.find("tl"), s.find("ar"), s.find("dp")
        event = dp if dp is not None else ar
        yield {
            "stop_id": s.get("id"),
            "eva": eva,
            "train_category": _attr(tl, "c"),
            "train_number": _attr(tl, "n"),
            "line": _attr(event, "l"),
            "planned_arr": parse_db_time(_attr(ar, "pt")),
            "planned_dep": parse_db_time(_attr(dp, "pt")),
            "planned_platform": _attr(event, "pp"),
            "route_ppth": _attr(event, "ppth"),
            "fetched_at": fetched_at,
        }


def content_hash(row: dict) -> str:
    key = "|".join(str(row[k]) for k in
                   ("stop_id", "changed_arr", "changed_dep", "changed_platform", "is_cancelled"))
    return hashlib.sha256(key.encode()).hexdigest()


def parse_changes(xml_bytes: bytes, eva: int, fetched_at: datetime):
    root = etree.fromstring(xml_bytes)
    for s in root.findall("s"):
        ar, dp = s.find("ar"), s.find("dp")
        if ar is None and dp is None:  # message-only entries (e.g. station notices)
            continue
        event = dp if dp is not None else ar
        row = {
            "stop_id": s.get("id"),
            "eva": eva,
            "changed_arr": parse_db_time(_attr(ar, "ct")),
            "changed_dep": parse_db_time(_attr(dp, "ct")),
            "changed_platform": _attr(event, "cp"),
            "is_cancelled": _attr(event, "cs") == "c",
            "fetched_at": fetched_at,
        }
        row["content_hash"] = content_hash(row)
        yield row


def parse_weather(json_bytes: bytes, evas: list[int], fetched_at: datetime):
    """Open-Meteo multi-location response is a list in the same order as `evas`."""
    data = json.loads(json_bytes)
    if isinstance(data, dict):  # single location returns an object, not a list
        data = [data]
    assert len(data) == len(evas), f"weather: {len(data)} locations for {len(evas)} stations"
    for eva, loc in zip(evas, data):
        h = loc["hourly"]
        for i, t in enumerate(h["time"]):
            yield {
                "eva": eva,
                "observed_hour": datetime.fromisoformat(t).replace(tzinfo=UTC),
                "temperature_c": h["temperature_2m"][i],
                "precipitation_mm": h["precipitation"][i],
                "snowfall_cm": h["snowfall"][i],
                "wind_gust_kmh": h["wind_gusts_10m"][i],
                "fetched_at": fetched_at,
            }
