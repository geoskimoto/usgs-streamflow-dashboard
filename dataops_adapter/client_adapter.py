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
        Get set of station numbers where is_active=True.

        Uses GET /api/v1/stations/?is_active=true — the same flag the db_adapter
        queries via WHERE is_active = TRUE. This is faster and more reliable than
        scanning discharge observations, which can return empty or partial sets.

        Args:
            months_back: Unused — kept for interface compatibility with db_adapter.

        Returns:
            Set of station number strings for active stations.
        """
        if not self.api_enabled or not self.api_client:
            logger.warning("API not available for active station lookup")
            return set()

        try:
            active_stations = set()
            page_size = 1000
            offset = 0

            while True:
                response = self.api_client.get_stations(
                    is_active=True,
                    limit=page_size,
                    offset=offset
                )

                for station in response.results:
                    if station.station_number:
                        active_stations.add(station.station_number)

                if not response.next:
                    break

                offset += page_size

            logger.info(f"Found {len(active_stations)} active stations (via is_active flag)")
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

    def _load_ec_nwrfc_crosswalk(self) -> dict:
        """Load EC gauge ID → NWRFC LID from data/ec_nwrfc_crosswalk.json."""
        if hasattr(self, '_ec_to_nwrfc') and self._ec_to_nwrfc:
            return self._ec_to_nwrfc

        self._ec_to_nwrfc = {}
        crosswalk_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'ec_nwrfc_crosswalk.json',
        )
        try:
            if os.path.exists(crosswalk_path):
                with open(crosswalk_path, 'r') as f:
                    self._ec_to_nwrfc = json.load(f)
                logger.info("Loaded EC→NWRFC crosswalk: %d mappings", len(self._ec_to_nwrfc))
        except Exception as exc:
            logger.warning("Failed to load EC→NWRFC crosswalk: %s", exc)

        return self._ec_to_nwrfc

    def _get_nwrfc_lid(self, site_id: str) -> Optional[str]:
        """Return NWRFC LID for a USGS or EC gauge ID, or None if no mapping."""
        usgs_map = getattr(self, '_usgs_to_nwrfc', {})
        lid = usgs_map.get(site_id)
        if lid:
            return lid
        return self._load_ec_nwrfc_crosswalk().get(site_id)

    def get_nwrfc_web_forecasts(self, site_id: str, num_days: int = 5) -> Optional[List[Dict]]:
        """Get nwrfc_web forecast runs for a USGS or EC station.

        Returns list of {'run_date': str, 'data': DataFrame} or None.
        """
        if not self.api_client:
            return None

        lid = self._get_nwrfc_lid(site_id)
        if not lid:
            logger.debug("get_nwrfc_web_forecasts: no NWRFC LID for %s", site_id)
            return None

        try:
            forecasts = self.api_client.get_nwrfc_web_forecasts(lid, num_days=num_days)
            if not forecasts:
                return None

            result = []
            for run in forecasts:
                rows = []
                for point in run.get('data', []):
                    dt = pd.to_datetime(point.get('date'), errors='coerce', utc=True)
                    val = point.get('value')
                    if pd.notna(dt) and val is not None:
                        rows.append({'datetime': dt, 'discharge_cfs': float(val)})
                if not rows:
                    continue
                df = pd.DataFrame(rows).sort_values('datetime').reset_index(drop=True)
                result.append({'run_date': run.get('run_date'), 'data': df})

            return result if result else None

        except Exception as exc:
            logger.warning("get_nwrfc_web_forecasts(%s / %s): %s", site_id, lid, exc)
            return None

    def get_nwrfc_forecasts(self, site_id: str, num_days: int = 5) -> Optional[List[Dict]]:
        """Get NWRFC forecasts preferring nwrfc_web with NOAA API fallback."""
        result = self.get_nwrfc_web_forecasts(site_id, num_days=num_days)
        if result:
            return result
        logger.debug("get_nwrfc_forecasts(%s): nwrfc_web empty, falling back to NOAA API", site_id)
        return self.get_forecast_data(site_id, num_days=num_days)

    def get_percentile_date_range(self) -> Dict[str, Optional[str]]:
        """
        Fetch the min/max dates available in daily_flow_percentiles.

        Calls GET /api/v1/observations/discharge/percentile-date-range/

        Returns {'min_date': 'YYYY-MM-DD', 'max_date': 'YYYY-MM-DD'} or
        empty dict on any error.
        """
        if not self.api_enabled or not self.api_client:
            logger.warning("API not available; cannot fetch percentile date range")
            return {}
        try:
            response = self.api_client._request(
                'GET',
                '/api/v1/observations/discharge/percentile-date-range/',
            )
            return {
                'min_date': response.get('min_date'),
                'max_date': response.get('max_date'),
            }
        except Exception as e:
            logger.error(f"Failed to fetch percentile date range: {e}")
            return {}

    def get_forecast_percentile_date_range(self, source: str = 'NWRFC') -> dict:
        """
        Fetch min/max forecast dates available in forecast_percentiles.
        GET /api/v1/forecasts/discharge/percentile-date-range/
        Returns {'min_date': str, 'max_date': str, 'forecast_run_date': str} or {}.
        """
        if not self.api_enabled or not self.api_client:
            logger.warning("API not available; cannot fetch forecast percentile date range")
            return {}
        try:
            response = self.api_client._request(
                'GET',
                '/api/v1/forecasts/discharge/percentile-date-range/',
                params={'source': source},
            )
            return {
                'min_date': response.get('min_date'),
                'max_date': response.get('max_date'),
                'forecast_run_date': response.get('forecast_run_date'),
            }
        except Exception as e:
            logger.error(f"Failed to fetch forecast percentile date range: {e}")
            return {}

    def get_forecast_percentile_bands(
        self,
        target_date: str,
        source: str = 'NWRFC',
    ) -> dict:
        """
        Fetch forecast percentile bands for a specific future date.
        GET /api/v1/forecasts/discharge/percentile-bands/
        Returns {'bands': {station_number: band}, 'forecast_run_date': str} or {}.
        """
        if not self.api_enabled or not self.api_client:
            logger.warning("API not available; cannot fetch forecast percentile bands")
            return {}
        try:
            response = self.api_client._request(
                'GET',
                '/api/v1/forecasts/discharge/percentile-bands/',
                params={'date': target_date, 'source': source},
            )
            results = response.get('results', [])
            bands = {r['station_number']: r['band'] for r in results}
            forecast_run_date = response.get('forecast_run_date')
            logger.info(
                f"Fetched forecast percentile bands for {len(bands)} stations "
                f"(date={target_date}, source={source})"
            )
            return {'bands': bands, 'forecast_run_date': forecast_run_date}
        except Exception as e:
            logger.error(f"Failed to fetch forecast percentile bands: {e}")
            return {}

    def get_flow_percentile_bands(self, target_date: Optional[str] = None) -> Dict[str, str]:
        """
        Fetch precomputed percentile bands from StreamflowOps.

        Calls GET /api/v1/observations/discharge/percentile-bands/ and returns
        a dict mapping station_number -> band_key.

        Parameters
        ----------
        target_date : str, optional
            ISO date string (YYYY-MM-DD).  If None, the API returns the latest
            available date.

        Band keys: p0_4, p5_10, p11_25, p26_50, p51_75, p76_100

        Returns empty dict on any error so callers degrade gracefully.
        """
        if not self.api_enabled or not self.api_client:
            logger.warning("API not available; cannot fetch percentile bands")
            return {}
        try:
            params = {'date': target_date} if target_date else {}
            response = self.api_client._request(
                'GET',
                '/api/v1/observations/discharge/percentile-bands/',
                params=params or None,
            )
            results = response.get('results', [])
            bands = {r['station_number']: r['band'] for r in results}
            suffix = f" (date={target_date})" if target_date else " (latest)"
            logger.info(f"Fetched percentile bands for {len(bands)} stations{suffix}")
            return bands
        except Exception as e:
            logger.error(f"Failed to fetch percentile bands: {e}")
            return {}
