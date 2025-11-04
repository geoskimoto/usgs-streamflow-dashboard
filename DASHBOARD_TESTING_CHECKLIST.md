# Dashboard End-to-End Testing Checklist

**Date**: October 27, 2025  
**Purpose**: Verify complete data consolidation to streamflow_data table  
**Dashboard URL**: http://localhost:8050

## Pre-Test Status

### Database State:
- **Total Stations**: 1,506 (across 6 states)
- **Stations with Historical Data**: 37 (streamflow_data table)
- **Stations with Realtime Data**: ~524 (realtime_discharge table)
- **Enrichment Status**:
  - 534 stations with `years_of_record` > 0
  - 525 stations with `years_of_record` > 50 years
  - 1,181 stations with `drainage_area` data

### State Distribution:
- CA: 501 stations
- WA: 292 stations
- OR: 216 stations
- MT: 205 stations
- NV: 168 stations
- ID: 124 stations

---

## Test 1: Map Display and State Filters ✓ or ✗

### 1.1 Initial Load
- [ ] Dashboard loads without errors
- [ ] Map displays successfully
- [ ] Default states shown (OR, WA, ID, MT)
- [ ] Station markers visible on map

### 1.2 State Filter Dropdown
**Test**: Open state filter dropdown

**Expected**:
- [ ] Shows all 6 states: OR 🌲, WA 🏔️, ID 🏔️, MT 🏔️, CA ☀️, NV 🎰
- [ ] Each state has emoji icon
- [ ] Default selection: OR, WA, ID, MT (checked)

**Actual**: _______________

### 1.3 State Filter Functionality
**Test**: Select different state combinations

- [ ] **Select CA only**: Shows ~501 California stations
- [ ] **Select NV only**: Shows ~168 Nevada stations
- [ ] **Select All States**: Shows all 1,506 stations
- [ ] **Deselect All**: Shows "No stations match filters" message

**Actual**: _______________

---

## Test 2: Years of Record Filter ✓ or ✗

### 2.1 Years Filter Display
**Test**: Check years of record slider

**Expected**:
- [ ] Slider shows range: 0 to ~116 years
- [ ] Current value displayed
- [ ] Stations update when slider moves

**Actual Range**: _____ to _____ years

### 2.2 Filter by Years
**Test**: Adjust years slider to different values

- [ ] **Set to 50+ years**: Shows ~525 stations with long records
- [ ] **Set to 100+ years**: Shows stations with full historical (1910-era start)
- [ ] **Set to 10+ years**: Shows more stations (~534)
- [ ] **Set to 0 years**: Shows all stations

**Stations Shown**:
- 50+ years: _____
- 100+ years: _____
- 10+ years: _____

---

## Test 3: Drainage Area Filter ✓ or ✗

### 3.1 Drainage Filter Display
**Test**: Check drainage area filter

**Expected**:
- [ ] Filter exists and is visible
- [ ] Shows range or input fields
- [ ] Stations update when filter applied

**Actual**: _______________

### 3.2 Filter Functionality
**Test**: Apply drainage area filter

**KNOWN STATUS**: Only 1,181 stations have drainage_area data (78% coverage after enrichment)

- [ ] **Filter 100-1000 sq mi**: Returns results (not "0 sites")
- [ ] **Filter > 5000 sq mi**: Shows major river basins
- [ ] **Clear filter**: Restores full station list

**Actual Results**:
- 100-1000 sq mi: _____ stations
- > 5000 sq mi: _____ stations

**Notes**: If returns 0, need to check filter range logic vs. available data

---

## Test 4: Station Selection and Historical Plots ✓ or ✗

### 4.1 Select Station with Historical Data
**Test**: Click on station with full historical record

**Recommended Test Stations**:
- **12510500** - Yakima River at Kiona, WA (116 years)
- **10396000** - Donner und Blitzen River near Frenchglen, OR (115 years)
- **12020000** - Chehalis River near Doty, WA (87 years)

**Expected**:
- [ ] Station info panel appears
- [ ] Shows station name, ID, location
- [ ] Shows years_of_record (should be 50-116 years, NOT "1" or "N/A")
- [ ] Loading indicator while data fetches

**Actual Station Tested**: _______________

**Years Shown**: _____ years (should match database: 87-116 years)

### 4.2 Historical Plot Display
**Test**: Verify visualizations load with full historical data

**Expected Plots**:
- [ ] **Time Series Plot**: Shows data from 1910s-2025 (NOT just 5 days!)
- [ ] **Flow Duration Curve**: Complete curve from full record
- [ ] **Water Year Comparison**: Shows multiple decades of data
- [ ] **Statistics Panel**: Shows realistic stats (not just from 5-day realtime)

**Actual Date Range in Plot**: _____ to _____

**Expected**: 1910s (or station start year) to 2025-10-27

### 4.3 Realtime Data Overlay
**Test**: Check if realtime data appears on plots

**Expected** (if station has realtime data):
- [ ] Recent 5-7 days overlaid on historical plot
- [ ] Different color/style from historical data
- [ ] Seamless connection between historical and realtime

**Actual**: _______________

---

## Test 5: Statistics Accuracy ✓ or ✗

### 5.1 Flow Duration Curve
**Test**: Click station, view flow duration curve

**Expected**:
- [ ] Curve calculated from FULL historical record (decades of data)
- [ ] Percentiles (P10, P50, P90) show realistic long-term values
- [ ] NOT calculated from just 5 days of realtime data

**Station Tested**: _______________

**Looks Realistic?**: [ ] Yes [ ] No

**Notes**: _______________

### 5.2 Water Year Statistics
**Test**: View water year comparison

**Expected**:
- [ ] Shows multiple water years (decades of data)
- [ ] Current water year (2026) highlighted
- [ ] Historical years visible for comparison
- [ ] Stats show long-term patterns

**Water Years Shown**: _____ to _____

---

## Test 6: Data Source Verification ✓ or ✗

### 6.1 Check Browser Console
**Test**: Open browser developer tools (F12), check Console tab

**Expected**:
- [ ] No JavaScript errors
- [ ] No "404 Not Found" errors
- [ ] No "table does not exist" database errors
- [ ] Data fetching logs show "Retrieved X records for site XXXXX"

**Errors Found**: _______________

### 6.2 Check Network Tab
**Test**: In developer tools, check Network tab while loading station

**Expected**:
- [ ] POST requests to `/_dash-update-component`
- [ ] Responses return data successfully (status 200)
- [ ] Response size appropriate for historical data (several KB+)

**Response Size**: _____ KB (should be large for historical data)

---

## Test 7: Edge Cases ✓ or ✗

### 7.1 Station with NO Historical Data
**Test**: Select station that only has realtime data (not in streamflow_data table)

**Expected**:
- [ ] Shows realtime data (last 5-7 days)
- [ ] years_of_record shows small number (1-5 years) or from realtime only
- [ ] No error messages
- [ ] Graceful handling

**Station Tested**: _______________

**Behavior**: _______________

### 7.2 Combine All Filters
**Test**: Apply multiple filters simultaneously

**Example**: CA only + 50+ years + 1000+ sq mi drainage

**Expected**:
- [ ] Filters work together (AND logic)
- [ ] Shows subset matching ALL criteria
- [ ] Count updates correctly
- [ ] Map updates to show only matching stations

**Stations Shown**: _____

---

## Test 8: Admin Panel (Optional) ✓ or ✗

### 8.1 Manual Data Collection
**Test**: Login to admin panel, trigger manual collection

**Steps**:
1. Navigate to admin panel
2. Login (admin / admin)
3. Select configuration (e.g., "Development Test Set")
4. Click "Update Daily Data"

**Expected**:
- [ ] Collection starts successfully
- [ ] Progress shown in logs
- [ ] "Calculating station statistics" appears in logs
- [ ] Enrichment runs automatically after collection
- [ ] years_of_record updated for collected stations

**Log Snippet**: _______________

---

## Known Issues to Watch For

### Issue 1: Years of Record
**Problem**: Was showing "1" or "N/A" before fix

**Expected Now**: 50-116 years for stations with historical data

**Status**: [ ] FIXED [ ] STILL BROKEN

### Issue 2: Drainage Area Filter
**Problem**: Was returning "0 sites"

**Root Cause**: Only 78% of stations have drainage_area data (1,181 / 1,506)

**Expected Now**: Should return results within available data range

**Status**: [ ] WORKING [ ] NEEDS FIX

### Issue 3: Historical Plot Date Range
**Problem**: Plots were showing only 5-7 days (realtime data)

**Expected Now**: Plots show full 1910-2025 historical data

**Status**: [ ] FIXED [ ] STILL SHOWING ONLY RECENT

---

## Success Criteria

### Minimum Requirements (Must Pass):
1. ✓ All 6 states (OR, WA, ID, MT, CA, NV) appear in dropdown
2. ✓ Years of record filter shows realistic values (50-116 years)
3. ✓ Clicking station with historical data shows 100+ years of plot
4. ✓ Flow duration curves calculated from full record (not 5 days)
5. ✓ No database errors in console

### Desired (Should Pass):
6. ✓ Drainage area filter returns results (not 0 sites)
7. ✓ Realtime data overlays on historical plots seamlessly
8. ✓ Statistics panels show realistic long-term values
9. ✓ Auto-enrichment works after data collection

### Nice to Have:
10. ✓ Fast load times (<2 seconds for station selection)
11. ✓ Smooth map interactions
12. ✓ No browser console warnings

---

## Test Results Summary

**Date Tested**: _______________  
**Tester**: _______________  
**Dashboard Version**: Post-consolidation (streamflow_data)

**Overall Status**: [ ] PASS [ ] FAIL [ ] PARTIAL

**Tests Passed**: _____ / _____

**Critical Issues Found**: _______________

**Non-Critical Issues Found**: _______________

**Notes**: _______________

---

## Next Steps if Tests Fail

### If Years Still Show "1" or "N/A":
1. Check `filters` table: `SELECT site_id, years_of_record FROM filters WHERE years_of_record > 0`
2. Verify enrichment ran: Check collection logs for "Updated statistics for X stations"
3. Re-run enrichment manually: `python enrich_station_metadata.py`

### If Historical Plots Show Only Recent Data:
1. Check `streamflow_data` table: `SELECT COUNT(*) FROM streamflow_data`
2. Verify data_manager queries streamflow_data (not daily_discharge_data)
3. Check browser console for SQL errors

### If Drainage Filter Returns 0:
1. Check drainage_area coverage: `SELECT COUNT(drainage_area) FROM filters WHERE drainage_area IS NOT NULL`
2. Check filter range vs. actual data: `SELECT MIN(drainage_area), MAX(drainage_area) FROM filters`
3. Adjust filter logic or run API enrichment to get more drainage_area data

---

## Testing Command to Start Dashboard

```bash
python app.py
```

Then navigate to: **http://localhost:8050**

Good luck with testing! 🧪
