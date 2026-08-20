"""Canonical mode and budget contracts for the threaded executor."""

from __future__ import annotations

from typing import Any

import pytest

from tests._executor_threaded_helpers import (
    ExecutorRequest,
    ExecutorResult,
    THREADED_FEATURE_REQUIRED,
    executor_contracts,
    executor_core,
    host_ports,
    threaded,
)

pytestmark = THREADED_FEATURE_REQUIRED


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("staged", "staged"),
        ("threaded", "threaded"),
        ("full", "staged"),
        ("two_step", "threaded"),
    ],
)
def test_mode_boundary_normalizes_canonical_values_and_legacy_aliases(
    raw: str, canonical: str
) -> None:
    assert executor_contracts.coerce_orchestration_mode(raw) == canonical
    request = ExecutorRequest.from_payload({"query": "inspect", "pipeline_mode": raw})
    assert request.pipeline_mode == canonical
    assert request.to_dict()["pipeline_mode"] == canonical


@pytest.mark.parametrize(
    "raw", ["automatic", "classify", "Threaded", " threaded ", "", True, 1]
)
def test_mode_boundary_rejects_every_unknown_or_untyped_value(raw: Any) -> None:
    with pytest.raises(executor_contracts.OrchestrationModeRequestError):
        executor_contracts.coerce_orchestration_mode(raw)


def test_mode_resolution_is_request_then_environment_then_staged_default() -> None:
    assert executor_contracts.resolve_orchestration_mode(
        ExecutorRequest(query="inspect"), {}
    ) == "staged"
    assert executor_contracts.resolve_orchestration_mode(
        ExecutorRequest(query="inspect"),
        {"VIBECOMFY_EXECUTOR_PIPELINE_MODE": "two_step"},
    ) == "threaded"
    assert executor_contracts.resolve_orchestration_mode(
        ExecutorRequest(query="inspect", pipeline_mode="staged"),
        {"VIBECOMFY_EXECUTOR_PIPELINE_MODE": "threaded"},
    ) == "staged"
    with pytest.raises(executor_contracts.OrchestrationModeConfigurationError):
        executor_contracts.resolve_orchestration_mode(
            ExecutorRequest(query="inspect"),
            {"VIBECOMFY_EXECUTOR_PIPELINE_MODE": "automatic"},
        )


def test_staged_dispatch_remains_the_unchanged_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = ExecutorResult.success(reply="staged")
    calls: list[dict[str, Any]] = []

    def fake_staged(request: ExecutorRequest, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(executor_core, "_run_staged_executor", fake_staged)
    result = executor_core.run_executor(
        ExecutorRequest(query="inspect"), host_ports=host_ports()
    )
    assert result is sentinel
    assert len(calls) == 1
    assert calls[0]["client_id"] is None
    assert calls[0]["classify_only"] is False
    assert calls[0]["additive"] is False
    assert isinstance(calls[0]["host_ports"], executor_contracts.ExecutorHostPorts)


def test_threaded_dispatch_never_enters_the_staged_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = ExecutorResult.success(reply="threaded")
    monkeypatch.setattr(
        executor_core,
        "_run_staged_executor",
        lambda *args, **kwargs: pytest.fail("threaded mode entered staged/classify"),
    )
    monkeypatch.setattr(
        executor_core,
        "_run_classify",
        lambda *args, **kwargs: pytest.fail("threaded mode called the classifier"),
    )
    monkeypatch.setattr(
        threaded, "run_threaded_executor", lambda *args, **kwargs: sentinel
    )

    result = executor_core.run_executor(
        ExecutorRequest(query="edit", pipeline_mode="threaded"),
        host_ports=host_ports(),
    )
    assert result is sentinel


def test_purpose_budget_keeps_recovery_and_terminal_projection_reserved() -> None:
    budget = threaded.ThreadedPurposeBudget(
        research_and_edit_batches=threaded.THREADED_MAX_AGENT_BATCHES,
        recovery_batches_reserved=2,
        final_projection_reserved=1,
    )
    assert budget.research_and_edit_batches == threaded.THREADED_MAX_AGENT_BATCHES
    assert budget.recovery_batches_reserved == 2
    assert budget.final_projection_reserved == 1

    with pytest.raises(ValueError, match="positive"):
        threaded.ThreadedPurposeBudget(research_and_edit_batches=0)
    with pytest.raises(ValueError, match="production ceiling"):
        threaded.ThreadedPurposeBudget(
            research_and_edit_batches=threaded.THREADED_MAX_AGENT_BATCHES + 1
        )
    with pytest.raises(ValueError, match="reserves"):
        threaded.ThreadedPurposeBudget(recovery_batches_reserved=0)
    with pytest.raises(ValueError, match="reserves"):
        threaded.ThreadedPurposeBudget(final_projection_reserved=0)
