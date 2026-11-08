{{ config(materialized='view', schema='ml', tags=['daily']) }}

-- Daily model quality from the prediction made at logging time (25-65 min before departure)
-- vs the actual delay. "persistence" = the train stays as late as it was at logging time.
select
    (planned_dep at time zone 'Europe/Berlin')::date                          as service_date,
    model_version,
    count(*)::int                                                             as departures,
    round(avg(abs(actual_delay_min - pred_delay_min))::numeric, 2)::numeric(8,2) as mae_model,
    round(avg(abs(actual_delay_min - coalesce(current_delay_min, 0)))::numeric, 2)::numeric(8,2) as mae_persistence,
    round(avg((actual_delay_min >= 6)::int)::numeric, 3)::numeric(5,3) as share_late_actual,
    round(avg(p_late)::numeric, 3)::numeric(5,3) as avg_p_late,
    count(*) filter (where p_late >= 0.5 and actual_delay_min >= 6)::int      as flagged_and_late,
    count(*) filter (where p_late >= 0.5)::int                                as flagged,
    count(*) filter (where actual_delay_min >= 6)::int                        as late
from {{ source('ml', 'feature_log') }}
where labeled_at is not null and not actual_cancelled and pred_delay_min is not null
group by 1, 2
