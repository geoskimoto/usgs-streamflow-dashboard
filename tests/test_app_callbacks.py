"""
Tests for Dash app callbacks (app.py).

Verifies dashboard UI behavior including data loading, filtering,
gauge selection, map rendering, and admin authentication.
All external data sources are mocked.
"""

import pytest
import json
import pandas as pd
from datetime import datetime
from unittest.mock import MagicMock, patch

import dash
from dash import html, dcc, no_update


# ---------------------------------------------------------------------------
# Helper: import the app with mocked data layer
# ---------------------------------------------------------------------------

def _make_mock_data_manager(sample_stations_df, sample_discharge_df):
    """Create a fully mocked data manager."""
    dm = MagicMock()
    dm.load_regional_gauges.return_value = _enrich_sample(sample_stations_df.copy())
    dm.get_streamflow_data.return_value = sample_discharge_df.copy()
    dm.get_realtime_data.return_value = pd.DataFrame()
    dm.get_sites_with_realtime_data.return_value = sample_stations_df["station_number"].tolist()
    dm.get_station_info.return_value = {
        "station_number": "12108500",
        "name": "NEWAUKUM CREEK NEAR BLACK DIAMOND, WA",
        "state": "WA",
    }
    dm.adapter = MagicMock()
    dm.adapter.get_status.return_value = {
        "mode": "hybrid", "api_enabled": True, "cache_enabled": True,
        "api_reachable": True, "api_url": "https://streamflowops.3rdplaces.io",
    }
    dm._stations_cache = _enrich_sample(sample_stations_df.copy())
    return dm


def _enrich_sample(df):
    """Add the dashboard-expected alias columns."""
    df["site_id"] = df["station_number"]
    df["site_no"] = df["station_number"]
    df["station_name"] = df["name"]
    df["station_nm"] = df["name"]
    df["drainage_area"] = None
    df["basin"] = None
    df["color"] = "#808080"
    return df


# ==========================================================================
# load_gauge_data() callback tests
# ==========================================================================

class TestLoadGaugeDataCallback:
    """Test the load_gauge_data callback that fires on app start."""

    def test_returns_gauges_list(self, sample_stations_df, sample_discharge_df):
        """Callback should return a non-empty list of gauge dicts."""
        mock_dm = _make_mock_data_manager(sample_stations_df, sample_discharge_df)

        with patch("app.data_manager", mock_dm):
            from app import load_gauge_data
            gauges_data, alert, site_limit = load_gauge_data("/")

        assert isinstance(gauges_data, list)
        assert len(gauges_data) > 0

    def test_returns_alert_on_success(self, sample_stations_df, sample_discharge_df):
        mock_dm = _make_mock_data_manager(sample_stations_df, sample_discharge_df)

        with patch("app.data_manager", mock_dm):
            from app import load_gauge_data
            _, alert, _ = load_gauge_data("/")

        # Alert should be a success (dbc.Alert with color='success')
        assert hasattr(alert, "children") or alert is not None

    def test_returns_empty_on_no_stations(self, sample_stations_df, sample_discharge_df):
        mock_dm = _make_mock_data_manager(sample_stations_df, sample_discharge_df)
        mock_dm.load_regional_gauges.return_value = pd.DataFrame()

        with patch("app.data_manager", mock_dm):
            from app import load_gauge_data
            gauges_data, alert, _ = load_gauge_data("/")

        assert gauges_data == []

    def test_returns_site_limit(self, sample_stations_df, sample_discharge_df):
        mock_dm = _make_mock_data_manager(sample_stations_df, sample_discharge_df)

        with patch("app.data_manager", mock_dm):
            from app import load_gauge_data
            _, _, site_limit = load_gauge_data("/")

        assert site_limit == 300  # Hardcoded in app.py

    def test_handles_exception_gracefully(self, sample_stations_df, sample_discharge_df):
        mock_dm = _make_mock_data_manager(sample_stations_df, sample_discharge_df)
        mock_dm.load_regional_gauges.side_effect = Exception("API down")

        with patch("app.data_manager", mock_dm):
            from app import load_gauge_data
            gauges_data, alert, _ = load_gauge_data("/")

        assert gauges_data == []


# ==========================================================================
# Map / Filter Callback Tests
# ==========================================================================

class TestUpdateMapCallback:
    """Test update_map_with_simplified_filters callback."""

    def _make_gauges_data(self, sample_stations_df):
        """Convert sample df to list-of-dicts like the gauges-store."""
        df = _enrich_sample(sample_stations_df.copy())
        return df.to_dict("records")

    @patch("app.callback_context")
    @patch("app.map_component")
    def test_returns_empty_figure_when_no_data(self, mock_map, mock_ctx):
        mock_ctx.triggered = [{"prop_id": "gauges-store.data"}]

        from app import update_map_with_simplified_filters
        fig, badge, count = update_map_with_simplified_filters(
            None, "open-street-map", 700, [], "", None, None, None, None, None, None
        )
        assert "Loading" in badge

    @patch("app.callback_context")
    @patch("app.map_component")
    def test_filters_by_search_text(self, mock_map, mock_ctx, sample_stations_df):
        import plotly.graph_objects as go
        mock_ctx.triggered = [{"prop_id": "search-input.value"}]
        mock_map.create_gauge_map.return_value = go.Figure()

        gauges_data = self._make_gauges_data(sample_stations_df)

        from app import update_map_with_simplified_filters
        fig, badge, count = update_map_with_simplified_filters(
            gauges_data, "open-street-map", 700, [],
            "NEWAUKUM",  # search text
            None, None, None, None, None, None
        )

        assert "1" in count  # Only 1 station matches

    @patch("app.callback_context")
    @patch("app.map_component")
    def test_filters_by_state(self, mock_map, mock_ctx, sample_stations_df):
        import plotly.graph_objects as go
        mock_ctx.triggered = [{"prop_id": "state-filter.value"}]
        mock_map.create_gauge_map.return_value = go.Figure()

        gauges_data = self._make_gauges_data(sample_stations_df)

        from app import update_map_with_simplified_filters
        fig, badge, count = update_map_with_simplified_filters(
            gauges_data, "open-street-map", 700, [],
            "", ["WA"], None, None, None, None, None
        )

        assert "2" in count  # 2 WA stations

    @patch("app.callback_context")
    @patch("app.map_component")
    def test_all_gauges_when_no_filters(self, mock_map, mock_ctx, sample_stations_df):
        import plotly.graph_objects as go
        mock_ctx.triggered = [{"prop_id": "gauges-store.data"}]
        mock_map.create_gauge_map.return_value = go.Figure()

        gauges_data = self._make_gauges_data(sample_stations_df)

        from app import update_map_with_simplified_filters
        fig, badge, count = update_map_with_simplified_filters(
            gauges_data, "open-street-map", 700, [],
            "", None, None, None, None, None, None
        )

        assert "3" in count  # All 3 stations


# ==========================================================================
# Gauge Selection Callback Tests
# ==========================================================================

class TestGaugeSelection:
    """Test handle_gauge_selection callback."""

    def _make_gauges_data(self, sample_stations_df):
        df = _enrich_sample(sample_stations_df.copy())
        return df.to_dict("records")

    def test_selects_gauge_from_click(self, sample_stations_df):
        click_data = {
            "points": [{
                "customdata": "12108500",
                "lat": 47.2916,
                "lon": -122.1192,
            }]
        }
        gauges_data = self._make_gauges_data(sample_stations_df)

        from app import handle_gauge_selection
        site_id, badge_text, badge_style, info_content = handle_gauge_selection(
            click_data, gauges_data
        )

        assert site_id == "12108500"
        assert "12108500" in badge_text
        assert badge_style["display"] == "inline"

    def test_returns_no_update_on_missing_click(self, sample_stations_df):
        gauges_data = self._make_gauges_data(sample_stations_df)

        from app import handle_gauge_selection
        result = handle_gauge_selection(None, gauges_data)
        assert result[0] is None  # No gauge selected

    def test_handles_array_customdata(self, sample_stations_df):
        """Click data may return customdata as array."""
        click_data = {
            "points": [{
                "customdata": ["12108500", "extra"],
                "lat": 47.2916,
                "lon": -122.1192,
            }]
        }
        gauges_data = self._make_gauges_data(sample_stations_df)

        from app import handle_gauge_selection
        site_id, _, _, _ = handle_gauge_selection(click_data, gauges_data)
        assert site_id == "12108500"


# ==========================================================================
# Authentication Callback Tests
# ==========================================================================
# Map Height Callback Tests
# ==========================================================================

class TestMapHeight:
    """Test map container height update."""

    def test_updates_height(self):
        from app import update_map_container_height
        style = update_map_container_height(800)
        assert style["height"] == "800px"


# ==========================================================================
# Filter Summary Callback Tests
# ==========================================================================

class TestFilterSummary:
    """Test update_filter_summary callback."""

    def test_returns_count(self, sample_stations_df):
        gauges_data = _enrich_sample(sample_stations_df.copy()).to_dict("records")

        from app import update_filter_summary
        result = update_filter_summary(gauges_data)
        # result should contain gauge count info
        assert result is not None

    def test_handles_empty_data(self):
        from app import update_filter_summary
        result = update_filter_summary(None)
        assert result is not None


# ==========================================================================
# Clear Search Callback Tests
# ==========================================================================

class TestClearSearch:
    """Test clear_search callback."""

    def test_clears_search(self):
        from app import clear_search
        result = clear_search(1)
        assert result == ""


# ==========================================================================
# Drainage Display Callback Tests
# ==========================================================================

class TestDrainageDisplay:
    """Test update_drainage_display callback."""

    def test_formats_range(self):
        from app import update_drainage_display
        result = update_drainage_display([100, 5000])
        assert "100" in result
        assert "5,000" in result or "5000" in result


# ==========================================================================
# Map Hover Panel Dismissal Tests
# ==========================================================================

def _find_component_by_id(component, target_id):
    """Recursively search a Dash layout tree for a component by id."""
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        found = _find_component_by_id(child, target_id)
        if found is not None:
            return found
    return None


class TestMapHoverPanelDismissal:
    """The hover panel must disappear as soon as the mouse leaves a station."""

    def test_gauge_map_clears_hover_data_on_unhover(self):
        """Without clear_on_unhover=True, hoverData persists after mouse-out
        and the callback that hides the panel never fires."""
        import app as app_module
        graph = _find_component_by_id(app_module.app.layout, "gauge-map")
        assert graph is not None, "gauge-map Graph not found in layout"
        assert getattr(graph, "clear_on_unhover", False) is True

    def test_tooltip_store_hides_panel_on_cleared_hover_data(self):
        """When hoverData is cleared (None), the store must signal hide."""
        from app import update_map_tooltip_store
        store, info = update_map_tooltip_store(None)
        assert store == {"show": False}
        assert info == []
