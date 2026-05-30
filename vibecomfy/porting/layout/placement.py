"""Constrained new-node placement for the fresh-layout engine.

Phase 2 Step 4: :func:`place_constrained` returns ``(x, y)`` for a new node
anchored relative to an existing node, dodging pinned nodes via a spiral-ray
geometric search.  All returned coords pass through ``_canonicalize_coord``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from vibecomfy.porting.ui_emitter import _canonicalize_coord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# Gap between nodes (pixels).
_ANCHOR_GAP_PX = 40

# Step size for spiral-ray radii (pixels).
_STEP = 60

# Maximum ray steps before fallback.
# Capped at max(64, canvas_extent // _STEP) when ray scan runs.
_BASE_MAX_RAY_STEPS = 64

# Compass directions in fixed clockwise order: N → NE → E → SE → S → SW → W → NW
_DIRECTIONS: tuple[tuple[float, float], ...] = (
    ( 0, -1),  # N
    ( 1, -1),  # NE
    ( 1,  0),  # E
    ( 1,  1),  # SE
    ( 0,  1),  # S
    (-1,  1),  # SW
    (-1,  0),  # W
    (-1, -1),  # NW
)


def place_constrained(
    new_uid: str,
    anchor_uid: str,
    *,
    pinned: dict[str, dict[str, Any]],
    size: tuple[float, float],
    canvas_extent: float,
) -> tuple[float, float]:
    """Return a placement ``(x, y)`` for *new_uid* near *anchor_uid*.

    Parameters
    ----------
    new_uid:
        UID of the node being placed (for logging only).
    anchor_uid:
        UID of an already-placed node serving as the anchor.
    pinned:
        ``{uid: {pos: [x, y], size: [w, h]}, ...}`` of already-placed nodes.
        Sorted internally by ``uid.zfill(20)`` for deterministic behaviour.
    size:
        ``(width, height)`` of the new node.
    canvas_extent:
        Approximate canvas extent (pixels) used to cap the ray search.

    Returns
    -------
    ``(x, y)`` both passed through ``_canonicalize_coord``.
    """
    # ── Validate anchor ──────────────────────────────────────────────
    anchor = pinned.get(anchor_uid)
    if anchor is None:
        # Anchor not in pinned yet — place at a safe default.
        x = float(_ANCHOR_GAP_PX)
        y = float(_ANCHOR_GAP_PX)
        return _canonicalize_coord(x), _canonicalize_coord(y)

    anchor_pos = anchor["pos"]
    anchor_size = anchor["size"]
    anchor_x = float(anchor_pos[0])
    anchor_y = float(anchor_pos[1])
    anchor_w = float(anchor_size[0])

    new_w = float(size[0])
    new_h = float(size[1])

    # ── Build pinned bboxes (sorted for determinism) ─────────────────
    bboxes: list[tuple[float, float, float, float]] = []
    for uid in sorted(pinned.keys(), key=lambda u: u.zfill(20)):
        entry = pinned[uid]
        pos = entry["pos"]
        sz = entry["size"]
        bboxes.append((float(pos[0]), float(pos[1]), float(sz[0]), float(sz[1])))

    # ── Initial candidate: right of anchor ───────────────────────────
    initial_x = anchor_x + anchor_w + float(_ANCHOR_GAP_PX)
    initial_y = anchor_y

    max_ray_steps = max(_BASE_MAX_RAY_STEPS, int(canvas_extent // _STEP))

    def _intersects(cx: float, cy: float, cw: float, ch: float) -> bool:
        """Check if ``(cx, cy, cw, ch)`` intersects any pinned bbox."""
        for bx, by, bw, bh in bboxes:
            # AABB overlap test
            if cx < bx + bw and cx + cw > bx and cy < by + bh and ch + cy > by:
                return True
        return False

    # ── Check initial candidate ──────────────────────────────────────
    candidate_x = initial_x
    candidate_y = initial_y
    if not _intersects(candidate_x, candidate_y, new_w, new_h):
        return _canonicalize_coord(candidate_x), _canonicalize_coord(candidate_y)

    # ── Spiral-ray search ────────────────────────────────────────────
    step = 1
    while step <= max_ray_steps:
        radius = float(step * _STEP)
        for dx, dy in _DIRECTIONS:
            # Clamp diagonal so all 8 directions have comparable step sizes.
            if dx != 0 and dy != 0:
                r = radius / math.sqrt(2)
            else:
                r = radius
            cx = initial_x + dx * r
            cy = initial_y + dy * r
            if not _intersects(cx, cy, new_w, new_h):
                return _canonicalize_coord(cx), _canonicalize_coord(cy)
        step += 1

    # ── Cap exhaustion → fallback right-edge dump ────────────────────
    fallback_x = initial_x  # already includes anchor_w + gap
    fallback_y = initial_y
    logger.warning(
        "place_constrained: ray cap reached; degrading to right-edge dump for uid=%s",
        new_uid,
    )
    return _canonicalize_coord(fallback_x), _canonicalize_coord(fallback_y)
