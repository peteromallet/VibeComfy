"""Compact deterministic layout evidence for executor classification."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from vibecomfy.porting.reorganise.assess import (
    ISSUE_BACKWARD_EDGE_RATIO_HIGH,
    ISSUE_GROUP_COHERENCE_LOW,
    ISSUE_HELPER_DISTANCE_WARNING,
    ISSUE_OVERLAPPING_NODES,
    ISSUE_SPACING_DENSITY_HIGH,
    ISSUE_WEAK_GROUP_SIGNAL,
    METRIC_BACKWARD_EDGE_RATIO,
    METRIC_GROUP_COHERENCE,
    METRIC_GROUP_SIGNAL_STRENGTH,
    METRIC_HELPER_DISTANCE_WARNING_COUNT,
    METRIC_OVERLAP_COUNT,
    METRIC_SPACING_DENSITY,
    assess_layout_facts,
)
from vibecomfy.porting.reorganise.orchestrate import assess_reorganise_workflow
from vibecomfy.porting.reorganise.plan_types import AssessmentReport

_CACHE_LIMIT = 128
_HINT_CACHE: dict[str, "ClassifyLayoutHint"] = {}
_HINT_CACHE_ORDER: list[str] = []

_REVIEW_HOSTILE_ISSUES = frozenset(
    {
        ISSUE_OVERLAPPING_NODES,
        ISSUE_BACKWARD_EDGE_RATIO_HIGH,
        ISSUE_SPACING_DENSITY_HIGH,
        ISSUE_WEAK_GROUP_SIGNAL,
        ISSUE_GROUP_COHERENCE_LOW,
        ISSUE_HELPER_DISTANCE_WARNING,
    }
)


@dataclass(frozen=True, slots=True)
class ClassifyLayoutHint:
    """Small layout assessment summary safe to include in classify context."""

    graph_hash: str
    verdict: str
    overlap_signal: str
    backward_edge_signal: str
    spacing_group_helper_signal: str
    review_hostile: bool

    def to_prompt_fields(self) -> dict[str, str | bool]:
        """Return only the compact fields that belong in the prompt."""

        return {
            "verdict": self.verdict,
            "overlap_signal": self.overlap_signal,
            "backward_edge_signal": self.backward_edge_signal,
            "spacing_group_helper_signal": self.spacing_group_helper_signal,
            "review_hostile": self.review_hostile,
        }


def layout_graph_hash(graph: Mapping[str, Any]) -> str:
    """Return the deterministic full-graph hash used for layout hint caching."""

    raw = json.dumps(
        _jsonish(graph),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_classify_layout_hint(graph: Mapping[str, Any] | None) -> ClassifyLayoutHint | None:
    """Assess *graph* and return compact layout evidence for classification.

    The assessment is best-effort and keyed by the full graph hash because
    layout evidence depends on furniture coordinates as well as topology.
    Invalid or unsupported graph payloads simply produce no hint.
    """

    if not isinstance(graph, Mapping) or not graph:
        return None

    graph_hash = layout_graph_hash(graph)
    cached = _HINT_CACHE.get(graph_hash)
    if cached is not None:
        return cached

    try:
        result = assess_reorganise_workflow(graph)
        assessment = assess_layout_facts(result.facts)
    except Exception:
        return None

    hint = _hint_from_assessment(graph_hash, assessment)
    _cache_hint(hint)
    return hint


def _hint_from_assessment(graph_hash: str, assessment: AssessmentReport) -> ClassifyLayoutHint:
    metrics = {metric.name: metric.value for metric in assessment.metrics}
    issues = {issue.code: issue for issue in assessment.issues}
    issue_codes = frozenset(issues)

    overlap_count = _number(metrics.get(METRIC_OVERLAP_COUNT))
    overlap_signal = f"count={_compact_number(overlap_count)}" if overlap_count > 0 else "none"

    backward_ratio = _number(metrics.get(METRIC_BACKWARD_EDGE_RATIO))
    backward_edge_signal = (
        f"high_ratio={_compact_number(backward_ratio)}"
        if ISSUE_BACKWARD_EDGE_RATIO_HIGH in issue_codes
        else f"ratio={_compact_number(backward_ratio)}"
    )

    spacing_signal = _spacing_signal(metrics, issue_codes)
    group_signal = _group_signal(metrics, issue_codes)
    helper_signal = _helper_signal(metrics, issue_codes)
    review_hostile = assessment.verdict != "ok" and bool(issue_codes & _REVIEW_HOSTILE_ISSUES)

    return ClassifyLayoutHint(
        graph_hash=graph_hash,
        verdict=str(assessment.verdict),
        overlap_signal=overlap_signal,
        backward_edge_signal=backward_edge_signal,
        spacing_group_helper_signal=(
            f"spacing={spacing_signal},group={group_signal},helper={helper_signal}"
        ),
        review_hostile=review_hostile,
    )


def _spacing_signal(metrics: Mapping[str, Any], issue_codes: frozenset[str]) -> str:
    density = _number(metrics.get(METRIC_SPACING_DENSITY))
    if ISSUE_SPACING_DENSITY_HIGH in issue_codes:
        return f"high_density:{_compact_number(density)}"
    return f"ok:{_compact_number(density)}"


def _group_signal(metrics: Mapping[str, Any], issue_codes: frozenset[str]) -> str:
    coverage = _number(metrics.get(METRIC_GROUP_SIGNAL_STRENGTH))
    coherence = _number(metrics.get(METRIC_GROUP_COHERENCE))
    if ISSUE_WEAK_GROUP_SIGNAL in issue_codes:
        return f"weak:{_compact_number(coverage)}"
    if ISSUE_GROUP_COHERENCE_LOW in issue_codes:
        return f"low_coherence:{_compact_number(coherence)}"
    return f"ok:{_compact_number(coverage)}/{_compact_number(coherence)}"


def _helper_signal(metrics: Mapping[str, Any], issue_codes: frozenset[str]) -> str:
    count = _number(metrics.get(METRIC_HELPER_DISTANCE_WARNING_COUNT))
    if ISSUE_HELPER_DISTANCE_WARNING in issue_codes:
        return f"far:{_compact_number(count)}"
    return "ok"


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _compact_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


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


def _cache_hint(hint: ClassifyLayoutHint) -> None:
    _HINT_CACHE[hint.graph_hash] = hint
    _HINT_CACHE_ORDER.append(hint.graph_hash)
    while len(_HINT_CACHE_ORDER) > _CACHE_LIMIT:
        evicted = _HINT_CACHE_ORDER.pop(0)
        _HINT_CACHE.pop(evicted, None)


__all__ = [
    "ClassifyLayoutHint",
    "build_classify_layout_hint",
    "layout_graph_hash",
]
