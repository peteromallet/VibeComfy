from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .ledger import EditLedger, ScopeState
from .ops import AddNodeOp, EditOp, LinkSourceRef, LinkTargetRef, NodeFieldTarget, NodeTarget
from vibecomfy.porting.report import PortIssue
from vibecomfy.schema import InputSpec


@dataclass(frozen=True, slots=True)
class ResolvedFieldRef:
    target: NodeFieldTarget
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None
    input_name: str | None
    input_slot_index: int | None
    widget_index: int | None
    widget_key: str | None
    schema_input: InputSpec | None
    automatic_link_removal: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedNodeRef:
    target: NodeTarget
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None


@dataclass(frozen=True, slots=True)
class ResolvedLinkEndpoint:
    ref: LinkSourceRef | LinkTargetRef
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None
    slot_index: int | None
    slot_name: str
    socket_type: str | None


@dataclass(frozen=True, slots=True)
class ResolvedRemoveLinkRef:
    scope_path: str
    link_id: int
    link: Any


@dataclass(frozen=True, slots=True)
class ResolvedLinkRewire:
    scope_path: str
    link_id: int
    old_origin_id: int
    new_origin_id: int
    new_origin_slot: int


@dataclass(frozen=True, slots=True)
class ResolvedRemoveNodePlan:
    node_ref: ResolvedNodeRef
    link_ids_to_remove: tuple[int, ...]
    link_rewires: tuple[ResolvedLinkRewire, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedAddNodeSpec:
    op: AddNodeOp
    scope: ScopeState
    schema: Any
    schema_inputs: Mapping[str, InputSpec]
    resolved_inputs: Mapping[str, ResolvedLinkEndpoint]
    anchor_near: ResolvedNodeRef | None = None
    anchor_between: tuple[ResolvedNodeRef, ResolvedNodeRef] | None = None
    anchor_group_index: int | None = None
    anchor_group_title: str | None = None


@dataclass(frozen=True, slots=True)
class AppliedAddNodeSpec:
    op: AddNodeOp
    scope_path: str
    uid: str
    node_id: int
    link_ids: tuple[int, ...]
    source_uids: tuple[str, ...]
    group_index: int | None = None


ResolvedOp = (
    ResolvedFieldRef
    | ResolvedNodeRef
    | tuple[ResolvedLinkEndpoint, ResolvedLinkEndpoint]
    | ResolvedRemoveLinkRef
    | ResolvedRemoveNodePlan
    | ResolvedAddNodeSpec
    | AppliedAddNodeSpec
)


@dataclass(frozen=True, slots=True)
class ResolveResult:
    ok: bool
    ledger: EditLedger
    diagnostics: tuple[PortIssue, ...]
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyResult:
    ok: bool
    candidate: dict[str, Any] | None
    diagnostics: tuple[PortIssue, ...]
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...] = ()
    mutation_started: bool = False
    guard_result: GuardResult | None = None


@dataclass(frozen=True, slots=True)
class GuardResult:
    ok: bool
    diagnostics: tuple[PortIssue, ...]
    normalize_fallback_used: bool = False
    normalize_allow_list_used: bool = False
