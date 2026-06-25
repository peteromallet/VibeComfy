from __future__ import annotations

import ast
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    StatementResult,
    _ConstantFoldError,
    _ExpandedStatement,
    _ParsedBatch,
    _diag,
)

_FORBIDDEN_CALL_NAMES = frozenset(
    {
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
        "open",
    }
)
_ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES = frozenset({"vibecomfy.exec"})
_RAW_COORDINATE_HINT_NAMES = frozenset({"pos", "position", "coords", "x", "y"})
_SAFE_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
_SAFE_UNARYOPS = (ast.UAdd, ast.USub)


def _resolve_vibecomfy_constructor(func: ast.expr) -> tuple[str | None, bool]:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "vibecomfy":
        return f"vibecomfy.{func.attr}", True
    if isinstance(func, ast.Name):
        return func.id, False
    return None, False


def _parse_and_validate_batch(
    code: str,
    *,
    max_batch_bytes: int,
    max_statements: int,
    max_expanded_statements: int,
    max_for_iterations: int,
) -> _ParsedBatch:
    byte_count = len(code.encode("utf-8"))
    if byte_count > max_batch_bytes:
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=(
                _diag(
                    "batch_byte_cap_exceeded",
                    "Edit batch exceeds the configured byte cap.",
                    severity="error",
                    detail={"bytes": byte_count, "max_bytes": max_batch_bytes},
                ),
            ),
        )
    try:
        module = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=(
                _diag(
                    "batch_syntax_error",
                    exc.msg,
                    severity="error",
                    detail={"line": exc.lineno, "offset": exc.offset},
                ),
            ),
        )

    if len(module.body) > max_statements:
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=(
                _diag(
                    "batch_statement_cap_exceeded",
                    "Edit batch exceeds the configured top-level statement cap.",
                    severity="error",
                    detail={"statements": len(module.body), "max_statements": max_statements},
                ),
            ),
        )

    statements: list[StatementResult] = []
    expanded_statements: list[_ExpandedStatement] = []
    diagnostics: list[CompactDiagnostic] = []
    expanded_count = 0
    for statement in module.body:
        expanded, issues = _expand_statement(
            statement,
            code,
            env=MappingProxyType({}),
            max_for_iterations=max_for_iterations,
        )
        diagnostics.extend(issues)
        if diagnostics:
            continue
        expanded_count += len(expanded)
        if expanded_count > max_expanded_statements:
            diagnostics.append(
                _diag(
                    "batch_expanded_statement_cap_exceeded",
                    "Edit batch exceeds the configured expanded statement cap.",
                    severity="error",
                    detail={
                        "expanded_statements": expanded_count,
                        "max_expanded_statements": max_expanded_statements,
                    },
                )
            )
            break
        statements.extend(expanded)
        expanded_statements.extend(
            _ExpandedStatement(
                statement_index=item.statement_index,
                source=item.source,
                op_kind=item.op_kind or "statement",
                node=item.detail["ast_node"],
                env=MappingProxyType(dict(item.detail.get("constant_env", {}))),
            )
            for item in expanded
        )

    if diagnostics:
        return _ParsedBatch(statements=tuple(statements), expanded=tuple(expanded_statements), diagnostics=tuple(diagnostics))
    return _ParsedBatch(statements=tuple(statements), expanded=tuple(expanded_statements), diagnostics=())


def _expand_statement(
    statement: ast.stmt,
    source: str,
    *,
    env: Mapping[str, Any],
    max_for_iterations: int,
) -> tuple[list[StatementResult], list[CompactDiagnostic]]:
    if isinstance(statement, ast.For):
        return _expand_for(statement, source, env=env, max_for_iterations=max_for_iterations)
    issues = _validate_planned_statement(statement, env=env)
    if issues:
        return [], issues
    segment = ast.get_source_segment(source, statement) or ""
    return [
        StatementResult(
            statement_index=getattr(statement, "lineno", 0),
            source=segment.strip(),
            ok=True,
            landed=False,
            op_kind=_statement_op_kind(statement),
            detail={
                "ast_node": statement,
                "constant_env": dict(env),
            },
        )
    ], []


def _expand_for(
    statement: ast.For,
    source: str,
    *,
    env: Mapping[str, Any],
    max_for_iterations: int,
) -> tuple[list[StatementResult], list[CompactDiagnostic]]:
    if not isinstance(statement.target, ast.Name):
        return [], [_unsafe(statement, "for_target_not_name", "Only simple for-loop targets are allowed.")]
    if statement.orelse:
        return [], [_unsafe(statement, "for_else_not_allowed", "for/else is not allowed.")]
    values, diagnostic = _constant_range_values(statement.iter, max_for_iterations=max_for_iterations)
    if diagnostic is not None:
        return [], [diagnostic]
    expanded: list[StatementResult] = []
    issues: list[CompactDiagnostic] = []
    for value in values:
        child_env = dict(env)
        child_env[statement.target.id] = value
        for child in statement.body:
            child_expanded, child_issues = _expand_statement(
                child,
                source,
                env=MappingProxyType(child_env),
                max_for_iterations=max_for_iterations,
            )
            issues.extend(child_issues)
            expanded.extend(child_expanded)
    return expanded, issues


def _constant_range_values(
    node: ast.expr,
    *,
    max_for_iterations: int,
) -> tuple[tuple[int, ...], CompactDiagnostic | None]:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "range":
        return (), _unsafe(node, "for_iter_not_range", "Only for-loops over range(...) are allowed.")
    if node.keywords or not 1 <= len(node.args) <= 3:
        return (), _unsafe(node, "range_shape_not_allowed", "range(...) must use one to three positional constants.")
    folded: list[Any] = []
    for arg in node.args:
        value, diagnostic = _fold_constant(arg, env=MappingProxyType({}))
        if diagnostic is not None:
            return (), diagnostic
        folded.append(value)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in folded):
        return (), _unsafe(node, "range_non_integer", "range(...) bounds must be integers.")
    try:
        values = tuple(range(*folded))
    except ValueError as exc:
        return (), _unsafe(node, "range_invalid", str(exc))
    if len(values) > max_for_iterations:
        return (), _unsafe(
            node,
            "for_iteration_cap_exceeded",
            "for-loop exceeds the configured iteration cap.",
            detail={"iterations": len(values), "max_iterations": max_for_iterations},
        )
    return values, None


def _validate_planned_statement(
    statement: ast.stmt,
    *,
    env: Mapping[str, Any],
) -> list[CompactDiagnostic]:
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        return [_unsafe(statement, "import_not_allowed", "Imports are not allowed in edit batches.")]
    if isinstance(statement, ast.Assign):
        if len(statement.targets) != 1:
            return [_unsafe(statement, "assignment_target_not_allowed", "Only single-target assignments are allowed.")]
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            return _validate_call(statement.value, env=env, top_level=True)
        if isinstance(target, ast.Attribute):
            return _validate_edit_assignment(target, statement.value, env=env)
        return [_unsafe(statement, "assignment_target_not_allowed", "Only name or one-hop attribute assignments are allowed.")]
    if isinstance(statement, ast.Delete):
        if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            return [_unsafe(statement, "delete_target_not_allowed", "Only bare graph names may be deleted.")]
        if statement.targets[0].id.startswith("__"):
            return [_unsafe(statement.targets[0], "dunder_name_not_allowed", "Dunder graph names are not allowed.")]
        return []
    if isinstance(statement, ast.Expr):
        return _validate_call(statement.value, env=env, top_level=True)
    return [_unsafe(statement, "statement_not_allowed", f"{type(statement).__name__} statements are not allowed.")]


def _validate_call(
    node: ast.expr,
    *,
    env: Mapping[str, Any],
    top_level: bool,
) -> list[CompactDiagnostic]:
    if not isinstance(node, ast.Call):
        return [_unsafe(node, "expression_not_call", "Only planned top-level calls are allowed.")]
    name, dotted_vibecomfy = _resolve_vibecomfy_constructor(node.func)
    if dotted_vibecomfy and name not in _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES:
        return [
            _unsafe(
                node.func,
                "intent_class_construction_not_allowed",
                "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface. Use vibecomfy.exec for executable Python code nodes.",
            )
        ]
    if name is None:
        return [_unsafe(node, "call_target_not_name", "Calls must target a simple function name.")]
    if name in _FORBIDDEN_CALL_NAMES or name.startswith("__"):
        return [_unsafe(node, "call_not_allowed", f"Call to {name!r} is not allowed.")]
    if name == "range":
        return [_unsafe(node, "range_only_in_for", "range(...) is only allowed as a for-loop iterator.")]
    if name == "done":
        if node.args or node.keywords:
            return [_unsafe(node, "done_arguments_not_allowed", "done() does not accept arguments.")]
        return []
    if name == "clarify":
        return [
            _unsafe(
                node,
                "unsupported_query_call",
                "Only search(...), research(...), python(), and done() are supported as top-level query calls.",
            )
        ]
    if name in {"python", "research", "search"}:
        if not top_level:
            return [_unsafe(node, "nested_call_not_allowed", "Nested calls are not allowed.")]
        return []
    if not top_level:
        return [_unsafe(node, "nested_call_not_allowed", "Nested calls are not allowed.")]
    if node.args:
        return [_unsafe(node, "positional_args_not_allowed", "Node calls must use keyword arguments.")]
    issues: list[CompactDiagnostic] = []
    for keyword in node.keywords:
        if keyword.arg is None:
            issues.append(_unsafe(keyword.value, "kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed."))
            continue
        if keyword.arg.startswith("__"):
            issues.append(
                _unsafe(keyword.value, "dunder_keyword_not_allowed", "Dunder keyword names are not allowed.")
            )
            continue
        if keyword.arg == "near":
            if isinstance(keyword.value, ast.Name):
                if keyword.value.id.startswith("__"):
                    issues.append(_unsafe(keyword.value, "dunder_name_not_allowed", "Dunder source graph names are not allowed."))
                continue
            issues.append(_unsafe(keyword.value, "invalid_near_hint", "near= must reference a rendered graph name."))
            continue
        if keyword.arg == "relation" or keyword.arg == "group" or keyword.arg in _RAW_COORDINATE_HINT_NAMES:
            value, diagnostic = _fold_constant(keyword.value, env=env)
            _ = value
            if diagnostic is not None:
                issues.append(diagnostic)
            continue
        issues.extend(_validate_node_call_value(keyword.value, env=env))
    return issues


def _validate_node_call_value(node: ast.expr, *, env: Mapping[str, Any]) -> list[CompactDiagnostic]:
    if _is_handle_ref(node):
        return []
    value, diagnostic = _fold_constant(node, env=env)
    if diagnostic is None:
        return []
    return [diagnostic]


def _is_handle_ref(node: ast.expr) -> bool:
    if not isinstance(node, ast.Attribute) or node.attr.startswith("__"):
        return False
    base = node.value
    return isinstance(base, ast.Name) and not base.id.startswith("__")


def _validate_edit_assignment(
    target: ast.Attribute,
    value: ast.expr,
    *,
    env: Mapping[str, Any],
) -> list[CompactDiagnostic]:
    issues = _validate_graph_attribute(target, role="target")
    if issues:
        return issues
    if target.attr == "mode":
        literal_value, diagnostic = _fold_constant(value, env=env)
        _ = literal_value
        if diagnostic is None:
            return []
        return [diagnostic]
    if isinstance(value, ast.Constant) and value.value is None:
        return []
    if isinstance(value, ast.Name) and value.id.startswith("__"):
        return [_unsafe(value, "dunder_name_not_allowed", "Dunder source graph names are not allowed.")]
    if isinstance(value, ast.Attribute):
        attr_issues = _validate_graph_attribute(value, role="source")
        if not attr_issues:
            return []
        return attr_issues
    if _is_graph_reference_value(value):
        return _validate_graph_reference_value(value)
    literal_value, diagnostic = _fold_constant(value, env=env)
    _ = literal_value
    if diagnostic is None:
        return []
    return [diagnostic]


def _validate_graph_attribute(attr: ast.Attribute, *, role: str) -> list[CompactDiagnostic]:
    if attr.attr.startswith("__"):
        return [_unsafe(attr, "dunder_attribute_not_allowed", f"Dunder {role} attributes are not allowed.")]
    if isinstance(attr.value, ast.Attribute):
        return [_unsafe(attr, "scope_escape_not_allowed", "Nested attribute scope escapes are not allowed.")]
    if not isinstance(attr.value, ast.Name):
        return [_unsafe(attr, "attribute_base_not_name", f"{role.capitalize()} attribute access must start from a graph name.")]
    if attr.value.id.startswith("__"):
        return [_unsafe(attr.value, "dunder_name_not_allowed", f"Dunder {role} graph names are not allowed.")]
    return []


def _is_graph_reference_value(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return not node.id.startswith("__")
    if isinstance(node, ast.Attribute):
        return not node.attr.startswith("__") and isinstance(node.value, ast.Name)
    return False


def _validate_graph_reference_value(node: ast.expr) -> list[CompactDiagnostic]:
    if isinstance(node, ast.Name):
        if node.id.startswith("__"):
            return [_unsafe(node, "dunder_name_not_allowed", "Dunder source graph names are not allowed.")]
        return []
    assert isinstance(node, ast.Attribute)
    return _validate_graph_attribute(node, role="source")


def _fold_constant(
    node: ast.expr,
    *,
    env: Mapping[str, Any],
) -> tuple[Any, CompactDiagnostic | None]:
    if isinstance(node, ast.Constant):
        return node.value, None
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id], None
    if isinstance(node, ast.List):
        return _fold_sequence(node, node.elts, list, env=env)
    if isinstance(node, ast.Tuple):
        return _fold_sequence(node, node.elts, tuple, env=env)
    if isinstance(node, ast.Set):
        return _fold_sequence(node, node.elts, set, env=env)
    if isinstance(node, ast.Dict):
        return _fold_dict(node, env=env)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _SAFE_UNARYOPS):
        value, diagnostic = _fold_constant(node.operand, env=env)
        if diagnostic is not None:
            return None, diagnostic
        try:
            if isinstance(node.op, ast.UAdd):
                return +value, None
            return -value, None
        except Exception:
            return None, _unsafe(node, "constant_fold_failed", "Unary constant expression could not be folded.")
    if isinstance(node, ast.BinOp) and isinstance(node.op, _SAFE_BINOPS):
        left, left_diag = _fold_constant(node.left, env=env)
        if left_diag is not None:
            return None, left_diag
        right, right_diag = _fold_constant(node.right, env=env)
        if right_diag is not None:
            return None, right_diag
        try:
            return _apply_binop(node.op, left, right), None
        except _ConstantFoldError as exc:
            return None, _unsafe(
                node,
                "constant_fold_failed",
                str(exc),
                detail=exc.detail,
            )
        except Exception:
            return None, _unsafe(node, "constant_fold_failed", "Binary constant expression could not be folded.")
    if isinstance(node, ast.JoinedStr):
        return None, _unsafe(node, "f_string_not_allowed", "f-string interpolation is not allowed.")
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return None, _unsafe(node, "comprehension_not_allowed", "Comprehensions are not allowed.")
    if isinstance(node, ast.Lambda):
        return None, _unsafe(node, "lambda_not_allowed", "Lambdas are not allowed.")
    if isinstance(node, ast.Call):
        return None, _unsafe(node, "nested_call_not_allowed", "Non-constant calls are not allowed.")
    if isinstance(node, ast.Attribute) and (
        node.attr.startswith("__") or (isinstance(node.value, ast.Name) and node.value.id.startswith("__"))
    ):
        return None, _unsafe(node, "dunder_attribute_not_allowed", "Dunder attributes are not allowed.")
    return None, _unsafe(node, "expression_not_constant", f"{type(node).__name__} is not an allowed constant.")


def _fold_sequence(
    node: ast.expr,
    elements: list[ast.expr],
    factory: Any,
    *,
    env: Mapping[str, Any],
) -> tuple[Any, CompactDiagnostic | None]:
    values: list[Any] = []
    for element in elements:
        value, diagnostic = _fold_constant(element, env=env)
        if diagnostic is not None:
            return None, diagnostic
        values.append(value)
    try:
        return factory(values), None
    except TypeError:
        return None, _unsafe(node, "constant_fold_failed", "Container constant expression could not be folded.")


def _fold_dict(node: ast.Dict, *, env: Mapping[str, Any]) -> tuple[dict[Any, Any] | None, CompactDiagnostic | None]:
    folded: dict[Any, Any] = {}
    for key_node, value_node in zip(node.keys, node.values, strict=True):
        if key_node is None:
            return None, _unsafe(node, "dict_unpack_not_allowed", "Dictionary unpacking is not allowed.")
        key, key_diag = _fold_constant(key_node, env=env)
        if key_diag is not None:
            return None, key_diag
        value, value_diag = _fold_constant(value_node, env=env)
        if value_diag is not None:
            return None, value_diag
        try:
            folded[key] = value
        except TypeError:
            return None, _unsafe(node, "unhashable_dict_key", "Dictionary constant has an unhashable key.")
    return folded, None


def _apply_binop(op: ast.operator, left: Any, right: Any) -> Any:
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        try:
            return left / right
        except ZeroDivisionError:
            raise _ConstantFoldError(
                "Division by zero in constant expression.",
                detail={"left": repr(left), "right": repr(right), "op": "Div"},
            ) from None
    if isinstance(op, ast.FloorDiv):
        try:
            return left // right
        except ZeroDivisionError:
            raise _ConstantFoldError(
                "Floor division by zero in constant expression.",
                detail={"left": repr(left), "right": repr(right), "op": "FloorDiv"},
            ) from None
    if isinstance(op, ast.Mod):
        try:
            return left % right
        except ZeroDivisionError:
            raise _ConstantFoldError(
                "Modulo by zero in constant expression.",
                detail={"left": repr(left), "right": repr(right), "op": "Mod"},
            ) from None
    raise TypeError(type(op).__name__)


def _statement_op_kind(statement: ast.stmt) -> str | None:
    if isinstance(statement, ast.Assign):
        target = statement.targets[0]
        if isinstance(target, ast.Name) and isinstance(statement.value, ast.Call):
            return "node_call"
        if isinstance(target, ast.Attribute):
            return _assignment_op_kind(statement.value, target_attr=target.attr)
        return "assign"
    if isinstance(statement, ast.Delete):
        return "remove_node"
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        if _call_name(statement.value) == "done":
            return "done"
        return "query"
    return None


def _assignment_op_kind(value: ast.expr, *, target_attr: str) -> str:
    if target_attr == "mode":
        return "set_mode"
    if isinstance(value, ast.Constant) and value.value is None:
        return "remove_link"
    if _is_graph_reference_value(value):
        return "upsert_link"
    return "set_node_field"


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _unsafe(
    node: ast.AST,
    code: str,
    message: str,
    *,
    detail: Mapping[str, Any] | None = None,
) -> CompactDiagnostic:
    payload = dict(detail or {})
    lineno = getattr(node, "lineno", None)
    col_offset = getattr(node, "col_offset", None)
    if lineno is not None:
        payload.setdefault("line", lineno)
    if col_offset is not None:
        payload.setdefault("column", col_offset)
    return _diag(code, message, severity="error", detail=payload)
