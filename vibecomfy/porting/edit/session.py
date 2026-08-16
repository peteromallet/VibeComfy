from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping

from .apply import apply_delta
from .ledger import EditLedger
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
from .projection import HELPER_NODE_TYPES, MODE_LABELS
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
from vibecomfy.porting.edit.apply_types import ValueDefaultContext

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
from vibecomfy.porting.resolution import _find_named_slot

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
        self.original_ui: dict[str, Any] = deepcopy(dict(raw_ui_json))
        self.working_ui: dict[str, Any] = deepcopy(dict(raw_ui_json))
        self.original_ledger = EditLedger.ingest(self.original_ui)
        self.ledger = EditLedger.ingest(self.working_ui)
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
        # It is never written to the ledger/working_ui, never consulted by
        # the pure naming function, and carries no binding semantics — a
        # fresh session (or render) resolves names purely by
        # (class_type, uid-order) again.
        self._transient_name_index: dict[str, str] = {}
        self._transient_uid_index: dict[str, str] = {}
        self.render_count = 0
        self.last_rendered_source: str | None = None
        self.last_rendered_workflow: VibeWorkflow | None = None
        self.last_render_diagnostics: tuple[CompactDiagnostic, ...] = ()
        # Batch 3 (IR authority): the ingest IR was constructed once by the
        # named door and is retained here.  Renders ALWAYS come from this IR;
        # it is refreshed once per committed batch through the copy-on-write
        # edit engine (apply_edits_cow — never a second ingest), so
        # render() never re-derives the IR from working_ui JSON.  working_ui
        # stays as the JSON store used for emit/ledger, not as the render
        # authority.  The rebuild is COW (Law 5): the pre-batch IR is never
        # mutated, untouched nodes keep their provenance, and edited nodes
        # compose provenance through the max-taint join.
        self.workflow: VibeWorkflow | None = initial_workflow
        if self.workflow is None:
            self.workflow = self._workflow_from_ui(self.original_ui)
        # Resolved edit-op attribution from the apply engine, accumulated per
        # committed statement for the emit-boundary guard (guard_emit).
        self.resolved_ops: list[Any] = []
        # Batch 7 (Law 2): committed history is (wf_i, Δ_i).  wf_0 is the
        # ingest IR; each successful batch appends the pre-state plus the
        # source that produced wf_{i+1} = interpret(wf_i, Δ_i).
        self._wf0: VibeWorkflow | None = self.workflow
        self.history: list[tuple[VibeWorkflow, str]] = []

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
        """Pop the last committed ``(wf_i, Δ_i)`` pair(s) and restore the IR.

        Replay from ``wf_0`` through the remaining deltas so no in-place
        mutation is required.  Returns True when at least one pair was popped.
        """
        if steps <= 0 or not self.history:
            return False
        popped = self.history[-steps:]
        del self.history[-steps:]
        from vibecomfy.porting.edit.interpret import interpret

        workflow = self._wf0
        if workflow is None:
            workflow = self._workflow_from_ui(self.original_ui)
            self._wf0 = workflow
        for _pre, delta in self.history:
            workflow = interpret(
                workflow,
                delta,
                schema_provider=self.schema_provider,
                max_batch_bytes=self.max_batch_bytes,
                max_statements=self.max_statements,
                max_expanded_statements=self.max_expanded_statements,
                max_for_iterations=self.max_for_iterations,
            ).workflow
        self.workflow = workflow
        _ = popped
        return True


__all__ = [
    "BatchResult",
    "CompactDiagnostic",
    "DoneResult",
    "EditSession",
    "StatementResult",
]
