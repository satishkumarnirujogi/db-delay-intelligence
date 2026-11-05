select
    eva,
    observed_hour,
    temperature_c::float    as temperature_c,
    precipitation_mm::float as precipitation_mm,
    snowfall_cm::float      as snowfall_cm,
    wind_gust_kmh::float    as wind_gust_kmh,
    fetched_at,
    loaded_at
from {{ source('db_raw', 'weather_hourly') }}
