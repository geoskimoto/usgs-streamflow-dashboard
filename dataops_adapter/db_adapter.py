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
    return {
        'host': os.getenv('DB_HOST', '127.0.0.1'),
        'port': os.getenv('DB_PORT', '5432'),
        'dbname': os.getenv('DB_NAME', 'streamflow_db'),
        'user': os.getenv('DB_USER', 'streamflow_user'),
        'password': os.getenv('DB_PASSWORD', 'streamflow123'),
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
        Get station numbers with recent discharge data.

        Much faster than the API version -- single query vs paginated HTTP calls.

        Args:
            months_back: Number of months to look back (default: 6)

        Returns:
            Set of station number strings with recent data
        """
        cutoff = (datetime.now() - timedelta(days=months_back * 30)).isoformat()

        query = """
            SELECT DISTINCT s.station_number
            FROM discharge_observations obs
            JOIN stations s ON obs.station_id = s.id
            WHERE obs.observed_at >= %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [cutoff])
                    result = {row[0] for row in cur.fetchall()}
        except Exception as e:
            logger.error(f"Error fetching active station numbers: {e}")
            return set()

        logger.info(
            f"Found {len(result)} active stations in last {months_back} months (DB)"
        )
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

    def get_flow_percentile_bands(self, days_back: int = 2) -> Dict[str, str]:
        """
        Fetch precomputed percentile bands directly from the DB.

        Returns:
            Dict mapping station_number -> band key (e.g. 'p26_50')
        """
        query = """
            SELECT s.station_number, fpb.band
            FROM flow_percentile_bands fpb
            JOIN stations s ON fpb.station_id = s.id
            WHERE fpb.observation_date >= CURRENT_DATE - (%s * INTERVAL '1 day')
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [days_back])
                    rows = cur.fetchall()
            bands = {row[0]: row[1] for row in rows}
            logger.info(f"Fetched percentile bands for {len(bands)} stations from DB")
            return bands
        except Exception as e:
            logger.error(f"Error fetching percentile bands: {e}")
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
