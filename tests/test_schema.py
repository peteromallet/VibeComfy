from __future__ import annotations

import asyncio
import json

import pytest

from vibecomfy.ingest.normalize import (
    _merge_slim_ui,
    convert_to_vibe_format,
    normalize_to_api,
    _schema_input_aliases,
    _schema_output_names,
    _schema_output_types,
    _schema_source_provenance,
)
from vibecomfy.schema import (
    InputSpec,
    ConversionSchemaProvider,
    LocalSchemaProvider,
    NodeSchema,
    ObjectInfoSchemaProvider,
    OutputSpec,
    RuntimeSchemaProvider,
    SchemaIndexError,
    SourceSchemaProvider,
    get_authoring_schema_provider,
    get_schema_provider,
    schema_for,
    schema_registry_empty,
    schemas_for,
    socket_types_compatible,
    validate_node_call,
)
from vibecomfy.schema.cache import load_object_info_cache
from vibecomfy.workflow import ValidationIssue, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class FakeSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self.schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schemas.get(class_type)


class LegacyGetSchemaProvider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def test_authoring_schema_provider_prefers_committed_object_info_when_node_index_empty(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")

    provider = get_authoring_schema_provider()

    assert provider.get_schema("KSampler").source_provider == "object_info_index"
    assert provider.get_schema("SaveImage").source_provider == "object_info_index"


def test_authoring_schema_provider_prefers_committed_object_info_when_node_index_stale(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "node_index.json").write_text(
        json.dumps([
            {"class_type": "KSampler", "inputs": {"bogus": "STRING"}, "outputs": ["IMAGE"]},
            {"class_type": "SaveImage", "inputs": {"bogus": "STRING"}, "outputs": []},
        ]),
        encoding="utf-8",
    )

    provider = get_authoring_schema_provider()
    ksampler = provider.get_schema("KSampler")
    save_image = provider.get_schema("SaveImage")

    assert ksampler.source_provider == "object_info_index"
    assert "latent_image" in ksampler.inputs
    assert "bogus" not in ksampler.inputs
    assert save_image.source_provider == "object_info_index"
    assert "images" in save_image.inputs


def test_authoring_schema_provider_prefers_committed_object_info_when_node_index_incomplete(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "node_index.json").write_text(
        json.dumps([{"class_type": "KSampler", "inputs": {"seed": "INT"}, "outputs": []}]),
        encoding="utf-8",
    )

    provider = get_authoring_schema_provider()

    assert provider.get_schema("KSampler").source_provider == "object_info_index"
    assert provider.get_schema("SaveImage").source_provider == "object_info_index"


def test_socket_types_compatible_public_helper_preserves_validation_semantics() -> None:
    assert socket_types_compatible("LATENT", "LATENT") is True
    assert socket_types_compatible("ANY", "IMAGE") is True
    assert socket_types_compatible("*", "IMAGE") is True
    assert socket_types_compatible(None, "IMAGE") is True
    assert socket_types_compatible("IMAGE", "LATENT") is False


def test_validate_node_call_reports_structured_primitive_errors() -> None:
    provider = FakeSchemaProvider(
        {
            "PrimitiveNode": NodeSchema(
                class_type="PrimitiveNode",
                pack=None,
                inputs={
                    "required_text": InputSpec("STRING", required=True),
                    "mode": InputSpec("CHOICE", choices=["a", "b"]),
                    "steps": InputSpec("INT", min=1, max=4),
                    "enabled": InputSpec("BOOLEAN"),
                },
                outputs=[],
            )
        }
    )

    report = validate_node_call(
        "PrimitiveNode",
        {"mode": "c", "steps": 9, "enabled": "yes", "extra": True},
        provider,
    )

    assert report.ok is False
    by_code = {issue.code: issue for issue in report.issues}
    assert by_code["missing_required_input"].input == "required_text"
    assert by_code["unknown_input"].input == "extra"
    assert by_code["value_not_in_enum"].detail["choices"] == ["a", "b"]
    assert by_code["value_out_of_range"].detail["max"] == 4
    assert by_code["primitive_type_mismatch"].detail["expected"] == "bool"


def _workflow(*nodes: VibeNode, edges: list[VibeEdge] | None = None) -> VibeWorkflow:
    workflow = VibeWorkflow("schema-test", WorkflowSource("schema-test"))
    workflow.nodes = {node.id: node for node in nodes}
    workflow.edges = edges or []
    return workflow


def _schema(
    class_type: str,
    *,
    inputs: dict[str, InputSpec] | None = None,
    outputs: list[OutputSpec] | None = None,
) -> NodeSchema:
    return NodeSchema(class_type=class_type, pack=None, inputs=inputs or {}, outputs=outputs or [])


def _only_issue(workflow: VibeWorkflow, provider: FakeSchemaProvider) -> ValidationIssue:
    report = workflow.validate(schema_provider=provider)
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert isinstance(issue, ValidationIssue)
    return issue


def test_schema_validation_reports_unknown_class_type() -> None:
    issue = _only_issue(_workflow(VibeNode("1", "MissingNode")), FakeSchemaProvider({}))

    assert issue.code == "unknown_class_type"
    assert issue.severity == "error"


def test_schema_validation_reports_missing_required_input() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", inputs={"text": InputSpec("STRING", required=True)})})
    issue = _only_issue(_workflow(VibeNode("1", "PromptNode")), provider)

    assert issue.code == "missing_required_input"
    assert issue.severity == "error"
    assert "text" in issue.message


def test_schema_validation_allows_missing_required_input_with_default() -> None:
    provider = FakeSchemaProvider(
        {"PromptNode": _schema("PromptNode", inputs={"text": InputSpec("STRING", required=True, default="")})}
    )
    report = _workflow(VibeNode("1", "PromptNode")).validate(schema_provider=provider)

    assert report.ok
    assert report.issues == []


def test_schema_validation_reports_unknown_input() -> None:
    provider = FakeSchemaProvider({"PromptNode": _schema("PromptNode", inputs={"text": InputSpec("STRING")})})
    issue = _only_issue(_workflow(VibeNode("1", "PromptNode", inputs={"extra": "value"})), provider)

    assert issue.code == "unknown_input"
    assert issue.severity == "error"


def test_schema_validation_reports_type_mismatch_as_warning() -> None:
    provider = FakeSchemaProvider(
        {
            "ImageSource": _schema("ImageSource", outputs=[OutputSpec("IMAGE", "image")]),
            "LatentSink": _schema("LatentSink", inputs={"latent": InputSpec("LATENT", required=True)}),
        }
    )
    workflow = _workflow(
        VibeNode("1", "ImageSource"),
        VibeNode("2", "LatentSink"),
        edges=[VibeEdge("1", "0", "2", "latent")],
    )
    issue = _only_issue(workflow, provider)

    assert issue.code == "type_mismatch"
    assert issue.severity == "warning"


def test_schema_validation_reports_invalid_output_index_as_error() -> None:
    provider = FakeSchemaProvider(
        {
            "TwoOutputSource": _schema("TwoOutputSource", outputs=[OutputSpec("LATENT"), OutputSpec("AUDIO")]),
            "LatentSink": _schema("LatentSink", inputs={"latent": InputSpec("LATENT", required=True)}),
        }
    )
    workflow = _workflow(
        VibeNode("1", "TwoOutputSource"),
        VibeNode("2", "LatentSink"),
        edges=[VibeEdge("1", "2", "2", "latent")],
    )
    issue = _only_issue(workflow, provider)

    assert issue.code == "invalid_output_index"
    assert issue.severity == "error"
    assert issue.detail["output_count"] == 2


def test_validate_without_schema_provider_remains_structural_only() -> None:
    workflow = _workflow(
        VibeNode("1", "CLIPTextEncode", inputs={"text": "old"}),
        VibeNode("2", "KSampler", inputs={"seed": 1, "steps": 4}),
        VibeNode("3", "SaveImage"),
        edges=[VibeEdge("1", "0", "2", "positive"), VibeEdge("2", "0", "3", "images")],
    )

    report = workflow.validate()
    explicit_none_report = workflow.validate(schema_provider=None)

    assert report.ok
    assert explicit_none_report.ok
    assert report.issues == explicit_none_report.issues == []


def test_normalize_to_api_maps_widgets_to_schema_input_names() -> None:
    provider = FakeSchemaProvider(
        {
            "PromptNode": _schema(
                "PromptNode",
                inputs={
                    "text": InputSpec("STRING"),
                    "clip": InputSpec("CLIP"),
                    "ckpt_name": InputSpec("STRING"),
                },
            )
        }
    )
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "PromptNode",
                "widgets_values": ["hello", "model.safetensors"],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw, schema_provider=provider)

    assert api["1"]["inputs"] == {"text": "hello", "ckpt_name": "model.safetensors"}


def test_normalize_to_api_uses_widget_only_schema_so_link_inputs_do_not_shift_positions() -> None:
    provider = FakeSchemaProvider(
        {
            "CheckpointLoaderSimple": _schema(
                "CheckpointLoaderSimple",
                inputs={
                    "model": InputSpec("MODEL"),
                    "clip": InputSpec("CLIP"),
                    "ckpt_name": InputSpec("STRING"),
                },
            )
        }
    )
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "widgets_values": ["model.safetensors"],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw, schema_provider=provider)

    assert api["1"]["inputs"] == {"ckpt_name": "model.safetensors"}


def test_normalize_to_api_preserves_ui_only_widget_slots_from_static_schema() -> None:
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "widgets_values": [123, "randomize", 30, 6, "uni_pc", "simple", 1],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw)

    assert api["1"]["inputs"] == {
        "seed": 123,
        "unused_widget_1": "randomize",
        "steps": 30,
        "cfg": 6,
        "sampler_name": "uni_pc",
        "scheduler": "simple",
        "denoise": 1,
    }


def test_normalize_to_api_without_schema_provider_preserves_widget_keys() -> None:
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "PromptNode",
                "widgets_values": ["hello", "clip-ref", "model.safetensors"],
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw)

    assert api["1"]["inputs"] == {
        "widget_0": "hello",
        "widget_1": "clip-ref",
        "widget_2": "model.safetensors",
    }


def test_normalize_to_api_preserves_dict_widget_values() -> None:
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "VHS_LoadVideo",
                "widgets_values": {
                    "video": "motion.mp4",
                    "force_rate": 16,
                    "custom_width": 832,
                    "custom_height": 480,
                    "save_output": True,
                },
                "inputs": [
                    {"name": "custom_width", "link": 1},
                ],
            },
            {"id": 2, "type": "INTConstant", "widgets_values": [512], "inputs": []},
        ],
        "links": [[1, 2, 0, 1, 0, "INT"]],
    }

    api = normalize_to_api(raw)

    assert api["1"]["inputs"]["video"] == "motion.mp4"
    assert api["1"]["inputs"]["force_rate"] == 16
    assert api["1"]["inputs"]["custom_width"] == ["2", 0]
    assert api["1"]["inputs"]["custom_height"] == 480
    assert api["1"]["inputs"]["save_output"] is True


def test_normalize_to_api_preserves_raw_widget_payload_for_mixed_rows() -> None:
    rows = [
        {"lora": "detail.safetensors", "strength": 0.45},
        "enabled",
        {"lora": "style.safetensors", "strength": 0.2},
    ]
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "DynamicRowsForRawWidgetTest",
                "widgets_values": rows,
                "inputs": [],
            }
        ],
        "links": [],
    }

    api = normalize_to_api(raw)

    assert api["1"]["_raw_widgets"] == {
        "values": rows,
        "shape": "list",
        "source": "ui.widgets_values",
        "has_dict_rows": True,
        "length": 3,
    }
    assert api["1"]["_ui"]["widgets_values"] == rows


def test_convert_to_vibe_format_carries_raw_widgets_without_compile_leak() -> None:
    rows = [{"lora": "detail.safetensors", "strength": 0.45}, "enabled"]
    wf = convert_to_vibe_format(
        {
            "nodes": [
                {
                    "id": 1,
                    "type": "DynamicRowsForRawWidgetTest",
                    "widgets_values": rows,
                    "inputs": [],
                }
            ],
            "links": [],
        }
    )

    node = wf.nodes["1"]
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == rows
    assert node.raw_widgets.shape == "list"
    assert node.raw_widgets.source == "ui.widgets_values"
    assert node.raw_widgets.has_dict_rows is True
    assert node.raw_widgets.length == 2
    assert node.metadata["_ui"]["widgets_values"] == rows
    assert "_raw_widgets" not in node.metadata
    assert wf.compile("api") == {
        "1": {
            "class_type": "DynamicRowsForRawWidgetTest",
            "inputs": {
                "widget_0": {"lora": "detail.safetensors", "strength": 0.45},
                "widget_1": "enabled",
            },
        }
    }


def test_convert_to_vibe_format_static_compile_unchanged_with_raw_widgets() -> None:
    api = {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 123,
                "steps": 30,
                "cfg": 6,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "denoise": 1,
            },
            "_ui": {
                "id": 1,
                "type": "KSampler",
                "widgets_values": [123, "randomize", 30, 6, "uni_pc", "simple", 1],
                "inputs": [],
            },
        }
    }

    wf = convert_to_vibe_format(api)

    assert wf.nodes["1"].raw_widgets is not None
    assert wf.nodes["1"].raw_widgets.length == 7
    assert wf.compile("api") == {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 123,
                "steps": 30,
                "cfg": 6,
                "sampler_name": "uni_pc",
                "scheduler": "simple",
                "denoise": 1,
            },
        }
    }


def test_merge_slim_ui_retains_widgets_values_and_raw_payload() -> None:
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "DynamicRows",
                "pos": [10, 20],
                "size": [300, 100],
                "properties": {"vibecomfy_uid": "dyn"},
                "widgets_values": [{"name": "row"}],
            }
        ]
    }
    converted = {"1": {"class_type": "DynamicRows", "inputs": {"widget_0": {"name": "row"}}}}

    _merge_slim_ui(raw, converted)

    assert converted["1"]["_ui"]["widgets_values"] == [{"name": "row"}]
    assert converted["1"]["_raw_widgets"] == {
        "values": [{"name": "row"}],
        "shape": "list",
        "source": "ui.widgets_values",
        "has_dict_rows": True,
        "length": 1,
    }


def test_local_schema_provider_missing_index_is_empty(tmp_path) -> None:
    provider = LocalSchemaProvider(tmp_path / "missing_node_index.json")

    assert provider.schemas() == {}


def test_local_schema_provider_reports_malformed_existing_index(tmp_path) -> None:
    index = tmp_path / "node_index.json"
    index.write_text("{not-json", encoding="utf-8")
    provider = LocalSchemaProvider(index)

    with pytest.raises(SchemaIndexError) as exc_info:
        provider.schemas()

    assert exc_info.value.path == index
    assert "JSONDecodeError" in str(exc_info.value)


def test_schema_provider_helpers_support_public_and_legacy_getters() -> None:
    schema = _schema("PromptNode")

    assert schema_for(FakeSchemaProvider({"PromptNode": schema}), "PromptNode") is schema
    assert schema_for(LegacyGetSchemaProvider({"PromptNode": schema}), "PromptNode") is schema
    assert schema_for(object(), "PromptNode") is None


def test_schema_registry_empty_helper_checks_optional_schemas_method() -> None:
    assert schema_registry_empty(LocalSchemaProvider("missing-node-index.json")) is True
    assert schema_registry_empty(object()) is False
    assert schemas_for(object()) is None


def test_local_schema_provider_parses_index_rows(tmp_path) -> None:
    index = tmp_path / "node_index.json"
    index.write_text(
        json.dumps(
            [
                {
                    "class_type": "PromptNode",
                    "pack": "core",
                    "inputs": {
                        "required": {"text": "STRING"},
                        "optional": {"mode": [["fast", "slow"], {"default": "fast"}]},
                    },
                    "outputs": [{"type": "CONDITIONING", "name": "conditioning"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    schema = LocalSchemaProvider(index).get_schema("PromptNode")

    assert schema is not None
    assert schema.pack == "core"
    assert schema.inputs["text"].type == "STRING"
    assert schema.inputs["text"].required is True
    assert schema.inputs["mode"].type == "CHOICE"
    assert schema.inputs["mode"].choices == ["fast", "slow"]
    assert schema.inputs["mode"].default == "fast"
    assert schema.outputs == [OutputSpec(type="CONDITIONING", name="conditioning")]


def test_malformed_object_info_cache_is_ignored(tmp_path) -> None:
    cache = tmp_path / "object_info.bad.json"
    cache.write_text("{not-json", encoding="utf-8")

    assert load_object_info_cache(cache) is None


def test_runtime_schema_provider_reads_cached_object_info(tmp_path) -> None:
    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)
    provider.cache_path.write_text(
        json.dumps(
            {
                "RuntimeNode": {
                    "pack": "runtime-pack",
                    "input": {"required": {"image": ["IMAGE", {"default": None}]}},
                    "output": ["LATENT"],
                    "output_name": ["latent"],
                }
            }
        ),
        encoding="utf-8",
    )

    schema = provider.get_schema("RuntimeNode")

    assert schema is not None
    assert schema.pack == "runtime-pack"
    assert schema.inputs["image"].type == "IMAGE"
    assert schema.inputs["image"].required is True
    assert schema.outputs == [OutputSpec(type="LATENT", name="latent")]


def test_object_info_schema_provider_reads_normalized_cache_shape(tmp_path) -> None:
    cache = tmp_path / "normalized_object_info.json"
    cache.write_text(
        json.dumps(
            {
                "SaveImage": {
                    "pack": "comfy",
                    "inputs": {
                        "required": {
                            "images": ["IMAGE", {}],
                            "filename_prefix": ["STRING", {"default": "ComfyUI"}],
                        }
                    },
                    "outputs": [{"type": "IMAGE", "name": "image"}],
                    "object_info_widget_order": [None, "filename_prefix"],
                }
            }
        ),
        encoding="utf-8",
    )

    schema = ObjectInfoSchemaProvider(cache).get_schema("SaveImage")

    assert schema is not None
    assert list(schema.inputs) == ["filename_prefix", "images"]
    assert schema.inputs["images"].type == "IMAGE"
    assert schema.outputs == [OutputSpec(type="IMAGE", name="image")]


def test_runtime_schema_provider_fetches_and_writes_object_info_cache(tmp_path, monkeypatch) -> None:
    class FakeServer:
        async def __aenter__(self):
            return "http://active-runtime.test"

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def object_info(self):
            assert self.url == "http://active-runtime.test"
            return {"FetchedNode": {"input": {"optional": {"strength": ["FLOAT", {"default": 1.0, "min": 0, "max": 2}]}}}}

    monkeypatch.setattr("vibecomfy.schema.provider.comfy_server", lambda **kwargs: FakeServer())
    monkeypatch.setattr("vibecomfy.schema.provider.ComfyClient", FakeClient)
    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)

    data = asyncio.run(provider.object_info_async())

    assert "FetchedNode" in data
    assert json.loads(provider.cache_path.read_text(encoding="utf-8")) == data
    schema = provider.get_schema("FetchedNode")
    assert schema is not None
    assert schema.inputs["strength"].default == 1.0
    assert schema.inputs["strength"].min == 0
    assert schema.inputs["strength"].max == 2


def test_source_schema_provider_reads_input_types_from_custom_node_source(tmp_path) -> None:
    node_source = tmp_path / "custom_pack" / "nodes"
    node_source.mkdir(parents=True)
    (node_source / "image_nodes.py").write_text(
        """
class ImageResizeKJv2:
    upscale_methods = ["nearest-exact", "lanczos"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 512, "min": 0}),
                "upscale_method": (cls.upscale_methods,),
            },
            "optional": {"device": (["cpu", "gpu"],)},
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
""",
        encoding="utf-8",
    )

    schema = SourceSchemaProvider([tmp_path]).get_schema("ImageResizeKJv2")

    assert schema is not None
    assert schema.inputs["image"].required is True
    assert schema.inputs["width"].type == "INT"
    assert schema.inputs["upscale_method"].choices == ["nearest-exact", "lanczos"]
    assert schema.inputs["device"].required is False
    assert schema.outputs == [OutputSpec(type="IMAGE", name="image")]


# ---------------------------------------------------------------------------
# Sprint 2 T4: numeric runtime semantics for named output handles
# ---------------------------------------------------------------------------


def test_named_output_handle_has_numeric_slot() -> None:
    """`builder.out('image')` produces a Handle whose output_slot is always int."""
    from vibecomfy.handles import Handle
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("named-test", WorkflowSource("named-test"))
    node = VibeNode("1", "LoadImage", metadata={"output_names": ["image", "mask"]})
    wf.nodes["1"] = node

    builder = wf.node("LoadImage")
    # Overwrite the auto-created node with our metadata-carrying node
    wf.nodes[builder.node.id] = node
    builder = type(builder)(workflow=wf, node=node)  # _NodeBuilder is frozen so reconstruct

    # Named lookup
    h = builder.out("image")
    assert isinstance(h, Handle)
    assert h.output_slot == 0
    assert h.name == "image"

    # Stringified handle is always numeric
    assert str(h) == f"1.0"

    # Integer lookup also works
    h2 = builder.out(1)
    assert h2.output_slot == 1
    assert str(h2) == "1.1"


def test_named_output_compile_emits_numeric_links() -> None:
    """`compile('api')` emits `[node_id, 0]` numeric links after named handle use."""
    from vibecomfy.handles import Handle
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    wf = VibeWorkflow("compile-test", WorkflowSource("compile-test"))
    src_node = VibeNode("10", "LoadImage", inputs={"image": "input.png"}, metadata={"output_names": ["image", "mask"]})
    dst_node = VibeNode("20", "SaveImage")
    wf.nodes["10"] = src_node
    wf.nodes["20"] = dst_node

    # Simulate named handle usage: connect via named output
    h = Handle(node_id="10", output_slot=0, name="image")
    wf.connect(h, "20.images")

    api = wf.compile("api")
    # The edge must be a numeric link
    assert api["20"]["inputs"]["images"] == ["10", 0]
    assert isinstance(api["20"]["inputs"]["images"][1], int)


def test_named_output_api_shape_unchanged_after_named_authoring() -> None:
    """API dict shape is identical whether handles are built with names or plain ints."""
    from vibecomfy.handles import Handle
    from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

    # Build via named authoring
    wf_named = VibeWorkflow("named", WorkflowSource("named"))
    wf_named.nodes["10"] = VibeNode("10", "LoadImage", inputs={"image": "input.png"}, metadata={"output_names": ["image"]})
    wf_named.nodes["20"] = VibeNode("20", "SaveImage")
    wf_named.connect(Handle(node_id="10", output_slot=0, name="image"), "20.images")

    # Build via numeric authoring
    wf_num = VibeWorkflow("num", WorkflowSource("num"))
    wf_num.nodes["10"] = VibeNode("10", "LoadImage", inputs={"image": "input.png"})
    wf_num.nodes["20"] = VibeNode("20", "SaveImage")
    wf_num.connect(Handle(node_id="10", output_slot=0), "20.images")

    api_named = wf_named.compile("api")
    api_num = wf_num.compile("api")

    # Both APIs should be structurally identical after stripping output_names metadata
    assert api_named.keys() == api_num.keys()
    assert api_named["20"]["inputs"]["images"] == api_num["20"]["inputs"]["images"]
    assert api_named["20"]["inputs"]["images"] == ["10", 0]


def test_get_schema_provider_auto_selection(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("vibecomfy.comfy_command.shutil.which", lambda _: None)
    monkeypatch.setattr("vibecomfy.comfy_command.importlib.util.find_spec", lambda _: None)

    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)
    assert isinstance(get_schema_provider("auto", server_url="http://runtime.test"), RuntimeSchemaProvider)

    (tmp_path / "node_index.json").write_text("[]", encoding="utf-8")
    assert isinstance(get_schema_provider("auto"), LocalSchemaProvider)


# ---------------------------------------------------------------------------
# Sprint 2 T3: enriched node metadata (output_names, output_types,
# input_aliases, schema_source) with partial evidence preservation
# ---------------------------------------------------------------------------


def test_schema_output_names_full() -> None:
    """All output names are returned when every entry is valid."""
    provider = FakeSchemaProvider(
        {
            "SaveImage": NodeSchema(
                class_type="SaveImage",
                pack=None,
                inputs={},
                outputs=[OutputSpec(type="IMAGE", name="image")],
            ),
        }
    )
    names = _schema_output_names(provider, "SaveImage")
    assert names == ["image"]


def test_schema_output_names_partial_preserves_blank() -> None:
    """A blank entry in the middle is preserved, not dropped."""
    provider = FakeSchemaProvider(
        {
            "MultiOut": NodeSchema(
                class_type="MultiOut",
                pack=None,
                inputs={},
                outputs=[
                    OutputSpec(type="IMAGE", name="image"),
                    OutputSpec(type="LATENT", name=""),
                    OutputSpec(type="VAE", name="latent"),
                ],
            ),
        }
    )
    names = _schema_output_names(provider, "MultiOut")
    # All three entries preserved, including the blank one
    assert names == ["image", "", "latent"]


def test_schema_output_names_all_blank_preserved() -> None:
    """When all names are blank, the list is preserved (not dropped to empty)."""
    provider = FakeSchemaProvider(
        {
            "Silent": NodeSchema(
                class_type="Silent",
                pack=None,
                inputs={},
                outputs=[
                    OutputSpec(type="IMAGE", name=None),
                    OutputSpec(type="LATENT", name=""),
                ],
            ),
        }
    )
    names = _schema_output_names(provider, "Silent")
    # Both entries preserved as empty strings
    assert names == ["", ""]


def test_schema_output_names_duplicate_preserved() -> None:
    """Duplicate output names are preserved as-is; emitter decides safety later."""
    provider = FakeSchemaProvider(
        {
            "DupOut": NodeSchema(
                class_type="DupOut",
                pack=None,
                inputs={},
                outputs=[
                    OutputSpec(type="IMAGE", name="image"),
                    OutputSpec(type="MASK", name="image"),
                ],
            ),
        }
    )
    names = _schema_output_names(provider, "DupOut")
    assert names == ["image", "image"]


def test_schema_input_aliases_excludes_link_only_types() -> None:
    """Link-only types (IMAGE, LATENT, MODEL, etc.) are excluded from input_aliases."""
    provider = FakeSchemaProvider(
        {
            "CheckpointLoader": NodeSchema(
                class_type="CheckpointLoader",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec(type="STRING"),
                    "model": InputSpec(type="MODEL"),
                    "clip": InputSpec(type="CLIP"),
                    "vae": InputSpec(type="VAE"),
                },
                outputs=[],
            ),
        }
    )
    aliases = _schema_input_aliases(provider, "CheckpointLoader")
    # Only the non-link-type input (ckpt_name) should appear
    assert aliases == ["ckpt_name"]


def test_schema_input_aliases_empty_when_all_link_only() -> None:
    """When all inputs are link-only types, input_aliases is empty."""
    provider = FakeSchemaProvider(
        {
            "ImagePass": NodeSchema(
                class_type="ImagePass",
                pack=None,
                inputs={
                    "image": InputSpec(type="IMAGE"),
                    "latent": InputSpec(type="LATENT"),
                },
                outputs=[],
            ),
        }
    )
    aliases = _schema_input_aliases(provider, "ImagePass")
    assert aliases == []


def test_convert_to_vibe_format_stores_output_names_with_partial_evidence() -> None:
    """Metadata stores all output names including blanks; emitter decides per slot."""
    provider = FakeSchemaProvider(
        {
            "MultiOut": NodeSchema(
                class_type="MultiOut",
                pack=None,
                inputs={},
                outputs=[
                    OutputSpec(type="IMAGE", name="image"),
                    OutputSpec(type="LATENT", name=""),
                    OutputSpec(type="VAE", name="latent"),
                ],
                source_provider="node_index",
                confidence=1.0,
            ),
        }
    )
    api = {"1": {"class_type": "MultiOut", "inputs": {}}}
    wf = convert_to_vibe_format(api, schema_provider=provider)
    node = wf.nodes["1"]
    meta = node.metadata
    assert meta.get("output_names") == ["image", "", "latent"]
    assert meta.get("output_types") == ["IMAGE", "LATENT", "VAE"]


def test_convert_to_vibe_format_stores_input_aliases_excluding_link_only() -> None:
    """input_aliases only includes widget-type inputs, not link-only types."""
    provider = FakeSchemaProvider(
        {
            "Loader": NodeSchema(
                class_type="Loader",
                pack=None,
                inputs={
                    "ckpt_name": InputSpec(type="STRING"),
                    "model": InputSpec(type="MODEL"),
                    "clip": InputSpec(type="CLIP"),
                },
                outputs=[OutputSpec(type="MODEL", name="model")],
                source_provider="widget_schema",
                confidence=0.3,
            ),
        }
    )
    api = {"1": {"class_type": "Loader", "inputs": {}}}
    wf = convert_to_vibe_format(api, schema_provider=provider)
    node = wf.nodes["1"]
    meta = node.metadata
    assert meta.get("input_aliases") == ["ckpt_name"]


def test_convert_to_vibe_format_stores_schema_source_provenance() -> None:
    """schema_source provenance is recorded per node from schema metadata."""
    provider = FakeSchemaProvider(
        {
            "PromptNode": NodeSchema(
                class_type="PromptNode",
                pack=None,
                inputs={"text": InputSpec(type="STRING")},
                outputs=[],
                source_provider="node_index",
                source_path="/path/to/node_index.json",
                source_cache_path=None,
                source_server_url=None,
                source_package="core",
                source_version="1.0",
                source_hash="abc123",
                confidence=1.0,
            ),
        }
    )
    api = {"1": {"class_type": "PromptNode", "inputs": {}}}
    wf = convert_to_vibe_format(api, schema_provider=provider)
    node = wf.nodes["1"]
    meta = node.metadata
    source = meta.get("schema_source")
    assert source is not None
    assert source["provider"] == "node_index"
    assert source["path"] == "/path/to/node_index.json"
    assert source["package"] == "core"
    assert source["version"] == "1.0"
    assert source["hash"] == "abc123"
    assert source["confidence"] == 1.0


def test_convert_to_vibe_format_conflicting_provider_evidence() -> None:
    """When multiple providers could serve a node, stored provenance reflects
    the winning (highest-priority) evidence."""
    provider = FakeSchemaProvider(
        {
            "CheckpointLoader": NodeSchema(
                class_type="CheckpointLoader",
                pack=None,
                inputs={"ckpt_name": InputSpec(type="STRING")},
                outputs=[OutputSpec(type="MODEL", name="model")],
                source_provider="source_parser",
                source_path="/custom_nodes/checkpoint.py",
                confidence=0.9,
                conflicts=("node_index_missing",),
                ignored_evidence=("widget_schema_stale",),
            ),
        }
    )
    api = {"1": {"class_type": "CheckpointLoader", "inputs": {}}}
    wf = convert_to_vibe_format(api, schema_provider=provider)
    node = wf.nodes["1"]
    source = node.metadata.get("schema_source")
    assert source is not None
    assert source["provider"] == "source_parser"
    assert source["path"] == "/custom_nodes/checkpoint.py"
    assert source["confidence"] == 0.9


# ---------------------------------------------------------------------------
# Sprint 2 T10: ConversionSchemaProvider precedence tests
# ---------------------------------------------------------------------------


def test_conversion_schema_provider_empty_returns_none_without_network() -> None:
    """ConversionSchemaProvider with no providers returns None without network access."""
    from vibecomfy.schema.provider import ConversionSchemaProvider

    provider = ConversionSchemaProvider(
        node_index_path="/nonexistent/node_index.json",
        source_roots=[],
        object_info_cache_path=None,
        widget_schema={},
        enable_runtime=False,
    )
    # Must return None, not try to reach a server
    assert provider.get_schema("UnknownNode") is None


def test_conversion_schema_provider_prefers_node_index_over_source(
    tmp_path,
) -> None:
    """Node index (committed) beats source parser in precedence."""
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Create a node_index.json with a known type
    index = tmp_path / "node_index.json"
    index.write_text(
        json.dumps(
            [
                {
                    "class_type": "TestNode",
                    "pack": "core",
                    "inputs": {"text": {"type": "STRING", "required": True}},
                    "outputs": [{"type": "IMAGE", "name": "image"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=None,
        widget_schema={},
        enable_runtime=False,
    )

    schema = provider.get_schema("TestNode")
    assert schema is not None
    assert schema.source_provider == "node_index"
    assert schema.inputs["text"].type == "STRING"
    assert schema.confidence == 1.0


def test_conversion_schema_provider_falls_back_to_source_parser(
    tmp_path,
) -> None:
    """When node_index lacks a type, source parser is tried next."""
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Create an empty node_index
    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")

    # Create a source tree with a Python node definition
    source_root = tmp_path / "custom_nodes"
    node_dir = source_root / "test_pack" / "nodes"
    node_dir.mkdir(parents=True)
    (node_dir / "test_nodes.py").write_text(
        """
class SourceOnlyNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"prompt": ("STRING", {"default": ""})}}
    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
""",
        encoding="utf-8",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[str(source_root)],
        object_info_cache_path=None,
        widget_schema={},
        enable_runtime=False,
    )

    schema = provider.get_schema("SourceOnlyNode")
    assert schema is not None
    assert schema.source_provider == "source_parser"
    assert schema.inputs["prompt"].type == "STRING"
    assert schema.confidence == 0.9


def test_conversion_schema_provider_falls_back_to_object_info_cache(
    tmp_path,
) -> None:
    """When node_index and source parser miss, object_info cache is tried."""
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Create an empty node_index
    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")

    # Create an object_info cache with provenance metadata
    import hashlib
    fp = hashlib.sha256(b"test-cache").hexdigest()[:16]
    cache = tmp_path / f"object_info.{fp}.json"
    cache.write_text(
        json.dumps(
            {
                "_cache_metadata": {
                    "fingerprint": fp,
                    "source": "test-cache",
                    "timestamp": "2026-01-01T00:00:00Z",
                },
                "CacheOnlyNode": {
                    "input": {"required": {"image": ["IMAGE", {}]}},
                    "output": ["MASK"],
                    "output_name": ["mask"],
                    "category": "test/cache",
                },
            }
        ),
        encoding="utf-8",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=str(cache),
        widget_schema={},
        enable_runtime=False,
    )

    schema = provider.get_schema("CacheOnlyNode")
    assert schema is not None
    assert schema.source_provider == "object_info_cache"
    assert schema.inputs["image"].type == "IMAGE"
    assert schema.confidence == 0.4
    assert any(item.startswith("stale_cache_fingerprint:") for item in schema.conflicts)


def test_conversion_schema_provider_uses_object_info_index_root(
    tmp_path,
) -> None:
    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")
    object_info_root = tmp_path / "object_info"
    object_info_root.mkdir()
    (object_info_root / "index.json").write_text(
        json.dumps({"IndexedNode": "pack.json"}),
        encoding="utf-8",
    )
    (object_info_root / "pack.json").write_text(
        json.dumps(
            {
                "IndexedNode": {
                    "pack": "indexed-pack",
                    "inputs": {"required": {"prompt": ["STRING", {}]}},
                    "outputs": [{"type": "IMAGE", "name": "image"}],
                }
            }
        ),
        encoding="utf-8",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=None,
        object_info_index_root=object_info_root,
        widget_schema={},
        enable_runtime=False,
    )

    schema = provider.get_schema("IndexedNode")
    assert schema is not None
    assert schema.source_provider == "object_info_index"
    assert schema.pack == "indexed-pack"
    assert schema.inputs["prompt"].type == "STRING"
    assert schema.outputs == [OutputSpec(type="IMAGE", name="image")]


def test_conversion_schema_provider_falls_back_to_widget_schema(
    tmp_path,
) -> None:
    """When all other providers miss, widget_schema fallback is used."""
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Create an empty node_index
    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")

    widget_schema = {
        "WidgetOnlyNode": ["text", "mode", None],
    }

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=None,
        widget_schema=widget_schema,
        enable_runtime=False,
    )

    schema = provider.get_schema("WidgetOnlyNode")
    assert schema is not None
    assert schema.source_provider == "widget_schema"
    assert "text" in schema.inputs
    assert schema.inputs["text"].type is None  # widget fallback has no type info
    assert schema.confidence == 0.3


def test_conversion_schema_provider_never_calls_runtime_without_flag(
    tmp_path,
) -> None:
    """Without enable_runtime, ConversionSchemaProvider never reaches runtime."""
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Create an empty node_index
    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=None,
        widget_schema={},
        enable_runtime=False,
    )

    # Even with all other providers empty, runtime is NOT consulted
    assert provider.get_schema("AnyMissingNode") is None
    # The _runtime attribute should be None when enable_runtime=False
    assert provider._runtime is None


def test_conversion_schema_provider_with_runtime_enabled(
    tmp_path,
    monkeypatch,
) -> None:
    """With enable_runtime=True, runtime provider is used as last resort."""
    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Create an empty node_index
    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")

    # Set up a fake RuntimeSchemaProvider that returns a schema
    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=None,
        widget_schema={},
        enable_runtime=True,
        runtime_server_url="http://runtime.test",
    )

    # Verify runtime provider was created
    assert provider._runtime is not None

    # Pre-populate the runtime cache so no actual network call happens
    from vibecomfy.schema.provider import NodeSchema, OutputSpec
    from vibecomfy.schema.cache import load_object_info_cache

    # Write directly to the runtime cache path
    runtime_cache_path = provider._runtime.cache_path
    runtime_cache_path.parent.mkdir(parents=True, exist_ok=True)
    import json

    runtime_cache_path.write_text(
        json.dumps(
            {
                "RuntimeNode": {
                    "input": {"required": {"seed": ["INT", {"default": 0}]}},
                    "output": ["IMAGE"],
                    "output_name": ["image"],
                }
            }
        ),
        encoding="utf-8",
    )

    schema = provider.get_schema("RuntimeNode")
    assert schema is not None
    assert schema.source_provider == "runtime"
    assert schema.confidence == 0.6
    assert schema.inputs["seed"].type == "INT"


def test_conversion_schema_provider_precedence_order_is_correct(
    tmp_path,
) -> None:
    """Full precedence: node_index > source > cache > widget > runtime.

    When a type is available in multiple providers, the highest-priority
    one wins.
    """
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Set up node_index with TestNode (confidence 1.0)
    index = tmp_path / "node_index.json"
    index.write_text(
        json.dumps(
            [
                {
                    "class_type": "TestNode",
                    "pack": "core",
                    "inputs": {"text": {"type": "STRING", "required": True}},
                    "outputs": [{"type": "IMAGE", "name": "image"}],
                }
            ]
        ),
        encoding="utf-8",
    )

    # Also set up source parser with same type
    source_root = tmp_path / "custom_nodes"
    node_dir = source_root / "test_pack" / "nodes"
    node_dir.mkdir(parents=True)
    (node_dir / "test_nodes.py").write_text(
        """
class TestNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"prompt": ("STRING", {"default": ""})}}
    RETURN_TYPES = ("CONDITIONING",)
""",
        encoding="utf-8",
    )

    # And object_info cache with same type
    cache = tmp_path / "object_info.json"
    cache.write_text(
        json.dumps(
            {
                "TestNode": {
                    "input": {"required": {"image": ["IMAGE", {}]}},
                    "output": ["MASK"],
                }
            }
        ),
        encoding="utf-8",
    )

    # And widget schema with same type
    widget_schema = {"TestNode": ["mode"]}

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[str(source_root)],
        object_info_cache_path=str(cache),
        widget_schema=widget_schema,
        enable_runtime=False,
    )

    schema = provider.get_schema("TestNode")
    assert schema is not None
    # Should come from node_index (highest priority)
    assert schema.source_provider == "node_index"
    assert schema.confidence == 1.0
    assert "text" in schema.inputs


def test_conversion_schema_provider_provenance_fields_populated(
    tmp_path,
) -> None:
    """Provider provenance fields are correctly populated on returned schemas."""
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Node index hit
    index = tmp_path / "node_index.json"
    index.write_text(
        json.dumps(
            [
                {
                    "class_type": "ProvenanceNode",
                    "pack": "test-pack",
                    "inputs": {"value": {"type": "FLOAT", "required": False}},
                    "outputs": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=None,
        widget_schema={},
        enable_runtime=False,
    )

    schema = provider.get_schema("ProvenanceNode")
    assert schema is not None
    assert schema.source_provider == "node_index"
    assert schema.source_path == str(index)
    assert schema.confidence == 1.0
    assert schema.pack == "test-pack"


def test_conversion_schema_provider_stale_cache_does_not_block_other_providers(
    tmp_path,
) -> None:
    """A malformed object_info cache does not prevent fallback to widget schema."""
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    # Empty node_index
    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")

    # Malformed cache
    cache = tmp_path / "object_info.json"
    cache.write_text("{not-json", encoding="utf-8")

    widget_schema = {"FallbackNode": ["alpha"]}

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=str(cache),
        widget_schema=widget_schema,
        enable_runtime=False,
    )

    # Malformed cache should be caught, falling through to widget schema
    schema = provider.get_schema("FallbackNode")
    assert schema is not None
    assert schema.source_provider == "widget_schema"
    assert schema.confidence == 0.3


def test_conversion_schema_provider_marks_metadata_less_object_info_cache(
    tmp_path,
) -> None:
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")
    cache = tmp_path / "object_info.json"
    cache.write_text(
        json.dumps(
            {
                "CachedNode": {
                    "input": {"required": {"prompt": ["STRING", {}]}},
                    "output": ["IMAGE"],
                    "output_name": ["image"],
                }
            }
        ),
        encoding="utf-8",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=str(cache),
        widget_schema={},
        enable_runtime=False,
    )

    schema = provider.get_schema("CachedNode")
    assert schema is not None
    assert schema.source_provider == "object_info_cache"
    assert schema.source_cache_path == str(cache)
    assert schema.confidence == 0.5
    assert "metadata_less_cache" in schema.ignored_evidence
    assert "missing_cache_fingerprint" in schema.ignored_evidence


def test_conversion_schema_provider_marks_stale_object_info_cache_fingerprint(
    tmp_path,
) -> None:
    import json

    from vibecomfy.schema.provider import ConversionSchemaProvider

    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")
    cache = tmp_path / "object_info.stale-fingerprint.json"
    cache.write_text(
        json.dumps(
            {
                "_cache_metadata": {"runtime_fingerprint": "stale-fingerprint"},
                "CachedNode": {
                    "input": {"required": {"prompt": ["STRING", {}]}},
                    "output": ["IMAGE"],
                    "output_name": ["image"],
                },
            }
        ),
        encoding="utf-8",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=str(cache),
        widget_schema={},
        enable_runtime=False,
    )

    schema = provider.get_schema("CachedNode")
    assert schema is not None
    assert schema.source_provider == "object_info_cache"
    assert schema.source_hash == "stale-fingerprint"
    assert schema.confidence == 0.4
    assert any(item.startswith("stale_cache_fingerprint:") for item in schema.conflicts)
