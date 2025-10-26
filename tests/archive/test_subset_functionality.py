"""
Test Data Subset Functionality

This script tests the new data subset feature to ensure it works correctly
and provides faster loading for development and testing.
"""

import sys
import os
sys.path.append('/home/mrguy/Projects/stackedlineplots/StackedLinePlots/usgs_dashboard')

from data.data_manager import get_data_manager
from utils.config import SUBSET_CONFIG
import pandas as pd
import time

def test_subset_functionality():
    """Test the data subset feature implementation."""
    print("🧪 Testing Data Subset Functionality...")
    print(f"📋 Current subset configuration:")
    for key, value in SUBSET_CONFIG.items():
        print(f"   {key}: {value}")
    
    # Get data manager
    dm = get_data_manager()
    
    # Clear cache to start fresh
    print("\n🗑️ Clearing cache for clean test...")
    dm.clear_cache()
    
    # Test 1: Load with subset enabled
    print(f"\n🎯 Test 1: Loading data with subset enabled (max {SUBSET_CONFIG['max_sites']} sites)")
    start_time = time.time()
    
    try:
        gauges_subset = dm.load_regional_gauges(refresh=True)
        load_time = time.time() - start_time
        
        print(f"✅ Subset loading successful!")
        print(f"   - Sites loaded: {len(gauges_subset)}")
        print(f"   - Load time: {load_time:.1f} seconds")
        print(f"   - Method used: {SUBSET_CONFIG['method']}")
        
        # Check subset composition
        if len(gauges_subset) > 0:
            print(f"\n📊 Subset composition:")
            
            # State distribution
            if 'state' in gauges_subset.columns:
                state_counts = gauges_subset['state'].value_counts()
                print(f"   States: {state_counts.to_dict()}")
            
            # Activity distribution
            if 'is_active' in gauges_subset.columns:
                active_count = gauges_subset['is_active'].sum()
                print(f"   Active sites: {active_count} ({100*active_count/len(gauges_subset):.1f}%)")
            
            # Years of record distribution
            if 'years_of_record' in gauges_subset.columns:
                years_stats = gauges_subset['years_of_record'].describe()
                print(f"   Years of record - Mean: {years_stats['mean']:.1f}, Max: {years_stats['max']:.0f}")
        
        # Test subset status
        print(f"\n📋 Subset status:")
        subset_status = dm.get_subset_status()
        for key, value in subset_status.items():
            print(f"   {key}: {value}")
        
        # Test 2: Test cached subset selection
        print(f"\n💾 Test 2: Testing cached subset selection...")
        start_time = time.time()
        
        gauges_cached = dm.load_regional_gauges(refresh=False)
        cached_load_time = time.time() - start_time
        
        print(f"✅ Cached loading successful!")
        print(f"   - Sites loaded: {len(gauges_cached)}")
        print(f"   - Load time: {cached_load_time:.1f} seconds")
        print(f"   - Same sites as first load: {len(gauges_subset) == len(gauges_cached)}")
        
        # Test 3: Compare different subset methods
        print(f"\n🔄 Test 3: Testing different subset methods...")
        
        methods_to_test = ['balanced', 'top_quality', 'random']
        results = {}
        
        for method in methods_to_test:
            # Temporarily change config
            original_method = SUBSET_CONFIG['method']
            SUBSET_CONFIG['method'] = method
            
            # Clear subset cache
            dm.clear_cache()
            
            # Load with new method
            start_time = time.time()
            gauges_method = dm.load_regional_gauges(refresh=True)
            method_time = time.time() - start_time
            
            results[method] = {
                'count': len(gauges_method),
                'time': method_time,
                'active_pct': (gauges_method['is_active'].sum() / len(gauges_method) * 100) if len(gauges_method) > 0 else 0
            }
            
            print(f"   {method}: {len(gauges_method)} sites, {method_time:.1f}s, {results[method]['active_pct']:.1f}% active")
        
        # Restore original method
        SUBSET_CONFIG['method'] = original_method
        
        # Test 4: Performance comparison estimation
        print(f"\n⚡ Test 4: Performance impact estimation...")
        
        # Estimate full dataset size (extrapolate from subset)
        if SUBSET_CONFIG['method'] == 'balanced':
            # For balanced method, we can estimate total sites per state
            state_totals = {}
            for state in ['OR', 'WA', 'ID']:
                state_subset = gauges_subset[gauges_subset['state'] == state]
                if len(state_subset) > 0:
                    # Rough estimate based on subset ratio
                    target_ratio = SUBSET_CONFIG['state_distribution'].get(state, 0.33)
                    estimated_state_total = len(state_subset) / target_ratio
                    state_totals[state] = int(estimated_state_total)
            
            estimated_total = sum(state_totals.values())
            print(f"   Estimated full dataset size: ~{estimated_total:,} sites")
            print(f"   Subset ratio: {len(gauges_subset) / estimated_total:.1%}")
            print(f"   Estimated full load time: {load_time * (estimated_total / len(gauges_subset)):.1f} seconds")
        
        print(f"\n🎉 All subset functionality tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during subset testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_subset_configuration_changes():
    """Test changing subset configuration."""
    print(f"\n🔧 Testing subset configuration changes...")
    
    dm = get_data_manager()
    
    # Test with different sizes
    sizes_to_test = [100, 300, 500]
    
    for size in sizes_to_test:
        print(f"\n   Testing size: {size}")
        
        # Update config
        original_size = SUBSET_CONFIG['max_sites']
        SUBSET_CONFIG['max_sites'] = size
        
        # Clear cache to force new selection
        dm.clear_cache()
        
        # Load data
        gauges = dm.load_regional_gauges(refresh=True)
        
        print(f"   Result: {len(gauges)} sites loaded")
        
        # Restore original size
        SUBSET_CONFIG['max_sites'] = original_size

if __name__ == "__main__":
    print("🎯 Data Subset Functionality Test")
    print("=" * 50)
    
    success = test_subset_functionality()
    
    if success:
        test_subset_configuration_changes()
        print(f"\n✅ All tests completed successfully!")
        print(f"\n💡 Next steps:")
        print(f"   1. Start the dashboard: python usgs_dashboard/app.py")
        print(f"   2. Test subset controls in the sidebar")
        print(f"   3. Try different subset sizes and methods")
        print(f"   4. Compare loading times with full dataset")
    else:
        print(f"\n❌ Tests failed - check error messages above")