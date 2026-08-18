"""B05: two-step reporting — Report.pipeline_mode + report.executor.execute.

Covers the intentional additive report schema change: every report
serializes its RESOLVED ``pipeline_mode`` (including ``"full"``), and
two-step runs additionally serialize the optional ``execute`` section
(session identity, route, budget usage, tool/evidence/Δ IDs, claim
validation, replacement use, self-assessment).  Also covers the typed
``MissingProfileStageError`` path: ``execute`` is resolved ONLY for
two-step and NEVER falls back to ``implement``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecuteReport,
    ExecutorRequest,
    ExecutorResult,
    Report,
)
from vibecomfy.executor.core import _resolve_spec, run_executor
from vibecomfy.executor.profiles import MissingProfileStageError

_EXECUTE_BUDGET_KEYS = {
    "output_tokens",
    "model_continuations",
    "tool_calls",
    "apply_batches",
    "replacement_attempts",
    "wall_clock_seconds",
}


# ── helpers ──────────────────────────────────────────────────────────────────


def _decision(route: str = "adapt") -> ClassifyDecision:
    return ClassifyDecision.edit(route=route, plan_summary="summary")


def _run_two_step_success(
    monkeypatch: pytest.MonkeyPatch,
    *,
    session_id: str = "sess-two-step",
) -> ExecutorResult:
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: _decision(),
    )
    # The B03 execute boundary runs a real bounded session; feed it a canned
    # outcome so these B05 report tests stay model-free.
    monkeypatch.setattr(
        "vibecomfy.executor.agent_backend.run_execute_turn",
        lambda *args, **kwargs: {"ok": True, "reply": "edited"},
    )
    return run_executor(
        ExecutorRequest(
            query="add a node",
            session_id=session_id,
            pipeline_mode="two_step",
        )
    )


def _run_full_mode_success(monkeypatch: pytest.MonkeyPatch) -> ExecutorResult:
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: ClassifyDecision.respond_only(route="respond"),
    )
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_reply",
        lambda *args, **kwargs: "hello",
    )
    return run_executor(ExecutorRequest(query="hello"))


# ── Report.pipeline_mode is ALWAYS serialized (including "full") ─────────────


def test_full_mode_report_always_serializes_pipeline_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_full_mode_success(monkeypatch)
    inner = result.to_dict()["report"]["executor"]
    assert inner["pipeline_mode"] == "full"
    # Full-mode reports never carry the two-step execute section.
    assert "execute" not in inner


def test_two_step_report_serializes_pipeline_mode_and_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_two_step_success(monkeypatch)
    inner = result.to_dict()["report"]["executor"]
    assert inner["pipeline_mode"] == "two_step"
    execute = inner["execute"]
    assert execute["session_id"] == "sess-two-step"
    assert execute["route"] == "adapt"
    assert set(execute["budget_usage"]) == _EXECUTE_BUDGET_KEYS
    assert execute["tool_call_ids"] == []
    assert execute["evidence_ids"] == []
    assert execute["accepted_delta_ids"] == []
    assert execute["claim_validation"] == {"status": "not_run"}
    assert execute["replacement_used"] is False


def test_bare_report_defaults_to_full_mode_serialization() -> None:
    """A Report constructed without a mode still serializes pipeline_mode
    (defaults to ``"full"``) — the additive schema change is unconditional."""
    inner = Report().to_dict()["executor"]
    assert inner["pipeline_mode"] == "full"
    assert "execute" not in inner


# ── ExecuteReport shape ──────────────────────────────────────────────────────


def test_execute_report_to_dict_full_shape() -> None:
    report = ExecuteReport(
        session_id="sess-1",
        route="revise",
        budget_usage={
            "output_tokens": 120,
            "model_continuations": 3,
            "tool_calls": 4,
            "apply_batches": 1,
            "replacement_attempts": 1,
            "wall_clock_seconds": 42.5,
        },
        tool_call_ids=["tool-1", "tool-2"],
        evidence_ids=["ev-1"],
        accepted_delta_ids=["delta-1"],
        claim_validation={"status": "ok", "violations": []},
        replacement_used=True,
        self_assessment={"confidence": "high", "note": "done"},
    )
    payload = report.to_dict()
    assert payload == {
        "session_id": "sess-1",
        "route": "revise",
        "budget_usage": {
            "output_tokens": 120,
            "model_continuations": 3,
            "tool_calls": 4,
            "apply_batches": 1,
            "replacement_attempts": 1,
            "wall_clock_seconds": 42.5,
        },
        "tool_call_ids": ["tool-1", "tool-2"],
        "evidence_ids": ["ev-1"],
        "accepted_delta_ids": ["delta-1"],
        "claim_validation": {"status": "ok", "violations": []},
        "replacement_used": True,
        "self_assessment": {"confidence": "high", "note": "done"},
    }


def test_execute_report_filters_unknown_budget_keys() -> None:
    """Only the canonical seven budget counters may ride in budget_usage."""
    report = ExecuteReport(
        route="adapt",
        budget_usage={
            "output_tokens": 10,
            "smuggled_field": "nope",
            "wall_clock_seconds": 1.0,
        },
    )
    payload = report.to_dict()
    assert set(payload["budget_usage"]) == {
        "output_tokens",
        "wall_clock_seconds",
    }


def test_execute_report_omits_none_self_assessment() -> None:
    payload = ExecuteReport(route="respond").to_dict()
    assert "self_assessment" not in payload


# ── execute is two-step ONLY; never falls back to implement ─────────────────


def test_resolve_execute_spec_uses_the_profiles_execute_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_resolve_spec(profile, 'execute') returns the declared execute spec —
    it is NOT the implement spec."""
    spec = _resolve_spec("default", "execute")
    from vibecomfy.executor.profiles import load_profile

    assert spec == load_profile("default")["execute"]
    assert spec == load_profile("default")["implement"]  # same family today
    assert spec.agent == "hermes"


def test_resolve_execute_missing_stage_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A profile without ``execute`` raises the typed MissingProfileStageError
    — the two-step path never synthesizes it from ``implement``."""
    from vibecomfy.executor.profiles import set_profile_override_dir

    (tmp_path / "no_execute.toml").write_text(
        "\n".join(
            [
                '[classify]\nagent = "hermes"\nmodel = "d"',
                '[research]\nagent = "hermes"\nmodel = "d"',
                '[implement]\nagent = "hermes"\nmodel = "d"',
                '[reply]\nagent = "hermes"\nmodel = "d"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    set_profile_override_dir(tmp_path)
    try:
        with pytest.raises(MissingProfileStageError, match="execute"):
            _resolve_spec("no_execute", "execute")
    finally:
        set_profile_override_dir(None)


def test_two_step_missing_execute_profile_fails_typed_not_implement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two-step with a profile that lacks ``execute`` fails as a typed profile
    failure — it does NOT silently run the implement spec."""
    from vibecomfy.executor.profiles import set_profile_override_dir

    (tmp_path / "no_execute.toml").write_text(
        "\n".join(
            [
                '[classify]\nagent = "hermes"\nmodel = "d"',
                '[research]\nagent = "hermes"\nmodel = "d"',
                '[implement]\nagent = "hermes"\nmodel = "d"',
                '[reply]\nagent = "hermes"\nmodel = "d"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    set_profile_override_dir(tmp_path)
    try:
        monkeypatch.setattr(
            "vibecomfy.executor.core._run_classify",
            lambda *args, **kwargs: _decision(),
        )
        result = run_executor(
            ExecutorRequest(
                query="add a node",
                profile="no_execute",
                session_id="sess-no-exec",
                pipeline_mode="two_step",
            )
        )
    finally:
        set_profile_override_dir(None)

    assert result.ok is False
    assert result.failure_stage == "profile"
    inner = result.to_dict()["report"]["executor"]
    assert inner["pipeline_mode"] == "two_step"
    assert "execute" not in inner


# ── two-step result records carry the execute report ─────────────────────────


def test_two_step_result_report_preserves_execute_across_serialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run_two_step_success(monkeypatch)
    assert result.ok is True
    report = result.report
    assert report.pipeline_mode == "two_step"
    assert report.execute is not None
    assert report.execute.session_id == "sess-two-step"
    assert report.execute.route == "adapt"
    assert report.execute.budget_usage["tool_calls"] == 0


def test_span_update_folds_execute_counters_into_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The single phase='execute' profiler span carries the budget counters."""
    from vibecomfy.executor import two_step as ts
    from vibecomfy.executor.profiler import ProfilerSpan

    result = ExecutorResult.success(
        report=Report(
            plan=_decision(),
            pipeline_mode="two_step",
            execute=ExecuteReport(
                session_id="sess-1",
                route="adapt",
                budget_usage={"tool_calls": 3, "output_tokens": 77},
            ),
        ),
        reply="ok",
    )
    captured: dict[str, Any] = {}
    span = ProfilerSpan(
        logger=ts.LOGGER,
        event="executor.phase",
        base_fields={"phase": "execute", "route": "hermes", "model": "m"},
    )
    try:
        ts._span_update_from_execute_result(span, result)
        span.finish()
    finally:
        captured = dict(span.result_fields)

    assert captured["tool_calls"] == 3
    assert captured["output_tokens"] == 77
    assert captured["execute_route"] == "adapt"
    assert captured["execute_session_id"] == "sess-1"


# ── execute-stage failure envelopes preserve execute telemetry (B04) ──────────


def _run_two_step_failure(
    monkeypatch: pytest.MonkeyPatch,
    outcome: dict[str, Any],
    *,
    route: str,
    session_id: str,
) -> ExecutorResult:
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: _decision(route),
    )
    monkeypatch.setattr(
        "vibecomfy.executor.agent_backend.run_execute_turn",
        lambda *args, **kwargs: outcome,
    )
    return run_executor(
        ExecutorRequest(query="edit", session_id=session_id, pipeline_mode="two_step")
    )


def test_forged_delta_failure_preserves_execute_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A forged-delta (missing_delta_reference) failure still serializes the
    execute section: route, session id, budget usage, and a failed
    claim-validation status — never a bare ``Report(plan, pipeline_mode)``."""
    from vibecomfy.executor.two_step import SessionBudget
    from vibecomfy.executor.two_step_session import TwoStepSessionError

    result = _run_two_step_failure(
        monkeypatch,
        {
            "ok": False,
            "route": "revise",
            "failure": TwoStepSessionError("missing_delta_reference", "forged delta"),
            "budget": SessionBudget().record_output_tokens(42),
        },
        route="adapt",
        session_id="sess-forged",
    )
    assert result.ok is False
    assert result.failure_kind == "missing_delta_reference"
    execute = result.report.execute
    assert execute is not None
    assert execute.route == "adapt"
    assert execute.session_id == "sess-forged"
    assert execute.budget_usage["output_tokens"] == 42
    assert execute.claim_validation["status"] == "failed"
    assert execute.claim_validation["failure_kind"] == "missing_delta_reference"


def test_budget_exhaustion_failure_preserves_execute_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A budget-exhaustion failure still carries the execute section with the
    route and the canonical seven budget counters (the real loop returns no
    ``budget`` on exhaustion, so the counters are all zero — but present)."""
    from vibecomfy.executor.two_step import BUDGET_FAMILY_OUTPUT_TOKENS, BudgetExceeded

    result = _run_two_step_failure(
        monkeypatch,
        {
            "ok": False,
            "route": "adapt",
            "failure": BudgetExceeded(
                family=BUDGET_FAMILY_OUTPUT_TOKENS,
                limit=12_000,
                used=12_001,
                route="adapt",
            ),
        },
        route="adapt",
        session_id="sess-budget",
    )
    assert result.ok is False
    assert result.failure_kind == BUDGET_FAMILY_OUTPUT_TOKENS
    execute = result.report.execute
    assert execute is not None
    assert execute.route == "adapt"
    assert execute.session_id == "sess-budget"
    assert set(execute.budget_usage) == _EXECUTE_BUDGET_KEYS
    assert all(v == 0 for v in execute.budget_usage.values())
    assert execute.claim_validation["status"] == "failed"


def test_real_loop_budget_exhaustion_preserves_execute_telemetry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Driving the REAL bounded loop to session budget exhaustion (12 accepted
    apply batches, then a 13th) must still surface execute telemetry — never a
    bare ``Report(plan, pipeline_mode)``.  The exhaustion surfaces as a typed
    ``session_apply_batches`` failure carrying route + canonical budget usage."""
    import json as _json

    from vibecomfy.executor import agent_backend as agent_backend_module
    from vibecomfy.executor import two_step as two_step_module
    from vibecomfy.executor.two_step import BUDGET_FAMILY_SESSION_APPLY_BATCHES
    from tests.executor_mode_harness import _law_edit_session, named_field_edit

    scenario = named_field_edit()
    code = 'lawnodec.prompt = "after"'

    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: scenario.decision,
    )
    monkeypatch.setattr(two_step_module, "_two_step_edit_session", _law_edit_session)

    real_run_execute_turn = agent_backend_module.run_execute_turn

    def scripted_execute_turn(request: Any, **kwargs: Any) -> dict[str, Any]:
        # A fresh apply → submit per message; the real loop + real session
        # store accumulate apply_batches across the 13 messages.
        actions = [
            {"action": "apply", "python": code},
            {"action": "submit", "reply": "edited", "claim_refs": {"delta_ids": ["d1"]}},
        ]

        def model_turn_fn(task: Any, messages: Any, **kw: Any) -> dict[str, Any]:
            action = actions.pop(0) if actions else {
                "action": "submit",
                "reply": "done",
                "claim_refs": {"delta_ids": []},
            }
            return {
                "content": _json.dumps(action),
                "model_attempts": [{"token_usage": {"completion_tokens": 10}}],
            }

        return real_run_execute_turn(request, model_turn_fn=model_turn_fn, **kwargs)

    monkeypatch.setattr(
        "vibecomfy.executor.agent_backend.run_execute_turn", scripted_execute_turn
    )

    real_two_step_outcome = two_step_module._two_step_outcome

    def isolated_outcome(
        *,
        request: Any,
        plan: Any,
        pipeline_mode: Any,
        client_id: Any,
        executor_id: Any,
        additive: bool,
    ) -> ExecutorResult:
        return real_two_step_outcome(
            request=request,
            plan=plan,
            pipeline_mode=pipeline_mode,
            client_id=client_id,
            executor_id=executor_id,
            additive=additive,
            session_root=tmp_path / "editor_sessions",
        )

    monkeypatch.setattr(two_step_module, "_two_step_outcome", isolated_outcome)

    def run_message() -> ExecutorResult:
        return run_executor(
            ExecutorRequest(
                query="edit the graph",
                graph=scenario.base_raw,
                pipeline_mode="two_step",
                session_id="exhaust-session",
            )
        )

    # 12 accepted apply batches fit exactly under the session ceiling.
    for _ in range(12):
        result = run_message()
        assert result.ok is True, result.failure_message

    # The 13th apply batch exhausts the session ceiling — but the failure still
    # carries execute telemetry (route + budget usage), never a bare report.
    final = run_message()
    assert final.ok is False
    assert final.failure_kind == BUDGET_FAMILY_SESSION_APPLY_BATCHES
    execute = final.report.execute
    assert execute is not None
    assert execute.route == "adapt"
    assert execute.session_id == "exhaust-session"
    assert set(execute.budget_usage) == _EXECUTE_BUDGET_KEYS
    assert execute.claim_validation["status"] == "failed"
    assert execute.claim_validation["failure_kind"] == BUDGET_FAMILY_SESSION_APPLY_BATCHES


def test_raised_execute_exception_preserves_execute_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raised exception escaping the real loop (not an injected outcome dict)
    still produces a report with execute telemetry — Blocker 2 part 2."""
    monkeypatch.setattr(
        "vibecomfy.executor.core._run_classify",
        lambda *args, **kwargs: _decision("adapt"),
    )

    def _raise(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr("vibecomfy.executor.agent_backend.run_execute_turn", _raise)
    result = run_executor(
        ExecutorRequest(query="edit", session_id="sess-raise", pipeline_mode="two_step")
    )
    assert result.ok is False
    assert result.failure_kind == "ExecuteError"
    execute = result.report.execute
    assert execute is not None
    assert execute.route == "adapt"
    assert execute.session_id == "sess-raise"
    assert set(execute.budget_usage) == _EXECUTE_BUDGET_KEYS
    assert execute.claim_validation["status"] == "failed"
    assert execute.claim_validation["failure_kind"] == "ExecuteError"
