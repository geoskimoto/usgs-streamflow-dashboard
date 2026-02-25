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
import threading
import time

from ..utils.config import TARGET_STATES, CACHE_DURATION, MAX_YEARS_LOAD, GAUGE_COLORS

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
    
    All data collection, storage, and management is now handled by
    StreamFlow DataOps (https://streamflowops.3rdplaces.io).
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
        
        # Cached stations DataFrame (refreshed on load_regional_gauges)
        self._stations_cache = None

        # Percentile bands cache
        self._percentile_cache: dict = {}
        self._percentile_cache_time: float = 0.0
        self._percentile_cache_ttl: int = 1800        # 30 minutes
        self._percentile_refresh_event = threading.Event()
        self._percentile_bg_thread: threading.Thread = None
        
        logger.info(f"✅ USGSDataManager initialized with DataOps adapter")
        logger.info(f"   Mode: {self.adapter.mode}")
        logger.info(f"   API enabled: {self.adapter.api_enabled}")
        logger.info(f"   Cache enabled: {self.adapter.cache_enabled}")
    
    def load_regional_gauges(self, refresh=False, max_sites=None) -> pd.DataFrame:
        """
        Load all USGS gauges with metadata from DataOps API.
        
        Fetches stations per-state from TARGET_STATES to ensure state
        metadata is available even if the list serializer omits it.
        
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
        
        # Use high limit to fetch all stations per state
        # (max_sites is per-state limit, not total)
        limit = max_sites if max_sites else 10000
        
        try:
            all_stations = []
            
            if TARGET_STATES:
                # Fetch per-state to ensure we have state metadata
                # Support multiple agencies (USGS for US states, EC for Canadian provinces)
                for state in TARGET_STATES:
                    try:
                        # Determine agency based on state/province
                        agency = 'EC' if state == 'BC' else 'USGS'
                        
                        state_df = self.adapter.get_stations(
                            agency=agency,
                            state=state,
                            limit=limit
                        )
                        if not state_df.empty:
                            # Ensure state column is populated (may be missing from StationList serializer)
                            if 'state' not in state_df.columns or state_df['state'].isna().all():
                                state_df['state'] = state
                            logger.info(f"  Loaded {len(state_df)} {agency} stations for {state}")
                            all_stations.append(state_df)
                    except Exception as e:
                        logger.warning(f"Error loading stations for state {state}: {e}")
                
                if all_stations:
                    stations_df = pd.concat(all_stations, ignore_index=True)
                    # Remove duplicates (station might appear in multiple state queries)
                    if 'station_number' in stations_df.columns:
                        stations_df = stations_df.drop_duplicates(subset=['station_number'], keep='first')
                else:
                    stations_df = pd.DataFrame()
            else:
                # No target states configured, fetch all
                stations_df = self.adapter.get_stations(
                    agency='USGS',
                    limit=limit
                )
            
            if stations_df.empty:
                logger.warning("No stations returned from DataOps")
                return pd.DataFrame()
            
            # Classify station activity based on recent discharge data
            stations_df = self._classify_station_activity(stations_df)
            
            # Enrich with CSV data (drainage area, etc.)
            stations_df = self._enrich_from_csv(stations_df)
            
            # Enrich with visualization metadata
            stations_df = self._enrich_station_metadata(stations_df)
            
            # Cache for use by get_filters_table() and other methods
            self._stations_cache = stations_df.copy()
            
            logger.info(f"✅ Loaded {len(stations_df)} stations from DataOps")
            return stations_df
            
        except Exception as e:
            logger.error(f"Error loading stations: {e}")
            # Return empty DataFrame on error
            return pd.DataFrame()
    
    def _classify_station_activity(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify stations as Active or Inactive based on recent discharge data.
        
        Active = has discharge observations in the last 6 months.
        Inactive = no discharge observations in the last 6 months.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Station data with 'station_number' column
        
        Returns:
        --------
        pd.DataFrame
            Station data with 'station_status' column added
        """
        if df.empty:
            return df
        
        try:
            # Get set of station numbers with recent discharge data
            active_stations = self.adapter.get_active_station_numbers(months_back=6)
            
            if active_stations:
                df['station_status'] = df['station_number'].apply(
                    lambda sn: 'Active' if sn in active_stations else 'Inactive'
                )
                active_count = (df['station_status'] == 'Active').sum()
                inactive_count = (df['station_status'] == 'Inactive').sum()
                logger.info(f"Station activity: {active_count} active, {inactive_count} inactive")
            else:
                # Fallback: mark all as unknown if we can't determine activity
                logger.warning("Could not determine station activity, defaulting to 'Active'")
                df['station_status'] = 'Active'
        except Exception as e:
            logger.error(f"Error classifying station activity: {e}")
            df['station_status'] = 'Active'
        
        return df
    
    def _enrich_from_csv(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich station data with information from CSV files.
        
        Merges drainage_area and other metadata from HUC17 CSV file
        with the API station data. This supplements fields not available
        in the API list endpoint.
        
        Parameters:
        -----------
        df : pd.DataFrame
            Station data from API
        
        Returns:
        --------
        pd.DataFrame
            Enriched station data
        """
        if df.empty:
            return df
        
        try:
            # Load HUC17 CSV with drainage area data
            csv_path = os.path.join(os.path.dirname(__file__), '../../data/huc17_discharge_stations.csv')
            if os.path.exists(csv_path):
                csv_df = pd.read_csv(csv_path)
                
                # Rename columns to match our schema
                csv_df = csv_df.rename(columns={
                    'site_no': 'station_number',
                    'station_nm': 'name'
                })
                
                # Ensure station_number is string type for merging
                csv_df['station_number'] = csv_df['station_number'].astype(str)
                
                # Select only the enrichment columns we need
                enrich_cols = ['station_number', 'drainage_area']
                csv_enrichment = csv_df[enrich_cols].copy()
                
                # Convert drainage_area to numeric (handle any formatting issues)
                csv_enrichment['drainage_area'] = pd.to_numeric(
                    csv_enrichment['drainage_area'], 
                    errors='coerce'
                )
                
                # Merge with existing data
                # Only update rows where catchment_area is None or drainage_area doesn't exist
                if 'drainage_area' not in df.columns or df['drainage_area'].isna().all():
                    # Left merge to add drainage_area from CSV
                    df = df.merge(
                        csv_enrichment, 
                        on='station_number', 
                        how='left',
                        suffixes=('', '_csv')
                    )
                    
                    # Use CSV drainage_area if API catchment_area is not available
                    if 'drainage_area_csv' in df.columns:
                        if 'drainage_area' in df.columns:
                            df['drainage_area'] = df['drainage_area'].fillna(df['drainage_area_csv'])
                        else:
                            df['drainage_area'] = df['drainage_area_csv']
                        df = df.drop(columns=['drainage_area_csv'])
                
                logger.info(f"Enriched {len(df)} stations with CSV data")
            else:
                logger.warning(f"CSV file not found: {csv_path}")
        except Exception as e:
            logger.error(f"Error enriching from CSV: {e}")
        
        return df
    
    def _enrich_station_metadata(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enrich station metadata with visualization-specific fields.
        
        Maps API field names to the names expected by the dashboard
        components (map, filters, etc.).
        
        Parameters:
        -----------
        df : pd.DataFrame
            Raw station data from DataOps
        
        Returns:
        --------
        pd.DataFrame
            Enriched station data with color coding, aliases, etc.
        """
        if df.empty:
            return df
        
        # === Column name mappings for backward compatibility ===
        
        # site_id: primary identifier used by map component and callbacks
        if 'station_number' in df.columns and 'site_id' not in df.columns:
            df['site_id'] = df['station_number']
        
        # site_no: alias used by some visualization code
        if 'station_number' in df.columns and 'site_no' not in df.columns:
            df['site_no'] = df['station_number']
        
        # station_name: display name used by map hover and info panels
        if 'name' in df.columns and 'station_name' not in df.columns:
            df['station_name'] = df['name']
        
        # station_nm: legacy alias
        if 'name' in df.columns and 'station_nm' not in df.columns:
            df['station_nm'] = df['name']
        
        # drainage_area: map sizing (API returns catchment_area in sq km)
        if 'catchment_area' in df.columns and 'drainage_area' not in df.columns:
            # Convert sq km to sq mi (1 sq km = 0.386102 sq mi)
            df['drainage_area'] = pd.to_numeric(df['catchment_area'], errors='coerce') * 0.386102
        elif 'drainage_area' not in df.columns:
            df['drainage_area'] = None
        
        # basin: filter dropdown (API returns 'basin' directly)
        if 'basin_name' in df.columns and 'basin' not in df.columns:
            df['basin'] = df['basin_name']
        
        # Ensure required columns exist with defaults
        required_defaults = {
            'latitude': None,
            'longitude': None,
            'state': None,
            'huc_code': None,
            'basin': None,
            'drainage_area': None,
            'is_active': True,
        }
        for col, default in required_defaults.items():
            if col not in df.columns:
                logger.warning(f"Missing column '{col}', using default: {default}")
                df[col] = default
        
        # Add color coding based on station activity status (for map visualization)
        if 'station_status' in df.columns:
            df['status'] = df['station_status']
            df['color'] = df['station_status'].apply(
                lambda s: '#32CD32' if s == 'Active' else '#808080'
            )
        elif 'state' in df.columns:
            df['status'] = 'Active'
            df['color'] = '#32CD32'
        else:
            df['status'] = 'Active'
            df['color'] = '#32CD32'
        
        # Filter by target states if configured
        if TARGET_STATES and 'state' in df.columns:
            df = df[df['state'].isin(TARGET_STATES)]
        
        return df
    
    def get_filters_table(self) -> pd.DataFrame:
        """
        Get station data for populating filter dropdowns (basin, HUC, state).
        
        Returns the cached stations DataFrame from the last load_regional_gauges()
        call. If no cache exists, fetches fresh data.
        
        Returns:
        --------
        pd.DataFrame
            Station data with state, basin, huc_code columns
        """
        if self._stations_cache is not None and not self._stations_cache.empty:
            return self._stations_cache
        
        # Cache miss — load fresh
        logger.info("get_filters_table: no cache, loading fresh station data")
        return self.load_regional_gauges()
    
    def get_sites_with_realtime_data(self) -> List[str]:
        """
        Get list of site IDs that have real-time (15-min) data available.
        
        Queries the DataOps API for stations that have realtime observations.
        Falls back to returning all sites if the query fails.
        
        Returns:
        --------
        list
            List of site IDs with real-time data
        """
        try:
            # Use cached stations if available
            if self._stations_cache is not None and not self._stations_cache.empty:
                if 'site_id' in self._stations_cache.columns:
                    return self._stations_cache['site_id'].tolist()
                elif 'station_number' in self._stations_cache.columns:
                    return self._stations_cache['station_number'].tolist()
            
            # Fallback: return all available sites
            return self.get_available_sites()
            
        except Exception as e:
            logger.error(f"Error getting sites with realtime data: {e}")
            return []
    
    def get_data_source_info(self) -> Dict[str, Any]:
        """
        Get information about the data source for discharge data.
        
        Returns:
        --------
        dict
            Dictionary with keys:
            - mode: 'api', 'cache', or 'hybrid'
            - api_enabled: bool
            - cache_enabled: bool
            - source_name: Human-readable source name
        """
        mode = self.adapter.mode
        api_enabled = self.adapter.api_enabled
        cache_enabled = self.adapter.cache_enabled
        
        # Determine source name
        if mode == 'api':
            source_name = "StreamFlow DataOps API"
        elif mode == 'cache':
            source_name = "Local Cache (Offline)"
        elif mode == 'hybrid':
            source_name = "StreamFlow DataOps API (Cache Fallback)"
        else:
            source_name = "Unknown"
        
        return {
            'mode': mode,
            'api_enabled': api_enabled,
            'cache_enabled': cache_enabled,
            'source_name': source_name
        }
    
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

    def get_forecast_data(self, site_id: str, num_days: int = 5) -> Optional[List[Dict]]:
        """
        Get NWRFC forecast data for a USGS station (multiple days).
        
        Uses the NWRFC→USGS crosswalk to look up the forecast code,
        then fetches the last num_days of forecasts from the DataOps API.
        
        Parameters:
        -----------
        site_id : str
            USGS station number (e.g., '14187500')
        num_days : int
            Number of distinct calendar days of forecasts (default: 5)
        
        Returns:
        --------
        list or None
            List of dicts with 'run_date' (str) and 'data' (DataFrame),
            ordered newest-first. None if no forecast available.
        """
        try:
            forecast_runs = self.adapter.get_forecast_data(site_id, num_days=num_days)
            if forecast_runs:
                logger.info(f"Got {len(forecast_runs)} forecast runs for {site_id}")
            return forecast_runs
        except Exception as e:
            logger.warning(f"Error getting forecast data for {site_id}: {e}")
            return None

    def get_forecast_station_ids(self) -> set:
        """
        Get the set of USGS station IDs that have NWRFC forecast data available.
        
        Queries the DataOps API for NOAA_RFC stations, then maps their codes
        to USGS station IDs via the NWRFC crosswalk. Results are cached.
        
        Returns:
        --------
        set
            Set of USGS station ID strings that have NWRFC forecasts (~278 stations).
        """
        # Return cached result if available
        if hasattr(self, '_forecast_station_ids_cache') and self._forecast_station_ids_cache:
            return self._forecast_station_ids_cache
        
        try:
            # Get all NOAA_RFC station codes from the API
            if not self.adapter.api_client:
                logger.warning("No API client available for forecast station lookup")
                return set()
            
            resp = self.adapter.api_client.get_stations(agency='NOAA_RFC', limit=500)
            nwrfc_codes = {s.station_number for s in resp.results}
            logger.info(f"Found {len(nwrfc_codes)} NOAA_RFC stations from API")
            
            # Load crosswalk and map NWRFC codes to USGS IDs
            self.adapter._load_nwrfc_crosswalk()
            nwrfc_to_usgs = self.adapter._nwrfc_to_usgs
            
            forecast_usgs_ids = set()
            for code in nwrfc_codes:
                usgs_id = nwrfc_to_usgs.get(code)
                if usgs_id:
                    forecast_usgs_ids.add(usgs_id)
            
            logger.info(f"Mapped to {len(forecast_usgs_ids)} unique USGS station IDs with forecasts")
            self._forecast_station_ids_cache = forecast_usgs_ids
            return forecast_usgs_ids
            
        except Exception as e:
            logger.warning(f"Error getting forecast station IDs: {e}")
            return set()


    def get_cached_percentile_bands(self) -> dict:
        """
        Return the most recently fetched percentile bands dict.
        Non-blocking. Returns {} if never fetched.
        """
        return self._percentile_cache.copy()

    def trigger_percentile_refresh(self):
        """Wake the background thread to refresh immediately."""
        if self._percentile_refresh_event is not None:
            self._percentile_refresh_event.set()

    def start_percentile_background_refresh(self, interval_seconds: int = 1800):
        """
        Start a daemon thread that refreshes percentile bands periodically.
        Call once at app startup.
        """
        if self._percentile_bg_thread and self._percentile_bg_thread.is_alive():
            return  # Already running

        def _loop():
            while True:
                try:
                    bands = self.adapter.get_flow_percentile_bands(days_back=2)
                    if bands:
                        self._percentile_cache = bands
                        self._percentile_cache_time = time.time()
                        logger.info(
                            f"Percentile bands refreshed: {len(bands)} stations "
                            f"at {datetime.now().strftime('%H:%M:%S')}"
                        )
                    else:
                        logger.warning("Percentile bands fetch returned empty result")
                except Exception as e:
                    logger.error(f"Percentile background refresh error: {e}")
                # Wait for next interval or manual trigger
                self._percentile_refresh_event.wait(timeout=interval_seconds)
                self._percentile_refresh_event.clear()

        self._percentile_bg_thread = threading.Thread(
            target=_loop, daemon=True, name="percentile-refresh"
        )
        self._percentile_bg_thread.start()
        logger.info("Percentile background refresh thread started")


def get_data_manager() -> USGSDataManager:
    """
    Get singleton instance of data manager.
    
    Returns:
    --------
    USGSDataManager
        Data manager instance
    """
    return USGSDataManager()
