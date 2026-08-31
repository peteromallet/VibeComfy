"""Tests for runner exit-code behaviour with deterministic assessment failures."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("sisypy", reason="structural harness tests require the optional Sisypy sibling package")

from tests.harness_common import OUTCOME_FAILED, OUTCOME_FAKE_NO_OP, OUTCOME_PASSED

_HARNESS_RUNNER = Path(__file__).resolve().parents[2] / "tests" / "structural_harness" / "runner.py"


def _run_runner(*extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tests.structural_harness.runner"]
        + list(extra_args),
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(Path(__file__).resolve().parents[2]),
    )


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction from runner output (stderr may be interleaved)."""
    # Try the whole text first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try each line from the end.
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue

    # Try to find the batch summary blob.
    start = text.rfind('{"batch_tag"')
    if start >= 0:
        end = text.rfind("}", start) + 1
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return {}


def test_structural_run_with_all_passing_returns_zero():
    """A structural run where every scenario passes assessment must return
    exit code 0.

    Runs a known-good scenario (add-save-node-finalize) which produces
    complete frozen evidence and passes all deterministic checks including
    the project-level deliverable_shape override.
    """
    from sisypy import summary_exit_code

    result = _run_runner(
        "--mode", "structural",
        "--actor", "fake",
        "--tag", "exit-code-test",
        "--no-parallel",
        "--name", "add-save-node-finalize",
    )

    batch = _extract_json(result.stdout)
    assert batch, f"Could not parse JSON from output.\nSTDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout[-2000:]}"

    expected_exit = summary_exit_code(batch)
    actual_exit = result.returncode

    assert actual_exit == expected_exit, (
        f"Exit code mismatch: runner exited {actual_exit}, "
        f"but summary_exit_code says {expected_exit}.\n"
        f"First scenario outcome: {batch.get('scenarios', [{}])[0].get('runs', [{}])[0].get('outcome')}"
    )
    assert actual_exit == 0, (
        f"Expected exit code 0 for all-passing scenario, got {actual_exit}."
    )

    # Verify the outcome is passed.
    scenarios = batch.get("scenarios", [])
    for ss in scenarios:
        for run_rec in ss.get("runs", []):
            outcome = run_rec.get("outcome", "")
            assert outcome == OUTCOME_PASSED, (
                f"Expected 'passed' for all-passing scenario, got {outcome!r}."
            )


def test_summary_exit_code_treats_assessment_failure_as_failure():
    """summary_exit_code() must return non-zero for a run whose outcome is
    'failed' (which is what _determine_outcome produces when
    assessment.overall_passed is false)."""
    from sisypy import summary_exit_code

    # Simulate a batch summary where a run failed assessment.
    batch = {
        "batch_tag": "test",
        "scenario_count": 1,
        "outcome_counts": {
            OUTCOME_FAILED: 1,
        },
        "has_undetermined": False,
        "has_blocked_or_error": False,
        "scenarios": [
            {
                "scenario_name": "test-scenario",
                "runs": [
                    {
                        "outcome": OUTCOME_FAILED,
                        "dispatcher": "fake",
                        "assessment": {
                            "overall_passed": False,
                            "summary": "Deterministic checks failed: deliverable_shape",
                        },
                    }
                ],
                "outcome_counts": {OUTCOME_FAILED: 1},
                "has_undetermined": False,
            }
        ],
    }
    assert summary_exit_code(batch) == 1

    # Single-scenario shape.
    single = {
        "runs": [
            {
                "outcome": OUTCOME_FAILED,
                "dispatcher": "fake",
                "assessment": {
                    "overall_passed": False,
                    "summary": "Deterministic checks failed: deliverable_shape",
                },
            }
        ],
    }
    assert summary_exit_code(single) == 1


def test_summary_exit_code_fake_no_op_with_no_assessment_still_zero():
    """A bare fake_no_op run without assessment data should still return 0
    (backward-compatible: raw fake_no_op in test data means no assessor ran)."""
    from sisypy import summary_exit_code

    summary = {
        "runs": [
            {"outcome": OUTCOME_FAKE_NO_OP},
        ],
    }
    assert summary_exit_code(summary) == 0


def test_summary_exit_code_passed_returns_zero():
    """A passed outcome returns exit code 0."""
    from sisypy import summary_exit_code

    batch = {
        "scenarios": [
            {
                "runs": [
                    {"outcome": OUTCOME_PASSED},
                ],
            }
        ],
    }
    assert summary_exit_code(batch) == 0
