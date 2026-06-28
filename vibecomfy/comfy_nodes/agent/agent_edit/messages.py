from __future__ import annotations

import difflib
import json
import re
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from vibecomfy.porting.edit.types import FieldChange

from ..contracts import (
    FailureEnvelope,
    FailureKind,
    TurnContext,
    TurnOutcome,
    _ABSENT_FIELD_OLD,
)
from ..provider import (
    AgentTurnResult,
    BatchTurnResult,
    ensure_sentence_message,
)
from ..session import structural_graph_hash
from .clarify import (
    _BATCH_EXIT_BUDGET,
    _BATCH_EXIT_NOOP,
)
from .fields import _real_field_changes
from .labels import (
    _change_subject,
    _display_value,
    _format_query_output,
    _format_statement_source,
    _join_human_list,
    _node_label_by_uid,
    _structural_change_phrases,
)
from .budget import _json_safe


def _total_landed_edit_count(state: "AgentEditState") -> int:
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


def _discovery_stop_message(state: "AgentEditState") -> str:
    return (
        "I could not find a workflow precedent or installed/provisional node schema "
        "specific enough to safely switch this graph to the requested workflow. "
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


def _batch_candidate_graph_changed(state: "AgentEditState") -> bool:
    if not isinstance(state.ui_payload, Mapping):
        return False
    return structural_graph_hash(state.ui_payload) != structural_graph_hash(state.graph)


def _landed_edit_lead(state: "AgentEditState") -> str:
    count = _total_landed_edit_count(state)
    if count <= 0:
        return ""
    noun = "edit" if count == 1 else "edits"
    return f"Applied {count} {noun}."


def _human_change_phrase(
    change: "FieldChange",
    labels: Mapping[str, str] | None = None,
    *,
    graph: Mapping[str, Any] | None = None,
    old_graph: Mapping[str, Any] | None = None,
    new_graph: Mapping[str, Any] | None = None,
) -> str:
    from .labels import _is_link_endpoint, _resolve_endpoint_label

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


def _humanized_edit_message(state: "AgentEditState") -> str:
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


def _terminal_answer_message(state: "AgentEditState") -> str | None:
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


def _humanized_noop_message(state: "AgentEditState") -> str:
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


def _revision_rejected_candidate_message(state: "AgentEditState") -> str:
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


def _revision_candidate_retry_hint(state: "AgentEditState") -> str:
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


def _operation_detail_payload(changes: tuple["FieldChange", ...]) -> list[dict[str, Any]]:
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


def _change_details_payload(state: "AgentEditState", context: TurnContext) -> dict[str, Any]:
    gate_snapshot = context.gate_snapshot()
    gate_a = gate_snapshot.get("edit_scope_ok") or gate_snapshot.get("python_load_ok")
    gate_b = gate_snapshot.get("isomorphic_ok") or gate_snapshot.get("ui_fidelity_ok")
    operations = _operation_detail_payload(tuple(state.batch_field_changes or ()))
    return {
        "landed_operation_count": _total_landed_edit_count(state),
        "done_summary": state.batch_done_summary or "",
        "final_summary": state.batch_final_summary or "",
        "gate_a": _json_safe(gate_a),
        "gate_b": _json_safe(gate_b),
        "operations": operations,
        "batch_turns": _json_safe(state.batch_turns),
    }


def _batch_warning_sentence(
    state: "AgentEditState",
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
    state: "AgentEditState",
    *,
    outcome: TurnOutcome | None = None,
    failure: FailureEnvelope | None = None,
) -> str:
    # Lazy import to avoid circular dependency with edit.py facade
    from ..edit import _resolver_candidates_from_batch_turns

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
                "I found custom-node evidence, but could not apply a grounded "
                "workflow pattern to the current graph."
            ),
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


def _batch_research_memory_summary(state: Any, *, max_items: int = 3) -> str:
    """Carry compact prior research/query evidence across batch turns.

    Packet-aware: when a statement detail includes ``precedent_packet``, a
    compact summary is built from structured option fields (source title,
    source tier, one-line pattern summary, caveat count) instead of
    reserializing the full packet or dumping ``query_output`` verbatim.
    Statements without a packet fall back to the marker-matched
    ``query_output`` path for non-research turns (e.g. ``search()``).
    """
    records: list[str] = []
    for turn in getattr(state, "batch_turns", ()) or ():
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        turn_number = turn.get("turn_number")
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue

            # --- packet-aware compact path ----------------------------
            precedent_packet = detail.get("precedent_packet")
            if isinstance(precedent_packet, Mapping):
                packet_record = _summarize_precedent_packet(
                    precedent_packet, turn_number
                )
                if packet_record:
                    records.append(packet_record)
                continue

            # --- legacy marker-matched query_output path --------------
            query_output = str(detail.get("query_output") or "").strip()
            if not query_output:
                continue
            relevant = any(
                marker in query_output
                for marker in (
                    "Concrete workflow pattern found",
                    "github_workflow_json",
                    "source_workflow_path",
                    "No node signature found",
                    "registry/schema lookup",
                    "Registry check",
                )
            ) or bool(detail.get("resolver_candidates"))
            if not relevant:
                continue
            query = str(detail.get("research_query") or detail.get("query") or "").strip()
            sources = detail.get("requested_research_sources") or detail.get("research_sources")
            source_text = f" sources={tuple(sources)!r}" if isinstance(sources, (list, tuple)) else ""
            header = f"turn {turn_number}: {query or statement.get('source') or 'query'}{source_text}"
            records.append(f"- {header}\n{_format_query_output(query_output, max_chars=1000)}")
    if not records:
        return ""
    return "\n\n".join(records[-max_items:])


def _summarize_precedent_packet(
    packet: Mapping[str, Any], turn_number: Any
) -> str | None:
    """Build a compact one-line-per-option summary from a precedent packet dict.

    Carries only source title, source tier, one-line pattern summary, and
    caveat count.  Does **not** reserialize the full packet and omits every
    forbidden public-key name (winner, best, selected, score, rank, primary,
    preferred, chosen, pick, choice, top, recommended).
    """
    options = packet.get("options")
    if not isinstance(options, (list, tuple)) or not options:
        return None

    packet_warnings = packet.get("warnings")
    packet_caveats = (
        len(packet_warnings) if isinstance(packet_warnings, (list, tuple)) else 0
    )

    lines: list[str] = [
        f"turn {turn_number}: research evidence "
        f"({len(options)} precedent option(s)):"
    ]
    for opt in options:
        if not isinstance(opt, Mapping):
            continue

        title = str(opt.get("source_class_type") or "(unknown)")

        # --- one-line pattern summary ---------------------------------
        description = str(opt.get("description", "")).strip()
        if description:
            summary_line = description.split("\n")[0].strip()
            if len(summary_line) > 120:
                summary_line = summary_line[:117] + "..."
        else:
            summary_line = "(no description)"

        # --- source tier from notes -----------------------------------
        notes = opt.get("notes")
        tier = ""
        option_caveats = 0
        if isinstance(notes, (list, tuple)):
            for note in notes:
                if not isinstance(note, str):
                    continue
                if note.startswith("source: "):
                    tier = note[len("source: "):]
                elif note.strip():
                    option_caveats += 1

        caveats = packet_caveats + option_caveats
        caveat_str = f" [{caveats} caveat(s)]" if caveats else ""
        tier_str = f" tier={tier}" if tier else ""

        lines.append(f"  - {title}{tier_str}: {summary_line}{caveat_str}")

    return "\n".join(lines)


def _premature_missing_custom_node_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str:
    """Reject missing-custom-node stops that skipped required registry evidence."""
    message_text = str(clarify_message or "").casefold()
    if not any(term in message_text for term in ("missing", "not installed", "install", "custom node")):
        return ""

    concrete_workflow_seen = False
    last_missing_turn = -1
    missing_classes: list[str] = []
    registry_after_missing = False
    for turn in getattr(state, "batch_turns", ()) or ():
        if not isinstance(turn, Mapping):
            continue
        raw_turn_number = turn.get("turn_number")
        turn_number = raw_turn_number if isinstance(raw_turn_number, int) else -1
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue
            query_output = str(detail.get("query_output") or "")
            if "Concrete workflow pattern found" in query_output or "github_workflow_json" in query_output:
                concrete_workflow_seen = True
            if (
                detail.get("query") == "research"
                and "registry" in tuple(detail.get("requested_research_sources") or ())
                and turn_number > last_missing_turn >= 0
            ):
                registry_after_missing = True
            if "No node signature found for exact class type(s):" in query_output:
                last_missing_turn = turn_number
                registry_after_missing = False
                for match in re.findall(r"'([^']+)'", query_output):
                    if match and match not in missing_classes:
                        missing_classes.append(match)

    if not concrete_workflow_seen or last_missing_turn < 0 or registry_after_missing:
        return ""

    class_text = ", ".join(missing_classes[:8]) if missing_classes else "the exact missing workflow classes"
    return (
        "Premature missing-custom-node clarification rejected: workflow/example evidence has named "
        f"missing exact class(es) ({class_text}), but no registry/schema research turn has verified "
        "the owning custom-node pack after that local schema miss. Next turn must run "
        "`research(\"<exact missing class names or concrete pack/family>\", sources=[\"registry\"])` "
        "using the workflow-sourced class names, then either apply with grounded schemas/provisional "
        "custom-node evidence or clarify with the registry-backed missing pack."
    )


def _premature_workflow_schema_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str:
    """Reject stops that ignore concrete workflow-derived constructor schemas."""
    message_text = str(clarify_message or "").casefold()
    if not any(term in message_text for term in ("not found", "lacks", "missing", "cannot", "without knowing")):
        return ""

    schema_classes: list[str] = []
    last_schema_turn = -1
    landed_after_schema = False
    for turn in getattr(state, "batch_turns", ()) or ():
        if not isinstance(turn, Mapping):
            continue
        raw_turn_number = turn.get("turn_number")
        turn_number = raw_turn_number if isinstance(raw_turn_number, int) else -1
        landed_count = turn.get("landed_op_count")
        if isinstance(landed_count, int) and landed_count > 0 and turn_number > last_schema_turn >= 0:
            landed_after_schema = True
        statements = turn.get("statements")
        if not isinstance(statements, list):
            continue
        for statement in statements:
            if not isinstance(statement, Mapping):
                continue
            detail = statement.get("detail")
            if not isinstance(detail, Mapping):
                continue
            query_output = str(detail.get("query_output") or "")
            matches = [
                *re.findall(r"workflow_schema\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", query_output),
                *re.findall(r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", query_output),
            ]
            if not matches:
                continue
            last_schema_turn = max(last_schema_turn, turn_number)
            landed_after_schema = False
            for class_type in matches:
                if class_type not in schema_classes:
                    schema_classes.append(class_type)

    if not schema_classes or landed_after_schema:
        return ""
    class_text = ", ".join(schema_classes[:8])
    return (
        "Premature clarification rejected: workflow-derived constructor schemas are already available "
        f"for {class_text}. The current graph lacking those nodes is not a reason to stop; it is the "
        "reason to add the workflow-sourced provisional nodes. Next turn must land the smallest "
        "evidence-backed workflow-pattern edit using those constructors, or run a strictly necessary "
        "additional schema/registry lookup for a named class that is still actually missing."
    )


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
    ``CompactDiagnostic`` fields --- it never invents schema hints or other
    generated content.
    """
    # Lazy import to avoid circular dependency
    from .artifacts import _compact_diag_to_dict

    statement_lines: list[str] = []
    landed_count = 0
    failed_count = 0
    for statement in batch_result.statements:
        if statement.landed:
            landed_count += 1
        if not statement.ok:
            failed_count += 1
        marker = "\u2713" if statement.ok else "\u2717"
        status = "landed" if statement.landed else "not landed"
        op_kind = statement.op_kind or "statement"
        source_text = _format_statement_source(statement.source)
        line = (
            f"{marker} Statement {statement.statement_index}: "
            f"{op_kind} \u2014 {status}"
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
            "do not search again unless the last query failed to identify a usable path. "
            "If a workflow-derived class has a usable signature, use that exact class as the "
            "workflow pattern even when its name is generic; do not invent or search for a "
            "branded variant that did not appear in the workflow evidence. "
            "After an exact local schema miss for a workflow-sourced class, use registry/schema "
            "lookup for that exact class instead of repeating workflow search."
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
    ``CompactDiagnostic`` fields --- no invented content.
    """
    # Lazy import to avoid circular dependency
    from .artifacts import _compact_diag_to_dict

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
