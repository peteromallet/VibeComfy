from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.live_agentic_harness.runner import (
    _persist_run_summary,
    _persist_scenario_summary,
    run_tag,
)


def _summary(tmp_path: Path, scenario_id: str, *, ok: bool) -> dict:
    output_dir = tmp_path / "tag" / scenario_id
    return {
        "scenario_id": scenario_id,
        "status": "success" if ok else "error",
        "output_dir": str(output_dir),
        "guard": {"live_agentic_success": ok},
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
        "model_attempts": [],
    }


def _failed_attempt(failure_type: str, *, completion_tokens: int = 0) -> dict:
    return {
        "phase": "classify",
        "attempt": 1,
        "outcome": "failure",
        "failure_type": failure_type,
        "requested_model": "requested",
        "resolved_model": "resolved",
        "adapter": "hermes",
        "provider": "openrouter",
        "transport": "openrouter",
        "endpoint": "https://openrouter.ai/api/v1",
        "finish_reason": "unknown",
        "token_usage": {
            "prompt_tokens": 10,
            "completion_tokens": completion_tokens,
            "total_tokens": 10 + completion_tokens,
        },
    }


def test_persists_per_scenario_and_incremental_run_summary(tmp_path: Path) -> None:
    passing = _summary(tmp_path, "passing", ok=True)
    failing = _summary(tmp_path, "failing", ok=False)

    _persist_scenario_summary(passing, tmp_path, "tag")
    _persist_scenario_summary(failing, tmp_path, "tag")
    partial = _persist_run_summary(
        "tag",
        [passing, failing, None],
        tmp_path,
        total_scenarios=3,
        complete=False,
    )

    assert partial["passed"] == 1
    assert partial["failed"] == 1
    assert partial["pending"] == 1
    assert partial["complete"] is False
    assert (tmp_path / "tag" / "passing" / "agentic_summary.json").exists()
    assert (tmp_path / "tag" / "failing" / "agentic_summary.json").exists()
    assert (tmp_path / "tag" / "run_summary.partial.json").exists()

    persisted = json.loads((tmp_path / "tag" / "run_summary.partial.json").read_text())
    assert persisted["passed"] == 1
    assert persisted["failed"] == 1


def test_final_summary_replaces_partial_summary(tmp_path: Path) -> None:
    passing = _summary(tmp_path, "passing", ok=True)

    _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=False)
    final = _persist_run_summary("tag", [passing], tmp_path, total_scenarios=1, complete=True)

    assert final["complete"] is True
    assert final["overall_success"] is True
    assert (tmp_path / "tag" / "run_summary.json").exists()
    assert not (tmp_path / "tag" / "run_summary.partial.json").exists()


def test_runner_does_not_retry_outer_timeout(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "retry-me.json"
    scenario_path.write_text(json.dumps({"id": "retry-me", "query": "do it"}), encoding="utf-8")

    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "retry-me"
        payload = _summary(tmp_path / "out" / tag, "retry-me", ok=True)
        payload["output_dir"] = str(output_dir)
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 1
    assert summary["passed"] == 0
    assert summary["raw_first_attempt_passed"] == 0
    assert scenario["attempt_count"] == 1
    assert scenario["attempts"][0]["failure_class"] == "infra_timeout"
    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
    assert scenario["attempts"][0]["agent_exercised"] is False
    assert scenario["attempts"][0]["elapsed_s"] is not None
    assert (
        tmp_path / "out" / "tag" / "retry-me" / "agentic_summary.json"
    ).exists()


def test_runner_types_provider_capacity_without_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "provider-capacity.json"
    scenario_path.write_text(
        json.dumps({"id": "provider-capacity", "query": "do it"}),
        encoding="utf-8",
    )

    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "provider-capacity"
        if calls == 1:
            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=False)
            payload.update(
                {
                    "status": "executor_failure",
                    "error": (
                        "OpenRouter rejected the request because the account does "
                        "not have enough credits for the requested token budget."
                    ),
                    "output_dir": str(output_dir),
                    "model_attempts": [_failed_attempt("provider_failure")],
                    "guard": {
                        "live_agentic_success": False,
                        "score_class": "product_fail",
                        "assessment": {
                            "passed": False,
                            "issues": [
                                {
                                    "check": "response_ok",
                                    "severity": "error",
                                    "detail": (
                                        "response.ok is False: OpenRouter rejected "
                                        "the request because the account does not "
                                        "have enough credits for the requested token budget."
                                    ),
                                }
                            ],
                        },
                    },
                }
            )
        else:
            payload = _summary(tmp_path / "out" / tag, "provider-capacity", ok=True)
            payload["output_dir"] = str(output_dir)
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 1
    assert summary["passed"] == 0
    assert summary["raw_first_attempt_passed"] == 0
    assert scenario["attempt_count"] == 1
    assert scenario["attempts"][0]["failure_class"] == "infra_provider_capacity"
    assert scenario["attempts"][0]["score_class"] == "infra_blocked"
    assert scenario["attempts"][0]["retryable_infra"] is False


def test_runner_retries_only_typed_empty_zero_token_attempt(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "typed-empty.json"
    scenario_path.write_text(json.dumps({"id": "typed-empty", "query": "do it"}), encoding="utf-8")
    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "typed-empty", ok=calls > 1)
        payload["output_dir"] = str(tmp_path / "out" / tag / "typed-empty")
        if calls == 1:
            payload["error"] = "arbitrary wording that must not drive classification"
            payload["model_attempts"] = [_failed_attempt("empty_response", completion_tokens=0)]
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 2
    assert scenario["attempts"][0]["failure_class"] == "infra_empty_response"
    assert scenario["attempts"][0]["model_attempts"][0]["failure_type"] == "empty_response"
    assert scenario["attempts"][1]["live_agentic_success"] is True


def test_runner_keeps_malformed_nonempty_as_product_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "malformed.json"
    scenario_path.write_text(json.dumps({"id": "malformed", "query": "do it"}), encoding="utf-8")
    calls = 0

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        payload = _summary(tmp_path / "out" / tag, "malformed", ok=False)
        payload["output_dir"] = str(tmp_path / "out" / tag / "malformed")
        payload["error"] = "OpenRouter rejected / HTTP 429 wording is irrelevant"
        payload["model_attempts"] = [_failed_attempt("malformed_json", completion_tokens=5)]
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert calls == 1
    assert scenario["score_class"] == "product_fail"
    assert scenario.get("retryable_infra") is not True


def test_runner_counts_persistent_provider_capacity_as_infra_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "provider-down.json"
    scenario_path.write_text(json.dumps({"id": "provider-down", "query": "do it"}), encoding="utf-8")

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "provider-down"
        payload = _summary(tmp_path / "out" / tag, "provider-down", ok=False)
        payload.update(
            {
                "status": "executor_failure",
                "error": "HTTP Error 429: Too Many Requests",
                "output_dir": str(output_dir),
                "model_attempts": [_failed_attempt("provider_failure")],
                "guard": {
                    "live_agentic_success": False,
                    "score_class": "product_fail",
                    "assessment": {"passed": False, "issues": []},
                },
            }
        )
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert scenario["attempt_count"] == 1
    assert scenario["failure_class"] == "infra_provider_capacity"
    assert scenario["score_class"] == "infra_blocked"
    assert summary["passed"] == 0
    assert summary["infra_failures"] == 1
    assert summary["product_or_assessment_failures"] == 0
    assert summary["score_classes"] == {"infra_blocked": 1}


def test_runner_does_not_classify_soft_search_429_as_infra(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "soft-search-warning.json"
    scenario_path.write_text(
        json.dumps({"id": "soft-search-warning", "query": "do it"}),
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202, ARG001
        out_file = Path(cmd[cmd.index("--single-out") + 1])
        tag = cmd[cmd.index("--tag") + 1]
        output_dir = tmp_path / "out" / tag / "soft-search-warning"
        payload = _summary(tmp_path / "out" / tag, "soft-search-warning", ok=False)
        payload.update(
            {
                "status": "success",
                "error": None,
                "output_dir": str(output_dir),
                "guard": {
                    "live_agentic_success": False,
                    "score_class": "product_fail",
                    "assessment": {
                        "passed": False,
                        "issues": [
                            {
                                "check": "graph_changed",
                                "severity": "error",
                                "detail": "Expected graph change but response.graph_unchanged is True.",
                            },
                            {
                                "check": "soft_warning",
                                "severity": "warning",
                                "detail": "web search: brave search HTTP error: HTTP Error 429: Too Many Requests",
                            },
                        ],
                    },
                },
            }
        )
        out_file.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")

    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=1,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert scenario["attempt_count"] == 1
    assert scenario["failure_class"] == "product_or_assessment_failure"
    assert scenario["score_class"] == "product_fail"
    assert scenario.get("retryable_infra") is not True
    assert summary["infra_failures"] == 0
    assert summary["product_or_assessment_failures"] == 1


def test_runner_timeout_preserves_scenario_graph_change_expectation(
    tmp_path: Path,
    monkeypatch,
) -> None:  # noqa: ANN001
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    scenario_path = scenarios_dir / "diagnose.json"
    scenario_path.write_text(
        json.dumps(
            {
                "id": "diagnose",
                "query": "explain the graph",
                "assessment": {"expect_graph_changed": False},
            }
        ),
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN202
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))

    monkeypatch.setattr("tests.live_agentic_harness.runner.subprocess.run", fake_run)

    summary = run_tag(
        "tag",
        scenarios_dir=scenarios_dir,
        output_base=tmp_path / "out",
        max_workers=1,
        per_scenario_timeout=1,
        infra_retries=0,
        progress_every=0,
    )

    scenario = summary["scenarios"][0]
    assert scenario["guard"]["assessment"]["expect_graph_changed"] is False
    assert scenario["failure_class"] == "infra_timeout"
    assert summary["infra_failures"] == 1
