from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

from vibecomfy.commands.run import _cmd_run
from vibecomfy.commands.run import register as register_run


def _args(path: Path, **overrides: object) -> argparse.Namespace:
    values: dict[str, object] = {
        "path": str(path),
        "ready": False,
        "runtime": "embedded",
        "server_url": None,
        "backend": "api",
        "prompt": None,
        "seed": None,
        "steps": None,
        "memory_profile": None,
        "ensure_packs": False,
        "ensure_models": None,
        "runtime_root": None,
        "session": None,
        "keep_warm": False,
        "restart_session": False,
        "download_workers": None,
        "json": False,
        "quiet_schema_degradation": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _bundle(source: Path) -> SimpleNamespace:
    workflow = SimpleNamespace(
        id="fixture",
        source=SimpleNamespace(path=str(source)),
        inputs={},
    )
    return SimpleNamespace(
        workflow=workflow,
        require_canonical_authority=lambda *_args, **_kwargs: None,
        compile=lambda **_kwargs: object(),
    )


def test_local_blockers_are_combined_before_runtime_side_effects(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "from vibecomfy.templates import ModelAsset\n"
        "MODELS = {'denoiser': ModelAsset(filename='denoiser.safetensors', url=None, subdir='checkpoints')}\n"
        "READY_REQUIREMENTS = {'custom_node_refs': [{'slug': 'example-pack', 'url': None}]}\n"
        "def build():\n"
        "    return node('1', 'UnaccountedNode')\n",
        encoding="utf-8",
    )
    bundle = _bundle(source)
    calls: list[str] = []
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *_a, **_k: bundle)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.prepare_workflow",
        lambda *_a, **_k: calls.append("prepare"),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *_a, **_k: calls.append("run"),
    )

    assert _cmd_run(_args(source)) == 1
    error = capsys.readouterr().err
    assert "Run blocked: dependencies unresolved" in error
    assert "MODELS[\"denoiser\"].url" in error
    assert "READY_REQUIREMENTS.custom_node_refs[0].url" in error
    assert "class_not_accounted_for" not in error
    assert "UnaccountedNode" in error
    assert calls == []
    assert "url=None" in source.read_text(encoding="utf-8")


def test_manual_repair_diagnostics_block_before_any_run_side_effect(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    source = tmp_path / "dynamic-workflow.py"
    source.write_text(
        "MODELS = load_models()\n"
        "READY_REQUIREMENTS = {'models': load_requirements()}\n"
        "def build():\n"
        "    return None\n",
        encoding="utf-8",
    )
    bundle = _bundle(source)
    calls: list[str] = []
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *_a, **_k: bundle)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.prepare_workflow",
        lambda *_a, **_k: calls.append("prepare"),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *_a, **_k: calls.append("run"),
    )

    assert _cmd_run(_args(source)) == 1
    error = capsys.readouterr().err
    assert "MODELS" in error
    assert "READY_REQUIREMENTS.models" in error
    assert "manual_repair_required" not in error
    assert calls == []


def test_resolved_local_source_reaches_existing_preparation_and_execution(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "workflow.py"
    source.write_text(
        "from vibecomfy.templates import ModelAsset\n"
        "MODELS = {'denoiser': ModelAsset(filename='denoiser.safetensors', url='https://example.test/denoiser', subdir='checkpoints')}\n"
        "def build():\n"
        "    return None\n",
        encoding="utf-8",
    )
    bundle = _bundle(source)
    calls: list[str] = []
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *_a, **_k: bundle)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.prepare_workflow",
        lambda *_a, **_k: calls.append("prepare") or object(),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda *_a, **_k: calls.append("run")
        or SimpleNamespace(run_id="run", prompt_id="prompt", metadata_path="m", log_path="l"),
    )

    assert _cmd_run(_args(source)) == 0
    assert calls == ["prepare", "run"]


def test_explicit_remote_run_skips_reconciliation_and_local_preparation(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "workflow.py"
    original = (
        "from vibecomfy.templates import ModelAsset\n"
        "MODELS = {'denoiser': ModelAsset(filename='denoiser.safetensors', url=None, subdir='checkpoints')}\n"
        "def build():\n"
        "    return None\n"
    )
    source.write_text(original, encoding="utf-8")
    bundle = _bundle(source)
    calls: list[str] = []
    monkeypatch.setattr("vibecomfy.commands.run.load_bundle", lambda *_a, **_k: bundle)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "vibecomfy.commands.run.reconcile_ready_template_file",
        lambda *_a, **_k: calls.append("reconcile"),
    )
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_sync",
        lambda *_a, **_k: calls.append("run")
        or SimpleNamespace(run_id="run", prompt_id="prompt", metadata_path="m", log_path="l"),
    )

    assert _cmd_run(_args(source, runtime="server", server_url="http://remote.test")) == 0
    assert calls == ["run"]
    assert source.read_text(encoding="utf-8") == original


def test_run_parser_has_no_preparation_declaration_flag() -> None:
    parser = argparse.ArgumentParser()
    register_run(parser.add_subparsers(dest="command"))
    help_text = parser.format_help()
    assert "--prepare" not in help_text
    assert "--dry-run" not in help_text
