"""
Download USGS Watershed Boundary Dataset (WBD) using state-specific downloads.
This is more reliable than downloading the entire national dataset.
"""

import requests
import zipfile
import io
import json
from pathlib import Path
import time

OUTPUT_DIR = Path("data/basemaps")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Download WBD for specific HUC2 regions
# Using state-specific downloads which are smaller and more reliable
HUC2_URLS = {
    "17": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/HU2/Shape/WBD_17_HU2_Shape.zip",
}

# For HUC4, we'll download by state (smaller files)
STATE_WBD_URLS = {
    "WA": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/State/Shape/WBD_WA_Shape.zip",
    "OR": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/State/Shape/WBD_OR_Shape.zip",
    "ID": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/State/Shape/WBD_ID_Shape.zip",
    "MT": "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/WBD/State/Shape/WBD_MT_Shape.zip",
}


def download_and_extract_shp_to_geojson(url, output_name, huc_level="HU2"):
    """
    Download shapefile ZIP, extract, and convert to GeoJSON.
    
    Parameters:
    -----------
    url : str
        URL to download
    output_name : str
        Output filename (without extension)
    huc_level : str
        HUC level to extract (HU2, HU4, HU8, etc.)
    """
    print(f"\n📥 Downloading {output_name}...")
    print(f"   URL: {url}")
    
    try:
        # Download with progress
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        print(f"   Size: {total_size / (1024*1024):.1f} MB")
        
        # Read into memory
        content = io.BytesIO()
        downloaded = 0
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"   Progress: {percent:.1f}%", end='\r')
        
        print(f"   Progress: 100.0%")
        content.seek(0)
        
        # Extract ZIP
        print("   📦 Extracting shapefile...")
        with zipfile.ZipFile(content) as zf:
            # Find the shapefile for the desired HUC level
            shp_files = [f for f in zf.namelist() if f.endswith('.shp') and huc_level in f.upper()]
            
            if not shp_files:
                print(f"   ⚠️  No {huc_level} shapefile found in ZIP")
                return False
            
            shp_file = shp_files[0]
            print(f"   Found: {shp_file}")
            
            # Extract to temp directory
            extract_dir = OUTPUT_DIR / "temp"
            extract_dir.mkdir(exist_ok=True)
            
            # Extract all related files (.shp, .shx, .dbf, .prj)
            base_name = shp_file.replace('.shp', '')
            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                try:
                    member = base_name + ext
                    zf.extract(member, extract_dir)
                except:
                    pass
            
            # Convert to GeoJSON using ogr2ogr if available
            shp_path = extract_dir / shp_file
            geojson_path = OUTPUT_DIR / f"{output_name}.geojson"
            
            import subprocess
            try:
                # Try using ogr2ogr for conversion
                subprocess.run([
                    'ogr2ogr',
                    '-f', 'GeoJSON',
                    '-t_srs', 'EPSG:4326',
                    '-simplify', '0.001',  # Simplify for web use
                    str(geojson_path),
                    str(shp_path)
                ], check=True, capture_output=True)
                
                print(f"   ✅ Created: {geojson_path}")
                
                # Clean up temp files
                import shutil
                shutil.rmtree(extract_dir)
                
                return True
                
            except (subprocess.CalledProcessError, FileNotFoundError):
                print("   ⚠️  ogr2ogr not found, trying geopandas...")
                
                # Fallback to geopandas
                try:
                    import geopandas as gpd
                    gdf = gpd.read_file(shp_path)
                    gdf = gdf.to_crs("EPSG:4326")
                    
                    # Simplify geometry
                    gdf['geometry'] = gdf['geometry'].simplify(0.001)
                    
                    # Save as GeoJSON
                    gdf.to_file(geojson_path, driver='GeoJSON')
                    
                    print(f"   ✅ Created: {geojson_path}")
                    
                    # Clean up
                    import shutil
                    shutil.rmtree(extract_dir)
                    
                    return True
                    
                except ImportError:
                    print("   ❌ Neither ogr2ogr nor geopandas available")
                    print("   Please install: pip install geopandas")
                    return False
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def main():
    """Download watershed boundaries."""
    print("="*80)
    print("USGS Watershed Boundary Dataset Downloader")
    print("="*80)
    
    # Download HUC2 for Pacific Northwest (Region 17)
    print("\n🗺️  Downloading HUC2 (Major Basins)...")
    for huc_code, url in HUC2_URLS.items():
        download_and_extract_shp_to_geojson(url, f"huc2_{huc_code}", "HU2")
        time.sleep(1)
    
    # Download HUC4 and HUC8 from state files
    print("\n🗺️  Downloading State WBD (includes HUC4 and HUC8)...")
    for state, url in STATE_WBD_URLS.items():
        print(f"\n{state}:")
        download_and_extract_shp_to_geojson(url, f"wbd_{state.lower()}_hu4", "HU4")
        time.sleep(1)
        download_and_extract_shp_to_geojson(url, f"wbd_{state.lower()}_hu8", "HU8")
        time.sleep(1)
    
    print("\n" + "="*80)
    print("✅ Download complete!")
    print("="*80)
    print("\nDownloaded files:")
    for f in sorted(OUTPUT_DIR.glob("*.geojson")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
