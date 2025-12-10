"""
Realtime Discharge Repository

Handles all CRUD operations for the realtime_discharge table (15-minute interval data).
"""

import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .connection import DatabaseConnection


class RealtimeRepository:
    """
    Repository for realtime discharge data operations.
    
    Manages 15-minute interval discharge data from USGS IV service.
    """
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """
        Initialize realtime repository.
        
        Parameters:
        -----------
        db_path : str
            Path to the database file
        """
        self.db = DatabaseConnection(db_path)
    
    def get_realtime_data(self, site_id: str, start_datetime: Optional[str] = None,
                         end_datetime: Optional[str] = None, hours_back: int = 48) -> pd.DataFrame:
        """
        Get realtime discharge data for a site.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        start_datetime : str, optional
            Start datetime (ISO format)
        end_datetime : str, optional
            End datetime (ISO format)
        hours_back : int
            If start/end not specified, get last N hours
            
        Returns:
        --------
        pd.DataFrame
            DataFrame with datetime index and discharge data
        """
        try:
            if start_datetime and end_datetime:
                query = """
                    SELECT datetime_utc, discharge_cfs, data_quality
                    FROM realtime_discharge
                    WHERE site_id = ? AND datetime_utc BETWEEN ? AND ?
                    ORDER BY datetime_utc
                """
                params = (site_id, start_datetime, end_datetime)
            else:
                # Get last N hours
                cutoff = (datetime.now() - timedelta(hours=hours_back)).isoformat()
                query = """
                    SELECT datetime_utc, discharge_cfs, data_quality
                    FROM realtime_discharge
                    WHERE site_id = ? AND datetime_utc >= ?
                    ORDER BY datetime_utc
                """
                params = (site_id, cutoff)
            
            results = self.db.execute_query(query, params, fetch='all', row_factory=True)
            
            if not results:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame([dict(row) for row in results])
            df['datetime_utc'] = pd.to_datetime(df['datetime_utc'])
            df = df.set_index('datetime_utc')
            
            return df
            
        except Exception as e:
            print(f"⚠️  Error loading realtime data for {site_id}: {e}")
            return pd.DataFrame()
    
    def add_realtime_data(self, site_id: str, datetime_utc: str, 
                         discharge_cfs: float, data_quality: str = 'P') -> bool:
        """
        Add a single realtime data point.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        datetime_utc : str
            Datetime in UTC (ISO format)
        discharge_cfs : float
            Discharge in cubic feet per second
        data_quality : str
            USGS quality code (A=Approved, P=Provisional, etc.)
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            query = """
                INSERT OR REPLACE INTO realtime_discharge
                (site_id, datetime_utc, discharge_cfs, data_quality, created_at)
                VALUES (?, ?, ?, ?, ?)
            """
            
            self.db.execute_query(
                query,
                (site_id, datetime_utc, discharge_cfs, data_quality, datetime.now().isoformat()),
                fetch='none'
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Error adding realtime data: {e}")
            return False
    
    def bulk_add_realtime_data(self, df: pd.DataFrame) -> int:
        """
        Add multiple realtime data points from DataFrame.
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame with columns: site_id, datetime_utc, discharge_cfs, data_quality
            
        Returns:
        --------
        int
            Number of records successfully added
        """
        if df.empty:
            return 0
        
        try:
            # Prepare data for bulk insert
            records = []
            created_at = datetime.now().isoformat()
            
            for idx, row in df.iterrows():
                records.append((
                    row.get('site_id'),
                    row.get('datetime_utc'),
                    row.get('discharge_cfs'),
                    row.get('data_quality', 'P'),
                    created_at
                ))
            
            query = """
                INSERT OR REPLACE INTO realtime_discharge
                (site_id, datetime_utc, discharge_cfs, data_quality, created_at)
                VALUES (?, ?, ?, ?, ?)
            """
            
            self.db.execute_many(query, records)
            
            return len(records)
            
        except Exception as e:
            print(f"❌ Error bulk adding realtime data: {e}")
            return 0
    
    def delete_realtime_data(self, site_id: str, before_datetime: Optional[str] = None) -> int:
        """
        Delete realtime data for a site.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        before_datetime : str, optional
            If provided, delete only data before this datetime
            
        Returns:
        --------
        int
            Number of records deleted
        """
        try:
            if before_datetime:
                count_query = """
                    SELECT COUNT(*) FROM realtime_discharge 
                    WHERE site_id = ? AND datetime_utc < ?
                """
                result = self.db.execute_query(count_query, (site_id, before_datetime), fetch='one')
                count = result[0] if result else 0
                
                delete_query = """
                    DELETE FROM realtime_discharge 
                    WHERE site_id = ? AND datetime_utc < ?
                """
                self.db.execute_query(delete_query, (site_id, before_datetime), fetch='none')
            else:
                count_query = "SELECT COUNT(*) FROM realtime_discharge WHERE site_id = ?"
                result = self.db.execute_query(count_query, (site_id,), fetch='one')
                count = result[0] if result else 0
                
                delete_query = "DELETE FROM realtime_discharge WHERE site_id = ?"
                self.db.execute_query(delete_query, (site_id,), fetch='none')
            
            return count
            
        except Exception as e:
            print(f"❌ Error deleting realtime data: {e}")
            return 0
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """
        Remove realtime data older than specified days.
        
        Parameters:
        -----------
        days_to_keep : int
            Number of days of data to keep (default 30)
            
        Returns:
        --------
        int
            Number of records deleted
        """
        try:
            cutoff = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            
            # Count first
            count_query = "SELECT COUNT(*) FROM realtime_discharge WHERE datetime_utc < ?"
            result = self.db.execute_query(count_query, (cutoff,), fetch='one')
            count = result[0] if result else 0
            
            # Delete
            if count > 0:
                delete_query = "DELETE FROM realtime_discharge WHERE datetime_utc < ?"
                self.db.execute_query(delete_query, (cutoff,), fetch='none')
                print(f"🧹 Cleaned up {count} old realtime records (older than {days_to_keep} days)")
            
            return count
            
        except Exception as e:
            print(f"❌ Error cleaning up old data: {e}")
            return 0
    
    def get_latest_datetime(self, site_id: str) -> Optional[str]:
        """
        Get the most recent datetime for a site's realtime data.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
            
        Returns:
        --------
        str or None
            Latest datetime (ISO format) or None if no data
        """
        try:
            query = """
                SELECT MAX(datetime_utc) 
                FROM realtime_discharge 
                WHERE site_id = ?
            """
            
            result = self.db.execute_query(query, (site_id,), fetch='one')
            return result[0] if result and result[0] else None
            
        except Exception as e:
            print(f"⚠️  Error getting latest datetime for {site_id}: {e}")
            return None
    
    def get_realtime_stats(self) -> Dict[str, Any]:
        """
        Get statistics about realtime data.
        
        Returns:
        --------
        Dict
            Statistics including total records, sites with data, date ranges
        """
        try:
            stats = {}
            
            # Total records
            count_query = "SELECT COUNT(*) FROM realtime_discharge"
            result = self.db.execute_query(count_query, fetch='one')
            stats['total_records'] = result[0] if result else 0
            
            # Unique sites
            sites_query = "SELECT COUNT(DISTINCT site_id) FROM realtime_discharge"
            result = self.db.execute_query(sites_query, fetch='one')
            stats['unique_sites'] = result[0] if result else 0
            
            # Date range
            range_query = "SELECT MIN(datetime_utc), MAX(datetime_utc) FROM realtime_discharge"
            result = self.db.execute_query(range_query, fetch='one')
            if result:
                stats['oldest_record'] = result[0]
                stats['newest_record'] = result[1]
            
            # Records by quality
            quality_query = """
                SELECT data_quality, COUNT(*) 
                FROM realtime_discharge 
                GROUP BY data_quality
            """
            results = self.db.execute_query(quality_query, fetch='all')
            stats['by_quality'] = {row[0]: row[1] for row in results} if results else {}
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting realtime stats: {e}")
            return {}
    
    def get_sites_with_realtime_data(self) -> List[str]:
        """
        Get list of site IDs that have realtime data.
        
        Returns:
        --------
        List[str]
            List of site IDs
        """
        try:
            query = "SELECT DISTINCT site_id FROM realtime_discharge ORDER BY site_id"
            results = self.db.execute_query(query, fetch='all')
            return [row[0] for row in results] if results else []
        except Exception as e:
            print(f"❌ Error getting sites with realtime data: {e}")
            return []
