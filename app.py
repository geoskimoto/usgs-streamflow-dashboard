"""
USGS Streamflow Dashboard

Interactive web dashboard for exploring USGS streamflow gauges 
in the Pacific Northwest (Oregon, Washington, Idaho).
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update, ALL
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Authentication imports
import flask
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import hashlib
import os

# Import dashboard components
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.components.map_component import get_map_component
from usgs_dashboard.components.viz_manager import get_visualization_manager
from usgs_dashboard.components.filter_panel import SimplifiedFilterPanel
from usgs_dashboard.utils.config import (
    APP_TITLE, APP_DESCRIPTION, GAUGE_COLORS, 
    TARGET_STATES, DEFAULT_ZOOM_LEVEL, SUBSET_CONFIG
)

# Authentication configuration
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Simple admin credentials - in production, use environment variables or secure config
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', 
    hashlib.sha256('admin123'.encode()).hexdigest())  # Default: admin123

def verify_password(username, password):
    """Verify admin credentials."""
    if username != ADMIN_USERNAME:
        return False
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    return password_hash == ADMIN_PASSWORD_HASH

# Initialize components
data_manager = get_data_manager()
map_component = get_map_component()
viz_manager = get_visualization_manager()
filter_panel = SimplifiedFilterPanel()

# Start percentile background refresh thread (fetches from StreamflowOps every 30 min)
data_manager.start_percentile_background_refresh(interval_seconds=1800)

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title=APP_TITLE,
    update_title='Loading...',
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1, shrink-to-fit=no"}
    ]
)

# Add custom CSS for responsive sidebar layout
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Sidebar base styles */
            .sidebar-col {
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
                padding: 1rem;
                overflow-y: auto;
            }

            .main-content-col {
                padding: 1rem;
                transition: all 0.3s ease-in-out;
                min-width: 0;  /* Allow shrinking */
            }

            /* Desktop: side-by-side layout */
            @media (min-width: 992px) {
                .sidebar-col {
                    min-height: 100vh;
                    flex: 0 0 auto !important;
                }
                .layout-row {
                    flex-wrap: nowrap !important;
                    display: flex !important;
                }
            }

            /* Mobile: stack and hide sidebar */
            @media (max-width: 991.98px) {
                .sidebar-col {
                    border-right: none;
                }
                .main-content-col {
                    padding: 0.5rem;
                }
            }

            /* Ensure plots scale properly */
            .plotly-graph-div {
                width: 100% !important;
                height: auto !important;
            }

            /* Card spacing */
            .main-content-col .card {
                margin-bottom: 1rem;
            }

            /* Compact date picker in map card header */
            .date-picker-compact .DateInput,
            .date-picker-compact .DateInput_input {
                font-size: 0.8rem !important;
                width: 110px !important;
                padding: 4px 6px !important;
            }
            .date-picker-compact .SingleDatePickerInput {
                border-radius: 4px;
            }

            /* Ensure responsive text on smaller screens */
            @media (max-width: 992px) {
                .sidebar-col {
                    font-size: 0.9rem;
                }
                .sidebar-col .card-header h5 {
                    font-size: 1rem;
                }
            }

            /* =============================================
               DARK MODE
               ============================================= */
            body.dark-mode {
                --bs-body-bg: #1e1e1e;
                --bs-body-bg-rgb: 30, 30, 30;
                --bs-body-color: #e0e0e0;
                --bs-border-color: #444444;
                --bs-card-bg: #2d2d2d;
                --bs-card-border-color: #444;
                background-color: #1e1e1e !important;
                color: #e0e0e0;
            }
            body.dark-mode .container-fluid,
            body.dark-mode .container { background-color: #1e1e1e; }

            body.dark-mode .sidebar-col {
                background-color: #252525 !important;
                border-right-color: #444 !important;
            }

            body.dark-mode .card {
                background-color: #2d2d2d !important;
                border-color: #444 !important;
                color: #e0e0e0 !important;
            }
            body.dark-mode .card-header {
                background-color: #252525 !important;
                border-bottom-color: #444 !important;
                color: #e0e0e0 !important;
            }
            body.dark-mode .card-body { background-color: #2d2d2d !important; color: #e0e0e0; }
            body.dark-mode .card-footer { background-color: #252525 !important; border-top-color: #444 !important; }

            body.dark-mode .form-control,
            body.dark-mode .form-select,
            body.dark-mode input[type="text"],
            body.dark-mode input[type="password"],
            body.dark-mode input[type="number"],
            body.dark-mode select,
            body.dark-mode textarea {
                background-color: #3a3a3a !important;
                border-color: #555 !important;
                color: #e0e0e0 !important;
            }
            body.dark-mode label,
            body.dark-mode .form-label,
            body.dark-mode .form-check-label { color: #cccccc; }

            /* React-Select (dcc.Dropdown) */
            body.dark-mode .Select-control { background-color: #3a3a3a !important; border-color: #555 !important; }
            body.dark-mode .Select-value-label,
            body.dark-mode .Select-placeholder,
            body.dark-mode .Select-input > input { color: #e0e0e0 !important; }
            body.dark-mode .Select-arrow { border-top-color: #aaa !important; }
            body.dark-mode .Select--single > .Select-control .Select-value { color: #e0e0e0 !important; }
            body.dark-mode .Select-menu-outer { background-color: #3a3a3a !important; border-color: #555 !important; }
            body.dark-mode .Select-option { background-color: #3a3a3a !important; color: #e0e0e0 !important; }
            body.dark-mode .Select-option.is-focused,
            body.dark-mode .Select-option:hover { background-color: #4a4a4a !important; color: #fff !important; }
            body.dark-mode .Select-option.is-selected { background-color: #2979c8 !important; color: #fff !important; }

            body.dark-mode .btn-outline-secondary { color: #aaa; border-color: #555; }
            body.dark-mode .btn-outline-secondary:hover { background-color: #3a3a3a; color: #e0e0e0; border-color: #666; }
            body.dark-mode .btn-secondary { background-color: #444; border-color: #555; color: #e0e0e0; }

            body.dark-mode .badge.bg-secondary { background-color: #555 !important; }
            body.dark-mode .badge.bg-light { background-color: #3a3a3a !important; color: #e0e0e0 !important; }

            body.dark-mode .alert-info    { background-color: #1a3a5c; border-color: #2979c8; color: #9ecbff; }
            body.dark-mode .alert-success { background-color: #0d2b14; border-color: #1a7a2c; color: #87dfa5; }
            body.dark-mode .alert-warning { background-color: #3a2a00; border-color: #b37700; color: #ffd97d; }
            body.dark-mode .alert-danger  { background-color: #2b0d0d; border-color: #7a1a1a; color: #e48787; }

            body.dark-mode .table { color: #e0e0e0; --bs-table-bg: #2d2d2d; --bs-table-striped-bg: #333; --bs-table-border-color: #444; }

            body.dark-mode .modal-content { background-color: #2d2d2d; color: #e0e0e0; border-color: #444; }
            body.dark-mode .modal-header { border-bottom-color: #444; }
            body.dark-mode .modal-footer { border-top-color: #444; }
            body.dark-mode .modal-header .btn-close { filter: invert(1) grayscale(1) brightness(2); }

            body.dark-mode hr { border-color: #444; }
            body.dark-mode .text-muted { color: #aaaaaa !important; }
            body.dark-mode .text-secondary { color: #aaaaaa !important; }
            body.dark-mode .list-group-item { background-color: #2d2d2d !important; border-color: #444 !important; color: #e0e0e0 !important; }

            body.dark-mode #site-header {
                background: linear-gradient(135deg, #1e1e1e 0%, #252525 100%) !important;
                border-color: #444 !important;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.4) !important;
            }

            body.dark-mode ::-webkit-scrollbar { background-color: #2d2d2d; width: 8px; }
            body.dark-mode ::-webkit-scrollbar-thumb { background-color: #555; border-radius: 4px; }
        </style>
    </head>
    <body>
        <script>
            /* Apply dark mode immediately on load, before React renders */
            document.documentElement.classList.add('dark-mode-init');
            document.body.classList.add('dark-mode');
        </script>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Expose the server for gunicorn
server = app.server

# Configure Flask-Login
server.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Global variables
gauges_df = pd.DataFrame()
selected_gauge_id = None


def create_header():
    """Create the application header with enhanced styling."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                # Enhanced header with gradient background and better typography
                html.Div([
                    html.H1(APP_TITLE, 
                           className="display-3 mb-2", 
                           style={
                               "fontWeight": "700",
                               "background": "linear-gradient(135deg, #1f77b4 0%, #2ca02c 100%)",
                               "webkitBackgroundClip": "text",
                               "webkitTextFillColor": "transparent",
                               "backgroundClip": "text",
                               "textAlign": "center"
                           }),
                    html.P(APP_DESCRIPTION,
                           className="lead mb-3 text-center d-none d-md-block",
                           style={
                               "fontSize": "1.1rem",
                               "color": "#6c757d",
                               "maxWidth": "800px",
                               "margin": "0 auto",
                               "lineHeight": "1.6"
                           }),
                    html.Hr(className="d-none d-md-block",
                            style={"width": "60%", "margin": "1.5rem auto", "border": "2px solid #e9ecef"}),
                ], id="site-header", style={
                    "background": "linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%)",
                    "padding": "1rem",
                    "borderRadius": "15px",
                    "boxShadow": "0 4px 6px rgba(0, 0, 0, 0.07)",
                    "border": "1px solid rgba(0, 0, 0, 0.05)",
                    "marginBottom": "1rem"
                })
            ])
        ])
    ], fluid=True)


def create_login_modal():
    """Create the login modal for admin authentication."""
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("🔐 Admin Login")),
        dbc.ModalBody([
            dbc.Form([
                dbc.Row([
                    dbc.Label("Username", html_for="login-username", width=3),
                    dbc.Col([
                        dbc.Input(
                            type="text",
                            id="login-username",
                            placeholder="Enter username",
                            className="mb-2"
                        )
                    ], width=9)
                ]),
                dbc.Row([
                    dbc.Label("Password", html_for="login-password", width=3),
                    dbc.Col([
                        dbc.Input(
                            type="password",
                            id="login-password",
                            placeholder="Enter password",
                            className="mb-2"
                        )
                    ], width=9)
                ]),
            ]),
            html.Div(id="login-feedback", className="mt-2")
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="login-cancel-btn", className="me-2", n_clicks=0),
            dbc.Button("Login", id="login-submit-btn", color="primary", n_clicks=0)
        ]),
    ],
    id="login-modal",
    is_open=False,
    centered=True,
    backdrop="static")


def create_sidebar():
    """Create the sidebar with simplified filtering and controls."""
    return dbc.Col([
        # Simplified Filter Panel
        filter_panel.create_filter_panel(),
        
        html.Br(),
        
        # Dashboard Controls
        dbc.Card([
            dbc.CardHeader(html.H5("⚙️ Dashboard Controls", className="mb-0")),
            dbc.CardBody([
                # Map controls
                html.H6("Map Settings", className="text-muted mb-2"),
                
                dbc.Label("Map Style:"),
                dcc.Dropdown(
                    id="map-style-dropdown",
                    options=[
                        {"label": "🏞️ USGS National Map", "value": "usgs-national"},
                        {"label": "🏔️ Stamen Terrain", "value": "stamen-terrain"},
                    ],
                    value="usgs-national",  # Set USGS National Map as default
                    className="mb-3"
                ),
                
                dbc.Label("Watershed Boundaries:"),
                dbc.Checklist(
                    id="basin-boundaries-checklist",
                    options=[
                        {"label": " Major Basins (HUC2)", "value": "huc2"},
                        {"label": " Sub-Regions (HUC4)", "value": "huc4"},
                        {"label": " Accounting Units (HUC6)", "value": "huc6"},
                        {"label": " Sub-Basins (HUC8)", "value": "huc8"}
                    ],
                    value=["huc2", "huc4"],  # Show HUC2 and HUC4 by default
                    inline=False,
                    className="mb-2"
                ),
                html.P("Display watershed boundaries on the map", 
                      className="small text-muted mb-3"),
                
                html.Hr(),
                
                # Visualization controls
                html.H6("Visualization Controls", className="text-muted mb-2"),
                
                dbc.Label("Years to Highlight:"),
                dbc.Input(
                    id="highlight-years-input",
                    type="text",
                    placeholder="e.g., 2025, 2024, 2023",
                    className="mb-2"
                ),
                html.P("Highlight specific years in charts (comma-separated)", 
                      className="small text-muted mb-3"),
                
                html.Hr(),
                
                # Plot size controls
                html.H6("Plot Size Controls", className="text-muted mb-2"),
                
                dbc.Label("Map Height:"),
                dcc.Dropdown(
                    id="map-height-dropdown",
                    options=[
                        {"label": "📱 Compact (500px)", "value": 500},
                        {"label": "📊 Standard (700px)", "value": 700},
                        {"label": "🖥️ Large (900px)", "value": 900},
                        {"label": "📺 Extra Large (1200px)", "value": 1200},
                    ],
                    value=700,  # Default current size
                    className="mb-3"
                ),
                
                dbc.Label("Chart Height:"),
                dcc.Dropdown(
                    id="chart-height-dropdown",
                    options=[
                        {"label": "📱 Compact (400px)", "value": 400},
                        {"label": "📊 Standard (500px)", "value": 500},
                        {"label": "🖥️ Large (600px)", "value": 600},
                        {"label": "📺 Extra Large (800px)", "value": 800},
                    ],
                    value=500,  # Default current size
                    className="mb-3"
                ),
                
                dbc.Label("Additional Options:"),
                dbc.Checklist(
                    id="plot-options-checklist",
                    options=[
                        {"label": "🔍 Enable plot zoom & pan", "value": "enable_zoom"},
                        {"label": "📱 Responsive sizing", "value": "responsive"},
                        {"label": "🖼️ Show plot toolbar", "value": "show_toolbar"},
                    ],
                    value=["enable_zoom", "show_toolbar"],  # Default options
                    className="mb-3"
                ),
            ])
        ], className="mb-3"),
        
        # Gauge information card
        dbc.Card([
            dbc.CardHeader(html.H5("📍 Selected Gauge", className="mb-0")),
            dbc.CardBody([
                html.Div(id="gauge-info-content", children=[
                    html.P("Select a gauge on the map to view details.", 
                          className="text-muted")
                ])
            ])
        ], className="mb-3"),
        
    ])  # Removed fixed width - now controlled by parent column


def create_public_sidebar():
    """Create the public sidebar without admin controls."""
    return [
        # Simplified Filter Panel
        filter_panel.create_filter_panel(),
        
        html.Br(),
        
        # Public Dashboard Controls (View-only settings)
        dbc.Card([
            dbc.CardHeader(html.H5("⚙️ Display Settings", className="mb-0")),
            dbc.CardBody([
                # Map controls
                html.H6("Map Settings", className="text-muted mb-2"),
                
                dbc.Label("Map Style:"),
                dcc.Dropdown(
                    id="map-style-dropdown",
                    options=[
                        {"label": "🏞️ USGS National Map", "value": "usgs-national"},
                        {"label": "🏔️ Stamen Terrain", "value": "stamen-terrain"},
                    ],
                    value="usgs-national",
                    className="mb-3"
                ),
                
                dbc.Label("Watershed Boundaries:"),
                dbc.Checklist(
                    id="basin-boundaries-checklist",
                    options=[
                        {"label": " Major Basins (HUC2)", "value": "huc2"},
                        {"label": " Sub-Regions (HUC4)", "value": "huc4"},
                        {"label": " Accounting Units (HUC6)", "value": "huc6"},
                        {"label": " Sub-Basins (HUC8)", "value": "huc8"}
                    ],
                    value=["huc2", "huc4"],  # Show HUC2 and HUC4 by default
                    inline=False,
                    className="mb-2"
                ),
                html.P("Display watershed boundaries on the map", 
                      className="small text-muted mb-3"),
                
                html.Hr(),
                
                # Visualization controls
                html.H6("Visualization Controls", className="text-muted mb-2"),
                
                dbc.Label("Years to Highlight:"),
                dbc.Input(
                    id="highlight-years-input",
                    type="text",
                    placeholder="e.g., 2025, 2024, 2023",
                    className="mb-2"
                ),
                html.P("Highlight specific years in charts (comma-separated)", 
                      className="small text-muted mb-3"),
                
                html.Hr(),
                
                # Plot size controls
                html.H6("Plot Size Controls", className="text-muted mb-2"),
                
                dbc.Label("Map Height:"),
                dcc.Dropdown(
                    id="map-height-dropdown",
                    options=[
                        {"label": "📱 Compact (500px)", "value": 500},
                        {"label": "📊 Standard (700px)", "value": 700},
                        {"label": "🖥️ Large (900px)", "value": 900},
                        {"label": "📺 Extra Large (1200px)", "value": 1200},
                    ],
                    value=700,
                    className="mb-3"
                ),
                
                dbc.Label("Chart Height:"),
                dcc.Dropdown(
                    id="chart-height-dropdown",
                    options=[
                        {"label": "📱 Compact (400px)", "value": 400},
                        {"label": "📊 Standard (500px)", "value": 500},
                        {"label": "🖥️ Large (600px)", "value": 600},
                        {"label": "📺 Extra Large (800px)", "value": 800},
                    ],
                    value=500,
                    className="mb-3"
                ),
                
                dbc.Label("Additional Options:"),
                dbc.Checklist(
                    id="plot-options-checklist",
                    options=[
                        {"label": "🔍 Enable plot zoom & pan", "value": "enable_zoom"},
                        {"label": "📱 Responsive sizing", "value": "responsive"},
                        {"label": "🖼️ Show plot toolbar", "value": "show_toolbar"},
                    ],
                    value=["enable_zoom", "show_toolbar"],
                    className="mb-3"
                ),
            ])
        ], className="mb-3"),
        
        # Gauge information card
        dbc.Card([
            dbc.CardHeader(html.H5("📍 Selected Gauge", className="mb-0")),
            dbc.CardBody([
                html.Div(id="gauge-info-content", children=[
                    html.P("Select a gauge on the map to view details.", 
                          className="text-muted")
                ])
            ])
        ], className="mb-3"),
    ]
def create_admin_content():
    """Create the admin panel content."""
    from dashboard_admin import create_enhanced_admin_content
    
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4("🔧 Admin Dashboard", className="mb-0"),
                    dbc.Button("🚪 Logout", id="logout-btn", color="outline-danger", size="sm", className="float-end")
                ]),
                dbc.CardBody([
                    # Enhanced Station Configuration Management
                    create_enhanced_admin_content(),
                    
                    html.Hr(),
                    
                    # System Information Section
                    html.H5("ℹ️ System Information", className="text-primary mb-3"),
                    html.Div(id="admin-system-info"),
                    
                    # Logs Section
                    html.H5("📝 Recent Activity", className="text-primary mb-3"),
                    html.Div(id="admin-activity-log"),
                    
                ])
            ])
        ], width=12)
    ])


def create_main_content():
    """Create the main content area."""
    return [
        # Status alerts
        html.Div(id="status-alerts"),
        
        # Map section
        dbc.Card([
            dbc.CardHeader(
                dbc.Row([
                    # Left: title + station count
                    dbc.Col(
                        [
                            html.Span("🗺️ ", className="fw-semibold"),
                            html.Span("Map", className="fw-semibold me-2 d-sm-none"),
                            html.Span("Streamflow Gauges Map", className="fw-semibold me-2 d-none d-sm-inline"),
                            dbc.Badge(id="gauge-count-badge", color="info", className="align-middle"),
                        ],
                        width="auto",
                        className="d-flex align-items-center",
                    ),
                    # Right: [−] date picker [+]
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Button(
                                        "−", id="prev-date-btn",
                                        color="secondary", outline=True, size="sm",
                                        title="Previous day",
                                        style={"minWidth": "32px", "minHeight": "32px"},
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    dcc.DatePickerSingle(
                                        id="percentile-date-picker",
                                        display_format="MMM D, YYYY",
                                        className="date-picker-compact",
                                    ),
                                    width="auto",
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        "+", id="next-date-btn",
                                        color="secondary", outline=True, size="sm",
                                        title="Next day",
                                        style={"minWidth": "32px", "minHeight": "32px"},
                                    ),
                                    width="auto",
                                ),
                            ],
                            align="center",
                            className="g-1 flex-nowrap",
                        ),
                        width="auto",
                    ),
                ], align="center", className="g-0 flex-nowrap justify-content-between"),
                className="py-2",
            ),
            dbc.CardBody([
                dcc.Loading(
                    id="loading-map",
                    type="default",
                    custom_spinner=html.Div(
                        className="hydro-loading-wrapper",
                        children=[
                            html.Div(
                                className="hydro-wave-container",
                                children=[html.Div(className="hydro-wave-bar") for _ in range(7)],
                            ),
                            html.Div("Loading map data…", className="hydro-loading-label"),
                        ],
                    ),
                    children=[
                        dcc.Graph(
                            id="gauge-map",
                            style={"height": "700px"},  # This will be updated dynamically
                            config={"displayModeBar": "hover", "displaylogo": False}
                        )
                    ]
                )
            ])
        ], className="mb-3"),
        
        # Multi-plot visualization section
        dbc.Card([
            dbc.CardHeader([
                html.H5("📊 Streamflow Analysis", className="mb-0 d-inline"),
                dbc.Badge(
                    id="selected-gauge-badge",
                    color="success",
                    className="float-end",
                    style={"display": "none"}
                )
            ]),
            dbc.CardBody([
                # History-load buttons (hidden until a station is selected)
                html.Div(
                    id="history-buttons-row",
                    style={"display": "none"},
                    children=[
                        html.Small(
                            "Water Year Plot shows current year + historical statistics. "
                            "Load additional history on demand:",
                            className="text-muted d-block mb-2",
                        ),
                        dbc.ButtonGroup([
                            dbc.Button(
                                "📈 Last 30 Years",
                                id="show-30yr-history-btn",
                                color="outline-primary",
                                size="sm",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "📜 Full Period of Record",
                                id="show-full-history-btn",
                                color="outline-secondary",
                                size="sm",
                                n_clicks=0,
                            ),
                            dbc.Button(
                                "↩ Current Year Only",
                                id="show-fast-plot-btn",
                                color="outline-success",
                                size="sm",
                                n_clicks=0,
                            ),
                        ], className="mb-3"),
                    ],
                ),
                dcc.Loading(
                    id="loading-multiplot",
                    type="default",
                    custom_spinner=html.Div(
                        className="hydro-loading-wrapper",
                        children=[
                            html.Div(
                                className="hydro-wave-container",
                                children=[html.Div(className="hydro-wave-bar") for _ in range(7)],
                            ),
                            html.Div("Loading streamflow data…", className="hydro-loading-label"),
                        ],
                    ),
                    children=[
                        html.Div(id="multi-plot-container", style={"maxHeight": "1200px", "overflowY": "auto"})
                    ]
                )
            ])
        ])
    ]


# Simplified layout without complex tabs - everything always exists
app.layout = dbc.Container([
    create_header(),
    
    # Navigation and control buttons
    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button("🏞️ Dashboard", id="show-dashboard-btn", color="primary", className="me-2"),
                dbc.Button("🔧 Admin", id="show-admin-btn", color="secondary"),
            ])
        ], width="auto"),
        dbc.Col([
            dbc.Button(
                "Filters",
                id="mobile-sidebar-btn",
                color="outline-primary",
                size="sm",
                className="d-lg-none me-2",
                n_clicks=0,
            ),
            dbc.ButtonGroup([
                dbc.Button(
                    "Light Mode",
                    id="dark-mode-btn",
                    color="outline-secondary",
                    size="sm",
                ),
                dbc.Button(
                    "◀️ Hide Sidebar",
                    id="sidebar-toggle-btn",
                    color="outline-secondary",
                    size="sm",
                    className="d-none d-lg-inline-block",
                ),
            ], className="float-end")
        ], width="auto")
    ], className="mb-3 d-flex justify-content-between align-items-center"),
    
    # Dashboard content (always exists, just hidden/shown)
    html.Div([
        dbc.Row([
            # Sidebar - hidden on mobile by default, visible on lg+
            dbc.Col(
                create_public_sidebar(),
                xs=12, lg=3,
                className="sidebar-col d-none d-lg-block",
                id="sidebar-col",
            ),
            # Main content - takes remaining space
            dbc.Col(
                create_main_content(),
                xs=12, lg=True,
                id="main-content-wrapper",
                className="main-content-col flex-grow-1",
                style={"minWidth": "0"}  # Allow shrinking
            )
        ], className="layout-row g-0", style={"minHeight": "100vh"})
    ], id="dashboard-content", style={"display": "block"}),
    
    # Admin content (always exists, just hidden/shown) 
    html.Div([
        create_admin_content()
    ], id="admin-content", style={"display": "none"}),
    
    # Login modal - ALWAYS exists in layout
    create_login_modal(),
    
    # Location component for URL tracking
    dcc.Location(id='url', refresh=False),
    
    # Store components for data persistence and authentication
    dcc.Store(id='dark-mode-store', data=True),  # True = dark mode (default on)
    dcc.Store(id='gauges-store'),
    dcc.Store(id='selected-gauge-store'),
    dcc.Store(id='history-mode-store', data=None),
    dcc.Store(id='streamflow-data-store'),
    dcc.Store(id='site-limit-store', data=300),
    dcc.Store(id='auth-store', data={'authenticated': False}),
    dcc.Store(id='percentile-bands-store', data={}),
    dcc.Store(id='percentile-date-range-store', data={}),
    dcc.Store(id='selected-percentile-date-store', data=None),
    dcc.Interval(
        id='percentile-refresh-interval',
        interval=30_000,   # poll every 30 seconds
        n_intervals=0,
    ),
    
    
    # Toast container for notifications
    html.Div(id='toast-container', style={
        'position': 'fixed',
        'top': '80px',
        'right': '20px',
        'zIndex': '9999',
        'width': 'min(350px, calc(100vw - 20px))'
    }),
    
], fluid=True)


# Authentication and Navigation Callbacks

@app.callback(
    [Output('dashboard-content', 'style'),
     Output('admin-content', 'style')],
    [Input('show-dashboard-btn', 'n_clicks'),
     Input('show-admin-btn', 'n_clicks'),
     Input('auth-store', 'data')],
    prevent_initial_call=False
)
def show_hide_content(dashboard_clicks, admin_clicks, auth_data):
    """Show/hide dashboard and admin content based on navigation and authentication."""
    ctx = callback_context
    
    if not ctx.triggered:
        # Default: show dashboard
        return {"display": "block"}, {"display": "none"}
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == 'show-dashboard-btn':
        return {"display": "block"}, {"display": "none"}
    
    elif trigger_id == 'show-admin-btn':
        # Check if authenticated
        if auth_data and auth_data.get('authenticated', False):
            return {"display": "none"}, {"display": "block"}
        else:
            # Not authenticated - stay on dashboard (modal will be opened by separate callback)
            return {"display": "block"}, {"display": "none"}
    
    elif trigger_id == 'auth-store':
        # Authentication state changed - if authenticated, show admin content
        if auth_data and auth_data.get('authenticated', False):
            return {"display": "none"}, {"display": "block"}
    
    # Default
    return {"display": "block"}, {"display": "none"}


@app.callback(
    [Output('login-modal', 'is_open')],
    [Input('show-admin-btn', 'n_clicks'),
     Input('login-cancel-btn', 'n_clicks'),
     Input('auth-store', 'data')],
    [State('login-modal', 'is_open'),
     State('auth-store', 'data')],
    prevent_initial_call=True
)
def toggle_login_modal(admin_clicks, cancel_clicks, auth_data_changed, is_open, current_auth):
    """Toggle the login modal."""
    ctx = callback_context
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Close modal on successful login
        if trigger_id == 'auth-store' and auth_data_changed and auth_data_changed.get('authenticated'):
            return [False]
        
        # Open modal when admin button clicked but not authenticated
        if trigger_id == 'show-admin-btn':
            if not current_auth or not current_auth.get('authenticated'):
                return [True]
        
        # Close modal on cancel
        if trigger_id == 'login-cancel-btn':
            return [False]
            
    return [is_open]


# Authentication callback
@app.callback(
    [Output('auth-store', 'data'),
     Output('login-feedback', 'children'),
     Output('login-username', 'value'),
     Output('login-password', 'value')],
    [Input('login-submit-btn', 'n_clicks')],
    [State('login-username', 'value'),
     State('login-password', 'value'),
     State('auth-store', 'data')],
    prevent_initial_call=True
)
def handle_login(login_clicks, username, password, auth_data):
    """Handle login authentication."""
    print(f"🔧 LOGIN CALLBACK TRIGGERED! clicks = {login_clicks}")
    print(f"Username: '{username}', Password: {'*' * len(password) if password else 'None'}")
    
    if login_clicks and login_clicks > 0:
        if not username or not password:
            print("❌ Missing credentials")
            return (auth_data or {'authenticated': False}, 
                    dbc.Alert("Please enter both username and password", color="warning"), 
                    username or "", password or "")
        
        print(f"🔍 Verifying credentials for user: {username}")
        if verify_password(username, password):
            print("✅ Login successful!")
            return ({'authenticated': True, 'username': username}, 
                    dbc.Alert("Login successful!", color="success"), 
                    "", "")
        else:
            print("❌ Invalid credentials")
            return (auth_data or {'authenticated': False}, 
                    dbc.Alert("Invalid username or password", color="danger"), 
                    username, "")
    
    return auth_data or {'authenticated': False}, "", username or "", password or ""


@app.callback(
    [Output('auth-store', 'data', allow_duplicate=True)],
    [Input('logout-btn', 'n_clicks')],
    prevent_initial_call=True
)
def handle_logout(logout_clicks):
    """Handle logout."""
    print(f"🚪 LOGOUT CALLBACK TRIGGERED! clicks = {logout_clicks}")
    
    if logout_clicks and logout_clicks > 0:
        print("✅ Logging out")
        return [{'authenticated': False}]
    
    return [no_update]


# Data Update Management Callbacks
# (Legacy callbacks removed - components no longer exist in layout)

# Manual job execution callbacks


# Admin Panel Callbacks
# (Legacy Admin callbacks removed - components no longer exist in layout)


# Main Dashboard Callbacks

@app.callback(
    [Output('gauges-store', 'data'),
     Output('status-alerts', 'children'),
     Output('site-limit-store', 'data')],
    [Input('url', 'pathname')],
    prevent_initial_call=False
)
def load_gauge_data(pathname):
    """Load gauge data on app start from DataOps API."""
    
    print(f"\n=== load_gauge_data CALLBACK FIRED ===")
    print(f"pathname: {pathname}")
    
    try:
        # Load all stations (no per-state cap)
        print("Loading all stations (no site limit)")
        
        # Load stations from DataOps API via data_manager
        filters_df = data_manager.load_regional_gauges()
        
        if filters_df.empty:
            print("WARNING: No stations returned from DataOps API")
            alert = dbc.Alert(
                "No gauge data available. Check DataOps API connection.",
                color="warning",
                dismissable=True
            )
            return [], alert, 0
        
        print(f"Loaded {len(filters_df)} stations from DataOps API")
        
        global gauges_df
        gauges_df = filters_df.copy()
        
        # Drop columns that can't be JSON-serialized
        if 'years_of_record' in gauges_df.columns:
            gauges_df = gauges_df.drop('years_of_record', axis=1)
        
        # Convert any remaining binary columns to None
        for col in gauges_df.columns:
            if gauges_df[col].dtype == object:
                sample = gauges_df[col].dropna().head(1)
                if len(sample) > 0 and isinstance(sample.iloc[0], bytes):
                    gauges_df[col] = None
        
        alert_msg = f"Successfully loaded {len(gauges_df)} USGS gauges from {', '.join(TARGET_STATES)}"
        if 'station_status' in gauges_df.columns:
            active_count = (gauges_df['station_status'] == 'Active').sum()
            alert_msg += f" ({active_count} active, {len(gauges_df) - active_count} inactive)"
        
        gauges_data = gauges_df.to_dict('records')
        print(f"Returning {len(gauges_data)} gauge records")
        print(f"Sample gauge: {gauges_data[0] if gauges_data else 'NONE'}")
        print("=== CALLBACK COMPLETE ===\n")
        
        alert = dbc.Alert(
            alert_msg,
            color="success",
            dismissable=True,
            duration=4000
        )
        return gauges_data, alert, len(gauges_data)
        
    except Exception as e:
        print(f"ERROR in load_gauge_data: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=== CALLBACK ERROR ===\n")
        
        alert = dbc.Alert(
            f"Error loading gauge data: {str(e)}",
            color="danger",
            dismissable=True
        )
        return [], alert, 0


# Legacy callbacks removed - UI components no longer exist


@app.callback(
    Output('percentile-bands-store', 'data'),
    Input('percentile-refresh-interval', 'n_intervals'),
    Input('selected-percentile-date-store', 'data'),
    State('percentile-bands-store', 'data'),
    prevent_initial_call=False,
)
def refresh_percentile_bands(n_intervals, selected_date, current_bands):
    """Poll cached percentile bands every 30 s. When a historical date is
    selected via the slider, fetches that date's bands on demand. Returns
    no_update when data is unchanged."""
    # Historical date selected — fetch directly (not from background cache)
    if selected_date:
        new_bands = data_manager.get_percentile_bands_for_date(selected_date)
    else:
        # Latest / default — use the background-refresh cache
        new_bands = data_manager.get_cached_percentile_bands()

    if new_bands == (current_bands or {}):
        return no_update
    return new_bands


@app.callback(
    Output('percentile-date-range-store', 'data'),
    Input('percentile-refresh-interval', 'n_intervals'),
    prevent_initial_call=False,
)
def load_percentile_date_range(n_intervals):
    """Fetch the available date range once on page load (n_intervals == 0)."""
    if n_intervals != 0:
        return no_update
    range_data = data_manager.get_percentile_date_range()
    if not range_data.get('min_date') or not range_data.get('max_date'):
        return {}
    min_d = date.fromisoformat(range_data['min_date'])
    max_d = date.fromisoformat(range_data['max_date'])
    return {
        'min_date': range_data['min_date'],
        'max_date': range_data['max_date'],
        'num_days': (max_d - min_d).days,
    }


@app.callback(
    [Output('percentile-date-picker', 'min_date_allowed'),
     Output('percentile-date-picker', 'max_date_allowed'),
     Output('percentile-date-picker', 'date'),
     Output('percentile-date-picker', 'initial_visible_month')],
    Input('percentile-date-range-store', 'data'),
    prevent_initial_call=True,
)
def init_date_picker(range_data):
    """Set picker bounds and default to the latest available date."""
    if not range_data or not range_data.get('max_date'):
        return no_update, no_update, no_update, no_update
    return (
        range_data['min_date'],
        range_data['max_date'],
        range_data['max_date'],   # default selection = latest
        range_data['max_date'],   # open calendar on latest month
    )


@app.callback(
    [Output('selected-percentile-date-store', 'data'),
     Output('percentile-date-picker', 'date', allow_duplicate=True)],
    [Input('prev-date-btn', 'n_clicks'),
     Input('next-date-btn', 'n_clicks'),
     Input('percentile-date-picker', 'date')],
    State('percentile-date-range-store', 'data'),
    prevent_initial_call=True,
)
def update_date_selection(prev_clicks, next_clicks, picker_date, range_data):
    """Handle − / + buttons and direct calendar selection.

    The date picker is always the single source of truth for what date is
    displayed. The − / + buttons shift it by one day and write back to it.
    When the selected date equals max_date, selected-percentile-date-store is
    set to None so the map uses the background-refresh cache instead of making
    an extra API call.
    """
    if not range_data or not range_data.get('max_date'):
        return no_update, no_update

    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    max_d = date.fromisoformat(range_data['max_date'])
    min_d = date.fromisoformat(range_data['min_date'])
    current = date.fromisoformat(picker_date) if picker_date else max_d

    if triggered_id == 'prev-date-btn':
        selected = max(current - timedelta(days=1), min_d)
    elif triggered_id == 'next-date-btn':
        selected = min(current + timedelta(days=1), max_d)
    elif triggered_id == 'percentile-date-picker':
        selected = current
    else:
        return no_update, no_update

    date_str = selected.isoformat()
    # Use background cache (None) when at the latest date
    store_val = None if selected >= max_d else date_str
    return store_val, date_str


@app.callback(
    [Output('gauge-map', 'figure'),
     Output('gauge-count-badge', 'children'),
     Output('results-count', 'children')],
    [Input('gauges-store', 'data'),
     Input('map-style-dropdown', 'value'),
     Input('map-height-dropdown', 'value'),
     Input('basin-boundaries-checklist', 'value'),
     Input('search-input', 'value'),
     Input('state-filter', 'value'),
     Input('drainage-area-filter', 'value'),
     Input('basin-filter', 'value'),
     Input('huc-filter', 'value'),
     Input('realtime-filter', 'value'),
     Input('station-status-filter', 'value'),
     Input('forecast-filter', 'value'),
     Input('resid-cast-filter', 'value'),
     Input('percentile-bands-store', 'data')],
    [State('selected-gauge-store', 'data')]
)
def update_map_with_simplified_filters(gauges_data, map_style, map_height, basin_boundaries, search_text, states,
                                     drainage_range, basins, hucs, show_realtime_only, station_status, show_forecast_only,
                                     show_resid_cast_only, percentile_bands, selected_gauge):
    """Update the gauge map based on simplified filters."""
    if not gauges_data:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Loading gauge data...",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=700
        )
        return empty_fig, "Loading...", "Loading..."
    
    # Check what triggered the callback - don't auto-fit bounds if just changing map style/height
    ctx = callback_context
    auto_fit = True  # Default to auto-fit
    if ctx.triggered:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        # Don't auto-fit for map style, height changes, or when map is just being built from store
        if trigger_id in ['map-style-dropdown', 'map-height-dropdown', 'gauges-store', 'percentile-bands-store']:
            auto_fit = False
    
    # Convert data to DataFrame
    all_gauges = pd.DataFrame(gauges_data)
    original_count = len(all_gauges)
    
    # Apply filters
    filtered_gauges = all_gauges.copy()
    
    # Search filter — matches USGS ID, station name, or NWRFC ID
    if search_text and search_text.strip():
        search_lower = search_text.lower().strip()
        search_filter = (
            filtered_gauges['site_id'].str.lower().str.contains(search_lower, na=False) |
            filtered_gauges['station_name'].str.lower().str.contains(search_lower, na=False)
        )
        if 'nwrfc_id' in filtered_gauges.columns:
            search_filter = search_filter | filtered_gauges['nwrfc_id'].str.lower().str.contains(search_lower, na=False)
        filtered_gauges = filtered_gauges[search_filter]
    
    # State filter (default to all if none selected)
    if states:
        filtered_gauges = filtered_gauges[filtered_gauges['state'].isin(states)]
    
    # Station status filter (Active / Inactive)
    if station_status and station_status != 'all' and 'station_status' in filtered_gauges.columns:
        if station_status == 'active':
            filtered_gauges = filtered_gauges[filtered_gauges['station_status'] == 'Active']
        elif station_status == 'inactive':
            filtered_gauges = filtered_gauges[filtered_gauges['station_status'] == 'Inactive']
    
    # Drainage area filter - only apply if not at default range [0, 90000]
    if drainage_range and len(drainage_range) == 2:
        min_area, max_area = drainage_range
        # Only filter if the user has changed from default range
        if min_area > 0 or max_area < 90000:
            # Filter for stations with drainage area in range (excluding None/NaN)
            area_filter = (
                filtered_gauges['drainage_area'].notna() &
                (filtered_gauges['drainage_area'] >= min_area) & 
                (filtered_gauges['drainage_area'] <= max_area)
            )
            filtered_gauges = filtered_gauges[area_filter]
    
    # Basin filter
    if basins:
        filtered_gauges = filtered_gauges[filtered_gauges['basin'].isin(basins)]
    
    # HUC filter
    if hucs:
        filtered_gauges = filtered_gauges[filtered_gauges['huc_code'].isin(hucs)]
    
    # Real-time data filter
    if show_realtime_only:
        try:
            realtime_sites = data_manager.get_sites_with_realtime_data()
            if realtime_sites:
                filtered_gauges = filtered_gauges[filtered_gauges['site_id'].isin(realtime_sites)]
            else:
                # No real-time sites available, return empty DataFrame
                filtered_gauges = pd.DataFrame()
        except Exception as e:
            print(f"Error filtering by real-time data: {e}")
    
    # Forecast data filter (NWRFC + ResidCast)
    if show_forecast_only:
        try:
            forecast_site_ids = data_manager.get_forecast_station_ids()
            if forecast_site_ids:
                filtered_gauges = filtered_gauges[filtered_gauges['site_id'].isin(forecast_site_ids)]
            else:
                filtered_gauges = pd.DataFrame()
        except Exception as e:
            print(f"Error filtering by forecast data: {e}")

    # ResidCast ML forecast filter
    if show_resid_cast_only:
        try:
            rc_ids = data_manager.get_resid_cast_station_ids()
            if rc_ids:
                filtered_gauges = filtered_gauges[filtered_gauges['site_id'].isin(rc_ids)]
            else:
                filtered_gauges = pd.DataFrame()
        except Exception as e:
            print(f"Error filtering by ResidCast stations: {e}")

    # Create map figure
    if len(filtered_gauges) > 0:
        fig = map_component.create_gauge_map(
            filtered_gauges,
            selected_gauge=selected_gauge,
            map_style=map_style,
            height=map_height,
            auto_fit_bounds=auto_fit,
            percentile_bands=percentile_bands or {}
        )
        
        # Add watershed boundaries if selected
        if basin_boundaries:
            show_huc2 = 'huc2' in basin_boundaries
            show_huc4 = 'huc4' in basin_boundaries
            show_huc6 = 'huc6' in basin_boundaries
            show_huc8 = 'huc8' in basin_boundaries
            fig = map_component.add_watershed_boundaries(
                fig, 
                show_huc2=show_huc2, 
                show_huc4=show_huc4,
                show_huc6=show_huc6,
                show_huc8=show_huc8,
                region='pnw'  # Pacific Northwest region
            )
    else:
        fig = go.Figure()
        fig.update_layout(
            title="No gauges match the current filters",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=700
        )
    
    # Calculate statistics
    filtered_count = len(filtered_gauges)
    gauge_badge = f"{filtered_count:,} / {original_count:,}"
    
    # Show active/inactive breakdown in results
    if 'station_status' in all_gauges.columns and filtered_count > 0:
        active_shown = (filtered_gauges['station_status'] == 'Active').sum() if 'station_status' in filtered_gauges.columns else 0
        inactive_shown = filtered_count - active_shown
        results_count = f"{filtered_count:,} sites shown ({active_shown:,} active, {inactive_shown:,} inactive)"
    else:
        results_count = f"{filtered_count:,} sites shown"
    
    return fig, gauge_badge, results_count


# Callback to update map container height dynamically
@app.callback(
    Output('gauge-map', 'style'),
    [Input('map-height-dropdown', 'value')]
)
def update_map_container_height(map_height):
    """Update the map container height based on user selection."""
    return {"height": f"{map_height}px"}


@app.callback(
    [Output('selected-gauge-store', 'data'),
     Output('selected-gauge-badge', 'children'),
     Output('selected-gauge-badge', 'style'),
     Output('gauge-info-content', 'children')],
    Input('gauge-map', 'clickData'),
    State('gauges-store', 'data')
)
def handle_gauge_selection(clickData, gauges_data):
    """Handle gauge selection from map click."""
    if not clickData or not gauges_data:
        return None, "", {"display": "none"}, html.P("Select a gauge on the map to view details.", className="text-muted")
    
    # Extract site ID from click data
    try:
        site_id = clickData['points'][0]['customdata']
        # Ensure site_id is a single string value, not an array
        if isinstance(site_id, (list, tuple)):
            site_id = site_id[0] if len(site_id) > 0 else None
        if site_id is None:
            return no_update, no_update, no_update, no_update
        site_id = str(site_id)  # Ensure it's a string
    except (KeyError, IndexError, TypeError):
        return no_update, no_update, no_update, no_update
    
    # Get gauge metadata
    gauges_df = pd.DataFrame(gauges_data)
    gauge_info = gauges_df[gauges_df['site_id'] == site_id]
    
    if gauge_info.empty:
        return no_update, no_update, no_update, no_update
    
    gauge = gauge_info.iloc[0]
    
    # Create gauge info display
    info_content = [
        html.H6(f"Site {site_id}", className="text-primary mb-2"),
        html.P([html.Strong("Name: "), gauge['station_name']], className="mb-1"),
        html.P([html.Strong("State: "), gauge['state']], className="mb-1"),
    ]
    
    # Add catchment area if available
    if 'catchment_area' in gauge and pd.notna(gauge['catchment_area']) and gauge['catchment_area'] > 0:
        # Convert from sq km to sq mi
        catchment_sq_mi = gauge['catchment_area'] * 0.386102
        info_content.append(
            html.P([html.Strong("Catchment Area: "), f"{catchment_sq_mi:,.1f} sq mi"], className="mb-1")
        )
    elif pd.notna(gauge.get('drainage_area')) and gauge['drainage_area'] > 0:
        info_content.append(
            html.P([html.Strong("Catchment Area: "), f"{gauge['drainage_area']:,.1f} sq mi"], className="mb-1")
        )
    
    # Add years of record if available
    if 'years_of_record' in gauge and pd.notna(gauge['years_of_record']):
        info_content.append(
            html.P([html.Strong("Years of Record: "), f"{int(gauge['years_of_record'])} years"], className="mb-1")
        )
    
    # Add agency/data source
    agency = gauge.get('agency', 'USGS')
    data_source = 'StreamFlow DataOps API' if 'catchment_area' in gauge or 'station_status' in gauge else 'USGS'
    info_content.append(
        html.P([html.Strong("Data Source: "), f"{agency} via {data_source}"], className="mb-1")
    )
    
    # Add coordinates
    info_content.extend([
        html.P([html.Strong("Location: "), 
               f"{gauge['latitude']:.4f}, {gauge['longitude']:.4f}"], className="mb-1"),
        html.Hr(),
        html.P("Streamflow analysis will load when available.", 
              className="text-muted small")
    ])
    
    badge_text = f"Selected: {site_id}"
    badge_style = {"display": "inline"}
    
    return site_id, badge_text, badge_style, info_content


# Callback: manage history-mode-store and history buttons visibility
@app.callback(
    [Output('history-mode-store', 'data'),
     Output('history-buttons-row', 'style')],
    [Input('selected-gauge-store', 'data'),
     Input('show-30yr-history-btn', 'n_clicks'),
     Input('show-full-history-btn', 'n_clicks'),
     Input('show-fast-plot-btn', 'n_clicks')],
    prevent_initial_call=True,
)
def update_history_mode(selected_gauge, n_30yr, n_full, n_fast):
    """Track which history mode the user has selected."""
    from dash import ctx
    triggered = ctx.triggered_id if ctx.triggered_id else None

    buttons_visible = {"display": "block"} if selected_gauge else {"display": "none"}

    if triggered == 'selected-gauge-store':
        # New station selected — reset to fast mode
        return None, buttons_visible
    if triggered == 'show-30yr-history-btn':
        return '30yr', buttons_visible
    if triggered == 'show-full-history-btn':
        return 'all', buttons_visible
    if triggered == 'show-fast-plot-btn':
        return None, buttons_visible

    return None, buttons_visible


# Multi-plot callback: generates all plots for selected site
@app.callback(
    Output('multi-plot-container', 'children'),
    [Input('selected-gauge-store', 'data'),
     Input('highlight-years-input', 'value'),
     Input('chart-height-dropdown', 'value'),
     Input('plot-options-checklist', 'value'),
     Input('history-mode-store', 'data'),
     Input('dark-mode-store', 'data')],
    [State('gauges-store', 'data')]
)
def update_multi_plots(selected_gauge, highlight_years_text, chart_height, plot_options,
                       history_mode, dark_mode, gauges_data):
    """Generate and display all streamflow plots for the selected site."""
    if not selected_gauge:
        return [html.P("Select a gauge on the map to view streamflow plots.", className="text-muted")]

    # Parse highlight years
    highlight_years = []
    if highlight_years_text:
        try:
            years_str = highlight_years_text.replace(' ', '')
            if years_str:
                highlight_years = [int(y.strip()) for y in years_str.split(',') if y.strip().isdigit()]
        except Exception as e:
            print(f"DEBUG: Error parsing highlight years: {e}")

    # Get station name and NWRFC ID
    station_name = "Unknown Station"
    nwrfc_id = None
    if gauges_data:
        for gauge in gauges_data:
            if gauge.get('site_id') == selected_gauge:
                station_name = gauge.get('station_name', 'Unknown Station')
                nwrfc_id = gauge.get('nwrfc_id')
                break

    if history_mode in ('30yr', 'all'):
        data_source_text = data_manager.get_data_source_info().get('source_name', 'Unknown')
    else:
        data_source_text = "Local Stats Cache"

    # Calculate current water year
    today = datetime.today()
    current_wy = today.year + 1 if today.month >= 10 else today.year
    if current_wy not in highlight_years:
        highlight_years.append(current_wy)

    # Fetch NWRFC and ResidCast forecasts (fast — small payloads)
    forecast_data = None
    try:
        forecast_data = data_manager.get_forecast_data(selected_gauge, num_days=5)
    except Exception as e:
        print(f"DEBUG: Error fetching forecast data: {e}")
    resid_cast_data = data_manager.get_resid_cast_forecasts(selected_gauge, num_runs=5)

    # ── Water year plot: fast vs full-history paths ───────────────────────
    if history_mode in ('30yr', 'all'):
        # Full history path: fetch complete record, render with year traces
        streamflow_data = data_manager.get_streamflow_data(selected_gauge)
        if streamflow_data is None or streamflow_data.empty:
            return [dbc.Alert(f"No streamflow data available for site {selected_gauge}", color="warning")]
        wy_fig = viz_manager.create_streamflow_plot(
            selected_gauge, streamflow_data,
            plot_type='water_year',
            highlight_years=highlight_years,
            show_percentiles=True, show_statistics=True,
            data_manager=data_manager,
            forecast_data=forecast_data,
            resid_cast_data=resid_cast_data,
            history_mode=history_mode,
        )
    else:
        # Fast path: current year data + cached statistics
        current_year_data = data_manager.get_current_year_data(selected_gauge)
        statistics = data_manager.get_flow_statistics(selected_gauge)
        if current_year_data is None or current_year_data.empty:
            return [dbc.Alert(f"No streamflow data available for site {selected_gauge}", color="warning")]
        wy_fig = viz_manager.create_fast_water_year_plot(
            site_id=selected_gauge,
            current_year_data=current_year_data,
            statistics=statistics,
            forecast_data=forecast_data,
            resid_cast_data=resid_cast_data,
            data_manager=data_manager,
        )
        # Full-history data needed for annual summary and flow duration —
        # fetch it now (same call would run anyway for those plots)
        streamflow_data = data_manager.get_streamflow_data(selected_gauge)
        if streamflow_data is None or streamflow_data.empty:
            streamflow_data = current_year_data  # fallback to current year

    # ── Build plot option config ───────────────────────────────────────────
    selected_options = plot_options or []
    graph_config = {
        "displaylogo": False,
        "displayModeBar": "hover" if "show_toolbar" in selected_options else False,
        "scrollZoom": "enable_zoom" in selected_options,
        "doubleClick": "autosize" if "enable_zoom" in selected_options else "reset",
    }
    graph_style = {"height": f"{chart_height}px"}
    if "responsive" in selected_options:
        graph_style["width"] = "100%"

    site_label = f"USGS {selected_gauge}"
    if nwrfc_id:
        site_label += f" / NWRFC {nwrfc_id}"

    plot_template = 'plotly_dark' if dark_mode else 'plotly'

    def _card(title, fig):
        fig.update_layout(template=plot_template)
        return dbc.Card([
            dbc.CardHeader([
                html.Div(f"{title} — {site_label} — {station_name}",
                         style={'fontWeight': 'bold'}),
                html.Div(f"Data Source: {data_source_text}",
                         style={'fontSize': '0.9em', 'fontWeight': 'normal', 'color': '#6c757d'}),
            ]),
            dbc.CardBody([dcc.Graph(figure=fig, config=graph_config, style=graph_style)])
        ], className="mb-3")

    cards = [_card("Water Year Plot", wy_fig)]

    # Annual summary and flow duration always use full history
    for title, plot_type in [("Annual Summary", "annual"), ("Flow Duration Curve", "flow_duration")]:
        try:
            if plot_type == "flow_duration":
                fig = viz_manager.create_flow_duration_curve(selected_gauge, streamflow_data)
            else:
                fig = viz_manager.create_streamflow_plot(
                    selected_gauge, streamflow_data,
                    plot_type=plot_type,
                    highlight_years=[],
                    show_percentiles=True, show_statistics=True,
                    data_manager=data_manager,
                )
            cards.append(_card(title, fig))
        except Exception as e:
            print(f"Error creating {plot_type} plot: {e}")
            cards.append(dbc.Alert(f"Error generating {title}: {str(e)}", color="warning", className="mb-3"))

    return cards


# Callbacks to populate dropdown options
@app.callback(
    [Output("basin-filter", "options"),
     Output("huc-filter", "options")],
    [Input("state-filter", "value")]
)
def update_dropdown_options(selected_states):
    """Update basin and HUC options based on selected states."""
    try:
        filters_df = data_manager.get_filters_table()
        
        if selected_states:
            state_filtered = filters_df[filters_df['state'].isin(selected_states)]
        else:
            state_filtered = filters_df
        
        # Get unique basins - convert to string and filter out invalid values
        basins = state_filtered['basin'].dropna().unique()
        basins_str = [str(b) for b in basins if b and not isinstance(b, bytes)]
        basin_options = [{"label": basin, "value": basin} for basin in sorted(basins_str)]
        
        # Get unique HUC codes - convert to string and filter out invalid values
        huc_codes = state_filtered['huc_code'].dropna().unique()
        huc_str = [str(h) for h in huc_codes if h and not isinstance(h, bytes)]
        huc_options = [{"label": huc, "value": huc} for huc in sorted(huc_str)]
        
        return basin_options, huc_options
    except Exception as e:
        print(f"Error updating dropdown options: {e}")
        import traceback
        traceback.print_exc()
        return [], []


# Dynamic filter summary callbacks
@app.callback(
    [Output('filter-summary-text', 'children'),
     Output('state-filter', 'options')],
    Input('gauges-store', 'data')
)
def update_filter_summary(gauges_data):
    """Update the dynamic filter summary text and state options."""
    if not gauges_data:
        return "Loading gauge data...", []
    
    try:
        gauges_df = pd.DataFrame(gauges_data)
        total_sites = len(gauges_df)
        
        # Count sites by state
        state_counts = gauges_df['state'].value_counts()
        
        # Create dynamic state options with current counts
        state_options = []
        state_labels = {
            'OR': '🌲 Oregon',
            'WA': '🏔️ Washington', 
            'ID': '⛰️ Idaho',
            'MT': '⛰️ Montana',
            'CA': '☀️ California',
            'NV': '🏜️ Nevada',
            'UT': '🏔️ Utah',
            'AZ': '🌵 Arizona',
            'CO': '⛰️ Colorado',
            'BC': '🍁 British Columbia'
        }
        
        for state in ['OR', 'WA', 'ID', 'MT', 'CA', 'NV', 'UT', 'AZ', 'CO', 'BC']:
            count = state_counts.get(state, 0)
            if count > 0:  # Only show states that have stations
                # Show active count breakdown if available
                if 'station_status' in gauges_df.columns:
                    state_data = gauges_df[gauges_df['state'] == state]
                    active = (state_data['station_status'] == 'Active').sum()
                    label = f"{state_labels[state]} ({count} sites, {active} active)"
                else:
                    label = f"{state_labels[state]} ({count} sites)"
                state_options.append({"label": label, "value": state})
        
        # Create summary text
        summary_text = f"Filter {total_sites} streamflow gauges (USGS & Environment Canada)"
        
        return summary_text, state_options
        
    except Exception as e:
        print(f"Error updating filter summary: {e}")
        return "Error loading gauge data", []


# Clear search callback
@app.callback(
    Output("search-input", "value"),
    [Input("clear-search", "n_clicks")],
    prevent_initial_call=True
)
def clear_search(n_clicks):
    """Clear the search input."""
    if n_clicks:
        return ""
    return no_update


# Simplified filter display callbacks
@app.callback(
    Output("drainage-area-display", "children"),
    [Input("drainage-area-filter", "value")]
)
def update_drainage_display(value):
    """Update drainage area display."""
    if value:
        return f"Selected: {value[0]:,} - {value[1]:,} sq mi"
    return ""


# Real-time filter info callback
@app.callback(
    Output("realtime-filter-info", "children"),
    [Input("gauges-store", "data")],
    prevent_initial_call=True
)
def update_realtime_filter_info(gauges_data):
    """Update the real-time filter info text with station count."""
    if not gauges_data:
        return "Loading real-time station data..."
    
    try:
        # Get sites with real-time data
        realtime_sites = data_manager.get_sites_with_realtime_data()
        total_sites = len(gauges_data)
        realtime_count = len(realtime_sites)
        
        if realtime_count > 0:
            return f"Stations with enhanced visualizations: {realtime_count} of {total_sites} ({realtime_count/total_sites*100:.0f}%)"
        else:
            return "No real-time data currently available"
    except Exception as e:
        print(f"Error updating real-time filter info: {e}")
        return "Real-time data status unavailable"


# Dark mode: pure clientside toggle — no server round-trip needed
app.clientside_callback(
    """
    function(n_clicks) {
        if (!n_clicks) { return [window.dash_clientside.no_update, window.dash_clientside.no_update]; }
        var isDark = document.body.classList.toggle('dark-mode');
        return [isDark ? 'Light Mode' : 'Dark Mode', isDark];
    }
    """,
    [Output('dark-mode-btn', 'children'),
     Output('dark-mode-store', 'data')],
    Input('dark-mode-btn', 'n_clicks'),
    prevent_initial_call=True,
)


# Sidebar toggle callback (desktop + mobile)
@app.callback(
    [Output("sidebar-col", "className"),
     Output("sidebar-toggle-btn", "children"),
     Output("main-content-wrapper", "className"),
     Output("mobile-sidebar-btn", "children")],
    [Input("sidebar-toggle-btn", "n_clicks"),
     Input("mobile-sidebar-btn", "n_clicks")],
    [State("sidebar-col", "className")],
    prevent_initial_call=False
)
def toggle_sidebar(desktop_clicks, mobile_clicks, current_class):
    """Toggle sidebar visibility for desktop and mobile."""
    ctx = callback_context
    trigger = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    if trigger == "mobile-sidebar-btn":
        # Mobile toggle: show full-width or hide
        current_class = current_class or ""
        if "d-block" in current_class and "d-none" not in current_class:
            # Currently visible on mobile -> hide
            return ("sidebar-col d-none d-lg-block",
                    "◀️ Hide Sidebar", "main-content-col flex-grow-1", "Filters")
        else:
            # Currently hidden on mobile -> show full-width
            return ("sidebar-col d-block",
                    "◀️ Hide Sidebar", "main-content-col flex-grow-1", "Close")

    if trigger == "sidebar-toggle-btn":
        # Desktop toggle
        is_hidden = desktop_clicks and (desktop_clicks % 2 == 1)
        if is_hidden:
            return ("sidebar-col d-none",
                    "▶️ Show Sidebar", "main-content-col w-100", "Filters")
        else:
            return ("sidebar-col d-none d-lg-block",
                    "◀️ Hide Sidebar", "main-content-col flex-grow-1", "Filters")

    # Default state (initial load)
    return ("sidebar-col d-none d-lg-block",
            "◀️ Hide Sidebar", "main-content-col flex-grow-1", "Filters")


# =============================================
# ADMIN INTERFACE CALLBACKS
# =============================================

@app.callback(
    Output('admin-tab-content', 'children'),
    [Input('admin-dashboard-tab', 'n_clicks'),
     Input('admin-stations-tab', 'n_clicks'),
     Input('admin-schedules-tab', 'n_clicks'),
     Input('admin-monitoring-tab', 'n_clicks')],
    [State('admin-tab-content', 'children')]
)
def update_admin_tab_content(dash_clicks, station_clicks, 
                           schedule_clicks, monitor_clicks, current_content):
    """Update admin tab content based on selected tab."""
    from dashboard_admin import (get_system_health_display, 
                                get_recent_activity_table)
    
    ctx = callback_context
    if not ctx.triggered:
        button_id = 'admin-dashboard-tab'
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # If no button was actually clicked, return current content (prevents refresh interval from resetting tabs)
    if not any([dash_clicks, station_clicks, schedule_clicks, monitor_clicks]):
        return current_content or no_update
    
    try:
        if button_id == 'admin-stations-tab':
            from dashboard_admin import get_stations_table
            return dbc.Container([
                html.H4("🗺️ Station Browser", className="mb-4"),
                
                # Filter controls
                dbc.Row([
                    dbc.Col([
                        dbc.Label("States:"),
                        dcc.Dropdown(
                            id="station-state-filter",
                            options=[
                                {'label': 'Washington', 'value': 'WA'},
                                {'label': 'Oregon', 'value': 'OR'},
                                {'label': 'Idaho', 'value': 'ID'},
                                {'label': 'Montana', 'value': 'MT'},
                                {'label': 'Nevada', 'value': 'NV'},
                                {'label': 'California', 'value': 'CA'}
                            ],
                            multi=True,
                            placeholder="All states"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("HUC Code:"),
                        dbc.Input(
                            id="station-huc-filter",
                            placeholder="e.g., 1701",
                            type="text"
                        )
                    ], width=2),
                    dbc.Col([
                        dbc.Label("Source:"),
                        dcc.Dropdown(
                            id="station-source-filter",
                            options=[
                                {'label': 'HADS PNW', 'value': 'HADS_PNW'},
                                {'label': 'HADS Columbia', 'value': 'HADS_Columbia'}
                            ],
                            multi=True,
                            placeholder="All sources"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Search:"),
                        dbc.Input(
                            id="station-search-filter",
                            placeholder="Name or ID...",
                            type="text"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Action:"),
                        dbc.Button("🔍 Filter", id="filter-stations-btn", color="primary", className="w-100")
                    ], width=1)
                ], className="mb-4"),
                
                # Results area
                html.Div(id="stations-table-content", children=[
                    get_stations_table(limit=50)  # Default view
                ])
            ])
        
        elif button_id == 'admin-schedules-tab':
            from dashboard_admin import get_schedules_table
            return dbc.Container([
                html.H4("⏰ Schedule Management", className="mb-4"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button("➕ New Schedule", id="new-schedule-btn", color="success", className="me-2", disabled=True),
                        dbc.Button("▶️ Run Selected", id="run-selected-schedule-btn", color="primary", className="me-2"),
                        dbc.Button("🔄 Toggle Selected", id="toggle-schedule-btn", color="warning", className="me-2"),
                        dbc.Button("🔄 Refresh", id="refresh-schedules-btn", color="info")
                    ])
                ], className="mb-4"),
                
                html.Div(id="schedule-status-message"),
                
                html.Div(id="schedules-table-container", children=[get_schedules_table()])
            ])
        
        elif button_id == 'admin-monitoring-tab':
            return dbc.Container([
                html.H4("📊 Collection Monitoring", className="mb-4"),
                dbc.Alert([
                    html.H5("Data Collection Managed by DataOps", className="alert-heading"),
                    html.P("All data collection is handled by the StreamFlow DataOps service."),
                    html.Hr(),
                    html.P([
                        "View collection status and logs at: ",
                        html.A("StreamFlow DataOps Admin",
                               href="https://streamflowops.3rdplaces.io/admin/",
                               target="_blank",
                               className="alert-link")
                    ]),
                ], color="info")
            ])
        
        else:  # Dashboard tab (default)
            return dbc.Container([
                html.H4("📈 System Dashboard", className="mb-4"),
                
                # System health overview
                dbc.Card([
                    dbc.CardHeader("🏥 System Health"),
                    dbc.CardBody([
                        get_system_health_display()
                    ])
                ], className="mb-4"),
                
                # Recent activity
                dbc.Card([
                    dbc.CardHeader("🔄 Recent Collection Activity"),
                    dbc.CardBody([
                        get_recent_activity_table()
                    ])
                ])
            ])
    
    except Exception as e:
        return dbc.Alert(f"Error loading admin content: {e}", color="danger")


@app.callback(
    [Output('admin-dashboard-tab', 'color'),
     Output('admin-stations-tab', 'color'),
     Output('admin-schedules-tab', 'color'),
     Output('admin-monitoring-tab', 'color')],
    [Input('admin-dashboard-tab', 'n_clicks'),
     Input('admin-stations-tab', 'n_clicks'),
     Input('admin-schedules-tab', 'n_clicks'),
     Input('admin-monitoring-tab', 'n_clicks')]
)
def update_admin_tab_styles(dash_clicks, station_clicks, 
                          schedule_clicks, monitor_clicks):
    """Update tab button colors based on active tab."""
    ctx = callback_context
    if not ctx.triggered:
        active_tab = 'admin-dashboard-tab'
    else:
        active_tab = ctx.triggered[0]['prop_id'].split('.')[0]
    
    colors = ['outline-primary'] * 4
    tab_ids = ['admin-dashboard-tab', 'admin-stations-tab', 
               'admin-schedules-tab', 'admin-monitoring-tab']
    
    if active_tab in tab_ids:
        colors[tab_ids.index(active_tab)] = 'primary'
    
    return colors


# Removed filter_stations_table callback - component doesn't exist

@app.callback(
    [Output('system-health-indicators', 'children'),
     Output('recent-activity-table', 'children')],
    [Input('admin-refresh-interval', 'n_intervals'),
     Input('refresh-monitoring-btn', 'n_clicks')]
)
def update_monitoring_displays(n_intervals, refresh_clicks):
    """Update monitoring tab displays - runs every 30 seconds or on refresh button."""
    from dashboard_admin import get_system_health_display, get_recent_activity_table
    
    try:
        return (
            get_system_health_display(),
            get_recent_activity_table()
        )
    except Exception as e:
        error_msg = dbc.Alert(f"Error updating monitoring displays: {e}", color="danger")
        return error_msg, error_msg


@app.callback(
    [Output('schedule-status-message', 'children'),
     Output('schedules-table-container', 'children'),
     Output('toast-container', 'children')],
    [Input('run-selected-schedule-btn', 'n_clicks'),
     Input('toggle-schedule-btn', 'n_clicks'),
     Input('refresh-schedules-btn', 'n_clicks')],
    [State('schedules-table', 'selected_rows'),
     State('schedules-table', 'data')]
)
def handle_schedule_actions(run_clicks, toggle_clicks, refresh_clicks, selected_rows, table_data):
    """
    Handle schedule management actions.
    
    Data collection is managed by StreamFlow DataOps — this dashboard
    only displays data. Schedule management is deferred to the DataOps
    admin interface.
    """
    from dashboard_admin import get_schedules_table
    
    ctx = callback_context
    if not ctx.triggered:
        return "", get_schedules_table(), None
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Handle refresh
    if button_id == 'refresh-schedules-btn':
        return "", get_schedules_table(), None
    
    # All management actions redirect to DataOps
    dataops_url = os.environ.get('DATAOPS_API_URL', 'https://streamflowops.3rdplaces.io')
    msg = dbc.Alert([
        html.H5("ℹ️ Data Collection Managed by DataOps", className="alert-heading"),
        html.P("Schedule and collection management is handled by the StreamFlow DataOps system."),
        dbc.Button(
            "Open DataOps Admin",
            href=f"{dataops_url}/admin/",
            target="_blank",
            color="primary",
            size="sm"
        )
    ], color="info", dismissable=True)
    
    return msg, get_schedules_table(), None

@app.callback(
    Output('admin-system-info', 'children'),
    [Input('admin-content', 'style'),
     Input('url', 'pathname')]
)
def update_admin_system_info(admin_style, pathname):
    """Update the admin system information section when admin panel is visible."""
    from dashboard_admin import get_system_info
    
    # Load system info when admin content is visible (display: block)
    if admin_style and admin_style.get('display') == 'block':
        return get_system_info()
    
    # Also load if pathname is /admin (for direct URL access)
    if pathname == '/admin':
        return get_system_info()
    
    return None


if __name__ == '__main__':
    import os
    
    print(f"Starting {APP_TITLE}...")
    print(f"Data source: StreamFlow DataOps API")
    
    # Ensure data directory exists (for local cache)
    os.makedirs('data', exist_ok=True)
    
    # Get port from environment (Render provides this) or default to 8050
    port = int(os.environ.get('PORT', 8050))
    host = os.environ.get('HOST', '0.0.0.0')
    
    # Debug mode off for production
    debug_mode = os.environ.get('DASH_DEBUG', 'False').lower() == 'true'
    
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Debug: {debug_mode}")
    
    if not debug_mode:
        print("Production mode - Dashboard running")
    else:
        print(f"Development mode - Open your browser to: http://localhost:{port}")
    
    app.run(debug=debug_mode, host=host, port=port)