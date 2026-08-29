"""
Revision evidence stages (T-039 extraction of the edit_revision_stages fragment).

Extracted from the edit.py exec-assembled fragments (T-039, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Function bodies resolve their free
names from the assembled edit-module namespace at call time (marked with a
T-039 late import comment) so monkeypatches on edit.* stay visible exactly as
under the old exec assembly; guarded imports stay function-local.
"""
from __future__ import annotations

from pathlib import Path
import dataclasses
import json
import time
from typing import Mapping


def _revision_evidence_prompt_json(state: AgentEditState) -> str:
    payload = state.revision_evidence_payload
    if not isinstance(payload, Mapping):
        return ""
    try:
        return json.dumps(payload, sort_keys=True, indent=2)
    except (TypeError, ValueError):
        return ""


def _stage_revision_evidence(
    state: AgentEditState,
    _context: TurnContext,
    *,
    route: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (RevisionEvidence, StageResult, _canonical_agent_edit_route, _duration_ms, _extract_readiness_diagnostics, _extract_ready_metadata, _hydrate_current_graph_unknown_node_schemas, _request_no_gpu_detected, _revision_no_candidate_reason, _runtime_execution_requested, _schema_provider_available, _write_revision_evidence_artifact, collect_graph_facts, collect_readiness_evidence, collect_topology_evidence)  # T-039 late import: host namespace lookup; resolved at call time
    start = time.monotonic()
    canonical_route = _canonical_agent_edit_route(state.route or route)
    if canonical_route != "revise":
        # Adapt route: collect compact GraphFacts for workflow-dependent
        # adapt execution without invoking full RevisionEvidence collateral.
        if canonical_route == "adapt":
            _hydrate_current_graph_unknown_node_schemas(state)
            schema_available = _schema_provider_available(state.schema_provider)
            ready_metadata = _extract_ready_metadata(state.request_payload, state.graph)
            readiness_diagnostics = _extract_readiness_diagnostics(state.request_payload, state.graph)
            no_gpu_runtime_request = (
                _runtime_execution_requested(state.task, state.request_payload)
                and _request_no_gpu_detected(state.request_payload)
            )
            explicit_readiness_blockers = (
                ("Runtime execution was requested, but no GPU is available.",)
                if no_gpu_runtime_request
                else ()
            )
            facts = collect_graph_facts(
                state.graph,
                schema_available=schema_available,
                schema_provider=state.schema_provider,
                ready_metadata=ready_metadata,
                diagnostics=readiness_diagnostics,
                no_gpu_detected=no_gpu_runtime_request,
                readiness_blockers=explicit_readiness_blockers,
            )
            state.graph_facts = facts.to_dict()
            return StageResult(
                stage="revision_evidence",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                value={
                    "mode": "graph_facts_collected",
                    "route": canonical_route,
                    "has_blockers": facts.has_blockers,
                },
            )
        return StageResult(
            stage="revision_evidence",
            ok=True,
            blocking=False,
            duration_ms=_duration_ms(start),
            value={"mode": "skipped", "route": canonical_route},
        )

    hydrated_candidates = _hydrate_current_graph_unknown_node_schemas(state)
    schema_available = _schema_provider_available(state.schema_provider)
    topology = collect_topology_evidence(
        state.graph,
        schema_available=schema_available,
        schema_provider=state.schema_provider,
    )
    ready_metadata = _extract_ready_metadata(state.request_payload, state.graph)
    readiness_diagnostics = _extract_readiness_diagnostics(state.request_payload, state.graph)
    no_gpu_runtime_request = (
        _runtime_execution_requested(state.task, state.request_payload)
        and _request_no_gpu_detected(state.request_payload)
    )
    explicit_readiness_blockers = (
        ("Runtime execution was requested, but no GPU is available.",)
        if no_gpu_runtime_request
        else ()
    )
    readiness = collect_readiness_evidence(
        state.graph,
        object_info_available=schema_available,
        schema_provider=state.schema_provider,
        ready_metadata=ready_metadata,
        diagnostics=readiness_diagnostics,
        no_gpu_detected=no_gpu_runtime_request,
        readiness_blockers=explicit_readiness_blockers,
    )
    draft = RevisionEvidence(
        topology=topology,
        readiness=readiness,
        no_candidate_reason=None,
        candidate_eligible=False,
    )
    draft = dataclasses.replace(
        draft,
        summary=(
            "Safe revise candidate can be attempted."
            if draft.safe_candidate_possible
            else "Safe revise candidate blocked before model repair."
        ),
    )
    state.revision_evidence = dataclasses.replace(
        draft,
        no_candidate_reason=_revision_no_candidate_reason(draft),
    )
    evidence_ref = _write_revision_evidence_artifact(
        state,
        route=canonical_route,
        conversation_messages=conversation_messages,
    )
    return StageResult(
        stage="revision_evidence",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(evidence_ref,),
        value={
            "mode": "collected",
            "safe_candidate_possible": state.revision_evidence.safe_candidate_possible,
            "no_candidate_reason": state.revision_evidence.no_candidate_reason,
            "hydrated_registry_candidate_count": len(hydrated_candidates),
        },
    )


def _revision_readonly_message(state: AgentEditState) -> str:
    evidence = state.revision_evidence
    if evidence is None:
        return "No safe revise candidate is available; the graph is unchanged."
    blockers: list[str] = []
    if evidence.topology.has_blockers:
        blockers.append(evidence.topology.summary or "topology blockers")
    if evidence.topology.schema_available is False:
        blockers.append("schema unavailable")
    if evidence.readiness.has_blockers:
        blockers.append(evidence.readiness.summary or "readiness blockers")
    detail = "; ".join(item for item in blockers if item) or "no safe candidate evidence"
    return (
        "No safe revise candidate is available, so I left the graph unchanged. "
        f"Evidence: {detail}."
    )


def _stage_readonly_diagnostic_report(
    state: AgentEditState,
    _context: TurnContext,
    *,
    route: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
    message: str | None = None,
    report_payload: Mapping[str, Any] | None = None,
    no_candidate_reason: str | None = None,
) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (StageResult, _BATCH_EXIT_NOOP, _artifact, _duration_ms, _revision_readonly_message, _write_revision_evidence_artifact)  # T-039 late import: host namespace lookup; resolved at call time
    start = time.monotonic()
    state.ui_payload = json.loads(json.dumps(state.graph))
    state.python_before = ""
    state.python_after = ""
    state.batch_exit_mode = _BATCH_EXIT_NOOP
    state.batch_turn_count = 0
    state.user_message = (
        message.strip()
        if isinstance(message, str) and message.strip()
        else _revision_readonly_message(state)
    )
    state.batch_final_summary = state.user_message
    state.batch_done_summary = state.user_message
    evidence_payload = (
        state.revision_evidence.to_dict()
        if state.revision_evidence is not None
        else {}
    )
    state.report = {
        "revision_evidence": evidence_payload,
        "read_only": True,
        "graph_unchanged": True,
        "queue_blockers": [],
    }
    if isinstance(report_payload, Mapping):
        state.report.update(json.loads(json.dumps(report_payload)))
    state.artifacts = {
        **(state.artifacts or {}),
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "revision_evidence": str(state.revision_evidence_path),
    }
    _write_revision_evidence_artifact(
        state,
        route=state.route or route,
        conversation_messages=conversation_messages,
    )
    resolved_no_candidate_reason = (
        no_candidate_reason
        if isinstance(no_candidate_reason, str) and no_candidate_reason
        else (
            state.revision_evidence.no_candidate_reason
            if state.revision_evidence is not None
            else "no_changes"
        )
    )
    return StageResult(
        stage="agent_batch",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=tuple(
            _artifact(Path(path))
            for path in (state.artifacts or {}).values()
            if Path(path).exists()
        ),
        value={
            "mode": "read_only_revision_report",
            "graph_unchanged": True,
            "no_candidate_reason": resolved_no_candidate_reason,
        },
    )


def _stage_revision_readonly_report(
    state: AgentEditState,
    context: TurnContext,
    *,
    route: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (_stage_readonly_diagnostic_report)  # T-039 late import: host namespace lookup; resolved at call time
    return _stage_readonly_diagnostic_report(
        state,
        context,
        route=route,
        conversation_messages=conversation_messages,
    )


def _finalize_revision_evidence_with_candidate(
    state: AgentEditState,
    *,
    route: str | None,
    conversation_messages: list[dict[str, Any]] | None,
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (_BATCH_EXIT_NOOP, _extract_readiness_diagnostics, _extract_ready_metadata, _localized_additive_scoped_evidence, _request_no_gpu_detected, _revision_readonly_message, _revision_target_node_ids, _runtime_execution_requested, _schema_provider_available, _write_revision_evidence_artifact, collect_readiness_evidence, collect_topology_evidence, compute_scoped_diff, write_json_artifact)  # T-039 late import: host namespace lookup; resolved at call time
    if state.revision_evidence is None:
        return
    candidate_graph = state.ui_payload if isinstance(state.ui_payload, dict) else None
    schema_available = _schema_provider_available(state.schema_provider)
    candidate_topology = collect_topology_evidence(
        candidate_graph,
        schema_available=schema_available,
        schema_provider=state.schema_provider,
    )
    ready_metadata = _extract_ready_metadata(state.request_payload, candidate_graph)
    readiness_diagnostics = _extract_readiness_diagnostics(state.request_payload, candidate_graph)
    no_gpu_runtime_request = (
        _runtime_execution_requested(state.task, state.request_payload)
        and _request_no_gpu_detected(state.request_payload)
    )
    candidate_readiness = collect_readiness_evidence(
        candidate_graph,
        object_info_available=schema_available,
        schema_provider=state.schema_provider,
        ready_metadata=ready_metadata,
        diagnostics=readiness_diagnostics,
        no_gpu_detected=no_gpu_runtime_request,
        readiness_blockers=(
            ("Runtime execution was requested, but no GPU is available.",)
            if no_gpu_runtime_request
            else ()
        ),
    )
    scoped_topology = state.revision_evidence.topology
    scoped_readiness = state.revision_evidence.readiness
    (
        localized_topology,
        localized_readiness,
        localized_candidate_topology,
        localized_candidate_readiness,
    ) = _localized_additive_scoped_evidence(
        state,
        candidate_topology=candidate_topology,
        candidate_readiness=candidate_readiness,
    )
    if (
        localized_topology is not None
        and localized_readiness is not None
        and localized_candidate_topology is not None
        and localized_candidate_readiness is not None
    ):
        scoped_topology = localized_topology
        scoped_readiness = localized_readiness
        candidate_topology = localized_candidate_topology
        candidate_readiness = localized_candidate_readiness
    scoped_diff = compute_scoped_diff(
        state.graph,
        candidate_graph,
        topology=scoped_topology,
        readiness=scoped_readiness,
        candidate_topology=candidate_topology,
        candidate_readiness=candidate_readiness,
        target_node_ids=_revision_target_node_ids(state, route=route),
    )
    # ADJUDICATION-4 (production evidence seam): this label is a GENERIC
    # terminal-state classification only — it is emitted whenever the scoped
    # diff has no eligible candidate, regardless of why, so it carries ZERO
    # adjudicative authority over any scenario's expected-no-candidate
    # contract (see tests/live_agentic_harness TERMINAL_NO_CANDIDATE_REASONS).
    # It must stay scenario-agnostic: never specialized from scenario
    # expectations, never treated by the assessor as absence evidence.
    # S2: never no_changes when final!=original or accepted_batch>0.
    # e8c20a staged 2 ops applied but no_changes; character-replacement same.
    from vibecomfy.comfy_nodes.agent._frag_state import _total_landed_edit_count as _s2_landed
    _s2_has_landed = False
    try:
        _s2_has_landed = _s2_landed(state) > 0
    except Exception:
        _s2_has_landed = False
    _s2_hashes_differ = bool(scoped_diff.before_hash and scoped_diff.after_hash and scoped_diff.before_hash != scoped_diff.after_hash)
    if _s2_has_landed or _s2_hashes_differ:
        if "no_diff" in scoped_diff.eligibility_blockers:
            _filtered = tuple(b for b in scoped_diff.eligibility_blockers if b != "no_diff")
            scoped_diff = dataclasses.replace(
                scoped_diff,
                eligibility_blockers=_filtered,
                candidate_eligible=len(_filtered) == 0 and scoped_diff.before_hash != "" and scoped_diff.after_hash != "",
                summary=scoped_diff.summary.replace("no_diff", "").replace("ineligible: ;", "").strip() if _filtered else scoped_diff.summary,
            )
    no_candidate_reason = None if scoped_diff.candidate_eligible else "no_changes"
    if no_candidate_reason == "no_changes" and (_s2_has_landed or _s2_hashes_differ):
        no_candidate_reason = None
        scoped_diff = dataclasses.replace(scoped_diff, candidate_eligible=True)
    state.revision_evidence = dataclasses.replace(
        state.revision_evidence,
        scoped_diff=scoped_diff,
        candidate_eligible=scoped_diff.candidate_eligible,
        no_candidate_reason=no_candidate_reason,
        summary=(
            scoped_diff.summary
            if scoped_diff.summary
            else state.revision_evidence.summary
        ),
    )
    evidence_payload = state.revision_evidence.to_dict()
    if state.report is None:
        state.report = {}
    state.report["revision_evidence"] = evidence_payload
    _write_revision_evidence_artifact(
        state,
        route=state.route or route,
        conversation_messages=conversation_messages,
    )
    if scoped_diff.candidate_eligible:
        return
    state.batch_exit_mode = _BATCH_EXIT_NOOP
    state.ui_payload = json.loads(json.dumps(state.graph))
    try:
        write_json_artifact(state.candidate_ui_path, state.ui_payload)
    except Exception:
        pass
    state.user_message = _revision_readonly_message(state)
    state.batch_final_summary = state.user_message
    state.batch_done_summary = state.user_message
    state.report.update(
        {
            "read_only": True,
            "graph_unchanged": True,
            "no_candidate_reason": no_candidate_reason,
        }
    )


__all__ = (
    "_finalize_revision_evidence_with_candidate",
    "_revision_evidence_prompt_json",
    "_revision_readonly_message",
    "_stage_readonly_diagnostic_report",
    "_stage_revision_evidence",
    "_stage_revision_readonly_report",
)
