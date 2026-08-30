from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import signal
import struct
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path
from typing import Any

import pytest

import vibecomfy.commands.session as session_cmd
import vibecomfy.runtime.session as session_module
from vibecomfy.memory_profile import MemoryProfile
from vibecomfy.runtime.session import SessionConfig, find_active_session


class FakePopen:
    started: list[list[str]] = []

    def __init__(self, cmd, *, stdout, stderr, start_new_session: bool) -> None:
        self.cmd = list(cmd)
        self.returncode = None
        FakePopen.started.append(self.cmd)
        assert start_new_session is True
        id_ = self.cmd[self.cmd.index("--id") + 1]
        config = json.loads(self.cmd[self.cmd.index("--config") + 1])
        session_dir = Path("out/sessions") / id_
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "pid").write_text("4242", encoding="utf-8")
        (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
        (session_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
        (session_dir / "launch.json").write_text(
            json.dumps(
                {
                    "launch_token": self.cmd[self.cmd.index("--launch-token") + 1],
                    "pid": 4242,
                    "process_start_identity": "fake-start",
                    "url": "http://127.0.0.1:8200",
                }
            ),
            encoding="utf-8",
        )

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


def test_session_cli_start_list_flush_stop_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    FakePopen.started = []
    alive = {4242}
    free_calls: list[tuple[str, bool, bool]] = []

    def fake_kill(pid: int, sig: int) -> None:
        if sig == 0:
            if pid not in alive:
                raise ProcessLookupError(pid)
            return
        if sig == signal.SIGTERM and pid in alive:
            alive.remove(pid)
            session_module._cleanup_session_files(Path("out/sessions/default"))
            return
        raise ProcessLookupError(pid)

    class FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def free(self, *, unload_models: bool, free_memory: bool) -> dict[str, Any]:
            free_calls.append((self.url, unload_models, free_memory))
            return {}

    monkeypatch.setattr(session_cmd.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_cmd, "ComfyClient", FakeClient)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: None)
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: True)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: "fake-start")
    monkeypatch.setattr(
        session_module,
        "_process_commandline",
        lambda _pid: ("python", "--launch-token", FakePopen.started[0][FakePopen.started[0].index("--launch-token") + 1]),
    )
    monkeypatch.setattr(session_cmd, "normalized_models_root", lambda: str(tmp_path / "ComfyUI/models"))

    start_args = argparse.Namespace(
        id="default",
        port=8200,
        vram_policy="high",
        reserve_vram_gb=2.0,
        cache_policy="lru:3",
        warm_policy="always",
        disable_smart_memory=True,
        memory_profile=None,
    )
    assert session_cmd._cmd_session_start(start_args) == 0
    assert (tmp_path / "out/sessions/default/pid").exists()
    assert (tmp_path / "out/sessions/default/url").read_text(encoding="utf-8") == "http://127.0.0.1:8200"
    config = json.loads((tmp_path / "out/sessions/default/config.json").read_text(encoding="utf-8"))
    assert config == {
        "port": 8200,
        "vram_policy": "high",
        "reserve_vram_gb": 2.0,
        "cache_policy": "lru:3",
        "warm_policy": "always",
        "disable_smart_memory": True,
        "server_log_path": "out/sessions/default/comfy.log",
        "models_root": str(tmp_path / "ComfyUI/models"),
        "models_root_normalized": str(tmp_path / "ComfyUI/models"),
        "locality": "managed_local_server",
    }

    assert session_cmd._cmd_session_list(argparse.Namespace()) == 0
    assert "default\thttp://127.0.0.1:8200" in capsys.readouterr().out

    assert session_cmd._cmd_session_flush(
        argparse.Namespace(id="default", unload_models=True, free_memory=True)
    ) == 0
    assert free_calls == [("http://127.0.0.1:8200", True, True)]

    assert session_cmd._cmd_session_stop(argparse.Namespace(id="default")) == 0
    assert not (tmp_path / "out/sessions/default/pid").exists()
    assert not (tmp_path / "out/sessions/default/url").exists()
    assert not (tmp_path / "out/sessions/default/config.json").exists()


def test_session_cli_start_persists_memory_profiles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_cmd.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(session_module.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: None)
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: True)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: "fake-start")
    monkeypatch.setattr(
        session_module,
        "_process_commandline",
        lambda _pid: ("python", "--launch-token", FakePopen.started[-1][FakePopen.started[-1].index("--launch-token") + 1]),
    )
    FakePopen.started = []

    for profile in range(1, 6):
        args = argparse.Namespace(
            id=f"profile-{profile}",
            port=8200 + profile,
            vram_policy=None,
            reserve_vram_gb=None,
            cache_policy=None,
            warm_policy="auto",
            disable_smart_memory=False,
            memory_profile=profile,
        )

        assert session_cmd._cmd_session_start(args) == 0
        config = json.loads(
            (tmp_path / f"out/sessions/profile-{profile}/config.json").read_text(encoding="utf-8")
        )
        assert config["memory_profile"] == profile
        assert config["port"] == 8200 + profile
        effective = SessionConfig.from_dict(config)
        assert effective.memory_profile == profile
        for key, value in MemoryProfile(profile).to_session_overrides().items():
            assert getattr(effective, key) == value


def test_session_cli_start_without_memory_profile_leaves_config_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_cmd.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(session_module.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: None)
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: True)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: "fake-start")
    monkeypatch.setattr(
        session_module,
        "_process_commandline",
        lambda _pid: ("python", "--launch-token", FakePopen.started[-1][FakePopen.started[-1].index("--launch-token") + 1]),
    )
    FakePopen.started = []
    args = argparse.Namespace(
        id="default",
        port=8200,
        vram_policy="auto",
        reserve_vram_gb=None,
        cache_policy="smart",
        warm_policy="auto",
        disable_smart_memory=False,
        memory_profile=None,
    )

    assert session_cmd._cmd_session_start(args) == 0
    config = json.loads((tmp_path / "out/sessions/default/config.json").read_text(encoding="utf-8"))

    assert "memory_profile" not in config


def _darwin_procargs2_fixture(
    executable: bytes, argv: tuple[bytes, ...], *, padding: bytes = b"\0"
) -> bytes:
    return struct.pack("=i", len(argv)) + executable + b"\0" + padding + b"\0".join(argv) + b"\0ENV=value\0"


def test_parse_darwin_procargs2_returns_counted_argv() -> None:
    raw = _darwin_procargs2_fixture(
        b"/usr/bin/python3",
        (b"/usr/bin/python3", b"-c", b"hello world", b"--launch-token", b"owned"),
    )
    assert session_module._parse_darwin_procargs2(raw) == (
        "/usr/bin/python3",
        "-c",
        "hello world",
        "--launch-token",
        "owned",
    )


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        struct.pack("=i", 0) + b"/bin/python\0\0/bin/python\0",
        struct.pack("=i", -1) + b"/bin/python\0\0/bin/python\0",
        struct.pack("=i", 2) + b"/bin/python\0\0/bin/python\0",
        struct.pack("=i", 1) + b"/bin/python\0\0/bin/python",
        struct.pack("=i", 1) + b"\0\0/bin/python\0",
        struct.pack("=i", 1) + b"/bin/\xff\0\0/bin/python\0",
        struct.pack("=i", 1) + b"/bin/python\0\0/bin/\xff\0",
    ],
)
def test_parse_darwin_procargs2_rejects_malformed_fixtures(raw: bytes) -> None:
    assert session_module._parse_darwin_procargs2(raw) is None


def test_parse_darwin_procargs2_rejects_changed_size_fixture() -> None:
    raw = _darwin_procargs2_fixture(b"/bin/python", (b"/bin/python",))
    assert session_module._parse_darwin_procargs2(raw[:-1]) is None


@pytest.mark.parametrize(
    ("first_result", "second_result", "second_size"),
    [
        (-1, 0, None),
        (0, -1, None),
        (0, 0, -1),
    ],
)
def test_darwin_sysctl_process_argv_fails_closed_on_errors_or_size_race(
    monkeypatch: pytest.MonkeyPatch,
    first_result: int,
    second_result: int,
    second_size: int | None,
) -> None:
    raw = _darwin_procargs2_fixture(b"/bin/python", (b"/bin/python",))

    class FakeSysctl:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, _mib: Any, _mib_len: int, oldp: Any, oldlenp: Any, *_args: Any) -> int:
            self.calls += 1
            if oldp is None:
                oldlenp._obj.value = len(raw)
                return first_result
            oldlenp._obj.value = len(raw) if second_size is None else len(raw) + second_size
            if second_result == 0:
                ctypes.memmove(oldp, raw, len(raw))
            return second_result

    fake_sysctl = FakeSysctl()
    monkeypatch.setattr(
        session_module.ctypes,
        "CDLL",
        lambda *_args, **_kwargs: SimpleNamespace(sysctl=fake_sysctl),
    )

    assert session_module._darwin_process_commandline(4242) is None
    assert fake_sysctl.calls == (1 if first_result else 2)


@pytest.mark.skipif(sys.platform != "darwin", reason="requires Darwin KERN_PROCARGS2")
def test_live_darwin_owned_child_has_exact_paired_argv(tmp_path: Path) -> None:
    token = "b08-live-owned-token"
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)", "--launch-token", token]
    )
    try:
        commandline = session_module._process_commandline(child.pid)
        assert commandline is not None
        assert session_module._launch_token_is_exactly_paired(commandline, token)

        session_dir = tmp_path / "session"
        session_dir.mkdir()
        (session_dir / "pid").write_text(str(child.pid), encoding="utf-8")
        (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
        (session_dir / "launch.json").write_text(
            json.dumps(
                {
                    "launch_token": token,
                    "pid": child.pid,
                    "process_start_identity": session_module._process_start_identity(child.pid),
                    "url": "http://127.0.0.1:8200",
                }
            ),
            encoding="utf-8",
        )
        assert session_module._session_ownership_verified(session_dir, child.pid)
    finally:
        child.terminate()
        child.wait(timeout=5)


@pytest.mark.parametrize(
    "child_argv",
    [
        lambda token: [
            sys.executable,
            "-c",
            f"import time; time.sleep(30) # --launch-token {token}",
        ],
        lambda token: [
            sys.executable,
            "-c",
            "import time; time.sleep(30)",
            f"--launch-token={token}",
        ],
    ],
)
@pytest.mark.skipif(sys.platform != "darwin", reason="requires Darwin KERN_PROCARGS2")
def test_live_darwin_embedded_or_equals_marker_refuses_ownership(
    tmp_path: Path, child_argv: Any
) -> None:
    token = "b08-live-forged-token"
    child = subprocess.Popen(child_argv(token))
    try:
        commandline = session_module._process_commandline(child.pid)
        assert commandline is not None
        assert not session_module._launch_token_is_exactly_paired(commandline, token)

        session_dir = tmp_path / "session"
        session_dir.mkdir()
        (session_dir / "pid").write_text(str(child.pid), encoding="utf-8")
        (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
        (session_dir / "launch.json").write_text(
            json.dumps(
                {
                    "launch_token": token,
                    "pid": child.pid,
                    "process_start_identity": session_module._process_start_identity(child.pid),
                    "url": "http://127.0.0.1:8200",
                }
            ),
            encoding="utf-8",
        )
        assert not session_module._session_ownership_verified(session_dir, child.pid)
    finally:
        child.terminate()
        child.wait(timeout=5)


@pytest.mark.skipif(sys.platform != "darwin", reason="requires Darwin KERN_PROCARGS2")
def test_live_darwin_foreign_child_with_forged_marker_refuses_ownership(
    tmp_path: Path,
) -> None:
    token = "b08-live-foreign-token"
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)", "--launch-token", "different-token"]
    )
    try:
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        (session_dir / "pid").write_text(str(child.pid), encoding="utf-8")
        (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
        (session_dir / "launch.json").write_text(
            json.dumps(
                {
                    "launch_token": token,
                    "pid": child.pid,
                    "process_start_identity": session_module._process_start_identity(child.pid),
                    "url": "http://127.0.0.1:8200",
                }
            ),
            encoding="utf-8",
        )
        assert not session_module._session_ownership_verified(session_dir, child.pid)
    finally:
        child.terminate()
        child.wait(timeout=5)


@pytest.mark.parametrize(
    "proc_output",
    [
        b"",
        b"python\0--launch-token\0owned",
        b"python\0--launch-token\0owned\0\0",
        b"python\0\0--launch-token\0owned\0",
        b"python\0--launch-token\0\xff\0",
        b"\0",
        b"python\0--launch-token\0",
        b"python\0--launch-token\0owned\0--launch-token\0owned\0",
    ],
)
def test_process_commandline_rejects_malformed_linux_proc_argv(
    monkeypatch: pytest.MonkeyPatch, proc_output: bytes
) -> None:
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: proc_output
        if path == Path("/proc/4242/cmdline")
        else (_ for _ in ()).throw(AssertionError(f"unexpected read: {path}")),
    )
    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("malformed Linux /proc argv must not call ps"),
    )

    assert session_module._process_commandline(4242) is None


@pytest.mark.parametrize(
    "proc_output",
    [b"", b"python\0--launch-token\0owned", b"python\0--launch-token\0\xff\0"],
)
def test_malformed_linux_process_evidence_never_authorizes_readiness_or_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, proc_output: bytes
) -> None:
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "launch.json").write_text(
        json.dumps(
            {
                "launch_token": "owned",
                "pid": 4242,
                "process_start_identity": "same-incarnation",
                "url": "http://127.0.0.1:8200",
            }
        ),
        encoding="utf-8",
    )
    signals: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        signals.append((pid, sig))

    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: "same-incarnation")
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: pytest.fail("ownership refusal must precede readiness HTTP"))
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: proc_output
        if path == Path("/proc/4242/cmdline")
        else (_ for _ in ()).throw(AssertionError(f"unexpected read: {path}")),
    )
    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("malformed Linux /proc argv must not call ps"),
    )

    assert session_module._session_ready(session_dir) is False
    assert session_module._terminate_session_pid(4242, session_dir=session_dir) is False
    assert session_cmd._cmd_session_stop(argparse.Namespace(id="default")) == 1
    assert all(sig == 0 for _pid, sig in signals)


@pytest.mark.parametrize(
    "hostile_evidence",
    [
        None,
        b"python --launch-token owned\n",
        object(),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
)
def test_hostile_darwin_process_evidence_never_authorizes_readiness_or_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hostile_evidence: object
) -> None:
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "launch.json").write_text(
        json.dumps(
            {
                "launch_token": "owned",
                "pid": 4242,
                "process_start_identity": "same-incarnation",
                "url": "http://127.0.0.1:8200",
            }
        ),
        encoding="utf-8",
    )
    signals: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        signals.append((pid, sig))

    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: "same-incarnation")
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: pytest.fail("ownership refusal must precede readiness HTTP"))
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: (_ for _ in ()).throw(OSError("/proc unavailable on Darwin"))
        if path == Path("/proc/4242/cmdline")
        else (_ for _ in ()).throw(AssertionError(f"unexpected read: {path}")),
    )

    def fake_run(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        if isinstance(hostile_evidence, BaseException):
            raise hostile_evidence
        return SimpleNamespace(returncode=0, stdout=hostile_evidence)

    monkeypatch.setattr(session_module.subprocess, "run", fake_run)

    assert session_module._session_ready(session_dir) is False
    assert session_module._terminate_session_pid(4242, session_dir=session_dir) is False
    assert session_cmd._cmd_session_stop(argparse.Namespace(id="default")) == 1
    assert all(sig == 0 for _pid, sig in signals)


@pytest.mark.parametrize(
    ("commandline", "expected"),
    [
        (("python", "--launch-token", "owned"), True),
        (("python", "--launch-token", "owned-suffix"), False),
        (("python", "--config", '{"token": "owned"}'), False),
        (("python", "owned", "--config", "spoof"), False),
        (("python", "--launch-token", "other"), False),
        (("python", "--launch-token"), False),
        (("python", "--launch-token", "owned", "--launch-token", "owned"), False),
        (("python", "--launch-token=owned"), False),
    ],
)
def test_launch_token_requires_one_exact_paired_argv_value(
    commandline: tuple[str, ...], expected: bool
) -> None:
    assert session_module._launch_token_is_exactly_paired(commandline, "owned") is expected


def test_process_commandline_preserves_linux_proc_argv_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda path: (
            b"/usr/bin/python3\0-m\0vibecomfy.commands.session\0"
            b"--launch-token\0owned\0--config\0{}\0"
            if path == Path("/proc/4242/cmdline")
            else (_ for _ in ()).throw(AssertionError(f"unexpected read: {path}"))
        ),
    )
    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Linux /proc argv should not call ps"),
    )

    assert session_module._process_commandline(4242) == (
        "/usr/bin/python3",
        "-m",
        "vibecomfy.commands.session",
        "--launch-token",
        "owned",
        "--config",
        "{}",
    )


def test_session_cli_start_timeout_terminates_daemon_and_records_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    sleep_calls: list[float] = []

    class SlowPopen:
        instance: "SlowPopen | None" = None

        def __init__(self, cmd, *, stdout, stderr, start_new_session: bool) -> None:
            self.cmd = list(cmd)
            self.returncode = None
            self.terminated = False
            SlowPopen.instance = self
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

    monkeypatch.setattr(session_cmd.subprocess, "Popen", SlowPopen)
    monkeypatch.setattr(session_cmd.time, "sleep", lambda seconds: sleep_calls.append(seconds))

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
        ready_timeout_sec=1,
    )

    assert session_cmd._cmd_session_start(args) == 1
    assert SlowPopen.instance is not None
    assert SlowPopen.instance.terminated is True
    assert "did not become ready within 1 seconds" in capsys.readouterr().err
    assert json.loads((tmp_path / "out/sessions/default/daemon_argv.json").read_text(encoding="utf-8")) == SlowPopen.instance.cmd


def test_find_active_session_returns_url_or_cleans_stale_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: None)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text("{}", encoding="utf-8")
    alive = True

    def fake_kill(pid: int, sig: int) -> None:
        assert pid == 4242
        assert sig == 0
        if not alive:
            raise ProcessLookupError(pid)

    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: alive)

    assert find_active_session("default") == "http://127.0.0.1:8200"
    alive = False
    assert find_active_session("default") is None
    assert not (session_dir / "pid").exists()
    assert not (session_dir / "url").exists()
    assert not (session_dir / "config.json").exists()


def test_find_active_session_healthy_daemon_survives_source_revision_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A healthy daemon must survive git HEAD movement after launch.

    source_revision is advisory metadata only (SD2).  A mismatch between
    the launch revision and the current git HEAD must never terminate or
    hide an otherwise-healthy session.  The advisory fields are still
    exposed via active_session_metadata().
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: "new-sha")
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: True)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text('{"port": 8200}', encoding="utf-8")
    (session_dir / "source_revision").write_text("old-sha", encoding="utf-8")

    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    monkeypatch.setattr(session_module.os, "kill", fake_kill)

    # The daemon is healthy (pid + url + /system_stats OK) — the revision
    # mismatch must not hide the session or terminate the process.
    assert find_active_session("default") == "http://127.0.0.1:8200"
    # Only the process-aliveness check (os.kill(pid, 0)) — no SIGTERM.
    assert kill_calls == [(4242, 0)]

    # Session files must still be present (no cleanup).
    assert (session_dir / "pid").exists()
    assert (session_dir / "url").exists()
    assert (session_dir / "config.json").exists()
    assert (session_dir / "source_revision").exists()

    # Advisory mismatch metadata is visible.
    meta = session_module.active_session_metadata("default")
    assert meta is not None
    assert meta["launch_source_revision"] == "old-sha"
    assert meta["current_source_revision"] == "new-sha"
    assert meta["url"] == "http://127.0.0.1:8200"


def test_find_active_session_accepts_matching_source_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: "same-sha")
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: True)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text("{}", encoding="utf-8")
    (session_dir / "source_revision").write_text("same-sha", encoding="utf-8")

    monkeypatch.setattr(session_module.os, "kill", lambda pid, sig: None)

    assert find_active_session("default") == "http://127.0.0.1:8200"


def test_find_active_session_rejects_dead_server_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: None)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text("{}", encoding="utf-8")
    terminated: list[int] = []

    def fake_kill(pid: int, sig: int) -> None:
        assert pid == 4242
        if sig == 0:
            return
        if sig == signal.SIGTERM:
            terminated.append(pid)
            return
        raise AssertionError(f"unexpected signal {sig}")

    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: False)

    assert find_active_session("default") is None
    # Legacy PID/URL/health markers do not authorize a signal.
    assert terminated == []
    assert not (session_dir / "pid").exists()
    assert not (session_dir / "url").exists()
    assert not (session_dir / "config.json").exists()


def test_session_cli_start_refuses_duplicate_without_clearing_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text("{}", encoding="utf-8")
    (session_dir / "launch.json").write_text(
        json.dumps(
            {
                "launch_token": "existing",
                "pid": 4242,
                "process_start_identity": "same-incarnation",
                "url": "http://127.0.0.1:8200",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(session_module.os, "kill", lambda _pid, sig: None if sig == 0 else None)
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: True)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: None)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: "same-incarnation")
    monkeypatch.setattr(
        session_module,
        "_process_commandline",
        lambda _pid: ("python", "--launch-token", "existing"),
    )
    monkeypatch.setattr(session_cmd.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("spawned duplicate"))

    assert session_cmd._cmd_session_start(argparse.Namespace(id="default")) == 1
    assert "refusing duplicate start" in capsys.readouterr().err
    assert (session_dir / "pid").read_text(encoding="utf-8") == "4242"
    assert (session_dir / "launch.json").exists()


@pytest.mark.parametrize(
    ("marker_start", "current_start", "commandline"),
    [
        ("old-incarnation", "new-incarnation", ("python", "--launch-token", "owned")),
        ("same-incarnation", "same-incarnation", ("foreign-server",)),
        ("same-incarnation", "same-incarnation", ("python", "owned", "--config", "owned-suffix")),
        (
            "same-incarnation",
            "same-incarnation",
            ("python", "--launch-token", "owned", "--launch-token", "owned"),
        ),
    ],
)
def test_stale_or_foreign_marker_never_authorizes_signal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    marker_start: str,
    current_start: str,
    commandline: tuple[str, ...],
) -> None:
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text("{}", encoding="utf-8")
    (session_dir / "launch.json").write_text(
        json.dumps(
            {
                "launch_token": "owned",
                "pid": 4242,
                "process_start_identity": marker_start,
                "url": "http://127.0.0.1:8200",
            }
        ),
        encoding="utf-8",
    )
    signals: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        signals.append((pid, sig))

    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: current_start)
    monkeypatch.setattr(session_module, "_process_commandline", lambda _pid: commandline)
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: False)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: None)

    assert find_active_session("default") is None
    assert signals
    assert all(sig == 0 for _pid, sig in signals)


def test_session_cli_stop_timeout_is_nonzero_and_retains_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "launch.json").write_text(
        json.dumps(
            {
                "launch_token": "owned",
                "pid": 4242,
                "process_start_identity": "same-incarnation",
                "url": "http://127.0.0.1:8200",
            }
        ),
        encoding="utf-8",
    )
    signals: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        signals.append((pid, sig))

    monkeypatch.setattr(session_module.os, "kill", fake_kill)
    monkeypatch.setattr(session_module, "_process_start_identity", lambda _pid: "same-incarnation")
    monkeypatch.setattr(
        session_module,
        "_process_commandline",
        lambda _pid: ("python", "--launch-token", "owned"),
    )
    monkeypatch.setattr(session_cmd.time, "sleep", lambda _seconds: None)

    assert session_cmd._cmd_session_stop(argparse.Namespace(id="default")) == 1
    assert signals[0] == (4242, signal.SIGTERM)
    assert all(sig == signal.SIGTERM or sig == 0 for _pid, sig in signals)
    assert (session_dir / "pid").exists()
    assert (session_dir / "launch.json").exists()
    assert "stop timed out; markers retained" in capsys.readouterr().err


def test_find_active_session_healthy_daemon_survives_missing_source_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A healthy daemon survives even when no source_revision was written at launch.

    If current_source_revision is known but the daemon was launched without
    writing a source_revision file (e.g. git was unavailable), the session
    must not be terminated or hidden.  active_session_metadata() still
    exposes current_source_revision as an advisory diagnostic field.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module, "current_source_revision", lambda: "new-sha")
    monkeypatch.setattr(session_module, "_session_url_healthy", lambda _url: True)
    session_dir = tmp_path / "out/sessions/default"
    session_dir.mkdir(parents=True)
    (session_dir / "pid").write_text("4242", encoding="utf-8")
    (session_dir / "url").write_text("http://127.0.0.1:8200", encoding="utf-8")
    (session_dir / "config.json").write_text('{"port": 8200}', encoding="utf-8")
    # No source_revision file written.

    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    monkeypatch.setattr(session_module.os, "kill", fake_kill)

    # The daemon is healthy — missing source_revision must not hide it.
    assert find_active_session("default") == "http://127.0.0.1:8200"
    # Only the process-aliveness check (os.kill(pid, 0)) — no SIGTERM.
    assert kill_calls == [(4242, 0)]

    # Session files must still be present (no cleanup).
    assert (session_dir / "pid").exists()
    assert (session_dir / "url").exists()
    assert (session_dir / "config.json").exists()
    assert not (session_dir / "source_revision").exists()

    # Advisory metadata still exposes current revision when available.
    meta = session_module.active_session_metadata("default")
    assert meta is not None
    assert meta["current_source_revision"] == "new-sha"
    assert "launch_source_revision" not in meta
    assert meta["url"] == "http://127.0.0.1:8200"


def test_daemon_config_carry_through_typed_and_raw_hiddenswitch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: list[SessionConfig] = []

    class FakeEvent:
        def set(self) -> None:
            pass

        async def wait(self) -> None:
            return None

    class FakeServerSession:
        def __init__(self, config: SessionConfig) -> None:
            self.config = config
            self.url = "http://127.0.0.1:8200"
            captured.append(config)

        async def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(session_cmd.asyncio, "Event", FakeEvent)
    monkeypatch.setattr(session_cmd, "ServerSession", FakeServerSession)

    typed = {
        "port": 8200,
        "memory_profile": 3,
        "vram_policy": "high",
        "reserve_vram_gb": 2.0,
        "cache_policy": "lru:3",
        "warm_policy": "always",
        "input_directory": "/tmp/session-input",
        "output_directory": "/tmp/session-output",
        "temp_directory": "/tmp/session-temp",
        "ready_timeout_sec": 450,
    }
    raw = {
        "reserve_vram": 12,
        "cache_none": True,
        "fp8_e4m3fn_text_enc": True,
        "port": 8200,
    }

    assert asyncio.run(session_cmd._daemon_main(argparse.Namespace(id="typed", config=json.dumps(typed)))) == 0
    assert asyncio.run(session_cmd._daemon_main(argparse.Namespace(id="raw", config=json.dumps(raw)))) == 0

    assert captured[0] == SessionConfig(
        memory_profile=MemoryProfile.LOW_VRAM,
        port=8200,
        vram_policy="high",
        reserve_vram_gb=2.0,
        cache_policy="lru:3",
        warm_policy="always",
        extra={
            "input_directory": "/tmp/session-input",
            "output_directory": "/tmp/session-output",
            "temp_directory": "/tmp/session-temp",
            "ready_timeout_sec": 450,
        },
    )
    assert captured[1] == SessionConfig(
        port=8200,
        reserve_vram_gb=12,
        cache_policy="none",
        extra={"fp8_e4m3fn_text_enc": True},
    )
