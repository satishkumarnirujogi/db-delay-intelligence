{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['service_date', 'eva', 'service_hour', 'train_category'],
    on_schema_change='fail',
    tags=['daily']
) }}

-- Departures only. Kept long-term; fact_stop_event detail is trimmed after 90 days.
select
    service_date,
    service_hour,
    eva,
    train_category,
    count(*)::int                                          as departures,
    count(*) filter (where not is_cancelled)::int           as departures_not_cancelled,
    count(*) filter (where is_punctual)::int                as punctual_departures,
    count(*) filter (where is_cancelled)::int               as cancellations,
    count(*) filter (where platform_changed)::int           as platform_changes,
    round(avg(dep_delay_min) filter (where not is_cancelled), 2)::numeric(8,2) as avg_dep_delay_min
from {{ ref('fact_stop_event') }}
where planned_dep is not null
  and planned_dep < now()  -- only departures that have happened
{% if is_incremental() %}
  and service_date >= (select max(service_date) - 2 from {{ this }})
{% endif %}
group by 1, 2, 3, 4
