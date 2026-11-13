# Flow-unit toggle (cfs / cms) — plan & spec

Status: approved design, tests-first. Scale: existing dashboard, no new infra.

## Decisions (user-approved)
- Default display unit: **cfs** for all stations. Global toggle (not per-station). Resets to cfs on every page load (no localStorage; plain `dcc.Store` with default `"cfs"`).
- Static hover-label PNG plots are out of scope.
- Percentiles / percent-of-normal / map colors are unit-free: unchanged.

## Findings
- DataOps rows carry a `unit` column per observation: EC (BC) = `cms`, USGS = `cfs` (verified live 2026-11-13).
- `'cfs'` is hardcoded in ~40 hover templates and 6 axis titles in `usgs_dashboard/components/viz_manager.py`, and in `streamflow_analyzer.py` (`yaxis_title='Discharge (cfs)'`). `create_fast_water_year_plot` sets no y-axis title at all.
- Forecast overlays (NWRFC, ResidCast, EA-LSTM, blended) are cfs-only (`discharge_cfs`), US stations only.
- Stats cache `data/stats_cache/<site>_WY<yr>.parquet` is computed from native-unit data. **Must stay native** — never write converted values into it.

## Design
1. `usgs_dashboard/utils/units.py` (single source of truth)
   - `CFS_PER_CMS = 35.3146667` (1 m³/s in ft³/s)
   - `normalize_unit(u) -> 'cfs' | 'cms'` (case-insensitive; accepts `'cfs'`, `'cms'`, `'m3/s'`, `'m³/s'`; `None`/NaN -> `'cfs'`; unknown -> `ValueError`)
   - `convert_flow(values, from_unit, to_unit)` — scalar / ndarray / Series; same unit returns equal values; NaN preserved.
   - `unit_label(unit) -> 'cfs' | 'm³/s'`
   - `axis_title(unit, prefix='Discharge') -> 'Discharge (cfs)' | 'Discharge (m³/s)'`
   - `convert_frame(df, to_unit, cols=None) -> DataFrame` — returns a **copy**; converts each row from its own `unit` column (default `'cfs'` if column missing) into `to_unit`; sets `unit` column to `to_unit`. Default `cols`: whichever of `discharge`, `discharge_cfs`, `q10 q25 q50 q75 q90 mean median` are present. Never mutates the input.
2. `data_manager.py`
   - `get_streamflow_data` stays **native** (stats-cache input must not be converted).
   - `get_current_year_data(site_id, display_unit='cfs')` and `get_flow_statistics(site_id, display_unit='cfs')` convert on the way out. Statistics: native unit is taken from the site's full-history `unit` column; cached parquet is never altered.
   - Forecast getters (`get_resid_cast_forecasts`, `get_blended_forecasts`, nwrfc) accept `display_unit='cfs'` and convert `discharge_cfs`-style frames (source is always cfs).
3. `viz_manager.py` — every plot builder takes `unit='cfs'`; all hovertemplates and `yaxis_title`s are built from `unit_label` / `axis_title`. `create_fast_water_year_plot` gets a y-axis title. `streamflow_analyzer.py` fallback path gets the same.
4. UI — `filter_panel.py`: `dbc.RadioItems(id="flow-unit-toggle", options cfs / "m³/s (cms)", value="cfs", inline)` in its own "Flow units" section; `dcc.Store(id="flow-unit-store", data="cfs")` in the layout. Plot callbacks take the toggle as an `Input` and pass `display_unit`/`unit` down; callbacks stay lean.
5. Out of scope / follow-up: station info panel and any text that shows a flow number (check during implementation; list in PR).

## Requirements (testable)
- R1 `convert_flow(1, 'cms', 'cfs') == pytest.approx(35.3146667)`; cfs->cms inverse; round trip within 1e-9 relative.
- R2 `convert_frame` handles mixed `unit` rows, doesn't mutate input, preserves NaN & non-flow columns, sets `unit`.
- R3 Same-unit conversion is the identity.
- R4 `get_flow_statistics(site, 'cms')` for a native-cfs site returns values ÷35.3146667 AND the on-disk parquet is byte-identical before/after (cache stays native).
- R5 `get_flow_statistics` for a native-cms site with `display_unit='cfs'` returns ×35.3146667; the parquet is native cms.
- R6 Every figure from every `viz_manager` builder has a non-empty y-axis title containing the unit label for the requested unit, and no hovertemplate contains the other unit's label.
- R7 Layout contains `flow-unit-toggle` (default `"cfs"`) and `flow-unit-store` (default `"cfs"`); `tests/test_layout_ids.py` guard stays green.
- R8 No localStorage persistence: the store is not `storage_type='local'`/`'session'`.

## Steps (each its own commit)
1. Tests (separate agent) — red.
2. `utils/units.py`.
3. `data_manager` conversion + cache-stays-native.
4. `viz_manager` + `streamflow_analyzer` labels.
5. UI toggle + callback wiring.
6. Independent mutation/semantic review; deploy per CLAUDE.md.

## Addendum (2026-11-13): precision + review gaps

### R9 — cms hover precision
In cms mode, `apply_unit_labels` rewrites the number format of every **flow** placeholder in a trace's `hovertemplate` to `,.4r` (4 significant digits, thousands separator): placeholders `%{y:<fmt>}`, `%{customdata[<n>]:<fmt>}` where `<fmt>` is any d3 format ending in `f` (e.g. `.0f`, `,.0f`, `.1f`, `,.1f`).
- Result e.g. `%{y:,.0f}` -> `%{y:,.4r}`; `%{customdata[2]:.1f}` -> `%{customdata[2]:,.4r}`.
- NOT touched: `%{x:...}` (e.g. exceedance %), bare `%{customdata}` (date text), `%{y}` with no format, anything non-flow.
- cfs mode: hovertemplates are byte-identical to what the builder produced (no format rewriting).
- Idempotent (applying twice == once). Word-boundary: the unit word replacement only touches the standalone token `cfs` (so `cfs_forecast`, `mcfs` untouched).
- Applies to every builder and overlay already covered in tests/test_unit_toggle_viz.py.

### R10 — review gaps to pin
- `USGSDataManager.convert_forecast_runs(runs, display_unit)`: cfs/None-ish -> returns runs unchanged; cms -> converts every numeric column whose name contains discharge/flow/cfs (e.g. `discharge_cfs`) by 1/35.3146667, leaves `datetime` and non-numeric columns alone, does NOT mutate the caller's run dicts or DataFrames, keeps `run_date`/`model_label` keys, passes through empty/None/runs with empty or non-DataFrame `data`. Also check `get_resid_cast_forecasts`, `get_blended_forecasts`, `get_nwrfc_forecasts`, `get_forecast_data` apply it (mock the underlying adapters/clients).
- Real-time: `get_realtime_data(site, display_unit)` converts per-row from `unit` (cms->cfs default); empty stays empty. `create_fast_water_year_plot(..., data_manager=dm, unit=u)` and `create_streamflow_plot(..., data_manager=dm, unit=u)` must call `dm.get_realtime_data(site_id, display_unit=u)` (assert on the mock) and the realtime trace's plotted values must equal what the mock returned (builders don't rescale).
- `_native_unit`: mode of `unit` column; ignores NaN; all-NaN/empty/absent column -> 'cfs'; mixed frame picks majority; unknown strings raise ValueError.
- `get_flow_statistics` returns a copy: mutating the result doesn't change the next call's result / cached frame; `get_current_year_data` on empty frame returns empty.
- `convert_flow(x, u, u)` for Series/ndarray returns an equal-valued *copy* (not same object); `normalize_unit('  CFS ')` -> 'cfs'.
- `apply_unit_labels(fig, 'cms', set_title=False)` leaves y-axis title untouched on a title-less figure; `set_title=True` adds `Discharge (m³/s)`.
