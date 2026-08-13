from __future__ import annotations

from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeEdge, VibeWorkflow


FP8_CHECKPOINT = "ltx-2.3-22b-dev-fp8.safetensors"
SOURCE_CHECKPOINT = "ltx-2.3-22b-dev.safetensors"
AUDIO_LOADER_ID = "4010"
CHECKPOINT_LOADER_ID = "3940"
CLOWN_SAMPLER_CLASS = "ClownSampler_Beta"
PORTABLE_SAMPLER = "euler_ancestral_cfg_pp"

COMFY_CONFIGURATION = {
    "reserve_vram": 12,
    "cache_none": True,
    "fp8_e4m3fn_text_enc": True,
}


def applies_to(workflow: VibeWorkflow) -> bool:
    return _is_supported_rewrite_target(workflow)


def apply(workflow: VibeWorkflow) -> VibeWorkflow:
    if not _is_supported_target(workflow):
        raise ValueError(
            "ltx_lowvram only supports LTX 2.3 workflows with node 3940 as a "
            "CheckpointLoaderSimple/LowVRAMCheckpointLoader and node 4010 as "
            "an LTXVAudioVAELoader."
        )

    image_to_video = workflow.metadata.get("capability") == "image_to_video"
    if "3159" in workflow.nodes:
        image_to_video = True

    _update_node(workflow, "3059", inputs={"width": 384, "height": 256}, widgets={"widget_0": 384, "widget_1": 256, "widget_2": 9})
    _update_node(workflow, "4979", widgets={"widget_0": 9})
    _update_node(workflow, "4978", widgets={"widget_0": 8})
    _update_node(workflow, "1241", widgets={"widget_0": 8})
    _update_node(workflow, "3980", widgets={"widget_0": 9, "widget_1": 8})
    _update_node(workflow, "4977", widgets={"widget_0": not image_to_video})
    _update_node(workflow, "2004", widgets={"widget_0": "egyptian_queen.png" if image_to_video else "example.png"})
    _update_node(workflow, "4981", widgets={"widget_1": 384})
    _replace_clown_samplers(workflow)

    if AUDIO_LOADER_ID in workflow.nodes:
        node = workflow.nodes[AUDIO_LOADER_ID]
        node.class_type = "LTXVAudioVAELoader"
        node.inputs = {"ckpt_name": FP8_CHECKPOINT}
        node.widgets = {}
    if CHECKPOINT_LOADER_ID in workflow.nodes:
        node = workflow.nodes[CHECKPOINT_LOADER_ID]
        node.class_type = "LowVRAMCheckpointLoader"
        node.inputs = {"ckpt_name": FP8_CHECKPOINT}
        node.widgets = {}
        workflow.edges = [
            edge
            for edge in workflow.edges
            if not (
                str(edge.to_node) == CHECKPOINT_LOADER_ID
                and edge.to_input == "dependencies"
            )
        ]
        workflow.edges.append(
            VibeEdge(
                from_node="4960",
                from_output="0",
                to_node=CHECKPOINT_LOADER_ID,
                to_input="dependencies",
            )
        )

    _ensure_current_ltx_schema_defaults(workflow)

    workflow.metadata["smoke_resolution"] = "384x256x9_frames"
    workflow.metadata["comfy_configuration"] = dict(COMFY_CONFIGURATION)
    if ready_template := workflow.metadata.get("ready_template"):
        workflow.metadata["external_python_marker"] = f"external_python:{ready_template}"

    workflow.finalize_metadata()
    ensure_custom_nodes(workflow, ("ComfyUI-LTXVideo", "ComfyUI-KJNodes"))
    return workflow


def rationale(workflow: VibeWorkflow) -> str:
    return (
        "LTXVideo nodes detected; reduces VRAM by using the fp8 checkpoint, "
        "low-VRAM model loader, portable sampler, and 384x256x9 smoke settings."
    )


def _is_supported_target(workflow: VibeWorkflow) -> bool:
    return _is_supported_rewrite_target(workflow) or _is_supported_applied_target(workflow)


def _is_supported_rewrite_target(workflow: VibeWorkflow) -> bool:
    audio_loader = workflow.nodes.get(AUDIO_LOADER_ID)
    checkpoint_loader = workflow.nodes.get(CHECKPOINT_LOADER_ID)
    if audio_loader is None or checkpoint_loader is None:
        return False

    return _is_supported_audio_loader(audio_loader) and _is_supported_checkpoint_loader(checkpoint_loader)


def _is_supported_applied_target(workflow: VibeWorkflow) -> bool:
    audio_loader = workflow.nodes.get(AUDIO_LOADER_ID)
    checkpoint_loader = workflow.nodes.get(CHECKPOINT_LOADER_ID)
    if audio_loader is None or checkpoint_loader is None:
        return False

    return _is_supported_audio_loader(audio_loader) and _is_lowvram_checkpoint_loader(checkpoint_loader)


def _is_supported_audio_loader(node) -> bool:
    if node.class_type != "LTXVAudioVAELoader":
        return False
    return _is_ltx_2_3_checkpoint(_node_checkpoint_name(node))


def _is_supported_checkpoint_loader(node) -> bool:
    if node.class_type != "CheckpointLoaderSimple":
        return False
    return _is_ltx_2_3_checkpoint(_node_checkpoint_name(node))


def _is_lowvram_checkpoint_loader(node) -> bool:
    if node.class_type != "LowVRAMCheckpointLoader":
        return False
    return _is_ltx_2_3_checkpoint(_node_checkpoint_name(node))


def _node_checkpoint_name(node) -> object:
    return node.inputs.get("ckpt_name") or node.inputs.get("ckpt_name.string") or node.widgets.get("widget_0")


def _is_ltx_2_3_checkpoint(value: object) -> bool:
    return isinstance(value, str) and value in {SOURCE_CHECKPOINT, FP8_CHECKPOINT}


def _update_node(
    workflow: VibeWorkflow,
    node_id: str,
    *,
    inputs: dict | None = None,
    widgets: dict | None = None,
) -> None:
    node = workflow.nodes.get(node_id)
    if node is None:
        return
    if inputs:
        for key, value in inputs.items():
            if isinstance(value, list):
                continue
            node.inputs[key] = value
    if widgets:
        node.widgets.update(widgets)


def _replace_clown_samplers(workflow: VibeWorkflow) -> None:
    for node in workflow.nodes.values():
        if node.class_type != CLOWN_SAMPLER_CLASS:
            continue
        node.class_type = "KSamplerSelect"
        node.inputs = {"sampler_name": PORTABLE_SAMPLER}
        node.widgets = {}


def _ensure_current_ltx_schema_defaults(workflow: VibeWorkflow) -> None:
    """Fill required API inputs added by current LTXVideo/Comfy output nodes."""
    _set_inputs(workflow, "3059", {"batch_size": 1})
    _set_inputs(workflow, "3980", {"frames_number": 9, "frame_rate": 8, "batch_size": 1})
    _set_inputs(workflow, "4981", {"longer_size": 384, "resize_type.longer_size": 384})
    _set_inputs(
        workflow,
        "4966",
        {"max_shift": 2.05, "base_shift": 0.95, "stretch": True, "terminal": 0.1},
    )
    _set_inputs(
        workflow,
        "4963",
        {"stg": 1.0, "perturb_attn": True, "rescale": 0.7, "skip_step": 0, "cross_attn": True},
    )
    _set_inputs(
        workflow,
        "4964",
        {
            "modality": "VIDEO",
            "stg": 1.0,
            "perturb_attn": True,
            "skip_step": 0,
            "cross_attn": True,
        },
    )
    if "4808" in workflow.nodes:
        node = workflow.nodes["4808"]
        node.inputs["skip_blocks"] = node.inputs.pop("widget_0", node.widgets.pop("widget_0", "28"))
    _set_inputs(workflow, "4982", {"last_frame_fix": False})
    _set_inputs(workflow, "4983", {"last_frame_fix": False})
    _drop_inputs(workflow, "4819", ("audio",))
    _drop_inputs(workflow, "4849", ("audio",))
    _set_inputs(workflow, "4823", {"format": "auto", "codec": "auto"})
    _set_inputs(workflow, "4852", {"format": "auto", "codec": "auto"})


def _set_inputs(workflow: VibeWorkflow, node_id: str, values: dict) -> None:
    node = workflow.nodes.get(node_id)
    if node is None:
        return
    node.inputs.update(values)


def _drop_inputs(workflow: VibeWorkflow, node_id: str, keys: tuple[str, ...]) -> None:
    node = workflow.nodes.get(node_id)
    if node is None:
        return
    key_set = set(keys)
    for key in keys:
        node.inputs.pop(key, None)
    workflow.edges = [
        edge
        for edge in workflow.edges
        if not (str(edge.to_node) == str(node_id) and edge.to_input in key_set)
    ]


patch = Patch("ltx_lowvram", applies_to, apply, rationale)


__all__ = ["COMFY_CONFIGURATION", "applies_to", "apply", "patch", "rationale"]
