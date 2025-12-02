# USGS Streamflow Dashboard - Architecture Overview

## System Architecture Analysis

This document outlines the architecture of the visualization system, focusing on the three key files: `viz_manager.py`, `streamflow_analyzer.py`, and `water_year_datetime.py`.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         app.py                               │
│                   (Main Dashboard)                           │
│  - Dash application with callbacks                           │
│  - Handles user interactions                                 │
│  - Orchestrates data fetching and visualization              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├──► data_manager (USGSDataManager)
                   │    - Fetches data from USGS API
                   │    - Manages database cache
                   │    - Handles realtime/daily data
                   │
                   └──► viz_manager (VisualizationManager)
                        ├──► streamflow_analyzer.py (EXTERNAL LIBRARY)
                        │    ├── StreamflowData class
                        │    └── StreamflowVisualizer class
                        │
                        └──► water_year_datetime.py (UTILITY)
                             └── WaterYearDateTime class
```

---

## 2. Component Breakdown

### 2.1 **viz_manager.py** - Orchestration Layer

**Purpose:** Acts as a **bridge/adapter** between the Dash app and the plotting libraries.

**Key Class:** `VisualizationManager`

**Responsibilities:**
1. **Receives plot requests from app.py** with parameters (site_id, data, plot_type, options)
2. **Decides which plotting strategy to use:**
   - Try `_create_integrated_plot()` using streamflow_analyzer (preferred)
   - Fall back to `_create_fallback_plot()` using water_year_datetime (robust)
3. **Fetches realtime data** from data_manager and overlays it
4. **Formats data** to match expected input formats for each library
5. **Returns Plotly figure** to app.py

**Design Pattern:** **Adapter Pattern** + **Strategy Pattern**
- Adapts between Dash app's expectations and the plotting libraries' interfaces
- Chooses strategy (integrated vs fallback) based on availability

**Key Methods:**
```python
create_streamflow_plot()      # Main entry point
├── _create_integrated_plot()  # Uses streamflow_analyzer.py
├── _create_fallback_plot()    # Uses water_year_datetime.py
└── _add_realtime_overlay()    # Adds 15-min data to any plot
```

---

### 2.2 **streamflow_analyzer.py** - External Analysis Library

**Purpose:** A **standalone, reusable Python library** for USGS streamflow analysis.

**Key Classes:**
1. **`StreamflowData`** - Data container and statistical analysis
2. **`StreamflowVisualizer`** - Creates publication-quality plots

**Responsibilities:**

#### StreamflowData Class:
- Fetches data from USGS NWIS (using `dataretrieval` library)
- Loads data from CSV files or dataframes
- Computes statistical analysis:
  - Daily statistics (mean, median, percentiles by day-of-year)
  - Monthly statistics
  - Annual statistics
  - Water year calculations
- **Stores processed data** for visualization

#### StreamflowVisualizer Class:
- Creates various plot types:
  - Stacked line plots (multiple water years overlaid)
  - Flow duration curves
  - Annual/monthly summaries
  - Statistical overlays (mean, median, percentile bands)
- **Highly configurable** with color schemes, line styles, etc.

**Design Pattern:** **Data Processing Pipeline**
```
Raw Data → Fetch → Process → Calculate Stats → Visualize
```

**Independence Level:** ★★★★★ (Fully independent)
- Can be used **completely standalone** outside this dashboard
- Has its own data fetching capabilities
- Self-contained with no dashboard dependencies
- Could be published as a PyPI package

**Usage in Dashboard:**
```python
# viz_manager creates instances when needed
sf_data = StreamflowData(data=df, site_id=site_id)
sf_viz = StreamflowVisualizer(sf_data)
fig = sf_viz.create_stacked_line_plot(highlight_years=[2024])
```

---

### 2.3 **water_year_datetime.py** - Specialized Utility

**Purpose:** A **specialized utility library** for water year datetime operations and plotting.

**Key Class:** `WaterYearDateTime`

**Responsibilities:**
1. **Water year calculations:**
   - Convert dates to water years (Oct 1 - Sep 30)
   - Calculate day-of-water-year (1-366)
   - Handle leap years correctly

2. **Datetime formatting for plotting:**
   - Solves Plotly's automatic datetime interpretation issues
   - Creates clean x-axis labels (month-day format)
   - Generates tick marks for water year plots

3. **Create water year plots directly:**
   - `create_water_year_plot()` - Complete plot generation
   - Overlays multiple years on same axis
   - Shows current day markers, percentiles, statistics
   - Handles zoom to current date

**Design Pattern:** **Utility/Helper Pattern** + **Domain-Specific Language (DSL)**

**Independence Level:** ★★★☆☆ (Moderately independent)
- **Can** be used in other projects that need water year handling
- **Requires** Plotly for visualization
- **Focused** on a specific domain (water year analysis)

**Why This Exists:**
Plotly has a problem: when you plot day-of-year data (1-366), it interprets it as "days since 1970-01-01", causing messy x-axes. This class solves that by using numeric x-axes with custom labels.

**Usage in Dashboard:**
```python
wy_handler = get_water_year_handler()
fig = wy_handler.create_water_year_plot(
    data, 'discharge',
    highlight_years=[2024],
    show_current_day=True
)
```

---

## 3. Data Flow Diagram

```
User Clicks Station on Map
         │
         ▼
    app.py: update_plots_output()
         │
         ├──► data_manager.get_streamflow_data(site_id)
         │    └──► Returns: pd.DataFrame (daily discharge data)
         │
         ├──► data_manager.get_realtime_data(site_id)
         │    └──► Returns: pd.DataFrame (15-min discharge data)
         │
         └──► viz_manager.create_streamflow_plot(
                  site_id, streamflow_data,
                  plot_type='water_year',
                  highlight_years=[2024, 2025]
              )
              │
              ├──► TRY: _create_integrated_plot()
              │    │
              │    ├──► StreamflowData(data=df, site_id=site_id)
              │    │    └──► Processes data, calculates statistics
              │    │
              │    └──► StreamflowVisualizer(sf_data)
              │         └──► create_stacked_line_plot()
              │              └──► Returns: go.Figure
              │
              └──► FALLBACK: _create_fallback_plot()
                   │
                   ├──► wy_handler.create_water_year_plot()
                   │    └──► Returns: go.Figure
                   │
                   └──► _add_realtime_overlay(fig, realtime_data)
                        └──► Returns: go.Figure (with red line)

Final go.Figure sent back to app.py → displayed in browser
```

---

## 4. Separation of Concerns Analysis

### ✅ **Good Separation:**

1. **Data fetching vs visualization are separated**
   - `data_manager` handles all database/API operations
   - `viz_manager` only creates plots from provided data

2. **Two plotting strategies provide redundancy**
   - If streamflow_analyzer fails, water_year_datetime works
   - Graceful degradation

3. **Utility libraries are reusable**
   - `streamflow_analyzer` is completely standalone
   - `water_year_datetime` is moderately reusable

### ⚠️ **Areas of Concern:**

1. **❌ DUPLICATION: Multiple water year plot implementations**
   - `streamflow_analyzer.py` has its own water year logic
   - `water_year_datetime.py` has different water year logic
   - `viz_manager.py` has fallback logic
   - **Result:** Three places where water year plots are created!

2. **❌ COMPLEXITY: viz_manager tries two different approaches**
   - Creates `StreamflowData` + `StreamflowVisualizer` objects
   - Falls back to `water_year_datetime` if that fails
   - **Why?** Unclear when/why one would fail vs the other

3. **❌ INCONSISTENCY: Different plotting interfaces**
   - `streamflow_analyzer` uses: `create_stacked_line_plot(**config)`
   - `water_year_datetime` uses: `create_water_year_plot(data, col, years)`
   - **Result:** viz_manager has to translate between interfaces

4. **❌ UNCLEAR RESPONSIBILITIES:**
   - `streamflow_analyzer` can fetch its own data (using NWIS)
   - But dashboard already fetches data (using data_manager)
   - **Result:** Duplicate data-fetching code paths

5. **❌ REAL-TIME OVERLAY LOGIC in viz_manager**
   - Realtime overlay is added in `viz_manager`
   - Neither plotting library handles it
   - **Result:** viz_manager has visualization logic mixed with orchestration

---

## 5. Recommended Improvements

### 5.1 **Consolidate Water Year Logic** ⭐⭐⭐ (High Priority)

**Problem:** Three different implementations of water year plots.

**Solution:**
```python
# Choose ONE approach:
# Option A: Use streamflow_analyzer exclusively
# Option B: Use water_year_datetime exclusively
# Option C: Create new unified water_year_plotter.py

# Recommended: Option B (simpler, dashboard-specific)
class WaterYearPlotter:
    """Single place for all water year plotting logic."""
    
    def create_plot(self, data, site_id, highlight_years, 
                   show_percentiles, show_statistics,
                   realtime_data=None):
        """One method to rule them all."""
        # All logic in one place
        # Handles both daily and realtime data
        pass
```

**Benefits:**
- One place to maintain plot logic
- Consistent behavior across dashboard
- Easier to add features (only update one place)

---

### 5.2 **Simplify viz_manager Role** ⭐⭐ (Medium Priority)

**Problem:** viz_manager is doing too much (orchestration + visualization logic)

**Solution:**
```python
class VisualizationManager:
    """ONLY orchestrates, doesn't create plots."""
    
    def create_streamflow_plot(self, ...):
        # Just prepare data and call the right plotter
        plotter = get_water_year_plotter()
        return plotter.create_plot(data, realtime_data, **options)
    
    # No fallback logic
    # No real-time overlay logic (moved to plotter)
```

**Benefits:**
- Clear single responsibility
- Easier to test
- Less code duplication

---

### 5.3 **Decide on streamflow_analyzer's Role** ⭐ (Lower Priority)

**Problem:** Unclear when/why to use streamflow_analyzer vs water_year_datetime

**Solution - Option A: Remove streamflow_analyzer**
```python
# If dashboard-specific needs are different from library
# Just use water_year_datetime exclusively
# Remove streamflow_analyzer dependency
```

**Solution - Option B: Use streamflow_analyzer properly**
```python
# If keeping it, use it CORRECTLY:
# 1. Let it fetch its own data (don't pre-fetch)
# 2. Don't fall back to water_year_datetime
# 3. Extend it with dashboard-specific features
```

**Recommendation:** Option A (Remove it)
- Dashboard has specific needs (realtime overlay, specific styling)
- Maintaining two plotting systems is expensive
- water_year_datetime is simpler and more maintainable

---

### 5.4 **Extract Realtime Overlay to Utility** ⭐

**Problem:** Realtime overlay logic is buried in viz_manager

**Solution:**
```python
# Add to water_year_datetime.py
class WaterYearDateTime:
    def add_realtime_overlay(self, fig, realtime_data, site_id):
        """Add realtime data to any water year plot."""
        # Move logic from viz_manager here
        pass
```

**Benefits:**
- Keeps viz_manager clean
- Makes realtime overlay reusable
- Co-locates water year logic

---

## 6. Proposed New Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         app.py                               │
│                   (Dashboard Entry Point)                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├──► data_manager (USGSDataManager)
                   │    - Fetch daily data
                   │    - Fetch realtime data
                   │    - Database caching
                   │
                   └──► visualization_manager
                        │
                        └──► water_year_plotter (NEW - Unified)
                             ├── WaterYearDateTime (utilities)
                             ├── create_water_year_plot()
                             ├── create_annual_summary()
                             ├── create_flow_duration()
                             └── add_realtime_overlay()

[REMOVE: streamflow_analyzer.py - Too generic for our needs]
```

**Key Changes:**
1. **Single plotting library:** `water_year_plotter.py`
2. **viz_manager becomes simple orchestrator**
3. **No fallback logic** (one reliable path)
4. **Realtime overlay** integrated into plotter

---

## 7. Current State Summary

### What Works Well ✅

1. **Data fetching is separated** from visualization
2. **Realtime data overlay** works correctly
3. **Graceful degradation** with fallback plotting
4. **Water year calculations** are accurate

### What Needs Improvement ⚠️

1. **Three different water year plot implementations** 
2. **Unclear when streamflow_analyzer vs water_year_datetime** is used
3. **viz_manager has too many responsibilities**
4. **Duplicate data fetching capabilities** (streamflow_analyzer + data_manager)
5. **Inconsistent interfaces** between plotting libraries

### Impact on Maintainability 📊

**Current Complexity Score: 6/10**
- Multiple code paths make debugging difficult
- Adding features requires updating 2-3 places
- New developers face steep learning curve

**After Refactoring: 9/10**
- Single plotting path
- Clear responsibilities
- Easy to extend

---

## 8. Migration Path (If Refactoring)

**Phase 1: Consolidate Plotting** (1-2 days)
1. Create unified `water_year_plotter.py`
2. Move all plot logic from viz_manager
3. Integrate realtime overlay

**Phase 2: Update viz_manager** (1 day)
1. Simplify to orchestration only
2. Remove fallback logic
3. Update tests

**Phase 3: Remove streamflow_analyzer** (1 day)
1. Remove import
2. Remove try/except fallback
3. Clean up dependencies

**Phase 4: Testing** (1 day)
1. Test all plot types
2. Verify realtime overlay
3. Check error handling

**Total Effort: 4-5 days**

---

## 9. Conclusion

The current system **works** but has **technical debt** from evolving requirements:

**Original Design:**
- Use external library (streamflow_analyzer) for standard plots
- Fall back to custom code if library fails

**Reality:**
- Dashboard has specific needs (realtime overlay, custom styling)
- External library doesn't fit perfectly
- Maintaining both paths is expensive

**Recommendation:**
- **Keep:** `water_year_datetime.py` (useful utility)
- **Simplify:** `viz_manager.py` (just orchestration)
- **Remove:** `streamflow_analyzer.py` (doesn't fit dashboard needs)
- **Create:** Unified plotting module (consolidate all logic)

This would result in **cleaner code, easier maintenance, and better separation of concerns**.
