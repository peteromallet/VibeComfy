from __future__ import annotations

import json

from vibecomfy.porting.emit.ui import emit_ui_json, materialize_litegraph_node
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _wf() -> VibeWorkflow:
    return VibeWorkflow("materialize-test", WorkflowSource("materialize-test"))


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
    metadata = {"_ui": {"pos": pos, "size": [320, 180]}}
    control = merged_fields.pop("control_after_generate", None)
    if isinstance(control, str):
        metadata["control_after_generate"] = control
    wf.nodes["1"] = VibeNode("1", class_type, inputs=merged_fields, metadata=metadata, uid=uid)
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
