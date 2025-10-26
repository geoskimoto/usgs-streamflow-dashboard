# USGS Dashboard Advanced Filtering System - Implementation Prompt

## Overview
Enhance the existing USGS Streamflow Dashboard by implementing a comprehensive filtering system that allows users to filter gauges by various criteria including active/inactive status, site type (streams vs wells), data availability, and geographic parameters.

## Data Analysis Results
Based on USGS data structure analysis:
- **Site Types (`site_tp_cd`)**: ST (Stream), GW (Groundwater), SP (Spring), LK (Lake), etc.
- **Agency (`agency_cd`)**: USGS, USACE, etc.
- **Well Data**: `well_depth_va`, `hole_depth_va` indicate groundwater sites
- **Geographic**: `state_cd`, `county_cd`, `huc_cd` (watershed), `drain_area_va`
- **Temporal**: Need to query data availability to determine active/inactive status

## Required Implementation

### 1. Enhanced Data Manager (`data/data_manager.py`)

**Add Active/Inactive Detection:**
```python
def _determine_site_activity(self, site_id: str) -> dict:
    """Determine if a site has recent data (active) or not (inactive)."""
    try:
        # Query last 2 years of data availability
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)
        
        # Check for recent streamflow data
        recent_data = nwis.get_record(
            sites=site_id, 
            service='dv', 
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            parameterCd='00060'  # Streamflow
        )
        
        if isinstance(recent_data, tuple):
            data_df = recent_data[0]
        else:
            data_df = recent_data
            
        has_recent_data = len(data_df) > 0
        last_measurement = data_df.index[-1] if len(data_df) > 0 else None
        
        return {
            'is_active': has_recent_data,
            'last_data_date': last_measurement,
            'recent_record_count': len(data_df)
        }
        
    except Exception:
        return {'is_active': False, 'last_data_date': None, 'recent_record_count': 0}
```

**Enhanced Metadata Processing:**
```python
def _process_gauge_metadata_with_activity(self, gauges_df):
    """Process gauge metadata including activity status and enhanced filtering fields."""
    processed_gauges = []
    
    for idx, gauge in gauges_df.iterrows():
        try:
            # Basic processing
            gauge_data = {
                'site_id': str(gauge.get('site_no', '')),
                'station_name': str(gauge.get('station_nm', 'Unknown')),
                'latitude': float(pd.to_numeric(gauge.get('dec_lat_va'), errors='coerce')),
                'longitude': float(pd.to_numeric(gauge.get('dec_long_va'), errors='coerce')),
                'drainage_area': pd.to_numeric(gauge.get('drain_area_va'), errors='coerce') or 0.0,
                'state': str(gauge.get('state_cd', '')),
                
                # Enhanced filtering fields
                'site_type': str(gauge.get('site_tp_cd', '')),
                'agency': str(gauge.get('agency_cd', 'USGS')),
                'county': str(gauge.get('county_cd', '')),
                'huc_code': str(gauge.get('huc_cd', '')),
                'well_depth': pd.to_numeric(gauge.get('well_depth_va'), errors='coerce'),
                'construction_date': gauge.get('construction_dt', ''),
                'inventory_date': gauge.get('inventory_dt', ''),
            }
            
            # Skip invalid coordinates
            if pd.isna(gauge_data['latitude']) or pd.isna(gauge_data['longitude']):
                continue
            
            # Determine activity status (sample for first 50 sites, then use heuristics)
            if len(processed_gauges) < 50:
                activity = self._determine_site_activity(gauge_data['site_id'])
                gauge_data['is_active'] = activity['is_active']
                gauge_data['last_data_date'] = activity['last_data_date']
            else:
                # Use heuristics for performance
                gauge_data['is_active'] = gauge_data['site_type'] in ['ST', 'LK'] and gauge_data['drainage_area'] > 0
                gauge_data['last_data_date'] = None
            
            # Categorize site types for filtering
            gauge_data['site_category'] = self._categorize_site_type(gauge_data['site_type'])
            gauge_data['is_stream'] = gauge_data['site_type'] == 'ST'
            gauge_data['is_groundwater'] = gauge_data['site_type'] == 'GW' or pd.notna(gauge_data['well_depth'])
            gauge_data['is_spring'] = gauge_data['site_type'] == 'SP'
            gauge_data['is_lake'] = gauge_data['site_type'] == 'LK'
            
            # Status for color coding
            if gauge_data['is_active']:
                gauge_data['status'] = 'active'
                gauge_data['color'] = self.config.GAUGE_COLORS['good']['color']
            else:
                gauge_data['status'] = 'inactive'
                gauge_data['color'] = self.config.GAUGE_COLORS['inactive']['color']
            
            processed_gauges.append(gauge_data)
            
        except Exception as e:
            continue
    
    return pd.DataFrame(processed_gauges)

def _categorize_site_type(self, site_type_code: str) -> str:
    """Categorize USGS site types into user-friendly categories."""
    categories = {
        'ST': 'Surface Water - Stream',
        'LK': 'Surface Water - Lake/Reservoir', 
        'GW': 'Groundwater - Well',
        'SP': 'Surface Water - Spring',
        'WE': 'Groundwater - Well',
        'ES': 'Surface Water - Estuary',
        'OC': 'Surface Water - Ocean',
        'AT': 'Meteorological',
        'GL': 'Surface Water - Glacier'
    }
    return categories.get(site_type_code, f'Other ({site_type_code})')
```

### 2. Advanced Filter Component (`components/filter_panel.py`)

**Create new filter panel component:**
```python
import dash_bootstrap_components as dbc
from dash import html, dcc, Input, Output, State, callback
import plotly.express as px

class AdvancedFilterPanel:
    def __init__(self):
        self.filter_options = self._initialize_filter_options()
    
    def create_filter_panel(self) -> dbc.Card:
        """Create comprehensive filter panel with multiple filter categories."""
        
        return dbc.Card([
            dbc.CardHeader(html.H5("🔍 Advanced Filters", className="mb-0")),
            dbc.CardBody([
                
                # Active/Inactive Status Filter
                html.Div([
                    html.Label("Site Status:", className="fw-bold"),
                    dbc.Checklist(
                        id="status-filter",
                        options=[
                            {"label": "✅ Active Sites", "value": "active"},
                            {"label": "❌ Inactive Sites", "value": "inactive"},
                        ],
                        value=["active", "inactive"],
                        inline=True,
                        className="mb-3"
                    )
                ]),
                
                # Site Type Filter  
                html.Div([
                    html.Label("Site Type:", className="fw-bold"),
                    dbc.Checklist(
                        id="site-type-filter",
                        options=[
                            {"label": "🌊 Streams/Rivers (ST)", "value": "ST"},
                            {"label": "🏔️ Lakes/Reservoirs (LK)", "value": "LK"},
                            {"label": "💧 Springs (SP)", "value": "SP"},
                            {"label": "🕳️ Groundwater Wells (GW)", "value": "GW"},
                            {"label": "🌊 Estuaries (ES)", "value": "ES"},
                            {"label": "📊 Other Types", "value": "OTHER"}
                        ],
                        value=["ST", "LK", "SP"],  # Default to surface water
                        className="mb-3"
                    )
                ]),
                
                # State Filter
                html.Div([
                    html.Label("States:", className="fw-bold"),
                    dbc.Checklist(
                        id="state-filter",
                        options=[
                            {"label": "🌲 Oregon (OR)", "value": "OR"},
                            {"label": "🏔️ Washington (WA)", "value": "WA"},
                            {"label": "⛰️ Idaho (ID)", "value": "ID"}
                        ],
                        value=["OR", "WA", "ID"],
                        inline=True,
                        className="mb-3"
                    )
                ]),
                
                # Drainage Area Filter
                html.Div([
                    html.Label("Drainage Area (sq mi):", className="fw-bold"),
                    html.Div(id="drainage-area-display", className="mb-2"),
                    dcc.RangeSlider(
                        id="drainage-area-filter",
                        min=0, max=10000, step=100,
                        value=[0, 10000],
                        marks={0: '0', 1000: '1K', 5000: '5K', 10000: '10K+'},
                        tooltip={"placement": "bottom", "always_visible": True}
                    )
                ], className="mb-3"),
                
                # Agency Filter
                html.Div([
                    html.Label("Data Source Agency:", className="fw-bold"),
                    dcc.Dropdown(
                        id="agency-filter",
                        options=[
                            {"label": "USGS - US Geological Survey", "value": "USGS"},
                            {"label": "USACE - Army Corps of Engineers", "value": "USACE"},
                            {"label": "All Agencies", "value": "ALL"}
                        ],
                        value="USGS",
                        clearable=False,
                        className="mb-3"
                    )
                ]),
                
                # Data Quality Filter
                html.Div([
                    html.Label("Minimum Data Requirements:", className="fw-bold"),
                    dbc.Checklist(
                        id="quality-filter",
                        options=[
                            {"label": "Has recent data (last 2 years)", "value": "recent_data"},
                            {"label": "Has drainage area info", "value": "has_drainage_area"},
                            {"label": "Complete coordinate info", "value": "complete_coords"},
                        ],
                        value=["complete_coords"],
                        className="mb-3"
                    )
                ]),
                
                # Reset and Apply Buttons
                html.Div([
                    dbc.Button(
                        "🔄 Reset Filters", 
                        id="reset-filters-btn",
                        color="secondary", 
                        size="sm", 
                        className="me-2"
                    ),
                    dbc.Button(
                        "✅ Apply Filters", 
                        id="apply-filters-btn",
                        color="primary", 
                        size="sm"
                    ),
                ], className="d-grid gap-2"),
                
                # Filter Summary
                html.Hr(),
                html.Div(id="filter-summary", className="small text-muted")
            ])
        ], className="h-100")
```

### 3. Enhanced App Layout (`app.py`)

**Update main layout to include filter panel:**
```python
# Add filter panel to layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H1("🌊 USGS Streamflow Dashboard - Pacific Northwest", 
                   className="text-center mb-4"),
            html.P("Interactive map and analysis of USGS streamflow gauges", 
                   className="text-center text-muted mb-4")
        ])
    ]),
    
    # Main Content Row
    dbc.Row([
        # Map Column
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id="gauge-map", style={'height': '600px'})
                ])
            ])
        ], width=8),
        
        # Filter and Control Panel Column
        dbc.Col([
            # Filter Panel
            filter_component.create_filter_panel(),
            
            html.Br(),
            
            # Gauge Info Panel
            dbc.Card([
                dbc.CardHeader([
                    html.H5("📊 Selected Gauge", className="mb-0"),
                    dbc.Badge(id="gauge-count-badge", color="info")
                ]),
                dbc.CardBody([
                    html.Div(id="gauge-info-panel")
                ])
            ])
        ], width=4)
    ], className="mb-4"),
    
    # Streamflow Analysis Row
    dbc.Row([
        dbc.Col([
            dbc.Collapse([
                dbc.Card([
                    dbc.CardBody([
                        html.Div(id="streamflow-analysis")
                    ])
                ])
            ], id="analysis-collapse", is_open=False)
        ])
    ])
], fluid=True)
```

**Add filtering callbacks:**
```python
@app.callback(
    [Output("gauge-map", "figure"),
     Output("gauge-count-badge", "children"),
     Output("filter-summary", "children")],
    [Input("apply-filters-btn", "n_clicks"),
     Input("reset-filters-btn", "n_clicks")],
    [State("status-filter", "value"),
     State("site-type-filter", "value"),
     State("state-filter", "value"),
     State("drainage-area-filter", "value"),
     State("agency-filter", "value"),
     State("quality-filter", "value")]
)
def update_map_with_filters(apply_clicks, reset_clicks, status_values, site_type_values, 
                           state_values, drainage_range, agency_value, quality_values):
    """Update map based on applied filters."""
    
    # Determine if reset was clicked
    ctx = dash.callback_context
    if ctx.triggered and 'reset-filters-btn' in ctx.triggered[0]['prop_id']:
        # Reset to default filters
        status_values = ["active", "inactive"]
        site_type_values = ["ST", "LK", "SP"]
        state_values = ["OR", "WA", "ID"]
        drainage_range = [0, 10000]
        agency_value = "USGS"
        quality_values = ["complete_coords"]
    
    # Load all gauges
    all_gauges = data_manager.load_regional_gauges()
    
    # Apply filters
    filtered_gauges = all_gauges.copy()
    
    # Status filter
    if status_values:
        if 'active' in status_values and 'inactive' not in status_values:
            filtered_gauges = filtered_gauges[filtered_gauges['is_active'] == True]
        elif 'inactive' in status_values and 'active' not in status_values:
            filtered_gauges = filtered_gauges[filtered_gauges['is_active'] == False]
    
    # Site type filter
    if site_type_values:
        if 'OTHER' in site_type_values:
            # Include specified types plus any others not in the main list
            main_types = ['ST', 'LK', 'SP', 'GW', 'ES']
            site_filter = (filtered_gauges['site_type'].isin(site_type_values)) | \
                         (~filtered_gauges['site_type'].isin(main_types))
        else:
            site_filter = filtered_gauges['site_type'].isin(site_type_values)
        filtered_gauges = filtered_gauges[site_filter]
    
    # State filter
    if state_values:
        filtered_gauges = filtered_gauges[filtered_gauges['state'].isin(state_values)]
    
    # Drainage area filter
    if drainage_range:
        min_area, max_area = drainage_range
        area_filter = (filtered_gauges['drainage_area'] >= min_area) & \
                     (filtered_gauges['drainage_area'] <= max_area)
        filtered_gauges = filtered_gauges[area_filter]
    
    # Agency filter
    if agency_value and agency_value != "ALL":
        filtered_gauges = filtered_gauges[filtered_gauges['agency'] == agency_value]
    
    # Quality filters
    if quality_values:
        if 'recent_data' in quality_values:
            filtered_gauges = filtered_gauges[filtered_gauges['is_active'] == True]
        if 'has_drainage_area' in quality_values:
            filtered_gauges = filtered_gauges[filtered_gauges['drainage_area'] > 0]
        if 'complete_coords' in quality_values:
            coord_filter = pd.notna(filtered_gauges['latitude']) & \
                          pd.notna(filtered_gauges['longitude'])
            filtered_gauges = filtered_gauges[coord_filter]
    
    # Create map with filtered gauges
    fig = map_component.create_gauge_map(filtered_gauges)
    
    # Create summary
    total_count = len(filtered_gauges)
    active_count = len(filtered_gauges[filtered_gauges['is_active'] == True])
    inactive_count = total_count - active_count
    
    gauge_badge = f"{total_count:,} gauges"
    
    filter_summary = html.Div([
        html.P([
            html.Strong("Filter Results: "),
            f"{total_count:,} total gauges"
        ]),
        html.P([
            f"🟢 {active_count:,} active | ",
            f"⚫ {inactive_count:,} inactive"
        ]),
        html.P([
            html.Strong("Site Types: "),
            ", ".join(site_type_values) if site_type_values else "None"
        ]),
        html.P([
            html.Strong("States: "),
            ", ".join(state_values) if state_values else "None"
        ])
    ])
    
    return fig, gauge_badge, filter_summary
```

### 4. Enhanced Configuration (`utils/config.py`)

**Add filter-related configurations:**
```python
# Site type configurations
SITE_TYPE_INFO = {
    'ST': {
        'name': 'Stream/River',
        'icon': '🌊',
        'description': 'Surface water monitoring at rivers and streams',
        'color': '#1f77b4'
    },
    'LK': {
        'name': 'Lake/Reservoir', 
        'icon': '🏔️',
        'description': 'Surface water monitoring at lakes and reservoirs',
        'color': '#ff7f0e'
    },
    'GW': {
        'name': 'Groundwater Well',
        'icon': '🕳️', 
        'description': 'Groundwater monitoring wells',
        'color': '#2ca02c'
    },
    'SP': {
        'name': 'Spring',
        'icon': '💧',
        'description': 'Natural springs and seeps',
        'color': '#d62728'
    },
    'ES': {
        'name': 'Estuary',
        'icon': '🌊',
        'description': 'Estuarine and tidal waters',
        'color': '#9467bd'
    }
}

# Filter defaults
DEFAULT_FILTERS = {
    'status': ['active', 'inactive'],
    'site_types': ['ST', 'LK', 'SP'],
    'states': ['OR', 'WA', 'ID'],
    'drainage_area_range': [0, 10000],
    'agency': 'USGS',
    'quality_requirements': ['complete_coords']
}

# Filter descriptions
FILTER_HELP = {
    'status': 'Filter by whether the site has recent data (active) or not (inactive)',
    'site_type': 'Select types of monitoring sites to display on the map',
    'drainage_area': 'Filter by watershed drainage area in square miles',
    'agency': 'Choose which agency operates the monitoring sites',
    'quality': 'Set minimum data quality requirements for displayed sites'
}
```

### 5. User Interface Enhancements

**Add filter tooltips and help:**
- Hover tooltips explaining each filter type
- Expandable help sections with USGS site type explanations  
- Real-time filter result preview
- Export filtered gauge list functionality
- Saved filter presets (e.g., "Streams Only", "Active Sites", "Large Watersheds")

## Expected Outcomes

After implementation:

1. **🔍 Advanced Filtering**: Users can filter 2,600+ gauges by multiple criteria
2. **🎯 Targeted Analysis**: Focus on specific site types (streams vs wells vs springs)
3. **📊 Active Site Focus**: Easily identify currently active vs inactive monitoring sites
4. **🗺️ Geographic Control**: Filter by state, county, watershed (HUC), drainage area
5. **⚡ Performance**: Smart caching and progressive loading for large datasets
6. **📱 Responsive Design**: Collapsible filter panel for different screen sizes
7. **💾 User Preferences**: Remember filter settings between sessions

## Implementation Priority

1. **High Priority**: Active/Inactive status, Site type filtering, State filtering
2. **Medium Priority**: Drainage area range, Agency filtering, Data quality filters
3. **Low Priority**: HUC watershed filtering, Advanced search, Filter presets

This comprehensive filtering system will transform the dashboard from a simple map viewer into a powerful tool for targeted hydrologic analysis across the Pacific Northwest region.
