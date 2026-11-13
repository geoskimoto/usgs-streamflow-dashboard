"""Spec tests for usgs_dashboard/utils/units.py (docs/UNIT_TOGGLE_PLAN.md R1-R3).

hypothesis is not installed, so property-style checks use parametrized,
seeded random inputs (SEED recorded below).
"""
import random

import numpy as np
import pandas as pd
import pytest

SEED = 20261113
CFS_PER_CMS = 35.3146667


def _u():
    from usgs_dashboard.utils import units
    return units


def _rand_values(n=200):
    rng = random.Random(SEED)
    return [10 ** rng.uniform(-3, 6) for _ in range(n)]


# ---------------- R1 conversion factor / inverse / round trip ----------------

def test_constant_cfs_per_cms_matches_spec():
    assert _u().CFS_PER_CMS == pytest.approx(CFS_PER_CMS, rel=1e-12)


def test_convert_flow_one_cms_is_35_3146667_cfs():
    assert _u().convert_flow(1, "cms", "cfs") == pytest.approx(CFS_PER_CMS)


def test_convert_flow_cfs_to_cms_is_inverse_factor():
    assert _u().convert_flow(CFS_PER_CMS, "cfs", "cms") == pytest.approx(1.0)
    assert _u().convert_flow(1, "cfs", "cms") == pytest.approx(1 / CFS_PER_CMS)


@pytest.mark.parametrize("v", _rand_values())
def test_round_trip_cfs_cms_cfs_within_1e9_relative(v):
    u = _u()
    back = u.convert_flow(u.convert_flow(v, "cfs", "cms"), "cms", "cfs")
    assert back == pytest.approx(v, rel=1e-9)


@pytest.mark.parametrize("v", _rand_values(60))
def test_round_trip_cms_cfs_cms_within_1e9_relative(v):
    u = _u()
    back = u.convert_flow(u.convert_flow(v, "cms", "cfs"), "cfs", "cms")
    assert back == pytest.approx(v, rel=1e-9)


def test_convert_flow_is_monotonic_increasing():
    u = _u()
    vals = sorted(_rand_values())
    out = [u.convert_flow(v, "cfs", "cms") for v in vals]
    assert all(a <= b for a, b in zip(out, out[1:]))
    out2 = [u.convert_flow(v, "cms", "cfs") for v in vals]
    assert all(a <= b for a, b in zip(out2, out2[1:]))


def test_convert_flow_zero_stays_zero_and_negative_sign_preserved():
    u = _u()
    assert u.convert_flow(0.0, "cms", "cfs") == 0.0
    assert u.convert_flow(-1.0, "cms", "cfs") == pytest.approx(-CFS_PER_CMS)


def test_convert_flow_ndarray():
    arr = np.array([1.0, 2.0, np.nan])
    out = _u().convert_flow(arr, "cms", "cfs")
    assert isinstance(out, np.ndarray)
    np.testing.assert_allclose(out[:2], [CFS_PER_CMS, 2 * CFS_PER_CMS])
    assert np.isnan(out[2])


def test_convert_flow_series_preserves_index_and_nan():
    s = pd.Series([1.0, np.nan, 3.0], index=pd.date_range("2026-01-01", periods=3))
    out = _u().convert_flow(s, "cms", "cfs")
    assert isinstance(out, pd.Series)
    assert out.index.equals(s.index)
    assert np.isnan(out.iloc[1])
    assert out.iloc[2] == pytest.approx(3 * CFS_PER_CMS)


def test_convert_flow_does_not_mutate_series_input():
    s = pd.Series([1.0, 2.0])
    _u().convert_flow(s, "cms", "cfs")
    assert s.tolist() == [1.0, 2.0]


# ---------------- R3 identity ----------------

@pytest.mark.parametrize("unit", ["cfs", "cms"])
@pytest.mark.parametrize("v", _rand_values(20))
def test_same_unit_conversion_is_identity(unit, v):
    assert _u().convert_flow(v, unit, unit) == v


def test_same_unit_conversion_preserves_nan():
    assert np.isnan(_u().convert_flow(float("nan"), "cfs", "cfs"))


# ---------------- normalize_unit ----------------

@pytest.mark.parametrize("raw,expected", [
    ("cfs", "cfs"), ("CFS", "cfs"), ("Cfs", "cfs"),
    ("cms", "cms"), ("CMS", "cms"),
    ("m3/s", "cms"), ("M3/S", "cms"), ("m³/s", "cms"),
    (None, "cfs"), (float("nan"), "cfs"),
])
def test_normalize_unit_accepts_variants(raw, expected):
    assert _u().normalize_unit(raw) == expected


@pytest.mark.parametrize("bad", ["furlongs", "mgd", "", "l/s"])
def test_normalize_unit_rejects_unknown(bad):
    with pytest.raises(ValueError):
        _u().normalize_unit(bad)


def test_convert_flow_unknown_unit_raises():
    with pytest.raises(ValueError):
        _u().convert_flow(1.0, "furlongs", "cfs")


def test_convert_flow_accepts_unit_aliases():
    assert _u().convert_flow(1, "m3/s", "CFS") == pytest.approx(CFS_PER_CMS)


# ---------------- labels ----------------

def test_unit_label():
    u = _u()
    assert u.unit_label("cfs") == "cfs"
    assert u.unit_label("cms") == "m³/s"


def test_axis_title_default_prefix():
    u = _u()
    assert u.axis_title("cfs") == "Discharge (cfs)"
    assert u.axis_title("cms") == "Discharge (m³/s)"


def test_axis_title_custom_prefix():
    assert _u().axis_title("cms", prefix="Flow") == "Flow (m³/s)"


# ---------------- R2 convert_frame ----------------

def _mixed_frame():
    return pd.DataFrame({
        "datetime": pd.date_range("2026-01-01", periods=4),
        "discharge": [10.0, 2.0, np.nan, 5.0],
        "unit": ["cfs", "cms", "cms", "cfs"],
        "site_no": ["X"] * 4,
        "note": ["a", "b", "c", "d"],
    })


def test_convert_frame_mixed_rows_to_cfs():
    out = _u().convert_frame(_mixed_frame(), "cfs")
    assert out["discharge"].iloc[0] == pytest.approx(10.0)
    assert out["discharge"].iloc[1] == pytest.approx(2 * CFS_PER_CMS)
    assert np.isnan(out["discharge"].iloc[2])
    assert out["discharge"].iloc[3] == pytest.approx(5.0)


def test_convert_frame_mixed_rows_to_cms():
    out = _u().convert_frame(_mixed_frame(), "cms")
    assert out["discharge"].iloc[0] == pytest.approx(10.0 / CFS_PER_CMS)
    assert out["discharge"].iloc[1] == pytest.approx(2.0)
    assert out["discharge"].iloc[3] == pytest.approx(5.0 / CFS_PER_CMS)


@pytest.mark.parametrize("target", ["cfs", "cms"])
def test_convert_frame_sets_unit_column(target):
    out = _u().convert_frame(_mixed_frame(), target)
    assert set(out["unit"]) == {target}


def test_convert_frame_does_not_mutate_input_and_returns_copy():
    df = _mixed_frame()
    before = df.copy(deep=True)
    out = _u().convert_frame(df, "cms")
    pd.testing.assert_frame_equal(df, before)
    assert out is not df


def test_convert_frame_preserves_non_flow_columns():
    df = _mixed_frame()
    out = _u().convert_frame(df, "cms")
    for c in ("datetime", "site_no", "note"):
        assert out[c].equals(df[c])
    assert len(out) == len(df)


def test_convert_frame_missing_unit_column_defaults_to_cfs():
    df = pd.DataFrame({"discharge": [CFS_PER_CMS, 70.6293334]})
    out = _u().convert_frame(df, "cms")
    assert out["discharge"].iloc[0] == pytest.approx(1.0)
    assert out["discharge"].iloc[1] == pytest.approx(2.0)
    assert set(out["unit"]) == {"cms"}


def test_convert_frame_default_cols_cover_discharge_cfs_and_stats():
    cols = ["discharge_cfs", "q10", "q25", "q50", "q75", "q90", "mean", "median"]
    df = pd.DataFrame({c: [CFS_PER_CMS] for c in cols})
    df["day_of_wy"] = [5]
    out = _u().convert_frame(df, "cms")
    for c in cols:
        assert out[c].iloc[0] == pytest.approx(1.0), c
    assert out["day_of_wy"].iloc[0] == 5  # not a flow column


def test_convert_frame_explicit_cols_only_converts_those():
    df = pd.DataFrame({"discharge": [CFS_PER_CMS], "other": [CFS_PER_CMS]})
    out = _u().convert_frame(df, "cms", cols=["other"])
    assert out["other"].iloc[0] == pytest.approx(1.0)
    assert out["discharge"].iloc[0] == pytest.approx(CFS_PER_CMS)


def test_convert_frame_same_unit_is_identity_on_values():
    df = _mixed_frame()
    df["unit"] = "cfs"
    out = _u().convert_frame(df, "cfs")
    pd.testing.assert_series_equal(out["discharge"], df["discharge"])


def test_convert_frame_round_trip():
    df = _mixed_frame()
    back = _u().convert_frame(_u().convert_frame(df, "cms"), "cfs")
    # all rows now cfs; originally-cms row 1 comes back as 2 cms * factor
    expected = [10.0, 2 * CFS_PER_CMS, np.nan, 5.0]
    np.testing.assert_allclose(back["discharge"], expected, rtol=1e-9)
