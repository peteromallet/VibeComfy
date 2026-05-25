# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import PreviewImage
from vibecomfy.nodes.kjnodes import GetImagesFromBatchIndexed, INTConstant, ImageResizeKJv2, PreviewAnimation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlnet, WanVideoControlnetLoader, WanVideoDecode, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoEnhanceAVideo, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FPS = 24
DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = 'Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"'
DEFAULT_PROMPT = "Close-up shot with soft lighting, focusing sharply on the lower half of a young woman's face. Her lips are slightly parted as she blows an enormous bubblegum bubble. The bubble is semi-transparent, shimmering gently under the light, and surprisingly contains a miniature aquarium inside, where two orange-and-white goldfish slowly swim, their fins delicately fluttering as if in an aquatic universe. The background is a pure light blue color."
DEFAULT_SEED = 47
DEVICE = 'cpu'
GUIDE_STRENGTH = 5
KEEP_PROPORTION = 'stretch'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'Wan2_2_VAE_bf16.safetensors'
MODEL_NAME_3 = 'wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors'
MODEL_NAME_4 = 'Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors'
UPSCALE_METHOD = 'nearest-exact'

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video_controlnet',
    requirements={'models': ['Wan2_2_VAE_bf16.safetensors', 'umt5-xxl-enc-bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PreviewAnimation'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='WanVideoWrapper 2.2 5B image-to-video ControlNet',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v_controlnet.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME)
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)

    wanvideoexperimentalargs = WanVideoExperimentalArgs(
        cfg_zero_star=True,
        use_tcfg=True,
    )

    wanvideoslg = WanVideoSLG(blocks='7,8,9', end_percent=0.7)
    wanvideoeasycache = WanVideoEasyCache()
    wanvideocontrolnetloader = WanVideoControlnetLoader(model=MODEL_NAME_3)
    wanvideoenhanceavideo = WanVideoEnhanceAVideo()
    intconstant = INTConstant(value=121)
    intconstant_2 = INTConstant(value=1280)
    intconstant_3 = INTConstant(value=704)

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_4,
        base_precision='fp16',
        compile_args=wanvideotorchcompilesettings,
    )

    image, frame_count, audio, video_info = VHS_LoadVideo(
        video='wolf_interpolated.mp4',
        frame_load_cap=intconstant,
    )

    image_image, width, height, mask = ImageResizeKJv2(
        upscale_method=UPSCALE_METHOD,
        keep_proportion=KEEP_PROPORTION,
        device=DEVICE,
        width=intconstant_2,
        height=intconstant_3,
        image=image,
    )

    midas_depthmappreprocessor = raw_call('MiDaS-DepthMapPreprocessor', '104',
        widget_0=6.28318530718,
        widget_1=0.1,
        widget_2=512,
        image=image_image,
    )

    getimagesfrombatchindexed = GetImagesFromBatchIndexed(
        widget_0='0',
        images=image_image,
    )

    image_image_2, width_image, height_image, mask_image = ImageResizeKJv2(
        upscale_method=UPSCALE_METHOD,
        keep_proportion=KEEP_PROPORTION,
        device=DEVICE,
        width=intconstant_2,
        height=intconstant_3,
        image=midas_depthmappreprocessor.out(0),
    )

    wanvideoencode = WanVideoEncode(
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=getimagesfrombatchindexed,
        vae=wanvideovaeloader,
    )

    # Outputs
    previewimage = PreviewImage(images=getimagesfrombatchindexed)

    wanvideocontrolnet = WanVideoControlnet(
        widget_0=1,
        widget_1=3,
        widget_2=0,
        widget_3=1,
        control_images=image_image_2,
        controlnet=wanvideocontrolnetloader,
        model=wanvideomodelloader,
    )

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        num_frames=DEFAULT_FRAMES,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        extra_latents=wanvideoencode,
        height=intconstant_3,
        width=intconstant_2,
    )

    previewanimation = PreviewAnimation(fps=DEFAULT_FPS, images=image_image_2)

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideocontrolnet,
        t5=loadwanvideot5textencoder,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=1,
        cfg=GUIDE_STRENGTH,
        shift=8,
        seed=DEFAULT_SEED,
        scheduler='flowmatch_pusa',
        batched_cfg='',
        add_noise_to_samples='',
        cache_args=wanvideoeasycache,
        experimental_args=wanvideoexperimentalargs,
        feta_args=wanvideoenhanceavideo,
        image_embeds=wanvideoemptyembeds,
        model=wanvideocontrolnet,
        slg_args=wanvideoslg,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    vhs_videocombine = VHS_VideoCombine(images=wanvideodecode)


    PUBLIC_INPUTS = {
        'model': InputSpec(node=loadwanvideot5textencoder, field='model_name', default=MODEL_NAME),
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED),
        'fps': InputSpec(node=previewanimation, field='fps', default=DEFAULT_FPS),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=previewimage, output_type='PreviewImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

