"""
Plot cache manager for pre-rendered water-year plot figures.

Caches serialized Plotly figure JSON so the dashboard can serve
pre-built plots without server-side computation on every station click.

Cache key:  data/plot_cache/<site_id>_WY<year>.json
Metadata:   data/plot_cache/<site_id>_WY<year>.meta.json
Validity:   Until explicitly invalidated or Oct 1 (new water year).
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLOT_CACHE_DIR = str(_REPO_ROOT / "data" / "plot_cache")
_WATER_YEAR_START = 10  # October


def _current_water_year() -> int:
    now = datetime.now()
    return now.year + 1 if now.month >= _WATER_YEAR_START else now.year


def _cache_path(site_id: str, water_year: int) -> Path:
    return Path(PLOT_CACHE_DIR) / f"{site_id}_WY{water_year}.json"


def _meta_path(site_id: str, water_year: int) -> Path:
    return Path(PLOT_CACHE_DIR) / f"{site_id}_WY{water_year}.meta.json"


def get(site_id: str) -> tuple[Optional[dict], Optional[datetime]]:
    """Return (figure_dict, generated_at) for current WY, or (None, None) on miss."""
    wy = _current_water_year()
    meta_p = _meta_path(site_id, wy)
    fig_p = _cache_path(site_id, wy)

    if not meta_p.exists() or not fig_p.exists():
        return None, None

    try:
        with open(meta_p) as f:
            meta = json.load(f)
        generated_at = datetime.fromisoformat(meta["generated_at"])
        with open(fig_p) as f:
            fig_dict = json.load(f)
        logger.debug(f"Plot cache HIT: {site_id} WY{wy}")
        return fig_dict, generated_at
    except Exception as exc:
        logger.warning(f"Plot cache read failed for {site_id}: {exc}")
        return None, None


def save(site_id: str, figure: go.Figure) -> None:
    """Serialize figure to JSON atomically via temp file."""
    wy = _current_water_year()
    os.makedirs(PLOT_CACHE_DIR, exist_ok=True)

    fig_p = _cache_path(site_id, wy)
    meta_p = _meta_path(site_id, wy)
    dir_ = str(fig_p.parent)

    try:
        fig_json = figure.to_json()

        with tempfile.NamedTemporaryFile("w", dir=dir_, suffix=".tmp", delete=False) as f:
            f.write(fig_json)
            tmp_fig = f.name
        os.replace(tmp_fig, str(fig_p))

        meta = {
            "generated_at": datetime.now().isoformat(),
            "site_id": site_id,
            "water_year": wy,
        }
        with tempfile.NamedTemporaryFile("w", dir=dir_, suffix=".tmp", delete=False) as f:
            json.dump(meta, f)
            tmp_meta = f.name
        os.replace(tmp_meta, str(meta_p))

        logger.info(f"Plot cached: {site_id} WY{wy} ({len(fig_json) // 1024}KB)")
        _remove_stale(site_id, wy)
    except Exception as exc:
        logger.warning(f"Plot cache write failed for {site_id}: {exc}")


def exists(site_id: str) -> bool:
    """Return True if a valid cache entry exists for the current water year."""
    wy = _current_water_year()
    return _meta_path(site_id, wy).exists() and _cache_path(site_id, wy).exists()


def age_seconds(site_id: str) -> Optional[float]:
    """Seconds since the cached figure was generated, or None if not cached."""
    _, generated_at = get(site_id)
    if generated_at is None:
        return None
    return (datetime.now() - generated_at).total_seconds()


def invalidate(site_id: str) -> None:
    """Delete cache files for the current water year."""
    wy = _current_water_year()
    for p in (_cache_path(site_id, wy), _meta_path(site_id, wy)):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def list_cached() -> list[str]:
    """Return site IDs with a valid cache entry for the current water year."""
    wy = _current_water_year()
    cache_dir = Path(PLOT_CACHE_DIR)
    if not cache_dir.exists():
        return []
    return [
        p.name.replace(f"_WY{wy}.meta.json", "")
        for p in cache_dir.glob(f"*_WY{wy}.meta.json")
    ]


def _remove_stale(site_id: str, current_wy: int) -> None:
    """Delete cache files from previous water years for this site."""
    for p in Path(PLOT_CACHE_DIR).glob(f"{site_id}_WY*"):
        if f"_WY{current_wy}" not in p.stem:
            try:
                p.unlink()
                logger.debug(f"Removed stale plot cache: {p.name}")
            except OSError:
                pass
