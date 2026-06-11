from __future__ import annotations

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

    assert materialize_litegraph_node("SaveImage", fields, schema, 9, "uid-save", pos) == {
        **expected,
        "id": 9,
    }
