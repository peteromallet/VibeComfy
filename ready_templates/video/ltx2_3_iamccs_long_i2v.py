# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioConcat, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, DualCLIPLoader, EmptyImage, LTXVAudioVAELoader, LTXVConditioning, LatentUpscaleModelLoader, LoadImage, PrimitiveStringMultiline, SaveVideo
from vibecomfy.nodes.gguf import UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVGemmaCLIPModelLoader, LowVRAMAudioVAELoader

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


CODEC = 'h264'
DEFAULT_FPS = 8
FORMAT = 'mp4'
MODEL_NAME = 'ltx-2-19b-distilled.safetensors'
MODEL_NAME_10 = 'ltx-2-19b-embeddings_connector_dev_bf16.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp8_e4m3fn.safetensors'
MODEL_NAME_3 = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_4 = 'ltx-2-spatial-upscaler-x2-1.0.safetensors'
MODEL_NAME_5 = 'LTX-2-dev-Q5_K_S.gguf'
MODEL_NAME_6 = 'ltx-2-19b-distilled-lora-384.safetensors'
MODEL_NAME_7 = 'ltx-2-19b-lora-camera-control-dolly-right.safetensors'
MODEL_NAME_8 = 'LTX2_video_vae_2_bf16.safetensors'
MODEL_NAME_9 = 'LTX23_audio_vae_bf16.safetensors'
WIDGET_0 = 'after'
WIDGET_1 = 'source'
WIDGET_10 = 'none'
WIDGET_14 = 'target_extension_ltx2'
WIDGET_2 = 'linear_blend'
WIDGET_4 = 'a-1'
WIDGET_5 = 'all_or_nothing'


MODELS = {}

PUBLIC_INPUTS = {
'image': InputSpec(node=ref('loadimage'), field='image', default='z-image_00255_.png', aliases=('input_image',)),
'model': InputSpec(node=ref('checkpointloadersimple'), field='ckpt_name', default=MODEL_NAME),
'prompt': InputSpec(node=ref('primitivestringmultiline'), field='value', default='Cinematic action packed shot. the man says silently: "We need to run." the camera zooms in on his mouth then immediately screams: "NOW!". the camera zooms back out, he turns around, and starts running away, the camera tracks his run in hand held style.'),
}

READY_METADATA = ReadyMetadata.build(
    capability='long_image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX-2-dev-Q5_K_S.gguf', 'LTX23_audio_vae_bf16.safetensors', 'LTX2_video_vae_2_bf16.safetensors', 'ltx-2-19b-distilled.safetensors', 'ltx-2-spatial-upscaler-x2-1.0.safetensors', 'ltx-2.3-22b-dev-fp8.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTXVAudioVAELoader', 'LTXVConditioning', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Any Switch (rgthree)', 'Fast Groups Muter (rgthree)'], 'pip_packages': [], 'status': 'pinned'}},
    approach='long low-VRAM image-to-video',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    primitivestringmultiline = PrimitiveStringMultiline(
        _id='5175',
        value='Cinematic action packed shot. the man says silently: "We need to run." the camera zooms in on his mouth then immediately screams: "NOW!". the camera zooms back out, he turns around, and starts running away, the camera tracks his run in hand held style.',
    )
    wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

    # Loaders
    checkpointloadersimple = CheckpointLoaderSimple(
        _id='5176',
        ckpt_name=MODEL_NAME,
        _outputs=('MODEL', 'CLIP', 'VAE'),
    )
    wf.metadata.setdefault('id_map', {})['checkpointloadersimple'] = checkpointloadersimple.node.id

    ltxvgemmaclipmodelloader = LTXVGemmaCLIPModelLoader(
        _id='5178',
        widget_0=MODEL_NAME_2,
        widget_1=MODEL_NAME,
        widget_2=1024,
    )
    wf.metadata.setdefault('id_map', {})['ltxvgemmaclipmodelloader'] = ltxvgemmaclipmodelloader.node.id

    # Inputs
    loadimage = LoadImage(
        _id='5180',
        image='z-image_00255_.png',
        _outputs=('IMAGE', 'MASK'),
    )
    wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

    lowvramaudiovaeloader = LowVRAMAudioVAELoader(
        _id='5188',
        ckpt_name=MODEL_NAME_3,
    )
    wf.metadata.setdefault('id_map', {})['lowvramaudiovaeloader'] = lowvramaudiovaeloader.node.id

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='5210',
        model_name=MODEL_NAME_4,
    )
    wf.metadata.setdefault('id_map', {})['latentupscalemodelloader'] = latentupscalemodelloader.node.id

    unetloadergguf = UnetLoaderGGUF(_id='5215', unet_name=MODEL_NAME_5)
    wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
    iamccs_ltx2_lorastackstaged = raw_call(wf, 'IAMCCS_LTX2_LoRAStackStaged', '5218',
        widget_0=MODEL_NAME_6,
        widget_1=1,
        widget_2=1,
        widget_3=MODEL_NAME_7,
        widget_4=0,
        widget_5=0,
        widget_6='no',
        widget_7=0,
        widget_8=0,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_lorastackstaged'] = iamccs_ltx2_lorastackstaged.node.id

    vaeloaderkj = VAELoaderKJ(
        _id='5220',
        vae_name=MODEL_NAME_8,
        device='main_device',
        weight_dtype='bf16',
    )
    wf.metadata.setdefault('id_map', {})['vaeloaderkj'] = vaeloaderkj.node.id

    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='5221', ckpt_name=MODEL_NAME_9)
    wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
    # Loaders
    dualcliploader = DualCLIPLoader(
        _id='5222',
        clip_name1=MODEL_NAME_2,
        clip_name2=MODEL_NAME_10,
        type_='ltxv',
        device='default',
    )
    wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

    iamccs_ltx2_frameratesync = raw_call(wf, 'IAMCCS_LTX2_FrameRateSync', '5225',
        widget_0=24,
        widget_1='fixed',
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_frameratesync'] = iamccs_ltx2_frameratesync.node.id

    primitivestringmultiline_2 = PrimitiveStringMultiline(
        _id='5232',
        value='man runs away from camera. the camera cranes up and show him run into the distance down the street at a busy New York night.',
    )
    wf.metadata.setdefault('id_map', {})['primitivestringmultiline_2'] = primitivestringmultiline_2.node.id

    fast_groups_muter__rgthree_ = raw_call(wf, 'Fast Groups Muter (rgthree)', '5265',
    )
    wf.metadata.setdefault('id_map', {})['fast_groups_muter__rgthree_'] = fast_groups_muter__rgthree_.node.id

    primitivestringmultiline_3 = PrimitiveStringMultiline(
        _id='9001',
        value='the camera cranes up and show the whole streets of new york.',
    )
    wf.metadata.setdefault('id_map', {})['primitivestringmultiline_3'] = primitivestringmultiline_3.node.id

    iamccs_autolinkarguments = raw_call(wf, 'IAMCCS_AutoLinkArguments', '9026',
        widget_0=False,
        widget_1=False,
        widget_10='Red',
        widget_11='Orange',
        widget_12='Black',
        widget_13='',
        widget_14='',
        widget_15='both',
        widget_17='',
        widget_19='',
        widget_2=False,
        widget_3=True,
        widget_4='None',
        widget_5='',
        widget_6='TopToDown',
        widget_7='AvoidAll',
        widget_8='',
        widget_9=True,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_autolinkarguments'] = iamccs_autolinkarguments.node.id

    emptyimage = EmptyImage(
        _id='10955',
        widget_0=1332,
        widget_1=720,
        widget_2=1,
        widget_3=0,
    )
    wf.metadata.setdefault('id_map', {})['emptyimage'] = emptyimage.node.id

    iamccs_ltx2_timeframecount = raw_call(wf, 'IAMCCS_LTX2_TimeFrameCount', '10956',
        widget_0=10,
        widget_1=241,
        widget_2='fixed',
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_timeframecount'] = iamccs_ltx2_timeframecount.node.id

    iamccs_modelwithlora_ltx2_staged = raw_call(wf, 'IAMCCS_ModelWithLoRA_LTX2_Staged', '5219',
        lora_stage1=iamccs_ltx2_lorastackstaged.out(0),
        lora_stage2=iamccs_ltx2_lorastackstaged.out(1),
        model=unetloadergguf,
        model_stage2=unetloadergguf,
    )
    wf.metadata.setdefault('id_map', {})['iamccs_modelwithlora_ltx2_staged'] = iamccs_modelwithlora_ltx2_staged.node.id

    iamccs_ltx2_lorastackmodelio = raw_call(wf, 'IAMCCS_LTX2_LoRAStackModelIO', '5259',
        widget_0=MODEL_NAME_6,
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4='no',
        widget_5=0,
        model=checkpointloadersimple.out('MODEL'),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_lorastackmodelio'] = iamccs_ltx2_lorastackmodelio.node.id

    any_switch__rgthree__2 = raw_call(wf, 'Any Switch (rgthree)', '5261',
        any_01=lowvramaudiovaeloader,
        any_02=ltxvaudiovaeloader,
    )
    wf.metadata.setdefault('id_map', {})['any_switch__rgthree__2'] = any_switch__rgthree__2.node.id

    any_switch__rgthree__3 = raw_call(wf, 'Any Switch (rgthree)', '5262',
        any_01=ltxvgemmaclipmodelloader,
        any_02=dualcliploader,
    )
    wf.metadata.setdefault('id_map', {})['any_switch__rgthree__3'] = any_switch__rgthree__3.node.id

    any_switch__rgthree__4 = raw_call(wf, 'Any Switch (rgthree)', '5263',
        any_01=checkpointloadersimple.out('VAE'),
        any_02=vaeloaderkj,
    )
    wf.metadata.setdefault('id_map', {})['any_switch__rgthree__4'] = any_switch__rgthree__4.node.id

    iamccs_autolinkconverter = raw_call(wf, 'IAMCCS_AutoLinkConverter', '9025',
        arg=iamccs_autolinkarguments.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_autolinkconverter'] = iamccs_autolinkconverter.node.id

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='5174',
        text=primitivestringmultiline,
        clip=any_switch__rgthree__3,
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

    cliptextencode_2 = CLIPTextEncode(
        _id='5233',
        text=primitivestringmultiline_2,
        clip=any_switch__rgthree__3,
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

    cliptextencode_3 = CLIPTextEncode(
        _id='9002',
        text=primitivestringmultiline_3,
        clip=any_switch__rgthree__3,
    )
    wf.metadata.setdefault('id_map', {})['cliptextencode_3'] = cliptextencode_3.node.id

    iamccs_gguf_accelerator = raw_call(wf, 'IAMCCS_GGUF_accelerator', '9684',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5=WIDGET_5,
        widget_6=1024,
        model=iamccs_modelwithlora_ltx2_staged.out(1),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_gguf_accelerator'] = iamccs_gguf_accelerator.node.id

    iamccs_gguf_accelerator_2 = raw_call(wf, 'IAMCCS_GGUF_accelerator', '9685',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5=WIDGET_5,
        widget_6=1024,
        model=iamccs_modelwithlora_ltx2_staged.out(1),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_gguf_accelerator_2'] = iamccs_gguf_accelerator_2.node.id

    ltxvconditioning = LTXVConditioning(
        _id='5173',
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode,
        positive=cliptextencode,
        _outputs=('POSITIVE', 'NEGATIVE'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

    ltxvconditioning_2 = LTXVConditioning(
        _id='5234',
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode_2,
        positive=cliptextencode_2,
        _outputs=('POSITIVE', 'NEGATIVE'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvconditioning_2'] = ltxvconditioning_2.node.id

    any_switch__rgthree_ = raw_call(wf, 'Any Switch (rgthree)', '5258',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator.out(0),
    )
    wf.metadata.setdefault('id_map', {})['any_switch__rgthree_'] = any_switch__rgthree_.node.id

    any_switch__rgthree__5 = raw_call(wf, 'Any Switch (rgthree)', '5264',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['any_switch__rgthree__5'] = any_switch__rgthree__5.node.id

    ltxvconditioning_3 = LTXVConditioning(
        _id='9003',
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=cliptextencode_3,
        positive=cliptextencode_3,
        _outputs=('POSITIVE', 'NEGATIVE'),
    )
    wf.metadata.setdefault('id_map', {})['ltxvconditioning_3'] = ltxvconditioning_3.node.id

    n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78 = raw_call(wf, '3eaa20c4-5842-4fe4-87df-c0a7e83a6a78', '5189',
        widget_0=121,
        widget_1=25,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2,
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_1=emptyimage,
        images=loadimage.out('IMAGE'),
        length=iamccs_ltx2_timeframecount.out(0),
        model=any_switch__rgthree__5,
        model_1=any_switch__rgthree_,
        negative=ltxvconditioning.out('NEGATIVE'),
        positive=ltxvconditioning.out('POSITIVE'),
        upscale_model_1=latentupscalemodelloader,
        vae=any_switch__rgthree__4,
    )
    wf.metadata.setdefault('id_map', {})['n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78'] = n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.node.id

    createvideo = CreateVideo(
        _id='5190',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(1),
        images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    wf.metadata.setdefault('id_map', {})['createvideo'] = createvideo.node.id

    iamccs_ltx2_getimagefrombatch = raw_call(wf, 'IAMCCS_LTX2_GetImageFromBatch', '9014',
        widget_0='from_end',
        widget_1=10,
        widget_2='none',
        widget_3='none',
        widget_4='none',
        widget_5='native_workflow_safe',
        widget_6=10,
        widget_7=0,
        widget_8=10,
        images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_getimagefrombatch'] = iamccs_ltx2_getimagefrombatch.node.id

    # Outputs
    savevideo = SaveVideo(
        _id='4958',
        filename_prefix='output',
        format=FORMAT,
        codec=CODEC,
        video=createvideo,
    )
    wf.metadata.setdefault('id_map', {})['savevideo'] = savevideo.node.id

    n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0 = raw_call(wf, '8b36a85a-087e-4ee5-85ca-cccc69c5c5d0', '5235',
        widget_0=121,
        widget_1=24,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2,
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_1=emptyimage,
        images=iamccs_ltx2_getimagefrombatch.out(0),
        length=iamccs_ltx2_timeframecount.out(0),
        model=any_switch__rgthree__5,
        model_1=any_switch__rgthree_,
        negative=ltxvconditioning_2.out('NEGATIVE'),
        positive=ltxvconditioning_2.out('POSITIVE'),
        upscale_model_1=latentupscalemodelloader,
        vae=any_switch__rgthree__4,
    )
    wf.metadata.setdefault('id_map', {})['n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0'] = n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.node.id

    createvideo_2 = CreateVideo(
        _id='5236',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(1),
        images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(0),
    )
    wf.metadata.setdefault('id_map', {})['createvideo_2'] = createvideo_2.node.id

    audioconcat = AudioConcat(
        _id='5252',
        widget_0=WIDGET_0,
        audio1=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(1),
        audio2=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(1),
    )
    wf.metadata.setdefault('id_map', {})['audioconcat'] = audioconcat.node.id

    iamccs_ltx2_extensionmodule = raw_call(wf, 'IAMCCS_LTX2_ExtensionModule', '9015',
        widget_0=10,
        widget_1=WIDGET_1,
        widget_10=WIDGET_10,
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14=WIDGET_14,
        widget_15=1,
        widget_2=WIDGET_2,
        widget_3=True,
        widget_4=WIDGET_4,
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(0),
        source_images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_extensionmodule'] = iamccs_ltx2_extensionmodule.node.id

    savevideo_2 = SaveVideo(
        _id='5237',
        filename_prefix='output',
        format=FORMAT,
        codec=CODEC,
        video=createvideo_2,
    )
    wf.metadata.setdefault('id_map', {})['savevideo_2'] = savevideo_2.node.id

    n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2 = raw_call(wf, '8b36a85a-087e-4ee5-85ca-cccc69c5c5d0', '9004',
        widget_0=121,
        widget_1=24,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2,
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_1=emptyimage,
        images=iamccs_ltx2_extensionmodule.out(1),
        length=iamccs_ltx2_timeframecount.out(0),
        model=any_switch__rgthree__5,
        model_1=any_switch__rgthree_,
        negative=ltxvconditioning_3.out('NEGATIVE'),
        positive=ltxvconditioning_3.out('POSITIVE'),
        upscale_model_1=latentupscalemodelloader,
        vae=any_switch__rgthree__4,
    )
    wf.metadata.setdefault('id_map', {})['n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2'] = n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.node.id

    createvideo_4 = CreateVideo(
        _id='9005',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(1),
        images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(0),
    )
    wf.metadata.setdefault('id_map', {})['createvideo_4'] = createvideo_4.node.id

    audioconcat_2 = AudioConcat(
        _id='9008',
        widget_0=WIDGET_0,
        audio1=audioconcat,
        audio2=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(1),
    )
    wf.metadata.setdefault('id_map', {})['audioconcat_2'] = audioconcat_2.node.id

    iamccs_ltx2_extensionmodule_2 = raw_call(wf, 'IAMCCS_LTX2_ExtensionModule', '9016',
        widget_0=10,
        widget_1=WIDGET_1,
        widget_10=WIDGET_10,
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14=WIDGET_14,
        widget_15=1,
        widget_2=WIDGET_2,
        widget_3=True,
        widget_4=WIDGET_4,
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(0),
        source_images=iamccs_ltx2_extensionmodule.out(2),
    )
    wf.metadata.setdefault('id_map', {})['iamccs_ltx2_extensionmodule_2'] = iamccs_ltx2_extensionmodule_2.node.id

    createvideo_3 = CreateVideo(
        _id='5254',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audioconcat_2,
        images=iamccs_ltx2_extensionmodule_2.out(2),
    )
    wf.metadata.setdefault('id_map', {})['createvideo_3'] = createvideo_3.node.id

    savevideo_4 = SaveVideo(
        _id='9006',
        filename_prefix='output',
        format=FORMAT,
        codec=CODEC,
        video=createvideo_4,
    )
    wf.metadata.setdefault('id_map', {})['savevideo_4'] = savevideo_4.node.id

    savevideo_3 = SaveVideo(
        _id='5255',
        filename_prefix='output',
        format=FORMAT,
        codec=CODEC,
        video=createvideo_3,
    )
    wf.metadata.setdefault('id_map', {})['savevideo_3'] = savevideo_3.node.id

    return wf.finalize(PUBLIC_INPUTS, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

