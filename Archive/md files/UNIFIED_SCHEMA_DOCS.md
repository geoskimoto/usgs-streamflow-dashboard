# Unified Database Schema Documentation

**File:** `unified_database_schema.sql`  
**Database:** `data/usgs_data.db`  
**Version:** 1.0  
**Date:** November 6, 2025

---

## Overview

This schema merges two previous databases:
- `station_config.db` (624 KB) - Configurations, schedules, logs
- `usgs_cache.db` (1.1 GB) - Station metadata, streamflow data

Into a single unified database with:
- ✅ **No data duplication** - Single source of truth for station metadata
- ✅ **Proper foreign keys** - Data integrity enforced
- ✅ **Optimized indexes** - Fast queries
- ✅ **Backward-compatible views** - Existing queries still work
- ✅ **Automated triggers** - Maintain data consistency

---

## Schema Statistics

| Category | Count |
|----------|-------|
| **Tables** | 12 |
| **Views** | 6 |
| **Indexes** | 45 |
| **Triggers** | 5 |
| **Foreign Keys** | 10 |

---

## Table Structure

### Core Tables

#### 1. `stations` (1,506 rows expected)
**Purpose:** Master station metadata (merged from station_lists + filters)

**Key Fields:**
- `id` - Auto-increment primary key
- `usgs_id` - USGS site number (UNIQUE)
- `nws_id`, `goes_id` - Additional identifiers
- `station_name` - Official name
- `state`, `county` - Location
- `latitude`, `longitude` - Coordinates
- `drainage_area` - Square miles
- `huc_code`, `basin` - Hydrologic units
- `years_of_record`, `num_water_years` - Data availability
- `is_active`, `status` - Operational state
- `source_dataset` - Provenance
- `color` - UI state

**Indexes:** 10 indexes including composite indexes for common filters

**Foreign Key References:**
- Referenced by: `configuration_stations.station_id`
- Referenced by: `streamflow_data.site_id`
- Referenced by: `realtime_discharge.site_no`
- Referenced by: `data_statistics.site_id`
- Referenced by: `station_errors.station_id`

#### 2. `configurations` (3+ rows)
**Purpose:** Station collection configurations

**Key Fields:**
- `config_name` - Unique name (e.g., "Pacific Northwest Full")
- `description` - Human-readable description
- `station_count` - Cached count (updated by triggers)
- `is_default` - Default configuration flag
- `is_active` - Whether available

**Relations:** One-to-many with `configuration_stations`, `schedules`, `collection_logs`

#### 3. `configuration_stations` (mapping table)
**Purpose:** Many-to-many relationship between configurations and stations

**Key Fields:**
- `config_id` → `configurations.id`
- `station_id` → `stations.id`
- `priority` - Collection order

**Triggers:** Automatically updates `configurations.station_count`

#### 4. `schedules` (4+ rows)
**Purpose:** Automated data collection schedules

**Key Fields:**
- `config_id` - Which configuration to run
- `schedule_name` - Human-readable name
- `data_type` - 'realtime', 'daily', 'both'
- `cron_expression` - Cron format timing
- `interval_minutes` - Simple interval alternative
- `is_enabled` - Active flag
- `last_run`, `next_run` - Execution tracking
- `run_count` - Total executions

#### 5. `streamflow_data` (millions of rows)
**Purpose:** Historical daily streamflow data

**Key Fields:**
- `site_id` → `stations.usgs_id` (FK enforced!)
- `data_json` - JSON blob with daily data
- `start_date`, `end_date` - Date range
- `last_updated` - When cached

**Indexes:** Optimized for site + date range queries

#### 6. `realtime_discharge` (thousands of rows)
**Purpose:** Real-time (15-minute) discharge data

**Key Fields:**
- `site_no` → `stations.usgs_id` (FK enforced!)
- `datetime_utc` - UTC timestamp
- `discharge_cfs` - Flow rate
- `data_quality` - USGS quality code (A/P/E/R/U)

**Indexes:** Optimized for site + datetime queries

#### 7. `data_statistics` (1,506 rows)
**Purpose:** Cached statistics per station

**Key Fields:**
- `site_id` → `stations.usgs_id` (FK enforced!)
- `stats_json` - JSON blob with mean, median, percentiles

#### 8. `subset_cache` (cache table)
**Purpose:** Cached filtered station subsets

**Key Fields:**
- `subset_config` - JSON filter configuration
- `site_ids` - Comma-separated IDs
- `total_available`, `subset_size` - Counts

#### 9. `collection_logs` (execution history)
**Purpose:** Track data collection runs

**Key Fields:**
- `config_id` → `configurations.id`
- `schedule_id` → `schedules.id` (nullable)
- `data_type` - What was collected
- `stations_attempted/successful/failed` - Counts
- `start_time`, `end_time`, `duration_seconds` - Timing
- `status` - 'running', 'completed', 'failed', 'cancelled', 'partial'
- `triggered_by` - Who initiated

**Triggers:** Updates `schedules.run_count` on completion

#### 10. `station_errors` (detailed errors)
**Purpose:** Per-station error tracking

**Key Fields:**
- `log_id` → `collection_logs.id`
- `station_id` → `stations.id`
- `error_type` - Category: 'network', 'parse', 'validation', 'timeout', etc.
- `error_message` - Details
- `http_status_code` - If network error
- `retry_count` - Attempts made

---

## Views

### 1. `configuration_summary`
**Purpose:** Configuration overview with station counts

**Columns:**
- Config details (id, name, description, flags)
- `actual_station_count` - From junction table
- `recorded_count` - Cached value
- Metadata (dates, creator)

**Used By:** Admin Panel - Configurations tab

### 2. `stations_by_state`
**Purpose:** Station counts grouped by state

**Columns:**
- State code
- Total/active station counts
- Source dataset
- Geographic bounds (min/max lat/lon)

**Used By:** Admin Panel - Stations tab

### 3. `recent_collection_activity`
**Purpose:** Recent data collection runs (last 100)

**Columns:**
- Run details (config, data type, status)
- Statistics (attempted/successful/failed)
- Timing (start, end, duration in minutes)
- Metadata (triggered by, schedule name)

**Used By:** Admin Panel - Monitoring tab

### 4. `stations_with_realtime`
**Purpose:** Stations with recent real-time data (last 24 hours)

**Columns:**
- Station identifiers and metadata
- `last_realtime_update` - Most recent timestamp

**Used By:** Dashboard - Real-time filter

### 5. `station_data_availability`
**Purpose:** Comprehensive data availability per station

**Columns:**
- Station identifiers
- Data counts (streamflow chunks, realtime points)
- Recent data flags
- Summary statistics

**Used By:** Admin Panel, Data quality checks

### 6. `error_summary`
**Purpose:** Error statistics (last 7 days)

**Columns:**
- Error type
- Error count
- Affected station count
- Most recent occurrence

**Used By:** Admin Panel - Monitoring tab

---

## Indexes

### Performance-Critical Indexes

**stations table (10 indexes):**
```sql
idx_stations_usgs_id          -- Unique lookups
idx_stations_state            -- State filter
idx_stations_basin            -- Basin filter
idx_stations_huc              -- HUC filter
idx_stations_active           -- Active filter
idx_stations_status           -- Status checks
idx_stations_drainage         -- Drainage area filter
idx_stations_location         -- Spatial queries (lat/lon)
idx_stations_source           -- Source dataset filter
```

**Composite indexes for common query patterns:**
```sql
idx_stations_state_active     -- State + active filter
idx_stations_basin_active     -- Basin + active filter
idx_stations_state_drainage   -- State + drainage range
idx_stations_active_status    -- Active + status checks
```

**streamflow_data table:**
```sql
idx_streamflow_site           -- Site lookups
idx_streamflow_dates          -- Date range queries
idx_streamflow_updated        -- Cache freshness checks
```

**realtime_discharge table:**
```sql
idx_realtime_site_datetime    -- Site + time queries (most common)
idx_realtime_datetime         -- Time-based queries
idx_realtime_site             -- Site-based queries
idx_realtime_quality          -- Quality filtering
```

**All other tables:** Indexes on foreign keys, status fields, timestamps

---

## Foreign Key Relationships

```
stations (id, usgs_id)
├──[1:M]→ configuration_stations (station_id)
├──[1:M]→ streamflow_data (site_id) ✅ FK enforced
├──[1:M]→ realtime_discharge (site_no) ✅ FK enforced
├──[1:M]→ data_statistics (site_id) ✅ FK enforced
└──[1:M]→ station_errors (station_id)

configurations (id)
├──[1:M]→ configuration_stations (config_id)
├──[1:M]→ schedules (config_id)
└──[1:M]→ collection_logs (config_id)

schedules (id)
└──[1:M]→ collection_logs (schedule_id)

collection_logs (id)
└──[1:M]→ station_errors (log_id)
```

**Note:** Foreign keys are **enforced** with `PRAGMA foreign_keys = ON`

---

## Triggers

### 1. `update_config_count_insert` / `update_config_count_delete`
**Purpose:** Automatically update `configurations.station_count` when stations added/removed

**Fires:** After INSERT/DELETE on `configuration_stations`

**Action:** Recalculates count for affected configuration

### 2. `update_config_modified`
**Purpose:** Timestamp configuration changes

**Fires:** After UPDATE on `configurations`

**Action:** Sets `last_modified = CURRENT_TIMESTAMP`

### 3. `increment_schedule_count`
**Purpose:** Track schedule execution count

**Fires:** After INSERT on `collection_logs` (when status = 'completed' and schedule_id not null)

**Action:** Increments `schedules.run_count`, updates `last_run`

### 4. `update_station_timestamp`
**Purpose:** Timestamp station metadata changes

**Fires:** After UPDATE on `stations`

**Action:** Sets `last_updated = CURRENT_TIMESTAMP`

---

## Data Integrity Constraints

### CHECK Constraints

**stations table:**
- `state` - Must be valid US state/territory code
- `latitude` - Between -90 and 90
- `longitude` - Between -180 and 180
- `drainage_area` - Non-negative or NULL
- `years_of_record` - Non-negative or NULL
- `status` - Must be 'active', 'inactive', 'error', 'pending', 'unknown'
- `source_dataset` - Must be valid source

**schedules table:**
- `data_type` - Must be 'realtime', 'daily', 'both'
- `interval_minutes` - Positive or NULL

**collection_logs table:**
- `status` - Must be 'running', 'completed', 'failed', 'cancelled', 'partial'
- `stations_successful + stations_failed <= stations_attempted`
- All counts non-negative

**realtime_discharge table:**
- `discharge_cfs` - Non-negative
- `data_quality` - Must be valid USGS code (A/P/E/R/U)

**station_errors table:**
- `error_type` - Must be valid category
- `http_status_code` - 100-599 range or NULL

---

## Migration Notes

### Field Mappings from Old Databases

**From `station_lists` (station_config.db):**
```
id                  → stations.id (remapped)
usgs_id             → stations.usgs_id ✓
nws_id              → stations.nws_id ✓
goes_id             → stations.goes_id ✓
station_name        → stations.station_name ✓
state               → stations.state ✓
latitude            → stations.latitude ✓
longitude           → stations.longitude ✓
huc_code            → stations.huc_code ✓
drainage_area       → stations.drainage_area ✓
source_dataset      → stations.source_dataset ✓
is_active           → stations.is_active ✓
date_added          → stations.date_added ✓
last_verified       → stations.last_verified ✓
notes               → stations.notes ✓
```

**From `filters` (usgs_cache.db):**
```
site_id             → stations.usgs_id (merge key)
station_name        → stations.station_name (prefer if different)
latitude            → stations.latitude (prefer station_lists)
longitude           → stations.longitude (prefer station_lists)
drainage_area       → stations.drainage_area (prefer station_lists)
state               → stations.state (prefer station_lists)
county              → stations.county ✓ NEW
site_type           → stations.site_type ✓ NEW
agency              → stations.agency ✓ NEW
huc_code            → stations.huc_code (prefer station_lists)
basin               → stations.basin ✓ NEW
years_of_record     → stations.years_of_record ✓ NEW
num_water_years     → stations.num_water_years ✓ NEW
last_data_date      → stations.last_data_date ✓ NEW
is_active           → stations.is_active (prefer station_lists)
status              → stations.status ✓ NEW
color               → stations.color ✓ NEW
last_updated        → stations.last_updated ✓ NEW
```

### Conflict Resolution Priority

When merging `station_lists` + `filters`:

1. **Use station_lists for core metadata:**
   - usgs_id, latitude, longitude, state
   - drainage_area (fixed binary bug!)
   - huc_code, is_active

2. **Use filters for USGS metadata:**
   - county, site_type, agency (from USGS API)
   - basin (derived from HUC)

3. **Use filters for computed fields:**
   - years_of_record, num_water_years
   - last_data_date

4. **Use filters for UI state:**
   - status, color

5. **Merge station_name:**
   - Prefer filters if different (may have USGS updates)
   - Log conflicts

---

## Query Translation Guide

### Common Query Updates

**OLD (filters table):**
```sql
SELECT site_id, station_name, latitude, longitude
FROM filters
WHERE is_active = 1 AND state = 'WA'
```

**NEW (stations table):**
```sql
SELECT usgs_id as site_id, station_name, latitude, longitude
FROM stations
WHERE is_active = 1 AND state = 'WA'
```

**OLD (two database join):**
```sql
-- In station_config.db:
SELECT sl.usgs_id FROM station_lists sl
JOIN configuration_stations cs ON sl.id = cs.station_id
WHERE cs.config_id = ?

-- Then in usgs_cache.db:
SELECT * FROM filters WHERE site_id IN (...)
```

**NEW (single database join):**
```sql
SELECT s.* FROM stations s
JOIN configuration_stations cs ON s.id = cs.station_id
WHERE cs.config_id = ?
```

---

## Performance Benchmarks

### Expected Query Performance

| Query Type | Expected Time | Index Used |
|------------|---------------|------------|
| Load all active stations | < 50ms | idx_stations_active |
| Filter by state | < 10ms | idx_stations_state |
| Filter by state + active | < 5ms | idx_stations_state_active |
| Get station by usgs_id | < 1ms | idx_stations_usgs_id |
| Get streamflow data | < 20ms | idx_streamflow_site |
| Get realtime data | < 10ms | idx_realtime_site_datetime |
| Configuration summary | < 50ms | View with joins |

### Optimization Notes

1. **Dashboard map loading:** Uses `idx_stations_active` or state-specific indexes
2. **Complex filters:** Composite indexes for common combinations
3. **Real-time filter:** View `stations_with_realtime` pre-filters recent data
4. **Admin panel:** Views pre-aggregate common queries

---

## Validation Queries

### After Migration, Run These:

```sql
-- 1. Check station count
SELECT COUNT(*) FROM stations;  -- Should be 1,506

-- 2. Check no missing metadata
SELECT COUNT(*) FROM stations WHERE station_name IS NULL;  -- Should be 0
SELECT COUNT(*) FROM stations WHERE latitude IS NULL;      -- Should be 0

-- 3. Check foreign keys valid
PRAGMA foreign_key_check;  -- Should return no results

-- 4. Check data counts match
SELECT COUNT(*) FROM streamflow_data;      -- Compare to old DB
SELECT COUNT(*) FROM realtime_discharge;   -- Compare to old DB
SELECT COUNT(*) FROM configurations;       -- Should be 3

-- 5. Test views work
SELECT COUNT(*) FROM configuration_summary;
SELECT COUNT(*) FROM stations_by_state;
SELECT COUNT(*) FROM recent_collection_activity;

-- 6. Check indexes created
SELECT COUNT(*) FROM sqlite_master WHERE type = 'index';  -- Should be 45+

-- 7. Check triggers exist
SELECT COUNT(*) FROM sqlite_master WHERE type = 'trigger';  -- Should be 5

-- 8. Database integrity
PRAGMA integrity_check;  -- Should return 'ok'
```

---

## Schema Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-06 | Initial unified schema design |

---

## Next Steps

1. ✅ **Schema designed** - This document
2. ⏳ **Create migration script** - `migrate_to_unified_db.py`
3. ⏳ **Test on copy** - Validate data integrity
4. ⏳ **Update code** - Modify all Python files
5. ⏳ **Deploy** - Production migration

**See:** `DATABASE_MERGER_PLAN.md` for complete implementation plan
