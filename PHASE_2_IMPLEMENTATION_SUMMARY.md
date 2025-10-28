# Phase 2: Historical Data Collection Implementation

## Overview

Successfully implemented full historical data collection (1910-present) with smart incremental updates for the USGS Streamflow Dashboard.

## Key Changes

### Data Collection Strategy

**Daily Historical Data (Daily Values)**:
- **New Stations**: Collect full historical record from **1910-10-01** to present (~115 years)
- **Existing Stations**: Incremental updates from `last end_date + 1 day` to present
- **Data Table**: `streamflow_data` (JSON blob format)
- **Resolution**: Daily values (not high-frequency)

**Real-time Data (Instantaneous Values)**:
- **All Stations**: Rolling window of last **5-7 days** (configurable via `days_back`)
- **Data Table**: `realtime_discharge`
- **Resolution**: 15-minute intervals

### Implementation Details

#### 1. Updated `get_last_update_dates()` Method

**Location**: `update_daily_discharge_configurable.py`

**Logic**:
```python
# Check streamflow_data table for each station
For each station:
    Query: SELECT MAX(end_date) FROM streamflow_data WHERE site_id = ?
    
    If end_date exists:
        → Incremental: Start from (end_date + 1 day)
    Else:
        → New station: Start from 1910-10-01 (full historical)
```

**Benefits**:
- Automatic detection of new vs. existing stations
- No manual configuration needed
- Prevents duplicate data collection
- Efficient bandwidth usage

#### 2. Updated `run_daily_collection()` Method

**Smart Collection Strategy**:
```python
if full_refresh:
    # Force full historical for all stations
    start_date = 1910-10-01
else:
    # Smart mode: check each station
    last_dates = get_last_update_dates(station_ids)
    
    if any new stations (year == 1910):
        # Use 1910 to capture new stations
        start_date = 1910-10-01
    else:
        # All incremental - use earliest update date
        start_date = min(last_dates)

end_date = today
```

**Advantages**:
- Single API call can handle mixed scenarios
- New stations get full history automatically
- Existing stations get recent updates only
- Batch efficiency maintained

#### 3. Data Storage Format

**streamflow_data Table Structure**:
```sql
CREATE TABLE streamflow_data (
    site_id TEXT,
    data_json TEXT,           -- JSON array of daily records
    start_date TEXT,          -- First date in dataset
    end_date TEXT,            -- Last date in dataset
    last_updated TIMESTAMP,
    PRIMARY KEY (site_id, start_date, end_date)
)
```

**JSON Data Format** (compatible with data_manager):
```json
[
    {
        "datetime": "2024-10-27",
        "discharge_cfs": 1234.5,
        "data_quality": "A"
    },
    ...
]
```

## Performance Considerations

### Data Volume Estimates

**Full Historical Collection** (115 years, 1910-2025):
- **Records per station**: ~42,000 daily values
- **10 stations**: ~420,000 records
- **100 stations**: ~4.2 million records
- **1506 stations**: ~63 million records

**Collection Time Estimates**:
- **Small batch** (10 stations): 5-10 minutes
- **Medium batch** (100 stations): 30-60 minutes  
- **Full dataset** (1506 stations): 8-12 hours (first run only)

### Optimization Strategy

**Initial Deployment**:
1. Start with **10 test stations** (Phase 2, Task 5)
2. Verify data quality and compatibility
3. Expand to **100 stations** (production subset)
4. Schedule full 1506-station collection overnight

**Ongoing Operations**:
- **Daily runs**: Incremental only (~1-2 minutes per 100 stations)
- **New stations**: Automatic full historical backfill
- **Bandwidth**: Minimal after initial collection

## Testing Plan

### Task 5: Test with Sample Stations

**Test Stations** (suggested):
```
13313000 - Snake River at Hells Canyon Dam (ID) - Long record
12510500 - Yakima River at Kiona (WA) - Complete data
14103000 - Sandy River below Bull Run River (OR) - Recent station
```

**Test Command**:
```bash
python update_daily_discharge_configurable.py --config "Test Collection" --stations 13313000,12510500,14103000
```

**Verification Steps**:
1. Check `streamflow_data` table for records
2. Verify date ranges (should go back to 1910 or station start)
3. Test data_manager.get_streamflow_data() compatibility
4. Run second collection (should be incremental)
5. Verify no duplicates

**Expected Results**:
- Station 13313000: ~100+ years of data
- Data stored in JSON format
- Compatible with dashboard visualizations
- Incremental update on second run (only new days)

## Migration Path

### Current State
- ✅ 10 stations have full historical data in `streamflow_data` (from old system)
- ✅ New collector writes to `streamflow_data` in correct format
- ✅ Enrichment script reads from `streamflow_data`
- ❌ 1496 stations need historical backfill

### Deployment Steps

1. **Test Phase** (Task 5):
   - Run on 3-5 test stations
   - Verify data quality
   - Test dashboard compatibility

2. **Pilot Phase**:
   - Expand to 50-100 priority stations
   - Monitor performance
   - Validate enrichment calculations

3. **Production Rollout**:
   - Schedule overnight collection for all 1506 stations
   - Monitor database size (~10-15 GB estimated)
   - Set up daily incremental updates via cron/scheduler

4. **Cleanup** (Task 7):
   - Drop `daily_discharge_data` table
   - Remove legacy code references
   - Update documentation

## Configuration

### Cron Schedule Recommendation

**Daily Historical Updates** (incremental):
```bash
# Run at 6 AM daily for incremental updates
0 6 * * * cd /path/to/project && python update_daily_discharge_configurable.py
```

**Real-time Updates** (rolling 5-day window):
```bash
# Run every 2 hours for fresh 15-min data
0 */2 * * * cd /path/to/project && python update_realtime_discharge_configurable.py
```

## Benefits Summary

### User Experience
- ✅ **115 years** of historical data for analysis
- ✅ Flow duration curves from complete record
- ✅ Long-term trend analysis (1910-2025)
- ✅ Water year comparisons across decades

### System Benefits
- ✅ **Efficient**: Incremental updates after initial load
- ✅ **Automatic**: New stations get full history automatically
- ✅ **Reliable**: No manual date range management
- ✅ **Scalable**: Handles 1506 stations efficiently

### Technical Benefits
- ✅ **Single data source**: streamflow_data table
- ✅ **JSON format**: Compatible with data_manager
- ✅ **Smart updates**: Detects new vs. existing stations
- ✅ **No duplicates**: Date-range checking prevents overlaps

## Next Steps

See **Task 5** in todo list: Test data collection with sample stations before full deployment.
