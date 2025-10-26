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
from utils.config import (
    MAP_CONFIG, GAUGE_COLORS, MAP_CENTER_LAT, MAP_CENTER_LON,
    MIN_ZOOM_LEVEL, MAX_ZOOM_LEVEL, DEFAULT_ZOOM_LEVEL
)


class ModernMapComponent:
    """Modern map component using MapLibre (not deprecated mapbox)."""
    
    def __init__(self):
        """Initialize the modern map component."""
        self.current_gauges = pd.DataFrame()
        self.selected_gauge = None
        
    def create_gauge_map(self, gauges_df: pd.DataFrame, 
                        selected_gauge: Optional[str] = None,
                        map_style: str = 'open-street-map') -> go.Figure:
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
            
        Returns:
        --------
        plotly.graph_objects.Figure
            Interactive map figure
        """
        self.current_gauges = gauges_df.copy()
        self.selected_gauge = selected_gauge
        
        # Handle empty dataframe
        if gauges_df.empty:
            return self._create_empty_map()
        
        # Prepare data for px.scatter_map
        map_data = self._prepare_map_data(gauges_df)
        
        # Create modern map using px.scatter_map (NEW METHOD)
        fig = px.scatter_map(
            map_data,
            lat="latitude",
            lon="longitude", 
            hover_name="station_name",
            hover_data={
                "site_id": True,
                "state": True,
                "drainage_area": ":,",
                "status": True,
                "years_of_record": True,
                "latitude": ":.4f",
                "longitude": ":.4f"
            },
            color="status",
            color_discrete_map=self._get_color_map(),
            size="size_value",
            size_max=20,
            zoom=DEFAULT_ZOOM_LEVEL,
            map_style=map_style,  # NEW: map_style not mapbox_style
            center=dict(lat=MAP_CENTER_LAT, lon=MAP_CENTER_LON),
            height=700,
            title=f"USGS Streamflow Gauges - Pacific Northwest ({len(gauges_df)} gauges)"
        )
        
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
            
        # Create size values for markers (normalized)
        if 'drainage_area' in map_data.columns and map_data['drainage_area'].notna().any():
            size_values = map_data['drainage_area'].fillna(100)
            # Normalize to reasonable marker sizes (5-20)
            size_min, size_max = size_values.min(), size_values.max()
            if size_max > size_min:
                normalized_size = 5 + 15 * (size_values - size_min) / (size_max - size_min)
            else:
                normalized_size = pd.Series([10] * len(size_values), index=size_values.index)
        else:
            normalized_size = pd.Series([10] * len(map_data), index=map_data.index)
            
        map_data['size_value'] = normalized_size
        
        return map_data
    
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
        
        # Add highlighted marker using NEW go.Scattermap
        fig.add_trace(go.Scattermap(  # NEW: Scattermap not Scattermapbox
            lat=[selected_data['latitude']],
            lon=[selected_data['longitude']],
            mode='markers',
            marker=dict(
                size=25,
                color='#FF1493',  # Hot pink for selection
                symbol='star'  # Removed line property - not supported in Scattermap
            ),
            hovertemplate=(
                f"<b>SELECTED: {selected_data['station_name']}</b><br>"
                f"Site ID: {selected_data['site_id']}<br>"
                f"<extra></extra>"
            ),
            name='Selected Gauge',
            showlegend=False
        ))
    
    def _create_empty_map(self) -> go.Figure:
        """Create an empty map when no data is available."""
        # Use modern approach for empty map too
        fig = go.Figure()
        
        fig.update_layout(
            map=dict(  # NEW: map not mapbox
                style='open-street-map',
                center=dict(lat=MAP_CENTER_LAT, lon=MAP_CENTER_LON),
                zoom=DEFAULT_ZOOM_LEVEL
            ),
            height=700,
            margin=dict(l=0, r=0, t=30, b=0),
            title=dict(
                text="No gauge data available",
                x=0.5,
                font=dict(size=16, color='gray')
            ),
            annotations=[dict(
                text="No gauges match the current filters",
                x=0.5, y=0.5,
                xref="paper", yref="paper",
                showarrow=False,
                font=dict(size=14, color="gray")
            )]
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
