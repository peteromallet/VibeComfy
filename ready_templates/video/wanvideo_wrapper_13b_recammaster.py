# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, GetImageRangeFromBatch, PreviewImage
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageResizeKJ, WidgetToString
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, ReCamMasterPoseVisualizer, WanVideoBlockSwap, WanVideoDecode, WanVideoEncode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoReCamMasterCameraEmbed, WanVideoReCamMasterDefaultCamera, WanVideoReCamMasterGenerateOrbitCamera, WanVideoSampler, WanVideoTeaCache, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader, WanVideoVRAMManagement

# --- legacy SymbolicNodeRef shim (this template is marked manual; the
# public ``vibecomfy.templates.ref`` symbol is retired) -------------------
class SymbolicNodeRef:
    """Local copy of the retired ``vibecomfy.templates.SymbolicNodeRef``."""

    __slots__ = ("label",)

    def __init__(self, label):
        self.label = label

    def __repr__(self):
        return f"SymbolicNodeRef({self.label!r})"

    def __eq__(self, other):
        return isinstance(other, SymbolicNodeRef) and self.label == other.label

    def __hash__(self):
        return hash(("SymbolicNodeRef", self.label))

    def resolve(self, namespace, wf):
        value = namespace.get(self.label)
        node_id = None
        if hasattr(value, "node_id"):
            node_id = str(value.node_id)
        elif hasattr(value, "node") and value.node is not None and hasattr(value.node, "id"):
            node_id = str(value.node.id)
        elif hasattr(value, "id"):
            node_id = str(value.id)
        elif isinstance(value, str):
            node_id = value
        if node_id is None or node_id not in wf.nodes:
            raise ValueError(
                f"SymbolicNodeRef({self.label!r}) could not be resolved to a node "
                f"in workflow {wf.id!r}"
            )
        wf.metadata.setdefault("id_map", {})[self.label] = node_id
        return node_id


def ref(label):
    """Local copy of the retired ``vibecomfy.templates.ref``."""

    return SymbolicNodeRef(label)
# --- end legacy shim -----------------------------------------------------


DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 42
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\Wan2_1_kwai_recammaster_1_3B_step20000_bf16.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'umt5_xxl_fp16.safetensors'
WIDGET_0 = ''
WIDGET_0_2 = 'WanModel'
WIDGET_0_3 = 'TextEmbeds'
WIDGET_0_4 = 'WanVAE'
WIDGET_0_5 = 'InputLatents'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
}

READY_METADATA = ReadyMetadata.build(
    capability='camera_control_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='ReCamMaster camera-control workflow',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
        _id='11',
        model_name=MODEL_NAME,
    )
    wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

    wanvideomodelloader = WanVideoModelLoader(_id='22', model=MODEL_NAME_2)
    wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
    wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_3)
    wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
    wanvideoblockswap = WanVideoBlockSwap(_id='39', use_non_blocking=True)
    wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id
    wanvideovrammanagement = WanVideoVRAMManagement(_id='45', widget_0=1)
    wf.metadata.setdefault('id_map', {})['wanvideovrammanagement'] = wanvideovrammanagement.node.id
    # Loaders
    cliploader = CLIPLoader(_id='48', clip_name=MODEL_NAME_4, type_='wan')
    wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
    wanvideoteacache = WanVideoTeaCache(
        _id='52',
        widget_0=0.1,
        widget_1=6,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e0',
    )
    wf.metadata.setdefault('id_map', {})['wanvideoteacache'] = wanvideoteacache.node.id

    downloadandloadflorence2model = raw_call(wf, 'DownloadAndLoadFlorence2Model', '124',
        widget_0='MiaoshouAI/Florence-2-base-PromptGen-v2.0',
        widget_1='fp16',
        widget_2='sdpa',
    )
    wf.metadata.setdefault('id_map', {})['downloadandloadflorence2model'] = downloadandloadflorence2model.node.id

    wanvideoexperimentalargs = WanVideoExperimentalArgs(
        _id='127',
        widget_0=WIDGET_0,
        widget_1=True,
        widget_2=False,
        widget_3=0,
    )
    wf.metadata.setdefault('id_map', {})['wanvideoexperimentalargs'] = wanvideoexperimentalargs.node.id

    vhs_loadvideo = VHS_LoadVideo(
        _id='128',
        video='wolf_interpolated.mp4',
        _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
    )
    wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

    getnode = raw_call(wf, 'GetNode', '141', widget_0=WIDGET_0_2)
    wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
    getnode_2 = raw_call(wf, 'GetNode', '143', widget_0=WIDGET_0_3)
    wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
    getnode_3 = raw_call(wf, 'GetNode', '145', widget_0=WIDGET_0_4)
    wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
    getnode_4 = raw_call(wf, 'GetNode', '146', widget_0=WIDGET_0_4)
    wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
    getnode_5 = raw_call(wf, 'GetNode', '157', widget_0=WIDGET_0_5)
    wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
    wanvideorecammastergenerateorbitcamera = WanVideoReCamMasterGenerateOrbitCamera(
        _id='206',
        widget_0=81,
        widget_1=90,
    )
    wf.metadata.setdefault('id_map', {})['wanvideorecammastergenerateorbitcamera'] = wanvideorecammastergenerateorbitcamera.node.id

    # Conditioning
    cliptextencode = CLIPTextEncode(_id='49', text=DEFAULT_PROMPT, clip=cliploader)
    wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id
    cliptextencode_2 = CLIPTextEncode(
        _id='50',
        text=DEFAULT_PROMPT_2,
        clip=cliploader,
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

    getimagesizeandcount = GetImageSizeAndCount(
        _id='129',
        image=vhs_loadvideo.out('IMAGE'),
        _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
    )
    wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

    setnode = raw_call(wf, 'SetNode', '140',
        widget_0=WIDGET_0_2,
        WANVIDEOMODEL=wanvideomodelloader,
    )
    wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

    setnode_3 = raw_call(wf, 'SetNode', '144',
        widget_0=WIDGET_0_4,
        WANVAE=wanvideovaeloader,
    )
    wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

    wanvideorecammasterdefaultcamera = WanVideoReCamMasterDefaultCamera(
        _id='205',
        widget_0='pan_right',
        latents=getnode_5.out(0),
    )
    wf.metadata.setdefault('id_map', {})['wanvideorecammasterdefaultcamera'] = wanvideorecammasterdefaultcamera.node.id

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        _id='46',
        negative=cliptextencode_2,
        positive=cliptextencode,
    )
    wf.metadata.setdefault('id_map', {})['wanvideotextembedbridge'] = wanvideotextembedbridge.node.id

    wanvideorecammastercameraembed = WanVideoReCamMasterCameraEmbed(
        _id='56',
        camera_poses=wanvideorecammasterdefaultcamera,
        latents=getnode_5.out(0),
        _outputs=('CAMERA_EMBEDS', 'CAMERA_POSES'),
    )
    wf.metadata.setdefault('id_map', {})['wanvideorecammastercameraembed'] = wanvideorecammastercameraembed.node.id

    imageresizekj = ImageResizeKJ(
        _id='59',
        widget_0=832,
        widget_1=480,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5='center',
        image=getimagesizeandcount.out('IMAGE'),
        _outputs=('IMAGE', 'WIDTH', 'HEIGHT'),
    )
    wf.metadata.setdefault('id_map', {})['imageresizekj'] = imageresizekj.node.id

    widgettostring = WidgetToString(
        _id='74',
        widget_0=0,
        widget_1='camera_type',
        widget_2=False,
        widget_3='',
        widget_4=2,
        any_input=wanvideorecammasterdefaultcamera,
    )
    wf.metadata.setdefault('id_map', {})['widgettostring'] = widgettostring.node.id

    getimagerangefrombatch = GetImageRangeFromBatch(
        _id='130',
        widget_0=0,
        widget_1=1,
        images=imageresizekj.out('IMAGE'),
        _outputs=('IMAGE', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['getimagerangefrombatch'] = getimagerangefrombatch.node.id

    recammasterposevisualizer = ReCamMasterPoseVisualizer(
        _id='138',
        widget_0=0.1,
        widget_1=0.2,
        widget_2=0.4,
        widget_3=0.5,
        camera_poses=wanvideorecammastercameraembed.out('CAMERA_POSES'),
    )
    wf.metadata.setdefault('id_map', {})['recammasterposevisualizer'] = recammasterposevisualizer.node.id

    setnode_4 = raw_call(wf, 'SetNode', '147',
        widget_0='InputVideo',
        IMAGE=imageresizekj.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

    wanvideosampler = WanVideoSampler(
        _id='155',
        steps=1,
        seed=DEFAULT_SEED,
        cache_args=wanvideoteacache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=wanvideorecammastercameraembed.out('CAMERA_EMBEDS'),
        model=getnode.out(0),
        text_embeds=getnode_2.out(0),
        _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
    )
    wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

    wanvideodecode = WanVideoDecode(
        _id='28',
        samples=wanvideosampler.out('SAMPLES'),
        vae=getnode_3.out(0),
    )
    wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

    wanvideoencode = WanVideoEncode(
        _id='58',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=setnode_4.out(0),
        vae=getnode_4.out(0),
    )
    wf.metadata.setdefault('id_map', {})['wanvideoencode'] = wanvideoencode.node.id

    florence2run = raw_call(wf, 'Florence2Run', '123',
        widget_0=WIDGET_0,
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
        image=getimagerangefrombatch.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['florence2run'] = florence2run.node.id

    # Outputs
    previewimage = PreviewImage(
        _id='131',
        images=getimagerangefrombatch.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['previewimage'] = previewimage.node.id

    previewimage_2 = PreviewImage(_id='139', images=recammasterposevisualizer)
    wf.metadata.setdefault('id_map', {})['previewimage_2'] = previewimage_2.node.id
    wanvideotextencode = WanVideoTextEncode(
        _id='16',
        negative_prompt=DEFAULT_NEGATIVE,
        positive_prompt=florence2run.out(2),
        t5=loadwanvideot5textencoder,
    )
    wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

    addlabel = AddLabel(
        _id='122',
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
    wf.metadata.setdefault('id_map', {})['addlabel'] = addlabel.node.id

    showtext_pysssss = raw_call(wf, 'ShowText|pysssss', '125',
        widget_0='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        widget_1='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        text=florence2run.out(2),
    )
    wf.metadata.setdefault('id_map', {})['showtext_pysssss'] = showtext_pysssss.node.id

    setnode_5 = raw_call(wf, 'SetNode', '156',
        widget_0=WIDGET_0_5,
        LATENT=wanvideoencode,
    )
    wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

    vhs_videocombine = VHS_VideoCombine(_id='30', images=addlabel)
    wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id
    setnode_2 = raw_call(wf, 'SetNode', '142',
        widget_0=WIDGET_0_3,
        WANVIDEOTEXTEMBEDS=wanvideotextencode,
    )
    wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

