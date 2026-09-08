from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import types
from pathlib import Path

import pytest
import vibecomfy.commands.nodes as nodes_cmd
import vibecomfy.node_packs as node_packs
from vibecomfy.commands._node_ensure import register_workflow_node
from vibecomfy.commands.run import _cmd_run
from vibecomfy.runtime.session import ensure_workflow_node_packs

runtime_run = importlib.import_module("vibecomfy.runtime.run")
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _scratchpad(tmp_path: Path) -> Path:
    path = tmp_path / "shot.py"
    path.write_text(
        """
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

def build():
    workflow = VibeWorkflow("shot", WorkflowSource("shot", path=__file__))
    workflow.nodes["1"] = VibeNode("1", "H3CustomNode")
    return workflow
""",
        encoding="utf-8",
    )
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    return path


def _workflow_object(path: Path) -> VibeWorkflow:
    workflow = VibeWorkflow("shot", WorkflowSource("shot", path=str(path)))
    workflow.nodes["1"] = VibeNode("1", "H3CustomNode")
    return workflow


def test_nodes_register_writes_and_merges_workflow_sidecar(tmp_path: Path) -> None:
    workflow = _scratchpad(tmp_path)
    repo = "https://example.test/ComfyUI-H3.git"

    assert register_workflow_node(
        str(workflow),
        "H3CustomNode",
        repo=repo,
        commit="abc123",
    ) == 0
    assert register_workflow_node(
        str(workflow),
        "H3SecondNode",
        repo=repo,
        commit="abc123",
    ) == 0

    sidecar = tmp_path / "shot.nodes.yaml"
    text = sidecar.read_text(encoding="utf-8")
    assert "url: https://example.test/ComfyUI-H3.git" in text
    assert "commit: abc123" in text
    assert text.count("- H3CustomNode") == 1
    assert text.count("- H3SecondNode") == 1


def test_nodes_install_plan_consumes_registered_unknown_class(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workflow = _scratchpad(tmp_path)
    register_workflow_node(
        str(workflow),
        "H3CustomNode",
        repo="https://example.test/ComfyUI-H3.git",
        commit="abc123",
    )
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(node_packs, "missing_class_types_for_workflow", lambda _workflow: {"H3CustomNode"})
    monkeypatch.setattr(node_packs, "missing_packs_for_workflow", lambda _workflow: ([], ["H3CustomNode"]))

    code = nodes_cmd._cmd_nodes_install_plan(argparse.Namespace(path=str(workflow), json=True))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["unresolved_class_types"] == []
    assert payload["packs"] == [
        {
            "name": "ComfyUI-H3",
            "repo": "https://example.test/ComfyUI-H3.git",
            "pip_packages": [],
            "classes": ["H3CustomNode"],
            "source": "git",
            "commit": "abc123",
        }
    ]


def test_nodes_ensure_passes_registered_pin_to_existing_batch_installer(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workflow = _scratchpad(tmp_path)
    register_workflow_node(
        str(workflow),
        "H3CustomNode",
        repo="https://example.test/ComfyUI-H3.git",
        commit="abc123",
    )
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(node_packs, "missing_class_types_for_workflow", lambda _workflow: {"H3CustomNode"})
    monkeypatch.setattr(node_packs, "missing_packs_for_workflow", lambda _workflow: ([], ["H3CustomNode"]))
    calls: dict[str, object] = {}

    def fake_install_required_packs(packs, **kwargs):
        calls["packs"] = packs
        calls["kwargs"] = kwargs
        return node_packs.InstallBatchResult(
            ok=True,
            results=(node_packs.InstallResult("ComfyUI-H3", "installed", "abc123", None),),
            preflight=node_packs.PipPreflightResult(ok=True),
        )

    monkeypatch.setattr(node_packs, "install_required_packs", fake_install_required_packs)

    code = nodes_cmd._cmd_nodes_ensure(
        argparse.Namespace(template=None, workflow=str(workflow), dry_run=False, force=True)
    )

    assert code == 0
    assert [pack.name for pack in calls["packs"]] == ["ComfyUI-H3"]
    assert calls["kwargs"] == {
        "force": True,
        "install_refs_by_name": {
            "ComfyUI-H3": {
                "slug": "ComfyUI-H3",
                "source": "git",
                "url": "https://example.test/ComfyUI-H3.git",
                "commit": "abc123",
            }
        },
    }
    assert "Nodepacks installed/refreshed." in capsys.readouterr().out


def test_run_auto_ensures_local_sidecar_for_embedded_runtime(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workflow = _scratchpad(tmp_path)
    register_workflow_node(
        str(workflow),
        "H3CustomNode",
        repo="https://example.test/ComfyUI-H3.git",
        commit="abc123",
    )
    capsys.readouterr()
    loaded = _workflow_object(workflow)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: loaded)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_embedded_sync",
        lambda _workflow, **kwargs: calls.append(kwargs)
        or types.SimpleNamespace(run_id="run", prompt_id="prompt", outputs=[], metadata_path="m", log_path="l"),
    )

    code = _cmd_run(
        argparse.Namespace(
            path=str(workflow), ready=False, runtime="embedded", server_url=None,
            backend="api", prompt=None, seed=None, steps=None, memory_profile=None,
            ensure_packs=False, ensure_models=None,
        )
    )

    assert code == 0
    assert calls == [{"backend": "api", "ensure_packs": True, "ensure_models": True}]
    capsys.readouterr()


def test_run_external_server_does_not_auto_ensure_local_sidecar(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workflow = _scratchpad(tmp_path)
    register_workflow_node(
        str(workflow),
        "H3CustomNode",
        repo="https://example.test/ComfyUI-H3.git",
        commit="abc123",
    )
    capsys.readouterr()
    loaded = _workflow_object(workflow)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: loaded)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_sync",
        lambda _workflow, **kwargs: calls.append(kwargs)
        or types.SimpleNamespace(run_id="run", prompt_id="prompt", outputs=[], metadata_path="m", log_path="l"),
    )

    code = _cmd_run(
        argparse.Namespace(
            path=str(workflow), ready=False, runtime="server", server_url="http://external.test",
            backend="api", prompt=None, seed=None, steps=None, memory_profile=None,
            ensure_packs=False, ensure_models=None,
        )
    )

    assert code == 0
    assert calls == [{
        "server_url": "http://external.test",
        "backend": "api",
    }]
    capsys.readouterr()


def test_run_auto_ensures_local_sidecar_for_new_managed_server(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    workflow = _scratchpad(tmp_path)
    register_workflow_node(
        str(workflow),
        "H3CustomNode",
        repo="https://example.test/ComfyUI-H3.git",
        commit="abc123",
    )
    capsys.readouterr()
    loaded = _workflow_object(workflow)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("vibecomfy.commands.run.find_active_session", lambda _id: None)
    monkeypatch.setattr("vibecomfy.commands.run.get_schema_provider", lambda *args, **kwargs: object())
    monkeypatch.setattr("vibecomfy.commands.run.load_workflow_reference", lambda *args, **kwargs: loaded)
    monkeypatch.setattr(
        "vibecomfy.commands.run.run_sync",
        lambda _workflow, **kwargs: calls.append(kwargs)
        or types.SimpleNamespace(run_id="run", prompt_id="prompt", outputs=[], metadata_path="m", log_path="l"),
    )

    code = _cmd_run(
        argparse.Namespace(
            path=str(workflow), ready=False, runtime="server", server_url=None,
            backend="api", prompt=None, seed=None, steps=None, memory_profile=None,
            ensure_packs=False, ensure_models=None,
        )
    )

    assert code == 0
    assert calls == [{
        "server_url": None,
        "backend": "api",
        "ensure_packs": True,
        "ensure_models": True,
    }]
    capsys.readouterr()


def test_runtime_node_reconciliation_reports_exact_research_commands(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workflow = _workflow_object(tmp_path / "shot.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(node_packs, "missing_packs_for_workflow", lambda _workflow: ([], ["H3CustomNode"]))

    try:
        ensure_workflow_node_packs(workflow)
    except RuntimeError as exc:
        message = str(exc)
    else:  # pragma: no cover - assertion gives a clearer failure than pytest.raises here
        raise AssertionError("unresolved node class should fail closed")

    assert "vibecomfy nodes register" in message
    assert "shot.py H3CustomNode --repo URL_FROM_RESEARCH" in message
    assert "vibecomfy nodes ensure --workflow" in message


def test_runtime_run_rejects_node_install_for_external_server(tmp_path: Path, monkeypatch) -> None:
    workflow = _workflow_object(tmp_path / "shot.py")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="external servers must already have"):
        asyncio.run(
            runtime_run.run(
                workflow,
                server_url="http://external.test",
                ensure_packs=True,
            )
        )
