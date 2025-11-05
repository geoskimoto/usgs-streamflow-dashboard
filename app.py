"""
USGS Streamflow Dashboard

Interactive web dashboard for exploring USGS streamflow gauges 
in the Pacific Northwest (Oregon, Washington, Idaho).
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title=APP_TITLE,
    update_title='Loading...'
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
            /* Force side-by-side layout */
            .sidebar-col {
                background-color: #f8f9fa;
                border-right: 1px solid #dee2e6;
                min-height: 100vh;
                padding: 1rem;
                flex: 0 0 auto !important;  /* Don't grow or shrink, fixed size */
                overflow-y: auto;
            }
            
            .main-content-col {
                padding: 1rem;
                transition: all 0.3s ease-in-out;
                overflow-x: auto;  /* Allow horizontal scrolling if needed */
                min-width: 0;  /* Allow shrinking */
            }
            
            /* Force flexbox row layout */
            .flex-nowrap {
                flex-wrap: nowrap !important;
                display: flex !important;
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
            
            /* Ensure responsive text on smaller screens */
            @media (max-width: 992px) {
                .sidebar-col {
                    font-size: 0.9rem;
                }
                .sidebar-col .card-header h5 {
                    font-size: 1rem;
                }
            }
        </style>
    </head>
    <body>
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
                           className="lead mb-3 text-center",
                           style={
                               "fontSize": "1.1rem",
                               "color": "#6c757d",
                               "maxWidth": "800px",
                               "margin": "0 auto",
                               "lineHeight": "1.6"
                           }),
                    html.Hr(style={"width": "60%", "margin": "1.5rem auto", "border": "2px solid #e9ecef"}),
                ], style={
                    "background": "linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%)",
                    "padding": "2rem 1rem",
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
                # Data refresh controls
                html.H6("Data Management", className="text-muted mb-2"),
                dbc.ButtonGroup([
                    dbc.Button("🔄 Refresh Gauges", id="refresh-gauges-btn", 
                              color="primary", size="sm"),
                    dbc.Button("🗑️ Clear Cache", id="clear-cache-btn", 
                              color="warning", size="sm")
                ], className="mb-3 w-100"),
                
                html.Hr(),
                
                # Site limit controls
                html.H6("Site Loading", className="text-muted mb-2"),
                dbc.Label("Max Sites to Load:"),
                dbc.Input(
                    id="site-limit-input",
                    type="number",
                    min=1,
                    max=3000,
                    step=1,
                    value=300,
                    className="mb-2"
                ),
                html.P("Enter number of sites (1-3000). Higher values take longer to load.", 
                      className="small text-muted mb-3"),
                html.Div(id="site-limit-feedback", className="mb-3"),
                
                html.Hr(),
                
                # Map controls
                html.H6("Map Settings", className="text-muted mb-2"),
                
                dbc.Label("Map Style:"),
                dcc.Dropdown(
                    id="map-style-dropdown",
                    options=[
                        {"label": "🏞️ USGS National Map", "value": "usgs-national"},
                        {"label": "🗺️ OpenStreetMap", "value": "open-street-map"},
                        {"label": "🌍 Carto Positron", "value": "carto-positron"},
                        {"label": "🌚 Carto Dark", "value": "carto-darkmatter"},
                        {"label": "🏔️ Stamen Terrain", "value": "stamen-terrain"},
                        {"label": "⚫ Stamen Toner", "value": "stamen-toner"},
                        {"label": "� Stamen Watercolor", "value": "stamen-watercolor"},
                        {"label": "📰 White Background", "value": "white-bg"}
                    ],
                    value="usgs-national",  # Set USGS National Map as default
                    className="mb-3"
                ),
                
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
                        {"label": "📱 Compact (300px)", "value": 300},
                        {"label": "📊 Standard (400px)", "value": 400},
                        {"label": "🖥️ Large (600px)", "value": 600},
                        {"label": "📺 Extra Large (800px)", "value": 800},
                    ],
                    value=400,  # Default current size
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
                        {"label": "🗺️ OpenStreetMap", "value": "open-street-map"},
                        {"label": "🌍 Carto Positron", "value": "carto-positron"},
                        {"label": "🌚 Carto Dark", "value": "carto-darkmatter"},
                        {"label": "🏔️ Stamen Terrain", "value": "stamen-terrain"},
                        {"label": "⚫ Stamen Toner", "value": "stamen-toner"},
                        {"label": "🎨 Stamen Watercolor", "value": "stamen-watercolor"},
                        {"label": "📰 White Background", "value": "white-bg"}
                    ],
                    value="usgs-national",
                    className="mb-3"
                ),
                
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
                        {"label": "📱 Compact (300px)", "value": 300},
                        {"label": "📊 Standard (400px)", "value": 400},
                        {"label": "🖥️ Large (600px)", "value": 600},
                        {"label": "📺 Extra Large (800px)", "value": 800},
                    ],
                    value=400,
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
    from admin_components import create_enhanced_admin_content
    
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
                    
                    # Legacy Data Management Section (keeping existing functionality)
                    html.H5("📊 Legacy Data Management", className="text-primary mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H6("Site Loading Controls"),
                                    dbc.Label("Max Sites to Load:"),
                                    dbc.Input(
                                        id="site-limit-input",
                                        type="number",
                                        min=1,
                                        max=3000,
                                        step=1,
                                        value=300,
                                        className="mb-2"
                                    ),
                                    html.P("Enter number of sites (1-3000). Higher values take longer to load.", 
                                          className="small text-muted mb-3"),
                                    html.Div(id="site-limit-feedback", className="mb-3"),
                                ])
                            ])
                        ], width=6),
                        
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H6("Data Operations"),
                                    dbc.ButtonGroup([
                                        dbc.Button("🔄 Refresh Gauges", id="refresh-gauges-btn", 
                                                  color="primary", size="sm"),
                                        dbc.Button("🗑️ Clear Cache", id="clear-cache-btn", 
                                                  color="warning", size="sm")
                                    ], className="mb-3 w-100"),
                                    
                                    dbc.Button("📥 Export Data", id="export-data-btn", 
                                              color="success", size="sm", className="w-100 mb-2"),
                                    dbc.Button("🔍 System Status", id="system-status-btn", 
                                              color="info", size="sm", className="w-100"),
                                ])
                            ])
                        ], width=6),
                    ], className="mb-4"),
                    
                    # Data Update Management Section
                    html.H5("🔄 Automated Data Updates", className="text-primary mb-3"),
                    html.P("Data updates are managed through the station configuration system. "
                          "Use the Station Management tab to configure which stations to collect data for.",
                          className="text-muted mb-4"),
                    
                    # Job Execution History
                    html.H6("📋 Recent Update History", className="text-info mb-2"),
                    html.Div(id="job-history-display", className="mb-4"),
                    
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
            dbc.CardHeader([
                html.H5("🗺️ USGS Streamflow Gauges Map", className="mb-0 d-inline"),
                dbc.Badge(
                    id="gauge-count-badge",
                    color="info",
                    className="float-end"
                )
            ]),
            dbc.CardBody([
                dcc.Loading(
                    id="loading-map",
                    type="default",
                    children=[
                        dcc.Graph(
                            id="gauge-map",
                            style={"height": "700px"},  # This will be updated dynamically
                            config={"displayModeBar": True, "displaylogo": False}
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
                dcc.Loading(
                    id="loading-multiplot",
                    type="default",
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
                "◀️ Hide Sidebar", 
                id="sidebar-toggle-btn", 
                color="outline-secondary", 
                size="sm",
                className="float-end"
            )
        ], width="auto")
    ], className="mb-3 d-flex justify-content-between align-items-center"),
    
    # Dashboard content (always exists, just hidden/shown)
    html.Div([
        dbc.Row([
            # Sidebar - always present, visibility controlled by CSS
            dbc.Col(
                create_public_sidebar(),
                width=3,  # Fixed 3 columns when visible
                className="sidebar-col flex-shrink-0",
                id="sidebar-col",
                style={"minWidth": "250px", "maxWidth": "300px", "display": "block"}  # Start visible
            ),
            # Main content - takes remaining space
            dbc.Col(
                create_main_content(),
                id="main-content-wrapper",
                className="main-content-col flex-grow-1",  # Initial state: sidebar open
                style={"minWidth": "0"}  # Allow shrinking
            )
        ], className="flex-nowrap g-0", style={"minHeight": "100vh"})
    ], id="dashboard-content", style={"display": "block"}),
    
    # Admin content (always exists, just hidden/shown) 
    html.Div([
        create_admin_content()
    ], id="admin-content", style={"display": "none"}),
    
    # Login modal - ALWAYS exists in layout
    create_login_modal(),
    
    # Store components for data persistence and authentication
    dcc.Store(id='gauges-store'),
    dcc.Store(id='selected-gauge-store'),
    dcc.Store(id='streamflow-data-store'),
    dcc.Store(id='site-limit-store', data=300),
    dcc.Store(id='auth-store', data={'authenticated': False}),
    
    # Toast container for notifications
    html.Div(id='toast-container', style={
        'position': 'fixed',
        'top': '80px',
        'right': '20px',
        'zIndex': '9999',
        'width': '350px'
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

@app.callback(
    [Output('realtime-status', 'children'),
     Output('daily-status', 'children'),
     Output('job-history-display', 'children')],
    [Input('refresh-gauges-btn', 'n_clicks'),  # Trigger on page refresh
     Input('run-realtime-btn', 'n_clicks'),
     Input('run-daily-btn', 'n_clicks'),
     Input('toggle-realtime-btn', 'n_clicks'),
     Input('toggle-daily-btn', 'n_clicks')],
    [State('auth-store', 'data')],
    prevent_initial_call=False
)
def update_job_status_and_history(refresh_clicks, run_rt_clicks, run_daily_clicks, 
                                toggle_rt_clicks, toggle_daily_clicks, auth_data):
    """Update job status displays and execution history."""
    if not auth_data or not auth_data.get('authenticated'):
        return "Not authenticated", "Not authenticated", "Authentication required"
    
    try:
        import sqlite3
        conn = sqlite3.connect('data/usgs_cache.db')
        cursor = conn.cursor()
        
        # Get current schedule configuration
        cursor.execute("""
            SELECT job_name, frequency_hours, last_run, next_run, enabled 
            FROM update_schedules
            ORDER BY job_name
        """)
        schedules = cursor.fetchall()
        
        realtime_status = "Configuration not found"
        daily_status = "Configuration not found"
        
        for job_name, freq_hours, last_run, next_run, enabled in schedules:
            status_text = "🟢 Enabled" if enabled else "🔴 Disabled"
            if last_run:
                last_run_formatted = last_run[:19].replace('T', ' ')
                status_detail = f"{status_text} | Every {freq_hours}h | Last: {last_run_formatted}"
            else:
                status_detail = f"{status_text} | Every {freq_hours}h | Never run"
            
            if job_name == 'realtime_update':
                realtime_status = status_detail
            elif job_name == 'daily_update':
                daily_status = status_detail
        
        # Get recent job execution history
        cursor.execute("""
            SELECT job_name, start_time, status, sites_processed, sites_failed, error_message
            FROM job_execution_log
            ORDER BY start_time DESC
            LIMIT 10
        """)
        history = cursor.fetchall()
        
        if history:
            history_items = []
            for job_name, start_time, status, sites_proc, sites_fail, error_msg in history:
                start_formatted = start_time[:19].replace('T', ' ')
                
                if status == 'success':
                    status_badge = dbc.Badge("✅ Success", color="success")
                elif status == 'partial':
                    status_badge = dbc.Badge("⚠️ Partial", color="warning")
                else:
                    status_badge = dbc.Badge("❌ Failed", color="danger")
                
                job_display = "📊 Real-time" if job_name == 'realtime_update' else "📈 Daily"
                
                history_items.append(
                    html.Div([
                        dbc.Row([
                            dbc.Col([
                                html.Strong(job_display),
                                html.Br(),
                                html.Small(start_formatted, className="text-muted")
                            ], width=3),
                            dbc.Col(status_badge, width=2),
                            dbc.Col([
                                html.Small(f"Sites: {sites_proc} ✅, {sites_fail} ❌")
                            ], width=4),
                            dbc.Col([
                                html.Small(error_msg[:50] + "..." if error_msg and len(error_msg) > 50 else error_msg or "")
                            ], width=3)
                        ], className="align-items-center")
                    ], className="mb-2 p-2 border-bottom")
                )
            
            job_history = html.Div(history_items)
        else:
            job_history = html.P("No job execution history found", className="text-muted")
        
        conn.close()
        
        return realtime_status, daily_status, job_history
        
    except Exception as e:
        return f"Error: {str(e)}", f"Error: {str(e)}", f"Error loading history: {str(e)}"

@app.callback(
    Output('realtime-frequency-input', 'value'),
    Input('realtime-frequency-input', 'value'),
    [State('auth-store', 'data')],
    prevent_initial_call=True
)
def update_realtime_frequency(frequency, auth_data):
    """Update real-time job frequency in database."""
    if not auth_data or not auth_data.get('authenticated'):
        return 2  # Default
    
    if frequency and 1 <= frequency <= 24:
        try:
            import sqlite3
            conn = sqlite3.connect('data/usgs_cache.db')
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE update_schedules 
                SET frequency_hours = ?, modified_at = datetime('now')
                WHERE job_name = 'realtime_update'
            """, (frequency,))
            conn.commit()
            conn.close()
            return frequency
        except Exception as e:
            print(f"Error updating realtime frequency: {e}")
    
    return 2  # Default fallback

@app.callback(
    Output('daily-frequency-input', 'value'),
    Input('daily-frequency-input', 'value'),
    [State('auth-store', 'data')],
    prevent_initial_call=True
)
def update_daily_frequency(frequency, auth_data):
    """Update daily job frequency in database."""
    if not auth_data or not auth_data.get('authenticated'):
        return 12  # Default
    
    if frequency and 6 <= frequency <= 72:
        try:
            import sqlite3
            conn = sqlite3.connect('data/usgs_cache.db')
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE update_schedules 
                SET frequency_hours = ?, modified_at = datetime('now')
                WHERE job_name = 'daily_update'
            """, (frequency,))
            conn.commit()
            conn.close()
            return frequency
        except Exception as e:
            print(f"Error updating daily frequency: {e}")
    
    return 12  # Default fallback

# Manual job execution callbacks


# Admin Panel Callbacks

@app.callback(
    [Output('admin-system-info', 'children')],
    [Input('system-status-btn', 'n_clicks')],
    [State('auth-store', 'data')],
    prevent_initial_call=True
)
def show_system_status(clicks, auth_data):
    """Show system status information."""
    if not auth_data or not auth_data.get('authenticated'):
        return [dbc.Alert("Authentication required", color="danger")]
    
    if clicks:
        try:
            import sqlite3
            import os
            from datetime import datetime
            
            # Get database info
            db_path = "data/usgs_cache.db"
            db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0
            db_size_mb = db_size / (1024 * 1024)
            
            # Get cache stats
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Count cached data
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = cursor.fetchone()[0]
            
            conn.close()
            
            return [dbc.Card([
                dbc.CardBody([
                    html.H6("Database Status"),
                    html.P(f"📁 Cache size: {db_size_mb:.2f} MB"),
                    html.P(f"📊 Tables: {table_count}"),
                    html.P(f"🕐 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
                ])
            ])]
            
        except Exception as e:
            return [dbc.Alert(f"Error getting system status: {str(e)}", color="warning")]
    
    return [html.P("Click 'System Status' to view information.", className="text-muted")]


@app.callback(
    [Output('admin-activity-log', 'children')],
    [Input('main-tabs', 'active_tab')],
    [State('auth-store', 'data')],
    prevent_initial_call=True
)
def show_activity_log(active_tab, auth_data):
    """Show recent activity log."""
    if active_tab != "admin-tab" or not auth_data or not auth_data.get('authenticated'):
        return [""]
    
    # Simulated activity log
    activities = [
        {"time": "10:30 AM", "action": "Dashboard accessed", "user": "Public"},
        {"time": "10:25 AM", "action": "Data refresh completed", "user": "System"},
        {"time": "10:20 AM", "action": "Admin login", "user": auth_data.get('username', 'Admin')},
    ]
    
    log_items = []
    for activity in activities:
        log_items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Small(activity["time"], className="text-muted float-end"),
                    html.Strong(activity["action"]),
                    html.Br(),
                    html.Small(f"User: {activity['user']}", className="text-muted")
                ])
            ])
        )
    
    return [dbc.ListGroup(log_items, flush=True)]


# Main Dashboard Callbacks

@app.callback(
    [Output('gauges-store', 'data'),
     Output('status-alerts', 'children'),
     Output('site-limit-store', 'data')],
    [Input('refresh-gauges-btn', 'n_clicks'),
     Input('site-limit-input', 'value')],
    prevent_initial_call=False
)
def load_gauge_data(refresh_clicks, site_limit):
    """Load gauge data on app start or refresh, using the filters table for metadata."""
    import sqlite3
    try:
        ctx = callback_context
        
        # Validate site limit input
        if site_limit is None or site_limit < 1:
            site_limit = 300
        elif site_limit > 3000:
            site_limit = 3000
        
        # Determine if this is a refresh or initial load
        refresh = False
        if ctx.triggered:
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if trigger_id == 'refresh-gauges-btn' and refresh_clicks:
                refresh = True
        
        # Always refresh the filters table if requested
        if refresh:
            data_manager.load_regional_gauges(refresh=True, max_sites=site_limit)
        
        # Load from filters table
        db_path = data_manager.cache_db
        conn = sqlite3.connect(db_path)
        filters_df = pd.read_sql_query('SELECT * FROM filters', conn)
        conn.close()
        
        global gauges_df
        gauges_df = filters_df.copy()
        
        # Convert binary columns to avoid serialization issues
        # years_of_record is stored as BLOB but not needed for map display
        if 'years_of_record' in gauges_df.columns:
            gauges_df = gauges_df.drop('years_of_record', axis=1)
        
        # Convert any remaining binary columns to None
        for col in gauges_df.columns:
            if gauges_df[col].dtype == object:
                # Check if any values are bytes
                sample = gauges_df[col].dropna().head(1)
                if len(sample) > 0 and isinstance(sample.iloc[0], bytes):
                    gauges_df[col] = None
        
        alert_msg = f"Successfully loaded {len(gauges_df)} USGS gauges from {', '.join(TARGET_STATES)} (limit: {site_limit})"
        
        alert = dbc.Alert(
            alert_msg,
            color="success",
            dismissable=True,
            duration=4000
        )
        return gauges_df.to_dict('records'), alert, site_limit
        
    except Exception as e:
        alert = dbc.Alert(
            f"Error loading gauge data: {str(e)}",
            color="danger",
            dismissable=True
        )
        return [], alert, site_limit or 300


@app.callback(
    Output('status-alerts', 'children', allow_duplicate=True),
    Input('clear-cache-btn', 'n_clicks'),
    prevent_initial_call=True
)
def clear_cache(n_clicks):
    """Clear the data cache."""
    if n_clicks:
        try:
            data_manager.clear_cache()
            return dbc.Alert(
                "Cache cleared successfully. Refresh gauges to reload data.",
                color="info",
                dismissable=True,
                duration=4000
            )
        except Exception as e:
            return dbc.Alert(
                f"Error clearing cache: {str(e)}",
                color="danger",
                dismissable=True
            )
    return no_update


@app.callback(
    Output('site-limit-feedback', 'children'),
    Input('site-limit-input', 'value')
)
def update_site_limit_feedback(site_limit):
    """Provide feedback for site limit input."""
    if site_limit is None:
        return ""
    
    if site_limit < 1:
        return dbc.Alert("Minimum 1 site required", color="warning", className="p-2")
    elif site_limit > 3000:
        return dbc.Alert("Maximum 3000 sites allowed", color="warning", className="p-2")
    elif site_limit > 1000:
        return dbc.Alert(f"Loading {site_limit} sites may take several minutes", color="info", className="p-2")
    else:
        return dbc.Alert(f"Will load {site_limit} sites", color="light", className="p-2")


@app.callback(
    [Output('gauge-map', 'figure'),
     Output('gauge-count-badge', 'children'),
     Output('results-count', 'children')],
    [Input('gauges-store', 'data'),
     Input('map-style-dropdown', 'value'),
     Input('map-height-dropdown', 'value'),
     Input('search-input', 'value'),
     Input('state-filter', 'value'),
     Input('drainage-area-filter', 'value'),
     Input('basin-filter', 'value'),
     Input('huc-filter', 'value'),
     Input('realtime-filter', 'value')],
    [State('selected-gauge-store', 'data')]
)
def update_map_with_simplified_filters(gauges_data, map_style, map_height, search_text, states, 
                                     drainage_range, basins, hucs, show_realtime_only, selected_gauge):
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
    
    # Convert data to DataFrame
    all_gauges = pd.DataFrame(gauges_data)
    original_count = len(all_gauges)
    
    # Apply filters
    filtered_gauges = all_gauges.copy()
    
    # Search filter
    if search_text and search_text.strip():
        search_lower = search_text.lower().strip()
        search_filter = (
            filtered_gauges['site_id'].str.lower().str.contains(search_lower, na=False) |
            filtered_gauges['station_name'].str.lower().str.contains(search_lower, na=False)
        )
        filtered_gauges = filtered_gauges[search_filter]
    
    # State filter (default to all if none selected)
    if states:
        filtered_gauges = filtered_gauges[filtered_gauges['state'].isin(states)]
    
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
    
    # Create map figure
    if len(filtered_gauges) > 0:
        fig = map_component.create_gauge_map(
            filtered_gauges,
            selected_gauge=selected_gauge,
            map_style=map_style,
            height=map_height,
            auto_fit_bounds=True  # Auto-fit bounds for filtered data
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
    
    # Add drainage area if available
    if pd.notna(gauge['drainage_area']) and gauge['drainage_area'] > 0:
        da_text = f"{gauge['drainage_area']:,.1f} sq mi"
        info_content.append(
            html.P([html.Strong("Drainage Area: "), da_text], className="mb-1")
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


# Multi-plot callback: generates all plots for selected site
@app.callback(
    Output('multi-plot-container', 'children'),
    [Input('selected-gauge-store', 'data'),
     Input('highlight-years-input', 'value'),
     Input('chart-height-dropdown', 'value'),
     Input('plot-options-checklist', 'value')],
    [State('gauges-store', 'data')]
)
def update_multi_plots(selected_gauge, highlight_years_text, chart_height, plot_options, gauges_data):
    """Generate and display all streamflow plots for the selected site."""
    if not selected_gauge:
        return [html.P("Select a gauge on the map to view streamflow plots.", className="text-muted")]
    
    # Parse highlight years
    highlight_years = []
    if highlight_years_text:
        try:
            years_str = highlight_years_text.replace(' ', '')
            if years_str:
                highlight_years = [int(year.strip()) for year in years_str.split(',') if year.strip().isdigit()]
            print(f"DEBUG: Parsed highlight years: {highlight_years} from input: '{highlight_years_text}'")
        except Exception as e:
            print(f"DEBUG: Error parsing highlight years: {e}")
            highlight_years = []
    
    # Set default visualization options (always enabled since they're controlled in Plotly)
    show_percentiles = True
    show_statistics = True
    print(f"DEBUG: Visualization options - percentiles: {show_percentiles}, statistics: {show_statistics}")
    
    # Get station name from gauges data
    station_name = "Unknown Station"
    if gauges_data:
        for gauge in gauges_data:
            if gauge.get('site_id') == selected_gauge:
                station_name = gauge.get('station_name', 'Unknown Station')
                break
    
    # Fetch streamflow data
    streamflow_data = data_manager.get_streamflow_data(selected_gauge)
    if streamflow_data is None or streamflow_data.empty:
        return [dbc.Alert(f"No streamflow data available for site {selected_gauge}", color="warning")]
    
    # Generate all plots
    plot_types = [
        ("Water Year Plot", "water_year"),
        ("Annual Summary", "annual"),
        ("Flow Duration Curve", "flow_duration")
    ]
    
    # Calculate current water year
    today = datetime.today()
    if today.month >= 10:
        current_wy = today.year + 1
    else:
        current_wy = today.year
    
    # Add current year to highlights if not already there
    if current_wy not in highlight_years:
        highlight_years.append(current_wy)
    
    cards = []
    for title, plot_type in plot_types:
        try:
            if plot_type == "flow_duration":
                fig = viz_manager.create_flow_duration_curve(selected_gauge, streamflow_data)
            elif plot_type == "water_year":
                fig = viz_manager.create_streamflow_plot(
                    selected_gauge,
                    streamflow_data,
                    plot_type=plot_type,
                    highlight_years=highlight_years,
                    show_percentiles=show_percentiles,
                    show_statistics=show_statistics,
                    data_manager=data_manager
                )
            else:
                fig = viz_manager.create_streamflow_plot(
                    selected_gauge,
                    streamflow_data,
                    plot_type=plot_type,
                    highlight_years=[],
                    show_percentiles=show_percentiles,
                    show_statistics=show_statistics,
                    data_manager=data_manager
                )
            
            # Configure plot options
            selected_options = plot_options or []
            
            # Set up graph configuration based on user options
            graph_config = {
                "displaylogo": False,
                "displayModeBar": "show_toolbar" in selected_options,
                "scrollZoom": "enable_zoom" in selected_options,
                "doubleClick": "autosize" if "enable_zoom" in selected_options else "reset"
            }
            
            # Set up graph style
            graph_style = {"height": f"{chart_height}px"}
            if "responsive" in selected_options:
                graph_style["width"] = "100%"
            
            cards.append(
                dbc.Card([
                    dbc.CardHeader(f"{title} - Site {selected_gauge} - {station_name}"),
                    dbc.CardBody([
                        dcc.Graph(figure=fig, config=graph_config, style=graph_style)
                    ])
                ], className="mb-3")
            )
        except Exception as e:
            print(f"Error creating {plot_type} plot: {e}")
            cards.append(
                dbc.Alert(f"Error generating {title}: {str(e)}", color="warning", className="mb-3")
            )
    
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
        
        # Get unique basins
        basins = state_filtered['basin'].dropna().unique()
        basin_options = [{"label": basin, "value": basin} for basin in sorted(basins)]
        
        # Get unique HUC codes
        huc_codes = state_filtered['huc_code'].dropna().unique()
        huc_options = [{"label": huc, "value": huc} for huc in sorted(huc_codes)]
        
        return basin_options, huc_options
    except Exception as e:
        print(f"Error updating dropdown options: {e}")
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
            'NV': '🏜️ Nevada'
        }
        
        for state in ['OR', 'WA', 'ID', 'MT', 'CA', 'NV']:
            count = state_counts.get(state, 0)
            if count > 0:  # Only show states that have stations
                label = f"{state_labels[state]} ({count} sites)"
                state_options.append({"label": label, "value": state})
        
        # Create summary text
        summary_text = f"Filter {total_sites} USGS streamflow gauges (1910-present)"
        
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


# Sidebar toggle callback
@app.callback(
    [Output("sidebar-col", "style"),
     Output("sidebar-toggle-btn", "children"),
     Output("main-content-wrapper", "className")],
    [Input("sidebar-toggle-btn", "n_clicks")],
    prevent_initial_call=False
)
def toggle_sidebar(n_clicks):
    """Toggle sidebar visibility and adjust main content width."""
    # Determine if sidebar should be hidden (odd number of clicks means hidden)
    is_hidden = n_clicks and (n_clicks % 2 == 1)
    
    if is_hidden:
        button_text = "▶️ Show Sidebar"
        # Hide sidebar completely
        sidebar_style = {"display": "none"}
        # Main content takes full width
        main_content_class = "main-content-col w-100"
    else:
        button_text = "◀️ Hide Sidebar"
        # Show sidebar with fixed width
        sidebar_style = {"minWidth": "250px", "maxWidth": "300px", "display": "block"}
        # Main content takes remaining space
        main_content_class = "main-content-col flex-grow-1"
    
    return sidebar_style, button_text, main_content_class


# =============================================
# ADMIN INTERFACE CALLBACKS
# =============================================

@app.callback(
    Output('admin-tab-content', 'children'),
    [Input('admin-dashboard-tab', 'n_clicks'),
     Input('admin-configs-tab', 'n_clicks'),
     Input('admin-stations-tab', 'n_clicks'),
     Input('admin-schedules-tab', 'n_clicks'),
     Input('admin-monitoring-tab', 'n_clicks')],
    [State('admin-tab-content', 'children')]
)
def update_admin_tab_content(dash_clicks, config_clicks, station_clicks, 
                           schedule_clicks, monitor_clicks, current_content):
    """Update admin tab content based on selected tab."""
    from admin_components import (get_configurations_table, get_system_health_display, 
                                get_recent_activity_table, StationAdminPanel)
    
    ctx = callback_context
    if not ctx.triggered:
        button_id = 'admin-dashboard-tab'
    else:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # If no button was actually clicked, return current content (prevents refresh interval from resetting tabs)
    if not any([dash_clicks, config_clicks, station_clicks, schedule_clicks, monitor_clicks]):
        return current_content or no_update
    
    try:
        if button_id == 'admin-configs-tab':
            return dbc.Container([
                html.H4("🎯 Station Configurations", className="mb-4"),
                get_configurations_table(),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button("➕ New Configuration", color="success", className="me-2"),
                        dbc.Button("📥 Import Stations", color="info", className="me-2"),
                        dbc.Button("📤 Export Configuration", color="secondary")
                    ])
                ], className="mt-3")
            ])
        
        elif button_id == 'admin-stations-tab':
            from admin_components import get_stations_table
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
            from admin_components import get_schedules_table
            return dbc.Container([
                html.H4("⏰ Schedule Management", className="mb-4"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Button("➕ New Schedule", id="new-schedule-btn", color="success", className="me-2", disabled=True),
                        dbc.Button("▶️ Run Selected", id="run-selected-schedule-btn", color="primary", className="me-2"),
                        dbc.Button("⏸️ Disable Selected", id="disable-schedule-btn", color="warning", className="me-2", disabled=True),
                        dbc.Button("🔄 Refresh", id="refresh-schedules-btn", color="info")
                    ])
                ], className="mb-4"),
                
                html.Div(id="schedule-status-message"),
                
                html.Div(id="schedules-table-container", children=[get_schedules_table()])
            ])
        
        elif button_id == 'admin-monitoring-tab':
            panel = StationAdminPanel()
            return panel.create_collection_monitoring()
        
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
     Output('admin-configs-tab', 'color'),
     Output('admin-stations-tab', 'color'),
     Output('admin-schedules-tab', 'color'),
     Output('admin-monitoring-tab', 'color')],
    [Input('admin-dashboard-tab', 'n_clicks'),
     Input('admin-configs-tab', 'n_clicks'),
     Input('admin-stations-tab', 'n_clicks'),
     Input('admin-schedules-tab', 'n_clicks'),
     Input('admin-monitoring-tab', 'n_clicks')]
)
def update_admin_tab_styles(dash_clicks, config_clicks, station_clicks, 
                          schedule_clicks, monitor_clicks):
    """Update tab button colors based on active tab."""
    ctx = callback_context
    if not ctx.triggered:
        active_tab = 'admin-dashboard-tab'
    else:
        active_tab = ctx.triggered[0]['prop_id'].split('.')[0]
    
    colors = ['outline-primary'] * 5
    tab_ids = ['admin-dashboard-tab', 'admin-configs-tab', 'admin-stations-tab', 
               'admin-schedules-tab', 'admin-monitoring-tab']
    
    if active_tab in tab_ids:
        colors[tab_ids.index(active_tab)] = 'primary'
    
    return colors


@app.callback(
    Output('stations-table-content', 'children'),
    [Input('filter-stations-btn', 'n_clicks')],
    [State('station-state-filter', 'value'),
     State('station-huc-filter', 'value'),
     State('station-source-filter', 'value'),
     State('station-search-filter', 'value')]
)
def filter_stations_table(n_clicks, states, huc_code, sources, search_text):
    """Filter stations table based on user input."""
    if not n_clicks:
        # Return default view on initial load
        from admin_components import get_stations_table
        return get_stations_table(limit=50)
    
    from admin_components import get_stations_table
    return get_stations_table(
        states=states,
        huc_code=huc_code.strip() if huc_code else None,
        source_datasets=sources,
        search_text=search_text.strip() if search_text else None,
        limit=200  # Higher limit when filtering
    )


@app.callback(
    [Output('system-health-indicators', 'children'),
     Output('recent-activity-table', 'children')],
    [Input('admin-refresh-interval', 'n_intervals'),
     Input('refresh-monitoring-btn', 'n_clicks')]
)
def update_monitoring_displays(n_intervals, refresh_clicks):
    """Update monitoring tab displays - runs every 30 seconds or on refresh button."""
    from admin_components import get_system_health_display, get_recent_activity_table
    
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
     Input('refresh-schedules-btn', 'n_clicks')],
    [State('schedules-table', 'selected_rows'),
     State('schedules-table', 'data')]
)
def handle_schedule_actions(run_clicks, refresh_clicks, selected_rows, table_data):
    """Handle schedule management actions (run, refresh)."""
    import subprocess
    import os
    from admin_components import get_schedules_table
    
    ctx = callback_context
    if not ctx.triggered:
        return "", get_schedules_table(), None
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Handle refresh
    if button_id == 'refresh-schedules-btn':
        return "", get_schedules_table(), None
    
    # Handle run selected
    if button_id == 'run-selected-schedule-btn':
        if not run_clicks:
            return "", get_schedules_table(), None
        
        if not selected_rows or len(selected_rows) == 0:
            return dbc.Alert("⚠️ Please select a schedule to run", color="warning", dismissable=True), get_schedules_table(), None
        
        # Get the selected schedule data
        selected_idx = selected_rows[0]
        if selected_idx >= len(table_data):
            return dbc.Alert("❌ Invalid selection", color="danger", dismissable=True), get_schedules_table(), None
        
        schedule_row = table_data[selected_idx]
        schedule_name = schedule_row['Schedule']
        config_name = schedule_row['Configuration']
        data_type = schedule_row['Data Type'].lower()
        
        try:
            # Determine which script to run
            if data_type == 'realtime':
                script = 'update_realtime_discharge_configurable.py'
            elif data_type == 'daily':
                script = 'update_daily_discharge_configurable.py'
            else:
                return dbc.Alert(f"❌ Unknown data type: {data_type}", color="danger", dismissable=True), get_schedules_table(), None
            
            # Build command
            project_root = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(project_root, script)
            
            # Create logs directory if it doesn't exist
            logs_dir = os.path.join(project_root, 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            
            # Create log files for this run
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(logs_dir, f'manual_run_{data_type}_{timestamp}.log')
            
            # Run in background
            cmd = [
                'python3', script_path,
                '--config', config_name
            ]
            
            # Debug: Print command for troubleshooting
            print(f"🚀 Starting collection process:")
            print(f"   Command: {' '.join(cmd)}")
            print(f"   Working directory: {project_root}")
            print(f"   Log file: {log_file}")
            
            # Start the collection process in background
            with open(log_file, 'w') as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,  # Redirect stderr to stdout (same log file)
                    cwd=project_root,
                    start_new_session=True  # Detach from parent process
                )
            
            print(f"   Process ID: {process.pid}")
            print(f"   Log file created: {log_file}")
            
            success_msg = dbc.Alert([
                html.H5(f"✅ Collection Started!", className="alert-heading"),
                html.P([
                    f"Schedule: {schedule_name}", html.Br(),
                    f"Configuration: {config_name}", html.Br(),
                    f"Data Type: {data_type.title()}", html.Br(),
                    html.Hr(),
                    html.Small([
                        "The collection is running in the background. ",
                        html.Strong("Check the Monitoring tab"), " to see live progress and results. ", html.Br(),
                        f"Process ID: {process.pid}", html.Br(),
                        f"Log file: logs/manual_run_{data_type}_{timestamp}.log"
                    ])
                ])
            ], color="success", dismissable=True)
            
            # Create toast notification
            toast = dbc.Toast(
                [html.P([
                    f"🔄 Collection started: {schedule_name}", html.Br(),
                    html.Small(f"{config_name} - {data_type.title()}", className="text-muted"), html.Br(),
                    html.Small("View progress in Monitoring tab →", className="text-info")
                ], className="mb-0 small")],
                header="Collection Started",
                icon="success",
                dismissable=True,
                is_open=True,
                duration=5000,  # Auto-dismiss after 5 seconds
                style={"position": "fixed", "top": 80, "right": 20, "width": 350, "zIndex": 9999}
            )
            
            return success_msg, get_schedules_table(), toast
            
        except Exception as e:
            error_msg = dbc.Alert([
                html.H5("❌ Error Starting Collection", className="alert-heading"),
                html.P(f"Error: {str(e)}")
            ], color="danger", dismissable=True)
            
            return error_msg, get_schedules_table(), None
    
    return "", get_schedules_table(), None


if __name__ == '__main__':
    import os
    
    print(f"Starting {APP_TITLE}...")
    
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