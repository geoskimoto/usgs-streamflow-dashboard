#!/usr/bin/env bash
# One-command deploy: push main from dev, pull in prod as streamflowdash, install deps if
# requirements.txt changed, restart, and smoke-check. Run from anywhere as geoskimoto:
#   ./deploy.sh
# Deploys what is COMMITTED on main (git pull), never uncommitted dev edits.
set -euo pipefail

DEV=/home/geoskimoto/projects/usgs-streamflow-dashboard
DEPLOY=/home/streamflowdash/htdocs/dashboard.streamflows.org
SERVICE=streamflow-dashboard.service
PORT=8050

cd "$DEV"

branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != "main" ]; then
    echo "!! On branch '$branch', not main. Deploy is main-only." >&2
    exit 1
fi

if ! git diff --quiet -- . ':!config/resid_cast_stations.json' || ! git diff --cached --quiet; then
    echo "!! Uncommitted changes to tracked files. Commit them first (they would not be deployed)." >&2
    git status --short >&2
    exit 1
fi
if ! git diff --quiet -- config/resid_cast_stations.json; then
    echo "-- Note: config/resid_cast_stations.json has uncommitted edits; they will NOT be deployed."
fi

echo "==> Pushing main..."
git push origin main

echo "==> Pulling in prod..."
old_req=$(sudo -u streamflowdash sha256sum "$DEPLOY/requirements.txt" | cut -d' ' -f1)
sudo -u streamflowdash git -C "$DEPLOY" pull --ff-only origin main
new_req=$(sudo -u streamflowdash sha256sum "$DEPLOY/requirements.txt" | cut -d' ' -f1)

if [ "$old_req" != "$new_req" ]; then
    echo "==> requirements.txt changed; installing..."
    sudo -u streamflowdash "$DEPLOY/.venv/bin/pip" install -r "$DEPLOY/requirements.txt" -q
fi

echo "==> Restarting $SERVICE..."
sudo systemctl restart "$SERVICE"

echo "==> Waiting for the app..."
code=000
for _ in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" || true)
    [ "$code" != "000" ] && break
    sleep 1
done
sudo systemctl status "$SERVICE" --no-pager | tail -6
if [ "$code" = "000" ] || [ "$code" -ge 500 ]; then
    echo "!! App returned HTTP $code. Check: journalctl -u $SERVICE -n 50" >&2
    exit 1
fi
echo "==> Deployed $(git rev-parse --short HEAD) (HTTP $code)"
