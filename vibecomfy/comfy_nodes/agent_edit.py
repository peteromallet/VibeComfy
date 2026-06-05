from __future__ import annotations

import ast
import dataclasses
import difflib
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .agent_audit import (
    artifact_ref_for_path,
    normalize_agent_edit_v2_metadata,
    write_allocation_failure_audit,
    write_audit,
    write_json_artifact,
)
from .agent_contracts import (
    ArtifactRef,
    FailureEnvelope,
    FailureKind,
    StageResult,
    TurnContext,
    TurnOutcome,
    apply_eligibility_payload,
    classify_failure,
    derive_apply_eligibility,
    failure_envelope,
    product_failure_envelope_fields,
    success_envelope,
    turn_envelope,
)
from vibecomfy.porting.edit_types import FieldChange
from .agent_gates import (
    apply_stage_gate_updates,
    derive_gates,
    initialize_gates,
    update_state_match_gate,
)
from .agent_provider import (
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
from .agent_diagnostics import lower_stage_result, queue_stage_result
from .agent_session import (
    allocate_turn,
    payload_hash,
    record_idempotent_response,
    session_dir_for,
    structural_graph_hash,
    turn_dir_for,
)

if TYPE_CHECKING:
    from vibecomfy.porting.edit_session import EditSession
    from vibecomfy.workflow import VibeWorkflow

DeepSeekClient = Callable[[list[dict[str, str]]], dict[str, str]]

_SESSION_ROOT = Path("out/editor_sessions")
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
    batch_turns: list[dict[str, Any]] = field(default_factory=list)
    batch_field_changes: tuple[FieldChange, ...] = ()
    batch_budget_state: dict[str, Any] = field(default_factory=dict)
    batch_turn_count: int = 0
    batch_max_turns: int = 20
    batch_max_consecutive_errors: int = 3
    batch_feedback: str = ""
    batch_final_summary: str = ""
    batch_exit_mode: str = ""
    batch_done_summary: str = ""


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


def _landed_edit_lead(state: AgentEditState) -> str:
    count = _total_landed_edit_count(state)
    if count <= 0:
        return ""
    noun = "edit" if count == 1 else "edits"
    return f"Applied {count} {noun}."


def _batch_warning_sentence(
    state: AgentEditState,
    *,
    failure: FailureEnvelope | None = None,
    outcome: TurnOutcome | None = None,
) -> str:
    if failure is not None:
        if state.batch_exit_mode == _BATCH_EXIT_BUDGET:
            return ensure_sentence_message(
                "I ran out of batch budget before completing the remaining changes",
                fallback=state.batch_final_summary or failure.message,
            )
        return ensure_sentence_message(
            "Some requested edits did not land, so I stopped before applying the rest",
            fallback=failure.message or failure.user_facing_message,
        )
    if outcome is not None and outcome.kind == "edit+clarify":
        return "I still need clarification before continuing."
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
        if state.batch_done_summary:
            tail = ensure_sentence_message(
                state.batch_done_summary,
                fallback="The candidate is ready to apply.",
            )
            if lead:
                return f"{lead} {tail}".strip()
            return tail
        if lead:
            return lead
        return ensure_sentence_message(state.user_message, fallback="The candidate is ready to apply.")
    if outcome.kind == "edit+clarify":
        warning = _batch_warning_sentence(state, outcome=outcome)
        if lead:
            return f"{lead} {warning}".strip()
        return warning
    if outcome.kind == "clarify":
        return "I need clarification before continuing."
    if outcome.kind == "budget":
        return ensure_sentence_message(
            "I ran out of batch budget before completing the requested changes",
            fallback=state.batch_final_summary or state.user_message,
        )
    if outcome.kind == "noop":
        return ensure_sentence_message(
            state.batch_done_summary,
            fallback="No graph changes were applied.",
        )
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
    summary = (
        f"Batch summary: {landed_count} landed, {failed_count} failed, "
        f"{len(batch_result.diagnostics)} batch diagnostic(s), "
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
) -> dict[str, Any]:
    """Build a deterministic JSON teaching report from a :class:`BatchResult`.

    Every field is derived from ``BatchResult.statements`` and
    ``CompactDiagnostic`` fields — no invented content.
    """
    landed_count = sum(1 for s in batch_result.statements if s.landed)
    failed_count = sum(1 for s in batch_result.statements if not s.ok)
    return {
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

    agent_text: str = response.get("message", "")
    if not isinstance(agent_text, str) or not agent_text.strip():
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


def read_session_chat(
    session_root: Path,
    session_id: str,
    *,
    max_messages: int = 5,
) -> dict[str, Any]:
    """Read conversation history for a session from persisted turn artifacts.

    Scans turn directories under the session root in deterministic order,
    reads ``chat.json`` where present, falls back to same-turn
    ``request.json`` + ``response.json``, and returns the last
    *max_messages* display messages with session metadata.

    Returns:
        dict with keys: ``ok``, ``session_id``, ``session_path``,
        ``latest_turn_id``, ``detail_json_path``, ``messages``.
    """
    safe_id = _safe_session_id(session_id)
    session_dir = session_dir_for(session_root, safe_id)
    turns_dir = session_dir / "turns"

    if not turns_dir.is_dir():
        return {
            "ok": True,
            "session_id": safe_id,
            "session_path": str(session_dir),
            "latest_turn_id": None,
            "detail_json_path": None,
            "messages": [],
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
                agent_text: str = response.get("message", "")
                if not isinstance(agent_text, str) or not agent_text.strip():
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

        if chat_record is None:
            continue

        # Extract display messages from the chat record.
        messages = chat_record.get("messages", [])
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, dict) and msg.get("role") in ("user", "agent"):
                    all_messages.append({
                        "role": msg["role"],
                        "text": msg.get("text", ""),
                        "turn_id": msg.get("turn_id", turn_id),
                    })
        latest_turn_id = turn_id

    # Take the last N messages for display.
    display_messages = all_messages[-max_messages:] if max_messages > 0 else all_messages

    return {
        "ok": True,
        "session_id": safe_id,
        "session_path": str(session_dir),
        "latest_turn_id": latest_turn_id,
        "detail_json_path": (
            str(turns_dir / latest_turn_id / "response.json")
            if latest_turn_id
            else None
        ),
        "messages": display_messages,
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

    See docs/agent_edit_concrete_tree.md. Match is by litegraph node id, which is
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
    # Phase 1 (concrete-tree migration, docs/agent_edit_concrete_tree.md): give the
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
    update_state_match_gate(
        context,
        baseline_graph_hash=state.baseline_graph_hash,
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
    from vibecomfy.porting.edit_ledger import EditLedger

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    ledger = EditLedger.ingest(state.graph)
    state.guard_original_ui = ledger.stamped_copy()
    original_ui_ref = write_json_artifact(state.original_ui_path, state.guard_original_ui)
    update_state_match_gate(
        context,
        baseline_graph_hash=state.baseline_graph_hash,
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
    from vibecomfy.porting.edit_projection import render_edit_projection, ProjectionOptions

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
    messages = build_messages(task=state.task, python_source=state.python_before)
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
    from vibecomfy.porting.edit_ops import (
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
    from vibecomfy.porting.edit_session import EditSession

    start = time.monotonic()
    prepared_ui = state.guard_original_ui or state.graph
    session = EditSession(prepared_ui, schema_provider=state.schema_provider)
    state.batch_session = session
    initial_render = session.render()
    present_types = _present_class_types(session)
    signature_catalog = session.search(focus_types=present_types, formatted=True)
    available_node_names = _format_available_node_names(session.search(formatted=False))
    state.python_before = initial_render
    state.before_py_path.write_text(initial_render, encoding="utf-8")
    if isinstance(signature_catalog, str):
        state.batch_signature_catalog = signature_catalog

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
    consecutive_errors = 0
    total_landed = 0
    done_noop_nudges = 0
    done_error_nudges = 0
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []

    for turn_number in range(max_batches):
        budget_remaining = max_batches - turn_number
        messages = build_batch_messages(
            task=state.task,
            turn_number=turn_number,
            python_source=initial_render if turn_number == 0 else "",
            signature_catalog=state.batch_signature_catalog if turn_number == 0 else "",
            available_node_names=available_node_names if turn_number == 0 else "",
            diff=last_diff,
            report=last_report,
            budget_remaining=budget_remaining,
            max_batches=max_batches,
            conversation_messages=conversation_messages if turn_number == 0 else None,
        )
        request_entry = {
            "turn_number": turn_number,
            "messages": messages,
            "budget_remaining": budget_remaining,
        }
        request_log.append(request_entry)
        write_json_artifact(
            state.model_request_path,
            {"response_contract": "batch_repl", "turns": request_log},
        )

        if deepseek_client is not None:
            turn_result = _normalize_test_client_batch_response(deepseek_client(messages))
        else:
            turn_result = run_agent_turn_batch(
                state.task,
                messages,
                route=route,
                model=model,
        )

        state.provider_metadata = dict(turn_result.audit_metadata or {})
        state.user_message = turn_result.message
        clarify_split = split_terminal_clarify(turn_result.batch)
        clarify_message = clarify_split.message
        editable_batch = clarify_split.batch if clarify_message is not None else turn_result.batch
        if clarify_message is not None and not editable_batch.strip():
            state.batch_turn_count = turn_number + 1
            state.batch_exit_mode = (
                _BATCH_EXIT_EDIT_CLARIFY
                if _batch_has_landed_edits(state)
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

        turn_has_errors = (not batch_result.ok) or bool(batch_result.diagnostics)
        total_landed += len(batch_result.landed_ops)
        consecutive_errors = consecutive_errors + 1 if turn_has_errors else 0
        diff_text = _render_batch_diff(current_render, next_render)
        report_text = _format_batch_report(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
        )
        report_json = _format_batch_report_json(
            batch_result,
            consecutive_errors=consecutive_errors,
            budget_remaining=max_batches - (turn_number + 1),
        )
        state.batch_field_changes = state.batch_field_changes + tuple(batch_result.field_changes)
        turn_record = {
            "turn_number": turn_number,
            "batch": turn_result.batch,
            "message": turn_result.message,
            "route": turn_result.route,
            "model": turn_result.model,
            "provider_metadata": _json_safe(dict(turn_result.audit_metadata or {})),
            "batch_ok": batch_result.ok,
            "statement_count": len(batch_result.statements),
            "landed_op_count": len(batch_result.landed_ops),
            "diagnostics": report_json["diagnostics"],
            "statements": report_json["statements"],
            "field_changes": _field_changes_payload(batch_result.field_changes),
            "diff": diff_text,
            "report": report_text,
        }
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
                if _batch_has_landed_edits(state)
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
            and (turn_number + 1) < max_batches
            and consecutive_errors < max_consecutive_errors
        ):
            if total_landed == 0 and done_noop_nudges < 2:
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
                else:
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
                _BATCH_EXIT_DONE if _batch_has_landed_edits(state) else _BATCH_EXIT_NOOP
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
        f"Stopped after {state.batch_turn_count} batch turn(s); "
        f"{state.batch_budget_state.get('remaining_batches', 0)} batch(es) remaining."
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
    from .agent_diagnostics import validate_stage_result

    start = time.monotonic()
    result = validate_stage_result(state.edited_workflow, schema_provider=state.schema_provider)
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_emit(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.layout import evaluate_felt_delta
    from vibecomfy.porting.layout_store import store_from_ui_json, write_store
    from vibecomfy.porting.ui_emitter import emit_ui_json

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
    from vibecomfy.porting.edit_apply import apply_delta
    from vibecomfy.porting.edit_apply import (
        AppliedAddNodeSpec,
        ResolvedFieldRef,
        ResolvedRemoveNodePlan,
    )
    from vibecomfy.porting.edit_ops import op_to_dict

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
    result = apply_delta(
        state.guard_original_ui or state.graph,
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
    return response


def _build_batch_repl_response(
    state: AgentEditState,
    context: TurnContext,
) -> dict[str, Any]:
    has_candidate = state.batch_exit_mode in {_BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_DONE}
    compatibility_fields = _build_compatibility_response_fields(state)
    response_apply_eligibility = derive_apply_eligibility(
        context,
        has_candidate=has_candidate,
        candidate_state="candidate",
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
    if state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY:
        outcome = TurnOutcome.clarify(question=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY:
        question = state.user_message or None
        outcome = TurnOutcome.edit_and_clarify(
            changes=state.batch_field_changes,
            question=question,
        )
    elif state.batch_exit_mode == _BATCH_EXIT_DONE:
        outcome = TurnOutcome.edit(changes=state.batch_field_changes)
    elif state.batch_exit_mode == _BATCH_EXIT_BUDGET:
        outcome = TurnOutcome.budget(reason=state.batch_final_summary or None)
    else:
        outcome = TurnOutcome.noop(reason=state.batch_done_summary or state.user_message or None)
    message = _synthesize_batch_repl_message(state, outcome=outcome)
    response.update(
        turn_envelope(
            message=message,
            outcome=outcome,
            candidate=_build_candidate_payload(
                state,
                compatibility_fields=compatibility_fields,
                has_candidate=has_candidate,
            ),
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
    response.update(compatibility_fields)
    if state.batch_exit_mode in {_BATCH_EXIT_PURE_CLARIFY, _BATCH_EXIT_EDIT_CLARIFY}:
        response["clarification_required"] = True
        response["graph_unchanged"] = state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
    elif state.batch_done_summary:
        response["done_summary"] = state.batch_done_summary
    response["batch_turns"] = _json_safe(state.batch_turns)
    return response


def _build_dev_success_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    contract: str,
) -> dict[str, Any]:
    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
        apply_eligibility=derive_apply_eligibility(
            context,
            has_candidate=True,
            candidate_state="candidate",
        ),
        canvas_apply_allowed=context.canvas_apply_allowed,
        queue_allowed=context.queue_allowed,
    )
    response.update(_build_compatibility_response_fields(state))
    if contract == "delta":
        from vibecomfy.porting.edit_ops import op_to_dict

        response["delta_ops"] = [op_to_dict(op) for op in state.delta_ops]
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
            or (name == "agent_batch" and _is_provider_exception(exc))
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
        failure = failure_envelope(
            failure_kind or FailureKind.VALIDATION_ERROR,
            name,
            context,
            agent_failure_context={
                "explanation": f"Stage {name} blocked the agent edit.",
                "issues": [dict(issue) for issue in result.issues if isinstance(issue, dict)],
            },
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
    from vibecomfy.schema import get_schema_provider

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
        return _product_failure_response(failure)

    task = payload.get("task")
    graph = payload.get("graph")
    if not isinstance(task, str) or not task.strip():
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "`task` is required."},
        )
        return _product_failure_response(failure)
    if not isinstance(graph, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={
                "explanation": "`graph` must be a ComfyUI UI JSON object."
            },
        )
        return _product_failure_response(failure)

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
        return allocation.replay.response
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
        return _product_failure_response(failure)

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
    if isinstance(payload.get("max_batches"), int) and payload["max_batches"] > 0:
        state.batch_max_turns = int(payload["max_batches"])
    if (
        isinstance(payload.get("max_consecutive_errors"), int)
        and payload["max_consecutive_errors"] > 0
    ):
        state.batch_max_consecutive_errors = int(payload["max_consecutive_errors"])

    contract = _agent_edit_contract()

    route = payload.get("route") if isinstance(payload.get("route"), str) else None
    model = payload.get("model") if isinstance(payload.get("model"), str) else None

    # Load session-local last-five conversation messages for prompt memory.
    # Only the batch_repl product path injects them (SD2); delta/full-dev
    # paths persist chat artifacts but do not receive prompt memory in this
    # slim v1 milestone.
    conversation_messages: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        try:
            chat = read_session_chat(root, session_id, max_messages=5)
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
                route=route,
                model=model,
                client_id=client_id,
                conversation_messages=conversation_messages,
            )
        elif contract == "delta":
            state = _run_delta_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=route,
                model=model,
            )
        else:
            state = _run_full_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=route,
                model=model,
            )
    except _StageBlocked as blocked:
        response = _failure_response(
            state,
            context,
            contract=contract,
            failure=blocked.failure or classify_failure(blocked.result.stage, blocked, context),
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

    if contract == "delta":
        response = _build_dev_success_response(state, context, contract=contract)
    elif contract == "batch_repl":
        response = _build_batch_repl_response(state, context)
    else:
        response = _build_dev_success_response(state, context, contract=contract)
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
        return _product_failure_response(failure)
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
