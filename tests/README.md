# Tests Directory

This directory contains organized test files for the USGS Streamflow Dashboard project.

## Directory Structure

### `/features/`
Contains tests for major dashboard features and enhancements:
- `test_cache_fix.py` - Tests for the data corruption fix (datetime preservation in caching)
- `test_enhanced_water_year.py` - Tests for enhanced water year plotting with statistics and current day markers
- `test_comprehensive_features.py` - Integration tests for all major features

### `/basemaps/`
Contains tests for map and basemap functionality:
- `test_usgs_basemap.py` - Tests for USGS National Map custom tile integration
- `test_dashboard_basemaps.py` - Tests for all dashboard basemap options
- `test_updated_basemaps.py` - Tests for updated basemap implementation with go.Scattermapbox

### `/archive/`
Contains older test files that may be useful for reference but are not actively maintained:
- Various test files from development iterations
- Legacy test implementations
- Experimental feature tests

## Running Tests

To run feature tests:
```bash
cd tests/features
python test_comprehensive_features.py  # Runs all major feature tests
```

To run basemap tests:
```bash
cd tests/basemaps
python test_dashboard_basemaps.py  # Tests all basemap options
```

## Key Test Results

All tests in `/features/` and `/basemaps/` should pass, confirming:
- ✅ Data corruption fix working
- ✅ Enhanced water year plots with statistics
- ✅ USGS National Map integration
- ✅ All basemap styles functional without tokens
- ✅ Professional UI enhancements