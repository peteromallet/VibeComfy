from __future__ import annotations

import asyncio

import pytest

import vibecomfy.runtime.session as session_module
from vibecomfy.errors import RuntimeStartupError
from vibecomfy.runtime.session import SessionConfig, _spawn_comfy_server


class _Process:
    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode
        self.killed = False

    async def wait(self) -> int:
        return self.returncode or 0

    def kill(self) -> None:
        self.killed = True


class _Client:
    def __init__(self, ready: bool) -> None:
        self._ready = ready

    async def ready(self) -> bool:
        return self._ready


def test_managed_spawn_refuses_preexisting_listener_before_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_module, "_port_has_listener", lambda _port: True)

    async def should_not_spawn(*_args: object, **_kwargs: object) -> _Process:
        raise AssertionError("managed startup spawned despite an occupied port")

    monkeypatch.setattr(session_module.asyncio, "create_subprocess_exec", should_not_spawn)

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(_spawn_comfy_server(SessionConfig(port=8200)))

    error = exc_info.value
    assert "port 8200 is already in use" in str(error)
    assert "refusing to attach to a pre-existing listener" in str(error)
    assert error.next_action == session_module.MANAGED_PORT_CONFLICT_NEXT_ACTION


def test_managed_spawn_reports_child_exit_during_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process(returncode=23)
    monkeypatch.setattr(session_module, "_port_has_listener", lambda _port: False)

    async def fake_spawn(*_args: object, **_kwargs: object) -> _Process:
        return process

    monkeypatch.setattr(session_module.asyncio, "create_subprocess_exec", fake_spawn)
    monkeypatch.setattr(session_module, "ComfyClient", lambda _url: _Client(False))

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(session_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(_spawn_comfy_server(SessionConfig(port=8200, extra={"ready_timeout_sec": 2})))

    error = exc_info.value
    assert "exited with code 23 before becoming ready" in str(error)
    assert "port may be occupied or startup failed" in str(error)
    assert error.next_action == session_module.MANAGED_STARTUP_NEXT_ACTION


def test_managed_spawn_does_not_accept_ready_response_after_child_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process(returncode=23)
    monkeypatch.setattr(session_module, "_port_has_listener", lambda _port: False)

    async def fake_spawn(*_args: object, **_kwargs: object) -> _Process:
        return process

    monkeypatch.setattr(session_module.asyncio, "create_subprocess_exec", fake_spawn)
    monkeypatch.setattr(session_module, "ComfyClient", lambda _url: _Client(True))

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(session_module.asyncio, "sleep", fake_sleep)

    with pytest.raises(RuntimeStartupError, match="exited with code 23"):
        asyncio.run(_spawn_comfy_server(SessionConfig(port=8200, extra={"ready_timeout_sec": 2})))
