"""Unit tests for executor contracts and prompt parsing.

Covers valid classify/reply JSON, malformed JSON, optional graph handling,
and the final executor result shape — without changing existing agent
contracts.
"""

from __future__ import annotations

import json

import pytest

from vibecomfy.executor.contracts import (
    AgentEvidence,
    AgentTurnResult,
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    InspectionSummary,
    PrecedentAdaptationPlan,
    Report,
    ResearchResult,
    WorkflowSlice,
)
from vibecomfy.executor.prompts import (
    build_classify_messages,
    build_reply_messages,
    parse_classify_response,
    parse_reply_response,
)


# ── ExecutorRequest ──────────────────────────────────────────────────────────


class TestExecutorRequest:
    def test_minimal_request(self) -> None:
        req = ExecutorRequest(query="hello")
        assert req.query == "hello"
        assert req.graph is None
        assert req.session_id is None
        assert req.profile is None
        assert req.idempotency_key is None

    def test_full_request(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest(
            query="set seed to 42",
            graph=graph,
            session_id="sess-1",
            profile="default",
            idempotency_key="idem-1",
        )
        assert req.graph == graph
        assert req.session_id == "sess-1"
        assert req.profile == "default"
        assert req.idempotency_key == "idem-1"

    def test_to_dict_minimal(self) -> None:
        req = ExecutorRequest(query="hello")
        d = req.to_dict()
        assert d == {"query": "hello"}

    def test_to_dict_full(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest(
            query="set seed",
            graph=graph,
            session_id="sess-1",
            profile="default",
            idempotency_key="idem-1",
        )
        d = req.to_dict()
        assert d["query"] == "set seed"
        assert d["graph"] == graph
        assert d["session_id"] == "sess-1"
        assert d["profile"] == "default"
        assert d["idempotency_key"] == "idem-1"

    def test_from_payload_minimal(self) -> None:
        req = ExecutorRequest.from_payload({"query": "hello"})
        assert req.query == "hello"

    def test_from_payload_full(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest.from_payload({
            "query": "edit graph",
            "graph": graph,
            "session_id": "s1",
            "profile": "default",
            "idempotency_key": "ik1",
        })
        assert req.graph == graph
        assert req.session_id == "s1"

    def test_from_payload_missing_query_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            ExecutorRequest.from_payload({})

    def test_from_payload_empty_query_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty string"):
            ExecutorRequest.from_payload({"query": "   "})

    def test_from_payload_bad_graph_type_raises(self) -> None:
        with pytest.raises(ValueError, match="graph"):
            ExecutorRequest.from_payload({"query": "x", "graph": "not-a-dict"})


# ── ClassifyDecision ─────────────────────────────────────────────────────────


class TestClassifyDecision:
    def test_defaults(self) -> None:
        d = ClassifyDecision()
        assert d.research is False
        assert d.implement is False
        assert d.reply is True
        assert d.effort == "low"
        assert d.plan_summary == ""

    def test_respond_only_convenience(self) -> None:
        d = ClassifyDecision.respond_only()
        assert d.research is False
        assert d.implement is False
        assert d.reply is True

    def test_edit_convenience(self) -> None:
        d = ClassifyDecision.edit()
        assert d.research is True
        assert d.implement is True
        assert d.reply is True

    def test_edit_no_research(self) -> None:
        d = ClassifyDecision.edit(research=False)
        assert d.research is False
        assert d.implement is True


    def test_to_dict_with_route_and_task(self) -> None:
        """to_dict() emits route and task fields when they are non-empty."""
        d = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="medium",
            plan_summary="simple edit",
            route="revise",
            task="edit_graph",
        )
        out = d.to_dict()
        assert out["route"] == "revise"
        assert out["task"] == "edit_graph"
        # Legacy fields still present
        assert out["research"] is False
        assert out["implement"] is True

    def test_to_dict_omits_empty_route_and_task(self) -> None:
        """to_dict() omits route/task when they are empty (preserving legacy shape)."""
        d = ClassifyDecision(
            research=False,
            implement=False,
            route="",
            task="",
        )
        out = d.to_dict()
        assert "route" not in out
        assert "task" not in out

    def test_effective_route_property(self) -> None:
        """effective_route derives correctly from legacy booleans when route is empty."""
        # implement=True, research=False → revise
        assert ClassifyDecision(research=False, implement=True).effective_route == "revise"
        # research=True, implement=False → inspect
        assert ClassifyDecision(research=True, implement=False).effective_route == "inspect"
        # research=False, implement=False → clarify
        assert ClassifyDecision(research=False, implement=False).effective_route == "clarify"
        # research=True, implement=True → ambiguous (empty)
        assert ClassifyDecision(research=True, implement=True).effective_route == ""

    def test_effective_route_explicit_wins(self) -> None:
        """Explicit route takes precedence over derived route."""
        d = ClassifyDecision(
            research=True,
            implement=True,  # ambiguous legacy → derived ""
            route="adapt",
        )
        assert d.effective_route == "adapt"

    def test_effective_task_property(self) -> None:
        """effective_task derives correctly from legacy booleans when task is empty."""
        # implement=True, research=False → edit_graph
        assert ClassifyDecision(research=False, implement=True).effective_task == "edit_graph"
        # research=True, implement=False, intent=explain_graph → inspect_graph
        assert ClassifyDecision(research=True, implement=False, intent="explain_graph").effective_task == "inspect_graph"
        # research=True, implement=False, intent=research → research_nodes
        assert ClassifyDecision(research=True, implement=False, intent="research").effective_task == "research_nodes"
        # research=False, implement=False → respond
        assert ClassifyDecision(research=False, implement=False).effective_task == "respond"
        # research=True, implement=True → ambiguous (empty)
        assert ClassifyDecision(research=True, implement=True).effective_task == ""

    def test_effective_task_explicit_wins(self) -> None:
        """Explicit task takes precedence over derived task."""
        d = ClassifyDecision(
            research=True,
            implement=True,  # ambiguous → derived ""
            task="edit_graph",
        )
        assert d.effective_task == "edit_graph"

    def test_unknown_explicit_route_fails_closed_to_clarify(self) -> None:
        """Unknown explicit routes fail closed to canonical clarify."""
        d = ClassifyDecision(route="bogus_route")
        assert d.route == "clarify"
        assert d.effective_route == "clarify"
        assert d.to_dict()["route"] == "clarify"

    def test_route_allows_all_valid_values(self) -> None:
        """All canonical route values are accepted."""
        valid_routes = ["", "clarify", "inspect", "revise", "adapt"]
        for r in valid_routes:
            d = ClassifyDecision(route=r)
            assert d.route == r, f"route={r!r} was clamped"

    @pytest.mark.parametrize(
        ("legacy_route", "research", "implement", "expected_route"),
        [
            ("inspect_only", True, False, "inspect"),
            ("direct_edit", False, True, "revise"),
            ("diagnose_repair", True, True, "revise"),
            ("precedent_research", True, True, "adapt"),
            ("asset_lookup", True, True, "adapt"),
            ("asset_lookup", False, True, "revise"),
            ("asset_lookup", False, False, "clarify"),
            ("subgraph_preview", True, True, "adapt"),
            ("subgraph_preview", False, True, "revise"),
            ("subgraph_preview", False, False, "clarify"),
        ],
    )
    def test_legacy_explicit_routes_normalize_before_serialization(
        self,
        legacy_route: str,
        research: bool,
        implement: bool,
        expected_route: str,
    ) -> None:
        decision = ClassifyDecision(
            research=research,
            implement=implement,
            route=legacy_route,
        )

        assert decision.route == expected_route
        assert decision.effective_route == expected_route
        assert decision.to_dict()["route"] == expected_route
        assert decision.to_dict()["route"] not in {
            "inspect_only",
            "direct_edit",
            "diagnose_repair",
            "precedent_research",
            "asset_lookup",
            "subgraph_preview",
        }

    def test_inspect_route_overrides_stale_implement_true(self) -> None:
        """Explicit route=inspect forces implement=false even when stale implement=true is set."""
        d = ClassifyDecision(
            research=False,
            implement=True,  # stale legacy field
            reply=True,
            intent="explain_graph",
            route="inspect",
            task="inspect_graph",
        )
        # Implement must be overridden to False per inspect read-only contract (SD1).
        assert d.implement is False
        assert d.route == "inspect"
        assert d.effective_route == "inspect"
        # Serialized output must not leak the stale implement=true.
        out = d.to_dict()
        assert out["implement"] is False
        assert out["route"] == "inspect"

    def test_inspect_only_alias_serializes_canonical_inspect(self) -> None:
        """inspect_only input alias normalizes to inspect in serialized output."""
        d = ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            intent="explain_graph",
            route="inspect_only",
            task="inspect_graph",
        )
        # Normalized to canonical "inspect".
        assert d.route == "inspect"
        assert d.effective_route == "inspect"
        out = d.to_dict()
        assert out["route"] == "inspect"
        # Legacy alias must never appear in serialization.
        assert out["route"] != "inspect_only"

    def test_inspect_only_alias_overrides_stale_implement_true(self) -> None:
        """inspect_only alias with stale implement=true: normalizes to inspect and forces implement=false."""
        d = ClassifyDecision(
            research=False,
            implement=True,  # stale
            reply=True,
            intent="explain_graph",
            route="inspect_only",
            task="inspect_graph",
        )
        assert d.route == "inspect"
        assert d.implement is False
        out = d.to_dict()
        assert out["route"] == "inspect"
        assert out["implement"] is False

    def test_task_clamped_to_empty(self) -> None:
        """Invalid task is clamped to empty string in __post_init__."""
        d = ClassifyDecision(task="bogus_task")
        assert d.task == ""

    def test_task_allows_all_valid_values(self) -> None:
        """All canonical task values are accepted."""
        valid_tasks = [
            "", "edit_graph", "inspect_graph", "find_assets",
            "diagnose", "preview_subgraph", "research_precedent", "respond", "research_nodes",
        ]
        for t in valid_tasks:
            d = ClassifyDecision(task=t)
            assert d.task == t, f"task={t!r} was clamped"

    def test_intent_clamped_to_respond(self) -> None:
        """Invalid intent is clamped to 'respond' in __post_init__."""
        d = ClassifyDecision(intent="bogus_intent")
        assert d.intent == "respond"

    def test_intent_allows_all_valid_values(self) -> None:
        """All canonical intent values are accepted."""
        for intent in ("edit", "research", "explain_graph", "respond"):
            d = ClassifyDecision(intent=intent)
            assert d.intent == intent

    def test_respond_only_with_explicit_route(self) -> None:
        """respond_only convenience accepts explicit route and task."""
        d = ClassifyDecision.respond_only(
            route="clarify",
            task="respond",
            plan_summary="clarifying question",
        )
        assert d.route == "clarify"
        assert d.task == "respond"
        assert d.research is False
        assert d.implement is False
        assert d.reply is True

    def test_edit_convenience_with_explicit_route(self) -> None:
        """edit convenience accepts explicit route and task."""
        d = ClassifyDecision.edit(
            research=False,
            route="revise",
            task="edit_graph",
            plan_summary="set seed",
        )
        assert d.route == "revise"
        assert d.task == "edit_graph"
        assert d.research is False
        assert d.implement is True

    def test_effort_clamped_to_low(self) -> None:
        d = ClassifyDecision(effort="extreme")
        assert d.effort == "low"

    def test_to_dict(self) -> None:
        d = ClassifyDecision(research=True, implement=False, reply=True, effort="medium", plan_summary="test plan")
        out = d.to_dict()
        assert out == {
            "research": True,
            "implement": False,
            "reply": True,
            "effort": "medium",
            "plan_summary": "test plan",
            "intent": "respond",
        }


# ── ResearchResult ───────────────────────────────────────────────────────────


class TestResearchResult:
    def test_defaults(self) -> None:
        r = ResearchResult()
        assert r.summary == ""
        assert r.sources == ()
        assert r.warnings == ()

    def test_with_data(self) -> None:
        r = ResearchResult(
            summary="found 3 templates",
            sources=({"name": "t1"}, {"name": "t2"}),
            warnings=("hivemind timeout",),
        )
        assert r.summary == "found 3 templates"
        assert len(r.sources) == 2
        assert len(r.warnings) == 1

    def test_to_dict(self) -> None:
        r = ResearchResult(
            summary="x",
            sources=({"k": "v"},),
            warnings=("w1",),
        )
        d = r.to_dict()
        assert d["summary"] == "x"
        assert d["sources"] == [{"k": "v"}]
        assert d["warnings"] == ["w1"]

    def test_immutable_tuples(self) -> None:
        r = ResearchResult(sources=({"a": 1},), warnings=("w",))
        # Tuple items cannot be reassigned (TypeError).
        with pytest.raises(TypeError):
            r.sources[0] = {"b": 2}  # type: ignore[index]
        # The frozen dataclass prevents field reassignment (FrozenInstanceError,
        # which is a subclass of AttributeError in CPython 3.11+).
        with pytest.raises(Exception):
            r.sources = ()  # type: ignore[misc]


# ── ImplementationResult ─────────────────────────────────────────────────────


class TestImplementationResult:
    def test_defaults(self) -> None:
        ir = ImplementationResult()
        assert ir.graph is None
        assert ir.delta == ()
        assert ir.message == ""

    def test_with_graph(self) -> None:
        g = {"nodes": [{"id": 1}]}
        ir = ImplementationResult(graph=g, message="added node")
        assert ir.graph == g
        assert ir.message == "added node"

    def test_with_delta(self) -> None:
        ops = ({"op": "set_field"},)
        ir = ImplementationResult(delta=ops, message="changed field")
        assert ir.delta == ops

    def test_to_dict(self) -> None:
        ir = ImplementationResult(graph={"n": 1}, message="done", delta=({"op": "add"},))
        d = ir.to_dict()
        assert d["graph"] == {"n": 1}
        assert d["message"] == "done"
        assert d["delta"] == [{"op": "add"}]


# ── Report ───────────────────────────────────────────────────────────────────


class TestReport:
    def test_default(self) -> None:
        r = Report()
        assert isinstance(r.plan, ClassifyDecision)
        assert r.research is None
        assert r.implementation is None

    def test_with_phases(self) -> None:
        plan = ClassifyDecision(research=True, implement=True)
        research = ResearchResult(summary="found")
        impl = ImplementationResult(message="edited")
        r = Report(plan=plan, research=research, implementation=impl)
        assert r.plan == plan
        assert r.research is research
        assert r.implementation is impl

    def test_to_dict(self) -> None:
        plan = ClassifyDecision(plan_summary="p")
        research = ResearchResult(summary="r")
        r = Report(plan=plan, research=research)
        d = r.to_dict()
        assert d["executor"]["plan"]["plan_summary"] == "p"
        assert d["executor"]["research"]["summary"] == "r"
        assert "implementation" not in d["executor"]


# ── AgentTurnResult ──────────────────────────────────────────────────────────


class TestAgentTurnResult:
    def test_canonical_envelope_shape(self) -> None:
        result = AgentTurnResult(
            route="revise",
            reply="Updated the graph.",
            evidence=AgentEvidence(
                classification={"route": "revise", "task": "edit_graph"},
                graph_inspection={},
                research={},
                implementation={"message": "done"},
                warnings=(),
            ),
            candidate={"graph": {"nodes": [{"id": 1}]}},
            disposition="edit_graph",
        )

        payload = result.to_dict()
        assert set(payload) == {
            "route",
            "reply",
            "evidence",
            "candidate",
            "apply_eligible",
            "no_candidate_reason",
        }
        assert payload["route"] == "revise"
        assert payload["reply"] == "Updated the graph."
        assert payload["candidate"] == {"graph": {"nodes": [{"id": 1}]}}
        assert payload["apply_eligible"] is True
        assert payload["no_candidate_reason"] is None
        assert set(payload["evidence"]) == {
            "classification",
            "graph_inspection",
            "research",
            "implementation",
            "warnings",
        }
        assert "disposition" not in payload

    @pytest.mark.parametrize(
        "reason",
        [
            "route_not_applyable",
            "no_graph",
            "implementation_skipped",
            "implementation_failed",
            "no_changes",
            "unknown_route",
        ],
    )
    def test_closed_no_candidate_reason_set(self, reason: str) -> None:
        result = AgentTurnResult(
            route="inspect",
            reply="Here is what the graph does.",
            no_candidate_reason=reason,
        )

        assert result.to_dict()["no_candidate_reason"] == reason
        assert result.to_dict()["apply_eligible"] is False

    def test_unknown_no_candidate_reason_fails_closed(self) -> None:
        result = AgentTurnResult(
            route="revise",
            reply="No edit was produced.",
            no_candidate_reason="legacy_reason",
        )

        assert result.to_dict()["no_candidate_reason"] == "no_changes"

    def test_candidate_clears_no_candidate_reason(self) -> None:
        result = AgentTurnResult(
            route="adapt",
            reply="Adapted the precedent.",
            candidate={"graph": {"nodes": []}},
            no_candidate_reason="no_graph",
        )

        assert result.to_dict()["candidate"] == {"graph": {"nodes": []}}
        assert result.to_dict()["apply_eligible"] is True
        assert result.to_dict()["no_candidate_reason"] is None

    def test_unknown_public_route_fails_closed_to_clarify(self) -> None:
        result = AgentTurnResult(route="retired_route", reply="legacy")

        assert result.to_dict()["route"] == "clarify"
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False

    @pytest.mark.parametrize(
        ("route", "candidate", "expected_apply_eligible", "expected_reason"),
        [
            ("clarify", None, False, "route_not_applyable"),
            ("inspect", None, False, "route_not_applyable"),
            ("revise", {"graph": {"nodes": [{"id": 1}]}}, True, None),
            ("adapt", {"graph": {"nodes": [{"id": 1}]}}, True, None),
        ],
    )
    def test_canonical_public_envelope_and_apply_eligibility_by_route(
        self,
        route: str,
        candidate: dict[str, object] | None,
        expected_apply_eligible: bool,
        expected_reason: str | None,
    ) -> None:
        result = AgentTurnResult(
            route=route,
            reply="Turn complete.",
            candidate=candidate,
            no_candidate_reason=expected_reason,
        )

        payload = result.to_dict()
        assert set(payload) == {
            "route",
            "reply",
            "evidence",
            "candidate",
            "apply_eligible",
            "no_candidate_reason",
        }
        assert payload["route"] == route
        assert payload["route"] in {"clarify", "inspect", "revise", "adapt"}
        assert payload["apply_eligible"] is expected_apply_eligible
        assert payload["candidate"] == candidate
        assert payload["no_candidate_reason"] == expected_reason


# ── ExecutorResult ───────────────────────────────────────────────────────────


class TestExecutorResult:
    def test_default_success(self) -> None:
        r = ExecutorResult()
        assert r.ok is True
        assert isinstance(r.report, Report)
        assert r.graph is None
        assert r.reply is None

    def test_success_convenience(self) -> None:
        graph = {"nodes": []}
        r = ExecutorResult.success(graph=graph, reply="done")
        assert r.ok is True
        assert r.graph == graph
        assert r.reply == "done"

    def test_failure_convenience(self) -> None:
        r = ExecutorResult.failure(kind="ProviderError", stage="classify", message="timeout")
        assert r.ok is False
        assert r.failure_kind == "ProviderError"
        assert r.failure_stage == "classify"
        assert r.failure_message == "timeout"

    def test_to_dict_success(self) -> None:
        plan = ClassifyDecision(plan_summary="chat turn", route="clarify")
        report = Report(plan=plan)
        r = ExecutorResult.success(report=report, reply="Hello!")
        d = r.to_dict()
        assert d["ok"] is True
        assert d["route"] == "clarify"
        assert d["reply"] == "Hello!"
        assert d["candidate"] is None
        assert d["apply_eligible"] is False
        assert d["no_candidate_reason"] == "route_not_applyable"
        assert set(d["evidence"]) == {
            "classification",
            "graph_inspection",
            "research",
            "implementation",
            "warnings",
        }
        assert d["report"]["executor"]["plan"]["plan_summary"] == "chat turn"
        assert "failure_kind" not in d

    def test_to_dict_success_with_apply_eligible_candidate(self) -> None:
        plan = ClassifyDecision(route="revise", task="edit_graph")
        report = Report(
            plan=plan,
            implementation=ImplementationResult(
                graph={"nodes": [{"id": 1}]},
                message="changed graph",
            ),
        )
        r = ExecutorResult.success(
            report=report,
            graph={"nodes": [{"id": 1}]},
            reply="Changed the graph.",
        )

        d = r.to_dict()
        assert d["route"] == "revise"
        assert d["candidate"] == {"graph": {"nodes": [{"id": 1}]}}
        assert d["apply_eligible"] is True
        assert d["no_candidate_reason"] is None

    def test_to_dict_non_apply_route_does_not_promote_graph_to_candidate(self) -> None:
        plan = ClassifyDecision(route="inspect", task="inspect_graph")
        report = Report(plan=plan)
        r = ExecutorResult.success(
            report=report,
            graph={"nodes": [{"id": 1}]},
            reply="Inspected the graph.",
        )

        d = r.to_dict()
        assert d["route"] == "inspect"
        assert d["candidate"] is None
        assert d["apply_eligible"] is False
        assert d["no_candidate_reason"] == "route_not_applyable"

    @pytest.mark.parametrize("route", ["clarify", "inspect"])
    def test_to_dict_non_applyable_routes_never_carry_stale_candidate(
        self,
        route: str,
    ) -> None:
        plan = ClassifyDecision(route=route, task="inspect_graph" if route == "inspect" else "respond")
        report = Report(
            plan=plan,
            implementation=ImplementationResult(
                graph={"nodes": [{"id": 99, "type": "StaleCandidate"}]},
                message="stale edit result",
            ),
        )
        r = ExecutorResult.success(
            report=report,
            graph={"nodes": [{"id": 99, "type": "StaleCandidate"}]},
            reply="No applyable edit.",
        )

        d = r.to_dict()
        assert d["route"] == route
        assert d["candidate"] is None
        assert d["apply_eligible"] is False
        assert d["no_candidate_reason"] == "route_not_applyable"

    def test_to_dict_keeps_internal_disposition_out_of_public_envelope(self) -> None:
        plan = ClassifyDecision(route="direct_edit", task="edit_graph")
        report = Report(plan=plan)
        d = ExecutorResult.success(report=report, reply="No changes.").to_dict()

        assert d["route"] == "revise"
        assert "disposition" not in d
        assert "disposition" not in d["evidence"]

    def test_report_plan_serialization_includes_canonical_derived_route(self) -> None:
        plan = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            intent="edit",
            task="edit_graph",
        )
        report = Report(plan=plan, implementation=ImplementationResult(message="no change"))

        d = ExecutorResult.success(report=report, reply="No changes.").to_dict()

        assert d["route"] == "revise"
        assert d["report"]["executor"]["plan"]["route"] == "revise"
        assert d["report"]["executor"]["plan"]["task"] == "edit_graph"

    def test_report_plan_serialization_never_emits_legacy_route_alias(self) -> None:
        plan = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            intent="edit",
            route="precedent_research",
            task="research_precedent",
        )
        report = Report(plan=plan)

        d = ExecutorResult.success(report=report, reply="No changes.").to_dict()

        assert d["route"] == "adapt"
        assert d["report"]["executor"]["plan"]["route"] == "adapt"
        assert d["report"]["executor"]["plan"]["route"] != "precedent_research"

    def test_to_dict_failure(self) -> None:
        r = ExecutorResult.failure(kind="TimeoutError", stage="classify", message="timed out")
        d = r.to_dict()
        assert d["ok"] is False
        assert d["route"] == "clarify"
        assert d["reply"] == "timed out"
        assert d["candidate"] is None
        assert d["apply_eligible"] is False
        assert d["no_candidate_reason"] == "route_not_applyable"
        assert d["failure_kind"] == "TimeoutError"
        assert d["failure_stage"] == "classify"
        assert d["failure_message"] == "timed out"


# ── Prompt building ──────────────────────────────────────────────────────────


class TestBuildClassifyMessages:
    def test_basic(self) -> None:
        msgs = build_classify_messages("hello")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert "hello" in msgs[1]["content"]

    def test_with_graph(self) -> None:
        msgs = build_classify_messages("edit graph", has_graph=True)
        assert "canvas graph is attached" in msgs[1]["content"]

    def test_with_graph_summary(self) -> None:
        msgs = build_classify_messages("edit graph", has_graph=True, graph_summary="3 nodes, 2 edges")
        content = msgs[1]["content"]
        assert "3 nodes, 2 edges" in content

    def test_no_graph(self) -> None:
        msgs = build_classify_messages("chat question", has_graph=False)
        assert "canvas graph is attached" not in msgs[1]["content"]

    def test_system_prompt_biases_ambiguous_edits_to_clarify(self) -> None:
        msgs = build_classify_messages("change that one", has_graph=True)
        system = msgs[0]["content"]
        assert "deterministic safety checks" in system
        assert "prefer route=\"clarify\"" in system
        assert "rather than guessing a mutation route" in system

    def test_session_context_renders_text_messages_options_and_reference_map(self) -> None:
        msgs = build_classify_messages(
            "option 2",
            has_graph=True,
            session_context={
                "recent_messages": [
                    {"role": "user", "text": "Change the sampler"},
                    {
                        "role": "agent",
                        "text": "Which sampler setting?",
                        "outcome": {"kind": "clarify"},
                    },
                ],
                "prior_clarification": {
                    "clarification_question": "Which sampler setting?",
                    "clarification_options": ["seed", "steps"],
                },
                "prior_route": "revise",
                "prior_task": "edit_graph",
                "latest_candidate": {
                    "turn_id": "0003",
                    "outcome": {"kind": "candidate"},
                    "change_details": {
                        "operations": [
                            {"summary": "changed KSampler steps"},
                            {"field_path": "nodes.2.widgets_values.1"},
                        ],
                    },
                },
            },
            graph_reference_map={"2": "KSampler", "1": "CheckpointLoaderSimple"},
        )
        content = msgs[1]["content"]
        assert "Recent conversation (for reference resolution):" in content
        assert "[user]: Change the sampler" in content
        assert "Prior clarification question: Which sampler setting?" in content
        assert "2. steps" in content
        assert 'previous turn was blocked on route="revise", task="edit_graph"' in content
        assert "Latest candidate reference" in content
        assert "turn=0003" in content
        assert "changed KSampler steps" in content
        assert "id=1: CheckpointLoaderSimple" in content
        assert "id=2: KSampler" in content


class TestBuildReplyMessages:
    def test_basic(self) -> None:
        msgs = build_reply_messages("hello")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_with_plan(self) -> None:
        plan = ClassifyDecision(plan_summary="simple chat reply")
        msgs = build_reply_messages("hello", plan=plan)
        assert "simple chat reply" in msgs[1]["content"]

    def test_with_research(self) -> None:
        msgs = build_reply_messages("edit", research_summary="found 2 templates")
        assert "found 2 templates" in msgs[1]["content"]

    def test_with_implementation(self) -> None:
        msgs = build_reply_messages("edit", implementation_message="added KSsampler node")
        assert "added KSsampler node" in msgs[1]["content"]

    def test_full_context(self) -> None:
        plan = ClassifyDecision(plan_summary="edit with research")
        msgs = build_reply_messages(
            "edit",
            plan=plan,
            research_summary="found template",
            implementation_message="applied template",
        )
        content = msgs[1]["content"]
        assert "edit with research" in content
        assert "found template" in content
        assert "applied template" in content

    def test_research_implementation_prompt_requests_concise_rationale(self) -> None:
        msgs = build_reply_messages(
            "edit",
            research_summary="found a relevant custom-audio workflow",
            implementation_message="applied the custom-audio wiring pattern",
        )
        system = msgs[0]["content"]
        assert "include one brief reason" in system
        assert "chosen approach/source informed the edit" in system
        assert "Do not dump the research summary" in system
        assert "quality scores only when that metadata is explicitly present" in system


# ── Response parsers ─────────────────────────────────────────────────────────


class TestParseClassifyResponse:
    def test_valid_respond_only(self) -> None:
        raw = '{"research": false, "implement": false, "reply": true, "effort": "low", "plan_summary": "chat question"}'
        d = parse_classify_response(raw)
        assert d.research is False
        assert d.implement is False
        assert d.reply is True
        assert d.effort == "low"
        assert d.plan_summary == "chat question"

    def test_valid_edit(self) -> None:
        raw = '{"research": true, "implement": true, "reply": true, "effort": "medium", "plan_summary": "edit seed"}'
        d = parse_classify_response(raw)
        assert d.research is True
        assert d.implement is True
        assert d.effort == "medium"

    def test_missing_keys_default(self) -> None:
        raw = '{"reply": false}'
        d = parse_classify_response(raw)
        assert d.research is False
        assert d.implement is False
        assert d.reply is False
        assert d.effort == "low"
        assert d.plan_summary == ""

    def test_json_with_fences(self) -> None:
        raw = '```json\n{"research": false, "implement": false, "reply": true, "effort": "low", "plan_summary": "x"}\n```'
        d = parse_classify_response(raw)
        assert d.research is False

    def test_json_with_trailing_text(self) -> None:
        raw = '{"research": true, "implement": false, "reply": true, "effort": "low", "plan_summary": "ok"} (done)'
        d = parse_classify_response(raw)
        assert d.research is True

    def test_non_bool_coercion(self) -> None:
        raw = '{"research": "yes", "implement": 0, "reply": 1, "effort": "low", "plan_summary": ""}'
        d = parse_classify_response(raw)
        assert d.research is True  # "yes" is truthy
        assert d.implement is False  # 0 is falsy
        assert d.reply is True  # 1 is truthy

    def test_bad_effort_defaults(self) -> None:
        raw = '{"research": false, "implement": false, "reply": true, "effort": "extreme", "plan_summary": ""}'
        d = parse_classify_response(raw)
        assert d.effort == "low"  # clamped

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_classify_response("not json at all")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_classify_response("")

    def test_non_object_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_classify_response('["list", "not", "object"]')

    def test_plan_summary_stripped(self) -> None:
        raw = '{"research": false, "implement": false, "reply": true, "effort": "low", "plan_summary": "  hello world  "}'
        d = parse_classify_response(raw)
        assert d.plan_summary == "hello world"


    def test_parse_with_route_and_task(self) -> None:
        """Parser correctly extracts route and task from JSON."""
        raw = json.dumps({
            "research": False,
            "implement": True,
            "reply": True,
            "effort": "low",
            "plan_summary": "simple edit",
            "intent": "edit",
            "route": "revise",
            "task": "edit_graph",
        })
        d = parse_classify_response(raw)
        assert d.route == "revise"
        assert d.task == "edit_graph"
        assert d.effective_route == "revise"
        assert d.effective_task == "edit_graph"

    def test_parse_legacy_explicit_route_serializes_canonical(self) -> None:
        raw = json.dumps({
            "research": False,
            "implement": True,
            "reply": True,
            "effort": "low",
            "plan_summary": "legacy route",
            "intent": "edit",
            "route": "direct_edit",
            "task": "edit_graph",
        })
        d = parse_classify_response(raw)

        assert d.route == "revise"
        assert d.effective_route == "revise"
        assert d.to_dict()["route"] == "revise"

    def test_parse_unknown_explicit_route_serializes_clarify(self) -> None:
        raw = json.dumps({
            "research": True,
            "implement": True,
            "reply": True,
            "effort": "medium",
            "plan_summary": "unknown route",
            "intent": "edit",
            "route": "retired_route",
            "task": "edit_graph",
        })
        d = parse_classify_response(raw)

        assert d.route == "clarify"
        assert d.effective_route == "clarify"
        assert d.to_dict()["route"] == "clarify"

    def test_parse_with_route_only(self) -> None:
        """Parser handles JSON with route but no task field."""
        raw = json.dumps({
            "research": True,
            "implement": False,
            "reply": True,
            "effort": "low",
            "plan_summary": "inspect graph",
            "intent": "explain_graph",
            "route": "inspect",
        })
        d = parse_classify_response(raw)
        assert d.route == "inspect"
        assert d.task == ""
        assert d.effective_route == "inspect"
        # task derived from legacy
        assert d.effective_task == "inspect_graph"

    def test_parse_with_adapt_route(self) -> None:
        """Parser handles adapt route with both research and implement true."""
        raw = json.dumps({
            "research": True,
            "implement": True,
            "reply": True,
            "effort": "high",
            "plan_summary": "research then edit",
            "intent": "edit",
            "route": "adapt",
            "task": "research_precedent",
        })
        d = parse_classify_response(raw)
        assert d.route == "adapt"
        assert d.task == "research_precedent"
        assert d.research is True
        assert d.implement is True
        # effective_route uses explicit route
        assert d.effective_route == "adapt"
        assert d.effective_task == "research_precedent"

    def test_parse_clarify_route(self) -> None:
        """Parser handles clarify route with no research or implement."""
        raw = json.dumps({
            "research": False,
            "implement": False,
            "reply": True,
            "effort": "low",
            "plan_summary": "clarifying question",
            "intent": "respond",
            "route": "clarify",
            "task": "respond",
        })
        d = parse_classify_response(raw)
        assert d.route == "clarify"
        assert d.task == "respond"
        assert d.effective_route == "clarify"
        assert d.effective_task == "respond"

    def test_parse_old_json_no_route_fields_still_works(self) -> None:
        """Legacy JSON without route/task keys parses and derives correctly."""
        raw = json.dumps({
            "research": False,
            "implement": True,
            "reply": True,
            "effort": "medium",
            "plan_summary": "edit seed",
            "intent": "edit",
        })
        d = parse_classify_response(raw)
        assert d.route == ""
        assert d.task == ""
        # Derived from legacy
        assert d.effective_route == "revise"
        assert d.effective_task == "edit_graph"

    def test_parse_intent_derived_from_legacy_booleans(self) -> None:
        """When intent is missing or invalid, parser derives from research/implement."""
        # Missing intent, implement=True → intent="edit"
        raw = json.dumps({
            "research": False,
            "implement": True,
            "reply": True,
            "effort": "low",
            "plan_summary": "edit",
        })
        d = parse_classify_response(raw)
        assert d.intent == "edit"

        # Missing intent, research=True, implement=False → intent="research"
        raw2 = json.dumps({
            "research": True,
            "implement": False,
            "reply": True,
            "effort": "low",
            "plan_summary": "research",
        })
        d2 = parse_classify_response(raw2)
        assert d2.intent == "research"

        # Invalid intent, research=False, implement=False → intent="respond"
        raw3 = json.dumps({
            "research": False,
            "implement": False,
            "reply": True,
            "effort": "low",
            "plan_summary": "chat",
            "intent": "bogus",
        })
        d3 = parse_classify_response(raw3)
        assert d3.intent == "respond"

    def test_parse_route_stripped_of_whitespace(self) -> None:
        """Route field is whitespace-stripped during parsing."""
        raw = json.dumps({
            "research": False,
            "implement": True,
            "reply": True,
            "effort": "low",
            "plan_summary": "edit",
            "route": "  revise  ",
            "task": "  edit_graph  ",
        })
        d = parse_classify_response(raw)
        assert d.route == "revise"
        assert d.task == "edit_graph"

    def test_parse_route_non_string_coerced_to_empty(self) -> None:
        """Non-string route values are coerced to empty string."""
        raw = '{"research": false, "implement": false, "reply": true, "effort": "low", "plan_summary": "", "route": 123, "task": null}'
        d = parse_classify_response(raw)
        assert d.route == ""
        assert d.task == ""


class TestParseReplyResponse:
    def test_valid_reply(self) -> None:
        raw = '{"reply": "I have set the seed to 42."}'
        text = parse_reply_response(raw)
        assert text == "I have set the seed to 42."

    def test_fallback_message_key(self) -> None:
        raw = '{"message": "The graph was edited successfully."}'
        text = parse_reply_response(raw)
        assert text == "The graph was edited successfully."

    def test_fallback_response_key(self) -> None:
        raw = '{"response": "All done."}'
        text = parse_reply_response(raw)
        assert text == "All done."

    def test_fallback_content_key(self) -> None:
        raw = '{"content": "Here you go."}'
        text = parse_reply_response(raw)
        assert text == "Here you go."

    def test_fallback_text_key(self) -> None:
        raw = '{"text": "Done."}'
        text = parse_reply_response(raw)
        assert text == "Done."

    def test_empty_reply_raises(self) -> None:
        raw = '{"reply": ""}'
        with pytest.raises(ValueError, match="reply"):
            parse_reply_response(raw)

    def test_no_valid_key_raises(self) -> None:
        raw = '{"unknown": "value"}'
        with pytest.raises(ValueError, match="reply"):
            parse_reply_response(raw)

    def test_reply_with_fences(self) -> None:
        raw = '```\n{"reply": "Done!"}\n```'
        text = parse_reply_response(raw)
        assert text == "Done!"

    def test_malformed_json_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_reply_response("not json")

    def test_strips_whitespace(self) -> None:
        raw = '{"reply": "  padded  "}'
        text = parse_reply_response(raw)
        assert text == "padded"


# ── Round-trip: classify → parse ─────────────────────────────────────────────


class TestClassifyRoundtrip:
    def test_respond_only_roundtrip(self) -> None:
        decision = ClassifyDecision.respond_only(plan_summary="chat")
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision

    def test_edit_roundtrip(self) -> None:
        decision = ClassifyDecision.edit(research=True, effort="medium", plan_summary="set seed")
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision

    def test_edit_no_research_roundtrip(self) -> None:
        decision = ClassifyDecision.edit(research=False, effort="low", plan_summary="simple edit")
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision


# ── ExecutorResult round-trip ────────────────────────────────────────────────

    def test_roundtrip_with_route_and_task(self) -> None:
        """Full roundtrip with explicit route and task fields."""
        decision = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="low",
            plan_summary="simple edit",
            intent="edit",
            route="revise",
            task="edit_graph",
        )
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision
        assert parsed.route == "revise"
        assert parsed.task == "edit_graph"

    def test_roundtrip_adapt(self) -> None:
        """Roundtrip with adapt route and both research/implement true."""
        decision = ClassifyDecision(
            research=True,
            implement=True,
            reply=True,
            effort="high",
            plan_summary="research precedent then edit",
            intent="edit",
            route="adapt",
            task="research_precedent",
        )
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision
        assert parsed.route == "adapt"
        assert parsed.task == "research_precedent"

    def test_roundtrip_clarify(self) -> None:
        """Roundtrip with clarify route."""
        decision = ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            effort="low",
            plan_summary="clarifying question",
            intent="respond",
            route="clarify",
            task="respond",
        )
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision

    def test_roundtrip_inspect(self) -> None:
        """Roundtrip with inspect route."""
        decision = ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            effort="medium",
            plan_summary="inspect graph structure",
            intent="explain_graph",
            route="inspect",
            task="inspect_graph",
        )
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)
        assert parsed == decision

    def test_roundtrip_old_json_shape_still_works(self) -> None:
        """Old JSON without route/task still round-trips correctly."""
        decision = ClassifyDecision(
            research=False,
            implement=True,
            reply=True,
            effort="medium",
            plan_summary="edit seed",
            intent="edit",
        )
        raw = json.dumps(decision.to_dict())
        assert "route" not in json.loads(raw)
        assert "task" not in json.loads(raw)
        parsed = parse_classify_response(raw)
        assert parsed == decision
        # effective properties still work
        assert parsed.effective_route == "revise"
        assert parsed.effective_task == "edit_graph"



# ── Route classification scenario fixtures (10 documented classes) ──────────

# These 10 scenarios are sourced from docs/plans/workflow-precedent-scenario-coverage.md.
# Each fixture asserts the normalized route, legacy booleans, intent, effort,
# task, and key metadata for a documented user-task class without making any
# live model call.

_SCENARIO_FIXTURES = [
    # ── 1. seed/prefix widget update ──────────────────────────────────────
    pytest.param(
        "seed/prefix widget update",
        dict(
            research=False, implement=True, reply=True, effort="low",
            plan_summary="update seed/prefix widget parameter",
            intent="edit", route="revise", task="edit_graph",
        ),
        "revise",  # expected effective_route
        False,          # expected research
        True,           # expected implement
        "edit",         # expected intent
        "low",          # expected effort
        "edit_graph",   # expected effective_task
        id="sc01_seed_prefix_widget",
    ),
    # ── 2. PreviewImage tap ──────────────────────────────────────────────
    pytest.param(
        "PreviewImage tap",
        dict(
            research=False, implement=False, reply=True, effort="low",
            plan_summary="preview intermediate PreviewImage node output",
            intent="explain_graph", route="clarify", task="preview_subgraph",
        ),
        "clarify",
        False,
        False,
        "explain_graph",
        "low",
        "preview_subgraph",
        id="sc02_preview_image_tap",
    ),
    # ── 3. explain current graph ─────────────────────────────────────────
    pytest.param(
        "explain current graph",
        dict(
            research=False, implement=False, reply=True, effort="medium",
            plan_summary="explain current graph structure and connections",
            intent="explain_graph", route="inspect", task="inspect_graph",
        ),
        "inspect",
        False,
        False,
        "explain_graph",
        "medium",
        "inspect_graph",
        id="sc03_explain_graph",
    ),
    # ── 4. LTX user audio path (external workflow precedent) ─────────────
    pytest.param(
        "LTX user audio path",
        dict(
            research=True, implement=True, reply=True, effort="high",
            plan_summary="add LTX audio pipeline from external workflow precedent",
            intent="edit", route="adapt", task="research_precedent",
        ),
        "adapt",
        True,
        True,
        "edit",
        "high",
        "research_precedent",
        id="sc04_ltx_audio_path",
    ),
    # ── 5. ambiguous audio ───────────────────────────────────────────────
    pytest.param(
        "ambiguous audio request",
        dict(
            research=False, implement=False, reply=True, effort="low",
            plan_summary="clarify ambiguous audio request before routing",
            intent="respond", route="clarify", task="respond",
        ),
        "clarify",
        False,
        False,
        "respond",
        "low",
        "respond",
        id="sc05_ambiguous_audio",
    ),
    # ── 6. asset swap ────────────────────────────────────────────────────
    pytest.param(
        "model/asset config swap",
        dict(
            research=False, implement=True, reply=True, effort="medium",
            plan_summary="swap model/asset configuration using registry",
            intent="edit", route="revise", task="find_assets",
        ),
        "revise",
        False,
        True,
        "edit",
        "medium",
        "find_assets",
        id="sc06_asset_swap",
    ),
    # ── 7. dangling audio repair ─────────────────────────────────────────
    pytest.param(
        "dangling audio node repair",
        dict(
            research=True, implement=True, reply=True, effort="high",
            plan_summary="diagnose and repair dangling audio connections",
            intent="edit", route="revise", task="diagnose",
        ),
        "revise",
        True,
        True,
        "edit",
        "high",
        "diagnose",
        id="sc07_dangling_audio_repair",
    ),
    # ── 8. runtime preview ───────────────────────────────────────────────
    pytest.param(
        "runtime subgraph preview",
        dict(
            research=False, implement=False, reply=True, effort="low",
            plan_summary="evaluate subgraph at runtime without mutating canvas",
            intent="explain_graph", route="clarify", task="preview_subgraph",
        ),
        "clarify",
        False,
        False,
        "explain_graph",
        "low",
        "preview_subgraph",
        id="sc08_runtime_preview",
    ),
    # ── 9. composite / decompose ─────────────────────────────────────────
    pytest.param(
        "composite multi-pattern edit",
        dict(
            research=True, implement=True, reply=True, effort="high",
            plan_summary="decompose composite edit into per-subgoal precedent research",
            intent="edit", route="adapt", task="research_precedent",
        ),
        "adapt",
        True,
        True,
        "edit",
        "high",
        "research_precedent",
        id="sc09_composite_decompose",
    ),
    # ── 10. respond-only ──────────────────────────────────────────────────
    pytest.param(
        "respond-only informational turn",
        dict(
            research=False, implement=False, reply=True, effort="low",
            plan_summary="informational response only, no research or edit",
            intent="respond", route="clarify", task="respond",
        ),
        "clarify",
        False,
        False,
        "respond",
        "low",
        "respond",
        id="sc10_respond_only",
    ),
]


class TestRouteScenarioFixtures:
    """Focused route-classification fixtures for the 10 documented scenario classes.

    Each test constructs a ClassifyDecision for one scenario and asserts the
    normalized effective_route, legacy research/implement booleans, intent,
    effort, and effective_task  without making any live model call.
    """

    @pytest.mark.parametrize(
        "scenario_name,kwargs,expected_route,expected_research,expected_implement,"
        "expected_intent,expected_effort,expected_task",
        _SCENARIO_FIXTURES,
    )
    def test_scenario_fixture_normalized_route_and_metadata(
        self,
        scenario_name: str,
        kwargs: dict,
        expected_route: str,
        expected_research: bool,
        expected_implement: bool,
        expected_intent: str,
        expected_effort: str,
        expected_task: str,
    ) -> None:
        """Each documented scenario class maps to the correct route + metadata."""
        decision = ClassifyDecision(**kwargs)

        # Effective route is the authoritative phase gate.
        assert decision.effective_route == expected_route, (
            f"{scenario_name}: expected effective_route={expected_route}, "
            f"got {decision.effective_route}"
        )

        # Legacy booleans remain correct.
        assert decision.research == expected_research, (
            f"{scenario_name}: research mismatch"
        )
        assert decision.implement == expected_implement, (
            f"{scenario_name}: implement mismatch"
        )

        # Intent.
        assert decision.intent == expected_intent, (
            f"{scenario_name}: intent mismatch"
        )

        # Effort hint.
        assert decision.effort == expected_effort, (
            f"{scenario_name}: effort mismatch"
        )

        # Normalized task.
        assert decision.effective_task == expected_task, (
            f"{scenario_name}: expected effective_task={expected_task}, "
            f"got {decision.effective_task}"
        )

        # Reply is always True for these scenarios (executor should produce a reply).
        assert decision.reply is True, (
            f"{scenario_name}: reply should be True"
        )

    @pytest.mark.parametrize(
        "scenario_name,kwargs,expected_route,expected_research,expected_implement,"
        "expected_intent,expected_effort,expected_task",
        _SCENARIO_FIXTURES,
    )
    def test_scenario_fixture_roundtrip_through_parser(
        self,
        scenario_name: str,
        kwargs: dict,
        expected_route: str,
        expected_research: bool,
        expected_implement: bool,
        expected_intent: str,
        expected_effort: str,
        expected_task: str,
    ) -> None:
        """Each scenario fixture survives a JSON serialize -> parse round-trip."""
        decision = ClassifyDecision(**kwargs)
        raw = json.dumps(decision.to_dict())
        parsed = parse_classify_response(raw)

        assert parsed == decision, (
            f"{scenario_name}: round-trip mismatch"
        )

        # Re-assert key fields on the parsed instance.
        assert parsed.effective_route == expected_route
        assert parsed.research == expected_research
        assert parsed.implement == expected_implement
        assert parsed.intent == expected_intent
        assert parsed.effort == expected_effort
        assert parsed.effective_task == expected_task

    @pytest.mark.parametrize(
        "scenario_name,kwargs,expected_route,expected_research,expected_implement,"
        "expected_intent,expected_effort,expected_task",
        _SCENARIO_FIXTURES,
    )
    def test_scenario_fixture_to_dict_includes_route_and_task(
        self,
        scenario_name: str,
        kwargs: dict,
        expected_route: str,
        expected_research: bool,
        expected_implement: bool,
        expected_intent: str,
        expected_effort: str,
        expected_task: str,
    ) -> None:
        """to_dict() emits route and task when non-empty."""
        decision = ClassifyDecision(**kwargs)
        d = decision.to_dict()

        assert d["route"] == expected_route, (
            f"{scenario_name}: route not emitted correctly"
        )
        assert d["task"] == expected_task, (
            f"{scenario_name}: task not emitted correctly"
        )

    def test_all_10_scenarios_accounted_for(self) -> None:
        """Smoke check: the fixture list has exactly 10 entries."""
        assert len(_SCENARIO_FIXTURES) == 10, (
            f"Expected 10 scenario fixtures, got {len(_SCENARIO_FIXTURES)}"
        )


class TestExecutorResultRoundtrip:
    def test_full_success_roundtrip(self) -> None:
        plan = ClassifyDecision(research=True, implement=True, reply=True, effort="medium", plan_summary="edit graph")
        research = ResearchResult(summary="found 2 templates", sources=({"id": "t1"},), warnings=("hivemind slow",))
        impl = ImplementationResult(graph={"nodes": [1]}, message="added node", delta=({"op": "add"},))
        report = Report(plan=plan, research=research, implementation=impl)
        result = ExecutorResult.success(report=report, graph={"nodes": [1]}, reply="Graph edited successfully.")

        d = result.to_dict()
        assert d["ok"] is True
        assert d["reply"] == "Graph edited successfully."
        assert d["graph"] == {"nodes": [1]}
        assert d["report"]["executor"]["plan"]["research"] is True
        assert d["report"]["executor"]["research"]["summary"] == "found 2 templates"
        assert d["report"]["executor"]["research"]["sources"] == [{"id": "t1"}]
        assert d["report"]["executor"]["research"]["warnings"] == ["hivemind slow"]
        assert d["report"]["executor"]["implementation"]["message"] == "added node"
        assert d["report"]["executor"]["implementation"]["delta"] == [{"op": "add"}]

    def test_failure_roundtrip(self) -> None:
        plan = ClassifyDecision.respond_only()
        report = Report(plan=plan)
        result = ExecutorResult.failure(kind="ProviderError", stage="classify", message="timeout", report=report)

        d = result.to_dict()
        assert d["ok"] is False
        assert d["failure_kind"] == "ProviderError"
        assert d["failure_stage"] == "classify"
        assert d["failure_message"] == "timeout"
        assert d["report"]["executor"]["plan"]["reply"] is True

# ── InspectionSummary contract tests (T9) ────────────────────────────────────


class TestInspectionSummary:
    """Round-trip and edge-case tests for InspectionSummary dataclass."""

    def test_defaults(self) -> None:
        s = InspectionSummary()
        assert s.node_count == 0
        assert s.node_types == ()
        assert s.has_dangling_inputs is False
        assert s.has_dangling_outputs is False
        assert s.key_widget_values == ()
        assert s.summary == ""

    def test_to_dict_defaults(self) -> None:
        s = InspectionSummary()
        d = s.to_dict()
        assert d == {
            "node_count": 0,
            "node_types": [],
            "has_dangling_inputs": False,
            "has_dangling_outputs": False,
            "key_widget_values": [],
            "summary": "",
        }

    def test_to_dict_with_data(self) -> None:
        s = InspectionSummary(
            node_count=5,
            node_types=("KSampler", "VAEDecode", "CLIPTextEncode"),
            has_dangling_inputs=True,
            has_dangling_outputs=False,
            key_widget_values=({"seed": 42}, {"steps": 20}),
            summary="3 core nodes, 1 dangling input",
        )
        d = s.to_dict()
        assert d["node_count"] == 5
        assert d["node_types"] == ["KSampler", "VAEDecode", "CLIPTextEncode"]
        assert d["has_dangling_inputs"] is True
        assert d["has_dangling_outputs"] is False
        assert d["key_widget_values"] == [{"seed": 42}, {"steps": 20}]
        assert d["summary"] == "3 core nodes, 1 dangling input"

    def test_key_widget_values_are_frozen(self) -> None:
        s = InspectionSummary(
            node_count=1,
            key_widget_values=({"seed": 42},),
        )
        # Tuples are immutable; frozen dataclass prevents field reassignment
        with pytest.raises(Exception):
            s.key_widget_values = ()  # type: ignore[misc]

    def test_node_types_coerced_to_tuple(self) -> None:
        s = InspectionSummary(node_types=["KSampler", "VAEDecode"])
        assert isinstance(s.node_types, tuple)
        assert s.node_types == ("KSampler", "VAEDecode")


# ── WorkflowSlice contract tests (T9) ────────────────────────────────────────


class TestWorkflowSlice:
    """Round-trip and edge-case tests for WorkflowSlice dataclass."""

    def test_defaults(self) -> None:
        ws = WorkflowSlice()
        assert ws.source_class_type == ""
        assert ws.node_ids == ()
        assert ws.entry_anchor is None
        assert ws.exit_anchor is None
        assert ws.python_path is None

    def test_to_dict_defaults(self) -> None:
        ws = WorkflowSlice()
        d = ws.to_dict()
        assert d == {
            "source_class_type": "",
            "node_ids": [],
        }
        # Optional fields are omitted when None
        assert "entry_anchor" not in d
        assert "exit_anchor" not in d
        assert "python_path" not in d

    def test_to_dict_with_all_fields(self) -> None:
        ws = WorkflowSlice(
            source_class_type="LTXRuneXXCustomAudioLipsync",
            node_ids=("45", "46", "47"),
            entry_anchor="45",
            exit_anchor="47",
            python_path="custom_nodes/ltxvideo/LTX_audio_lipsync.py",
        )
        d = ws.to_dict()
        assert d["source_class_type"] == "LTXRuneXXCustomAudioLipsync"
        assert d["node_ids"] == ["45", "46", "47"]
        assert d["entry_anchor"] == "45"
        assert d["exit_anchor"] == "47"
        assert d["python_path"] == "custom_nodes/ltxvideo/LTX_audio_lipsync.py"

    def test_to_dict_none_anchors_omitted(self) -> None:
        ws = WorkflowSlice(
            source_class_type="KSampler",
            node_ids=("10",),
            entry_anchor=None,
            exit_anchor=None,
            python_path=None,
        )
        d = ws.to_dict()
        assert d == {
            "source_class_type": "KSampler",
            "node_ids": ["10"],
        }

    def test_node_ids_coerced_to_tuple(self) -> None:
        ws = WorkflowSlice(node_ids=["1", "2", "3"])
        assert isinstance(ws.node_ids, tuple)
        assert ws.node_ids == ("1", "2", "3")

    def test_immutable(self) -> None:
        ws = WorkflowSlice(source_class_type="KSampler", node_ids=("1",))
        with pytest.raises(Exception):
            ws.source_class_type = "Other"  # type: ignore[misc]


# ── PrecedentAdaptationPlan contract tests (T9) ──────────────────────────────


class TestPrecedentAdaptationPlan:
    """Round-trip and edge-case tests for PrecedentAdaptationPlan dataclass."""

    def test_defaults(self) -> None:
        pap = PrecedentAdaptationPlan()
        assert isinstance(pap.selected_slice, WorkflowSlice)
        assert pap.selected_slice.source_class_type == ""
        assert pap.anchor_bindings == ()
        assert pap.required_new_nodes == ()
        assert pap.required_rewires == ()
        assert pap.edit_ops == ()
        assert pap.candidate_graph is None
        assert pap.structural_validation == "not_evaluated"
        assert pap.semantic_validation == "not_evaluated"

    def test_to_dict_defaults(self) -> None:
        pap = PrecedentAdaptationPlan()
        d = pap.to_dict()
        assert d["selected_slice"] == {"source_class_type": "", "node_ids": []}
        assert d["anchor_bindings"] == []
        assert d["required_new_nodes"] == []
        assert d["required_rewires"] == []
        assert d["edit_ops"] == []
        assert d["structural_validation"] == "not_evaluated"
        assert d["semantic_validation"] == "not_evaluated"
        # candidate_graph omitted when None
        assert "candidate_graph" not in d

    def test_to_dict_with_all_fields(self) -> None:
        ws = WorkflowSlice(
            source_class_type="LTXAudioLipsync",
            node_ids=("100", "101"),
            entry_anchor="100",
            exit_anchor="101",
        )
        pap = PrecedentAdaptationPlan(
            selected_slice=ws,
            anchor_bindings=(
                {"source": "100", "target": "LoadImage.output"},
                {"source": "101", "target": "VAEDecode.input"},
            ),
            required_new_nodes=(
                {"class_type": "AudioLoader", "widget_values": {"file": "audio.wav"}},
            ),
            required_rewires=(
                {"from_node": "100", "from_output": 0, "to_node": "AudioLoader", "to_input": 0},
            ),
            edit_ops=(
                {"op": "add_node", "class_type": "AudioLoader"},
                {"op": "rewire", "from": "100", "to": "AudioLoader"},
            ),
            candidate_graph={"nodes": [{"id": 1, "type": "LoadImage"}, {"id": 2, "type": "AudioLoader"}]},
            structural_validation="pass",
            semantic_validation="advisory",
        )
        d = pap.to_dict()
        assert d["selected_slice"]["source_class_type"] == "LTXAudioLipsync"
        assert len(d["anchor_bindings"]) == 2
        assert d["anchor_bindings"][0]["source"] == "100"
        assert len(d["required_new_nodes"]) == 1
        assert d["required_new_nodes"][0]["class_type"] == "AudioLoader"
        assert len(d["required_rewires"]) == 1
        assert len(d["edit_ops"]) == 2
        assert d["edit_ops"][0]["op"] == "add_node"
        assert d["candidate_graph"] == {"nodes": [{"id": 1, "type": "LoadImage"}, {"id": 2, "type": "AudioLoader"}]}
        assert d["structural_validation"] == "pass"
        assert d["semantic_validation"] == "advisory"

    def test_validation_values_are_clamped(self) -> None:
        """Invalid validation values are clamped to 'not_evaluated'."""
        pap = PrecedentAdaptationPlan(
            structural_validation="bogus",
            semantic_validation="invalid",
        )
        assert pap.structural_validation == "not_evaluated"
        assert pap.semantic_validation == "not_evaluated"

    def test_validation_allows_all_valid_values(self) -> None:
        """All canonical validation values are accepted."""
        for val in ("not_evaluated", "pass", "fail", "advisory"):
            pap = PrecedentAdaptationPlan(structural_validation=val)
            assert pap.structural_validation == val
            pap2 = PrecedentAdaptationPlan(semantic_validation=val)
            assert pap2.semantic_validation == val

    def test_candidate_graph_omitted_when_none(self) -> None:
        pap = PrecedentAdaptationPlan()
        d = pap.to_dict()
        assert "candidate_graph" not in d

    def test_immutable(self) -> None:
        pap = PrecedentAdaptationPlan()
        with pytest.raises(Exception):
            pap.structural_validation = "pass"  # type: ignore[misc]


# ── ResearchResult precedent field contract tests (T9) ───────────────────────


class TestResearchResultPrecedentFields:
    """Verify ResearchResult.to_dict() legacy shape is unchanged and
    new structured precedent fields are predictable when populated."""

    # ── Legacy shape preservation ────────────────────────────────────────

    def test_legacy_to_dict_no_precedent_fields(self) -> None:
        """No precedent_slices or adaptation_plan → legacy output shape only."""
        rr = ResearchResult(
            summary="Found 3 templates for KSampler",
            sources=(
                {"class_type": "KSampler", "pack": "core"},
                {"class_type": "KSamplerAdvanced", "pack": "efficiency"},
            ),
            warnings=("hivemind timeout",),
        )
        d = rr.to_dict()
        # Legacy keys
        assert d["summary"] == "Found 3 templates for KSampler"
        assert d["sources"] == [
            {"class_type": "KSampler", "pack": "core"},
            {"class_type": "KSamplerAdvanced", "pack": "efficiency"},
        ]
        assert d["warnings"] == ["hivemind timeout"]
        # New keys must NOT leak into legacy output
        assert "precedent_slices" not in d
        assert "adaptation_plan" not in d

    def test_legacy_to_dict_empty_defaults(self) -> None:
        """Default ResearchResult (all empty) produces only legacy keys."""
        rr = ResearchResult()
        d = rr.to_dict()
        assert d == {
            "summary": "",
            "sources": [],
            "warnings": [],
        }

    def test_legacy_to_dict_with_only_summary(self) -> None:
        """Summary-only result preserves legacy shape."""
        rr = ResearchResult(summary="No relevant local results found.")
        d = rr.to_dict()
        assert d == {
            "summary": "No relevant local results found.",
            "sources": [],
            "warnings": [],
        }
        assert "precedent_slices" not in d
        assert "adaptation_plan" not in d

    def test_legacy_to_dict_with_sources_no_warnings(self) -> None:
        """Sources present, no warnings → legacy shape preserved."""
        rr = ResearchResult(
            summary="research output",
            sources=({"name": "node1"}, {"name": "node2"}),
        )
        d = rr.to_dict()
        assert "summary" in d
        assert "sources" in d
        assert "warnings" in d
        assert "precedent_slices" not in d
        assert "adaptation_plan" not in d

    # ── Populated precedent fields ───────────────────────────────────────

    def test_to_dict_with_precedent_slices(self) -> None:
        """precedent_slices present → included in output."""
        ws = WorkflowSlice(
            source_class_type="LTXAudioLipsync",
            node_ids=("10", "11"),
            entry_anchor="10",
            exit_anchor="11",
        )
        rr = ResearchResult(
            summary="Found 1 matching precedent",
            sources=(),
            warnings=(),
            precedent_slices=(ws,),
        )
        d = rr.to_dict()
        # Legacy keys still present
        assert d["summary"] == "Found 1 matching precedent"
        assert d["sources"] == []
        assert d["warnings"] == []
        # New key present
        assert "precedent_slices" in d
        assert len(d["precedent_slices"]) == 1
        assert d["precedent_slices"][0]["source_class_type"] == "LTXAudioLipsync"
        # adaptation_plan still absent
        assert "adaptation_plan" not in d

    def test_to_dict_with_multiple_precedent_slices(self) -> None:
        """Multiple precedent slices are serialized correctly."""
        ws1 = WorkflowSlice(source_class_type="KSampler", node_ids=("1",))
        ws2 = WorkflowSlice(source_class_type="VAEDecode", node_ids=("2",))
        rr = ResearchResult(
            summary="Multiple precedents",
            sources=(),
            warnings=(),
            precedent_slices=(ws1, ws2),
        )
        d = rr.to_dict()
        assert len(d["precedent_slices"]) == 2
        assert d["precedent_slices"][0]["source_class_type"] == "KSampler"
        assert d["precedent_slices"][1]["source_class_type"] == "VAEDecode"

    def test_to_dict_with_adaptation_plan(self) -> None:
        """adaptation_plan present → included in output."""
        ws = WorkflowSlice(
            source_class_type="LTXAudioLipsync",
            node_ids=("100", "101"),
            entry_anchor="100",
            exit_anchor="101",
        )
        pap = PrecedentAdaptationPlan(
            selected_slice=ws,
            structural_validation="pass",
            semantic_validation="pass",
        )
        rr = ResearchResult(
            summary="Precedent adapted",
            sources=(),
            warnings=(),
            adaptation_plan=pap,
        )
        d = rr.to_dict()
        assert d["summary"] == "Precedent adapted"
        assert "adaptation_plan" in d
        assert d["adaptation_plan"]["selected_slice"]["source_class_type"] == "LTXAudioLipsync"
        assert d["adaptation_plan"]["structural_validation"] == "pass"
        # precedent_slices still absent when empty
        assert "precedent_slices" not in d

    def test_to_dict_with_both_precedent_fields(self) -> None:
        """Both precedent_slices and adaptation_plan populated."""
        ws = WorkflowSlice(
            source_class_type="HotshotXL",
            node_ids=("5", "6", "7"),
            entry_anchor="5",
            exit_anchor="7",
        )
        pap = PrecedentAdaptationPlan(
            selected_slice=ws,
            anchor_bindings=({"source": "5", "target": "SVD_XT.output"},),
            structural_validation="advisory",
        )
        rr = ResearchResult(
            summary="HotshotXL → SVD-XT adaptation plan",
            sources=({"class_type": "HotshotXL"},),
            warnings=("Some nodes may need custom import",),
            precedent_slices=(ws,),
            adaptation_plan=pap,
        )
        d = rr.to_dict()
        assert d["summary"] == "HotshotXL → SVD-XT adaptation plan"
        assert d["sources"] == [{"class_type": "HotshotXL"}]
        assert d["warnings"] == ["Some nodes may need custom import"]
        # Both new fields present
        assert "precedent_slices" in d
        assert len(d["precedent_slices"]) == 1
        assert d["precedent_slices"][0]["source_class_type"] == "HotshotXL"
        assert "adaptation_plan" in d
        assert d["adaptation_plan"]["selected_slice"]["node_ids"] == ["5", "6", "7"]

    # ── Round-trip: fields survive construction + to_dict ────────────────

    def test_empty_precedent_slices_not_in_output(self) -> None:
        """Empty precedent_slices tuple is omitted from serialization."""
        rr = ResearchResult(
            summary="test",
            precedent_slices=(),
        )
        d = rr.to_dict()
        assert "precedent_slices" not in d

    def test_none_adaptation_plan_not_in_output(self) -> None:
        """None adaptation_plan is omitted from serialization."""
        rr = ResearchResult(
            summary="test",
            adaptation_plan=None,
        )
        d = rr.to_dict()
        assert "adaptation_plan" not in d

    def test_precedent_slices_preserved_as_tuples(self) -> None:
        """precedent_slices are stored as tuples internally."""
        ws1 = WorkflowSlice(source_class_type="NodeA", node_ids=("1",))
        ws2 = WorkflowSlice(source_class_type="NodeB", node_ids=("2",))
        rr = ResearchResult(
            summary="test",
            precedent_slices=(ws1, ws2),
        )
        assert isinstance(rr.precedent_slices, tuple)
        assert len(rr.precedent_slices) == 2

    def test_research_result_is_immutable(self) -> None:
        """ResearchResult is a frozen dataclass."""
        rr = ResearchResult(summary="test")
        with pytest.raises(Exception):
            rr.summary = "modified"  # type: ignore[misc]
