"""COMFY_DYNAMICCOMBO_V3 widgets, linked value primitives, and UI-only notes.

Fixture rows are ComfyUI 0.42 /object_info for BlockSparseAttention and
SaveVideo (tooltips stripped).  The widgets_values rows are the ones ComfyUI's
own FastH3 text-to-video template saves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy._compile._resolve import HelperResolveError, resolve_helpers
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.widgets.aliases import widget_names_from_schema
from vibecomfy.schema.provider import _schema_from_object_info
from vibecomfy.schema.types import _input_spec_payload
from vibecomfy.schema.validate import validate_api_against_schema
from vibecomfy.workflow import VibeEdge, VibeNode

OBJECT_INFO = json.loads(
    (Path(__file__).parent / "fixtures/dynamic_combo/object_info_comfyui_0_42.json").read_text()
)
BSA_VALUES = ["vsa", 10, 0.2, 1, "", 12288, 256, "exact_kv_and_rows", False]
SAVE_VIDEO_VALUES = ["video/MiniMax_H3", "auto", "auto", "auto"]


class _Provider:
    def get_schema(self, class_type):
        info = OBJECT_INFO.get(class_type)
        return _schema_from_object_info(class_type, info) if info else None


def _schema(class_type):
    return _Provider().get_schema(class_type)


def test_dynamic_combo_controller_is_a_widget_with_its_option_fields():
    spec = _schema("BlockSparseAttention").inputs["selection"]
    assert spec.choices == ["sol-attn", "sla", "vsa"]
    assert spec.dynamic_fields == {
        "sol-attn": ("selection.tau",),
        "sla": ("selection.keep_percent",),
        "vsa": ("selection.keep_percent",),
    }
    assert set(spec.dynamic_options) == {"sol-attn", "sla", "vsa"}


def test_nested_dynamic_combo_fields_are_all_dotted_under_the_controller():
    fields = _schema("SaveVideo").inputs["format"].dynamic_fields["mp4"]
    assert "format.codec" in fields
    assert "format.codec.encoding" in fields
    assert all(name.startswith("format.codec") for name in fields)


def test_chosen_option_widgets_follow_the_controller():
    names = widget_names_from_schema("BlockSparseAttention", _schema("BlockSparseAttention"), BSA_VALUES)
    assert names == [
        "selection", "selection.keep_percent", "start_percent", "end_percent", "dense_blocks",
        "min_tokens", "extra_tokens", "sink_conditioning", "verbose",
    ]


def test_live_dynamic_schema_wins_over_the_committed_save_video_row():
    names = widget_names_from_schema("SaveVideo", _schema("SaveVideo"), SAVE_VIDEO_VALUES)
    assert names == ["filename_prefix", "format", "format.codec", "codec"]


def test_ui_import_names_dynamic_combo_widgets_and_validates():
    ui = {
        "nodes": [
            {"id": 1, "type": "BlockSparseAttention", "mode": 0, "inputs": [
                {"name": "model", "type": "MODEL", "link": None}], "outputs": [
                {"name": "MODEL", "type": "MODEL", "links": []}], "widgets_values": BSA_VALUES},
            {"id": 2, "type": "SaveVideo", "mode": 0, "inputs": [
                {"name": "video", "type": "VIDEO", "link": None}], "outputs": [],
             "widgets_values": SAVE_VIDEO_VALUES},
            {"id": 3, "type": "MarkdownNote", "mode": 0, "inputs": [], "outputs": [],
             "widgets_values": ["## About this workflow"]},
        ],
        "links": [],
    }
    workflow = from_ui(ui, workflow_id="dynamic-combo", schema_provider=_Provider())
    bsa = {**workflow.nodes["1"].widgets, **workflow.nodes["1"].inputs}
    assert bsa["selection"] == "vsa"
    assert bsa["selection.keep_percent"] == 10
    assert bsa["start_percent"] == 0.2 and bsa["end_percent"] == 1 and bsa["verbose"] is False
    assert not any(name.startswith("widget_") for name in bsa)
    save = {**workflow.nodes["2"].widgets, **workflow.nodes["2"].inputs}
    assert save["format"] == "auto" and save["format.codec"] == "auto"
    # A UI-only annotation is not a node the server is missing.
    assert "MarkdownNote" not in workflow.requirements.missing_nodes

    api = {"1": {"class_type": "BlockSparseAttention", "inputs": {
        **{k: v for k, v in bsa.items()}, "model": ["9", 0]}}}
    errors = [i for i in validate_api_against_schema(api, _Provider()) if i.severity == "error"]
    assert errors == []


def test_unchosen_option_field_is_still_rejected():
    inputs = dict(zip(widget_names_from_schema(
        "BlockSparseAttention", _schema("BlockSparseAttention"), BSA_VALUES), BSA_VALUES))
    inputs.update({"model": ["9", 0], "selection": "sol-attn"})
    api = {"1": {"class_type": "BlockSparseAttention", "inputs": inputs}}
    messages = [i.message for i in validate_api_against_schema(api, _Provider())]
    assert any("selection.keep_percent" in message for message in messages)


def test_plain_specs_serialize_without_dynamic_options():
    assert "dynamic_options" not in _input_spec_payload(_schema("BlockSparseAttention").inputs["start_percent"])
    assert "dynamic_options" in _input_spec_payload(_schema("BlockSparseAttention").inputs["selection"])


def test_linked_primitive_int_passes_its_source_through():
    # Stock LTX-2.5 template: ResolutionSelector -> subgraph input -> PrimitiveInt.
    nodes = {
        "res": VibeNode("res", "ResolutionSelector", native_output_names=["width", "height"],
                        native_output_types=["INT", "INT"]),
        "primitive": VibeNode("primitive", "PrimitiveInt", inputs={"value": 720}),
        "target": VibeNode("target", "EmptyLatent"),
    }
    edges = [VibeEdge("res", "height", "primitive", "value"), VibeEdge("primitive", "0", "target", "height")]

    resolve_helpers(nodes, edges, {})

    assert "primitive" not in nodes
    assert [(e.from_node, e.from_output, e.to_node, e.to_input) for e in edges] == [
        ("res", "height", "target", "height")]


def test_linked_primitive_known_type_mismatch_fails_closed():
    nodes = {
        "source": VibeNode("source", "Source", native_output_names=["out"], native_output_types=["IMAGE"]),
        "primitive": VibeNode("primitive", "PrimitiveFloat"),
        "target": VibeNode("target", "Target"),
    }
    edges = [VibeEdge("source", "out", "primitive", "value"), VibeEdge("primitive", "0", "target", "x")]

    with pytest.raises(HelperResolveError, match="not FLOAT"):
        resolve_helpers(nodes, edges, {})
