-- Daily size snapshot for the Pipeline health page. Safe to re-run.
create table if not exists ops.platform_usage (
  measured_at     timestamptz primary key default now(),
  db_mb           numeric(10,1) not null,
  storage_mb      numeric(10,1) not null,
  fact_rows       bigint,
  staging_rows    bigint,
  feature_rows    bigint
);
