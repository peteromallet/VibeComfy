"""Subgraph bounding-box groups for the fresh-layout engine.

Phase 2 Step 5: :func:`build_subgraph_groups` reads subgraph definitions from
``wf.metadata['definitions']['subgraphs']`` and produces a list of group dicts
with titled boxes, colours from a fixed palette, and canonicalized bounding
values.  Partial inner-uid matches are debug-logged; fully unmatched subgraphs
are skipped.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List

from vibecomfy.porting.emit.ui import _canonicalize_coord

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

# Padding added to each side of the bounding box (pixels).
_GROUP_PAD_PX = 24

# Role-color palette: named roles get consistent colors across workflows.
# Subgraph names without a named role fall through to a deterministic hash-
# based selection from the extended fallback palette.
_ROLE_COLOR_MAP: dict[str, str] = {
    # UUID subgraphs — teal
    "uuid": "#3f7e7e",
    # Video combine / output subgraphs — plum
    "vhs": "#7e3f7e",
    "videocombine": "#7e3f7e",
    # Audio subgraphs — olive
    "audio": "#7e7e3f",
    # Image-processing subgraphs — navy
    "image": "#3f3f7e",
    # Misc / generic subgraphs — rust
    "default": "#7e3f3f",
}

# Fallback palette for hash-based assignment when no named role matches.
_FALLBACK_PALETTE: tuple[str, ...] = (
    "#3f7e7e",
    "#7e3f7e",
    "#7e7e3f",
    "#3f3f7e",
    "#7e3f3f",
    "#5f9f9f",
    "#9f5f9f",
    "#9f9f5f",
    "#5f5f9f",
    "#9f5f5f",
    "#4f8f8f",
    "#8f4f8f",
)


def _role_color_for_subgraph(name: str) -> str:
    """Return a consistent colour for *name* based on its role.

    If *name* matches a known role key (case-insensitive substring match
    against ``_ROLE_COLOR_MAP``), the mapped colour is returned.  Otherwise
    a deterministic hash of *name* modulo ``len(_FALLBACK_PALETTE)`` is used
    so the same name always maps to the same colour across workflows.
    """
    name_lower = name.lower()
    for role_key, colour in _ROLE_COLOR_MAP.items():
        if role_key in name_lower:
            return colour
    # Deterministic hash fallback. Use a stable digest, NOT builtin hash() —
    # hash() is PYTHONHASHSEED-randomized per process, so it would pick a different
    # colour for the same name across runs (despite the docstring's promise), which
    # also defeats the byte-identical agent-edit guard. blake2b is process-stable.
    h = int.from_bytes(hashlib.blake2b(name.encode("utf-8"), digest_size=4).digest(), "big")
    return _FALLBACK_PALETTE[h % len(_FALLBACK_PALETTE)]


def build_subgraph_groups(
    wf: Any,
    *,
    positions: dict[str, dict[str, Any]],
    sizes: dict[str, tuple[int, int]],
) -> list[dict[str, Any]]:
    """Return a list of group-dicts for materializable subgraph bounding boxes.

    Parameters
    ----------
    wf:
        Workflow object with ``wf.metadata['definitions']['subgraphs']``.
    positions:
        ``{uid: {pos: [x, y]}, ...}`` of already-computed node positions.
    sizes:
        ``{uid: (w, h)}`` of already-computed node sizes.

    Returns
    -------
    A list of group dicts, each with keys ``title``, ``bounding``, and ``color``.
    Empty list when no subgraphs are present or no nodes matched.
    """
    metadata = getattr(wf, "metadata", None)
    if not isinstance(metadata, dict):
        return []

    definitions = metadata.get("definitions")
    if not isinstance(definitions, dict):
        return []

    raw_subgraphs = definitions.get("subgraphs")
    if not raw_subgraphs:
        return []

    # Accept both dict-of-subgraphs and list-of-subgraphs shapes.
    if isinstance(raw_subgraphs, dict):
        subgraph_items: list[dict[str, Any]] = [
            item for item in raw_subgraphs.values() if isinstance(item, dict)
        ]
    elif isinstance(raw_subgraphs, list):
        subgraph_items = [
            item for item in raw_subgraphs if isinstance(item, dict)
        ]
    else:
        return []

    groups: list[dict[str, Any]] = []

    for i, subgraph in enumerate(subgraph_items):
        # ── Identify subgraph name (title) ───────────────────────────
        # Subgraph raw dict has "name" (the raw ID string like "VHS_VideoCombine")
        # and optionally a slug.  We use the name field for title.
        title = str(subgraph.get("name") or subgraph.get("id") or f"subgraph_{i}")

        # ── Gather inner nodes and their vibecomfy_uid ───────────────
        inner_nodes = subgraph.get("nodes")
        if not isinstance(inner_nodes, list):
            logger.debug(
                "build_subgraph_groups: subgraph %r has no nodes list; skipping",
                title,
            )
            continue

        # Collect all uids present in the flat graph that belong to this subgraph.
        inner_uids: list[str] = []
        total_inner = len(inner_nodes)
        for inner_node in inner_nodes:
            if not isinstance(inner_node, dict):
                continue
            props = inner_node.get("properties")
            if isinstance(props, dict):
                vibecomfy_uid = props.get("vibecomfy_uid")
                if isinstance(vibecomfy_uid, str) and vibecomfy_uid:
                    inner_uids.append(vibecomfy_uid)

        matched = len(inner_uids)

        if matched == 0:
            logger.debug(
                "build_subgraph_groups: subgraph %r matched 0/%d inner nodes — skipping",
                title,
                total_inner,
            )
            continue

        if 0 < matched < total_inner:
            logger.debug(
                "build_subgraph_groups: subgraph %s matched %d/%d inner nodes — box encloses subset",
                title,
                matched,
                total_inner,
            )

        # ── Compute bounding box from matched inner uids ─────────────
        # Collect coords of matched nodes.
        min_x: float | None = None
        min_y: float | None = None
        max_x: float | None = None
        max_y: float | None = None

        for uid in inner_uids:
            pos_entry = positions.get(uid)
            if pos_entry is None:
                continue
            pos = pos_entry.get("pos")
            if not pos or len(pos) < 2:
                continue
            sz = sizes.get(uid, (320, 30))
            px = float(pos[0])
            py = float(pos[1])
            pw = float(sz[0])
            ph = float(sz[1])

            if min_x is None or px < min_x:
                min_x = px
            if min_y is None or py < min_y:
                min_y = py
            if max_x is None or px + pw > max_x:
                max_x = px + pw
            if max_y is None or py + ph > max_y:
                max_y = py + ph

        if min_x is None:
            # All inner uids had no position — skip.
            logger.debug(
                "build_subgraph_groups: subgraph %r matched %d inner uids but none have positions; skipping",
                title,
                matched,
            )
            continue

        # Apply padding.
        pad = float(_GROUP_PAD_PX)
        gx = min_x - pad
        gy = min_y - pad
        gw = (max_x - min_x) + 2 * pad
        gh = (max_y - min_y) + 2 * pad

        # Canonicalize bounding values.
        gx = _canonicalize_coord(gx)
        gy = _canonicalize_coord(gy)
        gw = _canonicalize_coord(gw)
        gh = _canonicalize_coord(gh)

        color = _role_color_for_subgraph(title)

        groups.append(
            {
                "title": title,
                "bounding": [gx, gy, gw, gh],
                "color": color,
            }
        )

    return groups
