"""Regression tests for deterministic demo asset bundle generation."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from scripts.build_demo_scenario_assets import write_bundle


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
