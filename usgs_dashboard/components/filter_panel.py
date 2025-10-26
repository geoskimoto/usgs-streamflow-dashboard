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
    
    def create_filter_panel(self) -> dbc.Card:
        """Create simplified, reliable filter panel."""
        
        return dbc.Card([
            dbc.CardHeader([
                html.H5("🔍 Site Filters", className="mb-0"),
                html.Small(id="filter-summary-text", className="text-muted")
            ]),
            dbc.CardBody([
                
                # Search Box
                html.Div([
                    html.Label("🔍 Search Sites:", className="fw-bold mb-2"),
                    dbc.InputGroup([
                        dcc.Input(
                            id="search-input",
                            type="text",
                            placeholder="Search by Site ID or Station Name...",
                            className="form-control",
                            style={'height': '38px'}
                        ),
                        dbc.Button("✕", id="clear-search", color="outline-secondary", size="sm")
                    ], className="mb-3")
                ]),
                
                # Real-time Data Filter
                html.Div([
                    html.Div([
                        html.Label("📊 Real-time Data:", className="fw-bold mb-2"),
                        html.Div([
                            dbc.Switch(
                                id="realtime-filter",
                                label="Show only stations with real-time data",
                                value=False,
                                className="mb-2"
                            ),
                            html.Small(
                                id="realtime-filter-info",
                                className="text-muted d-block",
                                children="Stations with enhanced visualizations (15-min data overlays)"
                            )
                        ])
                    ], className="mb-3")
                ]),
                
                # State Filter
                html.Div([
                    html.Label("States:", className="fw-bold"),
                    dbc.Checklist(
                        id="state-filter",
                        options=[],  # Will be populated dynamically
                        value=["OR", "WA", "ID"],
                        inline=True,
                        className="mb-3"
                    )
                ]),
                
                # Drainage Area Filter
                html.Div([
                    html.Label("Drainage Area (sq mi):", className="fw-bold"),
                    html.Div(id="drainage-area-display", className="mb-2 small text-muted"),
                    dcc.RangeSlider(
                        id="drainage-area-filter",
                        min=0, max=90000, step=1000,
                        value=[0, 90000],
                        marks={
                            0: {'label': '0', 'style': {'fontSize': '10px'}},
                            10000: {'label': '10K', 'style': {'fontSize': '10px'}},
                            25000: {'label': '25K', 'style': {'fontSize': '10px'}},
                            50000: {'label': '50K', 'style': {'fontSize': '10px'}},
                            90000: {'label': '90K', 'style': {'fontSize': '10px'}}
                        },
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], className="mb-3"),
                
                # Basin Filter
                html.Div([
                    html.Label("River Basin:", className="fw-bold"),
                    dcc.Dropdown(
                        id="basin-filter",
                        options=[],  # Will be populated from data
                        value=[],
                        multi=True,
                        placeholder="Select basins (optional)",
                        className="mb-3"
                    )
                ]),
                
                # HUC Code Filter
                html.Div([
                    html.Label("HUC Code (Watershed):", className="fw-bold"),
                    dcc.Dropdown(
                        id="huc-filter",
                        options=[],  # Will be populated from data
                        value=[],
                        multi=True,
                        placeholder="Select HUC codes (optional)",
                        className="mb-3"
                    )
                ]),
                
                # Results Summary
                html.Hr(),
                html.Div([
                    html.Strong(id="results-count", children="Loading..."),
                    html.Div(id="filter-summary", className="small text-muted mt-1")
                ])
            ])
        ], className="h-100", style={'maxHeight': '85vh', 'overflowY': 'auto'})
    
    def create_filter_status_bar(self) -> html.Div:
        """Create a compact status bar showing current filters."""
        return html.Div([
            html.Strong(id="results-count", children="Loading..."),
            html.Span(" | ", className="mx-2 text-muted"),
            html.Span(id="filter-status-text", className="small text-muted")
        ], className="mb-2")


# Create global instance
filter_component = SimplifiedFilterPanel()
