{{ config(materialized='view', tags=['daily']) }}

select
    eva,
    observed_hour,
    (observed_hour at time zone 'Europe/Berlin')::date             as service_date,
    extract(hour from observed_hour at time zone 'Europe/Berlin')::int as service_hour,
    temperature_c,
    precipitation_mm,
    snowfall_cm,
    wind_gust_kmh
from {{ ref('stg_meteo__weather_hourly') }}
