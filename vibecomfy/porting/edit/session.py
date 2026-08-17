from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping

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
        # IR once.  original_ui is that ingest snapshot (from_ui / pin /
        # guard).  It is not mutation authority.  working_ui starts as the
        # same ingest snapshot and is later only an emit-side cache of the
        # retained IR via _emit_working_snapshot — never a mutation store.
        self.original_ui: dict[str, Any] = deepcopy(dict(raw_ui_json))
        self.working_ui: dict[str, Any] = deepcopy(dict(raw_ui_json))
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
            value_default_context.with_graph_protections(self.original_ui)
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
        # here.  Renders ALWAYS come from this IR.  working_ui is only the
        # emit-side cache of this IR — never render authority and never a
        # parallel mutation store.
        self.workflow: VibeWorkflow | None = initial_workflow
        if self.workflow is None:
            self.workflow = self._workflow_from_ui(self.original_ui)
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

    def rollback(self, steps: int = 1) -> bool:
        """Pop the last committed ``(wf_i, Δ_i)`` pair(s) and restore IR + UI.

        Replay from ``wf_0`` through the remaining deltas via ``interpret`` so
        no in-place mutation is required.  ``working_ui`` is rebuilt by
        emitting the replayed IR (emit-side cache only).
        """
        if steps <= 0 or not self.history:
            return False
        del self.history[-steps:]
        from vibecomfy.porting.edit._interpret import interpret
        from vibecomfy.porting.edit._ir_utils import _cow_workflow_copy

        workflow = self._wf0
        if workflow is None:
            workflow = self._workflow_from_ui(self.original_ui)
            self._wf0 = _cow_workflow_copy(workflow)
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
        self.working_ui = self._emit_working_snapshot(workflow, ops=remaining_ops)
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
            workflow = self._workflow_from_ui(self.original_ui)
            self._wf0 = _cow_workflow_copy(workflow)
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
            return deepcopy(self.original_ui)
        emitted = emit_ui_json(
            target,
            schema_provider=self.schema_provider,
            include_virtual_wires=True,
            prior_ui_payload=self.original_ui,
        )
        pin_ops = tuple(self.landed_ops if ops is None else ops)
        return pin_untouched_ui(self.original_ui, emitted, pin_ops)

    def node_ui(self, uid: str, scope_path: str = "") -> dict[str, Any] | None:
        """Return the emit-side node dict for *uid*, or None.

        Inspection helper only — the retained IR is the mutation authority.
        The graph is the emit-door snapshot of that IR.  ``working_ui`` is
        not a Law-5 graph surface.
        """
        graph = self._emit_working_snapshot() if self.workflow is not None else self.original_ui
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
        nodes = graph.get("nodes")
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


__all__ = [
    "BatchResult",
    "CompactDiagnostic",
    "DoneResult",
    "EditSession",
    "StatementResult",
]
