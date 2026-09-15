"""T05 conversion preserves authored semantics and write behavior."""

from __future__ import annotations

import copy
from contextlib import contextmanager

import pytest

import vibecomfy.porting.convert as convert_module

from vibecomfy.porting.convert import (
    ManualTemplateRefusal,
    PortConvertResult,
    PortConvertValidation,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _wf(wf_id: str = "test-cvw") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


def _regular_node(
    node_id: str,
    class_type: str = "KSampler",
    *,
    pos=None,
    size=None,
) -> VibeNode:
    n = VibeNode(node_id, class_type, pos=pos, size=size)
    n.uid = node_id
    return n


def test_port_convert_binds_one_object_info_snapshot_for_the_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[list[str]] = []
    active = False

    @contextmanager
    def capture(class_types):
        nonlocal active
        captured.append(sorted(class_types))
        active = True
        try:
            yield
        finally:
            active = False

    original_emit = convert_module.emit_scratchpad_python

    def checked_emit(*args, **kwargs):
        assert active is True
        return original_emit(*args, **kwargs)

    monkeypatch.setattr(convert_module, "class_entry_snapshot", capture)
    monkeypatch.setattr(convert_module, "emit_scratchpad_python", checked_emit)
    wf = _wf("snapshot-bound")
    wf.nodes["1"] = _regular_node("1", "SaveImage")
    wf.definitions = {
        "subgraphs": [{
            "name": "Inner",
            "nodes": [{
                "id": "recursive",
                "uid": "recursive",
                "type": "RecursiveOnly",
                "inputs": {},
            }],
            "links": [],
        }]
    }

    result = port_convert_workflow(wf, validate=False)

    assert result.text
    assert captured == [["RecursiveOnly", "SaveImage"]]
    assert active is False


def test_port_convert_ready_template_emits_structured_custom_node_refs():
    wf = _wf("structured-refs")
    wf.nodes["1"] = _regular_node("1", "ExampleCustomNode")
    wf.metadata["requirements"] = {
        "custom_nodes": ["ExamplePack"],
        "custom_node_refs": [
            {
                "slug": "ExamplePack",
                "source": "git",
                "url": "https://example.test/ExamplePack.git",
                "commit": "abc123",
            }
        ],
    }

    result = port_convert_workflow(wf, ready_id="test/structured_refs", validate=False)

    assert "custom_node_refs" in result.text
    assert "ExamplePack" in result.text
    assert "abc123" in result.text


def test_ready_requirements_do_not_keep_edited_model_value_stale() -> None:
    wf = _wf("edited-model")
    wf.nodes["1"] = _regular_node("1", "CheckpointLoaderSimple")
    wf.nodes["1"].inputs["ckpt_name"] = "new-model.safetensors"
    wf.metadata["model_assets"] = [{"name": "old-model.safetensors", "url": "https://example.test/old"}]
    wf.requirements.models = ["new-model.safetensors"]

    requirements = convert_module._ready_requirements(wf)

    assert requirements["models"] == ["new-model.safetensors"]


def test_ready_requirements_refreshes_mixed_models_without_stale_assets() -> None:
    wf = _wf("mixed-models")
    wf.nodes["1"] = _regular_node("1", "CheckpointLoaderSimple")
    wf.nodes["1"].inputs["ckpt_name"] = "new.safetensors"
    wf.nodes["2"] = _regular_node("2", "LoraLoader")
    wf.nodes["2"].inputs["lora_name"] = "kept.safetensors"
    wf.metadata["model_assets"] = [
        {"name": "kept.safetensors", "url": "https://example.test/kept", "subdir": "loras"},
        {"name": "stale.safetensors", "url": "https://example.test/stale"},
    ]

    requirements = convert_module._ready_requirements(wf)

    assert requirements["models"] == ["new.safetensors", {
        "name": "kept.safetensors", "url": "https://example.test/kept", "subdir": "loras",
    }]


def test_ready_requirements_collapses_duplicate_inferred_picker_names() -> None:
    wf = _wf("shared-picker-model")
    for node_id in ("1", "2"):
        wf.nodes[node_id] = _regular_node(node_id, "CheckpointLoaderSimple")
        wf.nodes[node_id].inputs["ckpt_name"] = "shared.safetensors"

    assert convert_module._ready_requirements(wf)["models"] == ["shared.safetensors"]


def test_ready_requirements_preserves_authored_duplicates_and_adds_new_names_once() -> None:
    wf = _wf("authored-duplicate-model")
    wf.nodes["1"] = _regular_node("1", "CheckpointLoaderSimple")
    wf.nodes["1"].inputs["ckpt_name"] = "shared.safetensors"
    wf.nodes["2"] = _regular_node("2", "CheckpointLoaderSimple")
    wf.nodes["2"].inputs["ckpt_name"] = "new.safetensors"
    wf.requirements.models = ["shared.safetensors", "shared.safetensors"]

    assert convert_module._ready_requirements(wf)["models"] == [
        "shared.safetensors", "shared.safetensors", "new.safetensors",
    ]


def test_ready_requirements_refreshes_one_of_two_shared_loaders() -> None:
    wf = _wf("edited-shared-picker-model")
    for node_id, value in (("1", "old.safetensors"), ("2", "new.safetensors")):
        wf.nodes[node_id] = _regular_node(node_id, "CheckpointLoaderSimple")
        wf.nodes[node_id].inputs["ckpt_name"] = value
    wf.requirements.models = ["old.safetensors"]

    assert convert_module._ready_requirements(wf)["models"] == [
        "old.safetensors", "new.safetensors",
    ]


def test_ready_requirements_keeps_no_picker_fallback() -> None:
    wf = _wf("no-picker-fallback")
    wf.requirements.models = ["authored.safetensors"]

    assert convert_module._ready_requirements(wf)["models"] == ["authored.safetensors"]


def test_scratchpad_pair_uses_picker_model_requirements_for_v2_rebuild(
    tmp_path,
) -> None:
    """The preflight and external-companion rebuild must share one witness."""
    wf = _wf("model-requirement-pair")
    wf.nodes["1"] = _regular_node("1", "CheckpointLoaderSimple")
    wf.nodes["1"].inputs["ckpt_name"] = "repeated.safetensors"
    wf.nodes["2"] = _regular_node("2", "CheckpointLoaderSimple")
    wf.nodes["2"].inputs["ckpt_name"] = "repeated.safetensors"
    wf.nodes["3"] = _regular_node("3", "CheckpointLoaderSimple")
    wf.nodes["3"].inputs["ckpt_name"] = "second.safetensors"
    wf.metadata["model_assets"] = [
        {"name": "repeated.safetensors", "url": "https://example.test/repeated", "subdir": "checkpoints"},
        {"name": "second.safetensors", "url": "https://example.test/second", "subdir": "checkpoints"},
    ]
    # This is the stale source witness that previously made the external v2
    # rebuild fail its staged semantic-digest check.
    wf.requirements.models = ["repeated.safetensors"]
    before = wf.copy()

    result = port_convert_workflow(wf, validate=False)
    assert wf == before
    assert "canonical_requirements" not in result.text

    from vibecomfy.porting.convert import _build_emitted_workflow_from_text
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import emit_bundle_with_candidate, load_bundle

    staged = _build_emitted_workflow_from_text(result.text)
    destination = tmp_path / "model-requirement-pair.py"
    emit_bundle_with_candidate(staged, destination, {"operation": "authored"}, None)
    reloaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED).workflow
    assert reloaded.requirements.models == [
        {"name": "repeated.safetensors", "url": "https://example.test/repeated", "subdir": "checkpoints"},
        {"name": "second.safetensors", "url": "https://example.test/second", "subdir": "checkpoints"},
    ]


def test_scratchpad_pair_preserves_explicit_empty_model_requirements(tmp_path) -> None:
    wf = _wf("empty-model-requirements")
    wf.nodes["1"] = _regular_node("1", "CheckpointLoaderSimple")
    wf.nodes["1"].inputs["ckpt_name"] = "picker.safetensors"
    wf.requirements.models = []

    result = port_convert_workflow(wf, validate=False)
    assert "canonical_requirements" not in result.text

    from vibecomfy.porting.convert import _build_emitted_workflow_from_text
    from vibecomfy.security.provenance import Provenance
    from vibecomfy.workflow_bundle import emit_bundle_with_candidate, load_bundle

    staged = _build_emitted_workflow_from_text(result.text)
    destination = tmp_path / "empty-model-requirements.py"
    emit_bundle_with_candidate(staged, destination, {"operation": "authored"}, None)
    reloaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED).workflow
    assert reloaded.requirements.models == []


def test_port_convert_does_not_mutate_caller_owned_workflow_or_raw_evidence():
    wf = _wf("caller-owned")
    wf.nodes["1"] = VibeNode("1", "PrimitiveInt", inputs={"value": 7})
    wf.nodes["2"] = VibeNode("2", "Sink")
    wf.edges = [VibeEdge("1", "0", "2", "value")]
    raw = {
        "definitions": {
            "subgraphs": [
                {
                    "nodes": [
                        {"id": "10", "type": "PrimitiveInt", "widgets_values": [3]}
                    ],
                    "links": [],
                }
            ]
        }
    }
    workflow_before = wf.copy()
    raw_before = copy.deepcopy(raw)

    result = port_convert_workflow(wf, raw_workflow=raw, validate=False)

    assert "value=7" in result.text
    assert wf == workflow_before
    assert raw == raw_before


def test_open_draft_conversion_keeps_authored_graph_when_projection_is_unresolved(
    tmp_path,
) -> None:
    """A refused execution projection still has a parseable Python draft."""
    wf = _wf("unresolved-draft")
    bypass = _regular_node("bypass", "Filter")
    bypass.mode = "bypassed"
    bypass.native_output_names = ["image"]
    bypass.native_output_types = ["IMAGE"]
    bypass.metadata["output_types"] = ["IMAGE"]
    sink = _regular_node("sink", "Sink")
    sink.native_input_names = ["image"]
    sink.native_input_types = ["IMAGE"]
    sink.native_input_optional = [False]
    sink.metadata["input_types"] = {"image": "IMAGE"}
    wf.nodes.update({"bypass": bypass, "sink": sink})
    wf.edges = [VibeEdge("bypass", "image", "sink", "image")]

    result = port_convert_workflow(
        wf,
        validate=True,
        preserve_authored_graph=True,
    )

    assert result.text
    assert result.validation is not None
    assert result.validation.ok is True
    assert result.validation.compile_ok is False
    assert "Filter" in result.text

    from vibecomfy.porting.convert import _build_emitted_workflow_from_text
    from vibecomfy.workflow_bundle import emit_bundle_with_candidate, load_bundle
    from vibecomfy.security.provenance import Provenance

    staged = _build_emitted_workflow_from_text(result.text)
    bundle = emit_bundle_with_candidate(
        staged,
        tmp_path / "unresolved-draft.py",
        {"operation": "captured", "artifact_class": "open_draft", "execution_ready": False},
        None,
        preserve_authored_graph=True,
    )
    assert bundle.provenance["artifact_class"] == "open_draft"
    assert bundle.provenance["execution_ready"] is False
    reloaded = load_bundle(tmp_path / "unresolved-draft.py", trust=Provenance.USER_CONFIRMED)
    assert set(reloaded.workflow.nodes) == set(staged.nodes)
    assert reloaded.workflow.edges == staged.edges
    assert {
        node_id: node.uid for node_id, node in reloaded.workflow.nodes.items()
    } == {node_id: node.uid for node_id, node in staged.nodes.items()}


def _passing_write_result(text: str) -> PortConvertResult:
    return PortConvertResult(
        mode="scratchpad",
        text=text,
        validation=PortConvertValidation(
            ok=True,
            import_ok=True,
            build_ok=True,
            compile_ok=True,
            parity_ok=True,
        ),
    )


def test_diff_mode_forces_dry_run_and_preserves_manual_target(tmp_path):
    target = tmp_path / "manual.py"
    original = "# vibecomfy: manual\nVALUE = 'existing'\n"
    emitted = "VALUE = 'preview only'\n"
    target.write_text(original, encoding="utf-8")

    payload = port_convert_and_write(
        _passing_write_result(emitted),
        target,
        dry_run=False,
        diff=True,
    )

    assert payload["written"] is False
    assert payload["dry_run"] is True
    assert payload["diff_requested"] is True
    assert payload["diff_forced_dry_run"] is True
    assert payload["target_exists"] is True
    assert payload["manual_refusal"]["refused"] is True
    assert payload["manual_refusal"]["marker"] == "# vibecomfy: manual"
    assert "Remove the marker" in payload["manual_refusal"]["message"]
    assert payload["diff"]["original_exists"] is True
    assert payload["diff"]["changed"] is True
    assert payload["diff"]["original_line_count"] == 2
    assert payload["diff"]["emitted_line_count"] == 1
    assert payload["diff"]["line_count_delta"] == -1
    assert payload["diff"]["unified_diff_line_count"] > 0
    assert "preview only" in payload["diff"]["unified_diff"]
    assert target.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".vibecomfy-port-*")) == []


def test_manual_template_real_write_refusal_preserves_target_bytes(tmp_path):
    target = tmp_path / "manual.py"
    original = "# vibecomfy: manual\nVALUE = 'keep'\n"
    target.write_text(original, encoding="utf-8")

    with pytest.raises(ManualTemplateRefusal):
        port_convert_and_write(
            _passing_write_result("VALUE = 'replace'\n"),
            target,
            dry_run=False,
            diff=False,
        )

    assert target.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".vibecomfy-port-*")) == []


def test_ready_conversion_canonicalizes_provenance_identity_and_preserves_upstream(tmp_path) -> None:
    wf = _wf("image/future")
    wf.nodes["1"] = _regular_node("1")
    wf.metadata["provenance"] = {
        "source_id": "upstream_future", "source_path": "source.json",
        "metadata_only": "metadata-preserved",
    }
    wf.source.provenance["source_only"] = "source-preserved"
    result = port_convert_workflow(
        wf,
        ready_id="image/future",
        provenance={
            "source_id": "upstream_future",
            "source_path": "source.json",
        },
        validate=False,
    )
    destination = tmp_path / "future.py"
    destination.write_text(result.text, encoding="utf-8")
    from vibecomfy.workflow_bundle import load_bundle
    from vibecomfy.workflow_bundle import Provenance

    loaded = load_bundle(destination, trust=Provenance.USER_CONFIRMED)
    assert loaded.workflow.id == "image/future"
    provenance = loaded.workflow.metadata["provenance"]
    assert provenance["source_id"] == "image/future"
    assert provenance["ready_id"] == "image/future"
    assert provenance["upstream_source_id"] == "upstream_future"
    assert provenance["source_path"] == "source.json"
    for retained in (provenance, loaded.workflow.source.provenance):
        assert retained["metadata_only"] == "metadata-preserved"
        assert retained["source_only"] == "source-preserved"
