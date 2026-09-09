# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo, SimpleMath_2
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly, LTXVDrawTracks, LTXVImgToVideoConditionOnly, LTXVSparseTrackEditor, LTXVTiledVAEDecode


CKPT_NAME = 'ltx-2.3-22b-dev.safetensors'
DEFAULT_FPS = 24.0
DEFAULT_FRAMES = 121
DEFAULT_PROMPT = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_PROMPT_2 = 'Man on a small bycicle being chased by a police car. The sirens are blaring and the crowd of bystanders is cheering loudly. As he is pedaling away on the bike, he looks back at the police car and shouts in a taunting tone: "you can\'t catch me!" and waving his fist in the air. He then pedals away on his bike.'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.5
LANCZOS = 'lanczos'
LORA_NAME = 'ltxv/ltx2/ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors'
LORA_NAME_2 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
TEXT_ENCODER_NAME = 'comfy_gemma_3_12B_it.safetensors'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='2004', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'frames': InputSpec(node='3059', field='length', default=DEFAULT_FRAMES, type='INT'),
    'seed': InputSpec(node='4832', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'fps': InputSpec(node='4849', field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node='2483', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='2612', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['ltx-2.3-22b-dev.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'ltxv/ltx2/ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Motion_Track_Distilled.json', 'source_id': 'video/ltx2_3_lightricks_iclora_motion_track', 'upstream_source_id': 'LTX-2.3_ICLoRA_Motion_Track_Distilled', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Motion_Track_Distilled.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_iclora_motion_track'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='2004', image='motion_track_input.jpg')

    # Loaders
    model, _, vae = CheckpointLoaderSimple(_id='3940', ckpt_name=CKPT_NAME)
    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='4010', ckpt_name=CKPT_NAME)

    # Sampling
    ksamplerselect = KSamplerSelect(_id='4831', sampler_name='euler_ancestral_cfg_pp')

    randomnoise = RandomNoise(
        _id='4832',
        noise_seed=DEFAULT_SEED,
        control_after_generate='fixed',
    )

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        _id='5023',
        text_encoder=TEXT_ENCODER_NAME,
        ckpt_name=CKPT_NAME,
        device='default',
    )

    manualsigmas = ManualSigmas(
        _id='5025',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    ltxfloattoint = LTXFloatToInt(_id='5059', rounding=0, a=24.0)

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='2483',
        text=DEFAULT_PROMPT_2,
        clip=ltxavtextencoderloader,
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='2612',
        text=DEFAULT_PROMPT,
        clip=ltxavtextencoderloader,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        _id='3980',
        frames_number=121,
        frame_rate=ltxfloattoint,
        audio_vae=ltxvaudiovaeloader,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='4922',
        lora_name=LORA_NAME_2,
        strength_model=GUIDE_STRENGTH_2,
        model=model,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='5049',
        resize_type='scale shorter dimension',
        scale_method=LANCZOS,
        input=image,
    )

    positive, negative = LTXVConditioning(
        _id='1241',
        frame_rate=24.0,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    model_2, latent_downscale_factor = LTXICLoRALoaderModelOnly(
        _id='5011',
        lora_name=LORA_NAME,
        model=loraloadermodelonly,
    )

    math_int, _ = SimpleMath_2(_id='5056', value='a*32', a=latent_downscale_factor)

    resizeimagemasknode_2 = ResizeImageMaskNode(
        _id='5053',
        resize_type='scale to multiple',
        scale_method=LANCZOS,
        input=resizeimagemasknode,
        **{'resize_type.multiple': math_int},
    )

    ltxvsparsetrackeditor = LTXVSparseTrackEditor(
        _id='5040',
        widget_0='[[{"x":385.0759251206301,"y":238.92165891412267},{"x":226.6706827038015,"y":321.895716789677},{"x":118.7556948262006,"y":334.34620347590675},{"x":8.857468951125458,"y":294.56719637193584}],[{"x":550.4183052326947,"y":246.43019177413228},{"x":530.2019095759371,"y":493.9392986305124}]]',
        widget_1='[[{"x":385,"y":239},{"x":383,"y":240},{"x":381,"y":241},{"x":378,"y":243},{"x":375,"y":244},{"x":373,"y":246},{"x":369,"y":248},{"x":366,"y":249},{"x":363,"y":251},{"x":359,"y":253},{"x":355,"y":255},{"x":352,"y":258},{"x":348,"y":260},{"x":344,"y":262},{"x":339,"y":265},{"x":335,"y":267},{"x":331,"y":270},{"x":326,"y":272},{"x":322,"y":275},{"x":317,"y":277},{"x":313,"y":280},{"x":308,"y":282},{"x":303,"y":285},{"x":299,"y":287},{"x":294,"y":290},{"x":289,"y":292},{"x":285,"y":295},{"x":280,"y":297},{"x":275,"y":300},{"x":271,"y":302},{"x":266,"y":304},{"x":262,"y":306},{"x":258,"y":308},{"x":253,"y":311},{"x":249,"y":312},{"x":245,"y":314},{"x":241,"y":316},{"x":237,"y":318},{"x":234,"y":319},{"x":230,"y":321},{"x":227,"y":322},{"x":223,"y":323},{"x":220,"y":324},{"x":217,"y":325},{"x":214,"y":326},{"x":211,"y":327},{"x":208,"y":328},{"x":205,"y":329},{"x":202,"y":330},{"x":199,"y":330},{"x":196,"y":331},{"x":193,"y":332},{"x":191,"y":332},{"x":188,"y":333},{"x":185,"y":334},{"x":183,"y":334},{"x":180,"y":334},{"x":177,"y":335},{"x":175,"y":335},{"x":172,"y":336},{"x":170,"y":336},{"x":167,"y":336},{"x":165,"y":336},{"x":162,"y":336},{"x":160,"y":337},{"x":157,"y":337},{"x":155,"y":337},{"x":152,"y":337},{"x":150,"y":337},{"x":147,"y":337},{"x":145,"y":337},{"x":142,"y":336},{"x":140,"y":336},{"x":137,"y":336},{"x":135,"y":336},{"x":132,"y":336},{"x":129,"y":336},{"x":127,"y":335},{"x":124,"y":335},{"x":121,"y":335},{"x":119,"y":334},{"x":116,"y":334},{"x":113,"y":333},{"x":110,"y":333},{"x":107,"y":332},{"x":104,"y":332},{"x":101,"y":331},{"x":98,"y":330},{"x":95,"y":329},{"x":92,"y":328},{"x":89,"y":327},{"x":86,"y":326},{"x":82,"y":325},{"x":79,"y":324},{"x":76,"y":323},{"x":73,"y":322},{"x":70,"y":320},{"x":66,"y":319},{"x":63,"y":318},{"x":60,"y":317},{"x":57,"y":315},{"x":54,"y":314},{"x":51,"y":313},{"x":48,"y":311},{"x":45,"y":310},{"x":42,"y":309},{"x":39,"y":308},{"x":37,"y":306},{"x":34,"y":305},{"x":31,"y":304},{"x":29,"y":303},{"x":26,"y":302},{"x":24,"y":301},{"x":22,"y":300},{"x":19,"y":299},{"x":17,"y":298},{"x":15,"y":297},{"x":14,"y":296},{"x":12,"y":296},{"x":10,"y":295},{"x":9,"y":295}],[{"x":550,"y":246},{"x":550,"y":248},{"x":550,"y":251},{"x":550,"y":253},{"x":550,"y":255},{"x":550,"y":257},{"x":549,"y":259},{"x":549,"y":261},{"x":549,"y":263},{"x":549,"y":265},{"x":549,"y":267},{"x":549,"y":269},{"x":548,"y":271},{"x":548,"y":273},{"x":548,"y":275},{"x":548,"y":277},{"x":548,"y":279},{"x":548,"y":281},{"x":547,"y":284},{"x":547,"y":286},{"x":547,"y":288},{"x":547,"y":290},{"x":547,"y":292},{"x":547,"y":294},{"x":546,"y":296},{"x":546,"y":298},{"x":546,"y":300},{"x":546,"y":302},{"x":546,"y":304},{"x":546,"y":306},{"x":545,"y":308},{"x":545,"y":310},{"x":545,"y":312},{"x":545,"y":314},{"x":545,"y":317},{"x":545,"y":319},{"x":544,"y":321},{"x":544,"y":323},{"x":544,"y":325},{"x":544,"y":327},{"x":544,"y":329},{"x":544,"y":331},{"x":543,"y":333},{"x":543,"y":335},{"x":543,"y":337},{"x":543,"y":339},{"x":543,"y":341},{"x":543,"y":343},{"x":542,"y":345},{"x":542,"y":347},{"x":542,"y":350},{"x":542,"y":352},{"x":542,"y":354},{"x":541,"y":356},{"x":541,"y":358},{"x":541,"y":360},{"x":541,"y":362},{"x":541,"y":364},{"x":541,"y":366},{"x":540,"y":368},{"x":540,"y":370},{"x":540,"y":372},{"x":540,"y":374},{"x":540,"y":376},{"x":540,"y":378},{"x":539,"y":380},{"x":539,"y":383},{"x":539,"y":385},{"x":539,"y":387},{"x":539,"y":389},{"x":539,"y":391},{"x":538,"y":393},{"x":538,"y":395},{"x":538,"y":397},{"x":538,"y":399},{"x":538,"y":401},{"x":538,"y":403},{"x":537,"y":405},{"x":537,"y":407},{"x":537,"y":409},{"x":537,"y":411},{"x":537,"y":413},{"x":537,"y":416},{"x":536,"y":418},{"x":536,"y":420},{"x":536,"y":422},{"x":536,"y":424},{"x":536,"y":426},{"x":536,"y":428},{"x":535,"y":430},{"x":535,"y":432},{"x":535,"y":434},{"x":535,"y":436},{"x":535,"y":438},{"x":535,"y":440},{"x":534,"y":442},{"x":534,"y":444},{"x":534,"y":447},{"x":534,"y":449},{"x":534,"y":451},{"x":534,"y":453},{"x":533,"y":455},{"x":533,"y":457},{"x":533,"y":459},{"x":533,"y":461},{"x":533,"y":463},{"x":533,"y":465},{"x":532,"y":467},{"x":532,"y":469},{"x":532,"y":471},{"x":532,"y":473},{"x":532,"y":475},{"x":532,"y":477},{"x":531,"y":480},{"x":531,"y":482},{"x":531,"y":484},{"x":531,"y":486},{"x":531,"y":488},{"x":531,"y":490},{"x":530,"y":492},{"x":530,"y":494}]]',
        widget_2=121,
        widget_3='',
        image=resizeimagemasknode_2,
    )

    width, height, _ = GetImageSize(_id='5050', image=resizeimagemasknode_2)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='3059',
        length=DEFAULT_FRAMES,
        width=width,
        height=height,
    )

    ltxvdrawtracks = LTXVDrawTracks(
        _id='5034',
        height=height,
        tracks=ltxvsparsetrackeditor,
        width=width,
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        _id='3159',
        image=resizeimagemasknode_2,
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    createvideo_2 = CreateVideo(_id='5051', fps=DEFAULT_FPS, images=ltxvdrawtracks)

    positive_2, negative_2, latent = LTXAddVideoICLoRAGuide(
        _id='5012',
        crop=1,
        use_tiled_encode='disabled',
        image=ltxvdrawtracks,
        latent=ltxvimgtovideoconditiononly,
        latent_downscale_factor=latent_downscale_factor,
        negative=negative,
        positive=positive,
        vae=vae,
    )

    # Outputs
    savevideo_2 = SaveVideo(_id='5052', filename_prefix='tracks', video=createvideo_2)

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='4528',
        audio_latent=ltxvemptylatentaudio,
        video_latent=latent,
    )

    cfgguider = CFGGuider(
        _id='4828',
        cfg=GUIDE_STRENGTH,
        model=model_2,
        negative=negative_2,
        positive=positive_2,
    )

    output, _ = SamplerCustomAdvanced(
        _id='4829',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(_id='4845', av_latent=output)

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='4848',
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent,
    )

    _, _, latent_2 = LTXVCropGuides(
        _id='5013',
        latent=video_latent,
        negative=negative_2,
        positive=positive_2,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        _id='5058',
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        latents=latent_2,
        vae=vae,
    )

    createvideo = CreateVideo(
        _id='4849',
        fps=DEFAULT_FPS,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode,
    )

    savevideo = SaveVideo(_id='4852', filename_prefix='output', video=createvideo)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

