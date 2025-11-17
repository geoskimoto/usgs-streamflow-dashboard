"""
JSON-Based Configuration Manager with In-Memory Caching

This module manages station configurations and schedules by reading directly
from JSON files with in-memory caching for performance. No database tables
needed for configuration management.

Features:
- Loads configurations from config/default_configurations.json
- Loads schedules from config/default_schedules.json  
- In-memory caching with configurable TTL (default 5 minutes)
- Automatic cache invalidation and reload
- Station filtering and selection based on config rules
- Collection logging to database

Usage:
    from json_config_manager import JSONConfigManager
    
    manager = JSONConfigManager()
    configs = manager.get_configurations()
    stations = manager.get_stations_for_configuration('Pacific Northwest Full')
    schedules = manager.get_schedules()
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class JSONConfigManager:
    """Manages configurations and schedules from JSON files with caching."""
    
    def __init__(self, db_path: str = "data/usgs_data.db", cache_ttl: int = 300):
        """
        Initialize the JSON config manager.
        
        Args:
            db_path: Path to database (for stations and logging only)
            cache_ttl: Cache time-to-live in seconds (default 300 = 5 minutes)
        """
        self.db_path = Path(db_path)
        self.cache_ttl = cache_ttl
        
        # Config file paths
        self.config_dir = Path('config')
        self.configurations_file = self.config_dir / 'default_configurations.json'
        self.schedules_file = self.config_dir / 'default_schedules.json'
        self.settings_file = self.config_dir / 'system_settings.json'
        
        # In-memory caches
        self._configs_cache = None
        self._configs_cache_time = None
        self._schedules_cache = None
        self._schedules_cache_time = None
        self._settings_cache = None
        self._settings_cache_time = None
        
        self.logger = logging.getLogger(__name__)
    
    def _is_cache_valid(self, cache_time: Optional[float]) -> bool:
        """Check if cache is still valid based on TTL."""
        if cache_time is None:
            return False
        return (time.time() - cache_time) < self.cache_ttl
    
    def _load_json_file(self, filepath: Path) -> Dict:
        """Load and parse a JSON file."""
        if not filepath.exists():
            self.logger.warning(f"Config file not found: {filepath}")
            return {}
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def get_configurations(self, force_reload: bool = False) -> List[Dict]:
        """
        Get all station configurations from JSON.
        
        Args:
            force_reload: Force cache refresh
            
        Returns:
            List of configuration dictionaries
        """
        if not force_reload and self._is_cache_valid(self._configs_cache_time):
            return self._configs_cache
        
        # Load from JSON
        data = self._load_json_file(self.configurations_file)
        configs = data.get('configurations', [])
        
        # Normalize field names (handle both 'name' and 'config_name')
        for config in configs:
            if 'name' in config and 'config_name' not in config:
                config['config_name'] = config['name']
        
        # Cache the result
        self._configs_cache = configs
        self._configs_cache_time = time.time()
        
        self.logger.debug(f"Loaded {len(configs)} configurations from JSON")
        return configs
    
    def get_configuration_by_name(self, config_name: str) -> Optional[Dict]:
        """Get a specific configuration by name."""
        configs = self.get_configurations()
        for config in configs:
            if config.get('config_name') == config_name or config.get('name') == config_name:
                return config
        return None
    
    def get_default_configuration(self) -> Optional[Dict]:
        """Get the default configuration."""
        configs = self.get_configurations()
        for config in configs:
            if config.get('is_default', False):
                return config
        # Return first config if no default specified
        return configs[0] if configs else None
    
    def get_schedules(self, force_reload: bool = False) -> List[Dict]:
        """
        Get all collection schedules from JSON.
        
        Args:
            force_reload: Force cache refresh
            
        Returns:
            List of schedule dictionaries
        """
        if not force_reload and self._is_cache_valid(self._schedules_cache_time):
            return self._schedules_cache
        
        # Load from JSON
        data = self._load_json_file(self.schedules_file)
        schedules = data.get('schedules', [])
        
        # Normalize field names
        for schedule in schedules:
            if 'name' in schedule and 'schedule_name' not in schedule:
                schedule['schedule_name'] = schedule['name']
            if 'configuration' in schedule and 'config_name' not in schedule:
                schedule['config_name'] = schedule['configuration']
        
        # Cache the result
        self._schedules_cache = schedules
        self._schedules_cache_time = time.time()
        
        self.logger.debug(f"Loaded {len(schedules)} schedules from JSON")
        return schedules
    
    def get_schedules_for_configuration(self, config_name: str) -> List[Dict]:
        """Get all schedules for a specific configuration."""
        all_schedules = self.get_schedules()
        return [s for s in all_schedules if s.get('config_name') == config_name or s.get('configuration') == config_name]
    
    def get_settings(self, force_reload: bool = False) -> Dict:
        """
        Get system settings from JSON.
        
        Args:
            force_reload: Force cache refresh
            
        Returns:
            Settings dictionary
        """
        if not force_reload and self._is_cache_valid(self._settings_cache_time):
            return self._settings_cache
        
        # Load from JSON
        settings = self._load_json_file(self.settings_file)
        
        # Cache the result
        self._settings_cache = settings
        self._settings_cache_time = time.time()
        
        self.logger.debug(f"Loaded system settings from JSON")
        return settings
    
    def get_stations_for_configuration(self, config_name: str) -> List[Dict]:
        """
        Get all stations for a specific configuration.
        
        Reads station selection rules from config JSON and queries database.
        
        Args:
            config_name: Name of configuration
            
        Returns:
            List of station dictionaries
        """
        config = self.get_configuration_by_name(config_name)
        if not config:
            self.logger.error(f"Configuration '{config_name}' not found")
            return []
        
        # Get station source rules
        station_source = config.get('station_source', {})
        source_type = station_source.get('type', 'csv')
        
        # Query database based on source type
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        stations = []
        
        try:
            if source_type == 'csv':
                # Get stations from CSV file specification
                csv_path = station_source.get('path', '')
                # For now, just get all stations from the source_dataset
                # This assumes CSV has been imported to stations table
                if 'pnw' in csv_path.lower():
                    cursor.execute("SELECT * FROM stations WHERE source_dataset = 'HADS_PNW' AND is_active = 1")
                elif 'columbia' in csv_path.lower():
                    cursor.execute("SELECT * FROM stations WHERE source_dataset = 'HADS_Columbia' AND is_active = 1")
                else:
                    cursor.execute("SELECT * FROM stations WHERE is_active = 1")
            
            elif source_type == 'filter':
                # Build query from filters
                filters = station_source.get('filters', [])
                where_clauses = []
                params = []
                
                for filter_item in filters:
                    field = filter_item.get('field')
                    operator = filter_item.get('operator')
                    value = filter_item.get('value')
                    
                    if operator == 'in' and isinstance(value, list):
                        placeholders = ','.join(['?'] * len(value))
                        where_clauses.append(f"{field} IN ({placeholders})")
                        params.extend(value)
                    elif operator == '=':
                        where_clauses.append(f"{field} = ?")
                        params.append(value)
                
                where_clauses.append("is_active = 1")
                query = f"SELECT * FROM stations WHERE {' AND '.join(where_clauses)}"
                cursor.execute(query, params)
            
            else:
                # Default: get all active stations
                cursor.execute("SELECT * FROM stations WHERE is_active = 1")
            
            stations = [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            self.logger.error(f"Error getting stations for config '{config_name}': {e}")
        finally:
            conn.close()
        
        self.logger.info(f"Retrieved {len(stations)} stations for configuration '{config_name}'")
        return stations
    
    def get_system_health(self) -> Dict:
        """Get system health metrics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Active stations
            cursor.execute("SELECT COUNT(*) FROM stations WHERE is_active = 1")
            active_stations = cursor.fetchone()[0]
            
            # Active configurations (from JSON)
            configs = self.get_configurations()
            active_configs = len([c for c in configs if c.get('is_active', True)])
            
            # Recent collection success rate (last 24 hours)
            cursor.execute("""
            SELECT 
                COUNT(*) as recent_runs,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_runs
            FROM collection_logs
            WHERE start_time >= datetime('now', '-24 hours')
            """)
            
            recent_activity = cursor.fetchone()
            recent_runs, successful_runs = recent_activity[0], recent_activity[1]
            success_rate = (successful_runs / recent_runs * 100) if recent_runs > 0 else 0
            
            # Currently running collections
            cursor.execute("SELECT COUNT(*) FROM collection_logs WHERE status = 'running'")
            running_collections = cursor.fetchone()[0]
            
            return {
                'active_configurations': active_configs,
                'active_stations': active_stations,
                'recent_success_rate': round(success_rate, 1),
                'recent_runs_24h': recent_runs,
                'currently_running': running_collections,
                'last_updated': datetime.now().isoformat()
            }
        finally:
            conn.close()
    
    def get_stations_by_criteria(self, states=None, huc_codes=None, source_datasets=None, active_only=True):
        """
        Get stations filtered by various criteria.
        
        Parameters:
        -----------
        states : list, optional
            List of state codes to filter by (e.g., ['WA', 'OR'])
        huc_codes : list, optional
            List of HUC codes to filter by
        source_datasets : list, optional
            List of source datasets to filter by (e.g., ['HADS_PNW'])
        active_only : bool
            If True, only return active stations
            
        Returns:
        --------
        list
            List of station dictionaries matching the criteria
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Build WHERE clause dynamically
            where_clauses = []
            params = []
            
            if active_only:
                where_clauses.append("is_active = 1")
            
            if states:
                placeholders = ','.join('?' * len(states))
                where_clauses.append(f"state IN ({placeholders})")
                params.extend(states)
            
            if huc_codes:
                placeholders = ','.join('?' * len(huc_codes))
                where_clauses.append(f"huc_code IN ({placeholders})")
                params.extend(huc_codes)
            
            if source_datasets:
                placeholders = ','.join('?' * len(source_datasets))
                where_clauses.append(f"source_dataset IN ({placeholders})")
                params.extend(source_datasets)
            
            # Construct query
            query = "SELECT * FROM stations"
            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " ORDER BY state, station_name"
            
            cursor.execute(query, params)
            stations = [dict(row) for row in cursor.fetchall()]
            
            return stations
            
        except Exception as e:
            self.logger.error(f"Error getting stations by criteria: {e}")
            return []
        finally:
            conn.close()
    
    def start_collection_log(self, config_name: str, data_type: str, 
                           stations_attempted: int, triggered_by: str = 'system') -> int:
        """Start a new collection log entry."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            INSERT INTO collection_logs 
            (config_name, data_type, stations_attempted, start_time, status, triggered_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (config_name, data_type, stations_attempted, datetime.now().isoformat(), 'running', triggered_by))
            
            log_id = cursor.lastrowid
            conn.commit()
            return log_id
        finally:
            conn.close()
    
    def update_collection_log(self, log_id: int, stations_successful: int, 
                            stations_failed: int, status: str, error_summary: str = None):
        """Update collection log with results."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            end_time = datetime.now().isoformat()
            
            # Calculate duration
            cursor.execute("SELECT start_time FROM collection_logs WHERE id = ?", (log_id,))
            result = cursor.fetchone()
            if result:
                start_time_str = result[0]
                start_time = datetime.fromisoformat(start_time_str)
                duration = (datetime.now() - start_time).total_seconds()
            else:
                duration = 0
            
            cursor.execute("""
            UPDATE collection_logs 
            SET stations_successful = ?,
                stations_failed = ?,
                end_time = ?, 
                duration_seconds = ?, 
                status = ?, 
                error_summary = ?
            WHERE id = ?
            """, (stations_successful, stations_failed, end_time, duration, status, error_summary, log_id))
            
            conn.commit()
        finally:
            conn.close()
    
    def log_station_error(self, log_id: int, station_id: int, error_type: str, 
                         error_message: str, http_status_code: int = None):
        """Log an error for a specific station."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
            INSERT INTO station_errors 
            (log_id, station_id, error_type, error_message, http_status_code)
            VALUES (?, ?, ?, ?, ?)
            """, (log_id, station_id, error_type, error_message, http_status_code))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_recent_collection_logs(self, config_name: str = None, limit: int = 50) -> List[Dict]:
        """Get recent collection activity."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            if config_name:
                cursor.execute("""
                SELECT * FROM recent_collection_activity 
                WHERE config_name = ?
                LIMIT ?
                """, (config_name, limit))
            else:
                cursor.execute("SELECT * FROM recent_collection_activity LIMIT ?", (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def clear_cache(self):
        """Clear all caches to force reload from JSON files."""
        self._configs_cache = None
        self._configs_cache_time = None
        self._schedules_cache = None
        self._schedules_cache_time = None
        self._settings_cache = None
        self._settings_cache_time = None
        self.logger.info("All caches cleared")


# Convenience functions for backward compatibility
def get_station_list(config_name: str = None) -> List[str]:
    """Get list of site IDs for a configuration."""
    manager = JSONConfigManager()
    
    if config_name:
        config = manager.get_configuration_by_name(config_name)
        if not config:
            raise ValueError(f"Configuration '{config_name}' not found")
    else:
        config = manager.get_default_configuration()
        if not config:
            raise ValueError("No default configuration found")
        config_name = config.get('config_name') or config.get('name')
    
    stations = manager.get_stations_for_configuration(config_name)
    return [station['site_id'] for station in stations]


def get_configuration_info(config_name: str = None) -> Dict:
    """Get detailed information about a configuration."""
    manager = JSONConfigManager()
    
    if config_name:
        config = manager.get_configuration_by_name(config_name)
    else:
        config = manager.get_default_configuration()
    
    if not config:
        raise ValueError(f"Configuration '{config_name}' not found")
    
    config_name = config.get('config_name') or config.get('name')
    stations = manager.get_stations_for_configuration(config_name)
    schedules = manager.get_schedules_for_configuration(config_name)
    
    return {
        'configuration': config,
        'station_count': len(stations),
        'stations': stations,
        'schedules': schedules
    }
