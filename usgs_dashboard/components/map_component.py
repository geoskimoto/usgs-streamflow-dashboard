"""
Modern Map Component for USGS Dashboard - MapLibre Implementation

Uses the new px.scatter_map and go.Scattermap (replaces deprecated mapbox).
This should resolve the grey box issue by using the current Plotly map API.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional
from ..utils.config import (
    MAP_CONFIG, GAUGE_COLORS, MAP_CENTER_LAT, MAP_CENTER_LON,
    MIN_ZOOM_LEVEL, MAX_ZOOM_LEVEL, DEFAULT_ZOOM_LEVEL
)

# Ordered display groups for percentile-based map coloring.
# Tuple: (map_group_key, legend_label, color, opacity, size_factor)
PERCENTILE_GROUP_CONFIG = [
    ('p76_100',          'High (76-100th pct)',         '#0D47A1', 0.85, 1.0),
    ('p51_75',           'Above Normal (51-75th)',       '#1976D2', 0.85, 1.0),
    ('p26_50',           'Normal (26-50th)',             '#2E7D32', 0.85, 1.0),
    ('p11_25',           'Below Normal (11-25th)',       '#F9A825', 0.85, 1.0),
    ('p5_10',            'Low (5-10th)',                 '#E64A19', 0.90, 1.0),
    ('p0_4',             'Very Low (0-4th)',             '#880E4F', 0.90, 1.0),
    ('active_no_recent', 'Active (no 2-day data)',       '#9E9E9E', 0.60, 1.0),
    ('Inactive',         'Inactive',                    '#424242', 0.40, 0.6),
]

PERCENTILE_LABELS = {
    'p76_100':          'High (76-100th percentile)',
    'p51_75':           'Above Normal (51-75th percentile)',
    'p26_50':           'Normal (26-50th percentile)',
    'p11_25':           'Below Normal (11-25th percentile)',
    'p5_10':            'Low (5-10th percentile)',
    'p0_4':             'Very Low (0-4th percentile)',
    'active_no_recent': 'No 2-day data',
    'Inactive':         'Inactive',
}


class ModernMapComponent:
    """Modern map component using MapLibre (not deprecated mapbox)."""
    
    def __init__(self):
        """Initialize the modern map component."""
        self.current_gauges = pd.DataFrame()
        self.selected_gauge = None
        # Store last map view state to preserve zoom/pan between rebuilds
        self.last_center = dict(lat=MAP_CENTER_LAT, lon=MAP_CENTER_LON)
        self.last_zoom = DEFAULT_ZOOM_LEVEL
        
        # Watershed boundary data cache
        self._basin_cache = {}
        self._basemaps_dir = Path(__file__).parent.parent.parent / "data" / "basemaps"
        
    def create_gauge_map(self, gauges_df: pd.DataFrame, 
                        selected_gauge: Optional[str] = None,
                        map_style: str = 'open-street-map',
                        height: int = 700,
                        auto_fit_bounds: bool = True,
                        percentile_bands: dict = None) -> go.Figure:
        """
        Create interactive map using modern px.scatter_map (no deprecation warnings).
        
        Parameters:
        -----------
        gauges_df : pd.DataFrame
            DataFrame with gauge data including lat, lon, status, etc.
        selected_gauge : str, optional
            Site ID of gauge to highlight
        map_style : str
            Map style ('open-street-map', 'carto-positron', etc.)
        height : int
            Height of the map in pixels (default: 700)
            
        Returns:
        --------
        plotly.graph_objects.Figure
            Interactive map figure
        """
        self.current_gauges = gauges_df.copy()
        self.selected_gauge = selected_gauge
        
        # Handle empty dataframe
        if gauges_df.empty:
            return self._create_empty_map(map_style)
        
        # Calculate optimal map bounds if auto_fit_bounds is enabled
        if auto_fit_bounds:
            self._calculate_optimal_view(gauges_df)
        
        # Prepare data for px.scatter_map
        map_data = self._prepare_map_data(gauges_df, percentile_bands=percentile_bands or {})
        
        # Create modern map using px.scatter_map (NEW METHOD)
        # Prepare custom_data for tooltips
        # Note: years_of_record column may have been dropped for serialization
        custom_data_fields = [
            'site_id', 'state', 'catchment_area_display', 'years_of_record_display', 'status',
            'latitude', 'longitude', 'size_value', 'station_name'
        ]
        
        # Use go.Scattermapbox for all map styles with custom tile layers
        if map_style == 'stamen-terrain':
            fig = self._create_stamen_terrain_map(map_data, custom_data_fields, gauges_df, height)
        else:
            # Default to USGS National Map
            fig = self._create_usgs_national_map(map_data, custom_data_fields, gauges_df, height)
        # Set hovertemplate for each trace (10 customdata fields now)
        hovertemplate = (
            "<b>%{customdata[8]}</b><br>"
            "Site ID: %{customdata[0]}<br>"
            "State: %{customdata[1]}<br>"
            "Catchment Area: %{customdata[2]}<br>"
            "Years of Record: %{customdata[3]}<br>"
            "Status: %{customdata[4]}<br>"
            "Flow Condition: %{customdata[9]}<br>"
            "Lat: %{customdata[5]:.4f}, Lon: %{customdata[6]:.4f}<br>"
            "<extra></extra>"
        )
        for trace in fig.data:
            trace.hovertemplate = hovertemplate
        
        # Update layout with modern map configuration
        fig.update_layout(
            margin=dict(r=0, t=50, l=0, b=0),
            font=dict(family="Arial", size=12),
            legend=dict(
                orientation="v",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="black",
                borderwidth=1
            ),
            # NEW: hover configuration for modern maps
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="black",
                font=dict(size=12)
            )
        )
        
        # Add selected gauge highlight if specified
        if selected_gauge and selected_gauge in gauges_df['site_id'].values:
            self._add_selected_gauge_highlight(fig, gauges_df, selected_gauge)
            
        return fig
    
    def _prepare_map_data(self, gauges_df: pd.DataFrame, percentile_bands: dict = None) -> pd.DataFrame:
        """Prepare data for modern scatter_map visualization."""
        map_data = gauges_df.copy()
        
        # Ensure required columns exist
        if 'status' not in map_data.columns:
            # Use station_status if available, otherwise default
            if 'station_status' in map_data.columns:
                map_data['status'] = map_data['station_status']
            else:
                map_data['status'] = 'Active'  # Default status
        
        # Handle catchment_area (from API in sq km) - convert to display format
        if 'catchment_area' not in map_data.columns:
            map_data['catchment_area'] = None
        
        # Convert catchment/drainage area to display format
        # Check both drainage_area (from CSV in sq mi) and catchment_area (from API in sq km)
        def format_catchment_area(row):
            # First try drainage_area from CSV (already in sq mi)
            if 'drainage_area' in row and pd.notna(row['drainage_area']) and row['drainage_area'] > 0:
                try:
                    return f"{float(row['drainage_area']):,.1f} sq mi"
                except (ValueError, TypeError):
                    pass
            
            # Fall back to catchment_area from API (needs conversion from sq km)
            if pd.notna(row.get('catchment_area')) and row.get('catchment_area'):
                try:
                    sq_mi = float(row['catchment_area']) * 0.386102
                    return f"{sq_mi:,.1f} sq mi"
                except (ValueError, TypeError):
                    pass
            
            return 'N/A'
        
        map_data['catchment_area_display'] = map_data.apply(format_catchment_area, axis=1)
        
        # Ensure drainage_area exists for marker sizing
        # Use CSV drainage_area if available, otherwise try converting catchment_area
        if 'drainage_area' not in map_data.columns:
            map_data['drainage_area'] = pd.to_numeric(map_data['catchment_area'], errors='coerce') * 0.386102
        
        # Fill NaN drainage_area with default for sizing
        map_data['drainage_area'] = map_data['drainage_area'].fillna(100)
        
        # Handle years_of_record display
        def format_years_of_record(row):
            # Try years_of_record from API first
            if 'years_of_record' in row and pd.notna(row['years_of_record']):
                try:
                    years = int(float(row['years_of_record']))
                    return f"{years} years"
                except (ValueError, TypeError):
                    pass
            
            # Try to calculate from record dates
            if 'record_start_date' in row and 'record_end_date' in row:
                if pd.notna(row['record_start_date']) and pd.notna(row['record_end_date']):
                    try:
                        start = pd.to_datetime(row['record_start_date'])
                        end = pd.to_datetime(row['record_end_date'])
                        years = (end - start).days / 365.25
                        return f"{int(years)} years"
                    except Exception:
                        pass
            
            # Fall back to num_water_years if available
            if 'num_water_years' in row and pd.notna(row['num_water_years']):
                try:
                    years = int(row['num_water_years'])
                    return f"{years} years"
                except (ValueError, TypeError):
                    pass
            
            return 'N/A'
        
        map_data['years_of_record_display'] = map_data.apply(format_years_of_record, axis=1)
            
        # Create size values for markers (normalized) - Increased for better visibility
        if 'drainage_area' in map_data.columns and map_data['drainage_area'].notna().any():
            size_values = map_data['drainage_area'].fillna(100)
            # Normalize to reasonable marker sizes (10-25) - Increased from (5-20)
            size_min, size_max = size_values.min(), size_values.max()
            if size_max > size_min:
                normalized_size = 10 + 15 * (size_values - size_min) / (size_max - size_min)
            else:
                normalized_size = pd.Series([15] * len(size_values), index=size_values.index)
        else:
            normalized_size = pd.Series([15] * len(map_data), index=map_data.index)
            
        map_data['size_value'] = normalized_size
        
        # Assign map_group and percentile_label for color-coded rendering
        if percentile_bands is None:
            percentile_bands = {}
        
        def _assign_map_group(row):
            if row.get('status', 'Active') == 'Inactive':
                return 'Inactive'
            band = percentile_bands.get(row['site_id'])
            return band if band else 'active_no_recent'
        
        map_data['map_group'] = map_data.apply(_assign_map_group, axis=1)
        map_data['percentile_label'] = map_data['map_group'].map(PERCENTILE_LABELS).fillna('')
        
        return map_data
    
    def _create_usgs_national_map(self, map_data: pd.DataFrame, custom_data_fields: List, gauges_df: pd.DataFrame, height: int = 700) -> go.Figure:
        """Create map with USGS National Map basemap using custom tiles and go.Scattermapbox."""
        fig = go.Figure()
        
        # Render traces per percentile group in defined order
        for group_key, group_label, group_color, opacity, size_factor in PERCENTILE_GROUP_CONFIG:
            group_data = map_data[map_data['map_group'] == group_key]
            if group_data.empty:
                continue
            
            custom_data = []
            for _, row in group_data.iterrows():
                custom_data.append([
                    row['site_id'], row['state'], row['catchment_area_display'],
                    row['years_of_record_display'], row['status'], row['latitude'],
                    row['longitude'], row['size_value'], row['station_name'],
                    row.get('percentile_label', '')
                ])
            
            marker_sizes = group_data['size_value'] * size_factor
            
            fig.add_trace(go.Scattermapbox(
                lat=group_data['latitude'],
                lon=group_data['longitude'],
                mode='markers',
                marker=dict(size=marker_sizes, color=group_color, opacity=opacity),
                text=group_data['station_name'],
                name=f"{group_label} ({len(group_data)})",
                customdata=custom_data,
                hovertemplate=(
                    "<b>%{customdata[8]}</b><br>"
                    "Site ID: %{customdata[0]}<br>"
                    "State: %{customdata[1]}<br>"
                    "Catchment Area: %{customdata[2]}<br>"
                    "Years of Record: %{customdata[3]}<br>"
                    "Status: %{customdata[4]}<br>"
                    "Flow Condition: %{customdata[9]}<br>"
                    "Lat: %{customdata[5]:.4f}, Lon: %{customdata[6]:.4f}<br>"
                    "<extra></extra>"
                )
            ))
        
        # USGS National Map layers configuration matching your working example
        mapbox_layers = [
            {
                "below": "traces",
                "sourcetype": "raster", 
                "sourceattribution": "United States Geologic Society",
                "source": ["https://basemap.nationalmap.gov/arcgis/rest/services/USGSHydroCached/MapServer/tile/{z}/{y}/{x}"]
            }
        ]
        
        # Configure layout with USGS National Map tile layer using go.Layout()
        fig.update_layout(
            go.Layout(
                mapbox=dict(
                    style="white-bg",  # Use white background for custom tiles
                    layers=mapbox_layers,
                    center=self.last_center,
                    zoom=self.last_zoom
                ),
                height=height,
                margin=dict(r=0, t=50, l=0, b=0),
                title=f"USGS Streamflow Gauges - Pacific Northwest ({len(gauges_df)} gauges) - USGS National Map",
                font=dict(family="Arial", size=12),
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255, 255, 255, 0.9)",
                    bordercolor="black",
                    borderwidth=1
                ),
                hoverlabel=dict(
                    bgcolor="white",
                    bordercolor="black",
                    font=dict(size=12)
                )
            )
        )
        
        return fig

    def _create_stamen_terrain_map(self, map_data: pd.DataFrame, custom_data_fields: List, gauges_df: pd.DataFrame, height: int = 700) -> go.Figure:
        """Create map with Stamen Terrain basemap using Stadia Maps hosted tiles."""
        fig = go.Figure()
        
        # Render traces per percentile group in defined order
        for group_key, group_label, group_color, opacity, size_factor in PERCENTILE_GROUP_CONFIG:
            group_data = map_data[map_data['map_group'] == group_key]
            if group_data.empty:
                continue
            
            custom_data = []
            for _, row in group_data.iterrows():
                custom_data.append([
                    row['site_id'], row['state'], row['catchment_area_display'],
                    row['years_of_record_display'], row['status'], row['latitude'],
                    row['longitude'], row['size_value'], row['station_name'],
                    row.get('percentile_label', '')
                ])
            
            marker_sizes = group_data['size_value'] * size_factor
            
            fig.add_trace(go.Scattermapbox(
                lat=group_data['latitude'],
                lon=group_data['longitude'],
                mode='markers',
                marker=dict(size=marker_sizes, color=group_color, opacity=opacity),
                text=group_data['station_name'],
                name=f"{group_label} ({len(group_data)})",
                customdata=custom_data,
                hovertemplate=(
                    "<b>%{customdata[8]}</b><br>"
                    "Site ID: %{customdata[0]}<br>"
                    "State: %{customdata[1]}<br>"
                    "Catchment Area: %{customdata[2]}<br>"
                    "Years of Record: %{customdata[3]}<br>"
                    "Status: %{customdata[4]}<br>"
                    "Flow Condition: %{customdata[9]}<br>"
                    "Lat: %{customdata[5]:.4f}, Lon: %{customdata[6]:.4f}<br>"
                    "<extra></extra>"
                )
            ))
        
        # Stamen Terrain tiles hosted by Stadia Maps
        mapbox_layers = [
            {
                "below": "traces",
                "sourcetype": "raster",
                "sourceattribution": "Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL. Hosted by Stadia Maps.",
                "source": ["https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png"]
            }
        ]
        
        # Configure layout with Stamen Terrain tile layer
        fig.update_layout(
            go.Layout(
                mapbox=dict(
                    style="white-bg",
                    layers=mapbox_layers,
                    center=self.last_center,
                    zoom=self.last_zoom
                ),
                height=height,
                margin=dict(r=0, t=50, l=0, b=0),
                title=f"USGS Streamflow Gauges - Pacific Northwest ({len(gauges_df)} gauges) - Stamen Terrain",
                font=dict(family="Arial", size=12),
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01,
                    bgcolor="rgba(255, 255, 255, 0.9)",
                    bordercolor="black",
                    borderwidth=1
                ),
                hoverlabel=dict(
                    bgcolor="white",
                    bordercolor="black",
                    font=dict(size=12)
                )
            )
        )
        
        return fig
        
    def update_view_state(self, center_lat: float, center_lon: float, zoom: float):
        """Update stored view state to preserve zoom/pan between map rebuilds."""
        self.last_center = dict(lat=center_lat, lon=center_lon)
        self.last_zoom = zoom
    
    def _calculate_optimal_view(self, gauges_df: pd.DataFrame):
        """Calculate optimal center and zoom based on gauge locations."""
        if gauges_df.empty:
            return
        
        # Calculate bounds
        lat_min, lat_max = gauges_df['latitude'].min(), gauges_df['latitude'].max()
        lon_min, lon_max = gauges_df['longitude'].min(), gauges_df['longitude'].max()
        
        # Calculate center
        center_lat = (lat_min + lat_max) / 2
        center_lon = (lon_min + lon_max) / 2
        
        # Calculate zoom level based on data spread
        lat_range = lat_max - lat_min
        lon_range = lon_max - lon_min
        max_range = max(lat_range, lon_range)
        
        # Auto-zoom logic: larger spread = lower zoom level
        if max_range > 8:  # Very large area (multi-state)
            zoom_level = 4
        elif max_range > 4:  # Large area (state-wide)
            zoom_level = 5
        elif max_range > 2:  # Medium area (regional)
            zoom_level = 6
        elif max_range > 1:  # Smaller area (county-wide)
            zoom_level = 7
        elif max_range > 0.5:  # Small area (city-wide)
            zoom_level = 8
        else:  # Very small area
            zoom_level = 9
        
        # Constrain zoom to reasonable bounds
        zoom_level = max(MIN_ZOOM_LEVEL, min(MAX_ZOOM_LEVEL, zoom_level))
        
        # Update stored view state
        self.last_center = dict(lat=center_lat, lon=center_lon)
        self.last_zoom = zoom_level

    def _get_color_map(self) -> Dict[str, str]:
        """Get color mapping for gauge status."""
        return {
            'Active': '#32CD32',         # Lime Green - has recent data
            'Inactive': '#808080',       # Gray - no recent data
            'excellent': '#2E8B57',      # Sea Green (legacy)
            'good': '#FFD700',           # Gold (legacy)
            'fair': '#FF8C00',           # Dark Orange (legacy)
            'poor': '#DC143C',           # Crimson (legacy)
            'inactive': '#808080',       # Gray (legacy alias)
        }
    
    def _add_selected_gauge_highlight(self, fig: go.Figure, gauges_df: pd.DataFrame, 
                                    selected_gauge: str):
        """Add highlight for selected gauge using Scattermapbox (not Scattermap)."""
        selected_data = gauges_df[gauges_df['site_id'] == selected_gauge].iloc[0]
        
        # Add larger, more visible circle highlight for selected station
        # Layer 1: Outer ring (larger size, semi-transparent orange)
        fig.add_trace(go.Scattermapbox(
            lat=[selected_data['latitude']],
            lon=[selected_data['longitude']],
            mode='markers',
            marker=dict(
                size=28,  # Larger outer ring for visibility
                color='rgba(255, 69, 0, 0.4)',  # Orange with transparency
                symbol='circle'
            ),
            name='Selection Outer Ring',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Layer 2: Inner circle (solid, bright orange)
        fig.add_trace(go.Scattermapbox(
            lat=[selected_data['latitude']],
            lon=[selected_data['longitude']],
            mode='markers',
            marker=dict(
                size=16,  # Solid inner circle
                color='#FF4500',  # Orange red for high visibility
                symbol='circle'  # Simple circle - very visible
            ),
            hovertemplate=(
                f"<b>🎯 SELECTED: {selected_data['station_name']}</b><br>"
                f"Site ID: {selected_data['site_id']}<br>"
                f"Status: {selected_data.get('status', 'N/A')}<br>"
                f"<extra></extra>"
            ),
            name='Selected Gauge',
            showlegend=False
        ))
    
    def _create_empty_map(self, map_style: str = "open-street-map") -> go.Figure:
        """Create empty map with specified basemap style."""
        fig = go.Figure()
        fig.add_trace(go.Scattermapbox(
            lat=[],
            lon=[],
            mode='markers',
            showlegend=False
        ))
        
        # Build tile layers based on selected style
        if map_style == "stamen-terrain":
            mapbox_layers = [
                {
                    "below": "traces",
                    "sourcetype": "raster",
                    "sourceattribution": "Map tiles by Stamen Design, under CC BY 3.0. Data by OpenStreetMap, under ODbL. Hosted by Stadia Maps.",
                    "source": ["https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png"]
                }
            ]
        else:
            # Default: USGS National Map
            mapbox_layers = [
                {
                    "below": "traces",
                    "sourcetype": "raster", 
                    "sourceattribution": "United States Geologic Society",
                    "source": ["https://basemap.nationalmap.gov/arcgis/rest/services/USGSHydroCached/MapServer/tile/{z}/{y}/{x}"]
                }
            ]
        
        fig.update_layout(
            mapbox=dict(
                style="white-bg",
                layers=mapbox_layers,
                center=self.last_center,
                zoom=self.last_zoom
            ),
            height=700,
            margin=dict(r=0, t=50, l=0, b=0),
            title="No data available for selected filters"
        )
        
        return fig

    def _load_basin_geojson(self, basin_level: str, region: str = "pnw") -> Optional[Dict]:
        """
        Load watershed boundary GeoJSON file.
        
        Parameters:
        -----------
        basin_level : str
            Basin level: 'huc2', 'huc4', or 'huc8'
        region : str
            Region: 'pnw' (Pacific Northwest) or 'national'
            
        Returns:
        --------
        dict or None
            GeoJSON data if file exists, None otherwise
        """
        cache_key = f"{basin_level}_{region}"
        
        # Return cached data if available
        if cache_key in self._basin_cache:
            return self._basin_cache[cache_key]
        
        # Construct filename
        filename = f"{basin_level}_{region}.geojson"
        filepath = self._basemaps_dir / filename
        
        # Load from file
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    geojson_data = json.load(f)
                    self._basin_cache[cache_key] = geojson_data
                    return geojson_data
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                return None
        else:
            print(f"Basin file not found: {filepath}")
            return None
    
    def add_watershed_boundaries(self, fig: go.Figure, 
                                 show_huc2: bool = True,
                                 show_huc4: bool = True,
                                 show_huc6: bool = False,
                                 show_huc8: bool = False,
                                 region: str = "pnw") -> go.Figure:
        """
        Add watershed boundary layers to the map.
        
        Parameters:
        -----------
        fig : go.Figure
            Existing Plotly figure to add boundaries to
        show_huc2 : bool
            Show major regional basins (default: True)
        show_huc4 : bool
            Show sub-regional watersheds (default: True)
        show_huc6 : bool
            Show accounting units (default: False)
        show_huc8 : bool
            Show sub-basin watersheds (default: False, can be slow)
        region : str
            Region to display: 'pnw' or 'national' (default: 'pnw')
            
        Returns:
        --------
        go.Figure
            Figure with watershed boundary layers added
        """
        # Define layer styles
        layer_styles = {
            'huc2': {
                'color': 'rgba(139, 0, 139, 0.8)',  # Dark Magenta
                'width': 3,
                'name': 'Major Basins (HUC2)',
                'fill': 'rgba(139, 0, 139, 0.05)'
            },
            'huc4': {
                'color': 'rgba(0, 100, 200, 0.7)',  # Blue
                'width': 2,
                'name': 'Sub-Regions (HUC4)',
                'fill': 'rgba(0, 100, 200, 0.03)'
            },
            'huc6': {
                'color': 'rgba(255, 140, 0, 0.65)',  # Dark Orange
                'width': 1.5,
                'name': 'Accounting Units (HUC6)',
                'fill': 'rgba(255, 140, 0, 0.025)'
            },
            'huc8': {
                'color': 'rgba(34, 139, 34, 0.6)',  # Forest Green
                'width': 1,
                'name': 'Sub-Basins (HUC8)',
                'fill': 'rgba(34, 139, 34, 0.02)'
            }
        }
        
        # Add layers in order (largest to smallest)
        layers_to_add = []
        if show_huc8:
            layers_to_add.append('huc8')
        if show_huc6:
            layers_to_add.append('huc6')
        if show_huc4:
            layers_to_add.append('huc4')
        if show_huc2:
            layers_to_add.append('huc2')
        
        for level in layers_to_add:
            geojson_data = self._load_basin_geojson(level, region)
            if geojson_data:
                style = layer_styles[level]
                self._add_geojson_layer(fig, geojson_data, style)
        
        return fig
    
    def _add_geojson_layer(self, fig: go.Figure, geojson_data: Dict, style: Dict):
        """
        Add a GeoJSON layer to the map figure.
        
        Parameters:
        -----------
        fig : go.Figure
            Figure to add layer to
        geojson_data : dict
            GeoJSON FeatureCollection
        style : dict
            Style configuration (color, width, name, fill)
        """
        # Track if we've shown legend for this layer yet
        first_feature = True
        
        for feature in geojson_data.get('features', []):
            geometry = feature.get('geometry', {})
            properties = feature.get('properties', {})
            
            if geometry.get('type') == 'Polygon':
                coords = geometry.get('coordinates', [[]])[0]
                lons, lats = zip(*coords) if coords else ([], [])
                
                # Create hover text with basin info
                huc_code = properties.get('huc2') or properties.get('huc4') or properties.get('huc6') or properties.get('huc8', 'N/A')
                basin_name = properties.get('name', 'Unknown Basin')
                area_sqkm = properties.get('areasqkm', 'N/A')
                hover_text = f"<b>{basin_name}</b><br>HUC: {huc_code}<br>Area: {area_sqkm} km²"
                
                # Add filled polygon
                fig.add_trace(go.Scattermapbox(
                    lon=list(lons),
                    lat=list(lats),
                    mode='lines',
                    fill='toself',
                    fillcolor=style['fill'],
                    line=dict(color=style['color'], width=style['width']),
                    name=style['name'],
                    hovertext=hover_text,
                    hoverinfo='text',
                    showlegend=first_feature,  # Only show legend for first feature
                    legendgroup=style['name']
                ))
                first_feature = False
                
            elif geometry.get('type') == 'MultiPolygon':
                # Handle multi-polygon features
                for polygon in geometry.get('coordinates', []):
                    coords = polygon[0] if polygon else []
                    lons, lats = zip(*coords) if coords else ([], [])
                    
                    huc_code = properties.get('huc2') or properties.get('huc4') or properties.get('huc6') or properties.get('huc8', 'N/A')
                    basin_name = properties.get('name', 'Unknown Basin')
                    area_sqkm = properties.get('areasqkm', 'N/A')
                    hover_text = f"<b>{basin_name}</b><br>HUC: {huc_code}<br>Area: {area_sqkm} km²"
                    
                    fig.add_trace(go.Scattermapbox(
                        lon=list(lons),
                        lat=list(lats),
                        mode='lines',
                        fill='toself',
                        fillcolor=style['fill'],
                        line=dict(color=style['color'], width=style['width']),
                        name=style['name'],
                        hovertext=hover_text,
                        hoverinfo='text',
                        showlegend=first_feature,  # Only show legend for first feature
                        legendgroup=style['name']
                    ))
                    first_feature = False

    def create_simple_test_map(self) -> go.Figure:
        """Create a simple test map to verify functionality."""
        # Test data
        test_data = pd.DataFrame({
            'latitude': [45.0, 46.0, 44.0],
            'longitude': [-120.0, -121.0, -119.0],
            'station_name': ['Test Station 1', 'Test Station 2', 'Test Station 3'],
            'site_id': ['12345678', '87654321', '11111111'],
            'state': ['OR', 'WA', 'ID'],
            'drainage_area': [1000, 2000, 500],
            'status': ['excellent', 'good', 'fair'],
            'years_of_record': [25, 15, 10]
        })
        
        return self.create_gauge_map(test_data)
    
    def create_gauge_summary_stats(self, gauges_df: pd.DataFrame) -> Dict:
        """Create summary statistics for all gauges."""
        stats = {
            'total_gauges': len(gauges_df),
            'by_status': gauges_df['status'].value_counts().to_dict() if 'status' in gauges_df.columns else {},
            'by_state': gauges_df['state'].value_counts().to_dict() if 'state' in gauges_df.columns else {},
            'avg_years_record': gauges_df['num_water_years'].mean() if 'num_water_years' in gauges_df.columns else 0,
            'total_drainage_area': gauges_df['drainage_area'].sum() if 'drainage_area' in gauges_df.columns else 0,
            'active_gauges': len(gauges_df[gauges_df['status'] != 'inactive']) if 'status' in gauges_df.columns else len(gauges_df)
        }
        
        return stats

# Factory function for compatibility
def get_modern_map_component():
    """Get modern map component instance."""
    return ModernMapComponent()


# For backwards compatibility, but recommend using ModernMapComponent
class MapComponent(ModernMapComponent):
    """Backwards compatible map component using modern implementation."""
    pass


def get_map_component():
    """Get map component instance (modern implementation)."""
    return MapComponent()
