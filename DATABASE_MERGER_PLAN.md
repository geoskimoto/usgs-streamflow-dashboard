# Database Merger & Config System Refactor - Detailed Implementation Plan

**Date:** November 6, 2025  
**Objective:** Merge `station_config.db` and `usgs_cache.db` into unified `usgs_data.db` + Create config folder with version-controlled defaults  
**Status:** Planning Phase  
**Risk Level:** HIGH - Major structural change affecting all components

---

## Executive Summary

### Current State
- **Two databases with duplicated station metadata** (1,506 stations in both)
- **No version-controlled configuration defaults** (only runtime database)
- **Maintenance burden** - sync issues between databases
- **Deployment complexity** - requires database setup before running

### Target State
- **Single unified database** - `data/usgs_data.db`
- **Version-controlled config folder** - `config/` with JSON defaults
- **Easy deployment** - configs in git, database generated on first run
- **No duplication** - single source of truth for station metadata

### Benefits
✅ Eliminate data duplication and sync issues  
✅ Version control for default configurations  
✅ Simpler deployment (config files → auto-generate database)  
✅ Single database connection = better performance  
✅ Clear separation: configs in git, runtime data in database (gitignored)

### Risks
⚠️ Breaking change - affects 15+ Python files  
⚠️ Data migration complexity - must preserve all existing data  
⚠️ Testing burden - every feature must be verified  
⚠️ Rollback complexity if issues discovered  

---

## Phase 1: Discovery & Analysis

### 1.1 Database Inventory

**Current Databases:**

#### `data/station_config.db` (624 KB)
```
Tables:
├── station_lists (1,506 rows)           ← Master station metadata
├── station_configurations (3 rows)      ← Config sets (PNW Full, Columbia Basin, Test)
├── configuration_stations (mapping)     ← Many-to-many config ↔ stations
├── update_schedules (4 rows)            ← Collection schedules
├── data_collection_logs                 ← Collection history
└── station_collection_errors            ← Error logs

Views:
├── configuration_summary                ← Config overview
├── stations_by_state                    ← State groupings
└── recent_collection_activity           ← Recent runs

Indexes:
├── idx_station_usgs_id
├── idx_station_state
├── idx_station_huc
└── idx_station_active
```

#### `data/usgs_cache.db` (1.1 GB)
```
Tables:
├── filters (1,506 rows)                 ← DUPLICATE station metadata + UI state
├── streamflow_data (~millions of rows)  ← Historical time series
├── realtime_discharge (~thousands)      ← Live data
├── data_statistics                      ← Computed stats per station
├── subset_cache                         ← Cached data subsets
└── job_execution_log                    ← Legacy? (check if still used)

Indexes:
├── idx_filters_state
├── idx_filters_basin
├── idx_streamflow_site_date
└── [various performance indexes]
```

**Duplicated Fields:**
```
station_lists.usgs_id        = filters.site_id          ✓ Same
station_lists.station_name   = filters.station_name     ✓ Same
station_lists.state          = filters.state            ✓ Same
station_lists.latitude       = filters.latitude         ✓ Same
station_lists.longitude      = filters.longitude        ✓ Same
station_lists.drainage_area  = filters.drainage_area    ✓ Same (after binary fix)
station_lists.huc_code       = filters.huc_code         ✓ Same
station_lists.is_active      = filters.is_active        ✓ Same

Unique to station_lists:
- nws_id, goes_id (HADS identifiers)
- source_dataset (provenance)
- date_added, last_verified
- notes

Unique to filters:
- county, site_type, agency (USGS metadata)
- basin (derived from HUC)
- years_of_record, num_water_years (computed)
- last_data_date (data freshness)
- status, color (UI state)
- last_updated
```

### 1.2 Code Dependencies

**Files Reading from `station_config.db`:**
```python
✓ station_config_manager.py          - Main interface (407 lines)
✓ setup_configuration_database.py    - Schema creation (200+ lines)
✓ populate_station_database.py       - Initial population (~150 lines)
✓ sync_station_metadata.py           - Cross-database sync (100+ lines)
✓ configurable_data_collector.py     - Data collection (reads schedules)
✓ smart_scheduler.py                 - Schedule execution
✓ admin_components.py                - Admin panel UI (reads all tables)
✓ app.py                             - Monitoring tab queries
```

**Files Reading from `usgs_cache.db`:**
```python
✓ app.py                             - Dashboard map/filters (load_gauge_data)
✓ usgs_dashboard/components/map_component.py  - Map rendering
✓ usgs_dashboard/viz_manager.py      - Visualizations
✓ usgs_dashboard/utils/water_year_datetime.py - Plots
✓ streamflow_analyzer.py             - Statistics
✓ configurable_data_collector.py     - Writes streamflow data
✓ check_status.py                    - Status checks
```

**Files Writing to Databases:**
```python
✓ configurable_data_collector.py     - Writes streamflow_data, realtime_discharge, logs
✓ populate_station_database.py       - Writes station_lists
✓ enrich_station_metadata.py         - Updates station metadata
✓ sync_station_metadata.py           - Syncs station_lists → filters
✓ admin_components.py                - CRUD operations on configs/schedules
```

### 1.3 Critical Queries to Preserve

**Dashboard Map Loading (app.py ~770):**
```python
SELECT site_id, station_name, latitude, longitude, drainage_area, 
       state, county, basin, huc_code, is_active, status, color, 
       last_data_date, years_of_record
FROM filters
WHERE is_active = 1
LIMIT ?
```

**Admin Panel Stations Tab:**
```python
SELECT * FROM configuration_summary
SELECT * FROM stations_by_state  
SELECT * FROM station_lists WHERE state = ?
```

**Data Collection:**
```python
SELECT usgs_id FROM station_lists 
WHERE usgs_id IN (
    SELECT station_id FROM configuration_stations 
    WHERE config_id = ?
)
```

**Monitoring Tab:**
```python
SELECT * FROM recent_collection_activity ORDER BY execution_time DESC
SELECT * FROM data_collection_logs WHERE success = 0
```

---

## Phase 2: Design Unified Schema

### 2.1 New Database: `data/usgs_data.db`

#### Core Metadata Table
```sql
CREATE TABLE stations (
    -- Primary Key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- USGS Identifiers (from station_lists)
    usgs_id TEXT UNIQUE NOT NULL,           -- Main identifier
    nws_id TEXT,                             -- NOAA/NWS ID
    goes_id TEXT,                            -- GOES satellite ID
    
    -- Basic Metadata (merged from both)
    station_name TEXT NOT NULL,
    state TEXT NOT NULL,
    county TEXT,                             -- From filters
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    
    -- Hydrologic Metadata (merged)
    drainage_area REAL,
    huc_code TEXT,
    basin TEXT,                              -- From filters (derived from HUC)
    
    -- USGS Metadata (from filters)
    site_type TEXT,                          -- Stream, Lake, etc.
    agency TEXT,                             -- Usually 'USGS'
    
    -- Data Statistics (from filters)
    years_of_record INTEGER,
    num_water_years INTEGER,
    last_data_date TEXT,
    
    -- Status & Control (merged)
    is_active BOOLEAN DEFAULT TRUE,
    status TEXT,                             -- 'active', 'inactive', 'error'
    
    -- Provenance (from station_lists)
    source_dataset TEXT NOT NULL,            -- 'HADS_PNW', 'HADS_Columbia', 'Custom'
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified TIMESTAMP,
    
    -- UI State (from filters)
    color TEXT,                              -- Map marker color
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Notes
    notes TEXT
);

-- Indexes for performance
CREATE INDEX idx_stations_usgs_id ON stations(usgs_id);
CREATE INDEX idx_stations_state ON stations(state);
CREATE INDEX idx_stations_basin ON stations(basin);
CREATE INDEX idx_stations_huc ON stations(huc_code);
CREATE INDEX idx_stations_active ON stations(is_active);
CREATE INDEX idx_stations_status ON stations(status);
CREATE INDEX idx_stations_drainage ON stations(drainage_area);
```

#### Configuration Tables (from station_config.db)
```sql
CREATE TABLE configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name TEXT UNIQUE NOT NULL,
    description TEXT,
    station_count INTEGER DEFAULT 0,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system'
);

CREATE TABLE configuration_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    station_id INTEGER NOT NULL,              -- References stations.id
    sort_order INTEGER,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (config_id) REFERENCES configurations(id) ON DELETE CASCADE,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE,
    UNIQUE(config_id, station_id)
);

CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_name TEXT UNIQUE NOT NULL,
    config_id INTEGER NOT NULL,
    interval_minutes INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (config_id) REFERENCES configurations(id) ON DELETE CASCADE
);
```

#### Data Tables (from usgs_cache.db)
```sql
CREATE TABLE streamflow_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,                    -- References stations.usgs_id
    date TEXT NOT NULL,
    discharge REAL,
    qualification_code TEXT,
    water_year INTEGER,
    day_of_water_year INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES stations(usgs_id),
    UNIQUE(site_id, date)
);

CREATE TABLE realtime_discharge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,
    datetime TEXT NOT NULL,
    discharge REAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES stations(usgs_id),
    UNIQUE(site_id, datetime)
);

CREATE TABLE data_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,
    statistic_type TEXT NOT NULL,             -- 'mean', 'median', 'percentile_10', etc.
    day_of_water_year INTEGER NOT NULL,
    value REAL,
    water_years_count INTEGER,
    last_calculated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES stations(usgs_id),
    UNIQUE(site_id, statistic_type, day_of_water_year)
);

-- Keep subset_cache as-is
CREATE TABLE subset_cache (
    [... existing schema ...]
);
```

#### Operational Tables (from station_config.db)
```sql
CREATE TABLE collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER,
    station_id INTEGER,                       -- NULL for config-level logs
    execution_time TIMESTAMP NOT NULL,
    success BOOLEAN NOT NULL,
    records_collected INTEGER DEFAULT 0,
    error_message TEXT,
    execution_duration_seconds REAL,
    FOREIGN KEY (config_id) REFERENCES configurations(id),
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

CREATE TABLE station_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id INTEGER NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    occurrence_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (station_id) REFERENCES stations(id)
);
```

#### Views for Compatibility
```sql
-- Maintain existing view names for backward compatibility
CREATE VIEW configuration_summary AS
SELECT 
    c.id,
    c.config_name,
    c.description,
    c.station_count,
    c.is_default,
    c.is_active,
    c.created_date,
    COUNT(DISTINCT cs.station_id) as actual_station_count
FROM configurations c
LEFT JOIN configuration_stations cs ON c.id = cs.config_id
GROUP BY c.id;

CREATE VIEW stations_by_state AS
SELECT 
    state,
    COUNT(*) as station_count,
    COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_count
FROM stations
GROUP BY state
ORDER BY state;

CREATE VIEW recent_collection_activity AS
SELECT 
    cl.id,
    cl.execution_time,
    c.config_name,
    s.station_name,
    s.usgs_id,
    cl.success,
    cl.records_collected,
    cl.error_message,
    cl.execution_duration_seconds
FROM collection_logs cl
LEFT JOIN configurations c ON cl.config_id = c.config_id
LEFT JOIN stations s ON cl.station_id = s.id
ORDER BY cl.execution_time DESC
LIMIT 100;
```

### 2.2 Migration Strategy

**Data Preservation Rules:**
1. **Station metadata priority:**
   - Use `station_lists` as base (has provenance info)
   - Merge in unique fields from `filters` (county, agency, basin, etc.)
   - Prefer non-NULL values when conflicts exist
   - Keep both `drainage_area` values if different (log warning)

2. **Configuration data:**
   - Copy all configurations, schedules unchanged
   - Remap station IDs from usgs_id to new integer IDs

3. **Streamflow data:**
   - Copy all rows unchanged
   - Verify counts match before/after

4. **Logs:**
   - Copy all collection logs
   - Preserve timestamps exactly

**Conflict Resolution:**
```python
# If station exists in both databases with different values:
if station_lists.drainage_area != filters.drainage_area:
    # Prefer station_lists (source of truth after binary fix)
    final.drainage_area = station_lists.drainage_area
    log_warning(f"Drainage area mismatch for {usgs_id}")

if station_lists.station_name != filters.station_name:
    # Prefer filters (might have updated USGS data)
    final.station_name = filters.station_name
    log_warning(f"Name mismatch for {usgs_id}")
```

---

## Phase 3: Config Folder Design

### 3.1 Directory Structure
```
config/
├── README.md                          # Configuration documentation
├── default_configurations.json        # Station set definitions
├── default_schedules.json             # Update schedule templates
├── system_settings.json               # App-level settings
├── .gitignore                         # Ignore *.local.json
└── examples/
    ├── custom_configuration.json      # Example custom config
    └── custom_schedule.json           # Example schedule
```

### 3.2 Configuration File Schemas

#### `config/default_configurations.json`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "version": "1.0",
  "configurations": [
    {
      "name": "Pacific Northwest Full",
      "description": "Complete NOAA HADS discharge monitoring stations across WA, OR, ID, MT, NV, CA",
      "is_default": true,
      "is_active": true,
      "station_source": {
        "type": "csv",
        "path": "all_pnw_discharge_stations.csv",
        "columns": {
          "usgs_id": "usgs_id",
          "nws_id": "nws_id",
          "goes_id": "goes_id",
          "station_name": "station_name",
          "state": "state",
          "latitude": "latitude",
          "longitude": "longitude"
        }
      }
    },
    {
      "name": "Columbia River Basin (HUC17)",
      "description": "NOAA HADS discharge stations within Columbia River Basin watershed",
      "is_default": false,
      "is_active": true,
      "station_source": {
        "type": "csv",
        "path": "columbia_basin_hads_stations.csv",
        "columns": "auto"
      }
    },
    {
      "name": "Development Test Set",
      "description": "Small subset of reliable stations for development and testing",
      "is_default": false,
      "is_active": true,
      "station_source": {
        "type": "filter",
        "base_config": "Pacific Northwest Full",
        "filters": [
          {"field": "state", "operator": "in", "value": ["WA", "OR"]},
          {"field": "drainage_area", "operator": ">", "value": 500},
          {"field": "is_active", "operator": "=", "value": true}
        ],
        "limit": 25
      }
    }
  ]
}
```

#### `config/default_schedules.json`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "version": "1.0",
  "schedules": [
    {
      "name": "Hourly Full Update",
      "description": "Update all stations every hour",
      "configuration": "Pacific Northwest Full",
      "interval_minutes": 60,
      "is_active": true,
      "retry_on_error": true,
      "max_retries": 3
    },
    {
      "name": "15-Minute Realtime",
      "description": "Frequent updates for real-time monitoring subset",
      "configuration": "Development Test Set",
      "interval_minutes": 15,
      "is_active": false,
      "retry_on_error": true,
      "max_retries": 2
    },
    {
      "name": "Daily Full Collection",
      "description": "Complete data collection with statistics recalculation",
      "configuration": "Pacific Northwest Full",
      "interval_minutes": 1440,
      "is_active": true,
      "retry_on_error": true,
      "max_retries": 5,
      "tasks": [
        "collect_data",
        "calculate_statistics",
        "update_metadata",
        "cleanup_old_data"
      ]
    }
  ]
}
```

#### `config/system_settings.json`
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "version": "1.0",
  "database": {
    "path": "data/usgs_data.db",
    "backup_enabled": true,
    "backup_interval_hours": 24,
    "max_backups": 7
  },
  "data_collection": {
    "default_timeout_seconds": 30,
    "max_concurrent_requests": 10,
    "retry_delay_seconds": 5,
    "cache_expiry_days": 90
  },
  "dashboard": {
    "default_map_style": "open-street-map",
    "default_map_height": 600,
    "max_stations_displayed": 1500,
    "auto_refresh_interval_seconds": 300
  },
  "admin_panel": {
    "log_retention_days": 30,
    "max_log_entries_displayed": 1000
  },
  "logging": {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/app.log",
    "max_bytes": 10485760,
    "backup_count": 5
  }
}
```

### 3.3 Config Loading Priority
```
1. Load config/system_settings.json
2. Override with environment variables (USGS_DB_PATH, USGS_LOG_LEVEL, etc.)
3. Load config/default_configurations.json
4. Load config/default_schedules.json
5. Check if database exists:
   - If NO: Create database, populate from configs
   - If YES: Compare configs to database
     - New configs in files → Add to database
     - Missing configs in files → Keep database (user-created)
     - Changed configs in files → Log warning, keep database
6. User modifications via Admin Panel → Always saved to database only
```

---

## Phase 4: Implementation Steps

### Step 1: Create Migration Script

**File:** `migrate_to_unified_db.py`

```python
"""
Migrate station_config.db and usgs_cache.db to unified usgs_data.db

CRITICAL: Creates backups before migration. Validates all data copied correctly.
Run with --dry-run to preview changes without modifying databases.
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import logging

class DatabaseMigration:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.config_db = Path('data/station_config.db')
        self.cache_db = Path('data/usgs_cache.db')
        self.target_db = Path('data/usgs_data.db')
        self.backup_dir = Path('data/backups')
        
        # Statistics
        self.stats = {
            'stations_migrated': 0,
            'streamflow_records': 0,
            'realtime_records': 0,
            'configs_migrated': 0,
            'schedules_migrated': 0,
            'logs_migrated': 0
        }
    
    def create_backups(self):
        """Backup both databases before migration"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_dir.mkdir(exist_ok=True)
        
        config_backup = self.backup_dir / f'station_config_{timestamp}.db'
        cache_backup = self.backup_dir / f'usgs_cache_{timestamp}.db'
        
        shutil.copy2(self.config_db, config_backup)
        shutil.copy2(self.cache_db, cache_backup)
        
        logging.info(f"Backups created: {config_backup}, {cache_backup}")
    
    def create_unified_schema(self):
        """Create new database with unified schema"""
        # Implementation of schema from Phase 2.1
        pass
    
    def migrate_stations(self):
        """
        Merge station_lists and filters into unified stations table
        
        Priority:
        1. Base data from station_lists (has provenance)
        2. Merge unique fields from filters (county, basin, agency)
        3. Conflict resolution per Phase 2.2 rules
        """
        pass
    
    def migrate_configurations(self):
        """Copy configurations and remap station IDs"""
        pass
    
    def migrate_streamflow_data(self):
        """Copy all streamflow_data rows"""
        pass
    
    def migrate_realtime_data(self):
        """Copy all realtime_discharge rows"""
        pass
    
    def migrate_statistics(self):
        """Copy data_statistics"""
        pass
    
    def migrate_logs(self):
        """Copy collection_logs and errors"""
        pass
    
    def validate_migration(self):
        """
        Verify migration correctness:
        - Row counts match
        - No NULL values in NOT NULL columns
        - All foreign keys valid
        - Sample data spot checks
        """
        pass
    
    def run(self):
        """Execute full migration"""
        if not self.dry_run:
            self.create_backups()
        
        self.create_unified_schema()
        self.migrate_stations()
        self.migrate_configurations()
        self.migrate_streamflow_data()
        self.migrate_realtime_data()
        self.migrate_statistics()
        self.migrate_logs()
        
        if not self.dry_run:
            self.validate_migration()
        
        return self.stats

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    migration = DatabaseMigration(dry_run=args.dry_run)
    stats = migration.run()
    print(f"Migration complete: {stats}")
```

### Step 2: Create Config Loader

**File:** `config_loader.py`

```python
"""
Load configuration files and initialize database
"""

import json
import sqlite3
from pathlib import Path
import logging

class ConfigLoader:
    def __init__(self, config_dir='config', db_path='data/usgs_data.db'):
        self.config_dir = Path(config_dir)
        self.db_path = Path(db_path)
    
    def load_system_settings(self):
        """Load system_settings.json"""
        pass
    
    def load_configurations(self):
        """Load default_configurations.json"""
        pass
    
    def load_schedules(self):
        """Load default_schedules.json"""
        pass
    
    def populate_database(self):
        """
        Populate database from config files
        - Read CSV files referenced in configurations
        - Create configuration records
        - Create schedule records
        - Validate all foreign keys
        """
        pass
    
    def sync_configs(self):
        """
        Compare config files to database
        - New configs in files → add to DB
        - Existing configs → keep DB version (user may have modified)
        - Log any discrepancies
        """
        pass
```

### Step 3: Update Database Connection Code

**Modify:** `station_config_manager.py`

```python
class StationConfigurationManager:
    def __init__(self, db_path="data/usgs_data.db"):  # Changed path
        """Initialize with unified database path."""
        self.db_path = Path(db_path)
        self.connection = None
        self.logger = logging.getLogger(__name__)
    
    # Update all queries:
    # - station_lists → stations
    # - station_configurations → configurations
    # - update_schedules → schedules
    # - data_collection_logs → collection_logs
```

**Pattern for all other files:**
```python
# OLD:
config_db = sqlite3.connect('data/station_config.db')
cache_db = sqlite3.connect('data/usgs_cache.db')

# NEW:
db = sqlite3.connect('data/usgs_data.db')

# OLD:
SELECT * FROM filters WHERE site_id = ?

# NEW:
SELECT * FROM stations WHERE usgs_id = ?
```

### Step 4: Update All SQL Queries

**Search patterns to find and replace:**
```bash
# Find all database connections
grep -r "station_config\.db" --include="*.py"
grep -r "usgs_cache\.db" --include="*.py"

# Find all table references
grep -r "station_lists" --include="*.py"
grep -r "FROM filters" --include="*.py"
grep -r "station_configurations" --include="*.py"
grep -r "update_schedules" --include="*.py"
grep -r "data_collection_logs" --include="*.py"
```

**Critical queries to update:**

1. **app.py - Dashboard map loading (~770)**
```python
# OLD:
cache_db = sqlite3.connect('data/usgs_cache.db')
df = pd.read_sql_query("""
    SELECT site_id, station_name, latitude, longitude, ...
    FROM filters
    WHERE is_active = 1
    LIMIT ?
""", cache_db, params=[site_limit])

# NEW:
db = sqlite3.connect('data/usgs_data.db')
df = pd.read_sql_query("""
    SELECT usgs_id as site_id, station_name, latitude, longitude, ...
    FROM stations
    WHERE is_active = 1
    LIMIT ?
""", db, params=[site_limit])
```

2. **admin_components.py - Station management**
```python
# OLD:
config_db = sqlite3.connect('data/station_config.db')
stations = pd.read_sql_query("SELECT * FROM station_lists", config_db)

# NEW:
db = sqlite3.connect('data/usgs_data.db')
stations = pd.read_sql_query("SELECT * FROM stations", db)
```

3. **configurable_data_collector.py - Data collection**
```python
# OLD:
config_db = sqlite3.connect('data/station_config.db')
cache_db = sqlite3.connect('data/usgs_cache.db')

stations_query = """
    SELECT usgs_id FROM station_lists 
    WHERE usgs_id IN (
        SELECT station_id FROM configuration_stations WHERE config_id = ?
    )
"""
stations = pd.read_sql_query(stations_query, config_db)

# Write to cache_db...

# NEW:
db = sqlite3.connect('data/usgs_data.db')

stations_query = """
    SELECT s.usgs_id 
    FROM stations s
    JOIN configuration_stations cs ON s.id = cs.station_id
    WHERE cs.config_id = ?
"""
stations = pd.read_sql_query(stations_query, db)

# Write to same db...
```

### Step 5: Update Admin Panel

**File:** `admin_components.py` (~1,500 lines)

**Changes needed:**
1. Update database connection (single db instead of two)
2. Update table names in all queries:
   - `station_lists` → `stations`
   - `station_configurations` → `configurations`
   - `update_schedules` → `schedules`
   - `data_collection_logs` → `collection_logs`
3. Update column names:
   - `site_id` → `usgs_id` (in stations table)
   - Keep view names (configuration_summary, etc.) for compatibility
4. Test all CRUD operations:
   - Create/edit/delete configurations ✓
   - Create/edit/delete schedules ✓
   - View/filter stations ✓
   - View collection logs ✓
   - Run manual collection ✓

### Step 6: Update Visualization Components

**Files to update:**
- `usgs_dashboard/viz_manager.py`
- `usgs_dashboard/utils/water_year_datetime.py`
- `streamflow_analyzer.py`

**Changes:**
- Update database path to unified db
- Ensure queries still work for:
  - Loading streamflow_data by site_id
  - Loading station metadata for plot titles
  - Computing statistics

### Step 7: Create Initialization Script

**File:** `initialize_system.py`

```python
"""
Initialize USGS Streamflow Dashboard from config files

Run this on first deployment or to reset database to defaults.
"""

def main():
    print("USGS Streamflow Dashboard - System Initialization")
    print("=" * 60)
    
    # Check if database exists
    db_path = Path('data/usgs_data.db')
    if db_path.exists():
        response = input(f"{db_path} exists. Overwrite? (yes/NO): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return
        db_path.unlink()
    
    # Create database with schema
    print("Creating database schema...")
    create_database_schema(db_path)
    
    # Load configurations
    print("Loading configuration files...")
    loader = ConfigLoader()
    loader.load_system_settings()
    loader.load_configurations()
    loader.load_schedules()
    
    # Populate from CSV files
    print("Populating station data from CSV files...")
    loader.populate_database()
    
    # Validate
    print("Validating database...")
    validate_database(db_path)
    
    print("\n✓ Initialization complete!")
    print(f"Database: {db_path}")
    print("Run 'python app.py' to start the dashboard.")

if __name__ == '__main__':
    main()
```

---

## Phase 5: Testing Strategy

### 5.1 Unit Tests

**File:** `tests/test_unified_database.py`

```python
import pytest
import sqlite3
from pathlib import Path

class TestUnifiedDatabase:
    def test_database_schema(self):
        """Verify all tables, indexes, views exist"""
        
    def test_foreign_keys(self):
        """Verify all foreign keys are valid"""
        
    def test_station_queries(self):
        """Test various station queries"""
        
    def test_configuration_operations(self):
        """Test CRUD operations on configs"""
        
    def test_data_collection(self):
        """Test writing streamflow data"""
        
    def test_statistics_calculations(self):
        """Test data_statistics queries"""
```

### 5.2 Integration Tests

**Test Matrix:**

| Component | Test | Expected Result | Status |
|-----------|------|----------------|--------|
| **Database** | Migration script | All data copied, no loss | ⏳ |
| **Database** | Schema creation | All tables/indexes/views | ⏳ |
| **Config** | Load system_settings.json | Settings applied | ⏳ |
| **Config** | Load configurations | Configs in database | ⏳ |
| **Config** | Load schedules | Schedules in database | ⏳ |
| **Dashboard** | Map loads | 1,506 stations display | ⏳ |
| **Dashboard** | Search filter | Results update | ⏳ |
| **Dashboard** | State filter | Results update | ⏳ |
| **Dashboard** | Drainage filter | Results update | ⏳ |
| **Dashboard** | Basin filter | Results update | ⏳ |
| **Dashboard** | HUC filter | Results update | ⏳ |
| **Dashboard** | Real-time filter | Results update | ⏳ |
| **Dashboard** | Station selection | Orange circle appears | ⏳ |
| **Dashboard** | Time series plot | Data displays correctly | ⏳ |
| **Dashboard** | Water year plot | Correct traces, hover works | ⏳ |
| **Dashboard** | Statistics plot | Mean/median display | ⏳ |
| **Admin** | Configurations tab | List displays | ⏳ |
| **Admin** | Create config | Saves to database | ⏳ |
| **Admin** | Edit config | Updates database | ⏳ |
| **Admin** | Delete config | Removes from database | ⏳ |
| **Admin** | Stations tab | List displays | ⏳ |
| **Admin** | Filter stations | Results update | ⏳ |
| **Admin** | View station detail | Metadata displays | ⏳ |
| **Admin** | Schedules tab | List displays | ⏳ |
| **Admin** | Create schedule | Saves to database | ⏳ |
| **Admin** | Run Selected | Collection executes | ⏳ |
| **Admin** | Monitoring tab | Activity displays | ⏳ |
| **Admin** | System health | Stats update | ⏳ |
| **Collection** | Manual run | Data collected | ⏳ |
| **Collection** | Scheduled run | Runs on schedule | ⏳ |
| **Collection** | Error handling | Logs errors | ⏳ |
| **Collection** | Logging | Writes to collection_logs | ⏳ |

### 5.3 Performance Benchmarks

**Queries to benchmark (before vs after):**

```python
# 1. Dashboard map loading
SELECT * FROM stations WHERE is_active = 1 LIMIT 1500

# 2. Filter by state
SELECT * FROM stations WHERE state = 'WA' AND is_active = 1

# 3. Complex filter
SELECT * FROM stations 
WHERE state IN ('WA', 'OR', 'ID') 
AND drainage_area BETWEEN 100 AND 1000
AND basin = 'Columbia River'
AND is_active = 1

# 4. Configuration stations
SELECT s.* FROM stations s
JOIN configuration_stations cs ON s.id = cs.station_id
WHERE cs.config_id = 1

# 5. Recent activity
SELECT * FROM recent_collection_activity LIMIT 100

# 6. Streamflow data for station
SELECT * FROM streamflow_data 
WHERE site_id = '12345678' 
AND date BETWEEN '2024-01-01' AND '2024-12-31'
```

**Acceptance criteria:**
- No query should be slower than 2x current performance
- Dashboard load time should be ≤ current time
- Admin panel responsiveness maintained

### 5.4 Data Validation

**After migration, verify:**

```sql
-- 1. Station count matches
SELECT COUNT(*) FROM stations;  -- Should be 1,506

-- 2. No missing metadata
SELECT COUNT(*) FROM stations WHERE station_name IS NULL;  -- Should be 0
SELECT COUNT(*) FROM stations WHERE latitude IS NULL;      -- Should be 0
SELECT COUNT(*) FROM stations WHERE state IS NULL;         -- Should be 0

-- 3. Streamflow data count matches
SELECT COUNT(*) FROM streamflow_data;  -- Should match old database

-- 4. Configuration counts match
SELECT COUNT(*) FROM configurations;   -- Should be 3

-- 5. Foreign keys valid
SELECT COUNT(*) FROM configuration_stations cs
LEFT JOIN stations s ON cs.station_id = s.id
WHERE s.id IS NULL;  -- Should be 0

-- 6. Views work
SELECT COUNT(*) FROM configuration_summary;
SELECT COUNT(*) FROM stations_by_state;
SELECT COUNT(*) FROM recent_collection_activity;
```

---

## Phase 6: Rollback Plan

### 6.1 Rollback Procedure

**If migration fails or major issues discovered:**

1. **Stop the application immediately**
```bash
pkill -f "python app.py"
```

2. **Restore from backups**
```bash
cd data/backups
# Find latest backup
ls -lt

# Restore
cp station_config_YYYYMMDD_HHMMSS.db ../station_config.db
cp usgs_cache_YYYYMMDD_HHMMSS.db ../usgs_cache.db

# Remove failed migration
rm ../usgs_data.db
```

3. **Revert code changes**
```bash
# If on migration branch:
git checkout feature/remove-legacy-system  # Previous branch

# Or restore specific files:
git checkout HEAD~1 app.py
git checkout HEAD~1 station_config_manager.py
git checkout HEAD~1 admin_components.py
# ... etc
```

4. **Verify rollback successful**
```bash
python app.py
# Test dashboard loads
# Test admin panel works
```

### 6.2 Rollback Decision Criteria

**Abort migration if:**
- ❌ Data validation fails (row counts don't match)
- ❌ Critical functionality broken (map doesn't load, collection fails)
- ❌ Performance degradation >2x
- ❌ Data corruption detected
- ❌ Cannot complete testing in reasonable timeframe

**Proceed with fixes if:**
- ⚠️ Minor UI issues (can be fixed quickly)
- ⚠️ Non-critical features broken (can be fixed post-merge)
- ⚠️ Documentation needs updates

---

## Phase 7: Deployment Plan

### 7.1 Development Environment Migration

1. ✅ Create feature branch: `feature/unified-database`
2. ✅ Run migration on development copy
3. ✅ Test all functionality
4. ✅ Fix issues, iterate
5. ✅ Performance benchmarks
6. ✅ Update documentation

### 7.2 Staging Environment (if available)

1. Fresh clone of repository
2. Run `initialize_system.py` from scratch
3. Verify all defaults load correctly
4. Test full workflow end-to-end

### 7.3 Production Deployment

**Pre-deployment:**
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Rollback plan tested
- [ ] Team informed of changes

**Deployment steps:**
```bash
# 1. Backup current system
cp -r data/ data_backup_$(date +%Y%m%d)/

# 2. Pull latest code
git checkout main
git pull origin main

# 3. Stop application
pkill -f "python app.py"

# 4. Run migration
python migrate_to_unified_db.py

# 5. Verify migration
python -c "from migrate_to_unified_db import DatabaseMigration; m = DatabaseMigration(); m.validate_migration()"

# 6. Start application
python app.py

# 7. Test critical paths
# - Dashboard loads
# - Admin panel works
# - Data collection runs
```

**Post-deployment verification:**
- [ ] Dashboard loads with all stations
- [ ] All filters functional
- [ ] Admin panel operational
- [ ] Data collection working
- [ ] No errors in logs

---

## Phase 8: Documentation Updates

### Files to Update

1. **README.md**
   - Update database section (single database)
   - Document config folder
   - Update setup instructions

2. **QUICK_START.md**
   - Change database paths
   - Add config folder explanation
   - Update initialization steps

3. **DEPLOY.md**
   - Document new deployment process
   - Include config file requirements
   - Update troubleshooting section

4. **ADMIN_PANEL_DATABASE_GUIDE.md**
   - Rewrite for unified schema
   - Update all table names
   - Add config folder section

5. **DATA_COLLECTION_GUIDE.md**
   - Update database references
   - Explain config-driven collection

6. **Create: DATABASE_MIGRATION_GUIDE.md**
   - Document migration process
   - Include rollback procedures
   - Troubleshooting common issues

---

## Phase 9: Timeline & Milestones

### Estimated Timeline

| Phase | Tasks | Time Estimate | Dependencies |
|-------|-------|---------------|--------------|
| **Phase 1** | Analysis & Discovery | 4 hours | None |
| **Phase 2** | Schema Design | 4 hours | Phase 1 |
| **Phase 3** | Config Folder Design | 2 hours | Phase 2 |
| **Phase 4** | Migration Script | 8 hours | Phase 2 |
| **Phase 4** | Config Loader | 4 hours | Phase 3 |
| **Phase 4** | Update Connections | 6 hours | Phase 4 |
| **Phase 4** | Update Queries | 8 hours | Phase 4 |
| **Phase 4** | Update Admin Panel | 6 hours | Phase 4 |
| **Phase 5** | Unit Tests | 4 hours | Phase 4 |
| **Phase 5** | Integration Tests | 8 hours | Phase 4 |
| **Phase 5** | Performance Tests | 2 hours | Phase 4 |
| **Phase 6** | Rollback Testing | 2 hours | Phase 5 |
| **Phase 7** | Dev Migration | 2 hours | Phase 5 |
| **Phase 7** | Staging Test | 4 hours | Phase 7 |
| **Phase 8** | Documentation | 4 hours | Phase 7 |
| **Phase 9** | Production Deploy | 2 hours | Phase 8 |
| **Total** | | **70 hours** | (~9 days) |

### Milestones

- ✅ **M1: Design Complete** - Schema finalized, config structure defined
- ⏳ **M2: Migration Script Ready** - Can successfully migrate test database
- ⏳ **M3: Code Updated** - All files use unified database
- ⏳ **M4: Tests Passing** - All functionality verified
- ⏳ **M5: Documentation Complete** - All guides updated
- ⏳ **M6: Production Deployed** - Live system running on unified database

---

## Risk Assessment

### High Risk Items

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Data loss during migration | CRITICAL | LOW | Comprehensive backups, validation |
| Breaking existing functionality | HIGH | MEDIUM | Extensive testing, rollback plan |
| Performance degradation | MEDIUM | LOW | Benchmarking, index optimization |
| Config file conflicts | MEDIUM | MEDIUM | Clear loading priority, documentation |
| Rollback complexity | HIGH | LOW | Tested rollback procedure |

### Success Criteria

✅ **Must Have:**
- Zero data loss
- All current functionality preserved
- No performance regression
- Successful rollback tested

✅ **Should Have:**
- Improved code clarity
- Easier deployment process
- Better documentation

✅ **Nice to Have:**
- Performance improvements
- Reduced database size
- Cleaner architecture

---

## Conclusion

This is a **major refactoring project** that will significantly improve the system architecture. The benefits (eliminated duplication, version-controlled configs, easier deployment) justify the effort, but must be executed carefully with comprehensive testing and rollback capability.

**Recommended approach:**
1. Start with Phase 1 (Analysis) to confirm all dependencies
2. Build migration script with extensive validation
3. Test thoroughly on development copy
4. Update code systematically, file by file
5. Validate each component before moving to next
6. Only deploy to production after ALL tests pass

**Next Step:** Would you like to proceed with Phase 1 (Analysis & Discovery)?
