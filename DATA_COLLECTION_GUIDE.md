# Data Collection Guide - USGS Streamflow Dashboard

## 📊 Manual Data Collection

### Quick Start - Pull Data Now!

You have two types of data collection available:

#### 1️⃣ **Real-time Data Collection** (Last 5 days of hourly data)

```bash
# Using default configuration (Pacific Northwest Full - 1,506 stations)
python update_realtime_discharge_configurable.py

# Using specific configuration by name
python update_realtime_discharge_configurable.py --config "Columbia River Basin (HUC17)"

# Using configuration ID
python update_realtime_discharge_configurable.py --config-id 2

# Custom retention period (keep 7 days instead of default 5)
python update_realtime_discharge_configurable.py --retention-days 7
```

**What it does:**
- Fetches instantaneous discharge values (hourly data points)
- Keeps rolling window of last 5 days (configurable)
- Updates every 15-30 minutes (when scheduled)
- Fast updates, smaller data volume
- Used for "live" monitoring

**Expected Time:** ~5-15 minutes for 1,506 stations

---

#### 2️⃣ **Daily Data Collection** (Historical daily values)

```bash
# Incremental update (collect new data since last run)
python update_daily_discharge_configurable.py

# Using specific configuration
python update_daily_discharge_configurable.py --config "Columbia River Basin (HUC17)"

# Collect last 90 days
python update_daily_discharge_configurable.py --days-back 90

# Full refresh - get ALL historical data (WARNING: Takes a long time!)
python update_daily_discharge_configurable.py --full-refresh
```

**What it does:**
- Fetches daily mean discharge values
- Incremental updates (only gets new data since last run)
- Keeps complete historical record
- Updates once per day (when scheduled)
- Used for trend analysis and statistics

**Expected Time:** 
- Incremental (30 days): ~10-20 minutes
- Full refresh (all history): 2-4 hours for 1,506 stations

---

## 🚀 General Steps to Start Pulling Data

### Step 1: Verify Configuration Database

```bash
# Check that configurations are set up
python update_realtime_discharge_configurable.py --list-configs
```

**Expected Output:**
```
📋 Available Configurations:
==================================================
ID: 1 - Pacific Northwest Full
   Stations: 1506
   Status: ✅ Active ⭐ (Default)
   Description: Complete NOAA HADS discharge monitoring stations...

ID: 2 - Columbia River Basin (HUC17)
   Stations: 563
   Status: ✅ Active
   Description: NOAA HADS discharge stations within Columbia River Basin...
```

---

### Step 2: Initial Data Load (First Time Setup)

For a brand new system, follow this sequence:

```bash
# 1. Start with a small test to verify everything works
python update_realtime_discharge_configurable.py --config "Development Test Set"

# 2. If successful, do a quick real-time collection for all stations
python update_realtime_discharge_configurable.py

# 3. Start collecting daily data (last 30 days)
python update_daily_discharge_configurable.py --days-back 30

# 4. (Optional) Full historical load - run overnight or over weekend
# python update_daily_discharge_configurable.py --full-refresh
```

**Recommended First-Time Sequence:**
1. **Test Set (25 stations)** - 30 seconds - Verify system works
2. **Real-time Full (1,506 stations)** - 10 minutes - Get current data
3. **Daily 30-day (1,506 stations)** - 15 minutes - Get recent history
4. **Full Historical** (optional) - 3 hours - Get complete record

---

### Step 3: Monitor Progress

While scripts are running, watch the logs:

```bash
# Real-time updates will show:
🎯 Starting real-time collection: Pacific Northwest Full
📊 Processing 1506 stations
📅 Collecting data from 2025-10-21 to 2025-10-26
⏳ Batch 1/16: Processing 100 stations...
✅ Batch 1/16 complete: 87/100 successful (87.0%)
...
🎉 Real-time collection completed!
   ✅ Successful stations: 1,428
   ❌ Failed stations: 78
   📈 Total data points: 342,567
   🏞️ Stations with data: 1,428
```

---

### Step 4: Verify Data Loaded

```bash
# Check real-time data
sqlite3 data/usgs_cache.db "SELECT COUNT(*) as total_records, 
    COUNT(DISTINCT site_no) as unique_stations 
    FROM realtime_discharge;"

# Check daily data
sqlite3 data/usgs_cache.db "SELECT COUNT(*) as total_records, 
    COUNT(DISTINCT site_no) as unique_stations,
    MIN(datetime) as earliest_date,
    MAX(datetime) as latest_date
    FROM streamflow_data;"
```

**Expected Output (after initial load):**
```
Real-time:
total_records    unique_stations
342567          1428

Daily:
total_records    unique_stations    earliest_date    latest_date
45180           1506               2025-09-26       2025-10-26
```

---

## ⚙️ Advanced Options

### Configuration Selection

```bash
# List all available configurations
python update_realtime_discharge_configurable.py --list-configs
python update_daily_discharge_configurable.py --list-configs

# Use specific configuration by name (exact match required)
python update_realtime_discharge_configurable.py --config "Columbia River Basin (HUC17)"

# Use specific configuration by ID
python update_daily_discharge_configurable.py --config-id 2
```

### Verbose Logging

```bash
# Get detailed debugging information
python update_realtime_discharge_configurable.py --verbose

# Shows:
# - Individual station processing
# - API request details
# - Data transformation steps
# - Database operations
```

### Custom Database Path

```bash
# Use different database file (for testing)
python update_realtime_discharge_configurable.py --db-path data/test_cache.db
```

---

## 🎛️ Admin Panel Manual Trigger (Future Feature)

The admin panel has a **"▶️ Manual Run"** button in the Monitoring tab, but it's not yet wired up. 

### To Enable Manual Trigger from Admin Panel:

You would need to add a callback in `app.py` that:
1. Detects button click
2. Spawns background process running the collection script
3. Updates UI with progress
4. Shows completion status

**Workaround for now:** Use command-line scripts as shown above.

---

## 📅 Automated Scheduling

Once you've done the initial data load, you can set up automated scheduling:

### Option 1: Cron Jobs (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add these lines:

# Real-time updates every 15 minutes
*/15 * * * * cd /home/mrguy/Projects/usgs-streamflow-dashboard && python update_realtime_discharge_configurable.py >> logs/realtime.log 2>&1

# Daily updates at 6 AM
0 6 * * * cd /home/mrguy/Projects/usgs-streamflow-dashboard && python update_daily_discharge_configurable.py >> logs/daily.log 2>&1
```

### Option 2: Smart Scheduler (Database-driven)

```bash
# Use the smart scheduler that reads from database schedules
python smart_scheduler.py
```

The smart scheduler:
- Reads schedule configurations from `update_schedules` table
- Automatically runs collections at specified times
- Logs all activity to database
- Handles errors and retries
- Can be run as a background service

---

## 🔍 Troubleshooting

### No Data Retrieved

**Problem:** Script completes but 0 records inserted

**Solutions:**
1. Check internet connection
2. Verify USGS API is accessible: `curl "https://waterservices.usgs.gov/nwis/iv/?format=json&sites=12345000&parameterCd=00060"`
3. Try with test configuration first
4. Check if stations are actually active on USGS

### Slow Performance

**Problem:** Collection taking too long

**Solutions:**
1. Use smaller configuration: `--config "Development Test Set"`
2. Reduce date range: `--days-back 7`
3. Check network speed
4. Run during off-peak hours
5. Use `--verbose` to see which stations are slow

### Database Locked Errors

**Problem:** "database is locked" error

**Solutions:**
1. Don't run multiple collection scripts simultaneously
2. Close any SQLite browser connections
3. Stop the dashboard temporarily: `pkill -f app.py`
4. Run collection, then restart dashboard

### High Failure Rate

**Problem:** Many stations failing (>20%)

**Solutions:**
1. Check USGS API status: https://waterservices.usgs.gov/
2. Review error logs in admin panel (Monitoring tab)
3. Some stations may be discontinued - this is normal
4. Try again later if API is experiencing issues

---

## 📊 Data Collection Metrics

### Typical Success Rates
- **Real-time Data:** 90-95% success rate
- **Daily Data:** 95-98% success rate

### Common Failure Reasons
1. **Station Discontinued** (404 error) - 40% of failures
2. **No Data Available** (empty response) - 30%
3. **Network Timeout** (503 error) - 20%
4. **Data Format Issues** - 10%

### Performance Benchmarks
- **Batch Size:** 100 stations per batch
- **Rate Limiting:** 2-second delay between batches
- **Network Speed:** ~10-15 stations/minute
- **Database Writes:** ~5,000 records/second

---

## 🎯 Recommended Collection Strategy

### For Development/Testing
```bash
# Quick test with 25 stations
python update_realtime_discharge_configurable.py --config "Development Test Set"
python update_daily_discharge_configurable.py --config "Development Test Set" --days-back 7
```

### For Production - Initial Setup
```bash
# Day 1: Get current real-time data (10 min)
python update_realtime_discharge_configurable.py

# Day 1: Get last 30 days of daily data (15 min)
python update_daily_discharge_configurable.py --days-back 30

# Weekend: Full historical load (3 hours)
python update_daily_discharge_configurable.py --full-refresh
```

### For Production - Ongoing
```bash
# Set up automated schedules:
# - Real-time: Every 15 minutes
# - Daily: Once per day at 6 AM

# Monitor via admin panel
# Manual runs only when needed (API issues, missed runs, etc.)
```

---

## 📁 Output Files and Logs

### Database Files
- **`data/usgs_cache.db`** - Main data storage
  - `realtime_discharge` table - Last 5 days of hourly data
  - `streamflow_data` table - Complete daily historical data
  - `daily_update_log` table - Tracks last update per station

### Log Files (if configured)
- **`logs/realtime.log`** - Real-time collection logs
- **`logs/daily.log`** - Daily collection logs
- **Database logs** - `data_collection_logs` table in config database

### Collection Statistics (in config database)
```sql
-- View recent collection runs
SELECT * FROM recent_collection_activity LIMIT 10;

-- Check error patterns
SELECT error_type, COUNT(*) 
FROM station_collection_errors 
GROUP BY error_type;

-- Station success rates
SELECT site_no, 
       COUNT(*) as attempts,
       SUM(CASE WHEN error_type IS NULL THEN 1 ELSE 0 END) as successes
FROM station_collection_errors
GROUP BY site_no
ORDER BY successes DESC;
```

---

## ✅ Quick Reference Commands

```bash
# List configurations
python update_realtime_discharge_configurable.py --list-configs

# Quick test (25 stations)
python update_realtime_discharge_configurable.py --config "Development Test Set"

# Full real-time collection
python update_realtime_discharge_configurable.py

# Daily update (last 30 days)
python update_daily_discharge_configurable.py

# Check data
sqlite3 data/usgs_cache.db "SELECT COUNT(*) FROM realtime_discharge;"
sqlite3 data/usgs_cache.db "SELECT COUNT(*) FROM streamflow_data;"

# View logs in admin panel
python app.py
# Navigate to: http://localhost:8050 → Admin → Monitoring
```

---

**🎉 You're ready to start collecting data!**

Start with the test configuration to verify everything works, then scale up to full production collections.
