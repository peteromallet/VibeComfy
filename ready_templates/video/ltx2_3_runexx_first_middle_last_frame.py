# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, KSamplerSelect, LTXVAddGuideMulti, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, StringConcatenate, TextGenerateLTX2Prompt, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CKPT_NAME = 'LTX23_audio_vae_bf16.safetensors'
CLIP_NAME = 'gemma-3-12b-it-Q2_K.gguf'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CLIP_NAME_3 = 'gemma_3_12B_it_fp4_mixed.safetensors'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
DEVICE = 'cpu'
EXPRESSION = 'a/2'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
KEEP_PROPORTION = 'crop'
LORA_NAME = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
TYPE = 'ltxv'
UNET_NAME = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
UNET_NAME_2 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
UPSCALE_METHOD = 'lanczos'
VAE_NAME = 'taeltx2_3.safetensors'
VAE_NAME_2 = 'LTX23_video_vae_bf16.safetensors'


MODELS = {
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors', hf_revision='main', subdir='text_encoders'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors', hf_revision='main', subdir='vae'),
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', hf_revision='main', subdir='checkpoints'),
    'vae_2': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors', hf_revision='main', subdir='vae'),
    'diffusion_model': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', hf_revision='main', subdir='diffusion_models'),
    'lora': ModelAsset(filename='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', hf_revision='main', subdir='loras'),
}


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='first_middle_last_frame_video',
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='multi-anchor image-guided video',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json'},
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

    Materialized from subgraph 8fa4f93a-67ee-463f-ba43-249580c0bfb1 in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json.
    # vibecomfy source hash: sha256:094e5bae3cf11b90e6834d1ae830b87ad8136d88315ae4fde60a441fe3aaf086
    Inner nodes: Reroutex2, StringConcatenate, ComfySwitchNode, easy showAnything, TextGenerateLTX2Prompt, PrimitiveStringMultiline.
    """

    primitivestringmultiline = PrimitiveStringMultiline(
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.   \n\nMAIN GOAL: \nCREATE AN INTERESTING PROMPT WHERE THE START FRAME IS THE IMAGE TO THE LEFT, MIDDLE IMAGE IS MIDDLE FRAME AND END FRAME IS THE IMAGE TO THE RIGHT\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
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
        widget_0='Style: cinematic\n\nA close-up shot of an LTX soda can with ice cubes around it. The camera smoothly pans up as an arm enters the frame and grabs the can, lifting it into view. A woman with a soft British voice appears, holding the can, and says, "An LTX a day keeps the doctor away." She smiles warmly, takes a sip from the can, and then looks directly at the camera. The sound of ice clinking in the can and a gentle fizzing sound accompany the scene.',
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

    Materialized from subgraph 19e3f7e8-881c-4a61-a360-1c463734043a in workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json.
    # vibecomfy source hash: sha256:dee5a0a0eb24222c83974865726dfc1dc461bd3d96a0fbbab75ed8dc19ba5f79
    Inner nodes: ResizeImageMaskNodex3, ImagePadForOutpaintx2, GetNodex3, ImageStitchx2.
    """

    getnode = raw_call('GetNode', '2086', _outputs=('IMAGE',), widget_0='lastframe')
    getnode_2 = raw_call('GetNode', '2087', _outputs=('IMAGE',), widget_0='firstframe')
    getnode_3 = raw_call('GetNode', '2177', _outputs=('IMAGE',), widget_0='firstframe')

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

    resizeimagemasknode_3 = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        unused_widget_1=0.2,
        input=getnode_3.out('IMAGE'),
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

    imagestitch_2 = raw_call('ImageStitch', '2178',
        widget_0='right',
        widget_1=True,
        widget_2=0,
        widget_3='white',
        image1=imagestitch,
        image2=resizeimagemasknode_3,
    )

    return imagestitch_2

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')
        manualsigmas = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')

        randomnoise = RandomNoise(
            noise_seed=public('seed', default=DEFAULT_SEED),
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        randomnoise_2 = RandomNoise(
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        # Inputs
        image, mask = LoadImage(image=public('image', default='sodacan_01.png'))
        image_load, mask_load = LoadImage(image='image (11).png')
        ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
        vaeloader = VAELoader(vae_name=VAE_NAME)
        vaeloader_2 = VAELoader(vae_name=VAE_NAME_2)
        latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)
        unetloader = UNETLoader(unet_name=UNET_NAME)

        dualcliploadergguf = DualCLIPLoaderGGUF(
            clip_name1=CLIP_NAME,
            clip_name2=CLIP_NAME_2,
            type_=TYPE,
        )

        dualcliploader = DualCLIPLoader(
            clip_name1=CLIP_NAME_3,
            clip_name2=CLIP_NAME_2,
            type_=TYPE,
            device='default',
        )

        unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_2)

        manualsigmas_2 = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        manualsigmas_3 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
        primitivefloat = raw_call('PrimitiveFloat', '2076', value=8)
        intconstant = INTConstant(value=15)
        intconstant_2 = INTConstant(value=720)
        intconstant_3 = INTConstant(value=1280)
        primitiveboolean = raw_call('PrimitiveBoolean', '2082', value=public('use_lora', default=True))

        primitivestringmultiline = PrimitiveStringMultiline(
            value='Make this come alive with cinematic motion, smooth animation. \n\nThe scene starts with a close up of an LTX soda can with ic cubes around it. \n\nAll of a suddent an arm comes into frame and grabs the soda can, and lifts the soda can up. \n\nCamera pans up smoothly to show a woman holding the soda can. She talks with a soft British voice, and she says :" An LTX a day, keeps the doctor away". Then she laghts, and finally she drinks from the soda can. ',
        )

        primitivefloat_2 = raw_call('PrimitiveFloat', '2108', value=8)
        primitivefloat_3 = raw_call('PrimitiveFloat', '2110', value=8)
        image_load_2, mask_load_2 = LoadImage(image='image (12).png')
        primitivefloat_4 = raw_call('PrimitiveFloat', '2278', value=8)

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT),
            clip=dualcliploader,
        )

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

        float, int, boolean = SimpleCalculatorKJ(expression='a', a=primitivefloat)

        loraloadermodelonly = LoraLoaderModelOnly(
            lora_name=LORA_NAME,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )

        float_simple, int_simple, boolean_simple = SimpleCalculatorKJ(
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            a=intconstant,
            b=primitivefloat,
        )

        float_comfy, int_comfy = ComfyMathExpression(
            expression=EXPRESSION,
            **{'values.a': intconstant_3},
        )

        float_comfy_2, int_comfy_2 = ComfyMathExpression(
            expression=EXPRESSION,
            **{'values.a': intconstant_2},
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

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=int_comfy,
            height=int_comfy_2,
            length=int_simple,
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
            sage_attention='disabled',
            model=loraloadermodelonly,
        )

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            longer_edge=1536,
            images=image_image,
        )

        float_simple_2, int_simple_2, boolean_simple_2 = SimpleCalculatorKJ(
            expression=EXPRESSION,
            **{'variables.a': int_simple},
        )

        resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
            longer_edge=1536,
            images=image_image_2,
        )

        ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)

        ltxvpreprocess = LTXVPreprocess(
            img_compression=18,
            image=resizeimagesbylongeredge,
        )

        image_image_3, width_image_2, height_image_2, mask_image_3 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=32,
            device=DEVICE,
            width=width_image,
            height=height_image,
            image=image_load_2,
        )

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )

        resizeimagesbylongeredge_3 = ResizeImagesByLongerEdge(
            longer_edge=1536,
            images=image_image_3,
        )

        ltxvpreprocess_2 = LTXVPreprocess(
            img_compression=18,
            image=resizeimagesbylongeredge_2,
        )

        power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '2107',
            _outputs=('MODEL', 'CLIP'),
            model=ltx2attentiontunerpatch,
        )

        ltxvpreprocess_3 = LTXVPreprocess(
            img_compression=18,
            image=resizeimagesbylongeredge_3,
        )

        ltx2_nag = LTX2_NAG(
            model=power_lora_loader__rgthree_.out('MODEL'),
            nag_cond_audio=cliptextencode,
            nag_cond_video=cliptextencode,
        )

        positive_ltxv, negative_ltxv, latent = LTXVAddGuideMulti(
            num_guides='3',
            latent=emptyltxvlatentvideo,
            negative=negative,
            positive=positive,
            vae=vaeloader_2,
            **{'num_guides.frame_idx_1': 0, 'num_guides.frame_idx_3': -1, 'num_guides.frame_idx_2': int_simple_2, 'num_guides.image_1': ltxvpreprocess, 'num_guides.image_2': ltxvpreprocess_2, 'num_guides.image_3': ltxvpreprocess_3, 'num_guides.strength_1': primitivefloat_3, 'num_guides.strength_2': primitivefloat_4, 'num_guides.strength_3': primitivefloat_2},
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=ltxvemptylatentaudio,
            video_latent=latent,
        )

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=ltx2_nag,
            negative=negative_ltxv,
            positive=positive_ltxv,
        )

        ltxvscheduler = LTXVScheduler(steps=1, latent=ltxvconcatavlatent)

        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect,
            sigmas=manualsigmas_2,
        )

        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

        positive_ltxv_2, negative_ltxv_2, latent_ltxv = LTXVCropGuides(
            latent=video_latent,
            negative=negative_ltxv,
            positive=positive_ltxv,
        )

        positive_ltxv_3, negative_ltxv_3, latent_ltxv_2 = LTXVAddGuideMulti(
            num_guides='2',
            latent=latent_ltxv,
            negative=negative_ltxv_2,
            positive=latent_ltxv,
            vae=vaeloader_2,
            **{'num_guides.frame_idx_1': 0, 'num_guides.frame_idx_2': -1, 'num_guides.image_1': resizeimagesbylongeredge, 'num_guides.image_2': resizeimagesbylongeredge_3, 'num_guides.strength_1': primitivefloat_3, 'num_guides.strength_2': primitivefloat_2},
        )

        cfgguider_2 = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=ltx2_nag,
            negative=negative_ltxv_3,
            positive=positive_ltxv_3,
        )

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            audio_latent=audio_latent,
            video_latent=latent_ltxv_2,
        )

        output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
            guider=cfgguider_2,
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

        positive_ltxv_4, negative_ltxv_4, latent_ltxv_3 = LTXVCropGuides(
            latent=video_latent_ltxv,
            negative=negative_ltxv_3,
            positive=positive_ltxv_3,
        )

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            temporal_size=4096,
            samples=latent_ltxv_3,
            vae=vaeloader_2,
        )

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            filename_prefix='reigh_vibecomfy_ltx_first_middle_last',
            format='video/h264-mp4',
            frame_rate=primitivefloat,
            images=vaedecodetiled,
        )


        wf.register_input('model', ltxvaudiovaeloader.node.id, 'ckpt_name', CKPT_NAME)
        return wf.finalize({}, filename_prefix='reigh_vibecomfy_ltx_first_middle_last', spec=OUTPUT_SPEC)

