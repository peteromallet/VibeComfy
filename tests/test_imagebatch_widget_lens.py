from __future__ import annotations

import copy
import json
from pathlib import Path

from vibecomfy.executor.graph_inspection import inspect_graph, render_inspect_markdown
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.porting.widgets.aliases import (
    apply_positional_widget_aliases,
    resolve_widget_name_with_provenance,
)
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.porting.widgets.schema import effective_widget_names_for_class


ROOT = Path(__file__).resolve().parents[1]


def _image_batch_ui() -> dict:
    return {
        "version": 0.4,
        "last_node_id": 3,
        "last_link_id": 2,
        "nodes": [
            {
                "id": 1,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "pos": [0, 0],
                "size": [320, 74],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0}],
                "properties": {},
                "widgets_values": ["first.png"],
            },
            {
                "id": 2,
                "type": "LoadImage",
                "class_type": "LoadImage",
                "pos": [0, 100],
                "size": [320, 74],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [2], "slot_index": 0}],
                "properties": {},
                "widgets_values": ["second.png"],
            },
            {
                "id": 3,
                "type": "ImageBatch",
                "class_type": "ImageBatch",
                "pos": [400, 50],
                "size": [320, 74],
                "flags": {},
                "order": 2,
                "mode": 0,
                "inputs": [
                    {"name": "image1", "type": "IMAGE", "link": 1},
                    {"name": "image2", "type": "IMAGE", "link": 2},
                ],
                "outputs": [],
                "properties": {},
                "widgets_values": [],
            },
        ],
        "links": [
            [1, 1, 0, 3, 0, "IMAGE"],
            [2, 2, 0, 3, 1, "IMAGE"],
        ],
    }


def test_imagebatch_fixture_has_link_inputs_not_named_widget_fields() -> None:
    fixture = ROOT / "tests/fixtures/live_agentic_corpus/cdb8167d4eccd0a8.json"
    image_batch = json.loads(fixture.read_text(encoding="utf-8"))["53"]

    assert set(image_batch["inputs"]) == {"image1", "image2"}
    assert effective_widget_names_for_class("ImageBatch") == []
    resolution = resolve_widget_name_with_provenance(
        "ImageBatch", 0, allow_object_info_fallback=False
    )
    assert resolution.resolved is False
    assert resolution.name == "widget_0"

    node = {"class_type": "ImageBatch", "inputs": image_batch["inputs"], "widgets_values": []}
    assert compact_widget_names_for_node(node, "ImageBatch").names == ()


def test_imagebatch_positional_aliases_do_not_turn_socket_slots_into_widgets() -> None:
    inputs = {"widget_0": ["1", 0], "widget_1": ["2", 0]}

    apply_positional_widget_aliases(inputs, "ImageBatch")

    assert inputs == {"widget_0": ["1", 0], "widget_1": ["2", 0]}


def test_legitimate_curated_widget_mapping_remains_named() -> None:
    inputs = {"widget_0": 123, "widget_2": 20}

    apply_positional_widget_aliases(inputs, "KSampler", input_aliases=["seed", None, "steps"])

    assert inputs == {"seed": 123, "steps": 20}


def test_imagebatch_inspect_emit_round_trip_keeps_socket_shape_and_no_false_lens() -> None:
    original = _image_batch_ui()
    evidence = inspect_graph(original)
    image_batch = next(node for node in evidence.nodes if node.class_type == "ImageBatch")
    rendered = render_inspect_markdown(evidence)

    assert image_batch.widgets == ()
    assert {slot.name for slot in image_batch.input_slots} == {"image1", "image2"}
    assert "ImageBatch effective_frames" not in rendered

    workflow = from_ui(copy.deepcopy(original), use_comfy_converter=False)
    emitted = emit_ui_json(workflow, include_virtual_wires=False)
    emitted_batch = next(node for node in emitted["nodes"] if node["class_type"] == "ImageBatch")

    assert emitted_batch["widgets_values"] == []
    assert [slot["name"] for slot in emitted_batch["inputs"]] == ["image1", "image2"]
    assert [slot["link"] for slot in emitted_batch["inputs"]] == [1, 2]
