from __future__ import annotations

import asyncio
import json
from pathlib import Path

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
from vibecomfy.schema.cache import (
    CACHE_METADATA_KEY,
    OBJECT_INFO_CACHE_FORMAT_VERSION,
    load_object_info_cache,
    object_info_payload_checksum,
    runtime_fingerprint,
    validate_object_info_cache,
    write_object_info_cache,
)
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


def test_object_info_cache_checksum_excludes_metadata() -> None:
    data = {
        "CacheNode": {"input": {"required": {"image": ["IMAGE", {}]}}},
        CACHE_METADATA_KEY: {"format_version": 1, "checksum": "old"},
    }
    changed_metadata = {
        **data,
        CACHE_METADATA_KEY: {"format_version": 2, "checksum": "new", "note": "ignored"},
    }

    assert object_info_payload_checksum(data) == object_info_payload_checksum(changed_metadata)


def test_write_object_info_cache_stamps_metadata_and_validates(tmp_path) -> None:
    cache = tmp_path / "object_info.runtime-id.json"
    write_object_info_cache(
        cache,
        {
            "CacheNode": {
                "input": {"required": {"image": ["IMAGE", {}]}},
                "output": ["IMAGE"],
            },
            CACHE_METADATA_KEY: {
                "format_version": 1,
                "runtime_fingerprint": "stale-runtime",
                "checksum": "stale-checksum",
            },
        },
        server_url="http://runtime.test/",
    )

    data = load_object_info_cache(cache)
    assert data is not None
    assert data["CacheNode"]["output"] == ["IMAGE"]
    metadata = data[CACHE_METADATA_KEY]
    assert metadata["format_version"] == OBJECT_INFO_CACHE_FORMAT_VERSION
    assert metadata["runtime_fingerprint"] == "runtime-id"
    assert metadata["server_url"] == "http://runtime.test"
    assert metadata["checksum"] == object_info_payload_checksum(data)

    result = validate_object_info_cache(
        data,
        expected={"runtime_fingerprint": "runtime-id", "server_url": "http://runtime.test/"},
        cache_path=cache,
    )
    assert result.ok is True
    assert result.reason is None
    assert result.severity == "ok"
    assert result.cache_path == str(cache)


def test_validate_object_info_cache_reports_structured_mismatch(tmp_path) -> None:
    data = {
        "CacheNode": {"input": {"required": {"image": ["IMAGE", {}]}}},
    }
    data[CACHE_METADATA_KEY] = {
        "format_version": OBJECT_INFO_CACHE_FORMAT_VERSION,
        "checksum": object_info_payload_checksum(data),
        "runtime_fingerprint": "actual-runtime",
        "authored_pack_fingerprint": "actual-pack",
    }

    result = validate_object_info_cache(
        data,
        expected={"runtime_fingerprint": "expected-runtime", "authored_pack_fingerprint": "actual-pack"},
        cache_path=tmp_path / "object_info.actual-runtime.json",
    )

    assert result.ok is False
    assert result.reason == "cache_runtime_fingerprint_mismatch"
    assert result.expected["runtime_fingerprint"] == "expected-runtime"
    assert result.actual["runtime_fingerprint"] == "actual-runtime"
    assert result.severity == "error"


def test_validate_object_info_cache_covers_identity_and_format_failures(tmp_path) -> None:
    base = {
        "CacheNode": {"input": {"required": {"image": ["IMAGE", {}]}}},
    }
    metadata = {
        "format_version": OBJECT_INFO_CACHE_FORMAT_VERSION,
        "checksum": object_info_payload_checksum(base),
        "runtime_fingerprint": "runtime-id",
        "server_url": "http://runtime.test",
        "authored_pack_fingerprint": "pack-id",
        "authored_index_fingerprint": "index-id",
    }
    matching = {**base, CACHE_METADATA_KEY: metadata}

    ok = validate_object_info_cache(
        matching,
        expected={
            "runtime_fingerprint": "runtime-id",
            "server_url": "http://runtime.test/",
            "authored_pack_fingerprint": "pack-id",
            "authored_index_fingerprint": "index-id",
        },
        cache_path=tmp_path / "object_info.runtime-id.json",
    )
    assert ok.ok is True
    assert ok.reason is None
    assert ok.actual["server_url"] == "http://runtime.test"

    cases = [
        (
            {**base, CACHE_METADATA_KEY: {**metadata, "format_version": 1}},
            {"runtime_fingerprint": "runtime-id"},
            "cache_format_version_mismatch",
        ),
        (
            {**base, CACHE_METADATA_KEY: {key: value for key, value in metadata.items() if key != "format_version"}},
            {"runtime_fingerprint": "runtime-id"},
            "cache_format_version_missing",
        ),
        (
            {**base, CACHE_METADATA_KEY: {**metadata, "server_url": "http://other-runtime.test"}},
            {"server_url": "http://runtime.test"},
            "cache_server_url_mismatch",
        ),
        (
            {**base, CACHE_METADATA_KEY: {**metadata, "authored_index_fingerprint": "stale-index"}},
            {"authored_index_fingerprint": "index-id"},
            "cache_authored_index_fingerprint_mismatch",
        ),
        (
            ["not", "an", "object"],
            {"runtime_fingerprint": "runtime-id"},
            "cache_payload_not_object",
        ),
    ]
    for data, expected, reason in cases:
        result = validate_object_info_cache(data, expected=expected)
        assert result.ok is False
        assert result.reason == reason
        assert result.severity == "error"


def test_validate_object_info_cache_detects_payload_checksum_mismatch() -> None:
    data = {
        "CacheNode": {"input": {"required": {"image": ["IMAGE", {}]}}},
    }
    data[CACHE_METADATA_KEY] = {
        "format_version": OBJECT_INFO_CACHE_FORMAT_VERSION,
        "checksum": object_info_payload_checksum(data),
        "runtime_fingerprint": "runtime-id",
    }
    data["CacheNode"]["output"] = ["LATENT"]

    result = validate_object_info_cache(data, expected={"runtime_fingerprint": "runtime-id"})

    assert result.ok is False
    assert result.reason == "cache_checksum_mismatch"
    assert result.actual["checksum"] != result.actual["computed_checksum"]


def test_validate_object_info_cache_legacy_policy() -> None:
    data = {"LegacyNode": {"input": {"required": {"image": ["IMAGE", {}]}}}}

    strict = validate_object_info_cache(data, expected={"runtime_fingerprint": "runtime-id"})
    legacy = validate_object_info_cache(data, expected={"runtime_fingerprint": "runtime-id"}, policy="allow_legacy")

    assert strict.ok is False
    assert strict.reason == "cache_metadata_missing"
    assert strict.severity == "error"
    assert legacy.ok is True
    assert legacy.reason == "cache_metadata_missing"
    assert legacy.severity == "warning"


def test_write_object_info_cache_replace_failure_preserves_existing_file(tmp_path, monkeypatch) -> None:
    import vibecomfy.schema.cache as cache_module

    cache = tmp_path / "object_info.runtime-id.json"
    cache.write_text(json.dumps({"ExistingNode": {"input": {}}}), encoding="utf-8")

    def fail_replace(src, dst):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(cache_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_object_info_cache(cache, {"NewNode": {"input": {}}})

    assert json.loads(cache.read_text(encoding="utf-8")) == {"ExistingNode": {"input": {}}}
    assert list(tmp_path.glob(f".{cache.name}.*.tmp")) == []


def test_write_object_info_cache_pre_replace_failure_preserves_existing_bytes(tmp_path, monkeypatch) -> None:
    import vibecomfy.schema.cache as cache_module

    cache = tmp_path / "object_info.runtime-id.json"
    existing = b'{"ExistingNode":{"input":{}}}\n'
    cache.write_bytes(existing)

    def fail_fsync(fd):
        raise OSError("simulated pre-replace failure")

    monkeypatch.setattr(cache_module.os, "fsync", fail_fsync)

    with pytest.raises(OSError, match="simulated pre-replace failure"):
        write_object_info_cache(cache, {"NewNode": {"input": {}}})

    assert cache.read_bytes() == existing
    assert list(tmp_path.glob(f".{cache.name}.*.tmp")) == []


def test_runtime_schema_provider_reads_cached_object_info(tmp_path) -> None:
    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)
    write_object_info_cache(
        provider.cache_path,
        {
            "RuntimeNode": {
                "pack": "runtime-pack",
                "input": {"required": {"image": ["IMAGE", {"default": None}]}},
                "output": ["LATENT"],
                "output_name": ["latent"],
            }
        },
        runtime_fingerprint=runtime_fingerprint("http://runtime.test"),
        server_url="http://runtime.test",
    )

    schema = provider.get_schema("RuntimeNode")

    assert schema is not None
    assert schema.pack == "runtime-pack"
    assert schema.inputs["image"].type == "IMAGE"
    assert schema.inputs["image"].required is True
    assert schema.outputs == [OutputSpec(type="LATENT", name="latent")]


def test_runtime_schema_provider_rejects_stale_cache_refetches_and_clears_schemas(tmp_path, monkeypatch) -> None:
    class FakeServer:
        async def __aenter__(self):
            return "http://runtime.test"

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def object_info(self):
            return {
                "FetchedNode": {
                    "input": {"required": {"image": ["IMAGE", {}]}},
                    "output": ["LATENT"],
                    "output_name": ["latent"],
                }
            }

    monkeypatch.setattr("vibecomfy.schema.provider.comfy_server", lambda **kwargs: FakeServer())
    monkeypatch.setattr("vibecomfy.schema.provider.ComfyClient", FakeClient)

    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)
    write_object_info_cache(
        provider.cache_path,
        {"StaleNode": {"input": {"required": {"prompt": ["STRING", {}]}}}},
        runtime_fingerprint="stale-runtime",
    )
    provider._schemas = {"OldNode": NodeSchema(class_type="OldNode", pack=None, inputs={}, outputs=[])}

    data = provider.object_info()

    assert "FetchedNode" in data
    assert provider._schemas is None
    schema = provider.get_schema("FetchedNode")
    assert schema is not None
    assert schema.inputs["image"].type == "IMAGE"
    cached = load_object_info_cache(provider.cache_path)
    result = validate_object_info_cache(
        cached,
        expected={"runtime_fingerprint": runtime_fingerprint("http://runtime.test")},
        cache_path=provider.cache_path,
    )
    assert result.ok
    assert cached is not None and "FetchedNode" in cached


def test_runtime_schema_provider_async_rejects_stale_cache_and_rewrites_fresh(tmp_path, monkeypatch) -> None:
    class FakeServer:
        async def __aenter__(self):
            return "http://runtime.test"

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClient:
        def __init__(self, url: str) -> None:
            self.url = url

        async def object_info(self):
            return {"AsyncFetchedNode": {"input": {"optional": {"strength": ["FLOAT", {"default": 1.0}]}}}}

    monkeypatch.setattr("vibecomfy.schema.provider.comfy_server", lambda **kwargs: FakeServer())
    monkeypatch.setattr("vibecomfy.schema.provider.ComfyClient", FakeClient)

    provider = RuntimeSchemaProvider(server_url="http://runtime.test", cache_dir=tmp_path)
    write_object_info_cache(
        provider.cache_path,
        {"StaleNode": {"input": {"required": {"prompt": ["STRING", {}]}}}},
        runtime_fingerprint="stale-runtime",
    )

    data = asyncio.run(provider.object_info_async())

    assert "AsyncFetchedNode" in data
    cached = load_object_info_cache(provider.cache_path)
    result = validate_object_info_cache(
        cached,
        expected={"runtime_fingerprint": runtime_fingerprint("http://runtime.test")},
        cache_path=provider.cache_path,
    )
    assert result.ok
    assert cached is not None and "AsyncFetchedNode" in cached


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
    cached = json.loads(provider.cache_path.read_text(encoding="utf-8"))
    assert cached["FetchedNode"] == data["FetchedNode"]
    assert cached[CACHE_METADATA_KEY]["format_version"] == OBJECT_INFO_CACHE_FORMAT_VERSION
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


def test_source_schema_provider_default_roots_are_explicit() -> None:
    provider = SourceSchemaProvider()

    assert provider.roots == [Path("custom_nodes"), Path("vendor") / "ComfyUI"]
    assert SourceSchemaProvider([]).roots == []


def test_source_schema_provider_default_roots_do_not_scan_tmp_comfyui_checkout(tmp_path, monkeypatch) -> None:
    tmp_checkout = Path("/tmp") / f"ComfyUI-vibecomfy-t9-{tmp_path.name}"
    node_dir = tmp_checkout / "custom_nodes"
    node_dir.mkdir(parents=True)
    (node_dir / "tmp_only.py").write_text(
        """
class TmpOnlyNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("STRING", {})}}
""",
        encoding="utf-8",
    )
    try:
        monkeypatch.chdir(tmp_path)

        provider = SourceSchemaProvider()

        assert provider.get_schema("TmpOnlyNode") is None
        assert tmp_checkout not in provider.roots
    finally:
        (node_dir / "tmp_only.py").unlink(missing_ok=True)
        node_dir.rmdir()
        tmp_checkout.rmdir()


def test_source_schema_provider_bounds_roots_with_warning(tmp_path) -> None:
    skipped_root = tmp_path / "root_b"
    skipped_root.mkdir()
    (skipped_root / "SkippedRootNode.py").write_text(
        """
class SkippedRootNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("STRING", {})}}
""",
        encoding="utf-8",
    )

    provider = SourceSchemaProvider([tmp_path / "root_a", skipped_root], max_roots=1)

    assert provider.get_schema("SkippedRootNode") is None
    assert provider.roots == [tmp_path / "root_a"]
    assert [
        warning.code
        for warning in provider.scan_warnings
        if warning.path == str(skipped_root)
    ] == ["source_scan_root_cap_skipped"]


def test_source_schema_provider_bounds_recursive_scan_with_warning(tmp_path) -> None:
    source_root = tmp_path / "custom_nodes"
    source_root.mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (source_root / name).write_text(
            """
class CappedNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("STRING", {})}}
""",
            encoding="utf-8",
        )

    provider = SourceSchemaProvider([source_root], max_files_per_root=2, max_total_files=10)

    assert provider.get_schema("CappedNode") is not None
    assert any(warning.code == "source_scan_file_cap_skipped" for warning in provider.scan_warnings)


def test_source_schema_provider_bounds_total_files_deterministically(tmp_path) -> None:
    first_root = tmp_path / "a_root"
    second_root = tmp_path / "b_root"
    first_root.mkdir()
    second_root.mkdir()
    (first_root / "aa.py").write_text("# no schema here\n", encoding="utf-8")
    (first_root / "zz.py").write_text("# no schema here\n", encoding="utf-8")
    (second_root / "later.py").write_text(
        """
class LaterNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("STRING", {})}}
""",
        encoding="utf-8",
    )

    provider = SourceSchemaProvider([first_root, second_root], max_files_per_root=10, max_total_files=2)

    assert provider.get_schema("LaterNode") is None
    assert [
        warning.code
        for warning in provider.scan_warnings
        if warning.path == str(second_root / "later.py")
    ] == ["source_scan_total_file_cap_skipped"]


def test_source_schema_provider_excludes_common_large_directories(tmp_path) -> None:
    source_root = tmp_path / "custom_nodes"
    excluded_dir = source_root / "node_modules"
    excluded_dir.mkdir(parents=True)
    (excluded_dir / "excluded.py").write_text(
        """
class ExcludedDirectoryNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"value": ("STRING", {})}}
""",
        encoding="utf-8",
    )

    provider = SourceSchemaProvider([source_root])

    assert provider.get_schema("ExcludedDirectoryNode") is None
    assert provider.provenance_for("ExcludedDirectoryNode") is None


def test_source_schema_provider_reports_dynamic_input_types_miss(tmp_path) -> None:
    source_root = tmp_path / "custom_nodes"
    source_root.mkdir()
    (source_root / "dynamic.py").write_text(
        """
def make_inputs():
    return {"required": {"value": ("STRING", {})}}

class DynamicInputNode:
    @classmethod
    def INPUT_TYPES(cls):
        return make_inputs()
""",
        encoding="utf-8",
    )

    provider = SourceSchemaProvider([source_root])

    assert provider.get_schema("DynamicInputNode") is None
    assert provider.get_schema("AbsentNode") is None
    assert provider.provenance_for("AbsentNode") is None
    assert any(
        warning.code == "dynamic_input_types_miss" and warning.class_type == "DynamicInputNode"
        for warning in provider.scan_warnings
    )
    provenance = provider.provenance_for("DynamicInputNode")
    assert provenance is not None
    assert provenance.ignored_evidence == ["dynamic_input_types_miss"]


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

    cache = tmp_path / "object_info.json"
    write_object_info_cache(
        cache,
        {
            "CacheOnlyNode": {
                "input": {"required": {"image": ["IMAGE", {}]}},
                "output": ["MASK"],
                "output_name": ["mask"],
                "category": "test/cache",
            },
        },
        runtime_fingerprint=runtime_fingerprint(),
        metadata={"source": "test-cache", "timestamp": "2026-01-01T00:00:00Z"},
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
    assert schema.confidence == 0.8
    assert schema.conflicts == ()


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
    write_object_info_cache(
        object_info_root / "pack.json",
        {
            "IndexedNode": {
                "pack": "indexed-pack",
                "inputs": {"required": {"prompt": ["STRING", {}]}},
                "outputs": [{"type": "IMAGE", "name": "image"}],
            }
        },
        authored_pack_fingerprint="authored-pack-id",
        metadata={"package": "indexed-pack", "version": "1.2.3"},
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
    assert schema.source_hash == "authored-pack-id"
    assert schema.source_package == "indexed-pack"
    assert schema.source_version == "1.2.3"


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

    write_object_info_cache(
        runtime_cache_path,
        {
            "RuntimeNode": {
                "input": {"required": {"seed": ["INT", {"default": 0}]}},
                "output": ["IMAGE"],
                "output_name": ["image"],
            }
        },
        runtime_fingerprint=runtime_fingerprint("http://runtime.test"),
        server_url="http://runtime.test",
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


def test_conversion_schema_provider_rejects_metadata_less_object_info_cache(
    tmp_path,
    caplog,
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
        widget_schema={"CachedNode": ["fallback_prompt"]},
        enable_runtime=False,
    )

    schema = provider.get_schema("CachedNode")
    assert schema is not None
    assert schema.source_provider == "widget_schema"
    assert schema.confidence == 0.3
    assert "fallback_prompt" in schema.inputs
    assert provider._object_info is None
    assert any("rejected_metadata_less_object_info_cache" in item for item in provider._rejected_object_info_cache.conflicts)
    assert "rejected object_info cache" in caplog.text


def test_conversion_schema_provider_rejects_stale_object_info_cache_fingerprint(
    tmp_path,
    caplog,
) -> None:
    from vibecomfy.schema.provider import ConversionSchemaProvider

    index = tmp_path / "node_index.json"
    index.write_text("[]", encoding="utf-8")
    cache = tmp_path / "object_info.stale-fingerprint.json"
    write_object_info_cache(
        cache,
        {
            "CachedNode": {
                "input": {"required": {"prompt": ["STRING", {}]}},
                "output": ["IMAGE"],
                "output_name": ["image"],
            },
        },
        runtime_fingerprint="stale-fingerprint",
    )

    provider = ConversionSchemaProvider(
        node_index_path=str(index),
        source_roots=[],
        object_info_cache_path=str(cache),
        widget_schema={"CachedNode": ["fallback_prompt"]},
        enable_runtime=False,
    )

    schema = provider.get_schema("CachedNode")
    assert schema is not None
    assert schema.source_provider == "widget_schema"
    assert schema.confidence == 0.3
    assert provider._object_info is None
    assert provider._rejected_object_info_cache.hash == "stale-fingerprint"
    assert any("rejected_stale_object_info_cache" in item for item in provider._rejected_object_info_cache.conflicts)
    assert "cache_runtime_fingerprint_mismatch" in caplog.text
