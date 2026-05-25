# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, GetImageRangeFromBatch, PreviewImage
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageResizeKJ, WidgetToString
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, ReCamMasterPoseVisualizer, WanVideoBlockSwap, WanVideoDecode, WanVideoEncode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoReCamMasterCameraEmbed, WanVideoReCamMasterDefaultCamera, WanVideoReCamMasterGenerateOrbitCamera, WanVideoSampler, WanVideoTeaCache, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader, WanVideoVRAMManagement


DEFAULT_FRAMES = 81
DEFAULT_FRAMES_2 = 1
DEFAULT_SEED = 42
INPUTLATENTS = 'InputLatents'
TEXTEMBEDS = 'TextEmbeds'
WANMODEL = 'WanModel'
WANVAE = 'WanVAE'

READY_METADATA = ReadyMetadata.build(
    capability='camera_control_video',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'version': 'unknown', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git', 'version': 'unknown', 'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='ReCamMaster camera-control workflow',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        model_name='umt5-xxl-enc-bf16.safetensors',
    )

    wanvideomodelloader = WanVideoModelLoader(
        model='WanVideo\\Wan2_1_kwai_recammaster_1_3B_step20000_bf16.safetensors',
    )

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()

    wanvideovaeloader = WanVideoVAELoader(
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
    )

    wanvideoblockswap = WanVideoBlockSwap(use_non_blocking=True)
    wanvideovrammanagement = WanVideoVRAMManagement()
    cliploader = CLIPLoader(clip_name='umt5_xxl_fp16.safetensors', type_='wan')

    wanvideoteacache = WanVideoTeaCache(
        mode='e0',
        rel_l1_thresh=0.1,
        start_step=6,
        use_coefficients='true',
    )

    downloadandloadflorence2model = raw_call('DownloadAndLoadFlorence2Model', '124',
        widget_0='MiaoshouAI/Florence-2-base-PromptGen-v2.0',
        widget_1='fp16',
        widget_2='sdpa',
    )

    wanvideoexperimentalargs = WanVideoExperimentalArgs(cfg_zero_star=True)

    image_load, frame_count, audio, video_info = VHS_LoadVideo(
        video='wolf_interpolated.mp4',
    )

    wanvideorecammastergenerateorbitcamera = WanVideoReCamMasterGenerateOrbitCamera()

    # Conditioning
    cliptextencode = CLIPTextEncode(
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=cliploader,
    )

    cliptextencode_2 = CLIPTextEncode(
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader,
    )

    image_get, width_get, height_get, count = GetImageSizeAndCount(image=image_load)

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    image, width, height = ImageResizeKJ(
        widget_0=832,
        widget_1=480,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5='center',
        image=image_get,
    )

    wanvideoencode = WanVideoEncode(
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=image,
        vae=wanvideovaeloader,
    )

    image_get_2, mask = GetImageRangeFromBatch(images=image)

    florence2run = raw_call('Florence2Run', '123',
        widget_0='',
        widget_1='detailed_caption',
        widget_2=True,
        widget_3=False,
        widget_4=1024,
        widget_5=3,
        widget_6=True,
        widget_7='',
        widget_8=1,
        widget_9='fixed',
        florence2_model=downloadandloadflorence2model.out(0),
        image=image_get_2,
    )

    # Outputs
    previewimage = PreviewImage(images=image_get_2)

    wanvideorecammasterdefaultcamera = WanVideoReCamMasterDefaultCamera(
        latents=wanvideoencode,
    )

    wanvideotextencode = WanVideoTextEncode(
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        positive_prompt=florence2run.out(2),
        t5=loadwanvideot5textencoder,
    )

    camera_embeds, camera_poses = WanVideoReCamMasterCameraEmbed(
        camera_poses=wanvideorecammasterdefaultcamera,
        latents=wanvideoencode,
    )

    widgettostring = WidgetToString(
        node_title=2,
        widget_3='',
        widget_name='camera_type',
        any_input=wanvideorecammasterdefaultcamera,
    )

    showtext_pysssss = raw_call('ShowText|pysssss', '125',
        widget_0='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        widget_1='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        text=florence2run.out(2),
    )

    recammasterposevisualizer = ReCamMasterPoseVisualizer(
        scale=0.5,
        widget_0=0.1,
        zval=0.4,
        camera_poses=camera_poses,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=1,
        seed=DEFAULT_SEED,
        cache_args=wanvideoteacache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=camera_embeds,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(samples=samples, vae=wanvideovaeloader)
    previewimage_2 = PreviewImage(images=recammasterposevisualizer)

    addlabel = AddLabel(
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMonoBoldOblique.otf',
        widget_7='input',
        widget_8='up',
        image=wanvideodecode,
        text=widgettostring,
    )

    vhs_videocombine = VHS_VideoCombine(images=addlabel)


    PUBLIC_INPUTS = {
        'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
        'prompt': InputSpec(node=cliptextencode, field='text', default="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall", type='STRING', required=True, media_semantics='text'),
    }
    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

