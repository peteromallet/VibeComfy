"""Regression-guard consumer for the orphan snapshot sidecars.

Until this test landed, ``tests/snapshots/*.class_types.json`` and
``tests/snapshots/*.widget_values.json`` were written by
``python -m tools.regenerate_snapshots --check`` but read by nothing — so the CI
``--check`` gate protected nothing. This module compiles each ready template
identified by ``STEM_TO_READY_ID``, rederives the sidecar payloads with the
SAME canonicalisation as the regenerator, and asserts structural equality
against the committed bytes. ``regenerate_snapshots.py --check`` is now a real
regression guard.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.regenerate_snapshots import (
    STEM_TO_READY_ID,
    _canonical_class_types_text,
    _canonical_widget_values_text,
)

from vibecomfy import load_workflow_any


SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"


@pytest.mark.parametrize("stem", sorted(STEM_TO_READY_ID.keys()))
def test_snapshot_sidecars_match_compiled_workflow(stem: str) -> None:
    ready_id = STEM_TO_READY_ID[stem]
    workflow = load_workflow_any(ready_id)
    api = workflow.compile("api")

    committed_class_types = json.loads((SNAPSHOT_DIR / f"{stem}.class_types.json").read_text(encoding="utf-8"))
    regenerated_class_types = json.loads(_canonical_class_types_text(api))
    assert regenerated_class_types == committed_class_types, (
        f"class_types drift for {ready_id}: regenerate with `python -m tools.regenerate_snapshots --write`."
    )

    committed_widget_values = json.loads((SNAPSHOT_DIR / f"{stem}.widget_values.json").read_text(encoding="utf-8"))
    regenerated_widget_values = json.loads(_canonical_widget_values_text(api))
    assert regenerated_widget_values == committed_widget_values, (
        f"widget_values drift for {ready_id}: regenerate with `python -m tools.regenerate_snapshots --write`."
    )


def test_api_ingest_snapshot_is_retained_authority_for_ready_template() -> None:
    from vibecomfy.ingest.normalize import ingest_workflow_and_ui
    from vibecomfy.ingest.snapshot import SEMANTIC_HASH_VERSION, snapshot_of

    stem = sorted(STEM_TO_READY_ID.keys())[0]
    workflow = load_workflow_any(STEM_TO_READY_ID[stem])
    api = workflow.compile("api")
    retained, _canonical = ingest_workflow_and_ui(api)
    snapshot = snapshot_of(retained)
    assert snapshot is not None
    assert snapshot.source_representation == "api"
    assert snapshot.semantic_hash_version == SEMANTIC_HASH_VERSION
    assert snapshot.identity
    assert snapshot.workflow is not retained
    retained.nodes[next(iter(retained.nodes))].class_type = "MutatedAfterIngest"
    assert snapshot.workflow.nodes[next(iter(snapshot.workflow.nodes))].class_type != "MutatedAfterIngest"
