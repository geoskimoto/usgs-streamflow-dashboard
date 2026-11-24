"""Layout ids and CSS/JS asset checks for the per-station page feature."""
import re
from pathlib import Path

import pytest
from dash import dcc, html

import app as app_module
from tests.test_layout_ids import _get_layout, _find, _tree_ids

ROOT = Path(__file__).resolve().parent.parent
NEW_IDS = ["copy-station-link-btn", "station-back-link", "url-sync-dummy",
           "station-page-dummy", "url"]


@pytest.fixture(scope="module")
def layout():
    return _get_layout()


@pytest.fixture(scope="module")
def tree_ids(layout):
    return _tree_ids(layout)


@pytest.mark.parametrize("cid", NEW_IDS)
def test_station_page_id_present_in_layout(tree_ids, cid):
    assert cid in tree_ids


def test_url_is_dcc_location(layout):
    assert isinstance(_find(layout, "url"), dcc.Location)


def test_station_back_link_is_html_a(layout):
    comp = _find(layout, "station-back-link")
    assert isinstance(comp, html.A)


def test_new_callback_ids_exist_in_layout(tree_ids):
    cmap = app_module.app.callback_map
    ids = set()
    for key, spec in cmap.items():
        for item in spec.get("inputs", []) + spec.get("state", []):
            ids.add(item["id"])
    for cid in ("url-sync-dummy", "station-page-dummy", "copy-station-link-btn"):
        assert cid in tree_ids


def _css_blocks(css):
    return re.findall(r"([^{}]+)\{([^{}]*)\}", css)


def _hidden_by_station_page(selector_fragment):
    css = (ROOT / "assets" / "theme.css").read_text()
    for sel, body in _css_blocks(css):
        for s in sel.split(","):
            s = s.strip()
            if s.startswith("body.station-page") and selector_fragment in s \
                    and re.search(r"display\s*:\s*none", body):
                return True
    return False


def test_theme_css_hides_sidebar_on_station_page():
    assert _hidden_by_station_page("#sidebar-col")


def test_theme_css_hides_map_stage_on_station_page():
    assert _hidden_by_station_page(".map-stage")


def test_panel_resize_js_references_station_page():
    src = (ROOT / "assets" / "panel_resize.js").read_text()
    assert "station-page" in src
