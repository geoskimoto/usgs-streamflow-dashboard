"""resid-cast selection mode: one composite forecast per corrected station.

resid-cast's runner now stores a single forecast per corrected station
(model_name "selection", residual_type "composite"); stations it does not correct
get no rows in new runs (raw NWRFC served).
"""

from unittest.mock import MagicMock, patch

import pandas as pd


def _row(run_id, d, value):
    r = MagicMock()
    r.run_id, r.run_status = run_id, "complete"
    r.model_name, r.residual_type, r.is_general = "selection", "composite", False
    r.issued_at = pd.Timestamp("2026-10-01").to_pydatetime()
    r.lead_date, r.corrected_value_cfs = f"2026-10-{1 + d:02d}", value
    return r


def _db_client(rows):
    with patch("resid_cast.resid_cast_db_client.create_engine"), \
         patch("resid_cast.resid_cast_db_client.sessionmaker") as mock_sm:
        session = MagicMock()
        session.execute.return_value.fetchall.return_value = rows
        mock_sm.return_value.return_value = session
        from resid_cast.resid_cast_db_client import ResidCastDbClient
        client = ResidCastDbClient(db_url="postgresql://x:y@localhost/db")
        client._Session = mock_sm.return_value
        return client


def test_composite_has_a_label():
    from resid_cast.resid_cast_api_client import model_label
    assert model_label("selection/composite") == "ResidCast"


def test_db_client_returns_composite_forecast():
    client = _db_client([_row(7, d, 100.0 + d) for d in range(8)])
    out = client.get_forecasts("ABOM8", allowed_variants=["selection/composite"])
    assert len(out) == 1
    assert out[0]["model_key"] == "selection/composite" and out[0]["model_label"] == "ResidCast"
    assert len(out[0]["data"]) == 8


def test_query_ranks_latest_runs_not_latest_runs_with_rows():
    """A station resid-cast stops correcting must not keep showing old corrections."""
    from resid_cast.resid_cast_db_client import _FORECASTS_QUERY
    sql = " ".join(str(_FORECASTS_QUERY).split())
    assert "FROM forecast_runs ORDER BY id DESC LIMIT :num_runs" in sql
    assert "ROW_NUMBER" not in sql


def test_corrected_station_ids_are_stations_with_models():
    with patch("usgs_dashboard.data.data_manager.get_adapter") as mock_ga:
        mock_ga.return_value = MagicMock(mode="api", api_enabled=True, cache_enabled=False)
        from usgs_dashboard.data.data_manager import USGSDataManager
        dm = USGSDataManager()
        dm._resid_cast = MagicMock(_config={
            "111": {"nwrfc_id": "AAAA1", "models": ["selection/composite"]},
            "222": {"nwrfc_id": "BBBB1", "models": [], "ealstm_available": True},
        })
        assert dm.get_resid_cast_perstation_ids() == {"111"}


def test_composite_trace_is_solid_and_visible():
    import plotly.graph_objects as go
    from usgs_dashboard.components.viz_manager import VisualizationManager
    df = pd.DataFrame({"datetime": pd.to_datetime(["2026-10-01", "2026-10-02"]), "discharge_cfs": [100.0, 110.0]})
    fig = VisualizationManager()._add_resid_cast_overlay(go.Figure(), [
        {"run_date": "2026-10-01", "model_label": "ResidCast", "model_key": "selection/composite",
         "source": "resid_cast", "data": df}])
    assert len(fig.data) == 1
    assert fig.data[0].line.dash == "solid" and fig.data[0].visible is True
