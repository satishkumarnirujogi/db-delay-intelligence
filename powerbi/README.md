# Power BI — build guide

Builds pages **1 Network now**, **2 Station drill-down** and **7 Pipeline health** (pages 3–6 need
the model from Step 6b). Everything reads the `marts` schema as the read-only `powerbi_reader` user.

All times in `*_local` columns are already Berlin wall-clock time; "has the train left" and
"minutes since last load" are decided by the database clock. So no time-zone maths in DAX.

---

## 1. Connect

1. Power BI Desktop → **Get data → PostgreSQL database**
2. **Server:** `aws-1-eu-central-1.pooler.supabase.com:5432` · **Database:** `postgres`
3. **Data connectivity mode:** DirectQuery (you change single tables to Import/Dual later)
4. Credentials → **Database** tab
   - User name: `powerbi_reader.cfictjtkdxezatyznkcp`
   - Password: the one you set when running `sql/020_powerbi_reader.sql`
5. If you get a **certificate / SSL error**: Supabase → Project Settings → Database → **SSL
   Configuration → Download certificate**. Double-click the `.crt` → Install Certificate →
   Current User → *Place all certificates in:* **Trusted Root Certification Authorities** → Finish.
   Restart Power BI Desktop and connect again.

In the Navigator, tick these and click **Load**:

| Navigator name | Rename to (Model view → double-click the table name) |
|---|---|
| `marts.v_today_stop_event` | `v_today_stop_event` |
| `marts.agg_station_hour` | `agg_station_hour` |
| `marts.dim_station` | `dim_station` |
| `marts.dim_train` | `dim_train` |
| `marts.dim_date` | `dim_date` |
| `marts.dim_hour` | `dim_hour` |
| `marts.v_pipeline_status` | `v_pipeline_status` |
| `marts.v_pipeline_runs` | `v_pipeline_runs` |

The DAX below uses the short names.

## 2. Storage modes (Model view → select table → Properties → Advanced → Storage mode)

| Table | Mode | Why |
|---|---|---|
| `v_today_stop_event`, `v_pipeline_status`, `v_pipeline_runs` | **DirectQuery** | must be live |
| `agg_station_hour` | **Import** | history, fast; refreshed when you click Refresh |
| `dim_station`, `dim_train`, `dim_date`, `dim_hour` | **Dual** | small; filter both live and imported tables without "limited" relationships |

## 3. Relationships (Model view; all many-to-one, single direction, dim → fact)

| From (many) | To (one) |
|---|---|
| `v_today_stop_event[eva]` | `dim_station[eva]` |
| `v_today_stop_event[train_category]` | `dim_train[train_category]` |
| `v_today_stop_event[service_hour]` | `dim_hour[service_hour]` |
| `agg_station_hour[eva]` | `dim_station[eva]` |
| `agg_station_hour[train_category]` | `dim_train[train_category]` |
| `agg_station_hour[service_hour]` | `dim_hour[service_hour]` |
| `agg_station_hour[service_date]` | `dim_date[date_day]` |

Then: select `dim_date` → **Mark as date table** → `date_day`.
`v_pipeline_status` and `v_pipeline_runs` stay unrelated.

Data categories (Column tools): `dim_station[lat]` → **Latitude**, `dim_station[lon]` → **Longitude**.

## 4. Measures

Create a measure table: Home → **Enter data** → name it `_Measures` → Load. Then add each measure
(Home → New measure). Format `%` measures as Percentage, 1 decimal.

```dax
Departures =
CALCULATE ( COUNTROWS ( v_today_stop_event ), v_today_stop_event[is_departed] = TRUE () )

Departures Not Cancelled =
CALCULATE ( [Departures], v_today_stop_event[is_cancelled] = FALSE () )

On-time Departures =
CALCULATE ( [Departures], v_today_stop_event[is_punctual] = TRUE () )

Punctuality % =
DIVIDE ( [On-time Departures], [Departures Not Cancelled] )

Avg Delay (min) =
CALCULATE (
    AVERAGE ( v_today_stop_event[dep_delay_min] ),
    v_today_stop_event[is_departed] = TRUE (),
    v_today_stop_event[is_cancelled] = FALSE ()
)

Cancellations =
CALCULATE ( [Departures], v_today_stop_event[is_cancelled] = TRUE () )

Platform Changes =
CALCULATE ( COUNTROWS ( v_today_stop_event ), v_today_stop_event[platform_changed] = TRUE () )

Live Data Coverage % =
DIVIDE (
    CALCULATE ( [Departures], v_today_stop_event[has_realtime] = TRUE () ),
    [Departures]
)

History Punctuality % =
DIVIDE ( SUM ( agg_station_hour[punctual_departures] ),
         SUM ( agg_station_hour[departures_not_cancelled] ) )

History Punctuality % (same weekday last week) =
VAR _today = TODAY ()
RETURN
    CALCULATE ( [History Punctuality %], dim_date[date_day] = _today - 7 )

Minutes Since Last Load = MAX ( v_pipeline_status[minutes_since_changes] )

Pipeline Status =
IF ( [Minutes Since Last Load] <= 20 && MAX ( v_pipeline_status[failed_runs_24h] ) = 0,
     "Healthy", IF ( [Minutes Since Last Load] <= 60, "Degraded", "Down" ) )

Failed Runs (24h) = MAX ( v_pipeline_status[failed_runs_24h] )

DB Used % = DIVIDE ( MAX ( v_pipeline_status[db_mb] ), MAX ( v_pipeline_status[db_limit_mb] ) )

Storage Used % =
DIVIDE ( MAX ( v_pipeline_status[storage_mb] ), MAX ( v_pipeline_status[storage_limit_mb] ) )
```

`History Punctuality % (same weekday last week)` uses `TODAY()` (your laptop's date); fine for a
date-level comparison. It shows blank until 7 days of history exist.

## 5. Pages

Theme tip: View → Themes → pick one, then use red for "late", green for "on time".

### Page 1 — Network now
| Visual | Fields |
|---|---|
| 4 × **Card** | `Punctuality %`, `Avg Delay (min)`, `Cancellations`, `Platform Changes` |
| **Card** (small) | `Live Data Coverage %` |
| **Map** (or Azure Map) | Latitude `dim_station[lat]`, Longitude `dim_station[lon]`, Tooltips/Size `Departures`, Color saturation `Avg Delay (min)` (Format → Bubbles → Colors → fx → Gradient, low green / high red) |
| **Clustered bar** | Y `dim_train[train_group]`, X `Punctuality %` |
| **Clustered bar** | Y `dim_station[station_name]`, X `Punctuality %`, sorted ascending (worst first) |
| **Slicer** | `dim_station[is_berlin]` (Berlin only / all) |

If the map is blank: File → Options → Global → **Security → Map and Filled Map visuals** → enable.

### Page 2 — Station drill-down
| Visual | Fields |
|---|---|
| **Slicer** (dropdown, single select) | `dim_station[station_name]` |
| **Table** | `v_today_stop_event`: `planned_dep_local` (format `HH:mm`), `actual_dep_local` (`HH:mm`), `train_category`, `train_number`, `line`, `planned_platform`, `dep_delay_min`, `delay_band`. Sort by `planned_dep_local` descending. Conditional formatting on `dep_delay_min`: background color rules (<6 green, 6–15 amber, >15 red) |
| **Clustered column** | X `dim_hour[hour_label]`, Y `Avg Delay (min)` |
| **Bar** | Y `v_today_stop_event[line]`, X `Avg Delay (min)`, Top N filter = 10 by `Avg Delay (min)` (worst lines) |
| 2 × **Card** | `Punctuality %`, `Cancellations` |

### Page 7 — Pipeline health
| Visual | Fields |
|---|---|
| **Card** | `Pipeline Status` (conditional font color: Healthy green / Degraded amber / Down red) |
| **Card** | `Minutes Since Last Load` |
| **Card** | `Failed Runs (24h)` |
| 2 × **Gauge** | `DB Used %` and `Storage Used %` (max 1, target 0.8) |
| **Line chart** | X `v_pipeline_runs[started_local]`, Y Sum of `rows_inserted`, filter `job = changes` |
| **Table** | `v_pipeline_runs`: `started_local`, `job`, `status`, `duration_s`, `api_calls`, `rows_inserted`, `error`; filter `status = failed` OR sort by `started_local` desc |

## 6. Make it live

- Select each of pages 1, 2, 7 → Format page (paint roller, no visual selected) → **Page refresh** →
  On → **Auto page refresh**, every **5 minutes**. (Works because those pages use DirectQuery.)
- Footer text box on every page: **Data: Deutsche Bahn (CC BY 4.0) · Weather data by Open-Meteo.com**
- **File → Save as → Power BI project (.pbip)** into this folder:
  `C:\Users\niruj\projects\db_analysis\powerbi\db_delay.pbip`
  (the `.gitignore` already excludes the local cache and settings files).

## 7. Check it works

- Page 1 Punctuality % is roughly 65–90 % (matches `docs/PROGRESS.md` sanity numbers).
- Page 7 Minutes Since Last Load ≤ 10; wait 5 minutes → it resets without clicking Refresh.
- Page 2: pick Berlin Hbf → the newest rows match the departure board at bahn.de.

## 8. Sharing

Publishing to the Power BI Service needs Pro + a gateway, so for the portfolio: take screenshots
and a 60-second screen recording of the live dashboard for the README (Step 9).
