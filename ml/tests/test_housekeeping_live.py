"""The retention delete must never remove a day that has no Parquet export.
Runs against the real database inside a rolled-back transaction."""
import os
from datetime import date

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("PG_HOST") and not os.path.exists(".env"),
                                reason="needs a database")


def test_fact_delete_only_exported_days():
    from ingestion import loader
    from ml.housekeeping import DELETES

    sql = next(s for t, s, _ in DELETES if t == "marts.fact_stop_event")
    old = date(2020, 1, 1)
    with loader.connect() as conn:
        if conn.execute("select to_regclass('marts.fact_stop_event')").fetchone()[0] is None:
            pytest.skip("dbt models not built")
        with pytest.raises(RuntimeError, match="rollback"), conn.transaction():
            conn.execute("""insert into marts.fact_stop_event (stop_id, eva, planned_event_at, service_date)
                                values ('pytest-old', 1, '2020-01-01 12:00+00', %s)""", (old,))
            assert conn.execute(sql, {"days": 30, "exported": []}).rowcount == 0
            assert conn.execute(sql, {"days": 30, "exported": [old]}).rowcount == 1
            raise RuntimeError("rollback")
