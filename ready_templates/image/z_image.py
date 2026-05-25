# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, EmptySD3LatentImage, KSampler, ModelSamplingAuraFlow, SaveImage, UNETLoader, VAEDecode, VAELoader


CLIP_NAME = 'qwen_3_4b.safetensors'
DEFAULT_PROMPT = 'A fashion photography work full of surreal romanticism, using a low-angle upward shooting composition, with a clear light blue sky as the background, and the visual focus concentrated on the fantasy blue vegetation and the model walking through it.\n\nThe vegetation in the picture is processed into varying shades of blue, from light ice blue to deep cobalt blue. The textures of the leaves and branches are delicate and realistic. The warm brown tree trunks form a sharp contrast with the cool blue leaves, resembling a dreamy forest from another world. An African-American model wearing a yellow and white vertical striped long dress walks slowly on the sand. The warm tones of the dress echo with the surrounding cool blue vegetation. The noon sun casts clear shadows on the sand, enhancing the sense of space and reality in the picture.\n\nThe entire scene, with its clean and transparent colors and fantasy settings, not only exudes the vastness of the natural wilderness but also presents a quiet and poetic high-fashion sense due to the surreal vegetation.'
DEFAULT_SEED = 770044821593082
GUIDE_STRENGTH = 4.0
UNET_NAME = 'z_image_bf16.safetensors'
VAE_NAME = 'ae.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors', subdir='vae'),
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors', subdir='diffusion_models'),
}


OUTPUT_SPEC = OutputSpec(name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image',
    models=MODELS,
    provenance={'source_workflow': 'workflow_corpus/official/image/z_image.json'},
)

# === Subgraph functions ===

def text_to_image_z_image_base(
    *,
    width: int,
    height: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
    steps: int,
    cfg: float,
):
    """Text to Image(Z-Image-Base).

    Materialized from subgraph 9b9009e4-2d3d-445f-9be5-6063f465757e in workflow_corpus/official/image/z_image.json.
    # vibecomfy source hash: sha256:e8c21c13102d1e08b36437f1e19264764f618f4685007a0b10300175c5318d29
    Inner nodes: CLIPTextEncodex2, EmptySD3LatentImage, VAELoader, CLIPLoader, VAEDecode, ModelSamplingAuraFlow, UNETLoader, KSampler, MarkdownNote.
    """

    cliploader = CLIPLoader(type_='lumina2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)
    unetloader = UNETLoader(unet_name=unet_name)
    emptysd3latentimage = EmptySD3LatentImage(width=width, height=height)
    markdownnote = raw_call('MarkdownNote', '76', widget_0='- Steps: 30～50\n- cfg:  3～5')
    positive = CLIPTextEncode(text=prompt, clip=cliploader)
    modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=unetloader)
    negative = CLIPTextEncode(text='', clip=cliploader)

    ksampler = KSampler(
        seed=770044821593082,
        sampler_name='res_multistep',
        unused_widget_1='randomize',
        steps=steps,
        cfg=cfg,
        latent_image=emptysd3latentimage,
        model=modelsamplingauraflow,
        negative=negative,
        positive=positive,
    )

    vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    unetloader = UNETLoader(unet_name=UNET_NAME)
    cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='lumina2')
    vaeloader = VAELoader(vae_name=VAE_NAME)

    emptysd3latentimage = EmptySD3LatentImage(
        width=public('width', default=1024),
        height=public('height', default=1024),
    )

    modelsamplingauraflow = ModelSamplingAuraFlow(shift=3, model=unetloader)

    # Conditioning
    positive = CLIPTextEncode(
        text=public('prompt', default=DEFAULT_PROMPT),
        clip=cliploader,
    )

    negative = CLIPTextEncode(
        text=public('negative_prompt', default=''),
        clip=cliploader,
    )

    ksampler = KSampler(
        seed=public('seed', default=DEFAULT_SEED),
        steps=public('steps', default=25),
        cfg=GUIDE_STRENGTH,
        sampler_name='res_multistep',
        latent_image=emptysd3latentimage,
        model=modelsamplingauraflow,
        negative=negative,
        positive=positive,
    )

    # Decode
    vaedecode = VAEDecode(samples=ksampler, vae=vaeloader)

    # Outputs
    saveimage = SaveImage(filename_prefix='z-image', images=vaedecode)


    wf.register_input('model', unetloader.node.id, 'unet_name', UNET_NAME)
    return wf.finalize({}, filename_prefix='z-image', spec=OUTPUT_SPEC)

