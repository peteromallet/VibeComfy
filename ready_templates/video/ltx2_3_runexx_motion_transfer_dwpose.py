# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyAudio, EmptyLTXVLatentVideo, GetImageSize, ImageBlend, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideoFFmpeg, VHS_VideoCombine


CPU = 'cpu'
CROP = 'crop'
DEFAULT_SEED = 42
DEFAULT_SEED_2 = 43
FIXED = 'fixed'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 0.71
GUIDE_STRENGTH_3 = 2.5
LANCZOS = 'lanczos'
LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS = 'ltx-2.3_text_projection_bf16.safetensors'
NEAREST_EXACT = 'nearest-exact'
SCALE_BY_MULTIPLIER = 'scale by multiplier'

READY_METADATA = ReadyMetadata.build(
    capability='dwpose_motion_transfer',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'comfyui_controlnet_aux', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'comfyui_controlnet_aux', 'source': 'git', 'version': 'unknown', 'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='DWPose body motion transfer',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json'},
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 94e8f3a0-557f-4580-93a0-f762c7b0d076 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json.
    # vibecomfy source hash: sha256:898bc6d12bae585d9ee58c0f24e682c5fb3c8ae14cedcf53faa938213af409c1
    Inner nodes: TextGenerateLTX2Prompt, PrimitiveStringMultiline, LazySwitchKJ, StringConcatenate, Reroutex2.
    """

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    reroute = raw_call('Reroute', '1932', _outputs=('',))
    reroute_2 = raw_call('Reroute', '1933', _outputs=('',))

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline,
        string_b=reroute_2.out(0),
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        clip=clip,
        image=image,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_2.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute.out(0),
    )

    return lazyswitchkj

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(
        image='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg',
    )

    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)

    manualsigmas = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
    manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
    vaeloader = VAELoader(vae_name='LTX23_video_vae_bf16.safetensors')

    dualcliploader = DualCLIPLoader(
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )

    vaeloader_2 = VAELoader(vae_name='taeltx2_3.safetensors')

    unetloader = UNETLoader(
        unet_name='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
    )

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )

    reroute = raw_call('Reroute', '1932', _outputs=('',))
    reroute_2 = raw_call('Reroute', '1933', _outputs=('',))
    primitiveboolean = raw_call('PrimitiveBoolean', '5198', value=False)
    primitivefloat = raw_call('PrimitiveFloat', '5199', value=8)
    primitiveboolean_2 = raw_call('PrimitiveBoolean', '5201', value=False)
    intconstant = INTConstant(value=10)
    intconstant_2 = INTConstant(value=736)
    intconstant_3 = INTConstant(value=1280)

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1='gemma-3-12b-it-Q2_K.gguf',
        clip_name2=LTX_2_3_TEXT_PROJECTION_BF16_SAFETENSORS,
        type_='sdxl',
    )

    unetloadergguf = UnetLoaderGGUF(
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )

    primitivestringmultiline = PrimitiveStringMultiline(
        value='highly detailed, monochrime colors. Make this image come alive with fluid motion. \n\nA make boxer. \n\nHe is dancing in sync to the music ',
    )

    loadaudio = LoadAudio(audio='(Verse).mp3')

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        tile_size=544,
        temporal_size=4096,
        temporal_overlap=4,
    )

    primitivefloat_2 = raw_call('PrimitiveFloat', '5298', value=8)
    primitivefloat_3 = raw_call('PrimitiveFloat', '5299', value=8)
    primitiveboolean_3 = raw_call('PrimitiveBoolean', '5303', value=True)

    primitivestringmultiline_2 = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text='low contrast, washed out, text, subtitles, logo, still image, still video, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=dualcliploader,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale longer dimension',
        scale_method=LANCZOS,
        input=image,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    float, int, boolean = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': intconstant, 'variables.b': primitivefloat},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='a',
        **{'variables.a': primitivefloat},
    )

    stringconcatenate = StringConcatenate(
        widget_0='',
        widget_1='',
        string_a=primitivestringmultiline_2,
        string_b=reroute_2.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagemasknode)

    model, latent_downscale_factor = LTXICLoRALoaderModelOnly(
        lora_name='LTX\\LTX-2\\IC-Lora\\ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors',
        strength_model=GUIDE_STRENGTH_2,
        model=loraloadermodelonly,
    )

    image_load, mask_load, audio, video_info = VHS_LoadVideoFFmpeg(
        force_rate=primitivefloat,
        frame_load_cap=int,
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        input=resizeimagemasknode,
    )

    simplemath_ = raw_call('SimpleMath+', '5034',
        _outputs=('INT', 'FLOAT'),
        value='a*32',
        a=latent_downscale_factor,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        device=CPU,
        width=intconstant_2,
        height=intconstant_3,
        image=image_load,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='disabled',
        model=model,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        widget_0='',
        widget_1=256,
        widget_2='off',
        widget_3=False,
        clip=dualcliploader,
        image=resizeimagemasknode_2,
        prompt=stringconcatenate,
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute_2.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute.out(0),
    )

    resizeimagemasknode_3 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        input=image_image,
    )

    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)
    cliptextencode_2 = CLIPTextEncode(text=lazyswitchkj, clip=dualcliploader)

    resizeimagemasknode_4 = ResizeImageMaskNode(
        resize_type='scale shorter dimension',
        scale_method=LANCZOS,
        input=resizeimagemasknode_3,
    )

    width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode_3)

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    dwpreprocessor = raw_call('DWPreprocessor', '4986',
        detect_hand='enable',
        detect_body='enable',
        detect_face='enable',
        bbox_detector='yolox_l.onnx',
        pose_estimator='dw-ll_ucoco_384_bs5.torchscript.pt',
        scale_stick_for_xinsr_cn='disable',
        image=resizeimagemasknode_4,
    )

    depthanythingpreprocessor = raw_call('DepthAnythingPreprocessor', '5114',
        widget_0='depth_anything_vitl14.pth',
        widget_1=512,
        image=resizeimagemasknode_4,
    )

    power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '5275',
        _outputs=('MODEL', 'CLIP'),
        model=ltx2attentiontunerpatch,
    )

    positive, negative = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    imageblend = ImageBlend(
        widget_0=0.5,
        widget_1='multiply',
        image1=dwpreprocessor,
        image2=depthanythingpreprocessor.out(0),
    )

    ltx2_nag = LTX2_NAG(
        model=power_lora_loader__rgthree_.out('MODEL'),
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_3,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    comfyswitchnode = ComfySwitchNode(
        switch=False,
        on_false=dwpreprocessor,
        on_true=imageblend,
    )

    image_image_2, width_image, height_image, mask_image_2 = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=CROP,
        device=CPU,
        width=width_get,
        height=height_get,
        divisible_by=simplemath_.out('INT'),
        image=comfyswitchnode,
    )

    width_get_2, height_get_2, batch_size_get = GetImageSize(image=image_image_2)

    # Outputs
    vhs_videocombine = VHS_VideoCombine(images=image_image_2)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width_get_2,
        height=height_get_2,
        length=batch_size_get,
    )

    solidmask = SolidMask(
        value=0,
        widget_1=512,
        widget_2=512,
        height=height_get_2,
        width=width_get_2,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=batch_size_get,
        frame_rate=int_simple,
        audio_vae=ltxvaudiovaeloader,
    )

    float_simple_2, int_simple_2, boolean_simple_2 = SimpleCalculatorKJ(
        expression='a / b ',
        **{'variables.a': batch_size_get, 'variables.b': primitivefloat},
    )

    float_simple_3, int_simple_3, boolean_simple_3 = SimpleCalculatorKJ(
        expression='a / b',
        **{'variables.a': batch_size_get, 'variables.b': primitivefloat},
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        bypass=primitiveboolean,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=0,
        widget_1=60,
        audio=loadaudio,
        duration=float_simple_2,
    )

    emptyaudio = EmptyAudio(widget_0=60, duration=float_simple_3)

    positive_ltx, negative_ltx, latent = LTXAddVideoICLoRAGuide(
        crop=1,
        use_tiled_encode='disabled',
        tile_size=128,
        tile_overlap=32,
        strength=primitivefloat_3,
        image=image_image_2,
        latent=ltxvimgtovideoconditiononly,
        latent_downscale_factor=latent_downscale_factor,
        negative=negative,
        positive=positive,
        vae=vaeloader,
    )

    comfyswitchnode_2 = ComfySwitchNode(
        switch=None,
        widget_0=True,
        on_false=emptyaudio,
        on_true=audio,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_3,
        model=ltx2_nag,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    comfyswitchnode_3 = ComfySwitchNode(
        switch=False,
        on_false=comfyswitchnode_2,
        on_true=trimaudioduration,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=comfyswitchnode_3,
        audio_vae=ltxvaudiovaeloader,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    comfyswitchnode_4 = ComfySwitchNode(
        widget_0=True,
        on_false=ltxvemptylatentaudio,
        on_true=setlatentnoisemask,
        switch=primitiveboolean_3,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=comfyswitchnode_4,
        video_latent=latent,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    positive_ltxv, negative_ltxv, latent_ltxv = LTXVCropGuides(
        latent=video_latent,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        widget_0=0.7,
        widget_1=False,
        bypass=primitiveboolean,
        image=resizeimagemasknode,
        latent=latent_ltxv,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplace,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider,
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

    positive_ltxv_2, negative_ltxv_2, latent_ltxv_2 = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=negative,
        positive=positive,
    )

    vaedecodetiled_2 = VAEDecodeTiled(
        tile_size=544,
        temporal_size=4096,
        temporal_overlap=4,
        samples=latent_ltxv_2,
        vae=vaeloader,
    )

    comfyswitchnode_5 = ComfySwitchNode(
        widget_0=True,
        on_false=ltxvaudiovaedecode,
        on_true=comfyswitchnode_3,
        switch=primitiveboolean_3,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        frame_rate=primitivefloat,
        audio=comfyswitchnode_5,
        images=vaedecodetiled_2,
    )


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default='highly detailed, monochrime colors. Make this image come alive with fluid motion. \n\nA make boxer. \n\nHe is dancing in sync to the music ', type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

