"""Tests for PNG cache manager."""
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import importlib.util

import pytest

# Add repo root to path like conftest.py does
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def tmp_png_dir(tmp_path, monkeypatch):
    """Redirect PNG_CACHE_DIR to a temp directory."""
    # Load the module directly without triggering the package __init__
    spec = importlib.util.spec_from_file_location(
        "png_cache_manager",
        str(_REPO_ROOT / "usgs_dashboard" / "data" / "png_cache_manager.py")
    )
    pcm = importlib.util.module_from_spec(spec)
    sys.modules['usgs_dashboard.data.png_cache_manager'] = pcm
    spec.loader.exec_module(pcm)
    # Now patch PNG_CACHE_DIR after module is loaded
    monkeypatch.setattr(pcm, "PNG_CACHE_DIR", str(tmp_path))
    return tmp_path


def test_exists_returns_false_when_no_file(tmp_png_dir):
    from usgs_dashboard.data.png_cache_manager import exists
    assert exists("12345678") is False


def test_get_path_returns_correct_path(tmp_png_dir):
    from usgs_dashboard.data.png_cache_manager import exists, get_path, _current_water_year
    wy = _current_water_year()
    path = get_path("12345678")
    assert path == tmp_png_dir / f"12345678_WY{wy}.png"


def test_exists_returns_true_after_file_created(tmp_png_dir):
    from usgs_dashboard.data.png_cache_manager import exists, get_path
    get_path("12345678").touch()
    assert exists("12345678") is True


def test_invalidate_removes_file(tmp_png_dir):
    from usgs_dashboard.data.png_cache_manager import exists, get_path, invalidate
    get_path("12345678").touch()
    assert exists("12345678") is True
    invalidate("12345678")
    assert exists("12345678") is False


def test_list_cached_returns_site_ids(tmp_png_dir):
    from usgs_dashboard.data.png_cache_manager import list_cached, get_path, _current_water_year
    wy = _current_water_year()
    (tmp_png_dir / f"12345678_WY{wy}.png").touch()
    (tmp_png_dir / f"99887766_WY{wy}.png").touch()
    result = list_cached()
    assert set(result) == {"12345678", "99887766"}


def test_list_cached_ignores_stale_water_year(tmp_png_dir):
    from usgs_dashboard.data.png_cache_manager import list_cached, _current_water_year
    stale_wy = _current_water_year() - 1
    (tmp_png_dir / f"12345678_WY{stale_wy}.png").touch()
    assert list_cached() == []
