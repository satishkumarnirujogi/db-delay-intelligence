"""Anomaly SQL on synthetic history, inside a rolled-back transaction. Skipped without a database."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("PG_HOST") and not os.path.exists(".env"),
                                reason="needs a database")

NOW = "(now() at time zone 'Europe/Berlin')"
SETUP = f"""
insert into marts.agg_station_hour (service_date, service_hour, eva, train_category, departures,
  departures_not_cancelled, punctual_departures, cancellations, platform_changes, avg_dep_delay_min)
select {NOW}::date - w * 7, extract(hour from {NOW})::int, -1, 'ICE', 10, 10, 9, 0, 0, d
from (values (1, 2.0), (2, 3.0), (3, 2.0), (4, 3.0)) as h(w, d);

insert into marts.fact_stop_event (stop_id, eva, train_category, planned_dep, planned_event_at,
  service_date, service_hour, dep_delay_min, is_cancelled)
select 'pytest-anom-' || i, -1, 'ICE', now() - interval '1 minute', now() - interval '1 minute',
       {NOW}::date, extract(hour from {NOW})::int, 20, false
from generate_series(1, 6) i;
"""


def test_unusual_hour_raises_alert():
    from ingestion import loader
    from ml.anomalies import DETECT

    with loader.connect() as conn:
        if conn.execute("select to_regclass('ml.alerts')").fetchone()[0] is None:
            pytest.skip("ml tables not created")
        with pytest.raises(RuntimeError, match="rollback"), conn.transaction():
            conn.execute(SETUP)
            conn.execute(DETECT)
            row = conn.execute("""select current_value, baseline_median, robust_z, severity
                                  from ml.alerts where eva = -1 and metric = 'avg_delay_min'""").fetchone()
            assert row is not None
            current, median, z, severity = row
            assert current == 20 and median == 2.5  # median of 2, 3, 2, 3
            assert z >= 5 and severity == "critical"
            # a normal hour (no extra delay) must not alert on cancellations
            assert conn.execute("select count(*) from ml.alerts where eva = -1 and metric = 'cancel_rate'"
                                ).fetchone()[0] == 0
            raise RuntimeError("rollback")
