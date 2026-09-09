# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import ImageBlur
from vibecomfy.nodes.kjnodes import ImageConcatMulti
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlEmbeds, WanVideoDecode, WanVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoVAELoader


CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
LORA_NAME = 'WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors'
MODEL_NAME = 'WanVideo/wan2.1_t2v_1.3B_fp16.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=0, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoControlEmbeds', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json', 'source_id': 'video/wanvideo_wrapper_13b_control_lora', 'upstream_source_id': 'wan13b_control_lora', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_13b_control_lora'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        _id='11',
        model_name=CLIP_NAME,
    )

    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=VAE_NAME)

    wanvideoteacache = WanVideoTeaCache(
        _id='52',
        rel_l1_thresh=0.1,
        use_coefficients='true',
    )

    image, _, _, _ = VHS_LoadVideo(
        _id='97',
        video='wolf_interpolated.mp4',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'wolf_interpolated.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': 'image'},
    )

    wanvideoloraselect = WanVideoLoraSelect(_id='98', lora=LORA_NAME)

    wanvideotextencode = WanVideoTextEncode(
        _id='16',
        positive_prompt='video of a wolf',
        negative_prompt=DEFAULT_NEGATIVE,
        t5=loadwanvideot5textencoder,
    )

    wanvideomodelloader = WanVideoModelLoader(
        _id='22',
        model=MODEL_NAME,
        base_precision='fp16',
        lora=wanvideoloraselect,
    )

    imageblur = ImageBlur(
        _id='104',
        widget_0=4,
        widget_1=1,
        image=image,
    )

    wanvideoencode = WanVideoEncode(
        _id='95',
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1.0000000000000002,
        image=imageblur,
        vae=wanvideovaeloader,
    )

    wanvideocontrolembeds = WanVideoControlEmbeds(
        _id='96',
        end_percent=0.7,
        latents=wanvideoencode,
    )

    samples, _ = WanVideoSampler(
        _id='27',
        seed=0,
        batched_cfg='',
        cache_args=wanvideoteacache,
        image_embeds=wanvideocontrolembeds,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(_id='28', samples=samples, vae=wanvideovaeloader)

    imageconcatmulti = ImageConcatMulti(
        _id='103',
        unused_3=None,
        image_1=imageblur,
        image_2=wanvideodecode,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='30',
        frame_rate=16,
        filename_prefix='WanVideoWrapper_I2V',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_I2V_00159.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_I2V_00159.png', 'fullpath': 'N:\\AI\\ComfyUI\\output\\WanVideoWrapper_I2V_00159.mp4'}},
        images=imageconcatmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_I2V')

