from __future__ import annotations

import ast
from typing import Any, Mapping

from vibecomfy.porting.edit_ops import (
    AnchorRef,
    LinkSourceRef,
    NodeTarget,
)
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    InferredAnchorHint,
    infer_add_node_anchor_hint,
)
from vibecomfy.porting.slot_codec import to_raw_name
from vibecomfy.schema import schema_for, socket_types_compatible

from vibecomfy.porting.edit_session_types import (
    CompactDiagnostic,
    StatementResult,
    _ResolvedAddNodeCall,
    _ResolvedGraphName,
    _ResolvedOutputEndpoint,
    _ResolvedTargetField,
    _ExpandedStatement,
    _diag,
)
from vibecomfy.porting.edit_session_parse import (
    _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES,
    _RAW_COORDINATE_HINT_NAMES,
    _assignment_op_kind,
    _call_name,
    _fold_constant,
    _is_graph_reference_value,
    _resolve_vibecomfy_constructor,
    _unsafe,
)
from vibecomfy.porting.edit_session_ir_utils import (
    _MISSING_WIDGET_VALUE,
    _find_named_slot,
    _link_origin,
    _normalize_type,
    _output_slot_name,
    _output_specs,
    _socket_type_from_widget_value,
    _widget_value_for_field,
)


class _ResolveMixin:
    """Symbolic-name resolution methods — the named M4 seam."""

    def _uid_for_scope(self, scope_path: str, class_type: str) -> str:
        """Best-effort uid lookup for a newly added node by looking at the ledger."""
        # Look for nodes matching class_type that were recently added.
        # The simplest approach: check the most recently added node in the ledger.
        nodes = self.ledger.graph.get("nodes") or []
        for node in reversed(nodes):
            ct = str(node.get("type") or node.get("class_type") or "")
            if ct == class_type:
                uid = node.get("properties", {}).get("vibecomfy_uid", "")
                if uid and uid in self.name_by_uid:
                    return uid
        return ""

    def _resolve_statement(
        self,
        item: "_ExpandedStatement",
        *,
        placement_facts: BatchPlacementFacts,
    ) -> StatementResult:
        statement = item.node
        source = item.source
        env = item.env
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call_name = _call_name(statement.value)
            if call_name == "done":
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="done",
                )
            return self._resolve_query_statement(
                statement_index=item.statement_index,
                source=source,
                call=statement.value,
                env=env,
            )
        if isinstance(statement, ast.Assign):
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                return self._resolve_add_node_statement(
                    statement_index=item.statement_index,
                    source=source,
                    target_name=target.id,
                    value=statement.value,
                    env=env,
                    placement_facts=placement_facts,
                )
            assert isinstance(target, ast.Attribute)
            field_target, target_issues = self._resolve_target_field(target)
            if target_issues:
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind=_assignment_op_kind(statement.value, target_attr=target.attr),
                    diagnostics=tuple(target_issues),
                )
            assert field_target is not None
            rhs = statement.value
            if isinstance(rhs, ast.Constant) and rhs.value is None:
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="remove_link",
                    detail={"resolved_target": field_target, "ast_node": statement, "constant_env": dict(env)},
                )
            if _is_graph_reference_value(rhs):
                endpoint, endpoint_issues = self._resolve_rhs_endpoint(rhs, target=field_target)
                if endpoint_issues:
                    return StatementResult(
                        statement_index=item.statement_index,
                        source=source,
                        ok=False,
                        landed=False,
                        op_kind=_assignment_op_kind(rhs, target_attr=target.attr),
                        diagnostics=tuple(endpoint_issues),
                    )
                assert endpoint is not None
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="upsert_link",
                    detail={"resolved_target": field_target, "resolved_endpoint": endpoint, "ast_node": statement, "constant_env": dict(env)},
                )
            return StatementResult(
                statement_index=item.statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="set_mode" if target.attr == "mode" else "set_node_field",
                detail={"resolved_target": field_target, "ast_node": statement, "constant_env": dict(env)},
            )
        assert isinstance(statement, ast.Delete)
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            node_ref, issues = self._resolve_graph_name(target.id)
        else:
            node_ref, issues = None, [_unsafe(target, "scope_escape_not_allowed", "Only bare graph names may be deleted.")]
        _ = node_ref
        return StatementResult(
            statement_index=item.statement_index,
            source=source,
            ok=not issues,
            landed=False,
            op_kind="remove_node",
            diagnostics=tuple(issues),
            detail={"resolved_node": node_ref, "ast_node": statement, "constant_env": dict(env)}
            if node_ref is not None
            else {"ast_node": statement, "constant_env": dict(env)},
        )

    def _resolve_query_statement(
        self,
        *,
        statement_index: int,
        source: str,
        call: ast.Call,
        env: Mapping[str, Any],
    ) -> StatementResult:
        call_name = _call_name(call)
        if call_name != "search":
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "unsupported_query_call",
                        "Only search(...) and done() are supported as top-level query calls.",
                        severity="error",
                        detail={"call": call_name},
                    ),
                ),
            )

        allowed = {"focus_types", "compatible_input_type", "compatible_output_type", "formatted"}
        kwargs: dict[str, Any] = {}
        diagnostics: list[CompactDiagnostic] = []
        for keyword in call.keywords:
            if keyword.arg is None:
                diagnostics.append(
                    _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                )
                continue
            if keyword.arg not in allowed:
                diagnostics.append(
                    _diag(
                        "unsupported_search_keyword",
                        f"search(...) does not accept keyword {keyword.arg!r}.",
                        severity="error",
                        detail={"keyword": keyword.arg, "allowed": sorted(allowed)},
                    )
                )
                continue
            value, diagnostic = _fold_constant(keyword.value, env=env)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
                continue
            kwargs[keyword.arg] = value
        if diagnostics:
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=tuple(diagnostics),
                detail={"query": "search"},
            )

        try:
            output = self.search(
                focus_types=kwargs.get("focus_types"),
                compatible_input_type=kwargs.get("compatible_input_type"),
                compatible_output_type=kwargs.get("compatible_output_type"),
                formatted=True,
            )
        except Exception as exc:  # noqa: BLE001 - report query failures in-band
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "search_query_failed",
                        f"search(...) failed: {exc}",
                        severity="error",
                    ),
                ),
                detail={"query": "search"},
            )

        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="query",
            detail={"query": "search", "query_output": str(output)},
        )

    def _bind_graph_name(self, name: str, uid: str) -> None:
        prior_uid = self.uid_by_name.get(name)
        if prior_uid is not None and self.name_by_uid.get(prior_uid) == name:
            self.name_by_uid.pop(prior_uid, None)
        prior_name = self.name_by_uid.get(uid)
        if prior_name is not None and self.uid_by_name.get(prior_name) == uid:
            self.uid_by_name.pop(prior_name, None)
        self.uid_by_name[name] = uid
        self.name_by_uid[uid] = name
        self.unbound_names.discard(name)

    def _mark_name_unbound(self, name: str) -> None:
        prior_uid = self.uid_by_name.pop(name, None)
        if prior_uid is not None and self.name_by_uid.get(prior_uid) == name:
            self.name_by_uid.pop(prior_uid, None)
        self.unbound_names.add(name)

    def _resolve_add_node_statement(
        self,
        *,
        statement_index: int,
        source: str,
        target_name: str,
        value: ast.expr,
        env: Mapping[str, Any],
        placement_facts: BatchPlacementFacts,
    ) -> StatementResult:
        if target_name.startswith("__"):
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=(
                    _diag("dunder_name_not_allowed", f"Graph name {target_name!r} is not allowed.", severity="error"),
                ),
                detail={"target_name": target_name},
            )
        if not isinstance(value, ast.Call):
            self._mark_name_unbound(target_name)
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=(
                    _diag("expression_not_call", "Only node-construction calls may be assigned to graph names.", severity="error"),
                ),
                detail={"target_name": target_name},
            )
        resolved_call, issues = self._resolve_add_node_call(
            target_name,
            value,
            env=env,
            placement_facts=placement_facts,
        )
        if issues:
            self._mark_name_unbound(target_name)
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=tuple(issues),
                detail={"target_name": target_name, "ast_node": value, "constant_env": dict(env)},
            )
        assert resolved_call is not None
        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="node_call",
            detail={
                "target_name": target_name,
                "ast_node": value,
                "constant_env": dict(env),
                "resolved_add_node": resolved_call,
            },
        )

    def _resolve_add_node_call(
        self,
        target_name: str,
        call: ast.Call,
        *,
        env: Mapping[str, Any],
        placement_facts: BatchPlacementFacts,
    ) -> tuple[_ResolvedAddNodeCall | None, list[CompactDiagnostic]]:
        func = call.func
        class_type, dotted_vibecomfy = _resolve_vibecomfy_constructor(func)
        if dotted_vibecomfy and class_type not in _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES:
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface.",
                )
            ]
        if class_type is None:
            return None, [_unsafe(func, "call_target_not_name", "Node construction calls must target a simple class name.")]
        if class_type.startswith("vibecomfy.") and class_type not in _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES:
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface.",
                )
            ]

        schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        fake_target_node = _ResolvedGraphName(
            name=target_name,
            uid="<pending>",
            scope_path="",
            node={},
            class_type=class_type,
        )
        literal_fields: dict[str, Any] = {}
        linked_inputs: dict[str, LinkSourceRef] = {}
        anchor_near: NodeTarget | None = None
        relation: str | None = None
        group_title: str | None = None
        issues: list[CompactDiagnostic] = []

        for keyword in call.keywords:
            if keyword.arg is None:
                issues.append(_unsafe(keyword.value, "kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed."))
                continue
            name = keyword.arg
            if name in _RAW_COORDINATE_HINT_NAMES:
                issues.append(
                    _unsafe(
                        keyword.value,
                        "raw_coordinate_kwarg_not_allowed",
                        f"Raw coordinate kwarg {name!r} is not allowed; use near=..., relation=..., and group=... placement hints.",
                    )
                )
                continue
            if name == "near":
                if not isinstance(keyword.value, ast.Name):
                    issues.append(
                        _unsafe(keyword.value, "invalid_near_hint", "near= must reference a rendered graph name, not a slot or literal.")
                    )
                    continue
                node_ref, near_issues = self._resolve_graph_name(keyword.value.id)
                if near_issues:
                    issues.extend(near_issues)
                    continue
                assert node_ref is not None
                anchor_near = NodeTarget(node_ref.scope_path, node_ref.uid)
                continue
            if name == "relation":
                relation_value, relation_issue = _fold_constant(keyword.value, env=env)
                if relation_issue is not None:
                    issues.append(relation_issue)
                    continue
                if not isinstance(relation_value, str):
                    issues.append(_unsafe(keyword.value, "invalid_relation_hint", "relation= must be a string literal."))
                    continue
                relation = relation_value.strip()
                if relation not in {"near", "right_of", "below"}:
                    issues.append(
                        _unsafe(
                            keyword.value,
                            "invalid_relation_hint",
                            "relation= must be one of 'near', 'right_of', or 'below' for Python add-node statements.",
                        )
                    )
                continue
            if name == "group":
                group_value, group_issue = _fold_constant(keyword.value, env=env)
                if group_issue is not None:
                    issues.append(group_issue)
                    continue
                if not isinstance(group_value, str) or not group_value.strip():
                    issues.append(_unsafe(keyword.value, "invalid_group_hint", "group= must be a non-empty string literal."))
                    continue
                group_title = group_value
                continue
            if _is_graph_reference_value(keyword.value):
                socket_type = _normalize_type(getattr(schema_inputs.get(name), "type", None))
                target = _ResolvedTargetField(node=fake_target_node, field_name=name, socket_type=socket_type)
                endpoint, endpoint_issues = self._resolve_rhs_endpoint(keyword.value, target=target)
                if endpoint_issues:
                    issues.extend(endpoint_issues)
                    continue
                assert endpoint is not None
                linked_inputs[name] = LinkSourceRef(endpoint.node.scope_path, endpoint.node.uid, endpoint.slot_name)
                continue
            literal_value, literal_issue = _fold_constant(keyword.value, env=env)
            if literal_issue is not None:
                issues.append(literal_issue)
                continue
            literal_fields[name] = literal_value

        if relation is not None and anchor_near is None and group_title is None:
            issues.append(
                _diag(
                    "anchor_target_missing",
                    "relation= requires near=... or group=... to anchor the new node.",
                    severity="error",
                    detail={"class_type": class_type, "target_name": target_name},
                )
            )

        scope_paths = {ref.scope_path for ref in linked_inputs.values()}
        if anchor_near is not None:
            scope_paths.add(anchor_near.scope_path)
        if len(scope_paths) > 1:
            issues.append(
                _diag(
                    "cross_scope_add_node_unsupported",
                    "Add-node statements cannot mix link and anchor references from different scopes.",
                    severity="error",
                    detail={"target_name": target_name, "scope_paths": sorted(scope_paths)},
                )
            )
        if issues:
            return None, issues
        scope_path = next(iter(scope_paths), "")
        anchor = None
        if anchor_near is not None or group_title is not None:
            anchor = AnchorRef(
                relation=(relation or "near"),  # type: ignore[arg-type]
                near=anchor_near,
                group_title=group_title,
            )
        else:
            anchor = self._infer_add_node_anchor(
                target_name=target_name,
                scope_path=scope_path,
                resolved_inputs=linked_inputs,
                placement_facts=placement_facts,
            )
        return (
            _ResolvedAddNodeCall(
                target_name=target_name,
                scope_path=scope_path,
                class_type=class_type,
                fields=literal_fields,
                inputs=linked_inputs,
                anchor=anchor,
            ),
            [],
        )

    @staticmethod
    def _compact_port_issue(issue: Any) -> CompactDiagnostic:
        return CompactDiagnostic(
            code=str(getattr(issue, "code", "edit_apply_error")),
            message=str(getattr(issue, "message", "Edit apply failed.")),
            severity=str(getattr(issue, "severity", "error")),
            detail=dict(getattr(issue, "detail", {}) or {}),
        )

    def _estimate_add_node_width(self, class_type: str) -> int:
        from vibecomfy.porting.layout.sizing import estimate_node_size
        from vibecomfy.workflow import VibeNode

        schema = schema_for(self.schema_provider, class_type)
        return estimate_node_size(VibeNode(id="__batch__", class_type=class_type, uid="__batch__"), schema)[0]

    def _infer_add_node_anchor(
        self,
        *,
        target_name: str,
        scope_path: str,
        resolved_inputs: Mapping[str, LinkSourceRef],
        placement_facts: BatchPlacementFacts,
    ) -> AnchorRef | None:
        hint = infer_add_node_anchor_hint(
            target_name=target_name,
            resolved_inputs=resolved_inputs,
            placement_facts=placement_facts,
            current_input_source_ref=self._current_input_source_ref,
            uid_to_name=self.name_by_uid,
        )
        if hint is None:
            return None
        return self._materialize_inferred_anchor(scope_path=scope_path, hint=hint)

    def _materialize_inferred_anchor(
        self,
        *,
        scope_path: str,
        hint: InferredAnchorHint,
    ) -> AnchorRef | None:
        if hint.relation == "between" and hint.between_names is not None:
            left = self._resolve_graph_name_soft(hint.between_names[0])
            right = self._resolve_graph_name_soft(hint.between_names[1])
            if left is None or right is None or left.scope_path != scope_path or right.scope_path != scope_path:
                return None
            return AnchorRef(
                relation="between",
                between=(NodeTarget(left.scope_path, left.uid), NodeTarget(right.scope_path, right.uid)),
            )
        if hint.near_name is None:
            return None
        near = self._resolve_graph_name_soft(hint.near_name)
        if near is None or near.scope_path != scope_path:
            return None
        return AnchorRef(relation="right_of", near=NodeTarget(near.scope_path, near.uid))

    def _resolve_graph_name_soft(self, name: str) -> _ResolvedGraphName | None:
        node_ref, issues = self._resolve_graph_name(name)
        if issues:
            return None
        return node_ref

    def _graph_name_exists(self, name: str) -> bool:
        node_ref, issues = self._resolve_graph_name(name)
        return node_ref is not None and not issues

    def _current_input_source_ref(self, target_name: str, target_field: str) -> LinkSourceRef | None:
        target = self._resolve_graph_name_soft(target_name)
        if target is None:
            return None
        inputs = target.node.get("inputs")
        if not isinstance(inputs, list):
            return None
        input_slot = _find_named_slot(inputs, target_field)
        if input_slot is None:
            return None
        link_id = input_slot.get("link")
        if not isinstance(link_id, int):
            return None
        raw_link = self.ledger.resolve_link(target.scope_path, link_id)
        if raw_link is None:
            return None
        origin_id, origin_slot = _link_origin(raw_link)
        if origin_id is None:
            return None
        origin_node = self._node_by_id(target.scope_path, origin_id)
        if origin_node is None:
            return None
        origin_uid = str(origin_node.get("properties", {}).get("vibecomfy_uid") or origin_node.get("id"))
        slot_name = _output_slot_name(origin_node, origin_slot, self.schema_provider)
        output_slot: str | int = slot_name if slot_name is not None else origin_slot
        return LinkSourceRef(target.scope_path, origin_uid, output_slot)

    def _node_by_id(self, scope_path: str, node_id: int) -> Mapping[str, Any] | None:
        scope = self.ledger.scopes.get(scope_path)
        if scope is None:
            return None
        nodes = scope.graph.get("nodes")
        if not isinstance(nodes, list):
            return None
        for node in nodes:
            if isinstance(node, Mapping) and node.get("id") == node_id:
                return node
        return None

    @staticmethod
    def _dependency_cause(statement: StatementResult) -> str | None:
        for diagnostic in statement.diagnostics:
            if diagnostic.code == "unbound_graph_name":
                name = str(diagnostic.detail.get("name", "?"))
                return f"Statement depends on graph name {name!r} whose add-node statement did not land."
        return None

    def _resolve_graph_name(
        self,
        name: str,
    ) -> tuple[_ResolvedGraphName | None, list[CompactDiagnostic]]:
        if name.startswith("__"):
            return None, [_diag("dunder_name_not_allowed", f"Graph name {name!r} is not allowed.", severity="error")]
        if name in self.unbound_names:
            return None, [
                _diag(
                    "unbound_graph_name",
                    f"Graph name {name!r} is currently unbound because its add-node statement did not land.",
                    severity="error",
                    detail={"name": name},
                )
            ]
        uid = self.uid_by_name.get(name)
        if uid is None:
            return None, [
                _diag(
                    "unknown_graph_name",
                    f"Unknown graph name {name!r}. Render the session again if the canvas changed.",
                    severity="error",
                    detail={"name": name},
                )
            ]
        matches = [(scope_path, node) for (scope_path, node_uid), node in self.ledger.node_index.items() if node_uid == uid]
        if not matches:
            return None, [
                _diag(
                    "stale_graph_name",
                    f"Graph name {name!r} still points at uid {uid!r}, but that uid is no longer present.",
                    severity="error",
                    detail={"name": name, "uid": uid},
                )
            ]
        if len(matches) > 1:
            return None, [
                _diag(
                    "scope_escape_not_allowed",
                    f"Graph name {name!r} resolves to multiple scopes; explicit scope paths are not allowed in M1.",
                    severity="error",
                    detail={"name": name, "uid": uid, "scope_paths": [scope for scope, _ in matches]},
                )
            ]
        scope_path, node = matches[0]
        class_type = str(node.get("type") or node.get("class_type") or "")
        return _ResolvedGraphName(name=name, uid=uid, scope_path=scope_path, node=node, class_type=class_type), []

    def _resolve_target_field(
        self,
        target: ast.Attribute,
    ) -> tuple[_ResolvedTargetField | None, list[CompactDiagnostic]]:
        node_ref, issues = self._resolve_attribute_base(target, code_unknown="unknown_target_name")
        if issues:
            return None, issues
        assert node_ref is not None
        if target.attr.startswith("__"):
            return None, [_unsafe(target, "dunder_attribute_not_allowed", "Dunder target attributes are not allowed.")]
        schema = schema_for(self.schema_provider, node_ref.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        schema_input = schema_inputs.get(target.attr)
        raw_input = _find_named_slot(node_ref.node.get("inputs"), target.attr)
        widget_value = _widget_value_for_field(node_ref.node, node_ref.class_type, target.attr)
        if raw_input is None and schema_input is None and widget_value is _MISSING_WIDGET_VALUE and target.attr != "mode":
            return None, [
                _diag(
                    "unknown_target_field",
                    f"{node_ref.class_type} has no editable field or input named {target.attr!r}.",
                    severity="error",
                    detail={"name": node_ref.name, "uid": node_ref.uid, "field": target.attr},
                )
            ]
        socket_type = _normalize_type(
            getattr(schema_input, "type", None) if schema_input is not None else raw_input.get("type") if isinstance(raw_input, Mapping) else None
        )
        if socket_type is None and widget_value is not _MISSING_WIDGET_VALUE:
            socket_type = _socket_type_from_widget_value(widget_value)
        return _ResolvedTargetField(node=node_ref, field_name=target.attr, socket_type=socket_type), []

    def _resolve_rhs_endpoint(
        self,
        value: ast.expr,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        if isinstance(value, ast.Name):
            node_ref, issues = self._resolve_graph_name(value.id)
            if issues:
                return None, issues
            assert node_ref is not None
            return self._resolve_bare_output(node_ref, target=target)
        assert isinstance(value, ast.Attribute)
        node_ref, issues = self._resolve_attribute_base(value, code_unknown="unknown_source_name")
        if issues:
            return None, issues
        assert node_ref is not None
        if value.attr.startswith("__"):
            return None, [_unsafe(value, "dunder_attribute_not_allowed", "Dunder source attributes are not allowed.")]
        return self._resolve_named_output(node_ref, value.attr, target=target)

    def _resolve_attribute_base(
        self,
        attr: ast.Attribute,
        *,
        code_unknown: str,
    ) -> tuple[_ResolvedGraphName | None, list[CompactDiagnostic]]:
        if isinstance(attr.value, ast.Attribute):
            return None, [
                _unsafe(
                    attr,
                    "scope_escape_not_allowed",
                    "Only one attribute hop is allowed; nested attribute scope escapes are not allowed.",
                )
            ]
        if not isinstance(attr.value, ast.Name):
            return None, [_unsafe(attr, "attribute_base_not_name", "Attribute access must start from a rendered graph name.")]
        node_ref, issues = self._resolve_graph_name(attr.value.id)
        if issues and issues[0].code == "unknown_graph_name":
            issues = [
                _diag(
                    code_unknown,
                    issues[0].message,
                    severity=issues[0].severity,
                    detail=issues[0].detail,
                )
            ]
        return node_ref, issues

    def _resolve_named_output(
        self,
        node_ref: _ResolvedGraphName,
        slot_attr: str,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        raw_outputs = _output_specs(node_ref.node, self.schema_provider, node_ref.class_type)
        raw_name_map = {item["name"]: item["name"] for item in raw_outputs if item["name"]}
        try:
            raw_slot = slot_attr if slot_attr in raw_name_map else to_raw_name(slot_attr, context=raw_name_map)
        except (KeyError, ValueError):
            raw_slot = None
        if raw_slot is None:
            return None, [
                _diag(
                    "unknown_output_slot",
                    f"{node_ref.class_type} has no output named {slot_attr!r}.",
                    severity="error",
                    detail={
                        "name": node_ref.name,
                        "uid": node_ref.uid,
                        "slot": slot_attr,
                        "available_slots": [item["name"] for item in raw_outputs if item["name"]],
                    },
                )
            ]
        for item in raw_outputs:
            if item["name"] == raw_slot:
                return _ResolvedOutputEndpoint(
                    node=node_ref,
                    slot_name=raw_slot,
                    slot_index=item["index"],
                    socket_type=item["type"],
                ), []
        return None, [
            _diag(
                "unknown_output_slot",
                f"{node_ref.class_type} has no output named {raw_slot!r}.",
                severity="error",
                detail={"name": node_ref.name, "uid": node_ref.uid, "slot": raw_slot},
            )
        ]

    def _resolve_bare_output(
        self,
        node_ref: _ResolvedGraphName,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        if target.socket_type is None:
            return None, [
                _diag(
                    "ambiguous_bare_reference",
                    (
                        f"Bare reference {node_ref.name!r} cannot be resolved for "
                        f"{target.node.class_type}.{target.field_name} without a schema-backed target socket type."
                    ),
                    severity="error",
                    detail={"target_name": target.node.name, "target_field": target.field_name, "source_name": node_ref.name},
                )
            ]
        candidates = [
            item
            for item in _output_specs(node_ref.node, self.schema_provider, node_ref.class_type)
            if item["type"] is not None and socket_types_compatible(item["type"], target.socket_type)
        ]
        if len(candidates) != 1:
            return None, [
                _diag(
                    "ambiguous_bare_reference",
                    (
                        f"Bare reference {node_ref.name!r} is ambiguous for "
                        f"{target.node.class_type}.{target.field_name}; expected exactly one compatible output."
                    ),
                    severity="error",
                    detail={
                        "target_name": target.node.name,
                        "target_field": target.field_name,
                        "source_name": node_ref.name,
                        "target_socket_type": target.socket_type,
                        "candidate_slots": [item["name"] for item in candidates],
                    },
                )
            ]
        candidate = candidates[0]
        return _ResolvedOutputEndpoint(
            node=node_ref,
            slot_name=candidate["name"],
            slot_index=candidate["index"],
            socket_type=candidate["type"],
        ), []
