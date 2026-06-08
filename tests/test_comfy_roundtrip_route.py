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


# ---------------------------------------------------------------------------
# (f) exec node round-trip coverage (T10)
# ---------------------------------------------------------------------------


def test_exec_roundtrip_preserves_source_and_io() -> None:
    """Round-trip through the engine preserves source and io widget values."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import emit_ui_json
    from vibecomfy.schema import get_schema_provider

    source = "return {'image': image}"
    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}

    # Build API dict directly (skip normalize_to_api to avoid raw _ui pinning)
    api = {
        "1": {
            "class_type": "vibecomfy.exec",
            "inputs": {"source": source, "io": io_spec},
        }
    }

    wf = convert_to_vibe_format(api)
    schema_provider = get_schema_provider("local")
    emitted = emit_ui_json(wf, schema_provider=schema_provider)

    exec_nodes = [n for n in emitted["nodes"] if n["type"] == "vibecomfy.exec"]
    assert len(exec_nodes) == 1
    exec_node = exec_nodes[0]

    wv = exec_node.get("widgets_values", {})
    # widgets_values may be a dict (keyed) or list (positional from schema-less emit)
    if isinstance(wv, dict):
        assert wv.get("source") == source
        assert wv.get("io") == io_spec
    else:
        # Positional: [source, io]
        assert isinstance(wv, list) and len(wv) >= 2
        assert wv[0] == source
        assert wv[1] == io_spec


def test_exec_roundtrip_preserves_linked_in_references() -> None:
    """Exec round-trip preserves linked in_N references from upstream nodes."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import emit_ui_json
    from vibecomfy.schema import get_schema_provider

    source = "return {'image': image}"
    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}

    api = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "example.png"}},
        "2": {
            "class_type": "vibecomfy.exec",
            "inputs": {"source": source, "io": io_spec, "in_0": ["1", 0], "in_1": ["1", 0]},
        },
    }

    wf = convert_to_vibe_format(api)
    schema_provider = get_schema_provider("local")
    emitted = emit_ui_json(wf, schema_provider=schema_provider)

    links = emitted.get("links", [])
    node_by_type = {n["type"]: n for n in emitted["nodes"]}
    exec_node = node_by_type.get("vibecomfy.exec")
    assert exec_node is not None

    exec_id = exec_node["id"]
    upstream_links = [l for l in links if l[3] == exec_id]
    assert len(upstream_links) >= 1

    target_slots = {l[4] for l in upstream_links}
    assert 0 in target_slots


def test_exec_roundtrip_preserves_downstream_out_references() -> None:
    """Exec round-trip preserves downstream out_N links to consumer nodes."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import emit_ui_json
    from vibecomfy.schema import get_schema_provider

    source = "return {'image': image}"
    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}

    api = {
        "1": {
            "class_type": "vibecomfy.exec",
            "inputs": {"source": source, "io": io_spec},
        },
        "2": {
            "class_type": "SaveImage",
            "inputs": {"images": ["1", 0], "filename_prefix": "out/"},
        },
    }

    wf = convert_to_vibe_format(api)
    schema_provider = get_schema_provider("local")
    emitted = emit_ui_json(wf, schema_provider=schema_provider)

    links = emitted.get("links", [])
    node_by_type = {n["type"]: n for n in emitted["nodes"]}
    exec_node = node_by_type.get("vibecomfy.exec")
    assert exec_node is not None

    exec_id = exec_node["id"]
    downstream_links = [l for l in links if l[1] == exec_id]
    assert len(downstream_links) >= 1

    origin_slots = {l[2] for l in downstream_links}
    assert 0 in origin_slots


def test_exec_roundtrip_preserves_dynamic_socket_counts() -> None:
    """Exec node in the emitted UI graph preserves linked socket slots from the workflow.

    When the schema provider has the builtin schema, the emit produces exactly 16
    input and 16 output slots.  Without a schema, it emits best-effort slots
    (what the IR actually tracks).  This test verifies that linked in_N / out_N
    slots survive the engine round-trip regardless.
    """
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import emit_ui_json
    from vibecomfy.schema import get_schema_provider

    source = "return {'image': image}"
    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}

    api = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "example.png"}},
        "2": {
            "class_type": "vibecomfy.exec",
            "inputs": {"source": source, "io": io_spec, "in_0": ["1", 0]},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "out/"},
        },
    }

    wf = convert_to_vibe_format(api)
    schema_provider = get_schema_provider("local")
    emitted = emit_ui_json(wf, schema_provider=schema_provider)

    exec_nodes = [n for n in emitted["nodes"] if n["type"] == "vibecomfy.exec"]
    assert len(exec_nodes) == 1
    exec_node = exec_nodes[0]

    inputs = exec_node.get("inputs", [])
    outputs = exec_node.get("outputs", [])

    # At minimum, linked slots from upstream/downstream must be present.
    # Without a schema, the emit may use generic output_N names.
    input_names = {s.get("name") for s in inputs}
    output_names = {s.get("name") for s in outputs}
    assert "in_0" in input_names, f"missing linked in_0 in {input_names}"
    # Schema-less fallback may name slots output_N instead of out_N
    assert ("out_0" in output_names or "output_0" in output_names), (
        f"missing linked out_0/output_0 in {output_names}"
    )


def test_exec_api_reload_without_ui_metadata_restores_derived_io() -> None:
    """API-shape reload without _ui metadata restores properties.vibecomfy.io from the io widget."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format

    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}
    source = "return {'image': image}"

    # API shape: no _ui metadata
    api = {
        "1": {
            "class_type": "vibecomfy.exec",
            "inputs": {
                "source": source,
                "io": io_spec,
                "in_0": ["2", 0],
            },
        }
    }

    workflow = convert_to_vibe_format(api)

    node = workflow.nodes["1"]
    # Widget values are authoritative
    assert node.widgets["source"] == source
    assert node.widgets["io"] == io_spec
    # Derived metadata is rebuilt from widget
    assert node.metadata["_ui"]["properties"]["vibecomfy"]["io"] == io_spec


def test_exec_compile_preserves_linked_in_references() -> None:
    """Compile/reload preserves linked in_N references in the workflow edge model."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format

    source = "return {'image': image}"
    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}

    api = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "example.png"}},
        "2": {
            "class_type": "vibecomfy.exec",
            "inputs": {"source": source, "io": io_spec, "in_0": ["1", 0]},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "out/"},
        },
    }

    workflow = convert_to_vibe_format(api)

    # Verify linked in_0 from LoadImage
    in_edges = [e for e in workflow.edges if e.to_node == "2" and e.to_input == "in_0"]
    assert len(in_edges) == 1
    assert in_edges[0].from_node == "1"

    # Verify out_0 to SaveImage
    out_edges = [e for e in workflow.edges if e.from_node == "2" and e.from_output == "0"]
    assert len(out_edges) == 1
    assert out_edges[0].to_node == "3"


def test_exec_roundtrip_preserves_links_across_nodes() -> None:
    """Full round-trip preserves all link topology including exec in/out slots."""
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.ui_emitter import emit_ui_json
    from vibecomfy.schema import get_schema_provider

    source = "return {'image': image}"
    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}

    api = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "example.png"}},
        "2": {
            "class_type": "vibecomfy.exec",
            "inputs": {"source": source, "io": io_spec, "in_0": ["1", 0]},
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"images": ["2", 0], "filename_prefix": "out/"},
        },
    }

    wf = convert_to_vibe_format(api)
    schema_provider = get_schema_provider("local")
    emitted = emit_ui_json(wf, schema_provider=schema_provider)

    nodes = emitted["nodes"]
    links = emitted["links"]

    # Three nodes: LoadImage, vibecomfy.exec, SaveImage
    assert len(nodes) == 3

    # Two links: LoadImage→exec, exec→SaveImage
    assert len(links) == 2

    load = next(n for n in nodes if n["type"] == "LoadImage")
    exec_n = next(n for n in nodes if n["type"] == "vibecomfy.exec")
    save = next(n for n in nodes if n["type"] == "SaveImage")

    # First link: LoadImage out_0 → exec in_0
    link1 = next(l for l in links if l[1] == load["id"])
    assert link1[3] == exec_n["id"]

    # Second link: exec out_0 → SaveImage
    link2 = next(l for l in links if l[1] == exec_n["id"])
    assert link2[3] == save["id"]
