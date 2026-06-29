from __future__ import annotations

import dataclasses
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from ...audit import write_json_artifact
from ...contracts import StageResult, TurnContext
from ..budget import _json_safe
from ..clarify import _BATCH_EXIT_NOOP
from ..paths import _artifact
from ..runtime_schema import (
    _extract_readiness_diagnostics,
    _extract_ready_metadata,
    _hydrate_current_graph_unknown_node_schemas,
    _localized_additive_scoped_evidence,
    _request_no_gpu_detected,
    _revision_no_candidate_reason,
    _runtime_execution_requested,
    _schema_provider_available,
    _session_reference_map_for_evidence,
)
from ..state import AgentEditState
from .agent_delta import _resolve_provider_attr
from vibecomfy.executor.contracts import RevisionEvidence
from vibecomfy.executor.revision_evidence import (
    collect_graph_facts,
    collect_readiness_evidence,
    collect_topology_evidence,
    compute_scoped_diff,
)


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _canonical_agent_edit_route(route: str | None) -> str | None:
    """Normalize executor-facing route labels to the canonical vocabulary."""
    # Resolve from the edit facade so monkeypatch targets stay valid.
    return _resolve_provider_attr("_canonical_agent_edit_route")(route)


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


def _revision_evidence_artifact_payload(
    state: AgentEditState,
    *,
    route: str | None,
    conversation_messages: list[dict[str, Any]] | None,
) -> dict[str, Any]:
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
) -> "ArtifactRef":
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


def _stage_revision_evidence(
    state: AgentEditState,
    _context: TurnContext,
    *,
    route: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
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
