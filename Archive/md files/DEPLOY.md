# USGS Streamflow Dashboard - Render Deployment

## Quick Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## Manual Deployment Steps

1. **Fork/Clone this repository**
2. **Connect to Render**:
   - Go to [render.com](https://render.com)
   - Create account and connect your GitHub
   - Select "New Web Service"
   - Connect this repository

3. **Configure Service**:
   - **Name**: `usgs-streamflow-dashboard`
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd usgs_dashboard && python app.py`

4. **Environment Variables** (Optional):
   - `DASH_DEBUG`: `false` (for production)
   - `PORT`: (Auto-set by Render)

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run dashboard
cd usgs_dashboard
python app.py
```

Navigate to `http://localhost:8050`

## Features

- **Historical Data**: Full records from 1910 to present
- **Current Highlighting**: Water Year 2025 & 2026 highlighted by default  
- **Advanced Filtering**: Site status, drainage area, data quality filters
- **Performance Optimized**: Subset mode for faster testing (300 sites)
- **Real-time Updates**: Current water year automatically calculated

## Data Sources

- **USGS NWIS**: Real-time and historical streamflow data
- **Coverage**: Oregon, Washington, Idaho
- **Parameters**: Daily mean discharge (cubic feet per second)

## Dashboard Structure

```
usgs_dashboard/
├── app.py              # Main application
├── data/               # Data management
├── components/         # UI components  
├── utils/              # Configuration
└── requirements.txt    # Dependencies
```