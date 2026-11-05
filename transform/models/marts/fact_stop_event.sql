{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='stop_id',
    on_schema_change='fail',
    tags=['live'],
    indexes=[
        {'columns': ['stop_id'], 'unique': True},
        {'columns': ['loaded_at']},
        {'columns': ['service_date', 'eva']},
    ]
) }}

select
    stop_id,
    eva,
    train_category,
    train_number,
    line,
    planned_platform,
    planned_arr,
    planned_dep,
    actual_arr,
    actual_dep,
    planned_event_at,
    service_date,
    service_hour,
    dep_delay_min,
    arr_delay_min,
    has_realtime,
    is_cancelled,
    is_punctual,
    platform_changed,
    delay_band,
    loaded_at
from {{ ref('int_stop_enriched') }}
{% if is_incremental() %}
-- 3-hour lookback catches late changes to trains already in the table
where loaded_at > (select max(loaded_at) - interval '3 hours' from {{ this }})
{% endif %}
