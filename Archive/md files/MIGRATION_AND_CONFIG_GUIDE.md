# Database Migration & Configuration Loading Guide

Complete guide for migrating to the unified database and loading configurations.

## Table of Contents
- [Overview](#overview)
- [Phase 4: Database Migration](#phase-4-database-migration)
- [Phase 5: Configuration Loading](#phase-5-configuration-loading)
- [Complete Migration Workflow](#complete-migration-workflow)
- [Testing & Validation](#testing--validation)
- [Troubleshooting](#troubleshooting)

---

## Overview

This guide covers the final two setup phases:
- **Phase 4**: Migrate existing databases to unified schema
- **Phase 5**: Load JSON configurations into database

After completing these phases, the system will have:
- Single unified database (`usgs_data.db`)
- No data duplication
- Version-controlled configurations
- Environment-specific overrides

---

## Phase 4: Database Migration

### Migration Script: `migrate_to_unified_db.py`

Merges two separate databases into one unified database:
- `station_config.db` (configurations, schedules, logs)
- `usgs_cache.db` (station data, streamflow data)
- → `usgs_data.db` (unified database)

### Features

**Data Merging:**
- Intelligent station merging (station_lists + filters)
- Conflict detection and resolution
- Preserves all historical data
- ID remapping for foreign key integrity

**Safety:**
- Automatic timestamped backups
- Dry-run mode for testing
- Comprehensive validation
- Rollback capability

**Validation:**
- Row count verification
- NULL constraint checks
- Foreign key validation
- Index existence checks
- Database integrity checks

### Usage

#### 1. Test Migration (Dry Run)

```bash
python migrate_to_unified_db.py --dry-run --verbose
```

This shows what would be migrated without making changes.

#### 2. Run Migration

```bash
python migrate_to_unified_db.py
```

Prompts for confirmation before proceeding.

#### 3. Skip Confirmation

```bash
python migrate_to_unified_db.py --force
```

#### 4. Verbose Output

```bash
python migrate_to_unified_db.py --verbose
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without modifying databases |
| `--verbose` | Show detailed progress information |
| `--force` | Skip confirmation prompts |
| `--no-backup` | Skip backup creation (NOT RECOMMENDED) |

### Migration Process

The script performs these steps:

1. **Validate Preconditions**
   - Check source databases exist
   - Check schema file exists
   - Verify target doesn't already exist

2. **Create Backups**
   - Timestamp: `YYYYMMDD_HHMMSS`
   - Location: `data/backups/`
   - Files: `station_config_*.db`, `usgs_cache_*.db`

3. **Create Unified Schema**
   - Load `unified_database_schema.sql`
   - Create all tables, views, indexes, triggers

4. **Merge Station Data**
   - Load station_lists (1,506 stations)
   - Load filters (1,506 stations)
   - Merge with conflict resolution
   - Priority: station_lists > filters for core fields
   - Log conflicts to `migration_conflicts.log`

5. **Copy Configurations**
   - Copy station_configurations → configurations
   - Copy configuration_stations with ID remapping
   - Copy update_schedules → schedules

6. **Copy Streamflow Data**
   - Batch copy for performance (1,000 records/batch)
   - Includes historical streamflow_data
   - Includes realtime_discharge
   - Includes data_statistics

7. **Copy Logs**
   - Copy data_collection_logs → collection_logs
   - Copy station_collection_errors → station_errors
   - Remap all foreign keys

8. **Validate Migration**
   - Verify row counts match
   - Check for NULL values in required fields
   - Validate all foreign keys
   - Check indexes created (expect ~45)
   - Check views created (expect 6)
   - Check triggers created (expect 5)
   - Run SQLite integrity check

### Conflict Resolution

When station_lists and filters have different values:

**station_name:**
- Resolution: Use filters value (may have USGS updates)
- Logged to: `migration_conflicts.log`

**drainage_area:**
- Resolution: Use station_lists value (fixed binary bug)
- Logged if difference > 0.1 sq mi

**Other fields:**
- Core fields: station_lists (source of truth)
- USGS metadata: filters (computed from USGS API)
- Statistics: filters (computed from data)

### Output

**Success:**
```
MIGRATION SUMMARY
================================================================================
Stations (merged):              1506
  - From station_lists:         1506
  - From filters:               1506
  - Conflicts resolved:         23
Streamflow data records:        2,450,123
Realtime discharge records:     156,789
Statistics records:             1,506
Configurations:                 3
Configuration-station mappings: 2,094
Schedules:                      4
Collection logs:                142
Station errors:                 56
================================================================================

✓ Migration completed successfully in 45.3 seconds

New database: data/usgs_data.db
Backups: data/backups/

Next steps:
  1. Verify new database works: sqlite3 data/usgs_data.db '.tables'
  2. Test application with new database
  3. Update code to use data/usgs_data.db
  4. Keep backups until confident migration succeeded
```

**Errors:**
- Logged to console with stack traces
- Migration stops on critical errors
- Backups remain unchanged

---

## Phase 5: Configuration Loading

### Config Loader: `config_loader.py`

Loads configurations from JSON files into the database.

### Features

**Station Sources:**
- `csv` - Load from CSV file
- `filter` - Query database with filter criteria
- `manual` - Explicit USGS ID list
- `database` - Copy from existing configuration

**Overrides:**
- Local overrides: `*.local.json` files
- Environment variables: `USGS_*` prefix
- Priority: env vars > local files > default files

**Filter Operators:**
- Comparison: `=`, `!=`, `>`, `<`, `>=`, `<=`
- Lists: `in`, `not_in`
- Text: `contains`, `not_contains`, `starts_with`, `ends_with`
- NULL: `is_null`, `is_not_null`
- Range: `between`

### Usage

#### 1. Load All Configurations

```bash
python config_loader.py
```

Loads configurations, schedules, and settings.

#### 2. Force Reload

```bash
python config_loader.py --force
```

Reloads even if already loaded.

#### 3. Skip Station Data (Testing)

```bash
python config_loader.py --skip-stations
```

#### 4. Use Different Database

```bash
python config_loader.py --db /path/to/database.db
```

### Python API

```python
from config_loader import ConfigLoader

# Create loader
loader = ConfigLoader('data/usgs_data.db')

# Load everything
loader.load_all()

# Or load specific components
loader.load_settings()
loader.load_configurations()
loader.load_schedules()

# Get settings
settings = loader.get_settings()

# Force reload
loader.reload_all()
```

### Configuration Files

**config/default_configurations.json**
- Defines station configurations
- Specifies station sources
- Sets filters and limits

**config/default_schedules.json**
- Defines automated schedules
- Links to configurations
- Sets timing (cron/interval)

**config/system_settings.json**
- Database settings
- Data collection settings
- USGS API configuration
- Dashboard settings
- Logging configuration

**Local Overrides (Optional)**
- `config/default_configurations.local.json`
- `config/default_schedules.local.json`
- `config/system_settings.local.json`
- Automatically merged with defaults
- Not tracked in git

### Environment Variables

Override settings with environment variables:

| Variable | Setting | Example |
|----------|---------|---------|
| `USGS_DB_PATH` | Database path | `/data/prod/usgs_data.db` |
| `USGS_API_KEY` | USGS API key | `your-api-key-here` |
| `USGS_API_EMAIL` | Contact email | `admin@example.com` |
| `USGS_TIMEOUT` | Request timeout | `60` |
| `USGS_MAX_CONCURRENT` | Max concurrent | `20` |
| `USGS_LOG_LEVEL` | Log level | `DEBUG` |

### Station Source Examples

#### CSV Source

```json
{
  "station_source": {
    "type": "csv",
    "csv_file": "active_pnw_discharge_stations.csv"
  }
}
```

#### Filter Source

```json
{
  "station_source": {
    "type": "filter",
    "filters": [
      {"field": "state", "operator": "=", "value": "WA"},
      {"field": "drainage_area", "operator": ">=", "value": 1000},
      {"field": "station_name", "operator": "contains", "value": "RIVER"}
    ],
    "max_stations": 100
  }
}
```

#### Manual Source

```json
{
  "station_source": {
    "type": "manual",
    "usgs_ids": [
      "09380000",
      "14105700",
      "12513000"
    ]
  }
}
```

#### Database Source

```json
{
  "station_source": {
    "type": "database",
    "base_config": "Pacific Northwest Full",
    "filters": [
      {"field": "years_of_record", "operator": ">=", "value": 30}
    ]
  }
}
```

---

## Complete Migration Workflow

### Step-by-Step Process

#### 1. Prepare

```bash
# Ensure you're on the right branch
git checkout feature/remove-legacy-system

# Verify schema file exists
ls unified_database_schema.sql

# Verify config files exist
ls config/*.json
```

#### 2. Test Migration (Dry Run)

```bash
# Preview what will be migrated
python migrate_to_unified_db.py --dry-run --verbose
```

Review output for:
- Expected row counts
- No errors
- Conflict count acceptable

#### 3. Run Migration

```bash
# Execute migration
python migrate_to_unified_db.py

# Answer 'yes' when prompted
```

Migration creates:
- `data/usgs_data.db` (new unified database)
- `data/backups/station_config_TIMESTAMP.db`
- `data/backups/usgs_cache_TIMESTAMP.db`
- `migration_conflicts.log` (if conflicts exist)

#### 4. Verify Migration

```bash
# Check database exists
ls -lh data/usgs_data.db

# Check tables created
sqlite3 data/usgs_data.db '.tables'

# Check station count
sqlite3 data/usgs_data.db 'SELECT COUNT(*) FROM stations;'

# Check views exist
sqlite3 data/usgs_data.db "SELECT name FROM sqlite_master WHERE type='view';"
```

Expected output:
- Database size: ~1.1 GB
- 12 tables
- 6 views
- 1,506 stations

#### 5. Load Configurations

```bash
# Load configs into new database
python config_loader.py --db data/usgs_data.db --verbose
```

This populates:
- configurations table (3 configs)
- configuration_stations junction table (~2,000 mappings)
- schedules table (4 schedules)

#### 6. Verify Config Loading

```bash
# Check configurations
sqlite3 data/usgs_data.db 'SELECT * FROM configurations;'

# Check schedules
sqlite3 data/usgs_data.db 'SELECT * FROM schedules;'

# Check station mappings
sqlite3 data/usgs_data.db 'SELECT COUNT(*) FROM configuration_stations;'
```

#### 7. Test Application

```bash
# Update app to use new database
# (Phase 6+ will handle this)

# Start app
python app.py

# Test:
# - Dashboard loads
# - Map displays stations
# - Filters work
# - Data collection works
# - Admin panel works
```

#### 8. Commit Changes

```bash
# Once verified, commit
git add data/usgs_data.db
git commit -m "Migration complete: unified database created"
```

---

## Testing & Validation

### Database Validation Queries

**Check data integrity:**

```sql
-- Check for NULL values in required fields
SELECT COUNT(*) FROM stations 
WHERE usgs_id IS NULL OR station_name IS NULL 
   OR state IS NULL OR latitude IS NULL OR longitude IS NULL;

-- Should return: 0

-- Check foreign key violations
PRAGMA foreign_key_check;

-- Should return: (empty)

-- Check database integrity
PRAGMA integrity_check;

-- Should return: ok

-- Count stations
SELECT COUNT(*) FROM stations;

-- Should return: 1506

-- Count streamflow data
SELECT COUNT(*) FROM streamflow_data;

-- Should return: millions

-- Count realtime data
SELECT COUNT(*) FROM realtime_discharge;

-- Should return: thousands
```

**Check configurations:**

```sql
-- List configurations
SELECT id, config_name, station_count, is_default 
FROM configurations;

-- Check station mappings
SELECT c.config_name, COUNT(cs.station_id) as mapped_stations
FROM configurations c
LEFT JOIN configuration_stations cs ON c.id = cs.config_id
GROUP BY c.id;

-- List schedules
SELECT s.schedule_name, c.config_name, s.data_type, s.is_enabled
FROM schedules s
JOIN configurations c ON s.config_id = c.id;
```

### Performance Testing

**Index usage:**

```sql
-- Verify indexes exist
SELECT name, tbl_name FROM sqlite_master 
WHERE type='index' AND tbl_name='stations'
ORDER BY name;

-- Test query performance (should use idx_stations_state)
EXPLAIN QUERY PLAN
SELECT * FROM stations WHERE state = 'WA';
```

**View functionality:**

```sql
-- Test backward compatibility view
SELECT COUNT(*) FROM station_lists;

-- Should match stations table
SELECT COUNT(*) FROM stations;

-- Test active stations view
SELECT COUNT(*) FROM active_stations;
```

### Config Loader Testing

**Test with dry database:**

```bash
# Create test database
sqlite3 test.db < unified_database_schema.sql

# Load configs
python config_loader.py --db test.db --verbose

# Verify
sqlite3 test.db 'SELECT COUNT(*) FROM configurations;'
```

**Test environment overrides:**

```bash
# Set environment variables
export USGS_DB_PATH=/tmp/test.db
export USGS_LOG_LEVEL=DEBUG

# Run loader
python config_loader.py

# Check that overrides were applied
```

**Test local overrides:**

```bash
# Create local override
cat > config/system_settings.local.json << EOF
{
  "database": {
    "path": "data/dev_usgs_data.db"
  },
  "logging": {
    "level": "DEBUG"
  }
}
EOF

# Run loader
python config_loader.py

# Verify dev database used
```

---

## Troubleshooting

### Migration Issues

#### "Source database not found"

**Problem:** Can't find `station_config.db` or `usgs_cache.db`

**Solution:**
```bash
# Check database locations
ls -la data/*.db

# Ensure in correct directory
pwd  # Should be project root
```

#### "Target database already exists"

**Problem:** `usgs_data.db` already exists

**Solution:**
```bash
# Rename existing database
mv data/usgs_data.db data/usgs_data.old.db

# Or delete if not needed
rm data/usgs_data.db

# Then re-run migration
python migrate_to_unified_db.py
```

#### "Foreign key violations found"

**Problem:** Data inconsistencies after migration

**Solution:**
```bash
# Check violations
sqlite3 data/usgs_data.db "PRAGMA foreign_key_check;"

# Review migration_conflicts.log
cat migration_conflicts.log

# May need to:
# 1. Fix source data
# 2. Delete target database
# 3. Re-run migration
```

#### "Station count mismatch"

**Problem:** Fewer stations than expected

**Solution:**
```bash
# Check source counts
sqlite3 data/station_config.db "SELECT COUNT(*) FROM station_lists;"
sqlite3 data/usgs_cache.db "SELECT COUNT(*) FROM filters;"

# Check migration logs
# Look for warnings about missing stations

# Re-run with verbose
python migrate_to_unified_db.py --dry-run --verbose
```

### Config Loader Issues

#### "No configurations found"

**Problem:** JSON file missing or empty

**Solution:**
```bash
# Verify config files exist
ls -la config/*.json

# Check JSON syntax
python -m json.tool config/default_configurations.json

# If corrupted, restore from git
git checkout config/default_configurations.json
```

#### "Station not found"

**Problem:** CSV references stations not in database

**Solution:**
```sql
-- Check which stations are missing
SELECT usgs_id FROM (
  VALUES ('09380000'), ('14105700'), ('12513000')
) AS input(usgs_id)
WHERE usgs_id NOT IN (SELECT usgs_id FROM stations);

-- Either:
-- 1. Add missing stations to database
-- 2. Remove from configuration
-- 3. Use different station source
```

#### "Config not found"

**Problem:** Schedule references non-existent config

**Solution:**
```bash
# Check which configs exist
sqlite3 data/usgs_data.db "SELECT config_name FROM configurations;"

# Update schedule to reference existing config
# Edit config/default_schedules.json
```

### Performance Issues

#### "Migration taking too long"

**Normal:** Large databases take time
- 1-2 million streamflow records: ~30-60 seconds
- 5+ million records: 2-5 minutes

**Solution:**
```bash
# Monitor progress with verbose
python migrate_to_unified_db.py --verbose

# If stuck, check:
# 1. Disk space (df -h)
# 2. Database locks (fuser data/*.db)
# 3. System resources (top)
```

#### "Config loading slow"

**Problem:** CSV loading takes long with large files

**Solution:**
- Use filter source instead (queries database directly)
- Reduce max_stations limit
- Use database source to copy existing config

### Database Corruption

#### "Database integrity check failed"

**Problem:** Corrupted database

**Solution:**
```bash
# Restore from backup
cp data/backups/usgs_cache_TIMESTAMP.db data/usgs_cache.db
cp data/backups/station_config_TIMESTAMP.db data/station_config.db

# Re-run migration
rm data/usgs_data.db
python migrate_to_unified_db.py

# If backups corrupted:
# 1. Restore from git (if tracked)
# 2. Restore from system backup
# 3. Re-fetch data from USGS
```

---

## Next Steps

After completing Phases 4 & 5:

### Phase 6: Update Code
- Update all database connections to use `usgs_data.db`
- Update table references (e.g., `station_lists` → `stations`)
- Update queries to use new schema
- Test all functionality

### Phase 7: Testing
- Unit tests for database operations
- Integration tests for data collection
- UI tests for dashboard and admin panel
- Performance tests with real data

### Phase 8: Deployment
- Update deployment scripts
- Update environment variables
- Update documentation
- Monitor production migration

---

## Summary

**Phases 4 & 5 deliver:**

✅ **Single unified database** - No duplication, clean schema  
✅ **Safe migration** - Backups, validation, rollback capability  
✅ **Version-controlled configs** - JSON files in git  
✅ **Flexible configuration** - Multiple station sources, filters  
✅ **Environment overrides** - Dev/staging/prod customization  
✅ **Local development** - `.local.json` files for personal settings  
✅ **Production-ready** - Comprehensive error handling, logging  
✅ **Well-documented** - Complete guides and examples  

The foundation is now in place for the final code updates and deployment! 🎉
