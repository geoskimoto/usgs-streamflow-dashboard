"""Figure builder viz_manager.create_water_year_volume_plot (R10, R11, R13-R17, empty/error).

Written BEFORE the implementation; expected to fail until it exists.

ASSUMED INTERFACES:
  VisualizationManager().create_water_year_volume_plot(site_id, vol, mode, vol_unit, dark)
    vol      : the dict returned by USGSDataManager.get_water_year_volume (see
               tests/test_water_year_volume.py docstring). Handcrafted below.
    mode     : 'cumulative' | 'daily'
    vol_unit : 'kaf' | 'cfs-days'
    dark     : bool
  Returns go.Figure. vol None / status 'empty' / 'error' => figure with no data
  traces and one friendly annotation (via _create_error_plot); no exception text.
  Observed trace is named exactly 'Observed'. X values are datetimes inside one
  reference water year (Oct 1 start); xaxis.range spans Oct 1 .. Sep 30.
  Plain-text annotation wording used: 'missing' + 'lower bound' (R10),
  'Not enough complete years for percentile bands' (R11).
"""
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

KAF = 86400.0 / 43560.0 / 1000.0
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _vm():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    return VisualizationManager()


def _vol(n_days=60, missing=0, has_bands=True, status="ok"):
    days = np.arange(1, n_days + 1)
    daily = np.linspace(100.0, 200.0, n_days)
    if missing:
        daily[5:5 + missing] = np.nan
    cum = np.cumsum(np.nan_to_num(daily))
    table = pd.DataFrame({"water_year": 2027, "day_of_wy": days,
                          "daily_cfs_days": daily, "cum_cfs_days": cum})
    d = np.arange(1, 366)
    bands = pd.DataFrame({"day_of_wy": d, "q10": 50.0 * d, "q25": 80.0 * d,
                          "q50": 100.0 * d, "q75": 120.0 * d, "q90": 150.0 * d,
                          "median": 100.0 * d})
    daily_bands = pd.DataFrame({"day_of_wy": np.arange(1, 367), "q10": 50.0, "q25": 80.0,
                                "q50": 123.0, "q75": 160.0, "q90": 190.0,
                                "mean": 130.0, "median": 123.0})
    return {"status": status, "site_id": "SITE", "current_wy": 2027, "table": table,
            "summary": pd.DataFrame(), "daily_bands": daily_bands,
            "bands": {"has_bands": has_bands, "bands": bands if has_bands else None,
                      "n_years": 12 if has_bands else 4, "excluded_years": []},
            "current_missing_days": missing}


def _build(vol=None, mode="cumulative", unit="kaf", dark=False):
    return _vm().create_water_year_volume_plot("SITE", _vol() if vol is None else vol,
                                               mode, unit, dark)


def _observed(fig):
    obs = [t for t in fig.data if t.name == "Observed"]
    assert len(obs) == 1, [t.name for t in fig.data]
    return obs[0]


def _y_title(fig):
    return fig.layout.yaxis.title.text or ""


def _hover(t):
    ht = t.hovertemplate
    return ht if isinstance(ht, str) else " ".join(map(str, ht or []))


def _annotations(fig):
    return " | ".join((a.text or "") for a in fig.layout.annotations)


def _has_y(fig, expected):
    for t in fig.data:
        y = np.asarray([v if v is not None else np.nan for v in (t.y or [])], dtype=float)
        if len(y) == len(expected) and np.allclose(y, expected, equal_nan=True):
            return True
    return False


# ---------------- basic / R17

def test_builder_returns_figure():
    assert isinstance(_build(), go.Figure)


def test_r17_observed_trace_labelled_observed_and_in_legend():
    t = _observed(_build())
    assert t.showlegend is not False


def test_r17_observed_is_visually_distinct_from_bands():
    fig = _build()
    obs = _observed(fig)
    assert not obs.fill or obs.fill == "none"
    assert (obs.line.width or 0) >= 2
    others = [t for t in fig.data if t.name != "Observed"]
    assert others, "bands expected"
    assert all((t.line.width or 0) < obs.line.width or t.line.dash not in (None, "solid")
               or t.fill not in (None, "none") for t in others)


# ---------------- R13

def test_r13_observed_spans_oct1_to_last_observed_day_only():
    t = _observed(_build(_vol(n_days=60)))
    x = pd.to_datetime(pd.Series(list(t.x)))
    assert (x.dt.month.iloc[0], x.dt.day.iloc[0]) == (10, 1)
    assert len(x) == 60
    assert (x.iloc[-1] - x.iloc[0]).days == 59


def test_r13_x_axis_covers_full_water_year_oct1_to_sep30():
    fig = _build(_vol(n_days=60))
    lo, hi = (pd.Timestamp(v) for v in fig.layout.xaxis.range)
    assert (lo.month, lo.day) == (10, 1)
    assert (hi - lo).days >= 363
    assert hi.month in (9, 10)


def test_r13_x_axis_ticks_are_not_calendar_year_labelled():
    fmt = _build().layout.xaxis.tickformat or ""
    assert "%Y" not in fmt and "%y" not in fmt


# ---------------- R14

@pytest.mark.parametrize("mode,unit,ytitle", [
    ("cumulative", "kaf", "Cumulative volume (kaf)"),
    ("cumulative", "cfs-days", "Cumulative volume (cfs-days)"),
    ("daily", "kaf", "Daily volume (kaf)"),
    ("daily", "cfs-days", "Daily volume (cfs-days)"),
])
def test_r14_axis_title_carries_mode_and_unit(mode, unit, ytitle):
    assert _y_title(_build(mode=mode, unit=unit)) == ytitle


@pytest.mark.parametrize("mode", ["cumulative", "daily"])
@pytest.mark.parametrize("unit", ["kaf", "cfs-days"])
def test_r14_hover_text_carries_unit_and_not_the_other(mode, unit):
    fig = _build(mode=mode, unit=unit)
    other = "cfs-days" if unit == "kaf" else "kaf"
    h = _hover(_observed(fig))
    assert unit in h
    for t in fig.data:
        assert other not in _hover(t)


@pytest.mark.parametrize("mode,unit", [("cumulative", "kaf"), ("daily", "cfs-days")])
def test_r14_figure_title_reflects_mode_and_unit(mode, unit):
    title = (_build(mode=mode, unit=unit).layout.title.text or "").lower()
    assert mode in title and unit in title


# ---------------- values / scaling (R1/R12 at the display boundary)

def test_cumulative_kaf_values_are_cfs_days_times_factor():
    v = _vol()
    t = _observed(_build(v, "cumulative", "kaf"))
    np.testing.assert_allclose(np.asarray(t.y, dtype=float),
                               v["table"]["cum_cfs_days"].to_numpy() * KAF, rtol=1e-6)


def test_cumulative_cfs_days_values_are_unscaled():
    v = _vol()
    t = _observed(_build(v, "cumulative", "cfs-days"))
    np.testing.assert_allclose(np.asarray(t.y, dtype=float),
                               v["table"]["cum_cfs_days"].to_numpy(), rtol=1e-9)


def test_cumulative_bands_are_scaled_with_the_same_factor():
    v = _vol()
    exp = v["bands"]["bands"]["q50"].to_numpy() * KAF
    assert _has_y(_build(v, "cumulative", "kaf"), exp)


def test_daily_bands_are_scaled_stats_in_kaf():
    v = _vol()
    exp = v["daily_bands"]["q50"].to_numpy() * KAF
    assert _has_y(_build(v, "daily", "kaf"), exp)


def test_daily_bands_unscaled_in_cfs_days():
    v = _vol()
    assert _has_y(_build(v, "daily", "cfs-days"), v["daily_bands"]["q50"].to_numpy())


def test_daily_observed_gap_is_a_gap_not_interpolated():
    v = _vol(missing=3)
    t = _observed(_build(v, "daily", "cfs-days"))
    y = np.asarray([np.nan if a is None else a for a in t.y], dtype=float)
    assert np.isnan(y[5:8]).all()
    assert t.connectgaps is not True


def test_cumulative_mode_has_no_daily_bands_and_daily_mode_no_cumulative_bands():
    v = _vol()
    cum_fig = _build(v, "cumulative", "cfs-days")
    day_fig = _build(v, "daily", "cfs-days")
    assert not _has_y(cum_fig, v["daily_bands"]["q50"].to_numpy())
    assert not _has_y(day_fig, v["bands"]["bands"]["q50"].to_numpy())


# ---------------- R15

@pytest.mark.parametrize("mode", ["cumulative", "daily"])
def test_r15_hover_uses_four_significant_digits(mode):
    fig = _build(mode=mode)
    for t in fig.data:
        if t.hoverinfo == "skip":
            continue
        assert re.search(r"%\{y:[^}]*\.4[rg]\}", _hover(t)), (t.name, _hover(t))


# ---------------- R16

def test_r16_light_and_dark_use_plot_theme():
    from usgs_dashboard.utils import plot_theme
    ref_l = plot_theme.apply_theme(go.Figure(), False)
    ref_d = plot_theme.apply_theme(go.Figure(), True)
    fl, fd = _build(dark=False), _build(dark=True)
    assert fl.layout.template.layout.paper_bgcolor == ref_l.layout.template.layout.paper_bgcolor
    assert fd.layout.template.layout.paper_bgcolor == ref_d.layout.template.layout.paper_bgcolor
    assert fl.layout.template.layout.paper_bgcolor != fd.layout.template.layout.paper_bgcolor


def test_r16_line_colors_come_from_colorblind_safe_theme_palette():
    from usgs_dashboard.utils.plot_theme import COLORWAY
    allowed = {c.upper() for c in COLORWAY}
    fig = _build()
    for t in fig.data:
        c = t.line.color
        if c is None:
            continue
        assert not HEX.match(c) or c.upper() in allowed, (t.name, c)
        assert HEX.match(c) or c.startswith("rgba"), (t.name, c)


# ---------------- R10 / R11 annotations

def test_r10_missing_days_in_current_year_annotated_as_lower_bound():
    fig = _build(_vol(missing=4), "cumulative", "kaf")
    text = _annotations(fig).lower()
    assert "4" in text and "missing" in text and "lower bound" in text
    _observed(fig)   # trace still renders


def test_r10_no_gap_annotation_when_complete():
    text = _annotations(_build(_vol(missing=0))).lower()
    assert "lower bound" not in text


def test_r11_insufficient_years_omits_bands_and_notes_it_but_keeps_observed():
    v = _vol(has_bands=False)
    fig = _build(v, "cumulative", "kaf")
    assert "Not enough complete years for percentile bands" in _annotations(fig)
    assert [t.name for t in fig.data] == ["Observed"]
    assert len(_observed(fig).x) == 60


def test_r11_bands_present_do_not_carry_insufficient_note():
    assert "Not enough complete years" not in _annotations(_build(_vol(has_bands=True)))


# ---------------- empty / error

@pytest.mark.parametrize("vol", [None, {"status": "empty"}, {"status": "error"}])
@pytest.mark.parametrize("mode", ["cumulative", "daily"])
def test_empty_or_error_returns_friendly_figure_without_raising(vol, mode):
    fig = _vm().create_water_year_volume_plot("SITE", vol, mode, "kaf", False)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 0
    text = _annotations(fig)
    assert text.strip()
    assert "Traceback" not in text and "Error:" not in text


def test_error_figure_message_says_could_not_load():
    fig = _vm().create_water_year_volume_plot("SITE", {"status": "error"}, "cumulative", "kaf", False)
    assert "could not load" in _annotations(fig).lower() or "couldn't be loaded" in _annotations(fig).lower()


def test_builder_does_not_mutate_input_vol():
    v = _vol()
    before = v["table"].copy()
    _build(v, "cumulative", "kaf")
    pd.testing.assert_frame_equal(v["table"], before)
