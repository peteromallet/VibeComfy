from __future__ import annotations

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
from .diagnostics import queue_stage_result
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
)
from vibecomfy.executor.revision_evidence import (
    collect_graph_facts,
    collect_readiness_evidence,
    collect_topology_evidence,
    compute_scoped_diff,
)
from .agent_edit.clarify import (
    CLARIFY_FORBIDDEN_RESPONSE_KEYS as _CLARIFY_FORBIDDEN_RESPONSE_KEYS,
    _build_premature_clarify_turn_record,
    _compute_premature_clarify_feedback,
    format_clarify_markdown_message as _format_clarify_markdown_message,
    sanitize_pure_clarify_response as _sanitize_pure_clarify_response,
    split_terminal_clarify,
    strip_clarify_forbidden_response_fields as _strip_clarify_forbidden_response_fields,
)
from .agent_edit.client import DeepSeekClient
from .agent_edit.fields import (
    field_changes_payload as _field_changes_payload,
    repair_field_changes_from_original_ui as _repair_field_changes_from_original_ui,
)
from .agent_edit.lowering import (
    build_lowering_audit_entries as _build_lowering_audit_entries,
    build_lowering_change_entries as _build_lowering_change_entries,
    build_lowering_recovery_entries as _build_lowering_recovery_entries,
    inject_lowering_provenance as _inject_lowering_provenance,
)
from .agent_edit.paths import artifact as _artifact, safe_session_id as _safe_session_id
from .agent_edit.state import AgentEditState, _StageBlocked

from .agent_edit.labels import (
    _article_for,
    _change_subject,
    _display_value,
    _first_link_source_label,
    _format_available_node_names,
    _format_node_variable_index,
    _is_link_endpoint,
    _iter_ui_nodes,
    _link_endpoint_parts,
    _looks_internal_uid,
    _node_class_label,
    _node_key_values,
    _node_label_by_uid,
    _node_phrase,
    _present_class_types,
    _resolve_endpoint_label,
    _resolve_output_slot_name,
    _ui_display_widget_value_for_field,
    _ui_node_by_uid,
)
from .agent_edit.budget import (
    _BATCH_EXIT_BUDGET,
    _BATCH_EXIT_DONE,
    _BATCH_EXIT_EDIT_CLARIFY,
    _BATCH_EXIT_NOOP,
    _BATCH_EXIT_PURE_CLARIFY,
    _batch_budget_failure_kind,
    _batch_candidate_graph_changed,
    _batch_has_landed_edits,
    _duration_ms,
    _field_change_is_noop,
    _noop_field_changes,
    _read_only_discovery_turn_count,
    _real_field_changes,
    _total_landed_edit_count,
)
from .agent_edit.messages import (
    _batch_research_memory_summary,
    _batch_warning_sentence,
    _change_details_payload,
    _lint_issue_to_dict,
    _discovery_stop_message,
    _format_batch_report,
    _format_batch_report_json,
    _format_research_brief_for_prompt,
    _human_change_phrase,
    _humanized_edit_message,
    _humanized_noop_message,
    _join_human_list,
    _landed_edit_lead,
    _operation_detail_payload,
    _premature_missing_custom_node_clarify_feedback,
    _premature_workflow_schema_clarify_feedback,
    _resolver_candidates_from_batch_turns,
    _revision_candidate_retry_hint,
    _revision_rejected_candidate_message,
    _sentence_case,
    _structural_change_phrases,
    _summarize_precedent_packet,
    _synthesize_batch_repl_message,
    _terminal_answer_message,
)
from .agent_edit.artifacts import (
    _CHAT_REASONING_MAX_DIAGS,
    _CHAT_REASONING_MAX_OPERATIONS,
    _CHAT_REASONING_MAX_STEPS,
    _compact_chat_change_details,
    _compact_diag_to_dict,
    _format_query_output,
    _format_statement_source,
    _json_safe,
    _latest_session_candidate_payload,
    _normalize_test_client_batch_response,
    _normalize_test_client_response,
    _port_issue_to_dict,
    _read_turn_response_payload,
    _render_batch_diff,
    _stamped_message_outcome,
    _stamped_turn_response_outcome,
    _trim_chat_text,
    _write_turn_chat_artifact,
)
from .agent_edit.responses import (
    _build_batch_repl_failure_response as _build_batch_repl_failure_response_impl,
    _build_batch_repl_response as _build_batch_repl_response_impl,
    _build_candidate_payload as _build_candidate_payload_impl,
    _build_dev_failure_response as _build_dev_failure_response_impl,
    _build_dev_success_response as _build_dev_success_response_impl,
    _failure_response as _failure_response_impl,
    _legacy_failure_response as _legacy_failure_response_impl,
    _product_failure_response as _product_failure_response_impl,
    _session_artifact_response_fields as _session_artifact_response_fields_impl,
    _stage_snapshot_payloads as _stage_snapshot_payloads_impl,
    _validated_agent_edit_response as _validated_agent_edit_response_impl,
)
from .agent_edit.runtime_schema import (
    _RUNTIME_OBJECT_INFO_PATH,
    _build_compatibility_response_fields as _build_compatibility_response_fields_impl,
    _build_object_info_in_process as _build_object_info_in_process_impl,
    _candidate_stable_key as _candidate_stable_key_impl,
    _default_runtime_schema_provider as _default_runtime_schema_provider_impl,
    _enrich_schema_provider_from_resolver_candidates as _enrich_schema_provider_from_resolver_candidates_impl,
    _recovery_report_from_ui_payload as _recovery_report_from_ui_payload_impl,
    _resolver_candidates_from_batch_result as _resolver_candidates_from_batch_result_impl,
    _workflow_schema_candidates_from_batch_result as _workflow_schema_candidates_from_batch_result_impl,
    _write_unknown_transition_audits as _write_unknown_transition_audits_impl,
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
from .agent_edit.websocket import (
    _agent_edit_turn_event_payload as _agent_edit_turn_event_payload_impl,
    _brief_batch_statements as _brief_batch_statements_impl,
    _emit_agent_edit_turn_event as _emit_agent_edit_turn_event_impl,
    _ws_send as _ws_send_impl,
)
from .agent_edit.stages.ingest import (
    _stage_convert,
    _stage_ingest,
    _stage_ingest_v2,
    _stage_project_v2,
    _stale_rebaseline_recovery_issue,
    _stamp_identity_on_original,
)
from .agent_edit.stages.agent_delta import (
    _edit_lint_enabled,
    _stage_agent,
    _stage_agent_delta,
    _stage_apply_delta,
)
from .agent_edit.stages.load_lower_validate_emit import (
    _stage_emit,
    _stage_load_python,
    _stage_lower,
    _stage_validate,
)
from .agent_edit.stages.revision import (
    _finalize_revision_evidence_with_candidate,
    _localized_additive_scoped_evidence,
    _revision_evidence_prompt_json,
    _revision_no_candidate_reason,
    _revision_readonly_message,
    _revision_target_node_ids,
    _stage_revision_evidence,
    _stage_revision_readonly_report,
    _write_revision_evidence_artifact,
)


if TYPE_CHECKING:
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.workflow import VibeWorkflow

_SESSION_ROOT = Path("out/editor_sessions")
DEFAULT_CHAT_DISPLAY_MESSAGES = 50
PROMPT_MEMORY_MESSAGES = 5
LOGGER = logging.getLogger(__name__)
_WARNED_LEGACY_CONTRACTS: set[str] = set()
_WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS: set[str] = set()




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


def _record(context: TurnContext, result: StageResult) -> StageResult:
    context.stage_results[result.stage] = result
    apply_stage_gate_updates(context, result)
    return result


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


def _prefetch_research_summary(task: str) -> str:
    if not task.strip():
        return ""
    return (
        "Graph explanation context:\n"
        "Use the attached workflow structure to explain what the current graph is doing, "
        "call out the important nodes and connections, and answer in graph terms before "
        "proposing edits."
    )



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


def _stage_agent_batch_repl(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> StageResult:
    from vibecomfy.porting.edit import session as edit_session_module

    start = time.monotonic()
    prepared_ui = state.guard_original_ui or state.graph
    session = edit_session_module.EditSession(prepared_ui, schema_provider=state.schema_provider)
    state.batch_session = session
    initial_render = session.render()
    present_types = _present_class_types(session)
    focus_types = set(present_types)
    effective_task = _effective_implementation_task(state)
    focus_types.update(_seed_focus_types_for_authoring(state))
    focus_types.update(_focus_types_from_research_brief(state.executor_research_brief))
    if _is_code_node_intent(effective_task):
        focus_types.add("vibecomfy.exec")
    signature_catalog = session.search(focus_types=sorted(focus_types), formatted=True)
    available_node_names = _format_available_node_names(session.search(formatted=False))
    state.python_before = initial_render
    state.before_py_path.write_text(initial_render, encoding="utf-8")
    if isinstance(signature_catalog, str):
        state.batch_signature_catalog = signature_catalog

    classification = (
        state.request_payload.get("executor_classification")
        if isinstance(state.request_payload, dict)
        else None
    )
    intent = classification.get("intent") if isinstance(classification, dict) else ""
    # explain_graph intent now maps to the executor inspect route, which
    # never reaches the agent-edit pipeline.  Keep the text-pattern fallback
    # for revise / adapt operations where the task reads like a graph
    # explanation (provides helpful context in the batch-REPL prompt).
    prefetch_explain = not intent and _is_graph_explain_intent(effective_task)
    prefetch_research_summary = state.executor_research_summary or (
        _prefetch_research_summary(effective_task) if prefetch_explain else ""
    )
    research_brief_prompt = _format_research_brief_for_prompt(state.executor_research_brief)
    if prefetch_research_summary and state.executor_research_warnings:
        warning_lines = [
            f"- {warning}" for warning in state.executor_research_warnings[:6]
        ]
        prefetch_research_summary = (
            f"{prefetch_research_summary}\n\n"
            "Research warnings:\n"
            + "\n".join(warning_lines)
        )
    if prefetch_research_summary and state.executor_research_sources:
        source_lines = [
            json.dumps(source, sort_keys=True)
            for source in state.executor_research_sources[:8]
        ]
        prefetch_research_summary = (
            f"{prefetch_research_summary}\n\n"
            "Structured research sources (JSON lines):\n"
            + "\n".join(source_lines)
        )
    prefetch_graph_report = (
        _build_graph_report(state.graph) if prefetch_explain else ""
    )
    # Build compact adaptation plan prompt for adapt route.
    precedent_adaptation_prompt = ""
    adapt_scoped_research_context = ""
    canonical_route = _canonical_agent_edit_route(state.route or route)
    research_only_route = canonical_route == "research"
    if canonical_route == "adapt":
        if state.executor_adaptation_plan:
            precedent_adaptation_prompt = _build_precedent_adaptation_prompt(
                state.executor_adaptation_plan,
                state.executor_precedent_slices,
            )
        # SD3: scoped adapt prefetch from execution_protocol_notes and
        # research_context_packet — discardable, evidence-only context.
        if state.execution_protocol_notes or state.research_context_packet or state.graph_facts:
            parts: list[str] = []
            discard_note: str | None = None
            if state.execution_protocol_notes:
                notes = dict(state.execution_protocol_notes)
                discard_note = notes.pop("_discardability", None)
                notes_str = json.dumps(notes, indent=2, sort_keys=True)
                parts.append(
                    "## Scoped Research Context (execution_protocol_notes)\n"
                    "This is contextual evidence, NOT authoritative guidance.\n"
                    f"{notes_str}"
                )
            if state.research_context_packet:
                packet_str = json.dumps(
                    state.research_context_packet, indent=2, sort_keys=True
                )
                parts.append(
                    "## Research Context Packet (discardable)\n"
                    "Precedent evidence from research phase. "
                    "Discard if empty, irrelevant, or contradictory.\n"
                    f"{packet_str}"
                )
            # SD2: compact graph facts from topology/readiness collectors.
            if state.graph_facts:
                facts_str = json.dumps(state.graph_facts, indent=2, sort_keys=True)
                parts.append(
                    "## Graph Facts (workflow topology evidence)\n"
                    "Deterministic topology/readiness evidence about the current graph. "
                    "Use this to understand the workflow structure, terminal outputs, "
                    "and any known blockers. NOT a revision verdict.\n"
                    f"{facts_str}"
                )
            if discard_note:
                parts.append(f"**Discardability**: {discard_note}")
            adapt_scoped_research_context = "\n\n".join(parts)

    max_batches = max(1, int(state.batch_max_turns or 1))
    max_consecutive_errors = max(1, int(state.batch_max_consecutive_errors or 1))
    state.batch_budget_state = {
        "max_batches": max_batches,
        "max_consecutive_errors": max_consecutive_errors,
        "remaining_batches": max_batches,
        "remaining_consecutive_errors": max_consecutive_errors,
    }
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "revision_evidence": str(state.revision_evidence_path),
        "messages": str(state.messages_path),
    }

    current_render = initial_render
    last_diff = ""
    last_report = ""
    last_landed_count: int | None = None
    previous_model_message = ""
    consecutive_errors = 0
    total_landed = 0
    done_noop_nudges = 0
    done_error_nudges = 0
    done_candidate_rejection_nudges = 0
    failed_edit_turns = 0
    last_failed_edit_turn = -1
    last_successful_edit_turn_after_failure = -1
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []

    for turn_number in range(max_batches):
        budget_remaining = max_batches - turn_number
        include_full_render = turn_number == 0 or last_landed_count == 0
        node_variable_index = _format_node_variable_index(session)
        research_memory = _batch_research_memory_summary(state)
        turn_research_summary = prefetch_research_summary if turn_number == 0 else ""
        if research_memory:
            turn_research_summary = (
                f"{turn_research_summary}\n\nPrior research/query memory:\n{research_memory}"
            ).strip()
        messages = build_batch_messages(
            task=effective_task,
            turn_number=turn_number,
            python_source=(initial_render if turn_number == 0 else current_render)
            if include_full_render
            else "",
            node_variable_index=node_variable_index,
            previous_model_message=previous_model_message,
            signature_catalog=state.batch_signature_catalog if turn_number == 0 else "",
            available_node_names=available_node_names if turn_number == 0 else "",
            diff=last_diff,
            report=last_report,
            budget_remaining=budget_remaining,
            max_batches=max_batches,
            conversation_messages=conversation_messages if turn_number == 0 else None,
            research_only=research_only_route,
            research_brief=research_brief_prompt if turn_number == 0 else "",
            research_summary=turn_research_summary,
            graph_report=prefetch_graph_report if turn_number == 0 else "",
            precedent_adaptation_plan=(
                (precedent_adaptation_prompt + "\n\n" + adapt_scoped_research_context).strip()
                if turn_number == 0
                else ""
            ),
            revision_evidence_json=_revision_evidence_prompt_json(state)
            if turn_number == 0
            else "",
        )
        request_entry = {
            "turn_number": turn_number,
            "messages": messages,
            "budget_remaining": budget_remaining,
            "node_variable_index": node_variable_index,
            "included_full_render": include_full_render,
        }
        request_log.append(request_entry)
        write_json_artifact(
            state.model_request_path,
            {"response_contract": "batch_repl", "turns": request_log},
        )

        try:
            if deepseek_client is not None:
                turn_result = _normalize_test_client_batch_response(deepseek_client(messages))
            else:
                turn_result = run_agent_turn_batch(
                    state.task,
                    messages,
                    route=route,
                    model=model,
                )
        except (MalformedModelJSON, MissingRequiredField) as exc:
            feedback = (
                f"Agent response format error: {exc} "
                "Respond with one user-facing sentence followed by exactly one ```batch fenced block."
            )
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "retrying": consecutive_errors + 1 < max_consecutive_errors,
                    },
                }
            )
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            if consecutive_errors + 1 >= max_consecutive_errors:
                raise
            last_report = feedback
            previous_model_message = ""
            last_landed_count = 0
            consecutive_errors += 1
            continue
        except Exception as exc:
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            raise

        state.provider_metadata = dict(turn_result.audit_metadata or {})
        state.user_message = turn_result.message
        previous_model_message = turn_result.message
        clarify_split = split_terminal_clarify(turn_result.batch)
        clarify_message = clarify_split.message
        editable_batch = clarify_split.batch if clarify_message is not None else turn_result.batch
        response_log.append(
            {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "status": "received",
            }
        )
        write_json_artifact(state.model_response_path, {"turns": response_log})
        if clarify_message is not None and not editable_batch.strip():
            clarify_feedback = _compute_premature_clarify_feedback(
                state, clarify_message
            )
            if clarify_feedback:
                consecutive_errors += 1
                turn_record = _build_premature_clarify_turn_record(
                    turn_number, turn_result, clarify_feedback
                )
                state.batch_turns.append(turn_record)
                state.batch_feedback = clarify_feedback
                state.batch_turn_count = turn_number + 1
                state.batch_budget_state = {
                    "max_batches": max_batches,
                    "max_consecutive_errors": max_consecutive_errors,
                    "remaining_batches": max_batches - state.batch_turn_count,
                    "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
                    "consecutive_errors": consecutive_errors,
                }
                response_log[-1] = {
                    "turn_number": turn_number,
                    "response": turn_result.to_dict(),
                    "rejected_clarification": turn_record,
                }
                write_json_artifact(state.model_response_path, {"turns": response_log})
                state.messages_path.open("a", encoding="utf-8").write(
                    json.dumps(
                        {
                            "turn_number": turn_number,
                            "task": state.task,
                            "message": turn_result.message,
                            "batch": turn_result.batch,
                            "report": clarify_feedback,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                terminal_rejected_clarify = (
                    _batch_candidate_graph_changed(state)
                    or (
                        last_failed_edit_turn >= 0
                        and last_successful_edit_turn_after_failure < last_failed_edit_turn
                    )
                    or consecutive_errors >= max_consecutive_errors
                    or (turn_number + 1) >= max_batches
                )
                if terminal_rejected_clarify:
                    failure_kind = _batch_budget_failure_kind(state.batch_turns)
                    state.batch_exit_mode = _BATCH_EXIT_BUDGET
                    state.batch_final_summary = (
                        f"Stopped after {state.batch_turn_count} turn(s); "
                        f"{state.batch_budget_state.get('remaining_batches', 0)} turn(s) remaining."
                    )
                    _emit_agent_edit_turn_event(
                        state,
                        _context,
                        turn_record,
                        client_id=client_id,
                        status="budget_exhausted",
                    )
                    return StageResult(
                        stage="agent_batch",
                        ok=False,
                        blocking=True,
                        duration_ms=_duration_ms(start),
                        artifacts=(
                            _artifact(state.before_py_path),
                            _artifact(state.after_py_path),
                            _artifact(state.model_request_path),
                            _artifact(state.model_response_path),
                            _artifact(state.candidate_ui_path),
                            _artifact(state.messages_path),
                        ),
                        issues=(
                            {
                                "code": "batch_budget_exhausted",
                                "severity": "error",
                                "failure_kind": failure_kind.value,
                                "message": state.batch_final_summary,
                                "detail": {
                                    "turn_count": state.batch_turn_count,
                                    "budget_state": dict(state.batch_budget_state),
                                    "budget_classification": failure_kind.value,
                                },
                            },
                        ),
                        value={
                            "failure_kind": failure_kind.value,
                            "turn_count": state.batch_turn_count,
                            "budget_state": dict(state.batch_budget_state),
                            "budget_classification": failure_kind.value,
                        },
                    )
                last_report = clarify_feedback
                last_landed_count = 0
                _emit_agent_edit_turn_event(
                    state,
                    _context,
                    turn_record,
                    client_id=client_id,
                    status="in_progress",
                )
                continue
        if clarify_message is not None and not editable_batch.strip():
            state.batch_turn_count = turn_number + 1
            state.batch_exit_mode = (
                _BATCH_EXIT_EDIT_CLARIFY
                if _batch_candidate_graph_changed(state)
                else _BATCH_EXIT_PURE_CLARIFY
            )
            state.batch_final_summary = (
                f"Clarification requested after {state.batch_turn_count} batch turn(s)."
            )
            state.batch_budget_state = {
                "max_batches": max_batches,
                "max_consecutive_errors": max_consecutive_errors,
                "remaining_batches": max_batches - state.batch_turn_count,
                "remaining_consecutive_errors": max_consecutive_errors,
                "consecutive_errors": consecutive_errors,
            }
            state.user_message = clarify_message
            state.python_after = current_render
            state.after_py_path.write_text(current_render, encoding="utf-8")
            state.ui_payload = json.loads(json.dumps(session.working_ui))
            write_json_artifact(state.candidate_ui_path, state.ui_payload)
            state.report = {
                "clarification_required": True,
                "graph_unchanged": True,
                "queue_blockers": [],
            }
            turn_record = {
                "turn_number": turn_number,
                "batch": turn_result.batch,
                "message": turn_result.message,
                "route": turn_result.route,
                "model": turn_result.model,
                "provider_metadata": _json_safe(dict(turn_result.audit_metadata or {})),
                "clarification_required": True,
                "clarification_message": clarify_message,
                "field_changes": [],
            }
            state.batch_turns.append(turn_record)
            response_log[-1] = {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "clarification": turn_record,
            }
            write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(
                    {
                        "turn_number": turn_number,
                        "task": state.task,
                        "message": turn_result.message,
                        "batch": turn_result.batch,
                        "clarification_required": clarify_message,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            state.artifacts = {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "revision_evidence": str(state.revision_evidence_path),
                "messages": str(state.messages_path),
            }
            _emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=(
                    _artifact(state.after_py_path),
                    _artifact(state.model_request_path),
                    _artifact(state.model_response_path),
                    _artifact(state.candidate_ui_path),
                    _artifact(state.messages_path),
                ),
                value={"mode": "clarification_required", "graph_unchanged": True},
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                    "state_match_ok": True,
                }
                if state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY
                else {},
            )

        batch_result = session.apply_batch(editable_batch)
        _enrich_schema_provider_from_resolver_candidates(
            state,
            session,
            [
                *_workflow_schema_candidates_from_batch_result(batch_result),
                *_resolver_candidates_from_batch_result(batch_result),
            ],
        )
        next_render = session.render()
        state.python_after = next_render
        state.after_py_path.write_text(next_render, encoding="utf-8")
        state.ui_payload = json.loads(json.dumps(session.working_ui))
        write_json_artifact(state.candidate_ui_path, state.ui_payload)

        # ── lint gate: post-apply no-op detection on landed ops ──────────
        lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None
        lint_dropped_count = 0
        lint_diag_dicts: tuple[dict[str, Any], ...] = ()
        if (
            _edit_lint_enabled()
            and batch_result.landed_ops
            and _agent_edit_batch_repl_enabled()
        ):
            from vibecomfy.porting.edit.lint import LintIndex, lint_delta
            from vibecomfy.porting.edit.ops import (
                RemoveLinkOp,
                SetModeOp,
                SetNodeFieldOp,
                UpsertLinkOp,
            )

            index = LintIndex.build(state.graph)
            lint_result = lint_delta(
                batch_result.landed_ops,
                index,
                schema_provider=state.schema_provider,
            )

            landed_add_uids = {
                str(item.detail.get("minted_uid"))
                for item in batch_result.statements
                if item.ok
                and str(item.op_kind or "") == "node_call"
                and isinstance(item.detail, Mapping)
                and item.detail.get("minted_uid") is not None
            }

            # Build (uid, field_path) identities for lint-dropped ops.
            _dropped_keys: list[tuple[str, str]] = []
            for norm in lint_result.normalizations:
                if norm.disposition != "dropped_noop":
                    continue
                op = norm.op
                key: tuple[str, str] | None = None
                if isinstance(op, SetNodeFieldOp):
                    key = (op.target.uid, op.target.field_path)
                elif isinstance(op, SetModeOp):
                    key = (op.target.uid, "mode")
                elif isinstance(op, UpsertLinkOp):
                    key = (op.target.uid, op.target.input_field)
                elif isinstance(op, RemoveLinkOp) and op.target is not None:
                    key = (op.target.uid, op.target.input_field)
                if key is not None:
                    _dropped_keys.append(key)
            lint_dropped_op_ids = frozenset(_dropped_keys)
            lint_dropped_count = lint_result.dropped_count

            # Accumulate human-readable lint no-op messages
            _turn_noop_msgs: list[str] = []
            for norm in lint_result.normalizations:
                if norm.disposition == "dropped_noop" and norm.issue is not None:
                    _turn_noop_msgs.append(norm.issue.message)
            state.lint_noop_messages = state.lint_noop_messages + tuple(_turn_noop_msgs)

            lint_issues = tuple(
                issue
                for issue in lint_result.issues
                if not (
                    issue.code == "unknown_target"
                    and issue.uid in landed_add_uids
                )
            )
            lint_diag_dicts = tuple(
                _lint_issue_to_dict(issue) for issue in lint_issues
            )

        raw_landed = len(batch_result.landed_ops)
        effective_landed = raw_landed - lint_dropped_count
        landed_count = effective_landed
        total_landed += effective_landed
        last_landed_count = effective_landed

        turn_has_errors = (
            (not batch_result.ok)
            or bool(batch_result.diagnostics)
            or any(
                d.get("severity") == "error" for d in lint_diag_dicts
            )
        )
        consecutive_errors = consecutive_errors + 1 if turn_has_errors else 0
        diff_text = _render_batch_diff(current_render, next_render)
        report_text = _format_batch_report(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
            lint_dropped_count=lint_dropped_count,
            lint_diagnostics=lint_diag_dicts,
        )
        report_json = _format_batch_report_json(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
            lint_dropped_count=lint_dropped_count,
            lint_diagnostics=lint_diag_dicts,
        )
        field_changes = repair_field_changes(
            state.graph,
            tuple(batch_result.field_changes),
        )
        real_field_changes = _real_field_changes(
            field_changes,
            lint_dropped_op_ids=lint_dropped_op_ids,
        )
        noop_field_changes = _noop_field_changes(
            field_changes,
            lint_dropped_op_ids=lint_dropped_op_ids,
        )
        state.batch_field_changes = state.batch_field_changes + real_field_changes
        state.batch_noop_field_changes = state.batch_noop_field_changes + noop_field_changes
        turn_record = {
            "turn_number": turn_number,
            "batch": turn_result.batch,
            "message": turn_result.message,
            "route": turn_result.route,
            "model": turn_result.model,
            "provider_metadata": _json_safe(dict(turn_result.audit_metadata or {})),
            "batch_ok": batch_result.ok,
            "statement_count": len(batch_result.statements),
            "landed_op_count": effective_landed,
            "raw_landed_op_count": raw_landed,
            "lint_dropped_op_count": lint_dropped_count,
            "diagnostics": report_json["diagnostics"],
            "statements": report_json["statements"],
            "field_changes": _field_changes_payload(real_field_changes),
            "diff": diff_text,
            "report": report_text,
        }
        if noop_field_changes:
            turn_record["noop_field_changes"] = _field_changes_payload(noop_field_changes)
        if clarify_message is not None:
            turn_record["clarification_required"] = True
            turn_record["clarification_message"] = clarify_message
        state.batch_turns.append(turn_record)
        state.batch_feedback = report_text
        state.batch_turn_count = turn_number + 1
        state.batch_budget_state = {
            "max_batches": max_batches,
            "max_consecutive_errors": max_consecutive_errors,
            "remaining_batches": max_batches - state.batch_turn_count,
            "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
            "consecutive_errors": consecutive_errors,
        }

        response_log[-1] = {
            "turn_number": turn_number,
            "response": turn_result.to_dict(),
            "batch_result": turn_record,
        }
        write_json_artifact(state.model_response_path, {"turns": response_log})
        state.messages_path.open("a", encoding="utf-8").write(
            json.dumps(
                {
                    "turn_number": turn_number,
                    "task": state.task,
                    "message": turn_result.message,
                    "batch": turn_result.batch,
                    "report": report_text,
                },
                sort_keys=True,
            )
            + "\n"
        )

        if clarify_message is not None:
            state.batch_exit_mode = (
                _BATCH_EXIT_EDIT_CLARIFY
                if _batch_candidate_graph_changed(state)
                else _BATCH_EXIT_PURE_CLARIFY
            )
            state.batch_final_summary = (
                f"Clarification requested after {state.batch_turn_count} batch turn(s)."
            )
            state.user_message = clarify_message
            state.report = {
                "clarification_required": True,
                "graph_unchanged": state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY,
                "queue_blockers": [],
            }
            _emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=(
                    _artifact(state.after_py_path),
                    _artifact(state.model_request_path),
                    _artifact(state.model_response_path),
                    _artifact(state.candidate_ui_path),
                    _artifact(state.messages_path),
                ),
                value={
                    "mode": "clarification_required",
                    "graph_unchanged": state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY,
                },
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                    "state_match_ok": True,
                }
                if state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY
                else {},
            )

        current_render = next_render
        last_diff = diff_text
        last_report = report_text
        done_requested = any(
            item.ok and str(item.op_kind or "") == "done"
            for item in batch_result.statements
        )
        turn_failed_edit = any(
            (not item.ok)
            and str(item.op_kind or "") not in {"query", "done", "clarify"}
            for item in batch_result.statements
        )
        if turn_failed_edit:
            failed_edit_turns += 1
            last_failed_edit_turn = turn_number
        elif effective_landed > 0 and last_failed_edit_turn >= 0:
            last_successful_edit_turn_after_failure = turn_number
        unresolved_failed_edit = (
            last_failed_edit_turn >= 0
            and last_successful_edit_turn_after_failure < last_failed_edit_turn
        )
        turn_is_read_only = effective_landed == 0 and all(
            str(item.op_kind or "") in {"query", "done", "clarify"}
            for item in batch_result.statements
        )
        # Don't honor a premature done(): feed guidance back and let the model
        # self-correct. Two distinct cases, each separately bounded so a genuine
        # no-change request still commits and we can't loop forever:
        #  (1) NOTHING ever landed — committing would be an empty no-op. Causes:
        #      a wrong node signature, or a read-only search() then done().
        #  (2) Something landed but THIS (final) batch errored — some intended
        #      statements failed to land (e.g. a wrong output-slot name), so the
        #      edit is half-applied and likely broken (floating node / dangling
        #      wire). The diagnostics name the fix; force one more turn.
        refuse_done = False
        hint = ""
        if (
            done_requested
            and consecutive_errors < max_consecutive_errors
            and not research_only_route
        ):
            if total_landed == 0 and (turn_has_errors or failed_edit_turns > 0):
                done_noop_nudges += 1
                refuse_done = True
                if turn_has_errors:
                    hint = (
                        "your edit statement(s) did NOT land (see the diagnostics above)"
                        " and nothing has been applied. Fix the failed statement — correct"
                        " the wrong field name or supply the required input;"
                        " call search(focus_types=[\"ClassName\"]) for the exact signature —"
                        " then call done()."
                    )
                elif failed_edit_turns > 0:
                    hint = (
                        "earlier edit statement(s) failed and no edit has landed. A search()"
                        " is read-only and does NOT fix the failed edit. Use the diagnostics"
                        " above and construct a valid node/wire, or clarify the limitation;"
                        " do not report this as already done."
                    )
                else:
                    hint = (
                        "you called done() without making any edit, so nothing was applied."
                        " A search() is read-only and does NOT change the graph. Now CONSTRUCT"
                        " and wire the node(s) the request needs (e.g. `up = NodeType(...)` then"
                        " `consumer.input = up.OUTPUT`), then call done(). If the graph"
                        " genuinely needs no change, call done() again to confirm."
                    )
            elif unresolved_failed_edit and turn_is_read_only:
                done_noop_nudges += 1
                refuse_done = True
                hint = (
                    "an earlier edit batch failed after partially mutating the graph."
                    " A search() is read-only and does NOT repair that incomplete"
                    " candidate. Use the search result and diagnostics above to"
                    " construct and wire the missing node(s), then call done()."
                )
            elif (
                (turn_number + 1) < max_batches
                and total_landed == 0
                and done_noop_nudges < 2
            ):
                done_noop_nudges += 1
                refuse_done = True
                hint = (
                    "you called done() without making any edit, so nothing was applied."
                    " A search() is read-only and does NOT change the graph. Now CONSTRUCT"
                    " and wire the node(s) the request needs (e.g. `up = NodeType(...)` then"
                    " `consumer.input = up.OUTPUT`), then call done(). If the graph"
                    " genuinely needs no change, call done() again to confirm."
                )
            elif turn_has_errors and done_error_nudges < 2:
                done_error_nudges += 1
                refuse_done = True
                hint = (
                    "some of your edit statements did NOT land (see the diagnostics above),"
                    " so the edit is INCOMPLETE — nodes the request needs may be left"
                    " unconnected or a consumer's input left dangling. Do NOT stop here."
                    " Fix ONLY the failed statement(s): use the exact output-slot/field names"
                    " the diagnostics list (e.g. an output is `.UPSCALE_MODEL`, not `.model`),"
                    " drop any kwarg the node does not declare, re-wire the consumer, then"
                    " call done()."
                )
        if refuse_done:
            last_report = last_report + "\n\nNOTE: done() was NOT accepted — " + hint
            continue
        if done_requested:
            done_result = session.done()
            state.batch_turn_count = turn_number + 1
            state.batch_budget_state = {
                "max_batches": max_batches,
                "max_consecutive_errors": max_consecutive_errors,
                "remaining_batches": max_batches - state.batch_turn_count,
                "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
                "consecutive_errors": consecutive_errors,
            }
            state.batch_exit_mode = (
                _BATCH_EXIT_DONE if _batch_candidate_graph_changed(state) else _BATCH_EXIT_NOOP
            )
            state.batch_done_summary = done_result.summary
            state.batch_final_summary = done_result.summary
            if not done_result.ok:
                return StageResult(
                    stage="agent_batch",
                    ok=False,
                    blocking=True,
                    duration_ms=_duration_ms(start),
                    artifacts=(
                        _artifact(state.before_py_path),
                        _artifact(state.after_py_path),
                        _artifact(state.model_request_path),
                        _artifact(state.model_response_path),
                        _artifact(state.candidate_ui_path),
                        _artifact(state.messages_path),
                    ),
                    issues=tuple(_compact_diag_to_dict(item) for item in done_result.diagnostics),
                    value={
                        "failure_kind": FailureKind.VALIDATION_ERROR.value,
                        "turn_count": state.batch_turn_count,
                        "done_summary": done_result.summary,
                    },
                )
            state.user_message = ensure_sentence_message(
                turn_result.message,
                fallback="I made the requested workflow changes.",
            )
            state.report = {
                "done_summary": done_result.summary,
                "queue_blockers": [],
            }
            _finalize_revision_evidence_with_candidate(
                state,
                route=state.route,
                conversation_messages=conversation_messages,
            )
            scoped = (
                state.revision_evidence.scoped_diff
                if state.revision_evidence is not None
                else None
            )
            retryable_revise_blockers = (
                set(getattr(scoped, "eligibility_blockers", ()))
                - {"target_mismatch", "target_scope_violation"}
            )
            if (
                _canonical_agent_edit_route(state.route) == "revise"
                and state.revision_evidence is not None
                and state.revision_evidence.candidate_eligible is not True
                and retryable_revise_blockers
                and (turn_number + 1) < max_batches
                and done_candidate_rejection_nudges < 2
            ):
                done_candidate_rejection_nudges += 1
                last_report = (
                    last_report
                    + "\n\nNOTE: done() was NOT accepted — "
                    + _revision_candidate_retry_hint(state)
                )
                continue
            state.artifacts = {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "revision_evidence": str(state.revision_evidence_path),
                "messages": str(state.messages_path),
            }
            _emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="done",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=(
                    _artifact(state.before_py_path),
                    _artifact(state.after_py_path),
                    _artifact(state.model_request_path),
                    _artifact(state.model_response_path),
                    _artifact(state.candidate_ui_path),
                    _artifact(state.messages_path),
                ),
                value={"mode": "done", "done_summary": done_result.summary},
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                    "state_match_ok": True,
                },
            )
        if (
            total_landed == 0
            and _read_only_discovery_turn_count(state) >= 6
            and not _batch_candidate_graph_changed(state)
        ):
            state.batch_exit_mode = _BATCH_EXIT_PURE_CLARIFY
            state.batch_final_summary = (
                f"Stopped after {state.batch_turn_count} discovery-only batch turn(s)."
            )
            state.user_message = _discovery_stop_message(state)
            state.report = {
                "clarification_required": True,
                "graph_unchanged": True,
                "queue_blockers": [],
                "discovery_stop": {
                    "turn_count": state.batch_turn_count,
                    "reason": "repeated_read_only_discovery",
                },
            }
            _emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                artifacts=(
                    _artifact(state.after_py_path),
                    _artifact(state.model_request_path),
                    _artifact(state.model_response_path),
                    _artifact(state.candidate_ui_path),
                    _artifact(state.messages_path),
                ),
                value={
                    "mode": "discovery_stop",
                    "graph_unchanged": True,
                    "turn_count": state.batch_turn_count,
                },
            )
        _emit_agent_edit_turn_event(
            state,
            _context,
            turn_record,
            client_id=client_id,
            status="in_progress",
        )
        if consecutive_errors >= max_consecutive_errors:
            break

    failure_kind = _batch_budget_failure_kind(state.batch_turns)
    state.batch_exit_mode = _BATCH_EXIT_BUDGET
    state.batch_final_summary = (
        f"Stopped after {state.batch_turn_count} turn(s); "
        f"{state.batch_budget_state.get('remaining_batches', 0)} turn(s) remaining."
    )
    if state.batch_turns:
        _emit_agent_edit_turn_event(
            state,
            _context,
            state.batch_turns[-1],
            client_id=client_id,
            status="budget_exhausted",
        )
    return StageResult(
        stage="agent_batch",
        ok=False,
        blocking=True,
        duration_ms=_duration_ms(start),
        artifacts=(
            _artifact(state.before_py_path),
            _artifact(state.after_py_path),
            _artifact(state.model_request_path),
            _artifact(state.model_response_path),
            _artifact(state.candidate_ui_path),
            _artifact(state.messages_path),
        ),
        issues=(
            {
                "code": "batch_budget_exhausted",
                "severity": "error",
                "failure_kind": failure_kind.value,
                "message": state.batch_final_summary,
                "detail": {
                    "turn_count": state.batch_turn_count,
                    "budget_state": dict(state.batch_budget_state),
                    "budget_classification": failure_kind.value,
                },
            },
        ),
        value={
            "failure_kind": failure_kind.value,
            "turn_count": state.batch_turn_count,
            "budget_state": dict(state.batch_budget_state),
            "budget_classification": failure_kind.value,
        },
    )


def _stage_summarize(state: AgentEditState, context: TurnContext) -> StageResult:
    start = time.monotonic()
    queue_result = queue_stage_result(
        recovery_report=(state.report or {}).get("recovery"),
        change_report=(state.report or {}).get("change"),
    )
    _record(context, queue_result)
    derive_gates(context, queue_blockers=queue_result.issues)
    if state.report is None:
        state.report = {}
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _recovery_report_from_ui_payload(
    ui_payload: Mapping[str, Any] | None,
    schema_provider: Any,
) -> list[dict[str, Any]]:
    return _recovery_report_from_ui_payload_impl(ui_payload, schema_provider)


def _stage_summarize_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    start = time.monotonic()
    recovery_report = (state.report or {}).get("recovery")
    if not recovery_report and state.ui_payload is not None:
        recovery_report = _recovery_report_from_ui_payload(
            state.ui_payload, state.schema_provider
        )
    queue_result = queue_stage_result(
        recovery_report=recovery_report,
        change_report=(state.report or {}).get("change"),
    )
    _record(context, queue_result)
    derive_gates(context, queue_blockers=queue_result.issues)
    if state.report is None:
        state.report = {}
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "projection": str(state.projection_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "mode": "agent_edit_v2_delta",
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _stage_audit(
    state: AgentEditState,
    context: TurnContext,
    *,
    response: dict[str, Any] | None = None,
    failure: FailureEnvelope | None = None,
) -> ArtifactRef:
    metadata: dict[str, Any] = {
        "provider": state.provider_metadata or {},
        "lowering": _build_lowering_audit_entries(state.lowering_evidence),
    }
    if _agent_edit_v2_enabled():
        metadata["agent_edit_v2"] = normalize_agent_edit_v2_metadata(
            {
                "enabled": True,
                "op_count": len(state.delta_ops),
                "delta_ops": state.delta_audit or {},
            }
        )
    if _agent_edit_batch_repl_enabled():
        metadata["batch_repl"] = {
            "enabled": True,
            "turn_count": state.batch_turn_count,
            "signature_catalog_available": bool(state.batch_signature_catalog),
            "feedback": state.batch_feedback,
            "final_summary": state.batch_final_summary,
            "exit_mode": state.batch_exit_mode,
            "done_summary": state.batch_done_summary,
            "budget_state": _json_safe(state.batch_budget_state),
        }
    if state.revision_evidence is not None:
        metadata["revision_evidence"] = state.revision_evidence.to_dict()
    return write_audit(
        state.turn_dir / "audit",
        context=context,
        turn_state="candidate",
        stage_results=context.stage_results,
        failure=failure,
        response=response,
        artifacts={
            name: Path(path)
            for name, path in (state.artifacts or {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "messages": str(state.messages_path),
            }).items()
            if Path(path).exists()
        },
        metadata=metadata,
    )


def _write_unknown_transition_audits(
    *,
    session_root: Path,
    session_id: str,
    baseline_turn_id: str | None,
    unknown_transitions: tuple[dict[str, Any], ...],
    request_payload: Mapping[str, Any],
) -> None:
    _write_unknown_transition_audits_impl(
        session_root=session_root,
        session_id=session_id,
        baseline_turn_id=baseline_turn_id,
        unknown_transitions=unknown_transitions,
        request_payload=request_payload,
        write_audit_fn=write_audit,
    )


def _failure_response(
    state: AgentEditState,
    context: TurnContext,
    failure: FailureEnvelope,
    *,
    contract: str = "batch_repl",
) -> dict[str, Any]:
    return _failure_response_impl(
        state,
        context,
        failure,
        contract=contract,
        build_dev_failure_response=_build_dev_failure_response,
        build_batch_repl_failure_response=_build_batch_repl_failure_response,
    )


def _validated_agent_edit_response(
    response: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    return _validated_agent_edit_response_impl(response, stage=stage)


def _product_failure_response(failure: AgentError) -> dict[str, Any]:
    return _product_failure_response_impl(failure)


def _build_compatibility_response_fields(state: AgentEditState) -> dict[str, Any]:
    return _build_compatibility_response_fields_impl(state)


def _build_candidate_payload(
    state: AgentEditState,
    *,
    compatibility_fields: Mapping[str, Any],
    has_candidate: bool,
    turn_identity: TurnIdentity,
) -> dict[str, Any] | None:
    return _build_candidate_payload_impl(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
        turn_identity=turn_identity,
    )


def _stage_snapshot_payloads(context: TurnContext) -> list[dict[str, Any]]:
    return _stage_snapshot_payloads_impl(context)




def _resolver_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    return _resolver_candidates_from_batch_result_impl(batch_result)


def _workflow_schema_candidates_from_batch_result(batch_result: Any) -> list[dict[str, Any]]:
    return _workflow_schema_candidates_from_batch_result_impl(batch_result)


def _candidate_stable_key(candidate: Mapping[str, Any]) -> str:
    return _candidate_stable_key_impl(candidate)


def _enrich_schema_provider_from_resolver_candidates(
    state: AgentEditState,
    session: Any,
    candidates: list[dict[str, Any]],
) -> None:
    _enrich_schema_provider_from_resolver_candidates_impl(state, session, candidates)


def _legacy_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    return _legacy_failure_response_impl(
        state,
        context,
        failure=failure,
        build_compatibility_response_fields=_build_compatibility_response_fields,
        stage_audit=_stage_audit,
    )


def _build_batch_repl_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    return _build_batch_repl_failure_response_impl(
        state,
        context,
        failure=failure,
        build_compatibility_response_fields=_build_compatibility_response_fields,
        stage_audit=_stage_audit,
    )


def _build_dev_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: AgentError,
) -> dict[str, Any]:
    return _build_dev_failure_response_impl(
        state,
        context,
        failure=failure,
        build_compatibility_response_fields=_build_compatibility_response_fields,
        stage_audit=_stage_audit,
    )


def _session_artifact_response_fields(state: AgentEditState) -> dict[str, Any]:
    return _session_artifact_response_fields_impl(state)


def _build_batch_repl_response(
    state: AgentEditState,
    context: TurnContext,
) -> dict[str, Any]:
    return _build_batch_repl_response_impl(
        state,
        context,
        build_compatibility_response_fields=_build_compatibility_response_fields,
        canonical_route=_canonical_agent_edit_route,
        route_blocks_apply=_route_blocks_apply,
        route_change_focus_label=_route_change_focus_label,
        build_precedent_semantic_check_entries=_build_precedent_semantic_check_entries,
    )


def _build_dev_success_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    contract: str,
) -> dict[str, Any]:
    return _build_dev_success_response_impl(
        state,
        context,
        contract=contract,
        build_compatibility_response_fields=_build_compatibility_response_fields,
        canonical_route=_canonical_agent_edit_route,
        route_blocks_apply=_route_blocks_apply,
        route_change_focus_label=_route_change_focus_label,
        build_precedent_semantic_check_entries=_build_precedent_semantic_check_entries,
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


def _build_object_info_in_process() -> dict[str, Any] | None:
    return _build_object_info_in_process_impl()


def _default_runtime_schema_provider() -> Any:
    return _default_runtime_schema_provider_impl(
        build_object_info_in_process=_build_object_info_in_process,
        runtime_object_info_path=_RUNTIME_OBJECT_INFO_PATH,
    )


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
    _ws_send_impl(event, payload, client_id=client_id, logger=LOGGER)


def _brief_batch_statements(turn_record: dict[str, Any]) -> list[dict[str, Any]]:
    return _brief_batch_statements_impl(turn_record)


def _agent_edit_turn_event_payload(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    entry_type: str = "batch",
    status: str = "progress",
) -> dict[str, Any]:
    return _agent_edit_turn_event_payload_impl(
        state,
        context,
        turn_record,
        entry_type=entry_type,
        status=status,
    )


def _emit_agent_edit_turn_event(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    client_id: str | None = None,
    entry_type: str = "batch",
    status: str = "progress",
) -> None:
    try:
        payload = _agent_edit_turn_event_payload_impl(
            state,
            context,
            turn_record,
            entry_type=entry_type,
            status=status,
        )
        _ws_send("vibecomfy.agent_edit.turn", payload, client_id=client_id)
    except Exception:
        LOGGER.debug("emit agent-edit turn event failed (best-effort)", exc_info=True)


__all__ = [
    "AgentEditState",
    "DeepSeekClient",
    "handle_agent_edit",
]
