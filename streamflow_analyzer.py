"""
USGS Streamflow Analysis and Visualization Tool

A comprehensive toolkit for analyzing and visualizing streamflow data from USGS gauges.
Supports water year analysis, statistical calculations, and interactive plotting.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import dataretrieval.nwis as nwis
from datetime import datetime, timedelta
import warnings
from typing import Optional, List, Dict, Tuple, Union
import calendar

__version__ = "1.0.0"
__author__ = "USGS Streamflow Analysis Tool"


class StreamflowData:
    """
    A class for handling USGS streamflow data acquisition, processing, and statistical analysis.
    
    This class provides methods to fetch data from USGS NWIS using the dataretrieval library,
    process the data for water year analysis, and compute comprehensive statistics.
    """
    
    def __init__(self, site_id: Optional[str] = None, csv_path: Optional[str] = None, 
                 start_date: Optional[str] = None, end_date: Optional[str] = None, 
                 parameter_code: str = '00060', dataframe: Optional[pd.DataFrame] = None,
                 metadata: Optional[pd.DataFrame] = None, date_column: str = 'datetime',
                 value_column: str = 'value'):
        """
        Initialize StreamflowData object.
        
        Parameters:
        -----------
        site_id : str, optional
            USGS site number (e.g., '09380000')
        csv_path : str, optional
            Path to CSV file with streamflow data
        start_date : str, optional
            Start date in 'YYYY-MM-DD' format
        end_date : str, optional
            End date in 'YYYY-MM-DD' format
        parameter_code : str, default '00060'
            USGS parameter code ('00060' = discharge in cfs)
        dataframe : pd.DataFrame, optional
            Pre-loaded dataframe with streamflow data
        metadata : pd.DataFrame, optional
            Metadata associated with the dataframe
        date_column : str, default 'datetime'
            Name of date column when loading from CSV
        value_column : str, default 'value'
            Name of value column when loading from CSV
        """
        self.site_id = site_id
        self.parameter_code = parameter_code
        self.start_date = start_date
        self.end_date = end_date
        
        # Initialize data containers
        self._df = None
        self._metadata = None
        self._site_info = None
        self._daily_stats = None
        self._monthly_stats = None
        self._annual_stats = None
        self._water_years = None
        
        # Load data based on provided inputs
        if dataframe is not None:
            self._df = dataframe.copy()
            self._metadata = metadata
            self._process_data()
        elif csv_path:
            self.load_from_csv(csv_path, date_column=date_column, value_column=value_column)
        elif site_id and start_date and end_date:
            self.fetch_usgs_data(site_id, start_date, end_date, parameter_code=parameter_code)
    
    def fetch_usgs_data(self, site_id: str, start_date: str, end_date: str, 
                       service: str = 'dv', parameter_code: str = '00060') -> None:
        """
        Fetch streamflow data from USGS NWIS using dataretrieval.
        
        Parameters:
        -----------
        site_id : str
            USGS site number
        start_date : str
            Start date in 'YYYY-MM-DD' format
        end_date : str
            End date in 'YYYY-MM-DD' format
        service : str, default 'dv'
            NWIS service ('dv' = daily values, 'iv' = instantaneous values)
        parameter_code : str, default '00060'
            USGS parameter code
        """
        try:
            print(f"Fetching data for site {site_id} from {start_date} to {end_date}")
            
            # Fetch streamflow data
            result = nwis.get_record(sites=site_id, service=service, 
                                   start=start_date, end=end_date, 
                                   parameterCd=parameter_code)
            
            # Handle different return formats from dataretrieval
            if isinstance(result, tuple) and len(result) == 2:
                df, md = result
            elif isinstance(result, pd.DataFrame):
                df = result
                md = None
            else:
                raise ValueError(f"Unexpected return format from dataretrieval: {type(result)}")
            
            if df.empty:
                raise ValueError(f"No data returned for site {site_id}")
            
            self._df = df
            self._metadata = md
            self.site_id = site_id
            self.parameter_code = parameter_code
            
            # Get site information
            self._fetch_site_info()
            
            # Process the data
            self._process_data()
            
            print(f"Successfully loaded {len(self._df)} records")
            
        except Exception as e:
            raise ValueError(f"Error fetching data from USGS: {str(e)}")
    
    def _fetch_site_info(self) -> None:
        """Fetch site metadata from USGS."""
        try:
            site_info = nwis.get_record(sites=self.site_id, service='site')
            self._site_info = site_info
        except Exception as e:
            warnings.warn(f"Could not fetch site info: {str(e)}")
            self._site_info = None
    
    def load_from_csv(self, file_path: str, date_column: str = 'datetime', 
                     value_column: str = 'value') -> None:
        """
        Load streamflow data from CSV file.
        
        Parameters:
        -----------
        file_path : str
            Path to CSV file
        date_column : str, default 'datetime'
            Name of date column
        value_column : str, default 'value'
            Name of discharge value column
        """
        try:
            df = pd.read_csv(file_path)
            
            # Standardize column names
            df = df.rename(columns={date_column: 'datetime', value_column: 'value'})
            
            # Convert to datetime
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Convert values to numeric
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            
            self._df = df
            self._process_data()
            
            print(f"Successfully loaded {len(self._df)} records from CSV")
            
        except Exception as e:
            raise ValueError(f"Error loading CSV file: {str(e)}")
    
    def _process_data(self) -> None:
        """Process the raw data for analysis."""
        if self._df is None:
            return
        
        # Ensure datetime column exists and is proper datetime
        if 'datetime' not in self._df.columns:
            # Try common datetime column names
            datetime_cols = [col for col in self._df.columns if 'date' in col.lower() or 'time' in col.lower()]
            if datetime_cols:
                self._df = self._df.rename(columns={datetime_cols[0]: 'datetime'})
            else:
                raise ValueError("No datetime column found in data")
        
        self._df['datetime'] = pd.to_datetime(self._df['datetime'])
        
        # Ensure value column exists
        if 'value' not in self._df.columns:
            # Look for numeric columns that might be discharge
            numeric_cols = self._df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                self._df = self._df.rename(columns={numeric_cols[0]: 'value'})
            else:
                raise ValueError("No value column found in data")
        
        # Remove duplicates and sort
        self._df = self._df.drop_duplicates(subset=['datetime']).sort_values('datetime')
        
        # Calculate water year components
        self.calculate_water_year()
        
        # Calculate day of water year
        self.calculate_day_of_water_year()
    
    def calculate_water_year(self) -> None:
        """Calculate water year for each date (Oct 1 - Sep 30)."""
        if self._df is None:
            return
        
        # Water year starts Oct 1, so if month >= 10, water year = calendar year + 1
        self._df['water_year'] = self._df['datetime'].dt.year
        self._df.loc[self._df['datetime'].dt.month >= 10, 'water_year'] += 1
        
        # Also add calendar year, month, day for convenience
        self._df['year'] = self._df['datetime'].dt.year
        self._df['month'] = self._df['datetime'].dt.month
        self._df['day'] = self._df['datetime'].dt.day
    
    def calculate_day_of_water_year(self) -> None:
        """Calculate day of water year (1-365/366) for each date."""
        if self._df is None:
            return
        
        def get_water_year_day(row):
            date = row['datetime']
            water_year = row['water_year']
            
            # Water year starts October 1 of previous calendar year
            wy_start = datetime(water_year - 1, 10, 1)
            
            # Calculate days since start of water year
            delta = date - wy_start
            return delta.days + 1
        
        self._df['day_of_water_year'] = self._df.apply(get_water_year_day, axis=1)
        
        # Create month-day string for easier grouping (MM-DD format)
        self._df['month_day'] = self._df['datetime'].dt.strftime('%m-%d')
    
    def compute_statistics(self) -> None:
        """Compute comprehensive statistics for the streamflow data."""
        if self._df is None:
            return
        
        # Daily statistics (across all years for each day of water year)
        daily_stats = self._df.groupby('day_of_water_year')['value'].agg([
            'count', 'mean', 'median', 'std', 'min', 'max',
            ('q10', lambda x: x.quantile(0.10)),
            ('q25', lambda x: x.quantile(0.25)),
            ('q75', lambda x: x.quantile(0.75)),
            ('q90', lambda x: x.quantile(0.90))
        ]).round(2)
        
        # Add coefficient of variation
        daily_stats['cv'] = (daily_stats['std'] / daily_stats['mean']).round(3)
        
        self._daily_stats = daily_stats
        
        # Monthly statistics
        monthly_stats = self._df.groupby('month')['value'].agg([
            'count', 'mean', 'median', 'std', 'min', 'max',
            ('q10', lambda x: x.quantile(0.10)),
            ('q25', lambda x: x.quantile(0.25)),
            ('q75', lambda x: x.quantile(0.75)),
            ('q90', lambda x: x.quantile(0.90))
        ]).round(2)
        
        # Add month names
        monthly_stats.index = [calendar.month_name[i] for i in monthly_stats.index]
        self._monthly_stats = monthly_stats
        
        # Annual statistics (by water year)
        annual_stats = self._df.groupby('water_year')['value'].agg([
            'count', 'mean', 'median', 'std', 'min', 'max', 'sum'
        ]).round(2)
        
        # Add additional annual metrics
        annual_stats['peak_flow'] = self._df.groupby('water_year')['value'].max()
        annual_stats['min_7day'] = self._df.groupby('water_year')['value'].rolling(7, center=True).mean().groupby('water_year').min()
        annual_stats['volume_acre_feet'] = (annual_stats['sum'] * 1.98347).round(0)  # cfs-days to acre-feet
        
        self._annual_stats = annual_stats
    
    def filter_by_years(self, start_year: int, end_year: int) -> 'StreamflowData':
        """
        Filter data by water year range and return new StreamflowData object.
        
        Parameters:
        -----------
        start_year : int
            Starting water year
        end_year : int
            Ending water year
            
        Returns:
        --------
        StreamflowData
            New object with filtered data
        """
        if self._df is None:
            raise ValueError("No data available to filter")
        
        filtered_df = self._df[
            (self._df['water_year'] >= start_year) & 
            (self._df['water_year'] <= end_year)
        ].copy()
        
        # Create new object with filtered data
        new_obj = StreamflowData(dataframe=filtered_df, metadata=self._metadata)
        new_obj.site_id = self.site_id
        new_obj.parameter_code = self.parameter_code
        new_obj._site_info = self._site_info
        
        return new_obj
    
    def detect_data_quality_issues(self) -> Dict:
        """
        Detect potential data quality issues.
        
        Returns:
        --------
        dict
            Dictionary containing quality assessment results
        """
        if self._df is None:
            return {}
        
        issues = {
            'total_records': len(self._df),
            'missing_values': self._df['value'].isna().sum(),
            'negative_values': (self._df['value'] < 0).sum(),
            'zero_values': (self._df['value'] == 0).sum(),
            'duplicate_dates': self._df['datetime'].duplicated().sum(),
            'data_gaps': [],
            'potential_outliers': []
        }
        
        # Find data gaps (missing days)
        date_range = pd.date_range(start=self._df['datetime'].min(), 
                                 end=self._df['datetime'].max(), freq='D')
        missing_dates = date_range.difference(self._df['datetime'])
        if len(missing_dates) > 0:
            issues['data_gaps'] = missing_dates[:10].tolist()  # Show first 10
        
        # Find potential outliers (values > 3 standard deviations from mean)
        if len(self._df) > 10:
            mean_val = self._df['value'].mean()
            std_val = self._df['value'].std()
            outliers = self._df[abs(self._df['value'] - mean_val) > 3 * std_val]
            if len(outliers) > 0:
                issues['potential_outliers'] = len(outliers)
        
        return issues
    
    # Properties
    @property
    def daily_stats(self) -> pd.DataFrame:
        """Get daily statistics (computed on first access)."""
        if self._daily_stats is None:
            self.compute_statistics()
        return self._daily_stats
    
    @property
    def monthly_stats(self) -> pd.DataFrame:
        """Get monthly statistics (computed on first access)."""
        if self._monthly_stats is None:
            self.compute_statistics()
        return self._monthly_stats
    
    @property
    def annual_stats(self) -> pd.DataFrame:
        """Get annual statistics (computed on first access)."""
        if self._annual_stats is None:
            self.compute_statistics()
        return self._annual_stats
    
    @property
    def water_years(self) -> List[int]:
        """Get list of available water years."""
        if self._df is None:
            return []
        return sorted(self._df['water_year'].unique().tolist())
    
    @property
    def site_info(self) -> pd.DataFrame:
        """Get USGS site information."""
        return self._site_info
    
    @property
    def data(self) -> pd.DataFrame:
        """Get the processed data."""
        return self._df
    
    def export_statistics(self, filename: str) -> None:
        """Export statistics to CSV file."""
        with pd.ExcelWriter(filename.replace('.csv', '.xlsx')) as writer:
            if self._daily_stats is not None:
                self._daily_stats.to_excel(writer, sheet_name='Daily_Stats')
            if self._monthly_stats is not None:
                self._monthly_stats.to_excel(writer, sheet_name='Monthly_Stats')
            if self._annual_stats is not None:
                self._annual_stats.to_excel(writer, sheet_name='Annual_Stats')
        
        print(f"Statistics exported to {filename.replace('.csv', '.xlsx')}")


class StreamflowVisualizer:
    """
    A class for creating interactive visualizations of streamflow data using Plotly.
    
    This class provides methods to create various types of plots including stacked line plots
    for water year comparison, flow duration curves, and statistical summaries.
    """
    
    def __init__(self, streamflow_data: StreamflowData):
        """
        Initialize StreamflowVisualizer.
        
        Parameters:
        -----------
        streamflow_data : StreamflowData
            StreamflowData object containing processed streamflow data
        """
        self.data = streamflow_data
        self.color_schemes = {
            'viridis': px.colors.sequential.Viridis,
            'plasma': px.colors.sequential.Plasma,
            'blues': px.colors.sequential.Blues,
            'reds': px.colors.sequential.Reds,
            'greens': px.colors.sequential.Greens,
            'colorblind': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                          '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        }
    
    def create_stacked_line_plot(self, **kwargs) -> go.Figure:
        """
        Create an interactive stacked line plot showing multiple water years.
        
        Parameters:
        -----------
        **kwargs : dict
            Configuration options for the plot
            
        Returns:
        --------
        plotly.graph_objects.Figure
            Interactive Plotly figure
        """
        # Default configuration
        config = {
            'show_mean': True,
            'show_median': True,
            'percentile_bands': [25, 75],
            'highlight_years': [],
            'color_scheme': 'colorblind',
            'line_alpha': 0.3,
            'figure_size': (12, 8),
            'y_axis_scale': 'linear',
            'title': f'Streamflow Analysis - USGS Site {self.data.site_id}',
            'show_individual_years': True,
            'line_width': 1.0,
            'highlighted_line_width': 2.5
        }
        config.update(kwargs)
        
        # Create figure
        fig = go.Figure()
        
        # Get data for plotting
        df = self.data.data
        
        if df is None or df.empty:
            raise ValueError("No data available for plotting")
        
        # Create pivot table for water year comparison
        pivot_data = df.pivot_table(
            index='day_of_water_year', 
            columns='water_year', 
            values='value', 
            aggfunc='mean'
        )
        
        # Get statistics
        daily_stats = self.data.daily_stats
        
        # Add percentile bands first (so they appear behind lines)
        if config['percentile_bands']:
            self._add_percentile_bands(fig, daily_stats, config['percentile_bands'])
        
        # Add individual year lines
        if config['show_individual_years']:
            highlighted_years = config.get('highlight_years', [])
            colors = self._get_colors(config['color_scheme'], len(pivot_data.columns))
            
            for i, year in enumerate(pivot_data.columns):
                if year in highlighted_years:
                    # Highlighted years with thicker lines and specific colors
                    highlight_color = colors[highlighted_years.index(year) % len(colors)]
                    fig.add_trace(go.Scatter(
                        x=pivot_data.index,
                        y=pivot_data[year],
                        mode='lines',
                        name=f'WY {year}',
                        line=dict(color=highlight_color, width=config['highlighted_line_width']),
                        hovertemplate='<b>WY %{fullData.name}</b><br>' +
                                    'Day of WY: %{x}<br>' +
                                    'Discharge: %{y:.1f} cfs<extra></extra>'
                    ))
                else:
                    # Regular years with thin, transparent lines
                    fig.add_trace(go.Scatter(
                        x=pivot_data.index,
                        y=pivot_data[year],
                        mode='lines',
                        name=f'WY {year}',
                        line=dict(color='lightgray', width=config['line_width']),
                        opacity=config['line_alpha'],
                        showlegend=False,
                        hovertemplate='<b>WY %{fullData.name}</b><br>' +
                                    'Day of WY: %{x}<br>' +
                                    'Discharge: %{y:.1f} cfs<extra></extra>'
                    ))
        
        # Add statistical lines
        if config['show_mean']:
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['mean'],
                mode='lines',
                name='Mean',
                line=dict(color='black', width=2, dash='dash'),
                hovertemplate='<b>Mean</b><br>' +
                            'Day of WY: %{x}<br>' +
                            'Discharge: %{y:.1f} cfs<extra></extra>'
            ))
        
        if config['show_median']:
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['median'],
                mode='lines',
                name='Median',
                line=dict(color='red', width=2, dash='dot'),
                hovertemplate='<b>Median</b><br>' +
                            'Day of WY: %{x}<br>' +
                            'Discharge: %{y:.1f} cfs<extra></extra>'
            ))
        
        # Customize layout
        self._customize_layout(fig, config)
        
        return fig
    
    def _add_percentile_bands(self, fig: go.Figure, daily_stats: pd.DataFrame, 
                            percentiles: List[int]) -> None:
        """Add percentile bands to the figure."""
        if len(percentiles) != 2:
            return
        
        lower_p, upper_p = sorted(percentiles)
        lower_col = f'q{lower_p:02d}'
        upper_col = f'q{upper_p:02d}'
        
        if lower_col in daily_stats.columns and upper_col in daily_stats.columns:
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats[upper_col],
                mode='lines',
                line=dict(color='lightblue', width=0),
                showlegend=False,
                hoverinfo='skip'
            ))
            
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats[lower_col],
                mode='lines',
                fill='tonexty',
                fillcolor='rgba(173, 216, 230, 0.3)',
                line=dict(color='lightblue', width=0),
                name=f'{lower_p}th-{upper_p}th Percentile',
                hovertemplate=f'<b>{lower_p}th-{upper_p}th Percentile</b><br>' +
                            'Day of WY: %{x}<br>' +
                            f'{lower_p}th: ' + '%{y:.1f} cfs<extra></extra>'
            ))
    
    def _get_colors(self, color_scheme: str, n_colors: int) -> List[str]:
        """Get color palette for plotting."""
        if color_scheme in self.color_schemes:
            colors = self.color_schemes[color_scheme]
            if len(colors) >= n_colors:
                return colors[:n_colors]
            else:
                # Repeat colors if needed
                return (colors * ((n_colors // len(colors)) + 1))[:n_colors]
        else:
            # Default to colorblind-friendly palette
            return self.color_schemes['colorblind']
    
    def _customize_layout(self, fig: go.Figure, config: dict) -> None:
        """Customize the figure layout."""
        # Create custom x-axis labels for water year dates
        # Day 1 = Oct 1, Day 32 = Nov 1, etc.
        tick_vals = [1, 32, 62, 93, 124, 155, 185, 216, 247, 277, 308, 339]
        tick_labels = ['Oct 1', 'Nov 1', 'Dec 1', 'Jan 1', 'Feb 1', 'Mar 1', 
                      'Apr 1', 'May 1', 'Jun 1', 'Jul 1', 'Aug 1', 'Sep 1']
        
        fig.update_layout(
            title={
                'text': config['title'],
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16}
            },
            xaxis=dict(
                title='Water Year',
                tickvals=tick_vals,
                ticktext=tick_labels,
                showgrid=True,
                gridwidth=1,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title='Discharge (cfs)',
                type=config['y_axis_scale'],
                showgrid=True,
                gridwidth=1,
                gridcolor='lightgray'
            ),
            width=config['figure_size'][0] * 80,
            height=config['figure_size'][1] * 80,
            hovermode='x unified',
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.01
            ),
            margin=dict(r=150)  # Make room for legend
        )
    
    def create_flow_duration_curve(self, water_years: Optional[List[int]] = None) -> go.Figure:
        """
        Create a flow duration curve showing exceedance probabilities.
        
        Parameters:
        -----------
        water_years : List[int], optional
            Specific water years to include
            
        Returns:
        --------
        plotly.graph_objects.Figure
            Interactive Plotly figure
        """
        df = self.data.data
        
        if water_years:
            df = df[df['water_year'].isin(water_years)]
        
        # Calculate exceedance probabilities
        sorted_flows = np.sort(df['value'].dropna())[::-1]  # Sort descending
        exceedance = np.arange(1, len(sorted_flows) + 1) / len(sorted_flows) * 100
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=exceedance,
            y=sorted_flows,
            mode='lines',
            name='Flow Duration Curve',
            line=dict(color='blue', width=2),
            hovertemplate='<b>Flow Duration Curve</b><br>' +
                        'Exceedance: %{x:.1f}%<br>' +
                        'Discharge: %{y:.1f} cfs<extra></extra>'
        ))
        
        fig.update_layout(
            title='Flow Duration Curve',
            xaxis_title='Exceedance Probability (%)',
            yaxis_title='Discharge (cfs)',
            yaxis_type='log',
            showlegend=True
        )
        
        return fig
    
    def create_monthly_comparison(self) -> go.Figure:
        """Create a monthly comparison boxplot."""
        df = self.data.data
        
        fig = go.Figure()
        
        months = ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 
                 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
        
        for i, month_num in enumerate([10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]):
            month_data = df[df['month'] == month_num]['value']
            
            fig.add_trace(go.Box(
                y=month_data,
                name=months[i],
                boxpoints='outliers'
            ))
        
        fig.update_layout(
            title='Monthly Streamflow Distribution',
            xaxis_title='Month (Water Year Order)',
            yaxis_title='Discharge (cfs)',
            showlegend=False
        )
        
        return fig
    
    def create_annual_summary(self) -> go.Figure:
        """Create annual summary plot with multiple metrics."""
        annual_stats = self.data.annual_stats
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Annual Mean Flow', 'Annual Peak Flow', 
                          'Annual Minimum Flow', 'Annual Volume'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Annual mean
        fig.add_trace(
            go.Scatter(x=annual_stats.index, y=annual_stats['mean'], 
                      mode='lines+markers', name='Mean Flow'),
            row=1, col=1
        )
        
        # Annual peak
        fig.add_trace(
            go.Scatter(x=annual_stats.index, y=annual_stats['peak_flow'], 
                      mode='lines+markers', name='Peak Flow'),
            row=1, col=2
        )
        
        # Annual minimum
        fig.add_trace(
            go.Scatter(x=annual_stats.index, y=annual_stats['min'], 
                      mode='lines+markers', name='Min Flow'),
            row=2, col=1
        )
        
        # Annual volume
        if 'volume_acre_feet' in annual_stats.columns:
            fig.add_trace(
                go.Scatter(x=annual_stats.index, y=annual_stats['volume_acre_feet'], 
                          mode='lines+markers', name='Volume'),
                row=2, col=2
            )
        
        fig.update_layout(
            title='Annual Streamflow Summary',
            showlegend=False,
            height=600
        )
        
        return fig


# Convenience function for loading CSV data
def load_csv_data(file_path: str, date_column: str = 'dateTime', 
                 value_column: str = 'value') -> StreamflowData:
    """
    Convenience function to load CSV data with custom column names.
    
    Parameters:
    -----------
    file_path : str
        Path to CSV file
    date_column : str, default 'dateTime'
        Name of date column in CSV
    value_column : str, default 'value'
        Name of value column in CSV
        
    Returns:
    --------
    StreamflowData
        Loaded data object
    """
    return StreamflowData(csv_path=file_path, date_column=date_column, value_column=value_column)
def quick_analysis(site_id: str, start_date: str, end_date: str, 
                  highlight_years: Optional[List[int]] = None) -> Tuple[StreamflowData, go.Figure]:
    """
    Perform quick streamflow analysis and visualization.
    
    Parameters:
    -----------
    site_id : str
        USGS site number
    start_date : str
        Start date in 'YYYY-MM-DD' format
    end_date : str
        End date in 'YYYY-MM-DD' format
    highlight_years : List[int], optional
        Water years to highlight
        
    Returns:
    --------
    Tuple[StreamflowData, plotly.graph_objects.Figure]
        Data object and interactive plot
    """
    # Load data
    data = StreamflowData(site_id=site_id, start_date=start_date, end_date=end_date)
    
    # Create visualizer
    viz = StreamflowVisualizer(data)
    
    # Create plot
    fig = viz.create_stacked_line_plot(
        highlight_years=highlight_years or [],
        show_mean=True,
        show_median=True,
        percentile_bands=[25, 75]
    )
    
    return data, fig


if __name__ == "__main__":
    print("USGS Streamflow Analysis and Visualization Tool")
    print(f"Version: {__version__}")
    print("Use StreamflowData and StreamflowVisualizer classes for analysis")
