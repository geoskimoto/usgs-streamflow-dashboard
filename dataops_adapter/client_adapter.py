"""
DataOps Client Adapter

Unified interface for dashboard to access streamflow data.
Supports API mode, cache mode, and hybrid mode with fallback.
"""

import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import logging

from dataops_client import DataOpsClient
from .cache_manager import CacheManager
from .models import Station, DischargeObservation
from .config import config
from .exceptions import AdapterError, APIError, CacheError


logger = logging.getLogger(__name__)


class DataOpsAdapter:
    """
    Adapter for accessing streamflow data from DataOps API.
    
    Modes:
    - 'api': Use API only (no caching)
    - 'cache': Use local cache only (offline mode)
    - 'hybrid': Use API with local cache fallback (recommended)
    
    Usage:
        adapter = DataOpsAdapter()  # Auto-detects mode from config
        stations = adapter.get_stations(state='CO')
        data = adapter.get_discharge_data('09070500', '2026-01-01', '2026-01-17')
    """
    
    def __init__(self, mode: Optional[str] = None):
        """
        Initialize adapter.
        
        Args:
            mode: 'api', 'cache', or 'hybrid' (default: from config)
        """
        # Determine mode
        self.mode = mode or config.get_mode()
        self.api_enabled = self.mode in ('api', 'hybrid')
        self.cache_enabled = self.mode in ('cache', 'hybrid')
        
        logger.info(f"DataOpsAdapter initialized in '{self.mode}' mode")
        
        # Initialize API client
        self.api_client = None
        if self.api_enabled:
            try:
                self.api_client = DataOpsClient(
                    base_url=config.api_url,
                    api_token=config.api_token,
                    cache_enabled=False,  # We handle caching
                    verify_ssl=config.verify_ssl,
                    timeout=config.timeout
                )
                logger.info(f"✓ API client connected to {config.api_url}")
            except Exception as e:
                logger.warning(f"API client initialization failed: {e}")
                if self.mode == 'api':
                    # API mode requires API to work
                    raise APIError(f"Cannot initialize API client: {e}")
                # In hybrid mode, we can continue with cache only
                self.api_enabled = False
        
        # Initialize cache manager
        self.cache = None
        if self.cache_enabled:
            try:
                self.cache = CacheManager(
                    db_path=config.cache_db_path,
                    ttl=config.cache_ttl
                )
                logger.info(f"✓ Cache manager initialized at {config.cache_db_path}")
            except Exception as e:
                logger.warning(f"Cache manager initialization failed: {e}")
                if self.mode == 'cache':
                    raise CacheError(f"Cannot initialize cache: {e}")
                self.cache_enabled = False
    
    def test_connection(self) -> bool:
        """
        Test API connection.
        
        Returns:
            True if API is reachable, False otherwise
        """
        if not self.api_enabled or not self.api_client:
            return False
        
        try:
            # Try a simple API call
            result = self.api_client.get_stations(limit=1)
            return True
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False
    
    def get_stations(
        self,
        state: Optional[str] = None,
        agency: str = 'USGS',
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 10000
    ) -> pd.DataFrame:
        """
        Get list of stations.
        
        Args:
            state: Filter by state code (e.g., 'CO', 'CA')
            agency: Filter by agency (default: 'USGS')
            is_active: Filter by active status (default: True)
            search: Search in station number or name
            limit: Maximum results (default: 1000)
        
        Returns:
            DataFrame with columns:
            - station_number (str)
            - name (str)
            - agency (str)
            - latitude (float)
            - longitude (float)
            - state (str)
            - huc_code (str)
            - is_active (bool)
        """
        # Try cache first if enabled
        if self.cache_enabled and self.cache:
            cached = self.cache.get_stations(state=state, agency=agency)
            if cached is not None and not cached.empty:
                logger.debug(f"✓ Cache hit: stations (state={state}, agency={agency})")
                return cached
        
        # Fetch from API
        if self.api_enabled and self.api_client:
            try:
                logger.debug(f"Fetching stations from API (state={state}, limit={limit})")
                
                # Paginate through all results using page-based pagination
                all_stations = []
                page_size = min(limit, 1000)  # API max per page is 1000
                page_num = 1
                max_pages = 20  # Safety limit
                
                while page_num <= max_pages:
                    response = self.api_client.get_stations(
                        state=state,
                        agency=agency,
                        is_active=is_active,
                        search=search,
                        limit=page_size,
                        page=page_num
                    )
                    
                    if not response.results:
                        break
                    
                    all_stations.extend(response.results)
                    
                    # Stop if we got fewer results than requested (last page)
                    if len(response.results) < page_size:
                        break
                    
                    # Stop if we've reached the requested limit
                    if len(all_stations) >= limit:
                        break
                    
                    # Stop if no next page
                    if not response.next:
                        break
                    
                    page_num += 1
                
                # Convert to DataFrame
                df = self._stations_to_dataframe(all_stations)
                
                # Update cache
                if self.cache_enabled and self.cache:
                    self.cache.set_stations(df, state=state, agency=agency)
                
                logger.info(f"✓ Fetched {len(df)} stations from API")
                return df
                
            except Exception as e:
                logger.error(f"API error fetching stations: {e}")
                # Try cache as fallback in hybrid mode
                if self.mode == 'hybrid' and self.cache:
                    cached = self.cache.get_stations(state=state, agency=agency)
                    if cached is not None and not cached.empty:
                        logger.warning("Using cached data as fallback")
                        return cached
                raise APIError(f"Failed to fetch stations: {e}")
        
        # No data source available
        raise AdapterError(
            "No data source available. "
            "API is disabled and cache is empty or disabled."
        )
    
    def get_discharge_data(
        self,
        station_number: str,
        start_date: str,
        end_date: str,
        data_type: str = 'daily_mean'
    ) -> pd.DataFrame:
        """
        Get discharge observations for a station.
        
        Args:
            station_number: Station identifier (e.g., '09070500')
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')
            data_type: Type of data ('daily_mean' or 'realtime_15min')
        
        Returns:
            DataFrame with columns:
            - date (datetime)
            - station_number (str)
            - discharge (float)
            - unit (str)
            - quality (str)
        """
        # Try cache first if enabled
        if self.cache_enabled and self.cache:
            cached = self.cache.get_discharge_data(
                station_number, start_date, end_date, data_type
            )
            if cached is not None and not cached.empty:
                logger.debug(f"✓ Cache hit: discharge data for {station_number}")
                return cached
        
        # Fetch from API
        if self.api_enabled and self.api_client:
            try:
                logger.debug(
                    f"Fetching discharge data from API: "
                    f"{station_number} ({start_date} to {end_date})"
                )
                observations = self.api_client.get_station_data(
                    station_number=station_number,
                    start_date=start_date,
                    end_date=end_date,
                    data_type=data_type
                )
                
                # Convert to DataFrame
                df = self._observations_to_dataframe(observations)
                
                # Update cache
                if self.cache_enabled and self.cache:
                    self.cache.set_discharge_data(
                        df, station_number, start_date, end_date, data_type
                    )
                
                logger.info(f"✓ Fetched {len(df)} observations for {station_number}")
                return df
                
            except Exception as e:
                logger.error(f"API error fetching discharge data: {e}")
                # Try cache as fallback in hybrid mode
                if self.mode == 'hybrid' and self.cache:
                    cached = self.cache.get_discharge_data(
                        station_number, start_date, end_date, data_type
                    )
                    if cached is not None and not cached.empty:
                        logger.warning("Using cached data as fallback")
                        return cached
                raise APIError(f"Failed to fetch discharge data: {e}")
        
        # No data source available
        raise AdapterError(
            "No data source available. "
            "API is disabled and cache is empty or disabled."
        )
    
    def get_station_info(self, station_number: str) -> Dict[str, Any]:
        """
        Get detailed information for a single station.
        
        Args:
            station_number: Station identifier
        
        Returns:
            Dictionary with station details
        """
        if self.api_enabled and self.api_client:
            try:
                station = self.api_client.get_station(station_number)
                return {
                    'station_number': station.station_number,
                    'name': station.name,
                    'agency': station.agency,
                    'latitude': float(station.latitude) if station.latitude else None,
                    'longitude': float(station.longitude) if station.longitude else None,
                    'state': station.state_code,
                    'huc_code': station.huc_code,
                    'basin_name': station.basin_name,
                    'is_active': station.is_active,
                    'last_observation_date': station.last_observation_date,
                }
            except Exception as e:
                logger.error(f"Failed to get station info: {e}")
                raise APIError(f"Failed to get station info: {e}")
        
        raise AdapterError("API is not available")
    
    def get_realtime_data(
        self,
        station_number: str,
        hours_back: int = 48
    ) -> pd.DataFrame:
        """
        Get recent real-time 15-minute data.
        
        Args:
            station_number: Station identifier
            hours_back: Hours of data to retrieve (default: 48)
        
        Returns:
            DataFrame with real-time observations
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours_back)
        
        return self.get_discharge_data(
            station_number=station_number,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            data_type='realtime_15min'
        )
    
    def _stations_to_dataframe(self, stations: List) -> pd.DataFrame:
        """Convert API station objects to DataFrame."""
        if not stations:
            return pd.DataFrame()
        
        data = []
        for station in stations:
            data.append({
                'station_number': station.station_number,
                'name': station.name,
                'agency': station.agency,
                'latitude': float(station.latitude) if station.latitude else None,
                'longitude': float(station.longitude) if station.longitude else None,
                'state': station.state_code,
                'huc_code': station.huc_code,
                'is_active': station.is_active,
                'basin_name': getattr(station, 'basin_name', None),
                'catchment_area': float(station.catchment_area) if station.catchment_area else None,
                'years_of_record': int(float(station.years_of_record)) if station.years_of_record else None,
                'record_start_date': station.record_start_date,
                'record_end_date': station.record_end_date,
            })
        
        return pd.DataFrame(data)
    
    def _observations_to_dataframe(self, observations: List) -> pd.DataFrame:
        """Convert API observation objects to DataFrame."""
        if not observations:
            return pd.DataFrame(columns=['date', 'station_number', 'discharge', 'unit', 'quality'])
        
        data = []
        for obs in observations:
            data.append({
                'date': pd.to_datetime(obs.observed_at),
                'station_number': obs.station_number,
                'discharge': obs.discharge_value,
                'unit': obs.unit,
                'quality': obs.quality_code,
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values('date').reset_index(drop=True)
        
        return df
    
    def get_active_station_numbers(self, months_back: int = 6) -> set:
        """
        Get set of station numbers that have discharge data in the last N months.
        
        Queries the discharge observations API for recent data and returns the
        unique station numbers found. This is used to classify stations as
        'Active' (has recent data) vs 'Inactive' (no recent data).
        
        NOTE: Does NOT filter by agency since the observations endpoint doesn't 
        support agency filtering - it returns all agencies' observations naturally.
        
        Args:
            months_back: Number of months to look back (default: 6)
        
        Returns:
            Set of station number strings with recent discharge data
        """
        if not self.api_enabled or not self.api_client:
            logger.warning("API not available for active station lookup")
            return set()
        
        try:
            start_date = (datetime.now() - timedelta(days=months_back * 30)).strftime('%Y-%m-%d')
            active_stations = set()
            page_num = 1
            page_limit = 1000
            max_pages = 50  # Increased to handle more stations across all agencies
            
            for _ in range(max_pages):
                response = self.api_client._request(
                    'GET',
                    '/api/v1/observations/discharge/',
                    params={
                        'start_date': start_date,
                        'limit': page_limit,
                        'page': page_num,
                        'ordering': 'station_number'
                    }
                )
                
                if not isinstance(response, dict) or 'results' not in response:
                    break
                
                results = response['results']
                if not results:
                    break
                
                prev_count = len(active_stations)
                for obs in results:
                    sn = obs.get('station_number', '')
                    if sn:
                        active_stations.add(sn)
                
                # Stop if no new stations found (we've seen them all)
                if len(active_stations) == prev_count:
                    break
                
                # Stop if no more pages
                if not response.get('next'):
                    break
                
                page_num += 1
            
            logger.info(f"Found {len(active_stations)} stations with data in the last {months_back} months")
            return active_stations
            
        except Exception as e:
            logger.error(f"Error fetching active station numbers: {e}")
            return set()
    
    def clear_cache(self):
        """Clear local cache."""
        if self.cache:
            self.cache.clear_cache()
    
    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if self.cache:
            return self.cache.get_stats()
        return {'error': 'Cache not enabled'}
    
    def get_status(self) -> dict:
        """Get adapter status information."""
        return {
            'mode': self.mode,
            'api_enabled': self.api_enabled,
            'cache_enabled': self.cache_enabled,
            'api_reachable': self.test_connection() if self.api_enabled else False,
            'api_url': config.api_url if self.api_enabled else None,
            'cache_stats': self.get_cache_stats() if self.cache_enabled else None
        }

    # ===== NWRFC Forecast Crosswalk =====

    def _load_nwrfc_crosswalk(self) -> Dict[str, str]:
        """
        Load the NWRFC→USGS crosswalk from the CSV file.
        Returns dict mapping USGS station number → NWRFC code.
        """
        if hasattr(self, '_usgs_to_nwrfc') and self._usgs_to_nwrfc:
            return self._usgs_to_nwrfc

        crosswalk_csv = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'usgs_hads_raw_data.csv'
        )
        crosswalk_json = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'nwrfc_usgs_crosswalk.json'
        )

        self._usgs_to_nwrfc = {}
        self._nwrfc_to_usgs = {}

        try:
            # Prefer JSON crosswalk if available
            if os.path.exists(crosswalk_json):
                with open(crosswalk_json, 'r') as f:
                    nwrfc_map = json.load(f)  # nws_id → usgs_id
                for nws_id, usgs_id in nwrfc_map.items():
                    self._nwrfc_to_usgs[nws_id] = usgs_id
                    self._usgs_to_nwrfc[usgs_id] = nws_id
            elif os.path.exists(crosswalk_csv):
                import csv
                with open(crosswalk_csv, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        nws_id = row.get('nws_id', '').strip()
                        usgs_id = row.get('usgs_id', '').strip()
                        if nws_id and usgs_id:
                            self._nwrfc_to_usgs[nws_id] = usgs_id
                            self._usgs_to_nwrfc[usgs_id] = nws_id

            logger.info(f"Loaded NWRFC crosswalk: {len(self._usgs_to_nwrfc)} USGS→NWRFC mappings")
        except Exception as e:
            logger.warning(f"Failed to load NWRFC crosswalk: {e}")

        return self._usgs_to_nwrfc

    def get_nwrfc_code(self, usgs_station_number: str) -> Optional[str]:
        """
        Look up the NWRFC code for a USGS station number.
        
        Args:
            usgs_station_number: USGS station ID (e.g., '14187500')
        
        Returns:
            NWRFC code (e.g., 'WTLO3') or None if no mapping exists
        """
        crosswalk = self._load_nwrfc_crosswalk()
        return crosswalk.get(usgs_station_number)

    def get_forecast_data(self, usgs_station_number: str, num_days: int = 5) -> Optional[List[Dict]]:
        """
        Get NWRFC forecast runs for a USGS station (one per day, up to num_days).
        
        Uses the crosswalk to look up the NWRFC code, then fetches
        forecast data from the DataOps API.
        
        Args:
            usgs_station_number: USGS station ID (e.g., '14187500')
            num_days: Number of distinct calendar days of forecasts to fetch
        
        Returns:
            List of dicts, each with keys:
                'run_date': str (ISO format)
                'data': DataFrame with columns ['datetime', 'discharge_cfs']
            Ordered newest-first. Returns None if no data available.
        """
        if not self.api_client:
            return None

        nwrfc_code = self.get_nwrfc_code(usgs_station_number)
        if not nwrfc_code:
            logger.debug(f"No NWRFC mapping for USGS station {usgs_station_number}")
            return None

        try:
            forecasts = self.api_client.get_forecast_by_station(
                nwrfc_code, num_days=num_days
            )
            if not forecasts:
                logger.debug(f"No forecast data for {nwrfc_code}")
                return None

            result = []
            for run in forecasts:
                forecast_points = run.get('data', [])
                if not forecast_points:
                    continue

                rows = []
                for point in forecast_points:
                    dt = pd.to_datetime(point.get('date'), errors='coerce')
                    val = point.get('value')
                    if pd.notna(dt) and val is not None:
                        rows.append({'datetime': dt, 'discharge_cfs': float(val)})

                if not rows:
                    continue

                df = pd.DataFrame(rows)
                df = df.sort_values('datetime').reset_index(drop=True)

                run_date = run.get('run_date', 'unknown')
                result.append({
                    'run_date': run_date,
                    'data': df
                })
                logger.info(
                    f"Forecast for {usgs_station_number} ({nwrfc_code}): "
                    f"{len(df)} points, run_date={run_date}"
                )

            return result if result else None

        except Exception as e:
            logger.warning(f"Error fetching forecast for {usgs_station_number}: {e}")
            return None

    def get_flow_percentile_bands(self, days_back: int = 2) -> Dict[str, str]:
        """
        Fetch precomputed percentile bands from StreamflowOps.

        Calls GET /api/v1/observations/discharge/percentile-bands/ and returns
        a dict mapping station_number -> band_key.

        Band keys: p0_4, p5_10, p11_25, p26_50, p51_75, p76_100

        Returns empty dict on any error so callers degrade gracefully.
        """
        if not self.api_enabled or not self.api_client:
            logger.warning("API not available; cannot fetch percentile bands")
            return {}
        try:
            response = self.api_client._request(
                'GET',
                '/api/v1/observations/discharge/percentile-bands/',
                params={'days_back': days_back}
            )
            results = response.get('results', [])
            bands = {r['station_number']: r['band'] for r in results}
            logger.info(f"Fetched percentile bands for {len(bands)} stations")
            return bands
        except Exception as e:
            logger.error(f"Failed to fetch percentile bands: {e}")
            return {}
