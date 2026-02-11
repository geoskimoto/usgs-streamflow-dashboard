"""
Tests for the DataOps Adapter layer (dataops_adapter/).

Verifies adapter mode selection, station/discharge DataFrame conversion,
cache fallback in hybrid mode, and error propagation.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from dataops_adapter import DataOpsAdapter, AdapterError, APIError, CacheError
from dataops_adapter.cache_manager import CacheManager
from dataops_adapter.config import AdapterConfig
from dataops_client.models import (
    Station,
    DischargeObservation,
    PaginatedResponse,
)

from conftest import (
    SAMPLE_STATION_LIST_RESPONSE,
    SAMPLE_DISCHARGE_RESPONSE,
    SAMPLE_STATION_API_RESPONSE,
)


# ==========================================================================
# Config / Mode Tests
# ==========================================================================

class TestAdapterConfig:
    """Test adapter configuration and mode detection."""

    def test_hybrid_mode(self, env_hybrid):
        cfg = AdapterConfig()
        assert cfg.get_mode() == "hybrid"

    def test_api_only_mode(self, env_dataops_enabled):
        cfg = AdapterConfig()
        assert cfg.get_mode() == "api"

    def test_cache_only_mode(self, env_cache_only):
        cfg = AdapterConfig()
        assert cfg.get_mode() == "cache"

    def test_api_url_from_env(self, env_dataops_enabled):
        cfg = AdapterConfig()
        assert cfg.api_url == "https://streamflowops.3rdplaces.io"


# ==========================================================================
# Adapter Initialization Tests
# ==========================================================================

class TestAdapterInit:
    """Test DataOpsAdapter initialization."""

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    @patch("dataops_adapter.client_adapter.CacheManager")
    def test_hybrid_mode_creates_both(self, MockCache, MockClient, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")
        assert adapter.api_enabled is True
        assert adapter.cache_enabled is True

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_api_mode_no_cache(self, MockClient, env_dataops_enabled):
        adapter = DataOpsAdapter(mode="api")
        assert adapter.api_enabled is True
        assert adapter.cache_enabled is False

    @patch("dataops_adapter.client_adapter.CacheManager")
    def test_cache_mode_no_api(self, MockCache, env_cache_only):
        adapter = DataOpsAdapter(mode="cache")
        assert adapter.api_enabled is False
        assert adapter.cache_enabled is True


# ==========================================================================
# Station DataFrame Conversion Tests
# ==========================================================================

class TestStationsToDataFrame:
    """Test _stations_to_dataframe() conversion."""

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_converts_stations_to_df(self, MockClient, env_dataops_enabled):
        adapter = DataOpsAdapter(mode="api")

        stations = [
            Station.from_dict(r) for r in SAMPLE_STATION_LIST_RESPONSE["results"]
        ]
        df = adapter._stations_to_dataframe(stations)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "station_number" in df.columns
        assert "name" in df.columns
        assert "latitude" in df.columns
        assert "longitude" in df.columns
        assert "state" in df.columns
        assert "is_active" in df.columns

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_empty_stations_list(self, MockClient, env_dataops_enabled):
        adapter = DataOpsAdapter(mode="api")
        df = adapter._stations_to_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_station_state_column_name(self, MockClient, env_dataops_enabled):
        """Adapter maps state_code to 'state' column in DataFrame."""
        adapter = DataOpsAdapter(mode="api")
        station = Station.from_dict(SAMPLE_STATION_API_RESPONSE)
        df = adapter._stations_to_dataframe([station])
        assert df.iloc[0]["state"] == "WA"


# ==========================================================================
# Discharge DataFrame Conversion Tests
# ==========================================================================

class TestObservationsToDataFrame:
    """Test _observations_to_dataframe() conversion."""

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_converts_observations_to_df(self, MockClient, env_dataops_enabled):
        adapter = DataOpsAdapter(mode="api")

        observations = [
            DischargeObservation.from_dict(r)
            for r in SAMPLE_DISCHARGE_RESPONSE["results"]
        ]
        df = adapter._observations_to_dataframe(observations)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert "date" in df.columns
        assert "discharge" in df.columns
        assert "station_number" in df.columns
        assert "unit" in df.columns
        assert "quality" in df.columns

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_discharge_values_numeric(self, MockClient, env_dataops_enabled):
        adapter = DataOpsAdapter(mode="api")

        observations = [
            DischargeObservation.from_dict(r)
            for r in SAMPLE_DISCHARGE_RESPONSE["results"]
        ]
        df = adapter._observations_to_dataframe(observations)
        assert df["discharge"].dtype in ("float64", "float32")
        assert df.iloc[0]["discharge"] == pytest.approx(55.3)

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_dates_sorted_ascending(self, MockClient, env_dataops_enabled):
        adapter = DataOpsAdapter(mode="api")

        observations = [
            DischargeObservation.from_dict(r)
            for r in SAMPLE_DISCHARGE_RESPONSE["results"]
        ]
        df = adapter._observations_to_dataframe(observations)
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_empty_observations(self, MockClient, env_dataops_enabled):
        adapter = DataOpsAdapter(mode="api")
        df = adapter._observations_to_dataframe([])
        assert isinstance(df, pd.DataFrame)
        assert "date" in df.columns
        assert df.empty


# ==========================================================================
# get_stations() Integration Tests
# ==========================================================================

class TestAdapterGetStations:
    """Test adapter get_stations() with mocked client."""

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_api_mode_fetches_from_client(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")

        # Setup mock client response
        mock_paginated = PaginatedResponse.from_dict(
            SAMPLE_STATION_LIST_RESPONSE, result_class=Station
        )
        adapter.api_client.get_stations.return_value = mock_paginated

        # Setup cache miss
        adapter.cache.get_stations.return_value = None

        df = adapter.get_stations(state="WA")
        assert len(df) == 2
        assert df.iloc[0]["station_number"] == "12108500"

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_cache_hit_skips_api(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")

        cached_df = pd.DataFrame([{
            "station_number": "CACHED01",
            "name": "From Cache",
            "state": "WA",
        }])
        adapter.cache.get_stations.return_value = cached_df

        df = adapter.get_stations(state="WA")
        assert df.iloc[0]["station_number"] == "CACHED01"
        adapter.api_client.get_stations.assert_not_called()

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_api_failure_falls_back_to_cache(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")

        # Cache miss on first check
        adapter.cache.get_stations.side_effect = [
            None,  # Initial cache check
            pd.DataFrame([{"station_number": "FALLBACK", "name": "Fallback"}]),  # Fallback check
        ]
        adapter.api_client.get_stations.side_effect = Exception("API down")

        df = adapter.get_stations(state="WA")
        assert df.iloc[0]["station_number"] == "FALLBACK"


# ==========================================================================
# get_discharge_data() Tests
# ==========================================================================

class TestAdapterGetDischargeData:
    """Test adapter get_discharge_data() with mocked client."""

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_fetches_discharge_from_api(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")

        observations = [
            DischargeObservation.from_dict(r)
            for r in SAMPLE_DISCHARGE_RESPONSE["results"]
        ]
        adapter.api_client.get_station_data.return_value = observations
        adapter.cache.get_discharge_data.return_value = None

        df = adapter.get_discharge_data("12108500", "2026-01-01", "2026-01-31")
        assert len(df) == 3
        assert "date" in df.columns
        assert "discharge" in df.columns

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_updates_cache_after_fetch(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")

        observations = [
            DischargeObservation.from_dict(r)
            for r in SAMPLE_DISCHARGE_RESPONSE["results"]
        ]
        adapter.api_client.get_station_data.return_value = observations
        adapter.cache.get_discharge_data.return_value = None

        adapter.get_discharge_data("12108500", "2026-01-01", "2026-01-31")
        adapter.cache.set_discharge_data.assert_called_once()


# ==========================================================================
# Cache Manager Tests
# ==========================================================================

class TestCacheManager:
    """Test the SQLite-backed cache manager."""

    def test_init_creates_tables(self, temp_cache_db):
        cache = CacheManager(db_path=temp_cache_db)
        stats = cache.get_stats()
        assert "stations_entries" in stats or isinstance(stats, dict)

    def test_set_and_get_stations(self, temp_cache_db):
        cache = CacheManager(db_path=temp_cache_db)
        df = pd.DataFrame([
            {"station_number": "TEST01", "name": "Test", "state": "WA"},
        ])
        cache.set_stations(df, state="WA", agency="USGS")

        result = cache.get_stations(state="WA", agency="USGS")
        assert result is not None
        assert not result.empty
        assert result.iloc[0]["station_number"] == "TEST01"

    def test_cache_miss_returns_none(self, temp_cache_db):
        cache = CacheManager(db_path=temp_cache_db)
        result = cache.get_stations(state="XX", agency="USGS")
        assert result is None

    def test_set_and_get_discharge(self, temp_cache_db):
        cache = CacheManager(db_path=temp_cache_db)
        df = pd.DataFrame([
            {
                "date": pd.Timestamp("2026-01-01"),
                "station_number": "TEST01",
                "discharge": 100.0,
                "unit": "cfs",
                "quality": "A",
            },
        ])
        cache.set_discharge_data(df, "TEST01", "2026-01-01", "2026-01-31", "daily_mean")
        result = cache.get_discharge_data("TEST01", "2026-01-01", "2026-01-31", "daily_mean")
        assert result is not None
        assert not result.empty

    def test_clear_cache(self, temp_cache_db):
        cache = CacheManager(db_path=temp_cache_db)
        df = pd.DataFrame([{"station_number": "X", "name": "X", "state": "X"}])
        cache.set_stations(df, state="X", agency="X")
        cache.clear_cache()
        result = cache.get_stations(state="X", agency="X")
        assert result is None


# ==========================================================================
# Adapter Status Tests
# ==========================================================================

class TestAdapterStatus:
    """Test adapter status reporting."""

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_get_status_structure(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")
        adapter.api_client.get_stations.return_value = PaginatedResponse(
            count=1, next=None, previous=None, results=[]
        )

        status = adapter.get_status()
        assert "mode" in status
        assert "api_enabled" in status
        assert "cache_enabled" in status
        assert "api_reachable" in status
        assert status["mode"] == "hybrid"

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_test_connection_success(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")
        adapter.api_client.get_stations.return_value = PaginatedResponse(
            count=1, next=None, previous=None, results=[]
        )

        assert adapter.test_connection() is True

    @patch("dataops_adapter.client_adapter.CacheManager")
    @patch("dataops_adapter.client_adapter.DataOpsClient")
    def test_test_connection_failure(self, MockClient, MockCache, env_hybrid):
        adapter = DataOpsAdapter(mode="hybrid")
        adapter.api_client.get_stations.side_effect = Exception("Connection refused")

        assert adapter.test_connection() is False
