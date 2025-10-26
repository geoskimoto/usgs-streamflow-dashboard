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
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.components.map_component import get_map_component
from usgs_dashboard.components.viz_manager import get_visualization_manager
from usgs_dashboard.components.filter_panel import SimplifiedFilterPanel
from usgs_dashboard.utils.config import (
    APP_TITLE, APP_DESCRIPTION, GAUGE_COLORS, 
    TARGET_STATES, DEFAULT_ZOOM_LEVEL, SUBSET_CONFIG
)

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

# Expose the server for gunicorn
server = app.server

# Global variables
gauges_df = pd.DataFrame()
selected_gauge_id = None

import dash
from dash import dcc, html, Input, Output, State, callback_context, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import dashboard components (updated paths for root level)
from usgs_dashboard.data.data_manager import get_data_manager
from usgs_dashboard.components.map_component import get_map_component
from usgs_dashboard.components.viz_manager import get_visualization_manager
from usgs_dashboard.components.filter_panel import filter_component
from usgs_dashboard.utils.config import (
    APP_TITLE, APP_DESCRIPTION, GAUGE_COLORS, 
    TARGET_STATES, DEFAULT_ZOOM_LEVEL, SUBSET_CONFIG
)


# Initialize components
data_manager = get_data_manager()
map_component = get_map_component()
viz_manager = get_visualization_manager()

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
        
    ], width=3)  # Sidebar width


def create_main_content():
    """Create the main content area."""
    return dbc.Col([
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
    ], width=9)


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
    
], fluid=True)


def create_layout():
    """Create the main dashboard layout with sidebar filters."""
    return html.Div([
        create_header(),
        
        dbc.Container([
            dbc.Row([
                # Sidebar - Filter Panel
                dbc.Col([
                    filter_component.create_filter_panel()
                ], width=3, className="pe-3"),
                
                # Main Content Area
                dbc.Col([
                    dbc.Row([
                        # Map Column
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader([
                                    html.H5("USGS Streamflow Gauges", className="mb-0"),
                                    html.Small(id="gauge-count", className="text-muted")
                                ]),
                                dbc.CardBody([
                                    dcc.Loading(
                                        id="map-loading",
                                        children=[html.Div(id="map-container")],
                                        type="default"
                                    )
                                ])
                            ])
                        ], width=6),
                        
                        # Visualization Column
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader([
                                    html.H5("Streamflow Analysis", className="mb-0"),
                                    html.Small(id="selected-gauge-info", className="text-muted")
                                ]),
                                dbc.CardBody([
                                    dcc.Loading(
                                        id="viz-loading",
                                        children=[html.Div(id="visualization-container")],
                                        type="default"
                                    )
                                ])
                            ])
                        ], width=6)
                    ])
                ], width=9)
            ])
        ], fluid=True),
        
        # Store components for data sharing
        dcc.Store(id='filtered-data-store'),
        dcc.Store(id='selected-gauge-store'),
        dcc.Store(id='water-year-store', data=2026),

    ])


# Set the layout
app.layout = create_layout()


# Callback to update current water year display
@app.callback(
    Output("current-water-year", "children"),
    [Input("water-year-store", "data")]
)
def update_water_year_display(water_year):
    """Update the water year display in the header."""
    return str(water_year)


# Simplified main filtering callback
@app.callback(
    [Output('filtered-data-store', 'data'),
     Output('gauge-count', 'children'),
     Output('results-count', 'children')],
    [Input('search-input', 'value'),
     Input('state-filter', 'value'), 
     Input('drainage-area-filter', 'value'),
     Input('basin-filter', 'value'),
     Input('huc-filter', 'value')],
    # Allow initial call so data loads on page load
    prevent_initial_call=False
)
def update_filtered_data(search_text, state_values, drainage_area_range, 
                        basin_values, huc_values):
    """Filter the gauge data based on selected criteria."""
    try:
        # Get the base filters table
        filters_df = data_manager.get_filters_table()
        
        if filters_df.empty:
            return [], "No data available", "0 sites"
        
        # Handle initial load - if no filters are set, use defaults to show all data
        if (not search_text and not state_values and not drainage_area_range and 
            not basin_values and not huc_values):
            # Default to showing all sites on initial load
            state_values = ["OR", "WA", "ID"]
            drainage_area_range = [0, 90000]
        
        # Create filter criteria dictionary
        filter_criteria = {
            'search_text': search_text or '',
            'states': state_values or ["OR", "WA", "ID"],  # Default to all states if None
            'drainage_area_range': drainage_area_range or [0, 90000],
            'basins': basin_values or [],
            'huc_codes': huc_values or []
        }
        
        # Apply filters
        filtered_df = data_manager.apply_advanced_filters(filters_df, filter_criteria)
        
        # Convert to records for storage
        data = data_manager.prepare_data_for_frontend(filtered_df.to_dict('records'))
        
        # Update gauge count
        count_text = f"{len(filtered_df)} of {len(filters_df)} gauges"
        results_text = f"{len(filtered_df)} sites shown"
        
        return data, count_text, results_text
        
    except Exception as e:
        print(f"Error in filtering: {e}")
        return [], "Error loading data", "0 sites"


# Map update callback
@app.callback(
    Output('map-container', 'children'),
    [Input('filtered-data-store', 'data')]
)
def update_map(filtered_data):
    """Update the map with filtered gauge data."""
    if not filtered_data:
        return html.Div("No data to display", className="text-center p-4")
    
    try:
        # Create map with filtered data
        map_fig = map_component.create_map(filtered_data)
        return dcc.Graph(
            id='gauge-map',
            figure=map_fig,
            style={'height': '500px'}
        )
    except Exception as e:
        print(f"Error creating map: {e}")
        return html.Div(f"Error loading map: {str(e)}", className="text-center p-4")


# Gauge selection from map
@app.callback(
    [Output('selected-gauge-store', 'data'),
     Output('selected-gauge-info', 'children')],
    [Input('gauge-map', 'clickData')],
    prevent_initial_call=True
)
def handle_gauge_selection(click_data):
    """Handle gauge selection from map clicks."""
    if not click_data or 'points' not in click_data:
        return None, "Click on a gauge to view data"
    
    try:
        point = click_data['points'][0]
        site_id = point.get('customdata', [None])[0] if 'customdata' in point else None
        
        if site_id:
            # Get gauge info for display
            filters_df = data_manager.get_filters_table()
            gauge_info = filters_df[filters_df['site_id'] == site_id]
            
            if not gauge_info.empty:
                gauge = gauge_info.iloc[0]
                info_text = f"Selected: {gauge['station_name']} ({site_id})"
                return site_id, info_text
        
        return None, "Gauge information not available"
        
    except Exception as e:
        print(f"Error in gauge selection: {e}")
        return None, "Error selecting gauge"


# Visualization update callback
@app.callback(
    Output('visualization-container', 'children'),
    [Input('selected-gauge-store', 'data'),
     Input('water-year-store', 'data'),
     Input('highlight-years-input', 'value')],
    prevent_initial_call=True
)
def update_visualization(selected_gauge_id, water_year, highlight_years_input):
    """Update visualization based on selected gauge."""
    if not selected_gauge_id:
        return html.Div([
            html.H6("No Gauge Selected", className="text-center text-muted"),
            html.P("Click on a gauge in the map to view streamflow data", 
                  className="text-center text-muted")
        ], className="p-4")
    
    try:
        # Parse highlight years from input
        highlight_years = []
        if highlight_years_input and highlight_years_input.strip():
            try:
                # Parse comma-separated years
                years_text = highlight_years_input.strip()
                highlight_years = [int(year.strip()) for year in years_text.split(',') if year.strip().isdigit()]
            except ValueError:
                pass  # If parsing fails, just use empty list
        
        # Always include current water year in highlights
        if water_year and water_year not in highlight_years:
            highlight_years.append(water_year)
        
        # Get streamflow data for the selected gauge
        streamflow_data = data_manager.get_streamflow_data(
            site_id=selected_gauge_id,
            start_date='2020-01-01',  # Get recent years
            end_date=None
        )
        
        if streamflow_data.empty:
            return html.Div([
                html.H6("No Data Available", className="text-center text-muted"),
                html.P(f"No streamflow data found for gauge {selected_gauge_id}", 
                      className="text-center text-muted")
            ], className="p-4")
        
        # Create visualization
        viz_fig = viz_manager.create_streamflow_plot(
            site_id=selected_gauge_id,
            streamflow_data=streamflow_data,
            highlight_years=highlight_years if highlight_years else None
        )
        
        return dcc.Graph(
            figure=viz_fig,
            style={'height': '450px'}
        )
        
    except Exception as e:
        print(f"Error creating visualization: {e}")
        return html.Div([
            html.H6("Error Loading Data", className="text-center text-danger"),
            html.P(f"Error: {str(e)}", className="text-center text-muted small")
        ], className="p-4")



# Clear search callback
@app.callback(
    Output("search-input", "value", allow_duplicate=True),
    [Input("clear-search", "n_clicks")],
    prevent_initial_call=True
)
def clear_search(n_clicks):
    """Clear the search input."""
    if n_clicks:
        return ""
    return no_update


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


@app.callback(
    Output("filter-summary", "children"),
    [Input("search-input", "value"),
     Input("state-filter", "value"),
     Input("drainage-area-filter", "value"),
     Input("basin-filter", "value"),
     Input("huc-filter", "value")]
)
def update_filter_summary(search_text, state_values, drainage_area_range, 
                         basin_values, huc_values):
    """Update the filter summary display."""
    active_filters = []
    
    if search_text and search_text.strip():
        active_filters.append(f"Search: '{search_text.strip()}'")
    
    if state_values and len(state_values) < 3:
        active_filters.append(f"States: {', '.join(state_values)}")
    
    if drainage_area_range and (drainage_area_range[0] > 0 or drainage_area_range[1] < 90000):
        active_filters.append(f"Drainage: {drainage_area_range[0]:,}-{drainage_area_range[1]:,} sq mi")
    
    if basin_values:
        basin_text = f"Basins: {len(basin_values)} selected" if len(basin_values) > 2 else f"Basins: {', '.join(basin_values)}"
        active_filters.append(basin_text)
    
    if huc_values:
        huc_text = f"HUCs: {len(huc_values)} selected" if len(huc_values) > 2 else f"HUCs: {', '.join(huc_values)}"
        active_filters.append(huc_text)
    
    if active_filters:
        return f"Active filters: {', '.join(active_filters)}"
    else:
        return "No filters applied - showing all sites"


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