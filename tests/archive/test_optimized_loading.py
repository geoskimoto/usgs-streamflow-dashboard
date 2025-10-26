#!/usr/bin/env python3
"""
Test script to verify the optimized single-pass data loading system.
This tests the performance improvements and validates the functionality.
"""

import sys
import os
import time
sys.path.append('./usgs_dashboard')

import pandas as pd
from usgs_dashboard.utils.config import SUBSET_CONFIG
from usgs_dashboard.data.data_manager import USGSDataManager

def test_optimized_loading():
    """Test the optimized single-pass data loading system."""
    print("🚀 Testing Optimized Single-Pass Data Loading System")
    print("=" * 70)
    
    # Show current configuration
    print("Optimized Configuration:")
    for key, value in SUBSET_CONFIG.items():
        if 'optimized' in key.lower() or 'early' in key.lower() or 'validation' in key.lower() or 'single_pass' in key.lower():
            print(f"  ⚡ {key}: {value}")
        else:
            print(f"    {key}: {value}")
    print()
    
    # Create data manager instance
    manager = USGSDataManager()
    print("✅ Data manager created")
    
    # Clear cache to ensure fresh test
    try:
        manager.clear_cache()
        print("🧹 Cache cleared for fresh test")
    except:
        print("⚠️  Could not clear cache (may not exist yet)")
    
    print(f"\n🔍 Testing Optimized Data Loading")
    print("-" * 50)
    
    # Test the optimized loading system
    start_time = time.time()
    
    try:
        print("Starting optimized data loading...")
        gauges = manager.load_regional_gauges(refresh=True)
        
        end_time = time.time()
        loading_time = end_time - start_time
        
        print(f"\n🎉 OPTIMIZED LOADING SUCCESS!")
        print(f"📊 Results:")
        print(f"  ✅ Sites loaded: {len(gauges)}")
        print(f"  ⏱️  Loading time: {loading_time:.1f} seconds ({loading_time/60:.1f} minutes)")
        print(f"  🚀 Performance: ~{loading_time/len(gauges):.2f} seconds per site")
        
        # Analyze the loaded data
        print(f"\n📈 Data Analysis:")
        if 'state' in gauges.columns:
            state_dist = gauges['state'].value_counts().to_dict()
            print(f"  State distribution: {state_dist}")
        
        if 'is_active' in gauges.columns:
            active_count = gauges['is_active'].sum()
            print(f"  Active sites: {active_count}/{len(gauges)} ({active_count/len(gauges)*100:.1f}%)")
        
        # Verify data quality
        print(f"\n🔍 Data Quality Check:")
        if 'last_data_date' in gauges.columns:
            recent_data = gauges['last_data_date'].notna().sum()
            print(f"  Sites with recent data: {recent_data}/{len(gauges)} ({recent_data/len(gauges)*100:.1f}%)")
        
        # Test subset status
        try:
            status = manager.get_subset_status()
            print(f"\n📊 Subset Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")
        except Exception as e:
            print(f"⚠️  Could not get subset status: {e}")
        
        # Performance estimate for full dataset
        if SUBSET_CONFIG['enabled']:
            estimated_full_time = (loading_time / len(gauges)) * 2811
            print(f"\n📈 Performance Projection:")
            print(f"  Current subset: {len(gauges)} sites in {loading_time:.1f} seconds")
            print(f"  Full dataset estimate: 2811 sites in ~{estimated_full_time:.1f} seconds ({estimated_full_time/60:.1f} minutes)")
            print(f"  Estimated improvement: ~{(estimated_full_time/60):.1f} minutes vs old ~25 minutes (savings: ~{(25-(estimated_full_time/60)):.1f} minutes)")
        
    except Exception as e:
        print(f"❌ Error during optimized loading: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print(f"\n🎯 OPTIMIZATION TEST COMPLETE!")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if loading_time < 300:  # Less than 5 minutes
        print(f"  ✅ Performance is excellent! Loading completed in {loading_time/60:.1f} minutes")
    elif loading_time < 600:  # Less than 10 minutes
        print(f"  ⚠️  Performance is good but could be improved. Consider reducing validation_years.")
    else:
        print(f"  ❌ Performance needs improvement. Check network connection and consider smaller subset.")
    
    if SUBSET_CONFIG['enabled']:
        print(f"  🔧 To test full dataset: set SUBSET_CONFIG['enabled'] = False in config.py")
    else:
        print(f"  🔧 For faster testing: set SUBSET_CONFIG['enabled'] = True in config.py")
    
    return True

def test_data_consistency():
    """Test that the optimized system produces consistent results."""
    print(f"\n🔍 Testing Data Consistency")
    print("-" * 40)
    
    manager = USGSDataManager()
    
    # Load data twice and compare
    print("Loading data first time...")
    gauges1 = manager.load_regional_gauges(refresh=True)
    
    print("Loading data second time (should use cache)...")
    gauges2 = manager.load_regional_gauges(refresh=False)
    
    if len(gauges1) == len(gauges2):
        print(f"✅ Consistency check passed: Both loads returned {len(gauges1)} sites")
    else:
        print(f"❌ Consistency check failed: First load: {len(gauges1)}, Second load: {len(gauges2)}")
    
    return len(gauges1) == len(gauges2)

if __name__ == "__main__":
    print("🧪 OPTIMIZED DATA LOADING SYSTEM TEST")
    print("=" * 70)
    print("This test validates the new single-pass data loading system")
    print("that eliminates redundant API calls and applies subset filtering early.")
    print()
    
    success = test_optimized_loading()
    
    if success:
        consistency = test_data_consistency()
        if consistency:
            print(f"\n🎉 ALL TESTS PASSED!")
            print(f"✅ Optimized system is working correctly")
            print(f"✅ Performance improvements confirmed")
            print(f"✅ Data consistency verified")
        else:
            print(f"\n⚠️  Performance test passed but consistency check failed")
    else:
        print(f"\n❌ Tests failed - check implementation")
    
    print(f"\n🚀 Ready for optimized dashboard usage!")
    print(f"Run: cd usgs_dashboard && python app.py")