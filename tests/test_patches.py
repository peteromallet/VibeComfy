from __future__ import annotations

import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vibecomfy.patches.gguf_unet import GGUF_MODEL, patch as gguf_unet
from vibecomfy.patches.registry import find_applicable, register, registered_patches
from vibecomfy.patches.ltx_lowvram import COMFY_CONFIGURATION, FP8_CHECKPOINT, SOURCE_CHECKPOINT, patch as ltx_lowvram
from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.seed import seed
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


def test_patch_contract_documents_decoration_not_handle_construction() -> None:
    contract = inspect.getdoc(Patch) or ""

    assert "decoration of an existing workflow graph" in contract
    assert "Construction APIs" in contract
    assert "return public handles belong in blocks or ready workflows" in contract
    assert "public result is always the same" in contract
    assert "must not introduce a new handle-producing API" in contract
    assert "conservative, side-effect-free predicate" in contract
    assert "idempotent" in contract
    assert "fail clearly" in contract
    assert "silently leaving the graph unchanged" in contract


def test_builtin_patches_remain_discoverable_from_registry() -> None:
    builtin_names = {patch.name for patch in registered_patches(include_builtins=True)}

    assert {"controlnet", "gguf_unet", "ltx_lowvram"} <= builtin_names


def test_patch_package_import_does_not_register_builtins() -> None:
    script = """
import vibecomfy.patches
from vibecomfy.patches.registry import _PATCHES, bootstrap_builtin_patches, registered_patches

print(",".join(sorted(_PATCHES)))
print(",".join(sorted(patch.name for patch in bootstrap_builtin_patches())))
print(",".join(sorted(_PATCHES)))
print(",".join(sorted(patch.name for patch in registered_patches())))
"""
    env = {**os.environ, "PYTHONPATH": str(Path.cwd())}
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    before_bootstrap, builtin_names, after_bootstrap, registered_names = result.stdout.splitlines()
    assert before_bootstrap == ""
    assert builtin_names == "controlnet,gguf_unet,ltx_lowvram"
    assert after_bootstrap == ""
    assert registered_names == builtin_names


def test_find_applicable_uses_builtin_tuple_and_external_registry() -> None:
    workflow = VibeWorkflow("patch-registry-test", WorkflowSource("patch-registry-test"))
    external = Patch("external", lambda candidate: candidate is workflow, lambda candidate: candidate, lambda _: "test")

    register(external)

    assert external in registered_patches(include_builtins=False)
    assert external in find_applicable(workflow)


def test_patch_apply_preserves_return_value_and_compiled_api_for_metadata_only_patch() -> None:
    workflow = VibeWorkflow("metadata-only", WorkflowSource("metadata-only"))
    workflow.add_node("SaveImage", images="placeholder")
    before = workflow.compile("api")

    def apply(candidate: VibeWorkflow) -> VibeWorkflow:
        candidate.metadata["note"] = "patched"
        return candidate

    patched = Patch("metadata-only", lambda _: True, apply, lambda _: "metadata only")
    result = patched.apply(workflow)

    assert result is workflow
    assert workflow.compile("api") == before
    assert workflow.metadata["entrypoint"] == "patch"
    assert workflow.metadata["layer"] == "tests/test_patches.py:metadata-only"
    assert workflow.metadata["patch_applications"] == [
        {
            "name": "metadata-only",
            "layer": "patch",
            "called": True,
            "topology_changed": False,
            "nodes_added": [],
            "introduced_edges": [],
            "rewritten_edges": [],
        }
    ]


def test_seed_patch_records_value_change_without_topology_change() -> None:
    workflow = VibeWorkflow("seed-only", WorkflowSource("seed-only"))
    workflow.nodes["sampler"] = VibeNode("sampler", "KSampler", inputs={"seed": 1, "steps": 4})
    before = workflow.compile("api")

    patched = seed(99)
    result = patched.apply(workflow)

    assert result is workflow
    assert workflow.compile("api") == {
        **before,
        "sampler": {
            **before["sampler"],
            "inputs": {
                **before["sampler"]["inputs"],
                "seed": 99,
            },
        },
    }
    assert workflow.metadata["patch_applications"] == [
        {
            "name": "seed:99",
            "layer": "patch",
            "called": True,
            "topology_changed": False,
            "nodes_added": [],
            "introduced_edges": [],
            "rewritten_edges": [],
            "value_changed": True,
        }
    ]


def test_repeated_value_patch_upserts_telemetry_without_losing_first_change() -> None:
    workflow = VibeWorkflow("seed-repeat", WorkflowSource("seed-repeat"))
    workflow.nodes["sampler"] = VibeNode("sampler", "KSampler", inputs={"seed": 1})
    patched = seed(99)

    patched.apply(workflow)
    first_metadata = [dict(item) for item in workflow.metadata["patch_applications"]]
    patched.apply(workflow)

    assert workflow.metadata["patch_applications"] == first_metadata
    assert workflow.metadata["patch_applications"][0]["value_changed"] is True


def test_gguf_builtin_is_idempotent_in_graph_requirements_and_metadata() -> None:
    workflow = VibeWorkflow("gguf-repeat", WorkflowSource("gguf-repeat"))
    workflow.nodes["unet"] = VibeNode(
        "unet",
        "UNETLoader",
        inputs={"unet_name": "flux-2-klein-9b.safetensors"},
    )

    gguf_unet.apply(workflow)
    first_api = workflow.compile("api")
    first_metadata = [dict(item) for item in workflow.metadata["patch_applications"]]
    gguf_unet.apply(workflow)

    assert workflow.compile("api") == first_api
    assert workflow.nodes["unet"].inputs["unet_name"] == GGUF_MODEL
    assert workflow.requirements.custom_nodes.count("ComfyUI-GGUF") == 1
    assert workflow.metadata["patch_applications"] == first_metadata


def test_ensure_custom_nodes_appends_without_duplicates() -> None:
    workflow = VibeWorkflow("requirements-test", WorkflowSource("requirements-test"))
    workflow.requirements.custom_nodes.append("Existing")

    ensure_custom_nodes(workflow, ("Existing", "New"))
    ensure_custom_nodes(workflow, ("New",))

    assert workflow.requirements.custom_nodes == ["Existing", "New"]


def test_ltx_lowvram_rewrites_supported_graph() -> None:
    positive = _supported_ltx_workflow()
    positive.metadata["ready_template"] = "video/ltx2_3_t2v"

    assert ltx_lowvram.applies_to(positive)

    ltx_lowvram.apply(positive)

    assert positive.metadata["comfy_configuration"] == COMFY_CONFIGURATION
    assert positive.metadata["smoke_resolution"] == "384x256x9_frames"
    assert positive.metadata["external_python_marker"] == "external_python:video/ltx2_3_t2v"
    assert positive.nodes["4010"].class_type == "LTXVAudioVAELoader"
    assert positive.nodes["4010"].inputs == {"ckpt_name": FP8_CHECKPOINT}
    assert positive.nodes["4010"].widgets == {}
    assert positive.nodes["3940"].class_type == "LowVRAMCheckpointLoader"
    assert positive.nodes["3940"].inputs["ckpt_name"] == FP8_CHECKPOINT
    assert "dependencies" not in positive.nodes["3940"].inputs
    assert VibeEdge("4960", "0", "3940", "dependencies") in positive.edges
    assert "ComfyUI-LTXVideo" in positive.requirements.custom_nodes
    assert "ComfyUI-KJNodes" in positive.requirements.custom_nodes


def test_ltx_lowvram_accepts_already_applied_supported_graph_idempotently() -> None:
    workflow = _supported_ltx_workflow()
    ltx_lowvram.apply(workflow)
    first_api = workflow.compile("api")
    first_metadata = [dict(item) for item in workflow.metadata["patch_applications"]]

    assert not ltx_lowvram.applies_to(workflow)

    ltx_lowvram.apply(workflow)

    assert workflow.compile("api") == first_api
    assert workflow.requirements.custom_nodes.count("ComfyUI-LTXVideo") == 1
    assert workflow.requirements.custom_nodes.count("ComfyUI-KJNodes") == 1
    assert workflow.metadata["patch_applications"] == first_metadata


def test_ltx_lowvram_rejects_non_ltx_and_unsupported_ltx_like_graphs() -> None:
    negative = VibeWorkflow("plain", WorkflowSource("plain"))
    negative.add_node("SaveImage", images="placeholder")

    assert not ltx_lowvram.applies_to(negative)
    with pytest.raises(ValueError, match="ltx_lowvram only supports LTX 2.3 workflows"):
        ltx_lowvram.apply(negative)

    unsupported = VibeWorkflow("ltx-like", WorkflowSource("ltx-like"))
    unsupported.add_node("LTXVLoader")
    unsupported.nodes["4010"] = VibeNode(id="4010", class_type="LTXVAudioVAELoader", inputs={"ckpt_name": "other.safetensors"})
    unsupported.nodes["3940"] = VibeNode(id="3940", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": SOURCE_CHECKPOINT})

    assert not ltx_lowvram.applies_to(unsupported)
    with pytest.raises(ValueError, match="ltx_lowvram only supports LTX 2.3 workflows"):
        ltx_lowvram.apply(unsupported)


def test_ltx_lowvram_generated_ready_template_applies_before_metadata_policy() -> None:
    from ready_templates.video.ltx2_3_t2v import build

    workflow = build()

    assert workflow.metadata["ready_template"] == "video/ltx2_3_t2v"
    assert workflow.nodes["4010"].class_type == "LTXVAudioVAELoader"
    assert workflow.nodes["3940"].class_type == "LowVRAMCheckpointLoader"
    assert workflow.nodes["4010"].inputs["ckpt_name"] == FP8_CHECKPOINT
    assert workflow.nodes["3940"].inputs["ckpt_name"] == FP8_CHECKPOINT
    api = workflow.compile("api")
    assert api["3059"]["inputs"]["batch_size"] == 1
    assert api["3980"]["inputs"]["batch_size"] == 1
    assert api["4981"]["inputs"]["longer_size"] == 384
    assert api["4981"]["inputs"]["resize_type.longer_size"] == 384
    assert api["4966"]["inputs"]["max_shift"] == 2.05
    assert api["4966"]["inputs"]["base_shift"] == 0.95
    assert api["4966"]["inputs"]["stretch"] is True
    assert api["4966"]["inputs"]["terminal"] == 0.1
    assert api["4963"]["inputs"]["cross_attn"] is True
    assert api["4964"]["inputs"]["modality"] == "VIDEO"
    assert api["4808"]["inputs"]["skip_blocks"] == "28"
    assert api["4982"]["inputs"]["last_frame_fix"] is False
    assert api["4983"]["inputs"]["last_frame_fix"] is False
    assert "audio" not in api["4819"]["inputs"]
    assert "audio" not in api["4849"]["inputs"]
    assert api["4823"]["inputs"]["format"] == "auto"
    assert api["4823"]["inputs"]["codec"] == "auto"
    assert api["4852"]["inputs"]["format"] == "auto"
    assert api["4852"]["inputs"]["codec"] == "auto"


def _supported_ltx_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("ltx", WorkflowSource("ltx"))
    workflow.add_node("LTXVScheduler")
    workflow.nodes["4960"] = VibeNode(id="4960", class_type="LTXAVTextEncoderLoader")
    workflow.nodes["4010"] = VibeNode(id="4010", class_type="LTXVAudioVAELoader", inputs={"ckpt_name": SOURCE_CHECKPOINT})
    workflow.nodes["3940"] = VibeNode(id="3940", class_type="CheckpointLoaderSimple", inputs={"ckpt_name": SOURCE_CHECKPOINT})
    return workflow
