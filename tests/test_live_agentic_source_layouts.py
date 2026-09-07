from __future__ import annotations

from pathlib import Path

import pytest

from tests.live_agentic_harness.source_layouts import (
    has_layout_positions,
    is_litegraph_ui_graph,
    load_json,
    load_source_ui_graph,
    overlay_candidate_on_source,
    repo_root,
)


def _scenario_paths() -> list[Path]:
    return sorted((repo_root() / "tests" / "live_agentic_harness" / "scenarios").glob("*.json"))


def test_live_agentic_workflow_scenarios_have_source_ui_when_local_corpus_exists() -> None:
    root = repo_root()
    ignored_corpus = root / "external_workflows" / "corpus"
    # A two-file leftover directory is not the ignored full corpus this test needs.
    if not ignored_corpus.is_dir() or len(list(ignored_corpus.glob("*.json"))) < 50:
        pytest.skip("external workflow corpus is local ignored data")

    missing: list[str] = []
    for scenario_path in _scenario_paths():
        scenario = load_json(scenario_path)
        workflow_path = scenario.get("workflow_path")
        if not isinstance(workflow_path, str):
            continue
        resolved = load_source_ui_graph(workflow_path, root=root)
        if resolved is None:
            missing.append(f"{scenario_path.name}: {workflow_path}")
            continue
        source_path, source = resolved
        if not is_litegraph_ui_graph(source) or not has_layout_positions(source):
            missing.append(f"{scenario_path.name}: {source_path}")

    assert not missing, "Missing layout-bearing source UI workflows:\n" + "\n".join(missing)


def test_overlay_candidate_on_source_keeps_full_source_layout() -> None:
    source = {
        "nodes": [
            {"id": 1, "type": "A", "pos": [10, 20], "size": [100, 50], "widgets_values": ["old"]},
            {"id": 2, "type": "Note", "pos": [300, 20], "widgets_values": ["kept"]},
        ],
        "links": [[1, 2, 0, 1, 0, "STRING"]],
    }
    candidate = {
        "nodes": [
            {"id": 1, "type": "A", "pos": [999, 999], "widgets_values": ["new"]},
            {"id": 3, "type": "B", "pos": [500, 500]},
        ],
        "links": [[2, 3, 0, 1, 0, "STRING"]],
    }

    merged = overlay_candidate_on_source(source, candidate)
    nodes = {node["id"]: node for node in merged["nodes"]}
    assert nodes[1]["widgets_values"] == ["new"]
    assert nodes[1]["pos"] == [10, 20]
    assert nodes[1]["size"] == [100, 50]
    assert nodes[2]["pos"] == [300, 20]
    assert nodes[3]["pos"] == [500, 500]
    assert merged["links"] == [[2, 3, 0, 1, 0, "STRING"]]
    assert merged["extra"]["vibecomfy"]["demo_layout_source"] == "source_ui_overlay"
