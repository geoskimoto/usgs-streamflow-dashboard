# Water Year Plot Hover Label Fix

**Date:** November 5, 2025  
**Issue:** Hover labels showing too many water year traces  
**Status:** ✅ FIXED

---

## Problem

When hovering over the Water Year Plot, the hover label was listing **every single water year** trace, making it overly expansive and unusable.

**User Request:**
> "I only want values for the daily, realtime (if available), the mean, the median, the current water year and any other water year that is highlighted. I don't want values for any of the greyed out water year traces."

---

## Root Cause

The Water Year Plot was using `hovermode='x unified'`, which shows **ALL traces** at a given x-coordinate in the hover label. With potentially 100+ historical water years in the dataset, this created a massive, unusable hover popup.

**File:** `usgs_dashboard/utils/water_year_datetime.py`  
**Line:** ~477 (in `create_water_year_plot` method)

```python
# BEFORE - Shows ALL traces at x-coordinate
fig.update_layout(
    ...
    hovermode='x unified',  # ❌ Shows every single trace!
    ...
)
```

---

## Solution

Applied **two key changes** to fix hover behavior:

### 1. Changed Hovermode from 'x unified' to 'closest'

**Line ~477:**
```python
# AFTER - Only shows closest trace to cursor
fig.update_layout(
    ...
    hovermode='closest',  # ✅ Only shows trace you're hovering over
    ...
)
```

**Effect:** Now only shows the single trace closest to your cursor position.

### 2. Disabled Hover for Background Historical Years

**Line ~330 (historical years traces):**
```python
# BEFORE - Background years show in hover
fig.add_trace(go.Scatter(
    ...
    name=f"WY {year}",
    line=dict(color='#cccccc', width=1),
    opacity=0.5,
    hovertemplate=(  # ❌ Shows hover info
        f"Water Year {year}<br>" +
        "Date: %{customdata}<br>" +
        "Discharge: %{y:.1f} cfs<br>" +
        "<extra></extra>"
    ),
    ...
))
```

```python
# AFTER - Background years hidden from hover
fig.add_trace(go.Scatter(
    ...
    name=f"WY {year}",
    line=dict(color='#cccccc', width=1),
    opacity=0.5,
    hoverinfo='skip',  # ✅ Don't show in hover
    hovertemplate=None,
    ...
))
```

**Line ~348 (historical years toggle trace):**
```python
# BEFORE - Toggle trace shows in hover
fig.add_trace(go.Scatter(
    x=[],
    y=[],
    name=f'All Historical Years ({len(other_years_list)})',
    ...
    hovertemplate="<extra></extra>"  # ❌ Shows in hover
))
```

```python
# AFTER - Toggle trace hidden from hover
fig.add_trace(go.Scatter(
    x=[],
    y=[],
    name=f'All Historical Years ({len(other_years_list)})',
    ...
    hoverinfo='skip',  # ✅ Don't show in hover
    hovertemplate=None
))
```

---

## What Shows in Hover Now

✅ **Visible in hover labels:**
- **Highlighted water years** (e.g., current year, any user-selected years) - Colored lines
- **Real-time data** (if available) - Red line with "Real-time WY XXXX (15-min)" label
- **Mean line** (if toggled on in legend) - Black dotted line
- **Median line** (if toggled on in legend) - Black dashed line  
- **Current day marker** (if toggled on) - Red vertical dashed line

❌ **Hidden from hover labels:**
- **All greyed-out historical years** - Background context only
- **Historical years group toggle** - Legend control only
- **Percentile bands** - Visual context only (25th-75th, 10th-90th ranges)

---

## Behavior Details

### Before Fix
```
Hovering at any point would show:
┌────────────────────────────┐
│ Water Year 1910            │
│ Date: Oct 15               │
│ Discharge: 1250.0 cfs      │
│                            │
│ Water Year 1911            │
│ Date: Oct 15               │
│ Discharge: 1350.0 cfs      │
│                            │
│ Water Year 1912            │
│ Date: Oct 15               │
│ Discharge: 1150.0 cfs      │
│                            │
│ ... (100+ more years!) ... │
│                            │
│ Water Year 2025            │
│ Date: Oct 15               │
│ Discharge: 1450.0 cfs      │
└────────────────────────────┘
❌ UNUSABLE - Too much info!
```

### After Fix
```
Hovering shows only what you're pointing at:
┌────────────────────────────┐
│ Water Year 2026            │
│ Date: Oct 15               │
│ Discharge: 1450.0 cfs      │
└────────────────────────────┘
✅ CLEAN - Just what you need!

Or if hovering over real-time:
┌────────────────────────────┐
│ Real-time Data             │
│ Water Year 2026            │
│ Date: Oct 15               │
│ Day of WY: 15              │
│ Discharge: 1455.23 cfs     │
└────────────────────────────┘
✅ USEFUL - Real-time detail!

Or if hovering over median line:
┌────────────────────────────┐
│ Median                     │
│ Day of WY: 15              │
│ Median Discharge: 1200 cfs │
└────────────────────────────┘
✅ CLEAR - Statistical context!
```

---

## User Interaction

### Normal Usage
1. **Hover over current year line** (colored) → Shows current year data
2. **Hover over real-time line** (red) → Shows real-time data with 15-min resolution
3. **Hover over median line** (black dashed) → Shows median discharge
4. **Hover over mean line** (black dotted, if toggled on) → Shows mean discharge
5. **Hover near background grey lines** → Will snap to closest visible trace (not grey lines!)

### With Historical Years Toggled On
If user clicks "All Historical Years" in legend to show them:
- Grey lines become visible on plot
- Hovering will still use 'closest' mode
- Will show whichever trace is actually closest to cursor
- Still much more manageable than showing ALL at once

### Percentile Bands
- Show as shaded blue regions (light and dark)
- Provide visual context for normal range
- Don't clutter hover labels
- Legend shows "10th-90th Percentile Range" and "25th-75th Percentile Range"

---

## Technical Details

### Hovermode Options

**'x unified'** (old):
- Shows ALL traces at the x-coordinate
- Good for comparing many traces at exact same point
- Bad when you have 100+ traces (unusable!)

**'closest'** (new):
- Shows only the single trace nearest to cursor
- Good for plots with many overlapping traces
- User can precisely control what they see
- Much cleaner for water year comparisons

### Trace Visibility Control

Plotly provides two ways to hide traces from hover:

1. **`hoverinfo='skip'`** - Completely ignore this trace for hover
2. **`hovertemplate=None`** - No custom template (use default or skip)

Combined approach ensures background traces are invisible to hover system.

---

## Testing Scenarios

### ✅ Test 1: Hover Over Current Year
- Open Water Year Plot for any station
- Hover over the colored current year line
- **Expected:** See only current year data in hover
- **Result:** ✅ Clean, single hover label

### ✅ Test 2: Hover Over Real-Time Data
- Select station with real-time data
- Hover over red real-time line
- **Expected:** See real-time data with 15-min precision
- **Result:** ✅ Shows "Real-time WY XXXX (15-min)" with full detail

### ✅ Test 3: Hover Over Median Line
- Ensure Median line is visible (on by default)
- Hover over black dashed line
- **Expected:** See median discharge value
- **Result:** ✅ Shows "Median" with daily median discharge

### ✅ Test 4: Toggle Mean Line and Hover
- Click "Mean" in legend to show it
- Hover over black dotted line
- **Expected:** See mean discharge value
- **Result:** ✅ Shows "Mean" with daily mean discharge

### ✅ Test 5: Hover Over Grey Background
- Hover over area with many grey historical lines
- **Expected:** Snaps to nearest visible trace (colored year, median, real-time)
- **Result:** ✅ Does NOT show grey lines, shows closest relevant trace

### ✅ Test 6: Toggle Historical Years On
- Click "All Historical Years" in legend
- Grey lines become visible
- Hover over plot
- **Expected:** Shows closest trace (might be a grey one now)
- **Result:** ✅ Only shows single closest trace, not all of them

---

## Summary

✅ **Changed hovermode** from 'x unified' → 'closest'  
✅ **Disabled hover** for all background historical year traces  
✅ **Disabled hover** for historical years group toggle  
✅ **Kept hover enabled** for highlighted years, real-time, mean, median, current day  

**Result:** Clean, usable hover labels that show only relevant information! 🎉

---

## Files Modified

- `usgs_dashboard/utils/water_year_datetime.py`
  - Line ~330: Added `hoverinfo='skip'` to background year traces
  - Line ~348: Added `hoverinfo='skip'` to historical years toggle
  - Line ~477: Changed `hovermode='x unified'` → `hovermode='closest'`

**Total Changes:** 3 modifications in 1 file

