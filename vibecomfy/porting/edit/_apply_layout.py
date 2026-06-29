from __future__ import annotations

from typing import Any, Mapping

from ._apply_common import _issue
from ._apply_types import ResolvedAddNodeSpec
from .ledger import EditLedger
from .ops import AnchorRef
from vibecomfy.porting.report import PortIssue


_NODE_H_GAP = 80.0
_NODE_V_GAP = 36.0
_GROUP_PAD = 24.0
_COLLISION_NUDGE_X = 24.0
_COLLISION_NUDGE_Y = 32.0
_MAX_COLLISION_NUDGES = 64


def _node_rect(node: Mapping[str, Any]) -> list[float]:
    pos = node.get("pos")
    size = node.get("size")
    x = float(pos[0]) if isinstance(pos, (list, tuple)) and len(pos) >= 2 else 0.0
    y = float(pos[1]) if isinstance(pos, (list, tuple)) and len(pos) >= 2 else 0.0
    width = float(size[0]) if isinstance(size, (list, tuple)) and len(size) >= 2 else 320.0
    height = float(size[1]) if isinstance(size, (list, tuple)) and len(size) >= 2 else 180.0
    return [x, y, width, height]


def _node_size(node: Mapping[str, Any]) -> tuple[float, float]:
    rect = _node_rect(node)
    return rect[2], rect[3]


def _rectangles_overlap(left: list[float], right: list[float]) -> bool:
    return not (
        left[0] + left[2] <= right[0]
        or right[0] + right[2] <= left[0]
        or left[1] + left[3] <= right[1]
        or right[1] + right[3] <= left[1]
    )


def _right_of_rect(rect: list[float], size: tuple[float, float]) -> tuple[float, float]:
    return rect[0] + rect[2] + _NODE_H_GAP, rect[1]


def _left_of_rect(rect: list[float], size: tuple[float, float]) -> tuple[float, float]:
    return rect[0] - size[0] - _NODE_H_GAP, rect[1]


def _between_rects(
    left: list[float],
    right: list[float],
    size: tuple[float, float],
) -> tuple[float, float]:
    gap_left = left[0] + left[2]
    gap_right = right[0]
    if gap_right > gap_left and gap_right - gap_left >= size[0]:
        x = gap_left + max(0.0, (gap_right - gap_left - size[0]) / 2)
        y = ((left[1] + right[1]) / 2)
    elif gap_right > gap_left:
        x = left[0]
        y = max(left[1] + left[3], right[1] + right[3]) + _NODE_V_GAP
    else:
        left_center = left[0] + left[2] / 2
        right_center = right[0] + right[2] / 2
        x = ((left_center + right_center) / 2) - size[0] / 2
        y = max(left[1] + left[3], right[1] + right[3]) + _NODE_V_GAP
    return x, y


def _round_pos(value: float) -> float:
    return round(value, 2)


def _group_bounding(scope_graph: Mapping[str, Any], group_index: int) -> list[float] | None:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list) or not (0 <= group_index < len(groups)):
        return None
    group = groups[group_index]
    if not isinstance(group, Mapping):
        return None
    bounding = group.get("bounding")
    if not isinstance(bounding, (list, tuple)) or len(bounding) != 4:
        return None
    return [float(bounding[0]), float(bounding[1]), float(bounding[2]), float(bounding[3])]


def _group_index_for_rect(scope_graph: Mapping[str, Any], rect: list[float]) -> int | None:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list):
        return None
    center_x = rect[0] + rect[2] / 2
    center_y = rect[1] + rect[3] / 2
    best: tuple[float, int] | None = None
    for index, group in enumerate(groups):
        bbox = _group_bounding(scope_graph, index)
        if bbox is None:
            continue
        if bbox[0] <= center_x <= bbox[0] + bbox[2] and bbox[1] <= center_y <= bbox[1] + bbox[3]:
            area = bbox[2] * bbox[3]
            if best is None or area < best[0]:
                best = (area, index)
    return best[1] if best is not None else None


def _group_index_for_node(scope_graph: Mapping[str, Any], node: Mapping[str, Any]) -> int | None:
    return _group_index_for_rect(scope_graph, _node_rect(node))


def _group_index_by_title(scope_graph: Mapping[str, Any], title: str) -> int | None:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list):
        return None
    for index, group in enumerate(groups):
        if isinstance(group, Mapping) and group.get("title") == title:
            return index
    return None


def _rect_overlaps_any_node(scope_graph: Mapping[str, Any], rect: list[float]) -> bool:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return False
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        if _rectangles_overlap(rect, _node_rect(node)):
            return True
    return False


def _default_add_node_position(
    scope_graph: Mapping[str, Any],
    size: tuple[float, float],
) -> tuple[float, float]:
    max_right = 0.0
    min_top = 0.0
    seen = False
    nodes = scope_graph.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            x, y, width, _ = _node_rect(node)
            max_right = max(max_right, x + width)
            min_top = y if not seen else min(min_top, y)
            seen = True
    if seen:
        return max_right + _NODE_H_GAP, min_top
    return 0.0, 0.0


def _clamp_position_to_group(
    scope_graph: Mapping[str, Any],
    group_index: int,
    x: float,
    y: float,
    size: tuple[float, float],
) -> tuple[float, float]:
    group = _group_bounding(scope_graph, group_index)
    if group is None:
        return x, y
    min_x = group[0] + _GROUP_PAD
    min_y = group[1] + _GROUP_PAD
    return max(min_x, x), max(min_y, y)


def _nudge_to_open_slot(
    scope_graph: Mapping[str, Any],
    pos: list[float],
    size: tuple[float, float],
    *,
    within_group: int | None,
) -> list[float]:
    x, y = pos
    for _ in range(_MAX_COLLISION_NUDGES):
        rect = [x, y, size[0], size[1]]
        if not _rect_overlaps_any_node(scope_graph, rect):
            return [_round_pos(x), _round_pos(y)]
        x += _COLLISION_NUDGE_X
        y += _COLLISION_NUDGE_Y
        if within_group is not None:
            x, y = _clamp_position_to_group(scope_graph, within_group, x, y, size)
    return [_round_pos(x), _round_pos(y)]


def _grow_group_to_fit(
    scope_graph: Mapping[str, Any],
    group_index: int,
    pos: list[float],
    size: tuple[float, float],
) -> bool:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list) or not (0 <= group_index < len(groups)):
        return False
    group = groups[group_index]
    if not isinstance(group, dict):
        return False
    bounding = group.get("bounding")
    if not isinstance(bounding, list) or len(bounding) != 4:
        return False
    min_x = float(bounding[0])
    min_y = float(bounding[1])
    width = float(bounding[2])
    height = float(bounding[3])
    needed_right = pos[0] + size[0] + _GROUP_PAD
    needed_bottom = pos[1] + size[1] + _GROUP_PAD
    right = min_x + width
    bottom = min_y + height
    grew = False
    if needed_right > right:
        bounding[2] = _round_pos(needed_right - min_x)
        grew = True
    if needed_bottom > bottom:
        bounding[3] = _round_pos(needed_bottom - min_y)
        grew = True
    return grew


def _anchor_position(
    scope_graph: Mapping[str, Any],
    anchor: AnchorRef,
    spec: ResolvedAddNodeSpec,
    size: tuple[float, float],
    fallback: tuple[float, float],
) -> tuple[float, float]:
    if anchor.relation == "between" and spec.anchor_between is not None:
        return _between_rects(_node_rect(spec.anchor_between[0].node), _node_rect(spec.anchor_between[1].node), size)
    if spec.anchor_near is not None:
        rect = _node_rect(spec.anchor_near.node)
        if anchor.relation == "below":
            return rect[0], rect[1] + rect[3] + _NODE_V_GAP
        if anchor.relation == "left_of":
            return _left_of_rect(rect, size)
        if anchor.relation == "right_of":
            return _right_of_rect(rect, size)
        return _right_of_rect(rect, size)
    if anchor.group_title is not None:
        group_index = _group_index_by_title(scope_graph, anchor.group_title)
        if group_index is not None:
            group = _group_bounding(scope_graph, group_index)
            if group is not None:
                return group[0] + _GROUP_PAD, group[1] + _GROUP_PAD
    return fallback


def _target_group_index(
    scope_graph: Mapping[str, Any],
    spec: ResolvedAddNodeSpec,
    size: tuple[float, float],
) -> tuple[int | None, list[PortIssue]]:
    if spec.anchor_group_index is not None:
        return spec.anchor_group_index, []
    if spec.anchor_near is not None:
        return _group_index_for_node(scope_graph, spec.anchor_near.node), []
    if spec.anchor_between is not None:
        downstream_ref = spec.anchor_between[1]
        upstream_ref = spec.anchor_between[0]
        downstream = _group_index_for_node(scope_graph, downstream_ref.node)
        upstream = _group_index_for_node(scope_graph, upstream_ref.node)
        if downstream is not None:
            return downstream, []
        if upstream is not None:
            return upstream, []
        # Neither has a group — leave ungrouped with a diagnostic
        downstream_uid = str(downstream_ref.node.get("properties", {}).get("vibecomfy_uid", downstream_ref.node.get("id", "?")))
        upstream_uid = str(upstream_ref.node.get("properties", {}).get("vibecomfy_uid", upstream_ref.node.get("id", "?")))
        return None, [
            _issue(
                "splice_anchor_no_group",
                f"Splice-placed node of type '{spec.op.class_type}': neither downstream "
                f"'{downstream_uid}' nor upstream '{upstream_uid}' belongs to a group; "
                f"leaving ungrouped.",
                severity="info",
                detail={
                    "class_type": spec.op.class_type,
                    "downstream_uid": downstream_uid,
                    "upstream_uid": upstream_uid,
                },
            )
        ]
    if spec.resolved_inputs:
        primary = next(iter(sorted(spec.resolved_inputs.items())))[1]
        return _group_index_for_node(scope_graph, primary.node), []
    pos = _default_add_node_position(scope_graph, size)
    return _group_index_for_rect(scope_graph, [pos[0], pos[1], size[0], size[1]]), []


def _place_add_node(
    ledger: EditLedger,
    spec: ResolvedAddNodeSpec,
    size: tuple[float, float],
) -> tuple[list[float], int | None, bool, list[PortIssue]]:
    scope_graph = spec.scope.graph
    desired_x, desired_y = _default_add_node_position(scope_graph, size)
    target_group_index, group_issues = _target_group_index(scope_graph, spec, size)
    if spec.op.anchor is not None:
        desired_x, desired_y = _anchor_position(scope_graph, spec.op.anchor, spec, size, (desired_x, desired_y))
    elif spec.resolved_inputs:
        primary = next(iter(sorted(spec.resolved_inputs.items())))[1]
        desired_x, desired_y = _right_of_rect(_node_rect(primary.node), size)
    if target_group_index is not None:
        desired_x, desired_y = _clamp_position_to_group(scope_graph, target_group_index, desired_x, desired_y, size)
    pos = _nudge_to_open_slot(scope_graph, [desired_x, desired_y], size, within_group=target_group_index)
    grew_group = False
    if target_group_index is not None:
        grew_group = _grow_group_to_fit(scope_graph, target_group_index, pos, size)
    return pos, target_group_index, grew_group, group_issues


def _next_node_order(scope_graph: Mapping[str, Any]) -> int:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return 0
    max_order = -1
    for node in nodes:
        if isinstance(node, Mapping) and isinstance(node.get("order"), int):
            max_order = max(max_order, int(node["order"]))
    return max_order + 1
