"""Tests for PrecipRunoffAdapter."""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock


def test_adapter_returns_empty_when_api_url_unset(monkeypatch):
    monkeypatch.delenv("RESID_CAST_API_URL", raising=False)
    from resid_cast.precip_runoff_adapter import PrecipRunoffAdapter
    adapter = PrecipRunoffAdapter()
    result = adapter.get_forecasts("14178000")
    assert result == []


def test_adapter_returns_empty_for_unavailable_station():
    from resid_cast.precip_runoff_adapter import PrecipRunoffAdapter
    adapter = PrecipRunoffAdapter()
    result = adapter.get_forecasts("99999999")
    assert result == []


def test_adapter_get_forecasts_returns_correct_shape(monkeypatch):
    monkeypatch.setenv("RESID_CAST_API_URL", "http://localhost:8001")
    monkeypatch.setenv("RESID_CAST_API_TOKEN", "test-token")

    lead_dates = [d.strftime("%Y-%m-%d") for d in pd.date_range("2026-05-30", periods=14, freq="D")]
    mock_response = [
        {
            "issued_at": "2026-05-29T15:00:00",
            "model_name": "ealstm",
            "predictions": [
                {"lead_date": lead_dates[i], "predicted_flow_cfs": 1000.0 + i * 10}
                for i in range(14)
            ],
        }
    ]

    with patch("resid_cast.precip_runoff_adapter.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        from resid_cast.precip_runoff_adapter import PrecipRunoffAdapter
        with patch.object(PrecipRunoffAdapter, "_load_config",
                          return_value={"14178000": {"nwrfc_id": "MFKI1", "ealstm_available": True}}):
            adapter = PrecipRunoffAdapter()
            result = adapter.get_forecasts("14178000", num_runs=1)

    assert len(result) == 1
    assert result[0]["model_key"] == "ealstm/precip_runoff"
    assert result[0]["source"] == "precip_runoff"
    assert isinstance(result[0]["data"], pd.DataFrame)
    assert "discharge_cfs" in result[0]["data"].columns
    assert len(result[0]["data"]) == 14
