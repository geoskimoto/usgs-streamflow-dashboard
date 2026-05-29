"""Verify viz_manager create_streamflow_plot accepts precip_runoff_data."""
import pandas as pd
import plotly.graph_objects as go
from unittest.mock import patch, MagicMock


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


def test_create_streamflow_plot_accepts_precip_data():
    """create_streamflow_plot should accept precip_runoff_data kwarg without error."""
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    # Calling with precip_runoff_data should not raise TypeError
    # Use a minimal call that bypasses data fetching
    with patch.object(vm, '_add_precip_overlay', return_value=go.Figure()) as mock_overlay:
        try:
            # We expect TypeError only if the signature doesn't accept the kwarg
            import inspect
            sig = inspect.signature(vm.create_streamflow_plot)
            assert 'precip_runoff_data' in sig.parameters, \
                "create_streamflow_plot must accept precip_runoff_data parameter"
        except Exception as e:
            assert False, f"Unexpected error: {e}"


def test_create_fast_water_year_plot_accepts_precip_data():
    """create_fast_water_year_plot should accept precip_runoff_data kwarg."""
    from usgs_dashboard.components.viz_manager import VisualizationManager
    vm = VisualizationManager()
    import inspect
    sig = inspect.signature(vm.create_fast_water_year_plot)
    assert 'precip_runoff_data' in sig.parameters, \
        "create_fast_water_year_plot must accept precip_runoff_data parameter"
