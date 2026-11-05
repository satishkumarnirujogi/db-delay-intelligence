{{ config(materialized='view', tags=['live']) }}

-- Small, live slice for Power BI DirectQuery: today's stops in Berlin time.
-- *_local columns are Berlin wall-clock times (timestamp without zone) for display.
select
    f.*,
    s.station_name,
    (f.planned_dep at time zone 'Europe/Berlin')      as planned_dep_local,
    (f.actual_dep at time zone 'Europe/Berlin')       as actual_dep_local,
    (f.planned_event_at at time zone 'Europe/Berlin') as planned_event_local,
    -- departures that have left (punctuality counts only these); decided by the DB clock, not the laptop's
    (f.planned_dep is not null and coalesce(f.actual_dep, f.planned_dep) <= now()) as is_departed
from {{ ref('fact_stop_event') }} f
join {{ ref('dim_station') }} s using (eva)
where f.service_date = (now() at time zone 'Europe/Berlin')::date
