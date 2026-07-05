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
    for filename in [
        "candidate.patch.json",
        "layout_before.png",
        "layout_after.png",
        "layout_metrics.json",
        "layout_trace.json",
        "manifest.json",
    ]:
        assert not (tmp_path / filename).exists()

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


def test_reorganise_preview_debug_layout_writes_opt_in_layout_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    out_path = tmp_path / "cleaned.json"

    code = _cmd_reorganise(
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
            replace_original=False,
            visualize=False,
            metrics=False,
            trace_layout=False,
            debug_layout=True,
        )
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert stdout_payload["status"] == "ok"
    for filename in [
        "candidate.patch.json",
        "layout_before.png",
        "layout_after.png",
        "layout_metrics.json",
        "layout_trace.json",
        "manifest.json",
        "reorganisation_preview_manifest.json",
    ]:
        assert (tmp_path / filename).is_file()

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    legacy_manifest = json.loads(
        (tmp_path / "reorganisation_preview_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "ok"
    assert manifest["artifacts"]["candidate_patch_json"] == "candidate.patch.json"
    assert manifest["artifacts"]["layout_before_png"] == "layout_before.png"
    assert manifest["artifacts"]["layout_after_png"] == "layout_after.png"
    assert manifest["artifacts"]["layout_metrics_json"] == "layout_metrics.json"
    assert manifest["artifacts"]["layout_trace_json"] == "layout_trace.json"
    assert stdout_payload["artifacts"]["manifest_json"] == "manifest.json"
    assert legacy_manifest["artifacts"]["layout_trace_json"] == "layout_trace.json"

    trace_payload = json.loads((tmp_path / "layout_trace.json").read_text(encoding="utf-8"))
    assert trace_payload["status"] == "ok"
    assert trace_payload["entries"]
    assert trace_payload["compile"]["ok"] is True


def test_reorganise_preview_individual_flags_create_same_artifacts_as_debug_layout(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    out_path = tmp_path / "cleaned.json"

    code = _cmd_reorganise(
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
            replace_original=False,
            visualize=True,
            metrics=True,
            trace_layout=True,
            debug_layout=False,
        )
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert stdout_payload["status"] == "ok"
    for filename in [
        "candidate.patch.json",
        "layout_before.png",
        "layout_after.png",
        "layout_metrics.json",
        "layout_trace.json",
        "manifest.json",
        "reorganisation_preview_manifest.json",
    ]:
        assert (tmp_path / filename).is_file(), f"missing artifact: {filename}"

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "ok"
    assert manifest["artifacts"]["candidate_patch_json"] == "candidate.patch.json"
    assert manifest["artifacts"]["layout_before_png"] == "layout_before.png"
    assert manifest["artifacts"]["layout_after_png"] == "layout_after.png"
    assert manifest["artifacts"]["layout_metrics_json"] == "layout_metrics.json"
    assert manifest["artifacts"]["layout_trace_json"] == "layout_trace.json"


def test_reorganise_preview_metrics_json_includes_extended_keys(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    out_path = tmp_path / "cleaned.json"

    code = _cmd_reorganise(
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
            replace_original=False,
            visualize=False,
            metrics=False,
            trace_layout=False,
            debug_layout=True,
        )
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    assert code == 0

    metrics_payload = json.loads(
        (tmp_path / "layout_metrics.json").read_text(encoding="utf-8")
    )
    compile_metrics = metrics_payload["compile"]["report"]["metrics"]
    metric_names = {m["name"] for m in compile_metrics}

    extended_keys = {
        "compiled_node_overlap_count",
        "compiled_group_overlap_count",
        "compiled_internal_whitespace_ratio_max",
        "compiled_baseline_variance_max",
        "compiled_detached_group_distance_max",
        "compiled_helper_sidecar_overlap_count",
        "compiled_note_section_mismatch_count",
        "compiled_max_primary_nodes_per_row",
        "compiled_long_edge_distance_max",
    }
    missing = extended_keys - metric_names
    assert not missing, f"metrics JSON missing extended keys: {missing}"

    legacy_metrics = json.loads(
        (tmp_path / "reorganisation_metrics.json").read_text(encoding="utf-8")
    )
    legacy_metric_names = {m["name"] for m in legacy_metrics["compile"]["report"]["metrics"]}
    legacy_missing = extended_keys - legacy_metric_names
    assert not legacy_missing, f"legacy metrics JSON missing extended keys: {legacy_missing}"


def test_reorganise_preview_trace_json_entries_have_required_fields(
    tmp_path: Path,
    capsys,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    out_path = tmp_path / "cleaned.json"

    code = _cmd_reorganise(
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
            replace_original=False,
            visualize=False,
            metrics=False,
            trace_layout=False,
            debug_layout=True,
        )
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    assert code == 0

    trace_payload = json.loads(
        (tmp_path / "layout_trace.json").read_text(encoding="utf-8")
    )
    assert trace_payload["status"] == "ok"
    assert trace_payload["entries"]
    assert trace_payload["compile"]["ok"] is True

    required_fields = {
        "ref",
        "class_type",
        "role_hint",
        "layout_behavior",
    }
    optional_fields = {
        "section_id",
        "attachment_target",
        "placement_choice",
        "x",
        "y",
        "reason",
    }

    for entry in trace_payload["entries"]:
        entry_keys = set(entry.keys())
        assert required_fields <= entry_keys, (
            f"trace entry missing required field(s): {required_fields - entry_keys}"
        )
        # At least one optional field should be present for nodes that were placed
        if entry.get("x") is not None and entry.get("y") is not None:
            assert "section_id" in entry_keys or "placement_choice" in entry_keys, (
                f"placed node missing placement context: {entry}"
            )


def test_reorganise_preview_reports_explicit_artifact_path_on_write_failure(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    workflow_path = _write_workflow(tmp_path)
    out_path = tmp_path / "cleaned.json"
    original_write_json = reorganise_command._write_json

    def fail_trace_json(path: Path, payload: Any) -> None:
        if path.name == "layout_trace.json":
            raise OSError("disk full")
        original_write_json(path, payload)

    monkeypatch.setattr(reorganise_command, "_write_json", fail_trace_json)

    code = _cmd_reorganise(
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
            replace_original=False,
            visualize=False,
            metrics=False,
            trace_layout=True,
            debug_layout=False,
        )
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "reorganise preview failed:" in captured.err
    assert "layout_trace.json" in captured.err
    assert str(tmp_path / "layout_trace.json") in captured.err


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
            replace_original=False,
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
            replace_original=True,
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
            replace_original=False,
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
            replace_original=True,
        )
    )

    captured = capsys.readouterr()
    assert preview_code == 0
    assert apply_code == 1
    assert "stale preview manifest: source canonical hash changed" in captured.err
    assert workflow_path.read_bytes() == changed_source_bytes
    assert not workflow_path.with_name("workflow.json.bak").exists()


def test_reorganise_apply_requires_explicit_destination_or_replace_original(
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
            replace_original=False,
        )
    )
    capsys.readouterr()

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
            replace_original=False,
        )
    )

    captured = capsys.readouterr()
    assert preview_code == 0
    assert apply_code == 2
    assert "--apply requires --out DESTINATION.json or --replace-original" in captured.err
    assert not workflow_path.with_name("workflow.json.bak").exists()
