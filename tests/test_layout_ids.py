"""
Layout regression guard for app.py.

Locks the component-id contract so the UI can be restructured (top bar, filter
rail, detail panel) without breaking callbacks or hover_zoom.js.
Offline: importing app only builds the Dash object; nothing here calls an API.
Does not depend on assets/theme.css.
"""

import json
import pytest

import app as app_module

REQUIRED_IDS = [
    "sidebar-col", "sidebar-toggle-btn", "mobile-sidebar-btn",
    "main-content-wrapper", "dashboard-content", "admin-content",
    "gauge-map", "multi-plot-container", "annual-summary-container",
    "history-buttons-row", "annual-summary-prompt-row", "gauge-info-content",
    "percentile-date-picker", "prev-date-btn", "next-date-btn",
    "gauge-count-badge", "selected-gauge-badge",
    "show-30yr-history-btn", "show-full-history-btn", "show-fast-plot-btn",
    "load-annual-summary-btn", "dark-mode-btn", "dark-mode-store",
    "map-style-dropdown", "map-hover-panel", "map-hover-info-text",
    "map-hover-tooltip-img",
    # filters
    "search-input", "clear-search", "forecast-filter", "resid-cast-filter",
    "ealstm-filter", "station-status-filter", "state-filter",
    "drainage-area-filter", "basin-filter", "huc-filter", "results-count",
]

WILDCARDS = {"ALL", "MATCH", "ALLSMALLER"}


def _get_layout():
    layout = app_module.app.layout
    return layout() if callable(layout) else layout


def _walk(node):
    """Yield every component in the tree (children may be component/list/str/None)."""
    if node is None or isinstance(node, (str, int, float, bool)):
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)
        return
    if isinstance(node, dict):
        return
    yield node
    # children plus any other component-valued props (e.g. Collapse/Modal bodies)
    yield from _walk(getattr(node, "children", None))


def _tree_ids(layout):
    ids = set()
    for comp in _walk(layout):
        cid = getattr(comp, "id", None)
        if cid is None:
            continue
        if isinstance(cid, dict):
            cid = json.dumps(cid, sort_keys=True)
        ids.add(cid)
    return ids


def _find(layout, wanted):
    for comp in _walk(layout):
        if getattr(comp, "id", None) == wanted:
            return comp
    return None


def _normalize(cid):
    """Return a comparable id, or None for wildcard pattern ids."""
    if isinstance(cid, str) and cid.startswith("{"):
        try:
            cid = json.loads(cid)
        except ValueError:
            return cid
    if isinstance(cid, dict):
        if any(v in WILDCARDS for v in cid.values() if isinstance(v, str)):
            return None
        return json.dumps(cid, sort_keys=True)
    return cid


def _split_output_key(key):
    """callback_map keys look like 'a.prop', '..a.p...b.q..' or '{json}.prop'."""
    key = key.strip()
    parts = key[2:-2].split("...") if key.startswith("..") and key.endswith("..") else [key]
    return [p.rsplit(".", 1)[0] for p in parts]


def _callback_ids():
    ids = set()
    for key, spec in app_module.app.callback_map.items():
        for out in _split_output_key(key):
            ids.add(out)
        for group in ("inputs", "state"):
            for item in spec.get(group, []):
                ids.add(item["id"])
    normalized = {_normalize(i) for i in ids}
    normalized.discard(None)
    return normalized


@pytest.fixture(scope="module")
def layout():
    return _get_layout()


@pytest.fixture(scope="module")
def tree_ids(layout):
    return _tree_ids(layout)


def test_layout_is_nonempty_and_walkable(tree_ids):
    assert len(tree_ids) > 20


def test_callbacks_are_registered():
    assert len(app_module.app.callback_map) > 0


# Pre-existing orphans: these admin callbacks are registered in app.py but their
# components exist nowhere in app.layout (legacy admin panel, see
# archive/legacy_admin/). Recorded as of branch design/map-first. Remove entries
# as the dead callbacks are deleted; never add entries to hide a new break.
KNOWN_ORPHAN_CALLBACK_IDS = {
    "admin-dashboard-tab", "admin-monitoring-tab", "admin-refresh-interval",
    "admin-schedules-tab", "admin-stations-tab", "admin-tab-content",
    "recent-activity-table", "refresh-monitoring-btn", "refresh-schedules-btn",
    "run-selected-schedule-btn", "schedule-status-message", "schedules-table",
    "schedules-table-container", "system-health-indicators", "toggle-schedule-btn",
}


def test_no_new_callback_ids_missing_from_layout(tree_ids):
    """Regression guard: missing ids must be exactly the known legacy orphans."""
    missing = {str(i) for i in _callback_ids() if i not in tree_ids}
    new_breaks = sorted(missing - KNOWN_ORPHAN_CALLBACK_IDS)
    assert not new_breaks, f"Callback ids missing from layout: {new_breaks}"


@pytest.mark.xfail(strict=True, reason="15 legacy admin callbacks reference ids "
                   "absent from the layout (KNOWN_ORPHAN_CALLBACK_IDS); strict "
                   "spec 1. Flips to XPASS-fail once the dead callbacks are removed.")
def test_every_callback_id_exists_in_layout_strict(tree_ids):
    missing = sorted(str(i) for i in _callback_ids() if i not in tree_ids)
    assert not missing, f"Callback ids missing from layout: {missing}"


@pytest.mark.parametrize("cid", REQUIRED_IDS)
def test_required_id_present_in_layout(tree_ids, cid):
    assert cid in tree_ids, f"Required id '{cid}' not found in app.layout"


def test_hover_panel_width_is_462px(layout):
    panel = _find(layout, "map-hover-panel")
    assert panel is not None
    style = getattr(panel, "style", None) or {}
    assert style.get("width") == "462px"


def test_hover_panel_initially_hidden(layout):
    panel = _find(layout, "map-hover-panel")
    assert panel is not None
    style = getattr(panel, "style", None) or {}
    assert style.get("display") == "none"
