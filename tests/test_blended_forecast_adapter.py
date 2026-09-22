"""Tests for BlendedForecastAdapter and its data_manager delegation wrapper."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

import requests


# ---------------------------------------------------------------------------
# BlendedForecastAdapter tests
# ---------------------------------------------------------------------------

def test_adapter_returns_empty_when_api_url_unset(monkeypatch):
    monkeypatch.delenv("BLENDED_FORECAST_API_URL", raising=False)
    from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
    adapter = BlendedForecastAdapter()
    result = adapter.get_forecasts("14178000")
    assert result == []


def test_adapter_returns_empty_for_station_not_in_config(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
    with patch.object(BlendedForecastAdapter, "_load_config", return_value={}):
        adapter = BlendedForecastAdapter()
        result = adapter.get_forecasts("99999999")
    assert result == []


def test_adapter_returns_empty_when_ealstm_unavailable(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
    with patch.object(
        BlendedForecastAdapter,
        "_load_config",
        return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": False}},
    ):
        adapter = BlendedForecastAdapter()
        result = adapter.get_forecasts("14178000")
    assert result == []


def test_adapter_get_forecasts_happy_path_lead_day_zero(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    monkeypatch.setenv("BLENDED_FORECAST_API_TOKEN", "test-token")

    valid_dates = [d.strftime("%Y-%m-%d") for d in pd.date_range("2026-06-01", periods=8, freq="D")]
    mock_response = [
        {
            "valid_date": valid_dates[i],
            "lead_day": i,
            "value_cfs": 1000.0 + i * 10,
            "source": "streamflowops_nwrfc",
            "model_artifact": None,
        }
        for i in range(8)
    ]

    with patch("resid_cast.blended_forecast_adapter.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
        with patch.object(
            BlendedForecastAdapter,
            "_load_config",
            return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True}},
        ):
            adapter = BlendedForecastAdapter()
            result = adapter.get_forecasts("14178000", num_runs=5)

    assert len(result) == 1
    entry = result[0]
    assert entry["model_key"] == "blended"
    assert entry["source"] == "model_blender"
    assert entry["model_label"] == "Blended"
    assert isinstance(entry["data"], pd.DataFrame)
    assert "discharge_cfs" in entry["data"].columns
    assert len(entry["data"]) == 8
    # lowest lead_day is 0, so run_date == that row's valid_date exactly
    assert entry["run_date"] == "2026-06-01"


def test_adapter_get_forecasts_run_date_backcomputed_when_lead_day_not_zero(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    monkeypatch.setenv("BLENDED_FORECAST_API_TOKEN", "test-token")

    # Simulate lead_day 0 and 1 skipped by the blend job; rows also
    # provided out of lead_day order to prove the adapter sorts them
    # itself rather than trusting response order.
    mock_response = [
        {"valid_date": "2026-06-05", "lead_day": 4, "value_cfs": 1300.0, "source": "streamflowops_nwrfc", "model_artifact": None},
        {"valid_date": "2026-06-03", "lead_day": 2, "value_cfs": 1100.0, "source": "streamflowops_nwrfc", "model_artifact": None},
        {"valid_date": "2026-06-04", "lead_day": 3, "value_cfs": 1200.0, "source": "streamflowops_nwrfc", "model_artifact": None},
    ]

    with patch("resid_cast.blended_forecast_adapter.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
        with patch.object(
            BlendedForecastAdapter,
            "_load_config",
            return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True}},
        ):
            adapter = BlendedForecastAdapter()
            result = adapter.get_forecasts("14178000")

    assert len(result) == 1
    entry = result[0]
    assert len(entry["data"]) == 3
    # lowest lead_day present is 2, valid_date 2026-06-03 -> run_date = 2026-06-01
    assert entry["run_date"] == "2026-06-01"


def test_adapter_returns_empty_for_empty_response_list(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    monkeypatch.setenv("BLENDED_FORECAST_API_TOKEN", "test-token")

    with patch("resid_cast.blended_forecast_adapter.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = []
        mock_get.return_value = mock_resp

        from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
        with patch.object(
            BlendedForecastAdapter,
            "_load_config",
            return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True}},
        ):
            adapter = BlendedForecastAdapter()
            result = adapter.get_forecasts("14178000")

    assert result == []


def test_adapter_returns_empty_on_404(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    monkeypatch.setenv("BLENDED_FORECAST_API_TOKEN", "test-token")

    with patch("resid_cast.blended_forecast_adapter.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_get.return_value = mock_resp

        from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
        with patch.object(
            BlendedForecastAdapter,
            "_load_config",
            return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True}},
        ):
            adapter = BlendedForecastAdapter()
            result = adapter.get_forecasts("14178000")

    assert result == []


def test_adapter_returns_empty_on_request_exception(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    monkeypatch.setenv("BLENDED_FORECAST_API_TOKEN", "test-token")

    with patch("resid_cast.blended_forecast_adapter.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.ConnectionError("boom")

        from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
        with patch.object(
            BlendedForecastAdapter,
            "_load_config",
            return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True}},
        ):
            adapter = BlendedForecastAdapter()
            result = adapter.get_forecasts("14178000")

    assert result == []


def test_adapter_sends_bearer_auth_header(monkeypatch):
    monkeypatch.setenv("BLENDED_FORECAST_API_URL", "http://localhost:8011")
    monkeypatch.setenv("BLENDED_FORECAST_API_TOKEN", "super-secret-token")

    mock_response = [
        {"valid_date": "2026-06-01", "lead_day": 0, "value_cfs": 1000.0, "source": "streamflowops_nwrfc", "model_artifact": None},
    ]

    with patch("resid_cast.blended_forecast_adapter.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
        with patch.object(
            BlendedForecastAdapter,
            "_load_config",
            return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True}},
        ):
            adapter = BlendedForecastAdapter()
            adapter.get_forecasts("14178000")

    _, call_kwargs = mock_get.call_args
    assert call_kwargs["headers"] == {"Authorization": "Bearer super-secret-token"}
    assert call_kwargs["timeout"] == 10


def test_station_usgs_ids_filters_on_ealstm_available():
    from resid_cast.blended_forecast_adapter import BlendedForecastAdapter
    with patch.object(
        BlendedForecastAdapter,
        "_load_config",
        return_value={
            "14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True},
            "14179000": {"nwrfc_id": "MFKI2", "ealstm_available": False},
        },
    ):
        adapter = BlendedForecastAdapter()
        ids = adapter.station_usgs_ids()
    assert ids == {"14178000"}


# ---------------------------------------------------------------------------
# Data manager delegation wrapper tests
# ---------------------------------------------------------------------------

class TestDataManagerBlended:
    def test_get_blended_forecasts_delegates_to_adapter(self):
        mock_adapter = MagicMock()
        mock_adapter.get_forecasts.return_value = [
            {"run_date": "2026-09-22", "model_label": "Blended"}
        ]
        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_ga:
            mock_ga.return_value = MagicMock(mode="api", api_enabled=True, cache_enabled=False)
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm._blended_forecast = mock_adapter
            result = dm.get_blended_forecasts("13334300")
            mock_adapter.get_forecasts.assert_called_once_with("13334300", num_runs=5)
            assert len(result) == 1

    def test_get_blended_forecasts_returns_empty_when_disabled(self):
        with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_ga:
            mock_ga.return_value = MagicMock(mode="api", api_enabled=True, cache_enabled=False)
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager()
            dm._blended_forecast = None
            result = dm.get_blended_forecasts("13334300")
            assert result == []
