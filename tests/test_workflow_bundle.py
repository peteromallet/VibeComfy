from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vibecomfy.security import CapabilityFenceError
from vibecomfy.testing.canonical import canonical_json
from vibecomfy.security.provenance import Provenance
from vibecomfy.scratchpad_loader import load_scratchpad
from vibecomfy.workflow import (
    VibeInput,
    VibeWorkflow,
    WorkflowCompileError,
    WorkflowSource,
    canonical_ir_projection,
)
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundleError,
    capture_bundle,
    emit_bundle,
    emit_bundle_with_candidate,
    filter_provenance,
    load_bundle,
    materialize_ui_json,
    validate_sidecar,
)
from vibecomfy.workflow import VibeEdge, VibeNode


def _workflow(workflow_id: str = "bundle-test") -> VibeWorkflow:
    return VibeWorkflow(workflow_id, WorkflowSource(workflow_id))


def _nonempty_workflow(workflow_id: str = "bundle-test") -> VibeWorkflow:
    workflow = _workflow(workflow_id)
    workflow.add_node("Integer", uid="integer-node", value=7)
    return workflow


def test_revision_uses_exact_root_preimage_and_emitted_companion(tmp_path: Path) -> None:
    workflow = _nonempty_workflow()
    bundle = emit_bundle(workflow, tmp_path / "workflow.py", {"operation": "authored", "timestamp": "drop"})

    expected = hashlib.sha256(
        canonical_json([
            workflow.id,
            bundle.semantic_digest,
            bundle.ui_digest,
            {"operation": "authored"},
            "",
        ]).encode("utf-8")
    ).hexdigest()
    assert bundle.ui_sidecar is not None
    assert bundle.ui_sidecar["format_version"] == 2
    assert bundle.ui_digest == hashlib.sha256(
        canonical_json(bundle.ui_sidecar["presentation"]).encode()
    ).hexdigest()
    assert bundle.revision_id == expected


def test_reemitting_a_loaded_pair_is_byte_deterministic(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    emit_bundle(_nonempty_workflow("deterministic-pair"), first_dir / "workflow.py", {"operation": "authored"})
    loaded = load_bundle(first_dir / "workflow.py", trust=Provenance.USER_CONFIRMED)
    emit_bundle(loaded.workflow, second_dir / "workflow.py", {"operation": "authored"})

    assert (first_dir / "workflow.py").read_bytes() == (second_dir / "workflow.py").read_bytes()
    assert (first_dir / "workflow.vibe.json").read_bytes() == (second_dir / "workflow.vibe.json").read_bytes()


def test_source_provenance_report_survives_bundle_reload_and_reemission(tmp_path: Path) -> None:
    report = {
        "records": [
            {"node_id": "1", "class_type": "KSampler", "cnr_id": "comfy-core", "ver": "0.24.0"},
            {"node_id": "2", "class_type": "Aux", "aux_id": "owner/repo", "ver": "deadbeef"},
        ],
        "requirements": [], "warnings": [], "conflicts": [], "version_pins": [],
        "required_pack_slugs": ["comfy-core"], "aux_only": [], "unprovenanced": [],
        "core_slug_non_core": [], "low_confidence": False,
    }
    provenance = {"operation": "imported", "source_provenance": report}
    first = tmp_path / "first"; second = tmp_path / "second"
    first.mkdir(); second.mkdir()
    emit_bundle(_nonempty_workflow("provenance-pair"), first / "workflow.py", provenance)
    loaded = load_bundle(first / "workflow.py", trust=Provenance.USER_CONFIRMED)
    assert loaded.provenance["source_provenance"] == report
    emit_bundle(loaded.workflow, second / "workflow.py", loaded.provenance)
    assert "source_provenance" in (second / "workflow.py").read_text(encoding="utf-8")
    reloaded = load_bundle(second / "workflow.py", trust=Provenance.USER_CONFIRMED)
    assert reloaded.provenance["source_provenance"] == report


@pytest.mark.parametrize("corpus_id", ["352066ccef9dbe37", "8800a945cff8d090"])
def test_cli_convert_corpus_pair_admits_through_real_loader_path(
    corpus_id: str, tmp_path: Path
) -> None:
    """The CLI loader/converter path must pass v2 first-build admission."""
    from tests.live_agentic_harness.source_layouts import resolve_corpus_record_path
    from vibecomfy.porting.convert import (
        _build_emitted_workflow_from_text,
        port_convert_workflow,
    )
    from vibecomfy.porting.workbench import analyze_source, load_port_source

    source = resolve_corpus_record_path(
        f"tests/fixtures/live_agentic_corpus/corpus/{corpus_id}.json"
    )
    assert source is not None and source.is_file()
    loaded = load_port_source(str(source), use_comfy_converter=False)
    report = analyze_source(str(source), loaded_source=loaded, mode="auto")
    result = port_convert_workflow(
        loaded.workflow,
        source_path=loaded.source_path,
        provenance=report.provenance,
        source_hash=report.source_hash,
        workflow_shape=report.workflow_shape,
        registered_inputs={},
        schema_provider=None,
        keep_virtual_wires=False,
        preserve_node_ids=True,
    )
    emitted = _build_emitted_workflow_from_text(result.text)

    bundle = emit_bundle_with_candidate(
        emitted,
        tmp_path / f"{corpus_id}.py",
        report.provenance,
        None,
        operation="authored",
        source_provenance={
            "source_hash": report.source_hash,
            "workflow_shape": report.workflow_shape,
            "source_type": loaded.source_kind,
        },
        source_format="scratchpad",
    )
    assert bundle.semantic_digest


def test_load_workflow_any_promotes_source_widget_aliases_for_digest_admission() -> None:
    """The real CLI loader admits the remaining UI-backed positional case."""
    from vibecomfy.cli_loader import load_workflow_any
    from vibecomfy.porting.convert import port_convert_workflow

    source = Path(__file__).parent / "fixtures/live_agentic_corpus/corpus/1cc45704dcffe34a.json"
    workflow = load_workflow_any(str(source))

    assert workflow.nodes["369"].inputs["width"] == 832
    assert workflow.nodes["408"].inputs["context_length"] == 13
    assert workflow.nodes["380"].inputs["device"] == "cpu"
    assert workflow.nodes["500"].inputs["expression"] == "(a - 1) / 4 + 1"

    result = port_convert_workflow(
        workflow,
        source_path=str(source),
        registered_inputs={},
        preserve_node_ids=True,
    )
    assert result.validation is not None
    assert result.validation.import_ok
    assert result.validation.build_ok
    assert result.validation.compile_ok
    assert result.validation.parity_ok


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
    workflow = _nonempty_workflow()
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
        "    workflow = VibeWorkflow('canonical', WorkflowSource('canonical'))\n"
        "    workflow.add_node('Integer', uid='integer-node', value=7)\n"
        "    return workflow\n",
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
    bundle.workflow.source.provenance["author_id"] = "changed"
    with pytest.raises(WorkflowBundleError, match="revision"):
        bundle.compile()
    with pytest.raises(WorkflowBundleError, match="revision"):
        record.assert_matches(bundle, None, None, record.api_projection, record.ui_projection)
    bundle.workflow.source.provenance.clear()
    assert bundle.compile().to_canonical_bytes() == record.to_canonical_bytes()
    with pytest.raises(WorkflowBundleError, match="input binding"):
        record.assert_matches(bundle, None, {"unexpected": True}, record.api_projection, record.ui_projection)
    bundle.workflow.add_node("Integer", uid="changed-after-approval", value=1)
    with pytest.raises(WorkflowBundleError, match="stale"):
        bundle.compile()
    with pytest.raises(WorkflowBundleError, match="revision"):
        record.assert_matches(bundle, None, None, record.api_projection, record.ui_projection)
    with pytest.raises(AttributeError):
        bundle.workflow_identity = "other"  # type: ignore[misc]


def test_current_rebind_empty_live_provenance_supports_ephemeral_and_emitted(
    tmp_path: Path,
) -> None:
    ephemeral = load_bundle(_nonempty_workflow("empty-live-ephemeral"))
    ephemeral_record = ephemeral.compile()
    ephemeral_record.assert_matches(
        ephemeral, None, None, ephemeral_record.api_projection, ephemeral_record.ui_projection
    )

    emitted = emit_bundle(
        _nonempty_workflow("empty-live-emitted"),
        tmp_path / "emitted.py",
        {"operation": "authored"},
    )
    emitted_record = emitted.compile()
    emitted_record.assert_matches(
        emitted, None, None, emitted_record.api_projection, emitted_record.ui_projection
    )


def test_current_rebind_bound_nested_mutation_rejects_with_empty_live() -> None:
    bundle = load_bundle(_nonempty_workflow("bound-mutation-empty-live"))
    record = bundle.compile()
    bundle.provenance["tool_versions"] = {"compiler": "changed"}
    with pytest.raises(WorkflowBundleError, match="bound provenance"):
        bundle.compile()
    with pytest.raises(WorkflowBundleError, match="bound provenance"):
        record.assert_matches(bundle, None, None, record.api_projection, record.ui_projection)


def test_current_rebind_bound_nested_mutation_rejects_with_nonempty_live() -> None:
    from vibecomfy.workflow_bundle import _make_bundle

    workflow = _nonempty_workflow("bound-mutation-nonempty-live")
    provenance = {"operation": "ephemeral", "tool_versions": {"compiler": "stable"}}
    workflow.source.provenance = copy.deepcopy(provenance)
    bundle = _make_bundle(
        workflow,
        python_path=None,
        ui_sidecar=None,
        provenance=copy.deepcopy(provenance),
        operation="ephemeral",
    )
    record = bundle.compile()
    bundle.provenance["tool_versions"]["compiler"] = "changed"
    with pytest.raises(WorkflowBundleError, match="bound provenance"):
        bundle.compile()
    with pytest.raises(WorkflowBundleError, match="bound provenance"):
        record.assert_matches(bundle, None, None, record.api_projection, record.ui_projection)


def test_current_rebind_invalid_live_provenance_rejects_both() -> None:
    bundle = load_bundle(_nonempty_workflow("invalid-live-provenance"))
    record = bundle.compile()
    bundle.workflow.source.provenance = "invalid"  # type: ignore[assignment]
    with pytest.raises(WorkflowBundleError, match="source provenance"):
        bundle.compile()
    with pytest.raises(WorkflowBundleError, match="source provenance"):
        record.assert_matches(bundle, None, None, record.api_projection, record.ui_projection)


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
    bundle = load_bundle(_nonempty_workflow())

    with pytest.raises(WorkflowBundleError, match="projection failed"):
        bundle.compile("missing")


def test_unknown_or_replaced_bundle_authority_fails_closed() -> None:
    from dataclasses import replace

    bundle = load_bundle(_nonempty_workflow("authority-kind"))
    assert bundle.authority_kind == "canonical"
    with pytest.raises(WorkflowBundleError, match="unknown workflow authority kind"):
        replace(bundle, authority_kind="untrusted").compile()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "workflow_id": "raw-queue-api",
            "prompt": {"1": {"class_type": "Integer", "inputs": {"value": 7}}},
        },
        {
            "workflow_id": "raw-queue-ui",
            "nodes": [{"id": 1, "type": "Integer", "widgets_values": [7]}],
            "links": [],
            "groups": [],
        },
    ],
)
def test_raw_import_cannot_queue_and_explicit_python_conversion_restores_authority(
    tmp_path: Path, payload: dict,
) -> None:
    from vibecomfy.runtime.execution import authorized_queue_payload
    from vibecomfy.testing.canonical import canonical_digest

    source = tmp_path / "raw.json"
    source.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    raw = load_bundle(source)
    api = {"1": {"class_type": "Integer", "inputs": {"value": 7}}}
    record = ApprovedProjectionRecord(
        raw.revision_id, None, {}, api, {}, canonical_digest(api)
    )
    with pytest.raises(WorkflowBundleError, match="runtime queue.*import evidence only"):
        authorized_queue_payload(record, raw)

    destination = tmp_path / "converted.py"
    converted = emit_bundle(
        raw.workflow,
        destination,
        {"operation": "captured", "source_digest": "a" * 64},
    )
    assert converted.authority_kind == "canonical"
    reloaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED)
    assert reloaded.authority_kind == "canonical"
    assert reloaded.compile().api_projection["1"]["class_type"] == "Integer"


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
    reconciliation = _nonempty_workflow("reconciliation")
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
        load_bundle(_nonempty_workflow("missing-model")).compile()


def test_bundle_model_gate_checks_picker_metadata_and_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.fetch as fetch
    import vibecomfy.model_assets as model_assets
    import vibecomfy.registry.models_loader as models_loader

    workflow = _nonempty_workflow("all-model-declarations")
    workflow.metadata["model_assets"] = [{"name": "metadata-model.bin", "subdir": "vae"}]
    workflow.requirements.models.append("requirements-model.bin")
    monkeypatch.setattr(
        model_assets,
        "_referenced_model_values",
        lambda _workflow: [{"value": "picker-model.bin", "subdir": "checkpoints"}],
    )
    monkeypatch.setattr(models_loader, "load_registry", lambda: (object(),))
    resolved: list[str] = []

    def resolve(value: str, **_kwargs: object) -> object:
        resolved.append(value)
        return type("Entry", (), {"targets": (type("Target", (), {"path": "checkpoints/model.bin"})(),)})()

    monkeypatch.setattr(models_loader, "resolve_model_entry", resolve)
    monkeypatch.setattr(fetch, "is_present", lambda entry, **_kwargs: True)
    from vibecomfy.workflow_bundle import _approval_preconditions

    _approval_preconditions(workflow, type("Provider", (), {"get_schema": lambda _self, _class: object()})())
    assert resolved == ["picker-model.bin", "metadata-model.bin", "requirements-model.bin"]


def test_bundle_model_gate_rejects_metadata_model_not_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.model_assets as model_assets
    import vibecomfy.registry.models_loader as models_loader

    workflow = _nonempty_workflow("metadata-model-missing")
    workflow.metadata["model_assets"] = [{"name": "metadata-model.bin", "subdir": "vae"}]
    monkeypatch.setattr(model_assets, "_referenced_model_values", lambda _workflow: [])
    monkeypatch.setattr(models_loader, "load_registry", lambda: ())
    monkeypatch.setattr(models_loader, "resolve_model_entry", lambda *_args, **_kwargs: None)
    with pytest.raises(WorkflowBundleError, match="not locally registered"):
        load_bundle(workflow).compile()


def test_bundle_identity_comes_from_lock_and_schema_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import vibecomfy.node_packs as node_packs
    import vibecomfy.porting.object_info as object_info
    from vibecomfy.node_packs import CustomNodePack, LockEntry
    from vibecomfy.workflow_bundle import _approval_preconditions

    workflow = _workflow("locked-identity")
    node = workflow.add_node("LockedNode", uid="locked-node", value=1)
    node.metadata["schema_source"] = {
        "provider": "object_info",
        "pack_slug": "locked-pack",
        "git_commit": "abc123",
    }
    pack = CustomNodePack("LockedPack", "local", frozenset({"LockedNode"}))
    lock = LockEntry(name="LockedPack", slug="locked-pack", commit="abc123", source="local", path="packs/locked")
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [lock])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: (pack,))
    calls: list[tuple[object, object, object]] = []

    def resolve(class_type: str, identity: object, *, allow_class_fallback: bool) -> object:
        calls.append((class_type, identity, allow_class_fallback))
        return SimpleNamespace(entry={"class_type": class_type})

    monkeypatch.setattr(object_info, "resolve_class_entry", resolve)
    provider = type("Provider", (), {"get_schema": lambda _self, _class: object()})()
    diagnostics = _approval_preconditions(workflow, provider)
    assert diagnostics == []
    assert calls == [("LockedNode", {"pack_slug": "locked-pack", "git_commit": "abc123"}, False)]


def test_bundle_live_target_identity_override_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Target-authority reconciliation remains visible in runtime schema evidence."""
    import vibecomfy.node_packs as node_packs
    import vibecomfy.porting.object_info as object_info
    from vibecomfy.node_packs import CustomNodePack, LockEntry
    from vibecomfy.runtime.session import _schema_provider_provenance
    from vibecomfy.workflow_bundle import _approval_preconditions

    workflow = _workflow("live-target-identity-evidence")
    workflow.add_node("TargetNode", uid="target-node", value=1)
    pack = CustomNodePack("TargetPack", "local", frozenset({"TargetNode"}))
    lock = LockEntry(name="TargetPack", slug="target-pack", commit="abc123", path="packs/target")
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [lock])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: (pack,))
    import vibecomfy.runtime.drift as drift
    monkeypatch.setattr(drift, "_nodepack_dir", lambda _name: object())
    monkeypatch.setattr(drift, "_git_head", lambda _path: "abc123")
    monkeypatch.setattr(
        object_info,
        "resolve_class_entry",
        lambda *_args, **_kwargs: type("Result", (), {"entry": None, "source": "identity_miss"})(),
    )
    provider = type(
        "TargetProvider",
        (),
        {
            "requires_fresh_target": True,
            "schema_authority": "live_target",
            "server_url": "http://target",
            "_active_server_url": "http://target",
            "_object_info_digest": "d" * 64,
            "get_schema": lambda _self, _class: object(),
        },
    )()

    _approval_preconditions(workflow, provider)
    evidence = _schema_provider_provenance(provider)
    assert evidence["approval_diagnostics"][0]["code"] == "live_target_schema_override"
    assert evidence["approval_diagnostics"][0]["target_schema_digest"] == "d" * 64
    assert evidence["approval_diagnostics"][0]["verified_installed_commit"] == "abc123"


def test_bundle_identity_lock_miss_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.node_packs as node_packs
    import vibecomfy.porting.object_info as object_info
    from vibecomfy.node_packs import CustomNodePack, LockEntry
    from vibecomfy.workflow_bundle import _approval_preconditions

    workflow = _workflow("locked-identity-miss")
    workflow.add_node("LockedNode", uid="locked-node", value=1)
    pack = CustomNodePack("LockedPack", "local", frozenset({"LockedNode"}))
    lock = LockEntry(name="LockedPack", slug="locked-pack", commit="abc123", source="local", path="packs/locked")
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [lock])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: (pack,))
    monkeypatch.setattr(
        object_info,
        "resolve_class_entry",
        lambda *_args, **_kwargs: type("Result", (), {"entry": None})(),
    )
    provider = type("Provider", (), {"get_schema": lambda _self, _class: object()})()
    with pytest.raises(WorkflowBundleError, match="object-info identity"):
        _approval_preconditions(workflow, provider)


def test_bundle_identity_miss_uses_fresh_target_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live target schema can supersede stale offline provenance only at runtime."""
    import vibecomfy.node_packs as node_packs
    import vibecomfy.porting.object_info as object_info
    from vibecomfy.node_packs import CustomNodePack
    from vibecomfy.workflow_bundle import _approval_preconditions

    workflow = _workflow("live-target-identity-miss")
    node = workflow.add_node("TargetNode", uid="target-node", value=1)
    node.metadata["object_info_identity"] = {
        "pack_slug": "target-pack",
        "git_commit": "historical-commit",
    }
    pack = CustomNodePack("TargetPack", "local", frozenset({"TargetNode"}))
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: (pack,))
    monkeypatch.setattr(
        object_info,
        "resolve_class_entry",
        lambda *_args, **_kwargs: type("Result", (), {"entry": None, "source": "identity_miss"})(),
    )
    provider = type(
        "TargetProvider",
        (),
        {
            "requires_fresh_target": True,
            "schema_authority": "live_target",
            "get_schema": lambda _self, _class: object(),
        },
    )()

    _approval_preconditions(workflow, provider)


def test_bundle_live_target_identity_pin_mismatch_remains_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """A live class hit cannot hide a pinned checkout mismatch."""
    import vibecomfy.node_packs as node_packs
    import vibecomfy.porting.object_info as object_info
    import vibecomfy.runtime.drift as drift
    from vibecomfy.node_packs import CustomNodePack, LockEntry
    from vibecomfy.workflow_bundle import _approval_preconditions

    workflow = _workflow("live-target-pin-mismatch")
    workflow.add_node("TargetNode", uid="target-node", value=1)
    pack = CustomNodePack("TargetPack", "local", frozenset({"TargetNode"}))
    lock = LockEntry(name="TargetPack", slug="target-pack", commit="expected", path="packs/target")
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [lock])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: (pack,))
    monkeypatch.setattr(drift, "_nodepack_dir", lambda _name: object())
    monkeypatch.setattr(drift, "_git_head", lambda _path: "different")
    monkeypatch.setattr(
        object_info,
        "resolve_class_entry",
        lambda *_args, **_kwargs: type("Result", (), {"entry": None, "source": "identity_miss"})(),
    )
    provider = type(
        "TargetProvider",
        (),
        {
            "requires_fresh_target": True,
            "schema_authority": "live_target",
            "get_schema": lambda _self, _class: object(),
        },
    )()

    with pytest.raises(WorkflowBundleError, match="installed checkout does not match expected"):
        _approval_preconditions(workflow, provider)


def test_bundle_identity_pack_conflict_with_lock_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.node_packs as node_packs
    import vibecomfy.porting.object_info as object_info
    from vibecomfy.node_packs import CustomNodePack, LockEntry
    from vibecomfy.workflow_bundle import _approval_preconditions

    workflow = _workflow("locked-pack-conflict")
    node = workflow.add_node("LockedNode", uid="locked-node", value=1)
    node.metadata["schema_source"] = {"pack_slug": "other-pack", "git_commit": "abc123"}
    pack = CustomNodePack("LockedPack", "local", frozenset({"LockedNode"}))
    lock = LockEntry(name="LockedPack", slug="locked-pack", commit="abc123", source="local", path="packs/locked")
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [lock])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: (pack,))
    monkeypatch.setattr(object_info, "resolve_class_entry", lambda *_args, **_kwargs: pytest.fail("resolver called"))
    provider = type("Provider", (), {"get_schema": lambda _self, _class: object()})()
    with pytest.raises(WorkflowBundleError, match="pack conflicts"):
        _approval_preconditions(workflow, provider)


def test_bundle_identity_commit_conflict_with_lock_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.node_packs as node_packs
    import vibecomfy.porting.object_info as object_info
    from vibecomfy.node_packs import CustomNodePack, LockEntry
    from vibecomfy.workflow_bundle import _approval_preconditions

    workflow = _workflow("locked-commit-conflict")
    node = workflow.add_node("LockedNode", uid="locked-node", value=1)
    node.metadata["object_info_identity"] = {
        "pack_slug": "locked-pack",
        "git_commit": "different-commit",
    }
    pack = CustomNodePack("LockedPack", "local", frozenset({"LockedNode"}))
    lock = LockEntry(name="LockedPack", slug="locked-pack", commit="abc123", source="local", path="packs/locked")
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [lock])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: (pack,))
    monkeypatch.setattr(object_info, "resolve_class_entry", lambda *_args, **_kwargs: pytest.fail("resolver called"))
    provider = type("Provider", (), {"get_schema": lambda _self, _class: object()})()
    with pytest.raises(WorkflowBundleError, match="pin conflicts"):
        _approval_preconditions(workflow, provider)


def test_bundle_missing_class_gate_is_cwd_independent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import vibecomfy.node_packs as node_packs
    from vibecomfy.workflow_bundle import _approval_preconditions

    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workflow = _workflow("cwd-independent")
    workflow.add_node("BoundNode", uid="bound-node", value=1)
    monkeypatch.setattr(node_packs, "read_lockfile", lambda _path: [])
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda _path: ())
    provider = type("Provider", (), {"get_schema": lambda _self, class_type: object() if class_type == "BoundNode" else None})()
    _approval_preconditions(workflow, provider)


def test_bundle_empty_workflow_rejected_before_compile(monkeypatch: pytest.MonkeyPatch) -> None:
    workflow = _workflow("empty-rejected")
    bundle = load_bundle(workflow)
    monkeypatch.setattr(workflow, "compile", lambda *_args, **_kwargs: pytest.fail("compiler called"))
    with pytest.raises(WorkflowBundleError, match="workflow is empty"):
        bundle.compile()


def test_load_bundle_hashes_same_basename_presentation_candidate(tmp_path: Path) -> None:
    source = tmp_path / "canonical.py"
    source.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    return VibeWorkflow('canonical', WorkflowSource('canonical'))\n",
        encoding="utf-8",
    )
    sidecar = tmp_path / "canonical.vibe.json"
    expected_sidecar = {
        "format_version": 1,
        "bind": {
            "workflow_identity": "canonical",
            "semantic_digest": _workflow("canonical").semantic_digest(),
        },
        "nodes": {},
        "links": [],
        "groups": [],
        "canvas": {"zoom": 1.0},
    }
    sidecar.write_text(json.dumps(expected_sidecar), encoding="utf-8")

    bundle = load_bundle(source, trust=Provenance.USER_CONFIRMED)

    assert bundle.ui_sidecar == expected_sidecar
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


def test_strict_sidecar_accepts_only_exact_schema_less_output_slot_witness() -> None:
    workflow = _connected_workflow()
    workflow.nodes["a"].native_output_names = None
    workflow.nodes["a"].native_output_slots = [0]
    sidecar = _strict_sidecar(workflow)
    sidecar["bind"]["semantic_digest"] = workflow.semantic_digest()

    assert validate_sidecar(sidecar, workflow)["links"]

    workflow.nodes["a"].native_output_slots = [1]
    sidecar["bind"]["semantic_digest"] = workflow.semantic_digest()
    with pytest.raises(WorkflowBundleError, match="unknown_virtual_wire_port"):
        validate_sidecar(sidecar, workflow)

    workflow.nodes["a"].native_output_names = [None]
    workflow.nodes["a"].native_output_slots = [0]
    sidecar["bind"]["semantic_digest"] = workflow.semantic_digest()
    with pytest.raises(WorkflowBundleError, match="outside or a hole"):
        validate_sidecar(sidecar, workflow)


def test_bundle_roundtrip_preserves_schema_less_authored_output_slot_witness(
    tmp_path: Path,
) -> None:
    workflow = _workflow("slot-witness-bundle")
    source = workflow.node("SchemaLessSource")
    source.out(3)
    workflow.nodes["target"] = VibeNode(
        "target",
        "Target",
        uid="target",
        inputs={"value": None},
        native_input_names=["value"],
    )
    workflow.edges.append(VibeEdge(source.node.id, "3", "target", "value"))
    sidecar = {
        "format_version": 1,
        "bind": {
            "workflow_identity": workflow.id,
            "semantic_digest": workflow.semantic_digest(),
        },
        "nodes": {
            source.node.uid: {"id": 1, "pos": [0, 0]},
            "target": {"id": 2, "pos": [10, 10]},
        },
        "links": [
            {
                "edge_ref": {
                    "scope_path": "",
                    "from_uid": source.node.uid,
                    "from_port": 3,
                    "to_uid": "target",
                    "to_port": 0,
                },
                "occurrence_index": 0,
                "id": 9,
            }
        ],
        "groups": [],
        "canvas": {"zoom": 1, "pan": [0, 0]},
    }
    destination = tmp_path / "slot_witness.py"

    emitted = emit_bundle_with_candidate(
        workflow, destination, {"operation": "authored"}, sidecar
    )
    loaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED)

    assert emitted.semantic_digest == loaded.semantic_digest
    assert loaded.workflow.nodes[source.node.id].native_output_names is None
    assert loaded.workflow.nodes[source.node.id].native_output_slots == [3]
    assert loaded.ui_sidecar is not None


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


def test_strict_sidecar_rejects_occurrence_gaps_and_duplicate_native_ids() -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    duplicate = dict(sidecar["links"][0]); duplicate["occurrence_index"] = 2; duplicate["id"] = 10
    sidecar["links"].append(duplicate)
    with pytest.raises(WorkflowBundleError, match="contiguous"):
        validate_sidecar(sidecar, workflow)


def test_sidecar_digest_drift_is_diagnostic_when_workflow_identity_matches() -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    sidecar["bind"]["semantic_digest"] = "different-authorized-revision-digest"

    normalized = validate_sidecar(sidecar, workflow)

    assert normalized["bind"]["workflow_identity"] == workflow.id
    assert normalized["bind"]["semantic_digest"] == "different-authorized-revision-digest"


def test_sidecar_identity_mismatch_remains_fail_closed_even_with_digest_drift() -> None:
    workflow = _connected_workflow()
    sidecar = _strict_sidecar(workflow)
    sidecar["bind"]["workflow_identity"] = "other-workflow"
    sidecar["bind"]["semantic_digest"] = "different-authorized-revision-digest"

    with pytest.raises(WorkflowBundleError, match="workflow_identity"):
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


def test_first_build_semantic_drift_preserves_existing_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The private canonicalization preflight must fail before publication."""
    workflow = _nonempty_workflow("first-build-drift")
    destination = tmp_path / "first-build-drift.py"
    emit_bundle(workflow, destination, {"operation": "authored"})
    python_before = destination.read_bytes()
    sidecar_before = destination.with_suffix(".vibe.json").read_bytes()
    real_load_scratchpad = load_scratchpad

    def load_with_first_build_drift(*args, **kwargs):
        loaded = real_load_scratchpad(*args, **kwargs)
        loaded.nodes["1"].inputs["value"] = 8
        return loaded

    monkeypatch.setattr(
        "vibecomfy.scratchpad_loader.load_scratchpad",
        load_with_first_build_drift,
    )
    candidate = {
        "format_version": 1,
        "bind": {"workflow_identity": workflow.id, "semantic_digest": workflow.semantic_digest()},
        "nodes": {}, "links": [], "groups": [], "canvas": {},
    }
    with pytest.raises(WorkflowBundleError, match="first-build semantic digest"):
        emit_bundle_with_candidate(
            workflow, destination, {"operation": "authored"}, candidate,
        )
    assert destination.read_bytes() == python_before
    assert destination.with_suffix(".vibe.json").read_bytes() == sidecar_before


def test_helper_custody_preserves_source_backed_canvas_geometry(tmp_path: Path) -> None:
    """Lowered helpers stay inspectable in the companion without Python bloat."""
    workflow = _workflow("helper-geometry")
    workflow.nodes["source"] = VibeNode(
        "source", "SchemaLessSource", uid="source", native_output_names=["IMAGE"],
    )
    workflow.nodes["reroute"] = VibeNode(
        "reroute", "Reroute", uid="reroute", pos=[5, 6], size=[75, 26],
    )
    workflow.nodes["sink"] = VibeNode(
        "sink", "SchemaLessSink", uid="sink", inputs={"image": None},
        native_input_names=["image"],
    )
    workflow.edges = [
        VibeEdge("source", "0", "reroute", "0"),
        VibeEdge("reroute", "0", "sink", "image"),
    ]
    first_path = tmp_path / "helper-geometry.py"
    emit_bundle(workflow, first_path, {"operation": "authored"})
    first = load_bundle(first_path, trust=Provenance.USER_CONFIRMED)
    helper = first.ui_sidecar["custody"]["scopes"][0]["helpers"][0]
    assert helper["uid"] == "reroute"
    assert helper["pos"] == [5.0, 6.0]
    assert helper["size"] == [75.0, 26.0]

    second_path = tmp_path / "helper-geometry-copy.py"
    emit_bundle(first.workflow, second_path, {"operation": "authored"})
    second = load_bundle(second_path, trust=Provenance.USER_CONFIRMED)
    assert second.ui_sidecar["custody"]["scopes"][0]["helpers"][0]["pos"] == [5.0, 6.0]


def test_recursive_companion_scopes_match_recursive_definitions(tmp_path: Path) -> None:
    from tests.test_b11b_execution_projection import _depth_two_sibling_workflow
    from vibecomfy.workflow_bundle import _validate_v2_custody

    workflow, inner_key, outer_key = _depth_two_sibling_workflow()
    path = tmp_path / "recursive-scopes.py"
    bundle = emit_bundle(workflow, path, {"operation": "authored"})
    assert bundle.ui_sidecar is not None
    custody = copy.deepcopy(bundle.ui_sidecar["custody"])
    custody["scopes"] = [
        scope
        for scope in custody["scopes"]
        if scope["scope_path"] != f"{outer_key}/{inner_key}"
    ]
    with pytest.raises(WorkflowBundleError, match="scopes do not match definitions"):
        _validate_v2_custody(custody)


def test_recursive_companion_is_closed_and_structural_only(tmp_path: Path) -> None:
    """Recursive custody cannot become a hidden graph/value replay channel."""
    from tests.test_b11b_execution_projection import _depth_two_sibling_workflow
    from vibecomfy.workflow_bundle import _validate_v2_custody

    workflow, _inner_key, _outer_key = _depth_two_sibling_workflow()
    bundle = emit_bundle(workflow, tmp_path / "recursive-closed.py", {"operation": "authored"})
    assert bundle.ui_sidecar is not None
    base = copy.deepcopy(bundle.ui_sidecar["custody"])
    definition = base["definitions"]["subgraphs"][0]
    record = definition["definitions"]["subgraphs"][0]["_constructor_nodes"][0]

    cases = (
        ("runtime payload", lambda custody: custody["definitions"]["subgraphs"][0].update(
            {"runtime_payload": {"nodes": [{"id": "999"}], "value": 7}}
        )),
        ("record extension", lambda custody: custody["definitions"]["subgraphs"][0]["_constructor_nodes"][0].update(
            {"replay_values": {"x": 7}}
        )),
        ("shape extension", lambda custody: custody["definitions"]["subgraphs"][0]["definitions"]["subgraphs"][0]
            ["_constructor_nodes"][0]["input_shape"][0].update({"value": 7})),
        ("nested container extension", lambda custody: custody["definitions"]["subgraphs"][0].update(
            {"definitions": {"subgraphs": [], "edges": []}}
        )),
    )
    assert record["input_shape"]
    for label, mutate in cases:
        candidate = copy.deepcopy(base)
        mutate(candidate)
        with pytest.raises(WorkflowBundleError, match="unknown field|only subgraphs"):
            _validate_v2_custody(candidate)


def test_rewriting_existing_pair_preserves_authored_presentation(tmp_path: Path) -> None:
    """Editing semantic Python must retain the existing companion's canvas."""
    workflow = _nonempty_workflow("presentation-rewrite")
    destination = tmp_path / "presentation-rewrite.py"
    candidate = {
        "format_version": 1,
        "bind": {
            "workflow_identity": workflow.id,
            "semantic_digest": workflow.semantic_digest(),
        },
        "nodes": {
            "integer-node": {"id": 7, "pos": [101, 202], "class_type": "Integer"},
            "note": {"id": 8, "pos": [303, 404], "class_type": "MarkdownNote"},
        },
        "links": [],
        "groups": [],
        "canvas": {},
        "annotations": [{
        "annotation_id": "note",
        "scope_path": "",
        "owner": {"kind": "node", "uid": "note"},
        "class_type": "MarkdownNote",
        "title": "Authored note",
        "content": "Keep this through an edit",
        }],
    }
    emit_bundle_with_candidate(workflow, destination, {"operation": "captured"}, candidate)

    loaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED)
    loaded.workflow.nodes["1"].inputs["value"] = 8
    emit_bundle(loaded.workflow, destination, {"operation": "authored"})
    rewritten = load_bundle(destination, trust=Provenance.USER_CONFIRMED)
    presentation = rewritten.ui_sidecar["presentation"]
    assert rewritten.workflow.nodes["1"].inputs["value"] == 8
    assert presentation["nodes"]["integer-node"]["pos"] == [101.0, 202.0]
    assert presentation["nodes"]["note"]["pos"] == [303.0, 404.0]
    assert presentation["annotations"][0]["content"] == "Keep this through an edit"


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
    with pytest.raises(WorkflowBundleError, match="legacy_virtual_wire"):
        validate_sidecar(sidecar, workflow)
    workflow.virtual_wires = {"ghost": {"legs": [{
        "scope_path": "",
        "leg_index": 0,
        "occurrence_index": 0,
        "from_node": "source",
        "from_output": 0,
        "to_node": "ghost",
        "to_input": 0,
    }]}}
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
    bad_groups = dict(base)
    bad_groups["groups"] = None
    with pytest.raises(WorkflowBundleError, match="captured groups must be a list"):
        capture_bundle(bad_groups, tmp_path / "bad-groups.py", {"operation": "captured"})


def test_presentation_graph_door_returns_detached_records() -> None:
    from vibecomfy.porting.emit.ui import capture_presentation_graph_records

    candidate = {
        "nodes": [{"id": 1, "properties": {"vibecomfy_uid": "source"}}],
        "links": [[7, 1, 0, 2, 0, "IMAGE"]],
        "groups": [{"id": 3, "nodes": [1]}],
    }
    captured = capture_presentation_graph_records(candidate)
    candidate["nodes"][0]["properties"]["vibecomfy_uid"] = "changed"
    candidate["links"][0][0] = 99
    candidate["groups"][0]["nodes"].append(2)

    assert captured.nodes[0]["properties"]["vibecomfy_uid"] == "source"
    assert captured.links[0][0] == 7
    assert captured.groups[0]["nodes"] == [1]
    assert captured.groups_present is True

    absent_groups = capture_presentation_graph_records({"nodes": [], "links": []})
    assert absent_groups.groups is None
    assert absent_groups.groups_present is False


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
    presentation = bundle.ui_sidecar["presentation"]
    assert presentation["nodes"]["source"]["collapsed"] is True
    assert presentation["nodes"]["source"]["group"] == "7"
    assert presentation["groups"][0]["presentation_id"] == "7"
    assert presentation["canvas"] == {"zoom": 1.5, "pan": [11.0, 12.0]}
    assert "reroute" not in presentation["links"][0]
    graph["nodes"][0]["properties"]["widget_ue_connectable"] = True
    extra = capture_bundle(graph, tmp_path / "extra-prop.py", {"operation": "captured"})
    extra_presentation = extra.ui_sidecar["presentation"]
    assert extra_presentation["nodes"]["source"]["id"] == 1
    assert "widget_ue_connectable" not in extra_presentation["nodes"]["source"]


def test_capture_coerces_oversized_node_size_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LiteGraph size sometimes has extra members; capture must not abort apply."""
    workflow = _connected_workflow()
    for node in workflow.nodes.values():
        node.metadata["schema_source"] = {"provider": "authoritative_object_info"}
    graph = {
        "workflow_id": workflow.id,
        "nodes": [
            {
                "id": 1,
                "type": "Source",
                "pos": [1, 2, 0],
                "size": [3, 4, 1],
                "properties": {"vibecomfy_uid": "source"},
            },
            {
                "id": 2,
                "type": "Target",
                "pos": [5, 6],
                "size": [7, 8],
                "properties": {"vibecomfy_uid": "target"},
            },
        ],
        "links": [[9, 1, 0, 2, 0, "A"]],
        "groups": [],
    }
    monkeypatch.setattr("vibecomfy.ingest.normalize._named_import", lambda *args, **kwargs: workflow)
    bundle = capture_bundle(graph, tmp_path / "size.py", {"operation": "captured"})
    presentation = bundle.ui_sidecar["presentation"]
    assert presentation["nodes"]["source"]["size"] == [3.0, 4.0]
    assert presentation["nodes"]["source"]["pos"] == [1.0, 2.0]


def test_emit_bundle_rejects_semantic_digest_drift_before_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A staged semantic mismatch leaves both existing artifacts untouched."""
    workflow = _workflow("drift-id")
    workflow.add_node("Integer", uid="integer-node", value=7)
    destination = tmp_path / "drift.py"
    baseline = emit_bundle(workflow, destination, {"operation": "authored"})
    real_load_scratchpad = load_scratchpad

    load_calls = 0

    def load_with_diagnostic_drift(*args, **kwargs):
        nonlocal load_calls
        loaded = real_load_scratchpad(*args, **kwargs)
        load_calls += 1
        # Pair canonicalization performs one private staged load.  Drift on
        # the later visible publication preflight must still abort atomically.
        if load_calls >= 2:
            loaded.nodes["1"].inputs["value"] = 8
        return loaded

    monkeypatch.setattr(
        "vibecomfy.scratchpad_loader.load_scratchpad",
        load_with_diagnostic_drift,
    )
    sidecar = destination.with_suffix(".vibe.json")
    sidecar_payload = {
        "format_version": 1,
        "bind": {"workflow_identity": workflow.id, "semantic_digest": baseline.semantic_digest},
        "nodes": {}, "links": [], "groups": [], "canvas": {},
    }
    sidecar.write_text(json.dumps(sidecar_payload, sort_keys=True) + "\n", encoding="utf-8")
    python_before = destination.read_bytes()
    sidecar_before = sidecar.read_bytes()
    with pytest.raises(WorkflowBundleError, match="semantic digest"):
        emit_bundle(workflow, destination, {"operation": "authored"})
    assert destination.read_bytes() == python_before
    assert sidecar.read_bytes() == sidecar_before
    assert baseline.workflow.id == workflow.id


@pytest.mark.parametrize(
    "auxiliary_class",
    ["PreviewAny", "easy showAnything", "FutureCustomAuxiliaryOutput"],
)
def test_parameter_edit_publish_preserves_auxiliary_output_node_identity(
    tmp_path: Path,
    auxiliary_class: str,
) -> None:
    workflow = _workflow(f"auxiliary-output-{auxiliary_class}")
    workflow.nodes["3"] = VibeNode(
        "3",
        "ParameterNode",
        uid="parameters",
        inputs={"temperature": 0.8, "max_tokens": 1024},
    )
    workflow.nodes["6"] = VibeNode(
        "6",
        auxiliary_class,
        uid="auxiliary-output",
        inputs={"source": None},
    )
    sidecar = {
        "format_version": 1,
        "bind": {
            "workflow_identity": workflow.id,
            "semantic_digest": workflow.semantic_digest(),
        },
        "nodes": {
            "parameters": {"id": 3, "pos": [0, 0]},
            "auxiliary-output": {"id": 6, "pos": [300, 0]},
        },
        "links": [],
        "groups": [],
        "canvas": {},
    }
    destination = tmp_path / "edited.py"

    workflow.nodes["3"].inputs["max_tokens"] = 512
    published = emit_bundle_with_candidate(
        workflow,
        destination,
        {"operation": "authored"},
        sidecar,
    )
    reloaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED)
    projected_uids = {
        node["uid"] for node in canonical_ir_projection(reloaded.workflow)["nodes"]
    }

    assert reloaded.workflow.nodes["3"].inputs["max_tokens"] == 512
    assert projected_uids == {"parameters", "auxiliary-output"}
    assert reloaded.workflow.nodes["6"].class_type == auxiliary_class
    assert reloaded.ui_sidecar is not None
    assert validate_sidecar(reloaded.ui_sidecar, reloaded.workflow) == reloaded.ui_sidecar
    assert published.workflow.nodes["6"].class_type == auxiliary_class


def test_parameter_edit_sidecar_still_rejects_dangling_auxiliary_uid() -> None:
    workflow = _workflow("dangling-auxiliary-output")
    workflow.nodes["3"] = VibeNode(
        "3",
        "ParameterNode",
        uid="parameters",
        inputs={"temperature": 0.8, "max_tokens": 512},
    )
    sidecar = {
        "format_version": 1,
        "bind": {
            "workflow_identity": workflow.id,
            "semantic_digest": workflow.semantic_digest(),
        },
        "nodes": {
            "parameters": {"id": 3},
            "dangling-auxiliary-output": {"id": 6},
        },
        "links": [],
        "groups": [],
        "canvas": {},
    }

    with pytest.raises(WorkflowBundleError, match="does not match a Python node"):
        validate_sidecar(sidecar, workflow)


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
    assert bundle.ui_sidecar["presentation"]["nodes"]["u"] == {"id": 1}


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
    workflow = _nonempty_workflow("api-capture")
    api = {"workflow_id": workflow.id, "1": {"class_type": "Integer", "inputs": {"value": 1}}}
    monkeypatch.setattr("vibecomfy.ingest.normalize._named_import", lambda *args, **kwargs: workflow)
    bundle = capture_bundle(api, tmp_path / "api.py", {"operation": "captured"})
    assert bundle.workflow_identity == workflow.id
    assert bundle.ui_sidecar is not None
    assert bundle.ui_sidecar["format_version"] == 2
    assert bundle.ui_sidecar["presentation"] == {
        "nodes": {}, "links": [], "groups": [], "canvas": {}, "annotations": []
    }


def test_v2_companion_keeps_generated_python_small_and_round_trippable(tmp_path: Path) -> None:
    workflow = _nonempty_workflow("v2-shape")
    path = tmp_path / "v2-shape.py"

    bundle = emit_bundle(workflow, path, {"operation": "authored"})
    source = path.read_text(encoding="utf-8")

    assert path.with_suffix(".vibe.json").is_file()
    assert bundle.ui_sidecar is not None
    assert set(bundle.ui_sidecar) == {"format_version", "bind", "custody", "presentation"}
    assert all(
        token not in source
        for token in (
            "CANONICAL_CUSTODY",
            "HELPER_CUSTODY",
            "resolver_helper_custody",
            "wf.connect(",
            "wf.nodes[",
        )
    )
    assert "wf = wf.finalize({}, outputs=[])" in source
    loaded = load_bundle(path, trust=Provenance.USER_CONFIRMED)
    assert loaded.semantic_digest == bundle.semantic_digest
    assert loaded.ui_digest == bundle.ui_digest
    assert validate_sidecar(loaded.ui_sidecar, loaded.workflow) == loaded.ui_sidecar


def _assert_clean_v2_source(source: str) -> None:
    """Apply the whole-file readability contract used by the v2 evidence gate."""
    tree = ast.parse(source)
    def literal_keys(node: ast.AST) -> set[str]:
        if not isinstance(node, ast.Dict):
            return set()
        return {
            key.value for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }

    # Custody is an external companion concern.  Detect its shape rather than
    # banning ordinary constants/helpers merely because of their names.
    graph_payload_keys = {"nodes", "links", "edges", "helpers", "scopes"}
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        value = statement.value
        keys = literal_keys(value)
        assert not (
            {"scopes"} <= keys
            or {"generation_id", "custody_digest"} <= keys
            or len(keys & graph_payload_keys) >= 2
        )
    assert not any(
        isinstance(node, ast.Name) and "custody" in node.id.casefold()
        for node in ast.walk(tree)
    )
    replay_ops = {"connect", "finalize"}
    for statement in ast.walk(tree):
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) or statement.name == "build":
            continue
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in replay_ops
            for node in ast.walk(statement)
        )
        assert not any(
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "nodes"
            for node in ast.walk(statement)
        )
    build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build")
    graph_names = {
        target.id
        for node in ast.walk(build)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "new_workflow"
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    graph_names.update(
        item.optional_vars.id
        for node in ast.walk(build)
        if isinstance(node, ast.With)
        for item in node.items
        if isinstance(item.optional_vars, ast.Name)
        and isinstance(item.context_expr, ast.Call)
        and isinstance(item.context_expr.func, ast.Name)
        and item.context_expr.func.id == "new_workflow"
    )
    assert graph_names
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "connect"
        for node in ast.walk(build)
    )
    assert not any(
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "nodes"
        for node in ast.walk(build)
    )

    finalizers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "finalize"
    ]
    assert len(finalizers) == 1
    assert len(finalizers[0].args) == 1
    assert {keyword.arg for keyword in finalizers[0].keywords} == {"outputs"}

    marker_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "build"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ReadyMetadata"
    ]
    assert len(marker_calls) == 1
    source_bundle = next(
        keyword.value
        for keyword in marker_calls[0].keywords
        if keyword.arg == "source_bundle"
    )
    assert isinstance(source_bundle, ast.Dict)
    marker_keys = {
        key.value for key in source_bundle.keys if isinstance(key, ast.Constant)
    }
    assert marker_keys == {"format_version", "generation_id", "custody_digest"}


def test_v2_source_contract_rejects_whole_file_integrity_mutations(tmp_path: Path) -> None:
    """Mutation evidence covers hidden custody, replay tails, and bloated finalizers."""
    path = tmp_path / "source-contract.py"
    emit_bundle(_nonempty_workflow("source-contract"), path, {"operation": "authored"})
    source = path.read_text(encoding="utf-8")
    _assert_clean_v2_source(source)
    anchor = "        wf = wf.finalize({}, outputs=[] )"
    if anchor not in source:
        anchor = "        wf = wf.finalize({}, outputs=[])"
    assert anchor in source

    mutations = {
        "hidden custody": source.replace(
            "def build() -> VibeWorkflow:\n",
            "def build() -> VibeWorkflow:\n    helper_custody = {}\n",
            1,
        ),
        "replay topology": source.replace(
            anchor,
                "        wf.connect('integer-node.0', 'integer-node.value')\n" + anchor,
            1,
        ),
        "renamed graph topology": source.replace(
            anchor,
                "        graph.connect('integer-node.0', 'integer-node.value')\n" + anchor,
            1,
        ),
        "duplicate runtime value": source.replace(
            anchor,
                "        wf.nodes['replay'] = object()\n" + anchor,
            1,
        ),
        "bloated finalizer": source.replace(
            anchor,
            anchor[:-1] + ", canonical_custody={})",
            1,
        ),
        "module custody payload": source.replace(
            "from vibecomfy.workflow import VibeWorkflow\n",
            "from vibecomfy.workflow import VibeWorkflow\n"
            "MODULE_PAYLOAD = {'scopes': [], 'unexpected': {'nodes': []}}\n",
            1,
        ),
        "neutral module graph payload": source.replace(
            "from vibecomfy.workflow import VibeWorkflow\n",
            "from vibecomfy.workflow import VibeWorkflow\n"
            "MODULE_DATA = {'nodes': [], 'links': []}\n",
            1,
        ),
        "module replay helper": source.replace(
            "def build() -> VibeWorkflow:\n",
            "def replay_graph(wf):\n    return wf.finalize({}, outputs=[])\n\n"
            "def build() -> VibeWorkflow:\n",
            1,
        ),
        "nested module replay helper": source.replace(
            "def build() -> VibeWorkflow:\n",
            "def wrapper(wf):\n"
            "    def replay(wf):\n"
            "        return wf.nodes['replay']\n"
            "    return replay(wf)\n\n"
            "def build() -> VibeWorkflow:\n",
            1,
        ),
    }
    for label, mutated in mutations.items():
        with pytest.raises(AssertionError):
            _assert_clean_v2_source(mutated)


def test_v2_custody_rejects_open_or_graph_shaped_generated_provenance() -> None:
    from vibecomfy.workflow_bundle import _validate_v2_custody

    def custody(*, metadata=None, helper_provenance=None) -> dict:
        node = {
            "label": "node", "id": "1", "uid": "node", "class_type": "Integer",
            "metadata": metadata or {"provenance": "untrusted_source"},
        }
        helpers = []
        if helper_provenance is not None:
            helpers.append({
                "id": "helper", "uid": "helper", "class_type": "MarkdownNote",
                "provenance": helper_provenance,
            })
        return {"scopes": [{"scope_path": "", "nodes": [node], "helpers": helpers}]}

    with pytest.raises(WorkflowBundleError, match="provenance"):
        _validate_v2_custody(custody(metadata={"provenance": {"nodes": [], "links": []}}))
    with pytest.raises(WorkflowBundleError, match="provenance"):
        _validate_v2_custody(custody(helper_provenance={"workflow_shape": {"nodes": 1}, "payload": {}}))
    valid = _validate_v2_custody(custody(helper_provenance={"workflow_shape": {"nodes": 1}}))
    assert valid["scopes"][0]["helpers"][0]["provenance"]["workflow_shape"]["nodes"] == 1


def test_v2_rebuild_refreshes_edited_model_requirement(tmp_path: Path) -> None:
    workflow = _workflow("model-requirement-refresh")
    workflow.nodes["1"] = VibeNode(
        "1",
        "CheckpointLoaderSimple",
        inputs={"ckpt_name": "old.safetensors"},
        uid="loader",
    )
    workflow.requirements.models = ["old.safetensors"]
    path = tmp_path / "model-requirement-refresh.py"
    emit_bundle(workflow, path, {"operation": "authored"})

    source = path.read_text(encoding="utf-8")
    source = source.replace(
        "CKPT_NAME = 'old.safetensors'",
        "CKPT_NAME = 'new.safetensors'",
        1,
    )
    path.write_text(source, encoding="utf-8")

    rebuilt = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
    assert rebuilt.nodes["1"].inputs["ckpt_name"] == "new.safetensors"
    assert rebuilt.requirements.models == ["new.safetensors"]


def test_v2_annotations_bind_scope_and_owner_and_materialize_content(tmp_path: Path) -> None:
    workflow = _nonempty_workflow("annotation-binding")
    companion = emit_bundle(
        workflow, tmp_path / "annotation-binding.py", {"operation": "authored"}
    ).ui_sidecar
    assert companion is not None
    presentation = companion["presentation"]
    presentation["nodes"] = {"note": {"class_type": "MarkdownNote", "id": 7}}
    presentation["annotations"] = [{
        "annotation_id": "note", "scope_path": "",
        "owner": {"kind": "node", "uid": "note"},
        "class_type": "MarkdownNote", "title": "Note", "content": "preserve me",
    }]
    normalized = validate_sidecar(companion, workflow)
    materialized = materialize_ui_json(workflow, normalized)
    note = next(node for node in materialized["nodes"] if node.get("type") == "MarkdownNote")
    assert note["widgets_values"] == ["preserve me"]

    bad_scope = copy.deepcopy(companion)
    bad_scope["presentation"]["annotations"][0]["scope_path"] = "definition:missing"
    with pytest.raises(WorkflowBundleError, match="structural workflow scope"):
        validate_sidecar(bad_scope, workflow)
    bad_owner = copy.deepcopy(companion)
    bad_owner["presentation"]["annotations"][0]["owner"]["uid"] = "ghost"
    with pytest.raises(WorkflowBundleError, match="does not identify a node"):
        validate_sidecar(bad_owner, workflow)

    bad_annotation_id = copy.deepcopy(companion)
    bad_annotation_id["presentation"]["annotations"][0]["annotation_id"] = "other"
    with pytest.raises(WorkflowBundleError, match="self-owned"):
        validate_sidecar(bad_annotation_id, workflow)

    missing_presentation_node = copy.deepcopy(companion)
    missing_presentation_node["presentation"]["annotations"][0]["owner"]["uid"] = "missing"
    missing_presentation_node["presentation"]["annotations"][0]["annotation_id"] = "missing"
    with pytest.raises(WorkflowBundleError, match="presentation node"):
        validate_sidecar(missing_presentation_node, workflow)


def test_presentation_collision_remint_keeps_semantic_link_endpoints() -> None:
    workflow = _connected_workflow()
    from vibecomfy.porting.emit.ui import _overlay_validated_presentation

    envelope = {
        "nodes": [
            {"id": 159, "type": "Source", "properties": {"vibecomfy_uid": "source"}, "outputs": [{"links": [9]}]},
            {"id": 168, "type": "Target", "properties": {"vibecomfy_uid": "target"}, "inputs": [{"link": 9}]},
        ],
        "links": [[9, 159, 0, 168, 0, "A"]],
    }
    presentation = {
        "nodes": {"note": {"id": 159, "class_type": "MarkdownNote"}},
        "links": [], "groups": [], "canvas": {}, "annotations": [],
    }
    _overlay_validated_presentation(envelope, presentation, workflow)
    materialized = envelope
    nodes = {node["id"]: node for node in materialized["nodes"]}
    assert len(nodes) == 3
    assert any(node.get("type") == "MarkdownNote" for node in nodes.values())
    link = materialized["links"][0]
    assert link[1] != 159
    assert link[3] == 168
    assert link[1] in nodes and link[3] in nodes


def test_v2_companion_is_required_and_swapping_it_is_refused(tmp_path: Path) -> None:
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    emit_bundle(_nonempty_workflow("first"), first, {"operation": "authored"})
    emit_bundle(_nonempty_workflow("second"), second, {"operation": "authored"})

    companion = first.with_suffix(".vibe.json")
    original = companion.read_bytes()
    companion.unlink()
    with pytest.raises(WorkflowBundleError, match="companion is missing"):
        load_bundle(first, trust=Provenance.USER_CONFIRMED)

    companion.write_bytes(second.with_suffix(".vibe.json").read_bytes())
    with pytest.raises(WorkflowBundleError, match="identity"):
        load_bundle(first, trust=Provenance.USER_CONFIRMED)
    companion.write_bytes(original)


def test_v2_companion_rejects_duplicate_json_keys_before_loading_python(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.py"
    emit_bundle(_nonempty_workflow("duplicate"), path, {"operation": "authored"})
    path.with_suffix(".vibe.json").write_text(
        '{"format_version": 2, "format_version": 2}',
        encoding="utf-8",
    )

    with pytest.raises(WorkflowBundleError, match="duplicate JSON key"):
        load_bundle(path, trust=Provenance.USER_CONFIRMED)


def test_v2_companion_regeneration_is_deterministic(tmp_path: Path) -> None:
    first = emit_bundle(
        _nonempty_workflow("deterministic"),
        tmp_path / "one.py",
        {"operation": "authored"},
    )
    second = emit_bundle(
        _nonempty_workflow("deterministic"),
        tmp_path / "two.py",
        {"operation": "authored"},
    )

    assert (tmp_path / "one.py").read_bytes() == (tmp_path / "two.py").read_bytes()
    assert (tmp_path / "one.vibe.json").read_bytes() == (tmp_path / "two.vibe.json").read_bytes()
    assert first.revision_id == second.revision_id


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


def test_canonical_roundtrip_preserves_explicit_none_input_default(tmp_path: Path) -> None:
    workflow = _workflow("explicit-none-default")
    workflow.nodes["1"] = VibeNode(
        "1",
        "MysteryModel",
        inputs={"model": "current-model.safetensors"},
        uid="model",
    )
    # Construct the descriptor directly to represent the authored distinction
    # that register_input(value=..., default=None) cannot express: the current
    # model is a value, while the public default is intentionally unset.
    workflow.inputs["model"] = VibeInput(
        "model",
        "1",
        "model",
        "current-model.safetensors",
        type="STRING",
        default=None,
    )
    workflow._manual_input_names.add("model")

    destination = tmp_path / "explicit-none-default.py"
    bundle = emit_bundle(workflow, destination, {"operation": "authored"})
    reloaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED)

    assert reloaded.workflow.inputs["model"].value == "current-model.safetensors"
    assert reloaded.workflow.inputs["model"].default is None
    assert reloaded.semantic_digest == bundle.semantic_digest == workflow.semantic_digest()
    assert reloaded.revision_id == bundle.revision_id


def test_native_port_rosters_are_semantic_not_execution_data(tmp_path: Path) -> None:
    from vibecomfy.porting.emit.entrypoints import emit_scratchpad_python

    workflow = _connected_workflow()
    api_before = workflow.compile("api")
    digest_before = workflow.semantic_digest()
    workflow.nodes["a"].native_output_names = ["changed"]
    assert workflow.semantic_digest() != digest_before
    assert workflow.compile("api") == api_before

    source = emit_scratchpad_python(workflow)
    assert "'native_input_names':" not in source
    assert "'native_output_names':" not in source
    path = tmp_path / "generated.py"
    bundle = emit_bundle(workflow, path, {"operation": "authored"})
    assert bundle.ui_sidecar is not None
    assert "_native_ports=" not in source
    assert "_ui=" not in source
    loaded = load_bundle(path, trust=Provenance.USER_CONFIRMED).workflow
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


@pytest.mark.parametrize("bad_name", [{}, False, 7, ""])
def test_v2_native_port_roster_names_reject_nonblank_nonnull_values(bad_name) -> None:
    from vibecomfy.workflow_bundle import _validate_native_ports

    with pytest.raises(WorkflowBundleError, match="nonblank strings or null"):
        _validate_native_ports(
            {"native_input_names": ["head", bad_name, "tail"]},
            "custody node native ports",
        )
    accepted = _validate_native_ports(
        {"native_output_names": ["head", None, "tail"]},
        "custody node native ports",
    )
    assert accepted["native_output_names"] == ["head", None, "tail"]


def test_v2_canonical_pair_preserves_sparse_native_port_rosters(tmp_path: Path) -> None:
    workflow = _workflow("sparse-native-rosters")
    workflow.nodes["source"] = VibeNode(
        "source", "Source", uid="source",
        native_output_names=["out", None, "tail"],
        native_output_types=["A", None, "B"],
    )
    workflow.nodes["target"] = VibeNode(
        "target", "Target", uid="target", inputs={"in": None},
        native_input_names=["in", None, "tail"],
        native_input_types=["A", None, "B"],
        native_input_optional=[False, True, False],
    )
    workflow.edges.append(VibeEdge("source", "0", "target", "0"))

    path = tmp_path / "sparse-native-rosters.py"
    bundle = emit_bundle(workflow, path, {"operation": "authored"})
    assert bundle.ui_sidecar is not None
    validate_sidecar(bundle.ui_sidecar, workflow)
    loaded = load_bundle(path, trust=Provenance.USER_CONFIRMED)
    assert loaded.workflow.nodes["source"].native_output_names == ["out", None, "tail"]
    assert loaded.workflow.nodes["source"].native_output_types == ["A", None, "B"]
    assert loaded.workflow.nodes["target"].native_input_names == ["in", None, "tail"]
    assert loaded.workflow.nodes["target"].native_input_types == ["A", None, "B"]
    assert loaded.workflow.nodes["target"].native_input_optional == [False, True, False]


def test_recursive_edges_and_virtual_wires_use_structural_scope_and_local_uids() -> None:
    from vibecomfy.identity.scope import compose_scope_path, sg_key
    from vibecomfy.identity.uid import make_uid

    workflow = _workflow("recursive")
    definition = {
        "name": "inner",
        "nodes": [
            {"id": 10, "uid": "left", "class_type": "A", "outputs": [{"name": "out"}]},
            {"id": 20, "uid": "right", "class_type": "B", "inputs": [{"name": None}, {"name": "value"}]},
        ],
        "links": [{"origin_id": 10, "origin_slot": 0, "target_id": 20, "target_slot": 1}],
        "virtual_wires": {},
    }
    workflow.definitions = {"one": definition}
    scope = compose_scope_path((sg_key(definition),))
    definition["virtual_wires"] = {"vw": {"legs": [{
        "scope_path": scope,
        "leg_index": 0,
        "occurrence_index": 0,
        "from_node": "left",
        "from_output": "out",
        "to_node": "right",
        "to_input": "value",
    }]}}
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


def test_normalized_virtual_wire_legs_materialize_through_native_port_rosters() -> None:
    from vibecomfy.ingest.normalize import _normalize_virtual_wires

    workflow = _workflow("canonical-virtual-wire")
    workflow.nodes["source"] = VibeNode(
        "source", "Source", uid="source", native_output_names=["out"]
    )
    workflow.nodes["target"] = VibeNode(
        "target",
        "Target",
        uid="target",
        inputs={"value": None},
        native_input_names=["value"],
    )
    workflow.virtual_wires = _normalize_virtual_wires(
        {
            "bus": {
                "legs": [
                    {
                        "scope_path": "",
                        "leg_index": 0,
                        "occurrence_index": 0,
                        "from_node": "source",
                        "from_output": "out",
                        "to_node": "target",
                        "to_input": "value",
                    }
                ]
            }
        }
    )

    bundle = load_bundle(workflow)
    assert bundle.workflow.compile("api")["target"]["inputs"]["value"] == [
        "source",
        0,
    ]
    ui = bundle.materialize_ui()
    assert [1, 1, 0, 2, 0, ""] in ui["links"]


def test_shared_virtual_wire_resolver_preserves_nested_occurrences() -> None:
    from vibecomfy.workflow import _resolve_virtual_wire_legs

    scope = "definition:inner"
    nodes = {
        "source": {
            "id": 10,
            "properties": {"vibecomfy_uid": "source"},
            "outputs": [{"name": "out"}],
        },
        "target": {
            "id": 20,
            "properties": {"vibecomfy_uid": "target"},
            "inputs": [{"name": None}, {"name": "value"}],
        },
    }
    resolved = _resolve_virtual_wire_legs(
        nodes,
        {
            "bus": {
                "scope_path": scope,
                "legs": [
                    {
                        "scope_path": scope,
                        "leg_index": 0,
                        "occurrence_index": 0,
                        "from_node": "source",
                        "from_output": "out",
                        "to_node": "target",
                        "to_input": "value",
                    },
                    {
                        "scope_path": scope,
                        "leg_index": 0,
                        "occurrence_index": 1,
                        "from_node": "source",
                        "from_output": 0,
                        "to_node": "target",
                        "to_input": 1,
                    },
                ],
            }
        },
        scope_path=scope,
    )
    assert [(item.leg_index, item.occurrence_index) for item in resolved] == [(0, 0), (0, 1)]
    assert all(item.scope_path == scope for item in resolved)
    assert all(item.from_node == f"{scope}#source" for item in resolved)
    assert all(item.to_node == f"{scope}#target" for item in resolved)


def test_shared_virtual_wire_resolver_rejects_noncanonical_occurrence_aliases() -> None:
    from vibecomfy.workflow import WorkflowCompileError, _resolve_virtual_wire_legs

    nodes = {
        "a": {"id": 1, "uid": "a", "outputs": [{"name": "out"}, {"name": "other"}]},
        "b": {"id": 2, "uid": "b", "inputs": [{"name": "value"}]},
    }
    with pytest.raises(WorkflowCompileError, match="exactly the canonical fields"):
        _resolve_virtual_wire_legs(
            nodes,
            {
                "bus": {
                    "legs": [
                        {
                            "scope_path": "",
                            "leg_index": 0,
                            "occurrence_index": 0,
                            "from_uid": "a",
                            "from_port": 0,
                            "origin_slot": "other",
                            "to_uid": "b",
                            "to_port": 0,
                        }
                    ]
                }
            },
        )


def test_bundle_ui_materialization_rejects_empty_virtual_wire_through_shared_resolver() -> None:
    """Bundle/UI materialization must not silently drop an empty wire record."""
    workflow = _connected_workflow()
    workflow.virtual_wires = {"empty": {"legs": []}}

    with pytest.raises(WorkflowBundleError, match="at least one leg"):
        materialize_ui_json(workflow)


@pytest.mark.parametrize(
    "wire",
    [
        {
            "scope_path": None,
            "legs": [{
                "scope_path": "",
                "leg_index": 0,
                "occurrence_index": 0,
                "from_node": "source",
                "from_output": "out",
                "to_node": "target",
                "to_input": "in",
            }],
        },
        {
            "legs": [{
                "scope_path": None,
                "leg_index": 0,
                "occurrence_index": 0,
                "from_node": "source",
                "from_output": "out",
                "to_node": "target",
                "to_input": "in",
            }],
        },
    ],
    ids=("wire-scope-none", "leg-scope-none"),
)
def test_virtual_wire_scope_none_is_rejected_by_execution_and_ui_resolvers(wire) -> None:
    """Explicit null scope is malformed, not an omitted root scope."""
    workflow = _connected_workflow()
    workflow.virtual_wires = {"wire": wire}

    with pytest.raises(WorkflowCompileError) as compile_exc:
        workflow.compile()
    assert getattr(compile_exc.value, "code", None) == "virtual_wire_malformed"

    with pytest.raises(WorkflowBundleError, match="scope_path"):
        materialize_ui_json(workflow)


def test_nonempty_canonical_virtual_wire_reaches_execution_and_ui_materialization() -> None:
    """A valid fully indexed leg is shared by execution and UI projection."""
    workflow = _workflow("canonical-virtual-wire-direct")
    workflow.nodes["1"] = VibeNode(
        "1", "Source", uid="source", native_output_names=["out"]
    )
    workflow.nodes["2"] = VibeNode(
        "2", "Target", uid="target", inputs={"value": None},
        native_input_names=["value"],
    )
    workflow.virtual_wires = {
        "wire": {
            "scope_path": "",
            "legs": [{
                "scope_path": "",
                "leg_index": 0,
                "occurrence_index": 0,
                "from_node": "source",
                "from_output": "out",
                "to_node": "target",
                "to_input": "value",
            }],
        }
    }

    compiled = workflow.compile()
    assert compiled["2"]["inputs"]["value"] == ["1", 0]
    ui = materialize_ui_json(workflow)
    assert ui["links"]


@pytest.mark.parametrize(
    ("from_node", "from_output", "message"),
    [
        ("ghost", 0, "endpoint is not local"),
        ("source", "missing", "cannot derive from port"),
    ],
)
def test_normalized_virtual_wire_legs_reject_malformed_materialization(
    from_node: str,
    from_output: str | int,
    message: str,
) -> None:
    from vibecomfy.ingest.normalize import _normalize_virtual_wires

    workflow = _workflow("malformed-canonical-virtual-wire")
    workflow.nodes["source"] = VibeNode(
        "source", "Source", uid="source", native_output_names=["out"]
    )
    workflow.nodes["target"] = VibeNode(
        "target",
        "Target",
        uid="target",
        inputs={"value": None},
        native_input_names=["value"],
    )
    workflow.virtual_wires = _normalize_virtual_wires(
        {
            "bus": {
                "legs": [
                    {
                        "scope_path": "",
                        "leg_index": 0,
                        "occurrence_index": 0,
                        "from_node": from_node,
                        "from_output": from_output,
                        "to_node": "target",
                        "to_input": "value",
                    }
                ]
            }
        }
    )

    bundle = load_bundle(workflow)
    with pytest.raises(WorkflowBundleError, match=message):
        bundle.materialize_ui()


def test_public_imports_are_cold_process_safe() -> None:
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = str(repo)
    for module in ("workflow_bundle", "runtime"):
        result = subprocess.run(
            [sys.executable, "-c", f"import vibecomfy.{module}; print('IMPORT_OK')"],
            cwd=repo, env=env, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "IMPORT_OK"
        assert result.stderr == ""
