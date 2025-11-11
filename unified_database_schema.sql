-- ============================================================================
-- USGS Streamflow Dashboard - Unified Database Schema
-- ============================================================================
-- File: unified_database_schema.sql
-- Purpose: Complete schema for merged usgs_data.db
-- Date: November 6, 2025
-- 
-- This schema combines:
--   - station_config.db (configurations, schedules, logs)
--   - usgs_cache.db (streamflow data, filters)
-- 
-- Into single unified database with:
--   - No data duplication
--   - Proper foreign key constraints
--   - Optimized indexes for performance
--   - Backward-compatible views
-- ============================================================================

-- Enable foreign key support (CRITICAL!)
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CORE METADATA TABLE
-- ============================================================================

-- stations: Master station metadata (merged from station_lists + filters)
CREATE TABLE stations (
    -- Primary Key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Identifiers (from station_lists)
    usgs_id TEXT UNIQUE NOT NULL,              -- USGS site number (8-15 digits)
    nws_id TEXT,                                -- NOAA/NWS identifier
    goes_id TEXT,                               -- GOES satellite ID
    
    -- Basic Metadata (merged from both sources)
    station_name TEXT NOT NULL,                 -- Official station name
    state TEXT NOT NULL,                        -- Two-letter state code (e.g., 'WA')
    county TEXT,                                -- County name (from USGS/filters)
    
    -- Geographic Location (from station_lists - source of truth)
    latitude REAL NOT NULL,                     -- Decimal degrees
    longitude REAL NOT NULL,                    -- Decimal degrees
    
    -- Hydrologic Metadata (merged)
    drainage_area REAL,                         -- Square miles
    huc_code TEXT,                              -- Hydrologic Unit Code
    basin TEXT,                                 -- Basin name (from filters, derived from HUC)
    
    -- USGS Metadata (from filters)
    site_type TEXT,                             -- 'Stream', 'Lake', etc.
    agency TEXT DEFAULT 'USGS',                 -- Collecting agency
    
    -- Data Availability Statistics (from filters, computed)
    years_of_record INTEGER,                    -- Total years with data
    num_water_years INTEGER,                    -- Number of complete water years
    last_data_date TEXT,                        -- Most recent data (YYYY-MM-DD)
    
    -- Status & Control (merged)
    is_active BOOLEAN DEFAULT TRUE,             -- Whether to collect data
    status TEXT DEFAULT 'active',               -- 'active', 'inactive', 'error', 'pending'
    
    -- Provenance (from station_lists)
    source_dataset TEXT NOT NULL,               -- 'HADS_PNW', 'HADS_Columbia', 'Custom'
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When added to system
    last_verified TIMESTAMP,                    -- Last metadata verification
    
    -- UI State (from filters)
    color TEXT,                                 -- Map marker color (hex or name)
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- Last metadata update
    
    -- Notes
    notes TEXT,                                 -- Admin notes
    
    -- Constraints
    CHECK (state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID',
                     'IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS',
                     'MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK',
                     'OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV',
                     'WI','WY','DC','AS','GU','MP','PR','VI')),
    CHECK (latitude BETWEEN -90 AND 90),
    CHECK (longitude BETWEEN -180 AND 180),
    CHECK (drainage_area IS NULL OR drainage_area >= 0),
    CHECK (years_of_record IS NULL OR years_of_record >= 0),
    CHECK (num_water_years IS NULL OR num_water_years >= 0),
    CHECK (status IN ('active', 'inactive', 'error', 'pending', 'unknown')),
    CHECK (source_dataset IN ('HADS_PNW', 'HADS_Columbia', 'Custom', 'Manual', 'Import'))
);

-- Indexes for performance
CREATE INDEX idx_stations_usgs_id ON stations(usgs_id);
CREATE INDEX idx_stations_state ON stations(state);
CREATE INDEX idx_stations_basin ON stations(basin);
CREATE INDEX idx_stations_huc ON stations(huc_code);
CREATE INDEX idx_stations_active ON stations(is_active);
CREATE INDEX idx_stations_status ON stations(status);
CREATE INDEX idx_stations_drainage ON stations(drainage_area);
CREATE INDEX idx_stations_location ON stations(latitude, longitude);  -- For spatial queries
CREATE INDEX idx_stations_source ON stations(source_dataset);

-- ============================================================================
-- CONFIGURATION TABLES
-- ============================================================================

-- configurations: Station collection configurations/subsets
CREATE TABLE configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_name TEXT UNIQUE NOT NULL,
    description TEXT,
    station_count INTEGER DEFAULT 0,            -- Cached count for performance
    is_default BOOLEAN DEFAULT FALSE,           -- Default configuration
    is_active BOOLEAN DEFAULT TRUE,             -- Whether available for use
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT DEFAULT 'system',           -- 'system', 'admin', username
    
    -- Constraints
    CHECK (station_count >= 0),
    UNIQUE(config_name)
);

-- Indexes
CREATE INDEX idx_config_name ON configurations(config_name);
CREATE INDEX idx_config_active ON configurations(is_active);
CREATE INDEX idx_config_default ON configurations(is_default);

-- configuration_stations: Many-to-many mapping
CREATE TABLE configuration_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,
    station_id INTEGER NOT NULL,                -- References stations.id
    priority INTEGER DEFAULT 1,                 -- Collection order priority
    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    added_by TEXT DEFAULT 'system',
    
    -- Foreign Keys
    FOREIGN KEY (config_id) REFERENCES configurations(id) ON DELETE CASCADE,
    FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE,
    
    -- Constraints
    UNIQUE(config_id, station_id)               -- No duplicates
);

-- Indexes
CREATE INDEX idx_config_stations_config ON configuration_stations(config_id);
CREATE INDEX idx_config_stations_station ON configuration_stations(station_id);
CREATE INDEX idx_config_stations_priority ON configuration_stations(priority);

-- ============================================================================
-- SCHEDULING TABLES
-- ============================================================================

-- schedules: Data collection schedules
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,                 -- Which configuration to run
    schedule_name TEXT NOT NULL,
    data_type TEXT NOT NULL DEFAULT 'both',     -- 'realtime', 'daily', 'both'
    
    -- Schedule Timing
    cron_expression TEXT NOT NULL,              -- Cron format: "0 * * * *" (hourly)
    interval_minutes INTEGER,                   -- Alternative: simple interval
    is_enabled BOOLEAN DEFAULT TRUE,
    
    -- Execution Tracking
    last_run TIMESTAMP,                         -- When last executed
    next_run TIMESTAMP,                         -- When next scheduled
    run_count INTEGER DEFAULT 0,                -- Total executions
    
    -- Metadata
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    FOREIGN KEY (config_id) REFERENCES configurations(id) ON DELETE CASCADE,
    
    -- Constraints
    CHECK (data_type IN ('realtime', 'daily', 'both')),
    CHECK (run_count >= 0),
    CHECK (interval_minutes IS NULL OR interval_minutes > 0)
);

-- Indexes
CREATE INDEX idx_schedule_config ON schedules(config_id);
CREATE INDEX idx_schedule_enabled ON schedules(is_enabled);
CREATE INDEX idx_schedule_next_run ON schedules(next_run);
CREATE INDEX idx_schedule_data_type ON schedules(data_type);

-- ============================================================================
-- DATA TABLES
-- ============================================================================

-- streamflow_data: Historical daily streamflow data
CREATE TABLE streamflow_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,                      -- References stations.usgs_id
    data_json TEXT,                             -- JSON blob of daily data
    start_date TEXT NOT NULL,                   -- YYYY-MM-DD
    end_date TEXT NOT NULL,                     -- YYYY-MM-DD
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys (enforced!)
    FOREIGN KEY (site_id) REFERENCES stations(usgs_id) ON DELETE CASCADE,
    
    -- Constraints
    UNIQUE(site_id, start_date, end_date)
);

-- Indexes for performance
CREATE INDEX idx_streamflow_site ON streamflow_data(site_id);
CREATE INDEX idx_streamflow_dates ON streamflow_data(start_date, end_date);
CREATE INDEX idx_streamflow_updated ON streamflow_data(last_updated);

-- realtime_discharge: Real-time (15-minute) discharge data
CREATE TABLE realtime_discharge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,                      -- References stations.usgs_id
    datetime_utc TIMESTAMP NOT NULL,            -- UTC timestamp
    discharge_cfs REAL NOT NULL,                -- Discharge in cubic feet per second
    data_quality TEXT DEFAULT 'A',              -- USGS quality code: A=Approved, P=Provisional
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys (enforced!)
    FOREIGN KEY (site_id) REFERENCES stations(usgs_id) ON DELETE CASCADE,
    
    -- Constraints
    UNIQUE(site_id, datetime_utc),
    CHECK (discharge_cfs >= 0),
    CHECK (data_quality IN ('A', 'P', 'E', 'R', 'U'))  -- USGS quality codes
);

-- Indexes for performance
CREATE INDEX idx_realtime_site_datetime ON realtime_discharge(site_id, datetime_utc);
CREATE INDEX idx_realtime_datetime ON realtime_discharge(datetime_utc);
CREATE INDEX idx_realtime_site ON realtime_discharge(site_id);
CREATE INDEX idx_realtime_quality ON realtime_discharge(data_quality);

-- data_statistics: Cached statistics per station
CREATE TABLE data_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,                      -- References stations.usgs_id
    stats_json TEXT,                            -- JSON blob with mean, median, percentiles
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys (enforced!)
    FOREIGN KEY (site_id) REFERENCES stations(usgs_id) ON DELETE CASCADE,
    
    -- Constraints
    UNIQUE(site_id)
);

-- Indexes
CREATE INDEX idx_statistics_site ON data_statistics(site_id);
CREATE INDEX idx_statistics_updated ON data_statistics(last_updated);

-- subset_cache: Cached filtered station subsets
CREATE TABLE subset_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subset_config TEXT NOT NULL,                -- JSON config of filters applied
    site_ids TEXT NOT NULL,                     -- Comma-separated site IDs
    selection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_available INTEGER,                    -- Total stations before subset
    subset_size INTEGER,                        -- Size of subset
    
    -- Constraints
    CHECK (total_available >= 0),
    CHECK (subset_size >= 0),
    CHECK (subset_size <= total_available)
);

-- Indexes
CREATE INDEX idx_subset_config ON subset_cache(subset_config);
CREATE INDEX idx_subset_date ON subset_cache(selection_date);

-- ============================================================================
-- OPERATIONAL/LOGGING TABLES
-- ============================================================================

-- collection_logs: Data collection execution logs
CREATE TABLE collection_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id INTEGER NOT NULL,                 -- Which configuration was run
    schedule_id INTEGER,                        -- NULL if manual run
    data_type TEXT NOT NULL,                    -- 'realtime', 'daily', 'manual'
    
    -- Execution Statistics
    stations_attempted INTEGER DEFAULT 0,
    stations_successful INTEGER DEFAULT 0,
    stations_failed INTEGER DEFAULT 0,
    
    -- Timing
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Results
    error_summary TEXT,                         -- High-level error description
    status TEXT NOT NULL,                       -- 'running', 'completed', 'failed', 'cancelled'
    triggered_by TEXT DEFAULT 'system',         -- 'system', 'manual', 'api', username
    
    -- Foreign Keys
    FOREIGN KEY (config_id) REFERENCES configurations(id),
    FOREIGN KEY (schedule_id) REFERENCES schedules(id),
    
    -- Constraints
    CHECK (data_type IN ('realtime', 'daily', 'manual', 'both')),
    CHECK (status IN ('running', 'completed', 'failed', 'cancelled', 'partial')),
    CHECK (stations_attempted >= 0),
    CHECK (stations_successful >= 0),
    CHECK (stations_failed >= 0),
    CHECK (stations_successful + stations_failed <= stations_attempted),
    CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

-- Indexes
CREATE INDEX idx_logs_config ON collection_logs(config_id);
CREATE INDEX idx_logs_schedule ON collection_logs(schedule_id);
CREATE INDEX idx_logs_status ON collection_logs(status);
CREATE INDEX idx_logs_start_time ON collection_logs(start_time);
CREATE INDEX idx_logs_data_type ON collection_logs(data_type);

-- station_errors: Detailed error tracking per station
CREATE TABLE station_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER NOT NULL,                    -- References collection_logs.id
    station_id INTEGER NOT NULL,                -- References stations.id
    error_type TEXT NOT NULL,                   -- 'network', 'parse', 'validation', 'timeout'
    error_message TEXT,
    http_status_code INTEGER,
    retry_count INTEGER DEFAULT 0,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    FOREIGN KEY (log_id) REFERENCES collection_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (station_id) REFERENCES stations(id),
    
    -- Constraints
    CHECK (error_type IN ('network', 'parse', 'validation', 'timeout', 'api_error', 'no_data', 'unknown')),
    CHECK (retry_count >= 0),
    CHECK (http_status_code IS NULL OR (http_status_code >= 100 AND http_status_code < 600))
);

-- Indexes
CREATE INDEX idx_errors_log ON station_errors(log_id);
CREATE INDEX idx_errors_station ON station_errors(station_id);
CREATE INDEX idx_errors_type ON station_errors(error_type);
CREATE INDEX idx_errors_occurred ON station_errors(occurred_at);

-- ============================================================================
-- VIEWS (Backward Compatibility)
-- ============================================================================

-- configuration_summary: Overview of configurations
CREATE VIEW configuration_summary AS
SELECT 
    c.id,
    c.config_name,
    c.description,
    c.is_default,
    c.is_active,
    COUNT(cs.station_id) as actual_station_count,
    c.station_count as recorded_count,
    c.created_date,
    c.last_modified,
    c.created_by
FROM configurations c
LEFT JOIN configuration_stations cs ON c.id = cs.config_id
GROUP BY c.id, c.config_name, c.description, c.is_default, c.is_active, 
         c.station_count, c.created_date, c.last_modified, c.created_by;

-- stations_by_state: Station counts grouped by state
CREATE VIEW stations_by_state AS
SELECT 
    state,
    COUNT(*) as total_stations,
    COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_stations,
    source_dataset,
    MIN(latitude) as min_lat,
    MAX(latitude) as max_lat,
    MIN(longitude) as min_lon,
    MAX(longitude) as max_lon
FROM stations
GROUP BY state, source_dataset
ORDER BY state, source_dataset;

-- recent_collection_activity: Recent data collection runs
CREATE VIEW recent_collection_activity AS
SELECT 
    cl.id,
    c.config_name,
    cl.data_type,
    cl.status,
    cl.stations_attempted,
    cl.stations_successful,
    cl.stations_failed,
    ROUND(cl.duration_seconds / 60.0, 2) as duration_minutes,
    cl.start_time,
    cl.end_time,
    cl.triggered_by,
    s.schedule_name
FROM collection_logs cl
JOIN configurations c ON cl.config_id = c.id
LEFT JOIN schedules s ON cl.schedule_id = s.id
ORDER BY cl.start_time DESC
LIMIT 100;

-- stations_with_realtime: Stations that have recent real-time data
CREATE VIEW stations_with_realtime AS
SELECT DISTINCT
    s.id,
    s.usgs_id,
    s.station_name,
    s.state,
    s.latitude,
    s.longitude,
    MAX(rd.datetime_utc) as last_realtime_update
FROM stations s
JOIN realtime_discharge rd ON s.usgs_id = rd.site_id
WHERE rd.datetime_utc > datetime('now', '-24 hours')
GROUP BY s.id, s.usgs_id, s.station_name, s.state, s.latitude, s.longitude;

-- station_data_availability: Data availability summary per station
CREATE VIEW station_data_availability AS
SELECT 
    s.id,
    s.usgs_id,
    s.station_name,
    s.state,
    s.years_of_record,
    s.num_water_years,
    s.last_data_date,
    COUNT(DISTINCT sd.id) as streamflow_data_chunks,
    COUNT(DISTINCT rd.id) as realtime_data_points,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM realtime_discharge rd2 
            WHERE rd2.site_id = s.usgs_id 
            AND rd2.datetime_utc > datetime('now', '-24 hours')
        ) THEN 1 
        ELSE 0 
    END as has_recent_realtime
FROM stations s
LEFT JOIN streamflow_data sd ON s.usgs_id = sd.site_id
LEFT JOIN realtime_discharge rd ON s.usgs_id = rd.site_id
GROUP BY s.id, s.usgs_id, s.station_name, s.state, s.years_of_record, 
         s.num_water_years, s.last_data_date;

-- error_summary: Error statistics by type
CREATE VIEW error_summary AS
SELECT 
    error_type,
    COUNT(*) as error_count,
    COUNT(DISTINCT station_id) as affected_stations,
    MAX(occurred_at) as most_recent_occurrence
FROM station_errors
WHERE occurred_at > datetime('now', '-7 days')
GROUP BY error_type
ORDER BY error_count DESC;

-- ============================================================================
-- TRIGGERS (Data Integrity & Automation)
-- ============================================================================

-- Update configuration station count when stations added/removed
CREATE TRIGGER update_config_count_insert
AFTER INSERT ON configuration_stations
BEGIN
    UPDATE configurations 
    SET station_count = (
        SELECT COUNT(*) FROM configuration_stations WHERE config_id = NEW.config_id
    )
    WHERE id = NEW.config_id;
END;

CREATE TRIGGER update_config_count_delete
AFTER DELETE ON configuration_stations
BEGIN
    UPDATE configurations 
    SET station_count = (
        SELECT COUNT(*) FROM configuration_stations WHERE config_id = OLD.config_id
    )
    WHERE id = OLD.config_id;
END;

-- Update last_modified timestamp on configuration changes
CREATE TRIGGER update_config_modified
AFTER UPDATE ON configurations
BEGIN
    UPDATE configurations 
    SET last_modified = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

-- Increment schedule run count
CREATE TRIGGER increment_schedule_count
AFTER INSERT ON collection_logs
WHEN NEW.schedule_id IS NOT NULL AND NEW.status = 'completed'
BEGIN
    UPDATE schedules 
    SET run_count = run_count + 1,
        last_run = NEW.start_time
    WHERE id = NEW.schedule_id;
END;

-- Update station last_updated timestamp
CREATE TRIGGER update_station_timestamp
AFTER UPDATE ON stations
BEGIN
    UPDATE stations 
    SET last_updated = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

-- ============================================================================
-- INDEXES FOR COMPLEX QUERIES
-- ============================================================================

-- Composite indexes for common filter combinations
CREATE INDEX idx_stations_state_active ON stations(state, is_active);
CREATE INDEX idx_stations_basin_active ON stations(basin, is_active);
CREATE INDEX idx_stations_state_drainage ON stations(state, drainage_area);
CREATE INDEX idx_stations_active_status ON stations(is_active, status);

-- ============================================================================
-- SCHEMA VALIDATION QUERIES
-- ============================================================================

-- Use these to verify schema is correct:
-- SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;
-- SELECT name, sql FROM sqlite_master WHERE type='index' ORDER BY name;
-- SELECT name, sql FROM sqlite_master WHERE type='view' ORDER BY name;
-- SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name;
-- PRAGMA foreign_key_list(stations);
-- PRAGMA integrity_check;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
