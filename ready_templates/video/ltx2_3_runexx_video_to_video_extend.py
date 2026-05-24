# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioConcat, BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, GetImageRangeFromBatch, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, TrimAudioDuration, UNETLoader, VAEDecode, VAEDecodeTiled, VAEEncode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageBatchExtendWithOverlap, ImageBatchMulti, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVAudioVideoMask, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.ltxvideo import LTXVAddLatentGuide
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine, VHS_VideoInfo
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness

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


AUDIO = 'speech_smoke.wav'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_PROMPT_2 = ' distorted sound, saturated sound, loud sound'
DEFAULT_SEED = 42
DEFAULT_SEED_2 = 432
EXPRESSION = '((round((a * b -1) / 8)) * 8) + 1 '
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
MODEL_NAME = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_10 = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME_2 = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_3 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_4 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_6 = 'taeltx2_3.safetensors'
MODEL_NAME_7 = 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_8 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
MODEL_NAME_9 = 'gemma-3-12b-it-Q2_K.gguf'
WIDGET_0 = 'clip'
WIDGET_0_10 = 'ref_audio'
WIDGET_0_11 = 'overlap_seconds'
WIDGET_0_12 = 'vae_tiny'
WIDGET_0_13 = 'ref_image_overlap'
WIDGET_0_14 = 'max_size'
WIDGET_0_15 = 'ref_image'
WIDGET_0_16 = 'positive'
WIDGET_0_17 = 'negative'
WIDGET_0_18 = 'final_audio'
WIDGET_0_19 = 'final_video_blend'
WIDGET_0_2 = 'vae_audio'
WIDGET_0_20 = 'enable_promptenhance'
WIDGET_0_21 = 'final_video_cut'
WIDGET_0_3 = 'vae'
WIDGET_0_4 = 'fps'
WIDGET_0_5 = 'upscale_model'
WIDGET_0_6 = 'ref_frames'
WIDGET_0_7 = 'ext_seconds'
WIDGET_0_8 = 'ref_video'
WIDGET_0_9 = 'model'


MODELS = {}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node=ref('latentupscalemodelloader'), field='model_name', default=MODEL_NAME_2),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'steps': InputSpec(node=ref('basicscheduler'), field='steps', default=8),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=True),
}

READY_METADATA = ReadyMetadata.build(
    capability='video_to_video_extend',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX23_audio_vae_bf16.safetensors', 'LTX23_video_vae_bf16.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler', 'euler_ancestral', 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'taeltx2_3.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='video-to-video extension',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        randomnoise = RandomNoise(
            _id='115',
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(_id='127', temporal_size=4096)
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id
        # Sampling
        ksamplerselect = KSamplerSelect(_id='137', sampler_name='euler_ancestral')
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
        intconstant = INTConstant(_id='211', value=10)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '214', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        getnode = raw_call(wf, 'GetNode', '215', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '216', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '217', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        getnode_4 = raw_call(wf, 'GetNode', '219', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '220', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '221', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '222', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '223', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '242', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        randomnoise_2 = RandomNoise(
            _id='243',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        getnode_10 = raw_call(wf, 'GetNode', '244', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        # Sampling
        ksamplerselect_2 = KSamplerSelect(_id='254', sampler_name='euler')
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id
        intconstant_2 = INTConstant(_id='305', value=3)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        getnode_11 = raw_call(wf, 'GetNode', '326', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '356', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '363', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '369', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        getnode_15 = raw_call(wf, 'GetNode', '380', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        getnode_16 = raw_call(wf, 'GetNode', '392', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        getnode_17 = raw_call(wf, 'GetNode', '398', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '408', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '439', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        getnode_20 = raw_call(wf, 'GetNode', '442', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        # Loaders
        vaeloader = VAELoader(_id='463', vae_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        latentupscalemodelloader = LatentUpscaleModelLoader(
            _id='465',
            model_name=MODEL_NAME_2,
        )
        wf.metadata.setdefault('id_map', {})['latentupscalemodelloader'] = latentupscalemodelloader.node.id

        dualcliploader = DualCLIPLoader(
            _id='466',
            clip_name1=MODEL_NAME_3,
            clip_name2=MODEL_NAME_4,
            type_='ltxv',
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='471', ckpt_name=MODEL_NAME_5)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        vaeloader_2 = VAELoader(_id='473', vae_name=MODEL_NAME_6)
        wf.metadata.setdefault('id_map', {})['vaeloader_2'] = vaeloader_2.node.id
        unetloader = UNETLoader(_id='474', unet_name=MODEL_NAME_7)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        unetloadergguf = UnetLoaderGGUF(_id='475', unet_name=MODEL_NAME_8)
        wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
        dualcliploadergguf = DualCLIPLoaderGGUF(
            _id='477',
            clip_name1=MODEL_NAME_9,
            clip_name2=MODEL_NAME_4,
            type_='sdxl',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploadergguf'] = dualcliploadergguf.node.id

        manualsigmas = ManualSigmas(_id='479', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id
        manualsigmas_2 = ManualSigmas(
            _id='480',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id

        primitivestringmultiline = PrimitiveStringMultiline(
            _id='487',
            value='The Joker looks at the camera and talks, he says "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3". \n\nThen the Joker stands up with an LTX soda can in his hand. \n\nHe drinks from the soda can, and then he says "Ahhh...  with a bit of LTX and Snickers, my mood changed. Lets all be friends." \n\nThen he laughs.\n',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

        reroute = raw_call(wf, 'Reroute', '496')
        wf.metadata.setdefault('id_map', {})['reroute'] = reroute.node.id
        intconstant_3 = INTConstant(_id='497', value=832)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        getnode_21 = raw_call(wf, 'GetNode', '502', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_21'] = getnode_21.node.id
        getnode_22 = raw_call(wf, 'GetNode', '507', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_22'] = getnode_22.node.id
        getnode_23 = raw_call(wf, 'GetNode', '508', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_23'] = getnode_23.node.id
        getnode_24 = raw_call(wf, 'GetNode', '514', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_24'] = getnode_24.node.id
        reroute_2 = raw_call(wf, 'Reroute', '528')
        wf.metadata.setdefault('id_map', {})['reroute_2'] = reroute_2.node.id
        getnode_25 = raw_call(wf, 'GetNode', '541', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_25'] = getnode_25.node.id
        getnode_26 = raw_call(wf, 'GetNode', '542', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_26'] = getnode_26.node.id
        getnode_27 = raw_call(wf, 'GetNode', '555', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_27'] = getnode_27.node.id
        getnode_28 = raw_call(wf, 'GetNode', '572', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_28'] = getnode_28.node.id
        getnode_29 = raw_call(wf, 'GetNode', '573', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_29'] = getnode_29.node.id
        getnode_30 = raw_call(wf, 'GetNode', '576', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_30'] = getnode_30.node.id
        getnode_31 = raw_call(wf, 'GetNode', '577', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_31'] = getnode_31.node.id
        getnode_32 = raw_call(wf, 'GetNode', '579', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_32'] = getnode_32.node.id
        getnode_33 = raw_call(wf, 'GetNode', '580', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_33'] = getnode_33.node.id
        getnode_34 = raw_call(wf, 'GetNode', '581', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_34'] = getnode_34.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '594', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        getnode_35 = raw_call(wf, 'GetNode', '600', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_35'] = getnode_35.node.id
        getnode_36 = raw_call(wf, 'GetNode', '602', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_36'] = getnode_36.node.id
        getnode_37 = raw_call(wf, 'GetNode', '606', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_37'] = getnode_37.node.id
        getnode_38 = raw_call(wf, 'GetNode', '628', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_38'] = getnode_38.node.id
        getnode_39 = raw_call(wf, 'GetNode', '638', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_39'] = getnode_39.node.id
        getnode_40 = raw_call(wf, 'GetNode', '640', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_40'] = getnode_40.node.id
        getnode_41 = raw_call(wf, 'GetNode', '641', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_41'] = getnode_41.node.id
        loadaudio = LoadAudio(_id='642', audio=AUDIO, widget_0='speech_smoke.wav')
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id
        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='110',
            text=DEFAULT_PROMPT,
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        setnode_3 = raw_call(wf, 'SetNode', '209', widget_0=WIDGET_0_7, INT=intconstant)
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id
        setnode_4 = raw_call(wf, 'SetNode', '210',
            widget_0=WIDGET_0_4,
            FLOAT=primitivefloat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        getimagerangefrombatch = GetImageRangeFromBatch(
            _id='306',
            widget_0=0,
            widget_1=4096,
            images=reroute_2.out(0),
            start_index=getnode_11.out(0),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch'] = getimagerangefrombatch.node.id

        vhs_loadvideo = VHS_LoadVideo(
            _id='319',
            file='ltx_smoke_guide.mp4',
            video='ltx_smoke_guide.mp4',
            widget_0='ltx_smoke_guide.mp4',
            force_rate=getnode_6.out(0),
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

        simplecalculatorkj = SimpleCalculatorKJ(
            _id='352',
            expression=EXPRESSION,
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': intconstant, 'variables.b': primitivefloat},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj'] = simplecalculatorkj.node.id

        simplecalculatorkj_2 = SimpleCalculatorKJ(
            _id='357',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_12.out(0), 'variables.b': getnode_24.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_2'] = simplecalculatorkj_2.node.id

        getimagerangefrombatch_2 = GetImageRangeFromBatch(
            _id='379',
            widget_0=-1,
            widget_1=1,
            images=getnode_39.out(0),
            num_frames=getnode_15.out(0),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_2'] = getimagerangefrombatch_2.node.id

        normalizeaudioloudness = NormalizeAudioLoudness(
            _id='443',
            widget_0=-16,
            audio=loadaudio,
        )
        wf.metadata.setdefault('id_map', {})['normalizeaudioloudness'] = normalizeaudioloudness.node.id

        setnode_16 = raw_call(wf, 'SetNode', '459',
            widget_0=WIDGET_0_5,
            LATENT_UPSCALE_MODEL=latentupscalemodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_16'] = setnode_16.node.id

        setnode_17 = raw_call(wf, 'SetNode', '460',
            widget_0=WIDGET_0_2,
            VAE=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_17'] = setnode_17.node.id

        setnode_18 = raw_call(wf, 'SetNode', '461', widget_0=WIDGET_0_3, VAE=vaeloader)
        wf.metadata.setdefault('id_map', {})['setnode_18'] = setnode_18.node.id
        setnode_19 = raw_call(wf, 'SetNode', '462',
            widget_0=WIDGET_0,
            CLIP=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_19'] = setnode_19.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='464',
            lora_name=MODEL_NAME_10,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        setnode_20 = raw_call(wf, 'SetNode', '472',
            widget_0=WIDGET_0_12,
            VAE=vaeloader_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_20'] = setnode_20.node.id

        setnode_22 = raw_call(wf, 'SetNode', '498',
            widget_0=WIDGET_0_14,
            INT=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_22'] = setnode_22.node.id

        resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
            _id='505',
            longer_edge=getnode_22.out(0),
            images=reroute.out(0),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge_2'] = resizeimagesbylongeredge_2.node.id

        modelsamplingsd3 = ModelSamplingSD3(
            _id='526',
            shift=13,
            model=getnode_14.out(0),
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingsd3'] = modelsamplingsd3.node.id

        imagebatchextendwithoverlap = ImageBatchExtendWithOverlap(
            _id='536',
            widget_0=1,
            widget_1='source',
            widget_2='perceptual_crossfade',
            new_images=reroute_2.out(0),
            overlap=getnode_26.out(0),
            source_images=getnode_25.out(0),
            _outputs=('SOURCE_IMAGES', 'START_IMAGES', 'EXTENDED_IMAGES'),
        )
        wf.metadata.setdefault('id_map', {})['imagebatchextendwithoverlap'] = imagebatchextendwithoverlap.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='578',
            frame_rate=getnode_33.out(0),
            audio=getnode_32.out(0),
            images=getnode_34.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9 = raw_call(wf, '6002fb3c-ab34-4ad8-894e-fccaa60fd8c9', '599',
            clip=getnode_35.out(0),
            image=getnode_23.out(0),
            string_b=primitivestringmultiline,
        )
        wf.metadata.setdefault('id_map', {})['n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9'] = n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9.node.id

        setnode_25 = raw_call(wf, 'SetNode', '601',
            widget_0=WIDGET_0_20,
            BOOLEAN=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['setnode_25'] = setnode_25.node.id

        simplecalculatorkj_6 = SimpleCalculatorKJ(
            _id='605',
            expression=EXPRESSION,
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': intconstant_2, 'variables.b': getnode_37.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_6'] = simplecalculatorkj_6.node.id

        # Conditioning
        cliptextencode_3 = CLIPTextEncode(
            _id='626',
            text=DEFAULT_PROMPT_2,
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_3'] = cliptextencode_3.node.id

        # Outputs
        vhs_videocombine_2 = VHS_VideoCombine(
            _id='627',
            frame_rate=getnode_41.out(0),
            audio=getnode_40.out(0),
            images=getnode_38.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_2'] = vhs_videocombine_2.node.id

        # Sampling
        basicscheduler = BasicScheduler(
            _id='164',
            scheduler=1,
            steps=1,
            widget_1=8,
            model=modelsamplingsd3,
        )
        wf.metadata.setdefault('id_map', {})['basicscheduler'] = basicscheduler.node.id

        setnode_9 = raw_call(wf, 'SetNode', '310',
            widget_0=WIDGET_0_6,
            INT=simplecalculatorkj_6.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        setnode_11 = raw_call(wf, 'SetNode', '329',
            widget_0=WIDGET_0_10,
            AUDIO=normalizeaudioloudness,
        )
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id

        setnode_12 = raw_call(wf, 'SetNode', '349',
            widget_0='extended_frames',
            INT=simplecalculatorkj.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_12'] = setnode_12.node.id

        vhs_videoinfo = VHS_VideoInfo(
            _id='382',
            video_info=vhs_loadvideo.out('VIDEO_INFO'),
            _outputs=('SOURCE_FPS🟨', 'SOURCE_FRAME_COUNT🟨', 'SOURCE_DURATION🟨', 'SOURCE_WIDTH🟨', 'SOURCE_HEIGHT🟨', 'LOADED_FPS🟦', 'LOADED_FRAME_COUNT🟦', 'LOADED_DURATION🟦', 'LOADED_WIDTH🟦', 'LOADED_HEIGHT🟦'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videoinfo'] = vhs_videoinfo.node.id

        imagebatchmulti = ImageBatchMulti(
            _id='403',
            widget_0=2,
            image_1=getnode_13.out(0),
            image_2=getimagerangefrombatch.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['imagebatchmulti'] = imagebatchmulti.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='436',
            resize_type='scale by multiplier',
            input=getimagerangefrombatch_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        vhs_videoinfo_2 = VHS_VideoInfo(
            _id='492',
            video_info=vhs_loadvideo.out('VIDEO_INFO'),
            _outputs=('SOURCE_FPS🟨', 'SOURCE_FRAME_COUNT🟨', 'SOURCE_DURATION🟨', 'SOURCE_WIDTH🟨', 'SOURCE_HEIGHT🟨', 'LOADED_FPS🟦', 'LOADED_FRAME_COUNT🟦', 'LOADED_DURATION🟦', 'LOADED_WIDTH🟦', 'LOADED_HEIGHT🟦'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videoinfo_2'] = vhs_videoinfo_2.node.id

        pathchsageattentionkj = PathchSageAttentionKJ(
            _id='520',
            sage_attention='disabled',
            model=loraloadermodelonly,
        )
        wf.metadata.setdefault('id_map', {})['pathchsageattentionkj'] = pathchsageattentionkj.node.id

        ltx2_nag = LTX2_NAG(
            _id='563',
            model=getnode_14.out(0),
            nag_cond_audio=cliptextencode_3,
            nag_cond_video=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id

        getimagerangefrombatch_5 = GetImageRangeFromBatch(
            _id='566',
            widget_0=0,
            widget_1=1,
            images=getimagerangefrombatch_2.out('IMAGE'),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_5'] = getimagerangefrombatch_5.node.id

        setnode_24 = raw_call(wf, 'SetNode', '574',
            widget_0=WIDGET_0_19,
            IMAGE=imagebatchextendwithoverlap.out('EXTENDED_IMAGES'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_24'] = setnode_24.node.id

        # Conditioning
        cliptextencode_2 = CLIPTextEncode(
            _id='592',
            text=n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9.out(0),
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        simplecalculatorkj_3 = SimpleCalculatorKJ(
            _id='384',
            expression='a / b',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_15.out(0), 'variables.b': vhs_videoinfo.out('LOADED_FPS🟦')},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_3'] = simplecalculatorkj_3.node.id

        setnode_14 = raw_call(wf, 'SetNode', '451',
            widget_0=WIDGET_0_21,
            IMAGE=imagebatchmulti,
        )
        wf.metadata.setdefault('id_map', {})['setnode_14'] = setnode_14.node.id

        simplecalculatorkj_5 = SimpleCalculatorKJ(
            _id='500',
            expression='(a > c) or (b > c) ',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': vhs_videoinfo_2.out('LOADED_WIDTH🟦'), 'variables.b': vhs_videoinfo_2.out('LOADED_HEIGHT🟦'), 'variables.c': getnode_21.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_5'] = simplecalculatorkj_5.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='522',
            model=pathchsageattentionkj,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        getimagerangefrombatch_4 = GetImageRangeFromBatch(
            _id='556',
            widget_0=-1,
            widget_1=1,
            images=resizeimagemasknode,
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_4'] = getimagerangefrombatch_4.node.id

        vaeencode_2 = VAEEncode(
            _id='565',
            pixels=resizeimagemasknode,
            vae=getnode_3.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaeencode_2'] = vaeencode_2.node.id

        setnode_23 = raw_call(wf, 'SetNode', '567',
            widget_0=WIDGET_0_13,
            IMAGE=getimagerangefrombatch_5.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_23'] = setnode_23.node.id

        simplecalculatorkj_4 = SimpleCalculatorKJ(
            _id='386',
            expression='a - b',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': vhs_videoinfo.out('LOADED_DURATION🟦'), 'variables.b': simplecalculatorkj_3.out('FLOAT')},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_4'] = simplecalculatorkj_4.node.id

        setnode_13 = raw_call(wf, 'SetNode', '397',
            widget_0=WIDGET_0_11,
            FLOAT=simplecalculatorkj_3.out('FLOAT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_13'] = setnode_13.node.id

        lazyswitchkj = LazySwitchKJ(
            _id='504',
            widget_0=False,
            on_false=reroute.out(0),
            on_true=resizeimagesbylongeredge_2,
            switch=simplecalculatorkj_5.out('BOOLEAN'),
        )
        wf.metadata.setdefault('id_map', {})['lazyswitchkj'] = lazyswitchkj.node.id

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            _id='523',
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['ltx2attentiontunerpatch'] = ltx2attentiontunerpatch.node.id

        vaeencode = VAEEncode(
            _id='546',
            pixels=getimagerangefrombatch_4.out('IMAGE'),
            vae=getnode_27.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaeencode'] = vaeencode.node.id

        trimaudioduration = TrimAudioDuration(
            _id='377',
            widget_0=0,
            widget_1=60,
            audio=normalizeaudioloudness,
            duration=simplecalculatorkj_3.out('FLOAT'),
            start_index=simplecalculatorkj_4.out('FLOAT'),
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration'] = trimaudioduration.node.id

        setnode_21 = raw_call(wf, 'SetNode', '481',
            widget_0=WIDGET_0_9,
            MODEL=ltx2attentiontunerpatch,
        )
        wf.metadata.setdefault('id_map', {})['setnode_21'] = setnode_21.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='506',
            image=lazyswitchkj,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            _id='179',
            audio=trimaudioduration,
            audio_vae=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='512',
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=64,
            device='cpu',
            width=getimagesizeandcount.out('WIDTH'),
            height=getimagesizeandcount.out('HEIGHT'),
            image=getimagesizeandcount.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        ltxvaudiovideomask = LTXVAudioVideoMask(
            _id='178',
            widget_0=24,
            widget_1=0,
            widget_2=15,
            widget_3=0,
            widget_4=15,
            widget_5='pad',
            widget_6='add',
            audio_end_time=simplecalculatorkj_2.out('FLOAT'),
            audio_latent=ltxvaudiovaeencode,
            audio_start_time=getnode_24.out(0),
            video_end_time=simplecalculatorkj_2.out('FLOAT'),
            video_fps=getnode_8.out(0),
            video_latent=vaeencode_2,
            video_start_time=getnode_24.out(0),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovideomask'] = ltxvaudiovideomask.node.id

        setnode = raw_call(wf, 'SetNode', '207',
            widget_0='width',
            INT=imageresizekjv2.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        setnode_2 = raw_call(wf, 'SetNode', '208',
            widget_0='height',
            INT=imageresizekjv2.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        setnode_10 = raw_call(wf, 'SetNode', '328',
            widget_0=WIDGET_0_8,
            IMAGE=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        getimagerangefrombatch_3 = GetImageRangeFromBatch(
            _id='440',
            widget_0=0,
            widget_1=1,
            images=imageresizekjv2.out('IMAGE'),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_3'] = getimagerangefrombatch_3.node.id

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            _id='495',
            longer_edge=1536,
            images=getimagerangefrombatch_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge'] = resizeimagesbylongeredge.node.id

        ltxvaddlatentguide = LTXVAddLatentGuide(
            _id='545',
            widget_0=-1,
            widget_1=1,
            guiding_latent=vaeencode,
            latent=ltxvaudiovideomask.out('VIDEO_LATENT'),
            negative=cliptextencode,
            positive=cliptextencode_2,
            vae=getnode_27.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaddlatentguide'] = ltxvaddlatentguide.node.id

        ltxvconditioning = LTXVConditioning(
            _id='107',
            frame_rate=getnode_7.out(0),
            negative=ltxvaddlatentguide.out('NEGATIVE'),
            positive=ltxvaddlatentguide.out('POSITIVE'),
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='109',
            audio_latent=ltxvaudiovideomask.out('AUDIO_LATENT'),
            video_latent=ltxvaddlatentguide.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        setnode_8 = raw_call(wf, 'SetNode', '294',
            widget_0=WIDGET_0_15,
            IMAGE=resizeimagesbylongeredge,
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='299',
            img_compression=18,
            image=resizeimagesbylongeredge,
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        cfgguider = CFGGuider(
            _id='129',
            cfg=GUIDE_STRENGTH_2,
            model=ltx2_nag,
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        setnode_5 = raw_call(wf, 'SetNode', '224',
            widget_0=WIDGET_0_16,
            CONDITIONING=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        setnode_6 = raw_call(wf, 'SetNode', '225',
            widget_0=WIDGET_0_17,
            CONDITIONING=ltxvconditioning.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        setnode_7 = raw_call(wf, 'SetNode', '285',
            widget_0='compress_image',
            IMAGE=ltxvpreprocess,
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='113',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=basicscheduler,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='250',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='549',
            latent=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            negative=getnode_29.out(0),
            positive=getnode_28.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        # Conditioning
        cfgguider_2 = CFGGuider(
            _id='256',
            cfg=GUIDE_STRENGTH_2,
            model=ltx2_nag,
            negative=ltxvcropguides.out('NEGATIVE'),
            positive=ltxvcropguides.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            _id='438',
            widget_0=1,
            widget_1=False,
            image=getnode_19.out(0),
            latent=ltxvcropguides.out('LATENT'),
            vae=getnode_20.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='251',
            audio_latent=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
            video_latent=ltxvimgtovideoinplace,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        # Sampling
        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='258',
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='125',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='425',
            audio_vae=getnode_4.out(0),
            samples=ltxvseparateavlatent.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        ltxvcropguides_2 = LTXVCropGuides(
            _id='569',
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            negative=getnode_31.out(0),
            positive=getnode_30.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides_2'] = ltxvcropguides_2.node.id

        trimaudioduration_2 = TrimAudioDuration(
            _id='394',
            widget_0=0,
            widget_1=2048,
            audio=ltxvaudiovaedecode,
            start_index=getnode_17.out(0),
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration_2'] = trimaudioduration_2.node.id

        # Decode
        vaedecode = VAEDecode(
            _id='527',
            samples=ltxvcropguides_2.out('LATENT'),
            vae=getnode_5.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaedecode'] = vaedecode.node.id

        audioconcat = AudioConcat(
            _id='393',
            widget_0='after',
            audio1=getnode_16.out(0),
            audio2=trimaudioduration_2,
        )
        wf.metadata.setdefault('id_map', {})['audioconcat'] = audioconcat.node.id

        setnode_15 = raw_call(wf, 'SetNode', '453',
            widget_0=WIDGET_0_18,
            AUDIO=audioconcat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_15'] = setnode_15.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

