"""
Station Repository

Handles all CRUD operations for the stations table.
Consolidates logic from populate_station_database.py and related files.
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any
from datetime import datetime

from .connection import DatabaseConnection


class StationRepository:
    """
    Repository for station metadata operations.
    
    Provides clean interface for station CRUD operations without
    exposing raw SQL queries to the application layer.
    """
    
    def __init__(self, db_path: str = "data/usgs_data.db"):
        """
        Initialize station repository.
        
        Parameters:
        -----------
        db_path : str
            Path to the database file
        """
        self.db = DatabaseConnection(db_path)
    
    def get_station(self, site_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single station by site_id.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
            
        Returns:
        --------
        Dict or None
            Station data dictionary or None if not found
        """
        query = "SELECT * FROM stations WHERE site_id = ?"
        result = self.db.execute_query(query, (site_id,), fetch='one', row_factory=True)
        
        if result:
            return dict(result)
        return None
    
    def get_all_stations(self, active_only: bool = False) -> pd.DataFrame:
        """
        Get all stations as a DataFrame.
        
        Parameters:
        -----------
        active_only : bool
            If True, return only active stations
            
        Returns:
        --------
        pd.DataFrame
            DataFrame of all stations
        """
        query = "SELECT * FROM stations"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY site_id"
        
        results = self.db.execute_query(query, fetch='all', row_factory=True)
        
        if results:
            return pd.DataFrame([dict(row) for row in results])
        return pd.DataFrame()
    
    def get_stations_by_state(self, state: str, active_only: bool = False) -> pd.DataFrame:
        """
        Get stations filtered by state.
        
        Parameters:
        -----------
        state : str
            Two-letter state code
        active_only : bool
            If True, return only active stations
            
        Returns:
        --------
        pd.DataFrame
            DataFrame of filtered stations
        """
        query = "SELECT * FROM stations WHERE state = ?"
        params = [state]
        
        if active_only:
            query += " AND is_active = 1"
        
        query += " ORDER BY site_id"
        
        results = self.db.execute_query(query, tuple(params), fetch='all', row_factory=True)
        
        if results:
            return pd.DataFrame([dict(row) for row in results])
        return pd.DataFrame()
    
    def get_stations_by_basin(self, basin: str, active_only: bool = False) -> pd.DataFrame:
        """
        Get stations filtered by basin.
        
        Parameters:
        -----------
        basin : str
            Basin identifier (first 4 digits of HUC code)
        active_only : bool
            If True, return only active stations
            
        Returns:
        --------
        pd.DataFrame
            DataFrame of filtered stations
        """
        query = "SELECT * FROM stations WHERE basin = ?"
        params = [basin]
        
        if active_only:
            query += " AND is_active = 1"
        
        query += " ORDER BY site_id"
        
        results = self.db.execute_query(query, tuple(params), fetch='all', row_factory=True)
        
        if results:
            return pd.DataFrame([dict(row) for row in results])
        return pd.DataFrame()
    
    def add_station(self, station_data: Dict[str, Any]) -> bool:
        """
        Add a new station to the database.
        
        Parameters:
        -----------
        station_data : Dict
            Dictionary with station fields
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        required_fields = ['site_id', 'station_name', 'state', 'latitude', 'longitude', 'source_dataset']
        
        # Verify required fields
        for field in required_fields:
            if field not in station_data:
                print(f"❌ Missing required field: {field}")
                return False
        
        try:
            # Prepare insert query
            fields = list(station_data.keys())
            placeholders = ','.join(['?' for _ in fields])
            field_names = ','.join(fields)
            
            query = f"INSERT INTO stations ({field_names}) VALUES ({placeholders})"
            values = tuple(station_data[field] for field in fields)
            
            self.db.execute_query(query, values, fetch='none')
            return True
            
        except Exception as e:
            print(f"❌ Error adding station: {e}")
            return False
    
    def update_station(self, site_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update station metadata.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        updates : Dict
            Dictionary of fields to update
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        if not updates:
            return True
        
        try:
            # Add last_updated timestamp
            updates['last_updated'] = datetime.now().isoformat()
            
            # Build UPDATE query
            set_clause = ','.join([f"{key} = ?" for key in updates.keys()])
            query = f"UPDATE stations SET {set_clause} WHERE site_id = ?"
            
            values = tuple(list(updates.values()) + [site_id])
            
            self.db.execute_query(query, values, fetch='none')
            return True
            
        except Exception as e:
            print(f"❌ Error updating station: {e}")
            return False
    
    def bulk_upsert_stations(self, stations_df: pd.DataFrame) -> int:
        """
        Insert or update multiple stations from DataFrame.
        
        Parameters:
        -----------
        stations_df : pd.DataFrame
            DataFrame with station data
            
        Returns:
        --------
        int
            Number of stations successfully upserted
        """
        count = 0
        
        for idx, row in stations_df.iterrows():
            station_data = row.to_dict()
            
            # Convert numpy/pandas types to Python native types
            station_data = self._sanitize_values(station_data)
            
            try:
                # Check if station exists
                existing = self.get_station(station_data.get('site_id'))
                
                if existing:
                    # Update existing
                    updates = {k: v for k, v in station_data.items() if k != 'site_id'}
                    if self.update_station(station_data['site_id'], updates):
                        count += 1
                else:
                    # Insert new
                    if self.add_station(station_data):
                        count += 1
                        
            except Exception as e:
                print(f"❌ Error upserting station {station_data.get('site_id')}: {e}")
                continue
        
        return count
    
    def delete_station(self, site_id: str) -> bool:
        """
        Delete a station (and all its data via CASCADE).
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            query = "DELETE FROM stations WHERE site_id = ?"
            self.db.execute_query(query, (site_id,), fetch='none')
            return True
        except Exception as e:
            print(f"❌ Error deleting station: {e}")
            return False
    
    def set_station_active(self, site_id: str, is_active: bool) -> bool:
        """
        Set station active status.
        
        Parameters:
        -----------
        site_id : str
            USGS site identifier
        is_active : bool
            Active status
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        return self.update_station(site_id, {'is_active': is_active})
    
    def get_station_count(self, active_only: bool = False) -> int:
        """
        Get total number of stations.
        
        Parameters:
        -----------
        active_only : bool
            If True, count only active stations
            
        Returns:
        --------
        int
            Number of stations
        """
        query = "SELECT COUNT(*) FROM stations"
        if active_only:
            query += " WHERE is_active = 1"
        
        result = self.db.execute_query(query, fetch='one')
        return result[0] if result else 0
    
    def search_stations(self, search_term: str, limit: int = 50) -> pd.DataFrame:
        """
        Search stations by name, site_id, or location.
        
        Parameters:
        -----------
        search_term : str
            Search term
        limit : int
            Maximum number of results
            
        Returns:
        --------
        pd.DataFrame
            DataFrame of matching stations
        """
        query = """
            SELECT * FROM stations 
            WHERE site_id LIKE ? 
               OR station_name LIKE ? 
               OR county LIKE ?
               OR basin LIKE ?
            ORDER BY site_id
            LIMIT ?
        """
        
        search_pattern = f"%{search_term}%"
        params = (search_pattern, search_pattern, search_pattern, search_pattern, limit)
        
        results = self.db.execute_query(query, params, fetch='all', row_factory=True)
        
        if results:
            return pd.DataFrame([dict(row) for row in results])
        return pd.DataFrame()
    
    def sync_filters_table(self):
        """
        Synchronize the filters table with stations table.
        For backward compatibility with legacy code.
        """
        query = """
            INSERT OR REPLACE INTO filters (
                site_id, station_name, latitude, longitude, state, county,
                drainage_area, huc_code, basin, site_type, num_water_years,
                last_data_date, is_active, color, last_updated
            )
            SELECT 
                site_id, station_name, latitude, longitude, state, county,
                drainage_area, huc_code, basin, site_type, num_water_years,
                last_data_date, is_active, color, last_updated
            FROM stations
        """
        
        try:
            self.db.execute_query(query, fetch='none')
            print(f"✅ Synchronized filters table with stations")
            return True
        except Exception as e:
            print(f"❌ Error syncing filters table: {e}")
            return False
    
    def _sanitize_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert numpy/pandas types to Python native types."""
        sanitized = {}
        
        for key, value in data.items():
            # Handle NaN/None
            if pd.isna(value) or (hasattr(value, '__class__') and 'NaTType' in str(value.__class__)):
                sanitized[key] = None
            # Handle datetime
            elif hasattr(value, 'strftime'):
                sanitized[key] = value.strftime('%Y-%m-%d')
            # Handle numpy types
            elif hasattr(value, 'item'):
                sanitized[key] = value.item()
            # Handle boolean
            elif isinstance(value, bool):
                sanitized[key] = int(value)
            else:
                sanitized[key] = value
        
        return sanitized
