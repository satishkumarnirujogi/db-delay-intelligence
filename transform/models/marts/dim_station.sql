{{ config(tags=['daily']) }}

select eva, station_name, lat, lon, is_berlin
from {{ ref('stations') }}
