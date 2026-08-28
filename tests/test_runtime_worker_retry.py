"""Tests for the typed-empty-only retry wrapper around ``_run_worker``.

Only a canonical ``empty_response`` attempt with observed zero completion
tokens may receive a fresh subprocess/transport. Timeouts, provider failures,
and malformed non-empty content surface without retry.

These tests drive the wrapper directly by stubbing ``_run_worker_once`` (the
single-shot subprocess call), so no real subprocess or network is involved.
"""
from __future__ import annotations

import pytest

from vibecomfy.comfy_nodes.agent import runtime


def _stub_once(monkeypatch: pytest.MonkeyPatch, behaviors: list) -> list:
    """Replace ``_run_worker_once`` with a recorder that replays ``behaviors``.

    Each behavior is either an ``Exception`` instance/class to raise, or a dict
    to return. Returns the list of (args, kwargs) it was called with.
    """
    calls: list = []
    queue = list(behaviors)

    def fake_once(*args, **kwargs):
        calls.append((args, kwargs))
        behavior = queue.pop(0)
        if isinstance(behavior, BaseException) or (
            isinstance(behavior, type) and issubclass(behavior, BaseException)
        ):
            raise behavior
        return behavior

    monkeypatch.setattr(runtime, "_run_worker_once", fake_once)
    # Don't actually sleep between retries.
    monkeypatch.setattr(runtime.time, "sleep", lambda _s: None)
    return calls


def _common_kwargs():
    return {
        "response_contract": "batch_repl",
        "agent_id": "hermes",
        "model": "openrouter:deepseek/deepseek-v4-pro",
        "effort": "low",
        "profiling_context": {"model_turn_id": "test-turn"},
    }


def _attempt(
    *, outcome: str, failure_type: str | None = None, completion_tokens: int = 1
) -> dict:
    return {
        "phase": "batch",
        "attempt": 1,
        "outcome": outcome,
        "failure_type": failure_type,
        "requested_model": "requested-model",
        "resolved_model": "resolved-model",
        "adapter": "hermes",
        "provider": "openrouter",
        "transport": "openrouter",
        "endpoint": "https://openrouter.ai/api/v1",
        "finish_reason": "stop" if outcome == "success" else "unknown",
        "token_usage": {
            "prompt_tokens": 10,
            "completion_tokens": completion_tokens,
            "total_tokens": 10 + completion_tokens,
        },
    }


def test_timeout_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    good = {"content": "ok", "_profiling": {}}
    calls = _stub_once(monkeypatch, [TimeoutError("Agent worker timed out after 180.0 seconds."), good])

    with pytest.raises(TimeoutError) as raised:
        runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert len(calls) == 1
    assert raised.value.model_attempts[0]["failure_type"] == "timeout"  # type: ignore[attr-defined]


def test_timeout_surfaces_after_one_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_once(monkeypatch, [TimeoutError, TimeoutError, TimeoutError])

    with pytest.raises(TimeoutError):
        runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert len(calls) == 1


def test_untyped_transport_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    transient = {"error": "connection reset", "error_type": "ConnectionError"}
    good = {"content": "ok", "_profiling": {}}
    calls = _stub_once(monkeypatch, [transient, good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == transient
    assert len(calls) == 1


def test_typed_provider_failure_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transient = {
        "error": "503",
        "error_type": "APIStatusError",
        "model_attempts": [_attempt(outcome="failure", failure_type="provider_failure")],
    }
    calls = _stub_once(monkeypatch, [transient, transient, transient])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == transient
    assert len(calls) == 1


def test_typed_empty_zero_token_response_retries_on_fresh_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = {
        "error": "empty",
        "error_type": "ValueError",
        "model_attempts": [
            _attempt(
                outcome="failure",
                failure_type="empty_response",
                completion_tokens=0,
            )
        ],
    }
    good = {
        "content": "ok",
        "model_attempts": [_attempt(outcome="success")],
    }
    calls = _stub_once(monkeypatch, [empty, good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert len(calls) == 2
    assert [item["attempt"] for item in result["model_attempts"]] == [1, 2]
    assert result["model_attempts"][0]["failure_type"] == "empty_response"
    assert "raw_response_preview" not in result["model_attempts"][1]


def test_typed_empty_with_nonzero_tokens_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inconsistent = {
        "error": "empty",
        "error_type": "ValueError",
        "model_attempts": [
            _attempt(outcome="failure", failure_type="empty_response", completion_tokens=2)
        ],
    }
    calls = _stub_once(monkeypatch, [inconsistent])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result["model_attempts"][0]["failure_type"] == "empty_response"
    assert len(calls) == 1


def test_typed_empty_without_observed_usage_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unavailable = _attempt(
        outcome="failure", failure_type="empty_response", completion_tokens=0
    )
    unavailable["token_usage"] = {}
    first = {"error": "empty", "model_attempts": [unavailable]}
    calls = _stub_once(monkeypatch, [first, {"content": "should not run"}])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result["model_attempts"][0]["token_usage"]["completion_tokens"] == "unknown"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "error_type",
    ["ValueError", "JSONDecodeError", "AuthError", "AuthenticationError", "PermissionError"],
)
def test_non_transient_worker_error_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, error_type: str
) -> None:
    """Content/auth errors are owned by other layers and must not burn retry slots."""
    non_transient = {"error": "boom", "error_type": error_type}
    calls = _stub_once(monkeypatch, [non_transient])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == non_transient
    assert len(calls) == 1


def test_runtime_unavailable_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setup faults (missing backend / unregistered adapter) won't recover."""
    unavailable = {
        "error": "no adapter",
        "error_type": "LookupError",
        "runtime_unavailable": True,
    }
    calls = _stub_once(monkeypatch, [unavailable])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == unavailable
    assert len(calls) == 1


def test_success_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    good = {"content": "ok", "_profiling": {}}
    calls = _stub_once(monkeypatch, [good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == good
    assert len(calls) == 1


# ── Cluster B: iteration/token exhaustion correction retry ───────────────────


def _exhaustion_result(*, finish_reason: str, raw: str) -> dict:
    return {
        "error": "Agent response did not match the required contract.",
        "error_type": "ValueError",
        "finish_reason": finish_reason,
        "parse_reason": "malformed_json",
        "raw_response_preview": raw,
        "model_attempts": [
            _attempt(outcome="failure", failure_type="malformed_json", completion_tokens=0)
        ],
    }


def test_finish_reason_length_retries_once_with_correction_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """finish_reason="length" (provider cut the completion off) gets exactly one
    correction retry with a short prompt, then the (better) result wins."""
    exhausted = _exhaustion_result(
        finish_reason="length",
        raw="I reached the iteration limit and couldn't generate a summary.",
    )
    good = {
        "content": '{"reply": "ok"}',
        "json": {"reply": "ok"},
        "model_attempts": [_attempt(outcome="success")],
    }
    calls = _stub_once(monkeypatch, [exhausted, good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == good
    assert len(calls) == 2
    assert [item["attempt"] for item in result["model_attempts"]] == [1, 2]
    # The correction retry carries the short correction prompt appended to the
    # user message (positional arg 2 of _run_worker_once).
    assert "cut off by the model's iteration/token limit" in calls[1][0][2]


def test_iteration_limit_sentinel_retries_once_with_correction_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact iteration-limit sentinel triggers the correction retry even
    when finish_reason is not "length"."""
    sentinel = _exhaustion_result(
        finish_reason="stop",
        raw="I reached the iteration limit and couldn't generate a summary.",
    )
    good = {"content": "ok", "model_attempts": [_attempt(outcome="success")]}
    calls = _stub_once(monkeypatch, [sentinel, good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == good
    assert len(calls) == 2


def test_zero_usable_contract_output_retries_once_with_correction_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-empty-but-unusable worker result (parse failed on prose, no usable
    contract fields) is retried once with the correction prompt."""
    prose = _exhaustion_result(
        finish_reason="stop",
        raw="Here is a detailed explanation of how the workflow works...",
    )
    good = {"content": "ok", "model_attempts": [_attempt(outcome="success")]}
    calls = _stub_once(monkeypatch, [prose, good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == good
    assert len(calls) == 2


def test_iteration_exhaustion_retries_at_most_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The correction retry is bounded: a second exhaustion result surfaces."""
    exhausted = _exhaustion_result(
        finish_reason="length",
        raw="I reached the iteration limit and couldn't generate a summary.",
    )
    calls = _stub_once(monkeypatch, [exhausted, exhausted])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == exhausted
    assert len(calls) == 2
    assert [item["attempt"] for item in result["model_attempts"]] == [1, 2]


def test_iteration_exhaustion_does_not_retry_typed_empty_without_raw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A typed empty response with EMPTY raw text is not an exhaustion result:
    it stays exclusively on the canonical typed-empty transport retry path (and
    with nonzero tokens, surfaces without any retry)."""
    inconsistent = {
        "error": "empty",
        "error_type": "ValueError",
        "model_attempts": [
            _attempt(outcome="failure", failure_type="empty_response", completion_tokens=2)
        ],
    }
    calls = _stub_once(monkeypatch, [inconsistent])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == inconsistent
    assert len(calls) == 1

# ── T3.1: nested-retry ownership freeze ──────────────────────────────────────


class _FakeTime:
    """Deterministic stand-in for the ``time`` module inside runtime."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _empty_error_result() -> dict:
    return {
        "error": "empty",
        "error_type": "ValueError",
        "model_attempts": [
            _attempt(
                outcome="failure",
                failure_type="empty_response",
                completion_tokens=0,
            )
        ],
    }


def test_composed_wall_clock_budget_fails_closed_typed(monkeypatch) -> None:
    """Once the composed turn budget is spent, no further spawn starts and a
    truthful typed exhaustion raises even though transport-retry slots remain."""
    fake_time = _FakeTime()
    monkeypatch.setattr(runtime, "time", fake_time)
    calls: list = []

    def fake_once(*args, **kwargs):
        calls.append((args, kwargs))
        fake_time.now += 400.0  # one spawn burns past the whole 300s budget
        return _empty_error_result()

    monkeypatch.setattr(runtime, "_run_worker_once", fake_once)

    with pytest.raises(TimeoutError) as raised:
        runtime._run_worker(
            {"api_key": "k"},
            "sys",
            "usr",
            deadline=fake_time.monotonic() + 300.0,
            **_common_kwargs(),
        )

    ownership = raised.value.retry_ownership  # type: ignore[attr-defined]
    assert ownership["reason"] == "composed_turn_budget_exhausted"
    assert ownership["retry_owner"] == "harness_infrastructure"
    assert ownership["retry_disposition"] == "not_safe_to_retry_same_identity"
    assert ownership["remote_uncertainty"] == "no_remote_request_issued"
    assert ownership["durable_side_effect_free"] is True
    assert ownership["request_idempotency_key"] is None
    # Fail-closed: only ONE spawn happened although 3 retry slots existed.
    assert len(calls) == 1


def test_timeout_attempt_carries_480s_not_safe_to_retry_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D6 freeze: an in-attempt batch-stage (480s floor) timeout ends with the
    truthful typed exhaustion; the harness alone may retry it, new identity."""
    calls = _stub_once(monkeypatch, [TimeoutError])

    with pytest.raises(TimeoutError) as raised:
        runtime._run_worker(
            {"api_key": "k"},
            "sys",
            "usr",
            response_contract="batch_repl",
            agent_id="hermes",
            model="openrouter:deepseek/deepseek-v4-pro",
            effort="low",
            profiling_context={"backend_phase": "batch", "model_turn_id": "t480"},
        )

    exc = raised.value
    ownership = exc.retry_ownership  # type: ignore[attr-defined]
    assert ownership == {
        "reason": "in_attempt_timeout_not_retried_in_loop",
        "retry_owner": "harness_infrastructure",
        "attempt_deadline_seconds": 480.0,
        "remote_uncertainty": "timeout_before_response",
        "retry_disposition": "not_safe_to_retry_same_identity",
        "durable_side_effect_free": True,
        "request_idempotency_key": None,
    }
    row = exc.model_attempts[0]  # type: ignore[attr-defined]
    assert row["failure_type"] == "timeout"
    assert row["retry_owner"] == "harness_infrastructure"
    assert row["retry_disposition"] == "not_safe_to_retry_same_identity"
    assert row["attempt_deadline_seconds"] == 480.0
    assert len(calls) == 1  # never retried in-loop


def test_retry_rows_record_identity_nesting_deadline_and_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every attempt records owner/nesting/deadline/cost/uncertainty/side-effect
    evidence; the disposition mirrors what the loop actually did."""
    good = {"content": "ok", "model_attempts": [_attempt(outcome="success")]}
    calls = _stub_once(monkeypatch, [_empty_error_result(), good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert len(calls) == 2
    first, second = result["model_attempts"]
    assert first["failure_type"] == "empty_response"
    assert first["retry_owner"] == "runtime_worker_transport"
    assert first["nesting_depth"] == 1
    assert first["attempt_deadline_seconds"] == 240.0
    assert first["remote_uncertainty"] == "response_received"
    assert first["retry_disposition"] == "retry_fresh_subprocess_same_call"
    assert first["durable_side_effect_free"] is True
    assert first["request_idempotency_key"] is None
    assert first["token_usage"]["completion_tokens"] == 0
    assert second["retry_disposition"] == "success_terminal"
    assert second["token_usage"]["total_tokens"] == 11


def test_retry_ownership_vocabulary_is_frozen() -> None:
    """The fixture vocabulary and layer constants are a frozen contract."""
    assert runtime._TURN_TOTAL_BUDGET_SECONDS > 0
    assert runtime._JSON_CONTRACT_MAX_ATTEMPTS == 3
    assert runtime._RETRY_OWNER_WORKER_TRANSPORT == "runtime_worker_transport"
    assert runtime._RETRY_OWNER_HARNESS_INFRASTRUCTURE == "harness_infrastructure"
    assert (
        runtime._RETRY_DISPOSITION_NOT_SAFE_SAME_IDENTITY
        == "not_safe_to_retry_same_identity"
    )
    assert (
        runtime._REMOTE_UNCERTAINTY_TIMEOUT_BEFORE_RESPONSE
        == "timeout_before_response"
    )

def test_reply_timeout_attempt_carries_480s_not_safe_to_retry_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reply-phase turns now share the 480s floor; in-loop timeout still does
    not retry (harness owns the single infra retry under a new identity)."""
    calls = _stub_once(monkeypatch, [TimeoutError])

    with pytest.raises(TimeoutError) as raised:
        runtime._run_worker(
            {"api_key": "k"},
            "sys",
            "usr",
            response_contract="text",
            agent_id="hermes",
            model="openrouter:deepseek/deepseek-v4-pro",
            effort="low",
            profiling_context={"backend_phase": "reply", "model_turn_id": "t-reply"},
        )

    ownership = raised.value.retry_ownership  # type: ignore[attr-defined]
    assert ownership["attempt_deadline_seconds"] == 480.0
    assert ownership["retry_disposition"] == "not_safe_to_retry_same_identity"
    assert len(calls) == 1


def test_research_timeout_attempt_carries_480s_not_safe_to_retry_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stub_once(monkeypatch, [TimeoutError])

    with pytest.raises(TimeoutError) as raised:
        runtime._run_worker(
            {"api_key": "k"},
            "sys",
            "usr",
            response_contract="json",
            agent_id="hermes",
            model="openrouter:deepseek/deepseek-v4-pro",
            effort="low",
            profiling_context={"backend_phase": "research_stage", "model_turn_id": "t-research"},
        )

    ownership = raised.value.retry_ownership  # type: ignore[attr-defined]
    assert ownership["attempt_deadline_seconds"] == 480.0
    assert len(calls) == 1
