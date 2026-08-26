from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from vibecomfy.executor import core
from vibecomfy.executor.contracts import (
    RESEARCH_EVIDENCE_SHARED_KEYS,
    ClassifyDecision,
    ExecutorHostPorts,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    OrchestrationModeConfigurationError,
    Report,
    coerce_orchestration_mode,
    resolve_orchestration_mode,
    validate_reply_change_claims,
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
    assert seen["request"].pipeline_mode == "threaded"
    assert seen["plan"].effective_route == "adapt"
    assert seen["grounding"]["landed"] is True
    assert events == [("execute", "start"), ("execute", "done")]
    assert result.report.to_dict()["executor"]["orchestration_mode"] == "threaded"


def test_shipped_profiles_have_explicit_execute_specs() -> None:
    for name in ("default", "opensource", "openrouter", "openai", "anthropic"):
        assert isinstance(load_profile(name)["execute"], AgentSpecShape)


def test_frozen_durable_checkpoint_still_enforces_claims_subset_delta() -> None:
    implementation = ImplementationResult(
        graph={"nodes": [], "links": []},
        durable_response={
            "accepted_batch": [
                {
                    "op": {
                        "op": "set_node_field",
                        "target": ["workflow", "1", "steps"],
                        "value": 30,
                    }
                }
            ],
            "outcome": {
                "changes": [
                    {"uid": "1", "field_path": "cfg"},
                ]
            },
        },
    )

    assert implementation.durable_response is not None
    assert isinstance(implementation.durable_response["accepted_batch"], tuple)
    violations = validate_reply_change_claims(implementation.durable_response)
    assert len(violations) == 1
    assert "(1, cfg)" in violations[0]


def test_threaded_accepted_edit_survives_projection_failure() -> None:
    graph = {"nodes": [], "links": []}
    ended: list[object] = []
    ports = replace(
        _ports(),
        end_deepseek_usage_capture=lambda token: ended.append(token),
    )

    def run_implement(*args: Any, **kwargs: Any) -> ImplementationResult:
        return ImplementationResult(
            graph=graph,
            message="Untrusted narration after the checkpoint.",
            durable_response={
                "accepted_batch": [
                    {
                        "op": {
                            "op": "set_node_field",
                            "target": ["workflow", "1", "steps"],
                            "value": 30,
                        }
                    }
                ]
            },
        )

    kernel = ThreadedKernel(
        resolve_spec=lambda profile, stage: AgentSpecShape("hermes", "model", "medium"),
        run_implement=run_implement,
        emit_phase=lambda *args, **kwargs: None,
        enforce_reply_grounding=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("projection failed")
        ),
        accepted_delta_ops=lambda implementation: (
            dict(implementation.durable_response["accepted_batch"][0]["op"]),
        ),
        implementation_landed_edit=lambda implementation: True,
        no_candidate_reason=lambda implementation: None,
    )

    result = run_threaded_executor(
        ExecutorRequest(query="set steps", graph=graph, pipeline_mode="threaded"),
        kernel=kernel,
        host_ports=ports,
        executor_id="executor-test",
    )

    assert result.ok is True
    assert result.graph is graph
    assert "edit landed" in result.reply
    assert "1 operation" in result.reply
    assert len(ended) == 1


def test_threaded_replaces_prose_when_frozen_sidecar_claim_exceeds_delta() -> None:
    graph = {"nodes": [], "links": []}
    grounded: list[str] = []

    def run_implement(*args: Any, **kwargs: Any) -> ImplementationResult:
        return ImplementationResult(
            graph=graph,
            message="I changed both steps and cfg.",
            durable_response={
                "accepted_batch": [
                    {
                        "op": {
                            "op": "set_node_field",
                            "target": ["workflow", "1", "steps"],
                            "value": 30,
                        }
                    }
                ],
                "outcome": {
                    "changes": [{"uid": "1", "field_path": "cfg"}],
                },
            },
        )

    def enforce(reply: str, **kwargs: Any) -> str:
        grounded.append(reply)
        return reply

    kernel = ThreadedKernel(
        resolve_spec=lambda profile, stage: AgentSpecShape("hermes", "model", "medium"),
        run_implement=run_implement,
        emit_phase=lambda *args, **kwargs: None,
        enforce_reply_grounding=enforce,
        accepted_delta_ops=lambda implementation: (
            dict(implementation.durable_response["accepted_batch"][0]["op"]),
        ),
        implementation_landed_edit=lambda implementation: True,
        no_candidate_reason=lambda implementation: None,
    )

    result = run_threaded_executor(
        ExecutorRequest(query="set steps", graph=graph, pipeline_mode="threaded"),
        kernel=kernel,
        host_ports=_ports(),
        executor_id="executor-test",
    )

    assert result.ok is True
    assert grounded == [
        "I changed both steps and cfg.",
        "The workflow edit landed; see the accepted change set in the candidate.",
    ]
    assert result.reply == grounded[-1]


def test_threaded_no_graph_runs_research_conversation_instead_of_skipping() -> None:
    seen: dict[str, Any] = {}

    def run_implement(
        request: ExecutorRequest,
        spec: AgentSpecShape,
        **kwargs: Any,
    ) -> ImplementationResult:
        del request, spec
        seen["plan"] = kwargs["plan"]
        return ImplementationResult(
            message="Evidence-backed faster workflow options.",
            durable_response={
                "graph_unchanged": True,
                "research_findings": {
                    "sources": [{"title": "Distilled video precedent"}],
                    "summary": "A fetched workflow supports the faster path.",
                    "community_summary": "A fetched workflow supports the faster path.",
                    "warnings": [],
                },
                "batch_turns": [{
                    "turn_number": 0,
                    "statements": [{
                        "detail": {
                            "tool_call": "hivemind_get",
                            "tool_status": "ok",
                            "ledger_entry": {
                                "decision": "hivemind_get",
                                "conclusion": "Fetched workflow precedent.",
                                "evidence_ids": ["hivemind:workflows:1"],
                            },
                        },
                    }],
                }],
            },
        )

    kernel = ThreadedKernel(
        resolve_spec=lambda profile, stage: AgentSpecShape("hermes", "model", "medium"),
        run_implement=run_implement,
        emit_phase=lambda *args, **kwargs: None,
        enforce_reply_grounding=lambda reply, **kwargs: reply,
        accepted_delta_ops=lambda implementation: (),
        implementation_landed_edit=lambda implementation: False,
        no_candidate_reason=lambda implementation: "route_not_applyable",
    )
    result = run_threaded_executor(
        ExecutorRequest(query="find a faster distilled video workflow"),
        kernel=kernel,
        host_ports=_ports(),
        executor_id="executor-research",
    )

    assert result.ok is True
    assert result.reply == "Evidence-backed faster workflow options."
    # RR1-FIX-REV2 F9: the envelope is uniform for every request shape; a
    # missing graph is context ("No ComfyUI canvas graph is attached"), not
    # a forced research route.
    assert seen["plan"].effective_route == "adapt"
    assert seen["plan"].implement is True
    assert "No ComfyUI canvas graph is attached" in seen["plan"].plan_summary
    # RR1-FIX-REV2 F9: durable research-findings extraction from
    # ``evidence["research"]`` was exclusive to the removed forced-research
    # lane; under the uniform adapt envelope it behaves exactly like every
    # other adapt-routed threaded turn (narration grounding still consumes
    # the durable response).


def test_threaded_research_refusal_is_not_projected_as_tool_execution() -> None:
    result = ExecutorResult.success(
        report=Report(
            plan=ClassifyDecision(route="research", task="research_nodes"),
            implementation=ImplementationResult(
                message="Research was unavailable.",
                durable_response={
                    "research_findings": {
                        "sources": [{"title": "Unproven narrative source"}],
                        "summary": "Claimed research without execution.",
                        "tool_calls_executed": 12,
                        "research_attempt": "grounded",
                    },
                    "batch_turns": [{
                        "statements": [{
                            "detail": {
                                "tool_call": "hivemind_search",
                                "tool_status": "refused",
                                "ledger_entry": None,
                            },
                        }],
                    }],
                },
            ),
            orchestration_mode="threaded",
        ),
        reply="Research was unavailable.",
    )

    research = result.to_dict()["evidence"]["research"]
    assert research["research_attempt"] == "never"
    assert research["tool_calls_executed"] == 0
    assert research["evidence_artifacts"] == 0
    assert research["citations"] == []


def test_threaded_answer_only_travels_as_context_and_deliberator_owns_route() -> None:
    """RR1-FIX-REV2 F9: answer_only no longer forces the inspect lane.  The
    envelope is uniform, the interaction intent travels as context in the
    plan summary, and run_implement (the typed deliberation surface) runs;
    any deterministic ``run_inspect_reply`` shortcut must stay unused."""
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0]}},
    }
    seen: dict[str, Any] = {}

    def run_implement(
        request: ExecutorRequest,
        spec: AgentSpecShape,
        **kwargs: Any,
    ) -> ImplementationResult:
        del spec
        seen["request"] = request
        seen["plan"] = kwargs["plan"]
        return ImplementationResult(
            message="The checkpoint feeds the sampler.",
            durable_response={"graph_unchanged": True},
        )

    kernel = ThreadedKernel(
        resolve_spec=lambda profile, stage: AgentSpecShape("hermes", "model", "medium"),
        run_implement=run_implement,
        emit_phase=lambda *args, **kwargs: None,
        enforce_reply_grounding=lambda reply, **kwargs: reply,
        accepted_delta_ops=lambda implementation: (),
        implementation_landed_edit=lambda implementation: False,
        no_candidate_reason=lambda implementation: None,
        run_inspect_reply=lambda *args, **kwargs: pytest.fail(
            "deterministic inspect lane must not fire"
        ),
    )
    result = run_threaded_executor(
        ExecutorRequest(
            query="explain this graph",
            graph=graph,
            interaction_mode="answer_only",
        ),
        kernel=kernel,
        host_ports=_ports(),
        executor_id="executor-inspect",
    )

    assert result.ok is True
    assert result.reply == "The checkpoint feeds the sampler."
    assert seen["plan"].effective_route == "adapt"
    assert "answer_only: respond without editing" in seen["plan"].plan_summary


# ── T4.1: shared research evidence contract (cross-mode field parity) ────────


def _staged_research_result(*, status: str = "ok", deadline_reached: bool = False):
    """Build the staged carrier for the canonical one-fetch research scenario."""
    from vibecomfy.executor.agent_research_stage import (
        DECISION_GET,
        DECISION_QUESTION,
        AgentResearchIteration,
        AgentResearchTrace,
    )
    from vibecomfy.executor.core import AgentResearchResult
    from vibecomfy.executor.evidence_pack import (
        EvidenceArtifact,
        EvidenceLedger,
        EvidenceLedgerEntry,
        EvidencePack,
    )

    entries = (
        EvidenceLedgerEntry(
            decision=DECISION_QUESTION,
            conclusion="q",
            evidence_ids=("research_question",),
            uncertainty="",
        ),
        EvidenceLedgerEntry(
            decision=DECISION_GET,
            conclusion="Fetched workflow precedent.",
            evidence_ids=("hivemind_get:workflows:111",),
            uncertainty="",
            tool_status="ok",
        ),
        EvidenceLedgerEntry(
            decision="synthesize",
            conclusion="A fetched workflow supports the faster path.",
            evidence_ids=("hivemind_get:workflows:111",),
            uncertainty="low",
        ),
    )
    trace = AgentResearchTrace(
        route="research",
        question="q",
        final_verdict="enough",
        summary="A fetched workflow supports the faster path.",
        iterations=(
            AgentResearchIteration(
                iteration=1,
                question="q",
                tool_calls=({"tool": "hivemind_get"},),
                synthesis={},
                verdict="refine",
            ),
        ),
        citations=("hivemind_get:workflows:111",),
        uncertainty="low",
        status=status,
        elapsed_seconds=0.0,
        attempt="grounded",
        executed_tool_calls=1,
        evidence_artifact_count=1,
        budget={
            "deadline_seconds": 450.0,
            "turns_used": 2 if not deadline_reached else 8,
            "deadline_reached": deadline_reached,
        },
    )
    pack = EvidencePack(
        artifacts={
            "research_question": EvidenceArtifact(
                evidence_id="research_question",
                kind="research_question",
                body={"question": "q"},
            ),
            "hivemind_get:workflows:111": EvidenceArtifact(
                evidence_id="hivemind_get:workflows:111",
                kind="hivemind_get",
                body={"content": "fixture"},
            ),
        },
        ledger=EvidenceLedger(entries=entries),
    )
    return AgentResearchResult(route="research", trace=trace, evidence_pack=pack)


def _threaded_durable_response(*, deadline: bool = False) -> dict[str, Any]:
    """The threaded carrier's durable packet for the SAME scenario."""
    report: dict[str, Any] = {"graph_unchanged": True, "queue_blockers": []}
    if deadline:
        report["phase_deadline"] = "Research phase stopped after 3 turn(s)."
        report["phase_deadline_seconds"] = 450.0
    return {
        "graph_unchanged": True,
        "report": report,
        "research_findings": {
            "sources": [{"title": "Distilled video precedent"}],
            "summary": "A fetched workflow supports the faster path.",
            "community_summary": "A fetched workflow supports the faster path.",
            "warnings": [],
            "budget": {
                "turns_used": 3,
                "deadline_seconds": 450.0,
                **({"deadline_reached": True} if deadline else {}),
            },
        },
        "batch_turns": [{
            "turn_number": 0,
            "statements": [{
                "detail": {
                    "tool_call": "hivemind_get",
                    "tool_status": "ok",
                    "ledger_entry": {
                        "decision": "hivemind_get",
                        "conclusion": "Fetched workflow precedent.",
                        "evidence_ids": ["hivemind_get:workflows:111"],
                    },
                },
            }],
        }],
    }


def test_t41_shared_evidence_keys_present_in_both_carriers() -> None:
    from vibecomfy.executor.contracts import _durable_research_evidence

    staged = _staged_research_result().to_dict()
    threaded = _durable_research_evidence(
        ImplementationResult(
            message="done",
            durable_response=_threaded_durable_response(),
        ),
        plan=ClassifyDecision(route="research", task="research_nodes"),
    )
    # Field-for-field parity: every shared key present in BOTH; absence in
    # either mode is a failure. Counts/bytes may differ.
    assert RESEARCH_EVIDENCE_SHARED_KEYS <= set(staged)
    assert RESEARCH_EVIDENCE_SHARED_KEYS <= set(threaded)


def test_t41_attempt_status_citations_and_budget_agree_across_modes() -> None:
    from vibecomfy.executor.contracts import _durable_research_evidence

    staged = _staged_research_result().to_dict()
    threaded = _durable_research_evidence(
        ImplementationResult(
            message="done",
            durable_response=_threaded_durable_response(),
        ),
    )
    assert staged["research_attempt"] == threaded["research_attempt"] == "grounded"
    assert staged["status"] == threaded["status"] == "ok"
    assert staged["citations"] == threaded["citations"] == [
        "hivemind_get:workflows:111"
    ]
    assert (
        staged["budget"]["deadline_seconds"]
        == threaded["budget"]["deadline_seconds"]
        == 450.0
    )
    assert staged["budget"]["deadline_reached"] is False
    assert threaded["budget"]["deadline_reached"] is False
    assert staged["tool_call_statuses"] == {"ok": 1}
    assert set(threaded["tool_call_statuses"]) == {"ok"}
    # Permitted count divergence: the staged loop counts its decision
    # iterations; the threaded projection counts research-bearing batch
    # turns. Both are honest typed ints; they need not be equal.
    assert isinstance(staged["decision_turns"], int) and staged["decision_turns"] >= 1
    assert isinstance(threaded["decision_turns"], int) and threaded["decision_turns"] >= 1
    # Compact handoff ledger exists in both, same entry schema.
    staged_entry = staged["ledger"]["entries"][1]
    threaded_entry = threaded["ledger"]["entries"][0]
    assert staged_entry["evidence_ids"] == threaded_entry["evidence_ids"]
    assert staged_entry["tool_status"] == threaded_entry["tool_status"] == "ok"


def test_t41_exhausted_and_unsupported_source_agree_across_modes() -> None:
    from vibecomfy.executor.contracts import (
        _durable_research_evidence,
        source_policy_entries,
    )

    plan = ClassifyDecision(
        route="research",
        task="research_nodes",
        source_preferences=("web",),
    )
    staged_hit = _staged_research_result(
        status="exhausted", deadline_reached=True
    ).to_dict()
    assert staged_hit["status"] == "exhausted"
    assert staged_hit["budget"]["deadline_reached"] is True

    threaded_hit = _durable_research_evidence(
        ImplementationResult(
            message="done",
            durable_response=_threaded_durable_response(deadline=True),
        ),
        plan=plan,
    )
    assert threaded_hit["status"] == "exhausted"
    assert threaded_hit["budget"]["deadline_reached"] is True
    assert "research_phase_deadline" in {
        item["code"] for item in threaded_hit["diagnostics"]
    }
    # The unsupported-source diagnostic CONTRACT is shared: the identical
    # plan preferences yield the identical typed diagnostic on both carriers
    # (threaded plans are host-authored, so staged exercises the live path).
    _, policy = source_policy_entries(plan.source_preferences)
    assert [item["code"] for item in policy] == ["unsupported_research_source"]
    staged_result = _staged_research_result()
    core_result = core._source_policy_entries(plan)
    assert [item["code"] for item in core_result[1]] == [
        "unsupported_research_source"
    ]
    assert core_result[1] == policy


def test_threaded_implement_failure_keeps_retained_durable_turn() -> None:
    """RRSYN2-2: the threaded implement-failure branch must pass the
    retained failed ImplementationResult to build_report — a bare
    build_report() is why threaded failures published
    evidence.implementation={} and a blank lineage manifest."""
    from vibecomfy.executor.core import _ExecutorPhaseError

    def run_implement(*args: Any, **kwargs: Any) -> ImplementationResult:
        raise _ExecutorPhaseError(
            stage="implement",
            failure_kind="ValidationError",
            message="Emit refused: unknown port AUDIO_0.",
            implementation_result=ImplementationResult(
                message="Emit refused: unknown port AUDIO_0.",
                failure={
                    "failure_kind": "ValidationError",
                    "stage": "implement",
                    "message": "Emit refused: unknown port AUDIO_0.",
                    "session_id": "sess-threaded",
                    "turn_id": "turn-t7",
                },
                durable_response={
                    "session_id": "sess-threaded",
                    "turn_id": "turn-t7",
                    "accepted_batch": [],
                    "change_details": {"landed_operation_count": 0},
                },
            ),
        )

    kernel = ThreadedKernel(
        resolve_spec=lambda profile, stage: AgentSpecShape(
            "hermes", "model", "medium"
        ),
        run_implement=run_implement,
        emit_phase=lambda *args, **kwargs: None,
        enforce_reply_grounding=lambda reply, **kwargs: reply,
        accepted_delta_ops=lambda implementation: (),
        implementation_landed_edit=lambda implementation: False,
        no_candidate_reason=lambda implementation: None,
    )
    result = run_threaded_executor(
        ExecutorRequest(query="edit", graph={"nodes": [], "links": []}),
        kernel=kernel,
        host_ports=_ports(),
        executor_id="executor-test",
    )

    assert result.ok is False
    report = result.report.to_dict()["executor"]
    implementation = report["implementation"]
    assert implementation is not None
    assert implementation["failure"]["session_id"] == "sess-threaded"
    assert implementation["failure"]["turn_id"] == "turn-t7"
    lineage = report["artifact_lineage"]
    assert lineage["lineage"]["session_id"] == "sess-threaded"
    assert lineage["lineage"]["turn_id"] == "turn-t7"
