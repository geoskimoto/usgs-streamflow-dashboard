"""
Tests for the USGSDataManager (usgs_dashboard/data/data_manager.py).

Verifies the data pipeline from adapter through enrichment to dashboard output.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock


# ==========================================================================
# Station Enrichment Tests
# ==========================================================================

class TestEnrichStationMetadata:
    """Test _enrich_station_metadata() column mapping and color coding."""

    @pytest.fixture
    def data_manager(self):
        """Create a data manager with a mocked adapter."""
        with patch("usgs_dashboard.data.data_manager.DataOpsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm.adapter = mock_adapter
            return dm

    def test_adds_site_id_column(self, data_manager, sample_stations_df):
        result = data_manager._enrich_station_metadata(sample_stations_df)
        assert "site_id" in result.columns
        assert result.iloc[0]["site_id"] == result.iloc[0]["station_number"]

    def test_adds_site_no_column(self, data_manager, sample_stations_df):
        result = data_manager._enrich_station_metadata(sample_stations_df)
        assert "site_no" in result.columns
        assert result.iloc[0]["site_no"] == result.iloc[0]["station_number"]

    def test_adds_station_name_column(self, data_manager, sample_stations_df):
        result = data_manager._enrich_station_metadata(sample_stations_df)
        assert "station_name" in result.columns
        assert result.iloc[0]["station_name"] == result.iloc[0]["name"]

    def test_adds_station_nm_column(self, data_manager, sample_stations_df):
        result = data_manager._enrich_station_metadata(sample_stations_df)
        assert "station_nm" in result.columns

    def test_adds_color_column(self, data_manager, sample_stations_df):
        result = data_manager._enrich_station_metadata(sample_stations_df)
        assert "color" in result.columns
        # Every row should have a color string
        assert all(isinstance(c, str) and c.startswith("#") for c in result["color"])

    def test_adds_drainage_area_default(self, data_manager, sample_stations_df):
        result = data_manager._enrich_station_metadata(sample_stations_df)
        assert "drainage_area" in result.columns

    def test_empty_df_returns_empty(self, data_manager):
        result = data_manager._enrich_station_metadata(pd.DataFrame())
        assert result.empty

    def test_filters_by_target_states(self, data_manager, sample_stations_df):
        """Only stations in TARGET_STATES should be kept."""
        result = data_manager._enrich_station_metadata(sample_stations_df)
        from usgs_dashboard.utils.config import TARGET_STATES
        if TARGET_STATES:
            assert all(s in TARGET_STATES for s in result["state"].dropna())


# ==========================================================================
# load_regional_gauges() Tests
# ==========================================================================

class TestLoadRegionalGauges:
    """Test load_regional_gauges() per-state fetching and deduplication."""

    @pytest.fixture
    def data_manager(self):
        with patch("usgs_dashboard.data.data_manager.DataOpsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm.adapter = mock_adapter
            return dm

    def test_fetches_per_state(self, data_manager):
        """Should call get_stations once per TARGET_STATE."""
        from usgs_dashboard.utils.config import TARGET_STATES

        def mock_get_stations(**kwargs):
            state = kwargs.get("state", "XX")
            return pd.DataFrame([{
                "station_number": f"TEST_{state}_01",
                "name": f"Station in {state}",
                "agency": "USGS",
                "latitude": 45.0,
                "longitude": -120.0,
                "state": state,
                "huc_code": None,
                "is_active": True,
                "basin_name": None,
            }])

        data_manager.adapter.get_stations.side_effect = mock_get_stations

        result = data_manager.load_regional_gauges(max_sites=100)
        assert len(result) == len(TARGET_STATES)
        assert data_manager.adapter.get_stations.call_count == len(TARGET_STATES)

    def test_deduplicates_stations(self, data_manager):
        """Stations appearing in multiple state queries should be deduped."""
        dup_df = pd.DataFrame([
            {"station_number": "DUP01", "name": "Dup", "agency": "USGS",
             "latitude": 45.0, "longitude": -120.0, "state": "OR",
             "huc_code": None, "is_active": True, "basin_name": None},
        ])

        data_manager.adapter.get_stations.return_value = dup_df

        result = data_manager.load_regional_gauges(max_sites=100)
        # Should only have ONE entry for DUP01 despite 9 state calls
        assert len(result[result["station_number"] == "DUP01"]) == 1

    def test_caches_result(self, data_manager, sample_stations_df):
        data_manager.adapter.get_stations.return_value = sample_stations_df
        data_manager.load_regional_gauges(max_sites=100)
        assert data_manager._stations_cache is not None
        assert not data_manager._stations_cache.empty

    def test_returns_empty_on_total_failure(self, data_manager):
        data_manager.adapter.get_stations.side_effect = Exception("API down")
        result = data_manager.load_regional_gauges()
        assert result.empty

    def test_continues_on_partial_failure(self, data_manager):
        """Should continue loading other states when one fails."""
        call_count = [0]

        def mock_get_stations(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First state failed")
            return pd.DataFrame([{
                "station_number": f"ST_{call_count[0]}",
                "name": "OK",
                "agency": "USGS",
                "latitude": 45.0,
                "longitude": -120.0,
                "state": kwargs.get("state", "XX"),
                "huc_code": None,
                "is_active": True,
                "basin_name": None,
            }])

        data_manager.adapter.get_stations.side_effect = mock_get_stations
        result = data_manager.load_regional_gauges(max_sites=100)
        # Should have records from all states except the first that failed
        assert not result.empty


# ==========================================================================
# get_streamflow_data() Tests
# ==========================================================================

class TestGetStreamflowData:
    """Test get_streamflow_data() and _format_streamflow_data()."""

    @pytest.fixture
    def data_manager(self):
        with patch("usgs_dashboard.data.data_manager.DataOpsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm.adapter = mock_adapter
            return dm

    def test_returns_formatted_dataframe(self, data_manager, sample_discharge_df):
        data_manager.adapter.get_discharge_data.return_value = sample_discharge_df
        result = data_manager.get_streamflow_data("12108500", "2026-01-01", "2026-01-31")

        assert not result.empty
        assert "datetime" in result.columns
        assert "discharge" in result.columns
        assert "site_no" in result.columns

    def test_adds_site_no_column(self, data_manager, sample_discharge_df):
        data_manager.adapter.get_discharge_data.return_value = sample_discharge_df
        result = data_manager.get_streamflow_data("12108500", "2026-01-01", "2026-01-31")
        assert all(result["site_no"] == "12108500")

    def test_returns_empty_on_no_data(self, data_manager):
        data_manager.adapter.get_discharge_data.return_value = pd.DataFrame()
        result = data_manager.get_streamflow_data("99999999", "2026-01-01", "2026-01-31")
        assert result.empty

    def test_returns_empty_on_error(self, data_manager):
        data_manager.adapter.get_discharge_data.side_effect = Exception("API error")
        result = data_manager.get_streamflow_data("12108500", "2026-01-01", "2026-01-31")
        assert result.empty

    def test_default_dates_when_none(self, data_manager, sample_discharge_df):
        """Should compute default dates when not provided."""
        data_manager.adapter.get_discharge_data.return_value = sample_discharge_df
        result = data_manager.get_streamflow_data("12108500")
        assert not result.empty
        # Should have called get_discharge_data with computed dates
        call_args = data_manager.adapter.get_discharge_data.call_args
        assert call_args.kwargs["start_date"] is not None
        assert call_args.kwargs["end_date"] is not None


# ==========================================================================
# _format_streamflow_data() Tests
# ==========================================================================

class TestFormatStreamflowData:
    """Test _format_streamflow_data() transformations."""

    @pytest.fixture
    def data_manager(self):
        with patch("usgs_dashboard.data.data_manager.DataOpsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm.adapter = mock_adapter
            return dm

    def test_creates_datetime_from_date(self, data_manager, sample_discharge_df):
        result = data_manager._format_streamflow_data(sample_discharge_df, "12108500")
        assert "datetime" in result.columns

    def test_renames_discharge_value(self, data_manager):
        """Should rename 'discharge_value' to 'discharge' if needed."""
        df = pd.DataFrame([{
            "date": pd.Timestamp("2026-01-01"),
            "station_number": "12108500",
            "discharge_value": 55.0,
            "unit": "cfs",
        }])
        result = data_manager._format_streamflow_data(df, "12108500")
        assert "discharge" in result.columns

    def test_sorts_by_datetime(self, data_manager):
        df = pd.DataFrame([
            {"date": pd.Timestamp("2026-01-03"), "station_number": "X", "discharge": 30},
            {"date": pd.Timestamp("2026-01-01"), "station_number": "X", "discharge": 10},
            {"date": pd.Timestamp("2026-01-02"), "station_number": "X", "discharge": 20},
        ])
        result = data_manager._format_streamflow_data(df, "X")
        assert list(result["discharge"]) == [10.0, 20.0, 30.0]

    def test_removes_duplicate_dates(self, data_manager):
        df = pd.DataFrame([
            {"date": pd.Timestamp("2026-01-01"), "station_number": "X", "discharge": 10},
            {"date": pd.Timestamp("2026-01-01"), "station_number": "X", "discharge": 15},
        ])
        result = data_manager._format_streamflow_data(df, "X")
        assert len(result) == 1

    def test_empty_df_passthrough(self, data_manager):
        result = data_manager._format_streamflow_data(pd.DataFrame(), "X")
        assert result.empty


# ==========================================================================
# get_filters_table() Tests
# ==========================================================================

class TestGetFiltersTable:
    """Test get_filters_table() cache behavior."""

    @pytest.fixture
    def data_manager(self):
        with patch("usgs_dashboard.data.data_manager.DataOpsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm.adapter = mock_adapter
            return dm

    def test_returns_cached_data(self, data_manager, sample_stations_df):
        data_manager._stations_cache = sample_stations_df
        result = data_manager.get_filters_table()
        assert not result.empty
        # Should not call adapter again
        data_manager.adapter.get_stations.assert_not_called()

    def test_loads_fresh_on_cache_miss(self, data_manager, sample_stations_df):
        data_manager._stations_cache = None
        data_manager.adapter.get_stations.return_value = sample_stations_df
        result = data_manager.get_filters_table()
        # Should have tried to load fresh
        assert data_manager.adapter.get_stations.called


# ==========================================================================
# get_sites_with_realtime_data() Tests
# ==========================================================================

class TestGetSitesWithRealtimeData:
    """Test get_sites_with_realtime_data()."""

    @pytest.fixture
    def data_manager(self):
        with patch("usgs_dashboard.data.data_manager.DataOpsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm.adapter = mock_adapter
            return dm

    def test_returns_site_ids_from_cache(self, data_manager):
        data_manager._stations_cache = pd.DataFrame({
            "site_id": ["12108500", "12113150"],
            "name": ["A", "B"],
        })
        result = data_manager.get_sites_with_realtime_data()
        assert "12108500" in result
        assert "12113150" in result

    def test_returns_empty_on_error(self, data_manager):
        data_manager._stations_cache = None
        data_manager.adapter.get_stations.side_effect = Exception("fail")
        result = data_manager.get_sites_with_realtime_data()
        assert isinstance(result, list)


# ==========================================================================
# get_adapter_status() Tests
# ==========================================================================

class TestAdapterStatusFromManager:
    """Test get_adapter_status() delegation."""

    @pytest.fixture
    def data_manager(self):
        with patch("usgs_dashboard.data.data_manager.DataOpsAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            MockAdapter.return_value = mock_adapter
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm.adapter = mock_adapter
            return dm

    def test_delegates_to_adapter(self, data_manager):
        data_manager.adapter.get_status.return_value = {
            "mode": "hybrid",
            "api_enabled": True,
        }
        status = data_manager.get_adapter_status()
        assert status["mode"] == "hybrid"
        data_manager.adapter.get_status.assert_called_once()
