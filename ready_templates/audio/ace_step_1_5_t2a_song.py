# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import ConditioningZeroOut, DualCLIPLoader, KSampler, SaveAudioMP3, UNETLoader, VAEDecodeAudio, VAELoader


CLIP_NAME = 'qwen_0.6b_ace15.safetensors'
CLIP_NAME_2 = 'qwen_4b_ace15.safetensors'
DEFAULT_SEED = 561594583201063
GUIDE_STRENGTH = 1
UNET_NAME = 'acestep_v1.5_turbo.safetensors'
VAE_NAME = 'ace_1.5_vae.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_0.6b_ace15.safetensors', sha256='fd4590c82153b8ddb67e15a2e7aaa8afa8b83a858c8a9b82a4831063156aa7a7', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=1191588248, subdir='text_encoders'),
    'text_encoder_2': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/text_encoders/qwen_4b_ace15.safetensors', sha256='ffe5ffb855086c2ab55e467e9859fb01894781020a0376484dd19de166b79873', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=8379154232, subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/vae/ace_1.5_vae.safetensors', sha256='6de92e3a862acd287e08b024ac90f0783a8635451b728721a33ff03565bcb2bb', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=337431732, subdir='vae'),
    'diffusion_model': ModelAsset(url='https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files/resolve/main/split_files/diffusion_models/acestep_v1.5_turbo.safetensors', sha256='3f6e0797fad420a39bd33979eb6e840e30989e34a3794e843d23b60ec6e422d7', hf_revision='54b2ef4d8af5582f54c7e6b84c22b679a194bc4b', size_bytes=4787825604, subdir='diffusion_models'),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_audio_song',
    models=MODELS,
    output_prefix='audio/vibecomfy_ace_step_smoke',
    requirements={'custom_nodes': ['EmptyAceStep1', 'TextEncodeAceStepAudio1']},
    approach='ACE-Step 1.5 text-to-audio song generation',
    runtime_note='Official subgraph materialized to API-shaped nodes for VibeComfy smoke execution.',
    smoke_duration_seconds=2,
    subgraph_materialized=True,
    provenance={'source_workflow': 'workflow_corpus/official/audio/ace_step_1_5_t2a_song.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type_='ace',
        device='default',
    )

    vaeloader = VAELoader(vae_name=VAE_NAME)
    emptyacestep1_5latentaudio = raw_call('EmptyAceStep1.5LatentAudio', '122', seconds=2)
    unetloader = UNETLoader(unet_name=UNET_NAME)

    textencodeacestepaudio1_5 = raw_call('TextEncodeAceStepAudio1.5', '124',
        tags='synthwave, short instrumental',
        lyrics='Verse\nTiny signal in the night.',
        seed=DEFAULT_SEED,
        duration=2,
        bpm=120,
        timesignature='4',
        language='en',
        keyscale='E minor',
        cfg_scale=1.5,
        temperature=0,
        top_p=0.85,
        min_p=0.9,
        clip=dualcliploader,
        model=unetloader,
    )

    conditioningzeroout = ConditioningZeroOut(conditioning=textencodeacestepaudio1_5)

    ksampler = KSampler(
        seed=DEFAULT_SEED,
        steps=1,
        cfg=GUIDE_STRENGTH,
        sampler_name='euler',
        latent_image=emptyacestep1_5latentaudio,
        model=textencodeacestepaudio1_5,
        negative=conditioningzeroout,
        positive=textencodeacestepaudio1_5,
    )

    vaedecodeaudio = VAEDecodeAudio(samples=ksampler, vae=vaeloader)

    # Outputs
    saveaudiomp3 = SaveAudioMP3(
        filename_prefix='audio/vibecomfy_ace_step_smoke',
        audio=vaedecodeaudio,
    )


    wf.register_input('model', unetloader.node.id, 'unet_name', UNET_NAME)

    PUBLIC_INPUTS = {
        'model': InputSpec(node=unetloader, field='unet_name', default=UNET_NAME),
        'seed': InputSpec(node=textencodeacestepaudio1_5, field='seed', default=DEFAULT_SEED),
        'steps': InputSpec(node=ksampler, field='steps', default=1),
        'tags': InputSpec(node=textencodeacestepaudio1_5, field='tags', default='synthwave, short instrumental'),
        'lyrics': InputSpec(node=textencodeacestepaudio1_5, field='lyrics', default='Verse\nTiny signal in the night.'),
        'duration': InputSpec(node=textencodeacestepaudio1_5, field='duration', default=2),
        'bpm': InputSpec(node=textencodeacestepaudio1_5, field='bpm', default=120),
        'seed_2': InputSpec(node=ksampler, field='seed', default=DEFAULT_SEED),
        'cfg': InputSpec(node=ksampler, field='cfg', default=GUIDE_STRENGTH),
        'sampler_name': InputSpec(node=ksampler, field='sampler_name', default='euler'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=saveaudiomp3, output_type='SaveAudioMP3', name='audio', artifact_kind='audio', mime_type='audio/mpeg', expected_cardinality='one')

