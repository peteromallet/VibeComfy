from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.resolution import resolution
from vibecomfy.registry.ready import ready_template_ids, workflow_from_ready
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.runtime.session import SessionConfig
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


SNAPSHOT_IDS = (
    "image/z_image",
    "image/flux2_klein_4b_t2i",
    "image/flux2_klein_9b_gguf_t2i",
    "edit/qwen_image_edit",
    "edit/flux2_klein_4b_image_edit_distilled",
    "video/wan_t2v",
    "video/wan_i2v",
    "video/ltx2_3_t2v",
    "video/ltx2_3_i2v",
)

PROFILE_SMOKE_TEMPLATE_IDS = (
    "video/wanvideo_wrapper_22_5b_i2v",
    "video/wanvideo_wrapper_22_14b_vace_cocktail",
    "video/wan_t2v",
)


def test_ready_template_ids_include_curated_workflows() -> None:
    ids = ready_template_ids()

    assert "edit/qwen_image_edit" in ids
    assert "image/qwen_image_2512" in ids
    assert "edit/flux2_klein_4b_image_edit_base" in ids
    assert "edit/flux2_klein_9b_image_edit_base" in ids
    assert "edit/flux2_klein_9b_image_edit_distilled" in ids
    assert "image/z_image" in ids
    assert "image/flux2_klein_9b_t2i" in ids
    assert "video/wan_t2v" in ids
    assert "video/wanvideo_wrapper_22_14b_vace_cocktail" in ids
    assert all(not template_id.rsplit("/", 1)[-1].startswith("_") for template_id in ids)


def test_ready_template_loads_vibe_workflow() -> None:
    workflow = workflow_from_ready("edit/qwen_image_edit")

    assert workflow.validate().ok
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["python_policy_applied"] is True


def test_all_ready_templates_load_and_validate() -> None:
    for template_id in ready_template_ids():
        workflow = workflow_from_ready(template_id)

        assert workflow.id == template_id
        assert workflow.validate().ok
        assert workflow.metadata["ready_template"] == template_id


def test_ready_template_build_has_category_qualified_metadata() -> None:
    workflow = workflow_from_ready("qwen_image_edit")

    assert workflow.id == "edit/qwen_image_edit"
    assert workflow.metadata["ready_template"] == "edit/qwen_image_edit"
    assert workflow.metadata["workflow_template"] == "qwen_image_edit"


def test_ready_template_preserves_materialized_requirements() -> None:
    workflow = workflow_from_ready("video/ltx2_3_t2v")

    assert "ComfyUI-LTXVideo" in workflow.requirements.custom_nodes
    assert "ComfyUI-KJNodes" in workflow.requirements.custom_nodes


def test_ready_template_requirements_accept_structured_model_assets() -> None:
    workflow = VibeWorkflow("scratchpad", WorkflowSource("scratchpad"))
    workflow.add_node("CheckpointLoaderSimple", widget_0="checkpoint.safetensors")

    apply_ready_template_policy(
        workflow,
        {},
        source_path="scratch.py",
        requirements={
            "models": [
                "legacy.safetensors",
                {
                    "name": "z-model.safetensors",
                    "url": "https://example.test/z-model.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "z-model.safetensors",
                    "url": "https://example.test/duplicate.safetensors",
                    "subdir": "checkpoints",
                },
                {
                    "name": "a-model.safetensors",
                    "url": "https://example.test/a-model.safetensors",
                    "subdir": "vae",
                },
            ],
            "custom_nodes": [],
        },
    )

    assert workflow.requirements.models == [
        "a-model.safetensors",
        "legacy.safetensors",
        "z-model.safetensors",
    ]
    assert all(isinstance(model, str) for model in workflow.requirements.models)
    assert workflow.metadata["model_assets"] == [
        {
            "name": "z-model.safetensors",
            "url": "https://example.test/z-model.safetensors",
            "subdir": "checkpoints",
        },
        {
            "name": "a-model.safetensors",
            "url": "https://example.test/a-model.safetensors",
            "subdir": "vae",
        },
    ]


def test_ready_template_uses_real_python_before_comfy_compile() -> None:
    workflow = workflow_from_ready("edit/qwen_image_edit")

    marker = f"external_python:{workflow.metadata['ready_template']}"
    workflow.metadata["external_python_marker"] = marker
    workflow.add_node("MarkdownNote", widget_0=marker)
    api = workflow.compile("api")

    assert workflow.metadata["external_python_marker"] == marker
    assert any(node["inputs"].get("widget_0") == marker for node in api.values())


@pytest.mark.parametrize("template_id", PROFILE_SMOKE_TEMPLATE_IDS)
@pytest.mark.parametrize("memory_profile", [1, 2, 3, 4, 5])
def test_representative_video_ready_templates_compile_under_memory_profiles(
    template_id: str,
    memory_profile: int,
) -> None:
    baseline = workflow_from_ready(template_id)
    baseline_api = baseline.compile("api")
    workflow = workflow_from_ready(template_id)
    workflow.metadata["comfy_configuration"] = {"memory_profile": memory_profile}

    config = SessionConfig.from_workflow_metadata(workflow)
    api = workflow.compile("api")

    assert config.memory_profile == memory_profile
    assert workflow.validate().ok
    assert api
    assert _class_type_counter(api) == _class_type_counter(baseline_api)
    assert _topology_counter(api) == _topology_counter(baseline_api)


@pytest.mark.parametrize(
    "template_id",
    (
        "video/wanvideo_wrapper_22_14b_vace_cocktail",
        "video/wanvideo_wrapper_22_14b_vace_cocktail_dry_run",
    ),
)
def test_wan22_vace_cocktail_templates_have_expected_three_phase_topology(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)
    api = workflow.compile("api")

    loaders = _nodes_by_type(api, "WanVideoModelLoader")
    samplers = _nodes_by_type(api, "WanVideoSampler")
    decoders = _nodes_by_type(api, "WanVideoDecode")

    assert list(loaders) == ["20", "21"]
    assert list(samplers) == ["50", "51", "52"]
    assert list(decoders) == ["60"]
    assert loaders["20"]["inputs"]["model"].endswith("A14B_HIGH_mbf16.safetensors")
    assert loaders["21"]["inputs"]["model"].endswith("A14B_LOW_mbf16.safetensors")
    assert [samplers[node_id]["inputs"]["steps"] for node_id in ("50", "51", "52")] == [2, 2, 2]
    assert [samplers[node_id]["inputs"]["cfg"] for node_id in ("50", "51", "52")] == [3.0, 1.0, 1.0]
    assert all("scheduler" in samplers[node_id]["inputs"] for node_id in ("50", "51", "52"))
    assert {"filename_prefix", "format", "loop_count", "pingpong"}.issubset(decoders["60"]["inputs"] | api["70"]["inputs"])
    assert samplers["50"]["inputs"]["model"] == ["20", 0]
    assert samplers["51"]["inputs"]["model"] == ["20", 0]
    assert samplers["51"]["inputs"]["samples"] == ["50", 0]
    assert samplers["52"]["inputs"]["model"] == ["21", 0]
    assert samplers["52"]["inputs"]["samples"] == ["51", 0]
    assert decoders["60"]["inputs"]["samples"] == ["52", 0]
    assert workflow.metadata["phase_model_topology"] == ["HIGH", "HIGH", "LOW"]
    assert workflow.metadata["phase_step_allocation"] == [2, 2, 2]
    assert workflow.metadata["fixture_manifest_path"].endswith("fixtures/sprint35/manifest.json")


@pytest.mark.parametrize("template_id", SNAPSHOT_IDS)
def test_snapshotted_ready_template_graph_matches_pre_refactor_api(template_id: str) -> None:
    workflow = workflow_from_ready(template_id)
    actual = workflow.compile("api")
    snapshot_name = template_id.rsplit("/", 1)[-1]
    expected = json.loads((Path(__file__).parent / "snapshots" / f"{snapshot_name}.api.json").read_text(encoding="utf-8"))
    if template_id.startswith("video/ltx2_3_"):
        expected_workflow = convert_to_vibe_format(expected, workflow_id=template_id)
        expected_workflow.metadata["ready_template"] = template_id
        apply_ltx_lowvram(expected_workflow)
        resolution(384, 256, 9).apply(expected_workflow)
        expected = expected_workflow.compile("api")

    assert _class_type_counter(actual) == _class_type_counter(expected)
    assert _widget_value_counter(actual) == _widget_value_counter(expected)
    assert _topology_counter(actual) == _topology_counter(expected)


def _nodes_by_type(api: dict, class_type: str) -> dict[str, dict]:
    return {node_id: node for node_id, node in sorted(api.items(), key=lambda item: int(item[0])) if node.get("class_type") == class_type}


def _class_type_counter(api: dict) -> Counter[str]:
    return Counter(node["class_type"] for node in api.values() if node.get("class_type") != "MarkdownNote")


def _widget_value_counter(api: dict) -> Counter[tuple[str, str, str]]:
    values: Counter[tuple[str, str, str]] = Counter()
    for node in api.values():
        class_type = node.get("class_type")
        if class_type == "MarkdownNote":
            continue
        for key, value in node.get("inputs", {}).items():
            if _is_link(value):
                continue
            values[(class_type, key, repr(value))] += 1
    return values


def _topology_counter(api: dict) -> Counter[tuple[str, str, str, int]]:
    topology: Counter[tuple[str, str, str, int]] = Counter()
    for node_id, node in api.items():
        class_type = node.get("class_type")
        if class_type == "MarkdownNote":
            continue
        for key, value in node.get("inputs", {}).items():
            if not _is_link(value):
                continue
            source = api.get(str(value[0]), {})
            source_class = source.get("class_type")
            if source_class == "MarkdownNote":
                continue
            topology[(class_type, key, source_class, int(value[1]))] += 1
    return topology


def _is_link(value: object) -> bool:
    return isinstance(value, list) and len(value) == 2 and str(value[0]).isdigit()
