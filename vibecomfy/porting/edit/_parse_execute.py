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
        """Apply one Python batch through ``interpret(pre, batch)``.

        Mutation authority is the immutable interpreter.  ``working_ui`` is
        only an emit-side projection of the accepted Δ.  Query statements
        (search / python / tools) are overlaid after interpret so the agent
        still sees typed catalog results.
        """
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
        from vibecomfy.porting.edit.interpret import interpret

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
        snapshot = self._snapshot_mutable_state()
        try:
            if self.workflow is None:
                self.workflow = self._workflow_from_ui(self.original_ui)
            pre_ir = _cow_workflow_copy(self.workflow)
            cas_old = self._cas_snapshot(pre_ir)
            interpreted = interpret(
                pre_ir,
                code,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
                cas_old=cas_old,
                name_hints=self._transient_name_index,
            )
            statement_results = [
                self._statement_result_from_outcome(outcome)
                for outcome in interpreted.statements
            ]
            statement_results = self._overlay_query_results(
                parsed.expanded, statement_results
            )
            if interpreted.landed_ops:
                self.workflow = interpreted.workflow
                if getattr(self, "history", None) is None:
                    self.history = []
                self.history.append((pre_ir, code))
                self.working_ui, project_diags = self._project_ops_onto_ui_with_diagnostics(
                    self.working_ui, interpreted.landed_ops
                )
                if project_diags:
                    statement_results = self._merge_project_diagnostics(
                        statement_results, project_diags
                    )
                self.ledger = EditLedger.ingest(self.working_ui)
                self.landed_ops.extend(interpreted.landed_ops)
                for op in interpreted.landed_ops:
                    touched_uids, touched_node_ids = self._collect_touched_nodes((op,))
                    self.touched_uids.update(touched_uids)
                    self.touched_node_ids.update(touched_node_ids)
                for outcome in interpreted.statements:
                    if outcome.status == "applied" and outcome.op_kind == "node_call":
                        name = outcome.detail.get("target_name")
                        uid = outcome.detail.get("minted_uid")
                        if isinstance(name, str) and isinstance(uid, str):
                            self._register_transient_name(name, uid)
                    if outcome.status == "rejected" and outcome.op_kind == "node_call":
                        name = outcome.detail.get("target_name")
                        if isinstance(name, str):
                            self._mark_name_unbound(name)
            statement_results = self._enrich_statement_results(statement_results)
            field_changes, statement_results = self._build_field_changes(
                interpreted.landed_ops,
                tuple(statement_results),
            )
            query_diagnostics = tuple(
                diagnostic
                for statement in statement_results
                if statement.op_kind in {"query", "done"}
                for diagnostic in statement.diagnostics
                if diagnostic.severity in {"error", "warning"}
            )
            diagnostics = interpreted.diagnostics + query_diagnostics
            return BatchResult(
                ok=interpreted.ok and all(statement.ok for statement in statement_results),
                statements=statement_results,
                diagnostics=diagnostics,
                landed_ops=interpreted.landed_ops,
                field_changes=field_changes,
            )
        except Exception:
            self._restore_snapshot(snapshot)
            raise

    @staticmethod
    def _statement_result_from_outcome(outcome: Any) -> StatementResult:
        status = getattr(outcome, "status", None)
        reason = getattr(outcome, "reason", None)
        detail = dict(getattr(outcome, "detail", {}) or {})
        if status:
            detail.setdefault("status", status)
        if reason:
            detail.setdefault("reason", reason)
        if getattr(outcome, "op", None) is not None:
            detail.setdefault("edit_op", outcome.op)
        return StatementResult(
            statement_index=outcome.statement_index,
            source=outcome.source,
            ok=status != "rejected",
            landed=status == "applied" or (
                status == "skipped" and reason == "cas_unchanged"
            ),
            op_kind=outcome.op_kind,
            diagnostics=tuple(getattr(outcome, "diagnostics", ()) or ()),
            detail=detail,
            status=status,
            reason=reason,
        )

    def _overlay_query_results(
        self,
        expanded: tuple[_ExpandedStatement, ...],
        results: list[StatementResult] | tuple[StatementResult, ...],
    ) -> list[StatementResult]:
        """Run search/python/tool statements interpret skipped as non-edits."""
        by_index = {item.statement_index: item for item in expanded}
        overlaid: list[StatementResult] = []
        for result in results:
            if result.op_kind == "done":
                overlaid.append(result)
                continue
            if result.op_kind != "query" or result.landed:
                overlaid.append(result)
                continue
            item = by_index.get(result.statement_index)
            node = getattr(item, "node", None) if item is not None else None
            call = getattr(node, "value", None) if isinstance(node, ast.Expr) else None
            if not isinstance(call, ast.Call):
                overlaid.append(result)
                continue
            query = self._resolve_query_statement(
                statement_index=item.statement_index,
                source=item.source,
                call=call,
                env=item.env,
            )
            status = "skipped" if query.ok else "rejected"
            reason = (
                None
                if query.ok
                else (query.diagnostics[0].code if query.diagnostics else "query_failed")
            )
            overlaid.append(
                StatementResult(
                    statement_index=query.statement_index,
                    source=query.source,
                    ok=query.ok,
                    landed=False,
                    op_kind=query.op_kind,
                    diagnostics=query.diagnostics,
                    detail=dict(query.detail),
                    touched_uids=query.touched_uids,
                    dependency_cause=query.dependency_cause,
                    teaching_hint=query.teaching_hint,
                    status=status,
                    reason=reason,
                )
            )
        return overlaid

    def _enrich_statement_results(
        self,
        results: list[StatementResult] | tuple[StatementResult, ...],
    ) -> list[StatementResult]:
        enriched: list[StatementResult] = []
        for result in results:
            op = result.detail.get("edit_op") if isinstance(result.detail, dict) else None
            touched = result.touched_uids
            if result.landed and op is not None:
                uids, _ = self._collect_touched_nodes((op,))
                if uids:
                    touched = tuple(uids)
            cause = result.dependency_cause or self._dependency_cause(result)
            hint = result.teaching_hint
            if hint is None:
                for diagnostic in result.diagnostics:
                    if diagnostic.teaching_hint:
                        hint = diagnostic.teaching_hint
                        break
            enriched.append(
                StatementResult(
                    statement_index=result.statement_index,
                    source=result.source,
                    ok=result.ok,
                    landed=result.landed,
                    op_kind=result.op_kind,
                    diagnostics=result.diagnostics,
                    detail=dict(result.detail),
                    touched_uids=touched,
                    dependency_cause=cause,
                    teaching_hint=hint,
                    status=result.status,
                    reason=result.reason,
                )
            )
        return enriched

    def _merge_project_diagnostics(
        self,
        results: list[StatementResult],
        project_diags: tuple[Any, ...],
    ) -> list[StatementResult]:
        extras = [
            diagnostic
            for diagnostic in project_diags
            if getattr(diagnostic, "code", "") == "splice_anchor_no_group"
        ]
        if not extras:
            return results
        merged: list[StatementResult] = []
        attached = False
        for result in results:
            if not attached and result.op_kind == "node_call" and result.landed:
                merged.append(
                    StatementResult(
                        statement_index=result.statement_index,
                        source=result.source,
                        ok=result.ok,
                        landed=result.landed,
                        op_kind=result.op_kind,
                        diagnostics=result.diagnostics + tuple(extras),
                        detail=dict(result.detail),
                        touched_uids=result.touched_uids,
                        dependency_cause=result.dependency_cause,
                        teaching_hint=result.teaching_hint,
                        status=result.status,
                        reason=result.reason,
                    )
                )
                attached = True
            else:
                merged.append(result)
        return merged

    def _snapshot_mutable_state(self) -> dict:
        return {
            "working_ui": deepcopy(self.working_ui),
            "landed_ops": list(self.landed_ops),
            "touched_uids": set(self.touched_uids),
            "touched_node_ids": set(self.touched_node_ids),
            "uid_by_name": None,
            "name_by_uid": None,
            "unbound_names": set(self.unbound_names),
            "value_default_context": self.value_default_context,
            "workflow": self.workflow,
            "history": list(getattr(self, "history", [])),
            "resolved_ops": list(self.resolved_ops),
            "render_count": self.render_count,
            "last_rendered_source": self.last_rendered_source,
            "last_rendered_workflow": self.last_rendered_workflow,
            "last_render_diagnostics": self.last_render_diagnostics,
        }

    def _restore_snapshot(self, snapshot: dict) -> None:
        self.working_ui = deepcopy(snapshot["working_ui"])
        self.ledger = EditLedger.ingest(self.working_ui)
        self.landed_ops = list(snapshot["landed_ops"])
        self.touched_uids = set(snapshot["touched_uids"])
        self.touched_node_ids = set(snapshot["touched_node_ids"])
        # Batch 4: name locks are derived (no session state to restore).
        self.unbound_names = set(snapshot["unbound_names"])
        self.value_default_context = snapshot["value_default_context"]
        self.workflow = snapshot["workflow"]
        if "history" in snapshot:
            self.history = list(snapshot["history"])
        self.resolved_ops = list(snapshot["resolved_ops"])
        if "render_count" in snapshot:
            self.render_count = snapshot["render_count"]
            self.last_rendered_source = snapshot["last_rendered_source"]
            self.last_rendered_workflow = snapshot["last_rendered_workflow"]
            self.last_render_diagnostics = snapshot["last_render_diagnostics"]

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
                value_default_context=self.value_default_context,
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
            # Accumulate resolved-op attribution for the emit-boundary guard
            # (guard_emit), mirroring the delta path's emit_guard_resolved_ops.
            if applied.resolved_ops:
                self.resolved_ops.extend(applied.resolved_ops)

            # Propagate assigned uid/node_id back into AddNodeOp for canonical
            # persistence downstream.
            landed_op = op
            if isinstance(op, AddNodeOp):
                resolved = applied.resolved_ops[0][1] if applied.resolved_ops else None
                minted_uid = getattr(resolved, "uid", None)
                minted_node_id = getattr(resolved, "node_id", None)
                if isinstance(minted_uid, str) and minted_node_id is not None:
                    effective_op = getattr(resolved, "op", op)
                    landed_op = AddNodeOp(
                        op=effective_op.op,
                        scope_path=effective_op.scope_path,
                        class_type=effective_op.class_type,
                        fields=dict(effective_op.fields),
                        inputs=dict(effective_op.inputs),
                        anchor=effective_op.anchor,
                        uid=minted_uid,
                        node_id=str(minted_node_id),
                    )
                    receipts = tuple(getattr(resolved, "value_default_receipts", ()) or ())
                    if self.value_default_context is not None and receipts:
                        self.value_default_context = self.value_default_context.protect_node(
                            scope_path=effective_op.scope_path,
                            uid=minted_uid,
                            class_type=effective_op.class_type,
                            fields=tuple(receipt.canonical_field for receipt in receipts),
                            source_instance_ids=tuple(
                                receipt.source_instance_id
                                for receipt in receipts
                                if receipt.source_instance_id
                            ),
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
                if isinstance(minted_uid, str) and isinstance(minted_scope_path, str):
                    # Batch 4 (Law 5): no session name locks and no binding
                    # write — the emitted name is a pure function of
                    # (class_type, uid-order).  Only a TRANSIENT within-batch
                    # registration is recorded so later statements in the
                    # same batch can reference the minted node.
                    self._register_transient_name(target_name, minted_uid)
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
