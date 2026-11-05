select
    stop_id,
    eva,
    changed_arr,
    changed_dep,
    changed_platform,
    is_cancelled,
    content_hash,
    fetched_at,
    loaded_at
from {{ source('db_raw', 'stop_changes') }}
