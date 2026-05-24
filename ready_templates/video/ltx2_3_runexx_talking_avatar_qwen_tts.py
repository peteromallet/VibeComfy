# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PreviewAudio, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceClone
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CKPT_NAME = 'LTX23_audio_vae_bf16.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
CLIP_NAME_2 = 'ltx-2.3_text_projection_bf16.safetensors'
CLIP_NAME_3 = 'gemma-3-12b-it-Q2_K.gguf'
CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
LORA_NAME = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
UNET_NAME_2 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_NAME = 'LTX23_video_vae_bf16.safetensors'
VAE_NAME_2 = 'taeltx2_3.safetensors'
WIDGET_0 = 'vae'
WIDGET_0_10 = 'ref_image'
WIDGET_0_11 = 'vae_audio'
WIDGET_0_12 = 'upscale_model'
WIDGET_0_13 = 'negative'
WIDGET_0_14 = 'positive'
WIDGET_0_15 = 't2v_mode'
WIDGET_0_16 = 'model'
WIDGET_0_17 = 'model_with_lora'
WIDGET_0_18 = 'vae_tiny'
WIDGET_0_19 = 'latent'
WIDGET_0_2 = 'clip'
WIDGET_0_20 = 'latent_custom_audio'
WIDGET_0_21 = 'enhance_prompt'
WIDGET_0_3 = 'width'
WIDGET_0_4 = 'height'
WIDGET_0_5 = 'frames'
WIDGET_0_6 = 'fps'
WIDGET_0_7 = 'audio_tts'
WIDGET_0_8 = 'height_downscaled'
WIDGET_0_9 = 'width_downscaled'
WIDGET__NAME = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'

READY_METADATA = ReadyMetadata.build(
    capability='tts_talking_avatar',
    requirements={'models': ['LTX23_audio_vae_bf16.safetensors', 'LTX23_video_vae_bf16.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'taeltx2_3.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-QwenTTS', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceClone'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='Qwen TTS talking avatar',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        getnode = raw_call('GetNode', '413', widget_0=WIDGET_0)

        # Inputs
        image, mask = LoadImage(image=public('image', default='17745317855d08.png'))
        vaeloader = VAELoader(vae_name=VAE_NAME)

        latentupscalemodelloader = LatentUpscaleModelLoader(
            model_name=public('model', default=MODEL_NAME),
        )

        dualcliploader = DualCLIPLoader(
            clip_name1=CLIP_NAME,
            clip_name2=CLIP_NAME_2,
            type_='ltxv',
            device='default',
        )

        ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)
        vaeloader_2 = VAELoader(vae_name=VAE_NAME_2)
        unetloader = UNETLoader(unet_name=UNET_NAME)
        unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_2)

        dualcliploadergguf = DualCLIPLoaderGGUF(
            clip_name1=CLIP_NAME_3,
            clip_name2=CLIP_NAME_2,
            type_='sdxl',
        )

        intconstant = INTConstant(value=10)
        primitivefloat = raw_call('PrimitiveFloat', '1586', value=8)
        intconstant_2 = INTConstant(value=960)
        intconstant_3 = INTConstant(value=544)
        getnode_2 = raw_call('GetNode', '1619', widget_0=WIDGET_0_2)
        getnode_3 = raw_call('GetNode', '1622', widget_0=WIDGET_0_2)

        primitivestringmultiline = PrimitiveStringMultiline(
            value="A video from a TV broadcast with a male and a female news achor. They both stay in frame all the time.\n\nThe dialog from the male and female is as follows:\n\nSpaker_1 is the woman, and Speaker_2 is the man.\n\n[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and put us in this odd situation.\n[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, doesn't mean our voices change. \n[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n[speaker_2][happy]: I still have no idea what she said! Might be for the best [laughing]\n\nThe dialog with perfect lip-sync to the audio\n\n\nThey both smile at the end.\n\n\n",
        )

        getnode_4 = raw_call('GetNode', '1628', widget_0=WIDGET_0_3)
        getnode_5 = raw_call('GetNode', '1629', widget_0=WIDGET_0_4)
        getnode_6 = raw_call('GetNode', '1635', widget_0=WIDGET_0_5)
        getnode_7 = raw_call('GetNode', '1636', widget_0=WIDGET_0_6)
        getnode_8 = raw_call('GetNode', '1784', widget_0=WIDGET_0_7)
        getnode_9 = raw_call('GetNode', '1807', widget_0=WIDGET_0_8)
        getnode_10 = raw_call('GetNode', '1808', widget_0=WIDGET_0_9)
        getnode_11 = raw_call('GetNode', '1809', widget_0=WIDGET_0_10)
        getnode_12 = raw_call('GetNode', '1814', widget_0=WIDGET_0)
        getnode_13 = raw_call('GetNode', '1815', widget_0=WIDGET_0_11)
        getnode_14 = raw_call('GetNode', '1816', widget_0=WIDGET_0)
        getnode_15 = raw_call('GetNode', '1817', widget_0=WIDGET_0_12)
        getnode_16 = raw_call('GetNode', '1820', widget_0=WIDGET_0_13)
        getnode_17 = raw_call('GetNode', '1821', widget_0=WIDGET_0_14)
        getnode_18 = raw_call('GetNode', '1822', widget_0=WIDGET_0_6)
        getnode_19 = raw_call('GetNode', '1823', widget_0=WIDGET_0_15)
        getnode_20 = raw_call('GetNode', '1824', widget_0=WIDGET_0_10)
        getnode_21 = raw_call('GetNode', '1828', widget_0=WIDGET_0_16)
        getnode_22 = raw_call('GetNode', '1829', widget_0=WIDGET_0_13)
        getnode_23 = raw_call('GetNode', '1830', widget_0=WIDGET_0_14)
        getnode_24 = raw_call('GetNode', '1831', widget_0=WIDGET_0_17)

        randomnoise = RandomNoise(
            noise_seed=public('seed', default=DEFAULT_SEED),
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        getnode_25 = raw_call('GetNode', '1833', widget_0=WIDGET_0_18)
        getnode_26 = raw_call('GetNode', '1834', widget_0=WIDGET_0_17)
        getnode_27 = raw_call('GetNode', '1835', widget_0=WIDGET_0_16)
        getnode_28 = raw_call('GetNode', '1841', widget_0=WIDGET_0_16)

        randomnoise_2 = RandomNoise(
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )

        getnode_29 = raw_call('GetNode', '1843', widget_0=WIDGET_0_13)
        manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')
        ksamplerselect = KSamplerSelect(sampler_name='euler_cfg_pp')
        ksamplerselect_2 = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
        getnode_30 = raw_call('GetNode', '1855', widget_0=WIDGET_0_19)

        manualsigmas_2 = ManualSigmas(
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        primitiveboolean = raw_call('PrimitiveBoolean', '1862', value=public('use_lora', default=False))
        reroute = raw_call('Reroute', '1865')
        getnode_31 = raw_call('GetNode', '1878', widget_0=WIDGET_0_16)
        getnode_32 = raw_call('GetNode', '1887', widget_0=WIDGET_0_4)
        getnode_33 = raw_call('GetNode', '1888', widget_0=WIDGET_0_3)
        getnode_34 = raw_call('GetNode', '1889', widget_0=WIDGET_0_11)
        getnode_35 = raw_call('GetNode', '1894', widget_0=WIDGET_0_20)
        getnode_36 = raw_call('GetNode', '1898', widget_0=WIDGET_0_6)
        primitiveboolean_2 = raw_call('PrimitiveBoolean', '1929', value=True)
        getnode_37 = raw_call('GetNode', '1931', widget_0=WIDGET_0_21)
        getnode_38 = raw_call('GetNode', '1935', widget_0=WIDGET_0_15)
        melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '1937', widget_0=WIDGET__NAME)
        primitivestringmultiline_2 = PrimitiveStringMultiline(value='')
        loadaudio = LoadAudio(audio='d1b26d5a32db420183fa17af9c699278.mp3')

        primitivestringmultiline_3 = PrimitiveStringMultiline(
            value='So what if you just want to prompt. Text to video works fine as well. Go generate some while I enjoy my coffee. ',
        )

        setnode_4 = raw_call('SetNode', '1555', widget_0=WIDGET_0_12, LATENT_UPSCALE_MODEL=latentupscalemodelloader)
        setnode_5 = raw_call('SetNode', '1556', widget_0=WIDGET_0_11, VAE=ltxvaudiovaeloader)
        setnode_6 = raw_call('SetNode', '1557', widget_0=WIDGET_0, VAE=vaeloader)
        setnode_7 = raw_call('SetNode', '1558', widget_0=WIDGET_0_2, CLIP=dualcliploader)
        setnode_8 = raw_call('SetNode', '1568', widget_0=WIDGET_0_18, VAE=vaeloader_2)
        setnode_9 = raw_call('SetNode', '1575', widget_0=WIDGET_0_4, INT=intconstant_2)
        setnode_10 = raw_call('SetNode', '1576', widget_0=WIDGET_0_3, INT=intconstant_3)
        setnode_11 = raw_call('SetNode', '1577', widget_0=WIDGET_0_6, FLOAT=primitivefloat)
        setnode_19 = raw_call('SetNode', '1861', widget_0=WIDGET_0_15, BOOLEAN=primitiveboolean)
        subgraph_63e8c999 = raw_call('63e8c999-0a69-4f62-af3f-8b77f0095971', '1920', audio=reroute.out(0))
        setnode_22 = raw_call('SetNode', '1930', widget_0=WIDGET_0_21, BOOLEAN=primitiveboolean_2)

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=getnode_10.out(0),
            height=getnode_9.out(0),
            length=getnode_6.out(0),
        )

        image_image, width, height, mask_image = ImageResizeKJv2(
            upscale_method='lanczos',
            keep_proportion='crop',
            device='cpu',
            width=getnode_4.out(0),
            height=getnode_5.out(0),
            image=image,
        )

        ltxvpreprocess = LTXVPreprocess(img_compression=18, image=getnode_11.out(0))

        loraloadermodelonly = LoraLoaderModelOnly(
            lora_name=LORA_NAME,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text=public('prompt', default=DEFAULT_PROMPT),
            clip=getnode_3.out(0),
        )

        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=getnode_27.out(0),
            negative=getnode_16.out(0),
            positive=getnode_17.out(0),
        )

        ltx2_nag = LTX2_NAG(
            model=getnode_26.out(0),
            nag_cond_audio=getnode_29.out(0),
            nag_cond_video=getnode_29.out(0),
        )

        cfgguider_2 = CFGGuider(
            cfg=GUIDE_STRENGTH_2,
            model=getnode_28.out(0),
            negative=getnode_22.out(0),
            positive=getnode_23.out(0),
        )

        modelsamplingsd3 = ModelSamplingSD3(shift=13, model=getnode_31.out(0))

        solidmask = SolidMask(
            value=0,
            widget_1=512,
            widget_2=512,
            height=getnode_32.out(0),
            width=getnode_33.out(0),
        )

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            audio=reroute.out(0),
            audio_vae=getnode_34.out(0),
        )

        float, int, boolean = SimpleCalculatorKJ(
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            **{'variables.a': intconstant, 'variables.b': getnode_36.out(0)},
        )

        modelsamplingsd3_2 = ModelSamplingSD3(shift=13, model=getnode_27.out(0))
        trimaudioduration = TrimAudioDuration(widget_0=0, widget_1=15, audio=loadaudio)
        setnode_3 = raw_call('SetNode', '650', widget_0=WIDGET_0_10, IMAGE=image_image)
        setnode_12 = raw_call('SetNode', '1578', widget_0=WIDGET_0_5, _extras={'*': subgraph_63e8c999.out(0)})
        setnode_17 = raw_call('SetNode', '1840', widget_0=WIDGET_0_16, MODEL=ltx2_nag)
        setnode_21 = raw_call('SetNode', '1918', widget_0='frames_seconds', INT=int)

        melbandroformersampler = raw_call('MelBandRoFormerSampler', '1936',
            audio=trimaudioduration,
            model=melbandroformermodelloader.out(0),
        )

        pathchsageattentionkj = PathchSageAttentionKJ(
            sage_attention='disabled',
            model=loraloadermodelonly,
        )

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type='scale by multiplier',
            input=image_image,
        )

        output, denoised_output = SamplerCustomAdvanced(
            guider=cfgguider_2,
            latent_image=getnode_30.out(0),
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
        )

        basicscheduler = BasicScheduler(
            scheduler=1,
            steps=public('steps', default=1),
            widget_1=8,
            model=modelsamplingsd3,
        )

        setlatentnoisemask = SetLatentNoiseMask(
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )

        basicscheduler_2 = BasicScheduler(
            scheduler=1,
            steps=1,
            widget_1=4,
            model=modelsamplingsd3_2,
        )

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            widget_0=0.7,
            widget_1=False,
            bypass=getnode_38.out(0),
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=getnode.out(0),
        )

        setnode_20 = raw_call('SetNode', '1891', widget_0=WIDGET_0_20, LATENT=setlatentnoisemask)

        subgraph_a8d7fd9f = raw_call('a8d7fd9f-52aa-447a-9766-53cb91c0ef18', '1926',
            _1=primitivestringmultiline,
            clip=getnode_2.out(0),
            image=resizeimagemasknode,
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=getnode_35.out(0),
            video_latent=ltxvimgtovideoinplace,
        )

        ltxvchunkfeedforward = LTXVChunkFeedForward(model=pathchsageattentionkj)
        width_get, height_get, batch_size = GetImageSize(image=resizeimagemasknode)
        video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

        ailab_qwen3ttsvoiceclone = AILab_Qwen3TTSVoiceClone(
            widget_0='Hello, this is a cloned voice.',
            widget_3='',
            widget_4=True,
            widget_5=986337553816914,
            widget_6=116899311982882,
            widget_7='randomize',
            reference_audio=melbandroformersampler.out(0),
            reference_text=primitivestringmultiline_2,
            target_text=primitivestringmultiline_3,
        )

        setnode_14 = raw_call('SetNode', '1633', widget_0=WIDGET_0_9, INT=width_get)
        setnode_15 = raw_call('SetNode', '1634', widget_0=WIDGET_0_8, INT=height_get)
        setnode_18 = raw_call('SetNode', '1860', widget_0=WIDGET_0_19, LATENT=ltxvconcatavlatent)

        audionormalizelufs = raw_call('AudioNormalizeLUFS', '1916',
            widget_0=-20,
            widget_1=0,
            widget_2=0,
            widget_3='full_track',
            audio=ailab_qwen3ttsvoiceclone,
        )

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )

        cliptextencode_2 = CLIPTextEncode(
            text=subgraph_a8d7fd9f.out(0),
            clip=getnode_3.out(0),
        )

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            widget_0=1,
            widget_1=False,
            bypass=getnode_19.out(0),
            image=getnode_20.out(0),
            latent=video_latent,
            vae=getnode_14.out(0),
        )

        power_lora_loader__rgthree_ = raw_call('Power Lora Loader (rgthree)', '1627',
            _outputs=('MODEL', 'CLIP'),
            widget_4='',
            model=ltx2attentiontunerpatch,
        )

        audioenhancementnode = raw_call('AudioEnhancementNode', '1904',
            widget_0='manual',
            widget_1=0.7,
            widget_10=5,
            widget_11=0,
            widget_12=0,
            widget_13='full_track',
            widget_2=0.6,
            widget_3=1.3,
            widget_4=1.2,
            widget_5=1,
            widget_6=1,
            widget_7=0.5,
            widget_8='keep_original',
            widget_9=False,
            audio=audionormalizelufs.out(0),
        )

        positive, negative = LTXVConditioning(
            frame_rate=getnode_7.out(0),
            negative=cliptextencode,
            positive=cliptextencode_2,
        )

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            audio_latent=audio_latent,
            video_latent=ltxvimgtovideoinplace_2,
        )

        setnode = raw_call('SetNode', '645', widget_0=WIDGET_0_14, CONDITIONING=positive)
        setnode_2 = raw_call('SetNode', '646', widget_0=WIDGET_0_13, CONDITIONING=negative)
        setnode_13 = raw_call('SetNode', '1617', widget_0=WIDGET_0_17, MODEL=power_lora_loader__rgthree_.out('MODEL'))
        setnode_16 = raw_call('SetNode', '1758', widget_0=WIDGET_0_7, AUDIO=audioenhancementnode.out(0))

        output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
        )

        previewaudio = PreviewAudio(audio=audioenhancementnode.out(0))

        video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
            av_latent=output_sampler,
        )

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            temporal_size=4096,
            samples=video_latent_ltxv,
            vae=getnode_12.out(0),
        )

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            audio_vae=getnode_13.out(0),
            samples=audio_latent_ltxv,
        )

        any_output, image_pass, model_pass, freemem_before, freemem_after = VRAM_Debug(
            unload_all_models=True,
            image_pass=vaedecodetiled,
        )

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            frame_rate=getnode_18.out(0),
            audio=ltxvaudiovaedecode,
            images=image_pass,
        )

        return wf.finalize({}, output_node=previewaudio)

