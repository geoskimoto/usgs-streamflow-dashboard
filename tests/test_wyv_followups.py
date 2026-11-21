"""Follow-up tests for Water Year Volume behaviors found unprotected by mutation testing.

Reuses helpers from test_water_year_volume.py / test_viz_water_year_volume.py.
Test 'real adapter failure => status error' is expected to FAIL until implemented.
"""
import logging
import time
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tests.test_water_year_volume import _frame, _wire, dm  # noqa: F401 (dm is a fixture)
from tests.test_viz_water_year_volume import _vol, _build, _annotations

GAUGES = [{"site_id": "111", "station_name": "Test Creek"}, {"site_id": "222", "station_name": "Other"}]


@pytest.fixture
def app_module():
    import app as m
    return m


def _render(m, requested=True, mode="daily", unit="cfs-days", dark=True, gauge="111",
            height=600, window=1200):
    return m.render_water_year_volume(requested, mode, unit, dark, gauge, GAUGES, height, [], window)


# ---- app callbacks

@pytest.mark.parametrize("req,disp", [(False, "none"), (None, "none"), (True, "block")])
def test_toggle_wyv_section_shows_only_when_requested(app_module, req, disp):
    assert app_module.toggle_wyv_section(req) == {"display": disp}


@pytest.mark.parametrize("kw", [dict(requested=False), dict(gauge=None)])
def test_render_returns_empty_figure_without_fetching(app_module, kw):
    with patch.object(app_module, "data_manager") as dmm, patch.object(app_module, "viz_manager") as vm:
        fig, _, _, _ = _render(app_module, **kw)
    assert len(fig.data) == 0
    dmm.get_water_year_volume.assert_not_called()
    vm.create_water_year_volume_plot.assert_not_called()


def test_render_passes_gauge_volume_mode_unit_and_dark_to_builder(app_module):
    with patch.object(app_module, "data_manager") as dmm, patch.object(app_module, "viz_manager") as vm:
        dmm.get_water_year_volume.return_value = {"status": "ok"}
        _render(app_module, mode="daily", unit="cfs-days", dark=True)
    dmm.get_water_year_volume.assert_called_once_with("111")
    from datetime import datetime
    now = datetime.today()
    cur = now.year + 1 if now.month >= 10 else now.year
    vm.create_water_year_volume_plot.assert_called_once_with(
        "111", {"status": "ok"}, "daily", "cfs-days", True, highlight_years=[cur])


def test_render_none_mode_and_unit_fall_back_to_defaults(app_module):
    with patch.object(app_module, "data_manager"), patch.object(app_module, "viz_manager") as vm:
        _render(app_module, mode=None, unit=None, dark=None)
    assert vm.create_water_year_volume_plot.call_args.args[2:] == ("cumulative", "kaf", False)


def test_render_title_contains_station_name(app_module):
    with patch.object(app_module, "data_manager"), patch.object(app_module, "viz_manager"):
        _, _, _, title = _render(app_module)
    assert "Test Creek" in title and "111" in title


def test_render_narrow_window_caps_height_at_400(app_module):
    with patch.object(app_module, "data_manager"), patch.object(app_module, "viz_manager"):
        _, _, narrow, _ = _render(app_module, height=700, window=500)
        _, _, wide, _ = _render(app_module, height=700, window=1200)
    assert narrow["height"] == "400px"
    assert wide["height"] == "700px"


# ---- data_manager wiring

def test_dm_current_water_year_excluded_from_bands(dm):  # noqa: F811
    from usgs_dashboard.utils.water_year_calculator import get_water_year
    cur = get_water_year(pd.Timestamp.now())
    hist = _frame(list(range(cur - 12, cur)), flow=lambda wy, i: 100.0, current=(cur, 100))
    hist.loc[hist["datetime"] >= f"{cur - 1}-10-01", "discharge"] = 1e6
    _wire(dm, hist)
    out = dm.get_water_year_volume("SITE")
    b = out["bands"]["bands"].set_index("day_of_wy")
    assert b.loc[50, "q90"] == pytest.approx(100.0 * 50)


def test_dm_cache_ttl_is_300_seconds(dm, monkeypatch):  # noqa: F811
    from usgs_dashboard.utils.water_year_calculator import get_water_year
    cur = get_water_year(pd.Timestamp.now())
    _wire(dm, _frame(list(range(cur - 12, cur)), current=(cur, 40)))
    offset = {"v": 0.0}
    rt, rm = time.time, time.monotonic
    monkeypatch.setattr(time, "time", lambda: rt() + offset["v"])
    monkeypatch.setattr(time, "monotonic", lambda: rm() + offset["v"])
    dm.get_water_year_volume("SITE")
    offset["v"] = 299.0
    dm.get_water_year_volume("SITE")
    assert dm.get_streamflow_data.call_count == 1
    offset["v"] = 301.0
    dm.get_water_year_volume("SITE")
    assert dm.get_streamflow_data.call_count == 2


def test_r25_adapter_failure_is_error_status_and_logs_no_secret(dm, caplog):  # noqa: F811
    dm.adapter.get_discharge_data.side_effect = ConnectionError("https://api.example/x?token=SECRETTOKEN123")
    with caplog.at_level(logging.DEBUG):
        out = dm.get_water_year_volume("SITE88")
    assert out["status"] == "error"
    assert "SITE88" in caplog.text
    assert "SECRETTOKEN123" not in caplog.text
    assert "https://" not in caplog.text


def test_r25_genuinely_empty_adapter_response_is_empty_not_error(dm):  # noqa: F811
    dm.adapter.get_discharge_data.side_effect = None
    dm.adapter.get_discharge_data.return_value = pd.DataFrame()
    assert dm.get_water_year_volume("SITE")["status"] == "empty"


# ---- viz

def test_daily_mode_with_daily_bands_has_no_not_enough_years_note():
    fig = _build(_vol(has_bands=False), mode="daily")
    assert "Not enough complete years" not in _annotations(fig)
    assert any(t.name == "Observed" for t in fig.data)


def test_cumulative_mode_has_inner_25_75_band_trace():
    fig = _build(_vol(has_bands=True), mode="cumulative")
    assert any(t.name and "25th" in t.name for t in fig.data)
