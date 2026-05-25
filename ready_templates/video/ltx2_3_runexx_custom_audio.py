# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2_NAG, LTXVChunkFeedForward, SimpleCalculatorKJ
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


DEFAULT_SEED = 420
DEFAULT_SEED_2 = 43
FIXED = 'fixed'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS = 'ltx-2.3_text_projection_bf16.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='custom_audio_to_video',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='custom audio conditioning',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    manualsigmas = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')

    # Inputs
    image, mask = LoadImage(image='liam-neeson-in-retribution-ra.jpg')
    vaeloader = VAELoader(vae_name='LTX23_video_vae_bf16.safetensors')

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name='ltx-2.3-spatial-upscaler-x2-1.0.safetensors',
    )

    dualcliploader = DualCLIPLoader(
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )

    primitivefloat = raw_call('PrimitiveFloat', '285', value=8)
    primitiveboolean = raw_call('PrimitiveBoolean', '290', value=False)
    intconstant = INTConstant(value=10)
    intconstant_2 = INTConstant(value=1280)
    intconstant_3 = INTConstant(value=736)

    unetloader = UNETLoader(
        unet_name='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
    )

    vaeloader_2 = VAELoader(vae_name='taeltx2_3.safetensors')

    unetloadergguf = UnetLoaderGGUF(
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1='gemma-3-12b-it-Q2_K.gguf',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='sdxl',
    )

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    primitivestringmultiline_2 = PrimitiveStringMultiline(
        value='Make this image come alive with fluid motion. \n\nA man with an intimidating expression speaks with expressive body language and gesticulations. \n\nHe looks at the vewer and talks, he says  : "If you say a bad word about LTX 2 point 3, i will find you.... and i will kill you" ',
    )

    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '370',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )

    loadaudio = LoadAudio(audio='ComfyUI_00128_.mp3')
    reroute = raw_call('Reroute', '379')
    manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

    manualsigmas_3 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text='blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud',
        clip=dualcliploader,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method='nearest-exact',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        width=intconstant_2,
        height=intconstant_3,
        image=image,
    )

    float, int, boolean = SimpleCalculatorKJ(
        expression='1+ 8*(round(a*b)/8)',
        a=intconstant,
        b=primitivefloat,
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='a',
        **{'variables.a': primitivefloat},
    )

    stringconcatenate = StringConcatenate(
        string_b='',
        widget_0='',
        string_a=primitivestringmultiline,
    )

    solidmask = SolidMask(
        value=0,
        widget_1=512,
        widget_2=512,
        height=intconstant_3,
        width=intconstant_2,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=image_image,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=int,
        frame_rate=int_simple,
        audio_vae=ltxvaudiovaeloader,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(model=loraloadermodelonly)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        clip=dualcliploader,
        image=image_image,
        prompt=primitivestringmultiline_2,
    )

    float_simple_2, int_simple_2, boolean_simple_2 = SimpleCalculatorKJ(
        expression='a/b',
        a=int,
        b=primitivefloat,
    )

    power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '301',
        _outputs=('MODEL', 'CLIP'),
        model=ltxvchunkfeedforward,
    )

    cliptextencode_2 = CLIPTextEncode(text=textgenerateltx2prompt, clip=dualcliploader)
    ltxvpreprocess = LTXVPreprocess(img_compression=33, image=resizeimagesbylongeredge)
    width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode)

    trimaudioduration = TrimAudioDuration(
        widget_0=0,
        widget_1=8,
        audio=loadaudio,
        duration=float_simple_2,
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '371',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    positive, negative = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width_get,
        height=height_get,
        length=int,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        bypass=primitiveboolean,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    ltx2_nag = LTX2_NAG(
        model=power_lora_loader__rgthree_.out('MODEL'),
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    comfyswitchnode = ComfySwitchNode(
        switch=False,
        on_false=trimaudioduration,
        on_true=melbandroformersampler.out(0),
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=comfyswitchnode,
        audio_vae=ltxvaudiovaeloader,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    comfyswitchnode_2 = ComfySwitchNode(
        switch=True,
        on_false=ltxvemptylatentaudio,
        on_true=setlatentnoisemask,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=comfyswitchnode_2,
        video_latent=ltxvimgtovideoinplace,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas_3,
    )

    ltxvscheduler = LTXVScheduler(steps=1, latent=ltxvconcatavlatent)
    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        bypass=primitiveboolean,
        image=resizeimagesbylongeredge,
        latent=video_latent,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        temporal_size=4096,
        samples=video_latent_ltxv,
        vae=vaeloader,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=primitivefloat,
        audio=trimaudioduration,
        images=vaedecodetiled,
    )


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
        'image': InputSpec(node=image, field='image', default='liam-neeson-in-retribution-ra.jpg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________', type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

