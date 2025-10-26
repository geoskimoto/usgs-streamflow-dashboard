"""
Configuration settings for the USGS Streamflow Dashboard
"""
from datetime import date, datetime
current_date = date.today().isoformat()

def calculate_current_water_year():
    """Calculate the current water year based on today's date.
    Water year runs from October 1 to September 30.
    """
    today = datetime.now()
    if today.month >= 10:  # October, November, December
        return today.year + 1
    else:  # January through September  
        return today.year

# Map Settings
MAP_CENTER = [46.0, -117.0]  # Center on Pacific Northwest (OR, WA, ID)
MAP_CENTER_LAT = 46.0
MAP_CENTER_LON = -117.0
MAP_ZOOM = 5
DEFAULT_ZOOM_LEVEL = 5
MIN_ZOOM_LEVEL = 4
MAX_ZOOM_LEVEL = 12
MAPBOX_STYLE = "open-street-map"  # Free option, or use "satellite" with token

# You can set a Mapbox token for enhanced mapping (optional)
# MAPBOX_TOKEN = "your_mapbox_token_here"
MAPBOX_TOKEN = None

# Map configuration dictionary
MAP_CONFIG = {
    'center_lat': MAP_CENTER_LAT,
    'center_lon': MAP_CENTER_LON,
    'default_zoom': DEFAULT_ZOOM_LEVEL,
    'min_zoom': MIN_ZOOM_LEVEL,
    'max_zoom': MAX_ZOOM_LEVEL,
    'style': MAPBOX_STYLE
}

# Data Settings
CACHE_DURATION = 120 * 24 * 3600  # days * 24 hours in seconds
MAX_YEARS_LOAD = 120  # Extended to capture full historical record from 1910

# Current Water Year Configuration
CURRENT_WATER_YEAR = calculate_current_water_year()
DEFAULT_HIGHLIGHT_YEARS = [CURRENT_WATER_YEAR-1, CURRENT_WATER_YEAR]  # Previous + Current WY (2025, 2026)

DEFAULT_START_DATE = "1910-10-01"  # Start from 1910 water year for full historical record
DEFAULT_END_DATE = current_date     # Through today's date
WATER_YEAR_START = 10  # October 1st (month 10)
DEFAULT_PERCENTILES = [10, 25, 50, 75, 90]

# States to Include
TARGET_STATES = ['OR', 'WA', 'ID']

# Plot Settings
DASHBOARD_PLOT_HEIGHT = 400
DASHBOARD_PLOT_WIDTH = 600
PLOT_CONFIG = {
    'displayModeBar': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d'],
    'responsive': True
}

# Color Schemes for Gauges
GAUGE_COLORS = {
    'excellent': {'color': '#2E8B57', 'opacity': 0.8},    # Sea Green - >20 years of data
    'good': {'color': '#FFD700', 'opacity': 0.8},         # Gold - 10-20 years
    'fair': {'color': '#FF8C00', 'opacity': 0.8},         # Dark Orange - 5-10 years
    'poor': {'color': '#DC143C', 'opacity': 0.8},         # Crimson - <5 years
    'inactive': {'color': '#808080', 'opacity': 0.6},     # Gray - Inactive gauges
    'selected': {'color': '#FF1493', 'opacity': 1.0}      # Deep Pink - Selected gauge
}

# Map marker sizes
MARKER_SIZES = {
    'default': 8,
    'hover': 12,
    'selected': 15
}

# Dashboard Layout
LAYOUT_CONFIG = {
    'map_width': 7,
    'control_panel_width': 5,
    'plots_height': '500px'
}

# Performance Settings
PERFORMANCE = {
    'max_gauges_display': 1000,
    'clustering_zoom_threshold': 8,
    'cache_size_mb': 100
}

# Data Subset Configuration for Testing
SUBSET_CONFIG = {
    'enabled': True,  # Master switch - set to False for production
    'max_sites': 300,  # Maximum number of sites when subset is enabled
    'method': 'balanced',  # Options: 'balanced', 'random', 'top_quality'
    'prefer_active': True,  # Prefer active sites in subset selection
    'state_distribution': {'OR': 0.4, 'WA': 0.4, 'ID': 0.2},  # Balanced across states
    'min_years_record': 1,  # Minimum years of record for subset inclusion
    'cache_subset_selection': True,  # Cache the subset selection
    'selection_seed': 42,  # Random seed for reproducible subset selection
    
    # OPTIMIZED DATA LOADING SETTINGS
    'early_subset_application': True,  # Apply subset before data checking (major performance boost!)
    'validation_years': 2,  # Years of recent data for validation (2 years = fast validation)
    'single_pass_loading': True,  # Use optimized single-pass data loading system
    'cache_validation_data': True,  # Cache validation data for reuse
}

# App Settings
APP_TITLE = 'USGS Streamflow Dashboard - Pacific Northwest'
APP_DESCRIPTION = 'Interactive dashboard for exploring USGS streamflow data across Oregon, Washington, and Idaho'

APP_CONFIG = {
    'debug': True,
    'host': '127.0.0.1',
    'port': 8050,
    'title': APP_TITLE,
    'description': APP_DESCRIPTION
}
