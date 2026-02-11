#!/bin/bash
# Dashboard Startup Script - Fixed Version
# This script ensures the dashboard starts from the correct directory

echo "🚀 Starting USGS Dashboard with Fixes Applied..."
echo "================================================"

# Navigate to dashboard directory
cd "$(dirname "$0")"
echo "📁 Current directory: $(pwd)"

# Check if we're in the right place
if [ ! -f "app.py" ]; then
    echo "❌ Error: app.py not found. Make sure you're in the usgs_dashboard directory."
    exit 1
fi

# Show fix summary
echo ""
echo "✅ FIXES APPLIED:"
echo "   1. Fixed Plotly hoverlabel 'border_color' → 'bordercolor'"  
echo "   2. Updated deprecated Scattermapbox → Scattermap"
echo "   3. Added empty data handling in map component"
echo "   4. Fixed database table creation (gauge_metadata)"
echo "   5. Enhanced activity detection for site filtering"
echo "   6. Added comprehensive error handling"
echo ""
echo "🔧 FEATURES READY:"
echo "   - Interactive Pacific Northwest map with 2,600+ USGS gauges"
echo "   - Advanced filtering by active/inactive status, site type, state"
echo "   - Drainage area range filtering"
echo "   - Agency and data quality filters"
echo "   - Real-time filter status and gauge counts"
echo "   - Streamflow analysis for selected gauges"
echo ""

# Start the dashboard
echo "🌐 Starting dashboard on http://localhost:8050..."
echo "   Press Ctrl+C to stop"
echo ""

python app.py
