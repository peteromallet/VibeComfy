from __future__ import annotations

import argparse
import asyncio
import json
import importlib
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

import vibecomfy.commands.port as port_module
import vibecomfy.runtime.eval.prompt as eval_prompt_module
from vibecomfy.cli import build_parser
from vibecomfy.commands.inspect import _cmd_inspect
from vibecomfy.commands.nodes import _cmd_nodes_compatible_with
from vibecomfy.commands.port import _cmd_port_doctor_all, _cmd_port_validate_call
from vibecomfy.diagnostics.health import HealthReport, SubcheckFinding, SubcheckResult
from vibecomfy.errors import (
    CanonicalParityFailure,
    MissingModelAssetError,
    RuntimeNodeError,
    SchemaMismatchError,
    UnknownClassError,
)
from vibecomfy.runtime.eval.plan import plan_eval_node
from vibecomfy import workflow_from_ready
from vibecomfy.workflow_bundle import ApprovedProjectionRecord, WorkflowBundleError

doctor_module = importlib.import_module("vibecomfy.commands.port._doctor_all")


def test_port_validate_call_reports_unknown_kwarg_and_missing_required(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_validate_call(
        argparse.Namespace(class_type="KSampler", kwargs='{"seed":42,"sampler":"euler"}', workflow=None, json=True)
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["status"] == "error"
    assert payload["ok"] is False
    assert any(issue["code"] == "unknown_input" and issue["input"] == "sampler" for issue in payload["issues"])
    assert {"latent_image", "model", "positive", "negative"}.issubset(
        {issue["input"] for issue in payload["issues"] if issue["code"] == "missing_required_input"}
    )


def test_port_validate_call_reads_uuid_subgraph_schema(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "definitions": {
                    "subgraphs": {
                        "uuid-subgraph": {
                            "inputs": {"image": {"type": "IMAGE", "required": True}},
                            "outputs": [{"name": "result", "type": "IMAGE"}],
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    code = _cmd_port_validate_call(
        argparse.Namespace(class_type="uuid-subgraph", kwargs='{"img": "x"}', workflow=str(workflow), json=True)
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["status"] == "error"
    assert payload["ok"] is False
    assert payload["issues"][0]["code"] == "unknown_class_type"
    assert payload["issues"][0]["detail"]["class_type"] == "uuid-subgraph"

    # A registered public node remains a real positive schema-validation path;
    # an inline UUID definition is not silently promoted into that registry.
    code = _cmd_port_validate_call(
        argparse.Namespace(
            class_type="KSampler",
            kwargs='{"seed":1,"steps":1,"cfg":1.0,"sampler_name":"euler",'
            '"scheduler":"normal","positive":null,"negative":null,"model":null,"latent_image":null}',
            workflow=None,
            json=True,
        )
    )
    positive = json.loads(capsys.readouterr().out)
    assert code == 0
    assert positive["status"] == "ok"
    assert positive["ok"] is True


def test_nodes_compatible_with_input_and_output_semantics(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_nodes_compatible_with(
        argparse.Namespace(type_or_from_class="VAE", socket_role="input", to_class=None, json=True)
    )
    consumers = json.loads(capsys.readouterr().out)
    assert code == 0
    assert consumers["type"] == "VAE"
    assert consumers["as"] == "input"
    assert any(row["class_type"] == "VAEDecode" and row["socket"] == "vae" for row in consumers["matches"])

    code = _cmd_nodes_compatible_with(
        argparse.Namespace(
            type_or_from_class="CheckpointLoaderSimple",
            from_output="0",
            to_class="KSampler",
            to_input="model",
            json=True,
        )
    )
    producers = json.loads(capsys.readouterr().out)
    assert code == 0
    assert producers["from_class"] == "CheckpointLoaderSimple"
    assert producers["to_class"] == "KSampler"
    assert producers["from_output_type"] == producers["to_input_type"] == "MODEL"
    assert producers["compatible"] is True


def test_port_doctor_all_aggregates_warnings_without_failing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_section(_args: argparse.Namespace) -> dict:
        return {"name": "fake", "status": "warning", "findings": [{"code": "warn"}]}

    monkeypatch.setattr(doctor_module, "_doctor_all_port_check", fake_section)
    monkeypatch.setattr(doctor_module, "_doctor_all_nodes_install_plan", fake_section)
    monkeypatch.setattr(doctor_module, "_doctor_all_validate", fake_section)
    monkeypatch.setattr(doctor_module, "_doctor_all_doctor", fake_section)
    monkeypatch.setattr(doctor_module, "_doctor_all_runtime_doctor", fake_section)
    code = _cmd_port_doctor_all(argparse.Namespace(workflow="image/z_image", json=True))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["summary"]["warning_sections"] == 5
    assert payload["summary"]["finding_count"] == 5


def test_port_doctor_all_current_mode_has_single_global_checks_block(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    def fake_section(args: argparse.Namespace) -> dict:
        calls.append(args.workflow)
        return {"name": "fake", "status": "ok", "findings": []}

    for name in ("_doctor_all_port_check", "_doctor_all_nodes_install_plan", "_doctor_all_validate", "_doctor_all_doctor", "_doctor_all_runtime_doctor"):
        monkeypatch.setattr(doctor_module, name, fake_section)
    code = _cmd_port_doctor_all(argparse.Namespace(workflow="video/wan_i2v", json=True))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["workflow"] == "video/wan_i2v"
    assert payload["summary"]["section_count"] == 5
    assert calls == ["video/wan_i2v"] * 5


def test_lookup_id_runtime_api_and_inspect_cli_match(capsys: pytest.CaptureFixture[str]) -> None:
    workflow = workflow_from_ready("smoke/empty_image_red")
    direct = workflow.lookup_id("2")
    code = _cmd_inspect(argparse.Namespace(workflow="smoke/empty_image_red", node="2", field=None, json=True))
    cli = json.loads(capsys.readouterr().out)

    assert code == 0
    assert cli["id"] == "smoke/empty_image_red"
    assert cli["status"] == "runnable"
    assert cli["public_outputs"][0]["node_id"] == "2"
    assert cli["public_outputs"][0]["output_type"] == direct["class_type"]
    assert direct["class_type"] in cli["contract"]["runtime_class_types"]
    assert direct["outputs"] == ["SaveImage"]
    assert direct["class_type"] == "SaveImage"


def test_inspect_field_and_node_are_mutually_exclusive() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["inspect", "video/wan_i2v", "--field", "prompt", "--node", "37", "--json"])


def test_diagnostic_errors_preserve_next_action_and_severity() -> None:
    cases = [
        MissingModelAssetError("missing"),
        SchemaMismatchError("schema"),
        UnknownClassError("unknown"),
        RuntimeNodeError("runtime", next_action="vibecomfy inspect <workflow> --node <id>"),
        CanonicalParityFailure("parity"),
    ]
    for exc in cases:
        assert "next action:" in str(exc)
        payload = exc.to_dict()
        assert payload["severity"] == "error"
        assert payload["next_action"]


def test_eval_node_dry_run_classifies_outputs_and_plans_preview() -> None:
    from vibecomfy.cli_loader import load_bundle

    payload = plan_eval_node(load_bundle("video/wan_i2v"), "3", dry_run=True).to_json()

    assert payload["execution_mode"] == "dry_run"
    assert payload["queueable"] is True
    assert "56" in payload["skipped_terminal_node_ids"]
    assert payload["outputs"]["output_0"]["comfy_type"] == "LATENT"
    assert payload["preview_injections"][0]["wrapped_via"] == "VAEDecode+PreviewImage"
    assert not {"shape", "dtype", "mean", "std"} & set(json.dumps(payload).split('"'))


def test_eval_node_bundle_queue_once_and_raw_input_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    from vibecomfy.cli_loader import load_bundle

    queued: list[tuple[object, object, str | None]] = []

    class FakeResult:
        prompt_id = "prompt-1"
        outputs = {"1": {}}

    async def fake_run(record, bundle, *, server_url=None, config=None):
        queued.append((record, bundle, server_url))
        return FakeResult()

    monkeypatch.setattr(eval_prompt_module, "run", fake_run)
    bundle = load_bundle("smoke/empty_image_red")
    queued_result = asyncio.run(eval_prompt_module.eval_node(bundle, "1", runtime="server", server_url="http://external.test"))
    assert queued_result.queued is True
    assert queued_result.prompt_id == "prompt-1"
    assert len(queued) == 1
    record, candidate, server_url = queued[0]
    assert isinstance(record, ApprovedProjectionRecord)
    assert server_url == "http://external.test"
    assert "1_preview" in candidate.workflow.nodes
    assert any(edge.from_node == "1" and edge.to_node == "1_preview" for edge in candidate.workflow.edges)
    assert record.api_projection["1"]["class_type"] == "EmptyImage"
    assert record.api_projection["1_preview"]["inputs"]["images"] == ("1", 0)

    queued_before_dry_run = len(queued)
    schema_only = asyncio.run(eval_prompt_module.eval_node(bundle, "1", dry_run=True))
    assert schema_only.queued is False
    assert schema_only.plan.queueable is True
    assert len(queued) == queued_before_dry_run
    with pytest.raises(WorkflowBundleError, match="requires a WorkflowBundle"):
        asyncio.run(eval_prompt_module.eval_node("video/wan_i2v", "3", dry_run=True))
