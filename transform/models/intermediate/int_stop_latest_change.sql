-- One row per stop: the last change fetched before the train left.
with changes as (
    select * from {{ ref('stg_db__stop_changes') }}
),

plan as (
    select stop_id, coalesce(planned_dep, planned_arr) as planned_event
    from {{ ref('stg_db__plan_stops') }}
),

ranked as (
    select
        c.*,
        row_number() over (partition by c.stop_id order by c.fetched_at desc) as rn
    from changes c
    join plan p using (stop_id)
    -- ignore changes fetched long after the train left
    where c.fetched_at <= coalesce(c.changed_dep, c.changed_arr, p.planned_event) + interval '15 minutes'
)

select
    stop_id,
    changed_arr,
    changed_dep,
    changed_platform,
    is_cancelled,
    fetched_at,
    loaded_at
from ranked
where rn = 1
