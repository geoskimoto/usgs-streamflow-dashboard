"""
Minimal Dashboard Admin Interface
SIMPLIFIED: Focuses only on UI/visualization settings
Data management features moved to DataOps web interface

This replaces the old admin_components.py (779 LOC) with a lightweight
interface (~200 LOC) that only manages dashboard-specific settings.

For data management tasks (stations, schedules, collections), use the
DataOps web interface at: http://localhost:8000/admin/
"""

import dash_bootstrap_components as dbc
from dash import html, dcc
import logging
from datetime import datetime
from typing import Dict, Any
import os

# Import adapter to check DataOps status
from dataops_adapter import DataOpsAdapter

logger = logging.getLogger(__name__)


def create_enhanced_admin_content():
    """
    Create minimal admin interface with links to DataOps.
    
    Returns:
    --------
    dash component
        Admin interface layout
    """
    dataops_url = os.getenv('DATAOPS_API_URL', 'https://streamflowops.3rdplaces.io')
    
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H2("📊 Dashboard Administration", className="text-primary mb-4"),
                html.P("Lightweight dashboard settings. For data management, use DataOps interface.",
                       className="text-muted"),
            ])
        ]),
        
        html.Hr(),
        
        # DataOps Integration Status
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("🔗 DataOps Integration Status", className="mb-0")),
                    dbc.CardBody([
                        html.Div(id='dataops-status-display'),
                        html.Div([
                            dbc.Button(
                                "🌐 Open DataOps Admin",
                                href=f"{dataops_url}/admin/",
                                target="_blank",
                                color="primary",
                                className="me-2"
                            ),
                            dbc.Button(
                                "📡 Check Connection",
                                id='check-dataops-btn',
                                color="secondary"
                            ),
                        ], className="mt-3")
                    ])
                ], className="mb-4")
            ])
        ]),
        
        # Dashboard Settings
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("⚙️ Dashboard Settings", className="mb-0")),
                    dbc.CardBody([
                        # Refresh Interval
                        dbc.Row([
                            dbc.Col([
                                html.Label("Auto-refresh Interval (minutes)"),
                                dcc.Slider(
                                    id='refresh-interval-slider',
                                    min=5,
                                    max=60,
                                    step=5,
                                    value=15,
                                    marks={5: '5m', 15: '15m', 30: '30m', 60: '1h'},
                                    tooltip={"placement": "bottom", "always_visible": True}
                                ),
                            ], md=6),
                            dbc.Col([
                                html.Label("Max Sites to Display"),
                                dcc.Slider(
                                    id='max-sites-slider',
                                    min=10,
                                    max=1000,
                                    step=10,
                                    value=100,
                                    marks={10: '10', 250: '250', 500: '500', 1000: '1k'},
                                    tooltip={"placement": "bottom", "always_visible": True}
                                ),
                            ], md=6),
                        ], className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Button(
                                    "💾 Save Settings",
                                    id='save-settings-btn',
                                    color="success",
                                    className="me-2"
                                ),
                                dbc.Button(
                                    "🔄 Reset to Defaults",
                                    id='reset-settings-btn',
                                    color="warning"
                                ),
                            ])
                        ])
                    ])
                ], className="mb-4")
            ])
        ]),
        
        # Quick Links
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H4("🔗 Quick Links", className="mb-0")),
                    dbc.CardBody([
                        dbc.ListGroup([
                            dbc.ListGroupItem([
                                html.I(className="bi bi-database me-2"),
                                html.A(
                                    "Manage Stations",
                                    href=f"{dataops_url}/admin/core/station/",
                                    target="_blank",
                                    className="text-decoration-none"
                                ),
                                html.Span(" - Add, edit, or remove monitoring stations", className="text-muted ms-2")
                            ]),
                            dbc.ListGroupItem([
                                html.I(className="bi bi-calendar-check me-2"),
                                html.A(
                                    "Collection Schedules",
                                    href=f"{dataops_url}/admin/scheduler/schedule/",
                                    target="_blank",
                                    className="text-decoration-none"
                                ),
                                html.Span(" - Configure data collection schedules", className="text-muted ms-2")
                            ]),
                            dbc.ListGroupItem([
                                html.I(className="bi bi-activity me-2"),
                                html.A(
                                    "Collection History",
                                    href=f"{dataops_url}/admin/scheduler/collectionrun/",
                                    target="_blank",
                                    className="text-decoration-none"
                                ),
                                html.Span(" - View collection run logs and status", className="text-muted ms-2")
                            ]),
                            dbc.ListGroupItem([
                                html.I(className="bi bi-graph-up me-2"),
                                html.A(
                                    "Data Explorer",
                                    href=f"{dataops_url}/api/discharge/",
                                    target="_blank",
                                    className="text-decoration-none"
                                ),
                                html.Span(" - Browse discharge data via API", className="text-muted ms-2")
                            ]),
                        ], flush=True)
                    ])
                ], className="mb-4")
            ])
        ]),
        
        # Help Section
        dbc.Row([
            dbc.Col([
                dbc.Alert([
                    html.H5("💡 Migration Notice", className="alert-heading"),
                    html.P([
                        "This dashboard now uses the DataOps system for all data management. ",
                        "The old admin interface has been archived and is no longer accessible."
                    ]),
                    html.Hr(),
                    html.P([
                        "To manage data operations, use the ",
                        html.A("DataOps admin interface", href=f"{dataops_url}/admin/", target="_blank"),
                        ". This dashboard focuses solely on data visualization."
                    ], className="mb-0")
                ], color="info")
            ])
        ])
        
    ], fluid=True)


def get_system_health_display():
    """
    Get system health display showing DataOps connection status.
    
    Returns:
    --------
    dash component
        System health display
    """
    try:
        adapter = DataOpsAdapter()
        status = adapter.get_status()
        
        if status.get('api_connected', False):
            health_color = "success"
            health_icon = "✅"
            health_text = "Connected to DataOps"
        else:
            health_color = "warning"
            health_icon = "⚠️"
            health_text = "Using cached data (API unavailable)"
        
        return dbc.Alert([
            html.H5(f"{health_icon} System Status", className="alert-heading"),
            html.P(health_text),
            html.Small([
                f"Mode: {status.get('mode', 'unknown')} | ",
                f"Cache: {'enabled' if status.get('cache_enabled') else 'disabled'} | ",
                f"API: {'enabled' if status.get('api_enabled') else 'disabled'}"
            ])
        ], color=health_color)
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return dbc.Alert([
            html.H5("❌ System Error", className="alert-heading"),
            html.P("Unable to check system status"),
            html.Small(str(e))
        ], color="danger")


def get_recent_activity_table():
    """
    Note: Activity tracking now handled by DataOps.
    This returns a redirect message.
    
    Returns:
    --------
    dash component
        Redirect message to DataOps
    """
    dataops_url = os.getenv('DATAOPS_API_URL', 'https://streamflowops.3rdplaces.io')
    
    return dbc.Alert([
        html.H5("📊 Collection Activity", className="alert-heading"),
        html.P("Collection activity is now tracked in the DataOps system."),
        dbc.Button(
            "View Collection History",
            href=f"{dataops_url}/admin/scheduler/collectionrun/",
            target="_blank",
            color="primary",
            size="sm"
        )
    ], color="info")


def get_system_info():
    """
    Get basic system information.
    
    Returns:
    --------
    dash component
        System info display
    """
    try:
        adapter = DataOpsAdapter()
        status = adapter.get_status()
        
        return dbc.Card([
            dbc.CardHeader(html.H5("ℹ️ System Information")),
            dbc.CardBody([
                dbc.Table([
                    html.Tbody([
                        html.Tr([html.Td("Dashboard Version"), html.Td("2.0 (DataOps Integration)")]),
                        html.Tr([html.Td("Data Source"), html.Td("DataOps API")]),
                        html.Tr([html.Td("Connection Mode"), html.Td(status.get('mode', 'unknown'))]),
                        html.Tr([html.Td("API Status"), html.Td(
                            "✅ Connected" if status.get('api_connected') else "❌ Disconnected"
                        )]),
                        html.Tr([html.Td("Cache Status"), html.Td(
                            "✅ Enabled" if status.get('cache_enabled') else "❌ Disabled"
                        )]),
                        html.Tr([html.Td("Last Updated"), html.Td(
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        )]),
                    ])
                ], bordered=True, hover=True, size="sm")
            ])
        ])
        
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return dbc.Alert(f"Error: {e}", color="danger")


# Legacy function stubs for backward compatibility
# These redirect to DataOps interface
def get_stations_table(*args, **kwargs):
    """Legacy function - redirects to DataOps"""
    dataops_url = os.getenv('DATAOPS_API_URL', 'https://streamflowops.3rdplaces.io')
    return dbc.Alert([
        html.P("Station management has moved to DataOps."),
        dbc.Button("Manage Stations", href=f"{dataops_url}/admin/core/station/", 
                   target="_blank", color="primary", size="sm")
    ], color="info")


def get_schedules_table(*args, **kwargs):
    """Legacy function - redirects to DataOps"""
    dataops_url = os.getenv('DATAOPS_API_URL', 'https://streamflowops.3rdplaces.io')
    return dbc.Alert([
        html.P("Schedule management has moved to DataOps."),
        dbc.Button("Manage Schedules", href=f"{dataops_url}/admin/scheduler/schedule/", 
                   target="_blank", color="primary", size="sm")
    ], color="info")
