"""Focused tests for live-agentic-harness runner infra reclassification.

Covers G0-T3: a "The model response could not be parsed" failure is retryable
infrastructure ONLY when structured evidence (the attempt's ``deepseek_usage``)
shows the model call observed ``completion_tokens == 0`` — an empty/transport
response.  A nonzero-token parse failure (e.g. markdown instead of JSON) stays
a product failure, as does the phrase with no usage evidence at all.
"""

from __future__ import annotations

from tests.live_agentic_harness.runner import (
    _classify_retryable_infra_summary,
    _is_retryable_infra_summary,
)

_PARSE_DETAIL = (
    "response.ok is False: The model response could not be parsed. "
    "The graph is unchanged."
)


def _parse_failure_summary(*, completion_tokens: int) -> dict:
    return {
        "scenario_id": "parse-failure",
        "status": "error",
        "ok": False,
        "output_dir": "out/agentic/tag/parse-failure",
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
                    {"check": "response_ok", "severity": "error", "detail": _PARSE_DETAIL},
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
