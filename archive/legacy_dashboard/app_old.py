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

# Import dashboard components
from data.data_manager import get_data_manager
from components.map_component import get_map_component
from components.viz_manager import get_visualization_manager
from components.filter_panel import filter_component
from utils.config import (
    APP_TITLE, APP_DESCRIPTION, GAUGE_COLORS, 
    TARGET_STATES, DEFAULT_ZOOM_LEVEL, SUBSET_CONFIG
)


# Initialize components
data_manager = get_data_manager()
map_component = get_map_component()
viz_manager = get_visualization_manager()

# Initialize Dash app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title=APP_TITLE,
    update_title='Loading...'
)

# Expose the server for gunicorn
server = app.server

# Global variables
gauges_df = pd.DataFrame()
selected_gauge_id = None


def create_header():
    """Create the application header."""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1(APP_TITLE, className="display-4 text-primary mb-1"),
                html.P(APP_DESCRIPTION, className="lead mb-3"),
                html.Hr(),
            ])
        ])
    ], fluid=True)


def create_sidebar():
    """Create the sidebar with advanced filtering and controls."""
    return dbc.Col([
        # Advanced Filter Panel
        filter_component.create_filter_panel(),
        
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
                
                # Map controls
                html.H6("Map Settings", className="text-muted mb-2"),
                
                dbc.Label("Map Style:"),
                dcc.Dropdown(
                    id="map-style-dropdown",
                    options=[
                        {"label": "🗺️ OpenStreetMap", "value": "open-street-map"},
                        {"label": "🛰️ Satellite", "value": "satellite"},
                        {"label": "🏔️ Terrain", "value": "stamen-terrain"},
                        {"label": "📰 Toner", "value": "stamen-toner"}
                    ],
                    value="open-street-map",
                    className="mb-3"
                ),
                
                html.Hr(),
                
                # Visualization controls
                html.H6("Visualization Controls", className="text-muted mb-2"),
                
                # Plot Type dropdown removed
                
                dbc.Label("Years to Highlight (comma-separated):"),
                dbc.Input(
                    id="highlight-years-input",
                    type="text",
                    placeholder="e.g., 2015, 2020, 2021",
                    className="mb-2"
                ),
                
                dbc.Checklist(
                    options=[
                        {"label": "📊 Show Percentiles", "value": "percentiles"},
                        {"label": "📈 Show Statistics", "value": "statistics"}
                    ],
                    value=["percentiles", "statistics"],
                    id="viz-options-checklist",
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
        
        # Data subset controls
        dbc.Card([
            dbc.CardHeader(html.H5("🎯 Data Subset (Testing)", className="mb-0")),
            dbc.CardBody([
                html.P("Control data loading for faster testing and development.", 
                      className="text-muted small mb-2"),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Subset Mode:"),
                        dbc.Switch(
                            id="subset-enable-switch",
                            label="Enable Subset",
                            value=SUBSET_CONFIG['enabled'],
                            className="mb-2"
                        ),
                    ], width=12),
                ]),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Maximum Sites:"),
                        dcc.Dropdown(
                            id="subset-size-dropdown",
                            options=[
                                {"label": "100 sites", "value": 100},
                                {"label": "300 sites", "value": 300},
                                {"label": "500 sites", "value": 500},
                                {"label": "1000 sites", "value": 1000},
                                {"label": "ALL sites", "value": -1}
                            ],
                            value=SUBSET_CONFIG['max_sites'],
                            className="mb-2",
                            disabled=not SUBSET_CONFIG['enabled']
                        ),
                    ], width=12),
                ]),
                
                dbc.Row([
                    dbc.Col([
                        dbc.Label("Selection Method:"),
                        dcc.Dropdown(
                            id="subset-method-dropdown",
                            options=[
                                {"label": "🎯 Balanced (recommended)", "value": "balanced"},
                                {"label": "⭐ Top Quality", "value": "top_quality"},
                                {"label": "🎲 Random", "value": "random"}
                            ],
                            value=SUBSET_CONFIG['method'],
                            className="mb-2",
                            disabled=not SUBSET_CONFIG['enabled']
                        ),
                    ], width=12),
                ]),
                
                html.Hr(),
                
                dbc.Button(
                    "🔄 Regenerate Subset",
                    id="regenerate-subset-btn",
                    color="warning",
                    size="sm",
                    className="mb-2",
                    disabled=not SUBSET_CONFIG['enabled']
                ),
                
                html.Div(id="subset-status-content", className="small text-muted")
            ])
        ])
        
    ], width=2)  # Smaller width for sidebar


def create_main_content():
    """Create the main content area."""
    return dbc.Col([
        # Status alerts
        html.Div(id="status-alerts"),
        # Filter status bar
        filter_component.create_filter_status_bar(),
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
                            style={"height": "700px"},
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
    ], width=10)
# Multi-plot callback: generates all plots for selected site and displays them in the right column
@app.callback(
    Output('multi-plot-container', 'children'),
    [Input('selected-gauge-store', 'data')],
    [State('gauges-store', 'data')]
)
def update_multi_plots(selected_gauge, gauges_data):
    """Generate and display all streamflow plots for the selected site."""
    if not selected_gauge:
        return [html.P("Select a gauge on the map to view streamflow plots.", className="text-muted")]
    
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
        return [dbc.Alert(f"No streamflow data available for site {selected_gauge}", color="danger")]
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
    cards = []
    for title, plot_type in plot_types:
        if plot_type == "flow_duration":
            fig = viz_manager.create_flow_duration_curve(selected_gauge, streamflow_data)
        elif plot_type == "water_year":
            fig = viz_manager.create_streamflow_plot(
                selected_gauge,
                streamflow_data,
                plot_type=plot_type,
                highlight_years=[current_wy],
                show_percentiles=True,
                show_statistics=True
            )
        else:
            fig = viz_manager.create_streamflow_plot(
                selected_gauge,
                streamflow_data,
                plot_type=plot_type,
                highlight_years=[],
                show_percentiles=True,
                show_statistics=True
            )
        cards.append(
            dbc.Card([
                dbc.CardHeader(f"{title} - Site {selected_gauge} - {station_name}"),
                dbc.CardBody([
                    dcc.Graph(figure=fig, config={"displayModeBar": True, "displaylogo": False}, style={"height": "400px"})
                ])
            ], className="mb-3")
        )
    return cards


# Layout
app.layout = dbc.Container([
    create_header(),
    
    dbc.Row([
        create_sidebar(),
        create_main_content()
    ]),
    
    # Store components for data persistence
    dcc.Store(id='gauges-store'),
    dcc.Store(id='selected-gauge-store'),
    dcc.Store(id='streamflow-data-store'),
    dcc.Store(id='subset-config-store', data=SUBSET_CONFIG),
    
], fluid=True)


# Callbacks

@app.callback(
    [Output('gauges-store', 'data'),
     Output('status-alerts', 'children')],
    [Input('refresh-gauges-btn', 'n_clicks'),
     Input('regenerate-subset-btn', 'n_clicks')],
    [State('subset-config-store', 'data')],
    prevent_initial_call=False
)
def load_gauge_data(refresh_clicks, regenerate_clicks, subset_config):
    """Load gauge data on app start or refresh, using the filters table for metadata."""
    import sqlite3
    try:
        ctx = callback_context
        
        # Determine trigger and if this is a refresh or initial load
        refresh = False
        regenerate_subset = False
        
        if ctx.triggered:
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if trigger_id == 'refresh-gauges-btn' and refresh_clicks:
                refresh = True
            elif trigger_id == 'regenerate-subset-btn' and regenerate_clicks:
                regenerate_subset = True
                # Clear subset cache to force regeneration
                conn = sqlite3.connect(data_manager.cache_db)
                conn.execute("DELETE FROM subset_cache")
                conn.commit()
                conn.close()
        
        # Always refresh the filters table if requested
        if refresh or regenerate_subset:
            data_manager.load_regional_gauges(refresh=True)
        
        # Load from filters table
        db_path = data_manager.cache_db
        conn = sqlite3.connect(db_path)
        filters_df = pd.read_sql_query('SELECT * FROM filters', conn)
        conn.close()
        
        global gauges_df
        gauges_df = filters_df.copy()
        
        # Create appropriate alert message
        subset_status = data_manager.get_subset_status()
        if subset_status['enabled']:
            if regenerate_subset:
                alert_msg = f"Successfully regenerated subset: {len(gauges_df)} USGS gauges selected using '{subset_status['method']}' method"
            else:
                alert_msg = f"Successfully loaded {len(gauges_df)} USGS gauges from {', '.join(TARGET_STATES)} (subset mode: {subset_status['method']})"
        else:
            alert_msg = f"Successfully loaded {len(gauges_df)} USGS gauges from {', '.join(TARGET_STATES)} (full dataset)"
        
        alert = dbc.Alert(
            alert_msg,
            color="success",
            dismissable=True,
            duration=4000
        )
        return gauges_df.to_dict('records'), alert
        
    except Exception as e:
        alert = dbc.Alert(
            f"Error loading gauge data: {str(e)}",
            color="danger",
            dismissable=True
        )
        return [], alert


# Subset control callbacks
@app.callback(
    [Output('subset-size-dropdown', 'disabled'),
     Output('subset-method-dropdown', 'disabled'),
     Output('regenerate-subset-btn', 'disabled')],
    [Input('subset-enable-switch', 'value')]
)
def update_subset_controls(subset_enabled):
    """Enable/disable subset controls based on switch."""
    disabled = not subset_enabled
    return disabled, disabled, disabled


@app.callback(
    Output('subset-status-content', 'children'),
    [Input('gauges-store', 'data'),
     Input('subset-enable-switch', 'value')]
)
def update_subset_status(gauges_data, subset_enabled):
    """Update subset status display."""
    if not subset_enabled:
        return html.P("Subset mode disabled - using full dataset", className="text-muted")
    
    try:
        subset_status = data_manager.get_subset_status()
        
        if not gauges_data:
            return html.P("No data loaded", className="text-muted")
        
        status_parts = [
            html.P([
                html.Strong("Method: "), 
                subset_status['method'].replace('_', ' ').title()
            ], className="mb-1"),
            html.P([
                html.Strong("Sites loaded: "), 
                f"{len(gauges_data):,}"
            ], className="mb-1")
        ]
        
        if subset_status['has_cached_selection']:
            cache_date = datetime.fromisoformat(subset_status['cache_date']).strftime('%m/%d %H:%M')
            status_parts.append(
                html.P([
                    html.Strong("Cache: "), 
                    f"Generated {cache_date}"
                ], className="mb-0 small")
            )
        else:
            status_parts.append(
                html.P("No cached selection", className="mb-0 small text-warning")
            )
        
        return status_parts
        
    except Exception as e:
        return html.P(f"Error: {str(e)}", className="text-danger")


@app.callback(
    Output('subset-config-store', 'data'),
    [Input('subset-enable-switch', 'value'),
     Input('subset-size-dropdown', 'value'),
     Input('subset-method-dropdown', 'value')]
)
def update_subset_config(enabled, max_sites, method):
    """Update subset configuration when controls change."""
    config = SUBSET_CONFIG.copy()
    config['enabled'] = enabled
    if max_sites and max_sites > 0:
        config['max_sites'] = max_sites
    if method:
        config['method'] = method
    return config


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


# Advanced filtering callbacks

@app.callback(
    [Output("filter-help-collapse", "is_open")],
    [Input("filter-help-btn", "n_clicks")],
    [State("filter-help-collapse", "is_open")]
)
def toggle_filter_help(n_clicks, is_open):
    """Toggle filter help collapse."""
    if n_clicks:
        return [not is_open]
    return [is_open]


@app.callback(
    [Output("drainage-area-display", "children")],
    [Input("drainage-area-filter", "value")]
)
def update_drainage_area_display(drainage_range):
    """Update drainage area display."""
    if drainage_range:
        min_val, max_val = drainage_range
        if max_val >= 100000:
            return [f"Range: {min_val:,} - {max_val:,}+ sq mi"]
        else:
            return [f"Range: {min_val:,} - {max_val:,} sq mi"]
    return ["Range: All sizes"]


@app.callback(
    [Output("years-record-display", "children")],
    [Input("years-record-filter", "value")]
)
def update_years_record_display(years_range):
    """Update years of record display."""
    if years_range:
        min_val, max_val = years_range
        if max_val >= 50:
            return [f"Range: {min_val} - {max_val}+ years"]
        else:
            return [f"Range: {min_val} - {max_val} years"]
    return ["Range: All years"]


@app.callback(
    [Output("status-filter", "value"),
     Output("state-filter", "value"),
     Output("drainage-area-filter", "value"),
     Output("years-record-filter", "value"),
     Output("county-filter", "value"),
     Output("quality-filter", "value")],
    [Input("preset-streams", "n_clicks"),
     Input("preset-active", "n_clicks"),
     Input("preset-quality", "n_clicks"),
     Input("preset-reset", "n_clicks")]
)
def handle_filter_presets(streams_clicks, active_clicks, quality_clicks, reset_clicks):
    """Handle filter preset buttons."""
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update, no_update, no_update
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == "preset-streams":
        # Streams only preset
        return (
            ["active", "inactive"],  # All statuses
            ["OR", "WA", "ID"],  # All states
            [0, 100000],  # All drainage areas
            [1, 150],  # All years of record
            [],  # All counties
            ["complete_coords"]  # Basic quality
        )
    elif trigger_id == "preset-active":
        # Active only preset
        return (
            ["active"],  # Only active
            ["OR", "WA", "ID"],  # All states
            [0, 100000],  # All drainage areas
            [10, 150],  # 10+ years of record
            [],  # All counties
            ["complete_coords", "has_drainage_area"]  # Higher quality
        )
    elif trigger_id == "preset-quality":
        # Quality stations preset
        return (
            ["active"],  # Only active
            ["OR", "WA", "ID"],  # All states
            [10, 100000],  # Larger drainage areas
            [30, 150],  # 30+ years of record
            [],  # All counties
            ["complete_coords", "has_drainage_area", "has_county"]  # Highest quality
        )
    elif trigger_id == "preset-reset":
        # Reset all filters
        return (
            ["active", "inactive"],  # All statuses
            ["OR", "WA", "ID"],  # All states
            [0, 100000],  # All drainage areas
            [1, 150],  # All years of record
            [],  # All counties
            ["complete_coords"]  # Basic quality
        )
    
    return no_update, no_update, no_update, no_update, no_update, no_update


@app.callback(
    [Output('gauge-map', 'figure'),
     Output('gauge-count-badge', 'children'),
     Output('active-filter-count', 'children'),
     Output('total-gauge-count', 'children'),
     Output('filter-summary', 'children'),
     Output('filter-status-text', 'children')],
    [Input('gauges-store', 'data'),
     Input('map-style-dropdown', 'value'),
     Input('status-filter', 'value'),
     Input('state-filter', 'value'),
     Input('drainage-area-filter', 'value'),
     Input('years-record-filter', 'value'),
     Input('county-filter', 'value'),
     Input('quality-filter', 'value'),
     Input('selected-gauge-store', 'data')]
)
def update_map_with_advanced_filters(gauges_data, map_style, status_values, 
                                   state_values, drainage_range, years_range,
                                   county_values, quality_values, selected_gauge):
    """Update the gauge map based on advanced filters, using the new filtering system."""
    if not gauges_data:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Loading gauge data...",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=700
        )
        return empty_fig, "Loading...", "0", "0", "", ""
    
    # Convert data to DataFrame
    all_gauges = pd.DataFrame(gauges_data)
    original_count = len(all_gauges)
    
    # Build filter criteria dictionary
    filter_criteria = {}
    
    if status_values:
        filter_criteria['status'] = status_values
    
    if state_values:
        filter_criteria['states'] = state_values
    
    if drainage_range and len(drainage_range) == 2:
        filter_criteria['drainage_range'] = drainage_range
    
    if years_range and len(years_range) == 2:
        filter_criteria['years_range'] = years_range
    
    if county_values:
        filter_criteria['counties'] = county_values
    
    if quality_values:
        filter_criteria['quality'] = quality_values
    
    # Apply advanced filters using the new filtering system
    try:
        filtered_gauges = data_manager.apply_advanced_filters(all_gauges, filter_criteria)
    except Exception as e:
        print(f"Filter error: {e}")
        # Fallback to original logic if new filtering fails
        filtered_gauges = all_gauges.copy()
        
        # Status filter (use is_active from filters table)
        if status_values:
            if 'active' in status_values and 'inactive' not in status_values:
                filtered_gauges = filtered_gauges[filtered_gauges.get('is_active', 1) == 1]
            elif 'inactive' in status_values and 'active' not in status_values:
                filtered_gauges = filtered_gauges[filtered_gauges.get('is_active', 1) == 0]
        
        # State filter
        if state_values:
            filtered_gauges = filtered_gauges[filtered_gauges['state'].isin(state_values)]
        
        # Drainage area filter
        if drainage_range and len(drainage_range) == 2:
            min_area, max_area = drainage_range
            area_filter = (
                (filtered_gauges['drainage_area'] >= min_area) & 
                (filtered_gauges['drainage_area'] <= max_area)
            )
            filtered_gauges = filtered_gauges[area_filter]
        
        # Years of record filter
        if years_range and len(years_range) == 2:
            min_years, max_years = years_range
            years_filter = (
                (filtered_gauges.get('years_of_record', 0) >= min_years) &
                (filtered_gauges.get('years_of_record', 0) <= max_years)
            )
            filtered_gauges = filtered_gauges[years_filter]
        
        # County filter
        if county_values:
            filtered_gauges = filtered_gauges[filtered_gauges.get('county', '').isin(county_values)]
        
        # Quality filters
        if quality_values:
            for quality_req in quality_values:
                if quality_req == 'complete_coords':
                    coord_filter = (
                        pd.notna(filtered_gauges['latitude']) & 
                        pd.notna(filtered_gauges['longitude'])
                    )
                    filtered_gauges = filtered_gauges[coord_filter]
                elif quality_req == 'has_drainage_area':
                    filtered_gauges = filtered_gauges[
                        (pd.notna(filtered_gauges['drainage_area'])) & 
                        (filtered_gauges['drainage_area'] > 0)
                    ]
                elif quality_req == 'min_years':
                    filtered_gauges = filtered_gauges[
                        filtered_gauges.get('years_of_record', 0) >= 1
                    ]
                elif quality_req == 'has_county':
                    filtered_gauges = filtered_gauges[
                        pd.notna(filtered_gauges.get('county', '')) & 
                        (filtered_gauges.get('county', '') != '')
                    ]
    
    # Create map figure
    if len(filtered_gauges) > 0:
        fig = map_component.create_gauge_map(
            filtered_gauges,
            selected_gauge=selected_gauge,
            map_style=map_style
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
    active_count = len(filtered_gauges[filtered_gauges.get('is_active', 0) == 1]) if filtered_count > 0 else 0
    
    # Check if subset mode is enabled
    subset_status = data_manager.get_subset_status()
    if subset_status['enabled']:
        gauge_badge = f"{filtered_count:,} (subset)"
    else:
        gauge_badge = f"{filtered_count:,} / {original_count:,}"
    
    active_badge = f"{active_count:,} Active"
    total_badge = f"{original_count:,} Total"
    
    # Create enhanced filter summary
    filter_parts = []
    if status_values and len(status_values) < 2:
        filter_parts.append(f"Status: {', '.join(status_values)}")
    
    if state_values and len(state_values) < 3:
        filter_parts.append(f"States: {', '.join(state_values)}")
    
    if drainage_range and drainage_range != [0, 100000]:
        min_da, max_da = drainage_range
        if max_da >= 100000:
            filter_parts.append(f"Drainage: ≥{min_da:,} sq mi")
        else:
            filter_parts.append(f"Drainage: {min_da:,}-{max_da:,} sq mi")
    
    if years_range and years_range != [0, 50]:
        min_years, max_years = years_range
        if max_years >= 50:
            filter_parts.append(f"Years: ≥{min_years} years")
        else:
            filter_parts.append(f"Years: {min_years}-{max_years} years")
    
    if county_values:
        filter_parts.append(f"Counties: {len(county_values)} selected")
    
    if quality_values:
        quality_labels = {
            'complete_coords': 'Complete coordinates',
            'has_drainage_area': 'Has drainage area',
            'min_years': 'Min years data',
            'has_county': 'Has county info'
        }
        quality_text = [quality_labels.get(q, q) for q in quality_values]
        filter_parts.append(f"Quality: {', '.join(quality_text)}")
    
    # Enhanced filter summary display
    filter_summary = html.Div([
        html.P([
            html.Strong("Active Filters: "),
            html.Span(f"{len([x for x in [status_values, state_values, years_range, county_values, quality_values] if x])} applied")
        ], className="mb-1"),
        html.P([
            html.Strong("Results: "),
            f"{filtered_count:,} of {original_count:,} gauges ({100*filtered_count/original_count:.1f}%)"
        ], className="mb-1"),
        html.P([
            "🟢 ", f"{active_count:,} active",
            " | ⚫ ", f"{filtered_count - active_count:,} inactive"
        ], className="mb-0 small")
    ])
    
    # Status text
    filter_status_parts = filter_parts.copy() if filter_parts else []
    
    # Add subset status to filter status
    if subset_status['enabled']:
        filter_status_parts.append(f"Subset: {subset_status['method']} ({subset_status['max_sites']} max)")
    
    filter_status = " | ".join(filter_status_parts) if filter_status_parts else "No active filters"
    
    return fig, gauge_badge, active_badge, total_badge, filter_summary, filter_status


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
        html.P([html.Strong("Years of Record: "), f"{gauge['years_of_record']} years"], className="mb-1"),
        html.P([html.Strong("Status: "), gauge['status'].title()], className="mb-1"),
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
        html.P("Click 'Load Data' to view streamflow analysis.", 
              className="text-muted small")
    ])
    
    badge_text = f"Selected: {site_id}"
    badge_style = {"display": "inline"}
    
    return site_id, badge_text, badge_style, info_content




# Callback to populate county options based on selected states
@app.callback(
    Output("county-filter", "options"),
    [Input("state-filter", "value")]
)
def update_county_options(selected_states):
    """Update county options based on selected states."""
    if not selected_states:
        return []
    
    # Get available counties for selected states
    counties = data_manager.get_available_counties(selected_states)
    return [{"label": county, "value": county} for county in sorted(counties)]


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
