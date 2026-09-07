# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.ltxvideo import GuiderParameters, LTXFloatToInt, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode, MultimodalGuider
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.resolution import resolution


CKPT_NAME = 'ltx-2.3-22b-dev.safetensors'
DEFAULT_FPS = 24.0
DEFAULT_FRAMES = 121
DEFAULT_PROMPT = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_PROMPT_2 = 'A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.'
DEFAULT_SEED = 42
DEFAULT_SEED_2 = 43
FIXED = 'fixed'
GUIDE_STRENGTH = 7
GUIDE_STRENGTH_2 = 3
GUIDE_STRENGTH_3 = 1
GUIDE_STRENGTH_4 = 0.5
GUIDE_STRENGTH_5 = 0.2
LORA_NAME = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
TEXT_ENCODER_NAME = 'comfy_gemma_3_12B_it.safetensors'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='2004', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='3059', field='width', default=960, type='INT'),
    'height': InputSpec(node='3059', field='height', default=544, type='INT'),
    'frames': InputSpec(node='3059', field='length', default=DEFAULT_FRAMES, type='INT'),
    'seed': InputSpec(node='4814', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'fps': InputSpec(node='4819', field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node='2483', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='2612', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['ltx-2.3-22b-dev.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors']},
    custom_node_packs={'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json', 'source_id': 'video/ltx2_3_t2v', 'upstream_source_id': 'ltx2_3_single_stage_distilled_full', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_t2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='2004', image='example.png')

    # Sampling
    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='3059',
        width=960,
        height=544,
        length=DEFAULT_FRAMES,
    )

    # Loaders
    model, _, vae = CheckpointLoaderSimple(_id='3940', ckpt_name=CKPT_NAME)
    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='4010', ckpt_name=CKPT_NAME)

    randomnoise = RandomNoise(
        _id='4814',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
    )

    ksamplerselect = KSamplerSelect(_id='4831', sampler_name='euler_ancestral_cfg_pp')

    randomnoise_2 = RandomNoise(
        _id='4832',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
    )

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        _id='4960',
        text_encoder=TEXT_ENCODER_NAME,
        ckpt_name=CKPT_NAME,
        device='default',
    )

    guiderparameters = GuiderParameters(
        _id='4963',
        cfg=GUIDE_STRENGTH,
        modality='AUDIO',
        modality_scale=3,
    )

    clownsampler_beta = raw_call('ClownSampler_Beta', '4967',
        widget_0=0.25,
        widget_1='exponential/res_2s',
        widget_2=94,
        widget_3='fixed',
        widget_4=True,
    )

    manualsigmas = ManualSigmas(
        _id='4971',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    ltxfloattoint = LTXFloatToInt(_id='4985', rounding=0, a=24.0)

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='2483',
        text=DEFAULT_PROMPT_2,
        clip=ltxavtextencoderloader,
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='2612',
        text=DEFAULT_PROMPT,
        clip=ltxavtextencoderloader,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        _id='3980',
        frames_number=121,
        frame_rate=ltxfloattoint,
        audio_vae=ltxvaudiovaeloader,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='4922',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_4,
        model=model,
    )

    guiderparameters_2 = GuiderParameters(
        _id='4964',
        cfg=GUIDE_STRENGTH_2,
        modality_scale=3,
        rescale=0.9,
        parameters=guiderparameters,
    )

    loraloadermodelonly_2 = LoraLoaderModelOnly(
        _id='4968',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_5,
        model=model,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='4981',
        resize_type='scale longer dimension',
        scale_method='lanczos',
        input=image,
    )

    positive, negative = LTXVConditioning(
        _id='1241',
        frame_rate=24.0,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='3336',
        img_compression=18,
        image=resizeimagemasknode,
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        _id='3159',
        strength=0.7,
        bypass=True,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    multimodalguider = MultimodalGuider(
        _id='4808',
        widget_0='28',
        model=loraloadermodelonly_2,
        negative=negative,
        parameters=guiderparameters_2,
        positive=positive,
    )

    cfgguider = CFGGuider(
        _id='4828',
        cfg=GUIDE_STRENGTH_3,
        model=loraloadermodelonly,
        negative=negative,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='4528',
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoconditiononly,
    )

    output_2, _ = SamplerCustomAdvanced(
        _id='4829',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    ltxvscheduler = LTXVScheduler(_id='4966', steps=15, latent=ltxvconcatavlatent)

    output, _ = SamplerCustomAdvanced(
        _id='4802',
        guider=multimodalguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=clownsampler_beta.out(0),
        sigmas=ltxvscheduler,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(
        _id='4845',
        av_latent=output_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(_id='4824', av_latent=output)

    ltxvaudiovaedecode_2 = LTXVAudioVAEDecode(
        _id='4848',
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_2,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        _id='4982',
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        latents=video_latent_2,
        vae=vae,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='4818',
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent,
    )

    createvideo_2 = CreateVideo(
        _id='4849',
        fps=DEFAULT_FPS,
        audio=ltxvaudiovaedecode_2,
        images=ltxvtiledvaedecode,
    )

    ltxvtiledvaedecode_2 = LTXVTiledVAEDecode(
        _id='4983',
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        latents=video_latent,
        vae=vae,
    )

    createvideo = CreateVideo(
        _id='4819',
        fps=DEFAULT_FPS,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode_2,
    )

    # Outputs
    savevideo_2 = SaveVideo(_id='4852', filename_prefix='output_D', video=createvideo_2)
    savevideo = SaveVideo(_id='4823', filename_prefix='output_F', video=createvideo)

    apply_ltx_lowvram(wf)
    resolution(384, 256, 9).apply(wf)
    ensure_custom_nodes(wf, READY_METADATA.get("requirements", {}).get("custom_nodes", []))
    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output_F')

