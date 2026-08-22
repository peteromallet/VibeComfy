"""Unit tests for executor contracts and prompt parsing.

Covers valid classify/reply JSON, malformed JSON, optional graph handling,
and the final executor result shape — without changing existing agent
contracts.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from tests._splice_antigaming import assert_no_forbidden_fields
from vibecomfy.executor.agent_research_stage import AgentResearchTrace
from vibecomfy.executor.core import AgentResearchResult
from vibecomfy.executor.evidence_pack import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
)
from vibecomfy.executor.contracts import (
    AgentEvidence,
    AgentTurnResult,
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    GraphFacts,
    ImplementationResult,
    ManifestBoundaryAnchor,
    ManifestInquiryCoverage,
    ManifestInternalEdge,
    ManifestNode,
    ManifestOversized,
    ManifestValidation,
    ModelAttemptEvidence,
    ReadinessReport,
    Report,
    TopologyFindings,
    TopologyManifest,
    _ALLOWED_ROUTES,
    _ALLOWED_TASKS,
    adaptation_plan_actionability,
    adaptation_plan_actionability_payload,
    build_topology_manifest,
    format_route_options_for_prompt,
    redact_model_preview,
    warning_detail_from_exception,
)
from vibecomfy.executor.prompts import (
    build_classify_messages,
    build_reply_messages,
    parse_classify_response,
    parse_reply_response,
)


def test_executor_core_import_does_not_eagerly_load_comfyui_host_modules() -> None:
    code = """
import sys
import vibecomfy.executor.core
for name in (
    "vibecomfy.comfy_nodes.agent.contracts",
    "vibecomfy.comfy_nodes.agent.edit",
    "vibecomfy.comfy_nodes.agent.provider",
    "vibecomfy.comfy_nodes.agent.runtime",
    "vibecomfy.comfy_nodes.agent.session",
):
    assert name not in sys.modules, name
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_direct_classify_backend_repairs_one_malformed_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import provider as agent_provider
    from vibecomfy.executor.agent_backend import run_classify_turn

    calls: list[list[dict[str, object]]] = []

    def fake_model_turn(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        messages = list(args[1])
        calls.append(messages)
        if len(calls) == 1:
            content = "api_key=sk-secret prose with {LoRA}"
        else:
            content = (
                '{"research": false, "implement": false, "reply": true, '
                '"effort": "low", "plan_summary": "Clarify", '
                '"intent": "respond", "route": "respond"}'
            )
        return {"content": content, "model_attempts": []}

    monkeypatch.setattr(agent_provider, "run_model_turn", fake_model_turn)

    decision = run_classify_turn("help", route="openrouter", model="model")

    assert decision.effective_route == "respond"
    assert len(calls) == 2
    retry = calls[1][-1]
    assert retry["role"] == "system"
    assert "classify contract" in str(retry["content"])
    assert "Previous response preview" in str(retry["content"])
    assert "<redacted>" in str(retry["content"])
    assert "sk-secret" not in str(retry["content"])


def test_direct_classify_backend_never_retries_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.comfy_nodes.agent import provider as agent_provider
    from vibecomfy.executor.agent_backend import run_classify_turn

    calls = 0

    def fake_model_turn(*args, **kwargs):  # noqa: ANN001, ANN202, ARG001
        nonlocal calls
        calls += 1
        raise agent_provider.AuthError("bad credentials")

    monkeypatch.setattr(agent_provider, "run_model_turn", fake_model_turn)

    with pytest.raises(agent_provider.AuthError):
        run_classify_turn("help", route="openrouter", model="model")
    assert calls == 1


def _agent_research_result(summary: str = "found") -> AgentResearchResult:
    """Build a minimal H01 agent-owned research result for report tests."""
    ledger = EvidenceLedger(entries=(
        EvidenceLedgerEntry(
            decision="agent_research",
            conclusion=summary,
            evidence_ids=(),
            uncertainty="low",
        ),
    ))
    trace = AgentResearchTrace(
        route="research",
        question="q",
        iterations=(),
        final_verdict="enough",
        summary=summary,
        citations=(),
        uncertainty="low",
        status="ok",
        elapsed_seconds=0.0,
    )
    return AgentResearchResult(
        route="research",
        trace=trace,
        evidence_pack=EvidencePack(artifacts={}, ledger=ledger),
    )


# ── ExecutorRequest ──────────────────────────────────────────────────────────


class TestExecutorRequest:
    def test_minimal_request(self) -> None:
        req = ExecutorRequest(query="hello")
        assert req.query == "hello"
        assert req.graph is None
        assert req.workflow_id is None
        assert req.session_id is None
        assert req.profile is None
        assert req.idempotency_key is None
        assert req.client_graph_hash is None
        assert req.client_structural_graph_hash is None
        assert req.client_live_canvas_token is None
        assert req.expected_baseline_graph_hash is None
        assert req.expected_baseline_graph_hash_present is False

    def test_full_request(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest(
            query="set seed to 42",
            graph=graph,
            workflow_id="6b4611de-b2b2-42f2-b358-5f566d6a8933",
            session_id="sess-1",
            profile="default",
            idempotency_key="idem-1",
            client_graph_hash="graph-hash",
            client_structural_graph_hash="structural-hash",
            client_live_canvas_token="live-token",
            expected_baseline_graph_hash="baseline-hash",
        )
        assert req.graph == graph
        assert req.workflow_id == "6b4611de-b2b2-42f2-b358-5f566d6a8933"
        assert req.session_id == "sess-1"
        assert req.profile == "default"
        assert req.idempotency_key == "idem-1"
        assert req.client_graph_hash == "graph-hash"
        assert req.client_structural_graph_hash == "structural-hash"
        assert req.client_live_canvas_token == "live-token"
        assert req.expected_baseline_graph_hash == "baseline-hash"
        assert req.expected_baseline_graph_hash_present is True

    def test_on_demand_schemas_threads_through_payload(self) -> None:
        """The frontend 'Author Uninstalled Node Packs' toggle rides on the request so the
        backend schema provider honors it (the provider defaults ON when the field is absent)."""
        req = ExecutorRequest.from_payload({"query": "x", "on_demand_schemas": True})
        assert req.on_demand_schemas is True
        assert req.to_dict()["on_demand_schemas"] is True
        # Absent -> None (provider applies its default); omitted from to_dict.
        absent = ExecutorRequest.from_payload({"query": "x"})
        assert absent.on_demand_schemas is None
        assert "on_demand_schemas" not in absent.to_dict()
        # Non-bool junk -> None, never raises.
        junk = ExecutorRequest.from_payload({"query": "x", "on_demand_schemas": "yes"})
        assert junk.on_demand_schemas is None

    def test_to_dict_minimal(self) -> None:
        req = ExecutorRequest(query="hello")
        d = req.to_dict()
        assert d == {"query": "hello"}

    def test_to_dict_full(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest(
            query="set seed",
            graph=graph,
            workflow_id="6b4611de-b2b2-42f2-b358-5f566d6a8933",
            session_id="sess-1",
            profile="default",
            idempotency_key="idem-1",
            client_graph_hash="graph-hash",
            client_structural_graph_hash="structural-hash",
            client_live_canvas_token="live-token",
            expected_baseline_graph_hash="baseline-hash",
        )
        d = req.to_dict()
        assert d["query"] == "set seed"
        assert d["graph"] == graph
        assert d["workflow_id"] == "6b4611de-b2b2-42f2-b358-5f566d6a8933"
        assert d["session_id"] == "sess-1"
        assert d["profile"] == "default"
        assert d["idempotency_key"] == "idem-1"
        assert d["client_graph_hash"] == "graph-hash"
        assert d["client_structural_graph_hash"] == "structural-hash"
        assert d["client_live_canvas_token"] == "live-token"
        assert d["expected_baseline_graph_hash"] == "baseline-hash"

    def test_from_payload_minimal(self) -> None:
        req = ExecutorRequest.from_payload({"query": "hello"})
        assert req.query == "hello"

    def test_from_payload_full(self) -> None:
        graph = {"nodes": []}
        req = ExecutorRequest.from_payload({
            "query": "edit graph",
            "graph": graph,
            "workflow_id": "6b4611de-b2b2-42f2-b358-5f566d6a8933",
            "session_id": "s1",
            "profile": "default",
            "idempotency_key": "ik1",
            "client_graph_hash": "graph-hash",
            "client_structural_graph_hash": "structural-hash",
            "client_live_canvas_token": "live-token",
            "expected_baseline_graph_hash": "baseline-hash",
        })
        assert req.graph == graph
        assert req.workflow_id == "6b4611de-b2b2-42f2-b358-5f566d6a8933"
        assert req.session_id == "s1"
        assert req.client_graph_hash == "graph-hash"
        assert req.client_structural_graph_hash == "structural-hash"
        assert req.client_live_canvas_token == "live-token"
        assert req.expected_baseline_graph_hash == "baseline-hash"
        assert req.expected_baseline_graph_hash_present is True

    def test_explicit_null_baseline_capability_survives_roundtrip(self) -> None:
        req = ExecutorRequest.from_payload({
            "query": "first edit",
            "expected_baseline_graph_hash": None,
        })

        assert req.expected_baseline_graph_hash is None
        assert req.expected_baseline_graph_hash_present is True
        assert req.to_dict()["expected_baseline_graph_hash"] is None

    def test_from_payload_derives_workflow_id_from_graph_for_stale_clients(self) -> None:
        workflow_id = "6b4611de-b2b2-42f2-b358-5f566d6a8933"

        req = ExecutorRequest.from_payload({
            "query": "build a workflow",
            "graph": {"id": workflow_id, "nodes": [], "links": []},
        })

        assert req.workflow_id == workflow_id

    def test_from_payload_rejects_mismatched_workflow_identity(self) -> None:
        with pytest.raises(ValueError, match="must match"):
            ExecutorRequest.from_payload({
                "query": "build a workflow",
                "workflow_id": "6b4611de-b2b2-42f2-b358-5f566d6a8933",
                "graph": {
                    "id": "f6137f22-d44c-45a6-a20f-5f078499f39a",
                    "nodes": [],
                    "links": [],
                },
            })

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
        # research=True, implement=False → research
        assert ClassifyDecision(research=True, implement=False).effective_route == "research"
        # respond-only → respond
        assert ClassifyDecision(research=False, implement=False).effective_route == "respond"
        # explain_graph with no research/edit → inspect
        assert ClassifyDecision(
            research=False,
            implement=False,
            intent="explain_graph",
        ).effective_route == "inspect"
        # research=True, implement=True → adapt
        assert ClassifyDecision(research=True, implement=True).effective_route == "adapt"

    def test_effective_route_explicit_wins(self) -> None:
        """Explicit route takes precedence over derived route."""
        d = ClassifyDecision(
            research=True,
            implement=True,  # legacy booleans derive adapt
            route="adapt",
        )
        assert d.effective_route == "adapt"

    def test_effective_task_property(self) -> None:
        """effective_task derives correctly from legacy booleans when task is empty."""
        # implement=True, research=False → edit_graph
        assert ClassifyDecision(research=False, implement=True).effective_task == "edit_graph"
        # research=True, implement=False → research_nodes
        assert ClassifyDecision(research=True, implement=False, intent="research").effective_task == "research_nodes"
        # respond-only → respond
        assert ClassifyDecision(research=False, implement=False).effective_task == "respond"
        # explain_graph with no research/edit → inspect_graph
        assert ClassifyDecision(
            research=False,
            implement=False,
            intent="explain_graph",
        ).effective_task == "inspect_graph"
        # research=True, implement=True → research_precedent
        assert ClassifyDecision(research=True, implement=True).effective_task == "research_precedent"

    def test_effective_task_explicit_wins(self) -> None:
        """Explicit task takes precedence over derived task."""
        d = ClassifyDecision(
            research=False,
            implement=True,  # legacy booleans derive edit_graph
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
        valid_routes = ["", "clarify", "inspect", "revise", "adapt", "reorganise"]
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
        for t in _ALLOWED_TASKS:
            d = ClassifyDecision(task=t)
            assert d.task == t, f"task={t!r} was clamped"

    @pytest.mark.parametrize(
        "route_alias",
        [
            "reorganise",
            "layout_reorganise",
            "reorganise_workflow",
            "reorganize_workflow",
            "reorganise_comfy_workflow",
            "/reorganise_comfy_workflow",
        ],
    )
    def test_explicit_reorganise_aliases_canonicalize_to_layout_task(
        self,
        route_alias: str,
    ) -> None:
        d = ClassifyDecision(
            research=True,
            implement=False,
            intent="edit",
            route=route_alias,
            task="edit_graph",
        )

        assert d.route == "reorganise"
        assert d.task == "layout_reorganise"
        assert d.effective_route == "reorganise"
        assert d.effective_task == "layout_reorganise"
        assert d.research is False
        assert d.implement is True

    def test_layout_reorganise_task_without_route_canonicalizes_to_reorganise(self) -> None:
        d = ClassifyDecision(
            research=False,
            implement=True,
            intent="edit",
            task="layout_reorganise",
        )

        assert d.route == "reorganise"
        assert d.task == "layout_reorganise"

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


class TestModelAttemptEvidence:
    def test_preserves_requested_and_resolved_model_and_unknown_non_hermes_fields(self) -> None:
        payload = ModelAttemptEvidence(
            phase="reply",
            attempt=2,
            outcome="success",
            requested_model="profile-alias",
            resolved_model="provider/model-v2",
            adapter="codex",
            provider=None,  # type: ignore[arg-type]
            transport=None,  # type: ignore[arg-type]
            endpoint=None,  # type: ignore[arg-type]
            finish_reason=None,  # type: ignore[arg-type]
            token_usage={},
            raw_response_preview="success content must be dropped",
        ).to_dict()

        assert payload["requested_model"] == "profile-alias"
        assert payload["resolved_model"] == "provider/model-v2"
        assert payload["provider"] == "unknown"
        assert payload["transport"] == "unknown"
        assert payload["endpoint"] == "unknown"
        assert payload["finish_reason"] == "unknown"
        assert payload["token_usage"] == {
            "prompt_tokens": "unknown",
            "completion_tokens": "unknown",
            "total_tokens": "unknown",
        }
        assert "raw_response_preview" not in payload

    @pytest.mark.parametrize("scheme", ["Basic", "Bearer", "ApiKey", "Custom"])
    def test_preview_redacts_entire_authorization_header(self, scheme: str) -> None:
        credential = "dXNlcjpwYXNz"
        preview = redact_model_preview(
            f"request failed\nAuthorization: {scheme} {credential}\nresponse invalid"
        )

        assert preview == "request failed Authorization: <redacted> response invalid"
        assert scheme not in preview
        assert credential not in preview

    @pytest.fixture
    def json_quoted_secret_preview(self) -> str:
        """Failure preview embedding the three oracle finding 5 JSON-quoted secrets."""
        return (
            '{"api_key":"sk-secret",'
            '"authorization":"Basic dXNlcjpwYXNz",'
            '"token":"tok-secret"}'
        )

    def test_preview_redacts_json_quoted_sensitive_fields(
        self, json_quoted_secret_preview: str
    ) -> None:
        preview = redact_model_preview(json_quoted_secret_preview)

        assert preview is not None
        assert "sk-secret" not in preview
        assert "Basic dXNlcjpwYXNz" not in preview
        assert "tok-secret" not in preview
        assert preview.count("<redacted>") == 3

    @pytest.mark.parametrize("quote", ['"', "'"])
    def test_preview_redacts_single_and_double_quoted_json_fields(
        self, quote: str
    ) -> None:
        preview = redact_model_preview(
            f"{quote}api_key{quote}:{quote}sk-secret{quote} "
            f"{quote}Authorization{quote}: {quote}Basic dXNlcjpwYXNz{quote} "
            f"{quote}refresh_token{quote}:{quote}tok-secret{quote}"
        )

        assert "sk-secret" not in preview
        assert "Basic dXNlcjpwYXNz" not in preview
        assert "tok-secret" not in preview
        assert preview.count("<redacted>") == 3

    def test_preview_json_redaction_never_crashes_on_malformed_json(self) -> None:
        preview = redact_model_preview('{broken "api_key": "sk-secret" trailing')

        assert preview is not None
        assert "sk-secret" not in preview
        assert "<redacted>" in preview

    def test_evidence_to_dict_redacts_json_quoted_sensitive_fields(
        self, json_quoted_secret_preview: str
    ) -> None:
        payload = ModelAttemptEvidence(
            phase="classify",
            outcome="failure",
            failure_type="malformed_json",
            raw_response_preview=json_quoted_secret_preview,
        ).to_dict()

        assert "sk-secret" not in payload["raw_response_preview"]
        assert "Basic dXNlcjpwYXNz" not in payload["raw_response_preview"]
        assert "tok-secret" not in payload["raw_response_preview"]
        assert payload["raw_response_preview"].count("<redacted>") == 3


class TestReport:
    def test_default(self) -> None:
        r = Report()
        assert r.plan is None
        assert r.research is None
        assert r.implementation is None

    def test_with_phases(self) -> None:
        plan = ClassifyDecision(research=True, implement=True)
        research = _agent_research_result(summary="found")
        impl = ImplementationResult(message="edited")
        r = Report(plan=plan, research=research, implementation=impl)
        assert r.plan == plan
        assert r.research is research
        assert r.implementation is impl

    def test_to_dict_carries_compact_agent_owned_references(self) -> None:
        plan = ClassifyDecision(plan_summary="p")
        research = _agent_research_result(summary="found")
        r = Report(plan=plan, research=research)
        d = r.to_dict()
        assert d["executor"]["plan"]["plan_summary"] == "p"
        # Public serialization carries the compact stage/evidence package —
        # mode + ledger references — never the full research blob.
        research_payload = d["executor"]["research"]
        assert research_payload["mode"] == "agent_owned"
        assert research_payload["status"] == "ok"
        ledger = research_payload["ledger"]
        assert ledger["entries"][0]["conclusion"] == "found"
        assert "implementation" not in d["executor"]

    def test_legacy_research_payload_is_rejected_not_rewritten(self) -> None:
        """Backward-incompatible legacy research payloads fail explicitly."""
        for legacy_payload in (
            {"summary": "found", "sources": []},
            {"summary": "found", "precedent_packet": {"options": []}},
            {"summary": "found", "adaptation_plan": {"selected_slice": {}}},
        ):
            with pytest.raises(TypeError, match="must be an AgentResearchResult"):
                Report(research=legacy_payload)  # type: ignore[arg-type]

    def test_model_response_compatibility_view_is_derived_not_serialized(self) -> None:
        attempt = ModelAttemptEvidence(
            phase="classify",
            outcome="failure",
            failure_type="malformed_json",
        ).to_dict()
        report = Report(model_attempts=(attempt,))

        assert report.model_response == {"attempts": [attempt]}
        payload = report.to_dict()["executor"]
        assert payload["model_attempts"] == [attempt]
        assert "model_response" not in payload


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

    def test_unknown_public_route_fails_closed_to_respond(self) -> None:
        result = AgentTurnResult(route="retired_route", reply="legacy")

        assert result.to_dict()["route"] == "respond"
        assert result.to_dict()["candidate"] is None
        assert result.to_dict()["apply_eligible"] is False

    @pytest.mark.parametrize(
        ("route", "candidate", "expected_apply_eligible", "expected_reason"),
        [
            ("clarify", None, False, "route_not_applyable"),
            ("inspect", None, False, "route_not_applyable"),
            ("revise", {"graph": {"nodes": [{"id": 1}]}}, True, None),
            ("adapt", {"graph": {"nodes": [{"id": 1}]}}, True, None),
            ("reorganise", {"graph": {"nodes": [{"id": 1}]}}, True, None),
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
        assert payload["route"] in {"clarify", "inspect", "revise", "adapt", "reorganise"}
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

    @pytest.mark.parametrize(
        ("legacy_route", "research", "implement", "expected_route"),
        [
            ("precedent_research", True, True, "adapt"),
            ("asset_lookup", True, True, "adapt"),
            ("asset_lookup", False, True, "revise"),
            ("asset_lookup", False, False, "clarify"),
            ("subgraph_preview", True, True, "adapt"),
            ("subgraph_preview", False, True, "revise"),
            ("subgraph_preview", False, False, "clarify"),
        ],
    )
    def test_report_plan_serialization_never_emits_legacy_route_alias(
        self,
        legacy_route: str,
        research: bool,
        implement: bool,
        expected_route: str,
    ) -> None:
        plan = ClassifyDecision(
            research=research,
            implement=implement,
            reply=True,
            intent="edit",
            route=legacy_route,
            task="research_precedent",
        )
        report = Report(plan=plan)

        d = ExecutorResult.success(report=report, reply="No changes.").to_dict()
        serialized = json.dumps(d)

        assert d["route"] == expected_route
        assert d["report"]["executor"]["plan"]["route"] == expected_route
        assert legacy_route not in serialized

    def test_to_dict_failure(self) -> None:
        r = ExecutorResult.failure(kind="TimeoutError", stage="classify", message="timed out")
        d = r.to_dict()
        assert d["ok"] is False
        # B01: a failed classification invents no route (nullable decision).
        assert d["route"] == ""
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

    def test_system_prompt_never_clarifies_when_node_is_named(self) -> None:
        """A unique named node in the request/graph summary is an edit, never a clarify."""
        msgs = build_classify_messages("rename the SaveImage node", has_graph=True)
        system = msgs[0]["content"]
        assert (
            'NEVER choose route="clarify" when the graph summary or user '
            "request names a unique matching node" in system
        )
        assert 'route="revise"' in system

    def test_system_prompt_no_longer_advertises_set_title_edit_op(self) -> None:
        """set_title is not part of the grammar; the classifier must not teach it."""
        msgs = build_classify_messages("rename a node", has_graph=True)
        system = msgs[0]["content"]
        assert "ComfyUI node titles are editable via the set_title edit op" not in system
        assert "set_title" not in system
        assert 'route="revise"' in system

    def test_system_prompt_pins_outside_patterns_to_adapt_and_local_edits_elsewhere(self) -> None:
        msgs = build_classify_messages("borrow the VACE identity travel pattern", has_graph=True)
        system = msgs[0]["content"]
        assert "borrow, port, adapt, follow, or recreate" in system
        for phrase in (
            "VACE identity travel",
            "BlockSwap low-VRAM",
            "two-pass refinement",
            "LoRA chaining",
            "audio latent/lipsync",
            "ControlNet/depth/pose",
        ):
            assert phrase in system
        assert "route=\"adapt\"" in system
        assert "Generic edits to the current graph" in system
        assert "stay route=\"revise\" when concrete" in system
        assert "route=\"clarify\" when ambiguous" in system
        assert (
            "Widget, edge, and single-node-swap intents are route=\"revise\""
            in system
        )
        assert "Do not send these down route=\"adapt\"" in system

    def test_implement_prompt_acts_on_graph_local_evidence_when_research_fails(self) -> None:
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(task="set steps to 30", python_source="ksampler.steps = 20")
        system = messages[0]["content"]
        assert "If research is thin, empty, never, UNAVAILABLE, or exhausted" in system
        assert "graph-local edit that is fully justified by the attached IR" in system
        assert "Refuse only architectural invention" in system
        assert "Never use positional widget indices" in system

    def test_implement_prompt_requires_anchor_for_add_node_relation(self) -> None:
        from vibecomfy.comfy_nodes.agent.provider import build_batch_messages

        messages = build_batch_messages(task="add an image loader", python_source="save = SaveImage()")
        system = messages[0]["content"]
        assert (
            "Every add-node statement that uses `relation=` MUST also include "
            "`near=...` or `group=...`"
        ) in system
        assert "`relation=` alone is rejected" in system

    def test_session_context_renders_text_messages_options_and_census_reference_map(self) -> None:
        msgs = build_classify_messages(
            "option 2",
            has_graph=True,
            graph_summary=(
                "## Census\n"
                "2 node(s), 0 edge(s)\n"
                "class list: CheckpointLoaderSimple (1), KSampler (1)\n"
                "reference map:\n"
                "  1: CheckpointLoaderSimple\n"
                "  2: KSampler"
            ),
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
        )
        content = msgs[1]["content"]
        assert "Recent conversation (for reference resolution):" in content
        assert "[user]: Change the sampler" in content
        assert "Prior clarification question: Which sampler setting?" in content
        assert "2. steps" in content
        assert "Latest candidate reference" in content
        assert "turn=0003" in content
        assert "changed KSampler steps" in content
        # The node reference map comes from the renderer's census lens (the
        # graph summary) — no raw-JSON ref-map sidecar (batch 12 fix).
        assert "reference map:" in content
        assert "1: CheckpointLoaderSimple" in content
        assert "2: KSampler" in content


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

    def test_reply_prompt_uses_plain_prose_with_json_compat(self) -> None:
        msgs = build_reply_messages("explain this graph")
        system = msgs[0]["content"]
        assert '"reply"' in system
        assert "Lightweight Markdown" in system
        assert "short paragraphs, bullet lists, emphasis, and inline code" in system
        assert "plain prose" in system
        assert "backward compatibility" in system
        assert "Do NOT use fenced code blocks" in system

    def test_inspect_reply_prompt_encourages_readable_structure(self) -> None:
        msgs = build_reply_messages(
            "what does this graph do?",
            graph_inspection="1: CheckpointLoaderSimple -> 2: KSampler",
        )
        system = msgs[0]["content"]
        user = msgs[1]["content"]
        assert "For inspect-only or explain-style replies" in system
        assert "instead of compressing everything into one paragraph" in system
        assert "Use short paragraphs and/or bullet lists" in system
        assert "use inline code for node names, parameter names, and widget values" in system
        assert "Do NOT suggest edits or changes" in system
        assert "Graph inspection" in user
        assert "CheckpointLoaderSimple -> 2: KSampler" in user

    def test_failed_empty_adaptation_plan_reply_is_non_actionable(self) -> None:
        msgs = build_reply_messages(
            "adapt this graph",
            adaptation_plan={
                "selected_slice": {"source_class_type": "BadWF"},
                "anchor_bindings": [],
                "required_new_nodes": [],
                "required_rewires": [],
                "edit_ops": [],
                "structural_validation": "fail",
                "semantic_validation": "not_evaluated",
            },
        )
        user = msgs[1]["content"]
        assert "Adaptation plan: non-actionable" in user
        assert "BadWF" not in user
        assert "reference slice" not in user

    def test_concrete_adaptation_plan_reply_keeps_reference_summary(self) -> None:
        msgs = build_reply_messages(
            "adapt this graph",
            adaptation_plan={
                "selected_slice": {"source_class_type": "UsableWF"},
                "edit_ops": [{"op": "set_field", "target": "node_1.seed", "value": 42}],
                "structural_validation": "fail",
                "semantic_validation": "not_evaluated",
            },
        )
        user = msgs[1]["content"]
        assert "Adaptation plan (reference context - not a winner)" in user
        assert "UsableWF" in user

    def test_research_message_sources_cite_author_channel(self) -> None:
        msgs = build_reply_messages(
            "ltx",
            research_sources=(
                {
                    "source": "hivemind_message",
                    "author": "alice",
                    "channel": "ltx_chatter",
                    "title": "LTX 2.5 is great",
                    "description": "LTX 2.5 handles fast previews really well.",
                },
            ),
        )
        content = msgs[1]["content"]
        assert "Research sources:" in content
        assert "alice in #ltx_chatter" in content
        # Message citations carry author/channel, not a bare title line.
        assert "LTX 2.5 is great" not in content

    def test_research_distillation_sources_cite_title_status_confidence(self) -> None:
        msgs = build_reply_messages(
            "ltx",
            research_sources=(
                {
                    "source": "hivemind_distillation",
                    "title": "LTX 2.5 distillation",
                    "distillation_status": "approved",
                    "confidence": 0.9,
                    # Author/channel must never leak into distillation citations.
                    "author": "someone",
                    "channel": "spy-channel",
                },
            ),
        )
        content = msgs[1]["content"]
        assert "LTX 2.5 distillation (approved/0.9)" in content
        assert "someone" not in content
        assert "spy-channel" not in content

    def test_research_distillation_defaults_pending_status(self) -> None:
        msgs = build_reply_messages(
            "ltx",
            research_sources=(
                {
                    "source": "hivemind_distillation",
                    "title": "Draft distillation",
                },
            ),
        )
        content = msgs[1]["content"]
        assert "Draft distillation (pending)" in content

    def test_research_route_reply_instruction(self) -> None:
        """Research-route replies must follow the C5 decision-memo contract
        (question, conclusion, resolvable citation IDs, uncertainty, next
        action) and never add sources absent from the memo. The pre-rework
        community-findings framing was removed with the legacy research
        engine (Wave C)."""
        msgs = build_reply_messages("ltx")
        system = msgs[0]["content"]
        assert 'for route="research"' in system
        assert "C5 decision memo" in system
        assert "without implying an edit" in system
        assert "Do not add sources or claims that are absent from that memo" in system
        assert "question, conclusion, resolvable citation IDs, uncertainty/conflicts, and next action" in system

    def test_reply_prompt_requires_traced_link_citations_for_connectivity(self) -> None:
        """Connectivity claims must enumerate the actual links/nodes traced
        from the workflow IR and cite link ids (REC-C grounding rule)."""
        msgs = build_reply_messages(
            "what connects to the ksampler?",
            graph_inspection="[10] CheckpointLoaderSimple\nEdges:\n  10 -> 12",
        )
        system = msgs[0]["content"]
        user = msgs[1]["content"]
        assert "before asserting that two nodes are connected" in system
        assert "enumerate the actual links/nodes you traced" in system
        assert "cite the link ids" in system
        assert "link 35 connects node 5027 to node 4852" in system
        assert "Never assert a connection you cannot point to in the provided IR" in system
        # The graph-inspection user block frames the IR as the authoritative
        # source of node ids, widget values, and link ids.
        assert "authoritative" in user
        assert "cite link ids and widget" in user

    def test_reply_prompt_requires_exact_widget_key_value_citations(self) -> None:
        """Widget/parameter claims must cite the exact widget key and value
        present in the IR; no invented parameters (REC-C grounding rule)."""
        msgs = build_reply_messages(
            "what does the ipadapter do?",
            graph_inspection="[40] IPAdapterApply\nWidgets: weight=0.7",
        )
        system = msgs[0]["content"]
        assert "Ground every widget/parameter claim in the exact widget key and value" in system
        assert "IPAdapterApply widgets are only" in system
        assert "[weight=0.7]" in system
        assert "Never invent parameters, modes, or settings that are " in system
        assert "absent from the IR" in system
        assert "say it is not present rather than guessing" in system
        assert "marks a widget `unlabeled`" in system
        assert "do not name it" in system
        assert "Do not infer codec families, bit depths, or compositing" in system
        assert "string `auto`" in system
        assert "`switch` widget" in system

    def test_reply_prompt_forbids_unknowable_refusals_with_ir_evidence(self) -> None:
        """'Semantics unknowable' refusals are forbidden when the workflow IR
        provides labeled inputs / node inventory / widget values / link ids
        (REC-C grounding rule)."""
        msgs = build_reply_messages(
            "what does node 20 do?",
            graph_inspection="[20] DetailDaemonSamplerNode\nWidgets: w0=0.1",
        )
        system = msgs[0]["content"]
        assert '"semantics unknowable"' in system
        assert '"cannot be determined"' in system
        assert "reason from those provided graph facts" in system
        assert 'Reserve "unknowable" only for facts the provided evidence genuinely' in system

    def test_reply_prompt_handles_zero_on_topic_research_evidence(self) -> None:
        """When research returned zero on-topic evidence, the reply must say so
        explicitly and ground claims only in the workflow IR, never the
        off-topic research records (REC-C grounding rule)."""
        msgs = build_reply_messages(
            "how does detail daemon work here?",
            research_summary="searches returned only off-topic MiniMax video records",
            graph_inspection="[20] DetailDaemonSamplerNode in an audio chain",
        )
        system = msgs[0]["content"]
        assert "When research produced zero on-topic evidence" in system
        assert "say so explicitly in the reply" in system
        assert "instead of presenting those non-results as findings" in system
        assert "make claims only from the workflow IR" in system
        assert "never from the off-topic research records" in system


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

    def test_revise_attempt_with_string_missing_information_reaches_implement(self) -> None:
        raw = json.dumps(
            {
                "research": False,
                "implement": True,
                "reply": True,
                "intent": "edit",
                "route": "revise",
                "task": "edit_graph",
                "plan_summary": "Set the frame count.",
                "needs_input": {
                    "decision": "assumed",
                    "question": "Which frame count?",
                    "missing_information": "target frame count",
                    "options": ["49", "81"],
                    "bounded_assumption": "Use 49 frames.",
                    "extra_classifier_key": True,
                },
            }
        )

        decision = parse_classify_response(raw)

        assert decision.effective_route == "revise"
        assert decision.implement is True
        assert decision.needs_input is not None
        assert decision.needs_input.missing_information == ("target frame count",)

    def test_valid_revise_drops_malformed_needs_input_sidecar(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        raw = json.dumps(
            {
                "research": False,
                "implement": True,
                "reply": True,
                "intent": "edit",
                "route": "revise",
                "task": "edit_graph",
                "needs_input": {
                    "question": "Which frame count?",
                    "options": 49,
                },
            }
        )

        with caplog.at_level("WARNING", logger="vibecomfy.executor.prompts"):
            decision = parse_classify_response(raw)

        assert decision.effective_route == "revise"
        assert decision.implement is True
        assert getattr(decision, "needs_input", None) is None
        assert "Dropping malformed needs_input sidecar" in caplog.text

    def test_clarify_with_coerced_missing_information_and_assumption_still_raises(self) -> None:
        raw = json.dumps(
            {
                "research": False,
                "implement": False,
                "reply": True,
                "intent": "respond",
                "route": "clarify",
                "needs_input": {
                    "question": "Which frame count?",
                    "missing_information": "target frame count",
                    "bounded_assumption": "Use 49 frames.",
                },
            }
        )

        with pytest.raises(ValueError, match="clarify decision"):
            parse_classify_response(raw)

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

    def test_json_with_trailing_prose_containing_braces(self) -> None:
        """The greedy {.*} fallback matched past the object's closing brace
        when the model appended prose containing {} (e.g. "the {LoRA}
        distillation"), so json.loads failed on otherwise-valid JSON and the
        whole classify turn died with a bogus "workflow validation errors"
        envelope.  Extraction must stop at the FIRST balanced object."""
        raw = (
            '{\n  "research": false,\n  "implement": false,\n  "reply": true,\n'
            '  "effort": "low",\n  "plan_summary": "Clarify the user\'s request"\n}\n'
            "Note: the user asked about distillation {LoRA} for Minimax video."
        )
        d = parse_classify_response(raw)
        assert d.research is False
        assert d.implement is False
        assert d.reply is True
        assert d.plan_summary == "Clarify the user's request"

    def test_json_with_braces_inside_string_values(self) -> None:
        """Braces inside quoted string values must not confuse the scanner."""
        raw = (
            '{"research": false, "implement": false, "reply": true, "effort": "low", '
            '"plan_summary": "Use {Ksampler} with cfg 7"} then done'
        )
        d = parse_classify_response(raw)
        assert d.plan_summary == "Use {Ksampler} with cfg 7"

    def test_research_direction_metadata_round_trips(self) -> None:
        raw = json.dumps(
            {
                "research": True,
                "implement": False,
                "reply": True,
                "effort": "medium",
                "plan_summary": "research faster options",
                "intent": "research",
                "route": "research",
                "task": "research_nodes",
                "research_goal": "Find distilled or faster ways to run the workflow.",
                "search_directions": [
                    "distilled AnimateDiff or lightning motion models",
                    "context length, sampler, steps, and frame-count speed tradeoffs",
                ],
                "source_preferences": ["workflows", "messages", "web"],
                "avoid": ["raw sentence search", "stopword-only searches"],
                "known_graph_context": "Current graph resembles an AnimateDiff workflow.",
            }
        )

        d = parse_classify_response(raw)
        payload = d.to_dict()

        assert d.effective_route == "research"
        assert d.research_goal == "Find distilled or faster ways to run the workflow."
        assert d.search_directions == (
            "distilled AnimateDiff or lightning motion models",
            "context length, sampler, steps, and frame-count speed tradeoffs",
        )
        assert d.source_preferences == ("workflows", "messages", "web")
        assert d.avoid == ("raw sentence search", "stopword-only searches")
        assert d.known_graph_context == "Current graph resembles an AnimateDiff workflow."
        assert payload["search_directions"] == [
            "distilled AnimateDiff or lightning motion models",
            "context length, sampler, steps, and frame-count speed tradeoffs",
        ]

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

    @pytest.mark.parametrize(
        "request_text",
        [
            "/reorganise_comfy_workflow",
            "organise this workflow",
            "clean up the canvas",
            "make this readable",
        ],
    )
    def test_parse_reorganise_examples_canonicalize_to_layout_task(
        self,
        request_text: str,
    ) -> None:
        raw = json.dumps({
            "research": True,
            "implement": False,
            "reply": True,
            "effort": "low",
            "plan_summary": request_text,
            "intent": "edit",
            "route": "reorganise",
        })

        d = parse_classify_response(raw)

        assert d.route == "reorganise"
        assert d.task == "layout_reorganise"
        assert d.effective_task == "layout_reorganise"
        assert d.research is False
        assert d.implement is True

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

    @pytest.mark.parametrize(
        "request_text",
        [
            "borrow the VACE identity travel workflow for this character video",
            "adapt a BlockSwap low-VRAM pattern into this graph",
            "recreate a two-pass refinement workflow from a known template",
            "follow the LoRA chaining pattern from the reference workflow",
            "port an audio latent lipsync setup into my current graph",
            "adapt ControlNet depth and pose guidance from an outside template",
        ],
    )
    def test_parse_representative_outside_pattern_requests_as_adapt(
        self,
        request_text: str,
    ) -> None:
        """Representative classifier outputs for outside-pattern borrowing stay adapt."""
        raw = json.dumps({
            "research": True,
            "implement": True,
            "reply": True,
            "effort": "high",
            "plan_summary": request_text,
            "intent": "edit",
            "route": "adapt",
            "task": "research_precedent",
        })

        decision = parse_classify_response(raw)

        assert decision.effective_route == "adapt"
        assert decision.research is True
        assert decision.implement is True
        assert decision.effective_task == "research_precedent"

    @pytest.mark.parametrize(
        ("request_text", "route", "research", "implement", "task", "expected_route"),
        [
            ("change the sampler seed to 1234", "revise", False, True, "edit_graph", "revise"),
            ("set the prompt to a neon city", "revise", False, True, "edit_graph", "revise"),
            ("move the preview node next to the sampler", "revise", False, True, "edit_graph", "revise"),
            ("make it better using that thing", "clarify", False, False, "respond", "clarify"),
        ],
    )
    def test_parse_generic_local_edits_do_not_become_adapt(
        self,
        request_text: str,
        route: str,
        research: bool,
        implement: bool,
        task: str,
        expected_route: str,
    ) -> None:
        raw = json.dumps({
            "research": research,
            "implement": implement,
            "reply": True,
            "effort": "low",
            "plan_summary": request_text,
            "intent": "edit" if implement else "respond",
            "route": route,
            "task": task,
        })

        decision = parse_classify_response(raw)

        assert decision.effective_route == expected_route
        assert decision.effective_route != "adapt"

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

    def test_plain_prose_accepted(self) -> None:
        raw = "Based on my research, here are the relevant node types: KSampler, VAEDecode."
        text = parse_reply_response(raw)
        assert text == raw

    def test_multiline_prose_normalized(self) -> None:
        raw = "First line.\n\n\nSecond line.   \n\n\n\nThird line."
        text = parse_reply_response(raw)
        assert text == "First line.\n\nSecond line.\n\nThird line."

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            parse_reply_response("   \n\t ")

    def test_malformed_json_looking_raises(self) -> None:
        """JSON-looking-but-unparseable output stays a retryable error."""
        with pytest.raises(ValueError):
            parse_reply_response('{"reply": "unclosed')
        with pytest.raises(ValueError):
            parse_reply_response('```json\n{"reply": "unclosed')

    def test_iteration_limit_sentinel_raises(self) -> None:
        with pytest.raises(ValueError, match="iteration"):
            parse_reply_response(
                "I reached the iteration limit and couldn't generate a summary."
            )

    def test_long_prose_mentioning_limit_is_accepted(self) -> None:
        raw = (
            "LTX 2.5 has no hard iteration limit in practice: the sampler runs "
            "as many steps as configured, and you can raise the step count if "
            "you need more refinement passes."
        )
        text = parse_reply_response(raw)
        assert text == raw

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


# ── T3.1: research-tool / durable-path retry ownership freeze ────────────────


def test_t31_research_tool_retry_budgets_are_frozen() -> None:
    """D2 freeze: hivemind retries once inside the shared phase deadline;
    the research stage corrects malformed decisions at most twice."""
    from vibecomfy.executor import agent_research_stage, hivemind_clients

    assert hivemind_clients._HIVEMIND_STATEMENT_TIMEOUT_RETRIES == 1
    assert hivemind_clients._HIVEMIND_STATEMENT_TIMEOUT_BACKOFF_SECONDS <= 0.5
    assert agent_research_stage.MAX_RESEARCH_DECISION_TURNS == 8
    assert agent_research_stage.MAX_RESEARCH_TOOL_CALLS == 12
    assert agent_research_stage.HIVEMIND_TIMEOUT_CIRCUIT_THRESHOLD == 3
    assert agent_research_stage.TOOL_PHASE_DEADLINE_SECONDS == 450.0
    assert agent_research_stage._RESEARCH_DECISION_MAX_ATTEMPTS == 3


def test_t31_hivemind_deadline_is_checked_before_any_attempt() -> None:
    """The shared operation deadline wins before the first (and any retry)
    attempt: a spent deadline raises a typed timeout with no network call."""
    import time as _time

    from vibecomfy.executor.hivemind_clients import HivemindError, _hivemind_get_table

    with pytest.raises(HivemindError) as raised:
        _hivemind_get_table(
            "external_resources",
            {"select": "id"},
            timeout=5.0,
            deadline=_time.monotonic() - 1.0,
        )
    assert raised.value.reason == "timeout"


def test_t31_durable_path_stays_retry_free_with_bounded_lock() -> None:
    """D4 freeze: recovery on the durable path is pure replay — the only
    bounded wait is the session lock's 10s acquire bound."""
    from vibecomfy.comfy_nodes.agent import _session_lock

    assert _session_lock.DEFAULT_LOCK_TIMEOUT_SECONDS == 10.0
