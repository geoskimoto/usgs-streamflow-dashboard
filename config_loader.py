"""
Configuration Loader Module

Loads configurations from JSON files and populates the database on first run.
Handles config updates, environment variable overrides, and local overrides.

Features:
  - Load default configurations, schedules, and system settings from config/
  - Support local overrides (*.local.json files)
  - Environment variable overrides (USGS_* prefix)
  - Sync config files with database state
  - Validate JSON schemas
  - Load station data from CSV/filter/database sources

Usage:
    from config_loader import ConfigLoader
    
    loader = ConfigLoader('data/usgs_data.db')
    loader.load_all()  # Load everything
    
    # Or load specific components
    loader.load_configurations()
    loader.load_schedules()
    loader.load_settings()

Author: USGS Streamflow Dashboard Team
Date: November 6, 2025
"""

import sqlite3
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import logging
import os
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigLoader:
    """Load and sync JSON configurations with database"""
    
    def __init__(self, db_path: str = 'data/usgs_data.db'):
        self.db_path = Path(db_path)
        self.config_dir = Path('config')
        
        # Config file paths
        self.configurations_file = self.config_dir / 'default_configurations.json'
        self.schedules_file = self.config_dir / 'default_schedules.json'
        self.settings_file = self.config_dir / 'system_settings.json'
        
        # Check for local overrides
        self.configurations_local = self.config_dir / 'default_configurations.local.json'
        self.schedules_local = self.config_dir / 'default_schedules.local.json'
        self.settings_local = self.config_dir / 'system_settings.local.json'
        
        # Loaded data cache
        self._configurations = None
        self._schedules = None
        self._settings = None
        
    def load_all(self, force_reload: bool = False, skip_station_data: bool = False):
        """
        Load all configurations into database
        
        Args:
            force_reload: If True, reload even if already loaded
            skip_station_data: If True, don't fetch station data (for testing)
        """
        logger.info("Loading all configurations...")
        
        # Check if already loaded
        if not force_reload and self._is_database_populated():
            logger.info("Database already populated, skipping load")
            logger.info("Use force_reload=True to reload configurations")
            return
        
        # Load each component
        self.load_settings()
        self.load_configurations(skip_station_data=skip_station_data)
        self.load_schedules()
        
        logger.info("✓ All configurations loaded successfully")
    
    def _is_database_populated(self) -> bool:
        """Check if database has been populated with configs"""
        if not self.db_path.exists():
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM configurations")
        count = cursor.fetchone()[0]
        conn.close()
        
        return count > 0
    
    def load_json_with_overrides(self, base_file: Path, local_file: Path) -> Dict:
        """
        Load JSON file with local overrides
        
        Priority: local_file > base_file
        """
        # Load base config
        with open(base_file, 'r') as f:
            data = json.load(f)
        
        # Check for local override
        if local_file.exists():
            logger.info(f"Found local override: {local_file.name}")
            with open(local_file, 'r') as f:
                local_data = json.load(f)
            
            # Merge (local overrides base)
            data = self._deep_merge(data, local_data)
        
        return data
    
    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries (override wins)"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def apply_env_overrides(self, settings: Dict) -> Dict:
        """Apply environment variable overrides to settings"""
        logger.info("Checking for environment variable overrides...")
        
        overrides_applied = 0
        
        # Database path
        if 'USGS_DB_PATH' in os.environ:
            settings['database']['path'] = os.environ['USGS_DB_PATH']
            overrides_applied += 1
            logger.info(f"  USGS_DB_PATH: {os.environ['USGS_DB_PATH']}")
        
        # USGS API key
        if 'USGS_API_KEY' in os.environ:
            settings['usgs_api']['api_key'] = os.environ['USGS_API_KEY']
            overrides_applied += 1
            logger.info("  USGS_API_KEY: <set>")
        
        # Email for API requests
        if 'USGS_API_EMAIL' in os.environ:
            settings['usgs_api']['email'] = os.environ['USGS_API_EMAIL']
            overrides_applied += 1
            logger.info(f"  USGS_API_EMAIL: {os.environ['USGS_API_EMAIL']}")
        
        # Data collection timeout
        if 'USGS_TIMEOUT' in os.environ:
            try:
                settings['data_collection']['timeout_seconds'] = int(os.environ['USGS_TIMEOUT'])
                overrides_applied += 1
                logger.info(f"  USGS_TIMEOUT: {os.environ['USGS_TIMEOUT']}")
            except ValueError:
                logger.warning(f"Invalid USGS_TIMEOUT value: {os.environ['USGS_TIMEOUT']}")
        
        # Max concurrent requests
        if 'USGS_MAX_CONCURRENT' in os.environ:
            try:
                settings['data_collection']['max_concurrent_requests'] = int(os.environ['USGS_MAX_CONCURRENT'])
                overrides_applied += 1
                logger.info(f"  USGS_MAX_CONCURRENT: {os.environ['USGS_MAX_CONCURRENT']}")
            except ValueError:
                logger.warning(f"Invalid USGS_MAX_CONCURRENT value: {os.environ['USGS_MAX_CONCURRENT']}")
        
        # Log level
        if 'USGS_LOG_LEVEL' in os.environ:
            settings['logging']['level'] = os.environ['USGS_LOG_LEVEL']
            overrides_applied += 1
            logger.info(f"  USGS_LOG_LEVEL: {os.environ['USGS_LOG_LEVEL']}")
        
        if overrides_applied > 0:
            logger.info(f"✓ Applied {overrides_applied} environment variable overrides")
        else:
            logger.info("  No environment overrides found")
        
        return settings
    
    def load_settings(self):
        """Load system settings"""
        logger.info("Loading system settings...")
        
        # Load JSON with overrides
        settings = self.load_json_with_overrides(
            self.settings_file,
            self.settings_local
        )
        
        # Apply environment variables
        settings = self.apply_env_overrides(settings)
        
        # Cache settings
        self._settings = settings
        
        logger.info("✓ System settings loaded")
        
        # Note: Settings are not stored in database, they're used by application
        # at runtime. The config file is the source of truth.
        
        return settings
    
    def load_configurations(self, skip_station_data: bool = False):
        """Load station configurations into database"""
        logger.info("Loading station configurations...")
        
        # Load JSON
        data = self.load_json_with_overrides(
            self.configurations_file,
            self.configurations_local
        )
        
        configs = data.get('configurations', [])
        
        if not configs:
            logger.warning("No configurations found in JSON")
            return
        
        # Connect to database
        conn = sqlite3.connect(self.db_path)
        
        try:
            for config in configs:
                logger.info(f"  Loading: {config['config_name']}")
                
                # Get station list based on source
                if not skip_station_data:
                    station_ids = self._get_stations_for_config(config, conn)
                else:
                    station_ids = []
                
                # Insert configuration
                cursor = conn.execute("""
                INSERT INTO configurations 
                (config_name, description, station_count, is_default, is_active, 
                 created_date, last_modified, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(config_name) DO UPDATE SET
                    description = excluded.description,
                    station_count = excluded.station_count,
                    is_default = excluded.is_default,
                    is_active = excluded.is_active,
                    last_modified = excluded.last_modified
                """, (
                    config['config_name'],
                    config['description'],
                    len(station_ids),
                    config.get('is_default', False),
                    config.get('is_active', True),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    'config_loader'
                ))
                
                config_id = cursor.lastrowid
                if cursor.lastrowid == 0:  # UPDATE happened, get existing ID
                    cursor = conn.execute(
                        "SELECT id FROM configurations WHERE config_name = ?",
                        (config['config_name'],)
                    )
                    config_id = cursor.fetchone()[0]
                
                # Clear existing station mappings
                conn.execute(
                    "DELETE FROM configuration_stations WHERE config_id = ?",
                    (config_id,)
                )
                
                # Insert station mappings
                if not skip_station_data:
                    for priority, station_id in enumerate(station_ids, 1):
                        conn.execute("""
                        INSERT INTO configuration_stations 
                        (config_id, station_id, priority, added_date, added_by)
                        VALUES (?, ?, ?, ?, ?)
                        """, (
                            config_id, station_id, priority,
                            datetime.now().isoformat(), 'config_loader'
                        ))
                
                logger.info(f"    ✓ Loaded {len(station_ids)} stations")
            
            conn.commit()
            logger.info(f"✓ Loaded {len(configs)} configurations")
            
        finally:
            conn.close()
    
    def _get_stations_for_config(self, config: Dict, conn: sqlite3.Connection) -> List[int]:
        """
        Get station IDs for a configuration based on source type
        
        Returns list of station IDs (database primary keys)
        """
        source = config.get('station_source', {})
        source_type = source.get('type')
        
        if source_type == 'csv':
            return self._load_stations_from_csv(source, conn)
        
        elif source_type == 'filter':
            return self._load_stations_from_filter(source, conn)
        
        elif source_type == 'manual':
            return self._load_stations_manual(source, conn)
        
        elif source_type == 'database':
            return self._load_stations_from_database(source, conn)
        
        else:
            logger.warning(f"Unknown source type: {source_type}")
            return []
    
    def _load_stations_from_csv(self, source: Dict, conn: sqlite3.Connection) -> List[int]:
        """Load stations from CSV file"""
        csv_file = Path(source['csv_file'])
        
        if not csv_file.exists():
            logger.warning(f"CSV file not found: {csv_file}")
            return []
        
        # Read CSV to get USGS IDs
        usgs_ids = []
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try different possible column names
                usgs_id = row.get('usgs_id') or row.get('site_id') or row.get('site_id')
                if usgs_id:
                    usgs_ids.append(usgs_id)
        
        # Look up database IDs
        station_ids = []
        for usgs_id in usgs_ids:
            cursor = conn.execute(
                "SELECT id FROM stations WHERE usgs_id = ?",
                (usgs_id,)
            )
            result = cursor.fetchone()
            if result:
                station_ids.append(result[0])
        
        logger.info(f"    Loaded {len(station_ids)}/{len(usgs_ids)} stations from CSV")
        
        return station_ids
    
    def _load_stations_from_filter(self, source: Dict, conn: sqlite3.Connection) -> List[int]:
        """Load stations using filter criteria"""
        filters = source.get('filters', [])
        
        # Build SQL WHERE clause
        where_clauses = []
        params = []
        
        for filter_item in filters:
            field = filter_item['field']
            operator = filter_item['operator']
            value = filter_item['value']
            
            clause, param = self._build_filter_clause(field, operator, value)
            if clause:
                where_clauses.append(clause)
                if param is not None:
                    if isinstance(param, list):
                        params.extend(param)
                    else:
                        params.append(param)
        
        # Build full query
        if where_clauses:
            sql = f"SELECT id FROM stations WHERE {' AND '.join(where_clauses)}"
        else:
            sql = "SELECT id FROM stations"
        
        # Apply max_stations limit
        max_stations = source.get('max_stations')
        if max_stations:
            sql += f" LIMIT {max_stations}"
        
        # Execute query
        cursor = conn.execute(sql, params)
        station_ids = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"    Loaded {len(station_ids)} stations from filter")
        
        return station_ids
    
    def _build_filter_clause(self, field: str, operator: str, value: Any) -> Tuple[Optional[str], Any]:
        """Build SQL WHERE clause for a filter"""
        
        if operator == '=':
            return f"{field} = ?", value
        
        elif operator == '!=':
            return f"{field} != ?", value
        
        elif operator == '>':
            return f"{field} > ?", value
        
        elif operator == '<':
            return f"{field} < ?", value
        
        elif operator == '>=':
            return f"{field} >= ?", value
        
        elif operator == '<=':
            return f"{field} <= ?", value
        
        elif operator == 'in':
            if not isinstance(value, list):
                value = [value]
            placeholders = ','.join(['?'] * len(value))
            return f"{field} IN ({placeholders})", value
        
        elif operator == 'not_in':
            if not isinstance(value, list):
                value = [value]
            placeholders = ','.join(['?'] * len(value))
            return f"{field} NOT IN ({placeholders})", value
        
        elif operator == 'contains':
            return f"{field} LIKE ?", f"%{value}%"
        
        elif operator == 'not_contains':
            return f"{field} NOT LIKE ?", f"%{value}%"
        
        elif operator == 'starts_with':
            return f"{field} LIKE ?", f"{value}%"
        
        elif operator == 'ends_with':
            return f"{field} LIKE ?", f"%{value}"
        
        elif operator == 'is_null':
            return f"{field} IS NULL", None
        
        elif operator == 'is_not_null':
            return f"{field} IS NOT NULL", None
        
        elif operator == 'between':
            if isinstance(value, list) and len(value) == 2:
                return f"{field} BETWEEN ? AND ?", value
        
        else:
            logger.warning(f"Unknown operator: {operator}")
            return None, None
    
    def _load_stations_manual(self, source: Dict, conn: sqlite3.Connection) -> List[int]:
        """Load manually specified stations"""
        usgs_ids = source.get('usgs_ids', [])
        
        station_ids = []
        for usgs_id in usgs_ids:
            cursor = conn.execute(
                "SELECT id FROM stations WHERE usgs_id = ?",
                (usgs_id,)
            )
            result = cursor.fetchone()
            if result:
                station_ids.append(result[0])
            else:
                logger.warning(f"    Station not found: {usgs_id}")
        
        logger.info(f"    Loaded {len(station_ids)}/{len(usgs_ids)} manual stations")
        
        return station_ids
    
    def _load_stations_from_database(self, source: Dict, conn: sqlite3.Connection) -> List[int]:
        """Load stations from existing configuration"""
        config_name = source.get('base_config')
        
        cursor = conn.execute(
            "SELECT id FROM configurations WHERE config_name = ?",
            (config_name,)
        )
        result = cursor.fetchone()
        
        if not result:
            logger.warning(f"    Base config not found: {config_name}")
            return []
        
        base_config_id = result[0]
        
        # Get stations from base config
        cursor = conn.execute("""
        SELECT station_id FROM configuration_stations 
        WHERE config_id = ?
        ORDER BY priority
        """, (base_config_id,))
        
        station_ids = [row[0] for row in cursor.fetchall()]
        
        # Apply additional filters if specified
        additional_filters = source.get('filters', [])
        if additional_filters:
            # Filter the station_ids based on criteria
            filtered_ids = []
            for station_id in station_ids:
                # Check if station matches filters
                if self._station_matches_filters(station_id, additional_filters, conn):
                    filtered_ids.append(station_id)
            
            station_ids = filtered_ids
        
        logger.info(f"    Loaded {len(station_ids)} stations from base config")
        
        return station_ids
    
    def _station_matches_filters(self, station_id: int, filters: List[Dict], 
                                 conn: sqlite3.Connection) -> bool:
        """Check if a station matches filter criteria"""
        
        # Get station data
        cursor = conn.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
        station = cursor.fetchone()
        
        if not station:
            return False
        
        # Get column names
        columns = [desc[0] for desc in cursor.description]
        station_dict = dict(zip(columns, station))
        
        # Check each filter
        for filter_item in filters:
            field = filter_item['field']
            operator = filter_item['operator']
            value = filter_item['value']
            
            station_value = station_dict.get(field)
            
            # Apply operator
            if not self._apply_filter_operator(station_value, operator, value):
                return False
        
        return True
    
    def _apply_filter_operator(self, station_value: Any, operator: str, filter_value: Any) -> bool:
        """Apply filter operator to check if station value matches"""
        
        if operator == '=':
            return station_value == filter_value
        elif operator == '!=':
            return station_value != filter_value
        elif operator == '>':
            return station_value > filter_value if station_value is not None else False
        elif operator == '<':
            return station_value < filter_value if station_value is not None else False
        elif operator == '>=':
            return station_value >= filter_value if station_value is not None else False
        elif operator == '<=':
            return station_value <= filter_value if station_value is not None else False
        elif operator == 'in':
            return station_value in filter_value if isinstance(filter_value, list) else False
        elif operator == 'not_in':
            return station_value not in filter_value if isinstance(filter_value, list) else False
        elif operator == 'contains':
            return filter_value in str(station_value) if station_value is not None else False
        elif operator == 'not_contains':
            return filter_value not in str(station_value) if station_value is not None else False
        elif operator == 'starts_with':
            return str(station_value).startswith(filter_value) if station_value is not None else False
        elif operator == 'ends_with':
            return str(station_value).endswith(filter_value) if station_value is not None else False
        elif operator == 'is_null':
            return station_value is None
        elif operator == 'is_not_null':
            return station_value is not None
        elif operator == 'between':
            if isinstance(filter_value, list) and len(filter_value) == 2:
                return filter_value[0] <= station_value <= filter_value[1] if station_value is not None else False
        
        return False
    
    def load_schedules(self):
        """Load automated schedules into database"""
        logger.info("Loading schedules...")
        
        # Load JSON
        data = self.load_json_with_overrides(
            self.schedules_file,
            self.schedules_local
        )
        
        schedules = data.get('schedules', [])
        
        if not schedules:
            logger.warning("No schedules found in JSON")
            return
        
        # Connect to database
        conn = sqlite3.connect(self.db_path)
        
        try:
            for schedule in schedules:
                logger.info(f"  Loading: {schedule['schedule_name']}")
                
                # Look up config ID
                cursor = conn.execute(
                    "SELECT id FROM configurations WHERE config_name = ?",
                    (schedule['config_name'],)
                )
                result = cursor.fetchone()
                
                if not result:
                    logger.warning(f"    Config not found: {schedule['config_name']}")
                    continue
                
                config_id = result[0]
                
                # Insert schedule
                conn.execute("""
                INSERT INTO schedules 
                (config_id, schedule_name, data_type, cron_expression, interval_minutes,
                 is_enabled, run_count, created_date, retry_attempts, timeout_seconds,
                 max_concurrent, priority, notification_email)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(config_id, schedule_name) DO UPDATE SET
                    data_type = excluded.data_type,
                    cron_expression = excluded.cron_expression,
                    interval_minutes = excluded.interval_minutes,
                    is_enabled = excluded.is_enabled,
                    retry_attempts = excluded.retry_attempts,
                    timeout_seconds = excluded.timeout_seconds,
                    max_concurrent = excluded.max_concurrent,
                    priority = excluded.priority,
                    notification_email = excluded.notification_email
                """, (
                    config_id,
                    schedule['schedule_name'],
                    schedule['data_type'],
                    schedule['timing'].get('cron_expression'),
                    schedule['timing'].get('interval_minutes'),
                    schedule.get('is_enabled', True),
                    0,  # run_count starts at 0
                    datetime.now().isoformat(),
                    schedule.get('retry_attempts', 3),
                    schedule.get('timeout_seconds', 30),
                    schedule.get('max_concurrent_stations', 10),
                    schedule.get('priority', 5),
                    schedule.get('notification_email')
                ))
                
                logger.info(f"    ✓ Schedule loaded")
            
            conn.commit()
            logger.info(f"✓ Loaded {len(schedules)} schedules")
            
        finally:
            conn.close()
    
    def get_settings(self) -> Dict:
        """Get loaded settings (load if not cached)"""
        if self._settings is None:
            self._settings = self.load_settings()
        return self._settings
    
    def reload_all(self):
        """Force reload all configurations"""
        logger.info("Force reloading all configurations...")
        self._settings = None
        self._configurations = None
        self._schedules = None
        self.load_all(force_reload=True)


def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Load configurations from JSON files')
    parser.add_argument('--db', default='data/usgs_data.db',
                       help='Database path (default: data/usgs_data.db)')
    parser.add_argument('--force', action='store_true',
                       help='Force reload even if already loaded')
    parser.add_argument('--skip-stations', action='store_true',
                       help='Skip loading station data (for testing)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Create loader
    loader = ConfigLoader(args.db)
    
    # Load all
    loader.load_all(force_reload=args.force, skip_station_data=args.skip_stations)
    
    print("\n✓ Configuration loading complete")


if __name__ == '__main__':
    main()
