# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVSeparateAVLatent, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode, LowVRAMAudioVAELoader, LowVRAMCheckpointLoader


DEFAULT_FPS = 8
DEFAULT_FRAMES = 5
DEFAULT_PROMPT_2 = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 2.5
LANCZOS = 'lanczos'
LTX_2_3_22B_DEV_FP8_SAFETENSORS = 'ltx-2.3-22b-dev-fp8.safetensors'
VALUE = ''

READY_METADATA = ReadyMetadata.build(
    capability='union_control_video_guided_i2v',
    requirements={'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'comfyui_controlnet_aux'], 'custom_node_refs': [{'slug': 'ComfyUI-DepthAnythingV2', 'source': 'git', 'version': 'unknown', 'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'comfyui_controlnet_aux', 'source': 'git', 'version': 'unknown', 'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'}]},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['CannyEdgePreprocessor', 'DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='official IC-LoRA union control workflow with depth/pose-style guide preprocessing',
    runtime_note='Requires additional VideoDepthAnything/DWPose model setup beyond the core LTX smoke stack.',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(image='example.png', widget_0='example.png')

    model, clip, vae = LowVRAMCheckpointLoader(
        ckpt_name=LTX_2_3_22B_DEV_FP8_SAFETENSORS,
    )

    lowvramaudiovaeloader = LowVRAMAudioVAELoader(
        ckpt_name=LTX_2_3_22B_DEV_FP8_SAFETENSORS,
    )

    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate='fixed')

    loadvideo = LoadVideo(
        file='ltx_smoke_guide.mp4',
        video='ltx_smoke_guide.mp4',
        widget_0='ltx_smoke_guide.mp4',
    )

    primitiveboolean = raw_call('PrimitiveBoolean', '5019', value=True)
    primitivestring = raw_call('PrimitiveString', '5022', value='')

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        text_encoder='gemma_3_12B_it_fp4_mixed.safetensors',
        ckpt_name=LTX_2_3_22B_DEV_FP8_SAFETENSORS,
        device='default',
        widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
        widget_1='ltx-2.3-22b-dev-fp8.safetensors',
    )

    manualsigmas = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
        model='depth_anything_v2_vits_fp32.safetensors',
        precision='fp32',
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text='Apocalyptic landscape with abandoned buildings, overgrown with foliage and trees. The sky is clear and the sun is setting, with the horizon turning bright red. The buildings are delapidated, falling apart and crumbling due to being abandoned for so long.\nThe air is full of silence and the only thing to be heard is a young girl breathing and saying: "Where is everyone?"',
        clip=ltxavtextencoderloader,
    )

    cliptextencode_2 = CLIPTextEncode(
        text=DEFAULT_PROMPT_2,
        clip=ltxavtextencoderloader,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=GUIDE_STRENGTH,
        model=model,
    )

    images, audio, fps = GetVideoComponents(video=loadvideo)

    gemmaapitextencode = GemmaAPITextEncode(
        ckpt_name=LTX_2_3_22B_DEV_FP8_SAFETENSORS,
        enhance_prompt=False,
        prompt=DEFAULT_PROMPT_2,
        widget_0='',
        api_key=primitivestring,
    )

    gemmaapitextencode_2 = GemmaAPITextEncode(
        ckpt_name=LTX_2_3_22B_DEV_FP8_SAFETENSORS,
        enhance_prompt=LTX_2_3_22B_DEV_FP8_SAFETENSORS,
        widget_0='',
        api_key=primitivestring,
    )

    resizeimagemasknode_3 = ResizeImageMaskNode(
        resize_type='scale longer dimension',
        scale_method=LANCZOS,
        input=image,
    )

    positive, negative = LTXVConditioning(
        widget_0=8,
        frame_rate=fps,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    model_ltxic, latent_downscale_factor = LTXICLoRALoaderModelOnly(
        lora_name='ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors',
        widget_0='ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors',
        model=loraloadermodelonly,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale shorter dimension',
        scale_method=LANCZOS,
        input=images,
    )

    ltxfloattoint = LTXFloatToInt(rounding=0, a=fps)

    dwpreprocessor = raw_call('DWPreprocessor', '4986',
        detect_hand='enable',
        detect_body='enable',
        detect_face='enable',
        resolution=256,
        bbox_detector='yolox_l.onnx',
        pose_estimator='dw-ll_ucoco_384_bs5.torchscript.pt',
        scale_stick_for_xinsr_cn='disable',
        image=resizeimagemasknode,
    )

    cannyedgepreprocessor = raw_call('CannyEdgePreprocessor', '4991',
        low_threshold=92,
        resolution=256,
        image=resizeimagemasknode,
    )

    simplemath_ = raw_call('SimpleMath+', '5034',
        _outputs=('INT', 'FLOAT'),
        value='a*32',
        a=latent_downscale_factor,
    )

    depthanything_v2 = DepthAnything_V2(
        da_model=downloadandloaddepthanythingv2model,
        images=resizeimagemasknode,
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type='scale to multiple',
        scale_method=LANCZOS,
        input=cannyedgepreprocessor,
        **{'resize_type.multiple': simplemath_.out('INT')},
    )

    width, height, batch_size = GetImageSize(image=resizeimagemasknode_2)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=width,
        height=height,
        length=batch_size,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        widget_0=5,
        widget_1=8,
        frames_number=batch_size,
        frame_rate=ltxfloattoint,
        audio_vae=lowvramaudiovaeloader,
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        widget_1=False,
        bypass=primitiveboolean,
        image=resizeimagemasknode_3,
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    positive_ltx, negative_ltx, latent = LTXAddVideoICLoRAGuide(
        crop=1,
        use_tiled_encode='disabled',
        tile_size=128,
        tile_overlap=32,
        image=resizeimagemasknode_2,
        latent=ltxvimgtovideoconditiononly,
        latent_downscale_factor=latent_downscale_factor,
        negative=negative,
        positive=positive,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=latent,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=model_ltxic,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=lowvramaudiovaeloader,
        samples=audio_latent,
    )

    positive_ltxv, negative_ltxv, latent_ltxv = LTXVCropGuides(
        latent=video_latent,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        latents=latent_ltxv,
        vae=vae,
    )

    createvideo = CreateVideo(
        widget_0=8,
        fps=fps,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode,
    )

    # Outputs
    savevideo = SaveVideo(filename_prefix='output', video=createvideo)


    PUBLIC_INPUTS = {
        'image': InputSpec(node=image, field='image', default='example.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
        'seed': InputSpec(node=randomnoise, field='noise_seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=cliptextencode, field='text', default='Apocalyptic landscape with abandoned buildings, overgrown with foliage and trees. The sky is clear and the sun is setting, with the horizon turning bright red. The buildings are delapidated, falling apart and crumbling due to being abandoned for so long.\nThe air is full of silence and the only thing to be heard is a young girl breathing and saying: "Where is everyone?"', type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

