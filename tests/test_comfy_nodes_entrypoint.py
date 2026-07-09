"""Entry-point and structural tests for vibecomfy.comfy_nodes (M1.5 T12)."""

from __future__ import annotations

import asyncio
import importlib
import sys
import tomllib
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_entry_point_resolves_vibecomfy_in_comfyui_group() -> None:
    from importlib.metadata import entry_points

    eps = entry_points().select(group="comfyui.custom_nodes")
    names = [ep.name for ep in eps]
    if "vibecomfy" in names:
        return

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"]["entry-points"]["comfyui.custom_nodes"]
    assert declared.get("vibecomfy") == "vibecomfy.comfy_nodes", (
        "Expected 'vibecomfy' in installed comfyui.custom_nodes entry points "
        "or declared in pyproject.toml for source-tree test runs; "
        f"installed names: {names}"
    )


def test_comfy_nodes_exposes_web_directory() -> None:
    import vibecomfy.comfy_nodes as m

    assert hasattr(m, "WEB_DIRECTORY"), "comfy_nodes must export WEB_DIRECTORY"
    assert isinstance(m.WEB_DIRECTORY, str)


def test_comfy_nodes_exposes_node_class_mappings() -> None:
    import vibecomfy.comfy_nodes as m

    assert hasattr(m, "NODE_CLASS_MAPPINGS"), "comfy_nodes must export NODE_CLASS_MAPPINGS"
    assert isinstance(m.NODE_CLASS_MAPPINGS, dict)
    assert len(m.NODE_CLASS_MAPPINGS) > 0


def test_comfy_nodes_ping_handler_defined_when_server_absent() -> None:
    """Importing comfy_nodes outside a running ComfyUI server must not raise."""
    mod = importlib.import_module("vibecomfy.comfy_nodes")
    # The handler is defined only when PromptServer is importable; outside a
    # server we just verify the module loads and exposes the required attributes.
    assert hasattr(mod, "WEB_DIRECTORY")
    assert hasattr(mod, "NODE_CLASS_MAPPINGS")


def _reload_comfy_nodes_with_fake_server(monkeypatch):
    registered: dict[str, object] = {}

    class _Routes:
        def get(self, path):
            def _decorator(fn):
                registered[path] = fn
                return fn

            return _decorator

    server_module = types.ModuleType("server")
    server_module.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=_Routes())
    )
    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body}
    )
    agent_module = types.ModuleType("vibecomfy.comfy_nodes.agent")
    agent_module.__path__ = []  # type: ignore[attr-defined]
    routes_module = types.ModuleType("vibecomfy.comfy_nodes.agent.routes")
    agent_module.routes = routes_module

    monkeypatch.setitem(sys.modules, "server", server_module)
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)
    monkeypatch.setitem(sys.modules, "vibecomfy.comfy_nodes.agent", agent_module)
    monkeypatch.setitem(sys.modules, "vibecomfy.comfy_nodes.agent.routes", routes_module)

    module = importlib.reload(importlib.import_module("vibecomfy.comfy_nodes"))
    return module, registered


def test_comfy_nodes_info_route_returns_launch_and_git_facts(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "0")
    monkeypatch.setenv("VIBECOMFY_CODE_DYNAMIC_IO", "1")
    monkeypatch.setenv("VIBECOMFY_ARNOLD_RUNTIME_MODULE", "runtime.module")
    monkeypatch.setenv("VIBECOMFY_DEMO_PICKER", "demo")
    monkeypatch.setenv("VIBECOMFY_AGENTIC_REPLAY", "replay")

    mod, registered = _reload_comfy_nodes_with_fake_server(monkeypatch)
    monkeypatch.setattr(
        mod,
        "_git_info_snapshot",
        lambda: (
            {"sha": "abc123", "branch": "main", "dirty": False},
            None,
        ),
    )

    handler = registered["/vibecomfy/info"]
    response = asyncio.run(handler(object()))

    assert response["status"] == 200
    body = response["body"]
    assert body["git_sha"] == "abc123"
    assert body["git_branch"] == "main"
    assert body["git_dirty"] is False
    assert body["git_diagnostic"] is None
    assert body["WEB_DIRECTORY"] == mod.WEB_DIRECTORY
    assert body["launch_flags"] == {
        "VIBECOMFY_HEADLESS": "0",
        "VIBECOMFY_CODE_DYNAMIC_IO": "1",
        "VIBECOMFY_ARNOLD_RUNTIME_MODULE": "runtime.module",
        "VIBECOMFY_DEMO_PICKER": "demo",
        "VIBECOMFY_AGENTIC_REPLAY": "replay",
    }
    assert isinstance(body["start_time_utc"], str) and body["start_time_utc"].endswith("Z")
    assert isinstance(body["uptime_seconds"], float)
    assert body["uptime_seconds"] >= 0.0
    assert isinstance(body["web_source_hash"], (str, type(None)))
    assert body["served_web_path"]


def test_comfy_nodes_info_route_keeps_success_when_git_facts_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "0")

    mod, registered = _reload_comfy_nodes_with_fake_server(monkeypatch)
    monkeypatch.setattr(
        mod,
        "_git_info_snapshot",
        lambda: (
            {"sha": None, "branch": None, "dirty": None},
            {
                "code": "git_command_failed",
                "message": "git command failed",
                "severity": "error",
                "recoverable": True,
            },
        ),
    )

    handler = registered["/vibecomfy/info"]
    response = asyncio.run(handler(object()))

    assert response["status"] == 200
    body = response["body"]
    assert body["git_sha"] is None
    assert body["git_branch"] is None
    assert body["git_dirty"] is None
    assert body["git_diagnostic"]["code"] == "git_command_failed"


def test_git_info_snapshot_prefers_runtime_session_sha_helper(monkeypatch) -> None:
    import vibecomfy._git_utils as git_utils
    import vibecomfy.comfy_nodes as mod
    import vibecomfy.runtime.session as session_module

    calls: list[tuple[str, ...]] = []

    class _Result:
        def __init__(self, stdout: str | None) -> None:
            self.stdout = stdout
            self.diagnostic = None

    def _fake_git_stdout_result(_repo_root: Path, args: list[str]):
        calls.append(tuple(args))
        if args == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return _Result("feature/test\n")
        if args == ["status", "--porcelain"]:
            return _Result("")
        raise AssertionError(f"unexpected git command: {args}")

    monkeypatch.setattr(session_module, "current_source_revision", lambda: "session-sha")
    monkeypatch.setattr(git_utils, "git_stdout_result", _fake_git_stdout_result)

    git, diagnostic = mod._git_info_snapshot()

    assert diagnostic is None
    assert git == {
        "sha": "session-sha",
        "branch": "feature/test",
        "dirty": False,
    }
    assert ("rev-parse", "HEAD") not in calls
