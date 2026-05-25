# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, GetImageRangeFromBatch, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoraLoaderModelOnly, ManualSigmas, MaskToImage, ModelSamplingSD3, PreviewImage, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAEDecodeTiled, VAEEncode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import BlockifyMask, GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVAudioVideoMask, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.ltxvideo import LTXVAddLatentGuide, LTXVPreprocessMasks, LTXVSetVideoLatentNoiseMasks
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideoFFmpeg, VHS_VideoCombine, VHS_VideoInfo


DEFAULT = 'default'
DEFAULT_SEED = 790774741312584
DEFAULT_SEED_2 = 43
GEMMA_3_12B_IT_FP4_MIXED_SAFETENSORS = 'gemma_3_12B_it_fp4_mixed.safetensors'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS = 'ltx-2.3_text_projection_bf16.safetensors'
NEAREST_EXACT = 'nearest-exact'
SCALE_BY_MULTIPLIER = 'scale by multiplier'

READY_METADATA = ReadyMetadata.build(
    capability='voice_to_lipsync_video',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='custom-audio lip-sync / voice-to-video',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json'},
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    prompt,
    switch: bool,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph e428c881-c48b-4849-9158-8311b4df27c7 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json.
    # vibecomfy source hash: sha256:34428474561155b940e03271c17290d050b940f2e46c0ccfd9f83db2a53ddaae
    Inner nodes: Reroute, TextGenerateLTX2Prompt, ComfySwitchNode, StringConcatenate, PrimitiveStringMultiline.
    """

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    reroute = raw_call('Reroute', '785', _outputs=('',))

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline,
        string_b=reroute.out(0),
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    comfyswitchnode = ComfySwitchNode(
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=switch,
    )

    return comfyswitchnode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    randomnoise = RandomNoise(
        noise_seed=DEFAULT_SEED,
        control_after_generate='randomize',
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(temporal_size=4096)
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    intconstant = INTConstant(value=3)

    # Inputs
    primitivefloat = raw_call('PrimitiveFloat', '214', value=8)

    randomnoise_2 = RandomNoise(
        noise_seed=DEFAULT_SEED_2,
        control_after_generate='fixed',
    )

    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
    vaeloader = VAELoader(vae_name='LTX23_video_vae_bf16.safetensors')

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )

    dualcliploader = DualCLIPLoader(
        clip_name1=GEMMA_3_12B_IT_FP4_MIXED_SAFETENSORS,
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='ltxv',
        device=DEFAULT,
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )

    vaeloader_2 = VAELoader(vae_name='taeltx2_3.safetensors')

    unetloader = UNETLoader(
        unet_name='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
    )

    unetloadergguf = UnetLoaderGGUF(
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1='gemma-3-12b-it-Q2_K.gguf',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='sdxl',
    )

    manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    primitivestringmultiline = PrimitiveStringMultiline(
        value='Cinematic video woman wearing colorful make-up, with colorful  light creating a creative scene. \n\nShe talks with perfect lip-sync movements to the attached audio. Her mouth and lips moves as she talks. \n \nThe camera slowly moves away from the woman, showing her full body. She is standing at a  colorful theatre scene doing a victorian era play. ',
    )

    reroute = raw_call('Reroute', '496')
    intconstant_2 = INTConstant(value=650)
    primitiveboolean = raw_call('PrimitiveBoolean', '594', value=False)

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        text_encoder=GEMMA_3_12B_IT_FP4_MIXED_SAFETENSORS,
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
        device=DEFAULT,
    )

    reroute_2 = raw_call('Reroute', '785', _outputs=('',))
    primitivefloat_2 = raw_call('PrimitiveFloat', '814', value=8)
    loadaudio = LoadAudio(audio='e9318ca1-5e2b-47aa-8397-f4538b0151b0.wav')

    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '861',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )

    primitivestringmultiline_2 = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    # Conditioning
    negative = CLIPTextEncode(
        text='text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=ltxavtextencoderloader,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=intconstant_2,
        images=reroute.out(0),
    )

    cliptextencode = CLIPTextEncode(
        text=' distorted sound, saturated sound, loud sound',
        clip=ltxavtextencoderloader,
    )

    float, int = ComfyMathExpression(expression='a', **{'values.a': primitivefloat})
    image, mask, audio, video_info = VHS_LoadVideoFFmpeg(force_rate=primitivefloat)

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline_2,
        string_b=reroute_2.out(0),
    )

    source_fps_, source_frame_count_, source_duration_, source_width_, source_height_, loaded_fps_, loaded_frame_count_, loaded_duration_, loaded_width_, loaded_height_ = VHS_VideoInfo(
        video_info=video_info,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='disabled',
        model=loraloadermodelonly,
    )

    float_simple, int_simple, boolean = SimpleCalculatorKJ(
        expression='(a > c) or (b > c) ',
        **{'variables.a': loaded_width_, 'variables.b': loaded_height_, 'variables.c': intconstant_2},
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

    float_simple_2, int_simple_2, boolean_simple = SimpleCalculatorKJ(
        expression='(a/b)+c',
        **{'variables.a': loaded_frame_count_, 'variables.b': primitivefloat, 'variables.c': intconstant},
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=resizeimagesbylongeredge,
        switch=boolean,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=0,
        widget_1=40,
        audio=loadaudio,
        duration=float_simple_2,
    )

    power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '660',
        _outputs=('MODEL', 'CLIP'),
        model=ltx2attentiontunerpatch,
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '860',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    image_get, width, height, count = GetImageSizeAndCount(image=lazyswitchkj)

    image_image, width_image, height_image, mask_image = ImageResizeKJv2(
        upscale_method='nearest-exact',
        keep_proportion='crop',
        divisible_by=64,
        device='cpu',
        width=width,
        height=height,
        image=image_get,
    )

    modelsamplingsd3 = ModelSamplingSD3(
        shift=13,
        model=power_lora_loader__rgthree_.out('MODEL'),
    )

    ltx2_nag = LTX2_NAG(
        model=power_lora_loader__rgthree_.out('MODEL'),
        nag_cond_audio=cliptextencode,
        nag_cond_video=negative,
    )

    comfyswitchnode = ComfySwitchNode(
        switch=True,
        on_false=trimaudioduration,
        on_true=melbandroformersampler.out(0),
    )

    basicscheduler = BasicScheduler(
        scheduler=1,
        steps=1,
        widget_1=15,
        model=modelsamplingsd3,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        input=image_image,
    )

    image_get_2, mask_get = GetImageRangeFromBatch(images=image_image)

    image_get_3, width_get, height_get, count_get = GetImageSizeAndCount(
        image=image_image,
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        scale_method=NEAREST_EXACT,
        input=image_image,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=comfyswitchnode,
        audio_vae=ltxvaudiovaeloader,
    )

    facesegment = raw_call('FaceSegment', '761',
        widget_0=True,
        widget_1=True,
        widget_10=True,
        widget_11=True,
        widget_12=False,
        widget_13=False,
        widget_14=False,
        widget_15=512,
        widget_16=0,
        widget_17=10,
        widget_18=False,
        widget_19='Alpha',
        widget_2=False,
        widget_20='#222222',
        widget_3=True,
        widget_4=True,
        widget_5=False,
        widget_6=True,
        widget_7=True,
        widget_8=True,
        widget_9=True,
        images=resizeimagemasknode_2,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_get_2,
    )

    vaeencode = VAEEncode(pixels=resizeimagemasknode, vae=vaeloader)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=count_get,
        frame_rate=int,
        audio_vae=ltxvaudiovaeloader,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a/b',
        **{'values.a': count_get, 'values.b': primitivefloat},
    )

    image_get_4, mask_get_2 = GetImageRangeFromBatch(images=resizeimagemasknode_2)

    image_get_5, mask_get_3 = GetImageRangeFromBatch(
        start_index=-1,
        images=resizeimagemasknode,
    )

    solidmask = SolidMask(
        value=0,
        widget_1=512,
        widget_2=512,
        height=height_get,
        width=width_get,
    )

    ltxvpreprocess = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge_2,
    )

    float_comfy_2, int_comfy_2 = ComfyMathExpression(
        expression='a+b',
        **{'values.a': float_comfy, 'values.b': intconstant},
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        widget_4=True,
        clip=ltxavtextencoderloader,
        image=resizeimagesbylongeredge_2,
        prompt=stringconcatenate,
    )

    blockifymask = BlockifyMask(block_size=12, widget_1='cpu', masks=facesegment.out(1))
    vaeencode_2 = VAEEncode(pixels=image_get_5, vae=vaeloader)
    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    comfyswitchnode_2 = ComfySwitchNode(
        on_false=reroute_2.out(0),
        on_true=textgenerateltx2prompt,
        switch=primitiveboolean,
    )

    resizeimagemasknode_3 = ResizeImageMaskNode(
        resize_type='match size',
        scale_method=NEAREST_EXACT,
        input=blockifymask,
        **{'resize_type.match': image_get_4},
    )

    masktoimage = MaskToImage(mask=blockifymask)
    positive = CLIPTextEncode(text=comfyswitchnode_2, clip=ltxavtextencoderloader)

    ltxvpreprocessmasks = LTXVPreprocessMasks(
        widget_0=False,
        widget_1=False,
        widget_2='max',
        widget_3=0,
        widget_4=True,
        widget_5=0.5,
        widget_6=1,
        masks=resizeimagemasknode_3,
        vae=vaeloader,
    )

    image_get_6, mask_get_4 = GetImageRangeFromBatch(images=masktoimage)

    positive_ltxv, negative_ltxv = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=negative,
        positive=positive,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    # Outputs
    previewimage = PreviewImage(images=image_get_6)

    ltxvsetvideolatentnoisemasks = LTXVSetVideoLatentNoiseMasks(
        masks=ltxvpreprocessmasks,
        samples=vaeencode,
    )

    video_latent, audio_latent = LTXVAudioVideoMask(
        max_length='pad',
        widget_0=24,
        widget_1=0,
        widget_2=15,
        widget_4=10000,
        widget_6='add',
        audio_end_time=float_comfy_2,
        audio_latent=ltxvemptylatentaudio,
        video_end_time=float_comfy_2,
        video_fps=primitivefloat,
        video_latent=ltxvsetvideolatentnoisemasks,
        video_start_time=float_comfy,
    )

    positive_ltxv_2, negative_ltxv_2, latent = LTXVAddLatentGuide(
        widget_0=-1,
        widget_1=0.7,
        guiding_latent=vaeencode_2,
        latent=video_latent,
        latent_idx=count_get,
        negative=negative_ltxv,
        positive=positive_ltxv,
        strength=primitivefloat_2,
        vae=vaeloader,
    )

    comfyswitchnode_3 = ComfySwitchNode(
        switch=True,
        on_false=audio_latent,
        on_true=setlatentnoisemask,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        widget_0=0.7,
        widget_1=False,
        image=resizeimagesbylongeredge_2,
        latent=latent,
        vae=vaeloader,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=comfyswitchnode_3,
        video_latent=ltxvimgtovideoinplace,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

    positive_ltxv_3, negative_ltxv_3, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        widget_0=1,
        widget_1=False,
        image=resizeimagesbylongeredge_2,
        latent=latent_ltxv,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent_ltxv_2, audio_latent_ltxv_2 = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv_2,
    )

    positive_ltxv_4, negative_ltxv_4, latent_ltxv_2 = LTXVCropGuides(
        latent=video_latent_ltxv_2,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    vaedecode = VAEDecode(samples=latent_ltxv_2, vae=vaeloader)

    vhs_videocombine = VHS_VideoCombine(
        frame_rate=primitivefloat,
        audio=ltxvaudiovaedecode,
        images=vaedecode,
    )


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default='Cinematic video woman wearing colorful make-up, with colorful  light creating a creative scene. \n\nShe talks with perfect lip-sync movements to the attached audio. Her mouth and lips moves as she talks. \n \nThe camera slowly moves away from the woman, showing her full body. She is standing at a  colorful theatre scene doing a victorian era play. ', type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=previewimage, output_type='PreviewImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

