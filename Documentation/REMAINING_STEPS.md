# Remaining Steps — Scattermap Migration

## 1. Fix git permissions and commit

```bash
sudo chown -R geoskimoto:geoskimoto /home/geoskimoto/projects/usgs-streamflow-dashboard/.git/objects/

git add usgs_dashboard/components/map_component.py

git commit -m "fix: migrate map from go.Scattermapbox to go.Scattermap for Plotly 6.x compatibility

Plotly 6.x (Plotly.js 3.x) deprecated go.Scattermapbox and the mapbox
layout key in favour of go.Scattermap and map layout; the deprecated API
can fail to render in modern Plotly.js builds, causing blank maps on all
devices. Also replaces broken Stadia Maps Stamen Terrain tiles (HTTP 401)
with CartoDB Voyager tiles (free, no API key required).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

## 2. Deploy to production

```bash
sudo cp /home/geoskimoto/projects/usgs-streamflow-dashboard/usgs_dashboard/components/map_component.py \
  /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/usgs_dashboard/components/map_component.py

sudo chown streamflowdash:streamflowdash \
  /home/streamflowdash/htdocs/streamflow-dashboard.3rdplaces.io/usgs_dashboard/components/map_component.py

sudo systemctl restart streamflow-dashboard.service
```

## 3. Verify

```bash
systemctl is-active streamflow-dashboard.service
journalctl -u streamflow-dashboard.service -f
```

Check the live site at https://streamflow-dashboard.3rdplaces.io — the map should load on all devices.
