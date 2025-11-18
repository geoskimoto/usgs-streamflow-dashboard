# Watershed Boundary Dataset (WBD) Files

## Overview
Extracted from USGS WBD National Geodatabase (2.6 GB download)  
Generated: November 17, 2024  
Format: GeoJSON (EPSG:4326 / WGS84)

## Files Created

### National Boundaries (All US Watersheds)

| File | Size | Features | Description |
|------|------|----------|-------------|
| `huc2_national.geojson` | 1.2 MB | 22 | Major regional basins |
| `huc4_national.geojson` | 8.9 MB | 245 | Sub-regional watersheds |
| `huc8_national.geojson` | 44 MB | 2,456 | Sub-basin watersheds |

### Pacific Northwest Region (HUC 17)

| File | Size | Features | Description |
|------|------|----------|-------------|
| `huc2_pnw.geojson` | 71 KB | 1 | Columbia River Basin |
| `huc4_pnw.geojson` | 519 KB | 12 | Major PNW sub-regions |
| `huc8_pnw.geojson` | 3.3 MB | 229 | PNW sub-basins |

## Hydrologic Unit Codes (HUC)

### HUC2 - Regional Basins (22 total)
Major drainage regions across the United States:
- 01: New England Region
- 02: Mid-Atlantic Region
- 03: South Atlantic-Gulf Region
- ...
- **17: Pacific Northwest Region** (Columbia River Basin) ⭐
- 18: California Region
- 19: Great Basin Region
- 20: Hawaii Region
- 21: Caribbean Region
- 22: Alaska Region

### HUC4 - Sub-Regional Watersheds (245 total)
Pacific Northwest HUC4 sub-regions (12):
- 1701: Kootenai-Pend Oreille-Spokane
- 1702: Upper Columbia
- 1703: Yakima
- 1704: Upper Snake
- 1705: Middle Snake
- 1706: Lower Snake
- 1707: Middle Columbia
- 1708: John Day
- 1709: Deschutes
- 1710: Umatilla-Walla Walla-Willow
- 1711: Lower Columbia
- 1712: Oregon-Washington Coastal

### HUC8 - Sub-Basin Watersheds (2,456 total)
229 sub-basins within the Pacific Northwest region.

## Data Simplification

Boundaries were simplified for web use:
- **HUC2**: 0.005 degrees (~500m tolerance)
- **HUC4**: 0.002 degrees (~200m tolerance)  
- **HUC8**: 0.001 degrees (~100m tolerance)

This reduces file sizes while maintaining visual accuracy for web maps.

## Usage

These GeoJSON files can be directly loaded into:
- **Plotly/Mapbox** - `fig.add_trace(go.Scattermapbox(...))`
- **Leaflet** - `L.geoJSON(data)`
- **D3.js** - `d3.json(url).then(data => ...)`

## Next Steps

1. Integrate boundaries into the map visualization
2. Create hierarchical toggles (HUC2 → HUC4 → HUC8)
3. Default visibility: Pacific Northwest basins
4. Color-code boundaries by region
5. Add hover tooltips showing basin names and HUC codes

## Data Source

**USGS Watershed Boundary Dataset (WBD)**
- Downloaded: January 7, 2025
- Source: https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/National/GDB/WBD_National_GDB.zip
- Official USGS data with no restrictions on use

## Station Coverage

Current dashboard has **1,506 USGS stream gauge stations** in the database, with focus on:
- **563 stations** in the Pacific Northwest (HUC 17)
- Columbia River Basin and tributaries
- Real-time and daily discharge data
