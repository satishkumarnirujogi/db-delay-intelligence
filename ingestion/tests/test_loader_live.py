"""Runs against the real database inside a rolled-back transaction. Skipped without PG_HOST."""
import os
from datetime import UTC, datetime, timedelta

import pytest

from ingestion.parser import content_hash

pytestmark = pytest.mark.skipif(not os.getenv("PG_HOST") and not os.path.exists(".env"),
                                reason="needs a database")


def _row(delay_min: int, fetched_at: datetime) -> dict:
    row = {"stop_id": "pytest-stop-1", "eva": 1,
           "changed_arr": None,
           "changed_dep": datetime(2026, 1, 1, 12, tzinfo=UTC) + timedelta(minutes=delay_min),
           "changed_platform": None, "is_cancelled": False, "fetched_at": fetched_at}
    row["content_hash"] = content_hash(row)
    return row


def test_changes_insert_idempotent_and_revert():
    from ingestion import loader

    t0 = datetime(2026, 1, 1, 10, tzinfo=UTC)
    with loader.connect() as conn, pytest.raises(RuntimeError, match="rollback"), conn.transaction():
        ins = lambda rows: loader.insert(conn, loader.INSERT_CHANGES, rows)
        latest = lambda: conn.execute(
            """select changed_dep from staging.stop_changes where stop_id = 'pytest-stop-1'
                       order by fetched_at desc limit 1""").fetchone()[0]

        assert ins([_row(5, t0)]) == 1
        assert ins([_row(5, t0 + timedelta(minutes=10))]) == 0  # unchanged -> no write
        assert ins([_row(10, t0 + timedelta(minutes=20))]) == 1
        assert latest().minute == 10
        assert ins([_row(5, t0 + timedelta(minutes=30))]) == 1  # reverted -> latest again
        assert latest().minute == 5
        assert conn.execute("select count(*) from staging.stop_changes "
                            "where stop_id = 'pytest-stop-1'").fetchone()[0] == 2
        raise RuntimeError("rollback")
