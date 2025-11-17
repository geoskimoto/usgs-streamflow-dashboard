# Interactive USGS Streamflow Dashboard - Comprehensive Development Prompt

## Project Overview
Create an interactive web dashboard using Python Dash that displays USGS streamflow gauges across Oregon, Washington, and Idaho on an interactive map. When users click on a gauge, display comprehensive streamflow analysis including water year plots, statistics, and visualizations using the existing `streamflow_analyzer` module.

## Core Requirements

### 1. Interactive Map Component
**Technology Stack:**
- **Dash** for the web framework
- **Plotly/Mapbox** for interactive mapping
- **dataretrieval** for USGS station discovery and data fetching

**Map Features:**
- **Geographic Scope**: Oregon, Washington, and Idaho
- **Base Map**: Topographic or satellite imagery showing terrain
- **Gauge Markers**: Color-coded points representing USGS streamflow gauges
- **Interactive Elements**: Click, hover, zoom, pan capabilities
- **Real-time Loading**: Progressive loading of gauge information

**Gauge Discovery:**
```python
import dataretrieval.nwis as nwis

# Query gauges by state
states = ['OR', 'WA', 'ID']
active_gauges = []

for state in states:
    # Get active streamflow gauges
    gauges = nwis.get_record(stateCd=state, service='site', 
                            parameterCd='00060', hasDataTypeCd='dv')
    active_gauges.append(gauges)
```

### 2. Gauge Information System
**Station Metadata:**
- Site ID and name
- Location coordinates (lat/lon)
- Drainage area
- Period of record
- Real-time data availability
- Station status (active/inactive)

**Color Coding Scheme:**
- 🟢 **Green**: Active gauges with >20 years of data
- 🟡 **Yellow**: Active gauges with 10-20 years of data  
- 🟠 **Orange**: Active gauges with 5-10 years of data
- 🔴 **Red**: Active gauges with <5 years of data
- ⚫ **Gray**: Inactive or problematic gauges

**Hover Information:**
Display on map hover without clicking:
- Station name
- Site ID
- Drainage area
- Years of record
- Current status

### 3. Interactive Dashboard Layout

#### **Layout Structure:**
```
┌─────────────────────────────────────────────────────────────┐
│                    USGS Streamflow Dashboard                │
├─────────────────────────┬───────────────────────────────────┤
│                         │                                   │
│    Interactive Map      │         Control Panel            │
│    (60% width)          │         (40% width)               │
│                         │                                   │
│  🗺️ OR/WA/ID Gauges     │  📊 Selected Gauge Info          │
│                         │  📈 Quick Stats                   │
│                         │  ⚙️ Plot Controls                │
│                         │                                   │
├─────────────────────────┴───────────────────────────────────┤
│                                                             │
│              Streamflow Visualizations                      │
│              (Full width, collapsible)                      │
│                                                             │
│  📈 Water Year Plot  │  📊 Flow Duration  │  📅 Monthly    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 4. Streamflow Analysis Integration

**Integration with Existing Tool:**
- Import and use the `StreamflowData` and `StreamflowVisualizer` classes
- Maintain all existing functionality (water year analysis, statistics, etc.)
- Adapt plots for dashboard embedding

**Plot Adaptations:**
```python
# Dashboard-optimized plotting
def create_dashboard_plots(site_id, years_to_highlight=None):
    # Load data
    data = StreamflowData(site_id=site_id, 
                         start_date='2000-10-01', 
                         end_date='2024-09-30')
    
    viz = StreamflowVisualizer(data)
    
    # Create plots optimized for dashboard
    plots = {
        'main_plot': viz.create_stacked_line_plot(
            highlight_years=years_to_highlight,
            figure_size=(10, 6)  # Optimized for dashboard
        ),
        'flow_duration': viz.create_flow_duration_curve(),
        'monthly_comparison': viz.create_monthly_comparison(),
        'annual_summary': viz.create_annual_summary()
    }
    
    return plots, data
```

### 5. Dashboard Components

#### **A. Map Component (`map_component.py`)**
```python
import dash
from dash import dcc, html, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import dataretrieval.nwis as nwis

class USGSMapComponent:
    def __init__(self):
        self.gauges_data = self.load_regional_gauges()
    
    def load_regional_gauges(self):
        """Load all USGS gauges for OR, WA, ID with metadata"""
        
    def create_map(self):
        """Create the interactive map with gauge markers"""
        
    def get_map_figure(self):
        """Return the Plotly figure for the map"""
```

#### **B. Data Manager (`data_manager.py`)**
```python
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import dataretrieval.nwis as nwis

class USGSDataManager:
    def __init__(self):
        self.cache_db = 'usgs_cache.db'
        self.setup_cache()
    
    def setup_cache(self):
        """Setup SQLite database for caching gauge data"""
        
    def get_gauge_metadata(self, site_id):
        """Get comprehensive metadata for a gauge"""
        
    def get_streamflow_data(self, site_id, use_cache=True):
        """Get streamflow data with intelligent caching"""
        
    def refresh_gauge_cache(self, site_id):
        """Update cached data for specific gauge"""
```

#### **C. Visualization Manager (`viz_manager.py`)**
```python
from streamflow_analyzer import StreamflowData, StreamflowVisualizer

class DashboardVisualizationManager:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        
    def create_gauge_plots(self, site_id, plot_config):
        """Create all plots for selected gauge"""
        
    def create_summary_stats(self, site_id):
        """Generate summary statistics display"""
        
    def create_comparison_plots(self, site_ids):
        """Create comparison plots for multiple gauges"""
```

### 6. User Interface Components

#### **Control Panel Features:**
- **Gauge Search**: Search by name, ID, or location
- **Filter Options**:
  - Drainage area range
  - Years of record
  - Data availability
  - State selection
- **Plot Configuration**:
  - Years to highlight
  - Statistical overlays
  - Time period selection
  - Plot type selection
- **Export Options**:
  - Download plots (PNG, HTML)
  - Export data (CSV, Excel)
  - Generate reports

#### **Information Display:**
- **Selected Gauge Panel**:
  ```
  📍 Selected Station
  ├── 🏷️ Name: [Station Name]
  ├── 🆔 Site ID: [Site Number]  
  ├── 📍 Location: [Lat, Lon]
  ├── 🌊 Drainage: [Area] sq mi
  ├── 📅 Record: [Start] to [End]
  ├── 📊 Status: [Active/Inactive]
  └── 📈 Quick Stats: [Mean flow, etc.]
  ```

### 7. Advanced Features

#### **Multi-Gauge Comparison:**
- Select multiple gauges for comparison
- Overlay plots from different stations
- Regional flow pattern analysis
- Upstream/downstream relationships

#### **Time Series Animation:**
- Animate flow conditions over time
- Show seasonal patterns across region
- Drought/flood event visualization

#### **Data Quality Indicators:**
- Visual indicators for data gaps
- Quality flags and annotations
- Real-time vs. provisional data distinction

#### **Regional Analysis Tools:**
- Basin-wide statistics
- Flow correlation analysis
- Climate pattern relationships

### 8. Technical Implementation

#### **Project Structure:**
```
📁 usgs_dashboard/
├── 📄 app.py                    # Main Dash application
├── 📄 requirements.txt          # Dependencies
├── 📁 components/
│   ├── 📄 map_component.py      # Interactive map
│   ├── 📄 control_panel.py      # User controls
│   ├── 📄 viz_component.py      # Visualization panels
│   └── 📄 info_panel.py         # Information display
├── 📁 data/
│   ├── 📄 data_manager.py       # Data handling
│   ├── 📄 cache_manager.py      # Caching system
│   └── 📄 usgs_cache.db         # SQLite cache
├── 📁 utils/
│   ├── 📄 config.py             # Configuration
│   ├── 📄 helpers.py            # Utility functions
│   └── 📄 styles.py             # CSS styling
├── 📁 assets/
│   ├── 📄 dashboard.css         # Custom styles
│   └── 📄 logo.png              # Assets
└── 📄 streamflow_analyzer.py    # Existing analysis tool
```

#### **Dependencies:**
```python
# Web Framework
dash>=2.14.0
dash-bootstrap-components>=1.5.0

# Visualization
plotly>=5.15.0
dash-leaflet>=0.1.23  # Alternative mapping

# Data Processing
pandas>=2.0.0
numpy>=1.24.0
dataretrieval>=1.0.10

# Database & Caching
sqlite3  # Built-in
redis>=4.5.0  # Optional: Redis caching

# Geospatial
geopandas>=0.13.0  # Optional: Enhanced mapping
folium>=0.14.0     # Alternative: Folium integration

# Performance
diskcache>=5.6.0   # Intelligent caching
```

### 9. Performance Optimization

#### **Caching Strategy:**
- **Level 1**: In-memory gauge metadata cache
- **Level 2**: SQLite database for streamflow data
- **Level 3**: Redis cache for frequently accessed data
- **Level 4**: Pre-computed statistics cache

#### **Data Loading:**
- **Lazy Loading**: Load data only when gauge is selected
- **Background Loading**: Pre-load popular gauges
- **Progressive Loading**: Stream large datasets
- **Smart Updates**: Update only stale cached data

#### **Map Performance:**
- **Clustering**: Group nearby gauges at low zoom levels
- **LOD (Level of Detail)**: Show different information at different zoom levels
- **Tile Caching**: Cache map tiles locally
- **Marker Optimization**: Efficient marker rendering

### 10. User Experience Design

#### **Responsive Design:**
- **Desktop**: Full dashboard layout
- **Tablet**: Collapsible panels
- **Mobile**: Stacked layout with swipeable sections

#### **Loading States:**
- Map loading spinner
- Data fetching progress bars
- Plot rendering indicators
- Cache status displays

#### **Error Handling:**
- Network connectivity issues
- Data availability problems
- Invalid gauge selection
- Timeout handling

### 11. Configuration and Customization

#### **Configuration File (`config.py`):**
```python
# Map Settings
MAP_CENTER = [44.0, -120.5]  # Center on PNW
MAP_ZOOM = 6
MAPBOX_TOKEN = "your_token_here"

# Data Settings
CACHE_DURATION = 24 * 3600  # 24 hours
MAX_YEARS_LOAD = 30
DEFAULT_HIGHLIGHT_YEARS = [2012, 2015, 2023]

# States to Include
TARGET_STATES = ['OR', 'WA', 'ID']

# Plot Settings
DASHBOARD_PLOT_HEIGHT = 400
DASHBOARD_PLOT_WIDTH = 600

# Color Schemes
GAUGE_COLORS = {
    'excellent': '#2E8B57',    # >20 years
    'good': '#FFD700',         # 10-20 years
    'fair': '#FF8C00',         # 5-10 years
    'poor': '#DC143C',         # <5 years
    'inactive': '#808080'      # Inactive
}
```

### 12. Deployment Options

#### **Local Development:**
```bash
python app.py
# Dashboard available at http://localhost:8050
```

#### **Cloud Deployment:**
- **Heroku**: Easy deployment with git integration
- **AWS Elastic Beanstalk**: Scalable cloud hosting
- **Digital Ocean**: Simple VPS deployment
- **Docker**: Containerized deployment

#### **Docker Configuration:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8050
CMD ["python", "app.py"]
```

### 13. Testing and Quality Assurance

#### **Testing Strategy:**
- **Unit Tests**: Individual component testing
- **Integration Tests**: Data flow testing
- **Performance Tests**: Load testing with multiple users
- **UI Tests**: Selenium-based interaction testing

#### **Data Quality Checks:**
- Validate USGS data integrity
- Check for data gaps and anomalies
- Verify coordinate accuracy
- Test caching mechanisms

### 14. Documentation and Help

#### **User Guide:**
- Interactive tutorial overlay
- Help tooltips throughout interface
- Video demonstrations
- FAQ section

#### **Technical Documentation:**
- API documentation
- Component architecture
- Data flow diagrams
- Deployment guides

### 15. Example Usage Workflow

#### **User Journey:**
1. **Dashboard Loads**: Map displays with ~500-1000 gauges across OR/WA/ID
2. **User Explores**: Hovers over gauges to see basic info
3. **Gauge Selection**: Clicks on a gauge of interest
4. **Data Loading**: Dashboard fetches and caches streamflow data
5. **Visualization**: Water year plots and statistics appear
6. **Analysis**: User explores different plot types and time periods
7. **Comparison**: User selects additional gauges for comparison
8. **Export**: User downloads plots or data for further analysis

#### **Sample Implementation:**
```python
# Main application entry point
from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("USGS Streamflow Dashboard - Pacific Northwest"),
            dcc.Graph(id="usgs-map")
        ], width=7),
        dbc.Col([
            html.Div(id="control-panel")
        ], width=5)
    ]),
    dbc.Row([
        dbc.Col([
            html.Div(id="streamflow-plots")
        ], width=12)
    ])
])

# Callbacks for interactivity
@app.callback(
    Output("streamflow-plots", "children"),
    Input("usgs-map", "clickData")
)
def update_plots(click_data):
    if click_data:
        site_id = click_data['points'][0]['customdata']
        return create_streamflow_dashboard(site_id)
    return html.Div("Select a gauge on the map to view analysis")

if __name__ == "__main__":
    app.run_server(debug=True)
```

### 16. Success Criteria

The completed dashboard should enable users to:
- **Explore**: Discover USGS gauges across the Pacific Northwest interactively
- **Analyze**: Generate comprehensive streamflow analysis for any gauge with one click
- **Compare**: Examine multiple gauges simultaneously for regional patterns
- **Export**: Download high-quality plots and data for reports
- **Navigate**: Intuitively find and analyze streamflow information
- **Perform**: Handle hundreds of gauges with responsive performance

This dashboard will provide water managers, researchers, and analysts with a powerful, user-friendly tool for exploring regional streamflow patterns and conducting detailed hydrologic analysis across Oregon, Washington, and Idaho.

### 17. Future Enhancements

- **Real-time Integration**: Live streamflow data updates
- **Climate Data**: Integration with precipitation and temperature data
- **Forecasting**: Streamflow prediction capabilities
- **Mobile App**: Native mobile application
- **API Access**: RESTful API for programmatic access
- **Machine Learning**: Automated pattern recognition and anomaly detection
