"""
Water Year DateTime Handler for USGS Streamflow Dashboard

A specialized library to handle water year date formatting and plotting
that avoids Plotly's automatic datetime interpretation issues.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any
import plotly.graph_objects as go
from calendar import month_abbr


class WaterYearDateTime:
    """
    Handles water year datetime operations for clean plotting.
    
    Solves the common issue where Plotly interprets day-of-water-year
    as 1970-01-01 + days, causing plotting problems when stacking
    multiple years on the same axis.
    """
    
    def __init__(self, water_year_start_month: int = 10):
        """
        Initialize water year handler.
        
        Parameters:
        -----------
        water_year_start_month : int
            Month when water year starts (10 = October)
        """
        self.wy_start_month = water_year_start_month
        
    def get_water_year(self, date: pd.Timestamp) -> int:
        """Get water year for a given date."""
        if date.month >= self.wy_start_month:
            return date.year + 1
        else:
            return date.year
    
    def get_day_of_water_year(self, date: pd.Timestamp) -> int:
        """Get day of water year (1-365/366) for a given date."""
        water_year = self.get_water_year(date)
        
        # Water year start date
        if date.month >= self.wy_start_month:
            wy_start = pd.Timestamp(date.year, self.wy_start_month, 1)
        else:
            wy_start = pd.Timestamp(date.year - 1, self.wy_start_month, 1)
        
        # Calculate day difference
        day_of_wy = (date - wy_start).days + 1
        return day_of_wy
    
    def create_water_year_x_axis(self, max_days: int = 366) -> Tuple[List[int], List[str], List[str]]:
        """
        Create clean x-axis for water year plots.
        
        Returns:
        --------
        tick_values : List[int]
            Numeric values for x-axis (1, 32, 60, etc.)
        tick_labels : List[str] 
            Short labels ('Oct 1', 'Nov 1', etc.)
        tick_labels_long : List[str]
            Long labels ('October 1', 'November 1', etc.)
        """
        # Create month boundaries in water year
        months_in_order = list(range(self.wy_start_month, 13)) + list(range(1, self.wy_start_month))
        
        tick_values = []
        tick_labels = []
        tick_labels_long = []
        
        current_day = 1
        
        for month in months_in_order:
            # Days in this month (approximate - we'll use 30/31 day months)
            if month in [1, 3, 5, 7, 8, 10, 12]:
                days_in_month = 31
            elif month in [4, 6, 9, 11]:
                days_in_month = 30
            else:  # February
                days_in_month = 29  # Use 29 for leap year compatibility
            
            if current_day <= max_days:
                tick_values.append(current_day)
                tick_labels.append(f"{month_abbr[month]} 1")
                tick_labels_long.append(f"{month_abbr[month]} 1")
            
            current_day += days_in_month
            
            if current_day > max_days:
                break
        
        return tick_values, tick_labels, tick_labels_long
    
    def prepare_water_year_data(self, df: pd.DataFrame, value_col: str) -> pd.DataFrame:
        """
        Prepare data for water year plotting with clean numeric x-axis.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with DatetimeIndex and value column
        value_col : str
            Name of the value column to plot
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with water_year, day_of_wy, and value columns
        """
        # Make a copy to avoid modifying original
        data = df.copy()
        
        # Ensure we have a datetime index
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have DatetimeIndex")
        
        # Remove timezone to avoid issues
        if data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        
        # Calculate water year components
        data['water_year'] = data.index.map(self.get_water_year)
        data['day_of_wy'] = data.index.map(self.get_day_of_water_year)
        data['month_day'] = data.index.strftime('%b %d')
        
        # Keep only the value column and our calculated columns
        result_df = pd.DataFrame({
            'water_year': data['water_year'],
            'day_of_wy': data['day_of_wy'],
            'month_day': data['month_day'],
            'value': data[value_col],
            'date': data.index
        })
        
        return result_df
    
    def get_current_water_year_day(self) -> int:
        """Get the current day of the water year."""
        today = pd.Timestamp.now()
        return self.get_day_of_water_year(today)
    
    def get_default_zoom_range(self, days_buffer: int = 30) -> Tuple[int, int]:
        """
        Get default zoom range for water year plot centered on current day ±30 days.
        
        Parameters:
        -----------
        days_buffer : int
            Number of days before and after current day to show (default 30)
            
        Returns:
        --------
        Tuple[int, int]
            (start_day, end_day) for zoom range, properly handling water year boundaries
        """
        current_day = self.get_current_water_year_day()
        
        # Calculate raw zoom range
        zoom_start = current_day - days_buffer
        zoom_end = current_day + days_buffer
        
        # Handle water year boundaries (1-366)
        # If we go below day 1, wrap to end of previous water year
        if zoom_start < 1:
            zoom_start = max(1, zoom_start)  # Don't go below 1
        
        # If we go beyond day 366, wrap to beginning of next water year  
        if zoom_end > 366:
            zoom_end = min(366, zoom_end)  # Don't go beyond 366
        
        # Ensure minimum zoom range
        if zoom_end - zoom_start < 20:  # Minimum 20 days visible
            mid_point = (zoom_start + zoom_end) // 2
            zoom_start = max(1, mid_point - 10)
            zoom_end = min(366, mid_point + 10)
        
        return zoom_start, zoom_end

    def calculate_statistics(self, plot_data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Calculate mean and median for each day of water year across all years."""
        # Group by day of water year and calculate statistics
        daily_stats = plot_data.groupby('day_of_wy')['value'].agg(['mean', 'median']).reset_index()
        
        return {
            'mean': daily_stats[['day_of_wy', 'mean']].rename(columns={'mean': 'value'}),
            'median': daily_stats[['day_of_wy', 'median']].rename(columns={'median': 'value'})
        }

    def create_water_year_plot(self, df: pd.DataFrame, value_col: str, 
                             highlight_years: List[int] = None,
                             title: str = "Water Year Plot",
                             show_current_year: bool = True,
                             show_statistics: bool = True,
                             show_current_day: bool = True,
                             show_percentiles: bool = True,
                             use_default_zoom: bool = True) -> go.Figure:
        """
        Create a clean water year plot with proper numeric x-axis.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with DatetimeIndex
        value_col : str
            Column to plot
        highlight_years : List[int]
            Years to highlight with colors (if None, will default to current year)
        title : str
            Plot title
        show_current_year : bool
            Whether to default to showing current water year
        show_statistics : bool
            Whether to show mean and median lines
        show_current_day : bool
            Whether to show current day marker
        show_percentiles : bool
            Whether to show percentile bands (25th-75th, 10th-90th)
        use_default_zoom : bool
            Whether to use default zoom range (±30 days from current day)
            
        Returns:
        --------
        go.Figure
            Plotly figure with clean water year plot
        """
        # Prepare data
        plot_data = self.prepare_water_year_data(df, value_col)
        
        # Create figure
        fig = go.Figure()
        
        # Add percentile bands first (so they appear behind individual years)
        if show_percentiles and len(plot_data) > 100:  # Need sufficient data for meaningful percentiles
            # Calculate daily percentiles
            daily_percentiles = plot_data.groupby('day_of_wy')['value'].agg([
                lambda x: x.quantile(0.10),  # 10th percentile
                lambda x: x.quantile(0.25),  # 25th percentile
                lambda x: x.quantile(0.75),  # 75th percentile
                lambda x: x.quantile(0.90),  # 90th percentile
            ])
            daily_percentiles.columns = ['p10', 'p25', 'p75', 'p90']
            daily_percentiles = daily_percentiles.reset_index()
            
            # 10th-90th percentile band (lighter blue)
            fig.add_trace(go.Scatter(
                x=daily_percentiles['day_of_wy'],
                y=daily_percentiles['p90'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),  # Transparent line
                showlegend=False,
                name='90th percentile'
            ))
            
            fig.add_trace(go.Scatter(
                x=daily_percentiles['day_of_wy'],
                y=daily_percentiles['p10'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),  # Transparent line
                fill='tonexty',
                fillcolor='rgba(173, 216, 230, 0.3)',  # Light blue fill
                showlegend=True,
                name='10th-90th Percentile Range',
                hovertemplate=(
                    "Day of WY: %{x}<br>" +
                    "10th-90th Percentile Range<br>" +
                    "<extra></extra>"
                )
            ))
            
            # 25th-75th percentile band (darker blue, on top)
            fig.add_trace(go.Scatter(
                x=daily_percentiles['day_of_wy'],
                y=daily_percentiles['p75'],
                mode='lines',
                line=dict(color='rgba(100, 149, 237, 0)'),  # Transparent line
                showlegend=False,
                name='75th percentile'
            ))
            
            fig.add_trace(go.Scatter(
                x=daily_percentiles['day_of_wy'],
                y=daily_percentiles['p25'],
                mode='lines',
                line=dict(color='rgba(100, 149, 237, 0)'),  # Transparent line
                fill='tonexty',
                fillcolor='rgba(100, 149, 237, 0.4)',  # Darker blue fill
                showlegend=True,
                name='25th-75th Percentile Range',
                hovertemplate=(
                    "Day of WY: %{x}<br>" +
                    "25th-75th Percentile Range<br>" +
                    "<extra></extra>"
                )
            ))
        
        # Color palette for highlighted years
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                 '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        
        # Get unique years
        years = sorted(plot_data['water_year'].unique())
        
        # Determine which years to highlight
        if highlight_years is None and show_current_year:
            current_wy = self.get_water_year(pd.Timestamp.now())
            highlight_years = [current_wy] if current_wy in years else []
        elif highlight_years is None:
            highlight_years = []
        
        # Separate highlighted and non-highlighted years
        highlighted_years_list = [year for year in years if year in highlight_years]
        other_years_list = [year for year in years if year not in highlight_years]
        
        # First, add ALL background (non-highlighted) years at the bottom layer
        for year in other_years_list:
            year_data = plot_data[plot_data['water_year'] == year].copy()
            year_data = year_data.sort_values('day_of_wy')
            
            fig.add_trace(go.Scatter(
                x=year_data['day_of_wy'],
                y=year_data['value'],
                mode='lines',
                name=f"WY {year}",
                line=dict(color='#cccccc', width=1),
                opacity=0.5,
                visible=True,
                showlegend=False,  # Will be controlled by group toggle
                legendgroup='historical',
                hovertemplate=(
                    f"Water Year {year}<br>" +
                    "Date: %{customdata}<br>" +
                    "Discharge: %{y:.1f} cfs<br>" +
                    "<extra></extra>"
                ),
                customdata=year_data['month_day']
            ))
        
        # Add the group toggle for historical years (if any exist)
        if other_years_list:
            fig.add_trace(go.Scatter(
                x=[],
                y=[],
                mode='lines',
                name=f'All Historical Years ({len(other_years_list)})',
                line=dict(color='#cccccc', width=1),
                visible='legendonly',  # Start hidden, user can toggle
                showlegend=True,
                legendgroup='historical',
                hovertemplate="<extra></extra>"
            ))
        
        # Add statistics on top of background years  
        if show_statistics and len(plot_data) > 0:
            stats = self.calculate_statistics(plot_data)
            
            # Add mean line (dotted thin black) - OFF by default
            fig.add_trace(go.Scatter(
                x=stats['mean']['day_of_wy'],
                y=stats['mean']['value'],
                mode='lines',
                name='Mean',
                line=dict(color='black', width=2, dash='dot'),
                visible='legendonly',  # Off by default
                showlegend=True,
                hovertemplate=(
                    "Mean<br>" +
                    "Day of WY: %{x}<br>" +
                    "Mean Discharge: %{y:.1f} cfs<br>" +
                    "<extra></extra>"
                )
            ))
            
            # Add median line (dashed thin black) - ON by default
            fig.add_trace(go.Scatter(
                x=stats['median']['day_of_wy'],
                y=stats['median']['value'],
                mode='lines',
                name='Median',
                line=dict(color='black', width=2, dash='dash'),
                visible=True,  # On by default
                showlegend=True,
                hovertemplate=(
                    "Median<br>" +
                    "Day of WY: %{x}<br>" +
                    "Median Discharge: %{y:.1f} cfs<br>" +
                    "<extra></extra>"
                )
            ))
        
        # Finally, add highlighted years ON TOP of everything else
        color_idx = 0
        for year in highlighted_years_list:
            year_data = plot_data[plot_data['water_year'] == year].copy()
            year_data = year_data.sort_values('day_of_wy')
            
            # Highlighted year - use color and make prominent, on top layer
            color = colors[color_idx % len(colors)]
            line_width = 3
            opacity = 0.9
            name = f"Water Year {year}"
            visible = True
            color_idx += 1
            
            fig.add_trace(go.Scatter(
                x=year_data['day_of_wy'],
                y=year_data['value'],
                mode='lines',
                name=name,
                line=dict(color=color, width=line_width),
                opacity=opacity,
                visible=visible,
                showlegend=True,
                hovertemplate=(
                    f"Water Year {year}<br>" +
                    "Date: %{customdata}<br>" +
                    "Discharge: %{y:.1f} cfs<br>" +
                    "<extra></extra>"
                ),
                customdata=year_data['month_day']
            ))
        
        # Add current day marker if requested (on top of everything)
        if show_current_day:
            current_day = self.get_current_water_year_day()
            if 1 <= current_day <= 366:
                # Get y-axis range for the vertical line
                y_min = plot_data['value'].min()
                y_max = plot_data['value'].max()
                y_range = y_max - y_min
                y_bottom = y_min - 0.1 * y_range
                y_top = y_max + 0.1 * y_range
                
                fig.add_trace(go.Scatter(
                    x=[current_day, current_day],
                    y=[y_bottom, y_top],
                    mode='lines',
                    name='Current Day',
                    line=dict(color='red', width=2, dash='dash'),
                    visible=True,
                    showlegend=True,
                    hovertemplate=(
                        "Current Day<br>" +
                        f"Day of WY: {current_day}<br>" +
                        "<extra></extra>"
                    )
                ))
        
        # Create clean x-axis
        tick_values, tick_labels, _ = self.create_water_year_x_axis()
        
        # Determine x-axis range
        if use_default_zoom:
            zoom_start, zoom_end = self.get_default_zoom_range(days_buffer=30)
            x_range = [zoom_start, zoom_end]
        else:
            x_range = [1, 366]
        
        # Update layout with NUMERIC x-axis
        fig.update_layout(
            title=title,
            xaxis=dict(
                title="Day of Water Year",
                type="linear",  # CRITICAL: Force numeric axis
                tickmode="array",
                tickvals=tick_values,
                ticktext=tick_labels,
                range=x_range,  # Use calculated zoom range
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title="Discharge (cfs)",
                showgrid=True,
                gridcolor='lightgray'
            ),
            hovermode='x unified',
            showlegend=True,
            height=500,
            template='plotly_white',
            # Ensure statistics lines appear on top
            legend=dict(
                traceorder="normal"
            )
        )
        
        return fig


# Convenience function to get the handler
def get_water_year_handler():
    """Get a water year datetime handler instance."""
    return WaterYearDateTime()


# Example usage and testing
if __name__ == "__main__":
    # Test the water year handler
    handler = WaterYearDateTime()
    
    # Test date conversions
    test_date = pd.Timestamp('2024-01-15')
    print(f"Date: {test_date}")
    print(f"Water Year: {handler.get_water_year(test_date)}")
    print(f"Day of WY: {handler.get_day_of_water_year(test_date)}")
    
    # Test x-axis creation
    tick_vals, tick_labels, _ = handler.create_water_year_x_axis()
    print(f"X-axis ticks: {list(zip(tick_vals[:6], tick_labels[:6]))}")