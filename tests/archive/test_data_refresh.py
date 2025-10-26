"""
Test Data Refresh - Force rebuild cache with correct schema
"""

import sys
sys.path.append('/home/mrguy/Projects/streamflows/StackedLinePlots/usgs_dashboard')

from data.data_manager import get_data_manager
import pandas as pd

def test_data_refresh():
    """Test refreshing data to fix the schema issues."""
    print("🔄 Testing Data Refresh to Fix Schema...")
    
    # Get data manager
    data_manager = get_data_manager()
    
    # Clear cache first
    print("🗑️ Clearing existing cache...")
    data_manager.clear_cache()
    
    # Force refresh to rebuild with correct schema
    print("📊 Force refreshing gauge data (this may take a moment)...")
    try:
        # This should force a fresh fetch and rebuild the cache with all columns
        gauges_df = data_manager.load_regional_gauges(refresh=True)
        
        print(f"✅ Successfully loaded {len(gauges_df)} gauges")
        
        # Check the columns now
        print(f"\n📋 Available columns: {gauges_df.columns.tolist()}")
        
        # Check key filtering columns
        critical_columns = ['is_active', 'site_type', 'state', 'drainage_area']
        missing_columns = [col for col in critical_columns if col not in gauges_df.columns]
        
        if missing_columns:
            print(f"❌ Still missing columns: {missing_columns}")
        else:
            print("✅ All critical columns present!")
            
            # Test the filtering
            print(f"\n🧪 Testing Filters:")
            
            # Active sites
            if 'is_active' in gauges_df.columns:
                active_count = gauges_df['is_active'].sum()
                print(f"   - Active sites: {active_count} / {len(gauges_df)}")
                print(f"   - is_active types: {gauges_df['is_active'].dtype}")
                print(f"   - is_active values: {gauges_df['is_active'].value_counts().to_dict()}")
            
            # Site types
            if 'site_type' in gauges_df.columns:
                site_types = gauges_df['site_type'].value_counts()
                print(f"   - Site types: {site_types.to_dict()}")
                
                # Test stream filter
                stream_count = (gauges_df['site_type'] == 'ST').sum()
                print(f"   - Stream sites: {stream_count}")
            
            # States
            if 'state' in gauges_df.columns:
                states = gauges_df['state'].value_counts()
                print(f"   - States: {states.to_dict()}")
            
            # Test combined filter (typical dashboard scenario)
            print(f"\n🔄 Testing Combined Filter:")
            filtered = gauges_df[
                (gauges_df['is_active'] == True) &
                (gauges_df['site_type'].isin(['ST', 'LK', 'SP'])) &
                (gauges_df['state'].isin(['OR', 'WA', 'ID']))
            ]
            print(f"   - Active + Surface water + PNW states: {len(filtered)} gauges")
            
            if len(filtered) > 0:
                print("✅ Filtering should work now!")
                
                # Show a sample
                sample = filtered.head(3)[['site_id', 'station_name', 'state', 'site_type', 'is_active']].to_dict('records')
                print(f"\n🔍 Sample filtered gauges:")
                for i, gauge in enumerate(sample):
                    print(f"   {i+1}. {gauge}")
                    
            else:
                print("❌ Still getting 0 results from filtering")
        
        return gauges_df
        
    except Exception as e:
        print(f"❌ Error during refresh: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_data_refresh()
    print("\n🎉 Data refresh test complete!")
