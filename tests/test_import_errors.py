from __future__ import annotations

from vibecomfy.porting.import_errors import native_boundary_recovery
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.commands.schemas import _extract_class_types_from_source_json


def test_native_boundary_recovery_is_actionable_without_materializing_candidate() -> None:
    result = native_boundary_recovery(
        ValueError(
            "unsupported_boundary_encoding: definition 'definitions[0]' contains "
            "native inputNode/outputNode markers; use an explicit Python-owned boundary mapping"
        ),
        "workflow.json",
    )
    assert result is not None
    assert result["candidate_status"] == "not_materialized"
    assert "ComfyUI" in result["recovery"]["inspect_source"]
    assert "port check workflow.json" in result["recovery"]["port_after_resolution"]
    assert "port convert workflow.json" in result["recovery"]["materialize_after_resolution"]


def test_import_errors_does_not_relabel_unrelated_failures() -> None:
    assert native_boundary_recovery(ValueError("missing schema"), "workflow.json") is None


def test_native_subgraph_boundaries_are_imported_into_canonical_contract() -> None:
    raw = {
        "nodes": [{"id": 2, "type": "Box", "inputs": [], "outputs": [], "widgets_values": []}],
        "links": [],
        "definitions": {"subgraphs": [{
            "id": "box", "name": "Box", "inputNode": {"id": -10}, "outputNode": {"id": -20},
            "inputs": [{"name": "value", "type": "INT", "linkIds": [1]}],
            "outputs": [{"name": "result", "type": "INT", "linkIds": [2]}],
            "nodes": [
                {"id": "src", "type": "Source", "inputs": [], "outputs": [{"name": "out", "links": [2]}]},
                {"id": "sink", "type": "Sink", "inputs": [{"name": "value", "link": 1}], "outputs": []},
            ],
            "links": [
                {"id": 1, "origin_id": -10, "origin_slot": 0, "target_id": "sink", "target_slot": 0, "type": "INT"},
                {"id": 2, "origin_id": "src", "origin_slot": 0, "target_id": -20, "target_slot": 0, "type": "INT"},
            ],
        }]},
    }
    workflow = from_ui(raw, use_comfy_converter=False)
    assert len(workflow.nodes) == 2
    assert not workflow.definitions


def test_schema_ensure_source_discovery_expands_native_subgraphs() -> None:
    from pathlib import Path

    source = Path(__file__).parent / "fixtures" / "native_h3_minimal.json"
    classes = _extract_class_types_from_source_json(source)
    assert "MiniMaxH3ImageToVideo" in classes
    assert "LanPaint_AVEncode" in classes
    assert "LanPaint_AVDecode" in classes
    assert "4c314f31-ecda-4b08-ae98-faaba1bf613f" not in classes
