"""Every run: flag station-hours with unusual delays or cancellations -> ml.alerts.
    python -m ml.anomalies

Robust z-score: (current - median) / (1.4826 * MAD) against the same station, weekday and hour on
the last 4 weeks (marts.agg_station_hour). Median/MAD are not thrown off by one bad day.
Needs at least 3 of those 4 history days, so it stays silent for the first 3 weeks.
Runs entirely in SQL inside the database (no data pulled out).
"""
from ingestion import loader

DETECT = """
with now_berlin as (
    select (now() at time zone 'Europe/Berlin')::date as d,
           extract(hour from now() at time zone 'Europe/Berlin')::int as h
),
current_hours as (   -- the running hour and the one before, per station
    select f.eva, f.service_date, f.service_hour,
           count(*)::int as departures,
           avg(f.dep_delay_min) filter (where not f.is_cancelled) as avg_delay_min,
           avg(f.is_cancelled::int)::float as cancel_rate
    from marts.fact_stop_event f, now_berlin n
    where f.service_date = n.d and f.service_hour in (n.h, n.h - 1)
      and f.planned_dep is not null and f.planned_dep <= now()
    group by 1, 2, 3
    having count(*) >= 5
),
history as (         -- same station, hour and weekday, 1-4 weeks back, all train categories
    select a.eva, c.service_date, c.service_hour,
           sum(a.avg_dep_delay_min * a.departures_not_cancelled)
               / nullif(sum(a.departures_not_cancelled), 0) as avg_delay_min,
           sum(a.cancellations)::float / nullif(sum(a.departures), 0) as cancel_rate
    from current_hours c
    join marts.agg_station_hour a
      on a.eva = c.eva and a.service_hour = c.service_hour
     and a.service_date in (c.service_date - 7, c.service_date - 14, c.service_date - 21, c.service_date - 28)
    group by a.eva, c.service_date, c.service_hour, a.service_date
),
long as (            -- one row per metric
    select c.eva, c.service_date, c.service_hour, c.departures, m.metric, m.cur, m.hist
    from current_hours c
    join history h using (eva, service_date, service_hour)
    cross join lateral (values ('avg_delay_min', c.avg_delay_min, h.avg_delay_min),
                               ('cancel_rate',   c.cancel_rate,   h.cancel_rate))
        as m(metric, cur, hist)
),
med as (
    select eva, service_date, service_hour, metric, max(departures) as departures, max(cur) as cur,
           count(hist) as n_hist,
           percentile_cont(0.5) within group (order by hist) as median
    from long group by 1, 2, 3, 4
),
mad as (
    select m.*,
           (select percentile_cont(0.5) within group (order by abs(l.hist - m.median))
            from long l where (l.eva, l.service_date, l.service_hour, l.metric)
                            = (m.eva, m.service_date, m.service_hour, m.metric)) as mad
    from med m
),
scored as (
    select *,
           (cur - median) / (1.4826 * greatest(mad, case metric when 'avg_delay_min' then 1.0 else 0.02 end))
               as robust_z
    from mad
    where n_hist >= 3 and cur is not null and median is not null
)
insert into ml.alerts (eva, service_date, service_hour, metric, current_value, baseline_median,
                       robust_z, departures, severity)
select eva, service_date, service_hour, metric, cur, median, robust_z, departures,
       case when robust_z >= 5 then 'critical' else 'warning' end
from scored
where robust_z >= 3          -- only unusually BAD hours
on conflict (eva, service_date, service_hour, metric) do update set
  current_value = excluded.current_value, baseline_median = excluded.baseline_median,
  robust_z = excluded.robust_z, departures = excluded.departures, severity = excluded.severity,
  detected_at = now()
"""


def main() -> None:
    with loader.connect() as conn, conn.transaction():
        n = conn.execute(DETECT).rowcount
    print(f"anomalies: {n} alert rows written/updated")


if __name__ == "__main__":
    main()
