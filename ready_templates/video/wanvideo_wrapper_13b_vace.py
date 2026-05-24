# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import EmptyImage, GetImageRangeFromBatch, LoadImage, MaskPreview, PreviewImage
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageConcatMulti, ImagePadKJ, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVACEEncode, WanVideoVACEModelSelect, WanVideoVACEStartToEndFrame, WanVideoVAELoader

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


DEFAULT_NEGATIVE = 'colorful, bad quality, blurry, messy, chaotic'
DEFAULT_NEGATIVE_2 = 'bad quality, blurry, messy, chaotic'
DEFAULT_PROMPT = 'black and white cartoon character'
DEFAULT_PROMPT_2 = 'robotic cybernetic wolf turning his head'
DEFAULT_SEED = 18
DIRECTION = 'down'
DIRECTION_2 = 'left'
GUIDE_STRENGTH = 4.000000000000001
KEEP_PROPORTION = 'crop'
KEEP_PROPORTION_2 = 'pad'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'depth_anything_v2_vitl_fp16.safetensors'
MODEL_NAME_4 = 'WanVideo\\Wan2_1-VACE_module_1_3B_bf16.safetensors'
MODEL_NAME_5 = 'WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors'
PAD_COLOR = '172,172,172'
PAD_COLOR_2 = '255,255,255'
UPSCALE_METHOD = 'lanczos'
VIDEO = 'wolf_interpolated.mp4'
WIDGET_0 = ''
WIDGET_0_10 = 'InputVideo'
WIDGET_0_2 = '8'
WIDGET_0_3 = 'WanVAE'
WIDGET_0_4 = 'WanTextEncoder'
WIDGET_0_5 = 'WanModel'
WIDGET_0_6 = 'start_image'
WIDGET_0_7 = 'end_image'
WIDGET_0_8 = 'reference_image'
WIDGET_0_9 = 'control_video'
WIDGET_3 = 'offload_device'
WIDGET_4 = 'true'
WIDGET_4_2 = 'white'
WIDGET_5 = 'e'
WIDGET_5_2 = 'black'
WIDGET_5_3 = 'color'
WIDGET_6 = 'FreeMono.ttf'
WIDGET_8 = 'up'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('wanvideosampler_3'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp'),
    'width': InputSpec(node=ref('imageresizekjv2'), field='width', default=256),
    'height': InputSpec(node=ref('imageresizekjv2'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='vace_video_control',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='VACE control/edit workflow',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            _id='11',
            model_name=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(
            _id='39',
            blocks_to_swap=0,
            use_non_blocking=True,
            vace_blocks_to_swap=15,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        wanvideoteacache = WanVideoTeaCache(
            _id='52',
            widget_0=0.1,
            widget_1=0,
            widget_2=-1,
            widget_3=WIDGET_3,
            widget_4=WIDGET_4,
            widget_5=WIDGET_5,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoteacache'] = wanvideoteacache.node.id

        # Inputs
        loadimage = LoadImage(
            _id='64',
            image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        wanvideoexperimentalargs = WanVideoExperimentalArgs(
            _id='71',
            widget_0=WIDGET_0,
            widget_1=True,
            widget_2=False,
            widget_3=0,
            widget_4=False,
            widget_5=1,
            widget_6=1.25,
            widget_7=20,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoexperimentalargs'] = wanvideoexperimentalargs.node.id

        wanvideoslg = WanVideoSLG(
            _id='72',
            widget_0=WIDGET_0_2,
            widget_1=0.3,
            widget_2=0.7,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoslg'] = wanvideoslg.node.id

        loadimage_2 = LoadImage(
            _id='112',
            image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-3.webp',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        getnode = raw_call(wf, 'GetNode', '123', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '124', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '126', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        getnode_4 = raw_call(wf, 'GetNode', '127', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '128', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '130', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '131', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '142', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '143', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        wanvideoteacache_2 = WanVideoTeaCache(
            _id='147',
            widget_0=0.1,
            widget_1=0,
            widget_2=-1,
            widget_3=WIDGET_3,
            widget_4=WIDGET_4,
            widget_5=WIDGET_5,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoteacache_2'] = wanvideoteacache_2.node.id

        wanvideoslg_2 = WanVideoSLG(
            _id='149',
            widget_0=WIDGET_0_2,
            widget_1=0.3,
            widget_2=0.71,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoslg_2'] = wanvideoslg_2.node.id

        wanvideoexperimentalargs_2 = WanVideoExperimentalArgs(
            _id='150',
            widget_0=WIDGET_0,
            widget_1=True,
            widget_2=False,
            widget_3=0,
            widget_4=False,
            widget_5=1,
            widget_6=1.25,
            widget_7=20,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoexperimentalargs_2'] = wanvideoexperimentalargs_2.node.id

        getnode_10 = raw_call(wf, 'GetNode', '151', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '152', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '153', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '154', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '166', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        loadimage_3 = LoadImage(
            _id='169',
            image='hunhyuanwolf.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_3'] = loadimage_3.node.id

        vhs_loadvideo = VHS_LoadVideo(
            _id='173',
            video=VIDEO,
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

        downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
            _id='175',
            widget_0=MODEL_NAME_3,
        )
        wf.metadata.setdefault('id_map', {})['downloadandloaddepthanythingv2model'] = downloadandloaddepthanythingv2model.node.id

        getnode_15 = raw_call(wf, 'GetNode', '185', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        getnode_16 = raw_call(wf, 'GetNode', '186', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        wanvideoslg_3 = WanVideoSLG(
            _id='187',
            widget_0=WIDGET_0_2,
            widget_1=0.3,
            widget_2=0.7,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoslg_3'] = wanvideoslg_3.node.id

        wanvideoexperimentalargs_3 = WanVideoExperimentalArgs(
            _id='188',
            widget_0=WIDGET_0,
            widget_1=True,
            widget_2=False,
            widget_3=0,
            widget_4=False,
            widget_5=1,
            widget_6=1.25,
            widget_7=20,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoexperimentalargs_3'] = wanvideoexperimentalargs_3.node.id

        getnode_17 = raw_call(wf, 'GetNode', '189', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '190', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '195', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        vhs_loadvideo_2 = VHS_LoadVideo(
            _id='199',
            video=VIDEO,
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo_2'] = vhs_loadvideo_2.node.id

        getnode_20 = raw_call(wf, 'GetNode', '201', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        wanvideoteacache_3 = WanVideoTeaCache(
            _id='214',
            widget_0=0.1,
            widget_1=0,
            widget_2=-1,
            widget_3=WIDGET_3,
            widget_4=WIDGET_4,
            widget_5=WIDGET_5,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoteacache_3'] = wanvideoteacache_3.node.id

        wanvideovacemodelselect = WanVideoVACEModelSelect(
            _id='224',
            widget_0=MODEL_NAME_4,
        )
        wf.metadata.setdefault('id_map', {})['wanvideovacemodelselect'] = wanvideovacemodelselect.node.id

        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            model_to_offload=getnode_4.out(0),
            t5=getnode_3.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_5,
            base_precision='fp16',
            vace_model=wanvideovacemodelselect,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        setnode_2 = raw_call(wf, 'SetNode', '122',
            widget_0=WIDGET_0_3,
            WANVAE=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        setnode_3 = raw_call(wf, 'SetNode', '125',
            widget_0=WIDGET_0_4,
            WANTEXTENCODER=loadwanvideot5textencoder,
        )
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

        addlabel = AddLabel(
            _id='133',
            widget_0=10,
            widget_1=2,
            widget_2=48,
            widget_3=32,
            widget_4=WIDGET_4_2,
            widget_5=WIDGET_5_2,
            widget_6=WIDGET_6,
            widget_7='start_frame',
            widget_8=WIDGET_8,
            image=getnode_6.out(0),
        )
        wf.metadata.setdefault('id_map', {})['addlabel'] = addlabel.node.id

        addlabel_2 = AddLabel(
            _id='134',
            widget_0=10,
            widget_1=2,
            widget_2=48,
            widget_3=32,
            widget_4=WIDGET_4_2,
            widget_5=WIDGET_5_2,
            widget_6=WIDGET_6,
            widget_7='end_frame',
            widget_8=WIDGET_8,
            image=getnode_7.out(0),
        )
        wf.metadata.setdefault('id_map', {})['addlabel_2'] = addlabel_2.node.id

        addlabel_3 = AddLabel(
            _id='156',
            widget_0=10,
            widget_1=2,
            widget_2=48,
            widget_3=32,
            widget_4=WIDGET_4_2,
            widget_5=WIDGET_5_2,
            widget_6=WIDGET_6,
            widget_7='reference image',
            widget_8=WIDGET_8,
            image=getnode_12.out(0),
        )
        wf.metadata.setdefault('id_map', {})['addlabel_3'] = addlabel_3.node.id

        addlabel_4 = AddLabel(
            _id='157',
            widget_0=10,
            widget_1=2,
            widget_2=48,
            widget_3=32,
            widget_4=WIDGET_4_2,
            widget_5=WIDGET_5_2,
            widget_6=WIDGET_6,
            widget_7='control_video',
            widget_8=WIDGET_8,
            image=getnode_13.out(0),
        )
        wf.metadata.setdefault('id_map', {})['addlabel_4'] = addlabel_4.node.id

        wanvideotextencode_2 = WanVideoTextEncode(
            _id='168',
            positive_prompt=DEFAULT_PROMPT_2,
            negative_prompt=DEFAULT_NEGATIVE_2,
            model_to_offload=getnode_10.out(0),
            t5=getnode_9.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode_2'] = wanvideotextencode_2.node.id

        imagepadkj = ImagePadKJ(
            _id='184',
            widget_0=0,
            widget_1=0,
            widget_2=0,
            widget_3=0,
            widget_4=128,
            widget_5=WIDGET_5_3,
            widget_6='255,255,255',
            image=loadimage_3.out('IMAGE'),
            _outputs=('IMAGES', 'MASKS'),
        )
        wf.metadata.setdefault('id_map', {})['imagepadkj'] = imagepadkj.node.id

        addlabel_5 = AddLabel(
            _id='202',
            widget_0=10,
            widget_1=2,
            widget_2=48,
            widget_3=32,
            widget_4=WIDGET_4_2,
            widget_5=WIDGET_5_2,
            widget_6=WIDGET_6,
            widget_7='input',
            widget_8=WIDGET_8,
            image=getnode_20.out(0),
        )
        wf.metadata.setdefault('id_map', {})['addlabel_5'] = addlabel_5.node.id

        wanvideotextencode_3 = WanVideoTextEncode(
            _id='211',
            positive_prompt=DEFAULT_PROMPT_2,
            negative_prompt=DEFAULT_NEGATIVE_2,
            model_to_offload=getnode_17.out(0),
            t5=getnode_16.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode_3'] = wanvideotextencode_3.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='226',
            width=256,
            height=256,
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            pad_color=PAD_COLOR,
            image=vhs_loadvideo_2.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        imageresizekjv2_2 = ImageResizeKJv2(
            _id='227',
            width=256,
            height=256,
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            pad_color=PAD_COLOR,
            divisible_by=16,
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_2'] = imageresizekjv2_2.node.id

        imageresizekjv2_4 = ImageResizeKJv2(
            _id='229',
            width=256,
            height=256,
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            pad_color=PAD_COLOR,
            divisible_by=16,
            image=vhs_loadvideo.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_4'] = imageresizekjv2_4.node.id

        setnode = raw_call(wf, 'SetNode', '121',
            widget_0=WIDGET_0_5,
            WANVIDEOMODEL=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        imageconcatmulti_2 = ImageConcatMulti(
            _id='136',
            direction=DIRECTION,
            match_image_size=True,
            unused_3=None,
            image_1=addlabel,
            image_2=addlabel_2,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti_2'] = imageconcatmulti_2.node.id

        setnode_4 = raw_call(wf, 'SetNode', '140',
            widget_0=WIDGET_0_6,
            IMAGE=imageresizekjv2_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        imageconcatmulti_4 = ImageConcatMulti(
            _id='160',
            direction=DIRECTION,
            match_image_size=True,
            unused_3=None,
            image_1=addlabel_3,
            image_2=addlabel_4,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti_4'] = imageconcatmulti_4.node.id

        depthanything_v2 = DepthAnything_V2(
            _id='174',
            da_model=downloadandloaddepthanythingv2model,
            images=imageresizekjv2_4.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['depthanything_v2'] = depthanything_v2.node.id

        imagepadkj_2 = ImagePadKJ(
            _id='216',
            widget_0=0,
            widget_1=0,
            widget_2=0,
            widget_3=0,
            widget_4=128,
            widget_5=WIDGET_5_3,
            widget_6='127,127,127',
            image=imageresizekjv2.out('IMAGE'),
            _outputs=('IMAGES', 'MASKS'),
        )
        wf.metadata.setdefault('id_map', {})['imagepadkj_2'] = imagepadkj_2.node.id

        imageresizekjv2_3 = ImageResizeKJv2(
            _id='228',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            pad_color=PAD_COLOR,
            divisible_by=16,
            width=imageresizekjv2_2.out('WIDTH'),
            height=imageresizekjv2_2.out('HEIGHT'),
            image=loadimage_2.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_3'] = imageresizekjv2_3.node.id

        imageresizekjv2_5 = ImageResizeKJv2(
            _id='230',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION_2,
            pad_color=PAD_COLOR_2,
            divisible_by=16,
            width=imageresizekjv2_4.out('WIDTH'),
            height=imageresizekjv2_4.out('HEIGHT'),
            image=imagepadkj.out('IMAGES'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_5'] = imageresizekjv2_5.node.id

        imageresizekjv2_6 = ImageResizeKJv2(
            _id='238',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION_2,
            pad_color=PAD_COLOR_2,
            divisible_by=16,
            width=imageresizekjv2_4.out('WIDTH'),
            height=imageresizekjv2_4.out('HEIGHT'),
            image=loadimage_3.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_6'] = imageresizekjv2_6.node.id

        setnode_5 = raw_call(wf, 'SetNode', '141',
            widget_0=WIDGET_0_7,
            IMAGE=imageresizekjv2_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        setnode_6 = raw_call(wf, 'SetNode', '179',
            widget_0=WIDGET_0_8,
            IMAGE=imageresizekjv2_5.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        setnode_7 = raw_call(wf, 'SetNode', '180',
            widget_0=WIDGET_0_9,
            IMAGE=depthanything_v2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        getimagesizeandcount_6 = GetImageSizeAndCount(
            _id='205',
            image=imagepadkj_2.out('IMAGES'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_6'] = getimagesizeandcount_6.node.id

        getimagerangefrombatch = GetImageRangeFromBatch(
            _id='219',
            widget_0=0,
            widget_1=1,
            images=imagepadkj_2.out('IMAGES'),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch'] = getimagerangefrombatch.node.id

        setnode_8 = raw_call(wf, 'SetNode', '221',
            widget_0=WIDGET_0_10,
            IMAGE=imagepadkj_2.out('IMAGES'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        getimagerangefrombatch_2 = GetImageRangeFromBatch(
            _id='222',
            widget_0=0,
            widget_1=1,
            masks=imagepadkj_2.out('MASKS'),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_2'] = getimagerangefrombatch_2.node.id

        # Outputs
        previewimage_4 = PreviewImage(_id='237', images=imageresizekjv2_5.out('IMAGE'))
        wf.metadata.setdefault('id_map', {})['previewimage_4'] = previewimage_4.node.id
        wanvideovacestarttoendframe = WanVideoVACEStartToEndFrame(
            _id='111',
            widget_0=33,
            widget_1=0.5,
            end_image=setnode_5.out(0),
            start_image=setnode_4.out(0),
            _outputs=('IMAGES', 'MASKS'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideovacestarttoendframe'] = wanvideovacestarttoendframe.node.id

        vhs_videocombine_3 = VHS_VideoCombine(_id='177', images=setnode_7.out(0))
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_3'] = vhs_videocombine_3.node.id
        wanvideovaceencode_3 = WanVideoVACEEncode(
            _id='209',
            widget_0=480,
            widget_1=832,
            widget_2=29,
            widget_3=1.0000000000000002,
            widget_4=0,
            widget_5=1,
            widget_6=False,
            height=getimagesizeandcount_6.out('HEIGHT'),
            input_frames=getimagesizeandcount_6.out('IMAGE'),
            input_masks=imagepadkj_2.out('MASKS'),
            num_frames=getimagesizeandcount_6.out('COUNT'),
            vae=getnode_15.out(0),
            width=getimagesizeandcount_6.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideovaceencode_3'] = wanvideovaceencode_3.node.id

        previewimage_2 = PreviewImage(
            _id='220',
            images=getimagerangefrombatch.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['previewimage_2'] = previewimage_2.node.id

        wanvideovacestarttoendframe_2 = WanVideoVACEStartToEndFrame(
            _id='231',
            widget_0=33,
            widget_1=0.5,
            control_images=setnode_7.out(0),
            num_frames=vhs_loadvideo.out('FRAME_COUNT'),
            start_image=imageresizekjv2_6.out('IMAGE'),
            _outputs=('IMAGES', 'MASKS'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideovacestarttoendframe_2'] = wanvideovacestarttoendframe_2.node.id

        maskpreview_3 = MaskPreview(
            _id='235',
            mask=getimagerangefrombatch_2.out('MASK'),
        )
        wf.metadata.setdefault('id_map', {})['maskpreview_3'] = maskpreview_3.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='104',
            image=wanvideovacestarttoendframe.out('IMAGES'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        getimagesizeandcount_3 = GetImageSizeAndCount(
            _id='145',
            image=wanvideovacestarttoendframe_2.out('IMAGES'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_3'] = getimagesizeandcount_3.node.id

        wanvideosampler_3 = WanVideoSampler(
            _id='197',
            steps=1,
            cfg=GUIDE_STRENGTH,
            shift=8.000000000000002,
            seed=DEFAULT_SEED,
            start_step='',
            cache_args=wanvideoteacache_3,
            experimental_args=wanvideoexperimentalargs_3,
            image_embeds=wanvideovaceencode_3,
            model=getnode_18.out(0),
            slg_args=wanvideoslg_3,
            text_embeds=wanvideotextencode_3,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler_3'] = wanvideosampler_3.node.id

        previewimage_3 = PreviewImage(
            _id='232',
            images=wanvideovacestarttoendframe_2.out('IMAGES'),
        )
        wf.metadata.setdefault('id_map', {})['previewimage_3'] = previewimage_3.node.id

        maskpreview = MaskPreview(
            _id='233',
            mask=wanvideovacestarttoendframe_2.out('MASKS'),
        )
        wf.metadata.setdefault('id_map', {})['maskpreview'] = maskpreview.node.id

        maskpreview_2 = MaskPreview(
            _id='234',
            mask=wanvideovacestarttoendframe.out('MASKS'),
        )
        wf.metadata.setdefault('id_map', {})['maskpreview_2'] = maskpreview_2.node.id

        wanvideovaceencode = WanVideoVACEEncode(
            _id='56',
            widget_0=480,
            widget_1=832,
            widget_2=29,
            widget_3=1.0000000000000002,
            widget_4=0,
            widget_5=1,
            widget_6=False,
            height=getimagesizeandcount.out('HEIGHT'),
            input_frames=getimagesizeandcount.out('IMAGE'),
            input_masks=wanvideovacestarttoendframe.out('MASKS'),
            num_frames=getimagesizeandcount.out('COUNT'),
            vae=getnode_2.out(0),
            width=getimagesizeandcount.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideovaceencode'] = wanvideovaceencode.node.id

        previewimage = PreviewImage(_id='113', images=getimagesizeandcount.out('IMAGE'))
        wf.metadata.setdefault('id_map', {})['previewimage'] = previewimage.node.id
        wanvideovaceencode_2 = WanVideoVACEEncode(
            _id='148',
            widget_0=480,
            widget_1=832,
            widget_2=29,
            widget_3=1.0000000000000002,
            widget_4=0,
            widget_5=1,
            widget_6=False,
            height=getimagesizeandcount_3.out('HEIGHT'),
            input_frames=getimagesizeandcount_3.out('IMAGE'),
            input_masks=wanvideovacestarttoendframe_2.out('MASKS'),
            num_frames=getimagesizeandcount_3.out('COUNT'),
            vae=getnode_8.out(0),
            width=getimagesizeandcount_3.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideovaceencode_2'] = wanvideovaceencode_2.node.id

        wanvideodecode_3 = WanVideoDecode(
            _id='196',
            samples=wanvideosampler_3.out('SAMPLES'),
            vae=getnode_19.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode_3'] = wanvideodecode_3.node.id

        wanvideosampler = WanVideoSampler(
            _id='70',
            steps=1,
            cfg=GUIDE_STRENGTH,
            shift=8.000000000000002,
            seed=DEFAULT_SEED,
            start_step='',
            cache_args=wanvideoteacache,
            experimental_args=wanvideoexperimentalargs,
            image_embeds=wanvideovaceencode,
            model=getnode_5.out(0),
            slg_args=wanvideoslg,
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideosampler_2 = WanVideoSampler(
            _id='172',
            steps=1,
            cfg=GUIDE_STRENGTH,
            shift=8.000000000000002,
            start_step='',
            cache_args=wanvideoteacache_2,
            experimental_args=wanvideoexperimentalargs_2,
            image_embeds=wanvideovaceencode_2,
            model=getnode_11.out(0),
            slg_args=wanvideoslg_2,
            text_embeds=wanvideotextencode_2,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler_2'] = wanvideosampler_2.node.id

        getimagesizeandcount_5 = GetImageSizeAndCount(
            _id='193',
            image=wanvideodecode_3,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_5'] = getimagesizeandcount_5.node.id

        wanvideodecode = WanVideoDecode(
            _id='138',
            samples=wanvideosampler.out('SAMPLES'),
            vae=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        wanvideodecode_2 = WanVideoDecode(
            _id='167',
            samples=wanvideosampler_2.out('SAMPLES'),
            vae=getnode_14.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode_2'] = wanvideodecode_2.node.id

        emptyimage_3 = EmptyImage(
            _id='191',
            widget_0=8,
            widget_1=512,
            widget_2=1,
            widget_3=0,
            height=getimagesizeandcount_5.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['emptyimage_3'] = emptyimage_3.node.id

        getimagesizeandcount_2 = GetImageSizeAndCount(
            _id='137',
            image=wanvideodecode,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_2'] = getimagesizeandcount_2.node.id

        getimagesizeandcount_4 = GetImageSizeAndCount(
            _id='159',
            image=wanvideodecode_2,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_4'] = getimagesizeandcount_4.node.id

        imageconcatmulti_5 = ImageConcatMulti(
            _id='192',
            inputcount=3,
            direction=DIRECTION_2,
            match_image_size=True,
            unused_3=None,
            image_1=getimagesizeandcount_5.out('IMAGE'),
            image_2=emptyimage_3,
            image_3=addlabel_5,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti_5'] = imageconcatmulti_5.node.id

        emptyimage = EmptyImage(
            _id='132',
            widget_0=8,
            widget_1=512,
            widget_2=1,
            widget_3=0,
            height=getimagesizeandcount_2.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['emptyimage'] = emptyimage.node.id

        emptyimage_2 = EmptyImage(
            _id='155',
            widget_0=8,
            widget_1=512,
            widget_2=1,
            widget_3=0,
            height=getimagesizeandcount_4.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['emptyimage_2'] = emptyimage_2.node.id

        vhs_videocombine_4 = VHS_VideoCombine(_id='213', images=imageconcatmulti_5)
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_4'] = vhs_videocombine_4.node.id
        imageconcatmulti = ImageConcatMulti(
            _id='135',
            inputcount=3,
            direction=DIRECTION_2,
            match_image_size=True,
            unused_3=None,
            image_1=getimagesizeandcount_2.out('IMAGE'),
            image_2=emptyimage,
            image_3=imageconcatmulti_2,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti'] = imageconcatmulti.node.id

        imageconcatmulti_3 = ImageConcatMulti(
            _id='158',
            inputcount=3,
            direction=DIRECTION_2,
            match_image_size=True,
            unused_3=None,
            image_1=getimagesizeandcount_4.out('IMAGE'),
            image_2=emptyimage_2,
            image_3=imageconcatmulti_4,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti_3'] = imageconcatmulti_3.node.id

        vhs_videocombine = VHS_VideoCombine(_id='139', images=imageconcatmulti)
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id
        vhs_videocombine_2 = VHS_VideoCombine(_id='165', images=imageconcatmulti_3)
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_2'] = vhs_videocombine_2.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=previewimage, output_type='PreviewImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one')

