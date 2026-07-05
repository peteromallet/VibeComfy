from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.porting.reorganise.assess import (
    METRIC_BACKWARD_EDGE_RATIO,
    METRIC_GROUP_COHERENCE,
    METRIC_GROUP_SIGNAL_STRENGTH,
    METRIC_HELPER_DISTANCE_WARNING_COUNT,
    METRIC_OVERLAP_COUNT,
    METRIC_SPACING_DENSITY,
)
from vibecomfy.porting.reorganise.orchestrate import (
    apply_layout_candidate_patch_to_ui,
    assess_reorganise_workflow,
    preview_reorganise_workflow,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "reorganise"


@dataclass(frozen=True, slots=True)
class GoldenThresholds:
    max_overlap_count: int
    max_backward_edge_ratio: float
    max_spacing_density: float
    min_group_signal_strength: float
    min_group_coherence: float
    max_helper_distance_warnings: int
    allowed_group_coherence_drop: float = 0.0
    expected_helper_count: int | None = None
    expected_min_scope_count: int = 1
    expected_min_component_count: int | None = None
    expected_min_patch_group_count: int = 1


# These thresholds intentionally live beside the fixture matrix instead of being
# derived from the implementation. When the compiler's layout tradeoffs change,
# reviewers can adjust one fixture's contract without weakening the whole gate.
GOLDEN_THRESHOLDS: dict[str, GoldenThresholds] = {
    "base_refiner_samplers.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.12,
        min_group_signal_strength=1.0,
        min_group_coherence=0.65,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=3,
    ),
    "collapsed_set_get.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.10,
        min_group_signal_strength=1.0,
        min_group_coherence=0.50,
        max_helper_distance_warnings=0,
        expected_helper_count=4,
        expected_min_patch_group_count=6,
    ),
    "coherent_grouped_pipeline.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.06,
        min_group_signal_strength=1.0,
        min_group_coherence=0.54,
        max_helper_distance_warnings=0,
        allowed_group_coherence_drop=0.21,
        expected_min_patch_group_count=5,
    ),
    "controlnet_depth_pose_branches.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.14,
        min_group_signal_strength=1.0,
        min_group_coherence=0.70,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=4,
    ),
    "disconnected_islands.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.05,
        min_group_signal_strength=1.0,
        min_group_coherence=0.80,
        max_helper_distance_warnings=0,
        expected_min_component_count=2,
        expected_min_patch_group_count=3,
    ),
    "incoherent_crossed_groups.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.05,
        min_group_signal_strength=1.0,
        min_group_coherence=0.70,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=3,
    ),
    "ipadapter_reference_chain.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.10,
        min_group_signal_strength=1.0,
        min_group_coherence=0.67,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=3,
    ),
    "muted_sampler_alternative.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.09,
        min_group_signal_strength=1.0,
        min_group_coherence=0.65,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=3,
    ),
    "parallel_sampler_variations.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.09,
        min_group_signal_strength=1.0,
        min_group_coherence=0.65,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=3,
    ),
    "prompt_pair.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.09,
        min_group_signal_strength=1.0,
        min_group_coherence=0.66,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=5,
    ),
    "section_notes.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.10,
        min_group_signal_strength=1.0,
        min_group_coherence=0.60,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=3,
    ),
    "set_get_reroute_helpers.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.20,
        min_group_signal_strength=1.0,
        min_group_coherence=1.0,
        max_helper_distance_warnings=0,
        expected_helper_count=3,
        expected_min_patch_group_count=1,
    ),
    "sidecar_push_adjacent.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.12,
        min_group_signal_strength=1.0,
        min_group_coherence=0.70,
        max_helper_distance_warnings=0,
        expected_helper_count=2,
        expected_min_patch_group_count=1,
    ),
    "shared_model_vae_fanout.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.07,
        min_group_signal_strength=1.0,
        min_group_coherence=0.65,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=4,
    ),
    "simple_text_to_image.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.08,
        min_group_signal_strength=1.0,
        min_group_coherence=0.66,
        max_helper_distance_warnings=0,
        expected_min_patch_group_count=5,
    ),
    "stacked_sidecars.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.25,
        min_group_signal_strength=1.0,
        min_group_coherence=1.0,
        max_helper_distance_warnings=0,
        expected_helper_count=4,
        expected_min_patch_group_count=1,
    ),
    "subgraph_scoped_pipeline.json": GoldenThresholds(
        max_overlap_count=0,
        max_backward_edge_ratio=0.0,
        max_spacing_density=0.05,
        min_group_signal_strength=1.0,
        min_group_coherence=0.59,
        max_helper_distance_warnings=0,
        allowed_group_coherence_drop=0.41,
        expected_min_scope_count=2,
        expected_min_patch_group_count=7,
    ),
}


def _fixture_paths() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("*.json"))


@pytest.mark.parametrize("fixture_path", _fixture_paths(), ids=lambda path: path.stem)
def test_reorganise_golden_matrix_preserves_topology_and_layout_contract(
    fixture_path: Path,
) -> None:
    thresholds = GOLDEN_THRESHOLDS[fixture_path.name]
    before = assess_reorganise_workflow(fixture_path)
    preview = preview_reorganise_workflow(fixture_path)

    assert preview.ok is True
    assert preview.validation_report is not None
    assert preview.validation_report.ok is True
    assert preview.candidate_patch is not None
    assert preview.apply_data.layout_only_structural_noop is True
    assert preview.apply_data.structural_hash_before == preview.apply_data.structural_hash_after

    applied = apply_layout_candidate_patch_to_ui(fixture_path, preview.candidate_patch)
    after = assess_reorganise_workflow(applied.ui_json)

    assert applied.layout_only_structural_noop is True
    assert applied.structural_hash_before == applied.structural_hash_after
    assert applied.structural_hash_after == preview.apply_data.structural_hash_after
    assert _topology_signature(after.facts) == _topology_signature(before.facts)

    before_metrics = _metrics(before.assessment)
    after_metrics = _metrics(after.assessment)
    _assert_metric_improvement_or_fixture_local_no_regression(
        fixture_path.name,
        before_metrics,
        after_metrics,
        thresholds,
    )
    _assert_after_thresholds(fixture_path.name, after_metrics, thresholds)
    _assert_helper_and_group_contracts(
        fixture_path.name,
        before=before,
        after=after,
        preview_candidate_patch=preview.candidate_patch,
        thresholds=thresholds,
    )
    _assert_idempotent_second_preview(
        fixture_path.name,
        applied.ui_json,
        after_metrics,
        thresholds,
    )


def test_reorganise_golden_thresholds_cover_every_fixture_explicitly() -> None:
    fixture_names = {path.name for path in _fixture_paths()}

    assert set(GOLDEN_THRESHOLDS) == fixture_names
    for fixture_name, thresholds in GOLDEN_THRESHOLDS.items():
        fixture = json.loads((FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
        metadata = fixture.get("extra", {}).get("vibecomfy", {})

        assert metadata.get("fixture") == fixture_name.removesuffix(".json")
        assert metadata.get("coverage")
        assert thresholds.max_overlap_count >= 0
        assert thresholds.max_backward_edge_ratio >= 0.0
        assert thresholds.max_spacing_density > 0.0
        assert thresholds.min_group_signal_strength >= 0.0
        assert thresholds.min_group_coherence >= 0.0
        assert thresholds.max_helper_distance_warnings >= 0


def _metrics(assessment: Any) -> dict[str, int | float]:
    return {metric.name: metric.value for metric in assessment.metrics}


def _assert_metric_improvement_or_fixture_local_no_regression(
    fixture_name: str,
    before: Mapping[str, int | float],
    after: Mapping[str, int | float],
    thresholds: GoldenThresholds,
) -> None:
    assert after[METRIC_OVERLAP_COUNT] <= before[METRIC_OVERLAP_COUNT], fixture_name
    assert after[METRIC_BACKWARD_EDGE_RATIO] <= before[METRIC_BACKWARD_EDGE_RATIO], fixture_name
    assert after[METRIC_SPACING_DENSITY] <= before[METRIC_SPACING_DENSITY], fixture_name
    assert (
        after[METRIC_HELPER_DISTANCE_WARNING_COUNT]
        <= before[METRIC_HELPER_DISTANCE_WARNING_COUNT]
    ), fixture_name
    assert after[METRIC_GROUP_SIGNAL_STRENGTH] >= before[METRIC_GROUP_SIGNAL_STRENGTH], fixture_name
    assert (
        after[METRIC_GROUP_COHERENCE] + thresholds.allowed_group_coherence_drop
        >= before[METRIC_GROUP_COHERENCE]
    ), fixture_name


def _assert_after_thresholds(
    fixture_name: str,
    metrics: Mapping[str, int | float],
    thresholds: GoldenThresholds,
) -> None:
    assert metrics[METRIC_OVERLAP_COUNT] <= thresholds.max_overlap_count, fixture_name
    assert metrics[METRIC_BACKWARD_EDGE_RATIO] <= thresholds.max_backward_edge_ratio, fixture_name
    assert metrics[METRIC_SPACING_DENSITY] <= thresholds.max_spacing_density, fixture_name
    assert metrics[METRIC_GROUP_SIGNAL_STRENGTH] >= thresholds.min_group_signal_strength, fixture_name
    assert metrics[METRIC_GROUP_COHERENCE] >= thresholds.min_group_coherence, fixture_name
    assert (
        metrics[METRIC_HELPER_DISTANCE_WARNING_COUNT]
        <= thresholds.max_helper_distance_warnings
    ), fixture_name


def _assert_helper_and_group_contracts(
    fixture_name: str,
    *,
    before: Any,
    after: Any,
    preview_candidate_patch: Mapping[str, Any],
    thresholds: GoldenThresholds,
) -> None:
    assert len(after.facts.helper_nodes) == len(before.facts.helper_nodes), fixture_name
    if thresholds.expected_helper_count is not None:
        assert len(after.facts.helper_nodes) == thresholds.expected_helper_count, fixture_name

    before_scope_count = len(before.facts.scope_topologies)
    after_scope_count = len(after.facts.scope_topologies)
    assert after_scope_count == before_scope_count, fixture_name
    assert after_scope_count >= thresholds.expected_min_scope_count, fixture_name

    if thresholds.expected_min_component_count is not None:
        root_scope = next(
            scope for scope in after.graph_summary.scopes if scope.scope_path == ""
        )
        assert root_scope.wcc_count >= thresholds.expected_min_component_count, fixture_name

    patch_groups = preview_candidate_patch.get("groups", [])
    assert len(patch_groups) >= thresholds.expected_min_patch_group_count, fixture_name
    assert _scope_group_count(after.facts) >= thresholds.expected_min_patch_group_count, fixture_name


def _assert_idempotent_second_preview(
    fixture_name: str,
    applied_ui: Mapping[str, Any],
    first_metrics: Mapping[str, int | float],
    thresholds: GoldenThresholds,
) -> None:
    second_preview = preview_reorganise_workflow(applied_ui)

    assert second_preview.ok is True
    assert second_preview.candidate_patch is not None
    assert second_preview.apply_data.layout_only_structural_noop is True
    assert (
        second_preview.apply_data.structural_hash_before
        == second_preview.apply_data.structural_hash_after
    )

    second_applied = apply_layout_candidate_patch_to_ui(
        applied_ui,
        second_preview.candidate_patch,
    )
    second_after = assess_reorganise_workflow(second_applied.ui_json)

    assert second_applied.layout_only_structural_noop is True
    assert second_applied.structural_hash_before == second_applied.structural_hash_after
    second_metrics = _metrics(second_after.assessment)
    _assert_metric_improvement_or_fixture_local_no_regression(
        fixture_name,
        first_metrics,
        second_metrics,
        thresholds,
    )
    _assert_after_thresholds(fixture_name, second_metrics, thresholds)


def _topology_signature(facts: Any) -> dict[str, Any]:
    return {
        "canonical_refs": sorted(
            (
                {
                    "ref": fact.ref.to_json(),
                    "class_type": fact.class_type,
                    "is_helper": fact.is_helper,
                }
                for fact in facts.canonical_refs
            ),
            key=_json_sort_key,
        ),
        "scope_topologies": sorted(
            (
                {
                    "scope_path": topology.scope_path,
                    "raw_edges": sorted(
                        (edge.to_json() for edge in topology.raw_edges),
                        key=_json_sort_key,
                    ),
                    "effective_edges": sorted(
                        (edge.to_json() for edge in topology.effective_edges),
                        key=_json_sort_key,
                    ),
                }
                for topology in facts.scope_topologies
            ),
            key=_json_sort_key,
        ),
    }


def _json_sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _scope_group_count(facts: Any) -> int:
    return sum(len(scope.groups) for scope in facts.scope_furniture)


# ---------------------------------------------------------------------------
# T13: Determinism and metric tests for golden fixtures
# ---------------------------------------------------------------------------


def test_reorganise_golden_repeated_compiles_produce_identical_coordinates() -> None:
    """For every golden fixture, two successive preview_reorganise_workflow
    calls must produce compile results with identical node and group
    coordinates.  This proves the placement path is deterministic across
    the full fixture matrix.

    Fixtures where preview.ok is False are skipped -- those are pre-existing
    layout-plan issues outside the scope of determinism testing."""
    for fixture_path in _fixture_paths():
        first = preview_reorganise_workflow(fixture_path)
        second = preview_reorganise_workflow(fixture_path)

        if not first.ok or not second.ok:
            continue  # pre-existing preview failure, not a determinism issue

        assert first.compile_result is not None
        assert second.compile_result is not None

        first_nodes = {
            layout.ref.uid: (layout.x, layout.y)
            for layout in first.compile_result.node_layouts
        }
        second_nodes = {
            layout.ref.uid: (layout.x, layout.y)
            for layout in second.compile_result.node_layouts
        }
        assert first_nodes == second_nodes, \
            f"fixture {fixture_path.name}: node coordinates differ between compiles"

        first_groups = {
            group.id: (group.x, group.y, group.width, group.height)
            for group in first.compile_result.group_layouts
        }
        second_groups = {
            group.id: (group.x, group.y, group.width, group.height)
            for group in second.compile_result.group_layouts
        }
        assert first_groups == second_groups, \
            f"fixture {fixture_path.name}: group coordinates differ between compiles"


def test_reorganise_golden_compile_validation_metrics_present_in_every_fixture() -> None:
    """Every golden fixture compile result must include the full set of
    validation metrics (node overlap count, group overlap count, whitespace
    ratio, baseline variance, detached group distance, helper sidecar
    overlap, note section mismatch, max primary per row, long edge distance,
    backward edge ratio, crossing proxy count, minimum gutter, helper
    distance max, and idempotence delta).

    Fixtures where preview.ok is False are skipped -- those are pre-existing
    layout-plan issues outside the scope of metric-presence testing."""
    required_metrics = frozenset({
        "compiled_node_overlap_count",
        "compiled_group_overlap_count",
        "compiled_internal_whitespace_ratio_max",
        "compiled_baseline_variance_max",
        "compiled_detached_group_distance_max",
        "compiled_helper_sidecar_overlap_count",
        "compiled_note_section_mismatch_count",
        "compiled_max_primary_nodes_per_row",
        "compiled_long_edge_distance_max",
        "compiled_backward_edge_ratio",
        "compiled_crossing_proxy_count",
        "compiled_minimum_gutter",
        "compiled_helper_distance_max",
        "compiled_idempotence_delta",
    })

    for fixture_path in _fixture_paths():
        preview = preview_reorganise_workflow(fixture_path)
        if not preview.ok:
            continue  # pre-existing preview failure

        assert preview.compile_result is not None
        metric_names = {
            metric.name for metric in preview.compile_result.metrics
        }
        missing = required_metrics - metric_names
        assert not missing, \
            f"fixture {fixture_path.name}: missing validation metrics: {sorted(missing)}"


def test_reorganise_golden_compile_layouts_match_patch_entries_positions() -> None:
    """For every fixture that compiles successfully, the node_layout positions
    in the compile result must match the 'pos' values in the corresponding
    candidate_patch entries.  This proves that validation metrics report on
    placed positions without mutating them.

    Only entries whose uid appears in both the compile node_layouts and the
    patch entries are checked.  Scoped fixtures may use qualified uid keys
    that differ from the compile ref uid, and those are skipped gracefully."""
    for fixture_path in _fixture_paths():
        preview = preview_reorganise_workflow(fixture_path)
        if not preview.ok:
            continue

        assert preview.compile_result is not None
        assert preview.candidate_patch is not None

        entries = preview.candidate_patch["entries"]
        compile_by_uid = {
            layout.ref.uid: layout
            for layout in preview.compile_result.node_layouts
        }

        # Only check the intersection -- scoped fixtures use qualified keys
        common_uids = set(compile_by_uid) & set(entries)
        if not common_uids:
            continue

        for uid in common_uids:
            layout = compile_by_uid[uid]
            patch_pos = entries[uid].get("pos")
            assert patch_pos is not None, \
                f"fixture {fixture_path.name}: {uid} has no pos in patch"
            assert (layout.x, layout.y) == (patch_pos[0], patch_pos[1]), (
                f"fixture {fixture_path.name}: {uid} coords differ: "
                f"layout ({layout.x},{layout.y}) != patch ({patch_pos[0]},{patch_pos[1]})"
            )
