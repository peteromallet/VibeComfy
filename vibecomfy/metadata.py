from __future__ import annotations

import os

from vibecomfy.workflow import VibeInput, VibeNode, VibeWorkflow, WorkflowRequirements


PROMPT_KEYS = {"text", "prompt", "positive", "positive_prompt"}
SEED_KEYS = {"seed", "noise_seed"}
STEP_KEYS = {"steps"}
MODEL_KEYS = {"ckpt_name", "model_name", "unet_name"}
OUTPUT_NODE_NAMES = {
    "SaveImage",
    "PreviewImage",
    "SaveAnimatedWEBP",
    "SaveWEBM",
    "VHS_VideoCombine",
    "SaveVideo",
    "SaveAudio",
    "SaveAudioMP3",
}

MODEL_FILE_EXTENSIONS = ('.safetensors', '.ckpt', '.pt', '.pth', '.gguf', '.onnx', '.bin')

# Class-type allowlist for the universal `--prompt` override.
#
# Sourced by grepping the runtime-green image/edit corpus for nodes that pair
# a textual `text`/`prompt` field with downstream image-conditioning use:
#
#   ready_templates/sources/official/image/{flux2_klein_4b_t2i,flux2_klein_9b_t2i,z_image}.json
#   ready_templates/sources/official/edit/{flux2_klein_4b_image_edit_*,flux2_klein_9b_image_edit_*,qwen_image_edit}.json
#   ready_templates/sources/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json
#   ready_templates/sources/official/video/{wan_t2v,wan_i2v,ltx2_3_t2v,ltx2_3_i2v}.json
#
# Custom-node prompt classes (WanVideoTextEncode, TextEncodeAceStepAudio1.5,
# LoadWanVideoT5TextEncoder, etc.) are intentionally excluded because they
# accept tags/cached embeddings/etc. rather than a free-form image prompt.
PROMPT_NODE_CLASSES = {
    "CLIPTextEncode",
    "CLIPTextEncodeSDXL",
    "CLIPTextEncodeFlux",
    # Used by qwen_image_edit; takes a free-form image edit prompt string.
    "TextEncodeQwenImageEdit",
}

# Class-type allowlist for the universal `--steps` override.
#
# Sourced from the same image/edit/video corpus. KSamplerSelect is excluded
# because it only selects a sampler name and exposes no `steps` widget; the
# actual step count for those families lives in scheduler nodes
# (Flux2Scheduler, LTXVScheduler, BasicScheduler, ...) which take varied
# field names per family. We deliberately keep this list to true samplers
# whose `steps` field is the sample count.
STEPS_NODE_CLASSES = {
    "KSampler",
    "KSamplerAdvanced",
    "SamplerCustom",
    "SamplerCustomAdvanced",
    "BasicScheduler",
}


def _legacy_overrides_enabled() -> bool:
    return os.environ.get("VIBECOMFY_LEGACY_OVERRIDES") == "1"


def _register_common_inputs(workflow: VibeWorkflow, node_id: str, node: VibeNode) -> None:
    legacy = _legacy_overrides_enabled()
    for field, value in {**node.inputs, **node.widgets}.items():
        normalized = field.lower()
        if (
            normalized in PROMPT_KEYS
            and isinstance(value, str)
            and "prompt" not in workflow.inputs
            and (legacy or node.class_type in PROMPT_NODE_CLASSES)
        ):
            workflow.inputs["prompt"] = VibeInput("prompt", node_id, field, value)
        elif (
            normalized in SEED_KEYS
            and isinstance(value, int)
            and not isinstance(value, bool)
            and "seed" not in workflow.inputs
        ):
            workflow.inputs["seed"] = VibeInput("seed", node_id, field, value)
        elif (
            normalized in STEP_KEYS
            and isinstance(value, int)
            and not isinstance(value, bool)
            and "steps" not in workflow.inputs
            and (legacy or node.class_type in STEPS_NODE_CLASSES)
        ):
            workflow.inputs["steps"] = VibeInput("steps", node_id, field, value)
        elif normalized in MODEL_KEYS and isinstance(value, str) and "model" not in workflow.inputs:
            workflow.inputs["model"] = VibeInput("model", node_id, field, value)


def _infer_requirements(workflow: VibeWorkflow) -> WorkflowRequirements:
    models: list[str] = []
    custom_nodes: list[str] = []
    for node in workflow.nodes.values():
        if "." in node.class_type:
            custom_nodes.append(node.class_type.split(".", 1)[0])
        for key, value in {**node.inputs, **node.widgets}.items():
            if key.endswith("_name") and isinstance(value, str):
                if value.lower().endswith(MODEL_FILE_EXTENSIONS):
                    models.append(value)
    previous = getattr(workflow, "requirements", None)
    # Inferred graph facts are additive; authored exact custom-node refs are
    # semantic declarations and must survive the inference refresh.
    authored_refs = list(getattr(previous, "custom_node_refs", ()) or ())
    metadata_requirements = workflow.metadata.get("requirements")
    if isinstance(metadata_requirements, dict):
        from vibecomfy.custom_node_refs import normalize_custom_node_requirements

        normalized, _warnings = normalize_custom_node_requirements(metadata_requirements)
        custom_nodes.extend(normalized.get("custom_nodes") or ())
    return WorkflowRequirements(
        models=sorted(set(models)),
        custom_nodes=sorted(set(custom_nodes)),
        custom_node_refs=authored_refs,
    )
