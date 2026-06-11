"""Engine composition — Phase 2 Step 6.

:func:`layout` is the public entry-point.  It orchestrates all Phase-1/2
primitives into a :class:`LayoutResult` in ten ordered phases:

1. Reserved leaf column (ordered list of in-degree-0 leaf control nodes).
2. :func:`~vibecomfy.porting.layout.layering.compute_layers`.
3. :func:`~vibecomfy.porting.layout.lanes.assign_lanes`.
4. Barycenter sweep gate stub (gated by ``_BARYCENTER_SWEEP``; T11).
5. Sizing via :func:`~vibecomfy.porting.layout.sizing.estimate_node_size`.
6. Position composition.
7. Pinned override (pass-through pos + size verbatim).
8. Anchored placement via :func:`~vibecomfy.porting.layout.placement.place_constrained`.
9. :func:`~vibecomfy.porting.layout.groups.build_subgraph_groups`.
10. Return :class:`~vibecomfy.porting.layout.types.LayoutResult`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from vibecomfy.porting.layout.groups import build_subgraph_groups
from vibecomfy.porting.layout.lanes import (
    _BAND_GAP_PX,
    _COLUMN_PITCH_PX,
    _ROW_PITCH_PX,
    assign_lanes,
)
from vibecomfy.porting.layout import layering as _layering_mod
from vibecomfy.porting.layout.layering import _role_precedence_rank, compute_layers
from vibecomfy.porting.layout.placement import place_constrained
from vibecomfy.porting.layout.sizing import _DEFAULT_NODE_WIDTH, estimate_node_size
from vibecomfy.porting.layout.types import LayoutResult
from vibecomfy.porting.emit.ui import _canonicalize_coord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Leaf control classes eligible for the reserved leaf column.
_LEAF_CONTROL_CLASSES: tuple[str, ...] = (
    "PrimitiveNode",
    "PrimitiveString",
    "PrimitiveInt",
    "PrimitiveFloat",
    "LoadImage",
    "LoadImageMask",
    "LoadAudio",
    "LoadVideo",
    "VHS_LoadVideo",
    "IntegerPrimitive",
    "StringConstant",
    "FloatConstant",
)

# Gate flag for Phase 4 barycenter sweep; enabled per T11.
_BARYCENTER_SWEEP = True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def layout(
    wf: Any,
    *,
    schema_provider: Any = None,
    schema_cache: dict[str, Any] | None = None,
    pinned: dict[str, dict[str, Any]] | None = None,
    anchors: dict[str, Any] | None = None,
) -> LayoutResult:
    """Compute fresh layout for every node in *wf*.

    Parameters
    ----------
    wf:
        Workflow object with ``wf.nodes``, ``wf.edges``, ``wf.inputs``, and
        ``wf.metadata``.
    schema_provider:
        Optional schema provider; ``get_schema(class_type)`` is called only
        via :func:`_schema_for` (the single call site).
    schema_cache:
        Optional mutable dict used as a write-through cache.  If *class_type*
        is already present, the provider is never called.
    pinned:
        ``{uid: {pos: [x, y], size: [w, h]}, ...}`` — positions passed through
        verbatim in Phase 7, overriding layered geometry for those nodes.
    anchors:
        ``{new_uid: anchor_uid, ...}`` — new nodes whose positions are resolved
        via :func:`~vibecomfy.porting.layout.placement.place_constrained` in
        Phase 8.

    Returns
    -------
    :class:`~vibecomfy.porting.layout.types.LayoutResult`
    """
    # ── Centralized schema lookup (only call site for get_schema) ────────
    def _schema_for(class_type: str) -> Any:
        if schema_cache is not None and class_type in schema_cache:
            return schema_cache[class_type]
        if schema_provider is not None:
            schema = schema_provider.get_schema(class_type)
            if schema_cache is not None:
                schema_cache[class_type] = schema
            return schema
        return None

    # ── Phase 1: Reserved leaf column ────────────────────────────────────
    # id→uid translation (used in in-degree computation and later phases).
    id_to_uid: dict[str, str] = {n.id: n.uid for n in wf.nodes.values()}

    # Compute in-degree via id→uid-translated edge list (pre-broadcast).
    in_degree: dict[str, int] = {n.uid: 0 for n in wf.nodes.values()}
    for edge in wf.edges:
        to_uid = id_to_uid.get(edge.to_node)
        if to_uid is not None and to_uid in in_degree:
            in_degree[to_uid] += 1

    leaf_set: set[str] = {
        n.uid
        for n in wf.nodes.values()
        if n.class_type in _LEAF_CONTROL_CLASSES and in_degree.get(n.uid, 0) == 0
    }

    # Order by wf.inputs keys first (public-IO ordering), then uid.zfill(20).
    wf_inputs: dict[str, Any] = getattr(wf, "inputs", {}) or {}
    inputs_ordered: list[str] = []
    seen_in_inputs: set[str] = set()
    for _name, vi in wf_inputs.items():
        node_id = getattr(vi, "node_id", None)
        if node_id is not None:
            uid = id_to_uid.get(str(node_id))
            if uid is not None and uid in leaf_set and uid not in seen_in_inputs:
                inputs_ordered.append(uid)
                seen_in_inputs.add(uid)

    leaf_column: list[str] = inputs_ordered + sorted(
        (uid for uid in leaf_set if uid not in seen_in_inputs),
        key=lambda u: u.zfill(20),
    )
    leaf_column_index: dict[str, int] = {uid: idx for idx, uid in enumerate(leaf_column)}

    # ── Phase 2: compute_layers ──────────────────────────────────────────
    layers: dict[str, int] = compute_layers(wf)

    # ── Phase 3: assign_lanes ────────────────────────────────────────────
    lane_indices: dict[str, tuple[int, int]] = assign_lanes(wf, layers)

    # ── Phase 4: Barycenter crossing-reduction sweep ────────────────────
    if _BARYCENTER_SWEEP:
        # Build predecessor map: uid → list of predecessor uids (translated).
        _preds: dict[str, list[str]] = {n.uid: [] for n in wf.nodes.values()}
        for edge in wf.edges:
            from_uid = id_to_uid.get(edge.from_node)
            to_uid = id_to_uid.get(edge.to_node)
            if from_uid is not None and to_uid is not None and to_uid in _preds:
                _preds[to_uid].append(from_uid)

        # Group nodes into (band, layer) cells.
        _cell_nodes: dict[tuple[int, int], list[str]] = {}
        for uid, (band, _sub) in lane_indices.items():
            layer = layers.get(uid, 0)
            _cell_nodes.setdefault((band, layer), []).append(uid)

        # Build uid → class_type map for role-precedence tie-break.
        _uid_class_type: dict[str, str] = {
            n.uid: n.class_type for n in wf.nodes.values()
        }

        # Process each cell in deterministic order.
        for (band, layer) in sorted(_cell_nodes.keys()):
            cell_uids = _cell_nodes[(band, layer)]

            # Compute barycenter score for each node in this cell.
            _bary_scores: dict[str, float] = {}
            for uid in cell_uids:
                current_sub_lane = float(lane_indices[uid][1])
                # Preds in the previous layer (layer-1).
                layer_preds = [
                    p for p in _preds.get(uid, [])
                    if layers.get(p, 0) == layer - 1
                ]
                if layer_preds:
                    _bary_scores[uid] = sum(
                        float(lane_indices[p][1]) for p in layer_preds
                    ) / float(len(layer_preds))
                else:
                    _bary_scores[uid] = current_sub_lane

            # Sort key: (bary_score, [role_rank], uid.zfill(20)).
            # Role-rank tie-break is gated by _ROLE_CROSSING_REDUCTION_TIEBREAK
            # (accessed via module ref so runtime toggle changes take effect).
            if _layering_mod._ROLE_CROSSING_REDUCTION_TIEBREAK:
                cell_uids.sort(
                    key=lambda u: (
                        _bary_scores[u],
                        _role_precedence_rank(_uid_class_type.get(u, "")),
                        u.zfill(20),
                    )
                )
            else:
                cell_uids.sort(key=lambda u: (_bary_scores[u], u.zfill(20)))
            for new_sub_lane, uid in enumerate(cell_uids):
                lane_indices[uid] = (band, new_sub_lane)

    # ── Phase 5: Sizing ──────────────────────────────────────────────────
    sizes: dict[str, tuple[int, int]] = {}
    for node in wf.nodes.values():
        schema = _schema_for(node.class_type)
        sizes[node.uid] = estimate_node_size(node, schema)

    # ── Phase 6: Position composition ───────────────────────────────────
    # Max height per (band, layer) cell — determines row pitch.
    band_layer_max_height: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for uid, (band, _sub) in lane_indices.items():
        layer = layers.get(uid, 0)
        h = sizes[uid][1]
        if h > band_layer_max_height[band][layer]:
            band_layer_max_height[band][layer] = h

    # Max layer per band — determines horizontal extent for band_offset_x.
    band_max_layer: dict[int, int] = {}
    for uid, (band, _sub) in lane_indices.items():
        layer = layers.get(uid, 0)
        if band not in band_max_layer or layer > band_max_layer[band]:
            band_max_layer[band] = layer

    # Cumulative x offsets so bands don't overlap horizontally.
    # Each band's x-extent = (max_layer + 1) * _COLUMN_PITCH_PX + _DEFAULT_NODE_WIDTH.
    band_offset_x_map: dict[int, float] = {}
    cumulative_x = 0.0
    for band in sorted(band_max_layer.keys()):
        band_offset_x_map[band] = cumulative_x
        band_x_extent = float((band_max_layer[band] + 1) * _COLUMN_PITCH_PX + _DEFAULT_NODE_WIDTH)
        cumulative_x += band_x_extent + float(_BAND_GAP_PX)

    # Compute per-(band,layer) max sub_lane among NON-leaf nodes so leaf
    # column placement starts after the last non-leaf node in the same cell,
    # avoiding placement collisions (all nodes stacked at same y).
    _max_non_leaf_sub_lane: dict[tuple[int, int], int] = defaultdict(int)
    for node in wf.nodes.values():
        uid = node.uid
        band, sub = lane_indices.get(uid, (0, 0))
        layer = layers.get(uid, 0)
        if uid not in leaf_column_index:
            key = (band, layer)
            if sub > _max_non_leaf_sub_lane[key]:
                _max_non_leaf_sub_lane[key] = sub

    positions: dict[str, dict[str, Any]] = {}
    for node in wf.nodes.values():
        uid = node.uid
        band, sub_lane = lane_indices.get(uid, (0, 0))
        layer = layers.get(uid, 0)

        # Reserved leaf column: override sub_lane for leaf control nodes,
        # placing them after the last non-leaf node in the same (band,layer).
        if uid in leaf_column_index:
            sub_lane = _max_non_leaf_sub_lane.get((band, layer), -1) + 1 + leaf_column_index[uid]

        band_offset_x = band_offset_x_map.get(band, 0.0)
        max_h = float(band_layer_max_height[band][layer])

        x = float(layer) * float(_COLUMN_PITCH_PX) + band_offset_x
        y = float(sub_lane) * (max_h + float(_ROW_PITCH_PX))

        w, h = sizes[uid]
        positions[uid] = {
            "pos": [_canonicalize_coord(x), _canonicalize_coord(y)],
            "size": [_canonicalize_coord(float(w)), _canonicalize_coord(float(h))],
        }

    # ── Phase 7: Pinned override ─────────────────────────────────────────
    if pinned:
        for uid, entry in pinned.items():
            pos = entry.get("pos", [0.0, 0.0])
            sz = entry.get("size", [float(_DEFAULT_NODE_WIDTH), 30.0])
            positions[uid] = {
                "pos": [
                    _canonicalize_coord(float(pos[0])),
                    _canonicalize_coord(float(pos[1])),
                ],
                "size": [
                    _canonicalize_coord(float(sz[0])),
                    _canonicalize_coord(float(sz[1])),
                ],
            }

    # ── Phase 8: Anchored placement ──────────────────────────────────────
    if anchors:
        canvas_extent = cumulative_x if cumulative_x > 0.0 else 4000.0
        for new_uid, anchor_uid in anchors.items():
            sz = sizes.get(new_uid, (_DEFAULT_NODE_WIDTH, 30))
            x, y = place_constrained(
                new_uid,
                str(anchor_uid),
                pinned=positions,
                size=(float(sz[0]), float(sz[1])),
                canvas_extent=canvas_extent,
            )
            w, h = sz
            positions[new_uid] = {
                "pos": [x, y],
                "size": [_canonicalize_coord(float(w)), _canonicalize_coord(float(h))],
            }

    # ── Phase 9: build_subgraph_groups ───────────────────────────────────
    groups = build_subgraph_groups(wf, positions=positions, sizes=sizes)

    # ── Phase 10: Return LayoutResult ───────────────────────────────────
    return LayoutResult(positions=positions, groups=groups)
