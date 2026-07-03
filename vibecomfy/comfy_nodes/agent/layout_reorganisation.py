from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from vibecomfy.porting.reorganise.assess import (
    METRIC_BACKWARD_EDGE_RATIO,
    METRIC_HELPER_DISTANCE_WARNING_COUNT,
    METRIC_OVERLAP_COUNT,
    METRIC_SPACING_DENSITY,
    assess_layout_facts,
)
from vibecomfy.porting.reorganise.graph_facts import (
    GraphInventoryFacts,
    GroupFact,
    NodeFurnitureFact,
    ScopeTopologyFacts,
    extract_graph_facts,
)

REORGANISE_AUTO_ENV = "VIBECOMFY_REORGANISE_AUTO"

ReorganiseAutoMode = Literal["off", "suggest", "candidate"]
ReorganisationDecisionResult = Literal[
    "none",
    "offer_reorganisation",
    "prepare_candidate",
]

REORGANISE_AUTO_MODES: frozenset[str] = frozenset({"off", "suggest", "candidate"})
REORGANISATION_DECISION_RESULTS: frozenset[str] = frozenset(
    {"none", "offer_reorganisation", "prepare_candidate"}
)

_DEFAULT_MODE: ReorganiseAutoMode = "suggest"
_OVERLAP_REGRESSION_THRESHOLD = 0
_BACKWARD_RATIO_REGRESSION_THRESHOLD = 0.05
_SPACING_REGRESSION_THRESHOLD = 0.15
_MEANINGFUL_NODE_GROWTH_THRESHOLD = 3
_MEANINGFUL_LINK_CHANGE_THRESHOLD = 2


@dataclass(frozen=True, slots=True)
class ReorganiseAutoConfig:
    mode: ReorganiseAutoMode
    raw_value: str | None
    valid: bool = True
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": self.mode,
            "raw_value": self.raw_value,
            "valid": self.valid,
        }
        if self.error is not None:
            payload["error"] = self.error
        return payload


@dataclass(frozen=True, slots=True)
class PostEditLayoutFeatures:
    nodes_added: int
    nodes_removed: int
    rewired_links: int
    touched_groups: int
    helpers_added: int
    added_boxes_outside_groups: int
    overlap_delta: int
    backward_edge_ratio_delta: float
    spacing_density_delta: float
    helper_distance_warning_delta: int
    branches_added: int
    max_fanout_delta: int
    samplers_added: int
    output_paths_added: int
    output_nodes_added: int
    before_verdict: str
    after_verdict: str

    @property
    def node_delta(self) -> int:
        return self.nodes_added + self.nodes_removed

    @property
    def has_layout_regression(self) -> bool:
        return (
            self.overlap_delta > _OVERLAP_REGRESSION_THRESHOLD
            or self.backward_edge_ratio_delta > _BACKWARD_RATIO_REGRESSION_THRESHOLD
            or self.spacing_density_delta > _SPACING_REGRESSION_THRESHOLD
            or self.helper_distance_warning_delta > 0
        )

    @property
    def has_meaningful_growth(self) -> bool:
        return (
            self.nodes_added >= _MEANINGFUL_NODE_GROWTH_THRESHOLD
            or self.rewired_links >= _MEANINGFUL_LINK_CHANGE_THRESHOLD
            or self.branches_added > 0
            or self.max_fanout_delta > 0
            or self.samplers_added > 0
            or self.output_paths_added > 0
            or self.output_nodes_added > 0
        )

    @property
    def has_edit_magnitude(self) -> bool:
        return (
            self.node_delta > 0
            or self.rewired_links > 0
            or self.touched_groups > 0
            or self.helpers_added > 0
            or self.branches_added > 0
            or self.samplers_added > 0
            or self.output_paths_added > 0
            or self.output_nodes_added > 0
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "nodes_added": self.nodes_added,
            "nodes_removed": self.nodes_removed,
            "rewired_links": self.rewired_links,
            "touched_groups": self.touched_groups,
            "helpers_added": self.helpers_added,
            "added_boxes_outside_groups": self.added_boxes_outside_groups,
            "overlap_delta": self.overlap_delta,
            "backward_edge_ratio_delta": self.backward_edge_ratio_delta,
            "spacing_density_delta": self.spacing_density_delta,
            "helper_distance_warning_delta": self.helper_distance_warning_delta,
            "branches_added": self.branches_added,
            "max_fanout_delta": self.max_fanout_delta,
            "samplers_added": self.samplers_added,
            "output_paths_added": self.output_paths_added,
            "output_nodes_added": self.output_nodes_added,
            "before_verdict": self.before_verdict,
            "after_verdict": self.after_verdict,
        }


@dataclass(frozen=True, slots=True)
class PostEditReorganisationDecision:
    result: ReorganisationDecisionResult
    mode: ReorganiseAutoMode
    config: ReorganiseAutoConfig
    features: PostEditLayoutFeatures | None
    reason_codes: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "result": self.result,
            "mode": self.mode,
            "config": self.config.to_json(),
            "reason_codes": list(self.reason_codes),
        }
        if self.features is not None:
            payload["features"] = self.features.to_json()
        return payload


def read_reorganise_auto_config(
    env: Mapping[str, str] | None = None,
) -> ReorganiseAutoConfig:
    source = os.environ if env is None else env
    raw = source.get(REORGANISE_AUTO_ENV)
    if raw is None or not raw.strip():
        return ReorganiseAutoConfig(mode=_DEFAULT_MODE, raw_value=raw)

    normalized = raw.strip().casefold()
    if normalized in REORGANISE_AUTO_MODES:
        return ReorganiseAutoConfig(
            mode=normalized,  # type: ignore[arg-type]
            raw_value=raw,
        )

    return ReorganiseAutoConfig(
        mode="off",
        raw_value=raw,
        valid=False,
        error=(
            f"Invalid {REORGANISE_AUTO_ENV}={raw!r}; expected off, suggest, "
            "or candidate. Failing closed to off."
        ),
    )


def decide_post_edit_reorganisation(
    before_ui: Mapping[str, Any] | None,
    after_ui: Mapping[str, Any] | None,
    *,
    before_sidecar_envelope: Mapping[str, Any] | None = None,
    after_sidecar_envelope: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> PostEditReorganisationDecision:
    config = read_reorganise_auto_config(env)
    if config.mode == "off":
        return _decision(
            "none",
            config=config,
            features=None,
            reason_codes=_config_reason_codes(config) + ("mode_off",),
        )
    if not isinstance(before_ui, Mapping) or not isinstance(after_ui, Mapping):
        return _decision(
            "none",
            config=config,
            features=None,
            reason_codes=("invalid_graph_payload",),
        )

    try:
        before_facts = extract_graph_facts(
            before_ui,
            sidecar_envelope=before_sidecar_envelope,
        )
        after_facts = extract_graph_facts(
            after_ui,
            sidecar_envelope=after_sidecar_envelope,
        )
        before_assessment = assess_layout_facts(before_facts)
        after_assessment = assess_layout_facts(after_facts)
    except Exception:
        return _decision(
            "none",
            config=config,
            features=None,
            reason_codes=("layout_assessment_failed",),
        )

    features = _post_edit_layout_features(
        before_facts=before_facts,
        after_facts=after_facts,
        before_metrics={metric.name: metric.value for metric in before_assessment.metrics},
        after_metrics={metric.name: metric.value for metric in after_assessment.metrics},
        before_verdict=str(before_assessment.verdict),
        after_verdict=str(after_assessment.verdict),
    )
    reason_codes = _decision_reason_codes(features)
    if not reason_codes:
        return _decision(
            "none",
            config=config,
            features=features,
            reason_codes=("no_layout_reorganisation_signal",),
        )

    result: ReorganisationDecisionResult = (
        "prepare_candidate" if config.mode == "candidate" else "offer_reorganisation"
    )
    return _decision(result, config=config, features=features, reason_codes=reason_codes)


def _decision(
    result: ReorganisationDecisionResult,
    *,
    config: ReorganiseAutoConfig,
    features: PostEditLayoutFeatures | None,
    reason_codes: tuple[str, ...],
) -> PostEditReorganisationDecision:
    return PostEditReorganisationDecision(
        result=result,
        mode=config.mode,
        config=config,
        features=features,
        reason_codes=reason_codes,
    )


def _config_reason_codes(config: ReorganiseAutoConfig) -> tuple[str, ...]:
    return ("invalid_config",) if not config.valid else ()


def _post_edit_layout_features(
    *,
    before_facts: GraphInventoryFacts,
    after_facts: GraphInventoryFacts,
    before_metrics: Mapping[str, Any],
    after_metrics: Mapping[str, Any],
    before_verdict: str,
    after_verdict: str,
) -> PostEditLayoutFeatures:
    before_refs = _canonical_ref_set(before_facts)
    after_refs = _canonical_ref_set(after_facts)
    added_refs = after_refs - before_refs

    before_edges = _edge_signatures(before_facts.scope_topologies)
    after_edges = _edge_signatures(after_facts.scope_topologies)
    before_topology = _node_topology_summary(before_facts.scope_topologies)
    after_topology = _node_topology_summary(after_facts.scope_topologies)
    before_output_paths = _terminal_path_count(before_facts.scope_topologies)
    after_output_paths = _terminal_path_count(after_facts.scope_topologies)

    return PostEditLayoutFeatures(
        nodes_added=len(added_refs),
        nodes_removed=len(before_refs - after_refs),
        rewired_links=len(before_edges.symmetric_difference(after_edges)),
        touched_groups=_touched_group_count(before_facts, after_facts),
        helpers_added=len(_helper_ref_set(after_facts) - _helper_ref_set(before_facts)),
        added_boxes_outside_groups=_added_boxes_outside_groups(after_facts, added_refs),
        overlap_delta=_int_metric(after_metrics, METRIC_OVERLAP_COUNT)
        - _int_metric(before_metrics, METRIC_OVERLAP_COUNT),
        backward_edge_ratio_delta=round(
            _float_metric(after_metrics, METRIC_BACKWARD_EDGE_RATIO)
            - _float_metric(before_metrics, METRIC_BACKWARD_EDGE_RATIO),
            4,
        ),
        spacing_density_delta=round(
            _float_metric(after_metrics, METRIC_SPACING_DENSITY)
            - _float_metric(before_metrics, METRIC_SPACING_DENSITY),
            4,
        ),
        helper_distance_warning_delta=_int_metric(
            after_metrics,
            METRIC_HELPER_DISTANCE_WARNING_COUNT,
        )
        - _int_metric(before_metrics, METRIC_HELPER_DISTANCE_WARNING_COUNT),
        branches_added=max(
            0,
            _parallel_branch_count(after_facts.scope_topologies)
            - _parallel_branch_count(before_facts.scope_topologies),
        ),
        max_fanout_delta=max(0, after_topology["max_fanout"] - before_topology["max_fanout"]),
        samplers_added=max(0, after_topology["samplers"] - before_topology["samplers"]),
        output_paths_added=max(0, after_output_paths - before_output_paths),
        output_nodes_added=max(0, after_topology["outputs"] - before_topology["outputs"]),
        before_verdict=before_verdict,
        after_verdict=after_verdict,
    )


def _decision_reason_codes(features: PostEditLayoutFeatures) -> tuple[str, ...]:
    if not features.has_edit_magnitude and not features.has_layout_regression:
        return ()

    reasons: list[str] = []
    if features.has_layout_regression and features.has_edit_magnitude:
        reasons.append("layout_regressed_after_edit")
    if features.has_meaningful_growth:
        reasons.append("meaningful_graph_growth")
    if features.added_boxes_outside_groups > 0:
        reasons.append("candidate_boxes_outside_groups")
    if features.helpers_added > 0 and (
        features.helper_distance_warning_delta > 0 or features.rewired_links > 0
    ):
        reasons.append("helper_layout_attention")
    if features.branches_added > 0 or features.max_fanout_delta > 0:
        reasons.append("branch_path_added")
    if features.samplers_added > 0:
        reasons.append("sampler_path_added")
    if features.output_paths_added > 0 or features.output_nodes_added > 0:
        reasons.append("output_path_added")
    if (
        features.after_verdict != "ok"
        and features.nodes_added >= 2
        and "meaningful_graph_growth" not in reasons
    ):
        reasons.append("poor_layout_after_node_growth")

    return tuple(dict.fromkeys(reasons))


def _canonical_ref_set(facts: GraphInventoryFacts) -> set[tuple[str, str]]:
    return {(fact.ref.scope_path, fact.ref.uid) for fact in facts.canonical_refs}


def _helper_ref_set(facts: GraphInventoryFacts) -> set[tuple[str, str]]:
    return {(helper.ref.scope_path, helper.ref.uid) for helper in facts.helper_nodes}


def _edge_signatures(scopes: Sequence[ScopeTopologyFacts]) -> set[tuple[Any, ...]]:
    signatures: set[tuple[Any, ...]] = set()
    for scope in scopes:
        for edge in scope.raw_edges:
            signatures.add(
                (
                    edge.scope_path,
                    edge.source.scope_path,
                    edge.source.uid,
                    edge.target.scope_path,
                    edge.target.uid,
                    edge.source_slot,
                    edge.target_slot,
                    edge.socket_type,
                )
            )
    return signatures


def _node_topology_summary(scopes: Sequence[ScopeTopologyFacts]) -> dict[str, int]:
    samplers = 0
    outputs = 0
    max_fanout = 0
    for scope in scopes:
        for node in scope.node_topology:
            max_fanout = max(max_fanout, int(node.fan_out))
            lower_class = node.class_type.casefold()
            if node.terminal or "save" in lower_class or "preview" in lower_class:
                outputs += 1
            if "sampler" in lower_class:
                samplers += 1
    return {"samplers": samplers, "outputs": outputs, "max_fanout": max_fanout}


def _terminal_path_count(scopes: Sequence[ScopeTopologyFacts]) -> int:
    return sum(len(scope.terminal_paths) for scope in scopes)


def _parallel_branch_count(scopes: Sequence[ScopeTopologyFacts]) -> int:
    return sum(len(scope.parallel_branch_candidates) for scope in scopes)


def _touched_group_count(
    before_facts: GraphInventoryFacts,
    after_facts: GraphInventoryFacts,
) -> int:
    before = _group_signatures(before_facts)
    after = _group_signatures(after_facts)
    return len(before.keys() ^ after.keys()) + sum(
        1 for key in before.keys() & after.keys() if before[key] != after[key]
    )


def _group_signatures(facts: GraphInventoryFacts) -> dict[tuple[str, int], tuple[Any, ...]]:
    signatures: dict[tuple[str, int], tuple[Any, ...]] = {}
    for scope in facts.scope_furniture:
        for group in scope.groups:
            signatures[(group.scope_path, group.index)] = _group_signature(group)
    return signatures


def _group_signature(group: GroupFact) -> tuple[Any, ...]:
    return (
        group.title,
        tuple(_number_pair(group.bounding) or ()),
        tuple(sorted(str(node) for node in group.nodes)),
    )


def _added_boxes_outside_groups(
    facts: GraphInventoryFacts,
    added_refs: set[tuple[str, str]],
) -> int:
    if not added_refs:
        return 0
    groups_by_scope: dict[str, list[tuple[float, float, float, float]]] = {}
    for scope in facts.scope_furniture:
        for group in scope.groups:
            rect = _rect_tuple(group.bounding)
            if rect is not None:
                groups_by_scope.setdefault(group.scope_path, []).append(rect)
    if not any(groups_by_scope.values()):
        return 0

    outside = 0
    for furniture in facts.node_furniture:
        ref_key = (furniture.ref.scope_path, furniture.ref.uid)
        if ref_key not in added_refs:
            continue
        rect = _furniture_rect(furniture)
        if rect is None:
            continue
        groups = groups_by_scope.get(furniture.ref.scope_path, [])
        if groups and not any(_rect_center_inside(rect, group) for group in groups):
            outside += 1
    return outside


def _furniture_rect(furniture: NodeFurnitureFact) -> tuple[float, float, float, float] | None:
    pos = _number_pair(furniture.pos)
    size = _number_pair(furniture.size)
    if pos is None or size is None:
        return None
    return (pos[0], pos[1], size[0], size[1])


def _rect_tuple(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 4:
        return None
    numbers = [_number(item) for item in value[:4]]
    if any(item is None for item in numbers):
        return None
    return (numbers[0], numbers[1], numbers[2], numbers[3])  # type: ignore[return-value]


def _rect_center_inside(
    rect: tuple[float, float, float, float],
    group: tuple[float, float, float, float],
) -> bool:
    center_x = rect[0] + rect[2] / 2.0
    center_y = rect[1] + rect[3] / 2.0
    return (
        group[0] <= center_x <= group[0] + group[2]
        and group[1] <= center_y <= group[1] + group[3]
    )


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


def _int_metric(metrics: Mapping[str, Any], name: str) -> int:
    try:
        return int(metrics.get(name, 0))
    except (TypeError, ValueError):
        return 0


def _float_metric(metrics: Mapping[str, Any], name: str) -> float:
    try:
        return float(metrics.get(name, 0.0))
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "REORGANISATION_DECISION_RESULTS",
    "REORGANISE_AUTO_ENV",
    "REORGANISE_AUTO_MODES",
    "PostEditLayoutFeatures",
    "PostEditReorganisationDecision",
    "ReorganiseAutoConfig",
    "decide_post_edit_reorganisation",
    "read_reorganise_auto_config",
]
