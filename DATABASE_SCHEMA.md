# USGS Streamflow Dashboard - Database Schema Documentation
**Last Updated:** 2025-11-10  
**Database:** `data/usgs_data.db` (3.57 MB)  
**Total Stations:** 1,506

---

## 📊 Core Data Tables

### 1. stations (1,506 rows)
**Purpose:** Master list of all USGS gauge stations

**Schema:**
```sql
CREATE TABLE stations (
    site_id TEXT PRIMARY KEY,           -- USGS station ID (e.g., "10068500")
    station_name TEXT,                   -- Station full name
    state TEXT,                          -- Two-letter state code
    latitude REAL,                       -- Geographic coordinates
    longitude REAL,
    huc_code TEXT,                       -- Hydrologic Unit Code
    drainage_area REAL,                  -- Drainage basin area
    data_source TEXT,                    -- Source of station data (HADS, NWIS, etc.)
    is_active INTEGER DEFAULT 1,         -- Currently monitored (1/0)
    has_realtime INTEGER DEFAULT 0,      -- Has realtime data available (1/0)
    source_dataset TEXT,                 -- Original dataset name
    nws_id TEXT,                         -- NWS station identifier
    goes_id TEXT,                        -- GOES satellite identifier
    date_added TEXT,                     -- Timestamp when added
    last_updated TEXT                    -- Timestamp when last modified
);
CREATE INDEX idx_stations_state ON stations(state);
```

**Key Points:**
- Primary identifier is `site_id` (consistent across all tables)
- `has_realtime` flag indicates stations with 15-minute data
- `is_active=1` means station is currently being monitored

---

### 2. realtime_discharge (18,076 rows)
**Purpose:** 15-minute interval realtime discharge data from USGS IV service

**Schema:**
```sql
CREATE TABLE realtime_discharge (
    site_id TEXT NOT NULL,               -- References stations(site_id)
    datetime_utc TEXT NOT NULL,          -- Timestamp in UTC
    discharge_cfs REAL,                  -- Discharge in cubic feet per second
    qualifiers TEXT,                     -- USGS data quality codes
    last_updated TEXT,                   -- When record was fetched
    PRIMARY KEY (site_id, datetime_utc)
);
CREATE INDEX idx_realtime_discharge_site_id ON realtime_discharge(site_id);
CREATE INDEX idx_realtime_discharge_datetime ON realtime_discharge(datetime_utc);
```

**Data Source:** USGS NWIS Instantaneous Values (IV) API  
**Endpoint:** `https://waterservices.usgs.gov/nwis/iv`  
**Collection Frequency:** Hourly (Schedule 1)

---

### 3. streamflow_data (0 rows - awaiting daily collection)
**Purpose:** Daily aggregated historical discharge data from USGS DV service

**Schema:**
```sql
CREATE TABLE streamflow_data (
    site_id TEXT NOT NULL,               -- References stations(site_id)
    start_date TEXT NOT NULL,            -- Date (YYYY-MM-DD)
    end_date TEXT,                       -- For date ranges
    mean_discharge REAL,                 -- Daily mean discharge
    min_discharge REAL,                  -- Daily minimum
    max_discharge REAL,                  -- Daily maximum
    data_quality TEXT,                   -- Quality assessment
    last_updated TEXT,                   -- When record was fetched
    PRIMARY KEY (site_id, start_date),
    FOREIGN KEY (site_id) REFERENCES stations(site_id)
);
CREATE INDEX idx_streamflow_data_site_id ON streamflow_data(site_id);
CREATE INDEX idx_streamflow_data_date ON streamflow_data(start_date);
```

**Data Source:** USGS NWIS Daily Values (DV) API  
**Endpoint:** `https://waterservices.usgs.gov/nwis/dv`  
**Collection Frequency:** Daily at 2:00 AM (Schedule 3)

---

### 4. filters (1,506 rows) ⭐ CRITICAL
**Purpose:** Enriched metadata for map hover labels and plot displays

**Schema:**
```sql
CREATE TABLE filters (
    site_id TEXT PRIMARY KEY,            -- References stations(site_id)
    station_name TEXT,                   -- Station name
    latitude REAL,                       -- Geographic coordinates
    longitude REAL,
    drainage_area REAL,                  -- Fetched from USGS site service
    state TEXT,                          -- Two-letter state code
    county TEXT,                         -- Fetched from USGS
    site_type TEXT,                      -- Station type (stream, lake, etc.)
    agency TEXT,                         -- Operating agency (USGS, etc.)
    huc_code TEXT,                       -- Hydrologic Unit Code
    basin TEXT,                          -- River basin name
    years_of_record INTEGER,             -- Calculated: MAX(year) - MIN(year)
    num_water_years INTEGER,             -- Calculated: COUNT(DISTINCT water_year)
    last_data_date TEXT,                 -- Most recent data point
    is_active BOOLEAN,                   -- Currently monitored
    status TEXT,                         -- Operational status
    color TEXT,                          -- Display color on map
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Critical Notes:**
- **THIS IS THE SOURCE** for map hover labels (drainage_area, years_of_record)
- Populated by `enrich_station_metadata.py` after daily data collection
- Base fields copied from `stations`, statistics calculated from `streamflow_data`
- Metadata (drainage_area, county) fetched from USGS Site Service API

**Enrichment Process:**
1. Runs automatically after `data_type='daily'` collections
2. Calculates `years_of_record` and `num_water_years` from collected data
3. Fetches `drainage_area`, `county`, `site_type` from USGS
4. Updates `last_updated` timestamp

---

## ⚙️ Configuration & Scheduling Tables

### 5. configurations (3 rows)
**Purpose:** Define station groupings for different collection purposes

**Schema:**
```sql
CREATE TABLE configurations (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,               -- Comma-separated list of station IDs
    config_name TEXT NOT NULL,           -- Configuration name
    description TEXT,                    -- Human-readable purpose
    period_of_record_start TEXT,
    period_of_record_end TEXT,
    data_completeness REAL,              -- Quality metric (0.0-1.0)
    monitoring_status TEXT,              -- Active, inactive, etc.
    priority_level INTEGER,              -- Collection priority
    is_default INTEGER DEFAULT 0,        -- Whether this is default config
    date_created TEXT,
    last_modified TEXT,
    is_active INTEGER DEFAULT 1,         -- Whether config is enabled
    FOREIGN KEY (site_id) REFERENCES stations(site_id),
    UNIQUE(site_id, config_name)
);
CREATE INDEX idx_configurations_site_id ON configurations(site_id);
CREATE INDEX idx_configurations_active ON configurations(is_active);
```

**Current Configurations:**
1. **Pacific Northwest Full** (943 stations) - Default, all PNW HADS stations
2. **Columbia River Basin (HUC17)** (897 stations) - HUC 17 watershed
3. **Development Test Set** (25 stations) - Testing subset

**Design Note:** `site_id` column stores comma-separated station IDs (denormalized design)

---

### 6. schedules (4 rows)
**Purpose:** Define when and what type of data to collect for each configuration

**Schema:**
```sql
CREATE TABLE schedules (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,          -- References configurations(config_id)
    schedule_name TEXT,                  -- Human-readable name
    data_type TEXT DEFAULT 'realtime',   -- 'realtime', 'daily', or 'both'
    schedule_type TEXT NOT NULL,         -- 'cron' or 'interval'
    schedule_value TEXT NOT NULL,        -- Cron expression or interval seconds
    is_enabled INTEGER DEFAULT 1,        -- Whether schedule is active
    date_created TEXT,
    last_modified TEXT,
    FOREIGN KEY (config_id) REFERENCES configurations(config_id)
);
CREATE INDEX idx_schedules_config_id ON schedules(config_id);
```

**Current Schedules:**
| ID | Name | Data Type | Schedule | Status |
|----|------|-----------|----------|--------|
| 1 | Hourly Full Update | realtime | `0 * * * *` (hourly) | ✅ Enabled |
| 2 | 15-Minute Realtime (Dev) | realtime | `900` sec (15 min) | ❌ Disabled |
| 3 | Daily Full Collection | both | `0 2 * * *` (daily 2 AM) | ✅ Enabled |
| 4 | Weekly Metadata Refresh | daily | `0 3 * * 0` (Sun 3 AM) | ✅ Enabled |

**Data Type Behavior:**
- `realtime`: Collects from `/nwis/iv` → stores in `realtime_discharge`
- `daily`: Collects from `/nwis/dv` → stores in `streamflow_data` → runs enrichment
- `both`: Runs both realtime and daily collections sequentially

---

## 📝 Logging & Error Tracking

### 7. collection_logs (6 rows)
**Purpose:** Track data collection runs for monitoring and debugging

**Schema:**
```sql
CREATE TABLE collection_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER,                   -- References configurations(config_id)
    config_name TEXT,                    -- Configuration name
    data_type TEXT,                      -- 'realtime', 'daily', or 'both'
    start_time TEXT,                     -- Collection start timestamp
    end_time TEXT,                       -- Collection end timestamp
    status TEXT,                         -- 'running', 'completed', 'failed'
    stations_attempted INTEGER DEFAULT 0,
    stations_successful INTEGER DEFAULT 0,
    duration_seconds REAL,               -- How long collection took
    triggered_by TEXT DEFAULT 'manual',  -- 'manual', 'scheduled', 'command_line'
    error_message TEXT,                  -- If failed, error details
    FOREIGN KEY (config_id) REFERENCES configurations(config_id)
);
CREATE INDEX idx_collection_logs_config_id ON collection_logs(config_id);
CREATE INDEX idx_collection_logs_start_time ON collection_logs(start_time);
```

**Used By:** Admin panel Monitoring tab (auto-refreshes every 10 seconds)

---

### 8. station_errors (0 rows)
**Purpose:** Track recurring errors for specific stations

**Schema:**
```sql
CREATE TABLE station_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,               -- References stations(site_id)
    error_type TEXT NOT NULL,            -- Error category
    error_message TEXT,                  -- Full error details
    first_occurred TEXT,                 -- When first seen
    last_occurred TEXT,                  -- When last seen
    occurrence_count INTEGER DEFAULT 1,  -- How many times
    is_resolved INTEGER DEFAULT 0,       -- Whether fixed
    FOREIGN KEY (site_id) REFERENCES stations(site_id)
);
CREATE INDEX idx_station_errors_site_id ON station_errors(site_id);
```

---

## 🔍 Views & Utility Tables

### 9. configuration_summary (VIEW)
**Purpose:** Denormalized view joining configurations with their schedules

```sql
CREATE VIEW configuration_summary AS
SELECT 
    c.config_id as id,
    c.config_name,
    c.description,
    c.is_active,
    c.is_default,
    COUNT(DISTINCT c.site_id) as actual_station_count,
    c.date_created as created_date,
    c.last_modified,
    s.schedule_id,
    COALESCE(s.is_enabled, 0) as schedule_enabled,
    s.schedule_type,
    s.schedule_value,
    s.last_modified as schedule_last_modified
FROM configurations c
LEFT JOIN schedules s ON c.config_id = s.config_id
GROUP BY c.config_id, c.config_name, c.description, c.is_active, c.is_default,
         c.date_created, c.last_modified, s.schedule_id, s.is_enabled,
         s.schedule_type, s.schedule_value, s.last_modified;
```

**Used By:** Admin panel Configurations tab

---

### 10. recent_collection_activity (VIEW)
**Purpose:** Recent collection logs formatted for monitoring display

```sql
CREATE VIEW recent_collection_activity AS
SELECT 
    log_id,
    config_id,
    config_name,
    data_type,
    start_time,
    end_time,
    status,
    stations_attempted,
    stations_successful,
    ROUND(duration_seconds / 60.0, 1) as duration_minutes,
    triggered_by
FROM collection_logs
ORDER BY start_time DESC;
```

**Used By:** Admin panel Monitoring tab

---

### 11. data_statistics (0 rows - currently unused)
**Purpose:** JSON storage for precomputed statistics

```sql
CREATE TABLE data_statistics (
    site_id TEXT PRIMARY KEY,
    stats_json TEXT,                     -- JSON-encoded statistics
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 12. subset_cache (0 rows - currently unused)
**Purpose:** Cache filtered station subsets

```sql
CREATE TABLE subset_cache (
    id INTEGER PRIMARY KEY,
    subset_config TEXT,                  -- Filter configuration
    site_ids TEXT,                       -- Comma-separated station IDs
    selection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_available INTEGER,
    subset_size INTEGER
);
```

---

## 🔄 Data Flow Architecture

### Collection Workflow
```
User clicks "Run Now" (Admin Panel)
    ↓
app.py: run_schedule_now() callback
    ↓
subprocess: python configurable_data_collector.py 
            --config "Pacific Northwest Full" 
            --data-type realtime
    ↓
configurable_data_collector.py:
1. Query configurations table for site_id list
2. Parse comma-separated site_ids
3. Query stations table for station details
4. Fetch data from USGS API:
   - realtime: /nwis/iv → realtime_discharge table
   - daily: /nwis/dv → streamflow_data table
5. Log to collection_logs
6. IF data_type='daily': 
        ↓
   subprocess: python enrich_station_metadata.py
        ↓
   enrich_station_metadata.py:
   1. Calculate years_of_record from streamflow_data
   2. Fetch drainage_area, county from USGS site service
   3. Update filters table
        ↓
Dashboard reload
    ↓
app.py loads stations + filters for map display
```

### Key Relationships
```
configurations.site_id → comma-separated list of stations.site_id
schedules.config_id → configurations.config_id (many-to-one)
realtime_discharge.site_id → stations.site_id (many-to-one)
streamflow_data.site_id → stations.site_id (many-to-one)
filters.site_id → stations.site_id (one-to-one, enriched)
collection_logs.config_id → configurations.config_id (many-to-one)
station_errors.site_id → stations.site_id (many-to-one)
```

---

## 🚨 Critical Design Notes

### Column Naming Consistency
**ALL TABLES USE `site_id`** as the primary station identifier:
- ✅ stations.site_id
- ✅ realtime_discharge.site_id (was site_no - FIXED)
- ✅ streamflow_data.site_id
- ✅ filters.site_id
- ✅ configurations.site_id (comma-separated list)
- ✅ station_errors.site_id

**Never use:** `site_no`, `usgs_id`, `station_id`, `id`

### Denormalized Design
The `configurations.site_id` column stores comma-separated station ID lists:
```
"10068500,10092700,10243260,10243700,10244950,..."
```
This is not a normalized junction table design. To query stations for a configuration:
1. Get comma-separated string from configurations
2. Split by comma
3. Query stations with `WHERE site_id IN (...)`

### Dual Data Types
- **realtime_discharge**: 15-minute instantaneous readings from USGS IV API
- **streamflow_data**: Daily mean/min/max aggregates from USGS DV API
- Both reference the same stations but serve different use cases

### Filters Table is Critical
The `filters` table is THE authoritative source for:
- Map hover labels (drainage_area, years_of_record)
- Plot metadata displays
- Station filtering UI

**Without enrichment, these fields will be NULL or outdated.**

### Enrichment Timing
- Only runs after `data_type='daily'` collections
- NOT triggered by `data_type='realtime'` collections
- Fetches external metadata from USGS Site Service API
- Can be slow (1,506 stations × API calls)

### Monitoring Refresh
Admin panel Monitoring tab auto-refreshes every 10 seconds via:
```python
dcc.Interval(id='admin-refresh-interval', interval=10000)  # 10 seconds
```

---

## 📦 Database Size Metrics
- **Total Size:** 3.57 MB
- **Largest Table:** realtime_discharge (18,076 rows, ~2.5 MB estimated)
- **Station Count:** 1,506 active stations
- **States Covered:** CA (501), WA (292), MT (205), OR (216), ID (124), NV (168)

---

## 🔧 Maintenance Commands

### Check table sizes:
```bash
sqlite3 data/usgs_data.db "
SELECT name, 
       (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as row_count
FROM sqlite_master m WHERE type='table' ORDER BY name;"
```

### Verify data consistency:
```bash
# Check for orphaned realtime records
sqlite3 data/usgs_data.db "
SELECT COUNT(*) FROM realtime_discharge rd
LEFT JOIN stations s ON rd.site_id = s.site_id
WHERE s.site_id IS NULL;"

# Check for stations without metadata
sqlite3 data/usgs_data.db "
SELECT COUNT(*) FROM stations s
LEFT JOIN filters f ON s.site_id = f.site_id
WHERE f.site_id IS NULL;"
```

### Rebuild indexes:
```bash
sqlite3 data/usgs_data.db "REINDEX;"
```

### Vacuum database:
```bash
sqlite3 data/usgs_data.db "VACUUM;"
```

---

**Changelog:**
- 2025-11-10: Initial documentation
- 2025-11-10: Fixed site_no → site_id in realtime_discharge
- 2025-11-10: Added has_realtime column to stations table
- 2025-11-10: Populated filters table (1,506 rows)
- 2025-11-10: Integrated enrichment into daily collection workflow
