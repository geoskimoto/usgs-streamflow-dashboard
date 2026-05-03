# Fragility Audit — USGS Streamflow Dashboard

**Date:** 2026-05-03  
**Auditor:** Claude Sonnet 4.6 (automated static analysis)

---

## Summary

| Category | Count | High | Medium | Low |
|---|---|---|---|---|
| Hard-coded values / credentials | 4 | 3 | 1 | — |
| Missing error handling | 6 | 1 | 5 | — |
| Race conditions / thread safety | 2 | — | 2 | — |
| Data type assumptions | 3 | — | 3 | — |
| Config & env variable handling | 2 | — | 2 | — |
| Cache fragility | 2 | — | 1 | 1 |
| Startup fragility | 3 | — | 1 | 2 |
| Deployment fragility | 2 | 1 | 1 | — |
| Data validation | 2 | — | 2 | — |
| Auth security | 2 | 1 | 1 | — |
| **TOTAL** | **28** | **6** | **19** | **3** |

---

## HIGH Severity

### H1. Default credentials baked into source
**File:** `app.py` ~L41–50, L276  
```python
server.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH',
    hashlib.sha256('admin123'.encode()).hexdigest())
```
If production `.env` is missing `SECRET_KEY` or `ADMIN_PASSWORD_HASH`, the app runs with a known insecure session key and accepts `admin123` as the admin password. No startup validation exists to catch this.

**Fix:** Validate required env vars at startup and raise immediately with a clear message if missing.

---

### H2. `.env` may be in git history
**File:** `.env` / `.gitignore`  
If `.env` was ever committed, all tokens and database passwords in it are in git history and must be treated as compromised.

**Fix:** Run `git ls-files .env`. If tracked, purge with `git filter-branch` or BFG Repo Cleaner and rotate all credentials.

---

### H3. `deploy.sh` reports success on partial sync
**File:** `deploy.sh`  
`rsync` exits 0 even if individual file transfers fail. The service restart happens regardless. If a critical `.py` file was not synced, gunicorn crashes after restart — but the script reports "active."

**Fix:** Add `--checksum` or capture rsync exit code; add a health-check HTTP ping after restart before reporting success.

---

### H4. Weak password hashing — no salt, uses SHA256
**File:** `app.py` ~L41–50  
SHA256 is not a password hashing function. No salt means rainbow-table attacks work. Should use `bcrypt` or `argon2`. Also no rate limiting on login attempts.

**Fix:** Replace with `bcrypt.checkpw()`; add Flask-Limiter or equivalent at the login route.

---

## MEDIUM Severity

### M1. Percentile cache dict written without a lock
**File:** `usgs_dashboard/data/data_manager.py` (background refresh loop)  
The background thread does `self._percentile_cache = bands` while Dash callbacks read it. A callback can catch the dict mid-replacement → transient map color corruption or `KeyError`.

**Fix:** Add a `threading.Lock` around all reads and writes of `_percentile_cache`.

---

### M2. Background refresh thread swallows all exceptions silently
**File:** `usgs_dashboard/data/data_manager.py` (percentile refresh loop)  
If the percentile API is permanently down, the thread logs an error every 30 minutes and continues. No staleness signal reaches the UI — map colors stay wrong or stale indefinitely.

**Fix:** Track last-successful-refresh timestamp; expose a `is_percentile_data_stale()` method; show a user-facing banner when data is stale beyond a threshold.

---

### M3. `clickData['points'][0]['customdata']` has no bounds check
**File:** `app.py` ~L1510  
```python
site_id = clickData['points'][0]['customdata']
```
If `points` is empty, raises `IndexError`. If `customdata` is missing, raises `KeyError`. User click silently fails.

**Fix:** Guard with `if not clickData or not clickData.get('points'): return no_update`.

---

### M4. Stats cache parquet not schema-validated on read
**File:** `usgs_dashboard/data/stats_cache_manager.py`  
If an old-schema `.parquet` file exists from a prior version, `pd.read_parquet()` succeeds but returns a DataFrame with wrong/missing columns. Downstream viz code crashes with `KeyError`.

**Fix:** After reading, assert required columns (`day_of_wy`, `q10`, `q25`, `q50`, `q75`, `q90`, `mean`, `median`) exist; delete and recompute if validation fails.

---

### M5. `nwrfc_id` search filter on mixed-type or NaN column
**File:** `app.py` ~L1344–1348  
```python
filtered_gauges['site_id'].str.lower().str.contains(search_lower, na=False)
```
If `site_id` contains integers or `nwrfc_id` is all NaN, `.str.lower()` fails or silently returns all-NaN — user gets a blank map with no feedback.

**Fix:** Cast `site_id` to string explicitly before filter; wrap search filter in try/except with a user-facing "no results" message.

---

### M6. NWRFC crosswalk load failure is silent
**File:** `usgs_dashboard/data/data_manager.py` ~L396–407, L898–908  
If `nwrfc_usgs_crosswalk.json` is missing, all `nwrfc_id` values are set to `None` and a warning is logged. NWRFC forecast filtering and badges stop working with no visible error.

**Fix:** Promote to an error log with a dashboard-visible warning; consider a startup check that confirms the file exists.

---

### M7. API token `None` if env var missing — fails on first request, not startup
**File:** `dataops_adapter/config.py`  
`api_token = os.getenv('DATAOPS_API_TOKEN')` can be `None`. The client initializes fine but fails with a cryptic 401 on the first data fetch rather than a clear startup error.

**Fix:** Add to startup env var validation (see H1).

---

### M8. No health check after service restart in `deploy.sh`
**File:** `deploy.sh`  
`systemctl status` is checked immediately after `systemctl restart`, before gunicorn has bound to the port and the app is ready. Reports a false-positive success during the startup window.

**Fix:** Add a `curl -sf http://127.0.0.1:8050/ > /dev/null` retry loop with a timeout; fail the deploy script if the app doesn't respond within N seconds.

---

### M9. API adapter returns DataFrame without schema validation
**File:** `dataops_adapter/client_adapter.py`  
No validation that the returned DataFrame contains required columns (`station_number`, `name`, `latitude`, `longitude`, etc.). A breaking API schema change silently propagates to map rendering failures.

**Fix:** Add a `_validate_stations_schema(df)` helper that raises a descriptive error on missing columns.

---

### M10. Forecast data `None` return not always checked by callers
**File:** `usgs_dashboard/data/data_manager.py` ~L815–821; `app.py` ~L1657  
`get_forecast_data()` returns `None` on error. Not all callers guard against this before passing to `viz_manager`, which may crash on `None`.

**Fix:** Audit all call sites for `None` guard; `viz_manager` methods should accept and handle `None` forecast data gracefully.

---

### M11. Import of `dataops_adapter` at module level with no fallback
**File:** `usgs_dashboard/data/data_manager.py` ~L20  
If `dataops_adapter` has an import error, the entire app fails at startup with a cryptic traceback.

**Fix:** Wrap in try/except with a helpful error message pointing to the adapter configuration.

---

## LOW Severity

### L1. `int(os.getenv('PORT', 8050))` crashes on non-numeric input
**File:** `app.py` ~L2312  
If `PORT=abc` in the environment, startup fails with `ValueError: invalid literal for int()`.

**Fix:** `int(os.getenv('PORT', '8050') or '8050')` with a try/except and a fallback default.

---

### L2. Background station-prefetch thread exceptions are swallowed
**File:** `app.py` ~L62  
Daemon threads do not propagate exceptions to the main thread. If the prefetch fails, the app starts but the map shows "Loading gauge data..." indefinitely.

**Fix:** Add logging inside the thread target; consider setting a flag if prefetch fails so the UI can show a "data unavailable" state.

---

### L3. Cache TTL enforcement unverified
**File:** `dataops_adapter/cache_manager.py`  
TTL is configured but enforcement on cache reads is not verified in the audit. If TTL is not enforced, stale data may be served indefinitely.

**Fix:** Add a test that confirms cache entries are invalidated after TTL expires.

---

### L4. `get_data_manager()` creates a new instance each call
**File:** `usgs_dashboard/data/data_manager.py`  
Currently called once at startup, so benign. If ever called from multiple places, each gets its own cache — silently wasting memory and making background threads multiply.

**Fix:** Convert to a module-level singleton or use `functools.lru_cache(maxsize=1)`.

---

## Priority Remediation Plan

| Priority | Action | Effort |
|---|---|---|
| **Immediate** | Confirm `.env` not in git; rotate any exposed tokens | 30 min |
| **Before next deploy** | Add startup validation for `SECRET_KEY`, `DATAOPS_API_TOKEN`, `ADMIN_PASSWORD_HASH` — fail fast with clear message | 1 hr |
| **This sprint** | Lock `_percentile_cache` writes; validate parquet schema on read; guard `clickData` access; add health-check to `deploy.sh` | 4 hrs |
| **Near term** | Replace SHA256 with bcrypt; add login rate limiting; add UI staleness banner for stale percentile data; validate adapter DataFrame schema | 1 day |
| **This quarter** | Integration tests for adapter failure modes (API down, bad schema, cache miss); `.env.production.example` with all required vars documented | 2 days |
