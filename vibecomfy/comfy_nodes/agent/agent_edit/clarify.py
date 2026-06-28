from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass

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
