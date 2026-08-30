from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.check_strict_ready_templates as gate


def test_strict_ready_gate_report_is_repo_only_and_deterministic() -> None:
    first = gate.build_strict_ready_report()
    second = gate.build_strict_ready_report()

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["version"] == 1
    assert first["template_count"] >= first["target_count"] > 0
    assert all(target["source_scope"] == "repo" for target in first["targets"])
    assert all(target["indexed"] is True for target in first["targets"])
    assert all(target["source_scope"] != "dynamic" for target in first["targets"])
    assert first["diagnostics"] == sorted(
        first["diagnostics"],
        key=lambda item: (item["ready_id"], item["category"], item["code"], item["target"]),
    )


def test_strict_ready_gate_aggregates_every_diagnostic_category_into_truth(monkeypatch, capsys) -> None:
    """An enforced error from any target category must fail the report gate."""
    categories = (
        "static_contract_drift",
        "strict_ready",
        "generated_template_style",
        "pack_validation",
        "pack_provenance",
        "legacy_vocabulary",
        "v26_shape",
    )
    target = {
        "ready_id": "image/example",
        "static_drift": [],
        "strict_ready_diagnostics": [],
        "style_diagnostics": [],
        "pack_validation_diagnostics": [],
        "pack_provenance_diagnostics": [],
        "legacy_vocabulary_diagnostics": [],
        "v26_shape_diagnostics": [],
    }
    for category in categories:
        diagnostic = gate._diagnostic(
            code=f"{category}_error",
            message="enforced failure",
            ready_id="image/example",
            target="ready_templates/image/example.py:1",
            severity="error",
            category=category,
            enforced=True,
        )
        field = {
            "static_contract_drift": "static_drift",
            "strict_ready": "strict_ready_diagnostics",
            "generated_template_style": "style_diagnostics",
            "pack_validation": "pack_validation_diagnostics",
            "pack_provenance": "pack_provenance_diagnostics",
            "legacy_vocabulary": "legacy_vocabulary_diagnostics",
            "v26_shape": "v26_shape_diagnostics",
        }[category]
        target[field] = [diagnostic]

        monkeypatch.setattr(gate, "build_template_index", lambda: {"templates": [{
            "id": "image/example",
            "path": "ready_templates/image/example.py",
            "source_scope": "repo",
            "indexed": True,
        }]})
        monkeypatch.setattr(gate, "build_readability_inventory", lambda: SimpleNamespace(entries=[]))
        monkeypatch.setattr(gate, "_check_template", lambda *_args, **_kwargs: target)
        report = gate.build_strict_ready_report()

        assert report["ok"] is False
        assert report["summary"]["enforced_errors"] == 1
        assert [item["category"] for item in report["diagnostics"]] == [category]
        assert gate.main(["--json"]) == 1
        assert json.loads(capsys.readouterr().out)["ok"] is False

        target[field] = []


def test_static_drift_diagnostics_report_public_contract_mismatch(monkeypatch) -> None:
    class _Contract:
        def to_dict(self) -> dict[str, object]:
            return {
                "public_inputs": [{"name": "prompt", "node_id": "2", "field": "text"}],
                "public_outputs": [],
            }

    monkeypatch.setattr(gate, "_workflow_from_repo_template", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(gate, "build_contract", lambda _workflow: _Contract())
    diagnostics = gate._static_drift_diagnostics(
        {
            "id": "image/example",
            "path": "ready_templates/image/example.py",
            "public_inputs": [{"name": "prompt", "node_id": "1", "field": "text"}],
            "public_outputs": [],
        },
        ready_id="image/example",
        enforced=True,
    )

    assert [item["code"] for item in diagnostics] == [
        "static_contract_inputs_only_built",
        "static_contract_inputs_only_static",
    ]
    assert all(item["severity"] == "error" and item["enforced"] is True for item in diagnostics)


def test_generated_style_diagnostics_are_warnings_until_protected() -> None:
    entry = SimpleNamespace(
        marker="generated",
        counts=SimpleNamespace(
            positional_outs=1,
            widget_n_fields=0,
            uuid_class_types=0,
            n_uuid_variables=0,
            local_node_copies=0,
            missing_output_contract=True,
        ),
    )

    diagnostics = gate._style_diagnostics(
        entry,
        ready_id="image/generated",
        path="ready_templates/image/generated.py",
        enforced=False,
    )

    assert [item["code"] for item in diagnostics] == [
        "generated_template_positional_out",
        "generated_template_missing_output_contract",
    ]
    assert all(item["severity"] == "warning" and item["enforced"] is False for item in diagnostics)


def test_manual_legacy_v26_shape_diagnostics_are_not_blocking_when_unprotected(tmp_path: Path) -> None:
    template = tmp_path / "manual.py"
    template.write_text(
        """
# vibecomfy: manual
from vibecomfy.registry.ready_template import bind_input

def _at(wf, node_id, field):
    return wf.nodes[node_id].inputs[field]

def build():
    bind_input(None, 'prompt', '1', 'text')
""".lstrip(),
        encoding="utf-8",
    )

    diagnostics = gate._v26_shape_diagnostics(
        ready_id="image/manual",
        path=template,
        relative_path="ready_templates/image/manual.py",
        enforced=False,
    )

    assert any(item["code"] == "v26_legacy_ready_template_call" for item in diagnostics)
    assert all(item["severity"] == "warning" and item["enforced"] is False for item in diagnostics)


def test_v26_shape_accepts_canonical_flat_new_workflow_assignment(tmp_path: Path) -> None:
    template = tmp_path / "flat.py"
    template.write_text(
        """
from vibecomfy.templates import ReadyMetadata, new_workflow

READY_METADATA = ReadyMetadata.build(capability='image')

def build():
    wf = new_workflow(READY_METADATA, source_path=__file__)
    return wf.finalize({})
""".lstrip(),
        encoding="utf-8",
    )

    diagnostics = gate._v26_shape_diagnostics(
        ready_id="image/flat",
        path=template,
        relative_path="ready_templates/image/flat.py",
        enforced=True,
    )

    assert not any(item["code"] == "v26_new_workflow_context_count" for item in diagnostics)


def test_legacy_vocabulary_diagnostic_flips_per_target_ok_false(monkeypatch) -> None:
    """Synthetic legacy import/call diagnostic causes per-target ok=false."""
    monkeypatch.setattr(
        gate,
        "_legacy_vocabulary_diagnostics",
        lambda **_kwargs: [
            gate._diagnostic(
                code="legacy_vocabulary_import",
                message="Generated template imports legacy module 'vibecomfy.registry.ready_template'.",
                ready_id="image/example",
                target="ready_templates/image/example.py",
                severity="error",
                category="legacy_vocabulary",
                enforced=True,
                detail={"import": "vibecomfy.registry.ready_template", "line": 5},
            ),
        ],
    )

    target = gate._check_template(
        {
            "id": "image/example",
            "path": "ready_templates/image/example.py",
            "coverage_tier": "required",
            "app_active": True,
        },
        None,
    )

    assert target["ok"] is False
    assert len(target["legacy_vocabulary_diagnostics"]) == 1
    diag = target["legacy_vocabulary_diagnostics"][0]
    assert diag["code"] == "legacy_vocabulary_import"
    assert diag["severity"] == "error"
    assert diag["enforced"] is True
    assert diag["category"] == "legacy_vocabulary"


def test_legacy_vocabulary_call_flips_per_target_ok_false(monkeypatch) -> None:
    """Synthetic legacy call diagnostic causes per-target ok=false and exits nonzero."""
    monkeypatch.setattr(
        gate,
        "_legacy_vocabulary_diagnostics",
        lambda **_kwargs: [
            gate._diagnostic(
                code="legacy_vocabulary_call",
                message="Generated template calls legacy function 'bind_input'.",
                ready_id="video/legacy",
                target="ready_templates/video/legacy.py:42",
                severity="error",
                category="legacy_vocabulary",
                enforced=True,
                detail={"call": "bind_input", "line": 42},
            ),
        ],
    )

    target = gate._check_template(
        {
            "id": "video/legacy",
            "path": "ready_templates/video/legacy.py",
            "coverage_tier": "required",
            "app_active": True,
        },
        None,
    )

    assert target["ok"] is False
    assert len(target["legacy_vocabulary_diagnostics"]) == 1
    diag = target["legacy_vocabulary_diagnostics"][0]
    assert diag["code"] == "legacy_vocabulary_call"
    assert diag["severity"] == "error"
    assert diag["enforced"] is True
    assert diag["category"] == "legacy_vocabulary"


def test_legacy_vocabulary_main_exits_nonzero(monkeypatch, capsys) -> None:
    """Synthetic legacy diagnostic causes main() to exit nonzero and report ok=false."""
    monkeypatch.setattr(
        gate,
        "build_strict_ready_report",
        lambda: {
            "ok": False,
            "target_count": 1,
            "summary": {"diagnostics": 1, "enforced_errors": 1},
            "diagnostics": [
                {
                    "ready_id": "image/example",
                    "category": "legacy_vocabulary",
                    "code": "legacy_vocabulary_call",
                    "target": "ready_templates/image/example.py:42",
                    "severity": "error",
                    "enforced": True,
                    "message": "Generated template calls legacy function 'bind_input'.",
                }
            ],
        },
    )

    assert gate.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["summary"]["enforced_errors"] == 1


def test_strict_ready_gate_main_exits_nonzero_for_enforced_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        gate,
        "build_strict_ready_report",
        lambda: {
            "ok": False,
            "target_count": 1,
            "summary": {"diagnostics": 1},
            "diagnostics": [
                {
                    "ready_id": "image/example",
                    "category": "strict_ready",
                    "code": "strict_ready_missing_public_input",
                    "target": "public_inputs",
                    "severity": "error",
                    "enforced": True,
                    "message": "missing input",
                }
            ],
        },
    )

    assert gate.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_v26_shape_rejects_derivable_source_workflow_and_provenance(tmp_path: Path) -> None:
    template = tmp_path / "example.py"
    template.write_text(
        """
from vibecomfy.templates import ReadyMetadata, new_workflow

PUBLIC_INPUTS = {}
MODELS = {}
READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    source_workflow='ready_templates/sources/official/image/example.json',
    provenance={'source_workflow': 'ready_templates/sources/official/image/example.json'},
)

def build():
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
        return wf.finalize(PUBLIC_INPUTS)
""".lstrip(),
        encoding="utf-8",
    )

    diagnostics = gate._v26_shape_diagnostics(
        ready_id="image/example",
        path=template,
        relative_path="ready_templates/image/example.py",
        enforced=True,
    )

    codes = {item["code"] for item in diagnostics}
    assert codes == {"v26_derivable_metadata_field"}
    messages = {item["message"] for item in diagnostics}
    assert "ReadyMetadata.build emits derivable field 'source_workflow'." in messages
    assert "ReadyMetadata.build emits derivable field 'provenance'." in messages
    assert all(item["severity"] == "error" and item["enforced"] is True for item in diagnostics)


def _load_ready_template(relative_path: str):
    path = Path(__file__).parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(f"test_ready_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_core_get_image_size_is_not_attributed_to_kjnodes() -> None:
    from vibecomfy.node_packs import clear_known_node_packs_cache, get_known_node_packs, read_lockfile

    clear_known_node_packs_cache()
    try:
        kj_entry = next(entry for entry in read_lockfile(Path(__file__).parents[1] / "custom_nodes.lock") if entry.name == "ComfyUI-KJNodes")
        assert "GetImageSize" not in kj_entry.class_set
        kj_pack = next(pack for pack in get_known_node_packs() if pack.name == "ComfyUI-KJNodes")
        assert "GetImageSize" not in kj_pack.classes
    finally:
        clear_known_node_packs_cache()


def test_repaired_templates_omit_schema_defaults_but_keep_editable_inputs() -> None:
    cases = (
        (
            "ready_templates/video/ltx2_3_lightricks_iclora_hdr.py",
            "fps",
            "5108",
            30,
        ),
        ("ready_templates/video/wan_t2v.py", "height", "40", 480),
    )
    for relative_path, input_name, node_id, default in cases:
        module = _load_ready_template(relative_path)
        workflow = module.build()
        api = workflow.compile("api")
        assert input_name not in api[node_id]["inputs"]
        assert module.PUBLIC_INPUT_METADATA[input_name].default == default
        diagnostics = gate._v26_shape_diagnostics(
            ready_id=relative_path,
            path=Path(__file__).parents[1] / relative_path,
            relative_path=relative_path,
            enforced=True,
        )
        assert not any(
            item["code"] == "v26_schema_default_kwarg" for item in diagnostics
        )

        workflow.set_input(input_name, default)
        explicit_default_api = workflow.compile("api")
        expected_inputs = dict(api[node_id]["inputs"])
        expected_inputs[input_name] = default
        assert explicit_default_api[node_id]["inputs"] == expected_inputs

        workflow.set_input(input_name, default + 1)
        assert workflow.compile("api")[node_id]["inputs"][input_name] == default + 1


def test_schema_default_omission_survives_envelope_round_trip() -> None:
    module = _load_ready_template("ready_templates/video/wan_t2v.py")
    workflow = module.build()
    assert workflow.inputs["height"].allow_missing_target is True

    restored = workflow.from_envelope(workflow.to_envelope())

    assert restored.inputs["height"].allow_missing_target is True
    restored.set_input("height", 480)
    assert restored.compile("api")["40"]["inputs"]["height"] == 480


def test_allow_missing_target_requires_a_schema_default() -> None:
    from vibecomfy.porting.strict_ready import validate_strict_ready_workflow
    from vibecomfy.workflow import VibeInput, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource

    workflow = VibeWorkflow("image/strict", WorkflowSource("image/strict"))
    workflow.nodes["1"] = VibeNode("1", "KSampler", inputs={"seed": 1})
    workflow.outputs.append(VibeOutput("1", "IMAGE", name="image"))

    with pytest.raises(ValueError, match="may only be omitted"):
        workflow.register_input("bogus", "1", "typo", 0, allow_missing_target=True)

    workflow.inputs["bogus"] = VibeInput(
        name="bogus", node_id="1", field="typo", value=0, allow_missing_target=True
    )
    assert any(
        issue.code == "strict_ready_broken_public_input"
        for issue in validate_strict_ready_workflow(workflow)
    )
    with pytest.raises(ValueError, match="target field 'typo' is missing"):
        workflow.set_input("bogus", 1)


def test_template_index_preserves_manual_source_workflow() -> None:
    from tools.refresh_template_index import build_template_index

    index = build_template_index(generated_at="2026-01-01T00:00:00+00:00")
    rows = {item["id"]: item for item in index["templates"]}
    assert rows["video/ltx2_3_first_last_frame_travel_iclora_control"]["source_workflow"] == "manual"
    assert rows["video/ltx2_3_lightricks_iclora_hdr"]["source_workflow"].endswith(
        "LTX-2.3_ICLoRA_HDR_Distilled.json"
    )
    assert rows["video/wan_t2v"]["source_workflow"] == "ready_templates/sources/official/video/wan_t2v.json"


def test_source_workflow_resolver_covers_metadata_aliases() -> None:
    from vibecomfy.porting._provenance_utils import resolve_source_workflow

    cases = (
        ({"source_workflow": "top-level.json"}, "top-level.json"),
        ({"provenance": {"source_workflow": "nested.json"}}, "nested.json"),
        ({"provenance": {"source_workflow_path": "nested-path.json"}}, "nested-path.json"),
        ({"provenance": {"source_path": "nested-source.json"}}, "nested-source.json"),
    )
    for metadata, expected in cases:
        assert resolve_source_workflow(metadata) == expected


def test_first_last_template_does_not_add_manual_provenance() -> None:
    relative_path = "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py"
    source = (Path(__file__).parents[1] / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    metadata_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "build"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ReadyMetadata"
    ]
    assert len(metadata_calls) == 1
    assert not any(keyword.arg == "provenance" for keyword in metadata_calls[0].keywords)
