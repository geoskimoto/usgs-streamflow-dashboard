"""
Water Year DateTime Handler for USGS Streamflow Dashboard

A utility library to handle water year date calculations and data preparation.
Plotting functionality has been moved to viz_manager.py for better separation of concerns.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any
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
        """Get the current day of the water year (integer)."""
        today = pd.Timestamp.now()
        return self.get_day_of_water_year(today)
    
    def get_current_water_year_day_precise(self) -> float:
        """Get the current day of the water year with fractional day (includes time)."""
        now = pd.Timestamp.now()
        water_year = self.get_water_year(now)
        
        # Water year start date
        if now.month >= self.wy_start_month:
            wy_start = pd.Timestamp(now.year, self.wy_start_month, 1)
        else:
            wy_start = pd.Timestamp(now.year - 1, self.wy_start_month, 1)
        
        # Calculate day difference including fractional day (time component)
        time_delta = now - wy_start
        day_of_wy_precise = time_delta.total_seconds() / (24 * 3600) + 1
        return day_of_wy_precise
    
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

    # NOTE: The create_water_year_plot() method has been removed as part of architectural refactoring.
    # All plotting functionality is now consolidated in viz_manager.py (_create_enhanced_water_year_plot)
    # This class now focuses solely on utility functions for water year calculations and data preparation.


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