from __future__ import annotations

import json
import copy

import pytest

from vibecomfy.porting.emit.ui import emit_ui_json, materialize_litegraph_node
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import WorkflowBundleError, materialize_ui_json


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _wf() -> VibeWorkflow:
    return VibeWorkflow("materialize-test", WorkflowSource("materialize-test"))


def _connected_sidecar(wf: VibeWorkflow) -> dict[str, object]:
    return {
        "format_version": 1,
        "bind": {"workflow_identity": wf.id, "semantic_digest": wf.semantic_digest()},
        "nodes": {
            "source": {"id": 41, "pos": [11, 12], "size": [210, 120], "collapsed": True, "color": "#abc", "title": "Source title", "z_order": 8},
            "target": {"id": 42, "pos": [311, 12], "size": [220, 130]},
        },
        "links": [{"edge_ref": {"scope_path": "", "from_uid": "source", "from_port": 0, "to_uid": "target", "to_port": 0}, "occurrence_index": 0, "id": 77}],
        "groups": [],
        "canvas": {"zoom": 1.25, "pan": [9, 10]},
    }


def _connected_wf() -> VibeWorkflow:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "Source", uid="source", native_output_names=["out"])
    wf.nodes["2"] = VibeNode("2", "Target", uid="target", native_input_names=["in"])
    from vibecomfy.workflow import VibeEdge
    wf.edges.append(VibeEdge("1", "0", "2", "in"))
    return wf


def test_bundle_materialize_validates_before_emitter(monkeypatch: pytest.MonkeyPatch) -> None:
    wf = _connected_wf()
    sidecar = _connected_sidecar(wf)
    sidecar["unknown"] = True

    def sentinel(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("emitter must not run for an invalid sidecar")

    monkeypatch.setattr("vibecomfy.porting.emit.ui.emit_ui_json", sentinel)
    with pytest.raises(WorkflowBundleError, match="unknown field"):
        materialize_ui_json(wf, sidecar)


def test_materialize_present_and_missing_sidecar_skip_legacy_reconcile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wf = _connected_wf()
    sidecar = _connected_sidecar(wf)

    def sentinel(*args: object, **kwargs: object) -> object:
        raise AssertionError("legacy reconcile must not run during canonical materialization")

    monkeypatch.setattr("vibecomfy.porting.layout.reconcile.reconcile", sentinel)
    assert materialize_ui_json(wf, sidecar)["links"]
    assert materialize_ui_json(wf)["links"]


@pytest.mark.parametrize("missing", ["workflow_identity", "semantic_digest"])
def test_materialize_requires_complete_bind_before_emitter(
    missing: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    wf = _connected_wf()
    sidecar = _connected_sidecar(wf)
    del sidecar["bind"][missing]  # type: ignore[index]

    def sentinel(*args: object, **kwargs: object) -> object:
        raise AssertionError("emitter must not run for incomplete bind")

    monkeypatch.setattr("vibecomfy.porting.emit.ui.emit_ui_json", sentinel)
    with pytest.raises(WorkflowBundleError, match="bind"):
        materialize_ui_json(wf, sidecar)


def test_presentation_materialization_keeps_semantics_and_changes_only_ui_bytes() -> None:
    wf = _connected_wf()
    sidecar = _connected_sidecar(wf)
    first = materialize_ui_json(wf, sidecar)
    semantic_before = wf.semantic_digest()
    api_before = copy.deepcopy(wf.compile("api"))

    edited = copy.deepcopy(sidecar)
    edited["nodes"]["source"]["pos"] = [99, 101]  # type: ignore[index]
    edited["canvas"]["zoom"] = 2.0  # type: ignore[index]
    edited["bind"]["semantic_digest"] = wf.semantic_digest()  # type: ignore[index]
    second = materialize_ui_json(wf, edited)

    assert wf.semantic_digest() == semantic_before
    assert wf.compile("api") == api_before
    assert first["nodes"][0]["pos"] != second["nodes"][0]["pos"]
    assert first["extra"]["ds"] != second["extra"]["ds"]
    assert first["nodes"][0]["type"] == second["nodes"][0]["type"] == "Source"
    assert first["links"] == second["links"]


def test_nodes_only_sidecar_keeps_python_edges() -> None:
    wf = _connected_wf()
    sidecar = _connected_sidecar(wf)
    sidecar["links"] = []
    result = materialize_ui_json(wf, sidecar)
    assert len(result["links"]) == 1
    assert result["links"][0][1:5] == [41, 0, 42, 0]


def test_materialize_preserves_allowlisted_furniture_groups_and_occurrences() -> None:
    wf = _connected_wf()
    sidecar = _connected_sidecar(wf)
    sidecar["nodes"]["source"]["group"] = "g"  # type: ignore[index]
    sidecar["groups"] = [{  # type: ignore[assignment]
        "scope_path": "", "presentation_id": "g", "bounds": [1, 2, 300, 200],
        "title": "Presentation group", "color": "#123456", "z_order": 4,
    }]
    ref = sidecar["links"][0]["edge_ref"]  # type: ignore[index]
    sidecar["links"] = [  # type: ignore[assignment]
        {"edge_ref": ref, "occurrence_index": 0, "id": 77, "reroute": [[1, 2]]},
        {"edge_ref": ref, "occurrence_index": 1, "id": 78, "reroute": [[3, 4]]},
    ]

    result = materialize_ui_json(wf, sidecar)
    source = next(node for node in result["nodes"] if node["id"] == 41)
    assert source["pos"] == [11.0, 12.0]
    assert source["size"] == [210.0, 120.0]
    assert source["flags"]["collapsed"] is True
    assert source["color"] == "#abc"
    assert source["title"] == "Source title"
    assert source["order"] == 8
    assert source["group"] == "g"
    assert result["groups"] == [{
        "id": "g", "vibecomfy_group_id": "g", "nodes": [41],
        "bounding": [1.0, 2.0, 300.0, 200.0], "title": "Presentation group",
        "color": "#123456", "order": 4,
    }]
    assert result["links"] == [
        [77, 41, 0, 42, 0, "", [[1, 2]]],
        [78, 41, 0, 42, 0, "", [[3, 4]]],
    ]


def test_materialize_uses_native_roster_holes_for_named_edges() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1", "RosterSource", uid="source",
        native_output_names=["first", None, "third"],
    )
    wf.nodes["2"] = VibeNode(
        "2", "RosterTarget", uid="target", native_input_names=["value"],
    )
    from vibecomfy.workflow import VibeEdge
    wf.edges.append(VibeEdge("1", "third", "2", "value"))
    sidecar = {
        "format_version": 1,
        "bind": {"workflow_identity": wf.id, "semantic_digest": wf.semantic_digest()},
        "nodes": {"source": {"id": 11}, "target": {"id": 22}},
        "links": [{"edge_ref": {
            "scope_path": "", "from_uid": "source", "from_port": 2,
            "to_uid": "target", "to_port": 0,
        }, "occurrence_index": 0, "id": 33}],
        "groups": [], "canvas": {},
    }
    result = materialize_ui_json(wf, sidecar)
    source = next(node for node in result["nodes"] if node["id"] == 11)
    assert [slot["name"] for slot in source["outputs"]] == ["first", "output_1", "third"]
    assert result["links"] == [[33, 11, 2, 22, 0, ""]]


def test_materialize_repeats_deterministically_without_raw_evidence() -> None:
    wf = _connected_wf()
    wf.metadata["_ui_door"] = {"nodes": [{"id": 1, "type": "WrongType", "pos": [999, 999]}]}
    wf.nodes["1"].metadata["_ui"] = {"pos": [888, 888], "title": "Wrong title"}
    sidecar = _connected_sidecar(wf)
    semantic_before = wf.semantic_digest()
    first = materialize_ui_json(wf, sidecar)
    second = materialize_ui_json(wf, copy.deepcopy(sidecar))
    assert first == second
    assert wf.semantic_digest() == semantic_before
    assert first["nodes"][0]["type"] == "Source"
    assert first["nodes"][0]["pos"] == [11.0, 12.0]


def test_materialize_depth_two_virtual_leg_uses_structural_scope() -> None:
    from vibecomfy.identity.scope import compose_scope_path, sg_key
    from vibecomfy.identity.uid import make_uid

    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "Container", uid="root")
    inner = {
        "name": "inner",
        "nodes": [
            {"id": 10, "uid": "left", "class_type": "A"},
            {"id": 20, "uid": "right", "class_type": "B"},
        ],
        "links": [{"id": 1, "origin_id": 10, "origin_slot": 0,
                    "target_id": 20, "target_slot": 0, "type": "X"}],
        "virtual_wires": {"bus": {"legs": [{
            "origin_id": 10, "origin_slot": 0, "target_id": 20, "target_slot": 0,
        }]}},
    }
    outer = {"name": "outer", "nodes": [], "links": [], "definitions": {"subgraphs": [inner]}}
    wf.definitions = {"subgraphs": [outer]}
    wf.metadata["definitions"] = {"subgraphs": [{"name": "RAW_WRONG", "nodes": [], "links": []}]}
    scope = compose_scope_path((sg_key(outer), sg_key(inner)))
    ref = {"scope_path": scope, "name": "bus", "leg_index": 0}
    root_group = {"scope_path": "", "presentation_id": "shared", "bounds": [1, 2, 300, 200], "title": "Root group"}
    nested_group = {"scope_path": scope, "presentation_id": "shared", "bounds": [11, 12, 130, 140], "title": "Nested group"}
    sidecar = {
        "format_version": 1,
        "bind": {"workflow_identity": wf.id, "semantic_digest": wf.semantic_digest()},
        "nodes": {
            "root": {"id": 5, "group": "shared"},
            make_uid(scope, "left"): {"id": 77},
            make_uid(scope, "right"): {"id": 88, "group": "shared"},
        },
        "links": [{"virtual_wire_ref": ref, "occurrence_index": 0, "id": 91}],
        "groups": [root_group, nested_group], "canvas": {},
    }
    result = materialize_ui_json(wf, sidecar)
    nested = result["definitions"]["subgraphs"][0]["definitions"]["subgraphs"][0]
    assert result["groups"] == [{
        "id": "shared", "vibecomfy_group_id": "shared", "nodes": [5],
        "bounding": [1.0, 2.0, 300.0, 200.0], "title": "Root group",
    }]
    assert nested["groups"] == [{
        "id": "shared", "vibecomfy_group_id": "shared", "nodes": [88],
        "bounding": [11.0, 12.0, 130.0, 140.0], "title": "Nested group",
    }]
    assert nested["links"][0]["id"] == 91
    assert [node["id"] for node in nested["nodes"]] == [77, 88]
    assert nested["links"][0]["origin_id"] == 77
    assert nested["links"][0]["target_id"] == 88
    assert "RAW_WRONG" not in repr(result["definitions"])

    without_link_overlay = copy.deepcopy(sidecar)
    without_link_overlay["links"] = []
    python_only = materialize_ui_json(wf, without_link_overlay)
    python_nested = python_only["definitions"]["subgraphs"][0]["definitions"]["subgraphs"][0]
    assert len(python_nested["links"]) == 1
    assert python_nested["links"][0]["origin_id"] == 77
    assert python_nested["links"][0]["target_id"] == 88

    collision = copy.deepcopy(sidecar)
    collision["nodes"][make_uid(scope, "left")]["id"] = 20  # type: ignore[index]
    with pytest.raises(ValueError, match="nested node id collision"):
        materialize_ui_json(wf, collision)


def test_materialize_emits_root_python_virtual_legs_without_sidecar_links() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1", "Source", uid="source", native_output_names=["out"],
    )
    wf.nodes["2"] = VibeNode(
        "2", "Target", uid="target", native_input_names=["value"],
    )
    wf.virtual_wires = {"bus": {"legs": [{
        "from_uid": "source", "from_port": 0,
        "to_uid": "target", "to_port": 0,
    }]}}
    sidecar = {
        "format_version": 1,
        "bind": {"workflow_identity": wf.id, "semantic_digest": wf.semantic_digest()},
        "nodes": {"source": {"id": 51}, "target": {"id": 52}},
        "links": [], "groups": [], "canvas": {},
    }
    result = materialize_ui_json(wf, sidecar)
    assert result["links"] == [[1, 51, 0, 52, 0, ""]]


def _single_node_fixture(
    *,
    class_type: str,
    schema: NodeSchema,
    fields: dict[str, object],
    uid: str,
    pos: list[float],
) -> dict[str, object]:
    wf = _wf()
    merged_fields = {
        name: spec.default
        for name, spec in schema.inputs.items()
        if spec.default is not None
    }
    merged_fields.update(fields)
    metadata = {}
    control = merged_fields.pop("control_after_generate", None)
    if isinstance(control, str):
        metadata["control_after_generate"] = control
    wf.nodes["1"] = VibeNode(
        "1", class_type, inputs=merged_fields, metadata=metadata, uid=uid,
        pos=pos, size=[320, 180],
    )
    return emit_ui_json(wf, schema_provider=_Provider({class_type: schema}))["nodes"][0]


def test_materialize_checkpoint_loader_matches_single_node_emit() -> None:
    schema = NodeSchema(
        class_type="CheckpointLoaderSimple",
        pack=None,
        inputs={"ckpt_name": InputSpec("STRING", default="dreamshaper.safetensors")},
        outputs=[
            OutputSpec("MODEL", "MODEL"),
            OutputSpec("CLIP", "CLIP"),
            OutputSpec("VAE", "VAE"),
        ],
        source_provider="object_info",
    )
    fields = {"ckpt_name": "realvis.safetensors"}
    pos = [111.0, 222.0]
    expected = _single_node_fixture(
        class_type="CheckpointLoaderSimple",
        schema=schema,
        fields=fields,
        uid="uid-loader",
        pos=pos,
    )

    assert (
        materialize_litegraph_node(
            "CheckpointLoaderSimple",
            fields,
            schema,
            1,
            "uid-loader",
            pos,
        )
        == expected
    )


def test_materialize_ksampler_matches_single_node_emit() -> None:
    schema = NodeSchema(
        class_type="KSampler",
        pack=None,
        inputs={
            "seed": InputSpec("INT", default=5),
            "steps": InputSpec("INT", default=20),
            "cfg": InputSpec("FLOAT", default=7.0),
            "sampler_name": InputSpec("STRING", default="euler"),
            "scheduler": InputSpec("STRING", default="normal"),
            "denoise": InputSpec("FLOAT", default=1.0),
        },
        outputs=[OutputSpec("LATENT", "LATENT")],
        source_provider="object_info",
    )
    fields = {"seed": 123, "control_after_generate": "increment"}
    pos = [10.0, 20.0]
    expected = _single_node_fixture(
        class_type="KSampler",
        schema=schema,
        fields=fields,
        uid="uid-ksampler",
        pos=pos,
    )

    assert materialize_litegraph_node("KSampler", fields, schema, 7, "uid-ksampler", pos) == {
        **expected,
        "id": 7,
    }


def test_materialize_save_image_matches_single_node_emit() -> None:
    schema = NodeSchema(
        class_type="SaveImage",
        pack=None,
        inputs={
            "images": InputSpec("IMAGE"),
            "filename_prefix": InputSpec("STRING", default="ComfyUI"),
        },
        outputs=[],
        source_provider="object_info",
    )
    fields = {"filename_prefix": "agent-edit/output"}
    pos = [300.0, 450.0]
    expected = _single_node_fixture(
        class_type="SaveImage",
        schema=schema,
        fields=fields,
        uid="uid-save",
        pos=pos,
    )

    materialized = materialize_litegraph_node("SaveImage", fields, schema, 9, "uid-save", pos)
    assert materialized["inputs"] == [{"name": "images", "type": "IMAGE", "link": None}]
    assert {key: materialized[key] for key in materialized if key != "inputs"} == {
        key: value for key, value in {**expected, "id": 9}.items() if key != "inputs"
    }


def test_materialize_exec_uses_stringified_io_instead_of_generic_schema_pool() -> None:
    schema = NodeSchema(
        class_type="vibecomfy.exec",
        pack="vibecomfy",
        inputs={
            "source": InputSpec("STRING", required=True),
            "io": InputSpec("JSON", required=True),
            **{f"in_{index}": InputSpec("*", required=False) for index in range(16)},
        },
        outputs=[OutputSpec("*", f"out_{index}") for index in range(16)],
        source_provider="vibecomfy_builtin",
    )
    io_spec = {"inputs": [["image", "IMAGE"]], "outputs": [["image", "IMAGE"]]}

    node = materialize_litegraph_node(
        "vibecomfy.exec",
        {
            "source": "image = in_0",
            "io": json.dumps(io_spec),
        },
        schema,
        11,
        "uid-exec",
        [10.0, 20.0],
    )

    assert node["inputs"] == [{"name": "in_0", "label": "image: IMAGE", "type": "IMAGE"}]
    assert node["outputs"] == [
        {"name": "out_0", "label": "image: IMAGE", "type": "IMAGE", "links": None, "slot_index": 0}
    ]
    assert len(node["inputs"]) == 1
    assert len(node["outputs"]) == 1
    assert node["properties"]["vibecomfy"]["io"] == io_spec


def test_materialize_preserves_intervening_defaults_for_later_explicit_widget() -> None:
    schema = NodeSchema(
        class_type="WanLikeLoraSelect",
        pack=None,
        inputs={
            "lora": InputSpec("STRING", required=True),
            "strength": InputSpec("FLOAT", default=1.0),
            "low_mem_load": InputSpec("BOOLEAN", default=False),
            "merge_loras": InputSpec("BOOLEAN", default=True),
        },
        outputs=[],
        source_provider="object_info_index",
    )

    node = materialize_litegraph_node(
        schema.class_type,
        {
            "lora": "model.safetensors",
            "merge_loras": False,
        },
        schema,
        22,
        "uid-later-widget",
        [0.0, 0.0],
    )

    assert node["widgets_values"] == [
        "model.safetensors",
        1.0,
        False,
        False,
    ]
