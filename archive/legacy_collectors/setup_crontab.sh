#!/bin/bash
# USGS Data Update Crontab Configuration
# 
# Add these lines to your crontab by running: crontab -e
# Then paste these entries:

# Real-time data updates: Every 2 hours
0 */2 * * * cd /home/mrguy/Projects/stackedlineplots/StackedLinePlots && /usr/bin/python3 update_realtime_discharge.py >> logs/realtime_updates.log 2>&1

# Daily data updates: Every 12 hours at 6 AM and 6 PM
0 6,18 * * * cd /home/mrguy/Projects/stackedlineplots/StackedLinePlots && /usr/bin/python3 update_daily_discharge.py >> logs/daily_updates.log 2>&1

# Optional: Clean up old logs monthly
0 0 1 * * find /home/mrguy/Projects/stackedlineplots/StackedLinePlots/logs -name "*.log" -mtime +30 -delete

# Explanation:
# 0 */2 * * *     = Every 2 hours at minute 0 (12:00 AM, 2:00 AM, 4:00 AM, etc.)
# 0 6,18 * * *    = At 6:00 AM and 6:00 PM daily
# >> logs/file.log 2>&1 = Redirect both stdout and stderr to log file