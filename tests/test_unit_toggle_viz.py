"""R6: every viz_manager figure builder labels axes/hovers in the requested unit."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

LABEL = {"cfs": "cfs", "cms": "m³/s"}
OTHER = {"cfs": "m³/s", "cms": "cfs"}


def _daily(years=6, col="discharge"):
    idx = pd.date_range("2020-10-01", periods=365 * years, freq="D")
    rng = np.random.default_rng(1)
    return pd.DataFrame({"datetime": idx, col: 100 + 50 * rng.random(len(idx)),
                         "site_no": "SITE"})


def _stats():
    d = np.arange(1, 367)
    return pd.DataFrame({"day_of_wy": d, "q03": 10.0, "q10": 20.0, "q25": 30.0,
                         "q50": 40.0, "q75": 50.0, "q90": 60.0, "q97": 70.0,
                         "mean": 42.0, "median": 40.0})


def _current():
    return pd.DataFrame({"datetime": pd.date_range("2026-10-01", periods=30),
                         "discharge": np.linspace(30, 60, 30), "site_no": "SITE"})


def _fc_list(label="M", source="x"):
    df = pd.DataFrame({"datetime": pd.date_range("2026-11-05", periods=8),
                       "discharge_cfs": np.linspace(40, 80, 8)})
    return [{"run_date": "2026-11-05", "model_label": label, "model_key": "k",
             "source": source, "data": df}]


def _vm():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    return VisualizationManager()


def _hovers(fig):
    out = []
    for t in fig.data:
        ht = getattr(t, "hovertemplate", None)
        if ht:
            out.append(ht if isinstance(ht, str) else " ".join(map(str, ht)))
    return out


def _y_titles(fig):
    titles = []
    for k in fig.layout:
        if k.startswith("yaxis"):
            t = fig.layout[k].title.text
            if t:
                titles.append(t)
    return titles


def _assert_unit(fig, unit):
    assert isinstance(fig, go.Figure)
    titles = _y_titles(fig)
    assert titles, "figure has no y-axis title"
    assert any(LABEL[unit] in t for t in titles), titles
    assert not any(OTHER[unit] in t for t in titles), titles
    for h in _hovers(fig):
        assert OTHER[unit] not in h, h
    # hover templates that mention a unit at all must use the requested one
    hs = [h for h in _hovers(fig) if "cfs" in h.lower() or "m³/s" in h]
    for h in hs:
        assert LABEL[unit] in h


def _build_fast(vm, unit):
    return vm.create_fast_water_year_plot("SITE", _current(), _stats(), unit=unit)


def _build_fast_with_overlays(vm, unit):
    return vm.create_fast_water_year_plot(
        "SITE", _current(), _stats(),
        resid_cast_data=_fc_list("R"), precip_runoff_data=_fc_list("E"),
        blended_data=_fc_list("B"), unit=unit)


def _build_streamflow_all(vm, unit):
    return vm.create_streamflow_plot("SITE", _daily(), history_mode="all", unit=unit)


def _build_streamflow_30(vm, unit):
    return vm.create_streamflow_plot("SITE", _daily(), history_mode="30yr", unit=unit)


def _build_fallback(vm, unit):
    return vm._create_fallback_plot("SITE", _daily(), "water_year", [], unit=unit)


def _build_basic_wy(vm, unit):
    return vm._create_basic_water_year_plot(_daily(), "discharge", [], unit=unit)


def _build_enhanced_wy(vm, unit):
    return vm._create_enhanced_water_year_plot(_daily(), "discharge", [], unit=unit)


def _build_basic_ts(vm, unit):
    return vm._create_basic_timeseries_plot(_daily().set_index("datetime"), "discharge", unit=unit)


def _build_comparison(vm, unit):
    return vm.create_gauge_comparison_plot({"A": _daily(), "B": _daily()}, unit=unit)


def _build_fdc(vm, unit):
    return vm.create_flow_duration_curve("SITE", _daily(), unit=unit)


BUILDERS = {
    "fast_water_year": _build_fast,
    "fast_water_year_overlays": _build_fast_with_overlays,
    "streamflow_all": _build_streamflow_all,
    "streamflow_30yr": _build_streamflow_30,
    "fallback": _build_fallback,
    "basic_water_year": _build_basic_wy,
    "enhanced_water_year": _build_enhanced_wy,
    "basic_timeseries": _build_basic_ts,
    "gauge_comparison": _build_comparison,
    "flow_duration_curve": _build_fdc,
}


@pytest.mark.parametrize("unit", ["cfs", "cms"])
@pytest.mark.parametrize("name", list(BUILDERS))
def test_builder_axis_title_and_hovers_use_requested_unit(name, unit):
    fig = BUILDERS[name](_vm(), unit)
    _assert_unit(fig, unit)


@pytest.mark.parametrize("name", list(BUILDERS))
def test_builder_default_unit_is_cfs(name):
    """Calling without unit= must not fail on the signature and must label cfs."""
    import inspect
    vm = _vm()
    builder_name = {
        "fast_water_year": "create_fast_water_year_plot",
        "fast_water_year_overlays": "create_fast_water_year_plot",
        "streamflow_all": "create_streamflow_plot",
        "streamflow_30yr": "create_streamflow_plot",
        "fallback": "_create_fallback_plot",
        "basic_water_year": "_create_basic_water_year_plot",
        "enhanced_water_year": "_create_enhanced_water_year_plot",
        "basic_timeseries": "_create_basic_timeseries_plot",
        "gauge_comparison": "create_gauge_comparison_plot",
        "flow_duration_curve": "create_flow_duration_curve",
    }[name]
    p = inspect.signature(getattr(vm, builder_name)).parameters
    assert "unit" in p and p["unit"].default == "cfs"


def test_every_figure_returning_public_builder_is_covered():
    """Guard: a new create_* builder must be added to BUILDERS (and take unit=)."""
    import inspect
    from usgs_dashboard.components.viz_manager import VisualizationManager
    covered = {"create_fast_water_year_plot", "create_streamflow_plot",
               "create_gauge_comparison_plot", "create_flow_duration_curve"}
    public = {n for n, f in inspect.getmembers(VisualizationManager, inspect.isfunction)
              if n.startswith("create_")}
    assert public <= covered, f"uncovered builders: {public - covered}"


def test_fast_plot_has_yaxis_title_even_in_cfs():
    """Spec: create_fast_water_year_plot previously set no y-axis title."""
    fig = _vm().create_fast_water_year_plot("SITE", _current(), _stats())
    assert any("Discharge (cfs)" == t or "(cfs)" in t for t in _y_titles(fig))


def test_cms_figure_values_are_not_rescaled_by_builder():
    """Builders plot what they are given (conversion happens in data layer)."""
    cur = _current()
    fig = _vm().create_fast_water_year_plot("SITE", cur, _stats(), unit="cms")
    ys = np.concatenate([np.asarray(t.y, dtype=float) for t in fig.data
                         if getattr(t, "y", None) is not None and len(t.y)])
    assert np.nanmax(ys) <= 70.0 + 1e-9  # input maxima: stats q97=70, current<=60


# ---------------- overlays ----------------

@pytest.mark.parametrize("unit", ["cfs", "cms"])
@pytest.mark.parametrize("method,arg", [
    ("_add_resid_cast_overlay", "resid"),
    ("_add_precip_overlay", "precip"),
    ("_add_blended_overlay", "blended"),
])
def test_overlay_hovers_use_requested_unit(method, arg, unit):
    fig = getattr(_vm(), method)(go.Figure(), _fc_list(), unit=unit)
    assert len(fig.data) >= 1
    for h in _hovers(fig):
        assert OTHER[unit] not in h
    assert any(LABEL[unit] in h for h in _hovers(fig))


@pytest.mark.parametrize("unit", ["cfs", "cms"])
def test_nwrfc_forecast_overlay_hovers_use_requested_unit(unit):
    df = pd.DataFrame({"datetime": pd.date_range("2026-11-05", periods=8),
                       "discharge_cfs": np.linspace(40, 80, 8)})
    fig = _vm()._add_forecast_overlay(go.Figure(), df, unit=unit)
    for h in _hovers(fig):
        assert OTHER[unit] not in h


@pytest.mark.parametrize("unit", ["cfs", "cms"])
def test_realtime_overlay_hovers_use_requested_unit(unit):
    rt = pd.DataFrame({"datetime": pd.date_range("2026-11-12", periods=10, freq="15min"),
                       "discharge": np.linspace(1, 2, 10)})
    fig = _vm()._add_realtime_overlay(go.Figure(), rt, "SITE", unit=unit)
    for h in _hovers(fig):
        assert OTHER[unit] not in h
