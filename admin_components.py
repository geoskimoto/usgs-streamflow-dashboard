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
        return html.Div([
            # System health overview card
            dbc.Card([
                dbc.CardHeader([
                    html.H5("🏥 System Health", className="mb-0"),
                    dbc.Button("🔄 Refresh", id="refresh-monitoring-btn", color="info", size="sm", className="float-end")
                ]),
                dbc.CardBody([
                    html.Div(id="system-health-indicators")
                ])
            ], className="mb-4"),
            
            # Recent activity card
            dbc.Card([
                dbc.CardHeader(html.H5("📊 Recent Collection Activity", className="mb-0")),
                dbc.CardBody([
                    html.Div(id="recent-activity-table")
                ])
            ], className="mb-4")
        ])
    
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


def format_schedule_display(schedule_type, schedule_value, is_enabled):
    """Format schedule information for display."""
    if not schedule_type or not schedule_value:
        return "Not scheduled"
    
    if not is_enabled:
        return f"⏸️ {schedule_value} (disabled)"
    
    # Format common cron expressions
    if schedule_type == 'cron':
        if schedule_value == '0 * * * *':
            return "⏰ Hourly"
        elif schedule_value == '0 2 * * *':
            return "⏰ Daily at 02:00"
        elif schedule_value == '0 3 * * 0':
            return "⏰ Weekly (Sunday 03:00)"
        elif schedule_value.startswith('*/'):
            mins = schedule_value.split('/')[1].split()[0]
            return f"⏰ Every {mins} minutes"
        else:
            return f"⏰ {schedule_value}"
    elif schedule_type == 'interval':
        return f"⏰ Every {schedule_value}"
    
    return schedule_value

def get_configurations_table():
    """Get configurations as a formatted table with all schedules displayed."""
    try:
        import sqlite3
        
        # Query configurations and their schedules
        conn = sqlite3.connect('data/usgs_data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get configurations
        cursor.execute('''
            SELECT 
                c.config_id,
                c.config_name,
                c.description,
                c.is_active,
                c.is_default,
                COUNT(DISTINCT c.site_id) as station_count
            FROM configurations c
            GROUP BY c.config_id, c.config_name, c.description, c.is_active, c.is_default
            ORDER BY c.is_default DESC, c.config_name
        ''')
        
        configs = cursor.fetchall()
        
        if not configs:
            conn.close()
            return html.P("No configurations found.", className="text-muted")
        
        # Build table rows
        table_rows = []
        for config in configs:
            config_id = config['config_id']
            config_name = config['config_name']
            
            # Get all schedules for this configuration
            cursor.execute('''
                SELECT 
                    schedule_id,
                    schedule_name,
                    schedule_type,
                    schedule_value,
                    data_type,
                    is_enabled
                FROM schedules
                WHERE config_id = ?
                ORDER BY is_enabled DESC, schedule_id
            ''', (config_id,))
            
            schedules = cursor.fetchall()
            
            # Configuration header row
            config_row = html.Tr([
                html.Td(
                    dcc.RadioItems(
                        options=[{'label': '', 'value': config_name}],
                        id={'type': 'config-radio', 'index': config_name},
                        inline=True
                    ),
                    style={'width': '40px', 'vertical-align': 'middle'},
                    rowSpan=len(schedules) + 1 if schedules else 1
                ),
                html.Td(
                    [
                        html.Strong(config_name),
                        html.Br(),
                        html.Small(config['description'] or '', style={'color': '#666'}),
                        html.Br(),
                        html.Small(f"🗺️ {config['station_count']} stations", style={'color': '#007bff'}),
                        ' ',
                        html.Span('⭐ Default' if config['is_default'] else '', style={'color': '#ffc107'})
                    ],
                    colSpan=7,
                    style={'background-color': '#f8f9fa', 'font-weight': 'bold'}
                )
            ], style={'border-top': '2px solid #007bff'})
            
            table_rows.append(config_row)
            
            # Schedule rows
            if schedules:
                for schedule in schedules:
                    schedule_id = schedule['schedule_id']
                    schedule_name = schedule['schedule_name'] or 'Unnamed Schedule'
                    data_type = schedule['data_type'] or 'realtime'
                    is_enabled = schedule['is_enabled']
                    
                    # Format data type badge
                    if data_type == 'realtime':
                        data_badge = html.Span('⚡ Realtime', className='badge bg-info me-2')
                    elif data_type == 'daily':
                        data_badge = html.Span('📊 Daily', className='badge bg-primary me-2')
                    elif data_type == 'both':
                        data_badge = html.Span('🔄 Both', className='badge bg-success me-2')
                    else:
                        data_badge = html.Span(f'❓ {data_type}', className='badge bg-secondary me-2')
                    
                    schedule_display = format_schedule_display(
                        schedule['schedule_type'],
                        schedule['schedule_value'],
                        is_enabled
                    )
                    
                    schedule_row = html.Tr([
                        html.Td('   ' + schedule_name, style={'padding-left': '30px'}),
                        html.Td([data_badge], style={'text-align': 'center'}),
                        html.Td(schedule_display),
                        html.Td(
                            dbc.Checkbox(
                                id={'type': 'schedule-toggle', 'index': schedule_id},
                                value=is_enabled,
                                style={'transform': 'scale(1.2)'}
                            ),
                            style={'text-align': 'center'}
                        ),
                        html.Td(
                            dbc.Button(
                                "▶ Run",
                                id={'type': 'run-schedule', 'index': schedule_id},
                                size='sm',
                                color='success',
                                outline=True
                            ),
                            style={'text-align': 'center'}
                        )
                    ], style={'background-color': '#fff'})
                    
                    table_rows.append(schedule_row)
            else:
                # No schedules row
                no_schedule_row = html.Tr([
                    html.Td(
                        html.Em('No schedules configured', style={'color': '#999'}),
                        colSpan=5,
                        style={'padding-left': '30px', 'background-color': '#fff'}
                    )
                ])
                table_rows.append(no_schedule_row)
        
        conn.close()
        
        # Create table
        return dbc.Table([
            html.Thead(html.Tr([
                html.Th('', style={'width': '40px'}),
                html.Th('Schedule Name'),
                html.Th('Type', style={'text-align': 'center'}),
                html.Th('Timing'),
                html.Th('Enabled', style={'text-align': 'center'}),
                html.Th('Actions', style={'text-align': 'center'})
            ]), style={'backgroundColor': '#007bff', 'color': 'white'}),
            html.Tbody(table_rows)
        ], bordered=True, hover=True, responsive=True, striped=False, style={'font-size': '0.95em'})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
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
                    'schedule_id': schedule['id'],  # Hidden ID for reference
                    'config_id': schedule['config_id'],  # Hidden config ID
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
                id='schedules-table',
                data=table_data,
                columns=[
                    {'name': 'schedule_id', 'id': 'schedule_id'},  # Hidden
                    {'name': 'config_id', 'id': 'config_id'},  # Hidden
                    {'name': 'Status', 'id': 'Status'},
                    {'name': 'Schedule Name', 'id': 'Schedule'},
                    {'name': 'Configuration', 'id': 'Configuration'},
                    {'name': 'Type', 'id': 'Data Type'},
                    {'name': 'Cron Expression', 'id': 'Frequency'},
                    {'name': 'Last Run', 'id': 'Last Run'},
                    {'name': 'Next Run', 'id': 'Next Run'},
                    {'name': 'Runs', 'id': 'Run Count'}
                ],
                hidden_columns=['schedule_id', 'config_id'],  # Hide ID columns
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


def get_system_info():
    """Get comprehensive database and system information."""
    import os
    import sqlite3
    from pathlib import Path
    from datetime import datetime
    
    try:
        db_path = "data/usgs_data.db"
        
        if not os.path.exists(db_path):
            return dbc.Alert("Database not found!", color="danger")
        
        # Get database file size
        db_size_bytes = os.path.getsize(db_path)
        db_size_mb = db_size_bytes / (1024 * 1024)
        db_size_gb = db_size_bytes / (1024 * 1024 * 1024)
        
        if db_size_gb >= 1:
            db_size_str = f"{db_size_gb:.2f} GB"
        else:
            db_size_str = f"{db_size_mb:.2f} MB"
        
        # Get database modification time
        db_mtime = os.path.getmtime(db_path)
        db_modified = datetime.fromtimestamp(db_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        # Connect and get database information
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table information
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        
        # Get row counts for main tables
        table_stats = []
        main_tables = ['stations', 'configurations', 'schedules', 'collection_logs', 
                      'station_errors', 'streamflow_data', 'realtime_discharge']
        
        for table in main_tables:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_stats.append({'table': table, 'rows': f"{count:,}"})
        
        # Get active stations count
        cursor.execute("SELECT COUNT(*) FROM stations WHERE is_active = 1")
        active_stations = cursor.fetchone()[0]
        
        # Get total stations
        cursor.execute("SELECT COUNT(*) FROM stations")
        total_stations = cursor.fetchone()[0]
        
        # Get active configurations
        cursor.execute("SELECT COUNT(*) FROM configurations WHERE is_active = 1")
        active_configs = cursor.fetchone()[0]
        
        # Get date range for streamflow data
        cursor.execute("""
            SELECT MIN(start_date), MAX(end_date) 
            FROM streamflow_data
        """)
        date_range = cursor.fetchone()
        min_date = date_range[0] if date_range[0] else "N/A"
        max_date = date_range[1] if date_range[1] else "N/A"
        
        # Get realtime data info
        cursor.execute("""
            SELECT MIN(datetime_utc), MAX(datetime_utc), COUNT(DISTINCT site_no)
            FROM realtime_discharge
        """)
        realtime_info = cursor.fetchone()
        realtime_min = realtime_info[0] if realtime_info[0] else "N/A"
        realtime_max = realtime_info[1] if realtime_info[1] else "N/A"
        realtime_sites = realtime_info[2] if realtime_info[2] else 0
        
        conn.close()
        
        # Create information display
        return html.Div([
            # Database File Info
            dbc.Card([
                dbc.CardBody([
                    html.H6("💾 Database File", className="text-muted mb-3"),
                    dbc.Row([
                        dbc.Col([
                            html.Strong("File:"), html.Br(),
                            html.Code(db_path, style={'fontSize': '0.85rem'})
                        ], width=12, className="mb-2"),
                        dbc.Col([
                            html.Strong("Size:"), f" {db_size_str}",
                        ], width=6, className="mb-2"),
                        dbc.Col([
                            html.Strong("Last Modified:"), html.Br(),
                            html.Small(db_modified)
                        ], width=6, className="mb-2"),
                    ])
                ])
            ], className="mb-3"),
            
            # Key Metrics
            dbc.Card([
                dbc.CardBody([
                    html.H6("📊 Key Metrics", className="text-muted mb-3"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([
                                html.H4(f"{active_stations:,}", className="text-primary mb-0"),
                                html.Small("Active Stations", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                        dbc.Col([
                            html.Div([
                                html.H4(f"{total_stations:,}", className="text-secondary mb-0"),
                                html.Small("Total Stations", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                        dbc.Col([
                            html.Div([
                                html.H4(f"{active_configs:,}", className="text-success mb-0"),
                                html.Small("Active Configurations", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                        dbc.Col([
                            html.Div([
                                html.H4(f"{realtime_sites:,}", className="text-info mb-0"),
                                html.Small("Real-time Sites", className="text-muted")
                            ], className="text-center")
                        ], width=3),
                    ])
                ])
            ], className="mb-3"),
            
            # Table Statistics
            dbc.Card([
                dbc.CardBody([
                    html.H6("📋 Table Statistics", className="text-muted mb-3"),
                    dash_table.DataTable(
                        data=table_stats,
                        columns=[
                            {'name': 'Table Name', 'id': 'table'},
                            {'name': 'Row Count', 'id': 'rows'}
                        ],
                        style_cell={'textAlign': 'left', 'padding': '8px', 'fontSize': '0.9rem'},
                        style_header={'backgroundColor': '#f8f9fa', 'fontWeight': 'bold'},
                        style_data_conditional=[
                            {
                                'if': {'row_index': 'odd'},
                                'backgroundColor': '#f8f9fa'
                            }
                        ]
                    )
                ])
            ], className="mb-3"),
            
            # Data Coverage
            dbc.Card([
                dbc.CardBody([
                    html.H6("📅 Data Coverage", className="text-muted mb-3"),
                    dbc.Row([
                        dbc.Col([
                            html.Strong("Historical Daily Data:"), html.Br(),
                            html.Small(f"{min_date} to {max_date}", className="text-muted")
                        ], width=6, className="mb-2"),
                        dbc.Col([
                            html.Strong("Real-time Data:"), html.Br(),
                            html.Small(f"{realtime_min} to {realtime_max}", className="text-muted")
                        ], width=6, className="mb-2"),
                    ])
                ])
            ], className="mb-3"),
            
            # All Tables List
            dbc.Card([
                dbc.CardBody([
                    html.H6("🗂️ All Database Tables", className="text-muted mb-3"),
                    html.Div([
                        dbc.Badge(table, color="light", text_color="dark", className="me-2 mb-2")
                        for table in tables
                    ])
                ])
            ])
        ])
        
    except Exception as e:
        import traceback
        return dbc.Alert([
            html.H6("Error loading system information", className="mb-2"),
            html.Pre(str(e), style={'fontSize': '0.8rem'}),
            html.Hr(),
            html.Pre(traceback.format_exc(), style={'fontSize': '0.7rem', 'maxHeight': '200px', 'overflow': 'auto'})
        ], color="danger")