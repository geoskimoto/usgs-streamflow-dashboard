"""
Per-station URL feature: pure helpers (usgs_dashboard/utils/station_url.py) and
app.py selection helpers. Written before implementation; offline and deterministic.

Spec readings (ambiguities):
 - parse_station_site_id: pathname id is URL-decoded; an encoded slash (%2F)
   decodes into the id (the "no further /" rule applies to the raw path split).
 - "Whitespace-only id" -> None for both path and ?site= forms.
"""
import pytest
import pandas as pd
from dash import html, no_update

try:
    from hypothesis import given, settings, strategies as st
    HAVE_HYPOTHESIS = True
except ImportError:  # pragma: no cover
    HAVE_HYPOTHESIS = False

from usgs_dashboard.utils import station_url as su
import app as app_module


# ---------------------------------------------------------------- pure module
def test_station_path_prefix_constant():
    assert su.STATION_PATH_PREFIX == "/station/"


def test_station_path_plain_id():
    assert su.station_path("12108500") == "/station/12108500"


def test_station_path_encodes_space_and_slash():
    p = su.station_path("a b/c")
    assert p == "/station/a%20b%2Fc"
    assert p[len("/station/"):].count("/") == 0


def test_map_view_url_plain():
    assert su.map_view_url("12108500") == "/?site=12108500"


def test_map_view_url_quotes_id():
    assert su.map_view_url("a b/c") == "/?site=a%20b%2Fc"


@pytest.mark.parametrize("v", [None, ""])
def test_map_view_url_empty_returns_root(v):
    assert su.map_view_url(v) == "/"


@pytest.mark.parametrize("path", ["/station/12108500", "/station/12108500/"])
def test_parse_station_path(path):
    assert su.parse_station_site_id(path) == "12108500"


def test_parse_decodes_path_id():
    assert su.parse_station_site_id("/station/a%20b") == "a b"


def test_parse_search_site_param():
    assert su.parse_station_site_id("/", "?site=123&x=1") == "123"


def test_parse_search_site_param_decoded():
    assert su.parse_station_site_id("/", "?site=a%20b") == "a b"


def test_parse_pathname_takes_precedence_over_search():
    assert su.parse_station_site_id("/station/111", "?site=222") == "111"


@pytest.mark.parametrize("path,search", [
    (None, None), ("", ""), ("/", ""), ("/admin", ""), ("/station/", ""),
    ("/station", ""), ("/", "?site="), ("/", "?other=1"), ("/", "?site=%20%20"),
    ("/station/%20", ""), ("/station/   ", ""), ("/station/a/b", ""),
])
def test_parse_returns_none_for_non_matches(path, search):
    assert su.parse_station_site_id(path, search) is None


def test_parse_handles_none_search_with_valid_path():
    assert su.parse_station_site_id("/station/1", None) == "1"


def test_parse_result_is_str():
    assert isinstance(su.parse_station_site_id("/station/123"), str)
    assert isinstance(su.parse_station_site_id("/", "?site=123"), str)


@pytest.mark.parametrize("path,expected", [
    ("/station/12108500", True), ("/station/12108500/", True),
    ("/station/", False), ("/station", False), ("/", False), (None, False),
    ("/admin", False), ("", False),
])
def test_is_station_page(path, expected):
    assert su.is_station_page(path) is expected


@pytest.mark.parametrize("sid", ["12108500", "a b", "a/b", "a?b=c&d", "100%", "é ü", "x#y", "a+b"])
def test_round_trip_station_path(sid):
    assert su.parse_station_site_id(su.station_path(sid)) == sid


@pytest.mark.parametrize("sid", ["12108500", "a b", "a/b", "a&b=c", "100%", "x#y", "a+b"])
def test_round_trip_map_view_url(sid):
    url = su.map_view_url(sid)
    path, _, query = url.partition("?")
    assert su.parse_station_site_id(path, "?" + query) == sid


if HAVE_HYPOTHESIS:
    _ids = st.text(min_size=1, max_size=30).filter(lambda s: s.strip() != "" and "\x00" not in s)

    @settings(max_examples=200, deadline=None)
    @given(_ids)
    def test_property_station_path_round_trip(sid):
        assert su.parse_station_site_id(su.station_path(sid)) == sid
        assert su.is_station_page(su.station_path(sid)) is True

    @settings(max_examples=200, deadline=None)
    @given(_ids)
    def test_property_map_view_round_trip(sid):
        path, _, q = su.map_view_url(sid).partition("?")
        assert su.parse_station_site_id(path, "?" + q) == sid

    @settings(max_examples=100, deadline=None)
    @given(st.text(max_size=40), st.text(max_size=40))
    def test_property_parse_never_raises_and_returns_str_or_none(p, s):
        r = su.parse_station_site_id(p, s)
        assert r is None or (isinstance(r, str) and r.strip() != "")
else:
    @pytest.mark.skip(reason="hypothesis not installed")
    def test_property_tests_skipped_without_hypothesis():
        pass


# ------------------------------------------------------------- app helpers
GAUGES = [
    {"site_id": "12108500", "station_name": "NEWAUKUM CREEK NEAR BLACK DIAMOND, WA",
     "state": "WA", "latitude": 47.28, "longitude": -122.0,
     "drainage_area": 27.0, "catchment_area": 70.0},
    {"site_id": "14105700", "station_name": "COLUMBIA RIVER AT THE DALLES, OR",
     "state": "OR", "latitude": 45.6, "longitude": -121.2,
     "drainage_area": None, "catchment_area": None},
]


def _walk(node):
    if node is None or isinstance(node, (str, int, float, bool)):
        return
    if isinstance(node, (list, tuple)):
        for n in node:
            yield from _walk(n)
        return
    if isinstance(node, dict):
        return
    yield node
    yield from _walk(getattr(node, "children", None))


def _text(node):
    out = []
    if isinstance(node, str):
        return node
    if isinstance(node, (list, tuple)):
        return " ".join(_text(n) for n in node)
    if node is None or isinstance(node, (int, float, bool, dict)):
        return "" if node is None or isinstance(node, dict) else str(node)
    return _text(getattr(node, "children", None))


def _anchors(children):
    return [c for c in _walk(children) if isinstance(c, html.A)]


def test_build_gauge_selection_unknown_id_returns_none():
    assert app_module.build_gauge_selection("nope", GAUGES) is None


def test_build_gauge_selection_tuple_shape_and_badge():
    r = app_module.build_gauge_selection("12108500", GAUGES)
    assert isinstance(r, tuple) and len(r) == 4
    sid, badge, style, info = r
    assert sid == "12108500"
    assert badge == "Selected: 12108500"
    assert style == {"display": "inline"}
    assert isinstance(info, list)


def test_build_gauge_selection_contains_name_and_state():
    info = app_module.build_gauge_selection("12108500", GAUGES)[3]
    txt = _text(info)
    assert "NEWAUKUM CREEK NEAR BLACK DIAMOND, WA" in txt
    assert "WA" in txt


def test_build_gauge_selection_has_station_page_link():
    info = app_module.build_gauge_selection("12108500", GAUGES)[3]
    hrefs = [(a.href, getattr(a, "target", None)) for a in _anchors(info)]
    assert ("/station/12108500", "_blank") in hrefs


def test_build_gauge_selection_link_uses_station_path():
    info = app_module.build_gauge_selection("14105700", GAUGES)[3]
    assert any(a.href == su.station_path("14105700") and a.target == "_blank"
               for a in _anchors(info))


def test_url_selection_falsy_site_id_no_update():
    for sid in (None, ""):
        assert app_module.url_selection_outputs(sid, GAUGES, None, True) == (no_update,) * 4


@pytest.mark.parametrize("g", [None, []])
def test_url_selection_falsy_gauges_no_update(g):
    assert app_module.url_selection_outputs("12108500", g, None, True) == (no_update,) * 4


def test_url_selection_does_not_clobber_existing_click():
    r = app_module.url_selection_outputs("12108500", GAUGES, "14105700", False)
    assert r == (no_update,) * 4


def test_url_selection_url_changed_overrides_current_selection():
    r = app_module.url_selection_outputs("12108500", GAUGES, "14105700", True)
    exp = app_module.build_gauge_selection("12108500", GAUGES)
    assert r[:3] == exp[:3]
    assert _text(r[3]) == _text(exp[3])


def test_url_selection_no_current_selection_selects_even_if_unchanged():
    r = app_module.url_selection_outputs("12108500", GAUGES, None, False)
    exp = app_module.build_gauge_selection("12108500", GAUGES)
    assert r[:3] == exp[:3]
    assert _text(r[3]) == _text(exp[3])


def test_url_selection_not_found():
    r = app_module.url_selection_outputs("99999999", GAUGES, None, True)
    assert len(r) == 4
    assert r[0] is None
    assert r[1] == ""
    assert r[2] == {"display": "none"}
    txt = _text(r[3]).lower()
    assert "not found" in txt
    assert "99999999" in txt


def test_handle_gauge_selection_click_equals_build_gauge_selection():
    click = {"points": [{"customdata": "12108500"}]}
    got = app_module.handle_gauge_selection(click, GAUGES)
    expected = app_module.build_gauge_selection("12108500", GAUGES)
    assert expected is not None
    assert got[:3] == expected[:3]
    assert _text(got[3]) == _text(expected[3])


def test_handle_gauge_selection_unknown_click_no_update():
    click = {"points": [{"customdata": "nope"}]}
    assert app_module.handle_gauge_selection(click, GAUGES) == (no_update,) * 4


# ------------------------------------------------------ callback registration
def test_url_driven_callback_registered():
    cmap = app_module.app.callback_map
    keys = [k for k in cmap if "selected-gauge-store.data" in k
            and any(i["id"] == "url" and i["property"] == "pathname" for i in cmap[k]["inputs"])]
    assert keys, "no callback writing selected-gauge-store.data with url.pathname input"
    inputs = {(i["id"], i["property"]) for i in cmap[keys[0]]["inputs"]}
    assert ("url", "pathname") in inputs
    assert ("url", "search") in inputs
    assert ("gauges-store", "data") in inputs
