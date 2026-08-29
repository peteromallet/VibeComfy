from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from vibecomfy.executor.contracts import ClassifyDecision, ExecutorRequest
from vibecomfy.executor.core import run_executor


def test_classify_only_skips_research_implement_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ClassifyDecision.edit(route="adapt", plan_summary="test summary")
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )
    reply_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_reply",
        lambda *args, **kwargs: reply_calls.append(args) or "should not run",
    )
    research_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_research",
        lambda *args, **kwargs: research_calls.append(args) or None,
    )
    implement_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_implement",
        lambda *args, **kwargs: implement_calls.append(args) or None,
    )

    request = ExecutorRequest(query="add a brightness node")
    result = run_executor(request, classify_only=True)

    assert result.ok is True
    assert result.reply is not None
    assert "dry-run" in result.reply
    assert "adapt" in result.reply
    assert result.report.plan.effective_route == "adapt"
    assert result.graph is None
    assert not research_calls
    assert not implement_calls
    assert not reply_calls


def test_classify_only_does_not_resolve_post_classify_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ClassifyDecision.edit(route="adapt", plan_summary="test summary")

    def _resolve_spec(_profile: str | None, stage: str) -> object:
        if stage != "classify":
            raise AssertionError(f"unexpected {stage} spec resolution")
        return SimpleNamespace(agent="test", model="test-model", effort="high")

    monkeypatch.setattr("vibecomfy.executor.core._resolve_spec", _resolve_spec)
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )

    result = run_executor(ExecutorRequest(query="add a brightness node"), classify_only=True)

    assert result.ok is True
    assert result.report.plan.effective_route == "adapt"


def test_classify_only_failure_captured_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor.core import _ExecutorPhaseError

    def _raise(*args, **kwargs):
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind="model_error",
            message="model refused",
        )

    monkeypatch.setattr("vibecomfy.executor.core._run_classify", _raise)

    request = ExecutorRequest(query="do something")
    result = run_executor(request, classify_only=True)

    assert result.ok is False
    assert result.failure_stage == "classify"
    assert "model refused" in (result.failure_message or "")


def test_full_run_does_not_skip_phases_when_classify_only_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = ClassifyDecision.respond_only(route="respond")
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )
    reply_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_reply",
        lambda *args, **kwargs: reply_calls.append(args) or "reply text",
    )

    request = ExecutorRequest(query="hello")
    result = run_executor(request, classify_only=False)

    assert result.ok is True
    assert result.reply == "reply text"
    assert len(reply_calls) == 1


def test_network_disabled_refuses_before_host_or_pipeline_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor import core as executor_core

    def _unexpected(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network-disabled request reached executor dispatch")

    monkeypatch.setattr(executor_core, "_legacy_host_ports", _unexpected)
    monkeypatch.setattr(executor_core, "resolve_orchestration_mode", _unexpected)
    monkeypatch.setattr(executor_core, "_run_staged_executor", _unexpected)

    result = run_executor(
        ExecutorRequest(query="research and edit this graph", network=False),
        classify_only=True,
    )

    assert result.ok is False
    assert result.failure_kind == "NetworkCapabilityRefused"
    assert result.failure_stage == "configuration"
    assert "network=false" in (result.failure_message or "")
    assert "local and offline" in (result.failure_message or "")


def test_network_enabled_preserves_normal_executor_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor import core as executor_core
    from vibecomfy.executor.contracts import ExecutorResult

    ports = object()
    sentinel = ExecutorResult.success(reply="dispatched")
    seen: dict[str, Any] = {}

    monkeypatch.setattr(executor_core, "_legacy_host_ports", lambda: ports)
    monkeypatch.setattr(
        executor_core,
        "resolve_orchestration_mode",
        lambda request: "staged",
    )

    def _run_staged(request: ExecutorRequest, **kwargs: Any) -> ExecutorResult:
        seen["request"] = request
        seen["host_ports"] = kwargs["host_ports"]
        return sentinel

    monkeypatch.setattr(executor_core, "_run_staged_executor", _run_staged)

    result = run_executor(ExecutorRequest(query="continue", network=True))

    assert result is sentinel
    assert seen["request"].network is True
    assert seen["host_ports"] is ports
