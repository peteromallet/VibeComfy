from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from vibecomfy.porting.edit.apply import apply_delta, guard_full_ui, resolve_delta
from vibecomfy.porting.edit.ledger import EditLedger
from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.porting.edit.normalize import normalize_ui_json


class _SchemaProvider:
    def __init__(self) -> None:
        self._schemas = {
            "CheckpointLoaderSimple": NodeSchema(
                class_type="CheckpointLoaderSimple",
                pack="core",
                inputs={"ckpt_name": InputSpec(type="STRING", required=True)},
                outputs=[
                    OutputSpec(type="MODEL", name="MODEL"),
                    OutputSpec(type="CLIP", name="CLIP"),
                    OutputSpec(type="VAE", name="VAE"),
                ],
            ),
            "CLIPTextEncode": NodeSchema(
                class_type="CLIPTextEncode",
                pack="core",
                inputs={"text": InputSpec(type="STRING", required=True), "clip": InputSpec(type="CLIP", required=True)},
                outputs=[OutputSpec(type="CONDITIONING", name="CONDITIONING")],
            ),
            "KSampler": NodeSchema(
                class_type="KSampler",
                pack="core",
                inputs={
                    "seed": InputSpec(type="INT"),
                    "steps": InputSpec(type="INT", min=1, max=100),
                    "cfg": InputSpec(type="FLOAT", min=0.0, max=50.0),
                    "sampler_name": InputSpec(type="STRING", choices=["euler", "heun"]),
                    "scheduler": InputSpec(type="STRING", choices=["normal", "karras"]),
                    "denoise": InputSpec(type="FLOAT", min=0.0, max=1.0),
                    "model": InputSpec(type="MODEL", required=True),
                    "positive": InputSpec(type="CONDITIONING", required=True),
                    "negative": InputSpec(type="CONDITIONING", required=True),
                    "latent_image": InputSpec(type="LATENT", required=True),
                },
                outputs=[OutputSpec(type="LATENT", name="LATENT")],
            ),
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack="core",
                inputs={
                    "images": InputSpec(type="IMAGE", required=True),
                    "filename_prefix": InputSpec(type="STRING", required=True),
                },
                outputs=[],
            ),
        }

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


class _RuneXXSchemaProvider:
    def __init__(self) -> None:
        self._schemas = {
            "VAEDecodeTiled": NodeSchema(
                class_type="VAEDecodeTiled",
                pack="core",
                inputs={},
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
            ),
            "ImageScaleBy": NodeSchema(
                class_type="ImageScaleBy",
                pack="core",
                inputs={
                    "image": InputSpec(type="IMAGE", required=True),
                    "upscale_method": InputSpec(type="STRING", required=True),
                    "scale_by": InputSpec(type="FLOAT", required=True),
                },
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
            ),
            "VHS_VideoCombine": NodeSchema(
                class_type="VHS_VideoCombine",
                pack="ComfyUI-VideoHelperSuite",
                inputs={"images": InputSpec(type="IMAGE", required=True)},
                outputs=[OutputSpec(type="VHS_FILENAMES", name="Filenames")],
            ),
        }

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _fixture(name: str = "flat.json") -> dict[str, object]:
    path = Path("tests/fixtures/agent_edit") / name
    return json.loads(path.read_text(encoding="utf-8"))


def _helper_root_fixture() -> dict[str, object]:
    return {
        "last_node_id": 4,
        "last_link_id": 11,
        "nodes": [
            {
                "id": 1,
                "type": "SourceNode",
                "pos": [0, 0],
                "size": [210, 58],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "OUT", "type": "IMAGE", "links": [10], "slot_index": 0}],
                "properties": {},
                "widgets_values": [],
            },
            {
                "id": 2,
                "type": "SetNode",
                "pos": [220, 0],
                "size": [200, 58],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [{"name": "value", "type": "IMAGE", "link": 10}],
                "outputs": [],
                "properties": {},
                "widgets_values": ["bus"],
            },
            {
                "id": 3,
                "type": "GetNode",
                "pos": [440, 0],
                "size": [200, 58],
                "flags": {},
                "order": 2,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "value", "type": "IMAGE", "links": [11], "slot_index": 0}],
                "properties": {},
                "widgets_values": ["bus"],
            },
            {
                "id": 4,
                "type": "ConsumerNode",
                "pos": [660, 0],
                "size": [210, 58],
                "flags": {},
                "order": 3,
                "mode": 0,
                "inputs": [{"name": "image", "type": "IMAGE", "link": 11}],
                "outputs": [],
                "properties": {},
                "widgets_values": [],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "IMAGE"],
            [11, 3, 0, 4, 0, "IMAGE"],
        ],
    }


def _helper_subgraph_fixture() -> dict[str, object]:
    return {
        "nodes": [],
        "links": [],
        "definitions": {
            "subgraphs": [
                {
                    "name": "HelperGraph",
                    "state": {"lastNodeId": 3, "lastLinkId": 101},
                    "nodes": [
                        {
                            "id": 1,
                            "type": "SourceNode",
                            "pos": [0, 0],
                            "size": [210, 58],
                            "flags": {},
                            "order": 0,
                            "mode": 0,
                            "inputs": [],
                            "outputs": [{"name": "OUT", "type": "IMAGE", "links": [100], "slot_index": 0}],
                            "properties": {},
                            "widgets_values": [],
                        },
                        {
                            "id": 2,
                            "type": "Reroute",
                            "pos": [220, 0],
                            "size": [75, 26],
                            "flags": {},
                            "order": 1,
                            "mode": 0,
                            "inputs": [{"name": "", "type": "*", "link": 100}],
                            "outputs": [{"name": "", "type": "*", "links": [101], "slot_index": 0}],
                            "properties": {},
                            "widgets_values": [],
                        },
                        {
                            "id": 3,
                            "type": "ConsumerNode",
                            "pos": [360, 0],
                            "size": [210, 58],
                            "flags": {},
                            "order": 2,
                            "mode": 0,
                            "inputs": [{"name": "image", "type": "IMAGE", "link": 101}],
                            "outputs": [],
                            "properties": {},
                            "widgets_values": [],
                        },
                    ],
                    "links": [
                        {"id": 100, "origin_id": 1, "origin_slot": 0, "target_id": 2, "target_slot": 0, "type": "IMAGE"},
                        {"id": 101, "origin_id": 2, "origin_slot": 0, "target_id": 3, "target_slot": 0, "type": "IMAGE"},
                    ],
                }
            ]
        },
    }


def _normalized_root_nodes(ui: dict[str, object]) -> dict[int, dict[str, object]]:
    normalized = normalize_ui_json(ui)
    return {
        int(node["id"]): node
        for node in normalized.get("nodes", [])
        if isinstance(node, dict) and isinstance(node.get("id"), int)
    }


def _grouped_fixture() -> dict[str, object]:
    fixture = _fixture()
    fixture["groups"] = [
        {
            "title": "Outputs",
            "bounding": [1240.0, 160.0, 340.0, 220.0],
            "color": "#333333",
        }
    ]
    return fixture


def _node_rect(node: dict[str, object]) -> tuple[float, float, float, float]:
    pos = node.get("pos")
    size = node.get("size")
    assert isinstance(pos, list) and len(pos) >= 2
    assert isinstance(size, list) and len(size) >= 2
    return float(pos[0]), float(pos[1]), float(size[0]), float(size[1])


def _overlaps(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
    return not (
        left[0] + left[2] <= right[0]
        or right[0] + right[2] <= left[0]
        or left[1] + left[3] <= right[1]
        or right[1] + right[3] <= left[1]
    )


def test_resolve_delta_rejects_invalid_enum_without_mutating_original() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "5", "sampler_name"],
                "value": "not-a-real-sampler",
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=provider)

    assert result.ok is False
    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
    assert result.resolved_ops == ()
    assert original == before


def test_resolve_delta_rejects_known_incompatible_link_without_mutating_original() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "upsert_link",
                "from": ["", "1", "MODEL"],
                "to": ["", "5", "latent_image"],
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=provider)

    assert result.ok is False
    assert any(issue.code == "incompatible_socket_types" for issue in result.diagnostics)
    assert result.resolved_ops == ()
    assert original == before


def test_resolve_delta_rejects_unknown_add_node_class_before_any_mutation() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "TotallyUnknownNode",
                "fields": {"filename_prefix": "out/run"},
                "inputs": {},
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=provider)

    assert result.ok is False
    assert any(issue.code == "unknown_add_node_class_type" for issue in result.diagnostics)
    assert result.resolved_ops == ()
    assert original == before


def test_resolve_delta_rejects_add_node_out_of_range_field_before_any_mutation() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "KSampler",
                "fields": {"denoise": 1.5, "sampler_name": "euler"},
                "inputs": {},
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=provider)

    assert result.ok is False
    assert any(issue.code == "value_out_of_range" for issue in result.diagnostics)
    assert result.resolved_ops == ()
    assert original == before


def test_apply_delta_stops_before_mutation_for_invalid_delta() -> None:
    original = _fixture()
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "remove_link",
                "id": 999999,
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=provider)

    assert result.ok is False
    assert result.candidate is None
    assert result.mutation_started is False
    assert any(issue.code == "unknown_link_id" for issue in result.diagnostics)


def test_resolve_delta_accepts_mode_remove_node_and_link_endpoint_targets() -> None:
    original = _fixture()
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {"op": "set_mode", "target": ["", "5"], "mode": 4},
            {"op": "remove_node", "target": ["", "4"]},
            {"op": "remove_link", "to": ["", "5", "latent_image"]},
        ]
    )

    result = resolve_delta(original, delta, schema_provider=provider)

    assert result.ok is True
    assert len(result.resolved_ops) == 3
    assert not any(issue.severity == "error" for issue in result.diagnostics)


def test_apply_delta_resolves_earlier_ops_but_never_starts_mutation_when_later_op_fails() -> None:
    original = _fixture()
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {"op": "set_mode", "target": ["", "5"], "mode": 2},
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "TotallyUnknownNode",
                "fields": {},
                "inputs": {},
            },
        ]
    )

    result = apply_delta(original, delta, schema_provider=provider)

    assert result.ok is False
    assert result.candidate is None
    assert result.mutation_started is False
    assert len(result.resolved_ops) == 1
    assert any(issue.code == "unknown_add_node_class_type" for issue in result.diagnostics)


def test_apply_delta_sets_unlinked_widget_value_and_preserves_unrelated_nodes() -> None:
    original = _fixture()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "2", "text"],
                "value": "edited prompt text",
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=provider)

    assert result.ok is True
    assert result.candidate is not None
    assert result.mutation_started is True
    nodes_after = _normalized_root_nodes(result.candidate)
    nodes_before = _normalized_root_nodes(stamped_before)
    assert nodes_after[2]["widgets_values"] == ["edited prompt text"]
    for node_id, before in nodes_before.items():
        if node_id == 2:
            continue
        assert nodes_after[node_id] == before


def test_apply_delta_adds_node_with_ledger_ids_and_collision_nudging() -> None:
    original = _fixture()
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "SaveImage",
                "fields": {"filename_prefix": "agent-edit/new"},
                "inputs": {"images": ["", "6", "IMAGE"]},
                "anchor": {"relation": "right_of", "near": ["", "5"]},
            }
        ]
    )

    first = apply_delta(copy.deepcopy(original), delta, schema_provider=provider)
    second = apply_delta(copy.deepcopy(original), delta, schema_provider=provider)

    assert first.ok is True
    assert second.ok is True
    assert first.candidate is not None
    assert second.candidate is not None
    nodes_first = _normalized_root_nodes(first.candidate)
    nodes_second = _normalized_root_nodes(second.candidate)
    new_node = nodes_first[8]
    assert new_node["properties"]["vibecomfy_uid"] == "n1"
    assert new_node["widgets_values"] == ["agent-edit/new"]
    assert new_node["pos"] == nodes_second[8]["pos"]
    assert first.candidate["last_node_id"] == 8
    assert first.candidate["last_link_id"] > original["last_link_id"]
    assert any(issue.code == "add_node_applied" for issue in first.diagnostics)

    new_rect = _node_rect(new_node)
    for node_id, node in nodes_first.items():
        if node_id in {6, 8}:
            continue
        assert not _overlaps(new_rect, _node_rect(node))

    source_output = nodes_first[6]["outputs"][0]
    assert sorted(source_output["links"]) == [9, 10]


def test_apply_delta_resolves_node_added_earlier_in_same_delta() -> None:
    original = _fixture()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "CLIPTextEncode",
                "fields": {"text": "agent inserted"},
                "inputs": {"clip": ["", "1", "CLIP"]},
                "anchor": {"relation": "right_of", "near": ["", "1"]},
            },
            {
                "op": "upsert_link",
                "from": ["", "n1", "CONDITIONING"],
                "to": ["", "5", "positive"],
            },
        ]
    )

    resolved = resolve_delta(copy.deepcopy(original), delta, schema_provider=_SchemaProvider())
    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert resolved.ok is True
    assert result.ok is True
    assert result.candidate is not None
    assert [(type(op).__name__, type(resolved_op).__name__) for op, resolved_op in result.resolved_ops] == [
        ("AddNodeOp", "AppliedAddNodeSpec"),
        ("UpsertLinkOp", "tuple"),
    ]
    nodes_after = _normalized_root_nodes(result.candidate)
    nodes_before = _normalized_root_nodes(stamped_before)
    new_node = nodes_after[8]
    assert new_node["type"] == "CLIPTextEncode"
    assert new_node["properties"]["vibecomfy_uid"] == "n1"
    positive = next(slot for slot in nodes_after[5]["inputs"] if slot["name"] == "positive")
    new_link_id = positive["link"]
    assert [link for link in result.candidate["links"] if link[0] == new_link_id] == [
        [new_link_id, 8, 0, 5, 1, "CONDITIONING"]
    ]
    for node_id, before in nodes_before.items():
        if node_id in {1, 2, 5}:
            continue
        assert nodes_after[node_id] == before


def test_apply_delta_keeps_unknown_intra_delta_node_target_as_clean_failure() -> None:
    original = _fixture()
    before = copy.deepcopy(original)
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "CLIPTextEncode",
                "fields": {"text": "agent inserted"},
                "inputs": {"clip": ["", "1", "CLIP"]},
                "anchor": {"relation": "right_of", "near": ["", "1"]},
            },
            {
                "op": "upsert_link",
                "from": ["", "n2", "CONDITIONING"],
                "to": ["", "5", "positive"],
            },
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is False
    assert result.candidate is None
    assert result.mutation_started is False
    assert len(result.resolved_ops) == 1
    assert any(issue.code == "unknown_node_target" and issue.detail.get("uid") == "n2" for issue in result.diagnostics)
    assert original == before


def test_apply_delta_resolves_runexx_image_scale_added_then_wired_same_delta() -> None:
    workflow_path = Path("/tmp/runexx-ltx23/LTX-2.3_-_I2V_T2V_Basic.json")
    if not workflow_path.exists():
        pytest.skip("RuneXX LTX-2.3 fixture is not present at /tmp/runexx-ltx23")
    original = json.loads(workflow_path.read_text(encoding="utf-8"))
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "ImageScaleBy",
                "fields": {"upscale_method": "lanczos", "scale_by": 2.0},
                "inputs": {"image": ["", "127", "IMAGE"]},
                "anchor": {"relation": "right_of", "near": ["", "127"]},
            },
            {
                "op": "upsert_link",
                "from": ["", "n1", "IMAGE"],
                "to": ["", "140", "images"],
            },
        ]
    )

    result = apply_delta(original, delta, schema_provider=_RuneXXSchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    nodes_after = _normalized_root_nodes(result.candidate)
    nodes_before = _normalized_root_nodes(stamped_before)
    new_node_id = max(nodes_after)
    new_node = nodes_after[new_node_id]
    assert new_node["type"] == "ImageScaleBy"
    assert new_node["properties"]["vibecomfy_uid"] == "n1"
    saver = nodes_after[140]
    images_input = next(slot for slot in saver["inputs"] if slot["name"] == "images")
    new_link_id = images_input["link"]
    assert any(link == [new_link_id, new_node_id, 0, 140, 0, "IMAGE"] for link in result.candidate["links"])
    for node_id, before in nodes_before.items():
        if node_id in {127, 140}:
            continue
        assert nodes_after[node_id] == before


def test_apply_delta_adds_node_with_group_growth_attribution() -> None:
    original = _grouped_fixture()
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "SaveImage",
                "fields": {"filename_prefix": "agent-edit/grouped"},
                "inputs": {"images": ["", "6", "IMAGE"]},
                "anchor": {"relation": "right_of", "near": ["", "6"], "group_title": "Outputs"},
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=provider)

    assert result.ok is True
    assert result.candidate is not None
    groups = result.candidate["groups"]
    assert isinstance(groups, list) and len(groups) == 1
    assert groups[0]["bounding"][2] > original["groups"][0]["bounding"][2]
    assert any(issue.code == "add_node_group_growth" for issue in result.diagnostics)


def test_resolve_delta_rejects_unknown_add_node_group_anchor() -> None:
    original = _fixture()
    provider = _SchemaProvider()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "SaveImage",
                "fields": {"filename_prefix": "agent-edit/new"},
                "inputs": {"images": ["", "6", "IMAGE"]},
                "anchor": {"relation": "near", "group_title": "Missing Group"},
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=provider)

    assert result.ok is False
    assert any(issue.code == "unknown_group_anchor" for issue in result.diagnostics)


def test_apply_delta_auto_unlinks_schema_less_linked_widget_and_records_diagnostics() -> None:
    original = {
        "last_node_id": 2,
        "last_link_id": 1,
        "nodes": [
            {
                "id": 1,
                "type": "PrimitiveInt",
                "pos": [0, 0],
                "size": [210, 58],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "value", "type": "INT", "links": [1], "slot_index": 0}],
                "properties": {},
                "widgets_values": [7],
            },
            {
                "id": 2,
                "type": "UnknownWidgetNode",
                "pos": [240, 0],
                "size": [210, 58],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [{"name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": 1}],
                "outputs": [],
                "properties": {},
                "widgets_values": [],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "INT"]],
    }
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "2", "seed"],
                "value": 99,
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert {issue.code for issue in result.diagnostics} >= {
        "automatic_link_removal",
        "schema_less_linked_widget_recovery",
    }
    target = next(node for node in result.candidate["nodes"] if node["id"] == 2)
    source = next(node for node in result.candidate["nodes"] if node["id"] == 1)
    assert target["inputs"] == []
    assert target["widgets_values"] == [99]
    assert result.candidate["links"] == []
    assert source["outputs"][0]["links"] == []


def test_apply_delta_sets_schema_less_dict_widget_without_changing_other_nodes() -> None:
    original = {
        "last_node_id": 2,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "VAEDecodeTiled",
                "pos": [0, 0],
                "size": [210, 58],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
                "properties": {},
                "widgets_values": [],
            },
            {
                "id": 2,
                "type": "VHS_VideoCombine",
                "pos": [240, 0],
                "size": [315, 270],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE"}],
                "outputs": [{"name": "Filenames", "type": "VHS_FILENAMES", "links": None, "slot_index": 0}],
                "properties": {},
                "widgets_values": {
                    "frame_rate": 24,
                    "filename_prefix": "LTX-2",
                    "format": "video/h264-mp4",
                    "crf": 19,
                },
            },
        ],
        "links": [],
    }
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "2", "filename_prefix"],
                "value": "qa_run",
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=_RuneXXSchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    target = next(node for node in result.candidate["nodes"] if node["id"] == 2)
    assert target["widgets_values"] == {
        "frame_rate": 24,
        "filename_prefix": "qa_run",
        "format": "video/h264-mp4",
        "crf": 19,
    }
    before_nodes = _normalized_root_nodes(stamped_before)
    after_nodes = _normalized_root_nodes(result.candidate)
    assert after_nodes[1] == before_nodes[1]


def test_apply_delta_unlinks_widget_input_and_sets_dict_widget_value() -> None:
    original = {
        "last_node_id": 5,
        "last_link_id": 98,
        "nodes": [
            {
                "id": 1,
                "type": "PrimitiveInt",
                "pos": [0, 0],
                "size": [210, 58],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "value", "type": "INT", "links": [98], "slot_index": 0}],
                "properties": {},
                "widgets_values": [7],
            },
            {
                "id": 5,
                "type": "VHS_VideoCombine",
                "pos": [240, 0],
                "size": [315, 270],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [
                    {"name": "images", "type": "IMAGE", "link": None},
                    {"name": "frame_rate", "type": "FLOAT", "widget": {"name": "frame_rate"}, "link": 98},
                ],
                "outputs": [],
                "properties": {},
                "widgets_values": {
                    "frame_rate": 24,
                    "filename_prefix": "LTX-2",
                    "format": "video/h264-mp4",
                },
            },
        ],
        "links": [[98, 1, 0, 5, 1, "FLOAT"]],
    }
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "5", "frame_rate"],
                "value": 30,
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=_RuneXXSchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert {issue.code for issue in result.diagnostics} >= {"automatic_link_removal"}
    source = next(node for node in result.candidate["nodes"] if node["id"] == 1)
    target = next(node for node in result.candidate["nodes"] if node["id"] == 5)
    assert source["outputs"][0]["links"] == []
    assert target["inputs"] == [{"name": "images", "type": "IMAGE", "link": None}]
    assert target["widgets_values"] == {
        "frame_rate": 30,
        "filename_prefix": "LTX-2",
        "format": "video/h264-mp4",
    }
    assert result.candidate["links"] == []


def test_resolve_delta_rejects_unknown_dict_widget_field() -> None:
    original = {
        "nodes": [
            {
                "id": 5,
                "type": "VHS_VideoCombine",
                "pos": [240, 0],
                "size": [315, 270],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [{"name": "images", "type": "IMAGE", "link": None}],
                "outputs": [],
                "properties": {},
                "widgets_values": {"filename_prefix": "LTX-2"},
            },
        ],
        "links": [],
    }
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "5", "totally_not_a_field"],
                "value": 123,
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=_RuneXXSchemaProvider())

    assert result.ok is False
    assert any(issue.code == "unknown_node_field" for issue in result.diagnostics)


def test_apply_delta_set_mode_only_changes_target_node() -> None:
    original = _fixture()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta([{"op": "set_mode", "target": ["", "5"], "mode": 4}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    nodes_after = _normalized_root_nodes(result.candidate)
    nodes_before = _normalized_root_nodes(stamped_before)
    assert nodes_after[5]["mode"] == 4
    for node_id, before in nodes_before.items():
        if node_id == 5:
            continue
        assert nodes_after[node_id] == before


def test_apply_delta_remove_link_updates_root_array_links_and_node_references() -> None:
    original = _fixture()
    delta = parse_edit_delta([{"op": "remove_link", "to": ["", "5", "latent_image"]}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    ksampler = next(node for node in result.candidate["nodes"] if node["id"] == 5)
    latent_source = next(node for node in result.candidate["nodes"] if node["id"] == 4)
    assert all(link[0] != 7 for link in result.candidate["links"])
    latent_input = next(slot for slot in ksampler["inputs"] if slot["name"] == "latent_image")
    assert latent_input["link"] is None
    assert latent_source["outputs"][0]["links"] == []


def test_apply_delta_remove_link_updates_subgraph_dict_links_and_node_references() -> None:
    original = _fixture("subgraphed_wan_i2v.json")
    ledger = EditLedger.ingest(original)
    scope_path = next(scope.scope_path for scope in ledger.scopes.values() if scope.kind == "subgraph")
    delta = parse_edit_delta([{"op": "remove_link", "id": 181}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    subgraph = next(
        scope
        for scope in (result.candidate.get("definitions") or {}).get("subgraphs", [])
        if scope.get("name") == "Image to Video (Wan 2.2)"
    )
    node_105 = next(node for node in subgraph["nodes"] if node["id"] == 105)
    node_107 = next(node for node in subgraph["nodes"] if node["id"] == 107)
    assert all(link["id"] != 181 for link in subgraph["links"])
    assert node_105["outputs"][0]["links"] == [178]
    clip_input = next(slot for slot in node_107["inputs"] if slot["name"] == "clip")
    assert clip_input["link"] is None
    assert scope_path  # stamped resolution context exists for the subgraph fixture


def test_apply_delta_remove_node_cascades_connected_root_links_and_reports_cleanup() -> None:
    original = _fixture()
    delta = parse_edit_delta([{"op": "remove_node", "target": ["", "6"]}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    remaining_ids = {node["id"] for node in result.candidate["nodes"]}
    assert 6 not in remaining_ids
    assert all(link[0] not in {4, 8, 9} for link in result.candidate["links"])
    checkpoint = next(node for node in result.candidate["nodes"] if node["id"] == 1)
    sampler = next(node for node in result.candidate["nodes"] if node["id"] == 5)
    sink = next(node for node in result.candidate["nodes"] if node["id"] == 7)
    assert checkpoint["outputs"][2]["links"] == []
    assert sampler["outputs"][0]["links"] == []
    image_input = next(slot for slot in sink["inputs"] if slot["name"] == "images")
    assert image_input["link"] is None
    cleanup_link_ids = {issue.detail["link_id"] for issue in result.diagnostics if issue.code == "remove_node_link_cleanup"}
    assert cleanup_link_ids == {4, 8, 9}


def test_apply_delta_remove_node_cascades_connected_subgraph_dict_links_and_reports_cleanup() -> None:
    original = _fixture("subgraphed_wan_i2v.json")
    ledger = EditLedger.ingest(original)
    scope_path = next(scope.scope_path for scope in ledger.scopes.values() if scope.kind == "subgraph")
    delta = parse_edit_delta([{"op": "remove_node", "target": [scope_path, "124"]}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    subgraph = next(
        scope
        for scope in (result.candidate.get("definitions") or {}).get("subgraphs", [])
        if scope.get("name") == "Image to Video (Wan 2.2)"
    )
    remaining_ids = {node["id"] for node in subgraph["nodes"]}
    assert 124 not in remaining_ids
    assert all(link["id"] not in {189, 192} for link in subgraph["links"])
    node_127 = next(node for node in subgraph["nodes"] if node["id"] == 127)
    node_111 = next(node for node in subgraph["nodes"] if node["id"] == 111)
    assert node_127["outputs"][0]["links"] == []
    model_input = next(slot for slot in node_111["inputs"] if slot["name"] == "model")
    assert model_input["link"] is None
    cleanup_link_ids = {issue.detail["link_id"] for issue in result.diagnostics if issue.code == "remove_node_link_cleanup"}
    assert cleanup_link_ids == {189, 192}


def test_apply_delta_remove_node_restitches_root_getnode_passthrough() -> None:
    original = _helper_root_fixture()
    delta = parse_edit_delta([{"op": "remove_node", "target": ["", "3"]}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    remaining_ids = {node["id"] for node in result.candidate["nodes"]}
    assert 3 not in remaining_ids
    assert result.candidate["links"] == [[10, 1, 0, 2, 0, "IMAGE"], [11, 1, 0, 4, 0, "IMAGE"]]
    source = next(node for node in result.candidate["nodes"] if node["id"] == 1)
    consumer = next(node for node in result.candidate["nodes"] if node["id"] == 4)
    assert sorted(source["outputs"][0]["links"]) == [10, 11]
    image_input = next(slot for slot in consumer["inputs"] if slot["name"] == "image")
    assert image_input["link"] == 11
    assert any(issue.code == "remove_node_passthrough_rewire" for issue in result.diagnostics)


def test_apply_delta_remove_node_restitches_root_setnode_passthrough() -> None:
    original = _helper_root_fixture()
    delta = parse_edit_delta([{"op": "remove_node", "target": ["", "2"]}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    remaining_ids = {node["id"] for node in result.candidate["nodes"]}
    assert 2 not in remaining_ids
    assert result.candidate["links"] == [[11, 1, 0, 4, 0, "IMAGE"]]
    source = next(node for node in result.candidate["nodes"] if node["id"] == 1)
    get_node = next(node for node in result.candidate["nodes"] if node["id"] == 3)
    assert source["outputs"][0]["links"] == [11]
    assert get_node["outputs"][0]["links"] == []
    assert any(issue.code == "remove_node_passthrough_rewire" for issue in result.diagnostics)
    cleanup_link_ids = {issue.detail["link_id"] for issue in result.diagnostics if issue.code == "remove_node_link_cleanup"}
    assert cleanup_link_ids == {10}


def test_apply_delta_remove_node_restitches_subgraph_reroute_passthrough() -> None:
    original = _helper_subgraph_fixture()
    ledger = EditLedger.ingest(original)
    scope_path = next(scope.scope_path for scope in ledger.scopes.values() if scope.kind == "subgraph")
    delta = parse_edit_delta([{"op": "remove_node", "target": [scope_path, "2"]}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    subgraph = result.candidate["definitions"]["subgraphs"][0]
    remaining_ids = {node["id"] for node in subgraph["nodes"]}
    assert 2 not in remaining_ids
    assert subgraph["links"] == [
        {"id": 101, "origin_id": 1, "origin_slot": 0, "target_id": 3, "target_slot": 0, "type": "IMAGE"}
    ]
    source = next(node for node in subgraph["nodes"] if node["id"] == 1)
    consumer = next(node for node in subgraph["nodes"] if node["id"] == 3)
    assert source["outputs"][0]["links"] == [101]
    image_input = next(slot for slot in consumer["inputs"] if slot["name"] == "image")
    assert image_input["link"] == 101
    assert any(issue.code == "remove_node_passthrough_rewire" for issue in result.diagnostics)
    cleanup_link_ids = {issue.detail["link_id"] for issue in result.diagnostics if issue.code == "remove_node_link_cleanup"}
    assert cleanup_link_ids == {100}


def test_resolve_delta_rejects_helper_fan_in_remove_node() -> None:
    original = _helper_root_fixture()
    original["nodes"].insert(
        1,
        {
            "id": 5,
            "type": "SourceNode",
            "pos": [0, 100],
            "size": [210, 58],
            "flags": {},
            "order": 1,
            "mode": 0,
            "inputs": [],
            "outputs": [{"name": "OUT", "type": "IMAGE", "links": [12], "slot_index": 0}],
            "properties": {},
            "widgets_values": [],
        },
    )
    original["links"].append([12, 5, 0, 2, 0, "IMAGE"])
    delta = parse_edit_delta([{"op": "remove_node", "target": ["", "2"]}])

    result = resolve_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is False
    assert any(issue.code == "remove_node_helper_fan_in_unsupported" for issue in result.diagnostics)


def test_apply_delta_reorders_unlinked_widget_values_only() -> None:
    original = {
        "last_node_id": 1,
        "last_link_id": 0,
        "nodes": [
            {
                "id": 1,
                "type": "UnknownWidgetNode",
                "pos": [0, 0],
                "size": [210, 58],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [
                    {"name": "first", "type": "STRING", "widget": {"name": "first"}, "link": None},
                    {"name": "second", "type": "STRING", "widget": {"name": "second"}, "link": None},
                ],
                "outputs": [],
                "properties": {},
                "widgets_values": ["one", "two"],
            }
        ],
        "links": [],
    }
    delta = parse_edit_delta(
        [
            {
                "op": "reorder",
                "target": ["", "1"],
                "axis": "widgets",
                "order": ["second", "first"],
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    node = result.candidate["nodes"][0]
    assert node["widgets_values"] == ["two", "one"]
    assert node["inputs"] == original["nodes"][0]["inputs"]
    assert any(issue.code == "reorder_widgets_applied" for issue in result.diagnostics)


def test_resolve_delta_rejects_linked_widget_reorder() -> None:
    original = {
        "last_node_id": 2,
        "last_link_id": 1,
        "nodes": [
            {
                "id": 1,
                "type": "PrimitiveString",
                "pos": [0, 0],
                "size": [210, 58],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "value", "type": "STRING", "links": [1], "slot_index": 0}],
                "properties": {},
                "widgets_values": ["source"],
            },
            {
                "id": 2,
                "type": "UnknownWidgetNode",
                "pos": [240, 0],
                "size": [210, 58],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [
                    {"name": "first", "type": "STRING", "widget": {"name": "first"}, "link": 1},
                    {"name": "second", "type": "STRING", "widget": {"name": "second"}, "link": None},
                ],
                "outputs": [],
                "properties": {},
                "widgets_values": ["one", "two"],
            },
        ],
        "links": [[1, 1, 0, 2, 0, "STRING"]],
    }
    delta = parse_edit_delta(
        [
            {
                "op": "reorder",
                "target": ["", "2"],
                "axis": "widgets",
                "order": ["second", "first"],
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is False
    assert any(issue.code == "unsupported_reorder_form" for issue in result.diagnostics)


def test_apply_delta_upsert_link_replaces_existing_root_link_and_advances_counter() -> None:
    original = _fixture()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [
            {
                "op": "upsert_link",
                "from": ["", "3", "CONDITIONING"],
                "to": ["", "5", "positive"],
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert result.candidate["last_link_id"] == 10
    assert [link for link in result.candidate["links"] if link[0] == 5] == []
    assert [link for link in result.candidate["links"] if link[0] == 10] == [[10, 3, 0, 5, 1, "CONDITIONING"]]
    node_2 = next(node for node in result.candidate["nodes"] if node["id"] == 2)
    node_3 = next(node for node in result.candidate["nodes"] if node["id"] == 3)
    node_5 = next(node for node in result.candidate["nodes"] if node["id"] == 5)
    assert node_2["outputs"][0]["links"] == []
    assert sorted(node_3["outputs"][0]["links"]) == [6, 10]
    positive = next(slot for slot in node_5["inputs"] if slot["name"] == "positive")
    assert positive["link"] == 10
    nodes_after = _normalized_root_nodes(result.candidate)
    nodes_before = _normalized_root_nodes(stamped_before)
    for node_id, before in nodes_before.items():
        if node_id in {2, 3, 5}:
            continue
        assert nodes_after[node_id] == before
    assert any(issue.code == "upsert_link_replaced_existing" for issue in result.diagnostics)


def test_resolve_delta_rejects_structural_slot_reorder() -> None:
    original = _fixture()
    delta = parse_edit_delta(
        [
            {
                "op": "reorder",
                "target": ["", "1"],
                "axis": "slots",
                "order": ["VAE", "CLIP", "MODEL"],
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is False
    assert result.candidate is None
    assert result.mutation_started is False
    assert any(issue.code == "unsupported_reorder_form" for issue in result.diagnostics)


def test_apply_delta_upsert_link_handles_subgraph_dict_links_and_advances_counter() -> None:
    original = _helper_subgraph_fixture()
    ledger = EditLedger.ingest(original)
    scope_path = next(scope.scope_path for scope in ledger.scopes.values() if scope.kind == "subgraph")
    delta = parse_edit_delta(
        [
            {
                "op": "upsert_link",
                "from": [scope_path, "1", "OUT"],
                "to": [scope_path, "3", "image"],
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    subgraph = result.candidate["definitions"]["subgraphs"][0]
    assert subgraph["state"]["lastLinkId"] == 102
    assert all(link["id"] != 101 for link in subgraph["links"])
    assert any(
        link == {"id": 102, "origin_id": 1, "origin_slot": 0, "target_id": 3, "target_slot": 0, "type": "IMAGE"}
        for link in subgraph["links"]
    )
    source = next(node for node in subgraph["nodes"] if node["id"] == 1)
    consumer = next(node for node in subgraph["nodes"] if node["id"] == 3)
    assert sorted(source["outputs"][0]["links"]) == [100, 102]
    image_input = next(slot for slot in consumer["inputs"] if slot["name"] == "image")
    assert image_input["link"] == 102
    assert any(issue.code == "upsert_link_replaced_existing" for issue in result.diagnostics)


def test_guard_full_ui_rejects_unattributed_link_churn_in_touched_scope() -> None:
    original = _fixture()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [
            {
                "op": "upsert_link",
                "from": ["", "3", "CONDITIONING"],
                "to": ["", "5", "positive"],
            }
        ]
    )
    applied = apply_delta(original, delta, schema_provider=_SchemaProvider())
    assert applied.ok is True
    assert applied.candidate is not None

    candidate = copy.deepcopy(applied.candidate)
    candidate["links"].append([999, 1, 0, 7, 0, "IMAGE"])

    result = guard_full_ui(stamped_before, candidate, applied.resolved_ops)

    assert result.ok is False
    assert any(issue.code == "full_ui_link_added_unattributed" for issue in result.diagnostics)


def test_guard_full_ui_rejects_unattributed_extra_change_on_op_touched_node() -> None:
    original = _fixture()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [
            {
                "op": "upsert_link",
                "from": ["", "3", "CONDITIONING"],
                "to": ["", "5", "positive"],
            }
        ]
    )
    applied = apply_delta(original, delta, schema_provider=_SchemaProvider())
    assert applied.ok is True
    assert applied.candidate is not None

    candidate = copy.deepcopy(applied.candidate)
    sampler = next(node for node in candidate["nodes"] if node["id"] == 5)
    sampler["pos"] = [999, 999]

    result = guard_full_ui(stamped_before, candidate, applied.resolved_ops)

    assert result.ok is False
    assert any(issue.code == "full_ui_node_changed_unattributed" for issue in result.diagnostics)


def test_guard_full_ui_rejects_unattributed_node_change() -> None:
    original = EditLedger.ingest(_fixture()).stamped_copy()
    candidate = copy.deepcopy(original)
    candidate["nodes"][3]["pos"] = [999, 999]

    result = guard_full_ui(original, candidate, ())

    assert result.ok is False
    assert any(issue.code == "full_ui_node_changed_unattributed" for issue in result.diagnostics)


def test_guard_full_ui_allows_counter_advancement_but_rejects_regression() -> None:
    original = EditLedger.ingest(_fixture()).stamped_copy()
    advanced = copy.deepcopy(original)
    advanced["last_link_id"] = int(advanced["last_link_id"]) + 1
    advanced["last_node_id"] = int(advanced["last_node_id"]) + 1

    allowed = guard_full_ui(original, advanced, ())

    assert allowed.ok is True

    regressed = copy.deepcopy(original)
    regressed["last_link_id"] = int(regressed["last_link_id"]) - 1
    rejected = guard_full_ui(original, regressed, ())

    assert rejected.ok is False
    assert any(issue.code == "full_ui_counter_changed_unattributed" for issue in rejected.diagnostics)


def test_guard_full_ui_uses_fallback_allow_list_only_for_exact_measured_paths(monkeypatch) -> None:
    import vibecomfy.porting.edit.normalize as normalize_support

    original = EditLedger.ingest(_fixture()).stamped_copy()
    candidate = copy.deepcopy(original)
    candidate["nodes"][1]["properties"]["Node name for S&R"] = "CLIPTextEncode normalized"
    monkeypatch.setattr(
        normalize_support,
        "NORMALIZE_ALLOW_LIST",
        [
            {
                "node_class": "CLIPTextEncode",
                "field_path": "properties.Node name for S&R",
                "reason": "test-only measured fallback path",
                "fixture": "flat.json",
                "expiration": "2026-07-01",
            }
        ],
    )

    allowed = guard_full_ui(original, candidate, (), normalize_timeout_ms=0)

    assert allowed.ok is True
    assert any(issue.code == "full_ui_normalize_allow_list_used" for issue in allowed.diagnostics)

    candidate["nodes"][1]["pos"] = [123, 456]
    rejected = guard_full_ui(original, candidate, (), normalize_timeout_ms=0)

    assert rejected.ok is False
    assert any(issue.code == "full_ui_node_changed_unattributed" for issue in rejected.diagnostics)
