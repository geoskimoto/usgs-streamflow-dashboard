"""Regression: m3/s mode flat-lined plots (y-scale ~35x too large).

Root cause under test: the REAL stats frame (stats_cache_manager._compute_statistics)
has q03 and q97 columns that convert_frame's default flow columns missed, so those
stayed in cfs after conversion to cms.

These tests derive the column set from the real _compute_statistics output
instead of hardcoding it, so they track future column additions.
Mocked only: adapter is a MagicMock, cache dir redirected to tmp_path.
"""
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

CFS_PER_CMS = 35.3146667
SEED = 20261114
NON_FLOW = {"day_of_wy", "unit"}


def _history(native_unit, years=16):
    rng = np.random.default_rng(SEED)
    end = pd.Timestamp.now().normalize()
    idx = pd.date_range(end - pd.Timedelta(days=365 * years), end, freq="D")
    base = 500.0 if native_unit == "cfs" else 500.0 / CFS_PER_CMS
    vals = base * (1 + rng.random(len(idx)))
    return pd.DataFrame({"datetime": idx, "discharge": vals,
                         "unit": native_unit, "site_no": "SITE"})


def _real_stats_cfs():
    from usgs_dashboard.data.stats_cache_manager import _compute_statistics
    from usgs_dashboard.utils.water_year_calculator import get_water_year
    cur = get_water_year(pd.Timestamp.now())
    stats = _compute_statistics(_history("cfs"), cur)
    assert not stats.empty, "real _compute_statistics returned nothing for 16y history"
    stats["unit"] = "cfs"
    return stats


def _flow_cols(df):
    return [c for c in df.columns if c not in NON_FLOW]


# ---------------- (1) convert_frame on the real stats frame ----------------

def test_real_stats_frame_contains_q03_and_q97():
    """Guard that the premise (real frame has tail percentiles) holds."""
    cols = set(_real_stats_cfs().columns)
    assert {"q03", "q97"} <= cols


def test_convert_frame_cms_divides_every_real_stats_column_by_factor():
    from usgs_dashboard.utils.units import convert_frame
    stats = _real_stats_cfs()
    out = convert_frame(stats, "cms")
    assert set(out.columns) == set(stats.columns)
    cols = _flow_cols(stats)
    assert len(cols) >= 9
    for c in cols:
        np.testing.assert_allclose(out[c].to_numpy(), stats[c].to_numpy() / CFS_PER_CMS,
                                   rtol=1e-9, err_msg=f"column {c} not converted")


def test_convert_frame_leaves_day_of_wy_unchanged_and_sets_unit():
    from usgs_dashboard.utils.units import convert_frame
    stats = _real_stats_cfs()
    out = convert_frame(stats, "cms")
    np.testing.assert_array_equal(out["day_of_wy"].to_numpy(), stats["day_of_wy"].to_numpy())
    assert set(out["unit"]) == {"cms"}


def test_convert_frame_cms_to_cfs_roundtrip_on_real_stats():
    from usgs_dashboard.utils.units import convert_frame
    stats = _real_stats_cfs()
    back = convert_frame(convert_frame(stats, "cms"), "cfs")
    for c in _flow_cols(stats):
        np.testing.assert_allclose(back[c].to_numpy(), stats[c].to_numpy(), rtol=1e-9,
                                   err_msg=c)


# ---------------- (2) through USGSDataManager.get_flow_statistics ----------------

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


@pytest.mark.parametrize("native, shown, mult", [
    ("cfs", "cms", 1 / CFS_PER_CMS),   # cfs-native site shown in cms
    ("cms", "cfs", CFS_PER_CMS),       # cms-native site shown in cfs
])
def test_get_flow_statistics_scales_every_flow_column_including_tails(make_dm, native, shown, mult):
    dm, _, _ = make_dm(native)
    base = dm.get_flow_statistics("SITE", display_unit=native)
    out = dm.get_flow_statistics("SITE", display_unit=shown)
    assert {"q03", "q97"} <= set(base.columns)
    cols = _flow_cols(base)
    assert {"q03", "q97"} <= set(cols)
    for c in cols:
        np.testing.assert_allclose(out[c].to_numpy(), base[c].to_numpy() * mult,
                                   rtol=1e-9, err_msg=f"{c} wrong for {native}->{shown}")
    np.testing.assert_array_equal(out["day_of_wy"].to_numpy(), base["day_of_wy"].to_numpy())


@pytest.mark.parametrize("native, shown", [("cfs", "cms"), ("cms", "cfs")])
def test_parquet_stays_native_and_byte_identical_across_unit_requests(make_dm, native, shown):
    dm, cache, _ = make_dm(native)
    dm.get_flow_statistics("SITE", display_unit=native)
    files = _parquets(cache)
    assert len(files) == 1
    before = _digest(files[0])
    dm.get_flow_statistics("SITE", display_unit=shown)
    dm.get_flow_statistics("SITE", display_unit=native)
    assert _parquets(cache) == files
    assert _digest(files[0]) == before
    disk = pd.read_parquet(files[0])
    # native magnitude check on the tail columns specifically
    expect_max = 1100 if native == "cfs" else 1100 / CFS_PER_CMS
    assert disk["q97"].max() <= expect_max * 1.01
    assert disk["q03"].min() >= (500 if native == "cfs" else 500 / CFS_PER_CMS) * 0.99


# ---------------- (3) plotted magnitude in cms ----------------

def _all_plotted_y(fig):
    vals = []
    for t in fig.data:
        y = getattr(t, "y", None)
        if y is None:
            continue
        a = pd.to_numeric(pd.Series(list(y)), errors="coerce").dropna().to_numpy(dtype=float)
        vals.append(a)
    return np.concatenate(vals) if vals else np.array([])


def test_fast_water_year_plot_cms_has_no_trace_35x_too_large():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    from usgs_dashboard.utils.units import convert_frame
    stats_cfs = _real_stats_cfs()
    stats_cms = convert_frame(stats_cfs, "cms")
    cur_cfs = pd.DataFrame({
        "datetime": pd.date_range("2026-10-01", periods=30),
        "discharge": np.linspace(600.0, 900.0, 30),
        "unit": "cfs", "site_no": "SITE"})
    cur_cms = convert_frame(cur_cfs, "cms")
    fig = VisualizationManager().create_fast_water_year_plot(
        "SITE", cur_cms, stats_cms, unit="cms")
    y = _all_plotted_y(fig)
    assert y.size > 0
    # Reference max is computed independently from the cfs-native inputs, so a
    # column missed by convert_frame cannot inflate the bound.
    input_max = max(float(stats_cfs[_flow_cols(stats_cfs)].to_numpy().max()),
                    float(cur_cfs["discharge"].max())) / CFS_PER_CMS
    # Stacked percentile bands may be cumulative or not; allow 1.5x headroom only.
    assert y.max() <= 1.5 * input_max, (
        f"max plotted y {y.max():.2f} vs converted input max {input_max:.2f} "
        "(~35x ratio means an unconverted cfs column)")


def test_fast_water_year_plot_cms_max_y_comparable_to_cfs_max_y_divided_by_factor():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    from usgs_dashboard.utils.units import convert_frame
    stats = _real_stats_cfs()
    cur = pd.DataFrame({"datetime": pd.date_range("2026-10-01", periods=30),
                        "discharge": np.linspace(600.0, 900.0, 30),
                        "unit": "cfs", "site_no": "SITE"})
    vm = VisualizationManager()
    f_cfs = vm.create_fast_water_year_plot("SITE", cur, stats, unit="cfs")
    f_cms = vm.create_fast_water_year_plot(
        "SITE", convert_frame(cur, "cms"), convert_frame(stats, "cms"), unit="cms")
    ratio = _all_plotted_y(f_cfs).max() / _all_plotted_y(f_cms).max()
    assert ratio == pytest.approx(CFS_PER_CMS, rel=0.02)


# ---------------- (4) property: any q<digits> column is converted ----------------

# hypothesis is not installed in this venv, so this is a seeded randomized
# property test (seed recorded in SEED) rather than a hypothesis one.
@pytest.mark.parametrize("case", range(40))
def test_property_any_q_digits_column_is_converted_by_default(case):
    from usgs_dashboard.utils.units import convert_frame
    rng = np.random.default_rng(SEED + case)
    digits = rng.choice(1000, size=int(rng.integers(1, 7)), replace=False)
    values = rng.uniform(0.0, 1e6, size=int(rng.integers(1, 6)))
    names = [f"q{d:02d}" for d in digits]
    df = pd.DataFrame({n: values for n in names})
    df["day_of_wy"] = np.arange(1, len(values) + 1)
    df["unit"] = "cfs"
    out = convert_frame(df, "cms")
    for n in names:
        np.testing.assert_allclose(out[n].to_numpy(), values / CFS_PER_CMS, rtol=1e-9, err_msg=n)
    np.testing.assert_array_equal(out["day_of_wy"].to_numpy(), df["day_of_wy"].to_numpy())
