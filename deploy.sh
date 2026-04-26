#!/bin/bash
set -e

DEV=/home/geoskimoto/projects/usgs-streamflow-dashboard
DEPLOY=/home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io
SERVICE=streamflow-dashboard.service

echo "==> Syncing files..."
sudo rsync -av --chown=streamflowdash:streamflowdash \
  --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.env' --exclude='venv/' --exclude='data/stats_cache/' \
  --exclude='deploy.sh' \
  $DEV/ $DEPLOY/

echo "==> Restarting service..."
sudo systemctl restart $SERVICE

echo "==> Status:"
sudo systemctl status $SERVICE --no-pager | tail -6
