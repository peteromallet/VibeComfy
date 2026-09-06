from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping


class _ImmutableList(tuple):
    """Tuple-backed JSON array that still compares equal to ordinary lists.

    A ``list`` subclass is not immutable: callers can bypass overridden
    mutation methods with ``list.append(value, item)`` or
    ``list.__setitem__(value, index, item)``.  This value has no mutable list
    storage for those descriptors to reach.
    """

    __hash__ = None

    def __new__(cls, values: Any = ()) -> "_ImmutableList":
        return tuple.__new__(cls, tuple(values))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, (list, tuple)):
            return tuple(self) == tuple(other)
        return False

    def __repr__(self) -> str:
        return repr(list(self))

    def __deepcopy__(self, memo: dict[int, Any]) -> list[Any]:
        return [deepcopy(item, memo) for item in self]


class _FrozenDict(tuple, Mapping[str, Any]):
    """Tuple-backed mapping with no mutable ``dict`` storage to bypass."""

    __hash__ = None

    def __new__(cls, items: Any = ()) -> "_FrozenDict":
        return tuple.__new__(cls, tuple(items))

    def __getitem__(self, key: str) -> Any:
        for candidate, value in tuple.__iter__(self):
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self):
        return (key for key, _value in tuple.__iter__(self))

    def __len__(self) -> int:
        return tuple.__len__(self)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return False

    def __repr__(self) -> str:
        return repr(dict(self.items()))

    def __deepcopy__(self, memo: dict[int, Any]) -> dict[str, Any]:
        return {
            deepcopy(key, memo): deepcopy(value, memo)
            for key, value in self.items()
        }


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, _FrozenDict | _ImmutableList):
        return value
    if isinstance(value, Mapping):
        return _FrozenDict((key, _deep_freeze(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return _ImmutableList(_deep_freeze(item) for item in value)
    return value


def _unfreeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _unfreeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_unfreeze(item) for item in value]
    return value

from .ops import (
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
    UpsertLinkOp,
)
from .types import FieldChange
from vibecomfy.porting.emitter import EmissionDiagnostic, emit_agent_edit_python
from .constants import HELPER_NODE_TYPES, MODE_LABELS
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    InferredAnchorHint,
    build_batch_placement_facts,
    infer_add_node_anchor_hint,
)
from vibecomfy.identity.codec import to_raw_name
from vibecomfy.porting.widgets.schema import effective_widget_names_for_class
from vibecomfy.schema import get_schema_provider, schema_for, socket_types_compatible
from vibecomfy.porting.edit.admit import AdmissionSnapshot

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow




from vibecomfy.porting.edit._session_types import (
    ApplyOpsResult,
    BatchResult,
    CompactDiagnostic,
    DoneResult,
    InputSlotInfo,
    NodeDescriptor,
    OutputSlotInfo,
    StatementResult,
    _ConstantFoldError,
    _ExpandedStatement,
    _ParsedBatch,
    _ResolvedAddNodeCall,
    _ResolvedGraphName,
    _ResolvedOutputEndpoint,
    _ResolvedTargetField,
    _TEACHING_HINTS,
    _diag,
    _extract_uid_name_pairs,
    _freeze_operation_tuple,
    _freeze_report,
)
from vibecomfy.porting.edit.value_defaults import ValueDefaultContext

from vibecomfy.porting.edit._parse import (
    _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES,
    _RAW_COORDINATE_HINT_NAMES,
    _call_name,
    _fold_constant,
    _is_graph_reference_value,
    _parse_and_validate_batch,
    _resolve_vibecomfy_constructor,
    _unsafe,
)

from vibecomfy.porting.edit._ir_utils import (
    _MISSING_WIDGET_VALUE,
    _api_edges,
    _api_one_hop_neighbors,
    _changed_edge_endpoint_node_ids,
    _done_gate_b_uids_for_ops,
    _link_origin,
    _node_id_sort_key,
    _normalize_ir_type,
    _output_slot_name,
    _output_specs,
    _socket_type_from_widget_value,
    _subset_api_by_node_ids,
    _uids_for_op,
    _widget_value_for_field,
    _workflow_uid_to_node_id,
)


from vibecomfy.porting.edit._diff import (
    _DiffMixin,
    _UNRESOLVED_OLD_VALUE,
    _render_op_diff,
    _repr_short,
)

from vibecomfy.porting.edit._resolve import _ResolveMixin
from vibecomfy.porting.edit._describe import _DescribeMixin
from vibecomfy.porting.edit._gates import _GatesMixin
from vibecomfy.porting.edit._render import _RenderMixin
from vibecomfy.porting.edit._parse_execute import _ParseExecuteMixin


class EditSession(_RenderMixin, _ParseExecuteMixin, _ResolveMixin, _DescribeMixin, _GatesMixin, _DiffMixin):
    """State shell for the offline Python edit surface.

    T8 only establishes the render/state contract. Parsing batches, resolving
    statements, and the final proof gates land in later tasks.
    """

    def __init__(
        self,
        raw_ui_json: Mapping[str, Any],
        *,
        schema_provider: Any | None = None,
        caps: frozenset[str] | set[str] | tuple[str, ...] = (),
        render_budget_ms: float | None = None,
        max_batch_bytes: int = 20_000,
        max_statements: int = 100,
        max_expanded_statements: int = 500,
        max_for_iterations: int = 100,
        value_default_context: ValueDefaultContext | None = None,
        initial_workflow: VibeWorkflow | None = None,
        workflow_snapshot: Any | None = None,
    ) -> None:
        # raw_ui_json is door input only: the named ingest builds the retained
        # IR once.  The ingest snapshot is deep-frozen emit prior_ui furniture,
        # not a parallel mutation store and never a re-ingest fallback.
        self._ingest_ui: Mapping[str, Any] = _deep_freeze(deepcopy(dict(raw_ui_json)))
        self.landed_ops: list[Any] = []
        self.touched_uids: set[str] = set()
        self.touched_node_ids: set[str] = set()
        supplied_provider = schema_provider or get_schema_provider("auto")
        # Once a provider exposes an ingress snapshot, pin this session to a
        # provider reconstructed from that exact immutable snapshot.  This
        # prevents later presentation/lint emission from calling a poisoned
        # live provider or observing a newer ambient generation.
        from vibecomfy.schema import FrozenSchemaSnapshotProvider, SchemaSnapshot

        # Keep the ingress-bound live delegate only as advisory diagnostic
        # context.  The retained/frozen provider below remains the sole
        # schema authority; the interpreter uses this reference only to tell
        # a late live-only class apart from an ordinary invented constructor.
        self._advisory_schema_provider = supplied_provider
        supplied_snapshot = getattr(supplied_provider, "snapshot", None)
        if isinstance(supplied_snapshot, SchemaSnapshot):
            self.schema_provider = FrozenSchemaSnapshotProvider(supplied_snapshot)
            self.schema_provider._advisory_schema_provider = supplied_provider
        else:
            self.schema_provider = supplied_provider
        self.caps: frozenset[str] = frozenset(str(cap) for cap in caps)
        self.render_budget_ms = render_budget_ms
        self.max_batch_bytes = max_batch_bytes
        self.max_statements = max_statements
        self.max_expanded_statements = max_expanded_statements
        self.max_for_iterations = max_for_iterations
        self.value_default_context = (
            value_default_context.with_graph_protections(_unfreeze(self._ingest_ui))
            if value_default_context is not None
            else None
        )
        self.unbound_names: set[str] = set()
        # Batch 4 (Law 5): TRANSIENT within-batch name index.  When an
        # add-node statement lands, its target_name is registered here so
        # LATER statements in the same batch can reference the minted node.
        # It is never written to the retained IR or emit snapshot, never
        # consulted by the pure naming function, and carries no binding
        # semantics — a fresh session (or render) resolves names purely by
        # (class_type, uid-order) again.
        self._transient_name_index: dict[str, str] = {}
        self._transient_uid_index: dict[str, str] = {}
        self.render_count = 0
        self.last_rendered_source: str | None = None
        self.last_rendered_workflow: VibeWorkflow | None = None
        self.last_render_diagnostics: tuple[CompactDiagnostic, ...] = ()
        # The ingest IR is constructed once by the named door and retained
        # here.  Renders ALWAYS come from this IR.  Any UI the session
        # exposes is derived through the emit door.  The frozen
        # WorkflowSnapshot is the ingest authority; never re-decode raw.
        from vibecomfy.ingest.snapshot import snapshot_of

        self.workflow_snapshot = workflow_snapshot or snapshot_of(initial_workflow)
        if self.workflow_snapshot is not None and initial_workflow is None:
            initial_workflow = self.workflow_snapshot.workflow
        self.workflow: VibeWorkflow | None = initial_workflow
        if self.workflow is None:
            self.workflow = self._workflow_from_ui(_unfreeze(self._ingest_ui))
            self.workflow_snapshot = snapshot_of(self.workflow)
        # Resolved edit-op attribution from the apply engine, accumulated per
        # committed statement for the emit-boundary guard (guard_emit).
        self.resolved_ops: list[Any] = []
        # Batch 7 (Law 2) / Batch 9 (Law 3): committed history is
        # (wf_i, Δ_i, landed_ops) — Δ_i is the accepted batch source (the
        # canonical batch value) and landed_ops records the typed ops the
        # grammar yielded for it.  wf_0 is a COPY of the ingest IR so later
        # mutation of self.workflow cannot alias it.
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        self._wf0: VibeWorkflow | None = (
            _cow_workflow_copy(self.workflow) if self.workflow is not None else None
        )
        self._history: list[
            tuple[VibeWorkflow, str | tuple[Any, ...], tuple[Any, ...]]
        ] = []
        # Monotonic compare-and-swap token. Unlike ``len(history)`` it cannot
        # suffer an ABA after rollback.
        self._revision = 0

    # ── Batch 4 (Law 5): deterministic bindings, no session name locks ──
    # name_by_uid / uid_by_name are READ-ONLY derivations from the IR (the
    # emitted name is a pure function of (class_type, uid-order)).  No
    # mutation, no drift, no stored binding consulted.

    def _derived_name_maps(self) -> tuple[dict[str, str], dict[str, str]]:
        from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names

        uid_to_name: dict[str, str] = {}
        workflow = getattr(self, "workflow", None)
        if workflow is not None and getattr(workflow, "nodes", None):
            try:
                names = _compute_variable_names(workflow.nodes, list(workflow.edges))
            except Exception:
                names = {}
            for nid, name in names.items():
                node = workflow.nodes.get(nid)
                uid = str(getattr(node, "uid", "") or "")
                if uid:
                    uid_to_name.setdefault(uid, name)
        name_to_uid: dict[str, str] = {}
        for uid, name in uid_to_name.items():
            name_to_uid.setdefault(name, uid)
        return uid_to_name, name_to_uid

    @property
    def name_by_uid(self) -> dict[str, str]:
        return self._derived_name_maps()[0]

    @property
    def uid_by_name(self) -> dict[str, str]:
        return self._derived_name_maps()[1]

    @property
    def original_ui(self) -> Mapping[str, Any]:
        """Deep-frozen ingest snapshot used only as emit prior_ui furniture."""
        return self._ingest_ui

    @property
    def working_ui(self) -> dict[str, Any]:
        """Emit-door projection of the retained IR. Not stored session state."""
        if self.workflow is None:
            raise RuntimeError("EditSession has no retained IR to emit")
        return self._emit_working_snapshot(self.workflow)

    @property
    def history(
        self,
    ) -> tuple[tuple[VibeWorkflow, str | tuple[Any, ...], tuple[Any, ...]], ...]:
        """Return a detached, immutable view of committed edit history.

        Session replay owns the mutable ``_history`` list.  The public view
        must not expose either that container or its retained pre-commit IRs:
        callers may freely inspect or copy a workflow without changing future
        rollback/replay behavior.
        """
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        return tuple(
            (
                _cow_workflow_copy(pre),
                _freeze_report(source),
                _freeze_operation_tuple(recorded_ops),
            )
            for pre, source, recorded_ops in self._history
        )

    def rollback(self, steps: int = 1) -> bool:
        """Pop the last committed ``(wf_i, Δ_i)`` pair(s) and restore the IR.

        Replay from ``wf_0`` through the remaining deltas via ``interpret`` so
        no in-place mutation is required.  UI is not stored; callers that
        need a snapshot emit the replayed IR through the emit door.
        """
        if steps <= 0 or not self._history:
            return False
        del self._history[-steps:]
        from vibecomfy.porting.edit._interpret import interpret
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        workflow = self._wf0
        if workflow is None:
            raise RuntimeError("EditSession.rollback requires retained ingest IR")
        workflow = _cow_workflow_copy(workflow)
        remaining_ops: list[Any] = []
        remaining_resolved: list[Any] = []
        name_hints: dict[str, str] = {}
        for entry in self._history:
            _pre, delta, _recorded_ops = entry
            result = interpret(
                workflow,
                delta,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
                name_hints=name_hints,
            )
            workflow = result.workflow
            remaining_ops.extend(result.landed_ops)
            for outcome in result.statements:
                if outcome.status == "applied" and outcome.op_kind == "node_call":
                    name = outcome.detail.get("target_name")
                    uid = outcome.detail.get("minted_uid")
                    if isinstance(name, str) and isinstance(uid, str):
                        name_hints[name] = uid
        self.workflow = workflow
        self.landed_ops = remaining_ops
        self.resolved_ops = remaining_resolved
        self.touched_uids = set()
        self.touched_node_ids = set()
        self._transient_name_index = {}
        self._transient_uid_index = {}
        self.unbound_names = set()
        self._revision += 1
        return True

    @property
    def revision(self) -> int:
        """Monotonic revision used by every authoring frontend for CAS."""
        return self._revision

    def verify_delta_history(self, equality: Any | None = None) -> VibeWorkflow:
        """Replay ``wf_0 → wf_1 → …`` via ``interpret`` with the recorded Δ
        sources (Law 3) and verify each recorded batch.

        For every history entry the replayed post-IR is produced by
        ``interpret(pre, source)`` — the recorded source is the Δ — and
        ``diff(pre, post)`` must agree with it.  By default agreement means the
        generalized Δ equals the recorded landed ops exactly; pass a quotient
        comparator (``equality(a, b)``, e.g. a π_edit projection equality) to
        verify over the editable quotient instead — that also tolerates CAS
        no-op statements the minimal generalizer folds away.  Raises
        ``ValueError`` on the first mismatch.  Returns the replayed final
        workflow.
        """
        from vibecomfy.porting.edit._interpret import interpret
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
        from vibecomfy.porting.edit._diff import diff

        workflow = self._wf0
        if workflow is None:
            raise RuntimeError("EditSession.verify_delta_history requires retained ingest IR")
        workflow = _cow_workflow_copy(workflow)
        name_hints: dict[str, str] = {}
        for index, (_pre, source, recorded_ops) in enumerate(self._history):
            result = interpret(
                workflow,
                source,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
                name_hints=name_hints,
            )
            if not result.ok:
                raise ValueError(
                    f"delta history entry {index}: recorded source did not "
                    f"replay (ok=False): {source!r}"
                )
            generalized = diff(workflow, result.workflow)
            if equality is not None:
                reconstructed = interpret(
                    workflow,
                    generalized,
                    schema_provider=self.schema_provider,
                )
                if not equality(reconstructed.workflow, result.workflow):
                    raise ValueError(
                        f"delta history entry {index}: diff(pre, post) "
                        f"{tuple(generalized)!r} does not reconstruct the "
                        f"recorded batch's quotient for source {source!r}"
                    )
            elif tuple(generalized) != tuple(recorded_ops):
                raise ValueError(
                    f"delta history entry {index}: diff(pre, post) "
                    f"{tuple(generalized)!r} does not match the recorded batch "
                    f"{tuple(recorded_ops)!r} for source {source!r}"
                )
            for outcome in result.statements:
                if outcome.status == "applied" and outcome.op_kind == "node_call":
                    name = outcome.detail.get("target_name")
                    uid = outcome.detail.get("minted_uid")
                    if isinstance(name, str) and isinstance(uid, str):
                        name_hints[name] = uid
            workflow = result.workflow
        return workflow

    def _cas_snapshot(self, workflow: VibeWorkflow | None) -> dict[tuple[str, str], Any]:
        snapshot: dict[tuple[str, str], Any] = {}
        if workflow is None:
            return snapshot
        for node in workflow.nodes.values():
            uid = str(getattr(node, "uid", "") or "")
            if not uid:
                continue
            for name, value in {**node.inputs, **node.widgets}.items():
                snapshot[(uid, str(name))] = value
        return snapshot

    def _workflow_from_ui(self, ui_json: Mapping[str, Any]) -> VibeWorkflow:
        snapshot = getattr(self, "workflow_snapshot", None)
        if snapshot is not None:
            return snapshot.workflow
        from vibecomfy.ingest.normalize import from_ui
        from vibecomfy.ingest.snapshot import snapshot_of

        workflow = from_ui(
            dict(ui_json),
            schema_provider=self.schema_provider,
            use_comfy_converter=False,
        )
        self.workflow_snapshot = snapshot_of(workflow)
        return workflow

    def _emit_working_snapshot(
        self,
        workflow: VibeWorkflow | None = None,
        *,
        ops: tuple[Any, ...] | list[Any] | None = None,
    ) -> dict[str, Any]:
        """Emit the current IR to UI JSON. This is the only working-graph projector."""
        from vibecomfy.porting.emit.ui import emit_ui_json, pin_untouched_ui

        target = workflow if workflow is not None else getattr(self, "workflow", None)
        if target is None:
            raise RuntimeError("EditSession cannot emit UI without a retained IR")
        prior_ui = _unfreeze(self._ingest_ui)
        emitted = emit_ui_json(
            target,
            schema_provider=self.schema_provider,
            include_virtual_wires=True,
            prior_ui_payload=prior_ui,
        )
        pin_ops = tuple(self.landed_ops if ops is None else ops)
        return pin_untouched_ui(prior_ui, emitted, pin_ops)

    @classmethod
    def _guard_ops_for_ui(
        cls, workflow: VibeWorkflow, ops: tuple[Any, ...]
    ) -> tuple[Any, ...]:
        """Project only guard attribution onto emitted UI scope names."""
        from dataclasses import replace

        from vibecomfy.porting.edit._ir_utils import build_recursive_edit_index

        aliases = build_recursive_edit_index(workflow).ui_scope_aliases

        def path(value: str) -> str:
            return aliases.get(value, value)

        projected: list[Any] = []
        for op in ops:
            changes: dict[str, Any] = {}
            target = getattr(op, "target", None)
            if target is not None and getattr(target, "scope_path", ""):
                changes["target"] = replace(target, scope_path=path(target.scope_path))
            source = getattr(op, "source", None)
            if source is not None and getattr(source, "scope_path", ""):
                changes["source"] = replace(source, scope_path=path(source.scope_path))
            if getattr(op, "scope_path", ""):
                changes["scope_path"] = path(op.scope_path)
            projected.append(replace(op, **changes) if changes else op)
        return tuple(projected)

    def node_ui(self, uid: str, scope_path: str = "") -> dict[str, Any] | None:
        """Return the emit-side node dict for *uid*, or None.

        Inspection helper only — the retained IR is the mutation authority.
        The graph is the emit-door snapshot of that IR.
        """
        if self.workflow is None:
            raise RuntimeError("EditSession.node_ui requires a retained IR")
        if scope_path:
            raise RuntimeError(
                "EditSession.node_ui does not expose nested raw nodes; capture the "
                "current canvas/export, port through canonical Python, then reopen/reload."
            )
        from vibecomfy.ingest.normalize import door_get_nodes

        graph = self._emit_working_snapshot()
        nodes = door_get_nodes(graph)
        if not isinstance(nodes, list):
            return None
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            properties = node.get("properties")
            if isinstance(properties, Mapping) and properties.get("vibecomfy_uid") == uid:
                return dict(node)
        return None

    def _projection_op(self, op: Any) -> Any:
        return op

    @staticmethod
    def _authorize_emitted_list_values(
        baseline: dict[str, Any],
        candidate: Mapping[str, Any],
        workflow: VibeWorkflow,
        ops: tuple[Any, ...],
    ) -> None:
        """Expose normalized list-field values through the existing UI guard."""
        from vibecomfy.porting.emit.ui import _index_nodes
        from vibecomfy.porting.edit._ir_utils import build_recursive_edit_index

        aliases = build_recursive_edit_index(workflow).ui_scope_aliases
        before = _index_nodes(baseline)
        after = _index_nodes(candidate)
        for op in ops:
            target = getattr(op, "target", None)
            if not isinstance(op, SetNodeFieldOp) or target is None:
                continue
            key = (aliases.get(target.scope_path, target.scope_path), str(target.uid))
            old, new = before.get(key), after.get(key)
            if not isinstance(old, dict) or not isinstance(new, Mapping):
                continue
            old_inputs, new_inputs = old.get("inputs"), new.get("inputs")
            if not isinstance(old_inputs, list) or not isinstance(new_inputs, list):
                continue
            for old_slot, new_slot in zip(old_inputs, new_inputs):
                if (
                    isinstance(old_slot, dict)
                    and isinstance(new_slot, Mapping)
                    and old_slot.get("name") == target.field_path
                    and {k: v for k, v in old_slot.items() if k != "value"}
                    == {k: v for k, v in new_slot.items() if k != "value"}
                ):
                    old_slot["value"] = deepcopy(new_slot.get("value"))
                    break

    def apply_ops(
        self,
        ops: Any,
        *,
        expected_revision: int | None = None,
    ) -> ApplyOpsResult:
        """Atomically validate, canonicalize, replay-prove, and commit typed ops.

        Typed tools are only an input adapter. This method remains the sole
        mutation gateway and records the generalized canonical delta produced
        by the existing IR ``diff`` engine, so equivalent Python and tool
        edits share replay and persistence semantics.
        """
        from vibecomfy.porting.edit._diff import diff
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
        from vibecomfy.porting.edit.apply_gate import verify_apply
        from vibecomfy.porting.emit.ui import guard_exit_ui

        batch = tuple(ops or ())
        if expected_revision is not None and expected_revision != self._revision:
            return ApplyOpsResult(
                ok=False,
                reason="stale_revision",
                diagnostics=(
                    _diag(
                        "stale_revision",
                        f"expected revision {expected_revision}, current revision is {self._revision}.",
                        severity="error",
                        detail={"expected": expected_revision, "current": self._revision},
                    ),
                ),
                revision=self._revision,
                retryable=False,
            )
        if not batch:
            return ApplyOpsResult(
                ok=False,
                reason="invalid_arguments",
                diagnostics=(_diag("invalid_arguments", "no typed ops to apply", severity="error"),),
                revision=self._revision,
            )
        if self.workflow is None:
            return ApplyOpsResult(
                ok=False,
                reason="no_edit_session",
                diagnostics=(_diag("no_edit_session", "the session has no retained IR.", severity="error"),),
                revision=self._revision,
                retryable=False,
            )

        snapshot = self._snapshot_mutable_state()
        try:
            pre = _cow_workflow_copy(self.workflow)
            from vibecomfy.porting.edit._ir_utils import (
                RecursiveEditError,
                _RECURSIVE_GUIDANCE,
                _has_mixed_recursive_scope,
                _has_recursive_scope,
                _tag_edit_provenance,
                build_recursive_edit_index,
            )

            # Recursive authored nodes are plain typed-definition mappings,
            # not VibeNode instances with a metadata slot.  Establish the
            # canonical provenance on the isolated pre-state first so the
            # emitted baseline and candidate carry the same provenance while
            # the committed COW state retains the tag.  This is presentation
            # furniture, not editable semantic authority.
            try:
                recursive_index = build_recursive_edit_index(pre)
                for op in batch:
                    target = getattr(op, "target", None)
                    scope_path = str(
                        getattr(target, "scope_path", "")
                        or getattr(op, "scope_path", "")
                    )
                    if not scope_path or not isinstance(op, (SetNodeFieldOp, SetModeOp)):
                        continue
                    uid = getattr(target, "uid", None)
                    if uid is not None:
                        _tag_edit_provenance(
                            recursive_index.node(scope_path, str(uid)).node
                        )
            except RecursiveEditError as exc:
                return ApplyOpsResult(
                    ok=False,
                    reason=exc.code,
                    diagnostics=(
                        _diag(
                            exc.code,
                            f"{exc}; {_RECURSIVE_GUIDANCE}",
                            severity="error",
                        ),
                    ),
                    revision=self._revision,
                    retryable=False,
                )

            if _has_mixed_recursive_scope(batch):
                return ApplyOpsResult(
                    ok=False,
                    reason="unsupported_structural_scope",
                    diagnostics=(_diag(
                        "unsupported_structural_scope",
                        f"mixed root and nested scopes are unsupported; {_RECURSIVE_GUIDANCE}",
                        severity="error",
                    ),),
                    revision=self._revision,
                    retryable=False,
                )
            if any(
                isinstance(op, AddNodeOp)
                and not op.scope_path
                and _has_recursive_scope((op,))
                for op in batch
            ):
                return ApplyOpsResult(
                    ok=False,
                    reason="unsupported_structural_scope",
                    diagnostics=(
                        _diag(
                            "unsupported_structural_scope",
                            f"add_node references a nested scope; {_RECURSIVE_GUIDANCE}",
                            severity="error",
                        ),
                    ),
                    revision=self._revision,
                    retryable=False,
                )
            # Every successful typed transaction must carry the same detached
            # evaluator report as Python/preview.  There is no live-provider
            # validation fallback: without frozen authority the shared
            # evaluator returns a typed rejection and nothing can publish.
            from vibecomfy.porting.edit._interpret import _interpret_ops

            typed_report = _interpret_ops(
                pre,
                batch,
                schema_provider=self.schema_provider,
            )
            if not typed_report.ok:
                reason = (
                    typed_report.diagnostics[0].code
                    if typed_report.diagnostics else "apply_rejected"
                )
                return ApplyOpsResult(
                    ok=False,
                    reason=reason,
                    diagnostics=tuple(typed_report.diagnostics),
                    revision=self._revision,
                    retryable=False,
                    transitions=tuple(typed_report.transitions),
                    lint_result=typed_report.lint_result,
                    occurrence_to_statement_index=dict(
                        typed_report.occurrence_to_statement_index
                    ),
                )
            post = typed_report.workflow

            # The accepted batch is the generalized IR delta, never the
            # frontend's possibly non-canonical request representation.
            # Keep the evaluator/apply gate on ordinary canonical IR values;
            # detach only at publication so immutable report containers never
            # become inputs to replay/deepcopy machinery.
            canonical_ops = tuple(diff(pre, post, schema_provider=self.schema_provider))
            if not canonical_ops:
                # The shared evaluator has already classified and reported
                # every occurrence. An all-noop typed batch has no candidate
                # to verify or commit; preserve its immutable report rather
                # than replacing it with a later reportless apply-gate error.
                return ApplyOpsResult(
                    ok=False,
                    reason="no_op",
                    diagnostics=tuple(typed_report.diagnostics),
                    revision=self._revision,
                    retryable=False,
                    transitions=tuple(typed_report.transitions),
                    lint_result=typed_report.lint_result,
                    occurrence_to_statement_index=dict(
                        typed_report.occurrence_to_statement_index
                    ),
                )
            frozen_canonical_ops = _freeze_operation_tuple(canonical_ops)
            # Typed callers receive the same detached transition/lint report as
            # the Python surface.  A retained frozen snapshot is required for
            # this shared evaluator; legacy live-only providers keep the
            # established validate/diff path and expose an empty report.
            gate = verify_apply(
                pre,
                post,
                landed_ops=canonical_ops,
                schema_provider=self.schema_provider,
            )
            if not gate.ok or not gate.apply_eligible:
                specific = gate.reason or "verification_failed"
                return ApplyOpsResult(
                    ok=False,
                    reason="verification_failed",
                    diagnostics=(
                        _diag(
                            "verification_failed",
                            f"apply gate rejected the delta: {specific}",
                            severity="error",
                        ),
                        *gate.diagnostics,
                    ),
                    revision=self._revision,
                )

            baseline_ui = self._emit_working_snapshot(pre, ops=())
            # The returned candidate is the complete post-transaction graph,
            # not a graph containing only this batch's attribution.  Pinning
            # with just ``canonical_ops`` would restore earlier accepted edits
            # from ``original_ui`` while the retained IR already contains
            # them, so a second typed turn could return a graph that silently
            # regresses the first turn.  Include the prior landed operations
            # while the transaction is still uncommitted; this is equivalent
            # to the snapshot emitted after commit and keeps candidate/UI
            # equality stable across a durable threaded continuation.
            accepted_ops = tuple(self.landed_ops) + canonical_ops
            candidate_ui = self._emit_working_snapshot(post, ops=accepted_ops)
            self._authorize_emitted_list_values(
                baseline_ui, candidate_ui, pre, accepted_ops
            )
            exit_guard = guard_exit_ui(
                baseline_ui,
                candidate_ui,
                self._guard_ops_for_ui(pre, accepted_ops),
            )
            if not exit_guard.ok:
                diagnostics = tuple(
                    _diag(
                        getattr(issue, "code", "exit_guard"),
                        getattr(issue, "message", str(issue)),
                        severity=getattr(issue, "severity", "error") or "error",
                    )
                    for issue in exit_guard.diagnostics
                )
                return ApplyOpsResult(
                    ok=False,
                    reason="verification_failed",
                    diagnostics=diagnostics,
                    revision=self._revision,
                )

            self.workflow = post
            self._history.append((pre, frozen_canonical_ops, frozen_canonical_ops))
            self.landed_ops.extend(frozen_canonical_ops)
            self.resolved_ops = []
            for op in frozen_canonical_ops:
                touched_uids, touched_node_ids = self._collect_touched_nodes((op,))
                self.touched_uids.update(touched_uids)
                self.touched_node_ids.update(touched_node_ids)
            self._revision += 1
            from vibecomfy.porting.edit.checkpoint import accepted_delta_id

            return ApplyOpsResult(
                ok=True,
                reason="accepted",
                workflow=_cow_workflow_copy(post),
                graph=deepcopy(candidate_ui),
                landed_ops=frozen_canonical_ops,
                delta_id=accepted_delta_id(canonical_ops),
                revision=self._revision,
                transitions=tuple(getattr(typed_report, "transitions", ()) or ()),
                lint_result=getattr(typed_report, "lint_result", None),
                occurrence_to_statement_index=dict(
                    getattr(typed_report, "occurrence_to_statement_index", {}) or {}
                ),
            )
        except Exception:
            self._restore_snapshot(snapshot)
            raise


def preview_lint_delta(
    delta: Any,
    index: Any,
    *,
    retained_authority: AdmissionSnapshot,
    schema_provider: Any = None,
    pre_workflow: Any = None,
    pre_ui_payload: Mapping[str, Any] | None = None,
    schema_snapshot: Any = None,
) -> Any:
    """Classify an ordered delta through detached canonical application."""
    from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy
    from vibecomfy.porting.edit.admit import (
        AdmissionSnapshot,
        _require_preview_workflow_witness,
        admission_snapshot_for,
        _schema_provider_for,
    )
    from vibecomfy.porting.edit._session_types import OperationTransition

    if pre_workflow is None:
        raise ValueError("preview_lint_delta requires retained pre_workflow authority")
    if schema_snapshot is None:
        raise ValueError("preview_lint_delta requires retained frozen schema_snapshot authority")
    if not isinstance(retained_authority, AdmissionSnapshot):
        raise ValueError("preview_lint_delta requires retained_authority")
    _require_preview_workflow_witness(pre_workflow, retained_authority)
    pair = admission_snapshot_for(
        pre_workflow,
        schema_provider,
        schema_snapshot=schema_snapshot,
        retained_authority=retained_authority,
    )
    frozen_provider = _schema_provider_for(pair)
    payload = pre_ui_payload if pre_ui_payload is not None else index.graph
    if not isinstance(payload, Mapping) or dict(payload) != dict(index.graph):
        raise ValueError("presentation evidence does not match retained lint index")
    payload = _unfreeze(payload)
    # The supplied UI index is evidence, never a second mutable graph.  Its
    # complete identity/topology/value projection must agree with the retained
    # IR emission before any operation is classified.
    from vibecomfy.ingest.normalize import (
        door_get_links,
        door_get_nodes,
        door_get_widgets_values,
    )
    from vibecomfy.porting.emit.ui import emit_ui_json

    retained_ui = emit_ui_json(
        _cow_workflow_copy(pre_workflow),
        schema_provider=frozen_provider,
        include_virtual_wires=True,
        prior_ui_payload=payload,
    )

    def _presentation_projection(graph: Mapping[str, Any]) -> tuple[Any, ...]:
        raw_nodes = door_get_nodes(graph, ()) if isinstance(graph, Mapping) else ()
        nodes: list[Any] = []
        if isinstance(raw_nodes, list):
            for node in raw_nodes:
                if not isinstance(node, Mapping):
                    continue
                properties = node.get("properties")
                uid = properties.get("vibecomfy_uid") if isinstance(properties, Mapping) else None
                nodes.append((
                    node.get("id"), node.get("type"), uid, node.get("mode"),
                    door_get_widgets_values(node), node.get("inputs"), node.get("outputs"),
                ))
        links = door_get_links(graph, ()) if isinstance(graph, Mapping) else ()
        return (tuple(nodes), tuple(links) if isinstance(links, list) else links)

    if _presentation_projection(payload) != _presentation_projection(retained_ui):
        raise ValueError("presentation evidence does not match retained pre_workflow")
    raw_nodes = door_get_nodes(payload) if isinstance(payload, Mapping) else None
    retained_nodes = getattr(pre_workflow, "nodes", {}) or {}
    if isinstance(raw_nodes, list):
        for raw_node in raw_nodes:
            if not isinstance(raw_node, Mapping):
                continue
            node_id = str(raw_node.get("id", ""))
            retained = retained_nodes.get(node_id)
            if retained is None:
                continue
            raw_mode = raw_node.get("mode")
            retained_mode = getattr(retained, "mode", None)
            if raw_mode is not None and retained_mode is not None:
                try:
                    from vibecomfy.workflow import mode_to_litegraph
                    retained_mode = mode_to_litegraph(retained_mode)
                except (TypeError, ValueError):
                    # A non-numeric mode is not comparable evidence; the
                    # retained graph still remains the semantic authority.
                    retained_mode = None
                if retained_mode is not None and int(raw_mode) != int(retained_mode):
                    raise ValueError("presentation evidence does not match retained pre_workflow")
            raw_widgets = door_get_widgets_values(raw_node)
            if raw_widgets is not None and retained is not None:
                retained_values = getattr(getattr(retained, "raw_widgets", None), "values", None)
                if not isinstance(retained_values, (list, tuple)):
                    retained_meta = getattr(retained, "metadata", None)
                    retained_ui = retained_meta.get("_ui") if isinstance(retained_meta, Mapping) else None
                    retained_values = (
                        door_get_widgets_values(retained_ui)
                        if isinstance(retained_ui, Mapping)
                        else None
                    )
                if isinstance(retained_values, (list, tuple)) and list(raw_widgets) != list(retained_values):
                    raise ValueError("presentation evidence does not match retained pre_workflow")
    from vibecomfy.porting.edit._interpret import _evaluate_operation, _lint_result_from_transitions

    current_workflow = _cow_workflow_copy(pre_workflow)
    current_index = index
    current_ui = payload
    operations = tuple(delta or ())
    transitions: list[OperationTransition] = []
    for occurrence, submitted in enumerate(operations):
        evaluation = _evaluate_operation(
            current_workflow,
            submitted,
            schema_provider=frozen_provider,
            occurrence=occurrence,
            presentation_index=current_index,
            presentation_ui=current_ui,
            baseline_presentation_index=index,
        )
        transition = OperationTransition(
            occurrence=occurrence,
            submitted=submitted,
            normalized=evaluation.normalized,
            lowered=evaluation.lowered,
            outcome=evaluation.outcome,
            diagnostics=evaluation.diagnostics,
            lint_disposition=evaluation.lint_disposition,
        )
        transitions.append(transition)
        if evaluation.outcome == "staged":
            current_workflow = evaluation.workflow
            if evaluation.presentation_ui is not None:
                current_ui = evaluation.presentation_ui
            if evaluation.presentation_index is not None:
                current_index = evaluation.presentation_index
    return _lint_result_from_transitions(tuple(transitions), source_ops=operations)

__all__ = [
    "ApplyOpsResult",
    "BatchResult",
    "CompactDiagnostic",
    "DoneResult",
    "EditSession",
    "preview_lint_delta",
    "StatementResult",
]
