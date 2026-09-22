import pandas as pd
import plotly.graph_objects as go


_BLENDED_COLORS = ("#8E44AD", "#A569BD", "#BB8FCE", "#D2B4DE", "#EBDEF0")


def _make_blended_data():
    dates = pd.date_range("2026-09-22", periods=8, freq="D")
    df = pd.DataFrame({
        "datetime": dates,
        "discharge_cfs": [1000.0 + i * 25 for i in range(8)],
    })
    return [{
        "run_date": "2026-09-22",
        "model_label": "Blended",
        "model_key": "blended",
        "source": "model_blender",
        "data": df,
    }]


def test_add_blended_overlay_adds_trace():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    fig = go.Figure()
    result = vm._add_blended_overlay(fig, _make_blended_data())
    assert isinstance(result, go.Figure)
    assert len(result.data) == 1


def test_add_blended_overlay_uses_purple_color():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    fig = go.Figure()
    result = vm._add_blended_overlay(fig, _make_blended_data())
    trace_color = result.data[0].line.color
    assert trace_color in _BLENDED_COLORS


def test_add_blended_overlay_uses_dashdot_line_style():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    fig = go.Figure()
    result = vm._add_blended_overlay(fig, _make_blended_data())
    assert result.data[0].line.dash == "dashdot"


def test_add_blended_overlay_empty_returns_unchanged():
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1], y=[1], name="existing"))
    result = vm._add_blended_overlay(fig, [])
    assert len(result.data) == 1
