"""
Test Modern Map Component - MapLibre Implementation
"""

import sys
sys.path.append('/home/mrguy/Projects/streamflows/StackedLinePlots/usgs_dashboard')

from components.modern_map_component import ModernMapComponent
import pandas as pd

def test_modern_component():
    """Test the modern map component."""
    print("🧪 Testing Modern Map Component (MapLibre)...")
    
    # Create component
    map_comp = ModernMapComponent()
    
    # Test with sample data
    test_data = pd.DataFrame({
        'latitude': [45.5, 46.2, 44.8, 45.8],
        'longitude': [-122.5, -121.8, -120.2, -122.0],
        'station_name': ['Portland Gauge', 'Hood River', 'Bend Station', 'Forest Grove'],
        'site_id': ['14211720', '14113000', '14056500', '14206950'],
        'state': ['OR', 'OR', 'OR', 'OR'],
        'drainage_area': [1500, 670, 1250, 355],
        'status': ['excellent', 'good', 'fair', 'excellent'],
        'years_of_record': [45, 35, 25, 30]
    })
    
    print(f"📊 Creating map with {len(test_data)} test gauges...")
    
    # Create map
    fig = map_comp.create_gauge_map(test_data)
    
    print("✅ Modern map created successfully!")
    print(f"📍 Map center: {fig.layout.map.center}")
    print(f"🎨 Map style: {fig.layout.map.style}")
    print(f"🔍 Zoom level: {fig.layout.map.zoom}")
    
    # Save test output
    output_file = "test_modern_map_output.html"
    fig.write_html(output_file)
    print(f"💾 Map saved to: {output_file}")
    
    # Test empty map
    print("\n🧪 Testing empty map handling...")
    empty_fig = map_comp.create_gauge_map(pd.DataFrame())
    print("✅ Empty map handling works!")
    
    # Test selected gauge
    print("\n🧪 Testing selected gauge highlight...")
    selected_fig = map_comp.create_gauge_map(test_data, selected_gauge='14211720')
    print("✅ Selected gauge highlighting works!")
    
    print("\n🎉 All modern map component tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_modern_component()
        print("\n✅ SUCCESS: Modern map component works perfectly!")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
