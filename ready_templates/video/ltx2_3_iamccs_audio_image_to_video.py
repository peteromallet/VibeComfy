# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, DualCLIPLoader, EmptyLTXVLatentVideo, KSamplerSelect, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LoadAudio, LoadImage, PreviewAudio, PreviewImage, RandomNoise, SaveAudioMP3, SetLatentNoiseMask, SolidMask, TrimAudioDuration
from vibecomfy.nodes.custom_scripts import MathExpression_pysssss, ShowText_pysssss
from vibecomfy.nodes.gguf import UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import ImageResizeKJv2, VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVGemmaCLIPModelLoader
from vibecomfy.nodes.melbandroformer import MelBandRoFormerModelLoader, MelBandRoFormerSampler
from vibecomfy.nodes.rgthree import Seed_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX2_audio_vae_bf16.safetensors'
AUTO = 'auto'
BF16 = 'bf16'
CKPT_NAME = 'ltx-2-19b-distilled.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_e4m3fn.safetensors'
CLIP_NAME_2 = 'ltx-2-19b-embeddings_connector_dev_bf16.safetensors'
DEFAULT_PROMPT = 'blurry, out of focus, overexposed, underexposed, low contrast, washed out colors, excessive noise, grainy texture, poor lighting, flickering, motion blur, distorted proportions, unnatural skin tones, deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, wrong hand count, artifacts around text, unreadable text on shirt or hat, incorrect lettering on cap (“PNTR”), incorrect t-shirt slogan (“JUST DO IT”), missing microphone, misplaced microphone, inconsistent perspective, camera shake, incorrect depth of field, background too sharp, background clutter, distracting reflections, harsh shadows, inconsistent lighting direction, color banding, cartoonish rendering, 3D CGI look, unrealistic materials, uncanny valley effect, incorrect ethnicity, wrong gender, exaggerated expressions, smiling, laughing, exaggerated sadness, wrong gaze direction, eyes looking at camera, mismatched lip sync, silent or muted audio, distorted voice, robotic voice, echo, background noise, off-sync audio, missing sniff sounds, incorrect dialogue, added dialogue, repetitive speech, jittery movement, awkward pauses, incorrect timing, unnatural transitions, inconsistent framing, tilted camera, missing door or shelves, missing shallow depth of field, flat lighting, inconsistent tone, cinematic oversaturation, stylized filters, or AI artifacts.'
DEFAULT_SEED = 923615063061116
GUIDE_STRENGTH = 1
MAIN_DEVICE = 'main_device'
MEL_BAND_ROFORMER_NAME = 'MelBandRoformer_fp32.safetensors'
NO = 'no'
UNET_NAME_GGUF = 'LTX-2-dev-Q4_K_S.gguf'
VIDEO_VAE_NAME = 'LTX2_video_vae_2_bf16.safetensors'
V_1_7B = '1.7B'
WIDGET__NAME = 'ltx-2-19b-distilled-lora-384.safetensors'
WIDGET__NAME_2 = 'ltx-2-19b-lora-camera-control-static.safetensors'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='240', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='241', field='width', default=720, type='INT'),
    'height': InputSpec(node='241', field='height', default=1280, type='INT'),
    'seed': InputSpec(node='290', field='seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='165', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX-2-dev-Q4_K_S.gguf', 'LTX2_audio_vae_bf16.safetensors', 'LTX2_video_vae_2_bf16.safetensors', 'ltx-2-19b-distilled.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Seed (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_AU_IMG2V.json', 'source_id': 'video/ltx2_3_iamccs_audio_image_to_video', 'upstream_source_id': 'IAMCCS_LTX2_AU_IMG2V', 'source_type': 'api', 'source_workflow_path': 'ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_AU_IMG2V.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_iamccs_audio_image_to_video'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Sampling
    ksamplerselect = KSamplerSelect(_id='154', sampler_name='lcm')

    # Inputs
    image, _ = LoadImage(_id='240', image='ComfyUI_00126_.png')
    loadaudio = LoadAudio(_id='243', audio='man voice 1.mp3')

    seed__rgthree_ = Seed_rgthree(
        _id='290',
        seed=DEFAULT_SEED,
        widget_1='',
        widget_2='',
        widget_3='',
    )

    text_multiline = raw_call('Text Multiline', '293', widget_0='video of a goblin talking to the camera')
    unetloadergguf = UnetLoaderGGUF(_id='301', unet_name=UNET_NAME_GGUF)

    # Loaders
    dualcliploader = DualCLIPLoader(
        _id='303',
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_NAME_2,
        type='ltxv',
        device='default',
    )

    vaeloaderkj = VAELoaderKJ(
        _id='305',
        vae_name=VIDEO_VAE_NAME,
        device=MAIN_DEVICE,
        weight_dtype=BF16,
    )

    vaeloaderkj_2 = VAELoaderKJ(
        _id='311',
        vae_name=AUDIO_VAE_NAME,
        device=MAIN_DEVICE,
        weight_dtype=BF16,
    )

    iamccs_ltx2_lorastack = raw_call('IAMCCS_LTX2_LoRAStack', '321',
        widget_0=WIDGET__NAME,
        widget_1=0.7,
        widget_2=WIDGET__NAME_2,
        widget_3=1,
        widget_4=NO,
        widget_5=0,
    )

    loadaudio_2 = LoadAudio(_id='347', audio='man voice 2 LONG.mp3')
    loadaudio_3 = LoadAudio(_id='376', audio='EdgarLetfall.mp3')

    melbandroformermodelloader = MelBandRoFormerModelLoader(
        _id='377',
        model=MEL_BAND_ROFORMER_NAME,
    )

    cr_float_to_integer = raw_call('CR Float To Integer', '384', _float=25.0)
    load_whisper__mtb_ = raw_call('Load Whisper (mtb)', '405', widget_0='tiny', widget_1=True)
    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='411', ckpt_name=CKPT_NAME)

    ltxvgemmaclipmodelloader = LTXVGemmaCLIPModelLoader(
        _id='412',
        gemma_path=CLIP_NAME,
        ltxv_path=CKPT_NAME,
    )

    model, _, vae = CheckpointLoaderSimple(_id='413', ckpt_name=CKPT_NAME)

    randomnoise = RandomNoise(
        _id='178',
        control_after_generate='fixed',
        noise_seed=seed__rgthree_,
    )

    image_2, width, height, _ = ImageResizeKJv2(
        _id='241',
        width=720,
        height=1280,
        upscale_method='lanczos',
        keep_proportion='crop',
        crop_position='top',
        divisible_by=32,
        device='cpu',
        image=image,
    )

    iamccs_modelwithlora_ltx2 = raw_call('IAMCCS_ModelWithLoRA_LTX2', '322',
        lora=iamccs_ltx2_lorastack.out(0),
        model=unetloadergguf,
    )

    fl_chatterboxturbotts = raw_call('FL_ChatterboxTurboTTS', '348',
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

    trimaudioduration = TrimAudioDuration(_id='366', duration=20, audio=loadaudio_3)

    audio_to_text__mtb_ = raw_call('Audio To Text (mtb)', '406',
        widget_0='auto',
        widget_1=False,
        audio=loadaudio_3,
        pipeline=load_whisper__mtb_.out(0),
    )

    iamccs_ltx2_lorastackmodelio = raw_call('IAMCCS_LTX2_LoRAStackModelIO', '416',
        widget_0=WIDGET__NAME,
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4=NO,
        widget_5=0,
        model=model,
    )

    iamccs_multiswitch_3 = raw_call('IAMCCS_MultiSwitch', '452',
        widget_0='VAE AUDIO LOW',
        widget_1=True,
        widget_2=None,
        input_01=ltxvaudiovaeloader,
        input_02=vaeloaderkj_2,
    )

    iamccs_multiswitch_4 = raw_call('IAMCCS_MultiSwitch', '453',
        widget_0='VAE h',
        widget_1=True,
        widget_2=None,
        input_01=vae,
        input_02=vaeloaderkj,
    )

    iamccs_multiswitch_5 = raw_call('IAMCCS_MultiSwitch', '454',
        widget_0='CLIP L',
        widget_1=True,
        widget_2=None,
        input_01=ltxvgemmaclipmodelloader,
        input_02=dualcliploader,
    )

    ltxvpreprocess = LTXVPreprocess(_id='269', img_compression=33, image=image_2)

    # Outputs
    previewimage = PreviewImage(_id='275', images=image_2)
    saveaudiomp3 = SaveAudioMP3(_id='350', audio=fl_chatterboxturbotts.out(0))

    solidmask = SolidMask(
        _id='388',
        value=0,
        width=width,
        height=height,
    )

    easy_cleangpuused = raw_call('easy cleanGpuUsed', '407', anything=audio_to_text__mtb_.out(0))

    iamccs_multiswitch_2 = raw_call('IAMCCS_MultiSwitch', '451',
        widget_0='input_03',
        widget_1=True,
        widget_2=None,
        input_01=iamccs_ltx2_lorastackmodelio.out(0),
        input_02=iamccs_modelwithlora_ltx2.out(0),
    )

    showtext_pysssss = ShowText_pysssss(
        _id='373',
        widget_0=' How are you? I am from metallurgia, Elfica, a fantasy tale from our dear. Welcome to our show. And sit down and listen carefully.',
        text=easy_cleangpuused.out(0),
    )

    iamccs_gguf_accelerator = raw_call('IAMCCS_GGUF_accelerator', '475',
        widget_0='auto_oom_safe',
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs_multiswitch_2.out(0),
    )

    fb_qwen3ttsvoicecloneprompt = raw_call('FB_Qwen3TTSVoiceClonePrompt', '379',
        widget_0='',
        widget_1=V_1_7B,
        widget_2=AUTO,
        widget_3='fp32',
        widget_4='sage_attn',
        widget_5=True,
        widget_6=True,
        ref_audio=trimaudioduration,
        ref_text=showtext_pysssss.out(0),
    )

    iamccs_hwsupporter = raw_call('IAMCCS_HwSupporter', '893',
        widget_0='auto',
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

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='165',
        text=DEFAULT_PROMPT,
        clip=iamccs_hwsupporter.out(1),
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='169',
        text=text_multiline.out(0),
        clip=iamccs_hwsupporter.out(1),
    )

    basicscheduler = BasicScheduler(
        _id='238',
        scheduler='simple',
        steps=8,
        model=iamccs_hwsupporter.out(0),
    )

    iamccs_hwsupporterany = raw_call('IAMCCS_HwSupporterAny', '375',
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

    positive, negative = LTXVConditioning(
        _id='164',
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    fb_qwen3ttsvoiceclone = raw_call('FB_Qwen3TTSVoiceClone', '374',
        widget_0='this is only a test! check it out!',
        widget_1=V_1_7B,
        widget_10=20,
        widget_11=1,
        widget_12=1.05,
        widget_13=True,
        widget_14='auto',
        widget_15=True,
        widget_2=AUTO,
        widget_3='bf16',
        widget_4='Auto',
        widget_5='',
        widget_6=663647919912928,
        widget_7='fixed',
        widget_8=2048,
        widget_9=0.8,
        ref_audio=trimaudioduration,
        ref_text=showtext_pysssss.out(0),
        voice_clone_prompt=iamccs_hwsupporterany.out(0),
    )

    cfgguider = CFGGuider(
        _id='153',
        cfg=GUIDE_STRENGTH,
        model=iamccs_hwsupporter.out(0),
        negative=negative,
        positive=positive,
    )

    iamccs_multiswitch = raw_call('IAMCCS_MultiSwitch', '441',
        widget_0='input_6',
        widget_1=True,
        widget_2=None,
        input_01=loadaudio,
        input_03=fl_chatterboxturbotts.out(0),
        input_05=fb_qwen3ttsvoiceclone.out(0),
    )

    audio_duration__mtb_ = raw_call('Audio Duration (mtb)', '363', audio=iamccs_multiswitch.out(0))

    melbandroformersampler = MelBandRoFormerSampler(
        _id='365',
        audio=iamccs_multiswitch.out(0),
        model=melbandroformermodelloader.out(0),
    )

    mathexpression_pysssss = MathExpression_pysssss(
        _id='364',
        widget_0='((a*0.001)*b)',
        a=audio_duration__mtb_.out(0),
        b=cr_float_to_integer.out(0),
    )

    previewaudio = PreviewAudio(_id='380', audio=melbandroformersampler.out(0))

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        _id='387',
        audio=melbandroformersampler.out(0),
        audio_vae=iamccs_multiswitch_3.out(0),
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='162',
        width=width,
        height=height,
        length=mathexpression_pysssss.out(0),
    )

    setlatentnoisemask = SetLatentNoiseMask(
        _id='389',
        mask=solidmask,
        samples=ltxvaudiovaeencode,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        _id='239',
        strength=0.8,
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=iamccs_hwsupporter.out(2),
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        _id='166',
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace,
    )

    iamccs_sampleradvancedversion1 = raw_call('IAMCCS_SamplerAdvancedVersion1', '474',
        widget_0=True,
        widget_1=True,
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=basicscheduler,
    )

    video_latent, _ = LTXVSeparateAVLatent(
        _id='245',
        av_latent=iamccs_sampleradvancedversion1.out(0),
    )

    iamccs_vaedecodetiledsafe = raw_call('IAMCCS_VAEDecodeTiledSafe', '234',
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
        samples=video_latent,
        vae=iamccs_hwsupporter.out(2),
    )

    vhs_videocombine = VHS_VideoCombine(
        _id='190',
        frame_rate=25,
        filename_prefix='IAMCCS/LTX2_AU+IMG2V',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX2_AU+IMG2V_00008-audio.mp4', 'subfolder': 'IAMCCS', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'LTX2_AU+IMG2V_00008.png', 'fullpath': 'E:\\ComfyUI-Easy-Install\\ComfyUI-Easy-Install\\ComfyUI\\output\\IAMCCS\\LTX2_AU+IMG2V_00008-audio.mp4'}},
        audio=iamccs_multiswitch.out(0),
        images=iamccs_vaedecodetiledsafe.out(0),
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='IAMCCS/LTX2_AU+IMG2V')

