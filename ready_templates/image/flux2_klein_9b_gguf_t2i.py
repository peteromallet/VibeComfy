# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, EmptyFlux2LatentImage, Flux2Scheduler, KSamplerSelect, RandomNoise, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAELoader

READY_METADATA = ReadyMetadata.build(
    capability='image',
    provenance={'source_path': 'ready_templates/sources/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json', 'source_id': 'image/flux2_klein_9b_gguf_t2i', 'upstream_source_id': 'flux2_klein_9b_gguf_t2i', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json', 'output_mode': 'ready_template', 'ready_id': 'image/flux2_klein_9b_gguf_t2i'},
)

# === Subgraph functions ===

def text_to_image_flux2_klein_9b(
    *,
    width: int,
    height: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
):
    """Text to Image (Flux.2 Klein 9B).

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in ready_templates/sources/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json.
    # vibecomfy source hash: sha256:24b6e274da9a4dc9cb71344032bb8cb28886bd7cf1d2a89d8ae9939a306b8739
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, EmptyFlux2LatentImage, CLIPTextEncodex2, RandomNoise, UNETLoader, CLIPLoader, VAELoader.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    flux2scheduler = Flux2Scheduler()
    emptyflux2latentimage = EmptyFlux2LatentImage()
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=653844576367526,
        control_after_generate='randomize',
    )

    negative = CLIPTextEncode(text='', clip=cliploader)
    positive = CLIPTextEncode(text=prompt, clip=cliploader)

    cfgguider = CFGGuider(
        cfg=5,
        model=unetloader,
        negative=negative,
        positive=positive,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=emptyflux2latentimage,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=flux2scheduler,
    )

    vaedecode = VAEDecode(samples=output, vae=vaeloader)

    return vaedecode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    edited = text_to_image_flux2_klein_9b(
        width=None,
        height=None,
        unet_name='flux-2-klein-base-9b-fp8.safetensors',
        clip_name='qwen_3_8b_fp8mixed.safetensors',
        vae_name='full_encoder_small_decoder.safetensors',
        prompt='',
    )

    saveimage = SaveImage(_id='9', filename_prefix='Flux2-Klein', images=edited)

    return wf.finalize({}, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

