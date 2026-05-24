# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPVisionLoader, GetImageRangeFromBatch, LoadAudio, PreviewAny
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import DownloadAndLoadWav2VecModel, MultiTalkModelLoader, MultiTalkWav2VecEmbeds, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoEncode, WanVideoImageToVideoMultiTalk, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader, Wav2VecModelLoader

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


DEFAULT_NEGATIVE = 'bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards'
DEFAULT_SEED = 2
GUIDE_STRENGTH = 1.0000000000000002
MODEL_NAME = 'WanVideo\\InfiniteTalk\\InfiniteTalk\\Wan2_1-InfiniteTalk_Single_Q8.gguf'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME_4 = 'clip_vision_h.safetensors'
MODEL_NAME_5 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_6 = 'MelBandRoFormer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_7 = 'wav2vec2-chinese-base_fp16.safetensors'
MODEL_NAME_8 = 'WanVideo\\wan2.1-i2v-14b-480p-Q8_0.gguf'
WIDGET_0 = 'VAE'
WIDGET_0_2 = 'height'
WIDGET_0_3 = 'width'
WIDGET_0_4 = 'input_audio'
WIDGET_0_5 = 'wanmodel'
WIDGET_0_6 = 'clip_vision_model'
WIDGET_0_7 = 'max_frames'
WIDGET_1 = 'fp16'
WIDGET_2 = 'main_device'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('wanvideovaeloader'), field='model_name', default=MODEL_NAME_2),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
}

READY_METADATA = ReadyMetadata.build(
    capability='video_to_video_talking_avatar',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='InfiniteTalk video-to-video talking avatar',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        multitalkmodelloader = MultiTalkModelLoader(_id='120', widget_0=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['multitalkmodelloader'] = multitalkmodelloader.node.id
        loadaudio = LoadAudio(
            _id='125',
            audio='one-does-not-simply-walk-into-mordor-its-black-gates-are-guarded-by-more-than-just-orcs.mp3',
            widget_1=None,
            widget_2=None,
        )
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id

        wanvideovaeloader = WanVideoVAELoader(_id='129', model_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(
            _id='134',
            use_non_blocking=True,
            prefetch_blocks=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        downloadandloadwav2vecmodel = DownloadAndLoadWav2VecModel(
            _id='137',
            widget_0='TencentGameMate/chinese-wav2vec2-base',
            widget_1=WIDGET_1,
            widget_2=WIDGET_2,
        )
        wf.metadata.setdefault('id_map', {})['downloadandloadwav2vecmodel'] = downloadandloadwav2vecmodel.node.id

        wanvideoloraselect = WanVideoLoraSelect(
            _id='138',
            lora=MODEL_NAME_3,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselect'] = wanvideoloraselect.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='177')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        # Loaders
        clipvisionloader = CLIPVisionLoader(_id='238', clip_name=MODEL_NAME_4)
        wf.metadata.setdefault('id_map', {})['clipvisionloader'] = clipvisionloader.node.id
        wanvideotextencodecached = WanVideoTextEncodeCached(
            _id='241',
            model_name=MODEL_NAME_5,
            positive_prompt='a woman is singing a lullaby',
            negative_prompt=DEFAULT_NEGATIVE,
            use_disk_cache=False,
            _outputs=('TEXT_EMBEDS', 'NEGATIVE_TEXT_EMBEDS', 'POSITIVE_PROMPT'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencodecached'] = wanvideotextencodecached.node.id

        getnode = raw_call(wf, 'GetNode', '242', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '243', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '244', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        intconstant = INTConstant(_id='245', value=640)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='246', value=640)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        getnode_4 = raw_call(wf, 'GetNode', '249', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '250', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '254', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '261', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '265', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        intconstant_3 = INTConstant(_id='270', value=1000)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        getnode_9 = raw_call(wf, 'GetNode', '272', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        melbandroformermodelloader = raw_call(wf, 'MelBandRoFormerModelLoader', '303',
            widget_0=MODEL_NAME_6,
        )
        wf.metadata.setdefault('id_map', {})['melbandroformermodelloader'] = melbandroformermodelloader.node.id

        wav2vecmodelloader = Wav2VecModelLoader(
            _id='306',
            widget_0=MODEL_NAME_7,
            widget_1=WIDGET_1,
            widget_2=WIDGET_2,
        )
        wf.metadata.setdefault('id_map', {})['wav2vecmodelloader'] = wav2vecmodelloader.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='122',
            model=MODEL_NAME_8,
            base_precision='fp16',
            block_swap_args=wanvideoblockswap,
            lora=wanvideoloraselect,
            multitalk_model=multitalkmodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        vhs_loadvideo = VHS_LoadVideo(
            _id='228',
            video='wolf_interpolated.mp4',
            custom_height=getnode_4.out(0),
            custom_width=getnode_5.out(0),
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

        setnode = raw_call(wf, 'SetNode', '240',
            widget_0=WIDGET_0,
            WANVAE=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        setnode_2 = raw_call(wf, 'SetNode', '247', widget_0=WIDGET_0_3, INT=intconstant)
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id
        setnode_3 = raw_call(wf, 'SetNode', '248',
            widget_0=WIDGET_0_2,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

        setnode_4 = raw_call(wf, 'SetNode', '253', widget_0=WIDGET_0_4, AUDIO=loadaudio)
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id
        setnode_6 = raw_call(wf, 'SetNode', '264',
            widget_0=WIDGET_0_6,
            CLIP_VISION=clipvisionloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        setnode_7 = raw_call(wf, 'SetNode', '271',
            widget_0=WIDGET_0_7,
            INT=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='230',
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=16,
            device='cpu',
            width=getnode_5.out(0),
            height=getnode_4.out(0),
            image=vhs_loadvideo.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        setnode_5 = raw_call(wf, 'SetNode', '260',
            widget_0=WIDGET_0_5,
            WANVIDEOMODEL=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '304',
            audio=setnode_4.out(0),
            model=melbandroformermodelloader.out(0),
        )
        wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

        multitalkwav2vecembeds = MultiTalkWav2VecEmbeds(
            _id='194',
            widget_0=True,
            widget_1=400,
            widget_2=25,
            widget_3=1.5,
            widget_4=1,
            widget_5='para',
            audio_1=melbandroformersampler.out(0),
            num_frames=getnode_9.out(0),
            wav2vec_model=downloadandloadwav2vecmodel,
            _outputs=('MULTITALK_EMBEDS', 'AUDIO', 'NUM_FRAMES'),
        )
        wf.metadata.setdefault('id_map', {})['multitalkwav2vecembeds'] = multitalkwav2vecembeds.node.id

        wanvideoencode = WanVideoEncode(
            _id='229',
            widget_0=False,
            widget_1=272,
            widget_2=272,
            widget_3=144,
            widget_4=128,
            widget_5=0,
            widget_6=1,
            image=imageresizekjv2.out('IMAGE'),
            vae=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoencode'] = wanvideoencode.node.id

        getimagerangefrombatch = GetImageRangeFromBatch(
            _id='231',
            widget_0=0,
            widget_1=1,
            images=imageresizekjv2.out('IMAGE'),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch'] = getimagerangefrombatch.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='291',
            image=getimagerangefrombatch.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        setnode_8 = raw_call(wf, 'SetNode', '294',
            widget_0='actual_audio_frames',
            INT=multitalkwav2vecembeds.out('NUM_FRAMES'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        wanvideoclipvisionencode = WanVideoClipVisionEncode(
            _id='237',
            clip_vision=getnode_8.out(0),
            image_1=getimagesizeandcount.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoclipvisionencode'] = wanvideoclipvisionencode.node.id

        previewany = PreviewAny(_id='293', source=setnode_8.out(0))
        wf.metadata.setdefault('id_map', {})['previewany'] = previewany.node.id
        wanvideoimagetovideomultitalk = WanVideoImageToVideoMultiTalk(
            _id='192',
            widget_0=832,
            widget_1=480,
            widget_2=81,
            widget_3=9,
            widget_4=False,
            widget_5='disabled',
            widget_6=False,
            widget_7='infinitetalk',
            clip_embeds=wanvideoclipvisionencode,
            height=getimagesizeandcount.out('HEIGHT'),
            start_image=getimagesizeandcount.out('IMAGE'),
            vae=getnode_3.out(0),
            width=getimagesizeandcount.out('WIDTH'),
            _outputs=('IMAGE_EMBEDS', 'OUTPUT_PATH'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoimagetovideomultitalk'] = wanvideoimagetovideomultitalk.node.id

        wanvideosampler = WanVideoSampler(
            _id='128',
            steps=1,
            cfg=GUIDE_STRENGTH,
            shift=11.000000000000002,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            start_step=2,
            add_noise_to_samples=True,
            image_embeds=wanvideoimagetovideomultitalk.out('IMAGE_EMBEDS'),
            model=getnode_7.out(0),
            multitalk_embeds=multitalkwav2vecembeds.out('MULTITALK_EMBEDS'),
            samples=wanvideoencode,
            text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideodecode = WanVideoDecode(
            _id='130',
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        getimagesizeandcount_2 = GetImageSizeAndCount(
            _id='300',
            image=wanvideodecode,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_2'] = getimagesizeandcount_2.node.id

        getimagerangefrombatch_2 = GetImageRangeFromBatch(
            _id='301',
            widget_0=0,
            widget_1=1,
            images=getimagesizeandcount_2.out('IMAGE'),
            num_frames=getimagesizeandcount_2.out('COUNT'),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_2'] = getimagerangefrombatch_2.node.id

        imageconcatmulti = ImageConcatMulti(
            _id='299',
            direction='left',
            unused_3=None,
            image_1=getimagerangefrombatch_2.out('IMAGE'),
            image_2=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti'] = imageconcatmulti.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='131',
            audio=getnode_6.out(0),
            images=imageconcatmulti,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

