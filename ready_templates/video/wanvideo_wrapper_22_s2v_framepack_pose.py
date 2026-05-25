# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioEncoderEncode, AudioEncoderLoader, GetImageRangeFromBatch, LoadAudio, LoadImage, PreviewAny
from vibecomfy.nodes.kjnodes import ColorMatch, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2, LazySwitchKJ
from vibecomfy.nodes.videohelpersuite import VHS_LoadAudio, VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness, WanVideoAddS2VEmbeds, WanVideoBlockSwap, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader

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
DEFAULT_PROMPT = '3D animated scene of a young woman singing melancholically'
DEFAULT_SEED = 45
DEVICE = 'cpu'
GUIDE_STRENGTH = 1
KEEP_PROPORTION = 'crop'
MODEL_NAME = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'
MODEL_NAME_3 = 'wav2vec_xlsr_53_english_fp32.safetensors'
MODEL_NAME_4 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_5 = 'MelBandRoFormer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_6 = 'WanVideo\\S2V\\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_7 = 'yolox_l.torchscript.pt'
MODEL_NAME_8 = 'dw-ll_ucoco_384_bs5.torchscript.pt'
UPSCALE_METHOD = 'bilinear'
VIDEO = 'wolf_interpolated.mp4'
WIDGET_0 = 'VAE'
WIDGET_0_2 = 'reference_image'
WIDGET_0_3 = 'width'
WIDGET_0_4 = 'height'


MODELS = {}

PUBLIC_INPUTS = {
'height': InputSpec(node=ref('imageresizekjv2_3'), field='height', default=256),
'image': InputSpec(node=ref('loadimage'), field='image', default='2b.jpg', aliases=('input_image',)),
'model': InputSpec(node=ref('wanvideovaeloader'), field='model_name', default=MODEL_NAME),
'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
'width': InputSpec(node=ref('imageresizekjv2_3'), field='width', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='speech_to_video_pose_control',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'comfyui_controlnet_aux', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='S2V framepack pose workflow',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
    wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
    wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME)
    wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
    wanvideoblockswap = WanVideoBlockSwap(
        _id='39',
        blocks_to_swap=32,
        use_non_blocking=True,
        prefetch_blocks=1,
    )
    wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        _id='60',
        lora_0=MODEL_NAME_2,
        strength_0=1.2,
        merge_loras=False,
    )
    wf.metadata.setdefault('id_map', {})['wanvideoloraselectmulti'] = wanvideoloraselectmulti.node.id

    audioencoderloader = AudioEncoderLoader(_id='65', widget_0=MODEL_NAME_3)
    wf.metadata.setdefault('id_map', {})['audioencoderloader'] = audioencoderloader.node.id
    loadaudio = LoadAudio(
        _id='66',
        audio='0321. Alphaville - Big In Japan.mp3',
        widget_1=None,
        widget_2=None,
    )
    wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id

    wanvideotextencodecached = WanVideoTextEncodeCached(
        _id='67',
        model_name=MODEL_NAME_4,
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        _outputs=('TEXT_EMBEDS', 'NEGATIVE_TEXT_EMBEDS', 'POSITIVE_PROMPT'),
    )
    wf.metadata.setdefault('id_map', {})['wanvideotextencodecached'] = wanvideotextencodecached.node.id

    primitivenode = raw_call(wf, 'PrimitiveNode', '71',
        widget_0=501,
        widget_1='fixed',
    )
    wf.metadata.setdefault('id_map', {})['primitivenode'] = primitivenode.node.id

    # Inputs
    loadimage = LoadImage(_id='73', image='2b.jpg', _outputs=('IMAGE', 'MASK'))
    wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id
    melbandroformermodelloader = raw_call(wf, 'MelBandRoFormerModelLoader', '81',
        widget_0=MODEL_NAME_5,
    )
    wf.metadata.setdefault('id_map', {})['melbandroformermodelloader'] = melbandroformermodelloader.node.id

    vhs_loadaudio = VHS_LoadAudio(_id='94', _outputs=('AUDIO', 'DURATION'))
    wf.metadata.setdefault('id_map', {})['vhs_loadaudio'] = vhs_loadaudio.node.id
    getnode = raw_call(wf, 'GetNode', '120', widget_0=WIDGET_0)
    wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
    getnode_2 = raw_call(wf, 'GetNode', '121', widget_0=WIDGET_0)
    wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
    getnode_3 = raw_call(wf, 'GetNode', '122', widget_0=WIDGET_0)
    wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
    getnode_4 = raw_call(wf, 'GetNode', '126', widget_0=WIDGET_0_2)
    wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
    reroute = raw_call(wf, 'Reroute', '129')
    wf.metadata.setdefault('id_map', {})['reroute'] = reroute.node.id
    reroute_2 = raw_call(wf, 'Reroute', '130')
    wf.metadata.setdefault('id_map', {})['reroute_2'] = reroute_2.node.id
    intconstant = INTConstant(_id='131', value=640)
    wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
    intconstant_2 = INTConstant(_id='132', value=640)
    wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
    getnode_5 = raw_call(wf, 'GetNode', '137', widget_0=WIDGET_0_3)
    wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
    getnode_6 = raw_call(wf, 'GetNode', '138', widget_0=WIDGET_0_4)
    wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
    getnode_7 = raw_call(wf, 'GetNode', '139', widget_0=WIDGET_0_3)
    wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
    getnode_8 = raw_call(wf, 'GetNode', '140', widget_0=WIDGET_0_4)
    wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
    getnode_9 = raw_call(wf, 'GetNode', '141', widget_0=WIDGET_0_3)
    wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
    getnode_10 = raw_call(wf, 'GetNode', '142', widget_0=WIDGET_0_4)
    wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
    wanvideomodelloader = WanVideoModelLoader(
        _id='22',
        model=MODEL_NAME_6,
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        compile_args=wanvideotorchcompilesettings,
    )
    wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

    imageresizekjv2 = ImageResizeKJv2(
        _id='74',
        upscale_method='lanczos',
        keep_proportion=KEEP_PROPORTION,
        divisible_by=16,
        device=DEVICE,
        width=getnode_5.out(0),
        height=getnode_6.out(0),
        image=loadimage.out('IMAGE'),
        _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

    vhs_loadvideo = VHS_LoadVideo(
        _id='106',
        video=VIDEO,
        custom_height=getnode_10.out(0),
        custom_width=getnode_9.out(0),
        frame_load_cap=primitivenode.out(0),
        _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
    )
    wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

    vhs_loadvideo_2 = VHS_LoadVideo(
        _id='116',
        video=VIDEO,
        custom_height=getnode_8.out(0),
        custom_width=getnode_7.out(0),
        frame_load_cap=primitivenode.out(0),
        _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
    )
    wf.metadata.setdefault('id_map', {})['vhs_loadvideo_2'] = vhs_loadvideo_2.node.id

    setnode = raw_call(wf, 'SetNode', '119',
        widget_0=WIDGET_0,
        WANVAE=wanvideovaeloader,
    )
    wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

    setnode_3 = raw_call(wf, 'SetNode', '133', widget_0=WIDGET_0_3, INT=intconstant)
    wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id
    setnode_4 = raw_call(wf, 'SetNode', '134',
        widget_0=WIDGET_0_4,
        INT=intconstant_2,
    )
    wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        _id='37',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        height=imageresizekjv2.out('HEIGHT'),
        num_frames=primitivenode.out(0),
        width=imageresizekjv2.out('WIDTH'),
    )
    wf.metadata.setdefault('id_map', {})['wanvideoemptyembeds'] = wanvideoemptyembeds.node.id

    wanvideosetloras = WanVideoSetLoRAs(
        _id='58',
        lora=wanvideoloraselectmulti,
        model=wanvideomodelloader,
    )
    wf.metadata.setdefault('id_map', {})['wanvideosetloras'] = wanvideosetloras.node.id

    melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '82',
        audio=vhs_loadvideo.out('AUDIO'),
        model=melbandroformermodelloader.out(0),
    )
    wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

    imageresizekjv2_2 = ImageResizeKJv2(
        _id='110',
        upscale_method=UPSCALE_METHOD,
        keep_proportion=KEEP_PROPORTION,
        divisible_by=16,
        device=DEVICE,
        width=getnode_7.out(0),
        height=getnode_8.out(0),
        image=vhs_loadvideo_2.out('IMAGE'),
        _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['imageresizekjv2_2'] = imageresizekjv2_2.node.id

    setnode_2 = raw_call(wf, 'SetNode', '125',
        widget_0=WIDGET_0_2,
        IMAGE=imageresizekjv2.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

    wanvideosetblockswap = WanVideoSetBlockSwap(
        _id='56',
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )
    wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

    wanvideoencode = WanVideoEncode(
        _id='72',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=setnode_2.out(0),
        vae=getnode_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['wanvideoencode'] = wanvideoencode.node.id

    normalizeaudioloudness = NormalizeAudioLoudness(
        _id='98',
        widget_0=-23,
        audio=melbandroformersampler.out(0),
    )
    wf.metadata.setdefault('id_map', {})['normalizeaudioloudness'] = normalizeaudioloudness.node.id

    dwpreprocessor = raw_call(wf, 'DWPreprocessor', '107',
        detect_hand='disable',
        detect_body='disable',
        detect_face='enable',
        resolution=640,
        bbox_detector=MODEL_NAME_7,
        pose_estimator=MODEL_NAME_8,
        image=imageresizekjv2_2.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['dwpreprocessor'] = dwpreprocessor.node.id

    audioencoderencode = AudioEncoderEncode(
        _id='64',
        audio=normalizeaudioloudness,
        audio_encoder=audioencoderloader,
    )
    wf.metadata.setdefault('id_map', {})['audioencoderencode'] = audioencoderencode.node.id

    imageresizekjv2_3 = ImageResizeKJv2(
        _id='111',
        width=256,
        height=256,
        upscale_method=UPSCALE_METHOD,
        keep_proportion='stretch',
        divisible_by=16,
        device='gpu',
        image=dwpreprocessor,
        _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['imageresizekjv2_3'] = imageresizekjv2_3.node.id

    wanvideoencode_2 = WanVideoEncode(
        _id='109',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=0.5,
        image=imageresizekjv2_3.out('IMAGE'),
        vae=getnode_3.out(0),
    )
    wf.metadata.setdefault('id_map', {})['wanvideoencode_2'] = wanvideoencode_2.node.id

    wanvideoadds2vembeds = WanVideoAddS2VEmbeds(
        _id='117',
        widget_0=80,
        widget_1=1,
        widget_2=0,
        widget_3=1,
        widget_4=True,
        audio_encoder_output=audioencoderencode,
        embeds=wanvideoemptyembeds,
        pose_latent=wanvideoencode_2,
        ref_latent=wanvideoencode,
        vae=getnode_2.out(0),
        _outputs=('IMAGE_EMBEDS', 'AUDIO_FRAME_COUNT'),
    )
    wf.metadata.setdefault('id_map', {})['wanvideoadds2vembeds'] = wanvideoadds2vembeds.node.id

    wanvideosampler = WanVideoSampler(
        _id='27',
        steps=1,
        cfg=GUIDE_STRENGTH,
        shift=4,
        seed=DEFAULT_SEED,
        scheduler='lcm',
        image_embeds=wanvideoadds2vembeds.out('IMAGE_EMBEDS'),
        model=wanvideosetblockswap,
        text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
        _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
    )
    wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

    previewany = PreviewAny(
        _id='118',
        source=wanvideoadds2vembeds.out('AUDIO_FRAME_COUNT'),
    )
    wf.metadata.setdefault('id_map', {})['previewany'] = previewany.node.id

    wanvideodecode = WanVideoDecode(
        _id='28',
        normalization='default',
        samples=wanvideosampler.out('SAMPLES'),
        vae=getnode.out(0),
    )
    wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

    getimagesizeandcount = GetImageSizeAndCount(
        _id='70',
        image=wanvideodecode,
        _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
    )
    wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

    getimagerangefrombatch = GetImageRangeFromBatch(
        _id='143',
        widget_0=0,
        widget_1=501,
        images=getimagesizeandcount.out('IMAGE'),
        num_frames=primitivenode.out(0),
        _outputs=('IMAGE', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['getimagerangefrombatch'] = getimagerangefrombatch.node.id

    colormatch = ColorMatch(
        _id='105',
        widget_0='mkl',
        widget_1=1,
        widget_2=True,
        image_ref=getnode_4.out(0),
        image_target=getimagerangefrombatch.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['colormatch'] = colormatch.node.id

    imageconcatmulti = ImageConcatMulti(
        _id='112',
        unused_3=None,
        image_1=reroute_2.out(0),
        image_2=colormatch,
    )
    wf.metadata.setdefault('id_map', {})['imageconcatmulti'] = imageconcatmulti.node.id

    lazyswitchkj = LazySwitchKJ(
        _id='127',
        widget_0=True,
        on_false=colormatch,
        on_true=imageconcatmulti,
    )
    wf.metadata.setdefault('id_map', {})['lazyswitchkj'] = lazyswitchkj.node.id

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='97',
        audio=reroute.out(0),
        images=lazyswitchkj,
    )
    wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

