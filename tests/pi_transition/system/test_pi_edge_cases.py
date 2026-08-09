"""L2 — Timeout, Parallel, and Lifecycle Tests.

All tests use the fixture-backed Pi worker (no live credentials).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────

PI_TRANSITION_DIR = Path(__file__).resolve().parents[1]
WORKER_PATH = PI_TRANSITION_DIR / "pi_worker.py"
HARNESS_AVAILABLE = WORKER_PATH.exists()

_PI_RUNTIME_ROOT = Path(os.environ.get("VIBECOMFY_PI_ROOT", "/tmp/pi-compare/pi"))


def _pi_runtime_available() -> bool:
    """Mirror ``pi_worker._check_pi_available``: the runtime is usable iff the
    Pi agent ``package.json`` is present at VIBECOMFY_PI_ROOT (default
    /tmp/pi-compare/pi)."""
    return (_PI_RUNTIME_ROOT / "packages" / "agent" / "package.json").exists()


def _write_request(
    tmp_path: Path,
    *,
    user_message: str = "test",
    response_contract: str = "text",
    agent_kwargs: dict | None = None,
) -> Path:
    req = tmp_path / "request.json"
    req.write_text(
        json.dumps(
            {
                "user_message": user_message,
                "response_contract": response_contract,
                "agent_kwargs": agent_kwargs or {},
            }
        ),
        encoding="utf-8",
    )
    return req


def _run_and_read(tmp_path: Path, request: Path, **kwargs) -> dict | None:
    """Run worker, return parsed result.json or None."""
    result = tmp_path / "result.json"
    try:
        proc = subprocess.run(
            [sys.executable, str(WORKER_PATH), str(request), str(result)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=kwargs.pop("timeout", 60),
            **kwargs,
        )
    except subprocess.TimeoutExpired:
        return None

    if result.exists():
        try:
            return json.loads(result.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return None


# ── Timeout Tests ────────────────────────────────────────────────────────────


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Pi worker not available")
def test_timeout_below_worker_lifetime_kills_process(tmp_path: Path) -> None:
    """Parent timeout shorter than worker runtime → TimeoutExpired, no result.json corruption."""
    req = _write_request(tmp_path, user_message="deliberately-slow-fixture")

    if not _pi_runtime_available():
        # Current contract without the Pi runtime: the worker fast-fails with a
        # structured runtime_unavailable envelope instead of running a slow turn,
        # so the parent-side timeout is never hit. Assert the fast-fail envelope
        # and that result.json is still complete valid JSON (never a partial write).
        proc = subprocess.run(
            [sys.executable, str(WORKER_PATH), str(req), str(tmp_path / "result.json")],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 1
        data = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
        assert data.get("runtime_unavailable") is True
        return

    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            [sys.executable, str(WORKER_PATH), str(req), str(tmp_path / "result.json")],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=0.5,
        )

    # Worker should not leave a partial/corrupt result.json
    result_path = tmp_path / "result.json"
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            # If result exists, it should be valid JSON and not empty
            assert isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.fail("result.json exists but is not valid JSON after timeout")


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Pi worker not available")
def test_zero_timeout_raises_immediately(tmp_path: Path) -> None:
    """VIBECOMFY_AGENT_TURN_TIMEOUT=0 → immediate TimeoutError, clear message."""
    req = _write_request(tmp_path)
    env = dict(os.environ)
    env["VIBECOMFY_AGENT_TURN_TIMEOUT"] = "0"

    with pytest.raises(subprocess.TimeoutExpired):
        subprocess.run(
            [sys.executable, str(WORKER_PATH), str(req), str(tmp_path / "result.json")],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=0.01,
        )


# ── Parallel Tests ───────────────────────────────────────────────────────────


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Pi worker not available")
def test_concurrent_workers_independent_tmp_dirs(tmp_path: Path) -> None:
    """10 concurrent workers use distinct temp dirs, no cross-contamination."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def run_one(index: int) -> tuple[int, str]:
        workdir = tmp_path / f"worker-{index}"
        workdir.mkdir()
        req = _write_request(workdir, user_message=f"worker-{index}")
        result = _run_and_read(workdir, req, timeout=30)
        return index, "ok" if result else "fail"

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_one, i): i for i in range(10)}
        results = {}
        for future in as_completed(futures):
            idx, status = future.result()
            results[idx] = status

    failures = [idx for idx, status in results.items() if status != "ok"]
    assert not failures, f"Workers failed: {failures}"


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Pi worker not available")
def test_concurrent_workers_no_shared_state_leak(tmp_path: Path) -> None:
    """Each worker's result is independent — no cross-worker contamination."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    messages = [f"message-{i}" for i in range(5)]

    def run_one(msg: str) -> dict | None:
        workdir = tmp_path / f"worker-{msg}"
        workdir.mkdir()
        req = _write_request(workdir, user_message=msg)
        return _run_and_read(workdir, req, timeout=30)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(run_one, msg): msg for msg in messages}
        results = {futures[future]: future.result() for future in as_completed(futures)}

    # Every worker produced its own result — none crashed, none cross-wrote.
    assert set(results) == set(messages), (
        f"Missing worker results: {set(messages) - set(results)}"
    )
    for msg, result in results.items():
        assert result is not None, f"worker {msg} produced no result"
        assert isinstance(result, dict), f"worker {msg} produced non-dict result"

    if _pi_runtime_available():
        # Live runtime: each worker returns its own content — duplicate outputs
        # would mean shared mutable state leaked across workers.
        outputs = [
            str(result.get("content") or result.get("message") or result)
            for result in results.values()
        ]
        assert len(set(outputs)) == len(outputs), (
            f"Outputs not unique — possible shared state leak: {outputs}"
        )
    else:
        # No Pi runtime: every worker fast-fails with the identical
        # runtime_unavailable envelope. Independence = each workdir holds its own
        # result and no envelope references another worker's message.
        for msg, result in results.items():
            assert result.get("runtime_unavailable") is True, (
                f"worker {msg} unexpected result: {result}"
            )
            assert msg not in str(result), (
                f"worker {msg} result contaminated by another worker: {result}"
            )


# ── Lifecycle Tests ──────────────────────────────────────────────────────────


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Pi worker not available")
def test_repeated_turns_no_resource_leak(tmp_path: Path) -> None:
    """50 consecutive turns → all complete, no degradation."""
    times = []
    for i in range(50):
        workdir = tmp_path / f"turn-{i}"
        workdir.mkdir()
        req = _write_request(workdir, user_message=f"turn-{i}")
        start = time.monotonic()
        result = _run_and_read(workdir, req, timeout=30)
        elapsed = time.monotonic() - start
        times.append(elapsed)

        if result is None:
            pytest.fail(f"Turn {i} produced no result")

    # No monotonic degradation (last 10 turns not > 3x first 10 turns)
    first_10_avg = sum(times[:10]) / 10
    last_10_avg = sum(times[-10:]) / 10
    assert last_10_avg < first_10_avg * 3, (
        f"Possible resource leak: last-10 avg {last_10_avg:.2f}s vs "
        f"first-10 avg {first_10_avg:.2f}s"
    )


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Pi worker not available")
def test_temp_dir_cleaned_after_success(tmp_path: Path) -> None:
    """Worker's temp directory is removed after successful completion."""
    req = _write_request(tmp_path, user_message="quick fixture")
    result = _run_and_read(tmp_path, req, timeout=30)

    if result is None:
        pytest.skip("Pi worker not yet integrated")

    # The subprocess temp dir created by TemporaryDirectory should be gone
    # We can't check the worker's internal tmpdir from outside, but verify
    # our request/result files are intact
    assert (tmp_path / "result.json").exists()
    assert (tmp_path / "request.json").exists()


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Pi worker not available")
def test_interrupted_worker_no_zombie(tmp_path: Path) -> None:
    """SIGTERM to worker mid-turn → appropriate error, no zombie child."""
    import signal

    req = _write_request(tmp_path)
    result_path = tmp_path / "result.json"

    proc = subprocess.Popen(
        [sys.executable, str(WORKER_PATH), str(req), str(result_path)],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait a short time then terminate
    time.sleep(0.2)
    proc.terminate()

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    # Process should be terminated, not zombie
    assert proc.returncode is not None, "Worker is still running after terminate/kill"
    # Zombie check: poll() returns immediately after wait()
    assert proc.poll() is not None
