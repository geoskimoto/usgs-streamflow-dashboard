"""Local SQLite cache manager for DataOps data."""

import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path


class CacheManager:
    """Manages local SQLite cache for performance and offline mode."""
    
    def __init__(self, db_path: str = 'data/dataops_cache.db', ttl: int = 300):
        """
        Initialize cache manager.
        
        Args:
            db_path: Path to cache database
            ttl: Cache time-to-live in seconds (default 300 = 5 minutes)
        """
        self.db_path = db_path
        self.ttl = ttl
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self):
        """Initialize cache database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Stations cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_stations (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Discharge data cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_discharge (
                station_number TEXT,
                start_date TEXT,
                end_date TEXT,
                data_type TEXT,
                data TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (station_number, start_date, end_date, data_type)
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_discharge_station 
            ON cache_discharge(station_number)
        """)
        
        conn.commit()
        conn.close()
    
    def _is_expired(self, cached_at: str) -> bool:
        """Check if cached data is expired."""
        cached_time = datetime.fromisoformat(cached_at)
        return datetime.now() - cached_time > timedelta(seconds=self.ttl)
    
    def get_stations(
        self, 
        state: Optional[str] = None, 
        agency: str = 'USGS'
    ) -> Optional[pd.DataFrame]:
        """
        Get cached stations.
        
        Args:
            state: State code filter
            agency: Agency filter
            
        Returns:
            DataFrame or None if not cached/expired
        """
        cache_key = f"stations:{agency}:{state or 'all'}"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT data, cached_at FROM cache_stations WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            data_json, cached_at = row
            
            # Check if expired
            if self._is_expired(cached_at):
                return None
            
            # Deserialize
            data = json.loads(data_json)
            return pd.DataFrame(data)
            
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    
    def set_stations(
        self, 
        df: pd.DataFrame, 
        state: Optional[str] = None, 
        agency: str = 'USGS'
    ):
        """
        Cache stations data.
        
        Args:
            df: DataFrame with station data
            state: State code filter
            agency: Agency filter
        """
        cache_key = f"stations:{agency}:{state or 'all'}"
        data_json = df.to_json(orient='records')
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO cache_stations (cache_key, data, cached_at) 
                VALUES (?, ?, ?)
                """,
                (cache_key, data_json, datetime.now().isoformat())
            )
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def get_discharge_data(
        self,
        station_number: str,
        start_date: str,
        end_date: str,
        data_type: str = 'daily_mean'
    ) -> Optional[pd.DataFrame]:
        """
        Get cached discharge data.
        
        Args:
            station_number: Station identifier
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            data_type: Type of data
            
        Returns:
            DataFrame or None if not cached/expired
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT data, cached_at 
                FROM cache_discharge 
                WHERE station_number = ? 
                  AND start_date = ? 
                  AND end_date = ? 
                  AND data_type = ?
                """,
                (station_number, start_date, end_date, data_type)
            )
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            data_json, cached_at = row
            
            # Check if expired
            if self._is_expired(cached_at):
                return None
            
            # Deserialize
            data = json.loads(data_json)
            df = pd.DataFrame(data)
            
            if not df.empty and 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            
            return df
            
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    
    def set_discharge_data(
        self,
        df: pd.DataFrame,
        station_number: str,
        start_date: str,
        end_date: str,
        data_type: str = 'daily_mean'
    ):
        """
        Cache discharge data.
        
        Args:
            df: DataFrame with discharge data
            station_number: Station identifier
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            data_type: Type of data
        """
        # Convert dates to strings for JSON
        df_copy = df.copy()
        if 'date' in df_copy.columns:
            df_copy['date'] = df_copy['date'].astype(str)
        
        data_json = df_copy.to_json(orient='records')
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO cache_discharge 
                (station_number, start_date, end_date, data_type, data, cached_at) 
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (station_number, start_date, end_date, data_type, data_json, 
                 datetime.now().isoformat())
            )
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def clear_cache(self):
        """Clear all cached data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM cache_stations")
            cursor.execute("DELETE FROM cache_discharge")
            
            conn.commit()
            conn.close()
            
            print("✅ Cache cleared")
            
        except Exception as e:
            print(f"Cache clear error: {e}")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM cache_stations")
            stations_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM cache_discharge")
            discharge_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'stations_cached': stations_count,
                'discharge_cached': discharge_count,
                'cache_path': self.db_path,
                'ttl_seconds': self.ttl
            }
            
        except Exception as e:
            return {'error': str(e)}
