# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: State, common imports, basic change helpers.

SOURCE = r'''
from __future__ import annotations

import ast
import base64
import dataclasses
import difflib
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .audit import (
    artifact_ref_for_path,
    normalize_agent_edit_v2_metadata,
    write_allocation_failure_audit,
    write_audit,
    write_json_artifact,
)
from .contracts import (
    AgentError,
    ApplyCandidate,
    ApplyEligibility,
    ArtifactRef,
    FailureEnvelope,
    FailureKind,
    StageSnapshot,
    StageResult,
    TurnIdentity,
    TurnContext,
    TurnOutcome,
    _ABSENT_FIELD_OLD,
    _MISSING_FIELD_CHANGE_OLD,
    _iter_ui_graph_nodes,
    _ui_node_uid,
    _ui_node_uid_aliases,
    _ui_widget_value_for_field,
    build_legacy_agent_edit_v1,
    classify_failure,
    derive_apply_eligibility,
    ensure_agent_edit_response_contract,
    failure_envelope,
    product_failure_envelope_fields,
    public_outcome_from_turn_outcome,
    repair_field_changes,
    success_envelope,
    turn_envelope,
)
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.schema.validate import validation_errors_payload
from vibecomfy.workflow import ValidationIssue
from .gates import (
    apply_stage_gate_updates,
    derive_gates,
    initialize_gates,
    update_plan_validate_gate,
    update_state_match_gate,
)
from .provider import (
    AgentTurnResult,
    BatchTurnResult,
    MalformedModelJSON,
    MissingRequiredField,
    ProviderError,
    _latest_clarification_context,
    build_batch_messages,
    build_delta_messages,
    build_messages,
    ensure_sentence_message,
    run_agent_turn,
    run_agent_turn_batch,
    run_agent_turn_delta,
    run_model_turn,
)
from .diagnostics import lower_stage_result, queue_stage_result
from .execution_plan import (
    ExecutionPlan,
    PlanEvaluation,
)
from .execution_plan_runtime import (
    evaluate_execution_plan_for_state,
    format_compact_plan_feedback,
    format_compact_plan_status,
    hydrate_execution_plan_from_protocol_notes,
)
from .session import (
    allocate_turn,
    normalize_session_id,
    payload_hash,
    read_state,
    record_idempotent_response,
    session_dir_for,
    structural_graph_hash,
    turn_dir_for,
)
from vibecomfy.executor.contracts import (
    ReadinessReport,
    RevisionEvidence,
    TopologyFindings,
    is_actionable_adaptation_plan,
)
from vibecomfy.executor.revision_evidence import (
    collect_graph_facts,
    collect_readiness_evidence,
    collect_topology_evidence,
    compute_scoped_diff,
)

if TYPE_CHECKING:
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.workflow import VibeWorkflow

DeepSeekClient = Callable[[list[dict[str, str]]], dict[str, str]]

_SESSION_ROOT = Path("out/editor_sessions")
DEFAULT_CHAT_DISPLAY_MESSAGES = 50
PROMPT_MEMORY_MESSAGES = 5
LOGGER = logging.getLogger(__name__)
_WARNED_LEGACY_CONTRACTS: set[str] = set()
_WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS: set[str] = set()


@dataclass
class AgentEditState:
    task: str
    graph: dict[str, Any]
    request_payload: dict[str, Any]
    schema_provider: Any
    baseline_graph_hash: str | None
    submit_graph_hash: str | None
    submit_structural_graph_hash: str | None
    submitted_client_graph_hash: str | None
    submitted_client_structural_graph_hash: str | None
    session_dir: Path
    turn_dir: Path
    request_path: Path
    original_ui_path: Path
    before_py_path: Path
    after_py_path: Path
    projection_path: Path
    model_request_path: Path
    model_response_path: Path
    candidate_ui_path: Path
    messages_path: Path
    revision_evidence_path: Path = Path("revision_evidence.json")
    execution_plan_path: Path = Path("execution_plan.json")
    plan_evaluation_path: Path = Path("plan_evaluation.json")
    workflow: Any = None
    edited_workflow: Any = None
    original_intent_workflow: VibeWorkflow | None = None
    prior_store: Any = None
    guard_original_ui: dict[str, Any] | None = None
    python_before: str = ""
    python_after: str = ""
    user_message: str = ""
    lowering_evidence: list[dict[str, Any]] = field(default_factory=list)
    lowering_recovery_entries: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] | None = None
    revision_evidence: RevisionEvidence | None = None
    revision_evidence_payload: dict[str, Any] | None = None
    ui_payload: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    artifacts: dict[str, str] | None = None
    projection_text: str = ""
    delta_ops: tuple[Any, ...] = ()
    delta_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    delta_audit: dict[str, Any] | None = None
    emit_guard_resolved_ops: tuple[Any, ...] | None = None
    guard_result: dict[str, Any] | None = None
    # Batch REPL state (gated behind VIBECOMFY_AGENT_EDIT_BATCH_REPL=1)
    batch_session: EditSession | None = None
    batch_signature_catalog: str = ""
    executor_research_summary: str = ""
    executor_research_warnings: tuple[str, ...] = ()
    executor_research_sources: tuple[dict[str, Any], ...] = ()
    executor_precedent_slices: tuple[dict[str, Any], ...] = ()
    executor_adaptation_plan: dict[str, Any] | None = None
    executor_research_brief: dict[str, Any] | None = None
    # SD3: adapt-prefetch scoped research nested under execution_protocol_notes.
    execution_protocol_notes: dict[str, Any] | None = None
    execution_plan: ExecutionPlan | None = None
    plan_evaluation: PlanEvaluation | None = None
    # SD3: neutral precedent packet as discardable research context.
    research_context_packet: dict[str, Any] | None = None
    # SD2: compact graph facts from topology/readiness collectors for adapt context.
    graph_facts: dict[str, Any] | None = None
    graph_inspection: str = ""
    batch_turns: list[dict[str, Any]] = field(default_factory=list)
    batch_field_changes: tuple[FieldChange, ...] = ()
    batch_noop_field_changes: tuple[FieldChange, ...] = ()
    batch_budget_state: dict[str, Any] = field(default_factory=dict)
    batch_turn_count: int = 0
    batch_max_turns: int = 50
    batch_max_consecutive_errors: int = 3
    batch_feedback: str = ""
    batch_final_summary: str = ""
    batch_exit_mode: str = ""
    batch_done_summary: str = ""
    lint_noop_messages: tuple[str, ...] = ()
    provisional_registry_candidate_hashes: frozenset[str] = frozenset()
    # T15: route label carried on state so response builders can apply route-aware
    # validation/reporting without changing their call signatures.
    route: str | None = None
    # Narrative/debug fields: the first non-empty executor message is preserved as a
    # debug/input artifact and never overwritten by deterministic finish text.
    raw_executor_message: str = ""
    narrative_context_path: Path = Path("narrative_context.json")
    narrative_request_path: Path = Path("narrative_request.json")
    narrative_response_path: Path = Path("narrative_response.json")
    narrative_validation_path: Path = Path("narrative_validation.json")
    post_edit_reorganisation_advisory: dict[str, Any] | None = None


def _hydrate_execution_plan_from_protocol_notes(
    state: AgentEditState,
    protocol_notes: Mapping[str, Any],
) -> None:
    hydrate_execution_plan_from_protocol_notes(state, protocol_notes)


class _StageBlocked(Exception):
    def __init__(self, result: StageResult, failure: FailureEnvelope | None = None) -> None:
        super().__init__(result.stage)
        self.result = result
        self.failure = failure


def _build_lowering_recovery_entries(
    lowering_evidence: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in lowering_evidence:
        loop_node_id = item.get("loop_node_id")
        loop_uid = item.get("loop_uid")
        lowered_native_count = item.get("lowered_node_count", 0)
        entries.append(
            {
                "node_id": loop_node_id,
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": loop_uid,
                "lowered": True,
                "runtime_backed": False,
                "provider": "static_lowering",
                "confidence": 1.0,
                "diagnostic": f"statically lowered to {lowered_native_count} native node(s)",
                "lowered_native_count": lowered_native_count,
                "source_node_id": loop_node_id,
                "source_node_uid": loop_uid,
                "original_intent_hash": item.get("original_intent_hash"),
                "lowered_fragment_hash": item.get("lowered_fragment_hash"),
                "layout_policy": item.get("layout_policy"),
                "variable": item.get("variable"),
                "iterations": item.get("iterations"),
                "iteration_values": list(item.get("iteration_values") or ()),
            }
        )
    return entries


def _build_lowering_change_entries(
    lowering_evidence: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in lowering_evidence:
        loop_node_id = item.get("loop_node_id")
        loop_uid = item.get("loop_uid")
        entries.append(
            {
                "node_id": loop_node_id,
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": loop_uid,
                "lowered": True,
                "source_node_id": loop_node_id,
                "source_node_uid": loop_uid,
                "lowered_native_count": item.get("lowered_node_count", 0),
                "original_intent_hash": item.get("original_intent_hash"),
                "lowered_fragment_hash": item.get("lowered_fragment_hash"),
            }
        )
    return entries


def _build_lowering_audit_entries(
    lowering_evidence: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in lowering_evidence:
        entry = dict(item)
        if "lowered_node_count" in entry:
            entry["node_count"] = entry.pop("lowered_node_count")
        if "lowered_fragment_hash" in entry:
            entry["lowered_graph_fragment_hash"] = entry.pop("lowered_fragment_hash")
        entries.append(entry)
    return entries


def _inject_lowering_provenance(state: AgentEditState) -> None:
    if state.report is None or not state.lowering_evidence:
        state.lowering_recovery_entries = []
        return
    recovery_entries = _build_lowering_recovery_entries(state.lowering_evidence)
    state.lowering_recovery_entries = recovery_entries
    recovery_report = state.report.setdefault("recovery", [])
    if isinstance(recovery_report, list):
        recovery_report.extend(recovery_entries)
    change_report = state.report.setdefault("change", {})
    if isinstance(change_report, dict):
        change_report["lowered"] = _build_lowering_change_entries(state.lowering_evidence)


def _safe_session_id(value: str | None = None) -> str:
    """Normalize a session id to a safe path component.

    Delegates to the authoritative ``normalize_session_id`` in ``.session``
    so every call site (edit, routes, executor) shares the same containment
    contract.
    """
    return normalize_session_id(value)


def _artifact(path: Path) -> ArtifactRef:
    return artifact_ref_for_path(path)


def _repair_field_changes_from_original_ui(
    graph: Mapping[str, Any],
    changes: tuple[FieldChange, ...],
) -> tuple[FieldChange, ...]:
    return repair_field_changes(graph, changes)


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _total_landed_edit_count(state: AgentEditState) -> int:
    # Only non-noop field changes count as landed edits.
    real = _real_field_changes(tuple(state.batch_field_changes or ()))
    count = len(real)
    if count > 0:
        return count
    total = 0
    for turn in state.batch_turns:
        # Prefer the actual field changes list; if it exists and is empty,
        # the turn produced no real edits (only no-ops) and should not count.
        field_changes = turn.get("field_changes")
        if isinstance(field_changes, list) and not field_changes:
            continue
        landed = turn.get("landed_op_count")
        if isinstance(landed, int) and landed > 0:
            total += landed
    return total


def _read_only_discovery_turn_count(state: AgentEditState) -> int:
    count = 0
    for turn in state.batch_turns:
        statements = turn.get("statements")
        if not isinstance(statements, list) or not statements:
            continue
        landed = turn.get("landed_op_count")
        if isinstance(landed, int) and landed > 0:
            continue
        if all(
            isinstance(statement, Mapping)
            and str(statement.get("op_kind") or "") == "query"
            for statement in statements
        ):
            count += 1
    return count


_DISCOVERY_CONSTRUCTION_NUDGE_THRESHOLD = 3
_DISCOVERY_CONSTRUCTION_NUDGE = (
    "Discovery-only loop nudge: stop broad searching. Construct one bounded edit "
    "from the available signatures and workflow evidence. If no named node exists "
    "and code execution is appropriate, use `vibecomfy.exec` with typed `io` as a "
    "fallback; otherwise call `clarify(\"...\")` with the specific typed blocker."
)


def _turn_is_discovery_only_no_edit(turn: Mapping[str, Any]) -> bool:
    statements = turn.get("statements")
    if not isinstance(statements, list) or not statements:
        return False
    landed = turn.get("landed_op_count")
    if isinstance(landed, int) and landed > 0:
        return False
    return all(
        isinstance(statement, Mapping)
        and str(statement.get("op_kind") or "") == "query"
        for statement in statements
    )


def _consecutive_discovery_only_turn_count(state: AgentEditState) -> int:
    count = 0
    for turn in reversed(state.batch_turns):
        if not isinstance(turn, Mapping):
            break
        if not _turn_is_discovery_only_no_edit(turn):
            break
        count += 1
    return count


def _discovery_construction_nudge(state: AgentEditState) -> str:
    if _total_landed_edit_count(state) > 0:
        return ""
    if (
        _consecutive_discovery_only_turn_count(state)
        < _DISCOVERY_CONSTRUCTION_NUDGE_THRESHOLD
    ):
        return ""
    return _DISCOVERY_CONSTRUCTION_NUDGE


def _discovery_stop_message(state: AgentEditState) -> str:
    return (
        "I could not produce a safe graph edit from the available workflow precedent "
        "and current authoring surface. "
        "The graph is unchanged."
    )


def _format_research_brief_for_prompt(brief: Mapping[str, Any] | None) -> str:
    if not isinstance(brief, Mapping) or not brief:
        return ""
    allowed_keys = (
        "research_goal",
        "search_directions",
        "source_preferences",
        "avoid",
        "known_graph_context",
        "model_families",
        "pattern_category",
        "change_goal",
    )
    compact: dict[str, Any] = {}
    for key in allowed_keys:
        value = brief.get(key)
        if isinstance(value, str) and value.strip():
            compact[key] = value.strip()
        elif isinstance(value, (list, tuple)):
            items = [
                str(item).strip()
                for item in value
                if isinstance(item, str) and item.strip()
            ]
            if items:
                compact[key] = items[:8]
    return json.dumps(compact, indent=2, sort_keys=True) if compact else ""


'''
