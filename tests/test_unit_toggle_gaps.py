"""R10 (docs/UNIT_TOGGLE_PLAN.md addendum): review gaps for the unit toggle. Mocked only."""
import copy
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

CFS_PER_CMS = 35.3146667


@pytest.fixture
def dm(tmp_path):
    with patch("usgs_dashboard.data.data_manager.get_adapter") as ga:
        ga.return_value = MagicMock()
        from usgs_dashboard.data.data_manager import USGSDataManager
        return USGSDataManager(cache_dir=str(tmp_path / "dm"))


def _DM():
    from usgs_dashboard.data.data_manager import USGSDataManager
    return USGSDataManager


def _run(extra=None):
    df = pd.DataFrame({
        "datetime": pd.date_range("2026-11-05", periods=4),
        "discharge_cfs": [100.0, 200.0, np.nan, 400.0],
        "label": ["a", "b", "c", "d"],
    })
    if extra:
        for k, v in extra.items():
            df[k] = v
    return {"run_date": "2026-11-05", "model_label": "M", "model_key": "k",
            "source": "s", "data": df}


# ---------------- convert_forecast_runs ----------------

@pytest.mark.parametrize("unit", ["cfs", "CFS"])
def test_convert_runs_cfs_returns_runs_unchanged(unit):
    runs = [_run()]
    out = _DM().convert_forecast_runs(runs, unit)
    assert out is runs or out == runs or (out[0]["data"].equals(runs[0]["data"]))


def test_convert_runs_cms_divides_flow_columns():
    runs = [_run()]
    out = _DM().convert_forecast_runs(runs, "cms")
    np.testing.assert_allclose(out[0]["data"]["discharge_cfs"].to_numpy(),
                               runs[0]["data"]["discharge_cfs"].to_numpy() / CFS_PER_CMS,
                               rtol=1e-9, equal_nan=True)


def test_convert_runs_cms_converts_every_flow_named_numeric_column_only():
    runs = [_run({"flow_x": 10.0, "Discharge_raw": 20.0, "other": 5.0})]
    out = _DM().convert_forecast_runs(runs, "cms")[0]["data"]
    assert out["flow_x"].iloc[0] == pytest.approx(10.0 / CFS_PER_CMS)
    assert out["Discharge_raw"].iloc[0] == pytest.approx(20.0 / CFS_PER_CMS)
    assert out["other"].iloc[0] == 5.0
    assert out["label"].tolist() == ["a", "b", "c", "d"]
    pd.testing.assert_series_equal(out["datetime"], runs[0]["data"]["datetime"])


def test_convert_runs_cms_preserves_nan_gap():
    out = _DM().convert_forecast_runs([_run()], "cms")[0]["data"]
    assert out["discharge_cfs"].isna().tolist() == [False, False, True, False]


def test_convert_runs_cms_does_not_mutate_inputs():
    runs = [_run()]
    snapshot = copy.deepcopy(runs)
    original_df = runs[0]["data"]
    out = _DM().convert_forecast_runs(runs, "cms")
    assert out is not runs and out[0] is not runs[0]
    assert runs[0]["data"] is original_df
    pd.testing.assert_frame_equal(runs[0]["data"], snapshot[0]["data"])
    assert set(runs[0]) == set(snapshot[0])
    assert out[0]["data"] is not original_df


def test_convert_runs_cms_keeps_metadata_keys():
    out = _DM().convert_forecast_runs([_run()], "cms")[0]
    for k in ("run_date", "model_label"):
        assert out[k] == _run()[k]


@pytest.mark.parametrize("runs", [None, []])
def test_convert_runs_empty_or_none_passthrough(runs):
    assert _DM().convert_forecast_runs(runs, "cms") == runs


@pytest.mark.parametrize("data", [pd.DataFrame(), None, "not a frame", [1, 2]])
def test_convert_runs_bad_or_empty_data_passthrough(data):
    run = {"run_date": "2026-11-05", "model_label": "M", "data": data}
    out = _DM().convert_forecast_runs([run], "cms")
    assert len(out) == 1
    assert out[0]["run_date"] == "2026-11-05" and out[0]["model_label"] == "M"
    d = out[0]["data"]
    if isinstance(data, pd.DataFrame):
        assert d.empty
    else:
        assert d == data


# ---------------- getters apply conversion ----------------

def _first_val(runs):
    return runs[0]["data"]["discharge_cfs"].iloc[0]


def test_get_resid_cast_forecasts_applies_conversion(dm):
    dm._resid_cast = MagicMock()
    dm._resid_cast.get_forecasts.return_value = [_run()]
    assert _first_val(dm.get_resid_cast_forecasts("S", display_unit="cms")) == pytest.approx(100 / CFS_PER_CMS)
    assert _first_val(dm.get_resid_cast_forecasts("S")) == pytest.approx(100.0)


def test_get_blended_forecasts_applies_conversion(dm):
    dm._blended_forecast = MagicMock()
    dm._blended_forecast.get_forecasts.return_value = [_run()]
    assert _first_val(dm.get_blended_forecasts("S", display_unit="cms")) == pytest.approx(100 / CFS_PER_CMS)
    assert _first_val(dm.get_blended_forecasts("S")) == pytest.approx(100.0)


def test_get_forecast_data_applies_conversion(dm):
    dm.adapter.get_forecast_data.return_value = [_run()]
    assert _first_val(dm.get_forecast_data("S", display_unit="cms")) == pytest.approx(100 / CFS_PER_CMS)


@pytest.mark.parametrize("web", [True, False])
def test_get_nwrfc_forecasts_applies_conversion(dm, web):
    dm._use_nwrfc_web = web
    dm.adapter.get_nwrfc_forecasts.return_value = [_run()]
    dm.adapter.get_forecast_data.return_value = [_run()]
    assert _first_val(dm.get_nwrfc_forecasts("S", display_unit="cms")) == pytest.approx(100 / CFS_PER_CMS)


# ---------------- realtime ----------------

def test_get_realtime_data_converts_per_row_from_unit_column(dm):
    raw = pd.DataFrame({"datetime": pd.date_range("2026-11-12", periods=3, freq="15min"),
                        "discharge": [10.0, 10.0, 353.146667],
                        "unit": ["cms", "cms", "cfs"], "site_no": "SITE"})
    dm.adapter.get_discharge_data.return_value = raw
    dm._format_realtime_data = lambda df, site_id: df.copy()  # isolate from formatting
    out = dm.get_realtime_data("SITE", display_unit="cfs")
    np.testing.assert_allclose(out["discharge"].to_numpy(),
                               [353.146667, 353.146667, 353.146667], rtol=1e-6)
    out_cms = dm.get_realtime_data("SITE", display_unit="cms")
    np.testing.assert_allclose(out_cms["discharge"].to_numpy(), [10.0, 10.0, 10.0], rtol=1e-6)


def test_get_realtime_data_default_unit_is_cfs(dm):
    import inspect
    assert inspect.signature(dm.get_realtime_data).parameters["display_unit"].default == "cfs"


def test_get_realtime_data_empty_stays_empty(dm):
    dm.adapter.get_discharge_data.return_value = pd.DataFrame()
    assert dm.get_realtime_data("SITE", display_unit="cms").empty


def _rt_mock(values):
    m = MagicMock()
    m.get_realtime_data.return_value = pd.DataFrame({
        "datetime": pd.date_range("2026-11-12", periods=len(values), freq="15min"),
        "discharge": values})
    return m


def _called_with_unit(m, unit):
    return any(c.args[:1] == ("SITE",) and c.kwargs.get("display_unit") == unit
               for c in m.get_realtime_data.call_args_list)


def _has_trace_with(fig, values):
    for t in fig.data:
        y = getattr(t, "y", None)
        if y is not None and len(y) == len(values) and np.allclose(np.asarray(y, float), values):
            return True
    return False


def _vm():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    return VisualizationManager()


def _current():
    return pd.DataFrame({"datetime": pd.date_range("2026-10-01", periods=30),
                         "discharge": np.linspace(30, 60, 30), "site_no": "SITE"})


def _stats():
    d = np.arange(1, 367)
    return pd.DataFrame({"day_of_wy": d, "q03": 10.0, "q10": 20.0, "q25": 30.0,
                         "q50": 40.0, "q75": 50.0, "q90": 60.0, "q97": 70.0,
                         "mean": 42.0, "median": 40.0})


def _daily():
    idx = pd.date_range("2020-10-01", periods=365 * 6, freq="D")
    return pd.DataFrame({"datetime": idx, "discharge": 100.0, "site_no": "SITE"})


@pytest.mark.parametrize("unit", ["cfs", "cms"])
def test_fast_plot_requests_realtime_in_display_unit_and_plots_as_given(unit):
    vals = [7771.0, 7772.0, 7773.0, 7774.0]
    m = _rt_mock(vals)
    fig = _vm().create_fast_water_year_plot("SITE", _current(), _stats(), data_manager=m, unit=unit)
    assert _called_with_unit(m, unit)
    assert _has_trace_with(fig, vals)


@pytest.mark.parametrize("unit", ["cfs", "cms"])
def test_streamflow_plot_requests_realtime_in_display_unit_and_plots_as_given(unit):
    vals = [8881.0, 8882.0, 8883.0, 8884.0]
    m = _rt_mock(vals)
    fig = _vm().create_streamflow_plot("SITE", _daily(), history_mode="all", data_manager=m, unit=unit)
    assert _called_with_unit(m, unit)
    assert _has_trace_with(fig, vals)


# ---------------- _native_unit ----------------

def _nu(df):
    return _DM()._native_unit(df)


def test_native_unit_mode():
    assert _nu(pd.DataFrame({"unit": ["cms", "cms", "cfs"]})) == "cms"


def test_native_unit_ignores_nan():
    assert _nu(pd.DataFrame({"unit": [np.nan, np.nan, "cms"]})) == "cms"


@pytest.mark.parametrize("df", [
    pd.DataFrame({"unit": [np.nan, None]}),
    pd.DataFrame({"unit": pd.Series([], dtype=object)}),
    pd.DataFrame({"x": [1]}),
    pd.DataFrame(),
])
def test_native_unit_defaults_to_cfs(df):
    assert _nu(df) == "cfs"


def test_native_unit_unknown_raises():
    with pytest.raises(ValueError):
        _nu(pd.DataFrame({"unit": ["furlongs", "furlongs"]}))


# ---------------- stats / current-year copies ----------------

def test_get_flow_statistics_returns_independent_copy(tmp_path, monkeypatch):
    from usgs_dashboard.data import stats_cache_manager as scm
    monkeypatch.setattr(scm, "STATS_CACHE_DIR", str(tmp_path / "cache"))
    with patch("usgs_dashboard.data.data_manager.get_adapter") as ga:
        ga.return_value = MagicMock()
        dm = _DM()(cache_dir=str(tmp_path / "dm"))
    end = pd.Timestamp.now().normalize()
    idx = pd.date_range(end - pd.Timedelta(days=365 * 12), end, freq="D")
    hist = pd.DataFrame({"datetime": idx, "discharge": 100.0 + (np.arange(len(idx)) % 50),
                         "unit": "cfs", "site_no": "SITE"})
    dm.get_streamflow_data = MagicMock(side_effect=lambda *a, **k: hist.copy())
    for unit in ("cfs", "cms"):
        first = dm.get_flow_statistics("SITE", display_unit=unit)
        expected = first.copy()
        first["median"] = -999.0
        first.drop(columns=["mean"], inplace=True)
        second = dm.get_flow_statistics("SITE", display_unit=unit)
        pd.testing.assert_frame_equal(second, expected)


def test_current_year_data_empty_frame_returns_empty(dm):
    dm.get_streamflow_data = MagicMock(return_value=pd.DataFrame())
    assert dm.get_current_year_data("SITE").empty


# ---------------- units helpers ----------------

@pytest.mark.parametrize("make", [
    lambda: pd.Series([1.0, 2.0, np.nan]),
    lambda: np.array([1.0, 2.0, np.nan]),
])
@pytest.mark.parametrize("unit", ["cfs", "cms"])
def test_convert_flow_same_unit_returns_equal_valued_copy(make, unit):
    from usgs_dashboard.utils.units import convert_flow
    x = make()
    out = convert_flow(x, unit, unit)
    assert out is not x
    np.testing.assert_array_equal(np.asarray(out), np.asarray(x))
    # mutating the result must not affect the input
    if isinstance(out, pd.Series):
        out.iloc[0] = -1.0
    else:
        out[0] = -1.0
    assert np.asarray(x)[0] == 1.0


def test_normalize_unit_strips_whitespace_and_case():
    from usgs_dashboard.utils.units import normalize_unit
    assert normalize_unit("  CFS ") == "cfs"


# ---------------- apply_unit_labels set_title ----------------

def test_apply_unit_labels_set_title_false_leaves_titleless_axis_alone():
    from usgs_dashboard.components.viz_manager import apply_unit_labels
    fig = go.Figure(go.Scatter(x=[1], y=[1]))
    apply_unit_labels(fig, "cms", set_title=False)
    assert not fig.layout.yaxis.title.text


def test_apply_unit_labels_set_title_true_adds_cms_title():
    from usgs_dashboard.components.viz_manager import apply_unit_labels
    fig = go.Figure(go.Scatter(x=[1], y=[1]))
    apply_unit_labels(fig, "cms", set_title=True)
    assert fig.layout.yaxis.title.text == "Discharge (m³/s)"
