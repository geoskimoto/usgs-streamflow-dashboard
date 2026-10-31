"""
Simplified Filter Panel for USGS Dashboard

Provides clean, reliable filtering based on available data fields.
"""

import dash_bootstrap_components as dbc
from dash import html, dcc


class SimplifiedFilterPanel:
    """Simplified, reliable filtering component for USGS dashboard."""
    
    def __init__(self):
        pass
    
    @staticmethod
    def _section(title: str, *children) -> html.Section:
        """One flat rail section: small uppercase heading, then its controls."""
        return html.Section(
            [html.H3(title, className="rail-heading"), *children],
            className="rail-section",
        )

    def create_filter_panel(self, legend=None) -> html.Div:
        """Create the filter rail: flat sections, no card stack. All control ids are unchanged.

        `legend` is an optional section placed directly under Results (the map legend).
        """

        results = self._section(
            "Results",
            html.Strong(id="results-count", children="Loading...", className="rail-results"),
            html.Div(id="filter-summary", className="rail-hint"),
            html.Small(id="filter-summary-text", className="rail-hint d-block"),
        )

        search = self._section(
            "Find a gauge",
            dbc.InputGroup([
                dcc.Input(
                    id="search-input",
                    type="text",
                    placeholder="Site ID or station name",
                    className="form-control",
                ),
                dbc.Button("\u00d7", id="clear-search", color="outline-secondary", size="sm",
                           title="Clear search", className="rail-clear"),
            ]),
        )

        # Real-time Data Filter - TEMPORARILY HIDDEN
        # Real-time data ingestion is not yet wired up. The toggle and its info
        # element stay in the tree (hidden) so the Dash callbacks wired to
        # `realtime-filter` / `realtime-filter-info` keep resolving. Remove the
        # display:none wrapper to re-enable the UI.
        realtime = html.Div([
            html.Label("Real-time data", className="rail-label"),
            dbc.Switch(
                id="realtime-filter",
                label="Show only stations with real-time data",
                value=False,
            ),
            html.Small(
                id="realtime-filter-info",
                className="rail-hint d-block",
                children="Stations with enhanced visualizations (15-min data overlays)",
            ),
        ], style={'display': 'none'})

        forecasts = self._section(
            "Forecasts",
            dbc.Switch(
                id="forecast-filter",
                label="NWRFC forecast stations",
                value=False,
            ),
            html.Small(
                id="forecast-filter-info",
                className="rail-hint d-block",
                children="Stations with NWRFC river forecast model assignments (~292)",
            ),
            dbc.Switch(
                id="resid-cast-filter",
                label="ResidCast-corrected stations",
                value=False,
            ),
            html.Small(
                className="rail-hint d-block",
                children="Served a bias-corrected ResidCast forecast (~215)",
            ),
            dbc.Switch(
                id="ealstm-filter",
                label="EA-LSTM forecast stations",
                value=False,
            ),
            html.Small(
                className="rail-hint d-block",
                children="CAMELS-overlap basins with precipitation-runoff forecasts (37 stations)",
            ),
        )

        status = self._section(
            "Station status",
            dbc.RadioItems(
                id="station-status-filter",
                options=[
                    {"label": "All", "value": "all"},
                    {"label": "Active", "value": "active"},
                    {"label": "Inactive", "value": "inactive"},
                ],
                value="active",
                className="btn-group rail-segmented",
                inputClassName="btn-check",
                labelClassName="btn btn-outline-secondary btn-sm",
                labelCheckedClassName="active",
            ),
            html.Small(
                id="station-status-info",
                className="rail-hint d-block",
                children="Active = has discharge data in the last 6 months",
            ),
        )

        region = self._section(
            "States and provinces",
            dbc.Checklist(
                id="state-filter",
                options=[],  # Populated dynamically
                value=["OR", "WA", "ID", "MT", "NV", "BC"],
                className="rail-checklist",
            ),
        )

        drainage = self._section(
            "Drainage area (sq mi)",
            html.Div(id="drainage-area-display", className="rail-hint mb-2"),
            dcc.RangeSlider(
                id="drainage-area-filter",
                min=0, max=90000, step=1000,
                value=[0, 90000],
                marks={
                    0: {'label': '0', 'style': {'fontSize': '10px'}},
                    10000: {'label': '10K', 'style': {'fontSize': '10px'}},
                    25000: {'label': '25K', 'style': {'fontSize': '10px'}},
                    50000: {'label': '50K', 'style': {'fontSize': '10px'}},
                    90000: {'label': '90K', 'style': {'fontSize': '10px'}},
                },
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        )

        watershed = self._section(
            "Watershed",
            html.Label("River basin", className="rail-label"),
            dcc.Dropdown(
                id="basin-filter",
                options=[],  # Populated from data
                value=[],
                multi=True,
                placeholder="Select basins (optional)",
                className="mb-3",
            ),
            html.Label("HUC code", className="rail-label"),
            dcc.Dropdown(
                id="huc-filter",
                options=[],  # Populated from data
                value=[],
                multi=True,
                placeholder="Select HUC codes (optional)",
            ),
        )

        return html.Div(
            [results, *([legend] if legend is not None else []), search, realtime, forecasts, status, region, drainage, watershed],
            className="filter-rail",
        )

    def create_filter_status_bar(self) -> html.Div:
        """Create a compact status bar showing current filters."""
        return html.Div([
            html.Strong(id="results-count", children="Loading..."),
            html.Span(" | ", className="mx-2 text-muted"),
            html.Span(id="filter-status-text", className="small text-muted")
        ], className="mb-2")


# Create global instance
filter_component = SimplifiedFilterPanel()
