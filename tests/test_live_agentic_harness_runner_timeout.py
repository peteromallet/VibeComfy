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
import sys
import time
from pathlib import Path

from tests.live_agentic_harness.runner import _run_scenario_subprocess, run_tag
from tests.live_agentic_harness.scenario_manifest import write_manifest

FIXTURE = Path(__file__).parent / "live_agentic_harness" / "fixtures" / "harness_child.py"
_PER_SCENARIO_TIMEOUT = 3


def _run_with_fixture(
    monkeypatch,
    tmp_path: Path,
    scenario_id: str,
    fixture_args: list[str],
) -> dict:
    """Run one scenario through the REAL subprocess machinery with the fixture child."""
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / f"{scenario_id}.json").write_text(
        json.dumps({"id": scenario_id, "query": "do it"}), encoding="utf-8"
    )
    real_run = _run_scenario_subprocess

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
        return real_run(
            child_cmd,
            cwd=cwd,
            env=env,
            timeout=timeout,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            before_terminate=before_terminate,
        )

    monkeypatch.setattr(
        "tests.live_agentic_harness.runner._run_scenario_subprocess", run_fixture
    )
    write_manifest(scenarios_dir)
    return run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=_PER_SCENARIO_TIMEOUT,
        infra_retries=0,
        progress_every=0,
    )


def test_valid_summary_then_exit_with_held_stdio_is_not_a_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Child writes a valid summary, spawns a grandchild HOLDING our stdio fds,
    then exits: the runner must NOT time out (temp files, not pipes) and must
    recover the summary as a plain success well within bounds."""
    started = time.monotonic()
    summary = _run_with_fixture(
        monkeypatch,
        tmp_path,
        "held-stdio",
        ["--write-summary", "--hold-stdio"],
    )
    elapsed = time.monotonic() - started

    # The grandchild holds the stdio fds open for 60s; the old pipe-based
    # runner would hang past that. The new runner returns as soon as the
    # direct child exits — far below the per-scenario timeout.
    assert elapsed < 10.0
    scenario = summary["scenarios"][0]
    assert summary["passed"] == 1
    assert summary["infra_failures"] == 0
    assert scenario["attempt_count"] == 1
    assert scenario["guard"]["live_agentic_success"] is True
    assert scenario["agent_exercised"] is True
    assert scenario["attempts"][0]["agent_exercised"] is True
    assert not str(scenario["failure_class"]).startswith("infra_")


def test_valid_summary_then_hang_recovers_post_flow_exit_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Child writes a valid summary then hangs during shutdown: the runner
    times out, kills the group, and RECOVERS the written summary as
    ``post_flow_exit_cleanup`` — never fabricating ``infra_timeout``."""
    summary = _run_with_fixture(
        monkeypatch,
        tmp_path,
        "hang-after-summary",
        ["--write-summary", "--hang-after-summary"],
    )

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
        ["--hang-after-summary"],
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
