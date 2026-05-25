# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, DualCLIPLoader, EmptyLTXVLatentVideo, KSamplerSelect, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LoadAudio, LoadImage, PreviewAudio, PreviewImage, RandomNoise, SamplerCustomAdvanced, SaveAudioMP3, SetLatentNoiseMask, SolidMask, TrimAudioDuration
from vibecomfy.nodes.gguf import UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import ImageResizeKJv2, VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVGemmaCLIPModelLoader, LowVRAMAudioVAELoader
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


DEFAULT_PROMPT = 'blurry, out of focus, overexposed, underexposed, low contrast, washed out colors, excessive noise, grainy texture, poor lighting, flickering, motion blur, distorted proportions, unnatural skin tones, deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, wrong hand count, artifacts around text, unreadable text on shirt or hat, incorrect lettering on cap (“PNTR”), incorrect t-shirt slogan (“JUST DO IT”), missing microphone, misplaced microphone, inconsistent perspective, camera shake, incorrect depth of field, background too sharp, background clutter, distracting reflections, harsh shadows, inconsistent lighting direction, color banding, cartoonish rendering, 3D CGI look, unrealistic materials, uncanny valley effect, incorrect ethnicity, wrong gender, exaggerated expressions, smiling, laughing, exaggerated sadness, wrong gaze direction, eyes looking at camera, mismatched lip sync, silent or muted audio, distorted voice, robotic voice, echo, background noise, off-sync audio, missing sniff sounds, incorrect dialogue, added dialogue, repetitive speech, jittery movement, awkward pauses, incorrect timing, unnatural transitions, inconsistent framing, tilted camera, missing door or shelves, missing shallow depth of field, flat lighting, inconsistent tone, cinematic oversaturation, stylized filters, or AI artifacts.'
DEFAULT_SEED = 24838260293478
GUIDE_STRENGTH = 2.5
MODEL_NAME = 'LTX-2-dev-Q4_K_S.gguf'
MODEL_NAME_10 = 'ltx-2-19b-distilled.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp8_e4m3fn.safetensors'
MODEL_NAME_3 = 'ltx-2-19b-embeddings_connector_dev_bf16.safetensors'
MODEL_NAME_4 = 'LTX2_video_vae_2_bf16.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_6 = 'ltx-2-19b-distilled-lora-384.safetensors'
MODEL_NAME_7 = 'ltx-2-19b-lora-camera-control-static.safetensors'
MODEL_NAME_8 = 'MelBandRoformer_fp32.safetensors'
MODEL_NAME_9 = 'ltx-2.3-22b-dev-fp8.safetensors'
WIDGET_0 = 'tiny'
WIDGET_0_2 = 'auto'
WIDGET_1 = '1.7B'
WIDGET_3 = ''
WIDGET_4 = 'no'
WIDGET_8 = 'none'


MODELS = {}

PUBLIC_INPUTS = {
'height': InputSpec(node=ref('imageresizekjv2'), field='height', default=1280),
'image': InputSpec(node=ref('loadimage'), field='image', default='ComfyUI_00126_.png', aliases=('input_image',)),
'model': InputSpec(node=ref('unetloadergguf'), field='unet_name', default=MODEL_NAME),
'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
'steps': InputSpec(node=ref('basicscheduler'), field='steps', default=8),
'width': InputSpec(node=ref('imageresizekjv2'), field='width', default=720),
}

READY_METADATA = ReadyMetadata.build(
    capability='audio_image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX-2-dev-Q4_K_S.gguf', 'LTX23_audio_vae_bf16.safetensors', 'LTX2_video_vae_2_bf16.safetensors', 'lcm', 'ltx-2-19b-distilled.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Seed (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='audio plus image-to-video',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_AU_IMG2V.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

        # Sampling
    ksamplerselect = KSamplerSelect(_id='154', sampler_name='lcm')
    wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
    # Inputs
    loadimage = LoadImage(
        _id='240',
        image='ComfyUI_00126_.png',
        _outputs=('IMAGE', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

    loadaudio = LoadAudio(_id='243', audio='man voice 1.mp3')
    wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id
    seed__rgthree_ = raw_call(wf, 'Seed (rgthree)', '290',
        widget_0=923615063061116,
        widget_1='',
        widget_2='',
        widget_3=WIDGET_3,
    )
    wf.metadata.setdefault('id_map', {})['seed__rgthree_'] = seed__rgthree_.node.id

    text_multiline = raw_call(wf, 'Text Multiline', '293',
        widget_0='video of a goblin talking to the camera',
    )
    wf.metadata.setdefault('id_map', {})['text_multiline'] = text_multiline.node.id

    unetloadergguf = UnetLoaderGGUF(_id='301', unet_name=MODEL_NAME)
    wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
    # Loaders
    dualcliploader = DualCLIPLoader(
        _id='303',
        clip_name1=MODEL_NAME_2,
        clip_name2=MODEL_NAME_3,
        type_='ltxv',
        device='default',
    )
    wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

    vaeloaderkj = VAELoaderKJ(
        _id='305',
        vae_name=MODEL_NAME_4,
        device='main_device',
        weight_dtype='bf16',
    )
    wf.metadata.setdefault('id_map', {})['vaeloaderkj'] = vaeloaderkj.node.id

    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='311', ckpt_name=MODEL_NAME_5)
    wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
    iamccs_ltx2_lorastack = raw_call(wf, 'IAMCCS_LTX2_LoRAStack', '321',
        widget_0=MODEL_NAME_6,
        widget_1=0.7,
        widget_2=MODEL_NAME_7,
        widget_3=1,
        widget_4=WIDGET_4,
        widget_5=0,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_lorastack'] = iamccs_ltx2_lorastack.node.id

    loadaudio_2 = LoadAudio(_id='347', audio='man voice 2 LONG.mp3')
    wf.metadata.setdefault('id_map', {})['loadaudio_2'] = loadaudio_2.node.id
    loadaudio_3 = LoadAudio(_id='376', audio='EdgarLetfall.mp3')
    wf.metadata.setdefault('id_map', {})['loadaudio_3'] = loadaudio_3.node.id
    melbandroformermodelloader = raw_call(wf, 'MelBandRoFormerModelLoader', '377',
        widget_0=MODEL_NAME_8,
    )
    wf.metadata.setdefault('id_map', {})['melbandroformermodelloader'] = melbandroformermodelloader.node.id

    # Inputs
    primitivefloat = raw_call(wf, 'PrimitiveFloat', '382', value=8)
    wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
    load_whisper__mtb_ = raw_call(wf, 'Load Whisper (mtb)', '405',
        widget_0=WIDGET_0,
        widget_1=True,
    )
    wf.metadata.setdefault('id_map', {})['load_whisper__mtb_'] = load_whisper__mtb_.node.id

    lowvramaudiovaeloader = LowVRAMAudioVAELoader(_id='411', ckpt_name=MODEL_NAME_9)
    wf.metadata.setdefault('id_map', {})['lowvramaudiovaeloader'] = lowvramaudiovaeloader.node.id
    ltxvgemmaclipmodelloader = LTXVGemmaCLIPModelLoader(
        _id='412',
        widget_0=MODEL_NAME_2,
        widget_1=MODEL_NAME_10,
        widget_2=1024,
    )
    wf.metadata.setdefault('id_map', {})['ltxvgemmaclipmodelloader'] = ltxvgemmaclipmodelloader.node.id

    # Loaders
    checkpointloadersimple = CheckpointLoaderSimple(
        _id='413',
        ckpt_name=MODEL_NAME_10,
        _outputs=('MODEL', 'CLIP', 'VAE'),
    )
    wf.metadata.setdefault('id_map', {})['checkpointloadersimple'] = checkpointloadersimple.node.id

    load_whisper__mtb__2 = raw_call(wf, 'Load Whisper (mtb)', '433',
        widget_0=WIDGET_0,
        widget_1=True,
    )
    wf.metadata.setdefault('id_map', {})['load_whisper__mtb__2'] = load_whisper__mtb__2.node.id

    iamccs_bus_group = raw_call(wf, 'IAMCCS_bus_group', '448',
        widget_0='both',
        widget_1=False,
        widget_2=True,
        widget_3=WIDGET_3,
        widget_4='',
        widget_5=False,
        widget_7='',
        widget_8=WIDGET_8,
        widget_9=False,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_bus_group'] = iamccs_bus_group.node.id

    iamccs_bus_group_2 = raw_call(wf, 'IAMCCS_bus_group', '450',
        widget_0='groups',
        widget_1=True,
        widget_10=False,
        widget_11=False,
        widget_12=False,
        widget_2=False,
        widget_3='models',
        widget_4='',
        widget_5=False,
        widget_7='',
        widget_8=WIDGET_8,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_bus_group_2'] = iamccs_bus_group_2.node.id

    iamccs_autolinkarguments = raw_call(wf, 'IAMCCS_AutoLinkArguments', '457',
        widget_0=False,
        widget_1=False,
        widget_10='Orange',
        widget_11='Green',
        widget_12='Gray',
        widget_13='White',
        widget_14='',
        widget_15='',
        widget_16='both',
        widget_18='',
        widget_2=False,
        widget_3=True,
        widget_4=False,
        widget_5='None',
        widget_6='',
        widget_7='TopToDown',
        widget_8='AvoidAll',
        widget_9=True,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_autolinkarguments'] = iamccs_autolinkarguments.node.id

    # Sampling
    samplercustomadvanced = SamplerCustomAdvanced(
        _id='467',
        _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
    )
    wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

    randomnoise = RandomNoise(
        _id='178',
        control_after_generate='fixed',
        widget_0=24838260293478,
        noise_seed=seed__rgthree_,
    )
    wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

    imageresizekjv2 = ImageResizeKJv2(
        _id='241',
        width=720,
        height=1280,
        upscale_method='lanczos',
        keep_proportion='crop',
        crop_position='top',
        divisible_by=32,
        device='cpu',
        image=loadimage.out('IMAGE'),
        _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

    iamccs_modelwithlora_ltx2 = raw_call(wf, 'IAMCCS_ModelWithLoRA_LTX2', '322',
        lora=iamccs_ltx2_lorastack.out(0),
        model=unetloadergguf,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_modelwithlora_ltx2'] = iamccs_modelwithlora_ltx2.node.id

    fl_chatterboxturbotts = raw_call(wf, 'FL_ChatterboxTurboTTS', '348',
        widget_0='Hello! I am a goblin <laugh>  a real goblin. <sarcastic>  Are You a real human?',
        widget_1=0.8,
        widget_2=1000,
        widget_3=0.95,
        widget_4=1.2,
        widget_5=42,
        widget_6='fixed',
        widget_7=False,
        widget_8=True,
        audio_prompt=loadaudio_2,
    )
    wf.metadata.setdefault('id_map', {})['fl_chatterboxturbotts'] = fl_chatterboxturbotts.node.id

    trimaudioduration = TrimAudioDuration(
        _id='366',
        widget_0=0,
        widget_1=20,
        audio=loadaudio_3,
    )
    wf.metadata.setdefault('id_map', {})['trimaudioduration'] = trimaudioduration.node.id

    cr_float_to_integer = raw_call(wf, 'CR Float To Integer', '384',
        _float=primitivefloat,
    )
    wf.metadata.setdefault('id_map', {})['cr_float_to_integer'] = cr_float_to_integer.node.id

    audio_to_text__mtb_ = raw_call(wf, 'Audio To Text (mtb)', '406',
        widget_0=WIDGET_0_2,
        widget_1=False,
        audio=loadaudio_3,
        pipeline=load_whisper__mtb_.out(0),
    )
    wf.metadata.setdefault('id_map', {})['audio_to_text__mtb_'] = audio_to_text__mtb_.node.id

    iamccs_ltx2_lorastackmodelio = raw_call(wf, 'IAMCCS_LTX2_LoRAStackModelIO', '416',
        widget_0=MODEL_NAME_6,
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4=WIDGET_4,
        widget_5=0,
        model=checkpointloadersimple.out('MODEL'),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_lorastackmodelio'] = iamccs_ltx2_lorastackmodelio.node.id

    iamccs_multiswitch_3 = raw_call(wf, 'IAMCCS_MultiSwitch', '452',
        widget_0='VAE AUDIO LOW',
        widget_1=True,
        input_01=lowvramaudiovaeloader,
        input_02=ltxvaudiovaeloader,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_multiswitch_3'] = iamccs_multiswitch_3.node.id

    iamccs_multiswitch_4 = raw_call(wf, 'IAMCCS_MultiSwitch', '453',
        widget_0='VAE h',
        widget_1=True,
        input_01=checkpointloadersimple.out('VAE'),
        input_02=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_multiswitch_4'] = iamccs_multiswitch_4.node.id

    iamccs_multiswitch_5 = raw_call(wf, 'IAMCCS_MultiSwitch', '454',
        widget_0='CLIP L',
        widget_1=True,
        input_01=ltxvgemmaclipmodelloader,
        input_02=dualcliploader,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_multiswitch_5'] = iamccs_multiswitch_5.node.id

    iamccs_autolinkconverter = raw_call(wf, 'IAMCCS_AutoLinkConverter', '456',
        arg=iamccs_autolinkarguments.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_autolinkconverter'] = iamccs_autolinkconverter.node.id

    ltxvpreprocess = LTXVPreprocess(
        _id='269',
        img_compression=33,
        image=imageresizekjv2.out('IMAGE'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

    # Outputs
    previewimage = PreviewImage(_id='275', images=imageresizekjv2.out('IMAGE'))
    wf.metadata.setdefault('id_map', {})['previewimage'] = previewimage.node.id
    saveaudiomp3 = SaveAudioMP3(_id='350', audio=fl_chatterboxturbotts.out(0))
    wf.metadata.setdefault('id_map', {})['saveaudiomp3'] = saveaudiomp3.node.id
    solidmask = SolidMask(
        _id='388',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=imageresizekjv2.out('HEIGHT'),
        width=imageresizekjv2.out('WIDTH'),
    )
    wf.metadata.setdefault('id_map', {})['solidmask'] = solidmask.node.id

    easy_cleangpuused = raw_call(wf, 'easy cleanGpuUsed', '407',
        anything=audio_to_text__mtb_.out(0),
    )
    wf.metadata.setdefault('id_map', {})['easy_cleangpuused'] = easy_cleangpuused.node.id

    iamccs_multiswitch_2 = raw_call(wf, 'IAMCCS_MultiSwitch', '451',
        widget_0='input_03',
        widget_1=True,
        input_01=iamccs_ltx2_lorastackmodelio.out(0),
        input_02=iamccs_modelwithlora_ltx2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_multiswitch_2'] = iamccs_multiswitch_2.node.id

    showtext_pysssss_2 = raw_call(wf, 'ShowText|pysssss', '373',
        widget_0=' How are you? I am from metallurgia, Elfica, a fantasy tale from our dear. Welcome to our show. And sit down and listen carefully.',
        text=easy_cleangpuused.out(0),
    )
    wf.metadata.setdefault('id_map', {})['showtext_pysssss_2'] = showtext_pysssss_2.node.id

    iamccs_gguf_accelerator = raw_call(wf, 'IAMCCS_GGUF_accelerator', '475',
        widget_0='auto_oom_safe',
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs_multiswitch_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_gguf_accelerator'] = iamccs_gguf_accelerator.node.id

    fb_qwen3ttsvoicecloneprompt = raw_call(wf, 'FB_Qwen3TTSVoiceClonePrompt', '379',
        widget_0='',
        widget_1=WIDGET_1,
        widget_2='auto',
        widget_3='fp32',
        widget_4='sage_attn',
        widget_5=True,
        widget_6=True,
        ref_audio=trimaudioduration,
        ref_text=showtext_pysssss_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['fb_qwen3ttsvoicecloneprompt'] = fb_qwen3ttsvoicecloneprompt.node.id

    iamccs_hwsupporter = raw_call(wf, 'IAMCCS_HwSupporter', '893',
        widget_0=WIDGET_0_2,
        widget_1=True,
        widget_10='auto',
        widget_11=False,
        widget_12=True,
        widget_13=False,
        widget_14='overwrite',
        widget_15='(not probed)',
        widget_16='run',
        widget_17='copy',
        widget_18=True,
        widget_2='manual',
        widget_3=0,
        widget_4=1,
        widget_5=0,
        widget_6='auto',
        widget_7=False,
        widget_8='off',
        widget_9='auto',
        clip=iamccs_multiswitch_5.out(0),
        model=iamccs_gguf_accelerator.out(0),
        vae=iamccs_multiswitch_4.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_hwsupporter'] = iamccs_hwsupporter.node.id

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='165',
        text=DEFAULT_PROMPT,
        clip=iamccs_hwsupporter.out(1),
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

    cliptextencode_2 = CLIPTextEncode(
        _id='169',
        text=text_multiline.out(0),
        clip=iamccs_hwsupporter.out(1),
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

    # Sampling
    basicscheduler = BasicScheduler(
        _id='238',
        scheduler=1,
        steps=1,
        widget_1=8,
        model=iamccs_hwsupporter.out(0),
    )
    wf.metadata.setdefault('id_map', {})['basicscheduler'] = basicscheduler.node.id

    iamccs_hwsupporterany = raw_call(wf, 'IAMCCS_HwSupporterAny', '375',
        widget_0='low_vram',
        widget_1=True,
        widget_10=False,
        widget_11='overwrite',
        widget_12='run',
        widget_13='copy',
        widget_14='copy',
        widget_15=True,
        widget_2='auto_used_plus',
        widget_3=1.25,
        widget_4=1,
        widget_5=0,
        widget_6='auto',
        widget_7='auto',
        widget_8=True,
        widget_9=True,
        input=fb_qwen3ttsvoicecloneprompt.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_hwsupporterany'] = iamccs_hwsupporterany.node.id

    showtext_pysssss_3 = raw_call(wf, 'ShowText|pysssss', '974',
        text=iamccs_hwsupporter.out(3),
    )
    wf.metadata.setdefault('id_map', {})['showtext_pysssss_3'] = showtext_pysssss_3.node.id

    ltxvconditioning = LTXVConditioning(
        _id='164',
        frame_rate=primitivefloat,
        negative=cliptextencode,
        positive=cliptextencode_2,
        _outputs=('POSITIVE', 'NEGATIVE'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

    fb_qwen3ttsvoiceclone = raw_call(wf, 'FB_Qwen3TTSVoiceClone', '374',
        widget_0='this is only a test! check it out!',
        widget_1=WIDGET_1,
        widget_10=20,
        widget_11=1,
        widget_12=1.05,
        widget_13=True,
        widget_14='auto',
        widget_15=True,
        widget_2='auto',
        widget_3='bf16',
        widget_4='Auto',
        widget_5='',
        widget_6=663647919912928,
        widget_7='fixed',
        widget_8=2048,
        widget_9=0.8,
        ref_audio=trimaudioduration,
        ref_text=showtext_pysssss_2.out(0),
        voice_clone_prompt=iamccs_hwsupporterany.out(0),
    )
    wf.metadata.setdefault('id_map', {})['fb_qwen3ttsvoiceclone'] = fb_qwen3ttsvoiceclone.node.id

    # Conditioning
    cfgguider = CFGGuider(
        _id='153',
        cfg=GUIDE_STRENGTH,
        model=iamccs_hwsupporter.out(0),
        negative=ltxvconditioning.out('NEGATIVE'),
        positive=ltxvconditioning.out('POSITIVE'),
    )
    wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

    iamccs_multiswitch = raw_call(wf, 'IAMCCS_MultiSwitch', '441',
        widget_0='input_6',
        widget_1=True,
        input_01=loadaudio,
        input_03=fl_chatterboxturbotts.out(0),
        input_05=fb_qwen3ttsvoiceclone.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_multiswitch'] = iamccs_multiswitch.node.id

    audio_duration__mtb_ = raw_call(wf, 'Audio Duration (mtb)', '363',
        audio=iamccs_multiswitch.out(0),
    )
    wf.metadata.setdefault('id_map', {})['audio_duration__mtb_'] = audio_duration__mtb_.node.id

    melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '365',
        audio=iamccs_multiswitch.out(0),
        model=melbandroformermodelloader.out(0),
    )
    wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

    setnode = raw_call(wf, 'SetNode', '362',
        widget_0='audio_vocals',
        AUDIO=melbandroformersampler.out(0),
    )
    wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

    mathexpression_pysssss = raw_call(wf, 'MathExpression|pysssss', '364',
        widget_0='((a*0.001)*b)',
        a=audio_duration__mtb_.out(0),
        b=cr_float_to_integer.out(0),
    )
    wf.metadata.setdefault('id_map', {})['mathexpression_pysssss'] = mathexpression_pysssss.node.id

    audio_to_text__mtb__2 = raw_call(wf, 'Audio To Text (mtb)', '409',
        widget_0=WIDGET_0_2,
        widget_1=False,
        audio=melbandroformersampler.out(0),
        pipeline=load_whisper__mtb__2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['audio_to_text__mtb__2'] = audio_to_text__mtb__2.node.id

    # Sampling
    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='162',
        width=imageresizekjv2.out('WIDTH'),
        height=imageresizekjv2.out('HEIGHT'),
        length=mathexpression_pysssss.out(0),
    )
    wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

    previewaudio = PreviewAudio(_id='380', audio=setnode.out(0))
    wf.metadata.setdefault('id_map', {})['previewaudio'] = previewaudio.node.id
    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='387',
        audio=setnode.out(0),
        audio_vae=iamccs_multiswitch_3.out(0),
    )
    wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

    easy_cleangpuused_2 = raw_call(wf, 'easy cleanGpuUsed', '410',
        anything=audio_to_text__mtb__2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['easy_cleangpuused_2'] = easy_cleangpuused_2.node.id

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='239',
        widget_0=0.8,
        widget_1=False,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=iamccs_hwsupporter.out(2),
    )
    wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

    showtext_pysssss = raw_call(wf, 'ShowText|pysssss', '370',
        widget_0=" Hey, how are you? Well, I suppose you already know me, but wait a moment. Are human? I mean, I am not. So I've been thinking about it all day. Believe me.",
        text=easy_cleangpuused_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['showtext_pysssss'] = showtext_pysssss.node.id

    setlatentnoisemask = SetLatentNoiseMask(
        _id='389',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )
    wf.metadata.setdefault('id_map', {})['setlatentnoisemask'] = setlatentnoisemask.node.id

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='166',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace,
    )
    wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

    iamccs_sampleradvancedversion1 = raw_call(wf, 'IAMCCS_SamplerAdvancedVersion1', '474',
        widget_0=True,
        widget_1=True,
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=basicscheduler,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_sampleradvancedversion1'] = iamccs_sampleradvancedversion1.node.id

    ltxvseparateavlatent = LTXVSeparateAVLatent(
        _id='245',
        av_latent=iamccs_sampleradvancedversion1.out(0),
        _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

    iamccs_vaedecodetiledsafe = raw_call(wf, 'IAMCCS_VAEDecodeTiledSafe', '234',
        widget_0=True,
        widget_1='manual',
        widget_10='copy',
        widget_2=512,
        widget_3=32,
        widget_4=64,
        widget_5=32,
        widget_6=True,
        widget_7='overwrite',
        widget_8='run',
        widget_9='copy',
        samples=ltxvseparateavlatent.out('VIDEO_LATENT'),
        vae=iamccs_hwsupporter.out(2),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_vaedecodetiledsafe'] = iamccs_vaedecodetiledsafe.node.id

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='190',
        audio=iamccs_multiswitch.out(0),
        images=iamccs_vaedecodetiledsafe.out(0),
    )
    wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

    return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

