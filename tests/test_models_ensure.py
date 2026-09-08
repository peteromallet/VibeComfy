from __future__ import annotations

import argparse
from pathlib import PurePosixPath

from vibecomfy.commands import _model_ensure
from vibecomfy.commands.fetch import _cmd_fetch
from vibecomfy.commands.models import _cmd_models_ensure
from vibecomfy.commands.run import _cmd_run
from vibecomfy.errors import ModelAssetError
from vibecomfy.registry.models_loader import load_registry
from vibecomfy.runtime.session import _model_assets_from_workflow
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_models_ensure_uses_canonical_entries_and_explicit_root(monkeypatch, tmp_path, capsys):
    entries = [{"name": "h3.safetensors", "subdir": "diffusion_models", "url": "https://example/h3"}]
    calls = []
    monkeypatch.setattr(_model_ensure, "entries_for_workflow", lambda ref: entries)
    monkeypatch.setattr(
        _model_ensure.fetch_assets,
        "download_many",
        lambda got, **kwargs: calls.append((got, kwargs)),
    )

    args = argparse.Namespace(
        workflow="shot.py", models_root=tmp_path, dry_run=False, force=True
    )
    assert _cmd_models_ensure(args) == 0
    assert calls == [(entries, {"force": True, "root": tmp_path})]
    assert capsys.readouterr().err == ""


def test_models_ensure_force_verify_bypasses_receipts(monkeypatch, tmp_path):
    entries = [{"name": "h3.safetensors", "subdir": "diffusion_models", "url": "https://example/h3"}]
    calls = []
    monkeypatch.setattr(_model_ensure, "entries_for_workflow", lambda ref: entries)
    monkeypatch.setattr(
        _model_ensure.fetch_assets,
        "download_many",
        lambda got, **kwargs: calls.append((got, kwargs)),
    )

    args = argparse.Namespace(
        workflow="shot.py", models_root=tmp_path, dry_run=False, force=False, force_verify=True
    )
    assert _cmd_models_ensure(args) == 0
    assert calls == [(entries, {"force": False, "root": tmp_path, "force_verify": True})]


def test_h3_registry_rows_are_exact_and_not_generic_core_stage_targets():
    expected = {
        "minimax_h3_ref2va_diffusion": (
            "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors",
            20970379616,
            "9255f52b6677845ad238f20dfaafa94727053694127ab7f255c048f0f9365779",
        ),
        "minimax_h3_ref2va_diffusion_blackwell_nvfp4": (
            "diffusion_models/minimax_h3_ref2va_pruned_nvfp4.safetensors",
            12528636800,
            "c813c5eabd85e275daccbf45e6f8ac4d9d14a1827d425e5be5070c92c60b78ac",
        ),
        "minimax_h3_qwen3vl_text_encoder": (
            "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
            15687142551,
            "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6",
        ),
        "minimax_h3_video_vae": (
            "vae/minimax_h3_video_vae_fp16.safetensors",
            5207808496,
            "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522",
        ),
        "minimax_h3_audio_vae": (
            "vae/minimax_h3_audio_vae_fp32.safetensors",
            605254808,
            "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48",
        ),
        "minimax_h3_fl2v_turbo_8step_lora": (
            "loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
            1956193000,
            "2339acdf19bfe123f46b971ea35d367a84adb85de43627e1eceafa5a5b2b111e",
        ),
    }
    rows = {entry.id: entry for entry in load_registry() if entry.id in expected}
    assert set(rows) == set(expected)
    for entry_id, (target, size, sha) in expected.items():
        entry = rows[entry_id]
        assert entry.targets[0].path == target
        assert entry.source.url.endswith(PurePosixPath(target).name)
        assert (entry.size_bytes, entry.min_size, entry.sha256) == (size, size, sha)
        assert "phase:core" not in entry.tags


def test_fetch_is_compatibility_alias(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "vibecomfy.commands.fetch._reconcile_workflow_models",
        lambda args: calls.append(args) or 7,
    )
    args = argparse.Namespace(workflow="shot.py", dry_run=True, force=False)
    assert _cmd_fetch(args) == 7
    assert calls == [args]


def test_sidecar_registry_resolves_unknown_picker_without_package_mutation(tmp_path):
    workflow_path = tmp_path / "shot.py"
    workflow_path.write_text("# fixture\n", encoding="utf-8")
    sidecar = tmp_path / "shot.models.yaml"
    sidecar.write_text(
        """models:
  - id: local_h3
    source:
      kind: url
      url: https://example.test/h3.safetensors
    min_size: 12
    size_bytes: 12
    sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    targets:
      - node_pack: comfy_core
        path: diffusion_models/h3.safetensors
""",
        encoding="utf-8",
    )
    workflow = VibeWorkflow("shot", WorkflowSource("shot", path=str(workflow_path)))
    workflow.nodes["1"] = VibeNode("1", "UNETLoader", inputs={"unet_name": "h3.safetensors"})
    assets = _model_assets_from_workflow(workflow)
    assert assets == [
        {
            "name": "h3.safetensors",
            "url": "https://example.test/h3.safetensors",
            "subdir": "diffusion_models",
            "sha256": "a" * 64,
            "size_bytes": 12,
            "node_id": "1",
            "class_type": "UNETLoader",
            "field": "unet_name",
            "value": "h3.safetensors",
            "reference_type": "registry-backed",
            "downloadable": True,
        }
    ]


def test_register_writes_adjacent_sidecar(monkeypatch, tmp_path):
    workflow_path = tmp_path / "shot.py"
    workflow = VibeWorkflow("shot", WorkflowSource("shot", path=str(workflow_path)))
    monkeypatch.setattr(_model_ensure, "load_final_workflow", lambda ref: workflow)
    assert _model_ensure.register_workflow_model(
        "shot.py",
        "mystery.safetensors",
        url="https://example.test/mystery.safetensors",
        target_path="diffusion_models/mystery.safetensors",
        sha256="b" * 64,
        size_bytes=42,
    ) == 0
    text = (tmp_path / "shot.models.yaml").read_text(encoding="utf-8")
    assert "https://example.test/mystery.safetensors" in text
    assert "size_bytes: 42" in text


def test_run_unresolved_asset_prints_research_and_exact_reconciliation_commands(monkeypatch, capsys):
    workflow = VibeWorkflow("shot", WorkflowSource("shot"))
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *a, **k: workflow)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *a, **k: (_ for _ in ()).throw(
            ModelAssetError(
                "unresolved workflow model assets: UNETLoader 1.unet_name='mystery.safetensors'",
                next_action="vibecomfy doctor <workflow> --models",
            )
        ),
    )
    args = argparse.Namespace(
        path="shot.py", ready=False, runtime="embedded", server_url=None,
        backend="api", prompt=None, seed=None, steps=None, memory_profile=None,
        ensure_packs=False, ensure_models=None,
    )
    assert _cmd_run(args) == 1
    err = capsys.readouterr().err
    assert "research need" in err
    assert "vibecomfy models register shot.py mystery.safetensors" in err
    assert "--target-path diffusion_models/mystery.safetensors" in err
    assert "vibecomfy models ensure shot.py" in err
