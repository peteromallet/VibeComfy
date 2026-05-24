# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PreviewAudio, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceClone
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CKPT_NAME = 'LTX23_audio_vae_bf16.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CLIP_NAME_3 = 'gemma-3-12b-it-Q2_K.gguf'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LORA_NAME = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
UNET_NAME_2 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_NAME = 'LTX23_video_vae_bf16.safetensors'
VAE_NAME_2 = 'taeltx2_3.safetensors'
WIDGET_0 = 'vae'
WIDGET_0_10 = 'ref_image'
WIDGET_0_11 = 'vae_audio'
WIDGET_0_12 = 'upscale_model'
WIDGET_0_13 = 'negative'
WIDGET_0_14 = 'positive'
WIDGET_0_15 = 't2v_mode'
WIDGET_0_16 = 'model'
WIDGET_0_17 = 'model_with_lora'
WIDGET_0_18 = 'vae_tiny'
WIDGET_0_19 = 'latent'
WIDGET_0_2 = 'clip'
WIDGET_0_20 = 'latent_custom_audio'
WIDGET_0_21 = 'enhance_prompt'
WIDGET_0_3 = 'width'
WIDGET_0_4 = 'height'
WIDGET_0_5 = 'frames'
WIDGET_0_6 = 'fps'
WIDGET_0_7 = 'audio_tts'
WIDGET_0_8 = 'height_downscaled'
WIDGET_0_9 = 'width_downscaled'
WIDGET__NAME = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='tts_talking_avatar',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-QwenTTS', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git', 'version': 'unknown', 'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-QwenTTS', 'source': 'git', 'version': 'unknown', 'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceClone'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='Qwen TTS talking avatar',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json'},
)

# === Subgraph functions ===

def calculate_frames(
    *,
    audio,
):
    """Calculate Frames.

    Materialized from subgraph 63e8c999-0a69-4f62-af3f-8b77f0095971 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json.
    # vibecomfy source hash: sha256:1b113811260bc21cf194456174f57f31f684d4797b7bf6e7b24d7f2e1cc9df56
    Inner nodes: Audio Duration (mtb), SimpleCalculatorKJx3, GetNodex2, LazySwitchKJ, MarkdownNote.
    """

    audio_duration__mtb_ = raw_call('Audio Duration (mtb)', '1864', _outputs=('duration_ms',), audio=audio)
    getnode = raw_call('GetNode', '1871', _outputs=('FLOAT',), widget_0='fps')
    getnode_2 = raw_call('GetNode', '1919', _outputs=('INT',), widget_0='frames_seconds')

    markdownnote = raw_call('MarkdownNote', '1921',
        widget_0='Simply calculate if the audio is longer than the given user input for seconds length, and if so override to use length of audio\n',
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression='ceil(a/1000)',
        **{'variables.a': audio_duration__mtb_.out('duration_ms')},
    )

    float, int, boolean = SimpleCalculatorKJ(
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        **{'variables.a': int_simple, 'variables.b': getnode.out('FLOAT')},
    )

    float_simple_2, int_simple_2, boolean_simple_2 = SimpleCalculatorKJ(
        expression='a<b ',
        **{'variables.a': getnode_2.out('INT'), 'variables.b': int},
    )

    lazyswitchkj = LazySwitchKJ(
        widget_0=False,
        on_false=getnode_2.out('INT'),
        on_true=int,
        switch=boolean_simple_2,
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

    Materialized from subgraph a8d7fd9f-52aa-447a-9766-53cb91c0ef18 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json.
    # vibecomfy source hash: sha256:82a0262ab01d18c8c6ccd1c203fb4703ab56ca60a7d39e3727213e844bbd7f7d
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
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        image, mask = LoadImage(
            image=public('image', default='17745317855d08.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        )

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

        intconstant = INTConstant(value=10)
        primitivefloat = raw_call('PrimitiveFloat', '1586', value=8)
        intconstant_2 = INTConstant(value=960)
        intconstant_3 = INTConstant(value=544)

        primitivestringmultiline = PrimitiveStringMultiline(
            value=public('prompt', default="A video from a TV broadcast with a male and a female news achor. They both stay in frame all the time.\n\nThe dialog from the male and female is as follows:\n\nSpaker_1 is the woman, and Speaker_2 is the man.\n\n[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and put us in this odd situation.\n[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, doesn't mean our voices change. \n[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n[speaker_2][happy]: I still have no idea what she said! Might be for the best [laughing]\n\nThe dialog with perfect lip-sync to the audio\n\n\nThey both smile at the end.\n\n\n", type='STRING', required=True, media_semantics='text'),
        )

        randomnoise = RandomNoise(
            noise_seed=public('seed', default=DEFAULT_SEED, type='INT'),
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        randomnoise_2 = RandomNoise(
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
        ksamplerselect = KSamplerSelect(sampler_name='euler_cfg_pp')
        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')

        manualsigmas_2 = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        primitiveboolean = raw_call('PrimitiveBoolean', '1862', value=False)
        reroute = raw_call('Reroute', '1865')
        primitiveboolean_2 = raw_call('PrimitiveBoolean', '1929', value=True)
        melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '1937', widget_0=WIDGET__NAME)
        primitivestringmultiline_2 = PrimitiveStringMultiline(value='')
        loadaudio = LoadAudio(audio='d1b26d5a32db420183fa17af9c699278.mp3')

        primitivestringmultiline_3 = PrimitiveStringMultiline(
            value='So what if you just want to prompt. Text to video works fine as well. Go generate some while I enjoy my coffee. ',
        )

        calculate_frames_result = calculate_frames(audio=reroute.out(0))

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

        # Conditioning
        cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

        solidmask = SolidMask(
            value=0,
            widget_1=512,
            widget_2=512,
            height=intconstant_2,
            width=intconstant_3,
        )

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            audio=reroute.out(0),
            audio_vae=ltxvaudiovaeloader,
        )

        float, int, boolean = SimpleCalculatorKJ(
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            **{'variables.a': intconstant, 'variables.b': primitivefloat},
        )

        trimaudioduration = TrimAudioDuration(widget_0=0, widget_1=15, audio=loadaudio)

        melbandroformersampler = raw_call('MelBandRoFormerSampler', '1936',
            audio=trimaudioduration,
            model=melbandroformermodelloader.out(0),
        )

        ltxvpreprocess = LTXVPreprocess(img_compression=18, image=image_image)

        pathchsageattentionkj = PathchSageAttentionKJ(
            sage_attention='disabled',
            model=loraloadermodelonly,
        )

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type='scale by multiplier',
            input=image_image,
        )

        setlatentnoisemask = SetLatentNoiseMask(
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )

        prompt_enhancer_result = prompt_enhancer(
            clip=dualcliploader,
            image=resizeimagemasknode,
            enable=None,
            prompt=primitivestringmultiline,
        )
        ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)
        width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode)

        ailab_qwen3ttsvoiceclone = AILab_Qwen3TTSVoiceClone(
            widget_0='Hello, this is a cloned voice.',
            widget_3='',
            widget_4=True,
            widget_5=986337553816914,
            widget_6=116899311982882,
            widget_7='randomize',
            reference_audio=melbandroformersampler.out(0),
            reference_text=primitivestringmultiline_2,
            target_text=primitivestringmultiline_3,
        )

        audionormalizelufs = raw_call('AudioNormalizeLUFS', '1916',
            widget_0=-20,
            widget_1=0,
            widget_2=0,
            widget_3='full_track',
            audio=ailab_qwen3ttsvoiceclone,
        )

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=width_get,
            height=height_get,
            length=calculate_frames_result,
        )

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )

        cliptextencode_2 = CLIPTextEncode(
            text=prompt_enhancer_result,
            clip=dualcliploader,
        )

        power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '1627',
            _outputs=('MODEL', 'CLIP'),
            widget_4='',
            model=ltx2attentiontunerpatch,
        )

        audioenhancementnode = raw_call('AudioEnhancementNode', '1904',
            widget_0='manual',
            widget_1=0.7,
            widget_10=5,
            widget_11=0,
            widget_12=0,
            widget_13='full_track',
            widget_2=0.6,
            widget_3=1.3,
            widget_4=1.2,
            widget_5=1,
            widget_6=1,
            widget_7=0.5,
            widget_8='keep_original',
            widget_9=False,
            audio=audionormalizelufs.out(0),
        )

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            widget_0=0.7,
            widget_1=False,
            bypass=primitiveboolean,
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=vaeloader,
        )

        positive, negative = LTXVConditioning(
            frame_rate=primitivefloat,
            negative=cliptextencode,
            positive=cliptextencode_2,
        )

        ltx2_nag = LTX2_NAG(
            model=power_lora_loader__rgthree_.out('MODEL'),
            nag_cond_audio=negative,
            nag_cond_video=negative,
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=setlatentnoisemask,
            video_latent=ltxvimgtovideoinplace,
        )

        previewaudio = PreviewAudio(audio=audioenhancementnode.out(0))

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

        modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2_nag)
        modelsamplingsd3_2 = ModelSamplingSD3(shift=13, model=ltx2_nag)

        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
        )

        basicscheduler = BasicScheduler(
            scheduler=1,
            steps=1,
            widget_1=8,
            model=modelsamplingsd3,
        )

        basicscheduler_2 = BasicScheduler(
            scheduler=1,
            steps=1,
            widget_1=4,
            model=modelsamplingsd3_2,
        )

        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            widget_0=1,
            widget_1=False,
            bypass=primitiveboolean,
            image=image_image,
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
            sampler=ksamplerselect,
            sigmas=manualsigmas,
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

        any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
            unload_all_models=True,
            image_pass=vaedecodetiled,
        )

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            frame_rate=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=image_pass,
        )

        return wf.finalize({}, output_node=previewaudio)

