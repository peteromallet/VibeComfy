"""RRSYN-6: diagnosable comparison legs + harness-owned timeout-only retry.

Covers the ``compare_pipeline_modes`` process lane:
* every attempt persists bounded stdout/stderr evidence (never DEVNULL);
* a TIMED-OUT leg is relaunched exactly once under a FRESH attempt identity
  while its locked input stays byte-identical and attempt 1 evidence is
  preserved;
* product failures / non-timeout crashes are NEVER retried;
* an unknown timeout cause stays infra-blocked (never guessed green);
* ``raw_first_attempt_success``, disposition, cost basis and retry owner are
  recorded runner-style on the final summary and the persisted attempts index.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.live_agentic_harness import compare_pipeline_modes as comparator


def _descriptor(scenario_id: str = "retry-probe") -> dict[str, Any]:
    return {"id": scenario_id, "query": "q", "session_id": None}


def _one_descriptor(scenario_id: str = "retry-probe") -> list:
    return [(scenario_id, "staged", _descriptor(scenario_id), "0" * 64)]


def _sleep_stub(seconds: str = "5") -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


# ── spec identity ────────────────────────────────────────────────────────────


def test_attempt_one_spec_bytes_are_unchanged_and_retry_spec_is_fresh(
    tmp_path: Path,
) -> None:
    kwargs = dict(
        scenario=_descriptor("sid"),
        mode="staged",
        locked_input_sha256="a" * 64,
        output_base=tmp_path,
        tag="lane",
        transport=None,
    )
    legacy_path = tmp_path / "a1.json"
    comparator._write_leg_spec(legacy_path, **kwargs)
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    # Attempt 1 keeps its historical byte content (no identity field).
    assert "attempt_identity" not in legacy

    retry_path = tmp_path / "a2.json"
    comparator._write_leg_spec(
        retry_path, **kwargs, attempt_identity="lane/attempts/sid/staged/attempt_2"
    )
    retry = json.loads(retry_path.read_text(encoding="utf-8"))
    # Locked input identical; only the execution identity differs.
    for key in ("scenario", "locked_input_sha256", "mode"):
        assert retry[key] == legacy[key]
    assert retry["attempt_identity"] == "lane/attempts/sid/staged/attempt_2"


def test_child_entry_runs_retry_under_attempt_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_tags: list[str] = []

    def fake_run_mode(scenario, *, mode, locked_input_sha256, output_base, tag, transport):
        seen_tags.append(tag)
        return {"scenario_id": scenario["id"], "status": "success"}

    monkeypatch.setattr(comparator, "_run_mode", fake_run_mode)
    spec_path = tmp_path / "spec.json"
    out_path = tmp_path / "out.json"
    comparator._write_leg_spec(
        spec_path,
        scenario=_descriptor("sid"),
        mode="threaded",
        locked_input_sha256="b" * 64,
        output_base=tmp_path,
        tag="lane",
        transport=None,
        attempt_identity="lane/attempts/sid/threaded/attempt_2",
    )
    assert comparator.run_leg_from_spec(spec_path, out_path) == 0
    assert seen_tags == ["lane/attempts/sid/threaded/attempt_2"]
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True


# ── timeout-only retry, end to end through the real scheduler ────────────────


def test_timed_out_leg_retries_once_under_fresh_identity_and_stays_infra_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(comparator, "_leg_command", lambda spec, out: _sleep_stub())
    monkeypatch.setattr(comparator, "LEG_TIMEOUT_SECONDS", 0.4)

    results = comparator._run_legs_in_processes(
        _one_descriptor(), output_base=tmp_path, tag="lane", transport=None, concurrency=1
    )

    specs_dir = tmp_path / "_legs"
    final = results[0]
    assert isinstance(final, dict)
    # Exactly ONE relaunch: two attempt records, second attempt identity fresh.
    assert final["attempt_count"] == 2
    assert final["final_success"] is False
    assert final["retry_owner"] == comparator.HARNESS_RETRY_OWNER
    # Unknown timeout cause stays infra-blocked — never product, never green.
    assert final["failure_class"] == "infra_timeout"
    assert final["guard"]["score_class"] == "infra_blocked"

    first, second = final["attempts"]
    assert first["attempt"] == 1 and second["attempt"] == 2
    assert first["timed_out"] is True and second["timed_out"] is True
    assert (
        first["retry_ownership"]["retry_disposition"]
        == "not_safe_to_retry_same_identity"
    )
    assert first["retry_ownership"]["remote_uncertainty"] == "timeout_before_response"
    assert second["attempt_identity"].endswith("/attempt_2")
    assert first["attempt_identity"] != second["attempt_identity"]

    # Attempt 1 evidence preserved; per-attempt logs persisted (never DEVNULL).
    assert (specs_dir / "leg_0000_retry-probe_staged.json").is_file()
    assert (specs_dir / "leg_0000_retry-probe_staged.attempt_2.json").is_file()
    for name in (
        "leg_0000_retry-probe_staged.out.log",
        "leg_0000_retry-probe_staged.err.log",
        "leg_0000_retry-probe_staged.attempt_2.out.log",
    ):
        assert (specs_dir / name).is_file(), name
    # A timed-out child is killed before it can persist any result JSON:
    # attempt-1 evidence lives in spec/logs/record, not a result file.
    assert not (specs_dir / "result_0000_retry-probe_staged.json").is_file()
    assert len(first["stdout_tail"]) <= comparator.LEG_LOG_TAIL_CHARS

    index_payload = json.loads(
        (specs_dir / "attempts_0000_retry-probe_staged.json").read_text(
            encoding="utf-8"
        )
    )
    assert index_payload["attempt_count"] == 2
    assert index_payload["raw_first_attempt_success"] is False
    assert len(index_payload["attempts"]) == 2


def test_success_after_timeout_keeps_raw_first_attempt_failure_visible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leg that times out then succeeds keeps raw_first_attempt_success=False."""

    def command(spec: Path, out: Path) -> list[str]:
        if ".attempt_2" in str(spec):
            payload = {
                "ok": True,
                "summary": {
                    "ok": True,
                    "status": "success",
                    # Real _run_mode summaries always carry the typed guard;
                    # final_success derives from it (RR1-FIX-REV).
                    "guard": {
                        "live_agentic_success": True,
                        "score_class": "pass",
                    },
                },
            }
            out.write_text(json.dumps(payload), encoding="utf-8")
            return [sys.executable, "-c", "pass"]
        return _sleep_stub()

    monkeypatch.setattr(comparator, "_leg_command", command)
    monkeypatch.setattr(comparator, "LEG_TIMEOUT_SECONDS", 0.4)

    results = comparator._run_legs_in_processes(
        _one_descriptor(), output_base=tmp_path, tag="lane", transport=None, concurrency=1
    )

    final = results[0]
    assert final["final_success"] is True
    assert final["raw_first_attempt_success"] is False
    assert final["attempt_count"] == 2
    assert final["retried_after_timeout"] is True


def test_product_failure_is_never_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        comparator,
        "_leg_command",
        lambda spec, out: [sys.executable, "-c", "raise SystemExit(3)"],
    )

    results = comparator._run_legs_in_processes(
        _one_descriptor(), output_base=tmp_path, tag="lane", transport=None, concurrency=1
    )

    specs_dir = tmp_path / "_legs"
    final = results[0]
    # Terminal on the first attempt: no second spec/result may exist.
    assert final["attempt_count"] == 1
    assert final["retried_after_timeout"] is False
    assert final["final_success"] is False
    assert final["raw_first_attempt_success"] is False
    assert final["attempts"][0]["retry_ownership"]["retry_disposition"] == "terminal"
    assert not (specs_dir / "leg_0000_retry-probe_staged.attempt_2.json").exists()
    assert not (specs_dir / "result_0000_retry-probe_staged.attempt_2.json").exists()


def test_completed_product_failure_is_final_failure_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RRSYN-6 / RR1-FIX-REV: a child that COMPLETES with a typed
    product-failure guard is not retried and is bookkept as a final failure —
    summary presence alone must never mint final_success=True."""

    def command(spec: Path, out: Path) -> list[str]:
        payload = {
            "ok": True,
            "summary": {
                "ok": True,
                "status": "success",
                "guard": {
                    "live_agentic_success": False,
                    "score_class": "product_fail",
                    "failure_class": "assessment_fail",
                },
            },
        }
        out.write_text(json.dumps(payload), encoding="utf-8")
        return [sys.executable, "-c", "pass"]

    monkeypatch.setattr(comparator, "_leg_command", command)

    results = comparator._run_legs_in_processes(
        _one_descriptor(), output_base=tmp_path, tag="lane", transport=None, concurrency=1
    )

    specs_dir = tmp_path / "_legs"
    final = results[0]
    assert isinstance(final, dict)
    # Completed on attempt 1: terminal, never relaunched.
    assert final["attempt_count"] == 1
    assert final["retried_after_timeout"] is False
    assert final["final_success"] is False
    assert final["raw_first_attempt_success"] is False
    assert final["guard"]["score_class"] == "product_fail"
    assert not (specs_dir / "leg_0000_retry-probe_staged.attempt_2.json").exists()


# ── bounded tails ────────────────────────────────────────────────────────────


def test_bounded_tail_caps_and_tolerates_missing_files(tmp_path: Path) -> None:
    big = tmp_path / "big.log"
    big.write_text("x" * (comparator.LEG_LOG_TAIL_CHARS + 500), encoding="utf-8")
    tail = comparator._bounded_tail(big)
    assert tail is not None and len(tail) == comparator.LEG_LOG_TAIL_CHARS
    assert comparator._bounded_tail(tmp_path / "missing.log") is None
