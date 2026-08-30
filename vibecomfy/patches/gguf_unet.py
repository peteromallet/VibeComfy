from __future__ import annotations

from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeWorkflow


GGUF_MODEL = "flux-2-klein-9b-Q4_K_M.gguf"


def applies_to(workflow: VibeWorkflow) -> bool:
    return any(
        node.class_type == "UNETLoader"
        and _is_flux2_9b(node.inputs.get("unet_name") or node.widgets.get("widget_0"))
        and node.widgets.get("widget_0") != GGUF_MODEL
        for node in workflow.nodes.values()
    )


def apply(workflow: VibeWorkflow) -> VibeWorkflow:
    for node in workflow.nodes.values():
        if node.class_type == "UNETLoader" and _is_flux2_9b(node.inputs.get("unet_name") or node.widgets.get("widget_0")):
            node.class_type = "UnetLoaderGGUF"
            if "unet_name" in node.inputs:
                node.inputs["unet_name"] = GGUF_MODEL
            elif "widget_0" in node.widgets:
                node.widgets["widget_0"] = GGUF_MODEL
        if node.class_type == "VAELoader" and (
            node.inputs.get("vae_name") == "full_encoder_small_decoder.safetensors"
            or node.widgets.get("widget_0") == "full_encoder_small_decoder.safetensors"
        ):
            if "vae_name" in node.inputs:
                node.inputs["vae_name"] = "flux2-klein-9b-vae.safetensors"
            else:
                node.widgets["widget_0"] = "flux2-klein-9b-vae.safetensors"
    workflow.finalize_metadata()
    ensure_custom_nodes(workflow, ("ComfyUI-GGUF",))
    return workflow


def rationale(workflow: VibeWorkflow) -> str:
    return "UNETLoader can use the public Flux 2 Klein GGUF quantization."


def _is_flux2_9b(value: object) -> bool:
    return isinstance(value, str) and "flux-2-klein" in value and "9b" in value.lower()


patch = Patch("gguf_unet", applies_to, apply, rationale)


__all__ = ["GGUF_MODEL", "applies_to", "apply", "patch", "rationale"]
