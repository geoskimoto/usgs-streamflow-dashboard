# StreamflowOps: Flow Percentile Precomputation & API Endpoint Specification

**Prepared for:** StreamflowOps AI agent / backend developer  
**Prepared by:** USGS Streamflow Dashboard (consumer application)  
**Date:** February 2026

---

## 1. Context & Problem Statement

The USGS Streamflow Dashboard (a Dash/Plotly web app hosted on Render) colors map
markers by current flow condition relative to historical record. The coloring logic
requires, for each active station:

1. The most recent daily-mean discharge value (within the past 2 days)
2. The full 30-year daily-mean discharge history for that station
3. An exceedance-percentile calculation comparing (1) against (2)

Currently this is computed **inside the dashboard app** at startup via a background
thread. It makes up to 235 sequential API calls (one per forecast station with recent
data), each fetching up to 30 years of daily observations. On a single-worker Render
deployment this takes several minutes and saturates the process.

**The correct fix** is to have StreamflowOps — which already holds all the historical
data and runs scheduled tasks — precompute these percentiles on a schedule and expose
them via a single lightweight API endpoint. The dashboard then makes **one API call**
and receives a ready-to-use color classification for all stations.

---

## 2. What Needs to Be Computed

### 2.1 Per-Station Percentile Rank

For each station that has a daily-mean discharge observation within the past **2 days**:

```
percentile_rank = (count of historical daily values <= current_value) / (total historical values) * 100
```

More precisely, the dashboard currently uses **exceedance probability** and then
converts:

```python
exceedance = (historical_flows >= current_value).sum() / len(historical_flows) * 100
percentile_rank = 100.0 - exceedance
```

Both formulations are equivalent. Use whichever is more natural in your codebase.
The result is a float 0–100 where:
- 0 = current flow is the lowest ever recorded
- 100 = current flow is the highest ever recorded
- 50 = current flow equals the median of the historical record

### 2.2 Band Classification

Map the `percentile_rank` to one of ten band keys:

| Band Key    | Percentile Range   | Dashboard Color | Meaning           |
|-------------|--------------------|-----------------|-------------------|
| `p0_4`      | 0–4th              | `#880E4F`       | Very Low          |
| `p5_10`     | 5th–10th           | `#E64A19`       | Low               |
| `p11_25`    | 11th–25th          | `#F9A825`       | Below Normal      |
| `p26_50`    | 26th–50th          | `#2E7D32`       | Normal            |
| `p51_75`    | 51st–75th          | `#1976D2`       | Above Normal      |
| `p76_85`    | 76th–85th          | `#1565C0`       | High              |
| `p86_90`    | 86th–90th          | `#0D47A1`       | Very High         |
| `p91_95`    | 91st–95th          | `#0A3585`       | Exceptionally High|
| `p96_98`    | 96th–98th          | `#07256B`       | Near Record       |
| `p99_100`   | > 98th             | `#041552`       | Record / Extreme  |

Python classification logic for reference:
```python
if percentile_rank <= 4:
    band = 'p0_4'
elif percentile_rank <= 10:
    band = 'p5_10'
elif percentile_rank <= 25:
    band = 'p11_25'
elif percentile_rank <= 50:
    band = 'p26_50'
elif percentile_rank <= 75:
    band = 'p51_75'
elif percentile_rank <= 85:
    band = 'p76_85'
elif percentile_rank <= 90:
    band = 'p86_90'
elif percentile_rank <= 95:
    band = 'p91_95'
elif percentile_rank <= 98:
    band = 'p96_98'
else:
    band = 'p99_100'
```

### 2.3 Historical Baseline

- **Source:** Daily-mean discharge (`type = 'daily_mean'`) from the observations table
- **Window:** All available history, ideally 30 years. A minimum of 365 days of data
  is required to produce a meaningful percentile; stations with fewer than 30 daily
  records should be excluded from the output (the dashboard already handles missing
  stations gracefully by showing them as grey "active_no_recent")
- **Current value definition:** The most recent `daily_mean` observation within the
  past 2 calendar days for that station, compared against the **full historical
  record for the same calendar day-of-year window ± 7 days** OR against the full
  record with no seasonal filter — either approach is acceptable. Non-seasonal
  (all-time) comparison is what the dashboard currently uses and is sufficient

---

## 3. Which Stations to Include

The dashboard currently limits computation to stations that satisfy **both**:

1. Have a `daily_mean` observation within the past 2 days (i.e., "currently active")
2. Are in the NWRFC forecast station set (cross-walked to USGS station numbers via
   the NWRFC→USGS crosswalk table that StreamflowOps maintains)

In practice this yields ~235 stations. However, the **ideal behavior** for the
dashboard would be **all active stations** (any station with data in the past 2 days),
not just forecast stations. The forecast-station filter was a workaround added solely
to reduce computation load. If StreamflowOps precomputes this server-side, the filter
is no longer needed and the endpoint should cover all stations with recent data.

**Recommendation:** Compute for all stations with a `daily_mean` observation in the
past 2 days. At the time of writing this is approximately 969 stations in the dataset.

---

## 4. Recommended Computation Schedule

| Schedule           | Rationale |
|--------------------|-----------|
| Every **6 hours**  | Daily-mean values update once per day but new data arrives at different times per station; 6-hourly ensures freshness within a reasonable window |
| On-demand trigger  | Optionally expose a management endpoint to force a refresh after a bulk data ingest |

A 6-hour schedule means the worst-case staleness for a dashboard user is 6 hours,
which is acceptable for daily-mean data.

---

## 5. Recommended API Endpoint Design

### 5.1 Endpoint

```
GET /api/v1/observations/discharge/percentile-bands/
```

### 5.2 Query Parameters

| Parameter      | Type    | Default | Description |
|----------------|---------|---------|-------------|
| `days_back`    | int     | `2`     | Only return stations with data within this many days |
| `station`      | string  | —       | Filter to a single station number (optional) |
| `format`       | string  | `json`  | Response format (json only for now) |

### 5.3 Response Schema

```json
{
  "computed_at": "2026-02-25T20:00:00Z",
  "days_back": 2,
  "count": 235,
  "results": [
    {
      "station_number": "14211720",
      "current_discharge": 4520.0,
      "percentile_rank": 82.4,
      "band": "p76_100",
      "historical_record_count": 10957,
      "observation_date": "2026-02-24"
    },
    {
      "station_number": "12301933",
      "current_discharge": 210.5,
      "percentile_rank": 28.1,
      "band": "p26_50",
      "historical_record_count": 8760,
      "observation_date": "2026-02-24"
    }
  ]
}
```

**Field definitions:**

| Field                    | Type    | Description |
|--------------------------|---------|-------------|
| `computed_at`            | ISO 8601 datetime | When the percentiles were last computed |
| `days_back`              | int     | The `days_back` parameter used |
| `count`                  | int     | Number of stations in results |
| `station_number`         | string  | USGS station number (matches `station_number` in the stations endpoint) |
| `current_discharge`      | float   | The discharge value used for the comparison (cfs or m³/s, matching the observations unit) |
| `percentile_rank`        | float   | 0–100, computed as described in section 2.1 |
| `band`                   | string  | One of: `p0_4`, `p5_10`, `p11_25`, `p26_50`, `p51_75`, `p76_100` |
| `historical_record_count`| int     | Number of daily records used in the percentile computation |
| `observation_date`       | date    | Date of the `current_discharge` observation |

### 5.4 Authentication

Same token-based auth as all other DataOps endpoints (`Authorization: Token <token>`).

### 5.5 Caching / Freshness Headers

Include standard HTTP caching headers so the dashboard client can skip the request
if data is fresh:

```
Cache-Control: public, max-age=21600
Last-Modified: <computed_at timestamp>
ETag: <hash of computed_at>
```

---

## 6. How the Dashboard Will Consume the Endpoint

The dashboard's `client_adapter.py` will replace the current `get_flow_percentile_bands()`
heavy computation with a single lightweight method:

```python
def get_flow_percentile_bands_from_api(self, days_back: int = 2) -> dict:
    """
    Fetch precomputed percentile bands from StreamflowOps.
    Returns {station_number: band_key}.
    """
    response = self.api_client._request(
        'GET',
        '/api/v1/observations/discharge/percentile-bands/',
        params={'days_back': days_back}
    )
    return {r['station_number']: r['band'] for r in response.get('results', [])}
```

This replaces ~120 lines of threading/pooling code and hundreds of API calls with a
single request. The dashboard will continue to use the `_percentile_cache` and
background thread for local resilience (so it doesn't block if the endpoint is slow),
but the thread will call this one endpoint instead of fetching history per station.

The `map_component.py` code that reads the bands dict does **not need to change** —
the band keys (`p0_4`, `p5_10`, etc.) are the same values it already expects.

---

## 7. Additional Context About the Dashboard

- **API base URL:** `https://streamflowops.3rdplaces.io`
- **Auth:** `Authorization: Token <token>` header
- **Client library:** `dataops_client/client.py` in the dashboard repo is a thin
  `requests`-based wrapper; the new endpoint just needs to follow the same
  `{"count": N, "results": [...], "next": ..., "previous": ...}` paginated envelope
  already used by all other endpoints, OR can return all results in one response
  (no pagination) since the max count is ~1000 stations
- **Station identifier:** The dashboard uses `station_number` (string, e.g.
  `"14211720"`) as the primary key everywhere. The percentile endpoint must return
  the same field name
- **Discharge units:** The dashboard does not currently display the unit in the
  percentile context; it only uses the band key. Units just need to be internally
  consistent (all history and current value in the same unit per station)
- **Observations data type:** Only `daily_mean` is used for percentile computation;
  `realtime_15min` is not relevant here
- **Station "active" definition:** A station is considered active if it has a
  `daily_mean` observation in the past 6 months. The percentile endpoint's `days_back`
  filter uses 2 days (i.e., must have an ob in past 2 days to be colored)

---

## 8. Summary of Work Required in StreamflowOps

1. **Scheduled task** (every 6 hours): For all stations with a `daily_mean` ob in the
   past 2 days, compute exceedance percentile against full historical record, store
   results in a `flow_percentile_bands` table (or equivalent cache):
   ```
   table: flow_percentile_bands
   columns: station_number, current_discharge, percentile_rank, band,
            historical_record_count, observation_date, computed_at
   ```

2. **API endpoint** `GET /api/v1/observations/discharge/percentile-bands/` that
   reads from the precomputed table and returns the JSON schema from section 5.3

3. **No changes required** to the dashboard's `dataops_client/` or `dataops_adapter/`
   packages beyond adding the one new method shown in section 6 — that will be handled
   on the dashboard side once the endpoint is available

---

*End of specification*
