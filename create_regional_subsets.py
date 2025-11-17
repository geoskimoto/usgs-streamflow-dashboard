"""
Create regional subsets from national watershed boundary GeoJSON files.
"""

import json
from pathlib import Path

BASEMAPS_DIR = Path("data/basemaps")

# Regional definitions (HUC2 codes)
REGIONS = {
    "pnw": {
        "name": "Pacific Northwest",
        "huc2_codes": ["17"],
        "description": "Columbia River Basin and Pacific Northwest"
    },
    "southwest": {
        "name": "Southwest",
        "huc2_codes": ["14", "15"],
        "description": "Colorado River and Great Basin"
    },
    "california": {
        "name": "California",
        "huc2_codes": ["18"],
        "description": "California region"
    }
}


def create_regional_subset(input_file, output_file, huc_codes, huc_level):
    """
    Create a regional subset by filtering features by HUC code.
    
    Parameters:
    -----------
    input_file : Path
        Input GeoJSON file
    output_file : Path
        Output GeoJSON file
    huc_codes : list
        List of HUC codes to include (e.g., ["17"] for PNW)
    huc_level : str
        HUC level field name (e.g., "HUC2", "HUC4", "HUC8")
    """
    print(f"\n🗺️  Creating {output_file.name}...")
    
    with open(input_file) as f:
        data = json.load(f)
    
    # Filter features
    filtered_features = []
    for feature in data.get('features', []):
        huc_value = feature['properties'].get(huc_level, '')
        
        # Check if feature's HUC code starts with any of our target codes
        if any(huc_value.startswith(code) for code in huc_codes):
            filtered_features.append(feature)
    
    # Create new GeoJSON
    subset = {
        "type": "FeatureCollection",
        "features": filtered_features
    }
    
    # Write output
    with open(output_file, 'w') as f:
        json.dump(subset, f)
    
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"   ✓ Created {output_file.name}: {len(filtered_features)} features ({size_mb:.2f} MB)")
    
    return len(filtered_features)


def main():
    """Create regional subsets for each region and HUC level."""
    print("="*80)
    print("Creating Regional Watershed Boundary Subsets")
    print("="*80)
    
    # HUC levels (field names are lowercase in the GeoJSON)
    huc_levels = [
        ("huc2_national.geojson", "huc2", "huc2"),
        ("huc4_national.geojson", "huc4", "huc4"),
        ("huc8_national.geojson", "huc8", "huc8")
    ]
    
    # Create subsets for Pacific Northwest (primary focus)
    region_key = "pnw"
    region = REGIONS[region_key]
    
    print(f"\n🌲 {region['name']} (HUC codes: {', '.join(region['huc2_codes'])})")
    print(f"   {region['description']}")
    
    for input_filename, huc_field, huc_prefix in huc_levels:
        input_file = BASEMAPS_DIR / input_filename
        output_file = BASEMAPS_DIR / f"{huc_prefix}_{region_key}.geojson"
        
        if input_file.exists():
            create_regional_subset(
                input_file, 
                output_file, 
                region['huc2_codes'],
                huc_field
            )
        else:
            print(f"   ⚠️  Input file not found: {input_filename}")
    
    # Summary
    print("\n" + "="*80)
    print("✅ Regional Subsets Created!")
    print("="*80)
    print("\nPacific Northwest files:")
    for f in sorted(BASEMAPS_DIR.glob("*_pnw.geojson")):
        size_mb = f.stat().st_size / (1024 * 1024)
        with open(f) as file:
            data = json.load(file)
            count = len(data.get('features', []))
        print(f"  - {f.name}: {count} features ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
