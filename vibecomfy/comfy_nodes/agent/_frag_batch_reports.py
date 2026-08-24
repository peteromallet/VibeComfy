"""
Batch-loop report rendering helpers (T-038 extraction of the edit_batch_reports fragment).

Extracted from the edit.py exec-assembled fragments (T-038, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Imports of sibling _frag modules follow
the foundation dependency order; names that would form an import cycle are
resolved lazily at call time (marked with a T-038 late import comment).
"""
import ast
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping
from vibecomfy.comfy_nodes.agent.contracts import FailureKind
from ._frag_batch_memory import _format_query_output, _format_statement_source
from ._frag_chat import _json_safe
from ._frag_humanize import _batch_candidate_graph_changed
from ._frag_session_bundle import _compact_diag_to_dict

import re as _re

_DIAGNOSTIC_DETAIL_KEYS = (
    "choices",
    "valid_fields",
    "semantic_aliases",
    "available_slots",
    "min",
    "max",
)
_DETAIL_LIST_CAP = 8
_DETAIL_ALIAS_CAP = 8

# ── Duplicate-query cycle detection (Part C) ─────────────────────────────────
# Match top-level ``search(...)`` calls in a batch statement source and capture
# the ``focus_types`` / ``compatible_output_type`` / ``compatible_input_type``
# keyword arguments so two identical searches across consecutive turns can be
# detected.  Operates on raw statement source text (the parsed StatementResult
# detail only carries the rendered query_output, not the raw args), so this is
# the most conservative provably-correct mechanism.
_SEARCH_CALL_RE = _re.compile(r"\bsearch\s*\(", _re.IGNORECASE)
_SEARCH_KW_RE = _re.compile(
    r"\b(focus_types|compatible_output_type|compatible_input_type)\s*=\s*"
    r"(\[[^\]]*\]|\"[^\"]*\"|'[^']*')",
)


def _extract_search_signatures(batch_result: Any) -> tuple[str, ...]:
    """Return a normalized signature per ``search(...)`` call in this turn.

    Each signature is ``focus_types=<sorted list literal>|compatible_output_type=<v>
    |compatible_input_type=<v>`` for the keyword args that actually appear; a
    search with no recognized kwargs yields ``"search()"``.  Returns an empty
    tuple when the turn issued no search calls (so research()/python()/edits
    are ignored).
    """
    statements = getattr(batch_result, "statements", None) or ()
    signatures: list[str] = []
    for statement in statements:
        source = getattr(statement, "source", "") or ""
        if not isinstance(source, str) or not _SEARCH_CALL_RE.search(source):
            continue
        kwargs: list[str] = []
        for key, raw in _SEARCH_KW_RE.findall(source):
            if key == "focus_types":
                # Normalize the list literal so order/spacing differences don't
                # defeat the cycle check (e.g. ["A","B"] vs ["B", "A"]).
                inner = raw.strip("[]")
                parts = sorted(
                    p.strip().strip("\"' ")
                    for p in inner.split(",")
                    if p.strip().strip("\"' ")
                )
                kwargs.append(f"focus_types=[{','.join(parts)}]")
            else:
                _stripped = raw.strip("\"' ")
                kwargs.append(f"{key}={_stripped}")
        signatures.append("|".join(kwargs) if kwargs else "search()")
    return tuple(signatures)


def _duplicate_search_cycle_feedback(
    current_signatures: tuple[str, ...],
    prior_signatures: tuple[str, ...] | None,
    prior_search_landed: bool,
) -> str:
    """Deterministic feedback when the agent repeats an identical empty search.

    Fires only when: (a) there IS a prior turn's search record, (b) the prior
    turn's searches landed NOTHING, and (c) the current turn repeats at least
    one of those identical search signatures.  Never fires on a first search
    or on a search that previously succeeded.  Returns "" otherwise.
    """
    if not current_signatures:
        return ""
    if not prior_signatures:
        return ""
    if prior_search_landed:
        return ""
    repeated = [sig for sig in current_signatures if sig in prior_signatures]
    if not repeated:
        return ""
    # Describe the repeated search type for the feedback string.
    sample = repeated[0]
    _quote_strip = "\"' "
    if sample.startswith("focus_types="):
        type_desc = sample.split("=", 1)[1]
    elif sample.startswith("compatible_output_type=") or sample.startswith("compatible_input_type="):
        type_desc = sample.split("=", 1)[1].strip(_quote_strip)
    else:
        type_desc = "a node type"
    return (
        f"You already searched for {type_desc} and it produced no landed edit. "
        "Do not repeat the identical search — either rewire to an existing "
        "compatible node, search an adjacent type, or use a local "
        "vibecomfy.exec shim."
    )



def _format_diagnostic_detail_text(detail: dict[str, Any]) -> str:
    """Format engine diagnostic detail keys as stable, capped text."""
    if not isinstance(detail, dict):
        return ""
    parts: list[str] = []
    for key in _DIAGNOSTIC_DETAIL_KEYS:
        value = detail.get(key)
        if value is None:
            continue
        if key in ("choices", "valid_fields", "available_slots"):
            if isinstance(value, (list, tuple)):
                items = [str(v) for v in value if v is not None]
                if not items:
                    continue
                shown = items[:_DETAIL_LIST_CAP]
                label = f"{key}: [{', '.join(repr(v) for v in shown)}"
                if len(items) > _DETAIL_LIST_CAP:
                    label += f", ... (+{len(items) - _DETAIL_LIST_CAP} more)"
                label += "]"
                parts.append(label)
        elif key == "semantic_aliases":
            if isinstance(value, dict):
                items = [(str(k), str(v)) for k, v in value.items() if k and v and k != v]
                if not items:
                    continue
                items.sort()
                shown = items[:_DETAIL_ALIAS_CAP]
                label = f"semantic_aliases: {{{', '.join(f'{k!r}->{v!r}' for k, v in shown)}"
                if len(items) > _DETAIL_ALIAS_CAP:
                    label += f", ... (+{len(items) - _DETAIL_ALIAS_CAP} more)"
                label += "}"
                parts.append(label)
        elif key in ("min", "max"):
            parts.append(f"{key}: {value!r}")
    return "; ".join(parts) if parts else ""


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
        status = getattr(statement, "status", None)
        reason = getattr(statement, "reason", None)
        op_kind = statement.op_kind or "statement"
        # Query/control statements are intentionally non-editing.  Keep the
        # stable teaching wording used by the batch protocol even though the
        # typed interpreter records them internally as ``skipped``.
        if status and op_kind not in {"query", "done"}:
            status = f"{status}" + (f" ({reason})" if reason else "")
        else:
            status = "landed" if statement.landed else "not landed"
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
            detail_text = _format_diagnostic_detail_text(getattr(primary, "detail", {}))
            if detail_text:
                extras.append(detail_text)
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

    diagnostic_lines = []
    for diagnostic in batch_result.diagnostics:
        line = f"! {diagnostic.code}: {diagnostic.message}"
        diagnostic_lines.append(line)
        detail_text = _format_diagnostic_detail_text(getattr(diagnostic, "detail", {}))
        if detail_text:
            diagnostic_lines.append(f"  detail: {detail_text}")
    # Append lint diagnostics so the model sees them inline.
    if lint_diagnostics:
        for d in lint_diagnostics:
            diagnostic_lines.append(f"! [lint] {d['code']}: {d['message']}")
            lint_detail = d.get("detail") if isinstance(d, dict) else None
            lint_detail_text = _format_diagnostic_detail_text(lint_detail) if isinstance(lint_detail, dict) else ""
            if lint_detail_text:
                diagnostic_lines.append(f"  detail: {lint_detail_text}")
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
            "branded variant that did not appear in the workflow evidence. Treat weak "
            "external mentions as evidence only; they do not make a node authorable. "
            "If an exact local schema lookup missed, stop using local lookup as research "
            "and either adapt with available authorable classes or clarify with the "
            "specific missing authoring surface."
        )
    lines = [summary, *statement_lines, query_only_note, *diagnostic_lines]
    return "\n".join(line for line in lines if line)


def _cap_diagnostic_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """Cap list/dict values in a diagnostic detail for stable, bounded JSON."""
    if not isinstance(detail, dict):
        return {}
    capped: dict[str, Any] = {}
    for key in _DIAGNOSTIC_DETAIL_KEYS:
        value = detail.get(key)
        if value is None:
            continue
        if key in ("choices", "valid_fields", "available_slots"):
            if isinstance(value, (list, tuple)):
                capped[key] = [v for v in value[:_DETAIL_LIST_CAP] if v is not None]
            else:
                capped[key] = value
        elif key == "semantic_aliases":
            if isinstance(value, dict):
                items = [(str(k), str(v)) for k, v in value.items() if k and v and k != v]
                items.sort()
                capped[key] = dict(items[:_DETAIL_ALIAS_CAP])
            else:
                capped[key] = value
        else:
            capped[key] = value
    return capped


def _statement_op_payload(item: Any) -> dict[str, Any] | None:
    """Serialize the landed typed op for the accepted-batch Δ."""
    raw = getattr(item, "op", None)
    if raw is None and isinstance(getattr(item, "detail", None), Mapping):
        raw = item.detail.get("edit_op")
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        from vibecomfy.porting.edit.ops import op_to_dict

        return op_to_dict(raw)
    except Exception:
        return None


def _statement_report_entry(item: Any) -> dict[str, Any]:
    entry = {
        "statement_index": item.statement_index,
        "source": item.source,
        "ok": item.ok,
        "landed": item.landed,
        "status": getattr(item, "status", None),
        "reason": getattr(item, "reason", None),
        "op_kind": item.op_kind,
        "detail": _json_safe(dict(item.detail)),
        "touched_uids": list(item.touched_uids),
        "dependency_cause": item.dependency_cause,
        "teaching_hint": item.teaching_hint,
        "diagnostics": [
            _compact_diag_with_capped_detail(diag) for diag in item.diagnostics
        ],
    }
    op = _statement_op_payload(item)
    if op is not None:
        entry["op"] = op
    return entry


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
            _statement_report_entry(item) for item in batch_result.statements
        ],
        "diagnostics": [
            _compact_diag_with_capped_detail(item) for item in batch_result.diagnostics
        ],
    }
    if lint_dropped_count:
        result["summary"]["lint_dropped"] = lint_dropped_count
    if lint_diagnostics:
        result["lint_diagnostics"] = [
            _lint_diag_with_capped_detail(d) for d in lint_diagnostics
        ]
    return result


def _compact_diag_with_capped_detail(diagnostic: Any) -> dict[str, Any]:
    d = _compact_diag_to_dict(diagnostic)
    raw_detail = d.get("detail")
    if isinstance(raw_detail, dict):
        d["detail"] = _cap_diagnostic_detail(raw_detail)
    return d


def _lint_diag_with_capped_detail(d: dict[str, Any]) -> dict[str, Any]:
    result = dict(d)
    raw_detail = result.get("detail")
    if isinstance(raw_detail, dict):
        result["detail"] = _cap_diagnostic_detail(raw_detail)
    return result


_CLARIFY_CALL_RE = re.compile(
    r'(?m)^\s*clarify\("((?:[^"\\]|\\.)*)"\)\s*$'
)

_BATCH_EXIT_PURE_CLARIFY = "pure_clarify"
_BATCH_EXIT_EDIT_CLARIFY = "edit_clarify"
_BATCH_EXIT_DONE = "done"
_BATCH_EXIT_BUDGET = "budget"
_BATCH_EXIT_NOOP = "noop"
# PR-D: rejected clarification while an edit remained incomplete — a terminal
# stop that is NOT budget exhaustion (distinct from _BATCH_EXIT_BUDGET).
_BATCH_EXIT_STUCK = "stuck"


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


def _is_done_expr(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    call = node.value
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == "done"
        and not call.args
        and not call.keywords
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
    trailing = batch[terminal_match.end() :]
    trailing_lines = trailing.splitlines()
    allowed_done_seen = False
    for line in trailing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not allowed_done_seen and stripped == "done()":
            allowed_done_seen = True
            continue
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

    body = list(module.body)
    trailing_done: ast.stmt | None = None
    if body and _is_done_expr(body[-1]):
        trailing_done = body.pop()
    if not body:
        return TerminalClarifySplit(batch=batch, message=None)

    terminal = body[-1]
    if not _is_terminal_clarify_expr(terminal):
        return TerminalClarifySplit(batch=batch, message=None)
    if any(_contains_clarify_call(stmt) for stmt in body[:-1]):
        return TerminalClarifySplit(batch=batch, message=None)

    call = terminal.value
    assert isinstance(call, ast.Call)
    message_node = call.args[0]
    assert isinstance(message_node, ast.Constant)
    start = _offset_from_ast_position(batch, terminal.lineno, terminal.col_offset)
    editable_batch = batch[:start].rstrip()
    if editable_batch.endswith(";"):
        editable_batch = editable_batch[:-1].rstrip()
    if trailing_done is not None:
        trailing_start = _offset_from_ast_position(batch, trailing_done.lineno, trailing_done.col_offset)
        if terminal.end_lineno is None or terminal.end_col_offset is None:
            terminal_end = start
        else:
            terminal_end = _offset_from_ast_position(batch, terminal.end_lineno, terminal.end_col_offset)
        between = batch[terminal_end:trailing_start]
        if any(line.strip() and not line.lstrip().startswith("#") for line in between.splitlines()):
            return TerminalClarifySplit(batch=batch, message=None)
    return TerminalClarifySplit(batch=editable_batch, message=message_node.value)


def _batch_has_landed_edits(state: "AgentEditState") -> bool:
    return any(
        isinstance(turn, Mapping) and int(turn.get("landed_op_count", 0)) > 0
        for turn in state.batch_turns
    )


_BATCH_UNREPRESENTABLE_DIAGNOSTIC_CODES = {
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


def _batch_turn_diagnostics(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, Mapping):
            continue
        for diagnostic in turn.get("diagnostics") or []:
            if isinstance(diagnostic, Mapping):
                diagnostics.append(dict(diagnostic))
        for statement in turn.get("statements") or []:
            if not isinstance(statement, Mapping):
                continue
            for diagnostic in statement.get("diagnostics") or []:
                if isinstance(diagnostic, Mapping):
                    diagnostics.append(dict(diagnostic))
    return diagnostics

_BATCH_FAILURE_EVIDENCE_MAX_TURNS = 64
_BATCH_FAILURE_EVIDENCE_MAX_OPS = 512


def _batch_failure_ops_submitted(turns: list[Any]) -> list[dict[str, Any]]:
    """Collect the typed ops submitted across the recorded batch turns.

    §28 deep-audit fix 6: when a turn dies mid-flight, the ops the agent
    actually submitted must survive to disk next to the transcript, not just
    the landed subset.
    """
    ops: list[dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, Mapping):
            continue
        statements = turn.get("statements") or ()
        if isinstance(statements, Mapping) or not isinstance(statements, (list, tuple)):
            continue
        for statement in statements:
            if len(ops) >= _BATCH_FAILURE_EVIDENCE_MAX_OPS:
                return ops
            op = _record_statement_op(statement)
            if op is None:
                continue
            entry = dict(op)
            source = (
                statement.get("source")
                if isinstance(statement, Mapping)
                else getattr(statement, "source", None)
            )
            if isinstance(source, str) and source.strip():
                entry["source"] = _json_safe(source)[:2000]
            ops.append(entry)
    return ops


def _record_statement_op(statement: Any) -> dict[str, Any] | None:
    """Read the typed op from a serialized (Mapping) or live statement record."""
    if isinstance(statement, Mapping):
        raw = statement.get("op")
        if raw is None and isinstance(statement.get("detail"), Mapping):
            raw = statement["detail"].get("edit_op")
    else:
        return _statement_op_payload(statement)
    if isinstance(raw, Mapping):
        return dict(raw)
    return None


def _thaw_evidence_value(value: Any) -> Any:
    """Recursively thaw frozen envelope structures (mappingproxy/tuple)."""
    if isinstance(value, Mapping):
        return {str(key): _thaw_evidence_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_evidence_value(item) for item in value]
    return value


def build_batch_failure_evidence(
    state: Any,
    *,
    stage: str,
    failure_kind: str | None = None,
    agent_failure_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the durable mid-turn failure evidence payload (§28 fix 6).

    Carries everything an assessor needs to reconstruct a failed leg: the
    batch transcript (turn records seen so far), every submitted op, and the
    full structured failure context from the envelope. Bounded and JSON-safe;
    never mutates *state* and never raises on malformed records.
    """
    raw_turns = list(getattr(state, "batch_turns", ()) or ())
    turns = [
        dict(_thaw_evidence_value(turn))
        for turn in raw_turns[:_BATCH_FAILURE_EVIDENCE_MAX_TURNS]
        if isinstance(turn, Mapping)
    ]
    payload: dict[str, Any] = {
        "contract_version": 1,
        "code": "agent_batch_failure_evidence",
        "stage": stage,
        "transcript": _json_safe(turns),
        "ops_submitted": _json_safe(_batch_failure_ops_submitted(turns)),
    }
    if failure_kind:
        payload["failure_kind"] = str(failure_kind)
    if agent_failure_context:
        # Frozen envelopes arrive as mappingproxy trees — thaw BEFORE
        # json-safe serialization or structured issues degrade to strings.
        payload["failure_context"] = _json_safe(_thaw_evidence_value(agent_failure_context))
    if len(raw_turns) > len(turns):
        payload["transcript_truncated_from"] = len(raw_turns)
    return payload


def _batch_budget_artifixer_report(
    state: "AgentEditState",
    failure_kind: FailureKind,
) -> dict[str, Any]:
    """Classify a terminal batch stop for a future repair pass without mutating it."""
    diagnostics = _batch_turn_diagnostics(state.batch_turns)
    diagnostic_codes = sorted(
        {
            str(diagnostic.get("code"))
            for diagnostic in diagnostics
            if diagnostic.get("code") is not None
        }
    )
    hard_codes = sorted(
        set(diagnostic_codes).intersection(_BATCH_UNREPRESENTABLE_DIAGNOSTIC_CODES)
    )
    try:
        candidate_graph_changed = bool(_batch_candidate_graph_changed(state))
    except Exception:
        candidate_graph_changed = False
    landed_edits = _batch_has_landed_edits(state)
    hard_refusal = bool(hard_codes) or failure_kind is FailureKind.UNREPRESENTABLE
    if hard_refusal:
        outcome = "hard_refusal"
        reason = "unrepresentable_edit_surface"
    elif not candidate_graph_changed:
        outcome = "not_attempted"
        reason = "no_candidate_graph_change"
    elif not landed_edits:
        outcome = "not_attempted"
        reason = "no_landed_edits"
    else:
        outcome = "candidate_available"
        reason = "diagnostics_only"
    return {
        "stage": "artifixer",
        "version": 1,
        "policy": "diagnostics_only",
        "attempted": False,
        "outcome": outcome,
        "reason": reason,
        "failure_kind": failure_kind.value,
        "hard_refusal": hard_refusal,
        "candidate_graph_changed": candidate_graph_changed,
        "landed_edits": landed_edits,
        "turn_count": state.batch_turn_count,
        "budget_state": dict(state.batch_budget_state),
        "diagnostic_codes": diagnostic_codes,
        "hard_refusal_codes": hard_codes,
    }


def _batch_budget_failure_kind(turns: list[dict[str, Any]]) -> FailureKind:
    schema_gap_markers = (
        "schema",
        "schema-backed",
        "socket type",
        "compatible output",
        "confidence",
    )
    # Typed ApplyOpsError codes that must preserve their failure kind explicitly
    # (do not collapse via haystack). These are fixable model mistakes.
    _TYPED_MODEL_MISTAKE_CODES = {
        "unknown_schema",
        "unknown_port",
        "unknown_field",
        "wrong_channel",
        "unknown_target",
        "unknown_target_field",
        "unknown_target_node",
        "unknown_add_node_class_type",
        "unknown_output",
        "invalid_arguments",
        "malformed_op",
        "unsupported_op",
        "apply_failed",
        "batch_identity_rejected",
        "unbound_graph_name",
        "batch_syntax_error",
        "unsupported_query_call",
        "batch_transaction_rolled_back",
        "batch_consecutive_errors_exhausted",
        "batch_budget_exhausted",
    }
    _TYPED_SCHEMA_GAP_CODES = {
        "missing_touched_schema",
        "schema_less_queue_blocker",
    }
    category_turn_hits = {
        FailureKind.MODEL_MISTAKE: 0,
        FailureKind.UNREPRESENTABLE: 0,
        FailureKind.SCHEMA_GAP: 0,
    }
    for turn in turns:
        turn_categories: set[FailureKind] = set()
        diagnostics = _batch_turn_diagnostics([turn])
        for diagnostic in diagnostics:
            code = str(diagnostic.get("code", "")).lower()
            message = str(diagnostic.get("message", "")).lower()
            teaching_hint = str(diagnostic.get("teaching_hint", "")).lower()
            haystack = " ".join((code, message, teaching_hint))
            # Preserve typed kinds before haystack; prevents unknown_schema
            # containing "schema" from being misclassified as SCHEMA_GAP.
            if code in _BATCH_UNREPRESENTABLE_DIAGNOSTIC_CODES:
                turn_categories.add(FailureKind.UNREPRESENTABLE)
                continue
            if code in _TYPED_SCHEMA_GAP_CODES:
                turn_categories.add(FailureKind.SCHEMA_GAP)
                continue
            if code in _TYPED_MODEL_MISTAKE_CODES:
                turn_categories.add(FailureKind.MODEL_MISTAKE)
                continue
            if any(marker in haystack for marker in schema_gap_markers):
                turn_categories.add(FailureKind.SCHEMA_GAP)
                continue
            if "not allowed" in haystack or "immutable" in haystack:
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


__all__ = (
     "TerminalClarifySplit", "_BATCH_EXIT_BUDGET", "_BATCH_EXIT_DONE",
     "_BATCH_EXIT_EDIT_CLARIFY", "_BATCH_EXIT_NOOP", "_BATCH_EXIT_PURE_CLARIFY",
     "_BATCH_EXIT_STUCK",
     "_BATCH_UNREPRESENTABLE_DIAGNOSTIC_CODES", "_CLARIFY_CALL_RE", "_DETAIL_ALIAS_CAP",
     "_DETAIL_LIST_CAP", "_DIAGNOSTIC_DETAIL_KEYS", "_SEARCH_CALL_RE", "_SEARCH_KW_RE",
     "_batch_budget_artifixer_report", "_batch_budget_failure_kind",
     "_batch_failure_ops_submitted", "_batch_has_landed_edits",
     "_batch_turn_diagnostics", "_cap_diagnostic_detail",
     "build_batch_failure_evidence",
     "_compact_diag_with_capped_detail", "_contains_clarify_call",
     "_decode_clarify_literal", "_duplicate_search_cycle_feedback",
     "_extract_clarify_message", "_extract_search_signatures", "_format_batch_report",
     "_format_batch_report_json", "_format_diagnostic_detail_text", "_is_done_expr",
     "_is_terminal_clarify_expr", "_lint_diag_with_capped_detail",
     "_offset_from_ast_position", "_re", "_split_terminal_clarify_line_regex",
     "split_terminal_clarify",
)
