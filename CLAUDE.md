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
  └─ usgs_dashboard/
       ├─ data/data_manager.py      ← USGSDataManager (public API to callbacks)
       │     └─ dataops_adapter/    ← abstract data source (API / cache / PostgreSQL)
       │           └─ dataops_client/  ← HTTP client for StreamflowOps REST API
       ├─ components/
       │     ├─ map_component.py    ← Plotly scatter_map with percentile coloring
       │     ├─ viz_manager.py      ← orchestrates water-year plots
       │     └─ filter_panel.py     ← sidebar filter UI
       └─ utils/
             ├─ water_year_calculator.py  ← SINGLE SOURCE OF TRUTH for water-year logic
             ├─ water_year_datetime.py    ← Plotly-aware water-year datetime helpers
             └─ config.py                ← constants, colors, state list, etc.
```

Key standalone file:
- `streamflow_analyzer.py` — large (31 k LOC) self-contained analysis library; used by viz_manager but with a fallback path.

---

## Data Flow (High Level)

1. On load, `app.py → USGSDataManager.load_regional_gauges()` calls the DataOps adapter.
2. The adapter hits the StreamflowOps REST API (or local cache / PostgreSQL depending on env).
3. Stations are enriched with CSV metadata and returned as a DataFrame.
4. Background thread refreshes percentile bands every 30 min.
5. Clicking a station triggers `get_streamflow_data()` → `viz_manager` builds a water-year overlay plot.

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

**Live server** (VPS via CloudPanel + systemd):
```bash
# On the VPS as root or sudo user:
cd /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io
sudo -u streamflowdash git pull origin main
sudo systemctl restart streamflow-dashboard.service
sudo systemctl status streamflow-dashboard.service
journalctl -u streamflow-dashboard.service -f
```

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

---

## Technical Debt to Be Aware Of

- Three separate water-year plot implementations exist (`streamflow_analyzer`, `water_year_datetime`, `viz_manager`). Consolidation is a future goal — don't add a fourth.
- `streamflow_analyzer.py` has its own USGS data-fetch path. The dashboard does not use it for fetching — data always flows through `data_manager`. Only the visualization classes are used.
- The SQLite/database schema documented in `Documentation/DATABASE_SCHEMA.md` is legacy and not used in the current adapter-based architecture.
- Percentile map coloring is partially implemented (`PERCENTILE_IMPLEMENTATION_PLAN.md`). The background refresh thread and map component support it, but end-to-end integration may be incomplete.

---

## Config Files

- `config/system_settings.json` — global dashboard settings (map style, colors, performance)
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
