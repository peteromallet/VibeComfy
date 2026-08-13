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
