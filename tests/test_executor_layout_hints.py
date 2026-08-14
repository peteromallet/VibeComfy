"""Tests for the agent-invoked layout_hints tool (M2).

The module must be agent-invoked only: the first test asserts that importing
the classify/pipeline executor core never pulls in layout analysis, and the
classify message builder rejects a ``layout_hint`` kwarg (its injection point
was removed).
"""

from __future__ import annotations

import json
import sys

# Order matters: import the classify/pipeline surface BEFORE layout_hints so we
# can prove nothing in that path imports layout analysis automatically.
from vibecomfy.executor import core as _executor_core  # noqa: F401 — guard import
from vibecomfy.executor import prompts as executor_prompts
from vibecomfy.executor import agent_backend as executor_agent_backend

assert "vibecomfy.executor.layout_hints" not in sys.modules, (
    "classify/pipeline import chain pulled in layout_hints automatically"
)

from vibecomfy.executor.layout_hints import (  # noqa: E402
    DIAG_EMPTY_GRAPH,
    DIAG_INVALID_ANCHORS,
    DIAG_INVALID_OPERATION,
    DIAG_LAYOUT_FALLBACK,
    DIAG_MISSING_ANCHORS,
    DIAG_NO_INSERTION_POINTS,
    DIAG_UNRESOLVED_ANCHOR,
    LayoutAnchor,
    LayoutCandidate,
    LayoutHintsResult,
    OPERATION_CONNECT,
    OPERATION_INSERT,
    OPERATION_MOVE,
    OPERATION_REORGANISE,
    RELATION_LAST_RESORT,
    RELATION_RIGHT_OF,
    layout_graph_hash,
    layout_hints,
    layout_hints_tool,
)
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus


def _readable_layout_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [0, 0],
                "size": [160, 80],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "pos": [320, 0],
                "size": [160, 80],
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [640, 0],
                "size": [160, 80],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
        ],
        "groups": [],
    }


def _bad_layout_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [100, 100],
                "size": [300, 100],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "properties": {"vibecomfy_uid": "sample"},
                "pos": [50, 110],
                "size": [300, 100],
                "inputs": [{"name": "image", "type": "IMAGE", "link": 10}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [11]}],
            },
            {
                "id": 3,
                "type": "SaveImage",
                "class_type": "SaveImage",
                "properties": {"vibecomfy_uid": "save"},
                "pos": [80, 120],
                "size": [300, 100],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 11}],
            },
            {
                "id": 4,
                "type": "Reroute",
                "class_type": "Reroute",
                "properties": {"vibecomfy_uid": "reroute"},
                "pos": [900, 900],
                "size": [40, 40],
                "inputs": [{"name": "", "type": "*", "link": 12}],
                "outputs": [{"name": "", "type": "*", "links": [13]}],
            },
            {
                "id": 5,
                "type": "PreviewImage",
                "class_type": "PreviewImage",
                "properties": {"vibecomfy_uid": "preview"},
                "pos": [170, 130],
                "size": [300, 100],
                "inputs": [{"name": "images", "type": "IMAGE", "link": 13}],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 2, 0, 3, 0, "IMAGE"],
            [12, 1, 0, 4, 0, "IMAGE"],
            [13, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [
            {
                "title": "Too small",
                "bounding": [0, 0, 200, 140],
                "nodes": [1, 2],
            }
        ],
    }


def _single_node_graph() -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "properties": {"vibecomfy_uid": "load"},
                "pos": [0, 0],
                "size": [160, 80],
                "outputs": [],
            }
        ],
        "links": [],
        "groups": [],
    }


# ── tool returns anchors, signals, hash, diagnostics ──────────────────────


def test_layout_hints_insert_returns_anchors_signals_hash_diagnostics() -> None:
    result = layout_hints(
        _single_node_graph(),
        OPERATION_INSERT,
        anchors={"upscale": "load"},
    )

    assert isinstance(result, LayoutHintsResult)
    assert len(result.graph_hash) == 64
    assert all(character in "0123456789abcdef" for character in result.graph_hash)
    assert result.operation == OPERATION_INSERT
    assert result.fallback_used is False
    assert result.signals["node_count"] == 1
    assert result.signals["edge_count"] == 0
    # A lone node yields spacing_density 1.0 (existing geometry assessment);
    # signals are evidence only and never influence the placement itself.
    assert result.signals["verdict"] == "needs_reorganise"
    assert result.signals["metrics"]["overlap_count"] == 0
    assert not result.signals["issues"] or "SPACING_DENSITY_HIGH" in result.signals["issues"]

    assert len(result.anchors) == 1
    anchor = result.anchors[0]
    assert isinstance(anchor, LayoutAnchor)
    assert anchor.target == "upscale"
    assert anchor.anchor == "load"
    assert anchor.relation == RELATION_RIGHT_OF
    # Right-of placement math: anchor.x + anchor.w + gap(40), same y.
    assert anchor.position == (200.0, 0.0)
    assert anchor.reason == "right_of_anchor"

    assert not result.candidates
    assert not result.diagnostics


def test_layout_hints_insert_collision_uses_spiral_ray_and_never_overlaps() -> None:
    result = layout_hints(
        _readable_layout_ui(),
        OPERATION_INSERT,
        anchors={"new_node": "load"},
    )

    assert len(result.anchors) == 1
    anchor = result.anchors[0]
    assert anchor.relation == RELATION_RIGHT_OF
    assert anchor.reason == "spiral_ray_search"
    assert result.signals["verdict"] == "ok"
    x, y = anchor.position
    # The candidate must not overlap any existing node bbox.
    for node in _readable_layout_ui()["nodes"]:
        nx, ny = node["pos"]
        nw, nh = node["size"]
        assert not (x < nx + nw and x + 320 > nx and y < ny + nh and y + 30 > ny), (
            f"candidate {anchor.position} overlaps node {node['properties']['vibecomfy_uid']}"
        )


def test_layout_hints_anchors_resolve_by_node_id_as_well_as_uid() -> None:
    result = layout_hints(
        _single_node_graph(),
        OPERATION_INSERT,
        anchors={"new_node": 1},  # id, not uid
    )

    assert len(result.anchors) == 1
    assert result.anchors[0].anchor == "load"
    assert result.anchors[0].relation == RELATION_RIGHT_OF
    assert result.anchors[0].position == (200.0, 0.0)


def test_layout_hints_signals_expose_poor_geometry_as_evidence_only() -> None:
    result = layout_hints(_bad_layout_ui(), OPERATION_INSERT, anchors={"x": "load"})

    signals = result.signals
    assert signals["verdict"] == "needs_reorganise"
    assert signals["metrics"]["overlap_count"] == 6
    assert signals["metrics"]["backward_edge_ratio"] == 0.3333
    assert signals["metrics"]["spacing_density"] > 1.0
    assert "OVERLAPPING_NODES" in signals["issues"]
    assert "BACKWARD_EDGE_RATIO_HIGH" in signals["issues"]
    # Signals carry numbers, never instructions.
    assert json.dumps(result.to_dict())


def test_layout_graph_hash_is_deterministic_and_sensitive_to_geometry() -> None:
    graph = _readable_layout_ui()
    assert layout_graph_hash(graph) == layout_graph_hash(graph)

    moved = json.loads(json.dumps(graph))
    moved["nodes"][2]["pos"] = [700, 10]
    assert layout_graph_hash(moved) != layout_graph_hash(graph)


# ── geometry fallback is explicit and recorded ────────────────────────────


def test_unresolved_anchor_is_last_resort_with_reason_and_anchors() -> None:
    result = layout_hints(
        _readable_layout_ui(),
        OPERATION_INSERT,
        anchors={"new_node": "does_not_exist"},
    )

    assert result.fallback_used is True
    assert len(result.anchors) == 1
    anchor = result.anchors[0]
    assert anchor.relation == RELATION_LAST_RESORT
    assert anchor.reason == "no_anchor_resolved"
    assert anchor.anchor == "does_not_exist"
    assert anchor.position == (40.0, 40.0)

    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert DIAG_UNRESOLVED_ANCHOR in codes
    assert DIAG_LAYOUT_FALLBACK in codes
    fallback = next(
        diagnostic
        for diagnostic in result.diagnostics
        if diagnostic.code == DIAG_LAYOUT_FALLBACK
    )
    assert fallback.details["anchors"][0]["target"] == "new_node"
    assert fallback.details["anchors"][0]["anchor"] == "does_not_exist"


def test_move_with_unresolved_target_is_last_resort() -> None:
    result = layout_hints(
        _readable_layout_ui(),
        OPERATION_MOVE,
        anchors={"ghost": "load"},
    )

    assert result.fallback_used is True
    assert result.anchors[0].relation == RELATION_LAST_RESORT
    assert result.anchors[0].reason == "no_target_resolved"
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert DIAG_UNRESOLVED_ANCHOR in codes
    assert DIAG_LAYOUT_FALLBACK in codes


def test_move_places_existing_node_relative_to_anchor_without_overlap() -> None:
    result = layout_hints(
        _readable_layout_ui(),
        OPERATION_MOVE,
        anchors={"sample": "load"},
    )

    assert result.fallback_used is False
    assert len(result.anchors) == 1
    anchor = result.anchors[0]
    assert anchor.target == "sample"
    assert anchor.anchor == "load"
    # The right-of spot is blocked by the sampler itself; the spiral search
    # lands above the loader (deterministic first free ray).
    assert anchor.reason == "spiral_ray_search"
    assert anchor.relation == "above"
    x, y = anchor.position
    for node in _readable_layout_ui()["nodes"]:
        nx, ny = node["pos"]
        nw, nh = node["size"]
        assert not (x < nx + nw and x + 160 > nx and y < ny + nh and y + 80 > ny)


# ── operation-specific candidates ─────────────────────────────────────────


def test_insert_without_anchors_uses_free_output_sockets() -> None:
    result = layout_hints(_readable_layout_ui(), OPERATION_INSERT)

    assert result.fallback_used is False
    assert len(result.anchors) == 1
    anchor = result.anchors[0]
    assert anchor.target == "<new:save>"
    assert anchor.anchor == "save"
    assert anchor.relation == RELATION_RIGHT_OF
    assert anchor.position == (840.0, 0.0)
    assert anchor.reason == "right_of_anchor"


def test_insert_with_no_free_socket_reports_no_insertion_points() -> None:
    fully_wired = {
        "nodes": [
            {
                "id": 1,
                "type": "A",
                "class_type": "A",
                "properties": {"vibecomfy_uid": "a"},
                "pos": [0, 0],
                "size": [100, 30],
            },
            {
                "id": 2,
                "type": "B",
                "class_type": "B",
                "properties": {"vibecomfy_uid": "b"},
                "pos": [200, 0],
                "size": [100, 30],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "X"],
            [11, 2, 0, 1, 0, "Y"],
        ],
        "groups": [],
    }
    result = layout_hints(fully_wired, OPERATION_INSERT)

    assert result.anchors == ()
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert DIAG_NO_INSERTION_POINTS in codes


def test_connect_returns_link_midpoint_candidates() -> None:
    result = layout_hints(_readable_layout_ui(), OPERATION_CONNECT)

    assert len(result.candidates) == 2
    first, second = result.candidates
    assert isinstance(first, LayoutCandidate)
    assert first.kind == "position"
    assert first.reason == "connect_midpoint"
    assert first.target == "link:10"
    assert first.position == (240.0, 40.0)
    assert second.target == "link:11"
    assert second.position == (560.0, 40.0)


def test_reorganise_returns_component_and_existing_group_candidates() -> None:
    result = layout_hints(_bad_layout_ui(), OPERATION_REORGANISE)

    kinds = {(candidate.kind, candidate.reason) for candidate in result.candidates}
    assert (("group", "connected_component")) in kinds
    assert (("group", "existing_group")) in kinds
    component = next(
        candidate
        for candidate in result.candidates
        if candidate.reason == "connected_component"
    )
    x, y, w, h = component.bounds
    # Bad graph: min node pos is [50, 100]; pad 24 each side.
    assert x == 26.0 and y == 76.0 and w > 0 and h > 0
    existing = next(
        candidate
        for candidate in result.candidates
        if candidate.reason == "existing_group"
    )
    assert existing.target == "Too small"
    assert existing.bounds == (0.0, 0.0, 200.0, 140.0)


# ── typed tool envelope ───────────────────────────────────────────────────


def test_layout_hints_tool_returns_ok_with_full_payload() -> None:
    tool = layout_hints_tool(
        _single_node_graph(),
        OPERATION_INSERT,
        anchors={"upscale": "load"},
    )

    assert isinstance(tool, ToolResult)
    assert tool.tool_name == "layout_hints"
    assert tool.status is ToolStatus.OK
    assert tool.result["graph_hash"] == layout_graph_hash(_single_node_graph())
    assert tool.result["operation"] == OPERATION_INSERT
    assert len(tool.result["anchors"]) == 1
    # ToolResult freezes the payload: tuples come back as tuples.
    assert tool.result["anchors"][0]["position"] == (200.0, 0.0)
    assert tool.result["signals"]["verdict"] == "needs_reorganise"
    assert tool.result["fallback_used"] is False
    assert not tool.result["diagnostics"]

    # The ToolResult envelope round-trips through the F01 contract.
    restored = ToolResult.from_dict(tool.to_dict())
    assert restored == tool


def test_layout_hints_tool_invalid_operation_is_invalid_request() -> None:
    tool = layout_hints_tool(_readable_layout_ui(), "explode")

    assert tool.status is ToolStatus.INVALID_REQUEST
    codes = {diagnostic.code for diagnostic in tool.diagnostics}
    assert DIAG_INVALID_OPERATION in codes


def test_layout_hints_tool_empty_graph_is_no_results() -> None:
    tool = layout_hints_tool({"nodes": [], "links": [], "groups": []}, OPERATION_INSERT)

    assert tool.status is ToolStatus.NO_RESULTS
    codes = {diagnostic.code for diagnostic in tool.diagnostics}
    assert DIAG_EMPTY_GRAPH in codes
    assert tool.result["signals"]["node_count"] == 0


def test_layout_hints_tool_non_mapping_graph_is_invalid_request() -> None:
    tool = layout_hints_tool(None, OPERATION_INSERT)
    assert tool.status is ToolStatus.INVALID_REQUEST


def test_layout_hints_tool_bad_anchors_shape_is_invalid_request() -> None:
    tool = layout_hints_tool(_readable_layout_ui(), OPERATION_INSERT, anchors=42)

    assert tool.status is ToolStatus.INVALID_REQUEST
    codes = {diagnostic.code for diagnostic in tool.diagnostics}
    assert DIAG_INVALID_ANCHORS in codes


def test_layout_hints_tool_move_without_anchors_is_invalid_request() -> None:
    tool = layout_hints_tool(_readable_layout_ui(), OPERATION_MOVE)

    assert tool.status is ToolStatus.INVALID_REQUEST
    codes = {diagnostic.code for diagnostic in tool.diagnostics}
    assert DIAG_MISSING_ANCHORS in codes


def test_layout_hints_result_round_trips_json_safely() -> None:
    result = layout_hints(
        _readable_layout_ui(),
        OPERATION_REORGANISE,
    )
    payload = result.to_dict()
    assert json.dumps(payload)  # JSON-safe

    restored = LayoutHintsResult.from_dict(payload)
    assert restored == result
    assert restored.to_dict() == payload


def test_fallback_result_round_trips() -> None:
    result = layout_hints(
        _readable_layout_ui(),
        OPERATION_INSERT,
        anchors={"new_node": "nope"},
    )
    restored = LayoutHintsResult.from_dict(result.to_dict())
    assert restored == result
    assert restored.fallback_used is True


# ── no automatic invocation in the classify/pipeline path ─────────────────


def test_classify_message_builder_rejects_layout_hint_kwarg() -> None:
    try:
        executor_prompts.build_classify_messages(
            "make this readable",
            has_graph=True,
            layout_hint={"verdict": "needs_reorganise"},
        )
    except TypeError:
        pass
    else:
        raise AssertionError("build_classify_messages still accepts layout_hint")


def test_run_classify_turn_rejects_layout_hint_kwarg() -> None:
    try:
        executor_agent_backend.run_classify_turn(
            "hello",
            route="openrouter",
            model="test",
            layout_hint={"verdict": "ok"},
        )
    except TypeError:
        pass
    else:
        raise AssertionError("run_classify_turn still accepts layout_hint")


def test_fresh_interpreter_classify_import_never_loads_layout_hints() -> None:
    """A clean interpreter importing the executor core must not load layout_hints."""
    import subprocess

    probe = (
        "import sys\n"
        "from vibecomfy.executor import core\n"
        "from vibecomfy.executor import prompts\n"
        "from vibecomfy.executor import agent_backend\n"
        "print('vibecomfy.executor.layout_hints' in sys.modules)\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "False"
