-- ML tables written by Python (ml/score.py). Safe to re-run.
-- Features are logged ONCE per stop, 25-65 min before departure, so training only sees
-- what was known at prediction time (no leakage).
create table if not exists ml.feature_log (
  stop_id                    text primary key,
  logged_at                  timestamptz not null default now(),
  eva                        int  not null,
  train_category             text,
  line                       text,
  planned_dep                timestamptz not null,
  minutes_to_departure       int,
  current_delay_min          int,
  has_realtime               boolean,
  station_avg_delay_30m      numeric(6,2),
  station_cancellations_60m  int,
  upstream_delay_min         int,
  hour_of_day                int,
  iso_weekday                int,
  temperature_c              real,
  precipitation_mm           real,
  snowfall_cm                real,
  wind_gust_kmh              real
);

create index if not exists ix_feature_log_logged on ml.feature_log (logged_at);
