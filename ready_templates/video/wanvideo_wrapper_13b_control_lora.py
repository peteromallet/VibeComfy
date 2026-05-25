# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import ImageBlur
from vibecomfy.nodes.kjnodes import ImageConcatMulti
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlEmbeds, WanVideoDecode, WanVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 0
LORA_NAME = 'WanVid\\wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='control_lora_video',
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoControlEmbeds', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='WanVideoWrapper 1.3B control LoRA',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME)
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)
    wanvideoteacache = WanVideoTeaCache(rel_l1_thresh=0.1, use_coefficients='true')
    wanvideotorchcompilesettings_2 = WanVideoTorchCompileSettings()
    image, frame_count, audio, video_info = VHS_LoadVideo(video='wolf_interpolated.mp4')
    wanvideoloraselect = WanVideoLoraSelect(lora=LORA_NAME)

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt='video of a wolf',
        negative_prompt=DEFAULT_NEGATIVE,
        t5=loadwanvideot5textencoder,
    )

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_3,
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
        steps=1,
        seed=DEFAULT_SEED,
        batched_cfg='',
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
    vhs_videocombine = VHS_VideoCombine(images=imageconcatmulti)


    PUBLIC_INPUTS = {
        'model': InputSpec(node=loadwanvideot5textencoder, field='model_name', default=MODEL_NAME),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

