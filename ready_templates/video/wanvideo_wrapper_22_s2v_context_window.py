# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import OutputSpec, ReadyMetadata, new_workflow, node as raw_call, public
from vibecomfy.nodes.core import AudioEncoderEncode, AudioEncoderLoader, LoadAudio, LoadImage, PreviewAny
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, ImageResizeKJv2, InsertLatentToIndexed
from vibecomfy.nodes.videohelpersuite import VHS_LoadAudio, VHS_SelectEveryNthImage, VHS_SplitImages, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness, WanVideoAddS2VEmbeds, WanVideoBlockSwap, WanVideoContextOptions, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


AUDIO_ENCODER_NAME = 'wav2vec_xlsr_53_english_fp32.safetensors'
DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'a woman is singing passionately'
DEFAULT_SEED = 45
GUIDE_STRENGTH = 1
LORA__NAME = 'WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'
MODEL_NAME = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_3 = 'WanVideo\\S2V\\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors'
WIDGET__NAME = 'MelBandRoFormer\\MelBandRoformer_fp16.safetensors'
WIDGET__NAME_2 = 'gimmvfi_r_arb_lpips_fp32.safetensors'


OUTPUT_SPEC = OutputSpec(name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

READY_METADATA = ReadyMetadata.build(
    capability='speech_to_video_context_window',
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='S2V context-window workflow',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings()

        wanvideovaeloader = WanVideoVAELoader(
            model_name=public('model', default=MODEL_NAME),
        )

        wanvideoblockswap = WanVideoBlockSwap(
            blocks_to_swap=25,
            use_non_blocking=True,
            prefetch_blocks=1,
        )

        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            lora_0=LORA__NAME,
            strength_0=1.5,
            merge_loras=False,
        )

        audioencoderloader = AudioEncoderLoader(audio_encoder_name=AUDIO_ENCODER_NAME)

        loadaudio = LoadAudio(
            audio='NieR_ Automata - _Weight of the World_ ENG VER. by Lizz Robinett [CyOSTbel3AM].mp3',
            widget_1=None,
            widget_2=None,
        )

        text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
            model_name=MODEL_NAME_2,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
        )

        primitivenode = raw_call('PrimitiveNode', '71', widget_0=201, widget_1='fixed')

        # Inputs
        image_load, mask = LoadImage(
            image=public('image', default='2b.jpg', aliases=('input_image',)),
        )

        melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '81', widget_0=WIDGET__NAME)

        wanvideocontextoptions = WanVideoContextOptions(
            context_schedule='uniform_standard',
        )

        audio, duration = VHS_LoadAudio()

        downloadandloadgimmvfimodel = raw_call('DownloadAndLoadGIMMVFIModel', '95',
            widget_0=WIDGET__NAME_2,
            widget_1='fp16',
            widget_2=False,
        )

        wanvideomodelloader = WanVideoModelLoader(
            model=MODEL_NAME_3,
            base_precision='fp16',
            quantization='fp8_e4m3fn_scaled',
            compile_args=wanvideotorchcompilesettings,
        )

        image_image, width_image, height_image, mask_image = ImageResizeKJv2(
            width=public('width', default=256),
            height=public('height', default=256),
            upscale_method='lanczos',
            keep_proportion='crop',
            device='cpu',
            image=image_load,
        )

        melbandroformersampler = raw_call('MelBandRoFormerSampler', '82',
            audio=audio,
            model=melbandroformermodelloader.out(0),
        )

        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            widget_0=256,
            widget_1=256,
            widget_2=5,
            height=height_image,
            num_frames=primitivenode.out(0),
            width=width_image,
        )

        wanvideosetloras = WanVideoSetLoRAs(
            lora=wanvideoloraselectmulti,
            model=wanvideomodelloader,
        )

        previewany = PreviewAny(source=wanvideomodelloader)

        wanvideoencode = WanVideoEncode(
            widget_0=False,
            widget_1=272,
            widget_2=272,
            widget_3=144,
            widget_4=128,
            widget_5=0,
            widget_6=1,
            image=image_image,
            vae=wanvideovaeloader,
        )

        normalizeaudioloudness = NormalizeAudioLoudness(
            widget_0=-23,
            audio=melbandroformersampler.out(0),
        )

        wanvideosetblockswap = WanVideoSetBlockSwap(
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )

        audioencoderencode = AudioEncoderEncode(
            audio=normalizeaudioloudness,
            audio_encoder=audioencoderloader,
        )

        image_embeds, audio_frame_count = WanVideoAddS2VEmbeds(
            audio_scale=0,
            pose_end_percent=False,
            pose_start_percent=1,
            widget_0=201,
            widget_1=1,
            audio_encoder_output=audioencoderencode,
            embeds=wanvideoemptyembeds,
            frame_window_size=primitivenode.out(0),
            ref_latent=wanvideoencode,
        )

        samples, denoised_samples = WanVideoSampler(
            steps=1,
            cfg=GUIDE_STRENGTH,
            shift=4,
            seed=public('seed', default=DEFAULT_SEED),
            scheduler='dpm++_sde',
            context_options=wanvideocontextoptions,
            image_embeds=image_embeds,
            model=wanvideosetblockswap,
            text_embeds=text_embeds,
        )

        previewany_2 = PreviewAny(source=audio_frame_count)

        wanvideodecode = WanVideoDecode(
            normalization='default',
            samples=samples,
            vae=wanvideovaeloader,
        )

        insertlatenttoindexed = InsertLatentToIndexed(
            widget_0=0,
            destination=samples,
            source=wanvideoencode,
        )

        image, width, height, count = GetImageSizeAndCount(image=wanvideodecode)
        image_a, a_count, image_b, b_count = VHS_SplitImages(images=image)

        gimmvfi_interpolate = raw_call('GIMMVFI_interpolate', '96',
            widget_0=1,
            widget_1=3,
            widget_2=0,
            widget_3='fixed',
            widget_4=False,
            gimmvfi_model=downloadandloadgimmvfimodel.out(0),
            images=image_b,
        )

        # Outputs
        vhs_videocombine_2 = VHS_VideoCombine(audio=audio, images=image_b)

        image_select, count_select = VHS_SelectEveryNthImage(
            images=gimmvfi_interpolate.out(0),
        )

        vhs_videocombine = VHS_VideoCombine(audio=audio, images=image_select)

        return wf.finalize({}, output_node=vhs_videocombine, spec=OUTPUT_SPEC)

