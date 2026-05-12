"""
PNG cache manager for hover-tooltip water-year plot thumbnails.

Cache key:  data/png_cache/<site_id>_WY<year>.png
Validity:   Until explicitly invalidated or Oct 1 (new water year).
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PNG_CACHE_DIR = str(_REPO_ROOT / "data" / "png_cache")
_WATER_YEAR_START = 10  # October


def _current_water_year() -> int:
    now = datetime.now()
    return now.year + 1 if now.month >= _WATER_YEAR_START else now.year


def get_path(site_id: str) -> Path:
    """Return the expected PNG path for the current water year."""
    wy = _current_water_year()
    return Path(PNG_CACHE_DIR) / f"{site_id}_WY{wy}.png"


def exists(site_id: str) -> bool:
    """Return True if a PNG exists for the current water year."""
    return get_path(site_id).is_file()


def save(site_id: str, figure: go.Figure) -> bool:
    """
    Write figure to PNG atomically via temp file.
    Figure should already have axes clipped before calling this.
    Returns True on success, False on failure.
    """
    os.makedirs(PNG_CACHE_DIR, exist_ok=True)
    out_path = get_path(site_id)
    dir_ = str(out_path.parent)
    tmp = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".png", dir=dir_, delete=False) as f:
            tmp = f.name
        figure.write_image(tmp, format="png")
        os.replace(tmp, str(out_path))
        logger.info(f"PNG cached: {site_id} WY{_current_water_year()} → {out_path.name}")
        _remove_stale(site_id, _current_water_year())
        return True
    except Exception as exc:
        logger.warning(f"PNG cache write failed for {site_id}: {exc}")
        if tmp is not None:
            try:
                os.unlink(tmp)
            except Exception:
                pass
        return False


def invalidate(site_id: str) -> None:
    """Delete the PNG for the current water year if it exists."""
    p = get_path(site_id)
    try:
        p.unlink(missing_ok=True)
    except OSError:
        pass


def list_cached() -> list[str]:
    """Return site IDs that have a PNG for the current water year."""
    wy = _current_water_year()
    cache_dir = Path(PNG_CACHE_DIR)
    if not cache_dir.exists():
        return []
    return [
        p.stem.replace(f"_WY{wy}", "")
        for p in cache_dir.glob(f"*_WY{wy}.png")
    ]


def _remove_stale(site_id: str, current_wy: int) -> None:
    """Delete PNGs from previous water years for this site."""
    for p in Path(PNG_CACHE_DIR).glob(f"{site_id}_WY*.png"):
        if f"_WY{current_wy}" not in p.stem:
            try:
                p.unlink()
                logger.debug(f"Removed stale PNG cache: {p.name}")
            except OSError:
                pass
