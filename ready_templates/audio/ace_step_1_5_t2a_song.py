# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import ConditioningZeroOut, DualCLIPLoader, EmptyAceStep1_5LatentAudio, KSampler, ModelSamplingAuraFlow, SaveAudioMP3, TextEncodeAceStepAudio1_5, UNETLoader, VAEDecodeAudio, VAELoader


CLIP_NAME = 'qwen_0.6b_ace15.safetensors'
CLIP_NAME_2 = 'qwen_4b_ace15.safetensors'
DEFAULT_SEED = 561594583201063
GUIDE_STRENGTH = 1
UNET_NAME = 'acestep_v1.5_turbo.safetensors'
VAE_NAME = 'ace_1.5_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='3', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='audio',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['ace_1.5_vae.safetensors', 'acestep_v1.5_turbo.safetensors'], 'custom_nodes': ['EmptyAceStep1', 'TextEncodeAceStepAudio1']},
    provenance={'source_path': 'ready_templates/sources/official/audio/ace_step_1_5_t2a_song.json', 'source_id': 'audio/ace_step_1_5_t2a_song', 'upstream_source_id': 'ace_step_1_5_t2a_song', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/official/audio/ace_step_1_5_t2a_song.json', 'output_mode': 'ready_template', 'ready_id': 'audio/ace_step_1_5_t2a_song'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Loaders
    dualcliploader = DualCLIPLoader(
        _id='105',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type='ace',
        device='default',
    )

    vaeloader = VAELoader(_id='106', vae_name=VAE_NAME)

    emptyacestep1_5latentaudio = EmptyAceStep1_5LatentAudio(
        _id='122',
        seconds=2.0,
        widget_0=2,
    )

    unetloader = UNETLoader(_id='125', unet_name=UNET_NAME)
    modelsamplingauraflow = ModelSamplingAuraFlow(_id='78', shift=3, model=unetloader)

    textencodeacestepaudio1_5 = TextEncodeAceStepAudio1_5(
        _id='124',
        tags='synthwave, techno, synthpop, futuristic, electro, with liquid drum & bass drive.\nRestless, confident, dreamy mood at 128 BPM.\nAnalog bass, pulsating arps, percussive synth stabs, gated drums.\nQuick build,  then explosive drum burst, then clean fade.\nBreathy, rhythmic female vocals, minimal emotion, metallic echo.',
        lyrics='Verse\nNeon rain on my screen,\nDreams compile in silver sheen.\nNo weight, just motion,\nI’m plugged into emotion.\n\nChorus\nComfy Cloud — breathing light,\nCode and color, spark and wire.\nDrift through data, feel alive,\nIn your circuits, I arrive.',
        seed=DEFAULT_SEED,
        duration=2.0,
        timesignature='4',
        language='en',
        keyscale='E minor',
        cfg_scale=1.5,
        clip=dualcliploader,
    )

    conditioningzeroout = ConditioningZeroOut(
        _id='47',
        conditioning=textencodeacestepaudio1_5,
    )

    # Sampling
    ksampler = KSampler(
        _id='3',
        seed=DEFAULT_SEED,
        steps=1,
        cfg=GUIDE_STRENGTH,
        sampler_name='euler',
        latent_image=emptyacestep1_5latentaudio,
        model=modelsamplingauraflow,
        negative=conditioningzeroout,
        positive=textencodeacestepaudio1_5,
    )

    vaedecodeaudio = VAEDecodeAudio(_id='123', samples=ksampler, vae=vaeloader)

    # Outputs
    saveaudiomp3 = SaveAudioMP3(
        _id='59',
        filename_prefix='audio/vibecomfy_ace_step_smoke',
        audio=vaedecodeaudio,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveaudiomp3, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one', filename_prefix='audio/vibecomfy_ace_step_smoke')

