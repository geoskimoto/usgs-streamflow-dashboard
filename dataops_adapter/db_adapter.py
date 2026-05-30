"""
Direct PostgreSQL adapter for dashboard data access.

Use this when the dashboard and DataOps API share the same server,
bypassing the REST API for significantly faster data access.

Provides the same interface as DataOpsAdapter so it can be used
as a drop-in replacement.
"""

import json
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from decimal import Decimal

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

from .exceptions import AdapterError

logger = logging.getLogger(__name__)


def _get_db_config() -> dict:
    """Build database config from environment variables."""
    password = os.getenv('DB_PASSWORD')
    if not password:
        raise AdapterError("DB_PASSWORD environment variable is required but not set")
    return {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': os.getenv('DB_PORT', '5432'),
        'dbname': os.getenv('DB_NAME', 'streamflow_db'),
        'user': os.getenv('DB_USER', 'streamflow_user'),
        'password': password,
    }


class DirectDBAdapter:
    """
    Direct PostgreSQL adapter -- replaces REST API calls with SQL queries.

    Same method signatures as DataOpsAdapter so the data manager can
    swap between them with no code changes.

    Usage:
        adapter = DirectDBAdapter()
        stations = adapter.get_stations(state='OR')
        data = adapter.get_discharge_data('09070500', '2025-01-01', '2026-01-01')
    """

    def __init__(self, db_config: dict = None):
        """
        Initialize adapter.

        Args:
            db_config: Database connection params. If None, reads from env vars.
        """
        self.db_config = db_config or _get_db_config()
        self.mode = 'direct_db'
        self.api_enabled = False
        self.cache_enabled = False

        # Verify connectivity at startup
        if not self.test_connection():
            raise AdapterError(
                f"Cannot connect to PostgreSQL at "
                f"{self.db_config['host']}:{self.db_config['port']}"
                f"/{self.db_config['dbname']}"
            )
        logger.info(
            f"DirectDBAdapter: connected to {self.db_config['dbname']} "
            f"at {self.db_config['host']}:{self.db_config['port']}"
        )

    def _get_connection(self):
        """Get a new database connection."""
        return psycopg2.connect(**self.db_config)

    def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"DirectDBAdapter: connection test failed: {e}")
            return False

    def get_stations(
        self,
        state: Optional[str] = None,
        agency: str = 'USGS',
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 10000,
    ) -> pd.DataFrame:
        """
        Fetch stations directly from PostgreSQL.

        Args:
            state: Filter by state code (e.g., 'OR', 'WA')
            agency: Filter by agency (default: 'USGS')
            is_active: Filter by active status
            search: Search in station number or name
            limit: Maximum results

        Returns:
            DataFrame with station metadata
        """
        query = """
            SELECT
                s.station_number,
                s.name,
                s.agency,
                s.latitude,
                s.longitude,
                s.state,
                s.huc_code,
                s.basin AS basin_name,
                s.catchment_area,
                s.years_of_record,
                s.record_start_date,
                s.record_end_date,
                s.is_active
            FROM stations s
            WHERE 1=1
        """
        params = []

        if state:
            query += " AND s.state = %s"
            params.append(state)
        if agency:
            query += " AND s.agency = %s"
            params.append(agency)
        if is_active is not None:
            query += " AND s.is_active = %s"
            params.append(is_active)
        if search:
            query += " AND (s.station_number ILIKE %s OR s.name ILIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY s.station_number LIMIT %s"
        params.append(limit)

        try:
            with self._get_connection() as conn:
                df = pd.read_sql(query, conn, params=params)
        except Exception as e:
            logger.error(f"Error fetching stations: {e}")
            raise AdapterError(f"Failed to fetch stations: {e}")

        if df.empty:
            return df

        # Convert Decimal types to float for downstream compatibility
        decimal_cols = ['latitude', 'longitude', 'catchment_area', 'years_of_record']
        for col in decimal_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.info(f"Fetched {len(df)} stations from DB (state={state})")
        return df

    def get_discharge_data(
        self,
        station_number: str,
        start_date: str,
        end_date: str,
        data_type: str = 'daily_mean',
    ) -> pd.DataFrame:
        """
        Fetch discharge observations directly from PostgreSQL.

        Args:
            station_number: Station identifier (e.g., '09070500')
            start_date: Start date ('YYYY-MM-DD')
            end_date: End date ('YYYY-MM-DD')
            data_type: 'daily_mean' or 'realtime_15min'

        Returns:
            DataFrame with columns: date, station_number, discharge, unit, quality
        """
        query = """
            SELECT
                obs.observed_at AS date,
                s.station_number,
                obs.discharge,
                obs.unit,
                obs.quality_code AS quality
            FROM discharge_observations obs
            JOIN stations s ON obs.station_id = s.id
            WHERE s.station_number = %s
              AND obs.observed_at >= %s
              AND obs.observed_at < %s
              AND obs.type = %s
            ORDER BY obs.observed_at
        """
        params = [station_number, start_date, end_date, data_type]

        try:
            with self._get_connection() as conn:
                df = pd.read_sql(query, conn, params=params)
        except Exception as e:
            logger.error(f"Error fetching discharge data for {station_number}: {e}")
            raise AdapterError(f"Failed to fetch discharge data: {e}")

        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['discharge'] = pd.to_numeric(df['discharge'], errors='coerce')

        logger.info(
            f"Fetched {len(df)} observations for {station_number} from DB"
        )
        return df

    def get_station_info(self, station_number: str) -> Dict[str, Any]:
        """
        Get detailed station information.

        Args:
            station_number: Station identifier

        Returns:
            Dictionary with station details
        """
        query = """
            SELECT
                s.station_number,
                s.name,
                s.agency,
                s.latitude,
                s.longitude,
                s.state,
                s.huc_code,
                s.basin AS basin_name,
                s.is_active,
                s.catchment_area,
                s.years_of_record,
                s.record_start_date,
                s.record_end_date,
                ms.drainage_area_sqmi,
                ms.altitude_ft,
                ms.rfc_code,
                ms.noaa_lid
            FROM stations s
            LEFT JOIN master_stations ms
                ON s.station_number = ms.station_number
            WHERE s.station_number = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, [station_number])
                    row = cur.fetchone()
        except Exception as e:
            logger.error(f"Error fetching station info for {station_number}: {e}")
            raise AdapterError(f"Failed to get station info: {e}")

        if not row:
            return {}

        # Convert Decimal values to float for JSON serialization
        result = {}
        for k, v in dict(row).items():
            if isinstance(v, Decimal):
                result[k] = float(v)
            else:
                result[k] = v
        return result

    def get_active_station_numbers(self, months_back: int = 6) -> set:
        """
        Get station numbers for all active stations (any agency).

        Reads stations.is_active (maintained by the dataOps pipeline) rather
        than scanning discharge_observations, which is orders of magnitude
        faster and avoids multi-minute full-table scans.

        Args:
            months_back: Unused — kept for interface compatibility.

        Returns:
            Set of station number strings for active stations
        """
        query = """
            SELECT station_number
            FROM stations
            WHERE is_active = TRUE
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    result = {row[0] for row in cur.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching active station numbers: {e}")
            return set()

        logger.info(f"Found {len(result)} active stations (via is_active flag)")
        return result

    def _load_crosswalk(self) -> dict:
        """Load NWRFC→USGS crosswalk from bundled JSON file."""
        crosswalk_path = os.path.join(
            os.path.dirname(__file__), '..', 'data', 'nwrfc_usgs_crosswalk.json'
        )
        try:
            with open(crosswalk_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load NWRFC crosswalk: {e}")
            return {}

    def _get_nwrfc_code(self, usgs_station_number: str) -> Optional[str]:
        """Return the NWRFC station code for a given USGS station number, or None."""
        crosswalk = self._load_crosswalk()
        # crosswalk is nwrfc_code -> usgs_id; build reverse map
        usgs_to_nwrfc = {v: k for k, v in crosswalk.items()}
        return usgs_to_nwrfc.get(usgs_station_number)

    def get_percentile_date_range(self) -> Dict[str, Optional[str]]:
        """Return the min/max dates available in daily_flow_percentiles."""
        query = """
            SELECT MIN(date)::text, MAX(date)::text
            FROM daily_flow_percentiles
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    row = cur.fetchone()
            return {'min_date': row[0], 'max_date': row[1]} if row else {}
        except Exception as e:
            logger.error(f"Error fetching percentile date range from DB: {e}")
            return {}

    def get_flow_percentile_bands(self, target_date: Optional[str] = None) -> Dict[str, str]:
        """
        Fetch precomputed percentile bands directly from the DB.

        Parameters
        ----------
        target_date : str, optional
            ISO date string (YYYY-MM-DD).  If None, uses the latest date
            available in daily_flow_percentiles.

        Returns:
            Dict mapping station_number -> band key (e.g. 'p26_50')
        """
        if target_date:
            query = """
                SELECT s.station_number, dfp.band
                FROM daily_flow_percentiles dfp
                JOIN stations s ON dfp.station_id = s.id
                WHERE dfp.date = %s
            """
            params = [target_date]
        else:
            query = """
                SELECT s.station_number, dfp.band
                FROM daily_flow_percentiles dfp
                JOIN stations s ON dfp.station_id = s.id
                WHERE dfp.date = (SELECT MAX(date) FROM daily_flow_percentiles)
            """
            params = []
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    rows = cur.fetchall()
            bands = {row[0]: row[1] for row in rows}
            suffix = f" (date={target_date})" if target_date else " (latest)"
            logger.info(f"Fetched percentile bands for {len(bands)} stations from DB{suffix}")
            return bands
        except Exception as e:
            logger.error(f"Error fetching percentile bands: {e}")
            return {}

    def get_forecast_percentile_date_range(self, source: str = 'NWRFC') -> dict:
        """Return the min/max forecast dates available in forecast_percentiles."""
        query = """
            SELECT MIN(target_date)::text, MAX(target_date)::text,
                   MAX(forecast_run_date)::text
            FROM forecast_percentiles
            WHERE source = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [source])
                    row = cur.fetchone()
            if row and row[0]:
                return {
                    'min_date': row[0],
                    'max_date': row[1],
                    'forecast_run_date': row[2],
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching forecast percentile date range from DB: {e}")
            return {}

    def get_forecast_percentile_bands(
        self,
        target_date: str,
        source: str = 'NWRFC',
    ) -> dict:
        """
        Fetch forecast percentile bands directly from the DB.
        Returns {'bands': {station_number: band}, 'forecast_run_date': str}.
        """
        query = """
            SELECT s.station_number, fp.band, fp.forecast_run_date::text
            FROM forecast_percentiles fp
            JOIN stations s ON fp.station_id = s.id
            WHERE fp.target_date = %s AND fp.source = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [target_date, source])
                    rows = cur.fetchall()
            bands = {row[0]: row[1] for row in rows}
            run_date = rows[0][2] if rows else None
            logger.info(
                f"Fetched forecast percentile bands for {len(bands)} stations "
                f"from DB (date={target_date}, source={source})"
            )
            return {'bands': bands, 'forecast_run_date': run_date}
        except Exception as e:
            logger.error(f"Error fetching forecast percentile bands from DB: {e}")
            return {}

    def get_forecast_data(
        self, usgs_station_number: str, num_days: int = 5
    ) -> Optional[List[Dict]]:
        """
        Fetch recent forecast runs for a USGS station directly from the DB.

        Uses the NWRFC→USGS crosswalk to resolve the NWRFC station code,
        then queries the forecast_runs table (one run per calendar day).

        Returns:
            List of dicts with 'run_date' (str) and 'data' (DataFrame),
            ordered newest-first. None if no data available.
        """
        nwrfc_code = self._get_nwrfc_code(usgs_station_number)
        if not nwrfc_code:
            logger.debug(f"No NWRFC mapping for USGS station {usgs_station_number}")
            return None

        query = """
            SELECT DISTINCT ON (fr.run_date::date)
                fr.run_date,
                fr.data
            FROM forecast_runs fr
            JOIN stations s ON fr.station_id = s.id
            WHERE s.station_number = %s
              AND fr.run_date >= NOW() - (%s * INTERVAL '1 day')
            ORDER BY fr.run_date::date DESC, fr.run_date DESC
            LIMIT %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [nwrfc_code, num_days + 1, num_days])
                    rows = cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching forecast for {usgs_station_number}: {e}")
            return None

        if not rows:
            return None

        result = []
        for run_date, data_json in rows:
            points = data_json if isinstance(data_json, list) else []
            df_rows = []
            for pt in points:
                dt = pd.to_datetime(pt.get('date'), errors='coerce')
                val = pt.get('value')
                if pd.notna(dt) and val is not None:
                    df_rows.append({'datetime': dt, 'discharge_cfs': float(val)})
            if not df_rows:
                continue
            df = pd.DataFrame(df_rows).sort_values('datetime').reset_index(drop=True)
            result.append({
                'run_date': run_date.isoformat() if hasattr(run_date, 'isoformat') else str(run_date),
                'data': df,
            })

        logger.info(f"Fetched {len(result)} forecast runs for {usgs_station_number} from DB")
        return result if result else None

    def get_status(self) -> dict:
        """Get adapter status information."""
        return {
            'mode': 'direct_db',
            'api_enabled': False,
            'cache_enabled': False,
            'db_reachable': self.test_connection(),
            'db_host': self.db_config.get('host'),
            'db_name': self.db_config.get('dbname'),
        }

    def clear_cache(self):
        """No-op -- direct DB doesn't use caching."""
        pass

    def get_cache_stats(self) -> dict:
        """No-op -- direct DB doesn't use caching."""
        return {'mode': 'direct_db', 'cache': 'not applicable'}
