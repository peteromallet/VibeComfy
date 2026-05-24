# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2_NAG, LTXVChunkFeedForward, SimpleCalculatorKJ
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
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 43
GUIDE_STRENGTH = 2.5
GUIDE_STRENGTH_2 = 0.6
MODEL_NAME = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_10 = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_11 = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME_2 = 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors'
MODEL_NAME_3 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_4 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_6 = 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_7 = 'taeltx2_3.safetensors'
MODEL_NAME_8 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
MODEL_NAME_9 = 'gemma-3-12b-it-Q2_K.gguf'
WIDGET_0 = 'frames'
WIDGET_0_10 = 'height_downsized'
WIDGET_0_11 = 'latent'
WIDGET_0_12 = 'upscale_model'
WIDGET_0_13 = 'width'
WIDGET_0_14 = 'height'
WIDGET_0_15 = 'model_with_lora'
WIDGET_0_16 = 'fps'
WIDGET_0_17 = 't2v_mode'
WIDGET_0_18 = 'vae_tiny'
WIDGET_0_19 = 'latent_audio'
WIDGET_0_2 = 'ref_image'
WIDGET_0_20 = 'latent_custom_audio'
WIDGET_0_21 = 'org_audio'
WIDGET_0_22 = ''
WIDGET_0_3 = 'clip'
WIDGET_0_4 = 'vae_audio'
WIDGET_0_5 = 'vae'
WIDGET_0_6 = 'model'
WIDGET_0_7 = 'positive'
WIDGET_0_8 = 'negative'
WIDGET_0_9 = 'width_downsized'


MODELS = {}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node=ref('latentupscalemodelloader'), field='model_name', default=MODEL_NAME_2),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
    'image': InputSpec(node=ref('loadimage'), field='image', default='liam-neeson-in-retribution-ra.jpg'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='liam-neeson-in-retribution-ra.jpg'),
}

READY_METADATA = ReadyMetadata.build(
    capability='custom_audio_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX23_audio_vae_bf16.safetensors', 'LTX23_video_vae_bf16.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'taeltx2_3.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='custom audio conditioning',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        manualsigmas = ManualSigmas(_id='100', sigmas='0.909375, 0.725, 0.421875, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id
        randomnoise = RandomNoise(
            _id='114',
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        randomnoise_2 = RandomNoise(
            _id='115',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        # Sampling
        ksamplerselect = KSamplerSelect(
            _id='137',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id

        ksamplerselect_2 = KSamplerSelect(_id='138', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id
        # Inputs
        loadimage = LoadImage(
            _id='167',
            image='liam-neeson-in-retribution-ra.jpg',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        # Loaders
        vaeloader = VAELoader(_id='184', vae_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        latentupscalemodelloader = LatentUpscaleModelLoader(
            _id='189',
            model_name=MODEL_NAME_2,
        )
        wf.metadata.setdefault('id_map', {})['latentupscalemodelloader'] = latentupscalemodelloader.node.id

        dualcliploader = DualCLIPLoader(
            _id='190',
            clip_name1=MODEL_NAME_3,
            clip_name2=MODEL_NAME_4,
            type_='ltxv',
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='196', ckpt_name=MODEL_NAME_5)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        getnode = raw_call(wf, 'GetNode', '205', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        getnode_2 = raw_call(wf, 'GetNode', '210', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '212', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        getnode_4 = raw_call(wf, 'GetNode', '214', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '217', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '218', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '219', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '220', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '221', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        getnode_10 = raw_call(wf, 'GetNode', '225', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '228', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '229', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '230', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '231', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        getnode_15 = raw_call(wf, 'GetNode', '236', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        getnode_16 = raw_call(wf, 'GetNode', '237', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        getnode_17 = raw_call(wf, 'GetNode', '239', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '242', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '243', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        getnode_20 = raw_call(wf, 'GetNode', '244', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '285', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '290', value=False)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        intconstant = INTConstant(_id='291', value=10)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='292', value=1280)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        intconstant_3 = INTConstant(_id='293', value=736)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        getnode_21 = raw_call(wf, 'GetNode', '306', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_21'] = getnode_21.node.id
        getnode_22 = raw_call(wf, 'GetNode', '307', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_22'] = getnode_22.node.id
        getnode_23 = raw_call(wf, 'GetNode', '308', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_23'] = getnode_23.node.id
        getnode_24 = raw_call(wf, 'GetNode', '309', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_24'] = getnode_24.node.id
        getnode_25 = raw_call(wf, 'GetNode', '310', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_25'] = getnode_25.node.id
        getnode_26 = raw_call(wf, 'GetNode', '322', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_26'] = getnode_26.node.id
        # Loaders
        unetloader = UNETLoader(_id='329', unet_name=MODEL_NAME_6)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        vaeloader_2 = VAELoader(_id='330', vae_name=MODEL_NAME_7)
        wf.metadata.setdefault('id_map', {})['vaeloader_2'] = vaeloader_2.node.id
        getnode_27 = raw_call(wf, 'GetNode', '338', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_27'] = getnode_27.node.id
        getnode_28 = raw_call(wf, 'GetNode', '339', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_28'] = getnode_28.node.id
        getnode_29 = raw_call(wf, 'GetNode', '341', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_29'] = getnode_29.node.id
        getnode_30 = raw_call(wf, 'GetNode', '343', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_30'] = getnode_30.node.id
        getnode_31 = raw_call(wf, 'GetNode', '344', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_31'] = getnode_31.node.id
        unetloadergguf = UnetLoaderGGUF(_id='345', unet_name=MODEL_NAME_8)
        wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
        dualcliploadergguf = DualCLIPLoaderGGUF(
            _id='346',
            clip_name1=MODEL_NAME_9,
            clip_name2=MODEL_NAME_4,
            type_='sdxl',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploadergguf'] = dualcliploadergguf.node.id

        primitivestringmultiline = PrimitiveStringMultiline(
            _id='350',
            value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

        primitivestringmultiline_2 = PrimitiveStringMultiline(
            _id='352',
            value='Make this image come alive with fluid motion. \n\nA man with an intimidating expression speaks with expressive body language and gesticulations. \n\nHe looks at the vewer and talks, he says  : "If you say a bad word about LTX 2 point 3, i will find you.... and i will kill you" ',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline_2'] = primitivestringmultiline_2.node.id

        getnode_32 = raw_call(wf, 'GetNode', '359', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_32'] = getnode_32.node.id
        getnode_33 = raw_call(wf, 'GetNode', '360', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_33'] = getnode_33.node.id
        getnode_34 = raw_call(wf, 'GetNode', '361', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_34'] = getnode_34.node.id
        getnode_35 = raw_call(wf, 'GetNode', '368', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_35'] = getnode_35.node.id
        getnode_36 = raw_call(wf, 'GetNode', '369', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_36'] = getnode_36.node.id
        melbandroformermodelloader = raw_call(wf, 'MelBandRoFormerModelLoader', '370',
            widget_0=MODEL_NAME_10,
        )
        wf.metadata.setdefault('id_map', {})['melbandroformermodelloader'] = melbandroformermodelloader.node.id

        loadaudio = LoadAudio(_id='372', audio='ComfyUI_00128_.mp3')
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id
        getnode_37 = raw_call(wf, 'GetNode', '374', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_37'] = getnode_37.node.id
        getnode_38 = raw_call(wf, 'GetNode', '375', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_38'] = getnode_38.node.id
        getnode_39 = raw_call(wf, 'GetNode', '378', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_39'] = getnode_39.node.id
        reroute = raw_call(wf, 'Reroute', '379')
        wf.metadata.setdefault('id_map', {})['reroute'] = reroute.node.id
        manualsigmas_2 = ManualSigmas(_id='380', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id
        manualsigmas_3 = ManualSigmas(
            _id='381',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas_3'] = manualsigmas_3.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='103',
            cfg=GUIDE_STRENGTH,
            model=getnode_29.out(0),
            negative=getnode_12.out(0),
            positive=getnode_11.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='108',
            width=getnode_15.out(0),
            height=getnode_16.out(0),
            length=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='110',
            text=DEFAULT_PROMPT,
            clip=getnode_4.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        cfgguider_2 = CFGGuider(
            _id='129',
            cfg=GUIDE_STRENGTH,
            model=getnode_31.out(0),
            negative=getnode_14.out(0),
            positive=getnode_13.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='134',
            lora_name=MODEL_NAME_11,
            strength_model=GUIDE_STRENGTH_2,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='162',
            img_compression=33,
            image=getnode_2.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='165',
            upscale_method='nearest-exact',
            keep_proportion='crop',
            divisible_by=32,
            device='cpu',
            width=getnode_19.out(0),
            height=getnode_20.out(0),
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        setnode = raw_call(wf, 'SetNode', '188',
            widget_0=WIDGET_0_12,
            LATENT_UPSCALE_MODEL=latentupscalemodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        ltxvscheduler = LTXVScheduler(_id='206', steps=1, latent=getnode_17.out(0))
        wf.metadata.setdefault('id_map', {})['ltxvscheduler'] = ltxvscheduler.node.id
        setnode_4 = raw_call(wf, 'SetNode', '213',
            widget_0=WIDGET_0_3,
            CLIP=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        setnode_5 = raw_call(wf, 'SetNode', '215', widget_0=WIDGET_0_5, VAE=vaeloader)
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id
        setnode_6 = raw_call(wf, 'SetNode', '216',
            widget_0=WIDGET_0_4,
            VAE=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id

        setnode_14 = raw_call(wf, 'SetNode', '282',
            widget_0=WIDGET_0_14,
            INT=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_14'] = setnode_14.node.id

        setnode_15 = raw_call(wf, 'SetNode', '283',
            widget_0=WIDGET_0_13,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_15'] = setnode_15.node.id

        setnode_16 = raw_call(wf, 'SetNode', '284',
            widget_0=WIDGET_0_16,
            FLOAT=primitivefloat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_16'] = setnode_16.node.id

        simplecalculatorkj = SimpleCalculatorKJ(
            _id='287',
            expression='1+ 8*(round(a*b)/8)',
            a=intconstant,
            b=primitivefloat,
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj'] = simplecalculatorkj.node.id

        setnode_18 = raw_call(wf, 'SetNode', '288',
            widget_0=WIDGET_0_17,
            BOOLEAN=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['setnode_18'] = setnode_18.node.id

        simplecalculatorkj_2 = SimpleCalculatorKJ(
            _id='311',
            expression='a',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': getnode_25.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_2'] = simplecalculatorkj_2.node.id

        setnode_20 = raw_call(wf, 'SetNode', '331',
            widget_0=WIDGET_0_18,
            VAE=vaeloader_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_20'] = setnode_20.node.id

        ltx2_nag = LTX2_NAG(
            _id='342',
            model=getnode_28.out(0),
            nag_cond_audio=getnode_30.out(0),
            nag_cond_video=getnode_30.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id

        stringconcatenate = StringConcatenate(
            _id='347',
            widget_0=WIDGET_0_22,
            widget_1='',
            widget_2='',
            string_a=primitivestringmultiline,
        )
        wf.metadata.setdefault('id_map', {})['stringconcatenate'] = stringconcatenate.node.id

        solidmask = SolidMask(
            _id='362',
            widget_0=0,
            widget_1=512,
            widget_2=512,
            height=getnode_32.out(0),
            width=getnode_33.out(0),
        )
        wf.metadata.setdefault('id_map', {})['solidmask'] = solidmask.node.id

        simplecalculatorkj_3 = SimpleCalculatorKJ(
            _id='367',
            expression='a/b',
            a=getnode_35.out(0),
            b=getnode_36.out(0),
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj_3'] = simplecalculatorkj_3.node.id

        comfyswitchnode = ComfySwitchNode(
            _id='376',
            widget_0=True,
            on_false=getnode_37.out(0),
            on_true=getnode_38.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode'] = comfyswitchnode.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='113',
            guider=cfgguider_2,
            latent_image=getnode_17.out(0),
            noise=randomnoise_2,
            sampler=ksamplerselect,
            sigmas=manualsigmas_3,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            _id='161',
            widget_0=1,
            widget_1=False,
            bypass=getnode_23.out(0),
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=getnode_6.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace_2'] = ltxvimgtovideoinplace_2.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='164',
            resize_type='scale by multiplier',
            input=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='199',
            frames_number=getnode.out(0),
            frame_rate=simplecalculatorkj_2.out('INT'),
            audio_vae=getnode_5.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        setnode_3 = raw_call(wf, 'SetNode', '211',
            widget_0='compress_image',
            IMAGE=ltxvpreprocess,
        )
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

        resizeimagesbylongeredge = ResizeImagesByLongerEdge(
            _id='246',
            longer_edge=1536,
            images=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge'] = resizeimagesbylongeredge.node.id

        setnode_17 = raw_call(wf, 'SetNode', '286',
            widget_0=WIDGET_0,
            INT=simplecalculatorkj.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_17'] = setnode_17.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='332',
            model=loraloadermodelonly,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        setnode_21 = raw_call(wf, 'SetNode', '340', widget_0=WIDGET_0_6, MODEL=ltx2_nag)
        wf.metadata.setdefault('id_map', {})['setnode_21'] = setnode_21.node.id
        textgenerateltx2prompt = TextGenerateLTX2Prompt(
            _id='349',
            widget_0=WIDGET_0_22,
            widget_1=256,
            widget_2='off',
            clip=getnode_4.out(0),
            image=imageresizekjv2.out('IMAGE'),
            prompt=primitivestringmultiline_2,
        )
        wf.metadata.setdefault('id_map', {})['textgenerateltx2prompt'] = textgenerateltx2prompt.node.id

        trimaudioduration = TrimAudioDuration(
            _id='373',
            widget_0=0,
            widget_1=8,
            audio=loadaudio,
            duration=simplecalculatorkj_3.out('FLOAT'),
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration'] = trimaudioduration.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='109',
            audio_latent=comfyswitchnode,
            video_latent=ltxvimgtovideoinplace_2,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='116',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        # Conditioning
        cliptextencode_2 = CLIPTextEncode(
            _id='121',
            text=textgenerateltx2prompt,
            clip=getnode_4.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        getimagesize = GetImageSize(
            _id='163',
            image=resizeimagemasknode,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        setnode_2 = raw_call(wf, 'SetNode', '209',
            widget_0=WIDGET_0_2,
            IMAGE=resizeimagesbylongeredge,
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        setnode_12 = raw_call(wf, 'SetNode', '240',
            widget_0=WIDGET_0_19,
            LATENT=ltxvemptylatentaudio,
        )
        wf.metadata.setdefault('id_map', {})['setnode_12'] = setnode_12.node.id

        setnode_13 = raw_call(wf, 'SetNode', '248',
            widget_0='resize_image',
            IMAGE=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['setnode_13'] = setnode_13.node.id

        power_lora_loader__rgthree_ = raw_call(wf, 'Power Lora Loader (rgthree)', '301',
            _outputs=('MODEL', 'CLIP'),
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['power_lora_loader__rgthree_'] = power_lora_loader__rgthree_.node.id

        setnode_22 = raw_call(wf, 'SetNode', '365',
            widget_0=WIDGET_0_21,
            AUDIO=trimaudioduration,
        )
        wf.metadata.setdefault('id_map', {})['setnode_22'] = setnode_22.node.id

        melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '371',
            audio=trimaudioduration,
            model=melbandroformermodelloader.out(0),
        )
        wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

        ltxvconditioning = LTXVConditioning(
            _id='107',
            frame_rate=getnode_26.out(0),
            negative=cliptextencode,
            positive=cliptextencode_2,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            _id='160',
            widget_0=1,
            widget_1=False,
            bypass=getnode_24.out(0),
            image=getnode_3.out(0),
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            vae=getnode_7.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

        setnode_9 = raw_call(wf, 'SetNode', '233',
            widget_0=WIDGET_0_9,
            INT=getimagesize.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        setnode_10 = raw_call(wf, 'SetNode', '234',
            widget_0=WIDGET_0_10,
            INT=getimagesize.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        setnode_11 = raw_call(wf, 'SetNode', '238',
            widget_0=WIDGET_0_11,
            LATENT=ltxvconcatavlatent,
        )
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id

        setnode_19 = raw_call(wf, 'SetNode', '303',
            widget_0=WIDGET_0_15,
            MODEL=power_lora_loader__rgthree_.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_19'] = setnode_19.node.id

        comfyswitchnode_2 = ComfySwitchNode(
            _id='382',
            widget_0=False,
            on_false=trimaudioduration,
            on_true=melbandroformersampler.out(0),
        )
        wf.metadata.setdefault('id_map', {})['comfyswitchnode_2'] = comfyswitchnode_2.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='117',
            audio_latent=ltxvseparateavlatent.out('AUDIO_LATENT'),
            video_latent=ltxvimgtovideoinplace,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        setnode_7 = raw_call(wf, 'SetNode', '226',
            widget_0=WIDGET_0_7,
            CONDITIONING=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        setnode_8 = raw_call(wf, 'SetNode', '227',
            widget_0=WIDGET_0_8,
            CONDITIONING=ltxvconditioning.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            _id='364',
            audio=comfyswitchnode_2,
            audio_vae=getnode_34.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

        # Sampling
        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='119',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        setlatentnoisemask = SetLatentNoiseMask(
            _id='363',
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )
        wf.metadata.setdefault('id_map', {})['setlatentnoisemask'] = setlatentnoisemask.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='125',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        setnode_23 = raw_call(wf, 'SetNode', '366',
            widget_0=WIDGET_0_20,
            LATENT=setlatentnoisemask,
        )
        wf.metadata.setdefault('id_map', {})['setnode_23'] = setnode_23.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            _id='127',
            temporal_size=4096,
            samples=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            vae=getnode_8.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='201',
            audio_vae=getnode_9.out(0),
            samples=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='140',
            frame_rate=getnode_22.out(0),
            audio=getnode_39.out(0),
            images=vaedecodetiled,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

