# MapLibre Basemap Compatibility Research

**Date:** 2026-05-08  
**Context:** Evaluated three basemaps from the madewithmaplibre.com gallery as candidates for addition to the dashboard map style dropdown.

---

## Current Architecture Constraint

The dashboard map uses `go.Scattermap` with `style="white-bg"` and custom raster tile layers (defined in `_TILE_CONFIGS` in `map_component.py`). This approach supports **raster XYZ tile URLs only** — a single URL template with `{z}/{x}/{y}` or `{z}/{y}/{x}` tokens. It cannot consume:

- MapLibre GL v8 vector style JSON URLs
- Multi-source composited styles (hillshade DEM + vector features)
- Authenticated tile services without URL-embedded tokens

---

## Basemap Assessments

### ✅ Esri World Imagery (Satellite)
**Status: Implemented (2026-05-08)**

A standard raster XYZ tile service from Esri. No API key required.

| | |
|---|---|
| Tile URL | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` |
| URL pattern | `{z}/{y}/{x}` (note: y before x, same as USGS National Map) |
| Auth required | No |
| Compatibility | Full — drop-in raster tile |
| Attribution | Esri, Maxar, Earthstar Geographics, and the GIS User Community |

---

### ⚠️ Stamen Terrain (via Stadia Maps)
**Status: Possible with API key**

Stamen tiles were acquired by Stadia Maps. A raster tile version exists and would be compatible with the current architecture, but Stadia Maps requires an API key (free tier available for non-commercial/low-traffic use).

| | |
|---|---|
| Raster tile URL | `https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png?api_key={key}` |
| Auth required | Yes — Stadia Maps API key |
| Compatibility | Compatible once key is added as env var (`STADIA_API_KEY`) |
| Cost | Free tier available; see stadiamaps.com for limits |
| Notes | The current "Stamen Terrain" dropdown option points to a Carto Voyager tile URL as a placeholder — not actual Stamen Terrain. Implementing this properly would also fix that. |

**Implementation path:**
1. Register at stadiamaps.com, obtain API key
2. Add `STADIA_API_KEY` to `.env` and `.env.example`
3. Add entry to `_TILE_CONFIGS` with key injected into URL
4. Update both dropdown instances in `app.py`

---

### ❌ Terrarium Elevation
**Status: Not compatible with current architecture**

"Terrarium Elevation" as presented by MapLibre is a fully composited vector rendering pipeline, not a single raster tile source. The MapLibre GL v8 style JSON at `https://tiles.stadiamaps.com/styles/stamen_terrain.json` reveals four separate sources:

| Source | Type | Purpose |
|---|---|---|
| `terrarium` | Raster DEM | Elevation data for hillshade (AWS Terrarium format) |
| `stamen-omt` | Vector tiles | Roads, water, boundaries, labels |
| `global_landcover_v1` | Vector tiles | Land classification |
| `stamen_null` | Vector tiles | Reference data |

MapLibre GL JS composites these in the browser at render time. There is no pre-rendered raster tile equivalent — the hillshade is computed client-side from the elevation DEM.

**Options to implement this in the future:**

**Option A — MapTiler / Stadia raster terrain background**  
Use a pre-rendered terrain background tile (without dynamic hillshade):
- `https://tiles.stadiamaps.com/tiles/stamen_terrain_background/{z}/{x}/{y}.png` (Stadia key required)
- This loses the dynamic hillshade but is raster-compatible.

**Option B — Embed a MapLibre GL JS map**  
Replace `go.Scattermap` with a native MapLibre GL JS map rendered in a `dcc.Store` + `html.Iframe` or via a custom Dash component. The station scatter layer would be drawn as a GeoJSON source on the MapLibre map. This is the only path to true vector + hillshade terrain rendering.
- **Effort:** Large — requires a custom Dash component or iframe bridge, and rewiring all map callbacks.
- **Benefit:** Full access to any MapLibre GL style, including Terrarium Elevation, real-time hillshade, and vector layer control.

**Option C — OpenTopoMap (current-architecture substitute)**  
A topo/terrain-aesthetic raster tile that works as a drop-in today:
- URL: `https://tile.opentopomap.org/{z}/{x}/{y}.png`
- Attribution: `© OpenTopoMap contributors, CC-BY-SA`
- No API key; community-run service (rate limits apply)
- Visual character: contour lines + terrain coloring, no dynamic hillshade

---

## Summary

| Basemap | Compatible Now | Key Required | Path Forward |
|---|---|---|---|
| Esri Satellite | ✅ Done | No | — |
| Stamen Terrain | ✅ With key | Yes (Stadia) | Add `STADIA_API_KEY` env var |
| Terrarium Elevation | ❌ | Yes (Stadia) | Option A (approx), or Option B (full fidelity) |
| OpenTopoMap (substitute) | ✅ Drop-in | No | Add to `_TILE_CONFIGS` if desired |
