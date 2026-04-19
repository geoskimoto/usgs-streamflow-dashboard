"""Tests for the ResidCast forecast integration.

Covers:
  - API client: response parsing and variant filtering
  - DB client: SQL result grouping
  - Adapter: dispatch logic, config loading, DataFrame conversion
  - Data manager: get_resid_cast_forecasts, get_forecast_station_ids union
  - Viz manager: _add_resid_cast_overlay trace generation
  - Integration: live API (RUN_INTEGRATION_TESTS=1 only)
"""

import os
import json
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers / sample data
# ---------------------------------------------------------------------------

def _make_api_run(run_id: int, model_name: str, residual: str, general: bool):
    """Build a minimal /forecasts/ API response run dict."""
    issued = "2026-04-18T12:00:00Z"
    return {
        "station": "ANAW1",
        "run_id": run_id,
        "run_status": "complete",
        "forecasts": [
            {
                "model_name": model_name,
                "residual_type": residual,
                "is_general": general,
                "artifact_id": 1,
                "artifact_hash": "abc123",
                "issued_at": issued,
                "predictions": [
                    {"lead_day": d, "lead_date": f"2026-04-{18+d:02d}", "nwrfc_value_cfs": 100.0, "corrected_value_cfs": 95.0 + d}
                    for d in range(6)
                ],
            }
        ],
    }


SAMPLE_API_RESPONSE = [
    _make_api_run(10, "xgboost", "raw", False),
    _make_api_run(9,  "xgboost", "raw", False),
]

STATION_CONFIG = {
    "13334300": {
        "nwrfc_id": "ANAW1",
        "models": ["xgboost/raw", "muthre/standalone", "lstm/raw/general"],
    }
}


# ---------------------------------------------------------------------------
# API client tests
# ---------------------------------------------------------------------------

class TestResidCastApiClient:
    def _make_client(self, mock_resp_json):
        from resid_cast.resid_cast_api_client import ResidCastApiClient
        client = ResidCastApiClient(base_url="https://example.com", token="tok")
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_resp_json
        mock_resp.raise_for_status.return_value = None
        client._session.get = MagicMock(return_value=mock_resp)
        return client

    def test_returns_matching_variant(self):
        client = self._make_client(SAMPLE_API_RESPONSE)
        results = client.get_forecasts("ANAW1", allowed_variants=["xgboost/raw"], num_runs=5)
        assert len(results) == 2  # two runs
        assert all(r["model_key"] == "xgboost/raw" for r in results)
        assert results[0]["model_label"] == "XGBoost"

    def test_filters_out_unallowed_variant(self):
        client = self._make_client(SAMPLE_API_RESPONSE)
        results = client.get_forecasts("ANAW1", allowed_variants=["muthre/standalone"])
        assert results == []

    def test_data_rows_contain_discharge(self):
        client = self._make_client(SAMPLE_API_RESPONSE)
        results = client.get_forecasts("ANAW1", allowed_variants=["xgboost/raw"])
        assert len(results[0]["data"]) == 6
        assert results[0]["data"][0]["discharge_cfs"] == 95.0

    def test_run_date_derived_from_issued_at(self):
        client = self._make_client(SAMPLE_API_RESPONSE)
        results = client.get_forecasts("ANAW1", allowed_variants=["xgboost/raw"])
        assert results[0]["run_date"] == "2026-04-18"

    def test_source_tag_is_resid_cast(self):
        client = self._make_client(SAMPLE_API_RESPONSE)
        results = client.get_forecasts("ANAW1", allowed_variants=["xgboost/raw"])
        assert all(r["source"] == "resid_cast" for r in results)

    def test_network_error_returns_empty(self):
        from resid_cast.resid_cast_api_client import ResidCastApiClient
        import requests
        client = ResidCastApiClient(base_url="https://example.com", token="tok")
        client._session.get = MagicMock(side_effect=requests.RequestException("timeout"))
        results = client.get_forecasts("ANAW1", allowed_variants=["xgboost/raw"])
        assert results == []

    def test_general_model_key(self):
        from resid_cast.resid_cast_api_client import _variant_key
        assert _variant_key("lstm", "raw", True) == "lstm/raw/general"
        assert _variant_key("xgboost", "raw", False) == "xgboost/raw"

    def test_model_label_lookup(self):
        from resid_cast.resid_cast_api_client import model_label
        assert model_label("xgboost/raw") == "XGBoost"
        assert model_label("muthre/standalone") == "MUTHRE"
        assert model_label("lstm/raw/general") == "LSTM (general)"
        assert model_label("unknown/variant") == "unknown/variant"


# ---------------------------------------------------------------------------
# DB client tests (mocked SQLAlchemy)
# ---------------------------------------------------------------------------

class TestResidCastDbClient:
    def _make_row(self, run_id, model_name, residual, is_general, lead_day, corrected):
        """Build a mock SQLAlchemy result row."""
        row = MagicMock()
        row.run_id = run_id
        row.run_status = "complete"
        row.model_name = model_name
        row.residual_type = residual
        row.is_general = is_general
        row.issued_at = "2026-04-18T12:00:00"
        row.lead_date = f"2026-04-{18 + lead_day:02d}"
        row.corrected_value_cfs = corrected
        return row

    def _make_client(self, rows):
        with patch("resid_cast.resid_cast_db_client.create_engine"), \
             patch("resid_cast.resid_cast_db_client.sessionmaker") as mock_sm:
            mock_session = MagicMock()
            mock_session.execute.return_value.fetchall.return_value = rows
            mock_sm.return_value.return_value = mock_session
            from resid_cast.resid_cast_db_client import ResidCastDbClient
            client = ResidCastDbClient(db_url="postgresql://x:y@localhost/db")
            client._Session = mock_sm.return_value
            return client

    def test_groups_by_run_and_variant(self):
        rows = [
            self._make_row(10, "xgboost", "raw", False, d, 95.0 + d) for d in range(6)
        ]
        client = self._make_client(rows)
        results = client.get_forecasts("ANAW1", allowed_variants=["xgboost/raw"])
        assert len(results) == 1
        assert results[0]["model_key"] == "xgboost/raw"
        assert len(results[0]["data"]) == 6

    def test_filters_unallowed_variant(self):
        rows = [
            self._make_row(10, "xgboost", "raw", False, d, 95.0) for d in range(3)
        ]
        client = self._make_client(rows)
        results = client.get_forecasts("ANAW1", allowed_variants=["muthre/standalone"])
        assert results == []

    def test_db_error_returns_empty(self):
        with patch("resid_cast.resid_cast_db_client.create_engine"), \
             patch("resid_cast.resid_cast_db_client.sessionmaker") as mock_sm:
            mock_session = MagicMock()
            mock_session.execute.side_effect = Exception("connection refused")
            mock_sm.return_value.return_value = mock_session
            from resid_cast.resid_cast_db_client import ResidCastDbClient
            client = ResidCastDbClient(db_url="postgresql://x:y@localhost/db")
            client._Session = mock_sm.return_value
            results = client.get_forecasts("ANAW1", allowed_variants=["xgboost/raw"])
            assert results == []


# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------

class TestResidCastAdapter:
    def test_station_usgs_ids_loads_config(self):
        from resid_cast.resid_cast_adapter import ResidCastAdapter
        with patch("resid_cast.resid_cast_adapter._load_config", return_value=STATION_CONFIG), \
             patch("resid_cast.resid_cast_adapter.ResidCastAdapter._build_client", return_value=None):
            adapter = ResidCastAdapter()
            ids = adapter.station_usgs_ids()
            assert "13334300" in ids
            assert len(ids) == 1

    def test_get_forecasts_returns_dataframes(self):
        raw = [
            {
                "run_date": "2026-04-18",
                "model_label": "XGBoost",
                "model_key": "xgboost/raw",
                "source": "resid_cast",
                "data": [
                    {"datetime": "2026-04-18", "discharge_cfs": 120.0},
                    {"datetime": "2026-04-19", "discharge_cfs": 115.0},
                ],
            }
        ]
        mock_client = MagicMock()
        mock_client.get_forecasts.return_value = raw

        from resid_cast.resid_cast_adapter import ResidCastAdapter
        with patch("resid_cast.resid_cast_adapter._load_config", return_value=STATION_CONFIG), \
             patch("resid_cast.resid_cast_adapter.ResidCastAdapter._build_client", return_value=mock_client):
            adapter = ResidCastAdapter()
            results = adapter.get_forecasts("13334300")
            assert len(results) == 1
            assert isinstance(results[0]["data"], pd.DataFrame)
            assert list(results[0]["data"].columns) == ["datetime", "discharge_cfs"]
            assert len(results[0]["data"]) == 2

    def test_get_forecasts_returns_empty_for_unknown_station(self):
        from resid_cast.resid_cast_adapter import ResidCastAdapter
        with patch("resid_cast.resid_cast_adapter._load_config", return_value=STATION_CONFIG), \
             patch("resid_cast.resid_cast_adapter.ResidCastAdapter._build_client", return_value=MagicMock()):
            adapter = ResidCastAdapter()
            results = adapter.get_forecasts("99999999")
            assert results == []

    def test_get_forecasts_returns_empty_when_client_is_none(self):
        from resid_cast.resid_cast_adapter import ResidCastAdapter
        with patch("resid_cast.resid_cast_adapter._load_config", return_value=STATION_CONFIG), \
             patch("resid_cast.resid_cast_adapter.ResidCastAdapter._build_client", return_value=None):
            adapter = ResidCastAdapter()
            results = adapter.get_forecasts("13334300")
            assert results == []

    def test_dispatches_to_api_client(self, monkeypatch):
        monkeypatch.setenv("RESID_CAST_USE_API", "true")
        monkeypatch.setenv("RESID_CAST_API_URL", "https://resid-cast.example.com")
        monkeypatch.setenv("RESID_CAST_API_TOKEN", "tok")
        from resid_cast.resid_cast_adapter import ResidCastAdapter
        with patch("resid_cast.resid_cast_adapter._load_config", return_value={}), \
             patch("resid_cast.resid_cast_api_client.ResidCastApiClient") as MockApi:
            MockApi.return_value = MagicMock()
            adapter = ResidCastAdapter()
            assert MockApi.called

    def test_dispatches_to_db_client(self, monkeypatch):
        monkeypatch.setenv("RESID_CAST_USE_API", "false")
        monkeypatch.setenv("RESID_CAST_DB_URL", "postgresql://x:y@localhost/db")
        from resid_cast.resid_cast_adapter import ResidCastAdapter
        with patch("resid_cast.resid_cast_adapter._load_config", return_value={}), \
             patch("resid_cast.resid_cast_db_client.ResidCastDbClient") as MockDb:
            MockDb.return_value = MagicMock()
            adapter = ResidCastAdapter()
            assert MockDb.called


# ---------------------------------------------------------------------------
# Data manager tests
# ---------------------------------------------------------------------------

class TestDataManagerResidCast:
    def _make_manager_with_resid_cast(self, resid_cast_adapter):
        """Build a USGSDataManager with a mocked ResidCast adapter."""
        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_get_adapter, \
             patch("usgs_dashboard.data.data_manager._USE_RESID_CAST", True), \
             patch("usgs_dashboard.data.data_manager.ResidCastAdapter", return_value=resid_cast_adapter):
            mock_get_adapter.return_value = MagicMock(
                mode="api", api_enabled=True, cache_enabled=False
            )
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm._resid_cast = resid_cast_adapter
            return dm

    def test_get_resid_cast_forecasts_delegates_to_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.get_forecasts.return_value = [{"run_date": "2026-04-18", "model_label": "XGBoost"}]
        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_ga:
            mock_ga.return_value = MagicMock(mode="api", api_enabled=True, cache_enabled=False)
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm._resid_cast = mock_adapter
            result = dm.get_resid_cast_forecasts("13334300")
            mock_adapter.get_forecasts.assert_called_once_with("13334300", num_runs=5)
            assert len(result) == 1

    def test_get_resid_cast_forecasts_returns_empty_when_disabled(self):
        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_ga:
            mock_ga.return_value = MagicMock(mode="api", api_enabled=True, cache_enabled=False)
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm._resid_cast = None
            result = dm.get_resid_cast_forecasts("13334300")
            assert result == []

    def test_forecast_station_ids_unions_nwrfc_and_resid_cast(self):
        mock_nwrfc_df = pd.DataFrame([{"station_number": "ANAW1"}])
        mock_crosswalk = {"ANAW1": "13334300"}
        mock_rc_adapter = MagicMock()
        mock_rc_adapter.station_usgs_ids.return_value = {"13334300", "12340000"}

        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_ga, \
             patch("builtins.open", create=True) as mock_open, \
             patch("json.load", return_value=mock_crosswalk):
            mock_adapter = MagicMock(mode="api", api_enabled=True, cache_enabled=False)
            mock_adapter.get_stations.return_value = mock_nwrfc_df
            mock_ga.return_value = mock_adapter

            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm._resid_cast = mock_rc_adapter
            dm._forecast_station_ids_cache = None

            ids = dm.get_forecast_station_ids()
            assert "13334300" in ids
            assert "12340000" in ids


# ---------------------------------------------------------------------------
# Viz manager tests
# ---------------------------------------------------------------------------

class TestVizManagerResidCastOverlay:
    def _make_resid_cast_data(self):
        dates = pd.to_datetime(["2026-04-18", "2026-04-19", "2026-04-20"])
        df = pd.DataFrame({"datetime": dates, "discharge_cfs": [100.0, 110.0, 105.0]})
        return [
            {"run_date": "2026-04-18", "model_label": "XGBoost", "model_key": "xgboost/raw",
             "source": "resid_cast", "data": df},
            {"run_date": "2026-04-17", "model_label": "XGBoost", "model_key": "xgboost/raw",
             "source": "resid_cast", "data": df.copy()},
            {"run_date": "2026-04-18", "model_label": "MUTHRE", "model_key": "muthre/standalone",
             "source": "resid_cast", "data": df.copy()},
        ]

    def test_adds_one_trace_per_entry(self):
        import plotly.graph_objects as go
        from usgs_dashboard.components.viz_manager import VisualizationManager
        vm = VisualizationManager()
        fig = go.Figure()
        data = self._make_resid_cast_data()
        fig = vm._add_resid_cast_overlay(fig, data)
        assert len(fig.data) == 3

    def test_first_run_per_model_is_visible(self):
        import plotly.graph_objects as go
        from usgs_dashboard.components.viz_manager import VisualizationManager
        vm = VisualizationManager()
        fig = go.Figure()
        data = self._make_resid_cast_data()
        fig = vm._add_resid_cast_overlay(fig, data)
        # traces 0 and 2 are newest runs of XGBoost and MUTHRE — should be visible
        assert fig.data[0].visible is True
        assert fig.data[2].visible is True

    def test_older_run_is_legendonly(self):
        import plotly.graph_objects as go
        from usgs_dashboard.components.viz_manager import VisualizationManager
        vm = VisualizationManager()
        fig = go.Figure()
        data = self._make_resid_cast_data()
        fig = vm._add_resid_cast_overlay(fig, data)
        assert fig.data[1].visible == "legendonly"

    def test_traces_use_dashed_lines(self):
        import plotly.graph_objects as go
        from usgs_dashboard.components.viz_manager import VisualizationManager
        vm = VisualizationManager()
        fig = go.Figure()
        data = self._make_resid_cast_data()
        fig = vm._add_resid_cast_overlay(fig, data)
        for trace in fig.data:
            assert trace.line.dash == "dash"

    def test_empty_data_returns_unchanged_figure(self):
        import plotly.graph_objects as go
        from usgs_dashboard.components.viz_manager import VisualizationManager
        vm = VisualizationManager()
        fig = go.Figure()
        fig = vm._add_resid_cast_overlay(fig, [])
        assert len(fig.data) == 0

    def test_trace_names_include_model_and_date(self):
        import plotly.graph_objects as go
        from usgs_dashboard.components.viz_manager import VisualizationManager
        vm = VisualizationManager()
        fig = go.Figure()
        data = self._make_resid_cast_data()[:1]
        fig = vm._add_resid_cast_overlay(fig, data)
        assert "XGBoost" in fig.data[0].name
        assert "Apr" in fig.data[0].name


# ---------------------------------------------------------------------------
# Integration test (live API — guarded by RUN_INTEGRATION_TESTS=1)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to run live API tests",
)
class TestResidCastIntegration:
    def test_api_client_fetches_station_forecasts(self):
        from resid_cast.resid_cast_api_client import ResidCastApiClient
        api_url = os.environ["RESID_CAST_API_URL"]
        token = os.environ["RESID_CAST_API_TOKEN"]
        client = ResidCastApiClient(base_url=api_url, token=token)
        results = client.get_forecasts(
            "ANAW1", allowed_variants=["xgboost/raw", "muthre/standalone", "lstm/raw/general"]
        )
        # System may have 0 runs; just check it doesn't raise
        assert isinstance(results, list)
        for r in results:
            assert "run_date" in r
            assert "model_key" in r
            assert "data" in r
