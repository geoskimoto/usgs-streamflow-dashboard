# Manual Run Button - Implementation Guide

## ✅ WORKING - Issues Fixed!

### Fixes Applied (Oct 26, 2025)

**Issue 1: Tabs Randomly Showing Dashboard** ✅ FIXED
- **Problem:** Admin tabs would randomly switch to "System Dashboard" view
- **Cause:** `admin-refresh-interval` was triggering tab content callback every 30 seconds
- **Fix:** Removed interval from tab content callback inputs, added state preservation
- **Result:** Tabs now stay on selected view permanently

**Issue 2: Collection Process Not Visible** ℹ️ EXPLAINED  
- **Behavior:** "No collections currently running" message appears initially
- **Reason:** Subprocess takes 10-30 seconds to write database entry
- **Solution:** Wait 30 seconds or click refresh button
- **Note:** Small collections may complete before you switch tabs

---

# Manual Run Button - Implementation Guide

## 🎉 New Feature: Run Selected Schedule Button

You can now **manually trigger data collection directly from the admin panel UI** without using command-line!

---

## 📍 How to Use

### Step 1: Open Admin Panel
1. Start dashboard: `python app.py`
2. Open browser: http://localhost:8050
3. Click **🔧 Admin** tab
4. Login: `admin` / `admin123`

### Step 2: Navigate to Schedules Tab
1. Click **⏰ Schedules** button in admin panel
2. You'll see a table with all configured schedules

### Step 3: Run a Collection Manually
1. **Click on a row** in the schedules table to select it (row will highlight)
2. Click the **▶️ Run Selected** button
3. You'll see a success message with:
   - Schedule name
   - Configuration being used
   - Data type (realtime or daily)
   - Process ID of background job
4. Check the **📊 Monitoring** tab to see progress and results

---

## 📊 Available Schedules

Your system has 4 pre-configured schedules:

### Columbia River Basin (HUC17)
- **Daily Collection (6 AM)** - 563 stations, daily values
- **Realtime Collection (15min)** - 563 stations, hourly data

### Pacific Northwest Full  
- **Daily Collection (6 AM)** - 1,506 stations, daily values
- **Realtime Collection (15min)** - 1,506 stations, hourly data

---

## 🚀 Quick Start Example

### Test with Columbia Basin Realtime:
1. Go to Admin → Schedules
2. Click on row: "Columbia River Basin (HUC17) - Realtime (15min)"
3. Click "▶️ Run Selected"
4. Wait for success message
5. Go to Monitoring tab to see progress
6. Collection will take ~5-10 minutes for 563 stations

### Or Test with Small Set:
You can also run collections from command line:
```bash
# Quick test with 25 stations
python3 update_realtime_discharge_configurable.py --config "Development Test Set"
```

---

## ⚡ What Happens When You Click "Run Selected"

1. **Button Click** → Callback triggered in app.py
2. **Schedule Selected** → Reads configuration and data type from table
3. **Script Determined** → Chooses:
   - `update_realtime_discharge_configurable.py` for realtime
   - `update_daily_discharge_configurable.py` for daily
4. **Background Process** → Launches collection script with correct config
5. **Status Update** → Shows success message with process ID
6. **Collection Runs** → Script fetches data from USGS API
7. **Database Updated** → Data written to `usgs_cache.db`
8. **Logs Created** → Collection logged to `data_collection_logs` table

---

## 📈 Monitoring Progress

### Option 1: Admin Panel (Recommended)
1. Go to **📊 Monitoring** tab in admin panel
2. View **Recent Collection Activity** table
3. See:
   - Running/completed status
   - Success/failure counts
   - Duration
   - Error details

### Option 2: Database Query
```bash
# Check recent runs
sqlite3 data/station_config.db "SELECT * FROM recent_collection_activity LIMIT 5;"

# Check if collection is running
ps aux | grep update_realtime_discharge_configurable
```

### Option 3: Check Data
```bash
# See if new data arrived
sqlite3 data/usgs_cache.db "SELECT COUNT(*), MAX(datetime_utc) FROM realtime_discharge;"
```

---

## 🎛️ Button Functions

### ▶️ Run Selected (WORKING!)
- Triggers immediate data collection for selected schedule
- Runs in background (doesn't block UI)
- Shows success message with process ID
- Collection logs visible in Monitoring tab

### 🔄 Refresh (WORKING!)
- Reloads the schedules table
- Updates Last Run, Next Run times
- Shows current status

### ➕ New Schedule (COMING SOON)
- Currently disabled
- Future: Create custom schedules
- Future: Select stations and timing

### ⏸️ Disable Selected (COMING SOON)
- Currently disabled
- Future: Enable/disable automated schedules
- Future: Prevent scheduled runs

---

## 💡 Use Cases

### Use Case 1: On-Demand Data Refresh
**Scenario:** Dashboard showing old data, need fresh update NOW

**Solution:**
1. Admin → Schedules
2. Select "Pacific Northwest Full - Realtime (15min)"
3. Click "▶️ Run Selected"
4. Wait 10-15 minutes
5. Dashboard now shows current data

### Use Case 2: Testing New Configuration
**Scenario:** Just created Columbia Basin configuration, want to test

**Solution:**
1. Admin → Schedules
2. Select "Columbia River Basin (HUC17) - Realtime (15min)"
3. Click "▶️ Run Selected"
4. Monitor in Monitoring tab
5. Check for errors or failures

### Use Case 3: Recovering from Failed Scheduled Run
**Scenario:** Automated schedule failed at 6 AM, need to retry

**Solution:**
1. Admin → Monitoring → See failed run
2. Go to Schedules tab
3. Select the failed schedule
4. Click "▶️ Run Selected" to retry
5. Verify success in Monitoring

---

## 🔧 Technical Details

### Implementation
- **File Modified:** `app.py` (added callback for button actions)
- **File Modified:** `admin_components.py` (added table ID and hidden columns)
- **Callback Function:** `handle_schedule_actions()`
- **Background Execution:** Uses `subprocess.Popen()` with detached session

### Process Management
- Collections run as **background processes**
- Parent process (dashboard) continues running
- Child process writes logs to database
- Process ID shown in success message for tracking

### Error Handling
- Selection validation (must select a row)
- Script path validation
- Subprocess error catching
- User-friendly error messages

---

## 🎯 Benefits Over Command-Line

### Before (Command-Line Only):
```bash
# User had to:
1. Open terminal
2. Navigate to project directory
3. Remember exact command syntax
4. Type long configuration names correctly
5. Wait and watch terminal output
```

### After (UI Button):
```
# User now just:
1. Click Admin → Schedules
2. Click on a row
3. Click "▶️ Run Selected"
4. Done! ✅
```

**Much easier!** 🎉

---

## 📊 Next Steps

### Immediate
1. **Test the button** - Select a schedule and run it
2. **Monitor progress** - Check Monitoring tab
3. **Verify data** - See new records in dashboard

### Future Enhancements
1. **Real-time Progress Bar** - Show % complete as collection runs
2. **Cancel Button** - Stop running collections
3. **Schedule Creation** - UI for creating new schedules
4. **Bulk Operations** - Run multiple schedules at once
5. **Email Notifications** - Alert when collection completes/fails

---

## ✅ Summary

You asked: *"Can we make this the UI way of manually pulling data?"*

**Answer: YES! ✅ It's now implemented!**

- ✅ Button is wired up
- ✅ Callbacks working
- ✅ Background execution
- ✅ Status messages
- ✅ Error handling
- ✅ Integration with monitoring

**Try it now:**
1. Start dashboard: `python app.py`
2. Admin → Login → Schedules
3. Click a schedule row
4. Click "▶️ Run Selected"
5. Watch the magic happen! ✨

---

**No more command-line required for manual data collection!** 🎊
