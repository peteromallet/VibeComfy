# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGNorm, CLIPLoader, ComfySwitchNode, KSampler, LoadImage, LoraLoaderModelOnly, ModelSamplingAuraFlow, SaveImage, TextEncodeQwenImageEdit, UNETLoader, VAEDecode, VAEEncode, VAELoader


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='78', field='image', default='image_qwen_image_edit_input_image.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image',
    inputs=PUBLIC_INPUT_METADATA,
    provenance={'source_path': 'ready_templates/sources/official/edit/qwen_image_edit.json', 'source_id': 'edit/qwen_image_edit', 'upstream_source_id': 'qwen_image_edit', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/official/edit/qwen_image_edit.json', 'output_mode': 'ready_template', 'ready_id': 'edit/qwen_image_edit'},
)

# === Subgraph functions ===

def qwen_image_edit(
    *,
    image,
    prompt: str,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    lora_name: str,
    enable_turbo_mode: bool,
):
    """Qwen-Image-Edit - single-image variant.

    Materialized from subgraph 74a8e1e2-9cb8-4112-978e-06ce1b5793f1 in ready_templates/sources/official/edit/qwen_image_edit.json.
    # vibecomfy source hash: sha256:b7fc773a3b338bd4ce58cdc36f425635b40eb71bc0eb73b9f007ec3160c52b36
    Inner nodes: VAELoader, TextEncodeQwenImageEditx2, CFGNorm, ModelSamplingAuraFlow, VAEDecode, CLIPLoader, VAEEncode, LoraLoaderModelOnly, UNETLoader, KSampler, ComfySwitchNodex3.
    """

    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type='qwen_image', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)
    comfyswitchnode_2 = ComfySwitchNode(switch=False)
    comfyswitchnode_3 = ComfySwitchNode(switch=False)

    textencodeqwenimageedit = TextEncodeQwenImageEdit(
        prompt=prompt,
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    textencodeqwenimageedit_2 = TextEncodeQwenImageEdit(
        prompt='',
        clip=cliploader,
        image=image,
        vae=vaeloader,
    )

    vaeencode = VAEEncode(pixels=image, vae=vaeloader)
    loraloadermodelonly = LoraLoaderModelOnly(lora_name=lora_name, model=unetloader)

    comfyswitchnode = ComfySwitchNode(
        switch=False,
        on_false=unetloader,
        on_true=loraloadermodelonly,
    )

    modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=comfyswitchnode)
    cfgnorm = CFGNorm(widget_0=1, model=modelsamplingauraflow)

    ksampler = KSampler(
        seed=344147753686358,
        sampler_name='euler',
        steps=comfyswitchnode_3,
        cfg=comfyswitchnode_2,
        latent_image=vaeencode,
        model=cfgnorm,
        negative=textencodeqwenimageedit_2,
        positive=textencodeqwenimageedit,
    )

    vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    image, _ = LoadImage(_id='78', image='image_qwen_image_edit_input_image.png')

    qwen_image_edit_result = qwen_image_edit(
        image=image,
        prompt='Remove all UI text elements from the image. Keep the feeling that the characters and scene are in water. Also, remove the green UI elements at the bottom.',
        unet_name='qwen_image_edit_fp8_e4m3fn.safetensors',
        clip_name='qwen_2.5_vl_7b_fp8_scaled.safetensors',
        vae_name='qwen_image_vae.safetensors',
        lora_name='Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
        enable_turbo_mode=None,
    )

    saveimage = SaveImage(_id='60', images=qwen_image_edit_result)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='ComfyUI')

