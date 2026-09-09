from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

import pytest

import vibecomfy.commands.validate as validate_cmd
from vibecomfy.cli_loader import load_bundle
from vibecomfy.commands.contract import _cmd_contract_doctor, _cmd_contract_inspect
from vibecomfy.commands.doctor import _doctor_warnings
from vibecomfy.commands.inspect import _cmd_inspect
from vibecomfy.commands.nodes import _cmd_nodes_ensure
from vibecomfy.commands.workflows import _cmd_workflows_contract_validate
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.security.provenance import Provenance
from vibecomfy.workflow import VibeEdge, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource


class _InspectSchemaProvider:
    schemas = {
        "EmptyImage": NodeSchema(
            "EmptyImage", None,
            {
                "width": InputSpec("INT"), "height": InputSpec("INT"),
                "batch_size": InputSpec("INT"), "color": InputSpec("INT"),
            },
            [OutputSpec("IMAGE", "IMAGE")],
        ),
        "SaveImage": NodeSchema(
            "SaveImage", None,
            {"images": InputSpec("IMAGE"), "filename_prefix": InputSpec("STRING")},
            [],
        ),
    }

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schemas.get(class_type)


def _inspect_smoke_bundle() -> tuple[object, _InspectSchemaProvider]:
    provider = _InspectSchemaProvider()
    workflow = VibeWorkflow("inspect-smoke", WorkflowSource("inspect-smoke"))
    for node_id, class_type, inputs in (
        ("source", "EmptyImage", {"width": 8, "height": 8, "batch_size": 1, "color": 0}),
        ("save", "SaveImage", {"filename_prefix": "out/inspect"}),
    ):
        schema = provider.get_schema(class_type)
        assert schema is not None
        workflow.nodes[node_id] = VibeNode(
            node_id,
            class_type,
            uid=f"inspect-{node_id}",
            inputs=inputs,
            native_input_names=list(schema.inputs),
            native_input_types=[spec.type for spec in schema.inputs.values()],
            native_output_names=[spec.name for spec in schema.outputs],
            native_output_types=[spec.type for spec in schema.outputs],
        )
    workflow.edges.append(VibeEdge("source", "0", "save", "images"))
    workflow.outputs.append(VibeOutput("save", "SaveImage", name="image", artifact_kind="image"))
    workflow.finalize_metadata()
    return load_bundle(workflow), provider


def test_validate_no_schema_skips_schema_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratchpad = tmp_path / "workflow.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow("validate-no-schema", WorkflowSource("validate-no-schema"))
    workflow.nodes["1"] = VibeNode("1", "UnknownRuntimeOnlyNode", uid="validate-no-schema-1")
    return workflow
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_cmd,
        "get_schema_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("schema provider should not be built")),
    )
    real_load_bundle = validate_cmd.load_bundle
    monkeypatch.setattr(
        validate_cmd,
        "load_bundle",
        lambda path: real_load_bundle(path, trust=Provenance.USER_CONFIRMED),
    )

    assert validate_cmd._cmd_validate(argparse.Namespace(path=str(scratchpad), backend="api", no_schema=True)) == 0
    assert capsys.readouterr().out == "ok\n"


def test_doctor_warns_about_optional_video_audio_edge() -> None:
    workflow = VibeWorkflow("video", WorkflowSource("video"))
    workflow.nodes["1"] = VibeNode("1", "LTXVAudioVAEDecode")
    workflow.nodes["2"] = VibeNode("2", "CreateVideo")
    workflow.edges.append(VibeEdge("1", "0", "2", "audio"))

    warnings = _doctor_warnings(workflow)

    assert any("CreateVideo node 2 has optional audio input connected from 1:LTXVAudioVAEDecode" in item for item in warnings)


def test_doctor_warns_about_kj_ltx_audio_vae_loader() -> None:
    workflow = VibeWorkflow("audio-vae", WorkflowSource("audio-vae"))
    workflow.nodes["175"] = VibeNode(
        "175",
        "VAELoaderKJ",
        inputs={"vae_name": "LTX23_audio_vae_bf16.safetensors"},
    )

    warnings = _doctor_warnings(workflow)

    assert any("Use LTXVAudioVAELoader with the file staged under checkpoints" in item for item in warnings)


def test_nodes_ensure_suggests_custom_node_pack_for_unknown_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "SaveImage", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="DWPreprocessor")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert _cmd_nodes_ensure(
        argparse.Namespace(template=None, workflow=str(scratchpad), dry_run=True)
    ) == 0

    captured = capsys.readouterr()
    assert "Suggested custom node packs:" in captured.out
    assert "comfyui_controlnet_aux" in captured.out


def test_doctor_points_helper_diagnostics_to_port_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratchpad = tmp_path / "helper_issue.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

def build():
    workflow = VibeWorkflow(id="helper", source=WorkflowSource(id="helper"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="GetNode", inputs={"widget_0": "missing"})
    workflow.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"filename_prefix": "out/helper"})
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    from vibecomfy.commands.doctor import _cmd_doctor
    from vibecomfy.cli_loader import load_bundle
    from vibecomfy.workflow_bundle import WorkflowBundleError

    workflow = VibeWorkflow("helper", WorkflowSource("helper"))
    workflow.nodes["1"] = VibeNode(
        id="1", class_type="GetNode", uid="get-1", widgets={"widget_0": "missing"}
    )
    workflow.nodes["2"] = VibeNode(
        id="2", class_type="SaveImage", uid="save-2",
        inputs={"filename_prefix": "out/helper"},
    )
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    bundle = load_bundle(workflow)
    assert [issue.code for issue in workflow.helper_diagnostics()] == ["helper_broadcast_unresolved"]
    with pytest.raises(WorkflowBundleError, match="object-info identity"):
        bundle.compile()
    monkeypatch.setattr("vibecomfy.commands.doctor.load_bundle", lambda _path: bundle)
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad), json=False, lint=False, allow_drift=False)) == 1

    captured = capsys.readouterr()
    assert "Porting helper diagnostics" in captured.out
    assert f"vibecomfy port check {scratchpad} --json" in captured.out


@pytest.mark.parametrize(
    "payload",
    [
        {
            "workflow_id": "doctor-raw-api",
            "prompt": {"1": {"class_type": "Integer", "inputs": {"value": 7}}},
        },
        {
            "workflow_id": "doctor-raw-ui",
            "nodes": [{"id": 1, "type": "Integer", "widgets_values": [7]}],
            "links": [],
            "groups": [],
        },
    ],
)
def test_doctor_rejects_raw_import_evidence_before_helper_diagnosis(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    payload: dict,
) -> None:
    import vibecomfy.commands.doctor as doctor_cmd

    source = tmp_path / "raw.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert doctor_cmd._cmd_doctor(
        argparse.Namespace(path=str(source), json=False, lint=False, allow_drift=False)
    ) == 1
    output = capsys.readouterr().out
    assert "import evidence only" in output
    assert "vibecomfy port check" in output
    assert "vibecomfy port convert" in output


def test_inspect_json_exposes_canonical_public_contract_fields(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, provider = _inspect_smoke_bundle()
    monkeypatch.setattr("vibecomfy.commands.inspect.get_schema_provider", lambda _kind: provider)
    monkeypatch.setattr("vibecomfy.commands.inspect.load_bundle", lambda _ref, schema_provider: bundle)
    code = _cmd_inspect(argparse.Namespace(workflow="inspect-smoke", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["contract_shape"] == payload["contract"]["contract_shape"]
    assert payload["public_inputs"] == payload["contract"]["public_inputs"]
    assert payload["public_outputs"] == payload["contract"]["public_outputs"]
    assert payload["graph_contract"] == payload["contract"]["graph_contract"]
    assert isinstance(payload["inputs"], list)
    assert isinstance(payload["outputs"], list)


def test_inspect_text_exposes_public_contract_counts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, provider = _inspect_smoke_bundle()
    monkeypatch.setattr("vibecomfy.commands.inspect.get_schema_provider", lambda _kind: provider)
    monkeypatch.setattr("vibecomfy.commands.inspect.load_bundle", lambda _ref, schema_provider: bundle)
    code = _cmd_inspect(argparse.Namespace(workflow="inspect-smoke", json=False))

    output = capsys.readouterr().out
    assert code == 0
    assert "public inputs:" in output
    assert "public outputs:" in output
    assert "readiness:" in output
    assert "status: runnable" in output


def test_doctor_json_embeds_canonical_public_contract_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from vibecomfy.commands.doctor import _cmd_doctor

    bundle, provider = _inspect_smoke_bundle()
    monkeypatch.setattr("vibecomfy.commands.doctor.get_schema_provider", lambda _kind: provider)
    monkeypatch.setattr("vibecomfy.commands.doctor.load_bundle", lambda _ref: bundle)
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    code = _cmd_doctor(argparse.Namespace(path="inspect-smoke", json=True, lint=False, allow_drift=False))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["contract_shape"] == payload["contract"]["contract_shape"]
    assert payload["public_inputs"] == payload["contract"]["public_inputs"]
    assert payload["public_outputs"] == payload["contract"]["public_outputs"]
    assert payload["graph_contract"] == payload["contract"]["graph_contract"]


def test_contract_inspect_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_contract_inspect(argparse.Namespace(workflow="image/z_image", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["version"] == 1
    assert payload["workflow_id"] == "image/z_image"
    assert isinstance(payload["model_assets"], list)
    assert len(payload["model_assets"]) > 0
    assert isinstance(payload["inputs"], list)
    assert "model" in payload["inputs"]
    assert isinstance(payload["outputs"], list)
    assert payload["contract_shape"] == "workflow_runtime_contract.v1.public_descriptors.v2"
    assert isinstance(payload["public_inputs"], list)
    assert isinstance(payload["public_outputs"], list)
    assert isinstance(payload["graph_contract"], dict)
    assert isinstance(payload["runtime_nodes"], list)
    assert isinstance(payload["runtime_class_types"], list)
    assert payload["readiness_level"] == "ready"


def test_contract_text_exposes_public_contract_counts(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_contract_inspect(argparse.Namespace(workflow="image/z_image", json=False))

    output = capsys.readouterr().out
    assert code == 0
    assert "contract_shape: workflow_runtime_contract.v1.public_descriptors.v2" in output
    assert "public_inputs:" in output
    assert "public_outputs:" in output


def test_contract_doctor_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_contract_doctor(argparse.Namespace(workflow="image/z_image", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "status" in payload
    assert payload["status"] == "ok"
    assert isinstance(payload["contract"], dict)
    assert payload["contract"]["version"] == 1
    assert payload["contract"]["contract_shape"] == "workflow_runtime_contract.v1.public_descriptors.v2"
    assert isinstance(payload["contract"]["public_inputs"], list)
    assert isinstance(payload["contract"]["public_outputs"], list)
    assert isinstance(payload["diagnostics"], list)
    # No error diagnostics for a clean image/z_image
    error_diags = [d for d in payload["diagnostics"] if d["severity"] == "error"]
    assert error_diags == []


def test_workflows_contract_validate_success_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Successful LTX contract validation produces passing JSON output."""
    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="video/ltx2_3_lightricks_first_last_parity",
            type="ltx-first-last-two-stage",
            json=True,
            no_schema=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["passed"] is True
    assert payload["contract_name"] == "ltx-first-last-two-stage"
    assert isinstance(payload["issues"], list)
    # No errors or warnings for the clean parity template
    error_issues = [i for i in payload["issues"] if i["severity"] == "error"]
    assert error_issues == [], f"Unexpected error issues: {error_issues}"


def test_workflows_contract_validate_success_human(capsys: pytest.CaptureFixture[str]) -> None:
    """Successful LTX contract validation produces readable human output."""
    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="video/ltx2_3_lightricks_first_last_parity",
            type="ltx-first-last-two-stage",
            json=False,
            no_schema=False,
        )
    )

    captured = capsys.readouterr().out
    assert code == 0
    assert "ltx-first-last-two-stage" in captured
    assert "passed: True" in captured


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("wrong_guide_slot", "missing_last_strength_guide"),
        ("misbound_prompt", "wrong_prompt_binding"),
        ("missing_sigmas", "missing_sigmas"),
        ("ambiguous_sigmas", "ambiguous_sigmas"),
    ],
)
def test_ltx_contract_rejects_role_and_wiring_drift_on_canonical_graph(
    mutation: str,
    expected_code: str,
) -> None:
    from vibecomfy.cli_loader import load_bundle
    from vibecomfy.contracts.ltx_first_last import LTXFirstLastTwoStageContract

    workflow = load_bundle("video/ltx2_3_lightricks_first_last_parity").workflow.copy()
    if mutation == "wrong_guide_slot":
        chained = next(
            edge
            for edge in workflow.edges
            if edge.to_input == "latent"
            and workflow.nodes[edge.from_node].class_type == "LTXVAddGuide"
            and workflow.nodes[edge.to_node].class_type == "LTXVAddGuide"
        )
        assert chained.from_output == "2"
        chained.from_output = "1"
    elif mutation == "misbound_prompt":
        conditioning = next(node for node in workflow.nodes.values() if node.class_type == "LTXVConditioning")
        negative_edge = next(
            edge for edge in workflow.edges
            if edge.to_node == conditioning.id and edge.to_input == "negative"
        )
        workflow.inputs["prompt"].node_id = negative_edge.from_node
    elif mutation == "missing_sigmas":
        sigmas = next(node for node in workflow.nodes.values() if node.class_type == "ManualSigmas")
        del workflow.nodes[sigmas.id]
        workflow.edges[:] = [edge for edge in workflow.edges if edge.from_node != sigmas.id]
    else:
        sigmas = next(node for node in workflow.nodes.values() if node.class_type == "ManualSigmas")
        duplicate = deepcopy(sigmas)
        duplicate.id = "contract-ambiguous-sigmas"
        workflow.nodes[duplicate.id] = duplicate

    report = LTXFirstLastTwoStageContract(workflow).validate()
    assert report.passed is False
    assert expected_code in {issue.code for issue in report.issues}


def test_workflows_contract_validate_failure_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A broken workflow produces a stable, readable failure diagnostic."""
    workflow = VibeWorkflow("broken-ltx", WorkflowSource("broken-ltx"))
    workflow.nodes["save"] = VibeNode(
        "save", "SaveVideo", uid="broken-save", inputs={"filename_prefix": "broken"}
    )
    workflow.nodes["image"] = VibeNode(
        "image", "LoadImage", uid="broken-image", inputs={"image": "broken.png"}
    )
    workflow.finalize_metadata()
    bundle = load_bundle(workflow)
    monkeypatch.setattr("vibecomfy.cli_loader.load_bundle", lambda _ref: bundle)

    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="broken-ltx",
            type="ltx-first-last-two-stage",
            json=True,
            no_schema=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["passed"] is False
    assert payload["contract_name"] == "ltx-first-last-two-stage"
    issues = payload["issues"]
    assert len(issues) > 0, "Expected failure diagnostic issues"

    # Verify readable, stable issue codes
    codes = {i["code"] for i in issues}
    assert "missing_named_inputs" in codes
    assert "missing_first_strength_guide" in codes
    assert "missing_last_strength_guide" in codes

    # Verify issues have human-readable messages
    for issue in issues:
        assert isinstance(issue["code"], str) and issue["code"]
        assert isinstance(issue["message"], str) and issue["message"]
        assert issue["severity"] in ("error", "warning")

    # Human-readable version should also show the failure
    code2 = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="broken-ltx",
            type="ltx-first-last-two-stage",
            json=False,
            no_schema=False,
        )
    )
    captured2 = capsys.readouterr().out
    assert code2 == 1
    assert "passed: False" in captured2
    assert "missing_named_inputs" in captured2


def test_workflows_contract_validate_rejects_unknown_type(capsys: pytest.CaptureFixture[str]) -> None:
    """Unknown contract type returns exit code 1 with a clear error."""
    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path="video/ltx2_3_lightricks_first_last_parity",
            type="unknown-contract-type",
            json=False,
            no_schema=False,
        )
    )

    captured = capsys.readouterr().out
    assert code == 1
    assert "unknown contract type" in captured
    assert "ltx-first-last-two-stage" in captured
