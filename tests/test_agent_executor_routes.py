from __future__ import annotations

import importlib
import sys
import types

import pytest

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    _derive_route,
    _derive_task,
)
from vibecomfy.executor.core import (
    _canonical_route_for_plan,
    _context_text_mentions_ltx_audio,
    _delegated_clarification_plan,
    _route_behavior,
)


def test_agent_executor_http_route_uses_shared_serializer_and_durable_helper(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    executor_response = importlib.import_module("vibecomfy.comfy_nodes.agent.executor_response")
    executor_durable = importlib.import_module("vibecomfy.comfy_nodes.agent.executor_durable")

    assert routes._serialize_executor_result is executor_response.serialize_executor_result
    assert routes.maybe_write_executor_only_durable_turn is (
        executor_durable.maybe_write_executor_only_durable_turn
    )

    registered = {}

    class _Routes:
        def post(self, path):
            def _decorator(fn):
                registered[("POST", path)] = fn
                return fn
            return _decorator

        def get(self, path):
            def _decorator(fn):
                registered[("GET", path)] = fn
                return fn
            return _decorator

    real_aiohttp = sys.modules.get("aiohttp")
    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
    )
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    class _Result:
        ok = True

        def to_dict(self):
            return {
                "ok": True,
                "route": "inspect",
                "reply": "This graph loads an image.",
                "candidate": {"graph": {"nodes": [{"id": 1}], "links": []}},
                "candidate_graph": {"nodes": [{"id": 1}], "links": []},
                "graph": {"nodes": [{"id": 1}], "links": []},
                "apply_eligible": True,
                "apply_eligibility": {"applyable": True, "reason": "applyable"},
                "eligibility": {"applyable": True, "reason": "applyable"},
            }

    captured: dict[str, object] = {}

    def _fake_run_executor(request, *, client_id=None):
        captured["executor_request"] = request
        captured["client_id"] = client_id
        return _Result()

    def _fake_durable_helper(**kwargs):
        captured["durable_kwargs"] = kwargs
        response = dict(kwargs["response"])
        response["session_id"] = "http-parity-session"
        response["turn_id"] = "http-parity-turn"
        response["detail_json_path"] = str(tmp_path / "response.json")
        response["artifacts"] = {"response": "response.json", "chat": "chat.json"}
        return response

    async def _fake_to_thread(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    executor_core = importlib.import_module("vibecomfy.executor.core")
    monkeypatch.setattr(executor_core, "run_executor", _fake_run_executor)
    monkeypatch.setattr(routes, "maybe_write_executor_only_durable_turn", _fake_durable_helper)
    monkeypatch.setattr(routes.asyncio, "to_thread", _fake_to_thread)

    class _Request:
        query = {}

        async def json(self):
            return {
                "query": "explain this",
                "graph": {"nodes": [], "links": []},
                "session_id": "../unsafe session",
                "client_id": "client-http",
            }

    try:
        routes.register_agent_edit_routes(types.SimpleNamespace(routes=_Routes()))
        response = routes.asyncio.run(
            registered[("POST", "/vibecomfy/agent-executor")](_Request())
        )
    finally:
        if real_aiohttp is not None:
            sys.modules["aiohttp"] = real_aiohttp
        else:
            sys.modules.pop("aiohttp", None)

    assert response["status"] == 200
    body = response["body"]
    assert body["route"] == "inspect"
    assert body["message"] == "This graph loads an image."
    assert body["session_id"] == "http-parity-session"
    assert body["turn_id"] == "http-parity-turn"
    assert body["artifacts"] == {"response": "response.json", "chat": "chat.json"}
    for forbidden_key in (
        "candidate",
        "candidate_graph",
        "graph",
        "apply_eligible",
        "apply_eligibility",
        "eligibility",
    ):
        assert forbidden_key not in body

    durable_kwargs = captured["durable_kwargs"]
    assert durable_kwargs["response"]["route"] == "inspect"
    assert "candidate" not in durable_kwargs["response"]
    assert durable_kwargs["payload"]["session_id"] == durable_kwargs["request"].session_id
    assert durable_kwargs["payload"]["session_id"] != "../unsafe session"
    assert captured["client_id"] == "client-http"


def test_agent_executor_and_agent_edit_submit_share_executor_adapter(monkeypatch) -> None:
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")

    registered = {}

    class _Routes:
        def post(self, path):
            def _decorator(fn):
                registered[("POST", path)] = fn
                return fn
            return _decorator

        def get(self, path):
            def _decorator(fn):
                registered[("GET", path)] = fn
                return fn
            return _decorator

    real_aiohttp = sys.modules.get("aiohttp")
    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
    )
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    captured = []
    to_thread_calls = []

    def _fake_run_executor(request, *, client_id=None):
        captured.append((request, client_id))
        graph = {"nodes": [{"id": 1, "type": "PreviewImage"}], "links": []}
        durable_response = {
            "session_id": request.session_id or "sess-durable",
            "turn_id": "turn-durable-1",
            "baseline_graph_hash": "baseline-hash",
            "submit_structural_graph_hash": "submit-structural-hash",
            "candidate_graph_hash": "candidate-hash",
            "candidate_structural_graph_hash": "candidate-structural-hash",
            "audit_ref": {"path": "sessions/sess-durable/turns/turn-durable-1"},
            "artifacts": {
                "request": "request.json",
                "response": "response.json",
                "chat": "chat.json",
            },
            "apply_eligibility": {
                "applyable": True,
                "reason": "candidate_graph_available",
                "message": "Candidate graph is ready to apply.",
            },
            "graph": graph,
            "outcome": {"kind": "candidate"},
            "change_details": {"summary": "Changed the graph."},
        }
        return ExecutorResult.success(
            report=Report(
                plan=ClassifyDecision(route="revise", task="edit_graph"),
                implementation=ImplementationResult(
                    graph=graph,
                    message="Changed the graph.",
                    durable_response=durable_response,
                ),
            ),
            graph=graph,
            reply="Changed the graph.",
        )

    async def _fake_to_thread(fn, /, *args, **kwargs):
        to_thread_calls.append(getattr(fn, "__name__", repr(fn)))
        return fn(*args, **kwargs)

    executor_core = importlib.import_module("vibecomfy.executor.core")
    monkeypatch.setattr(executor_core, "run_executor", _fake_run_executor)
    monkeypatch.setattr(routes.asyncio, "to_thread", _fake_to_thread)

    class _Request:
        def __init__(self, payload):
            self._payload = payload
            self.query = {}

        async def json(self):
            return self._payload

    try:
        routes.register_agent_edit_routes(types.SimpleNamespace(routes=_Routes()))

        assert ("POST", "/vibecomfy/agent-executor") in registered
        assert ("POST", "/vibecomfy/agent-edit") in registered
        assert ("POST", "/vibecomfy/agent-edit/accept") in registered

        executor_response = routes.asyncio.run(registered[("POST", "/vibecomfy/agent-executor")](
            _Request({"query": "add preview", "graph": {}, "session_id": "sess", "client_id": "client-a"})
        ))
        assert executor_response["status"] == 200
        assert captured[-1][0].query == "add preview"
        assert captured[-1][0].graph == {}
        assert captured[-1][0].session_id == "sess"
        assert captured[-1][1] == "client-a"
        assert to_thread_calls[-1] == "_handle_agent_executor_submit"
        assert executor_response["body"]["route"] == "revise"
        assert executor_response["body"]["apply_eligible"] is True
        assert executor_response["body"]["outcome"]["kind"] == "candidate"

        legacy_response = routes.asyncio.run(registered[("POST", "/vibecomfy/agent-edit")](
            _Request({"task": "legacy submit", "graph": {}, "client_id": "client-b"})
        ))
        assert legacy_response["status"] == 200
        assert captured[-1][0].query == "legacy submit"
        assert captured[-1][1] == "client-b"
        assert to_thread_calls[-1] == "_handle_agent_executor_submit"

        body = legacy_response["body"]
        assert body["route"] == "revise"
        assert body["reply"] == "Changed the graph."
        assert body["message"] == "Changed the graph."
        assert body["candidate"]["graph"] == body["graph"]
        assert body["candidate_graph"] == body["graph"]
        assert body["apply_eligible"] is True
        assert body["apply_eligibility"]["applyable"] is True
        assert body["outcome"]["kind"] == "candidate"
        # ── Durability: verify executor response preserves durable handle_agent_edit envelope ──
        # The executor route must forward the full durable edit envelope for revise/adapt routes,
        # including session_id, turn_id, baseline/candidate hashes, audit/artifact refs,
        # apply_eligibility, graph, outcome, and change_details, while keeping executor
        # metadata nested under report.executor.

        durability_response = routes.asyncio.run(registered[("POST", "/vibecomfy/agent-executor")](
            _Request({
                "query": "add preview",
                "graph": {"nodes": [{"id": 1, "type": "PreviewImage"}], "links": []},
                "session_id": "sess-durable",
                "client_id": "client-c",
            })
        ))
        assert durability_response["status"] == 200
        body = durability_response["body"]

        # Durable session/turn identity must be present.
        assert body.get("session_id") == "sess-durable", (
            "Executor response missing durable session_id; session_id=%r" % body.get("session_id")
        )
        assert isinstance(body.get("turn_id"), str) and body["turn_id"], (
            "Executor response missing durable turn_id"
        )

        # Baseline and candidate hashes must be present.
        assert isinstance(body.get("baseline_graph_hash"), str), (
            "Executor response missing baseline_graph_hash"
        )
        assert isinstance(body.get("submit_structural_graph_hash"), str), (
            "Executor response missing submit_structural_graph_hash"
        )
        assert isinstance(body.get("candidate_graph_hash"), str), (
            "Executor response missing candidate_graph_hash"
        )
        assert isinstance(body.get("candidate_structural_graph_hash"), str), (
            "Executor response missing candidate_structural_graph_hash"
        )

        # Audit/artifact refs must be present.
        assert isinstance(body.get("audit_ref"), dict), (
            "Executor response missing durable audit_ref"
        )
        assert isinstance(body.get("artifacts"), dict), (
            "Executor response missing durable artifacts"
        )

        # apply_eligibility must be present and well-formed.
        eligibility = body.get("apply_eligibility")
        assert isinstance(eligibility, dict), (
            "Executor response missing apply_eligibility"
        )
        assert eligibility.get("applyable") is True, (
            "Executor response apply_eligibility.applyable should be True for revise"
        )
        assert isinstance(eligibility.get("reason"), str), (
            "Executor response apply_eligibility.reason missing"
        )
        assert isinstance(eligibility.get("message"), str), (
            "Executor response apply_eligibility.message missing"
        )

        # graph must be present (candidate graph).
        assert isinstance(body.get("graph"), dict), (
            "Executor response missing durable graph"
        )

        # outcome must be present and well-formed.
        outcome = body.get("outcome")
        assert isinstance(outcome, dict), (
            "Executor response missing outcome"
        )
        assert outcome.get("kind") in ("candidate", "edit"), (
            "Executor response outcome.kind should be candidate/edit for revise, got %r"
            % outcome.get("kind")
        )

        # change_details must be present.
        assert isinstance(body.get("change_details"), dict), (
            "Executor response missing durable change_details"
        )

        # Executor metadata must be nested under report.executor (not flattened).
        report = body.get("report")
        assert isinstance(report, dict), "Executor response missing report"
        executor_meta = report.get("executor")
        assert isinstance(executor_meta, dict), (
            "Executor response report must contain executor metadata, got report keys=%r"
            % list(report.keys()) if isinstance(report, dict) else None
        )
        plan = executor_meta.get("plan")
        assert isinstance(plan, dict), "report.executor.plan missing"
        assert plan.get("route") == "revise", (
            "report.executor.plan.route should be revise, got %r" % plan.get("route")
        )

    finally:
        if real_aiohttp is not None:
            sys.modules["aiohttp"] = real_aiohttp
        else:
            sys.modules.pop("aiohttp", None)


# ── T15: representative route scenario regressions ───────────────────────────
# Each scenario verifies that the contract-level route derivation produces the
# correct canonical route for a given combination of legacy booleans / intent /
# explicit route.  Delegated clarification is tested through the core helper.


class TestRepresentativeRouteScenarios:
    """Contract-level route derivation for the six-route vocabulary."""

    # ── workflow explanation → inspect ───────────────────────────────────

    def test_workflow_explanation_routes_to_inspect(self) -> None:
        """'What is this workflow doing?' → inspect (explain_graph, no edit)."""
        decision = ClassifyDecision(
            research=False,
            implement=False,
            intent="explain_graph",
            plan_summary="Explain the current workflow structure.",
        )
        assert decision.effective_route == "inspect"
        assert decision.effective_task == "inspect_graph"
        behavior = _route_behavior(decision)
        assert behavior.needs_research is False
        assert behavior.needs_implement is False
        assert behavior.can_produce_candidate is False

    def test_workflow_explanation_explicit_route(self) -> None:
        """Explicit inspect route is preserved."""
        decision = ClassifyDecision(route="inspect", plan_summary="Look at graph.")
        assert decision.effective_route == "inspect"

    # ── LTX/PIL lookup → research ────────────────────────────────────────

    def test_ltx_pil_lookup_routes_to_research(self) -> None:
        """'How does LTX Video handle frame blending?' → research (research=True,
        implement=False)."""
        decision = ClassifyDecision(
            research=True,
            implement=False,
            intent="research",
            research_goal="Understand LTX Video frame blending",
        )
        assert decision.effective_route == "research"
        assert decision.effective_task == "research_nodes"
        behavior = _route_behavior(decision)
        assert behavior.needs_research is True
        assert behavior.needs_implement is True
        assert behavior.can_produce_candidate is False

    def test_pil_lookup_routes_to_research(self) -> None:
        """'Find PIL.Image composite modes' → research (research=True,
        implement=False)."""
        decision = ClassifyDecision(
            research=True,
            implement=False,
            intent="research",
            research_goal="Find PIL.Image composite modes",
        )
        assert decision.effective_route == "research"

    def test_research_explicit_route(self) -> None:
        """Explicit research route is preserved."""
        decision = ClassifyDecision(route="research", plan_summary="Research nodes.")
        assert decision.effective_route == "research"

    # ── PIL code-node addition → revise (unless research explicit) ────────

    def test_pil_code_node_addition_routes_to_revise(self) -> None:
        """'Add a PIL code node that composites images' → revise (implement=True,
        research=False)."""
        decision = ClassifyDecision(
            research=False,
            implement=True,
            intent="edit",
            change_goal="Add a PIL Image.composite code node",
        )
        assert decision.effective_route == "revise"
        assert decision.effective_task == "edit_graph"
        behavior = _route_behavior(decision)
        assert behavior.needs_research is False
        assert behavior.needs_implement is True
        assert behavior.can_produce_candidate is True

    def test_pil_with_explicit_research_routes_to_adapt(self) -> None:
        """PIL code-node addition with explicit research=True routes to adapt,
        not revise."""
        decision = ClassifyDecision(
            research=True,
            implement=True,
            intent="edit",
            change_goal="Add PIL composite node after researching techniques",
        )
        assert decision.effective_route == "adapt"
        assert decision.effective_task == "research_precedent"
        behavior = _route_behavior(decision)
        assert behavior.needs_research is True
        assert behavior.needs_implement is True

    def test_pil_with_explicit_adapt_route(self) -> None:
        """Explicit adapt route for PIL addition + research."""
        decision = ClassifyDecision(
            route="adapt",
            plan_summary="Research PIL blending then edit graph.",
        )
        assert decision.effective_route == "adapt"

    # ── research-then-edit → adapt ───────────────────────────────────────

    def test_research_then_edit_routes_to_adapt(self) -> None:
        """'Find example workflows for SDXL and add similar nodes to my graph'
        → adapt (research=True, implement=True)."""
        decision = ClassifyDecision(
            research=True,
            implement=True,
            intent="edit",
            research_goal="Find SDXL workflow examples",
            change_goal="Add similar nodes to current graph",
        )
        assert decision.effective_route == "adapt"
        assert decision.effective_task == "research_precedent"
        behavior = _route_behavior(decision)
        assert behavior.needs_research is True
        assert behavior.needs_implement is True
        assert behavior.can_produce_candidate is True

    def test_install_intent_route_for_edit_normalizes_to_adapt(self) -> None:
        """Stale classifier output must not short-circuit an edit into a noop."""
        decision = ClassifyDecision(
            research=False,
            implement=False,
            intent="edit",
            route="requires_custom_nodes",
            task="edit_graph",
            plan_summary="Identify missing Hotshot custom nodes.",
        )

        assert decision.effective_route == "adapt"
        assert decision.research is True
        assert decision.implement is True
        behavior = _route_behavior(decision)
        assert behavior.needs_research is True
        assert behavior.needs_implement is True
        assert behavior.can_produce_candidate is True

    def test_install_intent_route_for_research_normalizes_to_research(self) -> None:
        """Custom-node lookup without an edit remains a research answer."""
        decision = ClassifyDecision(
            research=True,
            implement=False,
            intent="research",
            route="requires_custom_nodes",
            task="research_nodes",
        )

        assert decision.effective_route == "research"
        assert decision.research is True
        assert decision.implement is False

    def test_adapt_legacy_booleans_derive_correctly(self) -> None:
        """_derive_route with research=True, implement=True returns 'adapt'."""
        assert _derive_route(research=True, implement=True, intent="edit") == "adapt"

    # ── empty-graph SD1.5 generation → revise ────────────────────────────

    def test_empty_graph_sd15_generation_routes_to_revise(self) -> None:
        """'Generate an SD1.5 txt2img workflow' on empty graph → revise
        (implement=True, research=False)."""
        decision = ClassifyDecision(
            research=False,
            implement=True,
            intent="edit",
            change_goal="Build an SD1.5 txt2img workflow from scratch",
        )
        assert decision.effective_route == "revise"
        assert decision.effective_task == "edit_graph"
        behavior = _route_behavior(decision)
        assert behavior.needs_research is False
        assert behavior.needs_implement is True
        assert behavior.can_produce_candidate is True

    def test_empty_graph_explicit_revise_route(self) -> None:
        """Explicit revise route for empty graph generation."""
        decision = ClassifyDecision(route="revise", plan_summary="Build SD1.5 workflow.")
        assert decision.effective_route == "revise"

    # ── delegated clarification ──────────────────────────────────────────

    def test_delegated_clarification_detects_triggers(self) -> None:
        """'Pick some please' with prior clarification context triggers delegation."""
        request = ExecutorRequest(query="Pick some please")
        # Session context: prior_clarification must be a dict (checked by callee);
        # blocked_route/prior_route are read from the top-level session_context.
        session_context = {
            "prior_clarification": {"question_asked": "Which model family?"},
            "blocked_route": "revise",
        }
        delegated = _delegated_clarification_plan(request, session_context)
        assert delegated is not None
        assert delegated.effective_route == "revise"
        # Delegated plan must NOT be clarify (loop prevention).
        assert delegated.effective_route != "clarify"

    def test_delegated_clarification_you_figure_it_out(self) -> None:
        """'You figure it out' triggers delegation to the previously blocked route."""
        request = ExecutorRequest(query="You figure it out")
        session_context = {
            "prior_clarification": {"question_asked": "What edit?"},
            "blocked_route": "adapt",
        }
        delegated = _delegated_clarification_plan(request, session_context)
        assert delegated is not None
        assert delegated.effective_route == "adapt"

    def test_delegated_clarification_prior_route_fallback(self) -> None:
        """prior_route is used when blocked_route is absent."""
        request = ExecutorRequest(query="choose for me")
        session_context = {
            "prior_clarification": {"question_asked": "Which approach?"},
            "prior_route": "adapt",
        }
        delegated = _delegated_clarification_plan(request, session_context)
        assert delegated is not None
        assert delegated.effective_route == "adapt"

    def test_delegated_clarification_without_context_returns_none(self) -> None:
        """'Pick some please' without prior clarification context — delegation
        should not fire (no blocked route to resume)."""
        request = ExecutorRequest(query="Pick some please")
        session_context = {}
        delegated = _delegated_clarification_plan(request, session_context)
        assert delegated is None

    def test_delegated_clarification_without_prior_clarification_returns_none(self) -> None:
        """Delegation requires prior_clarification to be present in session_context."""
        request = ExecutorRequest(query="pick some please")
        session_context = {"blocked_route": "revise"}
        delegated = _delegated_clarification_plan(request, session_context)
        assert delegated is None

    def test_delegated_clarification_non_matching_query_returns_none(self) -> None:
        """Non-delegation query should return None."""
        request = ExecutorRequest(query="Use the Flux model please")
        session_context = {
            "prior_clarification": {},
            "blocked_route": "revise",
        }
        delegated = _delegated_clarification_plan(request, session_context)
        assert delegated is None

    # ── logs-in-prompt diagnosis → respond or inspect ─────────────────────

    def test_log_diagnosis_routes_to_respond(self) -> None:
        """'Can you explain the previous failure?' → respond (no research,
        no implement, intent=respond)."""
        decision = ClassifyDecision(
            research=False,
            implement=False,
            intent="respond",
            plan_summary="Diagnose the previous failure from logs.",
        )
        assert decision.effective_route == "respond"
        assert decision.effective_task == "respond"
        behavior = _route_behavior(decision)
        assert behavior.needs_research is False
        assert behavior.needs_implement is False
        assert behavior.can_produce_candidate is False

    def test_log_diagnosis_routes_to_inspect_when_graph_present(self) -> None:
        """Log diagnosis with explain_graph intent routes to inspect
        (no research, no implement, intent=explain_graph)."""
        decision = ClassifyDecision(
            research=False,
            implement=False,
            intent="explain_graph",
            plan_summary="Inspect graph to explain why the previous turn failed.",
        )
        assert decision.effective_route == "inspect"
        assert decision.effective_task == "inspect_graph"

    def test_log_diagnosis_never_routes_to_research(self) -> None:
        """Log diagnosis without explicit research=True must NOT route to research.
        It stays respond or inspect based on intent."""
        for intent in ("respond", "explain_graph"):
            decision = ClassifyDecision(
                research=False,
                implement=False,
                intent=intent,
                plan_summary="Diagnose failure from logs.",
            )
            assert decision.effective_route != "research", (
                f"Log diagnosis with intent={intent} routed to research "
                f"(expected respond or inspect)"
            )
            assert decision.effective_route in ("respond", "inspect")

    # ── explicit route vocabulary covers all six routes ──────────────────

    @pytest.mark.parametrize("route,expected_research,expected_implement", [
        ("clarify", False, False),
        ("respond", False, False),
        ("inspect", False, False),
        ("research", True, False),
        ("revise", False, True),
        ("adapt", True, True),
        ("reorganise", False, True),
    ])
    def test_all_canonical_routes_have_correct_boolean_canonicalization(
        self, route, expected_research, expected_implement,
    ) -> None:
        """Every explicit canonical route must canonicalize booleans correctly."""
        decision = ClassifyDecision(route=route)
        assert decision.effective_route == route
        assert decision.research == expected_research
        assert decision.implement == expected_implement

    @pytest.mark.parametrize("route", ["clarify", "respond", "inspect", "research", "revise", "adapt", "reorganise"])
    def test_canonical_routes_produce_applyable_for_candidate_routes(self, route) -> None:
        """Only candidate-producing routes are apply-eligible."""
        decision = ClassifyDecision(route=route)
        behavior = _route_behavior(decision)
        if route in ("revise", "adapt", "reorganise"):
            assert behavior.can_produce_candidate is True
        else:
            assert behavior.can_produce_candidate is False

    # ── legacy route aliases ─────────────────────────────────────────────

    def test_legacy_direct_edit_canonicalizes_to_revise(self) -> None:
        """Legacy 'direct_edit' → revise with correct booleans."""
        decision = ClassifyDecision(route="direct_edit")
        assert decision.effective_route == "revise"
        assert decision.research is False
        assert decision.implement is True

    def test_legacy_precedent_research_canonicalizes_to_adapt(self) -> None:
        """Legacy 'precedent_research' → adapt."""
        decision = ClassifyDecision(route="precedent_research")
        assert decision.effective_route == "adapt"
        assert decision.research is True
        assert decision.implement is True

    def test_legacy_asset_lookup_with_research_true_routes_to_research(self) -> None:
        """asset_lookup + research=True, implement=False → research."""
        decision = ClassifyDecision(
            route="asset_lookup", research=True, implement=False,
        )
        assert decision.effective_route == "research"

    def test_legacy_inspect_only_canonicalizes_to_inspect(self) -> None:
        """Legacy 'inspect_only' → inspect."""
        decision = ClassifyDecision(route="inspect_only")
        assert decision.effective_route == "inspect"
        assert decision.research is False
        assert decision.implement is False

    # ── _derive_route truth table ────────────────────────────────────────

    def test_derive_route_truth_table(self) -> None:
        """Full truth table for _derive_route."""
        # research + implement → adapt
        assert _derive_route(research=True, implement=True, intent="edit") == "adapt"
        # implement only → revise
        assert _derive_route(research=False, implement=True, intent="edit") == "revise"
        # research only → research
        assert _derive_route(research=True, implement=False, intent="research") == "research"
        # neither, explain_graph → inspect
        assert _derive_route(research=False, implement=False, intent="explain_graph") == "inspect"
        # neither, respond → respond
        assert _derive_route(research=False, implement=False, intent="respond") == "respond"
        # neither, edit → clarify (ambiguous — edit without research or implement)
        assert _derive_route(research=False, implement=False, intent="edit") == "clarify"

    # ── _derive_task truth table ─────────────────────────────────────────

    def test_derive_task_truth_table(self) -> None:
        """Full truth table for _derive_task."""
        assert _derive_task(research=True, implement=True, intent="edit") == "research_precedent"
        assert _derive_task(research=False, implement=True, intent="edit") == "edit_graph"
        assert _derive_task(research=True, implement=False, intent="research") == "research_nodes"
        assert _derive_task(research=False, implement=False, intent="explain_graph") == "inspect_graph"
        assert _derive_task(research=False, implement=False, intent="respond") == "respond"


# ── LTX/audio route behavior (T5 neutralization proofs) ───────────────────────


class TestLTXAudioRouteBehavior:
    """Tests proving LTX/audio is either classifier-covered as research-capable
    adapt or constrained to process-only fallback with no concrete node suggestions."""

    # ── _context_text_mentions_ltx_audio detection ──────────────────────────

    def test_detects_ltx_with_audio_in_recent_messages(self) -> None:
        """LTX + 'audio' in recent_messages triggers detection."""
        ctx = {
            "recent_messages": [
                {"text": "Can you add audio to my LTX video pipeline?"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    def test_detects_ltx_with_voice_in_recent_messages(self) -> None:
        """LTX + 'voice' in recent_messages triggers detection."""
        ctx = {
            "recent_messages": [
                {"text": "I need voice output from LTX"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    def test_detects_ltx_with_lipsync_in_recent_messages(self) -> None:
        """LTX + 'lipsync' in recent_messages triggers detection."""
        ctx = {
            "recent_messages": [
                {"text": "LTX lipsync for the generated video"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    def test_detects_ltx_with_lip_sync_in_recent_messages(self) -> None:
        """LTX + 'lip sync' (two words) in recent_messages triggers detection."""
        ctx = {
            "recent_messages": [
                {"text": "LTX lip sync generation"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    def test_detects_ltx_with_runexx_in_recent_messages(self) -> None:
        """LTX + 'runexx' in recent_messages triggers detection."""
        ctx = {
            "recent_messages": [
                {"text": "Using LTX with RuneXX audio"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    def test_no_detection_without_audio_terms(self) -> None:
        """LTX alone without audio-related terms does NOT trigger."""
        ctx = {
            "recent_messages": [
                {"text": "Generate video with LTX model"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is False

    def test_no_detection_with_audio_without_ltx(self) -> None:
        """Audio terms without LTX do NOT trigger."""
        ctx = {
            "recent_messages": [
                {"text": "Add audio output to the video"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is False

    def test_detects_from_prior_clarification_question(self) -> None:
        """LTX+audio in prior_clarification.clarification_question triggers detection."""
        ctx = {
            "prior_clarification": {
                "clarification_question": "Should I use LTX audio VAE?",
            },
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    def test_detects_from_prior_clarification_options(self) -> None:
        """LTX+audio in prior_clarification.clarification_options triggers detection."""
        ctx = {
            "prior_clarification": {
                "clarification_options": ["Use LTXVAudioVAELoader", "Skip audio"],
            },
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    def test_empty_context_returns_false(self) -> None:
        """Empty session context returns False."""
        assert _context_text_mentions_ltx_audio({}) is False

    def test_context_without_relevant_keys_returns_false(self) -> None:
        """Context with no text-bearing keys returns False."""
        ctx = {
            "some_other_key": {"value": "LTX audio"},
        }
        assert _context_text_mentions_ltx_audio(ctx) is False

    def test_case_insensitive_detection(self) -> None:
        """Detection is case-insensitive."""
        ctx = {
            "recent_messages": [
                {"text": "ltx AUDIO pipeline"},
            ],
        }
        assert _context_text_mentions_ltx_audio(ctx) is True

    # ── _delegated_clarification_plan: LTX/audio does NOT force adapt ──────

    def test_ltx_audio_does_not_force_adapt_route(self) -> None:
        """LTX+audio context with blocked_route='revise' must NOT force adapt.

        T5 neutralized the LTX/audio→adapt route override. The delegated
        clarification plan must respect the prior_route and NOT elevate to
        research-backed adapt just because LTX+audio terms appear.
        """
        from vibecomfy.executor.contracts import ExecutorRequest

        request = ExecutorRequest(query="you figure it out")
        session_context = {
            "prior_clarification": {"clarification_question": "Which LTX audio loader?"},
            "blocked_route": "revise",
            "recent_messages": [
                {"text": "I want LTX audio output"},
            ],
        }
        plan = _delegated_clarification_plan(request, session_context)
        assert plan is not None
        # Must NOT be adapt (no research-backed precedent lookups).
        assert plan.effective_route == "revise"
        assert plan.research is False
        assert plan.implement is True

    def test_ltx_audio_respects_explicit_adapt_prior_route(self) -> None:
        """LTX+audio with blocked_route='adapt' remains adapt.

        When the prior route was already adapt (classifier-set), the LTX/audio
        context should not downgrade it — it was already research-capable.
        """
        from vibecomfy.executor.contracts import ExecutorRequest

        request = ExecutorRequest(query="decide for me")
        session_context = {
            "prior_clarification": {"clarification_question": "Which LTX audio approach?"},
            "blocked_route": "adapt",
            "recent_messages": [
                {"text": "LTX video with audio"},
            ],
        }
        plan = _delegated_clarification_plan(request, session_context)
        assert plan is not None
        assert plan.effective_route == "adapt"
        assert plan.research is True
        assert plan.implement is True

    def test_ltx_audio_with_prior_route_fallback_to_revise(self) -> None:
        """LTX+audio with prior_route='revise' (not blocked_route) stays revise."""
        from vibecomfy.executor.contracts import ExecutorRequest

        request = ExecutorRequest(query="choose for me")
        session_context = {
            "prior_clarification": {"clarification_question": "LTX audio VAE?"},
            "prior_route": "revise",
            "recent_messages": [
                {"text": "LTX audio lipsync"},
            ],
        }
        plan = _delegated_clarification_plan(request, session_context)
        assert plan is not None
        assert plan.effective_route == "revise"
        assert plan.research is False

    def test_ltx_audio_no_graph_fallback_does_not_become_adapt(self) -> None:
        """LTX+audio with no graph and fallback → inspect, never adapt."""
        from vibecomfy.executor.contracts import ExecutorRequest

        request = ExecutorRequest(query="use your judgment", graph=None)
        session_context = {
            "prior_clarification": {"clarification_question": "LTX audio?"},
            "prior_route": "clarify",  # not in {revise, adapt}
            "recent_messages": [
                {"text": "LTX audio"},
            ],
        }
        plan = _delegated_clarification_plan(request, session_context)
        assert plan is not None
        # Falls back to inspect when no graph and prior_route not edit-capable.
        assert plan.effective_route in ("inspect", "revise")
        # Must NOT become adapt.
        assert plan.effective_route != "adapt"
        assert plan.effective_route != "research"

    def test_ltx_audio_delegated_plan_is_not_clarify_loop(self) -> None:
        """LTX+audio delegation must never produce a clarify loop."""
        from vibecomfy.executor.contracts import ExecutorRequest

        request = ExecutorRequest(query="decide")
        session_context = {
            "prior_clarification": {"clarification_question": "LTX audio VAE selection?"},
            "blocked_route": "revise",
            "recent_messages": [
                {"text": "LTX voice generation"},
            ],
        }
        plan = _delegated_clarification_plan(request, session_context)
        assert plan is not None
        assert plan.effective_route != "clarify", (
            "LTX/audio delegated clarification must not loop back to clarify"
        )

    def test_ltx_audio_delegated_plan_no_concrete_node_suggestions(self) -> None:
        """The plan_summary for LTX+audio delegation must not suggest concrete nodes."""
        from vibecomfy.executor.contracts import ExecutorRequest

        request = ExecutorRequest(query="you figure it out")
        session_context = {
            "prior_clarification": {"clarification_question": "LTX audio VAE?"},
            "blocked_route": "revise",
            "recent_messages": [
                {"text": "LTX audio pipeline"},
            ],
        }
        plan = _delegated_clarification_plan(request, session_context)
        assert plan is not None
        # plan_summary must be the generic delegation message, not LTX-specific.
        assert "conservative default" in plan.plan_summary.lower()
        assert "LTX" not in plan.plan_summary
        assert "audio" not in plan.plan_summary.lower()

    # ── _context_text_mentions_ltx_audio: detector remains available ────────

    def test_detector_function_exists_and_is_callable(self) -> None:
        """The _context_text_mentions_ltx_audio detector is importable and callable."""
        from vibecomfy.executor.core import _context_text_mentions_ltx_audio as detector
        assert callable(detector)
        # Should accept a dict without raising.
        result = detector({"recent_messages": [{"text": "Hello"}]})
        assert isinstance(result, bool)

    def test_detector_survives_malformed_context(self) -> None:
        """The detector does not raise on malformed/partial context dicts."""
        # Missing 'text' key in message dict
        assert _context_text_mentions_ltx_audio(
            {"recent_messages": [{"role": "user"}]}
        ) is False
        # recent_messages not a list
        assert _context_text_mentions_ltx_audio(
            {"recent_messages": "not a list"}
        ) is False
        # prior_clarification not a dict
        assert _context_text_mentions_ltx_audio(
            {"prior_clarification": "not a dict"}
        ) is False
