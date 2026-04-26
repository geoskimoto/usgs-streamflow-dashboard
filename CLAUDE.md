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

**How this is currently deployed:**
The dev repo and the deployed app live on the **same VPS**. Files are copied manually from the dev directory to the htdocs directory — there is no `git pull` on the deployed side.

| Path | Purpose |
|---|---|
| `/home/geoskimoto/projects/usgs-streamflow-dashboard/` | Dev working directory (this repo) |
| `/home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/` | Live deployed app |

The deployed app runs under the `streamflowdash` system user via systemd + gunicorn, proxied through nginx. It uses `.venv/` (not `venv/`) as its virtualenv.

**Deploy — one command:**

```bash
./deploy.sh
```

`deploy.sh` rsyncs all changed files (excluding `.env`, `data/stats_cache/`, `.git`, `__pycache__`), fixes ownership, and restarts the service. Always run from the dev directory root.

**If new Python dependencies were added**, install them after deploying:
```bash
sudo -u streamflowdash /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/.venv/bin/pip install -r /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/requirements.txt -q
```

**To tail logs after deploy:**
```bash
journalctl -u streamflow-dashboard.service -f
```

**Known layout quirks:**
- Deployed venv is `.venv/` — the `venv/` directory in htdocs is unused.
- `data/stats_cache/` holds the water-year statistics parquet cache — do **not** rsync this from dev; let it build on the server.
- The deployed `.env` has production credentials and must never be overwritten from dev.

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

Maps USGS gage ID → `{nwrfc_id, models[]}`. **Do not edit by hand.** Regenerate it from the resid-cast repo whenever stations or models change:

```bash
cd /home/geoskimoto/projects/resid-cast
.venv/bin/python scripts/build_dashboard_config.py
# Writes to ../usgs-streamflow-dashboard/config/resid_cast_stations.json
```

Current coverage: **60 stations**.

| Station type | Model list |
|---|---|
| 13 original quality stations | `xgboost/raw`, `muthre/standalone`, `lstm/raw/general`, `xgboost/raw/general` |
| 47 expanded stations | `muthre/standalone`, `lstm/raw/general`, `xgboost/raw/general` |

### Data flow on gauge selection

1. `app.py` callback → `data_manager.get_resid_cast_forecasts(site_id, num_runs=5)`
2. `ResidCastAdapter` dispatches to `ResidCastApiClient` (API mode) or `ResidCastDbClient` (direct DB mode) based on `RESID_CAST_USE_API` env var
3. Client hits `GET /api/v1/stations/{nwrfc_id}/forecasts/?limit=5` on the resid-cast FastAPI service (port 8001)
4. Results passed to `viz_manager._add_resid_cast_overlay()` — dashed traces, color-coded by model

### ResidCast environment variables

| Variable | Purpose |
|---|---|
| `RESID_CAST_USE_API` | `true` = call FastAPI on port 8001; `false` = query SQLite/Postgres directly |
| `RESID_CAST_API_URL` | Base URL of the resid-cast API (default: `http://localhost:8001`) |
| `RESID_CAST_API_TOKEN` | Bearer token matching `FORECAST_API_TOKEN` in resid-cast `.env` |
| `RESID_CAST_DB_URL` | SQLAlchemy URL for direct DB access when `RESID_CAST_USE_API=false` |

### Updating after a resid-cast station expansion

1. Run `python scripts/build_dashboard_config.py` in the resid-cast repo
2. Commit the updated `config/resid_cast_stations.json` to the dashboard repo
3. Deploy the dashboard (rsync or manual copy)
4. No code changes required — the adapter discovers stations from the JSON config at startup

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

Planning specs at root:
- `PERCENTILE_IMPLEMENTATION_PLAN.md`
- `STREAMFLOWOPS_PERCENTILE_ENDPOINT_SPEC.md`
