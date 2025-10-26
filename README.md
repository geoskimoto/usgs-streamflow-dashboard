# USGS Streamflow Analysis and Visualization Tool

A comprehensive Python toolkit for analyzing and visualizing streamflow data from USGS river gauges. This tool enables water year analysis, statistical calculations, and interactive plotting with a focus on comparative analysis across multiple years.

![Streamflow Analysis Example](https://via.placeholder.com/800x400/0077be/ffffff?text=Interactive+Streamflow+Visualization)

## Features

### 🌊 **Water Year Analysis**
- Proper water year handling (October 1 - September 30)
- Day-of-water-year calculations for year-over-year comparison
- Automatic water year assignment and validation

### 📊 **Comprehensive Statistics**
- Daily statistics across all years (mean, median, percentiles)
- Monthly patterns and seasonal analysis
- Annual summaries (peaks, volumes, low flows)
- Flow duration curves and exceedance probabilities

### 📈 **Interactive Visualizations**
- Stacked line plots with multiple water years overlaid
- Percentile bands and statistical overlays
- Highlighted years with customizable styling
- Flow duration curves and monthly comparisons
- Publication-quality plots with Plotly

### 🔗 **USGS Integration**
- Direct data fetching using official `dataretrieval` library
- Support for any USGS streamflow gauge
- Built-in data quality assessment
- Site metadata retrieval

## Installation

1. **Clone or download this repository**
2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

### Required Dependencies
- `pandas` - Data manipulation
- `numpy` - Numerical computations  
- `plotly` - Interactive visualizations
- `dataretrieval` - USGS data access (official library)
- `scipy` - Statistical analysis
- `openpyxl` - Excel export

## Quick Start

### Basic Usage

```python
from streamflow_analyzer import StreamflowData, StreamflowVisualizer

# Load data from USGS
data = StreamflowData(site_id='09380000',  # Lees Ferry
                     start_date='2010-10-01', 
                     end_date='2023-09-30')

# Create visualizer and plot
viz = StreamflowVisualizer(data)
fig = viz.create_stacked_line_plot(
    highlight_years=[2012, 2018, 2023],
    show_percentile_bands=[25, 75],
    title='Colorado River at Lees Ferry'
)

# Display and save
fig.show()
fig.write_html('analysis.html')
```

### One-Line Analysis

```python
from streamflow_analyzer import quick_analysis

# Quick analysis with automatic plotting
data, fig = quick_analysis('09380000', '2020-10-01', '2023-09-30')
fig.show()
```

## Examples

### 1. Jupyter Notebook Demo
Open `StackedLinePlots_plotly.ipynb` for a complete interactive demonstration.

### 2. Command Line Example
```bash
python example_usage.py
```

### 3. Load from CSV
```python
# Load existing data file
data = StreamflowData(csv_path='leesferry_webservice.csv')

# Analyze specific years
filtered_data = data.filter_by_years(2010, 2020)
```

## Advanced Features

### Customizable Plotting
```python
fig = viz.create_stacked_line_plot(
    highlight_years=[2002, 2012, 2023],
    show_mean=True,
    show_median=True,
    percentile_bands=[10, 90],
    color_scheme='viridis',
    line_alpha=0.3,
    y_axis_scale='log'
)
```

### Statistical Analysis
```python
# Access computed statistics
print(data.annual_stats)     # Annual summaries
print(data.monthly_stats)    # Monthly patterns  
print(data.daily_stats)      # Daily statistics

# Data quality assessment
quality = data.detect_data_quality_issues()
print(quality)
```

### Multiple Visualizations
```python
# Flow duration curve
fdc_fig = viz.create_flow_duration_curve()

# Monthly comparison
monthly_fig = viz.create_monthly_comparison()

# Annual summary dashboard
annual_fig = viz.create_annual_summary()
```

## Water Year Plotting

The tool correctly handles water years for streamflow analysis:

- **Water Year Definition**: October 1 to September 30
- **X-axis**: Shows day of water year (1-365/366)
- **Year Labeling**: Water Year 2023 = Oct 1, 2022 to Sep 30, 2023
- **Seasonal Alignment**: All years align for proper comparison

This ensures that:
- Peak snowmelt (spring) appears at the same x-position across years
- Baseflow periods (late summer/fall) are properly aligned
- Seasonal patterns are clearly visible

## API Reference

### StreamflowData Class

#### Initialization
```python
StreamflowData(site_id=None, csv_path=None, start_date=None, 
               end_date=None, parameter_code='00060')
```

#### Key Methods
- `fetch_usgs_data(site_id, start_date, end_date)` - Get data from USGS
- `load_from_csv(file_path)` - Load from CSV file
- `filter_by_years(start_year, end_year)` - Filter by water year range
- `compute_statistics()` - Calculate all statistics
- `detect_data_quality_issues()` - Assess data quality
- `export_statistics(filename)` - Export to Excel

#### Properties
- `data` - Processed DataFrame
- `daily_stats` - Daily statistics across all years
- `monthly_stats` - Monthly statistics
- `annual_stats` - Annual statistics by water year
- `water_years` - Available water years
- `site_info` - USGS site metadata

### StreamflowVisualizer Class

#### Initialization
```python
StreamflowVisualizer(streamflow_data)
```

#### Key Methods
- `create_stacked_line_plot(**kwargs)` - Main visualization
- `create_flow_duration_curve()` - Flow duration analysis
- `create_monthly_comparison()` - Monthly boxplots
- `create_annual_summary()` - Multi-panel annual plots

## File Structure

```
📁 StackedLinePlots/
├── 📄 streamflow_analyzer.py      # Main analysis classes
├── 📄 requirements.txt            # Dependencies
├── 📄 example_usage.py           # Example script
├── 📄 StackedLinePlots_plotly.ipynb  # Demo notebook
├── 📄 leesferry_webservice.csv   # Sample data
├── 📄 README.md                  # This file
└── 📁 Archive/                   # Old implementation files
```

## Sample Output

The tool generates:

1. **Interactive HTML plots** with hover information and zoom/pan
2. **Excel statistics files** with daily, monthly, and annual summaries  
3. **Publication-quality figures** suitable for reports and presentations

### Plot Features
- Multiple water years overlaid on same axes
- Highlighted years with custom colors and styles
- Statistical overlays (mean, median, percentiles)
- Percentile bands showing normal ranges
- Water year x-axis (Oct 1 - Sep 30)
- Interactive hover information
- Export capabilities (HTML, PNG, SVG)

## Troubleshooting

### Common Issues

1. **Import errors**: Install required packages with `pip install -r requirements.txt`

2. **USGS data access fails**: Check internet connection and verify site ID format

3. **Date format issues**: Use 'YYYY-MM-DD' format for dates

4. **Empty plots**: Verify data exists for specified date range and site

### Data Quality

The tool automatically:
- Removes duplicate timestamps
- Flags missing or invalid values
- Identifies potential outliers
- Reports data completeness

## Contributing

This tool is designed to be extensible. Key areas for enhancement:
- Additional statistical metrics
- New visualization types
- Multi-site comparison features
- Climate correlation analysis
- Web interface development

## License

This project is in the public domain. The USGS `dataretrieval` library is also public domain.

## Acknowledgments

- **USGS dataretrieval team** for the excellent Python library
- **Plotly** for interactive visualization capabilities
- **Pandas** for data manipulation tools

## Citation

If you use this tool in research or reports, please cite the USGS dataretrieval library:

> Hodson, T.O., Hariharan, J.A., Black, S., and Horsburgh, J.S., 2023, dataretrieval (Python): a Python package for discovering and retrieving water data available from U.S. federal hydrologic web services: U.S. Geological Survey software release, https://doi.org/10.5066/P94I5TX3

---

**For questions or issues, please check the troubleshooting section or review the example files.**
