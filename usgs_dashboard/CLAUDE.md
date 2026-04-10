# usgs_dashboard Package

This is the core application package. It contains the data access layer, UI components, and utilities.

## Package Layout

```
usgs_dashboard/
├─ data/
│   └─ data_manager.py   ← USGSDataManager — the only public data API for callbacks
├─ components/
│   ├─ map_component.py        ← station map (Plotly scatter_map)
│   ├─ modern_map_component.py ← alternative map (prefer map_component.py)
│   ├─ viz_manager.py          ← water-year plot orchestration
│   └─ filter_panel.py         ← sidebar filter UI
└─ utils/
    ├─ config.py                ← constants and settings
    ├─ water_year_calculator.py ← SINGLE SOURCE OF TRUTH for water-year logic
    └─ water_year_datetime.py   ← Plotly-aware datetime helpers
```

## Data Layer Rules

- `data_manager.py` is the **only** entry point for callbacks in `app.py`. Callbacks must not import from `dataops_adapter` or `dataops_client` directly.
- `USGSDataManager` maintains an in-memory station cache. Avoid re-fetching stations on every callback.
- Percentile bands are refreshed in a background daemon thread every 30 minutes via `start_percentile_background_refresh()`. This is started once at app startup.

## Component Rules

- `map_component.py` uses modern `px.scatter_map` (no Mapbox token required). Do not revert to deprecated `px.scatter_mapbox`.
- `viz_manager.py` follows a strategy pattern: try `streamflow_analyzer.StreamflowVisualizer` → fall back to `water_year_datetime.create_water_year_plot()`. Preserve this pattern — never remove the fallback.
- Keep component functions focused: map data prep → go.Figure construction. No API calls inside components.

## Utils Rules

- `water_year_calculator.py` has **no imports beyond stdlib**. Keep it pure. Do not add dependencies.
- All water-year calculations throughout the app must use functions from `water_year_calculator.py`. Never compute water years inline elsewhere.
- `config.py` is the single source for `TARGET_STATES`, `GAUGE_COLORS`, map center coordinates, and plot palette. If a constant is added to `app.py` instead, move it here.
