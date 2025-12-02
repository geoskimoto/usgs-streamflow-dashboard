"""
Water Year Calculation Utilities

Pure utility functions for water year calculations.
Single source of truth - all other modules should import from here.

Water Year Definition:
- Starts October 1 (month 10) by default
- Water year 2024 = Oct 1, 2023 - Sep 30, 2024
- Day 1 = October 1, Day 366 = September 30 (leap year)
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Tuple


def get_water_year(date: pd.Timestamp, start_month: int = 10) -> int:
    """
    Get water year for a given date.
    
    Parameters:
    -----------
    date : pd.Timestamp
        Date to get water year for
    start_month : int, default 10
        Month when water year starts (10 = October)
        
    Returns:
    --------
    int
        Water year number
        
    Examples:
    ---------
    >>> get_water_year(pd.Timestamp('2023-10-15'), 10)
    2024  # Oct 15, 2023 is in water year 2024
    
    >>> get_water_year(pd.Timestamp('2024-09-15'), 10)
    2024  # Sep 15, 2024 is in water year 2024
    """
    if date.month >= start_month:
        return date.year + 1
    else:
        return date.year


def get_day_of_water_year(date: pd.Timestamp, start_month: int = 10) -> int:
    """
    Get day of water year (1-365/366) for a given date.
    
    Parameters:
    -----------
    date : pd.Timestamp
        Date to get day of water year for
    start_month : int, default 10
        Month when water year starts (10 = October)
        
    Returns:
    --------
    int
        Day of water year (1-366)
        
    Examples:
    ---------
    >>> get_day_of_water_year(pd.Timestamp('2023-10-01'), 10)
    1  # First day of water year
    
    >>> get_day_of_water_year(pd.Timestamp('2024-09-30'), 10)
    366  # Last day of leap water year
    """
    water_year = get_water_year(date, start_month)
    
    # Water year start date
    if date.month >= start_month:
        wy_start = pd.Timestamp(date.year, start_month, 1)
    else:
        wy_start = pd.Timestamp(date.year - 1, start_month, 1)
    
    # Calculate day difference
    day_of_wy = (date - wy_start).days + 1
    return day_of_wy


def get_water_year_date_range(water_year: int, start_month: int = 10) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    Get start and end dates for a water year.
    
    Parameters:
    -----------
    water_year : int
        Water year number
    start_month : int, default 10
        Month when water year starts (10 = October)
        
    Returns:
    --------
    tuple
        (start_date, end_date) as pd.Timestamps
        
    Examples:
    ---------
    >>> get_water_year_date_range(2024, 10)
    (Timestamp('2023-10-01'), Timestamp('2024-09-30'))
    """
    start_date = pd.Timestamp(water_year - 1, start_month, 1)
    
    # End date is last day of month before start_month
    end_month = start_month - 1 if start_month > 1 else 12
    end_year = water_year if start_month > 1 else water_year - 1
    
    # Get last day of end month
    if end_month == 12:
        end_date = pd.Timestamp(end_year, 12, 31)
    else:
        # Get first day of next month, then subtract 1 day
        next_month_start = pd.Timestamp(end_year, end_month + 1, 1)
        end_date = next_month_start - timedelta(days=1)
    
    return start_date, end_date


def is_leap_year(year: int) -> bool:
    """
    Check if a year is a leap year.
    
    Parameters:
    -----------
    year : int
        Year to check
        
    Returns:
    --------
    bool
        True if leap year, False otherwise
        
    Examples:
    ---------
    >>> is_leap_year(2024)
    True
    
    >>> is_leap_year(2023)
    False
    """
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def get_water_year_length(water_year: int, start_month: int = 10) -> int:
    """
    Get length of water year in days (365 or 366).
    
    Parameters:
    -----------
    water_year : int
        Water year number
    start_month : int, default 10
        Month when water year starts (10 = October)
        
    Returns:
    --------
    int
        365 or 366 days
        
    Notes:
    ------
    For Oct-Sep water years:
    - Water year 2024 spans Oct 2023 - Sep 2024
    - It's a leap year if 2024 is a leap year (includes Feb 29, 2024)
    """
    # For standard Oct-Sep water year, check the calendar year portion
    if start_month == 10:
        # WY 2024 includes Feb 2024, so check year 'water_year'
        return 366 if is_leap_year(water_year) else 365
    else:
        # For other start months, check which year contains February
        start_date, end_date = get_water_year_date_range(water_year, start_month)
        return (end_date - start_date).days + 1


def validate_water_year_data(df: pd.DataFrame, date_column: str = 'datetime',
                             start_month: int = 10) -> dict:
    """
    Validate water year data coverage.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with datetime column
    date_column : str
        Name of datetime column
    start_month : int
        Water year start month
        
    Returns:
    --------
    dict
        Validation results including coverage statistics
    """
    if df.empty or date_column not in df.columns:
        return {'valid': False, 'error': 'Invalid dataframe or missing date column'}
    
    dates = pd.to_datetime(df[date_column])
    water_years = dates.apply(lambda d: get_water_year(d, start_month))
    
    results = {
        'valid': True,
        'water_years': sorted(water_years.unique().tolist()),
        'start_date': dates.min(),
        'end_date': dates.max(),
        'total_days': len(df),
        'gaps': None  # Could add gap detection here
    }
    
    return results


# Convenience function for backward compatibility
def calculate_water_year(date, start_month=10):
    """Alias for get_water_year() for backward compatibility."""
    return get_water_year(pd.Timestamp(date), start_month)


def calculate_day_of_water_year(date, start_month=10):
    """Alias for get_day_of_water_year() for backward compatibility."""
    return get_day_of_water_year(pd.Timestamp(date), start_month)
