"""Clarify parsing primitives, terminal-clarify support, and response formatting."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any

CLARIFY_CALL_RE = re.compile(r'(?m)^\s*clarify\("((?:[^"\\]|\\.)*)"\)\s*$')


@dataclass(frozen=True)
class TerminalClarifySplit:
    batch: str
    message: str | None


def extract_clarify_message(batch: str) -> str | None:
    matches = CLARIFY_CALL_RE.findall(batch)
    if not matches:
        return None
    try:
        return json.loads(f'"{matches[0]}"')
    except json.JSONDecodeError:
        return matches[0]


def is_terminal_clarify_expr(node: ast.stmt) -> bool:
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


def is_done_expr(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    call = node.value
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == "done"
        and not call.args
        and not call.keywords
    )


def contains_clarify_call(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "clarify"
        for child in ast.walk(node)
    )


def offset_from_ast_position(batch: str, lineno: int, col_offset: int) -> int:
    lines = batch.splitlines(keepends=True)
    if lineno <= 0:
        return 0
    before = sum(len(line) for line in lines[: lineno - 1])
    line = lines[lineno - 1] if lineno - 1 < len(lines) else ""
    char_col = len(line.encode("utf-8")[:col_offset].decode("utf-8", errors="ignore"))
    return before + char_col


def decode_clarify_literal(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw


def split_terminal_clarify_line_regex(batch: str) -> TerminalClarifySplit:
    matches = list(CLARIFY_CALL_RE.finditer(batch))
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
        message=decode_clarify_literal(terminal_match.group(1)),
    )


def split_terminal_clarify(batch: str) -> TerminalClarifySplit:
    try:
        module = ast.parse(batch)
    except SyntaxError:
        return split_terminal_clarify_line_regex(batch)
    if not module.body:
        return TerminalClarifySplit(batch=batch, message=None)

    body = list(module.body)
    trailing_done: ast.stmt | None = None
    if body and is_done_expr(body[-1]):
        trailing_done = body.pop()
    if not body:
        return TerminalClarifySplit(batch=batch, message=None)

    terminal = body[-1]
    if not is_terminal_clarify_expr(terminal):
        return TerminalClarifySplit(batch=batch, message=None)
    if any(contains_clarify_call(stmt) for stmt in body[:-1]):
        return TerminalClarifySplit(batch=batch, message=None)

    call = terminal.value
    assert isinstance(call, ast.Call)
    message_node = call.args[0]
    assert isinstance(message_node, ast.Constant)
    start = offset_from_ast_position(batch, terminal.lineno, terminal.col_offset)
    editable_batch = batch[:start].rstrip()
    if editable_batch.endswith(";"):
        editable_batch = editable_batch[:-1].rstrip()
    if trailing_done is not None:
        trailing_start = offset_from_ast_position(batch, trailing_done.lineno, trailing_done.col_offset)
        if terminal.end_lineno is None or terminal.end_col_offset is None:
            terminal_end = start
        else:
            terminal_end = offset_from_ast_position(batch, terminal.end_lineno, terminal.end_col_offset)
        between = batch[terminal_end:trailing_start]
        if any(line.strip() and not line.lstrip().startswith("#") for line in between.splitlines()):
            return TerminalClarifySplit(batch=batch, message=None)
    return TerminalClarifySplit(batch=editable_batch, message=message_node.value)


CLARIFY_FORBIDDEN_RESPONSE_KEYS = {
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


def format_clarify_markdown_message(message: Any) -> str:
    text = message.strip() if isinstance(message, str) else ""
    if not text:
        text = "What detail should I use before continuing?"
    return text


def strip_clarify_forbidden_response_fields(value: Any) -> Any:
    if isinstance(value, dict):
        stripped: dict[str, Any] = {}
        for key, item in value.items():
            if key in CLARIFY_FORBIDDEN_RESPONSE_KEYS or key.startswith("candidate_"):
                continue
            stripped[key] = strip_clarify_forbidden_response_fields(item)
        return stripped
    if isinstance(value, list):
        return [strip_clarify_forbidden_response_fields(item) for item in value]
    return value


def _compute_premature_clarify_feedback(
    state: Any,
    clarify_message: str,
) -> str | None:
    """Compute premature clarify feedback for a batch turn.

    Returns a feedback string if the clarify message is premature for the
    current state, or ``None`` if the clarify is valid.
    """
    from .messages import (
        _premature_missing_custom_node_clarify_feedback,
        _premature_workflow_schema_clarify_feedback,
    )

    return _premature_workflow_schema_clarify_feedback(
        state, clarify_message
    ) or _premature_missing_custom_node_clarify_feedback(state, clarify_message)


def _build_premature_clarify_turn_record(
    turn_number: int,
    turn_result: Any,
    clarify_feedback: str,
) -> dict[str, Any]:
    """Build a turn record dict for a prematurely-clarified batch turn."""
    from .artifacts import _json_safe

    return {
        "turn_number": turn_number,
        "batch": getattr(turn_result, "batch", ""),
        "message": getattr(turn_result, "message", ""),
        "route": getattr(turn_result, "route", None),
        "model": getattr(turn_result, "model", None),
        "provider_metadata": _json_safe(
            dict(getattr(turn_result, "audit_metadata", None) or {})
        ),
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


def sanitize_pure_clarify_response(response: dict[str, Any]) -> dict[str, Any]:
    outcome = response.get("outcome")
    if not isinstance(outcome, Mapping) or outcome.get("kind") != "clarify":
        return response
    message = response.get("message") or outcome.get("question")
    markdown = format_clarify_markdown_message(message)
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
    return strip_clarify_forbidden_response_fields(response)


__all__ = [
    "CLARIFY_CALL_RE",
    "CLARIFY_FORBIDDEN_RESPONSE_KEYS",
    "TerminalClarifySplit",
    "contains_clarify_call",
    "decode_clarify_literal",
    "extract_clarify_message",
    "format_clarify_markdown_message",
    "is_done_expr",
    "is_terminal_clarify_expr",
    "offset_from_ast_position",
    "sanitize_pure_clarify_response",
    "split_terminal_clarify",
    "split_terminal_clarify_line_regex",
    "strip_clarify_forbidden_response_fields",
]
