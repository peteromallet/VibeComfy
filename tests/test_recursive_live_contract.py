"""Fail-closed replay checks for the bounded T01 native recursive spike.

The fixture is deliberately marked undetermined: it records the native
definition/instance and -10/-20 boundary shape found in the installed
frontend, while refusing to turn source-derived structure into live bytes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.porting.edit.ops import (
    DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
    DELTA_SCHEMA_VERSION,
    EditOpParseError,
    ensure_root_scoped_delta_envelope,
)


FIXTURE = Path(__file__).parent / "fixtures" / "recursive_live_contract" / "depth2.json"


def _load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_preserves_native_recursive_definition_and_instance_shape() -> None:
    data = _load_fixture()
    assert data["schema"] == "b0s-t01-native-recursive-contract-v1"
    assert data["capture_status"] == "undetermined"

    contract = data["native_contract"]
    assert contract["definition_store"] == "rootGraph.subgraphs"
    assert contract["serialized_definition_container"] == "definitions.subgraphs"
    assert contract["scope_paths"] == ["", "outer", "outer:inner"]
    assert contract["boundary_link_ids"] == {
        "subgraph_input": -10,
        "subgraph_output": -20,
    }

    root = contract["root_graph"]
    assert root["nodes"][0]["type"] == "sg-outer"
    assert root["nodes"][0]["subgraph_instance"] is True
    assert root["definitions"] == ["sg-outer", "sg-inner"]

    definitions = contract["definitions"]
    outer = definitions["sg-outer"]
    inner = definitions["sg-inner"]
    assert outer["nodes"][0]["type"] == "sg-inner"
    assert inner["nodes"][0]["type"] == "Reroute"
    for graph in (outer, inner):
        links = graph["links"]
        assert any(link[1] == -10 for link in links)
        assert any(link[3] == -20 for link in links)


def test_inner_scoped_apply_is_rejected_without_mutating_the_contract() -> None:
    data = _load_fixture()
    before = json.dumps(data, sort_keys=True)
    with pytest.raises(EditOpParseError) as exc_info:
        ensure_root_scoped_delta_envelope(
            {
                "schema_version": DELTA_SCHEMA_VERSION,
                "ops": [
                    {
                        "op": "set_node_field",
                        "target": ["outer:inner", "21", "widgets.value"],
                        "value": "must-not-apply",
                    }
                ],
            }
        )
    assert exc_info.value.code == DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY
    assert "outer:inner" in exc_info.value.detail["scope_paths"]
    assert json.dumps(data, sort_keys=True) == before


def test_operation_matrix_is_explicit_about_missing_live_bytes() -> None:
    operations = _load_fixture()["operations"]
    assert operations["definition_discovery"] == "supported_by_native_frontend"
    assert operations["cloned_instance_discovery"] == "supported_by_native_frontend"
    assert operations["root_mutation"] == "supported_by_current_adapter"
    assert operations["inner_depth1_mutation"] == "unsupported_scoped_apply"
    assert operations["inner_depth2_mutation"] == "unsupported_scoped_apply"
    assert operations["serialize_reload"] == "not_captured_without_live_graph_export"
    assert operations["rollback"] == "root_inverse_delta_only; inner_scope_not_supported"
