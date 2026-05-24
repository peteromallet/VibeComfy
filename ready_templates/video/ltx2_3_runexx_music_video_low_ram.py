# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TrimAudioDuration, UNETLoader, VAEDecode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LoadVideosFromFolder, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
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
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
MODEL_NAME = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_10 = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_11 = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME_2 = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_3 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_4 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_6 = 'taeltx2_3.safetensors'
MODEL_NAME_7 = 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_8 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
MODEL_NAME_9 = 'gemma-3-12b-it-Q2_K.gguf'
WIDGET_0 = 'vae'
WIDGET_0_10 = 'enhance_prompt'
WIDGET_0_11 = 'ref_image'
WIDGET_0_12 = 'upscale_model'
WIDGET_0_13 = 'negative_base'
WIDGET_0_14 = 'positive_base'
WIDGET_0_15 = 'vae_tiny'
WIDGET_0_16 = 'model_with_lora'
WIDGET_0_17 = 'model'
WIDGET_0_18 = 'width_downscaled'
WIDGET_0_19 = 'height_downscaled'
WIDGET_0_2 = 'audio_original'
WIDGET_0_20 = 'image_strength'
WIDGET_0_21 = 'initial_frames_count'
WIDGET_0_22 = 'foldername'
WIDGET_0_23 = 'temp_name'
WIDGET_0_24 = 'final_frames'
WIDGET_0_25 = 'MusicVideo'
WIDGET_0_26 = 'output\\MusicVideo'
WIDGET_0_3 = 'height'
WIDGET_0_4 = 'vae_audio'
WIDGET_0_5 = 'width'
WIDGET_0_6 = 'clip'
WIDGET_0_7 = 'frames'
WIDGET_0_8 = 'fps'
WIDGET_0_9 = 'window_sec_01'
WIDGET_1 = ''
WIDGET_2 = '\\'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('latentupscalemodelloader'), field='model_name', default=MODEL_NAME_2),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode_2'), field='text', default=DEFAULT_PROMPT),
    'steps': InputSpec(node=ref('basicscheduler'), field='steps', default=4),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
    'image': InputSpec(node=ref('loadimage'), field='image', default='download (8).png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='download (8).png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='music_video_multiscene',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX23_audio_vae_bf16.safetensors', 'LTX23_video_vae_bf16.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'taeltx2_3.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='low-RAM multi-scene music video',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        getnode = raw_call(wf, 'GetNode', '236', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '413', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        # Inputs
        loadimage = LoadImage(
            _id='444',
            image='download (8).png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        getnode_3 = raw_call(wf, 'GetNode', '582', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        intconstant = INTConstant(_id='1527', value=1000)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        # Loaders
        vaeloader = VAELoader(_id='1559', vae_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        latentupscalemodelloader = LatentUpscaleModelLoader(
            _id='1561',
            model_name=MODEL_NAME_2,
        )
        wf.metadata.setdefault('id_map', {})['latentupscalemodelloader'] = latentupscalemodelloader.node.id

        dualcliploader = DualCLIPLoader(
            _id='1562',
            clip_name1=MODEL_NAME_3,
            clip_name2=MODEL_NAME_4,
            type_='ltxv',
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='1567', ckpt_name=MODEL_NAME_5)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        vaeloader_2 = VAELoader(_id='1569', vae_name=MODEL_NAME_6)
        wf.metadata.setdefault('id_map', {})['vaeloader_2'] = vaeloader_2.node.id
        unetloader = UNETLoader(_id='1570', unet_name=MODEL_NAME_7)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        unetloadergguf = UnetLoaderGGUF(_id='1571', unet_name=MODEL_NAME_8)
        wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
        dualcliploadergguf = DualCLIPLoaderGGUF(
            _id='1573',
            clip_name1=MODEL_NAME_9,
            clip_name2=MODEL_NAME_4,
            type_='sdxl',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploadergguf'] = dualcliploadergguf.node.id

        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '1586', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        intconstant_2 = INTConstant(_id='1591', value=480)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        loadaudio = LoadAudio(_id='1594', audio='ComfyUI_00152_.mp3')
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id
        getnode_4 = raw_call(wf, 'GetNode', '1595', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '1597', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        melbandroformermodelloader = raw_call(wf, 'MelBandRoFormerModelLoader', '1600',
            widget_0=MODEL_NAME_10,
        )
        wf.metadata.setdefault('id_map', {})['melbandroformermodelloader'] = melbandroformermodelloader.node.id

        getnode_6 = raw_call(wf, 'GetNode', '1601', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        intconstant_3 = INTConstant(_id='1606', value=832)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        getnode_7 = raw_call(wf, 'GetNode', '1622', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        primitivestringmultiline = PrimitiveStringMultiline(
            _id='1624',
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

        getnode_8 = raw_call(wf, 'GetNode', '1628', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '1629', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        getnode_10 = raw_call(wf, 'GetNode', '1635', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '1636', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '1654', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        primitivefloat_2 = raw_call(wf, 'PrimitiveFloat', '1722', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_2'] = primitivefloat_2.node.id
        primitivestringmultiline_2 = PrimitiveStringMultiline(
            _id='1805',
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline_2'] = primitivestringmultiline_2.node.id

        primitivefloat_3 = raw_call(wf, 'PrimitiveFloat', '1997', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_3'] = primitivefloat_3.node.id
        primitivefloat_4 = raw_call(wf, 'PrimitiveFloat', '2012', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_4'] = primitivefloat_4.node.id
        getnode_13 = raw_call(wf, 'GetNode', '2110', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '2111', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        getnode_15 = raw_call(wf, 'GetNode', '2113', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '2116', value=False)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        getnode_16 = raw_call(wf, 'GetNode', '2151', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        getnode_17 = raw_call(wf, 'GetNode', '2152', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '2154', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '2155', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        getnode_20 = raw_call(wf, 'GetNode', '2157', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        getnode_21 = raw_call(wf, 'GetNode', '2161', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_21'] = getnode_21.node.id
        getnode_22 = raw_call(wf, 'GetNode', '2162', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_22'] = getnode_22.node.id
        getnode_23 = raw_call(wf, 'GetNode', '2164', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_23'] = getnode_23.node.id
        getnode_24 = raw_call(wf, 'GetNode', '2165', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_24'] = getnode_24.node.id
        getnode_25 = raw_call(wf, 'GetNode', '2166', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_25'] = getnode_25.node.id
        getnode_26 = raw_call(wf, 'GetNode', '2167', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_26'] = getnode_26.node.id
        randomnoise = RandomNoise(
            _id='2169',
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        getnode_27 = raw_call(wf, 'GetNode', '2171', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_27'] = getnode_27.node.id
        getnode_28 = raw_call(wf, 'GetNode', '2172', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_28'] = getnode_28.node.id
        # Sampling
        ksamplerselect = KSamplerSelect(_id='2174', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
        manualsigmas = ManualSigmas(_id='2176', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id
        randomnoise_2 = RandomNoise(
            _id='2179',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        ksamplerselect_2 = KSamplerSelect(
            _id='2180',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id

        manualsigmas_2 = ManualSigmas(
            _id='2187',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id

        getnode_29 = raw_call(wf, 'GetNode', '2190', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_29'] = getnode_29.node.id
        getnode_30 = raw_call(wf, 'GetNode', '2191', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_30'] = getnode_30.node.id
        getnode_31 = raw_call(wf, 'GetNode', '2192', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_31'] = getnode_31.node.id
        getnode_32 = raw_call(wf, 'GetNode', '2198', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_32'] = getnode_32.node.id
        # Inputs
        primitiveint = raw_call(wf, 'PrimitiveInt', '2284', value=5, widget_1='fixed')
        wf.metadata.setdefault('id_map', {})['primitiveint'] = primitiveint.node.id
        n_5e410bb1_405a_4d3d_808b_8f5f29426943 = raw_call(wf, '5e410bb1-405a-4d3d-808b-8f5f29426943', '3877',
        )
        wf.metadata.setdefault('id_map', {})['n_5e410bb1_405a_4d3d_808b_8f5f29426943'] = n_5e410bb1_405a_4d3d_808b_8f5f29426943.node.id

        primitivestring = raw_call(wf, 'PrimitiveString', '4119', value='mynewvideo')
        wf.metadata.setdefault('id_map', {})['primitivestring'] = primitivestring.node.id
        getnode_33 = raw_call(wf, 'GetNode', '4204', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_33'] = getnode_33.node.id
        getnode_34 = raw_call(wf, 'GetNode', '4710', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_34'] = getnode_34.node.id
        getnode_35 = raw_call(wf, 'GetNode', '4711', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_35'] = getnode_35.node.id
        getnode_36 = raw_call(wf, 'GetNode', '4724', widget_0=WIDGET_0_23)
        wf.metadata.setdefault('id_map', {})['getnode_36'] = getnode_36.node.id
        getnode_37 = raw_call(wf, 'GetNode', '4727', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_37'] = getnode_37.node.id
        getnode_38 = raw_call(wf, 'GetNode', '4728', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_38'] = getnode_38.node.id
        getnode_39 = raw_call(wf, 'GetNode', '4729', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_39'] = getnode_39.node.id
        primitiveboolean_2 = raw_call(wf, 'PrimitiveBoolean', '4736', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_2'] = primitiveboolean_2.node.id
        primitiveboolean_3 = raw_call(wf, 'PrimitiveBoolean', '4740', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_3'] = primitiveboolean_3.node.id
        loadimage_2 = LoadImage(
            _id='4750',
            image='download (1).png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        getnode_40 = raw_call(wf, 'GetNode', '5065', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_40'] = getnode_40.node.id
        getnode_41 = raw_call(wf, 'GetNode', '5066', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_41'] = getnode_41.node.id
        primitiveboolean_4 = raw_call(wf, 'PrimitiveBoolean', '5067', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_4'] = primitiveboolean_4.node.id
        primitivestringmultiline_3 = PrimitiveStringMultiline(
            _id='5068',
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at the stage at an abandoned teather.  The camera slowly orbits around the woman, the woman is always looking at the viewer.\n\nShe sings the lyrics: "Now rise from weights, unchained and free.\nLike open doors for you and me.\nAnd every node connects the light. To hands that build without a figh.  No locked gates, just open skies.Where anyone can close their eyes…".\n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline_3'] = primitivestringmultiline_3.node.id

        getnode_42 = raw_call(wf, 'GetNode', '5070', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_42'] = getnode_42.node.id
        primitivefloat_5 = raw_call(wf, 'PrimitiveFloat', '5071', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_5'] = primitivefloat_5.node.id
        primitiveint_2 = raw_call(wf, 'PrimitiveInt', '5072', value=5, widget_1='fixed')
        wf.metadata.setdefault('id_map', {})['primitiveint_2'] = primitiveint_2.node.id
        loadimage_3 = LoadImage(
            _id='5074',
            image='download (6).png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_3'] = loadimage_3.node.id

        getnode_43 = raw_call(wf, 'GetNode', '5140', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_43'] = getnode_43.node.id
        getnode_44 = raw_call(wf, 'GetNode', '5141', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_44'] = getnode_44.node.id
        primitiveboolean_5 = raw_call(wf, 'PrimitiveBoolean', '5142', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_5'] = primitiveboolean_5.node.id
        primitivestringmultiline_4 = PrimitiveStringMultiline(
            _id='5143',
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from a cloudy sky. \n\n\nShe sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, you stitch the seams. Of every film, each trembling tone. Where lonely sparks now feel at home".\n\nShe sings for a bit before she stands up and walks towards the viewer. \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline_4'] = primitivestringmultiline_4.node.id

        getnode_45 = raw_call(wf, 'GetNode', '5145', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_45'] = getnode_45.node.id
        primitivefloat_6 = raw_call(wf, 'PrimitiveFloat', '5146', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_6'] = primitivefloat_6.node.id
        primitiveint_3 = raw_call(wf, 'PrimitiveInt', '5147', value=5, widget_1='fixed')
        wf.metadata.setdefault('id_map', {})['primitiveint_3'] = primitiveint_3.node.id
        loadimage_4 = LoadImage(
            _id='5149',
            image='download (2).png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_4'] = loadimage_4.node.id

        getnode_46 = raw_call(wf, 'GetNode', '5215', widget_0=WIDGET_0_22)
        wf.metadata.setdefault('id_map', {})['getnode_46'] = getnode_46.node.id
        getnode_47 = raw_call(wf, 'GetNode', '5216', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_47'] = getnode_47.node.id
        primitiveboolean_6 = raw_call(wf, 'PrimitiveBoolean', '5217', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_6'] = primitiveboolean_6.node.id
        primitivestringmultiline_5 = PrimitiveStringMultiline(
            _id='5218',
            value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is standing on a rooftop balcony with the city behind her, at night. Camera slowly orbits around her, with her always looking towards the viewer as she sings. \n\nShe sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path through digital space. We dream in code, we dream in blue. And every open door leads through.......". \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline_5'] = primitivestringmultiline_5.node.id

        getnode_48 = raw_call(wf, 'GetNode', '5220', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_48'] = getnode_48.node.id
        primitivefloat_7 = raw_call(wf, 'PrimitiveFloat', '5221', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_7'] = primitivefloat_7.node.id
        primitiveint_4 = raw_call(wf, 'PrimitiveInt', '5222', value=5, widget_1='fixed')
        wf.metadata.setdefault('id_map', {})['primitiveint_4'] = primitiveint_4.node.id
        loadimage_5 = LoadImage(
            _id='5224',
            image='download (12).png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_5'] = loadimage_5.node.id

        getnode_49 = raw_call(wf, 'GetNode', '5226', widget_0=WIDGET_0_24)
        wf.metadata.setdefault('id_map', {})['getnode_49'] = getnode_49.node.id
        getnode_50 = raw_call(wf, 'GetNode', '5227', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_50'] = getnode_50.node.id
        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='344',
            width=getnode_30.out(0),
            height=getnode_31.out(0),
            length=getnode_10.out(0),
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='445',
            upscale_method='lanczos',
            keep_proportion='crop',
            device='cpu',
            width=getnode_8.out(0),
            height=getnode_9.out(0),
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='446',
            img_compression=18,
            image=getnode_29.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        setnode_4 = raw_call(wf, 'SetNode', '1528',
            widget_0='start_seed',
            INT=intconstant,
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        setnode_5 = raw_call(wf, 'SetNode', '1555',
            widget_0=WIDGET_0_12,
            LATENT_UPSCALE_MODEL=latentupscalemodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        setnode_6 = raw_call(wf, 'SetNode', '1556',
            widget_0=WIDGET_0_4,
            VAE=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        setnode_7 = raw_call(wf, 'SetNode', '1557', widget_0=WIDGET_0, VAE=vaeloader)
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id
        setnode_8 = raw_call(wf, 'SetNode', '1558',
            widget_0=WIDGET_0_6,
            CLIP=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='1560',
            lora_name=MODEL_NAME_11,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        setnode_9 = raw_call(wf, 'SetNode', '1568',
            widget_0=WIDGET_0_15,
            VAE=vaeloader_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        setnode_10 = raw_call(wf, 'SetNode', '1575',
            widget_0=WIDGET_0_3,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        setnode_11 = raw_call(wf, 'SetNode', '1576',
            widget_0=WIDGET_0_5,
            INT=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id

        setnode_12 = raw_call(wf, 'SetNode', '1577',
            widget_0=WIDGET_0_8,
            FLOAT=primitivefloat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_12'] = setnode_12.node.id

        trimaudioduration = TrimAudioDuration(
            _id='1598',
            widget_0=11,
            widget_1=40,
            audio=loadaudio,
            duration=n_5e410bb1_405a_4d3d_808b_8f5f29426943.out(0),
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration'] = trimaudioduration.node.id

        solidmask = SolidMask(
            _id='1604',
            widget_0=0,
            widget_1=512,
            widget_2=512,
            height=getnode_4.out(0),
            width=getnode_6.out(0),
        )
        wf.metadata.setdefault('id_map', {})['solidmask'] = solidmask.node.id

        # Conditioning
        cliptextencode_2 = CLIPTextEncode(
            _id='1626',
            text=DEFAULT_PROMPT,
            clip=getnode_7.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        simplecalculatorkj = SimpleCalculatorKJ(
            _id='1651',
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': primitivefloat_4, 'variables.b': primitivefloat},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj'] = simplecalculatorkj.node.id

        setnode_22 = raw_call(wf, 'SetNode', '1738',
            widget_0=WIDGET_0_20,
            FLOAT=primitivefloat_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_22'] = setnode_22.node.id

        n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf = raw_call(wf, '3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf', '2109',
            _1=primitivestringmultiline,
            clip=getnode_13.out(0),
            image=getnode_15.out(0),
        )
        wf.metadata.setdefault('id_map', {})['n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf'] = n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf.node.id

        setnode_25 = raw_call(wf, 'SetNode', '2115',
            widget_0=WIDGET_0_10,
            BOOLEAN=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['setnode_25'] = setnode_25.node.id

        cfgguider = CFGGuider(
            _id='2170',
            cfg=GUIDE_STRENGTH_2,
            model=getnode_25.out(0),
            negative=getnode_21.out(0),
            positive=getnode_22.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        modelsamplingsd3 = ModelSamplingSD3(
            _id='2175',
            shift=13,
            model=getnode_27.out(0),
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingsd3'] = modelsamplingsd3.node.id

        cfgguider_2 = CFGGuider(
            _id='2177',
            cfg=GUIDE_STRENGTH_2,
            model=getnode_27.out(0),
            negative=getnode_18.out(0),
            positive=getnode_19.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        ltx2_nag = LTX2_NAG(
            _id='2178',
            model=getnode_24.out(0),
            nag_cond_audio=getnode_26.out(0),
            nag_cond_video=getnode_26.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id

        modelsamplingsd3_2 = ModelSamplingSD3(
            _id='2185',
            shift=13,
            model=getnode_28.out(0),
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingsd3_2'] = modelsamplingsd3_2.node.id

        setnode_28 = raw_call(wf, 'SetNode', '2196',
            widget_0='sampler',
            SAMPLER=ksamplerselect_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_28'] = setnode_28.node.id

        setnode_30 = raw_call(wf, 'SetNode', '2314',
            widget_0='sigmas_2',
            SIGMAS=manualsigmas,
        )
        wf.metadata.setdefault('id_map', {})['setnode_30'] = setnode_30.node.id

        setnode_31 = raw_call(wf, 'SetNode', '2315',
            widget_0='sampler_2',
            SAMPLER=ksamplerselect,
        )
        wf.metadata.setdefault('id_map', {})['setnode_31'] = setnode_31.node.id

        setnode_32 = raw_call(wf, 'SetNode', '2325',
            widget_0='window_sec_02',
            FLOAT=primitivefloat_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_32'] = setnode_32.node.id

        c4106aee_ad7a_4925_972b_6f5b3d34db6e = raw_call(wf, 'c4106aee-ad7a-4925-972b-6f5b3d34db6e', '2329',
            _1=primitivestringmultiline_2,
            _2=primitivefloat_3,
            _4=getnode_33.out(0),
            images=loadimage_2.out('IMAGE'),
            noise_seed=primitiveint,
        )
        wf.metadata.setdefault('id_map', {})['c4106aee_ad7a_4925_972b_6f5b3d34db6e'] = c4106aee_ad7a_4925_972b_6f5b3d34db6e.node.id

        setnode_33 = raw_call(wf, 'SetNode', '3722',
            widget_0=WIDGET_0_9,
            FLOAT=primitivefloat_4,
        )
        wf.metadata.setdefault('id_map', {})['setnode_33'] = setnode_33.node.id

        stringconcatenate = StringConcatenate(
            _id='4164',
            widget_0=WIDGET_0_25,
            widget_1=WIDGET_1,
            widget_2=WIDGET_2,
            string_b=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['stringconcatenate'] = stringconcatenate.node.id

        stringconcatenate_3 = StringConcatenate(
            _id='4743',
            widget_0=WIDGET_0_26,
            widget_1=WIDGET_1,
            widget_2=WIDGET_2,
            string_b=getnode_36.out(0),
        )
        wf.metadata.setdefault('id_map', {})['stringconcatenate_3'] = stringconcatenate_3.node.id

        setnode_37 = raw_call(wf, 'SetNode', '4995',
            widget_0='sigmas',
            SIGMAS=manualsigmas_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_37'] = setnode_37.node.id

        setnode_38 = raw_call(wf, 'SetNode', '5064',
            widget_0='window_sec_03',
            FLOAT=primitivefloat_5,
        )
        wf.metadata.setdefault('id_map', {})['setnode_38'] = setnode_38.node.id

        setnode_39 = raw_call(wf, 'SetNode', '5139',
            widget_0='window_sec_04',
            FLOAT=primitivefloat_6,
        )
        wf.metadata.setdefault('id_map', {})['setnode_39'] = setnode_39.node.id

        setnode_40 = raw_call(wf, 'SetNode', '5214',
            widget_0='window_sec_05',
            FLOAT=primitivefloat_7,
        )
        wf.metadata.setdefault('id_map', {})['setnode_40'] = setnode_40.node.id

        setnode_41 = raw_call(wf, 'SetNode', '5225',
            widget_0=WIDGET_0_23,
            STRING=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['setnode_41'] = setnode_41.node.id

        simplecalculatorkj_2 = SimpleCalculatorKJ(
            _id='5228',
            expression='a + 100',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_49.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_2'] = simplecalculatorkj_2.node.id

        pathchsageattentionkj = PathchSageAttentionKJ(
            _id='268',
            sage_attention='disabled',
            model=loraloadermodelonly,
        )
        wf.metadata.setdefault('id_map', {})['pathchsageattentionkj'] = pathchsageattentionkj.node.id

        setnode_13 = raw_call(wf, 'SetNode', '1578',
            widget_0=WIDGET_0_7,
            INT=simplecalculatorkj.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_13'] = setnode_13.node.id

        setnode_14 = raw_call(wf, 'SetNode', '1589',
            widget_0=WIDGET_0_2,
            AUDIO=trimaudioduration,
        )
        wf.metadata.setdefault('id_map', {})['setnode_14'] = setnode_14.node.id

        melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '1599',
            audio=trimaudioduration,
            model=melbandroformermodelloader.out(0),
        )
        wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

        cliptextencode = CLIPTextEncode(
            _id='1621',
            text=n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf.out(0),
            clip=getnode_7.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='1630',
            resize_type='scale by multiplier',
            input=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        # Sampling
        basicscheduler = BasicScheduler(
            _id='2173',
            scheduler=1,
            steps=1,
            widget_1=4,
            model=modelsamplingsd3,
        )
        wf.metadata.setdefault('id_map', {})['basicscheduler'] = basicscheduler.node.id

        setnode_26 = raw_call(wf, 'SetNode', '2184',
            widget_0=WIDGET_0_17,
            MODEL=ltx2_nag,
        )
        wf.metadata.setdefault('id_map', {})['setnode_26'] = setnode_26.node.id

        basicscheduler_2 = BasicScheduler(
            _id='2186',
            scheduler=1,
            steps=1,
            widget_1=10,
            model=modelsamplingsd3_2,
        )
        wf.metadata.setdefault('id_map', {})['basicscheduler_2'] = basicscheduler_2.node.id

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            _id='2189',
            longer_edge=1536,
            images=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge'] = resizeimagesbylongeredge.node.id

        setnode_27 = raw_call(wf, 'SetNode', '2195',
            widget_0='guider',
            GUIDER=cfgguider,
        )
        wf.metadata.setdefault('id_map', {})['setnode_27'] = setnode_27.node.id

        setnode_29 = raw_call(wf, 'SetNode', '2313',
            widget_0='guider_2',
            GUIDER=cfgguider_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_29'] = setnode_29.node.id

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            _id='4109',
            widget_0=1,
            widget_1=False,
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace_2'] = ltxvimgtovideoinplace_2.node.id

        loadvideosfromfolder = LoadVideosFromFolder(
            _id='4708',
            widget_0=WIDGET_0_26,
            widget_1=0,
            widget_2=0,
            widget_3=0,
            widget_4=0,
            widget_5=0,
            widget_6=1,
            widget_7='batch',
            widget_8=4,
            widget_9=False,
            frame_load_cap=simplecalculatorkj_2.out('INT'),
            video=stringconcatenate_3,
        )
        wf.metadata.setdefault('id_map', {})['loadvideosfromfolder'] = loadvideosfromfolder.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='4709',
            frame_rate=getnode_34.out(0),
            filename_prefix=getnode_35.out(0),
            save_output=primitiveboolean_2,
            audio=c4106aee_ad7a_4925_972b_6f5b3d34db6e.out(2),
            images=c4106aee_ad7a_4925_972b_6f5b3d34db6e.out(1),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        stringconcatenate_2 = StringConcatenate(
            _id='4735',
            widget_0=WIDGET_0_25,
            widget_1='MusicVideo',
            widget_2=WIDGET_2,
            string_a=stringconcatenate,
        )
        wf.metadata.setdefault('id_map', {})['stringconcatenate_2'] = stringconcatenate_2.node.id

        n_17238add_9973_482f_8fa3_248d4ed29886 = raw_call(wf, '17238add-9973-482f-8fa3-248d4ed29886', '5073',
            _1=primitivestringmultiline_3,
            _2=primitivefloat_5,
            _4=c4106aee_ad7a_4925_972b_6f5b3d34db6e.out(0),
            images=loadimage_3.out('IMAGE'),
            noise_seed=primitiveint_2,
        )
        wf.metadata.setdefault('id_map', {})['n_17238add_9973_482f_8fa3_248d4ed29886'] = n_17238add_9973_482f_8fa3_248d4ed29886.node.id

        ltxvconditioning = LTXVConditioning(
            _id='164',
            frame_rate=getnode_11.out(0),
            negative=cliptextencode_2,
            positive=cliptextencode,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='504',
            model=pathchsageattentionkj,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        setnode_3 = raw_call(wf, 'SetNode', '650',
            widget_0=WIDGET_0_11,
            IMAGE=resizeimagesbylongeredge,
        )
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

        setnode_15 = raw_call(wf, 'SetNode', '1590',
            widget_0='audio_vocals',
            AUDIO=melbandroformersampler.out(0),
        )
        wf.metadata.setdefault('id_map', {})['setnode_15'] = setnode_15.node.id

        comfyswitchnode = ComfySwitchNode(
            _id='1616',
            widget_0=True,
            on_false=trimaudioduration,
            on_true=melbandroformersampler.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode'] = comfyswitchnode.node.id

        getimagesize = GetImageSize(
            _id='1631',
            image=resizeimagemasknode,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        setnode_34 = raw_call(wf, 'SetNode', '4121',
            widget_0=WIDGET_0_22,
            STRING=stringconcatenate_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_34'] = setnode_34.node.id

        vhs_videocombine_2 = VHS_VideoCombine(
            _id='4725',
            frame_rate=getnode_37.out(0),
            audio=getnode_50.out(0),
            images=loadvideosfromfolder,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_2'] = vhs_videocombine_2.node.id

        vhs_videocombine_4 = VHS_VideoCombine(
            _id='5069',
            frame_rate=getnode_41.out(0),
            filename_prefix=getnode_40.out(0),
            save_output=primitiveboolean_4,
            audio=n_17238add_9973_482f_8fa3_248d4ed29886.out(2),
            images=n_17238add_9973_482f_8fa3_248d4ed29886.out(1),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_4'] = vhs_videocombine_4.node.id

        a3fb563d_4711_4225_9210_fbe61b1bd79d = raw_call(wf, 'a3fb563d-4711-4225-9210-fbe61b1bd79d', '5148',
            _1=primitivestringmultiline_4,
            _2=primitivefloat_6,
            _4=n_17238add_9973_482f_8fa3_248d4ed29886.out(0),
            images=loadimage_4.out('IMAGE'),
            noise_seed=primitiveint_3,
        )
        wf.metadata.setdefault('id_map', {})['a3fb563d_4711_4225_9210_fbe61b1bd79d'] = a3fb563d_4711_4225_9210_fbe61b1bd79d.node.id

        setnode = raw_call(wf, 'SetNode', '645',
            widget_0=WIDGET_0_14,
            CONDITIONING=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        setnode_2 = raw_call(wf, 'SetNode', '646',
            widget_0=WIDGET_0_13,
            CONDITIONING=ltxvconditioning.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            _id='1523',
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['ltx2attentiontunerpatch'] = ltx2attentiontunerpatch.node.id

        setnode_17 = raw_call(wf, 'SetNode', '1615',
            widget_0='audio',
            AUDIO=comfyswitchnode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_17'] = setnode_17.node.id

        setnode_19 = raw_call(wf, 'SetNode', '1633',
            widget_0=WIDGET_0_18,
            INT=getimagesize.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_19'] = setnode_19.node.id

        setnode_20 = raw_call(wf, 'SetNode', '1634',
            widget_0=WIDGET_0_19,
            INT=getimagesize.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_20'] = setnode_20.node.id

        trimaudioduration_2 = TrimAudioDuration(
            _id='1653',
            widget_0=0,
            widget_1=40,
            audio=comfyswitchnode,
            duration=getnode_12.out(0),
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration_2'] = trimaudioduration_2.node.id

        vhs_videocombine_5 = VHS_VideoCombine(
            _id='5144',
            frame_rate=getnode_44.out(0),
            filename_prefix=getnode_43.out(0),
            save_output=primitiveboolean_5,
            audio=a3fb563d_4711_4225_9210_fbe61b1bd79d.out(2),
            images=a3fb563d_4711_4225_9210_fbe61b1bd79d.out(1),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_5'] = vhs_videocombine_5.node.id

        n_4acc9924_c0bd_470a_b000_46c75e61d004 = raw_call(wf, '4acc9924-c0bd-470a-b000-46c75e61d004', '5223',
            _1=primitivestringmultiline_5,
            _2=primitivefloat_7,
            _4=a3fb563d_4711_4225_9210_fbe61b1bd79d.out(0),
            images=loadimage_5.out('IMAGE'),
            noise_seed=primitiveint_4,
        )
        wf.metadata.setdefault('id_map', {})['n_4acc9924_c0bd_470a_b000_46c75e61d004'] = n_4acc9924_c0bd_470a_b000_46c75e61d004.node.id

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            _id='1605',
            audio=trimaudioduration_2,
            audio_vae=getnode_5.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

        power_lora_loader__rgthree_ = raw_call(wf, 'Power Lora Loader (rgthree)', '2150',
            _outputs=('MODEL', 'CLIP'),
            widget_7='',
            model=ltx2attentiontunerpatch,
        )
        wf.metadata.setdefault('id_map', {})['power_lora_loader__rgthree_'] = power_lora_loader__rgthree_.node.id

        setnode_36 = raw_call(wf, 'SetNode', '4733',
            widget_0=WIDGET_0_24,
            INT=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(0),
        )
        wf.metadata.setdefault('id_map', {})['setnode_36'] = setnode_36.node.id

        vhs_videocombine_6 = VHS_VideoCombine(
            _id='5219',
            frame_rate=getnode_47.out(0),
            filename_prefix=getnode_46.out(0),
            save_output=primitiveboolean_6,
            audio=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(2),
            images=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(1),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_6'] = vhs_videocombine_6.node.id

        setlatentnoisemask = SetLatentNoiseMask(
            _id='1603',
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )
        wf.metadata.setdefault('id_map', {})['setlatentnoisemask'] = setlatentnoisemask.node.id

        setnode_18 = raw_call(wf, 'SetNode', '1617',
            widget_0=WIDGET_0_16,
            MODEL=power_lora_loader__rgthree_.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_18'] = setnode_18.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='350',
            audio_latent=setlatentnoisemask,
            video_latent=ltxvimgtovideoinplace_2,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        setnode_16 = raw_call(wf, 'SetNode', '1602',
            widget_0='latent_custom_audio',
            LATENT=setlatentnoisemask,
        )
        wf.metadata.setdefault('id_map', {})['setnode_16'] = setnode_16.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='2181',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='2159',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            _id='2183',
            widget_0=1,
            widget_1=False,
            image=getnode_20.out(0),
            latent=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            strength=getnode_32.out(0),
            vae=getnode_16.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='2153',
            audio_latent=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
            video_latent=ltxvimgtovideoinplace,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='2182',
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='245',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        # Decode
        vaedecode = VAEDecode(
            _id='1318',
            samples=ltxvseparateavlatent.out('VIDEO_LATENT'),
            vae=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaedecode'] = vaedecode.node.id

        getimagesizeandcount = GetImageSizeAndCount(
            _id='2023',
            image=vaedecode,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount'] = getimagesizeandcount.node.id

        vram_debug = VRAM_Debug(
            _id='4184',
            widget_0=True,
            widget_1=True,
            widget_2=False,
            image_pass=vaedecode,
            _outputs=('ANY_OUTPUT', 'IMAGE_PASS', 'MODEL_PASS', 'FREEMEM_BEFORE', 'FREEMEM_AFTER'),
        )
        wf.metadata.setdefault('id_map', {})['vram_debug'] = vram_debug.node.id

        # Outputs
        vhs_videocombine_3 = VHS_VideoCombine(
            _id='4730',
            frame_rate=getnode_39.out(0),
            filename_prefix=getnode_38.out(0),
            save_output=primitiveboolean_3,
            audio=getnode_3.out(0),
            images=vaedecode,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine_3'] = vhs_videocombine_3.node.id

        setnode_23 = raw_call(wf, 'SetNode', '1938',
            widget_0='height_generated',
            INT=getimagesizeandcount.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_23'] = setnode_23.node.id

        setnode_24 = raw_call(wf, 'SetNode', '1939',
            widget_0='width_generated',
            INT=getimagesizeandcount.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_24'] = setnode_24.node.id

        getimagesizeandcount_2 = GetImageSizeAndCount(
            _id='4199',
            image=vram_debug.out('IMAGE_PASS'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesizeandcount_2'] = getimagesizeandcount_2.node.id

        setnode_21 = raw_call(wf, 'SetNode', '1716',
            widget_0='initial_frames',
            IMAGE=getimagesizeandcount_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_21'] = setnode_21.node.id

        setnode_35 = raw_call(wf, 'SetNode', '4203',
            widget_0=WIDGET_0_21,
            INT=getimagesizeandcount_2.out('COUNT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_35'] = setnode_35.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

