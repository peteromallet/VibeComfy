"""Focused tests for Action 4: pos= reserved names, original ingest round-trip, dict-row + duplicate-name emit."""

from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.ingest.normalize import ingest_workflow_and_ui
from vibecomfy.porting.edit._parse import _parse_and_validate_batch, reserved_kwarg_is_coordinate_hint
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.porting.refuse import RefusedEmit
from vibecomfy.porting.widget_shape_fence import (
    WidgetShapeDecision,
    WidgetShapeReason,
    decide_widget_shape,
)
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import RawWidgetPayload, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def _parse(code: str):
    return _parse_and_validate_batch(
        code,
        max_batch_bytes=65536,
        max_statements=50,
        max_expanded_statements=50,
        max_for_iterations=50,
    )


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def test_pos_handle_ref_on_easy_pipein_is_not_expression_not_constant() -> None:
    parsed = _parse(
        "guide_pipe = node('easy pipeIn', "
        "pos=cliptextencode_2.CONDITIONING_0, "
        "neg=cliptextencode.CONDITIONING_0)\n"
    )
    assert parsed.diagnostics == ()
    codes = [d.code for d in parsed.diagnostics]
    assert "expression_not_constant" not in codes


def test_pos_constant_still_treated_as_coordinate_hint() -> None:
    assert reserved_kwarg_is_coordinate_hint("pos", value=__import__("ast").parse("12", mode="eval").body) is True
    handle = __import__("ast").parse("cliptextencode_2.CONDITIONING_0", mode="eval").body
    assert reserved_kwarg_is_coordinate_hint("pos", value=handle) is False
    assert reserved_kwarg_is_coordinate_hint(
        "pos",
        value=__import__("ast").parse("12", mode="eval").body,
        schema_inputs={"pos": object()},
    ) is False


def test_x_constant_on_saveimage_still_parses_as_hint() -> None:
    parsed = _parse("save_image = SaveImage(images=src.in_, x=12)\n")
    assert parsed.diagnostics == ()


def test_ingest_round_trip_original_schema_less_links() -> None:
    """Original-graph links to schema-less sockets must emit, not RefusedEmit."""
    ui = {
        "last_node_id": 55,
        "last_link_id": 4,
        "nodes": [
            {
                "id": 58,
                "type": "ImageBatchSplitter //Inspire",
                "pos": [0, 0],
                "size": [200, 80],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [{"name": "image", "type": "IMAGE", "link": None}],
                "outputs": [
                    {"name": "images", "type": "IMAGE", "links": [1, 2, 3, 4], "slot_index": 0},
                ],
                "properties": {},
                "widgets_values": [],
            },
            {
                "id": 55,
                "type": "ImageGridComposite2x2 //Inspire",
                "pos": [400, 0],
                "size": [200, 120],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [
                    {"name": "image1", "type": "IMAGE", "link": 1},
                    {"name": "image2", "type": "IMAGE", "link": 2},
                    {"name": "image3", "type": "IMAGE", "link": 3},
                    {"name": "image4", "type": "IMAGE", "link": 4},
                ],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": None, "slot_index": 0}],
                "properties": {},
                "widgets_values": [],
            },
        ],
        "links": [
            [1, 58, 0, 55, 0, "IMAGE"],
            [2, 58, 0, 55, 1, "IMAGE"],
            [3, 58, 0, 55, 2, "IMAGE"],
            [4, 58, 0, 55, 3, "IMAGE"],
        ],
        "groups": [],
        "extra": {},
    }
    workflow, retained = ingest_workflow_and_ui(ui, schema_provider=None)
    assert retained["nodes"][1]["id"] == 55
    emitted = emit_ui_json(
        workflow,
        schema_provider=None,
        prior_ui_payload=ui,
        guard_original_ui=ui,
    )
    assert len(emitted["links"]) == 4


def test_duplicate_input_name_emit_imagescale_width() -> None:
    ui = {
        "last_node_id": 89,
        "last_link_id": 2,
        "nodes": [
            {
                "id": 110,
                "type": "PrimitiveInt",
                "pos": [0, 0],
                "size": [100, 40],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "INT", "type": "INT", "links": [1], "slot_index": 0}],
                "properties": {},
                "widgets_values": [512],
            },
            {
                "id": 89,
                "type": "ImageScale",
                "pos": [200, 0],
                "size": [200, 100],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [
                    {"name": "image", "type": "IMAGE", "link": None},
                    {"name": "width", "type": "INT", "link": 1, "widget": {"name": "width"}},
                    {"name": "height", "type": "INT", "link": None, "widget": {"name": "height"}},
                    {"name": "width", "type": "INT", "link": 2, "widget": {"name": "width"}},
                ],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": None, "slot_index": 0}],
                "properties": {},
                "widgets_values": ["nearest-exact", 512, 512, "disabled"],
            },
            {
                "id": 7,
                "type": "PrimitiveInt",
                "pos": [0, 80],
                "size": [100, 40],
                "flags": {},
                "order": 2,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "INT", "type": "INT", "links": [2], "slot_index": 0}],
                "properties": {},
                "widgets_values": [768],
            },
        ],
        "links": [
            [1, 110, 0, 89, 1, "INT"],
            [2, 7, 0, 89, 3, "INT"],
        ],
        "groups": [],
        "extra": {},
    }
    provider = _Provider(
        {
            "ImageScale": NodeSchema(
                class_type="ImageScale",
                pack=None,
                inputs={
                    "image": InputSpec("IMAGE"),
                    "width": InputSpec("INT"),
                    "height": InputSpec("INT"),
                    "upscale_method": InputSpec("COMBO"),
                    "crop": InputSpec("COMBO"),
                },
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="test_provider",
                confidence=1.0,
            ),
            "PrimitiveInt": NodeSchema(
                class_type="PrimitiveInt",
                pack=None,
                inputs={"value": InputSpec("INT")},
                outputs=[OutputSpec("INT", "INT")],
                source_provider="test_provider",
                confidence=1.0,
            ),
        }
    )
    workflow, _retained = ingest_workflow_and_ui(ui, schema_provider=provider)
    width_edges = [e.to_input for e in workflow.edges if e.to_node == "89"]
    assert "width" in width_edges
    assert "width_1" in width_edges
    emitted = emit_ui_json(
        workflow,
        schema_provider=provider,
        prior_ui_payload=ui,
        guard_original_ui=ui,
    )
    assert len(emitted["links"]) == 2


def test_duplicate_input_name_emit_coordinates() -> None:
    ui = {
        "last_node_id": 33,
        "last_link_id": 1,
        "nodes": [
            {
                "id": 28,
                "type": "SplineEditor",
                "pos": [0, 0],
                "size": [140, 40],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [
                    {"name": "coordinates", "type": "FLOAT", "links": None, "slot_index": 0},
                    {"name": "coordinates", "type": "FLOAT", "links": [1], "slot_index": 1},
                ],
                "properties": {},
                "widgets_values": [],
            },
            {
                "id": 33,
                "type": "CutAndDragOnPath",
                "pos": [240, 0],
                "size": [200, 80],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [
                    {"name": "image", "type": "IMAGE", "link": None},
                    {"name": "coordinates", "type": "FLOAT", "link": 1},
                    {"name": "coordinates", "type": "FLOAT", "link": None},
                ],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": None, "slot_index": 0}],
                "properties": {},
                "widgets_values": [],
            },
        ],
        "links": [[1, 28, 1, 33, 1, "FLOAT"]],
        "groups": [],
        "extra": {},
    }
    workflow, _retained = ingest_workflow_and_ui(ui, schema_provider=None)
    emitted = emit_ui_json(
        workflow,
        schema_provider=None,
        prior_ui_payload=ui,
        guard_original_ui=ui,
    )
    assert len(emitted["links"]) == 1


def test_dict_row_vhs_format_field_emits() -> None:
    raw_widgets = {
        "frame_rate": 8,
        "loop_count": 0,
        "filename_prefix": "AnimateDiff",
        "format": "image/gif",
        "pingpong": False,
        "save_output": True,
        "videopreview": {"hidden": False, "paused": False},
        "crf": 20,
        "save_metadata": True,
        "trim_to_audio": False,
    }
    ui = {
        "last_node_id": 8,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 8,
                "type": "VHS_VideoCombine",
                "pos": [0, 0],
                "size": [300, 200],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [{"name": "Filenames", "type": "VHS_FILENAMES", "links": None}],
                "properties": {"vibecomfy_uid": "uid-vhs"},
                "widgets_values": dict(raw_widgets),
            }
        ],
        "links": [],
        "groups": [],
        "extra": {},
    }
    provider = _Provider(
        {
            "VHS_VideoCombine": NodeSchema(
                class_type="VHS_VideoCombine",
                pack=None,
                inputs={
                    "images": InputSpec("IMAGE"),
                    "frame_rate": InputSpec("FLOAT"),
                    "loop_count": InputSpec("INT"),
                    "filename_prefix": InputSpec("STRING"),
                    "format": InputSpec("COMBO"),
                    "pingpong": InputSpec("BOOLEAN"),
                    "save_output": InputSpec("BOOLEAN"),
                },
                outputs=[OutputSpec("Filenames", "VHS_FILENAMES")],
                source_provider="test_provider",
                confidence=1.0,
            )
        }
    )
    workflow, _retained = ingest_workflow_and_ui(ui, schema_provider=provider)
    node = workflow.nodes["8"]
    node.uid = "uid-vhs"
    node.widgets["format"] = "image/webp"
    if "format" in node.inputs:
        node.inputs["format"] = "image/webp"
    emitted = emit_ui_json(
        workflow,
        schema_provider=provider,
        prior_ui_payload=ui,
        guard_original_ui=ui,
    )
    vhs = next(item for item in emitted["nodes"] if item["id"] == 8)
    values = vhs["widgets_values"]
    assert isinstance(values, dict)
    assert values["format"] == "image/webp"
    assert "videopreview" in values


def test_dict_row_positional_widget_n_delta_still_refuses() -> None:
    from vibecomfy.porting.emit.ui import WidgetShapeEvidence

    evidence = WidgetShapeEvidence(
        node_id="7",
        class_type="DynamicRows",
        schema_less=False,
        confidence=1.0,
        raw_widget_count=2,
        candidate_widget_count=2,
        schema_widget_count=2,
        compacted_widget_names=("a", "b"),
        raw_widget_shape="list",
        has_dict_rows=True,
        overflow=False,
        provider="test_provider",
        explicit_widget_overflow=False,
        raw_widget_length_recovered=False,
    )
    verdict = decide_widget_shape(
        evidence,
        raw_widget_payloads={
            "7": RawWidgetPayload(
                values=[{"row": 1}, {"row": 2}],
                shape="list",
                source="ui.widgets_values",
                has_dict_rows=True,
                length=2,
            )
        },
        raw_payloads={
            "7": {
                "id": 7,
                "type": "DynamicRows",
                "pos": [10, 20],
                "size": [300, 120],
                "widgets_values": [{"row": 1}, {"row": 2}],
            }
        },
        layout_entries={"7": {"pos": [10, 20], "size": [300, 120]}},
        field_deltas={"7": {"widget_1": ("old", "new")}},
    )
    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.WIDGET_DELTA in verdict.reasons
