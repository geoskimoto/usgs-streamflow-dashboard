"""
Visualization Manager for USGS Streamflow Dashboard

Integrates streamflow analysis and visualization capabilities.
"""

import sys
import os
import logging
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Import the streamflow analysis tools
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)
try:
    from streamflow_analyzer import StreamflowData, StreamflowVisualizer
except ImportError:
    logger.warning("Could not import streamflow analysis tools. Creating fallback classes.")
    StreamflowData = None
    StreamflowVisualizer = None

from ..utils.config import WATER_YEAR_START, DEFAULT_PERCENTILES
from ..utils.water_year_datetime import get_water_year_handler
from ..utils.water_year_calculator import get_water_year, get_day_of_water_year


class VisualizationManager:
    """Manages visualization creation for streamflow dashboard."""
    
    def __init__(self):
        """Initialize visualization manager."""
        self.streamflow_viz = None  # Will be created when we have data
        self.current_data = None
        self.current_site_id = None
        self.wy_handler = get_water_year_handler()  # Water year datetime handler
        
    def create_streamflow_plot(self, site_id: str, streamflow_data: pd.DataFrame,
                             plot_type: str = 'water_year',
                             highlight_years: List[int] = None,
                             show_percentiles: bool = True,
                             show_statistics: bool = True,
                             data_manager=None,
                             forecast_data: pd.DataFrame = None,
                             resid_cast_data: list = None,
                             history_mode: str = "all") -> go.Figure:
        """
        Create streamflow visualization plot.
        
        Parameters:
        -----------
        site_id : str
            USGS site ID
        streamflow_data : pd.DataFrame
            Streamflow data with datetime and discharge columns
        plot_type : str
            Type of plot ('water_year', 'annual', 'monthly', 'daily')
        highlight_years : list
            Years to highlight in the plot
        show_percentiles : bool
            Whether to show percentile bands
        show_statistics : bool
            Whether to show statistical overlays
            
        Returns:
        --------
        go.Figure
            Plotly figure with streamflow visualization
        """
        self.current_data = streamflow_data.copy()
        self.current_site_id = site_id
        
        # Get real-time data if data_manager is available
        realtime_data = None
        if data_manager:
            try:
                realtime_data = data_manager.get_realtime_data(site_id)
                if not realtime_data.empty:
                    logger.debug(f"Retrieved {len(realtime_data)} real-time records for visualization")
                else:
                    logger.debug(f"No real-time data available for site {site_id}")
            except Exception as e:
                logger.warning(f"Error getting real-time data: {e}")
                realtime_data = None

        # Use integrated streamflow analyzer if available
        if self.streamflow_viz and StreamflowData:
            try:
                fig = self._create_integrated_plot(
                    site_id, streamflow_data, plot_type,
                    highlight_years, show_percentiles, show_statistics, realtime_data
                )
            except Exception as e:
                logger.warning(f"Error with integrated plot, using fallback: {e}")
                fig = self._create_fallback_plot(
                    site_id, streamflow_data, plot_type, highlight_years,
                    show_percentiles, show_statistics, realtime_data,
                    forecast_data=forecast_data, history_mode=history_mode,
                )
        else:
            fig = self._create_fallback_plot(
                site_id, streamflow_data, plot_type, highlight_years,
                show_percentiles, show_statistics, realtime_data,
                forecast_data=forecast_data, history_mode=history_mode,
            )
        
        # Add NWRFC forecast overlay on water year plots (works for both integrated and fallback)
        if plot_type == 'water_year' and forecast_data:
            fig = self._add_forecast_overlay(fig, forecast_data)

        # Add ResidCast ML forecast overlay
        if plot_type == 'water_year' and resid_cast_data:
            fig = self._add_resid_cast_overlay(fig, resid_cast_data)

        # Add range slider and window buttons to water year plots
        if plot_type == 'water_year':
            current_day_of_wy = get_day_of_water_year(pd.Timestamp.now(), WATER_YEAR_START)
            fig = self._add_range_controls(fig, current_day_of_wy)
        
        return fig
    
    def _create_integrated_plot(self, site_id: str, data: pd.DataFrame,
                              plot_type: str, highlight_years: List[int],
                              show_percentiles: bool, show_statistics: bool, realtime_data: pd.DataFrame = None) -> go.Figure:
        """Create plot using integrated streamflow analysis tools."""
        
        # Prepare data for StreamflowData class
        # Assume data has columns like 'datetime' and discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        
        if value_col is None:
            # Use the first numeric column after datetime
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                value_col = numeric_cols[0]
            else:
                raise ValueError("No numeric discharge column found")
        
        # Create StreamflowData instance
        sf_data = StreamflowData(
            data=data,
            site_id=site_id,
            date_column='datetime' if 'datetime' in data.columns else data.index.name,
            value_column=value_col
        )
        
        # Create StreamflowVisualizer with the data
        streamflow_viz = StreamflowVisualizer(sf_data)
        
        # Create appropriate plot based on type
        if plot_type == 'water_year':
            # Pass the parameters correctly to create_stacked_line_plot
            config = {
                'highlight_years': highlight_years or [],
                'show_mean': show_statistics,
                'show_median': show_statistics, 
                'percentile_bands': [25, 75] if show_percentiles else [],
                'show_percentile_bands': show_percentiles
            }
            fig = streamflow_viz.create_stacked_line_plot(**config)
        elif plot_type == 'annual':
            fig = streamflow_viz.create_annual_summary()
        elif plot_type == 'monthly':
            fig = streamflow_viz.create_monthly_comparison()
        else:  # daily or default
            fig = self._create_daily_timeseries_plot(sf_data)
        
        return fig
    
    def _create_fallback_plot(self, site_id: str, data: pd.DataFrame,
                            plot_type: str, highlight_years: List[int],
                            show_percentiles: bool = True,
                            show_statistics: bool = True, realtime_data: pd.DataFrame = None,
                            forecast_data: pd.DataFrame = None,
                            history_mode: str = "all") -> go.Figure:
        """
        Create basic fallback plot when integrated tools aren't available.
        Robust date handling:
        - Only set index to a valid date column ('datetime', 'date', 'timestamp').
        - If no valid date column exists, skip plotting and show error.
        - Never convert a pure integer index to datetime.
        - Documented logic and debug output for expected behavior.
        """
        # Make a copy to avoid modifying the original data
        data = data.copy()
        
        # Get discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        if value_col is None:
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                value_col = numeric_cols[0]
            else:
                return self._create_error_plot("No discharge data found")
        # Robust date column check
        date_col = None
        for col in data.columns:
            if col.lower() in ['datetime', 'date', 'dates', 'timestamp']:
                date_col = col
                break
        if date_col:
            # Try to set index to date column
            try:
                data[date_col] = pd.to_datetime(data[date_col], errors='coerce')
                data = data.set_index(date_col)
            except Exception as e:
                logger.error(f"Failed to set index to date column '{date_col}': {e}")
                return self._create_error_plot(f"Failed to parse date column '{date_col}' for plotting.")
        elif not isinstance(data.index, pd.DatetimeIndex):
            # No valid date column, do NOT convert integer index to datetime
            logger.error("No valid date column found. Cannot plot. Returning error plot.")
            return self._create_error_plot("No valid date column found for plotting.")
        # Remove timezone info to avoid mixing issues
        if hasattr(data.index, 'tz') and data.index.tz is not None:
            data.index = data.index.tz_localize(None)
        # Remove any rows with invalid dates
        data = data.dropna()
        fig = go.Figure()
        if plot_type == 'water_year':
            # Use the internal enhanced water year plot method
            fig = self._create_enhanced_water_year_plot(
                data, value_col, highlight_years,
                show_percentiles=True,
                show_statistics=True,
                realtime_data=realtime_data,
                forecast_data=forecast_data,
                history_mode=history_mode,
            )
        else:
            fig = self._create_basic_timeseries_plot(data, value_col)
            
            # Add real-time data overlay for non-water-year plots
            if realtime_data is not None and not realtime_data.empty:
                fig = self._add_realtime_overlay(fig, realtime_data, site_id)
        # Update layout (only for non-water year plots since water year handler manages its own)
        if plot_type != 'water_year':
            fig.update_layout(
                title=f"Streamflow Data - Site {site_id}",
                xaxis_title="Date",
                yaxis_title="Discharge (cfs)",
                height=500,
                showlegend=True
            )
        return fig
    
    def _day_of_wy_to_monthday(self, day_of_wy: int) -> str:
        """Convert day of water year to month-day string (e.g., Jan 1)."""
        # Water year starts Oct 1
        wy_start = pd.Timestamp(year=2000, month=10, day=1)  # 2000 is arbitrary non-leap year
        date = wy_start + pd.Timedelta(days=day_of_wy - 1)
        return date.strftime('%b %-d')
    
    def _create_basic_water_year_plot(self, data: pd.DataFrame, value_col: str,
                                    highlight_years: List[int]) -> go.Figure:
        """Create basic water year plot."""
        
        # Add water year and day of water year
        data_copy = data.copy()
        
        # Ensure index is datetime
        if not isinstance(data_copy.index, pd.DatetimeIndex):
            if 'datetime' in data_copy.columns:
                data_copy = data_copy.set_index('datetime')
            else:
                # Try to convert index to datetime
                data_copy.index = pd.to_datetime(data_copy.index, errors='coerce')
        
        # Filter out any rows with invalid dates
        data_copy = data_copy.dropna()
        
        # Now safely calculate water year and day using imported functions
        data_copy['water_year'] = data_copy.index.map(lambda d: get_water_year(d, WATER_YEAR_START))
        data_copy['day_of_wy'] = data_copy.index.map(lambda d: get_day_of_water_year(d, WATER_YEAR_START))
        
        fig = go.Figure()
        
        # Get unique years
        years = sorted(data_copy['water_year'].unique())
        
        # Plot each year
        for year in years:
            year_data = data_copy[data_copy['water_year'] == year]
            
            if len(year_data) == 0:
                continue
            
            # Determine line properties  
            if highlight_years and year in highlight_years:
                # Use different colors for each highlighted year
                highlight_index = highlight_years.index(year)
                highlight_colors = ['#FF0000', '#FF8C00', '#9932CC', '#228B22', '#DC143C', 
                                  '#4169E1', '#FF1493', '#32CD32', '#FF6347', '#8A2BE2']
                color_index = highlight_index % len(highlight_colors)
                line_color = highlight_colors[color_index]
                line_width = 3
                opacity = 1.0
                showlegend = True
                name = f"WY {year}"  # Clean year only, no extra text
            else:
                line_color = 'lightblue'
                line_width = 1
                opacity = 0.6
                showlegend = False
                name = f"WY {year}"
            
            fig.add_trace(go.Scatter(
                x=year_data['day_of_wy'],
                y=year_data[value_col],
                mode='lines',
                name=name,
                line=dict(color=line_color, width=line_width),
                opacity=opacity,
                showlegend=showlegend,
                customdata=[self._day_of_wy_to_monthday(d) for d in year_data['day_of_wy']],
                hovertemplate=f"<b>Water Year {year}</b><br>" +
                            "%{customdata}<br>" +
                            "Discharge: %{y:.1f} cfs<extra></extra>"
            ))

        # Add median line if enough data
        if len(years) >= 5:
            daily_medians = data_copy.groupby('day_of_wy')[value_col].median()

            fig.add_trace(go.Scatter(
                x=daily_medians.index,
                y=daily_medians.values,
                mode='lines',
                name='Median (All Years)',
                line=dict(color='black', width=2),
                customdata=[self._day_of_wy_to_monthday(d) for d in daily_medians.index],
                hovertemplate="%{customdata}<br>Median: %{y:.1f} cfs<extra></extra>"
            ))
        
        # After adding traces, set x-axis labels
        max_day = int(data_copy['day_of_wy'].max())
        tickvals = list(range(1, max_day+1, max(1, max_day//12)))
        ticktext = [self._day_of_wy_to_monthday(d) for d in tickvals]
        fig.update_xaxes(
            tickvals=tickvals, 
            ticktext=ticktext, 
            title="Month-Day",
            type='linear'  # Force linear axis, not datetime
        )
        
        return fig
    
    def create_fast_water_year_plot(
        self,
        site_id: str,
        current_year_data: pd.DataFrame,
        statistics: pd.DataFrame,
        forecast_data=None,
        resid_cast_data: list = None,
        data_manager=None,
    ) -> go.Figure:
        """
        Render the water year plot without loading historical year traces.

        Uses pre-computed per-day-of-WY statistics (percentile bands, mean,
        median) instead of recalculating from the full record.  Only the
        current water year discharge trace is plotted, making this path
        roughly 50–100× faster than the full history render.

        Parameters
        ----------
        site_id : str
        current_year_data : pd.DataFrame
            Discharge for the current water year only.
        statistics : pd.DataFrame
            Per-day-of-WY stats with columns:
            day_of_wy, q10, q25, q50, q75, q90, mean, median.
        forecast_data : list, optional
        resid_cast_data : list, optional
        data_manager : optional
            If provided, real-time 15-min data will be fetched.
        """
        from ..utils.config import WATER_YEAR_START
        from ..utils.water_year_calculator import get_water_year, get_day_of_water_year

        fig = go.Figure()

        # ── Percentile bands from pre-computed stats ──────────────────────
        if not statistics.empty and {"q10", "q25", "q75", "q90"}.issubset(statistics.columns):
            s = statistics.sort_values("day_of_wy")

            # Outermost 3rd–97th band (lightest). Added first so the darker
            # inner bands render on top of it. Pure band — no hover, to match
            # the 10–90 / 25–75 bands.
            if {"q03", "q97"}.issubset(s.columns):
                fig.add_trace(go.Scatter(
                    x=s["day_of_wy"], y=s["q97"],
                    mode="lines", line=dict(color="rgba(173,216,230,0)"),
                    showlegend=False, name="97th pct", hoverinfo="skip",
                ))
                fig.add_trace(go.Scatter(
                    x=s["day_of_wy"], y=s["q03"],
                    mode="lines", line=dict(color="rgba(173,216,230,0)"),
                    fill="tonexty", fillcolor="rgba(173,216,230,0.24)",
                    showlegend=True, name="3rd–97th percentile", hoverinfo="skip",
                ))

            fig.add_trace(go.Scatter(
                x=s["day_of_wy"], y=s["q90"],
                mode="lines", line=dict(color="rgba(173,216,230,0)"),
                showlegend=False, name="90th pct", hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=s["day_of_wy"], y=s["q10"],
                mode="lines", line=dict(color="rgba(173,216,230,0)"),
                fill="tonexty", fillcolor="rgba(173,216,230,0.42)",
                showlegend=True, name="10th–90th percentile", hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=s["day_of_wy"], y=s["q75"],
                mode="lines", line=dict(color="rgba(100,149,237,0)"),
                showlegend=False, name="75th pct", hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=s["day_of_wy"], y=s["q25"],
                mode="lines", line=dict(color="rgba(100,149,237,0)"),
                fill="tonexty", fillcolor="rgba(100,149,237,0.56)",
                showlegend=True, name="25th–75th percentile", hoverinfo="skip",
            ))

            # Mean and median lines
            if "mean" in s.columns:
                fig.add_trace(go.Scatter(
                    x=s["day_of_wy"], y=s["mean"],
                    mode="lines", name="Long-term Mean",
                    line=dict(color="gray", width=2.5, dash="dash"),
                    customdata=[self._day_of_wy_to_monthday(d) for d in s["day_of_wy"]],
                    hovertemplate="%{customdata}<br>Mean: %{y:.1f} cfs<extra></extra>",
                ))
            if "median" in s.columns:
                fig.add_trace(go.Scatter(
                    x=s["day_of_wy"], y=s["median"],
                    mode="lines", name="Long-term Median",
                    line=dict(color="black", width=2.5, dash="solid"),
                    customdata=[self._day_of_wy_to_monthday(d) for d in s["day_of_wy"]],
                    hovertemplate="%{customdata}<br>Median: %{y:.1f} cfs<extra></extra>",
                ))

        # ── Current water year trace ───────────────────────────────────────
        if not current_year_data.empty:
            df = current_year_data.copy()

            # Normalise to DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                for col in ("datetime", "date"):
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors="coerce")
                        df = df.set_index(col)
                        break

            if isinstance(df.index, pd.DatetimeIndex):
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                df = df.dropna()

                value_col = next(
                    (c for c in df.columns if any(t in c.lower() for t in ("discharge", "flow", "00060"))),
                    df.select_dtypes(include=[np.number]).columns[0] if len(df.select_dtypes(include=[np.number]).columns) > 0 else None,
                )

                if value_col:
                    current_wy = get_water_year(pd.Timestamp.now(), WATER_YEAR_START)
                    df["day_of_wy"] = df.index.map(lambda d: get_day_of_water_year(d, WATER_YEAR_START))
                    df_sorted = df.sort_values("day_of_wy")

                    fig.add_trace(go.Scatter(
                        x=df_sorted["day_of_wy"],
                        y=df_sorted[value_col],
                        mode="lines",
                        name=f"WY {current_wy} (Current)",
                        line=dict(color="#0000FF", width=3),
                        customdata=[self._day_of_wy_to_monthday(d) for d in df_sorted["day_of_wy"]],
                        hovertemplate=(
                            f"<b>WY {current_wy}</b><br>"
                            "%{customdata}<br>"
                            "<b>Discharge: %{y:.1f} cfs</b><extra></extra>"
                        ),
                    ))

        # ── Real-time overlay ──────────────────────────────────────────────
        if data_manager is not None:
            try:
                realtime_data = data_manager.get_realtime_data(site_id)
                if not realtime_data.empty:
                    rt = realtime_data.copy()
                    for col in ("datetime", "date"):
                        if col in rt.columns:
                            rt[col] = pd.to_datetime(rt[col], errors="coerce")
                            rt = rt.set_index(col)
                            break
                    if isinstance(rt.index, pd.DatetimeIndex):
                        if rt.index.tz is not None:
                            rt.index = rt.index.tz_localize(None)
                        rt = rt.dropna()
                        rt_val_col = next(
                            (c for c in rt.columns if any(t in c.lower() for t in ("discharge", "flow", "00060"))),
                            None,
                        )
                        if rt_val_col:
                            current_wy = get_water_year(pd.Timestamp.now(), WATER_YEAR_START)
                            rt["water_year"] = rt.index.map(lambda d: get_water_year(d, WATER_YEAR_START))
                            rt["day_of_wy"] = rt.index.map(lambda d: get_day_of_water_year(d, WATER_YEAR_START))
                            rt_current = rt[rt["water_year"] == current_wy].sort_values("day_of_wy")
                            if not rt_current.empty:
                                fig.add_trace(go.Scatter(
                                    x=rt_current["day_of_wy"],
                                    y=rt_current[rt_val_col],
                                    mode="lines",
                                    name="Real-time Data",
                                    line=dict(color="#FF0000", width=2.5),
                                    customdata=[self._day_of_wy_to_monthday(d) for d in rt_current["day_of_wy"]],
                                    hovertemplate=(
                                        "<b>Real-time</b><br>"
                                        "%{customdata}<br>"
                                        "Discharge: %{y:.1f} cfs<extra></extra>"
                                    ),
                                ))
            except Exception as exc:
                logger.warning(f"Real-time overlay failed in fast plot: {exc}")

        # ── Current day vertical line ──────────────────────────────────────
        current_day_of_wy = get_day_of_water_year(pd.Timestamp.now(), WATER_YEAR_START)
        fig.add_vline(
            x=current_day_of_wy,
            line_dash="dash", line_color="red", line_width=2,
            annotation_text="Today",
            annotation_position="top",
            annotation=dict(font_size=10, font_color="red"),
        )

        # ── X-axis labels ──────────────────────────────────────────────────
        tickvals = list(range(1, 367, 30))
        ticktext = [self._day_of_wy_to_monthday(d) for d in tickvals]
        fig.update_xaxes(tickvals=tickvals, ticktext=ticktext, title="Month-Day", type="linear")

        # ── Forecast overlays ──────────────────────────────────────────────
        if forecast_data:
            fig = self._add_forecast_overlay(fig, forecast_data)
        if resid_cast_data:
            fig = self._add_resid_cast_overlay(fig, resid_cast_data)

        # ── Range controls ─────────────────────────────────────────────────
        fig = self._add_range_controls(fig, current_day_of_wy)

        return fig

    def _create_enhanced_water_year_plot(self, data: pd.DataFrame, value_col: str,
                                       highlight_years: List[int],
                                       show_percentiles: bool = True,
                                       show_statistics: bool = True,
                                       realtime_data: pd.DataFrame = None,
                                       forecast_data: pd.DataFrame = None,
                                       history_mode: str = "all") -> go.Figure:
        """
        Create enhanced water year plot with percentile bands.
        Robust date handling: Only set index to a valid date column ('datetime', 'date', 'timestamp').
        If no valid date column exists, skip plotting and show error.
        Documented logic and debug output for expected behavior.
        """
        # Debug: Log index type and sample
        logger.debug("Water Year Plot: Data index type:", type(data.index))
        logger.debug("Water Year Plot: Data index sample:", data.index[:5].tolist() if hasattr(data.index, 'tolist') else data.index)
        logger.debug("Water Year Plot: Data columns:", data.columns.tolist())
        # Check for date/datetime columns
        date_cols = [col for col in data.columns if 'date' in col.lower() or 'time' in col.lower()]
        logger.debug("Water Year Plot: Date columns:", date_cols)
        # Add water year and day of water year
        data_copy = data.copy()

        # Apply history_mode filter AFTER index is set (done below), see post-index block.
        _history_mode = history_mode  # carried into the post-index section

        # Ensure index is datetime
        # Robust date column check
        if not isinstance(data_copy.index, pd.DatetimeIndex):
            # Try to find a valid date column
            date_col = None
            for col in data_copy.columns:
                if col.lower() in ['datetime', 'date', 'dates', 'timestamp']:
                    date_col = col
                    break
            if date_col:
                logger.debug(f"Setting index to '{date_col}' column.")
                data_copy[date_col] = pd.to_datetime(data_copy[date_col], errors='coerce')
                data_copy = data_copy.set_index(date_col)
            else:
                logger.error("No valid date column found. Cannot plot Water Year. Returning error plot.")
                return self._create_error_plot("No valid date column found for Water Year plot.")
        logger.debug("After index conversion: Data index type:", type(data_copy.index))
        logger.debug("After index conversion: Data index sample:", data_copy.index[:5].tolist() if hasattr(data_copy.index, 'tolist') else data_copy.index)
        # Filter out any rows with invalid dates
        data_copy = data_copy.dropna()
        logger.debug("After dropna: Data shape:", data_copy.shape)
        # Now safely calculate water year and day using imported functions
        data_copy['water_year'] = data_copy.index.map(lambda d: get_water_year(d, WATER_YEAR_START))
        data_copy['day_of_wy'] = data_copy.index.map(lambda d: get_day_of_water_year(d, WATER_YEAR_START))
        logger.debug("Unique water_years:", data_copy['water_year'].unique())
        logger.debug("Unique day_of_wy (first 10):", data_copy['day_of_wy'].unique()[:10])
        # Debug: Check for 1970 or other default years
        if np.all(data_copy.index.year == 1970):
            logger.error("All index years are 1970! Likely a conversion issue.")
        # Debug: Log x-axis values for first year
        if len(data_copy) > 0:
            first_year = data_copy['water_year'].min()
            year_data = data_copy[data_copy['water_year'] == first_year]
            logger.debug(f"First year ({first_year}) day_of_wy sample:", year_data['day_of_wy'][:10].tolist())

        # Apply history_mode filter
        if _history_mode == "30yr":
            current_wy = get_water_year(pd.Timestamp.now(), WATER_YEAR_START)
            cutoff_wy = current_wy - 30
            data_copy = data_copy[data_copy['water_year'] >= cutoff_wy]
            logger.debug(f"history_mode=30yr: keeping WY {cutoff_wy}–{current_wy} ({len(data_copy)} rows)")

        fig = go.Figure()
        # Calculate percentile bands first (25th, 75th percentiles)
        if show_percentiles and len(data_copy) > 100:
            daily_stats = data_copy.groupby('day_of_wy')[value_col].agg([
                'median',
                lambda x: x.quantile(0.03),
                lambda x: x.quantile(0.25),
                lambda x: x.quantile(0.75),
                lambda x: x.quantile(0.10),
                lambda x: x.quantile(0.90),
                lambda x: x.quantile(0.97)
            ])
            daily_stats.columns = ['median', 'q03', 'q25', 'q75', 'q10', 'q90', 'q97']
            # Store daily stats for tooltip customization
            self._daily_stats = daily_stats

            # Outermost 3rd–97th band (lightest). Added first so the darker
            # inner bands render on top of it. Pure band — no hover.
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q97'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),
                showlegend=False,
                name='97th percentile',
                hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q03'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),
                fill='tonexty',
                fillcolor='rgba(173, 216, 230, 0.24)',
                showlegend=True,
                name='3rd-97th percentile',
                hoverinfo='skip',
            ))

            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q90'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),
                showlegend=False,
                name='90th percentile',
                hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q10'],
                mode='lines',
                line=dict(color='rgba(173, 216, 230, 0)'),
                fill='tonexty',
                fillcolor='rgba(173, 216, 230, 0.42)',
                showlegend=True,
                name='10th-90th percentile',
                hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q75'],
                mode='lines',
                line=dict(color='rgba(100, 149, 237, 0)'),
                showlegend=False,
                name='75th percentile',
                hoverinfo='skip',
            ))
            fig.add_trace(go.Scatter(
                x=daily_stats.index,
                y=daily_stats['q25'],
                mode='lines',
                line=dict(color='rgba(100, 149, 237, 0)'),
                fill='tonexty',
                fillcolor='rgba(100, 149, 237, 0.56)',
                showlegend=True,
                name='25th-75th percentile',
                hoverinfo='skip',
            ))
        # Get unique years
        years = sorted(data_copy['water_year'].unique())
        logger.debug("Years to plot:", years)
        
        # Get current water year
        current_wy = get_water_year(pd.Timestamp.now(), WATER_YEAR_START)
        
        # Define colors for highlighted years (excluding current water year)
        highlight_colors = [
            '#FF8C00',  # Dark Orange  
            '#9932CC',  # Dark Orchid
            '#228B22',  # Forest Green
            '#DC143C',  # Crimson
            '#FF1493',  # Deep Pink
            '#32CD32',  # Lime Green
            '#FF6347',  # Tomato
            '#8A2BE2'   # Blue Violet
        ]
        
        # Plot each year
        # Track if we've shown the "All Historical Years" legend
        shown_historical_legend = False
        
        for i, year in enumerate(years):
            year_data = data_copy[data_copy['water_year'] == year]
            if len(year_data) == 0:
                continue
            # Debug: Log x and y sample for this year
            logger.debug(f"Plotting year {year}: day_of_wy sample:", year_data['day_of_wy'][:10].tolist())
            logger.debug(f"Plotting year {year}: discharge sample:", year_data[value_col][:10].tolist())
            
            # Determine line properties
            if year == current_wy:
                # Current water year is BLUE
                line_color = '#0000FF'  # Blue
                line_width = 3
                opacity = 1.0
                showlegend = True
                name = f"WY {year} (Current)"
                legendgroup = None
                trace_visible = True
            elif highlight_years and year in highlight_years:
                # Other highlighted years (not current) get different colors
                highlight_index = highlight_years.index(year)
                color_index = highlight_index % len(highlight_colors)
                line_color = highlight_colors[color_index]
                line_width = 3
                opacity = 1.0
                showlegend = True
                name = f"WY {year}"
                legendgroup = None
                trace_visible = True
            else:
                # All other historical years grouped together
                line_color = 'lightgray'
                line_width = 1
                opacity = 0.4
                showlegend = not shown_historical_legend  # Only show legend for first historical year
                name = "All Historical Years"
                legendgroup = "historical"
                shown_historical_legend = True
                # Default the historical years to hidden; users can toggle
                # them on via the legend entry.
                trace_visible = 'legendonly'
            
            # Create custom data for tooltip: [q90, q75, median, q25, q10, month_day]
            customdata = []
            for day in year_data['day_of_wy']:
                month_day = self._day_of_wy_to_monthday(day)
                if show_percentiles and hasattr(self, '_daily_stats') and day in self._daily_stats.index:
                    stats = self._daily_stats.loc[day]
                    customdata.append([
                        stats['q90'],
                        stats['q75'],
                        stats['median'],
                        stats['q25'],
                        stats['q10'],
                        month_day,
                    ])
                else:
                    customdata.append([None, None, None, None, None, month_day])

            hovertemplate = (
                f"<b>WY {year}</b><br>"
                "%{customdata[5]}<br>"
                "<b>Discharge: %{y:.1f} cfs</b><br>"
            )
            if show_percentiles:
                hovertemplate += (
                    "<br>"
                    "90th percentile: %{customdata[0]:.1f} cfs<br>"
                    "75th percentile: %{customdata[1]:.1f} cfs<br>"
                    "Median: %{customdata[2]:.1f} cfs<br>"
                    "25th percentile: %{customdata[3]:.1f} cfs<br>"
                    "10th percentile: %{customdata[4]:.1f} cfs"
                )
            hovertemplate += "<extra></extra>"

            trace = go.Scatter(
                x=year_data['day_of_wy'],
                y=year_data[value_col],
                mode='lines',
                name=name,
                line=dict(color=line_color, width=line_width),
                opacity=opacity,
                showlegend=showlegend,
                visible=trace_visible,
                customdata=customdata,
                hovertemplate=hovertemplate
            )
            
            # Add legendgroup for historical years
            if legendgroup:
                trace.legendgroup = legendgroup
                
            fig.add_trace(trace)
        
        # Add median and mean lines LAST so they appear on top of all year traces
        if show_statistics and len(data_copy) > 50:
            daily_median = data_copy.groupby('day_of_wy')[value_col].median()
            daily_mean = data_copy.groupby('day_of_wy')[value_col].mean()
            
            # Add median line (black, solid)
            fig.add_trace(go.Scatter(
                x=daily_median.index,
                y=daily_median.values,
                mode='lines',
                name='Long-term Median',
                line=dict(color='black', width=2.5, dash='solid'),
                customdata=[self._day_of_wy_to_monthday(d) for d in daily_median.index],
                hovertemplate="%{customdata}<br>Median: %{y:.1f} cfs<extra></extra>"
            ))

            # Add mean line (gray, dashed)
            fig.add_trace(go.Scatter(
                x=daily_mean.index,
                y=daily_mean.values,
                mode='lines',
                name='Long-term Mean',
                line=dict(color='gray', width=2.5, dash='dash'),
                customdata=[self._day_of_wy_to_monthday(d) for d in daily_mean.index],
                hovertemplate="%{customdata}<br>Mean: %{y:.1f} cfs<extra></extra>"
            ))
        
        # Add current date vertical line
        current_date = pd.Timestamp.now()
        current_day_of_wy = get_day_of_water_year(current_date, WATER_YEAR_START)
        
        fig.add_vline(
            x=current_day_of_wy,
            line_dash="dash",
            line_color="red",
            line_width=2,
            annotation_text="Current Day",
            annotation_position="top",
            annotation=dict(
                font_size=10,
                font_color="red"
            )
        )
        
        # Add realtime data if available
        if realtime_data is not None and not realtime_data.empty:
            # Find the discharge column in real-time data
            rt_value_col = None
            for col in realtime_data.columns:
                if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                    rt_value_col = col
                    break
            
            if rt_value_col is not None:
                # Prepare realtime data
                rt_data = realtime_data.copy()
                if not isinstance(rt_data.index, pd.DatetimeIndex):
                    # Try to find a date column
                    date_col = None
                    for col in rt_data.columns:
                        if col.lower() in ['datetime', 'date', 'dates', 'timestamp']:
                            date_col = col
                            break
                    if date_col:
                        rt_data[date_col] = pd.to_datetime(rt_data[date_col], errors='coerce')
                        rt_data = rt_data.set_index(date_col)
                
                if isinstance(rt_data.index, pd.DatetimeIndex):
                    # Calculate water year and day of water year for realtime data
                    rt_data['water_year'] = rt_data.index.map(lambda d: get_water_year(d, WATER_YEAR_START))
                    rt_data['day_of_wy'] = rt_data.index.map(lambda d: get_day_of_water_year(d, WATER_YEAR_START))
                    
                    # Filter for current water year
                    current_wy_rt = rt_data[rt_data['water_year'] == current_wy]
                    
                    if not current_wy_rt.empty:
                        # Sort by day of water year
                        current_wy_rt = current_wy_rt.sort_values('day_of_wy')
                        
                        # Add realtime trace in RED
                        fig.add_trace(go.Scatter(
                            x=current_wy_rt['day_of_wy'],
                            y=current_wy_rt[rt_value_col],
                            mode='lines',
                            name='Real-time Data',
                            line=dict(color='#FF0000', width=2.5),  # Red
                            customdata=[self._day_of_wy_to_monthday(d) for d in current_wy_rt['day_of_wy']],
                            hovertemplate="<b>Real-time</b><br>" +
                                        "%{customdata}<br>" +
                                        "Discharge: %{y:.1f} cfs<extra></extra>"
                        ))
        
        # Note: NWRFC forecast overlay is now added by _add_forecast_overlay()
        # called from create_streamflow_plot() after figure creation.

        # After adding traces, set x-axis labels
        max_day = int(data_copy['day_of_wy'].max())
        tickvals = list(range(1, max_day+1, max(1, max_day//12)))
        ticktext = [self._day_of_wy_to_monthday(d) for d in tickvals]
        fig.update_xaxes(
            tickvals=tickvals, 
            ticktext=ticktext, 
            title="Month-Day",
            type='linear'  # Force linear axis, not datetime
        )
        return fig
    
    def _add_forecast_overlay(self, fig: go.Figure, forecast_data) -> go.Figure:
        """
        Add NWRFC forecast data as overlays on a water year plot.
        
        Supports multiple forecast runs (one per day). The most recent run
        is visible by default; older runs are hidden (toggle via legend).
        
        Parameters:
        -----------
        fig : go.Figure
            Existing water year plot figure
        forecast_data : list
            List of dicts with 'run_date' (str) and 'data' (DataFrame).
            Each DataFrame has 'datetime' and 'discharge_cfs' columns.
            Ordered newest-first.
            
        Returns:
        --------
        go.Figure
            Figure with forecast overlay(s) added
        """
        if not forecast_data:
            return fig
        
        # Color gradient: newest=dark purple, older=progressively lighter
        colors = ['#7B2D8E', '#9B59B6', '#B07CC6', '#C89DD6', '#DFC0E6']
        
        try:
            for i, run in enumerate(forecast_data):
                run_date_str = run.get('run_date', '')
                fc_df = run.get('data')
                
                if fc_df is None or fc_df.empty:
                    continue
                
                fc_data = fc_df.copy()
                if 'datetime' not in fc_data.columns:
                    continue
                
                fc_data['datetime'] = pd.to_datetime(fc_data['datetime'], errors='coerce')
                fc_data = fc_data.dropna(subset=['datetime'])
                
                if fc_data.empty:
                    continue
                
                # Strip timezone for day-of-water-year calculation
                if fc_data['datetime'].dt.tz is not None:
                    fc_data['datetime'] = fc_data['datetime'].dt.tz_localize(None)
                
                # Calculate fractional day of water year (preserves sub-daily resolution)
                def _fractional_day_of_wy(d):
                    if d.month >= WATER_YEAR_START:
                        wy_start = pd.Timestamp(d.year, WATER_YEAR_START, 1)
                    else:
                        wy_start = pd.Timestamp(d.year - 1, WATER_YEAR_START, 1)
                    return (d - wy_start).total_seconds() / 86400.0 + 1.0

                fc_data['day_of_wy'] = fc_data['datetime'].map(_fractional_day_of_wy)
                
                # Find discharge column
                fc_value_col = None
                for col in fc_data.columns:
                    if any(term in col.lower() for term in ['discharge', 'flow', 'cfs']):
                        fc_value_col = col
                        break
                if fc_value_col is None:
                    fc_value_col = 'discharge_cfs'
                
                if fc_value_col not in fc_data.columns:
                    continue
                
                fc_data = fc_data.sort_values('day_of_wy')
                fc_data['hover_date'] = fc_data['datetime'].dt.strftime('%b %-d %H:%M')
                
                # Parse run date for label
                try:
                    from datetime import datetime as dt_cls
                    run_dt = dt_cls.fromisoformat(run_date_str.replace('Z', '+00:00'))
                    run_label = run_dt.strftime('%b %-d')
                except (ValueError, AttributeError):
                    run_label = f'Run {i+1}'
                
                color = colors[min(i, len(colors) - 1)]
                line_width = 3 if i == 0 else 2
                
                # Latest forecast visible, older ones hidden by default
                visible = True if i == 0 else 'legendonly'
                name = f'Forecast ({run_label})' if i > 0 else 'NWRFC Forecast'
                
                fig.add_trace(go.Scatter(
                    x=fc_data['day_of_wy'],
                    y=fc_data[fc_value_col],
                    mode='lines',
                    name=name,
                    line=dict(color=color, width=line_width),
                    visible=visible,
                    customdata=fc_data['hover_date'],
                    hovertemplate=(
                        f"<b>{name}</b><br>"
                        "%{customdata}<br>"
                        "Discharge: %{y:,.0f} cfs<extra></extra>"
                    )
                ))
                logger.debug(f"Added forecast overlay: {name}, {len(fc_data)} points, visible={visible}")
                
        except Exception as e:
            logger.warning(f"Error adding forecast overlay: {e}")
        
        return fig
    
    def _add_resid_cast_overlay(self, fig: go.Figure, resid_cast_data: list) -> go.Figure:
        """Add ResidCast ML forecast series to a water year plot.

        Each model variant gets its own colour. Multiple runs per variant are
        shown newest-visible / older-legendonly, using dashed lines to
        distinguish from the solid NWRFC forecast traces.

        Parameters:
        -----------
        fig : go.Figure
        resid_cast_data : list
            List of dicts from ResidCastAdapter.get_forecasts():
            run_date, model_label, model_key, source, data (DataFrame).
            Flat list ordered newest-first across all variants.
        """
        if not resid_cast_data:
            return fig

        # One base colour per model variant (dark → light for run age)
        _MODEL_COLORS: dict[str, list[str]] = {
            "xgboost/raw":       ["#0D6B5E", "#2A9D8F", "#76C7BD", "#B2E4DF", "#D9F2F0"],
            "muthre/standalone": ["#00C853", "#2ECC71", "#82E0AA", "#A9DFBF", "#D5F5E3"],
            "lstm/raw/general":  ["#1F5C8B", "#2E86C1", "#72B6DA", "#AED6F1", "#D6EAF8"],
        }
        # MuTHRE uses solid lines; all other models use dashed
        _MODEL_DASH: dict[str, str] = {
            "muthre/standalone": "solid",
        }
        _DEFAULT_COLORS = ["#555555", "#888888", "#AAAAAA", "#CCCCCC", "#EEEEEE"]

        # Track per-model run index (newest = 0, oldest = N)
        model_run_index: dict[str, int] = {}

        try:
            for entry in resid_cast_data:
                model_key   = entry.get("model_key", "")
                model_label = entry.get("model_label", model_key)
                run_date    = entry.get("run_date", "")
                fc_df       = entry.get("data")

                if fc_df is None or fc_df.empty:
                    continue
                if "datetime" not in fc_df.columns:
                    continue

                fc_data = fc_df.copy()
                fc_data["datetime"] = pd.to_datetime(fc_data["datetime"], errors="coerce")
                fc_data = fc_data.dropna(subset=["datetime"])
                if fc_data.empty:
                    continue

                if fc_data["datetime"].dt.tz is not None:
                    fc_data["datetime"] = fc_data["datetime"].dt.tz_localize(None)

                def _fractional_day_of_wy(d):
                    if d.month >= WATER_YEAR_START:
                        wy_start = pd.Timestamp(d.year, WATER_YEAR_START, 1)
                    else:
                        wy_start = pd.Timestamp(d.year - 1, WATER_YEAR_START, 1)
                    return (d - wy_start).total_seconds() / 86400.0 + 1.0

                fc_data["day_of_wy"] = fc_data["datetime"].map(_fractional_day_of_wy)

                discharge_col = next(
                    (c for c in fc_data.columns
                     if any(t in c.lower() for t in ["discharge", "flow", "cfs"])),
                    None,
                )
                if discharge_col is None or discharge_col not in fc_data.columns:
                    continue

                fc_data = fc_data.sort_values("day_of_wy")
                fc_data["hover_date"] = fc_data["datetime"].dt.strftime("%b %-d")

                run_idx = model_run_index.get(model_key, 0)
                model_run_index[model_key] = run_idx + 1

                palette = _MODEL_COLORS.get(model_key, _DEFAULT_COLORS)
                color = palette[min(run_idx, len(palette) - 1)]
                line_width = 2.5 if run_idx == 0 else 1.5
                visible = True if run_idx == 0 else "legendonly"

                try:
                    from datetime import datetime as _dt
                    run_dt = _dt.fromisoformat(run_date)
                    date_label = run_dt.strftime("%b %-d")
                except (ValueError, AttributeError):
                    date_label = run_date[:10] if run_date else f"Run {run_idx + 1}"

                name = f"{model_label} – {date_label}"

                dash_style = _MODEL_DASH.get(model_key, "dash")

                fig.add_trace(go.Scatter(
                    x=fc_data["day_of_wy"],
                    y=fc_data[discharge_col],
                    mode="lines",
                    name=name,
                    line=dict(color=color, width=line_width, dash=dash_style),
                    visible=visible,
                    customdata=fc_data["hover_date"],
                    hovertemplate=(
                        f"<b>{name}</b><br>"
                        "%{customdata}<br>"
                        "Discharge: %{y:,.0f} cfs<extra></extra>"
                    ),
                ))

        except Exception as e:
            logger.warning(f"Error adding ResidCast overlay: {e}")

        return fig

    def _add_precip_overlay(self, fig: go.Figure, precip_runoff_data: list) -> go.Figure:
        """Add EA-LSTM precip-runoff forecast traces to a water year plot.

        Uses amber/orange palette to distinguish from ResidCast teal/green/blue family.
        Multiple runs shown newest-visible / older-legendonly, with dot-dash lines
        to distinguish from ResidCast dashed traces.

        Parameters
        ----------
        fig : go.Figure
        precip_runoff_data : list
            List of dicts from PrecipRunoffAdapter.get_forecasts():
            run_date, model_label, model_key, source, data (DataFrame).
        """
        if not precip_runoff_data:
            return fig

        _PRECIP_COLORS = ["#E67E22", "#F0A500", "#F5C842", "#F7D98B", "#FBF3D0"]
        run_index = 0

        try:
            for entry in precip_runoff_data:
                fc_df = entry.get("data")
                if fc_df is None or fc_df.empty:
                    continue
                if "datetime" not in fc_df.columns:
                    continue

                fc_data = fc_df.copy()
                fc_data["datetime"] = pd.to_datetime(fc_data["datetime"], errors="coerce")
                fc_data = fc_data.dropna(subset=["datetime"])
                if fc_data.empty:
                    continue

                if fc_data["datetime"].dt.tz is not None:
                    fc_data["datetime"] = fc_data["datetime"].dt.tz_localize(None)

                def _fractional_day_of_wy(d):
                    if d.month >= WATER_YEAR_START:
                        wy_start = pd.Timestamp(d.year, WATER_YEAR_START, 1)
                    else:
                        wy_start = pd.Timestamp(d.year - 1, WATER_YEAR_START, 1)
                    return (d - wy_start).total_seconds() / 86400.0 + 1.0

                fc_data["day_of_wy"] = fc_data["datetime"].map(_fractional_day_of_wy)

                discharge_col = next(
                    (c for c in fc_data.columns
                     if any(t in c.lower() for t in ["discharge", "flow", "cfs"])),
                    None,
                )
                if discharge_col is None:
                    continue

                fc_data = fc_data.sort_values("day_of_wy")
                fc_data["hover_date"] = fc_data["datetime"].dt.strftime("%b %-d")

                run_date = entry.get("run_date", "")
                color = _PRECIP_COLORS[min(run_index, len(_PRECIP_COLORS) - 1)]
                line_width = 2.5 if run_index == 0 else 1.5
                visible = True if run_index == 0 else "legendonly"

                try:
                    from datetime import datetime as _dt
                    run_dt = _dt.fromisoformat(run_date)
                    date_label = run_dt.strftime("%b %-d")
                except (ValueError, AttributeError):
                    date_label = run_date[:10] if run_date else f"Run {run_index + 1}"

                name = f"EA-LSTM \u2013 {date_label}"
                run_index += 1

                fig.add_trace(go.Scatter(
                    x=fc_data["day_of_wy"],
                    y=fc_data[discharge_col],
                    mode="lines",
                    name=name,
                    line=dict(color=color, width=line_width, dash="dot"),
                    visible=visible,
                    customdata=fc_data["hover_date"],
                    hovertemplate=(
                        f"<b>{name}</b><br>"
                        "%{customdata}<br>"
                        "Discharge: %{y:,.0f} cfs<extra></extra>"
                    ),
                ))

        except Exception as exc:
            logger.warning("Error adding EA-LSTM precip overlay: %s", exc)

        return fig

    def _add_range_controls(self, fig: go.Figure, current_day: int) -> go.Figure:
        """
        Add a range slider and preset window buttons to a water year plot.

        Buttons: Forecast View (-7/+14 days, y-scaled to window), ±1mo, ±3mo, Full Year (default).
        All non-forecast buttons reset yaxis.autorange so y rescales on click.
        """
        # Compute forecast window bounds
        fc_x0 = max(1.0, current_day - 7)
        fc_x1 = min(366.0, current_day + 14)

        # Derive tight y-bounds from trace data inside the forecast window.
        # Prefer forecast + current-year traces; fall back to statistics (percentile
        # bands / long-term mean) only when no observed/forecast data is in the window.
        _STATS_FRAGMENTS = ('percentile', 'long-term', 'median', 'mean')
        priority_y, fallback_y = [], []
        for trace in fig.data:
            xs = getattr(trace, 'x', None)
            ys = getattr(trace, 'y', None)
            if xs is None or ys is None:
                continue
            name_lower = (getattr(trace, 'name', '') or '').lower()
            is_stats = any(f in name_lower for f in _STATS_FRAGMENTS)
            target = fallback_y if is_stats else priority_y
            for x, y in zip(xs, ys):
                try:
                    if y is not None and fc_x0 <= float(x) <= fc_x1:
                        target.append(float(y))
                except (TypeError, ValueError):
                    pass
        fc_y_vals = priority_y if priority_y else fallback_y

        if fc_y_vals:
            span = max(fc_y_vals) - min(fc_y_vals)
            pad = span * 0.12 if span > 0 else max(fc_y_vals) * 0.12
            fc_y_range = [max(0, min(fc_y_vals) - pad), max(fc_y_vals) + pad]
            fc_relayout = {'xaxis.range': [fc_x0, fc_x1], 'yaxis.range': fc_y_range, 'yaxis.autorange': False}
        else:
            fc_relayout = {'xaxis.range': [fc_x0, fc_x1], 'yaxis.autorange': True}

        buttons = [
            dict(label='Forecast', method='relayout', args=[fc_relayout]),
        ]

        for label, half_span in [('±1mo', 30), ('±3mo', 91)]:
            x0 = max(1, current_day - half_span)
            x1 = min(366, current_day + half_span)
            buttons.append(dict(
                label=label,
                method='relayout',
                args=[{'xaxis.range': [x0, x1], 'yaxis.autorange': True}]
            ))

        buttons.append(dict(
            label='Full Year',
            method='relayout',
            args=[{'xaxis.range': [1, 366], 'yaxis.autorange': True}]
        ))

        fig.update_layout(
            xaxis=dict(
                rangeslider=dict(visible=True, thickness=0.10),
                range=[1, 366],  # Full Year default
            ),
            yaxis=dict(autorange=True),
            legend=dict(
                orientation='h',
                yanchor='top',
                y=-0.22,
                xanchor='center',
                x=0.5,
                font=dict(size=10),
                tracegroupgap=0,
            ),
            margin=dict(b=140, t=60),
            updatemenus=[
                dict(
                    type='buttons',
                    direction='right',
                    x=0.0,
                    xanchor='left',
                    y=1.12,
                    yanchor='top',
                    showactive=True,
                    active=3,  # Full Year is index 3 — shown as active on load
                    buttons=buttons,
                    font=dict(size=10, color='#ffffff'),
                    bgcolor='rgba(55,65,81,0.85)',
                    bordercolor='rgba(100,116,139,0.7)',
                )
            ]
        )
        return fig

    def _create_basic_timeseries_plot(self, data: pd.DataFrame, value_col: str) -> go.Figure:
        """Create basic timeseries plot."""
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data[value_col],
            mode='lines',
            name='Daily Discharge',
            line=dict(color='blue', width=1),
            hovertemplate="Date: %{x}<br>Discharge: %{y:.1f} cfs<extra></extra>"
        ))
        
        return fig
    
    def _create_daily_timeseries_plot(self, sf_data) -> go.Figure:
        """Create daily timeseries plot using StreamflowData."""
        
        data = sf_data.data
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data[sf_data.value_column],
            mode='lines',
            name='Daily Discharge',
            line=dict(color='blue', width=1),
            hovertemplate="Date: %{x}<br>Discharge: %{y:.1f} cfs<extra></extra>"
        ))
        
        fig.update_layout(
            title=f"Daily Streamflow - Site {sf_data.site_id}",
            xaxis_title="Date",
            yaxis_title="Discharge (cfs)",
            height=500
        )
        
        return fig
    
    def _create_error_plot(self, error_message: str) -> go.Figure:
        """Create error plot when data cannot be processed."""
        
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {error_message}",
            x=0.5, y=0.5,
            xref='paper', yref='paper',
            showarrow=False,
            font=dict(size=16, color='red')
        )
        
        fig.update_layout(
            title="Error Loading Data",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=400
        )
        
        return fig
    
    def create_gauge_comparison_plot(self, gauge_data_dict: Dict[str, pd.DataFrame],
                                   comparison_type: str = 'annual') -> go.Figure:
        """
        Create comparison plot for multiple gauges.
        
        Parameters:
        -----------
        gauge_data_dict : dict
            Dictionary with site_id as key and streamflow data as value
        comparison_type : str
            Type of comparison ('annual', 'monthly', 'seasonal')
            
        Returns:
        --------
        go.Figure
            Comparison plot
        """
        
        fig = go.Figure()
        colors = px.colors.qualitative.Set1
        
        for i, (site_id, data) in enumerate(gauge_data_dict.items()):
            color = colors[i % len(colors)]
            
            if comparison_type == 'annual':
                # Calculate annual means
                data_copy = data.copy()
                if 'datetime' in data.columns:
                    data_copy = data_copy.set_index('datetime')
                
                # Get discharge column
                value_col = None
                for col in data.columns:
                    if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                        value_col = col
                        break
                
                if value_col is None:
                    continue
                
                annual_means = data_copy[value_col].resample('Y').mean()
                
                fig.add_trace(go.Scatter(
                    x=annual_means.index.year,
                    y=annual_means.values,
                    mode='lines+markers',
                    name=f"Site {site_id}",
                    line=dict(color=color, width=2),
                    marker=dict(size=6),
                    hovertemplate=f"<b>Site {site_id}</b><br>" +
                                "Year: %{x}<br>" +
                                "Mean Discharge: %{y:.1f} cfs<extra></extra>"
                ))
        
        fig.update_layout(
            title="Annual Mean Discharge Comparison",
            xaxis_title="Year",
            yaxis_title="Mean Discharge (cfs)",
            height=500,
            showlegend=True
        )
        
        return fig
    
    def create_flow_duration_curve(self, site_id: str, data: pd.DataFrame) -> go.Figure:
        """Create flow duration curve for a gauge."""
        
        # Make a copy to avoid modifying the original data
        data = data.copy()
        
        # Get discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        
        if value_col is None:
            return self._create_error_plot("No discharge data found for flow duration curve")
        
        # Calculate flow duration curve
        flows = data[value_col].dropna().sort_values(ascending=False)
        n = len(flows)
        exceedance_prob = np.arange(1, n + 1) / n * 100
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=exceedance_prob,
            y=flows.values,
            mode='lines',
            name='Flow Duration Curve',
            line=dict(color='blue', width=2),
            hovertemplate="Exceedance: %{x:.1f}%<br>Discharge: %{y:.1f} cfs<extra></extra>"
        ))
        
        # Add percentile markers
        percentiles = [10, 25, 50, 75, 90]
        for p in percentiles:
            idx = int(p / 100 * n)
            if idx < n:
                fig.add_vline(
                    x=p, 
                    line_dash="dash", 
                    line_color="red",
                    annotation_text=f"{p}th percentile"
                )
        
        # Plot most recent discharge value from the past 7 days on the curve
        try:
            cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=7)
            # Data may use a 'datetime' column rather than a DatetimeIndex
            if 'datetime' in data.columns:
                date_series = pd.to_datetime(data['datetime'], utc=True)
                mask = date_series >= cutoff
                recent_vals = data.loc[mask, value_col].dropna()
                recent_dates = date_series[recent_vals.index]
            else:
                # Fallback: try the index if it's datetime-like
                idx = pd.to_datetime(data.index, errors='coerce', utc=True)
                mask = idx >= cutoff
                recent_vals = data.loc[mask, value_col].dropna()
                recent_dates = idx[recent_vals.index]

            if not recent_vals.empty:
                current_val = recent_vals.iloc[-1]
                current_date = pd.to_datetime(recent_dates.iloc[-1])
                # Exceedance probability: fraction of all historical values >= current value
                current_exc = (flows >= current_val).sum() / n * 100
                fig.add_trace(go.Scatter(
                    x=[current_exc],
                    y=[current_val],
                    mode='markers',
                    name=f'Current ({current_date.strftime("%b %d")})',
                    marker=dict(
                        symbol='square',
                        size=14,
                        color='rgba(0, 160, 0, 0.9)',
                        line=dict(color='darkgreen', width=1.5),
                    ),
                    hovertemplate=(
                        f"<b>Most Recent Reading</b><br>"
                        f"Date: {current_date.strftime('%Y-%m-%d')}<br>"
                        "Exceedance: %{x:.1f}%<br>"
                        "Discharge: %{y:.1f} cfs<extra></extra>"
                    )
                ))
        except Exception:
            pass  # Never block the plot on a marker failure
        
        fig.update_layout(
            title=f"Flow Duration Curve - Site {site_id}",
            xaxis_title="Exceedance Probability (%)",
            yaxis_title="Discharge (cfs)",
            yaxis_type="log",
            height=500,
            showlegend=True
        )
        
        return fig
    
    # Removed: _get_water_year() and _get_day_of_water_year()
    # Now use imported functions from water_year_calculator.py:
    #   - get_water_year(date, start_month=10)
    #   - get_day_of_water_year(date, start_month=10)
    
    def get_data_summary_stats(self, data: pd.DataFrame) -> Dict:
        """Get summary statistics for streamflow data."""
        
        # Get discharge column
        value_col = None
        for col in data.columns:
            if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                value_col = col
                break
        
        if value_col is None:
            return {"error": "No discharge data found"}
        
        flows = data[value_col].dropna()
        
        stats = {
            'count': len(flows),
            'mean': flows.mean(),
            'median': flows.median(),
            'min': flows.min(),
            'max': flows.max(),
            'std': flows.std(),
            'start_date': data.index.min().strftime('%Y-%m-%d') if hasattr(data.index, 'min') else 'Unknown',
            'end_date': data.index.max().strftime('%Y-%m-%d') if hasattr(data.index, 'max') else 'Unknown',
        }
        
        # Add percentiles
        percentiles = [10, 25, 50, 75, 90, 95, 99]
        for p in percentiles:
            stats[f'p{p}'] = flows.quantile(p / 100)
        
        return stats

    def _add_realtime_overlay(self, fig: go.Figure, realtime_data: pd.DataFrame, site_id: str) -> go.Figure:
        """Add real-time data overlay to existing plot."""
        try:
            # Find the discharge column in real-time data
            value_col = None
            for col in realtime_data.columns:
                if any(term in col.lower() for term in ['discharge', 'flow', '00060']):
                    value_col = col
                    break
            
            if value_col is None:
                logger.warning("No discharge column found in real-time data")
                return fig

            # Clean the real-time data
            rt_data_clean = realtime_data.dropna()
            if rt_data_clean.empty:
                logger.debug("Real-time data is empty after cleaning")
                return fig
            
            # Check if this is a water year plot by looking at the x-axis type
            # Water year plots use numeric x-axis (day of water year), while others use datetime
            x_axis_type = fig.layout.xaxis.type if fig.layout.xaxis.type else 'date'
            is_water_year_plot = (x_axis_type == 'linear' and 
                                fig.layout.xaxis.title.text == "Day of Water Year")
            
            if is_water_year_plot:
                # For water year plots, convert real-time data to day-of-water-year format
                logger.debug("Adding real-time overlay to water year plot")
                
                # Prepare real-time data using the same water year system
                rt_prepared = self.wy_handler.prepare_water_year_data(rt_data_clean, value_col)
                
                # Group by current water year (most recent data)
                current_wy = self.wy_handler.get_water_year(pd.Timestamp.now())
                current_year_rt = rt_prepared[rt_prepared['water_year'] == current_wy]
                
                if not current_year_rt.empty:
                    # Sort by day of water year for proper line plotting
                    current_year_rt = current_year_rt.sort_values('day_of_wy')
                    
                    # Add real-time data trace with day-of-water-year x-axis
                    # Create custom data with both date and time
                    customdata_array = np.column_stack([
                        current_year_rt['month_day'].values,
                        current_year_rt.index.strftime('%H:%M').values
                    ])
                    
                    fig.add_trace(
                        go.Scatter(
                            x=current_year_rt['day_of_wy'],
                            y=current_year_rt['value'],
                            mode='lines',
                            name=f'Real-time WY {current_wy} (15-min)',
                            line=dict(
                                color='red',
                                width=3,
                                dash='solid'
                            ),
                            opacity=0.9,
                            hovertemplate=(
                                '<b>Real-time WY' + f' {current_wy}</b><br>' +
                                'Day %{x:.1f}: %{customdata[0]} %{customdata[1]}<br>' +
                                'Discharge: %{y:.2f} cfs' +
                                '<extra></extra>'
                            ),
                            customdata=customdata_array
                        )
                    )
                    logger.debug(f"Added real-time overlay to water year plot: {len(current_year_rt)} points for WY {current_wy}")
                else:
                    logger.debug(f"No real-time data available for current water year {current_wy}")
            else:
                # For non-water-year plots, use original datetime-based approach
                logger.debug("Adding real-time overlay to timeseries plot")
                
                # Add real-time data trace with datetime x-axis
                fig.add_trace(
                    go.Scatter(
                        x=rt_data_clean.index,
                        y=rt_data_clean[value_col],
                        mode='lines',
                        name='Real-time (15-min)',
                        line=dict(
                            color='red',
                            width=2,
                            dash='solid'
                        ),
                        opacity=0.8,
                        hovertemplate=(
                            '<b>Real-time Data</b><br>' +
                            'Date: %{x}<br>' +
                            'Discharge: %{y:.2f} cfs<br>' +
                            '<extra></extra>'
                        )
                    )
                )
            
            # Update legend to show both data types
            fig.update_layout(
                annotations=[
                    dict(
                        text=f"<b>Daily historical data + Real-time high-resolution data</b><br>Site: {site_id}",
                        xref="paper", yref="paper",
                        x=0.5, y=1.02, 
                        showarrow=False,
                        xanchor="center",
                        font=dict(size=12)
                    )
                ]
            )
            
            logger.debug(f"Added real-time overlay with {len(rt_data_clean)} points")
            return fig

        except Exception as e:
            logger.warning(f"Error adding real-time overlay: {e}")
            return fig


# Convenience function for creating visualization manager
def get_visualization_manager() -> VisualizationManager:
    """Get initialized visualization manager instance."""
    return VisualizationManager()
