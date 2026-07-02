from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any, Mapping, Sequence

from .diagnostics import ReorganiseDiagnostic
from .graph_facts import (
    GraphInventoryFacts,
    NodeFurnitureFact,
    ScopeTopologyFacts,
    TopologyEdgeFact,
    extract_graph_facts,
)
from .plan_types import AssessmentIssue, AssessmentMetric, AssessmentReport, CanonicalNodeRef
from .report import build_assessment_report

METRIC_OVERLAP_COUNT = "overlap_count"
METRIC_BACKWARD_EDGE_RATIO = "backward_edge_ratio"
METRIC_SPACING_DENSITY = "spacing_density"
METRIC_GROUP_SIGNAL_STRENGTH = "group_signal_strength"
METRIC_GROUP_COHERENCE = "group_coherence"
METRIC_HELPER_DISTANCE_WARNING_COUNT = "helper_distance_warning_count"

ISSUE_OVERLAPPING_NODES = "OVERLAPPING_NODES"
ISSUE_BACKWARD_EDGE_RATIO_HIGH = "BACKWARD_EDGE_RATIO_HIGH"
ISSUE_SPACING_DENSITY_HIGH = "SPACING_DENSITY_HIGH"
ISSUE_WEAK_GROUP_SIGNAL = "WEAK_GROUP_SIGNAL"
ISSUE_GROUP_COHERENCE_LOW = "GROUP_COHERENCE_LOW"
ISSUE_HELPER_DISTANCE_WARNING = "HELPER_DISTANCE_WARNING"

OVERLAP_COUNT_THRESHOLD = 0
BACKWARD_EDGE_RATIO_THRESHOLD = 0.15
BACKWARD_EDGE_X_TOLERANCE = 8.0
SPACING_DENSITY_HIGH_THRESHOLD = 0.72
GROUP_SIGNAL_NODE_THRESHOLD = 4
GROUP_SIGNAL_COVERAGE_THRESHOLD = 0.50
GROUP_COHERENCE_THRESHOLD = 0.65
GROUP_COHERENCE_CONTAINMENT_WEIGHT = 0.55
GROUP_COHERENCE_TOPOLOGY_WEIGHT = 0.35
GROUP_COHERENCE_LABEL_WEIGHT = 0.10
HELPER_DISTANCE_WARNING_THRESHOLD = 420.0

ASSESSMENT_METRIC_ORDER = (
    METRIC_OVERLAP_COUNT,
    METRIC_BACKWARD_EDGE_RATIO,
    METRIC_SPACING_DENSITY,
    METRIC_GROUP_SIGNAL_STRENGTH,
    METRIC_GROUP_COHERENCE,
    METRIC_HELPER_DISTANCE_WARNING_COUNT,
)
ASSESSMENT_ISSUE_ORDER = (
    ISSUE_OVERLAPPING_NODES,
    ISSUE_BACKWARD_EDGE_RATIO_HIGH,
    ISSUE_SPACING_DENSITY_HIGH,
    ISSUE_WEAK_GROUP_SIGNAL,
    ISSUE_GROUP_COHERENCE_LOW,
    ISSUE_HELPER_DISTANCE_WARNING,
)


@dataclass(frozen=True, slots=True)
class _Rect:
    ref: CanonicalNodeRef
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)


def assess_layout_facts(facts: GraphInventoryFacts) -> AssessmentReport:
    rects = _rects_by_ref(facts.node_furniture)
    helper_refs = {helper.ref for helper in facts.helper_nodes}
    primary_rects = {
        ref: rect
        for ref, rect in rects.items()
        if ref not in helper_refs
    }

    overlap_pairs = _overlap_pairs(primary_rects)
    backward_count, directed_edges = _backward_edge_counts(facts.scope_topologies, rects)
    backward_ratio = _ratio(backward_count, directed_edges)
    spacing_density = _spacing_density(primary_rects)
    group_signal_strength = _group_signal_strength(facts, primary_rects)
    group_coherence = _group_coherence(facts, rects)
    helper_distance_issues = _helper_distance_issues(facts, rects, helper_refs)

    metrics = (
        AssessmentMetric(
            name=METRIC_OVERLAP_COUNT,
            value=len(overlap_pairs),
            threshold=OVERLAP_COUNT_THRESHOLD,
        ),
        AssessmentMetric(
            name=METRIC_BACKWARD_EDGE_RATIO,
            value=round(backward_ratio, 4),
            threshold=BACKWARD_EDGE_RATIO_THRESHOLD,
        ),
        AssessmentMetric(
            name=METRIC_SPACING_DENSITY,
            value=round(spacing_density, 4),
            threshold=SPACING_DENSITY_HIGH_THRESHOLD,
        ),
        AssessmentMetric(
            name=METRIC_GROUP_SIGNAL_STRENGTH,
            value=round(group_signal_strength, 4),
            threshold=GROUP_SIGNAL_COVERAGE_THRESHOLD,
        ),
        AssessmentMetric(
            name=METRIC_GROUP_COHERENCE,
            value=round(group_coherence, 4),
            threshold=GROUP_COHERENCE_THRESHOLD,
        ),
        AssessmentMetric(
            name=METRIC_HELPER_DISTANCE_WARNING_COUNT,
            value=len(helper_distance_issues),
            threshold=0,
        ),
    )

    issues: list[AssessmentIssue] = []
    if overlap_pairs:
        issues.append(
            AssessmentIssue(
                code=ISSUE_OVERLAPPING_NODES,
                message="Observed node bounding boxes overlap.",
                refs=tuple(ref for pair in overlap_pairs for ref in pair),
                detail={
                    "count": len(overlap_pairs),
                    "pairs": [[left.to_json(), right.to_json()] for left, right in overlap_pairs],
                },
            )
        )
    if backward_ratio > BACKWARD_EDGE_RATIO_THRESHOLD:
        issues.append(
            AssessmentIssue(
                code=ISSUE_BACKWARD_EDGE_RATIO_HIGH,
                message="Rendered edge direction frequently moves backward on the x axis.",
                detail={
                    "backward_edges": backward_count,
                    "measured_edges": directed_edges,
                    "ratio": round(backward_ratio, 4),
                },
            )
        )
    if spacing_density > SPACING_DENSITY_HIGH_THRESHOLD:
        issues.append(
            AssessmentIssue(
                code=ISSUE_SPACING_DENSITY_HIGH,
                message="Node boxes occupy a dense bounding area with limited spacing.",
                detail={"density": round(spacing_density, 4)},
            )
        )
    if len(primary_rects) >= GROUP_SIGNAL_NODE_THRESHOLD and group_signal_strength < GROUP_SIGNAL_COVERAGE_THRESHOLD:
        issues.append(
            AssessmentIssue(
                code=ISSUE_WEAK_GROUP_SIGNAL,
                message="Existing group signal is missing or covers too few primary nodes.",
                detail={
                    "primary_node_count": len(primary_rects),
                    "coverage": round(group_signal_strength, 4),
                },
            )
        )
    if group_signal_strength > 0.0 and group_coherence < GROUP_COHERENCE_THRESHOLD:
        issues.append(
            AssessmentIssue(
                code=ISSUE_GROUP_COHERENCE_LOW,
                message="Existing groups have weak geometry or topology coherence.",
                detail={
                    "score": round(group_coherence, 4),
                    "containment_weight": GROUP_COHERENCE_CONTAINMENT_WEIGHT,
                    "topology_weight": GROUP_COHERENCE_TOPOLOGY_WEIGHT,
                    "label_weight": GROUP_COHERENCE_LABEL_WEIGHT,
                },
            )
        )
    issues.extend(helper_distance_issues)

    return build_assessment_report(
        metrics=metrics,
        issues=issues,
        diagnostics=facts.diagnostics,
        metric_order=ASSESSMENT_METRIC_ORDER,
        issue_order=ASSESSMENT_ISSUE_ORDER,
    )


def assess_layout_from_ui(
    ui_json: Mapping[str, Any],
    *,
    sidecar_envelope: Mapping[str, Any] | None = None,
) -> AssessmentReport:
    return assess_layout_facts(
        extract_graph_facts(ui_json, sidecar_envelope=sidecar_envelope)
    )


def _rects_by_ref(furniture: Sequence[NodeFurnitureFact]) -> dict[CanonicalNodeRef, _Rect]:
    rects: dict[CanonicalNodeRef, _Rect] = {}
    for fact in furniture:
        rect = _rect_from_furniture(fact)
        if rect is not None:
            rects[fact.ref] = rect
    return rects


def _rect_from_furniture(fact: NodeFurnitureFact) -> _Rect | None:
    pos = _number_pair(fact.pos)
    size = _number_pair(fact.size)
    if pos is None or size is None:
        return None
    width, height = size
    if width <= 0.0 or height <= 0.0:
        return None
    return _Rect(ref=fact.ref, x=pos[0], y=pos[1], width=width, height=height)


def _number_pair(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    first = _number(value[0])
    second = _number(value[1])
    if first is None or second is None:
        return None
    return first, second


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _overlap_pairs(rects: Mapping[CanonicalNodeRef, _Rect]) -> tuple[tuple[CanonicalNodeRef, CanonicalNodeRef], ...]:
    ordered = sorted(rects.values(), key=lambda rect: rect.ref.to_json())
    pairs: list[tuple[CanonicalNodeRef, CanonicalNodeRef]] = []
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            if left.x < right.right and left.right > right.x and left.y < right.bottom and left.bottom > right.y:
                pairs.append((left.ref, right.ref))
    return tuple(pairs)


def _backward_edge_counts(
    topologies: Sequence[ScopeTopologyFacts],
    rects: Mapping[CanonicalNodeRef, _Rect],
) -> tuple[int, int]:
    backward = 0
    measured = 0
    for topology in topologies:
        for edge in topology.effective_edges:
            source = rects.get(edge.source)
            target = rects.get(edge.target)
            if source is None or target is None:
                continue
            measured += 1
            if target.center[0] < source.center[0] - BACKWARD_EDGE_X_TOLERANCE:
                backward += 1
    return backward, measured


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _spacing_density(rects: Mapping[CanonicalNodeRef, _Rect]) -> float:
    if not rects:
        return 0.0
    left = min(rect.x for rect in rects.values())
    top = min(rect.y for rect in rects.values())
    right = max(rect.right for rect in rects.values())
    bottom = max(rect.bottom for rect in rects.values())
    bounding_area = max(0.0, right - left) * max(0.0, bottom - top)
    if bounding_area == 0.0:
        return 0.0
    return sum(rect.area for rect in rects.values()) / bounding_area


def _group_signal_strength(
    facts: GraphInventoryFacts,
    primary_rects: Mapping[CanonicalNodeRef, _Rect],
) -> float:
    if not primary_rects:
        return 0.0
    covered = _group_member_refs(facts) & set(primary_rects)
    return _ratio(len(covered), len(primary_rects))


def _group_coherence(
    facts: GraphInventoryFacts,
    rects: Mapping[CanonicalNodeRef, _Rect],
) -> float:
    scores: list[float] = []
    id_to_ref = _litegraph_id_to_ref(facts)
    adjacency = _effective_adjacency(facts.scope_topologies)
    for scope in facts.scope_furniture:
        for group in scope.groups:
            group_rect = _rect_from_group(scope.scope_path, group.index, group.bounding)
            member_refs = tuple(
                ref
                for raw_id in group.nodes
                if (ref := id_to_ref.get((scope.scope_path, str(raw_id)))) is not None
            )
            member_refs = tuple(ref for ref in member_refs if ref in rects)
            if not member_refs:
                continue
            containment = _ratio(
                sum(
                    1
                    for ref in member_refs
                    if group_rect is not None and _contains(group_rect, rects[ref])
                ),
                len(member_refs),
            )
            topology = _group_topology_coherence(member_refs, adjacency)
            label = 1.0 if group.title else 0.0
            scores.append(
                GROUP_COHERENCE_CONTAINMENT_WEIGHT * containment
                + GROUP_COHERENCE_TOPOLOGY_WEIGHT * topology
                + GROUP_COHERENCE_LABEL_WEIGHT * label
            )
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _rect_from_group(scope_path: str, index: int, bounding: Any) -> _Rect | None:
    pair = _number_quad(bounding)
    if pair is None:
        return None
    x, y, width, height = pair
    if width <= 0.0 or height <= 0.0:
        return None
    return _Rect(CanonicalNodeRef(scope_path, f"<group:{index}>"), x, y, width, height)


def _number_quad(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 4:
        return None
    numbers = tuple(_number(item) for item in value[:4])
    if any(item is None for item in numbers):
        return None
    return numbers  # type: ignore[return-value]


def _contains(container: _Rect, child: _Rect) -> bool:
    return (
        child.x >= container.x
        and child.y >= container.y
        and child.right <= container.right
        and child.bottom <= container.bottom
    )


def _group_member_refs(facts: GraphInventoryFacts) -> set[CanonicalNodeRef]:
    id_to_ref = _litegraph_id_to_ref(facts)
    refs: set[CanonicalNodeRef] = set()
    for scope in facts.scope_furniture:
        for group in scope.groups:
            for raw_id in group.nodes:
                ref = id_to_ref.get((scope.scope_path, str(raw_id)))
                if ref is not None:
                    refs.add(ref)
    return refs


def _litegraph_id_to_ref(facts: GraphInventoryFacts) -> dict[tuple[str, str], CanonicalNodeRef]:
    return {
        (fact.ref.scope_path, str(fact.litegraph_id)): fact.ref
        for fact in facts.canonical_refs
        if fact.litegraph_id is not None
    }


def _effective_adjacency(
    topologies: Sequence[ScopeTopologyFacts],
) -> dict[CanonicalNodeRef, set[CanonicalNodeRef]]:
    adjacency: dict[CanonicalNodeRef, set[CanonicalNodeRef]] = {}
    for topology in topologies:
        for edge in topology.effective_edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
            adjacency.setdefault(edge.target, set()).add(edge.source)
    return adjacency


def _group_topology_coherence(
    member_refs: Sequence[CanonicalNodeRef],
    adjacency: Mapping[CanonicalNodeRef, set[CanonicalNodeRef]],
) -> float:
    member_set = set(member_refs)
    incident = 0
    internal = 0
    seen: set[tuple[CanonicalNodeRef, CanonicalNodeRef]] = set()
    for ref in member_refs:
        for neighbor in adjacency.get(ref, set()):
            edge_key = tuple(sorted((ref, neighbor), key=lambda item: item.to_json()))
            if edge_key in seen:
                continue
            seen.add(edge_key)
            incident += 1
            if neighbor in member_set:
                internal += 1
    if incident == 0:
        return 1.0 if len(member_refs) == 1 else 0.0
    return _ratio(internal, incident)


def _helper_distance_issues(
    facts: GraphInventoryFacts,
    rects: Mapping[CanonicalNodeRef, _Rect],
    helper_refs: set[CanonicalNodeRef],
) -> tuple[AssessmentIssue, ...]:
    issues: list[AssessmentIssue] = []
    for helper_ref in sorted(helper_refs, key=lambda ref: ref.to_json()):
        helper_rect = rects.get(helper_ref)
        if helper_rect is None:
            continue
        neighbors = _helper_neighbor_refs(helper_ref, facts.scope_topologies, helper_refs)
        neighbor_rects = [rects[ref] for ref in neighbors if ref in rects]
        if not neighbor_rects:
            continue
        helper_center = helper_rect.center
        distance = min(_distance(helper_center, rect.center) for rect in neighbor_rects)
        if distance > HELPER_DISTANCE_WARNING_THRESHOLD:
            issues.append(
                AssessmentIssue(
                    code=ISSUE_HELPER_DISTANCE_WARNING,
                    message="Helper node is far from its connected layout context.",
                    refs=(helper_ref,),
                    detail={
                        "distance": round(distance, 2),
                        "threshold": HELPER_DISTANCE_WARNING_THRESHOLD,
                        "neighbor_refs": [rect.ref.to_json() for rect in neighbor_rects],
                    },
                )
            )
    return tuple(issues)


def _helper_neighbor_refs(
    helper_ref: CanonicalNodeRef,
    topologies: Sequence[ScopeTopologyFacts],
    helper_refs: set[CanonicalNodeRef],
) -> tuple[CanonicalNodeRef, ...]:
    refs: set[CanonicalNodeRef] = set()
    for topology in topologies:
        for edge in topology.raw_edges:
            _add_neighbor_from_edge(refs, edge, helper_ref, helper_refs)
    return tuple(sorted(refs, key=lambda ref: ref.to_json()))


def _add_neighbor_from_edge(
    refs: set[CanonicalNodeRef],
    edge: TopologyEdgeFact,
    helper_ref: CanonicalNodeRef,
    helper_refs: set[CanonicalNodeRef],
) -> None:
    if edge.source == helper_ref and edge.target not in helper_refs:
        refs.add(edge.target)
    if edge.target == helper_ref and edge.source not in helper_refs:
        refs.add(edge.source)


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


build_assessment = assess_layout_facts


__all__ = [
    "ASSESSMENT_ISSUE_ORDER",
    "ASSESSMENT_METRIC_ORDER",
    "BACKWARD_EDGE_RATIO_THRESHOLD",
    "BACKWARD_EDGE_X_TOLERANCE",
    "GROUP_COHERENCE_CONTAINMENT_WEIGHT",
    "GROUP_COHERENCE_LABEL_WEIGHT",
    "GROUP_COHERENCE_THRESHOLD",
    "GROUP_COHERENCE_TOPOLOGY_WEIGHT",
    "GROUP_SIGNAL_COVERAGE_THRESHOLD",
    "GROUP_SIGNAL_NODE_THRESHOLD",
    "HELPER_DISTANCE_WARNING_THRESHOLD",
    "ISSUE_BACKWARD_EDGE_RATIO_HIGH",
    "ISSUE_GROUP_COHERENCE_LOW",
    "ISSUE_HELPER_DISTANCE_WARNING",
    "ISSUE_OVERLAPPING_NODES",
    "ISSUE_SPACING_DENSITY_HIGH",
    "ISSUE_WEAK_GROUP_SIGNAL",
    "METRIC_BACKWARD_EDGE_RATIO",
    "METRIC_GROUP_COHERENCE",
    "METRIC_GROUP_SIGNAL_STRENGTH",
    "METRIC_HELPER_DISTANCE_WARNING_COUNT",
    "METRIC_OVERLAP_COUNT",
    "METRIC_SPACING_DENSITY",
    "OVERLAP_COUNT_THRESHOLD",
    "SPACING_DENSITY_HIGH_THRESHOLD",
    "assess_layout_facts",
    "assess_layout_from_ui",
    "build_assessment",
]
