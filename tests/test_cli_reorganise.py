from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import vibecomfy.commands.reorganise as reorganise_command
from vibecomfy.commands.reorganise import _cmd_reorganise


def _node(node_id: int, class_type: str, uid: str) -> dict:
    return {
        "id": node_id,
        "type": class_type,
        "class_type": class_type,
        "pos": [node_id * 15, node_id * 20],
        "size": [200, 80],
        "properties": {"vibecomfy_uid": uid, "kept": uid},
    }


def _ui() -> dict:
    return {
        "nodes": [
            _node(1, "CheckpointLoaderSimple", "checkpoint"),
            _node(2, "CLIPTextEncode", "positive"),
            _node(3, "KSampler", "sample"),
            _node(4, "VAEDecode", "decode"),
            _node(5, "SaveImage", "save"),
        ],
        "links": [
            [1, 1, 0, 3, 0, "MODEL"],
            [2, 2, 0, 3, 1, "CONDITIONING"],
            [3, 3, 0, 4, 0, "LATENT"],
            [4, 4, 0, 5, 0, "IMAGE"],
        ],
        "groups": [{"title": "Existing", "bounding": [0, 0, 100, 100], "nodes": [1]}],
        "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}},
        "lastRerouteId": 4,
    }


def _write_workflow(tmp_path: Path) -> Path:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(json.dumps(_ui()), encoding="utf-8")
    return workflow_path


def test_reorganise_assess_emits_deterministic_offline_json(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_path = _write_workflow(tmp_path)

    code = _cmd_reorganise(
        argparse.Namespace(
            workflow=str(workflow_path),
            assess=True,
            preview=False,
            apply=False,
            out=None,
            sidecar=None,
            spacing="compact",
            existing_group_policy="preserve",
            force_regroup=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    repeat_code = _cmd_reorganise(
        argparse.Namespace(
            workflow=str(workflow_path),
            assess=True,
            preview=False,
            apply=False,
            out=None,
            sidecar=None,
            spacing="compact",
            existing_group_policy="preserve",
            force_regroup=False,
        )
    )
    repeat_payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert repeat_code == 0
    assert repeat_payload == payload
    assert payload["mode"] == "assess"
    assert payload["loaded"]["source_label"] == "workflow.json"
    assert payload["options"]["compile_options"]["spacing_preset"] == "compact"
    assert payload["options"]["compile_options"]["existing_group_policy"] == "preserve"
    assert payload["assessment"]["metrics"]


def test_reorganise_preview_writes_artifacts_and_sanitized_report(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    sidecar_path = tmp_path / "workflow.layout.json"
    sidecar_path.write_text(
        json.dumps(
            {
                "store_version": 2,
                "vibecomfy_version": "test",
                "schema_hash": "old",
                "entries": {},
                "groups": [
                    {
                        "title": "Preserved",
                        "bounding": [1, 2, 3, 4],
                        "nodes": ["checkpoint"],
                    }
                ],
                "extra": {"ds": {"scale": 0.5, "offset": [4, 5]}, "kept": True},
                "lastRerouteId": 44,
                "definitions": {"subgraphs": []},
                "virtual_wires": {
                    "wire": {"type": "GetNode", "endpoints": ["checkpoint"]}
                },
            }
        ),
        encoding="utf-8",
    )
    out_path = tmp_path / "cleaned.json"
    preview_calls: list[dict[str, Any]] = []
    original_preview = reorganise_command.preview_reorganise_workflow

    def offline_preview(*call_args: Any, **call_kwargs: Any) -> Any:
        assert "semantic_plan_provider" not in call_kwargs
        assert "second_stage_plan_provider" not in call_kwargs
        preview_calls.append(dict(call_kwargs))
        return original_preview(*call_args, **call_kwargs)

    monkeypatch.setattr(
        reorganise_command,
        "preview_reorganise_workflow",
        offline_preview,
    )

    code = _cmd_reorganise(
        argparse.Namespace(
            workflow=str(workflow_path),
            assess=False,
            preview=True,
            apply=False,
            out=str(out_path),
            sidecar=str(sidecar_path),
            spacing="wide",
            existing_group_policy="preserve",
            force_regroup=False,
        )
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert stdout_payload["status"] == "ok"
    assert len(preview_calls) == 1
    for filename in [
        "cleaned.json",
        "reorganisation_plan.json",
        "reorganisation_report.md",
        "reorganisation_metrics.json",
        "structural_noop_evidence.json",
        "reorganisation_preview_manifest.json",
    ]:
        assert (tmp_path / filename).is_file()

    manifest = json.loads(
        (tmp_path / "reorganisation_preview_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["plan_source"] == "deterministic"
    assert manifest["source"]["label"] == "workflow.json"
    assert manifest["source"]["sidecar_label"] == "workflow.layout.json"
    assert manifest["options"]["compile_options"]["spacing_preset"] == "wide"
    assert manifest["options"]["compile_options"]["existing_group_policy"] == "preserve"
    assert manifest["options"]["compile_options"]["force_regroup"] is False
    assert manifest["apply_data"]["layout_only_structural_noop"] is True
    assert (
        manifest["apply_data"]["structural_hash_before"]
        == manifest["apply_data"]["structural_hash_after"]
    )
    assert manifest["apply_data"]["candidate_patch_sha256"]
    assert manifest["candidate_ui_sha256"]

    plan_payload = json.loads(
        (tmp_path / "reorganisation_plan.json").read_text(encoding="utf-8")
    )
    assert plan_payload["plan_source"] == "deterministic"
    assert plan_payload["provider_diagnostics"] == []
    assert plan_payload["second_stage_results"] == []

    report = (tmp_path / "reorganisation_report.md").read_text(encoding="utf-8")
    assert str(tmp_path) not in report
    assert str(workflow_path) not in report
    assert str(sidecar_path) not in report
    assert "workflow.json" in report
    assert str(tmp_path) not in manifest["sanitized_report_text"]
    assert str(workflow_path) not in manifest["sanitized_report_text"]
    assert str(sidecar_path) not in manifest["sanitized_report_text"]

    evidence = json.loads(
        (tmp_path / "structural_noop_evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["layout_only_structural_noop"] is True
    assert evidence["apply_data"]["layout_only_structural_noop"] is True
    assert evidence["patch_apply"]["layout_only_structural_noop"] is True
    assert (
        evidence["patch_apply"]["structural_hash_before"]
        == evidence["patch_apply"]["structural_hash_after"]
    )
    assert (
        evidence["patch_apply"]["candidate_patch_sha256"]
        == manifest["apply_data"]["candidate_patch_sha256"]
    )
    candidate = json.loads(out_path.read_text(encoding="utf-8"))
    assert candidate["extra"]["ds"] == {"scale": 0.5, "offset": [4, 5]}
    assert candidate["extra"]["kept"] is True
    assert candidate["extra"]["virtual_wires"] == {
        "wire": {"type": "GetNode", "endpoints": ["checkpoint"]}
    }
    assert candidate["lastRerouteId"] == 44


def test_reorganise_apply_writes_previewed_candidate_with_in_place_backup(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    out_path = tmp_path / "cleaned.json"

    preview_code = _cmd_reorganise(
        argparse.Namespace(
            workflow=str(workflow_path),
            assess=False,
            preview=True,
            apply=False,
            out=str(out_path),
            sidecar=None,
            spacing="balanced",
            existing_group_policy="semantic_preserve",
            force_regroup=False,
        )
    )
    capsys.readouterr()
    original_source_bytes = workflow_path.read_bytes()
    previewed_candidate_bytes = out_path.read_bytes()

    apply_code = _cmd_reorganise(
        argparse.Namespace(
            workflow=str(workflow_path),
            assess=False,
            preview=False,
            apply=True,
            out=None,
            sidecar=None,
            spacing="compact",
            existing_group_policy="preserve",
            force_regroup=True,
            manifest=str(tmp_path / "reorganisation_preview_manifest.json"),
        )
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    assert preview_code == 0
    assert apply_code == 0
    assert stdout_payload["status"] == "ok"
    assert workflow_path.read_bytes() == previewed_candidate_bytes
    assert workflow_path.with_name("workflow.json.bak").read_bytes() == original_source_bytes


def test_reorganise_apply_refuses_stale_source_graph(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    out_path = tmp_path / "cleaned.json"

    preview_code = _cmd_reorganise(
        argparse.Namespace(
            workflow=str(workflow_path),
            assess=False,
            preview=True,
            apply=False,
            out=str(out_path),
            sidecar=None,
            spacing="balanced",
            existing_group_policy="semantic_preserve",
            force_regroup=False,
        )
    )
    capsys.readouterr()
    source = json.loads(workflow_path.read_text(encoding="utf-8"))
    source["nodes"][0]["class_type"] = "DifferentLoader"
    workflow_path.write_text(json.dumps(source), encoding="utf-8")
    changed_source_bytes = workflow_path.read_bytes()

    apply_code = _cmd_reorganise(
        argparse.Namespace(
            workflow=str(workflow_path),
            assess=False,
            preview=False,
            apply=True,
            out=None,
            sidecar=None,
            spacing="balanced",
            existing_group_policy="semantic_preserve",
            force_regroup=False,
            manifest=str(tmp_path / "reorganisation_preview_manifest.json"),
        )
    )

    captured = capsys.readouterr()
    assert preview_code == 0
    assert apply_code == 1
    assert "stale preview manifest: source canonical hash changed" in captured.err
    assert workflow_path.read_bytes() == changed_source_bytes
    assert not workflow_path.with_name("workflow.json.bak").exists()
