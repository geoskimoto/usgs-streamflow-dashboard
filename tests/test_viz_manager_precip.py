import pandas as pd
import plotly.graph_objects as go


def _make_precip_data():
    dates = pd.date_range("2026-05-30", periods=14, freq="D")
    df = pd.DataFrame({
        "datetime": dates,
        "discharge_cfs": [1000.0 + i * 50 for i in range(14)],
    })
    return [{
        "run_date": "2026-05-29",
        "model_label": "EA-LSTM",
        "model_key": "ealstm/precip_runoff",
        "source": "precip_runoff",
        "data": df,
    }]


def test_add_precip_overlay_adds_trace():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    fig = go.Figure()
    result = vm._add_precip_overlay(fig, _make_precip_data())
    assert isinstance(result, go.Figure)
    assert len(result.data) == 1


def test_add_precip_overlay_uses_amber_color():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    fig = go.Figure()
    result = vm._add_precip_overlay(fig, _make_precip_data())
    trace_color = result.data[0].line.color
    assert trace_color in ("#E67E22", "#F0A500", "#F5C842", "#F7D98B", "#FBF3D0")


def test_add_precip_overlay_empty_returns_unchanged():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1], y=[1], name="existing"))
    result = vm._add_precip_overlay(fig, [])
    assert len(result.data) == 1
