from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping

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


# ── clarify response formatting helpers ─────────────────────────────────────

_CLARIFY_FORBIDDEN_RESPONSE_KEYS = {
    "candidate",
    "graph",
    "candidate_graph",
    "apply_eligible",
    "apply_eligibility",
    "eligibility",
    "apply_allowed",
    "canvas_apply_allowed",
    "queue_allowed",
}


def _format_clarify_markdown_message(message: Any) -> str:
    text = message.strip() if isinstance(message, str) else ""
    if not text:
        text = "What detail should I use before continuing?"
    return text


def _strip_clarify_forbidden_response_fields(value: Any) -> Any:
    if isinstance(value, dict):
        stripped: dict[str, Any] = {}
        for key, item in value.items():
            if key in _CLARIFY_FORBIDDEN_RESPONSE_KEYS or key.startswith("candidate_"):
                continue
            stripped[key] = _strip_clarify_forbidden_response_fields(item)
        return stripped
    if isinstance(value, list):
        return [_strip_clarify_forbidden_response_fields(item) for item in value]
    return value


def _sanitize_pure_clarify_response(response: dict[str, Any]) -> dict[str, Any]:
    outcome = response.get("outcome")
    if not isinstance(outcome, Mapping) or outcome.get("kind") != "clarify":
        return response
    message = response.get("message") or outcome.get("question")
    markdown = _format_clarify_markdown_message(message)
    response = dict(response)
    response["message"] = markdown
    response["outcome"] = {
        "kind": "clarify",
        "question": markdown,
        "clarification": {"message": markdown},
    }
    internal_outcome = response.get("internal_outcome")
    if isinstance(internal_outcome, Mapping) and internal_outcome.get("kind") == "clarify":
        response["internal_outcome"] = {"kind": "clarify", "question": markdown}
    response["clarification_required"] = True
    response["clarification_message"] = markdown
    return _strip_clarify_forbidden_response_fields(response)


# ── premature clarify helpers (extracted from _stage_agent_batch_repl) ──────

def _compute_premature_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str:
    """Compute premature clarify feedback from workflow schema or missing custom node checks.

    Returns empty string when no premature-clarify condition is detected.
    """
    # Late imports to avoid circular dependency with messages.py
    from .messages import (
        _premature_missing_custom_node_clarify_feedback,
        _premature_workflow_schema_clarify_feedback,
    )
    return (
        _premature_workflow_schema_clarify_feedback(state, clarify_message)
        or _premature_missing_custom_node_clarify_feedback(state, clarify_message)
    )


def _build_premature_clarify_turn_record(
    *,
    turn_number: int,
    batch: str,
    message: str,
    route: str,
    model: str,
    provider_metadata: dict[str, Any],
    clarify_feedback: str,
) -> dict[str, Any]:
    """Build a batch-turn record for a rejected premature clarify stop."""
    return {
        "turn_number": turn_number,
        "batch": batch,
        "message": message,
        "route": route,
        "model": model,
        "provider_metadata": provider_metadata,
        "batch_ok": False,
        "landed_op_count": 0,
        "raw_landed_op_count": 0,
        "statement_count": 1,
        "diagnostics": [
            {
                "code": "premature_missing_custom_node_clarify",
                "message": clarify_feedback,
                "severity": "error",
            }
        ],
        "report": clarify_feedback,
        "field_changes": [],
    }
