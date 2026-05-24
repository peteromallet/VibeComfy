# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, LazySwitchKJ, LoadVideosFromFolder, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CKPT_NAME = 'LTX23_audio_vae_bf16.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CLIP_NAME_3 = 'gemma-3-12b-it-Q2_K.gguf'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
DELIMITER = '\\'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LORA_NAME = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
STRING_A = 'MusicVideo'
STRING_B = ''
UNET_NAME = 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
UNET_NAME_2 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_NAME = 'LTX23_video_vae_bf16.safetensors'
VAE_NAME_2 = 'taeltx2_3.safetensors'
WIDGET_0 = 'vae'
WIDGET_0_10 = 'enhance_prompt'
WIDGET_0_11 = 'ref_image'
WIDGET_0_12 = 'upscale_model'
WIDGET_0_13 = 'negative_base'
WIDGET_0_14 = 'positive_base'
WIDGET_0_15 = 'vae_tiny'
WIDGET_0_16 = 'model_with_lora'
WIDGET_0_17 = 'model'
WIDGET_0_18 = 'width_downscaled'
WIDGET_0_19 = 'height_downscaled'
WIDGET_0_2 = 'audio_original'
WIDGET_0_20 = 'image_strength'
WIDGET_0_21 = 'initial_frames_count'
WIDGET_0_22 = 'foldername'
WIDGET_0_23 = 'temp_name'
WIDGET_0_24 = 'final_frames'
WIDGET_0_3 = 'height'
WIDGET_0_4 = 'vae_audio'
WIDGET_0_5 = 'width'
WIDGET_0_6 = 'clip'
WIDGET_0_7 = 'frames'
WIDGET_0_8 = 'fps'
WIDGET_0_9 = 'window_sec_01'
WIDGET__NAME = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='music_video_multiscene',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='low-RAM multi-scene music video',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json'},
)

# === Subgraph functions ===

def prompt_enhancer_3bd4eeb9(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:2c0c8593ff69b7ffbd92312db4d5f155112d0b48eb3ecf388d2ad4d7d1737b8c
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
        widget_4=True,
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


def prompt_enhancer(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 2413a8aa-1f77-466f-8508-ed07fa6ac302 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:4a910ac8f10be7c3c0a4b5575b2423d3b5e148804cebedb9bec75411b50bd2a3
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    reroute = raw_call('Reroute', '2121', _outputs=('',))
    reroute_2 = raw_call('Reroute', '2122', _outputs=('',))

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

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video_c4106aee(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph c4106aee-ad7a-4925-972b-6f5b3d34db6e in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:616ce3085f8a0cebb1b11464ed3b75e46b9370b0bcb449056d9aab848681d985
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, SamplerCustomAdvancedx2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 2413a8aa-1f77-466f-8508-ed07fa6ac302, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2.
    """

    getnode = raw_call('GetNode', '2209', _outputs=('MODEL',), widget_0='model')
    getnode_2 = raw_call('GetNode', '2217', _outputs=('AUDIO',), widget_0='audio')
    getnode_3 = raw_call('GetNode', '2218', _outputs=('VAE',), widget_0='vae_audio')
    getnode_4 = raw_call('GetNode', '2220', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_5 = raw_call('GetNode', '2221', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_6 = raw_call('GetNode', '2228', _outputs=('FLOAT',), widget_0='fps')
    getnode_7 = raw_call('GetNode', '2242', _outputs=('VAE',), widget_0='vae')
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    getnode_8 = raw_call('GetNode', '2245', _outputs=('SAMPLER',), widget_0='sampler')
    getnode_9 = raw_call('GetNode', '2246', _outputs=('SIGMAS',), widget_0='sigmas')
    getnode_10 = raw_call('GetNode', '2280', _outputs=('CLIP',), widget_0='clip')
    getnode_11 = raw_call('GetNode', '2282', _outputs=('BOOLEAN',), widget_0='enhance_prompt')
    getnode_12 = raw_call('GetNode', '2286', _outputs=('VAE',), widget_0='vae')
    solidmask = SolidMask(value=0)

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    getnode_13 = raw_call('GetNode', '2295', _outputs=('VAE',), widget_0='vae')
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    getnode_14 = raw_call('GetNode', '2300', _outputs=('MODEL',), widget_0='model')
    getnode_15 = raw_call('GetNode', '2305', _outputs=('CONDITIONING',), widget_0='positive_base')
    getnode_16 = raw_call('GetNode', '2306', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_17 = raw_call('GetNode', '2308', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_18 = raw_call('GetNode', '2310', _outputs=('LATENT_UPSCALE_MODEL',), widget_0='upscale_model')
    getnode_19 = raw_call('GetNode', '2316', _outputs=('SAMPLER',), widget_0='sampler_2')
    getnode_20 = raw_call('GetNode', '2317', _outputs=('SIGMAS',), widget_0='sigmas_2')
    getnode_21 = raw_call('GetNode', '2320', _outputs=('INT',), widget_0='width_downscaled')
    getnode_22 = raw_call('GetNode', '2321', _outputs=('INT',), widget_0='height_downscaled')

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    reroute = raw_call('Reroute', '2328', _outputs=('',))
    reroute_2 = raw_call('Reroute', '4200', _outputs=('',))
    reroute_3 = raw_call('Reroute', '4442', _outputs=('',))
    getnode_23 = raw_call('GetNode', '4746', _outputs=('AUDIO',), widget_0='audio_original')
    reroute_4 = raw_call('Reroute', '4748', _outputs=('',))

    float, int = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_3.out(0), 'values.b': getnode_6.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_2.out('AUDIO'),
        duration=reroute.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    prompt_enhancer_result = prompt_enhancer(
        clip=getnode_10.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    float_simple, int_simple, boolean = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute.out(0), 'variables.b': getnode_6.out('FLOAT')},
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode_3.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '2256',
        _outputs=('output',),
        widget_0='10.92',
        anything=float,
    )

    positive = CLIPTextEncode(text=prompt_enhancer_result, clip=getnode_10.out('CLIP'))

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_21.out('INT'),
        height=getnode_22.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode.out('MODEL'),
        negative=getnode_4.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_14.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_12.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_5.out('FLOAT')},
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_8.out('SAMPLER'),
        sigmas=getnode_9.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent_ltxv,
        upscale_model=getnode_18.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_13.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_13.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_17.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_19.out('SAMPLER'),
        sigmas=getnode_20.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)
    vaedecode = VAEDecode(samples=video_latent, vae=getnode_7.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float_simple_2, int_simple_2, boolean_simple = SimpleCalculatorKJ(
        **{'variables.a': reroute_2.out(0), 'variables.b': count},
    )

    return int_simple_2, vaedecode, trimaudioduration_2


def total_duration():
    """Total duration.

    Materialized from subgraph 5e410bb1-405a-4d3d-808b-8f5f29426943 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:1a4bf7220d6b539ecffe2f409af0554bbf4bf1e9c53fe8b0dd60ba3b7d4dd68c
    Inner nodes: GetNodex5, SimpleCalculatorKJ.
    """

    getnode = raw_call('GetNode', '3715', _outputs=('FLOAT',), widget_0='window_sec_01')
    getnode_2 = raw_call('GetNode', '3716', _outputs=('FLOAT',), widget_0='window_sec_02')
    getnode_3 = raw_call('GetNode', '3717', _outputs=('FLOAT',), widget_0='window_sec_03')
    getnode_4 = raw_call('GetNode', '3718', _outputs=('FLOAT',), widget_0='window_sec_04')
    getnode_5 = raw_call('GetNode', '3719', _outputs=('FLOAT',), widget_0='window_sec_05')

    float, int, boolean = SimpleCalculatorKJ(
        expression='a + b + c + d + e + 2\n',
        **{'variables.a': getnode.out('FLOAT'), 'variables.b': getnode_2.out('FLOAT'), 'variables.c': getnode_3.out('FLOAT'), 'variables.d': getnode_4.out('FLOAT'), 'variables.e': getnode_5.out('FLOAT')},
    )

    return float


def prompt_enhancer_97b9884d(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 97b9884d-4a32-4b0d-ad19-be662c1c2002 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:0ff255269ae95a4f63d13a3adaa2255c614d7a3cc476f01a9a7d3966151db13d
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    reroute = raw_call('Reroute', '5060', _outputs=('',))
    reroute_2 = raw_call('Reroute', '5061', _outputs=('',))

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

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

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 17238add-9973-482f-8fa3-248d4ed29886 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:07c51e2e6f74221aca2bec1c34ad7fcc45b81ff017489864bb6228b21318c95f
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 97b9884d-4a32-4b0d-ad19-be662c1c2002, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    getnode = raw_call('GetNode', '5000', _outputs=('VAE',), widget_0='vae_audio')
    getnode_2 = raw_call('GetNode', '5001', _outputs=('CLIP',), widget_0='clip')
    getnode_3 = raw_call('GetNode', '5002', _outputs=('VAE',), widget_0='vae')
    solidmask = SolidMask(value=0)
    getnode_4 = raw_call('GetNode', '5004', _outputs=('MODEL',), widget_0='model')
    getnode_5 = raw_call('GetNode', '5005', _outputs=('SAMPLER',), widget_0='sampler')
    getnode_6 = raw_call('GetNode', '5006', _outputs=('SIGMAS',), widget_0='sigmas')
    getnode_7 = raw_call('GetNode', '5007', _outputs=('VAE',), widget_0='vae')
    getnode_8 = raw_call('GetNode', '5008', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_9 = raw_call('GetNode', '5009', _outputs=('LATENT_UPSCALE_MODEL',), widget_0='upscale_model')
    getnode_10 = raw_call('GetNode', '5013', _outputs=('MODEL',), widget_0='model')
    getnode_11 = raw_call('GetNode', '5014', _outputs=('CONDITIONING',), widget_0='positive_base')
    getnode_12 = raw_call('GetNode', '5015', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_13 = raw_call('GetNode', '5016', _outputs=('SAMPLER',), widget_0='sampler_2')
    getnode_14 = raw_call('GetNode', '5017', _outputs=('SIGMAS',), widget_0='sigmas_2')
    getnode_15 = raw_call('GetNode', '5018', _outputs=('VAE',), widget_0='vae')
    getnode_16 = raw_call('GetNode', '5020', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_17 = raw_call('GetNode', '5021', _outputs=('BOOLEAN',), widget_0='enhance_prompt')
    getnode_18 = raw_call('GetNode', '5022', _outputs=('AUDIO',), widget_0='audio')
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    reroute = raw_call('Reroute', '5032', _outputs=('',))
    getnode_19 = raw_call('GetNode', '5033', _outputs=('FLOAT',), widget_0='fps')
    reroute_2 = raw_call('Reroute', '5034', _outputs=('',))
    getnode_20 = raw_call('GetNode', '5039', _outputs=('INT',), widget_0='width_downscaled')
    getnode_21 = raw_call('GetNode', '5040', _outputs=('INT',), widget_0='height_downscaled')
    reroute_3 = raw_call('Reroute', '5043', _outputs=('',))
    reroute_4 = raw_call('Reroute', '5045', _outputs=('',))

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    getnode_22 = raw_call('GetNode', '5049', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_23 = raw_call('GetNode', '5050', _outputs=('AUDIO',), widget_0='audio_original')

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_2.out(0), 'values.b': getnode_19.out('FLOAT')},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute_3.out(0), 'variables.b': getnode_19.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_18.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    prompt_enhancer_97b9884d_result = prompt_enhancer_97b9884d(
        clip=getnode_2.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    positive = CLIPTextEncode(
        text=prompt_enhancer_97b9884d_result,
        clip=getnode_2.out('CLIP'),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '5031',
        _outputs=('output',),
        widget_0='20.88',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_20.out('INT'),
        height=getnode_21.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode_4.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_3.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_22.out('FLOAT')},
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_10.out('MODEL'),
        negative=getnode_12.out('CONDITIONING'),
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_5.out('SAMPLER'),
        sigmas=getnode_6.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=getnode_9.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_7.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_7.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_8.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_13.out('SAMPLER'),
        sigmas=getnode_14.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=getnode_15.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': reroute.out(0), 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2


def prompt_enhancer_cc5ea718(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph cc5ea718-db6a-47c7-83cf-7d9a8442ba99 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:414324a132df36895098b984c5f98eec8a2e3c69bda4fb38062d251a780166ad
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    reroute = raw_call('Reroute', '5135', _outputs=('',))
    reroute_2 = raw_call('Reroute', '5136', _outputs=('',))

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

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

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video_a3fb563d(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph a3fb563d-4711-4225-9210-fbe61b1bd79d in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:27352869b3f659e4f05c7ff2c5289bd899f7077adc4b6988a1453679afa19035
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, cc5ea718-db6a-47c7-83cf-7d9a8442ba99, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    getnode = raw_call('GetNode', '5075', _outputs=('VAE',), widget_0='vae_audio')
    getnode_2 = raw_call('GetNode', '5076', _outputs=('CLIP',), widget_0='clip')
    getnode_3 = raw_call('GetNode', '5077', _outputs=('VAE',), widget_0='vae')
    solidmask = SolidMask(value=0)
    getnode_4 = raw_call('GetNode', '5079', _outputs=('MODEL',), widget_0='model')
    getnode_5 = raw_call('GetNode', '5080', _outputs=('SAMPLER',), widget_0='sampler')
    getnode_6 = raw_call('GetNode', '5081', _outputs=('SIGMAS',), widget_0='sigmas')
    getnode_7 = raw_call('GetNode', '5082', _outputs=('VAE',), widget_0='vae')
    getnode_8 = raw_call('GetNode', '5083', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_9 = raw_call('GetNode', '5084', _outputs=('LATENT_UPSCALE_MODEL',), widget_0='upscale_model')
    getnode_10 = raw_call('GetNode', '5088', _outputs=('MODEL',), widget_0='model')
    getnode_11 = raw_call('GetNode', '5089', _outputs=('CONDITIONING',), widget_0='positive_base')
    getnode_12 = raw_call('GetNode', '5090', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_13 = raw_call('GetNode', '5091', _outputs=('SAMPLER',), widget_0='sampler_2')
    getnode_14 = raw_call('GetNode', '5092', _outputs=('SIGMAS',), widget_0='sigmas_2')
    getnode_15 = raw_call('GetNode', '5093', _outputs=('VAE',), widget_0='vae')
    getnode_16 = raw_call('GetNode', '5095', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_17 = raw_call('GetNode', '5096', _outputs=('BOOLEAN',), widget_0='enhance_prompt')
    getnode_18 = raw_call('GetNode', '5097', _outputs=('AUDIO',), widget_0='audio')
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    reroute = raw_call('Reroute', '5107', _outputs=('',))
    getnode_19 = raw_call('GetNode', '5108', _outputs=('FLOAT',), widget_0='fps')
    reroute_2 = raw_call('Reroute', '5109', _outputs=('',))
    getnode_20 = raw_call('GetNode', '5114', _outputs=('INT',), widget_0='width_downscaled')
    getnode_21 = raw_call('GetNode', '5115', _outputs=('INT',), widget_0='height_downscaled')
    reroute_3 = raw_call('Reroute', '5118', _outputs=('',))
    reroute_4 = raw_call('Reroute', '5120', _outputs=('',))

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    getnode_22 = raw_call('GetNode', '5124', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_23 = raw_call('GetNode', '5125', _outputs=('AUDIO',), widget_0='audio_original')

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_2.out(0), 'values.b': getnode_19.out('FLOAT')},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute_3.out(0), 'variables.b': getnode_19.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_18.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    prompt_enhancer_cc5ea718_result = prompt_enhancer_cc5ea718(
        clip=getnode_2.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    positive = CLIPTextEncode(
        text=prompt_enhancer_cc5ea718_result,
        clip=getnode_2.out('CLIP'),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '5106',
        _outputs=('output',),
        widget_0='38.84',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_20.out('INT'),
        height=getnode_21.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode_4.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_3.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_22.out('FLOAT')},
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_10.out('MODEL'),
        negative=getnode_12.out('CONDITIONING'),
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_5.out('SAMPLER'),
        sigmas=getnode_6.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=getnode_9.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_7.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_7.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_8.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_13.out('SAMPLER'),
        sigmas=getnode_14.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=getnode_15.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': reroute.out(0), 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2


def prompt_enhancer_50a3ed96(
    *,
    clip,
    image,
    enable,
    prompt,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph 50a3ed96-aa61-4734-97cb-28cb47d171be in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:59946393626df05200ba41e42f6d6087be96f646df10e84df99a6d9e85b7ec4d
    Inner nodes: TextGenerateLTX2Prompt, LazySwitchKJ, Reroutex2, PrimitiveStringMultiline, StringConcatenate.
    """

    reroute = raw_call('Reroute', '5210', _outputs=('',))
    reroute_2 = raw_call('Reroute', '5211', _outputs=('',))

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

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

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=reroute.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute_2.out(0),
    )

    return lazyswitchkj


def generate_video_4acc9924(
    *,
    noise_seed: int,
    prompt,
    window_seconds,
    frames_count,
    ref_image,
):
    """Generate Video - single-image variant.

    Materialized from subgraph 4acc9924-c0bd-470a-b000-46c75e61d004 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json.
    # vibecomfy source hash: sha256:ea3c115b1cdb87be44e9b7a66c8310cc7368e5e06c053ad6b64f7e087eeafd53
    Inner nodes: GetNodex23, SolidMask, LTXVSeparateAVLatentx2, LTXVLatentUpsampler, CLIPTextEncode, LTXVAudioVAEEncode, CFGGuiderx2, SetLatentNoiseMask, LTXVConcatAVLatentx2, RandomNoisex2, easy showAnything, Reroutex4, SimpleCalculatorKJx2, GetImageSizeAndCount, VRAM_Debug, ComfyMathExpression, EmptyLTXVLatentVideo, TrimAudioDurationx2, VAEDecode, ResizeImageMaskNode, 50a3ed96-aa61-4734-97cb-28cb47d171be, LTXVPreprocess, ResizeImagesByLongerEdge, LTXVImgToVideoInplaceKJx2, SamplerCustomAdvancedx2.
    """

    getnode = raw_call('GetNode', '5150', _outputs=('VAE',), widget_0='vae_audio')
    getnode_2 = raw_call('GetNode', '5151', _outputs=('CLIP',), widget_0='clip')
    getnode_3 = raw_call('GetNode', '5152', _outputs=('VAE',), widget_0='vae')
    solidmask = SolidMask(value=0)
    getnode_4 = raw_call('GetNode', '5154', _outputs=('MODEL',), widget_0='model')
    getnode_5 = raw_call('GetNode', '5155', _outputs=('SAMPLER',), widget_0='sampler')
    getnode_6 = raw_call('GetNode', '5156', _outputs=('SIGMAS',), widget_0='sigmas')
    getnode_7 = raw_call('GetNode', '5157', _outputs=('VAE',), widget_0='vae')
    getnode_8 = raw_call('GetNode', '5158', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_9 = raw_call('GetNode', '5159', _outputs=('LATENT_UPSCALE_MODEL',), widget_0='upscale_model')
    getnode_10 = raw_call('GetNode', '5163', _outputs=('MODEL',), widget_0='model')
    getnode_11 = raw_call('GetNode', '5164', _outputs=('CONDITIONING',), widget_0='positive_base')
    getnode_12 = raw_call('GetNode', '5165', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_13 = raw_call('GetNode', '5166', _outputs=('SAMPLER',), widget_0='sampler_2')
    getnode_14 = raw_call('GetNode', '5167', _outputs=('SIGMAS',), widget_0='sigmas_2')
    getnode_15 = raw_call('GetNode', '5168', _outputs=('VAE',), widget_0='vae')
    getnode_16 = raw_call('GetNode', '5170', _outputs=('CONDITIONING',), widget_0='negative_base')
    getnode_17 = raw_call('GetNode', '5171', _outputs=('BOOLEAN',), widget_0='enhance_prompt')
    getnode_18 = raw_call('GetNode', '5172', _outputs=('AUDIO',), widget_0='audio')
    randomnoise = RandomNoise(control_after_generate='fixed', noise_seed=noise_seed)
    randomnoise_2 = RandomNoise(noise_seed=405, control_after_generate='fixed')
    reroute = raw_call('Reroute', '5182', _outputs=('',))
    getnode_19 = raw_call('GetNode', '5183', _outputs=('FLOAT',), widget_0='fps')
    reroute_2 = raw_call('Reroute', '5184', _outputs=('',))
    getnode_20 = raw_call('GetNode', '5189', _outputs=('INT',), widget_0='width_downscaled')
    getnode_21 = raw_call('GetNode', '5190', _outputs=('INT',), widget_0='height_downscaled')
    reroute_3 = raw_call('Reroute', '5193', _outputs=('',))
    reroute_4 = raw_call('Reroute', '5195', _outputs=('',))

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.5,
        input=ref_image,
    )

    getnode_22 = raw_call('GetNode', '5199', _outputs=('FLOAT',), widget_0='image_strength')
    getnode_23 = raw_call('GetNode', '5200', _outputs=('AUDIO',), widget_0='audio_original')

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=ref_image,
    )

    float_comfy, int_comfy = ComfyMathExpression(
        expression='a /  b ',
        **{'values.a': reroute_2.out(0), 'values.b': getnode_19.out('FLOAT')},
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': reroute_3.out(0), 'variables.b': getnode_19.out('FLOAT')},
    )

    trimaudioduration = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_18.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    prompt_enhancer_50a3ed96_result = prompt_enhancer_50a3ed96(
        clip=getnode_2.out('CLIP'),
        image=resizeimagemasknode,
        enable=None,
        prompt=['-10', 1],
    )

    trimaudioduration_2 = TrimAudioDuration(
        widget_0=9,
        widget_1=10,
        audio=getnode_23.out('AUDIO'),
        duration=reroute_3.out(0),
        start_index=reroute_4.out(0),
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)

    positive = CLIPTextEncode(
        text=prompt_enhancer_50a3ed96_result,
        clip=getnode_2.out('CLIP'),
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=trimaudioduration,
        audio_vae=getnode.out('VAE'),
    )

    easy_showanything = raw_call('easy showAnything', '5181',
        _outputs=('output',),
        widget_0='53.92',
        anything=float_comfy,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=getnode_20.out('INT'),
        height=getnode_21.out('INT'),
        length=int_simple,
    )

    cfgguider = CFGGuider(
        cfg=1,
        model=getnode_4.out('MODEL'),
        negative=getnode_16.out('CONDITIONING'),
        positive=positive,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=emptyltxvlatentvideo,
        vae=getnode_3.out('VAE'),
        **{'num_images.image_1': ltxvpreprocess, 'num_images.strength_1': getnode_22.out('FLOAT')},
    )

    cfgguider_2 = CFGGuider(
        cfg=1,
        model=getnode_10.out('MODEL'),
        negative=getnode_12.out('CONDITIONING'),
        positive=positive,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplacekj,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=getnode_5.out('SAMPLER'),
        sigmas=getnode_6.out('SIGMAS'),
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=getnode_9.out('LATENT_UPSCALE_MODEL'),
        vae=getnode_7.out('VAE'),
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        widget_0='1',
        widget_1=1,
        widget_2=0,
        latent=ltxvlatentupsampler,
        vae=getnode_7.out('VAE'),
        **{'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': getnode_8.out('FLOAT')},
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplacekj_2,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=getnode_13.out('SAMPLER'),
        sigmas=getnode_14.out('SIGMAS'),
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    vaedecode = VAEDecode(samples=video_latent_ltxv, vae=getnode_15.out('VAE'))

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        image_pass=vaedecode,
    )

    image, width, height, count = GetImageSizeAndCount(image=image_pass)

    float, int, boolean = SimpleCalculatorKJ(
        **{'variables.a': reroute.out(0), 'variables.b': count},
    )

    return int, vaedecode, trimaudioduration_2

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(
            image=public('image', default='download (8).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        )

        intconstant = INTConstant(value=1000)
        vaeloader = VAELoader(vae_name=VAE_NAME)
        latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)

        dualcliploader = DualCLIPLoader(
            clip_name1=CLIP_NAME,
            clip_name2=CLIP_NAME_2,
            type_='ltxv',
            device='default',
        )

        ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
        vaeloader_2 = VAELoader(vae_name=VAE_NAME_2)
        unetloader = UNETLoader(unet_name=UNET_NAME)
        unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_2)

        dualcliploadergguf = DualCLIPLoaderGGUF(
            clip_name1=CLIP_NAME_3,
            clip_name2=CLIP_NAME_2,
            type_='sdxl',
        )

        primitivefloat = raw_call('PrimitiveFloat', '1586', value=8)
        intconstant_2 = INTConstant(value=480)
        loadaudio = LoadAudio(audio='ComfyUI_00152_.mp3')
        melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '1600', widget_0=WIDGET__NAME)
        intconstant_3 = INTConstant(value=832)

        primitivestringmultiline = PrimitiveStringMultiline(
            value=public('prompt', default='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.', type='STRING', required=True, media_semantics='text'),
        )

        primitivefloat_2 = raw_call('PrimitiveFloat', '1722', value=8)

        primitivestringmultiline_2 = PrimitiveStringMultiline(
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )

        primitivefloat_3 = raw_call('PrimitiveFloat', '1997', value=8)
        primitivefloat_4 = raw_call('PrimitiveFloat', '2012', value=8)
        primitiveboolean = raw_call('PrimitiveBoolean', '2116', value=False)

        randomnoise = RandomNoise(
            noise_seed=public('seed', default=DEFAULT_SEED, type='INT'),
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        ksamplerselect = KSamplerSelect(sampler_name='euler_cfg_pp')
        manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

        randomnoise_2 = RandomNoise(
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')

        manualsigmas_2 = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        primitiveint = raw_call('PrimitiveInt', '2284', value=5, control_after_generate='fixed')
        total_duration_result = total_duration()
        primitivestring = raw_call('PrimitiveString', '4119', value='mynewvideo')
        primitiveboolean_2 = raw_call('PrimitiveBoolean', '4736', value=True)
        primitiveboolean_3 = raw_call('PrimitiveBoolean', '4740', value=True)
        image_load, mask_load = LoadImage(image='download (1).png')
        primitiveboolean_4 = raw_call('PrimitiveBoolean', '5067', value=True)

        primitivestringmultiline_3 = PrimitiveStringMultiline(
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at the stage at an abandoned teather.  The camera slowly orbits around the woman, the woman is always looking at the viewer.\n\nShe sings the lyrics: "Now rise from weights, unchained and free.\nLike open doors for you and me.\nAnd every node connects the light. To hands that build without a figh.  No locked gates, just open skies.Where anyone can close their eyes…".\n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )

        primitivefloat_5 = raw_call('PrimitiveFloat', '5071', value=8)
        primitiveint_2 = raw_call('PrimitiveInt', '5072', value=5, control_after_generate='fixed')
        image_load_2, mask_load_2 = LoadImage(image='download (6).png')
        primitiveboolean_5 = raw_call('PrimitiveBoolean', '5142', value=True)

        primitivestringmultiline_4 = PrimitiveStringMultiline(
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from a cloudy sky. \n\n\nShe sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, you stitch the seams. Of every film, each trembling tone. Where lonely sparks now feel at home".\n\nShe sings for a bit before she stands up and walks towards the viewer. \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )

        primitivefloat_6 = raw_call('PrimitiveFloat', '5146', value=8)
        primitiveint_3 = raw_call('PrimitiveInt', '5147', value=5, control_after_generate='fixed')
        image_load_3, mask_load_3 = LoadImage(image='download (2).png')
        primitiveboolean_6 = raw_call('PrimitiveBoolean', '5217', value=True)

        primitivestringmultiline_5 = PrimitiveStringMultiline(
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is standing on a rooftop balcony with the city behind her, at night. Camera slowly orbits around her, with her always looking towards the viewer as she sings. \n\nShe sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path through digital space. We dream in code, we dream in blue. And every open door leads through.......". \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )

        primitivefloat_7 = raw_call('PrimitiveFloat', '5221', value=8)
        primitiveint_4 = raw_call('PrimitiveInt', '5222', value=5, control_after_generate='fixed')
        image_load_4, mask_load_4 = LoadImage(image='download (12).png')

        image_image, width, height, mask_image = ImageResizeKJv2(
            upscale_method='lanczos',
            keep_proportion='crop',
            device='cpu',
            width=intconstant_3,
            height=intconstant_2,
            image=image,
        )

        loraloadermodelonly = LoraLoaderModelOnly(
            lora_name=LORA_NAME,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )

        trimaudioduration = TrimAudioDuration(
            widget_0=11,
            widget_1=40,
            audio=loadaudio,
            duration=total_duration_result,
        )

        solidmask = SolidMask(
            value=0,
            widget_1=512,
            widget_2=512,
            height=intconstant_2,
            width=intconstant_3,
        )

        # Conditioning
        cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

        float, int, boolean = SimpleCalculatorKJ(
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            **{'variables.a': primitivefloat_4, 'variables.b': primitivefloat},
        )

        stringconcatenate = StringConcatenate(
            delimiter='\\',
            string_a='MusicVideo',
            widget_1='',
            string_b=primitivestring,
        )

        stringconcatenate_3 = StringConcatenate(
            delimiter='\\',
            string_a='output\\MusicVideo',
            widget_1='',
            string_b=primitivestring,
        )

        pathchsageattentionkj = PathchSageAttentionKJ(
            sage_attention='disabled',
            model=loraloadermodelonly,
        )

        melbandroformersampler = raw_call('MelBandRoFormerSampler', '1599',
            audio=trimaudioduration,
            model=melbandroformermodelloader.out(0),
        )

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type='scale by multiplier',
            input=image_image,
        )

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            longer_edge=1536,
            images=image_image,
        )

        stringconcatenate_2 = StringConcatenate(
            delimiter='\\',
            string_b='MusicVideo',
            widget_0='MusicVideo',
            string_a=stringconcatenate,
        )

        ltxvpreprocess = LTXVPreprocess(
            img_compression=18,
            image=resizeimagesbylongeredge,
        )

        ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

        comfyswitchnode = ComfySwitchNode(
            switch=True,
            on_false=trimaudioduration,
            on_true=melbandroformersampler.out(0),
        )

        width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode)
        prompt_enhancer_3bd4eeb9_result = prompt_enhancer_3bd4eeb9(
            clip=dualcliploader,
            image=resizeimagesbylongeredge,
            enable=None,
            prompt=primitivestringmultiline,
        )

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=width_get,
            height=height_get,
            length=int,
        )

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )

        cliptextencode = CLIPTextEncode(
            text=prompt_enhancer_3bd4eeb9_result,
            clip=dualcliploader,
        )

        trimaudioduration_2 = TrimAudioDuration(
            widget_0=0,
            widget_1=40,
            audio=comfyswitchnode,
            duration=primitivefloat_4,
        )

        positive, negative = LTXVConditioning(
            frame_rate=primitivefloat,
            negative=cliptextencode_2,
            positive=cliptextencode,
        )

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            audio=trimaudioduration_2,
            audio_vae=ltxvaudiovaeloader,
        )

        power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '2150',
            _outputs=('MODEL', 'CLIP'),
            widget_7='',
            model=ltx2attentiontunerpatch,
        )

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            widget_0=1,
            widget_1=False,
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=vaeloader,
        )

        setlatentnoisemask = SetLatentNoiseMask(
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )

        ltx2_nag = LTX2_NAG(
            model=power_lora_loader__rgthree_.out('MODEL'),
            nag_cond_audio=negative,
            nag_cond_video=negative,
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=setlatentnoisemask,
            video_latent=ltxvimgtovideoinplace_2,
        )

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=ltx2_nag,
            negative=positive,
            positive=positive,
        )

        modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2_nag)

        cfgguider_2 = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=ltx2_nag,
            negative=negative,
            positive=positive,
        )

        modelsamplingsd3_2 = ModelSamplingSD3(shift=13, model=ltx2_nag)

        basicscheduler = BasicScheduler(
            scheduler=1,
            steps=1,
            widget_1=4,
            model=modelsamplingsd3,
        )

        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
        )

        basicscheduler_2 = BasicScheduler(
            scheduler=1,
            steps=1,
            widget_1=10,
            model=modelsamplingsd3_2,
        )

        video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(av_latent=output)

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            widget_0=1,
            widget_1=False,
            image=resizeimagesbylongeredge,
            latent=video_latent_ltxv,
            strength=primitivefloat_2,
            vae=vaeloader,
        )

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            audio_latent=audio_latent_ltxv,
            video_latent=ltxvimgtovideoinplace,
        )

        output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
        )

        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)

        # Decode
        vaedecode = VAEDecode(samples=video_latent, vae=vaeloader)

        image_get, width_get_2, height_get_2, count = GetImageSizeAndCount(
            image=vaedecode,
        )

        any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
            image_pass=vaedecode,
        )

        # Outputs
        vhs_videocombine_3 = VHS_VideoCombine(
            frame_rate=primitivefloat,
            filename_prefix=stringconcatenate_2,
            save_output=primitiveboolean_3,
            audio=trimaudioduration,
            images=vaedecode,
        )

        image_get_2, width_get_3, height_get_3, count_get = GetImageSizeAndCount(
            image=image_pass,
        )

        int, output_1, audio = generate_video_c4106aee(
            noise_seed=primitiveint,
            prompt=primitivestringmultiline_2,
            window_seconds=primitivefloat_3,
            frames_count=count_get,
            ref_image=image_load,
        )

        vhs_videocombine = VHS_VideoCombine(
            frame_rate=primitivefloat,
            filename_prefix=stringconcatenate_2,
            save_output=primitiveboolean_2,
            audio=audio,
            images=output_1,
        )

        int_2, output_1_2, audio_2 = generate_video(
            noise_seed=primitiveint_2,
            prompt=primitivestringmultiline_3,
            window_seconds=primitivefloat_5,
            frames_count=int,
            ref_image=image_load_2,
        )

        vhs_videocombine_4 = VHS_VideoCombine(
            frame_rate=primitivefloat,
            filename_prefix=stringconcatenate_2,
            save_output=primitiveboolean_4,
            audio=audio_2,
            images=output_1_2,
        )

        int_3, output_1_3, audio_3 = generate_video_a3fb563d(
            noise_seed=primitiveint_3,
            prompt=primitivestringmultiline_4,
            window_seconds=primitivefloat_6,
            frames_count=int_2,
            ref_image=image_load_3,
        )

        vhs_videocombine_5 = VHS_VideoCombine(
            frame_rate=primitivefloat,
            filename_prefix=stringconcatenate_2,
            save_output=primitiveboolean_5,
            audio=audio_3,
            images=output_1_3,
        )

        int_4, output_1_4, audio_4 = generate_video_4acc9924(
            noise_seed=primitiveint_4,
            prompt=primitivestringmultiline_5,
            window_seconds=primitivefloat_7,
            frames_count=int_3,
            ref_image=image_load_4,
        )

        vhs_videocombine_6 = VHS_VideoCombine(
            frame_rate=primitivefloat,
            filename_prefix=stringconcatenate_2,
            save_output=primitiveboolean_6,
            audio=audio_4,
            images=output_1_4,
        )

        float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
            expression='a + 100',
            **{'variables.a': int_4},
        )

        loadvideosfromfolder = LoadVideosFromFolder(
            widget_0='output\\MusicVideo',
            widget_4=0,
            frame_load_cap=int_simple,
            video=stringconcatenate_3,
        )

        vhs_videocombine_2 = VHS_VideoCombine(
            frame_rate=primitivefloat,
            audio=trimaudioduration,
            images=loadvideosfromfolder,
        )

        return wf.finalize({}, output_node=vhs_videocombine, spec=OUTPUT_SPEC)

