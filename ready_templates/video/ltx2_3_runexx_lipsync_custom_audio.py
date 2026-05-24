# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, GetImageRangeFromBatch, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoraLoaderModelOnly, ManualSigmas, MaskToImage, ModelSamplingSD3, PreviewImage, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, TrimAudioDuration, UNETLoader, VAEDecode, VAEDecodeTiled, VAEEncode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import BlockifyMask, GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVAudioVideoMask, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.ltxvideo import LTXVAddLatentGuide, LTXVPreprocessMasks, LTXVSetVideoLatentNoiseMasks
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideoFFmpeg, VHS_VideoCombine, VHS_VideoInfo

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


DEFAULT_PROMPT = 'text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_PROMPT_2 = ' distorted sound, saturated sound, loud sound'
DEFAULT_SEED = 790774741312584
DEFAULT_SEED_2 = 43
DEVICE = 'default'
GUIDE_STRENGTH = 2.5
GUIDE_STRENGTH_2 = 0.6
MODEL_NAME = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_10 = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_11 = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_12 = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME_2 = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_3 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_4 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_6 = 'taeltx2_3.safetensors'
MODEL_NAME_7 = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_8 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
MODEL_NAME_9 = 'gemma-3-12b-it-Q2_K.gguf'
RESIZE_TYPE = 'scale by multiplier'
SCALE_METHOD = 'nearest-exact'
WIDGET_0 = 'clip'
WIDGET_0_10 = 'max_size'
WIDGET_0_11 = 'positive'
WIDGET_0_12 = 'negative'
WIDGET_0_13 = 'final_video'
WIDGET_0_14 = 'enable_promptenhance'
WIDGET_0_15 = 'ref_video'
WIDGET_0_16 = 'final_audio'
WIDGET_0_17 = 'model_n_nag'
WIDGET_0_18 = 'last_latent_strength'
WIDGET_0_19 = 'positive_to_crop'
WIDGET_0_2 = 'vae_audio'
WIDGET_0_20 = 'negative_to_crop'
WIDGET_0_21 = 'latent_custom_audio'
WIDGET_0_22 = 'latent_audio'
WIDGET_0_23 = 'height_generated'
WIDGET_0_24 = 'width_generated'
WIDGET_0_25 = 'frames_loaded'
WIDGET_0_26 = 'latent_audio_selected'
WIDGET_0_3 = 'vae'
WIDGET_0_4 = 'fps'
WIDGET_0_5 = 'upscale_model'
WIDGET_0_6 = 'ext_seconds'
WIDGET_0_7 = 'model'
WIDGET_0_8 = 'vae_tiny'
WIDGET_0_9 = 'ref_image'


MODELS = {}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node=ref('latentupscalemodelloader'), field='model_name', default=MODEL_NAME_2),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'steps': InputSpec(node=ref('basicscheduler'), field='steps', default=15),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
}

READY_METADATA = ReadyMetadata.build(
    capability='voice_to_lipsync_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX23_audio_vae_bf16.safetensors', 'LTX23_video_vae_bf16.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'taeltx2_3.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='custom-audio lip-sync / voice-to-video',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        randomnoise = RandomNoise(
            _id='115',
            noise_seed=DEFAULT_SEED,
            control_after_generate='randomize',
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(_id='127', temporal_size=4096)
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id
        # Sampling
        ksamplerselect = KSamplerSelect(
            _id='137',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id

        intconstant = INTConstant(_id='211', value=3)
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
        getnode_8 = raw_call(wf, 'GetNode', '242', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        randomnoise_2 = RandomNoise(
            _id='243',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate='fixed',
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        getnode_9 = raw_call(wf, 'GetNode', '244', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        # Sampling
        ksamplerselect_2 = KSamplerSelect(_id='254', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id
        getnode_10 = raw_call(wf, 'GetNode', '356', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '369', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '408', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '439', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '442', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
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
            device=DEVICE,
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
            value='Cinematic video woman wearing colorful make-up, with colorful  light creating a creative scene. \n\nShe talks with perfect lip-sync movements to the attached audio. Her mouth and lips moves as she talks. \n \nThe camera slowly moves away from the woman, showing her full body. She is standing at a  colorful theatre scene doing a victorian era play. ',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

        reroute = raw_call(wf, 'Reroute', '496')
        wf.metadata.setdefault('id_map', {})['reroute'] = reroute.node.id
        intconstant_2 = INTConstant(_id='497', value=650)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        getnode_15 = raw_call(wf, 'GetNode', '502', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        getnode_16 = raw_call(wf, 'GetNode', '507', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        getnode_17 = raw_call(wf, 'GetNode', '508', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '572', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '573', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        getnode_20 = raw_call(wf, 'GetNode', '580', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        getnode_21 = raw_call(wf, 'GetNode', '581', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_21'] = getnode_21.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '594', value=False)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        getnode_22 = raw_call(wf, 'GetNode', '600', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_22'] = getnode_22.node.id
        getnode_23 = raw_call(wf, 'GetNode', '602', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_23'] = getnode_23.node.id
        getnode_24 = raw_call(wf, 'GetNode', '638', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_24'] = getnode_24.node.id
        getnode_25 = raw_call(wf, 'GetNode', '643', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_25'] = getnode_25.node.id
        getnode_26 = raw_call(wf, 'GetNode', '649', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_26'] = getnode_26.node.id
        getnode_27 = raw_call(wf, 'GetNode', '652', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_27'] = getnode_27.node.id
        getnode_28 = raw_call(wf, 'GetNode', '654', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_28'] = getnode_28.node.id
        getnode_29 = raw_call(wf, 'GetNode', '719', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_29'] = getnode_29.node.id
        getnode_30 = raw_call(wf, 'GetNode', '724', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_30'] = getnode_30.node.id
        getnode_31 = raw_call(wf, 'GetNode', '731', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_31'] = getnode_31.node.id
        getnode_32 = raw_call(wf, 'GetNode', '732', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_32'] = getnode_32.node.id
        getnode_33 = raw_call(wf, 'GetNode', '739', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_33'] = getnode_33.node.id
        getnode_34 = raw_call(wf, 'GetNode', '740', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_34'] = getnode_34.node.id
        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            _id='742',
            text_encoder=MODEL_NAME_3,
            ckpt_name=MODEL_NAME_10,
            device=DEVICE,
        )
        wf.metadata.setdefault('id_map', {})['ltxavtextencoderloader'] = ltxavtextencoderloader.node.id

        getnode_35 = raw_call(wf, 'GetNode', '804', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_35'] = getnode_35.node.id
        # Inputs
        primitivefloat_2 = raw_call(wf, 'PrimitiveFloat', '814', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_2'] = primitivefloat_2.node.id
        getnode_36 = raw_call(wf, 'GetNode', '816', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_36'] = getnode_36.node.id
        getnode_37 = raw_call(wf, 'GetNode', '822', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_37'] = getnode_37.node.id
        getnode_38 = raw_call(wf, 'GetNode', '823', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_38'] = getnode_38.node.id
        getnode_39 = raw_call(wf, 'GetNode', '825', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_39'] = getnode_39.node.id
        getnode_40 = raw_call(wf, 'GetNode', '826', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_40'] = getnode_40.node.id
        getnode_41 = raw_call(wf, 'GetNode', '845', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_41'] = getnode_41.node.id
        getnode_42 = raw_call(wf, 'GetNode', '846', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_42'] = getnode_42.node.id
        loadaudio = LoadAudio(
            _id='855',
            audio='e9318ca1-5e2b-47aa-8397-f4538b0151b0.wav',
        )
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id

        getnode_43 = raw_call(wf, 'GetNode', '856', widget_0=WIDGET_0_23)
        wf.metadata.setdefault('id_map', {})['getnode_43'] = getnode_43.node.id
        getnode_44 = raw_call(wf, 'GetNode', '858', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_44'] = getnode_44.node.id
        melbandroformermodelloader = raw_call(wf, 'MelBandRoFormerModelLoader', '861',
            widget_0=MODEL_NAME_11,
        )
        wf.metadata.setdefault('id_map', {})['melbandroformermodelloader'] = melbandroformermodelloader.node.id

        getnode_45 = raw_call(wf, 'GetNode', '862', widget_0=WIDGET_0_24)
        wf.metadata.setdefault('id_map', {})['getnode_45'] = getnode_45.node.id
        getnode_46 = raw_call(wf, 'GetNode', '872', widget_0=WIDGET_0_25)
        wf.metadata.setdefault('id_map', {})['getnode_46'] = getnode_46.node.id
        getnode_47 = raw_call(wf, 'GetNode', '873', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_47'] = getnode_47.node.id
        getnode_48 = raw_call(wf, 'GetNode', '874', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_48'] = getnode_48.node.id
        getnode_49 = raw_call(wf, 'GetNode', '879', widget_0=WIDGET_0_26)
        wf.metadata.setdefault('id_map', {})['getnode_49'] = getnode_49.node.id
        getnode_50 = raw_call(wf, 'GetNode', '887', widget_0=WIDGET_0_26)
        wf.metadata.setdefault('id_map', {})['getnode_50'] = getnode_50.node.id
        ltxvconditioning = LTXVConditioning(
            _id='107',
            frame_rate=getnode_7.out(0),
            negative=getnode_34.out(0),
            positive=getnode_33.out(0),
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='110',
            text=DEFAULT_PROMPT,
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        setnode_3 = raw_call(wf, 'SetNode', '209', widget_0=WIDGET_0_6, INT=intconstant)
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id
        setnode_4 = raw_call(wf, 'SetNode', '210',
            widget_0=WIDGET_0_4,
            FLOAT=primitivefloat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        cfgguider_2 = CFGGuider(
            _id='256',
            cfg=GUIDE_STRENGTH,
            model=getnode_27.out(0),
            negative=getnode_19.out(0),
            positive=getnode_18.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='436',
            resize_type=RESIZE_TYPE,
            input=getnode_24.out(0),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        setnode_9 = raw_call(wf, 'SetNode', '459',
            widget_0=WIDGET_0_5,
            LATENT_UPSCALE_MODEL=latentupscalemodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        setnode_10 = raw_call(wf, 'SetNode', '460',
            widget_0=WIDGET_0_2,
            VAE=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        setnode_11 = raw_call(wf, 'SetNode', '461', widget_0=WIDGET_0_3, VAE=vaeloader)
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id
        setnode_12 = raw_call(wf, 'SetNode', '462',
            widget_0=WIDGET_0,
            CLIP=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_12'] = setnode_12.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='464',
            lora_name=MODEL_NAME_12,
            strength_model=GUIDE_STRENGTH_2,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        setnode_13 = raw_call(wf, 'SetNode', '472',
            widget_0=WIDGET_0_8,
            VAE=vaeloader_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_13'] = setnode_13.node.id

        setnode_15 = raw_call(wf, 'SetNode', '498',
            widget_0=WIDGET_0_10,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_15'] = setnode_15.node.id

        resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
            _id='505',
            longer_edge=getnode_16.out(0),
            images=reroute.out(0),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge_2'] = resizeimagesbylongeredge_2.node.id

        modelsamplingsd3 = ModelSamplingSD3(
            _id='526',
            shift=13,
            model=getnode_11.out(0),
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingsd3'] = modelsamplingsd3.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='578',
            frame_rate=getnode_20.out(0),
            audio=getnode_26.out(0),
            images=getnode_21.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        setnode_16 = raw_call(wf, 'SetNode', '601',
            widget_0=WIDGET_0_14,
            BOOLEAN=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['setnode_16'] = setnode_16.node.id

        # Conditioning
        cliptextencode_3 = CLIPTextEncode(
            _id='626',
            text=DEFAULT_PROMPT_2,
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_3'] = cliptextencode_3.node.id

        getimagesizeandcount_2 = GetImageSizeAndCount(
            _id='698',
            image=getnode_24.out(0),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_2'] = getimagesizeandcount_2.node.id

        comfymathexpression = ComfyMathExpression(
            _id='699',
            widget_0='a',
            _outputs=('FLOAT', 'INT'),
            **{'values.a': getnode_25.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['comfymathexpression'] = comfymathexpression.node.id

        resizeimagemasknode_3 = ResizeImageMaskNode(
            _id='726',
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=getnode_30.out(0),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_3'] = resizeimagemasknode_3.node.id

        vhs_loadvideoffmpeg = VHS_LoadVideoFFmpeg(
            _id='774',
            force_rate=getnode_6.out(0),
            _outputs=('IMAGE', 'MASK', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideoffmpeg'] = vhs_loadvideoffmpeg.node.id

        e428c881_c48b_4849_9158_8311b4df27c7 = raw_call(wf, 'e428c881-c48b-4849-9158-8311b4df27c7', '784',
            clip=getnode_22.out(0),
            image=getnode_17.out(0),
            switch=getnode_23.out(0),
        )
        wf.metadata.setdefault('id_map', {})['e428c881_c48b_4849_9158_8311b4df27c7'] = e428c881_c48b_4849_9158_8311b4df27c7.node.id

        setnode_21 = raw_call(wf, 'SetNode', '815',
            widget_0=WIDGET_0_18,
            FLOAT=primitivefloat_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_21'] = setnode_21.node.id

        comfyswitchnode = ComfySwitchNode(
            _id='847',
            widget_0=True,
            on_false=getnode_42.out(0),
            on_true=getnode_41.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode'] = comfyswitchnode.node.id

        simplecalculatorkj_2 = SimpleCalculatorKJ(
            _id='854',
            expression='(a/b)+c',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_46.out(0), 'variables.b': getnode_47.out(0), 'variables.c': getnode_48.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_2'] = simplecalculatorkj_2.node.id

        solidmask = SolidMask(
            _id='865',
            widget_0=0,
            widget_1=512,
            widget_2=512,
            height=getnode_43.out(0),
            width=getnode_45.out(0),
        )
        wf.metadata.setdefault('id_map', {})['solidmask'] = solidmask.node.id

        # Sampling
        basicscheduler = BasicScheduler(
            _id='164',
            scheduler=1,
            steps=1,
            widget_1=15,
            model=modelsamplingsd3,
        )
        wf.metadata.setdefault('id_map', {})['basicscheduler'] = basicscheduler.node.id

        vhs_videoinfo = VHS_VideoInfo(
            _id='492',
            video_info=vhs_loadvideoffmpeg.out('VIDEO_INFO'),
            _outputs=('SOURCE_FPS🟨', 'SOURCE_FRAME_COUNT🟨', 'SOURCE_DURATION🟨', 'SOURCE_WIDTH🟨', 'SOURCE_HEIGHT🟨', 'LOADED_FPS🟦', 'LOADED_FRAME_COUNT🟦', 'LOADED_DURATION🟦', 'LOADED_WIDTH🟦', 'LOADED_HEIGHT🟦'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videoinfo'] = vhs_videoinfo.node.id

        pathchsageattentionkj = PathchSageAttentionKJ(
            _id='520',
            sage_attention='disabled',
            model=loraloadermodelonly,
        )
        wf.metadata.setdefault('id_map', {})['pathchsageattentionkj'] = pathchsageattentionkj.node.id

        ltx2_nag = LTX2_NAG(
            _id='563',
            model=getnode_11.out(0),
            nag_cond_audio=cliptextencode_3,
            nag_cond_video=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id

        vaeencode = VAEEncode(
            _id='565',
            pixels=resizeimagemasknode,
            vae=getnode_3.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaeencode'] = vaeencode.node.id

        # Conditioning
        cliptextencode_2 = CLIPTextEncode(
            _id='592',
            text=e428c881_c48b_4849_9158_8311b4df27c7.out(0),
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='642',
            frames_number=getimagesizeandcount_2.out('COUNT'),
            frame_rate=comfymathexpression.out('INT'),
            audio_vae=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        setnode_20 = raw_call(wf, 'SetNode', '656',
            widget_0=WIDGET_0_12,
            CONDITIONING=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_20'] = setnode_20.node.id

        comfymathexpression_2 = ComfyMathExpression(
            _id='700',
            widget_0='a/b',
            _outputs=('FLOAT', 'INT'),
            **{'values.a': getimagesizeandcount_2.out('COUNT'), 'values.b': getnode_25.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['comfymathexpression_2'] = comfymathexpression_2.node.id

        getimagerangefrombatch_2 = GetImageRangeFromBatch(
            _id='714',
            widget_0=0,
            widget_1=1,
            images=resizeimagemasknode_3,
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_2'] = getimagerangefrombatch_2.node.id

        facesegment = raw_call(wf, 'FaceSegment', '761',
            widget_0=True,
            widget_1=True,
            widget_10=True,
            widget_11=True,
            widget_12=False,
            widget_13=False,
            widget_14=False,
            widget_15=512,
            widget_16=0,
            widget_17=10,
            widget_18=False,
            widget_19='Alpha',
            widget_2=False,
            widget_20='#222222',
            widget_3=True,
            widget_4=True,
            widget_5=False,
            widget_6=True,
            widget_7=True,
            widget_8=True,
            widget_9=True,
            images=resizeimagemasknode_3,
        )
        wf.metadata.setdefault('id_map', {})['facesegment'] = facesegment.node.id

        getimagerangefrombatch_4 = GetImageRangeFromBatch(
            _id='806',
            widget_0=-1,
            widget_1=1,
            images=resizeimagemasknode,
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_4'] = getimagerangefrombatch_4.node.id

        setnode_24 = raw_call(wf, 'SetNode', '849',
            widget_0=WIDGET_0_26,
            LATENT=comfyswitchnode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_24'] = setnode_24.node.id

        trimaudioduration = TrimAudioDuration(
            _id='859',
            widget_0=0,
            widget_1=40,
            audio=loadaudio,
            duration=simplecalculatorkj_2.out('FLOAT'),
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration'] = trimaudioduration.node.id

        setnode_31 = raw_call(wf, 'SetNode', '883',
            widget_0=WIDGET_0_24,
            INT=getimagesizeandcount_2.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_31'] = setnode_31.node.id

        setnode_32 = raw_call(wf, 'SetNode', '884',
            widget_0=WIDGET_0_23,
            INT=getimagesizeandcount_2.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_32'] = setnode_32.node.id

        simplecalculatorkj = SimpleCalculatorKJ(
            _id='500',
            expression='(a > c) or (b > c) ',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': vhs_videoinfo.out('LOADED_WIDTH🟦'), 'variables.b': vhs_videoinfo.out('LOADED_HEIGHT🟦'), 'variables.c': getnode_15.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj'] = simplecalculatorkj.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='522',
            model=pathchsageattentionkj,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        setnode_18 = raw_call(wf, 'SetNode', '651',
            widget_0=WIDGET_0_17,
            MODEL=ltx2_nag,
        )
        wf.metadata.setdefault('id_map', {})['setnode_18'] = setnode_18.node.id

        setnode_19 = raw_call(wf, 'SetNode', '655',
            widget_0=WIDGET_0_11,
            CONDITIONING=cliptextencode_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_19'] = setnode_19.node.id

        comfymathexpression_3 = ComfyMathExpression(
            _id='701',
            widget_0='a+b',
            _outputs=('FLOAT', 'INT'),
            **{'values.a': comfymathexpression_2.out('FLOAT'), 'values.b': getnode_10.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['comfymathexpression_3'] = comfymathexpression_3.node.id

        blockifymask = BlockifyMask(
            _id='790',
            block_size=12,
            widget_1='cpu',
            masks=facesegment.out(1),
        )
        wf.metadata.setdefault('id_map', {})['blockifymask'] = blockifymask.node.id

        vaeencode_2 = VAEEncode(
            _id='809',
            pixels=getimagerangefrombatch_4.out('IMAGE'),
            vae=getnode_35.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaeencode_2'] = vaeencode_2.node.id

        setnode_25 = raw_call(wf, 'SetNode', '852',
            widget_0='audio_original',
            AUDIO=trimaudioduration,
        )
        wf.metadata.setdefault('id_map', {})['setnode_25'] = setnode_25.node.id

        melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '860',
            audio=trimaudioduration,
            model=melbandroformermodelloader.out(0),
        )
        wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

        setnode_29 = raw_call(wf, 'SetNode', '871',
            widget_0=WIDGET_0_25,
            INT=vhs_videoinfo.out('LOADED_FRAME_COUNT🟦'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_29'] = setnode_29.node.id

        lazyswitchkj = LazySwitchKJ(
            _id='504',
            widget_0=False,
            on_false=reroute.out(0),
            on_true=resizeimagesbylongeredge_2,
            switch=simplecalculatorkj.out('BOOLEAN'),
        )
        wf.metadata.setdefault('id_map', {})['lazyswitchkj'] = lazyswitchkj.node.id

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            _id='523',
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['ltx2attentiontunerpatch'] = ltx2attentiontunerpatch.node.id

        resizeimagemasknode_2 = ResizeImageMaskNode(
            _id='717',
            resize_type='match size',
            scale_method=SCALE_METHOD,
            input=blockifymask,
            **{'resize_type.match': getimagerangefrombatch_2.out('IMAGE')},
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_2'] = resizeimagemasknode_2.node.id

        masktoimage = MaskToImage(_id='791', mask=blockifymask)
        wf.metadata.setdefault('id_map', {})['masktoimage'] = masktoimage.node.id
        setnode_26 = raw_call(wf, 'SetNode', '853',
            widget_0='audio_vocals',
            AUDIO=melbandroformersampler.out(0),
        )
        wf.metadata.setdefault('id_map', {})['setnode_26'] = setnode_26.node.id

        comfyswitchnode_2 = ComfySwitchNode(
            _id='868',
            widget_0=True,
            on_false=trimaudioduration,
            on_true=melbandroformersampler.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_2'] = comfyswitchnode_2.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='506',
            image=lazyswitchkj,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        power_lora_loader__rgthree_ = raw_call(wf, 'Power Lora Loader (rgthree)', '660',
            _outputs=('MODEL', 'CLIP'),
            model=ltx2attentiontunerpatch,
        )
        wf.metadata.setdefault('id_map', {})['power_lora_loader__rgthree_'] = power_lora_loader__rgthree_.node.id

        ltxvpreprocessmasks = LTXVPreprocessMasks(
            _id='720',
            widget_0=False,
            widget_1=False,
            widget_2='max',
            widget_3=0,
            widget_4=True,
            widget_5=0.5,
            widget_6=1,
            masks=resizeimagemasknode_2,
            vae=getnode_29.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocessmasks'] = ltxvpreprocessmasks.node.id

        getimagerangefrombatch_3 = GetImageRangeFromBatch(
            _id='775',
            widget_0=0,
            widget_1=1,
            images=masktoimage,
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch_3'] = getimagerangefrombatch_3.node.id

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            _id='866',
            audio=comfyswitchnode_2,
            audio_vae=getnode_44.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

        setnode_28 = raw_call(wf, 'SetNode', '867',
            widget_0='audio',
            AUDIO=comfyswitchnode_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_28'] = setnode_28.node.id

        setnode_14 = raw_call(wf, 'SetNode', '481',
            widget_0=WIDGET_0_7,
            MODEL=power_lora_loader__rgthree_.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_14'] = setnode_14.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='512',
            upscale_method='nearest-exact',
            keep_proportion='crop',
            divisible_by=64,
            device='cpu',
            width=getimagesizeandcount.out('WIDTH'),
            height=getimagesizeandcount.out('HEIGHT'),
            image=getimagesizeandcount.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        # Outputs
        previewimage = PreviewImage(
            _id='763',
            images=getimagerangefrombatch_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['previewimage'] = previewimage.node.id

        ltxvsetvideolatentnoisemasks = LTXVSetVideoLatentNoiseMasks(
            _id='794',
            masks=ltxvpreprocessmasks,
            samples=vaeencode,
        )
        wf.metadata.setdefault('id_map', {})['ltxvsetvideolatentnoisemasks'] = ltxvsetvideolatentnoisemasks.node.id

        setlatentnoisemask = SetLatentNoiseMask(
            _id='864',
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )
        wf.metadata.setdefault('id_map', {})['setlatentnoisemask'] = setlatentnoisemask.node.id

        ltxvaudiovideomask = LTXVAudioVideoMask(
            _id='178',
            widget_0=24,
            widget_1=0,
            widget_2=15,
            widget_3=0,
            widget_4=10000,
            widget_5='pad',
            widget_6='add',
            audio_end_time=comfymathexpression_3.out('FLOAT'),
            audio_latent=ltxvemptylatentaudio,
            video_end_time=comfymathexpression_3.out('FLOAT'),
            video_fps=getnode_25.out(0),
            video_latent=ltxvsetvideolatentnoisemasks,
            video_start_time=comfymathexpression_2.out('FLOAT'),
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

        setnode_7 = raw_call(wf, 'SetNode', '328',
            widget_0=WIDGET_0_15,
            IMAGE=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        getimagerangefrombatch = GetImageRangeFromBatch(
            _id='440',
            widget_0=0,
            widget_1=1,
            images=imageresizekjv2.out('IMAGE'),
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['getimagerangefrombatch'] = getimagerangefrombatch.node.id

        setnode_27 = raw_call(wf, 'SetNode', '863',
            widget_0=WIDGET_0_21,
            LATENT=setlatentnoisemask,
        )
        wf.metadata.setdefault('id_map', {})['setnode_27'] = setnode_27.node.id

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            _id='495',
            longer_edge=1536,
            images=getimagerangefrombatch.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge'] = resizeimagesbylongeredge.node.id

        ltxvaddlatentguide = LTXVAddLatentGuide(
            _id='799',
            widget_0=-1,
            widget_1=0.7,
            guiding_latent=vaeencode_2,
            latent=ltxvaudiovideomask.out('VIDEO_LATENT'),
            latent_idx=getimagesizeandcount_2.out('COUNT'),
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
            strength=getnode_36.out(0),
            vae=getnode_35.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaddlatentguide'] = ltxvaddlatentguide.node.id

        setnode_30 = raw_call(wf, 'SetNode', '876',
            widget_0=WIDGET_0_22,
            LATENT=ltxvaudiovideomask.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_30'] = setnode_30.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='129',
            cfg=GUIDE_STRENGTH,
            model=getnode_28.out(0),
            negative=ltxvaddlatentguide.out('NEGATIVE'),
            positive=ltxvaddlatentguide.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        setnode_6 = raw_call(wf, 'SetNode', '294',
            widget_0=WIDGET_0_9,
            IMAGE=resizeimagesbylongeredge,
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='299',
            img_compression=18,
            image=resizeimagesbylongeredge,
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            _id='730',
            widget_0=0.7,
            widget_1=False,
            image=getnode_32.out(0),
            latent=ltxvaddlatentguide.out('LATENT'),
            vae=getnode_31.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace_2'] = ltxvimgtovideoinplace_2.node.id

        setnode_22 = raw_call(wf, 'SetNode', '820',
            widget_0=WIDGET_0_19,
            CONDITIONING=ltxvaddlatentguide.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_22'] = setnode_22.node.id

        setnode_23 = raw_call(wf, 'SetNode', '821',
            widget_0=WIDGET_0_20,
            CONDITIONING=ltxvaddlatentguide.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_23'] = setnode_23.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='109',
            audio_latent=getnode_50.out(0),
            video_latent=ltxvimgtovideoinplace_2,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        setnode_5 = raw_call(wf, 'SetNode', '285',
            widget_0='compress_image',
            IMAGE=ltxvpreprocess,
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='113',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas_2,
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
            _id='810',
            latent=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            negative=getnode_38.out(0),
            positive=getnode_37.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            _id='438',
            widget_0=1,
            widget_1=False,
            image=getnode_13.out(0),
            latent=ltxvcropguides.out('LATENT'),
            vae=getnode_14.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='251',
            audio_latent=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
            video_latent=ltxvimgtovideoinplace,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

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
            _id='824',
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            negative=getnode_39.out(0),
            positive=getnode_40.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides_2'] = ltxvcropguides_2.node.id

        # Decode
        vaedecode = VAEDecode(
            _id='527',
            samples=ltxvcropguides_2.out('LATENT'),
            vae=getnode_5.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaedecode'] = vaedecode.node.id

        setnode_17 = raw_call(wf, 'SetNode', '648',
            widget_0=WIDGET_0_16,
            AUDIO=ltxvaudiovaedecode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_17'] = setnode_17.node.id

        setnode_8 = raw_call(wf, 'SetNode', '451',
            widget_0=WIDGET_0_13,
            IMAGE=vaedecode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

