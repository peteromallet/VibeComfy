"""Agent-invoked layout hints for the Implement phase (M2).

``layout_hints(graph, operation, anchors=None)`` is a deterministic,
agent-invoked tool: the agent calls it during implementation to get candidate
positions/groups (with reasons), geometry signals (evidence only), a full-graph
hash, and structured diagnostics.  Nothing in the classify or pipeline path
imports or runs layout analysis automatically — the tool exists solely for
explicit Implement-phase calls (verified by the absence of any layout-hints
import in classify/pipeline code).

Geometry math is delegated to the porting layout machinery
(:func:`~vibecomfy.porting.layout.placement.place_constrained` spiral-ray
placement, reorganise layout assessment) so the deterministic calculations stay
in one place.  When geometry cannot produce a placement (unresolved anchor or
ray-search exhaustion) the candidate is explicitly labeled ``last_resort`` with
its reason and requested anchors recorded in the result.
"""

from __future__ import annotations

from vibecomfy.ingest.normalize import door_get_links, door_get_nodes
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from vibecomfy.porting.emit.ui import _canonicalize_coord
from vibecomfy.porting.layout.placement import _ANCHOR_GAP_PX, place_constrained
from vibecomfy.porting.reorganise.assess import (
    METRIC_BACKWARD_EDGE_RATIO,
    METRIC_GROUP_COHERENCE,
    METRIC_GROUP_SIGNAL_STRENGTH,
    METRIC_HELPER_DISTANCE_WARNING_COUNT,
    METRIC_OVERLAP_COUNT,
    METRIC_SPACING_DENSITY,
    assess_layout_from_ui,
)

from .evidence_pack import _check_keys, _freeze_json, _required_text, _thaw_json
from .tool_contracts import ToolDiagnostic, ToolResult, ToolStatus

# ---------------------------------------------------------------------------
# Operations the tool can advise on.
# ---------------------------------------------------------------------------

OPERATION_INSERT = "insert"
OPERATION_ADD = "add"
OPERATION_MOVE = "move"
OPERATION_CONNECT = "connect"
OPERATION_REORGANISE = "reorganise"

OPERATIONS = frozenset(
    {
        OPERATION_INSERT,
        OPERATION_ADD,
        OPERATION_MOVE,
        OPERATION_CONNECT,
        OPERATION_REORGANISE,
    }
)

# Placement relations (geometry-derived; ``last_resort`` is the explicit
# fallback label).
RELATION_RIGHT_OF = "right_of"
RELATION_LEFT_OF = "left_of"
RELATION_BELOW = "below"
RELATION_ABOVE = "above"
RELATION_BETWEEN = "between"
RELATION_LAST_RESORT = "last_resort"

_RELATIONS = frozenset(
    {
        RELATION_RIGHT_OF,
        RELATION_LEFT_OF,
        RELATION_BELOW,
        RELATION_ABOVE,
        RELATION_BETWEEN,
        RELATION_LAST_RESORT,
    }
)

CANDIDATE_KIND_POSITION = "position"
CANDIDATE_KIND_GROUP = "group"
_CANDIDATE_KINDS = frozenset({CANDIDATE_KIND_POSITION, CANDIDATE_KIND_GROUP})

# Sizing/geometry constants.
_DEFAULT_NODE_SIZE = (320.0, 30.0)
_FALLBACK_POSITION = (float(_ANCHOR_GAP_PX), float(_ANCHOR_GAP_PX))
_DEFAULT_CANVAS_EXTENT = 4000.0
_GROUP_PAD_PX = 24.0
_MAX_FURNITURE_WARNINGS = 5

# Diagnostic codes (status semantics are derived from these in the tool
# wrapper; ``invalid_*``/``missing_*`` map to ``invalid_request``,
# ``empty_graph`` maps to ``no_results``).
DIAG_INVALID_GRAPH = "invalid_graph"
DIAG_EMPTY_GRAPH = "empty_graph"
DIAG_INVALID_OPERATION = "invalid_operation"
DIAG_INVALID_ANCHORS = "invalid_anchors"
DIAG_MISSING_ANCHORS = "missing_anchors"
DIAG_UNRESOLVED_ANCHOR = "unresolved_anchor"
DIAG_LAYOUT_FALLBACK = "layout_fallback"
DIAG_SIGNALS_UNAVAILABLE = "signals_unavailable"
DIAG_NO_INSERTION_POINTS = "no_insertion_points"
DIAG_MISSING_FURNITURE = "missing_furniture"

_INVALID_REQUEST_CODES = frozenset(
    {
        DIAG_INVALID_GRAPH,
        DIAG_INVALID_OPERATION,
        DIAG_INVALID_ANCHORS,
        DIAG_MISSING_ANCHORS,
    }
)

# Metric names surfaced in the geometry signals (evidence only).
_SIGNAL_METRICS = (
    METRIC_OVERLAP_COUNT,
    METRIC_BACKWARD_EDGE_RATIO,
    METRIC_SPACING_DENSITY,
    METRIC_GROUP_SIGNAL_STRENGTH,
    METRIC_GROUP_COHERENCE,
    METRIC_HELPER_DISTANCE_WARNING_COUNT,
)


# ---------------------------------------------------------------------------
# Typed results
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LayoutAnchor:
    """One resolved candidate placement: a target placed relative to an anchor.

    ``relation`` is the geometry-derived compass relation or ``last_resort``
    (the explicit fallback label).  ``anchor`` records the anchor node the
    placement was requested against (the raw reference when it could not be
    resolved), so a fallback always carries its anchors.
    """

    target: str
    anchor: str | None
    relation: str
    position: tuple[float, float]
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "target", _required_text(self.target, "target"))
        if self.anchor is not None:
            object.__setattr__(self, "anchor", _required_text(self.anchor, "anchor"))
        if self.relation not in _RELATIONS:
            raise ValueError(f"`relation` must be one of: {', '.join(sorted(_RELATIONS))}.")
        object.__setattr__(self, "position", _freeze_json(self.position, "position"))
        object.__setattr__(self, "reason", _required_text(self.reason, "reason"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "anchor": self.anchor,
            "relation": self.relation,
            "position": _thaw_json(self.position),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LayoutAnchor":
        if not isinstance(payload, Mapping):
            raise ValueError("LayoutAnchor must be an object.")
        _check_keys(
            payload,
            required=frozenset({"target", "anchor", "relation", "position", "reason"}),
            contract="LayoutAnchor",
        )
        return cls(
            target=payload["target"],
            anchor=payload["anchor"],
            relation=payload["relation"],
            position=payload["position"],
            reason=payload["reason"],
        )


@dataclass(frozen=True, slots=True)
class LayoutCandidate:
    """A candidate position or group, with the reason it was produced."""

    kind: str
    target: str
    reason: str
    position: tuple[float, float] | None = None
    bounds: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.kind not in _CANDIDATE_KINDS:
            raise ValueError(f"`kind` must be one of: {', '.join(sorted(_CANDIDATE_KINDS))}.")
        object.__setattr__(self, "target", _required_text(self.target, "target"))
        object.__setattr__(self, "reason", _required_text(self.reason, "reason"))
        if self.position is not None:
            object.__setattr__(self, "position", _freeze_json(self.position, "position"))
        if self.bounds is not None:
            object.__setattr__(self, "bounds", _freeze_json(self.bounds, "bounds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "reason": self.reason,
            "position": _thaw_json(self.position) if self.position is not None else None,
            "bounds": _thaw_json(self.bounds) if self.bounds is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LayoutCandidate":
        if not isinstance(payload, Mapping):
            raise ValueError("LayoutCandidate must be an object.")
        _check_keys(
            payload,
            required=frozenset({"kind", "target", "reason", "position", "bounds"}),
            contract="LayoutCandidate",
        )
        return cls(
            kind=payload["kind"],
            target=payload["target"],
            reason=payload["reason"],
            position=payload["position"],
            bounds=payload["bounds"],
        )


@dataclass(frozen=True, slots=True)
class LayoutHintsResult:
    """Deterministic layout hints for one agent-invoked call.

    ``signals`` carries the compact geometry assessment (verdict, metrics,
    issues) as *evidence only* — it never contains instructions.  Full source
    geometry stays behind the graph hash; ``diagnostics`` records every
    non-happy path, including explicit ``last_resort`` fallbacks.
    """

    graph_hash: str
    operation: str
    anchors: tuple[LayoutAnchor, ...]
    candidates: tuple[LayoutCandidate, ...]
    signals: Mapping[str, Any]
    fallback_used: bool
    diagnostics: tuple[ToolDiagnostic, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.graph_hash, str):
            raise ValueError("`graph_hash` must be a string.")
        object.__setattr__(self, "operation", _required_text(self.operation, "operation"))
        if not isinstance(self.anchors, (list, tuple)):
            raise ValueError("`anchors` must be a list.")
        object.__setattr__(
            self,
            "anchors",
            tuple(
                item if isinstance(item, LayoutAnchor) else LayoutAnchor.from_dict(item)
                for item in self.anchors
            ),
        )
        if not isinstance(self.candidates, (list, tuple)):
            raise ValueError("`candidates` must be a list.")
        object.__setattr__(
            self,
            "candidates",
            tuple(
                item
                if isinstance(item, LayoutCandidate)
                else LayoutCandidate.from_dict(item)
                for item in self.candidates
            ),
        )
        if not isinstance(self.signals, Mapping):
            raise ValueError("`signals` must be an object.")
        object.__setattr__(self, "signals", _freeze_json(self.signals, "signals"))
        if not isinstance(self.fallback_used, bool):
            raise ValueError("`fallback_used` must be a boolean.")
        if not isinstance(self.diagnostics, (list, tuple)):
            raise ValueError("`diagnostics` must be a list.")
        object.__setattr__(
            self,
            "diagnostics",
            tuple(
                item if isinstance(item, ToolDiagnostic) else ToolDiagnostic.from_dict(item)
                for item in self.diagnostics
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_hash": self.graph_hash,
            "operation": self.operation,
            "anchors": [anchor.to_dict() for anchor in self.anchors],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "signals": _thaw_json(self.signals),
            "fallback_used": self.fallback_used,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LayoutHintsResult":
        if not isinstance(payload, Mapping):
            raise ValueError("LayoutHintsResult must be an object.")
        _check_keys(
            payload,
            required=frozenset({
                "graph_hash",
                "operation",
                "anchors",
                "candidates",
                "signals",
                "fallback_used",
                "diagnostics",
            }),
            contract="LayoutHintsResult",
        )
        return cls(
            graph_hash=payload["graph_hash"],
            operation=payload["operation"],
            anchors=payload["anchors"],
            candidates=payload["candidates"],
            signals=payload["signals"],
            fallback_used=payload["fallback_used"],
            diagnostics=payload["diagnostics"],
        )


# ---------------------------------------------------------------------------
# Graph hashing
# ---------------------------------------------------------------------------


def layout_graph_hash(graph: Mapping[str, Any]) -> str:
    """Return the deterministic full-graph hash used for layout hint caching."""

    raw = json.dumps(
        _jsonish(graph),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonish(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonish(item) for item in value]
    if isinstance(value, list):
        return [_jsonish(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Graph extraction
# ---------------------------------------------------------------------------


def _extract_nodes(graph: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[Any]]:
    """Return ``(node_records, skipped)`` for a UI graph mapping.

    Each record carries ``key`` (uid or str(id), the pinned-map key),
    ``uid``, ``id``, ``class_type``, and ``rect`` (x, y, w, h) when the node
    has both ``pos`` and ``size`` furniture.
    """

    raw = door_get_nodes(graph)
    if not isinstance(raw, list):
        return [], [None]
    records: list[dict[str, Any]] = []
    skipped: list[Any] = []
    for node in raw:
        if not isinstance(node, Mapping):
            skipped.append(node)
            continue
        props = node.get("properties")
        uid = props.get("vibecomfy_uid") if isinstance(props, Mapping) else None
        uid = str(uid).strip() if isinstance(uid, str) and uid.strip() else None
        node_id = node.get("id")
        if isinstance(node_id, bool):
            node_id = None
        if node_id is not None and not isinstance(node_id, (str, int)):
            node_id = None
        key = uid if uid is not None else (str(node_id) if node_id is not None else None)
        if key is None:
            skipped.append(node)
            continue
        pos = _number_pair(node.get("pos"))
        size = _number_pair(node.get("size"))
        rect = None
        if pos is not None and size is not None:
            rect = (pos[0], pos[1], size[0], size[1])
        if rect is None:
            skipped.append(node)
        records.append(
            {
                "key": key,
                "uid": uid,
                "id": node_id,
                "class_type": str(node.get("class_type") or node.get("type") or ""),
                "rect": rect,
            }
        )
    return records, skipped


def _number_pair(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    first, second = value[0], value[1]
    if isinstance(first, bool) or isinstance(second, bool):
        return None
    try:
        x, y = float(first), float(second)
    except (TypeError, ValueError):
        return None
    if not _finite(x) or not _finite(y):
        return None
    return x, y


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def _uid_by_id(records: list[dict[str, Any]]) -> dict[Any, str]:
    mapping: dict[Any, str] = {}
    for record in records:
        if record["id"] is None:
            continue
        mapping.setdefault(record["id"], record["key"])
    return mapping


def _resolve_ref(
    ref: Any,
    uid_by_id: Mapping[Any, str],
    records: list[dict[str, Any]],
) -> str | None:
    """Resolve an anchor/target reference (uid or node id) to a node key."""
    if isinstance(ref, bool):
        return None
    if isinstance(ref, str):
        if any(record["key"] == ref for record in records):
            return ref
        return uid_by_id.get(ref)
    if isinstance(ref, int):
        return uid_by_id.get(ref)
    return None


def _canvas_extent(records: list[dict[str, Any]]) -> float:
    extent = 0.0
    for record in records:
        rect = record["rect"]
        if rect is None:
            continue
        extent = max(extent, rect[0] + rect[2], rect[1] + rect[3])
    return extent if extent > 0.0 else _DEFAULT_CANVAS_EXTENT


# ---------------------------------------------------------------------------
# Geometry signals (evidence only)
# ---------------------------------------------------------------------------


def _geometry_signals(
    graph: Mapping[str, Any],
    records: list[dict[str, Any]],
) -> tuple[dict[str, Any], ToolDiagnostic | None]:
    links = door_get_links(graph)
    edge_count = len(links) if isinstance(links, list) else 0
    raw_groups = graph.get("groups")
    group_count = len(raw_groups) if isinstance(raw_groups, list) else 0
    signals: dict[str, Any] = {
        "verdict": "unavailable",
        "node_count": len(records),
        "edge_count": edge_count,
        "group_count": group_count,
        "canvas_extent": _canvas_extent(records),
        "metrics": {},
        "issues": [],
    }
    if not records:
        return signals, None
    try:
        report = assess_layout_from_ui(graph)
    except Exception:
        diagnostic = ToolDiagnostic(
            DIAG_SIGNALS_UNAVAILABLE,
            "Geometry signals unavailable for this graph payload.",
            {"node_count": len(records)},
        )
        return signals, diagnostic
    signals["verdict"] = str(report.verdict)
    metrics = {metric.name: metric.value for metric in report.metrics}
    signals["metrics"] = {name: metrics.get(name) for name in _SIGNAL_METRICS}
    signals["issues"] = [issue.code for issue in report.issues]
    return signals, None


# ---------------------------------------------------------------------------
# Candidate placement (geometry delegated to the porting machinery)
# ---------------------------------------------------------------------------


def _pinned(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    pinned: dict[str, dict[str, Any]] = {}
    for record in records:
        rect = record["rect"]
        if rect is None:
            continue
        pinned[record["key"]] = {
            "pos": [rect[0], rect[1]],
            "size": [rect[2], rect[3]],
        }
    return pinned


def _bboxes(pinned: Mapping[str, dict[str, Any]]) -> list[tuple[float, float, float, float]]:
    return [
        (entry["pos"][0], entry["pos"][1], entry["size"][0], entry["size"][1])
        for entry in pinned.values()
    ]


def _intersects(
    cx: float,
    cy: float,
    cw: float,
    ch: float,
    bboxes: Sequence[tuple[float, float, float, float]],
) -> bool:
    for bx, by, bw, bh in bboxes:
        if cx < bx + bw and cx + cw > bx and cy < by + bh and ch + cy > by:
            return True
    return False


def _place_relative(
    target: str,
    anchor_ref: Any,
    *,
    records: list[dict[str, Any]],
    uid_by_id: Mapping[Any, str],
    pinned: Mapping[str, dict[str, Any]],
    canvas_extent: float,
    size: tuple[float, float] = _DEFAULT_NODE_SIZE,
) -> tuple[LayoutAnchor, ToolDiagnostic | None]:
    """Place *target* relative to the resolved *anchor_ref*.

    Returns the placement record (relation ``last_resort`` when geometry could
    not resolve a free spot, with the reason and requested anchor recorded) and
    an optional ``unresolved_anchor`` diagnostic.
    """

    anchor_key = _resolve_ref(anchor_ref, uid_by_id, records)
    requested = str(anchor_ref) if anchor_ref is not None else None
    if anchor_key is None:
        diagnostic = ToolDiagnostic(
            DIAG_UNRESOLVED_ANCHOR,
            f"Anchor reference {requested!r} does not resolve to a node in the graph.",
            {"target": target, "anchor": requested},
        )
        return (
            LayoutAnchor(
                target=target,
                anchor=requested,
                relation=RELATION_LAST_RESORT,
                position=_FALLBACK_POSITION,
                reason="no_anchor_resolved",
            ),
            diagnostic,
        )

    anchor_entry = pinned.get(anchor_key)
    if anchor_entry is None:
        diagnostic = ToolDiagnostic(
            DIAG_UNRESOLVED_ANCHOR,
            f"Anchor {requested!r} has no position furniture; cannot place relative to it.",
            {"target": target, "anchor": requested},
        )
        return (
            LayoutAnchor(
                target=target,
                anchor=requested,
                relation=RELATION_LAST_RESORT,
                position=_FALLBACK_POSITION,
                reason="no_anchor_furniture",
            ),
            diagnostic,
        )

    anchor_x = float(anchor_entry["pos"][0])
    anchor_y = float(anchor_entry["pos"][1])
    anchor_w = float(anchor_entry["size"][0])
    anchor_h = float(anchor_entry["size"][1])
    size_w, size_h = float(size[0]), float(size[1])
    x, y = place_constrained(
        target,
        anchor_key,
        pinned=dict(pinned),
        size=(size_w, size_h),
        canvas_extent=canvas_extent,
    )

    if _intersects(x, y, size_w, size_h, _bboxes(pinned)):
        # place_constrained exhausted its ray search and degraded to a
        # right-edge dump that still collides — explicit last resort.
        return (
            LayoutAnchor(
                target=target,
                anchor=anchor_key,
                relation=RELATION_LAST_RESORT,
                position=(x, y),
                reason="ray_exhausted",
            ),
            None,
        )

    initial_x = anchor_x + anchor_w + float(_ANCHOR_GAP_PX)
    initial_y = anchor_y
    if _close(x, initial_x) and _close(y, initial_y):
        relation = RELATION_RIGHT_OF
        reason = "right_of_anchor"
    else:
        relation = _compass_relation(anchor_x, anchor_y, anchor_w, anchor_h, x, y)
        reason = "spiral_ray_search"
    return (
        LayoutAnchor(
            target=target,
            anchor=anchor_key,
            relation=relation,
            position=(x, y),
            reason=reason,
        ),
        None,
    )


def _close(left: float, right: float) -> bool:
    return abs(left - right) < 1e-6


def _compass_relation(
    anchor_x: float,
    anchor_y: float,
    anchor_w: float,
    anchor_h: float,
    x: float,
    y: float,
) -> str:
    center_x = anchor_x + anchor_w / 2.0
    center_y = anchor_y + anchor_h / 2.0
    dx = x - center_x
    dy = y - center_y
    if abs(dx) >= abs(dy):
        return RELATION_RIGHT_OF if dx >= 0 else RELATION_LEFT_OF
    return RELATION_BELOW if dy >= 0 else RELATION_ABOVE


def _free_output_keys(
    records: list[dict[str, Any]],
    graph: Mapping[str, Any],
) -> list[str]:
    """Node keys that are never a link source (free output sockets)."""
    links = door_get_links(graph)
    source_keys: set[str] = set()
    if isinstance(links, list):
        uid_by_id = _uid_by_id(records)
        for link in links:
            if not isinstance(link, Sequence) or isinstance(link, (str, bytes)) or len(link) < 3:
                continue
            resolved = _resolve_ref(link[1], uid_by_id, records)
            if resolved is not None:
                source_keys.add(resolved)
    return [
        record["key"]
        for record in sorted(records, key=lambda item: str(item["key"]).zfill(20))
        if record["key"] not in source_keys and record["rect"] is not None
    ]


def _component_bboxes(
    records: list[dict[str, Any]],
    graph: Mapping[str, Any],
) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Bounding boxes of connected components (from the links array)."""
    rect_by_key = {
        record["key"]: record["rect"]
        for record in records
        if record["rect"] is not None
    }
    if not rect_by_key:
        return []
    parent: dict[str, str] = {key: key for key in rect_by_key}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a: str, b: str) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[root_b] = root_a

    links = door_get_links(graph)
    if isinstance(links, list):
        uid_by_id = _uid_by_id(records)
        for link in links:
            if not isinstance(link, Sequence) or isinstance(link, (str, bytes)) or len(link) < 4:
                continue
            source = _resolve_ref(link[1], uid_by_id, records)
            target = _resolve_ref(link[3], uid_by_id, records)
            if source in rect_by_key and target in rect_by_key and source != target:
                union(source, target)

    components: dict[str, list[str]] = {}
    for key in rect_by_key:
        components.setdefault(find(key), []).append(key)

    boxes: list[tuple[str, tuple[float, float, float, float]]] = []
    for root, members in sorted(components.items(), key=lambda item: item[0].zfill(20)):
        if len(members) < 2:
            continue
        min_x = min(rect_by_key[key][0] for key in members)
        min_y = min(rect_by_key[key][1] for key in members)
        max_x = max(rect_by_key[key][0] + rect_by_key[key][2] for key in members)
        max_y = max(rect_by_key[key][1] + rect_by_key[key][3] for key in members)
        pad = _GROUP_PAD_PX
        boxes.append(
            (
                root,
                (
                    _canonicalize_coord(min_x - pad),
                    _canonicalize_coord(min_y - pad),
                    _canonicalize_coord(max_x - min_x + 2 * pad),
                    _canonicalize_coord(max_y - min_y + 2 * pad),
                ),
            )
        )
    return boxes


def _link_midpoint_candidates(
    records: list[dict[str, Any]],
    graph: Mapping[str, Any],
) -> list[LayoutCandidate]:
    rect_by_key = {
        record["key"]: record["rect"]
        for record in records
        if record["rect"] is not None
    }
    if not rect_by_key:
        return []
    uid_by_id = _uid_by_id(records)
    links = door_get_links(graph)
    if not isinstance(links, list):
        return []
    candidates: list[LayoutCandidate] = []
    for link in links:
        if not isinstance(link, Sequence) or isinstance(link, (str, bytes)) or len(link) < 6:
            continue
        link_id = link[0]
        source = _resolve_ref(link[1], uid_by_id, records)
        target = _resolve_ref(link[3], uid_by_id, records)
        if source not in rect_by_key or target not in rect_by_key:
            continue
        sx, sy, sw, sh = rect_by_key[source]
        tx, ty, tw, th = rect_by_key[target]
        mid_x = (sx + sw + tx) / 2.0
        mid_y = (sy + sh / 2.0 + ty + th / 2.0) / 2.0
        candidates.append(
            LayoutCandidate(
                kind=CANDIDATE_KIND_POSITION,
                target=f"link:{link_id}",
                reason="connect_midpoint",
                position=(
                    _canonicalize_coord(mid_x),
                    _canonicalize_coord(mid_y),
                ),
            )
        )
    return candidates


def _existing_group_candidates(graph: Mapping[str, Any]) -> list[LayoutCandidate]:
    raw_groups = graph.get("groups")
    if not isinstance(raw_groups, list):
        return []
    candidates: list[LayoutCandidate] = []
    for index, group in enumerate(raw_groups):
        if not isinstance(group, Mapping):
            continue
        title = str(group.get("title") or f"group:{index}")
        bounding = _number_quad(group.get("bounding"))
        if bounding is None:
            continue
        candidates.append(
            LayoutCandidate(
                kind=CANDIDATE_KIND_GROUP,
                target=title,
                reason="existing_group",
                bounds=bounding,
            )
        )
    return candidates


def _number_quad(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 4:
        return None
    numbers: list[float] = []
    for item in value[:4]:
        if isinstance(item, bool):
            return None
        try:
            number = float(item)
        except (TypeError, ValueError):
            return None
        if not _finite(number):
            return None
        numbers.append(number)
    return tuple(numbers)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Anchors parameter parsing
# ---------------------------------------------------------------------------


def _parse_anchors_param(
    anchors: Any,
) -> tuple[list[tuple[Any, Any]], ToolDiagnostic | None]:
    """Normalize the ``anchors`` parameter to ``(target, anchor_ref)`` pairs.

    Accepted shapes: a mapping ``{target: anchor_ref}``, a sequence of target
    references (anchor inferred per operation), or ``None``.
    """

    if anchors is None:
        return [], None
    if isinstance(anchors, Mapping):
        pairs: list[tuple[Any, Any]] = []
        for target, anchor_ref in anchors.items():
            if isinstance(target, bool) or not isinstance(target, (str, int)):
                continue
            if anchor_ref is not None and (
                isinstance(anchor_ref, bool) or not isinstance(anchor_ref, (str, int))
            ):
                continue
            pairs.append((target, anchor_ref))
        invalid = [
            key
            for key in anchors
            if isinstance(key, bool)
            or not isinstance(key, (str, int))
            or (
                anchors[key] is not None
                and (
                    isinstance(anchors[key], bool)
                    or not isinstance(anchors[key], (str, int))
                )
            )
        ]
        if invalid:
            return [], ToolDiagnostic(
                DIAG_INVALID_ANCHORS,
                "`anchors` must map string/int targets to string/int anchor references.",
                {"invalid_keys": [str(key) for key in invalid]},
            )
        return pairs, None
    if isinstance(anchors, (list, tuple)):
        for item in anchors:
            if isinstance(item, bool) or not isinstance(item, (str, int)):
                return [], ToolDiagnostic(
                    DIAG_INVALID_ANCHORS,
                    "`anchors` must be a list of string/int target references.",
                    {"invalid": [str(item) for item in anchors]},
                )
        return [(item, None) for item in anchors], None
    return [], ToolDiagnostic(
        DIAG_INVALID_ANCHORS,
        "`anchors` must be a mapping, a list, or null.",
        {},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def layout_hints(
    graph: Mapping[str, Any] | None,
    operation: str,
    anchors: Any = None,
) -> LayoutHintsResult:
    """Return deterministic layout hints for *graph* under *operation*.

    Parameters
    ----------
    graph:
        The ComfyUI canvas graph (mapping with ``nodes`` / ``links`` /
        ``groups``) the agent is editing.
    operation:
        One of ``insert``, ``add``, ``move``, ``connect``, ``reorganise``.
        ``insert``/``add`` and ``move`` use *anchors*; ``connect`` returns
        link-midpoint candidates and ``reorganise`` returns group candidates
        (both ignore *anchors*).
    anchors:
        Optional.  A mapping ``{target: anchor}`` (target = name of the node
        being placed, anchor = existing node uid or id) or a list of target
        references (anchor inferred from free output sockets for
        ``insert``/``add``; ``move`` requires explicit anchors).

    Returns
    -------
    :class:`LayoutHintsResult` with the graph hash, resolved anchor placements,
    candidate positions/groups (each with a reason), geometry signals
    (evidence only), a ``fallback_used`` flag, and structured diagnostics.
    Every unresolved placement is explicitly labeled ``last_resort`` with its
    reason and the requested anchors recorded.

    This tool is agent-invoked only; no classify/pipeline path calls it.
    """

    diagnostics: list[ToolDiagnostic] = []

    if not isinstance(graph, Mapping):
        diagnostics.append(
            ToolDiagnostic(DIAG_INVALID_GRAPH, "`graph` must be a workflow object.", {})
        )
        return _build_result(
            graph_hash="",
            operation=operation,
            anchors=[],
            candidates=[],
            signals=_empty_signals(),
            diagnostics=diagnostics,
        )

    graph_hash = layout_graph_hash(graph)

    operation_valid = operation in OPERATIONS
    if not isinstance(operation, str) or not operation.strip():
        diagnostics.append(
            ToolDiagnostic(
                DIAG_INVALID_OPERATION,
                "`operation` must be a non-empty string.",
                {},
            )
        )
    elif not operation_valid:
        diagnostics.append(
            ToolDiagnostic(
                DIAG_INVALID_OPERATION,
                f"`operation` must be one of: {', '.join(sorted(OPERATIONS))}.",
                {"operation": operation},
            )
        )

    pairs, anchors_diagnostic = _parse_anchors_param(anchors)
    if anchors_diagnostic is not None:
        diagnostics.append(anchors_diagnostic)
    anchors_valid = anchors_diagnostic is None

    records, skipped = _extract_nodes(graph)
    if not records:
        diagnostics.append(
            ToolDiagnostic(
                DIAG_EMPTY_GRAPH,
                "The graph has no analyzable nodes; nothing to lay out.",
                {"node_count": 0},
            )
        )
        signals, signals_diagnostic = _geometry_signals(graph, records)
        if signals_diagnostic is not None:
            diagnostics.append(signals_diagnostic)
        return _build_result(
            graph_hash=graph_hash,
            operation=operation,
            anchors=[],
            candidates=[],
            signals=signals,
            diagnostics=diagnostics,
        )

    if skipped:
        preview = [
            str(item.get("id") if isinstance(item, Mapping) else item)
            for item in skipped
        ]
        diagnostics.append(
            ToolDiagnostic(
                DIAG_MISSING_FURNITURE,
                "Some nodes lack position/size furniture and are excluded from placement geometry.",
                {
                    "skipped": preview[:_MAX_FURNITURE_WARNINGS],
                    "skipped_count": len(skipped),
                },
            )
        )

    signals, signals_diagnostic = _geometry_signals(graph, records)
    if signals_diagnostic is not None:
        diagnostics.append(signals_diagnostic)

    anchors_out: list[LayoutAnchor] = []
    candidates: list[LayoutCandidate] = []

    if operation_valid and anchors_valid:
        pinned = _pinned(records)
        uid_by_id = _uid_by_id(records)
        canvas_extent = _canvas_extent(records)

        if operation in (OPERATION_INSERT, OPERATION_ADD):
            anchors_out, candidates, fallback_diagnostics = _insert_candidates(
                pairs,
                graph=graph,
                records=records,
                uid_by_id=uid_by_id,
                pinned=pinned,
                canvas_extent=canvas_extent,
            )
            diagnostics.extend(fallback_diagnostics)
        elif operation == OPERATION_MOVE:
            if not pairs:
                diagnostics.append(
                    ToolDiagnostic(
                        DIAG_MISSING_ANCHORS,
                        "`move` requires explicit `anchors` mapping {target: anchor}.",
                        {},
                    )
                )
            else:
                anchors_out, fallback_diagnostics = _move_candidates(
                    pairs,
                    records=records,
                    uid_by_id=uid_by_id,
                    pinned=pinned,
                    canvas_extent=canvas_extent,
                )
                diagnostics.extend(fallback_diagnostics)
        elif operation == OPERATION_CONNECT:
            candidates = _link_midpoint_candidates(records, graph)
        elif operation == OPERATION_REORGANISE:
            candidates = [
                LayoutCandidate(
                    kind=CANDIDATE_KIND_GROUP,
                    target=f"component:{root}",
                    reason="connected_component",
                    bounds=box,
                )
                for root, box in _component_bboxes(records, graph)
            ]
            candidates.extend(_existing_group_candidates(graph))

    fallback_used = any(
        anchor.relation == RELATION_LAST_RESORT for anchor in anchors_out
    )
    if fallback_used:
        diagnostics.append(
            ToolDiagnostic(
                DIAG_LAYOUT_FALLBACK,
                "Geometry could not resolve a free placement; one or more candidates are labeled `last_resort`.",
                {
                    "anchors": [
                        anchor.to_dict()
                        for anchor in anchors_out
                        if anchor.relation == RELATION_LAST_RESORT
                    ]
                },
            )
        )

    return _build_result(
        graph_hash=graph_hash,
        operation=operation,
        anchors=anchors_out,
        candidates=candidates,
        signals=signals,
        diagnostics=diagnostics,
        fallback_used=fallback_used,
    )


def _insert_candidates(
    pairs: list[tuple[Any, Any]],
    *,
    graph: Mapping[str, Any],
    records: list[dict[str, Any]],
    uid_by_id: Mapping[Any, str],
    pinned: Mapping[str, dict[str, Any]],
    canvas_extent: float,
) -> tuple[list[LayoutAnchor], list[LayoutCandidate], list[ToolDiagnostic]]:
    anchors_out: list[LayoutAnchor] = []
    diagnostics: list[ToolDiagnostic] = []
    if pairs:
        for target, anchor_ref in pairs:
            if anchor_ref is None:
                # Infer the anchor from a node with a free output socket.
                free_keys = _free_output_keys(records, graph)
                if not free_keys:
                    diagnostics.append(
                        ToolDiagnostic(
                            DIAG_NO_INSERTION_POINTS,
                            f"No node with a free output socket to anchor {target!r} to.",
                            {"target": str(target)},
                        )
                    )
                    anchors_out.append(
                        LayoutAnchor(
                            target=str(target),
                            anchor=None,
                            relation=RELATION_LAST_RESORT,
                            position=_FALLBACK_POSITION,
                            reason="no_inferable_anchor",
                        )
                    )
                    continue
                anchor_ref = free_keys[0]
            anchor, diagnostic = _place_relative(
                str(target),
                anchor_ref,
                records=records,
                uid_by_id=uid_by_id,
                pinned=pinned,
                canvas_extent=canvas_extent,
            )
            anchors_out.append(anchor)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
        return anchors_out, [], diagnostics

    # No anchors given: suggest insertion points right of nodes with free
    # output sockets.
    free_keys = _free_output_keys(records, graph)
    if not free_keys:
        diagnostics.append(
            ToolDiagnostic(
                DIAG_NO_INSERTION_POINTS,
                "No nodes have free output sockets to anchor new nodes to.",
                {},
            )
        )
        return anchors_out, [], diagnostics
    for key in free_keys:
        anchor, diagnostic = _place_relative(
            f"<new:{key}>",
            key,
            records=records,
            uid_by_id=uid_by_id,
            pinned=pinned,
            canvas_extent=canvas_extent,
        )
        anchors_out.append(anchor)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return anchors_out, [], diagnostics


def _move_candidates(
    pairs: list[tuple[Any, Any]],
    *,
    records: list[dict[str, Any]],
    uid_by_id: Mapping[Any, str],
    pinned: Mapping[str, dict[str, Any]],
    canvas_extent: float,
) -> tuple[list[LayoutAnchor], list[ToolDiagnostic]]:
    anchors_out: list[LayoutAnchor] = []
    diagnostics: list[ToolDiagnostic] = []
    for target, anchor_ref in pairs:
        target_key = _resolve_ref(target, uid_by_id, records)
        if target_key is None:
            requested = str(target)
            diagnostics.append(
                ToolDiagnostic(
                    DIAG_UNRESOLVED_ANCHOR,
                    f"Target reference {requested!r} does not resolve to a node in the graph.",
                    {
                        "target": requested,
                        "anchor": str(anchor_ref) if anchor_ref is not None else None,
                    },
                )
            )
            anchors_out.append(
                LayoutAnchor(
                    target=requested,
                    anchor=str(anchor_ref) if anchor_ref is not None else None,
                    relation=RELATION_LAST_RESORT,
                    position=_FALLBACK_POSITION,
                    reason="no_target_resolved",
                )
            )
            continue
        rect = next(record["rect"] for record in records if record["key"] == target_key)
        size = (rect[2], rect[3]) if rect is not None else _DEFAULT_NODE_SIZE
        anchor, diagnostic = _place_relative(
            target_key,
            anchor_ref,
            records=records,
            uid_by_id=uid_by_id,
            pinned=pinned,
            canvas_extent=canvas_extent,
            size=size,
        )
        anchors_out.append(anchor)
        if diagnostic is not None:
            diagnostics.append(diagnostic)
    return anchors_out, diagnostics


def _build_result(
    *,
    graph_hash: str,
    operation: str,
    anchors: list[LayoutAnchor],
    candidates: list[LayoutCandidate],
    signals: Mapping[str, Any],
    diagnostics: list[ToolDiagnostic],
    fallback_used: bool = False,
) -> LayoutHintsResult:
    return LayoutHintsResult(
        graph_hash=graph_hash,
        operation=operation,
        anchors=anchors,
        candidates=candidates,
        signals=signals,
        fallback_used=fallback_used,
        diagnostics=diagnostics,
    )


def _empty_signals() -> dict[str, Any]:
    return {
        "verdict": "unavailable",
        "node_count": 0,
        "edge_count": 0,
        "group_count": 0,
        "canvas_extent": _DEFAULT_CANVAS_EXTENT,
        "metrics": {},
        "issues": [],
    }


def _status_from_diagnostics(diagnostics: Sequence[ToolDiagnostic]) -> ToolStatus:
    codes = frozenset(diagnostic.code for diagnostic in diagnostics)
    if codes & _INVALID_REQUEST_CODES:
        return ToolStatus.INVALID_REQUEST
    if DIAG_EMPTY_GRAPH in codes:
        return ToolStatus.NO_RESULTS
    return ToolStatus.OK


def layout_hints_tool(
    graph: Mapping[str, Any] | None,
    operation: str,
    anchors: Any = None,
) -> ToolResult:
    """F01-typed tool envelope for :func:`layout_hints`.

    Maps diagnostics to the typed status contract: invalid graph/operation/
    anchors → ``invalid_request``; an empty graph → ``no_results``; otherwise
    ``ok`` with the full hints payload.
    """

    result = layout_hints(graph, operation, anchors=anchors)
    return ToolResult(
        tool_name="layout_hints",
        status=_status_from_diagnostics(result.diagnostics),
        result=result.to_dict(),
        diagnostics=result.diagnostics,
    )


__all__ = [
    "CANDIDATE_KIND_GROUP",
    "CANDIDATE_KIND_POSITION",
    "DIAG_EMPTY_GRAPH",
    "DIAG_INVALID_ANCHORS",
    "DIAG_INVALID_GRAPH",
    "DIAG_INVALID_OPERATION",
    "DIAG_LAYOUT_FALLBACK",
    "DIAG_MISSING_ANCHORS",
    "DIAG_MISSING_FURNITURE",
    "DIAG_NO_INSERTION_POINTS",
    "DIAG_SIGNALS_UNAVAILABLE",
    "DIAG_UNRESOLVED_ANCHOR",
    "LayoutAnchor",
    "LayoutCandidate",
    "LayoutHintsResult",
    "OPERATION_ADD",
    "OPERATION_CONNECT",
    "OPERATION_INSERT",
    "OPERATION_MOVE",
    "OPERATION_REORGANISE",
    "OPERATIONS",
    "RELATION_ABOVE",
    "RELATION_BELOW",
    "RELATION_BETWEEN",
    "RELATION_LAST_RESORT",
    "RELATION_LEFT_OF",
    "RELATION_RIGHT_OF",
    "layout_graph_hash",
    "layout_hints",
    "layout_hints_tool",
]
