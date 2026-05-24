from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import vibecomfy.commands.validate as validate_cmd
from vibecomfy.commands.contract import _cmd_contract_doctor, _cmd_contract_inspect
from vibecomfy.commands.doctor import _doctor_warnings
from vibecomfy.commands.inspect import _cmd_inspect
from vibecomfy.commands.workflows import _cmd_workflows_contract_validate
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


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
    workflow.nodes["1"] = VibeNode("1", "UnknownRuntimeOnlyNode")
    return workflow
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        validate_cmd,
        "get_schema_provider",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("schema provider should not be built")),
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


def test_doctor_suggests_custom_node_pack_for_unknown_class(
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

    from vibecomfy.commands.doctor import _cmd_doctor

    # B5 lockfile drift verification is default-on per Step 16; this test predates B5 and isolates from the seam to keep its existing assertions stable.
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad))) == 1

    captured = capsys.readouterr()
    assert "Suggested custom node packs:" in captured.out
    assert "comfyui_controlnet_aux" in captured.out
    assert "vibecomfy port check" in captured.out


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

    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    assert _cmd_doctor(argparse.Namespace(path=str(scratchpad), json=False, lint=False, allow_drift=False)) == 1

    captured = capsys.readouterr()
    assert "Porting helper diagnostics" in captured.out
    assert f"vibecomfy port check {scratchpad} --json" in captured.out


def test_inspect_json_exposes_canonical_public_contract_fields(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(argparse.Namespace(workflow="image/z_image", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["contract_shape"] == payload["contract"]["contract_shape"]
    assert payload["public_inputs"] == payload["contract"]["public_inputs"]
    assert payload["public_outputs"] == payload["contract"]["public_outputs"]
    assert payload["graph_contract"] == payload["contract"]["graph_contract"]
    assert isinstance(payload["inputs"], list)
    assert isinstance(payload["outputs"], list)


def test_inspect_text_exposes_public_contract_counts(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_inspect(argparse.Namespace(workflow="image/z_image", json=False))

    output = capsys.readouterr().out
    assert code == 0
    assert "public inputs:" in output
    assert "public outputs:" in output
    assert "readiness: ready" in output


def test_doctor_json_embeds_canonical_public_contract_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from vibecomfy.commands.doctor import _cmd_doctor

    scratchpad = tmp_path / "doctor_contract.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

def build():
    workflow = VibeWorkflow(id="doctor-contract", source=WorkflowSource(id="doctor-contract"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="SaveImage", inputs={"filename_prefix": "out/test"})
    workflow.finalize_metadata()
    return workflow
""",
        encoding="utf-8",
    )

    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    code = _cmd_doctor(argparse.Namespace(path=str(scratchpad), json=True, lint=False, allow_drift=False))

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


@pytest.mark.xfail(strict=True, reason="Phase 1: LTX parity contract validate fails due to missing inputs in regen'd template; LTX family fix required")
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


@pytest.mark.xfail(strict=True, reason="Phase 1: LTX parity contract validate fails due to missing inputs in regen'd template; LTX family fix required")
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


def test_workflows_contract_validate_failure_diagnostic(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A broken workflow produces a stable, readable failure diagnostic."""
    # Build a deliberately broken workflow: missing named inputs, wrong conditioning, etc.
    scratchpad = tmp_path / "broken_ltx.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def build():
    wf = VibeWorkflow("broken-ltx", WorkflowSource("broken-ltx"))
    # Only add a SaveVideo output with no conditioning pipeline
    wf.node("SaveVideo", filename_prefix="broken")
    wf.node("LoadImage", image="broken.png")
    wf.finalize_metadata()
    return wf
""",
        encoding="utf-8",
    )

    code = _cmd_workflows_contract_validate(
        argparse.Namespace(
            template_or_path=str(scratchpad),
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
            template_or_path=str(scratchpad),
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
