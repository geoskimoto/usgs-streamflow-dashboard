# Percentile Map Coloring — Dashboard Implementation Plan

**Objective:** Consume the `GET /api/v1/observations/discharge/percentile-bands/`  
endpoint (specified in `STREAMFLOWOPS_PERCENTILE_ENDPOINT_SPEC.md`) and render  
map station markers colored by current flow condition.

**Prerequisite:** The StreamflowOps endpoint must be live before any of this is  
testable end-to-end. All dashboard code below can be written and tested with a  
mock response in the meantime.

**Reference branch:** `feature/percentile-map-coloring` — contains a complete  
working implementation (computing locally). The changes below are a simplified  
version of that work, replacing the heavy per-station computation with a single  
API call. Cherry-pick individual sections as needed rather than merging the  
branch, because the branch includes the old computation code that should not come  
back.

---

## Overview of Changes

| File | Change |
|------|--------|
| `dataops_adapter/client_adapter.py` | Add one new method |
| `usgs_dashboard/data/data_manager.py` | Add cache/thread wrapper + thin fetch method |
| `usgs_dashboard/components/map_component.py` | Add band constants + update trace loop |
| `usgs_dashboard/components/filter_panel.py` | Add "Load Flow Conditions" button |
| `app.py` | Add Store, Interval, two callbacks |

---

## Phase 1 — `client_adapter.py`

**File:** `dataops_adapter/client_adapter.py`

Add one method to `DataOpsAdapter`. It makes a single GET request and returns a  
dict keyed by station number.

```python
def get_flow_percentile_bands(self, days_back: int = 2) -> Dict[str, str]:
    """
    Fetch precomputed percentile bands from StreamflowOps.

    Returns:
        dict mapping station_number -> band_key
        e.g. {'14211720': 'p76_100', '12301933': 'p26_50', ...}

    Band keys: p0_4, p5_10, p11_25, p26_50, p51_75, p76_100
    Returns empty dict on any error so callers degrade gracefully.
    """
    if not self.api_enabled or not self.api_client:
        logger.warning("API not available; cannot fetch percentile bands")
        return {}
    try:
        response = self.api_client._request(
            'GET',
            '/api/v1/observations/discharge/percentile-bands/',
            params={'days_back': days_back}
        )
        results = response.get('results', [])
        bands = {r['station_number']: r['band'] for r in results}
        logger.info(f"Fetched percentile bands for {len(bands)} stations")
        return bands
    except Exception as e:
        logger.error(f"Failed to fetch percentile bands: {e}")
        return {}
```

Place this method near the other `get_*` methods, e.g. after `get_forecast_data`  
(line ~540).

---

## Phase 2 — `data_manager.py`

**File:** `usgs_dashboard/data/data_manager.py`

Add a lightweight cache layer around the adapter call. The cache avoids hammering  
the API on every map render. A background thread keeps it fresh on a 30-minute  
schedule so the initial page load never blocks.

### 2.1 — Additional imports (top of file)

```python
import threading
import time
```

### 2.2 — New instance attributes in `__init__`

```python
# Percentile bands cache
self._percentile_cache: dict = {}
self._percentile_cache_time: float = 0.0
self._percentile_cache_ttl: int = 1800        # 30 minutes
self._percentile_refresh_event = threading.Event()
self._percentile_bg_thread: threading.Thread = None
```

### 2.3 — New public methods

```python
def get_cached_percentile_bands(self) -> dict:
    """
    Return the most recently fetched percentile bands dict.
    Non-blocking. Returns {} if never fetched.
    """
    return self._percentile_cache.copy()

def trigger_percentile_refresh(self):
    """Wake the background thread to refresh immediately."""
    if self._percentile_refresh_event is not None:
        self._percentile_refresh_event.set()

def start_percentile_background_refresh(self, interval_seconds: int = 1800):
    """
    Start a daemon thread that refreshes percentile bands periodically.
    Call once at app startup.
    """
    if self._percentile_bg_thread and self._percentile_bg_thread.is_alive():
        return  # Already running

    def _loop():
        while True:
            try:
                bands = self.adapter.get_flow_percentile_bands(days_back=2)
                if bands:
                    self._percentile_cache = bands
                    self._percentile_cache_time = time.time()
                    print(
                        f"[percentile] Refreshed: {len(bands)} stations | "
                        f"{datetime.now().strftime('%H:%M:%S')}",
                        flush=True
                    )
                else:
                    print("[percentile] Fetch returned empty result", flush=True)
            except Exception as e:
                print(f"[percentile] Background refresh error: {e}", flush=True)
            # Wait for next interval or manual trigger
            self._percentile_refresh_event.wait(timeout=interval_seconds)
            self._percentile_refresh_event.clear()

    self._percentile_bg_thread = threading.Thread(
        target=_loop, daemon=True, name="percentile-refresh"
    )
    self._percentile_bg_thread.start()
    print("[percentile] Background refresh thread started", flush=True)
```

Note: `datetime` is already imported in `data_manager.py`. If not, add  
`from datetime import datetime` at the top.

---

## Phase 3 — `map_component.py`

**File:** `usgs_dashboard/components/map_component.py`

### 3.1 — Band constants (add near top of file, after imports)

```python
# Percentile band configuration: (band_key, label, hex_color, opacity, marker_size_factor)
PERCENTILE_GROUP_CONFIG = [
    ('p0_4',    'Very Low',     '#880E4F', 0.92, 1.25),
    ('p5_10',   'Low',          '#E64A19', 0.90, 1.15),
    ('p11_25',  'Below Normal', '#F9A825', 0.88, 1.05),
    ('p26_50',  'Normal',       '#2E7D32', 0.88, 1.00),
    ('p51_75',  'Above Normal', '#1976D2', 0.90, 1.05),
    ('p76_100', 'High',         '#0D47A1', 0.92, 1.15),
    ('no_data', 'No Percentile Data', '#808080', 0.60, 0.90),   # active but no API result
    ('inactive','Inactive',     '#404040', 0.40, 0.80),          # status-based fallback
]

PERCENTILE_LABELS = {cfg[0]: cfg[1] for cfg in PERCENTILE_GROUP_CONFIG}
```

### 3.2 — Update `create_gauge_map` signature

Add `percentile_bands: dict = None` parameter:

```python
def create_gauge_map(self, gauges_df: pd.DataFrame,
                    selected_gauge: Optional[str] = None,
                    map_style: str = 'open-street-map',
                    height: int = 700,
                    auto_fit_bounds: bool = True,
                    percentile_bands: dict = None) -> go.Figure:
```

### 3.3 — Update `_prepare_map_data`

In the private `_prepare_map_data` method (or wherever `map_data` is built from  
`gauges_df`), add a `map_group` column after the existing status column is  
computed:

```python
def _prepare_map_data(self, gauges_df, selected_gauge, percentile_bands):
    """Prepare map data with percentile group column."""
    map_data = gauges_df.copy()

    # Assign map_group: prefer percentile band, fall back to status
    if percentile_bands:
        station_col = 'station_number' if 'station_number' in map_data.columns else 'site_id'
        map_data['map_group'] = map_data[station_col].map(percentile_bands)
        # Stations with no band result: use status-based fallback
        no_band_mask = map_data['map_group'].isna()
        map_data.loc[no_band_mask & (map_data['status'] == 'inactive'), 'map_group'] = 'inactive'
        map_data.loc[no_band_mask & (map_data['status'] != 'inactive'), 'map_group'] = 'no_data'
    else:
        # Fall back to status-based coloring (original behavior)
        status_to_group = {
            'active':            'p26_50',   # green placeholder until bands load
            'active_no_recent':  'no_data',
            'inactive':          'inactive',
        }
        map_data['map_group'] = map_data['status'].map(status_to_group).fillna('no_data')

    map_data['percentile_label'] = map_data['map_group'].map(PERCENTILE_LABELS).fillna('Unknown')
    return map_data
```

### 3.4 — Replace status-based trace loop with band-based loop

The current `_create_usgs_national_map` and `_create_stamen_terrain_map` methods  
each have a loop like:

```python
for status in map_data['status'].unique():
    ...
    color=color_map.get(status, '#808080'),
```

Replace both loops with the `PERCENTILE_GROUP_CONFIG` loop:

```python
base_size = 9
for band_key, label, color, opacity, size_factor in PERCENTILE_GROUP_CONFIG:
    group_df = map_data[map_data['map_group'] == band_key]
    if group_df.empty:
        continue
    fig.add_trace(go.Scattermap(
        lat=group_df['latitude'],
        lon=group_df['longitude'],
        mode='markers',
        name=label,
        marker=dict(
            size=base_size * size_factor,
            color=color,
            opacity=opacity,
        ),
        customdata=group_df[[
            'site_id', 'station_name', 'status', 'latest_value',
            'latest_date', 'map_group', 'percentile_label',
        ]].values,
        hovertemplate=(
            '<b>%{customdata[1]}</b><br>'
            'ID: %{customdata[0]}<br>'
            'Flow: %{customdata[3]:.1f} cfs<br>'
            'As of: %{customdata[4]}<br>'
            'Condition: <b>%{customdata[6]}</b>'
            '<extra></extra>'
        ),
        ...  # keep map-specific layout params (uirevision, etc.) unchanged
    ))
```

Adjust `customdata` column list to match what actually exists in `map_data`.  
Column indices in `hovertemplate` must match the order in `customdata`.

### 3.5 — Pass `percentile_bands` through

In `create_gauge_map`, pass `percentile_bands` to `_prepare_map_data` and  
to whichever internal build method you call:

```python
map_data = self._prepare_map_data(gauges_df, selected_gauge, percentile_bands)
```

---

## Phase 4 — `filter_panel.py`

**File:** `usgs_dashboard/components/filter_panel.py`

Add a "Load Flow Conditions" button that the user can press to trigger an  
on-demand refresh of the percentile bands. Place it in a logical spot — e.g.  
below the existing filter controls, before or after the clear/apply buttons.

```python
dbc.Button(
    "Load Flow Conditions",
    id="refresh-flow-conditions-btn",
    color="info",
    outline=True,
    size="sm",
    className="mt-2 w-100",
    title="Color map markers by current flow percentile (updates every 30 min)",
),
```

---

## Phase 5 — `app.py`

**File:** `app.py`

### 5.1 — Startup: launch background thread

After `data_manager` is instantiated (near the top of the file), start the  
background refresh thread:

```python
data_manager.start_percentile_background_refresh(interval_seconds=1800)
```

### 5.2 — Layout: add Store and Interval

Inside the `app.layout` definition:

```python
dcc.Store(id='percentile-bands-store', data={}),
dcc.Interval(
    id='percentile-refresh-interval',
    interval=30_000,    # poll every 30 seconds
    n_intervals=0,
    disabled=False,
),
```

### 5.3 — Callback: populate the Store

```python
@app.callback(
    Output('percentile-bands-store', 'data'),
    Input('percentile-refresh-interval', 'n_intervals'),
    Input('refresh-flow-conditions-btn', 'n_clicks'),
    prevent_initial_call=False,
)
def refresh_percentile_bands(n_intervals, n_clicks):
    """
    Poll the cache every 30 s. Button click triggers an immediate background refresh.
    Returns the cached bands dict (may be empty on first load before thread populates it).
    """
    ctx = dash.callback_context
    if ctx.triggered and ctx.triggered[0]['prop_id'] == 'refresh-flow-conditions-btn.n_clicks':
        data_manager.trigger_percentile_refresh()
        # Return whatever is cached right now; the next poll will pick up fresh data
    return data_manager.get_cached_percentile_bands()
```

### 5.4 — Update the map callback

Add `percentile_bands` as an input to the existing map update callback:

```python
@app.callback(
    Output('gauge-map', 'figure'),
    ...existing inputs...,
    Input('percentile-bands-store', 'data'),
    ...
)
def update_map(..., percentile_bands, ...):
    ...
    fig = map_component.create_gauge_map(
        gauges_df=filtered_df,
        selected_gauge=selected_gauge,
        map_style=map_style,
        height=map_height,
        percentile_bands=percentile_bands or {},
    )
    return fig
```

---

## Phase 6 — Cleanup

Once the above is working:

- Remove any leftover `get_recent_discharge_values` method from  
  `client_adapter.py` if it was ever added back (it exists on  
  `feature/percentile-map-coloring` but should not be on `main`)
- Remove debug `print()` statements from the background thread once  
  stable in production (or convert to `logger.info()`)
- The `start_background_refresh` method name from the feature branch used  
  a generic name; the new method uses `start_percentile_background_refresh`  
  to be explicit — keep this naming

---

## Phase 7 — Testing

### 7.1 — Mock test (endpoint not yet live)

Add a temporary env-var gate in `client_adapter.get_flow_percentile_bands`:

```python
import os
if os.getenv('USE_MOCK_PERCENTILE_BANDS'):
    return {
        '14211720': 'p76_100',
        '12301933': 'p26_50',
        '09070500': 'p5_10',
        '14048000': 'p0_4',
    }
```

Set `USE_MOCK_PERCENTILE_BANDS=1` locally. The map will render colored markers  
using the mock data so all UI code can be verified before the endpoint ships.

### 7.2 — End-to-end test checklist

- [ ] Map renders on first load (grey / `no_data` initially, then colors after  
      first background thread cycle)
- [ ] "Load Flow Conditions" button triggers a refresh and map updates within ~30 s  
      (one Interval tick after the thread finishes)
- [ ] All 6 band colors appear in the legend
- [ ] Station tooltip shows "Condition: Very Low / Low / ..." correctly
- [ ] Stations absent from the API response show as grey (`no_data`)
- [ ] Inactive stations show as dark grey (`inactive`)
- [ ] No 502 / timeout on Render (single worker is never blocked)
- [ ] Zoom/pan state is preserved when bands update (check `uirevision`)

---

## Sequence Diagram

```
App startup
  └─► data_manager.start_percentile_background_refresh()
        └─► background thread sleeps 30 min, wakes, calls:
              adapter.get_flow_percentile_bands()
                └─► GET /api/v1/observations/discharge/percentile-bands/
              stores result in _percentile_cache

Browser loads page
  └─► Interval fires every 30 s
        └─► refresh_percentile_bands callback
              └─► get_cached_percentile_bands() → percentile-bands-store

Store update triggers map callback
  └─► create_gauge_map(..., percentile_bands={...})
        └─► _prepare_map_data assigns map_group per station
        └─► trace loop renders one trace per band key
```

---

## Files Not Changed

| File | Reason |
|------|--------|
| `dataops_client/client.py` | No changes needed; `_request` method used as-is |
| `dataops_adapter/models.py` | No new models needed |
| `dataops_adapter/exceptions.py` | Existing exceptions cover error cases |
| All other components | Unaffected by percentile feature |

---

*Implementation plan version 1.0 — tied to `STREAMFLOWOPS_PERCENTILE_ENDPOINT_SPEC.md`*
