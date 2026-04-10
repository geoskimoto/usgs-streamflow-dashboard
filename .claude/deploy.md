# Deployment Guide — streamflow-dashboard.3rdplaces.io

## Overview

The deployed app lives at:
```
/home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/
```

The source code lives at:
```
/home/geoskimoto/projects/usgs-streamflow-dashboard/
```

The deploy directory is **not** a git repo — it receives files via `rsync`.  
The service runs as the `streamflowdash` user under systemd, using the `.venv`
virtualenv inside the deploy directory.

---

## Deploy Steps

### 1. Sync code
```bash
rsync -av --checksum \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.well-known' \
  --exclude='CLAUDE.md' \
  /home/geoskimoto/projects/usgs-streamflow-dashboard/ \
  /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/
```

**Key exclusions — never overwrite these:**
- `.env` — production secrets/config
- `.venv` — production virtualenv (owned by `streamflowdash`)
- `.well-known` — SSL/Let's Encrypt artifacts

### 2. Check if dependencies changed
```bash
diff /home/geoskimoto/projects/usgs-streamflow-dashboard/requirements.txt \
     /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/requirements.txt
```

If `requirements.txt` changed, install new deps before restarting:
```bash
sudo -u streamflowdash /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/.venv/bin/pip install -r /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/requirements.txt
```

### 3. Restart the service
```bash
sudo systemctl restart streamflow-dashboard.service
```

### 4. Verify
```bash
sudo systemctl status streamflow-dashboard.service
# Watch logs for startup errors:
journalctl -u streamflow-dashboard.service -f
```

---

## Service Details

- **Unit file:** `/etc/systemd/system/streamflow-dashboard.service`
- **Gunicorn bind:** `127.0.0.1:8050` (proxied through nginx)
- **Workers:** 1, timeout 120s
- **Python:** `.venv/bin/python3.12`
- **Entry point:** `app:server`

---

## Nginx

Static files and proxy config are managed by CloudPanel. The nginx config is
in `/etc/nginx/sites-enabled/`. Do not route static files through gunicorn.
