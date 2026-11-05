from datetime import UTC, datetime
from pathlib import Path

from ingestion.parser import content_hash, parse_changes, parse_db_time, parse_plan, parse_weather

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 5, 12, 44, tzinfo=UTC)


def test_parse_db_time_winter():
    assert parse_db_time("2611051405") == datetime(2026, 11, 5, 13, 5, tzinfo=UTC)


def test_parse_db_time_summer():
    assert parse_db_time("2607011405") == datetime(2026, 7, 1, 12, 5, tzinfo=UTC)


def test_parse_db_time_dst_end_night():
    # 25 Oct 2026: 02:30 happens twice; we take the first one (CEST, UTC+2).
    assert parse_db_time("2610250230") == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert parse_db_time("2610250330") == datetime(2026, 10, 25, 2, 30, tzinfo=UTC)


def test_parse_db_time_none():
    assert parse_db_time(None) is None
    assert parse_db_time("") is None


def test_parse_plan_fixture():
    rows = list(parse_plan((FIX / "plan_8000105_26110513.xml").read_bytes(), 8000105, NOW))
    assert len(rows) == 57
    assert len({r["stop_id"] for r in rows}) == 57
    ice372 = next(r for r in rows if r["train_number"] == "372")
    assert ice372["train_category"] == "ICE"
    assert ice372["planned_dep"] == datetime(2026, 11, 5, 12, 15, tzinfo=UTC)
    assert ice372["planned_platform"] == "9"


def test_parse_changes_fixture():
    raw = (FIX / "fchg_8000105.xml").read_bytes()
    rows = list(parse_changes(raw, 8000105, NOW))
    assert len(rows) == 740 - 39  # message-only <s> entries are skipped
    # ICE 229: arrival cancelled but it still departs (starts here) -> not cancelled as a departure
    starts_here = next(r for r in rows if r["stop_id"] == "6492627968416470339-2611051232-9")
    assert starts_here["is_cancelled"] is False
    assert sum(r["is_cancelled"] for r in rows) > 0
    moved = next(r for r in rows if r["stop_id"] == "8088226351077928869-2611051046-7")
    assert moved["changed_platform"] == "9"
    assert moved["changed_dep"] == datetime(2026, 11, 5, 12, 54, tzinfo=UTC)


def test_content_hash_stable():
    raw = (FIX / "fchg_8098160.xml").read_bytes()
    a = list(parse_changes(raw, 8098160, NOW))
    b = list(parse_changes(raw, 8098160, datetime.now(UTC)))  # fetched_at must not affect the hash
    assert [r["content_hash"] for r in a] == [r["content_hash"] for r in b]
    changed = {**a[0], "is_cancelled": not a[0]["is_cancelled"]}
    assert content_hash(changed) != a[0]["content_hash"]


def test_parse_weather_fixture():
    evas = list(range(15))
    rows = list(parse_weather((FIX / "weather.json").read_bytes(), evas, NOW))
    assert {r["eva"] for r in rows} == set(evas)
    assert rows[0]["observed_hour"].tzinfo is not None
