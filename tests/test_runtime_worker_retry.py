"""Tests for the transient-stall retry wrapper around ``_run_worker``.

A single agent-edit model turn can stall on a flaky provider connection until
the hard ``_TURN_TIMEOUT_SECONDS`` subprocess kill, or come back as a transient
transport error (connection reset, read timeout, 429, 5xx). Historically both
surfaced immediately as an unrecoverable turn failure the user had to re-submit
by hand (the "make it img2img" symptom: one turn timed out at 180s, the identical
retry succeeded on a fresh connection). ``_run_worker`` now retries those
transient stalls a bounded number of times before giving up.

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


def test_timeout_is_retried_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transient timeout on the first attempt must not kill the whole turn."""
    good = {"content": "ok", "_profiling": {}}
    calls = _stub_once(monkeypatch, [TimeoutError("Agent worker timed out after 180.0 seconds."), good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == good
    assert len(calls) == 2  # one stall + one success
    # The retry is stamped so observability can see it was a transient retry.
    second_profiling = calls[1][1]["profiling_context"]
    assert second_profiling["transient_retry_count"] == 1
    # The original profiling context is preserved across the retry.
    assert second_profiling["model_turn_id"] == "test-turn"


def test_timeout_exhausting_retries_reraises(monkeypatch: pytest.MonkeyPatch) -> None:
    """If every attempt stalls, the timeout surfaces (no silent swallowing)."""
    calls = _stub_once(monkeypatch, [TimeoutError, TimeoutError, TimeoutError])

    with pytest.raises(TimeoutError):
        runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert len(calls) == runtime._WORKER_TRANSIENT_MAX_ATTEMPTS


def test_transient_worker_error_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A transport-class error returned by the worker is retried, not surfaced."""
    transient = {"error": "connection reset", "error_type": "ConnectionError"}
    good = {"content": "ok", "_profiling": {}}
    calls = _stub_once(monkeypatch, [transient, good])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == good
    assert len(calls) == 2


def test_transient_worker_error_exhausting_retries_returns_last_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transient = {"error": "503", "error_type": "APIStatusError"}
    calls = _stub_once(monkeypatch, [transient, transient, transient])

    result = runtime._run_worker({"api_key": "k"}, "sys", "usr", **_common_kwargs())

    assert result == transient
    assert len(calls) == runtime._WORKER_TRANSIENT_MAX_ATTEMPTS


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
