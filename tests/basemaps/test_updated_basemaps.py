#!/usr/bin/env python3

"""
Test the updated basemap functionality with go.Scattermapbox approach.
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

from usgs_dashboard.data.data_manager import USGSDataManager
from usgs_dashboard.components.map_component import MapComponent
import pandas as pd

def test_updated_basemaps():
    """Test the updated basemap functionality."""
    print("🗺️ Testing Updated Basemap Functionality")
    print("=" * 50)
    
    try:
        # Initialize components
        print("1. Initializing components...")
        data_manager = USGSDataManager()
        map_component = MapComponent()
        print("   ✅ Components initialized")
        
        # Get sample data
        print("\n2. Getting sample data...")
        gauges_df = data_manager.get_filters_table()
        print(f"   ✅ Got {len(gauges_df)} gauges")
        
        # Test different basemap styles with new implementation
        basemap_styles = [
            ("open-street-map", "Standard OpenStreetMap"),
            ("usgs-national", "USGS National Map"),
            ("carto-positron", "Carto Positron"),
            ("satellite-streets", "Satellite Streets"),
            ("white-bg", "White Background")
        ]
        
        for style, description in basemap_styles:
            print(f"\n3. Testing {description} ({style})...")
            
            try:
                fig = map_component.create_gauge_map(
                    gauges_df=gauges_df,
                    map_style=style
                )
                
                if fig is None:
                    print(f"   ❌ {style}: Figure is None")
                    continue
                
                # Check figure properties
                layout = fig.layout
                if not hasattr(layout, 'mapbox'):
                    print(f"   ❌ {style}: No mapbox configuration")
                    continue
                
                mapbox = layout.mapbox
                print(f"   🗺️ Mapbox style: {getattr(mapbox, 'style', 'Not set')}")
                
                # Check for traces
                print(f"   📊 Number of traces: {len(fig.data)}")
                
                if fig.data:
                    trace = fig.data[0]
                    print(f"   📊 Trace type: {type(trace).__name__}")
                    if hasattr(trace, 'lat') and trace.lat is not None:
                        print(f"   📍 Data points: {len(trace.lat)}")
                
                # Check for custom layers (USGS)
                if hasattr(mapbox, 'layers') and mapbox.layers:
                    print(f"   🏔️ Custom layers: {len(mapbox.layers)}")
                    layer = mapbox.layers[0]
                    print(f"   📡 Layer type: {layer.get('sourcetype', 'unknown')}")
                    if 'source' in layer and layer['source']:
                        source_url = layer['source'][0] if isinstance(layer['source'], list) else layer['source']
                        print(f"   🔗 Source: {source_url[:60]}...")
                else:
                    print("   🗺️ No custom layers (using standard basemap)")
                
                # Check center and zoom
                center = getattr(mapbox, 'center', {})
                zoom = getattr(mapbox, 'zoom', 'not set')
                if hasattr(center, 'lat'):
                    print(f"   📍 Center: lat={center.lat}, lon={center.lon}")
                else:
                    print(f"   📍 Center: {center}")
                print(f"   🔍 Zoom: {zoom}")
                
                print(f"   ✅ {style}: Successfully created and configured")
                
            except Exception as e:
                print(f"   ❌ {style}: Error - {str(e)}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 50)
        print("🏁 Updated basemap testing complete!")
        
        # Test empty map
        print("\n4. Testing empty map with USGS style...")
        try:
            empty_fig = map_component._create_empty_map("usgs-national")
            if empty_fig and hasattr(empty_fig.layout, 'mapbox'):
                layers = getattr(empty_fig.layout.mapbox, 'layers', [])
                print(f"   ✅ Empty USGS map created with {len(layers)} layers")
            else:
                print("   ❌ Empty USGS map creation failed")
        except Exception as e:
            print(f"   ❌ Empty map error: {str(e)}")
        
    except Exception as e:
        print(f"❌ Critical error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_updated_basemaps()