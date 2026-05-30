"""Layout vector helpers — capture and diff position/size snapshots of UI JSON graphs.

Both functions are stdlib-only and operate on raw litegraph UI JSON dicts.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class LayoutDriftReport:
    """Summary of positional drift between two layout snapshots."""

    max_pos_delta: float
    max_size_delta: float
    unmatched_keys: list[str]
    per_key_diff: dict[str, dict[str, Any]]


def layout_vector(
    ui_json: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract a position/size snapshot from a litegraph UI JSON dict.

    Returns a mapping ``{key: {"pos": [...], "size": [...], "group": str|None,
    "mode": int, "key_kind": str}}`` keyed by the node's canonical identity:

    1. ``properties["vibecomfy_uid"]`` if present and non-empty  (``key_kind="uid"``)
    2. ``properties["vibecomfy_id"]`` if present and non-empty   (``key_kind="vid"``)
    3. ``str(node["id"])``                                        (``key_kind="int_id"``)

    ``group`` is the title of the first group whose bounding box contains the node
    centroid, or ``None`` if no group claims the node.  ``mode`` is the litegraph
    node mode integer (0 = active, 2 = bypassed, 4 = muted).
    """
    nodes: list[dict[str, Any]] = ui_json.get("nodes", [])
    groups: list[dict[str, Any]] = ui_json.get("groups", [])

    result: dict[str, dict[str, Any]] = {}
    for node in nodes:
        props = node.get("properties", {})

        uid = props.get("vibecomfy_uid")
        if uid:
            key = uid
            kind = "uid"
        else:
            vid = props.get("vibecomfy_id")
            if vid:
                key = vid
                kind = "vid"
            else:
                key = str(node.get("id", ""))
                kind = "int_id"

        raw_pos = node.get("pos", [0, 0])
        raw_size = node.get("size", [0, 0])
        pos = [float(raw_pos[0]), float(raw_pos[1])] if len(raw_pos) >= 2 else [0.0, 0.0]
        size = [float(raw_size[0]), float(raw_size[1])] if len(raw_size) >= 2 else [0.0, 0.0]

        cx = pos[0] + size[0] / 2
        cy = pos[1] + size[1] / 2
        group = _find_group(cx, cy, groups)

        result[key] = {
            "pos": pos,
            "size": size,
            "group": group,
            "mode": int(node.get("mode", 0)),
            "key_kind": kind,
        }
    return result


def layout_drift(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
) -> LayoutDriftReport:
    """Compute positional drift between two layout vectors.

    Compares keys present in both snapshots.  Keys present in only one snapshot
    are collected as ``unmatched_keys``.  ``max_pos_delta`` and ``max_size_delta``
    are the largest Euclidean distances observed across matched keys.
    """
    matched = set(before) & set(after)
    unmatched = sorted((set(before) | set(after)) - matched)

    max_pos = 0.0
    max_size = 0.0
    per_key: dict[str, dict[str, Any]] = {}

    for key in matched:
        b = before[key]
        a = after[key]

        bp, ap = b["pos"], a["pos"]
        bs, as_ = b["size"], a["size"]

        pos_delta = math.sqrt((ap[0] - bp[0]) ** 2 + (ap[1] - bp[1]) ** 2)
        size_delta = math.sqrt((as_[0] - bs[0]) ** 2 + (as_[1] - bs[1]) ** 2)

        if pos_delta > max_pos:
            max_pos = pos_delta
        if size_delta > max_size:
            max_size = size_delta

        if pos_delta > 0 or size_delta > 0 or b.get("group") != a.get("group") or b.get("mode") != a.get("mode"):
            per_key[key] = {
                "pos_delta": pos_delta,
                "size_delta": size_delta,
                "before": b,
                "after": a,
            }

    return LayoutDriftReport(
        max_pos_delta=max_pos,
        max_size_delta=max_size,
        unmatched_keys=unmatched,
        per_key_diff=per_key,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_group(cx: float, cy: float, groups: list[dict[str, Any]]) -> str | None:
    """Return the title of the first group whose bounding box contains (cx, cy)."""
    for g in groups:
        b = g.get("bounding")
        if not b or len(b) < 4:
            continue
        x, y, w, h = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        if x <= cx <= x + w and y <= cy <= y + h:
            return g.get("title")
    return None
