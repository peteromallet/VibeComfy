"""Characterization-gate consumer for the committed snapshot triplets.

Re-skins ``tests/test_snapshot_api_workflows.py`` under the
``@pytest.mark.characterization`` marker so the characterization gate
guards the snapshot corpus byte-for-byte.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.regenerate_snapshots import (
    STEM_TO_READY_ID,
    _canonical_class_types_text,
    _canonical_widget_values_text,
)

from vibecomfy import load_workflow_any

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "tests" / "snapshots"


@pytest.mark.characterization
@pytest.mark.parametrize("stem", sorted(STEM_TO_READY_ID.keys()))
def test_snapshot_sidecars_match_compiled_workflow(stem: str) -> None:
    ready_id = STEM_TO_READY_ID[stem]
    workflow = load_workflow_any(ready_id)
    api = workflow.compile("api")

    committed_class_types = json.loads(
        (SNAPSHOT_DIR / f"{stem}.class_types.json").read_text(encoding="utf-8")
    )
    regenerated_class_types = json.loads(_canonical_class_types_text(api))
    assert regenerated_class_types == committed_class_types, (
        f"class_types drift for {ready_id}: regenerate with "
        f"`python scripts/regenerate_snapshots.py --write`."
    )

    committed_widget_values = json.loads(
        (SNAPSHOT_DIR / f"{stem}.widget_values.json").read_text(encoding="utf-8")
    )
    regenerated_widget_values = json.loads(_canonical_widget_values_text(api))
    assert regenerated_widget_values == committed_widget_values, (
        f"widget_values drift for {ready_id}: regenerate with "
        f"`python scripts/regenerate_snapshots.py --write`."
    )
