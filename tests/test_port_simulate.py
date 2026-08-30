from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from vibecomfy.porting import simulate

from vibecomfy.schema.provider import InputSpec, NodeSchema

def _source(body: str = "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))") -> str:
    return (
        "# vibecomfy: generated\n"
        "from __future__ import annotations\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build() -> VibeWorkflow:\n"
        f"{body}\n"
    )


def _corpus(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        simulate,
        "build_corpus_snapshot",
        lambda _root: SimpleNamespace(
            templates_list=[{"id": "image/case", "path": str(path), "marker": "generated"}]
        ),
    )
    monkeypatch.setattr(simulate, "get_schema_provider", lambda _mode: None)


def test_real_generated_template_is_admitted_and_executes_original_and_transform_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path("ready_templates/image/basic_image_upscale.py").read_text(encoding="utf-8")
    path = tmp_path / "basic_image_upscale.py"
    path.write_text(source + "\n# _set_id_map(\n", encoding="utf-8")
    _corpus(path, monkeypatch)
    calls: list[str] = []
    original = simulate._run_artifact_worker

    def counted(path: Path, *, logical_path: Path) -> dict[str, object]:
        calls.append(path.name)
        return original(path, logical_path=logical_path)

    monkeypatch.setattr(simulate, "_run_artifact_worker", counted)
    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "ok"
    assert result.parity_preserved == 1
    assert result.unsupported == 0
    assert len(calls) == 2
    assert result.schema_snapshot_digest


@pytest.mark.parametrize(
    ("source", "code"),
    [
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport os\n"), "forbidden_environment"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport pathlib\n"), "forbidden_source_read"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport subprocess\n"), "forbidden_process"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport socket\n"), "forbidden_network"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport sqlite3\n"), "forbidden_database"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport random\n"), "forbidden_entropy"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport time\n"), "forbidden_time"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nimport sys\n"), "forbidden_protocol_fd"),
        (_source().replace("# vibecomfy: generated\n", "# vibecomfy: generated\nfrom vibecomfy.schema import get_schema_provider\n"), "arbitrary_provider_import"),
        (_source("    return eval('1')"), "forbidden_dynamic_execution"),
        (_source("    return getattr(VibeWorkflow, 'x')"), "forbidden_introspection"),
        (_source("    return open(__file__).read()"), "forbidden_source_read"),
    ],
)
def test_admission_refuses_each_unsafe_capability(source: str, code: str) -> None:
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.admitted is False
    assert admission.reason is not None
    assert admission.reason["code"] == code
    assert set(admission.reason) == {"code", "message", "line", "column"}


def test_unsupported_is_structured_and_not_parity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "unsafe.py"
    path.write_text(
        "# vibecomfy: generated\n"
        "from __future__ import annotations\n"
        "import os\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build() -> VibeWorkflow:\n"
        "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))\n",
        encoding="utf-8",
    )
    _corpus(path, monkeypatch)

    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "unsupported"
    assert result.unsupported == 1
    assert result.parity_broken == 0
    assert result.parity_preserved == 0
    assert result.per_template[0]["status"] == "unsupported"
    assert result.per_template[0]["parity_ok"] is None
    assert result.per_template[0]["unsupported"]["reason"]["code"] == "forbidden_environment"


@pytest.mark.parametrize(
    ("module", "name"),
    [
        ("vibecomfy.templates", "Path"),
        ("vibecomfy.templates", "inspect"),
        ("vibecomfy.templates", "json"),
        ("vibecomfy.templates", "find_repo_root"),
        ("vibecomfy.workflow", "Path"),
        ("vibecomfy.nodes.core", "_current_workflow_or_raise"),
        ("vibecomfy.patches.resolution", "Path"),
    ],
)
def test_admission_refuses_reexported_or_private_imports(module: str, name: str) -> None:
    source = _source().replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        f"from {module} import {name}\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == "forbidden_import_name"


@pytest.mark.parametrize(
    "body",
    [
        "    Path('/tmp/grok-path-write').write_text('hit')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    source_length = len(Path(__file__).read_text())\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
    ],
)
def test_path_reexports_cannot_write_or_mask_transforms(body: str) -> None:
    source = _source(body).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import Path\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == "forbidden_import_name"


@pytest.mark.parametrize(
    "body",
    [
        "    inspect.sys.modules['os'].system('true')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    inspect.sys.modules['builtins'].eval('1')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    inspect.sys.modules['subprocess'].run(['true'])\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
        "    fd = int(inspect.sys.argv[6])\n    inspect.sys.modules['os'].write(fd, b'CORRUPT')\n    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))",
    ],
)

def test_inspect_reexport_cannot_reach_process_or_protocol(body: str) -> None:
    source = _source(body).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import inspect\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == "forbidden_import_name"

def test_path_write_and_source_read_attacks_never_execute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "path-attack-marker"
    source = _source(
        f"    Path({str(marker)!r}).write_text('PATH_HIT')\n"
        "    source_length = len(Path(__file__).read_text())\n"
        "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))"
    ).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import Path\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    _corpus(Path(tmp_path / "unsafe.py"), monkeypatch)
    unsafe_path = Path(tmp_path / "unsafe.py")
    unsafe_path.write_text(source + "\n# _set_id_map(\n", encoding="utf-8")

    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "unsupported"
    assert result.per_template[0]["changed"] is True
    assert result.per_template[0]["unsupported"]["reason"]["code"] == "forbidden_import_name"
    assert not marker.exists()


@pytest.mark.parametrize(
    "operation",
    [
        "system({marker!r}, 'INSPECT_OS')",
        "eval(f\"open({marker!r}, 'w').write('INSPECT_EVAL')\")",
        "run(['sh', '-c', f\"printf SUBPROCESS > {marker!s}\"])",
    ],
)
def test_inspect_process_attacks_never_execute(
    operation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "inspect-attack-marker"
    if operation.startswith("system"):
        body = f"    inspect.sys.modules['os'].{operation.format(marker=str(marker))}\n"
    elif operation.startswith("eval"):
        body = f"    inspect.sys.modules['builtins'].{operation.format(marker=str(marker))}\n"
    else:
        body = f"    inspect.sys.modules['subprocess'].{operation.format(marker=str(marker))}\n"
    source = _source(
        body + "    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))"
    ).replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        "from vibecomfy.templates import inspect\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    unsafe_path = tmp_path / "unsafe.py"
    unsafe_path.write_text(source, encoding="utf-8")
    _corpus(unsafe_path, monkeypatch)

    result = simulate.simulate_rule("drop_set_id_map=true", ["image/case"])

    assert result.status == "unsupported"
    assert result.per_template[0]["unsupported"]["reason"]["code"] == "forbidden_import_name"
    assert not marker.exists()

@pytest.mark.parametrize(
    ("statement", "code"),
    [
        ("from vibecomfy.templates import Path as benign", "forbidden_import_name"),
        ("from vibecomfy.templates import ReadyMetadata as inspect", "forbidden_import_alias"),
        ("from vibecomfy.nodes.core import LoadImage as open", "forbidden_import_alias"),
    ],
)
def test_import_aliases_cannot_relabel_admitted_or_reexported_names(
    statement: str, code: str
) -> None:
    source = _source().replace(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource",
        statement + "\nfrom vibecomfy.workflow import VibeWorkflow, WorkflowSource",
    )
    admission = simulate.admit_template_source(source)
    assert admission.status == "unsupported"
    assert admission.reason is not None
    assert admission.reason["code"] == code


def test_worker_transport_has_no_protocol_fd_in_argv_or_pass_fds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "safe.py"
    path.write_text(_source(), encoding="utf-8")
    observed: list[tuple[list[str], dict[str, object]]] = []
    original_popen = simulate.subprocess.Popen

    def capture(command, **kwargs):
        observed.append((list(command), dict(kwargs)))
        return original_popen(command, **kwargs)

    monkeypatch.setattr(simulate.subprocess, "Popen", capture)
    result = simulate._run_artifact_worker(path, logical_path=Path("/logical/template.py"))
    assert result["ok"] is True
    assert observed
    command, kwargs = observed[0]
    assert "--protocol-fd" not in command
    assert "pass_fds" not in kwargs
    if os.name == "nt":
        assert "creationflags" in kwargs
    else:
        assert kwargs["start_new_session"] is True


@pytest.mark.skipif(not hasattr(os, "fork"), reason="forked descendant regression requires POSIX")
def test_simulation_timeout_kills_forked_descendant_and_returns_bounded(tmp_path: Path) -> None:
    """A descendant holding captured pipes cannot defeat the timeout reap."""
    marker = tmp_path / "descendant.pid"
    command = [
        sys.executable,
        "-c",
        f"""
import os
import time
marker = {str(marker)!r}
pid = os.fork()
if pid == 0:
    with open(marker, "w") as stream:
        stream.write(str(os.getpid()))
    time.sleep(30)
    os._exit(0)
time.sleep(30)
""",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **simulate._simulation_process_kwargs(),
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.communicate(timeout=0.2)
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "forked descendant did not start"
        descendant_pid = int(marker.read_text(encoding="utf-8"))
        started = time.monotonic()
        warning = simulate._terminate_simulation_process_tree(
            process, owned_pgid=process.pid
        )
        assert warning is not None
        assert "unverified" in warning
        assert time.monotonic() - started < 2
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.01)
        else:
            pytest.fail("forked descendant survived process-group teardown")
    finally:
        if process.poll() is None:
            simulate._terminate_simulation_process_tree(process, owned_pgid=process.pid)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="forked descendant regression requires POSIX")
def test_detached_descendant_reports_incomplete_cleanup(tmp_path: Path) -> None:
    """An escaped descendant cannot make teardown claim success."""
    marker = tmp_path / "detached.pid"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"""
import os
import time
marker = {str(marker)!r}
pid = os.fork()
if pid == 0:
    os.setsid()
    with open(marker, "w") as stream:
        stream.write(str(os.getpid()))
    time.sleep(30)
    os._exit(0)
os._exit(0)
""",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **simulate._simulation_process_kwargs(),
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.communicate(timeout=0.2)
        deadline = time.monotonic() + 2
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "detached descendant did not start"
        warning = simulate._terminate_simulation_process_tree(
            process, owned_pgid=process.pid
        )
        assert warning is not None
        assert "unverified" in warning
    finally:
        if marker.exists():
            try:
                os.kill(int(marker.read_text(encoding="utf-8")), 9)
            except ProcessLookupError:
                pass


def test_permission_error_is_reported_as_incomplete_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None

        def poll(self) -> None:
            return None

        def wait(self, timeout: float) -> int:
            return 0

    process = Process()
    monkeypatch.setattr(simulate.os, "getpgid", lambda _pid: process.pid)

    def deny(_pid: int, _signal: int) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(simulate.os, "killpg", deny)
    warning = simulate._terminate_simulation_process_tree(
        process, owned_pgid=process.pid
    )  # type: ignore[arg-type]
    assert warning is not None
    assert "PermissionError" in warning


def test_posix_signals_recorded_group_before_wait_or_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None

        def poll(self) -> None:
            raise AssertionError("poll must not precede group signaling")

        def wait(self, timeout: float) -> int:
            events.append("wait")
            return 0

    process = Process()
    events: list[object] = []

    def signal_group(pgid: int, signal_number: int) -> None:
        events.append((pgid, signal_number))

    monkeypatch.setattr(simulate.os, "killpg", signal_group)
    warning = simulate._terminate_simulation_process_tree(
        process, owned_pgid=777
    )  # type: ignore[arg-type]
    assert events[0] == (777, simulate.signal.SIGKILL)
    assert events[1] == "wait"
    assert "unverified" in (warning or "")


def test_process_group_absence_is_explicitly_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None

        def wait(self, timeout: float) -> int:
            return 0

    def gone(_pgid: int, _signal_number: int) -> None:
        raise ProcessLookupError("gone")

    monkeypatch.setattr(simulate.os, "killpg", gone)
    warning = simulate._terminate_simulation_process_tree(
        Process(), owned_pgid=12345
    )  # type: ignore[arg-type]
    assert "already absent" in (warning or "")
    assert "unverified" in (warning or "")


def test_windows_uses_retained_handle_and_never_pid_taskkill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None
        killed = False

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: float) -> int:
            return 0

    process = Process()
    monkeypatch.setattr(simulate.os, "name", "nt")
    monkeypatch.setattr(
        simulate.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("PID-based taskkill is unsafe"),
    )
    warning = simulate._terminate_simulation_process_tree(
        process, owned_pgid=None
    )  # type: ignore[arg-type]
    assert process.killed
    assert "unverified" in (warning or "")


def test_communicate_error_cleans_up_and_preserves_original_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None
        waited = False

        def communicate(self, timeout: float) -> tuple[bytes, bytes]:
            raise OSError("pipe broke")

        def poll(self) -> None:
            return None

        def wait(self, timeout: float) -> int:
            self.waited = True
            return 0

    process = Process()
    monkeypatch.setattr(simulate.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(simulate.os, "getpgid", lambda _pid: process.pid)
    monkeypatch.setattr(simulate.os, "killpg", lambda _pid, _signal: None)
    with pytest.raises(OSError, match="pipe broke") as raised:
        simulate._run_artifact_worker(tmp_path / "artifact.py", logical_path=tmp_path / "artifact.py")
    assert process.waited
    assert "unverified" in " ".join(getattr(raised.value, "__notes__", []))


def test_nested_communicate_error_is_reported_after_bounded_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None
        waited = False

        def communicate(self, timeout: float) -> tuple[bytes, bytes]:
            raise ValueError("broken protocol pipe")

        def poll(self) -> None:
            return None

        def wait(self, timeout: float) -> int:
            self.waited = True
            return 0

    process = Process()
    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(simulate.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        simulate,
        "_emit_worker_payload",
        lambda payload, _fd: payloads.append(payload),
    )
    assert simulate._artifact_worker_main(
        ["--_artifact-worker", str(tmp_path / "artifact.py")]
    ) == 0
    assert process.waited
    assert payloads[0]["ok"] is False
    assert "ValueError: broken protocol pipe" in str(payloads[0]["error"])


def test_timeout_detail_requires_explicit_deadline_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(simulate._SIMULATION_DEADLINE_ENV, "ambient-value")
    assert simulate._simulation_timeout_detail(None) == "worker timed out after 30s"
    assert (
        simulate._simulation_timeout_detail(None, simulation_deadline=123.0)
        == "worker timed out before the simulation deadline"
    )


def test_outer_timeout_uses_remaining_absolute_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None
        waited = False

        def communicate(self, timeout: float) -> tuple[bytes, bytes]:
            assert timeout < 0.05
            raise subprocess.TimeoutExpired("worker", timeout)

        def wait(self, timeout: float) -> int:
            self.waited = True
            return 0

    process = Process()
    monkeypatch.setattr(simulate, "_WORKER_TIMEOUT", 0.1)

    def slow_popen(*args: object, **kwargs: object) -> Process:
        time.sleep(0.08)
        return process

    monkeypatch.setattr(simulate.subprocess, "Popen", slow_popen)
    monkeypatch.setattr(simulate.os, "killpg", lambda _pgid, _signal: None)
    with pytest.raises(simulate._ArtifactExecutionError, match="simulation deadline"):
        simulate._run_artifact_worker(tmp_path / "artifact.py", logical_path=tmp_path / "artifact.py")
    assert process.waited


def test_outer_expired_budget_cleans_up_once_without_communicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Stream:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    class Process:
        pid = 12345

        def __init__(self) -> None:
            self.stdout = Stream()
            self.stderr = Stream()
            self.communicates = 0
            self.waits = 0

        def communicate(self, timeout: float) -> tuple[bytes, bytes]:
            self.communicates += 1
            raise AssertionError("communicate must not run after the budget expires")

        def wait(self, timeout: float) -> int:
            self.waits += 1
            return 0

    process = Process()
    monkeypatch.setattr(simulate, "_WORKER_TIMEOUT", 1.0)
    monkeypatch.setattr(simulate.time, "monotonic", iter((10.0, 12.0)).__next__)
    monkeypatch.setattr(simulate.subprocess, "Popen", lambda *args, **kwargs: process)
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(
        simulate.os,
        "killpg",
        lambda pgid, signal_number: killed.append((pgid, signal_number)),
    )

    with pytest.raises(simulate._ArtifactExecutionError, match="simulation deadline"):
        simulate._run_artifact_worker(
            tmp_path / "artifact.py", logical_path=tmp_path / "artifact.py"
        )

    assert process.communicates == 0
    assert process.waits == 1
    assert process.stdout.closed == 1
    assert process.stderr.closed == 1
    assert killed == [(process.pid, simulate.signal.SIGKILL)]


def test_cleanup_wait_and_close_failures_are_accumulated() -> None:
    class Stream:
        def close(self) -> None:
            raise ValueError("closefail")

    class Process:
        pid = 12345
        stdout = Stream()
        stderr = Stream()

        def wait(self, timeout: float) -> int:
            raise OSError("waitfail")

    warning = simulate._terminate_simulation_process_tree(
        Process(), owned_pgid=None
    )  # type: ignore[arg-type]
    assert warning is not None
    assert "waitfail" in warning
    assert warning.count("closefail") == 2


def test_nested_timeout_payload_uses_stable_deadline_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        pid = 12345
        stdout = None
        stderr = None
        waited = False

        def communicate(self, timeout: float) -> tuple[bytes, bytes]:
            raise subprocess.TimeoutExpired("artifact", timeout)

        def wait(self, timeout: float) -> int:
            self.waited = True
            return 0

    process = Process()
    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(simulate.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        simulate,
        "_emit_worker_payload",
        lambda payload, _fd: payloads.append(payload),
    )
    monkeypatch.setattr(simulate.os, "killpg", lambda _pgid, _signal: None)
    monkeypatch.setenv(simulate._SIMULATION_DEADLINE_ENV, "123.0")
    assert simulate._artifact_worker_main(
        ["--_artifact-worker", str(tmp_path / "artifact.py")]
    ) == 0
    assert process.waited
    assert "simulation deadline" in str(payloads[0]["error"])


@pytest.mark.skipif(not hasattr(os, "fork"), reason="forked descendant regression requires POSIX")
def test_nested_simulation_timeout_kills_artifact_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker and artifact-exec layers share one bounded deadline."""
    marker = tmp_path / "artifact-descendant.pid"
    source = tmp_path / "forking_artifact.py"
    source.write_text(
        f"""import os
import time
marker = {str(marker)!r}
pid = os.fork()
if pid == 0:
    with open(marker, "w") as stream:
        stream.write(str(os.getpid()))
    time.sleep(30)
    os._exit(0)
from vibecomfy.workflow import VibeWorkflow, WorkflowSource

def build():
    return VibeWorkflow(id="case", source=WorkflowSource(id="case"))
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(simulate, "_WORKER_TIMEOUT", 12)
    started = time.monotonic()
    with pytest.raises(simulate._ArtifactExecutionError, match="simulation deadline"):
        simulate._run_artifact_worker(source, logical_path=source)
    assert time.monotonic() - started < 14
    descendant_pid = int(marker.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            os.kill(descendant_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.01)
    else:
        pytest.fail("artifact descendant survived nested process-tree teardown")


def test_logical_file_is_preserved_by_worker(tmp_path: Path) -> None:
    path = tmp_path / "logical.py"
    path.write_text(
        "# vibecomfy: generated\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    return VibeWorkflow(id='logical', source=WorkflowSource(id='logical', path=__file__))\n",
        encoding="utf-8",
    )
    result = simulate._run_artifact_worker(path, logical_path=Path("/logical/template.py"))
    assert result["envelope"]["source"]["path"] == "/logical/template.py"

def test_protocol_payload_is_bounded() -> None:
    read_fd, write_fd = os.pipe()
    try:
        simulate._emit_worker_payload({"ok": True, "data": "x" * simulate._PROTOCOL_LIMIT}, write_fd)
        os.close(write_fd)
        write_fd = -1
        payload = os.fdopen(read_fd, "rb").read()
        read_fd = -1
        assert len(payload) < simulate._PROTOCOL_LIMIT
        assert json.loads(payload)["ok"] is False
    finally:
        if write_fd >= 0:
            os.close(write_fd)
        if read_fd >= 0:
            os.close(read_fd)


def test_schema_snapshot_is_frozen_before_worker_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "schema.py"
    path.write_text(_source("    return VibeWorkflow(id='case', source=WorkflowSource(id='case'))"), encoding="utf-8")
    _corpus(path, monkeypatch)
    class Provider:
        calls = 0
        def schemas(self):
            self.calls += 1
            return {}
        def get_schema(self, _class_type):
            raise AssertionError("worker/provider lookup must not occur")
    provider = Provider()
    result = simulate.simulate_rule("drop_set_id_map=false", ["image/case"], schema_provider=provider)
    assert result.status == "ok"
    assert provider.calls == 1
    assert result.schema_snapshot_digest


def test_schema_snapshot_serialization_freezes_provider_drift() -> None:
    class Provider:
        version = 1

        def schemas(self):
            return {
                "Demo": NodeSchema(
                    class_type="Demo",
                    pack="test",
                    inputs={"value": InputSpec(type="INT", default=self.version)},
                    outputs=[],
                )
            }

    provider = Provider()
    payload = simulate._freeze_schema_snapshot(provider, {"Demo"})
    provider.version = 2
    frozen = simulate.schema_snapshot_provider_from_payload(payload)
    assert frozen.get_schema("Demo").inputs["value"].default == 1
