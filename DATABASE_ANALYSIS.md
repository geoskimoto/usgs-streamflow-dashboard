# Database Analysis - Complete Dependency Map

**Date:** November 6, 2025  
**Purpose:** Comprehensive analysis of current database structure before merger  
**Status:** ✅ Analysis Complete

---

## Executive Summary

### Current State
- **Two SQLite databases** with 1,506 duplicate station records
- **21 Python files** directly reference database paths
- **8 core tables** + 3 views in station_config.db
- **5 data tables** in usgs_cache.db
- **Significant duplication** in station metadata

---

## Database #1: `station_config.db` (624 KB)

### Tables

#### 1. `station_lists` (1,506 rows)
```sql
CREATE TABLE station_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usgs_id TEXT UNIQUE NOT NULL,
    nws_id TEXT,
    goes_id TEXT,
    station_name TEXT NOT NULL,
    state TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    huc_code TEXT,
    drainage_area REAL,
    source_dataset TEXT NOT NULL,         -- 'HADS_PNW', 'HADS_Columbia', 'Custom'
    is_active BOOLEAN DEFAULT TRUE,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified TIMESTAMP,
    notes TEXT
);
```

**Indexes:**
- `idx_station_usgs_id` ON usgs_id
- `idx_station_state` ON state
- `idx_station_huc` ON huc_code
- `idx_station_active` ON is_active

**Foreign Key References:**
- Referenced by: `configuration_stations.station_id`
- Referenced by: `station_collection_errors.station_id`

#### 2. `station_configurations` (3 rows)
```sql
CREATE TABLE station_configurations (
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
```

**Indexes:**
- `idx_config_name` ON config_name
- `idx_config_active` ON is_active

**Current Records:**
1. "Pacific Northwest Full" (1,506 stations, is_default=TRUE)
2. "Columbia River Basin (HUC17)" (563 stations)
3. "Development Test Set" (25 stations)

**Foreign Key References:**
- Referenced by: `configuration_stations.config_id`
- Referenced by: `update_schedules.config_id`
- Referenced by: `data_collection_logs.config_id`

#### 3. `configuration_stations` (mapping table)
```sql
CREATE TABLE configuration_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    station_id INTEGER NOT NULL,
    priority INTEGER DEFAULT 1,
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT DEFAULT 'system',
    FOREIGN KEY (config_id) REFERENCES station_configurations(id) ON DELETE CASCADE,
    FOREIGN KEY (station_id) REFERENCES station_lists(id) ON DELETE CASCADE,
    UNIQUE(config_id, station_id)
);
```

**Indexes:**
- `idx_config_stations_config` ON config_id
- `idx_config_stations_station` ON station_id

**Purpose:** Many-to-many relationship between configurations and stations

#### 4. `update_schedules` (4 rows)
```sql
CREATE TABLE update_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    schedule_name TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK (data_type IN ('realtime', 'daily', 'both')),
    cron_expression TEXT NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    run_count INTEGER DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (config_id) REFERENCES station_configurations(id) ON DELETE CASCADE
);
```

**Indexes:**
- `idx_schedule_config` ON config_id
- `idx_schedule_enabled` ON is_enabled
- `idx_schedule_next_run` ON next_run

**Purpose:** Automated data collection schedules

#### 5. `data_collection_logs` (execution history)
```sql
CREATE TABLE data_collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    schedule_id INTEGER,
    data_type TEXT NOT NULL CHECK (data_type IN ('realtime', 'daily', 'manual')),
    stations_attempted INTEGER DEFAULT 0,
    stations_successful INTEGER DEFAULT 0,
    stations_failed INTEGER DEFAULT 0,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    error_summary TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    triggered_by TEXT DEFAULT 'system',
    FOREIGN KEY (config_id) REFERENCES station_configurations(id),
    FOREIGN KEY (schedule_id) REFERENCES update_schedules(id)
);
```

**Indexes:**
- `idx_logs_config` ON config_id
- `idx_logs_status` ON status
- `idx_logs_start_time` ON start_time

**Purpose:** Track data collection runs for monitoring

#### 6. `station_collection_errors` (error tracking)
```sql
CREATE TABLE station_collection_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER NOT NULL,
    station_id INTEGER NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT,
    http_status_code INTEGER,
    retry_count INTEGER DEFAULT 0,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (log_id) REFERENCES data_collection_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (station_id) REFERENCES station_lists(id)
);
```

**Indexes:**
- `idx_errors_log` ON log_id
- `idx_errors_station` ON station_id
- `idx_errors_type` ON error_type

**Purpose:** Detailed error logging per station

### Views

#### 1. `configuration_summary`
```sql
SELECT 
    sc.id,
    sc.config_name,
    sc.description,
    sc.is_default,
    sc.is_active,
    COUNT(cs.station_id) as actual_station_count,
    sc.station_count as recorded_count,
    sc.created_date,
    sc.last_modified
FROM station_configurations sc
LEFT JOIN configuration_stations cs ON sc.id = cs.config_id
GROUP BY sc.id, ...
```

**Used By:** Admin Panel - Configurations tab

#### 2. `stations_by_state`
```sql
SELECT 
    state,
    COUNT(*) as total_stations,
    COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_stations,
    source_dataset,
    MIN(latitude) as min_lat,
    MAX(latitude) as max_lat,
    MIN(longitude) as min_lon,
    MAX(longitude) as max_lon
FROM station_lists
GROUP BY state, source_dataset
ORDER BY state, source_dataset
```

**Used By:** Admin Panel - Stations tab

#### 3. `recent_collection_activity`
```sql
SELECT 
    dcl.id,
    sc.config_name,
    dcl.data_type,
    dcl.status,
    dcl.stations_attempted,
    dcl.stations_successful,
    dcl.stations_failed,
    ROUND(dcl.duration_seconds / 60.0, 2) as duration_minutes,
    dcl.start_time,
    dcl.end_time,
    dcl.triggered_by
FROM data_collection_logs dcl
JOIN station_configurations sc ON dcl.config_id = sc.id
ORDER BY dcl.start_time DESC
LIMIT 100
```

**Used By:** Admin Panel - Monitoring tab

---

## Database #2: `usgs_cache.db` (1.1 GB)

### Tables

#### 1. `filters` (1,506 rows) ⚠️ DUPLICATE METADATA
```sql
CREATE TABLE filters (
    site_id TEXT PRIMARY KEY,
    station_name TEXT,
    latitude REAL,
    longitude REAL,
    drainage_area REAL,
    state TEXT,
    county TEXT,
    site_type TEXT,
    agency TEXT,
    huc_code TEXT,
    basin TEXT,
    years_of_record INTEGER,
    num_water_years INTEGER,
    last_data_date TEXT,
    is_active BOOLEAN,
    status TEXT,
    color TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**No Indexes!** (Performance opportunity)

**Used By:**
- Dashboard map loading (app.py)
- All filter operations (search, state, drainage, basin, HUC, realtime)
- Map component rendering

**Duplicate Fields (vs station_lists):**
- site_id = usgs_id ✓
- station_name ✓
- latitude ✓
- longitude ✓
- drainage_area ✓
- state ✓
- huc_code ✓
- is_active ✓

**Unique Fields:**
- county (from USGS metadata)
- site_type (from USGS metadata)
- agency (from USGS metadata)
- basin (derived from HUC)
- years_of_record (computed)
- num_water_years (computed)
- last_data_date (data freshness)
- status (UI state)
- color (UI state)

#### 2. `streamflow_data` (~millions of rows)
```sql
CREATE TABLE streamflow_data (
    site_id TEXT,
    data_json TEXT,
    start_date TEXT,
    end_date TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (site_id, start_date, end_date)
);
```

**Indexes:**
- `idx_streamflow_site` ON site_id
- `idx_streamflow_dates` ON start_date, end_date

**Purpose:** Historical daily streamflow data (stored as JSON blobs)

**Used By:**
- Time series plots
- Water year plots
- Statistics calculations

#### 3. `realtime_discharge` (~thousands of rows)
```sql
CREATE TABLE realtime_discharge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_no TEXT NOT NULL,
    datetime_utc TIMESTAMP NOT NULL,
    discharge_cfs REAL NOT NULL,
    data_quality TEXT DEFAULT 'A',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(site_no, datetime_utc)
);
```

**Indexes:**
- `idx_realtime_site_datetime` ON site_no, datetime_utc
- `idx_realtime_datetime` ON datetime_utc

**Purpose:** Real-time (15-minute) discharge data

**Used By:**
- Water year plot overlay (red line)
- Real-time filter (stations with recent data)
- Dashboard status indicators

#### 4. `data_statistics` (1,506 rows)
```sql
CREATE TABLE data_statistics (
    site_id TEXT PRIMARY KEY,
    stats_json TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**No Additional Indexes**

**Purpose:** Cached statistics (mean, median, percentiles) per station (stored as JSON)

**Used By:**
- Water year plot (mean/median lines)
- Statistics plot
- Filter by data availability

#### 5. `subset_cache` (cache table)
```sql
CREATE TABLE subset_cache (
    id INTEGER PRIMARY KEY,
    subset_config TEXT,
    site_ids TEXT,
    selection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_available INTEGER,
    subset_size INTEGER
);
```

**Purpose:** Cache filtered station subsets for performance

**Usage:** Uncertain - may be legacy or unused

---

## File Dependencies

### Files Reading `station_config.db`

| File | Usage | Critical? |
|------|-------|-----------|
| `station_config_manager.py` | Main interface - all config operations | ✅ CRITICAL |
| `setup_configuration_database.py` | Schema creation | ✅ CRITICAL |
| `populate_station_database.py` | Initial data population | ✅ CRITICAL |
| `sync_station_metadata.py` | Sync station_lists → filters | ⚠️ WILL BE OBSOLETE |
| `configurable_data_collector.py` | Reads station lists for collection | ✅ CRITICAL |
| `smart_scheduler.py` | Reads schedules | ✅ CRITICAL |
| `admin_components.py` | All admin panel operations | ✅ CRITICAL |
| `app.py` | Monitoring tab queries | ✅ CRITICAL |

### Files Reading `usgs_cache.db`

| File | Usage | Critical? |
|------|-------|-----------|
| `app.py` | Dashboard map loading from filters | ✅ CRITICAL |
| `usgs_dashboard/components/map_component.py` | Map rendering | ✅ CRITICAL |
| `usgs_dashboard/viz_manager.py` | Visualizations | ✅ CRITICAL |
| `usgs_dashboard/utils/water_year_datetime.py` | Water year plots | ✅ CRITICAL |
| `usgs_dashboard/data/data_manager.py` | Data loading | ✅ CRITICAL |
| `streamflow_analyzer.py` | Statistics | ✅ CRITICAL |
| `configurable_data_collector.py` | Writes streamflow/realtime data | ✅ CRITICAL |
| `update_daily_discharge_configurable.py` | Writes streamflow_data | ⚠️ Check if used |
| `update_realtime_discharge_configurable.py` | Writes realtime_discharge | ⚠️ Check if used |
| `check_status.py` | Status checks | ⚠️ Utility |
| `enrich_station_metadata.py` | Updates filters table | ⚠️ Utility |
| `fix_binary_data.py` | One-time fix | ❌ Not needed |

### Files Writing to Databases

| File | Writes To | Tables Affected |
|------|-----------|----------------|
| `station_config_manager.py` | station_config.db | ALL tables (CRUD) |
| `populate_station_database.py` | station_config.db | station_lists, configs |
| `sync_station_metadata.py` | BOTH | station_lists → filters |
| `configurable_data_collector.py` | usgs_cache.db | streamflow_data, realtime_discharge |
| `configurable_data_collector.py` | station_config.db | data_collection_logs, errors |
| `enrich_station_metadata.py` | usgs_cache.db | filters (metadata) |
| `admin_components.py` | station_config.db | configs, schedules |

---

## Data Duplication Analysis

### Overlapping Station Metadata

| Field | station_lists | filters | Conflict Resolution |
|-------|---------------|---------|---------------------|
| **usgs_id** | ✓ (PRIMARY) | ✓ (site_id) | Use station_lists |
| **station_name** | ✓ | ✓ | Prefer filters (may have USGS updates) |
| **latitude** | ✓ | ✓ | Use station_lists (source of truth) |
| **longitude** | ✓ | ✓ | Use station_lists (source of truth) |
| **state** | ✓ | ✓ | Use station_lists |
| **drainage_area** | ✓ | ✓ | Use station_lists (fixed binary bug) |
| **huc_code** | ✓ | ✓ | Use station_lists |
| **is_active** | ✓ | ✓ | Use station_lists |
| **nws_id** | ✓ | ❌ | Keep from station_lists |
| **goes_id** | ✓ | ❌ | Keep from station_lists |
| **source_dataset** | ✓ | ❌ | Keep from station_lists |
| **date_added** | ✓ | ❌ | Keep from station_lists |
| **last_verified** | ✓ | ❌ | Keep from station_lists |
| **notes** | ✓ | ❌ | Keep from station_lists |
| **county** | ❌ | ✓ | Merge from filters |
| **site_type** | ❌ | ✓ | Merge from filters |
| **agency** | ❌ | ✓ | Merge from filters |
| **basin** | ❌ | ✓ | Merge from filters (derived) |
| **years_of_record** | ❌ | ✓ | Merge from filters (computed) |
| **num_water_years** | ❌ | ✓ | Merge from filters (computed) |
| **last_data_date** | ❌ | ✓ | Merge from filters (freshness) |
| **status** | ❌ | ✓ | Merge from filters (UI state) |
| **color** | ❌ | ✓ | Merge from filters (UI state) |

**Estimated Duplicated Data:** ~50% of fields duplicated across 1,506 stations

---

## Critical Queries Inventory

### Dashboard Queries (app.py)

#### 1. Load Gauge Data for Map (~line 770)
```python
# CURRENT:
cache_db = sqlite3.connect('data/usgs_cache.db')
df = pd.read_sql_query("""
    SELECT site_id, station_name, latitude, longitude, drainage_area,
           state, county, basin, huc_code, is_active, status, color,
           last_data_date, years_of_record
    FROM filters
    WHERE is_active = 1
    LIMIT ?
""", cache_db, params=[site_limit])

# NEEDS TO BECOME:
db = sqlite3.connect('data/usgs_data.db')
df = pd.read_sql_query("""
    SELECT usgs_id as site_id, station_name, latitude, longitude, drainage_area,
           state, county, basin, huc_code, is_active, status, color,
           last_data_date, years_of_record
    FROM stations
    WHERE is_active = 1
    LIMIT ?
""", db, params=[site_limit])
```

#### 2. Filter Stations (various callbacks)
```python
# Search filter
SELECT * FROM filters WHERE station_name LIKE ? OR site_id LIKE ?

# State filter
SELECT * FROM filters WHERE state IN (?)

# Drainage area filter
SELECT * FROM filters WHERE drainage_area BETWEEN ? AND ?

# Basin filter
SELECT * FROM filters WHERE basin IN (?)

# HUC filter
SELECT * FROM filters WHERE huc_code LIKE ?

# Real-time filter
SELECT f.* FROM filters f
JOIN realtime_discharge r ON f.site_id = r.site_no
WHERE r.datetime_utc > datetime('now', '-24 hours')
GROUP BY f.site_id
```

### Admin Panel Queries (admin_components.py)

#### 1. Configurations Tab
```python
# List configurations
SELECT * FROM configuration_summary

# Get configuration details
SELECT * FROM station_configurations WHERE id = ?

# Get stations in configuration
SELECT s.* FROM station_lists s
JOIN configuration_stations cs ON s.id = cs.station_id
WHERE cs.config_id = ?
```

#### 2. Stations Tab
```python
# List all stations
SELECT * FROM station_lists WHERE is_active = 1

# Group by state
SELECT * FROM stations_by_state

# Search stations
SELECT * FROM station_lists WHERE usgs_id LIKE ? OR station_name LIKE ?
```

#### 3. Schedules Tab
```python
# List schedules
SELECT s.*, c.config_name
FROM update_schedules s
JOIN station_configurations c ON s.config_id = c.id

# Get next run time
SELECT * FROM update_schedules WHERE is_enabled = 1 ORDER BY next_run
```

#### 4. Monitoring Tab
```python
# Recent activity
SELECT * FROM recent_collection_activity LIMIT 100

# Error summary
SELECT error_type, COUNT(*) as count
FROM station_collection_errors
GROUP BY error_type
```

### Data Collection Queries

#### 1. Get Stations to Collect
```python
# From configurable_data_collector.py
config_db = sqlite3.connect('data/station_config.db')

# Get stations for configuration
stations = pd.read_sql_query("""
    SELECT sl.usgs_id, sl.station_name
    FROM station_lists sl
    JOIN configuration_stations cs ON sl.id = cs.station_id
    WHERE cs.config_id = ?
    AND sl.is_active = 1
""", config_db, params=[config_id])
```

#### 2. Write Streamflow Data
```python
# To usgs_cache.db
INSERT OR REPLACE INTO streamflow_data 
(site_id, data_json, start_date, end_date, last_updated)
VALUES (?, ?, ?, ?, ?)
```

#### 3. Write Real-time Data
```python
# To usgs_cache.db
INSERT OR IGNORE INTO realtime_discharge 
(site_no, datetime_utc, discharge_cfs, data_quality)
VALUES (?, ?, ?, ?)
```

#### 4. Log Collection Activity
```python
# To station_config.db
INSERT INTO data_collection_logs 
(config_id, schedule_id, data_type, stations_attempted, stations_successful, 
 stations_failed, start_time, end_time, duration_seconds, status, triggered_by)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

---

## Foreign Key Relationships

### station_config.db

```
station_configurations (id)
├──[1:M]→ configuration_stations (config_id)
├──[1:M]→ update_schedules (config_id)
└──[1:M]→ data_collection_logs (config_id)

station_lists (id)
├──[1:M]→ configuration_stations (station_id)
└──[1:M]→ station_collection_errors (station_id)

update_schedules (id)
└──[1:M]→ data_collection_logs (schedule_id)

data_collection_logs (id)
└──[1:M]→ station_collection_errors (log_id)
```

### usgs_cache.db

```
filters (site_id)
└──[1:M]→ (implicit) streamflow_data (site_id) [NO FK!]
└──[1:M]→ (implicit) realtime_discharge (site_no) [NO FK!]
└──[1:M]→ (implicit) data_statistics (site_id) [NO FK!]
```

**⚠️ Note:** usgs_cache.db has NO foreign key constraints! This is a data integrity risk.

---

## Performance Considerations

### Missing Indexes in usgs_cache.db

| Table | Missing Index | Impact |
|-------|---------------|--------|
| `filters` | ANY | Dashboard map queries do full table scan! |
| `filters` | state | State filter slow |
| `filters` | basin | Basin filter slow |
| `filters` | drainage_area | Drainage filter slow |
| `filters` | is_active | Active filter slow |

**Recommendation:** Add indexes in unified database

### Query Performance Baseline

Need to benchmark BEFORE migration:
- [ ] Dashboard load time (SELECT * FROM filters)
- [ ] State filter (SELECT * FROM filters WHERE state = ?)
- [ ] Complex filter (multiple WHERE clauses)
- [ ] Configuration stations join
- [ ] Recent collection activity view

---

## Migration Complexity Assessment

### Schema Changes Required

| Change Type | Complexity | Risk |
|-------------|-----------|------|
| Merge station metadata | HIGH | MEDIUM |
| Remap station IDs | HIGH | LOW (auto-increment) |
| Copy streamflow data | LOW | LOW (direct copy) |
| Copy collection logs | MEDIUM | LOW (need to remap IDs) |
| Update all queries | HIGH | HIGH (easy to miss) |
| Update foreign keys | MEDIUM | MEDIUM (must validate) |
| Create new indexes | LOW | LOW |
| Create views | LOW | LOW |

### Code Changes Required

| File | Lines Changed | Complexity | Risk |
|------|---------------|-----------|------|
| station_config_manager.py | ~50 | MEDIUM | HIGH (core library) |
| app.py | ~100 | HIGH | HIGH (main app) |
| admin_components.py | ~150 | HIGH | HIGH (all tabs) |
| configurable_data_collector.py | ~30 | MEDIUM | HIGH (data collection) |
| map_component.py | ~20 | LOW | MEDIUM |
| viz_manager.py | ~20 | LOW | MEDIUM |
| sync_station_metadata.py | DELETE | LOW | LOW (obsolete) |
| populate_station_database.py | ~40 | MEDIUM | MEDIUM |
| **TOTAL** | **~410 lines** | **HIGH** | **HIGH** |

---

## Risk Assessment

### Data Loss Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Station metadata lost | LOW | CRITICAL | Backups + validation |
| Streamflow data lost | LOW | CRITICAL | Row count checks |
| Configuration lost | LOW | HIGH | Backup + verify |
| Foreign key violations | MEDIUM | HIGH | Validation script |
| ID remapping errors | MEDIUM | HIGH | Test on copy first |

### Functional Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Dashboard broken | MEDIUM | CRITICAL | Extensive testing |
| Admin panel broken | MEDIUM | CRITICAL | Test all 5 tabs |
| Data collection broken | MEDIUM | CRITICAL | Manual test run |
| Queries slow | LOW | MEDIUM | Benchmarking |
| Views don't work | LOW | MEDIUM | Test all views |

### Deployment Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Cannot rollback | LOW | CRITICAL | Tested rollback procedure |
| Production downtime | MEDIUM | HIGH | Staging test first |
| Config conflicts | MEDIUM | MEDIUM | Clear loading priority |
| Missing dependencies | LOW | MEDIUM | Requirements check |

---

## Recommended Migration Order

1. ✅ **Create backups** (DONE FIRST!)
2. ✅ **Create unified schema** with all tables
3. ✅ **Migrate station_lists + filters → stations** (merge carefully)
4. ✅ **Migrate configurations/schedules** (remap station IDs)
5. ✅ **Migrate streamflow_data** (direct copy)
6. ✅ **Migrate realtime_discharge** (direct copy)
7. ✅ **Migrate data_statistics** (direct copy)
8. ✅ **Migrate collection_logs** (remap IDs)
9. ✅ **Create views** (configuration_summary, etc.)
10. ✅ **Validate migration** (row counts, FKs, spot checks)
11. ✅ **Update code** (systematic file-by-file)
12. ✅ **Test extensively** (dashboard, admin, collection)
13. ✅ **Performance benchmark** (compare to baseline)
14. ✅ **Deploy** (with rollback ready)

---

## Success Criteria

### Data Integrity
- [ ] All 1,506 stations migrated
- [ ] All streamflow_data rows present
- [ ] All realtime_discharge rows present
- [ ] All configurations preserved
- [ ] All schedules preserved
- [ ] All collection logs preserved
- [ ] All foreign keys valid
- [ ] No NULL values in NOT NULL columns

### Functionality
- [ ] Dashboard loads map with all stations
- [ ] All 6 filters work correctly
- [ ] Station selection/highlighting works
- [ ] All 3 plot types render
- [ ] Admin panel all 5 tabs work
- [ ] Data collection runs successfully
- [ ] Monitoring tab shows activity
- [ ] No console errors

### Performance
- [ ] Dashboard load time ≤ baseline
- [ ] Filter response time ≤ baseline
- [ ] Plot rendering time ≤ baseline
- [ ] No query >2x slower than baseline

---

## Next Steps

1. ✅ **Complete Phase 1** (Analysis) - THIS DOCUMENT
2. ⏳ **Phase 2:** Design unified schema (DATABASE_MERGER_PLAN.md already has this!)
3. ⏳ **Phase 3:** Create migration script (migrate_to_unified_db.py)
4. ⏳ **Phase 4:** Test migration on copy
5. ⏳ **Phase 5:** Update all code
6. ⏳ **Phase 6:** Test everything
7. ⏳ **Phase 7:** Deploy

**Estimated Timeline:** 70 hours (~9 days of focused work)

**Recommendation:** Proceed with caution. This is a major refactoring that touches every component of the system. The benefits (eliminating duplication, version-controlled configs, simpler deployment) justify the effort, but must be executed methodically with comprehensive testing and rollback capability.

---

## Appendix: Complete File List

### Python Files with Database Dependencies (21 files)

1. `station_config_manager.py` - station_config.db
2. `setup_configuration_database.py` - station_config.db
3. `populate_station_database.py` - station_config.db
4. `sync_station_metadata.py` - BOTH databases
5. `configurable_data_collector.py` - BOTH databases
6. `smart_scheduler.py` - usgs_cache.db
7. `admin_components.py` - station_config.db
8. `app.py` - BOTH databases
9. `usgs_dashboard/components/map_component.py` - usgs_cache.db
10. `usgs_dashboard/viz_manager.py` - usgs_cache.db
11. `usgs_dashboard/utils/water_year_datetime.py` - usgs_cache.db
12. `usgs_dashboard/data/data_manager.py` - usgs_cache.db
13. `streamflow_analyzer.py` - usgs_cache.db
14. `check_status.py` - usgs_cache.db
15. `enrich_station_metadata.py` - usgs_cache.db
16. `fix_binary_data.py` - usgs_cache.db (one-time fix)
17. `update_daily_discharge_configurable.py` - usgs_cache.db (check if used)
18. `update_realtime_discharge_configurable.py` - usgs_cache.db (check if used)
19. `update_database_schema.py` - usgs_cache.db (schema updates)
20. `Archive/legacy_collectors/update_daily_discharge.py` - usgs_cache.db (LEGACY)
21. `Archive/legacy_collectors/update_realtime_discharge.py` - usgs_cache.db (LEGACY)

### Files to Delete After Migration

- `sync_station_metadata.py` (no longer needed - single database)
- `fix_binary_data.py` (one-time fix already applied)

### Files to Verify Still Used

- `update_daily_discharge_configurable.py` (might be replaced by configurable_data_collector.py)
- `update_realtime_discharge_configurable.py` (might be replaced by configurable_data_collector.py)
- `check_status.py` (utility - check if actively used)

---

**Analysis Complete! ✅**

Ready to proceed to Phase 2: Design Unified Schema
