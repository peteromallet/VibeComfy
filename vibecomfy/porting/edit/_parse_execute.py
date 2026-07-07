from __future__ import annotations

import ast
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.porting.edit.apply import apply_delta
from vibecomfy.porting.edit.ledger import EditLedger
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.edit.projection import HELPER_NODE_TYPES, MODE_LABELS
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    build_batch_placement_facts,
)
from vibecomfy.porting.edit._session_types import (
    BatchResult,
    CompactDiagnostic,
    StatementResult,
    _ExpandedStatement,
    _ResolvedAddNodeCall,
    _ResolvedGraphName,
    _ResolvedOutputEndpoint,
    _ResolvedTargetField,
    _diag,
)
from vibecomfy.porting.edit._parse import (
    _fold_constant,
    _parse_and_validate_batch,
)
from vibecomfy.porting.edit._ir_utils import _uids_for_op

_MODE_LABEL_TO_VALUE = {str(label): mode for mode, label in MODE_LABELS.items()}


class _ParseExecuteMixin:

    def apply_batch(self, code: str) -> BatchResult:
        parsed = _parse_and_validate_batch(
            code,
            max_batch_bytes=self.max_batch_bytes,
            max_statements=self.max_statements,
            max_expanded_statements=self.max_expanded_statements,
            max_for_iterations=self.max_for_iterations,
        )
        if parsed.diagnostics:
            return BatchResult(
                ok=False,
                statements=parsed.statements,
                diagnostics=parsed.diagnostics,
            )
        placement_facts = build_batch_placement_facts(
            parsed.expanded,
            graph_name_exists=self._graph_name_exists,
            estimate_add_node_width=self._estimate_add_node_width,
        )
        snapshot = self._snapshot_mutable_state()
        statement_results, landed_ops, diagnostics = self._execute_statements(
            parsed.expanded,
            placement_facts=placement_facts,
        )
        saw_landed_edit = False
        saw_failed_edit = False
        failed_edit = False
        for statement in statement_results:
            if not self._is_edit_statement(statement):
                continue
            if statement.landed:
                saw_landed_edit = True
                continue
            if not statement.ok and (saw_landed_edit or saw_failed_edit):
                failed_edit = True
                break
            if not statement.ok:
                saw_failed_edit = True
        if failed_edit:
            self._restore_snapshot(snapshot)
            rollback_diag = _diag(
                "batch_transaction_rolled_back",
                "A later edit statement failed, so all edits from this batch were rolled back.",
                severity="error",
            )
            rolled_back: list[StatementResult] = []
            for stmt in statement_results:
                diagnostics_for_statement = stmt.diagnostics
                ok = stmt.ok
                if stmt.landed and self._is_edit_statement(stmt):
                    diagnostics_for_statement = stmt.diagnostics + (rollback_diag,)
                    ok = False
                rolled_back.append(
                    StatementResult(
                        statement_index=stmt.statement_index,
                        source=stmt.source,
                        ok=ok,
                        diagnostics=diagnostics_for_statement,
                        landed=False,
                        op_kind=stmt.op_kind,
                        detail=dict(stmt.detail),
                        touched_uids=(),
                        dependency_cause=stmt.dependency_cause,
                        teaching_hint=stmt.teaching_hint,
                    )
                )
            return BatchResult(
                ok=False,
                statements=tuple(rolled_back),
                diagnostics=diagnostics + (rollback_diag,),
                landed_ops=(),
                field_changes=(),
            )
        if saw_failed_edit and not landed_ops:
            self._restore_snapshot(snapshot)
        field_changes, statement_results = self._build_field_changes(
            landed_ops,
            statement_results,
        )
        return BatchResult(
            ok=not diagnostics and all(statement.ok for statement in statement_results),
            statements=statement_results,
            diagnostics=diagnostics,
            landed_ops=landed_ops,
            field_changes=field_changes,
        )

    def _snapshot_mutable_state(self) -> dict:
        return {
            "working_ui": deepcopy(self.working_ui),
            "landed_ops": list(self.landed_ops),
            "touched_uids": set(self.touched_uids),
            "touched_node_ids": set(self.touched_node_ids),
            "uid_by_name": dict(self.uid_by_name),
            "name_by_uid": dict(self.name_by_uid),
            "unbound_names": set(self.unbound_names),
        }

    def _restore_snapshot(self, snapshot: dict) -> None:
        self.working_ui = snapshot["working_ui"]
        self.ledger = EditLedger.ingest(self.working_ui)
        self.landed_ops = snapshot["landed_ops"]
        self.touched_uids = snapshot["touched_uids"]
        self.touched_node_ids = snapshot["touched_node_ids"]
        self.uid_by_name = snapshot["uid_by_name"]
        self.name_by_uid = snapshot["name_by_uid"]
        self.unbound_names = snapshot["unbound_names"]

    @staticmethod
    def _is_edit_statement(statement: StatementResult) -> bool:
        return str(statement.op_kind or "") not in {"", "query", "done"}

    def _execute_statements(
        self,
        statements: tuple[_ExpandedStatement, ...],
        *,
        placement_facts: BatchPlacementFacts,
    ) -> tuple[tuple[StatementResult, ...], tuple[EditOp, ...], tuple[CompactDiagnostic, ...]]:
        executed: list[StatementResult] = []
        landed_ops: list[EditOp] = []
        diagnostics: list[CompactDiagnostic] = []
        for item in statements:
            statement = self._resolve_statement(item, placement_facts=placement_facts)
            dep_cause = self._dependency_cause(statement)
            if statement.diagnostics:
                result = StatementResult(
                    statement_index=statement.statement_index,
                    source=statement.source,
                    ok=statement.ok,
                    landed=getattr(statement, "landed", False),
                    op_kind=statement.op_kind,
                    diagnostics=statement.diagnostics,
                    detail=dict(statement.detail),
                    dependency_cause=dep_cause,
                )
                executed.append(result)
                diagnostics.extend(statement.diagnostics)
                continue

            op, op_diagnostics = self._lower_statement_op(statement)
            if op_diagnostics:
                target_name = statement.detail.get("target_name")
                if statement.op_kind == "node_call" and isinstance(target_name, str):
                    self._mark_name_unbound(target_name)
                failed = StatementResult(
                    statement_index=statement.statement_index,
                    source=statement.source,
                    ok=False,
                    landed=False,
                    op_kind=statement.op_kind,
                    diagnostics=statement.diagnostics + tuple(op_diagnostics),
                    detail=dict(statement.detail),
                    dependency_cause=dep_cause,
                )
                executed.append(failed)
                diagnostics.extend(op_diagnostics)
                continue

            detail = dict(statement.detail)
            if op is None:
                executed.append(
                    StatementResult(
                        statement_index=statement.statement_index,
                        source=statement.source,
                        ok=statement.ok,
                        landed=False,
                        op_kind=statement.op_kind,
                        diagnostics=statement.diagnostics,
                        detail=detail,
                        dependency_cause=dep_cause,
                    )
                )
                continue

            detail["edit_op"] = op
            applied = apply_delta(
                self.working_ui,
                (op,),
                schema_provider=self.schema_provider,
            )
            if not applied.ok or applied.candidate is None:
                if isinstance(op, AddNodeOp):
                    target_name = detail.get("target_name")
                    if isinstance(target_name, str):
                        self._mark_name_unbound(target_name)
                issue_diagnostics = tuple(self._compact_port_issue(issue) for issue in applied.diagnostics)
                executed.append(
                    StatementResult(
                        statement_index=statement.statement_index,
                        source=statement.source,
                        ok=False,
                        landed=False,
                        op_kind=statement.op_kind,
                        diagnostics=statement.diagnostics + issue_diagnostics,
                        detail=detail,
                        dependency_cause=dep_cause,
                    )
                )
                diagnostics.extend(issue_diagnostics)
                continue

            self.working_ui = deepcopy(applied.candidate)
            self.ledger = EditLedger.ingest(self.working_ui)

            # Propagate assigned uid/node_id back into AddNodeOp for canonical
            # persistence downstream.
            landed_op = op
            if isinstance(op, AddNodeOp):
                resolved = applied.resolved_ops[0][1] if applied.resolved_ops else None
                minted_uid = getattr(resolved, "uid", None)
                minted_node_id = getattr(resolved, "node_id", None)
                if isinstance(minted_uid, str) and minted_node_id is not None:
                    landed_op = AddNodeOp(
                        op=op.op,
                        scope_path=op.scope_path,
                        class_type=op.class_type,
                        fields=dict(op.fields),
                        inputs=dict(op.inputs),
                        anchor=op.anchor,
                        uid=minted_uid,
                        node_id=str(minted_node_id),
                    )

            self.landed_ops.append(landed_op)
            landed_ops.append(landed_op)
            touched_uids, touched_node_ids = self._collect_touched_nodes((landed_op,))
            self.touched_uids.update(touched_uids)
            self.touched_node_ids.update(touched_node_ids)

            if isinstance(op, AddNodeOp):
                target_name = detail.get("target_name")
                resolved = applied.resolved_ops[0][1] if applied.resolved_ops else None
                minted_uid = getattr(resolved, "uid", None)
                minted_scope_path = getattr(resolved, "scope_path", None)
                if isinstance(target_name, str) and isinstance(minted_uid, str) and isinstance(minted_scope_path, str):
                    self._bind_graph_name(target_name, minted_uid)
                    detail["minted_uid"] = minted_uid
                    detail["minted_scope_path"] = minted_scope_path

            # Merge apply-level diagnostics (e.g., splice_anchor_no_group info) into
            # statement diagnostics so they are visible to callers even on success.
            # Only error/warning apply diagnostics affect batch-level ok; info-severity
            # diagnostics (e.g., add_node_applied, add_node_group_growth) are kept
            # at the statement level only to avoid false-positive batch failures.
            apply_diagnostics = tuple(
                self._compact_port_issue(issue) for issue in applied.diagnostics
            )
            merged_diagnostics = statement.diagnostics + apply_diagnostics
            diagnostics.extend(
                d for d in apply_diagnostics if d.severity in ("error", "warning")
            )

            executed.append(
                StatementResult(
                    statement_index=statement.statement_index,
                    source=statement.source,
                    ok=statement.ok,
                    landed=True,
                    op_kind=statement.op_kind,
                    diagnostics=merged_diagnostics,
                    detail=detail,
                    touched_uids=tuple(touched_uids),
                    dependency_cause=dep_cause,
                )
            )
        return tuple(executed), tuple(landed_ops), tuple(diagnostics)

    def _lower_statement_op(
        self,
        statement: StatementResult,
    ) -> tuple[EditOp | None, tuple[CompactDiagnostic, ...]]:
        op_kind = statement.op_kind
        if op_kind in {None, "done", "query"}:
            return None, ()

        if op_kind == "node_call":
            resolved_call = statement.detail.get("resolved_add_node")
            if not isinstance(resolved_call, _ResolvedAddNodeCall):
                return None, (
                    _diag("missing_resolved_add_node", "Add-node statement was missing its resolved node-call payload.", severity="error"),
                )
            return (
                AddNodeOp(
                    op="add_node",
                    scope_path=resolved_call.scope_path,
                    class_type=resolved_call.class_type,
                    fields=dict(resolved_call.fields),
                    inputs=dict(resolved_call.inputs),
                    anchor=resolved_call.anchor,
                    uid=getattr(resolved_call, "uid", None),
                    node_id=getattr(resolved_call, "node_id", None),
                ),
                (),
            )

        if op_kind == "remove_node":
            node_ref = statement.detail.get("resolved_node")
            if not isinstance(node_ref, _ResolvedGraphName):
                return None, (_diag("missing_resolved_node", "Delete statement was missing its resolved node.", severity="error"),)
            immutable = self._original_virtual_mutation_diagnostics(node_ref, action="delete")
            if immutable:
                return None, immutable
            return RemoveNodeOp(op="remove_node", target=NodeTarget(node_ref.scope_path, node_ref.uid)), ()

        target = statement.detail.get("resolved_target")
        if not isinstance(target, _ResolvedTargetField):
            return None, (
                _diag("missing_resolved_target", "Assignment statement was missing its resolved target.", severity="error"),
            )

        immutable = self._original_virtual_mutation_diagnostics(target.node, action="mutate")
        if immutable:
            return None, immutable

        node_target = NodeTarget(target.node.scope_path, target.node.uid)
        field_target = NodeFieldTarget(target.node.scope_path, target.node.uid, target.field_name)
        ast_node = statement.detail.get("ast_node")
        constant_env = MappingProxyType(dict(statement.detail.get("constant_env", {})))
        assign_node = ast_node if isinstance(ast_node, ast.Assign) else None
        rhs = assign_node.value if assign_node is not None else None

        if op_kind == "remove_link":
            return (
                RemoveLinkOp(
                    op="remove_link",
                    target=LinkTargetRef(target.node.scope_path, target.node.uid, target.field_name),
                ),
                (),
            )
        if op_kind == "upsert_link":
            endpoint = statement.detail.get("resolved_endpoint")
            if not isinstance(endpoint, _ResolvedOutputEndpoint):
                return None, (
                    _diag("missing_resolved_endpoint", "Link assignment was missing its resolved source endpoint.", severity="error"),
                )
            source_slot: str | int = endpoint.slot_name if endpoint.slot_index is None else endpoint.slot_name
            return (
                UpsertLinkOp(
                    op="upsert_link",
                    source=LinkSourceRef(endpoint.node.scope_path, endpoint.node.uid, source_slot),
                    target=LinkTargetRef(target.node.scope_path, target.node.uid, target.field_name),
                ),
                (),
            )
        if op_kind == "set_mode":
            if rhs is None:
                return None, (
                    _diag("missing_mode_value", "Mode assignment was missing its right-hand side.", severity="error"),
                )
            mode_value, mode_issues = self._coerce_mode_value(rhs, env=constant_env)
            if mode_issues:
                return None, mode_issues
            assert mode_value is not None
            return SetModeOp(op="set_mode", target=node_target, mode=mode_value), ()

        if rhs is None:
            return None, (
                _diag("missing_literal_value", "Field assignment was missing its right-hand side.", severity="error"),
            )
        literal_value, literal_issue = _fold_constant(rhs, env=constant_env)
        if literal_issue is not None:
            return None, (literal_issue,)
        return SetNodeFieldOp(op="set_node_field", target=field_target, value=literal_value), ()

    def _coerce_mode_value(
        self,
        value: ast.expr,
        *,
        env: Mapping[str, Any],
    ) -> tuple[int | None, tuple[CompactDiagnostic, ...]]:
        literal_value, diagnostic = _fold_constant(value, env=env)
        if diagnostic is not None:
            return None, (diagnostic,)
        if isinstance(literal_value, str):
            mode = _MODE_LABEL_TO_VALUE.get(literal_value.strip().lower())
            if mode is None:
                return None, (
                    _diag(
                        "unknown_mode_label",
                        f"Unknown mode label {literal_value!r}. Expected one of: {', '.join(sorted(_MODE_LABEL_TO_VALUE))}.",
                        severity="error",
                        detail={"value": literal_value},
                    ),
                )
            return mode, ()
        if isinstance(literal_value, bool) or not isinstance(literal_value, int) or literal_value not in MODE_LABELS:
            return None, (
                _diag(
                    "invalid_mode_value",
                    "Mode assignments must use 0, 2, 4 or their MODE_LABELS-derived labels.",
                    severity="error",
                    detail={"value": literal_value},
                ),
            )
        return literal_value, ()

    def _original_virtual_mutation_diagnostics(
        self,
        node_ref: _ResolvedGraphName,
        *,
        action: str,
    ) -> tuple[CompactDiagnostic, ...]:
        original_node = self.original_ledger.resolve_node(node_ref.scope_path, node_ref.uid)
        if original_node is None:
            return ()
        class_type = str(original_node.get("type") or original_node.get("class_type") or "")
        if class_type not in HELPER_NODE_TYPES:
            return ()
        return (
            _diag(
                "original_virtual_node_immutable",
                f"Original virtual substrate node {node_ref.name!r} ({class_type}) cannot be {action}d in M1.",
                severity="error",
                detail={
                    "name": node_ref.name,
                    "uid": node_ref.uid,
                    "scope_path": node_ref.scope_path,
                    "class_type": class_type,
                    "action": action,
                },
            ),
        )

    def _collect_touched_nodes(
        self,
        ops: tuple[EditOp, ...],
    ) -> tuple[set[str], set[str]]:
        touched_uids: set[str] = set()
        touched_node_ids: set[str] = set()
        for op in ops:
            for scope_path, uid in _uids_for_op(op):
                touched_uids.add(self.ledger.qualified_uid(scope_path, uid))
                node = self.ledger.resolve_node(scope_path, uid)
                if node is None:
                    continue
                node_id = node.get("id")
                if node_id is not None:
                    touched_node_ids.add(str(node_id))
        return touched_uids, touched_node_ids
