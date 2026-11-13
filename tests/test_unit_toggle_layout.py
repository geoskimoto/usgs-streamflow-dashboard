"""R7/R8: layout contains the flow-unit toggle and store (docs/UNIT_TOGGLE_PLAN.md)."""
import json

import app as app_module


def _layout():
    layout = app_module.app.layout
    return layout() if callable(layout) else layout


def _walk(node):
    if node is None or isinstance(node, (str, int, float, bool, dict)):
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)
        return
    yield node
    yield from _walk(getattr(node, "children", None))


def _find(wanted):
    for comp in _walk(_layout()):
        if getattr(comp, "id", None) == wanted:
            return comp
    return None


def test_layout_has_flow_unit_toggle():
    assert _find("flow-unit-toggle") is not None


def test_flow_unit_toggle_defaults_to_cfs():
    assert _find("flow-unit-toggle").value == "cfs"


def test_flow_unit_toggle_is_radio_items_with_cfs_and_cms_options():
    comp = _find("flow-unit-toggle")
    assert type(comp).__name__ == "RadioItems"
    values = [o["value"] if isinstance(o, dict) else o for o in comp.options]
    assert values == ["cfs", "cms"]
    labels = [o["label"] for o in comp.options]
    assert "m³/s" in labels[1]


def test_layout_has_flow_unit_store_defaulting_to_cfs():
    store = _find("flow-unit-store")
    assert store is not None
    assert type(store).__name__ == "Store"
    assert store.data == "cfs"


def test_flow_unit_store_has_no_persistence_r8():
    store = _find("flow-unit-store")
    assert store is not None
    assert getattr(store, "storage_type", None) not in ("local", "session")


def test_flow_unit_toggle_has_no_persistence_r8():
    comp = _find("flow-unit-toggle")
    assert comp is not None
    assert getattr(comp, "persistence", None) in (None, False)


def test_flow_unit_ids_unique_in_layout():
    ids = [getattr(c, "id", None) for c in _walk(_layout())]
    assert ids.count("flow-unit-toggle") == 1
    assert ids.count("flow-unit-store") == 1


def test_flow_unit_toggle_is_wired_as_callback_input():
    """Plot callbacks must take the toggle (or the store) as an Input."""
    cbs = app_module.app.callback_map
    found = False
    for key, spec in cbs.items():
        inputs = spec.get("inputs", [])
        if any(i.get("id") in ("flow-unit-toggle", "flow-unit-store") for i in inputs):
            found = True
    assert found, "no callback consumes flow-unit-toggle / flow-unit-store"
