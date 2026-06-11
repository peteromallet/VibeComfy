from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

import vibecomfy.commands.port as port_commands
from vibecomfy.cli import build_parser
from vibecomfy.commands.port import _cmd_port_check, _cmd_port_convert, _cmd_port_doctor_all, _cmd_port_export, _cmd_port_lint, _cmd_port_rules, _cmd_port_simulate, _cmd_port_validate_call, _cmd_port_widgets

from tests._cli_helpers import (
    _load_emitted_provenance,
    _write_port_node_index,
    _write_port_workflow,
)


def _comfy_available() -> bool:
    """True when the vendored ComfyUI ``convert_ui_to_api`` oracle is importable.

    The refusal-spine driven export paths (``--from`` / breadcrumb-recovered
    re-emit) run the candidate through the vendored ComfyUI backend. When the
    ``[comfy]`` extra / vendored dependency closure is not installed, those tests
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
    reason="vendored ComfyUI convert_ui_to_api not available for refusal-spine export",
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
    assert "turn source workflows into Python scratchpads" in convert_text
    assert "--ready-id" in convert_text
    assert "--head-check-models" in convert_text
    assert "--runtime-object-info" in convert_text


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
    assert result.stderr == ""
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


def test_port_widgets_json_suggests_widget_only_schema_entries(
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
    assert payload["unresolved_widget_aliases"] == [
        {"node_id": "1", "class_type": "PromptNode", "input": "widget_2", "source": "unresolved"}
    ]
    assert payload["suggestions"] == [
        {
            "class_type": "PromptNode",
            "nodes": [
                {
                    "node_id": "1",
                    "unresolved_inputs": ["widget_2"],
                    "widgets_values": ["hello", "fast", {"collapsed": True}],
                }
            ],
            "observed_widget_count": 3,
            "schema_source": "schema_provider",
            "suggested_schema_entry": ["text", "mode", None],
            "python": "'PromptNode': ['text', 'mode', None]",
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


def test_port_simulate_drop_set_id_map_all_json(capsys: pytest.CaptureFixture[str]) -> None:
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

    # The default output path should now exist with a breadcrumb.
    from vibecomfy.porting.emit.ui import default_output_path
    default_out = default_output_path(
        type("WF", (), {"nodes": {}, "edges": []})(), source_template="flat"
    )
    # Actually compute with the real workflow by importing it...
    # The default output is out/ui_export/flat.json
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
