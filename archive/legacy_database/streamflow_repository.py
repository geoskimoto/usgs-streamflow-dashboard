"""
Streamflow Data Repository

Handles all CRUD operations for the streamflow_data table (daily historical data).
"""

import pandas as pd
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .connection import DatabaseConnection


class StreamflowRepository:
    """
    Repository for daily streamflow data operations.
    
    Manages caching and retrieval of historical daily discharge data.
    """
    
    def __init__(self, db_path: str = "data/usgs_data.db", cache_duration_seconds: int = 300):
        """
        Initialize streamflow repository.
        
        Parameters:
        -----------
        db_path : str
            Path to the database file
        cache_duration_seconds : int
            How long cached data remains valid (default 5 minutes)
        """
        self.db = DatabaseConnection(db_path)
        self.cache_duration = cache_duration_seconds
    
    def get_streamflow_data(self, site_id: str, start_date: str, 
                           end_date: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Get streamflow data for a site and date range.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        start_date : str
            Start date (YYYY-MM-DD)
        end_date : str
            End date (YYYY-MM-DD)
        use_cache : bool
            Whether to use cached data if available
            
        Returns:
        --------
        pd.DataFrame or None
            DataFrame with datetime index and discharge columns
        """
        if not use_cache:
            return None
        
        try:
            query = """
                SELECT data_json, last_updated 
                FROM streamflow_data 
                WHERE site_id = ? AND start_date = ? AND end_date = ?
            """
            
            result = self.db.execute_query(query, (site_id, start_date, end_date), fetch='one')
            
            if not result:
                return None
            
            data_json, last_updated = result
            
            # Check if cache is still valid
            if not self._is_cache_valid(last_updated):
                return None
            
            # Parse JSON back to DataFrame
            data = json.loads(data_json)
            df = pd.DataFrame(data)
            
            # Reconstruct datetime index
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'])
                # Remove timezone to avoid mixing issues
                if df['datetime'].dt.tz is not None:
                    df['datetime'] = df['datetime'].dt.tz_localize(None)
                df = df.set_index('datetime')
                df.index.name = 'datetime'
            
            return df
            
        except Exception as e:
            print(f"⚠️  Error loading cached streamflow data for {site_id}: {e}")
            return None
    
    def save_streamflow_data(self, site_id: str, df: pd.DataFrame, 
                            start_date: str, end_date: str) -> bool:
        """
        Save streamflow data to cache.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        df : pd.DataFrame
            DataFrame with streamflow data
        start_date : str
            Start date (YYYY-MM-DD)
        end_date : str
            End date (YYYY-MM-DD)
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            # Prepare DataFrame for JSON serialization
            df_copy = df.copy()
            
            # Reset index to make datetime a column
            if isinstance(df_copy.index, pd.DatetimeIndex):
                df_copy = df_copy.reset_index()
                if 'datetime' in df_copy.columns:
                    df_copy['datetime'] = df_copy['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            elif 'datetime' in df_copy.columns:
                df_copy['datetime'] = df_copy['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            data_json = df_copy.to_json(orient='records')
            
            # Insert or replace
            query = """
                INSERT OR REPLACE INTO streamflow_data 
                (site_id, data_json, start_date, end_date, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """
            
            self.db.execute_query(
                query, 
                (site_id, data_json, start_date, end_date, datetime.now().isoformat()),
                fetch='none'
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Error caching streamflow data for {site_id}: {e}")
            return False
    
    def delete_streamflow_data(self, site_id: str, start_date: Optional[str] = None,
                              end_date: Optional[str] = None) -> bool:
        """
        Delete streamflow data for a site.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        start_date : str, optional
            If provided, delete only specific date range
        end_date : str, optional
            End date for deletion
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            if start_date and end_date:
                query = "DELETE FROM streamflow_data WHERE site_id = ? AND start_date = ? AND end_date = ?"
                params = (site_id, start_date, end_date)
            else:
                query = "DELETE FROM streamflow_data WHERE site_id = ?"
                params = (site_id,)
            
            self.db.execute_query(query, params, fetch='none')
            return True
            
        except Exception as e:
            print(f"❌ Error deleting streamflow data: {e}")
            return False
    
    def clear_expired_cache(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
        --------
        int
            Number of entries removed
        """
        try:
            cutoff_time = (datetime.now() - timedelta(seconds=self.cache_duration)).isoformat()
            
            # Count first
            count_query = "SELECT COUNT(*) FROM streamflow_data WHERE last_updated < ?"
            result = self.db.execute_query(count_query, (cutoff_time,), fetch='one')
            count = result[0] if result else 0
            
            # Delete
            if count > 0:
                delete_query = "DELETE FROM streamflow_data WHERE last_updated < ?"
                self.db.execute_query(delete_query, (cutoff_time,), fetch='none')
            
            return count
            
        except Exception as e:
            print(f"❌ Error clearing expired cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about cached streamflow data.
        
        Returns:
        --------
        Dict
            Statistics including total entries, size, oldest/newest
        """
        try:
            stats = {}
            
            # Total entries
            count_query = "SELECT COUNT(*) FROM streamflow_data"
            result = self.db.execute_query(count_query, fetch='one')
            stats['total_entries'] = result[0] if result else 0
            
            # Unique sites
            sites_query = "SELECT COUNT(DISTINCT site_id) FROM streamflow_data"
            result = self.db.execute_query(sites_query, fetch='one')
            stats['unique_sites'] = result[0] if result else 0
            
            # Date range
            range_query = "SELECT MIN(last_updated), MAX(last_updated) FROM streamflow_data"
            result = self.db.execute_query(range_query, fetch='one')
            if result:
                stats['oldest_entry'] = result[0]
                stats['newest_entry'] = result[1]
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting cache stats: {e}")
            return {}
    
    def _is_cache_valid(self, last_updated: str) -> bool:
        """Check if cached data is still valid based on timestamp."""
        try:
            last_update_time = datetime.fromisoformat(last_updated)
            age_seconds = (datetime.now() - last_update_time).total_seconds()
            return age_seconds < self.cache_duration
        except:
            return False
