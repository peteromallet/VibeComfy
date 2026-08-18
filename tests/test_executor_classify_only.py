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


# ── B01: pipeline-mode branching around classify_only ───────────────────────


def _capture_phase_events(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    """Patch ``core._ws_send`` and return the captured phase event payloads."""
    events: list[dict[str, Any]] = []

    def fake_ws_send(event: str, payload: dict[str, Any], *, client_id: str | None = None) -> None:
        assert event == "vibecomfy.executor.phase"
        events.append(payload)

    monkeypatch.setattr("vibecomfy.executor.core._ws_send", fake_ws_send)
    return events


def test_classify_only_full_mode_emits_existing_skipped_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full-mode classify_only still emits research/implement/reply skipped."""
    decision = ClassifyDecision.edit(route="adapt", plan_summary="summary")
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )
    events = _capture_phase_events(monkeypatch)

    result = run_executor(
        ExecutorRequest(query="add a node"),
        classify_only=True,
        client_id="client-1",
    )

    assert result.ok is True
    skipped = [
        (event["phase"], event["status"])
        for event in events
        if event["status"] == "skipped"
    ]
    assert skipped == [
        ("research", "skipped"),
        ("implement", "skipped"),
        ("reply", "skipped"),
    ]
    assert all(event["phase"] != "execute" for event in events)


def test_classify_only_two_step_emits_only_execute_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two-step classify_only emits exactly one skipped event: execute."""
    decision = ClassifyDecision.edit(route="adapt", plan_summary="summary")
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: decision,
    )
    events = _capture_phase_events(monkeypatch)

    result = run_executor(
        ExecutorRequest(query="add a node", pipeline_mode="two_step"),
        classify_only=True,
        client_id="client-1",
    )

    assert result.ok is True
    assert "dry-run" in (result.reply or "")
    skipped = [
        (event["phase"], event["status"])
        for event in events
        if event["status"] == "skipped"
    ]
    assert skipped == [("execute", "skipped")]
    assert all(event["phase"] not in {"research", "implement", "reply"} for event in events)


def test_classify_only_two_step_never_invokes_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """classify_only returns before the two-step branch: execute never runs."""
    from vibecomfy.executor import two_step as two_step_module

    # One-step mode never classifies — the seam must not even be reachable.
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: pytest.fail("classify must not run in one-step mode"),
    )
    monkeypatch.setattr(
        two_step_module,
        "_two_step_outcome",
        lambda **kwargs: pytest.fail("execute must not run for classify_only"),
    )

    result = run_executor(
        ExecutorRequest(query="add a node", pipeline_mode="two_step"),
        classify_only=True,
    )

    assert result.ok is True
    # No classifier ran, so the dry-run report carries no plan.
    assert result.report.plan is None
    assert result.graph is None


def test_classify_only_two_step_does_not_resolve_post_classify_specs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One-step classify_only resolves no profile spec (not even classify)."""
    from types import SimpleNamespace

    def _resolve_spec(_profile: str | None, stage: str) -> object:
        raise AssertionError(f"unexpected {stage} spec resolution in one-step dry-run")

    monkeypatch.setattr("vibecomfy.executor.core._resolve_spec", _resolve_spec)
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: pytest.fail("classify must not run in one-step mode"),
    )

    result = run_executor(
        ExecutorRequest(query="add a brightness node", pipeline_mode="two_step"),
        classify_only=True,
    )

    assert result.ok is True
    assert result.report.plan is None


def test_answer_only_one_step_derives_non_edit_route() -> None:
    """answer_only derives a non-edit route without any classify decision."""
    from vibecomfy.executor import two_step as two_step_module

    # One-step default: adapt (all ten tools).
    assert two_step_module._resolve_two_step_route(None, None) == "adapt"
    # answer_only forbids edits → the non-edit research route.
    assert two_step_module._resolve_two_step_route(None, "answer_only") == "research"
    # A plan (classify already ran) still uses the classified route / fallback.
    assert (
        two_step_module._resolve_two_step_route(
            ClassifyDecision.edit(route="adapt", plan_summary="edit me"), None
        )
        == "adapt"
    )
    assert (
        two_step_module._resolve_two_step_route(
            ClassifyDecision.respond_only(route="respond"), "answer_only"
        )
        == "respond"
    )


def test_answer_only_one_step_execute_never_submits_edits(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """answer_only one-step execute: the execute session must not submit edits."""
    import json

    from vibecomfy.executor import two_step as two_step_module
    from vibecomfy.executor.agent_backend import run_execute_turn
    from vibecomfy.executor.two_step_session import TwoStepSessionStore

    # Route derivation under answer_only is "research" (non-edit); a classify
    # decision is never involved.  Capture the route the outcome boundary
    # resolves and hand it to the real execute turn with an edit attempt that
    # must be denied.
    captured_route: dict[str, str] = {}

    def fake_outcome(*, request, plan, pipeline_mode, client_id, executor_id, additive, session_root=None):
        route = two_step_module._resolve_two_step_route(plan, request.interaction_mode)
        captured_route["route"] = route
        store = TwoStepSessionStore(tmp_path / "sessions")
        # Model attempts an edit then a submit — the edit must be denied for
        # a non-edit route, so the submit contract cites no accepted Δ.
        actions = iter([
            {"action": "apply", "python": "graph.set_node(1, brightness=2.0)"},
            {"action": "submit", "reply": "final message", "delta_ids": []},
        ])

        def model_turn_fn(task, messages, **kwargs):
            return {"content": json.dumps(next(actions))}

        outcome = run_execute_turn(
            request,
            plan=plan,
            route=route,
            spec=SimpleNamespace(agent="hermes", model="m", effort=None),
            session_store=store,
            session_id=request.session_id or "win-a",
            model_turn_fn=model_turn_fn,
        )
        from vibecomfy.executor.contracts import ExecutorResult

        return ExecutorResult.success(
            report=None,
            graph=outcome.get("graph"),
            reply=outcome.get("reply"),
        )

    monkeypatch.setattr(two_step_module, "_two_step_outcome", fake_outcome)

    result = run_executor(
        ExecutorRequest(
            query="explain the graph",
            interaction_mode="answer_only",
            pipeline_mode="two_step",
            session_id="win-a",
        )
    )

    assert result.ok is True
    assert captured_route["route"] == "research"
    assert result.graph is None
