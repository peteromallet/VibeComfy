# vibecomfy: manual
# Cannot reemit: IAMCCS_VideoCombineFromDir is not a known output node type for
# auto-detection, and source JSON has 42 hard schema errors blocking port convert.
# WIDGET_N constants are permanent until source JSON is repaired.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, KSamplerSelect, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, UNETLoader
from vibecomfy.nodes.gguf import UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import VAELoaderKJ
from vibecomfy.nodes.videohelpersuite import VHS_LoadAudioUpload

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


CONTROL_AFTER_GENERATE = 'randomize'
DEFAULT_FRAMES = 5
DEFAULT_PROMPT = 'cinematic image to video shot of a singer actor acting and singing a song during a musical, intense expression, coherent motion, smooth camera movement, high detail, stable composition, audio-reactive motion'
DEFAULT_PROMPT_2 = 'flicker, jitter, low quality, bad anatomy, static image, frozen frame, deformed motion'
DEFAULT_SEED = 851629932274714
DEFAULT_SEED_2 = 264060544821466
DEFAULT_SEED_3 = 606399719654025
GUIDE_STRENGTH = 0.7
GUIDE_STRENGTH_2 = 2.5
MODEL_NAME = 'ltx-2.3-22b-dev-Q4_K_S.gguf'
MODEL_NAME_2 = 'gemma_3_12B_it_fp8_e4m3fn.safetensors'
MODEL_NAME_3 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_4 = 'ltx-2.3-22b-dev_video_vae.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_6 = 'MelBandRoformer_fp32.safetensors'
MODEL_NAME_7 = 'ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors'
WIDGET_0 = 'iamccs_vae_frames/30s_free_low_ram/seg0'
WIDGET_1 = 'left_context_only'
WIDGET_10 = 'videoclip_audio_24fps'
WIDGET_11 = ''
WIDGET_1_2 = 'all'
WIDGET_2 = 'jpg'
WIDGET_4 = 'use_timeline_cursor'
WIDGET_4_2 = 'source'
WIDGET_5 = 'snap_to_video_duration'
WIDGET_5_2 = 'auto'
WIDGET_5_3 = 'cut'
WIDGET_6 = 'soft_clamp'
WIDGET_7 = 'none'
WIDGET_8 = 'native_workflow_safe'
WIDGET_9 = 'iamccs_seam_debug'


MODELS = {
    'ltx23_audio_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', subdir='checkpoints'),
}

PUBLIC_INPUTS = {
'frames': InputSpec(node=ref('emptyltxvlatentvideo'), field='length', default=DEFAULT_FRAMES),
'height': InputSpec(node=ref('emptyltxvlatentvideo'), field='height', default=256),
'image': InputSpec(node=ref('loadimage'), field='image', default='ChatGPT Image Mar 27, 2026, 08_27_32 AM.png', aliases=('input_image',)),
'model': InputSpec(node=ref('ltxvaudiovaeloader'), field='ckpt_name', default=MODEL_NAME_5),
'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
'width': InputSpec(node=ref('emptyltxvlatentvideo'), field='width', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='audio_extended_multisegment_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ResizeImagesByLongerEdge', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    approach='low-RAM three-segment audio extension',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

        # Inputs
    loadimage = LoadImage(
        _id='1',
        image='ChatGPT Image Mar 27, 2026, 08_27_32 AM.png',
        _outputs=('IMAGE', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

    vhs_loadaudioupload = VHS_LoadAudioUpload(
        _id='4',
        _outputs=('AUDIO', 'DURATION'),
    )
    wf.metadata.setdefault('id_map', {})['vhs_loadaudioupload'] = vhs_loadaudioupload.node.id

    unetloadergguf = UnetLoaderGGUF(_id='5', unet_name=MODEL_NAME)
    wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
    # Loaders
    dualcliploader = DualCLIPLoader(
        _id='7',
        clip_name1=MODEL_NAME_2,
        clip_name2=MODEL_NAME_3,
        type_='ltxv',
        device='default',
    )
    wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

    # Sampling
    ksamplerselect = KSamplerSelect(_id='12', sampler_name='euler')
    wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
    manualsigmas = ManualSigmas(
        _id='13',
        sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

    vaeloaderkj = VAELoaderKJ(
        _id='14',
        vae_name=MODEL_NAME_4,
        device='main_device',
        weight_dtype='bf16',
    )
    wf.metadata.setdefault('id_map', {})['vaeloaderkj'] = vaeloaderkj.node.id

    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='15', ckpt_name=MODEL_NAME_5)
    wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
    solidmask = SolidMask(
        _id='16',
        widget_0=0,
        widget_1=1024,
        widget_2=1024,
    )
    wf.metadata.setdefault('id_map', {})['solidmask'] = solidmask.node.id

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='17',
        width=256,
        height=256,
        length=DEFAULT_FRAMES,
        widget_0=256,
        widget_1=256,
        widget_2=5,
    )
    wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

    randomnoise = RandomNoise(
        _id='25',
        noise_seed=DEFAULT_SEED,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )
    wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

    ltxvpreprocess_2 = LTXVPreprocess(_id='31', img_compression=33)
    wf.metadata.setdefault('id_map', {})['ltxvpreprocess_2'] = ltxvpreprocess_2.node.id
    emptyltxvlatentvideo_2 = EmptyLTXVLatentVideo(
        _id='32',
        width=256,
        height=256,
        length=DEFAULT_FRAMES,
        widget_0=256,
        widget_1=256,
        widget_2=5,
    )
    wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo_2'] = emptyltxvlatentvideo_2.node.id

    randomnoise_2 = RandomNoise(
        _id='39',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )
    wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

    ltxvpreprocess_3 = LTXVPreprocess(_id='45', img_compression=33)
    wf.metadata.setdefault('id_map', {})['ltxvpreprocess_3'] = ltxvpreprocess_3.node.id
    emptyltxvlatentvideo_3 = EmptyLTXVLatentVideo(
        _id='46',
        width=256,
        height=256,
        length=DEFAULT_FRAMES,
        widget_0=256,
        widget_1=256,
        widget_2=5,
    )
    wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo_3'] = emptyltxvlatentvideo_3.node.id

    randomnoise_3 = RandomNoise(
        _id='53',
        noise_seed=DEFAULT_SEED_3,
        control_after_generate=CONTROL_AFTER_GENERATE,
    )
    wf.metadata.setdefault('id_map', {})['randomnoise_3'] = randomnoise_3.node.id

    # Loaders
    unetloader = UNETLoader(_id='77', unet_name=MODEL_NAME_6)
    wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
    resizeimagemasknode = ResizeImageMaskNode(
        _id='2',
        resize_type='scale dimensions',
        scale_method=1080,
        widget_3='center',
        widget_4='lanczos',
        input=loadimage.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='6',
        lora_name=MODEL_NAME_7,
        strength_model=GUIDE_STRENGTH,
        model=unetloadergguf,
    )
    wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='8',
        text=DEFAULT_PROMPT,
        clip=dualcliploader,
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

    cliptextencode_2 = CLIPTextEncode(
        _id='9',
        text=DEFAULT_PROMPT_2,
        clip=dualcliploader,
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

    iamccs_audioextensionmath = raw_call(wf, 'IAMCCS_AudioExtensionMath', '20',
        widget_0=24,
        widget_1=0,
        widget_2=240,
        widget_3=240,
        widget_4=True,
        widget_5=240,
        widget_6=0,
        audio=vhs_loadaudioupload.out('AUDIO'),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audioextensionmath'] = iamccs_audioextensionmath.node.id

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        _id='3',
        longer_edge=1536,
        images=resizeimagemasknode,
    )
    wf.metadata.setdefault('id_map', {})['resizeimagesbylongeredge'] = resizeimagesbylongeredge.node.id

    ltxvconditioning = LTXVConditioning(
        _id='10',
        frame_rate=8,
        negative=cliptextencode_2,
        positive=cliptextencode,
        _outputs=('POSITIVE', 'NEGATIVE'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

    iamccs_audioextender = raw_call(wf, 'IAMCCS_AudioExtender', '21',
        widget_0=24,
        widget_1=WIDGET_1,
        widget_10=240,
        widget_11=240,
        widget_12=0,
        widget_13=0,
        widget_14=240,
        widget_15=240,
        widget_2=0.5,
        widget_3=0,
        widget_4=WIDGET_4,
        widget_5=WIDGET_5,
        widget_6=WIDGET_6,
        widget_7=0,
        widget_8=10,
        widget_9=240,
        audio=vhs_loadaudioupload.out('AUDIO'),
        effective_unique_frames=iamccs_audioextensionmath.out(3),
        segment_start_frames=iamccs_audioextensionmath.out(1),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audioextender'] = iamccs_audioextender.node.id

    iamccs_audiotimelinegate = raw_call(wf, 'IAMCCS_AudioTimelineGate', '30',
        widget_0=1,
        widget_1=True,
        widget_2=1,
        widget_3=True,
        widget_4=0,
        widget_5=0,
        cursor_frames_out=iamccs_audioextensionmath.out(0),
        effective_unique_frames=iamccs_audioextensionmath.out(3),
        is_last_segment=iamccs_audioextensionmath.out(8),
        remaining_frames_after=iamccs_audioextensionmath.out(7),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audiotimelinegate'] = iamccs_audiotimelinegate.node.id

    cfgguider = CFGGuider(
        _id='11',
        cfg=GUIDE_STRENGTH_2,
        model=loraloadermodelonly,
        negative=ltxvconditioning.out('NEGATIVE'),
        positive=ltxvconditioning.out('POSITIVE'),
    )
    wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

    ltxvpreprocess = LTXVPreprocess(
        _id='18',
        img_compression=33,
        image=resizeimagesbylongeredge,
    )
    wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='22',
        audio=iamccs_audioextender.out(0),
        audio_vae=ltxvaudiovaeloader,
    )
    wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

    iamccs_audioextensionmath_2 = raw_call(wf, 'IAMCCS_AudioExtensionMath', '34',
        widget_0=24,
        widget_1=1,
        widget_2=249,
        widget_3=240,
        widget_4=True,
        widget_5=240,
        widget_6=0,
        audio=vhs_loadaudioupload.out('AUDIO'),
        cursor_frames_in=iamccs_audiotimelinegate.out(3),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audioextensionmath_2'] = iamccs_audioextensionmath_2.node.id

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='19',
        widget_0=1,
        widget_1=False,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

    setlatentnoisemask = SetLatentNoiseMask(
        _id='23',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )
    wf.metadata.setdefault('id_map', {})['setlatentnoisemask'] = setlatentnoisemask.node.id

    iamccs_audioextender_2 = raw_call(wf, 'IAMCCS_AudioExtender', '35',
        widget_0=24,
        widget_1=WIDGET_1,
        widget_10=249,
        widget_11=240,
        widget_12=0,
        widget_13=240,
        widget_14=240,
        widget_15=240,
        widget_2=0.5,
        widget_3=0,
        widget_4=WIDGET_4,
        widget_5=WIDGET_5,
        widget_6=WIDGET_6,
        widget_7=1,
        widget_8=10,
        widget_9=240,
        audio=vhs_loadaudioupload.out('AUDIO'),
        effective_unique_frames=iamccs_audioextensionmath_2.out(3),
        segment_start_frames=iamccs_audioextensionmath_2.out(1),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audioextender_2'] = iamccs_audioextender_2.node.id

    iamccs_audiotimelinegate_2 = raw_call(wf, 'IAMCCS_AudioTimelineGate', '44',
        widget_0=1,
        widget_1=True,
        widget_2=1,
        widget_3=True,
        widget_4=0,
        widget_5=0,
        cursor_frames_out=iamccs_audioextensionmath_2.out(0),
        effective_unique_frames=iamccs_audioextensionmath_2.out(3),
        is_last_segment=iamccs_audioextensionmath_2.out(8),
        remaining_frames_after=iamccs_audioextensionmath_2.out(7),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audiotimelinegate_2'] = iamccs_audiotimelinegate_2.node.id

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='24',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace,
    )
    wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

    ltxvaudiovaeencode_2 = LTXVAudioVAEEncode(
        _id='36',
        audio=iamccs_audioextender_2.out(0),
        audio_vae=ltxvaudiovaeloader,
    )
    wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode_2'] = ltxvaudiovaeencode_2.node.id

    iamccs_audioextensionmath_3 = raw_call(wf, 'IAMCCS_AudioExtensionMath', '48',
        widget_0=24,
        widget_1=2,
        widget_2=249,
        widget_3=240,
        widget_4=True,
        widget_5=240,
        widget_6=0,
        audio=vhs_loadaudioupload.out('AUDIO'),
        cursor_frames_in=iamccs_audiotimelinegate_2.out(3),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audioextensionmath_3'] = iamccs_audioextensionmath_3.node.id

    # Sampling
    samplercustomadvanced = SamplerCustomAdvanced(
        _id='26',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
        _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
    )
    wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

    setlatentnoisemask_2 = SetLatentNoiseMask(
        _id='37',
        mask=solidmask,
        samples=ltxvaudiovaeencode_2,
    )
    wf.metadata.setdefault('id_map', {})['setlatentnoisemask_2'] = setlatentnoisemask_2.node.id

    iamccs_audioextender_3 = raw_call(wf, 'IAMCCS_AudioExtender', '49',
        widget_0=24,
        widget_1=WIDGET_1,
        widget_10=249,
        widget_11=240,
        widget_12=0,
        widget_13=480,
        widget_14=240,
        widget_15=240,
        widget_2=0.5,
        widget_3=0,
        widget_4=WIDGET_4,
        widget_5=WIDGET_5,
        widget_6=WIDGET_6,
        widget_7=2,
        widget_8=10,
        widget_9=240,
        audio=vhs_loadaudioupload.out('AUDIO'),
        effective_unique_frames=iamccs_audioextensionmath_3.out(3),
        segment_start_frames=iamccs_audioextensionmath_3.out(1),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audioextender_3'] = iamccs_audioextender_3.node.id

    iamccs_audiotimelinegate_3 = raw_call(wf, 'IAMCCS_AudioTimelineGate', '58',
        widget_0=1,
        widget_1=True,
        widget_2=1,
        widget_3=True,
        widget_4=0,
        widget_5=0,
        cursor_frames_out=iamccs_audioextensionmath_3.out(0),
        effective_unique_frames=iamccs_audioextensionmath_3.out(3),
        is_last_segment=iamccs_audioextensionmath_3.out(8),
        remaining_frames_after=iamccs_audioextensionmath_3.out(7),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_audiotimelinegate_3'] = iamccs_audiotimelinegate_3.node.id

    ltxvseparateavlatent = LTXVSeparateAVLatent(
        _id='27',
        av_latent=samplercustomadvanced.out('OUTPUT'),
        _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

    ltxvaudiovaeencode_3 = LTXVAudioVAEEncode(
        _id='50',
        audio=iamccs_audioextender_3.out(0),
        audio_vae=ltxvaudiovaeloader,
    )
    wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode_3'] = ltxvaudiovaeencode_3.node.id

    setlatentnoisemask_3 = SetLatentNoiseMask(
        _id='51',
        mask=solidmask,
        samples=ltxvaudiovaeencode_3,
    )
    wf.metadata.setdefault('id_map', {})['setlatentnoisemask_3'] = setlatentnoisemask_3.node.id

    iamccs_vaedecodetodisk = raw_call(wf, 'IAMCCS_VAEDecodeToDisk', '60',
        widget_0=WIDGET_0,
        widget_1='seg0',
        widget_10=True,
        widget_2=WIDGET_2,
        widget_3=95,
        widget_4=True,
        widget_5=WIDGET_5_2,
        widget_6=512,
        widget_7=64,
        widget_8=True,
        widget_9=WIDGET_9,
        samples=ltxvseparateavlatent.out('VIDEO_LATENT'),
        vae=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_vaedecodetodisk'] = iamccs_vaedecodetodisk.node.id

    iamccs_ltx2_extensionmodule_disk = raw_call(wf, 'IAMCCS_LTX2_ExtensionModule_Disk', '29',
        widget_0=WIDGET_0,
        widget_1='iamccs_extension_disk/30s_free_low_ram/seg0_extended',
        widget_10=WIDGET_10,
        widget_11=WIDGET_11,
        widget_12=1,
        widget_2='iamccs_extension_disk/30s_free_low_ram/seg0_start',
        widget_3=9,
        widget_4=WIDGET_4_2,
        widget_5=WIDGET_5_3,
        widget_6=True,
        widget_7=WIDGET_7,
        widget_8=WIDGET_8,
        widget_9='none',
        source_dir=iamccs_vaedecodetodisk.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_extensionmodule_disk'] = iamccs_ltx2_extensionmodule_disk.node.id

    iamccs_startdirtovideolatent = raw_call(wf, 'IAMCCS_StartDirToVideoLatent', '33',
        widget_0='iamccs_extension_disk/30s_free_low_ram/seg0_start',
        widget_1=WIDGET_1_2,
        widget_2=9,
        widget_3=0,
        widget_4=1,
        widget_5=True,
        widget_6=33,
        latent=emptyltxvlatentvideo_2,
        start_dir=iamccs_ltx2_extensionmodule_disk.out(1),
        vae=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_startdirtovideolatent'] = iamccs_startdirtovideolatent.node.id

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        _id='38',
        audio_latent=setlatentnoisemask_2,
        video_latent=iamccs_startdirtovideolatent.out(0),
    )
    wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

    samplercustomadvanced_2 = SamplerCustomAdvanced(
        _id='40',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
        _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
    )
    wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

    ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
        _id='41',
        av_latent=samplercustomadvanced_2.out('OUTPUT'),
        _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

    iamccs_vaedecodetodisk_2 = raw_call(wf, 'IAMCCS_VAEDecodeToDisk', '61',
        widget_0='iamccs_vae_frames/30s_free_low_ram/seg1',
        widget_1='seg1',
        widget_10=True,
        widget_2=WIDGET_2,
        widget_3=95,
        widget_4=True,
        widget_5=WIDGET_5_2,
        widget_6=512,
        widget_7=64,
        widget_8=True,
        widget_9=WIDGET_9,
        samples=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
        vae=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_vaedecodetodisk_2'] = iamccs_vaedecodetodisk_2.node.id

    iamccs_ltx2_extensionmodule_disk_2 = raw_call(wf, 'IAMCCS_LTX2_ExtensionModule_Disk', '43',
        widget_0=WIDGET_0,
        widget_1='iamccs_extension_disk/30s_free_low_ram/seg1_extended',
        widget_10=WIDGET_10,
        widget_11=WIDGET_11,
        widget_12=0,
        widget_2='iamccs_extension_disk/30s_free_low_ram/seg1_start',
        widget_3=9,
        widget_4=WIDGET_4_2,
        widget_5=WIDGET_5_3,
        widget_6=True,
        widget_7=WIDGET_7,
        widget_8=WIDGET_8,
        widget_9='none',
        new_dir=iamccs_vaedecodetodisk_2.out(0),
        source_dir=iamccs_ltx2_extensionmodule_disk.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_extensionmodule_disk_2'] = iamccs_ltx2_extensionmodule_disk_2.node.id

    iamccs_startdirtovideolatent_2 = raw_call(wf, 'IAMCCS_StartDirToVideoLatent', '47',
        widget_0='iamccs_extension_disk/30s_free_low_ram/seg1_start',
        widget_1=WIDGET_1_2,
        widget_2=9,
        widget_3=0,
        widget_4=1,
        widget_5=True,
        widget_6=33,
        latent=emptyltxvlatentvideo_3,
        start_dir=iamccs_ltx2_extensionmodule_disk_2.out(1),
        vae=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_startdirtovideolatent_2'] = iamccs_startdirtovideolatent_2.node.id

    ltxvconcatavlatent_3 = LTXVConcatAVLatent(
        _id='52',
        audio_latent=setlatentnoisemask_3,
        video_latent=iamccs_startdirtovideolatent_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_3'] = ltxvconcatavlatent_3.node.id

    samplercustomadvanced_3 = SamplerCustomAdvanced(
        _id='54',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_3,
        noise=randomnoise_3,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
        _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
    )
    wf.metadata.setdefault('id_map', {})['samplercustomadvanced_3'] = samplercustomadvanced_3.node.id

    ltxvseparateavlatent_3 = LTXVSeparateAVLatent(
        _id='55',
        av_latent=samplercustomadvanced_3.out('OUTPUT'),
        _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_3'] = ltxvseparateavlatent_3.node.id

    iamccs_vaedecodetodisk_3 = raw_call(wf, 'IAMCCS_VAEDecodeToDisk', '62',
        widget_0='iamccs_vae_frames/30s_free_low_ram/seg2',
        widget_1='seg2',
        widget_10=True,
        widget_2=WIDGET_2,
        widget_3=95,
        widget_4=True,
        widget_5=WIDGET_5_2,
        widget_6=512,
        widget_7=64,
        widget_8=True,
        widget_9=WIDGET_9,
        samples=ltxvseparateavlatent_3.out('VIDEO_LATENT'),
        vae=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_vaedecodetodisk_3'] = iamccs_vaedecodetodisk_3.node.id

    iamccs_ltx2_extensionmodule_disk_3 = raw_call(wf, 'IAMCCS_LTX2_ExtensionModule_Disk', '57',
        widget_0=WIDGET_0,
        widget_1='iamccs_extension_disk/30s_free_low_ram/final_extended',
        widget_10=WIDGET_10,
        widget_11=WIDGET_11,
        widget_12=1,
        widget_2='iamccs_extension_disk/30s_free_low_ram/final_start',
        widget_3=9,
        widget_4=WIDGET_4_2,
        widget_5=WIDGET_5_3,
        widget_6=True,
        widget_7=WIDGET_7,
        widget_8=WIDGET_8,
        widget_9='none',
        new_dir=iamccs_vaedecodetodisk_3.out(0),
        source_dir=iamccs_ltx2_extensionmodule_disk_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_extensionmodule_disk_3'] = iamccs_ltx2_extensionmodule_disk_3.node.id

    iamccs_videocombinefromdir = raw_call(wf, 'IAMCCS_VideoCombineFromDir', '59',
        widget_0='iamccs_extension_disk/30s_free_low_ram/final_extended',
        widget_1=24,
        widget_2='IAMCCS/LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM',
        widget_3=19,
        widget_4='yuv420p',
        widget_5=True,
        audio=vhs_loadaudioupload.out('AUDIO'),
        frames_dir=iamccs_ltx2_extensionmodule_disk_3.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_videocombinefromdir'] = iamccs_videocombinefromdir.node.id

    return wf.finalize(
        PUBLIC_INPUTS,
        output_node=iamccs_videocombinefromdir,
        output_type='IAMCCS_VideoCombineFromDir',
        name='video',
        artifact_kind='video',
        mime_type='video/mp4',
        expected_cardinality='one',
        filename_prefix='IAMCCS/LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM',
    )
