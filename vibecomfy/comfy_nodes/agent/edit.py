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
    ApplyEligibility,
    ArtifactRef,
    FailureEnvelope,
    FailureKind,
    StageResult,
    TurnContext,
    TurnOutcome,
    apply_eligibility_payload,
    classify_failure,
    derive_apply_eligibility,
    ensure_agent_edit_response_contract,
    failure_envelope,
    product_failure_envelope_fields,
    public_outcome_from_turn_outcome,
    success_envelope,
    turn_envelope,
)
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.porting.widgets.aliases import widget_names_for_class
from .gates import (
    apply_stage_gate_updates,
    derive_gates,
    initialize_gates,
    update_state_match_gate,
)
from .provider import (
    AgentTurnResult,
    BatchTurnResult,
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
    ui_payload: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    artifacts: dict[str, str] | None = None
    projection_text: str = ""
    delta_ops: tuple[Any, ...] = ()
    delta_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    delta_audit: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    # Batch REPL state (gated behind VIBECOMFY_AGENT_EDIT_BATCH_REPL=1)
    batch_session: EditSession | None = None
    batch_signature_catalog: str = ""
    executor_research_summary: str = ""
    executor_research_sources: tuple[dict[str, Any], ...] = ()
    executor_precedent_slices: tuple[dict[str, Any], ...] = ()
    executor_adaptation_plan: dict[str, Any] | None = None
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
    # T15: route label carried on state so response builders can apply route-aware
    # validation/reporting without changing their call signatures.
    route: str | None = None


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
    if not value:
        return uuid.uuid4().hex
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return safe[:80] or uuid.uuid4().hex


def _artifact(path: Path) -> ArtifactRef:
    return artifact_ref_for_path(path)


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _total_landed_edit_count(state: AgentEditState) -> int:
    count = len(state.batch_field_changes)
    if count > 0:
        return count
    total = 0
    for turn in state.batch_turns:
        landed = turn.get("landed_op_count")
        if isinstance(landed, int) and landed > 0:
            total += landed
    return total


def _field_change_is_noop(
    change: FieldChange,
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> bool:
    """Return True when *change* is a no-op.

    By default a change is a no-op when the old value is present and
    matches the new value.  When ``lint_dropped_op_ids`` is provided,
    any field change whose ``(uid, field_path)`` appears in that set is
    ALSO classified as a no-op — lint-owned classification wins.
    """
    if lint_dropped_op_ids is not None:
        key = (change.uid, change.field_path)
        if key in lint_dropped_op_ids:
            return True
    return change.old is not _ABSENT_FIELD_OLD and change.old == change.new


def _real_field_changes(
    changes: tuple[FieldChange, ...],
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> tuple[FieldChange, ...]:
    return tuple(
        change
        for change in changes
        if not _field_change_is_noop(change, lint_dropped_op_ids=lint_dropped_op_ids)
    )


def _noop_field_changes(
    changes: tuple[FieldChange, ...],
    *,
    lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None,
) -> tuple[FieldChange, ...]:
    return tuple(
        change
        for change in changes
        if _field_change_is_noop(change, lint_dropped_op_ids=lint_dropped_op_ids)
    )


def _batch_candidate_graph_changed(state: AgentEditState) -> bool:
    if not isinstance(state.ui_payload, Mapping):
        return False
    return structural_graph_hash(state.ui_payload) != structural_graph_hash(state.graph)


def _landed_edit_lead(state: AgentEditState) -> str:
    count = _total_landed_edit_count(state)
    if count <= 0:
        return ""
    noun = "edit" if count == 1 else "edits"
    return f"Applied {count} {noun}."


def _display_value(value: Any, *, limit: int = 48) -> str:
    if isinstance(value, str):
        text = value
    elif value is None:
        text = "null"
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            text = json.dumps(_json_safe(value), sort_keys=True)
        except (TypeError, ValueError):
            text = str(value)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: max(0, limit - 1)] + "…"
    return text


def _node_label_by_uid(*graphs: Mapping[str, Any] | None) -> dict[str, str]:
    labels: dict[str, str] = {}
    for graph in graphs:
        if not isinstance(graph, Mapping):
            continue
        for node in _iter_ui_graph_nodes(graph):
            class_type = node.get("type") or node.get("class_type")
            title = node.get("title")
            label = title if isinstance(title, str) and title.strip() else class_type
            if isinstance(label, str) and label.strip():
                for uid in _ui_node_uid_aliases(node):
                    labels[str(uid)] = label.strip()
    return labels


def _change_subject(change: FieldChange, labels: Mapping[str, str] | None = None) -> str:
    uid = str(change.uid or "node").strip() or "node"
    field = str(change.field_path or "field").strip() or "field"
    label = labels.get(uid) if labels else None
    if isinstance(label, str) and label.strip():
        return f"{label.strip()} {field}"
    if labels is not None and _looks_internal_uid(uid):
        return f"node {field}"
    return f"{uid}.{field}"


def _looks_internal_uid(uid: str) -> bool:
    return bool(re.fullmatch(r"n\d+|.*_\d+|\d+", uid.strip()))


def _link_endpoint_parts(value: Any) -> tuple[str, int | str] | None:
    """Return ``(uid, output_slot)`` for supported FieldChange link endpoint shapes.

    Accepts both ``list`` / ``tuple`` and the batch editor's mapping form because
    ``FieldChange.__post_init__`` freezes JSON-ish mappings into ``MappingProxyType``.
    """
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (int, str))
        and isinstance(value[1], int)
    ):
        return str(value[0]), value[1]
    if isinstance(value, Mapping):
        uid = value.get("uid")
        output_slot = value.get("output_slot")
        if isinstance(uid, (int, str)) and isinstance(output_slot, (int, str)):
            return str(uid), output_slot
    return None


def _is_link_endpoint(value: Any) -> bool:
    return _link_endpoint_parts(value) is not None


def _resolve_output_slot_name(graph: Mapping[str, Any], uid: str, slot_index: int | str) -> str | None:
    """Return the human-readable output-slot name for *uid* / *slot_index*, or None."""
    if isinstance(slot_index, str):
        return slot_index
    for node in _iter_ui_graph_nodes(graph):
        if uid not in _ui_node_uid_aliases(node):
            continue
        outputs = node.get("outputs")
        if isinstance(outputs, list) and 0 <= slot_index < len(outputs):
            entry = outputs[slot_index]
            if isinstance(entry, Mapping):
                name = entry.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        break
    return None


def _resolve_endpoint_label(
    endpoint: Any,
    node_labels: Mapping[str, str],
    graph: Mapping[str, Any],
    *fallback_graphs: Mapping[str, Any] | None,
) -> str:
    """Resolve a link endpoint ``[uid, slot]`` to a label like ``'VAE Decode IMAGE'``."""
    parts = _link_endpoint_parts(endpoint)
    if parts is None:
        return "unknown source"
    uid, slot = parts
    node_label = node_labels.get(uid)
    slot_name = _resolve_output_slot_name(graph, uid, slot)
    if slot_name is None:
        for fallback_graph in fallback_graphs:
            if isinstance(fallback_graph, Mapping):
                slot_name = _resolve_output_slot_name(fallback_graph, uid, slot)
                if slot_name is not None:
                    break
    if node_label and slot_name:
        return f"{node_label} {slot_name}"
    if node_label:
        return node_label
    if slot_name:
        return slot_name
    return "unknown source"


def _ui_node_by_uid(graph: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(graph, Mapping):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for node in _iter_ui_graph_nodes(graph):
        uid = _ui_node_uid(node)
        if uid:
            result[str(uid)] = node
    return result


def _node_class_label(node: Mapping[str, Any]) -> str:
    class_type = node.get("type") or node.get("class_type")
    if isinstance(class_type, str) and class_type.strip():
        return class_type.strip()
    title = node.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return "node"


def _ui_display_widget_value_for_field(node: Mapping[str, Any], field: str) -> Any:
    widgets = node.get("widgets")
    widgets_values = node.get("widgets_values")
    if isinstance(widgets, list) and isinstance(widgets_values, list):
        for index, widget in enumerate(widgets):
            if (
                isinstance(widget, Mapping)
                and widget.get("name") == field
                and index < len(widgets_values)
            ):
                return widgets_values[index]
    return _ui_widget_value_for_field(node, field)


def _node_key_values(node: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for field in ("scale_by", "scale", "upscale_method", "filename_prefix", "seed", "steps", "denoise"):
        value = _ui_display_widget_value_for_field(node, field)
        if value is _MISSING_FIELD_CHANGE_OLD:
            continue
        if field in {"scale_by", "scale"} and isinstance(value, (int, float)) and 0 < float(value) <= 1:
            values.append(f"{round(float(value) * 100):g}%")
        elif field == "filename_prefix":
            values.append(str(value))
        else:
            values.append(_display_value(value, limit=28))
    return values[:3]


def _node_phrase(node: Mapping[str, Any]) -> str:
    label = _node_class_label(node)
    values = _node_key_values(node)
    if values:
        return f"{label} ({', '.join(values)})"
    return label


def _article_for(text: str) -> str:
    first = text[:1].lower()
    return "an" if first in {"a", "e", "i", "o", "u"} else "a"


def _first_link_source_label(
    node: Mapping[str, Any],
    graph: Mapping[str, Any] | None,
    labels: Mapping[str, str],
) -> str | None:
    if not isinstance(graph, Mapping):
        return None
    inputs = node.get("inputs")
    links = graph.get("links")
    if not isinstance(inputs, list) or not isinstance(links, list):
        return None
    link_id = None
    for input_slot in inputs:
        if isinstance(input_slot, Mapping) and isinstance(input_slot.get("link"), (int, float)):
            link_id = int(input_slot["link"])
            break
    if link_id is None:
        return None
    by_id: dict[int, Any] = {}
    for link in links:
        if isinstance(link, Mapping) and isinstance(link.get("id"), (int, float)):
            by_id[int(link["id"])] = link
        elif isinstance(link, (list, tuple)) and link and isinstance(link[0], (int, float)):
            by_id[int(link[0])] = link
    link = by_id.get(link_id)
    if isinstance(link, Mapping):
        source_id = link.get("origin_id")
        source_slot = link.get("origin_slot", 0)
    elif isinstance(link, (list, tuple)) and len(link) >= 3:
        source_id = link[1]
        source_slot = link[2]
    else:
        return None
    source_uid = None
    for candidate in _iter_ui_graph_nodes(graph):
        if candidate.get("id") == source_id:
            source_uid = _ui_node_uid(candidate)
            break
    if not source_uid:
        return None
    return _resolve_endpoint_label({"uid": source_uid, "output_slot": source_slot}, labels, graph)


def _structural_change_phrases(state: AgentEditState, labels: Mapping[str, str]) -> list[str]:
    before_by_uid = _ui_node_by_uid(state.graph)
    after_by_uid = _ui_node_by_uid(state.ui_payload)
    if not before_by_uid or not after_by_uid:
        return []
    added = [after_by_uid[uid] for uid in sorted(set(after_by_uid) - set(before_by_uid))]
    removed = [before_by_uid[uid] for uid in sorted(set(before_by_uid) - set(after_by_uid))]
    phrases: list[str] = []
    if added:
        parts: list[str] = []
        for node in added[:3]:
            node_text = _node_phrase(node)
            source = _first_link_source_label(node, state.ui_payload, labels)
            if source:
                node_text = f"{node_text} fed by {source}"
            parts.append(node_text)
        text = _join_human_list(parts)
        article = _article_for(parts[0]) if len(parts) == 1 else ""
        phrases.append(f"added {article + ' ' if article else ''}{text}")
    if removed:
        parts = [_node_phrase(node) for node in removed[:3]]
        phrases.append(f"removed {_join_human_list(parts)}")
    return phrases


def _join_human_list(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"


def _human_change_phrase(
    change: FieldChange,
    labels: Mapping[str, str] | None = None,
    *,
    graph: Mapping[str, Any] | None = None,
    old_graph: Mapping[str, Any] | None = None,
    new_graph: Mapping[str, Any] | None = None,
) -> str:
    subject = _change_subject(change, labels)
    if graph is not None and labels is not None:
        old_endpoint_graph = old_graph if isinstance(old_graph, Mapping) else graph
        new_endpoint_graph = new_graph if isinstance(new_graph, Mapping) else graph
        old_link = _is_link_endpoint(change.old)
        new_link = _is_link_endpoint(change.new)
        if old_link and new_link:
            old_label = _resolve_endpoint_label(change.old, labels, old_endpoint_graph, graph, new_graph)
            new_label = _resolve_endpoint_label(change.new, labels, new_endpoint_graph, graph, old_graph)
            return f"rewired {subject} to come from {new_label} instead of {old_label}"
        if new_link and not old_link:
            new_label = _resolve_endpoint_label(change.new, labels, new_endpoint_graph, graph, old_graph)
            return f"connected {subject} to {new_label}"
        if old_link and not new_link:
            old_label = _resolve_endpoint_label(change.old, labels, old_endpoint_graph, graph, new_graph)
            return f"disconnected {subject} from {old_label}"
    if change.old is None or change.old is _ABSENT_FIELD_OLD:
        return f"set {subject} to {_display_value(change.new)}"
    return (
        f"updated {subject} from "
        f"{_display_value(change.old)} to {_display_value(change.new)}"
    )


def _sentence_case(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped[0].upper() + stripped[1:]


def _humanized_edit_message(state: AgentEditState) -> str:
    changes = _real_field_changes(tuple(state.batch_field_changes or ()))
    labels = _node_label_by_uid(state.graph, state.ui_payload)
    structural_phrases = _structural_change_phrases(state, labels)
    if structural_phrases:
        return _sentence_case(
            ensure_sentence_message(
                _join_human_list(structural_phrases),
                fallback="Updated the workflow structure.",
            )
        )
    if not changes:
        return ensure_sentence_message(
            "",
            fallback="The candidate is ready to review.",
        )
    if len(changes) == 1:
        return _sentence_case(
            ensure_sentence_message(
                _human_change_phrase(
                    changes[0],
                    labels,
                    graph=state.graph,
                    old_graph=state.graph,
                    new_graph=state.ui_payload,
                ),
                fallback="Updated the workflow.",
            )
        )
    phrases = [
        _human_change_phrase(
            change,
            labels,
            graph=state.graph,
            old_graph=state.graph,
            new_graph=state.ui_payload,
        )
        for change in changes[:3]
    ]
    if len(changes) == 2:
        text = f"{phrases[0]} and {phrases[1]}"
    else:
        text = f"{phrases[0]}, {phrases[1]}, and {phrases[2]}"
        remaining = len(changes) - 3
        if remaining > 0:
            noun = "other field" if remaining == 1 else "other fields"
            text = f"{text}, plus {remaining} {noun}"
    return _sentence_case(ensure_sentence_message(text, fallback=f"Updated {len(changes)} workflow fields."))


def _terminal_answer_message(state: AgentEditState) -> str | None:
    if state.lint_noop_messages or state.batch_noop_field_changes or state.batch_field_changes:
        return None
    if state.batch_exit_mode != _BATCH_EXIT_NOOP:
        return None

    for turn in reversed(state.batch_turns or []):
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        has_terminal_done = False
        if isinstance(statements, list):
            has_terminal_done = any(
                isinstance(stmt, Mapping) and stmt.get("op_kind") == "done"
                for stmt in statements
            )
        batch = turn.get("batch")
        if not has_terminal_done and isinstance(batch, str):
            has_terminal_done = batch.strip().startswith("done(")
        if not has_terminal_done:
            continue
        message = turn.get("message")
        if isinstance(message, str) and message.strip():
            return ensure_sentence_message(message.strip(), fallback="No graph changes were needed.")
    return None


def _humanized_noop_message(state: AgentEditState) -> str:
    # Prefer lint normalization messages when available (they carry
    # class/title/field/slot context and avoid raw gate text or uids).
    if state.lint_noop_messages:
        msgs = state.lint_noop_messages
        if len(msgs) == 1:
            return _sentence_case(ensure_sentence_message(msgs[0], fallback="No change needed."))
        return "The requested changes are already in place; no updates needed."

    changes = tuple(state.batch_noop_field_changes or ())
    labels = _node_label_by_uid(state.graph, state.ui_payload)
    if len(changes) == 1:
        change = changes[0]
        return _sentence_case(
            ensure_sentence_message(
                f"{_change_subject(change, labels)} is already {_display_value(change.new)}; no change needed",
                fallback="No change needed.",
            )
        )
    if len(changes) > 1:
        return "The requested fields already match the current graph; no change needed."
    answer = _terminal_answer_message(state)
    if answer:
        return answer
    summary = (state.batch_done_summary or "").strip()
    gate_jargon = bool(re.search(r"\bGate\s+[AB]\b|identity verified|No operations were applied", summary, re.I))
    if summary and not gate_jargon:
        return ensure_sentence_message(summary, fallback="No graph changes were needed.")
    if gate_jargon:
        return "Nothing needed changing; the workflow already matches that."
    return "No graph changes were needed."


def _operation_detail_payload(changes: tuple[FieldChange, ...]) -> list[dict[str, Any]]:
    return [
        {
            **change.to_dict(),
            "summary": (
                f"Set {_change_subject(change)} to {_display_value(change.new)}."
                if change.old is None or change.old is _ABSENT_FIELD_OLD
                else (
                    f"Changed {_change_subject(change)} from "
                    f"{_display_value(change.old)} to {_display_value(change.new)}."
                )
            ),
        }
        for change in _real_field_changes(changes)
    ]


def _change_details_payload(state: AgentEditState, context: TurnContext) -> dict[str, Any]:
    gate_snapshot = context.gate_snapshot()
    gate_a = gate_snapshot.get("edit_scope_ok") or gate_snapshot.get("python_load_ok")
    gate_b = gate_snapshot.get("isomorphic_ok") or gate_snapshot.get("ui_fidelity_ok")
    operations = _operation_detail_payload(tuple(state.batch_field_changes or ()))
    return {
        "landed_operation_count": len(operations),
        "done_summary": state.batch_done_summary or "",
        "final_summary": state.batch_final_summary or "",
        "gate_a": _json_safe(gate_a),
        "gate_b": _json_safe(gate_b),
        "operations": operations,
        "batch_turns": _json_safe(state.batch_turns),
    }


def _batch_warning_sentence(
    state: AgentEditState,
    *,
    failure: FailureEnvelope | None = None,
    outcome: TurnOutcome | None = None,
) -> str:
    if failure is not None:
        if failure.kind is FailureKind.STALE_STATE_MISMATCH:
            return ensure_sentence_message(
                failure.user_facing_message,
                fallback="The canvas changed since the current baseline. Rebaseline and resubmit from the current canvas.",
            )
        if state.batch_exit_mode == _BATCH_EXIT_BUDGET:
            return ensure_sentence_message(
                "I ran out of turn budget before completing the remaining changes",
                fallback=state.batch_final_summary or failure.message,
            )
        return ensure_sentence_message(
            failure.user_facing_message,
            fallback=failure.message or "The graph is unchanged.",
        )
    if outcome is not None and outcome.kind == "edit+clarify":
        return ensure_sentence_message(
            outcome.question,
            fallback=state.user_message or "I still need clarification before continuing.",
        )
    return ""


def _synthesize_batch_repl_message(
    state: AgentEditState,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
) -> str:
    lead = _landed_edit_lead(state)
    if failure is not None:
        warning = _batch_warning_sentence(state, failure=failure)
        if lead:
            return f"{lead} {warning}".strip()
        return warning
    if outcome is None:
        return ensure_sentence_message(state.user_message, fallback="The agent edit turn completed.")
    if outcome.kind == "edit":
        return _humanized_edit_message(state)
    if outcome.kind == "edit+clarify":
        warning = _batch_warning_sentence(state, outcome=outcome)
        if lead:
            return f"{lead} {warning}".strip()
        return warning
    if outcome.kind == "clarify":
        return ensure_sentence_message(
            outcome.question,
            fallback=state.user_message or "I need clarification before continuing.",
        )
    if outcome.kind == "budget":
        return ensure_sentence_message(
            "I ran out of turn budget before completing the requested changes",
            fallback=state.batch_final_summary or state.user_message,
        )
    if outcome.kind == "noop":
        return _humanized_noop_message(state)
    return ensure_sentence_message(state.user_message, fallback="The agent edit turn completed.")


def _normalize_test_client_response(response: dict[str, str]) -> AgentTurnResult:
    python = response.get("python")
    message = response.get("message")
    if not isinstance(python, str):
        raise ValueError("Agent JSON must include string key `python`.")
    if not isinstance(message, str):
        raise ValueError("Agent JSON must include string key `message`.")
    return AgentTurnResult(
        python=python,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client"},
    )


def _normalize_test_client_batch_response(response: dict[str, str]) -> BatchTurnResult:
    batch = response.get("batch")
    message = response.get("message")
    if not isinstance(batch, str):
        raise ValueError("Batch agent response must include string key `batch`.")
    if not isinstance(message, str):
        raise ValueError("Batch agent response must include string key `message`.")
    return BatchTurnResult(
        batch=batch,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client", "response_contract": "batch_repl"},
    )


def _render_batch_diff(before: str, after: str, *, max_chars: int = 2000) -> str:
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before.py",
            tofile="after.py",
            n=2,
        )
    ).strip()
    if len(diff) <= max_chars:
        return diff
    return diff[: max(0, max_chars - 15)].rstrip() + "\n... [truncated]"


def _format_statement_source(source: str, *, max_chars: int = 72) -> str:
    """Truncate a statement source string for inline display."""
    if len(source) <= max_chars:
        return source
    return source[: max(0, max_chars - 3)] + "..."


def _iter_ui_nodes(ui_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return root and nested UI node dictionaries from a LiteGraph payload."""
    found: list[Mapping[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            nodes = value.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, Mapping):
                        found.append(node)
                        visit(node)
            for key in ("graphs", "subgraphs"):
                nested = value.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        visit(item)
                elif isinstance(nested, Mapping):
                    for item in nested.values():
                        visit(item)

    visit(ui_payload)
    return found


def _present_class_types(session: Any) -> list[str]:
    """Enumerate class types currently present in an EditSession working graph."""
    working_ui = getattr(session, "working_ui", None)
    if not isinstance(working_ui, Mapping):
        return []
    types: set[str] = set()
    for node in _iter_ui_nodes(working_ui):
        class_type = node.get("type") or node.get("class_type")
        if isinstance(class_type, str) and class_type:
            types.add(class_type)
    return sorted(types)


def _format_node_variable_index(session: Any) -> str:
    """Return ``var = ClassType`` lines for the current EditSession graph."""
    working_ui = getattr(session, "working_ui", None)
    name_by_uid = getattr(session, "name_by_uid", None)
    if not isinstance(working_ui, Mapping) or not isinstance(name_by_uid, Mapping):
        return ""
    rows: list[tuple[str, str, str]] = []
    for node in _iter_ui_nodes(working_ui):
        uid = _ui_node_uid(node)
        if not uid:
            continue
        name = name_by_uid.get(uid)
        class_type = node.get("type") or node.get("class_type")
        if isinstance(name, str) and name and isinstance(class_type, str) and class_type:
            rows.append((name, uid, class_type))
    rows.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(f"{name} = {class_type}" for name, _uid, class_type in rows)


def _format_available_node_names(rows: Any, *, max_line_chars: int = 96) -> str:
    """Format NodeSignatureRow-like objects as a compact deterministic name list."""
    names = sorted(
        {
            class_type
            for row in rows or []
            if isinstance((class_type := getattr(row, "class_type", None)), str)
            and class_type
        }
    )
    if not names:
        return ""
    lines: list[str] = []
    current = names[0]
    for name in names[1:]:
        candidate = f"{current}, {name}"
        if len(candidate) > max_line_chars:
            lines.append(current)
            current = name
        else:
            current = candidate
    lines.append(current)
    return "\n".join(lines)


def _format_query_output(text: str, *, max_chars: int | None = 4000) -> str:
    """Bound read-only query output before it is included in agent feedback."""
    if max_chars is None:
        return text
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 18)].rstrip() + "\n... [truncated]"


def _format_batch_report(
    batch_result: Any,
    *,
    consecutive_errors: int,
    budget_remaining: int,
    lint_dropped_count: int = 0,
    lint_diagnostics: tuple[dict[str, Any], ...] = (),
) -> str:
    """Build a deterministic text teaching report from a :class:`BatchResult`.

    The report is grounded only in ``BatchResult.statements`` and
    ``CompactDiagnostic`` fields — it never invents schema hints or other
    generated content.
    """
    statement_lines: list[str] = []
    landed_count = 0
    failed_count = 0
    for statement in batch_result.statements:
        if statement.landed:
            landed_count += 1
        if not statement.ok:
            failed_count += 1
        marker = "✓" if statement.ok else "✗"
        status = "landed" if statement.landed else "not landed"
        op_kind = statement.op_kind or "statement"
        source_text = _format_statement_source(statement.source)
        line = (
            f"{marker} Statement {statement.statement_index}: "
            f"{op_kind} — {status}"
        )
        extras: list[str] = []
        if source_text:
            extras.append(f'source: "{source_text}"')
        if statement.touched_uids:
            extras.append(
                "touched uids: [{}]".format(", ".join(statement.touched_uids))
            )
        if statement.dependency_cause:
            extras.append(f"cause: {statement.dependency_cause}")
        if statement.diagnostics:
            primary = statement.diagnostics[0]
            extras.append(f"{primary.code}: {primary.message}")
        if statement.teaching_hint:
            extras.append(f"hint: {statement.teaching_hint}")
        if extras:
            line += f" ({'; '.join(extras)})"
        statement_lines.append(line)
        query_output = statement.detail.get("query_output") if isinstance(statement.detail, dict) else None
        if isinstance(query_output, str) and query_output:
            query_name = statement.detail.get("query") if isinstance(statement.detail, dict) else None
            statement_lines.append(
                _format_query_output(
                    query_output,
                    max_chars=None if query_name == "python" else 4000,
                )
            )

    diagnostic_lines = [
        f"! {diagnostic.code}: {diagnostic.message}"
        for diagnostic in batch_result.diagnostics
    ]
    # Append lint diagnostics so the model sees them inline.
    if lint_diagnostics:
        diagnostic_lines.extend(
            f"! [lint] {d['code']}: {d['message']}"
            for d in lint_diagnostics
        )
    lint_note = (
        f", {lint_dropped_count} lint-dropped no-op(s)"
        if lint_dropped_count
        else ""
    )
    summary = (
        f"Turn summary: {landed_count} landed, {failed_count} failed, "
        f"{len(batch_result.diagnostics)} diagnostic(s)"
        f"{lint_note}, "
        f"{budget_remaining} turn(s) remaining, "
        f"{consecutive_errors} consecutive error turn(s)."
    )
    query_only_note = ""
    statements = tuple(batch_result.statements or ())
    if statements and landed_count == 0 and all((statement.op_kind or "") == "query" for statement in statements):
        query_only_note = (
            "No edits were made this turn. Search/query output is discovery only. "
            "If it returned a usable signature or precedent, construct and wire the edit now; "
            "do not search again unless the last query failed to identify a usable path."
        )
    lines = [summary, *statement_lines, query_only_note, *diagnostic_lines]
    return "\n".join(line for line in lines if line)


def _format_batch_report_json(
    batch_result: Any,
    *,
    consecutive_errors: int,
    budget_remaining: int,
    lint_dropped_count: int = 0,
    lint_diagnostics: tuple[dict[str, Any], ...] = (),
) -> dict[str, Any]:
    """Build a deterministic JSON teaching report from a :class:`BatchResult`.

    Every field is derived from ``BatchResult.statements`` and
    ``CompactDiagnostic`` fields — no invented content.
    """
    landed_count = sum(1 for s in batch_result.statements if s.landed)
    failed_count = sum(1 for s in batch_result.statements if not s.ok)
    result: dict[str, Any] = {
        "summary": {
            "landed": landed_count,
            "failed": failed_count,
            "budget_remaining": budget_remaining,
            "consecutive_errors": consecutive_errors,
        },
        "statements": [
            {
                "statement_index": item.statement_index,
                "source": item.source,
                "ok": item.ok,
                "landed": item.landed,
                "op_kind": item.op_kind,
                "detail": _json_safe(dict(item.detail)),
                "touched_uids": list(item.touched_uids),
                "dependency_cause": item.dependency_cause,
                "teaching_hint": item.teaching_hint,
                "diagnostics": [
                    _compact_diag_to_dict(diag) for diag in item.diagnostics
                ],
            }
            for item in batch_result.statements
        ],
        "diagnostics": [
            _compact_diag_to_dict(item) for item in batch_result.diagnostics
        ],
    }
    if lint_dropped_count:
        result["summary"]["lint_dropped"] = lint_dropped_count
    if lint_diagnostics:
        result["lint_diagnostics"] = [
            dict(d) for d in lint_diagnostics
        ]
    return result


_CLARIFY_CALL_RE = re.compile(
    r'(?m)^\s*clarify\("((?:[^"\\]|\\.)*)"\)\s*$'
)

_BATCH_EXIT_PURE_CLARIFY = "pure_clarify"
_BATCH_EXIT_EDIT_CLARIFY = "edit_clarify"
_BATCH_EXIT_DONE = "done"
_BATCH_EXIT_BUDGET = "budget"
_BATCH_EXIT_NOOP = "noop"


@dataclass(frozen=True)
class TerminalClarifySplit:
    batch: str
    message: str | None


def _extract_clarify_message(batch: str) -> str | None:
    matches = _CLARIFY_CALL_RE.findall(batch)
    if not matches:
        return None
    try:
        return json.loads(f'"{matches[0]}"')
    except json.JSONDecodeError:
        return matches[0]


def _is_terminal_clarify_expr(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    call = node.value
    if not isinstance(call.func, ast.Name) or call.func.id != "clarify":
        return False
    return (
        len(call.args) == 1
        and not call.keywords
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    )


def _contains_clarify_call(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "clarify"
        for child in ast.walk(node)
    )


def _offset_from_ast_position(batch: str, lineno: int, col_offset: int) -> int:
    lines = batch.splitlines(keepends=True)
    if lineno <= 0:
        return 0
    before = sum(len(line) for line in lines[: lineno - 1])
    line = lines[lineno - 1] if lineno - 1 < len(lines) else ""
    # AST column offsets are UTF-8 byte offsets. Convert them back to Python
    # character offsets before slicing the original source string.
    char_col = len(line.encode("utf-8")[:col_offset].decode("utf-8", errors="ignore"))
    return before + char_col


def _decode_clarify_literal(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw


def _split_terminal_clarify_line_regex(batch: str) -> TerminalClarifySplit:
    matches = list(_CLARIFY_CALL_RE.finditer(batch))
    if not matches:
        return TerminalClarifySplit(batch=batch, message=None)
    terminal_match = matches[-1]
    if any(match.start() != terminal_match.start() for match in matches[:-1]):
        return TerminalClarifySplit(batch=batch, message=None)
    trailing_lines = batch[terminal_match.end() :].splitlines()
    if any(line.strip() and not line.lstrip().startswith("#") for line in trailing_lines):
        return TerminalClarifySplit(batch=batch, message=None)
    return TerminalClarifySplit(
        batch=batch[: terminal_match.start()].rstrip(),
        message=_decode_clarify_literal(terminal_match.group(1)),
    )


def split_terminal_clarify(batch: str) -> TerminalClarifySplit:
    """Split a final top-level clarify("...") call from editable batch code."""
    try:
        module = ast.parse(batch)
    except SyntaxError:
        return _split_terminal_clarify_line_regex(batch)
    if not module.body:
        return TerminalClarifySplit(batch=batch, message=None)

    terminal = module.body[-1]
    if not _is_terminal_clarify_expr(terminal):
        return TerminalClarifySplit(batch=batch, message=None)
    if any(_contains_clarify_call(stmt) for stmt in module.body[:-1]):
        return TerminalClarifySplit(batch=batch, message=None)

    call = terminal.value
    assert isinstance(call, ast.Call)
    message_node = call.args[0]
    assert isinstance(message_node, ast.Constant)
    start = _offset_from_ast_position(batch, terminal.lineno, terminal.col_offset)
    editable_batch = batch[:start].rstrip()
    if editable_batch.endswith(";"):
        editable_batch = editable_batch[:-1].rstrip()
    return TerminalClarifySplit(batch=editable_batch, message=message_node.value)


def _batch_has_landed_edits(state: "AgentEditState") -> bool:
    return any(
        isinstance(turn, Mapping) and int(turn.get("landed_op_count", 0)) > 0
        for turn in state.batch_turns
    )


def _batch_budget_failure_kind(turns: list[dict[str, Any]]) -> FailureKind:
    schema_gap_markers = (
        "schema",
        "schema-backed",
        "socket type",
        "compatible output",
        "confidence",
    )
    unrepresentable_codes = {
        "statement_not_allowed",
        "call_not_allowed",
        "nested_call_not_allowed",
        "raw_coordinate_kwarg_not_allowed",
        "intent_class_construction_not_allowed",
        "cross_scope_add_node_unsupported",
        "scope_escape_not_allowed",
        "original_virtual_node_immutable",
        "kwargs_unpack_not_allowed",
        "dict_unpack_not_allowed",
        "lambda_not_allowed",
        "comprehension_not_allowed",
        "f_string_not_allowed",
        "for_else_not_allowed",
        "import_not_allowed",
    }
    category_turn_hits = {
        FailureKind.MODEL_MISTAKE: 0,
        FailureKind.UNREPRESENTABLE: 0,
        FailureKind.SCHEMA_GAP: 0,
    }
    for turn in turns:
        turn_categories: set[FailureKind] = set()
        diagnostics = list(turn.get("diagnostics") or [])
        for statement in turn.get("statements") or []:
            diagnostics.extend(statement.get("diagnostics") or [])
        for diagnostic in diagnostics:
            code = str(diagnostic.get("code", "")).lower()
            message = str(diagnostic.get("message", "")).lower()
            teaching_hint = str(diagnostic.get("teaching_hint", "")).lower()
            haystack = " ".join((code, message, teaching_hint))
            if any(marker in haystack for marker in schema_gap_markers):
                turn_categories.add(FailureKind.SCHEMA_GAP)
                continue
            if code in unrepresentable_codes or "not allowed" in haystack or "immutable" in haystack:
                turn_categories.add(FailureKind.UNREPRESENTABLE)
                continue
            turn_categories.add(FailureKind.MODEL_MISTAKE)
        for category in turn_categories:
            category_turn_hits[category] += 1
    ranked = sorted(
        category_turn_hits.items(),
        key=lambda item: (item[1], item[0] == FailureKind.SCHEMA_GAP, item[0] == FailureKind.UNREPRESENTABLE),
        reverse=True,
    )
    if ranked and ranked[0][1] > 0:
        return ranked[0][0]
    return FailureKind.MODEL_MISTAKE


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _field_changes_payload(changes: tuple[FieldChange, ...]) -> list[dict[str, Any]]:
    return [change.to_dict() for change in changes]


_MISSING_FIELD_CHANGE_OLD = object()
_ABSENT_FIELD_OLD = object()  # marker for fields genuinely absent from the original UI graph


def _ui_node_uid(node: Mapping[str, Any]) -> str | None:
    properties = node.get("properties")
    if isinstance(properties, Mapping):
        uid = properties.get("vibecomfy_uid")
        if isinstance(uid, str) and uid:
            return uid
    node_id = node.get("id")
    if isinstance(node_id, str) and node_id:
        return node_id
    if isinstance(node_id, int):
        return str(node_id)
    return None


def _ui_node_uid_aliases(node: Mapping[str, Any]) -> tuple[str, ...]:
    aliases: list[str] = []
    primary = _ui_node_uid(node)
    if primary:
        aliases.append(primary)
    node_id = node.get("id")
    if isinstance(node_id, (int, str)) and str(node_id):
        node_id_key = str(node_id)
        if node_id_key not in aliases:
            aliases.append(node_id_key)
    return tuple(aliases)


def _iter_ui_graph_nodes(graph: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return ()
    return tuple(node for node in nodes if isinstance(node, Mapping))


def _widget_index_from_field_path(field_path: str) -> int | None:
    match = re.fullmatch(r"widgets_values(?:\.|\[)(\d+)\]?", field_path)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _ui_widget_value_for_field(node: Mapping[str, Any], field_path: str) -> Any:
    widgets_values = node.get("widgets_values")
    explicit_index = _widget_index_from_field_path(field_path)
    if explicit_index is not None:
        if isinstance(widgets_values, list) and 0 <= explicit_index < len(widgets_values):
            return widgets_values[explicit_index]
        return _MISSING_FIELD_CHANGE_OLD
    if isinstance(widgets_values, Mapping):
        return widgets_values[field_path] if field_path in widgets_values else _MISSING_FIELD_CHANGE_OLD
    if isinstance(widgets_values, list):
        class_type = str(node.get("type") or node.get("class_type") or "")
        widget_names = widget_names_for_class(class_type) or []
        for index, name in enumerate(widget_names):
            if name == field_path and index < len(widgets_values):
                return widgets_values[index]
        widgets = node.get("widgets")
        if isinstance(widgets, list):
            for index, widget in enumerate(widgets):
                if (
                    isinstance(widget, Mapping)
                    and widget.get("name") == field_path
                    and index < len(widgets_values)
                ):
                    return widgets_values[index]
    return _MISSING_FIELD_CHANGE_OLD


def _original_ui_field_value(graph: Mapping[str, Any], change: FieldChange) -> Any:
    for node in _iter_ui_graph_nodes(graph):
        if _ui_node_uid(node) != change.uid:
            continue
        if change.field_path in node and not change.field_path.startswith("widgets_values"):
            return node[change.field_path]
        widget_value = _ui_widget_value_for_field(node, change.field_path)
        if widget_value is not _MISSING_FIELD_CHANGE_OLD:
            return widget_value
        return _MISSING_FIELD_CHANGE_OLD
    return _ABSENT_FIELD_OLD  # node not found in original UI graph — genuinely absent


def _repair_field_changes_from_original_ui(
    graph: Mapping[str, Any],
    changes: tuple[FieldChange, ...],
) -> tuple[FieldChange, ...]:
    if not changes:
        return ()
    repaired: list[FieldChange] = []
    changed = False
    for change in changes:
        if change.old is None:
            old = _original_ui_field_value(graph, change)
            if old is not _MISSING_FIELD_CHANGE_OLD and old is not _ABSENT_FIELD_OLD:
                repaired.append(
                    FieldChange(
                        uid=change.uid,
                        field_path=change.field_path,
                        old=old,
                        new=change.new,
                    )
                )
                changed = True
                continue
            # Genuinely absent from original UI — keep old=None as the
            # normalised absent marker (serialises as null via to_dict()).
            # _ABSENT_FIELD_OLD is the internal sentinel; FieldChange stores None.
            repaired.append(change)
            continue
        old = _original_ui_field_value(graph, change)
        if old is _MISSING_FIELD_CHANGE_OLD or old is _ABSENT_FIELD_OLD or old == change.old:
            repaired.append(change)
            continue
        repaired.append(
            FieldChange(
                uid=change.uid,
                field_path=change.field_path,
                old=old,
                new=change.new,
            )
        )
        changed = True
    return tuple(repaired) if changed else changes


def _write_turn_chat_artifact(
    state: AgentEditState,
    context: TurnContext,
    response: dict[str, Any],
    contract: str,
) -> None:
    """Best-effort write of ``chat.json`` for an allocated, completed edit turn.

    ``response.json`` is the durable turn artifact; ``chat.json`` is a
    JSON-canonical UI convenience.  Failures here are logged and swallowed.
    """
    turn_dir = state.turn_dir
    chat_path = turn_dir / "chat.json"

    agent_text_raw = response.get("user_facing_message") or response.get("message", "")
    agent_text: str = agent_text_raw if isinstance(agent_text_raw, str) else ""
    if not agent_text.strip():
        agent_text = "The agent edit turn completed."

    # Extract structured changes by contract shape.
    changes: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        outcome = response.get("outcome")
        if isinstance(outcome, Mapping):
            raw = outcome.get("changes")
            if isinstance(raw, list):
                changes = [_json_safe(c) for c in raw]
        if changes is None and state.batch_field_changes:
            changes = _field_changes_payload(state.batch_field_changes)
    elif contract == "delta":
        delta_ops = response.get("delta_ops")
        if isinstance(delta_ops, list):
            changes = _json_safe(delta_ops)

    agent_msg: dict[str, Any] = {
        "role": "agent",
        "text": agent_text,
        "turn_id": context.turn_id,
    }
    outcome_payload = response.get("outcome")
    if isinstance(outcome_payload, Mapping):
        agent_msg["outcome"] = dict(outcome_payload)
    if changes is not None:
        agent_msg["changes"] = changes
    change_details = response.get("change_details")
    if isinstance(change_details, Mapping):
        agent_msg["change_details"] = _json_safe(dict(change_details))

    chat_record: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "session_path": str(state.session_dir),
        "turn_path": str(turn_dir),
        "response_path": str(turn_dir / "response.json"),
        "detail_json_path": str(turn_dir / "response.json"),
        "messages": [
            {
                "role": "user",
                "text": state.task,
                "turn_id": context.turn_id,
            },
            agent_msg,
        ],
    }

    try:
        turn_dir.mkdir(parents=True, exist_ok=True)
        chat_path.write_text(
            json.dumps(chat_record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError) as exc:
        LOGGER.warning(
            "chat.json write failed for turn %s (best-effort): %s",
            context.turn_id,
            exc,
        )


def _stamped_turn_response_outcome(
    response: Mapping[str, Any] | None,
    *,
    stage: str = "submit",
) -> dict[str, Any] | None:
    if not isinstance(response, Mapping):
        return None
    try:
        stamped = ensure_agent_edit_response_contract(dict(response), stage=stage)
    except Exception:
        return None
    outcome = stamped.get("outcome")
    return dict(outcome) if isinstance(outcome, Mapping) else None


def _stamped_message_outcome(
    outcome: Mapping[str, Any] | None,
    *,
    stage: str = "chat",
) -> dict[str, Any] | None:
    if not isinstance(outcome, Mapping):
        return None
    try:
        stamped = ensure_agent_edit_response_contract(
            {"ok": True, "outcome": dict(outcome)},
            stage=stage,
        )
    except Exception:
        return None
    public_outcome = stamped.get("outcome")
    return dict(public_outcome) if isinstance(public_outcome, Mapping) else None


def _read_turn_response_payload(turn_dir: Path) -> dict[str, Any]:
    response_path = turn_dir / "response.json"
    try:
        response = json.loads(response_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(response) if isinstance(response, Mapping) else {}


def _latest_session_candidate_payload(session_dir: Path, turn_ids: list[str]) -> dict[str, Any] | None:
    try:
        state = read_state(session_dir)
    except Exception:
        state = {}
    turns_state = state.get("turns") if isinstance(state, Mapping) else {}
    if not isinstance(turns_state, Mapping):
        turns_state = {}
    for turn_id in reversed(turn_ids):
        turn_state = turns_state.get(turn_id)
        if not isinstance(turn_state, Mapping) or turn_state.get("state") != "candidate":
            continue
        turn_dir = session_dir / "turns" / turn_id
        response = _read_turn_response_payload(turn_dir)
        outcome = _stamped_turn_response_outcome(response, stage="submit")
        if outcome is None or outcome.get("kind") != "candidate":
            continue
        candidate_path = turn_dir / "candidate.ui.json"
        graph = response.get("graph")
        if not isinstance(graph, Mapping) and candidate_path.is_file():
            try:
                graph = json.loads(candidate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                graph = None
        if not isinstance(graph, Mapping):
            continue
        candidate = response.get("candidate")
        eligibility = response.get("apply_eligibility") or response.get("eligibility")
        latest_candidate = {
            "turn_id": turn_id,
            "session_id": session_dir.name,
            "baseline_turn_id": response.get("baseline_turn_id"),
            "message": response.get("message"),
            "graph": _json_safe(graph),
            "report": _json_safe(response.get("report")) if isinstance(response.get("report"), Mapping) else None,
            "candidate": _json_safe(candidate) if isinstance(candidate, Mapping) else None,
            "apply_eligibility": _json_safe(eligibility) if isinstance(eligibility, Mapping) else None,
            "canvas_apply_allowed": bool(response.get("canvas_apply_allowed")),
            "apply_allowed": response.get("apply_allowed") is not False,
            "queue_allowed": bool(response.get("queue_allowed")),
            "candidate_graph_hash": response.get("candidate_graph_hash") or turn_state.get("candidate_graph_hash"),
            "candidate_structural_graph_hash": response.get("candidate_structural_graph_hash") or turn_state.get("candidate_structural_graph_hash"),
            "submit_graph_hash": response.get("submit_graph_hash") or turn_state.get("submit_graph_hash"),
            "submit_structural_graph_hash": response.get("submit_structural_graph_hash") or turn_state.get("submit_structural_graph_hash"),
            "baseline_graph_hash": response.get("baseline_graph_hash") or state.get("baseline_graph_hash"),
            "baseline_graph_hash_kind": response.get("baseline_graph_hash_kind") or state.get("baseline_graph_hash_kind"),
            "baseline_graph_hash_version": response.get("baseline_graph_hash_version") or state.get("baseline_graph_hash_version"),
            "audit_ref": _json_safe(response.get("audit_ref")) if isinstance(response.get("audit_ref"), Mapping) else None,
            "change_details": _json_safe(response.get("change_details")) if isinstance(response.get("change_details"), Mapping) else None,
            "batch_turns": _json_safe(response.get("batch_turns")) if isinstance(response.get("batch_turns"), list) else [],
            "outcome": outcome,
        }
        return latest_candidate
    return None


# Bounds for the reasoning trim attached to rehydrated chat messages. The chat
# endpoint is fetched on every page reload, so the embedded reasoning must stay
# lean — keep enough per-step context to diagnose a turn (what the agent tried
# and why the engine rejected it) without shipping the full diff/statements.
_CHAT_REASONING_MAX_STEPS = 12
_CHAT_REASONING_MAX_DIAGS = 4
_CHAT_REASONING_MAX_OPERATIONS = 8


def _trim_chat_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def _compact_chat_change_details(change_details: Any) -> dict[str, Any] | None:
    """Trim a turn's ``change_details`` to the reasoning the panel report needs.

    The full ``change_details`` carries per-step diffs, statements, and provider
    metadata that bloat the chat-rehydrate payload. The diagnostic report only
    consumes the agent's per-step ``message`` / ``batch`` and the engine
    ``diagnostics`` (which carry the root data — valid enum ``choices`` and
    ``available_slots``), plus the change summary. Keep just those.
    """
    if not isinstance(change_details, dict):
        return None
    compact: dict[str, Any] = {}

    summary = _trim_chat_text(
        change_details.get("done_summary") or change_details.get("final_summary"),
        400,
    )
    if summary is not None:
        compact["done_summary"] = summary
    if isinstance(change_details.get("landed_operation_count"), int):
        compact["landed_operation_count"] = change_details["landed_operation_count"]

    operations = change_details.get("operations")
    if isinstance(operations, list) and operations:
        trimmed_ops = []
        for op in operations[:_CHAT_REASONING_MAX_OPERATIONS]:
            if not isinstance(op, dict):
                continue
            entry = {}
            op_summary = _trim_chat_text(op.get("summary"), 160)
            if op_summary is not None:
                entry["summary"] = op_summary
            field_path = _trim_chat_text(op.get("field_path"), 160)
            if field_path is not None:
                entry["field_path"] = field_path
            if entry:
                trimmed_ops.append(entry)
        if trimmed_ops:
            compact["operations"] = trimmed_ops

    batch_turns = change_details.get("batch_turns")
    if isinstance(batch_turns, list) and batch_turns:
        trimmed_steps = []
        for step in batch_turns[:_CHAT_REASONING_MAX_STEPS]:
            if not isinstance(step, dict):
                continue
            trimmed: dict[str, Any] = {}
            if isinstance(step.get("turn_number"), int):
                trimmed["turn_number"] = step["turn_number"]
            if isinstance(step.get("batch_ok"), bool):
                trimmed["batch_ok"] = step["batch_ok"]
            if isinstance(step.get("landed_op_count"), int):
                trimmed["landed_op_count"] = step["landed_op_count"]
            message = _trim_chat_text(step.get("message"), 500)
            if message is not None:
                trimmed["message"] = message
            batch = _trim_chat_text(step.get("batch"), 400)
            if batch is not None:
                trimmed["batch"] = batch
            diagnostics = step.get("diagnostics")
            if isinstance(diagnostics, list) and diagnostics:
                trimmed_diags = []
                for diag in diagnostics[:_CHAT_REASONING_MAX_DIAGS]:
                    if not isinstance(diag, dict):
                        continue
                    diag_entry: dict[str, Any] = {}
                    for key in ("code", "severity"):
                        if isinstance(diag.get(key), str):
                            diag_entry[key] = diag[key]
                    diag_message = _trim_chat_text(diag.get("message"), 300)
                    if diag_message is not None:
                        diag_entry["message"] = diag_message
                    detail = diag.get("detail")
                    if isinstance(detail, dict):
                        detail_entry = {}
                        for key in ("input", "value", "slot", "class_type", "name"):
                            if isinstance(detail.get(key), (str, int, float, bool)):
                                detail_entry[key] = detail[key]
                        for key in ("choices", "available_slots"):
                            values = detail.get(key)
                            if isinstance(values, list):
                                detail_entry[key] = [v for v in values[:24] if isinstance(v, (str, int, float))]
                        if detail_entry:
                            diag_entry["detail"] = detail_entry
                    if diag_entry:
                        trimmed_diags.append(diag_entry)
                if trimmed_diags:
                    trimmed["diagnostics"] = trimmed_diags
            if trimmed:
                trimmed_steps.append(trimmed)
        if trimmed_steps:
            compact["batch_turns"] = trimmed_steps

    return compact or None


def read_session_chat(
    session_root: Path,
    session_id: str,
    *,
    max_messages: int = DEFAULT_CHAT_DISPLAY_MESSAGES,
) -> dict[str, Any]:
    """Read conversation history for a session from persisted turn artifacts.

    Scans turn directories under the session root in deterministic order,
    reads ``chat.json`` where present, falls back to same-turn
    ``request.json`` + ``response.json``, and returns a bounded display
    history with session metadata.

    Returns:
        dict with keys: ``ok``, ``session_id``, ``session_path``,
        ``latest_turn_id``, ``detail_json_path``, ``messages``.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    turns_dir = session_dir / "turns"

    session_exists = session_dir.is_dir()
    if not turns_dir.is_dir():
        return {
            "ok": True,
            "exists": session_exists,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "session_path_resolved": str(session_dir.resolve()),
            "latest_turn_id": None,
            "detail_json_path": None,
            "detail_json_path_resolved": None,
            "messages": [],
            "latest_candidate": None,
        }

    # Sort turn directories deterministically (zero-padded integers).
    try:
        turn_ids: list[str] = sorted(
            [d.name for d in turns_dir.iterdir() if d.is_dir()],
        )
    except OSError:
        turn_ids = []

    all_messages: list[dict[str, Any]] = []
    latest_turn_id: str | None = None

    for turn_id in turn_ids:
        turn_dir = turns_dir / turn_id
        chat_path = turn_dir / "chat.json"
        chat_record: dict[str, Any] | None = None
        response = _read_turn_response_payload(turn_dir)
        fallback_agent_outcome = _stamped_turn_response_outcome(response, stage="submit")

        # Try chat.json first.
        if chat_path.is_file():
            try:
                chat_record = json.loads(chat_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        # Fall back to request.json + response.json.
        if chat_record is None:
            request_path = turn_dir / "request.json"
            response_path = turn_dir / "response.json"
            if request_path.is_file() and response_path.is_file():
                try:
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                    response = json.loads(response_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue  # skip unrecoverable turn
                agent_text_raw = response.get("user_facing_message") or response.get("message", "")
                agent_text: str = agent_text_raw if isinstance(agent_text_raw, str) else ""
                if not agent_text.strip():
                    agent_text = "The agent edit turn completed."
                chat_record = {
                    "session_id": safe_id,
                    "turn_id": turn_id,
                    "session_path": str(session_dir),
                    "turn_path": str(turn_dir),
                    "response_path": str(response_path),
                    "detail_json_path": str(response_path),
                    "messages": [
                        {
                            "role": "user",
                            "text": request.get("task", ""),
                            "turn_id": turn_id,
                        },
                        {
                            "role": "agent",
                            "text": agent_text,
                            "turn_id": turn_id,
                        },
                    ],
                }
                if fallback_agent_outcome is not None:
                    chat_record["messages"][1]["outcome"] = fallback_agent_outcome

        if chat_record is None:
            continue

        # Best-effort wall-clock for this turn, used by the panel to show a
        # relative timestamp ("5 minutes ago") below each chat bubble. Turn
        # artifacts carry no explicit timestamp, so the turn directory's mtime
        # is the most faithful proxy for when the exchange landed.
        try:
            turn_ts = datetime.fromtimestamp(
                turn_dir.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        except OSError:
            turn_ts = None

        # Extract display messages from the chat record.
        messages = chat_record.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") in ("user", "agent"):
                    display_msg = {
                        "role": msg["role"],
                        "text": msg.get("text", ""),
                        "turn_id": msg.get("turn_id", turn_id),
                    }
                    if turn_ts is not None:
                        display_msg["timestamp"] = turn_ts
                    stamped_outcome = _stamped_message_outcome(msg.get("outcome"))
                    if msg["role"] == "agent" and stamped_outcome is None:
                        stamped_outcome = fallback_agent_outcome
                    if msg["role"] == "agent" and stamped_outcome is not None:
                        display_msg["outcome"] = stamped_outcome
                    if msg["role"] == "agent":
                        # Carry a trimmed view of the agent's per-step reasoning so a
                        # reloaded panel's diagnostic report can show what the agent
                        # tried and why the engine rejected it (the on-disk
                        # change_details is otherwise unreachable after reload).
                        reasoning = _compact_chat_change_details(msg.get("change_details"))
                        if reasoning is not None:
                            display_msg["change_details"] = reasoning
                    all_messages.append(display_msg)
        latest_turn_id = turn_id

    # Take the last N messages for display.
    display_messages = all_messages[-max_messages:] if max_messages > 0 else all_messages

    return {
        "ok": True,
        "exists": True,
        "session_id": safe_id,
        "session_path": str(session_dir),
        "session_path_resolved": str(session_dir.resolve()),
        "latest_turn_id": latest_turn_id,
        "detail_json_path": (
            str(turns_dir / latest_turn_id / "response.json")
            if latest_turn_id
            else None
        ),
        "detail_json_path_resolved": (
            str((turns_dir / latest_turn_id / "response.json").resolve())
            if latest_turn_id
            else None
        ),
        "messages": display_messages,
        "latest_candidate": _latest_session_candidate_payload(session_dir, turn_ids),
    }


# Suffixes treated as UTF-8 text in the downloadable session bundle; everything
# else is base64-encoded so binary artifacts (PNG previews, etc.) survive.
_BUNDLE_TEXT_SUFFIXES = frozenset(
    {".json", ".jsonl", ".py", ".txt", ".md", ".log", ".csv", ".yaml", ".yml", ".diff", ".html"}
)
_BUNDLE_MAX_FILE_BYTES = 8 * 1024 * 1024  # 8 MiB per file
_BUNDLE_MAX_TOTAL_BYTES = 64 * 1024 * 1024  # 64 MiB per bundle


def read_session_bundle(
    session_root: Path,
    session_id: str,
    *,
    max_file_bytes: int = _BUNDLE_MAX_FILE_BYTES,
    max_total_bytes: int = _BUNDLE_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """Read every artifact under a session dir for a self-contained issue bundle.

    The issue-report ZIP is built in the browser, which cannot reach the
    filesystem; the report/prompt point at ``messages.jsonl`` etc. that a
    recipient on another machine does not have. This returns the full set of
    session artifacts (turn dirs + session_state.json) so the browser can embed
    them in the ZIP — making the report self-contained.

    Files are returned with names relative to the session dir. Text artifacts
    carry a ``text`` field; binary artifacts carry base64 ``base64``. Oversized
    files and anything past the total cap are recorded in ``skipped`` rather
    than silently dropped.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    if not session_dir.is_dir():
        return {
            "ok": True,
            "exists": False,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "session_path_resolved": str(session_dir.resolve()),
            "files": [],
            "skipped": [],
            "file_count": 0,
            "total_bytes": 0,
        }

    files: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    total = 0
    try:
        candidates = sorted(p for p in session_dir.rglob("*") if p.is_file())
    except OSError as exc:
        return {
            "ok": True,
            "exists": True,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "session_path_resolved": str(session_dir.resolve()),
            "files": [],
            "skipped": [{"name": "(walk)", "reason": f"walk_failed: {exc}"}],
            "file_count": 0,
            "total_bytes": 0,
        }

    for path in candidates:
        try:
            rel = path.relative_to(session_dir).as_posix()
        except ValueError:
            continue  # defensive: never escape the session dir
        try:
            size = path.stat().st_size
        except OSError:
            skipped.append({"name": rel, "reason": "stat_failed"})
            continue
        if size > max_file_bytes:
            skipped.append({"name": rel, "reason": "too_large", "size": size})
            continue
        if total + size > max_total_bytes:
            skipped.append({"name": rel, "reason": "bundle_full", "size": size})
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            skipped.append({"name": rel, "reason": "read_failed"})
            continue
        total += len(raw)
        if path.suffix.lower() in _BUNDLE_TEXT_SUFFIXES:
            files.append({"name": rel, "text": raw.decode("utf-8", errors="replace")})
        else:
            files.append({"name": rel, "base64": base64.b64encode(raw).decode("ascii")})

    return {
        "ok": True,
        "exists": True,
        "session_id": safe_id,
        "session_path": str(session_dir),
        "files": files,
        "skipped": skipped,
        "file_count": len(files),
        "total_bytes": total,
    }


def read_session_json(
    session_root: Path,
    session_id: str,
    *,
    max_messages: int = 5,
) -> dict[str, Any]:
    """Return session metadata, sorted turn summaries, and last-five messages.

    This is the JSON detail route helper — it returns turn-level artifact
    paths (``request.json``, ``response.json``, ``chat.json``) for each
    persisted turn alongside the same last-five display messages as
    ``read_session_chat``.  It does **not** browse, search, index, or read
    arbitrary paths.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    turns_dir = session_dir / "turns"

    session_meta = {
        "session_id": safe_id,
        "session_path": str(session_dir),
        "turns_dir": str(turns_dir),
    }

    if not turns_dir.is_dir():
        return {
            **session_meta,
            "ok": True,
            "latest_turn_id": None,
            "detail_json_path": None,
            "turn_count": 0,
            "turns": [],
            "messages": [],
        }

    # Deterministic sort of turn directories.
    try:
        turn_names: list[str] = sorted(
            [d.name for d in turns_dir.iterdir() if d.is_dir()],
        )
    except OSError:
        turn_names = []

    turn_summaries: list[dict[str, Any]] = []
    all_messages: list[dict[str, Any]] = []
    latest_turn_id: str | None = None

    for turn_name in turn_names:
        turn_dir = turns_dir / turn_name
        summary: dict[str, Any] = {
            "turn_id": turn_name,
            "turn_path": str(turn_dir),
        }

        # Artifact paths — only note what is actually present.
        for artifact_name in ("request.json", "response.json", "chat.json"):
            artifact_path = turn_dir / artifact_name
            if artifact_path.is_file():
                summary[artifact_name] = str(artifact_path)

        # Reuse the chat-reader logic for message extraction.
        chat_path = turn_dir / "chat.json"
        chat_record: dict[str, Any] | None = None

        if chat_path.is_file():
            try:
                chat_record = json.loads(chat_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        if chat_record is None:
            request_path = turn_dir / "request.json"
            response_path = turn_dir / "response.json"
            if request_path.is_file() and response_path.is_file():
                try:
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                    response = json.loads(response_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    summary["error"] = "unreadable artifacts"
                    turn_summaries.append(summary)
                    continue
                agent_text: str = response.get("message", "")
                if not isinstance(agent_text, str) or not agent_text.strip():
                    agent_text = "The agent edit turn completed."
                chat_record = {
                    "session_id": safe_id,
                    "turn_id": turn_name,
                    "session_path": str(session_dir),
                    "turn_path": str(turn_dir),
                    "response_path": str(response_path),
                    "detail_json_path": str(response_path),
                    "messages": [
                        {
                            "role": "user",
                            "text": request.get("task", ""),
                            "turn_id": turn_name,
                        },
                        {
                            "role": "agent",
                            "text": agent_text,
                            "turn_id": turn_name,
                        },
                    ],
                }

        if chat_record is None:
            summary["error"] = "no readable artifacts"
            turn_summaries.append(summary)
            continue

        messages = chat_record.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") in ("user", "agent"):
                    all_messages.append({
                        "role": msg["role"],
                        "text": msg.get("text", ""),
                        "turn_id": msg.get("turn_id", turn_name),
                    })

        summary["message_count"] = len(
            [m for m in messages if isinstance(m, dict) and m.get("role") in ("user", "agent")]
        )
        turn_summaries.append(summary)
        latest_turn_id = turn_name

    display_messages = all_messages[-max_messages:] if max_messages > 0 else all_messages

    return {
        **session_meta,
        "ok": True,
        "latest_turn_id": latest_turn_id,
        "detail_json_path": (
            str(turns_dir / latest_turn_id / "response.json")
            if latest_turn_id
            else None
        ),
        "turn_count": len(turn_summaries),
        "turns": turn_summaries,
        "messages": display_messages,
    }


def _compact_diag_to_dict(diagnostic: Any) -> dict[str, Any]:
    return {
        "code": getattr(diagnostic, "code", type(diagnostic).__name__),
        "message": getattr(diagnostic, "message", str(diagnostic)),
        "severity": getattr(diagnostic, "severity", "error"),
        "detail": _json_safe(getattr(diagnostic, "detail", {})),
        "teaching_hint": getattr(diagnostic, "teaching_hint", None),
    }


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
    """
    if not adaptation_plan:
        return ""

    parts: list[str] = []

    # ── selected slice ──
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
        parts.append(f"Selected slice: {slice_desc}")

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

    inspect routes only observe the graph without modifying it.
    clarify routes ask the user a question and do not produce a candidate.
    Both are semantically inapplicable for Apply.
    """
    return _canonical_agent_edit_route(route) in {"inspect", "clarify"}


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

def _prefetch_research_summary(task: str) -> str:
    try:
        from vibecomfy.executor.research import (
            _default_hivemind_client,
            research as run_research_phase,
        )

        result = run_research_phase(task, hivemind_client=_default_hivemind_client)
        return result.summary
    except Exception as exc:
        return f"Research lookup failed: {type(exc).__name__}: {exc}"


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
    if _is_code_node_intent(state.task):
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
    prefetch_research = intent == "research" or (
        not intent and _is_research_intent(state.task)
    )
    prefetch_explain = intent == "explain_graph" or (
        not intent and _is_graph_explain_intent(state.task)
    )
    prefetch_research_summary = state.executor_research_summary or (
        _prefetch_research_summary(state.task) if prefetch_research else ""
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
    if _canonical_agent_edit_route(state.route or route) == "adapt" and state.executor_adaptation_plan:
        precedent_adaptation_prompt = _build_precedent_adaptation_prompt(
            state.executor_adaptation_plan,
            state.executor_precedent_slices,
        )

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
    failed_edit_turns = 0
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []

    for turn_number in range(max_batches):
        budget_remaining = max_batches - turn_number
        include_full_render = turn_number == 0 or last_landed_count == 0
        node_variable_index = _format_node_variable_index(session)
        messages = build_batch_messages(
            task=state.task,
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
            research_summary=prefetch_research_summary if turn_number == 0 else "",
            graph_report=prefetch_graph_report if turn_number == 0 else "",
            precedent_adaptation_plan=precedent_adaptation_prompt if turn_number == 0 else "",
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
            response_log.append(
                {
                    "turn_number": turn_number,
                    "response": turn_result.to_dict(),
                    "clarification": turn_record,
                }
            )
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

            def _lint_issue_to_dict(issue: Any) -> dict[str, Any]:
                return {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity,
                    "op_index": getattr(issue, "op_index", None),
                    "op_kind": getattr(issue, "op_kind", None),
                    "source": "lint",
                }

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
        field_changes = _repair_field_changes_from_original_ui(
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

        response_log.append(
            {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "batch_result": turn_record,
            }
        )
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
            state.user_message = (
                f"{turn_result.message}\n\n{done_result.summary}".strip()
                if turn_result.message
                else done_result.summary
            )
            state.report = {
                "done_summary": done_result.summary,
                "queue_blockers": [],
            }
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


def _stage_load_python(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.security.agent_generated_loader import load_agent_generated_scratchpad

    start = time.monotonic()
    state.after_py_path.write_text(state.python_after, encoding="utf-8")
    state.edited_workflow = load_agent_generated_scratchpad(state.after_py_path)
    return StageResult(
        stage="load_python",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.after_py_path),),
        gate_updates={"python_load_ok": True},
    )


def _stage_lower(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.lowering import lower_workflow

    start = time.monotonic()
    original_workflow = state.edited_workflow
    lowering = lower_workflow(state.edited_workflow, schema_provider=state.schema_provider)
    result = lower_stage_result(lowering)
    if result.ok:
        if lowering.lowered_count > 0:
            if lowering.workflow is not None:
                state.edited_workflow = lowering.workflow
            state.original_intent_workflow = original_workflow
        else:
            state.edited_workflow = original_workflow
        state.lowering_evidence = [dict(dataclasses.asdict(item)) for item in lowering.evidence]
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_validate(state: AgentEditState, _context: TurnContext) -> StageResult:
    from .diagnostics import validate_stage_result

    start = time.monotonic()
    result = validate_stage_result(state.edited_workflow, schema_provider=state.schema_provider)
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_emit(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.layout import evaluate_felt_delta
    from vibecomfy.porting.layout_store import store_from_ui_json, write_store
    from vibecomfy.porting.emit.ui import emit_ui_json

    start = time.monotonic()
    recovery_report: list[dict[str, Any]] = []
    change_report_out: list[Any] = []
    ui_payload = emit_ui_json(
        state.edited_workflow,
        schema_provider=state.schema_provider,
        prior_store=state.prior_store,
        recovery_report=recovery_report,
        change_report_out=change_report_out,
        guard_original_ui=state.guard_original_ui or state.graph,
    )
    state.candidate_ui_path.write_text(
        json.dumps(ui_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_store(state.after_py_path, store_from_ui_json(ui_payload))
    state.ui_payload = ui_payload

    reroute_uids = frozenset(
        (node.uid or node_id)
        for node_id, node in state.edited_workflow.nodes.items()
        if node.class_type == "Reroute"
    )
    felt_report = (
        evaluate_felt_delta(
            state.prior_store,
            ui_payload,
            change_report_out[0],
            reroute_uids=reroute_uids,
        )
        if change_report_out
        else None
    )
    state.report = {
        "change": dataclasses.asdict(change_report_out[0]) if change_report_out else {},
        "recovery": recovery_report,
        "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
    }
    _inject_lowering_provenance(state)
    return StageResult(
        stage="emit",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.candidate_ui_path),),
        gate_updates={
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    )


def _stage_apply_delta(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.apply import apply_delta
    from vibecomfy.porting.edit.apply import (
        AppliedAddNodeSpec,
        ResolvedFieldRef,
        ResolvedRemoveNodePlan,
    )
    from vibecomfy.porting.edit.ops import op_to_dict

    def _build_delta_audit(result: Any) -> dict[str, Any]:
        automatic_link_removals: list[dict[str, Any]] = []
        re_stitches: list[dict[str, Any]] = []
        for op, resolved_op in result.resolved_ops:
            if isinstance(resolved_op, ResolvedFieldRef) and resolved_op.automatic_link_removal is not None:
                automatic_link_removals.append(
                    {
                        "scope_path": resolved_op.target.scope_path,
                        "uid": resolved_op.target.uid,
                        "field_path": resolved_op.target.field_path,
                        "link_id": resolved_op.automatic_link_removal,
                    }
                )
            elif isinstance(resolved_op, ResolvedRemoveNodePlan) and resolved_op.link_rewires:
                re_stitches.append(
                    {
                        "scope_path": resolved_op.node_ref.target.scope_path,
                        "uid": resolved_op.node_ref.target.uid,
                        "class_type": resolved_op.node_ref.class_type,
                        "link_rewrites": [
                            {
                                "scope_path": rewire.scope_path,
                                "link_id": rewire.link_id,
                                "old_origin_id": rewire.old_origin_id,
                                "new_origin_id": rewire.new_origin_id,
                                "new_origin_slot": rewire.new_origin_slot,
                            }
                            for rewire in resolved_op.link_rewires
                        ],
                    }
                )
            elif isinstance(resolved_op, AppliedAddNodeSpec):
                continue
        guard = result.guard_result
        guard_payload = {
            "ok": bool(guard.ok) if guard is not None else True,
            "diagnostics": [
                _port_issue_to_dict(issue) for issue in (guard.diagnostics if guard is not None else ())
            ],
        }
        normalize_payload = {
            "fallback_used": bool(getattr(guard, "normalize_fallback_used", False)),
            "allow_list_used": bool(getattr(guard, "normalize_allow_list_used", False)),
        }
        return {
            "ops": [op_to_dict(op) for op in state.delta_ops],
            "diagnostics": [_port_issue_to_dict(issue) for issue in result.diagnostics],
            "automatic_link_removals": automatic_link_removals,
            "re_stitches": re_stitches,
            "guard_result": guard_payload,
            "normalize": normalize_payload,
        }

    start = time.monotonic()

    # ── lint gate (VIBECOMFY_AGENT_EDIT_LINT defaults ON) ──────────────────
    original_ui = state.guard_original_ui or state.graph
    if _edit_lint_enabled() and state.delta_ops:
        from vibecomfy.porting.edit.lint import LintIndex, lint_delta

        index = LintIndex.build(original_ui)
        lint_result = lint_delta(
            state.delta_ops,
            index,
            schema_provider=state.schema_provider,
        )

        def _lint_issue_to_dict(issue: Any) -> dict[str, Any]:
            return {
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
                "op_index": getattr(issue, "op_index", None),
                "op_kind": getattr(issue, "op_kind", None),
            }

        lint_issue_dicts = tuple(
            _lint_issue_to_dict(issue) for issue in lint_result.issues
        )

        # Rejected ops → fail before mutation
        if lint_result.rejected_count > 0:
            error_issues = tuple(
                i for i in lint_issue_dicts if i.get("severity") == "error"
            )
            return StageResult(
                stage="apply_delta",
                ok=False,
                blocking=True,
                duration_ms=_duration_ms(start),
                issues=error_issues or lint_issue_dicts,
                value={
                    "failure_kind": FailureKind.VALIDATION_ERROR.value,
                    "mutation_started": 0,
                    "op_count": len(state.delta_ops),
                    "lint_rejected": lint_result.rejected_count,
                    "lint_dropped": lint_result.dropped_count,
                },
            )

        # All ops dropped as no-ops → clean no-op turn
        if lint_result.passed_count == 0:
            state.ui_payload = original_ui
            state.delta_diagnostics = [
                dict(d) for d in lint_issue_dicts
            ]
            # Collect human-readable no-op messages for user-facing display
            _noop_msgs: list[str] = []
            for norm in lint_result.normalizations:
                if norm.disposition == "dropped_noop" and norm.issue is not None:
                    _noop_msgs.append(norm.issue.message)
            state.lint_noop_messages = tuple(_noop_msgs)
            state.report = {
                "change": {
                    "mode": "agent_edit_v2_delta",
                    "op_count": len(state.delta_ops),
                    "ops": [],
                    "mutation_started": 0,
                    "lint_noop": True,
                },
                "recovery": [],
                "felt": {},
                "diagnostics": lint_issue_dicts,
            }
            return StageResult(
                stage="apply_delta",
                ok=True,
                blocking=False,
                duration_ms=_duration_ms(start),
                issues=lint_issue_dicts,
                value={
                    "mode": "agent_edit_v2_delta",
                    "op_count": 0,
                    "mutation_started": 0,
                    "lint_noop": True,
                    "lint_dropped": lint_result.dropped_count,
                },
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                },
            )

        # Surviving ops proceed to apply
        state.delta_ops = lint_result.surviving
        state.delta_lint = {
            "issues": [dict(d) for d in lint_issue_dicts],
            "dropped": lint_result.dropped_count,
            "rejected": lint_result.rejected_count,
            "passed": lint_result.passed_count,
        }

    result = apply_delta(
        original_ui,
        state.delta_ops,
        schema_provider=state.schema_provider,
    )
    issues = tuple(_port_issue_to_dict(issue) for issue in result.diagnostics)
    if not result.ok or result.candidate is None:
        return StageResult(
            stage="apply_delta",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            issues=issues,
            value={
                "failure_kind": FailureKind.VALIDATION_ERROR.value,
                "mutation_started": result.mutation_started,
                "op_count": len(state.delta_ops),
            },
        )

    state.ui_payload = result.candidate
    candidate_ui_ref = write_json_artifact(state.candidate_ui_path, state.ui_payload)
    ops = [op_to_dict(op) for op in state.delta_ops]
    state.delta_diagnostics = [_port_issue_to_dict(issue) for issue in result.diagnostics]
    state.guard_result = {
        "ok": bool(result.guard_result.ok) if result.guard_result is not None else True,
        "diagnostics": [
            _port_issue_to_dict(issue)
            for issue in (result.guard_result.diagnostics if result.guard_result is not None else ())
        ],
        "normalize": {
            "fallback_used": bool(getattr(result.guard_result, "normalize_fallback_used", False)),
            "allow_list_used": bool(getattr(result.guard_result, "normalize_allow_list_used", False)),
        },
    }
    state.delta_audit = _build_delta_audit(result)
    state.report = {
        "change": {
            "mode": "agent_edit_v2_delta",
            "op_count": len(ops),
            "ops": ops,
            "mutation_started": result.mutation_started,
        },
        "recovery": [],
        "felt": {},
        "diagnostics": [issue for issue in issues if issue.get("severity") != "info"],
    }
    return StageResult(
        stage="apply_delta",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(candidate_ui_ref,),
        issues=issues,
        value={
            "mode": "agent_edit_v2_delta",
            "op_count": len(ops),
            "mutation_started": result.mutation_started,
        },
        gate_updates={
            "python_load_ok": True,
            "lower_ok": True,
            "ir_validate_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
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


def _stage_summarize_v2(state: AgentEditState, context: TurnContext) -> StageResult:
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


def _product_failure_response(failure: FailureEnvelope) -> dict[str, Any]:
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
) -> dict[str, Any] | None:
    if not has_candidate:
        return None
    return {
        "state": "candidate",
        "graph": state.ui_payload,
        "graph_hash": compatibility_fields["candidate_graph_hash"],
        "structural_graph_hash": compatibility_fields["candidate_structural_graph_hash"],
        "baseline_graph_hash": compatibility_fields["baseline_graph_hash"],
        "submit_graph_hash": compatibility_fields["submit_graph_hash"],
        "submit_structural_graph_hash": compatibility_fields["submit_structural_graph_hash"],
    }


def _legacy_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: FailureEnvelope,
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
        apply_eligibility_payload(
            eligibility,
            canvas_apply_allowed=context.canvas_apply_allowed,
            queue_allowed=context.queue_allowed,
        )
    )
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
    failure: FailureEnvelope,
) -> dict[str, Any]:
    response = _legacy_failure_response(state, context, failure=failure)
    legacy_audit_ref = response.get("audit_ref")
    compatibility_fields = _build_compatibility_response_fields(state)
    response.update(compatibility_fields)
    response.update(_session_artifact_response_fields(state))
    response.update(product_failure_envelope_fields(failure))
    if legacy_audit_ref is not None:
        response["audit_ref"] = legacy_audit_ref
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
    failure: FailureEnvelope,
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
    has_candidate = (
        state.batch_exit_mode in {_BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_DONE}
        and _batch_candidate_graph_changed(state)
    )
    compatibility_fields = _build_compatibility_response_fields(state)
    response_apply_eligibility = derive_apply_eligibility(
        context,
        has_candidate=has_candidate,
        candidate_state="candidate",
    )
    # inspect and clarify routes cannot be Apply-eligible.
    if _route_blocks_apply(state.route):
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
    )
    if state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY:
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
    public_outcome = public_outcome_from_turn_outcome(
        internal_outcome,
        response={"candidate": candidate_payload},
    )
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
    if state.batch_exit_mode in {_BATCH_EXIT_PURE_CLARIFY, _BATCH_EXIT_EDIT_CLARIFY}:
        response["clarification_required"] = True
        response["graph_unchanged"] = state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
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
    return response


def _build_dev_success_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    contract: str,
) -> dict[str, Any]:
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
    response.update(
        turn_envelope(
            message=state.user_message,
            outcome=public_outcome_from_turn_outcome(
                internal_outcome,
                response={"candidate": {"graph_hash": compatibility_fields["candidate_graph_hash"]}} if has_candidate else None,
            ),
            candidate=_build_candidate_payload(
                state,
                compatibility_fields=compatibility_fields,
                has_candidate=has_candidate,
            ),
            eligibility=eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
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
    return response


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
        projection_path=turn_dir / "projection.txt",
        messages_path=turn_dir / "messages.jsonl",
    )
    research_summary = payload.get("research_summary")
    if isinstance(research_summary, str) and research_summary.strip():
        state.executor_research_summary = research_summary.strip()
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
