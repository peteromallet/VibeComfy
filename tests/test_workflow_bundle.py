from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from vibecomfy.security import CapabilityFenceError
from vibecomfy.testing.canonical import canonical_json
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import (
    WorkflowBundleError,
    capture_bundle,
    emit_bundle,
    emit_bundle_with_candidate,
    filter_provenance,
    load_bundle,
    validate_sidecar,
)
from vibecomfy.workflow import VibeEdge, VibeNode


def _workflow(workflow_id: str = "bundle-test") -> VibeWorkflow:
    return VibeWorkflow(workflow_id, WorkflowSource(workflow_id))


def test_revision_uses_exact_root_preimage_and_missing_sidecar_is_empty(tmp_path: Path) -> None:
    workflow = _workflow()
    bundle = emit_bundle(workflow, tmp_path / "workflow.py", {"operation": "authored", "timestamp": "drop"})

    expected = hashlib.sha256(
        canonical_json([
            workflow.id,
            bundle.semantic_digest,
            "",
            {"operation": "authored"},
            "",
        ]).encode("utf-8")
    ).hexdigest()
    assert bundle.ui_digest == ""
    assert bundle.revision_id == expected


def test_provenance_is_closed_and_excludes_operational_fields() -> None:
    filtered = filter_provenance(
        {
            "origin": {"kind": "canvas", "uri": "urn:canvas:1"},
            "origin_pin": "commit:abc",
            "source_digest": "a" * 64,
            "operation": "captured",
            "author": "pom",
            "tool_versions": {"converter": "1.2"},
            "timestamp": "drop",
            "session_id": "drop",
            "path": "/tmp/drop",
        },
        default_operation="captured",
    )
    assert filtered == {
        "origin_kind": "canvas",
        "origin_uri": "urn:canvas:1",
        "origin_pin": "commit:abc",
        "source_digest": "a" * 64,
        "operation": "captured",
        "author_id": "pom",
        "tool_versions": {"converter": "1.2"},
    }


def test_source_identity_is_checked_before_digest() -> None:
    workflow = _workflow()
    workflow.metadata["bind"] = {"workflow_identity": "other"}
    with pytest.raises(WorkflowBundleError, match="workflow identity mismatch"):
        # No semantic digest can be obtained from the invalid source.
        emit_bundle(workflow, "/tmp/never-written.py", {"operation": "authored"})


def test_legacy_json_bundle_requires_explicit_identity(tmp_path: Path) -> None:
    source = tmp_path / "legacy.json"
    source.write_text('{"1":{"class_type":"Integer","inputs":{"value":7}}}', encoding="utf-8")

    with pytest.raises(WorkflowBundleError, match="no explicit durable identity"):
        load_bundle(source)


def test_capture_bundle_requires_explicit_identity(tmp_path: Path) -> None:
    from vibecomfy.workflow_bundle import capture_bundle

    with pytest.raises(WorkflowBundleError, match="no explicit durable identity"):
        capture_bundle({"1": {"class_type": "Integer", "inputs": {"value": 7}}}, tmp_path / "capture.py", {})


def test_ready_reference_identity_is_checked_before_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace
    import vibecomfy.cli_loader as cli_loader
    import vibecomfy.registry.ready as ready

    workflow = _workflow("actual")
    monkeypatch.setattr(cli_loader, "load_workflow_any", lambda _: workflow)
    monkeypatch.setattr(ready, "resolve_ready_template", lambda *_: SimpleNamespace(template_id="declared"))

    with pytest.raises(WorkflowBundleError, match="workflow identity mismatch"):
        load_bundle("template-alias")


def test_parent_revision_requires_existing_matching_evidence(tmp_path: Path) -> None:
    workflow = _workflow()
    root = emit_bundle(workflow, tmp_path / "root.py", {"operation": "authored"})
    workflow.metadata["revision_evidence"] = [
        {"revision_id": root.revision_id, "workflow_identity": workflow.id}
    ]
    child = emit_bundle(workflow, tmp_path / "child.py", {"operation": "authored"}, root.revision_id)
    assert child.parent_revision == root.revision_id

    unrelated = _workflow()
    with pytest.raises(WorkflowBundleError, match="unknown parent revision"):
        emit_bundle(unrelated, tmp_path / "unknown.py", {"operation": "authored"}, root.revision_id)

    workflow.metadata["revision_evidence"] = [
        {"revision_id": root.revision_id, "workflow_identity": "different"}
    ]
    with pytest.raises(WorkflowBundleError, match="parent revision workflow identity"):
        emit_bundle(workflow, tmp_path / "mismatch.py", {"operation": "authored"}, root.revision_id)


def test_load_bundle_uses_restricted_build_loader_and_derives_identity(tmp_path: Path) -> None:
    source = tmp_path / "canonical.py"
    source.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n"
        "def build():\n"
        "    return VibeWorkflow('canonical', WorkflowSource('canonical'))\n",
        encoding="utf-8",
    )
    with pytest.raises(CapabilityFenceError, match="non_interactive_refusal"):
        load_bundle(source)
    bundle = load_bundle(source, trust=Provenance.USER_CONFIRMED)
    assert bundle.workflow_identity == bundle.workflow.id == "canonical"
    assert bundle.python_path == source
    assert bundle.ui_digest == ""
    assert not hasattr(bundle, "compile")
    with pytest.raises(AttributeError):
        bundle.workflow_identity = "other"  # type: ignore[misc]


def test_load_bundle_hashes_same_basename_presentation_candidate(tmp_path: Path) -> None:
    source = tmp_path / "canonical.py"
    source.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    return VibeWorkflow('canonical', WorkflowSource('canonical'))\n",
        encoding="utf-8",
    )
    sidecar = tmp_path / "canonical.vibe.json"
    sidecar.write_text(
        '{"format_version":1,"bind":{"workflow_identity":"canonical"},'
        '"nodes":{},"links":[],"groups":[],"canvas":{"zoom":1.0}}',
        encoding="utf-8",
    )

    bundle = load_bundle(source, trust=Provenance.USER_CONFIRMED)

    assert bundle.ui_sidecar == {
        "format_version": 1,
        "bind": {"workflow_identity": "canonical"},
        "nodes": {},
        "links": [],
        "groups": [],
        "canvas": {"zoom": 1.0},
    }
    assert bundle.ui_digest == hashlib.sha256(canonical_json(bundle.ui_sidecar).encode()).hexdigest()


def test_load_workflow_any_remains_bare_compatibility_result(tmp_path: Path) -> None:
    from vibecomfy.cli_loader import load_workflow_any

    source = tmp_path / "bare.py"
    source.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n"
        "def build():\n"
        "    return VibeWorkflow('bare', WorkflowSource('bare'))\n",
        encoding="utf-8",
    )
    result = load_workflow_any(source)
    assert isinstance(result, VibeWorkflow)
    assert not hasattr(result, "revision_id")


def _strict_sidecar(workflow: VibeWorkflow) -> dict:
    return {
        "format_version": 1,
        "bind": {"workflow_identity": workflow.id, "semantic_digest": workflow.semantic_digest()},
        "nodes": {"source": {"id": 1, "pos": [0, 0]}, "target": {"id": 2, "pos": [10, 10]}},
        "links": [{"edge_ref": {"scope_path": "", "from_uid": "source", "from_port": 0, "to_uid": "target", "to_port": 0}, "occurrence_index": 0, "id": 9}],
        "groups": [],
        "canvas": {"zoom": 1, "pan": [0, 0]},
    }


def _connected_workflow() -> VibeWorkflow:
    workflow = _workflow("strict")
    workflow.nodes["a"] = VibeNode("a", "Source", uid="source")
    workflow.nodes["b"] = VibeNode("b", "Target", uid="target")
    workflow.edges.append(VibeEdge("a", "0", "b", "0"))
    return workflow


def test_strict_sidecar_rejects_unknown_nested_fields_and_qualified_refs() -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    sidecar["nodes"]["source"]["properties"] = {}
    with pytest.raises(WorkflowBundleError, match="unknown field"):
        validate_sidecar(sidecar, workflow)
    sidecar = _strict_sidecar(workflow)
    sidecar["links"][0]["edge_ref"]["from_uid"] = "scope#source"
    with pytest.raises(WorkflowBundleError, match="qualified UID"):
        validate_sidecar(sidecar, workflow)


def test_strict_sidecar_rejects_occurrence_gaps_duplicate_native_ids_and_stale_digest() -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    duplicate = dict(sidecar["links"][0]); duplicate["occurrence_index"] = 2; duplicate["id"] = 10
    sidecar["links"].append(duplicate)
    with pytest.raises(WorkflowBundleError, match="contiguous"):
        validate_sidecar(sidecar, workflow)
    sidecar = _strict_sidecar(workflow)
    sidecar["bind"]["semantic_digest"] = "stale"
    with pytest.raises(WorkflowBundleError, match="semantic digest"):
        validate_sidecar(sidecar, workflow)


def test_presentation_digest_isolated_from_semantic_digest_and_legacy_sidecar_rejected(tmp_path: Path) -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    first = emit_bundle_with_candidate(workflow, tmp_path / "strict.py", {"operation": "authored"}, sidecar)
    sidecar["nodes"]["source"]["pos"] = [99, 100]
    second = emit_bundle_with_candidate(workflow, tmp_path / "strict.py", {"operation": "authored"}, sidecar)
    assert first.semantic_digest == second.semantic_digest
    assert first.ui_digest != second.ui_digest
    (tmp_path / "strict.layout.json").write_text("{}", encoding="utf-8")
    with pytest.raises(WorkflowBundleError, match="not an approved source"):
        emit_bundle(workflow, tmp_path / "strict.py", {"operation": "authored"})


def test_atomic_pair_rolls_back_after_second_replacement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    emit_bundle_with_candidate(workflow, tmp_path / "atomic.py", {"operation": "authored"}, sidecar)
    before = {(tmp_path / name).read_bytes() for name in ("atomic.py", "atomic.vibe.json")}
    original_replace = __import__("vibecomfy.workflow_bundle", fromlist=["os"]).os.replace
    calls = 0

    def fail_once(source: str, destination: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected replacement failure")
        original_replace(source, destination)

    monkeypatch.setattr("vibecomfy.workflow_bundle.os.replace", fail_once)
    with pytest.raises(OSError, match="injected replacement failure"):
        emit_bundle_with_candidate(workflow, tmp_path / "atomic.py", {"operation": "authored"}, sidecar)
    assert before == {(tmp_path / name).read_bytes() for name in ("atomic.py", "atomic.vibe.json")}
    assert not list(tmp_path.glob(".*.tmp"))


def test_sidecar_groups_are_sorted_and_duplicate_identity_rejected() -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    sidecar["groups"] = [
        {"scope_path": "", "presentation_id": "b", "bounds": [1, 2, 3, 4]},
        {"scope_path": "", "presentation_id": "a", "bounds": [1, 2, 3, 4]},
    ]
    normalized = validate_sidecar(sidecar, workflow)
    assert [item["presentation_id"] for item in normalized["groups"]] == ["a", "b"]
    sidecar["groups"].append(dict(sidecar["groups"][0]))
    with pytest.raises(WorkflowBundleError, match="duplicate scoped group"):
        validate_sidecar(sidecar, workflow)


def test_sidecar_rejects_nonfinite_canvas_and_recursive_virtual_native_form() -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    sidecar["canvas"]["zoom"] = float("inf")
    with pytest.raises(WorkflowBundleError, match="finite"):
        validate_sidecar(sidecar, workflow)
    workflow.virtual_wires = {"wire": {"endpoints": [["a", -10, "b", 0]]}}
    sidecar = _strict_sidecar(workflow)
    sidecar["links"] = [{"virtual_wire_ref": {"scope_path": "", "name": "wire", "leg_index": 0}, "occurrence_index": 0}]
    with pytest.raises(WorkflowBundleError, match="materialized leg"):
        validate_sidecar(sidecar, workflow)
    workflow.virtual_wires = {"ghost": {"legs": [{"from_uid": "source", "from_port": 0, "to_uid": "ghost", "to_port": 0}]}}
    sidecar["bind"]["semantic_digest"] = workflow.semantic_digest()
    sidecar["links"] = [{"virtual_wire_ref": {"scope_path": "", "name": "ghost", "leg_index": 0}, "occurrence_index": 0}]
    with pytest.raises(WorkflowBundleError, match="not local"):
        validate_sidecar(sidecar, workflow)


def test_sidecar_semantic_gate_rejects_malformed_python_edge_without_bind_digest() -> None:
    workflow = _connected_workflow()
    workflow.edges.append(VibeEdge("missing", "0", "b", "0"))
    sidecar = {"format_version": 1, "bind": {"workflow_identity": workflow.id}, "nodes": {"source": {}, "target": {}}, "links": [], "groups": [], "canvas": {}}
    with pytest.raises(WorkflowBundleError, match="endpoint"):
        validate_sidecar(sidecar, workflow)


def test_capture_preserves_ui_fidelity_and_rejects_known_raw_properties(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _connected_workflow()
    for node in workflow.nodes.values():
        node.metadata["schema_source"] = {"provider": "authoritative_object_info"}
    graph = {
        "workflow_id": workflow.id,
        "nodes": [
            {"id": 1, "type": "Source", "pos": [1, 2], "size": [3, 4], "flags": {"collapsed": True}, "properties": {"vibecomfy_uid": "source"}},
            {"id": 2, "type": "Target", "pos": [5, 6], "size": [7, 8], "properties": {"vibecomfy_uid": "target"}},
        ],
        "links": [[9, 1, 0, 2, 0, "A"]],
        "groups": [{"id": 7, "nodes": [1], "bounding": [0, 0, 20, 20], "title": "G"}],
        "extra": {"ds": {"scale": 1.5, "offset": [11, 12]}},
    }
    monkeypatch.setattr("vibecomfy.ingest.normalize._named_import", lambda *args, **kwargs: workflow)
    bundle = capture_bundle(graph, tmp_path / "capture.py", {"operation": "captured"})
    assert bundle.ui_sidecar["nodes"]["source"]["collapsed"] is True
    assert bundle.ui_sidecar["nodes"]["source"]["group"] == "7"
    assert bundle.ui_sidecar["groups"][0]["presentation_id"] == "7"
    assert bundle.ui_sidecar["canvas"] == {"zoom": 1.5, "pan": [11.0, 12.0]}
    assert "reroute" not in bundle.ui_sidecar["links"][0]
    graph["nodes"][0]["properties"]["editor_flag"] = True
    with pytest.raises(WorkflowBundleError, match="unclassified"):
        capture_bundle(graph, tmp_path / "bad.py", {"operation": "captured"})


def test_capture_unknown_node_keeps_local_fallback_properties_out_of_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _workflow("unknown-capture")
    workflow.nodes["u"] = VibeNode("u", "FutureCustomNode", uid="u")
    graph = {
        "workflow_id": workflow.id,
        "nodes": [{"id": 1, "type": "SomeFutureNode", "properties": {"vibecomfy_uid": "u", "opaque": 3}}],
        "links": [], "groups": [],
    }
    monkeypatch.setattr("vibecomfy.ingest.normalize._named_import", lambda *args, **kwargs: workflow)
    bundle = capture_bundle(graph, tmp_path / "unknown.py", {"operation": "captured"})
    assert bundle.ui_sidecar["nodes"]["u"] == {"id": 1}


def test_staged_sidecar_corruption_and_first_replace_failure_preserve_old_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vibecomfy.workflow_bundle as module

    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    path = tmp_path / "fault.py"
    emit_bundle_with_candidate(workflow, path, {"operation": "authored"}, sidecar)
    before = {name: (tmp_path / name).read_bytes() for name in ("fault.py", "fault.vibe.json")}
    original_read_text = Path.read_text

    def corrupt_staged_sidecar(self: Path, *args, **kwargs):
        if self.name.startswith(".fault.vibe.json."):
            return "{"
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", corrupt_staged_sidecar)
    with pytest.raises(WorkflowBundleError, match="staged workflow sidecar"):
        emit_bundle_with_candidate(workflow, path, {"operation": "authored"}, sidecar)
    assert before == {name: (tmp_path / name).read_bytes() for name in before}
    assert not list(tmp_path.glob(".fault.*.bak"))
    monkeypatch.setattr(Path, "read_text", original_read_text)
    original_replace = module.os.replace
    calls = 0

    def fail_first(source, destination):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("injected first replacement failure")
        return original_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_first)
    with pytest.raises(OSError, match="first replacement"):
        emit_bundle_with_candidate(workflow, path, {"operation": "authored"}, sidecar)
    assert before == {name: (tmp_path / name).read_bytes() for name in before}
    assert not list(tmp_path.glob(".fault.*.tmp"))


def test_rollback_failure_is_explicitly_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vibecomfy.workflow_bundle as module

    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    path = tmp_path / "rollback.py"
    emit_bundle_with_candidate(workflow, path, {"operation": "authored"}, sidecar)
    original_replace = module.os.replace
    calls = 0

    def fail_publication_and_rollback(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2 or calls == 3:
            raise OSError("injected rollback failure")
        return original_replace(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_publication_and_rollback)
    with pytest.raises(WorkflowBundleError, match="rollback/cleanup failed"):
        emit_bundle_with_candidate(workflow, path, {"operation": "authored"}, sidecar)


def test_api_capture_separates_identity_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = _workflow("api-capture")
    api = {"workflow_id": workflow.id, "1": {"class_type": "Integer", "inputs": {"value": 1}}}
    monkeypatch.setattr("vibecomfy.ingest.normalize._named_import", lambda *args, **kwargs: workflow)
    bundle = capture_bundle(api, tmp_path / "api.py", {"operation": "captured"})
    assert bundle.workflow_identity == workflow.id
    assert bundle.ui_sidecar is None


def test_recursive_edges_and_virtual_wires_use_structural_scope_and_local_uids() -> None:
    from vibecomfy.identity.scope import compose_scope_path, sg_key
    from vibecomfy.identity.uid import make_uid

    workflow = _workflow("recursive")
    definition = {
        "name": "inner",
        "nodes": [
            {"id": 10, "uid": "left", "class_type": "A"},
            {"id": 20, "uid": "right", "class_type": "B"},
        ],
        "links": [{"origin_id": 10, "origin_slot": 0, "target_id": 20, "target_slot": 1}],
        "virtual_wires": {"vw": {"legs": [{"origin_id": 10, "origin_slot": 0, "target_id": 20, "target_slot": 1}]}},
    }
    workflow.definitions = {"one": definition}
    scope = compose_scope_path((sg_key(definition),))
    sidecar = {
        "format_version": 1,
        "bind": {"workflow_identity": workflow.id, "semantic_digest": workflow.semantic_digest()},
        "nodes": {make_uid(scope, "left"): {}, make_uid(scope, "right"): {}},
        "links": [
            {"edge_ref": {"scope_path": scope, "from_uid": "left", "from_port": 0, "to_uid": "right", "to_port": 1}, "occurrence_index": 0},
            {"virtual_wire_ref": {"scope_path": scope, "name": "vw", "leg_index": 0}, "occurrence_index": 0},
        ],
        "groups": [], "canvas": {},
    }
    normalized = validate_sidecar(sidecar, workflow)
    assert len(normalized["links"]) == 2
