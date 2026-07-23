"""Regression tests for deterministic demo asset bundle generation."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from scripts.build_demo_scenario_assets import build_bundle, write_bundle


def test_write_bundle_is_byte_for_byte_deterministic(tmp_path: Path) -> None:
    bundle = {
        "version": 1,
        "scenarios": {
            "example": {
                "source_run_dir": "example",
                "original_graph": {"links": [], "nodes": [{"id": 1}]},
                "candidate_graph": {"links": [], "nodes": [{"id": 2}]},
                "response": {"reply": "done"},
            }
        },
    }
    first = tmp_path / "first.json.gz"
    second = tmp_path / "second.json.gz"
    write_bundle(bundle, first)
    write_bundle(bundle, second)
    assert first.read_bytes() == second.read_bytes()
    with gzip.open(first, "rt", encoding="utf-8") as handle:
        assert json.load(handle) == bundle


def test_build_bundle_preserves_minimal_preview_response_contract(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    run_dir = run_root / "example"
    run_dir.mkdir(parents=True)
    graph = {"links": [], "nodes": [{"id": 1}]}
    (run_dir / "original.ui.json").write_text(json.dumps(graph), encoding="utf-8")
    (run_dir / "candidate.ui.json").write_text(
        json.dumps({"links": [], "nodes": [{"id": 1}, {"id": 2}]}),
        encoding="utf-8",
    )
    (run_dir / "response.json").write_text(
        json.dumps(
            {
                "reply": "done",
                "session_id": "session",
                "turn_id": "turn",
                "candidate_graph_hash": "candidate-hash",
                "candidate_structural_graph_hash": "structural-hash",
                "outcome": {
                    "kind": "candidate",
                    "changes": [
                        {"uid": "1", "field_path": "seed", "old": 1, "new": 2}
                    ],
                },
                "change_details": {
                    "done_summary": "Changed seed.",
                    "batch_turns": [
                        {
                            "turn_number": 1,
                            "field_changes": [
                                {"uid": "1", "field_path": "seed", "old": 1, "new": 2}
                            ],
                            "report": {"executor": {"private": "must not ship"}},
                            "statements": [
                                {
                                    "op_kind": "node_call",
                                    "landed": True,
                                    "touched_uids": ["n2"],
                                    "detail": {"private": "must not ship"},
                                }
                            ],
                        }
                    ],
                },
                "report": {
                    "kind": "reorganise",
                    "revision_evidence": {"scoped_diff": {"has_diff": True}},
                    "executor": {"private": "must not ship"},
                },
                "debug": {"private": "must not ship"},
            }
        ),
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_run_tree": "runs",
                "scenarios": [
                    {"id": "example", "run_location": {"run_dir": "example"}}
                ],
            }
        ),
        encoding="utf-8",
    )

    response = build_bundle(root=tmp_path, manifest_path=manifest_path)["scenarios"][
        "example"
    ]["response"]

    assert response["outcome"]["changes"][0]["field_path"] == "seed"
    assert response["change_details"]["batch_turns"][0]["field_changes"][0]["new"] == 2
    assert response["candidate_graph_hash"] == "candidate-hash"
    assert response["candidate_structural_graph_hash"] == "structural-hash"
    assert response["report"] == {
        "kind": "reorganise",
        "revision_evidence": {"scoped_diff": {"has_diff": True}},
    }
    assert "debug" not in response
    assert "report" not in response["change_details"]["batch_turns"][0]
    assert response["change_details"]["batch_turns"][0]["statements"] == [
        {"op_kind": "node_call", "landed": True, "touched_uids": ["n2"]}
    ]
