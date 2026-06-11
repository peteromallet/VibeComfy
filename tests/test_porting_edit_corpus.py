from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from vibecomfy.porting.edit.apply import apply_delta
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
                inputs={
                    "text": InputSpec(type="STRING", required=True),
                    "clip": InputSpec(type="CLIP", required=True),
                },
                outputs=[OutputSpec(type="CONDITIONING", name="CONDITIONING")],
            ),
            "EmptyLatentImage": NodeSchema(
                class_type="EmptyLatentImage",
                pack="core",
                inputs={
                    "width": InputSpec(type="INT", min=16, max=8192),
                    "height": InputSpec(type="INT", min=16, max=8192),
                    "batch_size": InputSpec(type="INT", min=1, max=64),
                },
                outputs=[OutputSpec(type="LATENT", name="LATENT")],
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
            "VAEDecode": NodeSchema(
                class_type="VAEDecode",
                pack="core",
                inputs={
                    "samples": InputSpec(type="LATENT", required=True),
                    "vae": InputSpec(type="VAE", required=True),
                },
                outputs=[OutputSpec(type="IMAGE", name="IMAGE")],
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
            "PrimitiveInt": NodeSchema(
                class_type="PrimitiveInt",
                pack="core",
                inputs={"value": InputSpec(type="INT")},
                outputs=[OutputSpec(type="INT", name="value")],
            ),
        }

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((Path("tests/fixtures/agent_edit") / name).read_text(encoding="utf-8"))


def _scope_path_by_name(ui: Mapping[str, Any], name: str) -> str:
    ledger = EditLedger.ingest(ui)
    for scope in ledger.scopes.values():
        if scope.kind == "subgraph" and scope.graph.get("name") == name:
            return scope.scope_path
    raise AssertionError(f"missing subgraph scope {name!r}")


def _nodes_by_scope_and_uid(ui: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    normalized = normalize_ui_json(ui)
    ledger = EditLedger.ingest(normalized)
    return {
        (scope_path, uid): copy.deepcopy(node)
        for (scope_path, uid), node in ledger.node_index.items()
    }


def _assert_preserves_out_of_delta_nodes(
    before_ui: Mapping[str, Any],
    after_ui: Mapping[str, Any],
    *,
    touched: set[tuple[str, str]],
) -> None:
    before_nodes = _nodes_by_scope_and_uid(before_ui)
    after_nodes = _nodes_by_scope_and_uid(after_ui)
    for key, before_node in before_nodes.items():
        if key in touched:
            continue
        assert after_nodes[key] == before_node


def _node(ui: Mapping[str, Any], node_id: int) -> dict[str, Any]:
    return next(node for node in ui["nodes"] if node["id"] == node_id)


def _subgraph_node(ui: Mapping[str, Any], scope_name: str, node_id: int) -> dict[str, Any]:
    subgraphs = ui.get("definitions", {}).get("subgraphs", [])
    scope = next(scope for scope in subgraphs if scope.get("name") == scope_name)
    return next(node for node in scope["nodes"] if node["id"] == node_id)


def _flat_with_linked_seed() -> dict[str, Any]:
    ui = _fixture("flat.json")
    ui["last_node_id"] = 8
    ui["last_link_id"] = 10
    ui["nodes"].append(
        {
            "id": 8,
            "type": "PrimitiveInt",
            "pos": [740, -220],
            "size": [210, 58],
            "flags": {},
            "order": 7,
            "mode": 0,
            "inputs": [],
            "outputs": [{"name": "value", "type": "INT", "links": [10], "slot_index": 0}],
            "properties": {},
            "widgets_values": [7],
        }
    )
    sampler = _node(ui, 5)
    sampler["widgets_values"] = []
    sampler["inputs"].append({"name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": 10})
    ui["links"].append([10, 8, 0, 5, 4, "INT"])
    return ui


def _flat_with_reroute_before_save() -> dict[str, Any]:
    ui = _fixture("flat.json")
    ui["last_node_id"] = 8
    decode = _node(ui, 6)
    save = _node(ui, 7)
    decode["outputs"][0]["links"] = [9]
    image_input = next(slot for slot in save["inputs"] if slot["name"] == "images")
    image_input["link"] = 11
    ui["nodes"].insert(
        6,
        {
            "id": 8,
            "type": "Reroute",
            "pos": [1120, 246],
            "size": [75, 26],
            "flags": {},
            "order": 6,
            "mode": 0,
            "inputs": [{"name": "", "type": "*", "link": 9}],
            "outputs": [{"name": "", "type": "*", "links": [11], "slot_index": 0}],
            "properties": {},
            "widgets_values": [],
        },
    )
    ui["links"] = [link for link in ui["links"] if link[0] != 9]
    ui["links"].extend([[9, 6, 0, 8, 0, "IMAGE"], [11, 8, 0, 7, 0, "IMAGE"]])
    ui["last_link_id"] = 11
    return ui


def test_edit_corpus_prompt_set_preserves_flat_fixture_nodes() -> None:
    original = _fixture("flat.json")
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "2", "text"], "value": "a faithful edited prompt"}]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert _node(result.candidate, 2)["widgets_values"] == ["a faithful edited prompt"]
    _assert_preserves_out_of_delta_nodes(stamped_before, result.candidate, touched={("", "2")})


def test_edit_corpus_seed_auto_unlink_preserves_flat_fixture_nodes() -> None:
    original = _flat_with_linked_seed()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta([{"op": "set_node_field", "target": ["", "5", "seed"], "value": 12345}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    sampler = _node(result.candidate, 5)
    seed_input = next((slot for slot in sampler["inputs"] if slot["name"] == "seed"), None)
    assert seed_input is None
    assert sampler["widgets_values"][0] == 12345
    assert all(link[0] != 10 for link in result.candidate["links"])
    assert _node(result.candidate, 8)["outputs"][0]["links"] == []
    assert any(issue.code == "automatic_link_removal" for issue in result.diagnostics)
    _assert_preserves_out_of_delta_nodes(stamped_before, result.candidate, touched={("", "5"), ("", "8")})


def test_edit_corpus_add_node_and_upsert_link_script_preserves_flat_fixture_nodes() -> None:
    original = _fixture("flat.json")
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta(
        [
            {
                "op": "add_node",
                "scope_path": "",
                "class_type": "SaveImage",
                "fields": {"filename_prefix": "agent-edit/corpus"},
                "inputs": {"images": ["", "6", "IMAGE"]},
                "anchor": {"relation": "right_of", "near": ["", "6"]},
            },
            {"op": "upsert_link", "from": ["", "3", "CONDITIONING"], "to": ["", "5", "positive"]},
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert _node(result.candidate, 8)["type"] == "SaveImage"
    assert _node(result.candidate, 8)["widgets_values"] == ["agent-edit/corpus"]
    sampler_positive = next(slot for slot in _node(result.candidate, 5)["inputs"] if slot["name"] == "positive")
    assert sampler_positive["link"] == 11
    assert any(issue.code == "add_node_applied" for issue in result.diagnostics)
    assert any(issue.code == "upsert_link_replaced_existing" for issue in result.diagnostics)
    _assert_preserves_out_of_delta_nodes(
        stamped_before,
        result.candidate,
        touched={("", "2"), ("", "3"), ("", "5"), ("", "6")},
    )


def test_edit_corpus_remove_reroute_restitches_flat_fixture_links() -> None:
    original = _flat_with_reroute_before_save()
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta([{"op": "remove_node", "target": ["", "8"]}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert {node["id"] for node in result.candidate["nodes"]} == {1, 2, 3, 4, 5, 6, 7}
    assert [link for link in result.candidate["links"] if link[0] == 11] == [[11, 6, 0, 7, 0, "IMAGE"]]
    assert _node(result.candidate, 6)["outputs"][0]["links"] == [11]
    assert next(slot for slot in _node(result.candidate, 7)["inputs"] if slot["name"] == "images")["link"] == 11
    assert any(issue.code == "remove_node_passthrough_rewire" for issue in result.diagnostics)
    _assert_preserves_out_of_delta_nodes(stamped_before, result.candidate, touched={("", "6"), ("", "7"), ("", "8")})


def test_edit_corpus_set_mode_bypass_preserves_flat_fixture_nodes() -> None:
    original = _fixture("flat.json")
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta([{"op": "set_mode", "target": ["", "5"], "mode": 4}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert _node(result.candidate, 5)["mode"] == 4
    _assert_preserves_out_of_delta_nodes(stamped_before, result.candidate, touched={("", "5")})


def test_edit_corpus_subgraph_internal_edit_preserves_available_fixture_nodes() -> None:
    original = _fixture("subgraphed_wan_i2v.json")
    scope_path = _scope_path_by_name(original, "Image to Video (Wan 2.2)")
    stamped_before = EditLedger.ingest(original).stamped_copy()
    delta = parse_edit_delta([{"op": "set_mode", "target": [scope_path, "110"], "mode": 2}])

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is True
    assert result.candidate is not None
    assert _subgraph_node(result.candidate, "Image to Video (Wan 2.2)", 110)["mode"] == 2
    _assert_preserves_out_of_delta_nodes(stamped_before, result.candidate, touched={(scope_path, "110")})


def test_edit_corpus_multi_turn_re_edit_preserves_flat_fixture_nodes_each_turn() -> None:
    original = _fixture("flat.json")
    first_before = EditLedger.ingest(original).stamped_copy()
    first_delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "2", "text"], "value": "first edit"}]
    )

    first = apply_delta(original, first_delta, schema_provider=_SchemaProvider())

    assert first.ok is True
    assert first.candidate is not None
    _assert_preserves_out_of_delta_nodes(first_before, first.candidate, touched={("", "2")})

    second_before = EditLedger.ingest(first.candidate).stamped_copy()
    second_delta = parse_edit_delta(
        [{"op": "set_node_field", "target": ["", "2", "text"], "value": "second edit"}]
    )

    second = apply_delta(first.candidate, second_delta, schema_provider=_SchemaProvider())

    assert second.ok is True
    assert second.candidate is not None
    assert _node(second.candidate, 2)["widgets_values"] == ["second edit"]
    _assert_preserves_out_of_delta_nodes(second_before, second.candidate, touched={("", "2")})


@pytest.mark.parametrize(
    ("raw_delta", "expected_code"),
    [
        (
            [{"op": "set_node_field", "target": ["", "5", "sampler_name"], "value": "not-real"}],
            "value_not_in_enum",
        ),
        (
            [{"op": "set_node_field", "target": ["", "5", "steps"], "value": 1000}],
            "value_out_of_range",
        ),
        (
            [{"op": "set_node_field", "target": ["", "5", "steps"], "value": "twenty"}],
            "value_type_mismatch",
        ),
        (
            [{"op": "upsert_link", "from": ["", "1", "MODEL"], "to": ["", "5", "latent_image"]}],
            "incompatible_socket_types",
        ),
    ],
)
def test_edit_corpus_rejects_invalid_scripted_ops_atomically(
    raw_delta: list[dict[str, Any]],
    expected_code: str,
) -> None:
    original = _fixture("flat.json")
    before = copy.deepcopy(original)

    result = apply_delta(original, parse_edit_delta(raw_delta), schema_provider=_SchemaProvider())

    assert result.ok is False
    assert result.candidate is None
    assert result.mutation_started is False
    assert original == before
    assert any(issue.code == expected_code for issue in result.diagnostics)


def test_edit_corpus_later_rejection_keeps_earlier_successful_op_atomic() -> None:
    original = _fixture("flat.json")
    before = copy.deepcopy(original)
    delta = parse_edit_delta(
        [
            {"op": "set_node_field", "target": ["", "2", "text"], "value": "should not apply"},
            {"op": "set_node_field", "target": ["", "5", "sampler_name"], "value": "not-real"},
        ]
    )

    result = apply_delta(original, delta, schema_provider=_SchemaProvider())

    assert result.ok is False
    assert result.candidate is None
    assert result.mutation_started is False
    assert original == before
    assert any(issue.code == "value_not_in_enum" for issue in result.diagnostics)
