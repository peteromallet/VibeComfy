from __future__ import annotations

import difflib
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from ..agent_audit import artifact_ref_for_path
from ..agent_contracts import (
    ArtifactRef,
    FailureEnvelope,
    FailureKind,
    TurnContext,
    TurnOutcome,
)
from ..agent_provider import (
    AgentTurnResult,
    BatchTurnResult,
    ensure_sentence_message,
)
from ..agent_session import structural_graph_hash
from vibecomfy.porting.edit_types import FieldChange
from vibecomfy.porting.widget_aliases import widget_names_for_class

if TYPE_CHECKING:
    from ..agent_edit import AgentEditState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentinels
# ---------------------------------------------------------------------------

_MISSING_FIELD_CHANGE_OLD = object()
_ABSENT_FIELD_OLD = object()  # marker for fields genuinely absent from the original UI graph

_BATCH_EXIT_BUDGET = "budget"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _field_changes_payload(changes: tuple[FieldChange, ...]) -> list[dict[str, Any]]:
    return [change.to_dict() for change in changes]


def _compact_diag_to_dict(diagnostic: Any) -> dict[str, Any]:
    return {
        "code": getattr(diagnostic, "code", type(diagnostic).__name__),
        "message": getattr(diagnostic, "message", str(diagnostic)),
        "severity": getattr(diagnostic, "severity", "error"),
        "detail": _json_safe(getattr(diagnostic, "detail", {})),
        "teaching_hint": getattr(diagnostic, "teaching_hint", None),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
                "I ran out of batch budget before completing the remaining changes",
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
            "I ran out of batch budget before completing the requested changes",
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


def _format_query_output(text: str, *, max_chars: int = 4000) -> str:
    """Bound read-only query output before it is included in agent feedback."""
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
            statement_lines.append(_format_query_output(query_output))

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
        f"Batch summary: {landed_count} landed, {failed_count} failed, "
        f"{len(batch_result.diagnostics)} batch diagnostic(s)"
        f"{lint_note}, "
        f"{budget_remaining} batch(es) remaining, "
        f"{consecutive_errors} consecutive error turn(s)."
    )
    lines = [summary, *statement_lines, *diagnostic_lines]
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

# ---------------------------------------------------------------------------
# UI graph introspection
# ---------------------------------------------------------------------------

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



