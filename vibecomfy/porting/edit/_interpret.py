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
import logging
import re
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Literal, Mapping, Sequence

_LOGGER = logging.getLogger(__name__)

from vibecomfy.porting.edit._ir_utils import (
    _canonical_input_name_for_class,
    _cow_workflow_copy,
    _input_spec_for_field,
    _mint_ir_uid,
    EditNoOpError,
    apply_edit_cow,
)
from vibecomfy.porting.edit._parse import (
    _channel_side_unpack,
    _fold_constant,
    _is_graph_reference_value,
    _parse_and_validate_batch,
    _resolve_vibecomfy_constructor,
    reserved_kwarg_is_coordinate_hint,
)
from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    OperationTransition,
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
from vibecomfy.porting.emit.ui import guard_exit_ui as _canonical_guard_exit_ui
from vibecomfy.porting.edit._resolve import (
    _EXEC_CLASS_TYPE,
    _exec_semantic_slot_name,
    _infer_exec_io,
    _normalize_exec_io,
)
from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget, input_spec_is_socket_only
from vibecomfy.schema import schema_for, socket_types_compatible
from vibecomfy.workflow import VibeWorkflow


StatementStatus = Literal["applied", "rejected", "skipped"]

_UID_COMMENT = re.compile(r"#\s*uid:([^\s]+)")
_TYPED_PORT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)_(\d+)$")
_SLOT_COMMENT = re.compile(
    r"(\w+)(?:='([^']*)')?(?:\s+(?:known|provisional|unknown))?"
)
_MODE_LABEL_TO_VALUE = {str(label): mode for mode, label in MODE_LABELS.items()}
_PLACEMENT_KWARGS = frozenset({"near", "relation", "group"})
_RAW_COORDINATE_KWARGS = frozenset({"pos", "position", "coords", "x", "y"})
_VALUE_DEFAULT_RECEIPT_CODES = frozenset({
    "value_default_binding_receipt",
    "value_default_edit_receipt",
})


def _published_diagnostics(
    diagnostics: Sequence[CompactDiagnostic],
) -> tuple[CompactDiagnostic, ...]:
    """Publish errors/warnings plus retained value-default receipts.

    Ordinary info chatter stays session-local. Binding and edit receipts are
    accepted-batch proof, so they survive the published diagnostic filter.
    """
    return tuple(
        diagnostic
        for diagnostic in diagnostics
        if getattr(diagnostic, "severity", "error") in {"error", "warning"}
        or getattr(diagnostic, "code", "") in _VALUE_DEFAULT_RECEIPT_CODES
    )


def _has_frozen_schema_authority(provider: Any) -> bool:
    """Return whether *provider* carries the retained ingress witness."""
    from vibecomfy.schema import FrozenSchemaSnapshotProvider, SchemaSnapshot

    if isinstance(provider, FrozenSchemaSnapshotProvider):
        return True
    snapshot = getattr(provider, "snapshot", None)
    # A retained witness is data, not a lookup hook.  Do not invoke a
    # callable ``snapshot`` surface here: that could consult mutable provider
    # state after ingress and silently turn advisory evidence into authority.
    return isinstance(snapshot, SchemaSnapshot)


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
    transitions: tuple[OperationTransition, ...] = ()
    lint_result: Any = None
    occurrence_to_statement_index: Mapping[int, int] = field(default_factory=dict)
    value_default_context: Any = None
    schema_provider: Any = None


@dataclass(frozen=True, slots=True)
class OperationEvaluation:
    """Detached result of one canonical operation-boundary evaluation."""

    workflow: VibeWorkflow
    normalized: EditOp
    lowered: tuple[EditOp, ...] = ()
    outcome: Literal["staged", "noop", "rejected"] = "rejected"
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    lint_issue: Any = None
    lint_disposition: str = "passed"
    presentation_ui: Any = None
    presentation_index: Any = None
    value_default_context: Any = None


def _capture_presentation(
    workflow: VibeWorkflow,
    schema_provider: Any,
) -> tuple[Any, Any, CompactDiagnostic | None]:
    """Capture the mandatory retained presentation projection once."""
    from vibecomfy.porting.edit.lint import LintIndex
    from vibecomfy.porting.emit.ui import emit_ui_json
    from vibecomfy.porting.refuse import RefusedEmit

    try:
        payload = emit_ui_json(
            workflow,
            schema_provider=schema_provider,
            include_virtual_wires=True,
        )
    except RefusedEmit as exc:
        return (
            None,
            None,
            _diag(
                "presentation_rejected",
                f"canonical presentation projection was refused: {exc}",
                severity="error",
            ),
        )
    return payload, LintIndex.build(payload), None


def _presentation_guard_ops(
    workflow: VibeWorkflow,
    operations: Sequence[EditOp],
    schema_provider: Any,
) -> tuple[EditOp, ...]:
    """Project canonical ops onto the retained UI's physical identities.

    Semantic operations keep authored names (``texture_quality`` or a schema
    output name such as ``emotion_control``).  The strict UI guard compares
    against a positional canvas projection, so its attribution view must use
    the same frozen name/slot evidence rather than infer from list order or a
    live registry.  This changes only the guard view; the canonical lowered
    operations remain authored and are what replay applies.
    """
    from dataclasses import replace

    from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid
    from vibecomfy.porting.widgets.compact_resolver import widget_index_for_field

    widget_names = frozen_widget_names_by_uid(workflow)
    projected: list[EditOp] = []
    for operation in operations:
        current = operation
        if isinstance(operation, SetNodeFieldOp):
            target_node = next(
                (
                    node
                    for node in (getattr(workflow, "nodes", {}) or {}).values()
                    if str(getattr(node, "uid", "") or "")
                    == str(operation.target.uid)
                ),
                None,
            )
            widget_index = (
                widget_index_for_field(
                    target_node,
                    str(operation.target.field_path),
                    schema_provider=schema_provider,
                    name_authority=widget_names,
                )
                if target_node is not None
                else None
            )
            if widget_index is not None:
                current = replace(
                    operation,
                    target=replace(
                        operation.target,
                        field_path=f"widgets_values[{widget_index}]",
                    ),
                )
        elif isinstance(operation, UpsertLinkOp):
            source = next(
                (
                    node
                    for node in (getattr(workflow, "nodes", {}) or {}).values()
                    if str(getattr(node, "uid", "") or "")
                    == str(operation.source.uid)
                ),
                None,
            )
            if source is not None:
                resolved = canonical_renderer_output(
                    source,
                    operation.source.output_slot,
                    provider=schema_provider,
                )
                if resolved is not None:
                    names, _types, _sources, _count = _frozen_output_evidence(
                        source, schema_provider
                    )
                    physical_slot = next(
                        (
                            index
                            for index, name in names.items()
                            if str(name) == str(resolved)
                        ),
                        None,
                    )
                    if physical_slot is not None:
                        current = replace(
                            operation,
                            source=replace(
                                operation.source,
                                output_slot=physical_slot,
                            ),
                        )
        projected.append(current)
        if isinstance(operation, AddNodeOp) and operation.uid:
            # AddNode is the canonical aggregate for constructor syntax: its
            # linked kwargs materialize edges in the same COW transition.
            # Attribute those exact edges to the guard as typed link ops so
            # strict presentation custody sees the whole admitted aggregate.
            for input_name, source in operation.inputs.items():
                link_op = UpsertLinkOp(
                    op="upsert_link",
                    source=source,
                    target=LinkTargetRef(
                        scope_path=operation.scope_path,
                        uid=operation.uid,
                        input_field=str(input_name),
                    ),
                )
                source_node = next(
                    (
                        node
                        for node in (getattr(workflow, "nodes", {}) or {}).values()
                        if str(getattr(node, "uid", "") or "")
                        == str(source.uid)
                    ),
                    None,
                )
                if source_node is not None:
                    resolved = canonical_renderer_output(
                        source_node,
                        source.output_slot,
                        provider=schema_provider,
                    )
                    if resolved is not None:
                        names, _types, _sources, _count = _frozen_output_evidence(
                            source_node, schema_provider
                        )
                        physical_slot = next(
                            (
                                index
                                for index, name in names.items()
                                if str(name) == str(resolved)
                            ),
                            None,
                        )
                        if physical_slot is not None:
                            link_op = replace(
                                link_op,
                                source=replace(source, output_slot=physical_slot),
                            )
                projected.append(link_op)
    return tuple(projected)


def _normalize_operation_output_identity(
    workflow: VibeWorkflow,
    operation: EditOp,
    schema_provider: Any,
) -> EditOp:
    """Normalize a link source through the one frozen renderer-output seam.

    Canonical graph application stores physical output indexes.  Diff/replay
    consequently spells an edge as the renderer alias ``TYPE_N`` even when
    the original author used the raw output name.  Presentation lint sees the
    raw UI name, so both spellings must resolve to that same frozen endpoint
    before classification.  Invalid aliases remain untouched and are rejected
    by lint with their original evidence.
    """
    if not isinstance(operation, UpsertLinkOp):
        return operation
    source_ref = operation.source
    if source_ref.scope_path:
        return operation
    source_node = next(
        (
            node
            for node_key, node in (getattr(workflow, "nodes", {}) or {}).items()
            if str(node_key) == str(source_ref.uid)
            or str(getattr(node, "uid", "") or "") == str(source_ref.uid)
        ),
        None,
    )
    if source_node is None:
        return operation
    if str(getattr(source_node, "class_type", "")) == _EXEC_CLASS_TYPE:
        metadata = getattr(source_node, "metadata", None) or {}
        if (
            isinstance(metadata, Mapping)
            and metadata.get("_edit_created_in_transaction") is True
        ):
            # A fresh exec's retained presentation is built from its authored
            # IO and therefore names this endpoint semantically (``image``).
            # Converting it to the captured UI spelling (``out_0``) would make
            # ordered lint reject a valid future wire against the fresh native
            # Python roster.
            authored_io, authored, valid = _exec_authored_io(source_node)
            if not authored or not valid or authored_io is None:
                return operation
            slot = str(source_ref.output_slot)
            index: int | None = None
            typed = _TYPED_PORT.fullmatch(slot)
            if typed is not None:
                candidate = int(typed.group(2))
                if (
                    0 <= candidate < len(authored_io["outputs"])
                    and typed.group(1).casefold()
                    == authored_io["outputs"][candidate][1].casefold()
                ):
                    index = candidate
            elif slot.startswith("out_") and slot[4:].isdigit():
                candidate = int(slot[4:])
                if 0 <= candidate < len(authored_io["outputs"]):
                    index = candidate
            else:
                for candidate, (name, _socket_type) in enumerate(
                    authored_io["outputs"]
                ):
                    if name == slot:
                        index = candidate
                        break
            if index is None:
                return operation
            semantic = authored_io["outputs"][index][0]
            if semantic == slot:
                return operation
            from dataclasses import replace

            return replace(
                operation,
                source=replace(source_ref, output_slot=semantic),
            )
        # A captured exec uses physical ``out_N`` UI rows.  Normalize its
        # renderer alias to that exact retained endpoint.
        from dataclasses import replace

        physical = _raw_output_slot(source_node, str(source_ref.output_slot))
        if physical == str(source_ref.output_slot):
            return operation
        return replace(
            operation,
            source=replace(source_ref, output_slot=physical),
        )
    # Literal frozen names already have canonical identity, while integer
    # slots are an established public lint normalization surface and must
    # retain their authored type.  The replay mismatch is specific to the
    # renderer's typed ``TYPE_N`` spelling.
    if not (
        isinstance(source_ref.output_slot, str)
        and _TYPED_PORT.fullmatch(source_ref.output_slot) is not None
    ):
        return operation
    resolved = canonical_renderer_output(
        source_node,
        source_ref.output_slot,
        provider=schema_provider,
    )
    if resolved is None or str(resolved) == str(source_ref.output_slot):
        return operation

    from dataclasses import replace

    return replace(
        operation,
        source=replace(source_ref, output_slot=resolved),
    )


def _lint_result_from_transitions(
    transitions: Sequence[OperationTransition],
    source_ops: Sequence[EditOp] | None = None,
) -> Any:
    """Build the immutable lint report from shared evaluator transitions."""
    from vibecomfy.porting.edit.lint import LintIssue, LintNormalization, LintResult

    issues: list[LintIssue] = []
    normalizations: list[LintNormalization] = []
    surviving: list[EditOp] = []
    for position, transition in enumerate(transitions):
        disposition = transition.lint_disposition or {
            "staged": "passed",
            "noop": "dropped_noop",
            "rejected": "rejected",
        }.get(transition.outcome, "rejected")
        issue = None
        if transition.diagnostics:
            diagnostic = transition.diagnostics[0]
            issue = LintIssue(
                code=diagnostic.code,
                message=diagnostic.message,
                severity=diagnostic.severity,
                op_index=transition.occurrence,
                op_kind=getattr(transition.submitted, "op", None),
                scope_path=diagnostic.detail.get("scope_path") if isinstance(diagnostic.detail, Mapping) else None,
                uid=diagnostic.detail.get("uid") if isinstance(diagnostic.detail, Mapping) else None,
                lg_id=diagnostic.detail.get("lg_id") if isinstance(diagnostic.detail, Mapping) else None,
                detail=dict(diagnostic.detail),
            )
            if diagnostic.severity in {"error", "warning", "info"}:
                issues.append(issue)
        normalized = transition.normalized or transition.submitted
        normalizations.append(
            LintNormalization(transition.occurrence, normalized, disposition, issue)
        )
        if disposition == "passed":
            source = (
                source_ops[position]
                if source_ops is not None and position < len(source_ops)
                else transition.submitted
            )
            surviving.append(
                source
                if normalized == transition.submitted
                else normalized
            )
    return LintResult(
        surviving=tuple(surviving),
        issues=tuple(issues),
        normalizations=tuple(normalizations),
        transitions=tuple(transitions),
    )


def _evaluate_operation(
    workflow: VibeWorkflow,
    operation: EditOp,
    *,
    schema_provider: Any,
    batch_operations: Sequence[EditOp] | None = None,
    occurrence: int = 0,
    presentation_index: Any = None,
    presentation_ui: Any = None,
    baseline_presentation_index: Any = None,
    source: str = "",
    future_wired_uids: frozenset[str] = frozenset(),
) -> OperationEvaluation:
    """Evaluate exactly one operation against the current detached cursor.

    This is the sole semantic operation boundary shared by Python, typed
    operations, and detached lint preview.  Lowering, validation, finalization
    and COW application are one atomic step; expected typed rejections return
    an unchanged cursor, while unexpected exceptions deliberately escape.
    """
    from vibecomfy.porting.edit.admit import (
        AdmissionRejected,
        admission_snapshot_for,
        admit_operation,
        _schema_provider_for,
    )
    from vibecomfy.porting.edit._ir_utils import (
        _RECURSIVE_GUIDANCE,
        RecursiveEditError,
        _operation_scope_paths,
        build_recursive_edit_index,
        lower_edit_operation,
    )
    from vibecomfy.porting.edit._op_validate import ApplyOpsError, _validate_one

    def reject(code: str, message: str, *, detail: Mapping[str, Any] | None = None) -> OperationEvaluation:
        return OperationEvaluation(
            workflow=workflow,
            normalized=operation,
            outcome="rejected",
            diagnostics=(_diag(code, message, severity="error", detail=detail or {}),),
            lint_disposition="rejected",
        )

    # Nested topology edits are outside the supported operation matrix.  This
    # semantic fence precedes presentation lint because socket/name quality is
    # irrelevant once the operation would change a derived recursive scope
    # identity; allowing the UI classifier to run first leaks incidental
    # ``unknown_*`` reasons for an operation the canonical contract rejects as
    # structural in every case.
    scoped_paths = tuple(path for path in _operation_scope_paths(operation) if path)
    scoped_paths_known = True
    if scoped_paths:
        try:
            recursive_index = build_recursive_edit_index(workflow)
            for scope_path in scoped_paths:
                recursive_index.scope(scope_path)
        except RecursiveEditError:
            scoped_paths_known = False
    if (
        scoped_paths
        and scoped_paths_known
        and not isinstance(operation, (SetNodeFieldOp, SetModeOp))
    ):
        return reject(
            "unsupported_structural_scope",
            f"{getattr(operation, 'op', type(operation).__name__)} at scope "
            f"{scoped_paths[0]!r} changes unsupported recursive structure; "
            f"{_RECURSIVE_GUIDANCE}",
            detail={
                "scope_path": scoped_paths[0],
                "operation": getattr(operation, "op", type(operation).__name__),
            },
        )

    authority = admission_snapshot_for(workflow, schema_provider)
    if authority.schema is None:
        return reject(
            "missing_schema_authority",
            "canonical operation evaluation requires a retained frozen schema snapshot",
        )
    frozen_provider = _schema_provider_for(authority)

    # Admission owns touched-schema classification.  In particular, an
    # add-node class absent from the retained generation is a canonical
    # ``missing_touched_schema`` authority failure, not presentation lint's
    # generic ``unknown_class_type``.  Check only for that fail-closed reason
    # before lint; all other admission and normalization decisions still run
    # in their established order below.  This reads the frozen snapshot pair
    # exclusively and never probes an advisory/live provider.
    schema_admission = admit_operation(
        authority,
        operation,
        working_workflow=workflow,
    )
    if (
        isinstance(schema_admission, AdmissionRejected)
        and schema_admission.typed_reason == "missing_touched_schema"
        and isinstance(operation, AddNodeOp)
        and (not scoped_paths or scoped_paths_known)
    ):
        return OperationEvaluation(
            workflow=workflow,
            normalized=operation,
            outcome="rejected",
            diagnostics=(_diag(
                schema_admission.typed_reason,
                schema_admission.typed_reason,
                severity="error",
                detail={"evidence_refs": tuple(schema_admission.evidence_refs)},
            ),),
            lint_disposition="rejected",
        )

    # Presentation lint is evidence produced at the same operation boundary
    # as canonical lowering/application.  Its rejected/no-op dispositions are
    # eligibility decisions; a surviving operation must still pass the
    # canonical validator below before it can stage.  Both decisions remain
    # visible in the transition report.
    from vibecomfy.porting.edit.lint import LintIndex, _classify_operation
    from vibecomfy.porting.emit.ui import emit_ui_json, pin_untouched_ui
    from vibecomfy.porting.refuse import RefusedEmit

    lint_candidate = _normalize_operation_output_identity(
        workflow,
        operation,
        frozen_provider,
    )

    if presentation_index is None:
        lint_ui, presentation_index, presentation_error = _capture_presentation(
            workflow, frozen_provider
        )
        if presentation_error is not None:
            return OperationEvaluation(
                workflow=workflow,
                normalized=operation,
                outcome="rejected",
                diagnostics=(presentation_error,),
                presentation_ui=None,
                presentation_index=None,
            )
    else:
        lint_ui = presentation_ui
        if lint_ui is None:
            return OperationEvaluation(
                workflow=workflow,
                normalized=operation,
                outcome="rejected",
                diagnostics=(_diag(
                    "presentation_rejected",
                    "retained presentation index has no matching UI payload",
                    severity="error",
                ),),
            )
    if lint_ui is None:
        lint_normalized, lint_issue, lint_disposition = lint_candidate, None, "passed"
    elif isinstance(operation, SubgraphInterfaceOp):
        # Subgraph interfaces mutate canonical definition metadata and have no
        # node/link presentation classifier.  They still cross this same
        # evaluator for lowering, admission, application, and projection; an
        # absent presentation rule is not a lint rejection.
        lint_normalized, lint_issue, lint_disposition = operation, None, "passed"
    else:
        if presentation_index is not None:
            lint_index = presentation_index
        else:
            lint_index = LintIndex.build(lint_ui)
        lint_normalized, lint_issue, lint_disposition = _classify_operation(
            lint_candidate,
            occurrence,
            lint_index,
            schema_provider=frozen_provider,
            workflow=workflow,
            # The classifier's orphan-add check is intentionally the one
            # batch-level exception to current-cursor evaluation: later
            # authored wiring may prove that an otherwise isolated add is
            # intentional, but it never makes a future node available to
            # canonical application.  Typed batches can supply that complete
            # syntax here while lowering/application still advance one
            # occurrence at a time against ``workflow``.
            delta=(
                tuple(batch_operations)
                if batch_operations is not None
                else (operation,)
            ),
            future_wired_uids=future_wired_uids,
        )
    lint_op = lint_normalized or operation
    lint_diags = ()
    if lint_issue is not None:
        lint_diags = (
            _diag(
                lint_issue.code,
                lint_issue.message,
                severity=lint_issue.severity,
                detail=lint_issue.detail,
            ),
        )
    if lint_disposition == "dropped_noop":
        return OperationEvaluation(
            workflow=workflow,
            normalized=lint_op,
            outcome="noop",
            diagnostics=lint_diags,
            lint_issue=lint_issue,
            lint_disposition=lint_disposition,
            presentation_ui=lint_ui,
            presentation_index=presentation_index,
        )

    # A link-id is a stable authored reference for this batch.  Once an
    # earlier occurrence has removed that edge, the current presentation
    # index quite correctly reports the id as absent; that is an ordered
    # no-op, not an unknown-link rejection.  Keep the baseline index only as
    # evidence for this transition classification (never as apply authority).
    if (
        lint_disposition == "rejected"
        and lint_issue is not None
        and lint_issue.code == "unknown_link"
        and isinstance(operation, RemoveLinkOp)
        and operation.link_id is not None
        and baseline_presentation_index is not None
        and baseline_presentation_index.link_exists("", operation.link_id)
    ):
        lint_issue = None
        lint_disposition = "dropped_noop"
        lint_diags = (_diag(
            "noop_remove_link",
            "link was already removed by an earlier occurrence in this batch",
            severity="info",
        ),)
        return OperationEvaluation(
            workflow=workflow,
            normalized=operation,
            outcome="noop",
            diagnostics=lint_diags,
            lint_issue=None,
            lint_disposition=lint_disposition,
            presentation_ui=lint_ui,
            presentation_index=presentation_index,
        )

    # A presentation-lint rejection is an eligibility decision, not merely a
    # report annotation.  Never let a rejected operation reach lowering,
    # admission, validation, canonical application, or projection.  The
    # complete-batch delta above has already had its one legitimate role in
    # preserving future orphan intent; graph authority remains current-cursor
    # only.
    if lint_disposition == "rejected":
        rejected_diags = lint_diags or (
            _diag(
                "lint_rejected",
                "canonical presentation lint rejected this operation",
                severity="error",
            ),
        )
        return OperationEvaluation(
            workflow=workflow,
            normalized=lint_op,
            outcome="rejected",
            diagnostics=rejected_diags,
            lint_issue=lint_issue,
            lint_disposition=lint_disposition,
            presentation_ui=lint_ui,
            presentation_index=presentation_index,
        )

    try:
        lowered = tuple(lower_edit_operation(workflow, lint_op))
        if not lowered:
            code = "unsupported_op"
            message = "operation lowered to no canonical effect"
            if lint_issue is not None and lint_disposition == "rejected":
                code = lint_issue.code
                message = lint_issue.message
            return OperationEvaluation(
                workflow=workflow,
                normalized=lint_op,
                lowered=(),
                outcome="rejected",
                diagnostics=lint_diags + (_diag(code, message, severity="error"),),
                lint_issue=lint_issue,
                lint_disposition=lint_disposition,
                presentation_ui=lint_ui,
                presentation_index=presentation_index,
            )
        cursor = workflow
        staged_components: list[EditOp] = []
        finalized_lowered = list(lowered)
        for component_index, component in enumerate(lowered):
            before_node_uids = {
                str(getattr(node, "uid", "") or "")
                for node in (getattr(cursor, "nodes", {}) or {}).values()
                if str(getattr(node, "uid", "") or "")
            }
            pair = admission_snapshot_for(
                cursor,
                schema_provider,
                schema_snapshot=authority.schema,
                retained_authority=authority,
            )
            admitted = admit_operation(pair, component, working_workflow=cursor)
            if isinstance(admitted, AdmissionRejected):
                if admitted.typed_reason == "no_op":
                    if len(lowered) > 1:
                        continue
                    return OperationEvaluation(
                        workflow=workflow,
                        normalized=lint_op,
                        lowered=lowered,
                        outcome="noop",
                        diagnostics=lint_diags + (_diag(
                            "no_op",
                            "operation is already represented by the current canonical cursor",
                            severity="info",
                        ),),
                        lint_issue=lint_issue,
                        lint_disposition="dropped_noop",
                        presentation_ui=lint_ui,
                        presentation_index=presentation_index,
                    )
                return OperationEvaluation(
                    workflow=workflow,
                    normalized=lint_op,
                    outcome="rejected",
                    diagnostics=lint_diags + (_diag(
                        admitted.typed_reason,
                        admitted.typed_reason,
                        severity="error",
                        detail={"evidence_refs": tuple(admitted.evidence_refs)},
                    ),),
                    lint_issue=lint_issue,
                    lint_disposition=lint_disposition,
                    presentation_ui=lint_ui,
                    presentation_index=presentation_index,
                )
            try:
                _validate_one(cursor, component, frozen_provider)
                cursor = apply_edit_cow(cursor, component, schema_provider=frozen_provider)
                # Finalize semantic add-node metadata before any projection,
                # index construction, or promotion.  The evaluator's cursor
                # is therefore identical for Python, typed, and preview
                # callers; the runner must not perform a second post-pass.
                finalized_component = component
                if isinstance(component, AddNodeOp):
                    added_key: str | None = None
                    added_node: Any | None = None
                    for node_key, node in tuple(cursor.nodes.items()):
                        node_uid = str(getattr(node, "uid", "") or "")
                        if component.uid and node_uid == str(component.uid):
                            added_key, added_node = str(node_key), node
                            break
                        if (
                            not component.uid
                            and node_uid
                            and node_uid not in before_node_uids
                            and str(getattr(node, "class_type", ""))
                            == str(component.class_type)
                        ):
                            added_key, added_node = str(node_key), node
                            break
                    if added_key is not None and added_node is not None:
                        cursor.nodes[added_key] = _stamped_node(
                            added_node, source, frozen_provider
                        )
                        # LiteGraph assigns the UID/ID during canonical COW
                        # application when the authored AddNodeOp omitted
                        # them.  Carry those minted identities into the
                        # evaluator's lowered attribution tuple; otherwise
                        # order/new-node guard checks would mistake a valid
                        # add for forged presentation drift.
                        from dataclasses import replace

                        finalized_component = replace(
                            component,
                            uid=str(getattr(added_node, "uid", "") or "") or component.uid,
                            node_id=str(getattr(added_node, "id", "") or "") or component.node_id,
                        )
                        finalized_lowered[component_index] = finalized_component
                staged_components.append(finalized_component)
            except ApplyOpsError as exc:
                if getattr(exc, "code", None) == "no_op":
                    if len(lowered) > 1:
                        continue
                    return OperationEvaluation(
                        workflow=workflow,
                        normalized=lint_op,
                        lowered=lowered,
                        outcome="noop",
                        diagnostics=lint_diags + (_diag(
                            "no_op",
                            str(exc) or "operation is already represented by the current canonical cursor",
                            severity="info",
                        ),),
                        lint_issue=lint_issue,
                        lint_disposition="dropped_noop",
                        presentation_ui=lint_ui,
                        presentation_index=presentation_index,
                    )
                raise
        if not staged_components:
            return OperationEvaluation(
                workflow=workflow,
                normalized=lint_op,
                lowered=lowered,
                outcome="noop",
                diagnostics=lint_diags + (_diag(
                    "no_op",
                    "all aggregate constituents were already set to their requested values",
                    severity="info",
                ),),
                lint_issue=lint_issue,
                lint_disposition="dropped_noop",
                presentation_ui=lint_ui,
                presentation_index=presentation_index,
            )
        guard_ops = _presentation_guard_ops(
            cursor,
            tuple(staged_components),
            frozen_provider,
        )
        if lint_ui is not None:
            try:
                candidate_ui = emit_ui_json(
                    cursor,
                    schema_provider=frozen_provider,
                    include_virtual_wires=True,
                    # Preserve the retained presentation furniture while
                    # projecting the detached cursor.  The supplied payload
                    # remains evidence; it is never used as semantic state.
                    prior_ui_payload=lint_ui,
                )
            except RefusedEmit as exc:
                return OperationEvaluation(
                    workflow=workflow,
                    normalized=lint_op,
                    lowered=lowered,
                    outcome="rejected",
                    diagnostics=lint_diags + (_diag(
                        "presentation_rejected",
                        f"canonical candidate presentation was refused: {exc}",
                        severity="error",
                    ),),
                    lint_issue=lint_issue,
                    lint_disposition=lint_disposition,
                    presentation_ui=None,
                    presentation_index=None,
                )
            if candidate_ui is not None:
                # Reconstructive emission may hydrate untouched sockets from a
                # schema and thereby rewrite presentation-only bytes (for
                # example an existing input type ``IMAGE`` becoming ``*``).
                # Pin the retained ingest projection before the strict guard;
                # only the exact topology paths owned by the lowered ops may
                # differ.  This is still one projection/evaluation boundary,
                # not a second semantic authority.
                candidate_ui = pin_untouched_ui(
                    lint_ui,
                    candidate_ui,
                    guard_ops,
                )
                candidate_index = LintIndex.build(candidate_ui)
                presentation_guard = _canonical_guard_exit_ui(
                    lint_ui,
                    candidate_ui,
                    # Attribute the emitted projection to the canonical
                    # lowered edits, not a presentation alias (for example a
                    # widget_N spelling or a link id).  The guard must see
                    # the same exact endpoint/field identity that was
                    # applied to the cursor.
                    guard_ops,
                )
                if not presentation_guard.ok:
                    guard_diags = tuple(
                        _diag(
                            getattr(issue, "code", "presentation_rejected"),
                            getattr(issue, "message", str(issue)),
                            severity=getattr(issue, "severity", "error") or "error",
                        )
                        for issue in presentation_guard.diagnostics
                    )
                    return OperationEvaluation(
                        workflow=workflow,
                        normalized=lint_op,
                        lowered=lowered,
                        outcome="rejected",
                        diagnostics=lint_diags + guard_diags,
                        lint_issue=lint_issue,
                        lint_disposition=lint_disposition,
                        presentation_ui=candidate_ui,
                        presentation_index=candidate_index,
                    )
        else:
            candidate_ui = None
            candidate_index = None
        return OperationEvaluation(
            workflow=cursor,
            normalized=lint_op,
            # Preserve the complete authored aggregate mapping in the report;
            # unchanged constituents are intentionally admitted but simply do
            # not allocate another COW write.
            lowered=tuple(finalized_lowered),
            outcome="staged",
            diagnostics=lint_diags,
            lint_issue=lint_issue,
            lint_disposition=lint_disposition,
            presentation_ui=candidate_ui,
            presentation_index=candidate_index,
        )
    except (RecursiveEditError, ApplyOpsError) as exc:
        code = getattr(exc, "code", None) or getattr(exc, "typed_reason", None) or "apply_rejected"
        message = getattr(exc, "message", None) or str(exc)
        return OperationEvaluation(
            workflow=workflow,
            normalized=lint_op,
            lowered=lowered if "lowered" in locals() else (),
            outcome="rejected",
            diagnostics=lint_diags + (_diag(code, message, severity="error"),),
            lint_issue=lint_issue,
            lint_disposition=lint_disposition,
            presentation_ui=lint_ui,
            presentation_index=presentation_index,
        )
    except EditNoOpError as exc:
        return OperationEvaluation(
            workflow=workflow,
            normalized=lint_op,
            lowered=lowered if "lowered" in locals() else (),
            outcome="noop",
            diagnostics=lint_diags + (_diag("no_op", str(exc), severity="info"),),
            lint_issue=lint_issue,
            lint_disposition="dropped_noop",
            presentation_ui=lint_ui,
            presentation_index=presentation_index,
        )


def _workflow_node_classes(workflow: VibeWorkflow) -> dict[str, str]:
    classes: dict[str, str] = {}
    for node_id, node in workflow.nodes.items():
        class_type = str(getattr(node, "class_type", "") or "")
        if not class_type:
            continue
        classes[str(node_id)] = class_type
        uid = str(getattr(node, "uid", "") or "")
        if uid:
            classes[uid] = class_type
    return classes


def _touched_classes_for_interpret(
    workflow: VibeWorkflow,
    batch_source: str | Sequence[EditOp],
    snapshot: Any,
    *,
    catalog: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    """Return the delta-bounded class closure needed before admission."""
    node_classes = dict(getattr(snapshot, "node_classes", {}) or {})
    node_classes.update(_workflow_node_classes(workflow))
    touched: set[str] = set()
    if not isinstance(batch_source, str):
        from vibecomfy.schema.types import touched_schema_classes

        catalog = {
            "schemas": dict(getattr(snapshot, "schemas", {}) or {}),
            "missing_classes": list(getattr(snapshot, "missing_classes", ()) or ()),
            "node_classes": node_classes,
        }
        for operation in batch_source:
            explicit_class = getattr(operation, "class_type", None)
            if isinstance(explicit_class, str) and explicit_class:
                touched.add(explicit_class)
            touched.update(touched_schema_classes(operation, catalog))
        return tuple(sorted(touched))

    # Python-surface names are a deterministic projection of the current IR.
    # Select only graph names actually present in the submitted source.  Node
    # constructors are resolved below against the authoritative catalog.
    try:
        module = ast.parse(batch_source, mode="exec")
        names = {node.id for node in ast.walk(module) if isinstance(node, ast.Name)}
        emitted = _compute_variable_names(workflow.nodes, list(workflow.edges))
        for node_id, name in emitted.items():
            if name in names and str(node_id) in workflow.nodes:
                touched.add(str(workflow.nodes[str(node_id)].class_type))
        if catalog:
            from vibecomfy.porting.authoring_names import (
                constructor_aliases_for_class_types,
            )

            aliases = {
                alias: class_type
                for class_type, alias in constructor_aliases_for_class_types(
                    str(class_type) for class_type in catalog
                ).items()
            }
            for call in (node for node in ast.walk(module) if isinstance(node, ast.Call)):
                if (
                    isinstance(call.func, ast.Name)
                    and call.func.id == "node"
                    and call.args
                ):
                    raw = call.args[0]
                    if isinstance(raw, ast.Constant) and isinstance(raw.value, str):
                        touched.add(raw.value)
                    continue
                constructor = None
                if isinstance(call.func, ast.Name):
                    constructor = call.func.id
                elif (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "vibecomfy"
                ):
                    constructor = call.func.attr
                if constructor in catalog:
                    touched.add(str(constructor))
                elif constructor in aliases:
                    touched.add(aliases[str(constructor)])
    except (SyntaxError, AttributeError, KeyError, TypeError, ValueError):
        pass
    return tuple(sorted(touched))


def _frozen_provider_for_interpret(
    schema_provider: Any,
    *,
    pre_workflow: VibeWorkflow,
    batch_source: str | Sequence[EditOp],
) -> Any | None:
    """Freeze and delta-bound available catalog authority for interpretation."""
    from vibecomfy.schema import FrozenSchemaSnapshotProvider, SchemaSnapshot

    if schema_provider is None:
        return None
    frozen_provider = (
        schema_provider
        if isinstance(schema_provider, FrozenSchemaSnapshotProvider)
        else None
    )
    if isinstance(schema_provider, SchemaSnapshot):
        return FrozenSchemaSnapshotProvider(schema_provider)
    snapshot = getattr(schema_provider, "snapshot", None)
    if not isinstance(snapshot, SchemaSnapshot):
        snapshot = None

    frozen_catalog = getattr(schema_provider, "_frozen_schema_catalog", None)
    catalog_error = getattr(schema_provider, "_frozen_schema_catalog_error", None)
    catalog_provider = schema_provider
    catalog = dict(frozen_catalog) if isinstance(frozen_catalog, Mapping) else None
    schemas = getattr(catalog_provider, "schemas", None)
    if catalog is None and callable(schemas):
        try:
            catalog = schemas()
        except Exception as exc:
            catalog = None
            catalog_error = f"{type(exc).__name__}: {exc}"
    touched = (
        _touched_classes_for_interpret(
            pre_workflow,
            batch_source,
            snapshot,
            catalog=catalog,
        )
        if snapshot is not None
        else ()
    )
    unresolved_touched = (
        tuple(class_type for class_type in touched if class_type not in snapshot.schemas)
        if snapshot is not None
        else ()
    )
    if unresolved_touched and isinstance(catalog_error, str) and catalog_error:
        provider = frozen_provider or FrozenSchemaSnapshotProvider(snapshot)
        provider._frozen_schema_catalog_error = catalog_error
        provider._frozen_schema_catalog_issue = {
            "code": "schema_provider_error",
            "message": (
                "authoritative schema catalog failed while resolving touched "
                "class(es): " + ", ".join(unresolved_touched)
            ),
            "provider_error": catalog_error,
            "class_types": unresolved_touched,
        }
        return provider
    if isinstance(catalog, Mapping) and catalog:
        from vibecomfy.schema.types import (
            _complete_schema_snapshot_with_authoritative_catalog,
            capture_schema_snapshot,
            schema_payload_from_node_schema,
        )

        if snapshot is not None:
            mismatched: list[str] = []
            for class_type in unresolved_touched:
                candidate = catalog.get(class_type)
                if candidate is None:
                    continue
                try:
                    payload = schema_payload_from_node_schema(class_type, candidate)
                except Exception:
                    mismatched.append(class_type)
                    continue
                if (
                    getattr(candidate, "class_type", None) != class_type
                    or payload.get("class_type") != class_type
                ):
                    mismatched.append(class_type)
            if mismatched:
                provider = frozen_provider or FrozenSchemaSnapshotProvider(snapshot)
                provider._frozen_schema_catalog = dict(catalog)
                provider._frozen_schema_catalog_issue = {
                    "code": "schema_admission_mismatch",
                    "message": (
                        "authoritative catalog entries did not match their "
                        "touched class identity: " + ", ".join(mismatched)
                    ),
                    "class_types": tuple(mismatched),
                }
                return provider
            completed = _complete_schema_snapshot_with_authoritative_catalog(
                snapshot,
                catalog,
                class_types=touched,
                node_classes=_workflow_node_classes(pre_workflow),
            )
            provider = FrozenSchemaSnapshotProvider(completed)
            provider._frozen_schema_catalog = dict(catalog)
            return provider

        payload: dict[str, Any] = {}
        for key, value in catalog.items():
            if value is None:
                continue
            try:
                payload[str(key)] = schema_payload_from_node_schema(str(key), value)
            except Exception:
                continue
        if payload:
            provider = FrozenSchemaSnapshotProvider(
                capture_schema_snapshot(
                    class_types=tuple(payload),
                    request_snapshot={
                        "schemas": payload,
                        "missing_classes": [],
                    },
                )
            )
            provider._frozen_schema_catalog = dict(catalog)
            return provider
    if frozen_provider is not None:
        return frozen_provider
    if snapshot is not None:
        return FrozenSchemaSnapshotProvider(snapshot)
    return None


def _missing_schema_interpretation(
    pre_workflow: VibeWorkflow,
    batch_source: str | Sequence[EditOp],
) -> InterpretationResult:
    """Fail before presentation/parsing can consult ambient schema state."""
    diagnostic = _diag(
        "missing_schema_authority",
        "interpret requires a retained frozen schema snapshot",
        severity="error",
    )
    operations = () if isinstance(batch_source, str) else tuple(batch_source)
    transitions = tuple(
        OperationTransition(
            occurrence=index,
            submitted=operation,
            normalized=operation,
            outcome="rejected",
            diagnostics=(diagnostic,),
            lint_disposition="rejected",
        )
        for index, operation in enumerate(operations)
    )
    return InterpretationResult(
        workflow=_cow_workflow_copy(pre_workflow),
        statements=tuple(
            StatementOutcome(
                statement_index=index,
                source=type(operation).__name__,
                status="rejected",
                reason=diagnostic.code,
                op_kind=getattr(operation, "op", type(operation).__name__),
                diagnostics=(diagnostic,),
                op=operation,
            )
            for index, operation in enumerate(operations)
        ),
        ok=False,
        diagnostics=(diagnostic,),
        landed_ops=(),
        preflight_ok=False,
        transitions=transitions,
        lint_result=_lint_result_from_transitions(transitions),
        occurrence_to_statement_index={
            transition.occurrence: transition.statement_index
            for transition in transitions
        },
    )


def _schema_catalog_issue_interpretation(
    pre_workflow: VibeWorkflow,
    batch_source: str | Sequence[EditOp],
    issue: Mapping[str, Any],
) -> InterpretationResult:
    """Reject a provider/mismatch failure distinctly and atomically."""
    code = str(issue.get("code") or "schema_provider_error")
    message = str(issue.get("message") or code)
    diagnostic = _diag(
        code,
        message,
        severity="error",
        detail={
            key: value
            for key, value in issue.items()
            if key not in {"code", "message"}
        },
    )
    operations = () if isinstance(batch_source, str) else tuple(batch_source)
    transitions = tuple(
        OperationTransition(
            occurrence=index,
            submitted=operation,
            normalized=operation,
            outcome="rejected",
            diagnostics=(diagnostic,),
            lint_disposition="rejected",
        )
        for index, operation in enumerate(operations)
    )
    return InterpretationResult(
        workflow=_cow_workflow_copy(pre_workflow),
        statements=tuple(
            StatementOutcome(
                statement_index=index,
                source=type(operation).__name__,
                status="rejected",
                reason=code,
                op_kind=getattr(operation, "op", type(operation).__name__),
                diagnostics=(diagnostic,),
                op=operation,
            )
            for index, operation in enumerate(operations)
        ),
        ok=False,
        diagnostics=(diagnostic,),
        landed_ops=(),
        preflight_ok=False,
        transitions=transitions,
        lint_result=_lint_result_from_transitions(transitions),
        occurrence_to_statement_index={
            transition.occurrence: transition.statement_index
            for transition in transitions
        },
    )


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
    value_default_context: Any = None,
) -> InterpretationResult:
    """Interpret ``batch_source`` against ``pre_workflow``, returning a NEW IR.

    Pure: the input workflow is never mutated.  ``batch_source`` is either
    Python surface text or an already-lowered op sequence (Law 3).
    """
    if not isinstance(pre_workflow, VibeWorkflow):
        raise TypeError(
            f"interpret requires VibeWorkflow, got {type(pre_workflow).__name__}"
        )
    provider = _frozen_provider_for_interpret(
        schema_provider,
        pre_workflow=pre_workflow,
        batch_source=batch_source,
    )
    if provider is None:
        return _missing_schema_interpretation(pre_workflow, batch_source)
    catalog_issue = getattr(provider, "_frozen_schema_catalog_issue", None)
    if isinstance(catalog_issue, Mapping):
        return _schema_catalog_issue_interpretation(
            pre_workflow, batch_source, catalog_issue
        )
    if not isinstance(batch_source, str):
        result = _interpret_ops(
            pre_workflow,
            tuple(batch_source),
            schema_provider=provider,
            value_default_context=value_default_context,
        )
    else:
        result = _interpret_source(
            pre_workflow,
            batch_source,
            schema_provider=provider,
            max_batch_bytes=max_batch_bytes,
            max_statements=max_statements,
            max_expanded_statements=max_expanded_statements,
            max_for_iterations=max_for_iterations,
            cas_old=cas_old,
            name_hints=name_hints,
            value_default_context=value_default_context,
        )
    return replace(result, schema_provider=provider)


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
    value_default_context: Any,
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
        value_default_context=value_default_context,
    )
    return runner.run(parsed.expanded)


def _interpret_ops(
    pre_workflow: VibeWorkflow,
    ops: tuple[EditOp, ...],
    *,
    schema_provider: Any,
    value_default_context: Any = None,
) -> InterpretationResult:
    """Interpret already-typed operations through the shared boundary."""
    from vibecomfy.porting.edit._ir_utils import _RECURSIVE_GUIDANCE, _has_mixed_recursive_scope

    if _has_mixed_recursive_scope(ops):
        diagnostic = _diag(
            "unsupported_structural_scope",
            f"mixed root and nested scopes are unsupported; {_RECURSIVE_GUIDANCE}",
            severity="error",
        )
        return InterpretationResult(
            workflow=_cow_workflow_copy(pre_workflow),
            statements=(),
            ok=False,
            diagnostics=(diagnostic,),
            landed_ops=(),
        )
    cursor = _cow_workflow_copy(pre_workflow)
    context_cursor = value_default_context
    presentation_ui, presentation_index, presentation_error = _capture_presentation(
        cursor, schema_provider
    )
    if presentation_error is not None:
        return InterpretationResult(
            workflow=_cow_workflow_copy(pre_workflow),
            statements=tuple(
                StatementOutcome(
                    statement_index=index,
                    source=type(operation).__name__,
                    status="rejected",
                    reason=presentation_error.code,
                    op_kind=getattr(operation, "op", type(operation).__name__),
                    diagnostics=(presentation_error,),
                    op=operation,
                )
                for index, operation in enumerate(ops)
            ),
            ok=False,
            diagnostics=(presentation_error,),
            landed_ops=(),
        )
    baseline_presentation_index = presentation_index
    outcomes: list[StatementOutcome] = []
    landed: list[EditOp] = []
    diagnostics: list[CompactDiagnostic] = []
    transitions: list[OperationTransition] = []
    failed = False
    for index, operation in enumerate(ops):
        effective_operation, next_context, value_diagnostics, value_error = (
            _prepare_value_default_operation(
                cursor,
                operation,
                schema_provider=schema_provider,
                context=context_cursor,
            )
        )
        if value_error is not None:
            evaluation = OperationEvaluation(
                workflow=cursor,
                normalized=operation,
                outcome="rejected",
                diagnostics=(value_error,),
                lint_disposition="rejected",
                presentation_ui=presentation_ui,
                presentation_index=presentation_index,
            )
        else:
            evaluation = _evaluate_operation(
                cursor,
                effective_operation,
                schema_provider=schema_provider,
                batch_operations=ops,
                occurrence=index,
                presentation_ui=presentation_ui,
                presentation_index=presentation_index,
                baseline_presentation_index=baseline_presentation_index,
            )
            if value_diagnostics:
                evaluation = OperationEvaluation(
                    workflow=evaluation.workflow,
                    normalized=evaluation.normalized,
                    lowered=evaluation.lowered,
                    outcome=evaluation.outcome,
                    diagnostics=tuple(value_diagnostics) + tuple(evaluation.diagnostics),
                    lint_issue=evaluation.lint_issue,
                    lint_disposition=evaluation.lint_disposition,
                    presentation_ui=evaluation.presentation_ui,
                    presentation_index=evaluation.presentation_index,
                )
        diagnostics.extend(evaluation.diagnostics)
        transitions.append(OperationTransition(
            occurrence=index,
            submitted=operation,
            normalized=evaluation.normalized,
            lowered=evaluation.lowered,
            outcome=evaluation.outcome,
            diagnostics=evaluation.diagnostics,
            lint_disposition=evaluation.lint_disposition,
        ))
        if evaluation.outcome == "staged":
            effective_operation = (
                evaluation.lowered[0]
                if len(evaluation.lowered) == 1
                else evaluation.normalized
            )
            apply_diags = _apply_diagnostics(cursor, evaluation.workflow, effective_operation)
            diagnostics.extend(apply_diags)
            cursor = evaluation.workflow
            context_cursor = next_context
            presentation_ui = evaluation.presentation_ui
            presentation_index = evaluation.presentation_index
            landed.append(effective_operation)
            outcomes.append(StatementOutcome(
                statement_index=index,
                source=type(operation).__name__,
                status="applied",
                op_kind=getattr(operation, "op", type(operation).__name__),
                op=effective_operation,
                diagnostics=apply_diags,
            ))
        elif evaluation.outcome == "noop":
            outcomes.append(StatementOutcome(
                statement_index=index,
                source=type(operation).__name__,
                status="skipped",
                reason="no_op",
                op_kind=getattr(operation, "op", type(operation).__name__),
                diagnostics=evaluation.diagnostics,
                op=operation,
            ))
        else:
            failed = True
            outcomes.append(StatementOutcome(
                statement_index=index,
                source=type(operation).__name__,
                status="rejected",
                reason=(evaluation.diagnostics[0].code if evaluation.diagnostics else "apply_rejected"),
                op_kind=getattr(operation, "op", type(operation).__name__),
                diagnostics=evaluation.diagnostics,
                op=operation,
            ))
    if failed:
        rollback_diag = _diag(
            "batch_transaction_rolled_back",
            "A later edit statement failed, so all edits from this batch were rolled back.",
            severity="error",
        )
        rolled = tuple(
            StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="rejected" if item.status == "applied" else item.status,
                reason="batch_transaction_rolled_back" if item.status == "applied" else item.reason,
                op_kind=item.op_kind,
                diagnostics=item.diagnostics + ((rollback_diag,) if item.status == "applied" else ()),
                op=item.op,
                detail=dict(item.detail),
            )
            for item in outcomes
        )
        return InterpretationResult(
            workflow=_cow_workflow_copy(pre_workflow),
            statements=rolled,
            ok=False,
            diagnostics=tuple(diagnostics) + (rollback_diag,),
            landed_ops=(),
            transitions=tuple(transitions),
            lint_result=_lint_result_from_transitions(tuple(transitions)),
            occurrence_to_statement_index={
                transition.occurrence: transition.statement_index
                for transition in transitions
            },
        )
    return InterpretationResult(
        workflow=cursor,
        statements=tuple(outcomes),
        ok=True,
        diagnostics=tuple(diagnostics),
        landed_ops=tuple(landed),
        transitions=tuple(transitions),
        lint_result=_lint_result_from_transitions(tuple(transitions)),
        occurrence_to_statement_index={
            transition.occurrence: transition.statement_index
            for transition in transitions
        },
        value_default_context=context_cursor,
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


def _prepare_value_default_operation(
    workflow: VibeWorkflow,
    operation: EditOp,
    *,
    schema_provider: Any,
    context: Any,
) -> tuple[EditOp, Any, tuple[CompactDiagnostic, ...], CompactDiagnostic | None]:
    """Resolve the explicit default context into one canonical typed op.

    This runs inside ``interpret`` before the shared operation evaluator.  Its
    result is therefore the operation admitted, validated, replayed, and
    published; the session never rewrites a post-state or UI representation.
    """
    from dataclasses import replace

    from vibecomfy.porting.edit.value_defaults import (
        VALUE_DEFAULT_FIELDS_MARKER,
        authorize_protected_value_change,
        bind_add_node_value_defaults,
    )

    if context is None or not getattr(context, "active", False):
        return operation, context, (), None
    if isinstance(operation, AddNodeOp):
        schema = schema_for(schema_provider, operation.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        existing_marker = operation.fields.get(VALUE_DEFAULT_FIELDS_MARKER)
        if existing_marker is not None:
            if (
                operation.uid is None
                or operation.node_id is None
                or not isinstance(existing_marker, (list, tuple))
                or not all(isinstance(field, str) and field for field in existing_marker)
                or any(field not in schema_inputs for field in existing_marker)
            ):
                return operation, context, (), _diag(
                    "invalid_value_default_replay_marker",
                    "value-default protection is valid only on a canonical landed add-node operation",
                    severity="error",
                )
            return (
                operation,
                context.protect_node(
                    scope_path=operation.scope_path,
                    uid=str(operation.uid),
                    class_type=operation.class_type,
                    fields=tuple(existing_marker),
                ),
                (),
                None,
            )
        if schema is None:
            return operation, context, (), None
        uid = str(operation.uid or "")
        fields, receipts, next_context, warning_records = bind_add_node_value_defaults(
            class_type=operation.class_type,
            scope_path=operation.scope_path,
            uid=uid,
            proposed_fields=operation.fields,
            schema_inputs=schema_inputs,
            context=context,
        )
        diagnostics = [
            _diag(
                str(record["code"]),
                str(record["message"]),
                severity="warning",
                detail=record.get("detail", {}),
            )
            for record in warning_records
        ]
        diagnostics.extend(
            _diag(
                "value_default_binding_receipt",
                f"Bound {receipt.class_type}.{receipt.canonical_field} from {receipt.provenance} authority.",
                severity="info",
                detail=receipt.to_dict(),
            )
            for receipt in receipts
        )
        if receipts:
            fields[VALUE_DEFAULT_FIELDS_MARKER] = tuple(
                receipt.canonical_field for receipt in receipts
            )
        return replace(operation, fields=fields), next_context, tuple(diagnostics), None
    if not isinstance(operation, SetNodeFieldOp):
        return operation, context, (), None
    node = next(
        (
            candidate
            for candidate in workflow.nodes.values()
            if str(getattr(candidate, "uid", "") or "") == str(operation.target.uid)
        ),
        None,
    )
    if node is None:
        return operation, context, (), None
    class_type = str(getattr(node, "class_type", "") or "")
    field_name = str(operation.target.field_path)
    if not context.protects(
        operation.target.scope_path,
        str(operation.target.uid),
        class_type,
        field_name,
    ):
        return operation, context, (), None
    schema = schema_for(schema_provider, class_type)
    spec = _input_spec_for_field(getattr(schema, "inputs", {}) or {}, field_name)
    old_value = _current_field_value(node, field_name)
    receipt = authorize_protected_value_change(
        context=context,
        scope_path=operation.target.scope_path,
        uid=str(operation.target.uid),
        class_type=class_type,
        field_name=field_name,
        old_value=old_value,
        new_value=operation.value,
        spec=spec,
    )
    if receipt is None:
        return operation, context, (), _diag(
            "unauthorized_set_node_field_override",
            (
                f"{class_type}.{field_name} is protected by value-default binding; "
                "a different value requires an exact user or schema-correction receipt."
            ),
            severity="error",
            detail={
                "scope_path": operation.target.scope_path,
                "uid": str(operation.target.uid),
                "class_type": class_type,
                "field": field_name,
                "old_value": old_value,
                "proposed_value": operation.value,
            },
        )
    return operation, context, (
        _diag(
            "value_default_edit_receipt",
            "Protected widget edit applied with an authority receipt.",
            severity="info",
            detail=receipt.to_dict(),
        ),
    ), None


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
        value_default_context: Any = None,
    ) -> None:
        self._pre = pre_workflow
        self.workflow = _cow_workflow_copy(pre_workflow)
        self.schema_provider = schema_provider
        self.cas_old = dict(cas_old or {})
        self._source = source
        self._source_lines = source.splitlines()
        self._initial_value_default_context = value_default_context
        self.value_default_context = value_default_context
        self.unbound: set[str] = set()
        self.transient: dict[str, str] = dict(name_hints or {})
        # Names are uid-anchored for this interpreter/batch.  Once a live
        # binding disappears its spelling is retired rather than reassigned to
        # a different surviving node after class+order renumbering.
        self._retired_name_uids: dict[str, str] = {}
        self._pending_apply_diagnostics: list[CompactDiagnostic] = []
        self._transitions: list[OperationTransition] = []
        self._occurrence_to_statement_index: dict[int, int] = {}
        self._last_transition: OperationTransition | None = None
        self._last_effective_op: EditOp | None = None
        self._future_wired_uids: frozenset[str] = frozenset()
        self._planned_add_uids: dict[int, str] = {}
        self._pre_helper_uids = {
            str(node.uid)
            for node in pre_workflow.nodes.values()
            if str(getattr(node, "uid", "") or "")
            and str(node.class_type) in HELPER_NODE_TYPES
        }
        # P0-WIDGET-CANON: sealed snapshot table is the sole name authority
        # for widget_N → canonical-name canonicalization in this batch.
        from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid  # noqa: PLC0415

        self.name_authority = frozen_widget_names_by_uid(pre_workflow)
        (
            self._presentation_ui,
            self._presentation_index,
            self._presentation_error,
        ) = _capture_presentation(self.workflow, schema_provider)
        self._baseline_presentation_index = self._presentation_index
        self._refresh_bindings()
        self.placement_facts = None

    def run(self, statements: tuple[_ExpandedStatement, ...]) -> InterpretationResult:
        from vibecomfy.porting.layout.placement import build_batch_placement_facts

        if self._presentation_error is not None:
            diagnostic = self._presentation_error
            return InterpretationResult(
                workflow=_cow_workflow_copy(self._pre),
                statements=tuple(
                    StatementOutcome(
                        statement_index=item.statement_index,
                        source=item.source,
                        status="rejected",
                        reason=diagnostic.code,
                        op_kind=item.op_kind,
                        diagnostics=(diagnostic,),
                    )
                    for item in statements
                ),
                ok=False,
                diagnostics=(diagnostic,),
                landed_ops=(),
                value_default_context=self._initial_value_default_context,
            )

        # Parse-only evidence for the orphan-add classifier. Plan the same
        # deterministic uid that _add_node will use for an unstamped
        # constructor, then associate later graph-reference attributes by the
        # assignment name. This never resolves or applies the future
        # statement; current-cursor authority and transactional rollback
        # remain unchanged.
        add_uid_by_name: dict[str, str] = {}
        referenced_names: set[str] = set()
        reserved_uids = {
            str(getattr(node, "uid", "") or "")
            for node in self.workflow.nodes.values()
            if str(getattr(node, "uid", "") or "")
        }
        highest_minted_uid = max(
            (
                int(uid[1:])
                for uid in reserved_uids
                if uid.startswith("n") and uid[1:].isdigit()
            ),
            default=0,
        )
        for item in statements:
            node = item.node
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                uid = self._uid_from_lines(item)
                if uid is None:
                    highest_minted_uid += 1
                    uid = f"n{highest_minted_uid}"
                    while uid in reserved_uids:
                        highest_minted_uid += 1
                        uid = f"n{highest_minted_uid}"
                elif uid.startswith("n") and uid[1:].isdigit():
                    highest_minted_uid = max(highest_minted_uid, int(uid[1:]))
                reserved_uids.add(uid)
                self._planned_add_uids[id(item)] = uid
                add_uid_by_name[node.targets[0].id] = uid
            if isinstance(node, ast.Assign):
                target = node.targets[0] if len(node.targets) == 1 else None
                if (
                    _is_graph_reference_value(node.value)
                    and isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                ):
                    referenced_names.add(target.value.id)
                for child in ast.walk(node.value):
                    if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
                        referenced_names.add(child.value.id)
        self._future_wired_uids = frozenset(
            uid for name, uid in add_uid_by_name.items() if name in referenced_names
        )

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
            self._last_transition = None
            outcome = self._run_one(item)
            outcomes.append(outcome)
            if self._last_transition is not None:
                self._transitions.append(self._last_transition)
                self._occurrence_to_statement_index[
                    self._last_transition.occurrence
                ] = item.statement_index
            diagnostics.extend(outcome.diagnostics)
            diagnostics.extend(self._pending_apply_diagnostics)
            self._pending_apply_diagnostics.clear()
            is_edit = outcome.op_kind not in {None, "query", "done", "statement"}
            if outcome.status == "applied" and is_edit:
                saw_landed_edit = True
                if outcome.op is not None:
                    landed.append(outcome.op)
                continue
            if outcome.status == "skipped" and outcome.reason == "cas_unchanged":
                # A repeated occurrence is accounted for in transitions but
                # never becomes a durable landed operation.
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
                transitions=tuple(self._transitions),
                lint_result=_lint_result_from_transitions(tuple(self._transitions)),
                occurrence_to_statement_index=dict(self._occurrence_to_statement_index),
                value_default_context=self._initial_value_default_context,
            )
        ok = not any(
            outcome.status == "rejected"
            and outcome.op_kind not in {None, "query", "done"}
            for outcome in outcomes
        ) and not any(diag.severity == "error" for diag in diagnostics)
        lint_result = _lint_result_from_transitions(tuple(self._transitions))
        return InterpretationResult(
            workflow=self.workflow,
            statements=tuple(outcomes),
            ok=ok,
            diagnostics=_published_diagnostics(diagnostics),
            landed_ops=tuple(landed),
            transitions=tuple(self._transitions),
            lint_result=lint_result,
            occurrence_to_statement_index=dict(self._occurrence_to_statement_index),
            value_default_context=self.value_default_context,
        )

    def _run_one(self, item: _ExpandedStatement) -> StatementOutcome:
        statement = item.node
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call_name = _call_id(statement.value)
            if call_name == "subgraph_interface":
                return self._subgraph_interface(item, statement.value)
            if call_name in ("search", "node_schema"):
                try:
                    from vibecomfy.porting.edit._ir_utils import _resolve_class_type_from_alias
                    from vibecomfy.schema.provider import schema_for as _s1_schema_for
                    if call_name == "search":
                        focus = None
                        for kw in statement.value.keywords:
                            if kw.arg == "focus_types":
                                try:
                                    val, _ = _fold_constant(kw.value, env=item.env)
                                    if isinstance(val, (list, tuple)):
                                        focus = [str(v) for v in val if isinstance(v, str) and v]
                                except Exception:
                                    pass
                        if focus:
                            for ct in focus:
                                try:
                                    _s1_schema_for(self.schema_provider, ct)
                                    try:
                                        resolved = _resolve_class_type_from_alias(ct, self.schema_provider)
                                        if resolved and resolved != ct:
                                            _s1_schema_for(self.schema_provider, resolved)
                                        lower = ct.lower()
                                        if lower != ct:
                                            _s1_schema_for(self.schema_provider, lower)
                                            rl = _resolve_class_type_from_alias(lower, self.schema_provider)
                                            if rl and rl != lower:
                                                _s1_schema_for(self.schema_provider, rl)
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                    else:
                        arg_val = None
                        if statement.value.args:
                            try:
                                arg_val, _ = _fold_constant(statement.value.args[0], env=item.env)
                            except Exception:
                                pass
                        else:
                            for kw in statement.value.keywords:
                                if kw.arg in ("node_class", "class_type", "type"):
                                    try:
                                        arg_val, _ = _fold_constant(kw.value, env=item.env)
                                    except Exception:
                                        pass
                        if isinstance(arg_val, str) and arg_val:
                            try:
                                _s1_schema_for(self.schema_provider, arg_val)
                                try:
                                    resolved = _resolve_class_type_from_alias(arg_val, self.schema_provider)
                                    if resolved and resolved != arg_val:
                                        _s1_schema_for(self.schema_provider, resolved)
                                    lower = arg_val.lower()
                                    if lower != arg_val:
                                        _s1_schema_for(self.schema_provider, lower)
                                except Exception:
                                    pass
                            except Exception:
                                pass
                except Exception:
                    pass
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
            # A live provider cannot establish the canonical touched-schema
            # closure.  Fail at the frozen-authority boundary so callers see
            # the custody failure, rather than laundering it into an
            # ``unknown_add_node_class_type`` parse diagnostic.
            if not _has_frozen_schema_authority(self.schema_provider):
                return self._reject(
                    item,
                    "missing_schema_authority",
                    "node_call",
                    "add_node requires a retained frozen schema snapshot.",
                )
            # The frozen provider's catalog absence is itself touched-schema
            # evidence.  Preserve the authored class on an AddNodeOp and let
            # the shared evaluator/admission boundary produce the canonical
            # typed reason.  Looking at an advisory provider here would make
            # the result depend on mutable post-ingress state.
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
            if reserved_kwarg_is_coordinate_hint(
                name, value=keyword.value, schema_inputs=schema_inputs
            ):
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
        # Frozen schema snapshots retain the raw positional input order even
        # when reconstructed ``NodeSchema.inputs`` deliberately exposes only
        # named socket/widget fields. Preserve an explicitly authored
        # ``widget_N`` carrier as widget-channel evidence for the one shared
        # lowerer; do not infer arbitrary fields from the UI payload.
        if not widget_field_names:
            snapshot = getattr(self.schema_provider, "snapshot", None)
            raw_schema = (
                snapshot.schemas.get(class_type)
                if snapshot is not None and isinstance(getattr(snapshot, "schemas", None), Mapping)
                else None
            )
            raw_order = raw_schema.get("input_order") if isinstance(raw_schema, Mapping) else ()
            if isinstance(raw_order, (list, tuple)):
                widget_field_names = tuple(
                    name for name in fields
                    if isinstance(name, str)
                    and name.startswith("widget_")
                    and name in raw_order
                )
        uid = (
            _uid_from_source(item.source)
            or self._uid_from_lines(item)
            or self._planned_add_uids.get(id(item))
            or _mint_ir_uid(self.workflow)
        )
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
        self._refresh_bindings()
        return StatementOutcome(
            statement_index=item.statement_index,
            source=item.source,
            status="applied",
            op_kind="node_call",
            op=self._last_effective_op or op,
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
        target_name = target.value.id if isinstance(target.value, ast.Name) else ""
        return self._set_field(item, node, target_name, field_name, rhs)

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
        op = SetModeOp(op="set_mode", target=NodeTarget("", str(node.uid)), mode=mode)  # type: ignore[arg-type]
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
        target_name: str,
        field_name: str,
        rhs: ast.expr,
    ) -> StatementOutcome:
        # Positional widget aliases are an ingest carrier, never a durable edit
        # vocabulary.  ``_canonical_field`` resolves one only when the node's
        # frozen/instance schema proves the compact slot's render-visible name.
        # If it could not do so, reject rather than sealing a ``widget_N`` op
        # that authoritative replay is required to reject later.
        if is_positional_alias(field_name):
            # S2: help the agent discover the real field name + valid range.
            try:
                from vibecomfy.porting.widgets.compact_resolver import (
                    compact_widget_names_for_node,
                )

                try:
                    idx = int(field_name.split("_")[1])
                except Exception:
                    idx = -1
                if idx >= 0:
                    res = compact_widget_names_for_node(
                        node,
                        schema_provider=self.schema_provider,
                        name_authority=self.name_authority,
                    )
                    if 0 <= idx < len(res.names):
                        named = res.names[idx]
                        if isinstance(named, str) and named and not is_positional_alias(named):
                            schema = schema_for(self.schema_provider, node.class_type)
                            spec = _input_spec_for_field(
                                getattr(schema, "inputs", {}) or {}, named
                            )
                            hint = ""
                            if spec is not None:
                                choices = getattr(spec, "choices", None)
                                min_v = getattr(spec, "min", None)
                                max_v = getattr(spec, "max", None)
                                if choices:
                                    hint = f" Use '{named}' with one of {list(choices)[:5]}."
                                elif min_v is not None or max_v is not None:
                                    if min_v is not None and max_v is not None:
                                        hint = f" Use '{named}' with valid range {min_v} to {max_v}."
                                    elif min_v is not None:
                                        hint = f" Use '{named}' with valid range >= {min_v}."
                                    else:
                                        hint = f" Use '{named}' with valid range <= {max_v}."
                                else:
                                    hint = f" Use '{named}' instead."
                            else:
                                hint = f" Use '{named}' instead."
                            return self._reject(
                                item,
                                "widget_unknown",
                                "set_node_field",
                                (
                                    f"{node.class_type}.{field_name} has no schema-proven "
                                    f"render-visible field name. Did you mean '{named}'?{hint}"
                                ),
                            )
            except Exception:
                pass
            return self._reject(
                item,
                "widget_unknown",
                "set_node_field",
                (
                    f"{node.class_type}.{field_name} has no schema-proven "
                    "render-visible field name."
                ),
            )
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
            detail: dict[str, Any] = {
                "name": target_name,
                "uid": str(getattr(node, "uid", "") or ""),
                "field": field_name,
            }
            try:
                from vibecomfy.porting.edit.apply_field_aliases import (
                    field_diagnostics_for_node,
                )

                metadata = getattr(node, "metadata", None)
                raw_ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
                diagnostic_node = raw_ui if isinstance(raw_ui, Mapping) else {}
                field_detail = field_diagnostics_for_node(
                    diagnostic_node,
                    str(node.class_type),
                    schema_inputs,
                    schema_provider=self.schema_provider,
                )
                if field_detail.get("valid_fields"):
                    detail["valid_fields"] = field_detail["valid_fields"]
                if field_detail.get("semantic_aliases"):
                    detail["semantic_aliases"] = field_detail["semantic_aliases"]
            except Exception:
                pass
            return self._reject(
                item,
                "unknown_target_field",
                "set_node_field",
                f"{node.class_type} has no editable field or input named {field_name!r}.",
                detail=detail,
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
            op=self._last_effective_op or op,
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
            if str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE:
                authored_io, authored, valid = _exec_authored_io(node)
                if authored:
                    ports = (
                        {
                            index: f"{socket_type}_{index}"
                            for index, (_name, socket_type) in enumerate(
                                authored_io["outputs"]
                            )
                        }
                        if valid and authored_io is not None
                        else {}
                    )
                else:
                    ports = _agent_edit_output_ports(node)
            else:
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
        from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node

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
        if is_positional_alias(raw) and raw.startswith("widget_"):
            index = int(raw.removeprefix("widget_"))
            resolution = compact_widget_names_for_node(
                node,
                schema_provider=self.schema_provider,
                name_authority=self.name_authority,
            )
            if 0 <= index < len(resolution.names):
                named = resolution.names[index]
                if isinstance(named, str) and named and not is_positional_alias(named):
                    # Apply the same schema/Python-identifier decoding used by
                    # an originally named assignment.  The landed op therefore
                    # contains only the canonical render-visible name.
                    schema = schema_for(self.schema_provider, node.class_type)
                    schema_inputs = getattr(schema, "inputs", {}) or {}
                    return _surface_field_name(
                        schema_inputs,
                        str(node.class_type),
                        named,
                        schema_provider=self.schema_provider,
                    )
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
    def _refresh_bindings(self) -> None:
        try:
            names = _compute_variable_names(self.workflow.nodes, list(self.workflow.edges))
        except (AttributeError, KeyError, ValueError, TypeError) as exc:
            _LOGGER.debug("compute_variable_names failed: %s", exc)
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
            if not uid:
                continue
            if uid in bound_uids:
                # A batch-local assignment alias may already address this
                # node, but the next prompt exposes the canonical renderer
                # name.  Keep both spellings resolvable instead of letting the
                # transient alias shadow the name the model can actually see.
                if name not in used_names:
                    bindings[name] = uid
                    used_names.add(name)
                continue
            stable_name = fresh_name(name)
            bindings[stable_name] = uid
            used_names.add(stable_name)
            bound_uids.add(uid)
        self.name_to_uid = bindings

    def _apply(self, item: _ExpandedStatement, op: EditOp) -> StatementOutcome | None:
        effective_op, next_context, value_diagnostics, value_error = (
            _prepare_value_default_operation(
                self.workflow,
                op,
                schema_provider=self.schema_provider,
                context=self.value_default_context,
            )
        )
        if value_error is not None:
            self._last_transition = OperationTransition(
                occurrence=len(self._transitions),
                submitted=op,
                normalized=op,
                outcome="rejected",
                diagnostics=(value_error,),
                lint_disposition="rejected",
            )
            return StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="rejected",
                reason=value_error.code,
                op_kind=item.op_kind or getattr(op, "op", type(op).__name__),
                diagnostics=(value_error,),
                op=op,
            )
        evaluation = _evaluate_operation(
            self.workflow,
            effective_op,
            schema_provider=self.schema_provider,
            source=self._source_block(item) or item.source,
            presentation_ui=self._presentation_ui,
            presentation_index=self._presentation_index,
            baseline_presentation_index=self._baseline_presentation_index,
            future_wired_uids=self._future_wired_uids,
        )
        if evaluation.outcome == "noop":
            combined = tuple(value_diagnostics) + tuple(evaluation.diagnostics)
            self._last_transition = OperationTransition(
                occurrence=len(self._transitions), submitted=op,
                normalized=evaluation.normalized,
                outcome="noop", diagnostics=combined,
                lint_disposition=evaluation.lint_disposition,
            )
            return StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="skipped",
                reason="no_op",
                op_kind=item.op_kind or getattr(op, "op", type(op).__name__),
                diagnostics=combined,
                op=effective_op,
            )
        if evaluation.outcome != "staged":
            combined = tuple(value_diagnostics) + tuple(evaluation.diagnostics)
            self._last_transition = OperationTransition(
                occurrence=len(self._transitions), submitted=op,
                normalized=evaluation.normalized,
                lowered=evaluation.lowered,
                outcome="rejected", diagnostics=combined,
                lint_disposition=evaluation.lint_disposition,
            )
            return StatementOutcome(
                statement_index=item.statement_index,
                source=item.source,
                status="rejected",
                reason=(combined[0].code if combined else "apply_rejected"),
                op_kind=item.op_kind or getattr(op, "op", type(op).__name__),
                diagnostics=combined,
                op=effective_op,
            )
        before = self.workflow
        self.workflow = evaluation.workflow
        self.value_default_context = next_context
        self._last_effective_op = effective_op
        self._presentation_ui = evaluation.presentation_ui
        self._presentation_index = evaluation.presentation_index
        combined = tuple(value_diagnostics) + tuple(evaluation.diagnostics)
        self._pending_apply_diagnostics.extend(value_diagnostics)
        self._pending_apply_diagnostics.extend(
            _apply_diagnostics(before, self.workflow, effective_op)
        )
        self._last_transition = OperationTransition(
            occurrence=len(self._transitions), submitted=op,
            normalized=evaluation.normalized,
            lowered=evaluation.lowered, outcome="staged",
            diagnostics=combined,
            lint_disposition=evaluation.lint_disposition,
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
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> StatementOutcome:
        diagnostic = _diag(
            code,
            message or code,
            severity="error",
            detail=detail,
        )
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
    from vibecomfy.workflow import RawWidgetPayload

    stamped = deepcopy(node)
    _attach_emitted_ports(stamped, source, schema_provider)
    if getattr(stamped, "raw_widgets", None) is None:
        schema = schema_for(schema_provider, stamped.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        ordered_names: list[str] = []
        for name in getattr(schema, "widget_input_order", ()) or ():
            if name in schema_inputs:
                ordered_names.append(str(name))
        for name in schema_inputs:
            if str(name) not in ordered_names:
                ordered_names.append(str(name))
        for carrier in tuple(getattr(stamped, "inputs", {}) or {}) + tuple(
            getattr(stamped, "widgets", {}) or {}
        ):
            if str(carrier) not in ordered_names:
                ordered_names.append(str(carrier))
        values: list[Any] = []
        for name in ordered_names:
            if name in getattr(stamped, "inputs", {}) and not _is_link_value(
                stamped.inputs[name]
            ):
                values.append(stamped.inputs[name])
            elif name in getattr(stamped, "widgets", {}):
                values.append(stamped.widgets[name])
        if values:
            stamped.raw_widgets = RawWidgetPayload(
                values=values,
                shape="list",
                source="canonical.add_node",
                has_dict_rows=False,
                length=len(values),
            )
    return stamped


def _attach_emitted_ports(node: Any, source: str, schema_provider: Any) -> None:
    """Stamp typed emit ports onto a freshly added IR node.

    ``apply_edit_cow`` only copies class/fields; output ports live in
    instance metadata.  Without them ``src.IMAGE_0`` cannot resolve.
    Callers must pass a node that is not aliased to the pre-IR.
    """
    metadata = dict(getattr(node, "metadata", None) or {})
    is_exec = str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE
    schema = None
    normalized_exec_io = None
    if is_exec:
        # Authored exec IO is the complete dynamic roster authority.  Do not
        # perform another provider lookup after ingress or derive physical
        # ports from a generic exec schema.
        io_value = None
        if isinstance(getattr(node, "inputs", None), Mapping):
            io_value = node.inputs.get("io")
        if io_value is None and isinstance(getattr(node, "widgets", None), Mapping):
            io_value = node.widgets.get("io")
        normalized_exec_io = _normalize_exec_io(io_value)
        if normalized_exec_io is not None:
            node.native_input_names = [
                f"in_{index}"
                for index, _entry in enumerate(normalized_exec_io["inputs"])
            ]
    else:
        schema = schema_for(schema_provider, node.class_type)
        schema_inputs = getattr(schema, "inputs", None) or {}
        if isinstance(schema_inputs, Mapping):
            native_inputs = [
                str(name)
                for name, spec in schema_inputs.items()
                if input_spec_is_socket_only(spec)
            ]
            if native_inputs:
                node.native_input_names = native_inputs
    ports = _slots_from_source(source)
    if not ports and is_exec:
        if normalized_exec_io and normalized_exec_io["outputs"]:
            ports = [
                (f"{str(socket_type or 'unknown').replace(' ', '_').upper()}_{index}", name)
                for index, (name, socket_type) in enumerate(
                    normalized_exec_io["outputs"]
                )
            ]
    if not ports and not is_exec:
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
        authored_io, authored, valid = _exec_authored_io(node)
        if authored:
            if not valid or authored_io is None:
                return None
            outputs = authored_io["outputs"]
            mapped_index: int | None = None
            if attr.startswith("out_") and attr[4:].isdigit():
                mapped_index = int(attr[4:])
            else:
                typed = _TYPED_PORT.fullmatch(attr)
                if typed is not None:
                    mapped_index = int(typed.group(2))
                    if not 0 <= mapped_index < len(outputs):
                        return None
                    if outputs[mapped_index][1].casefold() != typed.group(1).casefold():
                        return None
                else:
                    for index, (name, _socket_type) in enumerate(outputs):
                        if name == attr:
                            mapped_index = index
                            break
            if mapped_index is None or not 0 <= mapped_index < len(outputs):
                return None
            socket_type = outputs[mapped_index][1]
            return f"{socket_type}_{mapped_index}"
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
        authored_io, authored, valid = _exec_authored_io(node)
        if authored:
            if not valid or authored_io is None:
                return slot
            typed = _TYPED_PORT.fullmatch(slot)
            if typed is not None:
                index = int(typed.group(2))
                if (
                    0 <= index < len(authored_io["outputs"])
                    and typed.group(1).casefold()
                    == authored_io["outputs"][index][1].casefold()
                ):
                    return f"out_{index}"
                return slot
            for index, (name, _socket_type) in enumerate(authored_io["outputs"]):
                if name == slot:
                    return f"out_{index}"
            return slot
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
        # RRSYN2-4: the canonical renderer-alias seam decides whether this
        # ``TYPE_N`` alias resolves against frozen evidence; its resolved
        # endpoint IS the declared UI name whenever the evidence carries one.
        resolved = canonical_renderer_output(node, slot)
        if resolved is not None and resolved != slot:
            return resolved
        named = _name_at(int(match.group(2)))
        if named:
            return named
        return _raw_output_slot(node, slot)
    return slot


def _frozen_output_evidence(
    node: Any,
    provider: Any = None,
) -> tuple[dict[int, str], dict[int, str], tuple[str, ...], int]:
    """Collect frozen output evidence as parallel name/type maps by index.

    Order (frozen render first): retained emit names, the rendered UI
    outputs list, then the provider's frozen schema outputs.  Returns
    ``(names_by_index, types_by_index, sources, slot_count)`` where
    ``sources`` records which evidence layers contributed a NAME at some
    index and ``slot_count`` is the largest declared output arity — an
    entry with NO name/type text (e.g. the raw UI row ``{}``) still proves
    that its slot index exists.
    """
    metadata = getattr(node, "metadata", None) or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    names: dict[int, str] = {}
    types: dict[int, str] = {}
    sources: list[str] = []
    slot_count = 0

    if str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE:
        authored_io, authored, valid = _exec_authored_io(node)
        if not authored:
            # A dynamic exec instance has no generic output capacity.  Its
            # authored IO declaration is the sole socket authority; stale UI
            # rows, provider rosters, and metadata cannot manufacture slots.
            return {}, {}, ("missing_authored_exec_io",), 0
        if authored:
            if not valid or authored_io is None:
                return {}, {}, ("invalid_authored_exec_io",), 0
            outputs = authored_io["outputs"]
            return (
                {index: name for index, (name, _socket_type) in enumerate(outputs)},
                {index: socket_type for index, (_name, socket_type) in enumerate(outputs)},
                ("authored_exec_io",),
                len(outputs),
            )

    def _absorb(names_obj: Any, types_obj: Any, label: str) -> None:
        nonlocal slot_count
        if isinstance(names_obj, (list, tuple)):
            slot_count = max(slot_count, len(names_obj))
            for index, raw in enumerate(names_obj):
                text = str(raw).strip() if raw is not None else ""
                if text and index not in names:
                    names[index] = text
            if any(
                str(raw).strip()
                for raw in names_obj
                if raw is not None
            ):
                sources.append(label)
        if isinstance(types_obj, (list, tuple)):
            slot_count = max(slot_count, len(types_obj))
            for index, raw in enumerate(types_obj):
                text = str(raw).strip() if raw is not None else ""
                if text and index not in types:
                    types[index] = text

    ui = metadata.get("_ui")
    outputs_ui = (
        ui.get("outputs") if isinstance(ui, Mapping) else None
    ) or ()
    # The RAW rendered row count proves slot existence even when a row has
    # no name/type text (``[{}]`` emits unknown_0 and must round-trip).
    if isinstance(outputs_ui, (list, tuple)):
        slot_count = max(slot_count, len(outputs_ui))
    # Retained emit names win over the rendered UI list (same precedence
    # the emitter itself uses); _absorb never overrides a recorded index.
    _absorb(
        metadata.get("output_names"),
        metadata.get("output_types"),
        "retained_emit_names",
    )
    # The rendered UI list may carry mapping rows OR bare name strings.
    # Batch-review RR2: the roster keeps ONE entry PER raw output row — a
    # row lacking the field stays a blank placeholder so downstream indices
    # match the frozen render exactly.  Filtering blank rows out shifts
    # every later alias onto the wrong slot ([IMAGE, {}, AUDIO] would
    # advertise 1:AUDIO and accept AUDIO_1 while rejecting real AUDIO_2).
    ui_names = [
        (
            str(item.get("name"))
            if isinstance(item, Mapping) and item.get("name") is not None
            else (str(item) if not isinstance(item, Mapping) else "")
        )
        for item in outputs_ui
    ]
    ui_types = [
        str(item.get("type"))
        if isinstance(item, Mapping) and item.get("type") is not None
        else ""
        for item in outputs_ui
    ]
    _absorb(ui_names, ui_types, "frozen_render_ui")
    if provider is not None:
        try:
            from vibecomfy.schema import schema_for  # noqa: PLC0415

            schema = schema_for(provider, str(getattr(node, "class_type", "")))
            outputs_schema = getattr(schema, "outputs", None) or ()
            _absorb(
                [getattr(item, "name", "") for item in outputs_schema],
                [getattr(item, "type", "") for item in outputs_schema],
                "frozen_schema",
            )
        except Exception:  # noqa: BLE001 - schema lookup failure is simply no evidence
            pass
    return names, types, tuple(dict.fromkeys(sources)), slot_count


def _exec_authored_io(
    node: Any,
) -> tuple[dict[str, list[tuple[str, str]]] | None, bool, bool]:
    """Return the retained authored exec IO, without admitting a loose copy.

    ``_normalize_exec_io`` remains the one parser for the contract.  The
    shape checks here only reject the parser's intentionally permissive
    repair/default behavior (missing names/types, malformed rows, duplicate
    names), so a malformed authored declaration cannot fall through to a
    provider's generic output roster.
    """
    values: list[Any] = []
    for channel in ("inputs", "widgets"):
        carrier = getattr(node, channel, None)
        if isinstance(carrier, Mapping) and "io" in carrier:
            values.append(carrier["io"])
    if not values:
        return None, False, True

    def _decoded(value: Any) -> Any:
        if not isinstance(value, str):
            # ``AddNodeOp`` reports are deeply frozen before authority replay:
            # mappings become ``mappingproxy`` instances and row vectors become
            # tuples.  Rehydrate that immutable *wire representation* to the
            # ordinary JSON-shaped containers expected by the one shared exec
            # IO parser.  This is representation normalization only; it does
            # not infer sockets or consult a provider.
            def _thaw(item: Any) -> Any:
                if isinstance(item, Mapping):
                    return {key: _thaw(child) for key, child in item.items()}
                if isinstance(item, tuple):
                    return [_thaw(child) for child in item]
                if isinstance(item, list):
                    return [_thaw(child) for child in item]
                return item

            return _thaw(value)
        try:
            import json

            return json.loads(value)
        except (TypeError, ValueError):
            return None

    def _strict(value: Any) -> dict[str, list[tuple[str, str]]] | None:
        decoded = _decoded(value)
        normalized = _normalize_exec_io(decoded)
        if normalized is None or not isinstance(decoded, Mapping):
            return None
        for direction in ("inputs", "outputs"):
            if direction not in decoded:
                continue
            raw_entries = decoded[direction]
            if isinstance(raw_entries, Mapping):
                rows = list(raw_entries.items())
                if any(
                    not isinstance(name, str) or not name.strip()
                    or not isinstance(socket_type, str) or not socket_type.strip()
                    for name, socket_type in rows
                ):
                    return None
                seen: set[str] = set()
                for name, _socket_type in rows:
                    folded = name.strip().casefold()
                    if folded in seen:
                        return None
                    seen.add(folded)
            elif isinstance(raw_entries, list):
                rows: list[tuple[Any, Any]] = []
                for row in raw_entries:
                    if isinstance(row, Mapping):
                        if (
                            "name" not in row
                            or "type" not in row
                            or not isinstance(row["name"], str)
                            or not row["name"].strip()
                            or not isinstance(row["type"], str)
                            or not row["type"].strip()
                        ):
                            return None
                        rows.append((row["name"], row["type"]))
                    elif isinstance(row, (list, tuple)) and len(row) == 2:
                        if (
                            not isinstance(row[0], str)
                            or not row[0].strip()
                            or not isinstance(row[1], str)
                            or not row[1].strip()
                        ):
                            return None
                        rows.append((row[0], row[1]))
                    else:
                        return None
                seen = set()
                for name, _socket_type in rows:
                    folded = name.strip().casefold()
                    if folded in seen:
                        return None
                    seen.add(folded)
            else:
                return None
        return normalized

    normalized_values = [_strict(value) for value in values]
    if any(value is None for value in normalized_values):
        return None, True, False
    first = normalized_values[0]
    if any(value != first for value in normalized_values[1:]):
        return None, True, False
    assert first is not None
    return first, True, True


def renderer_output_slots(
    node: Any,
    provider: Any = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (``index:name`` valid slots, evidence sources) for rejection
    detail (RRSYN2-4 admission evidence)."""
    names, types, sources, _slot_count = _frozen_output_evidence(node, provider)
    indexes = sorted(set(names) | set(types))
    slots = tuple(
        f"{index}:{names.get(index) or types.get(index)}"
        for index in indexes
    )
    return slots, sources or ("none",)

def canonical_renderer_output(
    node: Any,
    slot: str | int,
    provider: Any = None,
) -> str | None:
    """One canonical renderer-alias → frozen output-name seam (RRSYN2-4).

    Admission (``_op_validate._known_output``/``_validate_link``),
    interpretation (``_ui_output_slot``/``_output_socket_type``) and
    authority replay (``recompute_apply``, through ``admit_operations``)
    MUST NOT disagree about an endpoint the frozen render emitted. This is
    that single seam.

    Accepts exactly what the render emits — an integer slot, an
    ``unknown_N`` typed-unknown fallback, a ``TYPE_N`` alias such as
    ``AUDIO_0``, or a literal frozen output name:

    * int / digit string / ``unknown_N``: the index must exist in frozen
      output evidence; resolves to the indexed name when one exists.
    * ``TYPE_N``: the index must exist AND the ``TYPE`` token must
      case-fold-agree with the indexed name OR type; a mismatched token
      rejects even though the index exists.
    * literal names pass only against frozen evidence.

    Returns the resolved endpoint name, or ``None`` (fail closed).
    """
    if isinstance(slot, bool):
        return None
    text = str(slot)
    names, types, _sources, slot_count = _frozen_output_evidence(node, provider)

    def _index_exists(index: int) -> bool:
        # A blank rendered row (``[{}]``) proves the slot exists even though
        # it contributes no name/type text (unknown_N round-trip law).
        return index in names or index in types or 0 <= index < slot_count

    if isinstance(slot, int) or text.isdigit():
        index = int(slot) if isinstance(slot, int) else int(text)
        if not _index_exists(index):
            return None
        named = names.get(index)
        if named:
            return named
        typed = types.get(index)
        return f"{typed}_{index}" if typed else text

    unknown = re.fullmatch(r"[Uu]nknown_(\d+)", text)
    if unknown is not None:
        index = int(unknown.group(1))
        if not _index_exists(index):
            return None
        return names.get(index) or text

    typed_match = _TYPED_PORT.fullmatch(text)
    if typed_match is not None:
        base = typed_match.group(1)
        index = int(typed_match.group(2))
        if not _index_exists(index):
            return None
        folded = base.casefold()
        name = names.get(index)
        out_type = types.get(index)
        if (
            str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE
            and folded == "out"
            and name is not None
        ):
            return name
        agrees = bool(
            (name and name.casefold() == folded)
            or (out_type and out_type.casefold() == folded)
        )
        if not agrees:
            return None
        return name or text

    if text in set(names.values()):
        return text
    return None


def _output_socket_type(node: Any, slot: str | int) -> str | None:
    # RRSYN2-4: resolve renderer aliases (AUDIO_0) to their frozen endpoint
    # BEFORE the type lookup so admission and replay see identical type
    # evidence for the alias the agent was shown.
    lookup: str | int = slot
    if isinstance(slot, str):
        resolved = canonical_renderer_output(node, slot)
        if resolved is not None:
            lookup = resolved
    if str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE:
        authored_io, authored, valid = _exec_authored_io(node)
        # Dynamic exec has no renderer/provider capacity unless this exact
        # instance carries a valid authored declaration.  Keep the one
        # canonical IO parser as the sole socket authority; stale UI rows and
        # generic metadata cannot create a socket.
        if not authored or not valid or authored_io is None:
            return None
        resolved_name = lookup if isinstance(lookup, str) else None
        for index, (name, socket_type) in enumerate(authored_io["outputs"]):
            if resolved_name == name or (
                isinstance(slot, str)
                and slot.startswith("out_")
                and slot[4:].isdigit()
                and int(slot[4:]) == index
            ):
                return socket_type
        return None
    ports = _agent_edit_output_ports(node)
    if isinstance(lookup, str):
        for index, name in ports.items():
            if name == lookup:
                metadata = getattr(node, "metadata", None) or {}
                types = metadata.get("output_types") if isinstance(metadata, Mapping) else None
                if isinstance(types, (list, tuple)) and index < len(types):
                    return str(types[index]) or None
                token = lookup.rsplit("_", 1)[0]
                return token if token else None
    return None


def _input_socket_type(node: Any, field_name: str, schema_provider: Any) -> str | None:
    if str(getattr(node, "class_type", "")) == _EXEC_CLASS_TYPE:
        authored_io, authored, valid = _exec_authored_io(node)
        if authored:
            if not valid or authored_io is None:
                return None
            inputs = authored_io["inputs"]
            if field_name.startswith("in_") and field_name[3:].isdigit():
                index = int(field_name[3:])
                return inputs[index][1] if 0 <= index < len(inputs) else None
            for name, socket_type in inputs:
                if name == field_name:
                    return socket_type
            return None
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
