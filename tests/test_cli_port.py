from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import vibecomfy.commands.port as port_commands
import vibecomfy.commands.port._convert as port_convert_module

import vibecomfy.commands.port._export as port_export_cmd
import vibecomfy.commands.port._simulate as port_simulate_cmd
from vibecomfy.cli import build_parser
from vibecomfy.commands.port import _cmd_port_check, _cmd_port_convert, _cmd_port_doctor_all, _cmd_port_export, _cmd_port_lint, _cmd_port_rules, _cmd_port_simulate, _cmd_port_validate_call, _cmd_port_widgets
from vibecomfy.porting import simulate

from tests._cli_helpers import (
    _load_emitted_provenance,
    _write_port_node_index,
    _write_port_workflow,
)


_BENIGN_STDERR_PREFIXES = (
    "Could not locate ComfyUI root",
    "Could not register VibeComfy agent routes",
    "vibecomfy agent routes module could not register",
    "Overriding a previously registered kernel",
    "operator: aten::mm",
    "registered at /Users/runner/work/pytorch/pytorch",
    "dispatch key: MPS",
    "previous kernel: registered at",
    "new kernel: registered at",
    "self.m.impl(",
)


def _stderr_is_benign(stderr: str) -> bool:
    """Return True when stderr only contains import-time warnings we don't own."""
    if not stderr:
        return True
    for line in stderr.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # torch warning header line starts with the torch/library.py path
        if stripped.startswith("/") and "torch/library.py" in stripped:
            continue
        if any(stripped.startswith(prefix) for prefix in _BENIGN_STDERR_PREFIXES):
            continue
        return False
    return True


def _comfy_available() -> bool:
    """True when the ComfyUI ``convert_ui_to_api`` oracle is importable.

    The refusal-spine driven export paths (``--from`` / breadcrumb-recovered
    re-emit) run the candidate through the installed ComfyUI backend. When the
    pinned ``[comfy]`` extra is not installed, those tests
    skip rather than fail — matching the convention in ``tests/test_refuse.py``.
    """
    try:
        from vibecomfy.comfy_backend import ensure_nodes

        if not ensure_nodes():
            return False
        from comfy.component_model.workflow_convert import convert_ui_to_api  # noqa: F401
        from comfy.nodes_context import get_nodes

        nodes = get_nodes()
        return "KSampler" in nodes.NODE_CLASS_MAPPINGS
    except Exception:
        return False


_requires_comfy_oracle = pytest.mark.skipif(
    not _comfy_available(),
    reason="ComfyUI convert_ui_to_api not available for refusal-spine export",
)


def test_port_help_explains_check_convert_and_related_commands(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["port", "--help"])

    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    for text in [
        "port check",
        "port convert",
        "doctor",
        "validate",
        "nodes install-plan",
        "fetch",
        "--head-check-models",
        "RunPod",
    ]:
        assert text in help_text


def test_port_subcommand_help_is_discoverable(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as check_help:
        parser.parse_args(["port", "check", "--help"])
    check_text = capsys.readouterr().out

    with pytest.raises(SystemExit) as convert_help:
        parser.parse_args(["port", "convert", "--help"])
    convert_text = capsys.readouterr().out

    assert check_help.value.code == 0
    assert convert_help.value.code == 0
    assert "before manual template editing or expensive RunPod validation" in check_text
    assert "--head-check-models" in check_text
    assert "--runtime-object-info" in check_text
    assert "--resolve-on-demand" in check_text
    assert "turn source workflows into Python scratchpads" in convert_text
    assert "--ready-id" in convert_text
    assert "--head-check-models" in convert_text
    assert "--runtime-object-info" in convert_text
    assert "--resolve-on-demand" in convert_text
    assert "Human output is best-effort" in convert_text
    assert "per-template failures" in convert_text
    assert "--json exits nonzero" in convert_text
    assert "row fails" in convert_text


def test_port_convert_all_parser_accepts_omitted_workflow() -> None:
    args = build_parser().parse_args(["port", "convert", "--all", "--dry-run", "--json"])

    assert args.workflow is None
    assert args.all is True
    assert args.dry_run is True
    assert args.json is True



def test_port_export_ready_template_json_matches_compile(capsys: pytest.CaptureFixture[str]) -> None:
    from vibecomfy import load_workflow_any

    code = _cmd_port_export(
        argparse.Namespace(
            workflow="image/z_image",
            ready=True,
            to="json",
            json=True,
            object_info_cache=None,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["api"] == load_workflow_any("image/z_image").compile("api")


def test_port_export_ready_template_subprocess_json_matches_compile() -> None:
    from vibecomfy import load_workflow_any

    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "port", "export", "image/z_image", "--ready", "--to", "json", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["api"] == load_workflow_any("image/z_image").compile("api")


def test_port_export_ui_sidecar_write_failure_reports_partial_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow_path = tmp_path / "scratch.py"
    workflow_path.write_text("from vibecomfy.workflow import VibeWorkflow\n", encoding="utf-8")
    out_path = tmp_path / "out.json"

    class _Source:
        path = str(workflow_path)

    class _Workflow:
        source = _Source()

    ui_payload = {
        "nodes": [
            {
                "id": 1,
                "pos": [0, 0],
                "size": [100, 50],
                "properties": {"vibecomfy_uid": "node-1"},
            }
        ]
    }

    def fail_write_store(py_path: Path, store_envelope: dict[str, object]) -> Path:
        raise PermissionError("denied")

    monkeypatch.setattr(port_commands, "_build_conversion_provider", lambda args: object())
    monkeypatch.setattr(port_commands, "load_workflow_reference", lambda *args, **kwargs: _Workflow())
    monkeypatch.setattr(port_commands, "emit_ui_json", lambda *args, **kwargs: ui_payload)
    monkeypatch.setattr(port_export_cmd, "_resolve_preserve_source", lambda *args, **kwargs: (None, None, {}, None))
    monkeypatch.setattr(port_export_cmd, "write_store", fail_write_store)

    code = _cmd_port_export(
        argparse.Namespace(
            workflow=str(workflow_path),
            ready=False,
            to="ui",
            out=str(out_path),
            json=True,
            object_info_cache=None,
            no_object_info_cache=True,
            from_path=None,
            fresh=True,
            strict=False,
            main_positions=False,
            no_virtual_wires=False,
            force_drop=False,
            dry_run=False,
        )
    )

    captured = capsys.readouterr()
    assert code == 0
    assert out_path.exists()
    assert json.loads(out_path.read_text(encoding="utf-8")) == ui_payload
    assert "wrote" in captured.out
    partial_payload = json.loads(captured.out[captured.out.find("{"):])
    assert partial_payload["status"] == "partial"
    diagnostic = partial_payload["diagnostics"][0]
    assert diagnostic["code"] == "sidecar_write_failed"
    assert diagnostic["details"]["path"] == str(workflow_path.with_suffix(".layout.json"))
    assert diagnostic["details"]["exception_type"] == "PermissionError"


def test_port_export_ui_sidecar_write_failure_reports_warning_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow_path = tmp_path / "scratch.py"
    workflow_path.write_text("from vibecomfy.workflow import VibeWorkflow\n", encoding="utf-8")
    out_path = tmp_path / "out.json"

    class _Source:
        path = str(workflow_path)

    class _Workflow:
        source = _Source()

    monkeypatch.setattr(port_commands, "_build_conversion_provider", lambda args: object())
    monkeypatch.setattr(port_commands, "load_workflow_reference", lambda *args, **kwargs: _Workflow())
    monkeypatch.setattr(
        port_commands,
        "emit_ui_json",
        lambda *args, **kwargs: {
            "nodes": [
                {
                    "id": 1,
                    "pos": [0, 0],
                    "size": [100, 50],
                    "properties": {"vibecomfy_uid": "node-1"},
                }
            ]
        },
    )
    monkeypatch.setattr(port_export_cmd, "_resolve_preserve_source", lambda *args, **kwargs: (None, None, {}, None))
    monkeypatch.setattr(
        port_export_cmd,
        "write_store",
        lambda py_path, store_envelope: (_ for _ in ()).throw(PermissionError("denied")),
    )

    code = _cmd_port_export(
        argparse.Namespace(
            workflow=str(workflow_path),
            ready=False,
            to="ui",
            out=str(out_path),
            json=False,
            object_info_cache=None,
            no_object_info_cache=True,
            from_path=None,
            fresh=True,
            strict=False,
            main_positions=False,
            no_virtual_wires=False,
            force_drop=False,
            dry_run=False,
        )
    )

    captured = capsys.readouterr()
    assert code == 0
    assert out_path.exists()
    assert str(workflow_path.with_suffix(".layout.json")) in captured.err
    assert "PermissionError" in captured.err


def test_port_export_rejects_unsupported_target(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_export(argparse.Namespace(workflow="image/z_image", ready=True, to="yaml", json=True))

    captured = capsys.readouterr()
    assert code == 2
    assert "unsupported export target" in captured.err


def test_port_validate_call_returns_structured_errors(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_validate_call(
        argparse.Namespace(
            class_type="KSampler",
            kwargs=json.dumps({"seed": "bad", "sampler_name": "not-a-sampler", "steps": 999999, "extra": 1}),
            json=True,
            object_info_cache=None,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    codes = {issue["code"] for issue in payload["issues"]}
    assert code == 1
    assert payload["status"] == "error"
    assert payload["provider"] == "AuthoringSchemaProvider"
    assert {"missing_required_input", "unknown_input", "value_not_in_enum", "value_out_of_range", "primitive_type_mismatch"} <= codes


def test_port_validate_call_success_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_validate_call(
        argparse.Namespace(
            class_type="SaveImage",
            kwargs=json.dumps({"images": ["1", 0], "filename_prefix": "out/test"}),
            json=True,
            object_info_cache=None,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["issues"] == []


def test_port_validate_call_subprocess_nonzero_for_structured_errors() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibecomfy.cli",
            "port",
            "validate-call",
            "KSampler",
            "--kwargs",
            '{"seed": "bad"}',
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert any(issue["code"] == "primitive_type_mismatch" for issue in payload["issues"])


@pytest.mark.parametrize(
    ("kwargs", "expected_code", "expected_input"),
    [
        ({"sampler_name": "not-a-sampler"}, "value_not_in_enum", "sampler_name"),
        ({}, "missing_required_input", "model"),
        ({"unknown_knob": 1}, "unknown_input", "unknown_knob"),
        ({"steps": 999999}, "value_out_of_range", "steps"),
        ({"seed": "12"}, "primitive_type_mismatch", "seed"),
    ],
)
def test_port_validate_call_subprocess_reports_stable_error_fields(
    kwargs: dict[str, object],
    expected_code: str,
    expected_input: str,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vibecomfy.cli",
            "port",
            "validate-call",
            "KSampler",
            "--kwargs",
            json.dumps(kwargs),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    matching = [issue for issue in payload["issues"] if issue["code"] == expected_code and issue["input"] == expected_input]
    assert result.returncode == 1
    assert payload["status"] == "error"
    assert payload["class_type"] == "KSampler"
    assert payload["provider"] == "AuthoringSchemaProvider"
    assert matching
    issue = matching[0]
    assert set(issue) == {"code", "message", "severity", "input", "detail"}
    assert issue["severity"] == "error"
    assert issue["detail"]["class_type"] == "KSampler"
    assert issue["detail"]["input"] == expected_input


def test_port_doctor_all_json_combines_isolated_sections(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("vibecomfy.commands.doctor.read_lockfile", lambda: [])
    scratchpad = tmp_path / "doctor_all.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def build():
    workflow = VibeWorkflow(id="doctor-all", source=WorkflowSource(id="doctor-all"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="EmptyImage", inputs={"width": 8, "height": 8, "batch_size": 1, "color": 0})
    workflow.nodes["2"] = VibeNode(id="2", class_type="SaveImage", inputs={"filename_prefix": "out/doctor"})
    workflow.edges.append(VibeEdge("1", "0", "2", "images"))
    workflow.finalize_metadata()
    return workflow
""",
        encoding="utf-8",
    )

    from vibecomfy.security import GateContext, set_gate_context

    token = set_gate_context(GateContext(non_interactive=True, assume_yes=True))
    try:
        code = _cmd_port_doctor_all(argparse.Namespace(workflow=str(scratchpad), ready=False, json=True, object_info_cache=None))
    finally:
        token.var.reset(token)

    payload = json.loads(capsys.readouterr().out)
    sections = {section["name"]: section for section in payload["sections"]}
    assert code == 0
    assert payload["status"] == "ok"
    assert {"port_check", "nodes_install_plan", "validate", "doctor", "runtime_doctor"} <= set(sections)
    for section in sections.values():
        assert "duration_ms" in section
        assert "payload" in section
        assert "findings" in section
        assert "stderr" in section
        assert "next_action" in section
    assert payload["summary"]["section_count"] == 5


def test_port_doctor_all_continues_after_section_failures(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_doctor_all(argparse.Namespace(workflow="image/z_image", ready=True, json=True, object_info_cache=None))

    payload = json.loads(capsys.readouterr().out)
    sections = {section["name"]: section for section in payload["sections"]}
    assert code == 1
    assert payload["status"] == "error"
    assert payload["summary"]["section_count"] == 5
    assert sections["runtime_doctor"]["status"] == "ok"
    assert sections["doctor"]["payload"] is not None
    assert isinstance(payload["findings"], list)
    assert payload["next_action"]


def test_port_doctor_all_subprocess_stdout_is_single_json_object() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "port", "doctor-all", "image/z_image", "--ready", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    decoder = json.JSONDecoder()
    payload, end = decoder.raw_decode(result.stdout)
    assert result.stdout[end:].strip() == ""
    assert result.stdout.lstrip().startswith("{")
    assert result.stdout.rstrip().endswith("}")
    assert _stderr_is_benign(result.stderr), (
        f"Unexpected stderr output:\n{result.stderr}"
    )
    assert result.returncode == 1
    assert payload["summary"]["section_count"] == 5
    sections = {section["name"]: section for section in payload["sections"]}
    assert sections["runtime_doctor"]["status"] == "ok"
    assert sections["runtime_doctor"]["payload"] is not None
    assert sections["doctor"]["payload"] is not None
    assert all(isinstance(section["captured_stdout"], str) for section in payload["sections"])


def test_port_check_json_returns_zero_for_clean_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_check(argparse.Namespace(workflow=str(workflow_path), json=True, head_check_models=False))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["provenance"]["source_kind"] == "raw_json"
    assert payload["contract_shape"] == "workflow_runtime_contract.v1.public_descriptors.v2"
    assert isinstance(payload["public_inputs"], list)
    assert isinstance(payload["public_outputs"], list)
    assert isinstance(payload["graph_contract"], dict)


def test_port_check_returns_nonzero_for_hard_port_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = tmp_path / "bad_port_workflow.json"
    workflow_path.write_text(json.dumps({"1": {"class_type": "UnknownRuntimeNode", "inputs": {}}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_check(argparse.Namespace(workflow=str(workflow_path), json=False, head_check_models=False))

    captured = capsys.readouterr()
    assert code == 1
    assert "unresolved_runtime_class" in captured.out


def test_port_widgets_json_reports_unresolved_widget_aliases_with_unavailable_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = tmp_path / "widgets_workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "PromptNode",
                        "widgets_values": ["hello", "fast", {"collapsed": True}],
                        "inputs": [],
                    }
                ],
                "links": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_widgets(argparse.Namespace(workflow=str(workflow_path), json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    # AuthoringSchemaProvider now prefers the committed object_info index over the
    # local node_index.json, so a synthetic class resolves no schema → every
    # positional widget alias stays unresolved and the suggestions block reports
    # the schema as unavailable (no suggested entry, no python render).
    assert payload["unresolved_widget_aliases"] == [
        {"node_id": "1", "class_type": "PromptNode", "input": "widget_0", "source": "unresolved"},
        {"node_id": "1", "class_type": "PromptNode", "input": "widget_1", "source": "unresolved"},
        {"node_id": "1", "class_type": "PromptNode", "input": "widget_2", "source": "unresolved"},
    ]
    assert payload["suggestions"] == [
        {
            "class_type": "PromptNode",
            "nodes": [
                {
                    "node_id": "1",
                    "unresolved_inputs": ["widget_0", "widget_1", "widget_2"],
                    "widgets_values": ["hello", "fast", {"collapsed": True}],
                }
            ],
            "observed_widget_count": 3,
            "schema_source": "unavailable",
            "suggested_schema_entry": None,
        }
    ]


def test_port_convert_emits_importable_scratchpad_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    out = tmp_path / "out" / "scratchpads" / "converted.py"
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=str(out),
            ready_id=None,
            json=True,
            head_check_models=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["conversion"]["mode"] == "scratchpad"
    text = out.read_text(encoding="utf-8")
    assert "source_type='scratchpad'" in text
    assert "READY_METADATA" not in text
    provenance = _load_emitted_provenance(out)
    assert provenance["source_hash"] == payload["report"]["source_hash"]
    assert provenance["workflow_shape"] == payload["report"]["workflow_shape"]
    assert provenance["output_mode"] == "scratchpad"


def test_port_convert_ready_template_mode_requires_ready_id_and_writes_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    out = tmp_path / "candidate.py"
    monkeypatch.chdir(tmp_path)

    assert _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=str(out),
            ready_id="image/ported",
            json=True,
            head_check_models=False,
        )
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    text = out.read_text(encoding="utf-8")
    assert "READY_METADATA =" in text
    assert "template_id='image/ported'" not in text
    provenance = _load_emitted_provenance(out)
    assert provenance["ready_id"] == "image/ported"
    assert provenance["source_hash"] == payload["report"]["source_hash"]
    assert provenance["workflow_shape"] == payload["report"]["workflow_shape"]
    assert provenance["output_mode"] == "ready_template"


def test_port_convert_diff_implies_dry_run_and_preserves_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    out = tmp_path / "existing.py"
    original = "# existing user file\nVALUE = 'keep me'\n"
    out.write_text(original, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=str(out),
            ready_id=None,
            json=True,
            head_check_models=False,
            strict_ready_template=False,
            dry_run=False,
            diff=True,
            all=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out.read_text(encoding="utf-8") == original
    assert payload["status"] == "ok"
    assert payload["write"]["written"] is False
    assert payload["write"]["dry_run"] is True
    assert payload["write"]["diff_requested"] is True
    assert payload["write"]["diff_forced_dry_run"] is True
    assert payload["write"]["diff"]["original_exists"] is True
    assert payload["write"]["diff"]["changed"] is True
    assert payload["write"]["diff"]["unified_diff_line_count"] > 0
    assert payload["write"]["diff"]["unified_diff"].startswith("--- ")


def test_port_convert_real_write_refuses_manual_target_preserving_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    out = tmp_path / "manual.py"
    original = "# vibecomfy: manual\nVALUE = 'keep me'\n"
    out.write_text(original, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=str(out),
            ready_id=None,
            json=True,
            head_check_models=False,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 1
    assert payload["status"] == "refused"
    assert "# vibecomfy: manual" in payload["message"]
    assert "port convert refused" in captured.err
    assert out.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob(".vibecomfy-port-*")) == []


def test_strict_ready_template_gate_escalates_unresolved_widgets() -> None:
    from vibecomfy.commands.port import _apply_strict_ready_template_gate
    from vibecomfy.porting.report import PortReport

    report = PortReport(
        source="ready_templates/video/example.py",
        workflow_shape={"outputs": 1},
        metadata={
            "widget_analysis": {
                "unresolved_widget_aliases": [
                    {"node_id": "1", "class_type": "ExampleNode", "input": "widget_0"}
                ],
                "suggestions": [
                    {
                        "class_type": "ExampleNode",
                        "schema_source": "committed_widget_schema",
                        "suggested_schema_entry": ["value"],
                    }
                ],
            }
        },
    )

    _apply_strict_ready_template_gate(report)

    assert report.has_errors
    assert report.diagnostics[0].code == "strict_ready_unresolved_widgets"
    assert report.diagnostics[0].detail["count"] == 1


def test_strict_ready_template_gate_requires_output_contract() -> None:
    from vibecomfy.commands.port import _apply_strict_ready_template_gate
    from vibecomfy.porting.report import PortReport

    report = PortReport(
        source="ready_templates/video/example.py",
        workflow_shape={"outputs": 0},
        metadata={"widget_analysis": {"unresolved_widget_aliases": [], "suggestions": []}},
    )

    _apply_strict_ready_template_gate(report)

    assert report.has_errors
    assert report.diagnostics[0].code == "strict_ready_missing_output_contract"
    assert "bind_output" in (report.diagnostics[0].recommendation or "")
    assert "public_outputs" in (report.diagnostics[0].recommendation or "")


# ── port rules ──────────────────────────────────────────────────────────


def test_port_rules_json_returns_deterministic_list(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_rules(argparse.Namespace(json=True, explain=False))
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert isinstance(payload, dict)
    assert "rules_by_category" in payload
    assert "total_rules" in payload
    assert payload["total_rules"] > 0
    by_cat = payload["rules_by_category"]
    assert isinstance(by_cat, dict)
    # Get first rule from first category
    first_cat = next(iter(by_cat.values()))
    rule = first_cat[0]
    assert "id" in rule
    assert "description" in rule
    assert "behavior" in rule
    # Verify note about partial coverage
    assert payload.get("partial_coverage") is True or any(
        r.get("partial_coverage", False)
        for rules in by_cat.values()
        for r in rules
    )


def test_port_rules_explain_shows_behavior(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_rules(argparse.Namespace(json=False, explain=True))
    text = capsys.readouterr().out
    assert code == 0
    assert "R-NAME-01" in text
    assert "emitter.py" in text


# ── port lint ───────────────────────────────────────────────────────────


def test_port_lint_all_json_returns_diagnostics(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_lint(argparse.Namespace(all=True, json=True, workflow=None))
    payload = json.loads(capsys.readouterr().out)
    assert code == 0  # zero unless errors
    assert "diagnostics" in payload
    assert "total" in payload
    assert isinstance(payload["diagnostics"], list)
    # All diagnostics should have required fields
    for d in payload["diagnostics"]:
        assert "severity" in d
        assert "path" in d
        assert "line" in d
        assert "code" in d
        assert "message" in d


def test_port_lint_single_wf_renders_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Lint a known ready template
    code = _cmd_port_lint(argparse.Namespace(workflow="video/wan_i2v", all=False, json=False))
    text = capsys.readouterr().out
    assert code == 0
    # Should report something — at minimum the file path header
    assert "wan_i2v" in text or "ready_templates" in text


# ── port simulate ───────────────────────────────────────────────────────


def test_port_simulate_drop_set_id_map_all_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        port_simulate_cmd,
        "simulate_rule",
        lambda *args, **kwargs: simulate.SimulationResult(
            rule_spec="drop_set_id_map=true",
            templates_total=1,
            templates_affected=0,
            loc_delta_total=0,
            parity_preserved=1,
            parity_broken=0,
            per_template=[{"status": "ok", "changed": False, "original_loc": 1, "loc_delta": 0}],
        ),
    )
    code = _cmd_port_simulate(
        argparse.Namespace(rule="drop_set_id_map=true", all=True, json=True)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "templates_affected" in payload
    assert "loc_delta_total" in payload
    assert "parity_preserved" in payload
    assert isinstance(payload["templates_affected"], int)
    assert isinstance(payload["parity_preserved"], int)


def test_port_simulate_unknown_rule_returns_nonzero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_simulate(
        argparse.Namespace(rule="nonexistent_rule=xyz", all=False, json=True)
    )
    captured = capsys.readouterr()
    assert code == 1
    # Should have some error output
    assert captured.err or captured.out


def test_port_simulate_parity_broken_returns_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        port_simulate_cmd,
        "simulate_rule",
        lambda *args, **kwargs: simulate.SimulationResult(
            rule_spec="drop_set_id_map=true",
            templates_total=1,
            templates_affected=1,
            loc_delta_total=-1,
            parity_preserved=0,
            parity_broken=1,
            per_template=[],
        ),
    )

    code = _cmd_port_simulate(
        argparse.Namespace(rule="drop_set_id_map=true", all=False, json=True)
    )

    assert code == 1
    assert json.loads(capsys.readouterr().out)["parity_broken"] == 1

def test_port_simulate_unsupported_returns_refusal_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        port_simulate_cmd,
        "simulate_rule",
        lambda *args, **kwargs: simulate.SimulationResult(
            rule_spec="drop_set_id_map=true",
            templates_total=1,
            templates_affected=1,
            loc_delta_total=0,
            parity_preserved=0,
            parity_broken=0,
            unsupported=1,
            per_template=[{"status": "unsupported"}],
        ),
    )

    code = _cmd_port_simulate(
        argparse.Namespace(rule="drop_set_id_map=true", all=False, json=True)
    )

    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "unsupported"
    assert payload["parity_broken"] == 0
    assert payload["unsupported"] == 1


def test_port_simulate_unsupported_human_output_is_not_success_framed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        port_simulate_cmd,
        "simulate_rule",
        lambda *args, **kwargs: simulate.SimulationResult(
            rule_spec="drop_set_id_map=true",
            templates_total=1,
            templates_affected=1,
            loc_delta_total=0,
            parity_preserved=0,
            parity_broken=0,
            unsupported=1,
            per_template=[{"status": "unsupported"}],
        ),
    )

    code = _cmd_port_simulate(
        argparse.Namespace(rule="drop_set_id_map=true", all=False, json=False)
    )
    text = capsys.readouterr().out
    assert code == 2
    assert "0/0 preserved" not in text
    assert "✅" not in text
    assert "no broken outputs" not in text
    assert "no admitted templates evaluated" in text
    assert "simulation incomplete" in text


@pytest.mark.parametrize(
    "rule",
    ['drop_set_id_map="true', "drop_set_id_map='true\""],
)
def test_port_simulate_malformed_quotes_return_nonzero(
    rule: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _cmd_port_simulate(
        argparse.Namespace(rule=rule, all=False, json=True)
    )

    assert code == 1
    captured = capsys.readouterr()
    assert "Malformed quoted boolean value" in captured.err

# ── port convert dry-run diff ───────────────────────────────────────────


def test_port_convert_dry_run_diff_json_includes_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = _write_port_workflow(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=None,
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=True,
            diff=True,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert "write" in payload
    assert payload["write"]["dry_run"] is True


def test_port_convert_dry_run_diff_with_ready_template_shows_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Use a real ready template for dry-run diff; target derived from source
    # Manual templates may be refused; dry-run shows diff anyway
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="video/wan_i2v",
            out=None,
            json=False,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=True,
            diff=True,
        )
    )
    captured = capsys.readouterr()
    text = captured.out + captured.err
    # May exit 0 for manual template showing diff, or exit 1 if target resolution fails
    if code == 0:
        assert any(x in text.lower() for x in ["validated", "parity", "import=", "loc"])
    else:
        # Non-zero may happen if the ready template path can't be derived
        # Error output may be on stdout or stderr
        assert len(text) > 0, f"Expected some output, got empty. code={code}"


def _convert_all_args(*, json_output: bool) -> argparse.Namespace:
    return argparse.Namespace(
        workflow="unused",
        out=None,
        all=True,
        ready_id=None,
        json=json_output,
        dry_run=True,
        diff=False,
        head_check_models=False,
        strict_ready_template=False,
        runtime_object_info=False,
        object_info_cache=None,
        no_object_info_cache=False,
        server_url=None,
    )


def _patch_convert_all_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    failing_ids: set[str] | None = None,
    validation_by_id: dict[str, SimpleNamespace] | None = None,
) -> tuple[Path, Path]:
    good_path = tmp_path / "good.py"
    bad_path = tmp_path / "bad.py"
    good_path.write_text("GOOD = True\n", encoding="utf-8")
    bad_path.write_text("BAD = True\n", encoding="utf-8")
    failing_ids = failing_ids or set()
    validation_by_id = validation_by_id or {}
    snapshot = SimpleNamespace(
        templates_list=[
            {"id": "template/good", "path": str(good_path)},
            {"id": "template/bad", "path": str(bad_path)},
        ]
    )
    monkeypatch.setattr(
        "vibecomfy.analysis.corpus.build_corpus_snapshot",
        lambda: snapshot,
    )
    monkeypatch.setattr(
        port_commands,
        "_build_conversion_provider",
        lambda _args: object(),
    )

    def fake_load(path: str, *, schema_provider: object) -> SimpleNamespace:
        del schema_provider
        return SimpleNamespace(workflow=path, raw_workflow={})

    def fake_convert(workflow: str, **_kwargs: object) -> SimpleNamespace:
        template_id = "template/good" if workflow == str(good_path) else "template/bad"
        if template_id in failing_ids:
            raise ValueError("synthetic conversion failure")
        return SimpleNamespace(
            text=Path(workflow).read_text(encoding="utf-8"),
            validation=validation_by_id.get(template_id, SimpleNamespace(parity_ok=True)),
        )

    monkeypatch.setattr("vibecomfy.commands.port._convert.load_port_source", fake_load)
    monkeypatch.setattr("vibecomfy.commands.port._convert.port_convert_workflow", fake_convert)
    return good_path, bad_path


def test_port_convert_all_json_marks_parity_and_validation_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_convert_all_fixture(
        monkeypatch,
        tmp_path,
        validation_by_id={
            "template/good": SimpleNamespace(
                ok=True,
                parity_ok=False,
                parity_error="synthetic parity mismatch",
            ),
            "template/bad": SimpleNamespace(
                ok=False,
                parity_ok=True,
                error="synthetic validation failure",
            ),
        },
    )

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    payload = json.loads(capsys.readouterr().out)
    templates = {item["id"]: item for item in payload["templates"]}

    assert code == 1
    assert payload["status"] == "error"
    assert payload["summary"]["ok_count"] == 0
    assert payload["summary"]["error_count"] == 2
    assert templates["template/good"]["status"] == "error"
    assert templates["template/good"]["parity"] == "failed"
    assert templates["template/good"]["error"] == {
        "type": "ValidationError",
        "message": "synthetic parity mismatch",
    }
    assert templates["template/bad"]["status"] == "error"
    assert templates["template/bad"]["error"] == {
        "type": "ValidationError",
        "message": "synthetic validation failure",
    }



def test_port_convert_all_json_reports_template_failure_and_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_convert_all_fixture(monkeypatch, tmp_path, failing_ids={"template/bad"})

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    templates = {item["id"]: item for item in payload["templates"]}

    assert code == 1
    assert captured.err == ""
    assert payload["status"] == "error"
    assert payload["mode"] == "convert_all"
    assert payload["dry_run"] is True
    assert payload["summary"] == {
        "template_count": 2,
        "ok_count": 1,
        "error_count": 1,
        "changed_count": 0,
    }
    assert templates["template/good"]["status"] == "ok"
    assert templates["template/bad"]["status"] == "error"
    assert templates["template/bad"]["error"] == {
        "type": "ValueError",
        "message": "synthetic conversion failure",
    }


def test_port_convert_all_json_safe_aggregate_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_convert_all_fixture(monkeypatch, tmp_path)

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["summary"] == {
        "template_count": 2,
        "ok_count": 2,
        "error_count": 0,
        "changed_count": 0,
    }
    assert [item["status"] for item in payload["templates"]] == ["ok", "ok"]
    assert all(item["error"] is None for item in payload["templates"])


def test_port_convert_all_human_mode_keeps_line_output_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_convert_all_fixture(monkeypatch, tmp_path, failing_ids={"template/bad"})

    code = _cmd_port_convert(_convert_all_args(json_output=False))
    captured = capsys.readouterr()

    assert code == 0
    assert captured.err == ""
    assert "template/good: parity=ok LOC 1→1 (+0)" in captured.out
    assert "template/bad: error: ValueError: synthetic conversion failure" in captured.out
    assert not captured.out.lstrip().startswith("{")

def test_port_convert_all_json_rejects_malformed_result_comparison(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    before_path = tmp_path / "before.py"
    malformed_path = tmp_path / "malformed.py"
    after_path = tmp_path / "after.py"
    before_path.write_text("BEFORE = True\n", encoding="utf-8")
    malformed_path.write_text("MALFORMED = True\n", encoding="utf-8")
    after_path.write_text("AFTER = True\n", encoding="utf-8")
    snapshot = SimpleNamespace(
        templates_list=[
            {"id": "template/before", "path": str(before_path)},
            {"id": "template/malformed", "path": str(malformed_path)},
            {"id": "template/after", "path": str(after_path)},
        ]
    )
    monkeypatch.setattr(
        "vibecomfy.analysis.corpus.build_corpus_snapshot",
        lambda: snapshot,
    )
    monkeypatch.setattr(
        port_commands,
        "_build_conversion_provider",
        lambda _args: object(),
    )

    class MalformedComparison(str):
        def __ne__(self, _other: object) -> object:
            return object()

    def fake_load(path: str, *, schema_provider: object) -> SimpleNamespace:
        del schema_provider
        return SimpleNamespace(workflow=path, raw_workflow={})

    def fake_convert(workflow: str, **_kwargs: object) -> SimpleNamespace:
        if workflow == str(malformed_path):
            text: object = MalformedComparison("MALFORMED = True\n")
        else:
            text = Path(workflow).read_text(encoding="utf-8")
        return SimpleNamespace(
            text=text,
            validation=SimpleNamespace(parity_ok=True),
        )

    monkeypatch.setattr("vibecomfy.commands.port._convert.load_port_source", fake_load)
    monkeypatch.setattr(
        "vibecomfy.commands.port._convert.port_convert_workflow",
        fake_convert,
    )

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    templates = {item["id"]: item for item in payload["templates"]}

    assert code == 1
    assert captured.err == ""
    assert [item["id"] for item in payload["templates"]] == [
        "template/before",
        "template/malformed",
        "template/after",
    ]
    assert payload["summary"] == {
        "template_count": 3,
        "ok_count": 2,
        "error_count": 1,
        "changed_count": 0,
    }
    assert type(payload["status"]) is str
    assert type(payload["mode"]) is str
    assert type(payload["dry_run"]) is bool
    assert type(payload["templates"]) is list
    assert all(
        type(item["id"]) is str
        and (item["path"] is None or type(item["path"]) is str)
        and type(item["status"]) is str
        and (item["parity"] is None or type(item["parity"]) is str)
        and (item["original_loc"] is None or type(item["original_loc"]) is int)
        and (item["emitted_loc"] is None or type(item["emitted_loc"]) is int)
        and (item["line_count_delta"] is None or type(item["line_count_delta"]) is int)
        and (item["changed"] is None or type(item["changed"]) is bool)
        for item in payload["templates"]
    )
    assert all(type(value) is int for value in payload["summary"].values())
    assert all(
        item["error"] is None
        or (
            type(item["error"]) is dict
            and type(item["error"]["type"]) is str
            and type(item["error"]["message"]) is str
        )
        for item in payload["templates"]
    )
    assert templates["template/before"]["status"] == "ok"
    assert templates["template/after"]["status"] == "ok"
    assert templates["template/malformed"]["error"]["type"] == "TypeError"
    assert "exact builtin str" in templates["template/malformed"]["error"]["message"]


def test_port_convert_all_json_preserves_good_rows_with_malformed_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    good_path, _ = _patch_convert_all_fixture(monkeypatch, tmp_path)
    invalid_path = tmp_path / "invalid.py"
    invalid_path.write_bytes(b"\xff\xfe")
    snapshot = SimpleNamespace(
        templates_list=[
            {"id": "template/good", "path": str(good_path)},
            {"id": "template/invalid", "path": str(invalid_path)},
            {"id": "template/missing-path"},
            {"path": str(good_path)},
            {"id": "template/not-an-object", "path": str(good_path)},
        ]
    )
    snapshot.templates_list[-1] = ["not", "a", "mapping"]
    monkeypatch.setattr(
        "vibecomfy.analysis.corpus.build_corpus_snapshot",
        lambda: snapshot,
    )

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    payload = json.loads(capsys.readouterr().out)
    templates = {item["id"]: item for item in payload["templates"]}

    assert code == 1
    assert payload["status"] == "error"
    assert payload["summary"]["template_count"] == 5
    assert templates["template/good"]["status"] == "ok"
    assert templates["template/invalid"]["error"]["type"] == "UnicodeDecodeError"
    assert templates["template/missing-path"]["path"] is None
    assert templates["template/missing-path"]["error"]["type"] == "KeyError"
    assert templates["<row-3>"]["error"]["type"] == "KeyError"
    assert templates["<row-4>"]["error"]["type"] == "TypeError"


def _run_convert_all_with_adversarial_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    validation_error: object = None,
    result_text: object = None,
) -> tuple[int, dict[str, object], float]:
    good_path = tmp_path / "good.py"
    bad_path = tmp_path / "bad.py"
    good_path.write_text("GOOD = True\n", encoding="utf-8")
    bad_path.write_text("BAD = True\n", encoding="utf-8")
    snapshot = SimpleNamespace(
        templates_list=[
            {"id": "template/good", "path": str(good_path)},
            {"id": "template/bad", "path": str(bad_path)},
        ]
    )
    monkeypatch.setattr(
        "vibecomfy.analysis.corpus.build_corpus_snapshot",
        lambda: snapshot,
    )
    monkeypatch.setattr(port_commands, "_build_conversion_provider", lambda _args: object())
    monkeypatch.setattr(
        "vibecomfy.commands.port._convert.load_port_source",
        lambda path, *, schema_provider: SimpleNamespace(
            workflow=path,
            raw_workflow={},
        ),
    )

    def fake_convert(workflow: str, **_kwargs: object) -> SimpleNamespace:
        if workflow == str(bad_path):
            return SimpleNamespace(
                text=bad_path.read_text(encoding="utf-8") if result_text is None else result_text,
                validation=SimpleNamespace(
                    ok=False,
                    parity_ok=True,
                    error=validation_error,
                ),
            )
        return SimpleNamespace(
            text=good_path.read_text(encoding="utf-8"),
            validation=SimpleNamespace(ok=True, parity_ok=True),
        )

    monkeypatch.setattr(
        "vibecomfy.commands.port._convert.port_convert_workflow",
        fake_convert,
    )
    started = time.monotonic()
    code = _cmd_port_convert(_convert_all_args(json_output=True))
    elapsed = time.monotonic() - started
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert captured.err == ""
    return code, payload, elapsed


def _cyclic_list() -> list[object]:
    value: list[object] = []
    value.append(value)
    return value


def _deep_list() -> list[object]:
    value: list[object] = []
    for _ in range(port_convert_module._CONVERT_ALL_MAX_DEPTH + 5):
        value = [value]
    return value


def _recursive_dict() -> dict[str, object]:
    value: dict[str, object] = {}
    value["self"] = value
    return value


def _oversized_string() -> str:
    return "x" * (port_convert_module._CONVERT_ALL_MAX_STRING_BYTES + 1)





class _InfiniteIterable:
    def __iter__(self):
        while True:
            yield 1


class _InfiniteList(list):
    def __iter__(self):
        while True:
            yield 1



class _InfiniteMapping(dict):
    def items(self):
        while True:
            yield "never", 1


def _oversized_nonascii_string() -> str:
    return "é" * (port_convert_module._CONVERT_ALL_MAX_STRING_BYTES // 2 + 1)


def _oversized_aggregate() -> list[str]:
    return ["x" * 1024] * 17_000


@pytest.mark.parametrize(
    ("case", "value_factory"),
    [
        ("cyclic", _cyclic_list),
        ("recursive", _recursive_dict),
        ("oversized-string", _oversized_string),
        ("oversized-nonascii-string", _oversized_nonascii_string),
        ("deep", _deep_list),
        (
            "oversized",
            lambda: list(range(port_convert_module._CONVERT_ALL_MAX_ITEMS + 1)),
        ),
        ("custom-infinite-iterable", _InfiniteIterable),
        ("custom-infinite-mapping", _InfiniteMapping),
        ("oversized-aggregate", _oversized_aggregate),
        ("custom-infinite-list", _InfiniteList),
    ],
)
def test_port_convert_all_json_bounds_adversarial_nested_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: str,
    value_factory,
) -> None:
    del case
    code, payload, elapsed_text = _run_convert_all_with_adversarial_value(
        tmp_path,
        monkeypatch,
        capsys,
        validation_error=value_factory(),
    )
    templates = {item["id"]: item for item in payload["templates"]}

    assert float(elapsed_text) < 1.0
    assert code == 1
    assert payload["status"] == "error"
    assert payload["summary"] == {
        "template_count": 2,
        "ok_count": 1,
        "error_count": 1,
        "changed_count": 0,
    }
    assert templates["template/good"]["status"] == "ok"
    assert templates["template/bad"]["status"] == "error"
    assert templates["template/bad"]["error"]["type"] == "AggregateNormalizationError"
    assert type(templates["template/bad"]["error"]["message"]) is str


class _HostileResultText(str):
    def splitlines(self, *args: object, **kwargs: object):
        raise AssertionError("hostile splitlines was invoked")

    def __ne__(self, _other: object):
        raise AssertionError("hostile comparison was invoked")


def test_port_convert_all_json_rejects_hostile_result_text_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    started = time.monotonic()
    code, payload, elapsed_text = _run_convert_all_with_adversarial_value(
        tmp_path,
        monkeypatch,
        capsys,
        result_text=_HostileResultText("BAD = True\n"),
    )
    elapsed = time.monotonic() - started
    templates = {item["id"]: item for item in payload["templates"]}

    assert float(elapsed_text) < 1.0
    assert elapsed < 1.0
    assert code == 1
    assert payload["status"] == "error"
    assert templates["template/good"]["status"] == "ok"
    assert templates["template/bad"]["status"] == "error"
    assert templates["template/bad"]["error"]["type"] == "TypeError"
    assert "exact builtin str" in templates["template/bad"]["error"]["message"]


def _assert_json_strings_bounded(value: object) -> None:
    if type(value) is str:
        assert len(value.encode("utf-8")) <= port_convert_module._CONVERT_ALL_MAX_STRING_BYTES
    elif type(value) is dict:
        for nested in value.values():
            _assert_json_strings_bounded(nested)
    elif type(value) is list:
        for nested in value:
            _assert_json_strings_bounded(nested)


def test_port_convert_all_json_bounds_exact_string_cap_off_by_one() -> None:
    normalizer = port_convert_module._BoundedJsonNormalizer()
    at_limit = "x" * port_convert_module._CONVERT_ALL_MAX_STRING_BYTES

    assert normalizer.normalize(at_limit) == at_limit
    with pytest.raises(port_convert_module.AggregateNormalizationError):
        normalizer.normalize(at_limit + "x")

    remaining = port_convert_module._CONVERT_ALL_MAX_AGGREGATE_BYTES - 2 - (
        15 * port_convert_module._CONVERT_ALL_MAX_STRING_BYTES
    )
    exact_aggregate = ["x" * port_convert_module._CONVERT_ALL_MAX_STRING_BYTES] * 15
    exact_aggregate.append("x" * remaining)
    assert type(port_convert_module._BoundedJsonNormalizer().normalize(exact_aggregate)) is list
    with pytest.raises(port_convert_module.AggregateNormalizationError):
        port_convert_module._BoundedJsonNormalizer().normalize(exact_aggregate + ["x"])


def test_port_convert_all_json_bounds_twenty_oversized_paths_and_keeps_good_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    good_path = tmp_path / "good.py"
    good_path.write_text("GOOD = True\n", encoding="utf-8")
    oversized_path = "p" * (port_convert_module._CONVERT_ALL_MAX_STRING_BYTES + 1)
    snapshot = SimpleNamespace(
        templates_list=[
            {"id": "template/good", "path": str(good_path)},
            *[
                {"id": f"template/oversized-{index}", "path": oversized_path}
                for index in range(20)
            ],
        ]
    )
    monkeypatch.setattr("vibecomfy.analysis.corpus.build_corpus_snapshot", lambda: snapshot)
    monkeypatch.setattr(port_commands, "_build_conversion_provider", lambda _args: object())
    monkeypatch.setattr(
        "vibecomfy.commands.port._convert.load_port_source",
        lambda path, *, schema_provider: SimpleNamespace(workflow=path, raw_workflow={}),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.port._convert.port_convert_workflow",
        lambda workflow, **_kwargs: SimpleNamespace(
            text=good_path.read_text(encoding="utf-8"),
            validation=SimpleNamespace(ok=True, parity_ok=True),
        ),
    )

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    templates = {item["id"]: item for item in payload["templates"]}

    assert code == 1
    assert captured.err == ""
    assert len(captured.out.encode("utf-8")) <= port_convert_module._CONVERT_ALL_MAX_AGGREGATE_BYTES
    _assert_json_strings_bounded(payload)
    assert templates["template/good"]["status"] == "ok"
    assert len(templates) == 22


def test_port_convert_all_json_hostile_exception_metaclass_emits_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class HostileExceptionMeta(type):
        def __getattribute__(cls, name: str) -> object:
            if name == "__name__":
                raise AssertionError("hostile exception name access")
            return type.__getattribute__(cls, name)

    class HostileSnapshotError(Exception, metaclass=HostileExceptionMeta):
        pass

    def fail_snapshot() -> None:
        raise HostileSnapshotError("snapshot failure")

    monkeypatch.setattr("vibecomfy.analysis.corpus.build_corpus_snapshot", fail_snapshot)

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 1
    assert captured.err == ""
    assert payload["status"] == "error"
    assert payload["templates"][0]["error"]["type"] == "HostileSnapshotError"
    _assert_json_strings_bounded(payload)


def test_port_convert_all_json_rejects_missing_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_convert_all_fixture(
        monkeypatch,
        tmp_path,
        validation_by_id={"template/good": None},
    )

    code = _cmd_port_convert(_convert_all_args(json_output=True))
    payload = json.loads(capsys.readouterr().out)
    templates = {item["id"]: item for item in payload["templates"]}

    assert code == 1
    assert payload["status"] == "error"
    assert payload["summary"]["ok_count"] == 1
    assert payload["summary"]["error_count"] == 1
    assert templates["template/good"]["status"] == "error"
    assert templates["template/good"]["parity"] == "no-validation"
    assert templates["template/good"]["error"] == {
        "type": "ValidationError",
        "message": "conversion produced no validation result",
    }
    assert templates["template/bad"]["status"] == "ok"


def _write_flat_fixture_node_index(tmp_path: Path) -> None:
    """Write a node_index.json covering every node type in the flat fixture."""
    (tmp_path / "node_index.json").write_text(
        json.dumps(
            [
                {
                    "class_type": "CheckpointLoaderSimple",
                    "pack": "core",
                    "inputs": {
                        "ckpt_name": {"type": "STRING", "required": True},
                        "widget_1": {"type": "STRING", "required": False},
                    },
                    "outputs": [
                        {"type": "MODEL", "name": "MODEL"},
                        {"type": "CLIP", "name": "CLIP"},
                        {"type": "VAE", "name": "VAE"},
                    ],
                },
                {
                    "class_type": "CLIPTextEncode",
                    "pack": "core",
                    "inputs": {
                        "clip": {"type": "CLIP", "required": True},
                        "text": {"type": "STRING", "required": True},
                    },
                    "outputs": [{"type": "CONDITIONING", "name": "CONDITIONING"}],
                },
                {
                    "class_type": "EmptyLatentImage",
                    "pack": "core",
                    "inputs": {
                        "width": {"type": "INT", "required": True},
                        "height": {"type": "INT", "required": True},
                        "batch_size": {"type": "INT", "required": True},
                        "widget_0": {"type": "INT", "required": False},
                        "widget_1": {"type": "INT", "required": False},
                        "widget_2": {"type": "INT", "required": False},
                    },
                    "outputs": [{"type": "LATENT", "name": "LATENT"}],
                },
                {
                    "class_type": "KSampler",
                    "pack": "core",
                    "inputs": {
                        "model": {"type": "MODEL", "required": True},
                        "positive": {"type": "CONDITIONING", "required": True},
                        "negative": {"type": "CONDITIONING", "required": True},
                        "latent_image": {"type": "LATENT", "required": True},
                        "seed": {"type": "INT", "required": False},
                        "steps": {"type": "INT", "required": False},
                        "cfg": {"type": "FLOAT", "required": False},
                        "sampler_name": {"type": "STRING", "required": False},
                        "scheduler": {"type": "STRING", "required": False},
                        "denoise": {"type": "FLOAT", "required": False},
                    },
                    "outputs": [{"type": "LATENT", "name": "LATENT"}],
                },
                {
                    "class_type": "VAEDecode",
                    "pack": "core",
                    "inputs": {
                        "samples": {"type": "LATENT", "required": True},
                        "vae": {"type": "VAE", "required": True},
                    },
                    "outputs": [{"type": "IMAGE", "name": "IMAGE"}],
                },
                {
                    "class_type": "SaveImage",
                    "pack": "core",
                    "inputs": {
                        "images": {"type": "IMAGE", "required": True},
                        "filename_prefix": {"type": "STRING", "required": True},
                    },
                    "outputs": [],
                },
            ]
        ),
        encoding="utf-8",
    )


def test_port_export_to_ui_uses_conversion_schema_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """port export --to ui uses ConversionSchemaProvider, not AuthoringSchemaProvider."""
    import shutil

    from vibecomfy.commands.port import _build_authoring_provider, _build_conversion_provider

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)

    out_emit = tmp_path / "flat_emit.json"
    monkeypatch.chdir(tmp_path)

    called_conversion = False
    called_authoring = False
    _orig_conversion = _build_conversion_provider
    _orig_authoring = _build_authoring_provider

    def _tracked_conversion(args):
        nonlocal called_conversion
        called_conversion = True
        return _orig_conversion(args)

    def _tracked_authoring(args):
        nonlocal called_authoring
        called_authoring = True
        return _orig_authoring(args)

    monkeypatch.setattr(
        "vibecomfy.commands.port._build_conversion_provider", _tracked_conversion
    )
    monkeypatch.setattr(
        "vibecomfy.commands.port._build_authoring_provider", _tracked_authoring
    )

    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.json",
            ready=False,
            to="ui",
            json=True,
            out=str(out_emit),
            object_info_cache=None,
        )
    )

    assert code == 0, f"port export --to ui failed with code {code}"
    assert out_emit.exists(), f"flat_emit.json was not written at {out_emit}"
    assert called_conversion, "_build_conversion_provider was NOT called for --to ui"
    assert not called_authoring, "_build_authoring_provider was called (should be _build_conversion_provider)"


def test_port_export_to_ui_roundtrip_pos_and_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """port export --to ui writes a litegraph envelope with uid-matched pos and vibecomfy_uid."""
    import shutil

    # Write node_index covering all flat-fixture types
    _write_flat_fixture_node_index(tmp_path)

    # Copy flat fixture into tmp_path
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)

    monkeypatch.chdir(tmp_path)

    # Step 1: convert flat.json → flat.py
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"
    assert (tmp_path / "flat.py").exists(), "flat.py was not written"
    assert (tmp_path / "flat.layout.json").exists(), "sidecar flat.layout.json was not written"

    # Step 2: export flat.py --to ui → flat_emit.json
    out_emit = tmp_path / "flat_emit.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=True,
            out=str(out_emit),
            object_info_cache=None,
        )
    )
    assert code == 0, f"port export --to ui failed with code {code}"
    assert out_emit.exists(), f"flat_emit.json was not written at {out_emit}"

    # Step 3: verify the emitted litegraph envelope
    emit_data = json.loads(out_emit.read_text(encoding="utf-8"))
    assert "nodes" in emit_data, "emitted envelope missing 'nodes'"
    assert isinstance(emit_data["nodes"], list), "emitted nodes is not a list"

    # Build uid→pos map from the SOURCE flat fixture
    source_raw = json.loads(flat_json.read_text(encoding="utf-8"))
    source_pos_by_uid: dict[str, list] = {
        str(node["id"]): node["pos"] for node in source_raw["nodes"]
    }

    # Verify each emitted node has vibecomfy_uid and correct pos
    for emitted_node in emit_data["nodes"]:
        props = emitted_node.get("properties", {})
        uid = props.get("vibecomfy_uid")
        assert uid is not None, (
            f"Emitted node id={emitted_node.get('id')} missing properties.vibecomfy_uid"
        )
        assert uid, f"Emitted node {emitted_node.get('id')} has empty vibecomfy_uid"
        expected_pos = source_pos_by_uid.get(uid)
        assert expected_pos is not None, f"uid {uid} not found in source fixture"
        assert emitted_node["pos"] == expected_pos, (
            f"uid {uid}: expected pos {expected_pos}, got {emitted_node['pos']}"
        )


# ── T3: strict exit-code + recovery report ─────────────────────────────


def test_port_export_strict_exits_distinct_code_on_schema_less(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--strict`` exits 2 (not 1) when any node is schema-less or low-confidence."""
    # Write a minimal litegraph workflow with a class_type unknown to every
    # tier of ConversionSchemaProvider (no node_index, no object_info cache,
    # no source parser hit, not in WIDGET_SCHEMA).
    unknown_json = tmp_path / "unknown.json"
    unknown_json.write_text(
        json.dumps(
            {
                "last_node_id": 1,
                "last_link_id": 0,
                "nodes": [
                    {
                        "id": 1,
                        "type": "TotallyFakeNode_12345",
                        "pos": [0, 0],
                        "size": [200, 80],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "inputs": [],
                        "outputs": [],
                        "properties": {},
                        "widgets_values": [],
                    }
                ],
                "links": [],
                "groups": [],
                "config": {},
                "extra": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_export(
        argparse.Namespace(
            workflow="unknown.json",
            ready=False,
            to="ui",
            json=True,
            out=str(tmp_path / "unknown_emit.json"),
            object_info_cache=None,
            no_object_info_cache=True,
            strict=True,
        )
    )

    captured = capsys.readouterr()
    assert code == 2, f"--strict should exit 2 for schema-less corpus, got {code}"
    assert "strict" in captured.err.lower(), (
        f"Expected strict-failure message on stderr, got: {captured.err!r}"
    )


def test_port_export_recovery_report_text_and_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-strict export with schema-less nodes prints recovery report to stderr (text) and stdout (--json)."""
    # Write a node_index covering only one known type (SaveImage).
    # All other node types in the fixture will be schema-less.
    _write_saveimage_only_node_index(tmp_path)

    # Build a tiny workflow: one known node (SaveImage) + one unknown node.
    mixed_json = tmp_path / "mixed.json"
    mixed_json.write_text(
        json.dumps(
            {
                "last_node_id": 2,
                "last_link_id": 1,
                "nodes": [
                    {
                        "id": 1,
                        "type": "UnknownCustomNode_99999",
                        "pos": [0, 0],
                        "size": [200, 80],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "inputs": [],
                        "outputs": [
                            {"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0}
                        ],
                        "properties": {},
                        "widgets_values": [],
                    },
                    {
                        "id": 2,
                        "type": "SaveImage",
                        "pos": [300, 0],
                        "size": [200, 80],
                        "flags": {},
                        "order": 1,
                        "mode": 0,
                        "inputs": [
                            {"name": "images", "type": "IMAGE", "link": 1}
                        ],
                        "outputs": [],
                        "properties": {},
                        "widgets_values": ["ComfyUI"],
                    },
                ],
                "links": [
                    [1, 1, 0, 2, 0, "IMAGE"],
                ],
                "groups": [],
                "config": {},
                "extra": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    # ── Text mode ────────────────────────────────────────────────────────
    out_text = tmp_path / "mixed_emit_text.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="mixed.json",
            ready=False,
            to="ui",
            json=False,
            out=str(out_text),
            object_info_cache=None,
            no_object_info_cache=True,
        )
    )
    captured_text = capsys.readouterr()
    assert code == 0, f"non-strict export failed with code {code}"
    assert out_text.exists(), f"mixed_emit_text.json not written at {out_text}"
    assert "[recovery-report]" in captured_text.err, (
        f"Expected [recovery-report] on stderr, got: {captured_text.err!r}"
    )
    assert "schema-less" in captured_text.err.lower(), (
        f"Expected schema-less mention in stderr recovery report, got: {captured_text.err!r}"
    )
    assert "widget-shape verdicts:" in captured_text.err, (
        f"Expected widget-shape verdict counters in stderr recovery report, got: {captured_text.err!r}"
    )

    # ── JSON mode ────────────────────────────────────────────────────────
    out_json = tmp_path / "mixed_emit_json.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="mixed.json",
            ready=False,
            to="ui",
            json=True,
            out=str(out_json),
            object_info_cache=None,
            no_object_info_cache=True,
        )
    )
    captured_json = capsys.readouterr()
    assert code == 0, f"non-strict --json export failed with code {code}"
    assert out_json.exists(), f"mixed_emit_json.json not written at {out_json}"

    # The recovery report JSON block is printed to stdout alongside any other
    # JSON blocks (e.g. change_report from T11).  Scan all JSON objects in
    # stdout and pick the one containing "recovery_report".
    out_text_all = captured_json.out.strip()
    recovery_json: dict | None = None
    decoder = json.JSONDecoder()
    scan_pos = 0
    while scan_pos < len(out_text_all):
        brace_idx = out_text_all.find("{", scan_pos)
        if brace_idx < 0:
            break
        try:
            obj, end_pos = decoder.raw_decode(out_text_all, brace_idx)
            if isinstance(obj, dict) and "recovery_report" in obj:
                recovery_json = obj
                break
            scan_pos = end_pos
        except json.JSONDecodeError:
            scan_pos = brace_idx + 1
    assert recovery_json is not None, f"No recovery_report JSON block found in stdout: {captured_json.out!r}"
    assert isinstance(recovery_json, dict) and "recovery_report" in recovery_json, (
        f"Parsed JSON missing recovery_report key: {recovery_json!r}"
    )
    rr = recovery_json["recovery_report"]
    assert "summary" in rr, "recovery_report JSON missing 'summary'"
    assert "entries" in rr, "recovery_report JSON missing 'entries'"
    assert rr["summary"]["total_nodes"] > 0, "recovery_report summary reports 0 nodes"
    assert rr["summary"]["schema_less"] > 0, (
        f"Expected at least one schema-less node in partial coverage, "
        f"got schema_less={rr['summary']['schema_less']}"
    )
    assert rr["summary"]["widget_shape"]["safe_to_regenerate"] > 0, (
        f"Expected safe widget-shape count in recovery summary, got: {rr['summary']!r}"
    )
    assert rr["summary"]["widget_shape"]["pin_opaque"] == 0
    assert rr["summary"]["widget_shape"]["refuse"] == 0
    # Every entry must have the canonical keys
    for entry in rr["entries"]:
        if "node_id" not in entry:
            continue
        for key in ("node_id", "class_type", "provider", "confidence", "schema_less"):
            assert key in entry, f"recovery_report entry missing key {key!r}: {entry}"


def test_port_export_refused_widget_shape_reports_text_json_and_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from vibecomfy.porting.refuse import RefusedEmit

    workflow_path = tmp_path / "refusing.py"
    workflow_path.write_text("# scratchpad\n", encoding="utf-8")

    class _Source:
        path = workflow_path

    class _Workflow:
        source = _Source()

    def _fake_emit_ui_json(*args: object, recovery_report: list[dict[str, object]], **kwargs: object) -> dict[str, object]:
        recovery_report.append(
            {
                "node_id": "7",
                "class_type": "Power Lora Loader",
                "provider": "test",
                "confidence": 1.0,
                "schema_less": False,
                "widget_shape_verdict": "refuse",
                "widget_shape_reasons": ["overflow"],
                "widget_shape_details": {
                    "reasons": ["overflow"],
                    "evidence": {
                        "node_id": "7",
                        "class_type": "Power Lora Loader",
                        "overflow": True,
                    },
                },
            }
        )
        raise RefusedEmit(
            "widget shape refused: 1 node(s) cannot be emitted safely",
            {
                "7": {
                    "axis": "widget_shape",
                    "node_id": "7",
                    "class_type": "Power Lora Loader",
                    "reason": "overflow",
                    "reasons": ["overflow"],
                    "details": {"decision": "refuse"},
                }
            },
        )

    monkeypatch.setattr(port_commands, "_build_conversion_provider", lambda args: object())
    monkeypatch.setattr(port_commands, "load_workflow_reference", lambda *args, **kwargs: _Workflow())
    monkeypatch.setattr(port_commands, "emit_ui_json", _fake_emit_ui_json)

    common_args = dict(
        workflow=str(workflow_path),
        ready=False,
        to="ui",
        out=str(tmp_path / "out.json"),
        object_info_cache=None,
        no_object_info_cache=True,
        from_path=None,
        fresh=True,
        strict=False,
        main_positions=False,
        no_virtual_wires=False,
        force_drop=False,
        dry_run=False,
    )

    text_code = _cmd_port_export(argparse.Namespace(json=False, **common_args))
    text_captured = capsys.readouterr()
    assert text_code == 3
    assert "widget-shape verdicts: safe=0, pinned=0, refused=1" in text_captured.err
    assert "refused widget-shape nodes (1):" in text_captured.err
    assert "7(Power Lora Loader): reasons=overflow" in text_captured.err
    assert '"node_id": "7"' in text_captured.err
    assert '"class_type": "Power Lora Loader"' in text_captured.err
    assert '"reason": "overflow"' in text_captured.err

    json_code = _cmd_port_export(argparse.Namespace(json=True, **common_args))
    json_captured = capsys.readouterr()
    assert json_code == 3

    decoder = json.JSONDecoder()
    objects: list[dict[str, object]] = []
    scan_pos = 0
    while scan_pos < len(json_captured.out):
        brace_idx = json_captured.out.find("{", scan_pos)
        if brace_idx < 0:
            break
        obj, end_pos = decoder.raw_decode(json_captured.out, brace_idx)
        if isinstance(obj, dict):
            objects.append(obj)
        scan_pos = end_pos

    recovery_json = next(obj for obj in objects if "recovery_report" in obj)
    refusal_json = next(obj for obj in objects if "refused_emit" in obj)
    summary = recovery_json["recovery_report"]["summary"]  # type: ignore[index]
    assert summary["widget_shape"]["refuse"] == 1  # type: ignore[index]
    assert refusal_json["status"] == "refused"
    refused = refusal_json["refused_emit"]["7"]  # type: ignore[index]
    assert refused["node_id"] == "7"
    assert refused["class_type"] == "Power Lora Loader"
    assert refused["reason"] == "overflow"


def _write_saveimage_only_node_index(tmp_path: Path) -> None:
    """Write a node_index.json covering ONLY SaveImage for recovery-report testing."""
    (tmp_path / "node_index.json").write_text(
        json.dumps(
            [
                {
                    "class_type": "SaveImage",
                    "pack": "core",
                    "inputs": {
                        "images": {"type": "IMAGE", "required": True},
                        "filename_prefix": {"type": "STRING", "required": True},
                    },
                    "outputs": [],
                },
            ]
        ),
        encoding="utf-8",
    )


# ── T12: --fresh / --from flags + preserve-by-default matrix ────────────────


@_requires_comfy_oracle
def test_export_from_flag_loads_ui_json_as_preserve_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--from <path>`` loads a prior emitted UI JSON via store_from_ui_json."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)

    # First, emit a UI JSON from flat.json to use as the --from source.
    out_prior = tmp_path / "flat_prior_emit.json"
    monkeypatch.chdir(tmp_path)
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.json",
            ready=False,
            to="ui",
            json=False,
            out=str(out_prior),
            object_info_cache=None,
        )
    )
    assert code == 0, f"prior export failed with code {code}"
    assert out_prior.exists(), f"flat_prior_emit.json not written at {out_prior}"

    # Now convert flat.json → flat.py to get a fresh workflow.
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"

    # Remove the sidecar so only --from is available.
    sidecar = tmp_path / "flat.layout.json"
    if sidecar.exists():
        sidecar.unlink()

    # Export with --from pointing at the prior emission.
    out_emit = tmp_path / "flat_emit_from.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            from_path=str(out_prior),
            object_info_cache=None,
        )
    )
    assert code == 0, f"port export --from failed with code {code}"
    assert out_emit.exists(), f"flat_emit_from.json not written at {out_emit}"

    # Verify positions are preserved from the prior emission.
    prior_data = json.loads(out_prior.read_text(encoding="utf-8"))
    emit_data = json.loads(out_emit.read_text(encoding="utf-8"))
    prior_pos_by_uid: dict[str, list] = {}
    for node in prior_data["nodes"]:
        uid = node.get("properties", {}).get("vibecomfy_uid")
        if uid:
            prior_pos_by_uid[uid] = node["pos"]
    for node in emit_data["nodes"]:
        uid = node.get("properties", {}).get("vibecomfy_uid")
        if uid and uid in prior_pos_by_uid:
            assert node["pos"] == prior_pos_by_uid[uid], (
                f"uid {uid}: --from did not preserve pos: expected {prior_pos_by_uid[uid]}, got {node['pos']}"
            )


def test_export_fresh_overrides_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--fresh`` ignores an existing sidecar and emits a fresh layout."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Convert to get a sidecar.
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"
    assert (tmp_path / "flat.layout.json").exists(), "sidecar was not written"

    out_emit = tmp_path / "flat_emit_fresh.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            fresh=True,
            object_info_cache=None,
        )
    )
    assert code == 0, f"port export --fresh failed with code {code}"
    assert out_emit.exists(), f"flat_emit_fresh.json not written at {out_emit}"

    # Verify the emitted nodes have positions (fresh layout still places nodes).
    emit_data = json.loads(out_emit.read_text(encoding="utf-8"))
    for node in emit_data["nodes"]:
        assert isinstance(node["pos"], list) and len(node["pos"]) == 2, (
            f"Node id={node['id']} missing position in fresh layout"
        )


def test_export_fresh_overrides_from_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--fresh`` beats ``--from`` — no preserve, fresh layout emitted."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Emit a prior UI JSON.
    out_prior = tmp_path / "flat_prior_emit.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.json",
            ready=False,
            to="ui",
            json=False,
            out=str(out_prior),
            object_info_cache=None,
        )
    )
    assert code == 0

    # Convert to .py
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0

    # Remove sidecar.
    sidecar = tmp_path / "flat.layout.json"
    if sidecar.exists():
        sidecar.unlink()

    out_emit = tmp_path / "flat_emit_fresh_over_from.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            fresh=True,
            from_path=str(out_prior),
            object_info_cache=None,
        )
    )
    assert code == 0, f"port export --fresh --from failed with code {code}"
    emit_data = json.loads(out_emit.read_text(encoding="utf-8"))
    for node in emit_data["nodes"]:
        assert isinstance(node["pos"], list) and len(node["pos"]) == 2, (
            f"Node id={node['id']} missing position with --fresh --from"
        )


@_requires_comfy_oracle
def test_export_breadcrumb_auto_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breadcrumb auto-discovery: prior emitted UI JSON found at default output path."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Step 1: convert flat.json → flat.py (creates sidecar)
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"

    # Step 2: export flat.py --to ui (writes breadcrumb to default output path)
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=None,
            object_info_cache=None,
        )
    )
    assert code == 0, f"first export failed with code {code}"

    candidate = tmp_path / "out" / "ui_export" / "flat.json"
    assert candidate.exists(), f"Default output not found at {candidate}"
    candidate_data = json.loads(candidate.read_text(encoding="utf-8"))
    prior_path = candidate_data.get("extra", {}).get("vibecomfy", {}).get("prior_path")
    assert prior_path is not None, "Breadcrumb prior_path missing"

    # Step 3: remove the sidecar, re-export — should auto-discover via breadcrumb.
    sidecar = tmp_path / "flat.layout.json"
    if sidecar.exists():
        sidecar.unlink()

    out_emit2 = tmp_path / "flat_emit_breadcrumb.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit2),
            object_info_cache=None,
        )
    )
    assert code == 0, f"breadcrumb-recovered export failed with code {code}"
    emit_data = json.loads(out_emit2.read_text(encoding="utf-8"))
    prior_data = json.loads(candidate.read_text(encoding="utf-8"))
    prior_pos_by_uid = {
        node["properties"]["vibecomfy_uid"]: node["pos"]
        for node in prior_data["nodes"]
        if node.get("properties", {}).get("vibecomfy_uid")
    }
    for node in emit_data["nodes"]:
        uid = node.get("properties", {}).get("vibecomfy_uid")
        if uid and uid in prior_pos_by_uid:
            assert node["pos"] == prior_pos_by_uid[uid], (
                f"uid {uid}: breadcrumb did not preserve pos: "
                f"expected {prior_pos_by_uid[uid]}, got {node['pos']}"
            )


def test_export_no_source_is_fresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No sidecar, no --from, no breadcrumb → fresh layout (non-zero positions)."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Convert to .py
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"

    # Remove sidecar so there is no preserve source.
    sidecar = tmp_path / "flat.layout.json"
    if sidecar.exists():
        sidecar.unlink()

    # Ensure no default output exists (breadcrumb path).
    default_out = tmp_path / "out" / "ui_export" / "flat.json"
    if default_out.exists():
        default_out.unlink()

    out_emit = tmp_path / "flat_emit_no_source.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            object_info_cache=None,
        )
    )
    assert code == 0, f"no-source export failed with code {code}"
    emit_data = json.loads(out_emit.read_text(encoding="utf-8"))
    for node in emit_data["nodes"]:
        assert isinstance(node["pos"], list) and len(node["pos"]) == 2, (
            f"Node id={node['id']} missing position in no-source fresh layout"
        )


def test_export_from_flag_takes_priority_over_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both sidecar and --from exist, --from takes priority."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Emit a prior UI JSON with DIFFERENT positions (shifted by +100,+100).
    prior_data = json.loads(flat_json.read_text(encoding="utf-8"))
    for node in prior_data["nodes"]:
        node["pos"] = [node["pos"][0] + 100, node["pos"][1] + 100]
    out_prior = tmp_path / "flat_shifted.json"
    out_prior.write_text(json.dumps(prior_data), encoding="utf-8")

    # Convert to .py (creates sidecar with ORIGINAL positions).
    # Need to use the un-shifted fixture.
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    shutil.copy(fixture, flat_json)
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"
    assert (tmp_path / "flat.layout.json").exists(), "sidecar not written"

    # Export with --from pointing at the SHIFTED prior emission.
    out_emit = tmp_path / "flat_emit_from_over_sidecar.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            from_path=str(out_prior),
            object_info_cache=None,
        )
    )
    assert code == 0, f"port export --from (conflict) failed with code {code}"
    emit_data = json.loads(out_emit.read_text(encoding="utf-8"))
    shifted_pos_by_uid = {
        node.get("properties", {}).get("vibecomfy_uid"): node["pos"]
        for node in prior_data["nodes"]
        if node.get("properties", {}).get("vibecomfy_uid")
    }
    for node in emit_data["nodes"]:
        uid = node.get("properties", {}).get("vibecomfy_uid")
        if uid and uid in shifted_pos_by_uid:
            assert node["pos"] == shifted_pos_by_uid[uid], (
                f"uid {uid}: --from did NOT override sidecar: "
                f"expected shifted {shifted_pos_by_uid[uid]}, got {node['pos']}"
            )


# ── S5 T5: felt-fidelity CLI integration tests ───────────────────────────


@_requires_comfy_oracle
def test_port_export_to_ui_persists_change_report_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``port export --to ui`` persists a .change-report.json artifact
    carrying ``change_report``, ``felt``, ``latency``, and ``version``."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Convert to create a sidecar (preserve source for the gate).
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"

    out_emit = tmp_path / "flat_emit_felt.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            object_info_cache=None,
        )
    )
    assert code == 0, f"port export failed with code {code}"
    assert out_emit.exists(), f"UI output not written at {out_emit}"

    # The artifact must exist at <output>.change-report.json
    artifact_path = out_emit.with_suffix(".change-report.json")
    assert artifact_path.exists(), (
        f"change-report artifact not written at {artifact_path}"
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert "change_report" in artifact, "artifact missing change_report"
    assert "felt" in artifact, "artifact missing felt"
    assert "latency" in artifact, "artifact missing latency"
    assert "version" in artifact, "artifact missing version"
    assert artifact["version"] == 1


@_requires_comfy_oracle
def test_port_export_felt_violation_exits_code_5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A preserved-node felt violation exits with code 5."""
    import shutil

    from vibecomfy.porting.layout import (
        FeltDeltaReport,
        FeltDeltaViolation,
    )

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Convert to get a sidecar.
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"

    # Inject a synthetic felt failure: +50px on the first preserved node.
    def _failing_evaluate(
        prior_store, emitted_ui, change_report, *,
        reroute_uids=frozenset(),
        position_tolerance_px=0.0,
        latency_report=None,
    ):
        return FeltDeltaReport(
            ok=False,
            violations=[
                FeltDeltaViolation(
                    uid="injected",
                    reason="position_moved",
                    prior_pos=[100.0, 200.0],
                    current_pos=[150.0, 200.0],
                    delta_px=50.0,
                )
            ],
            summary="felt gate failed: 1 preserved-node fidelity violation(s)",
            skipped_snapshot_absent=False,
        )

    monkeypatch.setattr(
        "vibecomfy.commands.port.evaluate_felt_delta",
        _failing_evaluate,
    )

    out_emit = tmp_path / "flat_emit_violation.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            object_info_cache=None,
        )
    )
    assert code == 5, f"Expected exit code 5 for felt violation, got {code}"

    # The artifact should still be written even when the gate fails.
    artifact_path = out_emit.with_suffix(".change-report.json")
    assert artifact_path.exists(), (
        "change-report artifact must be written even on felt violation"
    )
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["felt"]["ok"] is False


@_requires_comfy_oracle
def test_port_export_fresh_skips_felt_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--fresh`` exits 0 and skips the felt gate (no preserve source)."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Convert to create sidecar (which --fresh will ignore).
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"

    out_emit = tmp_path / "flat_emit_fresh_gate.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            fresh=True,
            object_info_cache=None,
        )
    )
    assert code == 0, f"--fresh export should exit 0, got {code}"


@_requires_comfy_oracle
def test_port_export_no_virtual_wires_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--no-virtual-wires`` exits 0 for intentional reroute collapse."""
    import shutil

    _write_flat_fixture_node_index(tmp_path)
    fixture = Path(__file__).resolve().parent / "fixtures" / "walking_skeleton" / "flat.json"
    flat_json = tmp_path / "flat.json"
    shutil.copy(fixture, flat_json)
    monkeypatch.chdir(tmp_path)

    # Convert to get a sidecar.
    code = _cmd_port_convert(
        argparse.Namespace(
            workflow="flat.json",
            out="flat.py",
            json=True,
            head_check_models=False,
            ready_id=None,
            strict_ready_template=False,
            dry_run=False,
            diff=False,
            all=False,
        )
    )
    assert code == 0, f"port convert failed with code {code}"

    out_emit = tmp_path / "flat_emit_no_vw.json"
    code = _cmd_port_export(
        argparse.Namespace(
            workflow="flat.py",
            ready=False,
            to="ui",
            json=False,
            out=str(out_emit),
            no_virtual_wires=True,
            object_info_cache=None,
        )
    )
    assert code == 0, f"--no-virtual-wires export should exit 0, got {code}"


# ---------------------------------------------------------------------------
# M6 T14 — --help self-checks
# ---------------------------------------------------------------------------


def test_port_export_help_lists_all_flags() -> None:
    """``port export --help`` must contain every expected flag string."""
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "port", "export", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, f"port export --help failed: {result.stderr}"
    stdout = result.stdout
    for flag in (
        "--to",
        "--fresh",
        "--from",
        "--out",
        "--change-report-out",
        "--strict",
        "--main-positions",
        "--dry-run",
        "--force-drop",
        "--no-virtual-wires",
    ):
        assert flag in stdout, f"Missing flag '{flag}' in port export --help output"


def test_port_convert_help_lists_keep_virtual_wires() -> None:
    """``port convert --help`` must list ``--keep-virtual-wires``."""
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "port", "convert", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, f"port convert --help failed: {result.stderr}"
    assert "--keep-virtual-wires" in result.stdout, (
        "Missing --keep-virtual-wires in port convert --help output"
    )


def test_port_convert_keep_virtual_wires_integration(tmp_path: Path) -> None:
    """Synthetic fixture: ``--keep-virtual-wires`` produces .py with GetNode/SetNode
    literals; without the flag, those literals are absent."""
    from vibecomfy.porting.convert import port_convert_workflow
    from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

    # Build a minimal synthetic workflow with one SetNode and one GetNode.
    wf = VibeWorkflow(
        "help-vw-test",
        WorkflowSource("help-vw-test", path="test/help_vw.json", source_type="raw_json"),
    )
    wf.nodes["1"] = VibeNode("1", "EmptyImage", inputs={"width": 64, "height": 64, "batch_size": 1, "color": 0})
    wf.nodes["2"] = VibeNode("2", "SetNode", inputs={"widget_0": "TEST_SIG"})
    wf.nodes["3"] = VibeNode("3", "GetNode", inputs={"widget_0": "TEST_SIG"})
    wf.nodes["4"] = VibeNode("4", "SaveImage", inputs={"filename_prefix": "out/help"})
    wf.nodes["1"].uid = "1"
    wf.nodes["2"].uid = "2"
    wf.nodes["3"].uid = "3"
    wf.nodes["4"].uid = "4"
    wf.edges.append(VibeEdge("1", "0", "2", "broadcast_in"))
    wf.edges.append(VibeEdge("2", "0", "3", "broadcast_out"))
    wf.edges.append(VibeEdge("3", "0", "4", "images"))

    def _convert_and_get_text(keep: bool) -> str:
        wf_copy = VibeWorkflow(
            "help-vw-test",
            WorkflowSource("help-vw-test", path="test/help_vw.json", source_type="raw_json"),
        )
        for nid in ("1", "2", "3", "4"):
            orig = wf.nodes[nid]
            nn = VibeNode(orig.id, orig.class_type, inputs=dict(orig.inputs), metadata=dict(orig.metadata))
            nn.uid = orig.uid
            wf_copy.nodes[nid] = nn
        for e in wf.edges:
            wf_copy.edges.append(VibeEdge(e.from_node, e.from_output, e.to_node, e.to_input))
        result = port_convert_workflow(
            wf_copy,
            keep_virtual_wires=keep,
            source_path="test/help_vw.json",
            validate=False,
        )
        return result.text

    # Without --keep-virtual-wires: helpers are resolved, no GetNode/SetNode literals.
    text_default = _convert_and_get_text(keep=False)
    assert "GetNode" not in text_default, (
        "Default convert should NOT contain GetNode literal"
    )
    assert "SetNode" not in text_default, (
        "Default convert should NOT contain SetNode literal"
    )

    # With --keep-virtual-wires: helpers survive, .py carries explicit literals.
    text_keep = _convert_and_get_text(keep=True)
    assert "GetNode" in text_keep, (
        "--keep-virtual-wires convert should contain GetNode literal"
    )
    assert "SetNode" in text_keep, (
        "--keep-virtual-wires convert should contain SetNode literal"
    )
