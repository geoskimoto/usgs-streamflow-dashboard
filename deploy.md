# Deploy to streamflow-dashboard.3rdplaces.io

## Quick Deploy (run as root or with sudo)

```bash
cd /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io
sudo -u streamflowdash git pull origin main
sudo systemctl restart streamflow-dashboard.service
```

## Verify

```bash
sudo systemctl status streamflow-dashboard.service
```

Then hard-refresh browser (Ctrl+Shift+R) at https://streamflow-dashboard.3rdplaces.io

If Varnish cache is enabled in CloudPanel, purge it too:

```bash
sudo varnishadm "ban req.url ~ /"
```
