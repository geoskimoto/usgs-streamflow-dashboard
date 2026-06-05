# USGS Streamflow Dashboard — Project CLAUDE.md

## What This Is
A Plotly Dash dashboard visualizing USGS streamflow data for the Pacific Northwest and western US. It fetches station data and discharge observations from a private REST API (StreamflowOps/DataOps) and renders interactive maps and water-year overlay plots.

- **Live URL:** `streamflow-dashboard.3rdplaces.io`
- **Local dev:** `python app.py` → `http://localhost:8050`
- **Primary language:** Python 3.12
- **Framework:** Plotly Dash + Dash Bootstrap Components

---

## Architecture at a Glance

```
app.py  (Dash app, callbacks, layout)
manage_cache.py  (CLI for rebuilding/clearing the stats cache)
assets/
  └─ spinner.css   ← hydrology wave loading spinner
  └─ usgs_dashboard/
       ├─ data/data_manager.py          ← USGSDataManager (public API to callbacks)
       │     ├─ stats_cache_manager.py  ← parquet cache for per-day-of-WY statistics
       │     └─ dataops_adapter/        ← abstract data source (API / cache / PostgreSQL)
       │           └─ dataops_client/   ← HTTP client for StreamflowOps REST API
       ├─ components/
       │     ├─ map_component.py    ← Plotly scatter_map with percentile coloring
       │     ├─ viz_manager.py      ← orchestrates water-year plots
       │     └─ filter_panel.py     ← sidebar filter UI
       └─ utils/
             ├─ water_year_calculator.py  ← SINGLE SOURCE OF TRUTH for water-year logic
             ├─ water_year_datetime.py    ← Plotly-aware water-year datetime helpers
             └─ config.py                ← constants, colors, state list, etc.
data/
  └─ stats_cache/  ← parquet files: <site_id>_WY<year>.parquet (gitignored)
```

Key standalone file:
- `streamflow_analyzer.py` — large (31 k LOC) self-contained analysis library; used by viz_manager but with a fallback path.

---

## Data Flow (High Level)

1. On load, `app.py → USGSDataManager.load_regional_gauges()` calls the DataOps adapter.
2. The adapter hits the StreamflowOps REST API (or local cache / PostgreSQL depending on env).
3. Stations are enriched with CSV metadata and returned as a DataFrame.
4. Background thread refreshes percentile bands every 30 min. A 1s startup interval (max 10 fires) ensures colors appear within ~1s of page load rather than waiting for the 30s poll cycle.
5. Clicking a station triggers the **fast plot path** by default:
   - `get_current_year_data()` fetches only the current water year (~200 rows).
   - `get_flow_statistics()` loads pre-computed per-day-of-WY stats from `data/stats_cache/` (parquet). On cache miss, fetches full history, computes stats, and writes the cache.
   - `viz_manager.create_fast_water_year_plot()` renders current year + percentile bands + forecasts with no historical year trace loop.
6. "Last 30 Years" / "Full Period of Record" buttons trigger the full history path: `get_streamflow_data()` → `create_streamflow_plot()` with `history_mode='30yr'` or `'all'`.

---

## Environment Variables

All secrets go in `.env` (see `.env.example`). Key vars:

| Variable | Purpose |
|---|---|
| `USE_DATAOPS_API` | `true` = REST API, `false` = direct PostgreSQL |
| `DATAOPS_API_URL` | StreamflowOps base URL |
| `DATAOPS_API_TOKEN` | Bearer token for API auth |
| `DATAOPS_CACHE_ENABLED` | Enable local disk cache |
| `DATAOPS_CACHE_TTL` | Cache TTL in seconds (default 300) |
| `DB_HOST/PORT/NAME/USER/PASSWORD` | Direct PostgreSQL credentials |
| `DEBUG_MODE` | Enable Dash debug mode |

Never hardcode these. Never commit `.env`.

---

## Deployment

| Path | Purpose |
|---|---|
| `/home/geoskimoto/projects/usgs-streamflow-dashboard/` | Dev working directory (this repo) |
| `/home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/` | Live deployed app |

The deployed app runs under the `streamflowdash` system user via systemd + gunicorn, proxied through nginx. It uses `.venv/` (not `venv/`) as its virtualenv.

**Deploy — push to main, then pull in prod:**

```bash
# 1. Commit and push from dev as usual
git push

# 2. Pull in the deployed directory
cd /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io
sudo -u streamflowdash git pull

# 3. Restart the service
sudo systemctl restart streamflow-dashboard.service
```

**If new Python dependencies were added**, install them after pulling:
```bash
sudo -u streamflowdash /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/.venv/bin/pip install -r /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/requirements.txt -q
```

**To tail logs after deploy:**
```bash
journalctl -u streamflow-dashboard.service -f
```

**SSH deploy key:** `streamflowdash` authenticates to GitHub via an Ed25519 deploy key at `/home/streamflowdash/.ssh/id_ed25519`. The corresponding public key is registered as a read-only deploy key on this repo (`Settings → Deploy keys`). Never delete this key without adding a replacement first.

**Known layout quirks:**
- Deployed venv is `.venv/` — the `venv/` directory in htdocs is unused.
- `data/stats_cache/` is gitignored and builds independently on the server — never commit or force-overwrite it.
- The deployed `.env` has production credentials and is gitignored — it will never be touched by `git pull`.

**Render.com** (alt deployment — see `render.yaml`):
```bash
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 app:server
```

Static files are served via nginx — do not route them through gunicorn.

---

## Testing

```bash
pytest                              # All mocked tests
RUN_INTEGRATION_TESTS=1 pytest      # Include live API tests
pytest -v -s tests/test_data_manager.py   # Specific file
```

- Tests are **mocked by default**. Live API tests require `RUN_INTEGRATION_TESTS=1`.
- `tests/archive/` contains ~55 legacy tests — excluded from collection.
- **Never modify application code to make a failing test pass.** Report failures and stop.

---

## Key Conventions

- **Water year = Oct 1 – Sep 30.** Always use `water_year_calculator.py` — never reimplement inline.
- **Flow units:** discharge is in CFS. Label all axes. Do not mix unit systems silently.
- **Time zones:** USGS data is local time. DataOps API may return UTC. Verify and convert explicitly.
- **Station data types:** distinguish instantaneous vs daily-mean values. They are not interchangeable.
- **Callbacks stay lean.** All data logic belongs in `data_manager.py` or the adapter, not in `app.py` callbacks.
- **Single source of truth:** if a utility exists in `utils/`, use it — do not reimplement in `app.py` or a component.
- **Fallback plots:** `viz_manager` tries `streamflow_analyzer` first, then falls back to `water_year_datetime`. Do not remove the fallback.
- **Stats cache:** `data/stats_cache/<site_id>_WY<year>.parquet` holds per-day-of-WY percentile bands + mean/median. Valid for the entire current water year; auto-rebuilds at Oct 1. Use `manage_cache.py rebuild_stats` to pre-warm. Never commit or rsync this directory — let it build on each environment independently.

---

## Technical Debt to Be Aware Of

- Three separate water-year plot implementations exist (`streamflow_analyzer`, `water_year_datetime`, `viz_manager`). Consolidation is a future goal — don't add a fourth.
- `streamflow_analyzer.py` has its own USGS data-fetch path. The dashboard does not use it for fetching — data always flows through `data_manager`. Only the visualization classes are used.
- The SQLite/database schema documented in `Documentation/DATABASE_SCHEMA.md` is legacy and not used in the current adapter-based architecture.
- Percentile map coloring is **fully implemented end-to-end** (`PERCENTILE_IMPLEMENTATION_PLAN.md`). Background thread → `_percentile_cache` → 30s poll interval + 1s startup interval → `percentile-bands-store` → map callback → band-colored traces. Data lives in `daily_flow_percentiles` DB table (4,867 stations, updated daily). Historical date picker path also wired and working.

---

## ResidCast Forecast Integration

The dashboard displays bias-corrected forecasts from the resid-cast service alongside raw NWRFC/CHPS forecasts for stations that have trained model artifacts.

### Station config: `config/resid_cast_stations.json`

Maps USGS gage ID → `{nwrfc_id, models[], ealstm_available}`. **Do not edit by hand.** Regenerate it from the resid-cast repo whenever stations or models change:

```bash
cd /home/geoskimoto/projects/resid-cast
.venv/bin/python scripts/build_dashboard_config.py
# Writes to ../usgs-streamflow-dashboard/config/resid_cast_stations.json
```

Current coverage: **239 stations total** (all NWRFC stations visible in dashboard).

| Station type | Count | `ealstm_available` | Model list |
|---|---|---|---|
| 13 original quality stations | 13 | some | `xgboost/raw`, `muthre/standalone`, `lstm/raw/general`, `xgboost/raw/general` |
| 47 expanded stations | 47 | some | `muthre/standalone`, `lstm/raw/general`, `xgboost/raw/general` |
| CAMELS-overlap PNW basins | 37 | **true** | EA-LSTM precip-runoff forecasts available |

The `ealstm_available` flag is set manually for the 37 CAMELS-overlap stations that have trained EA-LSTM artifacts and CAMELS forcing data in StreamflowOps.

### Data flow on gauge selection — residual correction

1. `app.py` callback → `data_manager.get_resid_cast_forecasts(site_id, num_runs=5)`
2. `ResidCastAdapter` dispatches to `ResidCastApiClient` (API mode) or `ResidCastDbClient` (direct DB mode) based on `RESID_CAST_USE_API` env var
3. Client hits `GET /api/v1/stations/{nwrfc_id}/forecasts/?limit=5` on the resid-cast FastAPI service (port 8001)
4. Results passed to `viz_manager._add_resid_cast_overlay()` — dashed traces, color-coded by model

### Data flow on gauge selection — EA-LSTM precip-runoff

1. `app.py` callback → `_precip_adapter.get_forecasts(usgs_station_id, num_runs=5)` (module-level singleton)
2. `PrecipRunoffAdapter` (`resid_cast/precip_runoff_adapter.py`) checks `ealstm_available` flag; returns `[]` if false or no `RESID_CAST_API_URL`
3. Calls `GET {RESID_CAST_API_URL}/api/v1/precip-forecasts/{nwrfc_id}/?limit=5` with Bearer token
4. Returns list of `{run_date, model_label="EA-LSTM", model_key="ealstm/precip_runoff", source="precip_runoff", data: DataFrame}`
5. Results passed to `viz_manager._add_precip_overlay()` — dotted amber traces (`["#E67E22","#F0A500",...]`); newest run visible, rest hidden

### Environment variables

| Variable | Purpose |
|---|---|
| `RESID_CAST_USE_API` | `true` = call FastAPI on port 8001; `false` = query SQLite/Postgres directly |
| `RESID_CAST_API_URL` | Base URL of the resid-cast residual correction API (default: `http://localhost:8001`) |
| `RESID_CAST_API_TOKEN` | Bearer token matching `FORECAST_API_TOKEN` in resid-cast `.env` |
| `RESID_CAST_DB_URL` | SQLAlchemy URL for direct DB access when `RESID_CAST_USE_API=false` |
| `PRECIP_CAST_API_URL` | Base URL of the precip-runoff-cast EA-LSTM API (default: `http://localhost:8002`); production: `https://pr-cast.3rdplaces.io` |

`PrecipRunoffAdapter` reads `PRECIP_CAST_API_URL` first, falls back to `RESID_CAST_API_URL` for backward compatibility. Uses `RESID_CAST_API_TOKEN` for Bearer auth.

### Updating after a resid-cast station expansion

1. Run `python scripts/build_dashboard_config.py` in the resid-cast repo
2. Commit the updated `config/resid_cast_stations.json` to the dashboard repo
3. If new stations have EA-LSTM coverage, manually set `ealstm_available: true` in the JSON
4. Deploy the dashboard (rsync or manual copy)
5. No code changes required — the adapters discover stations from the JSON config at startup

---

## Config Files

- `config/system_settings.json` — global dashboard settings (map style, colors, performance)
- `config/resid_cast_stations.json` — ResidCast station config; 60 stations; generated by `resid-cast/scripts/build_dashboard_config.py`
- `usgs_dashboard/utils/config.py` — Python constants (`TARGET_STATES`, `GAUGE_COLORS`, map center, etc.)
- `pytest.ini` — test discovery settings (excludes `tests/archive/`)

---

## Documentation

All design docs live in `Documentation/`:
- `ARCHITECTURE.md` — system design
- `DATABASE_SCHEMA.md` — legacy SQLite schema (for reference only)
- `DEPLOYMENT.md` — deployment steps
- `QUICK_START.md` — onboarding
- **`DISPLAY_BEHAVIOR_SPEC.md` — canonical definition of station classification (Active/Inactive/Unknown), filter logic, map coloring, and plot display behavior. All code changes affecting these systems must be validated against this spec.**

Planning specs at root:
- `PERCENTILE_IMPLEMENTATION_PLAN.md`
- `STREAMFLOWOPS_PERCENTILE_ENDPOINT_SPEC.md`
