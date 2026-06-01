# Dashboard Display Behavior Specification

> **Purpose:** This document defines the _intended_ behavior for station classification, map display, filter logic, and plot rendering. All future code changes must be validated against these definitions. When a change causes behavior that contradicts this spec, that is a regression — not a feature.

---

## 1. Station Classification (Active / Inactive / Unknown)

### Definitions

| Status | Criteria | Color on Map |
|---|---|---|
| **Active** | Has discharge observations within the last **6 months** (180 days) | Green / percentile color |
| **Inactive** | No discharge observations in the last 6 months but has historical data | Dark gray (`#404040`, opacity 0.40) |
| **Unknown** | Activity status could not be determined (API/adapter failure, empty response) | Mid gray (`#808080`, opacity 0.60) |

### Rules

1. **Active is opt-in, not the default.** A station is Active only if its ID appears in the set returned by `get_active_station_numbers(months_back=6)`. Failure to determine activity must never result in a station being shown as Active.
2. **Unknown is the safe fallback.** If `get_active_station_numbers()` returns an empty set or raises an exception, all stations fall back to **Unknown** — never to Active or Inactive. Showing Unknown as green would be a bug.
3. **Inactive ≠ broken.** An inactive station still has valid historical data and a full period of record. Its data must remain accessible when clicked.
4. **The 6-month threshold is canonical.** Do not change it without explicitly updating this document and the `_classify_station_activity()` docstring.

### Expected Map Population After Load

On a normal page load with a healthy API:
- The majority of USGS stations actively reporting data should appear as **Active** (green or percentile-colored).
- Stations that have been discontinued or are on hiatus should appear as **Inactive** (dark gray).
- **Unknown stations should be a small minority** — they represent API failure, not the default state.
- If most stations on the map are gray (Unknown or Inactive), that is a signal of a classification bug or API connectivity issue, not correct behavior.

---

## 2. Map Display

### Percentile Band Coloring

Active stations with a current percentile value are colored by their discharge percentile relative to the same day-of-water-year historically:

| Band Key | Percentile Range | Color | Meaning |
|---|---|---|---|
| `p0_4` | < 5th | `#880E4F` Dark Maroon | Extreme low / drought |
| `p5_10` | 5th–10th | `#E64A19` Red-Orange | Very low |
| `p11_25` | 10th–25th | `#F9A825` Orange | Low |
| `p26_50` | 25th–50th | `#2E7D32` Dark Green | Below median |
| `p51_75` | 50th–75th | `#1976D2` Blue | Above median |
| `p76_85` | 75th–85th | `#1565C0` Deep Blue | High |
| `p86_90` | 85th–90th | `#0D47A1` Navy | Very high |
| `p91_95` | 90th–95th | `#0A3585` Dark Navy | Flood range |
| `p96_98` | 95th–98th | `#07256B` Darker Navy | Major flood |
| `p99_100` | > 98th | `#041552` Near-black | Extreme flood |

### Non-Percentile Marker States

| Map Group | When Applied | Color | Opacity | Size Factor |
|---|---|---|---|---|
| `active_no_band` | Active station, no percentile data yet (e.g., new station, insufficient history) | `#32CD32` Lime Green | 0.70 | 0.90× |
| `no_data` | Unknown status — could not determine activity | `#808080` Mid Gray | 0.60 | 0.90× |
| `inactive` | Confirmed inactive (>6 months without data) | `#404040` Dark Gray | 0.40 | 0.80× |

### Marker Layers (rendered in this order)

1. Band-colored station circles (largest, bottom layer)
2. White inner dots (0.5× size) on all non-inactive/non-no_data stations
3. Diamond NWRFC overlay on stations with active forecast products
4. Orange highlight ring + inner circle for the currently selected station

---

## 3. Filter Behavior

Filters are **cumulative (AND logic)**. Each active filter narrows the set; no filter widens it.

### Filter Panel Controls

| Filter | Column / Source | Default | Behavior |
|---|---|---|---|
| **Search** | `station_number`, `name`, NWRFC ID | (empty) | Case-insensitive substring match across all three fields |
| **Station Status** | `station_status` | `all` | `all` = no filter; `active` = Active only; `inactive` = Inactive only |
| **State / Province** | `state` | OR, WA, ID, MT, NV, BC | Checklist; only stations in checked states shown |
| **Drainage Area** | `drainage_area` (sq mi) | 0–90,000 | Range slider; stations outside range hidden |
| **River Basin** | `basin` | (none) | Multi-select dropdown; empty = no filter |
| **HUC Code** | `huc_code` | (none) | Multi-select dropdown; empty = no filter |
| **NWRFC Forecast** | `data_manager.get_forecast_station_ids()` | off | When on: show only stations with an active NWRFC forecast product |
| **ResidCast ML** | `data_manager.get_resid_cast_station_ids()` | off | When on: show only stations with a trained ResidCast model |

### Filter Application Order

Search → State → Station Status → Drainage Area → Basin → HUC → NWRFC → ResidCast

### Critical: "Active" Filter vs. Station Status Field

The **Station Status filter** (`active` / `inactive` / `all`) shows or hides stations based on the `station_status` column value. It is independent of percentile coloring. A station can be **Active** (in the status sense) but shown in a percentile color, not green. Do not conflate map color with activity status.

---

## 4. Plot Display — On Station Click

### Plot Selection Logic (on gauge click)

```
If station_status == 'Inactive':
    → Show full period of record (all available discharge data)
    → Plot type: full history via create_streamflow_plot(history_mode='all')
    → No percentile bands shown (may lack sufficient daily-of-WY overlap)
    → Forecast overlays: disabled

Else (Active or Unknown):
    → Show current water year via create_fast_water_year_plot()
    → Percentile bands from stats cache (parquet)
    → Forecast overlays: enabled if station has NWRFC / ResidCast config
```

### Fast Water Year Plot (Default for Active/Unknown Stations)

**What it shows:**

| Trace | Color | Description |
|---|---|---|
| Current water year discharge | Blue, width 3 | Oct 1 of current WY → today |
| 3rd–97th percentile band | Light blue, opacity 0.24 | Outermost shaded fill |
| 10th–90th percentile band | Light blue, opacity 0.42 | Middle fill |
| 25th–75th percentile band | Cornflower, opacity 0.56 | Inner fill |
| Long-term mean | Gray dashed, width 2.5 | Per-day-of-WY mean |
| Long-term median | Black solid, width 2.5 | Per-day-of-WY median |
| Real-time (last 48 hr) | Red, width 2.5 | 15-minute resolution overlay |
| Today marker | Red vertical dashed line | Annotated "Today" |
| NWRFC forecast runs | Multi-color | Conditional on station config |
| ResidCast ML forecasts | Model-specific colors | Conditional on station config |
| EA-LSTM precip-runoff | Amber (`#E67E22` family, dotted) | Conditional on `ealstm_available` flag |

**What it does NOT show:** Individual historical year traces (that is the full history view).

**Data sources:**
- Current year: `get_current_year_data(site_id)` → Oct 1 → today (~200 rows)
- Statistics (bands, mean, median): `get_flow_statistics(site_id)` → parquet stats cache
- Real-time: `get_realtime_data(site_id)` → last 48 hr at 15-min resolution

### Full History Plot ("Last 30 Years" / "Full Period of Record" Buttons)

Triggered by user clicking a history button, or automatically for Inactive stations.

| Button | `history_mode` | Data range |
|---|---|---|
| Last 30 Years | `'30yr'` | Current date minus 30 water years |
| Full Period of Record | `'all'` | All available discharge observations |

These plots include individual annual traces or a continuous time-series line (not percentile bands by default).

---

## 5. Intended Behavior: Current Water Year Data

### When current water year data should appear

- **Active stations:** Always attempt to show current water year data on click. If `get_current_year_data()` returns an empty DataFrame, show a user-friendly "No current year data available" message — do not silently fall back to a blank or broken plot.
- **Unknown stations:** Attempt current water year display. If data returns empty, show same message.
- **Inactive stations:** Do NOT attempt current water year. Show full period of record directly.

### What "no current water year data" looks like vs. broken

| Scenario | Expected behavior |
|---|---|
| Station Active, API healthy, data exists | Blue current-year trace shown from Oct 1 to today |
| Station Active, data exists only back to Nov | Trace starts at first available date within WY |
| Station Active, no data yet this WY (e.g., brand-new station) | Empty plot area with "No data for current water year" label |
| Station Inactive | Redirect to full period of record automatically |
| API failure | Error message shown; do not show empty axes as if data were returned |

---

## 6. Regressions to Watch For

The following behaviors indicate a regression and must be treated as bugs:

1. **Most stations showing as gray (Unknown or Inactive) when the API is healthy.** Correct state: most active reporting stations should be green or percentile-colored.
2. **Active stations not showing current water year data on click.** If `get_current_year_data()` is returning empty for active stations, the fetch logic or activity classification is broken.
3. **Stations defaulting to Inactive when classification fails.** Unknown is the correct fallback — not Inactive.
4. **Inactive stations not showing any plot at all.** They should auto-load full period of record.
5. **"active" filter showing zero results.** If `get_active_station_numbers()` is returning empty, it is likely an API or query issue, not a data issue.
6. **Percentile bands missing from fast water year plot for active stations.** Check stats cache parquet files and `get_flow_statistics()` return.

---

## 7. Debugging Checklist (Station Activity Issues)

When most stations appear inactive or Unknown:

1. Check `get_active_station_numbers(months_back=6)` — does it return IDs? If empty, the adapter or API is failing silently.
2. Check `_classify_station_activity()` log output — it logs the active set size.
3. Verify API connectivity: `USE_DATAOPS_API` env var and `DATAOPS_API_URL`/`DATAOPS_API_TOKEN`.
4. Check the 1-hour activity cache (`_active_stations_cache`) — a stale empty cache will hold all stations as Unknown for up to an hour.
5. Confirm the `months_back=6` query window is using the correct date arithmetic (timezone-aware, not naive datetime comparison).
