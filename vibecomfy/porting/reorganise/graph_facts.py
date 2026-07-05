from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from vibecomfy._compile._helpers import collect_broadcast_sources
from vibecomfy.porting.layout.lanes import assign_lanes
from vibecomfy.porting.layout.layering import _tarjan_scc_iterative, compute_layers
from vibecomfy.porting.edit.ledger import EditLedger, ScopeState
from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

from .diagnostics import ReorganiseDiagnostic
from .plan_types import (
    HELPER_CLASS_TYPES,
    LAYOUT_BEHAVIOR_NOTE,
    LAYOUT_BEHAVIOR_PRIMARY,
    LAYOUT_BEHAVIOR_SIDECAR,
    LAYOUT_BEHAVIOR_UNKNOWN,
    LAYOUT_BEHAVIOR_WALL,
    LAYOUT_BEHAVIORS,
    ROLE_HINT_HELPER,
    ROLE_HINT_LOADER,
    ROLE_HINT_OUTPUT,
    ROLE_HINT_SAMPLER,
    ROLE_HINT_UI,
    ROLE_HINT_UNKNOWN,
    CanonicalNodeRef,
    CanonicalNodeSummary,
    GraphFactsSummary,
    LayoutBehavior,
    RoleHint,
    SamplerRelationClaim,
    ScopeGraphSummary,
)


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_jsonish(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_jsonish(item) for item in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_jsonish(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_jsonish(item) for item in value]
    return value


def _json_sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str, ensure_ascii=True)


@dataclass(frozen=True, slots=True)
class CanonicalRefFact:
    ref: CanonicalNodeRef
    display: str
    class_type: str
    litegraph_id: Any = None
    title: str | None = None
    role_hint: RoleHint = ROLE_HINT_UNKNOWN
    is_helper: bool = False
    layout_behavior: LayoutBehavior = LAYOUT_BEHAVIOR_UNKNOWN

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ref": self.ref.to_json(),
            "display": self.display,
            "class_type": self.class_type,
            "litegraph_id": self.litegraph_id,
            "role_hint": self.role_hint,
            "is_helper": self.is_helper,
            "layout_behavior": self.layout_behavior,
        }
        if self.title is not None:
            payload["title"] = self.title
        return payload


@dataclass(frozen=True, slots=True)
class NodeFurnitureFact:
    ref: CanonicalNodeRef
    pos: Any = None
    size: Any = None
    color: str | None = None
    bgcolor: str | None = None
    flags: Mapping[str, Any] = field(default_factory=dict)
    mode: Any = None
    title: str | None = None
    properties: Mapping[str, Any] = field(default_factory=dict)
    sidecar_entry_key: str | None = None
    sidecar_entry: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pos", _freeze_jsonish(self.pos))
        object.__setattr__(self, "size", _freeze_jsonish(self.size))
        object.__setattr__(self, "flags", _freeze_jsonish(self.flags))
        object.__setattr__(self, "properties", _freeze_jsonish(self.properties))
        object.__setattr__(self, "sidecar_entry", _freeze_jsonish(self.sidecar_entry))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ref": self.ref.to_json(),
            "pos": _thaw_jsonish(self.pos),
            "size": _thaw_jsonish(self.size),
            "color": self.color,
            "bgcolor": self.bgcolor,
            "flags": _thaw_jsonish(self.flags),
            "mode": self.mode,
            "properties": _thaw_jsonish(self.properties),
        }
        if self.title is not None:
            payload["title"] = self.title
        if self.sidecar_entry_key is not None:
            payload["sidecar_entry_key"] = self.sidecar_entry_key
            payload["sidecar_entry"] = _thaw_jsonish(self.sidecar_entry)
        return payload


@dataclass(frozen=True, slots=True)
class GroupFact:
    scope_path: str
    index: int
    title: str | None = None
    bounding: Any = None
    color: str | None = None
    nodes: tuple[Any, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bounding", _freeze_jsonish(self.bounding))
        object.__setattr__(self, "nodes", tuple(_freeze_jsonish(node) for node in self.nodes))
        object.__setattr__(self, "payload", _freeze_jsonish(self.payload))

    def to_json(self) -> dict[str, Any]:
        return {
            "scope_path": self.scope_path,
            "index": self.index,
            "title": self.title,
            "bounding": _thaw_jsonish(self.bounding),
            "color": self.color,
            "nodes": [_thaw_jsonish(node) for node in self.nodes],
            "payload": _thaw_jsonish(self.payload),
        }


@dataclass(frozen=True, slots=True)
class ScopeFurnitureFact:
    scope_path: str
    groups: tuple[GroupFact, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)
    definitions_present: bool = False
    last_reroute_id: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "groups", tuple(self.groups))
        object.__setattr__(self, "extra", _freeze_jsonish(self.extra))

    def to_json(self) -> dict[str, Any]:
        return {
            "scope_path": self.scope_path,
            "groups": [group.to_json() for group in self.groups],
            "extra": _thaw_jsonish(self.extra),
            "definitions_present": self.definitions_present,
            "lastRerouteId": self.last_reroute_id,
        }


@dataclass(frozen=True, slots=True)
class HelperNodeFact:
    ref: CanonicalNodeRef
    display: str
    class_type: str
    helper_kind: str
    channel: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ref": self.ref.to_json(),
            "display": self.display,
            "class_type": self.class_type,
            "helper_kind": self.helper_kind,
        }
        if self.channel is not None:
            payload["channel"] = self.channel
        return payload


@dataclass(frozen=True, slots=True)
class RerouteFact:
    ref: CanonicalNodeRef
    input_links: tuple[Any, ...] = ()
    output_links: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_links", tuple(_freeze_jsonish(link) for link in self.input_links))
        object.__setattr__(self, "output_links", tuple(_freeze_jsonish(link) for link in self.output_links))

    def to_json(self) -> dict[str, Any]:
        return {
            "ref": self.ref.to_json(),
            "input_links": [_thaw_jsonish(link) for link in self.input_links],
            "output_links": [_thaw_jsonish(link) for link in self.output_links],
        }


@dataclass(frozen=True, slots=True)
class VirtualWireFact:
    key: str
    source: str
    wire_type: str | None = None
    channel: str | None = None
    endpoints: tuple[Any, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "endpoints", tuple(_freeze_jsonish(item) for item in self.endpoints))
        object.__setattr__(self, "payload", _freeze_jsonish(self.payload))

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "source": self.source,
            "type": self.wire_type,
            "channel": self.channel,
            "endpoints": [_thaw_jsonish(item) for item in self.endpoints],
            "payload": _thaw_jsonish(self.payload),
        }


@dataclass(frozen=True, slots=True)
class TopologyEdgeFact:
    scope_path: str
    source: CanonicalNodeRef
    target: CanonicalNodeRef
    source_slot: str
    target_slot: str
    link_id: Any = None
    socket_type: str | None = None
    passthrough: bool = False

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "scope_path": self.scope_path,
            "source": self.source.to_json(),
            "target": self.target.to_json(),
            "source_slot": self.source_slot,
            "target_slot": self.target_slot,
            "passthrough": self.passthrough,
        }
        if self.link_id is not None:
            payload["link_id"] = self.link_id
        if self.socket_type is not None:
            payload["socket_type"] = self.socket_type
        return payload


@dataclass(frozen=True, slots=True)
class NodeTopologyFact:
    ref: CanonicalNodeRef
    class_type: str
    fan_in: int
    fan_out: int
    topological_rank: int
    lane_band: int
    lane_index: int
    scc_id: str
    wcc_id: str
    terminal: bool = False
    terminal_output_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "terminal_output_types", tuple(self.terminal_output_types))

    def to_json(self) -> dict[str, Any]:
        return {
            "ref": self.ref.to_json(),
            "class_type": self.class_type,
            "fan_in": self.fan_in,
            "fan_out": self.fan_out,
            "topological_rank": self.topological_rank,
            "lane_band": self.lane_band,
            "lane_index": self.lane_index,
            "scc_id": self.scc_id,
            "wcc_id": self.wcc_id,
            "terminal": self.terminal,
            "terminal_output_types": list(self.terminal_output_types),
        }


@dataclass(frozen=True, slots=True)
class TerminalPathFact:
    scope_path: str
    terminal: CanonicalNodeRef
    terminal_type: str
    path: tuple[CanonicalNodeRef, ...]
    terminal_output_types: tuple[str, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", tuple(self.path))
        object.__setattr__(self, "terminal_output_types", tuple(self.terminal_output_types))

    def to_json(self) -> dict[str, Any]:
        return {
            "scope_path": self.scope_path,
            "terminal": self.terminal.to_json(),
            "terminal_type": self.terminal_type,
            "path": [ref.to_json() for ref in self.path],
            "terminal_output_types": list(self.terminal_output_types),
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class ParallelBranchCandidate:
    scope_path: str
    source: CanonicalNodeRef
    branch_roots: tuple[CanonicalNodeRef, ...]
    terminal_refs: tuple[CanonicalNodeRef, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "branch_roots", tuple(self.branch_roots))
        object.__setattr__(self, "terminal_refs", tuple(self.terminal_refs))

    def to_json(self) -> dict[str, Any]:
        return {
            "scope_path": self.scope_path,
            "source": self.source.to_json(),
            "branch_roots": [ref.to_json() for ref in self.branch_roots],
            "terminal_refs": [ref.to_json() for ref in self.terminal_refs],
        }


@dataclass(frozen=True, slots=True)
class ScopeTopologyFacts:
    scope_path: str
    raw_edges: tuple[TopologyEdgeFact, ...] = ()
    effective_edges: tuple[TopologyEdgeFact, ...] = ()
    node_topology: tuple[NodeTopologyFact, ...] = ()
    terminal_paths: tuple[TerminalPathFact, ...] = ()
    parallel_branch_candidates: tuple[ParallelBranchCandidate, ...] = ()
    sampler_relation_candidates: tuple[SamplerRelationClaim, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_edges", tuple(self.raw_edges))
        object.__setattr__(self, "effective_edges", tuple(self.effective_edges))
        object.__setattr__(self, "node_topology", tuple(self.node_topology))
        object.__setattr__(self, "terminal_paths", tuple(self.terminal_paths))
        object.__setattr__(self, "parallel_branch_candidates", tuple(self.parallel_branch_candidates))
        object.__setattr__(self, "sampler_relation_candidates", tuple(self.sampler_relation_candidates))

    def to_json(self) -> dict[str, Any]:
        return {
            "scope_path": self.scope_path,
            "raw_edges": [edge.to_json() for edge in self.raw_edges],
            "effective_edges": [edge.to_json() for edge in self.effective_edges],
            "node_topology": [node.to_json() for node in self.node_topology],
            "terminal_paths": [path.to_json() for path in self.terminal_paths],
            "parallel_branch_candidates": [candidate.to_json() for candidate in self.parallel_branch_candidates],
            "sampler_relation_candidates": [
                candidate.to_json() for candidate in self.sampler_relation_candidates
            ],
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class GraphInventoryFacts:
    canonical_refs: tuple[CanonicalRefFact, ...]
    canonical_refs_by_key: Mapping[tuple[str, str], CanonicalNodeRef]
    node_furniture: tuple[NodeFurnitureFact, ...]
    scope_furniture: tuple[ScopeFurnitureFact, ...]
    helper_nodes: tuple[HelperNodeFact, ...] = ()
    reroutes: tuple[RerouteFact, ...] = ()
    virtual_wires: tuple[VirtualWireFact, ...] = ()
    scope_topologies: tuple[ScopeTopologyFacts, ...] = ()
    sidecar_envelope: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[ReorganiseDiagnostic, ...] = ()
    summary: GraphFactsSummary = field(default_factory=GraphFactsSummary)

    def __post_init__(self) -> None:
        object.__setattr__(self, "canonical_refs", tuple(self.canonical_refs))
        object.__setattr__(
            self,
            "canonical_refs_by_key",
            MappingProxyType(dict(self.canonical_refs_by_key)),
        )
        object.__setattr__(self, "node_furniture", tuple(self.node_furniture))
        object.__setattr__(self, "scope_furniture", tuple(self.scope_furniture))
        object.__setattr__(self, "helper_nodes", tuple(self.helper_nodes))
        object.__setattr__(self, "reroutes", tuple(self.reroutes))
        object.__setattr__(self, "virtual_wires", tuple(self.virtual_wires))
        object.__setattr__(self, "scope_topologies", tuple(self.scope_topologies))
        object.__setattr__(self, "sidecar_envelope", _freeze_jsonish(self.sidecar_envelope))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def ref_for(self, scope_path: str, uid: str) -> CanonicalNodeRef | None:
        return self.canonical_refs_by_key.get((scope_path, uid))

    def to_json(self) -> dict[str, Any]:
        return {
            "canonical_refs": [fact.to_json() for fact in self.canonical_refs],
            "node_furniture": [fact.to_json() for fact in self.node_furniture],
            "scope_furniture": [fact.to_json() for fact in self.scope_furniture],
            "helper_nodes": [fact.to_json() for fact in self.helper_nodes],
            "reroutes": [fact.to_json() for fact in self.reroutes],
            "virtual_wires": [fact.to_json() for fact in self.virtual_wires],
            "scope_topologies": [fact.to_json() for fact in self.scope_topologies],
            "sidecar_envelope": _thaw_jsonish(self.sidecar_envelope),
            "diagnostics": [diagnostic.to_json() for diagnostic in self.diagnostics],
            "summary": self.summary.to_json(),
        }


def extract_graph_facts(
    ui_json: Mapping[str, Any],
    *,
    sidecar_envelope: Mapping[str, Any] | None = None,
) -> GraphInventoryFacts:
    """Extract the canonical read-only graph inventory for LayoutPlan v1.

    The UI JSON is ingested through :class:`EditLedger` for scoped identity. The
    original LiteGraph mapping is never modified; any UID stamping happens on
    the ledger's internal copy. UI furniture and sidecar facts are captured as
    immutable fact records, not as topology edits or ownership claims.
    """

    ledger = EditLedger.ingest(ui_json)
    stamped_graph = ledger.stamped_copy()
    sidecar = (
        copy.deepcopy(dict(sidecar_envelope))
        if sidecar_envelope is not None
        else _sidecar_from_stamped_graph(stamped_graph)
    )
    sidecar_last = _first_present(sidecar.get("lastRerouteId"), _scope_last_reroute_id(stamped_graph))
    if sidecar_last is not None:
        sidecar.setdefault("lastRerouteId", sidecar_last)

    canonical_refs: list[CanonicalRefFact] = []
    refs_by_key: dict[tuple[str, str], CanonicalNodeRef] = {}
    node_furniture: list[NodeFurnitureFact] = []
    helper_nodes: list[HelperNodeFact] = []
    reroutes: list[RerouteFact] = []

    entries = sidecar.get("entries") if isinstance(sidecar.get("entries"), Mapping) else {}
    entries = entries if isinstance(entries, Mapping) else {}

    for scope_path, uid, node in _ordered_nodes(ledger):
        class_type = _class_type(node)
        ref = CanonicalNodeRef(scope_path=scope_path, uid=uid)
        refs_by_key[(scope_path, uid)] = ref
        display = display_ref(ref, class_type=class_type)
        title = node.get("title") if isinstance(node.get("title"), str) and node.get("title") else None
        is_helper = class_type in HELPER_CLASS_TYPES
        role_hint = _role_hint(class_type, is_helper=is_helper)
        layout_behavior = _derive_layout_behavior(class_type, is_helper=is_helper, role_hint=role_hint)
        canonical_refs.append(
            CanonicalRefFact(
                ref=ref,
                display=display,
                class_type=class_type,
                litegraph_id=node.get("id"),
                title=title,
                role_hint=role_hint,
                is_helper=is_helper,
                layout_behavior=layout_behavior,
            )
        )
        sidecar_key, sidecar_entry = _sidecar_entry_for(ledger, entries, scope_path, uid)
        node_furniture.append(
            NodeFurnitureFact(
                ref=ref,
                pos=node.get("pos"),
                size=node.get("size"),
                color=node.get("color") if isinstance(node.get("color"), str) else None,
                bgcolor=node.get("bgcolor") if isinstance(node.get("bgcolor"), str) else None,
                flags=node.get("flags") if isinstance(node.get("flags"), Mapping) else {},
                mode=node.get("mode"),
                title=title,
                properties=node.get("properties") if isinstance(node.get("properties"), Mapping) else {},
                sidecar_entry_key=sidecar_key,
                sidecar_entry=sidecar_entry,
            )
        )
        if is_helper:
            helper_nodes.append(
                HelperNodeFact(
                    ref=ref,
                    display=display,
                    class_type=class_type,
                    helper_kind=_helper_kind(class_type),
                    channel=_helper_channel(node),
                )
            )
        if class_type == "Reroute":
            reroutes.append(
                RerouteFact(
                    ref=ref,
                    input_links=_input_links(node),
                    output_links=_output_links(node),
                )
            )

    scope_furniture = tuple(_scope_furniture(ledger))
    virtual_wires = tuple(_virtual_wire_facts(sidecar, stamped_graph))
    scope_topologies = tuple(_scope_topology_facts(ledger, canonical_refs))
    diagnostics = tuple(
        ReorganiseDiagnostic(
            code=issue.code,
            message=issue.message,
            severity=issue.severity,
            detail=issue.detail,
        )
        for issue in ledger.diagnostics
    )
    summary = _summary(ledger, canonical_refs, scope_topologies)

    return GraphInventoryFacts(
        canonical_refs=tuple(canonical_refs),
        canonical_refs_by_key=refs_by_key,
        node_furniture=tuple(node_furniture),
        scope_furniture=scope_furniture,
        helper_nodes=tuple(helper_nodes),
        reroutes=tuple(reroutes),
        virtual_wires=virtual_wires,
        scope_topologies=scope_topologies,
        sidecar_envelope=sidecar,
        diagnostics=diagnostics,
        summary=summary,
    )


def display_ref(ref: CanonicalNodeRef, *, class_type: str | None = None) -> str:
    scope_label = "<root>" if ref.scope_path == "" else ref.scope_path
    label = f"{scope_label}::{ref.uid}"
    if class_type:
        return f"{label} ({class_type})"
    return label


def _ordered_nodes(ledger: EditLedger) -> list[tuple[str, str, Mapping[str, Any]]]:
    rows: list[tuple[str, str, Mapping[str, Any]]] = []
    for (scope_path, uid), node in ledger.node_index.items():
        rows.append((scope_path, uid, node))
    return sorted(rows, key=lambda row: (_scope_sort_key(row[0]), _node_sort_key(row[2]), row[1]))


def _ordered_scopes(ledger: EditLedger) -> list[tuple[str, ScopeState]]:
    return sorted(ledger.scopes.items(), key=lambda item: _scope_sort_key(item[0]))


def _scope_sort_key(scope_path: str) -> tuple[int, str]:
    return (0, "") if scope_path == "" else (1, scope_path)


def _node_sort_key(node: Mapping[str, Any]) -> tuple[int, int, str]:
    node_id = node.get("id")
    if isinstance(node_id, int):
        return (0, node_id, "")
    return (1, 0, _json_sort_key(node_id))


def _class_type(node: Mapping[str, Any]) -> str:
    return str(node.get("type") or node.get("class_type") or "")


def _role_hint(class_type: str, *, is_helper: bool) -> RoleHint:
    if is_helper:
        if class_type in {"Note", "MarkdownNote"}:
            return ROLE_HINT_UI
        return ROLE_HINT_HELPER
    lower = class_type.lower()
    if "sampler" in lower:
        return ROLE_HINT_SAMPLER
    if "save" in lower or "preview" in lower or "combine" in lower:
        return ROLE_HINT_OUTPUT
    if "loader" in lower or lower.startswith(("checkpoint", "unet", "clip", "vae")):
        return ROLE_HINT_LOADER
    return ROLE_HINT_UNKNOWN


def _derive_layout_behavior(
    class_type: str,
    *,
    is_helper: bool,
    role_hint: RoleHint,
) -> LayoutBehavior:
    """Derive ``LayoutBehavior`` from ``role_hint`` (orthogonal placement dimension).

    This mirrors :func:`vibecomfy.porting.reorganise.classify._derive_layout_behavior`
    but uses only the pre-classification ``_role_hint`` call, so results may be
    refined by the full classification pass later.
    """
    if is_helper:
        if role_hint == ROLE_HINT_UI:
            return LAYOUT_BEHAVIOR_NOTE
        return LAYOUT_BEHAVIOR_SIDECAR

    if role_hint == ROLE_HINT_OUTPUT:
        return LAYOUT_BEHAVIOR_WALL

    if role_hint in (ROLE_HINT_LOADER, ROLE_HINT_SAMPLER):
        return LAYOUT_BEHAVIOR_PRIMARY

    if role_hint == ROLE_HINT_UNKNOWN:
        lower = class_type.lower()
        if any(token in lower for token in ("save", "preview", "combine")):
            return LAYOUT_BEHAVIOR_WALL
        if any(token in lower for token in ("getnode", "setnode", "reroute")):
            return LAYOUT_BEHAVIOR_SIDECAR
        if any(token in lower for token in ("note", "markdown")):
            return LAYOUT_BEHAVIOR_NOTE

    return LAYOUT_BEHAVIOR_UNKNOWN


def _helper_kind(class_type: str) -> str:
    if class_type == "Reroute":
        return "reroute"
    if class_type in {"SetNode", "GetNode"}:
        return "virtual-wire"
    if class_type in {"Note", "MarkdownNote"}:
        return "ui-note"
    return "helper"


def _helper_channel(node: Mapping[str, Any]) -> str | None:
    properties = node.get("properties")
    if isinstance(properties, Mapping):
        for key in ("channel", "name", "key"):
            value = properties.get(key)
            if isinstance(value, str) and value:
                return value
    widgets = node.get("widgets_values")
    if isinstance(widgets, Sequence) and not isinstance(widgets, (str, bytes)) and widgets:
        value = widgets[0]
        if isinstance(value, str) and value:
            return value
    return None


def _input_links(node: Mapping[str, Any]) -> tuple[Any, ...]:
    links: list[Any] = []
    inputs = node.get("inputs")
    if isinstance(inputs, Sequence) and not isinstance(inputs, (str, bytes)):
        for item in inputs:
            if isinstance(item, Mapping) and "link" in item:
                links.append(item.get("link"))
    return tuple(links)


def _output_links(node: Mapping[str, Any]) -> tuple[Any, ...]:
    links: list[Any] = []
    outputs = node.get("outputs")
    if isinstance(outputs, Sequence) and not isinstance(outputs, (str, bytes)):
        for item in outputs:
            if isinstance(item, Mapping):
                raw_links = item.get("links")
                if isinstance(raw_links, Sequence) and not isinstance(raw_links, (str, bytes)):
                    links.extend(raw_links)
    return tuple(links)


def _sidecar_entry_for(
    ledger: EditLedger,
    entries: Mapping[Any, Any],
    scope_path: str,
    uid: str,
) -> tuple[str | None, Mapping[str, Any]]:
    candidates = (ledger.qualified_uid(scope_path, uid), uid)
    for key in candidates:
        value = entries.get(key)
        if isinstance(value, Mapping):
            return str(key), dict(value)
    return None, {}


def _sidecar_from_stamped_graph(stamped_graph: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return store_from_ui_json(stamped_graph)
    except KeyError:
        filtered = copy.deepcopy(dict(stamped_graph))
        nodes = filtered.get("nodes")
        if isinstance(nodes, list):
            filtered["nodes"] = [
                node
                for node in nodes
                if isinstance(node, Mapping) and node.get("pos") is not None
            ]
        return store_from_ui_json(filtered)


def _scope_furniture(ledger: EditLedger) -> list[ScopeFurnitureFact]:
    facts: list[ScopeFurnitureFact] = []
    for scope_path, scope in _ordered_scopes(ledger):
        graph = scope.graph
        raw_groups = graph.get("groups")
        groups = raw_groups if isinstance(raw_groups, Sequence) and not isinstance(raw_groups, (str, bytes)) else []
        group_facts: list[GroupFact] = []
        for index, group in enumerate(groups):
            if not isinstance(group, Mapping):
                continue
            nodes = group.get("nodes")
            nodes_tuple = tuple(nodes) if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes)) else ()
            group_facts.append(
                GroupFact(
                    scope_path=scope_path,
                    index=index,
                    title=group.get("title") if isinstance(group.get("title"), str) else None,
                    bounding=group.get("bounding"),
                    color=group.get("color") if isinstance(group.get("color"), str) else None,
                    nodes=nodes_tuple,
                    payload=group,
                )
            )
        extra = graph.get("extra") if isinstance(graph.get("extra"), Mapping) else {}
        facts.append(
            ScopeFurnitureFact(
                scope_path=scope_path,
                groups=tuple(group_facts),
                extra=extra,
                definitions_present=isinstance(graph.get("definitions"), Mapping),
                last_reroute_id=_scope_last_reroute_id(graph),
            )
        )
    return facts


def _scope_last_reroute_id(graph: Mapping[str, Any]) -> Any:
    if "lastRerouteId" in graph:
        return graph.get("lastRerouteId")
    state = graph.get("state")
    if isinstance(state, Mapping) and "lastRerouteId" in state:
        return state.get("lastRerouteId")
    return None


def _virtual_wire_facts(sidecar: Mapping[str, Any], graph: Mapping[str, Any]) -> list[VirtualWireFact]:
    facts: list[VirtualWireFact] = []
    seen: set[tuple[str, str]] = set()

    def add_many(source: str, raw: Any) -> None:
        if isinstance(raw, Mapping):
            iterable = raw.items()
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            iterable = ((str(index), item) for index, item in enumerate(raw))
        else:
            return
        for key, payload in iterable:
            if not isinstance(payload, Mapping):
                continue
            fact_key = str(key)
            marker = (source, fact_key)
            if marker in seen:
                continue
            seen.add(marker)
            endpoints = payload.get("endpoints")
            if not isinstance(endpoints, Sequence) or isinstance(endpoints, (str, bytes)):
                endpoints = ()
            facts.append(
                VirtualWireFact(
                    key=fact_key,
                    source=source,
                    wire_type=payload.get("type") if isinstance(payload.get("type"), str) else None,
                    channel=payload.get("channel") if isinstance(payload.get("channel"), str) else None,
                    endpoints=tuple(endpoints),
                    payload=payload,
                )
            )

    add_many("sidecar", sidecar.get("virtual_wires"))
    extra = graph.get("extra")
    if isinstance(extra, Mapping):
        add_many("ui_extra", extra.get("virtual_wires"))
    return sorted(facts, key=lambda fact: (fact.source, fact.key))


@dataclass(frozen=True, slots=True)
class _RawEdge:
    link_id: Any
    from_node: str
    from_output: str
    to_node: str
    to_input: str
    socket_type: str | None = None


@dataclass(frozen=True, slots=True)
class _ScopeTopologyAdapter:
    scope_path: str
    workflow: VibeWorkflow
    id_to_ref: Mapping[str, CanonicalNodeRef]
    id_to_node: Mapping[str, Mapping[str, Any]]
    raw_edges: tuple[_RawEdge, ...]


_MAX_TERMINAL_PATHS_PER_SCOPE = 64
_MAX_TERMINAL_PATH_DEPTH = 48


def _scope_topology_facts(
    ledger: EditLedger,
    canonical_refs: Sequence[CanonicalRefFact],
) -> list[ScopeTopologyFacts]:
    facts_by_scope = _canonical_facts_by_scope(canonical_refs)
    topologies: list[ScopeTopologyFacts] = []
    for scope_path, scope in _ordered_scopes(ledger):
        adapter = _topology_adapter(scope_path, scope, facts_by_scope.get(scope_path, ()))
        raw_edges = tuple(_edge_fact(adapter, edge, passthrough=False) for edge in adapter.raw_edges)
        effective_raw_edges = tuple(_effective_edges(adapter))
        effective_edges = tuple(_edge_fact(adapter, edge, passthrough=True) for edge in effective_raw_edges)
        effective_workflow = _workflow_with_edges(adapter.workflow, effective_raw_edges)
        layers = compute_layers(effective_workflow)
        lanes = assign_lanes(effective_workflow, layers)
        fan_in, fan_out, adjacency, reverse_adjacency = _degree_maps(adapter, effective_raw_edges)
        scc_by_uid = _scc_ids(adapter, adjacency)
        wcc_by_uid = _wcc_ids(lanes)
        node_topology = tuple(
            _node_topology_fact(
                adapter,
                node,
                layers,
                lanes,
                fan_in,
                fan_out,
                scc_by_uid,
                wcc_by_uid,
            )
            for node in _sorted_workflow_nodes(adapter.workflow)
        )
        terminal_paths, paths_truncated = _terminal_paths(adapter, adjacency, reverse_adjacency)
        parallel_candidates = tuple(_parallel_branch_candidates(adapter, adjacency))
        sampler_candidates = tuple(_sampler_relation_candidates(adapter, adjacency, scc_by_uid, wcc_by_uid))
        topologies.append(
            ScopeTopologyFacts(
                scope_path=scope_path,
                raw_edges=raw_edges,
                effective_edges=effective_edges,
                node_topology=node_topology,
                terminal_paths=terminal_paths,
                parallel_branch_candidates=parallel_candidates,
                sampler_relation_candidates=sampler_candidates,
                truncated=paths_truncated,
            )
        )
    return topologies


def _canonical_facts_by_scope(
    canonical_refs: Sequence[CanonicalRefFact],
) -> dict[str, tuple[CanonicalRefFact, ...]]:
    rows: dict[str, list[CanonicalRefFact]] = {}
    for fact in canonical_refs:
        rows.setdefault(fact.ref.scope_path, []).append(fact)
    return {scope: tuple(facts) for scope, facts in rows.items()}


def _topology_adapter(
    scope_path: str,
    scope: ScopeState,
    node_facts: Sequence[CanonicalRefFact],
) -> _ScopeTopologyAdapter:
    id_to_ref: dict[str, CanonicalNodeRef] = {}
    id_to_node: dict[str, Mapping[str, Any]] = {}
    wf = VibeWorkflow(id=f"reorganise:{scope_path or 'root'}", source=WorkflowSource(id="reorganise"))
    for fact in node_facts:
        if fact.litegraph_id is None:
            continue
        node_id = str(fact.litegraph_id)
        node = scope.graph.get("nodes")
        raw_node = _node_by_id(node, fact.litegraph_id)
        if raw_node is None:
            continue
        id_to_ref[node_id] = fact.ref
        id_to_node[node_id] = raw_node
        wf.nodes[node_id] = VibeNode(
            id=node_id,
            class_type=fact.class_type,
            inputs=_workflow_inputs(raw_node),
            widgets=_workflow_widgets(raw_node),
            uid=fact.ref.uid,
        )

    raw_edges = tuple(
        edge
        for edge in _raw_edges(scope.graph)
        if edge.from_node in id_to_ref and edge.to_node in id_to_ref
    )
    wf.edges = [
        VibeEdge(edge.from_node, edge.from_output, edge.to_node, edge.to_input)
        for edge in raw_edges
    ]
    return _ScopeTopologyAdapter(
        scope_path=scope_path,
        workflow=wf,
        id_to_ref=id_to_ref,
        id_to_node=id_to_node,
        raw_edges=raw_edges,
    )


def _workflow_with_edges(wf: VibeWorkflow, edges: Sequence[_RawEdge]) -> VibeWorkflow:
    adapted = VibeWorkflow(id=wf.id, source=wf.source)
    adapted.nodes.update(wf.nodes)
    adapted.edges = [
        VibeEdge(edge.from_node, edge.from_output, edge.to_node, edge.to_input)
        for edge in edges
    ]
    return adapted


def _node_by_id(raw_nodes: Any, node_id: Any) -> Mapping[str, Any] | None:
    if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, (str, bytes)):
        return None
    for node in raw_nodes:
        if isinstance(node, Mapping) and str(node.get("id")) == str(node_id):
            return node
    return None


def _workflow_inputs(node: Mapping[str, Any]) -> dict[str, Any]:
    inputs: dict[str, Any] = {}
    raw_inputs = node.get("inputs")
    if isinstance(raw_inputs, Mapping):
        inputs.update({str(key): value for key, value in raw_inputs.items()})
    elif isinstance(raw_inputs, Sequence) and not isinstance(raw_inputs, (str, bytes)):
        for index, slot in enumerate(raw_inputs):
            if not isinstance(slot, Mapping):
                continue
            name = slot.get("name")
            if name is not None:
                inputs[str(name)] = slot.get("link")
            inputs[f"slot_{index}"] = slot.get("link")
    return inputs


def _workflow_widgets(node: Mapping[str, Any]) -> dict[str, Any]:
    widgets: dict[str, Any] = {}
    values = node.get("widgets_values")
    if isinstance(values, Sequence) and not isinstance(values, (str, bytes)):
        for index, value in enumerate(values):
            widgets[f"widget_{index}"] = value
    elif isinstance(values, Mapping):
        widgets.update({str(key): value for key, value in values.items()})
    raw_widgets = node.get("widgets")
    if isinstance(raw_widgets, Mapping):
        widgets.update({str(key): value for key, value in raw_widgets.items()})
    return widgets


def _raw_edges(graph: Mapping[str, Any]) -> list[_RawEdge]:
    links = graph.get("links")
    if not isinstance(links, Sequence) or isinstance(links, (str, bytes)):
        return []
    edges: list[_RawEdge] = []
    for index, link in enumerate(links):
        edge = _raw_edge(link, index)
        if edge is not None:
            edges.append(edge)
    return sorted(edges, key=_raw_edge_sort_key)


def _raw_edge(link: Any, index: int) -> _RawEdge | None:
    if isinstance(link, Mapping):
        source = link.get("origin_id", link.get("from_node"))
        target = link.get("target_id", link.get("to_node"))
        if source is None or target is None:
            return None
        link_id = link.get("id", link.get("link_id", index))
        return _RawEdge(
            link_id=link_id,
            from_node=str(source),
            from_output=str(link.get("origin_slot", link.get("from_output", 0))),
            to_node=str(target),
            to_input=str(link.get("target_slot", link.get("to_input", 0))),
            socket_type=link.get("type") if isinstance(link.get("type"), str) else None,
        )
    if isinstance(link, Sequence) and not isinstance(link, (str, bytes)) and len(link) >= 5:
        return _RawEdge(
            link_id=link[0],
            from_node=str(link[1]),
            from_output=str(link[2]),
            to_node=str(link[3]),
            to_input=str(link[4]),
            socket_type=link[5] if len(link) > 5 and isinstance(link[5], str) else None,
        )
    return None


def _raw_edge_sort_key(edge: _RawEdge) -> tuple[str, str, str, str, str]:
    return (
        _natural_id_key(edge.from_node),
        edge.from_output,
        _natural_id_key(edge.to_node),
        edge.to_input,
        _json_sort_key(edge.link_id),
    )


def _natural_id_key(value: str) -> str:
    return value.zfill(20) if value.isdigit() else value


def _edge_fact(adapter: _ScopeTopologyAdapter, edge: _RawEdge, *, passthrough: bool) -> TopologyEdgeFact:
    return TopologyEdgeFact(
        scope_path=adapter.scope_path,
        source=adapter.id_to_ref[edge.from_node],
        target=adapter.id_to_ref[edge.to_node],
        source_slot=edge.from_output,
        target_slot=edge.to_input,
        link_id=edge.link_id,
        socket_type=edge.socket_type,
        passthrough=passthrough,
    )


def _effective_edges(adapter: _ScopeTopologyAdapter) -> list[_RawEdge]:
    raw = list(adapter.raw_edges)
    after_broadcast = _resolve_broadcast_edges(adapter, raw)
    return sorted(_resolve_reroute_edges(adapter, after_broadcast), key=_raw_edge_sort_key)


def _resolve_broadcast_edges(adapter: _ScopeTopologyAdapter, edges: list[_RawEdge]) -> list[_RawEdge]:
    helper_ids = {
        node_id
        for node_id, node in adapter.workflow.nodes.items()
        if node.class_type in {"SetNode", "GetNode"}
    }
    if not helper_ids:
        return list(edges)
    sources = collect_broadcast_sources(adapter.workflow.nodes, adapter.workflow.edges)
    get_sources: dict[str, tuple[str, str]] = {}
    for node_id in helper_ids:
        node = adapter.workflow.nodes[node_id]
        if node.class_type != "GetNode":
            continue
        channel = _helper_channel(adapter.id_to_node.get(node_id, {}))
        source = sources.get(channel) if channel else None
        if source is not None:
            get_sources[node_id] = (str(source[0]), str(source[1]))

    result: list[_RawEdge] = []
    for edge in edges:
        if edge.to_node in helper_ids:
            continue
        if edge.from_node in helper_ids:
            redirect = get_sources.get(edge.from_node)
            if redirect is None:
                continue
            source_node, source_slot = redirect
            result.append(
                _RawEdge(
                    link_id=edge.link_id,
                    from_node=source_node,
                    from_output=source_slot,
                    to_node=edge.to_node,
                    to_input=edge.to_input,
                    socket_type=edge.socket_type,
                )
            )
            continue
        result.append(edge)
    return result


def _resolve_reroute_edges(adapter: _ScopeTopologyAdapter, edges: list[_RawEdge]) -> list[_RawEdge]:
    reroute_ids = {
        node_id
        for node_id, node in adapter.workflow.nodes.items()
        if node.class_type == "Reroute"
    }
    if not reroute_ids:
        return list(edges)
    inbound: dict[str, list[_RawEdge]] = {}
    for edge in edges:
        if edge.to_node in reroute_ids:
            inbound.setdefault(edge.to_node, []).append(edge)
    for node_id in inbound:
        inbound[node_id].sort(key=_raw_edge_sort_key)

    def terminal(node_id: str, visited: frozenset[str]) -> tuple[str, str] | None:
        if node_id in visited:
            return None
        incoming = inbound.get(node_id, [])
        if not incoming:
            return None
        source = incoming[0]
        if source.from_node in reroute_ids:
            return terminal(source.from_node, visited | {node_id})
        return source.from_node, source.from_output

    result: list[_RawEdge] = []
    for edge in edges:
        if edge.from_node in reroute_ids:
            source = terminal(edge.from_node, frozenset())
            if source is None:
                continue
            source_node, source_slot = source
            result.append(
                _RawEdge(
                    link_id=edge.link_id,
                    from_node=source_node,
                    from_output=source_slot,
                    to_node=edge.to_node,
                    to_input=edge.to_input,
                    socket_type=edge.socket_type,
                )
            )
        elif edge.to_node in reroute_ids:
            continue
        else:
            result.append(edge)
    return result


def _degree_maps(
    adapter: _ScopeTopologyAdapter,
    edges: Sequence[_RawEdge],
) -> tuple[dict[str, int], dict[str, int], dict[str, list[str]], dict[str, list[str]]]:
    fan_in = {node.uid: 0 for node in adapter.workflow.nodes.values()}
    fan_out = {node.uid: 0 for node in adapter.workflow.nodes.values()}
    adjacency = {node.uid: [] for node in adapter.workflow.nodes.values()}
    reverse = {node.uid: [] for node in adapter.workflow.nodes.values()}
    id_to_uid = {node.id: node.uid for node in adapter.workflow.nodes.values()}
    seen_edges: set[tuple[str, str]] = set()
    for edge in edges:
        source_uid = id_to_uid.get(edge.from_node)
        target_uid = id_to_uid.get(edge.to_node)
        if source_uid is None or target_uid is None:
            continue
        edge_key = (source_uid, target_uid)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        fan_out[source_uid] = fan_out.get(source_uid, 0) + 1
        fan_in[target_uid] = fan_in.get(target_uid, 0) + 1
        adjacency.setdefault(source_uid, []).append(target_uid)
        reverse.setdefault(target_uid, []).append(source_uid)
    for mapping in (adjacency, reverse):
        for uid in mapping:
            mapping[uid] = sorted(mapping[uid], key=lambda item: item.zfill(20))
    return fan_in, fan_out, adjacency, reverse


def _scc_ids(adapter: _ScopeTopologyAdapter, adjacency: Mapping[str, Sequence[str]]) -> dict[str, str]:
    all_uids = sorted((node.uid for node in adapter.workflow.nodes.values()), key=lambda uid: uid.zfill(20))
    neighbors = {uid: list(adjacency.get(uid, ())) for uid in all_uids}
    raw_roots = _tarjan_scc_iterative(neighbors, all_uids)
    ordered_roots = sorted(set(raw_roots.values()), key=lambda uid: uid.zfill(20))
    root_to_id = {root: f"scc{index}" for index, root in enumerate(ordered_roots)}
    return {uid: root_to_id[raw_roots[uid]] for uid in all_uids}


def _wcc_ids(lanes: Mapping[str, tuple[int, int]]) -> dict[str, str]:
    return {uid: f"wcc{band}" for uid, (band, _sub_lane) in lanes.items()}


def _sorted_workflow_nodes(wf: VibeWorkflow) -> list[VibeNode]:
    return sorted(wf.nodes.values(), key=lambda node: node.uid.zfill(20))


def _node_topology_fact(
    adapter: _ScopeTopologyAdapter,
    node: VibeNode,
    layers: Mapping[str, int],
    lanes: Mapping[str, tuple[int, int]],
    fan_in: Mapping[str, int],
    fan_out: Mapping[str, int],
    scc_ids: Mapping[str, str],
    wcc_ids: Mapping[str, str],
) -> NodeTopologyFact:
    ref = adapter.id_to_ref[node.id]
    lane_band, lane_index = lanes.get(node.uid, (0, 0))
    terminal = fan_out.get(node.uid, 0) == 0 and node.class_type not in HELPER_CLASS_TYPES
    return NodeTopologyFact(
        ref=ref,
        class_type=node.class_type,
        fan_in=fan_in.get(node.uid, 0),
        fan_out=fan_out.get(node.uid, 0),
        topological_rank=layers.get(node.uid, 0),
        lane_band=lane_band,
        lane_index=lane_index,
        scc_id=scc_ids.get(node.uid, "scc0"),
        wcc_id=wcc_ids.get(node.uid, "wcc0"),
        terminal=terminal,
        terminal_output_types=_node_output_types(adapter.id_to_node.get(node.id, {})),
    )


def _node_output_types(node: Mapping[str, Any]) -> tuple[str, ...]:
    outputs = node.get("outputs")
    if not isinstance(outputs, Sequence) or isinstance(outputs, (str, bytes)):
        return ()
    types = {
        str(item.get("type"))
        for item in outputs
        if isinstance(item, Mapping) and item.get("type") not in (None, "")
    }
    return tuple(sorted(types))


def _terminal_paths(
    adapter: _ScopeTopologyAdapter,
    adjacency: Mapping[str, Sequence[str]],
    reverse: Mapping[str, Sequence[str]],
) -> tuple[tuple[TerminalPathFact, ...], bool]:
    uid_to_node = {node.uid: node for node in adapter.workflow.nodes.values()}
    terminals = [
        uid
        for uid, node in uid_to_node.items()
        if not adjacency.get(uid) and node.class_type not in HELPER_CLASS_TYPES
    ]
    sources = [
        uid
        for uid, node in uid_to_node.items()
        if not reverse.get(uid) and node.class_type not in HELPER_CLASS_TYPES
    ]
    sources_set = set(sources)
    facts: list[TerminalPathFact] = []
    truncated = False

    def walk(uid: str, path: tuple[str, ...]) -> None:
        nonlocal truncated
        if len(facts) >= _MAX_TERMINAL_PATHS_PER_SCOPE:
            truncated = True
            return
        if len(path) > _MAX_TERMINAL_PATH_DEPTH:
            truncated = True
            return
        if uid in sources_set or not reverse.get(uid):
            refs = tuple(_uid_to_ref(adapter, item) for item in reversed(path))
            terminal_uid = path[0]
            terminal_node = uid_to_node[terminal_uid]
            facts.append(
                TerminalPathFact(
                    scope_path=adapter.scope_path,
                    terminal=_uid_to_ref(adapter, terminal_uid),
                    terminal_type=terminal_node.class_type,
                    path=refs,
                    terminal_output_types=_node_output_types(adapter.id_to_node.get(terminal_node.id, {})),
                )
            )
            return
        for predecessor in reverse.get(uid, ()):
            if predecessor in path:
                continue
            walk(predecessor, (*path, predecessor))

    for terminal_uid in sorted(terminals, key=lambda uid: uid.zfill(20)):
        walk(terminal_uid, (terminal_uid,))
    return tuple(sorted(facts, key=_terminal_path_sort_key)), truncated


def _uid_to_ref(adapter: _ScopeTopologyAdapter, uid: str) -> CanonicalNodeRef:
    for node in adapter.workflow.nodes.values():
        if node.uid == uid:
            return adapter.id_to_ref[node.id]
    return CanonicalNodeRef(adapter.scope_path, uid)


def _terminal_path_sort_key(path: TerminalPathFact) -> tuple[list[str], list[str]]:
    return ([ref.uid.zfill(20) for ref in path.path], path.terminal.to_json())


def _parallel_branch_candidates(
    adapter: _ScopeTopologyAdapter,
    adjacency: Mapping[str, Sequence[str]],
) -> list[ParallelBranchCandidate]:
    candidates: list[ParallelBranchCandidate] = []
    for uid in sorted(adjacency.keys(), key=lambda item: item.zfill(20)):
        children = tuple(adjacency.get(uid, ()))
        if len(children) < 2:
            continue
        terminal_refs = sorted(
            {_uid_to_ref(adapter, terminal) for child in children for terminal in _reachable_terminals(child, adjacency)},
            key=lambda ref: ref.uid.zfill(20),
        )
        candidates.append(
            ParallelBranchCandidate(
                scope_path=adapter.scope_path,
                source=_uid_to_ref(adapter, uid),
                branch_roots=tuple(_uid_to_ref(adapter, child) for child in children),
                terminal_refs=tuple(terminal_refs),
            )
        )
    return candidates


def _reachable_terminals(start: str, adjacency: Mapping[str, Sequence[str]]) -> set[str]:
    pending = [start]
    seen: set[str] = set()
    terminals: set[str] = set()
    while pending:
        uid = pending.pop(0)
        if uid in seen:
            continue
        seen.add(uid)
        children = adjacency.get(uid, ())
        if not children:
            terminals.add(uid)
            continue
        pending.extend(child for child in children if child not in seen)
    return terminals


def _sampler_relation_candidates(
    adapter: _ScopeTopologyAdapter,
    adjacency: Mapping[str, Sequence[str]],
    scc_ids: Mapping[str, str],
    wcc_ids: Mapping[str, str],
) -> list[SamplerRelationClaim]:
    samplers = [
        node.uid
        for node in _sorted_workflow_nodes(adapter.workflow)
        if "sampler" in node.class_type.lower()
    ]
    candidates: list[SamplerRelationClaim] = []
    for index, left in enumerate(samplers):
        for right in samplers[index + 1 :]:
            left_ref = _uid_to_ref(adapter, left)
            right_ref = _uid_to_ref(adapter, right)
            if scc_ids.get(left) == scc_ids.get(right):
                candidates.append(
                    SamplerRelationClaim(
                        kind="same_sampler_pair",
                        samplers=(left_ref, right_ref),
                        reason="samplers share a strongly connected component",
                    )
                )
            elif _has_path(left, right, adjacency):
                candidates.append(
                    SamplerRelationClaim(
                        kind="sampler_precedes",
                        samplers=(left_ref, right_ref),
                        source=left_ref,
                        target=right_ref,
                        reason="topology has a path from source sampler to target sampler",
                    )
                )
            elif _has_path(right, left, adjacency):
                candidates.append(
                    SamplerRelationClaim(
                        kind="sampler_precedes",
                        samplers=(right_ref, left_ref),
                        source=right_ref,
                        target=left_ref,
                        reason="topology has a path from source sampler to target sampler",
                    )
                )
            elif wcc_ids.get(left) == wcc_ids.get(right):
                candidates.append(
                    SamplerRelationClaim(
                        kind="parallel_sampler_branch",
                        samplers=(left_ref, right_ref),
                        reason="samplers share a weak component without direct precedence",
                    )
                )
            else:
                candidates.append(
                    SamplerRelationClaim(
                        kind="independent_samplers",
                        samplers=(left_ref, right_ref),
                        reason="samplers are in different weak components",
                    )
                )
    return candidates


def _has_path(source: str, target: str, adjacency: Mapping[str, Sequence[str]]) -> bool:
    pending = list(adjacency.get(source, ()))
    seen: set[str] = set()
    while pending:
        uid = pending.pop(0)
        if uid == target:
            return True
        if uid in seen:
            continue
        seen.add(uid)
        pending.extend(child for child in adjacency.get(uid, ()) if child not in seen)
    return False


def _summary(
    ledger: EditLedger,
    canonical_refs: Sequence[CanonicalRefFact],
    scope_topologies: Sequence[ScopeTopologyFacts],
) -> GraphFactsSummary:
    summaries: list[ScopeGraphSummary] = []
    helper_refs: list[CanonicalNodeRef] = []
    canonical_node_summaries: list[CanonicalNodeSummary] = []
    sampler_relation_candidates: list[SamplerRelationClaim] = []
    topology_by_scope = {topology.scope_path: topology for topology in scope_topologies}
    refs_by_scope: dict[str, list[CanonicalRefFact]] = {}
    for fact in canonical_refs:
        refs_by_scope.setdefault(fact.ref.scope_path, []).append(fact)
        canonical_node_summaries.append(
            CanonicalNodeSummary(
                ref=fact.ref,
                class_type=fact.class_type,
                title=fact.title,
                role_hint=fact.role_hint,
                is_helper=fact.is_helper,
            )
        )
        if fact.is_helper:
            helper_refs.append(fact.ref)

    for scope_path, scope in _ordered_scopes(ledger):
        node_facts = refs_by_scope.get(scope_path, [])
        helper_count = sum(1 for fact in node_facts if fact.is_helper)
        topology = topology_by_scope.get(scope_path)
        sampler_relation_candidates.extend(
            topology.sampler_relation_candidates if topology is not None else ()
        )
        summaries.append(
            ScopeGraphSummary(
                scope_path=scope_path,
                node_count=len(node_facts),
                edge_count=_edge_count(scope.graph),
                helper_count=helper_count,
                wcc_count=_component_count(topology, "wcc_id"),
                scc_count=_component_count(topology, "scc_id"),
                terminal_refs=tuple(_terminal_refs(scope, node_facts)),
                sampler_refs=tuple(fact.ref for fact in node_facts if fact.role_hint == ROLE_HINT_SAMPLER),
                summarized=topology.truncated if topology is not None else False,
            )
        )

    return GraphFactsSummary(
        canonical_nodes=tuple(canonical_node_summaries),
        scopes=tuple(summaries),
        helper_refs=tuple(helper_refs),
        sampler_relation_candidates=tuple(sampler_relation_candidates),
        truncated=any(topology.truncated for topology in scope_topologies),
    )


def _component_count(topology: ScopeTopologyFacts | None, attr: str) -> int:
    if topology is None:
        return 0
    return len({getattr(fact, attr) for fact in topology.node_topology})


def _edge_count(graph: Mapping[str, Any]) -> int:
    links = graph.get("links")
    if isinstance(links, Sequence) and not isinstance(links, (str, bytes)):
        return sum(1 for link in links if isinstance(link, (Mapping, Sequence)) and not isinstance(link, (str, bytes)))
    return 0


def _terminal_refs(scope: ScopeState, node_facts: Sequence[CanonicalRefFact]) -> list[CanonicalNodeRef]:
    outgoing_ids: set[Any] = set()
    links = scope.graph.get("links")
    if isinstance(links, Sequence) and not isinstance(links, (str, bytes)):
        for link in links:
            origin_id: Any = None
            if isinstance(link, Mapping):
                origin_id = link.get("origin_id")
            elif isinstance(link, Sequence) and not isinstance(link, (str, bytes)) and len(link) >= 2:
                origin_id = link[1]
            if origin_id is not None:
                outgoing_ids.add(origin_id)
    return [
        fact.ref
        for fact in node_facts
        if not fact.is_helper and fact.litegraph_id not in outgoing_ids
    ]


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


build_graph_facts = extract_graph_facts


__all__ = [
    "CanonicalRefFact",
    "GraphInventoryFacts",
    "GroupFact",
    "HelperNodeFact",
    "NodeFurnitureFact",
    "NodeTopologyFact",
    "ParallelBranchCandidate",
    "RerouteFact",
    "ScopeFurnitureFact",
    "ScopeTopologyFacts",
    "TerminalPathFact",
    "TopologyEdgeFact",
    "VirtualWireFact",
    "build_graph_facts",
    "display_ref",
    "extract_graph_facts",
]
