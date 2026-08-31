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
        ExecutorRequest(query="research this graph", graph=graph, interaction_mode="answer_only"),
        kernel=kernel,
        host_ports=ports,
        executor_id="semantic-test",
    )
    assert result.ok is True
    assert result.graph is None
    assert calls == ["research", "reply"]
    assert result.report.research is not None
