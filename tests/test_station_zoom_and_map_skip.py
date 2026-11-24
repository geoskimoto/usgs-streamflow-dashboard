"""
Station page: skip map rebuild, and client-side deep-link zoom.
Written before implementation; offline and deterministic.

JS source is located by reading app.py text (callback_map does not retain
clientside JS): the block from the nearest preceding `app.clientside_callback(`
to the next callback decorator/registration after the Output('deep-link-zoom-dummy', ...).
"""
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from dash import no_update

import app as app_module
from tests.test_layout_ids import _get_layout, _tree_ids, _find

APP_SRC = (Path(__file__).resolve().parent.parent / "app.py").read_text()
MAP_OUTPUTS = ["gauge-map.figure", "gauge-count-badge.children", "results-count.children"]


def _map_cb_key():
    for k in app_module.app.callback_map:
        if "gauge-map.figure" in k and "gauge-count-badge.children" in k:
            return k
    return None


def _call(pathname="__omit__"):
    # 16 Inputs (gauges_data first) + selected_gauge State = 17 existing positionals
    args = [[]] + [None] * 15 + [None]
    if pathname == "__omit__":
        return app_module.update_map_with_simplified_filters(*args)
    return app_module.update_map_with_simplified_filters(*args, pathname)


# ------------------------------------------------------ 1. skip map rebuild
@pytest.mark.parametrize("path", ["/station/12108500", "/station/12108500/"])
def test_station_page_skips_map_rebuild(path):
    r = _call(path)
    assert r == (no_update, no_update, no_update)


def test_station_page_does_not_build_figure_even_with_data():
    gauges = [{"site_id": "1", "station_name": "A", "state": "WA",
               "latitude": 47.0, "longitude": -122.0}]
    args = [gauges] + [None] * 15 + [None]
    with patch.object(app_module.map_component, "create_gauge_map") as m:
        r = app_module.update_map_with_simplified_filters(*args, "/station/1")
    assert r == (no_update, no_update, no_update)
    m.assert_not_called()


@pytest.mark.parametrize("path", [None, "/"])
def test_non_station_path_behaviour_unchanged_loading_figure(path):
    fig, badge, results = _call(path)
    assert badge == "Loading..." and results == "Loading..."
    assert "Loading gauge data" in fig.layout.title.text


def test_pathname_param_is_optional_default_none():
    fig, badge, results = _call()
    assert badge == "Loading..." and results == "Loading..."


def test_map_callback_state_includes_url_pathname_and_selected_store():
    key = _map_cb_key()
    assert key is not None
    states = [(s["id"], s["property"]) for s in app_module.app.callback_map[key]["state"]]
    assert ("url", "pathname") in states
    assert states.index(("selected-gauge-store", "data")) < states.index(("url", "pathname"))


def test_map_callback_outputs_unchanged():
    key = _map_cb_key()
    assert key is not None
    assert key == "..gauge-map.figure...gauge-count-badge.children...results-count.children.."


# ----------------------------------------------------- 2. deep-link zoom
def _zoom_key():
    for k in app_module.app.callback_map:
        if "deep-link-zoom-dummy.data" in k:
            return k
    return None


def test_deep_link_zoom_store_in_layout():
    assert "deep-link-zoom-dummy" in _tree_ids(_get_layout())


def test_deep_link_zoom_callback_registered_with_inputs_and_states():
    key = _zoom_key()
    assert key is not None, "no callback writing deep-link-zoom-dummy.data"
    spec = app_module.app.callback_map[key]
    inputs = {(i["id"], i["property"]) for i in spec["inputs"]}
    states = {(s["id"], s["property"]) for s in spec["state"]}
    assert ("selected-gauge-store", "data") in inputs
    assert {("gauges-store", "data"), ("url", "search"), ("url", "pathname")} <= states


def _zoom_js():
    idx = APP_SRC.find("Output('deep-link-zoom-dummy'")
    if idx < 0:
        idx = APP_SRC.find('Output("deep-link-zoom-dummy"')
    assert idx >= 0, "Output('deep-link-zoom-dummy', ...) not found in app.py source"
    start = APP_SRC.rfind("app.clientside_callback(", 0, idx)
    assert start >= 0
    nxt = [APP_SRC.find(m, idx) for m in ("\napp.clientside_callback(", "\n@app.callback")]
    nxt = [n for n in nxt if n >= 0]
    return APP_SRC[start:min(nxt) if nxt else len(APP_SRC)]


def test_deep_link_zoom_js_uses_plotly_relayout():
    js = _zoom_js()
    assert "Plotly.relayout" in js


def test_deep_link_zoom_js_sets_map_center_and_zoom():
    js = _zoom_js()
    assert "map.center" in js and "map.zoom" in js


def test_deep_link_zoom_js_is_noop_on_station_pages():
    assert "station" in _zoom_js()


def test_deep_link_zoom_js_reads_site_query_param():
    js = _zoom_js()
    assert "site" in js and ("URLSearchParams" in js or "site=" in js)
