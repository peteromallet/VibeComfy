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
