"""
Statistics cache manager for per-day-of-water-year flow statistics.

Caches computed percentile bands, mean, and median to parquet so the
dashboard can render the fast water year plot without pulling full
historical discharge on every station click.

Cache key:  data/stats_cache/<site_id>_WY<year>.parquet
Validity:   Entire current water year. Invalidated at Oct 1 when a new
            completed year is added to the historical record.
"""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from ..utils.config import WATER_YEAR_START
from ..utils.water_year_calculator import get_day_of_water_year, get_water_year

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATS_CACHE_DIR = str(_REPO_ROOT / "data" / "stats_cache")


def _current_water_year() -> int:
    from datetime import datetime
    now = datetime.now()
    return now.year + 1 if now.month >= WATER_YEAR_START else now.year


def _cache_path(site_id: str, water_year: int) -> str:
    return os.path.join(STATS_CACHE_DIR, f"{site_id}_WY{water_year}.parquet")


def _remove_stale(site_id: str, current_wy: int) -> None:
    """Delete cache files from previous water years for this site."""
    for f in Path(STATS_CACHE_DIR).glob(f"{site_id}_WY*.parquet"):
        if f.stem != f"{site_id}_WY{current_wy}":
            try:
                f.unlink()
                logger.debug(f"Removed stale stats cache: {f.name}")
            except OSError:
                pass


def get_statistics(site_id: str, discharge_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return per-day-of-water-year statistics for site_id.

    Loads from parquet cache when valid for the current water year.
    On cache miss, computes statistics from discharge_df (full history
    excluding current WY), writes the cache file, and returns the result.

    Parameters
    ----------
    site_id : str
    discharge_df : pd.DataFrame
        Full historical discharge data with a 'datetime'/'date' column
        or DatetimeIndex plus a discharge column.

    Returns
    -------
    pd.DataFrame
        Columns: day_of_wy, q10, q25, q50, q75, q90, mean, median
        (366 rows max — one per day of water year)
        Empty DataFrame if insufficient data.
    """
    os.makedirs(STATS_CACHE_DIR, exist_ok=True)
    current_wy = _current_water_year()
    path = _cache_path(site_id, current_wy)

    if os.path.exists(path):
        try:
            stats = pd.read_parquet(path)
            logger.debug(f"Stats cache HIT: {site_id} WY{current_wy} ({len(stats)} day-rows)")
            return stats
        except Exception as exc:
            logger.warning(f"Stats cache read failed ({path}): {exc} — recomputing")

    logger.info(f"Stats cache MISS: computing for {site_id} WY{current_wy}")
    stats = _compute_statistics(discharge_df, current_wy)

    if not stats.empty:
        try:
            stats.to_parquet(path, index=False)
            logger.info(f"Stats cached: {path}")
            _remove_stale(site_id, current_wy)
        except Exception as exc:
            logger.warning(f"Stats cache write failed ({path}): {exc}")

    return stats


def _compute_statistics(discharge_df: pd.DataFrame, current_wy: int) -> pd.DataFrame:
    """
    Compute per-day-of-WY percentiles, mean, and median from historical data.

    Excludes the current (in-progress) water year so statistics only
    reflect completed years.
    """
    if discharge_df.empty:
        return pd.DataFrame()

    df = discharge_df.copy()

    # Ensure DatetimeIndex
    if not isinstance(df.index, pd.DatetimeIndex):
        for col in ("datetime", "date"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df = df.set_index(col)
                break

    if not isinstance(df.index, pd.DatetimeIndex):
        logger.warning("Cannot compute stats: no DatetimeIndex or datetime column")
        return pd.DataFrame()

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df = df.dropna()

    # Identify discharge column
    value_col = next(
        (c for c in df.columns if any(t in c.lower() for t in ("discharge", "flow", "00060"))),
        None,
    )
    if value_col is None:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            logger.warning("No numeric discharge column found")
            return pd.DataFrame()
        value_col = numeric_cols[0]

    df["water_year"] = df.index.map(lambda d: get_water_year(d, WATER_YEAR_START))
    df["day_of_wy"] = df.index.map(lambda d: get_day_of_water_year(d, WATER_YEAR_START))

    # Only completed water years
    historical = df[df["water_year"] < current_wy].copy()

    if len(historical) < 365:
        logger.warning(
            f"Insufficient historical data for stats ({len(historical)} rows); need ≥365"
        )
        return pd.DataFrame()

    stats = (
        historical.groupby("day_of_wy")[value_col]
        .agg(
            q10=lambda x: x.quantile(0.10),
            q25=lambda x: x.quantile(0.25),
            q50=lambda x: x.quantile(0.50),
            q75=lambda x: x.quantile(0.75),
            q90=lambda x: x.quantile(0.90),
            mean="mean",
            median="median",
        )
        .reset_index()
    )

    logger.info(
        f"Computed stats from {historical['water_year'].nunique()} water years "
        f"({len(historical)} obs) for {len(stats)} day-of-WY rows"
    )
    return stats
