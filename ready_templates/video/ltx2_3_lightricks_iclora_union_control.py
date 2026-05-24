# vibecomfy: broken-regen
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVSeparateAVLatent, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode, LowVRAMAudioVAELoader, LowVRAMCheckpointLoader

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


DEFAULT_FPS = 8
DEFAULT_FRAMES = 5
DEFAULT_PROMPT = 'Apocalyptic landscape with abandoned buildings, overgrown with foliage and trees. The sky is clear and the sun is setting, with the horizon turning bright red. The buildings are delapidated, falling apart and crumbling due to being abandoned for so long.\nThe air is full of silence and the only thing to be heard is a young girl breathing and saying: "Where is everyone?"'
DEFAULT_PROMPT_2 = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_SEED = 42
FILE = 'ltx_smoke_guide.mp4'
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 2.5
IMAGE = 'example.png'
MODEL_NAME = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_3 = 'depth_anything_v2_vits_fp32.safetensors'
MODEL_NAME_4 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
MODEL_NAME_5 = 'ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors'
MODEL_NAME_6 = 'yolox_l.onnx'
MODEL_NAME_7 = 'dw-ll_ucoco_384_bs5.torchscript.pt'
SCALE_METHOD = 'lanczos'
WIDGET_0 = ''


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('lowvramcheckpointloader'), field='ckpt_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'image': InputSpec(node=ref('loadimage'), field='image', default=IMAGE),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default=IMAGE),
}

READY_METADATA = ReadyMetadata.build(
    capability='union_control_video_guided_i2v',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['euler_ancestral_cfg_pp', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'], 'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'comfyui_controlnet_aux']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['CannyEdgePreprocessor', 'DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='official IC-LoRA union control workflow with depth/pose-style guide preprocessing',
    runtime_note='Requires additional VideoDepthAnything/DWPose model setup beyond the core LTX smoke stack.',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        loadimage = LoadImage(
            _id='2004',
            image=IMAGE,
            widget_0='example.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        lowvramcheckpointloader = LowVRAMCheckpointLoader(
            _id='3940',
            ckpt_name=MODEL_NAME,
            _outputs=('MODEL', 'CLIP', 'VAE'),
        )
        wf.metadata.setdefault('id_map', {})['lowvramcheckpointloader'] = lowvramcheckpointloader.node.id

        lowvramaudiovaeloader = LowVRAMAudioVAELoader(_id='4010', ckpt_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['lowvramaudiovaeloader'] = lowvramaudiovaeloader.node.id
        # Sampling
        ksamplerselect = KSamplerSelect(
            _id='4831',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id

        randomnoise = RandomNoise(
            _id='4832',
            noise_seed=DEFAULT_SEED,
            control_after_generate='fixed',
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        loadvideo = LoadVideo(
            _id='5001',
            file=FILE,
            video='ltx_smoke_guide.mp4',
            widget_0='ltx_smoke_guide.mp4',
        )
        wf.metadata.setdefault('id_map', {})['loadvideo'] = loadvideo.node.id

        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '5019', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        # Inputs
        primitivestring = raw_call(wf, 'PrimitiveString', '5022', value='')
        wf.metadata.setdefault('id_map', {})['primitivestring'] = primitivestring.node.id
        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            _id='5023',
            text_encoder=MODEL_NAME_2,
            ckpt_name=MODEL_NAME,
            device='default',
            widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
            widget_1='ltx-2.3-22b-dev-fp8.safetensors',
        )
        wf.metadata.setdefault('id_map', {})['ltxavtextencoderloader'] = ltxavtextencoderloader.node.id

        manualsigmas = ManualSigmas(
            _id='5025',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
            _id='5060',
            model=MODEL_NAME_3,
            precision='fp32',
        )
        wf.metadata.setdefault('id_map', {})['downloadandloaddepthanythingv2model'] = downloadandloaddepthanythingv2model.node.id

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

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='4922',
            lora_name=MODEL_NAME_4,
            strength_model=GUIDE_STRENGTH,
            model=lowvramcheckpointloader.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        getvideocomponents = GetVideoComponents(
            _id='5000',
            video=loadvideo,
            _outputs=('IMAGES', 'AUDIO', 'FPS'),
        )
        wf.metadata.setdefault('id_map', {})['getvideocomponents'] = getvideocomponents.node.id

        gemmaapitextencode = GemmaAPITextEncode(
            _id='5020',
            widget_0=WIDGET_0,
            widget_1='pc game, console game, video game, cartoon, childish, ugly',
            widget_2=False,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['gemmaapitextencode'] = gemmaapitextencode.node.id

        gemmaapitextencode_2 = GemmaAPITextEncode(
            _id='5021',
            widget_0=WIDGET_0,
            widget_1='',
            widget_2=MODEL_NAME,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['gemmaapitextencode_2'] = gemmaapitextencode_2.node.id

        resizeimagemasknode_3 = ResizeImageMaskNode(
            _id='5035',
            resize_type='scale longer dimension',
            scale_method=SCALE_METHOD,
            input=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_3'] = resizeimagemasknode_3.node.id

        ltxvconditioning = LTXVConditioning(
            _id='1241',
            widget_0=8,
            frame_rate=getvideocomponents.out('FPS'),
            negative=cliptextencode_2,
            positive=cliptextencode,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxicloraloadermodelonly = LTXICLoRALoaderModelOnly(
            _id='5011',
            lora_name=MODEL_NAME_5,
            widget_0='ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors',
            model=loraloadermodelonly,
            _outputs=('MODEL', 'LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['ltxicloraloadermodelonly'] = ltxicloraloadermodelonly.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='5026',
            resize_type='scale shorter dimension',
            scale_method=SCALE_METHOD,
            input=getvideocomponents.out('IMAGES'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        ltxfloattoint = LTXFloatToInt(
            _id='5066',
            rounding=0,
            a=getvideocomponents.out('FPS'),
        )
        wf.metadata.setdefault('id_map', {})['ltxfloattoint'] = ltxfloattoint.node.id

        dwpreprocessor = raw_call(wf, 'DWPreprocessor', '4986',
            detect_hand='enable',
            detect_body='enable',
            detect_face='enable',
            resolution=256,
            bbox_detector=MODEL_NAME_6,
            pose_estimator=MODEL_NAME_7,
            scale_stick_for_xinsr_cn='disable',
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['dwpreprocessor'] = dwpreprocessor.node.id

        cannyedgepreprocessor = raw_call(wf, 'CannyEdgePreprocessor', '4991',
            low_threshold=92,
            high_threshold=200,
            resolution=256,
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['cannyedgepreprocessor'] = cannyedgepreprocessor.node.id

        simplemath_ = raw_call(wf, 'SimpleMath+', '5034',
            _outputs=('INT', 'FLOAT'),
            widget_0='a*32',
            a=ltxicloraloadermodelonly.out('LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['simplemath_'] = simplemath_.node.id

        depthanything_v2 = DepthAnything_V2(
            _id='5061',
            da_model=downloadandloaddepthanythingv2model,
            images=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['depthanything_v2'] = depthanything_v2.node.id

        resizeimagemasknode_2 = ResizeImageMaskNode(
            _id='5028',
            resize_type='scale to multiple',
            scale_method=SCALE_METHOD,
            input=cannyedgepreprocessor,
            **{'resize_type.multiple': simplemath_.out('INT')},
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_2'] = resizeimagemasknode_2.node.id

        getimagesize = GetImageSize(
            _id='5029',
            image=resizeimagemasknode_2,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='3059',
            widget_0=256,
            widget_1=256,
            widget_2=5,
            width=getimagesize.out('WIDTH'),
            height=getimagesize.out('HEIGHT'),
            length=getimagesize.out('BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='3980',
            widget_0=5,
            widget_1=8,
            frames_number=getimagesize.out('BATCH_SIZE'),
            frame_rate=ltxfloattoint,
            audio_vae=lowvramaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
            _id='3159',
            widget_1=False,
            bypass=primitiveboolean,
            image=resizeimagemasknode_3,
            latent=emptyltxvlatentvideo,
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoconditiononly'] = ltxvimgtovideoconditiononly.node.id

        ltxaddvideoicloraguide = LTXAddVideoICLoRAGuide(
            _id='5012',
            crop=1,
            use_tiled_encode='disabled',
            tile_size=128,
            tile_overlap=32,
            image=resizeimagemasknode_2,
            latent=ltxvimgtovideoconditiononly,
            latent_downscale_factor=ltxicloraloadermodelonly.out('LATENT_DOWNSCALE_FACTOR'),
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
            vae=lowvramcheckpointloader.out('VAE'),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxaddvideoicloraguide'] = ltxaddvideoicloraguide.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='4528',
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxaddvideoicloraguide.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='4828',
            cfg=GUIDE_STRENGTH_2,
            model=ltxicloraloadermodelonly.out('MODEL'),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

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

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='4845',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='4848',
            audio_vae=lowvramaudiovaeloader,
            samples=ltxvseparateavlatent.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='5013',
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        ltxvtiledvaedecode = LTXVTiledVAEDecode(
            _id='5065',
            horizontal_tiles=2,
            vertical_tiles=2,
            overlap=6,
            latents=ltxvcropguides.out('LATENT'),
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvtiledvaedecode'] = ltxvtiledvaedecode.node.id

        createvideo = CreateVideo(
            _id='4849',
            widget_0=8,
            fps=getvideocomponents.out('FPS'),
            audio=ltxvaudiovaedecode,
            images=ltxvtiledvaedecode,
        )
        wf.metadata.setdefault('id_map', {})['createvideo'] = createvideo.node.id

        # Outputs
        savevideo = SaveVideo(_id='4852', filename_prefix='output', video=createvideo)
        wf.metadata.setdefault('id_map', {})['savevideo'] = savevideo.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

