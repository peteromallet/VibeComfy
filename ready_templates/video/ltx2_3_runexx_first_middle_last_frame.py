# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfyMathExpression, DualCLIPLoader, EmptyLTXVLatentVideo, KSamplerSelect, LTXVAddGuideMulti, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImagesByLongerEdge, SamplerCustomAdvanced, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, PathchSageAttentionKJ, SimpleCalculatorKJ
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine

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
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
DEVICE = 'cpu'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
KEEP_PROPORTION = 'crop'
MODEL_NAME = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_10 = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
MODEL_NAME_2 = 'taeltx2_3.safetensors'
MODEL_NAME_3 = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_4 = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_5 = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_6 = 'gemma-3-12b-it-Q2_K.gguf'
MODEL_NAME_7 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_8 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_9 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
TYPE = 'ltxv'
UPSCALE_METHOD = 'lanczos'
WIDGET_0 = 'width'
WIDGET_0_10 = 'vae_tiny'
WIDGET_0_11 = 'negative'
WIDGET_0_12 = 'model_nag'
WIDGET_0_13 = 'final_video'
WIDGET_0_14 = 'final_audio'
WIDGET_0_15 = 'lastframe'
WIDGET_0_16 = 'firstframe'
WIDGET_0_17 = 'enhance_prompt'
WIDGET_0_18 = 'negative_guider'
WIDGET_0_19 = 'positive_guider'
WIDGET_0_2 = 'height'
WIDGET_0_20 = 'negative_guider2'
WIDGET_0_21 = 'positive_guider2'
WIDGET_0_22 = 'middleframe'
WIDGET_0_23 = 'firstframe_strength'
WIDGET_0_24 = 'lastframe_strength'
WIDGET_0_25 = 'middleframe_strength'
WIDGET_0_26 = 'latent_audio'
WIDGET_0_27 = 'a/2'
WIDGET_0_3 = 'fps'
WIDGET_0_4 = 'vae_audio'
WIDGET_0_5 = 'vae'
WIDGET_0_6 = 'model'
WIDGET_0_7 = 'clip'
WIDGET_0_8 = 'frames'
WIDGET_0_9 = 'upscale_model'


MODELS = {
    'ltx_2_3_text_projection_bf16': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors', hf_revision='main', subdir='text_encoders'),
    'ltx23_video_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors', hf_revision='main', subdir='vae'),
    'ltx23_audio_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', hf_revision='main', subdir='checkpoints'),
    'taeltx2_3': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors', hf_revision='main', subdir='vae'),
    'ltx_2_3_22b_distilled_1_1_transformer_only_fp8_scaled': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', hf_revision='main', subdir='diffusion_models'),
    'ltx_v2_ltx_2_3_22b_distilled_1_1_lora_dynamic_fro09_avg_rank_111_bf16': ModelAsset(filename='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', hf_revision='main', subdir='loras'),
}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node=ref('ltxvaudiovaeloader'), field='ckpt_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=True),
    'image': InputSpec(node=ref('loadimage'), field='image', default='sodacan_01.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='sodacan_01.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_middle_last_frame_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='multi-anchor image-guided video',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Sampling
        ksamplerselect = KSamplerSelect(_id='1', sampler_name='euler_ancestral_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
        ksamplerselect_2 = KSamplerSelect(_id='4', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id
        manualsigmas = ManualSigmas(_id='5', sigmas='0.909375, 0.725, 0.421875, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id
        randomnoise = RandomNoise(
            _id='14',
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        randomnoise_2 = RandomNoise(
            _id='15',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        # Inputs
        loadimage = LoadImage(
            _id='45',
            image='sodacan_01.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        loadimage_2 = LoadImage(
            _id='47',
            image='image (11).png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        getnode = raw_call(wf, 'GetNode', '70', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '71', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '91', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        getnode_4 = raw_call(wf, 'GetNode', '93', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '117', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '120', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '122', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '124', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '127', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        getnode_10 = raw_call(wf, 'GetNode', '128', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '129', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '133', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '137', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '147', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        getnode_15 = raw_call(wf, 'GetNode', '148', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='175', ckpt_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        # Loaders
        vaeloader = VAELoader(_id='180', vae_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        vaeloader_2 = VAELoader(_id='181', vae_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['vaeloader_2'] = vaeloader_2.node.id
        latentupscalemodelloader = LatentUpscaleModelLoader(
            _id='182',
            model_name=MODEL_NAME_4,
        )
        wf.metadata.setdefault('id_map', {})['latentupscalemodelloader'] = latentupscalemodelloader.node.id

        unetloader = UNETLoader(_id='187', unet_name=MODEL_NAME_5)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        dualcliploadergguf = DualCLIPLoaderGGUF(
            _id='189',
            clip_name1=MODEL_NAME_6,
            clip_name2=MODEL_NAME_7,
            type_=TYPE,
        )
        wf.metadata.setdefault('id_map', {})['dualcliploadergguf'] = dualcliploadergguf.node.id

        dualcliploader = DualCLIPLoader(
            _id='190',
            clip_name1=MODEL_NAME_8,
            clip_name2=MODEL_NAME_7,
            type_=TYPE,
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        unetloadergguf = UnetLoaderGGUF(_id='191', unet_name=MODEL_NAME_9)
        wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
        getnode_16 = raw_call(wf, 'GetNode', '193', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        getnode_17 = raw_call(wf, 'GetNode', '196', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '200', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '201', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        getnode_20 = raw_call(wf, 'GetNode', '203', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        getnode_21 = raw_call(wf, 'GetNode', '204', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_21'] = getnode_21.node.id
        manualsigmas_2 = ManualSigmas(
            _id='215',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id

        manualsigmas_3 = ManualSigmas(_id='216', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas_3'] = manualsigmas_3.node.id
        getnode_22 = raw_call(wf, 'GetNode', '219', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_22'] = getnode_22.node.id
        getnode_23 = raw_call(wf, 'GetNode', '220', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_23'] = getnode_23.node.id
        getnode_24 = raw_call(wf, 'GetNode', '224', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_24'] = getnode_24.node.id
        getnode_25 = raw_call(wf, 'GetNode', '225', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_25'] = getnode_25.node.id
        getnode_26 = raw_call(wf, 'GetNode', '2067', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_26'] = getnode_26.node.id
        getnode_27 = raw_call(wf, 'GetNode', '2068', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_27'] = getnode_27.node.id
        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '2076', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        intconstant = INTConstant(_id='2078', value=15)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='2079', value=720)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        intconstant_3 = INTConstant(_id='2080', value=1280)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '2082', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        primitivestringmultiline = PrimitiveStringMultiline(
            _id='2103',
            value='Make this come alive with cinematic motion, smooth animation. \n\nThe scene starts with a close up of an LTX soda can with ic cubes around it. \n\nAll of a suddent an arm comes into frame and grabs the soda can, and lifts the soda can up. \n\nCamera pans up smoothly to show a woman holding the soda can. She talks with a soft British voice, and she says :" An LTX a day, keeps the doctor away". Then she laghts, and finally she drinks from the soda can. ',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

        getnode_28 = raw_call(wf, 'GetNode', '2106', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_28'] = getnode_28.node.id
        primitivefloat_2 = raw_call(wf, 'PrimitiveFloat', '2108', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_2'] = primitivefloat_2.node.id
        primitivefloat_3 = raw_call(wf, 'PrimitiveFloat', '2110', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_3'] = primitivefloat_3.node.id
        getnode_29 = raw_call(wf, 'GetNode', '2154', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_29'] = getnode_29.node.id
        getnode_30 = raw_call(wf, 'GetNode', '2155', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_30'] = getnode_30.node.id
        getnode_31 = raw_call(wf, 'GetNode', '2163', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_31'] = getnode_31.node.id
        getnode_32 = raw_call(wf, 'GetNode', '2166', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_32'] = getnode_32.node.id
        getnode_33 = raw_call(wf, 'GetNode', '2167', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_33'] = getnode_33.node.id
        loadimage_3 = LoadImage(
            _id='2172',
            image='image (12).png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_3'] = loadimage_3.node.id

        getnode_34 = raw_call(wf, 'GetNode', '2173', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_34'] = getnode_34.node.id
        getnode_35 = raw_call(wf, 'GetNode', '2175', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_35'] = getnode_35.node.id
        getnode_36 = raw_call(wf, 'GetNode', '2187', widget_0=WIDGET_0_23)
        wf.metadata.setdefault('id_map', {})['getnode_36'] = getnode_36.node.id
        getnode_37 = raw_call(wf, 'GetNode', '2188', widget_0=WIDGET_0_24)
        wf.metadata.setdefault('id_map', {})['getnode_37'] = getnode_37.node.id
        getnode_38 = raw_call(wf, 'GetNode', '2189', widget_0=WIDGET_0_25)
        wf.metadata.setdefault('id_map', {})['getnode_38'] = getnode_38.node.id
        getnode_39 = raw_call(wf, 'GetNode', '2214', widget_0=WIDGET_0_26)
        wf.metadata.setdefault('id_map', {})['getnode_39'] = getnode_39.node.id
        getnode_40 = raw_call(wf, 'GetNode', '2220', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_40'] = getnode_40.node.id
        getnode_41 = raw_call(wf, 'GetNode', '2226', widget_0=WIDGET_0_24)
        wf.metadata.setdefault('id_map', {})['getnode_41'] = getnode_41.node.id
        getnode_42 = raw_call(wf, 'GetNode', '2255', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_42'] = getnode_42.node.id
        getnode_43 = raw_call(wf, 'GetNode', '2259', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_43'] = getnode_43.node.id
        getnode_44 = raw_call(wf, 'GetNode', '2260', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_44'] = getnode_44.node.id
        getnode_45 = raw_call(wf, 'GetNode', '2276', widget_0=WIDGET_0_23)
        wf.metadata.setdefault('id_map', {})['getnode_45'] = getnode_45.node.id
        primitivefloat_4 = raw_call(wf, 'PrimitiveFloat', '2278', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_4'] = primitivefloat_4.node.id
        getnode_46 = raw_call(wf, 'GetNode', '2279', widget_0=WIDGET_0_23)
        wf.metadata.setdefault('id_map', {})['getnode_46'] = getnode_46.node.id
        getnode_47 = raw_call(wf, 'GetNode', '2280', widget_0=WIDGET_0_24)
        wf.metadata.setdefault('id_map', {})['getnode_47'] = getnode_47.node.id
        getnode_48 = raw_call(wf, 'GetNode', '2281', widget_0=WIDGET_0_25)
        wf.metadata.setdefault('id_map', {})['getnode_48'] = getnode_48.node.id
        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='11',
            text=DEFAULT_PROMPT,
            clip=getnode_8.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        cliptextencode_2 = CLIPTextEncode(
            _id='16',
            text=primitivestringmultiline,
            clip=getnode_8.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='43',
            filename_prefix='reigh_vibecomfy_ltx_first_middle_last',
            format='video/h264-mp4',
            frame_rate=getnode_13.out(0),
            images=getnode_20.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='44',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=32,
            device=DEVICE,
            width=getnode.out(0),
            height=getnode_2.out(0),
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='50',
            img_compression=18,
            image=getnode_24.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        simplecalculatorkj = SimpleCalculatorKJ(
            _id='92',
            expression='a',
            a=getnode_3.out(0),
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj'] = simplecalculatorkj.node.id

        setnode_5 = raw_call(wf, 'SetNode', '171',
            widget_0=WIDGET_0_9,
            LATENT_UPSCALE_MODEL=latentupscalemodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        setnode_6 = raw_call(wf, 'SetNode', '172',
            widget_0=WIDGET_0_4,
            VAE=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        setnode_7 = raw_call(wf, 'SetNode', '173', widget_0=WIDGET_0_5, VAE=vaeloader_2)
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id
        setnode_8 = raw_call(wf, 'SetNode', '177', widget_0=WIDGET_0_10, VAE=vaeloader)
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id
        loraloadermodelonly = LoraLoaderModelOnly(
            _id='186',
            lora_name=MODEL_NAME_10,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        setnode_9 = raw_call(wf, 'SetNode', '188',
            widget_0=WIDGET_0_7,
            CLIP=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        ltx2_nag = LTX2_NAG(
            _id='197',
            model=getnode_7.out(0),
            nag_cond_audio=getnode_17.out(0),
            nag_cond_video=getnode_17.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id

        setnode_13 = raw_call(wf, 'SetNode', '2072',
            widget_0=WIDGET_0_2,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_13'] = setnode_13.node.id

        setnode_14 = raw_call(wf, 'SetNode', '2073',
            widget_0=WIDGET_0,
            INT=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_14'] = setnode_14.node.id

        setnode_15 = raw_call(wf, 'SetNode', '2074',
            widget_0=WIDGET_0_3,
            FLOAT=primitivefloat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_15'] = setnode_15.node.id

        simplecalculatorkj_2 = SimpleCalculatorKJ(
            _id='2077',
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            a=intconstant,
            b=primitivefloat,
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_2'] = simplecalculatorkj_2.node.id

        setnode_17 = raw_call(wf, 'SetNode', '2081',
            widget_0=WIDGET_0_17,
            BOOLEAN=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['setnode_17'] = setnode_17.node.id

        ltxvpreprocess_2 = LTXVPreprocess(
            _id='2084',
            img_compression=18,
            image=getnode_25.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess_2'] = ltxvpreprocess_2.node.id

        setnode_18 = raw_call(wf, 'SetNode', '2112',
            widget_0=WIDGET_0_23,
            FLOAT=primitivefloat_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_18'] = setnode_18.node.id

        setnode_19 = raw_call(wf, 'SetNode', '2113',
            widget_0=WIDGET_0_24,
            FLOAT=primitivefloat_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_19'] = setnode_19.node.id

        ltxvpreprocess_3 = LTXVPreprocess(
            _id='2174',
            img_compression=18,
            image=getnode_34.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess_3'] = ltxvpreprocess_3.node.id

        comfymathexpression = ComfyMathExpression(
            _id='2191',
            widget_0=WIDGET_0_27,
            _outputs=('FLOAT', 'INT'),
            **{'values.a': getnode_23.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['comfymathexpression'] = comfymathexpression.node.id

        comfymathexpression_2 = ComfyMathExpression(
            _id='2192',
            widget_0=WIDGET_0_27,
            _outputs=('FLOAT', 'INT'),
            **{'values.a': getnode_22.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['comfymathexpression_2'] = comfymathexpression_2.node.id

        simplecalculatorkj_3 = SimpleCalculatorKJ(
            _id='2216',
            expression='a/2',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_35.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_3'] = simplecalculatorkj_3.node.id

        setnode_31 = raw_call(wf, 'SetNode', '2277',
            widget_0=WIDGET_0_25,
            FLOAT=primitivefloat_4,
        )
        wf.metadata.setdefault('id_map', {})['setnode_31'] = setnode_31.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='9',
            frames_number=getnode_9.out(0),
            frame_rate=simplecalculatorkj.out('INT'),
            audio_vae=getnode_5.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        ltxvconditioning = LTXVConditioning(
            _id='10',
            frame_rate=getnode_4.out(0),
            negative=cliptextencode,
            positive=cliptextencode_2,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='32',
            width=comfymathexpression.out('INT'),
            height=comfymathexpression_2.out('INT'),
            length=getnode_9.out(0),
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        imageresizekjv2_2 = ImageResizeKJv2(
            _id='48',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=32,
            device=DEVICE,
            width=imageresizekjv2.out('WIDTH'),
            height=imageresizekjv2.out('HEIGHT'),
            image=loadimage_2.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_2'] = imageresizekjv2_2.node.id

        setnode_11 = raw_call(wf, 'SetNode', '199',
            widget_0=WIDGET_0_12,
            MODEL=ltx2_nag,
        )
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id

        pathchsageattentionkj = PathchSageAttentionKJ(
            _id='226',
            sage_attention='disabled',
            model=loraloadermodelonly,
        )
        wf.metadata.setdefault('id_map', {})['pathchsageattentionkj'] = pathchsageattentionkj.node.id

        setnode_16 = raw_call(wf, 'SetNode', '2075',
            widget_0=WIDGET_0_8,
            INT=simplecalculatorkj_2.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_16'] = setnode_16.node.id

        resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
            _id='2083',
            longer_edge=1536,
            images=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge_2'] = resizeimagesbylongeredge_2.node.id

        setnode_23 = raw_call(wf, 'SetNode', '2185',
            widget_0='middleframe_count',
            INT=simplecalculatorkj_3.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_23'] = setnode_23.node.id

        setnode_25 = raw_call(wf, 'SetNode', '2217',
            widget_0='firstframe_resized',
            IMAGE=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_25'] = setnode_25.node.id

        setnode_30 = raw_call(wf, 'SetNode', '2233',
            widget_0=WIDGET_0_11,
            CONDITIONING=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_30'] = setnode_30.node.id

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            _id='49',
            longer_edge=1536,
            images=imageresizekjv2_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge'] = resizeimagesbylongeredge.node.id

        setnode = raw_call(wf, 'SetNode', '75',
            widget_0=WIDGET_0_16,
            IMAGE=resizeimagesbylongeredge_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='228',
            model=pathchsageattentionkj,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        imageresizekjv2_3 = ImageResizeKJv2(
            _id='2171',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=32,
            device=DEVICE,
            width=imageresizekjv2_2.out('WIDTH'),
            height=imageresizekjv2_2.out('HEIGHT'),
            image=loadimage_3.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_3'] = imageresizekjv2_3.node.id

        setnode_24 = raw_call(wf, 'SetNode', '2215',
            widget_0=WIDGET_0_26,
            LATENT=ltxvemptylatentaudio,
        )
        wf.metadata.setdefault('id_map', {})['setnode_24'] = setnode_24.node.id

        setnode_26 = raw_call(wf, 'SetNode', '2218',
            widget_0='middleframe_resized',
            IMAGE=imageresizekjv2_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_26'] = setnode_26.node.id

        ltxvaddguidemulti_2 = LTXVAddGuideMulti(
            _id='2221',
            num_guides='3',
            latent=emptyltxvlatentvideo,
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
            vae=getnode_42.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
            **{'num_guides.frame_idx_1': 0, 'num_guides.frame_idx_3': -1, 'num_guides.frame_idx_2': simplecalculatorkj_3.out('INT'), 'num_guides.image_1': ltxvpreprocess_2, 'num_guides.image_2': ltxvpreprocess_3, 'num_guides.image_3': ltxvpreprocess, 'num_guides.strength_1': getnode_46.out(0), 'num_guides.strength_2': getnode_48.out(0), 'num_guides.strength_3': getnode_47.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['ltxvaddguidemulti_2'] = ltxvaddguidemulti_2.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='24',
            audio_latent=getnode_39.out(0),
            video_latent=ltxvaddguidemulti_2.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        # Conditioning
        cfgguider_2 = CFGGuider(
            _id='36',
            cfg=GUIDE_STRENGTH_2,
            model=getnode_18.out(0),
            negative=ltxvaddguidemulti_2.out('NEGATIVE'),
            positive=ltxvaddguidemulti_2.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        setnode_2 = raw_call(wf, 'SetNode', '78',
            widget_0=WIDGET_0_22,
            IMAGE=resizeimagesbylongeredge,
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            _id='229',
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['ltx2attentiontunerpatch'] = ltx2attentiontunerpatch.node.id

        resizeimagesbylongeredge_3 = ResizeImagesByLongerEdge(
            _id='2168',
            longer_edge=1536,
            images=imageresizekjv2_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge_3'] = resizeimagesbylongeredge_3.node.id

        setnode_27 = raw_call(wf, 'SetNode', '2219',
            widget_0='lastframe_resized',
            IMAGE=imageresizekjv2_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_27'] = setnode_27.node.id

        setnode_28 = raw_call(wf, 'SetNode', '2223',
            widget_0=WIDGET_0_19,
            CONDITIONING=ltxvaddguidemulti_2.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_28'] = setnode_28.node.id

        setnode_29 = raw_call(wf, 'SetNode', '2224',
            widget_0=WIDGET_0_18,
            CONDITIONING=ltxvaddguidemulti_2.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_29'] = setnode_29.node.id

        ltxvscheduler = LTXVScheduler(_id='2', steps=1, latent=ltxvconcatavlatent)
        wf.metadata.setdefault('id_map', {})['ltxvscheduler'] = ltxvscheduler.node.id
        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='13',
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect,
            sigmas=manualsigmas_2,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        power_lora_loader__rgthree_ = raw_call(wf, 'Power Lora Loader (rgthree)', '2107',
            _outputs=('MODEL', 'CLIP'),
            model=ltx2attentiontunerpatch,
        )
        wf.metadata.setdefault('id_map', {})['power_lora_loader__rgthree_'] = power_lora_loader__rgthree_.node.id

        setnode_22 = raw_call(wf, 'SetNode', '2169',
            widget_0=WIDGET_0_15,
            IMAGE=resizeimagesbylongeredge_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_22'] = setnode_22.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='18',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        setnode_10 = raw_call(wf, 'SetNode', '192',
            widget_0=WIDGET_0_6,
            MODEL=power_lora_loader__rgthree_.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        setnode_12 = raw_call(wf, 'SetNode', '230',
            widget_0='model_with_lora',
            MODEL=power_lora_loader__rgthree_.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_12'] = setnode_12.node.id

        ltxvcropguides_2 = LTXVCropGuides(
            _id='2222',
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            negative=getnode_43.out(0),
            positive=getnode_44.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides_2'] = ltxvcropguides_2.node.id

        ltxvaddguidemulti = LTXVAddGuideMulti(
            _id='2182',
            num_guides='2',
            latent=ltxvcropguides_2.out('LATENT'),
            negative=ltxvcropguides_2.out('NEGATIVE'),
            positive=ltxvcropguides_2.out('LATENT'),
            vae=getnode_30.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
            **{'num_guides.frame_idx_1': 0, 'num_guides.frame_idx_2': -1, 'num_guides.image_1': getnode_40.out(0), 'num_guides.image_2': getnode_28.out(0), 'num_guides.strength_1': getnode_45.out(0), 'num_guides.strength_2': getnode_41.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['ltxvaddguidemulti'] = ltxvaddguidemulti.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='8',
            cfg=GUIDE_STRENGTH_2,
            model=getnode_19.out(0),
            negative=ltxvaddguidemulti.out('NEGATIVE'),
            positive=ltxvaddguidemulti.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='34',
            audio_latent=ltxvseparateavlatent.out('AUDIO_LATENT'),
            video_latent=ltxvaddguidemulti.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        setnode_20 = raw_call(wf, 'SetNode', '2164',
            widget_0=WIDGET_0_21,
            CONDITIONING=ltxvaddguidemulti.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_20'] = setnode_20.node.id

        setnode_21 = raw_call(wf, 'SetNode', '2165',
            widget_0=WIDGET_0_20,
            CONDITIONING=ltxvaddguidemulti.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_21'] = setnode_21.node.id

        # Sampling
        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='21',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_3,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='146',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='150',
            audio_vae=getnode_15.out(0),
            samples=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='2156',
            latent=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            negative=getnode_32.out(0),
            positive=getnode_33.out(0),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            _id='149',
            temporal_size=4096,
            samples=ltxvcropguides.out('LATENT'),
            vae=getnode_14.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id

        setnode_4 = raw_call(wf, 'SetNode', '154',
            widget_0=WIDGET_0_14,
            AUDIO=ltxvaudiovaedecode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        setnode_3 = raw_call(wf, 'SetNode', '153',
            widget_0=WIDGET_0_13,
            IMAGE=vaedecodetiled,
        )
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='reigh_vibecomfy_ltx_first_middle_last')

