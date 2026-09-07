# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPVisionLoader, GetImageRangeFromBatch, LoadAudio
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.melbandroformer import MelBandRoFormerModelLoader, MelBandRoFormerSampler
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import DownloadAndLoadWav2VecModel, MultiTalkModelLoader, MultiTalkWav2VecEmbeds, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoEncode, WanVideoImageToVideoMultiTalk, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEncodeCached, WanVideoVAELoader


CLIP_NAME = 'clip_vision_h.safetensors'
CLIP_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_NEGATIVE = 'bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards'
DEFAULT_SEED = 2
GUIDE_STRENGTH = 1.0000000000000002
LORA_NAME = 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoFormer/MelBandRoformer_fp16.safetensors'
MODEL_NAME = 'WanVideo/InfiniteTalk/InfiniteTalk/Wan2_1-InfiniteTalk_Single_Q8.gguf'
MODEL_NAME_2 = 'WanVideo/wan2.1-i2v-14b-480p-Q8_0.gguf'
MODEL_NAME_3 = 'TencentGameMate/chinese-wav2vec2-base'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='128', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncodeCached', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'source_id': 'video/wanvideo_wrapper_21_14b_v2v_infinitetalk', 'upstream_source_id': 'wan21_14b_v2v_infinitetalk', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_v2v_infinitetalk'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    multitalkmodelloader = MultiTalkModelLoader(_id='120', model=MODEL_NAME)

    loadaudio = LoadAudio(
        _id='125',
        audio='one-does-not-simply-walk-into-mordor-its-black-gates-are-guarded-by-more-than-just-orcs.mp3',
    )

    wanvideovaeloader = WanVideoVAELoader(_id='129', model_name=VAE_NAME)

    wanvideoblockswap = WanVideoBlockSwap(
        _id='134',
        use_non_blocking=True,
        prefetch_blocks=1,
    )

    downloadandloadwav2vecmodel = DownloadAndLoadWav2VecModel(
        _id='137',
        model=MODEL_NAME_3,
    )

    wanvideoloraselect = WanVideoLoraSelect(
        _id='138',
        lora=LORA_NAME,
        merge_loras=False,
    )

    # Loaders
    clipvisionloader = CLIPVisionLoader(_id='238', clip_name=CLIP_NAME)

    text_embeds, _, _ = WanVideoTextEncodeCached(
        _id='241',
        model_name=CLIP_NAME_2,
        positive_prompt='a woman is singing a lullaby',
        negative_prompt=DEFAULT_NEGATIVE,
        use_disk_cache=False,
    )

    intconstant = INTConstant(_id='245', value=640)
    intconstant_2 = INTConstant(_id='246', value=640)
    intconstant_3 = INTConstant(_id='270', value=1000)

    melbandroformermodelloader = MelBandRoFormerModelLoader(
        _id='303',
        model=MEL_BAND_ROFORMER_NAME,
    )

    wanvideomodelloader = WanVideoModelLoader(
        _id='122',
        model=MODEL_NAME_2,
        base_precision='fp16_fast',
        attention_mode='sageattn',
        block_swap_args=wanvideoblockswap,
        lora=wanvideoloraselect,
        multitalk_model=multitalkmodelloader,
    )

    image, _, _, _ = VHS_LoadVideo(
        _id='228',
        video='10.mp4',
        format='Wan',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': '10.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': None, 'custom_height': 480, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        custom_width=intconstant,
        custom_height=intconstant_2,
        **{'choose video to upload': 'image'},
    )

    melbandroformersampler = MelBandRoFormerSampler(
        _id='304',
        audio=loadaudio,
        model=melbandroformermodelloader.out(0),
    )

    multitalk_embeds, _, _ = MultiTalkWav2VecEmbeds(
        _id='194',
        widget_1=400,
        widget_2=25,
        widget_3=1.5,
        widget_4=1,
        widget_5='para',
        audio_1=melbandroformersampler.out(0),
        num_frames=intconstant_3,
        wav2vec_model=downloadandloadwav2vecmodel,
    )

    image_2, _, _, _ = ImageResizeKJv2(
        _id='230',
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=16,
        device='cpu',
        width=intconstant,
        height=intconstant_2,
        image=image,
    )

    wanvideoencode = WanVideoEncode(
        _id='229',
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=image_2,
        vae=wanvideovaeloader,
    )

    image_3, _ = GetImageRangeFromBatch(_id='231', images=image_2)
    image_4, width_2, height_2, _ = GetImageSizeAndCount(_id='291', image=image_3)

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        _id='237',
        clip_vision=clipvisionloader,
        image_1=image_4,
    )

    image_embeds, _ = WanVideoImageToVideoMultiTalk(
        _id='192',
        colormatch=False,
        force_offload='disabled',
        frame_window_size=9,
        motion_frame=False,
        widget_7='infinitetalk',
        clip_embeds=wanvideoclipvisionencode,
        height=height_2,
        start_image=image_4,
        vae=wanvideovaeloader,
        width=width_2,
    )

    samples, _ = WanVideoSampler(
        _id='128',
        steps=4,
        cfg=GUIDE_STRENGTH,
        shift=11.000000000000002,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        start_step=2,
        add_noise_to_samples=True,
        image_embeds=image_embeds,
        model=wanvideomodelloader,
        multitalk_embeds=multitalk_embeds,
        samples=wanvideoencode,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        _id='130',
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_5, _, _, count_2 = GetImageSizeAndCount(_id='300', image=wanvideodecode)
    image_6, _ = GetImageRangeFromBatch(_id='301', num_frames=count_2, images=image_5)

    imageconcatmulti = ImageConcatMulti(
        _id='299',
        direction='left',
        unused_3=None,
        image_1=image_6,
        image_2=image_2,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='131',
        frame_rate=25,
        filename_prefix='WanVideo2_1_InfiniteTalk',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_1_InfiniteTalk_00007-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'WanVideo2_1_InfiniteTalk_00007.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_InfiniteTalk_00007-audio.mp4'}},
        audio=loadaudio,
        images=imageconcatmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_1_InfiniteTalk')

