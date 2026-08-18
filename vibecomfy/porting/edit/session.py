from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, field
from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping


class _ImmutableList(list):
    """List that compares like a list but rejects mutation."""

    def _frozen(self, *_args: Any, **_kwargs: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")

    __setitem__ = _frozen  # type: ignore[assignment]
    __delitem__ = _frozen  # type: ignore[assignment]
    append = _frozen  # type: ignore[assignment]
    extend = _frozen  # type: ignore[assignment]
    insert = _frozen  # type: ignore[assignment]
    pop = _frozen  # type: ignore[assignment]
    remove = _frozen  # type: ignore[assignment]
    clear = _frozen  # type: ignore[assignment]
    sort = _frozen  # type: ignore[assignment]
    reverse = _frozen  # type: ignore[assignment]

    def __iadd__(self, _other: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")

    def __imul__(self, _other: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")


class _FrozenDict(dict):
    """Dict that compares like a dict but rejects mutation."""

    def _frozen(self, *_args: Any, **_kwargs: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")

    __setitem__ = _frozen  # type: ignore[assignment]
    __delitem__ = _frozen  # type: ignore[assignment]
    clear = _frozen  # type: ignore[assignment]
    pop = _frozen  # type: ignore[assignment]
    popitem = _frozen  # type: ignore[assignment]
    setdefault = _frozen  # type: ignore[assignment]
    update = _frozen  # type: ignore[assignment]

    def __ior__(self, _other: Any) -> Any:
        raise TypeError("ingest snapshot is immutable")


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping) and not isinstance(value, _FrozenDict):
        return _FrozenDict((key, _deep_freeze(item)) for key, item in value.items())
    if isinstance(value, list) and not isinstance(value, _ImmutableList):
        return _ImmutableList(_deep_freeze(item) for item in value)
    return value


def _unfreeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _unfreeze(item) for key, item in value.items()}
    if isinstance(value, list):
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
    ) -> None:
        # raw_ui_json is door input only: the named ingest builds the retained
        # IR once.  The ingest snapshot is deep-frozen emit prior_ui furniture,
        # not a parallel mutation store and never a re-ingest fallback.
        self._ingest_ui: Mapping[str, Any] = _deep_freeze(deepcopy(dict(raw_ui_json)))
        self.landed_ops: list[Any] = []
        self.touched_uids: set[str] = set()
        self.touched_node_ids: set[str] = set()
        self.schema_provider = schema_provider or get_schema_provider("auto")
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
        # exposes is derived through the emit door.
        self.workflow: VibeWorkflow | None = initial_workflow
        if self.workflow is None:
            self.workflow = self._workflow_from_ui(_unfreeze(self._ingest_ui))
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
        self.history: list[tuple[VibeWorkflow, str, tuple[Any, ...]]] = []

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

    def rollback(self, steps: int = 1) -> bool:
        """Pop the last committed ``(wf_i, Δ_i)`` pair(s) and restore the IR.

        Replay from ``wf_0`` through the remaining deltas via ``interpret`` so
        no in-place mutation is required.  UI is not stored; callers that
        need a snapshot emit the replayed IR through the emit door.
        """
        if steps <= 0 or not self.history:
            return False
        del self.history[-steps:]
        from vibecomfy.porting.edit._interpret import interpret
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        workflow = self._wf0
        if workflow is None:
            raise RuntimeError("EditSession.rollback requires retained ingest IR")
        workflow = _cow_workflow_copy(workflow)
        remaining_ops: list[Any] = []
        remaining_resolved: list[Any] = []
        for entry in self.history:
            _pre, delta, _recorded_ops = entry
            result = interpret(
                workflow,
                delta,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
            )
            workflow = result.workflow
            remaining_ops.extend(result.landed_ops)
        self.workflow = workflow
        self.landed_ops = remaining_ops
        self.resolved_ops = remaining_resolved
        self.touched_uids = set()
        self.touched_node_ids = set()
        self._transient_name_index = {}
        self._transient_uid_index = {}
        self.unbound_names = set()
        return True

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
        for index, (_pre, source, recorded_ops) in enumerate(self.history):
            result = interpret(
                workflow,
                source,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
            )
            if not result.ok:
                raise ValueError(
                    f"delta history entry {index}: recorded source did not "
                    f"replay (ok=False): {source!r}"
                )
            generalized = diff(workflow, result.workflow)
            if equality is not None:
                reconstructed = interpret(workflow, generalized)
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

    def node_ui(self, uid: str, scope_path: str = "") -> dict[str, Any] | None:
        """Return the emit-side node dict for *uid*, or None.

        Inspection helper only — the retained IR is the mutation authority.
        The graph is the emit-door snapshot of that IR.
        """
        if self.workflow is None:
            raise RuntimeError("EditSession.node_ui requires a retained IR")
        from vibecomfy.ingest.normalize import door_get_nodes

        graph = self._emit_working_snapshot()
        if scope_path:
            for part in scope_path.split("/"):
                if not part.startswith("sg"):
                    return None
                try:
                    index = int(part[2:])
                except ValueError:
                    return None
                definitions = graph.get("definitions")
                if not isinstance(definitions, Mapping):
                    return None
                subgraphs = definitions.get("subgraphs")
                if not isinstance(subgraphs, list) or index >= len(subgraphs):
                    return None
                child = subgraphs[index]
                if not isinstance(child, Mapping):
                    return None
                graph = child
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

    def apply_ops(self, ops: Any) -> "ApplyOpsResult":
        """Apply typed edit ops through the FULL verified-acceptance gate.

        This is the shared typed-op authority the edit tools dispatch through
        (the old grammar path's ``apply_batch`` → ``verify_apply`` → ``done()``
        gates, re-expressed for already-lowered typed ops):

        1. schema/port + no-op validation (``validate_typed_ops``);
        2. copy-on-write application (``apply_edits_cow`` — the pre-IR is never
           mutated);
        3. structural + replay + empty-Δ verification (``verify_apply``);
        4. emit/exit guard (``guard_exit_ui`` over the emitted pre/post UI);
        5. atomic commit of ONE durable Δ onto the retained IR.

        Returns :class:`ApplyOpsResult`; it never raises for a typed rejection
        (a rejection is a result with ``ok=False`` and a stable ``reason``).
        """
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy, apply_edits_cow
        from vibecomfy.porting.edit._op_validate import ApplyOpsError, validate_typed_ops
        from vibecomfy.porting.edit._session_types import ApplyOpsResult, _diag
        from vibecomfy.porting.edit.apply_gate import verify_apply
        from vibecomfy.porting.emit.ui import guard_exit_ui

        ops = tuple(ops or ())
        if not ops:
            return ApplyOpsResult(
                ok=False,
                reason="invalid_arguments",
                diagnostics=(_diag("invalid_arguments", "no typed ops to apply", severity="error"),),
            )

        workflow = getattr(self, "workflow", None)
        if workflow is None:
            return ApplyOpsResult(
                ok=False,
                reason="no_edit_session",
                diagnostics=(
                    _diag("no_edit_session", "this route has no retained IR to edit.", severity="error"),
                ),
            )

        snapshot = self._snapshot_mutable_state()
        try:
            pre = _cow_workflow_copy(workflow)

            # 1. schema/port + no-op validation (typed, before any mutation).
            try:
                validate_typed_ops(workflow, ops, schema_provider=self.schema_provider)
            except ApplyOpsError as exc:
                return ApplyOpsResult(
                    ok=False,
                    reason=exc.code,
                    diagnostics=(_diag(exc.code, exc.message, severity="error"),),
                    retryable=exc.retryable,
                )

            # 2. copy-on-write application.
            post = apply_edits_cow(workflow, ops, schema_provider=self.schema_provider)

            # 3. structural (self-loop / orphaned output) + replay + empty-Δ gate.
            gate = verify_apply(pre, post, landed_ops=ops, schema_provider=self.schema_provider)
            if not gate.ok or not gate.apply_eligible:
                # Normalize every gate rejection to the advertised
                # ``verification_failed`` code; the specific reason stays in
                # the diagnostics/message (Codex generalization fix).
                specific = gate.reason or "verification_failed"
                diagnostics = (
                    _diag(
                        "verification_failed",
                        f"apply gate rejected the Δ: {specific}",
                        severity="error",
                    ),
                    *gate.diagnostics,
                )
                return ApplyOpsResult(
                    ok=False,
                    reason="verification_failed",
                    diagnostics=diagnostics,
                )

            # 4. emit/exit guard: the candidate may only change what the ops
            # attribute.
            baseline_ui = self._emit_working_snapshot(pre, ops=())
            candidate_ui = self._emit_working_snapshot(post, ops=ops)
            exit_guard = guard_exit_ui(baseline_ui, candidate_ui, ops)
            if not exit_guard.ok:
                diagnostics = tuple(
                    _diag(
                        getattr(issue, "code", "exit_guard"),
                        getattr(issue, "message", str(issue)),
                        severity=getattr(issue, "severity", "error") or "error",
                    )
                    for issue in exit_guard.diagnostics
                ) or (
                    _diag("exit_guard", "the emit-exit guard rejected the candidate.", severity="error"),
                )
                return ApplyOpsResult(
                    ok=False,
                    reason="verification_failed",
                    diagnostics=diagnostics,
                )

            # 5. commit: the retained IR advances, ONE Δ is recorded.
            pre_ir = _cow_workflow_copy(workflow)
            self.workflow = post
            if getattr(self, "history", None) is None:
                self.history = []
            self.history.append((pre_ir, ops, tuple(ops)))
            self.landed_ops.extend(ops)
            for op in ops:
                touched_uids, touched_node_ids = self._collect_touched_nodes((op,))
                self.touched_uids.update(touched_uids)
                self.touched_node_ids.update(touched_node_ids)
            self.resolved_ops = []
            return ApplyOpsResult(
                ok=True,
                reason="accepted",
                workflow=post,
                graph=candidate_ui,
                landed_ops=ops,
            )
        except Exception:
            self._restore_snapshot(snapshot)
            raise



__all__ = [
    "ApplyOpsResult",
    "BatchResult",
    "CompactDiagnostic",
    "DoneResult",
    "EditSession",
    "StatementResult",
]
