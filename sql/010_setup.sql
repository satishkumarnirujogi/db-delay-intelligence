-- Run once in Supabase → SQL Editor. Safe to re-run (all "if not exists").
create schema if not exists staging;
create schema if not exists intermediate;
create schema if not exists marts;
create schema if not exists ml;
create schema if not exists ops;

create table if not exists staging.plan_stops (
  stop_id          text primary key,
  eva              int  not null,
  train_category   text,
  train_number     text,
  line             text,
  planned_arr      timestamptz,
  planned_dep      timestamptz,
  planned_platform text,
  route_ppth       text,
  fetched_at       timestamptz not null,
  loaded_at        timestamptz not null default now()
);

create table if not exists staging.stop_changes (
  stop_id          text not null,
  eva              int  not null,
  changed_arr      timestamptz,
  changed_dep      timestamptz,
  changed_platform text,
  is_cancelled     boolean not null default false,
  content_hash     text not null,
  fetched_at       timestamptz not null,
  loaded_at        timestamptz not null default now(),
  primary key (stop_id, content_hash)
);

create table if not exists staging.weather_hourly (
  eva              int not null,
  observed_hour    timestamptz not null,
  temperature_c    numeric,
  precipitation_mm numeric,
  snowfall_cm      numeric,
  wind_gust_kmh    numeric,
  fetched_at       timestamptz not null,
  loaded_at        timestamptz not null default now(),
  primary key (eva, observed_hour)
);

create table if not exists ops.ingestion_runs (
  run_id        uuid primary key default gen_random_uuid(),
  job           text not null,
  started_at    timestamptz not null,
  finished_at   timestamptz,
  api_calls     int,
  rows_inserted int,
  status        text,
  error         text
);

create index if not exists ix_changes_loaded on staging.stop_changes (loaded_at);
create index if not exists ix_plan_loaded    on staging.plan_stops (loaded_at);

-- Supabase exposes the "public" schema via its REST API; these schemas are not exposed,
-- so no RLS is needed here. Only the pipeline (postgres user) and powerbi_reader touch them.
