from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.live_agentic_harness.scenario_manifest import (
    DEFAULT_MANIFEST_PATH,
    DEFAULT_SCENARIOS_DIR,
    ScenarioManifestError,
    discover_manifest_scenarios,
    sha256_file,
    write_manifest,
)
from tests.live_agentic_harness.runner import run_tag


CORRECTED_EDITS = {
    "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
    "video-image-to-video-conversion-with-moonvalley-d7853c",
    "multi-3d-preview-and-image-output-workflow-d93baf",
}


def _scenario(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_authoritative_manifest_selects_and_hashes_exactly_100_scenarios() -> None:
    paths = discover_manifest_scenarios()
    manifest = json.loads(DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest["entries"]

    assert len(paths) == manifest["scenario_count"] == len(entries) == 100
    assert len({entry["id"] for entry in entries}) == 100
    assert len({entry["path"] for entry in entries}) == 100
    assert all(entry["id"] == Path(entry["path"]).stem for entry in entries)
    assert all(entry["inclusion_status"] == "included" for entry in entries)
    assert {entry["revision_status"] for entry in entries} == {"matched", "revised"}
    assert {entry["id"] for entry in entries if entry["revision_status"] == "revised"} == CORRECTED_EDITS

    source_entries = [entry for entry in entries if entry["source_workflow"]]
    assert len(source_entries) == 98
    for entry in source_entries:
        source = entry["source_workflow"]
        source_path = Path(__file__).parents[1] / source["path"]
        assert source_path.is_file()
        assert source["sha256"] == sha256_file(source_path)


def test_d13_no_change_reconciliation_and_rubric_contract() -> None:
    scenarios = [_scenario(path) for path in discover_manifest_scenarios()]
    semantic = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "semantic_product"]
    controls = [s for s in scenarios if (s.get("classification") or {}).get("kind") == "health_control"]
    corrected = [s for s in scenarios if s["id"] in CORRECTED_EDITS]

    assert len(semantic) == 35
    assert len(controls) == 2
    assert len(corrected) == 3
    assert len(semantic) + len(controls) + len(corrected) == 40
    assert {s["_tags"]["query_type"] for s in semantic} == {"research", "explain", "diagnose"}
    assert all(s["assessment"]["expect_graph_changed"] is False for s in semantic + controls)
    assert all(s["classification"]["excluded_from_semantic_product_rates"] is True for s in controls)
    assert all(s["assessment"]["expect_graph_changed"] is True and s["apply"] is True for s in corrected)

    for scenario in semantic:
        rubric = scenario["answer_rubric"]
        assert rubric["judge"] == "semantic_answer"
        assert rubric["workflow_path"] == scenario["workflow_path"]
        assert rubric["required_node_evidence"]
        assert len(rubric["expected_criteria"]) >= 4
        assert "grounded" in rubric["pass_condition"]
        assert len(rubric["fail_conditions"]) == 5

    desired_edits = [s for s in scenarios if s.get("desired")]
    assert desired_edits
    for scenario in desired_edits:
        assessment = scenario["assessment"]
        # A desired edit is an active acceptance rubric: it must expect a graph
        # change and must never be configured so a refusal can skip the judge.
        assert assessment["expect_graph_changed"] is True, scenario["id"]
        # skip_intent_judge would let an allowlisted refusal bypass ALL judging
        # (both the edit-intent judge and the grounded-refusal gate) — invalid.
        assert assessment.get("skip_intent_judge") is not True, (
            f"{scenario['id']}: skip_intent_judge would let a refusal skip the judge"
        )


def test_runner_rejects_unmanifested_descriptor_before_execution(tmp_path: Path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "one.json").write_text(
        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
    )
    write_manifest(scenarios_dir)
    (scenarios_dir / "stray.json").write_text(
        json.dumps({"id": "stray", "query": "stray"}), encoding="utf-8"
    )
    with pytest.raises(ScenarioManifestError, match="unmanifested"):
        run_tag("stray-preflight", scenarios_dir=scenarios_dir, output_base=tmp_path / "out")


def test_manifest_discovery_rejects_changed_or_missing_descriptor(tmp_path: Path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    descriptor = scenarios_dir / "one.json"
    descriptor.write_text(json.dumps({"id": "one", "query": "one"}), encoding="utf-8")
    write_manifest(scenarios_dir)
    descriptor.write_text(json.dumps({"id": "one", "query": "changed"}), encoding="utf-8")
    with pytest.raises(ScenarioManifestError, match="hash mismatch"):
        discover_manifest_scenarios(scenarios_dir)

    descriptor.unlink()
    with pytest.raises(ScenarioManifestError, match="missing"):
        discover_manifest_scenarios(scenarios_dir)


def test_manifest_discovery_rejects_duplicate_id_and_path(tmp_path: Path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "one.json").write_text(
        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
    )
    manifest_path = write_manifest(scenarios_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["entries"].append(dict(manifest["entries"][0]))
    manifest["scenario_count"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ScenarioManifestError, match="duplicate scenario id"):
        discover_manifest_scenarios(scenarios_dir)


def test_manifest_discovery_rejects_duplicate_path_with_distinct_id(tmp_path: Path) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir()
    (scenarios_dir / "one.json").write_text(
        json.dumps({"id": "one", "query": "one"}), encoding="utf-8"
    )
    manifest_path = write_manifest(scenarios_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    duplicate = dict(manifest["entries"][0])
    duplicate["id"] = "two"
    manifest["entries"].append(duplicate)
    manifest["scenario_count"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ScenarioManifestError, match="duplicate scenario path"):
        discover_manifest_scenarios(scenarios_dir)
