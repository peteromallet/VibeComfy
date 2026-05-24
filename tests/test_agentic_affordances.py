from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

import vibecomfy.commands.port as port_module
import vibecomfy.runtime.eval_prompt as eval_prompt_module
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
from vibecomfy.runtime.eval import plan_eval_node
from vibecomfy import workflow_from_ready


def test_port_validate_call_reports_unknown_kwarg_and_missing_required(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_port_validate_call(
        argparse.Namespace(class_type="KSampler", kwargs='{"seed":42,"sampler":"euler"}', workflow=None, json=True)
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["valid"] is False
    assert {"kwarg": "sampler", "type": "unknown_kwarg", "suggestion": "did you mean 'sampler_name'?"} in payload[
        "errors"
    ]
    assert {"latent_image", "model", "positive", "negative"}.issubset(set(payload["missing_required"]))
    assert "LATENT" in payload["schema_outputs"]


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
    assert payload["schema_source"] == "workflow_subgraph"
    assert payload["missing_required"] == ["image"]
    assert payload["schema_outputs"] == ["IMAGE"]
    assert payload["errors"][0]["kwarg"] == "img"


def test_nodes_compatible_with_input_and_output_semantics(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_nodes_compatible_with(argparse.Namespace(target="VAE", direction="input", json=True))
    consumers = json.loads(capsys.readouterr().out)
    assert code == 0
    assert {"class": "VAEDecode", "kwarg": "vae", "required": True} in consumers

    code = _cmd_nodes_compatible_with(argparse.Namespace(target="KSampler", direction="output", json=True))
    producers = json.loads(capsys.readouterr().out)
    assert code == 0
    assert any(row["feeds_kwarg"] == "model" and row["output_type"] == "MODEL" for row in producers)
    assert any(row["feeds_kwarg"] == "positive" and row["output_type"] == "CONDITIONING" for row in producers)


def test_port_doctor_all_aggregates_warnings_without_failing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_health(target: str) -> HealthReport:
        return HealthReport(
            workflow=target,
            ok=True,
            subchecks=[
                SubcheckResult(
                    name="port lint",
                    ok=True,
                    findings=[SubcheckFinding(severity="warning", code="warn", message="warning only")],
                )
            ],
        )

    monkeypatch.setattr(port_module, "run_health_checks", fake_health)
    code = _cmd_port_doctor_all(argparse.Namespace(workflow="image/z_image", all=False, json=True))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["ok"] is True
    assert payload["templates"][0]["subchecks"][0]["warning_count"] == 1


def test_port_doctor_all_all_mode_has_single_global_checks_block(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    paths = [tmp_path / "a.py", tmp_path / "b.py"]
    for path in paths:
        path.write_text("# test\n", encoding="utf-8")

    monkeypatch.setattr(port_module, "repo_ready_template_paths", lambda: paths)
    monkeypatch.setattr(port_module, "repo_ready_template_id_for_path", lambda path: Path(path).stem)
    monkeypatch.setattr(
        port_module,
        "run_health_checks",
        lambda target: HealthReport(workflow=target, ok=True, subchecks=[SubcheckResult(name="validate", ok=True)]),
    )

    code = _cmd_port_doctor_all(argparse.Namespace(workflow=None, all=True, json=True))
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["global_checks"]["template_count"] == 2
    assert payload["global_checks"]["repeated_global_nodepack_drift_checks"] is False
    assert [item["label"] for item in payload["templates"]] == ["a", "b"]


def test_lookup_id_runtime_api_and_inspect_cli_match(capsys: pytest.CaptureFixture[str]) -> None:
    workflow = workflow_from_ready("video/wan_i2v")
    direct = workflow.lookup_id("37", source_path="ready_templates/video/wan_i2v.py")

    code = _cmd_inspect(argparse.Namespace(workflow="video/wan_i2v", node="37", field=None, json=True))
    cli = json.loads(capsys.readouterr().out)

    assert code == 0
    assert cli["node_id"] == direct["node_id"] == "37"
    assert cli["variable"] == direct["variable"] == "unetloader"
    assert cli["class_type"] == direct["class_type"] == "UNETLoader"
    assert cli["source_line"] == direct["source_line"]


def test_inspect_field_and_node_are_mutually_exclusive() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["inspect", "video/wan_i2v", "--field", "prompt", "--node", "37", "--json"])


def test_diagnostic_errors_preserve_next_action_and_severity() -> None:
    cases = [
        MissingModelAssetError("missing"),
        SchemaMismatchError("schema"),
        UnknownClassError("unknown"),
        RuntimeNodeError("runtime"),
        CanonicalParityFailure("parity"),
    ]
    for exc in cases:
        assert "next action:" in str(exc)
        payload = exc.to_dict()
        assert payload["severity"] == "error"
        assert payload["next_action"]


def test_eval_node_dry_run_classifies_outputs_and_plans_preview() -> None:
    payload = plan_eval_node("video/wan_i2v", "50", dry_run=True).to_json()

    assert payload["execution_mode"] == "dry_run"
    assert payload["queueable"] is True
    assert "56" in payload["skipped_terminal_node_ids"]
    assert payload["outputs"]["positive"]["info"] == "type-only"
    assert payload["outputs"]["latent"]["wrapped_via"] == "VAEDecode+PreviewImage"
    assert not {"shape", "dtype", "mean", "std"} & set(json.dumps(payload).split('"'))


def test_eval_node_raw_queue_once_and_schema_only_never_queues(monkeypatch: pytest.MonkeyPatch) -> None:
    queued_prompts: list[dict] = []
    entered_servers: list[str | None] = []

    @asynccontextmanager
    async def fake_server(*, server_url=None, log_path=None, config=None):
        entered_servers.append(server_url)
        yield server_url or "http://fake.test"

    class FakeClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def queue_prompt(self, api_dict: dict) -> dict:
            queued_prompts.append(api_dict)
            return {"prompt_id": "prompt-1"}

    async def fake_wait(server_url: str, prompt_id: str | None, *, config=None) -> dict:
        return {prompt_id: {"outputs": {"52": {"images": [{"filename": "preview.png"}]}}}}

    monkeypatch.setattr(eval_prompt_module, "comfy_server", fake_server)
    monkeypatch.setattr(eval_prompt_module, "ComfyClient", FakeClient)
    monkeypatch.setattr(eval_prompt_module, "_wait_for_server_history", fake_wait)

    queued = asyncio.run(eval_prompt_module.eval_node("video/wan_i2v", "50", server_url="http://external.test"))
    schema_only = asyncio.run(eval_prompt_module.eval_node("video/wan_i2v", "37"))

    assert queued.queued is True
    assert queued.prompt_id == "prompt-1"
    assert len(queued_prompts) == 1
    assert any(node.get("class_type") == "PreviewImage" for node in queued_prompts[0].values())
    assert schema_only.queued is False
    assert len(queued_prompts) == 1
    assert entered_servers == ["http://external.test"]
