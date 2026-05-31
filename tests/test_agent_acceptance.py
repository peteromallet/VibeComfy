from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import vibecomfy.commands.workflows as workflows_cmd
from vibecomfy.commands.contract import _cmd_contract_doctor, _cmd_contract_inspect
from vibecomfy.commands.inspect import _cmd_inspect
from vibecomfy.commands.port import _cmd_port_convert
from vibecomfy.commands.workflows import _cmd_workflows_list
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.runtime.session import RunResult, _run_metadata
from vibecomfy.workflow import VibeOutput, VibeWorkflow, WorkflowSource


def _read_json(capsys: pytest.CaptureFixture[str]) -> object:
    return json.loads(capsys.readouterr().out)


def _write_template_index(root: Path) -> None:
    (root / "template_index.json").write_text(
        json.dumps(
            {
                "templates": [
                    {
                        "id": "image/indexed",
                        "path": "ready_templates/image/indexed.py",
                        "public_inputs": [{"name": "prompt"}],
                        "public_outputs": [{"name": "image"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_port_node_index(root: Path) -> None:
    (root / "node_index.json").write_text(
        json.dumps(
            [
                {
                    "class_type": "LoadImage",
                    "pack": "core",
                    "inputs": {"image": {"type": "STRING", "required": True}},
                    "outputs": [{"type": "IMAGE", "name": "image"}],
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


def test_acceptance_discover_default_uses_index_without_plugin_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_template_index(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        workflows_cmd,
        "dynamic_ready_template_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("dynamic discovery should be opt-in")),
    )

    code = _cmd_workflows_list(argparse.Namespace(ready=True, limit=10, json=True, include_dynamic=False))

    payload = _read_json(capsys)
    assert code == 0
    assert len(payload) == 1
    row = payload[0]
    assert row["id"] == "image/indexed"
    assert row["media_type"] == "ready"
    assert row["path"] == "ready_templates/image/indexed.py"
    assert row["source_scope"] == "repo"
    assert row["indexed"] is True
    assert row["contract_shape"] == "workflow_runtime_contract.v1.public_descriptors.v2"
    assert row["public_inputs"] == [{"name": "prompt"}]
    assert row["public_outputs"] == [{"name": "image"}]
    assert row["strict_ready_diagnostic_counts"] == {}


def test_acceptance_discover_dynamic_opt_in_marks_unindexed_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_template_index(tmp_path)
    monkeypatch.chdir(tmp_path)
    dynamic_path = tmp_path / "vibecomfy_extras" / "ready_templates" / "image" / "dynamic.py"
    monkeypatch.setattr(
        workflows_cmd,
        "dynamic_ready_template_rows",
        lambda *, exclude_ids: [
            {
                "id": "image/dynamic",
                "path": str(dynamic_path),
                "source_scope": "dynamic",
                "indexed": False,
            }
        ],
    )

    code = _cmd_workflows_list(argparse.Namespace(ready=True, limit=10, json=True, include_dynamic=True))

    payload = _read_json(capsys)
    assert code == 0
    assert [row["id"] for row in payload] == ["image/indexed", "image/dynamic"]
    assert payload[0]["source_scope"] == "repo"
    assert payload[0]["indexed"] is True
    assert payload[1]["source_scope"] == "dynamic"
    assert payload[1]["indexed"] is False
    assert payload[1]["public_inputs"] == []
    assert payload[1]["public_outputs"] == []


def test_acceptance_inspect_contract_and_doctor_surfaces_align_for_z_image(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _cmd_inspect(argparse.Namespace(workflow="image/z_image", json=True)) == 0
    inspect_payload = _read_json(capsys)

    assert _cmd_contract_inspect(argparse.Namespace(workflow="image/z_image", json=True)) == 0
    contract_payload = _read_json(capsys)

    assert _cmd_contract_doctor(argparse.Namespace(workflow="image/z_image", json=True)) == 0
    doctor_payload = _read_json(capsys)

    for payload in (inspect_payload, contract_payload, doctor_payload):
        assert payload["contract_shape"] == "workflow_runtime_contract.v1.public_descriptors.v2"
        assert payload["source_scope"] == "repo"
        assert payload["indexed"] is True
        assert payload["readiness_class"] == "ready"
        assert isinstance(payload["strict_ready_diagnostic_counts"], dict)

    assert inspect_payload["public_inputs"] == contract_payload["public_inputs"] == doctor_payload["public_inputs"]
    assert inspect_payload["public_outputs"] == contract_payload["public_outputs"] == doctor_payload["public_outputs"]
    assert {item["name"] for item in contract_payload["public_inputs"]} >= {"prompt", "seed", "steps"}
    assert {item["name"] for item in contract_payload["public_outputs"]} == {"image"}
    assert doctor_payload["status"] == "ok"
    assert [item for item in doctor_payload["diagnostics"] if item["severity"] == "error"] == []


def test_acceptance_set_public_input_and_compile_z_image_to_api() -> None:
    workflow = workflow_from_ready("image/z_image")
    prompt = "acceptance prompt: a small brass camera on a blue table"

    workflow.set_input("prompt", prompt)
    api = workflow.compile("api")

    assert isinstance(api, dict)
    assert workflow.inputs["prompt"].value == prompt
    assert api[workflow.inputs["prompt"].node_id]["inputs"][workflow.inputs["prompt"].field] == prompt
    output = workflow.outputs[0]
    save_node = api[output.node_id]
    assert save_node["class_type"] == "SaveImage"
    assert save_node["inputs"]["images"] == ["11", 0]


def test_acceptance_dry_run_ready_conversion_reports_strict_evidence_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_port_node_index(tmp_path)
    workflow_path = tmp_path / "workflow.json"
    target = tmp_path / "ready_templates" / "image" / "candidate.py"
    workflow_path.write_text(
        json.dumps(
            {
                "1": {"class_type": "LoadImage", "inputs": {"image": "input.png"}},
                "2": {
                    "class_type": "SaveImage",
                    "inputs": {"images": ["1", 0], "filename_prefix": "out/agent_acceptance"},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = _cmd_port_convert(
        argparse.Namespace(
            workflow=str(workflow_path),
            out=str(target),
            ready_id="image/candidate",
            json=True,
            dry_run=True,
            diff=False,
            head_check_models=False,
            strict_ready_template=False,
            runtime_object_info=False,
            object_info_cache=None,
            no_object_info_cache=True,
            server_url=None,
        )
    )

    payload = _read_json(capsys)
    assert code == 0
    assert not target.exists()
    assert payload["status"] == "ok"
    assert payload["write"]["dry_run"] is True
    assert payload["write"]["written"] is False
    assert payload["strict_ready_ok"] is True
    assert payload["strict_ready_diagnostics"] == []
    assert payload["conversion"]["validation"]["strict_ready_ok"] is True
    assert payload["conversion"]["validation"]["strict_ready_diagnostics"] == []
    assert payload["report"]["contract_shape"] == "workflow_runtime_contract.v1.public_descriptors.v2"
    assert isinstance(payload["report"]["public_outputs"], list)


def test_acceptance_run_metadata_artifact_manifest_lookup_without_runtime(tmp_path: Path) -> None:
    preview = tmp_path / "out" / "previews" / "preview_00001.png"
    clip = tmp_path / "out" / "clips" / "clip_00001.mp4"
    preview.parent.mkdir(parents=True)
    clip.parent.mkdir(parents=True)
    preview.write_bytes(b"image")
    clip.write_bytes(b"video")

    workflow = VibeWorkflow("agent-acceptance", WorkflowSource("agent-acceptance"))
    workflow.outputs.extend(
        [
            VibeOutput(
                node_id="9",
                output_type="SaveImage",
                name="preview",
                artifact_kind="image",
                filename_prefix="previews/preview",
            ),
            VibeOutput(
                node_id="10",
                output_type="SaveVideo",
                name="clip",
                artifact_kind="video",
                filename_prefix="clips/clip",
            ),
        ]
    )
    metadata = _run_metadata(
        run_id="run-agent-acceptance",
        workflow=workflow,
        api_dict={},
        queued={"prompt_id": "prompt-agent-acceptance"},
        outputs=[str(preview), str(clip)],
        runtime="embedded",
    )
    run_dir = tmp_path / "out" / "runs" / metadata["run_id"]
    run_dir.mkdir(parents=True)
    metadata_path = run_dir / "metadata.json"
    log_path = run_dir / "comfy.log"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    log_path.write_text("", encoding="utf-8")
    result = RunResult(
        run_id=metadata["run_id"],
        prompt_id="prompt-agent-acceptance",
        outputs=metadata["outputs"],
        metadata_path=str(metadata_path),
        log_path=str(log_path),
    )

    persisted = json.loads(Path(result.metadata_path).read_text(encoding="utf-8"))
    manifest = persisted["artifact_manifest"]
    assert result.outputs == [str(preview), str(clip)]
    assert manifest["by_output"] == {"preview": [str(preview)], "clip": [str(clip)]}
    assert manifest["unmapped"] == []
    assert {item["output"] for item in manifest["attribution"]} == {"preview", "clip"}
