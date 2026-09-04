from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import vibecomfy.commands.nodes as nodes_cmd
import vibecomfy.node_packs as node_packs
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowRequirements, WorkflowSource


class _Provider:
    def __init__(self, classes: set[str] | None = None) -> None:
        self._classes = classes or set()

    def schemas(self) -> dict[str, None]:
        return {name: None for name in self._classes}

    def get_schema(self, class_type: str) -> None:
        return None


def _workflow(*, class_type: str = "KSampler", metadata: dict | None = None, requirements=None) -> VibeWorkflow:
    return VibeWorkflow(
        id="fixture",
        source=WorkflowSource(id="fixture"),
        nodes={"1": VibeNode(id="1", class_type=class_type)},
        metadata=metadata or {},
        requirements=requirements or WorkflowRequirements(),
    )


def _args(tmp_path: Path, **overrides) -> argparse.Namespace:
    values = {
        "workflow": str(tmp_path / "workflow.json"),
        "json": True,
        "lockfile": str(tmp_path / "custom_nodes.lock"),
        "registry": str(tmp_path / "models.yaml"),
        "models_root": str(tmp_path / "models"),
        "server_url": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


@pytest.fixture()
def isolated_reconcile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text("", encoding="utf-8")
    monkeypatch.setattr(nodes_cmd, "get_authoring_schema_provider", lambda **_: _Provider({"KSampler"}))
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(nodes_cmd, "load_workflow_reference", lambda *_args, **_kwargs: _workflow())
    from vibecomfy.registry import models_loader

    monkeypatch.setattr(models_loader, "load_registry", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(nodes_cmd, "_reconcile_model_references", lambda _workflow: [])
    return tmp_path


def test_reconcile_clean_report_has_exact_shape_and_is_byte_deterministic(
    isolated_reconcile: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _args(isolated_reconcile)
    assert nodes_cmd._cmd_nodes_reconcile(args) == 0
    first = capsys.readouterr().out
    assert nodes_cmd._cmd_nodes_reconcile(args) == 0
    second = capsys.readouterr().out
    assert first == second
    payload = json.loads(first)
    assert set(payload) == {"schema_version", "status", "diagnostics", "remediations"}
    assert payload["schema_version"] == "vibecomfy.nodes.reconcile.v1"
    assert payload["status"] == "ok"


def test_reconcile_reports_unknown_node_and_model_in_parallel_with_safe_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lockfile = tmp_path / "custom_nodes.lock"
    lockfile.write_text("", encoding="utf-8")
    workflow = _workflow(
        class_type="Mystery;$(touch PWNED)",
        metadata={"model_assets": [{"name": "missing model;$(touch PWNED).safetensors", "subdir": "checkpoints"}]},
    )
    monkeypatch.setattr(nodes_cmd, "get_authoring_schema_provider", lambda **_: _Provider())
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(nodes_cmd, "load_workflow_reference", lambda *_args, **_kwargs: workflow)
    from vibecomfy.registry import models_loader

    monkeypatch.setattr(models_loader, "load_registry", lambda *_args, **_kwargs: ())
    args = _args(tmp_path)
    assert nodes_cmd._cmd_nodes_reconcile(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert {item["subject_type"] for item in payload["diagnostics"]} == {"node", "model"}
    commands = "\n".join(item["command"] for item in payload["remediations"])
    assert "vibecomfy nodes lookup 'Mystery;$(touch PWNED)' --json" in commands
    assert "missing model;$(touch PWNED).safetensors" in json.dumps(payload)
    assert "'" in commands


def test_reconcile_malformed_lock_emits_blocking_json_without_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lockfile = tmp_path / "bad.lock"
    lockfile.write_text("[nodepacks.bad\n", encoding="utf-8")
    discovery_called = False

    def fail_discovery(*_args, **_kwargs):
        nonlocal discovery_called
        discovery_called = True
        raise AssertionError("discovery must not run after malformed lock")

    monkeypatch.setattr(nodes_cmd, "get_authoring_schema_provider", fail_discovery)
    args = _args(tmp_path, lockfile=str(lockfile))
    assert nodes_cmd._cmd_nodes_reconcile(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "blocked"
    assert payload["diagnostics"][0]["code"] == "reconcile_error"
    assert discovery_called is False


def test_reconcile_external_runtime_is_never_ok(
    isolated_reconcile: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from vibecomfy.runtime import session

    calls: list[str] = []
    monkeypatch.setattr(session, "_nodepack_reload_status", lambda url: calls.append(url) or "restart_required")
    args = _args(isolated_reconcile, server_url="https://external.example:8188")
    assert nodes_cmd._cmd_nodes_reconcile(args) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "restart_required"
    assert payload["diagnostics"][0]["code"] == "restart_required"
    assert calls == ["https://external.example:8188"]


def test_reconcile_empty_external_url_is_usage_error(isolated_reconcile: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert nodes_cmd._cmd_nodes_reconcile(_args(isolated_reconcile, server_url="")) == 2
    assert "must not be empty" in capsys.readouterr().err


def test_reconcile_parser_registers_required_cli_shape() -> None:
    from vibecomfy.cli import build_parser

    args = build_parser().parse_args(["nodes", "reconcile", "--workflow", "w.json", "--json"])
    assert args.func is nodes_cmd._cmd_nodes_reconcile
    assert args.lockfile is None
    assert args.registry is None
    assert args.models_root is None


def test_reconcile_known_pack_emits_exact_install_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pack = SimpleNamespace(name="ComfyUI-Test", classes=frozenset({"MissingNode"}))
    workflow = _workflow(class_type="MissingNode")
    monkeypatch.setattr(nodes_cmd, "get_authoring_schema_provider", lambda **_: _Provider())
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda *_args, **_kwargs: (pack,))
    monkeypatch.setattr(nodes_cmd, "load_workflow_reference", lambda *_args, **_kwargs: workflow)
    from vibecomfy.registry import models_loader

    monkeypatch.setattr(models_loader, "load_registry", lambda *_args, **_kwargs: ())
    assert nodes_cmd._cmd_nodes_reconcile(_args(tmp_path)) == 1
    payload = json.loads(capsys.readouterr().out)
    assert any(item["command"] == "vibecomfy nodes install 'ComfyUI-Test'" for item in payload["remediations"])


def test_reconcile_registered_missing_model_emits_stage_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflow = _workflow()
    entry = SimpleNamespace(id="model_id", targets=(SimpleNamespace(path="checkpoints/model.safetensors"),))
    monkeypatch.setattr(nodes_cmd, "get_authoring_schema_provider", lambda **_: _Provider({"KSampler"}))
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(nodes_cmd, "load_workflow_reference", lambda *_args, **_kwargs: workflow)
    monkeypatch.setattr(nodes_cmd, "_reconcile_model_references", lambda _workflow: [{"value": "model.safetensors", "subdir": "checkpoints"}])
    from vibecomfy import fetch
    from vibecomfy.registry import models_loader

    monkeypatch.setattr(models_loader, "load_registry", lambda *_args, **_kwargs: (entry,))
    monkeypatch.setattr(models_loader, "resolve_model_entry", lambda *_args, **_kwargs: entry)
    monkeypatch.setattr(fetch, "is_present", lambda *_args, **_kwargs: False)
    assert nodes_cmd._cmd_nodes_reconcile(_args(tmp_path)) == 1
    payload = json.loads(capsys.readouterr().out)
    assert any(item["command"] == "vibecomfy models stage --ids model_id --registry '" + str(tmp_path / "models.yaml") + "' --models-root '" + str(tmp_path / "models") + "'" for item in payload["remediations"])


def test_reconcile_identity_lookup_is_exact_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from vibecomfy.node_packs import LockEntry
    from vibecomfy.porting.object_info import consume

    pack = SimpleNamespace(name="Pack", classes=frozenset({"CustomNode"}))
    workflow = _workflow(class_type="CustomNode")
    calls: list[bool] = []
    monkeypatch.setattr(nodes_cmd, "get_authoring_schema_provider", lambda **_: _Provider({"CustomNode"}))
    monkeypatch.setattr(node_packs, "get_known_node_packs", lambda *_args, **_kwargs: (pack,))
    monkeypatch.setattr(nodes_cmd, "read_lockfile", lambda *_args, **_kwargs: [LockEntry(name="Pack", commit="abc", class_set=("CustomNode",))])
    monkeypatch.setattr(nodes_cmd, "load_workflow_reference", lambda *_args, **_kwargs: workflow)
    monkeypatch.setattr(consume, "resolve_class_entry", lambda _class, _identity, *, allow_class_fallback: calls.append(allow_class_fallback) or SimpleNamespace(entry=None, source="identity_miss"))
    from vibecomfy.registry import models_loader

    monkeypatch.setattr(models_loader, "load_registry", lambda *_args, **_kwargs: ())
    assert nodes_cmd._cmd_nodes_reconcile(_args(tmp_path)) == 1
    payload = json.loads(capsys.readouterr().out)
    assert False in calls
    assert any(item["code"] == "identity_mismatch" for item in payload["diagnostics"])


def test_reconcile_mutation_fence_and_repeat_bytes(isolated_reconcile: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("reconcile invoked a mutating path")

    monkeypatch.setattr(node_packs, "install_pack", forbidden)
    monkeypatch.setattr(node_packs, "install_required_packs", forbidden)
    from vibecomfy import fetch
    monkeypatch.setattr(fetch, "download_many", forbidden)
    args = _args(isolated_reconcile)
    assert nodes_cmd._cmd_nodes_reconcile(args) == 0
    first = capsys.readouterr().out
    assert nodes_cmd._cmd_nodes_reconcile(args) == 0
    second = capsys.readouterr().out
    assert first == second
