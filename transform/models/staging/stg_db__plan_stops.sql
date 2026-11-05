select
    stop_id,
    eva,
    train_category,
    train_number,
    line,
    planned_arr,
    planned_dep,
    planned_platform,
    route_ppth,
    fetched_at,
    loaded_at
from {{ source('db_raw', 'plan_stops') }}
-- replacement buses are not trains; they would distort punctuality
where coalesce(upper(train_category), '') <> 'BUS'
