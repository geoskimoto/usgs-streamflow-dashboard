"""
Admin interface components for station configuration management.

This module provides the web-based admin panel components for managing
station configurations, monitoring collection status, and controlling
data collection operations.
"""

import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import json

from station_config_manager import StationConfigurationManager


class StationAdminPanel:
    """Admin panel for station configuration management."""
    
    def __init__(self):
        """Initialize the admin panel."""
        self.config_manager = StationConfigurationManager()
    
    def create_configuration_overview(self):
        """Create the configuration overview section."""
        return dbc.Card([
            dbc.CardHeader([
                html.H5("🎯 Station Configurations", className="mb-0"),
                dbc.Button("➕ New Configuration", id="new-config-btn", 
                          color="success", size="sm", className="float-end")
            ]),
            dbc.CardBody([
                html.Div(id="config-overview-content"),
                
                # Configuration details modal
                dbc.Modal([
                    dbc.ModalHeader(dbc.ModalTitle("Configuration Details")),
                    dbc.ModalBody(id="config-details-modal-body"),
                    dbc.ModalFooter([
                        dbc.Button("Edit", id="edit-config-btn", color="primary"),
                        dbc.Button("Close", id="close-config-modal", className="ms-auto")
                    ])
                ], id="config-details-modal", size="xl")
            ])
        ], className="mb-4")
    
    def create_station_browser(self):
        """Create the station browser section."""
        return dbc.Card([
            dbc.CardHeader([
                html.H5("🗺️ Station Browser", className="mb-0"),
                dbc.ButtonGroup([
                    dbc.Button("📍 Map View", id="station-map-btn", color="primary", size="sm"),
                    dbc.Button("📊 Table View", id="station-table-btn", color="outline-primary", size="sm"),
                ], className="float-end")
            ]),
            dbc.CardBody([
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
                            placeholder="Select states..."
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("HUC Code:"),
                        dbc.Input(
                            id="station-huc-filter",
                            placeholder="e.g., 1701 for Columbia Basin",
                            type="text"
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Source Dataset:"),
                        dcc.Dropdown(
                            id="station-source-filter",
                            options=[
                                {'label': 'HADS PNW', 'value': 'HADS_PNW'},
                                {'label': 'HADS Columbia', 'value': 'HADS_Columbia'}
                            ],
                            multi=True,
                            placeholder="Select source..."
                        )
                    ], width=3),
                    dbc.Col([
                        dbc.Label("Search:"),
                        dbc.Input(
                            id="station-search-filter",
                            placeholder="Station name or ID...",
                            type="text"
                        )
                    ], width=3)
                ], className="mb-3"),
                
                # Station content area
                html.Div(id="station-browser-content")
            ])
        ], className="mb-4")
    
    def create_collection_monitoring(self):
        """Create the collection monitoring section."""
        return dbc.Card([
            dbc.CardHeader([
                html.H5("📊 Collection Monitoring", className="mb-0"),
                dbc.ButtonGroup([
                    dbc.Button("▶️ Manual Run", id="manual-collection-btn", color="success", size="sm"),
                    dbc.Button("⏸️ Stop All", id="stop-collection-btn", color="danger", size="sm"),
                    dbc.Button("🔄 Refresh", id="refresh-monitoring-btn", color="info", size="sm")
                ], className="float-end")
            ]),
            dbc.CardBody([
                # System health overview
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H6("System Health", className="text-center"),
                                html.Div(id="system-health-indicators")
                            ])
                        ])
                    ], width=4),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H6("Collection Statistics (24h)", className="text-center"),
                                html.Div(id="collection-stats-24h")
                            ])
                        ])
                    ], width=4),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H6("Currently Running", className="text-center"),
                                html.Div(id="current-collections")
                            ])
                        ])
                    ], width=4)
                ], className="mb-3"),
                
                # Recent activity
                html.H6("Recent Collection Activity"),
                html.Div(id="recent-activity-table")
            ])
        ], className="mb-4")
    
    def create_schedule_management(self):
        """Create the schedule management section."""
        return dbc.Card([
            dbc.CardHeader([
                html.H5("⏰ Schedule Management", className="mb-0"),
                dbc.Button("➕ New Schedule", id="new-schedule-btn", 
                          color="success", size="sm", className="float-end")
            ]),
            dbc.CardBody([
                html.Div(id="schedule-management-content"),
                
                # Schedule editor modal
                dbc.Modal([
                    dbc.ModalHeader(dbc.ModalTitle("Schedule Editor")),
                    dbc.ModalBody([
                        dbc.Form([
                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Configuration:"),
                                    dcc.Dropdown(id="schedule-config-dropdown", placeholder="Select configuration...")
                                ], width=6),
                                dbc.Col([
                                    dbc.Label("Data Type:"),
                                    dcc.Dropdown(
                                        id="schedule-datatype-dropdown",
                                        options=[
                                            {'label': 'Real-time Data', 'value': 'realtime'},
                                            {'label': 'Daily Data', 'value': 'daily'},
                                            {'label': 'Both', 'value': 'both'}
                                        ],
                                        placeholder="Select data type..."
                                    )
                                ], width=6)
                            ], className="mb-3"),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Schedule Name:"),
                                    dbc.Input(id="schedule-name-input", placeholder="e.g., Columbia Basin - Hourly")
                                ], width=6),
                                dbc.Col([
                                    dbc.Label("Frequency:"),
                                    dcc.Dropdown(
                                        id="schedule-frequency-dropdown",
                                        options=[
                                            {'label': 'Every 15 minutes', 'value': '*/15 * * * *'},
                                            {'label': 'Every 30 minutes', 'value': '*/30 * * * *'},
                                            {'label': 'Every hour', 'value': '0 * * * *'},
                                            {'label': 'Every 6 hours', 'value': '0 */6 * * *'},
                                            {'label': 'Daily at 6 AM', 'value': '0 6 * * *'},
                                            {'label': 'Custom', 'value': 'custom'}
                                        ],
                                        placeholder="Select frequency..."
                                    )
                                ], width=6)
                            ], className="mb-3"),
                            dbc.Row([
                                dbc.Col([
                                    dbc.Label("Custom Cron Expression:"),
                                    dbc.Input(id="schedule-cron-input", placeholder="e.g., 0 */2 * * *")
                                ], width=12)
                            ])
                        ])
                    ]),
                    dbc.ModalFooter([
                        dbc.Button("Save Schedule", id="save-schedule-btn", color="primary"),
                        dbc.Button("Cancel", id="cancel-schedule-btn", className="ms-auto")
                    ])
                ], id="schedule-editor-modal")
            ])
        ])
    
    def create_system_overview(self):
        """Create system overview with key metrics."""
        return dbc.Card([
            dbc.CardHeader(html.H5("📈 System Overview", className="mb-0")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H6("📊 Quick Stats", className="text-primary"),
                        html.Div(id="system-quick-stats")
                    ], width=6),
                    dbc.Col([
                        html.H6("🔄 Next Scheduled Runs", className="text-primary"),
                        html.Div(id="next-scheduled-runs")
                    ], width=6)
                ])
            ])
        ], className="mb-4")


def create_enhanced_admin_content():
    """Create the enhanced admin content with station configuration management."""
    panel = StationAdminPanel()
    
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.H4("🔧 Station Configuration Admin", className="mb-0"),
                        dbc.ButtonGroup([
                            dbc.Button("📊 Dashboard", id="admin-dashboard-tab", color="primary", size="sm"),
                            dbc.Button("🎯 Configurations", id="admin-configs-tab", color="outline-primary", size="sm"),
                            dbc.Button("🗺️ Stations", id="admin-stations-tab", color="outline-primary", size="sm"),
                            dbc.Button("⏰ Schedules", id="admin-schedules-tab", color="outline-primary", size="sm"),
                            dbc.Button("📊 Monitoring", id="admin-monitoring-tab", color="outline-primary", size="sm")
                        ], className="float-end")
                    ]),
                    dbc.CardBody([
                        # Tab content area
                        html.Div(id="admin-tab-content")
                    ])
                ])
            ], width=12)
        ]),
        
        # Interval component for auto-refresh
        dcc.Interval(
            id='admin-refresh-interval',
            interval=30*1000,  # 30 seconds
            n_intervals=0
        ),
        
        # Store components for state management
        dcc.Store(id='admin-selected-config', data=None),
        dcc.Store(id='admin-selected-stations', data=[]),
        dcc.Store(id='admin-filter-state', data={})
    ], fluid=True)


def get_configurations_table():
    """Get configurations as a formatted table."""
    try:
        with StationConfigurationManager() as manager:
            configs = manager.get_configurations()
            
            if not configs:
                return html.P("No configurations found.", className="text-muted")
            
            # Create table data
            table_data = []
            for config in configs:
                table_data.append({
                    'Name': config['config_name'],
                    'Stations': config['actual_station_count'],
                    'Status': '✅ Active' if config['is_active'] else '❌ Inactive',
                    'Default': '⭐ Yes' if config['is_default'] else '',
                    'Created': config['created_date'][:10] if config['created_date'] else '',
                    'Description': config['description'] or 'No description'
                })
            
            return dash_table.DataTable(
                data=table_data,
                columns=[
                    {'name': 'Configuration', 'id': 'Name'},
                    {'name': 'Stations', 'id': 'Stations', 'type': 'numeric'},
                    {'name': 'Status', 'id': 'Status'},
                    {'name': 'Default', 'id': 'Default'},
                    {'name': 'Created', 'id': 'Created'},
                    {'name': 'Description', 'id': 'Description'}
                ],
                style_cell={'textAlign': 'left', 'padding': '10px'},
                style_data_conditional=[
                    {
                        'if': {'filter_query': '{Status} contains Active'},
                        'backgroundColor': '#d4edda',
                        'color': 'black',
                    }
                ],
                style_header={'backgroundColor': '#007bff', 'color': 'white', 'fontWeight': 'bold'},
                page_size=10,
                sort_action="native",
                row_selectable="single"
            )
    
    except Exception as e:
        return dbc.Alert(f"Error loading configurations: {e}", color="danger")


def get_system_health_display():
    """Get system health indicators."""
    try:
        with StationConfigurationManager() as manager:
            health = manager.get_system_health()
            
            return dbc.Row([
                dbc.Col([
                    html.H4(health['active_configurations'], className="text-primary mb-0"),
                    html.Small("Active Configs", className="text-muted")
                ], width=3),
                dbc.Col([
                    html.H4(f"{health['active_stations']:,}", className="text-success mb-0"),
                    html.Small("Active Stations", className="text-muted")
                ], width=3),
                dbc.Col([
                    html.H4(f"{health['recent_success_rate']}%", className="text-info mb-0"),
                    html.Small("Success Rate (24h)", className="text-muted")
                ], width=3),
                dbc.Col([
                    html.H4(health['currently_running'], className="text-warning mb-0"),
                    html.Small("Running Jobs", className="text-muted")
                ], width=3)
            ])
            
    except Exception as e:
        return dbc.Alert(f"Error loading system health: {e}", color="danger")


def get_recent_activity_table():
    """Get recent collection activity table."""
    try:
        with StationConfigurationManager() as manager:
            activities = manager.get_recent_collection_logs(limit=10)
            
            if not activities:
                return html.P("No recent activity.", className="text-muted")
            
            table_data = []
            for activity in activities:
                status_icon = "✅" if activity['status'] == 'completed' else "❌" if activity['status'] == 'failed' else "🔄"
                
                table_data.append({
                    'Status': f"{status_icon} {activity['status'].title()}",
                    'Configuration': activity['config_name'],
                    'Type': activity['data_type'].title(),
                    'Success Rate': f"{activity['stations_successful']}/{activity['stations_attempted']}",
                    'Duration': f"{activity['duration_minutes'] or 0:.1f} min",
                    'Started': activity['start_time'][-8:-3] if activity['start_time'] else '',  # Show time only
                    'Triggered By': activity['triggered_by']
                })
            
            return dash_table.DataTable(
                data=table_data,
                columns=[
                    {'name': 'Status', 'id': 'Status'},
                    {'name': 'Configuration', 'id': 'Configuration'},
                    {'name': 'Type', 'id': 'Type'},
                    {'name': 'Success', 'id': 'Success Rate'},
                    {'name': 'Duration', 'id': 'Duration'},
                    {'name': 'Time', 'id': 'Started'},
                    {'name': 'Triggered', 'id': 'Triggered By'}
                ],
                style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '12px'},
                style_header={'backgroundColor': '#007bff', 'color': 'white', 'fontWeight': 'bold'},
                page_size=5
            )
            
    except Exception as e:
        return dbc.Alert(f"Error loading recent activity: {e}", color="danger")


def get_stations_table(states=None, huc_code=None, source_datasets=None, search_text=None, limit=100):
    """Get stations table with filtering."""
    try:
        with StationConfigurationManager() as manager:
            # Get filtered stations
            stations = manager.get_stations_by_criteria(
                states=states,
                huc_codes=[huc_code] if huc_code else None,
                source_datasets=source_datasets,
                active_only=True
            )
            
            # Apply search filter
            if search_text:
                search_text = search_text.lower()
                stations = [s for s in stations if 
                           search_text in s['station_name'].lower() or 
                           search_text in s['usgs_id'].lower()]
            
            # Limit results
            stations = stations[:limit]
            
            if not stations:
                return html.P("No stations found matching criteria.", className="text-muted")
            
            # Create table data
            table_data = []
            for station in stations:
                table_data.append({
                    'USGS_ID': station['usgs_id'],
                    'Name': station['station_name'][:60] + '...' if len(station['station_name']) > 60 else station['station_name'],
                    'State': station['state'],
                    'HUC': station['huc_code'] or 'N/A',
                    'Source': station['source_dataset'].replace('HADS_', ''),
                    'Lat': f"{station['latitude']:.4f}",
                    'Lon': f"{station['longitude']:.4f}",
                    'Drainage': f"{station['drainage_area']:.1f}" if station['drainage_area'] else 'N/A'
                })
            
            return dbc.Container([
                dbc.Alert(f"Showing {len(table_data)} stations (limited to {limit})", color="info", className="mb-3"),
                
                dash_table.DataTable(
                    data=table_data,
                    columns=[
                        {'name': 'USGS ID', 'id': 'USGS_ID'},
                        {'name': 'Station Name', 'id': 'Name'},
                        {'name': 'State', 'id': 'State'},
                        {'name': 'HUC', 'id': 'HUC'},
                        {'name': 'Source', 'id': 'Source'},
                        {'name': 'Latitude', 'id': 'Lat'},
                        {'name': 'Longitude', 'id': 'Lon'},
                        {'name': 'Drainage (sq mi)', 'id': 'Drainage'}
                    ],
                    style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '12px'},
                    style_header={'backgroundColor': '#007bff', 'color': 'white', 'fontWeight': 'bold'},
                    style_data_conditional=[
                        {
                            'if': {'filter_query': '{Source} = Columbia'},
                            'backgroundColor': '#e3f2fd'
                        }
                    ],
                    page_size=20,
                    sort_action="native",
                    filter_action="native",
                    row_selectable="multi"
                )
            ])
            
    except Exception as e:
        return dbc.Alert(f"Error loading stations: {e}", color="danger")


def get_schedules_table():
    """Get schedules management table."""
    try:
        with StationConfigurationManager() as manager:
            configs = manager.get_configurations()
            
            all_schedules = []
            for config in configs:
                schedules = manager.get_schedules_for_configuration(config['id'], enabled_only=False)
                all_schedules.extend(schedules)
            
            if not all_schedules:
                return html.P("No schedules configured.", className="text-muted")
            
            table_data = []
            for schedule in all_schedules:
                status_icon = "✅" if schedule['is_enabled'] else "❌"
                
                table_data.append({
                    'Status': f"{status_icon} {'Enabled' if schedule['is_enabled'] else 'Disabled'}",
                    'Schedule': schedule['schedule_name'],
                    'Configuration': schedule['config_name'],
                    'Data Type': schedule['data_type'].title(),
                    'Frequency': schedule['cron_expression'],
                    'Last Run': schedule['last_run'][:16] if schedule['last_run'] else 'Never',
                    'Next Run': schedule['next_run'][:16] if schedule['next_run'] else 'Not scheduled',
                    'Run Count': schedule['run_count'] or 0
                })
            
            return dash_table.DataTable(
                data=table_data,
                columns=[
                    {'name': 'Status', 'id': 'Status'},
                    {'name': 'Schedule Name', 'id': 'Schedule'},
                    {'name': 'Configuration', 'id': 'Configuration'},
                    {'name': 'Type', 'id': 'Data Type'},
                    {'name': 'Cron Expression', 'id': 'Frequency'},
                    {'name': 'Last Run', 'id': 'Last Run'},
                    {'name': 'Next Run', 'id': 'Next Run'},
                    {'name': 'Runs', 'id': 'Run Count'}
                ],
                style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '12px'},
                style_header={'backgroundColor': '#007bff', 'color': 'white', 'fontWeight': 'bold'},
                style_data_conditional=[
                    {
                        'if': {'filter_query': '{Status} contains Enabled'},
                        'backgroundColor': '#d4edda'
                    },
                    {
                        'if': {'filter_query': '{Status} contains Disabled'},
                        'backgroundColor': '#f8d7da'
                    }
                ],
                page_size=15,
                sort_action="native",
                row_selectable="single"
            )
            
    except Exception as e:
        return dbc.Alert(f"Error loading schedules: {e}", color="danger")