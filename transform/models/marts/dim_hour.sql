{{ config(tags=['daily']) }}

select
    h                                       as service_hour,
    lpad(h::text, 2, '0') || ':00'          as hour_label,
    case when h between 6 and 9 or h between 16 and 19 then 'Peak' else 'Off-peak' end as day_part
from generate_series(0, 23) as h
