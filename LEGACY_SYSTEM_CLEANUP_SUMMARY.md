# Legacy System Cleanup Summary

## Completed Actions (Phase 1)

### Files Archived
- ✅ `update_daily_discharge.py` → `Archive/legacy_collectors/`
- ✅ `update_realtime_discharge.py` → `Archive/legacy_collectors/`

### Database Cleanup
- ✅ Dropped `gauge_metadata` table (was empty)
- ✅ Dropped `gauges` table (was empty)
- ✅ Removed CREATE TABLE statements from `usgs_dashboard/data/data_manager.py`

### Code Updates
- ✅ Updated `smart_scheduler.py` to use configurable scripts
- ✅ Removed legacy manual run UI components from `app.py`
- ✅ Updated `update_daily_discharge_configurable.py` to use `streamflow_data` table
- ✅ Added JSON blob format storage (compatible with data_manager)

### Table Consolidation
**NEW SYSTEM:**
- `streamflow_data` - Historical daily data (1910-present) in JSON format
- `realtime_discharge` - Real-time 15-min data (last 5 days)
- `filters` - Station metadata (THE primary metadata table)

**DEPRECATED (to be removed after Phase 2 testing):**
- `daily_discharge_data` - Replaced by streamflow_data
- Legacy methods in data_manager.py that reference dropped tables

## Remaining Manual Cleanup Tasks

### app.py - Legacy Callbacks to Remove

The following callbacks in `app.py` still reference the removed UI components and need to be deleted:

1. **Lines ~810-900**: `update_job_status_and_history()` callback
   - References: `realtime-status`, `daily-status`, `job-history-display`
   - References removed buttons: `run-realtime-btn`, `run-daily-btn`, `toggle-realtime-btn`, `toggle-daily-btn`

2. **Lines ~910-940**: `update_realtime_frequency()` callback
   - References: `realtime-frequency-input`

3. **Lines ~940-970**: `update_daily_frequency()` callback  
   - References: `daily-frequency-input`

**Action Required**: Manually delete these three callback functions since they no longer have corresponding UI elements.

### Setup Scripts to Update

These scripts still reference the old update scripts and need updating:

1. **`setup_scheduling.sh`**
   - Lines 20, 64-65, 78, 83-84, 158
   - Change `update_daily_discharge.py` → `update_daily_discharge_configurable.py`
   - Change `update_realtime_discharge.py` → `update_realtime_discharge_configurable.py`

2. **`setup_crontab.sh`**
   - Lines 8, 11
   - Same updates as above

3. **`check_status.py`**
   - Lines 89, 120
   - Update to reference configurable scripts

## System Status

**Active System**: New configurable collector system
- Uses `station_config_manager.py` for database-driven station configuration
- Writes to `streamflow_data` table in JSON format
- Compatible with main dashboard data_manager

**Next Steps (Phase 2)**:
- Update data collection from 30 days to full historical range (1910-present)
- Implement incremental update strategy
- Test with sample stations
- Drop `daily_discharge_data` table after successful testing
