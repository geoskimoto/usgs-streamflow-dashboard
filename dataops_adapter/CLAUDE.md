# dataops_adapter Package

Abstracts the data source so the rest of the application doesn't care whether data comes from the StreamflowOps REST API, a local disk cache, or a direct PostgreSQL connection.

## Adapter Modes

Controlled by the `USE_DATAOPS_API` environment variable and `DATAOPS_ADAPTER_MODE`:

| Mode | Class | When Used |
|---|---|---|
| `api` | `DataOpsAdapter` | REST API only; fails if API is down |
| `cache` | `DataOpsAdapter` | Local disk cache only (offline) |
| `hybrid` | `DataOpsAdapter` | API with cache fallback — **recommended for production** |
| `db` | `DirectDBAdapter` | Direct PostgreSQL (same-server deployments) |

`__init__.py` contains the factory function that reads env vars and returns the correct adapter instance. `data_manager.py` calls this factory — nothing else should.

## Key Files

- `client_adapter.py` — `DataOpsAdapter`: wraps `DataOpsClient` with caching; main implementation
- `db_adapter.py` — `DirectDBAdapter`: PostgreSQL queries via psycopg2
- `cache_manager.py` — disk-backed cache (DiskCache); shared between adapter modes
- `models.py` — shared data models (Station, DischargeObservation, etc.)
- `config.py` — adapter configuration (TTL, timeout, SSL, etc.)
- `exceptions.py` — `DataOpsError`, `CacheError`, etc.

## Rules

- The adapter layer must always return **pandas DataFrames** (not raw dicts or models) so the data layer above doesn't need to know which adapter ran.
- Cache TTL is configurable via `DATAOPS_CACHE_TTL` (default 300s). Do not hardcode cache durations in adapter logic.
- SSL verification is controlled by `DATAOPS_VERIFY_SSL`. Never disable SSL in production without an explicit env flag.
- All adapter errors should raise from `exceptions.py` — never let raw `requests.RequestException` or `psycopg2.Error` bubble up to `data_manager.py`.
- Do not add business logic (water-year math, station enrichment) to this layer. It is fetch + transform only.
