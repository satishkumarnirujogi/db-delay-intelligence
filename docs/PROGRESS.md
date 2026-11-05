# Progress

| Step | What | Status |
|---|---|---|
| 0 | Repo scaffold, .env, venv (Python 3.11) | ✅ |
| 1 | `ingestion/explore.py` → stations seed, fixtures, `docs/api_notes.md` | ✅ |
| 2 | `sql/010_setup.sql`, `sql/020_powerbi_reader.sql`, buckets `bronze` + `ml` | ✅ verified live |
| 3 | Ingestion: `db_client`, `meteo_client`, `parser`, `storage`, `loader`, `run` + 8 tests | ✅ verified live |
| 4 | `pipeline.yml` + cron-job.org trigger | 🟡 workflow written; push, secrets, cron-job.org pending |
| 5 | dbt | ⏳ next |
| 6 | ML | ⏳ needs 2–3 weeks of data |
| 7 | Housekeeping + CI | ⏳ |
| 8 | Power BI | ⏳ |
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

## First live run (2026-11-05)

`changes`: 15 calls, ~19 s, 6,281 rows (2nd run: 43 new rows, 0 duplicates) ·
`hourly`: 30 calls, ~36 s, 1,017 plan stops + 135 weather rows · DB size 13 MB.
