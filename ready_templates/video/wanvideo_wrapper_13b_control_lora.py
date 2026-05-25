# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import PublicInput, ready_template, ReadyMetadata
from vibecomfy.nodes.core import ImageBlur
from vibecomfy.nodes.kjnodes import ImageConcatMulti
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlEmbeds, WanVideoDecode, WanVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


BF16 = 'bf16'
DEFAULT = 'default'
DEFAULT_SEED = 0
DISABLED = 'disabled'
GUIDE_STRENGTH = 6
INDUCTOR = 'inductor'
OFFLOAD_DEVICE = 'offload_device'

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoControlEmbeds', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json', 'source_id': 'wan13b_control_lora', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_13b_control_lora'},
)

PUBLIC_INPUTS = {
    'seed': PublicInput(node='samples', field='seed', default=DEFAULT_SEED, type='INT'),
}
OUTPUT = dict(
    node='vhs_videocombine',
    output_type='VHS_VideoCombine',
    name='video',
    artifact_kind='video',
    mime_type='video/mp4',
    expected_cardinality='one',
    filename_prefix='WanVideoWrapper_I2V',
)


@ready_template(READY_METADATA, source_path=__file__, inputs=PUBLIC_INPUTS, output=OUTPUT)
def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        model_name='umt5-xxl-enc-bf16.safetensors',
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()

    wanvideovaeloader = WanVideoVAELoader(
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
    )

    wanvideoteacache = WanVideoTeaCache(rel_l1_thresh=0.1, use_coefficients='true')
    wanvideotorchcompilesettings_2 = WanVideoTorchCompileSettings()

    image, frame_count, audio, video_info = VHS_LoadVideo(
        video='wolf_interpolated.mp4',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'wolf_interpolated.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': 'image'},
    )

    wanvideoloraselect = WanVideoLoraSelect(
        lora='WanVid\\wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors',
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt='video of a wolf',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        t5=loadwanvideot5textencoder,
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors',
        base_precision='fp16',
        lora=wanvideoloraselect,
    )

    imageblur = ImageBlur(widget_0=4, widget_1=1, image=image)

    wanvideoencode = WanVideoEncode(
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1.0000000000000002,
        image=imageblur,
        vae=wanvideovaeloader,
    )

    wanvideocontrolembeds = WanVideoControlEmbeds(
        end_percent=0.7,
        latents=wanvideoencode,
    )

    samples, denoised_samples = WanVideoSampler(
        seed=DEFAULT_SEED,
        batched_cfg='',
        unused_widget_4='fixed',
        cache_args=wanvideoteacache,
        image_embeds=wanvideocontrolembeds,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(samples=samples, vae=wanvideovaeloader)

    imageconcatmulti = ImageConcatMulti(
        unused_3=None,
        image_1=imageblur,
        image_2=wanvideodecode,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
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
