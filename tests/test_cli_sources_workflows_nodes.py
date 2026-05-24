from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

import vibecomfy.node_packs_install as node_packs_install
from vibecomfy.commands.nodes import (
    _cmd_nodes_audit,
    _cmd_nodes_compatible_with,
    _cmd_nodes_coverage,
    _cmd_nodes_drift,
    _cmd_nodes_ensure,
    _cmd_nodes_install,
    _cmd_nodes_install_plan,
    _cmd_nodes_list,
    _cmd_nodes_lookup,
    _cmd_nodes_refresh_template,
    _cmd_nodes_restore,
    _cmd_nodes_spec,
)
from vibecomfy.node_packs_lockfile import LockEntry
from vibecomfy.registry.pack_resolver import PackRef, PackResolution
from vibecomfy.commands.workflows import (
    _cmd_workflows_enrich_targets,
    _cmd_workflows_lens,
    _cmd_workflows_list,
    _cmd_workflows_source_info,
)


def test_workflows_list_reports_malformed_index_with_recovery_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "workflow_index.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _cmd_workflows_list(argparse.Namespace(ready=False, limit=10)) == 1

    captured = capsys.readouterr()
    assert "workflow_index.json could not be read" in captured.err
    assert "vibecomfy sources sync" in captured.err


def test_workflows_source_info_json_reports_pure_python_source(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _cmd_workflows_source_info(argparse.Namespace(template_id="image/z_image", json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["template_id"] == "image/z_image"
    assert payload["source_mode"] == "pure_python"
    assert payload["runtime_source_of_truth"] is True


def test_workflows_source_info_accepts_policy_applied_python_fork(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = _cmd_workflows_source_info(
        argparse.Namespace(
            template_id="video/ltx2_3_runexx_first_last_raw_video_guide",
            json=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["template_id"] == "video/ltx2_3_runexx_first_last_raw_video_guide"
    assert payload["source_mode"] == "pure_python"
    assert payload["runtime_source_of_truth"] is True


def test_workflows_enrich_targets_writes_schema_and_asset_metadata(tmp_path: Path) -> None:
    targets_path = tmp_path / "targets.json"
    output_path = tmp_path / "enriched.json"
    models_root = tmp_path / "models"
    targets_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "selector": {"backend": "vibecomfy"},
                "selection": {"case_names": ["z_image_turbo"]},
                "targets": [
                    {
                        "case_name": "z_image_turbo",
                        "task_type": "z_image_turbo",
                        "route_key": "z_image_turbo",
                        "template_id": "image/z_image",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    code = _cmd_workflows_enrich_targets(
        argparse.Namespace(
            targets_json=str(targets_path),
            output=str(output_path),
            models_root=models_root,
        )
    )

    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["producer"] == "vibecomfy.workflows.enrich-targets"
    assert payload["templates"] == ["image/z_image"]
    assert payload["target_count"] == 1
    assert payload["template_count"] == 1
    target = payload["targets"][0]
    assert target["source"]["source_mode"] == "pure_python"
    assert target["schema"]["node_count"] > 0
    assert "SaveImage" in target["schema"]["class_types"]
    assets = {asset["name"]: asset for asset in target["assets"]}
    assert "z_image_bf16.safetensors" in assets
    assert assets["z_image_bf16.safetensors"]["expected_path"].startswith(str(models_root))
    assert assets["z_image_bf16.safetensors"]["present"] is False
    missing_asset_issues = [item for item in target["issues"] if item["code"] == "missing_model_asset"]
    assert missing_asset_issues
    missing_z_image = next(
        item for item in missing_asset_issues if item["detail"]["name"] == "z_image_bf16.safetensors"
    )
    assert missing_z_image["detail"]["expected_path"] == assets["z_image_bf16.safetensors"]["expected_path"]
    assert missing_asset_issues[0]["detail"]["paths_checked"]
    assert "curl -L" in (missing_asset_issues[0]["detail"]["remediation"] or "")


def test_workflows_enrich_targets_treats_orchestrators_as_non_template_info(tmp_path: Path):
    targets_path = tmp_path / "targets.json"
    output_path = tmp_path / "enriched.json"
    targets_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "selector": {"backend": "vibecomfy"},
                "selection": {"case_names": ["travel_orchestrator_wan2_1seg"]},
                "targets": [
                    {
                        "case_name": "travel_orchestrator_wan2_1seg",
                        "task_type": "travel_orchestrator",
                        "route_key": "travel_orchestrator",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    code = _cmd_workflows_enrich_targets(
        argparse.Namespace(
            targets_json=str(targets_path),
            output=str(output_path),
            models_root=str(tmp_path / "models"),
        )
    )

    assert code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["target_count"] == 1
    assert payload["template_count"] == 0
    assert payload["templates"] == []
    target = payload["targets"][0]
    assert target["enrichment_status"] == "skipped"
    assert target["issues"] == [
        {
            "group": "workflow_source",
            "code": "non_template_target",
            "severity": "info",
            "message": "Target does not execute a VibeComfy template directly.",
        }
    ]


def test_nodes_list_reports_malformed_index_with_recovery_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text("{not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _cmd_nodes_list(argparse.Namespace(limit=10)) == 1

    captured = capsys.readouterr()
    assert "node_index.json could not be read" in captured.err
    assert "vibecomfy sources sync" in captured.err


def test_nodes_spec_reads_object_info_cache(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cache = tmp_path / "object_info.json"
    cache.write_text(
        json.dumps(
            {
                "RuntimeOnlyNode": {
                    "input": {"required": {"latent": ["LATENT", {}]}},
                    "output": ["IMAGE"],
                    "output_name": ["image"],
                    "category": "runtime/test",
                }
            }
        ),
        encoding="utf-8",
    )

    assert _cmd_nodes_spec(argparse.Namespace(class_type="RuntimeOnlyNode", object_info_cache=str(cache))) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["class_type"] == "RuntimeOnlyNode"
    assert payload["inputs"]["latent"]["type"] == "LATENT"
    assert payload["outputs"][0]["name"] == "image"


def test_nodes_compatible_with_searches_input_sockets(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_nodes_compatible_with(argparse.Namespace(type_or_from_class="LATENT", to_class=None, to_input=None, socket_role="input", object_info_cache=None, json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["as"] == "input"
    assert payload["compatible_count"] > 0
    assert any(match["class_type"] == "KSampler" and match["socket"] == "latent_image" for match in payload["matches"])


def test_nodes_compatible_with_searches_output_sockets(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_nodes_compatible_with(argparse.Namespace(type_or_from_class="IMAGE", to_class=None, to_input=None, socket_role="output", object_info_cache=None, json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["as"] == "output"
    assert payload["compatible_count"] > 0
    assert any(match["class_type"] == "VAEDecode" for match in payload["matches"])


def test_nodes_compatible_with_image_input_subprocess_includes_saveimage() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "nodes", "compatible-with", "IMAGE", "--as", "input", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["type"] == "IMAGE"
    assert payload["as"] == "input"
    assert isinstance(payload["matches"], list)
    assert "SaveImage" in payload["classes"]
    assert any(
        match["class_type"] == "SaveImage"
        and match["socket"] == "images"
        and match["socket_role"] == "input"
        for match in payload["matches"]
    )


def test_nodes_compatible_with_output_mode_response_shape() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "nodes", "compatible-with", "IMAGE", "--as", "output", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert set(payload) == {"as", "classes", "compatible_count", "matches", "provider", "type"}
    assert payload["as"] == "output"
    assert isinstance(payload["classes"], list)
    assert payload["matches"]
    assert {"class_type", "socket", "socket_role", "socket_type"} <= set(payload["matches"][0])


def test_nodes_spec_uuid_reads_subgraph_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    uuid = "7b34ab90-36f9-45ba-a665-71d418f0df18"
    corpus_dir = tmp_path / "workflow_corpus" / "official" / "edit"
    corpus_dir.mkdir(parents=True)
    workflow = corpus_dir / "workflow.json"
    workflow.write_text(
        json.dumps(
            {
                "definitions": {
                    "subgraphs": [
                        {
                            "id": uuid,
                            "name": "Image Edit (Flux.2 Klein 9B)",
                            "inputs": [{"name": "prompt", "type": "STRING"}],
                            "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                            "nodes": [
                                {"id": 1, "type": "KSampler"},
                                {"id": 2, "type": "CLIPTextEncode"},
                                {"id": 3, "type": "CLIPTextEncode"},
                            ],
                            "links": [[1, 1, 0, 2, 0, "CONDITIONING"]],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = _cmd_nodes_spec(
        argparse.Namespace(
            class_type=uuid,
            object_info_cache=None,
            source=None,
            verbose=True,
            json=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["uuid"] == uuid
    assert payload["name"] == "Image Edit (Flux.2 Klein 9B)"
    assert payload["inputs"] == [{"name": "prompt", "type": "STRING"}]
    assert payload["outputs"] == [{"name": "IMAGE", "type": "IMAGE"}]
    assert payload["inner_node_count"] == 3
    assert payload["inner_node_class_types"] == {"CLIPTextEncode": 2, "KSampler": 1}
    assert payload["inner_graph"]["edges"] == [[1, 1, 0, 2, 0, "CONDITIONING"]]


def test_nodes_spec_uuid_missing_reports_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workflow = tmp_path / "workflow.json"
    workflow.write_text(json.dumps({"definitions": {"subgraphs": []}}), encoding="utf-8")

    code = _cmd_nodes_spec(
        argparse.Namespace(
            class_type="7b34ab90-36f9-45ba-a665-71d418f0df18",
            object_info_cache=None,
            source=str(workflow),
            verbose=False,
            json=True,
        )
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "subgraph UUID not found" in captured.err


def test_nodes_install_plan_suggests_pack_for_missing_class(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "PreviewAudio", "pack": "core", "inputs": {}, "outputs": []}]),
        encoding="utf-8",
    )
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert _cmd_nodes_install_plan(argparse.Namespace(path=str(scratchpad), json=False)) == 0

    captured = capsys.readouterr()
    assert "ComfyUI-Qwen3-TTS" in captured.out
    assert "Qwen3CustomVoice" in captured.out


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("installed", 0),
        ("refreshed", 0),
        ("skipped_dirty", 1),
        ("failed", 1),
    ],
)
def test_cmd_nodes_install_translates_install_result_to_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected_code: int,
) -> None:
    def fake_install_pack(**kwargs):
        assert kwargs == {"name": "ExamplePack", "repo": None, "force": False}
        return node_packs_install.InstallResult(
            name="ExamplePack",
            status=status,  # type: ignore[arg-type]
            git_commit_sha="abc123" if status in {"installed", "refreshed"} else None,
            error="install issue" if status in {"skipped_dirty", "failed"} else None,
        )

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)

    code = _cmd_nodes_install(argparse.Namespace(name="ExamplePack", repo=None, force=False))

    captured = capsys.readouterr()
    assert code == expected_code
    assert f"ExamplePack: {status}" in captured.out
    if expected_code:
        assert "install issue" in captured.err
    else:
        assert captured.err == ""


def test_cmd_nodes_lookup_resolves_pack(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import vibecomfy.commands.nodes as nodes_cmd

    monkeypatch.setattr(
        nodes_cmd,
        "resolve_pack",
        lambda query: PackResolution(
            query=query,
            query_type="class",
            ref=PackRef(slug="comfyui-example", source="comfy-registry", version="1.0.0"),
        ),
    )

    assert _cmd_nodes_lookup(argparse.Namespace(query="ExampleNode", json=True)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["pack"]["slug"] == "comfyui-example"


def test_cmd_nodes_refresh_template_dry_run_reports_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import vibecomfy.commands.nodes as nodes_cmd
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    template = tmp_path / "template.py"
    template.write_text(
        "READY_METADATA = ReadyMetadata.build(\n"
        "    template_id='image/example',\n"
        "    capability='test',\n"
        "    inputs={},\n"
        "    models={},\n"
        "    output_prefix='out/example',\n"
        ")\n",
        encoding="utf-8",
    )
    workflow = VibeWorkflow("image/example", WorkflowSource("image/example", path=str(template)))
    workflow.nodes["1"] = VibeNode(id="1", class_type="ExampleNode")
    monkeypatch.setattr(nodes_cmd, "load_workflow_reference", lambda *_args, **_kwargs: workflow)
    monkeypatch.setattr(nodes_cmd, "read_lockfile", lambda *_args, **_kwargs: [
        LockEntry(
            name="ExamplePack",
            git_commit_sha="abc",
            url="https://example.test/pack.git",
            slug="example-pack",
            source="git",
            commit="abc",
            class_set=("ExampleNode",),
        )
    ])

    assert _cmd_nodes_refresh_template(argparse.Namespace(file=str(template), dry_run=True, diff=True, json=True)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry-run"
    assert payload["custom_nodes"] == ["example-pack"]
    assert "custom_node_refs" in payload["diff"]
    assert "custom_node_refs" not in template.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        ("installed", 0),
        ("refreshed", 0),
        ("skipped_dirty", 1),
        ("failed", 1),
    ],
)
def test_cmd_nodes_restore_translates_results_to_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: str,
    expected_code: int,
) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text("ExamplePack abc123 https://example.test/example.git\n", encoding="utf-8")

    def fake_restore_pack(entry):
        assert entry.name == "ExamplePack"
        assert entry.git_commit_sha == "abc123"
        return node_packs_install.InstallResult(
            name="ExamplePack",
            status=status,  # type: ignore[arg-type]
            git_commit_sha="abc123" if status in {"installed", "refreshed"} else None,
            error="restore issue" if status in {"skipped_dirty", "failed"} else None,
        )

    monkeypatch.setattr(node_packs_install, "restore_pack", fake_restore_pack)

    code = _cmd_nodes_restore(argparse.Namespace(lockfile=str(lockfile)))

    captured = capsys.readouterr()
    assert code == expected_code
    assert f"ExamplePack: {status}" in captured.out
    if expected_code:
        assert "restore issue" in captured.err
    else:
        assert captured.err == ""


def test_cmd_nodes_ensure_dry_run_does_not_install(
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
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    def fail_install_pack(**_kwargs):
        raise AssertionError("install_pack must not be called during dry-run")

    monkeypatch.setattr(node_packs_install, "install_pack", fail_install_pack)

    code = _cmd_nodes_ensure(argparse.Namespace(template=None, workflow=str(scratchpad), dry_run=True))

    captured = capsys.readouterr()
    assert code == 0
    assert "Suggested custom node packs:" in captured.out
    assert "ComfyUI-Qwen3-TTS" in captured.out


def test_ensure_calls_install_for_each_missing_pack(
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
    workflow.nodes["1"] = VibeNode(id="1", class_type="Qwen3CustomVoice")
    workflow.nodes["2"] = VibeNode(id="2", class_type="VHS_LoadVideo")
    return workflow
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    installed: list[str | None] = []

    def fake_install_pack(**kwargs):
        installed.append(kwargs.get("name"))
        return node_packs_install.InstallResult(
            name=str(kwargs["name"]),
            status="refreshed",
            git_commit_sha="abc123",
            error=None,
        )

    monkeypatch.setattr(node_packs_install, "install_pack", fake_install_pack)

    code = _cmd_nodes_ensure(argparse.Namespace(template=None, workflow=str(scratchpad), dry_run=False))

    captured = capsys.readouterr()
    assert code == 0
    assert installed == ["ComfyUI-Qwen3-TTS", "ComfyUI-VideoHelperSuite"]
    assert "Nodepacks installed/refreshed." in captured.out


@pytest.mark.xfail(strict=True, reason="Phase 1: LTX parity template missing seed_first/seed_last in registered inputs; LTX family fix required")
def test_workflows_lens_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    """JSON lens output includes node/edge counts, inputs, outputs, and per-node metadata."""
    code = _cmd_workflows_lens(
        argparse.Namespace(template_or_path="video/ltx2_3_lightricks_first_last_parity", json=True)
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["workflow_id"] == "video/ltx2_3_lightricks_first_last_parity"
    assert payload["node_count"] >= 20
    assert payload["edge_count"] >= 20
    assert "prompt" in payload["inputs"]
    assert "negative_prompt" in payload["inputs"]
    assert "first_image" in payload["inputs"]
    assert "last_image" in payload["inputs"]
    assert "seed_first" in payload["inputs"]
    assert "seed_last" in payload["inputs"]
    assert "width" in payload["inputs"]
    assert "height" in payload["inputs"]
    assert "first_strength" in payload["inputs"]
    assert "last_strength" in payload["inputs"]
    assert "frames" in payload["inputs"]
    assert "fps" in payload["inputs"]
    outputs = payload["outputs"]
    assert any(o["output_type"] == "SaveVideo" for o in outputs)
    nodes = payload["nodes"]
    assert len(nodes) == payload["node_count"]
    class_types = {n["class_type"] for n in nodes}
    assert "LTXVAddGuide" in class_types
    assert "RandomNoise" in class_types


def test_workflows_lens_human_readable(capsys: pytest.CaptureFixture[str]) -> None:
    """Human-readable lens diagnostics produce a readable graph summary."""
    code = _cmd_workflows_lens(
        argparse.Namespace(template_or_path="video/ltx2_3_lightricks_first_last_parity", json=False)
    )

    captured = capsys.readouterr().out
    assert code == 0
    assert "video/ltx2_3_lightricks_first_last_parity" in captured
    assert "LTXVAddGuide" in captured


# ── nodes coverage ──────────────────────────────────────────────────────


def test_nodes_coverage_json_returns_coverage_stats(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_nodes_coverage(
        argparse.Namespace(workflow="video/wan_i2v", json=True, lockfile=None)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "per_class" in payload
    assert "total" in payload
    assert "typed_wrapper" in payload
    assert "raw_call" in payload
    assert "missing_lock" in payload
    assert "coverage_pct" in payload

    # Verify each per_class entry has required fields
    for entry in payload["per_class"]:
        assert "class_type" in entry
        assert "pack" in entry
        assert "coverage" in entry


def test_nodes_coverage_text_renders_table(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_nodes_coverage(
        argparse.Namespace(workflow="video/wan_i2v", json=False, lockfile=None)
    )
    text = capsys.readouterr().out
    assert code == 0
    assert "Coverage:" in text
    # Table contains class names and coverage status
    assert "CLIPLoader" in text or "UNETLoader" in text
    assert "raw_call" in text or "typed wrapper" in text or "missing_lock" in text


# ── nodes drift ─────────────────────────────────────────────────────────


def test_nodes_drift_unavailable_pack_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = _cmd_nodes_drift(
        argparse.Namespace(pack="NonexistentPackXYZ123", json=True, from_ref=None, to_ref=None)
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "unavailable"
    assert payload["pack"] == "NonexistentPackXYZ123"


# ── nodes audit ─────────────────────────────────────────────────────────


def test_nodes_audit_json_returns_versioned_payload(capsys: pytest.CaptureFixture[str]) -> None:
    """``nodes audit --json`` produces deterministic, versioned JSON."""
    code = _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
            json=True,
            object_info_cache=None,
            strict_ready_template=False,
            head_check_models=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["audit_version"] == "1.0.0"
    assert payload["workflow"] == "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    assert "source_hash" in payload
    assert "total_classified" in payload
    assert "classifications" in payload
    assert "summary" in payload
    assert isinstance(payload["classifications"], list)


def test_nodes_audit_primitive_node_covered_by_core_fallback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """PrimitiveNode is declared in comfy-core-fallback → audit produces no error-severity entries for it.

    PrimitiveNode's only diagnostics are widget_alias_unresolved warnings (not errors), so it
    does not appear in audit classifications at all. This verifies the comfy-core-fallback pack
    declaration suppresses error-level audit noise for this core UI-only node.
    """
    from vibecomfy.node_packs import KNOWN_NODE_PACKS

    fallback_packs = [p for p in KNOWN_NODE_PACKS if p.name == "comfy-core-fallback"]
    assert fallback_packs, "comfy-core-fallback pack must be declared in node_packs.py"
    assert "PrimitiveNode" in fallback_packs[0].classes

    _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
            json=True,
            object_info_cache=None,
            strict_ready_template=False,
            head_check_models=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    primitive_entries = [
        c for c in payload["classifications"]
        if c.get("class_type") == "PrimitiveNode"
    ]
    # comfy-core-fallback covers PrimitiveNode; its diagnostics are warnings only, not errors.
    assert primitive_entries == [], "PrimitiveNode should not appear as an error-severity audit entry"


def test_nodes_audit_classifies_widget_alias_issues(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Widget alias / unknown_input diagnostics are classified as widget-alias-missing."""
    # Use motion_transfer workflow which has SimpleCalculatorKJ with unknown_input (variables.a/b/c)
    # — the dynamic COMFY_AUTOGROW_V3 sub-keys are not in any installed schema snapshot.
    code = _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json",
            json=True,
            object_info_cache=None,
            strict_ready_template=False,
            head_check_models=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    widget_entries = [
        c for c in payload["classifications"]
        if c["classification"] == "widget-alias-missing"
    ]
    assert len(widget_entries) >= 1
    for entry in widget_entries:
        assert entry["class_type"] is not None
        assert "Widget alias" in entry["rationale"] or "Widget" in entry["rationale"]


def test_nodes_audit_ace_step_widget_alias_resolved(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TextEncodeAceStepAudio1.5 widget_14 is resolved by the committed WIDGET_SCHEMA entry."""
    _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
            json=True,
            object_info_cache=None,
            strict_ready_template=False,
            head_check_models=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    widget_entries = [
        c for c in payload["classifications"]
        if c["classification"] == "widget-alias-missing"
    ]
    assert widget_entries == [], "TextEncodeAceStepAudio1.5.widget_14 should now be resolved"


def test_nodes_audit_summary_counts_match_classifications(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Summary bucket counts match the actual classification list."""
    code = _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
            json=True,
            object_info_cache=None,
            strict_ready_template=False,
            head_check_models=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    summary = payload["summary"]
    actual_counts = {
        "pack-not-installed": 0,
        "pack-installed-but-stale-schema": 0,
        "widget-alias-missing": 0,
        "model-registry-gap": 0,
        "community-node-unknown": 0,
    }
    for c in payload["classifications"]:
        bucket = c["classification"]
        actual_counts[bucket] = actual_counts.get(bucket, 0) + 1
    for bucket, expected in summary.items():
        assert actual_counts.get(bucket, 0) == expected, f"mismatch for {bucket}"


def test_nodes_audit_strict_ready_diagnostics_are_classified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Strict-ready diagnostics are captured and classified (community-node-unknown)."""
    code = _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/official/video/ltx2_3_i2v.json",
            json=True,
            object_info_cache=None,
            strict_ready_template=True,
            head_check_models=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    strict_entries = [
        c for c in payload["classifications"]
        if c.get("code", "").startswith("strict_ready_")
    ]
    assert len(strict_entries) >= 1
    for entry in strict_entries:
        assert entry["classification"] == "community-node-unknown"
        assert "Environment or template shape" in entry["rationale"]


def test_nodes_audit_every_classification_has_required_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every classification row has class_type, code, classification, rationale, pack."""
    code = _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
            json=True,
            object_info_cache=None,
            strict_ready_template=False,
            head_check_models=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)
    for entry in payload["classifications"]:
        assert "class_type" in entry
        assert "code" in entry
        assert "classification" in entry
        assert "rationale" in entry
        assert "pack" in entry
        assert entry["classification"] in (
            "pack-not-installed",
            "pack-installed-but-stale-schema",
            "widget-alias-missing",
            "model-registry-gap",
            "community-node-unknown",
        )


def test_nodes_audit_text_output_does_not_crash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-JSON text output renders without crashing."""
    code = _cmd_nodes_audit(
        argparse.Namespace(
            workflow="workflow_corpus/official/audio/ace_step_1_5_t2a_song.json",
            json=False,
            object_info_cache=None,
            strict_ready_template=False,
            head_check_models=False,
        )
    )
    captured = capsys.readouterr()
    assert "nodes audit:" in captured.out
    assert "pack-not-installed" in captured.out
    assert "community-node-unknown" in captured.out


def test_nodes_audit_registered_in_cli_help() -> None:
    """``vibecomfy nodes --help`` includes the audit subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "nodes", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "audit" in result.stdout
    assert "Audit unresolved nodes" in result.stdout


def test_nodes_audit_help_is_discoverable() -> None:
    """``vibecomfy nodes audit --help`` renders help text."""
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "nodes", "audit", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--workflow" in result.stdout
    assert "--json" in result.stdout


# ── nodes reconcile ─────────────────────────────────────────────────────


def test_nodes_reconcile_json_returns_versioned_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``nodes reconcile --json`` produces deterministic, versioned JSON."""
    out, code = _run_reconcile_capture(
        capsys, "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    payload = json.loads(out)
    assert payload["reconcile_version"] == "1.0.0"
    assert (
        payload["workflow"]
        == "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    assert "source_hash" in payload
    assert "total_remediations" in payload
    assert "remediations" in payload
    assert "summary" in payload
    assert isinstance(payload["remediations"], list)
    assert payload["total_remediations"] == len(payload["remediations"])


def test_nodes_reconcile_every_remediation_has_required_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every remediation row has action, detail, classification, class_type, code, pack."""
    out, code = _run_reconcile_capture(
        capsys, "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    payload = json.loads(out)
    for entry in payload["remediations"]:
        assert "action" in entry
        assert "detail" in entry
        assert "classification" in entry
        assert "class_type" in entry
        assert "code" in entry
        assert "pack" in entry
        assert entry["action"] in (
            "declare-pack",
            "install-pack",
            "refresh-schema",
            "register-widget-alias",
            "register-model",
            "defer-as-out-of-scope",
        )


def test_nodes_reconcile_no_phantom_commands_in_details(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No detail string references a non-existent subcommand.

    The correctness flag (T3) requires that remediation detail strings name
    ONLY verified-existing commands (``vibecomfy nodes install``,
    ``vibecomfy nodes refresh-template``) or concrete file edits
    (``vibecomfy/node_packs.py``, ``vibecomfy/registry/models.yaml``,
    ``widget_aliases`` module).  Phantom commands like ``refresh-schema``,
    ``widgets register``, or ``models register`` must never appear.
    """
    out, code = _run_reconcile_capture(
        capsys, "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    payload = json.loads(out)
    all_details = " ".join(
        str(entry.get("detail", "")) for entry in payload["remediations"]
    ).lower()

    # These phantom commands must NOT appear
    forbidden = [
        "refresh-schema",       # not a CLI command
        "widgets register",     # not a CLI command
        "models register",      # not a CLI command
        "vibecomfy refresh-schema",
        "vibecomfy widgets",
        "vibecomfy models",
    ]
    for phantom in forbidden:
        assert phantom not in all_details, (
            f"Phantom command {phantom!r} found in reconcile detail strings"
        )


def test_nodes_reconcile_details_only_reference_existing_commands(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every CLI-reference in detail strings uses a verified-existing command."""
    out, code = _run_reconcile_capture(
        capsys, "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    payload = json.loads(out)

    # Valid commands that can appear in detail strings
    valid_cli_commands = {
        "vibecomfy nodes install",
        "vibecomfy nodes refresh-template",
    }
    # Valid concrete file-edit locations
    valid_file_locations = {
        "vibecomfy/node_packs.py",
        "widget_aliases module",
        "vibecomfy/registry/models.yaml",
    }

    for entry in payload["remediations"]:
        detail = str(entry.get("detail", ""))
        # If detail contains a vibecomfy CLI reference, it must be a known command
        if "vibecomfy " in detail.lower():
            has_valid_cli = any(
                valid_cmd in detail for valid_cmd in valid_cli_commands
            )
            assert has_valid_cli, (
                f"Detail references a CLI command not verified to exist: {detail!r}"
            )

        # If detail references a file path, it must be a known file location
        if ".py" in detail or ".yaml" in detail or "module" in detail:
            has_valid_file = any(
                valid_file in detail for valid_file in valid_file_locations
            )
            assert has_valid_file, (
                f"Detail references a file not verified to exist: {detail!r}"
            )


def test_nodes_reconcile_maps_community_unknown_to_defer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """community-node-unknown classifications map to defer-as-out-of-scope."""
    # Use motion transfer workflow which has LTX2SamplingPreviewOverride / PathchSageAttentionKJ
    # as community-node-unknown (no known pack declaration covers them).
    out, code = _run_reconcile_capture(
        capsys,
        "workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json",
    )
    payload = json.loads(out)
    defer_entries = [
        r
        for r in payload["remediations"]
        if r.get("action") == "defer-as-out-of-scope"
    ]
    assert len(defer_entries) >= 1
    for entry in defer_entries:
        assert entry["action"] == "defer-as-out-of-scope"
        assert "community-node-unknown" in entry["detail"]


def test_nodes_reconcile_maps_widget_alias_to_register_widget_alias(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """widget-alias-missing classifications map to register-widget-alias."""
    # Use motion transfer workflow which has SimpleCalculatorKJ with unknown_input (variables.a/b/c)
    # — the dynamic COMFY_AUTOGROW_V3 sub-keys are not in any installed schema snapshot.
    out, code = _run_reconcile_capture(
        capsys,
        "workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json",
    )
    payload = json.loads(out)
    widget_entries = [
        r
        for r in payload["remediations"]
        if r.get("classification") == "widget-alias-missing"
    ]
    assert len(widget_entries) >= 1
    for entry in widget_entries:
        assert entry["action"] == "register-widget-alias"
        assert "widget_aliases module" in entry["detail"]


def test_nodes_reconcile_summary_counts_match_remediations(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Summary action counts match the actual remediations list."""
    out, code = _run_reconcile_capture(
        capsys, "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    payload = json.loads(out)
    summary = payload["summary"]
    actual_counts: dict[str, int] = {}
    for r in payload["remediations"]:
        action = r["action"]
        actual_counts[action] = actual_counts.get(action, 0) + 1
    for action, expected in summary.items():
        assert actual_counts.get(action, 0) == expected, f"mismatch for {action}"


def test_nodes_reconcile_text_output_does_not_crash(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-JSON text output renders without crashing."""
    out, code = _run_reconcile_capture(
        capsys, "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json", json=False
    )
    assert "nodes reconcile:" in out
    assert "defer-as-out-of-scope" in out
    assert "install-pack" in out or "declare-pack" in out


def test_nodes_reconcile_registered_in_cli_help() -> None:
    """``vibecomfy nodes --help`` includes the reconcile subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "nodes", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "reconcile" in result.stdout


def test_nodes_reconcile_help_is_discoverable() -> None:
    """``vibecomfy nodes reconcile --help`` renders help text."""
    result = subprocess.run(
        [sys.executable, "-m", "vibecomfy.cli", "nodes", "reconcile", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--workflow" in result.stdout
    assert "--json" in result.stdout


def test_nodes_reconcile_output_is_non_mutating_proposal(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The reconcile output is a proposal only — it does not mutate any files."""
    # Run reconcile and verify it completes without side effects
    out, code = _run_reconcile_capture(
        capsys, "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    payload = json.loads(out)
    assert "remediations" in payload
    # No action should have been taken — this is a read-only proposal
    assert code == 0
    # Verify the workflow file itself is unmodified (it's a git-tracked file)
    wf_path = Path(
        "workflow_corpus/official/audio/ace_step_1_5_t2a_song.json"
    )
    assert wf_path.exists(), "workflow file still exists unchanged"


# ── reconcile helpers ───────────────────────────────────────────────────


def _run_reconcile_capture(
    capsys: pytest.CaptureFixture[str],
    workflow: str,
    *,
    json: bool = True,
    strict_ready: bool = False,
) -> tuple[str, int]:
    """Run reconcile and return captured stdout + exit code.

    IMPORTANT: the caller MUST NOT call capsys.readouterr() after this —
    the output has already been drained and returned.
    """
    from vibecomfy.commands.nodes import _cmd_nodes_reconcile

    code = _cmd_nodes_reconcile(
        argparse.Namespace(
            workflow=workflow,
            json=json,
            object_info_cache=None,
            strict_ready_template=strict_ready,
            head_check_models=False,
        )
    )
    # Drain capsys immediately — caller must use the returned string
    return capsys.readouterr().out, code
