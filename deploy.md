# Deploy to dashboard.streamflows.org

## Quick Deploy

From the dev directory on the VPS:

```bash
./deploy.sh
```

`deploy.sh` rsyncs changed files to the htdocs directory, fixes ownership, and restarts the service. It excludes `.env`, `data/stats_cache/`, `.git`, and `__pycache__`.

## If new Python dependencies were added

```bash
sudo -u streamflowdash /home/streamflowdash/htdocs/dashboard.streamflows.org/.venv/bin/pip install -r /home/streamflowdash/htdocs/dashboard.streamflows.org/requirements.txt -q
```

## Pre-warm the stats cache (optional but recommended)

The water-year statistics cache (parquet files in `data/stats_cache/`) is excluded from rsync and builds automatically on first gauge click. To pre-warm it on the server instead:

```bash
cd /home/streamflowdash/htdocs/dashboard.streamflows.org
sudo -u streamflowdash .venv/bin/python manage_cache.py rebuild_stats --active
```

Cache files are stored as `data/stats_cache/<site_id>_WY<year>.parquet` — one file per station per water year. They are **not** a SQLite database.

## Verify

```bash
sudo systemctl status streamflow-dashboard.service
journalctl -u streamflow-dashboard.service -f
```

Then hard-refresh browser (Ctrl+Shift+R) at https://dashboard.streamflows.org

If Varnish cache is enabled in CloudPanel, purge it too:

```bash
sudo varnishadm "ban req.url ~ /"
```
