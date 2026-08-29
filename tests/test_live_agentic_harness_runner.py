"""Focused tests for live-agentic-harness runner infra reclassification.

Covers G0-T3: a "The model response could not be parsed" failure is retryable
infrastructure ONLY when structured evidence (the attempt's ``deepseek_usage``)
shows the model call observed ``completion_tokens == 0`` — an empty/transport
response.  A nonzero-token parse failure (e.g. markdown instead of JSON) stays
a product failure, as does the phrase with no usage evidence at all.
"""

from __future__ import annotations

from scripts.b09_reducer import _score_class as b09_score_class
from scripts.b09_reducer import _verdict as b09_verdict

from tests.live_agentic_harness.runner import (
    _build_run_summary,
    _classify_retryable_infra_summary,
    _is_retryable_infra_summary,
)

_PARSE_DETAIL = (
    "response.ok is False: The model response could not be parsed. "
    "The graph is unchanged."
)


def _parse_failure_summary(
    *, completion_tokens: int, parse_reason: str = "empty"
) -> dict:
    return {
        "scenario_id": "parse-failure",
        "status": "error",
        "ok": False,
        "output_dir": "out/agentic/tag/parse-failure",
        "parse_reason": parse_reason,
        "deepseek_usage": {
            "prompt_tokens": 900,
            "completion_tokens": completion_tokens,
            "total_tokens": 900 + completion_tokens,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 900,
            "n_calls": 1,
        },
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
        "guard": {
            "live_agentic_success": False,
            "score_class": "product_fail",
            "assessment": {
                "passed": False,
                "issues": [
                    {
                        "check": "response_ok",
                        "severity": "error",
                        "detail": _PARSE_DETAIL,
                    },
                ],
            },
        },
    }


def test_zero_token_parse_failure_classifies_retryable_infra() -> None:
    """Empty model response (completion_tokens == 0) is retryable infra."""
    summary = _parse_failure_summary(completion_tokens=0)

    classified = _classify_retryable_infra_summary(summary)

    assert classified is summary
    assert summary["retryable_infra"] is True
    assert summary["failure_class"] == "infra_empty_response"
    assert summary["score_class"] == "infra_blocked"
    assert summary["guard"]["failure_class"] == "infra_empty_response"
    assert summary["guard"]["score_class"] == "infra_blocked"
    assert _is_retryable_infra_summary(summary) is True


def test_nonzero_token_parse_failure_stays_product_fail() -> None:
    """Model emitted tokens (e.g. markdown instead of JSON) is a product failure."""
    summary = _parse_failure_summary(completion_tokens=512)

    _classify_retryable_infra_summary(summary)

    assert summary.get("retryable_infra") is not True
    assert summary.get("failure_class") is None
    # The classifier leaves non-infra summaries untouched; the guard verdict
    # keeps its product_fail score class.
    assert summary["guard"]["score_class"] == "product_fail"
    assert _is_retryable_infra_summary(summary) is False


def test_parse_phrase_without_usage_evidence_stays_product_fail() -> None:
    """The phrase alone — no token evidence — must never classify as infra."""
    summary = _parse_failure_summary(completion_tokens=0)
    summary["deepseek_usage"] = {}

    _classify_retryable_infra_summary(summary)

    assert summary.get("retryable_infra") is not True
    assert summary.get("failure_class") is None
    assert _is_retryable_infra_summary(summary) is False


def test_timeout_failure_type_classifies_retryable_infra() -> None:
    """RC3: failure_type=timeout is retryable infra (capped at one retry)."""
    summary = {
        "scenario_id": "timeout-failure",
        "status": "error",
        "ok": False,
        "output_dir": "out/agentic/tag/timeout-failure",
        "model_attempts": [
            {
                "phase": "implement",
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "timeout",
                "token_usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 0,
                    "total_tokens": 100,
                },
            }
        ],
        "guard": {
            "live_agentic_success": False,
            "score_class": "product_fail",
            "assessment": {"passed": False, "issues": []},
        },
    }
    classified = _classify_retryable_infra_summary(summary)
    assert classified is summary
    assert summary["retryable_infra"] is True
    assert summary["failure_class"] == "infra_timeout"
    assert _is_retryable_infra_summary(summary) is True


def test_malformed_json_is_not_retryable_infra() -> None:
    summary = {
        "scenario_id": "malformed",
        "status": "error",
        "ok": False,
        "model_attempts": [
            {
                "phase": "classify",
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "malformed_json",
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 40,
                    "total_tokens": 50,
                },
            }
        ],
        "guard": {"live_agentic_success": False, "score_class": "product_fail"},
    }
    assert _is_retryable_infra_summary(summary) is False
    assert summary.get("retryable_infra") is not True


def test_undetermined_guard_class_survives_runner_and_b09_reducer() -> None:
    scenario_summary = {
        "scenario_id": "blocked-missing-response",
        "guard": {
            "live_agentic_success": False,
            "verdict": "undetermined",
            "score_class": "undetermined",
        },
    }

    run_summary = _build_run_summary(
        "truth-contract",
        [scenario_summary],
        total_scenarios=1,
        complete=True,
    )

    assert run_summary["score_classes"] == {"undetermined": 1}
    assert b09_verdict(scenario_summary) == "undetermined"
    assert b09_score_class(scenario_summary) == "undetermined"


def test_undetermined_guard_verdict_overrides_stale_product_score_class() -> None:
    scenario_summary = {
        "scenario_id": "blocked-stale-score",
        "score_class": "product_fail",
        "guard": {
            "live_agentic_success": False,
            "verdict": "undetermined",
            "score_class": "product_fail",
        },
    }

    run_summary = _build_run_summary(
        "truth-contract-stale",
        [scenario_summary],
        total_scenarios=1,
        complete=True,
    )

    assert run_summary["score_classes"] == {"undetermined": 1}
    assert b09_score_class(scenario_summary) == "undetermined"
