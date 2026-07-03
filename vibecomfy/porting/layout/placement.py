"""Constrained new-node placement for the fresh-layout engine.

Phase 2 Step 4: :func:`place_constrained` returns ``(x, y)`` for a new node
anchored relative to an existing node, dodging pinned nodes via a spiral-ray
geometric search.  All returned coords pass through ``_canonicalize_coord``.
"""

from __future__ import annotations

import ast
import logging
import math
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping

from vibecomfy.porting.emit.ui import _canonicalize_coord

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


@dataclass(frozen=True, slots=True)
class BatchGraphRef:
    name: str
    slot_name: str | None = None


@dataclass(frozen=True, slots=True)
class BatchRewirePlan:
    source_name: str
    target_name: str
    target_field: str


@dataclass(frozen=True, slots=True)
class InferredAnchorHint:
    relation: Literal["right_of", "left_of", "between"]
    near_name: str | None = None
    between_names: tuple[str, str] | None = None


@dataclass(frozen=True, slots=True)
class BatchAddNodePlan:
    target_name: str
    class_type: str
    explicit_anchor: bool
    input_refs: tuple[BatchGraphRef, ...]
    statement_order: int


@dataclass(frozen=True, slots=True)
class BatchPlacementFacts:
    cluster_hints: Mapping[str, InferredAnchorHint]
    rewires_by_source: Mapping[str, tuple[BatchRewirePlan, ...]]


def build_batch_placement_facts(
    statements: tuple[Any, ...],
    *,
    graph_name_exists: Callable[[str], bool],
    estimate_add_node_width: Callable[[str], int],
) -> BatchPlacementFacts:
    """Infer batch-local placement facts from edit-surface statements."""
    add_plans: list[BatchAddNodePlan] = []
    rewires_by_source: dict[str, list[BatchRewirePlan]] = {}
    for order, item in enumerate(statements):
        statement = getattr(item, "node", item)
        add_plan = _extract_batch_add_node_plan(statement, statement_order=order)
        if add_plan is not None:
            add_plans.append(add_plan)
        rewire = _extract_batch_rewire_plan(statement)
        if rewire is not None:
            rewires_by_source.setdefault(rewire.source_name, []).append(rewire)
    return BatchPlacementFacts(
        cluster_hints=_infer_cluster_anchor_hints(
            add_plans,
            graph_name_exists=graph_name_exists,
            estimate_add_node_width=estimate_add_node_width,
        ),
        rewires_by_source={key: tuple(value) for key, value in rewires_by_source.items()},
    )


def infer_add_node_anchor_hint(
    *,
    target_name: str,
    resolved_inputs: Mapping[str, Any],
    placement_facts: BatchPlacementFacts,
    current_input_source_ref: Callable[[str, str], Any | None],
    target_has_any_link: Callable[[str], bool],
    uid_to_name: Mapping[str, str],
) -> InferredAnchorHint | None:
    """Infer the anchor hint for a newly added node in a batch."""
    splice_anchor = _infer_splice_anchor_hint(
        target_name=target_name,
        resolved_inputs=resolved_inputs,
        rewires=placement_facts.rewires_by_source.get(target_name, ()),
        current_input_source_ref=current_input_source_ref,
        target_has_any_link=target_has_any_link,
        uid_to_name=uid_to_name,
    )
    if splice_anchor is not None:
        return splice_anchor
    return placement_facts.cluster_hints.get(target_name)


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


def _infer_cluster_anchor_hints(
    add_plans: list[BatchAddNodePlan],
    *,
    graph_name_exists: Callable[[str], bool],
    estimate_add_node_width: Callable[[str], int],
) -> dict[str, InferredAnchorHint]:
    if len(add_plans) < 2:
        return {}
    add_by_name = {plan.target_name: plan for plan in add_plans}
    statement_order = {plan.target_name: plan.statement_order for plan in add_plans}
    widths = {plan.target_name: estimate_add_node_width(plan.class_type) for plan in add_plans}
    deps: dict[str, set[str]] = {plan.target_name: set() for plan in add_plans}
    external_refs: dict[str, list[BatchGraphRef]] = {plan.target_name: [] for plan in add_plans}
    adjacency: dict[str, set[str]] = {plan.target_name: set() for plan in add_plans}
    for plan in add_plans:
        for ref in plan.input_refs:
            if ref.name in add_by_name:
                deps[plan.target_name].add(ref.name)
                adjacency[plan.target_name].add(ref.name)
                adjacency[ref.name].add(plan.target_name)
            elif graph_name_exists(ref.name):
                external_refs[plan.target_name].append(ref)

    hints: dict[str, InferredAnchorHint] = {}
    seen: set[str] = set()
    for plan in sorted(add_plans, key=lambda item: item.statement_order):
        if plan.target_name in seen:
            continue
        stack = [plan.target_name]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        seen.update(component)
        if len(component) < 2:
            continue
        ordered = _toposort_component(component, deps, statement_order)
        if not ordered:
            continue
        cluster_anchor_name = _first_external_anchor_name(ordered, external_refs)
        lane_weight: dict[str, int] = {}
        for index, name in enumerate(ordered):
            predecessors = [dep for dep in deps[name] if dep in component]
            if predecessors:
                predecessor = max(
                    predecessors,
                    key=lambda dep: (lane_weight.get(dep, 0) + widths.get(dep, 0), -statement_order[dep]),
                )
                lane_weight[name] = lane_weight.get(predecessor, 0) + widths.get(predecessor, 0)
                if not add_by_name[name].explicit_anchor:
                    hints[name] = InferredAnchorHint(relation="right_of", near_name=predecessor)
                continue
            lane_weight[name] = 0
            if add_by_name[name].explicit_anchor:
                continue
            if cluster_anchor_name is not None:
                hints[name] = InferredAnchorHint(relation="right_of", near_name=cluster_anchor_name)
            elif index > 0:
                hints[name] = InferredAnchorHint(relation="right_of", near_name=ordered[index - 1])
    return hints


def _toposort_component(
    component: set[str],
    deps: Mapping[str, set[str]],
    statement_order: Mapping[str, int],
) -> list[str]:
    """Topological sort using dependency counts and reverse edges.

    Builds in-degree counts and reverse adjacency once (O(V+E)), then
    processes a deterministically-sorted ready queue.  When a cycle is
    detected the partially-ordered prefix is preserved and the remainder
    is appended in deterministic ``statement_order`` order.
    """
    # ---- dependency counts + reverse edges (intra-component only) -----
    in_degree: dict[str, int] = {}
    reverse_edges: dict[str, list[str]] = {name: [] for name in component}
    for name in component:
        comp_deps = [d for d in deps.get(name, set()) if d in component]
        in_degree[name] = len(comp_deps)
        for dep in comp_deps:
            reverse_edges[dep].append(name)

    # ---- deterministic ready queue -----------------------------------
    _key = lambda n: statement_order[n]  # noqa: E731
    ready = sorted(
        [name for name, deg in in_degree.items() if deg == 0],
        key=_key,
    )

    ordered: list[str] = []
    while ready:
        current = ready.pop(0)
        ordered.append(current)
        # Only decrement the nodes that actually depend on *current*.
        for dependent in reverse_edges[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
                ready.sort(key=_key)

    # ---- cycle remainder: keep partial order, append remainder --------
    if len(ordered) != len(component):
        remainder = sorted(
            [name for name in component if name not in ordered],
            key=_key,
        )
        ordered.extend(remainder)

    return ordered


def _first_external_anchor_name(
    ordered: list[str],
    external_refs: Mapping[str, list[BatchGraphRef]],
) -> str | None:
    for name in ordered:
        refs = external_refs.get(name) or []
        if refs:
            return refs[0].name
    return None


def _infer_splice_anchor_hint(
    *,
    target_name: str,
    resolved_inputs: Mapping[str, Any],
    rewires: tuple[BatchRewirePlan, ...],
    current_input_source_ref: Callable[[str, str], Any | None],
    target_has_any_link: Callable[[str], bool],
    uid_to_name: Mapping[str, str],
) -> InferredAnchorHint | None:
    if not rewires:
        return None
    for rewire in rewires:
        current_source = current_input_source_ref(rewire.target_name, rewire.target_field)
        for source_ref in resolved_inputs.values():
            source_name = uid_to_name.get(source_ref.uid)
            if source_name and current_source is None and target_has_any_link(rewire.target_name):
                return InferredAnchorHint(
                    relation="between",
                    between_names=(source_name, rewire.target_name),
                )
            if current_source is None:
                continue
            if source_ref.scope_path != current_source.scope_path or source_ref.uid != current_source.uid:
                continue
            if not _source_slots_match(source_ref.output_slot, current_source.output_slot):
                continue
            return InferredAnchorHint(
                relation="between",
                between_names=(uid_to_name.get(current_source.uid, current_source.uid), rewire.target_name),
            )
        if not resolved_inputs and target_has_any_link(rewire.target_name):
            return InferredAnchorHint(relation="left_of", near_name=rewire.target_name)
    return None


def _source_slots_match(expected: str | int, actual: str | int) -> bool:
    return expected == actual or str(expected) == str(actual)


def _extract_batch_add_node_plan(
    statement: ast.stmt,
    *,
    statement_order: int,
) -> BatchAddNodePlan | None:
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return None
    target = statement.targets[0]
    value = statement.value
    if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
        return None
    func = value.func
    if not isinstance(func, ast.Name):
        return None
    input_refs: list[BatchGraphRef] = []
    explicit_anchor = False
    for keyword in value.keywords:
        if keyword.arg is None:
            continue
        if keyword.arg in {"near", "relation", "group"}:
            explicit_anchor = True
            continue
        ref = _graph_ref_from_expr(keyword.value)
        if ref is not None:
            input_refs.append(ref)
    return BatchAddNodePlan(
        target_name=target.id,
        class_type=func.id,
        explicit_anchor=explicit_anchor,
        input_refs=tuple(input_refs),
        statement_order=statement_order,
    )


def _extract_batch_rewire_plan(statement: ast.stmt) -> BatchRewirePlan | None:
    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
        return None
    target = statement.targets[0]
    value = statement.value
    if not isinstance(target, ast.Attribute) or not isinstance(target.value, ast.Name):
        return None
    ref = _graph_ref_from_expr(value)
    if ref is None:
        return None
    return BatchRewirePlan(
        source_name=ref.name,
        target_name=target.value.id,
        target_field=target.attr,
    )


def _graph_ref_from_expr(node: ast.expr) -> BatchGraphRef | None:
    if isinstance(node, ast.Name):
        return BatchGraphRef(name=node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return BatchGraphRef(name=node.value.id, slot_name=node.attr)
    return None
