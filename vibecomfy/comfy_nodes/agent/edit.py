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
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from .audit import (
    normalize_agent_edit_v2_metadata,
    write_allocation_failure_audit,
    write_audit,
    write_json_artifact,
)
from .contracts import (
    AgentError,
    ApplyCandidate,
    ApplyEligibility,
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
from .agent_edit.clarify import (
    TerminalClarifySplit,
    _BATCH_EXIT_BUDGET,
    _BATCH_EXIT_DONE,
    _BATCH_EXIT_EDIT_CLARIFY,
    _BATCH_EXIT_NOOP,
    _BATCH_EXIT_PURE_CLARIFY,
    _CLARIFY_FORBIDDEN_RESPONSE_KEYS,
    _build_premature_clarify_turn_record,
    _compute_premature_clarify_feedback,
    _extract_clarify_message,
    _format_clarify_markdown_message,
    _sanitize_pure_clarify_response,
    _strip_clarify_forbidden_response_fields,
    split_terminal_clarify,
)
from .agent_edit.client import DeepSeekClient
from .agent_edit.fields import (
    _field_change_is_noop,
    _noop_field_changes,
    _real_field_changes,
    _repair_field_changes_from_original_ui,
)
from .agent_edit.lowering import (
    _build_lowering_audit_entries,
    _inject_lowering_provenance,
)
from .agent_edit.paths import _artifact, _safe_session_id
from .agent_edit.state import AgentEditState
from .agent_edit.budget import (
    _batch_budget_failure_kind,
    _batch_has_landed_edits,
    _field_changes_payload,
    _json_safe,
)
from .agent_edit.labels import (
    _article_for,
    _change_subject,
    _display_value,
    _first_link_source_label,
    _format_available_node_names,
    _format_node_variable_index,
    _format_query_output,
    _format_statement_source,
    _is_link_endpoint,
    _iter_ui_nodes,
    _join_human_list,
    _link_endpoint_parts,
    _looks_internal_uid,
    _node_class_label,
    _node_key_values,
    _node_label_by_uid,
    _node_phrase,
    _present_class_types,
    _resolve_endpoint_label,
    _resolve_output_slot_name,
    _structural_change_phrases,
    _ui_display_widget_value_for_field,
    _ui_node_by_uid,
)
from .agent_edit.messages import (
    _batch_candidate_graph_changed,
    _batch_research_memory_summary,
    _batch_warning_sentence,
    _change_details_payload,
    _discovery_stop_message,
    _format_batch_report,
    _format_batch_report_json,
    _format_research_brief_for_prompt,
    _human_change_phrase,
    _humanized_edit_message,
    _humanized_noop_message,
    _landed_edit_lead,
    _lint_issue_to_dict,
    _normalize_test_client_batch_response,
    _normalize_test_client_response,
    _operation_detail_payload,
    _premature_missing_custom_node_clarify_feedback,
    _premature_workflow_schema_clarify_feedback,
    _render_batch_diff,
    _revision_candidate_retry_hint,
    _revision_rejected_candidate_message,
    _sentence_case,
    _summarize_precedent_packet,
    _synthesize_batch_repl_message,
    _terminal_answer_message,
    _total_landed_edit_count,
)
from .agent_edit.artifacts import (
    _CHAT_REASONING_MAX_DIAGS,
    _CHAT_REASONING_MAX_OPERATIONS,
    _CHAT_REASONING_MAX_STEPS,
    _compact_chat_change_details,
    _compact_diag_to_dict,
    _latest_session_candidate_payload,
    _read_turn_response_payload,
    _stamped_message_outcome,
    _stamped_turn_response_outcome,
    _trim_chat_text,
    _write_turn_chat_artifact,
)
from .agent_edit.stages.apply_summarize_audit import (
    _stage_apply_delta_impl,
    _stage_audit_impl,
    _stage_summarize_impl,
    _stage_summarize_v2_impl,
)
from .agent_edit.stages.batch_repl import _stage_agent_batch_repl_impl
from .agent_edit.stages.load_lower_validate_emit import (
    _stage_emit,
    _stage_load_python,
    _stage_lower,
    _stage_validate,
)
from .agent_edit.stages.revision import (
    _finalize_revision_evidence_with_candidate,
    _revision_evidence_artifact_payload,
    _revision_evidence_prompt_json,
    _revision_readonly_message,
    _revision_target_node_ids,
    _stage_revision_evidence,
    _stage_revision_readonly_report,
    _write_revision_evidence_artifact,
)
from .agent_edit.session_read import (
    _BUNDLE_MAX_FILE_BYTES,
    _BUNDLE_MAX_TOTAL_BYTES,
    _BUNDLE_TEXT_SUFFIXES,
    _conversation_with_candidate_reference,
    read_session_bundle,
    read_session_chat,
    read_session_json,
)
from vibecomfy.porting.edit.types import FieldChange
from .gates import (
    apply_stage_gate_updates,
    derive_gates,
    initialize_gates,
    update_state_match_gate,
)
from .provider import (
    AgentTurnResult,
    BatchTurnResult,
    MalformedModelJSON,
    MissingRequiredField,
    _latest_clarification_context,
    build_batch_messages,
    build_delta_messages,
    build_messages,
    ensure_sentence_message,
    run_agent_turn,
    run_agent_turn_batch,
    run_agent_turn_delta,
)
from .diagnostics import lower_stage_result, queue_stage_result
from .session import (
    allocate_turn,
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
)
from vibecomfy.executor.revision_evidence import (
    collect_graph_facts,
    collect_readiness_evidence,
    collect_topology_evidence,
    compute_scoped_diff,
)

_SESSION_ROOT = Path("out/editor_sessions")
DEFAULT_CHAT_DISPLAY_MESSAGES = 50
PROMPT_MEMORY_MESSAGES = 5
LOGGER = logging.getLogger(__name__)
_WARNED_LEGACY_CONTRACTS: set[str] = set()
_WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS: set[str] = set()


class _StageBlocked(Exception):
    def __init__(self, result: StageResult, failure: FailureEnvelope | None = None) -> None:
        super().__init__(result.stage)
        self.result = result
        self.failure = failure


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))
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
def _port_issue_to_dict(issue: Any) -> dict[str, Any]:
    to_json = getattr(issue, "to_json", None)
    if callable(to_json):
        rendered = to_json()
        if isinstance(rendered, dict):
            return rendered
    if isinstance(issue, Mapping):
        return dict(issue)
    return {"code": type(issue).__name__, "message": str(issue), "severity": "error"}


def _warn_legacy_contract_once(contract: str) -> None:
    if contract in _WARNED_LEGACY_CONTRACTS:
        return
    _WARNED_LEGACY_CONTRACTS.add(contract)
    LOGGER.warning(
        "agent-edit legacy contract '%s' selected via VIBECOMFY_AGENT_EDIT_LEGACY; "
        "this is deprecated and will be removed",
        contract,
    )


def _warn_ignored_public_protocol_envs_once(env_names: tuple[str, ...]) -> None:
    unseen = tuple(name for name in env_names if name not in _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS)
    if not unseen:
        return
    _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS.update(unseen)
    LOGGER.warning(
        "agent-edit ignoring legacy public protocol env vars (%s); product protocol is always "
        "'batch_repl'. For dev-only legacy protocols set "
        "VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS=1 and "
        "VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL=delta|full.",
        ", ".join(unseen),
    )


def _agent_edit_contract() -> str:
    ignored_public_envs = tuple(
        name
        for name in (
            "VIBECOMFY_AGENT_EDIT_LEGACY",
            "VIBECOMFY_AGENT_EDIT_V2",
            "VIBECOMFY_AGENT_EDIT_BATCH_REPL",
        )
        if os.getenv(name) is not None
    )
    if ignored_public_envs:
        _warn_ignored_public_protocol_envs_once(ignored_public_envs)
    if os.getenv("VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS") == "1":
        dev_protocol = os.getenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL")
        if dev_protocol in {"delta", "full"}:
            _warn_legacy_contract_once(dev_protocol)
            return dev_protocol
    return "batch_repl"


def _agent_edit_v2_enabled() -> bool:
    return _agent_edit_contract() == "delta"


def _agent_edit_batch_repl_enabled() -> bool:
    return _agent_edit_contract() == "batch_repl"


def _edit_lint_enabled() -> bool:
    """Return True unless VIBECOMFY_AGENT_EDIT_LINT is explicitly disabled.

    Accepts ``0``, ``false``, ``off``, or ``no`` (case-insensitive) as disabled
    values.  Defaults to ON (enabled) when the env var is unset or set to any
    other value.

    Rollout flag / off-switch
    -------------------------
    Setting ``VIBECOMFY_AGENT_EDIT_LINT=0`` disables the entire lint gate in
    ``_stage_apply_delta`` and ``_stage_agent_batch_repl``.  When lint is off the
    pipeline falls back to pre-lint behaviour: ``apply_delta()`` receives every
    op unchecked, no-ops are not pre-filtered, and diagnostics come from
    ``resolve_delta`` / ``apply_delta`` rather than from ``lint_delta()``.  This
    flag is intended as an emergency off-switch; the default path is *enabled*.
    """
    raw = os.getenv("VIBECOMFY_AGENT_EDIT_LINT")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "off", "no"}


def _record(context: TurnContext, result: StageResult) -> StageResult:
    context.stage_results[result.stage] = result
    apply_stage_gate_updates(context, result)
    return result


def _stamp_identity_on_original(graph: dict[str, Any], workflow: Any) -> int:
    """Phase 1 (concrete-tree migration): stamp the IR's stable uid onto the
    *original* UI nodes so the delta-scope guard (`guard_emit`) and pin-opaque
    can match on a user's FIRST edit. A hand-authored ComfyUI canvas carries no
    `properties.vibecomfy_uid`, so `guard_emit`'s scope (uids shared between the
    original and the candidate) is otherwise empty and the whole preserve/guard
    layer no-ops (blockers.md B12). The candidate inherits these same uids from
    the IR, so stamping the original makes the scope non-empty.

    See docs/agent-edit/concrete-tree.md. Match is by litegraph node id, which is
    stable across the round-trip.
    """
    by_id = {str(nid): node for nid, node in getattr(workflow, "nodes", {}).items()}
    stamped = 0
    for ui_node in graph.get("nodes") or []:
        if not isinstance(ui_node, dict):
            continue
        ir = by_id.get(str(ui_node.get("id")))
        uid = getattr(ir, "uid", "") if ir is not None else ""
        if not uid:
            continue
        props = ui_node.get("properties")
        if not isinstance(props, dict):
            props = {}
            ui_node["properties"] = props
        if not props.get("vibecomfy_uid"):
            props["vibecomfy_uid"] = uid
            stamped += 1
    return stamped


def _stale_rebaseline_recovery_issue(
    state: AgentEditState,
    gate_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "stale_state_recovery",
        "last_known_baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
        "client_structural_graph_hash": state.submitted_client_structural_graph_hash,
    }
    return {
        "code": "stale_state_mismatch",
        "severity": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "message": "Submitted graph no longer matches the current baseline.",
        "detail": dict(gate_evidence),
        "rebaseline_recovery": recovery,
    }


def _stage_ingest(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.layout_store import store_from_ui_json

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    original_ui_ref = write_json_artifact(state.original_ui_path, state.graph)
    state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
    state.prior_store = store_from_ui_json(state.graph)
    # Phase 1 (concrete-tree migration, docs/agent-edit/concrete-tree.md): give the
    # user's original graph stable identity so the delta-scope guard (guard_emit)
    # engages on the FIRST edit. Stamp a COPY — never mutate state.graph, which is
    # hashed/echoed/audited. The candidate inherits the same uids (verified: uid ==
    # node id, preserved across the scratchpad round-trip), so the guard scope
    # becomes non-empty.
    #
    # Gated OFF by default: with the guard engaged but the candidate still produced
    # by the LOSSY regeneration path (Phase 2 not yet landed), guard_emit correctly
    # refuses candidates that diverge from the original outside the intended delta.
    # Enabling identity is therefore only safe once Phase 2 (verbatim-preserve)
    # makes the candidate faithful. Toggle with VIBECOMFY_AGENT_EDIT_IDENTITY=1.
    if os.getenv("VIBECOMFY_AGENT_EDIT_IDENTITY") == "1":
        from copy import deepcopy as _deepcopy
        guard_original = _deepcopy(state.graph)
        _stamp_identity_on_original(guard_original, state.workflow)
        state.guard_original_ui = guard_original
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
    )


def _stage_ingest_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.ledger import EditLedger

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    # The EditLedger walks a UI ``nodes`` array. An API-format (compiled_api)
    # source has no ``nodes`` key, so every edit op would die on ``stale_graph_name``
    # ("uid no longer present"). When the source is not already UI format,
    # re-serialize the canonical VibeWorkflow (which ingests both formats) to a UI
    # envelope so the ledger sees the nodes. UI-format inputs already have ``nodes``
    # and are left untouched — re-serializing them is lossy and breaks the path that
    # already works. ``state.graph`` is hashed/echoed/audited, so all downstream
    # consumers share this one canonical view.
    from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape
    from vibecomfy.porting.emit.ui import emit_ui_json

    if detect_workflow_shape(state.graph) != "ui":
        state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
        state.graph = emit_ui_json(
            state.workflow,
            schema_provider=state.schema_provider,
            guard_original_ui=state.graph,
        )
    ledger = EditLedger.ingest(state.graph)
    state.guard_original_ui = ledger.stamped_copy()
    original_ui_ref = write_json_artifact(state.original_ui_path, state.guard_original_ui)
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
        issues=tuple(issue.to_dict() for issue in ledger.diagnostics),
        value={
            "mode": "agent_edit_v2_delta",
            "node_count": len(ledger.node_index),
            "scope_count": len(ledger.scopes),
        },
    )


def _stage_convert(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.convert import port_convert_and_write, port_convert_workflow

    start = time.monotonic()
    conversion = port_convert_workflow(
        state.workflow,
        source_path=str(state.original_ui_path),
        schema_provider=state.schema_provider,
        raw_workflow=state.graph,
        # Editing a user's live canvas must preserve every node. Dead-branch
        # pruning is for authoring minimal templates; here it would silently
        # drop nodes that don't feed a recognized output (e.g. a GeminiNode
        # feeding only a PreviewAny passthrough) and corrupt the round-trip.
        prune_dead_branches=False,
    )
    # Keep the strict parity gate: with prune disabled + UI-only passthrough
    # preservation (emitter), a faithful user canvas round-trips and passes here,
    # while a genuinely-lossy conversion still fails honestly rather than applying
    # a corrupted candidate.
    port_convert_and_write(conversion, state.before_py_path)
    state.python_before = state.before_py_path.read_text(encoding="utf-8")
    return StageResult(
        stage="convert",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.before_py_path),),
    )


def _stage_project_v2(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.projection import ProjectionOptions, render_edit_projection

    start = time.monotonic()
    # The 8000-token default forces sparse mode on every real ComfyUI graph (140-200+
    # nodes), collapsing all nodes to summaries and starving the model of the field
    # names / slot types it needs to target edits and wire links correctly. Modern
    # models have 64K+ context, so render real graphs in FULL detail. Env-overridable.
    try:
        _proj_budget = int(os.getenv("VIBECOMFY_EDIT_PROJECTION_MAX_TOKENS", "256000"))
    except (TypeError, ValueError):
        _proj_budget = 256000
    projection = render_edit_projection(
        state.guard_original_ui or state.graph,
        task=state.task,
        schema_provider=state.schema_provider,
        options=ProjectionOptions(max_tokens=_proj_budget),
    )
    state.projection_text = projection.text
    state.projection_path.write_text(projection.text, encoding="utf-8")
    return StageResult(
        stage="project",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.projection_path),),
        value={
            "token_estimate": projection.token_estimate,
            "node_count": projection.node_count,
            "detailed_node_count": projection.detailed_node_count,
            "truncated": projection.truncated,
        },
    )


def _stage_agent(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    start = time.monotonic()
    messages = build_messages(task=state.task, python_source=state.python_before, execution_mode="sandboxed_loose")
    write_json_artifact(state.model_request_path, {"messages": messages})
    if deepseek_client is not None:
        agent_result = _normalize_test_client_response(
            deepseek_client(messages)
        )
    else:
        agent_result = run_agent_turn(
            state.task,
            state.python_before,
            route=route,
            model=model,
        )
    state.python_after = agent_result.python
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    model_response_ref = write_json_artifact(
        state.model_response_path,
        agent_result.to_dict(),
    )
    return StageResult(
        stage="agent",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "provider_metadata": state.provider_metadata,
        },
    )


def _stage_agent_delta(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    from vibecomfy.porting.edit.ops import (
        EDIT_OP_RESPONSE_SCHEMA_V2,
        normalize_delta_test_client_response,
    )

    start = time.monotonic()
    messages = build_delta_messages(
        task=state.task,
        projection=state.projection_text,
        op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
    )
    write_json_artifact(
        state.model_request_path,
        {"messages": messages, "response_contract": "delta"},
    )
    if deepseek_client is not None:
        agent_result = normalize_delta_test_client_response(deepseek_client(messages))
    else:
        agent_result = run_agent_turn_delta(
            state.task,
            state.projection_text,
            op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
            route=route,
            model=model,
        )
    state.delta_ops = agent_result.delta
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    model_response_ref = write_json_artifact(
        state.model_response_path,
        agent_result.to_dict(),
    )
    return StageResult(
        stage="agent_delta",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "op_count": len(agent_result.delta),
            "provider_metadata": state.provider_metadata,
        },
    )


_RESEARCH_TRIGGER_TERMS = (
    "look up", "lookup", "research", "find out", "how does", "how do", "what is",
    "what are", "explain how", "how can", "how to", "information about",
)

_GRAPH_EXPLAIN_TRIGGER_TERMS = (
    "what's happening", "what is happening", "what's going on", "what is going on",
    "explain this graph", "explain the graph", "describe this graph",
    "describe the graph", "analyze this graph", "analyze the graph",
    "inspect this graph", "inspect the graph", "what does this graph do",
)

_CODE_NODE_TRIGGER_TERMS = (
    "code node",
    "python",
    "pil",
    "pillow",
    "custom image-processing",
    "custom image processing",
    "process images",
    "image processing",
)


def _task_mentions_any(task: str, terms: tuple[str, ...]) -> bool:
    lowered = task.lower()
    return any(term in lowered for term in terms)


def _is_research_intent(task: str) -> bool:
    return _task_mentions_any(task, _RESEARCH_TRIGGER_TERMS)


def _is_graph_explain_intent(task: str) -> bool:
    return _task_mentions_any(task, _GRAPH_EXPLAIN_TRIGGER_TERMS)


def _is_code_node_intent(task: str) -> bool:
    return _task_mentions_any(task, _CODE_NODE_TRIGGER_TERMS)


def _build_graph_report(graph: dict[str, Any] | None) -> str:
    """Legacy: build a compact text report from a raw ComfyUI graph dict.

    .. deprecated::
        The executor now handles graph inspection for **inspect** routes via
        :mod:`vibecomfy.executor.graph_inspection` (structured evidence +
        Markdown renderer).  This function is kept for internal agent-edit
        tests and for the batch-REPL prompt building when graph context is
        injected into edit (revise / adapt) operations.
    """
    if not graph:
        return "No graph attached."
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return "Empty graph (0 nodes)."

    lines: list[str] = []
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or node.get("type") or "Unknown"
        node_id = node.get("id", i)
        parts: list[str] = [f"[{node_id}] {ct}"]
        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and widgets:
            widget_parts = []
            for j, w in enumerate(widgets[:5]):
                if w is not None and str(w).strip():
                    widget_parts.append(f"w{j}={str(w)[:80]}")
            if widget_parts:
                parts.append("values=(" + ", ".join(widget_parts) + ")")
        inputs = node.get("inputs")
        if isinstance(inputs, list):
            slot_info = []
            for inp in inputs:
                if isinstance(inp, dict):
                    name = inp.get("name", "?")
                    link = inp.get("link")
                    slot_info.append(
                        f"{name}=linked({link})" if link is not None else f"{name}=open"
                    )
            if slot_info:
                parts.append("inputs=(" + "; ".join(slot_info[:6]) + ")")
        lines.append(" ".join(parts))

    links = graph.get("links")
    if isinstance(links, list) and links:
        edge_lines: list[str] = []
        for link in links[:40]:
            if isinstance(link, dict):
                src = link.get("origin_id", "?")
                tgt = link.get("target_id", "?")
                edge_lines.append(f"  {src} -> {tgt}")
            elif isinstance(link, list) and len(link) >= 4:
                edge_lines.append(f"  {link[1]} -> {link[3]}")
        if edge_lines:
            lines.append("Edges:")
            lines.extend(edge_lines)

    return f"{len(nodes)} node(s):\n" + "\n".join(lines)



def _build_precedent_adaptation_prompt(
    adaptation_plan: dict[str, Any] | None,
    precedent_slices: tuple[dict[str, Any], ...] = (),
) -> str:
    """Build a compact precedent adaptation prompt for batch REPL injection.

    Only invoked for the `precedent_research` route.  Includes anchors,
    required nodes/rewires, socket evidence, avoid patterns, and semantic
    checks from the structured adaptation plan, but never the full
    candidate_graph to avoid biasing the model toward a single solution.

    All precedent material is neutral context — it is NOT a winner,
    recommendation, or required implementation.  The adaptation agent
    evaluates all available slices independently.
    """
    if not adaptation_plan:
        return ""

    parts: list[str] = []

    # ── context note (neutrality disclaimer) ──
    context_note = adaptation_plan.get("context_note")
    if isinstance(context_note, str) and context_note.strip():
        parts.append(f"IMPORTANT: {context_note.strip()}")

    # ── selected slice (presentation context only — not a winner) ──
    selected_slice = adaptation_plan.get("selected_slice")
    if isinstance(selected_slice, dict):
        source_class = selected_slice.get("source_class_type", "")
        node_ids = selected_slice.get("node_ids") or []
        entry = selected_slice.get("entry_anchor")
        exit_ = selected_slice.get("exit_anchor")
        py_path = selected_slice.get("python_path")
        slice_desc = f"Source: {source_class}" if source_class else "Source: (unnamed)"
        if isinstance(node_ids, list) and node_ids:
            slice_desc += f", {len(node_ids)} node(s): [{', '.join(str(n) for n in node_ids[:8])}]"
            if len(node_ids) > 8:
                slice_desc += f" (+{len(node_ids) - 8} more)"
        if entry:
            slice_desc += f", entry_anchor={entry}"
        if exit_:
            slice_desc += f", exit_anchor={exit_}"
        if py_path:
            slice_desc += f", path={py_path}"
        parts.append(f"Reference slice (presentation context only — NOT a winner): {slice_desc}")

    # ── all available slices (neutral summary) ──
    all_slices = adaptation_plan.get("all_slices")
    if isinstance(all_slices, list) and all_slices:
        slice_summaries = []
        for i, s in enumerate(all_slices[:12]):
            if isinstance(s, dict):
                ct = s.get("source_class_type") or "unnamed"
                nids = s.get("node_ids") or []
                n = len(nids) if isinstance(nids, (list, tuple)) else 0
                entry_a = s.get("entry_anchor")
                exit_a = s.get("exit_anchor")
                desc = f"{ct} ({n} nodes"
                if entry_a:
                    desc += f", entry={entry_a}"
                if exit_a:
                    desc += f", exit={exit_a}"
                desc += ")"
                slice_summaries.append(desc)
        if slice_summaries:
            if len(all_slices) > 12:
                slice_summaries.append(f"(+{len(all_slices) - 12} more slices)")
            parts.append("All available precedent slices (neutral context): " + "; ".join(slice_summaries))

    # ── anchor bindings ──
    anchor_bindings = adaptation_plan.get("anchor_bindings")
    if isinstance(anchor_bindings, list) and anchor_bindings:
        binding_lines = []
        for b in anchor_bindings:
            if isinstance(b, dict):
                binding_lines.append(", ".join(f"{k} → {v}" for k, v in b.items()))
        if binding_lines:
            parts.append("Anchor bindings: " + "; ".join(binding_lines))

    # ── required new nodes ──
    required_new_nodes = adaptation_plan.get("required_new_nodes")
    if isinstance(required_new_nodes, list) and required_new_nodes:
        node_lines = []
        for n in required_new_nodes[:10]:
            if isinstance(n, dict):
                class_type = n.get("class_type") or n.get("type") or "node"
                node_id = n.get("id") or n.get("node_id") or "?"
                slot_info = ""
                inputs = n.get("inputs")
                if isinstance(inputs, dict):
                    slot_info = ", ".join(f"{k}={v}" for k, v in list(inputs.items())[:3])
                desc = f"{class_type}(id={node_id}"
                if n.get("widget_values"):
                    desc += f", values={json.dumps(n['widget_values'])[:80]}"
                if slot_info:
                    desc += f", inputs={{{slot_info}}}"
                desc += ")"
                node_lines.append(desc)
        if node_lines:
            parts.append("Required new nodes: " + "; ".join(node_lines))

    # ── required rewires ──
    required_rewires = adaptation_plan.get("required_rewires")
    if isinstance(required_rewires, list) and required_rewires:
        rewire_lines = []
        for r in required_rewires[:6]:
            if isinstance(r, dict):
                src = r.get("from") or r.get("source") or "?"
                tgt = r.get("to") or r.get("target") or "?"
                slot = r.get("slot") or r.get("input_slot") or ""
                desc = f"{src} → {tgt}"
                if slot:
                    desc += f".{slot}"
                rewire_lines.append(desc)
        if rewire_lines:
            parts.append("Required rewires: " + "; ".join(rewire_lines))

    # ── edit ops (compact) ──
    edit_ops = adaptation_plan.get("edit_ops")
    if isinstance(edit_ops, list) and edit_ops:
        op_lines = []
        for op in edit_ops[:6]:
            if isinstance(op, dict):
                op_kind = op.get("kind") or op.get("op") or "edit"
                op_target = op.get("target") or op.get("node_id") or "?"
                op_value = op.get("value")
                desc = f"{op_kind} {op_target}"
                if op_value is not None:
                    desc += f"={json.dumps(op_value)[:40]}"
                op_lines.append(desc)
        if op_lines:
            parts.append("Edit ops: " + "; ".join(op_lines))

    # ── socket evidence (from slices) ──
    if precedent_slices:
        socket_lines = []
        for s in precedent_slices[:4]:
            if isinstance(s, dict):
                class_type = s.get("source_class_type") or "node"
                entry = s.get("entry_anchor")
                exit_ = s.get("exit_anchor")
                node_ids = s.get("node_ids") or []
                desc = class_type
                if entry or exit_:
                    anchors = []
                    if entry:
                        anchors.append(f"in={entry}")
                    if exit_:
                        anchors.append(f"out={exit_}")
                    desc += f" ({', '.join(anchors)})"
                socket_lines.append(desc)
        if socket_lines:
            parts.append("Socket evidence (workflow slices): " + "; ".join(socket_lines))

    # ── avoid patterns (derived from structural validation) ──
    structural_val = adaptation_plan.get("structural_validation", "")
    if structural_val == "fail":
        parts.append("AVOID: structural validation FAILED — the precedent slice may not be structurally compatible. Prefer a different precedent or adapt conservatively.")
    elif structural_val == "advisory":
        parts.append("NOTE: structural validation has advisories — verify wiring compatibility before landing edits.")

    # ── semantic checks ──
    semantic_val = adaptation_plan.get("semantic_validation", "")
    if semantic_val == "pass":
        parts.append("Semantic validation: PASS — the adaptation is semantically sound.")
    elif semantic_val == "fail":
        parts.append("AVOID: semantic validation FAILED — the precedent may not produce the expected behavior. Consider an alternative.")
    elif semantic_val == "advisory":
        parts.append("Semantic validation advisories present — review model compatibility and slot types.")

    if not parts:
        return ""

    return "\n".join(parts)


def _route_blocks_apply(route: str | None) -> bool:
    """Return True when *route* forbids Apply eligibility.

    Non-applyable routes (clarify, respond, inspect, research) do not
    produce edits and must never carry a candidate, apply_eligible flag,
    or apply-eligibility payload.  Only revise and adapt are apply-eligible.
    """
    return _canonical_agent_edit_route(route) in {"clarify", "respond", "inspect", "research"}


def _canonical_agent_edit_route(route: str | None) -> str | None:
    """Normalize executor-facing route labels to the canonical vocabulary."""
    if not isinstance(route, str):
        return None
    normalized = route.strip()
    if not normalized:
        return None
    aliases = {
        "inspect_only": "inspect",
        "direct_edit": "revise",
        "diagnose_repair": "revise",
        "precedent_research": "adapt",
    }
    return aliases.get(normalized, normalized)


def _route_change_focus_label(route: str | None) -> str:
    """Return a short change-focus label for *route* when reporting edits.

    revise is a focused, targeted change — the label makes that
    explicit in user-facing summaries.
    """
    if _canonical_agent_edit_route(route) == "revise":
        return "Focused change"
    return ""


def _build_precedent_semantic_check_entries(
    state: "AgentEditState",
) -> list[dict[str, Any]]:
    """Build task-satisfaction entries from the precedent adaptation plan.

    Semantic and structural validation fields are mapped to task satisfaction
    entries with a satisfaction key of advisory (for advisory warnings)
    or not_evaluated (for fields the plan did not evaluate).  These entries
    provide route-level observability without blocking Apply or Queue.
    """
    plan = state.executor_adaptation_plan
    if not isinstance(plan, dict):
        return []

    entries: list[dict[str, Any]] = []

    structural_val = plan.get("structural_validation")
    if structural_val in ("pass", "fail", "advisory", "not_evaluated"):
        entries.append(
            {
                "check": "structural_validation",
                "status": structural_val,
                "satisfaction": structural_val if structural_val != "not_evaluated" else "not_evaluated",
                "description": _structural_validation_description(structural_val),
            }
        )

    semantic_val = plan.get("semantic_validation")
    if semantic_val in ("pass", "fail", "advisory", "not_evaluated"):
        entries.append(
            {
                "check": "semantic_validation",
                "status": semantic_val,
                "satisfaction": semantic_val if semantic_val != "not_evaluated" else "not_evaluated",
                "description": _semantic_validation_description(semantic_val),
            }
        )

    return entries


def _structural_validation_description(status: str) -> str:
    if status == "pass":
        return "Precedent slice is structurally compatible with the current graph."
    if status == "fail":
        return "Precedent slice has structural incompatibilities — adapt conservatively."
    if status == "advisory":
        return "Precedent slice has structural advisories — verify wiring compatibility."
    return "Structural validation was not evaluated for the precedent slice."


def _semantic_validation_description(status: str) -> str:
    if status == "pass":
        return "Precedent adaptation is semantically sound."
    if status == "fail":
        return "Precedent may not produce expected behavior — consider alternatives."
    if status == "advisory":
        return "Semantic advisories present — review model compatibility and slot types."
    return "Semantic validation was not evaluated for the precedent adaptation."


def _schema_provider_available(schema_provider: Any) -> bool:
    if schema_provider is None:
        return False
    schemas = getattr(schema_provider, "schemas", None)
    if callable(schemas):
        try:
            return bool(schemas())
        except Exception:
            return False
    get_schema = getattr(schema_provider, "get_schema", None)
    return callable(get_schema)


def _schema_provider_has_class(schema_provider: Any, class_type: str) -> bool:
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema):
        return False
    try:
        return get_schema(class_type) is not None
    except Exception:
        return False


def _graph_class_types_missing_from_schema(
    graph: Mapping[str, Any] | None,
    schema_provider: Any,
) -> tuple[str, ...]:
    if not isinstance(graph, Mapping):
        return ()
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return ()
    missing: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        raw = node.get("class_type") or node.get("type")
        class_type = str(raw or "").strip()
        if not class_type or class_type == "Unknown" or class_type in seen:
            continue
        seen.add(class_type)
        if not _schema_provider_has_class(schema_provider, class_type):
            missing.append(class_type)
    return tuple(missing)


def _candidate_dict(candidate: Any) -> dict[str, Any] | None:
    if isinstance(candidate, Mapping):
        return dict(candidate)
    to_dict = getattr(candidate, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return dict(value)
    return None


def _resolver_candidate_supports_class(
    candidate: Mapping[str, Any],
    class_type: str,
) -> bool:
    expected = candidate.get("expected_classes")
    if isinstance(expected, (list, tuple)) and class_type in {str(item) for item in expected}:
        return True
    schema_payload = candidate.get("provisional_schema")
    if isinstance(schema_payload, Mapping):
        raw_schema = schema_payload.get("schema")
        if isinstance(raw_schema, Mapping):
            nodes = raw_schema.get("nodes") or raw_schema.get("object_info") or raw_schema
            return isinstance(nodes, Mapping) and class_type in nodes
    return False


def _hydrate_current_graph_unknown_node_schemas(state: AgentEditState) -> tuple[dict[str, Any], ...]:
    missing_classes = _graph_class_types_missing_from_schema(state.graph, state.schema_provider)
    if not missing_classes:
        return ()

    try:
        from vibecomfy.registry.pack_resolver import resolve_missing_nodes
        from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider
    except Exception as exc:  # noqa: BLE001 - registry hydration is best-effort
        LOGGER.debug("registry schema hydration unavailable: %s", exc)
        return ()

    candidates: list[dict[str, Any]] = []
    for class_type in missing_classes:
        try:
            resolution = resolve_missing_nodes(class_type, query_intent="class_name")
        except Exception as exc:  # noqa: BLE001 - keep existing blocker on lookup failure
            LOGGER.debug("registry schema hydration failed for %s: %s", class_type, exc)
            continue
        for raw_candidate in getattr(resolution, "candidates", ()) or ():
            candidate = _candidate_dict(raw_candidate)
            if candidate is None:
                continue
            if not _resolver_candidate_supports_class(candidate, class_type):
                continue
            candidates.append(candidate)

    new_candidates = [
        candidate
        for candidate in candidates
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return ()
    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
    if not provisional.schemas():
        return ()
    state.provisional_registry_candidate_hashes = frozenset(
        {
            *state.provisional_registry_candidate_hashes,
            *(_candidate_stable_key(candidate) for candidate in new_candidates),
        }
    )
    state.schema_provider = CompositeSchemaProvider(provisional, state.schema_provider)
    return tuple(new_candidates)


def _revision_no_candidate_reason(evidence: RevisionEvidence) -> str | None:
    if evidence.safe_candidate_possible:
        return None
    if evidence.topology.missing_graph:
        return "no_graph"
    return "no_changes"


def _executor_classification_text(state: AgentEditState) -> str:
    classification = state.request_payload.get("executor_classification")
    if isinstance(classification, Mapping):
        return " ".join(
            str(classification.get(key) or "")
            for key in ("plan_summary", "intent", "route", "task")
        )
    return ""


def _effective_implementation_task(state: AgentEditState) -> str:
    classification_text = _executor_classification_text(state).strip()
    if not classification_text:
        return state.task
    return (
        f"{state.task}\n\n"
        "Resolved executor plan/context:\n"
        f"{classification_text}"
    )


def _runtime_code_additive_request(state: AgentEditState) -> bool:
    classification_text = _executor_classification_text(state)
    task = (
        f"{state.task} {state.request_payload.get('query') or ''} "
        f"{classification_text}"
    ).lower()
    return (
        (
            "code node" in task
            or "runtime code" in task
            or "vibecomfy.exec" in task
            or "imagecode" in task
            or ("pil" in task and "transformation" in task)
        )
        and ("pil" in task or "image" in task or "frame" in task or "process" in task)
    )


def _executor_requested_implementation(state: AgentEditState) -> bool:
    classification = state.request_payload.get("executor_classification")
    if isinstance(classification, Mapping) and "implement" in classification:
        return bool(classification.get("implement"))
    return _canonical_agent_edit_route(state.route) in {"revise", "adapt", "dev"}


def _state_runtime_execution_requested(state: AgentEditState) -> bool:
    runtime = state.request_payload.get("runtime")
    return isinstance(runtime, Mapping) and bool(runtime.get("execution_requested"))


def _empty_graph_authoring_request(state: AgentEditState) -> bool:
    evidence = state.revision_evidence
    if evidence is None or not evidence.topology.missing_graph:
        return False
    if _state_runtime_execution_requested(state):
        return False
    return _executor_requested_implementation(state)


_TEXT_TO_IMAGE_SEED_TYPES = (
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)


def _seed_focus_types_for_authoring(state: AgentEditState) -> set[str]:
    task = _effective_implementation_task(state).lower()
    if not _empty_graph_authoring_request(state):
        return set()
    if (
        "sd1.5" in task
        or "sd 1.5" in task
        or "sd15" in task
        or "stable diffusion" in task
        or "text-to-image" in task
        or "text to image" in task
    ):
        return set(_TEXT_TO_IMAGE_SEED_TYPES)
    return set()


def _focus_types_from_research_brief(brief: Mapping[str, Any] | None) -> set[str]:
    """Pull likely node/class names out of the executor research brief.

    The classifier often emits search directions like
    ``"Hotshot ComfyUI custom nodes"``.  Surfacing those capitalized tokens in
    the turn-0 signature catalog lets the agent discover a local schema hit
    (e.g. the ``Hotshot`` stub) before falling back to noisy web/registry
    research.
    """
    if not brief:
        return set()
    candidates: set[str] = set()
    for key in ("search_directions", "model_families"):
        values = brief.get(key)
        if not isinstance(values, (list, tuple)):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            for token in value.split():
                token = token.strip(".,;:\"'")
                if (
                    token
                    and token[0].isupper()
                    and len(token) >= 2
                    and token.isascii()
                ):
                    candidates.add(token)
            # Also keep the leading phrase word as a likely brand/class name.
            parts = value.split()
            if parts and parts[0] and parts[0][0].isupper():
                candidates.add(parts[0].strip(".,;:\"'"))
    return candidates


def _can_attempt_local_additive_revise(state: AgentEditState) -> bool:
    evidence = state.revision_evidence
    if evidence is None:
        return False
    topology = evidence.topology
    readiness = evidence.readiness
    if _empty_graph_authoring_request(state):
        if topology.dangling_links or topology.absent_endpoint_nodes:
            return False
        if readiness.no_gpu_detected or readiness.validation_errors or readiness.readiness_blockers:
            return False
        return True
    if not _runtime_code_additive_request(state):
        return False
    if topology.missing_graph or topology.dangling_links or topology.absent_endpoint_nodes:
        return False
    if readiness.no_gpu_detected or readiness.validation_errors or readiness.readiness_blockers:
        return False
    return bool(
        topology.unknown_class_types
        or topology.missing_required_inputs
        or readiness.missing_models
        or readiness.missing_node_packs
    )


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




def _stage_agent_batch_repl(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    return _stage_agent_batch_repl_impl(
        state,
        context,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
        client_id=client_id,
        conversation_messages=conversation_messages,
    )


def _stage_apply_delta(state: AgentEditState, _context: TurnContext) -> StageResult:
    return _stage_apply_delta_impl(state, _context)


def _stage_summarize(state: AgentEditState, context: TurnContext) -> StageResult:
    return _stage_summarize_impl(state, context)


def _stage_summarize_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    return _stage_summarize_v2_impl(state, context)


def _stage_audit(
    state: AgentEditState,
    context: TurnContext,
    *,
    response: dict[str, Any] | None = None,
    failure: FailureEnvelope | None = None,
) -> ArtifactRef:
    return _stage_audit_impl(state, context, response=response, failure=failure)


def _write_unknown_transition_audits(
    *,
    session_root: Path,
    session_id: str,
    baseline_turn_id: str | None,
    unknown_transitions: tuple[dict[str, Any], ...],
    request_payload: Mapping[str, Any],
) -> None:
    for transition in unknown_transitions:
        turn_id = transition.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        try:
            write_audit(
                turn_dir_for(session_root, session_id, turn_id) / "unknown_audit",
                context=TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    baseline_turn_id=baseline_turn_id,
                ),
                turn_state="unknown",
                artifacts={"request": dict(request_payload)},
                metadata={"action": "unknown", **transition},
            )
        except Exception:
            continue


def _failure_response(
    state: AgentEditState,
    context: TurnContext,
    failure: FailureEnvelope,
    *,
    contract: str = "batch_repl",
) -> dict[str, Any]:
    if contract != "batch_repl":
        return _build_dev_failure_response(state, context, failure=failure)
    return _build_batch_repl_failure_response(state, context, failure=failure)


def _validated_agent_edit_response(
    response: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    try:
        return ensure_agent_edit_response_contract(response, stage=stage)
    except Exception as exc:
        fallback = _product_failure_response(
            failure_envelope(
                FailureKind.VALIDATION_ERROR,
                stage,
                agent_failure_context={
                    "explanation": (
                        "Agent edit response contract validation failed before return: "
                        f"{exc}"
                    )
                },
            )
        )
        return ensure_agent_edit_response_contract(fallback, stage=stage)


def _product_failure_response(failure: AgentError) -> dict[str, Any]:
    response = failure.to_dict()
    response.update(product_failure_envelope_fields(failure))
    return response


def _build_compatibility_response_fields(state: AgentEditState) -> dict[str, Any]:
    candidate_graph_hash = payload_hash(state.ui_payload)
    candidate_structural_graph_hash = structural_graph_hash(state.ui_payload)
    return {
        "baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "submitted_client_graph_hash": state.submitted_client_graph_hash,
        "submitted_client_structural_graph_hash": state.submitted_client_structural_graph_hash,
        "candidate_graph_hash": candidate_graph_hash,
        "candidate_structural_graph_hash": candidate_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
    }


def _build_candidate_payload(
    state: AgentEditState,
    *,
    compatibility_fields: Mapping[str, Any],
    has_candidate: bool,
    turn_identity: TurnIdentity,
) -> dict[str, Any] | None:
    if not has_candidate:
        return None
    candidate = ApplyCandidate(
        state="candidate",
        graph=state.ui_payload or {},
        graph_hash=compatibility_fields["candidate_graph_hash"],
        structural_graph_hash=compatibility_fields["candidate_structural_graph_hash"],
        baseline_graph_hash=compatibility_fields["baseline_graph_hash"],
        submit_graph_hash=compatibility_fields["submit_graph_hash"],
        submit_structural_graph_hash=compatibility_fields["submit_structural_graph_hash"],
        turn_identity=turn_identity,
    )
    return candidate.to_dict()


def _stage_snapshot_payloads(context: TurnContext) -> list[dict[str, Any]]:
    snapshots = tuple(
        StageSnapshot.from_stage_result(result)
        for result in context.stage_results.values()
    )
    return [snapshot.to_dict() for snapshot in snapshots]


def _resolver_candidates_from_batch_turns(state: AgentEditState) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for turn in state.batch_turns:
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue
            raw_candidates = detail.get("resolver_candidates")
            if not isinstance(raw_candidates, list):
                continue
            for raw_candidate in raw_candidates:
                if not isinstance(raw_candidate, Mapping):
                    continue
                candidate = dict(raw_candidate)
                key = (
                    str(candidate.get("stable_install_hash") or "")
                    or json.dumps(candidate, sort_keys=True, default=str)
                )
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(candidate)
    return candidates


def _resolver_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for statement in getattr(batch_result, "statements", ()) or ():
        detail = getattr(statement, "detail", None)
        if not isinstance(detail, Mapping):
            continue
        raw_candidates = detail.get("resolver_candidates")
        if not isinstance(raw_candidates, list):
            continue
        for raw_candidate in raw_candidates:
            if isinstance(raw_candidate, Mapping):
                candidates.append(dict(raw_candidate))
    return candidates


def _workflow_schema_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for statement in getattr(batch_result, "statements", ()) or ():
        detail = getattr(statement, "detail", None)
        if not isinstance(detail, Mapping):
            continue
        raw_candidates = detail.get("workflow_schema_candidates")
        if not isinstance(raw_candidates, list):
            continue
        for raw_candidate in raw_candidates:
            if isinstance(raw_candidate, Mapping):
                candidates.append(dict(raw_candidate))
    return candidates


def _candidate_stable_key(candidate: Mapping[str, Any]) -> str:
    return (
        str(candidate.get("stable_install_hash") or "")
        or json.dumps(dict(candidate), sort_keys=True, default=str)
    )


def _enrich_schema_provider_from_resolver_candidates(
    state: AgentEditState,
    session: Any,
    candidates: list[dict[str, Any]],
) -> None:
    new_candidates = [
        candidate
        for candidate in candidates
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return
    from vibecomfy.schema import CompositeSchemaProvider, ProvisionalRegistrySchemaProvider

    provisional = ProvisionalRegistrySchemaProvider(new_candidates)
    if not provisional.schemas():
        return
    state.provisional_registry_candidate_hashes = frozenset(
        {
            *state.provisional_registry_candidate_hashes,
            *(_candidate_stable_key(candidate) for candidate in new_candidates),
        }
    )
    enriched = CompositeSchemaProvider(provisional, session.schema_provider)
    session.schema_provider = enriched
    state.schema_provider = enriched


def _legacy_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    derive_gates(
        context,
        baseline_graph_hash=state.baseline_graph_hash,
        client_graph_hash=state.submit_structural_graph_hash,
    )
    failure = dataclasses.replace(
        failure,
        canvas_apply_allowed=context.canvas_apply_allowed,
        queue_allowed=context.queue_allowed,
    )
    try:
        audit_ref = _stage_audit(state, context, failure=failure)
        failure = dataclasses.replace(failure, audit_ref=audit_ref)
    except Exception as audit_exc:
        failure = dataclasses.replace(failure, audit_error=str(audit_exc))
    response = failure.to_dict()
    if failure.kind is FailureKind.STALE_STATE_MISMATCH:
        eligibility = derive_apply_eligibility(
            context,
            live_structural_graph_hash=state.baseline_graph_hash,
            submit_structural_graph_hash=state.submit_structural_graph_hash,
        )
    else:
        eligibility = derive_apply_eligibility(context, has_candidate=False)
    response.update(
        {
            "eligibility": eligibility.to_dict(),
            "canvas_apply_allowed": context.canvas_apply_allowed,
            "queue_allowed": context.queue_allowed,
        }
    )
    response = build_legacy_agent_edit_v1(response)
    response.update(product_failure_envelope_fields(failure))
    failure_context = response.get("agent_failure_context")
    issues = failure_context.get("issues") if isinstance(failure_context, Mapping) else None
    if isinstance(issues, list):
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            recovery = issue.get("rebaseline_recovery")
            if isinstance(recovery, Mapping):
                response["rebaseline_recovery"] = dict(recovery)
                break
    response["internal_outcome"] = TurnOutcome.from_failure(failure).to_dict()
    return response


def _build_batch_repl_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    response = _legacy_failure_response(state, context, failure=failure)
    compatibility_fields = _build_compatibility_response_fields(state)
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    response["eligibility"] = response["apply_eligibility"]
    response["message"] = _synthesize_batch_repl_message(state, failure=failure)
    response["debug"] = {
        **response["debug"],
        "gates": context.gate_snapshot(),
        "hashes": dict(compatibility_fields),
    }
    return response


def _build_dev_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    response = _legacy_failure_response(state, context, failure=failure)
    response.update(_build_compatibility_response_fields(state))
    response.update(_session_artifact_response_fields(state))
    return response


def _session_artifact_response_fields(state: AgentEditState) -> dict[str, Any]:
    response_path = state.turn_dir / "response.json"
    return {
        "session_path": str(state.session_dir),
        "session_path_resolved": str(state.session_dir.resolve()),
        "detail_json_path": str(response_path),
        "detail_json_path_resolved": str(response_path.resolve()),
    }


def _build_batch_repl_response(
    state: AgentEditState,
    context: TurnContext,
) -> dict[str, Any]:
    turn_identity = TurnIdentity.from_context(context)
    stage_snapshots = _stage_snapshot_payloads(context)
    canonical_route = _canonical_agent_edit_route(state.route)
    route_blocks_apply = _route_blocks_apply(state.route)
    has_candidate = (
        state.batch_exit_mode in {_BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_DONE}
        and _batch_candidate_graph_changed(state)
    )
    if (
        _canonical_agent_edit_route(state.route) == "revise"
        and (
            state.revision_evidence is None
            or state.revision_evidence.scoped_diff is None
            or state.revision_evidence.candidate_eligible is not True
        )
    ):
        has_candidate = False
    if route_blocks_apply:
        has_candidate = False
    compatibility_fields = _build_compatibility_response_fields(state)
    response_apply_eligibility = derive_apply_eligibility(
        context,
        has_candidate=has_candidate,
        candidate_state="candidate",
    )
    # inspect and clarify routes cannot be Apply-eligible.
    if route_blocks_apply:
        response_apply_eligibility = ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message=f"Apply is not available for {state.route} routes.",
        )
    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
        apply_eligibility=response_apply_eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed if has_candidate else False,
        queue_allowed=context.queue_allowed if has_candidate else False,
    )
    candidate_payload = _build_candidate_payload(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
        turn_identity=turn_identity,
    )
    resolver_candidates = _resolver_candidates_from_batch_turns(state)
    missing_custom_nodes_terminal = (
        state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
        and bool(resolver_candidates)
    )
    if missing_custom_nodes_terminal:
        internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    elif route_blocks_apply and canonical_route != "clarify":
        internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY:
        internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY:
        question = state.user_message or None
        internal_outcome = TurnOutcome.edit_and_clarify(
            changes=_real_field_changes(state.batch_field_changes),
            question=question,
        )
    elif state.batch_exit_mode == _BATCH_EXIT_DONE:
        internal_outcome = TurnOutcome.edit(changes=_real_field_changes(state.batch_field_changes))
    elif state.batch_exit_mode == _BATCH_EXIT_BUDGET:
        internal_outcome = TurnOutcome.budget(reason=state.batch_final_summary or None)
    else:
        internal_outcome = TurnOutcome.noop(
            reason=state.batch_done_summary or state.user_message or None
        )
    if missing_custom_nodes_terminal:
        public_outcome = {
            "kind": "requires_custom_nodes",
            "candidates": resolver_candidates,
            "warnings": [],
        }
    else:
        public_outcome = public_outcome_from_turn_outcome(
            internal_outcome,
            response={"candidate": candidate_payload},
        )
    if internal_outcome.kind == "edit":
        message = ensure_sentence_message(
            state.user_message,
            fallback="I made the requested workflow changes.",
        )
    else:
        message = _synthesize_batch_repl_message(state, outcome=internal_outcome)
    change_details = _change_details_payload(state, context)
    response.update(
        turn_envelope(
            message=message,
            outcome=public_outcome,
            candidate=candidate_payload,
            eligibility=response_apply_eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
                "turn_identity": turn_identity.to_dict(),
                "stage_snapshots": stage_snapshots,
                "batch_repl": {
                    "turn_count": state.batch_turn_count,
                    "exit_mode": state.batch_exit_mode,
                    "done_summary": state.batch_done_summary,
                    "final_summary": state.batch_final_summary,
                    "budget_state": _json_safe(state.batch_budget_state),
                },
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    response["change_details"] = change_details
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    if canonical_route:
        response["route"] = canonical_route
    if canonical_route == "research":
        response["graph_unchanged"] = True
        response["no_candidate_reason"] = "route_not_applyable"
    if state.batch_exit_mode in {_BATCH_EXIT_PURE_CLARIFY, _BATCH_EXIT_EDIT_CLARIFY} and not missing_custom_nodes_terminal:
        response["clarification_required"] = True
        response["graph_unchanged"] = state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
    elif missing_custom_nodes_terminal:
        response["graph_unchanged"] = True
        response["no_candidate_reason"] = "route_not_applyable"
    elif state.batch_exit_mode == _BATCH_EXIT_NOOP:
        response["graph_unchanged"] = True
        if state.batch_done_summary:
            response["done_summary"] = state.batch_done_summary
    elif state.batch_done_summary:
        response["done_summary"] = state.batch_done_summary
    response["batch_turns"] = _json_safe(state.batch_turns)
    # adapt carries semantic checks as advisory/not_evaluated.
    if _canonical_agent_edit_route(state.route) == "adapt":
        semantic_entries = _build_precedent_semantic_check_entries(state)
        if semantic_entries:
            response.setdefault("task_satisfaction", []).extend(semantic_entries)
    # revise reports change focus.
    change_focus = _route_change_focus_label(state.route)
    if change_focus:
        response["change_focus"] = change_focus
    built_response = build_legacy_agent_edit_v1(
        {
            **response,
            "canvas_apply_allowed": context.canvas_apply_allowed if has_candidate else False,
            "queue_allowed": context.queue_allowed if has_candidate else False,
        }
    )
    if missing_custom_nodes_terminal:
        return _strip_clarify_forbidden_response_fields(built_response)
    return _sanitize_pure_clarify_response(built_response)


def _build_dev_success_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    contract: str,
) -> dict[str, Any]:
    turn_identity = TurnIdentity.from_context(context)
    stage_snapshots = _stage_snapshot_payloads(context)
    compatibility_fields = _build_compatibility_response_fields(state)
    eligibility = derive_apply_eligibility(
        context,
        has_candidate=True,
        candidate_state="candidate",
    )
    # inspect and clarify routes cannot be Apply-eligible.
    if _route_blocks_apply(state.route):
        eligibility = ApplyEligibility(
            applyable=False,
            reason="no_candidate",
            message=f"Apply is not available for {state.route} routes.",
        )
    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
        apply_eligibility=eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed,
        queue_allowed=context.queue_allowed,
    )
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    # No-candidate routes (inspect, clarify) must not produce a
    # candidate outcome or candidate payload even in dev/delta paths.
    if _route_blocks_apply(state.route):
        has_candidate = False
        if _canonical_agent_edit_route(state.route) == "clarify":
            internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
        else:
            internal_outcome = TurnOutcome.noop(reason=state.user_message or None)
    else:
        has_candidate = True
        internal_outcome = TurnOutcome.edit()
    candidate_payload = _build_candidate_payload(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
        turn_identity=turn_identity,
    )
    response.update(
        turn_envelope(
            message=state.user_message,
            outcome=public_outcome_from_turn_outcome(
                internal_outcome,
                response={"candidate": candidate_payload} if has_candidate else None,
            ),
            candidate=candidate_payload,
            eligibility=eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
                "turn_identity": turn_identity.to_dict(),
                "stage_snapshots": stage_snapshots,
                "contract": contract,
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    if contract == "delta":
        from vibecomfy.porting.edit.ops import op_to_dict

        response["delta_ops"] = [op_to_dict(op) for op in state.delta_ops]
    # adapt carries semantic checks as advisory/not_evaluated.
    if _canonical_agent_edit_route(state.route) == "adapt":
        semantic_entries = _build_precedent_semantic_check_entries(state)
        if semantic_entries:
            response.setdefault("task_satisfaction", []).extend(semantic_entries)
    # revise reports change focus.
    change_focus = _route_change_focus_label(state.route)
    if change_focus:
        response["change_focus"] = change_focus
    return _sanitize_pure_clarify_response(
        build_legacy_agent_edit_v1(
            {
                **response,
                "canvas_apply_allowed": context.canvas_apply_allowed if has_candidate else False,
                "queue_allowed": context.queue_allowed if has_candidate else False,
            }
        )
    )


def _run_stage(
    name: str,
    state: AgentEditState,
    context: TurnContext,
    fn: Callable[..., StageResult],
    *args: Any,
    **kwargs: Any,
) -> StageResult:
    try:
        result = fn(state, context, *args, **kwargs)
    except Exception as exc:
        failure_stage = (
            "agent_response"
            if name in {"agent", "agent_delta"}
            or (name in {"agent_batch", "agent_batch_repl"} and _is_provider_exception(exc))
            else name
        )
        failure = classify_failure(failure_stage, exc, context)
        result = StageResult(
            stage=name,
            ok=False,
            blocking=True,
            issues=(failure.agent_failure_context,),
        )
        _record(context, result)
        raise _StageBlocked(result, failure) from exc
    _record(context, result)
    if result.blocking:
        failure_kind = None
        if isinstance(result.value, dict):
            failure_kind = result.value.get("failure_kind")
        public_stage = name
        issue_codes = {
            str(issue.get("code"))
            for issue in result.issues
            if isinstance(issue, dict) and issue.get("code") is not None
        }
        diagnostic_codes: set[str] = set()
        if name == "agent_batch_repl":
            for turn in state.batch_turns:
                if not isinstance(turn, Mapping):
                    continue
                diagnostics = list(turn.get("diagnostics") or [])
                for statement in turn.get("statements") or []:
                    if isinstance(statement, Mapping):
                        diagnostics.extend(statement.get("diagnostics") or [])
                diagnostic_codes.update(
                    str(diagnostic.get("code"))
                    for diagnostic in diagnostics
                    if isinstance(diagnostic, Mapping) and diagnostic.get("code") is not None
                )
        parse_or_query_codes = {
            "batch_syntax_error",
            "nested_call_not_allowed",
            "unsupported_query_call",
        }
        if (
            name == "agent_batch_repl"
            and "batch_budget_exhausted" in issue_codes
            and not diagnostic_codes.intersection(parse_or_query_codes)
        ):
            public_stage = "agent_batch"
        failure = failure_envelope(
            failure_kind or FailureKind.VALIDATION_ERROR,
            public_stage,
            context,
            agent_failure_context={
                "explanation": f"Stage {public_stage} blocked the agent edit.",
                "issues": [dict(issue) for issue in result.issues if isinstance(issue, dict)],
            },
        )
        if failure.kind is FailureKind.STALE_STATE_MISMATCH and public_stage in {"ingest", "ingest_v2"}:
            failure = dataclasses.replace(
                failure,
                user_facing_message=(
                    "The canvas changed since the current backend baseline. "
                    "Rebaseline and resubmit from the current canvas."
                ),
            )
        raise _StageBlocked(result, failure)
    return result


def _is_provider_exception(exc: Exception) -> bool:
    provider_exception_names = {
        "AuthError",
        "MalformedModelJSON",
        "MissingRequiredField",
        "ProviderError",
    }
    return any(type_.__name__ in provider_exception_names for type_ in type(exc).__mro__)


def _run_batch_repl_product_path(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> AgentEditState:
    _run_stage("ingest", state, context, _stage_ingest_v2)
    _run_stage(
        "revision_evidence",
        state,
        context,
        _stage_revision_evidence,
        route=state.route,
        conversation_messages=conversation_messages,
    )
    if (
        state.revision_evidence is not None
        and not state.revision_evidence.safe_candidate_possible
        and not _can_attempt_local_additive_revise(state)
    ):
        _run_stage(
            "agent_batch",
            state,
            context,
            _stage_revision_readonly_report,
            route=state.route,
            conversation_messages=conversation_messages,
        )
        return state
    _run_stage(
        "agent_batch",
        state,
        context,
        _stage_agent_batch_repl,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
        client_id=client_id,
        conversation_messages=conversation_messages,
    )
    _run_stage("summarize", state, context, _stage_summarize_v2)
    return state


def _run_delta_dev_path(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> AgentEditState:
    _run_stage("ingest", state, context, _stage_ingest_v2)
    _run_stage("project", state, context, _stage_project_v2)
    _run_stage(
        "agent_delta",
        state,
        context,
        _stage_agent_delta,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
    )
    _run_stage("apply_delta", state, context, _stage_apply_delta)
    _run_stage("summarize", state, context, _stage_summarize_v2)
    return state


def _run_full_dev_path(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> AgentEditState:
    _run_stage("ingest", state, context, _stage_ingest)
    _run_stage("convert", state, context, _stage_convert)
    _run_stage(
        "agent",
        state,
        context,
        _stage_agent,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
    )
    _run_stage("load_python", state, context, _stage_load_python)
    _run_stage("lower", state, context, _stage_lower)
    _run_stage("validate", state, context, _stage_validate)
    _run_stage("emit", state, context, _stage_emit)
    _run_stage("summarize", state, context, _stage_summarize)
    return state


_RUNTIME_OBJECT_INFO_PATH: list[str] = []


def _build_object_info_in_process() -> dict[str, Any] | None:
    """Build ComfyUI /object_info IN-PROCESS from the live node registry.

    Mirrors ComfyUI server.py's ``node_info`` builder. We must NOT fetch /object_info
    over HTTP here: the agent-edit turn runs inside ComfyUI's event loop, so a blocking
    self-request deadlocks (the server can't answer while the loop is blocked) and times
    out, silently degrading to an empty schema provider. Reading the in-memory mappings
    avoids the loop entirely.
    """
    try:
        import nodes as comfy_nodes_registry  # ComfyUI global registry
    except Exception:
        return None
    mappings = getattr(comfy_nodes_registry, "NODE_CLASS_MAPPINGS", None)
    if not isinstance(mappings, dict) or not mappings:
        return None
    display = getattr(comfy_nodes_registry, "NODE_DISPLAY_NAME_MAPPINGS", {}) or {}
    out: dict[str, Any] = {}
    for name, cls in mappings.items():
        try:
            getv1 = getattr(cls, "GET_NODE_INFO_V1", None)
            if callable(getv1) and getattr(cls, "GET_NODE_INFO_V1", None) is not None:
                try:
                    out[name] = getv1()
                    continue
                except Exception:
                    pass
            info: dict[str, Any] = {}
            info["input"] = cls.INPUT_TYPES()
            rt = list(getattr(cls, "RETURN_TYPES", []) or [])
            info["output"] = rt
            info["output_name"] = list(getattr(cls, "RETURN_NAMES", rt) or rt)
            info["output_is_list"] = list(getattr(cls, "OUTPUT_IS_LIST", [False] * len(rt)) or [])
            info["name"] = name
            info["display_name"] = display.get(name, name)
            info["output_node"] = bool(getattr(cls, "OUTPUT_NODE", False))
            out[name] = info
        except Exception:
            # Some INPUT_TYPES() raise (missing models, etc.); skip those classes.
            continue
    return out or None


def _default_runtime_schema_provider() -> Any:
    """Schema provider for live edit turns: the LIVE in-process ComfyUI registry.

    The offline ``local`` provider reads an out/cache snapshot that is empty in a bare
    ComfyUI checkout, so it knows ZERO classes — which makes ``add_node`` reject every
    class as ``unknown_add_node_class_type`` (even a perfectly-installed ``PreviewImage``).
    ``RuntimeSchemaProvider`` (HTTP) can't be used here: it's either blocked inside the
    event loop, or a self-request deadlocks. So we build object_info IN-PROCESS from
    ``nodes.NODE_CLASS_MAPPINGS`` once, cache it to a temp file, and return the synchronous
    file-backed ``ObjectInfoSchemaProvider``. Falls back to ``local`` only if the registry
    is unavailable (i.e. not running inside ComfyUI).
    """
    from vibecomfy.schema import get_authoring_schema_provider, get_schema_provider

    try:
        if not (_RUNTIME_OBJECT_INFO_PATH and Path(_RUNTIME_OBJECT_INFO_PATH[0]).is_file()):
            data = _build_object_info_in_process()
            if data:
                import tempfile

                fd, path = tempfile.mkstemp(prefix="vibecomfy_object_info_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                _RUNTIME_OBJECT_INFO_PATH[:] = [path]
        if _RUNTIME_OBJECT_INFO_PATH:
            from vibecomfy.schema.provider import ObjectInfoSchemaProvider

            return ObjectInfoSchemaProvider(_RUNTIME_OBJECT_INFO_PATH[0])
    except Exception:
        pass
    fallback = get_authoring_schema_provider()
    try:
        schemas = getattr(fallback, "schemas", None)
        if callable(schemas) and schemas():
            return fallback
    except Exception:
        pass
    return get_schema_provider("local")


def handle_agent_edit(
    payload: dict[str, Any],
    *,
    schema_provider: Any = None,
    deepseek_client: DeepSeekClient | None = None,
    session_root: Path | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Convert current UI JSON to Python, ask the agent to edit it, emit UI JSON."""
    from vibecomfy.schema import get_schema_provider

    if not isinstance(payload, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")

    task = payload.get("task")
    graph = payload.get("graph")
    if not isinstance(task, str) or not task.strip():
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "`task` is required."},
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")
    if not isinstance(graph, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={
                "explanation": "`graph` must be a ComfyUI UI JSON object."
            },
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")

    if schema_provider is None:
        schema_provider = _default_runtime_schema_provider()
    root = session_root or _SESSION_ROOT
    session_id = _safe_session_id(payload.get("session_id"))
    allocation = allocate_turn(
        session_root=root,
        session_id=session_id,
        request_payload=payload,
        idempotency_key=payload.get("idempotency_key")
        if isinstance(payload.get("idempotency_key"), str)
        else None,
    )
    if allocation.replay is not None:
        return _validated_agent_edit_response(allocation.replay.response, stage="replay")
    if allocation.conflict is not None:
        try:
            audit_ref = write_allocation_failure_audit(
                allocation.session_dir,
                session_id=session_id,
                failure=allocation.conflict.failure,
                request=payload,
            )
            failure = dataclasses.replace(allocation.conflict.failure, audit_ref=audit_ref)
        except Exception:
            failure = allocation.conflict.failure
        return _validated_agent_edit_response(
            _product_failure_response(failure),
            stage="allocation",
        )

    context = allocation.context
    context.client_graph_hash = payload.get("client_graph_hash") if isinstance(payload.get("client_graph_hash"), str) else None
    initialize_gates(context)
    _write_unknown_transition_audits(
        session_root=root,
        session_id=session_id,
        baseline_turn_id=context.baseline_turn_id,
        unknown_transitions=allocation.unknown_transitions,
        request_payload=payload,
    )
    turn_dir = allocation.turn_dir
    turn_record = allocation.state.get("turns", {}).get(context.turn_id)
    baseline_graph_hash = (
        allocation.state.get("baseline_graph_hash")
        if isinstance(allocation.state.get("baseline_graph_hash"), str)
        else None
    )
    submit_graph_hash = (
        turn_record.get("submit_graph_hash")
        if isinstance(turn_record, dict) and isinstance(turn_record.get("submit_graph_hash"), str)
        else None
    )
    submit_structural_graph_hash = (
        turn_record.get("submit_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submit_structural_graph_hash"), str)
        else None
    )
    submitted_client_graph_hash = (
        turn_record.get("submitted_client_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_graph_hash"), str)
        else None
    )
    submitted_client_structural_graph_hash = (
        turn_record.get("submitted_client_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_structural_graph_hash"), str)
        else None
    )
    state = AgentEditState(
        task=task,
        graph=graph,
        request_payload=payload,
        schema_provider=schema_provider,
        baseline_graph_hash=baseline_graph_hash,
        submit_graph_hash=submit_graph_hash,
        submit_structural_graph_hash=submit_structural_graph_hash,
        submitted_client_graph_hash=submitted_client_graph_hash,
        submitted_client_structural_graph_hash=submitted_client_structural_graph_hash,
        session_dir=allocation.session_dir,
        turn_dir=turn_dir,
        request_path=turn_dir / "request.json",
        original_ui_path=turn_dir / "original.ui.json",
        before_py_path=turn_dir / "before.py",
        after_py_path=turn_dir / "after.py",
        model_request_path=turn_dir / "model_request.json",
        model_response_path=turn_dir / "model_response.json",
        candidate_ui_path=turn_dir / "candidate.ui.json",
        revision_evidence_path=turn_dir / "revision_evidence.json",
        projection_path=turn_dir / "projection.txt",
        messages_path=turn_dir / "messages.jsonl",
    )
    research_summary = payload.get("research_summary")
    if isinstance(research_summary, str) and research_summary.strip():
        state.executor_research_summary = research_summary.strip()
    research_warnings: list[str] = []
    raw_research_warnings = payload.get("research_warnings")
    if isinstance(raw_research_warnings, list):
        research_warnings.extend(
            warning.strip()
            for warning in raw_research_warnings
            if isinstance(warning, str) and warning.strip()
        )
    executor_research = payload.get("executor_research")
    if isinstance(executor_research, dict):
        raw_executor_warnings = executor_research.get("warnings")
        if isinstance(raw_executor_warnings, list):
            research_warnings.extend(
                warning.strip()
                for warning in raw_executor_warnings
                if isinstance(warning, str) and warning.strip()
            )
    if research_warnings:
        state.executor_research_warnings = tuple(dict.fromkeys(research_warnings))
    research_sources = payload.get("research_sources")
    if isinstance(research_sources, list):
        state.executor_research_sources = tuple(
            source for source in research_sources if isinstance(source, dict)
        )
    # Extract structured precedent data from payload (SD2)
    precedent_slices = payload.get("precedent_slices")
    if isinstance(precedent_slices, list):
        state.executor_precedent_slices = tuple(
            s for s in precedent_slices if isinstance(s, dict)
        )
    adaptation_plan = payload.get("adaptation_plan")
    if isinstance(adaptation_plan, dict):
        state.executor_adaptation_plan = adaptation_plan
    research_brief = payload.get("research_brief")
    if isinstance(research_brief, dict):
        state.executor_research_brief = research_brief
    # SD3: scoped adapt-prefetch fields.
    protocol_notes = payload.get("execution_protocol_notes")
    if isinstance(protocol_notes, dict):
        state.execution_protocol_notes = protocol_notes
    context_packet = payload.get("research_context_packet")
    if isinstance(context_packet, dict):
        state.research_context_packet = context_packet
    if isinstance(payload.get("max_batches"), int) and payload["max_batches"] > 0:
        state.batch_max_turns = int(payload["max_batches"])
    if (
        isinstance(payload.get("max_consecutive_errors"), int)
        and payload["max_consecutive_errors"] > 0
    ):
        state.batch_max_consecutive_errors = int(payload["max_consecutive_errors"])

    contract = _agent_edit_contract()

    raw_route = payload.get("route") if isinstance(payload.get("route"), str) else None
    executor_route = payload.get("executor_route") if isinstance(payload.get("executor_route"), str) else raw_route
    provider_route = payload.get("provider_route") if isinstance(payload.get("provider_route"), str) else raw_route
    route = _canonical_agent_edit_route(executor_route)
    model = payload.get("model") if isinstance(payload.get("model"), str) else None
    state.route = route

    # Load session-local last-five conversation messages for prompt memory.
    # Only the batch_repl product path injects them (SD2); delta/full-dev
    # paths persist chat artifacts but do not receive prompt memory in this
    # slim v1 milestone.
    conversation_messages: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        try:
            chat = read_session_chat(root, session_id, max_messages=PROMPT_MEMORY_MESSAGES)
            if chat.get("ok") and isinstance(chat.get("messages"), list):
                conversation_messages = chat["messages"]
                conversation_messages = _conversation_with_candidate_reference(
                    conversation_messages,
                    chat.get("latest_candidate"),
                )
        except Exception:
            conversation_messages = None

    try:
        if contract == "batch_repl":
            state = _run_batch_repl_product_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
                client_id=client_id,
                conversation_messages=conversation_messages,
            )
        elif contract == "delta":
            state = _run_delta_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
            )
        else:
            state = _run_full_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
            )
    except _StageBlocked as blocked:
        stage_name = (
            blocked.failure.stage
            if blocked.failure is not None
            else blocked.result.stage
        )
        response = _validated_agent_edit_response(
            _failure_response(
                state,
                context,
                contract=contract,
                failure=blocked.failure
                or classify_failure(blocked.result.stage, blocked, context),
            ),
            stage=stage_name,
        )
        _write_turn_chat_artifact(state, context, response, contract)
        record_idempotent_response(
            session_root=root,
            session_id=session_id,
            scope="edit",
            idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
            request_hash=allocation.request_hash,
            response=response,
            response_path=turn_dir / "response.json",
            operation="edit",
            turn_id=context.turn_id,
        )
        return response

    # Carry canonical executor route on state so response builders can apply
    # route-aware gating independent of provider dispatch.
    state.route = route

    if contract == "delta":
        response = _validated_agent_edit_response(
            _build_dev_success_response(state, context, contract=contract),
            stage="submit",
        )
    elif contract == "batch_repl":
        response = _validated_agent_edit_response(
            _build_batch_repl_response(state, context),
            stage="submit",
        )
    else:
        response = _validated_agent_edit_response(
            _build_dev_success_response(state, context, contract=contract),
            stage="submit",
        )
    try:
        if contract == "delta":
            _record(
                context,
                StageResult(
                    stage="audit",
                    ok=True,
                    blocking=False,
                    value={"mode": "agent_edit_v2_delta"},
                ),
            )
        elif contract == "batch_repl":
            _record(
                context,
                StageResult(
                    stage="audit",
                    ok=True,
                    blocking=False,
                    value={"mode": state.batch_exit_mode or "batch_repl"},
                ),
            )
        audit_ref = _stage_audit(state, context, response=response)
        response["audit_ref"] = audit_ref.to_dict()
    except Exception as exc:
        failure = failure_envelope(
            FailureKind.AUDIT_WRITE_FAILURE,
            "audit",
            context,
            agent_failure_context={"explanation": str(exc)},
            audit_error=str(exc),
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="audit")
    response = _validated_agent_edit_response(response, stage="submit")
    _write_turn_chat_artifact(state, context, response, contract)
    record_idempotent_response(
        session_root=root,
        session_id=session_id,
        scope="edit",
        idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
        request_hash=allocation.request_hash,
        response=response,
        response_path=turn_dir / "response.json",
        operation="edit",
        turn_id=context.turn_id,
    )
    return response


# ── WebSocket event helpers (best-effort, compact) ──────────────────────────


def _ws_send(event: str, payload: dict[str, Any], *, client_id: str | None = None) -> None:
    """Send a websocket event to a client, preferring send_sync, falling back to send_json.

    This is a best-effort adapter: failures are logged and swallowed so websocket issues
    never block the agent-edit control flow.
    """
    try:
        from server import PromptServer  # noqa: PLC0415
    except ImportError:
        return  # not running inside ComfyUI (tests, CLI, etc.)
    try:
        if hasattr(PromptServer.instance, "send_sync") and callable(
            PromptServer.instance.send_sync
        ):
            PromptServer.instance.send_sync(event, payload, sid=client_id)
        elif hasattr(PromptServer.instance, "send_json") and callable(
            PromptServer.instance.send_json
        ):
            PromptServer.instance.send_json(event, payload, sid=client_id)
    except Exception:
        LOGGER.debug("websocket send for event %r to client %r failed (best-effort)", event, client_id, exc_info=True)


def _brief_batch_statements(turn_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact, privacy-safe list of statement summaries from a batch turn record.

    Excludes: diff, raw batch/source, report text, provider metadata, and any raw JSON dumps.
    """
    if not isinstance(turn_record, dict):
        return []

    # Clarification turns have a different shape
    if turn_record.get("clarification_required"):
        return [
            {
                "clarification": True,
                "message": turn_record.get("clarification_message", ""),
            }
        ]

    statements = turn_record.get("statements")
    if not isinstance(statements, list) or not statements:
        # Fallback: build a minimal summary from turn-level fields
        return [
            {
                "ok": bool(turn_record.get("batch_ok")),
                "statement_count": int(turn_record.get("statement_count", 0)),
                "landed": int(turn_record.get("landed_op_count", 0)),
                "diagnostic_count": len(turn_record.get("diagnostics") or []),
            }
        ]

    brief: list[dict[str, Any]] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        compact: dict[str, Any] = {
            "statement_index": stmt.get("statement_index"),
            "ok": stmt.get("ok"),
            "landed": stmt.get("landed"),
            "op_kind": stmt.get("op_kind"),
        }
        # Only include teaching_hint if present (it's compact guidance, not raw source)
        if stmt.get("teaching_hint"):
            compact["teaching_hint"] = stmt["teaching_hint"]
        if stmt.get("dependency_cause"):
            compact["dependency_cause"] = stmt["dependency_cause"]
        # Compact diagnostics: only code + message, no raw detail blobs
        diags = stmt.get("diagnostics")
        if isinstance(diags, list) and diags:
            compact["diagnostics"] = [
                {"code": d.get("code"), "message": d.get("message")}
                for d in diags
                if isinstance(d, dict)
            ][:5]
        # Touched uids are small identifiers, safe to include
        if stmt.get("touched_uids"):
            compact["touched_uids"] = list(stmt["touched_uids"])[:10]
        brief.append(compact)
    return brief


def _agent_edit_turn_event_payload(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    entry_type: str = "batch",
    status: str = "progress",
) -> dict[str, Any]:
    """Build a compact websocket event payload for a batch turn.

    Excludes: diff, raw batch/source text, file paths, provider metadata,
    and raw JSON blobs.  Only includes fields safe for wire transport.
    """
    payload: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "turn_number": turn_record.get("turn_number"),
        "entry_type": entry_type,
        "status": status,
    }

    # Include a bounded user-facing message
    message = turn_record.get("message")
    if isinstance(message, str) and message:
        payload["message"] = message[:500] if len(message) > 500 else message

    if turn_record.get("clarification_required"):
        payload["clarification_required"] = True
        cm = turn_record.get("clarification_message")
        if isinstance(cm, str) and cm:
            payload["clarification_message"] = cm[:500] if len(cm) > 500 else cm
    else:
        payload["batch_ok"] = bool(turn_record.get("batch_ok"))
        payload["statement_count"] = int(turn_record.get("statement_count", 0))
        payload["landed_op_count"] = int(turn_record.get("landed_op_count", 0))

    # Compact statement summaries (privacy-safe)
    statements = _brief_batch_statements(turn_record)
    if statements:
        payload["statements"] = statements

    # Turn-level diagnostics (compact: code + message only)
    diags = turn_record.get("diagnostics")
    if isinstance(diags, list) and diags:
        payload["diagnostics"] = [
            {"code": d.get("code"), "message": d.get("message")}
            for d in diags
            if isinstance(d, dict)
        ][:5]

    # Exit mode info when present
    exit_mode = getattr(state, "batch_exit_mode", "")
    if exit_mode:
        payload["exit_mode"] = exit_mode
    if exit_mode in {_BATCH_EXIT_DONE, _BATCH_EXIT_NOOP} and getattr(state, "batch_done_summary", ""):
        payload["done_summary"] = str(state.batch_done_summary)[:500]

    # Budget snapshot
    budget = getattr(state, "batch_budget_state", None)
    if isinstance(budget, dict) and budget:
        payload["budget"] = {
            "remaining_batches": budget.get("remaining_batches"),
            "consecutive_errors": budget.get("consecutive_errors"),
        }

    return payload


def _emit_agent_edit_turn_event(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    client_id: str | None = None,
    entry_type: str = "batch",
    status: str = "progress",
) -> None:
    """Emit a compact websocket event for a batch turn.  Best-effort; never raises."""
    try:
        payload = _agent_edit_turn_event_payload(
            state, context, turn_record, entry_type=entry_type, status=status
        )
        _ws_send("vibecomfy.agent_edit.turn", payload, client_id=client_id)
    except Exception:
        LOGGER.debug("emit agent-edit turn event failed (best-effort)", exc_info=True)


__all__ = [
    "AgentEditState",
    "DeepSeekClient",
    "handle_agent_edit",
]
