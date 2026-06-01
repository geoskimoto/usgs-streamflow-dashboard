"""Tests for NWRFC web forecast integration in the dashboard."""

from unittest.mock import MagicMock
import pandas as pd


# ── dataops_client tests ──────────────────────────────────────────────────────

def test_get_nwrfc_web_forecasts_calls_api_with_source_filter():
    """get_nwrfc_web_forecasts passes source=nwrfc_web to the API."""
    from dataops_client.client import DataOpsClient

    client = DataOpsClient.__new__(DataOpsClient)
    client._request = MagicMock(return_value={
        'results': [
            {
                'id': 1,
                'run_date': '2026-06-01T12:00:00Z',
                'source': 'nwrfc_web',
                'is_forecast': True,
                'data': [
                    {'date': '2026-06-02T00:00:00Z', 'value': 14000.0},
                ],
            }
        ],
        'next': None,
    })

    result = client.get_nwrfc_web_forecasts('REVQ2', num_days=3)
    # The list-fetch is the FIRST call; call_args returns the last call (detail fetch)
    first_call = client._request.call_args_list[0]
    assert 'nwrfc_web' in str(first_call)
    assert isinstance(result, list)


# ── client_adapter tests ──────────────────────────────────────────────────────

def test_get_nwrfc_lid_usgs_path():
    """_get_nwrfc_lid finds US stations via USGS crosswalk."""
    from dataops_adapter.client_adapter import DataOpsAdapter

    adapter = DataOpsAdapter.__new__(DataOpsAdapter)
    adapter._usgs_to_nwrfc = {'14187500': 'WTLO3'}
    adapter._ec_to_nwrfc = {}

    assert adapter._get_nwrfc_lid('14187500') == 'WTLO3'


def test_get_nwrfc_lid_ec_path():
    """_get_nwrfc_lid falls back to EC crosswalk for Canadian stations."""
    from dataops_adapter.client_adapter import DataOpsAdapter

    adapter = DataOpsAdapter.__new__(DataOpsAdapter)
    adapter._usgs_to_nwrfc = {}
    adapter._ec_to_nwrfc = {'08NE006': 'REVQ2'}

    assert adapter._get_nwrfc_lid('08NE006') == 'REVQ2'


def test_get_nwrfc_lid_unknown_returns_none():
    from dataops_adapter.client_adapter import DataOpsAdapter

    adapter = DataOpsAdapter.__new__(DataOpsAdapter)
    adapter._usgs_to_nwrfc = {}
    adapter._ec_to_nwrfc = {}

    assert adapter._get_nwrfc_lid('UNKNOWN999') is None


def test_get_nwrfc_forecasts_falls_back_to_noaa_api():
    """When nwrfc_web returns empty, fall back to NOAA API path."""
    from dataops_adapter.client_adapter import DataOpsAdapter

    adapter = DataOpsAdapter.__new__(DataOpsAdapter)
    adapter._usgs_to_nwrfc = {'14187500': 'WTLO3'}
    adapter._ec_to_nwrfc = {}
    adapter.api_client = MagicMock()
    adapter.api_client.get_nwrfc_web_forecasts.return_value = []
    adapter.get_forecast_data = MagicMock(return_value=[
        {'run_date': '2026-06-01', 'data': pd.DataFrame()}
    ])

    result = adapter.get_nwrfc_forecasts('14187500', num_days=3)
    adapter.get_forecast_data.assert_called_once_with('14187500', num_days=3)
    assert result is not None


# ── data_manager tests ────────────────────────────────────────────────────────

def test_data_manager_get_nwrfc_forecasts_uses_web_when_flag_set():
    """With _use_nwrfc_web=True, data_manager calls adapter.get_nwrfc_forecasts."""
    from usgs_dashboard.data.data_manager import USGSDataManager

    dm = USGSDataManager.__new__(USGSDataManager)
    dm.adapter = MagicMock()
    dm.adapter.get_nwrfc_forecasts.return_value = []
    dm._use_nwrfc_web = True

    result = dm.get_nwrfc_forecasts('14187500')
    dm.adapter.get_nwrfc_forecasts.assert_called_once_with('14187500')
    assert result == []


def test_data_manager_get_nwrfc_forecasts_uses_legacy_when_flag_false():
    """With _use_nwrfc_web=False, falls back to get_forecast_data."""
    from usgs_dashboard.data.data_manager import USGSDataManager

    dm = USGSDataManager.__new__(USGSDataManager)
    dm.adapter = MagicMock()
    dm.adapter.get_forecast_data.return_value = None
    dm._use_nwrfc_web = False

    result = dm.get_nwrfc_forecasts('14187500')
    dm.adapter.get_forecast_data.assert_called_once_with('14187500')
