# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioEncoderEncode, AudioEncoderLoader, LoadAudio, LoadImage, PreviewAny
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, ImageResizeKJv2, InsertLatentToIndexed
from vibecomfy.nodes.videohelpersuite import VHS_LoadAudio, VHS_SelectEveryNthImage, VHS_SplitImages, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness, WanVideoAddS2VEmbeds, WanVideoBlockSwap, WanVideoContextOptions, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader

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
DEFAULT_PROMPT = 'a woman is singing passionately'
DEFAULT_SEED = 45
GUIDE_STRENGTH = 1
MODEL_NAME = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'
MODEL_NAME_3 = 'wav2vec_xlsr_53_english_fp32.safetensors'
MODEL_NAME_4 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_5 = 'MelBandRoFormer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_6 = 'gimmvfi_r_arb_lpips_fp32.safetensors'
MODEL_NAME_7 = 'WanVideo\\S2V\\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('wanvideovaeloader'), field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='2b.jpg'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='2b.jpg'),
    'width': InputSpec(node=ref('imageresizekjv2'), field='width', default=256),
    'height': InputSpec(node=ref('imageresizekjv2'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='speech_to_video_context_window',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='S2V context-window workflow',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(
            _id='39',
            blocks_to_swap=25,
            use_non_blocking=True,
            prefetch_blocks=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            _id='60',
            lora_0=MODEL_NAME_2,
            strength_0=1.5,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselectmulti'] = wanvideoloraselectmulti.node.id

        audioencoderloader = AudioEncoderLoader(_id='65', widget_0=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['audioencoderloader'] = audioencoderloader.node.id
        loadaudio = LoadAudio(
            _id='66',
            audio='NieR_ Automata - _Weight of the World_ ENG VER. by Lizz Robinett [CyOSTbel3AM].mp3',
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
            widget_0=201,
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

        wanvideocontextoptions = WanVideoContextOptions(
            _id='83',
            context_schedule='uniform_standard',
        )
        wf.metadata.setdefault('id_map', {})['wanvideocontextoptions'] = wanvideocontextoptions.node.id

        vhs_loadaudio = VHS_LoadAudio(_id='94', _outputs=('AUDIO', 'DURATION'))
        wf.metadata.setdefault('id_map', {})['vhs_loadaudio'] = vhs_loadaudio.node.id
        downloadandloadgimmvfimodel = raw_call(wf, 'DownloadAndLoadGIMMVFIModel', '95',
            widget_0=MODEL_NAME_6,
            widget_1='fp16',
            widget_2=False,
        )
        wf.metadata.setdefault('id_map', {})['downloadandloadgimmvfimodel'] = downloadandloadgimmvfimodel.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_7,
            base_precision='fp16',
            quantization='fp8_e4m3fn_scaled',
            compile_args=wanvideotorchcompilesettings,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='74',
            width=256,
            height=256,
            upscale_method='lanczos',
            keep_proportion='crop',
            device='cpu',
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '82',
            audio=vhs_loadaudio.out('AUDIO'),
            model=melbandroformermodelloader.out(0),
        )
        wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

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

        previewany = PreviewAny(_id='62', source=wanvideomodelloader)
        wf.metadata.setdefault('id_map', {})['previewany'] = previewany.node.id
        wanvideoencode = WanVideoEncode(
            _id='72',
            widget_0=False,
            widget_1=272,
            widget_2=272,
            widget_3=144,
            widget_4=128,
            widget_5=0,
            widget_6=1,
            image=imageresizekjv2.out('IMAGE'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoencode'] = wanvideoencode.node.id

        normalizeaudioloudness = NormalizeAudioLoudness(
            _id='98',
            widget_0=-23,
            audio=melbandroformersampler.out(0),
        )
        wf.metadata.setdefault('id_map', {})['normalizeaudioloudness'] = normalizeaudioloudness.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='56',
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        audioencoderencode = AudioEncoderEncode(
            _id='64',
            audio=normalizeaudioloudness,
            audio_encoder=audioencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['audioencoderencode'] = audioencoderencode.node.id

        wanvideoadds2vembeds = WanVideoAddS2VEmbeds(
            _id='101',
            widget_0=201,
            widget_1=1,
            widget_2=0,
            widget_3=1,
            widget_4=False,
            audio_encoder_output=audioencoderencode,
            embeds=wanvideoemptyembeds,
            frame_window_size=primitivenode.out(0),
            ref_latent=wanvideoencode,
            _outputs=('IMAGE_EMBEDS', 'AUDIO_FRAME_COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoadds2vembeds'] = wanvideoadds2vembeds.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=1,
            cfg=GUIDE_STRENGTH,
            shift=4,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            context_options=wanvideocontextoptions,
            image_embeds=wanvideoadds2vembeds.out('IMAGE_EMBEDS'),
            model=wanvideosetblockswap,
            text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        previewany_2 = PreviewAny(
            _id='69',
            source=wanvideoadds2vembeds.out('AUDIO_FRAME_COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['previewany_2'] = previewany_2.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        insertlatenttoindexed = InsertLatentToIndexed(
            _id='77',
            widget_0=0,
            destination=wanvideosampler.out('SAMPLES'),
            source=wanvideoencode,
        )
        wf.metadata.setdefault('id_map', {})['insertlatenttoindexed'] = insertlatenttoindexed.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='70',
            image=wanvideodecode,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        vhs_splitimages = VHS_SplitImages(
            _id='80',
            images=getimagesizeandcount.out('IMAGE'),
            _outputs=('IMAGE_A', 'A_COUNT', 'IMAGE_B', 'B_COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_splitimages'] = vhs_splitimages.node.id

        gimmvfi_interpolate = raw_call(wf, 'GIMMVFI_interpolate', '96',
            widget_0=1,
            widget_1=3,
            widget_2=0,
            widget_3='fixed',
            widget_4=False,
            gimmvfi_model=downloadandloadgimmvfimodel.out(0),
            images=vhs_splitimages.out('IMAGE_B'),
        )
        wf.metadata.setdefault('id_map', {})['gimmvfi_interpolate'] = gimmvfi_interpolate.node.id

        # Outputs
        vhs_videocombine_2 = VHS_VideoCombine(
            _id='97',
            audio=vhs_loadaudio.out('AUDIO'),
            images=vhs_splitimages.out('IMAGE_B'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_2'] = vhs_videocombine_2.node.id

        vhs_selecteverynthimage = VHS_SelectEveryNthImage(
            _id='102',
            images=gimmvfi_interpolate.out(0),
            _outputs=('IMAGE', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_selecteverynthimage'] = vhs_selecteverynthimage.node.id

        vhs_videocombine = VHS_VideoCombine(
            _id='30',
            audio=vhs_loadaudio.out('AUDIO'),
            images=vhs_selecteverynthimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

