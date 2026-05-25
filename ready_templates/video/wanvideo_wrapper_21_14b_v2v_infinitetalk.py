# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPVisionLoader, GetImageRangeFromBatch, LoadAudio, PreviewAny
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import DownloadAndLoadWav2VecModel, MultiTalkModelLoader, MultiTalkWav2VecEmbeds, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoEncode, WanVideoImageToVideoMultiTalk, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader, Wav2VecModelLoader


BF16 = 'bf16'
CLIP_VISION_MODEL = 'clip_vision_model'
DEFAULT_FPS = 1.5
DEFAULT_FRAMES = 1
DEFAULT_SEED = 2
DISABLED = 'disabled'
FP16 = 'fp16'
GUIDE_STRENGTH = 1.0000000000000002
HEIGHT = 'height'
INPUT_AUDIO = 'input_audio'
MAIN_DEVICE = 'main_device'
MAX_FRAMES = 'max_frames'
VAE = 'VAE'
WANMODEL = 'wanmodel'
WIDTH = 'width'

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'source_id': 'wan21_14b_v2v_infinitetalk', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'source_ref': '/Users/peteromalley/Documents/.megaplan-worktrees/scratchpad-emitter/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'source_kind': 'raw_json', 'indexed_id': None, 'workflow_source_id': 'wan21_14b_v2v_infinitetalk', 'workflow_source_type': 'api', 'raw_workflow_shape': 'ui', 'source_hash': 'sha256:a0951c61b13ec6755772adfc5c13afe133284363e02053574a9fcbfd4c43817e', 'workflow_shape': {'nodes': 53, 'runtime_nodes': 31, 'helper_nodes': 22, 'edges': 47, 'inputs': 2, 'outputs': 1}, 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_v2v_infinitetalk'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    multitalkmodelloader = MultiTalkModelLoader(
        model='WanVideo\\InfiniteTalk\\InfiniteTalk\\Wan2_1-InfiniteTalk_Single_Q8.gguf',
    )

    loadaudio = LoadAudio(
        audio='one-does-not-simply-walk-into-mordor-its-black-gates-are-guarded-by-more-than-just-orcs.mp3',
        widget_1=None,
        widget_2=None,
    )

    wanvideovaeloader = WanVideoVAELoader(
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
    )

    wanvideoblockswap = WanVideoBlockSwap(use_non_blocking=True, prefetch_blocks=1)

    downloadandloadwav2vecmodel = DownloadAndLoadWav2VecModel(
        model='TencentGameMate/chinese-wav2vec2-base',
    )

    wanvideoloraselect = WanVideoLoraSelect(
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        merge_loras=False,
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    clipvisionloader = CLIPVisionLoader(clip_name='clip_vision_h.safetensors')

    text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
        model_name='umt5-xxl-enc-bf16.safetensors',
        positive_prompt='a woman is singing a lullaby',
        negative_prompt='bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards',
        use_disk_cache=False,
    )

    intconstant = INTConstant(value=640)
    intconstant_2 = INTConstant(value=640)
    intconstant_3 = INTConstant(value=1000)

    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '303',
        _outputs=('model',),
        model='MelBandRoFormer\\MelBandRoformer_fp16.safetensors',
    )

    wav2vecmodelloader = Wav2VecModelLoader(
        model='wav2vec2-chinese-base_fp16.safetensors',
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\wan2.1-i2v-14b-480p-Q8_0.gguf',
        base_precision='fp16',
        block_swap_args=wanvideoblockswap,
        lora=wanvideoloraselect,
        multitalk_model=multitalkmodelloader,
    )

    image, frame_count, audio_load, video_info = VHS_LoadVideo(
        format='Wan',
        video='10.mp4',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': '10.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': None, 'custom_height': 480, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        custom_height=intconstant_2,
        custom_width=intconstant,
        **{'choose video to upload': 'image'},
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '304',
        _outputs=('audio', 'instrumental'),
        audio=loadaudio,
        model=melbandroformermodelloader.out('model'),
    )

    multitalk_embeds, audio, num_frames = MultiTalkWav2VecEmbeds(
        audio_cfg_scale='para',
        fps=DEFAULT_FPS,
        normalize_loudness=400,
        audio_1=melbandroformersampler.out('audio'),
        num_frames=intconstant_3,
        wav2vec_model=downloadandloadwav2vecmodel,
    )

    image_image, width, height, mask = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=16,
        device='cpu',
        width=intconstant,
        height=intconstant_2,
        image=image,
    )

    wanvideoencode = WanVideoEncode(
        enable_vae_tiling=272,
        noise_aug_strength=1,
        tile_stride_x=128,
        tile_stride_y=0,
        tile_y=144,
        image=image_image,
        vae=wanvideovaeloader,
    )

    image_get, mask_get = GetImageRangeFromBatch(images=image_image)
    previewany = PreviewAny(source=num_frames)
    image_get_2, width_get, height_get, count = GetImageSizeAndCount(image=image_get)

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        clip_vision=clipvisionloader,
        image_1=image_get_2,
    )

    image_embeds, output_path = WanVideoImageToVideoMultiTalk(
        colormatch=False,
        force_offload='disabled',
        frame_window_size=9,
        motion_frame=False,
        tiled_vae='infinitetalk',
        clip_embeds=wanvideoclipvisionencode,
        height=height_get,
        start_image=image_get_2,
        vae=wanvideovaeloader,
        width=width_get,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=4,
        cfg=GUIDE_STRENGTH,
        shift=11.000000000000002,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        start_step=2,
        add_noise_to_samples=True,
        unused_widget_4='fixed',
        image_embeds=image_embeds,
        model=wanvideomodelloader,
        multitalk_embeds=multitalk_embeds,
        samples=wanvideoencode,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_get_3, width_get_2, height_get_2, count_get = GetImageSizeAndCount(
        image=wanvideodecode,
    )

    image_get_4, mask_get_2 = GetImageRangeFromBatch(
        images=image_get_3,
        num_frames=count_get,
    )

    imageconcatmulti = ImageConcatMulti(
        direction='left',
        unused_3=None,
        image_1=image_get_4,
        image_2=image_image,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
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


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
        'fps': InputSpec(node=multitalk_embeds, field='fps', default=DEFAULT_FPS, type='FLOAT'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_1_InfiniteTalk')

