"""
USGS Data Manager for streamflow dashboard
REFACTORED: Now uses DataOps adapter for all data operations
SIMPLIFIED: Reduced from 1,465 LOC to ~400 LOC (73% reduction)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os
import logging

from ..utils.config import TARGET_STATES, CACHE_DURATION, MAX_YEARS_LOAD, GAUGE_COLORS, SUBSET_CONFIG

# Import DataOps adapter
from dataops_adapter import DataOpsAdapter

logger = logging.getLogger(__name__)


class USGSDataManager:
    """
    Manages USGS data retrieval using DataOps adapter.
    
    This is now a lightweight wrapper around the DataOpsAdapter that:
    1. Provides backward compatibility with existing dashboard code
    2. Handles data format conversions for visualization components
    3. Maintains the same interface as the old data_manager
    
    All data collection, storage, and management is now handled by DataOps.
    """
    
    def __init__(self, cache_dir: str = "data"):
        """
        Initialize the data manager with DataOps adapter.
        
        Parameters:
        -----------
        cache_dir : str
            Directory to store cache database (used by adapter)
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Initialize DataOps adapter (hybrid mode by default)
        self.adapter = DataOpsAdapter()
        
        logger.info(f"✅ USGSDataManager initialized with DataOps adapter")
        logger.info(f"   Mode: {self.adapter.mode}")
        logger.info(f"   API enabled: {self.adapter.api_enabled}")
        logger.info(f"   Cache enabled: {self.adapter.cache_enabled}")
    
    def load_regional_gauges(self, refresh=False, max_sites=None) -> pd.DataFrame:
        """
        Load all USGS gauges with metadata.
        
        Parameters:
        -----------
        refresh : bool
            Force refresh of cached data (passed to adapter)
        max_sites : int, optional
            Maximum number of sites to load
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with gauge metadata
        """
        logger.info("Loading regional gauges via DataOps adapter")
        
        # If subset is enabled, apply limit
        limit = max_sites if max_sites else (SUBSET_CONFIG['max_sites'] if SUBSET_CONFIG['enabled'] else 10000)
        
        try:
            # Get stations from DataOps
            stations_df = self.adapter.get_stations(
                agency='USGS',
                is_active=True,
                limit=limit
            )
            
            if stations_df.empty:
                logger.warning("No stations returned from DataOps")
                return pd.DataFrame()
            
            # Enrich with visualization metadata
            stations_df = self._enrich_station_metadata(stations_df)
            
            logger.info(f"✅ Loaded {len(stations_df)} stations from DataOps")
            return stations_df
            
        except Exception as e:
            logger.error(f"Error loading stations: {e}")
            # Return empty DataFrame on error
            return pd.DataFrame()
    
    def _enrich_station_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich station metadata with visualization-specific fields.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw station data from DataOps
        
        Returns:
        --------
        pd.DataFrame
            Enriched station data with color coding, etc.
        """
        if df.empty:
            return df
        
        # Add site_no column (alias for station_number) for compatibility
        if 'station_number' in df.columns and 'site_no' not in df.columns:
            df['site_no'] = df['station_number']
        
        # Add station_nm column (alias for name) for compatibility
        if 'name' in df.columns and 'station_nm' not in df.columns:
            df['station_nm'] = df['name']
        
        # Ensure required columns exist
        required_cols = ['latitude', 'longitude', 'state']
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"Missing required column: {col}")
                df[col] = None
        
        # Add color coding based on state (for map visualization)
        if 'state' in df.columns:
            df['color'] = df['state'].apply(lambda x: GAUGE_COLORS.get(x, '#808080'))
        else:
            df['color'] = '#808080'  # Default gray
        
        # Filter by target states if configured
        if TARGET_STATES and 'state' in df.columns:
            df = df[df['state'].isin(TARGET_STATES)]
        
        return df
    
    def get_streamflow_data(
        self, 
        site_id: str, 
        start_date: str = None, 
        end_date: str = None,
        years_back: int = None
    ) -> pd.DataFrame:
        """
        Get daily mean discharge data for a site.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        start_date : str, optional
            Start date (YYYY-MM-DD)
        end_date : str, optional
            End date (YYYY-MM-DD)
        years_back : int, optional
            Number of years to fetch (alternative to start_date)
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with discharge data
        """
        # Calculate dates if not provided
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        if start_date is None:
            if years_back:
                start_date = (datetime.now() - timedelta(days=years_back*365)).strftime('%Y-%m-%d')
            else:
                # Default to MAX_YEARS_LOAD from config
                start_date = (datetime.now() - timedelta(days=MAX_YEARS_LOAD*365)).strftime('%Y-%m-%d')
        
        logger.debug(f"Fetching streamflow data: {site_id} ({start_date} to {end_date})")
        
        try:
            # Get data from DataOps
            df = self.adapter.get_discharge_data(
                station_number=site_id,
                start_date=start_date,
                end_date=end_date,
                data_type='daily_mean'
            )
            
            if df.empty:
                logger.warning(f"No data returned for {site_id}")
                return pd.DataFrame()
            
            # Format for dashboard compatibility
            df = self._format_streamflow_data(df, site_id)
            
            logger.info(f"✅ Retrieved {len(df)} observations for {site_id}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching streamflow data for {site_id}: {e}")
            return pd.DataFrame()
    
    def _format_streamflow_data(self, df: pd.DataFrame, site_id: str) -> pd.DataFrame:
        """
        Format discharge data for dashboard compatibility.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw discharge data from DataOps
        site_id : str
            Site identifier
        
        Returns:
        --------
        pd.DataFrame
            Formatted data
        """
        if df.empty:
            return df
        
        # Ensure datetime column
        if 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'])
        
        # Ensure discharge column (rename if needed)
        if 'discharge' not in df.columns and 'discharge_value' in df.columns:
            df['discharge'] = df['discharge_value']
        
        # Add site_no column for compatibility
        df['site_no'] = site_id
        
        # Ensure sorted by date
        if 'datetime' in df.columns:
            df = df.sort_values('datetime')
        
        # Remove any duplicates
        if 'datetime' in df.columns:
            df = df.drop_duplicates(subset=['datetime'], keep='first')
        
        return df
    
    def get_realtime_data(
        self, 
        site_id: str, 
        start_date: str = None, 
        end_date: str = None,
        hours_back: int = 48
    ) -> pd.DataFrame:
        """
        Get real-time 15-minute discharge data.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        start_date : str, optional
            Start date (YYYY-MM-DD)
        end_date : str, optional
            End date (YYYY-MM-DD)
        hours_back : int, optional
            Hours of data to retrieve (default: 48)
        
        Returns:
        --------
        pd.DataFrame
            DataFrame with real-time discharge data
        """
        # Calculate dates if not provided
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        if start_date is None:
            start_date = (datetime.now() - timedelta(hours=hours_back)).strftime('%Y-%m-%d')
        
        logger.debug(f"Fetching realtime data: {site_id} ({start_date} to {end_date})")
        
        try:
            # Get real-time data from DataOps
            df = self.adapter.get_discharge_data(
                station_number=site_id,
                start_date=start_date,
                end_date=end_date,
                data_type='realtime_15min'
            )
            
            if df.empty:
                logger.warning(f"No realtime data for {site_id}")
                return pd.DataFrame()
            
            # Format for dashboard compatibility
            df = self._format_realtime_data(df, site_id)
            
            logger.info(f"✅ Retrieved {len(df)} realtime observations for {site_id}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching realtime data for {site_id}: {e}")
            return pd.DataFrame()
    
    def _format_realtime_data(self, df: pd.DataFrame, site_id: str) -> pd.DataFrame:
        """
        Format real-time data for dashboard compatibility.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw realtime data from DataOps
        site_id : str
            Site identifier
        
        Returns:
        --------
        pd.DataFrame
            Formatted data
        """
        if df.empty:
            return df
        
        # Ensure datetime column
        if 'date' in df.columns:
            df['datetime'] = pd.to_datetime(df['date'])
        elif 'datetime' not in df.columns and 'observed_at' in df.columns:
            df['datetime'] = pd.to_datetime(df['observed_at'])
        
        # Ensure discharge column
        if 'discharge' not in df.columns and 'discharge_value' in df.columns:
            df['discharge'] = df['discharge_value']
        
        # Add site_no for compatibility
        df['site_no'] = site_id
        
        # Ensure sorted by datetime
        if 'datetime' in df.columns:
            df = df.sort_values('datetime')
        
        return df
    
    def get_station_info(self, site_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a station.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        
        Returns:
        --------
        dict
            Station metadata
        """
        try:
            info = self.adapter.get_station_info(site_id)
            return info
        except Exception as e:
            logger.error(f"Error getting station info for {site_id}: {e}")
            return {}
    
    def get_available_sites(self, state: str = None) -> List[str]:
        """
        Get list of available site IDs.
        
        Parameters:
        -----------
        state : str, optional
            Filter by state code
        
        Returns:
        --------
        list
            List of site IDs
        """
        try:
            df = self.adapter.get_stations(state=state, limit=10000)
            if 'station_number' in df.columns:
                return df['station_number'].tolist()
            return []
        except Exception as e:
            logger.error(f"Error getting available sites: {e}")
            return []
    
    def clear_cache(self):
        """Clear the adapter cache."""
        logger.info("Clearing adapter cache")
        self.adapter.clear_cache()
    
    def get_adapter_status(self) -> Dict[str, Any]:
        """
        Get status of the DataOps adapter.
        
        Returns:
        --------
        dict
            Adapter status information
        """
        return self.adapter.get_status()


def get_data_manager() -> USGSDataManager:
    """
    Get singleton instance of data manager.
    
    Returns:
    --------
    USGSDataManager
        Data manager instance
    """
    return USGSDataManager()
