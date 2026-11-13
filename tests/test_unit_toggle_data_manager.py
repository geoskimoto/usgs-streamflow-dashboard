"""R4/R5: data_manager display_unit conversion; stats cache stays native.

Mocked: adapter is a MagicMock, stats cache dir is redirected to tmp_path.
"""
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

CFS_PER_CMS = 35.3146667
STAT_COLS = ["q10", "q25", "q50", "q75", "q90", "mean", "median"]
SEED = 20261113


def _history(native_unit, years=15):
    """Daily history ending before the current water year, flow in native unit."""
    rng = np.random.default_rng(SEED)
    end = pd.Timestamp.now().normalize()
    idx = pd.date_range(end - pd.Timedelta(days=365 * years), end, freq="D")
    base = 500.0 if native_unit == "cfs" else 500.0 / CFS_PER_CMS
    vals = base * (1 + rng.random(len(idx)))
    return pd.DataFrame({
        "datetime": idx, "discharge": vals,
        "unit": native_unit, "site_no": "SITE",
    })


@pytest.fixture
def make_dm(tmp_path, monkeypatch):
    def _make(native_unit, subdir="cache"):
        from usgs_dashboard.data import stats_cache_manager as scm
        cache = tmp_path / subdir
        monkeypatch.setattr(scm, "STATS_CACHE_DIR", str(cache))
        with patch("usgs_dashboard.data.data_manager.get_adapter") as ga:
            ga.return_value = MagicMock()
            from usgs_dashboard.data.data_manager import USGSDataManager
            dm = USGSDataManager(cache_dir=str(tmp_path / "dm"))
        hist = _history(native_unit)
        dm.get_streamflow_data = MagicMock(side_effect=lambda *a, **k: hist.copy())
        return dm, cache, hist
    return _make


def _parquets(cache):
    return sorted(Path(cache).glob("*.parquet"))


def _digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------- R4: native cfs site ----------------

def test_stats_cms_for_cfs_site_is_native_divided_by_factor(make_dm):
    dm, cache, _ = make_dm("cfs")
    native = dm.get_flow_statistics("SITE", display_unit="cfs")
    out = dm.get_flow_statistics("SITE", display_unit="cms")
    assert len(native) == len(out) > 0
    for c in STAT_COLS:
        np.testing.assert_allclose(out[c].to_numpy(), native[c].to_numpy() / CFS_PER_CMS, rtol=1e-9)
    np.testing.assert_array_equal(out["day_of_wy"], native["day_of_wy"])


def test_stats_default_display_unit_is_cfs(make_dm):
    dm, _, _ = make_dm("cfs")
    a = dm.get_flow_statistics("SITE")
    b = dm.get_flow_statistics("SITE", display_unit="cfs")
    pd.testing.assert_frame_equal(a, b)


def test_stats_cache_parquet_byte_identical_after_cms_request_warm_cache(make_dm):
    dm, cache, _ = make_dm("cfs")
    dm.get_flow_statistics("SITE", display_unit="cfs")
    files = _parquets(cache)
    assert len(files) == 1
    before = _digest(files[0])
    dm.get_flow_statistics("SITE", display_unit="cms")
    assert _parquets(cache) == files
    assert _digest(files[0]) == before


def test_stats_cache_written_native_when_first_request_is_cms(make_dm):
    """Cold cache + cms request must still persist cfs-native values."""
    dm_a, cache_a, _ = make_dm("cfs", "a")
    dm_a.get_flow_statistics("SITE", display_unit="cfs")
    dm_b, cache_b, _ = make_dm("cfs", "b")
    dm_b.get_flow_statistics("SITE", display_unit="cms")
    fa, fb = _parquets(cache_a), _parquets(cache_b)
    assert len(fa) == len(fb) == 1
    pd.testing.assert_frame_equal(pd.read_parquet(fa[0]), pd.read_parquet(fb[0]))


def test_stats_repeated_cms_requests_do_not_double_convert(make_dm):
    dm, _, _ = make_dm("cfs")
    first = dm.get_flow_statistics("SITE", display_unit="cms")
    second = dm.get_flow_statistics("SITE", display_unit="cms")
    pd.testing.assert_frame_equal(first, second)


# ---------------- R5: native cms site ----------------

def test_stats_cfs_for_cms_site_is_native_times_factor(make_dm):
    dm, cache, _ = make_dm("cms")
    native = dm.get_flow_statistics("SITE", display_unit="cms")
    out = dm.get_flow_statistics("SITE", display_unit="cfs")
    for c in STAT_COLS:
        np.testing.assert_allclose(out[c].to_numpy(), native[c].to_numpy() * CFS_PER_CMS, rtol=1e-9)


def test_stats_parquet_for_cms_site_is_native_cms_even_when_cfs_requested(make_dm):
    dm, cache, hist = make_dm("cms")
    out = dm.get_flow_statistics("SITE", display_unit="cfs")
    files = _parquets(cache)
    assert len(files) == 1
    disk = pd.read_parquet(files[0])
    # native cms magnitude ~ 14-28; cfs would be ~500-1000
    assert disk["median"].max() < 100
    np.testing.assert_allclose(out["median"].to_numpy(), disk["median"].to_numpy() * CFS_PER_CMS, rtol=1e-9)


def test_stats_parquet_bytes_unchanged_for_cms_site_across_unit_requests(make_dm):
    dm, cache, _ = make_dm("cms")
    dm.get_flow_statistics("SITE", display_unit="cms")
    f = _parquets(cache)[0]
    before = _digest(f)
    dm.get_flow_statistics("SITE", display_unit="cfs")
    dm.get_flow_statistics("SITE", display_unit="cms")
    assert _digest(f) == before


def test_stats_empty_history_returns_empty_for_any_unit(make_dm):
    dm, _, _ = make_dm("cfs")
    dm.get_streamflow_data = MagicMock(return_value=pd.DataFrame())
    assert dm.get_flow_statistics("SITE", display_unit="cms").empty


# ---------------- get_current_year_data ----------------

def _current_frame(unit):
    return pd.DataFrame({
        "datetime": pd.date_range("2026-10-01", periods=5),
        "discharge": [100.0, 110.0, np.nan, 130.0, 140.0],
        "unit": unit, "site_no": "SITE",
    })


@pytest.fixture
def dm_plain(tmp_path):
    with patch("usgs_dashboard.data.data_manager.get_adapter") as ga:
        ga.return_value = MagicMock()
        from usgs_dashboard.data.data_manager import USGSDataManager
        return USGSDataManager(cache_dir=str(tmp_path / "dm"))


def test_current_year_data_cms_converts_cfs_native(dm_plain):
    src = _current_frame("cfs")
    dm_plain.get_streamflow_data = MagicMock(return_value=src.copy())
    out = dm_plain.get_current_year_data("SITE", display_unit="cms")
    np.testing.assert_allclose(out["discharge"].to_numpy(),
                               src["discharge"].to_numpy() / CFS_PER_CMS, rtol=1e-9)
    assert set(out["unit"]) == {"cms"}
    assert out["discharge"].isna().sum() == 1  # gap preserved, not filled


def test_current_year_data_default_is_cfs_and_unchanged_for_cfs_site(dm_plain):
    src = _current_frame("cfs")
    dm_plain.get_streamflow_data = MagicMock(return_value=src.copy())
    out = dm_plain.get_current_year_data("SITE")
    np.testing.assert_allclose(out["discharge"].to_numpy(), src["discharge"].to_numpy(), equal_nan=True)


def test_current_year_data_cms_native_site_shown_in_cfs(dm_plain):
    src = _current_frame("cms")
    dm_plain.get_streamflow_data = MagicMock(return_value=src.copy())
    out = dm_plain.get_current_year_data("SITE", display_unit="cfs")
    np.testing.assert_allclose(out["discharge"].to_numpy(),
                               src["discharge"].to_numpy() * CFS_PER_CMS, rtol=1e-9, equal_nan=True)
    assert set(out["unit"]) == {"cfs"}


def test_current_year_data_empty_stays_empty(dm_plain):
    dm_plain.get_streamflow_data = MagicMock(return_value=pd.DataFrame())
    assert dm_plain.get_current_year_data("SITE", display_unit="cms").empty


def test_get_streamflow_data_stays_native_cms(dm_plain):
    """Stats-cache input must not be converted: native values pass through."""
    raw = pd.DataFrame({
        "date": pd.date_range("2026-01-01", periods=3),
        "discharge": [1.0, 2.0, 3.0], "unit": "cms",
    })
    dm_plain.adapter.get_discharge_data.return_value = raw
    out = dm_plain.get_streamflow_data("SITE", start_date="2026-01-01", end_date="2026-01-03")
    assert out["discharge"].tolist() == [1.0, 2.0, 3.0]
    assert set(out["unit"]) == {"cms"}


# ---------------- forecast getters accept display_unit ----------------

@pytest.mark.parametrize("name", ["get_resid_cast_forecasts", "get_blended_forecasts"])
def test_forecast_getters_signature_has_display_unit_default_cfs(name):
    import inspect
    from usgs_dashboard.data.data_manager import USGSDataManager
    p = inspect.signature(getattr(USGSDataManager, name)).parameters
    assert "display_unit" in p
    assert p["display_unit"].default == "cfs"


def test_current_year_and_stats_signatures_have_display_unit_default_cfs():
    import inspect
    from usgs_dashboard.data.data_manager import USGSDataManager
    for name in ("get_current_year_data", "get_flow_statistics"):
        p = inspect.signature(getattr(USGSDataManager, name)).parameters
        assert p["display_unit"].default == "cfs", name
