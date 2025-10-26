#!/usr/bin/env python3

"""
Test basemap configuration and token requirements.
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

from usgs_dashboard.components.map_component import MapComponent
from usgs_dashboard.data.data_manager import USGSDataManager
import plotly.graph_objects as go
import plotly.express as px

def test_simple_map_creation():
    """Test creating simple maps with different configurations."""
    print("🗺️ Testing Simple Map Creation")
    print("=" * 50)
    
    # Test 1: Simple plotly express map
    print("\n1. Testing px.scatter_map with OpenStreetMap...")
    try:
        import pandas as pd
        
        # Simple test data
        test_data = pd.DataFrame({
            'lat': [45.5152, 47.0379],
            'lon': [-122.6784, -122.9015], 
            'city': ['Portland', 'Olympia'],
            'size': [10, 8]
        })
        
        fig = px.scatter_map(
            test_data,
            lat="lat", 
            lon="lon",
            size="size",
            hover_name="city",
            zoom=6,
            map_style="open-street-map"
        )
        
        print("   ✅ px.scatter_map created successfully")
        print(f"   📊 Data points: {len(fig.data)}")
        print(f"   🗺️ Map style: {fig.layout.map.style}")
        
    except Exception as e:
        print(f"   ❌ px.scatter_map failed: {str(e)}")
    
    # Test 2: Plotly graph_objects map 
    print("\n2. Testing go.Scattermap...")
    try:
        fig2 = go.Figure(go.Scattermap(
            lat=[45.5152, 47.0379],
            lon=[-122.6784, -122.9015],
            mode='markers',
            marker=dict(size=10),
            text=['Portland', 'Olympia']
        ))
        
        fig2.update_layout(
            map=dict(
                style='open-street-map',
                center=dict(lat=46.2, lon=-122.8),
                zoom=6
            ),
            height=500
        )
        
        print("   ✅ go.Scattermap created successfully")
        print(f"   📊 Data points: {len(fig2.data)}")
        
    except Exception as e:
        print(f"   ❌ go.Scattermap failed: {str(e)}")
    
    # Test 3: Check for mapbox token
    print("\n3. Checking Mapbox configuration...")
    try:
        import plotly.io as pio
        
        # Check default config
        config = pio.kaleido.scope.default_config
        print(f"   📋 Plotly config exists: {config is not None}")
        
        # Check environment variables
        mapbox_token = os.environ.get('MAPBOX_ACCESS_TOKEN')
        print(f"   🔑 MAPBOX_ACCESS_TOKEN: {'Set' if mapbox_token else 'Not set'}")
        
        if mapbox_token:
            print(f"   🔑 Token length: {len(mapbox_token)} chars")
        
    except Exception as e:
        print(f"   ❌ Config check failed: {str(e)}")
    
    # Test 4: USGS National Map test
    print("\n4. Testing USGS National Map implementation...")
    try:
        data_manager = USGSDataManager()
        map_component = MapComponent()
        gauges_df = data_manager.get_filters_table()
        
        # Create USGS map
        fig3 = map_component.create_gauge_map(
            gauges_df,
            map_style="usgs-national"
        )
        
        print("   ✅ USGS National Map created")
        
        # Check layers
        if hasattr(fig3.layout, 'mapbox') and hasattr(fig3.layout.mapbox, 'layers'):
            layers = fig3.layout.mapbox.layers
            print(f"   🗺️ Custom layers: {len(layers)}")
            if layers:
                layer = layers[0]
                print(f"   📍 Layer source: {layer.source[:80]}...")
                print(f"   📍 Layer type: {layer.type}")
        
    except Exception as e:
        print(f"   ❌ USGS map test failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("🏁 Map creation testing complete")

if __name__ == "__main__":
    test_simple_map_creation()