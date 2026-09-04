from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vibecomfy.security import CapabilityFenceError
from vibecomfy.testing.canonical import canonical_json
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
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
    import vibecomfy.registry.ready as ready

    workflow = _workflow("actual")
    monkeypatch.setattr(ready, "resolve_ready_template", lambda *_: SimpleNamespace(template_id="declared"))
    monkeypatch.setattr(ready, "workflow_from_ready", lambda *_args, **_kwargs: workflow)
    monkeypatch.setattr(ready, "ready_template_discovery", lambda: SimpleNamespace())

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
    record = bundle.compile()
    assert isinstance(record, ApprovedProjectionRecord)
    assert set(record.to_dict()) == {
        "revision_id",
        "selected_variant",
        "input_binding",
        "api_projection",
        "ui_projection",
        "api_digest",
    }
    record.assert_matches(bundle, None, None, record.api_projection, record.ui_projection)
    with pytest.raises(WorkflowBundleError, match="input binding"):
        record.assert_matches(bundle, None, {"unexpected": True}, record.api_projection, record.ui_projection)
    assert bundle.compile().to_canonical_bytes() == record.to_canonical_bytes()
    bundle.workflow.add_node("Integer", uid="changed-after-approval", value=1)
    with pytest.raises(WorkflowBundleError, match="stale"):
        bundle.compile()
    with pytest.raises(WorkflowBundleError, match="revision"):
        record.assert_matches(bundle, None, None, record.api_projection, record.ui_projection)
    with pytest.raises(AttributeError):
        bundle.workflow_identity = "other"  # type: ignore[misc]


def test_approved_projection_record_is_detached_immutable_and_canonical() -> None:
    api = {"1": {"class_type": "Integer", "inputs": {"value": 7}}}
    ui = {"nodes": [{"id": 1}], "links": []}
    inputs = {"seed": {"value": 3}}
    record = ApprovedProjectionRecord(
        "revision",
        None,
        inputs,
        api,
        ui,
        hashlib.sha256(canonical_json(api).encode()).hexdigest(),
    )
    inputs["seed"]["value"] = 99
    api["1"]["inputs"]["value"] = 8
    assert record.input_binding["seed"]["value"] == 3
    assert record.api_projection["1"]["inputs"]["value"] == 7
    with pytest.raises(TypeError):
        record.api_projection["1"] = {}  # type: ignore[index]
    encoded = record.to_canonical_bytes()
    assert ApprovedProjectionRecord.from_canonical_bytes(encoded) == record
    with pytest.raises(WorkflowBundleError, match="not canonical"):
        ApprovedProjectionRecord.from_canonical_bytes(json.dumps(record.to_dict()).encode())


def test_bundle_compile_rejects_unknown_variant() -> None:
    bundle = load_bundle(_workflow())

    with pytest.raises(WorkflowBundleError, match="projection failed"):
        bundle.compile("missing")


def test_bundle_compile_rejects_unresolved_class_and_identity() -> None:
    unknown = _workflow("unknown-class")
    unknown.add_node("NotARealNode", uid="unknown-node", value=1)
    with pytest.raises(WorkflowBundleError, match="unresolved class types"):
        load_bundle(unknown).compile()

    identity = _workflow("identity-mismatch")
    node = identity.add_node("Integer", uid="identity-node", value=1)
    node.metadata["object_info_identity"] = {
        "pack_slug": "missing-pack",
        "git_commit": "missing-commit",
    }
    with pytest.raises(WorkflowBundleError, match="object-info identity"):
        load_bundle(identity).compile()


def test_bundle_compile_rejects_nested_reconciliation_and_model_presence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reconciliation = _workflow("reconciliation")
    reconciliation.metadata["reconciliation"] = {
        "diagnostics": [{"severity": "error", "message": "stale"}]
    }
    with pytest.raises(WorkflowBundleError, match="reconciliation"):
        load_bundle(reconciliation).compile()

    import vibecomfy.fetch as fetch
    import vibecomfy.model_assets as model_assets
    import vibecomfy.registry.models_loader as models_loader

    monkeypatch.setattr(
        model_assets,
        "_referenced_model_values",
        lambda _workflow: [{"value": "model.bin", "subdir": "checkpoints"}],
    )
    monkeypatch.setattr(models_loader, "load_registry", lambda: ())
    monkeypatch.setattr(models_loader, "resolve_model_entry", lambda *args, **kwargs: object())
    monkeypatch.setattr(fetch, "is_present", lambda *args, **kwargs: False)
    with pytest.raises(WorkflowBundleError, match="not present locally"):
        load_bundle(_workflow("missing-model")).compile()


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
    workflow.nodes["a"] = VibeNode(
        "a", "Source", uid="source", native_output_names=["out"]
    )
    workflow.nodes["b"] = VibeNode(
        "b", "Target", uid="target", native_input_names=["in"]
    )
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


@pytest.mark.parametrize(
    "virtual_wires, message",
    [
        ([], "must be a mapping"),
        ({"": {}}, "nonblank"),
        ({"wire": []}, "must be a mapping"),
        ({"wire": {"legs": {}}}, "legs must be a list"),
        ({"wire": {"legs": ["bad"]}}, "malformed Python leg"),
    ],
)
def test_malformed_python_virtual_wire_containers_fail_closed(virtual_wires, message) -> None:
    workflow = _connected_workflow()
    workflow.virtual_wires = virtual_wires
    sidecar = _strict_sidecar(workflow)
    sidecar["bind"]["semantic_digest"] = workflow.semantic_digest()
    with pytest.raises(WorkflowBundleError, match=message):
        validate_sidecar(sidecar, workflow)


def test_capture_rejects_malformed_properties_and_link_lengths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workflow = _connected_workflow()
    monkeypatch.setattr("vibecomfy.ingest.normalize._named_import", lambda *args, **kwargs: workflow)
    base = {
        "workflow_id": workflow.id,
        "nodes": [
            {"id": 1, "properties": {"vibecomfy_uid": "source"}},
            {"id": 2, "properties": {"vibecomfy_uid": "target"}},
        ],
        "links": [], "groups": [],
    }
    bad_properties = dict(base)
    bad_properties["nodes"] = [dict(base["nodes"][0], properties=None), base["nodes"][1]]
    with pytest.raises(WorkflowBundleError, match="properties must be a mapping"):
        capture_bundle(bad_properties, tmp_path / "bad-properties.py", {"operation": "captured"})
    bad_link = dict(base)
    bad_link["links"] = [[9, 1, 0, 2, 0, "A", "extra"]]
    with pytest.raises(WorkflowBundleError, match="malformed"):
        capture_bundle(bad_link, tmp_path / "bad-link.py", {"operation": "captured"})


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


def test_real_converter_backed_public_capture_roundtrips_pair(tmp_path: Path) -> None:
    import json

    fixture = Path("tests/characterization/fixtures/agent_edit/case_01_widget_set/input_ui.json")
    graph = json.loads(fixture.read_text(encoding="utf-8"))
    graph["workflow_id"] = "07824bbb-6672-4bb0-ac36-4313a519e35b"
    destination = tmp_path / "captured.py"
    bundle = capture_bundle(graph, destination, {"operation": "captured"})
    reloaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED)
    assert reloaded.semantic_digest == bundle.semantic_digest
    assert reloaded.ui_digest == bundle.ui_digest
    assert destination.is_file()
    assert destination.with_suffix(".vibe.json").is_file()


def test_native_port_rosters_are_semantic_not_execution_data() -> None:
    from vibecomfy.porting.emit.entrypoints import emit_scratchpad_python

    workflow = _connected_workflow()
    api_before = workflow.compile("api")
    digest_before = workflow.semantic_digest()
    workflow.nodes["a"].native_output_names = ["changed"]
    assert workflow.semantic_digest() != digest_before
    assert workflow.compile("api") == api_before

    source = emit_scratchpad_python(workflow)
    assert "_input_ports=" in source
    assert "_output_ports=" in source
    assert "_ui=" not in source
    namespace: dict[str, object] = {"__file__": "generated.py"}
    exec(source, namespace)
    loaded = namespace["build"]()
    assert loaded.nodes["a"].native_output_names == ["changed"]
    assert loaded.nodes["b"].native_input_names == ["in"]
    restored = VibeWorkflow.from_envelope(workflow.to_envelope())
    assert restored.nodes["a"].native_output_names == ["changed"]
    assert restored.semantic_digest() == workflow.semantic_digest()


def test_native_port_rosters_validate_holes_duplicates_and_missing_sidecar_evidence() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        VibeNode("x", "Source", native_output_names=["out", "out"])
    with pytest.raises(ValueError, match="nonblank"):
        VibeNode("x", "Source", native_output_names=[""])
    node = VibeNode("x", "Source", native_output_names=["out", None, "tail"])
    assert node.native_output_names == ["out", None, "tail"]

    workflow = _workflow("missing-roster")
    workflow.nodes["a"] = VibeNode("a", "Source", uid="source")
    workflow.nodes["b"] = VibeNode("b", "Target", uid="target")
    workflow.edges.append(VibeEdge("a", "0", "b", "0"))
    sidecar = _strict_sidecar(workflow)
    with pytest.raises(WorkflowBundleError, match="native output roster"):
        validate_sidecar(sidecar, workflow)


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
