from __future__ import annotations

import ast
import copy
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
from vibecomfy.porting.edit.constants import (
    WIDGET_CHANNEL_SIDE_KEY,
    decode_channel_side_payload,
)
from vibecomfy.porting.edit.grammar import (
    ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES,
    CONTROL_CALL_NAMES,
    FORBIDDEN_ASSIGN_ATTRS,
    FORBIDDEN_CALL_NAMES,
    QUERY_CALL_NAMES,
    diagnose_unadmitted_ast,
    op_kind_for_assignment,
    op_kind_for_statement,
)
from vibecomfy.executor.tool_specs import (
    AGENT_TOOL_CALL_NAMES as _AGENT_TOOL_CALL_NAMES,
)

# Admission sets are generated from grammar.py — do not hand-maintain copies.
_FORBIDDEN_CALL_NAMES = FORBIDDEN_CALL_NAMES
_ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES = ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES
_RAW_COORDINATE_HINT_NAMES = frozenset({"pos", "position", "coords", "x", "y"})
_QUERY_CALL_NAMES = QUERY_CALL_NAMES
_SAFE_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
_SAFE_UNARYOPS = (ast.UAdd, ast.USub)


def _channel_side_unpack(
    keyword: ast.keyword,
    *,
    env: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...], CompactDiagnostic | None] | None:
    """Return ``(widgets, order, issue)`` if *keyword* is the field roster.

    The side channel is ``**{WIDGET_CHANNEL_SIDE_KEY: {widgets, order}}`` —
    a non-identifier unpack key.  A real field with that raw name is never
    emitted as this unpack.  Returns ``None`` when this is not that unpack.
    """
    if keyword.arg is not None:
        return None
    literal, issue = _fold_constant(keyword.value, env=env)
    if issue is not None:
        return None
    if not isinstance(literal, dict) or set(literal) != {WIDGET_CHANNEL_SIDE_KEY}:
        return None
    decoded = decode_channel_side_payload(literal[WIDGET_CHANNEL_SIDE_KEY])
    if decoded is not None:
        return decoded[0], decoded[1], None
    return (
        (),
        (),
        _unsafe(
            keyword.value,
            "invalid_widget_channel_side",
            (
                f"{WIDGET_CHANNEL_SIDE_KEY!r} must be a field-name sequence "
                "or a {{widgets, order}} roster."
            ),
        ),
    )


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

    refusal_indexes = [
        index
        for index, statement in enumerate(module.body)
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "refuse"
    ]
    allowed_refusal_index = len(module.body) - 1
    if module.body and isinstance(module.body[-1], ast.Expr) and isinstance(module.body[-1].value, ast.Call):
        tail_call = module.body[-1].value
        if isinstance(tail_call.func, ast.Name) and tail_call.func.id == "done":
            allowed_refusal_index -= 1
    if refusal_indexes and (len(refusal_indexes) != 1 or refusal_indexes[0] != allowed_refusal_index):
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=(_diag("refusal_must_be_terminal", "refuse(...) must be the single final action (optionally followed by done()).", severity="error"),),
        )

    admission_issues = [
        _unsafe(node, code, message)
        for node, code, message in diagnose_unadmitted_ast(module)
    ]
    if admission_issues:
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=tuple(admission_issues),
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
            op_kind=op_kind_for_statement(statement),
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
    if isinstance(statement.iter, (ast.List, ast.Tuple)):
        return _expand_for_sequence(
            statement, source, env=env, max_for_iterations=max_for_iterations
        )
    values, diagnostic = _constant_range_values(statement.iter, max_for_iterations=max_for_iterations)
    if diagnostic is not None:
        return [], [diagnostic]
    return _expand_for_constant_values(
        statement, source, values, env=env, max_for_iterations=max_for_iterations
    )


def _expand_for_constant_values(
    statement: ast.For,
    source: str,
    values: tuple[Any, ...],
    *,
    env: Mapping[str, Any],
    max_for_iterations: int,
) -> tuple[list[StatementResult], list[CompactDiagnostic]]:
    assert isinstance(statement.target, ast.Name)
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


class _RewriteLoopName(ast.NodeTransformer):
    def __init__(self, name: str, replacement: ast.expr) -> None:
        self._name = name
        self._replacement = replacement

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id != self._name:
            return node
        return ast.copy_location(copy.deepcopy(self._replacement), node)


def _expand_for_sequence(
    statement: ast.For,
    source: str,
    *,
    env: Mapping[str, Any],
    max_for_iterations: int,
) -> tuple[list[StatementResult], list[CompactDiagnostic]]:
    assert isinstance(statement.target, ast.Name)
    assert isinstance(statement.iter, (ast.List, ast.Tuple))
    items = list(statement.iter.elts)
    if len(items) > max_for_iterations:
        return [], [
            _unsafe(
                statement.iter,
                "for_iteration_cap_exceeded",
                "for-loop exceeds the configured iteration cap.",
                detail={"iterations": len(items), "max_iterations": max_for_iterations},
            )
        ]
    if all(_is_graph_reference_value(item) for item in items):
        expanded: list[StatementResult] = []
        issues: list[CompactDiagnostic] = []
        rewriter = None
        for item in items:
            rewriter = _RewriteLoopName(statement.target.id, item)
            for child in statement.body:
                rewritten = rewriter.visit(copy.deepcopy(child))
                ast.fix_missing_locations(rewritten)
                child_expanded, child_issues = _expand_statement(
                    rewritten,
                    source,
                    env=env,
                    max_for_iterations=max_for_iterations,
                )
                issues.extend(child_issues)
                expanded.extend(child_expanded)
        return expanded, issues
    values: list[Any] = []
    for item in items:
        value, diagnostic = _fold_constant(item, env=env)
        if diagnostic is not None:
            return [], [diagnostic]
        values.append(value)
    return _expand_for_constant_values(
        statement,
        source,
        tuple(values),
        env=env,
        max_for_iterations=max_for_iterations,
    )


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
            if (
                isinstance(statement.value, ast.Call)
                and _call_name(statement.value) in _AGENT_TOOL_CALL_NAMES
            ):
                return [
                    _unsafe(
                        statement.value,
                        "tool_call_not_standalone",
                        "Agent tool calls must be standalone statements, not assignments.",
                    )
                ]
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


_SUBGRAPH_INTERFACE_KWARGS = frozenset({"name", "id", "inputs", "outputs"})


def _validate_subgraph_interface_call(
    node: ast.Call,
    *,
    env: Mapping[str, Any],
) -> list[CompactDiagnostic]:
    if node.args:
        return [_unsafe(node, "positional_args_not_allowed", "subgraph_interface() must use keyword arguments.")]
    issues: list[CompactDiagnostic] = []
    seen: set[str] = set()
    for keyword in node.keywords:
        if keyword.arg is None:
            issues.append(_unsafe(keyword.value, "kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed."))
            continue
        if keyword.arg not in _SUBGRAPH_INTERFACE_KWARGS:
            issues.append(
                _unsafe(
                    keyword.value,
                    "unknown_subgraph_interface_field",
                    f"subgraph_interface() does not accept {keyword.arg!r}.",
                )
            )
            continue
        seen.add(keyword.arg)
        _, fold_issue = _fold_constant(keyword.value, env=env)
        if fold_issue is not None:
            issues.append(fold_issue)
    missing = {"name", "inputs", "outputs"} - seen
    if missing:
        issues.append(
            _unsafe(
                node,
                "missing_subgraph_interface_field",
                "subgraph_interface() requires name=, inputs=, and outputs=.",
                detail={"missing": sorted(missing)},
            )
        )
    return issues


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
    if name in FORBIDDEN_CALL_NAMES or name.startswith("__"):
        if name == "set_title":
            return [_unsafe(node, "set_title_not_allowed", "set_title is not part of the edit grammar.")]
        return [_unsafe(node, "call_not_allowed", f"Call to {name!r} is not allowed.")]
    if name == "range":
        return [_unsafe(node, "range_only_in_for", "range(...) is only allowed as a for-loop iterator.")]
    if name == "subgraph_interface":
        if not top_level:
            return [_unsafe(node, "nested_call_not_allowed", "Nested calls are not allowed.")]
        return _validate_subgraph_interface_call(node, env=env)
    if name in CONTROL_CALL_NAMES:
        if name == "done" and (node.args or node.keywords):
            return [_unsafe(node, "done_arguments_not_allowed", "done() does not accept arguments.")]
        if name == "refuse":
            if node.args:
                return [_unsafe(node, "refusal_arguments_not_allowed", "refuse() requires keyword arguments.")]
            allowed = {"kind", "missing_classes", "feature_absences", "evidence", "message", "question"}
            names = [kw.arg for kw in node.keywords]
            unknown = [name for name in names if name not in allowed]
            duplicates = sorted(name for name in set(names) if names.count(name) > 1)
            kind_kw = next((kw for kw in node.keywords if kw.arg == "kind"), None)
            try:
                kind = ast.literal_eval(kind_kw.value) if kind_kw is not None else None
            except (ValueError, TypeError, SyntaxError):
                kind = None
            message_kw = next((kw for kw in node.keywords if kw.arg in {"message", "question"}), None)
            try:
                message = ast.literal_eval(message_kw.value) if message_kw is not None else None
            except (ValueError, TypeError, SyntaxError):
                message = None
            invalid_fields: list[str] = []
            if kind not in {"requires_custom_nodes", "clarify"}:
                invalid_fields.append("kind")
            if not isinstance(message, str) or not message.strip():
                invalid_fields.append("message")
            if sum(item.arg in {"message", "question"} for item in node.keywords) != 1:
                invalid_fields.append("message_or_question")
            for field in ("missing_classes", "evidence"):
                kw = next((item for item in node.keywords if item.arg == field), None)
                if kw is None:
                    continue
                try:
                    value = ast.literal_eval(kw.value)
                except (ValueError, TypeError, SyntaxError):
                    value = None
                if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) and item.strip() for item in value):
                    invalid_fields.append(field)
                # ``evidence`` is required and non-empty for a
                # requires_custom_nodes refusal.  A clarify refusal may
                # intentionally carry no evidence: it remains an
                # unvalidated model-selected clarification until the
                # authority layer proves a complete absence ledger.  Treat
                # the empty optional list as valid syntax so a model cannot
                # burn its entire retry budget on harmless serialization.
                elif field == "evidence" and not value and kind == "requires_custom_nodes":
                    invalid_fields.append(field)
            feature_kw = next((item for item in node.keywords if item.arg == "feature_absences"), None)
            if feature_kw is not None:
                try:
                    features = ast.literal_eval(feature_kw.value)
                except (ValueError, TypeError, SyntaxError):
                    features = None
                if not isinstance(features, (list, tuple)) or not all(isinstance(item, dict) for item in features):
                    invalid_fields.append("feature_absences")
            if kind == "requires_custom_nodes":
                if not any(item.arg == "missing_classes" for item in node.keywords):
                    invalid_fields.append("missing_classes")
                if not any(item.arg == "evidence" for item in node.keywords):
                    invalid_fields.append("evidence")
            if duplicates or unknown or invalid_fields:
                return [_unsafe(
                    node,
                    "invalid_refusal_action",
                    "refuse() requires kind= and accepts only missing_classes, feature_absences, evidence, message, or question.",
                    detail={"unknown": unknown, "duplicates": duplicates, "invalid": invalid_fields},
                )]
        return []
    if name == "clarify":
        return [
            _unsafe(
                node,
                "unsupported_query_call",
                "Only search(...), python(), done(), and the ten agent "
                "tool calls (hivemind_search, hivemind_get, registry_lookup, "
                "ready_template_list, ready_template_load, rank_edit_targets, "
                "suggest_seed_nodes, layout_hints, web_search) are supported as "
                "top-level query calls.",
            )
        ]
    if name in _QUERY_CALL_NAMES:
        if not top_level:
            return [_unsafe(node, "nested_call_not_allowed", "Nested calls are not allowed.")]
        if name in _AGENT_TOOL_CALL_NAMES:
            return _validate_tool_call(node, env=env)
        if name == "schema_check":
            allowed = {"class_type", "member_kind", "member"}
            seen: set[str] = set()
            issues: list[CompactDiagnostic] = []
            for keyword in node.keywords:
                if keyword.arg is None or keyword.arg not in allowed or keyword.arg in seen:
                    issues.append(_unsafe(keyword, "invalid_schema_check", "schema_check requires unique class_type, member_kind, and member keywords."))
                    continue
                seen.add(keyword.arg)
                value, issue = _fold_constant(keyword.value, env=env)
                if issue is not None or not isinstance(value, str) or not value.strip():
                    issues.append(issue or _unsafe(keyword.value, "invalid_schema_check", f"schema_check {keyword.arg}= must be a non-empty string."))
            if seen != allowed:
                issues.append(_unsafe(node, "invalid_schema_check", "schema_check requires class_type=, member_kind=, and member=."))
            return issues
        return []
    if not top_level:
        return [_unsafe(node, "nested_call_not_allowed", "Nested calls are not allowed.")]
    if node.args:
        # `node("ClassType", **kwargs)` is the emit form for identifiers that
        # are not valid Python names (subgraph uuids, hyphenated classes).
        if name == "node" and len(node.args) == 1:
            class_type, class_issue = _fold_constant(node.args[0], env=env)
            if class_issue is not None:
                return [class_issue]
            if not isinstance(class_type, str) or not class_type:
                return [
                    _unsafe(
                        node.args[0],
                        "invalid_node_class_type",
                        "node(...) requires a non-empty class-type string.",
                    )
                ]
        else:
            return [_unsafe(node, "positional_args_not_allowed", "Node calls must use keyword arguments.")]
    issues: list[CompactDiagnostic] = []
    for keyword in node.keywords:
        if keyword.arg is None:
            side = _channel_side_unpack(keyword, env=env)
            if side is not None:
                _widgets, _inputs, side_issue = side
                if side_issue is not None:
                    issues.append(side_issue)
                continue
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
        if keyword.arg == "relation" or keyword.arg == "group":
            value, diagnostic = _fold_constant(keyword.value, env=env)
            _ = value
            if diagnostic is not None:
                issues.append(diagnostic)
            continue
        if reserved_kwarg_is_coordinate_hint(keyword.arg, value=keyword.value):
            value, diagnostic = _fold_constant(keyword.value, env=env)
            _ = value
            if diagnostic is not None:
                issues.append(diagnostic)
            continue
        issues.extend(_validate_node_call_value(keyword.value, env=env))
    return issues


def _validate_tool_call(node: ast.Call, *, env: Mapping[str, Any]) -> list[CompactDiagnostic]:
    """Validate a Wave-A agent tool call's arguments as constants.

    Tool arguments (positional and keyword) must be constant-foldable values;
    handle references, nested calls, ``**kwargs`` unpacking, and dunder
    keywords are rejected here.  Shape validation (arity, required names,
    allowed keywords) happens at resolve time in ``_resolve.py``.
    """
    issues: list[CompactDiagnostic] = []
    for arg in node.args:
        if _is_handle_ref(arg):
            issues.append(
                _unsafe(arg, "tool_argument_not_constant", "Tool call arguments must be constant values.")
            )
            continue
        value, diagnostic = _fold_constant(arg, env=env)
        _ = value
        if diagnostic is not None:
            issues.append(diagnostic)
    for keyword in node.keywords:
        if keyword.arg is None:
            issues.append(
                _unsafe(keyword.value, "kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.")
            )
            continue
        if keyword.arg.startswith("__"):
            issues.append(
                _unsafe(keyword.value, "dunder_keyword_not_allowed", "Dunder keyword names are not allowed.")
            )
            continue
        value, diagnostic = _fold_constant(keyword.value, env=env)
        _ = value
        if diagnostic is not None:
            issues.append(diagnostic)
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
    forbidden_attr_code = FORBIDDEN_ASSIGN_ATTRS.get(target.attr)
    if forbidden_attr_code is not None:
        return [
            _unsafe(
                target,
                forbidden_attr_code,
                f"{target.attr} assignment is not part of the edit grammar.",
            )
        ]
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


def reserved_kwarg_is_coordinate_hint(
    name: str | None,
    *,
    value: ast.expr | None = None,
    schema_inputs: Mapping[str, Any] | None = None,
) -> bool:
    """True when *name* is a placement hint, not a real node input.

    ``pos`` / ``position`` / ``coords`` / ``x`` / ``y`` are reserved as raw
    coordinate placement kwargs, but some classes (``easy pipeIn``) expose a
    real input with the same name.  A schema input of that name or a
    graph-reference value is the real input; only foldable constants stay
    hints.
    """
    if name not in _RAW_COORDINATE_HINT_NAMES:
        return False
    if schema_inputs is not None and name in schema_inputs:
        return False
    if value is not None and _is_graph_reference_value(value):
        return False
    return True


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
