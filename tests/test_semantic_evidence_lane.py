"""Focused regressions for the evidence-preserving semantic answer lane."""

from __future__ import annotations

import json
from typing import Any

from vibecomfy.executor.evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidencePack,
    project_ledger_for_prompt,
)
from vibecomfy.executor.prompts import build_reply_messages
from vibecomfy.executor.core import AgentResearchResult, _validate_reply_provenance
from vibecomfy.executor.agent_research_stage import AgentResearchTrace, run_agent_research_stage
from vibecomfy.executor.graph_inspection import inspect_workflow
from vibecomfy.executor.hivemind_tools import hivemind_get, hivemind_search
from vibecomfy.executor.agent_research_stage import _safe_research_args
from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ImplementationResult,
    _durable_research_evidence,
)
from vibecomfy.executor.tool_contracts import ToolStatus
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def test_overflow_projection_keeps_newest_ledger_evidence() -> None:
    artifact = EvidenceArtifact(
        evidence_id="evidence:full",
        kind="research",
        body={"full_body": "durable source body"},
    )
    pack = EvidencePack(
        artifacts={artifact.evidence_id: artifact},
        ledger=EvidenceLedger(
            entries=(
                EvidenceLedgerEntry(
                    decision="synthesis",
                    conclusion="A very long conclusion " + ("x" * 3970),
                    evidence_ids=(artifact.evidence_id,),
                    uncertainty="",
                ),
            )
        ),
    )

    projected = project_ledger_for_prompt(pack.ledger, max_chars=180)
    assert projected["entries"], "overflow must not erase the evidence ledger"
    assert projected.get("truncated") is True
    assert artifact.evidence_id in pack.artifacts
    assert pack.artifacts[artifact.evidence_id].body["full_body"] == "durable source body"
    assert len(json.dumps(projected, sort_keys=True)) <= 180


def test_claim_provenance_round_trips_and_reaches_reply_prompt() -> None:
    entry = EvidenceLedgerEntry(
        decision="synthesis",
        conclusion="The fetched record supports the wiring pattern.",
        evidence_ids=("evidence:1",),
        uncertainty="",
        claim_provenance={"wiring pattern": ("evidence:1",)},
    )
    pack = EvidencePack(
        artifacts={
            "evidence:1": EvidenceArtifact(
                evidence_id="evidence:1", kind="record", body={"body": "source"}
            )
        },
        ledger=EvidenceLedger(entries=(entry,)),
    )
    rebuilt = EvidencePack.from_dict(pack.to_dict())
    assert rebuilt.ledger.claim_provenance == {"wiring pattern": ("evidence:1",)}
    trace = AgentResearchTrace(
        route="research",
        question="Explain the pattern",
        iterations=(),
        final_verdict="enough",
        summary="The fetched record supports the wiring pattern.",
        citations=("evidence:1",),
        uncertainty="",
        status="ok",
        elapsed_seconds=0.0,
    )
    durable = AgentResearchResult(
        route="research", trace=trace, evidence_pack=rebuilt
    )
    durable_payload = durable.to_dict()
    assert durable_payload["evidence_pack"]["artifacts"]["evidence:1"]["body"]["body"] == "source"
    public_payload = durable.to_public_dict()
    assert "evidence_pack" not in public_payload
    assert durable.evidence_pack.artifacts["evidence:1"].body["body"] == "source"

    messages = build_reply_messages(
        "Explain the pattern",
        claim_provenance=rebuilt.ledger.claim_provenance,
        graph_facts={
            "nodes": [
                {
                    "node_id": 1,
                    "class_type": "KSampler",
                    "widgets": [
                        {"field": "steps", "type": "int", "widget_index": 0, "value": 20}
                    ],
                }
            ],
            "edges": [{"link_id": 7, "origin_node": 1, "target_node": 2}],
        },
    )
    user = messages[1]["content"]
    assert "Claim provenance" in user
    assert "evidence:1" in user
    assert '"widget_index": 0' in user
    assert '"link_id": 7' in user


def test_reply_provenance_repair_removes_invented_and_search_only_citations() -> None:
    search = EvidenceArtifact(
        evidence_id="hivemind_search:1",
        kind="hivemind_search_hit",
        body={"title": "lead"},
    )
    pack = EvidencePack(
        artifacts={search.evidence_id: search},
        ledger=EvidenceLedger(
            entries=(EvidenceLedgerEntry(
                decision="synthesis",
                conclusion="lead",
                evidence_ids=(search.evidence_id,),
                uncertainty="",
            ),)
        ),
    )
    trace = AgentResearchTrace(
        route="inspect",
        question="q",
        iterations=(),
        status="ok",
        final_verdict="enough",
        summary="",
        citations=(),
        uncertainty="",
        elapsed_seconds=0.0,
    )
    result = AgentResearchResult(route="inspect", trace=trace, evidence_pack=pack)
    repaired = _validate_reply_provenance(
        "The current capability is supported [hivemind_search:1] and [invented:9].",
        result,
    )
    assert "[invented:9]" not in repaired
    assert "unverified" in repaired


def test_no_research_answer_qualifies_external_current_claims() -> None:
    repaired = _validate_reply_provenance(
        "The latest Claude model costs less and has higher rate limits.",
        None,
    )
    assert "unverified" in repaired


def test_named_scalar_inputs_never_get_sorted_synthetic_widget_indices() -> None:
    workflow = VibeWorkflow(id="semantic", source=WorkflowSource(id="semantic"))
    workflow.nodes["1"] = VibeNode(
        id="1",
        class_type="UnknownNode",
        inputs={"zeta": 3, "alpha": 1},
    )
    widgets = inspect_workflow(workflow).nodes[0].widgets
    assert {widget.name for widget in widgets} == {"alpha", "zeta"}
    assert all(widget.index is None for widget in widgets)


def test_optional_research_can_finish_without_a_tool_call() -> None:
    trace, pack = run_agent_research_stage(
        route="inspect",
        question="Explain this graph locally",
        judge_fn=lambda *_args: {
            "action": "finish",
            "conclusion": "The graph is locally explainable.",
            "evidence_ids": [],
            "uncertainty": "",
        },
        deadline_seconds=5,
        max_turns=1,
        allow_empty_finish=True,
    )
    assert trace.status == "ok"
    assert trace.executed_tool_calls == 0
    assert any(entry.decision == "synthesize" for entry in pack.ledger.entries)


def test_research_egress_rejects_oversized_query_and_timeout() -> None:
    query_result = hivemind_search("x" * 513)
    timeout_result = hivemind_get("hivemind:messages:1", timeout=31)
    assert query_result.status is ToolStatus.INVALID_REQUEST
    assert timeout_result.status is ToolStatus.INVALID_REQUEST


def test_research_egress_rejects_nonfinite_timeout_and_redacts_embedded_payloads() -> None:
    import math

    safe = _safe_research_args(
        "hivemind_search",
        {
            "query": (
                "find workflow= {\"nodes\": [{\"class_type\": \"SecretNode\"}]} "
                "with api_key=abc123 and Authorization: Bearer supersecret"
            ),
            "timeout": "NaN",
        },
    )
    # Preserve malformed values so the registered validator returns a typed
    # invalid_request before transport; do not silently default/drop them.
    assert safe["timeout"] == "NaN"
    assert "SecretNode" not in safe["query"]
    assert "abc123" not in safe["query"]
    assert "supersecret" not in safe["query"]
    assert not any(isinstance(value, float) and not math.isfinite(value) for value in safe.values())
    assert hivemind_search("q", timeout=float("nan")).status is ToolStatus.INVALID_REQUEST
    assert hivemind_get("hivemind:messages:1", timeout=float("inf")).status is ToolStatus.INVALID_REQUEST


def test_research_egress_redacts_escaped_quote_secret_without_suffix_leak() -> None:
    safe = _safe_research_args(
        "hivemind_search",
        {"query": 'query {"api_key": "TOP\\\"SECRET", "password": "PW"}'},
    )
    assert "TOP" not in safe["query"]
    assert "SECRET" not in safe["query"]
    assert "PW" not in safe["query"]


def test_research_egress_redacts_scalar_workflow_and_body_markers() -> None:
    for query, secret in (
        ('workflow="SECRETWORKFLOW"', "SECRETWORKFLOW"),
        ('body="TOPSECRET_BODY"', "TOPSECRET_BODY"),
        ("workflow: SECRETWORKFLOW", "SECRETWORKFLOW"),
        ("body=TOPSECRET_BODY", "TOPSECRET_BODY"),
    ):
        redacted = _safe_research_args("hivemind_search", {"query": query})["query"]
        assert secret not in redacted
        assert "redacted structured payload" in redacted
    benign = _safe_research_args(
        "hivemind_search", {"query": "the workflow is useful for comparison"}
    )["query"]
    assert benign == "the workflow is useful for comparison"


def test_reply_provenance_requires_body_support_and_claim_coverage() -> None:
    fetched = EvidenceArtifact(
        evidence_id="hivemind_record:1",
        kind="hivemind_record",
        body={"body": "The record discusses a blue sampler with 20 steps."},
    )
    pack = EvidencePack(
        artifacts={fetched.evidence_id: fetched},
        ledger=EvidenceLedger(entries=()),
    )
    trace = AgentResearchTrace(
        route="inspect", question="q", iterations=(), status="ok",
        final_verdict="enough", summary="", citations=(), uncertainty="",
        elapsed_seconds=0.0,
    )
    result = AgentResearchResult(route="inspect", trace=trace, evidence_pack=pack)
    unsupported = _validate_reply_provenance(
        "The system currently supports feature X [hivemind_record:1].", result
    )
    assert "[hivemind_record:1]" not in unsupported
    assert "unverified" in unsupported
    supported = _validate_reply_provenance(
        "The record discusses a blue sampler with 20 steps [hivemind_record:1].", result
    )
    assert "unverified" not in supported
    mixed = _validate_reply_provenance(
        "The record discusses a blue sampler with 20 steps and pricing is $100 [hivemind_record:1].",
        result,
    )
    assert "blue sampler" in mixed and "pricing is $100" in mixed
    assert mixed.count("[hivemind_record:1]") == 1
    assert "pricing is $100" in mixed and "This claim is unverified" in mixed


def test_graph_provenance_requires_a_concrete_node_or_link_witness() -> None:
    fetched = EvidenceArtifact(
        evidence_id="hivemind_record:graph",
        kind="hivemind_record",
        body={"body": "unrelated fetched record"},
    )
    trace = AgentResearchTrace(
        route="inspect", question="q", iterations=(), status="ok",
        final_verdict="enough", summary="", citations=(), uncertainty="",
        elapsed_seconds=0.0,
    )
    result = AgentResearchResult(
        route="inspect", trace=trace,
        evidence_pack=EvidencePack(
            artifacts={fetched.evidence_id: fetched}, ledger=EvidenceLedger()
        ),
    )
    graph = {
        "nodes": [{"node_id": "1", "class_type": "KSampler", "inputs": {"steps": 20}}],
        "edges": [{"link_id": 7, "origin_node": "1", "target_node": "2"}],
    }
    unsupported = _validate_reply_provenance(
        "The graph supports FooBar [hivemind_record:graph].", result, graph
    )
    assert "[hivemind_record:graph]" not in unsupported
    assert "unverified" in unsupported
    grounded = _validate_reply_provenance(
        "The graph contains node 1 of type KSampler.", result, graph
    )
    assert "unverified" not in grounded


def test_reply_prompt_bounds_actual_combined_context_and_identifier_length() -> None:
    messages = build_reply_messages(
        "answer " + "q" * 10000,
        research_memo={"summary": "m" * 100000, "sources": ["s" * 100000]},
        claim_provenance={"claim " + str(index): ["evidence:" + "x" * 10000] for index in range(24)},
        graph_facts={
            "nodes": [{"node_id": index, "class_type": "N", "title": "t" * 10000} for index in range(48)],
            "edges": [{"link_id": index, "origin_node": 1, "target_node": 2} for index in range(96)],
        },
    )
    content = messages[1]["content"]
    assert len(content) <= 32000
    assert "evidence:" in content
    assert "x" * 1000 not in content


def test_threaded_missing_research_profile_degrades_to_reply() -> None:
    from vibecomfy.executor.contracts import ExecutorHostPorts, ExecutorRequest
    from vibecomfy.executor.profiles import AgentSpecShape
    from vibecomfy.executor.threaded import ThreadedKernel, run_threaded_executor

    phases: list[str] = []

    def resolve(_profile: str | None, stage: str) -> AgentSpecShape:
        phases.append(stage)
        if stage == "research":
            raise LookupError("research profile unavailable")
        return AgentSpecShape("hermes", "model", "low")

    kernel = ThreadedKernel(
        resolve_spec=resolve,
        run_implement=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("edit")),
        emit_phase=lambda *_args, **kwargs: None,
        enforce_reply_grounding=lambda reply, **_kwargs: reply,
        accepted_delta_ops=lambda _implementation: (),
        implementation_landed_edit=lambda _implementation: False,
        no_candidate_reason=lambda _implementation: None,
        run_inspect_reply=lambda *_args, **_kwargs: "Reply without research.",
        run_research=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    ports = ExecutorHostPorts(
        handle_agent_edit=lambda *_args, **_kwargs: {},
        payload_hash=lambda payload: "hash",
        classify_failure=lambda *_args, **_kwargs: type("Failure", (), {"kind": type("K", (), {"value": "ValidationError"})(), "user_facing_message": "failure"})(),
        failure_envelope=lambda *_args, **_kwargs: None,
        begin_deepseek_usage_capture=lambda: None,
        snapshot_deepseek_usage_capture=lambda: ({}, True),
        end_deepseek_usage_capture=lambda _token: None,
        begin_model_attempt_capture=lambda: None,
        snapshot_model_attempt_capture=lambda: (),
        end_model_attempt_capture=lambda _token: None,
    )
    result = run_threaded_executor(
        ExecutorRequest(query="explain", interaction_mode="answer_only", research_required=True),
        kernel=kernel, host_ports=ports, executor_id="test",
    )
    assert result.ok
    assert phases == ["research", "reply"]


def test_threaded_durable_projection_retains_full_artifact_body() -> None:
    implementation = ImplementationResult(
        durable_response={
            "research_findings": {"sources": [], "summary": "s", "warnings": []},
            "batch_turns": [{"statements": [{"detail": {
                "tool_call": "hivemind_get", "tool_status": "ok",
                "evidence_artifacts": [{
                    "evidence_id": "hivemind_record:1", "kind": "hivemind_record",
                    "body": {"body": "complete fetched record body"},
                }],
                "ledger_entry": {"decision": "get", "conclusion": "fetched", "evidence_ids": ["hivemind_record:1"]},
            }}]}],
        }
    )
    projected = _durable_research_evidence(implementation, ClassifyDecision(route="research", research=True))
    assert projected["evidence_pack"]["artifacts"]["hivemind_record:1"]["body"]["body"] == "complete fetched record body"


def test_live_threaded_tool_surface_is_serialized_before_terminal_close() -> None:
    from types import SimpleNamespace

    from vibecomfy.comfy_nodes.agent._frag_response_contract import _batch_tool_evidence_pack
    from vibecomfy.porting.edit._resolve import _AgentToolSurface

    surface = _AgentToolSurface(search_budget=1, fetch_budget=1, registry_budget=1)
    artifact = EvidenceArtifact(
        evidence_id="hivemind_record:live",
        kind="hivemind_record",
        body={"body": "the complete live body"},
    )
    surface.artifacts[artifact.evidence_id] = artifact
    state = SimpleNamespace(batch_session=SimpleNamespace(_tool_surface=surface))
    packed = _batch_tool_evidence_pack(state)
    assert packed is not None
    assert packed["artifacts"]["hivemind_record:live"]["body"]["body"] == "the complete live body"


def test_answer_only_research_callback_cannot_produce_edit() -> None:
    """Threaded answer-only gets research affordance while edit stays absent."""
    from vibecomfy.executor.contracts import ExecutorHostPorts, ExecutorRequest
    from vibecomfy.executor.profiles import AgentSpecShape
    from vibecomfy.executor.threaded import ThreadedKernel, run_threaded_executor

    calls: list[str] = []
    graph: dict[str, Any] = {"nodes": [], "links": []}

    class Research:
        ledger = EvidenceLedger(entries=())
        research_attempt = "empty"
        claim_provenance: dict[str, tuple[str, ...]] = {}

        def to_dict(self) -> dict[str, Any]:
            return {"research_attempt": self.research_attempt, "ledger": self.ledger.to_dict()}

    def inspect_reply(*_args: Any, **kwargs: Any) -> str:
        calls.append("reply")
        assert kwargs["research_result"] is not None
        return "Grounded answer."

    kernel = ThreadedKernel(
        resolve_spec=lambda _profile, _stage: AgentSpecShape("hermes", "model", "low"),
        run_implement=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("answer-only must never enter implement")
        ),
        emit_phase=lambda *_args, **_kwargs: None,
        enforce_reply_grounding=lambda reply, **_kwargs: reply,
        accepted_delta_ops=lambda _implementation: (),
        implementation_landed_edit=lambda _implementation: False,
        no_candidate_reason=lambda _implementation: None,
        run_inspect_reply=inspect_reply,
        run_research=lambda *_args, **_kwargs: (calls.append("research") or Research()),
    )
    ports = ExecutorHostPorts(
        handle_agent_edit=lambda *_args, **_kwargs: {},
        payload_hash=lambda _payload: "hash",
        classify_failure=lambda *_args, **_kwargs: type("F", (), {"kind": type("K", (), {"value": "ValidationError"})(), "user_facing_message": "failed"})(),
        failure_envelope=lambda *_args, **_kwargs: None,
        begin_deepseek_usage_capture=lambda: object(),
        snapshot_deepseek_usage_capture=lambda: ({}, False),
        end_deepseek_usage_capture=lambda _token: None,
        begin_model_attempt_capture=lambda: object(),
        snapshot_model_attempt_capture=lambda: (),
        end_model_attempt_capture=lambda _token: None,
    )
    result = run_threaded_executor(
            ExecutorRequest(
                query="research this graph",
                graph=graph,
                interaction_mode="answer_only",
                research_required=True,
            ),
        kernel=kernel,
        host_ports=ports,
        executor_id="semantic-test",
    )
    assert result.ok is True
    assert result.graph is None
    assert calls == ["research", "reply"]
    assert result.report.research is not None
