# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyAudio, EmptyLTXVLatentVideo, GetImageSize, ImageBlend, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideoFFmpeg, VHS_VideoCombine

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


CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'low contrast, washed out, text, subtitles, logo, still image, still video, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 42
DEFAULT_SEED_2 = 43
DEVICE = 'cpu'
GUIDE_STRENGTH = 2.5
GUIDE_STRENGTH_2 = 0.6
GUIDE_STRENGTH_3 = 0.71
KEEP_PROPORTION = 'crop'
MODEL_NAME = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_10 = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME_11 = 'LTX\\LTX-2\\IC-Lora\\ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors'
MODEL_NAME_12 = 'yolox_l.onnx'
MODEL_NAME_13 = 'dw-ll_ucoco_384_bs5.torchscript.pt'
MODEL_NAME_14 = 'depth_anything_vitl14.pth'
MODEL_NAME_2 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_3 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_4 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_5 = 'taeltx2_3.safetensors'
MODEL_NAME_6 = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_7 = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_8 = 'gemma-3-12b-it-Q2_K.gguf'
MODEL_NAME_9 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
RESIZE_TYPE = 'scale by multiplier'
SCALE_METHOD = 'lanczos'
UPSCALE_METHOD = 'nearest-exact'
WIDGET_0 = 'clip'
WIDGET_0_10 = 'negative'
WIDGET_0_11 = 'positive_guider'
WIDGET_0_12 = 'negative_guider'
WIDGET_0_13 = 'ref_image'
WIDGET_0_14 = 't2v_mode'
WIDGET_0_15 = 'latent_down_factor'
WIDGET_0_16 = 'model_with_lora'
WIDGET_0_17 = 'vae_tiny'
WIDGET_0_18 = 'upscale_model'
WIDGET_0_19 = 'fps'
WIDGET_0_2 = 'vae'
WIDGET_0_20 = 'audio_selected'
WIDGET_0_21 = 'width'
WIDGET_0_22 = 'height'
WIDGET_0_23 = 'frames'
WIDGET_0_24 = 'enhance_prompt'
WIDGET_0_25 = 'latent_audio_selected'
WIDGET_0_26 = 'latent_audio_custom'
WIDGET_0_27 = 'audio_output'
WIDGET_0_28 = 'video_output'
WIDGET_0_29 = 'ref_blended'
WIDGET_0_3 = 'vae_audio'
WIDGET_0_30 = 'ref_pose'
WIDGET_0_31 = 'ref_selected'
WIDGET_0_32 = 'audio_custom'
WIDGET_0_33 = 'audio_original'
WIDGET_0_34 = 'latent_audio'
WIDGET_0_35 = 'ref_strength'
WIDGET_0_36 = 'audio_custom_mode'
WIDGET_0_4 = 'model'
WIDGET_0_5 = 'ref_video'
WIDGET_0_6 = 'ref_height'
WIDGET_0_7 = 'ref_width'
WIDGET_0_8 = 'ref_frames'
WIDGET_0_9 = 'positive'


MODELS = {}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node=ref('ltxvaudiovaeloader'), field='ckpt_name', default=MODEL_NAME_4),
    'prompt': InputSpec(node=ref('cliptextencode_2'), field='text', default=DEFAULT_PROMPT),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
    'image': InputSpec(node=ref('loadimage'), field='image', default='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg'),
}

READY_METADATA = ReadyMetadata.build(
    capability='dwpose_motion_transfer',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX23_audio_vae_bf16.safetensors', 'LTX23_video_vae_bf16.safetensors', 'LTX\\LTX-2\\IC-Lora\\ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'taeltx2_3.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'comfyui_controlnet_aux', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='DWPose body motion transfer',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        loadimage = LoadImage(
            _id='2004',
            image='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        # Sampling
        ksamplerselect = KSamplerSelect(
            _id='4831',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id

        randomnoise = RandomNoise(
            _id='4832',
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        manualsigmas = ManualSigmas(
            _id='5025',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        randomnoise_2 = RandomNoise(
            _id='5068',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        ksamplerselect_2 = KSamplerSelect(_id='5070', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id
        manualsigmas_2 = ManualSigmas(_id='5071', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id
        # Loaders
        vaeloader = VAELoader(_id='5125', vae_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        dualcliploader = DualCLIPLoader(
            _id='5126',
            clip_name1=MODEL_NAME_2,
            clip_name2=MODEL_NAME_3,
            type_='ltxv',
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='5127', ckpt_name=MODEL_NAME_4)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        vaeloader_2 = VAELoader(_id='5129', vae_name=MODEL_NAME_5)
        wf.metadata.setdefault('id_map', {})['vaeloader_2'] = vaeloader_2.node.id
        unetloader = UNETLoader(_id='5130', unet_name=MODEL_NAME_6)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        latentupscalemodelloader = LatentUpscaleModelLoader(
            _id='5132',
            model_name=MODEL_NAME_7,
        )
        wf.metadata.setdefault('id_map', {})['latentupscalemodelloader'] = latentupscalemodelloader.node.id

        getnode = raw_call(wf, 'GetNode', '5137', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '5139', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '5140', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        getnode_4 = raw_call(wf, 'GetNode', '5141', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '5143', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '5145', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '5146', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '5147', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '5149', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        getnode_10 = raw_call(wf, 'GetNode', '5150', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '5152', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '5156', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '5157', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '5158', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        getnode_15 = raw_call(wf, 'GetNode', '5159', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        getnode_16 = raw_call(wf, 'GetNode', '5160', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        getnode_17 = raw_call(wf, 'GetNode', '5163', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '5164', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '5169', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        getnode_20 = raw_call(wf, 'GetNode', '5170', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        getnode_21 = raw_call(wf, 'GetNode', '5171', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_21'] = getnode_21.node.id
        getnode_22 = raw_call(wf, 'GetNode', '5172', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_22'] = getnode_22.node.id
        getnode_23 = raw_call(wf, 'GetNode', '5173', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_23'] = getnode_23.node.id
        getnode_24 = raw_call(wf, 'GetNode', '5174', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_24'] = getnode_24.node.id
        getnode_25 = raw_call(wf, 'GetNode', '5176', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_25'] = getnode_25.node.id
        getnode_26 = raw_call(wf, 'GetNode', '5177', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_26'] = getnode_26.node.id
        getnode_27 = raw_call(wf, 'GetNode', '5180', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_27'] = getnode_27.node.id
        getnode_28 = raw_call(wf, 'GetNode', '5181', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_28'] = getnode_28.node.id
        getnode_29 = raw_call(wf, 'GetNode', '5184', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_29'] = getnode_29.node.id
        getnode_30 = raw_call(wf, 'GetNode', '5185', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_30'] = getnode_30.node.id
        getnode_31 = raw_call(wf, 'GetNode', '5188', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_31'] = getnode_31.node.id
        getnode_32 = raw_call(wf, 'GetNode', '5190', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_32'] = getnode_32.node.id
        getnode_33 = raw_call(wf, 'GetNode', '5191', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_33'] = getnode_33.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '5198', value=False)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '5199', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        primitiveboolean_2 = raw_call(wf, 'PrimitiveBoolean', '5201', value=False)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_2'] = primitiveboolean_2.node.id
        getnode_34 = raw_call(wf, 'GetNode', '5203', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_34'] = getnode_34.node.id
        intconstant = INTConstant(_id='5205', value=10)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='5206', value=736)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        intconstant_3 = INTConstant(_id='5207', value=1280)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        getnode_35 = raw_call(wf, 'GetNode', '5209', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_35'] = getnode_35.node.id
        getnode_36 = raw_call(wf, 'GetNode', '5210', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_36'] = getnode_36.node.id
        getnode_37 = raw_call(wf, 'GetNode', '5212', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_37'] = getnode_37.node.id
        getnode_38 = raw_call(wf, 'GetNode', '5213', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_38'] = getnode_38.node.id
        getnode_39 = raw_call(wf, 'GetNode', '5216', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_39'] = getnode_39.node.id
        getnode_40 = raw_call(wf, 'GetNode', '5217', widget_0=WIDGET_0_23)
        wf.metadata.setdefault('id_map', {})['getnode_40'] = getnode_40.node.id
        getnode_41 = raw_call(wf, 'GetNode', '5218', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_41'] = getnode_41.node.id
        # Loaders
        dualcliploadergguf = DualCLIPLoaderGGUF(
            _id='5228',
            clip_name1=MODEL_NAME_8,
            clip_name2=MODEL_NAME_3,
            type_='sdxl',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploadergguf'] = dualcliploadergguf.node.id

        unetloadergguf = UnetLoaderGGUF(_id='5229', unet_name=MODEL_NAME_9)
        wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
        getnode_42 = raw_call(wf, 'GetNode', '5235', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_42'] = getnode_42.node.id
        getnode_43 = raw_call(wf, 'GetNode', '5236', widget_0=WIDGET_0_24)
        wf.metadata.setdefault('id_map', {})['getnode_43'] = getnode_43.node.id
        primitivestringmultiline = PrimitiveStringMultiline(
            _id='5242',
            value='highly detailed, monochrime colors. Make this image come alive with fluid motion. \n\nA make boxer. \n\nHe is dancing in sync to the music ',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

        getnode_44 = raw_call(wf, 'GetNode', '5245', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_44'] = getnode_44.node.id
        getnode_45 = raw_call(wf, 'GetNode', '5248', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_45'] = getnode_45.node.id
        getnode_46 = raw_call(wf, 'GetNode', '5250', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_46'] = getnode_46.node.id
        getnode_47 = raw_call(wf, 'GetNode', '5253', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_47'] = getnode_47.node.id
        getnode_48 = raw_call(wf, 'GetNode', '5255', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_48'] = getnode_48.node.id
        getnode_49 = raw_call(wf, 'GetNode', '5257', widget_0=WIDGET_0_25)
        wf.metadata.setdefault('id_map', {})['getnode_49'] = getnode_49.node.id
        getnode_50 = raw_call(wf, 'GetNode', '5261', widget_0=WIDGET_0_26)
        wf.metadata.setdefault('id_map', {})['getnode_50'] = getnode_50.node.id
        loadaudio = LoadAudio(_id='5263', audio='(Verse).mp3')
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id
        getnode_51 = raw_call(wf, 'GetNode', '5267', widget_0=WIDGET_0_27)
        wf.metadata.setdefault('id_map', {})['getnode_51'] = getnode_51.node.id
        # Decode
        vaedecodetiled_2 = VAEDecodeTiled(
            _id='5268',
            tile_size=544,
            temporal_size=4096,
            temporal_overlap=4,
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled_2'] = vaedecodetiled_2.node.id

        getnode_52 = raw_call(wf, 'GetNode', '5269', widget_0=WIDGET_0_28)
        wf.metadata.setdefault('id_map', {})['getnode_52'] = getnode_52.node.id
        getnode_53 = raw_call(wf, 'GetNode', '5278', widget_0=WIDGET_0_29)
        wf.metadata.setdefault('id_map', {})['getnode_53'] = getnode_53.node.id
        getnode_54 = raw_call(wf, 'GetNode', '5279', widget_0=WIDGET_0_30)
        wf.metadata.setdefault('id_map', {})['getnode_54'] = getnode_54.node.id
        getnode_55 = raw_call(wf, 'GetNode', '5281', widget_0=WIDGET_0_31)
        wf.metadata.setdefault('id_map', {})['getnode_55'] = getnode_55.node.id
        getnode_56 = raw_call(wf, 'GetNode', '5285', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_56'] = getnode_56.node.id
        getnode_57 = raw_call(wf, 'GetNode', '5286', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_57'] = getnode_57.node.id
        getnode_58 = raw_call(wf, 'GetNode', '5287', widget_0=WIDGET_0_32)
        wf.metadata.setdefault('id_map', {})['getnode_58'] = getnode_58.node.id
        getnode_59 = raw_call(wf, 'GetNode', '5288', widget_0=WIDGET_0_33)
        wf.metadata.setdefault('id_map', {})['getnode_59'] = getnode_59.node.id
        getnode_60 = raw_call(wf, 'GetNode', '5291', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_60'] = getnode_60.node.id
        getnode_61 = raw_call(wf, 'GetNode', '5292', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_61'] = getnode_61.node.id
        getnode_62 = raw_call(wf, 'GetNode', '5295', widget_0=WIDGET_0_34)
        wf.metadata.setdefault('id_map', {})['getnode_62'] = getnode_62.node.id
        getnode_63 = raw_call(wf, 'GetNode', '5296', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_63'] = getnode_63.node.id
        # Inputs
        primitivefloat_2 = raw_call(wf, 'PrimitiveFloat', '5298', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_2'] = primitivefloat_2.node.id
        primitivefloat_3 = raw_call(wf, 'PrimitiveFloat', '5299', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_3'] = primitivefloat_3.node.id
        getnode_64 = raw_call(wf, 'GetNode', '5301', widget_0=WIDGET_0_35)
        wf.metadata.setdefault('id_map', {})['getnode_64'] = getnode_64.node.id
        primitiveboolean_3 = raw_call(wf, 'PrimitiveBoolean', '5303', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_3'] = primitiveboolean_3.node.id
        getnode_65 = raw_call(wf, 'GetNode', '5305', widget_0=WIDGET_0_36)
        wf.metadata.setdefault('id_map', {})['getnode_65'] = getnode_65.node.id
        getnode_66 = raw_call(wf, 'GetNode', '5306', widget_0=WIDGET_0_36)
        wf.metadata.setdefault('id_map', {})['getnode_66'] = getnode_66.node.id
        # Conditioning
        cliptextencode_2 = CLIPTextEncode(
            _id='2612',
            text=DEFAULT_PROMPT,
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='3059',
            width=getnode_13.out(0),
            height=getnode_12.out(0),
            length=getnode_14.out(0),
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='3336',
            img_compression=18,
            image=getnode_26.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        simplemath_ = raw_call(wf, 'SimpleMath+', '5034',
            _outputs=('INT', 'FLOAT'),
            widget_0='a*32',
            a=getnode_30.out(0),
        )
        wf.metadata.setdefault('id_map', {})['simplemath_'] = simplemath_.node.id

        resizeimagemasknode_2 = ResizeImageMaskNode(
            _id='5035',
            resize_type='scale longer dimension',
            scale_method=SCALE_METHOD,
            input=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_2'] = resizeimagemasknode_2.node.id

        # Conditioning
        cfgguider_2 = CFGGuider(
            _id='5069',
            cfg=GUIDE_STRENGTH,
            model=getnode_10.out(0),
            negative=getnode_22.out(0),
            positive=getnode_21.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            _id='5079',
            audio=getnode_63.out(0),
            audio_vae=getnode_8.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

        solidmask = SolidMask(
            _id='5080',
            widget_0=0,
            widget_1=512,
            widget_2=512,
            height=getnode_15.out(0),
            width=getnode_16.out(0),
        )
        wf.metadata.setdefault('id_map', {})['solidmask'] = solidmask.node.id

        setnode = raw_call(wf, 'SetNode', '5121',
            widget_0=WIDGET_0_18,
            LATENT_UPSCALE_MODEL=latentupscalemodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        setnode_2 = raw_call(wf, 'SetNode', '5122',
            widget_0=WIDGET_0_3,
            VAE=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        setnode_3 = raw_call(wf, 'SetNode', '5123', widget_0=WIDGET_0_2, VAE=vaeloader)
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id
        setnode_4 = raw_call(wf, 'SetNode', '5124',
            widget_0=WIDGET_0,
            CLIP=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        setnode_5 = raw_call(wf, 'SetNode', '5128',
            widget_0=WIDGET_0_17,
            VAE=vaeloader_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='5131',
            lora_name=MODEL_NAME_10,
            strength_model=GUIDE_STRENGTH_2,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        vhs_loadvideoffmpeg = VHS_LoadVideoFFmpeg(
            _id='5192',
            force_rate=getnode_41.out(0),
            frame_load_cap=getnode_40.out(0),
            _outputs=('IMAGE', 'MASK', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideoffmpeg'] = vhs_loadvideoffmpeg.node.id

        setnode_19 = raw_call(wf, 'SetNode', '5194',
            widget_0=WIDGET_0_22,
            INT=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_19'] = setnode_19.node.id

        setnode_20 = raw_call(wf, 'SetNode', '5195',
            widget_0=WIDGET_0_21,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_20'] = setnode_20.node.id

        setnode_21 = raw_call(wf, 'SetNode', '5196',
            widget_0=WIDGET_0_19,
            FLOAT=primitivefloat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_21'] = setnode_21.node.id

        setnode_22 = raw_call(wf, 'SetNode', '5197',
            widget_0=WIDGET_0_14,
            BOOLEAN=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['setnode_22'] = setnode_22.node.id

        setnode_23 = raw_call(wf, 'SetNode', '5200',
            widget_0=WIDGET_0_24,
            BOOLEAN=primitiveboolean_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_23'] = setnode_23.node.id

        simplecalculatorkj = SimpleCalculatorKJ(
            _id='5202',
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': intconstant, 'variables.b': getnode_34.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj'] = simplecalculatorkj.node.id

        # Outputs
        vhs_videocombine_2 = VHS_VideoCombine(
            _id='5208',
            frame_rate=getnode_35.out(0),
            audio=getnode_51.out(0),
            images=getnode_52.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_2'] = vhs_videocombine_2.node.id

        simplecalculatorkj_2 = SimpleCalculatorKJ(
            _id='5247',
            expression='a',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_44.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_2'] = simplecalculatorkj_2.node.id

        ltx2_nag = LTX2_NAG(
            _id='5251',
            model=getnode_31.out(0),
            nag_cond_audio=getnode_47.out(0),
            nag_cond_video=getnode_47.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id

        comfyswitchnode = ComfySwitchNode(
            _id='5256',
            widget_0=True,
            on_false=getnode_62.out(0),
            on_true=getnode_50.out(0),
            switch=getnode_66.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode'] = comfyswitchnode.node.id

        comfyswitchnode_3 = ComfySwitchNode(
            _id='5272',
            widget_0=False,
            on_false=getnode_54.out(0),
            on_true=getnode_53.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_3'] = comfyswitchnode_3.node.id

        simplecalculatorkj_3 = SimpleCalculatorKJ(
            _id='5284',
            expression='a / b ',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_56.out(0), 'variables.b': getnode_57.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_3'] = simplecalculatorkj_3.node.id

        simplecalculatorkj_4 = SimpleCalculatorKJ(
            _id='5290',
            expression='a / b',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_60.out(0), 'variables.b': getnode_61.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_4'] = simplecalculatorkj_4.node.id

        setnode_36 = raw_call(wf, 'SetNode', '5300',
            widget_0=WIDGET_0_35,
            FLOAT=primitivefloat_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_36'] = setnode_36.node.id

        setnode_37 = raw_call(wf, 'SetNode', '5304',
            widget_0=WIDGET_0_36,
            BOOLEAN=primitiveboolean_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_37'] = setnode_37.node.id

        ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
            _id='3159',
            bypass=getnode_28.out(0),
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoconditiononly'] = ltxvimgtovideoconditiononly.node.id

        ltxicloraloadermodelonly = LTXICLoRALoaderModelOnly(
            _id='5011',
            lora_name=MODEL_NAME_11,
            strength_model=GUIDE_STRENGTH_3,
            model=loraloadermodelonly,
            _outputs=('MODEL', 'LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['ltxicloraloadermodelonly'] = ltxicloraloadermodelonly.node.id

        setlatentnoisemask = SetLatentNoiseMask(
            _id='5081',
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )
        wf.metadata.setdefault('id_map', {})['setlatentnoisemask'] = setlatentnoisemask.node.id

        setnode_15 = raw_call(wf, 'SetNode', '5175',
            widget_0=WIDGET_0_13,
            IMAGE=resizeimagemasknode_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_15'] = setnode_15.node.id

        setnode_17 = raw_call(wf, 'SetNode', '5189',
            widget_0=WIDGET_0_4,
            MODEL=ltx2_nag,
        )
        wf.metadata.setdefault('id_map', {})['setnode_17'] = setnode_17.node.id

        setnode_18 = raw_call(wf, 'SetNode', '5193',
            widget_0=WIDGET_0_33,
            AUDIO=vhs_loadvideoffmpeg.out('AUDIO'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_18'] = setnode_18.node.id

        setnode_24 = raw_call(wf, 'SetNode', '5204',
            widget_0=WIDGET_0_23,
            INT=simplecalculatorkj.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_24'] = setnode_24.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='5211',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            device=DEVICE,
            width=getnode_37.out(0),
            height=getnode_38.out(0),
            image=vhs_loadvideoffmpeg.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        resizeimagemasknode_4 = ResizeImageMaskNode(
            _id='5241',
            resize_type=RESIZE_TYPE,
            input=resizeimagemasknode_2,
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_4'] = resizeimagemasknode_4.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='5243',
            frames_number=getnode_45.out(0),
            frame_rate=simplecalculatorkj_2.out('INT'),
            audio_vae=getnode_48.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        setnode_26 = raw_call(wf, 'SetNode', '5258',
            widget_0=WIDGET_0_25,
            LATENT=comfyswitchnode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_26'] = setnode_26.node.id

        setnode_32 = raw_call(wf, 'SetNode', '5280',
            widget_0=WIDGET_0_31,
            IMAGE=comfyswitchnode_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_32'] = setnode_32.node.id

        trimaudioduration = TrimAudioDuration(
            _id='5283',
            widget_0=0,
            widget_1=60,
            audio=loadaudio,
            duration=simplecalculatorkj_3.out('FLOAT'),
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration'] = trimaudioduration.node.id

        emptyaudio = EmptyAudio(
            _id='5289',
            widget_0=60,
            widget_1=44100,
            widget_2=2,
            duration=simplecalculatorkj_4.out('FLOAT'),
        )
        wf.metadata.setdefault('id_map', {})['emptyaudio'] = emptyaudio.node.id

        ltxaddvideoicloraguide = LTXAddVideoICLoRAGuide(
            _id='5012',
            crop=1,
            use_tiled_encode='disabled',
            tile_size=128,
            tile_overlap=32,
            strength=getnode_64.out(0),
            image=getnode_11.out(0),
            latent=ltxvimgtovideoconditiononly,
            latent_downscale_factor=getnode_29.out(0),
            negative=getnode_18.out(0),
            positive=getnode_17.out(0),
            vae=getnode_7.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxaddvideoicloraguide'] = ltxaddvideoicloraguide.node.id

        setnode_6 = raw_call(wf, 'SetNode', '5148',
            widget_0='model_iclora',
            MODEL=ltxicloraloadermodelonly.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        setnode_16 = raw_call(wf, 'SetNode', '5183',
            widget_0=WIDGET_0_15,
            FLOAT=ltxicloraloadermodelonly.out('LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_16'] = setnode_16.node.id

        resizeimagemasknode_3 = ResizeImageMaskNode(
            _id='5214',
            resize_type=RESIZE_TYPE,
            input=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_3'] = resizeimagemasknode_3.node.id

        pathchsageattentionkj = PathchSageAttentionKJ(
            _id='5231',
            sage_attention='disabled',
            model=ltxicloraloadermodelonly.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['pathchsageattentionkj'] = pathchsageattentionkj.node.id

        n_94e8f3a0_557f_4580_93a0_f762c7b0d076 = raw_call(wf, '94e8f3a0-557f-4580-93a0-f762c7b0d076', '5237',
            _1=primitivestringmultiline,
            clip=getnode_42.out(0),
            image=resizeimagemasknode_4,
        )
        wf.metadata.setdefault('id_map', {})['n_94e8f3a0_557f_4580_93a0_f762c7b0d076'] = n_94e8f3a0_557f_4580_93a0_f762c7b0d076.node.id

        setnode_27 = raw_call(wf, 'SetNode', '5260',
            widget_0=WIDGET_0_26,
            LATENT=setlatentnoisemask,
        )
        wf.metadata.setdefault('id_map', {})['setnode_27'] = setnode_27.node.id

        comfyswitchnode_4 = ComfySwitchNode(
            _id='5273',
            switch=None,
            widget_0=True,
            on_false=emptyaudio,
            on_true=getnode_59.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_4'] = comfyswitchnode_4.node.id

        setnode_33 = raw_call(wf, 'SetNode', '5282',
            widget_0=WIDGET_0_32,
            AUDIO=trimaudioduration,
        )
        wf.metadata.setdefault('id_map', {})['setnode_33'] = setnode_33.node.id

        setnode_35 = raw_call(wf, 'SetNode', '5294',
            widget_0=WIDGET_0_34,
            LATENT=ltxvemptylatentaudio,
        )
        wf.metadata.setdefault('id_map', {})['setnode_35'] = setnode_35.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='2483',
            text=n_94e8f3a0_557f_4580_93a0_f762c7b0d076.out(0),
            clip=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='4528',
            audio_latent=getnode_49.out(0),
            video_latent=ltxaddvideoicloraguide.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        cfgguider = CFGGuider(
            _id='4828',
            cfg=GUIDE_STRENGTH,
            model=getnode_9.out(0),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='5026',
            resize_type='scale shorter dimension',
            scale_method=SCALE_METHOD,
            input=resizeimagemasknode_3,
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        setnode_13 = raw_call(wf, 'SetNode', '5165',
            widget_0=WIDGET_0_11,
            CONDITIONING=ltxaddvideoicloraguide.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_13'] = setnode_13.node.id

        setnode_14 = raw_call(wf, 'SetNode', '5166',
            widget_0=WIDGET_0_12,
            CONDITIONING=ltxaddvideoicloraguide.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_14'] = setnode_14.node.id

        getimagesize_2 = GetImageSize(
            _id='5219',
            image=resizeimagemasknode_3,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize_2'] = getimagesize_2.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='5232',
            model=pathchsageattentionkj,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        comfyswitchnode_5 = ComfySwitchNode(
            _id='5274',
            widget_0=False,
            on_false=comfyswitchnode_4,
            on_true=getnode_58.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_5'] = comfyswitchnode_5.node.id

        ltxvconditioning = LTXVConditioning(
            _id='1241',
            frame_rate=getnode_39.out(0),
            negative=cliptextencode_2,
            positive=cliptextencode,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='4829',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        dwpreprocessor = raw_call(wf, 'DWPreprocessor', '4986',
            detect_hand='enable',
            detect_body='enable',
            detect_face='enable',
            resolution=512,
            bbox_detector=MODEL_NAME_12,
            pose_estimator=MODEL_NAME_13,
            scale_stick_for_xinsr_cn='disable',
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['dwpreprocessor'] = dwpreprocessor.node.id

        depthanythingpreprocessor = raw_call(wf, 'DepthAnythingPreprocessor', '5114',
            widget_0=MODEL_NAME_14,
            widget_1=512,
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['depthanythingpreprocessor'] = depthanythingpreprocessor.node.id

        imageresizekjv2_2 = ImageResizeKJv2(
            _id='5221',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            device=DEVICE,
            width=getimagesize_2.out('WIDTH'),
            height=getimagesize_2.out('HEIGHT'),
            divisible_by=simplemath_.out('INT'),
            image=getnode_55.out(0),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_2'] = imageresizekjv2_2.node.id

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            _id='5233',
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['ltx2attentiontunerpatch'] = ltx2attentiontunerpatch.node.id

        setnode_34 = raw_call(wf, 'SetNode', '5293',
            widget_0=WIDGET_0_20,
            AUDIO=comfyswitchnode_5,
        )
        wf.metadata.setdefault('id_map', {})['setnode_34'] = setnode_34.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='4845',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        getimagesize = GetImageSize(
            _id='5029',
            image=imageresizekjv2_2.out('IMAGE'),
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        imageblend = ImageBlend(
            _id='5115',
            widget_0=0.5,
            widget_1='multiply',
            image1=dwpreprocessor,
            image2=depthanythingpreprocessor.out(0),
        )
        wf.metadata.setdefault('id_map', {})['imageblend'] = imageblend.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='5120',
            images=imageresizekjv2_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        setnode_7 = raw_call(wf, 'SetNode', '5151',
            widget_0=WIDGET_0_5,
            IMAGE=imageresizekjv2_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        setnode_11 = raw_call(wf, 'SetNode', '5161',
            widget_0=WIDGET_0_9,
            CONDITIONING=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id

        setnode_12 = raw_call(wf, 'SetNode', '5162',
            widget_0=WIDGET_0_10,
            CONDITIONING=ltxvconditioning.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_12'] = setnode_12.node.id

        power_lora_loader__rgthree_ = raw_call(wf, 'Power Lora Loader (rgthree)', '5275',
            _outputs=('MODEL', 'CLIP'),
            model=ltx2attentiontunerpatch,
        )
        wf.metadata.setdefault('id_map', {})['power_lora_loader__rgthree_'] = power_lora_loader__rgthree_.node.id

        setnode_31 = raw_call(wf, 'SetNode', '5277',
            widget_0=WIDGET_0_30,
            IMAGE=dwpreprocessor,
        )
        wf.metadata.setdefault('id_map', {})['setnode_31'] = setnode_31.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='5013',
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            negative=getnode_20.out(0),
            positive=getnode_19.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        setnode_8 = raw_call(wf, 'SetNode', '5153',
            widget_0=WIDGET_0_6,
            INT=getimagesize.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        setnode_9 = raw_call(wf, 'SetNode', '5154',
            widget_0=WIDGET_0_7,
            INT=getimagesize.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        setnode_10 = raw_call(wf, 'SetNode', '5155',
            widget_0=WIDGET_0_8,
            INT=getimagesize.out('BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        setnode_25 = raw_call(wf, 'SetNode', '5234',
            widget_0=WIDGET_0_16,
            MODEL=power_lora_loader__rgthree_.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_25'] = setnode_25.node.id

        setnode_30 = raw_call(wf, 'SetNode', '5276',
            widget_0=WIDGET_0_29,
            IMAGE=imageblend,
        )
        wf.metadata.setdefault('id_map', {})['setnode_30'] = setnode_30.node.id

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            _id='5067',
            widget_0=0.7,
            widget_1=False,
            bypass=getnode_27.out(0),
            image=getnode_25.out(0),
            latent=ltxvcropguides.out('LATENT'),
            vae=getnode_4.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='5072',
            audio_latent=ltxvseparateavlatent.out('AUDIO_LATENT'),
            video_latent=ltxvimgtovideoinplace,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        # Sampling
        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='5073',
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='5074',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='5076',
            audio_vae=getnode_6.out(0),
            samples=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        ltxvcropguides_2 = LTXVCropGuides(
            _id='5082',
            latent=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            negative=getnode_23.out(0),
            positive=getnode_24.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides_2'] = ltxvcropguides_2.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            _id='5075',
            tile_size=544,
            temporal_size=4096,
            temporal_overlap=4,
            samples=ltxvcropguides_2.out('LATENT'),
            vae=getnode_5.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id

        comfyswitchnode_2 = ComfySwitchNode(
            _id='5264',
            widget_0=True,
            on_false=ltxvaudiovaedecode,
            on_true=getnode_36.out(0),
            switch=getnode_65.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_2'] = comfyswitchnode_2.node.id

        setnode_28 = raw_call(wf, 'SetNode', '5265',
            widget_0=WIDGET_0_27,
            AUDIO=comfyswitchnode_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_28'] = setnode_28.node.id

        setnode_29 = raw_call(wf, 'SetNode', '5266',
            widget_0=WIDGET_0_28,
            IMAGE=vaedecodetiled,
        )
        wf.metadata.setdefault('id_map', {})['setnode_29'] = setnode_29.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

