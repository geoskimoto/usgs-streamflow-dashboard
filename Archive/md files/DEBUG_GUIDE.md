# Debug Guide - Map Loading Issue

## Current Status

Added extensive debug logging to the `load_gauge_data()` callback to understand what's happening.

## How to Debug

### Step 1: Stop the current app
```bash
# Find and kill the running process
pkill -f "python app.py"

# Or if that doesn't work:
ps aux | grep "python app.py"
# Then kill the PID: kill <PID>
```

### Step 2: Start the app fresh
```bash
cd /home/mrguy/Projects/usgs-streamflow-dashboard
python app.py
```

### Step 3: Watch for debug output

When the app starts, you should see:
```
=== load_gauge_data CALLBACK FIRED ===
pathname: /
refresh_clicks: None
site_limit: 300
Callback triggered by: [{'prop_id': 'url.pathname', 'value': '/'}]
Using site_limit: 300
Loading from database: data/usgs_cache.db
Loaded 1506 stations from filters table
Returning 1506 gauge records
Sample gauge: {'site_id': '10068500', ...}
=== CALLBACK COMPLETE ===
```

### Step 4: Check for errors

If you see:
```
ERROR in load_gauge_data: ...
```

Then we have the error message and stack trace to diagnose.

## Possible Issues to Look For

### Issue 1: Callback Not Firing At All
**Symptom:** No "=== load_gauge_data CALLBACK FIRED ===" message

**Possible Causes:**
- `dcc.Location` component not properly initialized
- Dash callback registration failed
- Multiple Input() objects causing issues

**Debug:**
- Check for Dash errors in terminal output
- Look for "Callback graph" errors

### Issue 2: Callback Fires But Returns Empty
**Symptom:** See "Returning 0 gauge records"

**Possible Causes:**
- Database query returned empty
- filters table is empty
- SQL error

**Debug:**
- Check: "Loaded X stations from filters table"
- Should say 1506 stations

### Issue 3: Callback Fires But Map Doesn't Update
**Symptom:** Debug shows 1506 records but map still says "Loading..."

**Possible Causes:**
- Data serialization issue
- Map callback not receiving data
- Dash state management issue

**Debug:**
- Check browser console for JavaScript errors
- Check if `gauges-store` is being updated

### Issue 4: Data Format Issue
**Symptom:** Error about binary data or serialization

**Possible Causes:**
- Binary columns not properly converted
- Data types not JSON serializable

**Debug:**
- Check "Sample gauge:" output
- Look for `b'...'` (binary data) in sample

## Expected Terminal Output

```
Starting USGS Streamflow Dashboard - Pacific Northwest...
Host: 0.0.0.0
Port: 8050
Debug: False
Production mode - Dashboard running
Dash is running on http://0.0.0.0:8050/

 * Serving Flask app 'app'
 * Debug mode: off

=== load_gauge_data CALLBACK FIRED ===
pathname: /
refresh_clicks: None
site_limit: 300
Callback triggered by: [{'prop_id': 'url.pathname', 'value': '/'}]
Using site_limit: 300
Loading from database: data/usgs_cache.db
Loaded 1506 stations from filters table
Returning 1506 gauge records
Sample gauge: {'site_id': '10068500', 'station_name': 'BEAR RIVER AT PESCADERO ID', ...}
=== CALLBACK COMPLETE ===
```

## What to Report Back

Please share:
1. ✅ Does the callback fire? (do you see the === markers?)
2. ✅ How many stations loaded? (should be 1506)
3. ✅ Does it complete successfully? (see === CALLBACK COMPLETE ===)
4. ✅ Any error messages?
5. ✅ What does the browser console show? (F12 → Console tab)

## Next Steps Based on Results

### If callback never fires:
→ Issue with Dash callback registration
→ Need to investigate Input/Output connections

### If callback fires but returns 0 records:
→ Issue with database query
→ Need to check filters table

### If callback fires, returns 1506 records, but map doesn't update:
→ Issue with map callback or data format
→ Need to debug `update_map_with_simplified_filters()` callback

### If you see an error:
→ Share the full error message and stack trace
→ We can diagnose the specific issue

---

**Current State:**
- ✅ App compiles with debug logging
- ✅ Database has 1506 stations (verified)
- ✅ Callback properly structured
- ⏳ Waiting for debug output from fresh app start

**Ready to debug!** 🔍
