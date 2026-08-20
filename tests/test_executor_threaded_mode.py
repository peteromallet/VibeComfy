from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.executor import core
from vibecomfy.executor.contracts import (
    ExecutorHostPorts,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    OrchestrationModeConfigurationError,
    coerce_orchestration_mode,
    resolve_orchestration_mode,
)
from vibecomfy.executor.profiles import AgentSpecShape, load_profile
from vibecomfy.executor.threaded import (
    THREADED_MAX_AGENT_BATCHES,
    ThreadedKernel,
    run_threaded_executor,
)


class _Failure:
    kind = type("Kind", (), {"value": "ValidationError"})()
    user_facing_message = "failed"


def _ports() -> ExecutorHostPorts:
    return ExecutorHostPorts(
        handle_agent_edit=lambda *a, **k: {},
        payload_hash=lambda payload: "hash",
        classify_failure=lambda *a, **k: _Failure(),
        failure_envelope=lambda *a, **k: _Failure(),
        begin_deepseek_usage_capture=lambda: object(),
        snapshot_deepseek_usage_capture=lambda: ({}, False),
        end_deepseek_usage_capture=lambda token: None,
        begin_model_attempt_capture=lambda: object(),
        snapshot_model_attempt_capture=lambda: (),
        end_model_attempt_capture=lambda token: None,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("staged", "staged"),
        ("threaded", "threaded"),
        ("full", "staged"),
        ("two_step", "threaded"),
    ],
)
def test_mode_boundary_normalizes_aliases(raw: str, expected: str) -> None:
    assert coerce_orchestration_mode(raw) == expected
    request = ExecutorRequest.from_payload({"query": "x", "pipeline_mode": raw})
    assert request.pipeline_mode == expected
    assert request.to_dict()["pipeline_mode"] == expected


def test_mode_resolution_defaults_staged_and_invalid_env_fails() -> None:
    request = ExecutorRequest(query="x")
    assert resolve_orchestration_mode(request, {}) == "staged"
    assert resolve_orchestration_mode(
        request, {"VIBECOMFY_EXECUTOR_PIPELINE_MODE": "two_step"}
    ) == "threaded"
    with pytest.raises(OrchestrationModeConfigurationError):
        resolve_orchestration_mode(
            request, {"VIBECOMFY_EXECUTOR_PIPELINE_MODE": "automatic"}
        )


def test_staged_dispatch_is_the_unchanged_default(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = ExecutorResult.success(reply="staged")
    calls: list[dict[str, Any]] = []

    def fake_staged(request: ExecutorRequest, **kwargs: Any) -> ExecutorResult:
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(core, "_run_staged_executor", fake_staged)
    result = core.run_executor(ExecutorRequest(query="x"), host_ports=_ports())
    assert result is sentinel
    assert calls and calls[0]["classify_only"] is False


def test_threaded_dispatch_never_enters_staged_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.executor import threaded

    sentinel = ExecutorResult.success(reply="threaded")
    monkeypatch.setattr(
        core,
        "_run_staged_executor",
        lambda *a, **k: pytest.fail("staged/classifier path must not run"),
    )
    monkeypatch.setattr(threaded, "run_threaded_executor", lambda *a, **k: sentinel)
    result = core.run_executor(
        ExecutorRequest(query="x", pipeline_mode="threaded"),
        host_ports=_ports(),
    )
    assert result is sentinel


def test_threaded_run_uses_execute_profile_closed_checkpoint_and_hard_cap() -> None:
    seen: dict[str, Any] = {}
    events: list[tuple[str, str]] = []
    graph = {"nodes": [], "links": []}

    def run_implement(request: ExecutorRequest, spec: AgentSpecShape, **kwargs: Any) -> ImplementationResult:
        seen["request"] = request
        seen["spec"] = spec
        seen["plan"] = kwargs["plan"]
        return ImplementationResult(
            graph=graph,
            message="I changed the workflow.",
            durable_response={
                "accepted_batch": [
                    {
                        "delta_id": "d1",
                        "op": {
                            "op": "set_node_field",
                            "target": ["workflow", "1", "steps"],
                            "value": 30,
                        },
                    }
                ]
            },
        )

    def resolve_spec(profile: str | None, stage: str) -> AgentSpecShape:
        seen["stage"] = stage
        return AgentSpecShape("hermes", "model", "medium")

    def enforce_reply_grounding(reply: str, **kwargs: Any) -> str:
        seen["grounding"] = kwargs
        return reply

    kernel = ThreadedKernel(
        resolve_spec=resolve_spec,
        run_implement=run_implement,
        emit_phase=lambda request, **kwargs: events.append(
            (kwargs["phase"], kwargs["status"])
        ),
        enforce_reply_grounding=enforce_reply_grounding,
        accepted_delta_ops=lambda implementation: (
            dict(implementation.durable_response["accepted_batch"][0]["op"]),
        ),
        implementation_landed_edit=lambda implementation: True,
        no_candidate_reason=lambda implementation: None,
    )
    result = run_threaded_executor(
        ExecutorRequest(
            query="set steps",
            graph=graph,
            session_id="same-window",
            pipeline_mode="threaded",
            max_batches=250,
        ),
        kernel=kernel,
        host_ports=_ports(),
        executor_id="executor-test",
    )

    assert result.ok is True
    assert result.graph is graph
    assert seen["stage"] == "execute"
    assert seen["request"].max_batches == THREADED_MAX_AGENT_BATCHES
    assert seen["plan"].effective_route == "adapt"
    assert seen["grounding"]["landed"] is True
    assert events == [("execute", "start"), ("execute", "done")]
    assert result.report.to_dict()["executor"]["orchestration_mode"] == "threaded"


def test_shipped_profiles_have_explicit_execute_specs() -> None:
    for name in ("default", "opensource", "openrouter", "openai", "anthropic"):
        assert isinstance(load_profile(name)["execute"], AgentSpecShape)
