"""Action 1: 480s reply/research floor, 0-token TimeoutError infra-retry, prose-JSON extraction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.live_agentic_harness.runner import (
    _classify_retryable_infra_summary,
    _is_retryable_infra_summary,
)
from vibecomfy.comfy_nodes.agent import runtime
from vibecomfy.comfy_nodes.agent.contracts import FAILURE_SPECS, FailureKind
from vibecomfy.comfy_nodes.agent.provider import (
    _normalize_turn_response,
    extract_research_json,
)
from vibecomfy.executor.agent_research_stage import parse_agent_research_decision


# ── 480s floor ───────────────────────────────────────────────────────────────


def test_reply_and_research_turns_floor_at_480s() -> None:
    assert runtime._turn_timeout_seconds("hi", stage="reply") == 480.0
    assert runtime._turn_timeout_seconds("hi", stage="research") == 480.0
    assert runtime._turn_timeout_seconds("hi", stage="research_stage") == 480.0


def test_classify_stays_at_240s_default() -> None:
    assert runtime._turn_timeout_seconds("hi", stage="classify") == 240.0
    assert runtime._turn_timeout_seconds("hi", stage=None) == 240.0


def test_timeout_error_contract_is_retryable() -> None:
    spec = FAILURE_SPECS[FailureKind.TIMEOUT_ERROR]
    assert spec.retryable is True


# ── infra-retry classification ───────────────────────────────────────────────


def _timeout_summary(*, tokens: int, kind_on_envelope: bool = False) -> dict:
    summary: dict = {
        "scenario_id": "reply-timeout",
        "status": "error",
        "ok": False,
        "guard": {
            "live_agentic_success": False,
            "score_class": "product_fail",
            "assessment": {"passed": False, "issues": []},
        },
        "deepseek_usage": {
            "prompt_tokens": 80,
            "completion_tokens": tokens,
            "total_tokens": 80 + tokens,
        },
        "model_attempts": [
            {
                "phase": "reply",
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "timeout",
                "token_usage": {
                    "prompt_tokens": 80,
                    "completion_tokens": tokens,
                    "total_tokens": 80 + tokens,
                },
            }
        ],
    }
    if kind_on_envelope:
        summary["failure_kind"] = "TimeoutError"
    return summary


def test_zero_token_reply_timeout_classifies_retryable_infra() -> None:
    summary = _timeout_summary(tokens=0)
    _classify_retryable_infra_summary(summary)
    assert summary["retryable_infra"] is True
    assert summary["failure_class"] == "infra_timeout"
    assert summary["score_class"] == "infra_blocked"
    assert _is_retryable_infra_summary(summary) is True


def test_zero_token_timeout_error_envelope_without_attempts_is_retryable() -> None:
    summary = {
        "scenario_id": "clean-exit-timeout",
        "ok": False,
        "failure_kind": "TimeoutError",
        "deepseek_usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        "guard": {"live_agentic_success": False, "score_class": "product_fail"},
    }
    assert _is_retryable_infra_summary(summary) is True
    assert summary["failure_class"] == "infra_timeout"


def test_product_assessment_failure_is_not_retryable_infra() -> None:
    summary = {
        "scenario_id": "product",
        "ok": False,
        "model_attempts": [
            {
                "phase": "reply",
                "attempt": 1,
                "outcome": "failure",
                "failure_type": "malformed_json",
                "token_usage": {"prompt_tokens": 10, "completion_tokens": 40, "total_tokens": 50},
            }
        ],
        "guard": {"live_agentic_success": False, "score_class": "product_fail"},
    }
    assert _is_retryable_infra_summary(summary) is False
    assert summary.get("retryable_infra") is not True


# ── prose-JSON extraction ────────────────────────────────────────────────────


_CALL = {"action": "call", "tool": "hivemind_search", "args": {"query": "gemini vs claude"}}
_FINISH = {
    "action": "finish",
    "conclusion": "Gemini is faster; Claude is more careful.",
    "evidence_ids": ["hivemind:message_feed:1"],
    "uncertainty": "low",
    "refine_question": None,
}


def test_research_decision_extracts_prose_prefixed_json() -> None:
    raw = "I'll research this systematically… " + json.dumps(_CALL)
    parsed = parse_agent_research_decision(raw)
    assert parsed["action"] == "call"
    assert parsed["tool"] == "hivemind_search"
    assert parsed["args"]["query"] == "gemini vs claude"


def test_research_decision_extracts_json_fence_after_prose() -> None:
    raw = (
        "Here is the tool call.\n"
        "```json\n"
        + json.dumps(_FINISH, indent=2)
        + "\n```\n"
    )
    parsed = parse_agent_research_decision(raw)
    assert parsed["action"] == "finish"
    assert "Gemini" in parsed["conclusion"]


def test_research_decision_still_fails_closed_on_prose_only() -> None:
    with pytest.raises(ValueError, match="malformed JSON"):
        parse_agent_research_decision("I'll research this systematically with no object.")


def test_extract_research_json_from_prose_and_fence() -> None:
    prose = "Let me look that up. " + json.dumps(_CALL)
    assert extract_research_json(prose) == _CALL
    fenced = "```json\n" + json.dumps(_FINISH) + "\n```"
    assert extract_research_json(fenced)["action"] == "finish"
    assert extract_research_json("no object here") is None


def test_normalize_research_turn_extracts_prose_json() -> None:
    raw = "I'll research this systematically… " + json.dumps(_CALL)
    out = _normalize_turn_response(
        {"content": raw, "json": {"decoy": True}},
        response_contract="json",
        phase="research_stage",
    )
    assert out["json"]["action"] == "call"
    assert out["parse_provenance"]["parse_reason"] == "extracted_from_prose"
    assert out["raw_content"] == raw


def test_normalize_classify_path_unchanged_for_research_text_contract() -> None:
    prose = "plain reply text"
    out = _normalize_turn_response(
        {"content": prose},
        response_contract="text",
        phase="reply",
    )
    assert out["content"] == prose
    assert "raw_content" not in out
