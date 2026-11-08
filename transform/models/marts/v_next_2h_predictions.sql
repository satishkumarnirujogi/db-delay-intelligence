{{ config(materialized='view', tags=['daily']) }}

-- Power BI "Next 2 hours": upcoming departures with the latest model prediction.
select
    f.stop_id,
    f.eva,
    s.station_name,
    f.train_category,
    f.train_number,
    f.line,
    f.planned_platform,
    (f.planned_dep at time zone 'Europe/Berlin')                       as planned_dep_local,
    round(extract(epoch from f.planned_dep - now()) / 60)::int          as minutes_to_departure,
    f.dep_delay_min                                                    as current_delay_min,
    round(p.pred_delay_min::numeric, 1)::numeric(6,1)                  as pred_delay_min,
    round(p.p_late::numeric, 3)::numeric(4,3)                          as p_late,
    case when p.p_late >= 0.6 then 'High'
         when p.p_late >= 0.3 then 'Medium'
         else 'Low' end                                                as risk_band,
    p.model_version,
    (p.scored_at at time zone 'Europe/Berlin')                         as scored_local
from {{ ref('fact_stop_event') }} f
join {{ source('ml', 'predictions') }} p using (stop_id)
join {{ ref('dim_station') }} s using (eva)
where f.planned_dep between now() and now() + interval '2 hours'
  and not f.is_cancelled
