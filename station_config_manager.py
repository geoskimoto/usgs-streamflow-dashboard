"""
Database manager for configurable USGS station data collection system.

This module provides a high-level interface for managing station configurations,
collection schedules, and operational monitoring in the USGS streamflow system.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging


class StationConfigurationManager:
    """Manages station configurations and collection operations."""
    
    def __init__(self, db_path="data/station_config.db"):
        """Initialize with database path."""
        self.db_path = Path(db_path)
        self.connection = None
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """Create database connection with foreign key support."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Configuration database not found: {self.db_path}")
        
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.row_factory = sqlite3.Row  # Enable column access by name
        return self.connection
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # Configuration Management
    def get_configurations(self, active_only=True) -> List[Dict]:
        """Get all station configurations."""
        cursor = self.connection.cursor()
        
        query = "SELECT * FROM configuration_summary"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY config_name"
        
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_configuration_by_name(self, config_name: str) -> Optional[Dict]:
        """Get configuration by name."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT * FROM station_configurations 
        WHERE config_name = ?
        """, (config_name,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_default_configuration(self) -> Optional[Dict]:
        """Get the default configuration."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT * FROM station_configurations 
        WHERE is_default = 1 AND is_active = 1
        LIMIT 1
        """)
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_configuration(self, name: str, description: str, station_ids: List[int], 
                           is_default: bool = False) -> int:
        """Create a new station configuration."""
        cursor = self.connection.cursor()
        
        try:
            # Insert configuration
            cursor.execute("""
            INSERT INTO station_configurations 
            (config_name, description, station_count, is_default, created_by)
            VALUES (?, ?, ?, ?, ?)
            """, (name, description, len(station_ids), is_default, 'admin'))
            
            config_id = cursor.lastrowid
            
            # Add station mappings
            for i, station_id in enumerate(station_ids, 1):
                cursor.execute("""
                INSERT INTO configuration_stations (config_id, station_id, priority)
                VALUES (?, ?, ?)
                """, (config_id, station_id, i))
            
            self.connection.commit()
            self.logger.info(f"Created configuration '{name}' with {len(station_ids)} stations")
            return config_id
            
        except sqlite3.IntegrityError as e:
            self.connection.rollback()
            self.logger.error(f"Error creating configuration '{name}': {e}")
            raise
    
    # Station Management
    def get_stations_for_configuration(self, config_id: int) -> List[Dict]:
        """Get all stations for a specific configuration."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT sl.*, cs.priority
        FROM station_lists sl
        JOIN configuration_stations cs ON sl.id = cs.station_id
        WHERE cs.config_id = ? AND sl.is_active = 1
        ORDER BY cs.priority, sl.usgs_id
        """, (config_id,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stations_by_criteria(self, states: List[str] = None, 
                                huc_codes: List[str] = None,
                                source_datasets: List[str] = None,
                                active_only: bool = True) -> List[Dict]:
        """Get stations matching specified criteria."""
        cursor = self.connection.cursor()
        
        conditions = []
        params = []
        
        if active_only:
            conditions.append("is_active = 1")
        
        if states:
            placeholders = ','.join(['?'] * len(states))
            conditions.append(f"state IN ({placeholders})")
            params.extend(states)
        
        if huc_codes:
            huc_conditions = []
            for huc in huc_codes:
                huc_conditions.append("huc_code LIKE ?")
                params.append(f"{huc}%")
            conditions.append(f"({' OR '.join(huc_conditions)})")
        
        if source_datasets:
            placeholders = ','.join(['?'] * len(source_datasets))
            conditions.append(f"source_dataset IN ({placeholders})")
            params.extend(source_datasets)
        
        query = "SELECT * FROM station_lists"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY state, usgs_id"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_station_by_usgs_id(self, usgs_id: str) -> Optional[Dict]:
        """Get station by USGS ID."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM station_lists WHERE usgs_id = ?", (usgs_id,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # Schedule Management
    def get_schedules_for_configuration(self, config_id: int, enabled_only: bool = True) -> List[Dict]:
        """Get all schedules for a configuration."""
        cursor = self.connection.cursor()
        
        query = """
        SELECT us.*, sc.config_name
        FROM update_schedules us
        JOIN station_configurations sc ON us.config_id = sc.id
        WHERE us.config_id = ?
        """
        params = [config_id]
        
        if enabled_only:
            query += " AND us.is_enabled = 1"
        
        query += " ORDER BY us.data_type, us.schedule_name"
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_next_scheduled_runs(self, limit: int = 10) -> List[Dict]:
        """Get upcoming scheduled runs."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT us.*, sc.config_name
        FROM update_schedules us
        JOIN station_configurations sc ON us.config_id = sc.id
        WHERE us.is_enabled = 1 AND us.next_run IS NOT NULL
        ORDER BY us.next_run
        LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_schedule_run_time(self, schedule_id: int, last_run: datetime, next_run: datetime = None):
        """Update schedule run times."""
        cursor = self.connection.cursor()
        cursor.execute("""
        UPDATE update_schedules 
        SET last_run = ?, next_run = ?, run_count = run_count + 1
        WHERE id = ?
        """, (last_run, next_run, schedule_id))
        
        self.connection.commit()
    
    # Collection Logging
    def start_collection_log(self, config_id: int, data_type: str, 
                           stations_attempted: int, triggered_by: str = 'system') -> int:
        """Start a new collection log entry."""
        cursor = self.connection.cursor()
        cursor.execute("""
        INSERT INTO data_collection_logs 
        (config_id, data_type, stations_attempted, start_time, status, triggered_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (config_id, data_type, stations_attempted, datetime.now(), 'running', triggered_by))
        
        log_id = cursor.lastrowid
        self.connection.commit()
        return log_id
    
    def update_collection_log(self, log_id: int, stations_successful: int, 
                            stations_failed: int, status: str, error_summary: str = None):
        """Update collection log with results."""
        cursor = self.connection.cursor()
        end_time = datetime.now()
        
        # Calculate duration
        cursor.execute("SELECT start_time FROM data_collection_logs WHERE id = ?", (log_id,))
        start_time_str = cursor.fetchone()[0]
        start_time = datetime.fromisoformat(start_time_str)
        duration = int((end_time - start_time).total_seconds())
        
        cursor.execute("""
        UPDATE data_collection_logs 
        SET stations_successful = ?, stations_failed = ?, 
            end_time = ?, duration_seconds = ?, status = ?, error_summary = ?
        WHERE id = ?
        """, (stations_successful, stations_failed, end_time, duration, status, error_summary, log_id))
        
        self.connection.commit()
    
    def log_station_error(self, log_id: int, station_id: int, error_type: str, 
                         error_message: str, http_status_code: int = None):
        """Log an error for a specific station."""
        cursor = self.connection.cursor()
        cursor.execute("""
        INSERT INTO station_collection_errors 
        (log_id, station_id, error_type, error_message, http_status_code)
        VALUES (?, ?, ?, ?, ?)
        """, (log_id, station_id, error_type, error_message, http_status_code))
        
        self.connection.commit()
    
    def get_recent_collection_logs(self, config_id: int = None, limit: int = 50) -> List[Dict]:
        """Get recent collection activity."""
        cursor = self.connection.cursor()
        
        if config_id:
            cursor.execute("""
            SELECT * FROM recent_collection_activity 
            WHERE config_name = (SELECT config_name FROM station_configurations WHERE id = ?)
            LIMIT ?
            """, (config_id, limit))
        else:
            cursor.execute("SELECT * FROM recent_collection_activity LIMIT ?", (limit,))
        
        return [dict(row) for row in cursor.fetchall()]
    
    # Statistics and Monitoring
    def get_collection_statistics(self, config_id: int = None, 
                                days_back: int = 7) -> Dict:
        """Get collection statistics for monitoring."""
        cursor = self.connection.cursor()
        
        since_date = datetime.now() - timedelta(days=days_back)
        
        if config_id:
            config_condition = "AND config_id = ?"
            params = [since_date, config_id]
        else:
            config_condition = ""
            params = [since_date]
        
        # Get success rates
        cursor.execute(f"""
        SELECT 
            COUNT(*) as total_runs,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_runs,
            AVG(CASE WHEN status = 'completed' THEN 
                CAST(stations_successful AS FLOAT) / stations_attempted * 100 
            END) as avg_success_rate,
            AVG(duration_seconds) as avg_duration
        FROM data_collection_logs
        WHERE start_time >= ? {config_condition}
        """, params)
        
        stats = dict(cursor.fetchone())
        
        # Get error breakdown
        cursor.execute(f"""
        SELECT error_type, COUNT(*) as error_count
        FROM station_collection_errors sce
        JOIN data_collection_logs dcl ON sce.log_id = dcl.id
        WHERE dcl.start_time >= ? {config_condition}
        GROUP BY error_type
        ORDER BY error_count DESC
        """, params)
        
        stats['error_breakdown'] = [dict(row) for row in cursor.fetchall()]
        
        return stats
    
    def get_system_health(self) -> Dict:
        """Get overall system health metrics."""
        cursor = self.connection.cursor()
        
        # Active configurations
        cursor.execute("SELECT COUNT(*) FROM station_configurations WHERE is_active = 1")
        active_configs = cursor.fetchone()[0]
        
        # Total active stations
        cursor.execute("SELECT COUNT(*) FROM station_lists WHERE is_active = 1")
        active_stations = cursor.fetchone()[0]
        
        # Recent collection success rate (last 24 hours)
        cursor.execute("""
        SELECT 
            COUNT(*) as recent_runs,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_runs
        FROM data_collection_logs
        WHERE start_time >= datetime('now', '-24 hours')
        """)
        
        recent_activity = dict(cursor.fetchone())
        success_rate = 0
        if recent_activity['recent_runs'] > 0:
            success_rate = (recent_activity['successful_runs'] / recent_activity['recent_runs']) * 100
        
        # Currently running collections
        cursor.execute("SELECT COUNT(*) FROM data_collection_logs WHERE status = 'running'")
        running_collections = cursor.fetchone()[0]
        
        return {
            'active_configurations': active_configs,
            'active_stations': active_stations,
            'recent_success_rate': round(success_rate, 1),
            'recent_runs_24h': recent_activity['recent_runs'],
            'currently_running': running_collections,
            'last_updated': datetime.now().isoformat()
        }


# Convenience functions for common operations
def get_station_list(config_name: str = None) -> List[str]:
    """Get list of USGS IDs for a configuration (for backward compatibility)."""
    with StationConfigurationManager() as manager:
        if config_name:
            config = manager.get_configuration_by_name(config_name)
            if not config:
                raise ValueError(f"Configuration '{config_name}' not found")
            config_id = config['id']
        else:
            config = manager.get_default_configuration()
            if not config:
                raise ValueError("No default configuration found")
            config_id = config['id']
        
        stations = manager.get_stations_for_configuration(config_id)
        return [station['usgs_id'] for station in stations]


def get_configuration_info(config_name: str = None) -> Dict:
    """Get detailed information about a configuration."""
    with StationConfigurationManager() as manager:
        if config_name:
            config = manager.get_configuration_by_name(config_name)
        else:
            config = manager.get_default_configuration()
        
        if not config:
            raise ValueError(f"Configuration '{config_name}' not found")
        
        stations = manager.get_stations_for_configuration(config['id'])
        schedules = manager.get_schedules_for_configuration(config['id'])
        
        return {
            'configuration': config,
            'station_count': len(stations),
            'stations': stations,
            'schedules': schedules
        }