"""Focused regression coverage for live-agentic-harness infra classification.

DEEP-AUDIT-REVIEW-3 finding 004: a RECOVERED classify timeout — a later
SUCCESSFUL attempt in the same phase — must never reclassify a later
product/assessment failure as retryable infrastructure. Only terminal
(unrecovered) failures may drive ``infra_*`` classification and the harness
infra retry policy.
"""

from __future__ import annotations

from typing import Any

from tests.live_agentic_harness.runner import (
    _classify_retryable_infra_summary,
    _is_retryable_infra_summary,
)


def _guard_false_summary(model_attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """A leg whose final guard is FALSE for a product/assessment reason."""
    return {
        "scenario_id": "recovered-timeout-product-failure",
        "status": "error",
        "ok": False,
        "agent_exercised": True,
        "guard": {
            "live_agentic_success": False,
            "metadata_success": False,
            "score_class": "product_fail",
            "assessment": {
                "passed": False,
                "issues": [
                    {
                        "check": "response_ok",
                        "severity": "error",
                        "detail": "The model response could not be parsed.",
                    }
                ],
            },
        },
        "model_attempts": model_attempts,
    }


def test_recovered_classify_timeout_then_product_failure_is_not_infra() -> None:
    """THE finding: [classify timeout, classify success] + guard false is a
    product failure — never infra_timeout/infra_blocked/retryable_infra."""
    summary = _guard_false_summary(
        [
            {"phase": "classify", "attempt": 1, "outcome": "failure",
             "failure_type": "timeout"},
            {"phase": "classify", "attempt": 2, "outcome": "success"},
        ]
    )

    _classify_retryable_infra_summary(summary)

    assert summary.get("failure_class") != "infra_timeout"
    assert summary.get("score_class") != "infra_blocked"
    assert summary.get("retryable_infra") is not True
    assert _is_retryable_infra_summary(summary) is False


def test_terminal_unrecovered_timeout_still_classifies_infra() -> None:
    """Control: a timeout with NO later same-phase success stays infra."""
    summary = _guard_false_summary(
        [
            {"phase": "classify", "attempt": 1, "outcome": "success"},
            {"phase": "implement", "attempt": 1, "outcome": "failure",
             "failure_type": "timeout"},
        ]
    )

    _classify_retryable_infra_summary(summary)

    assert summary["failure_class"] == "infra_timeout"
    assert summary["score_class"] == "infra_blocked"
    assert summary["retryable_infra"] is True
    assert _is_retryable_infra_summary(summary) is True


def test_auth_envelope_is_not_infra_empty_even_when_attempt_says_empty() -> None:
    """Live 401s were stamped empty_response while failure_kind was AuthError."""
    summary = _guard_false_summary(
        [
            {
                "phase": "classify",
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "empty_response",
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            },
        ]
    )
    summary["failure_kind"] = "AuthError"
    summary["error"] = (
        "The model provider rejected authentication. Check your credentials "
        "in Agent Settings."
    )

    _classify_retryable_infra_summary(summary)

    assert summary.get("failure_class") != "infra_empty_response"
    assert summary.get("retryable_infra") is not True
    assert _is_retryable_infra_summary(summary) is False


def test_failed_arnold_turn_with_401_raises_permission_error() -> None:
    from vibecomfy.comfy_nodes.agent.worker import _raise_if_failed_auth_turn

    try:
        _raise_if_failed_auth_turn(
            {
                "failed": True,
                "error": "Error code: 401 - Missing Authentication header",
            },
            "",
        )
    except PermissionError as exc:
        assert "401" in str(exc)
    else:
        raise AssertionError("expected PermissionError for a failed 401 turn")


def test_auth_error_attempt_is_not_infra_empty_response() -> None:
    """A 401 with zero tokens is auth, not an empty model response."""
    summary = _guard_false_summary(
        [
            {
                "phase": "classify",
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "auth_error",
                "token_usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            },
        ]
    )
    summary["error"] = (
        "The model provider rejected authentication. Check your credentials "
        "in Agent Settings."
    )

    _classify_retryable_infra_summary(summary)

    assert summary.get("failure_class") != "infra_empty_response"
    assert summary.get("retryable_infra") is not True
    assert _is_retryable_infra_summary(summary) is False


def test_live_success_is_not_labeled_product_or_assessment_failure() -> None:
    from tests.live_agentic_harness.runner import _attempt_record

    summary = {
        "scenario_id": "passed-edit",
        "status": "success",
        "ok": True,
        "guard": {
            "live_agentic_success": True,
            "verdict": "pass",
            "score_class": "pass",
            "assessment": {"passed": True, "verdict": "pass", "issues": []},
        },
        "model_attempts": [
            {"phase": "classify", "attempt": 1, "outcome": "success", "failure_type": None},
        ],
    }
    record = _attempt_record(
        summary,
        attempt=1,
        attempt_identity="tag/attempts/passed-edit/attempt_1",
        attempt_deadline_seconds=1200.0,
    )
    assert record["failure_class"] != "product_or_assessment_failure"


def test_runtime_unavailable_attempt_is_not_infra_provider_capacity() -> None:
    """Missing Arnold is a blocked runtime, not provider capacity."""
    summary = _guard_false_summary(
        [
            {
                "phase": "classify",
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "runtime_unavailable",
            },
        ]
    )
    summary["error"] = "No module named 'arnold'"

    _classify_retryable_infra_summary(summary)

    assert summary.get("failure_class") != "infra_provider_capacity"
    assert summary.get("retryable_infra") is not True
    assert _is_retryable_infra_summary(summary) is False


def test_recovered_implement_timeout_superseded_by_later_phase_success() -> None:
    """A recovered failure inside ANY phase is superseded by a later success
    in that same phase; only the terminal outcome can classify infra."""
    summary = _guard_false_summary(
        [
            {"phase": "implement", "attempt": 1, "outcome": "failure",
             "failure_type": "provider_failure"},
            {"phase": "implement", "attempt": 2, "outcome": "success"},
            {"phase": "reply", "attempt": 1, "outcome": "success"},
        ]
    )

    _classify_retryable_infra_summary(summary)

    assert summary.get("failure_class") != "infra_provider_capacity"
    assert summary.get("retryable_infra") is not True
