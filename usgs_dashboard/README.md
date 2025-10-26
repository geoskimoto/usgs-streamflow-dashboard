# USGS Streamflow Dashboard

Interactive web dashboard for exploring USGS streamflow gauges across Oregon, Washington, and Idaho. Click on any gauge to view comprehensive water year analysis, flow statistics, and visualizations.

## Features

### 🗺️ Interactive Map
- **Geographic Coverage**: Oregon, Washington, Idaho
- **Color-coded Gauges**: Status based on years of record
  - 🟢 Green: >20 years (excellent)
  - 🟡 Yellow: 10-20 years (good) 
  - 🟠 Orange: 5-10 years (fair)
  - 🔴 Red: <5 years (poor)
  - ⚫ Gray: Inactive gauges
- **Hover Information**: Station name, drainage area, years of record
- **Multiple Map Styles**: OpenStreetMap, satellite, terrain

### 📊 Streamflow Analysis
- **Water Year Plots**: October-September water year visualization
- **Flow Duration Curves**: Statistical flow analysis
- **Annual/Monthly Summaries**: Temporal pattern analysis
- **Percentile Bands**: Statistical overlays and comparisons
- **Highlight Years**: Emphasize drought/flood years

### 🎛️ Dashboard Controls
- **State Filtering**: Select OR, WA, ID individually or combined
- **Years of Record Filter**: Minimum data availability requirements
- **Plot Configuration**: Highlight years, statistics options
- **Data Management**: Refresh gauges, clear cache

## Installation

### Prerequisites
- Python 3.8+ 
- Internet connection (for USGS data access)

### Quick Start

1. **Navigate to dashboard directory:**
   ```bash
   cd usgs_dashboard
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the dashboard:**
   ```bash
   ./run_dashboard.sh
   ```
   
   Or manually:
   ```bash
   python app.py
   ```

4. **Open your browser:**
   ```
   http://localhost:8050
   ```

## Usage

### Basic Workflow
1. **Explore the Map**: View ~500-1000 USGS gauges across the Pacific Northwest
2. **Filter Gauges**: Use controls to filter by state, data availability, etc.
3. **Select a Gauge**: Click on any colored marker to select it
4. **View Analysis**: Streamflow plots and statistics automatically load
5. **Customize Plots**: Change plot types, highlight specific years
6. **Export Data**: Download plots or data for further analysis

### Plot Types Available
- **Water Year Plot**: Day-of-water-year stacked line plots
- **Annual Summary**: Year-over-year flow statistics  
- **Monthly Summary**: Seasonal flow patterns
- **Flow Duration Curve**: Exceedance probability analysis
- **Daily Timeseries**: Complete daily flow record

### Highlighting Years
Enter comma-separated years in the control panel to highlight specific periods:
```
2012, 2015, 2021
```
Useful for drought years, flood years, or periods of interest.

## Project Structure

```
usgs_dashboard/
├── app.py                      # Main Dash application
├── requirements.txt            # Python dependencies
├── run_dashboard.sh           # Startup script
├── components/
│   ├── map_component.py       # Interactive map functionality
│   └── viz_manager.py         # Streamflow visualization manager
├── data/
│   ├── data_manager.py        # USGS data retrieval and caching
│   └── usgs_cache.db          # SQLite cache database (auto-created)
└── utils/
    └── config.py              # Configuration settings
```

## Configuration

Edit `utils/config.py` to customize:

```python
# Target states for gauge discovery
TARGET_STATES = ['OR', 'WA', 'ID']

# Map center and zoom
MAP_CENTER_LAT = 44.0
MAP_CENTER_LON = -120.5
DEFAULT_ZOOM_LEVEL = 6

# Cache settings
CACHE_DURATION = 86400  # 24 hours in seconds

# Color scheme for gauge status
GAUGE_COLORS = {
    'excellent': {'color': '#2E8B57', 'opacity': 0.8},  # >20 years
    'good': {'color': '#FFD700', 'opacity': 0.8},       # 10-20 years
    'fair': {'color': '#FF8C00', 'opacity': 0.8},       # 5-10 years
    'poor': {'color': '#DC143C', 'opacity': 0.8},       # <5 years
    'inactive': {'color': '#808080', 'opacity': 0.6}    # Inactive
}
```

## Data Sources

- **USGS NWIS**: Real-time and historical streamflow data
- **dataretrieval**: Official Python library for USGS data access
- **Gauge Metadata**: Station information, drainage areas, periods of record

## Performance Features

### Caching System
- **SQLite Database**: Local caching of gauge metadata and streamflow data
- **Smart Updates**: Only fetches new data when cache expires
- **Background Loading**: Efficient data retrieval and storage

### Map Optimization
- **Marker Sizing**: Drainage area-based marker scaling
- **Clustering**: Efficient display of hundreds of gauges
- **Responsive Design**: Works on desktop, tablet, and mobile

## Integration with Streamflow Analyzer

This dashboard integrates with the existing `streamflow_analyzer.py` tool, providing:
- **StreamflowData Class**: Standardized data handling
- **StreamflowVisualizer Class**: Water year plot generation
- **Statistical Analysis**: Percentiles, flow statistics, comparisons
- **Water Year Focus**: October 1 - September 30 plotting

## Troubleshooting

### Common Issues

1. **No gauges loading**: 
   - Check internet connection
   - Try clearing cache with "Clear Cache" button
   - Refresh gauges with "Refresh Gauges" button

2. **Slow performance**:
   - Reduce number of states in filter
   - Increase minimum years of record filter
   - Clear cache to remove old data

3. **Plot not loading**:
   - Selected gauge may have no data available
   - Try a different gauge with more years of record
   - Check console for error messages

4. **Import errors**:
   - Ensure you're in the correct directory
   - Run: `pip install -r requirements.txt`
   - Verify streamflow_analyzer.py exists in parent directory

### Data Issues
- **Missing data**: Some USGS gauges may have data gaps
- **Provisional data**: Recent data may be provisional/unreviewed
- **Network timeouts**: Large data requests may timeout - try shorter time periods

## Development

### Running in Development Mode
```bash
# Enable debug mode for development
python app.py
```

### Adding New Features
- **Components**: Add new UI components in `components/`
- **Data Sources**: Extend `data_manager.py` for additional data
- **Visualizations**: Add plot types in `viz_manager.py`
- **Configuration**: Update `utils/config.py` for new settings

### Testing
```bash
# Test individual components
python -m components.data_manager
python -m components.map_component
python -m components.viz_manager
```

## Dependencies

### Core Framework
- **Dash 2.14+**: Web application framework
- **Plotly 5.15+**: Interactive plotting library
- **Dash Bootstrap Components**: UI components

### Data Processing  
- **Pandas 2.0+**: Data manipulation
- **NumPy 1.24+**: Numerical computing
- **dataretrieval 1.0.10+**: USGS data access

### Database
- **SQLite3**: Built-in caching database (no installation required)

## License

This project builds on USGS public data and open-source Python libraries. The dashboard code is provided as-is for educational and research purposes.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the configuration options
3. Check that all dependencies are installed
4. Verify internet connectivity for USGS data access

## Acknowledgments

- **USGS**: United States Geological Survey for streamflow data
- **dataretrieval**: Official Python library for USGS data access
- **Plotly/Dash**: Interactive web application framework
- **Bootstrap**: UI component library

---

**Quick Start**: `./run_dashboard.sh` → Open http://localhost:8050 → Click on any gauge → Analyze streamflow data!
