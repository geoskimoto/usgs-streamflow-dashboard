#!/usr/bin/env python3

"""
Test map display with and without mapbox token configuration.
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

import plotly.express as px
import pandas as pd

def test_map_display():
    """Test if maps display properly in different configurations."""
    print("🖥️ Testing Map Display Configurations")
    print("=" * 50)
    
    # Test data
    test_data = pd.DataFrame({
        'lat': [45.5152, 47.0379, 46.8721],
        'lon': [-122.6784, -122.9015, -121.1583], 
        'city': ['Portland', 'Olympia', 'Yakima'],
        'size': [15, 10, 8]
    })
    
    # Test different map styles
    map_styles = [
        "open-street-map",      # Should work without token
        "white-bg",             # Should work without token
        "carto-positron",       # Should work without token
        "satellite-streets",    # Might need token
        "outdoors"              # Might need token
    ]
    
    for style in map_styles:
        print(f"\n📍 Testing style: {style}")
        
        try:
            fig = px.scatter_map(
                test_data,
                lat="lat", 
                lon="lon",
                size="size",
                hover_name="city",
                zoom=6,
                map_style=style
            )
            
            print(f"   ✅ Created successfully")
            
            # Save as HTML to test display
            filename = f"test_map_{style.replace('-', '_')}.html"
            fig.write_html(filename)
            print(f"   💾 Saved as {filename}")
            
            # Check figure properties
            layout = fig.layout
            if hasattr(layout, 'map'):
                print(f"   🗺️ Map style set: {layout.map.style}")
            elif hasattr(layout, 'mapbox'):
                print(f"   🗺️ Mapbox style set: {layout.mapbox.style}")
            
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
    
    # Test setting a mapbox token (using a placeholder)
    print(f"\n🔑 Testing with Mapbox token configuration...")
    
    try:
        # Set a placeholder token to see if it changes behavior
        os.environ['MAPBOX_ACCESS_TOKEN'] = 'pk.test_token_placeholder'
        
        fig = px.scatter_map(
            test_data,
            lat="lat", 
            lon="lon",
            size="size",
            hover_name="city",
            zoom=6,
            map_style="satellite-streets"
        )
        
        fig.write_html("test_map_with_token.html")
        print("   💾 Map with token configuration saved as test_map_with_token.html")
        
        # Clean up
        del os.environ['MAPBOX_ACCESS_TOKEN']
        
    except Exception as e:
        print(f"   ❌ Token test failed: {str(e)}")
    
    print(f"\n📋 HTML files created for visual inspection:")
    import glob
    html_files = glob.glob("test_map_*.html")
    for file in html_files:
        print(f"   - {file}")
    
    print("\n💡 To test display:")
    print("   1. Open the HTML files in a web browser")
    print("   2. Check if maps render with tiles")
    print("   3. Check browser console for any errors")
    
    print("\n" + "=" * 50)
    print("🏁 Map display testing complete")

if __name__ == "__main__":
    test_map_display()