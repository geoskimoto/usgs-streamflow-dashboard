"""
Modern Map Component for USGS Dashboard - MapLibre Implementation

Uses the new px.scatter_map and go.Scattermap (replaces deprecated mapbox).
This should resolve the grey box issue by using the current Plotly map API.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from ..utils.config import (
    MAP_CONFIG, GAUGE_COLORS, MAP_CENTER_LAT, MAP_CENTER_LON,
    MIN_ZOOM_LEVEL, MAX_ZOOM_LEVEL, DEFAULT_ZOOM_LEVEL
)


class ModernMapComponent:
    """Modern map component using MapLibre (not deprecated mapbox)."""
    
    def __init__(self):
        """Initialize the modern map component."""
        self.current_gauges = pd.DataFrame()
        self.selected_gauge = None
        # Store last map view state to preserve zoom/pan between rebuilds
        self.last_center = dict(lat=MAP_CENTER_LAT, lon=MAP_CENTER_LON)
        self.last_zoom = DEFAULT_ZOOM_LEVEL
        
    def create_gauge_map(self, gauges_df: pd.DataFrame, 
                        selected_gauge: Optional[str] = None,
                        map_style: str = 'open-street-map',
                        height: int = 700,
                        auto_fit_bounds: bool = True) -> go.Figure:
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
        map_data = self._prepare_map_data(gauges_df)
        
        # Create modern map using px.scatter_map (NEW METHOD)
        # Prepare custom_data for tooltips
        custom_data_fields = [
            'site_id', 'state', 'drainage_area', 'years_of_record', 'status',
            'latitude', 'longitude', 'size_value', 'station_name'
        ]
        
        # Use go.Scattermapbox for all map styles for consistency
        # Check if using custom USGS National Map
        if map_style == 'usgs-national':
            # Create figure with custom USGS tile layer
            fig = self._create_usgs_national_map(map_data, custom_data_fields, gauges_df, height)
        else:
            # Create figure with standard mapbox styles using go.Scattermapbox
            fig = self._create_standard_mapbox_map(map_data, custom_data_fields, gauges_df, map_style, height)
        # Set hovertemplate for each trace
        hovertemplate = (
            "<b>%{customdata[8]}</b><br>"
            "Site ID: %{customdata[0]}<br>"
            "State: %{customdata[1]}<br>"
            "Drainage Area: %{customdata[2]:,.0f} sq mi<br>"
            "Years of Record: %{customdata[3]}<br>"
            "Status: %{customdata[4]}<br>"
            "Lat: %{customdata[5]:.4f}, Lon: %{customdata[6]:.4f}<br>"
            "Size Value: %{customdata[7]:.1f}<br>"
            "<extra></extra>"
        )
        for trace in fig.data:
            trace.hovertemplate = hovertemplate
        
        # Update layout with modern map configuration
        fig.update_layout(
            margin=dict(r=0, t=50, l=0, b=0),
            font=dict(family="Arial", size=12),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(255, 255, 255, 0.8)",
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
    
    def _prepare_map_data(self, gauges_df: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for modern scatter_map visualization."""
        map_data = gauges_df.copy()
        
        # Ensure required columns exist
        if 'status' not in map_data.columns:
            map_data['status'] = 'good'  # Default status
            
        if 'drainage_area' not in map_data.columns:
            map_data['drainage_area'] = 100  # Default size
            
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
        
        return map_data
    
    def _create_usgs_national_map(self, map_data: pd.DataFrame, custom_data_fields: List, gauges_df: pd.DataFrame, height: int = 700) -> go.Figure:
        """Create map with USGS National Map basemap using custom tiles and go.Scattermapbox."""
        fig = go.Figure()
        
        # Group by status for different traces
        color_map = self._get_color_map()
        
        for status in map_data['status'].unique():
            status_data = map_data[map_data['status'] == status]
            
            # Prepare custom data for this status group
            custom_data = []
            for _, row in status_data.iterrows():
                custom_data.append([
                    row['site_id'], row['state'], row['drainage_area'], 
                    row['years_of_record'], row['status'], row['latitude'], 
                    row['longitude'], row['size_value'], row['station_name']
                ])
            
            fig.add_trace(go.Scattermapbox(
                lat=status_data['latitude'],
                lon=status_data['longitude'],
                mode='markers',
                marker=dict(
                    size=status_data['size_value'],
                    color=color_map.get(status, '#808080'),
                    opacity=0.8
                ),
                text=status_data['station_name'],
                name=status.title(),
                customdata=custom_data,
                hovertemplate=(
                    "<b>%{customdata[8]}</b><br>"
                    "Site ID: %{customdata[0]}<br>"
                    "State: %{customdata[1]}<br>"
                    "Drainage Area: %{customdata[2]:,.0f} sq mi<br>"
                    "Years of Record: %{customdata[3]}<br>"
                    "Status: %{customdata[4]}<br>"
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
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    bgcolor="rgba(255, 255, 255, 0.8)",
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

    def _create_standard_mapbox_map(self, map_data: pd.DataFrame, custom_data_fields: List, gauges_df: pd.DataFrame, map_style: str, height: int = 700) -> go.Figure:
        """Create map with standard mapbox basemap styles using go.Scattermapbox."""
        fig = go.Figure()
        
        # Validate map style
        valid_map_styles = [
            'open-street-map', 'satellite-streets', 'outdoors', 'light', 'dark', 'white-bg',
            'carto-positron', 'carto-darkmatter', 'stamen-terrain', 'stamen-toner', 'stamen-watercolor'
        ]
        
        if map_style not in valid_map_styles:
            print(f"Warning: Invalid map style '{map_style}', using default 'open-street-map'")
            map_style = 'open-street-map'
        
        # Group by status for different traces
        color_map = self._get_color_map()
        
        for status in map_data['status'].unique():
            status_data = map_data[map_data['status'] == status]
            
            # Prepare custom data for this status group
            custom_data = []
            for _, row in status_data.iterrows():
                custom_data.append([
                    row['site_id'], row['state'], row['drainage_area'], 
                    row['years_of_record'], row['status'], row['latitude'], 
                    row['longitude'], row['size_value'], row['station_name']
                ])
            
            fig.add_trace(go.Scattermapbox(
                lat=status_data['latitude'],
                lon=status_data['longitude'],
                mode='markers',
                marker=dict(
                    size=status_data['size_value'],
                    color=color_map.get(status, '#808080'),
                    opacity=0.8
                ),
                text=status_data['station_name'],
                name=status.title(),
                customdata=custom_data,
                hovertemplate=(
                    "<b>%{customdata[8]}</b><br>"
                    "Site ID: %{customdata[0]}<br>"
                    "State: %{customdata[1]}<br>"
                    "Drainage Area: %{customdata[2]:,.0f} sq mi<br>"
                    "Years of Record: %{customdata[3]}<br>"
                    "Status: %{customdata[4]}<br>"
                    "Lat: %{customdata[5]:.4f}, Lon: %{customdata[6]:.4f}<br>"
                    "<extra></extra>"
                )
            ))
        
        # Configure layout with standard mapbox style (no custom layers)
        fig.update_layout(
            mapbox=dict(
                style=map_style,  # Use standard mapbox styles
                center=self.last_center,
                zoom=self.last_zoom
            ),
            height=height,
            margin=dict(r=0, t=50, l=0, b=0),
            title=f"USGS Streamflow Gauges - Pacific Northwest ({len(gauges_df)} gauges)",
            font=dict(family="Arial", size=12),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="black",
                borderwidth=1
            ),
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="black",
                font=dict(size=12)
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
            'excellent': '#2E8B57',      # Sea Green
            'good': '#FFD700',           # Gold
            'fair': '#FF8C00',           # Dark Orange  
            'poor': '#DC143C',           # Crimson
            'inactive': '#808080',       # Gray
            'active_excellent': '#2E8B57',
            'active_good': '#32CD32',    # Lime Green
            'active_fair': '#FFA500',    # Orange
            'active_poor': '#FF6347'     # Tomato
        }
    
    def _add_selected_gauge_highlight(self, fig: go.Figure, gauges_df: pd.DataFrame, 
                                    selected_gauge: str):
        """Add highlight for selected gauge using modern Scattermap."""
        selected_data = gauges_df[gauges_df['site_id'] == selected_gauge].iloc[0]
        
        # Add professional multi-layer selection highlight (reduced sizes)
        # Layer 1: Outer ring (moderate size, semi-transparent)
        fig.add_trace(go.Scattermap(
            lat=[selected_data['latitude']],
            lon=[selected_data['longitude']],
            mode='markers',
            marker=dict(
                size=20,  # Reduced from 35
                color='rgba(255, 69, 0, 0.3)',  # Orange with transparency
                symbol='circle'
            ),
            name='Selection Outer Ring',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Layer 2: Inner highlight (smaller diamond)
        fig.add_trace(go.Scattermap(
            lat=[selected_data['latitude']],
            lon=[selected_data['longitude']],
            mode='markers',
            marker=dict(
                size=14,  # Reduced from 22
                color='#FF4500',  # Orange red for visibility
                symbol='diamond'  # Professional diamond shape (no line property supported in Scattermap)
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
        
        # Handle USGS National Map style
        if map_style == "usgs-national":
            # USGS National Map layers using your working configuration
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
                title="No data available for selected filters - USGS National Map"
            )
        else:
            fig.update_layout(
                mapbox=dict(
                    style=map_style,
                    center=self.last_center,
                    zoom=self.last_zoom
                ),
                height=700,
                margin=dict(r=0, t=50, l=0, b=0),
                title="No data available for selected filters"
            )
        
        return fig

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
            'avg_years_record': gauges_df['years_of_record'].mean() if 'years_of_record' in gauges_df.columns else 0,
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
