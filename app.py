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
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
import bcrypt
import logging
import os
import threading

logger = logging.getLogger(__name__)

# Import dashboard components
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.data import plot_cache_manager
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

# Admin credentials — set ADMIN_PASSWORD_BCRYPT in .env (bcrypt hash of the password)
# Generate with: python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
_ADMIN_PASSWORD_BCRYPT = os.environ.get('ADMIN_PASSWORD_BCRYPT', '').encode()

def verify_password(username, password):
    """Verify admin credentials using bcrypt."""
    if username != ADMIN_USERNAME:
        return False
    if not _ADMIN_PASSWORD_BCRYPT:
        return False
    return bcrypt.checkpw(password.encode(), _ADMIN_PASSWORD_BCRYPT)

# Initialize components
data_manager = get_data_manager()
map_component = get_map_component()
viz_manager = get_visualization_manager()
filter_panel = SimplifiedFilterPanel()
from resid_cast.precip_runoff_adapter import PrecipRunoffAdapter
_precip_adapter = PrecipRunoffAdapter()

# Start percentile background refresh thread (fetches from StreamflowOps every 30 min)
data_manager.start_percentile_background_refresh(interval_seconds=1800)

# Pre-warm station cache in background so first user request hits cache, not cold API
def _prefetch_stations():
    try:
        data_manager.load_regional_gauges()
    except Exception as e:
        logger.error(f"Station prefetch failed: {e}", exc_info=True)

threading.Thread(target=_prefetch_stations, daemon=True, name="station-prefetch").start()

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title=APP_TITLE,
    update_title='Loading...',
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1, shrink-to-fit=no"}
    ]
)

# Serve pre-generated hover PNG thumbnails
import re as _re
from usgs_dashboard.data import png_cache_manager as _png_cache_mgr

@app.server.route("/plot-png/<site_id>")
def serve_plot_png(site_id):
    """Serve a pre-generated hover PNG for the given site."""
    if not _re.match(r'^[A-Za-z0-9_\-]+$', site_id):
        return flask.abort(400)
    png_path = _png_cache_mgr.get_path(site_id)
    if not png_path.is_file():
        return flask.abort(404)
    return flask.send_file(str(png_path), mimetype="image/png")

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

            body.dark-mode input[type="date"] {
                background-color: #3a3a3a !important;
                border-color: #555 !important;
                color: #e0e0e0 !important;
                color-scheme: dark;
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
                        {"label": "🌍 National Geographic", "value": "natgeo"},
                        {"label": "🛰️ Satellite", "value": "esri-satellite"},
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
                    value=600,
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
                        {"label": "🌍 National Geographic", "value": "natgeo"},
                        {"label": "🛰️ Satellite", "value": "esri-satellite"},
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
                    value=600,
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
                    # Right: label + [−] date picker [+]
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Small(
                                        "Flow conditions for date:",
                                        className="text-muted",
                                        style={"whiteSpace": "nowrap", "fontSize": "0.75rem"},
                                    ),
                                    width="auto",
                                    className="d-none d-sm-block",  # hide label on phones
                                ),
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
                                    [
                                        dbc.Input(
                                            type="date",
                                            id="percentile-date-picker",
                                            size="sm",
                                            style={"width": "140px", "fontSize": "0.8rem"},
                                        ),
                                        html.Small(
                                            id='percentile-source-label',
                                            children="Observed conditions",
                                            className="text-muted d-block mt-1",
                                            style={"fontSize": "0.7rem", "whiteSpace": "nowrap"},
                                        ),
                                    ],
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
            dbc.CardHeader(
                html.Div([
                    html.H5("📊 Streamflow Analysis", className="mb-0"),
                    html.Div([
                        dbc.Badge(
                            id="cache-age-badge",
                            color="secondary",
                            style={"display": "none", "cursor": "default", "fontSize": "11px"},
                        ),
                        dbc.Button(
                            "🔄 Refresh",
                            id="refresh-live-plot-btn",
                            color="outline-info",
                            size="sm",
                            n_clicks=0,
                            style={"display": "none"},
                        ),
                        dbc.Badge(
                            id="selected-gauge-badge",
                            color="success",
                            style={"display": "none"},
                        ),
                    ], className="d-flex align-items-center gap-2"),
                ], className="d-flex justify-content-between align-items-center"),
            ),
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
                ),
                # Period-of-record prompt (hidden until a station is selected)
                html.Div(
                    id="annual-summary-prompt-row",
                    style={"display": "none"},
                    children=[
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    html.P(
                                        "Annual Summary and Flow Duration Curve use the full "
                                        "period of record and may take a moment to load.",
                                        className="text-muted mb-3",
                                    ),
                                    dbc.Button(
                                        "📊 Load Period-of-Record Analysis",
                                        id="load-annual-summary-btn",
                                        color="primary",
                                        outline=True,
                                        size="md",
                                        n_clicks=0,
                                    ),
                                ], className="text-center py-2"),
                            ])
                        ], className="mb-3"),
                    ],
                ),
                dcc.Loading(
                    id="loading-annual-summary",
                    type="default",
                    custom_spinner=html.Div(
                        className="hydro-loading-wrapper",
                        children=[
                            html.Div(
                                className="hydro-wave-container",
                                children=[html.Div(className="hydro-wave-bar") for _ in range(7)],
                            ),
                            html.Div("Loading period-of-record analysis…", className="hydro-loading-label"),
                        ],
                    ),
                    children=[
                        html.Div(id="annual-summary-container")
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
    dcc.Store(id='annual-summary-requested', data=False),
    dcc.Store(id='gauges-store'),
    dcc.Store(id='selected-gauge-store'),
    dcc.Store(id='history-mode-store', data=None),
    dcc.Store(id='streamflow-data-store'),
    dcc.Store(id='site-limit-store', data=300),
    dcc.Store(id='auth-store', data={'authenticated': False}),
    dcc.Store(id='percentile-bands-store', data={}),
    dcc.Store(id='percentile-date-range-store', data={}),
    dcc.Store(id='forecast-date-range-store', storage_type='memory'),
    dcc.Store(id='forecast-run-date-store', storage_type='memory'),
    dcc.Store(id='selected-percentile-date-store', data=None),
    dcc.Store(id='window-width-store', data=1200),   # populated by clientside callback
    dcc.Store(id='scroll-trigger-store', data=None), # dummy output for scroll clientside callback
    dcc.Store(id='fast-plot-figure-store', data=None),
    dcc.Store(id='plot-cache-meta-store', data=None),
    dcc.Store(id='map-tooltip-store', data=None),
    dcc.Interval(
        id='percentile-refresh-interval',
        interval=30_000,   # poll every 30 seconds
        n_intervals=0,
    ),
    # Fast startup poll: fires every 1s for the first 10s so percentile colors
    # appear immediately after the background thread populates the cache.
    dcc.Interval(
        id='percentile-startup-interval',
        interval=1_000,
        max_intervals=10,
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

    # Map station hover panel — follows cursor, shows station info + PNG thumbnail
    html.Div(
        id='map-hover-panel',
        style={'display': 'none'},
        children=[
            html.Div(id='map-hover-info-text', style={
                'padding': '5px 9px 4px 9px',
                'backgroundColor': '#252525',
            }),
            html.Img(
                id='map-hover-tooltip-img',
                src='',
                style={
                    'width': '462px',
                    'height': '268px',
                    'display': 'block',
                    'borderRadius': '0 0 6px 6px',
                },
            ),
        ],
    ),

], fluid=True)


# ── Mobile clientside helpers ─────────────────────────────────────────────────

# Capture browser viewport width once on page load so server callbacks can
# cap chart height on narrow screens without re-querying the browser.
app.clientside_callback(
    "function(href) { return window.innerWidth || 1200; }",
    Output('window-width-store', 'data'),
    Input('url', 'href'),
)

# On mobile, auto-scroll to the chart card after a gauge is selected so the
# user doesn't have to manually scroll past the map.
app.clientside_callback(
    """
    function(children) {
        if (children && children.length && children[0] && children[0].type === 'Card'
                && window.innerWidth < 992) {
            setTimeout(function() {
                var el = document.getElementById('multi-plot-container');
                if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'});
            }, 500);
        }
        return null;
    }
    """,
    Output('scroll-trigger-store', 'data'),
    Input('multi-plot-container', 'children'),
)


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
    if login_clicks and login_clicks > 0:
        if not username or not password:
            return (auth_data or {'authenticated': False},
                    dbc.Alert("Please enter both username and password", color="warning"),
                    username or "", password or "")

        if verify_password(username, password):
            logger.info(f"Login successful for user: {username}")
            return ({'authenticated': True, 'username': username},
                    dbc.Alert("Login successful!", color="success"),
                    "", "")
        else:
            logger.warning(f"Failed login attempt for user: {username}")
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
    if logout_clicks and logout_clicks > 0:
        logger.info("User logged out")
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
    
    logger.debug(f"load_gauge_data callback fired: pathname={pathname}")

    try:
        # Load stations from DataOps API via data_manager
        filters_df = data_manager.load_regional_gauges()

        if filters_df.empty:
            logger.warning("No stations returned from DataOps API")
            alert = dbc.Alert(
                "No gauge data available. Check DataOps API connection.",
                color="warning",
                dismissable=True
            )
            return [], alert, 0
        
        logger.info(f"Loaded {len(filters_df)} stations from DataOps API")
        
        global gauges_df
        gauges_df = filters_df.copy()
        
        # Drop columns that can't be JSON-serialized
        if 'years_of_record' in gauges_df.columns:
            gauges_df = gauges_df.drop('years_of_record', axis=1)
        
        # Slim payload: keep only columns needed by map + filter callbacks
        _keep_cols = [
            'site_id', 'station_number', 'station_name', 'state',
            'latitude', 'longitude', 'drainage_area', 'station_status',
            'huc_code', 'basin', 'nwrfc_id', 'color', 'catchment_area',
            'site_no', 'station_nm', 'name', 'status',
        ]
        available = [c for c in _keep_cols if c in gauges_df.columns]
        gauges_df = gauges_df[available]

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
        logger.debug(f"Returning {len(gauges_data)} gauge records")
        
        alert = dbc.Alert(
            alert_msg,
            color="success",
            dismissable=True,
            duration=4000
        )
        return gauges_data, alert, len(gauges_data)
        
    except Exception as e:
        logger.error(f"Error in load_gauge_data: {e}", exc_info=True)
        alert = dbc.Alert(
            f"Error loading gauge data: {str(e)}",
            color="danger",
            dismissable=True
        )
        return [], alert, 0


# Legacy callbacks removed - UI components no longer exist


@app.callback(
    [Output('percentile-bands-store', 'data'),
     Output('forecast-run-date-store', 'data')],
    Input('percentile-refresh-interval', 'n_intervals'),
    Input('percentile-startup-interval', 'n_intervals'),
    Input('selected-percentile-date-store', 'data'),
    State('percentile-bands-store', 'data'),
    prevent_initial_call=False,
)
def refresh_percentile_bands(n_intervals, startup_n_intervals, selected_date, current_bands):
    """Route to forecast or observed bands depending on selected date."""
    today = date.today().isoformat()

    if selected_date and selected_date > today:
        result = data_manager.get_forecast_percentile_bands_for_date(selected_date)
        new_bands = result.get('bands', {})
        run_date = result.get('forecast_run_date')
        if new_bands == (current_bands or {}):
            return no_update, run_date
        return new_bands, run_date
    elif selected_date:
        new_bands = data_manager.get_percentile_bands_for_date(selected_date)
        if new_bands == (current_bands or {}):
            return no_update, None
        return new_bands, None
    else:
        new_bands = data_manager.get_cached_percentile_bands()
        if new_bands == (current_bands or {}):
            return no_update, None
        return new_bands, None


@app.callback(
    Output('percentile-date-range-store', 'data'),
    Input('percentile-refresh-interval', 'n_intervals'),
    Input('percentile-startup-interval', 'n_intervals'),
    State('percentile-date-range-store', 'data'),
    prevent_initial_call=False,
)
def load_percentile_date_range(n_intervals, startup_intervals, current_range):
    """Fetch the available date range once on load; skip if already populated."""
    if current_range:
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
    Output('forecast-date-range-store', 'data'),
    Input('percentile-startup-interval', 'n_intervals'),
    State('forecast-date-range-store', 'data'),
    prevent_initial_call=False,
)
def load_forecast_date_range(startup_intervals, current_range):
    """Fetch forecast date range once on load; skip if already populated."""
    if current_range:
        return no_update
    return data_manager.get_forecast_percentile_date_range()


@app.callback(
    [Output('percentile-date-picker', 'min'),
     Output('percentile-date-picker', 'max'),
     Output('percentile-date-picker', 'value')],
    [Input('percentile-date-range-store', 'data'),
     Input('forecast-date-range-store', 'data')],
    prevent_initial_call=True,
)
def init_date_picker(obs_range, fcst_range):
    """Set picker bounds: min from observed, max extended to forecast window if available."""
    if not obs_range or not obs_range.get('max_date'):
        return no_update, no_update, no_update
    min_date = obs_range['min_date']
    obs_max = obs_range['max_date']
    fcst_max = (fcst_range or {}).get('max_date')
    max_date = fcst_max if (fcst_max and fcst_max > obs_max) else obs_max
    return min_date, max_date, obs_max  # default to latest observed date, not forecast end


@app.callback(
    Output('percentile-source-label', 'children'),
    [Input('selected-percentile-date-store', 'data'),
     Input('forecast-run-date-store', 'data')],
    prevent_initial_call=False,
)
def update_source_label(selected_date, forecast_run_date):
    """Show 'Observed conditions' or 'Forecast: NWRFC — issued [run date]'."""
    today = date.today().isoformat()
    if selected_date and selected_date > today and forecast_run_date:
        try:
            from datetime import datetime
            run_dt = datetime.fromisoformat(forecast_run_date.replace('Z', '+00:00'))
            run_local = run_dt.strftime('%-m/%-d/%Y %-I:%M %p UTC')
        except Exception:
            run_local = forecast_run_date
        return f"Forecast: NWRFC — issued {run_local}"
    return "Observed conditions"


@app.callback(
    [Output('selected-percentile-date-store', 'data'),
     Output('percentile-date-picker', 'value', allow_duplicate=True)],
    [Input('prev-date-btn', 'n_clicks'),
     Input('next-date-btn', 'n_clicks'),
     Input('percentile-date-picker', 'value')],
    [State('percentile-date-range-store', 'data'),
     State('forecast-date-range-store', 'data')],
    prevent_initial_call=True,
)
def update_date_selection(prev_clicks, next_clicks, picker_value, range_data, fcst_range):
    """Handle − / + buttons and direct date input.

    The date input is always the single source of truth for what date is
    displayed. The − / + buttons shift it by one day and write back to it.
    When the selected date equals max_date, selected-percentile-date-store is
    set to None so the map uses the background-refresh cache instead of making
    an extra API call.
    """
    if not range_data or not range_data.get('max_date'):
        return no_update, no_update

    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    obs_max = range_data['max_date']
    fcst_max = (fcst_range or {}).get('max_date')
    max_d = date.fromisoformat(fcst_max if (fcst_max and fcst_max > obs_max) else obs_max)
    min_d = date.fromisoformat(range_data['min_date'])
    try:
        current = date.fromisoformat(picker_value) if picker_value else max_d
    except ValueError:
        return no_update, no_update

    if triggered_id == 'prev-date-btn':
        selected = max(current - timedelta(days=1), min_d)
    elif triggered_id == 'next-date-btn':
        selected = min(current + timedelta(days=1), max_d)
    elif triggered_id == 'percentile-date-picker':
        # Clamp typed value to valid range
        selected = max(min_d, min(current, max_d))
    else:
        return no_update, no_update

    date_str = selected.isoformat()
    # Use background cache (None) when at the observed max date; forecast dates always need explicit fetch
    obs_max_d = date.fromisoformat(obs_max)
    # None = use background cache (only when exactly at the latest observed date)
    # Future dates must use an explicit date string to trigger the forecast API call
    store_val = None if selected == obs_max_d else date_str
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
     Input('percentile-bands-store', 'data'),
     Input('dark-mode-store', 'data')],
    [State('selected-gauge-store', 'data')]
)
def update_map_with_simplified_filters(gauges_data, map_style, map_height, basin_boundaries, search_text, states,
                                     drainage_range, basins, hucs, show_realtime_only, station_status, show_forecast_only,
                                     show_resid_cast_only, percentile_bands, dark_mode, selected_gauge):
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
            logger.warning(f"Error filtering by real-time data: {e}")
    
    # NWRFC forecast filter — keep only stations with active NWRFC forecast data
    # Always use get_forecast_station_ids() (queries DataOps NOAA_RFC stations) rather
    # than the nwrfc_id crosswalk column, which covers ~1,567 entries regardless of
    # whether the station has current forecast data.
    if show_forecast_only:
        try:
            forecast_site_ids = data_manager.get_forecast_station_ids()
            if forecast_site_ids:
                filtered_gauges = filtered_gauges[filtered_gauges['site_id'].isin(forecast_site_ids)]
            else:
                filtered_gauges = pd.DataFrame()
        except Exception as e:
            logger.warning(f"Error filtering by NWRFC forecast data: {e}")

    # ResidCast ML forecast filter — per-station models only (13 quality stations)
    if show_resid_cast_only:
        try:
            rc_ids = data_manager.get_resid_cast_perstation_ids()
            if rc_ids:
                filtered_gauges = filtered_gauges[filtered_gauges['site_id'].isin(rc_ids)]
            else:
                filtered_gauges = pd.DataFrame()
        except Exception as e:
            logger.warning(f"Error filtering by ResidCast stations: {e}")

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
        
        # Apply dark mode legend / tooltip styling (basemap is unchanged)
        if dark_mode:
            fig.update_layout(
                legend=dict(
                    bgcolor="rgba(40,40,40,0.92)",
                    bordercolor="#555555",
                    font=dict(color="#e0e0e0"),
                ),
                hoverlabel=dict(
                    bgcolor="#2d2d2d",
                    bordercolor="#555555",
                    font=dict(color="#e0e0e0"),
                ),
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


# Clientside callback: patch selection highlight into the map without a server round-trip.
# Triggered only when the user clicks a station; does not cause a full map rebuild.
app.clientside_callback(
    """
    function(selectedGauge, gaugesData, figure) {
        if (!figure) return window.dash_clientside.no_update;

        // Remove any existing selection highlight traces
        var filteredData = figure.data.filter(function(trace) {
            return trace.name !== 'Selected Gauge' && trace.name !== 'Selection Outer Ring';
        });

        if (!selectedGauge || !gaugesData) {
            return Object.assign({}, figure, {data: filteredData});
        }

        // Find the clicked station
        var gauge = null;
        for (var i = 0; i < gaugesData.length; i++) {
            if (String(gaugesData[i].site_id) === String(selectedGauge)) {
                gauge = gaugesData[i];
                break;
            }
        }
        if (!gauge) return Object.assign({}, figure, {data: filteredData});

        var name = gauge.station_name || gauge.site_id;

        return Object.assign({}, figure, {
            data: filteredData.concat([
                {
                    type: 'scattermap',
                    lat: [gauge.latitude],
                    lon: [gauge.longitude],
                    mode: 'markers',
                    marker: {size: 28, color: 'rgba(255, 69, 0, 0.4)'},
                    showlegend: false,
                    hoverinfo: 'skip',
                    name: 'Selection Outer Ring'
                },
                {
                    type: 'scattermap',
                    lat: [gauge.latitude],
                    lon: [gauge.longitude],
                    mode: 'markers',
                    marker: {size: 16, color: '#FF4500'},
                    showlegend: false,
                    hoverinfo: 'skip',
                    name: 'Selected Gauge'
                }
            ])
        });
    }
    """,
    Output('gauge-map', 'figure', allow_duplicate=True),
    Input('selected-gauge-store', 'data'),
    [State('gauges-store', 'data'),
     State('gauge-map', 'figure')],
    prevent_initial_call=True,
)


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
    [Output('multi-plot-container', 'children'),
     Output('fast-plot-figure-store', 'data'),
     Output('plot-cache-meta-store', 'data')],
    [Input('selected-gauge-store', 'data'),
     Input('highlight-years-input', 'value'),
     Input('chart-height-dropdown', 'value'),
     Input('plot-options-checklist', 'value'),
     Input('history-mode-store', 'data'),
     Input('dark-mode-store', 'data'),
     Input('refresh-live-plot-btn', 'n_clicks')],
    [State('gauges-store', 'data'),
     State('window-width-store', 'data')]
)
def update_multi_plots(selected_gauge, highlight_years_text, chart_height, plot_options,
                       history_mode, dark_mode, refresh_n_clicks, gauges_data, window_width):
    """Generate and display all streamflow plots for the selected site."""
    if not selected_gauge:
        return [html.P("Select a gauge on the map to view streamflow plots.", className="text-muted")], None, None

    triggered_id = callback_context.triggered_id if callback_context.triggered else None
    force_live = (triggered_id == 'refresh-live-plot-btn')

    # Parse highlight years
    highlight_years = []
    if highlight_years_text:
        try:
            years_str = highlight_years_text.replace(' ', '')
            if years_str:
                highlight_years = [int(y.strip()) for y in years_str.split(',') if y.strip().isdigit()]
        except Exception as e:
            logger.debug(f"Error parsing highlight years: {e}")

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
        logger.warning(f"Forecast fetch failed for {selected_gauge}: {e}")
    resid_cast_data = data_manager.get_resid_cast_forecasts(selected_gauge, num_runs=5)
    precip_runoff_data = _precip_adapter.get_forecasts(selected_gauge, num_runs=5)

    # ── Water year plot: fast vs full-history paths ───────────────────────
    fast_fig_dict = None
    cache_meta = None

    if history_mode in ('30yr', 'all'):
        # Full history path: fetch complete record, render with year traces
        streamflow_data = data_manager.get_streamflow_data(selected_gauge)
        if streamflow_data is None or streamflow_data.empty:
            return [dbc.Alert(f"No streamflow data available for site {selected_gauge}", color="warning")], None, None
        wy_fig = viz_manager.create_streamflow_plot(
            selected_gauge, streamflow_data,
            plot_type='water_year',
            highlight_years=highlight_years,
            show_percentiles=True, show_statistics=True,
            data_manager=data_manager,
            forecast_data=forecast_data,
            resid_cast_data=resid_cast_data,
            precip_runoff_data=precip_runoff_data,
            history_mode=history_mode,
        )
    else:
        # Fast path: serve from plot cache when available, else compute and cache
        if not force_live and plot_cache_manager.exists(selected_gauge):
            fig_dict, generated_at = plot_cache_manager.get(selected_gauge)
            if fig_dict is not None:
                wy_fig = go.Figure(fig_dict)
                age = plot_cache_manager.age_seconds(selected_gauge)
                cache_meta = {
                    'cached': True,
                    'generated_at': generated_at.isoformat(),
                    'age_seconds': age,
                }
                fast_fig_dict = fig_dict
            else:
                force_live = True  # cache read failed, fall through to live

        if force_live or not plot_cache_manager.exists(selected_gauge) or fast_fig_dict is None:
            current_year_data = data_manager.get_current_year_data(selected_gauge)
            statistics = data_manager.get_flow_statistics(selected_gauge)
            if current_year_data is None or current_year_data.empty:
                # Station has no current water-year data (inactive/historical).
                # Fall back to full period of record so historical stations are still viewable.
                streamflow_data = data_manager.get_streamflow_data(selected_gauge)
                if streamflow_data is None or streamflow_data.empty:
                    return [dbc.Alert(f"No streamflow data available for site {selected_gauge}", color="warning")], None, None
                wy_fig = viz_manager.create_streamflow_plot(
                    selected_gauge, streamflow_data,
                    plot_type='water_year',
                    highlight_years=highlight_years,
                    show_percentiles=True, show_statistics=True,
                    data_manager=data_manager,
                    forecast_data=forecast_data,
                    resid_cast_data=resid_cast_data,
                    precip_runoff_data=precip_runoff_data,
                    history_mode='all',
                )
                now_iso = datetime.now().isoformat()
                cache_meta = {'cached': False, 'generated_at': now_iso, 'age_seconds': 0}
                fast_fig_dict = wy_fig.to_dict()
            else:
                wy_fig = viz_manager.create_fast_water_year_plot(
                    site_id=selected_gauge,
                    current_year_data=current_year_data,
                    statistics=statistics,
                    forecast_data=forecast_data,
                    resid_cast_data=resid_cast_data,
                    precip_runoff_data=precip_runoff_data,
                    data_manager=data_manager,
                )
                plot_cache_manager.save(selected_gauge, wy_fig)
                now_iso = datetime.now().isoformat()
                cache_meta = {'cached': False, 'generated_at': now_iso, 'age_seconds': 0}
                fast_fig_dict = wy_fig.to_dict()

    # ── Build plot option config ───────────────────────────────────────────
    selected_options = plot_options or []
    graph_config = {
        "displaylogo": False,
        "displayModeBar": "hover" if "show_toolbar" in selected_options else False,
        "scrollZoom": "enable_zoom" in selected_options,
        "doubleClick": "autosize" if "enable_zoom" in selected_options else "reset",
    }
    effective_height = min(chart_height, 400) if window_width and window_width < 600 else chart_height
    graph_style = {"height": f"{effective_height}px"}
    if "responsive" in selected_options:
        graph_style["width"] = "100%"

    site_label = f"USGS {selected_gauge}"
    if nwrfc_id:
        site_label += f" / NWRFC {nwrfc_id}"

    plot_template = 'plotly_dark' if dark_mode else 'plotly'

    def _card(title, fig, graph_id=None):
        fig.update_layout(template=plot_template, hovermode='x unified')
        graph_kwargs = dict(figure=fig, config=graph_config, style=graph_style)
        if graph_id:
            graph_kwargs['id'] = graph_id
        return dbc.Card([
            dbc.CardHeader([
                html.Div(f"{title} — {site_label} — {station_name}",
                         style={'fontWeight': 'bold'}),
                html.Div(f"Data Source: {data_source_text}",
                         style={'fontSize': '0.9em', 'fontWeight': 'normal', 'color': '#6c757d'}),
            ]),
            dbc.CardBody([dcc.Graph(**graph_kwargs)])
        ], className="mb-3")

    return [_card("Water Year Plot", wy_fig, graph_id='water-year-graph')], fast_fig_dict, cache_meta


def _format_cache_age(seconds: float) -> str:
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    if seconds < 86400:
        return f"{seconds / 3600:.1f}h ago"
    return f"{int(seconds / 86400)}d ago"


@app.callback(
    [Output('refresh-live-plot-btn', 'disabled'),
     Output('refresh-live-plot-btn', 'style'),
     Output('cache-age-badge', 'children'),
     Output('cache-age-badge', 'color'),
     Output('cache-age-badge', 'style')],
    [Input('selected-gauge-store', 'data'),
     Input('history-mode-store', 'data'),
     Input('plot-cache-meta-store', 'data')],
)
def update_refresh_controls(selected_gauge, history_mode, cache_meta):
    hidden = {'display': 'none'}
    visible = {'display': 'inline-block'}

    if not selected_gauge:
        return True, hidden, "", "secondary", hidden

    in_history_mode = history_mode in ('30yr', 'all')
    disabled = in_history_mode

    if cache_meta and not in_history_mode:
        if cache_meta.get('cached'):
            age_str = _format_cache_age(cache_meta.get('age_seconds', 0))
            badge_text = f"⏱ Cached {age_str}"
            badge_color = "secondary"
        else:
            badge_text = "⚡ Live"
            badge_color = "success"
        badge_style = {'display': 'inline-block', 'fontSize': '11px', 'cursor': 'default'}
    else:
        badge_text = ""
        badge_color = "secondary"
        badge_style = hidden

    return disabled, visible, badge_text, badge_color, badge_style


# ── Period-of-record lazy-load callbacks ──────────────────────────────────────

@app.callback(
    [Output('annual-summary-requested', 'data'),
     Output('annual-summary-prompt-row', 'style'),
     Output('annual-summary-container', 'children', allow_duplicate=True)],
    [Input('selected-gauge-store', 'data'),
     Input('load-annual-summary-btn', 'n_clicks')],
    prevent_initial_call=True,
)
def toggle_annual_summary_requested(selected_gauge, n_clicks):
    """Reset to False on new gauge selection; set True when button clicked."""
    from dash import ctx
    triggered = ctx.triggered_id if ctx.triggered_id else None
    prompt_visible = {"display": "block"} if selected_gauge else {"display": "none"}
    if triggered == 'load-annual-summary-btn' and n_clicks:
        return True, {"display": "none"}, no_update
    # New gauge selected — clear container directly (no spinner) and reset state
    return False, prompt_visible, []


@app.callback(
    Output('annual-summary-container', 'children'),
    [Input('annual-summary-requested', 'data')],
    [State('dark-mode-store', 'data'),
     State('selected-gauge-store', 'data'),
     State('gauges-store', 'data'),
     State('chart-height-dropdown', 'value'),
     State('plot-options-checklist', 'value'),
     State('window-width-store', 'data')],
    prevent_initial_call=True,
)
def render_annual_summary(requested, dark_mode, selected_gauge, gauges_data,
                          chart_height, plot_options, window_width):
    """Render period-of-record plots only when explicitly requested via button."""
    from dash.exceptions import PreventUpdate
    if not requested or not selected_gauge:
        raise PreventUpdate

    # ── Full render ───────────────────────────────────────────────────────────
    station_name = "Unknown Station"
    nwrfc_id = None
    if gauges_data:
        for gauge in gauges_data:
            if gauge.get('site_id') == selected_gauge:
                station_name = gauge.get('station_name', 'Unknown Station')
                nwrfc_id = gauge.get('nwrfc_id')
                break

    streamflow_data = data_manager.get_streamflow_data(selected_gauge)
    if streamflow_data is None or streamflow_data.empty:
        return [dbc.Alert(
            f"No historical data available for site {selected_gauge}.",
            color="warning", className="mb-3",
        )]

    data_source_text = data_manager.get_data_source_info().get('source_name', 'Unknown')
    site_label = f"USGS {selected_gauge}"
    if nwrfc_id:
        site_label += f" / NWRFC {nwrfc_id}"

    plot_template = 'plotly_dark' if dark_mode else 'plotly'
    selected_options = plot_options or []
    graph_config = {
        "displaylogo": False,
        "displayModeBar": "hover" if "show_toolbar" in selected_options else False,
        "scrollZoom": "enable_zoom" in selected_options,
        "doubleClick": "autosize" if "enable_zoom" in selected_options else "reset",
    }
    effective_height = min(chart_height, 400) if window_width and window_width < 600 else chart_height
    graph_style = {"height": f"{effective_height}px"}
    if "responsive" in selected_options:
        graph_style["width"] = "100%"

    def _por_card(title, fig):
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

    cards = []
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
            cards.append(_por_card(title, fig))
        except Exception as e:
            logger.error(f"Error creating {plot_type} plot: {e}", exc_info=True)
            cards.append(dbc.Alert(
                f"Error generating {title}: {str(e)}", color="warning", className="mb-3"
            ))

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
        logger.warning(f"Error updating dropdown options: {e}")
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
        logger.warning(f"Error updating filter summary: {e}")
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
        logger.warning(f"Error updating real-time filter info: {e}")
        return "Real-time data status unavailable"


from usgs_dashboard.components.map_component import PERCENTILE_GROUP_CONFIG as _PG_CONFIG
# Map condition label → exact hex color used for map markers (single source of truth)
_CONDITION_COLORS = {cfg[1]: cfg[2] for cfg in _PG_CONFIG}

def _condition_color(label: str) -> str:
    return _CONDITION_COLORS.get(label, '#aaaaaa')


@app.callback(
    Output('map-tooltip-store', 'data'),
    Output('map-hover-info-text', 'children'),
    Input('gauge-map', 'hoverData'),
    prevent_initial_call=True,
)
def update_map_tooltip_store(hover_data):
    """Populate station info panel and store; clientside callback handles positioning."""
    from usgs_dashboard.data import png_cache_manager as _png_mgr

    if not hover_data or not hover_data.get('points'):
        return {'show': False}, []

    pt = hover_data['points'][0]
    customdata = pt.get('customdata')
    if not customdata:
        return {'show': False}, []

    site_id    = str(customdata[0])
    state      = customdata[1] or ''
    area       = customdata[2] or 'N/A'
    years      = customdata[3] or 'N/A'
    lat        = customdata[5] or 0
    lon        = customdata[6] or 0
    name       = customdata[8] or site_id
    condition  = customdata[9] or 'Unknown'
    cond_color = _condition_color(condition)

    has_png = _png_mgr.exists(site_id)
    if has_png:
        mtime = int(_png_mgr.get_path(site_id).stat().st_mtime)
        src = f"/plot-png/{site_id}?v={mtime}"
    else:
        src = ''

    info = html.Div([
        html.Div(name, style={
            'fontSize': '12px', 'fontWeight': '700', 'color': '#e0e0e0',
            'marginBottom': '2px', 'lineHeight': '1.2',
        }),
        html.Hr(style={'margin': '2px 0 4px 0', 'borderColor': '#444', 'borderWidth': '1px'}),
        html.Div([
            html.Span("Site: ", style={'color': '#aaaaaa', 'fontSize': '10px'}),
            html.Span(site_id, style={'fontSize': '10px', 'fontWeight': '600', 'color': '#e0e0e0', 'marginRight': '10px'}),
            html.Span("State: ", style={'color': '#aaaaaa', 'fontSize': '10px'}),
            html.Span(state, style={'fontSize': '10px', 'color': '#e0e0e0'}),
        ], style={'marginBottom': '2px'}),
        html.Div([
            html.Span("Area: ", style={'color': '#aaaaaa', 'fontSize': '10px'}),
            html.Span(area, style={'fontSize': '10px', 'color': '#e0e0e0', 'marginRight': '10px'}),
            html.Span("Record: ", style={'color': '#aaaaaa', 'fontSize': '10px'}),
            html.Span(years, style={'fontSize': '10px', 'color': '#e0e0e0'}),
        ], style={'marginBottom': '2px'}),
        html.Div([
            html.Span("Condition: ", style={'color': '#aaaaaa', 'fontSize': '10px'}),
            html.Span(condition, style={'fontSize': '10px', 'fontWeight': '700', 'color': cond_color}),
        ], style={'marginBottom': '2px'}),
        html.Div([
            html.Span(f"{lat:.4f}°N, {lon:.4f}°W", style={'fontSize': '9px', 'color': '#888888'}),
        ]),
    ])

    return {'show': True, 'src': src, 'has_png': has_png}, info


# Map hover panel: position near cursor using window._hoverCursor (populated by hover_zoom.js).
app.clientside_callback(
    """
    function(storeData) {
        var hidden = {'display': 'none'};
        var noUpdate = window.dash_clientside.no_update;

        if (!storeData || !storeData.show) {
            return [hidden, noUpdate, {'display': 'none'}];
        }

        var cx = (window._hoverCursor && window._hoverCursor.x) || 0;
        var cy = (window._hoverCursor && window._hoverCursor.y) || 0;

        var hasPng  = storeData.has_png;
        var PW      = 462;
        var PH      = hasPng ? 357 : 116;
        var OFFSET  = 14;
        var vw = window.innerWidth, vh = window.innerHeight;
        var left = cx + OFFSET;
        var top  = cy - Math.round(PH / 2);
        if (left + PW > vw - 8) { left = cx - PW - OFFSET; }
        if (top < 8)             { top  = 8; }
        if (top + PH > vh - 8)  { top  = vh - PH - 8; }

        var panelStyle = {
            'display': 'block',
            'position': 'fixed',
            'left': left + 'px',
            'top':  top  + 'px',
            'width': PW + 'px',
            'zIndex': 9000,
            'backgroundColor': '#252525',
            'border': '1px solid #444444',
            'borderRadius': '8px',
            'boxShadow': '0 6px 24px rgba(0,0,0,0.65)',
            'padding': '0',
            'overflow': 'hidden',
            'pointerEvents': 'none',
        };

        var imgStyle = hasPng
            ? {'display': 'block', 'width': '462px', 'height': '268px', 'borderRadius': '0 0 6px 6px'}
            : {'display': 'none'};

        return [panelStyle, storeData.src || '', imgStyle];
    }
    """,
    [Output('map-hover-panel', 'style'),
     Output('map-hover-tooltip-img', 'src'),
     Output('map-hover-tooltip-img', 'style')],
    Input('map-tooltip-store', 'data'),
)


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