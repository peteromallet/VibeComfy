"""Tests for the vibecomfy.comfy_nodes.routes._handle_roundtrip core helper.

All tests call _handle_roundtrip or the engine primitives it wraps directly —
no aiohttp, no ComfyUI boot required.

Fixture: tests/fixtures/walking_skeleton/flat.json — a 7-node litegraph UI JSON
with no prior vibecomfy_uid stamps, making guard_emit a no-op (empty scope_uids).
"""

from __future__ import annotations

import json
import pathlib

import pytest

_FIXTURE_PATH = (
    pathlib.Path(__file__).parent / "fixtures" / "walking_skeleton" / "flat.json"
)


@pytest.fixture(scope="module")
def flat_fixture() -> dict:
    return json.loads(_FIXTURE_PATH.read_text())


@pytest.fixture(scope="module")
def schema_provider():
    from vibecomfy.schema import get_schema_provider

    return get_schema_provider("local")


# ---------------------------------------------------------------------------
# (a) Response envelope shape
# ---------------------------------------------------------------------------


def test_response_envelope_shape(flat_fixture, schema_provider):
    """Route returns {graph, report: {change, recovery, felt}, version: 1}."""
    from vibecomfy.comfy_nodes.routes import _handle_roundtrip

    result = _handle_roundtrip({"graph": flat_fixture}, schema_provider=schema_provider)

    assert "graph" in result, f"expected 'graph' key, got {list(result)}"
    assert "report" in result, f"expected 'report' key, got {list(result)}"
    assert result["version"] == 1

    report = result["report"]
    assert "change" in report, f"expected 'change' in report, got {list(report)}"
    assert "recovery" in report, f"expected 'recovery' in report, got {list(report)}"
    assert "felt" in report, f"expected 'felt' in report, got {list(report)}"

    change = report["change"]
    assert "content_edits" in change, (
        f"expected 'content_edits' in change, got {list(change)}"
    )
    assert "identity_stabilization" in change
    assert report["felt"]["ok"] is True


# ---------------------------------------------------------------------------
# (b) Unmodified round-trip produces non-empty preserved
# Tested via the direct engine path (convert_to_vibe_format → emit_ui_json)
# with a prior_store built from the first emission.  The route itself does not
# accept a prior_store; this test validates the underlying engine capability.
# ---------------------------------------------------------------------------


def test_engine_roundtrip_preserved_nonempty(flat_fixture, schema_provider):
    """Engine round-trip with prior_store: preserved is non-empty."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.layout_store import store_from_ui_json
    from vibecomfy.porting.ui_emitter import emit_ui_json

    # Pass 1: initial emit stamps vibecomfy_uid into every node's properties.
    wf1 = convert_to_vibe_format(flat_fixture)
    emitted1 = emit_ui_json(wf1, schema_provider=schema_provider)

    # Build the prior store that tracks every uid from pass 1.
    prior_store = store_from_ui_json(emitted1)
    assert prior_store.get("entries"), "prior_store must have entries after first emit"

    # Pass 2: re-convert the emitted output and re-emit with the prior store.
    wf2 = convert_to_vibe_format(emitted1)
    change_report_out: list = []
    emit_ui_json(
        wf2,
        schema_provider=schema_provider,
        prior_store=prior_store,
        change_report_out=change_report_out,
    )

    assert change_report_out, "change_report_out should be populated after emit"
    preserved = change_report_out[0].content_edits.preserved
    assert len(preserved) > 0, (
        f"expected non-empty preserved in unmodified round-trip, got {preserved!r}"
    )


# ---------------------------------------------------------------------------
# (c) recovery has one entry per emitted node
# ---------------------------------------------------------------------------


def test_recovery_one_entry_per_emitted_node(flat_fixture, schema_provider):
    """Every emitted node id appears in the recovery report."""
    from vibecomfy.comfy_nodes.routes import _handle_roundtrip

    result = _handle_roundtrip({"graph": flat_fixture}, schema_provider=schema_provider)

    assert "graph" in result, f"route failed: {result}"
    emitted_node_ids = {str(n["id"]) for n in result["graph"]["nodes"]}
    recovery_node_ids = {
        str(r["node_id"])
        for r in result["report"]["recovery"]
        if r.get("node_id") is not None
    }
    missing = emitted_node_ids - recovery_node_ids
    assert not missing, (
        f"emitted nodes {missing!r} have no recovery entry; "
        f"recovery ids: {recovery_node_ids!r}"
    )


# ---------------------------------------------------------------------------
# (d) Structural equivalence between route output and direct engine call
# ---------------------------------------------------------------------------


def test_structural_equivalence_with_direct_engine(flat_fixture, schema_provider):
    """Route output is structurally equivalent to a direct emit_ui_json call.

    Checks: same uid set, same class_type per uid, same edge set
    (not byte-for-byte — per gate flag correctness-6/issue_hints-3).
    """
    from vibecomfy.comfy_nodes.routes import _handle_roundtrip
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import emit_ui_json

    # Route path
    route_result = _handle_roundtrip(
        {"graph": flat_fixture}, schema_provider=schema_provider
    )
    assert "graph" in route_result, f"route failed: {route_result}"
    route_graph = route_result["graph"]

    # Direct engine path — mirrors what the route does internally
    wf = convert_to_vibe_format(flat_fixture)
    direct_graph = emit_ui_json(
        wf,
        schema_provider=schema_provider,
        guard_original_ui=flat_fixture,
    )

    # uid set
    route_uids = {n["properties"]["vibecomfy_uid"] for n in route_graph["nodes"]}
    direct_uids = {n["properties"]["vibecomfy_uid"] for n in direct_graph["nodes"]}
    assert route_uids == direct_uids, (
        f"uid sets differ — route: {route_uids!r}, direct: {direct_uids!r}"
    )

    # class_type per uid
    route_ct = {n["properties"]["vibecomfy_uid"]: n["type"] for n in route_graph["nodes"]}
    direct_ct = {
        n["properties"]["vibecomfy_uid"]: n["type"] for n in direct_graph["nodes"]
    }
    assert route_ct == direct_ct, (
        f"class_type mismatch — route: {route_ct!r}, direct: {direct_ct!r}"
    )

    # Edge set: (from_node, from_slot, to_node, to_slot)
    route_edges = {(l[1], l[2], l[3], l[4]) for l in route_graph.get("links", [])}
    direct_edges = {(l[1], l[2], l[3], l[4]) for l in direct_graph.get("links", [])}
    assert route_edges == direct_edges, (
        f"edge set mismatch — route: {route_edges!r}, direct: {direct_edges!r}"
    )


# ---------------------------------------------------------------------------
# (e) Malformed payload returns error envelope instead of raising
# ---------------------------------------------------------------------------


def test_malformed_payload_returns_error_envelope():
    """Malformed payload returns {error, kind} dict, never raises."""
    from vibecomfy.comfy_nodes.routes import _handle_roundtrip

    result = _handle_roundtrip({"graph": {"nodes": "oops"}})

    assert "error" in result, f"expected 'error' in result, got {list(result)}"
    assert "kind" in result, f"expected 'kind' in result, got {list(result)}"
    assert isinstance(result["error"], str)
    assert isinstance(result["kind"], str)
    assert "graph" not in result, "error envelope must not contain 'graph'"


def test_validated_failure_response_accept_preserves_nested_recovery() -> None:
    from vibecomfy.comfy_nodes.agent_contracts import FailureKind, failure_envelope
    from vibecomfy.comfy_nodes.routes import _validated_failure_response

    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "scoped_accept_conflict",
    }
    failure = failure_envelope(
        FailureKind.STALE_STATE_MISMATCH,
        "accept",
        agent_failure_context={
            "explanation": "Scoped accept verification failed.",
            "issues": [
                {
                    "code": "scoped_conflict",
                    "detail": "Node 2 prompt drifted after submit.",
                    "rebaseline_recovery": recovery,
                }
            ],
        },
    )

    payload = _validated_failure_response("accept", failure)

    assert payload["rebaseline_recovery"] == recovery
    assert payload["outcome"]["rebaseline_recovery"] == recovery
    assert payload["agent_failure_context"]["issues"] == [
        {
            "code": "scoped_conflict",
            "detail": "Node 2 prompt drifted after submit.",
            "rebaseline_recovery": recovery,
        }
    ]
