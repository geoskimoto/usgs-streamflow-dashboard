"""
Configuration Repository

Handles configuration and schedule management, plus collection logging.
Consolidates logic from json_config_manager.py.
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

from .connection import DatabaseConnection


class ConfigRepository:
    """
    Repository for configuration, schedule, and logging operations.
    
    Manages:
    - Configuration loading from JSON files (with caching)
    - Schedule management
    - Collection logging
    """
    
    def __init__(self, db_path: str = "data/usgs_data.db", cache_ttl: int = 300):
        """
        Initialize config repository.
        
        Parameters:
        -----------
        db_path : str
            Path to the database file
        cache_ttl : int
            Cache time-to-live in seconds (default 300 = 5 minutes)
        """
        self.db = DatabaseConnection(db_path)
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
    
    def _is_cache_valid(self, cache_time: Optional[float]) -> bool:
        """Check if cache is still valid based on TTL."""
        if cache_time is None:
            return False
        return (time.time() - cache_time) < self.cache_ttl
    
    def _load_json_file(self, filepath: Path) -> Dict:
        """Load and parse a JSON file."""
        if not filepath.exists():
            print(f"⚠️  Config file not found: {filepath}")
            return {}
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def get_configurations(self, force_reload: bool = False) -> List[Dict]:
        """
        Get all station configurations from JSON.
        
        Parameters:
        -----------
        force_reload : bool
            Force cache refresh
            
        Returns:
        --------
        List[Dict]
            List of configuration dictionaries
        """
        if not force_reload and self._is_cache_valid(self._configs_cache_time):
            return self._configs_cache
        
        # Load from JSON
        data = self._load_json_file(self.configurations_file)
        configs = data.get('configurations', [])
        
        # Normalize field names
        for config in configs:
            if 'name' in config and 'config_name' not in config:
                config['config_name'] = config['name']
        
        # Cache the result
        self._configs_cache = configs
        self._configs_cache_time = time.time()
        
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
        return configs[0] if configs else None
    
    def get_schedules(self, force_reload: bool = False) -> List[Dict]:
        """
        Get all collection schedules from JSON.
        
        Parameters:
        -----------
        force_reload : bool
            Force cache refresh
            
        Returns:
        --------
        List[Dict]
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
        
        return schedules
    
    def get_schedule_by_name(self, schedule_name: str) -> Optional[Dict]:
        """Get a specific schedule by name."""
        schedules = self.get_schedules()
        for schedule in schedules:
            if schedule.get('schedule_name') == schedule_name or schedule.get('name') == schedule_name:
                return schedule
        return None
    
    def get_settings(self, force_reload: bool = False) -> Dict:
        """
        Get system settings from JSON.
        
        Parameters:
        -----------
        force_reload : bool
            Force cache refresh
            
        Returns:
        --------
        Dict
            System settings dictionary
        """
        if not force_reload and self._is_cache_valid(self._settings_cache_time):
            return self._settings_cache
        
        # Load from JSON
        settings = self._load_json_file(self.settings_file)
        
        # Cache the result
        self._settings_cache = settings
        self._settings_cache_time = time.time()
        
        return settings
    
    def start_collection_log(self, schedule_name: str, metadata: Optional[Dict] = None) -> int:
        """
        Create a new collection log entry.
        
        Parameters:
        -----------
        schedule_name : str
            Name of the schedule being run
        metadata : Dict, optional
            Additional metadata to store
            
        Returns:
        --------
        int
            Log ID of the new entry
        """
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            
            query = """
                INSERT INTO collection_logs 
                (schedule_name, start_time, status, metadata)
                VALUES (?, ?, 'running', ?)
            """
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (schedule_name, datetime.now().isoformat(), metadata_json))
                return cursor.lastrowid
                
        except Exception as e:
            print(f"❌ Error starting collection log: {e}")
            return -1
    
    def update_collection_log(self, log_id: int, status: str = None,
                             stations_attempted: int = None,
                             stations_successful: int = None,
                             stations_failed: int = None,
                             error_message: str = None) -> bool:
        """
        Update an existing collection log entry.
        
        Parameters:
        -----------
        log_id : int
            ID of the log entry to update
        status : str, optional
            New status ('running', 'completed', 'failed')
        stations_attempted : int, optional
            Number of stations attempted
        stations_successful : int, optional
            Number of successful stations
        stations_failed : int, optional
            Number of failed stations
        error_message : str, optional
            Error message if failed
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        try:
            updates = []
            params = []
            
            if status:
                updates.append("status = ?")
                params.append(status)
            
            if stations_attempted is not None:
                updates.append("stations_attempted = ?")
                params.append(stations_attempted)
            
            if stations_successful is not None:
                updates.append("stations_successful = ?")
                params.append(stations_successful)
            
            if stations_failed is not None:
                updates.append("stations_failed = ?")
                params.append(stations_failed)
            
            if error_message:
                updates.append("error_message = ?")
                params.append(error_message)
            
            if status in ['completed', 'failed']:
                updates.append("end_time = ?")
                params.append(datetime.now().isoformat())
            
            if not updates:
                return True
            
            params.append(log_id)
            query = f"UPDATE collection_logs SET {', '.join(updates)} WHERE id = ?"
            
            self.db.execute_query(query, tuple(params), fetch='none')
            return True
            
        except Exception as e:
            print(f"❌ Error updating collection log: {e}")
            return False
    
    def complete_collection_log(self, log_id: int, stations_attempted: int,
                               stations_successful: int, stations_failed: int) -> bool:
        """
        Mark a collection log as completed.
        
        Parameters:
        -----------
        log_id : int
            ID of the log entry
        stations_attempted : int
            Total stations attempted
        stations_successful : int
            Successful stations
        stations_failed : int
            Failed stations
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        return self.update_collection_log(
            log_id,
            status='completed',
            stations_attempted=stations_attempted,
            stations_successful=stations_successful,
            stations_failed=stations_failed
        )
    
    def fail_collection_log(self, log_id: int, error_message: str) -> bool:
        """
        Mark a collection log as failed.
        
        Parameters:
        -----------
        log_id : int
            ID of the log entry
        error_message : str
            Error message
            
        Returns:
        --------
        bool
            True if successful, False otherwise
        """
        return self.update_collection_log(log_id, status='failed', error_message=error_message)
    
    def get_recent_collection_logs(self, limit: int = 50) -> List[Dict]:
        """
        Get recent collection logs.
        
        Parameters:
        -----------
        limit : int
            Maximum number of logs to return
            
        Returns:
        --------
        List[Dict]
            List of log dictionaries
        """
        try:
            query = """
                SELECT * FROM collection_logs 
                ORDER BY start_time DESC 
                LIMIT ?
            """
            
            results = self.db.execute_query(query, (limit,), fetch='all', row_factory=True)
            
            if results:
                return [dict(row) for row in results]
            return []
            
        except Exception as e:
            print(f"❌ Error getting collection logs: {e}")
            return []
    
    def clear_cache(self):
        """Clear all in-memory caches."""
        self._configs_cache = None
        self._configs_cache_time = None
        self._schedules_cache = None
        self._schedules_cache_time = None
        self._settings_cache = None
        self._settings_cache_time = None
        print("✅ Configuration cache cleared")
