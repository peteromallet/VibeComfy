# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXFloatToInt, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode


DEFAULT_PROMPT = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.5
LTX_2_3_22B_DEV_SAFETENSORS = 'ltx-2.3-22b-dev.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    requirements={'models': ['euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-dev.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors']},
    custom_node_packs={'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json', 'source_id': 'LTX-2.3_T2V_I2V_Two_Stage_Distilled', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json', 'source_ref': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json', 'source_kind': 'raw_json', 'indexed_id': None, 'workflow_source_id': 'LTX-2.3_T2V_I2V_Two_Stage_Distilled', 'workflow_source_type': 'api', 'raw_workflow_shape': 'ui', 'source_hash': 'sha256:2ea553cfa291cae680ef2b5834cbdb0f7b3e7ef5a81fe431953a18402931a7ba', 'workflow_shape': {'nodes': 43, 'runtime_nodes': 41, 'helper_nodes': 2, 'edges': 56, 'inputs': 3, 'outputs': 1}, 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_two_stage'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(image='example.png', unused_widget_1='image')
    model, clip, vae = CheckpointLoaderSimple(ckpt_name=LTX_2_3_22B_DEV_SAFETENSORS)
    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=LTX_2_3_22B_DEV_SAFETENSORS)
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )

    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
    primitivestring = raw_call('PrimitiveString', '4979', value='')

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        text_encoder='comfy_gemma_3_12B_it.safetensors',
        ckpt_name=LTX_2_3_22B_DEV_SAFETENSORS,
        device='default',
    )

    manualsigmas = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
    primitiveboolean = raw_call('PrimitiveBoolean', '4987', value=True)
    primitiveint = raw_call('PrimitiveInt', '4988', value=121, control_after_generate='fixed')
    primitivefloat = raw_call('PrimitiveFloat', '4989', value=24)

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text='A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.',
        clip=ltxavtextencoderloader,
    )

    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=ltxavtextencoderloader)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=960,
        height=544,
        length=primitiveint,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=GUIDE_STRENGTH_2,
        model=model,
    )

    gemmaapitextencode = GemmaAPITextEncode(
        ckpt_name=LTX_2_3_22B_DEV_SAFETENSORS,
        enhance_prompt=LTX_2_3_22B_DEV_SAFETENSORS,
        api_key=primitivestring,
    )

    gemmaapitextencode_2 = GemmaAPITextEncode(
        ckpt_name=LTX_2_3_22B_DEV_SAFETENSORS,
        enhance_prompt=False,
        prompt=DEFAULT_PROMPT,
        api_key=primitivestring,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale longer dimension',
        scale_method='lanczos',
        unused_widget_1=1536,
        input=image,
    )

    ltxfloattoint = LTXFloatToInt(rounding=0, a=primitivefloat)

    positive, negative = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagemasknode)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=primitiveint,
        frame_rate=ltxfloattoint,
        audio_vae=ltxvaudiovaeloader,
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        strength=0.7,
        bypass=primitiveboolean,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=loraloadermodelonly,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=loraloadermodelonly,
        negative=negative,
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoconditiononly,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vae,
    )

    ltxvimgtovideoconditiononly_2 = LTXVImgToVideoConditionOnly(
        bypass=primitiveboolean,
        image=resizeimagemasknode,
        latent=ltxvlatentupsampler,
        vae=vae,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoconditiononly_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        unused_widget_4='auto',
        unused_widget_5='auto',
        latents=video_latent_ltxv,
        vae=vae,
    )

    createvideo = CreateVideo(
        fps=primitivefloat,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode,
    )

    # Outputs
    savevideo = SaveVideo(filename_prefix='output', video=createvideo)


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='example.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'width': InputSpec(node=emptyltxvlatentvideo, field='width', default=960, type='INT'),
        'height': InputSpec(node=emptyltxvlatentvideo, field='height', default=544, type='INT'),
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=cliptextencode, field='text', default='A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.', type='STRING', required=True, media_semantics='text'),
        'negative_prompt': InputSpec(node=cliptextencode_2, field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

