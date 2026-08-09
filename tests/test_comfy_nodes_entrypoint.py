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
    monkeypatch.setenv("VIBECOMFY_DEMO_PICKER", "1")
    monkeypatch.setenv("VIBECOMFY_AGENTIC_REPLAY", "1")

    mod, registered = _reload_comfy_nodes_with_fake_server(monkeypatch)
    monkeypatch.setattr(
        mod,
        "_git_info_snapshot",
        lambda: {"sha": "a" * 40, "dirty": False, "state": "clean"},
    )
    # Pin the web-asset dimension so the payload is deterministic regardless of
    # which web_dist copy this checkout resolves to.
    monkeypatch.setattr(mod, "_web_source_hash", lambda: "123456789abc")
    monkeypatch.setattr(mod, "WEB_DIRECTORY", "./web")

    handler = registered["/vibecomfy/info"]
    response = asyncio.run(handler(object()))

    assert response["status"] == 200
    body = response["body"]
    assert body["info_contract_version"] == 1
    assert body["process_start_id"] == mod._PROCESS_START_ID
    assert body["git_sha"] == "a" * 40
    assert body["git_dirty"] is False
    assert body["git_state"] == "clean"
    assert body["web_source_hash"] == "123456789abc"
    assert body["web_source_state"] == "identified"
    assert body["served_asset_kind"] == "source"
    assert body["served_asset_id"] == "source:123456789abc"
    assert body["served_asset_state"] == "identified"
    assert body["runtime_modes"] == {
        "headless": False,
        "dynamic_io": True,
        "runtime_module": "configured",
        "demo_picker": True,
        "agentic_replay": True,
    }
    assert isinstance(body["start_time_utc"], str) and body["start_time_utc"].endswith("Z")
    assert body["remediation"] == []


def test_comfy_nodes_info_route_keeps_success_when_git_facts_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "0")

    mod, registered = _reload_comfy_nodes_with_fake_server(monkeypatch)
    monkeypatch.setattr(
        mod,
        "_git_info_snapshot",
        lambda: {"sha": None, "dirty": None, "state": "unavailable"},
    )

    handler = registered["/vibecomfy/info"]
    response = asyncio.run(handler(object()))

    assert response["status"] == 200
    body = response["body"]
    assert body["git_sha"] is None
    assert body["git_dirty"] is None
    assert body["git_state"] == "unavailable"
    assert "restore_git_metadata" in body["remediation"]


def test_git_info_snapshot_derives_validated_sha_from_git_and_reports_state(
    monkeypatch,
) -> None:
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
        if args == ["rev-parse", "HEAD"]:
            return _Result("a" * 40 + "\n")
        if args == ["status", "--porcelain"]:
            return _Result("")
        raise AssertionError(f"unexpected git command: {args}")

    # The runtime session sha helper must NOT influence the info snapshot: the
    # verification-and-trust redesign removed the session-sha preference so the
    # info route reflects validated git facts only.
    monkeypatch.setattr(session_module, "current_source_revision", lambda: "session-sha")
    monkeypatch.setattr(git_utils, "git_stdout_result", _fake_git_stdout_result)

    git = mod._git_info_snapshot()

    assert git == {
        "sha": "a" * 40,
        "dirty": False,
        "state": "clean",
    }
    assert ("rev-parse", "HEAD") in calls
    assert ("status", "--porcelain") in calls
    assert ("rev-parse", "--abbrev-ref", "HEAD") not in calls
