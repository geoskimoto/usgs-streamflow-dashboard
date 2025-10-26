#!/usr/bin/env python3
"""
Test script to verify deployment configuration.
"""

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """Test that we can import the app module from usgs_dashboard."""
    try:
        # Change to the usgs_dashboard directory
        original_cwd = os.getcwd()
        usgs_dashboard_path = os.path.join(os.path.dirname(__file__), 'usgs_dashboard')
        os.chdir(usgs_dashboard_path)
        
        # Try to import the app (this simulates what gunicorn will do)
        sys.path.insert(0, usgs_dashboard_path)
        
        # This would be equivalent to: gunicorn --chdir usgs_dashboard app:server
        import app
        server = getattr(app, 'server', None)
        
        if server:
            print("✅ SUCCESS: app.server found and accessible")
            print(f"   Server type: {type(server)}")
            return True
        else:
            print("❌ ERROR: app.server not found")
            return False
            
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False
    finally:
        # Restore original working directory
        os.chdir(original_cwd)

def test_procfile():
    """Test that Procfile format is correct."""
    try:
        with open('Procfile', 'r') as f:
            content = f.read().strip()
        
        print(f"📄 Procfile content: {content}")
        
        if content.startswith('web: gunicorn') and 'app:server' in content:
            print("✅ Procfile format looks correct")
            return True
        else:
            print("❌ Procfile format may be incorrect")
            return False
            
    except FileNotFoundError:
        print("❌ ERROR: Procfile not found")
        return False

if __name__ == "__main__":
    print("🚀 Testing deployment configuration...")
    print()
    
    procfile_ok = test_procfile()
    print()
    
    import_ok = test_import()
    print()
    
    if procfile_ok and import_ok:
        print("🎉 All tests passed! Deployment should work.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")