from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


SNAPSHOT_PATH = Path("tests/snapshots/template_index_contracts.json")
PINNED_FIELDS = (
    "id",
    "public_inputs",
    "public_outputs",
    "artifact_expectations",
    "requirements",
    "custom_node_packs",
    "models",
)


def _index_rows() -> dict[str, dict[str, Any]]:
    payload = json.loads(Path("template_index.json").read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["templates"]}


def _shape(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in PINNED_FIELDS}


def _snapshot_rows() -> dict[str, dict[str, Any]]:
    payload = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["templates"]}


def test_template_index_pinned_template_ids_are_stable() -> None:
    rows = _index_rows()
    snapshot = _snapshot_rows()

    assert set(snapshot) <= set(rows)
    assert [rows[template_id]["id"] for template_id in snapshot] == list(snapshot)


@pytest.mark.parametrize("template_id", list(_snapshot_rows()), ids=list(_snapshot_rows()))
def test_template_index_contract_shape_matches_post_f_snapshot(template_id: str) -> None:
    rows = _index_rows()
    snapshot = _snapshot_rows()

    assert _shape(rows[template_id]) == snapshot[template_id]
