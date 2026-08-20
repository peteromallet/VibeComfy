from __future__ import annotations

import ast
from typing import Any

from vibecomfy.porting.edit.ops import EditOp
from vibecomfy.porting.edit._session_types import (
    BatchResult,
    CompactDiagnostic,
    StatementResult,
    _ExpandedStatement,
    _diag,
)
from vibecomfy.porting.edit._parse import (
    _parse_and_validate_batch,
)
from vibecomfy.porting.edit._ir_utils import _uids_for_op


_IDENTITY_DIAGNOSTIC_CODES = frozenset(
    {
        "unknown_graph_name",
        "unknown_source_name",
        "unknown_target_name",
        "unbound_graph_name",
        "stale_graph_name",
    }
)


class _ParseExecuteMixin:

    def apply_batch(self, code: str) -> BatchResult:
        """Apply one Python batch through ``interpret(pre, batch)``.

        Mutation authority is the immutable interpreter.  The retained IR
        is the only session graph.  Query statements (search / python /
        tools) are overlaid after interpret so the agent still sees typed
        catalog results.
        """
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
        from vibecomfy.porting.edit._interpret import interpret

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
                raise RuntimeError("EditSession.apply_batch requires a retained IR")
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
            identity_diagnostics = tuple(
                diagnostic
                for outcome in interpreted.statements
                for diagnostic in tuple(getattr(outcome, "diagnostics", ()) or ())
                if getattr(diagnostic, "code", "") in _IDENTITY_DIAGNOSTIC_CODES
            )
            if identity_diagnostics:
                names = sorted(
                    {
                        str(diagnostic.detail.get("name"))
                        for diagnostic in identity_diagnostics
                        if diagnostic.detail.get("name") is not None
                    }
                )
                rejection = _diag(
                    "batch_identity_rejected",
                    (
                        "Batch rejected before commit because it references "
                        "unbound or stale graph names: "
                        + (", ".join(repr(name) for name in names) or "unknown")
                        + ". Re-render and use only names or uids present in the "
                        "current graph."
                    ),
                    severity="error",
                    detail={"names": names, "atomic": True, "retryable": True},
                )
                statement_results = self._enrich_statement_results(statement_results)
                for statement in statement_results:
                    if statement.landed:
                        statement.ok = False
                        statement.landed = False
                        statement.status = "rejected"
                        statement.reason = "batch_identity_rejected"
                        statement.diagnostics = statement.diagnostics + (rejection,)
                return BatchResult(
                    ok=False,
                    statements=tuple(statement_results),
                    diagnostics=interpreted.diagnostics + identity_diagnostics + (rejection,),
                    landed_ops=(),
                    field_changes=(),
                    apply_eligible=False,
                )
            apply_gate_eligible = True
            if interpreted.ok and interpreted.landed_ops:
                from vibecomfy.porting.edit.apply_gate import verify_apply

                gate = verify_apply(
                    pre_ir,
                    interpreted.workflow,
                    delta=code,
                    landed_ops=interpreted.landed_ops,
                    schema_provider=self.schema_provider,
                )
                apply_gate_eligible = gate.apply_eligible
                if not gate.ok:
                    rejected = tuple(
                        StatementResult(
                            statement_index=item.statement_index,
                            source=item.source,
                            ok=False,
                            landed=False,
                            op_kind=item.op_kind,
                            diagnostics=item.diagnostics + gate.diagnostics,
                            detail=dict(item.detail),
                            touched_uids=item.touched_uids,
                            dependency_cause=item.dependency_cause,
                            teaching_hint=item.teaching_hint,
                            status="rejected",
                            reason=gate.reason or "apply_gate_rejected",
                        )
                        if item.landed
                        else item
                        for item in statement_results
                    )
                    return BatchResult(
                        ok=False,
                        statements=rejected,
                        diagnostics=interpreted.diagnostics + gate.diagnostics,
                        landed_ops=(),
                        apply_eligible=False,
                    )
            if interpreted.landed_ops:
                self.workflow = interpreted.workflow
                if getattr(self, "history", None) is None:
                    self.history = []
                # The accepted batch IS the Δ.  Each history entry records
                # (wf_i, source, landed_ops) — the Python-surface source AND
                # the typed ops the grammar yields are the same batch value.
                self.history.append(
                    (pre_ir, code, tuple(interpreted.landed_ops))
                )
                self.landed_ops.extend(interpreted.landed_ops)
                self.resolved_ops = []
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
            batch_ok = interpreted.ok and all(
                statement.ok for statement in statement_results
            )
            return BatchResult(
                ok=batch_ok,
                statements=statement_results,
                diagnostics=diagnostics,
                landed_ops=interpreted.landed_ops,
                field_changes=field_changes,
                apply_eligible=batch_ok and bool(interpreted.landed_ops) and apply_gate_eligible,
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
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        workflow = getattr(self, "workflow", None)
        return {
            "landed_ops": list(self.landed_ops),
            "touched_uids": set(self.touched_uids),
            "touched_node_ids": set(self.touched_node_ids),
            "uid_by_name": None,
            "name_by_uid": None,
            "unbound_names": set(self.unbound_names),
            "value_default_context": self.value_default_context,
            "workflow": (
                _cow_workflow_copy(workflow) if workflow is not None else None
            ),
            "history": list(getattr(self, "history", [])),
            "resolved_ops": list(self.resolved_ops),
            "render_count": self.render_count,
            "last_rendered_source": self.last_rendered_source,
            "last_rendered_workflow": self.last_rendered_workflow,
            "last_render_diagnostics": self.last_render_diagnostics,
        }

    def _restore_snapshot(self, snapshot: dict) -> None:
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

    def _collect_touched_nodes(
        self,
        ops: tuple[EditOp, ...],
    ) -> tuple[set[str], set[str]]:
        touched_uids: set[str] = set()
        touched_node_ids: set[str] = set()
        workflow = getattr(self, "workflow", None)
        uid_to_id = {}
        if workflow is not None:
            for node in workflow.nodes.values():
                uid = str(getattr(node, "uid", "") or "")
                if uid:
                    uid_to_id[uid] = str(getattr(node, "id", "") or "")
        for op in ops:
            for _scope_path, uid in _uids_for_op(op):
                touched_uids.add(uid)
                node_id = uid_to_id.get(uid)
                if node_id:
                    touched_node_ids.add(node_id)
        return touched_uids, touched_node_ids
