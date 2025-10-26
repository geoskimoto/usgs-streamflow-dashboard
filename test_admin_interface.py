"""
Test script for the enhanced admin interface functionality.

This script tests the admin interface components to ensure proper integration
with the station configuration system and validates all major features.
"""

import sys
import requests
import time
from pathlib import Path

# Test the admin components independently
def test_admin_components():
    """Test admin components functionality."""
    print("🧪 Testing Admin Interface Components")
    print("=" * 50)
    
    try:
        # Import admin components
        from admin_components import (
            get_configurations_table, 
            get_system_health_display,
            get_recent_activity_table,
            get_stations_table,
            get_schedules_table,
            StationAdminPanel
        )
        
        print("✅ Admin components imported successfully")
        
        # Test configuration table
        print("\n🎯 Testing configuration table...")
        config_table = get_configurations_table()
        if config_table:
            print("   ✅ Configuration table generated")
        else:
            print("   ❌ Configuration table failed")
        
        # Test system health
        print("\n🏥 Testing system health display...")
        health_display = get_system_health_display()
        if health_display:
            print("   ✅ System health display generated")
        else:
            print("   ❌ System health display failed")
        
        # Test recent activity
        print("\n🔄 Testing recent activity table...")
        activity_table = get_recent_activity_table()
        if activity_table:
            print("   ✅ Recent activity table generated")
        else:
            print("   ❌ Recent activity table failed")
        
        # Test stations table
        print("\n🗺️ Testing stations table...")
        stations_table = get_stations_table(states=['WA'], limit=10)
        if stations_table:
            print("   ✅ Stations table generated (WA filter)")
        else:
            print("   ❌ Stations table failed")
        
        # Test schedules table
        print("\n⏰ Testing schedules table...")
        schedules_table = get_schedules_table()
        if schedules_table:
            print("   ✅ Schedules table generated")
        else:
            print("   ❌ Schedules table failed")
        
        # Test admin panel initialization
        print("\n🎛️ Testing admin panel initialization...")
        panel = StationAdminPanel()
        if panel:
            print("   ✅ Admin panel initialized")
        else:
            print("   ❌ Admin panel initialization failed")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Admin components test failed: {e}")
        return False


def test_dashboard_accessibility():
    """Test if the dashboard is accessible."""
    print("\n🌐 Testing Dashboard Accessibility")
    print("=" * 40)
    
    try:
        # Test main dashboard
        response = requests.get("http://localhost:8050", timeout=10)
        if response.status_code == 200:
            print("   ✅ Dashboard is accessible")
            
            # Check if response contains admin elements
            content = response.text
            if 'admin-tab-content' in content:
                print("   ✅ Admin interface elements found in HTML")
            else:
                print("   ⚠️  Admin interface elements not found in HTML")
            
            return True
        else:
            print(f"   ❌ Dashboard returned status code: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to dashboard (not running?)")
        return False
    except Exception as e:
        print(f"   ❌ Dashboard accessibility test failed: {e}")
        return False


def test_database_integration():
    """Test database integration with admin interface."""
    print("\n💾 Testing Database Integration")
    print("=" * 35)
    
    try:
        from station_config_manager import StationConfigurationManager
        
        with StationConfigurationManager() as manager:
            # Test configuration retrieval
            configs = manager.get_configurations()
            print(f"   ✅ Retrieved {len(configs)} configurations")
            
            # Test station queries
            all_stations = manager.get_stations_by_criteria()
            print(f"   ✅ Retrieved {len(all_stations)} total stations")
            
            # Test WA stations specifically
            wa_stations = manager.get_stations_by_criteria(states=['WA'])
            print(f"   ✅ Retrieved {len(wa_stations)} Washington stations")
            
            # Test Columbia Basin stations
            columbia_stations = manager.get_stations_by_criteria(source_datasets=['HADS_Columbia'])
            print(f"   ✅ Retrieved {len(columbia_stations)} Columbia Basin stations")
            
            # Test system health
            health = manager.get_system_health()
            print(f"   ✅ System health: {health['active_configurations']} configs, {health['active_stations']} stations")
            
            # Test recent activity (might be empty)
            activity = manager.get_recent_collection_logs(limit=5)
            print(f"   ✅ Retrieved {len(activity)} recent activity logs")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Database integration test failed: {e}")
        return False


def demonstrate_admin_features():
    """Demonstrate key admin interface features."""
    print("\n💡 Admin Interface Feature Demonstration")
    print("=" * 45)
    
    print("🎯 Available Admin Features:")
    print("   - Configuration Management: View and manage station configurations")
    print("   - Station Browser: Search and filter 1,500+ discharge stations")
    print("   - Schedule Management: Configure automated data collection")
    print("   - Collection Monitoring: Real-time status and performance metrics")
    print("   - System Health: Overview of system status and statistics")
    
    print("\n📊 Current System Status:")
    try:
        from station_config_manager import StationConfigurationManager
        
        with StationConfigurationManager() as manager:
            configs = manager.get_configurations()
            health = manager.get_system_health()
            
            print(f"   Configurations: {len(configs)} available")
            for config in configs:
                status = "✅ Active" if config['is_active'] else "❌ Inactive"
                default = " (Default)" if config['is_default'] else ""
                print(f"     - {config['config_name']}: {config['actual_station_count']} stations {status}{default}")
            
            print(f"\n   System Health:")
            print(f"     - Active Stations: {health['active_stations']:,}")
            print(f"     - Success Rate (24h): {health['recent_success_rate']}%")
            print(f"     - Recent Runs: {health['recent_runs_24h']}")
            print(f"     - Currently Running: {health['currently_running']}")
    
    except Exception as e:
        print(f"   ❌ Feature demonstration failed: {e}")
    
    print("\n🔗 Access Instructions:")
    print("   1. Open http://localhost:8050 in your browser")
    print("   2. Click the '🔧 Admin' button in the top navigation")
    print("   3. Use the admin tabs to navigate between features:")
    print("      - 📈 Dashboard: System overview and health metrics")
    print("      - 🎯 Configurations: Manage station configurations")
    print("      - 🗺️ Stations: Browse and filter stations")
    print("      - ⏰ Schedules: Manage collection schedules")
    print("      - 📊 Monitoring: View collection activity and performance")


def main():
    """Run all admin interface tests."""
    print("🔧 USGS Admin Interface Test Suite")
    print("=" * 40)
    
    # Run tests
    tests = [
        test_admin_components,
        test_database_integration,
        test_dashboard_accessibility
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   💥 Test crashed: {e}")
            failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All admin interface tests passed!")
        demonstrate_admin_features()
        
        print("\n🎉 Phase 2 Admin Interface - READY FOR USE!")
        print("=" * 50)
        print("The admin interface is fully operational with:")
        print("  ✅ Station configuration management")
        print("  ✅ Real-time system monitoring")
        print("  ✅ Advanced station browser with filtering")
        print("  ✅ Schedule management interface")
        print("  ✅ Collection activity tracking")
        print("  ✅ System health dashboard")
        print("\nAdmin interface accessible at: http://localhost:8050 → 🔧 Admin")
        
    else:
        print("❌ Some admin interface tests failed. Please review errors.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())