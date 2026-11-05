{{ config(tags=['daily']) }}

select
    d::date                              as date_day,
    extract(isodow from d)::int          as iso_weekday,
    to_char(d, 'Dy')                     as weekday_name,
    extract(isodow from d) in (6, 7)     as is_weekend,
    extract(month from d)::int           as month_num,
    to_char(d, 'YYYY-MM')                as year_month,
    extract(isoyear from d)::int * 100 + extract(week from d)::int as iso_year_week
from generate_series(date '2026-01-01', date '2028-12-31', interval '1 day') as d
