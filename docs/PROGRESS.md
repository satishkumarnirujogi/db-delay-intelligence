# Progress

| Step | What | Status |
|---|---|---|
| 0 | Repo scaffold, .env, venv (Python 3.11) | ✅ |
| 1 | `ingestion/explore.py` → stations seed, fixtures, `docs/api_notes.md` | ✅ |
| 2 | `sql/010_setup.sql`, `sql/020_powerbi_reader.sql`, buckets `bronze` + `ml` | ✅ verified live |
| 3 | Ingestion: `db_client`, `meteo_client`, `parser`, `storage`, `loader`, `run` + 8 tests | ✅ verified live |
| 4 | `pipeline.yml` + cron-job.org trigger | ✅ running every 10 min |
| 5 | dbt: staging → intermediate → marts, 2 unit tests, 22 data tests, contracts, exposure; `daily.yml` | ✅ green locally (39/39) |
| 6a | Feature log: `ml_features_upcoming` view + `ml.feature_log` + `ml/score.py` | ✅ logging since 2026-11-05 |
| 6b | `ml/train.py` (weekly, `train.yml`), predictions in `ml/score.py`, `ml/anomalies.py`, `ml_prediction_eval`, `v_next_2h_predictions`, `v_alerts` | ✅ first model promoted 2026-11-08 (see below); anomalies silent until ~2026-11-29 |
| 7 | `ml/housekeeping.py` (Parquet export, retention, raw cleanup, `ops.platform_usage`) in `daily.yml`; `ci.yml` | ✅ housekeeping verified live; CI verified on first GitHub run |
| 8 | Power BI: `v_today_stop_event` local-time + `is_departed` columns, `v_pipeline_runs`, `v_pipeline_status`; build guide `powerbi/README.md` (pages 1, 2, 7) | 🟡 data side done; dashboard to build in Desktop |
| 9 | README polish | ⏳ |

## Decisions made while building

- **Berlin Hbf uses EVA 8098160** (Berlin Hbf "tief"), not 8011160: the main EVA returns an empty
  timetable; the ICE/RE trains are listed under the meta EVA. S-Bahn/bus meta EVAs of other
  stations are left out (one EVA per station = 15 calls per run). Some main EVAs (Köln,
  Düsseldorf, Nürnberg, Frankfurt) still include S-Bahn trains; filter them in dbt if needed.
- **`is_cancelled` = the stop's departure is cancelled** (arrival for terminating trains). A train
  whose arrival is cancelled but which still departs (starts here) is not a cancelled departure.
- Message-only `<s>` entries in `fchg` (no `<ar>`/`<dp>`) are skipped.
- Weather: last 6 h + next 3 h per hourly run, upserted (observations replace earlier forecasts).
- Station coordinates are approximate (hand-entered); only used for the weather grid cell.
- **Change dedupe fix:** the guide's `on conflict do nothing` loses reverts (delay 5 → 10 → 5 would
  stay at 10). The insert now refreshes `fetched_at` of a returning state, only when it is not
  already the latest for that stop (no write for unchanged trains). Tested in `test_loader_live.py`.
- dbt: no `dbt_utils` package (two small generic tests in `transform/tests/generic/` instead),
  so no `dbt deps` network call every 10 min. Replacement buses (`Bus`) are filtered in staging.
- `dim_train` groups categories into Long distance / Regional / S-Bahn.
- `agg_station_hour` is incremental (last 3 service dates rebuilt daily) so history survives the
  trim of `fact_stop_event`.
- **Retention (from first-day measurements):** stop_changes ~15 MB/day, fact ~4 MB/day, raw fchg
  files ~70 MB/day. The guide's 7-day staging + 90-day fact would pass 500 MB, so: staging 3 days,
  fact detail 30 days, feature_log 60 days, raw files 3 days, weather 7 days. Fact/feature rows
  are deleted only for days whose Parquet export exists (`history/<table>/service_date=…/`).
  Expected steady state: database ~250–300 MB, storage ~250 MB + ~165 MB/year Parquet.
- **Never `--full-refresh` `fact_stop_event`:** staging only holds 3 days, so a rebuild would drop
  older detail (it is still in Parquet).
- `daily.yml` has its own concurrency group: in the shared group a queued daily run would be
  cancelled by the next 10-min trigger.
- CI runs on PRs and pushes to `main` against a throwaway Postgres 17 (`PG_SSLMODE=disable`).

## First live run (2026-11-05)

`changes`: 15 calls, ~19 s, 6,281 rows (2nd run: 43 new rows, 0 duplicates) ·
`hourly`: 30 calls, ~36 s, 1,017 plan stops + 135 weather rows · DB size 13 MB.

## AI layer (2026-11-08)

- **Labels live in `ml.feature_log`** (`actual_delay_min`, filled 30 min after departure) together with
  the prediction made at logging time, so training, evaluation and Parquet history use one table and
  survive the 30-day trim of `fact_stop_event`.
- **First model `20261108-1811`** (4 days of data; test = last quarter, 3,926 departures, never shuffled):

  | | MAE (min) | AUC (6+ min late) |
  |---|---|---|
  | Baseline: median per station × hour × category | 5.08 | 0.68 |
  | Persistence: "stays as late as now" | 2.92 | – |
  | **LightGBM** | **2.88** | **0.83** (precision 0.70, recall 0.48 at p ≥ 0.5) |

  Honest read: most of the signal is the current delay; the model's main gain over persistence is the
  calibrated *probability* of being late. Promotion rule: beat the baseline MAE with ≥ 500 test rows.
- Anomalies: robust z-score vs the same station/weekday/hour 1–4 weeks back; needs 3 of those 4 days,
  so the first real alerts can appear around 2026-11-26/29. Logic tested on synthetic history.
- **Views are rebuilt daily, not every 10 min.** Re-creating views every run made concurrent readers
  (Power BI DirectQuery, `score.py`) briefly fail with "relation does not exist". The 10-min run now only
  updates `fact_stop_event` (updated in place). After changing a view's SQL, run `daily.yml` by hand
  (Actions → daily → Run workflow) or `dbt build` locally.
- Model files (~1 MB) are cached on the GitHub runner (`actions/cache`); only `meta.json` is downloaded
  per run, saving ~1.4 GB/month of the 5 GB Supabase egress.
