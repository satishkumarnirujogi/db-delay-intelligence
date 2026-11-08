{{ config(materialized='view', tags=['daily']) }}

-- Last 7 days of pipeline jobs for the Pipeline health page (DirectQuery).
select
    run_id::text                                           as run_id,
    job,
    status,
    (started_at at time zone 'Europe/Berlin')              as started_local,
    round(extract(epoch from finished_at - started_at))::int as duration_s,
    api_calls,
    rows_inserted,
    error
from {{ source('ops', 'ingestion_runs') }}
where started_at > now() - interval '7 days'
