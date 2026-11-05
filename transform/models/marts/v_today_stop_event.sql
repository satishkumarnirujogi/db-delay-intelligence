{{ config(materialized='view', tags=['live']) }}

-- Small, live slice for Power BI DirectQuery: today's stops in Berlin time.
select f.*, s.station_name
from {{ ref('fact_stop_event') }} f
join {{ ref('dim_station') }} s using (eva)
where f.service_date = (now() at time zone 'Europe/Berlin')::date
