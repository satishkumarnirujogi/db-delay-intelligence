{{ config(materialized='view', tags=['live']) }}

-- One row, computed at query time, so DirectQuery cards are always current
-- (no time-zone maths in DAX).
with last_ok as (
    select job, max(finished_at) as finished_at
    from {{ source('ops', 'ingestion_runs') }}
    where status = 'success'
    group by job
),

usage as (
    select db_mb, storage_mb
    from {{ source('ops', 'platform_usage') }}
    order by measured_at desc
    limit 1
)

select
    (select round(extract(epoch from now() - finished_at) / 60)::int from last_ok where job = 'changes')
        as minutes_since_changes,
    (select round(extract(epoch from now() - finished_at) / 60)::int from last_ok where job = 'plan')
        as minutes_since_plan,
    (select round(extract(epoch from now() - finished_at) / 60)::int from last_ok where job = 'score')
        as minutes_since_score,
    (select count(*)::int from {{ source('ops', 'ingestion_runs') }}
        where status = 'failed' and started_at > now() - interval '24 hours')
        as failed_runs_24h,
    (select db_mb from usage)                                  as db_mb,
    (select storage_mb from usage)                             as storage_mb,
    500                                                        as db_limit_mb,
    1024                                                       as storage_limit_mb
