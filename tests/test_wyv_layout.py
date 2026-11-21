"""Layout/callback contract for the Water Year Volume card (R18-R23).

Written BEFORE the implementation; expected to fail until app.py has the card.

NAMES USED (plan fixes none beyond the callback inputs it lists):
  wyv-section  container Div, style display:none initially (R18)
  wyv-mode     dbc.RadioItems, options 'cumulative' | 'daily', default 'cumulative'
  wyv-unit     dbc.RadioItems, options 'kaf' | 'cfs-days', default 'kaf'
  wyv-graph    dcc.Graph (or a container whose children hold the figure)
Callback 1: Output wyv-section.style (show/hide + reset), Input annual-summary-requested.
Callback 2: Inputs annual-summary-requested, wyv-mode, wyv-unit, dark-mode-store;
            NO Input flow-unit-store (R21); it writes into wyv-graph / its container.
"""
import json

import pytest

import app as app_module
from tests.test_layout_ids import _find, _get_layout, _tree_ids, _split_output_key

NEW_IDS = ["wyv-section", "wyv-mode", "wyv-unit", "wyv-graph"]


@pytest.fixture(scope="module")
def layout():
    return _get_layout()


@pytest.fixture(scope="module")
def tree_ids(layout):
    return _tree_ids(layout)


def _wyv_callbacks():
    out = []
    for key, spec in app_module.app.callback_map.items():
        ins = {i["id"] for i in spec.get("inputs", [])}
        states = {i["id"] for i in spec.get("state", [])}
        outs = set(_split_output_key(key))
        if any(str(i).startswith("wyv-") for i in ins | states | outs):
            out.append((key, spec, ins, states, outs))
    return out


def _option_values(comp):
    return [o["value"] if isinstance(o, dict) else o for o in comp.options]


@pytest.mark.parametrize("cid", NEW_IDS)
def test_r23_new_id_present_in_static_layout(tree_ids, cid):
    assert cid in tree_ids


def test_r23_every_wyv_callback_id_exists_in_layout(tree_ids):
    cbs = _wyv_callbacks()
    assert cbs, "no callbacks reference wyv-* ids"
    for key, spec, ins, states, outs in cbs:
        for cid in ins | states | outs:
            assert cid in tree_ids, f"{cid} (callback {key}) missing from layout"


def test_r23_wyv_section_sits_after_annual_summary_container(layout):
    from tests.test_layout_ids import _walk
    order = [getattr(c, "id", None) for c in _walk(layout)]
    assert order.index("wyv-section") > order.index("annual-summary-container")


def test_r18_section_hidden_initially(layout):
    sec = _find(layout, "wyv-section")
    assert (getattr(sec, "style", None) or {}).get("display") == "none"


def test_r18_visibility_callback_driven_by_annual_summary_requested():
    hits = [c for c in _wyv_callbacks()
            if "wyv-section" in c[4] and "annual-summary-requested" in c[2]]
    assert hits, "no callback shows/hides wyv-section from annual-summary-requested"


def test_r18_section_is_not_inside_annual_summary_container(layout):
    cont = _find(layout, "annual-summary-container")
    assert _find(cont, "wyv-section") is None


def test_r19_mode_control_options_and_default(layout):
    c = _find(layout, "wyv-mode")
    assert c.value == "cumulative"
    assert _option_values(c) == ["cumulative", "daily"]


def test_r19_unit_control_options_and_default(layout):
    c = _find(layout, "wyv-unit")
    assert c.value == "kaf"
    assert _option_values(c) == ["kaf", "cfs-days"]


def test_r19_graph_component_is_a_graph(layout):
    g = _find(layout, "wyv-graph")
    assert type(g).__name__ == "Graph"


def test_r20_render_callback_inputs_include_mode_unit_request_and_theme():
    hits = [c for c in _wyv_callbacks() if "wyv-mode" in c[2]]
    assert len(hits) == 1
    ins = hits[0][2]
    assert {"wyv-mode", "wyv-unit", "annual-summary-requested", "dark-mode-store"} <= ins


def test_r21_render_callback_does_not_take_flow_unit_store_as_input():
    for key, spec, ins, states, outs in _wyv_callbacks():
        assert "flow-unit-store" not in ins, key


def test_r21_flow_unit_store_is_not_even_a_state_of_wyv_callbacks():
    # R4: cfs/cms has no effect on volume values or labels
    for key, spec, ins, states, outs in _wyv_callbacks():
        assert "flow-unit-store" not in states, key


def test_r22_dark_mode_store_is_an_input_not_state():
    hit = [c for c in _wyv_callbacks() if "wyv-mode" in c[2]][0]
    assert "dark-mode-store" in hit[2]


def test_r22_render_callback_reads_context_as_state():
    hit = [c for c in _wyv_callbacks() if "wyv-mode" in c[2]][0]
    assert {"selected-gauge-store", "gauges-store"} <= hit[3]


def test_render_callback_writes_into_the_card():
    hit = [c for c in _wyv_callbacks() if "wyv-mode" in c[2]][0]
    assert any(o in ("wyv-graph", "wyv-section", "wyv-container") or o.startswith("wyv-")
               for o in hit[4])


def test_wyv_callbacks_use_no_wildcard_ids():
    for key, spec, ins, states, outs in _wyv_callbacks():
        for cid in ins | states | outs:
            assert not str(cid).startswith("{"), cid


def test_existing_annual_summary_callback_still_depends_on_flow_unit_store():
    # Non-goal: the other cards are unchanged.
    hits = [spec for key, spec in app_module.app.callback_map.items()
            if "annual-summary-container.children" in key
            and "flow-unit-store" in {i["id"] for i in spec.get("inputs", [])}]
    assert hits
