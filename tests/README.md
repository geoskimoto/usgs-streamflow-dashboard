# Test Suite

Comprehensive test suite for the USGS Streamflow Dashboard, covering the DataOps
API client, adapter layer, data manager, UI callbacks, and water year utilities.

## Structure

| File | Coverage | Mock/Live |
|------|----------|-----------|
| `conftest.py` | Shared fixtures, sample API data | — |
| `test_dataops_client.py` | HTTP client, models, pagination, errors, caching | Mocked |
| `test_dataops_adapter.py` | Adapter modes, DataFrame conversion, cache fallback | Mocked |
| `test_data_manager.py` | Station enrichment, regional loading, streamflow data | Mocked |
| `test_app_callbacks.py` | Dash callbacks: data loading, filters, selection, auth | Mocked |
| `test_water_year.py` | Water year calculations, config values | Unit |
| `test_integration.py` | End-to-end against live DataOps API | Live |

## Running Tests

```bash
# All unit/mock tests (recommended for development)
pytest

# Include live API integration tests
RUN_INTEGRATION_TESTS=1 pytest

# Specific test file
pytest tests/test_dataops_client.py

# Specific test class
pytest tests/test_data_manager.py::TestLoadRegionalGauges

# Verbose with print output
pytest -v -s
```

## Archived Tests

Legacy tests (SQLite-based, direct-USGS-API) are preserved in `tests/archive/`
for reference. They are excluded from collection via `pytest.ini`.