# Map Loading Fix - Column Name Compatibility

**Issue:** Map was not displaying any stations after database migration  
**Date:** November 6, 2024  
**Branch:** feature/remove-legacy-system  
**Status:** ✅ FIXED

## Problem

After migrating to the unified database (`usgs_data.db`), the map component was not displaying any stations despite having 1,506 stations in the database.

## Root Cause

**Column name mismatch between database schema and application code:**

- **Database schema** (`stations` table): Uses column name `usgs_id`
- **Application code** (map_component.py, callbacks): Expects column name `site_id`

The original `filters` table (old schema) used `site_id`, but the new unified schema standardized on `usgs_id` as the column name.

## Verification Steps

### 1. Confirmed stations exist in database
```bash
sqlite3 data/usgs_data.db "SELECT COUNT(*) FROM stations;"
# Result: 1506 stations
```

### 2. Confirmed stations have location data
```bash
sqlite3 data/usgs_data.db "SELECT usgs_id, latitude, longitude FROM stations LIMIT 5;"
# Result: All stations have lat/lon data
```

### 3. Identified column name mismatch
```bash
sqlite3 data/usgs_data.db "PRAGMA table_info(stations);"
# Column: usgs_id (not site_id)
```

### 4. Checked map component expectations
```bash
grep -n "site_id" usgs_dashboard/components/map_component.py
# 14 references to 'site_id' found
```

## Solution

Added column rename in `app.py` `load_gauge_data()` function to maintain backward compatibility:

```python
# Rename usgs_id to site_id for backward compatibility with map component
if 'usgs_id' in filters_df.columns and 'site_id' not in filters_df.columns:
    filters_df = filters_df.rename(columns={'usgs_id': 'site_id'})
    print("Renamed 'usgs_id' to 'site_id' for compatibility")
```

**Location:** `/home/mrguy/Projects/usgs-streamflow-dashboard/app.py`, line ~767

## Files Modified

- `app.py` - Added column rename in `load_gauge_data()` function

## Alternative Solutions Considered

### Option 1: Update all code to use 'usgs_id' ❌
- **Rejected:** Would require changing 14+ references across multiple files
- Risk of breaking other functionality
- More extensive testing required

### Option 2: Add SQL alias in query ❌
- **Rejected:** Requires changes in multiple query locations
- Less maintainable

### Option 3: Rename column in database schema ❌
- **Rejected:** Would require re-running migration
- Schema uses `usgs_id` consistently (better naming)
- Breaking change for other components

### Option 4: Rename on load (CHOSEN) ✅
- **Selected:** Single point of change
- Maintains backward compatibility
- No schema changes needed
- Clear intent with comment
- Easy to maintain

## Testing

### Before Fix
- Map displayed "Loading gauge data..." message
- No stations appeared on map
- Sidebar showed "1506 sites" but map was empty

### After Fix
- App starts successfully
- Stations data loaded: 1,506 records
- Column rename applied automatically
- Map component receives data in expected format

## Related Code Locations

### Map Component Dependencies
File: `usgs_dashboard/components/map_component.py`
- Line 72: Validates required columns including `site_id`
- Line 122: Checks selected gauge in `site_id` column
- Line 175, 274: Uses `site_id` in hover text
- Line 394, 424: References `site_id` for selected gauge
- Line 486: Example data uses `site_id`

### Callback Dependencies
File: `app.py`
- Line ~850: Search filter uses `site_id` column
- Line ~860: State filter references data with `site_id`
- Line ~894: Real-time filter matches `site_id`

## Schema Documentation

### Stations Table (Unified Database)
```sql
CREATE TABLE stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usgs_id TEXT NOT NULL UNIQUE,  -- ⚠️ Named 'usgs_id', not 'site_id'
    station_name TEXT NOT NULL,
    state TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    drainage_area REAL,
    basin TEXT,
    huc_code TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    -- ... other columns
);
```

### Legacy Filters Table (Old Database)
```sql
CREATE TABLE filters (
    site_id TEXT PRIMARY KEY,  -- ⚠️ Old name was 'site_id'
    station_name TEXT,
    state TEXT,
    latitude REAL,
    longitude REAL,
    -- ... other columns
);
```

## Future Considerations

### Long-term Solution Options

**Option A: Gradual code migration** (Recommended)
- Keep the rename in `load_gauge_data()`
- Gradually update other components to use `usgs_id`
- Eventually remove the rename when all code is updated
- Pro: Minimal risk, gradual transition
- Con: Temporary inconsistency

**Option B: Add database view**
- Create a view `filters` that aliases `usgs_id` as `site_id`
- Keep old code working with view
- Pro: Database-level compatibility layer
- Con: Extra database object to maintain

**Option C: Complete code refactor**
- Update all code references to use `usgs_id`
- Remove column rename
- Pro: Clean, consistent naming
- Con: Large change surface, more testing needed

## Commit History

- **aa0652c** - Fix map loading: rename usgs_id to site_id for compatibility
- **534c7fc** - Phase 6: Update all Python code to use unified database

## Verification Commands

### Check if app loads stations correctly
```python
python -c "
import sqlite3
import pandas as pd
conn = sqlite3.connect('data/usgs_data.db')
df = pd.read_sql_query('SELECT * FROM stations LIMIT 5', conn)
print('Columns:', df.columns.tolist())
print('Has usgs_id:', 'usgs_id' in df.columns)
print('Has site_id:', 'site_id' in df.columns)
conn.close()
"
```

### Test the rename logic
```python
python -c "
import pandas as pd
import sqlite3
conn = sqlite3.connect('data/usgs_data.db')
df = pd.read_sql_query('SELECT * FROM stations LIMIT 5', conn)
conn.close()

# Apply rename
if 'usgs_id' in df.columns and 'site_id' not in df.columns:
    df = df.rename(columns={'usgs_id': 'site_id'})
    print('✅ Rename successful')
    print('Columns after rename:', df.columns.tolist())
else:
    print('❌ Rename not applied')
"
```

## Success Criteria

- ✅ App starts without errors
- ✅ Stations table has 1,506 records
- ✅ All stations have latitude/longitude
- ✅ Column rename applied automatically on load
- ✅ Map component receives data in expected format (`site_id` column present)
- ✅ No code changes needed in map_component.py
- ✅ Backward compatibility maintained

## Summary

A simple column rename in the data loading function resolved the map display issue while maintaining backward compatibility with existing code. This allows the unified database to use the more accurate `usgs_id` column name while keeping all existing application code working without changes.

The fix is minimal, maintainable, and clearly documented for future developers.
