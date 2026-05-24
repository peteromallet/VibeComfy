# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.ltxvideo import GuiderParameters, LTXFloatToInt, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode, LowVRAMAudioVAELoader, LowVRAMCheckpointLoader, MultimodalGuider
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.resolution import resolution

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


DEFAULT_FRAMES = 9
DEFAULT_PROMPT = 'A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.'
DEFAULT_PROMPT_2 = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_SEED = 42
DEFAULT_SEED_2 = 43
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 0.2
GUIDE_STRENGTH_3 = 1
MODEL_NAME = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_2 = 'comfy_gemma_3_12B_it.safetensors'
MODEL_NAME_3 = 'ltx-2.3-22b-dev.safetensors'
MODEL_NAME_4 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
UNKNOWN = 'auto'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('lowvramcheckpointloader'), field='ckpt_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'image': InputSpec(node=ref('loadimage'), field='image', default='egyptian_queen.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='egyptian_queen.png'),
    'start_image': InputSpec(node=ref('loadimage'), field='image', default='egyptian_queen.png'),
    'negative_prompt': InputSpec(node=ref('cliptextencode_2'), field='text', default=DEFAULT_PROMPT_2),
    'negative': InputSpec(node=ref('cliptextencode_2'), field='text', default=DEFAULT_PROMPT_2),
    'width': InputSpec(node=ref('emptyltxvlatentvideo'), field='width', default=384),
    'height': InputSpec(node=ref('emptyltxvlatentvideo'), field='height', default=256),
    'output_fps': InputSpec(node=ref('primitivefloat'), field='value', default=8),
    'fps': InputSpec(node=ref('primitivefloat'), field='value', default=8),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
    'length': InputSpec(node=ref('primitiveint'), field='value', default=9),
    'frames': InputSpec(node=ref('primitiveint'), field='value', default=9),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['euler_ancestral_cfg_pp', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-dev.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='384x256x9_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    external_python_marker='external_python:video/ltx2_3_i2v',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        loadimage = LoadImage(
            _id='2004',
            image='example.png',
            widget_0='egyptian_queen.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        lowvramaudiovaeloader = LowVRAMAudioVAELoader(_id='4010', ckpt_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['lowvramaudiovaeloader'] = lowvramaudiovaeloader.node.id
        randomnoise = RandomNoise(_id='4814', noise_seed=DEFAULT_SEED)
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id
        # Sampling
        ksamplerselect = KSamplerSelect(
            _id='4831',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id

        randomnoise_2 = RandomNoise(_id='4832', noise_seed=DEFAULT_SEED_2)
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id
        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            _id='4960',
            text_encoder=MODEL_NAME_2,
            ckpt_name=MODEL_NAME_3,
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['ltxavtextencoderloader'] = ltxavtextencoderloader.node.id

        guiderparameters = GuiderParameters(_id='4963', UNKNOWN=True)
        wf.metadata.setdefault('id_map', {})['guiderparameters'] = guiderparameters.node.id
        clownsampler_beta = raw_call(wf, 'ClownSampler_Beta', '4967', UNKNOWN=True)
        wf.metadata.setdefault('id_map', {})['clownsampler_beta'] = clownsampler_beta.node.id
        manualsigmas = ManualSigmas(
            _id='4971',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '4977',
            value=True,
            widget_0=False,
        )
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id

        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '4978', value=24, widget_0=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        primitiveint = raw_call(wf, 'PrimitiveInt', '4979', value=121, widget_0=9)
        wf.metadata.setdefault('id_map', {})['primitiveint'] = primitiveint.node.id
        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='2483',
            text=DEFAULT_PROMPT,
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        cliptextencode_2 = CLIPTextEncode(
            _id='2612',
            text=DEFAULT_PROMPT_2,
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='3059',
            width=384,
            height=256,
            widget_0=384,
            widget_1=256,
            widget_2=9,
            length=primitiveint,
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        lowvramcheckpointloader = LowVRAMCheckpointLoader(
            _id='3940',
            ckpt_name=MODEL_NAME,
            dependencies=ltxavtextencoderloader,
            _outputs=('MODEL', 'CLIP', 'VAE'),
        )
        wf.metadata.setdefault('id_map', {})['lowvramcheckpointloader'] = lowvramcheckpointloader.node.id

        guiderparameters_2 = GuiderParameters(
            _id='4964',
            UNKNOWN=True,
            parameters=guiderparameters,
        )
        wf.metadata.setdefault('id_map', {})['guiderparameters_2'] = guiderparameters_2.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='4981',
            resize_type='scale longer dimension',
            scale_method='lanczos',
            input=loadimage.out('IMAGE'),
            **{'resize_type.longer_size': 1536},
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        ltxfloattoint = LTXFloatToInt(_id='4985', UNKNOWN=0, a=primitivefloat)
        wf.metadata.setdefault('id_map', {})['ltxfloattoint'] = ltxfloattoint.node.id
        ltxvconditioning = LTXVConditioning(
            _id='1241',
            widget_0=8,
            frame_rate=primitivefloat,
            negative=cliptextencode_2,
            positive=cliptextencode,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='3336',
            img_compression=18,
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='3980',
            widget_0=9,
            widget_1=8,
            frames_number=primitiveint,
            frame_rate=ltxfloattoint,
            audio_vae=lowvramaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='4922',
            lora_name=MODEL_NAME_4,
            strength_model=GUIDE_STRENGTH,
            model=lowvramcheckpointloader.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        loraloadermodelonly_2 = LoraLoaderModelOnly(
            _id='4968',
            lora_name=MODEL_NAME_4,
            strength_model=GUIDE_STRENGTH_2,
            model=lowvramcheckpointloader.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly_2'] = loraloadermodelonly_2.node.id

        ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
            _id='3159',
            UNKNOWN=False,
            bypass=primitiveboolean,
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoconditiononly'] = ltxvimgtovideoconditiononly.node.id

        # Conditioning
        multimodalguider = MultimodalGuider(
            _id='4808',
            UNKNOWN='28',
            model=loraloadermodelonly_2,
            negative=ltxvconditioning.out('NEGATIVE'),
            parameters=guiderparameters_2,
            positive=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['multimodalguider'] = multimodalguider.node.id

        cfgguider = CFGGuider(
            _id='4828',
            cfg=GUIDE_STRENGTH_3,
            model=loraloadermodelonly,
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='4528',
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxvimgtovideoconditiononly,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        # Sampling
        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='4829',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        ltxvscheduler = LTXVScheduler(_id='4966', steps=15, latent=ltxvconcatavlatent)
        wf.metadata.setdefault('id_map', {})['ltxvscheduler'] = ltxvscheduler.node.id
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='4802',
            guider=multimodalguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=clownsampler_beta.out(0),
            sigmas=ltxvscheduler,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='4845',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='4824',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        ltxvaudiovaedecode_2 = LTXVAudioVAEDecode(
            _id='4848',
            audio_vae=lowvramaudiovaeloader,
            samples=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode_2'] = ltxvaudiovaedecode_2.node.id

        ltxvtiledvaedecode = LTXVTiledVAEDecode(
            _id='4982',
            UNKNOWN=UNKNOWN,
            latents=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvtiledvaedecode'] = ltxvtiledvaedecode.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='4818',
            audio_vae=lowvramaudiovaeloader,
            samples=ltxvseparateavlatent.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        createvideo_2 = CreateVideo(
            _id='4849',
            fps=primitivefloat,
            audio=ltxvaudiovaedecode_2,
            images=ltxvtiledvaedecode,
        )
        wf.metadata.setdefault('id_map', {})['createvideo_2'] = createvideo_2.node.id

        ltxvtiledvaedecode_2 = LTXVTiledVAEDecode(
            _id='4983',
            UNKNOWN=UNKNOWN,
            latents=ltxvseparateavlatent.out('VIDEO_LATENT'),
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvtiledvaedecode_2'] = ltxvtiledvaedecode_2.node.id

        createvideo = CreateVideo(
            _id='4819',
            fps=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=ltxvtiledvaedecode_2,
        )
        wf.metadata.setdefault('id_map', {})['createvideo'] = createvideo.node.id

        # Outputs
        savevideo_2 = SaveVideo(
            _id='4852',
            filename_prefix='output_D',
            video=createvideo_2,
        )
        wf.metadata.setdefault('id_map', {})['savevideo_2'] = savevideo_2.node.id

        savevideo = SaveVideo(_id='4823', filename_prefix='output_F', video=createvideo)
        wf.metadata.setdefault('id_map', {})['savevideo'] = savevideo.node.id

        apply_ltx_lowvram(wf)
        resolution(384, 256, 9).apply(wf)
        ensure_custom_nodes(wf, READY_METADATA.get("requirements", {}).get("custom_nodes", []))
        return wf.finalize(PUBLIC_INPUTS, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output_F')

