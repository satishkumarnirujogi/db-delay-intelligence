{{ config(materialized='view', schema='ml', tags=['live']) }}

-- Features for departures in the next 2 hours, computed from what is known right now.
-- ml/score.py logs each stop once (25-65 min before departure) into ml.feature_log.
with f as (
    select * from {{ ref('fact_stop_event') }}
    where service_date between (now() at time zone 'Europe/Berlin')::date - 1
                           and (now() at time zone 'Europe/Berlin')::date + 1
),

upcoming as (
    select * from f
    where planned_dep between now() and now() + interval '2 hours'
      and not is_cancelled
),

station_recent as (
    select
        eva,
        avg(dep_delay_min) filter (where not is_cancelled
                                   and planned_dep between now() - interval '30 minutes' and now())
            as station_avg_delay_30m,
        count(*) filter (where is_cancelled
                         and planned_event_at between now() - interval '60 minutes' and now())
            as station_cancellations_60m
    from f
    group by eva
)

select
    u.stop_id,
    u.eva,
    u.train_category,
    u.line,
    u.planned_dep,
    round(extract(epoch from u.planned_dep - now()) / 60)::int          as minutes_to_departure,
    u.dep_delay_min                                                     as current_delay_min,
    u.has_realtime,
    round(coalesce(sr.station_avg_delay_30m, 0), 2)::numeric(6,2)       as station_avg_delay_30m,
    coalesce(sr.station_cancellations_60m, 0)::int                      as station_cancellations_60m,
    up.upstream_delay_min,
    u.service_hour                                                      as hour_of_day,
    extract(isodow from u.service_date)::int                            as iso_weekday,
    w.temperature_c::real                                               as temperature_c,
    w.precipitation_mm::real                                            as precipitation_mm,
    w.snowfall_cm::real                                                 as snowfall_cm,
    w.wind_gust_kmh::real                                               as wind_gust_kmh
from upcoming u
left join station_recent sr using (eva)
-- the same train's latest known delay at the nearest earlier tracked station
left join lateral (
    select coalesce(p.dep_delay_min, p.arr_delay_min) as upstream_delay_min
    from f p
    where p.train_category = u.train_category
      and p.train_number = u.train_number
      and p.service_date = u.service_date
      and p.eva <> u.eva
      and p.planned_event_at < u.planned_event_at
      and p.has_realtime
    order by p.planned_event_at desc
    limit 1
) up on true
left join {{ ref('stg_meteo__weather_hourly') }} w
    on w.eva = u.eva and w.observed_hour = date_trunc('hour', u.planned_dep)
