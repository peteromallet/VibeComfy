"""RRSYN-7 (modified spec): verbatim user request context, judgment-owned routes.

Covers:
* the classifier user prompt carries the user's query VERBATIM plus an
  affordance note that describes research / inspection / answers / edits as
  available capabilities — never required steps;
* the research stage's brief seam forwards the verbatim ``request.query``
  (the real end-user API field) alongside the classifier's paraphrased
  question — no manifest tags, expected outcomes, or acceptance criteria;
* threaded purpose derivation keeps using only public request shape
  (``deterministic_request_purpose``) with the verbatim query as goal text.
"""

from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.executor import core as executor_core
from vibecomfy.executor import prompts as executor_prompts
from vibecomfy.executor import threaded as executor_threaded
from vibecomfy.executor.contracts import ExecutorRequest


def _request(**overrides: Any) -> ExecutorRequest:
    payload: dict[str, Any] = {
        "query": "Research how VACE preprocessing works first, then explain it",
        "graph": None,
        "workflow_id": None,
        "session_id": None,
    }
    payload.update(overrides)
    return ExecutorRequest.from_payload(payload) if hasattr(
        ExecutorRequest, "from_payload"
    ) else ExecutorRequest(**payload)


# ── classify prompt ──────────────────────────────────────────────────────────


def test_classify_prompt_carries_verbatim_query_and_affordances() -> None:
    query = "Explain what this graph does; do not change anything"
    messages = executor_prompts.build_classify_messages(query, has_graph=True)

    user = messages[-1]["content"]
    assert f"User request:\n{query}" in user
    # Affordance framing: MAY-route capabilities, never required steps.
    assert "Available affordances" in user
    assert "none is a required step" in user


def test_expect_graph_changed_is_context_not_mandate() -> None:
    """RRSYN-7 / RR1-FIX-REV: expect_graph_changed is forwarded as the end
    user's interaction intent — never as a mandatory edit-route decree."""
    messages = executor_prompts.build_classify_messages(
        "make the background red", has_graph=True, expect_graph_changed=True
    )
    user = messages[-1]["content"]
    assert "expect_graph_changed=true" in user
    assert "not a routing mandate" in user
    assert "judgment-owned outcome" in user
    # The removed deterministic coercion must be gone from the prompt.
    assert "MUST be an edit route" not in user
    assert "will be rejected" not in user


def test_classify_system_prompt_has_no_route_coercion() -> None:
    system = executor_prompts._CLASSIFY_SYSTEM
    assert "route MUST be an edit route" not in system
    assert "are rejected." not in system
    assert "not a routing mandate" in system


# ── research brief seam ──────────────────────────────────────────────────────


class _Plan:
    """Minimal stand-in for ClassifyDecision plan fields."""

    def __init__(self, *, research_goal: str = "") -> None:
        self.research_goal = research_goal
        self.change_goal = ""
        self.search_directions: tuple[str, ...] = ()
        self.source_preferences: tuple[str, ...] = ()
        self.known_graph_context = ""
        self.avoid: tuple[str, ...] = ()
        self.model_families: tuple[str, ...] = ()
        self.pattern_category = ""


class _Request:
    def __init__(self, query: str) -> None:
        self.query = query


def test_research_brief_seam_appends_verbatim_user_request() -> None:
    from vibecomfy.executor.agent_research_stage import build_research_brief

    request = _Request("Find a face-detection precedent for this crop step")
    plan = _Plan(research_goal="locate face-detection precedent")
    brief = build_research_brief(plan=plan, request=request)

    combined = executor_core._research_brief_with_verbatim_query(brief, request)
    assert "User request (verbatim):" in combined
    assert "Find a face-detection precedent for this crop step" in combined
    # The paraphrased plan content is still present alongside it.
    assert "locate face-detection precedent" in combined


def test_research_brief_seam_handles_empty_brief_and_blank_query() -> None:
    helper = executor_core._research_brief_with_verbatim_query

    request = _Request("  ")
    assert helper("", request) == ""
    assert helper("Research brief:\n- x", request) == "Research brief:\n- x"

    request = _Request("explain only")
    assert helper("", request) == "User request (verbatim):\nexplain only"


def test_run_agent_owned_research_forwards_brief_with_verbatim_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_stage(*, route, question, research_brief, spec, **kwargs):
        captured.update(
            route=route, question=question, research_brief=research_brief
        )
        from types import SimpleNamespace

        from vibecomfy.executor.evidence_pack import EvidenceLedger, EvidencePack

        trace = SimpleNamespace(
            citations=(),
            budget=None,
            decision=None,
            uncertainty="",
            refine_question=None,
            summary="",
            warnings=(),
            question="",
            final_verdict=None,
            status="never",
            executed_tool_calls=0,
            evidence_artifact_count=0,
            error=None,
        )
        return (
            trace,
            EvidencePack(artifacts={}, ledger=EvidenceLedger(entries=[])),
        )

    monkeypatch.setattr(executor_core, "run_agent_research_stage", fake_stage)

    from vibecomfy.executor.contracts import ClassifyDecision

    request = _request()
    plan = ClassifyDecision(
        research=True,
        implement=False,
        reply=True,
        route="research",
        task="research_nodes",
        intent="research",
        research_goal="how VACE preprocessing works",
    )
    result = executor_core._run_agent_owned_research(
        request, type("Spec", (), {"agent": "agent", "model": "m", "effort": None})(),
        plan=plan,
    )

    assert result is not None
    assert "User request (verbatim):" in str(captured["research_brief"])
    assert request.query in str(captured["research_brief"])


# ── threaded purpose derivation stays product-bound ─────────────────────────


def test_threaded_plan_goals_carry_verbatim_query_only() -> None:
    request = _request()
    plan = executor_threaded._threaded_plan(request)
    assert plan.research_goal == request.query
    assert request.query == "Research how VACE preprocessing works first, then explain it"


def test_threaded_default_envelope_equips_without_prescribing() -> None:
    """RRSYN-7 / RR1-FIX-REV: the classifier-free threaded plan forwards the
    verbatim query and interaction-intent context, frames affordances as
    optional, and never prescribes a mandatory route."""
    request = _request(interaction_mode=None, graph={"nodes": {}, "links": []})
    plan = executor_threaded._threaded_plan(request)
    assert plan.research_goal == request.query
    assert plan.change_goal == request.query
    assert "interaction_mode=unspecified" in plan.plan_summary
    assert "NONE of them is a required step" in plan.plan_summary

    answer_only = _request(
        interaction_mode="answer_only", graph={"nodes": {}, "links": []}
    )
    plan = executor_threaded._threaded_plan(answer_only)
    assert plan.effective_route == "inspect"
    assert "answer_only: respond without editing" in plan.plan_summary
