# tests/

## Running Tests

```bash
pytest                                   # All mocked tests (default)
RUN_INTEGRATION_TESTS=1 pytest           # Include live API integration tests
pytest -v -s tests/test_data_manager.py  # Single file, verbose
pytest tests/test_water_year.py::TestGetWaterYear  # Single class
```

## Test Files

| File | What It Covers |
|---|---|
| `conftest.py` | Shared fixtures: mock API responses, sample station/discharge DataFrames |
| `test_dataops_client.py` | HTTP client — mocked `requests` |
| `test_dataops_adapter.py` | Adapter modes (api/cache/hybrid), fallback behavior |
| `test_data_manager.py` | Station loading, enrichment, caching behavior |
| `test_app_callbacks.py` | Dash callback outputs (data loading, filtering, auth) |
| `test_water_year.py` | Pure unit tests for water-year calculator functions |
| `test_integration.py` | Live API tests — only run with `RUN_INTEGRATION_TESTS=1` |

## Rules

- **Never modify application code to make a failing test pass.** If a test fails, report which test and why, then stop. Only fix the test itself if the test is clearly wrong.
- Mock the DataOps API in all tests except `test_integration.py`. Do not hit the live API in CI.
- Integration tests require `DATAOPS_API_URL` and `DATAOPS_API_TOKEN` in the environment.
- `tests/archive/` contains ~55 legacy tests — do not move files out of archive without vetting them for compatibility with the current adapter architecture.
- Add new tests alongside any new feature. Minimum coverage: unit test for any new utility function, adapter-level mock test for any new API endpoint usage.
- Fixtures for sample data live in `conftest.py`. Reuse them — do not create duplicate sample DataFrames in individual test files.
