"""T-055: runtime integration matrix — one spawn contract across every startup surface.

ORACLE-8 R:S7 consolidated the managed-Comfy spawn contract (T-049..T-054):
``vibecomfy/runtime/session.py`` is the sole owner (richer argv incl.
sage-attention + io-dir args; readiness timeout precedence ``extra`` -> env
``VIBECOMFY_SESSION_READY_TIMEOUT_SEC`` -> 300; ``RuntimeStartupError`` with the
exact next_action chained from the underlying readiness ``TimeoutError``;
``runtime/config.py`` deleted, ``server_process.py`` re-exports by identity).

This matrix proves the contract END-TO-END — with fakes, no real Comfy server —
across the four startup surfaces that consume it:

- embedded startup — ``runtime.run.run()`` (the one-shot run helper that embeds
  the managed-server start for ``--runtime server`` / ``--runtime auto`` without
  an active session);
- server — ``runtime.server.comfy_server`` context manager (identity-delegates
  to the session spawn);
- session — ``ServerSession.start()``;
- CLI — the ``session start`` command and its daemon.

Plus the timeout precedence and the error-chaining guarantee at those surfaces.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
from pathlib import Path

import pytest

from vibecomfy.errors import RuntimeStartupError
import vibecomfy.commands.session as session_cmd
import vibecomfy.runtime.server as server_module
import vibecomfy.runtime.server_process as server_process_module
import vibecomfy.runtime.session as session_module
from vibecomfy.runtime.server import comfy_server
from vibecomfy.runtime.session import ServerSession, SessionConfig, _comfy_server_argv

from tests._runtime_session_helpers import FakeProcess, _workflow

# ``vibecomfy.runtime.run`` is shadowed by the ``run`` function export in the
# package __init__, so the submodule must be fetched via importlib.
run_module = importlib.import_module("vibecomfy.runtime.run")

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


def _rich_config(*, ready_timeout_sec: int = 1) -> SessionConfig:
    """A config that exercises every richer-argv dimension of the contract."""
    return SessionConfig.from_dict(
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
            "ready_timeout_sec": ready_timeout_sec,
        }
    )


async def _enter_server_ctx(ctx) -> str:
    """Enter a ``comfy_server`` context and return the yielded URL."""
    async with ctx as url:
        return url


async def _enter_server_ctx_raising(ctx) -> None:
    """Enter a ``comfy_server`` context, letting a startup error propagate."""
    async with ctx:
        pass


# --- embedded startup path: runtime.run's one-shot helper embeds the server start


def test_embedded_run_helper_surfaces_startup_error_with_canonical_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Embedded startup — the run helper embeds ``comfy_server``; on readiness
    timeout the contract exception surfaces end-to-end with the exact next_action,
    and the subprocess argv is byte-identical to the canonical session builder."""
    monkeypatch.chdir(tmp_path)
    spawned, _client = _patch_spawn(monkeypatch)
    config = _rich_config(ready_timeout_sec=1)

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(run_module.run(_workflow(), config=config))

    error = exc_info.value
    assert error.next_action == NEXT_ACTION
    assert "did not become ready within 1 seconds" in str(error)
    assert isinstance(error.__cause__, TimeoutError)
    assert str(error.__cause__) in str(error)
    # The run helper passes the workflow-derived config straight through, so the
    # spawned subprocess argv is exactly the canonical builder's output.
    assert spawned[0][0] == _comfy_server_argv(config)
    assert "--use-sage-attention" in spawned[0][0]
    assert "--input-directory" in spawned[0][0]
    assert "--port" in spawned[0][0]
    # The timed-out process is torn down before the error surfaces.
    assert spawned[0][1].killed is True


# --- server path: runtime.server's comfy_server context manager


def test_comfy_server_ctx_identity_delegates_to_session_spawn() -> None:
    """Server path — ``comfy_server`` is identity-bound to the session owner: the
    consolidation left ONE spawn and ONE argv builder, not a second implementation."""
    assert server_module._spawn_comfy_server is session_module._spawn_comfy_server
    assert server_process_module._spawn_comfy_server is session_module._spawn_comfy_server
    assert server_process_module._comfy_server_argv is session_module._comfy_server_argv


def test_comfy_server_ctx_surfaces_startup_error_and_records_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Server path behavior — the context manager surfaces the same exception
    shape on timeout and records the canonical argv in the startup log."""
    monkeypatch.chdir(tmp_path)
    spawned, _client = _patch_spawn(monkeypatch)
    log_path = tmp_path / "sessions" / "comfy.log"

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(
            _enter_server_ctx_raising(
                comfy_server(
                    config=SessionConfig(port=8200, extra={"ready_timeout_sec": 1}),
                    log_path=log_path,
                )
            )
        )

    error = exc_info.value
    assert error.next_action == NEXT_ACTION
    assert "did not become ready within 1 seconds" in str(error)
    assert isinstance(error.__cause__, TimeoutError)
    assert spawned[0][1].killed is True
    # The startup log records the exact canonical argv of the launch.
    assert log_path.exists()
    launch_line = log_path.read_text(encoding="utf-8").splitlines()[0]
    assert "[vibecomfy] launching managed Comfy server:" in launch_line
    assert json.loads(launch_line.split(": ", 1)[1]) == list(_comfy_server_argv(SessionConfig(port=8200)))


def test_comfy_server_ctx_external_url_passthrough_never_spawns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server path — an explicit external URL bypasses the spawn entirely."""
    spawned, _client = _patch_spawn(monkeypatch)

    url = asyncio.run(_enter_server_ctx(comfy_server(server_url="http://external.test:8188")))

    assert url == "http://external.test:8188"
    assert spawned == []


def test_comfy_server_ctx_timeout_precedence_extra_beats_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-session timeout precedence — explicit ``extra`` param wins over env."""
    monkeypatch.setenv("VIBECOMFY_SESSION_READY_TIMEOUT_SEC", "7")
    _spawned, client = _patch_spawn(monkeypatch)

    with pytest.raises(RuntimeStartupError):
        asyncio.run(
            _enter_server_ctx_raising(
                comfy_server(config=SessionConfig(port=8200, extra={"ready_timeout_sec": 2}))
            )
        )

    assert client.ready_calls == 2


def test_comfy_server_ctx_timeout_precedence_env_beats_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-session timeout precedence — env var beats the 300s default."""
    monkeypatch.setenv("VIBECOMFY_SESSION_READY_TIMEOUT_SEC", "3")
    _spawned, client = _patch_spawn(monkeypatch)

    with pytest.raises(RuntimeStartupError):
        asyncio.run(_enter_server_ctx_raising(comfy_server(config=SessionConfig(port=8200))))

    assert client.ready_calls == 3


# --- session path: ServerSession.start()


def test_server_session_start_surfaces_contract_with_chained_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session path — ``ServerSession.start()`` surfaces ``RuntimeStartupError``
    with the exact next_action, the chained readiness cause, and the richer argv
    (sage-attention + io-dirs) reaching the subprocess."""
    spawned, _client = _patch_spawn(monkeypatch)
    config = _rich_config(ready_timeout_sec=1)
    session = ServerSession(config)

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(session.start())

    error = exc_info.value
    assert error.next_action == NEXT_ACTION
    assert "did not become ready within 1 seconds" in str(error)
    cause = error.__cause__
    assert isinstance(cause, TimeoutError)
    assert str(cause) in str(error)
    # Canonical argv: the session records it and the subprocess receives it.
    assert session._argv == _comfy_server_argv(config)
    assert spawned[0][0] == _comfy_server_argv(config)
    assert "--use-sage-attention" in spawned[0][0]
    assert "--input-directory" in spawned[0][0]
    assert "--temp-directory" in spawned[0][0]
    assert spawned[0][1].killed is True
    # No half-started state survives the failure.
    assert session.process is None
    assert session.url is None


def test_server_session_retries_cleanly_after_startup_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session path — each ``start()`` attempt is a fresh single spawn; a timeout
    leaves no zombie process or stuck session state behind."""
    spawned, _client = _patch_spawn(monkeypatch)
    session = ServerSession(SessionConfig(port=8200, extra={"ready_timeout_sec": 1}))

    for _ in range(2):
        with pytest.raises(RuntimeStartupError):
            asyncio.run(session.start())
        assert session.process is None
        assert session.url is None

    assert len(spawned) == 2


# --- CLI path: session start command + its daemon


def test_cli_start_daemon_delegates_to_session_spawn_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """CLI path — the ``session start`` daemon delegates to ``ServerSession.start()``
    → ``_spawn_comfy_server``; the same real spawn times out through the daemon and
    surfaces the contract exception with the exact next_action and chained cause."""
    monkeypatch.chdir(tmp_path)
    spawned, _client = _patch_spawn(monkeypatch)
    config_dict = {"port": 8200, "ready_timeout_sec": 1}
    args = argparse.Namespace(id="default", config=json.dumps(config_dict))

    with pytest.raises(RuntimeStartupError) as exc_info:
        asyncio.run(session_cmd._daemon_main(args))

    error = exc_info.value
    assert error.next_action == NEXT_ACTION
    assert "did not become ready within 1 seconds" in str(error)
    assert isinstance(error.__cause__, TimeoutError)
    assert spawned[0][0] == _comfy_server_argv(SessionConfig.from_dict(config_dict))
    assert spawned[0][1].killed is True
    # The daemon records the canonical argv before starting (contract wiring).
    recorded = json.loads(
        (tmp_path / "out/sessions/default/server_argv.json").read_text(encoding="utf-8")
    )
    assert recorded == list(_comfy_server_argv(SessionConfig.from_dict(config_dict)))


class _SlowPopen:
    """Daemon stand-in that never becomes ready; tracks termination."""

    instance: "_SlowPopen | None" = None

    def __init__(self, cmd, *, stdout, stderr, start_new_session: bool) -> None:
        self.cmd = list(cmd)
        self.returncode = None
        self.terminated = False
        _SlowPopen.instance = self
        assert start_new_session is True

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


@pytest.mark.parametrize(
    ("explicit", "env", "expected_seconds"),
    [
        (1, None, 1),       # explicit --ready-timeout-sec beats env
        (None, "2", 2),     # env var beats the default
        (None, None, 300),  # default
    ],
)
def test_cli_start_surfaces_timeout_contract_with_precedence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    explicit: int | None,
    env: str | None,
    expected_seconds: int,
) -> None:
    """CLI path — ``session start`` mirrors the shared contract on timeout: same
    readiness-window message, daemon termination, and the same precedence
    (explicit param > env var > 300)."""
    monkeypatch.chdir(tmp_path)
    sleep_calls: list[float] = []
    _SlowPopen.instance = None
    monkeypatch.setattr(session_cmd.subprocess, "Popen", _SlowPopen)
    monkeypatch.setattr(session_module, "_session_ready", lambda _dir: False)
    monkeypatch.setattr(session_cmd.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(session_cmd, "normalized_models_root", lambda: str(tmp_path / "ComfyUI/models"))
    if env is not None:
        monkeypatch.setenv("VIBECOMFY_SESSION_READY_TIMEOUT_SEC", env)
    else:
        monkeypatch.delenv("VIBECOMFY_SESSION_READY_TIMEOUT_SEC", raising=False)
    args = argparse.Namespace(
        id="default",
        port=8200,
        vram_policy="auto",
        reserve_vram_gb=None,
        cache_policy="smart",
        warm_policy="auto",
        disable_smart_memory=False,
        memory_profile=None,
        input_directory=None,
        output_directory=None,
        temp_directory=None,
        ready_timeout_sec=explicit,
    )

    assert session_cmd._cmd_session_start(args) == 1
    assert len(sleep_calls) == expected_seconds
    assert _SlowPopen.instance is not None
    assert _SlowPopen.instance.terminated is True
    err = capsys.readouterr().err
    assert f"session default did not become ready within {expected_seconds} seconds" in err
    # The explicit timeout travels into the daemon config so the daemon's
    # ServerSession honors the same contract (env/default stay implicit).
    daemon_config = json.loads(
        _SlowPopen.instance.cmd[_SlowPopen.instance.cmd.index("--config") + 1]
    )
    if explicit is not None:
        assert daemon_config["ready_timeout_sec"] == explicit
    else:
        assert "ready_timeout_sec" not in daemon_config
