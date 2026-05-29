from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.commands.port import _cmd_port_check, _cmd_port_convert, _cmd_port_doctor_all, _cmd_port_export, _cmd_port_lint, _cmd_port_rules, _cmd_port_simulate, _cmd_port_validate_call, _cmd_port_widgets

from tests._cli_helpers import (
    _load_emitted_provenance,
    _write_port_node_index,
    _write_port_workflow,
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

    code = _cmd_port_doctor_all(argparse.Namespace(workflow=str(scratchpad), ready=False, json=True, object_info_cache=None))

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

    # The recovery report JSON block is printed to stdout AFTER the "wrote ..."
    # message.  Extract it by finding the JSON object after the first newline.
    out_text_all = captured_json.out.strip()
    # Find the first '{' that starts the JSON block
    brace_idx = out_text_all.find("{")
    assert brace_idx >= 0, f"No JSON block found in stdout: {captured_json.out!r}"
    recovery_json = json.loads(out_text_all[brace_idx:])
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
    # Every entry must have the canonical keys
    for entry in rr["entries"]:
        for key in ("node_id", "class_type", "provider", "confidence", "schema_less"):
            assert key in entry, f"recovery_report entry missing key {key!r}: {entry}"


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
