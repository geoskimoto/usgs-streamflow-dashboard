"""
Test Active Sites with New 30-Day Definition
"""

import sys
sys.path.append('/home/mrguy/Projects/streamflows/StackedLinePlots/usgs_dashboard')

from data.data_manager import get_data_manager

def test_new_active_definition():
    """Test the new 30-day active definition."""
    print("🧪 Testing New Active Definition (30 days)...")
    
    # Clear cache and refresh to apply new active definition
    dm = get_data_manager()
    print("🗑️ Clearing cache to apply new 30-day active definition...")
    dm.clear_cache()
    
    print("📊 Refreshing data with new 30-day active logic...")
    # Note: This will only check the first 50 sites for performance
    gauges = dm.load_regional_gauges(refresh=True)
    
    # Check activity distribution
    active_count = (gauges['is_active'] == True).sum()
    inactive_count = (gauges['is_active'] == False).sum()
    
    print(f"✅ Results with 30-day active definition:")
    print(f"   - Active sites (data within 30 days): {active_count}")
    print(f"   - Inactive sites: {inactive_count}")
    print(f"   - Total: {len(gauges)}")
    print(f"   - Active percentage: {100 * active_count / len(gauges):.1f}%")
    
    if active_count > 1:
        print("🎉 More sites should now be marked as active!")
        
        # Show some active sites
        active_sites = gauges[gauges['is_active'] == True].head(5)
        print(f"\n🔍 Sample active sites:")
        for _, site in active_sites.iterrows():
            print(f"   - {site['site_id']}: {site['station_name']} ({site['state']})")
    else:
        print("⚠️ Still very few active sites - may need to check more than first 50")
        print("💡 Consider increasing the sample size or using heuristics")

if __name__ == "__main__":
    test_new_active_definition()
    print("\n🎉 Active definition test complete!")
