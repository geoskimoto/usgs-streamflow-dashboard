"""
USGS Dashboard Map Component - Updated to use Modern MapLibre Implementation

This component creates interactive maps showing USGS streamflow gauge locations.
Now uses px.scatter_map and go.Scattermap instead of deprecated mapbox components.
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

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from utils.config import (
    MAP_CONFIG, GAUGE_COLORS, MAP_CENTER_LAT, MAP_CENTER_LON,
    MIN_ZOOM_LEVEL, MAX_ZOOM_LEVEL, DEFAULT_ZOOM_LEVEL
)


class MapComponent:
    """Handles the interactive map display of USGS gauges."""
    
    def __init__(self):
        """Initialize map component."""
        self.current_gauges = pd.DataFrame()
        self.selected_gauge = None
        
    def create_gauge_map(self, gauges_df: pd.DataFrame, 
                        selected_gauge: str = None,
                        map_style: str = 'open-street-map') -> go.Figure:
        """
        Create interactive map with USGS gauge locations.
        
        Parameters:
        -----------
        gauges_df : pd.DataFrame
            DataFrame with gauge metadata including lat/lon
        selected_gauge : str
            Site ID of currently selected gauge
        map_style : str
            Map style ('open-street-map', 'satellite', etc.)
            
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
        
        # Create base map
        fig = go.Figure()
        
        # Add gauge markers by status
        for status in GAUGE_COLORS.keys():
            if 'status' not in gauges_df.columns:
                # If no status column, skip status-based rendering
                continue
                
            status_gauges = gauges_df[gauges_df['status'] == status]
            
            if len(status_gauges) == 0:
                continue
            
            # Create hover text
            hover_text = self._create_hover_text(status_gauges)
            
            # Determine marker size based on drainage area
            marker_sizes = self._calculate_marker_sizes(status_gauges)
            
            # Add trace for this status
            fig.add_trace(go.Scattermap(
                lat=status_gauges['latitude'],
                lon=status_gauges['longitude'],
                mode='markers',
                marker=dict(
                    size=marker_sizes,
                    color=GAUGE_COLORS[status]['color'],
                    opacity=GAUGE_COLORS[status]['opacity'],
                    sizemin=4
                ),
                text=status_gauges['site_id'],  # For click events
                hovertext=hover_text,
                hoverinfo='text',
                name=f"{status.title()} ({len(status_gauges)})",
                customdata=status_gauges['site_id'],  # For callbacks
                showlegend=True
            ))
        
        # Highlight selected gauge
        if selected_gauge and selected_gauge in gauges_df['site_id'].values:
            selected_data = gauges_df[gauges_df['site_id'] == selected_gauge].iloc[0]
            
            fig.add_trace(go.Scattermap(
                lat=[selected_data['latitude']],
                lon=[selected_data['longitude']],
                mode='markers',
                marker=dict(
                    size=25,
                    color='red',
                    symbol='circle-open'
                ),
                hovertext=f"<b>SELECTED:</b> {selected_data['station_name']}<br>" +
                         f"Site ID: {selected_data['site_id']}",
                hoverinfo='text',
                name='Selected Gauge',
                showlegend=False
            ))
        
        # Configure map layout
        fig.update_layout(
            mapbox=dict(
                style=map_style,
                center=dict(lat=MAP_CENTER_LAT, lon=MAP_CENTER_LON),
                zoom=DEFAULT_ZOOM_LEVEL
            ),
            height=600,
            margin=dict(l=0, r=0, t=30, b=0),
            title=dict(
                text=f"USGS Streamflow Gauges in Pacific Northwest ({len(gauges_df)} total)",
                x=0.5,
                font=dict(size=16)
            ),
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255, 255, 255, 0.8)",
                bordercolor="Black",
                borderwidth=1
            ),
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="black",
                font=dict(size=12)
            )
        )
        
        return fig
    
    def _create_empty_map(self) -> go.Figure:
        """Create an empty map when no data is available."""
        fig = go.Figure()
        
        fig.update_layout(
            mapbox=dict(
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
    
    def _create_hover_text(self, gauges_df: pd.DataFrame) -> List[str]:
        """Create hover text for gauge markers."""
        hover_texts = []
        
        for _, gauge in gauges_df.iterrows():
            # Format drainage area
            drainage_area = gauge.get('drainage_area', np.nan)
            if pd.notna(drainage_area) and drainage_area > 0:
                if drainage_area >= 1000:
                    da_text = f"{drainage_area:,.0f} sq mi"
                else:
                    da_text = f"{drainage_area:.1f} sq mi"
            else:
                da_text = "Unknown"
            
            # Format years of record
            years = gauge.get('years_of_record', 0)
            years_text = f"{years} years" if years > 0 else "No data"
            
            # Create hover text
            hover_text = (
                f"<b>{gauge['station_name']}</b><br>"
                f"Site ID: {gauge['site_id']}<br>"
                f"State: {gauge.get('state', 'Unknown')}<br>"
                f"Drainage Area: {da_text}<br>"
                f"Years of Record: {years_text}<br>"
                f"Status: {gauge['status'].title()}<br>"
                f"<i>Click for details</i>"
            )
            
            hover_texts.append(hover_text)
        
        return hover_texts
    
    def _calculate_marker_sizes(self, gauges_df: pd.DataFrame) -> List[float]:
        """Calculate marker sizes based on drainage area."""
        sizes = []
        
        for _, gauge in gauges_df.iterrows():
            drainage_area = gauge.get('drainage_area', np.nan)
            
            if pd.notna(drainage_area) and drainage_area > 0:
                # Scale marker size based on drainage area (log scale)
                # Small watersheds (< 100 sq mi): size 6-8
                # Medium watersheds (100-1000 sq mi): size 8-12
                # Large watersheds (1000-10000 sq mi): size 12-16
                # Very large watersheds (> 10000 sq mi): size 16-20
                
                log_area = np.log10(max(drainage_area, 1))
                
                if log_area < 2:  # < 100 sq mi
                    size = 6 + (log_area / 2) * 2
                elif log_area < 3:  # 100-1000 sq mi
                    size = 8 + ((log_area - 2) / 1) * 4
                elif log_area < 4:  # 1000-10000 sq mi
                    size = 12 + ((log_area - 3) / 1) * 4
                else:  # > 10000 sq mi
                    size = 16 + min((log_area - 4) / 1, 1) * 4
                
                sizes.append(max(6, min(20, size)))
            else:
                sizes.append(8)  # Default size
        
        return sizes
    
    def create_gauge_summary_stats(self, gauges_df: pd.DataFrame) -> Dict:
        """Create summary statistics for all gauges."""
        stats = {
            'total_gauges': len(gauges_df),
            'by_status': gauges_df['status'].value_counts().to_dict(),
            'by_state': gauges_df['state'].value_counts().to_dict(),
            'avg_years_record': gauges_df['years_of_record'].mean(),
            'total_drainage_area': gauges_df['drainage_area'].sum(),
            'active_gauges': len(gauges_df[gauges_df['status'] != 'inactive'])
        }
        
        return stats
    
    def filter_gauges_by_region(self, gauges_df: pd.DataFrame, 
                               bbox: Dict[str, float] = None,
                               min_years: int = 0,
                               states: List[str] = None,
                               min_drainage_area: float = 0) -> pd.DataFrame:
        """
        Filter gauges based on various criteria.
        
        Parameters:
        -----------
        gauges_df : pd.DataFrame
            Full gauge dataset
        bbox : dict
            Bounding box with 'north', 'south', 'east', 'west' keys
        min_years : int
            Minimum years of record
        states : list
            List of state codes to include
        min_drainage_area : float
            Minimum drainage area in square miles
            
        Returns:
        --------
        pd.DataFrame
            Filtered gauge dataset
        """
        filtered_df = gauges_df.copy()
        
        # Filter by bounding box
        if bbox:
            filtered_df = filtered_df[
                (filtered_df['latitude'] >= bbox['south']) &
                (filtered_df['latitude'] <= bbox['north']) &
                (filtered_df['longitude'] >= bbox['west']) &
                (filtered_df['longitude'] <= bbox['east'])
            ]
        
        # Filter by minimum years of record
        if min_years > 0:
            filtered_df = filtered_df[filtered_df['years_of_record'] >= min_years]
        
        # Filter by states
        if states:
            filtered_df = filtered_df[filtered_df['state'].isin(states)]
        
        # Filter by drainage area
        if min_drainage_area > 0:
            filtered_df = filtered_df[
                (pd.notna(filtered_df['drainage_area'])) &
                (filtered_df['drainage_area'] >= min_drainage_area)
            ]
        
        return filtered_df
    
    def get_gauge_clusters(self, gauges_df: pd.DataFrame, 
                          cluster_distance: float = 0.1) -> pd.DataFrame:
        """
        Identify clusters of nearby gauges for improved map display.
        
        Parameters:
        -----------
        gauges_df : pd.DataFrame
            Gauge dataset
        cluster_distance : float
            Distance threshold for clustering (in decimal degrees)
            
        Returns:
        --------
        pd.DataFrame
            Gauges with cluster information added
        """
        # Simple clustering based on lat/lon distance
        # In a production app, you might use more sophisticated clustering
        
        gauges_with_clusters = gauges_df.copy()
        gauges_with_clusters['cluster_id'] = -1
        
        cluster_id = 0
        unassigned_mask = gauges_with_clusters['cluster_id'] == -1
        
        while unassigned_mask.sum() > 0:
            # Find first unassigned gauge
            first_unassigned_idx = gauges_with_clusters[unassigned_mask].index[0]
            first_gauge = gauges_with_clusters.loc[first_unassigned_idx]
            
            # Find all gauges within cluster distance
            lat_diff = abs(gauges_with_clusters['latitude'] - first_gauge['latitude'])
            lon_diff = abs(gauges_with_clusters['longitude'] - first_gauge['longitude'])
            distance = (lat_diff**2 + lon_diff**2)**0.5
            
            cluster_mask = (distance <= cluster_distance) & unassigned_mask
            gauges_with_clusters.loc[cluster_mask, 'cluster_id'] = cluster_id
            
            cluster_id += 1
            unassigned_mask = gauges_with_clusters['cluster_id'] == -1
        
        return gauges_with_clusters
    
    def create_state_summary_map(self, gauges_df: pd.DataFrame) -> go.Figure:
        """Create a choropleth map showing gauge density by state."""
        
        # Count gauges by state
        state_counts = gauges_df['state'].value_counts().reset_index()
        state_counts.columns = ['state', 'gauge_count']
        
        # Create choropleth map
        fig = go.Figure(data=go.Choropleth(
            locations=state_counts['state'],
            z=state_counts['gauge_count'],
            locationmode='USA-states',
            colorscale='Viridis',
            text=state_counts['state'],
            hovertemplate='<b>%{text}</b><br>Gauges: %{z}<extra></extra>',
            colorbar=dict(title="Number of Gauges")
        ))
        
        fig.update_layout(
            title_text='USGS Streamflow Gauges by State',
            geo=dict(
                scope='usa',
                projection=go.layout.geo.Projection(type='albers usa'),
                showlakes=True,
                lakecolor='rgb(255, 255, 255)',
            ),
            height=400
        )
        
        return fig


# Convenience function for creating map component
def get_map_component() -> MapComponent:
    """Get initialized map component instance."""
    return MapComponent()
