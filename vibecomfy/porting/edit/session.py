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
    ReorderOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from .types import FieldChange
from vibecomfy.porting.emit.emitter import EmissionDiagnostic, emit_agent_edit_python
from .projection import HELPER_NODE_TYPES, MODE_LABELS
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    InferredAnchorHint,
    build_batch_placement_facts,
    infer_add_node_anchor_hint,
)
from vibecomfy.porting.identity.codec import to_raw_name
from vibecomfy.porting.widgets.schema import effective_widget_names_for_class
from vibecomfy.schema import get_schema_provider, schema_for, socket_types_compatible

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow




from vibecomfy.porting.edit_session_types import (
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

from vibecomfy.porting.edit_session_parse import (
    _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES,
    _RAW_COORDINATE_HINT_NAMES,
    _assignment_op_kind,
    _call_name,
    _fold_constant,
    _is_graph_reference_value,
    _parse_and_validate_batch,
    _resolve_vibecomfy_constructor,
    _unsafe,
)

from vibecomfy.porting.edit_session_ir_utils import (
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

from vibecomfy.porting.edit_session_diff import (
    _DiffMixin,
    _UNRESOLVED_OLD_VALUE,
    _render_op_diff,
    _repr_short,
)

from vibecomfy.porting.edit_session_resolve import _ResolveMixin
from vibecomfy.porting.edit_session_describe import _DescribeMixin
from vibecomfy.porting.edit_session_gates import _GatesMixin
from vibecomfy.porting.edit_session_render import _RenderMixin
from vibecomfy.porting.edit_session_parse_execute import _ParseExecuteMixin


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
        self.name_by_uid: dict[str, str] = {}
        self.uid_by_name: dict[str, str] = {}
        self.unbound_names: set[str] = set()
        self.render_count = 0
        self.last_rendered_source: str | None = None
        self.last_rendered_workflow: VibeWorkflow | None = None
        self.last_render_diagnostics: tuple[CompactDiagnostic, ...] = ()


__all__ = [
    "BatchResult",
    "CompactDiagnostic",
    "DoneResult",
    "EditSession",
    "StatementResult",
]
