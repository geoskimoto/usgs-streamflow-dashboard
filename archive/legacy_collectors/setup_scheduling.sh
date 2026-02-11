#!/bin/bash
"""
USGS Real-time Data System Setup

This script helps you set up the automated scheduling for your USGS data updates.
Run this script to configure crontab and create necessary directories.
"""

echo "🚀 Setting up USGS Real-time Data System Scheduling..."
echo "=================================================="

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p logs
chmod 755 logs

# Make scripts executable
echo "🔧 Making scripts executable..."
chmod +x update_realtime_discharge.py
chmod +x update_daily_discharge.py
chmod +x smart_scheduler.py

# Get the current directory
PROJECT_DIR=$(pwd)
echo "📍 Project directory: $PROJECT_DIR"

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 is not installed or not in PATH"
    echo "   Please install Python 3 and try again"
    exit 1
fi

PYTHON_PATH=$(which python3)
echo "🐍 Python path: $PYTHON_PATH"

echo ""
echo "📅 SCHEDULING OPTIONS:"
echo "====================="
echo ""
echo "Choose your preferred scheduling method:"
echo ""
echo "1️⃣  OPTION 1: Basic Crontab (Simple, reliable)"
echo "   - Real-time updates every 2 hours"  
echo "   - Daily updates at 6 AM and 6 PM"
echo "   - Direct cron job execution"
echo ""
echo "2️⃣  OPTION 2: Smart Scheduler (Advanced, flexible)"
echo "   - Database-driven scheduling"
echo "   - Configurable via dashboard"
echo "   - Better error handling and logging"
echo ""

read -p "Enter your choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    echo ""
    echo "📋 BASIC CRONTAB SETUP"
    echo "====================="
    echo ""
    echo "Add these lines to your crontab (crontab -e):"
    echo ""
    echo "# USGS Real-time Data Updates"
    echo "0 */2 * * * cd $PROJECT_DIR && $PYTHON_PATH update_realtime_discharge.py >> logs/realtime_updates.log 2>&1"
    echo "0 6,18 * * * cd $PROJECT_DIR && $PYTHON_PATH update_daily_discharge.py >> logs/daily_updates.log 2>&1"
    echo ""
    
    read -p "Would you like me to add these to your crontab automatically? (y/N): " auto_setup
    
    if [ "$auto_setup" = "y" ] || [ "$auto_setup" = "Y" ]; then
        # Create temporary crontab file
        TEMP_CRON=$(mktemp)
        
        # Get existing crontab (if any)
        crontab -l 2>/dev/null > "$TEMP_CRON" || true
        
        # Add our jobs if they don't already exist
        if ! grep -q "update_realtime_discharge.py" "$TEMP_CRON"; then
            echo "# USGS Real-time Data Updates" >> "$TEMP_CRON"
            echo "0 */2 * * * cd $PROJECT_DIR && $PYTHON_PATH update_realtime_discharge.py >> logs/realtime_updates.log 2>&1" >> "$TEMP_CRON"
        fi
        
        if ! grep -q "update_daily_discharge.py" "$TEMP_CRON"; then
            echo "0 6,18 * * * cd $PROJECT_DIR && $PYTHON_PATH update_daily_discharge.py >> logs/daily_updates.log 2>&1" >> "$TEMP_CRON"
        fi
        
        # Install the new crontab
        crontab "$TEMP_CRON"
        rm "$TEMP_CRON"
        
        echo "✅ Crontab updated successfully!"
        echo "📊 View your crontab: crontab -l"
    else
        echo "⚠️  Manual setup required. Run 'crontab -e' and add the lines above."
    fi

elif [ "$choice" = "2" ]; then
    echo ""
    echo "🧠 SMART SCHEDULER SETUP"
    echo "========================"
    echo ""
    echo "Add this single line to your crontab (crontab -e):"
    echo ""
    echo "# USGS Smart Scheduler (checks every 15 minutes)"
    echo "*/15 * * * * cd $PROJECT_DIR && $PYTHON_PATH smart_scheduler.py >> logs/scheduler.log 2>&1"
    echo ""
    
    read -p "Would you like me to add this to your crontab automatically? (y/N): " auto_setup
    
    if [ "$auto_setup" = "y" ] || [ "$auto_setup" = "Y" ]; then
        # Create temporary crontab file
        TEMP_CRON=$(mktemp)
        
        # Get existing crontab (if any)
        crontab -l 2>/dev/null > "$TEMP_CRON" || true
        
        # Add smart scheduler if it doesn't exist
        if ! grep -q "smart_scheduler.py" "$TEMP_CRON"; then
            echo "# USGS Smart Scheduler" >> "$TEMP_CRON"
            echo "*/15 * * * * cd $PROJECT_DIR && $PYTHON_PATH smart_scheduler.py >> logs/scheduler.log 2>&1" >> "$TEMP_CRON"
        fi
        
        # Install the new crontab
        crontab "$TEMP_CRON"
        rm "$TEMP_CRON"
        
        echo "✅ Crontab updated successfully!"
        echo "📊 View your crontab: crontab -l"
    else
        echo "⚠️  Manual setup required. Run 'crontab -e' and add the line above."
    fi

else
    echo "❌ Invalid choice. Please run the script again and choose 1 or 2."
    exit 1
fi

echo ""
echo "🎉 SETUP COMPLETE!"
echo "=================="
echo ""
echo "📁 Log files will be created in: $PROJECT_DIR/logs/"
echo "🔍 Monitor real-time updates: tail -f logs/realtime_updates.log"
echo "🔍 Monitor daily updates: tail -f logs/daily_updates.log"
echo "📊 Check job status in the dashboard Admin tab"
echo ""
echo "🚦 NEXT STEPS:"
echo "-------------"
echo "1. The scripts will start running automatically according to the schedule"
echo "2. Check the logs in a few hours to ensure everything is working"
echo "3. Use the dashboard Admin tab to monitor job status and trigger manual runs"
echo "4. Real-time data will appear in visualizations automatically"
echo ""
echo "📞 TROUBLESHOOTING:"
echo "------------------"
echo "- Check crontab: crontab -l"
echo "- View logs: ls -la logs/"
echo "- Test scripts manually: python3 update_realtime_discharge.py"
echo "- Check database: python3 -c 'from usgs_dashboard.data.data_manager import USGSDataManager; dm = USGSDataManager(); print(len(dm.get_realtime_data(\"10039500\")) if dm.get_realtime_data(\"10039500\") is not None else 0, \"records\")'"
echo ""