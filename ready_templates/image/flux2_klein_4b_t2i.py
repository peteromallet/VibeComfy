# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPLoader, CLIPTextEncode, ConditioningZeroOut, EmptyFlux2LatentImage, Flux2Scheduler, KSamplerSelect, RandomNoise, SamplerCustomAdvanced, SaveImage, UNETLoader, VAEDecode, VAELoader


DEFAULT_PROMPT = 'A hedgehog wearing a tiny party hat surrounded by confetti, early digital camera style, slight noise, flash photography, candid moment, 2000s digicam aesthetic, festive birthday celebration atmosphere\n'
WIDGET__NAME = 'flux-2-klein-base-4b.safetensors'
WIDGET__NAME_2 = 'qwen_3_4b.safetensors'
WIDGET__NAME_3 = 'flux2-vae.safetensors'
WIDGET__NAME_4 = 'flux-2-klein-4b.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='image',
    provenance={'source_path': 'ready_templates/sources/official/image/flux2_klein_4b_t2i.json', 'source_id': 'image/flux2_klein_4b_t2i', 'upstream_source_id': 'flux2_klein_4b_t2i', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/official/image/flux2_klein_4b_t2i.json', 'output_mode': 'ready_template', 'ready_id': 'image/flux2_klein_4b_t2i'},
)

# === Subgraph functions ===

def text_to_image_flux2_klein_4b(
    *,
    value: int,
    value_1: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
):
    """Text to Image (Flux.2 Klein 4B).

    Materialized from subgraph 7b34ab90-36f9-45ba-a665-71d418f0df18 in ready_templates/sources/official/image/flux2_klein_4b_t2i.json.
    # vibecomfy source hash: sha256:629ead7cab536eafae6292fca730a3374e922bb025849d25e36fe6857fd92c58
    Inner nodes: KSamplerSelect, Flux2Scheduler, CFGGuider, SamplerCustomAdvanced, VAEDecode, EmptyFlux2LatentImage, CLIPTextEncodex2, RandomNoise, UNETLoader, CLIPLoader, VAELoader.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    flux2scheduler = Flux2Scheduler()
    emptyflux2latentimage = EmptyFlux2LatentImage()
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)
    randomnoise = RandomNoise(control_after_generate='randomize')
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


def text_to_image_flux2_klein_4b_distilled(
    *,
    value: int,
    value_1: int,
    unet_name: str,
    clip_name: str,
    vae_name: str,
    prompt: str,
):
    """Text to Image (Flux.2 Klein 4B Distilled).

    Materialized from subgraph a67caa28-5f85-4917-8396-36004960dd30 in ready_templates/sources/official/image/flux2_klein_4b_t2i.json.
    # vibecomfy source hash: sha256:be70dd108a908bd4271722bf059d5c2d25e56e38bfe5f286b86df90c8692ac10
    Inner nodes: KSamplerSelect, SamplerCustomAdvanced, VAEDecode, EmptyFlux2LatentImage, RandomNoise, UNETLoader, CLIPLoader, VAELoader, CFGGuider, ConditioningZeroOut, CLIPTextEncode, Flux2Scheduler.
    """

    ksamplerselect = KSamplerSelect(sampler_name='euler')
    flux2scheduler = Flux2Scheduler(steps=4)
    emptyflux2latentimage = EmptyFlux2LatentImage()
    unetloader = UNETLoader(unet_name=unet_name)
    cliploader = CLIPLoader(type='flux2', clip_name=clip_name)
    vaeloader = VAELoader(vae_name=vae_name)

    randomnoise = RandomNoise(
        noise_seed=432262096973490,
        control_after_generate='randomize',
    )

    positive = CLIPTextEncode(text=prompt, clip=cliploader)
    conditioningzeroout = ConditioningZeroOut(conditioning=positive)

    cfgguider = CFGGuider(
        cfg=1,
        model=unetloader,
        negative=conditioningzeroout,
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

    edited = text_to_image_flux2_klein_4b(
        value=1024,
        value_1=1024,
        unet_name='flux-2-klein-base-4b.safetensors',
        clip_name='qwen_3_4b.safetensors',
        vae_name='flux2-vae.safetensors',
        prompt='',
    )

    edited_2 = text_to_image_flux2_klein_4b_distilled(
        value=1024,
        value_1=1024,
        unet_name='flux-2-klein-4b.safetensors',
        clip_name='qwen_3_4b.safetensors',
        vae_name='flux2-vae.safetensors',
        prompt='',
    )

    saveimage = SaveImage(_id='9', filename_prefix='Flux2-Klein', images=edited)
    saveimage_2 = SaveImage(_id='78', filename_prefix='Flux2-Klein', images=edited_2)

    return wf.finalize({}, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Flux2-Klein')

