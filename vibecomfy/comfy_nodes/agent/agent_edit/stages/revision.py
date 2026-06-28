"""Revision-evidence stage functions for the agent-edit pipeline.

These stages collect topology and readiness evidence for the current graph,
produce a revision-evidence artifact, and finalize the evidence after a
candidate graph has been produced by the agent.
"""

from __future__ import annotations

import dataclasses
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from ...audit import write_json_artifact
from ...contracts import (
    ArtifactRef,
    FailureKind,
    StageResult,
    TurnContext,
)
from ..budget import (
    _BATCH_EXIT_NOOP,
    _duration_ms,
)
from ..paths import artifact as _artifact
from ..state import AgentEditState
from vibecomfy.executor.contracts import (
    ReadinessReport,
    RevisionEvidence,
    TopologyFindings,
)
from vibecomfy.executor.revision_evidence import (
    collect_graph_facts,
    collect_readiness_evidence,
    collect_topology_evidence,
    compute_scoped_diff,
)

# Cross-stage import: _resolve_provider_attr lets us reach back into the
# edit.py facade for helpers that are still defined there.
from .agent_delta import _resolve_provider_attr


# ---------------------------------------------------------------------------
# Internal helpers (only used within this module)
# ---------------------------------------------------------------------------


def _revision_no_candidate_reason(evidence: RevisionEvidence) -> str | None:
    if evidence.safe_candidate_possible:
        return None
    if evidence.topology.missing_graph:
        return "no_graph"
    return "no_changes"


def _stable_blocker_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _subtract_existing_blockers(
    current: tuple[Any, ...],
    existing: tuple[Any, ...],
) -> tuple[Any, ...]:
    existing_keys = {_stable_blocker_key(item) for item in existing}
    return tuple(item for item in current if _stable_blocker_key(item) not in existing_keys)


def _localized_additive_scoped_evidence(
    state: AgentEditState,
    *,
    candidate_topology: TopologyFindings,
    candidate_readiness: ReadinessReport,
) -> tuple[
    TopologyFindings | None,
    ReadinessReport | None,
    TopologyFindings | None,
    ReadinessReport | None,
]:
    _can_attempt_local_additive_revise = _resolve_provider_attr("_can_attempt_local_additive_revise")
    _empty_graph_authoring_request = _resolve_provider_attr("_empty_graph_authoring_request")
    if not _can_attempt_local_additive_revise(state) or state.revision_evidence is None:
        return None, None, None, None
    topology = state.revision_evidence.topology
    readiness = state.revision_evidence.readiness
    empty_graph_authoring = _empty_graph_authoring_request(state)
    filtered_original_topology = TopologyFindings(
        missing_graph=False if empty_graph_authoring else topology.missing_graph,
        dangling_links=topology.dangling_links,
        absent_endpoint_nodes=topology.absent_endpoint_nodes,
        socket_type_mismatches=topology.socket_type_mismatches,
        schema_available=topology.schema_available,
        summary=(
            "pre-existing empty-graph authoring baseline ignored for new workflow"
            if empty_graph_authoring
            else "pre-existing unknown/custom-node blockers ignored for localized "
            "runtime code-node addition"
        ),
    )
    filtered_original_readiness = ReadinessReport(
        validation_errors=readiness.validation_errors,
        no_gpu_detected=readiness.no_gpu_detected,
        readiness_blockers=readiness.readiness_blockers,
        object_info_available=readiness.object_info_available,
        summary=(
            "pre-existing missing model/node-pack blockers ignored for localized "
            "runtime code-node addition"
        ),
    )
    filtered_candidate_topology = TopologyFindings(
        missing_graph=candidate_topology.missing_graph,
        dangling_links=candidate_topology.dangling_links,
        absent_endpoint_nodes=candidate_topology.absent_endpoint_nodes,
        socket_type_mismatches=_subtract_existing_blockers(
            candidate_topology.socket_type_mismatches,
            topology.socket_type_mismatches,
        ),
        unknown_class_types=_subtract_existing_blockers(
            candidate_topology.unknown_class_types,
            topology.unknown_class_types,
        ),
        missing_required_inputs=_subtract_existing_blockers(
            candidate_topology.missing_required_inputs,
            topology.missing_required_inputs,
        ),
        schema_available=candidate_topology.schema_available,
        summary=(
            "pre-existing unknown/custom-node blockers subtracted for localized "
            "runtime code-node addition"
        ),
    )
    filtered_candidate_readiness = ReadinessReport(
        missing_models=_subtract_existing_blockers(
            candidate_readiness.missing_models,
            readiness.missing_models,
        ),
        missing_node_packs=_subtract_existing_blockers(
            candidate_readiness.missing_node_packs,
            readiness.missing_node_packs,
        ),
        validation_errors=candidate_readiness.validation_errors,
        no_gpu_detected=candidate_readiness.no_gpu_detected,
        readiness_blockers=candidate_readiness.readiness_blockers,
        object_info_available=candidate_readiness.object_info_available,
        summary=(
            "pre-existing missing model/node-pack blockers subtracted for localized "
            "runtime code-node addition"
        ),
    )
    return (
        filtered_original_topology,
        filtered_original_readiness,
        filtered_candidate_topology,
        filtered_candidate_readiness,
    )


def _session_reference_map_for_evidence(
    conversation_messages: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    from ...provider import _latest_clarification_context

    if not conversation_messages:
        return {}
    compact: dict[str, Any] = {"recent_message_count": len(conversation_messages)}
    latest = conversation_messages[-1] if conversation_messages else None
    if isinstance(latest, Mapping):
        outcome = latest.get("outcome")
        if isinstance(outcome, Mapping) and isinstance(outcome.get("kind"), str):
            compact["latest_outcome_kind"] = outcome["kind"]
        text = latest.get("text")
        if isinstance(text, str) and text.strip():
            compact["latest_text_preview"] = text.strip()[:160]
    clarification = _latest_clarification_context(conversation_messages)
    if clarification is not None:
        compact["pending_clarification"] = {
            "prior_request": clarification["prior_request"][:240],
            "question": clarification["question"][:240],
        }
    latest_candidate = next(
        (
            msg
            for msg in reversed(conversation_messages)
            if isinstance(msg, Mapping)
            and isinstance(msg.get("text"), str)
            and "Latest candidate reference" in msg["text"]
        ),
        None,
    )
    if isinstance(latest_candidate, Mapping):
        compact["latest_candidate_reference"] = str(latest_candidate.get("text", ""))[:400]
    return compact


def _runtime_execution_requested(task: str | None, payload: Mapping[str, Any]) -> bool:
    text = (task or "").lower()
    if any(word in text for word in ("run", "queue", "execute", "render", "generate")):
        return True
    requested = payload.get("execution_requested") or payload.get("run_requested")
    if requested is True:
        return True
    runtime = payload.get("runtime")
    return isinstance(runtime, Mapping) and runtime.get("execution_requested") is True


def _extract_ready_metadata(payload: Mapping[str, Any], graph: Mapping[str, Any] | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("ready_metadata", "ready_template_metadata", "metadata", "requirements"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            metadata[key] = dict(value)
    if isinstance(graph, Mapping):
        extra = graph.get("extra")
        if isinstance(extra, Mapping):
            vibecomfy = extra.get("vibecomfy")
            if isinstance(vibecomfy, Mapping):
                metadata["vibecomfy"] = dict(vibecomfy)
            for key in ("ready_metadata", "requirements", "diagnostics"):
                value = extra.get(key)
                if isinstance(value, Mapping):
                    metadata[key] = dict(value)
                elif isinstance(value, list):
                    metadata[key] = list(value)
    return metadata


def _extract_readiness_diagnostics(payload: Mapping[str, Any], graph: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    diagnostics: list[dict[str, Any]] = []
    for source in (payload, graph if isinstance(graph, Mapping) else {}):
        raw = source.get("diagnostics") if isinstance(source, Mapping) else None
        if isinstance(raw, list):
            diagnostics.extend(dict(item) for item in raw if isinstance(item, Mapping))
    if isinstance(graph, Mapping):
        extra = graph.get("extra")
        if isinstance(extra, Mapping) and isinstance(extra.get("diagnostics"), list):
            diagnostics.extend(dict(item) for item in extra["diagnostics"] if isinstance(item, Mapping))
    runtime = payload.get("runtime")
    if isinstance(runtime, Mapping) and runtime.get("no_gpu_detected") is True:
        diagnostics.append(
            {
                "code": "no_gpu_detected",
                "severity": "error",
                "message": "No GPU is available for runtime execution.",
            }
        )
    return tuple(diagnostics)


def _request_no_gpu_detected(payload: Mapping[str, Any]) -> bool:
    if payload.get("no_gpu_detected") is True:
        return True
    runtime = payload.get("runtime")
    return isinstance(runtime, Mapping) and runtime.get("no_gpu_detected") is True


def _revision_target_node_ids(
    state: AgentEditState,
    *,
    route: str | None,
) -> tuple[str, ...]:
    payload = state.request_payload if isinstance(state.request_payload, Mapping) else {}
    values: list[Any] = []
    for key in ("target_node_ids", "target_nodes", "node_ids"):
        raw = payload.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif raw is not None:
            values.append(raw)
    classification = payload.get("executor_classification")
    if isinstance(classification, Mapping):
        raw = classification.get("target_node_ids") or classification.get("target_nodes")
        if isinstance(raw, list):
            values.extend(raw)
        elif raw is not None:
            values.append(raw)
    task = state.task or ""
    values.extend(re.findall(r"(?:node|#)\s*(\d+)", task, flags=re.IGNORECASE))
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


# ---------------------------------------------------------------------------
# Revision evidence payload / artifact helpers
# ---------------------------------------------------------------------------


def _revision_evidence_artifact_payload(
    state: AgentEditState,
    *,
    route: str | None,
    conversation_messages: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    _canonical_agent_edit_route = _resolve_provider_attr("_canonical_agent_edit_route")
    _json_safe = _resolve_provider_attr("_json_safe")
    classification = (
        state.request_payload.get("executor_classification")
        if isinstance(state.request_payload, Mapping)
        else None
    )
    return {
        "revision_evidence": (
            state.revision_evidence.to_dict()
            if state.revision_evidence is not None
            else {}
        ),
        "classification": _json_safe(classification)
        if isinstance(classification, Mapping)
        else {"route": _canonical_agent_edit_route(state.route or route)},
        "session_reference_map": _session_reference_map_for_evidence(conversation_messages),
    }


def _write_revision_evidence_artifact(
    state: AgentEditState,
    *,
    route: str | None,
    conversation_messages: list[dict[str, Any]] | None,
) -> ArtifactRef:
    payload = _revision_evidence_artifact_payload(
        state,
        route=route,
        conversation_messages=conversation_messages,
    )
    state.revision_evidence_payload = payload
    state.artifacts = {
        **(state.artifacts or {}),
        "revision_evidence": str(state.revision_evidence_path),
    }
    return write_json_artifact(state.revision_evidence_path, payload)


def _revision_evidence_prompt_json(state: AgentEditState) -> str:
    payload = state.revision_evidence_payload
    if not isinstance(payload, Mapping):
        return ""
    try:
        return json.dumps(payload, sort_keys=True, indent=2)
    except (TypeError, ValueError):
        return ""


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------


def _stage_revision_evidence(
    state: AgentEditState,
    _context: TurnContext,
    *,
    route: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    _canonical_agent_edit_route = _resolve_provider_attr("_canonical_agent_edit_route")
    _schema_provider_available = _resolve_provider_attr("_schema_provider_available")
    _hydrate_current_graph_unknown_node_schemas = _resolve_provider_attr(
        "_hydrate_current_graph_unknown_node_schemas"
    )

    start = time.monotonic()
    canonical_route = _canonical_agent_edit_route(state.route or route)
    if canonical_route != "revise":
        # Adapt route: collect compact GraphFacts for workflow-dependent
        # adapt execution without invoking full RevisionEvidence collateral.
        if canonical_route == "adapt":
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


def _stage_revision_readonly_report(
    state: AgentEditState,
    _context: TurnContext,
    *,
    route: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    start = time.monotonic()
    state.ui_payload = json.loads(json.dumps(state.graph))
    state.python_before = ""
    state.python_after = ""
    state.batch_exit_mode = _BATCH_EXIT_NOOP
    state.batch_turn_count = 0
    state.user_message = _revision_readonly_message(state)
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
            "no_candidate_reason": (
                state.revision_evidence.no_candidate_reason
                if state.revision_evidence is not None
                else "no_changes"
            ),
        },
    )


def _finalize_revision_evidence_with_candidate(
    state: AgentEditState,
    *,
    route: str | None,
    conversation_messages: list[dict[str, Any]] | None,
) -> None:
    _schema_provider_available = _resolve_provider_attr("_schema_provider_available")

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
    no_candidate_reason = None if scoped_diff.candidate_eligible else "no_changes"
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
