"""WCC-based lane assignment for the fresh-layout engine.

Phase 1 Step 3: :func:`assign_lanes` returns ``{uid: (band_index, sub_lane_index)}``
by computing weakly-connected components via union-find on the undirected view
of the id→uid-translated edges, then assigning one band per WCC and
deterministic sub-lane indices within each ``(band, layer)`` cell.

Named constants ``_COLUMN_PITCH_PX``, ``_ROW_PITCH_PX``, and ``_BAND_GAP_PX``
define the pixel geometry; :func:`compute_canvas_extent` derives the total
canvas width from the lane assignment.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

_COLUMN_PITCH_PX = 520   # Horizontal spacing between sub-lanes (pixels).
_ROW_PITCH_PX = 40       # Vertical spacing between layers (pixels).
_BAND_GAP_PX = 80        # Horizontal gap between bands (pixels).

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assign_lanes(wf: Any, layers: dict[str, int]) -> dict[str, tuple[int, int]]:
    """Return ``{uid: (band_index, sub_lane_index)}`` for every node in *wf*.

    The workflow object is expected to have ``wf.nodes`` (``dict[str, VibeNode]``)
    and ``wf.edges`` (``list[VibeEdge]``).  Every edge's ``from_node`` / ``to_node``
    is translated through ``id_to_uid`` before WCC construction (same discipline
    as :func:`vibecomfy.porting.layout.layering.compute_layers`).

    WCCs are detected via union-find on the **undirected** view of the translated
    edges.  Each WCC becomes one *band*.  Bands are ordered by the minimum
    ``uid.zfill(20)`` among their members.  Within each ``(band, layer)`` cell,
    nodes are sorted by ``(class_type, uid.zfill(20))`` and assigned monotonically
    increasing *sub-lane* indices starting from ``0``.
    """
    # ── Build id → uid translation table ──────────────────────────────
    id_to_uid: dict[str, str] = {
        n.id: n.uid for n in wf.nodes.values()
    }

    all_uids: list[str] = sorted(
        (n.uid for n in wf.nodes.values()),
        key=lambda u: u.zfill(20),
    )

    # ── Union-Find on undirected view ─────────────────────────────────
    parent: dict[str, str] = {uid: uid for uid in all_uids}

    def _find(x: str) -> str:
        """Path-compressing find."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: str, b: str) -> None:
        ra, rb = _find(a), _find(b)
        if ra == rb:
            return
        # Union by uid.zfill(20) — smaller uid becomes root for determinism.
        if ra.zfill(20) < rb.zfill(20):
            parent[rb] = ra
        else:
            parent[ra] = rb

    # Process every edge (undirected — one edge joins both endpoints).
    for edge in wf.edges:
        from_uid = id_to_uid.get(edge.from_node)
        to_uid = id_to_uid.get(edge.to_node)
        if from_uid is None:
            logger.debug(
                "assign_lanes: unknown from_node=%r in edge; dropping",
                edge.from_node,
            )
            continue
        if to_uid is None:
            logger.debug(
                "assign_lanes: unknown to_node=%r in edge; dropping",
                edge.to_node,
            )
            continue
        _union(from_uid, to_uid)

    # ── Group nodes by WCC ────────────────────────────────────────────
    # wcc_members: root → list of member uids
    wcc_members: dict[str, list[str]] = {}
    for uid in all_uids:
        root = _find(uid)
        wcc_members.setdefault(root, []).append(uid)

    # Sort WCCs by minimum uid.zfill(20) to assign band indices.
    wcc_roots = sorted(wcc_members.keys(), key=lambda r: r.zfill(20))

    # ── Assign (band, sub_lane) per uid ───────────────────────────────
    result: dict[str, tuple[int, int]] = {}

    for band_index, root in enumerate(wcc_roots):
        members = wcc_members[root]
        # Group members by layer.
        layer_buckets: dict[int, list[str]] = {}
        for uid in members:
            layer = layers.get(uid, 0)
            layer_buckets.setdefault(layer, []).append(uid)

        for layer, bucket in layer_buckets.items():
            # Within a (band, layer) cell, sort by (class_type, uid.zfill(20)).
            # We need the node's class_type; look it up from wf.nodes via uid.
            # Build a lookup first for efficiency.
            uid_to_class: dict[str, str] = {}
            for n in wf.nodes.values():
                if n.uid in members:
                    uid_to_class[n.uid] = n.class_type

            def _sort_key(uid: str) -> tuple[str, str]:
                return (uid_to_class.get(uid, ""), uid.zfill(20))

            bucket.sort(key=_sort_key)

            for sub_lane, uid in enumerate(bucket):
                result[uid] = (band_index, sub_lane)

    # ── Soft totality: any uid not yet assigned gets band 0, sub_lane 0 ──
    missed: list[str] = []
    for uid in all_uids:
        if uid not in result:
            result[uid] = (0, 0)
            missed.append(uid)

    if missed:
        logger.warning(
            "assign_lanes: %d uid(s) not assigned by lane walk; "
            "defaulted to (0, 0): %s",
            len(missed),
            ", ".join(sorted(missed, key=lambda u: u.zfill(20))),
        )

    return result


def compute_canvas_extent(
    lanes: dict[str, tuple[int, int]],
    layers: dict[str, int],
) -> float:
    """Compute the total canvas width (x extent) implied by *lanes*.

    For each band, the extent is the maximum across its layers of
    ``(max_sub_lane_in_layer + 1) * _COLUMN_PITCH_PX``.
    The canvas extent is the sum of all band extents plus ``_BAND_GAP_PX``
    gaps between adjacent bands.
    """
    if not lanes:
        return 0.0

    # per_band_layers: band_index → {layer: max_sub_lane}
    per_band_layers: dict[int, dict[int, int]] = {}

    for uid, (band, sub_lane) in lanes.items():
        layer = layers.get(uid, 0)
        band_layers = per_band_layers.setdefault(band, {})
        band_layers[layer] = max(band_layers.get(layer, -1), sub_lane)

    if not per_band_layers:
        return 0.0

    band_extents: list[float] = []
    for band in sorted(per_band_layers.keys()):
        max_width = 0.0
        for layer, max_sub in per_band_layers[band].items():
            width = (max_sub + 1) * _COLUMN_PITCH_PX
            if width > max_width:
                max_width = width
        band_extents.append(max_width)

    canvas = sum(band_extents) + (len(band_extents) - 1) * _BAND_GAP_PX
    return canvas
