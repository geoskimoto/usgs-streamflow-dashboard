"""R9 (docs/UNIT_TOGGLE_PLAN.md addendum): cms hover precision in apply_unit_labels.

In cms mode every FLOW placeholder (%{y:<fmt>f}, %{customdata[n]:<fmt>f}) becomes
`,.4r`. Not touched: %{x:..}, bare %{customdata}, unformatted %{y}. cfs mode is
byte-identical. Idempotent. Unit word replacement is word-boundary only.

R9 is not implemented yet: these tests are expected to fail until it is.
"""
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

M3S = "m³/s"
FLOW_F = re.compile(r"%\{(y|customdata\[\d+\]):[^}]*f\}")


def _apply():
    from usgs_dashboard.components.viz_manager import apply_unit_labels
    return apply_unit_labels


def _fig(*templates):
    fig = go.Figure()
    for i, t in enumerate(templates):
        fig.add_trace(go.Scatter(x=[1, 2], y=[1.0, 2.0], hovertemplate=t,
                                 customdata=[[0, 1, 2], [0, 1, 2]], name=f"t{i}"))
    return fig


def _hts(fig):
    return [t.hovertemplate for t in fig.data]


def _one(template, unit="cms"):
    return _hts(_apply()(_fig(template), unit))[0]


# ---------------- direct unit tests ----------------

@pytest.mark.parametrize("src,expected", [
    ("%{y:,.0f} cfs", f"%{{y:,.4r}} {M3S}"),
    ("%{y:.1f} cfs", f"%{{y:,.4r}} {M3S}"),
    ("%{y:,.1f} cfs", f"%{{y:,.4r}} {M3S}"),
    ("%{y:.0f} cfs", f"%{{y:,.4r}} {M3S}"),
    ("%{customdata[2]:.1f} cfs", f"%{{customdata[2]:,.4r}} {M3S}"),
    ("%{customdata[0]:,.0f} cfs", f"%{{customdata[0]:,.4r}} {M3S}"),
    ("Q: %{y:,.0f} cfs, P: %{customdata[1]:.1f} cfs",
     f"Q: %{{y:,.4r}} {M3S}, P: %{{customdata[1]:,.4r}} {M3S}"),
])
def test_cms_rewrites_flow_placeholder_to_4_sig_digits(src, expected):
    assert _one(src) == expected


def test_cms_does_not_touch_x_placeholder():
    out = _one("%{x:.1f}% exceed: %{y:,.0f} cfs")
    assert "%{x:.1f}" in out and "%{y:,.4r}" in out


def test_cms_does_not_touch_bare_customdata():
    out = _one("%{customdata}<br>%{y:,.0f} cfs")
    assert "%{customdata}" in out and "%{customdata:" not in out


def test_cms_does_not_touch_unformatted_y():
    out = _one("%{y} cfs")
    assert out == f"%{{y}} {M3S}"


def test_cms_unit_word_replacement_is_word_boundary():
    out = _one("%{y:,.0f} cfs | cfs_forecast | mcfs | cfsx")
    assert "cfs_forecast" in out and "mcfs" in out and "cfsx" in out
    assert out.startswith(f"%{{y:,.4r}} {M3S} |")


@pytest.mark.parametrize("src", [
    "%{y:,.0f} cfs", "%{y:.1f} cfs", "%{customdata[2]:.1f} cfs",
    "%{x:.1f}%<br>%{customdata}<br>%{y} cfs", "cfs_forecast %{y:,.0f}",
])
def test_cms_idempotent(src):
    once = _apply()(_fig(src), "cms")
    twice = _apply()(once, "cms")
    assert _hts(once) == _hts(twice)


@pytest.mark.parametrize("src", [
    "%{y:,.0f} cfs", "%{y:.1f} cfs", "%{customdata[2]:.1f} cfs",
    "%{x:.1f}%<br>%{customdata}<br>%{y} cfs",
])
def test_cfs_mode_hovertemplates_byte_identical(src):
    fig = _fig(src)
    before = _hts(fig)
    _apply()(fig, "cfs")
    assert _hts(fig) == before


def test_cms_multiple_traces_all_rewritten():
    out = _hts(_apply()(_fig("%{y:,.0f} cfs", "%{y:.1f} cfs"), "cms"))
    assert all("%{y:,.4r}" in h for h in out)


# ---------------- every builder / overlay ----------------

def _daily(years=6):
    idx = pd.date_range("2020-10-01", periods=365 * years, freq="D")
    rng = np.random.default_rng(1)
    return pd.DataFrame({"datetime": idx, "discharge": 100 + 50 * rng.random(len(idx)),
                         "site_no": "SITE"})


def _stats():
    d = np.arange(1, 367)
    return pd.DataFrame({"day_of_wy": d, "q03": 10.0, "q10": 20.0, "q25": 30.0,
                         "q50": 40.0, "q75": 50.0, "q90": 60.0, "q97": 70.0,
                         "mean": 42.0, "median": 40.0})


def _current():
    return pd.DataFrame({"datetime": pd.date_range("2026-10-01", periods=30),
                         "discharge": np.linspace(30, 60, 30), "site_no": "SITE"})


def _fc_list(label="M"):
    df = pd.DataFrame({"datetime": pd.date_range("2026-11-05", periods=8),
                       "discharge_cfs": np.linspace(40, 80, 8)})
    return [{"run_date": "2026-11-05", "model_label": label, "model_key": "k",
             "source": "x", "data": df}]


def _vm():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    return VisualizationManager()


BUILDERS = {
    "fast_water_year": lambda vm, u: vm.create_fast_water_year_plot("SITE", _current(), _stats(), unit=u),
    "fast_water_year_overlays": lambda vm, u: vm.create_fast_water_year_plot(
        "SITE", _current(), _stats(), resid_cast_data=_fc_list("R"),
        precip_runoff_data=_fc_list("E"), blended_data=_fc_list("B"), unit=u),
    "streamflow_all": lambda vm, u: vm.create_streamflow_plot("SITE", _daily(), history_mode="all", unit=u),
    "streamflow_30yr": lambda vm, u: vm.create_streamflow_plot("SITE", _daily(), history_mode="30yr", unit=u),
    "fallback": lambda vm, u: vm._create_fallback_plot("SITE", _daily(), "water_year", [], unit=u),
    "basic_water_year": lambda vm, u: vm._create_basic_water_year_plot(_daily(), "discharge", [], unit=u),
    "enhanced_water_year": lambda vm, u: vm._create_enhanced_water_year_plot(_daily(), "discharge", [], unit=u),
    "basic_timeseries": lambda vm, u: vm._create_basic_timeseries_plot(_daily().set_index("datetime"), "discharge", unit=u),
    "gauge_comparison": lambda vm, u: vm.create_gauge_comparison_plot({"A": _daily(), "B": _daily()}, unit=u),
    "flow_duration_curve": lambda vm, u: vm.create_flow_duration_curve("SITE", _daily(), unit=u),
    "overlay_resid": lambda vm, u: vm._add_resid_cast_overlay(go.Figure(), _fc_list(), unit=u),
    "overlay_precip": lambda vm, u: vm._add_precip_overlay(go.Figure(), _fc_list(), unit=u),
    "overlay_blended": lambda vm, u: vm._add_blended_overlay(go.Figure(), _fc_list(), unit=u),
    "overlay_nwrfc": lambda vm, u: vm._add_forecast_overlay(go.Figure(), _fc_list(), unit=u),
    "overlay_realtime": lambda vm, u: vm._add_realtime_overlay(
        go.Figure(),
        pd.DataFrame({"datetime": pd.date_range("2026-11-12", periods=10, freq="15min"),
                      "discharge": np.linspace(1, 2, 10)}), "SITE", unit=u),
}


def _expected_cms(template):
    """Spec: flow placeholders -> ,.4r ; standalone 'cfs' -> m³/s."""
    t = FLOW_F.sub(lambda m: "%{" + m.group(1) + ":,.4r}", template)
    return re.sub(r"\bcfs\b", M3S, t)


@pytest.mark.parametrize("name", list(BUILDERS))
def test_builder_cms_has_no_leftover_fixed_decimal_flow_placeholders(name):
    fig = BUILDERS[name](_vm(), "cms")
    for h in (h for h in _hts(fig) if isinstance(h, str)):
        assert not FLOW_F.search(h), h


@pytest.mark.parametrize("name", list(BUILDERS))
def test_builder_cms_hovers_equal_spec_rewrite_of_cfs_hovers(name):
    cfs = [h for h in _hts(BUILDERS[name](_vm(), "cfs")) if isinstance(h, str)]
    cms = [h for h in _hts(BUILDERS[name](_vm(), "cms")) if isinstance(h, str)]
    assert len(cfs) == len(cms)
    assert cms == [_expected_cms(h) for h in cfs]


@pytest.mark.parametrize("name", list(BUILDERS))
def test_builder_cfs_hovers_keep_fixed_decimal_formats(name):
    """cfs mode must not be rewritten: no ',.4r' anywhere."""
    fig = BUILDERS[name](_vm(), "cfs")
    for h in (h for h in _hts(fig) if isinstance(h, str)):
        assert ",.4r" not in h


def test_builders_collectively_exercise_flow_placeholders():
    """Non-vacuity guard: the cfs figures contain flow placeholders to rewrite."""
    n = sum(len(FLOW_F.findall(h)) for name in BUILDERS
            for h in _hts(BUILDERS[name](_vm(), "cfs")) if isinstance(h, str))
    assert n > 0


@pytest.mark.parametrize("name", list(BUILDERS))
def test_builder_cms_figure_is_idempotent_under_reapply(name):
    fig = BUILDERS[name](_vm(), "cms")
    before = _hts(fig)
    _apply()(fig, "cms")
    assert _hts(fig) == before
