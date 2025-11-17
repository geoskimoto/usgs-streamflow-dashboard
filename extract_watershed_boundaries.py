"""
Extract watershed boundaries from USGS WBD National Geodatabase.

This script extracts HUC2, HUC4, and HUC8 boundaries from the national
geodatabase and converts them to simplified GeoJSON files for web use.
"""

import subprocess
import json
from pathlib import Path
import shutil

# Paths
BASEMAPS_DIR = Path("data/basemaps")
GDB_ZIP = BASEMAPS_DIR / "WBD_National_GDB.zip"
EXTRACT_DIR = BASEMAPS_DIR / "wbd_extract"
GDB_DIR = EXTRACT_DIR / "WBD_National_GDB.gdb"

# HUC levels to extract
HUC_LEVELS = {
    "WBDHU2": "huc2_national",
    "WBDHU4": "huc4_national", 
    "WBDHU8": "huc8_national"
}


def check_gdal():
    """Check if GDAL/OGR tools are available."""
    try:
        result = subprocess.run(['ogrinfo', '--version'], 
                              capture_output=True, text=True, timeout=5)
        print(f"✓ GDAL/OGR found: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✗ GDAL/OGR not found")
        print("  Please install: sudo apt-get install gdal-bin")
        return False


def extract_gdb():
    """Extract the geodatabase from ZIP."""
    print("\n📦 Extracting geodatabase...")
    print(f"   Source: {GDB_ZIP}")
    print(f"   Target: {EXTRACT_DIR}")
    
    if GDB_DIR.exists():
        print("   ✓ Already extracted")
        return True
    
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        subprocess.run([
            'unzip', '-q', str(GDB_ZIP), '-d', str(EXTRACT_DIR)
        ], check=True, timeout=300)
        print("   ✓ Extraction complete")
        return True
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def list_layers():
    """List all layers in the geodatabase."""
    print("\n📋 Listing geodatabase layers...")
    try:
        result = subprocess.run([
            'ogrinfo', '-so', str(GDB_DIR)
        ], capture_output=True, text=True, check=True, timeout=30)
        
        layers = []
        for line in result.stdout.split('\n'):
            if ':' in line and 'Layer name' not in line:
                parts = line.split(':')
                if len(parts) >= 2:
                    layer_name = parts[1].strip().split('(')[0].strip()
                    if layer_name and 'WBD' in layer_name:
                        layers.append(layer_name)
        
        print(f"   Found {len(layers)} WBD layers:")
        for layer in sorted(layers):
            print(f"     - {layer}")
        
        return layers
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return []


def convert_layer_to_geojson(layer_name, output_name, simplify=0.001):
    """
    Convert a geodatabase layer to simplified GeoJSON.
    
    Parameters:
    -----------
    layer_name : str
        Name of the layer in the geodatabase
    output_name : str
        Output filename (without .geojson extension)
    simplify : float
        Simplification tolerance in degrees (0.001 ≈ 100m)
    """
    output_path = BASEMAPS_DIR / f"{output_name}.geojson"
    
    print(f"\n🗺️  Converting {layer_name}...")
    print(f"   Output: {output_path.name}")
    print(f"   Simplification: {simplify} degrees")
    
    try:
        # Convert to GeoJSON with simplification
        subprocess.run([
            'ogr2ogr',
            '-f', 'GeoJSON',
            '-t_srs', 'EPSG:4326',  # WGS84 lat/lon
            '-simplify', str(simplify),  # Simplify for web
            '-lco', 'COORDINATE_PRECISION=5',  # 5 decimal places
            str(output_path),
            str(GDB_DIR),
            layer_name
        ], check=True, capture_output=True, timeout=600)
        
        # Check file size
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"   ✓ Created: {output_path.name} ({size_mb:.2f} MB)")
        
        # Get feature count
        with open(output_path) as f:
            data = json.load(f)
            feature_count = len(data.get('features', []))
            print(f"   ✓ Features: {feature_count}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Conversion failed: {e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def cleanup_temp_files():
    """Remove temporary extraction directory."""
    print("\n🧹 Cleaning up temporary files...")
    try:
        if EXTRACT_DIR.exists():
            shutil.rmtree(EXTRACT_DIR)
            print("   ✓ Temp files removed")
    except Exception as e:
        print(f"   ⚠️  Could not remove temp files: {e}")


def main():
    """Main extraction workflow."""
    print("="*80)
    print("USGS WBD National Geodatabase Extractor")
    print("="*80)
    
    # Check prerequisites
    if not check_gdal():
        print("\n❌ GDAL tools required. Please install and try again.")
        return
    
    if not GDB_ZIP.exists():
        print(f"\n❌ Geodatabase not found: {GDB_ZIP}")
        return
    
    print(f"\n📁 Geodatabase: {GDB_ZIP}")
    print(f"   Size: {GDB_ZIP.stat().st_size / (1024**3):.2f} GB")
    
    # Extract geodatabase
    if not extract_gdb():
        return
    
    # List layers to verify
    layers = list_layers()
    
    # Convert each HUC level
    print("\n" + "="*80)
    print("Converting layers to GeoJSON...")
    print("="*80)
    
    for layer_name, output_name in HUC_LEVELS.items():
        if layer_name in layers:
            # Adjust simplification based on HUC level
            # Larger HUCs can be simplified more
            simplify = {
                "WBDHU2": 0.005,  # ~500m
                "WBDHU4": 0.002,  # ~200m
                "WBDHU8": 0.001   # ~100m
            }.get(layer_name, 0.001)
            
            convert_layer_to_geojson(layer_name, output_name, simplify)
        else:
            print(f"\n⚠️  Layer not found: {layer_name}")
    
    # Optional: Create regional subsets
    print("\n" + "="*80)
    print("Creating regional subsets...")
    print("="*80)
    
    # Extract Pacific Northwest region (HUC 17)
    print("\n🌲 Extracting Pacific Northwest (HUC 17)...")
    for layer in ["WBDHU2", "WBDHU4", "WBDHU8"]:
        if layer in layers:
            huc_field = layer.replace("WBD", "")
            output_name = f"{layer.lower()}_pnw"
            output_path = BASEMAPS_DIR / f"{output_name}.geojson"
            
            try:
                subprocess.run([
                    'ogr2ogr',
                    '-f', 'GeoJSON',
                    '-t_srs', 'EPSG:4326',
                    '-simplify', '0.001',
                    '-where', f"{huc_field} LIKE '17%'",
                    '-lco', 'COORDINATE_PRECISION=5',
                    str(output_path),
                    str(GDB_DIR),
                    layer
                ], check=True, capture_output=True, timeout=300)
                
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"   ✓ {output_name}.geojson ({size_mb:.2f} MB)")
            except:
                pass
    
    # Cleanup
    cleanup_temp_files()
    
    # Summary
    print("\n" + "="*80)
    print("✅ Extraction Complete!")
    print("="*80)
    print("\nGenerated files:")
    for f in sorted(BASEMAPS_DIR.glob("*.geojson")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name} ({size_mb:.2f} MB)")
    
    print(f"\n📁 Output directory: {BASEMAPS_DIR}")


if __name__ == "__main__":
    main()
