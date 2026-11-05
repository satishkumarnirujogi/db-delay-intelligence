{{ config(tags=['daily']) }}

-- One row per train category seen in the data, grouped for the dashboard.
select distinct
    train_category,
    case
        when train_category in ('ICE', 'IC', 'EC', 'ECE', 'RJ', 'RJX', 'FLX', 'NJ', 'TGV', 'EUR', 'EST', 'WB')
            then 'Long distance'
        when train_category = 'S' then 'S-Bahn'
        else 'Regional'
    end as train_group
from {{ ref('fact_stop_event') }}
where train_category is not null
