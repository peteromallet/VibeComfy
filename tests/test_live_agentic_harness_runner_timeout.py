"""R2-A regression tests: outer runner's inherited-pipe hang + post-flow recovery.

The outer runner previously launched each scenario child with
``subprocess.run(cmd, capture_output=True, timeout=...)``. A grandchild (model
HTTP call / research subprocess) inheriting the captured pipe kept
``communicate()`` blocked forever, so the per-scenario timeout never fired and
the whole scenario hung to the outer kill even after the flow SUCCEEDED
(evidence: ``video-generates-a-video-from-a`` completed with
``flow_metadata.status=success``, all phases ok, ``ok:true``, full artifact set
— yet recorded as 900s ``infra_timeout``/``agent_exercised=false``).

The runner now spawns the child with ``Popen(start_new_session=True)`` and
temp-file stdout/stderr (mirroring ``vibecomfy/comfy_nodes/agent/runtime.py``
PR-A), kills the process GROUP on timeout (SIGTERM → grace → SIGKILL → bounded
reap), and recovers an already-written ``--single-out`` summary as
``post_flow_exit_cleanup`` instead of fabricating ``infra_timeout``.

Each test exercises the REAL ``_run_scenario_subprocess`` (Popen + process-group
kill) against a controllable child fixture
(``live_agentic_harness/fixtures/harness_child.py``); only the child COMMAND is
rewritten to point at the fixture.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from tests.live_agentic_harness import runner
from tests.live_agentic_harness.runner import _run_scenario_subprocess, run_tag
from tests.live_agentic_harness.scenario_manifest import write_manifest

FIXTURE = Path(__file__).parent / "live_agentic_harness" / "fixtures" / "harness_child.py"
_PER_SCENARIO_TIMEOUT = 3
pytestmark = pytest.mark.skipif(
    not (hasattr(os, "killpg") and hasattr(os, "getpgid")),
    reason="Wave 5 contract requires POSIX process-group primitives",
)


def _wait_for_json(path: Path, *, timeout: float = 2.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
            else:
                if isinstance(payload, dict):
                    return payload
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for JSON probe: {path}")


def _wait_for_pids(path: Path, *, timeout: float = 2.0) -> list[int]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                pids = [int(value) for value in path.read_text().split()]
            except (OSError, ValueError):
                pids = []
            if pids:
                return pids
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for child PID: {path}")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_for_dead(pid: int, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.02)
    assert not _pid_alive(pid), f"process {pid} survived process-group cleanup"


def _run_with_fixture(
    monkeypatch,
    tmp_path: Path,
    scenario_id: str,
    fixture_args: list[str],
    *,
    probe_path: Path | None = None,
    pid_file: Path | None = None,
    per_scenario_timeout: float = _PER_SCENARIO_TIMEOUT,
    transport: str = "native",
    capture: dict | None = None,
) -> dict:
    """Run one scenario through the REAL subprocess machinery with the fixture child."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / f"{scenario_id}.json").write_text(
        json.dumps({"id": scenario_id, "query": "do it"}), encoding="utf-8"
    )
    real_run = _run_scenario_subprocess
    monkeypatch.setattr(runner, "_SCENARIO_KILL_GRACE_SECONDS", 0.05)

    def run_fixture(
        cmd,
        *,
        cwd,
        env,
        timeout,
        stdout_path,
        stderr_path,
        before_terminate=None,
    ):  # noqa: ANN001, ANN202
        # ``run_tag`` must leave durable evidence before entering the real
        # Popen/wait path, even if the child then hangs.
        attempt_dir = (
            tmp_path
            / "out"
            / "tag"
            / "attempts"
            / scenario_id
            / "attempt_1"
            / scenario_id
        )
        assert attempt_dir.is_dir()
        partial = json.loads(
            (tmp_path / "out" / "tag" / "run_summary.partial.json").read_text(
                encoding="utf-8"
            )
        )
        assert partial["completed"] == 0
        assert partial["pending"] == 1
        if capture is not None:
            capture["cmd"] = list(cmd)
            capture["cwd"] = cwd
            capture["env"] = dict(env)
            capture["timeout"] = timeout
            capture["stdout_path"] = stdout_path
            capture["stderr_path"] = stderr_path
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        child_cmd = [
            sys.executable,
            str(FIXTURE),
            "--single-out",
            str(out_file),
            "--scenario-id",
            scenario_id,
            *fixture_args,
        ]
        if probe_path is not None:
            child_cmd += ["--probe", str(probe_path)]
        if pid_file is not None:
            child_cmd += ["--pid-file", str(pid_file)]
        result = real_run(
            child_cmd,
            cwd=cwd,
            env=env,
            timeout=timeout,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            before_terminate=before_terminate,
        )
        if capture is not None:
            capture["result"] = result
        return result

    monkeypatch.setattr(
        "tests.live_agentic_harness.runner._run_scenario_subprocess", run_fixture
    )
    write_manifest(scenarios_dir)
    return run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=per_scenario_timeout,
        infra_retries=0,
        progress_every=0,
        transport=transport,
    )


def test_valid_summary_then_exit_with_held_stdio_is_not_a_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Child writes a valid summary, spawns a grandchild HOLDING our stdio fds,
    then exits: the runner must NOT time out (temp files, not pipes) and must
    recover the summary as a plain success well within bounds."""
    capture: dict = {}
    probe = tmp_path / "held-stdio.probe.json"
    pid_file = tmp_path / "held-stdio.pids"
    started = time.monotonic()
    summary = _run_with_fixture(
        monkeypatch,
        tmp_path,
        "held-stdio",
        ["--write-summary", "--hold-stdio", "--hold-seconds", "2"],
        probe_path=probe,
        pid_file=pid_file,
        capture=capture,
    )
    elapsed = time.monotonic() - started

    # The grandchild holds the stdio fds open for 2s; the old pipe-based runner
    # would wait for it, while the new runner returns as soon as the direct
    # child exits because stdout/stderr are regular files.
    assert elapsed < 1.0
    observed = _wait_for_json(probe)
    [grandchild_pid] = _wait_for_pids(pid_file)
    assert observed["module_name"] == "__main__"
    assert observed["pgid"] == observed["pid"]
    assert observed["cwd"] == capture["cwd"]
    assert capture["result"][0] == 0
    assert json.loads(capture["result"][1].strip())["ok"] is True
    assert capture["result"][2] == ""
    scenario = summary["scenarios"][0]
    assert summary["passed"] == 1
    assert summary["infra_failures"] == 0
    assert scenario["attempt_count"] == 1
    assert scenario["guard"]["live_agentic_success"] is True
    assert scenario["agent_exercised"] is True
    assert scenario["attempts"][0]["agent_exercised"] is True
    assert not str(scenario["failure_class"]).startswith("infra_")
    # The helper intentionally outlives the direct child; clean up its group
    # explicitly so the fixture cannot leave a process behind in the test run.
    try:
        runner._terminate_scenario_group(observed["pid"])
    finally:
        _wait_for_dead(grandchild_pid)


def test_real_child_receives_authoritative_command_environment_and_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The run_tag command and env survive exec, without importing the app."""
    monkeypatch.setenv("VIBECOMFY_TRANSPORT", "native")
    monkeypatch.setenv("VIBECOMFY_OPENROUTER_BASE_URL", "https://evil.invalid")
    monkeypatch.setenv("VIBECOMFY_FORCE_MODEL", "evil-model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-openrouter-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-deepseek-key")
    capture: dict = {}
    probe = tmp_path / "identity.probe.json"

    summary = _run_with_fixture(
        monkeypatch,
        tmp_path,
        "identity",
        ["--write-summary"],
        probe_path=probe,
        capture=capture,
    )

    command = capture["cmd"]
    assert command[:3] == [sys.executable, "-m", "tests.live_agentic_harness.runner"]
    assert command[command.index("--single") + 1] == str(
        tmp_path / "scenarios" / "identity.json"
    )
    assert command[command.index("--tag") + 1] == "tag/attempts/identity/attempt_1"
    assert Path(command[command.index("--single-out") + 1]).is_absolute()
    assert command[command.index("--output-base") + 1] == str(tmp_path / "out")
    assert command[command.index("--transport") + 1] == "native"
    assert capture["cwd"] == str(runner.REPO)
    assert capture["env"]["OPENROUTER_API_KEY"] == "fixture-openrouter-key"
    assert capture["env"]["DEEPSEEK_API_KEY"] == "fixture-deepseek-key"
    for key in (
        "VIBECOMFY_TRANSPORT",
        "VIBECOMFY_OPENROUTER_BASE_URL",
        "VIBECOMFY_FORCE_MODEL",
    ):
        assert key not in capture["env"]

    observed = _wait_for_json(probe)
    assert observed["pid"] != os.getpid()
    assert observed["ppid"] == os.getpid()
    assert observed["pgid"] == observed["pid"]
    assert observed["module_name"] == "__main__"
    assert observed["cwd"] == str(runner.REPO)
    assert observed["vibecomfy_modules"] == []
    assert observed["env"]["VIBECOMFY_TRANSPORT"] is None
    assert observed["env"]["VIBECOMFY_OPENROUTER_BASE_URL"] is None
    assert observed["env"]["VIBECOMFY_FORCE_MODEL"] is None
    assert observed["env"]["OPENROUTER_API_KEY"] == "fixture-openrouter-key"
    assert observed["env"]["DEEPSEEK_API_KEY"] == "fixture-deepseek-key"

    [scenario] = summary["scenarios"]
    assert summary["overall_success"] is True
    assert capture["result"][0] == 0
    assert json.loads(capture["result"][1].strip()) == {
        "scenario_id": "identity",
        "ok": True,
    }
    assert capture["result"][2] == ""
    attempt_output = tmp_path / "out" / "tag" / "attempts" / "identity" / "attempt_1" / "identity"
    assert Path(scenario["output_dir"]) == attempt_output
    assert (tmp_path / "out" / "tag" / "identity" / "agentic_summary.json").is_file()
    assert attempt_output.resolve().is_relative_to((tmp_path / "out").resolve())


def test_nonzero_child_without_summary_is_bounded_infra_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    capture: dict = {}
    summary = _run_with_fixture(
        monkeypatch,
        tmp_path,
        "nonzero-no-summary",
        ["--exit-code", "7"],
        capture=capture,
    )

    [scenario] = summary["scenarios"]
    assert capture["result"][0] == 7
    assert capture["result"][1] == ""
    assert capture["result"][2] == ""
    assert scenario["failure_class"] == "infra_no_summary"
    assert scenario["agent_exercised"] is False
    assert summary["overall_success"] is False
    assert summary["infra_failures"] == 1
    assert (tmp_path / "out" / "tag" / "nonzero-no-summary" / "agentic_summary.json").is_file()


def test_valid_summary_then_hang_recovers_post_flow_exit_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Child writes a valid summary then hangs during shutdown: the runner
    times out, kills the group, and RECOVERS the written summary as
    ``post_flow_exit_cleanup`` — never fabricating ``infra_timeout``."""
    probe = tmp_path / "hang-after-summary.probe.json"
    pid_file = tmp_path / "hang-after-summary.pids"
    started = time.monotonic()
    summary = _run_with_fixture(
        monkeypatch,
        tmp_path,
        "hang-after-summary",
        ["--write-summary", "--hang-after-summary", "--hold-seconds", "60"],
        probe_path=probe,
        pid_file=pid_file,
        per_scenario_timeout=0.8,
    )
    assert time.monotonic() - started < 2.0
    observed = _wait_for_json(probe)
    [grandchild_pid] = _wait_for_pids(pid_file)
    _wait_for_dead(observed["pid"])
    _wait_for_dead(grandchild_pid)

    scenario = summary["scenarios"][0]
    assert scenario["attempt_count"] == 1
    # The real child summary was recovered, not a synthetic failure.
    assert scenario["flow_metadata"]["status"] == "success"
    assert scenario["guard"]["live_agentic_success"] is True
    assert scenario["failure_class"] == "post_flow_exit_cleanup"
    assert scenario["guard"]["failure_class"] == "post_flow_exit_cleanup"
    assert scenario["agent_exercised"] is True
    assert scenario["attempts"][0]["failure_class"] == "post_flow_exit_cleanup"
    assert scenario["attempts"][0]["agent_exercised"] is True
    assert scenario["attempts"][0]["elapsed_s"] is not None
    assert summary["passed"] == 1
    assert summary["infra_failures"] == 0


def test_no_summary_then_hang_stays_infra_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Control: a child that never writes a summary and hangs stays a genuine
    ``infra_timeout`` — recovery must never fire without valid evidence."""
    summary = _run_with_fixture(
        monkeypatch,
        tmp_path,
        "never-writes",
        ["--hang-after-summary", "--hold-seconds", "60"],
        per_scenario_timeout=0.8,
    )

    scenario = summary["scenarios"][0]
    assert scenario["attempt_count"] == 1
    assert scenario["failure_class"] == "infra_timeout"
    assert scenario["guard"]["failure_class"] == "infra_timeout"
    assert scenario["agent_exercised"] is False
    assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
    assert scenario["attempts"][0]["agent_exercised"] is False
    assert scenario["attempts"][0]["elapsed_s"] is not None
    assert summary["passed"] == 0
    assert summary["infra_failures"] == 1
    assert summary["score_classes"] == {"infra_blocked": 1}
