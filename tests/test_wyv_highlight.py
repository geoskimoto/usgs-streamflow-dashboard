"""Water Year Volume highlighted years (H1-H10).

Spec: docs/superpowers/plans/2026-11-21-wyv-highlight-years.md
Written BEFORE the implementation; expected to fail until it exists.

ASSUMED INTERFACES:
  VisualizationManager().create_water_year_volume_plot(site_id, vol, mode, vol_unit, dark,
                                                       highlight_years=None)
  usgs_dashboard.utils.config.HIGHLIGHT_YEAR_COLORS
  app.parse_highlight_years(text) -> list[int]
  app.render_water_year_volume(..., window_width, highlight_text=None)
  The builder is called by the callback with highlight_years either as 6th positional or
  as the keyword 'highlight_years'.
AMBIGUITY: the plan does not say whether the trace line colour is compared case-sensitively;
  colours are compared lower-cased.
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from tests.test_viz_water_year_volume import _vol as _base_vol, _observed, _hover, _vm

KAF = 86400.0 / 43560.0 / 1000.0


def _year_table(wy, base):
    d = np.arange(1, 366)
    daily = base + 0.5 * d
    return pd.DataFrame({"water_year": wy, "day_of_wy": d, "daily_cfs_days": daily,
                         "cum_cfs_days": np.cumsum(daily)})


def _vol(years=(2023, 2024, 2025), gaps=None):
    """Base vol (current WY 2027, 60 observed days) plus full tables for other years.

    gaps: {year: [day_of_wy, ...]} daily values set to NaN; summary reports them missing.
    """
    gaps = {2024: [10, 11, 12], 2025: [20]} if gaps is None else gaps
    v = _base_vol()
    tables, rows = [v["table"]], []
    for i, y in enumerate(years):
        t = _year_table(y, 100.0 + 37.0 * i)
        for d in gaps.get(y, []):
            t.loc[t["day_of_wy"] == d, "daily_cfs_days"] = np.nan
        tables.append(t)
        n = len(gaps.get(y, []))
        rows.append({"water_year": y, "elapsed_days": 365, "observed_days": 365 - n,
                     "missing_days": n})
    v["table"] = pd.concat(tables, ignore_index=True)
    v["summary"] = pd.DataFrame(rows, columns=["water_year", "elapsed_days",
                                               "observed_days", "missing_days"])
    return v


def _build(vol=None, hy=None, mode="cumulative", unit="kaf"):
    return _vm().create_water_year_volume_plot("SITE", _vol() if vol is None else vol,
                                               mode, unit, False, highlight_years=hy)


def _names(fig):
    return [t.name for t in fig.data]


def _hl(fig):
    return [t for t in fig.data if (t.name or "").startswith("WY ")]


def _y(t):
    return np.asarray([np.nan if a is None else a for a in t.y], dtype=float)


def _col(t):
    return t.line.color.lower()


# ---- H1
@pytest.mark.parametrize("hy", [None, []])
def test_h1_none_or_empty_highlights_leave_trace_names_unchanged(hy):
    v = _vol()
    baseline = _vm().create_water_year_volume_plot("SITE", v, "cumulative", "kaf", False)
    assert _names(_build(v, hy)) == _names(baseline)
    assert not _hl(_build(v, hy))


# ---- H2
@pytest.mark.parametrize("mode,col", [("cumulative", "cum_cfs_days"), ("daily", "daily_cfs_days")])
@pytest.mark.parametrize("unit,f", [("kaf", KAF), ("cfs-days", 1.0)])
def test_h2_highlight_values_scaled_for_mode_and_unit(mode, col, unit, f):
    v = _vol(gaps={})
    fig = _build(v, [2023], mode, unit)
    t = [x for x in fig.data if x.name == "WY 2023"][0]
    exp = v["table"].query("water_year == 2023")[col].to_numpy() * f
    np.testing.assert_allclose(_y(t), exp, rtol=1e-6)


def test_h2_highlight_x_aligned_with_observed_reference_dates():
    fig = _build(_vol(), [2023])
    obs = pd.to_datetime(pd.Series(list(_observed(fig).x)))
    t = [x for x in fig.data if x.name == "WY 2023"][0]
    hx = pd.to_datetime(pd.Series(list(t.x)))
    assert (hx.iloc[0].month, hx.iloc[0].day) == (10, 1)
    assert list(hx.iloc[:len(obs)]) == list(obs)


# ---- H3
def test_h3_highlight_width_is_1_75_and_thinner_than_observed():
    fig = _build(_vol(), [2023, 2024])
    obs = _observed(fig)
    for t in _hl(fig):
        assert t.line.width == 1.75
        assert t.line.width < obs.line.width


# ---- H4
def test_h4_colours_follow_palette_by_input_index():
    from usgs_dashboard.utils.config import HIGHLIGHT_YEAR_COLORS as P
    fig = _build(_vol(), [2025, 2023, 2024])
    got = {t.name.split(" (")[0]: _col(t) for t in _hl(fig)}
    assert got == {"WY 2025": P[0].lower(), "WY 2023": P[1].lower(), "WY 2024": P[2].lower()}


def test_h4_colour_index_wraps_beyond_palette_length():
    from usgs_dashboard.utils.config import HIGHLIGHT_YEAR_COLORS as P
    years = list(range(2014, 2025))  # 11 years > 8 colours
    fig = _build(_vol(years=years, gaps={}), years)
    got = {t.name: _col(t) for t in _hl(fig)}
    for i, y in enumerate(years):
        assert got[f"WY {y}"] == P[i % len(P)].lower()


def test_h4_index_counts_skipped_years():
    from usgs_dashboard.utils.config import HIGHLIGHT_YEAR_COLORS as P
    fig = _build(_vol(), [1999, 2023, 2024])  # 1999 absent from table, still occupies index 0
    got = {t.name.split(" (")[0]: _col(t) for t in _hl(fig)}
    assert got == {"WY 2023": P[1].lower(), "WY 2024": P[2].lower()}


# ---- H5
def test_h5_missing_duplicate_current_and_non_int_are_ignored_in_input_order():
    fig = _build(_vol(), [2025, 1999, 2025, 2027, "abc", None, 2023])
    names = [t.name.split(" (")[0] for t in _hl(fig)]
    assert names == ["WY 2025", "WY 2023"]
    assert _names(fig).count("Observed") == 1


# ---- H6
@pytest.mark.parametrize("mode,unit,other", [("cumulative", "kaf", "cfs-days"),
                                             ("daily", "cfs-days", "kaf")])
def test_h6_hover_has_year_four_sig_digits_and_only_its_unit(mode, unit, other):
    t = _hl(_build(_vol(), [2023], mode, unit))[0]
    h = _hover(t)
    assert "2023" in h
    assert unit in h and other not in h
    assert ":.4g" in h or ".4g" in h or "%{y:.4" in h  # 4 significant digits, as the other traces


# ---- H7
def test_h7_order_is_bands_then_highlights_then_observed_last():
    fig = _build(_vol(), [2023, 2024])
    names = _names(fig)
    assert names[-1] == "Observed"
    hl_idx = [i for i, n in enumerate(names) if n.startswith("WY ")]
    band_idx = [i for i, n in enumerate(names) if not n.startswith("WY ") and n != "Observed"]
    assert hl_idx and band_idx
    assert max(band_idx) < min(hl_idx) and max(hl_idx) < len(names) - 1


# ---- H8
def test_h8_missing_day_suffix_plural_singular_and_none_when_complete():
    names = _names(_build(_vol(), [2024, 2025, 2023]))
    assert "WY 2024 (3 missing days)" in names
    assert "WY 2025 (1 missing day)" in names
    assert "WY 2023" in names


def test_h8_daily_gaps_stay_nan_not_interpolated():
    t = [x for x in _build(_vol(), [2024], "daily", "cfs-days").data
         if x.name.startswith("WY 2024")][0]
    assert np.isnan(_y(t)[9:12]).all()
    assert not np.isnan(_y(t)[[8, 12]]).any()


# ---- H9
@pytest.mark.parametrize("text,exp", [("2025, 2024 ,x,2023", [2025, 2024, 2023]),
                                      ("2025 2024", [2025, 2024]),
                                      ("", []), (None, [])])
def test_h9_parse_highlight_years(text, exp):
    import app
    assert app.parse_highlight_years(text) == exp


# ---- H10
@pytest.fixture
def app_module():
    import app as m
    return m


def _call(m, *extra, **kw):
    gauges = [{"site_id": "111", "station_name": "Test Creek"}]
    with patch.object(m, "data_manager") as dmm, patch.object(m, "viz_manager") as vm:
        dmm.get_water_year_volume.return_value = {"status": "ok"}
        m.render_water_year_volume(True, "daily", "kaf", False, "111", gauges, 600, [], 1200,
                                   *extra, **kw)
    return vm.create_water_year_volume_plot.call_args


def _hy_arg(call):
    return call.kwargs["highlight_years"] if "highlight_years" in call.kwargs else call.args[5]


def _current_wy():
    t = pd.Timestamp.now()
    return t.year + 1 if t.month >= 10 else t.year


def test_h10_callback_passes_parsed_years_then_current_wy(app_module):
    cur = _current_wy()
    assert _hy_arg(_call(app_module, highlight_text="2025, 2024")) == [2025, 2024, cur]
    assert _hy_arg(_call(app_module, highlight_text=f"{cur}, 2024")) == [cur, 2024]
    assert _hy_arg(_call(app_module, highlight_text=None)) == [cur]


def test_h10_nine_positional_call_still_works(app_module):
    assert _call(app_module) is not None


def test_h10_callback_map_wiring(app_module):
    for entry in app_module.app.callback_map.values():
        ids = [i["id"] for i in entry["inputs"]]
        if "wyv-mode" in ids:
            break
    else:
        pytest.fail("render callback not found in callback_map")
    props = {i["id"] for i in entry["inputs"]}
    assert {"highlight-years-input", "wyv-mode", "wyv-unit", "annual-summary-requested",
            "dark-mode-store"} <= props
    assert "flow-unit-store" not in props
