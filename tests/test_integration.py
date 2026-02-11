"""
Integration tests against the live DataOps API.

These tests verify real connectivity and data availability.
Skip with:  pytest -m "not integration"
Run only:   pytest -m integration
"""

import os
import pytest
import pandas as pd
from datetime import datetime, timedelta

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# Skip entire module if no API connectivity desired
SKIP_REASON = "Set RUN_INTEGRATION_TESTS=1 to run live API tests"
if not os.environ.get("RUN_INTEGRATION_TESTS"):
    pytest.skip(SKIP_REASON, allow_module_level=True)


@pytest.fixture(scope="module")
def client():
    from dataops_client import DataOpsClient
    return DataOpsClient(
        base_url="https://streamflowops.3rdplaces.io",
        cache_enabled=False,
        timeout=60,
    )


@pytest.fixture(scope="module")
def adapter():
    from dataops_adapter import DataOpsAdapter
    return DataOpsAdapter(mode="api")


@pytest.fixture(scope="module")
def data_manager():
    from usgs_dashboard.data.data_manager import USGSDataManager
    return USGSDataManager()


# ==========================================================================
# API Client Integration Tests
# ==========================================================================

class TestLiveAPIClient:
    """Test DataOpsClient against the live API."""

    def test_get_stations_returns_results(self, client):
        result = client.get_stations(state="WA", limit=5)
        assert result.count > 0
        assert len(result.results) > 0
        assert result.results[0].station_number is not None

    def test_get_stations_filters_by_state(self, client):
        result = client.get_stations(state="OR", limit=5)
        assert result.count > 0

    def test_get_single_station(self, client):
        station = client.get_station("12108500")
        assert station.station_number == "12108500"
        assert station.name is not None
        assert station.agency == "USGS"

    def test_get_station_data_with_data(self, client):
        """Station 12108500 is known to have data."""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        result = client.get_station_data(
            "12108500", start_date=start_date, end_date=end_date
        )
        # May or may not have recent data, but shouldn't error
        assert isinstance(result, list)

    def test_get_station_data_returns_observations(self, client):
        """Test with a known date range that has data."""
        result = client.get_station_data(
            "12108500",
            start_date="2026-01-01",
            end_date="2026-02-07",
            data_type="daily_mean",
        )
        assert len(result) > 0
        obs = result[0]
        assert obs.station_number == "12108500"
        assert obs.discharge_value > 0
        assert obs.unit == "cfs"


# ==========================================================================
# Adapter Integration Tests
# ==========================================================================

class TestLiveAdapter:
    """Test DataOpsAdapter against the live API."""

    def test_get_stations_returns_dataframe(self, adapter):
        df = adapter.get_stations(state="WA", limit=10)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "station_number" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns

    def test_get_discharge_data(self, adapter):
        df = adapter.get_discharge_data(
            "12108500", "2026-01-01", "2026-02-07"
        )
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "date" in df.columns
            assert "discharge" in df.columns

    def test_test_connection(self, adapter):
        assert adapter.test_connection() is True


# ==========================================================================
# Data Manager Integration Tests
# ==========================================================================

class TestLiveDataManager:
    """Test USGSDataManager against the live API."""

    def test_load_regional_gauges(self, data_manager):
        df = data_manager.load_regional_gauges(max_sites=5)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "site_id" in df.columns
        assert "station_name" in df.columns
        assert "state" in df.columns

    def test_get_streamflow_data(self, data_manager):
        df = data_manager.get_streamflow_data(
            "12108500", "2026-01-01", "2026-02-07"
        )
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "discharge" in df.columns
            assert "site_no" in df.columns

    def test_get_adapter_status(self, data_manager):
        status = data_manager.get_adapter_status()
        assert status["mode"] in ("api", "hybrid", "cache")
        assert status["api_enabled"] is True
