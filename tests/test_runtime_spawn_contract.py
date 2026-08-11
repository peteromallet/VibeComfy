"""T-049: runtime spawn contract pinned at the session owner.

Decided contract (ORACLE-8, R:S7) — ONE owner, ONE timeout, ONE exception shape:

- Sole owner: ``vibecomfy/runtime/session.py`` — ``_comfy_server_argv`` (richer argv
  incl. sage-attention + io-dir args) and ``_spawn_comfy_server`` (ServerSession path).
  ``config.py`` / ``server_process.py`` delegate (T-051..T-054).
- Timeout precedence: ``config.extra["ready_timeout_sec"]`` -> env
  ``VIBECOMFY_SESSION_READY_TIMEOUT_SEC`` -> default 300 seconds.
- Exception shape: readiness timeout raises ``RuntimeStartupError`` with the exact
  next_action "Check the ComfyUI startup log, installed custom nodes, and selected
  port before retrying." (chained from the underlying readiness ``TimeoutError``).
  The old raw ``TimeoutError`` surface from the session spawn is retired.
"""
from __future__ import annotations

import asyncio

import pytest

from vibecomfy.errors import RuntimeStartupError
import vibecomfy.runtime.server_process as server_process_module
import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.session import SessionConfig, _comfy_server_argv, _spawn_comfy_server

from tests._runtime_session_helpers import FakeProcess

NEXT_ACTION = (
    "Check the ComfyUI startup log, installed custom nodes, and selected port before retrying."
)


class _NotReadyClient:
    """ComfyClient stand-in whose readiness probe never succeeds."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.ready_calls = 0

    async def ready(self) -> bool:
        self.ready_calls += 1
        return False


def _patch_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[tuple[tuple[str, ...], FakeProcess]], _NotReadyClient]:
    """Fake subprocess + client + sleep so the readiness loop runs instantly."""
    spawned: list[tuple[tuple[str, ...], FakeProcess]] = []
    client = _NotReadyClient()

    async def fake_create_subprocess_exec(*argv: str, **kwargs: object) -> FakeProcess:
        process = FakeProcess()
        spawned.append((tuple(argv), process))
        return process

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(session_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(session_module, "ComfyClient", lambda _url: client)
    monkeypatch.setattr(session_module.asyncio, "sleep", fake_sleep)
    return spawned, client


def test_spawn_timeout_raises_runtime_startup_error_with_exact_next_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spawned, _client = _patch_spawn(monkeypatch)
    config = SessionConfig(port=8200, extra={"ready_timeout_sec": 2})

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(_spawn_comfy_server(config))

    error = exc_info.value
    assert error.next_action == NEXT_ACTION
    assert "did not become ready within 2 seconds" in str(error)
    assert f"next action: {NEXT_ACTION}" in str(error)
    # The timed-out process is torn down before the error surfaces.
    assert spawned[0][1].killed is True


def test_server_session_start_surfaces_runtime_startup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spawned, _client = _patch_spawn(monkeypatch)
    session = session_module.ServerSession(
        SessionConfig(port=8200, extra={"ready_timeout_sec": 1})
    )

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(session.start())

    assert exc_info.value.next_action == NEXT_ACTION


def test_spawn_timeout_precedence_extra_wins_over_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIBECOMFY_SESSION_READY_TIMEOUT_SEC", "7")
    _spawned, client = _patch_spawn(monkeypatch)
    config = SessionConfig(port=8200, extra={"ready_timeout_sec": 2})

    with pytest.raises(RuntimeStartupError):
        asyncio.run(_spawn_comfy_server(config))

    assert client.ready_calls == 2


def test_spawn_timeout_chains_underlying_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T-052: the RuntimeStartupError carries the readiness TimeoutError as its cause."""
    _spawned, _client = _patch_spawn(monkeypatch)
    config = SessionConfig(port=8200, extra={"ready_timeout_sec": 2})

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(_spawn_comfy_server(config))

    cause = exc_info.value.__cause__
    assert isinstance(cause, TimeoutError)
    assert "did not become ready within 2 seconds" in str(cause)
    # The chained detail is preserved in the surfaced message.
    assert str(cause) in str(exc_info.value)


def test_spawn_timeout_precedence_env_over_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_SESSION_READY_TIMEOUT_SEC", "3")
    _spawned, client = _patch_spawn(monkeypatch)

    with pytest.raises(RuntimeStartupError):
        asyncio.run(_spawn_comfy_server(SessionConfig(port=8200)))

    assert client.ready_calls == 3


def test_spawn_timeout_default_is_300_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    _spawned, client = _patch_spawn(monkeypatch)

    with pytest.raises(RuntimeStartupError):
        asyncio.run(_spawn_comfy_server(SessionConfig(port=8200)))

    assert client.ready_calls == 300


def test_spawn_argv_includes_richer_args(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIBECOMFY_ATTENTION_PROFILE", "sage")
    config = SessionConfig.from_dict(
        {
            "port": 8200,
            "input_directory": "/tmp/vibe-input",
            "output_directory": "/tmp/vibe-output",
            "temp_directory": "/tmp/vibe-temp",
        }
    )

    argv = _comfy_server_argv(config)

    assert "--use-sage-attention" in argv
    assert argv[argv.index("--input-directory") + 1] == "/tmp/vibe-input"
    assert argv[argv.index("--output-directory") + 1] == "/tmp/vibe-output"
    assert argv[argv.index("--temp-directory") + 1] == "/tmp/vibe-temp"
    assert argv[argv.index("--port") + 1] == "8200"


def test_spawn_passes_richer_argv_to_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    spawned, _client = _patch_spawn(monkeypatch)
    config = SessionConfig.from_dict(
        {
            "port": 8200,
            "vram_policy": "high",
            "reserve_vram_gb": 2.0,
            "cache_policy": "lru:32",
            "input_directory": "/tmp/vibe-input",
            "output_directory": "/tmp/vibe-output",
            "temp_directory": "/tmp/vibe-temp",
            "ready_timeout_sec": 1,
        }
    )

    with pytest.raises(RuntimeStartupError):
        asyncio.run(_spawn_comfy_server(config))

    argv = spawned[0][0]
    assert "--highvram" in argv
    assert argv[argv.index("--reserve-vram") + 1] == "2.0"
    assert argv[argv.index("--cache-lru") + 1] == "32"
    assert argv[argv.index("--input-directory") + 1] == "/tmp/vibe-input"
    assert argv[argv.index("--output-directory") + 1] == "/tmp/vibe-output"
    assert argv[argv.index("--temp-directory") + 1] == "/tmp/vibe-temp"
    assert argv[argv.index("--port") + 1] == "8200"


def test_server_process_delegates_argv_to_session_owner() -> None:
    """T-051: server_process reuses the session argv builder — same argv, no duplicate construction."""
    config = SessionConfig.from_dict(
        {
            "port": 8200,
            "vram_policy": "high",
            "reserve_vram_gb": 2.0,
            "cache_policy": "lru:32",
            "disable_smart_memory": True,
            "use_sage_attention": True,
            "input_directory": "/tmp/vibe-input",
            "output_directory": "/tmp/vibe-output",
            "temp_directory": "/tmp/vibe-temp",
        }
    )

    # Delegation, not a second builder: server_process exposes the session-owned function.
    assert server_process_module._comfy_server_argv is _comfy_server_argv
    # Identical argv for identical inputs, including the richer sage-attention + io-dir args.
    assert server_process_module._comfy_server_argv(config) == _comfy_server_argv(config)
