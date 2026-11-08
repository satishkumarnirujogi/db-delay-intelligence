{{ config(materialized='view', tags=['daily']) }}

-- Power BI "Alerts": last 7 days of unusual station-hours, newest first.
select
    a.eva,
    s.station_name,
    a.service_date,
    a.service_hour,
    a.metric,
    case a.metric when 'avg_delay_min' then 'Average delay (min)' else 'Cancellation rate' end as metric_label,
    round(a.current_value::numeric, 2)::numeric(10,2)   as current_value,
    round(a.baseline_median::numeric, 2)::numeric(10,2) as baseline_median,
    round(a.robust_z::numeric, 1)::numeric(6,1)         as robust_z,
    a.departures,
    a.severity,
    (a.detected_at at time zone 'Europe/Berlin')        as detected_local
from {{ source('ml', 'alerts') }} a
join {{ ref('dim_station') }} s using (eva)
where a.service_date >= (now() at time zone 'Europe/Berlin')::date - 7
