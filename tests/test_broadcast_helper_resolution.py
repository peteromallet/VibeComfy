"""T3: Pin helper resolution with tests.

Asserts that resolved SetNode/GetNode/Reroute helpers never appear as
raw_call('GetNode' / 'SetNode' / 'Reroute' in emitted Python, across five
well-specified fixtures.
"""
from __future__ import annotations

from typing import Any

from vibecomfy.porting.emitter import (
    EmissionDiagnostic,
    HELPER_RESOLUTION_MULTI_SETNODE_COLLISION,
    emit_scratchpad_python,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _emit(wf: VibeWorkflow, *, diagnostics: list[EmissionDiagnostic] | None = None) -> str:
    """Emit a scratchpad so _resolve_helper_nodes_for_emission runs."""
    return emit_scratchpad_python(
        wf, source_path="tests/fixtures/helper_resolution.json", diagnostics=diagnostics
    )


def _assert_no_raw_helper_calls(text: str) -> None:
    """Assert the emitted Python contains none of raw_call('GetNode' / 'SetNode' / 'Reroute'."""
    for helper in ("GetNode", "SetNode", "Reroute"):
        assert f"raw_call('{helper}'" not in text, (
            f"Unexpected raw_call('{helper}' in emitted code. "
            f"Helper should have been resolved before emission."
        )
        # Also check double-quoted form just in case
        assert f'raw_call("{helper}"' not in text, (
            f"Unexpected raw_call(\"{helper}\" in emitted code."
        )


# ---------------------------------------------------------------------------
# fixture builders
# ---------------------------------------------------------------------------


def _wf_typed_reroute() -> VibeWorkflow:
    """Fixture 1: typed Reroute node between LoadImage and SaveImage."""
    wf = VibeWorkflow("test/typed_reroute", WorkflowSource("test/typed_reroute", provenance={"origin": "unit"}))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "test.png"})
    wf.nodes["2"] = VibeNode("2", "Reroute")
    wf.nodes["3"] = VibeNode("3", "SaveImage", inputs={"filename_prefix": "out"})
    wf.edges.append(VibeEdge("1", "0", "2", ""))
    wf.edges.append(VibeEdge("2", "0", "3", "images"))
    return wf


def _wf_raw_reroute_equivalent() -> VibeWorkflow:
    """Fixture 2: the same topology as fixture 1 — raw_call('Reroute',...) is
    indistinguishable from typed Reroute in the VibeNode model (both have
    class_type='Reroute').  Assert they resolve identically.
    """
    return _wf_typed_reroute()


def _wf_setnode_getnode_pair() -> VibeWorkflow:
    """Fixture 3: SetNode/GetNode broadcast pair — GetNode consumer redirected
    to the broadcast source (SetNode's input).
    """
    wf = VibeWorkflow("test/broadcast_pair", WorkflowSource("test/broadcast_pair", provenance={"origin": "unit"}))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "ref.png"})
    wf.nodes["2"] = VibeNode("2", "SetNode", widgets={"widget_0": "ref_image"})
    wf.nodes["3"] = VibeNode("3", "GetNode", widgets={"widget_0": "ref_image"})
    wf.nodes["4"] = VibeNode("4", "SaveImage", inputs={"filename_prefix": "out"})
    wf.edges.append(VibeEdge("1", "0", "2", "IMAGE"))
    wf.edges.append(VibeEdge("3", "0", "4", "images"))
    return wf


def _wf_reroute_chain_of_three() -> VibeWorkflow:
    """Fixture 4: Reroute-A → Reroute-B → Reroute-C chain.
    Consumer should be redirected to the ultimate source (LoadImage),
    not to an intermediate Reroute.
    """
    wf = VibeWorkflow("test/reroute_chain", WorkflowSource("test/reroute_chain", provenance={"origin": "unit"}))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "chain.png"})
    wf.nodes["2"] = VibeNode("2", "Reroute")
    wf.nodes["3"] = VibeNode("3", "Reroute")
    wf.nodes["4"] = VibeNode("4", "Reroute")
    wf.nodes["5"] = VibeNode("5", "SaveImage", inputs={"filename_prefix": "out"})
    wf.edges.append(VibeEdge("1", "0", "2", ""))
    wf.edges.append(VibeEdge("2", "0", "3", ""))
    wf.edges.append(VibeEdge("3", "0", "4", ""))
    wf.edges.append(VibeEdge("4", "0", "5", "images"))
    return wf


def _wf_multi_setnode_collision() -> VibeWorkflow:
    """Fixture 5: two SetNode nodes sharing the same broadcast name.
    First-by-node-id should win; a HELPER_RESOLUTION_MULTI_SETNODE_COLLISION
    warning diagnostic must be emitted.
    """
    wf = VibeWorkflow(
        "test/multi_setnode",
        WorkflowSource("test/multi_setnode", provenance={"origin": "unit"}),
    )
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "first.png"})
    wf.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "second.png"})
    wf.nodes["3"] = VibeNode("3", "SetNode", widgets={"widget_0": "shared_name"})
    wf.nodes["4"] = VibeNode("4", "SetNode", widgets={"widget_0": "shared_name"})
    wf.nodes["5"] = VibeNode("5", "GetNode", widgets={"widget_0": "shared_name"})
    wf.nodes["6"] = VibeNode("6", "SaveImage", inputs={"filename_prefix": "out"})
    # Each SetNode gets its own source; both share the same broadcast name.
    wf.edges.append(VibeEdge("1", "0", "3", "IMAGE"))
    wf.edges.append(VibeEdge("2", "0", "4", "IMAGE"))
    wf.edges.append(VibeEdge("5", "0", "6", "images"))
    return wf


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_typed_reroute_resolved_no_raw_call() -> None:
    """Typed Reroute is resolved; emitted output contains no raw_call('Reroute'."""
    text = _emit(_wf_typed_reroute())
    _assert_no_raw_helper_calls(text)
    # The consumer (SaveImage) should receive the source directly
    assert "LoadImage(" in text
    assert "SaveImage(" in text


def test_raw_call_reroute_equivalent_resolved_no_raw_call() -> None:
    """raw_call('Reroute',...) has the same class_type as typed Reroute,
    so it is resolved identically.
    """
    text = _emit(_wf_raw_reroute_equivalent())
    _assert_no_raw_helper_calls(text)
    assert "LoadImage(" in text
    assert "SaveImage(" in text


def test_setnode_getnode_pair_inlined_no_raw_call() -> None:
    """SetNode→GetNode broadcast pair: both are removed before emission."""
    text = _emit(_wf_setnode_getnode_pair())
    _assert_no_raw_helper_calls(text)
    # SaveImage's images input should be wired to LoadImage directly
    assert "LoadImage(" in text
    assert "SaveImage(" in text


def test_reroute_chain_of_three_collapsed_no_raw_call() -> None:
    """Chain of three Reroutes collapses to the ultimate source."""
    text = _emit(_wf_reroute_chain_of_three())
    _assert_no_raw_helper_calls(text)
    assert "LoadImage(" in text
    assert "SaveImage(" in text


def test_multi_setnode_collision_warns_and_picks_first_by_node_id() -> None:
    """Multi-SetNode same-name collision emits warning + first-by-node-id wins."""
    diags: list[EmissionDiagnostic] = []
    text = _emit(_wf_multi_setnode_collision(), diagnostics=diags)

    _assert_no_raw_helper_calls(text)

    # Must contain the collision warning
    collision_diags = [
        d for d in diags
        if d.code == HELPER_RESOLUTION_MULTI_SETNODE_COLLISION
    ]
    assert len(collision_diags) == 1, (
        f"Expected exactly one {HELPER_RESOLUTION_MULTI_SETNODE_COLLISION} diagnostic, "
        f"got {[d.code for d in diags]}"
    )
    cd = collision_diags[0]
    assert cd.severity == "warning"
    assert "shared_name" in cd.message
    # First-by-node-id should be "3" (lowest sorted node id among SetNodes 3, 4)
    assert cd.node_id == "3", f"Expected first-by-node-id '3', got {cd.node_id!r}"
    assert cd.class_type == "SetNode"
    assert cd.detail.get("broadcast") == "shared_name"
    assert cd.detail.get("node_ids") == ["3", "4"]

    # The output should use the first LoadImage's value (first.png, from node 1 → SetNode 3)
    assert "LoadImage(" in text
    assert "SaveImage(" in text
