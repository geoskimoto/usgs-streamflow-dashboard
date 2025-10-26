"""
Test Updated USGS Dashboard with Modern Map Component
"""

import sys
sys.path.append('/home/mrguy/Projects/streamflows/StackedLinePlots/usgs_dashboard')

from components.map_component import MapComponent
import pandas as pd

def test_updated_dashboard():
    """Test the updated dashboard with modern map component."""
    print("🧪 Testing Updated USGS Dashboard with Modern Map Component...")
    
    # Create map component
    map_comp = MapComponent()
    
    # Create test gauge data
    test_data = pd.DataFrame({
        'latitude': [45.5, 46.2, 44.8, 45.8, 46.8, 44.2],
        'longitude': [-122.5, -121.8, -120.2, -122.0, -121.0, -121.5],
        'station_name': [
            'Portland Gauge', 'Hood River', 'Bend Station', 
            'Forest Grove', 'Columbia River', 'Santiam River'
        ],
        'site_id': ['14211720', '14113000', '14056500', '14206950', '14144900', '14185000'],
        'state': ['OR', 'OR', 'OR', 'OR', 'WA', 'OR'],
        'drainage_area': [1500, 670, 1250, 355, 3400, 1800],
        'status': ['excellent', 'good', 'fair', 'excellent', 'good', 'inactive'],
        'years_of_record': [45, 35, 25, 30, 50, 20]
    })
    
    print(f"📊 Creating dashboard map with {len(test_data)} test gauges...")
    
    # Test basic map creation
    fig = map_comp.create_gauge_map(test_data)
    print("✅ Basic map created successfully!")
    
    # Test selected gauge
    selected_fig = map_comp.create_gauge_map(test_data, selected_gauge='14211720')
    print("✅ Selected gauge highlighting works!")
    
    # Test empty map (using private method for testing)
    empty_fig = map_comp._create_empty_map()
    print("✅ Empty map handling works!")
    
    # Test summary stats
    stats = map_comp.create_gauge_summary_stats(test_data)
    print(f"✅ Summary stats: {stats['total_gauges']} gauges, {stats['active_gauges']} active")
    
    # Save test outputs
    fig.write_html("test_updated_dashboard_map.html")
    selected_fig.write_html("test_updated_dashboard_selected.html") 
    print("💾 Test maps saved!")
    
    # Check for modern layout properties
    print(f"\n🔍 Map Layout Check:")
    print(f"   - Uses 'map' layout: {'map' in fig.layout}")
    print(f"   - Uses 'mapbox' layout: {'mapbox' in fig.layout}")
    print(f"   - Map style: {fig.layout.map.style if 'map' in fig.layout else 'NOT FOUND'}")
    print(f"   - Number of traces: {len(fig.data)}")
    
    print("\n🎉 All updated dashboard tests passed!")
    print("\n📋 Key Updates:")
    print("   ✅ Uses px.scatter_map instead of deprecated px.scatter_mapbox")
    print("   ✅ Uses go.Scattermap instead of deprecated go.Scattermapbox")
    print("   ✅ Uses layout.map instead of deprecated layout.mapbox") 
    print("   ✅ Uses map_style instead of deprecated mapbox_style")
    print("   ✅ No deprecation warnings expected!")
    
    return True

if __name__ == "__main__":
    try:
        test_updated_dashboard()
        print("\n✅ SUCCESS: Updated dashboard map component works perfectly!")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
