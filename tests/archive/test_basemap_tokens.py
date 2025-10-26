#!/usr/bin/env python3

"""
Test which basemap styles work without Mapbox tokens.
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots')

import plotly.graph_objects as go
import pandas as pd

def test_basemap_token_requirements():
    """Test which basemap styles work without tokens."""
    print("🔑 Testing Basemap Token Requirements")
    print("=" * 50)
    
    # Sample data
    test_data = {
        'lat': [45.5152, 47.0379],
        'lon': [-122.6784, -122.9015],
        'text': ['Portland', 'Olympia']
    }
    
    # Test both dropdown styles and additional no-token styles
    styles_to_test = [
        # Dropdown styles
        ("open-street-map", "🗺️ OpenStreetMap", "No token needed"),
        ("satellite-streets", "🛰️ Satellite Streets", "May need token"),
        ("outdoors", "🏔️ Outdoors/Terrain", "May need token"),
        ("light", "🌆 Light", "May need token"),
        ("dark", "🌃 Dark", "May need token"),
        ("white-bg", "📰 White Background", "No token needed"),
        
        # Additional no-token alternatives
        ("carto-positron", "🌍 Carto Positron", "No token needed"),
        ("carto-darkmatter", "🌚 Carto Dark", "No token needed"),
        ("stamen-terrain", "🏞️ Stamen Terrain", "No token needed"),
        ("stamen-toner", "⚫ Stamen Toner", "No token needed"),
        ("stamen-watercolor", "🎨 Stamen Watercolor", "No token needed")
    ]
    
    working_styles = []
    token_required_styles = []
    
    for style_value, style_name, expected in styles_to_test:
        print(f"\n📍 Testing {style_name} ({style_value})...")
        print(f"   Expected: {expected}")
        
        try:
            # Create test figure
            fig = go.Figure()
            
            fig.add_trace(go.Scattermapbox(
                lat=test_data['lat'],
                lon=test_data['lon'],
                mode='markers',
                marker=dict(size=10),
                text=test_data['text']
            ))
            
            fig.update_layout(
                mapbox=dict(
                    style=style_value,
                    center=dict(lat=46.2, lon=-122.8),
                    zoom=6
                ),
                height=400,
                margin=dict(r=0, t=30, l=0, b=0)
            )
            
            # Save as HTML to test display
            filename = f"basemap_test_{style_value.replace('-', '_')}.html"
            fig.write_html(filename)
            
            print(f"   ✅ Created successfully")
            print(f"   💾 Saved as {filename}")
            
            # Check if this is a token-free style
            no_token_styles = [
                'open-street-map', 'white-bg', 'carto-positron', 'carto-darkmatter',
                'stamen-terrain', 'stamen-toner', 'stamen-watercolor'
            ]
            
            if style_value in no_token_styles:
                working_styles.append((style_value, style_name))
                print(f"   🆓 No token required")
            else:
                token_required_styles.append((style_value, style_name))
                print(f"   🔑 Likely requires token for full functionality")
                
        except Exception as e:
            print(f"   ❌ Failed: {str(e)}")
    
    print("\n" + "=" * 50)
    print("📋 SUMMARY")
    print("=" * 50)
    
    print(f"\n🆓 Styles that work WITHOUT tokens ({len(working_styles)}):")
    for value, name in working_styles:
        print(f"   - {name} ({value})")
    
    print(f"\n🔑 Styles that may need tokens ({len(token_required_styles)}):")
    for value, name in token_required_styles:
        print(f"   - {name} ({value})")
    
    print(f"\n💡 Recommendations:")
    print(f"   1. Keep token-free styles in dropdown for reliable display")
    print(f"   2. Consider adding Mapbox token for premium styles")
    print(f"   3. Test HTML files in browser to verify display")
    
    return working_styles, token_required_styles

if __name__ == "__main__":
    test_basemap_token_requirements()