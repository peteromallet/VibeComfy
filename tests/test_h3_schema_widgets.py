import json
from pathlib import Path

import pytest

from vibecomfy._compile._widgets import WIDGET_SCHEMA
from vibecomfy.ingest.normalize import from_api
from vibecomfy.schema.provider import AuthoringSchemaProvider, NodeSchema
from vibecomfy.schema.types import InputSpec
from vibecomfy.schema.validate import validate_api_against_schema


class _Provider:
    def __init__(self, schemas):
        self.schemas = schemas

    def get_schema(self, class_type):
        return self.schemas.get(class_type)


def test_model_attention_backend_offline_schema_has_pinned_source_provenance():
    provider = AuthoringSchemaProvider(on_demand_schemas=False)
    schema = provider.get_schema("ModelAttentionBackend")
    assert schema is not None
    assert schema.source_provider == "object_info_index"
    assert schema.source_package == "comfy_core"
    assert schema.source_version == "zz-official-ee71d5c4"
    assert set(schema.inputs) == {"model", "attention"}
    assert schema.inputs["model"] == InputSpec("MODEL", required=True)
    assert schema.inputs["attention"].choices == ["pytorch attention", "comfy kitchen attention"]
    assert schema.inputs["attention"].default == "pytorch attention"
    assert [(output.name, output.type) for output in schema.outputs] == [("model", "MODEL")]
    assert schema.widget_input_order == ("attention",)

    path = Path(schema.source_cache_path)
    raw = json.loads(path.read_text())["ModelAttentionBackend"]
    provenance = json.loads((path.parent / "provenance.json").read_text())["packs"][path.name]
    assert raw["source_commit"] == provenance["locked_commit"] == "ee71d5c4993f29086b27fde1629a945ae48425bf"
    assert raw["source_sha256"] == provenance["schema_sha256"] == "59bcf2c72de0f931383b74c9be5b6fc2ced06a315277d34631ae5ac9ac90fa91"
    assert provenance["source_kind"] == "official_pinned_source"


def test_unknown_class_still_fails_offline_schema_validation():
    provider = AuthoringSchemaProvider(on_demand_schemas=False)
    assert provider.get_schema("UnknownH3AttentionBackend") is None
    issues = validate_api_against_schema(
        {"988": {"class_type": "UnknownH3AttentionBackend", "inputs": {}}}, provider,
    )
    assert [(issue.code, issue.severity) for issue in issues] == [("unknown_class_type", "error")]


@pytest.mark.parametrize("attention", ["pytorch attention", "comfy kitchen attention"])
def test_h3_model_patch_chain_resolves_attention_backend(attention):
    provider = AuthoringSchemaProvider(on_demand_schemas=False)
    # The H3 continuation fixture patches the diffusion model before sampling.
    api = {
        "1": {"class_type": "UNETLoader", "inputs": {
            "unet_name": "flux1-dev.safetensors", "weight_dtype": "default",
        }},
        "988": {"class_type": "ModelAttentionBackend", "inputs": {
            "model": ["1", 0], "attention": attention,
        }},
        "5": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["988", 0], "shift": 3.0}},
    }
    workflow = from_api(api, workflow_id="h3-model-patch", schema_provider=provider)
    report = workflow.validate(schema_provider=provider)
    assert report.ok, report.issues


def test_h3_widget_slots_preserve_core_and_lanpaint_values():
    assert WIDGET_SCHEMA["ResolutionSelector"] == ["aspect_ratio", "megapixels", "multiple"]
    assert WIDGET_SCHEMA["LanPaint_SamplerCustomAdvanced"][-1] is None
    assert WIDGET_SCHEMA["ComfyMathExpression"] == ["expression"]


def test_comfy_math_expression_accepts_autogrow_dotted_values():
    provider = _Provider(
        {
            "ComfyMathExpression": NodeSchema(
                class_type="ComfyMathExpression",
                pack="comfy_core",
                inputs={
                    "expression": InputSpec("STRING", required=True),
                    "values": InputSpec("COMFY_AUTOGROW_V3", required=True),
                },
                outputs=[],
            )
        }
    )
    issues = validate_api_against_schema(
        {
            "107": {
                "class_type": "ComfyMathExpression",
                "inputs": {
                    "expression": "a * 2",
                    "values.a": ["115", 1],
                },
            }
        },
        provider,
    )
    assert not [issue for issue in issues if issue.severity == "error"]


def test_generic_comfy_autogrow_accepts_dotted_reference_sockets():
    provider = _Provider(
        {
            "MiniMaxH3ReferenceToVideo": NodeSchema(
                class_type="MiniMaxH3ReferenceToVideo",
                pack="comfy_core",
                inputs={
                    "ref_images": InputSpec("COMFY_AUTOGROW_V3"),
                },
                outputs=[],
            )
        }
    )
    issues = validate_api_against_schema(
        {
            "973": {
                "class_type": "MiniMaxH3ReferenceToVideo",
                "inputs": {
                    "ref_images.ref_image_0": ["1020", 0],
                    "ref_images.ref_image_1": ["1021", 0],
                },
            }
        },
        provider,
    )
    assert not [issue for issue in issues if issue.severity == "error"]
