# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.controlnet_aux import CannyEdgePreprocessor
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVSeparateAVLatent, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo, SimpleMath_2
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode


CKPT_NAME = 'ltx-2.3-22b-dev.safetensors'
DEFAULT_PROMPT = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_PROMPT_2 = 'Apocalyptic landscape with abandoned buildings, overgrown with foliage and trees. The sky is clear and the sun is setting, with the horizon turning bright red. The buildings are delapidated, falling apart and crumbling due to being abandoned for so long.\nThe air is full of silence and the only thing to be heard is a young girl breathing and saying: "Where is everyone?"'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.5
LANCZOS = 'lanczos'
LORA_NAME = 'ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors'
LORA_NAME_2 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
TEXT_ENCODER_NAME = 'comfy_gemma_3_12B_it.safetensors'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='2004', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='4832', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='2483', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='2612', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['ltx-2.3-22b-dev.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'discovered'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['CannyEdgePreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json', 'source_id': 'video/ltx2_3_lightricks_iclora_union_control', 'upstream_source_id': 'LTX-2.3_ICLoRA_Union_Control_Distilled', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_iclora_union_control'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='2004', image='example.png')

    # Loaders
    model, _, vae = CheckpointLoaderSimple(_id='3940', ckpt_name=CKPT_NAME)
    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='4010', ckpt_name=CKPT_NAME)

    # Sampling
    ksamplerselect = KSamplerSelect(_id='4831', sampler_name='euler_ancestral_cfg_pp')

    randomnoise = RandomNoise(
        _id='4832',
        noise_seed=DEFAULT_SEED,
        control_after_generate='fixed',
    )

    loadvideo = LoadVideo(_id='5001', file='buildings.mp4')

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        _id='5023',
        text_encoder=TEXT_ENCODER_NAME,
        ckpt_name=CKPT_NAME,
        device='default',
    )

    manualsigmas = ManualSigmas(
        _id='5025',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

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

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='4922',
        lora_name=LORA_NAME_2,
        strength_model=GUIDE_STRENGTH_2,
        model=model,
    )

    images, _, fps = GetVideoComponents(_id='5000', video=loadvideo)

    resizeimagemasknode_3 = ResizeImageMaskNode(
        _id='5035',
        resize_type='scale longer dimension',
        scale_method=LANCZOS,
        input=image,
    )

    positive, negative = LTXVConditioning(
        _id='1241',
        frame_rate=fps,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    model_2, latent_downscale_factor = LTXICLoRALoaderModelOnly(
        _id='5011',
        lora_name=LORA_NAME,
        model=loraloadermodelonly,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='5026',
        resize_type='scale shorter dimension',
        scale_method=LANCZOS,
        input=images,
    )

    ltxfloattoint = LTXFloatToInt(_id='5066', rounding=0, a=fps)

    cannyedgepreprocessor = CannyEdgePreprocessor(
        _id='4991',
        low_threshold=92,
        image=resizeimagemasknode,
    )

    math_int, _ = SimpleMath_2(_id='5034', value='a*32', a=latent_downscale_factor)

    resizeimagemasknode_2 = ResizeImageMaskNode(
        _id='5028',
        resize_type='scale to multiple',
        scale_method=LANCZOS,
        input=cannyedgepreprocessor,
        **{'resize_type.multiple': math_int},
    )

    width, height, batch_size = GetImageSize(_id='5029', image=resizeimagemasknode_2)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='3059',
        width=width,
        height=height,
        length=batch_size,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        _id='3980',
        frames_number=batch_size,
        frame_rate=ltxfloattoint,
        audio_vae=ltxvaudiovaeloader,
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        _id='3159',
        bypass=True,
        image=resizeimagemasknode_3,
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    positive_2, negative_2, latent = LTXAddVideoICLoRAGuide(
        _id='5012',
        crop=1,
        use_tiled_encode='disabled',
        image=resizeimagemasknode_2,
        latent=ltxvimgtovideoconditiononly,
        latent_downscale_factor=latent_downscale_factor,
        negative=negative,
        positive=positive,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='4528',
        audio_latent=ltxvemptylatentaudio,
        video_latent=latent,
    )

    cfgguider = CFGGuider(
        _id='4828',
        cfg=GUIDE_STRENGTH,
        model=model_2,
        negative=negative_2,
        positive=positive_2,
    )

    output, _ = SamplerCustomAdvanced(
        _id='4829',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(_id='4845', av_latent=output)

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='4848',
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent,
    )

    _, _, latent_2 = LTXVCropGuides(
        _id='5013',
        latent=video_latent,
        negative=negative_2,
        positive=positive_2,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        _id='5065',
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        latents=latent_2,
        vae=vae,
    )

    createvideo = CreateVideo(
        _id='4849',
        fps=fps,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode,
    )

    # Outputs
    savevideo = SaveVideo(_id='4852', filename_prefix='output', video=createvideo)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

