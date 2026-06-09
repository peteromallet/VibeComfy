"""Golden-run regression guard for the M4 template-edit scenarios.

Each ``_M4_BUILDERS`` builder loads (or faithfully mirrors) a real Wan/LTX base
workflow, performs the canonical "correct" multi-edit, finalizes metadata, and
freezes a golden evidence pack. This guard locks those golden runs so they
cannot silently rot if a VibeComfy API (compile, finalize_metadata, a node
class) changes underneath them.

It asserts, per scenario:
  * the builder runs without error and emits compiled_api.json + metadata.json +
    actions.jsonl, all non-empty,
  * compiled_api.json parses to a non-empty node graph,
  * actions.jsonl records finalize_metadata with status=completed,
  * metadata.json stamps this scenario's builder as the origin layer,
  * a matching scenario YAML + brief exist for the builder key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentic.actors_m4 import _M4_BUILDERS

_AGENTIC_DIR = Path(__file__).resolve().parents[1] / "agentic"
_SCENARIOS_DIR = _AGENTIC_DIR / "scenarios"
_BRIEFS_DIR = _AGENTIC_DIR / "briefs"

_BUILDER_ITEMS = sorted(_M4_BUILDERS.items())

# Scenarios whose rubric carries an `observed` entrypoint/layer telemetry check —
# those builders must stamp the actors_m4 origin into metadata. Builders that load
# a real base template (e.g. ltx-i2v-swap) legitimately carry the template's own
# provenance instead, and their rubric observes template-grounding, not the layer.
_ORIGIN_OBSERVED_SCENARIOS = frozenset(
    {
        "wan-t2v-append-frame-interpolation",
        "wan22-i2v-second-pass-refine",
        "wan22-stack-highlow-noise-lora",
    }
)


def test_m4_builders_registered() -> None:
    # The six nuanced template-edit scenarios must all be wired.
    assert len(_M4_BUILDERS) == 6, sorted(_M4_BUILDERS)


@pytest.mark.parametrize("name,builder", _BUILDER_ITEMS, ids=[n for n, _ in _BUILDER_ITEMS])
def test_m4_golden_builder_emits_valid_evidence(name: str, builder, tmp_path: Path) -> None:
    manifest = builder(tmp_path)

    # 1. The three frozen-evidence files exist and are non-empty.
    for key in ("compiled_api_path", "metadata_path", "actions_path"):
        p = Path(manifest[key])
        assert p.is_file(), f"{name}: missing {key} ({p})"
        assert p.stat().st_size > 0, f"{name}: empty {key} ({p})"

    # 2. compiled_api.json parses to a non-empty node graph.
    compiled = json.loads(Path(manifest["compiled_api_path"]).read_text(encoding="utf-8"))
    assert isinstance(compiled, dict) and compiled, f"{name}: empty compiled_api"
    # Every node entry carries a class_type — the ground-truth the rubric reads.
    class_types = [
        v.get("class_type")
        for v in compiled.values()
        if isinstance(v, dict) and "class_type" in v
    ]
    assert class_types, f"{name}: no class_type nodes in compiled_api"

    # 3. actions.jsonl records finalize_metadata with status=completed.
    actions = [
        json.loads(line)
        for line in Path(manifest["actions_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        a.get("op") == "finalize_metadata" and a.get("status") == "completed"
        for a in actions
    ), f"{name}: actions.jsonl missing finalize_metadata/completed"

    # 4. metadata.json is valid and carries a workflow identity from finalize.
    metadata = json.loads(Path(manifest["metadata_path"]).read_text(encoding="utf-8"))
    assert isinstance(metadata, dict) and metadata, f"{name}: empty metadata"
    assert (
        metadata.get("workflow_id")
        or metadata.get("run_id")
        or "workflow_hash" in metadata
    ), f"{name}: metadata missing a workflow identity"

    # 5. Scenarios whose rubric OBSERVES the entrypoint/layer must stamp the origin.
    if name in _ORIGIN_OBSERVED_SCENARIOS:
        assert "actors_m4" in json.dumps(metadata), (
            f"{name}: rubric observes entrypoint/layer but metadata lacks the "
            "actors_m4 origin stamp"
        )


@pytest.mark.parametrize("name", [n for n, _ in _BUILDER_ITEMS])
def test_m4_scenario_and_brief_exist(name: str) -> None:
    yaml_path = _SCENARIOS_DIR / f"{name}.yaml"
    brief_path = _BRIEFS_DIR / f"{name}.md"
    assert yaml_path.is_file(), f"missing scenario yaml: {yaml_path}"
    assert brief_path.is_file(), f"missing brief: {brief_path}"
    # The scenario name field must match the builder registry key.
    text = yaml_path.read_text(encoding="utf-8")
    assert f"name: {name}" in text, f"{yaml_path}: name field != registry key {name!r}"
