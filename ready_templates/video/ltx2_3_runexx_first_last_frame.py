# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, ImageScaleBy, KSamplerSelect, LTXVAddGuide, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVLatentUpsampler, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CKPT_NAME = 'LTX23_audio_vae_bf16.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = "wf.nodes['11'].inputs.get('text', '')"
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
DEVICE = 'cpu'
EXPRESSION = 'a'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
KEEP_PROPORTION = 'crop'
LORA_NAME = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
SIGMAS = '0.909375, 0.725, 0.421875, 0.0'
UNET_NAME = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
UPSCALE_METHOD = 'nearest-exact'
VAE_NAME = 'taeltx2_3.safetensors'
VAE_NAME_2 = 'LTX23_video_vae_bf16.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors', sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d', hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492', size_bytes=9447702218, subdir='text_encoders'),
    'text_encoder_2': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors', hf_revision='main', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors', hf_revision='main', subdir='vae'),
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', hf_revision='main', subdir='checkpoints'),
    'vae_2': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors', hf_revision='main', subdir='vae'),
    'diffusion_model': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', hf_revision='main', subdir='diffusion_models'),
    'lora': ModelAsset(filename='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', hf_revision='main', subdir='loras'),
    'upscale_model': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors', sha256='5f416311fa8172b65af67530758964708d29a317b830d689a51143b7f91913ed', hf_revision='76730e634e70a28f4e8d51f5e29c08e40e2d8e74', size_bytes=995743560, subdir='latent_upscale_models'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_video',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'LTXVAddGuide', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='first/last-frame image anchors',
    smoke_resolution='256x256x5_frames',
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by PathchSageAttentionKJ auto mode for 4090-speed LTX Runexx validation.', 'source': 'SageAttention-ada'}],
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json'},
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    enabled,
    prompt,
):
    """PROMPT ENHANCER - single-image variant.

    Materialized from subgraph 8fa4f93a-67ee-463f-ba43-249580c0bfb1 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json.
    # vibecomfy source hash: sha256:895a04220ee78e03e0223c4df31671bd6ca26b9f5e0ee4842eb06c21ad21e75a
    Inner nodes: Reroutex2, StringConcatenate, ComfySwitchNode, easy showAnything, TextGenerateLTX2Prompt, PrimitiveStringMultiline.
    """

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.   \n\nMAIN GOAL: \nCREATE AN INTERESTING PROMPT WHERE THE START FRAME IS THE IMAGE TO THE LEFT, AND END FRAME IS THE IMAGE TO THE RIGHT\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )

    reroute = raw_call('Reroute', '598', _outputs=('',))
    reroute_2 = raw_call('Reroute', '1997', _outputs=('',))

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

    easy_showanything = raw_call('easy showAnything', '486',
        _outputs=('output',),
        widget_0="Style: cinematic - A thick, swirling fog obscures the cobblestone streets and canal buildings of 1700s Amsterdam, illuminated by the warm glow of streetlights. The camera smoothly cranes down from a high angle, revealing a vampire's gloved hand gripping a walking cane, the sound of footsteps echoing softly on the wet cobblestones. The scene is moody and unsettling, with a palpable sense of unease hanging in the air.",
        anything=textgenerateltx2prompt,
    )

    comfyswitchnode = ComfySwitchNode(
        widget_0=False,
        on_false=reroute_2.out(0),
        on_true=textgenerateltx2prompt,
        switch=reroute.out(0),
    )

    return comfyswitchnode


def frames_split_view():
    """Frames split view.

    Materialized from subgraph 19e3f7e8-881c-4a61-a360-1c463734043a in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json.
    # vibecomfy source hash: sha256:15880df52a4893175f1cb307bfae4788f299a66697d6e3cef64c835bbf983c8c
    Inner nodes: GetNodex2, ResizeImageMaskNodex2, ImagePadForOutpaintx2, ImageStitch.
    """

    getnode = raw_call('GetNode', '2086', _outputs=('IMAGE',), widget_0='lastframe')
    getnode_2 = raw_call('GetNode', '2087', _outputs=('IMAGE',), widget_0='firstframe')

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.2,
        input=getnode.out('IMAGE'),
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.2,
        input=getnode_2.out('IMAGE'),
    )

    imagepadforoutpaint = raw_call('ImagePadForOutpaint', '2098',
        _outputs=('IMAGE', 'MASK'),
        widget_0=16,
        widget_1=16,
        widget_2=16,
        widget_3=16,
        widget_4=0,
        image=resizeimagemasknode,
    )

    imagepadforoutpaint_2 = raw_call('ImagePadForOutpaint', '2100',
        _outputs=('IMAGE', 'MASK'),
        widget_0=16,
        widget_1=16,
        widget_2=16,
        widget_3=16,
        widget_4=0,
        image=resizeimagemasknode_2,
    )

    imagestitch = raw_call('ImageStitch', '2085',
        widget_0='right',
        widget_1=True,
        widget_2=0,
        widget_3='white',
        image1=imagepadforoutpaint_2.out('IMAGE'),
        image2=imagepadforoutpaint.out('IMAGE'),
    )

    return imagestitch

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
    manualsigmas = ManualSigmas(sigmas=SIGMAS)

    randomnoise = RandomNoise(
        noise_seed=DEFAULT_SEED,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )

    randomnoise_2 = RandomNoise(
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )

    # Inputs
    image, mask = LoadImage(image='image (6).png')
    image_load, mask_load = LoadImage(image='0 (13).webp')
    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
    vaeloader = VAELoader(vae_name=VAE_NAME)
    vaeloader_2 = VAELoader(vae_name=VAE_NAME_2)
    latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type_='ltxv',
        device='default',
    )

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    manualsigmas_3 = ManualSigmas(sigmas=SIGMAS)
    primitivefloat = raw_call('PrimitiveFloat', '2076', value=24)
    intconstant = INTConstant(value=81)
    intconstant_2 = INTConstant(value=720)
    intconstant_3 = INTConstant(value=1280)
    primitiveboolean = raw_call('PrimitiveBoolean', '2082', value=True)

    primitivestringmultiline = PrimitiveStringMultiline(
        value="wf.nodes['2103'].inputs.get('value', '')",
    )

    primitivefloat_2 = raw_call('PrimitiveFloat', '2108', value=1.0)
    primitivefloat_3 = raw_call('PrimitiveFloat', '2110', value=1.0)

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    cliptextencode_2 = CLIPTextEncode(
        text=primitivestringmultiline,
        clip=dualcliploader,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method=UPSCALE_METHOD,
        keep_proportion=KEEP_PROPORTION,
        divisible_by=32,
        device=DEVICE,
        width=intconstant_3,
        height=intconstant_2,
        image=image,
    )

    float, int, boolean = SimpleCalculatorKJ(
        expression=EXPRESSION,
        variables='a',
        a=primitivefloat,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
        expression=EXPRESSION,
        variables='a,b',
        widget_0='a',
        a=intconstant,
        b=primitivefloat,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=int_simple,
        frame_rate=int,
        audio_vae=ltxvaudiovaeloader,
    )

    positive, negative = LTXVConditioning(
        frame_rate=primitivefloat,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    imagescaleby = ImageScaleBy(
        upscale_method='lanczos',
        scale_by=0.5,
        image=image_image,
    )

    image_image_2, width_image, height_image, mask_image_2 = ImageResizeKJv2(
        upscale_method=UPSCALE_METHOD,
        keep_proportion=KEEP_PROPORTION,
        divisible_by=32,
        device=DEVICE,
        width=width,
        height=height,
        image=image_load,
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image,
    )

    width_get, height_get, batch_size = GetImageSize(image=imagescaleby)

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=image_image_2,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=image_image_2)
    ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

    ltxvpreprocess_2 = LTXVPreprocess(
        img_compression=18,
        image=resizeimagesbylongeredge,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width_get,
        height=height_get,
        length=int_simple,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
        triton_kernels=False,
        model=ltxvchunkfeedforward,
    )

    ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
        num_images='2',
        latent=emptyltxvlatentvideo,
        vae=vaeloader_2,
        **{'num_images.index_1': 0, 'num_images.index_2': -1, 'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess, 'num_images.strength_1': primitivefloat_3, 'num_images.strength_2': primitivefloat_2},
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        model=ltx2attentiontunerpatch,
    )

    power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '2107',
        _outputs=('MODEL', 'CLIP'),
        model=ltx2memoryefficientsageattentionpatch,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvimgtovideoinplacekj,
    )

    ltxvscheduler = LTXVScheduler(steps=1, latent=ltxvconcatavlatent)

    ltx2_nag = LTX2_NAG(
        model=power_lora_loader__rgthree_.out('MODEL'),
        nag_cond_audio=negative,
        nag_cond_video=negative,
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

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader_2,
    )

    any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
        unload_all_models=True,
        any_input=ltxvlatentupsampler,
    )

    ltxvimgtovideoinplacekj_2 = LTXVImgToVideoInplaceKJ(
        num_images='1',
        latent=any_output,
        vae=vaeloader_2,
        **{'num_images.index_1': 0, 'num_images.image_1': resizeimagesbylongeredge, 'num_images.strength_1': primitivefloat_3},
    )

    positive_ltxv, negative_ltxv, latent = LTXVAddGuide(
        frame_idx=-1,
        strength=primitivefloat_2,
        image=resizeimagesbylongeredge_2,
        latent=ltxvimgtovideoinplacekj_2,
        negative=negative,
        positive=positive,
        vae=vaeloader_2,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=latent,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_3,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv,
        negative=negative_ltxv,
        positive=positive_ltxv,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        temporal_size=4096,
        samples=latent_ltxv,
        vae=vaeloader_2,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        filename_prefix='reigh_vibecomfy_ltx_first_last',
        format='video/h264-mp4',
        frame_rate=primitivefloat,
        images=vaedecodetiled,
    )


    wf.register_input('model', ltxvaudiovaeloader.node.id, 'ckpt_name', CKPT_NAME)

    PUBLIC_INPUTS = {
        'seed': InputSpec(node=randomnoise_2, field='noise_seed', default=DEFAULT_SEED_2),
        'model': InputSpec(node=ltxvaudiovaeloader, field='ckpt_name', default=CKPT_NAME),
        'prompt': InputSpec(node=primitivestringmultiline, field='value', default="wf.nodes['2103'].inputs.get('value', '')"),
        'seed_last': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED),
        'first_image': InputSpec(node=image, field='image', default='image (6).png', aliases=('start_image',)),
        'last_image': InputSpec(node=image_load, field='image', default='0 (13).webp', aliases=('end_image',)),
        'fps': InputSpec(node=primitivefloat, field='value', default=24, aliases=('output_fps',)),
        'frames': InputSpec(node=intconstant, field='value', default=81, aliases=('length',)),
        'height': InputSpec(node=intconstant_2, field='value', default=720),
        'width': InputSpec(node=intconstant_3, field='value', default=1280),
        'use_lora': InputSpec(node=primitiveboolean, field='value', default=True),
        'last_frame_strength': InputSpec(node=primitivefloat_2, field='value', default=1.0),
        'first_frame_strength': InputSpec(node=primitivefloat_3, field='value', default=1.0),
        'negative_prompt': InputSpec(node=cliptextencode, field='text', default=DEFAULT_PROMPT),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='reigh_vibecomfy_ltx_first_last')

