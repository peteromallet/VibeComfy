# Generated from edit.py. Keep behavior changes in the installed source body.
# Contents: Human-readable edit messages and operation details.

SOURCE = r'''
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
    if _real_field_changes(tuple(state.batch_field_changes or ())):
        return True
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
    if not after_by_uid:
        return []
    added = [after_by_uid[uid] for uid in sorted(set(after_by_uid) - set(before_by_uid))]
    removed = [before_by_uid[uid] for uid in sorted(set(before_by_uid) - set(after_by_uid))]
    phrases: list[str] = []
    if added:
        parts: list[str] = []
        for node in added[:8]:
            node_text = _node_phrase(node)
            source = _first_link_source_label(node, state.ui_payload, labels)
            if source:
                node_text = f"{node_text} fed by {source}"
            parts.append(node_text)
        text = _join_human_list(parts)
        remaining = len(added) - len(parts)
        if remaining > 0:
            noun = "other node" if remaining == 1 else "other nodes"
            text = f"{text}, plus {remaining} {noun}"
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
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


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
    revision_message = _revision_rejected_candidate_message(state)
    if revision_message:
        return revision_message

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


def _revision_rejected_candidate_message(state: AgentEditState) -> str:
    evidence = state.revision_evidence
    scoped = evidence.scoped_diff if evidence is not None else None
    if evidence is None or scoped is None or evidence.candidate_eligible is True:
        return ""
    blockers = list(scoped.eligibility_blockers or ())
    mismatch_reasons = [
        str(item.get("reason") or "").strip()
        for item in evidence.topology.socket_type_mismatches
        if isinstance(item, Mapping) and str(item.get("reason") or "").strip()
    ]
    if "candidate_topology_blockers" in blockers and mismatch_reasons:
        return ensure_sentence_message(
            "I left the graph unchanged because the candidate did not repair existing socket type mismatches first: "
            + "; ".join(mismatch_reasons[:3]),
            fallback="I left the graph unchanged because the candidate would not produce a valid workflow.",
        )
    if blockers:
        return ensure_sentence_message(
            "I left the graph unchanged because the candidate was not safe to apply: "
            + ", ".join(blockers),
            fallback="I left the graph unchanged because the candidate was not safe to apply.",
        )
    return "I left the graph unchanged because the candidate was not safe to apply."


def _revision_candidate_retry_hint(state: AgentEditState) -> str:
    message = _revision_rejected_candidate_message(state)
    evidence = state.revision_evidence
    mismatch_reasons = []
    if evidence is not None:
        mismatch_reasons = [
            str(item.get("reason") or "").strip()
            for item in evidence.topology.socket_type_mismatches
            if isinstance(item, Mapping) and str(item.get("reason") or "").strip()
        ]
    details = "; ".join(mismatch_reasons[:3])
    if details:
        return (
            "the candidate still leaves invalid graph wiring. Repair these existing "
            f"socket mismatches first: {details}. Then add the save/export path. "
            "Prefer installed local nodes from search results such as CreateVideo -> SaveVideo "
            "or SaveAnimatedWEBP when their signatures are available; use vibecomfy.exec only "
            "for explicit code/Python requests or when no installed node path exists."
        )
    return (
        (message or "the candidate was not safe to apply")
        + " Fix the reported eligibility blockers, then call done() again."
    )


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
    payload = {
        "landed_operation_count": _total_landed_edit_count(state),
        "done_summary": state.batch_done_summary or "",
        "final_summary": state.batch_final_summary or "",
        "gate_a": _json_safe(gate_a),
        "gate_b": _json_safe(gate_b),
        "operations": operations,
        "batch_turns": _json_safe(state.batch_turns),
    }
    advisory = getattr(state, "post_edit_reorganisation_advisory", None)
    if isinstance(advisory, Mapping):
        payload["layout_reorganisation"] = _json_safe(dict(advisory))
    return payload


_NARRATIVE_GATE_JARGON_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bGate\s+[AB]\b", re.I),
    re.compile(r"\bidentity verified\b", re.I),
    re.compile(r"\bplan_validate_ok\b", re.I),
    re.compile(r"\bqueue_validate_ok\b", re.I),
    re.compile(r"\bui_fidelity_ok\b", re.I),
    re.compile(r"\bir_validate_ok\b", re.I),
    re.compile(r"\bstate_match_ok\b", re.I),
    re.compile(r"\bedit_scope_ok\b", re.I),
    re.compile(r"\bpython_load_ok\b", re.I),
)

_NARRATIVE_EDIT_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(applied|changed|updated|edited|rewired|connected|disconnected|added|removed)\b", re.I),
)

_NARRATIVE_NO_EDIT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(no (?:change|changes|edit|edits|updates?) needed|unchanged|left the graph unchanged|nothing needed changing)\b", re.I),
)

_NARRATIVE_VALIDATION_PASS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(validation (?:passed|succeeded)|valid(?:ated)?|ready to apply|safe to apply)\b", re.I),
)

_NARRATIVE_VALIDATION_FAIL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(validation (?:failed|error|errors|issue|issues)|invalid|blocked by validation)\b", re.I),
)

_NARRATIVE_QUESTION_START = re.compile(
    r"^\s*(?:what|which|where|when|why|how|who|whom|whose|should|would|could|can|do|does|did|is|are|am|will|won't)\b",
    re.I,
)

_NARRATIVE_COUNT_PATTERN = re.compile(
    r"\b(\d+)\s+(?:landed\s+)?(?:edit|edits|operation|operations|change|changes)\b",
    re.I,
)

_NARRATOR_RESPONSE_REQUIRED_FIELD = "message"


def _narrator_system_message() -> str:
    return (
        "You write the final user-facing status line for a completed agent-edit turn. "
        "Use only the provided structured facts. Do not invent edits, validation status, "
        "or apply readiness. Do not mention internal gate labels. Return JSON with a "
        'single string field named "message".'
    )


def _narrator_user_message(
    *,
    narrative_context: Mapping[str, Any],
    raw_executor_message: str,
    fallback_message: str,
) -> str:
    request_payload = {
        "instructions": {
            "style": "One or two concise sentences.",
            "must_include": [
                "Describe what actually happened after validation.",
                "Ask a direct question when the outcome requires clarification.",
            ],
            "must_avoid": [
                "Internal gate jargon",
                "Contradicting the landed edit count or validation outcome",
            ],
        },
        "raw_executor_message": raw_executor_message[:240],
        "fallback_message": fallback_message,
        "narrative_context": narrative_context,
    }
    return (
        "Return a JSON object with the final public message for this agent-edit turn.\n"
        + json.dumps(_json_safe(request_payload), indent=2, sort_keys=True)
    )


def _narrator_message_from_response(response: Mapping[str, Any]) -> str:
    response_json = response.get("json")
    if not isinstance(response_json, Mapping):
        raise MalformedModelJSON("Narrator response must include a JSON object.")
    message = response_json.get(_NARRATOR_RESPONSE_REQUIRED_FIELD)
    if not isinstance(message, str) or not message.strip():
        raise MissingRequiredField(
            'Narrator JSON must include non-empty string key "message".'
        )
    return message.strip()


def _narrative_issue_summary(issue: Any) -> str:
    if isinstance(issue, Mapping):
        for key in ("summary", "message", "diagnostic", "reason", "code"):
            value = issue.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    text = " ".join(str(issue).split())
    return text[:160] if text else ""


def _narrative_issue_payloads(issues: Any, *, limit: int = 3) -> list[dict[str, Any]]:
    if not isinstance(issues, (list, tuple)):
        return []
    payloads: list[dict[str, Any]] = []
    for issue in issues:
        summary = _narrative_issue_summary(issue)
        if not summary:
            continue
        code = ""
        if isinstance(issue, Mapping):
            raw_code = issue.get("code") or issue.get("kind") or issue.get("severity")
            if isinstance(raw_code, str):
                code = raw_code.strip()
        payload = {"summary": summary}
        if code:
            payload["code"] = code
        payloads.append(payload)
        if len(payloads) >= limit:
            break
    return payloads


def _narrative_stage_payload(result: StageResult | None) -> dict[str, Any] | None:
    if not isinstance(result, StageResult):
        return None
    payload = {
        "ok": result.ok,
        "blocking": result.blocking,
        "issues": _narrative_issue_payloads(result.issues),
    }
    if result.duration_ms is not None:
        payload["duration_ms"] = result.duration_ms
    return payload


def _validation_summary_payload(context: TurnContext) -> dict[str, Any]:
    gate_snapshot = context.gate_snapshot()
    plan_gate = gate_snapshot.get("plan_validate_ok")
    return {
        "passed": bool(
            gate_snapshot.get("ir_validate_ok")
            and gate_snapshot.get("queue_validate_ok")
            and gate_snapshot.get("ui_load_safe_ok")
            and (plan_gate is not False)
        ),
        "canvas_apply_allowed": context.canvas_apply_allowed,
        "queue_allowed": context.queue_allowed,
        "gates": {
            "python_load_ok": gate_snapshot.get("python_load_ok"),
            "ir_validate_ok": gate_snapshot.get("ir_validate_ok"),
            "ui_load_safe_ok": gate_snapshot.get("ui_load_safe_ok"),
            "queue_validate_ok": gate_snapshot.get("queue_validate_ok"),
            "plan_validate_ok": plan_gate,
            "state_match_ok": gate_snapshot.get("state_match_ok"),
        },
        "stages": {
            "lower": _narrative_stage_payload(context.stage_results.get("lower")),
            "validate": _narrative_stage_payload(context.stage_results.get("validate")),
            "queue": _narrative_stage_payload(context.stage_results.get("queue")),
        },
    }


def _narrative_research_payload(state: AgentEditState) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    summary = " ".join((state.executor_research_summary or "").split())
    if summary:
        payload["summary"] = summary[:240]
    warnings = [str(item).strip() for item in state.executor_research_warnings if str(item).strip()]
    if warnings:
        payload["warnings"] = warnings[:3]
    plan = state.execution_plan
    if plan is not None:
        plan_id = getattr(plan, "plan_id", None)
        if isinstance(plan_id, str) and plan_id.strip():
            payload["plan_id"] = plan_id.strip()
    return payload


def _narrative_revision_payload(state: AgentEditState) -> dict[str, Any]:
    evidence = state.revision_evidence
    scoped = evidence.scoped_diff if evidence is not None else None
    if evidence is None and scoped is None:
        return {}
    payload: dict[str, Any] = {}
    candidate_eligible = getattr(evidence, "candidate_eligible", None)
    if candidate_eligible is None and scoped is not None:
        candidate_eligible = getattr(scoped, "candidate_eligible", None)
    if candidate_eligible is not None:
        payload["candidate_eligible"] = bool(candidate_eligible)
    blockers = ()
    if scoped is not None:
        blockers = getattr(scoped, "eligibility_blockers", ()) or ()
    elif evidence is not None:
        blockers = getattr(evidence, "eligibility_blockers", ()) or ()
    blocker_list = [str(item).strip() for item in blockers if str(item).strip()]
    if blocker_list:
        payload["eligibility_blockers"] = blocker_list[:4]
    readiness = getattr(evidence, "readiness", None) if evidence is not None else None
    readiness_blockers = getattr(readiness, "readiness_blockers", ()) if readiness is not None else ()
    readiness_list = [str(item).strip() for item in readiness_blockers if str(item).strip()]
    if readiness_list:
        payload["readiness_blockers"] = readiness_list[:3]
    topology = getattr(evidence, "topology", None) if evidence is not None else None
    mismatches = getattr(topology, "socket_type_mismatches", ()) if topology is not None else ()
    mismatch_payloads = _narrative_issue_payloads(mismatches, limit=3)
    if mismatch_payloads:
        payload["socket_type_mismatches"] = mismatch_payloads
    return payload


def _compact_change_details_payload(change_details: Mapping[str, Any]) -> dict[str, Any]:
    operations = change_details.get("operations")
    compact_operations: list[dict[str, Any]] = []
    if isinstance(operations, list):
        for item in operations[:5]:
            if not isinstance(item, Mapping):
                continue
            compact_item = {
                "uid": item.get("uid"),
                "field_path": item.get("field_path"),
                "summary": item.get("summary"),
            }
            compact_operations.append(_json_safe(compact_item))
    payload = {
        "landed_operation_count": int(change_details.get("landed_operation_count") or 0),
        "done_summary": str(change_details.get("done_summary") or "").strip(),
        "final_summary": str(change_details.get("final_summary") or "").strip(),
        "operations": compact_operations,
    }
    if "gate_a" in change_details:
        payload["gate_a"] = _json_safe(change_details.get("gate_a"))
    if "gate_b" in change_details:
        payload["gate_b"] = _json_safe(change_details.get("gate_b"))
    advisory = change_details.get("layout_reorganisation")
    if isinstance(advisory, Mapping):
        payload["layout_reorganisation"] = _json_safe(dict(advisory))
    return payload


def _post_edit_reorganisation_advice_sentence(state: AgentEditState) -> str:
    advisory = getattr(state, "post_edit_reorganisation_advisory", None)
    if not isinstance(advisory, Mapping):
        return ""
    if advisory.get("result") != "offer_reorganisation":
        return ""
    command = advisory.get("suggested_command")
    command_text = (
        command
        if isinstance(command, str) and command.strip()
        else "/reorganise_comfy_workflow"
    )
    return (
        "The edit is ready to review, and the canvas may benefit from "
        f"{command_text}."
    )


def _append_post_edit_reorganisation_advice(message: str, state: AgentEditState) -> str:
    advice = _post_edit_reorganisation_advice_sentence(state)
    if not advice:
        return message
    base = ensure_sentence_message(message, fallback="The candidate is ready to review.")
    return f"{base} {advice}"


def _narrative_context_payload(
    state: AgentEditState,
    context: TurnContext,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    public_outcome: str | None = None,
    apply_eligibility: ApplyEligibility | None = None,
    change_details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if change_details is None:
        change_details = _change_details_payload(state, context)
    compact_change_details = _compact_change_details_payload(change_details)
    landed_operation_count = int(compact_change_details.get("landed_operation_count") or 0)
    graph_changed = bool(_batch_candidate_graph_changed(state) or landed_operation_count > 0)
    internal_kind = outcome.kind if outcome is not None else ("failure" if failure is not None else "unknown")
    if apply_eligibility is None:
        apply_eligibility = context.apply_eligibility
    validation = _validation_summary_payload(context)
    payload: dict[str, Any] = {
        "task": " ".join((state.task or "").split())[:240],
        "route": state.route or "",
        "outcome": {
            "internal_kind": internal_kind,
            "public_kind": public_outcome or "",
            "batch_exit_mode": state.batch_exit_mode or "",
            "clarification_question": (
                outcome.question.strip()
                if outcome is not None and isinstance(outcome.question, str) and outcome.question.strip()
                else ""
            ),
        },
        "change": {
            "graph_changed": graph_changed,
            "landed_operation_count": landed_operation_count,
            "operations": compact_change_details.get("operations", []),
        },
        "validation": validation,
        "apply_eligibility": apply_eligibility.to_dict(),
        "change_details": compact_change_details,
        "diagnostics": {
            "delta": _narrative_issue_payloads(state.delta_diagnostics),
            "lowering": _narrative_issue_payloads(state.lowering_evidence),
        },
        "research": _narrative_research_payload(state),
        "revision": _narrative_revision_payload(state),
    }
    if failure is not None:
        payload["failure"] = {
            "kind": failure.kind.value,
            "stage": failure.stage,
            "retryable": failure.retryable,
            "graph_unchanged": failure.graph_unchanged,
            "next_action": failure.next_action,
            "message": " ".join((failure.user_facing_message or "").split())[:240],
        }
    return _json_safe(payload)


def _fallback_narrative_message(
    state: AgentEditState,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    narrative_context: Mapping[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> str:
    if failure is not None:
        if state.batch_exit_mode == _BATCH_EXIT_BUDGET or failure.kind is FailureKind.BATCH_BUDGET_EXHAUSTED:
            warning = ensure_sentence_message(
                "I ran out of turn budget before completing the remaining changes",
                fallback=state.batch_final_summary or failure.user_facing_message,
            )
        else:
            warning = ensure_sentence_message(
                failure.user_facing_message,
                fallback=failure.message or "The graph is unchanged.",
            )
        lead = _landed_edit_lead(state)
        if lead:
            return f"{lead} {warning}".strip()
        return warning

    if outcome is None:
        return ensure_sentence_message(state.user_message, fallback="The agent edit turn completed.")

    if outcome.kind == "edit":
        message = _humanized_edit_message(state)
        if fallback_reason in {"provider_failure", "malformed_response", "refused_narrative", "timeout"}:
            message = ensure_sentence_message(message, fallback="The candidate is ready to review.")
        return _append_post_edit_reorganisation_advice(message, state)
    if outcome.kind == "edit+clarify":
        question = (
            outcome.question.strip()
            if isinstance(outcome.question, str) and outcome.question.strip()
            else "What detail should I use before continuing?"
        )
        lead = _landed_edit_lead(state)
        if lead:
            return f"{lead} {ensure_sentence_message(question, fallback=question)}".strip()
        return ensure_sentence_message(question, fallback="What detail should I use before continuing?")
    if outcome.kind == "clarify":
        question = (
            outcome.question.strip()
            if isinstance(outcome.question, str) and outcome.question.strip()
            else "What detail should I use before continuing?"
        )
        return ensure_sentence_message(question, fallback="What detail should I use before continuing?")
    if outcome.kind == "noop":
        return _humanized_noop_message(state)
    if outcome.kind == "budget":
        return ensure_sentence_message(
            "I ran out of turn budget before completing the remaining changes",
            fallback=state.batch_final_summary or state.user_message,
        )

    if narrative_context is not None:
        change = narrative_context.get("change")
        if isinstance(change, Mapping) and int(change.get("landed_operation_count") or 0) > 0:
            return _humanized_edit_message(state)
    return ensure_sentence_message(state.user_message, fallback="The agent edit turn completed.")


def _validate_narrative_message(
    message: Any,
    *,
    narrative_context: Mapping[str, Any],
) -> dict[str, Any]:
    text = " ".join(str(message or "").split())
    issues: list[str] = []
    if not text:
        issues.append("empty_message")
        return {"ok": False, "message": "", "issues": issues}

    lowered = text.lower()
    for pattern in _NARRATIVE_GATE_JARGON_PATTERNS:
        if pattern.search(text):
            issues.append("exposed_gate_jargon")
            break

    outcome_payload = narrative_context.get("outcome")
    change_payload = narrative_context.get("change")
    validation_payload = narrative_context.get("validation")
    internal_kind = outcome_payload.get("internal_kind") if isinstance(outcome_payload, Mapping) else ""
    question = outcome_payload.get("clarification_question") if isinstance(outcome_payload, Mapping) else ""
    landed_operation_count = (
        int(change_payload.get("landed_operation_count") or 0)
        if isinstance(change_payload, Mapping)
        else 0
    )
    graph_changed = bool(change_payload.get("graph_changed")) if isinstance(change_payload, Mapping) else False
    validation_passed = bool(validation_payload.get("passed")) if isinstance(validation_payload, Mapping) else False

    claims_edit = any(pattern.search(text) for pattern in _NARRATIVE_EDIT_CLAIM_PATTERNS)
    claims_no_edit = any(pattern.search(text) for pattern in _NARRATIVE_NO_EDIT_PATTERNS)
    if internal_kind in {"edit", "edit+clarify"}:
        if claims_no_edit:
            issues.append("contradicts_edit_outcome")
        if landed_operation_count <= 0 or not graph_changed:
            issues.append("edit_outcome_without_landed_operations")
    else:
        if claims_edit:
            issues.append("contradicts_no_edit_outcome")

    if landed_operation_count <= 0 and claims_edit:
        issues.append("claims_landed_edits_when_none_landed")
    if landed_operation_count > 0 and claims_no_edit:
        issues.append("claims_no_edit_when_edits_landed")

    for match in _NARRATIVE_COUNT_PATTERN.finditer(text):
        claimed_count = int(match.group(1))
        if claimed_count != landed_operation_count:
            issues.append("incorrect_landed_operation_count")
            break

    if validation_passed:
        if any(pattern.search(text) for pattern in _NARRATIVE_VALIDATION_FAIL_PATTERNS):
            issues.append("contradicts_validation_success")
    else:
        if any(pattern.search(text) for pattern in _NARRATIVE_VALIDATION_PASS_PATTERNS):
            issues.append("contradicts_validation_failure")

    if internal_kind in {"clarify", "edit+clarify"}:
        has_question_shape = "?" in text or bool(_NARRATIVE_QUESTION_START.search(text))
        if not has_question_shape:
            issues.append("clarify_without_question")
        if isinstance(question, str) and question.strip() and question.strip("?").lower() not in lowered:
            issues.append("clarify_question_missing")

    return {
        "ok": not issues,
        "message": text,
        "issues": issues,
    }


def _narrative_artifact_path(state: AgentEditState, path: Path) -> Path:
    if path.is_absolute():
        return path
    return state.turn_dir / path


def _synthesize_post_validation_narrative(
    state: AgentEditState,
    context: TurnContext,
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
    public_outcome: str | None = None,
    apply_eligibility: ApplyEligibility | None = None,
    change_details: Mapping[str, Any] | None = None,
) -> str:
    if change_details is None:
        change_details = _change_details_payload(state, context)
    context_path = _narrative_artifact_path(state, state.narrative_context_path)
    request_path = _narrative_artifact_path(state, state.narrative_request_path)
    response_path = _narrative_artifact_path(state, state.narrative_response_path)
    validation_path = _narrative_artifact_path(state, state.narrative_validation_path)
    state.narrative_context_path = context_path
    state.narrative_request_path = request_path
    state.narrative_response_path = response_path
    state.narrative_validation_path = validation_path
    narrative_context = _narrative_context_payload(
        state,
        context,
        outcome=outcome,
        failure=failure,
        public_outcome=public_outcome,
        apply_eligibility=apply_eligibility,
        change_details=change_details,
    )
    write_json_artifact(context_path, narrative_context)

    route = os.getenv("VIBECOMFY_NARRATOR_ROUTE") or None
    model = os.getenv("VIBECOMFY_NARRATOR_MODEL") or None
    fallback_message = _fallback_narrative_message(
        state,
        outcome=outcome,
        failure=failure,
        narrative_context=narrative_context,
    )
    final_message = fallback_message
    fallback_reason = "deterministic_only"
    attempted = bool(route or model)
    raw_executor_message = " ".join((state.raw_executor_message or "").split())
    request_payload: dict[str, Any] = {
        "attempted": attempted,
        "route": route,
        "model": model,
        "response_contract": "json",
        "raw_executor_message": raw_executor_message[:240],
    }
    response_payload: dict[str, Any] = {
        "attempted": attempted,
        "selected_source": "fallback",
        "selected_message": fallback_message,
    }
    validation_payload: dict[str, Any]

    if attempted:
        messages = [
            {"role": "system", "content": _narrator_system_message()},
            {
                "role": "user",
                "content": _narrator_user_message(
                    narrative_context=narrative_context,
                    raw_executor_message=raw_executor_message,
                    fallback_message=fallback_message,
                ),
            },
        ]
        request_payload["messages"] = messages
        write_json_artifact(request_path, request_payload)
        try:
            narrator_response = run_model_turn(
                task="Write the final post-validation narrative message.",
                messages=messages,
                route=route,
                model=model,
                response_contract="json",
                profiling_context={
                    "surface": "agent_edit_narrator",
                    "session_dir": str(state.session_dir),
                    "turn_dir": str(state.turn_dir),
                },
            )
            response_payload["provider_response"] = _json_safe(dict(narrator_response))
            candidate_message = _narrator_message_from_response(narrator_response)
            candidate_validation = _validate_narrative_message(
                candidate_message,
                narrative_context=narrative_context,
            )
            response_payload["candidate_message"] = candidate_message
            if candidate_validation.get("ok"):
                final_message = candidate_validation["message"]
                fallback_reason = ""
                response_payload["selected_source"] = "narrator"
                response_payload["selected_message"] = final_message
                validation_payload = {
                    "attempted": True,
                    "selected_source": "narrator",
                    "selected_message": final_message,
                    "candidate_validation": candidate_validation,
                }
            else:
                fallback_reason = "refused_narrative"
                response_payload["selected_message"] = fallback_message
                response_payload["fallback_reason"] = fallback_reason
                validation_payload = {
                    "attempted": True,
                    "selected_source": "fallback",
                    "selected_message": fallback_message,
                    "candidate_validation": candidate_validation,
                    "fallback_reason": fallback_reason,
                }
        except TimeoutError as exc:
            fallback_reason = "timeout"
            response_payload["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            response_payload["fallback_reason"] = fallback_reason
            validation_payload = {
                "attempted": True,
                "selected_source": "fallback",
                "selected_message": fallback_message,
                "fallback_reason": fallback_reason,
                "error": response_payload["error"],
            }
        except (MalformedModelJSON, MissingRequiredField) as exc:
            fallback_reason = "malformed_response"
            response_payload["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            response_payload["fallback_reason"] = fallback_reason
            validation_payload = {
                "attempted": True,
                "selected_source": "fallback",
                "selected_message": fallback_message,
                "fallback_reason": fallback_reason,
                "error": response_payload["error"],
            }
        except ProviderError as exc:
            fallback_reason = "provider_failure"
            response_payload["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
            response_payload["fallback_reason"] = fallback_reason
            validation_payload = {
                "attempted": True,
                "selected_source": "fallback",
                "selected_message": fallback_message,
                "fallback_reason": fallback_reason,
                "error": response_payload["error"],
            }
    else:
        request_payload["skip_reason"] = "narrator_env_unset"
        write_json_artifact(request_path, request_payload)
        response_payload["skip_reason"] = "narrator_env_unset"
        validation_payload = {
            "attempted": False,
            "selected_source": "fallback",
            "selected_message": fallback_message,
            "fallback_reason": fallback_reason,
        }

    final_validation = _validate_narrative_message(
        final_message,
        narrative_context=narrative_context,
    )
    validation_payload["final_validation"] = final_validation
    response_payload["selected_message"] = final_message
    write_json_artifact(response_path, response_payload)
    write_json_artifact(validation_path, validation_payload)
    state.artifacts = {
        **(state.artifacts or {}),
        "narrative_context": str(context_path),
        "narrative_request": str(request_path),
        "narrative_response": str(response_path),
        "narrative_validation": str(validation_path),
    }
    return final_message


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
    if outcome.kind == "noop" and _resolver_candidates_from_batch_turns(state):
        return ensure_sentence_message(
            state.user_message,
            fallback=(
                "I found external node evidence, but could not apply a grounded "
                "workflow pattern to the current graph."
            ),
        )
    if outcome.kind == "noop":
        return _humanized_noop_message(state)
    return ensure_sentence_message(state.user_message, fallback="The agent edit turn completed.")


'''
