# Comprehensive Prompt for USGS Streamflow Analysis and Visualization Tool

## Project Overview
Create a robust, object-oriented Python tool for analyzing and visualizing daily streamflow data from USGS river gauges. The tool should enable users to pull data from any USGS gauge via web services, perform statistical analysis, and create interactive visualizations showing multiple water years overlaid on the same axes for comparative analysis.

## Core Requirements

### 1. Data Acquisition and Management
- **USGS Data Integration using dataretrieval**: Implement methods to fetch streamflow data using the official USGS `dataretrieval` Python library
  - Support for site number input (e.g., '09380000' for Lees Ferry)
  - Configurable date ranges and parameter codes
  - Leverage multiple NWIS services (daily values 'dv', instantaneous values 'iv', statistics 'stat', site info 'site')
  - Built-in error handling for invalid sites or network issues provided by the library
  - Access to internal USGS data when connected to USGS network (access='3')
  
- **Data Processing**:
  - Convert date strings to datetime objects
  - Handle duplicate timestamps (common with 15-minute data)
  - For sub-daily data: calculate daily means
  - Remove or flag missing/invalid data points using USGS qualifier codes
  - Support both calendar years and water years (Oct 1 - Sep 30)
  - Leverage dataretrieval's built-in data validation and quality flags

### 1.1. USGS dataretrieval Library Integration
The tool will use the official USGS `dataretrieval` Python library for all NWIS data access:

#### Available NWIS Services:
- **Daily Values ('dv')**: Daily statistical summaries (mean, min, max)
- **Instantaneous Values ('iv')**: Real-time or sub-daily measurements  
- **Statistics ('stat')**: Historical statistical summaries
- **Site Information ('site')**: Gauge metadata, location, drainage area
- **Peak Flows ('peaks')**: Annual peak discharge records
- **Discharge Measurements ('measurements')**: Field measurements
- **Water Quality ('qwdata')**: Chemical and physical water quality data

#### Key Features:
- Automatic handling of USGS data formats and metadata
- Built-in data quality indicators and qualifier codes
- Support for multiple parameter codes (discharge, stage, temperature, etc.)
- Access to both public and internal USGS data (when on USGS network)
- Robust error handling for invalid sites or date ranges

#### Example dataretrieval Usage:
```python
import dataretrieval.nwis as nwis

# Get daily discharge data
df, md = nwis.get_record(sites='09380000', service='dv', 
                        start='2020-10-01', end='2023-09-30', 
                        parameterCd='00060')

# Get site information  
site_info = nwis.get_record(sites='09380000', service='site')

# Get peak flow data
peaks = nwis.get_record(sites='09380000', service='peaks')
```

### 2. Water Year Functionality
- **Water Year Conversion**: Implement proper water year calculation where:
  - October 1st to September 30th defines a water year
  - Water year is named by the ending calendar year (e.g., WY 2023 = Oct 1, 2022 to Sep 30, 2023)
- **Day of Water Year**: Convert all dates to day-of-water-year (1-365/366) for plotting alignment

### 3. Statistical Analysis Engine
Implement comprehensive statistical calculations for streamflow data:

#### Daily Statistics (across all years for each day):
- Mean daily flow
- Median daily flow  
- Standard deviation
- Percentiles: 10th, 25th, 75th, 90th percentiles
- Minimum and maximum values
- Coefficient of variation

#### Monthly Statistics:
- Monthly mean, median, standard deviation
- Monthly volume calculations
- Seasonal patterns analysis

#### Annual Statistics:
- Annual peak flows
- Annual low flows (7-day minimum)
- Annual volumes
- Flow duration curves

#### Drought/Flood Analysis:
- Identification of extreme years
- Return period calculations
- Flow exceedance probabilities

### 4. Interactive Visualization with Plotly
Create a modern, interactive plotting system using Plotly that supports:

#### Core Plot Elements:
- **Individual Year Lines**: Each water year as a separate line trace
- **Statistical Overlays**: 
  - Mean and median lines (dashed/dotted styles)
  - Percentile bands (25th-75th, 10th-90th)
  - Standard deviation envelopes
- **Highlighted Years**: Ability to emphasize specific years with different colors/styles
- **Background Shading**: Optional percentile or standard deviation bands

#### Interactive Features:
- **Hover Information**: Show exact values, dates, and statistics on hover
- **Zoom/Pan**: Allow users to focus on specific time periods
- **Toggle Traces**: Enable/disable individual years or statistics
- **Brush Selection**: Select time periods for detailed analysis
- **Crossfilter**: Link multiple plots for coordinated views

#### Customization Options:
- Color schemes (colorblind-friendly options)
- Line styles and widths
- Axis formatting and labels
- Title and annotation customization
- Legend positioning and styling
- Export capabilities (PNG, SVG, HTML)

### 5. Object-Oriented Architecture

#### Main Classes:

**StreamflowData Class**:
```python
import dataretrieval.nwis as nwis

class StreamflowData:
    def __init__(self, site_id=None, csv_path=None, start_date=None, end_date=None, parameter_code='00060')
    # Properties
    @property
    def daily_stats(self)
    @property 
    def monthly_stats(self)
    @property
    def annual_stats(self)
    @property
    def water_years(self)
    @property
    def site_info(self)  # USGS site metadata
    
    # Methods
    def fetch_usgs_data(self, site_id, start_date, end_date, service='dv', parameter_code='00060')
    def load_from_csv(self, file_path)
    def calculate_water_year(self)
    def calculate_day_of_water_year(self)
    def compute_statistics(self)
    def filter_by_years(self, start_year, end_year)
    def detect_data_quality_issues(self)
    def get_site_metadata(self, site_id)  # Get site info using dataretrieval
```

**StreamflowVisualizer Class**:
```python
class StreamflowVisualizer:
    def __init__(self, streamflow_data)
    
    # Main plotting methods
    def create_stacked_line_plot(self, **kwargs)
    def create_flow_duration_curve(self)
    def create_monthly_comparison(self)
    def create_annual_summary(self)
    
    # Utility methods
    def add_percentile_bands(self, fig, percentiles)
    def add_statistical_lines(self, fig, stats)
    def highlight_specific_years(self, fig, years, colors)
    def customize_layout(self, fig, title, xlabel, ylabel)
```

### 6. Advanced Features

#### Data Quality Assessment:
- Identify data gaps
- Flag outliers and suspect values
- Generate data completeness reports
- Visualize data availability timelines

#### Comparative Analysis:
- Compare multiple gauge sites
- Upstream/downstream relationships
- Regional flow patterns
- Climate correlation analysis

#### Export and Reporting:
- Generate automated summary reports
- Export statistical tables to CSV/Excel
- Save high-resolution plots
- Create interactive HTML dashboards

### 7. User Interface Options

#### Jupyter Notebook Interface:
- Interactive widgets for parameter selection
- Real-time plot updates
- Integrated documentation and examples

#### Command Line Interface:
- Batch processing capabilities
- Scripted analysis workflows
- Configuration file support

#### Optional Web Dashboard:
- Streamlit or Dash-based interface
- Multi-site comparison tools
- Real-time data updates

### 8. Configuration and Customization

#### Plot Configuration:
```python
plot_config = {
    'show_mean': True,
    'show_median': True,
    'percentile_bands': [25, 75],
    'highlight_years': [2012, 2018, 2023],
    'color_scheme': 'viridis',
    'line_alpha': 0.3,
    'figure_size': (12, 8),
    'y_axis_scale': 'linear',  # or 'log'
    'date_range': ('10-01', '09-30'),
    'title': 'Streamflow Analysis for USGS Site {site_id}'
}
```

#### Statistical Configuration:
```python
stats_config = {
    'percentiles': [10, 25, 50, 75, 90],
    'rolling_window': 7,  # for smoothing
    'outlier_threshold': 3,  # standard deviations
    'minimum_years': 10,  # for statistical validity
    'water_year_start': 10  # October = month 10
}
```

### 9. Error Handling and Validation

#### Data Validation:
- Check for reasonable flow values (no negative flows) using USGS qualifier codes
- Validate date formats and ranges with dataretrieval built-in checks
- Ensure site IDs are valid USGS format (8-15 digit site numbers)
- Handle missing data appropriately using USGS data quality indicators
- Leverage dataretrieval's automatic metadata validation

#### User Input Validation:
- Validate year ranges
- Check percentile values (0-100)
- Ensure color specifications are valid
- Provide helpful error messages

### 10. Documentation and Testing

#### Documentation Requirements:
- Comprehensive docstrings for all methods
- Jupyter notebook examples and tutorials
- API reference documentation
- Best practices guide for streamflow analysis

#### Testing Requirements:
- Unit tests for all statistical calculations
- Integration tests for dataretrieval NWIS API calls
- Visual regression tests for plots
- Performance tests for large datasets
- Validation tests for USGS data quality handling

### 11. Performance Optimization

#### Efficiency Considerations:
- Lazy loading of statistical calculations
- Caching of computed statistics
- Efficient data structures for time series
- Vectorized operations using NumPy/Pandas
- Optional parallel processing for multiple sites

### 12. Dependencies and Environment

#### Required Libraries:
```python
# Core data handling
pandas>=1.5.0
numpy>=1.20.0

# USGS data acquisition (official library)
dataretrieval>=1.0.10

# Visualization
plotly>=5.0.0
matplotlib>=3.5.0  # for fallback plots

# Statistical analysis
scipy>=1.8.0
statsmodels>=0.13.0

# Optional enhancements
jupyter>=1.0.0
ipywidgets>=7.0.0
streamlit>=1.0.0  # for web interface
```

### 13. Implementation Phases

#### Phase 1: Core Functionality
1. Basic StreamflowData class with CSV import
2. Water year calculations
3. Basic statistical methods
4. Simple matplotlib plotting

#### Phase 2: USGS Integration
1. `dataretrieval` library integration for NWIS data access
2. Site metadata retrieval and validation
3. Data quality assessment tools using USGS qualifiers
4. Enhanced data processing with multiple parameter codes

#### Phase 3: Advanced Visualization
1. Plotly integration
2. Interactive features
3. Customization options
4. Export capabilities

#### Phase 4: Advanced Features
1. Multi-site comparison
2. Automated reporting
3. Web interface
4. Performance optimization

### 14. Success Criteria

The completed tool should enable users to:
- Fetch data from any USGS streamflow gauge with a single method call
- Generate publication-quality visualizations with minimal code
- Perform comprehensive statistical analysis of streamflow patterns
- Compare flow patterns across multiple years interactively
- Identify trends, extremes, and anomalies in streamflow data
- Export results in multiple formats for reports and presentations

### 15. Example Usage

```python
# Basic usage example
import dataretrieval.nwis as nwis
from streamflow_analyzer import StreamflowData, StreamflowVisualizer

# Load data from USGS using dataretrieval (Lees Ferry gauge)
data = StreamflowData(site_id='09380000', 
                     start_date='1990-10-01', 
                     end_date='2023-09-30',
                     parameter_code='00060')  # Discharge in cfs

# Alternative: Load data directly using dataretrieval
# df, md = nwis.get_record(sites='09380000', service='dv', 
#                         start='1990-10-01', end='2023-09-30', 
#                         parameterCd='00060')
# data = StreamflowData(dataframe=df, metadata=md)

# Get site information
site_info = data.site_info
print(f"Site: {site_info['station_nm'].iloc[0]}")
print(f"Drainage Area: {site_info['drain_area_va'].iloc[0]} sq mi")

# Create visualizer
viz = StreamflowVisualizer(data)

# Generate interactive plot
fig = viz.create_stacked_line_plot(
    highlight_years=[2002, 2012, 2023],
    show_percentile_bands=[25, 75],
    show_statistics=['mean', 'median'],
    title='Colorado River at Lees Ferry - Water Year Comparison'
)

# Display statistics
print(data.annual_stats)
print(data.monthly_stats)

# Export results
fig.write_html('lees_ferry_analysis.html')
data.export_statistics('lees_ferry_stats.csv')
```

This comprehensive tool will provide researchers, water managers, and analysts with a powerful, flexible platform for understanding streamflow patterns and making data-driven decisions about water resources.
