from __future__ import annotations

import json
from pathlib import Path

from tests.structural_harness.actors_reorganise import (
    build_reorganise_large_messy_batch_evidence,
    build_reorganise_large_messy_ltx_workflow_evidence,
)
from vibecomfy.porting.reorganise import (
    apply_layout_candidate_patch_to_ui,
    assess_reorganise_workflow,
    preview_reorganise_workflow,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_agentic_reorganise_large_messy_ltx_workflow_evidence(tmp_path: Path) -> None:
    build_reorganise_large_messy_ltx_workflow_evidence(tmp_path)

    observation = json.loads((tmp_path / "layout_observation.json").read_text(encoding="utf-8"))
    before = observation["before_metrics"]
    after = observation["after_metrics"]

    assert observation["node_count"] == 119
    assert observation["structural_noop"] is True
    # structural hash now includes layout (group geometry + node furniture); a
    # layout-only change must move it while the topology-based noop stays True.
    assert observation["structural_hash_before"] != observation["structural_hash_after"]
    assert before["overlap_count"] > 0
    assert after["overlap_count"] == 0
    assert after["spacing_density"] < before["spacing_density"]
    assert after["group_signal_strength"] >= 1.0
    assert after["group_coherence"] >= 0.65
    assert observation["after_wall_aspect_ratio"] >= 1.6
    assert observation["after_bounds"]["width"] > observation["after_bounds"]["height"]
    assert observation["visual_verdict"] == "cleaner_layout"
    assert (tmp_path / "layout_before.png").is_file()
    assert (tmp_path / "layout_after.png").is_file()
    assert (tmp_path / "vision_prompt.txt").is_file()


def test_agentic_reorganise_large_messy_batch_evidence(tmp_path: Path) -> None:
    build_reorganise_large_messy_batch_evidence(tmp_path)

    observation = json.loads((tmp_path / "layout_observation.json").read_text(encoding="utf-8"))

    assert observation["case_count"] == 4
    assert observation["all_structural_noop"] is True
    assert observation["all_overlap_free"] is True
    assert observation["all_grouped"] is True
    assert observation["all_wall_aspect"] is True
    for case in observation["cases"]:
        assert case["structural_noop"] is True
        assert case["structural_hash_before"] != case["structural_hash_after"]
        assert case["before_metrics"]["overlap_count"] > 0
        assert case["after_metrics"]["overlap_count"] == 0
        assert case["after_metrics"]["group_signal_strength"] >= 1.0
        assert case["after_metrics"]["group_coherence"] >= 0.65
        assert case["after_wall_aspect_ratio"] >= 1.6
    assert (tmp_path / "layout_before_contact.png").is_file()
    assert (tmp_path / "layout_after_contact.png").is_file()
    assert (tmp_path / "vision_prompt.txt").is_file()


def test_reorganise_small_clean_workflows_use_node_only_layout() -> None:
    cases = (
        REPO_ROOT / "ready_templates/sources/official/audio/ace_step_1_5_t2a_song.json",
        REPO_ROOT / "tests/fixtures/agent_edit/hotshot_base_unsaved_workflow_4.json",
    )
    for path in cases:
        graph = json.loads(path.read_text(encoding="utf-8"))
        preview = preview_reorganise_workflow(graph)

        assert preview.ok is True
        assert preview.compile_result is not None
        assert preview.candidate_patch is not None
        assert len(preview.compile_result.group_layouts) == 0

        applied = apply_layout_candidate_patch_to_ui(graph, preview.candidate_patch)
        after = assess_reorganise_workflow(applied.ui_json)
        after_metrics = {metric.name: metric.value for metric in after.assessment.metrics}
        assert applied.layout_only_structural_noop is True
        # node-only layout still re-projects furniture, so the layout-inclusive
        # structural hash moves while the topology-based noop stays True.
        assert applied.structural_hash_before != applied.structural_hash_after
        assert after_metrics["overlap_count"] == 0


def test_reorganise_ungrouped_complex_workflow_generates_groups() -> None:
    cases = (
        REPO_ROOT
        / "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json",
        REPO_ROOT
        / "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json",
    )
    for path in cases:
        graph = json.loads(path.read_text(encoding="utf-8"))
        assert not graph.get("groups")
        assert len(graph.get("nodes", ())) >= 15

        preview = preview_reorganise_workflow(graph)

        assert preview.ok is True
        assert preview.compile_result is not None
        assert preview.candidate_patch is not None
        assert len(preview.compile_result.group_layouts) > 0

        applied = apply_layout_candidate_patch_to_ui(graph, preview.candidate_patch)
        after = assess_reorganise_workflow(applied.ui_json)
        after_metrics = {metric.name: metric.value for metric in after.assessment.metrics}
        assert applied.layout_only_structural_noop is True
        assert applied.structural_hash_before != applied.structural_hash_after
        assert after_metrics["overlap_count"] == 0
        assert after_metrics["group_signal_strength"] >= 1.0


def test_reorganise_small_subgraph_wrapper_avoids_generated_groups() -> None:
    graph = json.loads(
        (
            REPO_ROOT
            / "ready_templates/sources/official/edit/flux2_klein_4b_image_edit_base.json"
        ).read_text(encoding="utf-8")
    )
    preview = preview_reorganise_workflow(graph)

    assert preview.ok is True
    assert preview.compile_result is not None
    assert preview.candidate_patch is not None
    assert len(preview.compile_result.group_layouts) == 0

    applied = apply_layout_candidate_patch_to_ui(graph, preview.candidate_patch)
    after = assess_reorganise_workflow(applied.ui_json)
    after_metrics = {metric.name: metric.value for metric in after.assessment.metrics}
    assert applied.layout_only_structural_noop is True
    assert after_metrics["overlap_count"] == 0
