# Forecast Percentile Bands — Dashboard Implementation Guide

**Date:** 2026-05-14  
**Backend feature:** StreamflowOps `forecast_percentiles` table + `/api/v1/forecasts/discharge/percentile-bands/` and `/api/v1/forecasts/discharge/percentile-date-range/` endpoints (deployed to `streamflowops.3rdplaces.io`).

---

## What this adds

- Date picker max extends from today to today + 8 days (NWRFC forecast window)
- Selecting a future date fetches forecast percentile bands instead of observed
- A small source label below the date picker updates based on which data type is shown:
  - Past/today: *"Observed conditions"*
  - Future: *"Forecast: NWRFC — issued [run date]"*
- Map coloring is unchanged — same 10-band classification applies to forecast bands

---

## New API endpoints (StreamflowOps)

### Percentile bands

```
GET https://streamflowops.3rdplaces.io/api/v1/forecasts/discharge/percentile-bands/
```

| Param | Required | Description |
|---|---|---|
| `date` | No | `YYYY-MM-DD`. Defaults to earliest forecast date. |
| `source` | No | Defaults to `NWRFC`. |
| `station` | No | Filter to a single station number. |

Response:
```json
{
  "date": "2026-05-18",
  "source": "NWRFC",
  "forecast_run_date": "2026-05-14T12:00:00Z",
  "computed_at": "2026-05-14T13:01:22Z",
  "count": 238,
  "results": [
    {
      "station_number": "12114500",
      "forecast_discharge": 4820.0,
      "percentile_rank": 72.4,
      "band": "p51_75",
      "historical_record_count": 8431
    }
  ]
}
```

`band` values are the same 10 keys already used by the map (`p0_4` … `p99_100`). No changes needed in `map_component.py`.

### Date range

```
GET https://streamflowops.3rdplaces.io/api/v1/forecasts/discharge/percentile-date-range/
```

| Param | Required | Description |
|---|---|---|
| `source` | No | Defaults to `NWRFC`. |

Response:
```json
{
  "source": "NWRFC",
  "min_date": "2026-05-15",
  "max_date": "2026-05-22",
  "forecast_run_date": "2026-05-14T12:00:00Z"
}
```

Cached 1 hour server-side. Call once on load, same as observed date-range.

---

## Files to change

| File | Change |
|---|---|
| `dataops_adapter/client_adapter.py` | Add 2 new methods |
| `usgs_dashboard/data/data_manager.py` | Add 2 wrapper methods + cache attrs |
| `app.py` | Update date range store, `init_date_picker`, band-fetching callback, add source label element and callback |

---

## Step 1 — `dataops_adapter/client_adapter.py`

Add the two methods below **after the existing `get_percentile_date_range` method** (currently ending around line 631).

```python
def get_forecast_percentile_date_range(self, source: str = 'NWRFC') -> dict:
    """
    Fetch min/max forecast dates from StreamflowOps.
    GET /api/v1/forecasts/discharge/percentile-date-range/
    Returns {'min_date': str, 'max_date': str, 'forecast_run_date': str} or {}.
    """
    if not self.api_enabled or not self.api_client:
        logger.warning("API not available; cannot fetch forecast date range")
        return {}
    try:
        response = self.api_client._request(
            'GET',
            '/api/v1/forecasts/discharge/percentile-date-range/',
            params={'source': source},
        )
        return {
            'min_date': response.get('min_date'),
            'max_date': response.get('max_date'),
            'forecast_run_date': response.get('forecast_run_date'),
        }
    except Exception as e:
        logger.error(f"Failed to fetch forecast percentile date range: {e}")
        return {}


def get_forecast_percentile_bands(
    self,
    target_date: str,
    source: str = 'NWRFC',
) -> dict:
    """
    Fetch forecast percentile bands for a specific future date.
    GET /api/v1/forecasts/discharge/percentile-bands/
    Returns {'bands': {station_number: band}, 'forecast_run_date': str} or {}.
    """
    if not self.api_enabled or not self.api_client:
        logger.warning("API not available; cannot fetch forecast percentile bands")
        return {}
    try:
        response = self.api_client._request(
            'GET',
            '/api/v1/forecasts/discharge/percentile-bands/',
            params={'date': target_date, 'source': source},
        )
        results = response.get('results', [])
        bands = {r['station_number']: r['band'] for r in results}
        forecast_run_date = response.get('forecast_run_date')
        logger.info(
            f"Fetched forecast percentile bands for {len(bands)} stations "
            f"(date={target_date}, source={source})"
        )
        return {'bands': bands, 'forecast_run_date': forecast_run_date}
    except Exception as e:
        logger.error(f"Failed to fetch forecast percentile bands: {e}")
        return {}
```

---

## Step 2 — `usgs_dashboard/data/data_manager.py`

### 2a — Add cache attributes in `__init__`

Find the block where `_date_range_cache` and `_date_range_cache_time` are initialised (around line 60-80) and add two more:

```python
self._forecast_date_range_cache: dict = {}
self._forecast_date_range_cache_time: float = 0.0
```

### 2b — Add two wrapper methods after `get_percentile_date_range` (ends ~line 966)

```python
def get_forecast_percentile_date_range(self, source: str = 'NWRFC') -> dict:
    """Return forecast min/max dates. Cached 1 hour."""
    now = time.time()
    if (
        self._forecast_date_range_cache
        and (now - self._forecast_date_range_cache_time) < 3600
    ):
        return self._forecast_date_range_cache.copy()
    try:
        result = self.adapter.get_forecast_percentile_date_range(source=source)
        if result.get('min_date') and result.get('max_date'):
            self._forecast_date_range_cache = result
            self._forecast_date_range_cache_time = now
            logger.info(
                f"Forecast percentile date range: "
                f"{result['min_date']} – {result['max_date']} "
                f"(run {result.get('forecast_run_date', '?')})"
            )
        return result
    except Exception as e:
        logger.error(f"Failed to fetch forecast percentile date range: {e}")
        return self._forecast_date_range_cache.copy()


def get_forecast_percentile_bands_for_date(
    self,
    target_date: str,
    source: str = 'NWRFC',
) -> dict:
    """
    Fetch forecast bands for a specific future date.
    Returns {'bands': {station_number: band}, 'forecast_run_date': str}.
    No caching — forecast data updates intraday.
    """
    try:
        return self.adapter.get_forecast_percentile_bands(
            target_date=target_date, source=source
        )
    except Exception as e:
        logger.error(f"Failed to fetch forecast percentile bands for {target_date}: {e}")
        return {}
```

---

## Step 3 — `app.py`

### 3a — Add a `dcc.Store` for forecast date range

Find where the other `dcc.Store` components are registered (around the layout definition) and add:

```python
dcc.Store(id='forecast-date-range-store', storage_type='memory'),
```

### 3b — Add a source-label `html.Small` element near the date picker

The date picker area is around line 707. Below the `dbc.Input` for the date picker, add:

```python
html.Small(
    id='percentile-source-label',
    children="Observed conditions",
    className="text-muted d-block mt-1",
    style={"fontSize": "0.7rem", "whiteSpace": "nowrap"},
),
```

### 3c — Add callback to load forecast date range on startup

Add this callback alongside `load_percentile_date_range` (around line 1288):

```python
@app.callback(
    Output('forecast-date-range-store', 'data'),
    Input('percentile-startup-interval', 'n_intervals'),
    State('forecast-date-range-store', 'data'),
    prevent_initial_call=False,
)
def load_forecast_date_range(startup_intervals, current_range):
    """Fetch forecast date range once on load; skip if already populated."""
    if current_range:
        return no_update
    return data_manager.get_forecast_percentile_date_range()
```

### 3d — Update `init_date_picker` to extend max to forecast window

Currently `init_date_picker` (lines 1311-1326) only takes `percentile-date-range-store` as input.
Replace it with a version that also takes `forecast-date-range-store` and extends the max:

```python
@app.callback(
    [Output('percentile-date-picker', 'min'),
     Output('percentile-date-picker', 'max'),
     Output('percentile-date-picker', 'value')],
    [Input('percentile-date-range-store', 'data'),
     Input('forecast-date-range-store', 'data')],
    prevent_initial_call=True,
)
def init_date_picker(obs_range, fcst_range):
    """Set picker bounds: min from observed, max from forecast (or observed if no forecast)."""
    if not obs_range or not obs_range.get('max_date'):
        return no_update, no_update, no_update

    min_date = obs_range['min_date']

    # Extend max to forecast window if available
    obs_max = obs_range['max_date']
    fcst_max = (fcst_range or {}).get('max_date')
    if fcst_max and fcst_max > obs_max:
        max_date = fcst_max
    else:
        max_date = obs_max

    return min_date, max_date, max_date   # default to latest available
```

### 3e — Update `refresh_percentile_bands` to route observed vs forecast

The current callback (lines 1264-1285) always calls observed bands. Replace its body so future dates
are routed to the forecast endpoint and the `forecast_run_date` is passed along for the source label:

```python
@app.callback(
    [Output('percentile-bands-store', 'data'),
     Output('forecast-run-date-store', 'data')],   # new store, see 3a
    [Input('percentile-refresh-interval', 'n_intervals'),
     Input('percentile-startup-interval', 'n_intervals'),
     Input('selected-percentile-date-store', 'data')],
    State('percentile-bands-store', 'data'),
    prevent_initial_call=False,
)
def refresh_percentile_bands(n_intervals, startup_n_intervals, selected_date, current_bands):
    from datetime import date as _date
    today = _date.today().isoformat()

    if selected_date and selected_date > today:
        # Future date → forecast endpoint
        result = data_manager.get_forecast_percentile_bands_for_date(selected_date)
        bands = result.get('bands', {})
        run_date = result.get('forecast_run_date')
        return bands or no_update, run_date
    elif selected_date:
        # Historical/today → observed endpoint
        new_bands = data_manager.get_percentile_bands_for_date(selected_date)
        return new_bands or no_update, None
    else:
        # No date selected → latest cached observed bands
        new_bands = data_manager.get_cached_percentile_bands()
        return new_bands or no_update, None
```

Also add the new store to the layout (step 3a):

```python
dcc.Store(id='forecast-run-date-store', storage_type='memory'),
```

### 3f — Add callback to update source label

```python
@app.callback(
    Output('percentile-source-label', 'children'),
    [Input('selected-percentile-date-store', 'data'),
     Input('forecast-run-date-store', 'data')],
    prevent_initial_call=False,
)
def update_source_label(selected_date, forecast_run_date):
    from datetime import date as _date, datetime
    today = _date.today().isoformat()

    if selected_date and selected_date > today and forecast_run_date:
        try:
            run_dt = datetime.fromisoformat(forecast_run_date.replace('Z', '+00:00'))
            run_local = run_dt.strftime('%-m/%-d/%Y %-I:%M %p UTC')
        except Exception:
            run_local = forecast_run_date
        return f"Forecast: NWRFC — issued {run_local}"

    return "Observed conditions"
```

---

## Testing checklist

- [ ] Load app — date picker max is today + 8 (or nearby if forecast task ran recently)
- [ ] Source label shows "Observed conditions" on load
- [ ] Click next-date button past today — map recolors with forecast bands, label updates
- [ ] Label shows correct NWRFC run date from API response
- [ ] Clicking back to today or earlier — map returns to observed bands, label resets
- [ ] When forecast data is unavailable (station mapping not yet fixed) — map shows `no_data` grey for forecast dates without error
- [ ] Source label gracefully handles `forecast_run_date: null` (falls back to "Observed conditions")

---

## Known limitation

The forecast percentile pipeline currently produces 0 rows for most stations because `ForecastRun` records (linked to NOAA LID station objects) and `DischargeObservation` records (linked to USGS station objects) do not share the same `Station` primary key. The SQL join requires the same `station_id` for both tables.

**Effect on the dashboard:** Future dates will return empty results and the map will show grey `no_data` markers — same as today when no observed data exists. No errors will occur.

**Resolution:** Fix the station alignment in StreamflowOps (associate NOAA_RFC ForecastRuns with the same Station records that hold DischargeObservation history). Once fixed, rerunning the Celery task will populate the table and the dashboard will display forecast bands automatically.
