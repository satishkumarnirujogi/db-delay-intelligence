with joined as (
    select
        p.stop_id,
        p.eva,
        p.train_category,
        p.train_number,
        p.line,
        p.planned_platform,
        p.planned_arr,
        p.planned_dep,
        coalesce(c.changed_arr, p.planned_arr)  as actual_arr,
        coalesce(c.changed_dep, p.planned_dep)  as actual_dep,
        (c.stop_id is not null)                 as has_realtime,
        coalesce(c.is_cancelled, false)         as is_cancelled,
        coalesce(c.changed_platform is not null and c.changed_platform <> p.planned_platform, false)
                                                as platform_changed,
        round(extract(epoch from (coalesce(c.changed_dep, p.planned_dep) - p.planned_dep)) / 60)::int
                                                as dep_delay_min,
        round(extract(epoch from (coalesce(c.changed_arr, p.planned_arr) - p.planned_arr)) / 60)::int
                                                as arr_delay_min,
        greatest(p.loaded_at, coalesce(c.loaded_at, p.loaded_at)) as loaded_at
    from {{ ref('stg_db__plan_stops') }} p
    left join {{ ref('int_stop_latest_change') }} c using (stop_id)
)

select
    *,
    coalesce(planned_dep, planned_arr)                                   as planned_event_at,
    ((coalesce(planned_dep, planned_arr) at time zone 'Europe/Berlin'))::date as service_date,
    extract(hour from (coalesce(planned_dep, planned_arr) at time zone 'Europe/Berlin'))::int
                                                                         as service_hour,
    -- DB definition: under 6 minutes late counts as punctual
    (not is_cancelled and coalesce(dep_delay_min, arr_delay_min) < 6)    as is_punctual,
    case
        when is_cancelled then 'cancelled'
        when coalesce(dep_delay_min, arr_delay_min) < 6 then 'on time (<6)'
        when coalesce(dep_delay_min, arr_delay_min) < 16 then '6-15 min'
        when coalesce(dep_delay_min, arr_delay_min) < 31 then '16-30 min'
        else '30+ min'
    end                                                                  as delay_band
from joined
