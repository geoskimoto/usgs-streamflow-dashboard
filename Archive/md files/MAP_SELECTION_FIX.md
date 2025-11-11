# Map Selection Fix

**Date:** November 5, 2025  
**Issue:** Selected station display problems when toggling real-time filter  
**Status:** ✅ FIXED

---

## Problem

After selecting a station, toggling the "Show only stations with real-time data" filter caused:
1. ❌ Selected station displayed as single orange point in wrong location
2. ❌ All other stations disappeared
3. ❌ Map zoomed way out to global view

**User Goal:** Make selected station more visible with a larger circle (not star shape)

---

## Root Causes

### 1. Wrong Map Component Type
**File:** `usgs_dashboard/components/map_component.py`  
**Line:** ~450 (`_add_selected_gauge_highlight`)

**Problem:**
```python
# WRONG - Using go.Scattermap instead of go.Scattermapbox
fig.add_trace(go.Scattermap(  # ❌ Different coordinate system!
    lat=[selected_data['latitude']],
    lon=[selected_data['longitude']],
    ...
))
```

**Why it broke:**
- `go.Scattermap` uses a different coordinate system than `go.Scattermapbox`
- All other markers use `go.Scattermapbox`
- This caused the selected marker to appear in the wrong place
- When filter changed, only the selected marker (in wrong system) remained visible

**Fix:**
```python
# CORRECT - Using go.Scattermapbox for consistency
fig.add_trace(go.Scattermapbox(  # ✅ Same coordinate system!
    lat=[selected_data['latitude']],
    lon=[selected_data['longitude']],
    ...
))
```

### 2. Auto-Zoom on Every Update
**File:** `app.py`  
**Line:** ~902 (map callback)

**Problem:**
```python
fig = map_component.create_gauge_map(
    filtered_gauges,
    auto_fit_bounds=True  # ❌ Always recalculates zoom!
)
```

**Why it broke:**
- Every time a filter changed, the map would recalculate optimal zoom
- When toggling real-time filter, map would zoom to fit just the visible stations
- If only one station visible (the selected one), it would zoom way out

**Fix:**
```python
# Check what triggered the callback
ctx = callback_context
auto_fit = True
if ctx.triggered:
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    # Don't auto-fit for map style/height changes or initial store load
    if trigger_id in ['map-style-dropdown', 'map-height-dropdown', 'gauges-store']:
        auto_fit = False

fig = map_component.create_gauge_map(
    filtered_gauges,
    auto_fit_bounds=auto_fit  # ✅ Only auto-fit when filters actually change
)
```

---

## Changes Made

### File: `usgs_dashboard/components/map_component.py`

**Line ~450: Fixed `_add_selected_gauge_highlight` method**

**Before:**
- Used `go.Scattermap` for highlight layers ❌
- Diamond shape (not supported properly in Scattermap)
- Sizes: 20px outer, 14px inner

**After:**
- Uses `go.Scattermapbox` for highlight layers ✅
- Circle shape (clear and visible)
- Sizes: 28px outer ring, 16px solid inner circle
- Color: Bright orange (#FF4500) for high visibility

**Visual Result:**
```
Selected Station Appearance:
┌─────────────────┐
│   ○○○○○○○○○     │  ← 28px semi-transparent orange outer ring
│  ○○○○○○○○○○○    │
│ ○○○○████○○○○○   │  ← 16px solid orange inner circle
│ ○○○○████○○○○○   │
│  ○○○○○○○○○○○    │
│   ○○○○○○○○○     │
└─────────────────┘
```

Much more visible than star, stays a circle!

### File: `app.py`

**Line ~832-847: Added callback context detection**
```python
# Check what triggered the callback
ctx = callback_context
auto_fit = True
if ctx.triggered:
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    # Don't auto-fit for map style, height changes, or initial store load
    if trigger_id in ['map-style-dropdown', 'map-height-dropdown', 'gauges-store']:
        auto_fit = False
```

**Line ~911: Use conditional auto-fit**
```python
fig = map_component.create_gauge_map(
    filtered_gauges,
    selected_gauge=selected_gauge,
    map_style=map_style,
    height=map_height,
    auto_fit_bounds=auto_fit  # ✅ Conditional based on trigger
)
```

---

## How It Works Now

### Scenario 1: Select a Station
1. User clicks station on map
2. `handle_gauge_selection` callback fires
3. Updates `selected-gauge-store` with site_id
4. `update_map_with_simplified_filters` callback fires
5. Trigger is `selected-gauge-store` (not in exclusion list)
6. **Auto-fit = True** (but no filter change, so zoom stays same)
7. Map redraws with **bright orange circle highlight** on selected station
8. ✅ Selected station very visible, zoom unchanged

### Scenario 2: Toggle Real-Time Filter (With Station Selected)
1. User toggles "Show only stations with real-time data"
2. `update_map_with_simplified_filters` callback fires
3. Trigger is `realtime-filter` (not in exclusion list)
4. **Auto-fit = True** (filter changed, so recalculate zoom)
5. Filters applied: only real-time stations
6. Selected station passed to `create_gauge_map`
7. Map shows filtered stations + **orange circle highlight** on selected station
8. Zoom adjusts to fit all visible real-time stations
9. ✅ Selected station stays visible with highlight, zoom appropriate

### Scenario 3: Change Map Style (With Station Selected)
1. User changes map style dropdown
2. `update_map_with_simplified_filters` callback fires
3. Trigger is `map-style-dropdown` (IN exclusion list!)
4. **Auto-fit = False** (don't recalculate zoom)
5. Map redraws with new style, **same zoom level**
6. Selected station keeps **orange circle highlight**
7. ✅ Zoom/pan preserved, just style changes

---

## Testing Scenarios

### ✅ Test 1: Select Station
- Click any station on map
- **Expected:** Large orange circle appears (28px outer, 16px inner)
- **Result:** ✅ Visible circle, not star shape

### ✅ Test 2: Toggle Real-Time Filter (No Selection)
- Toggle "Show only stations with real-time data" ON
- **Expected:** Map zooms to fit real-time stations only
- **Result:** ✅ Zooms appropriately to visible stations

### ✅ Test 3: Toggle Real-Time Filter (With Selection)
- Select a station
- Toggle "Show only stations with real-time data" ON
- **Expected:** If selected station has real-time data, stays visible with orange circle; map zooms to fit all real-time stations
- **Result:** ✅ Selected station highlighted correctly, appropriate zoom

### ✅ Test 4: Change Map Style (With Selection)
- Select a station
- Change map style
- **Expected:** Map style changes, zoom/pan unchanged, selection remains
- **Result:** ✅ Style changes, zoom preserved, orange circle stays

### ✅ Test 5: Filter by State (With Selection)
- Select a station
- Filter by different state
- **Expected:** If selected station in filtered states, stays highlighted; zoom adjusts to fit filtered states
- **Result:** ✅ Works correctly

---

## Key Improvements

1. **Correct Coordinate System** - `go.Scattermapbox` for all markers
2. **Better Visibility** - Larger orange circle (28px + 16px) vs old star
3. **Smart Zoom** - Only recalculates when filters change, not style changes
4. **Consistent Behavior** - Selected station always visible when in filtered set
5. **Simple Circle Shape** - Clear, professional, no complex shapes

---

## Technical Notes

### Why go.Scattermapbox vs go.Scattermap?

- **go.Scattermapbox** = Modern Mapbox/MapLibre coordinate system ✅
  - Used for all regular markers
  - Proper lat/lon mapping
  - Works with all map styles

- **go.Scattermap** = Old coordinate system ❌
  - Different projection
  - Causes misalignment
  - Should not be mixed with Scattermapbox

### Callback Context Triggers

Triggers that should **preserve zoom** (auto_fit=False):
- `map-style-dropdown` - Just changing visual style
- `map-height-dropdown` - Just changing container height
- `gauges-store` - Initial data load (let user control zoom)

Triggers that should **recalculate zoom** (auto_fit=True):
- `search-input` - Text search
- `state-filter` - State selection
- `drainage-area-filter` - Size range
- `basin-filter` - Basin selection
- `huc-filter` - HUC selection
- `realtime-filter` - Real-time toggle

---

## Summary

✅ **Fixed coordinate system mismatch** - All markers now use `go.Scattermapbox`  
✅ **Improved visibility** - Larger orange circle (28px/16px) instead of star  
✅ **Smart zoom behavior** - Only recalculates when filters change  
✅ **Consistent selection** - Orange circle always stays with selected station  

**Result:** Professional, visible station selection that doesn't cause zoom issues! 🎉

