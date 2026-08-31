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
    ).to_dict()
    assert durable["evidence_pack"]["artifacts"]["evidence:1"]["body"]["body"] == "source"

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
