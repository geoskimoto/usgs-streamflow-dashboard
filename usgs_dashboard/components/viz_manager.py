"""
Visualization Manager for USGS Streamflow Dashboard

Integrates streamflow analysis and visualization capabilities.
"""

import sys
import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

# Import the streamflow analysis tools
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)
try:
    from streamflow_analyzer import StreamflowData, StreamflowVisualizer
except ImportError:
    print("Warning: Could not import streamflow analysis tools. Creating fallback classes.")
    StreamflowData = None
    StreamflowVisualizer = None

from ..utils.config import WATER_YEAR_START, DEFAULT_PERCENTILES
from ..utils.water_year_datetime import get_water_year_handler


class VisualizationManager:
    """Manages visualization creation for streamflow dashboard."""
    
    def __init__(self):
        """Initialize visualization manager."""
        self.streamflow_viz = None  # Will be created when we have data
        self.current_data = None
        self.current_site_id = None
        self.wy_handler = get_water_year_handler()  # Water year datetime handler
        
    def create_streamflow_plot(self, site_id: str, streamflow_data: pd.DataFrame,
                             plot_type: str = 'water_year',
                             highlight_years: List[int] = None,
                             show_percentiles: bool = True,
                             show_statistics: bool = True,
                             data_manager=None) -> go.Figure:
        """
        Create streamflow visualization plot.
        
        Parameters:
        -----------
        site_id : str
            USGS site ID
        streamflow_data : pd.DataFrame
            Streamflow data with datetime and discharge columns
        plot_type : str
            Type of plot ('water_year', 'annual', 'monthly', 'daily')
        highlight_years : list
            Years to highlight in the plot
        show_percentiles : bool
            Whether to show percentile bands
        show_statistics : bool
            Whether to show statistical overlays
            
        Returns:
        --------
        go.Figure
            Plotly figure with streamflow visualization
        """
        self.current_data = streamflow_data.copy()
        self.current_site_id = site_id
        
        # Get real-time data if data_manager is available
        realtime_data = None
        if data_manager:
            try:
                realtime_data = data_manager.get_realtime_data(site_id)
                if not realtime_data.empty:
                    print(f"Retrieved {len(realtime_data)} real-time records for visualization")
                else:
                    print(f"No real-time data available for site {site_id}")
            except Exception as e:
                print(f"Error getting real-time data: {e}")
                realtime_data = None
        
        # Use integrated streamflow analyzer if available
        if self.streamflow_viz and StreamflowData:
            try:
                return self._create_integrated_plot(
                    site_id, streamflow_data, plot_type, 
                    highlight_years, show_percentiles, show_statistics, realtime_data
                )
            except Exception as e:
                print(f"Error with integrated plot, using fallback: {e}")
                return self._create_fallback_plot(
                    site_id, streamflow_data, plot_type, highlight_years,
                    show_percentiles, show_statistics, realtime_data
                )
        else:
            return self._create_fallback_plot(
                site_id, streamflow_data, plot_type, highlight_years,
                show_percentiles, show_statistics, realtime_data
            )
    
    def _create_integrated_plot(self, site_id: str, data: pd.DataFrame,
                              plot_type: str, highlight_years: List[int],
                              show_percentiles: bool, show_statistics: bool, realtime_data: pd.DataFrame = None) -> go.Figure:
        """Create plot using integrated streamflow analysis tools."""
        
        # Prepare data for StreamflowData class
        # Assume data has columns like 'datetime' and discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        
        if value_col is None:
            # Use the first numeric column after datetime
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                value_col = numeric_cols[0]
            else:
                raise ValueError("No numeric discharge column found")
        
        # Create StreamflowData instance
        sf_data = StreamflowData(
            data=data,
            site_id=site_id,
            date_column='datetime' if 'datetime' in data.columns else data.index.name,
            value_column=value_col
        )
        
        # Create StreamflowVisualizer with the data
        streamflow_viz = StreamflowVisualizer(sf_data)
        
        # Create appropriate plot based on type
        if plot_type == 'water_year':
            # Pass the parameters correctly to create_stacked_line_plot
            config = {
                'highlight_years': highlight_years or [],
                'show_mean': show_statistics,
                'show_median': show_statistics, 
                'percentile_bands': [25, 75] if show_percentiles else [],
                'show_percentile_bands': show_percentiles
            }
            fig = streamflow_viz.create_stacked_line_plot(**config)
        elif plot_type == 'annual':
            fig = streamflow_viz.create_annual_summary()
        elif plot_type == 'monthly':
            fig = streamflow_viz.create_monthly_comparison()
        else:  # daily or default
            fig = self._create_daily_timeseries_plot(sf_data)
        
        return fig
    
    def _create_fallback_plot(self, site_id: str, data: pd.DataFrame,
                            plot_type: str, highlight_years: List[int],
                            show_percentiles: bool = True, 
                            show_statistics: bool = True, realtime_data: pd.DataFrame = None) -> go.Figure:
        """
        Create basic fallback plot when integrated tools aren't available.
        Robust date handling:
        - Only set index to a valid date column ('datetime', 'date', 'timestamp').
        - If no valid date column exists, skip plotting and show error.
        - Never convert a pure integer index to datetime.
        - Documented logic and debug output for expected behavior.
        """
        # Make a copy to avoid modifying the original data
        data = data.copy()
        
        # Get discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        if value_col is None:
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                value_col = numeric_cols[0]
            else:
                return self._create_error_plot("No discharge data found")
        # Robust date column check
        date_col = None
        for col in data.columns:
            if col.lower() in ['datetime', 'date', 'dates', 'timestamp']:
                date_col = col
                break
        if date_col:
            # Try to set index to date column
            try:
                data[date_col] = pd.to_datetime(data[date_col], errors='coerce')
                data = data.set_index(date_col)
            except Exception as e:
                print(f"[ERROR] Failed to set index to date column '{date_col}': {e}")
                return self._create_error_plot(f"Failed to parse date column '{date_col}' for plotting.")
        elif not isinstance(data.index, pd.DatetimeIndex):
            # No valid date column, do NOT convert integer index to datetime
            print("[ERROR] No valid date column found. Cannot plot. Returning error plot.")
            return self._create_error_plot("No valid date column found for plotting.")
        # Remove timezone info to avoid mixing issues
        if hasattr(data.index, 'tz') and data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        # Remove any rows with invalid dates
        data = data.dropna()
        fig = go.Figure()
        if plot_type == 'water_year':
            # Use the new clean water year handler with enhanced features
            fig = self.wy_handler.create_water_year_plot(
                data, value_col, highlight_years, 
                title=f"Water Year Plot - Site {site_id}",
                show_current_year=True,  # Default to current water year
                show_statistics=True,    # Show mean and median lines
                show_current_day=True,   # Show current day marker
                show_percentiles=True,   # Show percentile bands for context
                use_default_zoom=True    # Enable ±30 day zoom from current day
            )
        else:
            fig = self._create_basic_timeseries_plot(data, value_col)
            
        # Add real-time data overlay if available
        if realtime_data is not None and not realtime_data.empty:
            fig = self._add_realtime_overlay(fig, realtime_data, site_id)
        # Update layout (only for non-water year plots since water year handler manages its own)
        if plot_type != 'water_year':
            fig.update_layout(
                title=f"Streamflow Data - Site {site_id}",
                xaxis_title="Date",
                yaxis_title="Discharge (cfs)",
                height=500,
                showlegend=True
            )
        return fig
    
    def _day_of_wy_to_monthday(self, day_of_wy: int) -> str:
        """Convert day of water year to month-day string (e.g., Jan 1)."""
        # Water year starts Oct 1
        wy_start = pd.Timestamp(year=2000, month=10, day=1)  # 2000 is arbitrary non-leap year
        date = wy_start + pd.Timedelta(days=day_of_wy - 1)
        return date.strftime('%b %-d')
    
    def _create_basic_water_year_plot(self, data: pd.DataFrame, value_col: str,
                                    highlight_years: List[int]) -> go.Figure:
        """Create basic water year plot."""
        
        # Add water year and day of water year
        data_copy = data.copy()
        
        # Ensure index is datetime
        if not isinstance(data_copy.index, pd.DatetimeIndex):
            if 'datetime' in data_copy.columns:
                data_copy = data_copy.set_index('datetime')
            else:
                # Try to convert index to datetime
                data_copy.index = pd.to_datetime(data_copy.index, errors='coerce')
        
        # Filter out any rows with invalid dates
        data_copy = data_copy.dropna()
        
        # Now safely calculate water year and day
        data_copy['water_year'] = data_copy.index.map(self._get_water_year)
        data_copy['day_of_wy'] = data_copy.index.map(self._get_day_of_water_year)
        
        fig = go.Figure()
        
        # Get unique years
        years = sorted(data_copy['water_year'].unique())
        
        # Plot each year
        for year in years:
            year_data = data_copy[data_copy['water_year'] == year]
            
            if len(year_data) == 0:
                continue
            
            # Determine line properties  
            if highlight_years and year in highlight_years:
                # Use different colors for each highlighted year
                highlight_index = highlight_years.index(year)
                highlight_colors = ['#FF0000', '#FF8C00', '#9932CC', '#228B22', '#DC143C', 
                                  '#4169E1', '#FF1493', '#32CD32', '#FF6347', '#8A2BE2']
                color_index = highlight_index % len(highlight_colors)
                line_color = highlight_colors[color_index]
                line_width = 3
                opacity = 1.0
                showlegend = True
                name = f"WY {year}"  # Clean year only, no extra text
            else:
                line_color = 'lightblue'
                line_width = 1
                opacity = 0.6
                showlegend = False
                name = f"WY {year}"
            
            fig.add_trace(go.Scatter(
                x=year_data['day_of_wy'],
                y=year_data[value_col],
                mode='lines',
                name=name,
                line=dict(color=line_color, width=line_width),
                opacity=opacity,
                showlegend=showlegend,
                hovertemplate=f"<b>Water Year {year}</b><br>" +
                            "Day %{x}<br>" +
                            "Discharge: %{y:.1f} cfs<extra></extra>"
            ))
        
        # Add median line if enough data
        if len(years) >= 5:
            daily_medians = data_copy.groupby('day_of_wy')[value_col].median()
            
            fig.add_trace(go.Scatter(
                x=daily_medians.index,
                y=daily_medians.values,
                mode='lines',
                name='Median (All Years)',
                line=dict(color='black', width=2),
                hovertemplate="Day %{x}<br>Median: %{y:.1f} cfs<extra></extra>"
            ))
        
        # After adding traces, set x-axis labels
        max_day = int(data_copy['day_of_wy'].max())
        tickvals = list(range(1, max_day+1, max(1, max_day//12)))
        ticktext = [self._day_of_wy_to_monthday(d) for d in tickvals]
        fig.update_xaxes(
            tickvals=tickvals, 
            ticktext=ticktext, 
            title="Month-Day",
            type='linear'  # Force linear axis, not datetime
        )
        
        return fig
    
    def _create_enhanced_water_year_plot(self, data: pd.DataFrame, value_col: str,
                                       highlight_years: List[int],
                                       show_percentiles: bool = True,
                                       show_statistics: bool = True) -> go.Figure:
        """
        Create enhanced water year plot with percentile bands.
        Robust date handling: Only set index to a valid date column ('datetime', 'date', 'timestamp').
        If no valid date column exists, skip plotting and show error.
        Documented logic and debug output for expected behavior.
        """
        # Debug: Log index type and sample
        print("[DEBUG] Water Year Plot: Data index type:", type(data.index))
        print("[DEBUG] Water Year Plot: Data index sample:", data.index[:5].tolist() if hasattr(data.index, 'tolist') else data.index)
        print("[DEBUG] Water Year Plot: Data columns:", data.columns.tolist())
        # Check for date/datetime columns
        date_cols = [col for col in data.columns if 'date' in col.lower() or 'time' in col.lower()]
        print("[DEBUG] Water Year Plot: Date columns:", date_cols)
        # Add water year and day of water year
        data_copy = data.copy()
        # Ensure index is datetime
        # Robust date column check
        if not isinstance(data_copy.index, pd.DatetimeIndex):
            # Try to find a valid date column
            date_col = None
            for col in data_copy.columns:
                if col.lower() in ['datetime', 'date', 'dates', 'timestamp']:
                    date_col = col
                    break
            if date_col:
                print(f"[DEBUG] Setting index to '{date_col}' column.")
                data_copy[date_col] = pd.to_datetime(data_copy[date_col], errors='coerce')
                data_copy = data_copy.set_index(date_col)
            else:
                print("[ERROR] No valid date column found. Cannot plot Water Year. Returning error plot.")
                return self._create_error_plot("No valid date column found for Water Year plot.")
        print("[DEBUG] After index conversion: Data index type:", type(data_copy.index))
        print("[DEBUG] After index conversion: Data index sample:", data_copy.index[:5].tolist() if hasattr(data_copy.index, 'tolist') else data_copy.index)
        # Filter out any rows with invalid dates
        data_copy = data_copy.dropna()
        print("[DEBUG] After dropna: Data shape:", data_copy.shape)
        # Now safely calculate water year and day
        data_copy['water_year'] = data_copy.index.map(self._get_water_year)
        data_copy['day_of_wy'] = data_copy.index.map(self._get_day_of_water_year)
        print("[DEBUG] Unique water_years:", data_copy['water_year'].unique())
        print("[DEBUG] Unique day_of_wy (first 10):", data_copy['day_of_wy'].unique()[:10])
        # Debug: Check for 1970 or other default years
        if np.all(data_copy.index.year == 1970):
            print("[ERROR] All index years are 1970! Likely a conversion issue.")
        # Debug: Log x-axis values for first year
        if len(data_copy) > 0:
            first_year = data_copy['water_year'].min()
            year_data = data_copy[data_copy['water_year'] == first_year]
            print(f"[DEBUG] First year ({first_year}) day_of_wy sample:", year_data['day_of_wy'][:10].tolist())
        fig = go.Figure()
        # Calculate percentile bands first (25th, 75th percentiles)
        if show_percentiles and len(data_copy) > 100:
            daily_stats = data_copy.groupby('day_of_wy')[value_col].agg([
                'median', 
                lambda x: x.quantile(0.25),
                lambda x: x.quantile(0.75),
                lambda x: x.quantile(0.10),
                lambda x: x.quantile(0.90)
            ])
            daily_stats.columns = ['median', 'q25', 'q75', 'q10', 'q90']
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q90'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),
                showlegend=False,
                name='90th percentile'
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q10'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),
                fill='tonexty',
                fillcolor='rgba(173, 216, 230, 0.3)',
                showlegend=True,
                name='10th-90th percentile'
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q75'],
                mode='lines',
                line=dict(color='rgba(100, 149, 237, 0)'),
                showlegend=False,
                name='75th percentile'
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q25'],
                mode='lines',
                line=dict(color='rgba(100, 149, 237, 0)'),
                fill='tonexty',
                fillcolor='rgba(100, 149, 237, 0.4)',
                showlegend=True,
                name='25th-75th percentile'
            ))
        # Get unique years
        years = sorted(data_copy['water_year'].unique())
        print("[DEBUG] Years to plot:", years)
        
        # Define colors for highlighted years
        highlight_colors = [
            '#FF0000',  # Red
            '#FF8C00',  # Dark Orange  
            '#9932CC',  # Dark Orchid
            '#228B22',  # Forest Green
            '#DC143C',  # Crimson
            '#4169E1',  # Royal Blue
            '#FF1493',  # Deep Pink
            '#32CD32',  # Lime Green
            '#FF6347',  # Tomato
            '#8A2BE2'   # Blue Violet
        ]
        
        # Plot each year
        for i, year in enumerate(years):
            year_data = data_copy[data_copy['water_year'] == year]
            if len(year_data) == 0:
                continue
            # Debug: Log x and y sample for this year
            print(f"[DEBUG] Plotting year {year}: day_of_wy sample:", year_data['day_of_wy'][:10].tolist())
            print(f"[DEBUG] Plotting year {year}: discharge sample:", year_data[value_col][:10].tolist())
            # Determine line properties
            if highlight_years and year in highlight_years:
                # Use different colors for each highlighted year
                highlight_index = highlight_years.index(year)
                color_index = highlight_index % len(highlight_colors)
                line_color = highlight_colors[color_index]
                line_width = 3
                opacity = 1.0
                showlegend = True
                name = f"WY {year}"  # Clean year only, no extra text
            else:
                line_color = 'lightblue'
                line_width = 1
                opacity = 0.6
                showlegend = False
                name = f"WY {year}"
            fig.add_trace(go.Scatter(
                x=year_data['day_of_wy'],
                y=year_data[value_col],
                mode='lines',
                name=name,
                line=dict(color=line_color, width=line_width),
                opacity=opacity,
                showlegend=showlegend,
                hovertemplate=f"<b>Water Year {year}</b><br>" +
                            "Day %{x}<br>" +
                            "Discharge: %{y:.1f} cfs<extra></extra>"
            ))
        
        # Add median/mean line LAST so it appears on top of all year traces
        if show_statistics and len(data_copy) > 50:
            daily_stats = data_copy.groupby('day_of_wy')[value_col].median()
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats.values,
                mode='lines',
                name='Long-term Median',
                line=dict(color='black', width=3),  # Made thicker for better visibility
                hovertemplate="Day %{x}<br>Median: %{y:.1f} cfs<extra></extra>"
            ))
        
        # After adding traces, set x-axis labels
        max_day = int(data_copy['day_of_wy'].max())
        tickvals = list(range(1, max_day+1, max(1, max_day//12)))
        ticktext = [self._day_of_wy_to_monthday(d) for d in tickvals]
        fig.update_xaxes(
            tickvals=tickvals, 
            ticktext=ticktext, 
            title="Month-Day",
            type='linear'  # Force linear axis, not datetime
        )
        return fig
    
    def _create_basic_timeseries_plot(self, data: pd.DataFrame, value_col: str) -> go.Figure:
        """Create basic timeseries plot."""
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data[value_col],
            mode='lines',
            name='Daily Discharge',
            line=dict(color='blue', width=1),
            hovertemplate="Date: %{x}<br>Discharge: %{y:.1f} cfs<extra></extra>"
        ))
        
        return fig
    
    def _create_daily_timeseries_plot(self, sf_data) -> go.Figure:
        """Create daily timeseries plot using StreamflowData."""
        
        data = sf_data.data
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data[sf_data.value_column],
            mode='lines',
            name='Daily Discharge',
            line=dict(color='blue', width=1),
            hovertemplate="Date: %{x}<br>Discharge: %{y:.1f} cfs<extra></extra>"
        ))
        
        fig.update_layout(
            title=f"Daily Streamflow - Site {sf_data.site_id}",
            xaxis_title="Date",
            yaxis_title="Discharge (cfs)",
            height=500
        )
        
        return fig
    
    def _create_error_plot(self, error_message: str) -> go.Figure:
        """Create error plot when data cannot be processed."""
        
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {error_message}",
            x=0.5, y=0.5,
            xref='paper', yref='paper',
            showarrow=False,
            font=dict(size=16, color='red')
        )
        
        fig.update_layout(
            title="Error Loading Data",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=400
        )
        
        return fig
    
    def create_gauge_comparison_plot(self, gauge_data_dict: Dict[str, pd.DataFrame],
                                   comparison_type: str = 'annual') -> go.Figure:
        """
        Create comparison plot for multiple gauges.
        
        Parameters:
        -----------
        gauge_data_dict : dict
            Dictionary with site_id as key and streamflow data as value
        comparison_type : str
            Type of comparison ('annual', 'monthly', 'seasonal')
            
        Returns:
        --------
        go.Figure
            Comparison plot
        """
        
        fig = go.Figure()
        colors = px.colors.qualitative.Set1
        
        for i, (site_id, data) in enumerate(gauge_data_dict.items()):
            color = colors[i % len(colors)]
            
            if comparison_type == 'annual':
                # Calculate annual means
                data_copy = data.copy()
                if 'datetime' in data.columns:
                    data_copy = data_copy.set_index('datetime')
                
                # Get discharge column
                value_col = None
                for col in data.columns:
                    if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                        value_col = col
                        break
                
                if value_col is None:
                    continue
                
                annual_means = data_copy[value_col].resample('Y').mean()
                
                fig.add_trace(go.Scatter(
                    x=annual_means.index.year,
                    y=annual_means.values,
                    mode='lines+markers',
                    name=f"Site {site_id}",
                    line=dict(color=color, width=2),
                    marker=dict(size=6),
                    hovertemplate=f"<b>Site {site_id}</b><br>" +
                                "Year: %{x}<br>" +
                                "Mean Discharge: %{y:.1f} cfs<extra></extra>"
                ))
        
        fig.update_layout(
            title="Annual Mean Discharge Comparison",
            xaxis_title="Year",
            yaxis_title="Mean Discharge (cfs)",
            height=500,
            showlegend=True
        )
        
        return fig
    
    def create_flow_duration_curve(self, site_id: str, data: pd.DataFrame) -> go.Figure:
        """Create flow duration curve for a gauge."""
        
        # Make a copy to avoid modifying the original data
        data = data.copy()
        
        # Get discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        
        if value_col is None:
            return self._create_error_plot("No discharge data found for flow duration curve")
        
        # Calculate flow duration curve
        flows = data[value_col].dropna().sort_values(ascending=False)
        n = len(flows)
        exceedance_prob = np.arange(1, n + 1) / n * 100
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=exceedance_prob,
            y=flows.values,
            mode='lines',
            name='Flow Duration Curve',
            line=dict(color='blue', width=2),
            hovertemplate="Exceedance: %{x:.1f}%<br>Discharge: %{y:.1f} cfs<extra></extra>"
        ))
        
        # Add percentile markers
        percentiles = [10, 25, 50, 75, 90]
        for p in percentiles:
            idx = int(p / 100 * n)
            if idx < n:
                fig.add_vline(
                    x=p, 
                    line_dash="dash", 
                    line_color="red",
                    annotation_text=f"{p}th percentile"
                )
        
        fig.update_layout(
            title=f"Flow Duration Curve - Site {site_id}",
            xaxis_title="Exceedance Probability (%)",
            yaxis_title="Discharge (cfs)",
            yaxis_type="log",
            height=500,
            showlegend=True
        )
        
        return fig
    
    def _get_water_year(self, date) -> int:
        """Get water year for a given date."""
        try:
            # Handle different input types
            if isinstance(date, (int, float)):
                # If it's a number, probably not a valid date
                return 2024  # Default year
            
            # Ensure it's a pandas Timestamp
            if not isinstance(date, pd.Timestamp):
                date = pd.to_datetime(date)
            
            # Remove timezone info to avoid timezone mixing issues
            if date.tz is not None:
                date = date.tz_localize(None)
            
            if date.month >= WATER_YEAR_START:
                return date.year + 1
            else:
                return date.year
        except Exception as e:
            print(f"Error getting water year for date {date}: {e}")
            return 2024  # Default year
    
    def _get_day_of_water_year(self, date) -> int:
        """Get day of water year (1-365/366)."""
        try:
            # Handle different input types
            if isinstance(date, (int, float)):
                # If it's a number, probably not a valid date
                return 1  # Default day
            
            # Ensure it's a pandas Timestamp
            if not isinstance(date, pd.Timestamp):
                date = pd.to_datetime(date)
            
            # Remove timezone info to avoid timezone mixing issues
            if date.tz is not None:
                date = date.tz_localize(None)
            
            water_year = self._get_water_year(date)
            
            if date.month >= WATER_YEAR_START:
                wy_start = pd.Timestamp(year=date.year, month=WATER_YEAR_START, day=1)
            else:
                wy_start = pd.Timestamp(year=date.year - 1, month=WATER_YEAR_START, day=1)
            
            return (date - wy_start).days + 1
        except Exception as e:
            print(f"Error getting day of water year for date {date}: {e}")
            return 1  # Default day
    
    def get_data_summary_stats(self, data: pd.DataFrame) -> Dict:
        """Get summary statistics for streamflow data."""
        
        # Get discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        
        if value_col is None:
            return {"error": "No discharge data found"}
        
        flows = data[value_col].dropna()
        
        stats = {
            'count': len(flows),
            'mean': flows.mean(),
            'median': flows.median(),
            'min': flows.min(),
            'max': flows.max(),
            'std': flows.std(),
            'start_date': data.index.min().strftime('%Y-%m-%d') if hasattr(data.index, 'min') else 'Unknown',
            'end_date': data.index.max().strftime('%Y-%m-%d') if hasattr(data.index, 'max') else 'Unknown',
        }
        
        # Add percentiles
        percentiles = [10, 25, 50, 75, 90, 95, 99]
        for p in percentiles:
            stats[f'p{p}'] = flows.quantile(p / 100)
        
        return stats

    def _add_realtime_overlay(self, fig: go.Figure, realtime_data: pd.DataFrame, site_id: str) -> go.Figure:
        """Add real-time data overlay to existing plot."""
        try:
            # Find the discharge column in real-time data
            value_col = None
            for col in realtime_data.columns:
                if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                    value_col = col
                    break
            
            if value_col is None:
                print("No discharge column found in real-time data")
                return fig
            
            # Clean the real-time data
            rt_data_clean = realtime_data.dropna()
            if rt_data_clean.empty:
                print("Real-time data is empty after cleaning")
                return fig
            
            # Check if this is a water year plot by looking at the x-axis type
            # Water year plots use numeric x-axis (day of water year), while others use datetime
            x_axis_type = fig.layout.xaxis.type if fig.layout.xaxis.type else 'date'
            is_water_year_plot = (x_axis_type == 'linear' and 
                                fig.layout.xaxis.title.text == "Day of Water Year")
            
            if is_water_year_plot:
                # For water year plots, convert real-time data to day-of-water-year format
                print(f"Adding real-time overlay to water year plot")
                
                # Prepare real-time data using the same water year system
                rt_prepared = self.wy_handler.prepare_water_year_data(rt_data_clean, value_col)
                
                # Group by current water year (most recent data)
                current_wy = self.wy_handler.get_water_year(pd.Timestamp.now())
                current_year_rt = rt_prepared[rt_prepared['water_year'] == current_wy]
                
                if not current_year_rt.empty:
                    # Sort by day of water year for proper line plotting
                    current_year_rt = current_year_rt.sort_values('day_of_wy')
                    
                    # Add real-time data trace with day-of-water-year x-axis
                    # Create custom data with both date and time
                    customdata_array = np.column_stack([
                        current_year_rt['month_day'].values,
                        current_year_rt.index.strftime('%H:%M').values
                    ])
                    
                    fig.add_trace(
                        go.Scatter(
                            x=current_year_rt['day_of_wy'],
                            y=current_year_rt['value'],
                            mode='lines',
                            name=f'Real-time WY {current_wy} (15-min)',
                            line=dict(
                                color='red',
                                width=3,
                                dash='solid'
                            ),
                            opacity=0.9,
                            hovertemplate=(
                                '<b>Real-time WY' + f' {current_wy}</b><br>' +
                                'Day %{x:.1f}: %{customdata[0]} %{customdata[1]}<br>' +
                                'Discharge: %{y:.2f} cfs' +
                                '<extra></extra>'
                            ),
                            customdata=customdata_array
                        )
                    )
                    print(f"Added real-time overlay to water year plot: {len(current_year_rt)} points for WY {current_wy}")
                else:
                    print(f"No real-time data available for current water year {current_wy}")
            else:
                # For non-water-year plots, use original datetime-based approach
                print(f"Adding real-time overlay to timeseries plot")
                
                # Add real-time data trace with datetime x-axis
                fig.add_trace(
                    go.Scatter(
                        x=rt_data_clean.index,
                        y=rt_data_clean[value_col],
                        mode='lines',
                        name='Real-time (15-min)',
                        line=dict(
                            color='red',
                            width=2,
                            dash='solid'
                        ),
                        opacity=0.8,
                        hovertemplate=(
                            '<b>Real-time Data</b><br>' +
                            'Date: %{x}<br>' +
                            'Discharge: %{y:.2f} cfs<br>' +
                            '<extra></extra>'
                        )
                    )
                )
            
            # Update legend to show both data types
            fig.update_layout(
                annotations=[
                    dict(
                        text=f"<b>Daily historical data + Real-time high-resolution data</b><br>Site: {site_id}",
                        xref="paper", yref="paper",
                        x=0.5, y=1.02, 
                        showarrow=False,
                        xanchor="center",
                        font=dict(size=12)
                    )
                ]
            )
            
            print(f"Added real-time overlay with {len(rt_data_clean)} points")
            return fig
            
        except Exception as e:
            print(f"Error adding real-time overlay: {e}")
            return fig


# Convenience function for creating visualization manager
def get_visualization_manager() -> VisualizationManager:
    """Get initialized visualization manager instance."""
    return VisualizationManager()
