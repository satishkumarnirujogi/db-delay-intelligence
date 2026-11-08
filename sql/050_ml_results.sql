-- AI layer result tables (written by ml/score.py, ml/train.py, ml/anomalies.py). Safe to re-run.

-- Labels and the point-in-time prediction live next to the features, so training, evaluation
-- and the Parquet history all come from one table.
alter table ml.feature_log add column if not exists actual_delay_min int;
alter table ml.feature_log add column if not exists actual_cancelled boolean;
alter table ml.feature_log add column if not exists labeled_at timestamptz;
alter table ml.feature_log add column if not exists pred_delay_min real;
alter table ml.feature_log add column if not exists p_late real;
alter table ml.feature_log add column if not exists model_version text;
create index if not exists ix_feature_log_unlabeled on ml.feature_log (planned_dep) where labeled_at is null;

-- Latest prediction per upcoming departure (Power BI page "Next 2 hours").
create table if not exists ml.predictions (
  stop_id         text primary key,
  scored_at       timestamptz not null default now(),
  pred_delay_min  real not null,
  p_late          real not null,
  model_version   text not null
);

-- One row per weekly training run.
create table if not exists ml.model_runs (
  model_version     text primary key,
  trained_at        timestamptz not null default now(),
  train_rows        int,
  test_rows         int,
  test_from         timestamptz,
  mae_model         real,
  mae_baseline      real,   -- median delay per station x hour x train category
  mae_persistence   real,   -- "stays as late as it is now"
  auc_model         real,
  auc_baseline      real,
  precision_late    real,
  recall_late       real,
  promoted          boolean not null,
  note              text
);

-- Unusual station-hours (robust z-score vs the same station/weekday/hour, last 4 weeks).
create table if not exists ml.alerts (
  eva             int not null,
  service_date    date not null,
  service_hour    int not null,
  metric          text not null,        -- 'avg_delay_min' | 'cancel_rate'
  current_value   real not null,
  baseline_median real not null,
  robust_z        real not null,
  departures      int not null,
  severity        text not null,        -- 'warning' (z>=3) | 'critical' (z>=5)
  detected_at     timestamptz not null default now(),
  primary key (eva, service_date, service_hour, metric)
);
