"""
Tests for manage_cache.py CLI commands.

Covers argument parsing, station list building, rebuild logic,
and clear logic — all with mocked data_manager and filesystem.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ── Path bootstrap (manage_cache.py lives at repo root) ───────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """Redirect STATS_CACHE_DIR to a temp directory."""
    import usgs_dashboard.data.stats_cache_manager as scm
    monkeypatch.setattr(scm, "STATS_CACHE_DIR", str(tmp_path))
    import manage_cache as mc
    monkeypatch.setattr(mc, "STATS_CACHE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def mock_dm():
    """A USGSDataManager mock with a small station list and synthetic discharge."""
    dm = MagicMock()

    stations = pd.DataFrame({
        "station_number": ["14187500", "14185000", "14182500", "14160000"],
        "station_name": ["Station A", "Station B", "Station C", "Station D"],
        "is_active": [True, True, False, True],
        "state": ["OR", "OR", "OR", "WA"],
    })
    dm.load_regional_gauges.return_value = stations

    # Synthetic discharge for any site
    idx = pd.date_range("1994-10-01", "2024-09-30", freq="D")
    rng = np.random.default_rng(7)
    discharge_df = pd.DataFrame({
        "datetime": idx,
        "discharge": np.abs(rng.normal(400, 100, len(idx))),
    })
    dm.get_streamflow_data.return_value = discharge_df
    dm.get_flow_statistics.return_value = pd.DataFrame({
        "day_of_wy": list(range(1, 367)),
        "q10": [100.0] * 366,
        "q25": [200.0] * 366,
        "q50": [300.0] * 366,
        "q75": [400.0] * 366,
        "q90": [500.0] * 366,
        "mean": [310.0] * 366,
        "median": [300.0] * 366,
    })
    dm.get_resid_cast_station_ids.return_value = {"14160000"}

    return dm


@pytest.fixture
def tmp_crosswalk(tmp_path, monkeypatch):
    """Write a minimal crosswalk JSON and point manage_cache at it."""
    cw = {"ACAW1": "13335050", "ABOM8": "12340500", "ACKI1": "14182500"}
    cw_path = tmp_path / "nwrfc_usgs_crosswalk.json"
    cw_path.write_text(json.dumps(cw))
    import manage_cache as mc
    monkeypatch.setattr(mc, "_REPO_ROOT", tmp_path)
    # Also make data dir
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "nwrfc_usgs_crosswalk.json").write_text(json.dumps(cw))
    return cw_path


# ── Argument parser tests ──────────────────────────────────────────────────────

class TestArgParser:
    def _parse(self, args: list):
        import manage_cache as mc
        return mc._build_parser().parse_args(args)

    def test_rebuild_all_stations(self):
        args = self._parse(["rebuild_stats", "--all-stations"])
        assert args.all_stations is True
        assert args.active is False
        assert args.forecast is False
        assert args.site is None

    def test_rebuild_active(self):
        args = self._parse(["rebuild_stats", "--active"])
        assert args.active is True

    def test_rebuild_forecast(self):
        args = self._parse(["rebuild_stats", "--forecast"])
        assert args.forecast is True

    def test_rebuild_single_site(self):
        args = self._parse(["rebuild_stats", "--site", "14187500"])
        assert args.site == "14187500"

    def test_rebuild_flags_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            self._parse(["rebuild_stats", "--all-stations", "--active"])

    def test_rebuild_requires_selection_flag(self):
        with pytest.raises(SystemExit):
            self._parse(["rebuild_stats"])

    def test_workers_default(self):
        args = self._parse(["rebuild_stats", "--all-stations"])
        assert args.workers == 4

    def test_workers_custom(self):
        args = self._parse(["rebuild_stats", "--all-stations", "--workers", "8"])
        assert args.workers == 8

    def test_force_flag(self):
        args = self._parse(["rebuild_stats", "--all-stations", "--force"])
        assert args.force is True

    def test_dry_run_flag(self):
        args = self._parse(["rebuild_stats", "--all-stations", "--dry-run"])
        assert args.dry_run is True

    def test_clear_stats_no_site(self):
        args = self._parse(["clear_stats"])
        assert args.site is None

    def test_clear_stats_with_site(self):
        args = self._parse(["clear_stats", "--site", "14187500"])
        assert args.site == "14187500"


# ── _build_station_list tests ─────────────────────────────────────────────────

class TestBuildStationList:
    def _make_args(self, **kwargs):
        import argparse
        defaults = {
            "all_stations": False,
            "active": False,
            "forecast": False,
            "site": None,
            "workers": 4,
            "force": False,
            "dry_run": False,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_single_site_returns_that_site(self, mock_dm):
        import manage_cache as mc
        args = self._make_args(site="14187500")
        result = mc._build_station_list(args, mock_dm)
        assert result == ["14187500"]
        mock_dm.load_regional_gauges.assert_not_called()

    def test_all_stations_returns_all(self, mock_dm):
        import manage_cache as mc
        args = self._make_args(all_stations=True)
        result = mc._build_station_list(args, mock_dm)
        assert set(result) == {"14187500", "14185000", "14182500", "14160000"}

    def test_active_filters_correctly(self, mock_dm):
        import manage_cache as mc
        args = self._make_args(active=True)
        result = mc._build_station_list(args, mock_dm)
        assert "14182500" not in result  # is_active=False
        assert "14187500" in result
        assert "14185000" in result

    def test_forecast_includes_nwrfc_and_resid_cast(self, mock_dm, tmp_crosswalk, monkeypatch):
        import manage_cache as mc
        # Crosswalk maps to 14182500; ResidCast mock returns 14160000
        args = self._make_args(forecast=True)
        result = mc._build_station_list(args, mock_dm)
        assert "14182500" in result   # from NWRFC crosswalk
        assert "14160000" in result   # from ResidCast
        assert "14187500" not in result  # not in either

    def test_returns_empty_when_stations_df_empty(self, mock_dm):
        import manage_cache as mc
        mock_dm.load_regional_gauges.return_value = pd.DataFrame()
        args = self._make_args(all_stations=True)
        result = mc._build_station_list(args, mock_dm)
        assert result == []


# ── _rebuild_one tests ─────────────────────────────────────────────────────────

class TestRebuildOne:
    def test_rebuilds_when_no_cache(self, mock_dm, tmp_cache):
        import manage_cache as mc
        sid, status, elapsed = mc._rebuild_one("14187500", mock_dm, force=False)
        assert status == "rebuilt"
        assert elapsed >= 0

    def test_skips_when_cache_exists_and_no_force(self, mock_dm, tmp_cache):
        import manage_cache as mc
        from usgs_dashboard.data.stats_cache_manager import _current_water_year, _cache_path
        # Pre-create a cache file
        wy = _current_water_year()
        path = _cache_path("14187500", wy)
        Path(path).write_text("placeholder")

        sid, status, elapsed = mc._rebuild_one("14187500", mock_dm, force=False)
        assert status == "skipped"

    def test_force_rebuilds_even_when_cache_exists(self, mock_dm, tmp_cache):
        import manage_cache as mc
        from usgs_dashboard.data.stats_cache_manager import _current_water_year, _cache_path
        wy = _current_water_year()
        path = _cache_path("14187500", wy)
        Path(path).write_text("placeholder")

        sid, status, elapsed = mc._rebuild_one("14187500", mock_dm, force=True)
        assert status == "rebuilt"

    def test_returns_error_status_on_exception(self, mock_dm, tmp_cache):
        import manage_cache as mc
        mock_dm.get_flow_statistics.side_effect = RuntimeError("API down")
        sid, status, elapsed = mc._rebuild_one("14187500", mock_dm, force=True)
        assert status == "error"


# ── cmd_rebuild_stats integration tests ───────────────────────────────────────

class TestCmdRebuildStats:
    def _make_args(self, **kwargs):
        import argparse
        defaults = {
            "all_stations": False,
            "active": False,
            "forecast": False,
            "site": None,
            "workers": 2,
            "force": False,
            "dry_run": False,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_dry_run_does_not_call_get_flow_statistics(self, mock_dm, tmp_cache, capsys):
        import manage_cache as mc
        with patch.object(mc, "_get_data_manager", return_value=mock_dm):
            args = self._make_args(site="14187500", dry_run=True)
            mc.cmd_rebuild_stats(args)

        mock_dm.get_flow_statistics.assert_not_called()

    def test_dry_run_prints_station_list(self, mock_dm, tmp_cache, capsys):
        import manage_cache as mc
        with patch.object(mc, "_get_data_manager", return_value=mock_dm):
            args = self._make_args(site="14187500", dry_run=True)
            mc.cmd_rebuild_stats(args)

        out = capsys.readouterr().out
        assert "14187500" in out

    def test_processes_all_sites_for_all_stations(self, mock_dm, tmp_cache, capsys):
        import manage_cache as mc
        with patch.object(mc, "_get_data_manager", return_value=mock_dm):
            args = self._make_args(all_stations=True, workers=2)
            mc.cmd_rebuild_stats(args)

        assert mock_dm.get_flow_statistics.call_count == 4

    def test_processes_single_site(self, mock_dm, tmp_cache, capsys):
        import manage_cache as mc
        with patch.object(mc, "_get_data_manager", return_value=mock_dm):
            args = self._make_args(site="14187500")
            mc.cmd_rebuild_stats(args)

        mock_dm.get_flow_statistics.assert_called_once_with("14187500")


# ── cmd_clear_stats tests ──────────────────────────────────────────────────────

class TestCmdClearStats:
    def _make_args(self, site=None):
        import argparse
        return argparse.Namespace(site=site)

    def test_clears_specific_site(self, tmp_cache, monkeypatch):
        import manage_cache as mc
        from usgs_dashboard.data.stats_cache_manager import _current_water_year

        wy = _current_water_year()
        (tmp_cache / f"14187500_WY{wy}.parquet").write_text("x")
        (tmp_cache / f"14185000_WY{wy}.parquet").write_text("x")

        args = self._make_args(site="14187500")
        mc.cmd_clear_stats(args)

        assert not (tmp_cache / f"14187500_WY{wy}.parquet").exists()
        assert (tmp_cache / f"14185000_WY{wy}.parquet").exists()  # untouched

    def test_clears_all_with_confirmation(self, tmp_cache, monkeypatch):
        import manage_cache as mc
        from usgs_dashboard.data.stats_cache_manager import _current_water_year

        wy = _current_water_year()
        for sid in ("14187500", "14185000", "14182500"):
            (tmp_cache / f"{sid}_WY{wy}.parquet").write_text("x")

        monkeypatch.setattr("builtins.input", lambda _: "y")
        args = self._make_args()
        mc.cmd_clear_stats(args)

        assert list(tmp_cache.glob("*_WY*.parquet")) == []

    def test_aborts_clear_all_without_confirmation(self, tmp_cache, monkeypatch):
        import manage_cache as mc
        from usgs_dashboard.data.stats_cache_manager import _current_water_year

        wy = _current_water_year()
        p = tmp_cache / f"14187500_WY{wy}.parquet"
        p.write_text("x")

        monkeypatch.setattr("builtins.input", lambda _: "n")
        args = self._make_args()
        mc.cmd_clear_stats(args)

        assert p.exists()  # file still there

    def test_reports_no_files_when_cache_empty(self, tmp_cache, capsys):
        import manage_cache as mc
        args = self._make_args(site="99999999")
        mc.cmd_clear_stats(args)
        out = capsys.readouterr().out
        assert "No cache files found" in out
