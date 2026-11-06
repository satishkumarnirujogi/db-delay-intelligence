# Power BI — page-by-page build guide

Continues from **README.md section 4** (tables loaded, storage modes, relationships, measures done).
You build three pages: **1 Network now**, **2 Station drill-down**, **7 Pipeline health**.

Every visual has an exact **position and size** for a 1280 × 720 canvas, so the pages line up
without dragging. Do the steps in order; each one says where to click.

---

## Part A — One-time setup (≈ 10 min)

### A1. Stop Power BI from querying while you build
DirectQuery runs a query every time you drop a field, which is what made visuals slow.
1. Ribbon **Optimize → Pause visuals**. Visuals now stay empty while you build.
   When a page is finished: **Optimize → Refresh visuals** (or **Resume visuals**).
2. **File → Options and settings → Options → CURRENT FILE → DirectQuery** →
   *Maximum connections per data source* = **3** → OK.
3. Same window: **CURRENT FILE → Query reduction** → tick **Add an Apply button to each slicer** → OK.

### A2. Import the theme (colors, fonts, borders, rounded corners for every visual)
1. **View → Themes → ⌄ (expand) → Browse for themes**.
2. Pick `C:\Users\niruj\projects\db_analysis\powerbi\db_delay_theme.json` → Open.
   Every new visual now gets a white background, light-grey border with 8 px rounded corners,
   no shadow and dark titles. The page background becomes light grey `#F5F6F8`.
   If Power BI rejects the file, skip it and use the colors in **A4** by hand.

### A3. Column formats (Data pane on the right, select the column → **Column tools** ribbon)
| Table | Column | Set |
|---|---|---|
| `v_today_stop_event` | `planned_dep_local` | Format → **Custom** → `HH:mm` |
| `v_today_stop_event` | `actual_dep_local` | Format → **Custom** → `HH:mm` |
| `v_pipeline_runs` | `started_local` | Format → **Custom** → `dd.MM HH:mm` |
| `dim_hour` | `hour_label` | (no change; sorts correctly as text) |

### A4. Color reference (used below)
| Use | Hex |
|---|---|
| On time / good | `#1E8E3E` (green) |
| 6–15 min / warning | `#F9AB00` (amber) |
| 16–30 min | `#E8710A` (orange) |
| 30+ min / bad | `#D93025` (red) |
| Cancelled / muted text | `#6B7280` (grey) |
| Main bars | `#2563EB` (blue) |
| Titles | `#1F2937` (near black) |
| Page background | `#F5F6F8` |

### A5. Add six helper measures
Select the `_Measures` table → **Home → New measure** → paste one → Enter. Repeat.

```dax
Last Load Label = "Last load " & [Minutes Since Last Load] & " min ago"

Pipeline Status Color =
SWITCH ( [Pipeline Status], "Healthy", "#1E8E3E", "Degraded", "#F9AB00", "#D93025" )

Delay Band Color =
SWITCH (
    SELECTEDVALUE ( v_today_stop_event[delay_band] ),
    "on time (<6)", "#1E8E3E",
    "6-15 min",     "#F9AB00",
    "16-30 min",    "#E8710A",
    "30+ min",      "#D93025",
    "cancelled",    "#6B7280"
)

Run Status Color =
SWITCH ( SELECTEDVALUE ( v_pipeline_runs[status] ), "success", "#1E8E3E", "failed", "#D93025", "#F9AB00" )

Usage Warning Line = 0.8

Departures Today = COUNTROWS ( v_today_stop_event )
```
Format `Usage Warning Line` as Percentage (Measure tools → % button).

### A6. How to set an exact position and size (used for every visual)
Select the visual → **Format** pane (paintbrush icon) → **General** tab → **Properties** →
- **Size**: Height, Width
- **Position**: Horizontal (= X), Vertical (= Y)

Type the numbers and press Enter. All tables below are written as **X, Y, W, H**.

### A7. Canvas size (do this on every new page)
Click an empty spot on the canvas → **Format** pane → **Canvas settings** → Type **16:9**
(1280 × 720) → Vertical alignment **Top**.

---

## Part B — Page 1 "Network now"

Rename the first page: double-click the tab at the bottom → `Network now`. Apply **A7**.

**Layout (1280 × 720):**
```
┌───────────────────────────── title ──────────────┬─ last load ─┬── train-group slicer ──┐  y 8
├──────────┬──────────┬──────────┬──────────┬──────────┤                                   y 64
│Punctual %│Avg delay │Cancelled │Platform Δ│Live data │  5 KPI cards                      │
├──────────┴──────────┴────────┬─┴──────────┴──────────┤                                   y 180
│                              │ Punctuality by station (bar, worst first)                 │
│        Station map           ├────────────────────────────────────────────────────────── y 492
│                              │ Punctuality by train group (bar)                          │
└──────────────────────────────┴────────────────────────────────────────────────────────── y 678
  footer                                                                                     y 688
```

### B1. Page title — Text box
1. **Insert → Text box**. Type: `Network now — DB punctuality today`
2. Select the text → font **Segoe UI Semibold**, size **20**, color `#1F2937`.
3. Format → General → Effects → **Background off**, **Visual border off**.
4. Position **16, 8, 700, 44**.

### B2. Last-load label — Card
1. Visualizations → **Card**. Fields → **Fields**: `Last Load Label`.
2. Format → Visual → **Callout value**: size **11**, color `#6B7280`, font Segoe UI.
3. **Category label**: Off. General → Effects → **Background off**, **Visual border off**. Title: Off.
4. Position **728, 8, 252, 44**.

### B3. Train-group filter — Slicer
1. Visualizations → **Slicer**. Field: `dim_train[train_group]`.
2. Format → Visual → **Slicer settings → Options → Style: Tile**; Selection: **Multi-select with Ctrl** on.
3. **Slicer header**: Off. **Values**: size 10.
4. Position **992, 8, 272, 48**.
   (Nothing selected = all trains.)

### B4. Five KPI cards — Card
Make the first card fully, then copy it (Ctrl+C / Ctrl+V) and only swap the field and position.

1. Visualizations → **Card**. Field: `Punctuality %`.
2. Format → Visual:
   - **Callout value**: size **28**, font Segoe UI Semibold, display units **None**.
   - **Category label**: On, size **11**, color `#6B7280`.
3. Conditional color (only for **Punctuality %**): Callout value → **Color → fx** →
   Format style **Rules** → based on field `Punctuality %`:
   - If value **>= 0.8** (number) and **<= 1** → `#1E8E3E`
   - If value **>= 0.65** and **< 0.8** → `#F9AB00`
   - If value **>= 0** and **< 0.65** → `#D93025` → OK
4. General → Title: **Off** (the category label already names the card).

| # | Field | X, Y, W, H | Note |
|---|---|---|---|
| 1 | `Punctuality %` | 16, 64, 240, 104 | with the color rules above |
| 2 | `Avg Delay (min)` | 268, 64, 240, 104 | Callout value → value decimal places **1** |
| 3 | `Cancellations` | 520, 64, 240, 104 | Callout value color `#D93025` |
| 4 | `Platform Changes` | 772, 64, 240, 104 | Callout value color `#F9AB00` |
| 5 | `Live Data Coverage %` | 1024, 64, 240, 104 | Callout value color `#2563EB` |

Cards 2–5 are copies, so they carry the green/amber/red rule from card 1. Remove it on each:
Callout value → Color → **fx** → **Delete** (bottom-left of the dialog), then pick the plain color
from the Note column.

### B5. Station map — Azure Map
1. Visualizations → **Azure Map** (globe with pin icon).
   If it is missing or blank: File → Options → **GLOBAL → Security** → tick
   **Use Azure Maps visual** (and *Map and Filled Map visuals*) → restart Power BI.
2. Fields:
   - **Latitude**: `dim_station[lat]`
   - **Longitude**: `dim_station[lon]`
   - **Size**: `Departures`
   - **Tooltips**: `dim_station[station_name]`, `Punctuality %`, `Avg Delay (min)`, `Departures`
3. Format → Visual:
   - **Map settings → Style**: **Grayscale (light)**; **Auto zoom**: On.
   - **Bubble layer → Size**: min **8**, max **28**.
   - **Bubble layer → Fill color → fx** → Format style **Gradient** → based on `Avg Delay (min)` →
     Minimum **Number 0** = `#1E8E3E`, tick **Add a middle color** **Number 5** = `#F9AB00`,
     Maximum **Number 15** = `#D93025` → OK.
   - **Bubble layer → Border**: color `#FFFFFF`, width 1.
4. General → Title: On, text `Stations — bubble size = departures, color = avg delay`.
5. Position **16, 180, 620, 498**.

### B6. Punctuality by station — Clustered bar chart
1. Visualizations → **Clustered bar chart**.
   - **Y-axis**: `dim_station[station_name]`
   - **X-axis**: `Punctuality %`
2. Sort worst first: click **… (More options)** on the visual → **Sort axis → Punctuality %**,
   then **… → Sort axis → Sort ascending**.
3. Format → Visual:
   - **Bars → Color → fx** → **Gradient** on `Punctuality %`: Minimum **Number 0.6** = `#D93025`,
     middle **Number 0.75** = `#F9AB00`, Maximum **Number 0.95** = `#1E8E3E`.
   - **Data labels**: On, size 9, display units None (shows e.g. 82.4%).
   - **X-axis**: Off. **Y-axis → Values**: size 10. **Gridlines**: Off.
4. Title text: `Punctuality by station (departed trains, today)`.
5. Position **648, 180, 616, 300**.

### B7. Punctuality by train group — Clustered bar chart
1. Copy B6 (Ctrl+C, Ctrl+V). Replace **Y-axis** with `dim_train[train_group]`.
2. Bars color: remove fx, set plain `#2563EB`. Keep data labels.
3. Title text: `Punctuality by train group`.
4. Position **648, 492, 616, 186**.

### B8. Footer — Text box
1. **Insert → Text box**: `Data: Deutsche Bahn (CC BY 4.0) · Weather data by Open-Meteo.com · Punctual = < 6 min late`
2. Font Segoe UI, size **9**, color `#6B7280`. Background off, border off.
3. Position **16, 688, 1248, 24**.

### B9. Check
**Optimize → Refresh visuals.** Expect: Punctuality % ≈ 65–90 %, 15 bubbles across Germany,
station bars sorted worst on top.

---

## Part C — Page 2 "Station drill-down"

Add a page (**+** at the bottom) → rename `Station drill-down`. Apply **A7**.
Copy the **title**, **last-load card** and **footer** from page 1 (select them with Ctrl+click →
Ctrl+C → go to page 2 → Ctrl+V; positions stay the same). Change the title text to
`Station drill-down — today's departures`.

**Layout:**
```
┌────────────────── title ─────────────────┬─ last load ─┬──── station dropdown ────┐  y 4–8
├───────────────┬───────────────┬───────────────┬───────────────┤                      y 68
│ Departures    │ Punctuality % │ Avg delay     │ Cancellations │  4 KPI cards
├───────────────┴───────────────┴──────┬────────┴───────────────┤                      y 176
│                                      │ Avg delay by hour       │
│     Departure table                  ├─────────────────────────┤                      y 433
│                                      │ Worst lines (top 10)    │
└──────────────────────────────────────┴─────────────────────────┘                      y 678
```

### C1. Station dropdown — Slicer
1. Visualizations → **Slicer**. Field: `dim_station[station_name]`.
2. Format → Visual → **Slicer settings → Options → Style: Dropdown**;
   **Selection → Single select: On**.
3. **Slicer header**: On, title text `Station`, size 10.
4. Position **920, 4, 344, 60**.
5. Click the dropdown → pick **Berlin Hbf** (this becomes the default when you save).

### C2. Four KPI cards
Copy card 1 (`Punctuality %`, with its color rules) from page 1 and paste 4 times. Set:

| # | Field | X, Y, W, H |
|---|---|---|
| 1 | `Departures Today` | 16, 68, 303, 96 |
| 2 | `Punctuality %` | 331, 68, 303, 96 |
| 3 | `Avg Delay (min)` | 646, 68, 303, 96 |
| 4 | `Cancellations` | 961, 68, 303, 96 |

Only card 2 keeps the color rules; set cards 1 `#2563EB`, 3 `#1F2937`, 4 `#D93025`.

### C3. Departure table — Table
1. Visualizations → **Table**. Columns, in this order (drag into **Columns**):
   `planned_dep_local`, `actual_dep_local`, `train_category`, `train_number`, `line`,
   `planned_platform`, `dep_delay_min`, `delay_band`, `platform_changed`
   (all from `v_today_stop_event`).
2. Rename headers (double-click each field in the **Columns** well → type):
   `Planned`, `Actual`, `Type`, `Train`, `Line`, `Platform`, `Delay (min)`, `Status`, `Platform changed`.
   For `dep_delay_min` click the ⌄ next to it → **Don't summarize**; same for `train_number`.
3. Sort: click the **Planned** column header twice → newest at the top (descending).
4. Visual filter (Filters pane → *Filters on this visual*): `planned_dep_local` → **is not blank**
   (hides arrivals that end here).
5. Conditional formatting:
   - **Status** column: Columns well → ⌄ on `delay_band` → **Conditional formatting →
     Background color** → Format style **Field value** → based on `Delay Band Color` → OK.
     Then Format → Visual → **Cell elements** → *Apply settings to* `Status` → Font color `#FFFFFF`
     (white text on the colored cell).
   - **Delay (min)** column: ⌄ on `dep_delay_min` → Conditional formatting → **Font color** →
     **Rules**: `>= 0` and `< 6` → `#1E8E3E`; `>= 6` and `< 16` → `#F9AB00`; `>= 16` and `<= 1440` → `#D93025`.
6. Format → Visual: **Grid → Row padding** 4; **Values** size 10; **Column headers** size 10 bold,
   background `#F3F4F6`; **Style presets**: *Minimal*.
7. Title: `Departures (latest first)`.
8. Position **16, 176, 760, 502**.

### C4. Avg delay by hour — Clustered column chart
1. Visualizations → **Clustered column chart**.
   - **X-axis**: `dim_hour[hour_label]`
   - **Y-axis**: `Avg Delay (min)`
2. Sort: … → **Sort axis → hour_label → Sort ascending**.
3. **Columns → Color → fx → Gradient** on `Avg Delay (min)`: Min **Number 0** `#1E8E3E`,
   middle **Number 5** `#F9AB00`, Max **Number 15** `#D93025`.
4. Data labels On (size 8, 1 decimal). Y-axis Off. Gridlines Off.
5. Title: `Average departure delay by hour (min)`.
6. Position **788, 176, 476, 245**.

### C5. Worst lines — Clustered bar chart
1. Visualizations → **Clustered bar chart**.
   - **Y-axis**: `v_today_stop_event[line]`
   - **X-axis**: `Avg Delay (min)`
2. Filters pane → *Filters on this visual* → `line`:
   - **Filter type: Top N** → Show items **Top 10** → By value: drag `Avg Delay (min)` → **Apply filter**.
   - Add another filter on `line` → Basic → untick **(Blank)**.
3. Sort: … → Sort axis → **Avg Delay (min)** → **Sort descending**.
4. Bars color `#D93025`, data labels On (1 decimal), X-axis Off, gridlines Off.
5. Title: `Worst lines today (avg delay, min)`.
6. Position **788, 433, 476, 245**.

### C6. Check
**Refresh visuals.** Pick a different station in the dropdown → all visuals change.
The top table rows should match the departure board for that station on bahn.de.

---

## Part D — Page 7 "Pipeline health"

Add a page → rename `Pipeline health`. Apply **A7**. Copy title, last-load card and footer from
page 1; title text `Pipeline health — is the data fresh?`.

**Layout:**
```
┌──────────────────── title ───────────────────┬─ last load ─┐                          y 8
├──────────┬──────────┬──────────┬──────────┬──────────┤                                y 64
│ Status   │ Minutes  │ Failed   │ DB used  │ Storage  │  3 cards + 2 gauges
│          │ since    │ runs 24h │ (gauge)  │ (gauge)  │
├──────────┴──────────┴──────────┴──────────┴──────────┤                                y 226
│ Rows loaded per run (line chart, last 24 h)          │
├──────────────────────────────────────────────────────┤                                y 438
│ Recent runs (table)                                  │
└──────────────────────────────────────────────────────┘                                y 678
```

### D1. Status card — Card
1. **Card**, field `Pipeline Status`.
2. Callout value size **28**; **Color → fx** → Format style **Field value** → based on
   `Pipeline Status Color` → OK.
3. Category label On (`Pipeline Status`). Title Off.
4. Position **16, 64, 240, 150**.

### D2. Minutes since last load — Card
1. **Card**, field `Minutes Since Last Load`. Callout size 28.
2. Color → fx → **Rules** on `Minutes Since Last Load`: `>= 0` and `<= 20` → `#1E8E3E`;
   `> 20` and `<= 60` → `#F9AB00`; `> 60` and `<= 100000` → `#D93025`.
3. Position **268, 64, 240, 150**.

### D3. Failed runs — Card
1. **Card**, field `Failed Runs (24h)`. Callout size 28.
2. Color → fx → **Rules**: `>= 0` and `< 1` → `#1E8E3E`; `>= 1` and `<= 100000` → `#D93025`.
3. Position **520, 64, 240, 150**.

### D4. Database used — Gauge
1. Visualizations → **Gauge**.
   - **Value**: `DB Used %`
   - **Minimum value**: (leave empty) — set in format below
   - **Target value**: `Usage Warning Line`
2. Format → Visual → **Gauge axis**: Min **0**, Max **1**.
   **Colors → Fill color → fx → Rules** on `DB Used %`: `>= 0` and `< 0.6` → `#1E8E3E`;
   `>= 0.6` and `< 0.8` → `#F9AB00`; `>= 0.8` and `<= 1` → `#D93025`. **Target color** `#1F2937`.
3. **Callout value**: size 20, display units None (shows %).
4. Title: `Database used (500 MB free tier)`.
5. Position **772, 64, 240, 150**.

### D5. Storage used — Gauge
Copy D4 → Value `Storage Used %` (swap the field in the color rule too) →
Title `File storage used (1 GB)` → Position **1024, 64, 240, 150**.

### D6. Rows loaded per run — Line chart
1. Visualizations → **Line chart**.
   - **X-axis**: `v_pipeline_runs[started_local]` → ⌄ → choose `started_local` (not Date Hierarchy).
   - **Y-axis**: `v_pipeline_runs[rows_inserted]` (Sum).
2. Filters on this visual:
   - `job` → Basic → tick **changes** only.
   - `started_local` → **Relative time** → is in the last **24 hours** → Apply.
3. Format → **X-axis → Type: Continuous**. **Lines** color `#2563EB`, stroke width 2.
   **Markers** On, size 3. Gridlines: horizontal only, color `#E5E7EB`.
4. Title: `New change rows per 10-min run (last 24 h)`.
5. Position **16, 226, 1248, 200**.

A healthy pipeline shows a point every ~10 min; gaps mean missed runs.

### D7. Recent runs — Table
1. **Table**, columns from `v_pipeline_runs`:
   `started_local`, `job`, `status`, `duration_s`, `api_calls`, `rows_inserted`, `error`
   (set `duration_s`, `api_calls`, `rows_inserted` to **Don't summarize**).
2. Rename headers: `Started`, `Job`, `Status`, `Duration (s)`, `API calls`, `Rows`, `Error`.
3. Sort by **Started** descending (click header twice).
4. **Status** column → Conditional formatting → **Font color → Field value** → `Run Status Color`.
5. Format: Style preset *Minimal*, values size 10, row padding 3, **Error** column width ~400
   (drag the header edge) and Values → **Text wrap** On.
6. Title: `Recent runs (latest first)`.
7. Position **16, 438, 1248, 240**.

### D8. Check
**Refresh visuals.** Status = Healthy (green), minutes ≤ 10, failed runs 0, DB gauge ≈ 5–10 %.

---

## Part E — Make it live and save

1. **Resume visuals** (Optimize ribbon) if still paused.
2. For each page (Network now, Station drill-down, Pipeline health): click empty canvas →
   **Format** pane → **Page refresh** → On → Refresh type **Auto page refresh** →
   every **5 Minutes**.
3. Page order: drag tabs so it reads `Network now`, `Station drill-down`, `Pipeline health`.
4. **File → Save as** → *Save as type* **Power BI project files (\*.pbip)** →
   `C:\Users\niruj\projects\db_analysis\powerbi\db_delay.pbip` → Save.
5. Tell Claude it is saved; it gets committed to GitHub.

## Part F — If something goes wrong

| Symptom | Fix |
|---|---|
| "Error fetching data" / visuals spin forever | Check Supabase → Database → **Network Bans**, remove your IP. Then File → Options → Data source settings → **Clear permissions** and sign in again as `powerbi_reader.cfictjtkdxezatyznkcp`. |
| Slow while building | **Optimize → Pause visuals** (A1); max connections = 3. |
| Card shows a number instead of a % | Select the measure → Measure tools → **%** button, 1 decimal. |
| Map empty | A5 lat/lon data categories (README step 3) + Azure Maps enabled (B5). |
| Table shows "Sum of dep_delay_min" or one row only | Set numeric columns to **Don't summarize** (C3 step 2). |
| Hour chart in wrong order | … → Sort axis → hour_label → ascending (C4 step 2). |
| Theme import error | Skip A2; set background/border/corner radius per visual: General → Effects → Background `#FFFFFF`, Visual border `#E5E7EB` rounded corners 8. Page: Canvas background `#F5F6F8`, transparency 0. |
