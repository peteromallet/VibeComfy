"""Pure immutable interpreter for the Python edit surface.

``interpret(pre, batch)`` is the Law 2 engine: same ``(pre, batch)`` yields
the same post-IR, the pre-IR is never mutated, and a batch is transactional
(all landed edits apply, or the pre-IR is returned with per-statement
outcomes).  Session history entries are ``(wf_i, Δ_i, landed_ops)`` triples
where ``Δ_i`` is the accepted batch source of this function.
"""

from __future__ import annotations

import ast
import keyword
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence

from vibecomfy.porting.edit._ir_utils import (
    _canonical_input_name_for_class,
    _cow_workflow_copy,
    _input_spec_for_field,
    _mint_ir_uid,
    apply_edit_cow,
)
from vibecomfy.porting.edit._parse import (
    _channel_side_unpack,
    _fold_constant,
    _is_graph_reference_value,
    _parse_and_validate_batch,
    _resolve_vibecomfy_constructor,
)
from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    StatementResult,
    _ExpandedStatement,
    _diag,
)
from vibecomfy.porting.edit.validate import validate_literal_value as _validate_literal_value
from vibecomfy.porting.edit.editable_surface import (
    editable_surface_for,
    is_positional_alias,
    _is_link_value,
)
from vibecomfy.porting.edit.grammar import op_kind_for_assignment
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    AnchorRef,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    SubgraphInterfaceOp,
    UpsertLinkOp,
)
from vibecomfy.porting.edit.constants import (
    HELPER_NODE_TYPES,
    MODE_LABELS,
)
from vibecomfy.identity.codec import (
    _BUILTIN_NAMES,
    encode_slot_names,
    to_python_identifier,
    to_raw_name,
)
from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names
from vibecomfy.porting.emit.emit_prepare import _agent_edit_output_ports
from vibecomfy.porting.edit._resolve import (
    _EXEC_CLASS_TYPE,
    _exec_semantic_slot_name,
    _infer_exec_io,
    _normalize_exec_io,
)
from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget, input_spec_is_socket_only
from vibecomfy.schema import get_schema_provider, schema_for, socket_types_compatible
from vibecomfy.workflow import VibeWorkflow, mode_to_litegraph


StatementStatus = Literal["applied", "rejected", "skipped"]

_UID_COMMENT = re.compile(r"#\s*uid:([^\s]+)")
_TYPED_PORT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)_(\d+)$")
_SLOT_COMMENT = re.compile(
    r"(\w+)(?:='([^']*)')?(?:\s+(?:known|provisional|unknown))?"
)
_MODE_LABEL_TO_VALUE = {str(label): mode for mode, label in MODE_LABELS.items()}
_PLACEMENT_KWARGS = frozenset({"near", "relation", "group"})
_RAW_COORDINATE_KWARGS = frozenset({"pos", "position", "coords", "x", "y"})


@dataclass(frozen=True, slots=True)
class StatementOutcome:
    """Typed per-statement result of ``interpret``."""

    statement_index: int
    source: str
    status: StatementStatus
    reason: str | None = None
    op_kind: str | None = None
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    op: EditOp | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InterpretationResult:
    """New IR plus the per-statement ledger for one batch.

    ``workflow`` is always a distinct object from the pre-IR.  ``ok`` is true
    only when every edit statement applied (or was a non-edit skip) and no
    error diagnostic was produced.  A transactional rollback leaves
    ``workflow`` equal (by value) to a copy of the pre-IR and marks previously
    applied edits as rejected.
    """

    workflow: VibeWorkflow
    statements: tuple[StatementOutcome, ...]
    ok: bool
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    landed_ops: tuple[EditOp, ...] = ()
    preflight_ok: bool = True


def interpret(
    pre_workflow: VibeWorkflow,
    batch_source: str | Sequence[EditOp],
    *,
    schema_provider: Any | None = None,
    max_batch_bytes: int = 1_000_000,
    max_statements: int = 10_000,
    max_expanded_statements: int = 20_000,
    max_for_iterations: int = 100,
    cas_old: Mapping[tuple[str, str], Any] | None = None,
    name_hints: Mapping[str, str] | None = None,
) -> InterpretationResult:
    """Interpret ``batch_source`` against ``pre_workflow``, returning a NEW IR.

    Pure: the input workflow is never mutated.  ``batch_source`` is either
    Python surface text or an already-lowered op sequence (Law 3).
    """
    if not isinstance(pre_workflow, VibeWorkflow):
        raise TypeError(
            f"interpret requires VibeWorkflow, got {type(pre_workflow).__name__}"
        )
    provider = schema_provider or get_schema_provider("auto")
    if not isinstance(batch_source, str):
        return _interpret_ops(pre_workflow, tuple(batch_source), schema_provider=provider)
    return _interpret_source(
        pre_workflow,
        batch_source,
        schema_provider=provider,
        max_batch_bytes=max_batch_bytes,
        max_statements=max_statements,
        max_expanded_statements=max_expanded_statements,
        max_for_iterations=max_for_iterations,
        cas_old=cas_old,
        name_hints=name_hints,
    )


def _interpret_source(
    pre_workflow: VibeWorkflow,
    source: str,
    *,
    schema_provider: Any,
    max_batch_bytes: int,
    max_statements: int,
    max_expanded_statements: int,
    max_for_iterations: int,
    cas_old: Mapping[tuple[str, str], Any] | None,
    name_hints: Mapping[str, str] | None,
) -> InterpretationResult:
    parsed = _parse_and_validate_batch(
        source,
        max_batch_bytes=max_batch_bytes,
        max_statements=max_statements,
        max_expanded_statements=max_expanded_statements,
        max_for_iterations=max_for_iterations,
    )
    if parsed.diagnostics:
        return InterpretationResult(
            workflow=_cow_workflow_copy(pre_workflow),
            statements=_outcomes_from_parse(parsed.statements, parsed.diagnostics),
            ok=False,
            diagnostics=parsed.diagnostics,
            landed_ops=(),
            preflight_ok=False,
        )
    runner = _InterpretRunner(
        pre_workflow,
        schema_provider=schema_provider,
        cas_old=cas_old,
        source=source,
        name_hints=name_hints,
    )
    return runner.run(parsed.expanded)


def _interpret_ops(
    pre_workflow: VibeWorkflow,
    ops: tuple[EditOp, ...],
    *,
    schema_provider: Any,
) -> InterpretationResult:
    post = _cow_workflow_copy(pre_workflow)
    statements: list[StatementOutcome] = []
    landed: list[EditOp] = []
    diagnostics: list[CompactDiagnostic] = []
    for index, op in enumerate(ops):
        try:
            # Typed deltas bypass the Python parser, so run the shared
            # sequential validator before each COW step.  This preserves
            # add-then-link batches while keeping invalid batches atomic.
            if not _op_has_scoped_target(op):
                from vibecomfy.porting.edit._op_validate import _validate_one

                _validate_one(post, op, schema_provider)
            # Typed-op callers carry their channel contract in the op (and,
            # for AddNodeOp, its explicit widget_field_names), while Python
            # source batches are replayed from source by apply_gate. Keep the
            # typed-op interpreter aligned with typed validation here.
            before = post
            post = apply_edit_cow(post, op, schema_provider=schema_provider)
            diagnostics.extend(_apply_diagnostics(before, post, op))
        except Exception as exc:
            code = getattr(exc, "code", "apply_failed")
            failed = StatementOutcome(
                statement_index=index,
                source=type(op).__name__,
                status="rejected",
                reason=code,
                op_kind=getattr(op, "op", type(op).__name__),
                diagnostics=(
                    _diag(code, str(exc), severity="error"),
                ),
                op=op,
            )
            rolled = []
            rollback_diag = _diag(
                "batch_transaction_rolled_back",
                "A later edit statement failed, so all edits from this batch were rolled back.",
                severity="error",
            )
            for prior in statements:
                if prior.status == "applied":
                    rolled.append(
                        StatementOutcome(
                            statement_index=prior.statement_index,
                            source=prior.source,
                            status="rejected",
                            reason="batch_transaction_rolled_back",
                            op_kind=prior.op_kind,
                            diagnostics=prior.diagnostics + (rollback_diag,),
                            op=prior.op,
                            detail=dict(prior.detail),
                        )
                    )
                else:
                    rolled.append(prior)
            rolled.append(failed)
            return InterpretationResult(
                workflow=_cow_workflow_copy(pre_workflow),
                statements=tuple(rolled),
                ok=False,
                diagnostics=tuple(diagnostics) + (rollback_diag, *failed.diagnostics),
                landed_ops=(),
            )
        statements.append(
            StatementOutcome(
                statement_index=index,
                source=type(op).__name__,
                status="applied",
                op_kind=getattr(op, "op", type(op).__name__),
                op=op,
            )
        )
        landed.append(op)
    return InterpretationResult(
        workflow=post,
        statements=tuple(statements),
        ok=True,
        diagnostics=tuple(diagnostics),
        landed_ops=tuple(landed),
    )


def _apply_diagnostics(
    before: VibeWorkflow,
    after: VibeWorkflow,
    op: EditOp,
) -> tuple[CompactDiagnostic, ...]:
    """Return informational diagnostics describing COW graph side effects."""
    before_edges = tuple(before.edges)
    after_edges = tuple(after.edges)
    if isinstance(op, AddNodeOp):
        return (
            _diag(
                "add_node_applied",
                "add_node materialized a new LiteGraph node with deterministic ledger ids and placement.",
                severity="info",
            ),
        )
    if isinstance(op, SetNodeFieldOp):
        if any(
            edge.to_input == op.target.field_path and edge not in after_edges
            for edge in before_edges
        ):
            return (
                _diag(
                    "automatic_link_removal",
                    "A literal widget assignment removed the previous incoming link.",
                    severity="info",
                ),
            )
    elif isinstance(op, UpsertLinkOp):
        target_id = next(
            (node.id for node in before.nodes.values() if node.uid == op.target.uid),
            None,
        )
        if any(
            edge.to_node == target_id and edge.to_input == op.target.input_field
            for edge in before_edges
        ):
            return (
                _diag(
                    "upsert_link_replaced_existing",
                    "upsert_link removed the previous incoming link for the target input.",
                    severity="info",
                ),
            )
    elif isinstance(op, RemoveNodeOp):
        removed_node = next(
            (node for node in before.nodes.values() if node.uid == op.target.uid),
            None,
        )
        if removed_node is not None and any(
            edge not in before_edges
            and edge.from_node != removed_node.id
            and edge.to_node != removed_node.id
            for edge in after_edges
        ):
            return (
                _diag(
                    "remove_node_passthrough_rewire",
                    "remove_node rewired the retained passthrough edge.",
                    severity="info",
                ),
            )
    return ()


def _op_has_scoped_target(op: EditOp) -> bool:
    """Whether an op addresses retained subgraph data rather than root IR."""
    scope_path = getattr(op, "scope_path", "")
    if scope_path:
        return True
    for attr in ("target", "source"):
        ref = getattr(op, attr, None)
        if ref is not None and getattr(ref, "scope_path", ""):
            return True
    return False


def _outcomes_from_parse(
    statements: tuple[StatementResult, ...],
    diagnostics: tuple[CompactDiagnostic, ...],
) -> tuple[StatementOutcome, ...]:
    if statements:
        return tuple(
            StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="rejected",
                reason=item.diagnostics[0].code if item.diagnostics else "preflight_failed",
                op_kind=item.op_kind,
                diagnostics=item.diagnostics,
                detail=dict(item.detail),
            )
            for item in statements
        )
    return (
        StatementOutcome(
            statement_index=0,
            source="",
            status="rejected",
            reason=diagnostics[0].code if diagnostics else "preflight_failed",
            diagnostics=diagnostics,
        ),
    )


class _InterpretRunner:
    """Sequential, copy-on-write statement runner over one pre-IR."""

    def __init__(
        self,
        pre_workflow: VibeWorkflow,
        *,
        schema_provider: Any,
        cas_old: Mapping[tuple[str, str], Any] | None,
        source: str = "",
        name_hints: Mapping[str, str] | None = None,
    ) -> None:
        self._pre = pre_workflow
        self.workflow = _cow_workflow_copy(pre_workflow)
        self.schema_provider = schema_provider
        self.cas_old = dict(cas_old or {})
        self._source = source
        self._source_lines = source.splitlines()
        self.unbound: set[str] = set()
        self.transient: dict[str, str] = dict(name_hints or {})
        # Names are uid-anchored for this interpreter/batch.  Once a live
        # binding disappears its spelling is retired rather than reassigned to
        # a different surviving node after class+order renumbering.
        self._retired_name_uids: dict[str, str] = {}
        self._pending_apply_diagnostics: list[CompactDiagnostic] = []
        self._pre_helper_uids = {
            str(node.uid)
            for node in pre_workflow.nodes.values()
            if str(getattr(node, "uid", "") or "")
            and str(node.class_type) in HELPER_NODE_TYPES
        }
        self._refresh_bindings()
        self.placement_facts = None

    def run(self, statements: tuple[_ExpandedStatement, ...]) -> InterpretationResult:
        from vibecomfy.porting.layout.placement import build_batch_placement_facts

        self.placement_facts = build_batch_placement_facts(
            statements,
            graph_name_exists=lambda name: self._resolve_name(name)[0] is not None,
            estimate_add_node_width=lambda _class_type: 210,
        )
        outcomes: list[StatementOutcome] = []
        landed: list[EditOp] = []
        diagnostics: list[CompactDiagnostic] = []
        saw_landed_edit = False
        saw_failed_edit = False
        rollback = False
        for item in statements:
            outcome = self._run_one(item)
            outcomes.append(outcome)
            diagnostics.extend(outcome.diagnostics)
            diagnostics.extend(self._pending_apply_diagnostics)
            self._pending_apply_diagnostics.clear()
            is_edit = outcome.op_kind not in {None, "query", "done", "statement"}
            if outcome.status == "applied" and is_edit:
                saw_landed_edit = True
                if outcome.op is not None:
                    landed.append(outcome.op)
                continue
            if (
                outcome.status == "skipped"
                and outcome.reason == "cas_unchanged"
                and outcome.op is not None
            ):
                landed.append(outcome.op)
                continue
            if outcome.status == "rejected" and is_edit:
                # All-or-nothing commit: keep evaluating later statements so
                # outcomes stay honest, then discard the working IR.
                rollback = True
                saw_failed_edit = True
        if rollback:
            rollback_diag = _diag(
                "batch_transaction_rolled_back",
                "A later edit statement failed, so all edits from this batch were rolled back.",
                severity="error",
            )
            rolled: list[StatementOutcome] = []
            for outcome in outcomes:
                if outcome.status == "applied" and outcome.op_kind not in {None, "query", "done"}:
                    rolled.append(
                        StatementOutcome(
                            statement_index=outcome.statement_index,
                            source=outcome.source,
                            status="rejected",
                            reason="batch_transaction_rolled_back",
                            op_kind=outcome.op_kind,
                            diagnostics=outcome.diagnostics + (rollback_diag,),
                            detail=dict(outcome.detail),
                        )
                    )
                else:
                    rolled.append(outcome)
            return InterpretationResult(
                workflow=_cow_workflow_copy(self._pre),
                statements=tuple(rolled),
                ok=False,
                diagnostics=tuple(diagnostics) + (rollback_diag,),
                landed_ops=(),
            )
        ok = not any(
            outcome.status == "rejected"
            and outcome.op_kind not in {None, "query", "done"}
            for outcome in outcomes
        ) and not any(diag.severity == "error" for diag in diagnostics)
        return InterpretationResult(
            workflow=self.workflow,
            statements=tuple(outcomes),
            ok=ok,
            diagnostics=tuple(
                diag for diag in diagnostics if diag.severity in {"error", "warning"}
            ),
            landed_ops=tuple(landed),
        )

    def _run_one(self, item: _ExpandedStatement) -> StatementOutcome:
        statement = item.node
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call_name = _call_id(statement.value)
            if call_name == "subgraph_interface":
                return self._subgraph_interface(item, statement.value)
            return StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="skipped",
                reason="non_edit",
                op_kind="done" if call_name == "done" else "query",
            )
        if isinstance(statement, ast.Delete):
            return self._delete(item)
        if isinstance(statement, ast.Assign):
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                return self._add_node(item, target.id, statement.value)
            if isinstance(target, ast.Attribute):
                return self._assign_attribute(item, target, statement.value)
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="rejected",
            reason="unsupported_statement",
            op_kind=item.op_kind,
            diagnostics=(
                _diag(
                    "unsupported_statement",
                    "interpret only accepts the designed edit-surface statements.",
                    severity="error",
                ),
            ),
        )

    def _add_node(self, item: _ExpandedStatement, target_name: str, value: ast.expr) -> StatementOutcome:
        if target_name.startswith("__"):
            return self._reject(item, "dunder_name_not_allowed", "node_call")
        if not isinstance(value, ast.Call):
            self.unbound.add(target_name)
            return self._reject(
                item,
                "expression_not_call",
                "node_call",
                "Only node-construction calls may be assigned to graph names.",
            )
        class_type, class_issues = _class_type_from_call(value, item.env)
        if class_issues:
            self.unbound.add(target_name)
            return self._reject_diagnostics(item, "node_call", class_issues)
        fields: dict[str, Any] = {}
        linked: dict[str, LinkSourceRef] = {}
        issues: list[CompactDiagnostic] = []
        # uid comment present ⇒ emit replay of an existing instance.  User
        # add (no uid) still enforces enum/asset bounds.
        reconstructing = bool(
            _uid_from_source(item.source) or self._uid_from_lines(item)
        )
        schema = schema_for(self.schema_provider, class_type)
        if schema is None:
            from vibecomfy.porting.authoring_names import class_type_for_constructor_name
            from vibecomfy.porting.edit._ir_utils import _resolve_class_type_from_alias

            resolved = _resolve_class_type_from_alias(class_type, self.schema_provider)
            if resolved:
                class_type = resolved
                schema = schema_for(self.schema_provider, class_type)
            if schema is None:
                raw_class_type = class_type_for_constructor_name(
                    self.schema_provider, class_type
                )
                if raw_class_type is not None:
                    class_type = raw_class_type
                    schema = schema_for(self.schema_provider, class_type)
        if schema is None and not reconstructing:
            self.unbound.add(target_name)
            return self._reject(
                item,
                "unknown_add_node_class_type",
                "node_call",
                f"Unknown class_type {class_type!r} for add_node.",
            )
        schema_inputs = getattr(schema, "inputs", {}) or {}
        relation: str | None = None
        near_ref: NodeTarget | None = None
        group_title: str | None = None
        widget_field_names: tuple[str, ...] = ()
        emit_order_names: tuple[str, ...] = ()
        exec_io_value: Any = None
        if class_type == _EXEC_CLASS_TYPE:
            for keyword in value.keywords:
                if keyword.arg == "io":
                    exec_io_value, _ = _fold_constant(keyword.value, env=item.env)
                    break
        for keyword in value.keywords:
            if keyword.arg is None:
                side = _channel_side_unpack(keyword, env=item.env)
                if side is not None:
                    widget_field_names, emit_order_names, side_issue = side
                    if side_issue is not None:
                        issues.append(side_issue)
                    continue
                issues.append(
                    _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                )
                continue
            name = keyword.arg
            if name == "relation":
                literal, literal_issue = _fold_constant(keyword.value, env=item.env)
                if literal_issue is not None:
                    issues.append(literal_issue)
                    continue
                if isinstance(literal, str):
                    relation = literal
                continue
            if name == "group":
                literal, literal_issue = _fold_constant(keyword.value, env=item.env)
                if literal_issue is not None:
                    issues.append(literal_issue)
                    continue
                if isinstance(literal, str):
                    group_title = literal
                continue
            if name in _RAW_COORDINATE_KWARGS:
                issues.append(
                    _diag(
                        "raw_coordinate_kwarg_not_allowed",
                        f"Raw coordinate keyword {name!r} is not allowed; use near=/relation=.",
                        severity="error",
                        detail={"keyword": name, "target_name": target_name},
                    )
                )
                continue
            if name == "near":
                if isinstance(keyword.value, ast.Name):
                    near_node, near_issues = self._resolve_name(keyword.value.id)
                    if near_issues:
                        issues.extend(near_issues)
                        continue
                    assert near_node is not None
                    near_ref = NodeTarget("", str(near_node.uid))
                    continue
                endpoint, endpoint_issues = self._resolve_source(keyword.value)
                if endpoint_issues:
                    issues.extend(endpoint_issues)
                    continue
                assert endpoint is not None
                near_ref = NodeTarget(endpoint.scope_path, endpoint.uid)
                continue
            if name in _PLACEMENT_KWARGS:
                continue
            if class_type == _EXEC_CLASS_TYPE:
                name = _exec_semantic_slot_name(
                    class_type, exec_io_value, name, direction="input"
                )
            if _is_graph_reference_value(keyword.value):
                endpoint, endpoint_issues = self._resolve_source(keyword.value)
                if endpoint_issues:
                    issues.extend(endpoint_issues)
                    continue
                assert endpoint is not None
                name = _decode_kwarg_name(
                    name,
                    schema_inputs,
                    class_type,
                    endpoint=endpoint,
                    schema_provider=self.schema_provider,
                )
                linked[name] = endpoint
                continue
            name = _decode_kwarg_name(
                name,
                schema_inputs,
                class_type,
                schema_provider=self.schema_provider,
            )
            literal, literal_issue = _fold_constant(keyword.value, env=item.env)
            if literal_issue is not None:
                issues.append(literal_issue)
                continue
            spec = _input_spec_for_field(schema_inputs, name)
            if input_spec_is_socket_only(spec) and not reconstructing:
                issues.append(
                    _diag(
                        "socket_input_not_literal_widget",
                        f"{class_type}.{name} is an input socket, not a widget; connect a source node instead.",
                        severity="error",
                        detail={
                            "class_type": class_type,
                            "input": name,
                            "target_name": target_name,
                            "input_type": getattr(spec, "type", None),
                        },
                    )
                )
                continue
            bound_issues = _validate_literal_value(
                value=literal,
                spec=spec,
                class_type=class_type,
                input_name=name,
                context="interpret",
            )
            hard = [
                issue
                for issue in bound_issues
                if getattr(issue, "severity", "error") == "error"
                and not (
                    reconstructing
                    and str(getattr(issue, "code", ""))
                    in {"value_not_in_enum", "asset_not_installed"}
                )
            ]
            if hard:
                issues.extend(_port_issues(hard))
                continue
            fields[name] = literal
        roster = emit_order_names or widget_field_names
        if roster:
            fields = _remap_encoded_field_names(fields, roster)
            linked = _remap_encoded_field_names(linked, roster)
        if class_type == _EXEC_CLASS_TYPE:
            normalized_io = _normalize_exec_io(fields.get("io", exec_io_value))
            if normalized_io is None or (
                not normalized_io["inputs"] and not normalized_io["outputs"]
            ):
                inferred_io = _infer_exec_io(fields.get("source"), linked)
                if inferred_io is not None:
                    normalized_io = inferred_io
            if normalized_io is not None:
                fields["io"] = {
                    "inputs": [[name, socket_type] for name, socket_type in normalized_io["inputs"]],
                    "outputs": [[name, socket_type] for name, socket_type in normalized_io["outputs"]],
                }
        inferred_anchor: AnchorRef | None = None
        inferred_anchor_diag: CompactDiagnostic | None = None
        if (
            relation is None
            and near_ref is None
            and group_title is None
            and self.placement_facts is not None
        ):
            inferred_anchor = self._inferred_anchor(target_name, linked)
            if inferred_anchor is not None and inferred_anchor.relation == "between":
                inferred_anchor_diag = _diag(
                    "splice_anchor_no_group",
                    (
                        f"Splice-placed node of type '{class_type}': neither "
                        "downstream nor upstream belongs to a group; leaving ungrouped."
                    ),
                    severity="info",
                    detail={"class_type": class_type, "target_name": target_name},
                )
        if relation is not None and near_ref is None and group_title is None:
            issues.append(
                _diag(
                    "anchor_target_missing",
                    "relation= requires near=... or group=... to anchor the new node.",
                    severity="error",
                    detail={"class_type": class_type, "target_name": target_name},
                )
            )
        if issues:
            self.unbound.add(target_name)
            return self._reject_diagnostics(item, "node_call", issues)
        uid = _uid_from_source(item.source) or self._uid_from_lines(item) or _mint_ir_uid(self.workflow)
        node_id = uid if uid not in {str(n.id) for n in self.workflow.nodes.values()} else None
        anchor = inferred_anchor
        if anchor is None and (near_ref is not None or group_title is not None):
            anchor = AnchorRef(
                relation=(relation or "near"),  # type: ignore[arg-type]
                near=near_ref,
                group_title=group_title,
            )
        op = AddNodeOp(
            op="add_node",
            scope_path="",
            class_type=class_type,
            fields=fields,
            inputs=linked,
            anchor=anchor,
            uid=uid,
            node_id=node_id,
            widget_field_names=widget_field_names,
        )
        applied = self._apply(item, op)
        if isinstance(applied, StatementOutcome):
            self.unbound.add(target_name)
            return applied
        minted = uid or self._uid_for_newest(class_type)
        if minted:
            self.transient[target_name] = minted
            added = self._node_by_uid(minted)
            if added is not None:
                port_source = self._source_block(item) or item.source
                self.workflow.nodes[str(added.id)] = _stamped_node(
                    added, port_source, self.schema_provider
                )
        self._refresh_bindings()
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="node_call",
            op=op,
            diagnostics=() if inferred_anchor_diag is None else (inferred_anchor_diag,),
            detail={"target_name": target_name, "minted_uid": minted, "class_type": class_type},
        )

    def _assign_attribute(
        self,
        item: _ExpandedStatement,
        target: ast.Attribute,
        rhs: ast.expr,
    ) -> StatementOutcome:
        node, node_issues = self._resolve_name(
            target.value.id if isinstance(target.value, ast.Name) else "",
            unknown_code="unknown_target_name",
        )
        if node_issues:
            return self._reject_diagnostics(
                item,
                op_kind_for_assignment(rhs, target_attr=target.attr),
                node_issues,
            )
        assert node is not None
        guarded = self._guard_original_virtual(item, node, action="mutate")
        if guarded is not None:
            return guarded
        field_name = self._canonical_field(node, target.attr)
        if target.attr == "mode":
            return self._set_mode(item, node, rhs)
        if isinstance(rhs, ast.Constant) and rhs.value is None:
            return self._remove_link(item, node, field_name)
        if _is_graph_reference_value(rhs):
            return self._upsert_link(item, node, field_name, rhs)
        return self._set_field(item, node, field_name, rhs)

    def _set_mode(self, item: _ExpandedStatement, node: Any, rhs: ast.expr) -> StatementOutcome:
        literal, issue = _fold_constant(rhs, env=item.env)
        if issue is not None:
            return self._reject_diagnostics(item, "set_mode", (issue,))
        mode: int | None
        if isinstance(literal, str):
            mode = _MODE_LABEL_TO_VALUE.get(literal.strip().lower())
        elif isinstance(literal, bool) or not isinstance(literal, int):
            mode = None
        else:
            mode = literal if literal in MODE_LABELS else None
        if mode is None:
            return self._reject(
                item,
                "invalid_mode_value",
                "set_mode",
                "Mode assignments must use 0, 2, 4 or their MODE_LABELS-derived labels.",
            )
        current = mode_to_litegraph(node.mode)
        op = SetModeOp(op="set_mode", target=NodeTarget("", str(node.uid)), mode=mode)  # type: ignore[arg-type]
        if current == mode:
            return StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="skipped",
                reason="cas_unchanged",
                op_kind="set_mode",
                op=op,
            )
        applied = self._apply(item, op)
        if isinstance(applied, StatementOutcome):
            return applied
        self._refresh_bindings()
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="set_mode",
            op=op,
        )

    def _set_field(
        self,
        item: _ExpandedStatement,
        node: Any,
        field_name: str,
        rhs: ast.expr,
    ) -> StatementOutcome:
        surface = editable_surface_for(
            node, schema_provider=self.schema_provider, edges=self.workflow.edges
        )
        if field_name in surface.socket_names() and field_name not in surface.literal_names():
            schema = schema_for(self.schema_provider, node.class_type)
            spec = _input_spec_for_field(getattr(schema, "inputs", {}) or {}, field_name)
            current_input = node.inputs.get(field_name) if isinstance(getattr(node, "inputs", None), Mapping) else None
            scalar_input = current_input is not None and not _is_link_value(current_input)
            if (
                not input_spec_is_literal_widget(spec)
                and field_name not in node.widgets
                and not scalar_input
            ):
                return self._reject(
                    item,
                    "socket_input_not_literal_widget",
                    "set_node_field",
                    f"{node.class_type}.{field_name} is an input socket, not a widget; connect a source node instead.",
                )
        schema = schema_for(self.schema_provider, node.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        if (
            field_name
            and field_name not in surface.literal_names()
            and field_name not in node.inputs
            and field_name not in node.widgets
            and field_name not in schema_inputs
            and not is_positional_alias(field_name)
        ):
            return self._reject(
                item,
                "unknown_target_field",
                "set_node_field",
                f"{node.class_type} has no editable field or input named {field_name!r}.",
            )
        literal, issue = _fold_constant(rhs, env=item.env)
        if issue is not None:
            return self._reject_diagnostics(item, "set_node_field", (issue,))
        schema = schema_for(self.schema_provider, node.class_type)
        spec = _input_spec_for_field(getattr(schema, "inputs", {}) or {}, field_name)
        bound_issues = _validate_literal_value(
            value=literal,
            spec=spec,
            class_type=str(node.class_type),
            input_name=field_name,
            context="interpret",
        )
        hard = [issue for issue in bound_issues if getattr(issue, "severity", "error") == "error"]
        if hard:
            return self._reject_diagnostics(item, "set_node_field", _port_issues(hard))
        current = _current_field_value(node, field_name)
        cas_key = (str(node.uid), field_name)
        expected = self.cas_old.get(cas_key)
        if expected is None:
            expected = self.cas_old.get((str(getattr(node, "id", "")), field_name))
        if expected is not None and expected != current:
            return self._reject(
                item,
                "cas_mismatch",
                "set_node_field",
                f"{node.class_type}.{field_name} CAS failed: expected {expected!r}, current {current!r}.",
            )
        if current == literal:
            op = SetNodeFieldOp(
                op="set_node_field",
                target=NodeFieldTarget("", str(node.uid), field_name),
                value=literal,
            )
            return StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="skipped",
                reason="cas_unchanged",
                op_kind="set_node_field",
                op=op,
            )
        op = SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget("", str(node.uid), field_name),
            value=literal,
        )
        applied = self._apply(item, op)
        if isinstance(applied, StatementOutcome):
            return applied
        self.cas_old[cas_key] = literal
        self._refresh_bindings()
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="set_node_field",
            op=op,
        )

    def _upsert_link(
        self,
        item: _ExpandedStatement,
        node: Any,
        field_name: str,
        rhs: ast.expr,
    ) -> StatementOutcome:
        surface = editable_surface_for(
            node, schema_provider=self.schema_provider, edges=self.workflow.edges
        )
        if field_name in surface.literal_names() and field_name not in surface.socket_names():
            return self._reject(
                item,
                "literal_field_not_socket",
                "upsert_link",
                f"{node.class_type}.{field_name} is a literal field, not a wiring socket.",
            )
        endpoint, issues = self._resolve_source(rhs)
        if issues:
            return self._reject_diagnostics(item, "upsert_link", issues)
        assert endpoint is not None
        source_node = self._node_by_uid(endpoint.uid)
        if source_node is not None and endpoint.output_slot:
            source_type = _output_socket_type(source_node, endpoint.output_slot)
            dest_type = _input_socket_type(node, field_name, self.schema_provider)
            if (
                source_type
                and dest_type
                and not socket_types_compatible(source_type, dest_type)
            ):
                return self._reject(
                    item,
                    "socket_type_mismatch",
                    "upsert_link",
                    f"Cannot wire {source_type} into {dest_type} on {node.class_type}.{field_name}.",
                )
        op = UpsertLinkOp(
            op="upsert_link",
            source=endpoint,
            target=LinkTargetRef("", str(node.uid), field_name),
        )
        applied = self._apply(item, op)
        if isinstance(applied, StatementOutcome):
            return applied
        self._refresh_bindings()
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="upsert_link",
            op=op,
        )

    def _remove_link(self, item: _ExpandedStatement, node: Any, field_name: str) -> StatementOutcome:
        op = RemoveLinkOp(
            op="remove_link",
            target=LinkTargetRef("", str(node.uid), field_name),
        )
        applied = self._apply(item, op)
        if isinstance(applied, StatementOutcome):
            return applied
        self._refresh_bindings()
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="remove_link",
            op=op,
        )

    def _delete(self, item: _ExpandedStatement) -> StatementOutcome:
        target = item.node.targets[0] if isinstance(item.node, ast.Delete) else None
        if not isinstance(target, ast.Name):
            return self._reject(item, "scope_escape_not_allowed", "remove_node")
        node, issues = self._resolve_name(target.id)
        if issues:
            return self._reject_diagnostics(item, "remove_node", issues)
        assert node is not None
        guarded = self._guard_original_virtual(item, node, action="delete")
        if guarded is not None:
            return guarded
        op = RemoveNodeOp(op="remove_node", target=NodeTarget("", str(node.uid)))
        applied = self._apply(item, op)
        if isinstance(applied, StatementOutcome):
            return applied
        self.transient.pop(target.id, None)
        self._refresh_bindings()
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="remove_node",
            op=op,
        )

    def _resolve_name(
        self,
        name: str,
        *,
        unknown_code: str = "unknown_graph_name",
    ) -> tuple[Any | None, tuple[CompactDiagnostic, ...]]:
        if not name:
            return None, (
                _diag(unknown_code, "Unknown graph name.", severity="error", detail={"name": name}),
            )
        if name in self.unbound:
            return None, (
                _diag(
                    "unbound_graph_name",
                    f"Graph name {name!r} is currently unbound because its add-node statement did not land.",
                    severity="error",
                    detail={"name": name},
                ),
            )
        if name in self._retired_name_uids and name not in self.name_to_uid:
            uid = self._retired_name_uids[name]
            return None, (
                _diag(
                    "stale_graph_name",
                    f"Graph name {name!r} referred to removed uid {uid!r} earlier in this batch.",
                    severity="error",
                    detail={"name": name, "uid": uid},
                ),
            )
        uid = self.name_to_uid.get(name) or self.transient.get(name)
        if uid is None:
            node = self._node_by_uid(name)
            if node is not None:
                return node, ()
            return None, (
                _diag(
                    unknown_code,
                    f"Unknown graph name {name!r}. Render the session again if the canvas changed.",
                    severity="error",
                    detail={"name": name},
                ),
            )
        node = self._node_by_uid(uid)
        if node is None:
            return None, (
                _diag(
                    "stale_graph_name",
                    f"Graph name {name!r} still points at uid {uid!r}, but that uid is no longer present.",
                    severity="error",
                    detail={"name": name, "uid": uid},
                ),
            )
        return node, ()

    def _resolve_source(self, value: ast.expr) -> tuple[LinkSourceRef | None, tuple[CompactDiagnostic, ...]]:
        if isinstance(value, ast.Name):
            node, issues = self._resolve_name(value.id)
            if issues:
                return None, issues
            assert node is not None
            ports = _agent_edit_output_ports(node)
            if len(ports) == 1:
                slot = _raw_output_slot(node, next(iter(ports.values())))
                return LinkSourceRef("", str(node.uid), slot), ()
            return None, (
                _diag(
                    "ambiguous_bare_reference",
                    f"Bare reference {value.id!r} is ambiguous; use an explicit slot.",
                    severity="error",
                    detail={"name": value.id},
                ),
            )
        if not isinstance(value, ast.Attribute) or not isinstance(value.value, ast.Name):
            return None, (
                _diag(
                    "attribute_base_not_name",
                    "Attribute access must start from a rendered graph name.",
                    severity="error",
                ),
            )
        node, issues = self._resolve_name(value.value.id, unknown_code="unknown_source_name")
        if issues:
            return None, issues
        assert node is not None
        if is_positional_alias(value.attr):
            slot = None
        else:
            slot = _resolve_output_slot(node, value.attr)
            if slot is None and _TYPED_PORT.fullmatch(value.attr):
                slot = value.attr
        if slot is None:
            return None, (
                _diag(
                    "unknown_output_slot",
                    f"{node.class_type} has no output named {value.attr!r}.",
                    severity="error",
                    detail={"name": value.value.id, "uid": node.uid, "slot": value.attr},
                ),
            )
        return LinkSourceRef("", str(node.uid), slot), ()

    def _canonical_field(self, node: Any, raw: str) -> str:
        from vibecomfy.porting.edit.widget_slots import _canonical_ui_only_widget_field

        mapping: dict[str, Any] = {"type": node.class_type, "class_type": node.class_type}
        metadata = getattr(node, "metadata", None)
        if isinstance(metadata, Mapping):
            ui = metadata.get("_ui")
            if isinstance(ui, Mapping):
                mapping.update(ui)
                mapping["type"] = node.class_type
                mapping["class_type"] = node.class_type
        alias = _canonical_ui_only_widget_field(
            mapping, raw, schema_provider=self.schema_provider
        )
        if alias is not None:
            return alias[0]
        if str(node.class_type) == _EXEC_CLASS_TYPE:
            io_value = None
            if isinstance(getattr(node, "inputs", None), Mapping):
                io_value = node.inputs.get("io")
            if io_value is None and isinstance(getattr(node, "widgets", None), Mapping):
                io_value = node.widgets.get("io")
            mapped = _exec_semantic_slot_name(
                str(node.class_type), io_value, raw, direction="input"
            )
            if mapped != raw:
                return mapped
        schema = schema_for(self.schema_provider, node.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        return _surface_field_name(
            schema_inputs,
            str(node.class_type),
            raw,
            schema_provider=self.schema_provider,
        )

    def _node_by_uid(self, uid: str) -> Any | None:
        for node in self.workflow.nodes.values():
            if str(getattr(node, "uid", "") or "") == str(uid):
                return node
        return None

    def _source_block(self, item: _ExpandedStatement) -> str:
        node = item.node
        start = max(int(getattr(node, "lineno", 1) or 1) - 1, 0)
        end = int(getattr(node, "end_lineno", start + 1) or start + 1)
        return "\n".join(self._source_lines[start:end])

    def _uid_from_lines(self, item: _ExpandedStatement) -> str | None:
        return _uid_from_source(self._source_block(item))

    def _uid_for_newest(self, class_type: str) -> str | None:
        for node in reversed(list(self.workflow.nodes.values())):
            if str(node.class_type) == class_type and str(getattr(node, "uid", "") or ""):
                return str(node.uid)
        return None

    def _inferred_anchor(
        self,
        target_name: str,
        linked: Mapping[str, LinkSourceRef],
    ) -> AnchorRef | None:
        from vibecomfy.porting.layout.placement import infer_add_node_anchor_hint

        if self.placement_facts is None:
            return None
        hint = infer_add_node_anchor_hint(
            target_name=target_name,
            resolved_inputs=linked,
            placement_facts=self.placement_facts,
            current_input_source_ref=self._current_input_source_ref,
            target_has_any_link=self._target_has_any_link,
            uid_to_name={uid: name for name, uid in self.name_to_uid.items()},
        )
        if hint is not None and hint.relation == "between":
            pass
        else:
            pre_uids = {
                str(getattr(node, "uid", "") or "")
                for node in self._pre.nodes.values()
                if getattr(node, "uid", None)
            }
            for rewire in self.placement_facts.rewires_by_source.get(target_name, ()):
                dest, dest_issues = self._resolve_name(rewire.target_name)
                if (
                    dest is not None
                    and not dest_issues
                    and str(dest.uid) in pre_uids
                    and self._target_has_any_link(rewire.target_name)
                ):
                    return AnchorRef(
                        relation="left_of",
                        near=NodeTarget("", str(dest.uid)),
                    )
        if hint is None:
            return None
        if hint.relation == "between" and hint.between_names is not None:
            left, left_issues = self._resolve_name(hint.between_names[0])
            right, right_issues = self._resolve_name(hint.between_names[1])
            if left is None or right is None or left_issues or right_issues:
                return None
            return AnchorRef(
                relation="between",
                between=(
                    NodeTarget("", str(left.uid)),
                    NodeTarget("", str(right.uid)),
                ),
            )
        if hint.near_name is None:
            return None
        near, near_issues = self._resolve_name(hint.near_name)
        if near is None or near_issues:
            return None
        return AnchorRef(relation=hint.relation, near=NodeTarget("", str(near.uid)))

    def _current_input_source_ref(self, target_name: str, target_field: str) -> LinkSourceRef | None:
        node, issues = self._resolve_name(target_name)
        if node is None or issues:
            return None
        node_id = str(getattr(node, "id", "") or "")
        for edge in self.workflow.edges:
            if str(getattr(edge, "to_node", "")) == node_id and str(
                getattr(edge, "to_input", "")
            ) == target_field:
                source = self.workflow.nodes.get(str(getattr(edge, "from_node", "")))
                if source is None:
                    continue
                return LinkSourceRef(
                    "",
                    str(getattr(source, "uid", "") or ""),
                    _raw_output_slot(source, str(getattr(edge, "from_output", "") or "")),
                )
        return None

    def _target_has_any_link(self, target_name: str) -> bool:
        node, issues = self._resolve_name(target_name)
        if node is None or issues:
            return False
        node_id = str(getattr(node, "id", "") or "")
        return any(str(getattr(edge, "to_node", "")) == node_id for edge in self.workflow.edges)

    def _refresh_bindings(self) -> None:
        try:
            names = _compute_variable_names(self.workflow.nodes, list(self.workflow.edges))
        except Exception:
            names = {}
        live_uids = {
            str(getattr(node, "uid", "") or "")
            for node in self.workflow.nodes.values()
            if str(getattr(node, "uid", "") or "")
        }
        previous = dict(getattr(self, "name_to_uid", {}) or {})
        bindings: dict[str, str] = {}
        bound_uids: set[str] = set()
        for name, uid in previous.items():
            if uid in live_uids:
                bindings[name] = uid
                bound_uids.add(uid)
            else:
                self._retired_name_uids.setdefault(name, uid)

        # Assignment names for nodes added in this batch outrank computed
        # class-order names, but may never steal a still-live or retired name.
        for name, uid in self.transient.items():
            if (
                uid in live_uids
                and uid not in bound_uids
                and name not in bindings
                and name not in self._retired_name_uids
            ):
                bindings[name] = uid
                bound_uids.add(uid)

        used_names = set(bindings) | set(self._retired_name_uids)

        def fresh_name(preferred: str) -> str:
            if preferred not in used_names:
                return preferred
            match = re.match(r"^(.*?)(?:_(\d+))?$", preferred)
            base = (match.group(1) if match else preferred) or preferred
            suffix = int(match.group(2) or 1) + 1 if match else 2
            candidate = f"{base}_{suffix}"
            while candidate in used_names:
                suffix += 1
                candidate = f"{base}_{suffix}"
            return candidate

        for node_id, name in names.items():
            node = self.workflow.nodes.get(str(node_id))
            uid = str(getattr(node, "uid", "") or "")
            if not uid or uid in bound_uids:
                continue
            stable_name = fresh_name(name)
            bindings[stable_name] = uid
            used_names.add(stable_name)
            bound_uids.add(uid)
        self.name_to_uid = bindings

    def _apply(self, item: _ExpandedStatement, op: EditOp) -> StatementOutcome | None:
        try:
            before = self.workflow
            # Add-node reconstruction matches from_ui: named literals land in
            # inputs, widget_* names in widgets.  Passing the catalog would
            # re-channel named widgets and break π_edit channel honesty.
            provider = None if isinstance(op, AddNodeOp) else self.schema_provider
            self.workflow = apply_edit_cow(
                self.workflow, op, schema_provider=provider
            )
            self._pending_apply_diagnostics.extend(_apply_diagnostics(before, self.workflow, op))
        except Exception as exc:
            return StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="rejected",
                reason="apply_failed",
                op_kind=item.op_kind or getattr(op, "op", type(op).__name__),
                diagnostics=(_diag("apply_failed", str(exc), severity="error"),),
                op=op,
            )
        return None

    def _guard_original_virtual(
        self,
        item: _ExpandedStatement,
        node: Any,
        *,
        action: str,
    ) -> StatementOutcome | None:
        uid = str(getattr(node, "uid", "") or "")
        if uid and uid in self._pre_helper_uids:
            return self._reject(
                item,
                "original_virtual_node_immutable",
                "remove_node" if action == "delete" else "set_node_field",
                (
                    f"Original virtual substrate node ({node.class_type}) "
                    f"cannot be {action}d."
                ),
            )
        return None

    def _subgraph_interface(self, item: _ExpandedStatement, call: ast.Call) -> StatementOutcome:
        folded: dict[str, Any] = {}
        issues: list[CompactDiagnostic] = []
        for keyword in call.keywords:
            if keyword.arg is None:
                issues.append(
                    _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                )
                continue
            literal, issue = _fold_constant(keyword.value, env=item.env)
            if issue is not None:
                issues.append(issue)
                continue
            folded[keyword.arg] = literal
        name = folded.get("name")
        subgraph_id = folded.get("id") or name
        inputs = folded.get("inputs")
        outputs = folded.get("outputs")
        if not isinstance(name, str) or not name:
            issues.append(
                _diag(
                    "invalid_subgraph_interface",
                    "subgraph_interface name must be a non-empty string.",
                    severity="error",
                )
            )
        if not isinstance(inputs, (list, tuple)) or not isinstance(outputs, (list, tuple)):
            issues.append(
                _diag(
                    "invalid_subgraph_interface",
                    "subgraph_interface inputs/outputs must be sequences of (name, type).",
                    severity="error",
                )
            )
        if issues:
            return self._reject_diagnostics(item, "subgraph_interface", issues)
        subgraph_id_str = (
            subgraph_id if isinstance(subgraph_id, str) and subgraph_id else name
        )
        parsed_inputs = tuple(
            (str(port[0]), port[1] if len(port) > 1 else None)
            for port in inputs
            if isinstance(port, (list, tuple)) and port
        )
        parsed_outputs = tuple(
            (str(port[0]), port[1] if len(port) > 1 else None)
            for port in outputs
            if isinstance(port, (list, tuple)) and port
        )
        existing = self.workflow.metadata.get("definitions")
        existing_ids: set[str] = set()
        if isinstance(existing, Mapping):
            for entry in existing.get("subgraphs") or []:
                if isinstance(entry, Mapping):
                    existing_ids.add(str(entry.get("id") or entry.get("name") or ""))
        action: Literal["add", "change"] = (
            "change" if subgraph_id_str in existing_ids else "add"
        )
        op = SubgraphInterfaceOp(
            op="subgraph_interface",
            action=action,
            name=name,
            inputs=parsed_inputs,
            outputs=parsed_outputs,
            id=subgraph_id_str,
        )
        applied = self._apply(item, op)
        if isinstance(applied, StatementOutcome):
            return applied
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="subgraph_interface",
            op=op,
            detail={"name": name, "id": subgraph_id_str, "action": action},
        )

    def _reject(
        self,
        item: _ExpandedStatement,
        code: str,
        op_kind: str,
        message: str | None = None,
    ) -> StatementOutcome:
        diagnostic = _diag(code, message or code, severity="error")
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="rejected",
            reason=code,
            op_kind=op_kind,
            diagnostics=(diagnostic,),
        )

    def _reject_diagnostics(
        self,
        item: _ExpandedStatement,
        op_kind: str,
        diagnostics: Sequence[CompactDiagnostic],
    ) -> StatementOutcome:
        diags = tuple(diagnostics)
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="rejected",
            reason=diags[0].code if diags else "rejected",
            op_kind=op_kind,
            diagnostics=diags,
        )


def _class_type_from_call(
    call: ast.Call,
    env: Mapping[str, Any],
) -> tuple[str, tuple[CompactDiagnostic, ...]]:
    func = call.func
    name, dotted = _resolve_vibecomfy_constructor(func)
    if isinstance(func, ast.Name) and func.id == "node":
        if not call.args:
            return "", (
                _diag(
                    "missing_node_class_type",
                    "node(...) requires a class-type string as its first argument.",
                    severity="error",
                ),
            )
        value, issue = _fold_constant(call.args[0], env=env)
        if issue is not None:
            return "", (issue,)
        if not isinstance(value, str) or not value:
            return "", (
                _diag(
                    "invalid_node_class_type",
                    "node(...) class type must be a non-empty string.",
                    severity="error",
                ),
            )
        return value, ()
    if name is None:
        return "", (
            _diag("call_target_not_name", "Node construction calls must target a simple class name.", severity="error"),
        )
    if dotted:
        return name, ()
    return name, ()


def _surface_field_name(
    schema_inputs: Mapping[str, Any],
    class_type: str,
    name: str,
    *,
    schema_provider: Any = None,
) -> str:
    return _decode_kwarg_name(
        name, schema_inputs, class_type, schema_provider=schema_provider
    )


def _remap_encoded_field_names(
    fields: Mapping[str, Any],
    raw_names: Sequence[str],
) -> dict[str, Any]:
    """Restore emit's ``encode_slot_names`` encoding to the roster's raw names."""
    if not raw_names:
        return dict(fields)
    raw_list = [str(name) for name in raw_names]
    raw_set = set(raw_list)
    reverse = {encoded: raw for raw, encoded in encode_slot_names(raw_list).items()}
    return {
        (name if name in raw_set else reverse.get(name, name)): value
        for name, value in fields.items()
    }


def _decode_kwarg_name(
    name: str,
    schema_inputs: Mapping[str, Any],
    class_type: str,
    *,
    endpoint: LinkSourceRef | None = None,
    schema_provider: Any = None,
) -> str:
    """Reverse emit's ``encode_slot_names`` using schema + type tokens."""
    canonical = _canonical_input_name_for_class(
        schema_inputs, class_type, name, schema_provider=schema_provider
    )
    if canonical != name:
        return canonical
    candidates = {str(key) for key in schema_inputs}
    candidates.add(name)
    dotted = name.replace("_", ".")
    if dotted != name and dotted in schema_inputs:
        candidates.add(dotted)
    if name.startswith("variables_"):
        candidates.add("variables." + name[len("variables_"):])
    if name.endswith("_") and (
        keyword.iskeyword(name[:-1]) or name[:-1] in _BUILTIN_NAMES
    ):
        candidates.add(name[:-1])
        if class_type == "SetNode":
            candidates.add(name[:-1].upper())
    if class_type == "SetNode" and endpoint is not None:
        candidates.add(str(endpoint.output_slot).rsplit("_", 1)[0])
    if class_type == "Reroute":
        candidates.add("_" + name)
    reverse: dict[str, str] = {}
    collisions: dict[str, set[str]] = {}
    for raw in candidates:
        encoded = to_python_identifier(raw)
        existing = reverse.get(encoded)
        if existing is not None and existing != raw:
            collisions.setdefault(encoded, {existing}).add(raw)
        else:
            reverse[encoded] = raw
    if name in collisions:
        options = collisions[name]
        if class_type == "Reroute":
            underscored = [item for item in options if item.startswith("_")]
            if len(underscored) == 1:
                return underscored[0]
        if class_type == "SetNode":
            upper = [item for item in options if item.isupper()]
            if len(upper) == 1:
                return upper[0]
        return sorted(options)[0]
    if name in reverse:
        return reverse[name]
    return name


def _uid_from_source(source: str) -> str | None:
    match = _UID_COMMENT.search(source)
    return match.group(1) if match else None


def _call_id(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _current_field_value(node: Any, field_name: str) -> Any:
    if field_name in getattr(node, "widgets", {}):
        return node.widgets[field_name]
    if field_name in getattr(node, "inputs", {}):
        return node.inputs[field_name]
    return None


def _slots_from_source(source: str) -> list[tuple[str, str | None]]:
    marker = source.rfind("slots ")
    if marker < 0:
        return []
    blob = source[marker + 6 :].split("#", 1)[0]
    found: list[tuple[str, str | None]] = []
    for match in _SLOT_COMMENT.finditer(blob):
        port, raw = match.group(1), match.group(2)
        if port in {"known", "provisional", "unknown"}:
            continue
        found.append((port, raw))
    return found


def _stamped_node(node: Any, source: str, schema_provider: Any) -> Any:
    """Return a NEW node with emit ports stamped (never mutate the input)."""
    from copy import deepcopy

    stamped = deepcopy(node)
    _attach_emitted_ports(stamped, source, schema_provider)
    return stamped


def _attach_emitted_ports(node: Any, source: str, schema_provider: Any) -> None:
    """Stamp typed emit ports onto a freshly added IR node.

    ``apply_edit_cow`` only copies class/fields; output ports live in
    instance metadata.  Without them ``src.IMAGE_0`` cannot resolve.
    Callers must pass a node that is not aliased to the pre-IR.
    """
    metadata = dict(getattr(node, "metadata", None) or {})
    ports = _slots_from_source(source)
    if not ports and str(getattr(node, "class_type", "")) == "vibecomfy.exec":
        from vibecomfy.porting.edit._resolve import _normalize_exec_io

        io_value = None
        if isinstance(getattr(node, "inputs", None), Mapping):
            io_value = node.inputs.get("io")
        if io_value is None and isinstance(getattr(node, "widgets", None), Mapping):
            io_value = node.widgets.get("io")
        normalized = _normalize_exec_io(io_value)
        if normalized and normalized["outputs"]:
            ports = [
                (f"{str(socket_type or 'unknown').replace(' ', '_').upper()}_{index}", name)
                for index, (name, socket_type) in enumerate(normalized["outputs"])
            ]
    if not ports:
        schema = schema_for(schema_provider, node.class_type)
        schema_outputs = list(getattr(schema, "outputs", None) or [])
        ports = [
            (
                f"{str(getattr(item, 'type', None) or getattr(item, 'name', None) or 'unknown').replace(' ', '_').upper()}_{index}",
                getattr(item, "name", None),
            )
            for index, item in enumerate(schema_outputs)
        ]
    if not ports:
        return
    ui = dict(metadata.get("_ui") or {})
    ui_outputs = []
    alias: dict[str, str] = {}
    for index, (port, raw) in enumerate(ports):
        type_token = port.rsplit("_", 1)[0] if "_" in port else port
        ui_outputs.append(
            {
                "name": raw or port,
                "type": type_token,
                "slot_index": index,
            }
        )
        alias[port] = port
        if raw:
            alias[raw] = port
    ui["outputs"] = ui_outputs
    metadata["_ui"] = ui
    metadata["_edit_ports"] = alias
    metadata["output_names"] = [raw or port for port, raw in ports]
    metadata["output_types"] = [
        (port.rsplit("_", 1)[0] if "_" in port else port) for port, _raw in ports
    ]
    node.metadata = metadata


def _resolve_output_slot(node: Any, attr: str) -> str | None:
    if str(getattr(node, "class_type", "")) == "vibecomfy.exec":
        io_value = None
        if isinstance(getattr(node, "inputs", None), Mapping):
            io_value = node.inputs.get("io")
        if io_value is None and isinstance(getattr(node, "widgets", None), Mapping):
            io_value = node.widgets.get("io")
        mapped = _exec_semantic_slot_name(
            "vibecomfy.exec", io_value, attr, direction="output"
        )
        if mapped != attr:
            attr = mapped
        if attr.startswith("out_") and attr[4:].isdigit():
            index = int(attr[4:])
            ports = _agent_edit_output_ports(node)
            if index in ports:
                return ports[index]
            return attr
    aliases = (getattr(node, "metadata", None) or {}).get("_edit_ports")
    if isinstance(aliases, Mapping) and attr in aliases:
        return aliases[attr]
    decoded = attr
    if attr.endswith("_") and (
        keyword.iskeyword(attr[:-1]) or attr[:-1] in _BUILTIN_NAMES
    ):
        decoded = attr[:-1]
    if isinstance(aliases, Mapping) and decoded in aliases:
        return aliases[decoded]
    ports = _agent_edit_output_ports(node)
    if attr in ports.values():
        return attr
    metadata = getattr(node, "metadata", None) or {}
    raw_names = metadata.get("output_names") if isinstance(metadata, Mapping) else None
    if isinstance(raw_names, (list, tuple)) and attr in raw_names:
        index = list(raw_names).index(attr)
        return ports.get(index, attr)
    ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    outputs = ui.get("outputs") if isinstance(ui, Mapping) else None
    if isinstance(outputs, list):
        for index, output in enumerate(outputs):
            if isinstance(output, Mapping) and output.get("name") in {attr, decoded}:
                return str(output.get("name") or attr)
    if decoded != attr:
        if isinstance(raw_names, (list, tuple)) and decoded in raw_names:
            index = list(raw_names).index(decoded)
            return ports.get(index, decoded)
        return decoded
    names = {str(name): str(name) for name in ports.values() if name}
    if names:
        try:
            raw = to_raw_name(attr, context=names)
        except (KeyError, ValueError):
            raw = None
        if raw:
            return raw
        lowered = attr.casefold()
        for name in names:
            if name.casefold() == lowered or to_python_identifier(name) == attr:
                return name
    match = _TYPED_PORT.fullmatch(attr)
    if match is not None:
        index = int(match.group(2))
        if index in ports:
            return ports[index]
    candidates: list[str] = [str(name) for name in ports.values() if name]
    if isinstance(raw_names, (list, tuple)):
        candidates.extend(str(name) for name in raw_names if name)
    if isinstance(outputs, list):
        for output in outputs:
            if isinstance(output, Mapping) and output.get("name"):
                candidates.append(str(output["name"]))
    lowered = attr.casefold()
    for name in candidates:
        if name.casefold() == lowered or to_python_identifier(name) == attr:
            return name
    return None


def _raw_output_slot(node: Any, slot: str) -> str:
    """Map a typed emit alias (IMAGE_0) back to the UI/raw slot name."""
    if str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE:
        if slot.startswith("out_") or slot.startswith("in_"):
            return slot
        typed = _TYPED_PORT.fullmatch(slot)
        if typed is not None:
            return f"out_{typed.group(2)}"
        io_value = None
        if isinstance(getattr(node, "inputs", None), Mapping):
            io_value = node.inputs.get("io")
        if io_value is None and isinstance(getattr(node, "widgets", None), Mapping):
            io_value = node.widgets.get("io")
        if io_value is None:
            metadata = getattr(node, "metadata", None) or {}
            if isinstance(metadata, Mapping):
                vibe = metadata.get("vibecomfy")
                if isinstance(vibe, Mapping):
                    io_value = vibe.get("io")
        mapped = _exec_semantic_slot_name(
            _EXEC_CLASS_TYPE, io_value, slot, direction="output"
        )
        if mapped != slot:
            return mapped
    metadata = getattr(node, "metadata", None) or {}
    if slot.isdigit():
        ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
        outputs = ui.get("outputs") if isinstance(ui, Mapping) else None
        if isinstance(outputs, list) and int(slot) < len(outputs):
            named = outputs[int(slot)]
            if isinstance(named, Mapping) and named.get("name"):
                return str(named["name"])
        ports = _agent_edit_output_ports(node)
        mapped = ports.get(int(slot))
        if mapped:
            slot = str(mapped)
    aliases = metadata.get("_edit_ports") if isinstance(metadata, Mapping) else None
    if isinstance(aliases, Mapping):
        for raw, typed in aliases.items():
            if typed == slot and raw != typed:
                return str(raw)
    raw_names = metadata.get("output_names") if isinstance(metadata, Mapping) else None
    if isinstance(raw_names, (list, tuple)) and slot in raw_names:
        return slot
    ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    outputs = ui.get("outputs") if isinstance(ui, Mapping) else None
    if isinstance(outputs, list):
        for output in outputs:
            if isinstance(output, Mapping) and output.get("name") == slot:
                return slot
    match = _TYPED_PORT.fullmatch(slot)
    if match is not None:
        base = match.group(1)
        if isinstance(outputs, list):
            for output in outputs:
                if isinstance(output, Mapping) and output.get("name") == base:
                    return base
        if isinstance(raw_names, (list, tuple)) and base in raw_names:
            return base
        return base
    return slot


def _ui_output_slot(node: Any, slot: str) -> str:
    """Map an IR typed emit slot to the working UI output name.

    Interpret keeps typed aliases (``IMAGE_0``) on ``LinkSourceRef`` for
    Law 2.  The emit-side projector and agent-facing field changes need the
    declared UI name: LoadImage's ``IMAGE_0`` is ``image``, ImageScaleBy's
    ``IMAGE_0`` is ``IMAGE``.  ``_raw_output_slot`` only strips the index
    (returning the type token), which apply_delta then rejects when the UI
    name differs from the type.
    """
    if str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE:
        return _raw_output_slot(node, slot)

    metadata = getattr(node, "metadata", None) or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    ui = metadata.get("_ui")
    outputs = ui.get("outputs") if isinstance(ui, Mapping) else None
    raw_names = metadata.get("output_names")

    def _name_at(index: int) -> str | None:
        if isinstance(outputs, list) and 0 <= index < len(outputs):
            named = outputs[index]
            if isinstance(named, Mapping) and named.get("name"):
                return str(named["name"])
        if (
            isinstance(raw_names, (list, tuple))
            and 0 <= index < len(raw_names)
            and raw_names[index]
        ):
            return str(raw_names[index])
        return None

    aliases = metadata.get("_edit_ports")
    if isinstance(aliases, Mapping):
        for raw, typed in aliases.items():
            if typed == slot and raw != typed:
                return str(raw)

    if slot.isdigit():
        named = _name_at(int(slot))
        if named:
            return named

    match = _TYPED_PORT.fullmatch(slot)
    if match is not None:
        named = _name_at(int(match.group(2)))
        if named:
            return named
        return _raw_output_slot(node, slot)
    return slot


def _output_socket_type(node: Any, slot: str | int) -> str | None:
    ports = _agent_edit_output_ports(node)
    if isinstance(slot, str):
        for index, name in ports.items():
            if name == slot:
                metadata = getattr(node, "metadata", None) or {}
                types = metadata.get("output_types") if isinstance(metadata, Mapping) else None
                if isinstance(types, (list, tuple)) and index < len(types):
                    return str(types[index]) or None
                token = slot.rsplit("_", 1)[0]
                return token if token else None
    return None


def _input_socket_type(node: Any, field_name: str, schema_provider: Any) -> str | None:
    schema = schema_for(schema_provider, node.class_type)
    spec = _input_spec_for_field(getattr(schema, "inputs", {}) or {}, field_name)
    if spec is not None and getattr(spec, "type", None):
        return str(spec.type)
    return None


def _port_issues(issues: Iterable[Any]) -> tuple[CompactDiagnostic, ...]:
    return tuple(
        CompactDiagnostic(
            code=str(getattr(issue, "code", "edit_apply_error")),
            message=str(getattr(issue, "message", "Edit apply failed.")),
            severity=str(getattr(issue, "severity", "error")),
            detail=dict(getattr(issue, "detail", {}) or {}),
        )
        for issue in issues
    )


__all__ = [
    "InterpretationResult",
    "StatementOutcome",
    "StatementStatus",
    "interpret",
]
