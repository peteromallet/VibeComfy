# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
# vibecomfy: surface=canonical
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.workflow import VibeWorkflow
from vibecomfy.nodes.core import BasicGuider, BasicScheduler, CLIPLoader, ComfyMathExpression, KSamplerSelect, LoadAudio, LoadImage, LoraLoaderModelOnly, PrimitiveFloat, PrimitiveInt, RandomNoise, ResolutionSelector, SamplerCustomAdvanced, UNETLoader, VAEDecode, VAEDecodeAudio, VAELoader
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideoFFmpeg, VHS_VideoCombine


AUDIO_VAE_NAME = 'minimax_h3_audio_vae_fp32.safetensors'
CLIP_NAME = 'qwen3vl_32b_minimax_h3_int8_convrot.safetensors'
CONTINUE_THE_EXISTING_SCENE_FROM_THE_PREVIOUS_GENERATED_H3_CLIP_WITH_NO_CUT_RESET_OR_RE_ESTABLISHMENT_THE_INCOMING_PROTECTED_H3_AUDIOVISUAL_LATENT_PREFIX_IS_AUTHORITATIVE_FOR_CURRENT_POSE_MOTION_CAMERA_TRAJECTORY_FACIAL_STATE_LIGHTING_ENVIRONMENT_OBJECT_STATE_VOICE_AMBIENCE_AND_TIMING_CONNECTED_REFERENCE_IMAGES_ARE_OPTIONAL_USE_THEM_ONLY_TO_PRESERVE_STABLE_SUBJECT_IDENTITY_AND_APPEARANCE_BENEATH_THAT_INCOMING_STATE_SHOT_1_CONTINUE_THE_EXACT_MOTION_AND_SOUND_ALREADY_IN_PROGRESS_THEN_DEVELOP_THE_NEXT_ACTION_NATURALLY_DESCRIBE_WHAT_HAPPENS_NEXT_DO_NOT_RESTART_FROM_REST = 'Continue the existing scene from the previous generated H3 clip with no cut, reset, or re-establishment. The incoming protected H3 audiovisual latent prefix is authoritative for current pose, motion, camera trajectory, facial state, lighting, environment, object state, voice, ambience, and timing. Connected reference images are optional; use them only to preserve stable subject identity and appearance beneath that incoming state.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]'
DEFAULT_SEED = 123456789
DEFAULT_SEED_2 = 123469134
DEFAULT_SEED_3 = 123481479
DEFAULT_SEED_4 = 123493824
DEFAULT_SEED_5 = 123506169
DEFAULT_SEED_6 = 123518514
DEFAULT_SEED_7 = 123432109
DEFAULT_SEED_8 = 918273645
EXISTING_VIDEO = 'Existing Video'
FIXED = 'fixed'
GUIDE_STRENGTH = 0.95
LORA_NAME = 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors'
MATCH = 'match'
UNET_NAME = 'minimax_h3_ref2va_pruned_int8_convrot.safetensors'
VIDEO_H264_MP4 = 'video/h264-mp4'
VIDEO_VAE_NAME = 'minimax_h3_video_vae_int8_convrot.safetensors'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='120', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='970', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
}

READY_METADATA = ReadyMetadata.build(
    capability='video',
    template_id='video/h3_motion_context_multi_ref',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'custom_nodes': ['seitanism/ComfyUI-H3-Motion-Context-MultiRef', 'comfyui-videohelpersuite']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}},
    task='video',
    title='H3 canonical motion context multi-reference',
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Loaders
    unetloader = UNETLoader(_id='1', unet_name=UNET_NAME, _uid='1')

    cliploader = CLIPLoader(
        _id='2',
        clip_name=CLIP_NAME,
        type_='minimax',
        _uid='2',
    )

    vaeloader = VAELoader(_id='3', vae_name=VIDEO_VAE_NAME, _uid='3')
    vaeloader_2 = VAELoader(_id='4', vae_name=AUDIO_VAE_NAME, _uid='4')

    image, _, _, video_info = VHS_LoadVideoFFmpeg(
        _id='99',
        force_rate=24,
        video='',
        videopreview={'hidden': False, 'paused': False, 'params': {}, 'muted': False},
        _uid='99',
    )

    # Inputs
    primitivefloat = PrimitiveFloat(_id='101', value=5, _uid='101')

    randomnoise_2 = RandomNoise(
        _id='120',
        noise_seed=DEFAULT_SEED,
        control_after_generate=FIXED,
        _uid='120',
    )

    randomnoise_3 = RandomNoise(
        _id='210',
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=FIXED,
        _mode=4,
        _uid='210',
    )

    randomnoise_4 = RandomNoise(
        _id='310',
        noise_seed=DEFAULT_SEED_3,
        control_after_generate=FIXED,
        _mode=4,
        _uid='310',
    )

    randomnoise_5 = RandomNoise(
        _id='410',
        noise_seed=DEFAULT_SEED_4,
        control_after_generate=FIXED,
        _mode=4,
        _uid='410',
    )

    randomnoise_6 = RandomNoise(
        _id='510',
        noise_seed=DEFAULT_SEED_5,
        control_after_generate=FIXED,
        _mode=4,
        _uid='510',
    )

    randomnoise_7 = RandomNoise(
        _id='610',
        noise_seed=DEFAULT_SEED_6,
        control_after_generate=FIXED,
        _mode=4,
        _uid='610',
    )

    primitiveint_3 = PrimitiveInt(
        _id='936',
        value=8,
        control_after_generate='fixed',
        _uid='936',
    )

    # Sampling
    ksamplerselect = KSamplerSelect(_id='937', sampler_name='res_multistep', _uid='937')

    primitiveint_4 = PrimitiveInt(
        _id='939',
        value=39,
        control_after_generate='fixed',
        _uid='939',
    )

    primitiveint_5 = PrimitiveInt(
        _id='940',
        value=39,
        control_after_generate='fixed',
        _uid='940',
    )

    image_2, _ = LoadImage(
        _id='970',
        image='',
        _mode=4,
        _uid='970',
    )

    randomnoise_8 = RandomNoise(
        _id='974',
        noise_seed=DEFAULT_SEED_7,
        control_after_generate=FIXED,
        _mode=4,
        _uid='974',
    )

    minimaxh3avextensioncontroller = raw_call('MiniMaxH3AVExtensionController', '980',
        widget_0=EXISTING_VIDEO,
        widget_1=1,
        widget_2=8,
        widget_3='All Active',
        widget_4='Keep source audio',
        _uid='980',
    )

    image_3, _ = LoadImage(_id='1020', image='', _uid='1020')
    image_4, _ = LoadImage(_id='1021', image='', _uid='1021')

    width, height = ResolutionSelector(
        _id='1024',
        aspect_ratio='16:9 (Widescreen)',
        megapixels=0.5,
        widget_2=32,
        _uid='1024',
    )

    loadaudio = LoadAudio(
        _id='1027',
        audio='',
        _mode=4,
        _uid='1027',
    )

    loadaudio_2 = LoadAudio(
        _id='1028',
        audio='',
        _mode=4,
        _uid='1028',
    )

    randomnoise = RandomNoise(
        _id='1034',
        noise_seed=DEFAULT_SEED_8,
        control_after_generate=FIXED,
        _mode=4,
        _uid='1034',
    )

    minimaxh3avstartmodeparam = raw_call('MiniMaxH3AVStartModeParam', '1038', widget_0=EXISTING_VIDEO, _uid='1038')

    primitiveint = PrimitiveInt(
        _id='1039',
        value=1,
        control_after_generate='fixed',
        _uid='1039',
    )

    primitiveint_2 = PrimitiveInt(
        _id='1040',
        value=8,
        control_after_generate='fixed',
        _uid='1040',
    )

    minimaxh3avsourceaudiomodeparam = raw_call('MiniMaxH3AVSourceAudioModeParam', '1041',
        widget_0='Keep source audio',
        _uid='1041',
    )

    minimaxh3cropto32 = raw_call('MiniMaxH3CropTo32', '100', _uid='100')

    _, comfy_int, _ = ComfyMathExpression(
        _id='102',
        expression='max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17',
        _uid='102',
    )

    modelattentionbackend = raw_call('ModelAttentionBackend', '988', widget_0='comfy kitchen attention', _uid='988')
    reroute = raw_call('Reroute', '1029', _uid='1029')
    reroute_2 = raw_call('Reroute', '1030', _uid='1030')

    loraloadermodelonly = LoraLoaderModelOnly(
        _id='935',
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        _uid='935',
    )

    minimaxh3startcanvasselector = raw_call('MiniMaxH3StartCanvasSelector', '972',
        widget_0=960,
        widget_1=544,
        widget_2=0,
        widget_3=0,
        _uid='972',
    )

    minimaxh3sourceaudioregenlength = raw_call('MiniMaxH3SourceAudioRegenLength', '1031',
        source_fps=24,
        _mode=4,
        _uid='1031',
    )

    minimaxh3sigmashift = raw_call('MiniMaxH3SigmaShift', '5',
        widget_0=12,
        widget_1=3,
        _uid='5',
    )

    minimaxh3referencetovideo_2 = raw_call('MiniMaxH3ReferenceToVideo', '110',
        widget_0='Continue directly from the final moment of the selected start clip with no cut, reset, or re-establishment. The incoming protected audiovisual prefix is authoritative for pose, motion, camera trajectory, lighting, environment, object state, voice, ambience, and timing. Connected reference images are identity/appearance references only; never pull the subject back toward a reference-image pose, expression, framing, or lighting.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]',
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _uid='110',
    )

    minimaxh3referencetovideo_3 = raw_call('MiniMaxH3ReferenceToVideo', '200',
        widget_0=CONTINUE_THE_EXISTING_SCENE_FROM_THE_PREVIOUS_GENERATED_H3_CLIP_WITH_NO_CUT_RESET_OR_RE_ESTABLISHMENT_THE_INCOMING_PROTECTED_H3_AUDIOVISUAL_LATENT_PREFIX_IS_AUTHORITATIVE_FOR_CURRENT_POSE_MOTION_CAMERA_TRAJECTORY_FACIAL_STATE_LIGHTING_ENVIRONMENT_OBJECT_STATE_VOICE_AMBIENCE_AND_TIMING_CONNECTED_REFERENCE_IMAGES_ARE_OPTIONAL_USE_THEM_ONLY_TO_PRESERVE_STABLE_SUBJECT_IDENTITY_AND_APPEARANCE_BENEATH_THAT_INCOMING_STATE_SHOT_1_CONTINUE_THE_EXACT_MOTION_AND_SOUND_ALREADY_IN_PROGRESS_THEN_DEVELOP_THE_NEXT_ACTION_NATURALLY_DESCRIBE_WHAT_HAPPENS_NEXT_DO_NOT_RESTART_FROM_REST,
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _mode=4,
        _uid='200',
    )

    minimaxh3referencetovideo_4 = raw_call('MiniMaxH3ReferenceToVideo', '300',
        widget_0=CONTINUE_THE_EXISTING_SCENE_FROM_THE_PREVIOUS_GENERATED_H3_CLIP_WITH_NO_CUT_RESET_OR_RE_ESTABLISHMENT_THE_INCOMING_PROTECTED_H3_AUDIOVISUAL_LATENT_PREFIX_IS_AUTHORITATIVE_FOR_CURRENT_POSE_MOTION_CAMERA_TRAJECTORY_FACIAL_STATE_LIGHTING_ENVIRONMENT_OBJECT_STATE_VOICE_AMBIENCE_AND_TIMING_CONNECTED_REFERENCE_IMAGES_ARE_OPTIONAL_USE_THEM_ONLY_TO_PRESERVE_STABLE_SUBJECT_IDENTITY_AND_APPEARANCE_BENEATH_THAT_INCOMING_STATE_SHOT_1_CONTINUE_THE_EXACT_MOTION_AND_SOUND_ALREADY_IN_PROGRESS_THEN_DEVELOP_THE_NEXT_ACTION_NATURALLY_DESCRIBE_WHAT_HAPPENS_NEXT_DO_NOT_RESTART_FROM_REST,
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _mode=4,
        _uid='300',
    )

    minimaxh3referencetovideo_5 = raw_call('MiniMaxH3ReferenceToVideo', '400',
        widget_0=CONTINUE_THE_EXISTING_SCENE_FROM_THE_PREVIOUS_GENERATED_H3_CLIP_WITH_NO_CUT_RESET_OR_RE_ESTABLISHMENT_THE_INCOMING_PROTECTED_H3_AUDIOVISUAL_LATENT_PREFIX_IS_AUTHORITATIVE_FOR_CURRENT_POSE_MOTION_CAMERA_TRAJECTORY_FACIAL_STATE_LIGHTING_ENVIRONMENT_OBJECT_STATE_VOICE_AMBIENCE_AND_TIMING_CONNECTED_REFERENCE_IMAGES_ARE_OPTIONAL_USE_THEM_ONLY_TO_PRESERVE_STABLE_SUBJECT_IDENTITY_AND_APPEARANCE_BENEATH_THAT_INCOMING_STATE_SHOT_1_CONTINUE_THE_EXACT_MOTION_AND_SOUND_ALREADY_IN_PROGRESS_THEN_DEVELOP_THE_NEXT_ACTION_NATURALLY_DESCRIBE_WHAT_HAPPENS_NEXT_DO_NOT_RESTART_FROM_REST,
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _mode=4,
        _uid='400',
    )

    minimaxh3referencetovideo_6 = raw_call('MiniMaxH3ReferenceToVideo', '500',
        widget_0=CONTINUE_THE_EXISTING_SCENE_FROM_THE_PREVIOUS_GENERATED_H3_CLIP_WITH_NO_CUT_RESET_OR_RE_ESTABLISHMENT_THE_INCOMING_PROTECTED_H3_AUDIOVISUAL_LATENT_PREFIX_IS_AUTHORITATIVE_FOR_CURRENT_POSE_MOTION_CAMERA_TRAJECTORY_FACIAL_STATE_LIGHTING_ENVIRONMENT_OBJECT_STATE_VOICE_AMBIENCE_AND_TIMING_CONNECTED_REFERENCE_IMAGES_ARE_OPTIONAL_USE_THEM_ONLY_TO_PRESERVE_STABLE_SUBJECT_IDENTITY_AND_APPEARANCE_BENEATH_THAT_INCOMING_STATE_SHOT_1_CONTINUE_THE_EXACT_MOTION_AND_SOUND_ALREADY_IN_PROGRESS_THEN_DEVELOP_THE_NEXT_ACTION_NATURALLY_DESCRIBE_WHAT_HAPPENS_NEXT_DO_NOT_RESTART_FROM_REST,
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _mode=4,
        _uid='500',
    )

    minimaxh3referencetovideo_7 = raw_call('MiniMaxH3ReferenceToVideo', '600',
        widget_0=CONTINUE_THE_EXISTING_SCENE_FROM_THE_PREVIOUS_GENERATED_H3_CLIP_WITH_NO_CUT_RESET_OR_RE_ESTABLISHMENT_THE_INCOMING_PROTECTED_H3_AUDIOVISUAL_LATENT_PREFIX_IS_AUTHORITATIVE_FOR_CURRENT_POSE_MOTION_CAMERA_TRAJECTORY_FACIAL_STATE_LIGHTING_ENVIRONMENT_OBJECT_STATE_VOICE_AMBIENCE_AND_TIMING_CONNECTED_REFERENCE_IMAGES_ARE_OPTIONAL_USE_THEM_ONLY_TO_PRESERVE_STABLE_SUBJECT_IDENTITY_AND_APPEARANCE_BENEATH_THAT_INCOMING_STATE_SHOT_1_CONTINUE_THE_EXACT_MOTION_AND_SOUND_ALREADY_IN_PROGRESS_THEN_DEVELOP_THE_NEXT_ACTION_NATURALLY_DESCRIBE_WHAT_HAPPENS_NEXT_DO_NOT_RESTART_FROM_REST,
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _mode=4,
        _uid='600',
    )

    minimaxh3referencetovideo_8 = raw_call('MiniMaxH3ReferenceToVideo', '973',
        widget_0='Create the opening clip for a new continuous video. Establish coherent subject identity, camera, lighting, environment, motion, voice, ambience, and audiovisual timing so later masked extensions can continue seamlessly. If an H3 keyframe is enabled at frame 1, treat it as the exact opening image and animate naturally forward. Connected reference images are identity/appearance references only and should not force their pose, framing, expression, or lighting onto the shot.',
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _mode=4,
        _uid='973',
    )

    minimaxh3referencetovideo = raw_call('MiniMaxH3ReferenceToVideo', '1032',
        widget_0='Regenerate the complete soundtrack for the supplied source video. The entire visual stream is protected and authoritative: do not change, reinterpret, restart, or replace the video. Generate synchronized audio for the full clip from beginning to end, including dialogue/voice when visually implied, foley, impacts, movement sounds, room tone, ambience, and other scene-appropriate sound. Match visible timing precisely and maintain continuous acoustic perspective across the whole source clip.',
        widget_1=960,
        widget_2=544,
        widget_3=362,
        widget_4=MATCH,
        _mode=4,
        _uid='1032',
    )

    basicguider_2 = BasicGuider(_id='121', _uid='121')
    basicguider_3 = BasicGuider(_id='211', _mode=4, _uid='211')
    basicguider_4 = BasicGuider(_id='311', _mode=4, _uid='311')
    basicguider_5 = BasicGuider(_id='411', _mode=4, _uid='411')
    basicguider_6 = BasicGuider(_id='511', _mode=4, _uid='511')
    basicguider_7 = BasicGuider(_id='611', _mode=4, _uid='611')
    basicscheduler = BasicScheduler(_id='976', scheduler='simple', _uid='976')

    minimaxh3customkeyframes = raw_call('MiniMaxH3CustomKeyframes', '1022',
        widget_0='{"count":1,"positions":[1]}',
        widget_1='1-based',
        widget_2='disabled',
        _mode=4,
        _uid='1022',
    )

    minimaxh3sourceaudioregenmask = raw_call('MiniMaxH3SourceAudioRegenMask', '1033',
        crop='disabled',
        source_fps=24,
        _mode=4,
        _uid='1033',
    )

    basicguider = BasicGuider(_id='1035', _mode=4, _uid='1035')
    basicguider_8 = BasicGuider(_id='975', _mode=4, _uid='975')
    output_8, _ = SamplerCustomAdvanced(_id='1036', _mode=4, _uid='1036')
    output_7, _ = SamplerCustomAdvanced(_id='977', _mode=4, _uid='977')
    minimaxh3sourceaudiopolicy = raw_call('MiniMaxH3SourceAudioPolicy', '1037', source_fps=24, _uid='1037')

    minimaxh3startmaskedcontext = raw_call('MiniMaxH3StartMaskedContext', '103',
        widget_0=39,
        widget_1=8,
        widget_2=24,
        widget_3='disabled',
        _uid='103',
    )

    # Decode
    vaedecode_3 = VAEDecode(_id='1008', _mode=4, _uid='1008')
    vaedecodeaudio_4 = VAEDecodeAudio(_id='1009', _mode=4, _uid='1009')
    output, _ = SamplerCustomAdvanced(_id='124', _uid='124')

    # Outputs
    vhs_videocombine_4 = VHS_VideoCombine(
        _id='1010',
        frame_rate=24,
        filename_prefix='h3_preview/generated_starter',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=False,
        trim_to_audio=True,
        videopreview={'hidden': False, 'paused': False, 'params': {}},
        _mode=4,
        _uid='1010',
    )

    minimaxh3generatedavmaskedcontext = raw_call('MiniMaxH3GeneratedAVMaskedContext', '201',
        widget_0=39,
        widget_1=8,
        _mode=4,
        _uid='201',
    )

    vaedecode_4 = VAEDecode(_id='990', _uid='990')
    vaedecodeaudio_5 = VAEDecodeAudio(_id='991', _uid='991')
    output_2, _ = SamplerCustomAdvanced(_id='214', _mode=4, _uid='214')

    vhs_videocombine_5 = VHS_VideoCombine(
        _id='992',
        frame_rate=24,
        filename_prefix='h3_preview/extension_01',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=False,
        trim_to_audio=True,
        videopreview={'hidden': False, 'paused': False, 'params': {}},
        _uid='992',
    )

    minimaxh3generatedavmaskedcontext_2 = raw_call('MiniMaxH3GeneratedAVMaskedContext', '301',
        widget_0=39,
        widget_1=8,
        _mode=4,
        _uid='301',
    )

    vaedecode_5 = VAEDecode(_id='993', _mode=4, _uid='993')
    vaedecodeaudio_6 = VAEDecodeAudio(_id='994', _mode=4, _uid='994')
    output_3, _ = SamplerCustomAdvanced(_id='314', _mode=4, _uid='314')

    vhs_videocombine_6 = VHS_VideoCombine(
        _id='995',
        frame_rate=24,
        filename_prefix='h3_preview/extension_02',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=False,
        trim_to_audio=True,
        videopreview={'hidden': False, 'paused': False, 'params': {}},
        _mode=4,
        _uid='995',
    )

    minimaxh3generatedavmaskedcontext_3 = raw_call('MiniMaxH3GeneratedAVMaskedContext', '401',
        widget_0=39,
        widget_1=8,
        _mode=4,
        _uid='401',
    )

    vaedecode_6 = VAEDecode(_id='996', _mode=4, _uid='996')
    vaedecodeaudio_7 = VAEDecodeAudio(_id='997', _mode=4, _uid='997')
    output_4, _ = SamplerCustomAdvanced(_id='414', _mode=4, _uid='414')

    vhs_videocombine_7 = VHS_VideoCombine(
        _id='998',
        frame_rate=24,
        filename_prefix='h3_preview/extension_03',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=False,
        trim_to_audio=True,
        videopreview={'hidden': False, 'paused': False, 'params': {}},
        _mode=4,
        _uid='998',
    )

    minimaxh3generatedavmaskedcontext_4 = raw_call('MiniMaxH3GeneratedAVMaskedContext', '501',
        widget_0=39,
        widget_1=8,
        _mode=4,
        _uid='501',
    )

    vaedecode_7 = VAEDecode(_id='999', _mode=4, _uid='999')
    vaedecodeaudio = VAEDecodeAudio(_id='1000', _mode=4, _uid='1000')
    output_5, _ = SamplerCustomAdvanced(_id='514', _mode=4, _uid='514')

    vhs_videocombine = VHS_VideoCombine(
        _id='1001',
        frame_rate=24,
        filename_prefix='h3_preview/extension_04',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=False,
        trim_to_audio=True,
        videopreview={'hidden': False, 'paused': False, 'params': {}},
        _mode=4,
        _uid='1001',
    )

    minimaxh3generatedavmaskedcontext_5 = raw_call('MiniMaxH3GeneratedAVMaskedContext', '601',
        widget_0=39,
        widget_1=8,
        _mode=4,
        _uid='601',
    )

    vaedecode = VAEDecode(_id='1002', _mode=4, _uid='1002')
    vaedecodeaudio_2 = VAEDecodeAudio(_id='1003', _mode=4, _uid='1003')
    output_6, _ = SamplerCustomAdvanced(_id='614', _mode=4, _uid='614')

    vhs_videocombine_2 = VHS_VideoCombine(
        _id='1004',
        frame_rate=24,
        filename_prefix='h3_preview/extension_05',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=False,
        trim_to_audio=True,
        videopreview={'hidden': False, 'paused': False, 'params': {}},
        _mode=4,
        _uid='1004',
    )

    vaedecode_2 = VAEDecode(_id='1005', _mode=4, _uid='1005')
    vaedecodeaudio_3 = VAEDecodeAudio(_id='1006', _mode=4, _uid='1006')

    vhs_videocombine_3 = VHS_VideoCombine(
        _id='1007',
        frame_rate=24,
        filename_prefix='h3_preview/extension_06',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=False,
        trim_to_audio=True,
        videopreview={'hidden': False, 'paused': False, 'params': {}},
        _mode=4,
        _uid='1007',
    )

    minimaxh3lastactivevhspreviewbarrier = raw_call('MiniMaxH3LastActiveVHSPreviewBarrier', '1042',
        widget_0=6,
        _uid='1042',
    )

    minimaxh3streamliveextensionavtovhs = raw_call('MiniMaxH3StreamLiveExtensionAVToVHS', '946',
        widget_0=6,
        widget_1=39,
        widget_10=True,
        widget_2=39,
        widget_3=24,
        widget_4='disabled',
        widget_5='video/masked_av_extension',
        widget_6='yuv420p',
        widget_7=19,
        widget_8=False,
        widget_9=True,
        _uid='946',
    )

    minimaxh3finalizevhsoutput = raw_call('MiniMaxH3FinalizeVHSOutput', '1043', _uid='1043')

    wf.connect('5.0', '121.model')
    wf.connect('110.0', '121.conditioning')
    wf.connect('120.0', '124.noise')
    wf.connect('121.0', '124.guider')
    wf.connect('937.0', '124.sampler')
    wf.connect('976.0', '124.sigmas')
    wf.connect('103.0', '124.latent_image')
    wf.connect('5.0', '211.model')
    wf.connect('200.0', '211.conditioning')
    wf.connect('210.0', '214.noise')
    wf.connect('211.0', '214.guider')
    wf.connect('937.0', '214.sampler')
    wf.connect('976.0', '214.sigmas')
    wf.connect('201.0', '214.latent_image')
    wf.connect('2.0', '300.clip')
    wf.connect('3.0', '300.vae')
    wf.connect('4.0', '300.audio_vae')
    wf.connect('1020.0', '300.ref_images.ref_image_0')
    wf.connect('1021.0', '300.ref_images.ref_image_1')
    wf.connect('1029.0', '300.ref_audios.ref_audio_0')
    wf.connect('972.0', '300.width')
    wf.connect('972.1', '300.height')
    wf.connect('102.1', '300.length')
    wf.connect('1030.0', '300.ref_audios.ref_audio_1')
    wf.connect('5.0', '311.model')
    wf.connect('300.0', '311.conditioning')
    wf.connect('310.0', '314.noise')
    wf.connect('311.0', '314.guider')
    wf.connect('937.0', '314.sampler')
    wf.connect('976.0', '314.sigmas')
    wf.connect('301.0', '314.latent_image')
    wf.connect('2.0', '400.clip')
    wf.connect('3.0', '400.vae')
    wf.connect('4.0', '400.audio_vae')
    wf.connect('1020.0', '400.ref_images.ref_image_0')
    wf.connect('1021.0', '400.ref_images.ref_image_1')
    wf.connect('1029.0', '400.ref_audios.ref_audio_0')
    wf.connect('972.0', '400.width')
    wf.connect('972.1', '400.height')
    wf.connect('102.1', '400.length')
    wf.connect('1030.0', '400.ref_audios.ref_audio_1')
    wf.connect('5.0', '411.model')
    wf.connect('400.0', '411.conditioning')
    wf.connect('410.0', '414.noise')
    wf.connect('411.0', '414.guider')
    wf.connect('937.0', '414.sampler')
    wf.connect('976.0', '414.sigmas')
    wf.connect('401.0', '414.latent_image')
    wf.connect('2.0', '500.clip')
    wf.connect('3.0', '500.vae')
    wf.connect('4.0', '500.audio_vae')
    wf.connect('1020.0', '500.ref_images.ref_image_0')
    wf.connect('1021.0', '500.ref_images.ref_image_1')
    wf.connect('1029.0', '500.ref_audios.ref_audio_0')
    wf.connect('972.0', '500.width')
    wf.connect('972.1', '500.height')
    wf.connect('102.1', '500.length')
    wf.connect('1030.0', '500.ref_audios.ref_audio_1')
    wf.connect('5.0', '511.model')
    wf.connect('500.0', '511.conditioning')
    wf.connect('510.0', '514.noise')
    wf.connect('511.0', '514.guider')
    wf.connect('937.0', '514.sampler')
    wf.connect('976.0', '514.sigmas')
    wf.connect('501.0', '514.latent_image')
    wf.connect('2.0', '600.clip')
    wf.connect('3.0', '600.vae')
    wf.connect('4.0', '600.audio_vae')
    wf.connect('1020.0', '600.ref_images.ref_image_0')
    wf.connect('1021.0', '600.ref_images.ref_image_1')
    wf.connect('1029.0', '600.ref_audios.ref_audio_0')
    wf.connect('972.0', '600.width')
    wf.connect('972.1', '600.height')
    wf.connect('102.1', '600.length')
    wf.connect('1030.0', '600.ref_audios.ref_audio_1')
    wf.connect('5.0', '611.model')
    wf.connect('600.0', '611.conditioning')
    wf.connect('610.0', '614.noise')
    wf.connect('611.0', '614.guider')
    wf.connect('937.0', '614.sampler')
    wf.connect('976.0', '614.sigmas')
    wf.connect('601.0', '614.latent_image')
    wf.connect('110.1', '103.latent')
    wf.connect('3.0', '103.vae')
    wf.connect('4.0', '103.audio_vae')
    wf.connect('1038.0', '103.start_mode')
    wf.connect('100.0', '103.source_frames')
    wf.connect('1037.0', '103.source_audio')
    wf.connect('977.0', '103.live_starter_latent')
    wf.connect('939.0', '103.context_length')
    wf.connect('1040.0', '103.audio_feather_ticks')
    wf.connect('200.1', '201.latent')
    wf.connect('124.0', '201.source_latent')
    wf.connect('939.0', '201.context_length')
    wf.connect('1040.0', '201.audio_feather_ticks')
    wf.connect('300.1', '301.latent')
    wf.connect('214.0', '301.source_latent')
    wf.connect('939.0', '301.context_length')
    wf.connect('1040.0', '301.audio_feather_ticks')
    wf.connect('400.1', '401.latent')
    wf.connect('314.0', '401.source_latent')
    wf.connect('939.0', '401.context_length')
    wf.connect('1040.0', '401.audio_feather_ticks')
    wf.connect('500.1', '501.latent')
    wf.connect('414.0', '501.source_latent')
    wf.connect('939.0', '501.context_length')
    wf.connect('1040.0', '501.audio_feather_ticks')
    wf.connect('600.1', '601.latent')
    wf.connect('514.0', '601.source_latent')
    wf.connect('939.0', '601.context_length')
    wf.connect('1040.0', '601.audio_feather_ticks')
    wf.connect('974.0', '977.noise')
    wf.connect('975.0', '977.guider')
    wf.connect('937.0', '977.sampler')
    wf.connect('976.0', '977.sigmas')
    wf.connect('973.1', '977.latent_image')
    wf.connect('2.0', '200.clip')
    wf.connect('3.0', '200.vae')
    wf.connect('4.0', '200.audio_vae')
    wf.connect('1020.0', '200.ref_images.ref_image_0')
    wf.connect('1021.0', '200.ref_images.ref_image_1')
    wf.connect('1029.0', '200.ref_audios.ref_audio_0')
    wf.connect('972.0', '200.width')
    wf.connect('972.1', '200.height')
    wf.connect('102.1', '200.length')
    wf.connect('1030.0', '200.ref_audios.ref_audio_1')
    wf.connect('990.0', '992.images')
    wf.connect('991.0', '992.audio')
    wf.connect('214.0', '993.samples')
    wf.connect('3.0', '993.vae')
    wf.connect('214.0', '994.samples')
    wf.connect('4.0', '994.vae')
    wf.connect('993.0', '995.images')
    wf.connect('994.0', '995.audio')
    wf.connect('314.0', '996.samples')
    wf.connect('3.0', '996.vae')
    wf.connect('314.0', '997.samples')
    wf.connect('4.0', '997.vae')
    wf.connect('996.0', '998.images')
    wf.connect('997.0', '998.audio')
    wf.connect('414.0', '999.samples')
    wf.connect('3.0', '999.vae')
    wf.connect('414.0', '1000.samples')
    wf.connect('4.0', '1000.vae')
    wf.connect('999.0', '1001.images')
    wf.connect('1000.0', '1001.audio')
    wf.connect('514.0', '1002.samples')
    wf.connect('3.0', '1002.vae')
    wf.connect('514.0', '1003.samples')
    wf.connect('4.0', '1003.vae')
    wf.connect('1002.0', '1004.images')
    wf.connect('1003.0', '1004.audio')
    wf.connect('614.0', '1005.samples')
    wf.connect('3.0', '1005.vae')
    wf.connect('614.0', '1006.samples')
    wf.connect('4.0', '1006.vae')
    wf.connect('1005.0', '1007.images')
    wf.connect('1006.0', '1007.audio')
    wf.connect('2.0', '110.clip')
    wf.connect('3.0', '110.vae')
    wf.connect('4.0', '110.audio_vae')
    wf.connect('1020.0', '110.ref_images.ref_image_0')
    wf.connect('1021.0', '110.ref_images.ref_image_1')
    wf.connect('1029.0', '110.ref_audios.ref_audio_0')
    wf.connect('972.0', '110.width')
    wf.connect('972.1', '110.height')
    wf.connect('102.1', '110.length')
    wf.connect('1030.0', '110.ref_audios.ref_audio_1')
    wf.connect('5.0', '975.model')
    wf.connect('1022.0', '975.conditioning')
    wf.connect('977.0', '1008.samples')
    wf.connect('3.0', '1008.vae')
    wf.connect('977.0', '1009.samples')
    wf.connect('4.0', '1009.vae')
    wf.connect('124.0', '991.samples')
    wf.connect('4.0', '991.vae')
    wf.connect('124.0', '990.samples')
    wf.connect('3.0', '990.vae')
    wf.connect('2.0', '973.clip')
    wf.connect('3.0', '973.vae')
    wf.connect('4.0', '973.audio_vae')
    wf.connect('1020.0', '973.ref_images.ref_image_0')
    wf.connect('1021.0', '973.ref_images.ref_image_1')
    wf.connect('1029.0', '973.ref_audios.ref_audio_0')
    wf.connect('972.0', '973.width')
    wf.connect('972.1', '973.height')
    wf.connect('102.1', '973.length')
    wf.connect('1030.0', '973.ref_audios.ref_audio_1')
    wf.connect('973.0', '1022.conditioning')
    wf.connect('3.0', '1022.vae')
    wf.connect('973.1', '1022.latent')
    wf.connect('970.0', '1022.keyframe_image_1')
    wf.connect('3.0', '946.video_vae')
    wf.connect('4.0', '946.audio_vae')
    wf.connect('1038.0', '946.start_mode')
    wf.connect('100.0', '946.source_frames')
    wf.connect('1037.0', '946.source_audio')
    wf.connect('977.0', '946.starter_latent')
    wf.connect('1042.0', '946.preview_gate')
    wf.connect('124.0', '946.extension_1')
    wf.connect('214.0', '946.extension_2')
    wf.connect('314.0', '946.extension_3')
    wf.connect('414.0', '946.extension_4')
    wf.connect('514.0', '946.extension_5')
    wf.connect('614.0', '946.extension_6')
    wf.connect('1039.0', '946.active_extensions')
    wf.connect('939.0', '946.context_frames')
    wf.connect('940.0', '946.video_overlap_frames')
    wf.connect('99.0', '100.images')
    wf.connect('5.0', '976.model')
    wf.connect('936.0', '976.steps')
    wf.connect('935.0', '5.model')
    wf.connect('988.0', '935.model')
    wf.connect('1.0', '988.model')
    wf.connect('1008.0', '1010.images')
    wf.connect('1009.0', '1010.audio')
    wf.connect('1038.0', '972.start_mode')
    wf.connect('1024.0', '972.generated_width')
    wf.connect('1024.1', '972.generated_height')
    wf.connect('100.1', '972.source_width')
    wf.connect('100.2', '972.source_height')
    wf.connect('101.0', '102.values.a')
    wf.connect('1027.0', '1029._un392')
    wf.connect('1028.0', '1030._un400')
    wf.connect('100.0', '1031.source_frames')
    wf.connect('2.0', '1032.clip')
    wf.connect('3.0', '1032.vae')
    wf.connect('4.0', '1032.audio_vae')
    wf.connect('1020.0', '1032.ref_images.ref_image_0')
    wf.connect('1021.0', '1032.ref_images.ref_image_1')
    wf.connect('1029.0', '1032.ref_audios.ref_audio_0')
    wf.connect('100.1', '1032.width')
    wf.connect('100.2', '1032.height')
    wf.connect('1031.0', '1032.length')
    wf.connect('1030.0', '1032.ref_audios.ref_audio_1')
    wf.connect('1032.1', '1033.latent')
    wf.connect('3.0', '1033.vae')
    wf.connect('100.0', '1033.source_frames')
    wf.connect('5.0', '1035.model')
    wf.connect('1032.0', '1035.conditioning')
    wf.connect('1034.0', '1036.noise')
    wf.connect('1035.0', '1036.guider')
    wf.connect('937.0', '1036.sampler')
    wf.connect('976.0', '1036.sigmas')
    wf.connect('1033.0', '1036.latent_image')
    wf.connect('4.0', '1037.audio_vae')
    wf.connect('1041.0', '1037.mode')
    wf.connect('100.0', '1037.source_frames')
    wf.connect('99.3', '1037.video_info')
    wf.connect('1036.0', '1037.regenerated_latent')
    wf.connect('1039.0', '1042.active_extensions')
    wf.connect('992.0', '1042.preview_1')
    wf.connect('995.0', '1042.preview_2')
    wf.connect('998.0', '1042.preview_3')
    wf.connect('1001.0', '1042.preview_4')
    wf.connect('1004.0', '1042.preview_5')
    wf.connect('1007.0', '1042.preview_6')
    wf.connect('946.0', '1043.filenames')
    wf = wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine_4, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='h3_preview/generated_starter')
    wf.nodes['1'].inputs = {'unet_name': 'minimax_h3_ref2va_pruned_int8_convrot.safetensors', 'weight_dtype': 'default'}
    wf.nodes['1'].widgets = {}
    wf.nodes['1'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1'].native_input_names = []
    wf.nodes['1'].native_output_names = ['MODEL']
    wf.nodes['1'].native_input_types = []
    wf.nodes['1'].native_output_types = ['MODEL']
    wf.nodes['1'].native_input_optional = []
    wf.nodes['100'].inputs = {}
    wf.nodes['100'].widgets = {}
    wf.nodes['100'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['100'].native_input_names = ['images']
    wf.nodes['100'].native_output_names = ['images', 'width', 'height']
    wf.nodes['100'].native_input_types = ['IMAGE']
    wf.nodes['100'].native_output_types = ['IMAGE', 'INT', 'INT']
    wf.nodes['100'].native_input_optional = [False]
    wf.nodes['1000'].inputs = {}
    wf.nodes['1000'].widgets = {}
    wf.nodes['1000'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1000'].native_input_names = ['samples', 'vae']
    wf.nodes['1000'].native_output_names = ['AUDIO']
    wf.nodes['1000'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['1000'].native_output_types = ['AUDIO']
    wf.nodes['1000'].native_input_optional = [False, False]
    wf.nodes['1001'].inputs = {'frame_rate': 24, 'loop_count': 0, 'filename_prefix': 'h3_preview/extension_04', 'format': 'video/h264-mp4', 'pix_fmt': 'yuv420p', 'crf': 19, 'save_metadata': False, 'trim_to_audio': True, 'pingpong': False, 'save_output': False, 'videopreview': {'hidden': False, 'paused': False, 'params': {}}}
    wf.nodes['1001'].widgets = {}
    wf.nodes['1001'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1001'].native_input_names = ['images', 'audio', 'meta_batch', 'vae']
    wf.nodes['1001'].native_output_names = ['Filenames']
    wf.nodes['1001'].native_input_types = ['IMAGE', 'AUDIO', 'VHS_BatchManager', 'VAE']
    wf.nodes['1001'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['1001'].native_input_optional = [False, True, True, True]
    wf.nodes['1002'].inputs = {}
    wf.nodes['1002'].widgets = {}
    wf.nodes['1002'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1002'].native_input_names = ['samples', 'vae']
    wf.nodes['1002'].native_output_names = ['IMAGE']
    wf.nodes['1002'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['1002'].native_output_types = ['IMAGE']
    wf.nodes['1002'].native_input_optional = [False, False]
    wf.nodes['1003'].inputs = {}
    wf.nodes['1003'].widgets = {}
    wf.nodes['1003'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1003'].native_input_names = ['samples', 'vae']
    wf.nodes['1003'].native_output_names = ['AUDIO']
    wf.nodes['1003'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['1003'].native_output_types = ['AUDIO']
    wf.nodes['1003'].native_input_optional = [False, False]
    wf.nodes['1004'].inputs = {'frame_rate': 24, 'loop_count': 0, 'filename_prefix': 'h3_preview/extension_05', 'format': 'video/h264-mp4', 'pix_fmt': 'yuv420p', 'crf': 19, 'save_metadata': False, 'trim_to_audio': True, 'pingpong': False, 'save_output': False, 'videopreview': {'hidden': False, 'paused': False, 'params': {}}}
    wf.nodes['1004'].widgets = {}
    wf.nodes['1004'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1004'].native_input_names = ['images', 'audio', 'meta_batch', 'vae']
    wf.nodes['1004'].native_output_names = ['Filenames']
    wf.nodes['1004'].native_input_types = ['IMAGE', 'AUDIO', 'VHS_BatchManager', 'VAE']
    wf.nodes['1004'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['1004'].native_input_optional = [False, True, True, True]
    wf.nodes['1005'].inputs = {}
    wf.nodes['1005'].widgets = {}
    wf.nodes['1005'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1005'].native_input_names = ['samples', 'vae']
    wf.nodes['1005'].native_output_names = ['IMAGE']
    wf.nodes['1005'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['1005'].native_output_types = ['IMAGE']
    wf.nodes['1005'].native_input_optional = [False, False]
    wf.nodes['1006'].inputs = {}
    wf.nodes['1006'].widgets = {}
    wf.nodes['1006'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1006'].native_input_names = ['samples', 'vae']
    wf.nodes['1006'].native_output_names = ['AUDIO']
    wf.nodes['1006'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['1006'].native_output_types = ['AUDIO']
    wf.nodes['1006'].native_input_optional = [False, False]
    wf.nodes['1007'].inputs = {'frame_rate': 24, 'loop_count': 0, 'filename_prefix': 'h3_preview/extension_06', 'format': 'video/h264-mp4', 'pix_fmt': 'yuv420p', 'crf': 19, 'save_metadata': False, 'trim_to_audio': True, 'pingpong': False, 'save_output': False, 'videopreview': {'hidden': False, 'paused': False, 'params': {}}}
    wf.nodes['1007'].widgets = {}
    wf.nodes['1007'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1007'].native_input_names = ['images', 'audio', 'meta_batch', 'vae']
    wf.nodes['1007'].native_output_names = ['Filenames']
    wf.nodes['1007'].native_input_types = ['IMAGE', 'AUDIO', 'VHS_BatchManager', 'VAE']
    wf.nodes['1007'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['1007'].native_input_optional = [False, True, True, True]
    wf.nodes['1008'].inputs = {}
    wf.nodes['1008'].widgets = {}
    wf.nodes['1008'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1008'].native_input_names = ['samples', 'vae']
    wf.nodes['1008'].native_output_names = ['IMAGE']
    wf.nodes['1008'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['1008'].native_output_types = ['IMAGE']
    wf.nodes['1008'].native_input_optional = [False, False]
    wf.nodes['1009'].inputs = {}
    wf.nodes['1009'].widgets = {}
    wf.nodes['1009'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1009'].native_input_names = ['samples', 'vae']
    wf.nodes['1009'].native_output_names = ['AUDIO']
    wf.nodes['1009'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['1009'].native_output_types = ['AUDIO']
    wf.nodes['1009'].native_input_optional = [False, False]
    wf.nodes['101'].inputs = {'value': 5}
    wf.nodes['101'].widgets = {}
    wf.nodes['101'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['101'].native_input_names = []
    wf.nodes['101'].native_output_names = ['FLOAT']
    wf.nodes['101'].native_input_types = []
    wf.nodes['101'].native_output_types = ['FLOAT']
    wf.nodes['101'].native_input_optional = []
    wf.nodes['1010'].inputs = {'frame_rate': 24, 'loop_count': 0, 'filename_prefix': 'h3_preview/generated_starter', 'format': 'video/h264-mp4', 'pix_fmt': 'yuv420p', 'crf': 19, 'save_metadata': False, 'trim_to_audio': True, 'pingpong': False, 'save_output': False, 'videopreview': {'hidden': False, 'paused': False, 'params': {}}}
    wf.nodes['1010'].widgets = {}
    wf.nodes['1010'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1010'].native_input_names = ['images', 'audio', 'meta_batch', 'vae']
    wf.nodes['1010'].native_output_names = ['Filenames']
    wf.nodes['1010'].native_input_types = ['IMAGE', 'AUDIO', 'VHS_BatchManager', 'VAE']
    wf.nodes['1010'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['1010'].native_input_optional = [False, True, True, True]
    wf.nodes['102'].inputs = {}
    wf.nodes['102'].widgets = {'widget_0': 'max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17'}
    wf.nodes['102'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['102'].native_input_names = ['values.a', 'values.b']
    wf.nodes['102'].native_output_names = ['FLOAT', 'INT', 'BOOL']
    wf.nodes['102'].native_input_types = ['FLOAT,INT,BOOLEAN', 'FLOAT,INT,BOOLEAN']
    wf.nodes['102'].native_output_types = ['FLOAT', 'INT', 'BOOLEAN']
    wf.nodes['102'].native_input_optional = [False, True]
    wf.nodes['1020'].inputs = {'image': '', 'unused_widget_1': 'image'}
    wf.nodes['1020'].widgets = {}
    wf.nodes['1020'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1020'].native_input_names = []
    wf.nodes['1020'].native_output_names = ['IMAGE', 'MASK']
    wf.nodes['1020'].native_input_types = []
    wf.nodes['1020'].native_output_types = ['IMAGE', 'MASK']
    wf.nodes['1020'].native_input_optional = []
    wf.nodes['1021'].inputs = {'image': '', 'unused_widget_1': 'image'}
    wf.nodes['1021'].widgets = {}
    wf.nodes['1021'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1021'].native_input_names = []
    wf.nodes['1021'].native_output_names = ['IMAGE', 'MASK']
    wf.nodes['1021'].native_input_types = []
    wf.nodes['1021'].native_output_types = ['IMAGE', 'MASK']
    wf.nodes['1021'].native_input_optional = []
    wf.nodes['1022'].inputs = {}
    wf.nodes['1022'].widgets = {'widget_0': '{"count":1,"positions":[1]}', 'widget_1': '1-based', 'widget_2': 'disabled'}
    wf.nodes['1022'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1022'].native_input_names = ['conditioning', 'vae', 'latent', 'keyframe_image_1']
    wf.nodes['1022'].native_output_names = ['conditioning']
    wf.nodes['1022'].native_input_types = ['CONDITIONING', 'VAE', 'LATENT', 'IMAGE']
    wf.nodes['1022'].native_output_types = ['CONDITIONING']
    wf.nodes['1022'].native_input_optional = [False, False, False, False]
    wf.nodes['1024'].inputs = {}
    wf.nodes['1024'].widgets = {'widget_0': '16:9 (Widescreen)', 'widget_1': 0.5, 'widget_2': 32}
    wf.nodes['1024'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1024'].native_input_names = []
    wf.nodes['1024'].native_output_names = ['width', 'height']
    wf.nodes['1024'].native_input_types = []
    wf.nodes['1024'].native_output_types = ['INT', 'INT']
    wf.nodes['1024'].native_input_optional = []
    wf.nodes['1027'].inputs = {'audio': '', 'unused_widget_1': None, 'unused_widget_2': None}
    wf.nodes['1027'].widgets = {}
    wf.nodes['1027'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1027'].native_input_names = []
    wf.nodes['1027'].native_output_names = ['AUDIO']
    wf.nodes['1027'].native_input_types = []
    wf.nodes['1027'].native_output_types = ['AUDIO']
    wf.nodes['1027'].native_input_optional = []
    wf.nodes['1028'].inputs = {'audio': '', 'unused_widget_1': None, 'unused_widget_2': None}
    wf.nodes['1028'].widgets = {}
    wf.nodes['1028'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1028'].native_input_names = []
    wf.nodes['1028'].native_output_names = ['AUDIO']
    wf.nodes['1028'].native_input_types = []
    wf.nodes['1028'].native_output_types = ['AUDIO']
    wf.nodes['1028'].native_input_optional = []
    wf.nodes['1029'].inputs = {}
    wf.nodes['1029'].widgets = {}
    wf.nodes['1029'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1029'].native_input_names = [None]
    wf.nodes['1029'].native_output_names = [None]
    wf.nodes['1029'].native_input_types = ['AUDIO']
    wf.nodes['1029'].native_output_types = ['AUDIO']
    wf.nodes['1029'].native_input_optional = [False]
    wf.nodes['103'].inputs = {}
    wf.nodes['103'].widgets = {'widget_0': 39, 'widget_1': 8, 'widget_2': 24, 'widget_3': 'disabled'}
    wf.nodes['103'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['103'].native_input_names = ['latent', 'vae', 'audio_vae', 'start_mode', 'source_frames', 'source_audio', 'live_starter_latent', 'context_length', 'audio_feather_ticks']
    wf.nodes['103'].native_output_names = ['latent', 'trim_frames']
    wf.nodes['103'].native_input_types = ['LATENT', 'VAE', 'VAE', 'STRING', 'IMAGE', 'AUDIO', 'LATENT', 'INT', 'INT']
    wf.nodes['103'].native_output_types = ['LATENT', 'INT']
    wf.nodes['103'].native_input_optional = [False, False, False, False, True, True, True, False, False]
    wf.nodes['1030'].inputs = {}
    wf.nodes['1030'].widgets = {}
    wf.nodes['1030'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1030'].native_input_names = [None]
    wf.nodes['1030'].native_output_names = [None]
    wf.nodes['1030'].native_input_types = ['AUDIO']
    wf.nodes['1030'].native_output_types = ['AUDIO']
    wf.nodes['1030'].native_input_optional = [False]
    wf.nodes['1031'].inputs = {'source_fps': 24}
    wf.nodes['1031'].widgets = {}
    wf.nodes['1031'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1031'].native_input_names = ['source_frames', 'source_fps']
    wf.nodes['1031'].native_output_names = ['h3_length', 'source_frames_24fps']
    wf.nodes['1031'].native_input_types = ['IMAGE', 'FLOAT']
    wf.nodes['1031'].native_output_types = ['INT', 'INT']
    wf.nodes['1031'].native_input_optional = [False, False]
    wf.nodes['1032'].inputs = {}
    wf.nodes['1032'].widgets = {'widget_0': 'Regenerate the complete soundtrack for the supplied source video. The entire visual stream is protected and authoritative: do not change, reinterpret, restart, or replace the video. Generate synchronized audio for the full clip from beginning to end, including dialogue/voice when visually implied, foley, impacts, movement sounds, room tone, ambience, and other scene-appropriate sound. Match visible timing precisely and maintain continuous acoustic perspective across the whole source clip.', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['1032'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1032'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['1032'].native_output_names = ['positive', 'LATENT']
    wf.nodes['1032'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['1032'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['1032'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['1033'].inputs = {'source_fps': 24, 'crop': 'disabled'}
    wf.nodes['1033'].widgets = {}
    wf.nodes['1033'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1033'].native_input_names = ['latent', 'vae', 'source_frames', 'source_fps', 'crop']
    wf.nodes['1033'].native_output_names = ['latent']
    wf.nodes['1033'].native_input_types = ['LATENT', 'VAE', 'IMAGE', 'FLOAT', 'COMBO']
    wf.nodes['1033'].native_output_types = ['LATENT']
    wf.nodes['1033'].native_input_optional = [False, False, False, False, False]
    wf.nodes['1034'].inputs = {'noise_seed': 918273645, 'control_after_generate': 'fixed'}
    wf.nodes['1034'].widgets = {}
    wf.nodes['1034'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1034'].native_input_names = []
    wf.nodes['1034'].native_output_names = ['NOISE']
    wf.nodes['1034'].native_input_types = []
    wf.nodes['1034'].native_output_types = ['NOISE']
    wf.nodes['1034'].native_input_optional = []
    wf.nodes['1035'].inputs = {}
    wf.nodes['1035'].widgets = {}
    wf.nodes['1035'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1035'].native_input_names = ['model', 'conditioning']
    wf.nodes['1035'].native_output_names = ['GUIDER']
    wf.nodes['1035'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['1035'].native_output_types = ['GUIDER']
    wf.nodes['1035'].native_input_optional = [False, False]
    wf.nodes['1036'].inputs = {}
    wf.nodes['1036'].widgets = {}
    wf.nodes['1036'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1036'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['1036'].native_output_names = ['output', 'denoised_output']
    wf.nodes['1036'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['1036'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['1036'].native_input_optional = [False, False, False, False, False]
    wf.nodes['1037'].inputs = {'source_fps': 24}
    wf.nodes['1037'].widgets = {}
    wf.nodes['1037'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1037'].native_input_names = ['audio_vae', 'mode', 'source_frames', 'video_info', 'source_fps', 'regenerated_latent']
    wf.nodes['1037'].native_output_names = ['source_audio']
    wf.nodes['1037'].native_input_types = ['VAE', 'STRING', 'IMAGE', 'VHS_VIDEOINFO', 'FLOAT', 'LATENT']
    wf.nodes['1037'].native_output_types = ['AUDIO']
    wf.nodes['1037'].native_input_optional = [False, False, False, False, False, True]
    wf.nodes['1038'].inputs = {}
    wf.nodes['1038'].widgets = {'widget_0': 'Existing Video'}
    wf.nodes['1038'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1038'].native_input_names = []
    wf.nodes['1038'].native_output_names = ['start_mode']
    wf.nodes['1038'].native_input_types = []
    wf.nodes['1038'].native_output_types = ['STRING']
    wf.nodes['1038'].native_input_optional = []
    wf.nodes['1039'].inputs = {'value': 1}
    wf.nodes['1039'].widgets = {'widget_1': 'fixed'}
    wf.nodes['1039'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1039'].native_input_names = []
    wf.nodes['1039'].native_output_names = ['INT']
    wf.nodes['1039'].native_input_types = []
    wf.nodes['1039'].native_output_types = ['INT']
    wf.nodes['1039'].native_input_optional = []
    wf.nodes['1040'].inputs = {'value': 8}
    wf.nodes['1040'].widgets = {'widget_1': 'fixed'}
    wf.nodes['1040'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1040'].native_input_names = []
    wf.nodes['1040'].native_output_names = ['INT']
    wf.nodes['1040'].native_input_types = []
    wf.nodes['1040'].native_output_types = ['INT']
    wf.nodes['1040'].native_input_optional = []
    wf.nodes['1041'].inputs = {}
    wf.nodes['1041'].widgets = {'widget_0': 'Keep source audio'}
    wf.nodes['1041'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1041'].native_input_names = []
    wf.nodes['1041'].native_output_names = ['source_audio_mode']
    wf.nodes['1041'].native_input_types = []
    wf.nodes['1041'].native_output_types = ['STRING']
    wf.nodes['1041'].native_input_optional = []
    wf.nodes['1042'].inputs = {}
    wf.nodes['1042'].widgets = {'widget_0': 6}
    wf.nodes['1042'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1042'].native_input_names = ['active_extensions', 'preview_1', 'preview_2', 'preview_3', 'preview_4', 'preview_5', 'preview_6']
    wf.nodes['1042'].native_output_names = ['preview_gate']
    wf.nodes['1042'].native_input_types = ['INT', 'VHS_FILENAMES', 'VHS_FILENAMES', 'VHS_FILENAMES', 'VHS_FILENAMES', 'VHS_FILENAMES', 'VHS_FILENAMES']
    wf.nodes['1042'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['1042'].native_input_optional = [False, True, True, True, True, True, True]
    wf.nodes['1043'].inputs = {}
    wf.nodes['1043'].widgets = {}
    wf.nodes['1043'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['1043'].native_input_names = ['filenames']
    wf.nodes['1043'].native_output_names = []
    wf.nodes['1043'].native_input_types = ['VHS_FILENAMES']
    wf.nodes['1043'].native_output_types = []
    wf.nodes['1043'].native_input_optional = [True]
    wf.nodes['110'].inputs = {}
    wf.nodes['110'].widgets = {'widget_0': 'Continue directly from the final moment of the selected start clip with no cut, reset, or re-establishment. The incoming protected audiovisual prefix is authoritative for pose, motion, camera trajectory, lighting, environment, object state, voice, ambience, and timing. Connected reference images are identity/appearance references only; never pull the subject back toward a reference-image pose, expression, framing, or lighting.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['110'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['110'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['110'].native_output_names = ['positive', 'LATENT']
    wf.nodes['110'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['110'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['110'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['120'].inputs = {'noise_seed': 123456789, 'control_after_generate': 'fixed'}
    wf.nodes['120'].widgets = {}
    wf.nodes['120'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['120'].native_input_names = []
    wf.nodes['120'].native_output_names = ['NOISE']
    wf.nodes['120'].native_input_types = []
    wf.nodes['120'].native_output_types = ['NOISE']
    wf.nodes['120'].native_input_optional = []
    wf.nodes['121'].inputs = {}
    wf.nodes['121'].widgets = {}
    wf.nodes['121'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['121'].native_input_names = ['model', 'conditioning']
    wf.nodes['121'].native_output_names = ['GUIDER']
    wf.nodes['121'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['121'].native_output_types = ['GUIDER']
    wf.nodes['121'].native_input_optional = [False, False]
    wf.nodes['124'].inputs = {}
    wf.nodes['124'].widgets = {}
    wf.nodes['124'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['124'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['124'].native_output_names = ['output', 'denoised_output']
    wf.nodes['124'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['124'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['124'].native_input_optional = [False, False, False, False, False]
    wf.nodes['2'].inputs = {'clip_name': 'qwen3vl_32b_minimax_h3_int8_convrot.safetensors', 'type': 'minimax', 'device': 'default'}
    wf.nodes['2'].widgets = {}
    wf.nodes['2'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['2'].native_input_names = []
    wf.nodes['2'].native_output_names = ['CLIP']
    wf.nodes['2'].native_input_types = []
    wf.nodes['2'].native_output_types = ['CLIP']
    wf.nodes['2'].native_input_optional = []
    wf.nodes['200'].inputs = {}
    wf.nodes['200'].widgets = {'widget_0': 'Continue the existing scene from the previous generated H3 clip with no cut, reset, or re-establishment. The incoming protected H3 audiovisual latent prefix is authoritative for current pose, motion, camera trajectory, facial state, lighting, environment, object state, voice, ambience, and timing. Connected reference images are optional; use them only to preserve stable subject identity and appearance beneath that incoming state.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['200'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['200'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['200'].native_output_names = ['positive', 'LATENT']
    wf.nodes['200'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['200'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['200'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['201'].inputs = {}
    wf.nodes['201'].widgets = {'widget_0': 39, 'widget_1': 8}
    wf.nodes['201'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['201'].native_input_names = ['latent', 'source_latent', 'context_length', 'audio_feather_ticks']
    wf.nodes['201'].native_output_names = ['latent', 'trim_frames']
    wf.nodes['201'].native_input_types = ['LATENT', 'LATENT', 'INT', 'INT']
    wf.nodes['201'].native_output_types = ['LATENT', 'INT']
    wf.nodes['201'].native_input_optional = [False, False, False, False]
    wf.nodes['210'].inputs = {'noise_seed': 123469134, 'control_after_generate': 'fixed'}
    wf.nodes['210'].widgets = {}
    wf.nodes['210'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['210'].native_input_names = []
    wf.nodes['210'].native_output_names = ['NOISE']
    wf.nodes['210'].native_input_types = []
    wf.nodes['210'].native_output_types = ['NOISE']
    wf.nodes['210'].native_input_optional = []
    wf.nodes['211'].inputs = {}
    wf.nodes['211'].widgets = {}
    wf.nodes['211'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['211'].native_input_names = ['model', 'conditioning']
    wf.nodes['211'].native_output_names = ['GUIDER']
    wf.nodes['211'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['211'].native_output_types = ['GUIDER']
    wf.nodes['211'].native_input_optional = [False, False]
    wf.nodes['214'].inputs = {}
    wf.nodes['214'].widgets = {}
    wf.nodes['214'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['214'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['214'].native_output_names = ['output', 'denoised_output']
    wf.nodes['214'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['214'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['214'].native_input_optional = [False, False, False, False, False]
    wf.nodes['3'].inputs = {'vae_name': 'minimax_h3_video_vae_int8_convrot.safetensors'}
    wf.nodes['3'].widgets = {}
    wf.nodes['3'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['3'].native_input_names = []
    wf.nodes['3'].native_output_names = ['VAE']
    wf.nodes['3'].native_input_types = []
    wf.nodes['3'].native_output_types = ['VAE']
    wf.nodes['3'].native_input_optional = []
    wf.nodes['300'].inputs = {}
    wf.nodes['300'].widgets = {'widget_0': 'Continue the existing scene from the previous generated H3 clip with no cut, reset, or re-establishment. The incoming protected H3 audiovisual latent prefix is authoritative for current pose, motion, camera trajectory, facial state, lighting, environment, object state, voice, ambience, and timing. Connected reference images are optional; use them only to preserve stable subject identity and appearance beneath that incoming state.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['300'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['300'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['300'].native_output_names = ['positive', 'LATENT']
    wf.nodes['300'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['300'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['300'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['301'].inputs = {}
    wf.nodes['301'].widgets = {'widget_0': 39, 'widget_1': 8}
    wf.nodes['301'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['301'].native_input_names = ['latent', 'source_latent', 'context_length', 'audio_feather_ticks']
    wf.nodes['301'].native_output_names = ['latent', 'trim_frames']
    wf.nodes['301'].native_input_types = ['LATENT', 'LATENT', 'INT', 'INT']
    wf.nodes['301'].native_output_types = ['LATENT', 'INT']
    wf.nodes['301'].native_input_optional = [False, False, False, False]
    wf.nodes['310'].inputs = {'noise_seed': 123481479, 'control_after_generate': 'fixed'}
    wf.nodes['310'].widgets = {}
    wf.nodes['310'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['310'].native_input_names = []
    wf.nodes['310'].native_output_names = ['NOISE']
    wf.nodes['310'].native_input_types = []
    wf.nodes['310'].native_output_types = ['NOISE']
    wf.nodes['310'].native_input_optional = []
    wf.nodes['311'].inputs = {}
    wf.nodes['311'].widgets = {}
    wf.nodes['311'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['311'].native_input_names = ['model', 'conditioning']
    wf.nodes['311'].native_output_names = ['GUIDER']
    wf.nodes['311'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['311'].native_output_types = ['GUIDER']
    wf.nodes['311'].native_input_optional = [False, False]
    wf.nodes['314'].inputs = {}
    wf.nodes['314'].widgets = {}
    wf.nodes['314'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['314'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['314'].native_output_names = ['output', 'denoised_output']
    wf.nodes['314'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['314'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['314'].native_input_optional = [False, False, False, False, False]
    wf.nodes['4'].inputs = {'vae_name': 'minimax_h3_audio_vae_fp32.safetensors'}
    wf.nodes['4'].widgets = {}
    wf.nodes['4'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['4'].native_input_names = []
    wf.nodes['4'].native_output_names = ['VAE']
    wf.nodes['4'].native_input_types = []
    wf.nodes['4'].native_output_types = ['VAE']
    wf.nodes['4'].native_input_optional = []
    wf.nodes['400'].inputs = {}
    wf.nodes['400'].widgets = {'widget_0': 'Continue the existing scene from the previous generated H3 clip with no cut, reset, or re-establishment. The incoming protected H3 audiovisual latent prefix is authoritative for current pose, motion, camera trajectory, facial state, lighting, environment, object state, voice, ambience, and timing. Connected reference images are optional; use them only to preserve stable subject identity and appearance beneath that incoming state.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['400'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['400'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['400'].native_output_names = ['positive', 'LATENT']
    wf.nodes['400'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['400'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['400'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['401'].inputs = {}
    wf.nodes['401'].widgets = {'widget_0': 39, 'widget_1': 8}
    wf.nodes['401'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['401'].native_input_names = ['latent', 'source_latent', 'context_length', 'audio_feather_ticks']
    wf.nodes['401'].native_output_names = ['latent', 'trim_frames']
    wf.nodes['401'].native_input_types = ['LATENT', 'LATENT', 'INT', 'INT']
    wf.nodes['401'].native_output_types = ['LATENT', 'INT']
    wf.nodes['401'].native_input_optional = [False, False, False, False]
    wf.nodes['410'].inputs = {'noise_seed': 123493824, 'control_after_generate': 'fixed'}
    wf.nodes['410'].widgets = {}
    wf.nodes['410'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['410'].native_input_names = []
    wf.nodes['410'].native_output_names = ['NOISE']
    wf.nodes['410'].native_input_types = []
    wf.nodes['410'].native_output_types = ['NOISE']
    wf.nodes['410'].native_input_optional = []
    wf.nodes['411'].inputs = {}
    wf.nodes['411'].widgets = {}
    wf.nodes['411'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['411'].native_input_names = ['model', 'conditioning']
    wf.nodes['411'].native_output_names = ['GUIDER']
    wf.nodes['411'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['411'].native_output_types = ['GUIDER']
    wf.nodes['411'].native_input_optional = [False, False]
    wf.nodes['414'].inputs = {}
    wf.nodes['414'].widgets = {}
    wf.nodes['414'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['414'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['414'].native_output_names = ['output', 'denoised_output']
    wf.nodes['414'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['414'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['414'].native_input_optional = [False, False, False, False, False]
    wf.nodes['5'].inputs = {}
    wf.nodes['5'].widgets = {'widget_0': 12, 'widget_1': 3}
    wf.nodes['5'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['5'].native_input_names = ['model']
    wf.nodes['5'].native_output_names = ['MODEL']
    wf.nodes['5'].native_input_types = ['MODEL']
    wf.nodes['5'].native_output_types = ['MODEL']
    wf.nodes['5'].native_input_optional = [False]
    wf.nodes['500'].inputs = {}
    wf.nodes['500'].widgets = {'widget_0': 'Continue the existing scene from the previous generated H3 clip with no cut, reset, or re-establishment. The incoming protected H3 audiovisual latent prefix is authoritative for current pose, motion, camera trajectory, facial state, lighting, environment, object state, voice, ambience, and timing. Connected reference images are optional; use them only to preserve stable subject identity and appearance beneath that incoming state.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['500'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['500'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['500'].native_output_names = ['positive', 'LATENT']
    wf.nodes['500'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['500'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['500'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['501'].inputs = {}
    wf.nodes['501'].widgets = {'widget_0': 39, 'widget_1': 8}
    wf.nodes['501'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['501'].native_input_names = ['latent', 'source_latent', 'context_length', 'audio_feather_ticks']
    wf.nodes['501'].native_output_names = ['latent', 'trim_frames']
    wf.nodes['501'].native_input_types = ['LATENT', 'LATENT', 'INT', 'INT']
    wf.nodes['501'].native_output_types = ['LATENT', 'INT']
    wf.nodes['501'].native_input_optional = [False, False, False, False]
    wf.nodes['510'].inputs = {'noise_seed': 123506169, 'control_after_generate': 'fixed'}
    wf.nodes['510'].widgets = {}
    wf.nodes['510'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['510'].native_input_names = []
    wf.nodes['510'].native_output_names = ['NOISE']
    wf.nodes['510'].native_input_types = []
    wf.nodes['510'].native_output_types = ['NOISE']
    wf.nodes['510'].native_input_optional = []
    wf.nodes['511'].inputs = {}
    wf.nodes['511'].widgets = {}
    wf.nodes['511'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['511'].native_input_names = ['model', 'conditioning']
    wf.nodes['511'].native_output_names = ['GUIDER']
    wf.nodes['511'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['511'].native_output_types = ['GUIDER']
    wf.nodes['511'].native_input_optional = [False, False]
    wf.nodes['514'].inputs = {}
    wf.nodes['514'].widgets = {}
    wf.nodes['514'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['514'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['514'].native_output_names = ['output', 'denoised_output']
    wf.nodes['514'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['514'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['514'].native_input_optional = [False, False, False, False, False]
    wf.nodes['600'].inputs = {}
    wf.nodes['600'].widgets = {'widget_0': 'Continue the existing scene from the previous generated H3 clip with no cut, reset, or re-establishment. The incoming protected H3 audiovisual latent prefix is authoritative for current pose, motion, camera trajectory, facial state, lighting, environment, object state, voice, ambience, and timing. Connected reference images are optional; use them only to preserve stable subject identity and appearance beneath that incoming state.\n\n[Shot 1] Continue the exact motion and sound already in progress, then develop the next action naturally. [DESCRIBE WHAT HAPPENS NEXT; DO NOT RESTART FROM REST.]', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['600'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['600'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['600'].native_output_names = ['positive', 'LATENT']
    wf.nodes['600'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['600'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['600'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['601'].inputs = {}
    wf.nodes['601'].widgets = {'widget_0': 39, 'widget_1': 8}
    wf.nodes['601'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['601'].native_input_names = ['latent', 'source_latent', 'context_length', 'audio_feather_ticks']
    wf.nodes['601'].native_output_names = ['latent', 'trim_frames']
    wf.nodes['601'].native_input_types = ['LATENT', 'LATENT', 'INT', 'INT']
    wf.nodes['601'].native_output_types = ['LATENT', 'INT']
    wf.nodes['601'].native_input_optional = [False, False, False, False]
    wf.nodes['610'].inputs = {'noise_seed': 123518514, 'control_after_generate': 'fixed'}
    wf.nodes['610'].widgets = {}
    wf.nodes['610'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['610'].native_input_names = []
    wf.nodes['610'].native_output_names = ['NOISE']
    wf.nodes['610'].native_input_types = []
    wf.nodes['610'].native_output_types = ['NOISE']
    wf.nodes['610'].native_input_optional = []
    wf.nodes['611'].inputs = {}
    wf.nodes['611'].widgets = {}
    wf.nodes['611'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['611'].native_input_names = ['model', 'conditioning']
    wf.nodes['611'].native_output_names = ['GUIDER']
    wf.nodes['611'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['611'].native_output_types = ['GUIDER']
    wf.nodes['611'].native_input_optional = [False, False]
    wf.nodes['614'].inputs = {}
    wf.nodes['614'].widgets = {}
    wf.nodes['614'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['614'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['614'].native_output_names = ['output', 'denoised_output']
    wf.nodes['614'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['614'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['614'].native_input_optional = [False, False, False, False, False]
    wf.nodes['935'].inputs = {'lora_name': 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors', 'strength_model': 0.95}
    wf.nodes['935'].widgets = {}
    wf.nodes['935'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['935'].native_input_names = ['model']
    wf.nodes['935'].native_output_names = ['MODEL']
    wf.nodes['935'].native_input_types = ['MODEL']
    wf.nodes['935'].native_output_types = ['MODEL']
    wf.nodes['935'].native_input_optional = [False]
    wf.nodes['936'].inputs = {'value': 8}
    wf.nodes['936'].widgets = {'widget_1': 'fixed'}
    wf.nodes['936'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['936'].native_input_names = []
    wf.nodes['936'].native_output_names = ['INT']
    wf.nodes['936'].native_input_types = []
    wf.nodes['936'].native_output_types = ['INT']
    wf.nodes['936'].native_input_optional = []
    wf.nodes['937'].inputs = {'sampler_name': 'res_multistep'}
    wf.nodes['937'].widgets = {}
    wf.nodes['937'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['937'].native_input_names = []
    wf.nodes['937'].native_output_names = ['SAMPLER']
    wf.nodes['937'].native_input_types = []
    wf.nodes['937'].native_output_types = ['SAMPLER']
    wf.nodes['937'].native_input_optional = []
    wf.nodes['939'].inputs = {'value': 39}
    wf.nodes['939'].widgets = {'widget_1': 'fixed'}
    wf.nodes['939'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['939'].native_input_names = []
    wf.nodes['939'].native_output_names = ['INT']
    wf.nodes['939'].native_input_types = []
    wf.nodes['939'].native_output_types = ['INT']
    wf.nodes['939'].native_input_optional = []
    wf.nodes['940'].inputs = {'value': 39}
    wf.nodes['940'].widgets = {'widget_1': 'fixed'}
    wf.nodes['940'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['940'].native_input_names = []
    wf.nodes['940'].native_output_names = ['INT']
    wf.nodes['940'].native_input_types = []
    wf.nodes['940'].native_output_types = ['INT']
    wf.nodes['940'].native_input_optional = []
    wf.nodes['946'].inputs = {}
    wf.nodes['946'].widgets = {'widget_0': 6, 'widget_1': 39, 'widget_2': 39, 'widget_3': 24, 'widget_4': 'disabled', 'widget_5': 'video/masked_av_extension', 'widget_6': 'yuv420p', 'widget_7': 19, 'widget_8': False, 'widget_9': True, 'widget_10': True}
    wf.nodes['946'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['946'].native_input_names = ['video_vae', 'audio_vae', 'start_mode', 'source_frames', 'source_audio', 'starter_latent', 'preview_gate', 'extension_1', 'extension_2', 'extension_3', 'extension_4', 'extension_5', 'extension_6', 'active_extensions', 'context_frames', 'video_overlap_frames']
    wf.nodes['946'].native_output_names = ['Filenames']
    wf.nodes['946'].native_input_types = ['VAE', 'VAE', 'STRING', 'IMAGE', 'AUDIO', 'LATENT', 'VHS_FILENAMES', 'LATENT', 'LATENT', 'LATENT', 'LATENT', 'LATENT', 'LATENT', 'INT', 'INT', 'INT']
    wf.nodes['946'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['946'].native_input_optional = [False, False, False, True, True, True, True, True, True, True, True, True, True, False, False, False]
    wf.nodes['970'].inputs = {'image': '', 'unused_widget_1': 'image'}
    wf.nodes['970'].widgets = {}
    wf.nodes['970'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['970'].native_input_names = []
    wf.nodes['970'].native_output_names = ['IMAGE', 'MASK']
    wf.nodes['970'].native_input_types = []
    wf.nodes['970'].native_output_types = ['IMAGE', 'MASK']
    wf.nodes['970'].native_input_optional = []
    wf.nodes['972'].inputs = {}
    wf.nodes['972'].widgets = {'widget_0': 960, 'widget_1': 544, 'widget_2': 0, 'widget_3': 0}
    wf.nodes['972'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['972'].native_input_names = ['start_mode', 'generated_width', 'generated_height', 'source_width', 'source_height']
    wf.nodes['972'].native_output_names = ['width', 'height']
    wf.nodes['972'].native_input_types = ['STRING', 'INT', 'INT', 'INT', 'INT']
    wf.nodes['972'].native_output_types = ['INT', 'INT']
    wf.nodes['972'].native_input_optional = [False, False, False, True, True]
    wf.nodes['973'].inputs = {}
    wf.nodes['973'].widgets = {'widget_0': 'Create the opening clip for a new continuous video. Establish coherent subject identity, camera, lighting, environment, motion, voice, ambience, and audiovisual timing so later masked extensions can continue seamlessly. If an H3 keyframe is enabled at frame 1, treat it as the exact opening image and animate naturally forward. Connected reference images are identity/appearance references only and should not force their pose, framing, expression, or lighting onto the shot.', 'widget_1': 960, 'widget_2': 544, 'widget_3': 362, 'widget_4': 'match'}
    wf.nodes['973'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['973'].native_input_names = ['clip', 'vae', 'audio_vae', 'ref_images.ref_image_0', 'ref_images.ref_image_1', 'ref_images.ref_image_2', 'ref_videos.ref_video_0', 'ref_video_audios.ref_video_audio_0', 'ref_audios.ref_audio_0', 'width', 'height', 'length', 'ref_audios.ref_audio_1']
    wf.nodes['973'].native_output_names = ['positive', 'LATENT']
    wf.nodes['973'].native_input_types = ['CLIP', 'VAE', 'VAE', 'IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'AUDIO', 'AUDIO', 'INT', 'INT', 'INT', 'AUDIO']
    wf.nodes['973'].native_output_types = ['CONDITIONING', 'LATENT']
    wf.nodes['973'].native_input_optional = [False, False, False, True, True, True, True, True, True, False, False, False, True]
    wf.nodes['974'].inputs = {'noise_seed': 123432109, 'control_after_generate': 'fixed'}
    wf.nodes['974'].widgets = {}
    wf.nodes['974'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['974'].native_input_names = []
    wf.nodes['974'].native_output_names = ['NOISE']
    wf.nodes['974'].native_input_types = []
    wf.nodes['974'].native_output_types = ['NOISE']
    wf.nodes['974'].native_input_optional = []
    wf.nodes['975'].inputs = {}
    wf.nodes['975'].widgets = {}
    wf.nodes['975'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['975'].native_input_names = ['model', 'conditioning']
    wf.nodes['975'].native_output_names = ['GUIDER']
    wf.nodes['975'].native_input_types = ['MODEL', 'CONDITIONING']
    wf.nodes['975'].native_output_types = ['GUIDER']
    wf.nodes['975'].native_input_optional = [False, False]
    wf.nodes['976'].inputs = {'scheduler': 'simple', 'denoise': 1}
    wf.nodes['976'].widgets = {}
    wf.nodes['976'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['976'].native_input_names = ['model', 'steps']
    wf.nodes['976'].native_output_names = ['SIGMAS']
    wf.nodes['976'].native_input_types = ['MODEL', 'INT']
    wf.nodes['976'].native_output_types = ['SIGMAS']
    wf.nodes['976'].native_input_optional = [False, False]
    wf.nodes['977'].inputs = {}
    wf.nodes['977'].widgets = {}
    wf.nodes['977'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['977'].native_input_names = ['noise', 'guider', 'sampler', 'sigmas', 'latent_image']
    wf.nodes['977'].native_output_names = ['output', 'denoised_output']
    wf.nodes['977'].native_input_types = ['NOISE', 'GUIDER', 'SAMPLER', 'SIGMAS', 'LATENT']
    wf.nodes['977'].native_output_types = ['LATENT', 'LATENT']
    wf.nodes['977'].native_input_optional = [False, False, False, False, False]
    wf.nodes['980'].inputs = {}
    wf.nodes['980'].widgets = {'widget_0': 'Existing Video', 'widget_1': 1, 'widget_2': 8, 'widget_3': 'All Active', 'widget_4': 'Keep source audio'}
    wf.nodes['980'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['980'].native_input_names = []
    wf.nodes['980'].native_output_names = ['start_mode', 'active_extensions', 'audio_feather_ticks', 'preview_mode', 'source_audio_mode']
    wf.nodes['980'].native_input_types = []
    wf.nodes['980'].native_output_types = ['STRING', 'INT', 'INT', 'STRING', 'STRING']
    wf.nodes['980'].native_input_optional = []
    wf.nodes['988'].inputs = {}
    wf.nodes['988'].widgets = {'widget_0': 'comfy kitchen attention'}
    wf.nodes['988'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['988'].native_input_names = ['model']
    wf.nodes['988'].native_output_names = ['MODEL']
    wf.nodes['988'].native_input_types = ['MODEL']
    wf.nodes['988'].native_output_types = ['MODEL']
    wf.nodes['988'].native_input_optional = [False]
    wf.nodes['99'].inputs = {'video': '', 'force_rate': 24, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'start_time': 0, 'format': 'AnimateDiff', 'videopreview': {'hidden': False, 'paused': False, 'params': {}, 'muted': False}}
    wf.nodes['99'].widgets = {}
    wf.nodes['99'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['99'].native_input_names = ['meta_batch', 'vae']
    wf.nodes['99'].native_output_names = ['IMAGE', 'mask', 'audio', 'video_info']
    wf.nodes['99'].native_input_types = ['VHS_BatchManager', 'VAE']
    wf.nodes['99'].native_output_types = ['IMAGE', 'MASK', 'AUDIO', 'VHS_VIDEOINFO']
    wf.nodes['99'].native_input_optional = [True, True]
    wf.nodes['990'].inputs = {}
    wf.nodes['990'].widgets = {}
    wf.nodes['990'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['990'].native_input_names = ['samples', 'vae']
    wf.nodes['990'].native_output_names = ['IMAGE']
    wf.nodes['990'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['990'].native_output_types = ['IMAGE']
    wf.nodes['990'].native_input_optional = [False, False]
    wf.nodes['991'].inputs = {}
    wf.nodes['991'].widgets = {}
    wf.nodes['991'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['991'].native_input_names = ['samples', 'vae']
    wf.nodes['991'].native_output_names = ['AUDIO']
    wf.nodes['991'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['991'].native_output_types = ['AUDIO']
    wf.nodes['991'].native_input_optional = [False, False]
    wf.nodes['992'].inputs = {'frame_rate': 24, 'loop_count': 0, 'filename_prefix': 'h3_preview/extension_01', 'format': 'video/h264-mp4', 'pix_fmt': 'yuv420p', 'crf': 19, 'save_metadata': False, 'trim_to_audio': True, 'pingpong': False, 'save_output': False, 'videopreview': {'hidden': False, 'paused': False, 'params': {}}}
    wf.nodes['992'].widgets = {}
    wf.nodes['992'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['992'].native_input_names = ['images', 'audio', 'meta_batch', 'vae']
    wf.nodes['992'].native_output_names = ['Filenames']
    wf.nodes['992'].native_input_types = ['IMAGE', 'AUDIO', 'VHS_BatchManager', 'VAE']
    wf.nodes['992'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['992'].native_input_optional = [False, True, True, True]
    wf.nodes['993'].inputs = {}
    wf.nodes['993'].widgets = {}
    wf.nodes['993'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['993'].native_input_names = ['samples', 'vae']
    wf.nodes['993'].native_output_names = ['IMAGE']
    wf.nodes['993'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['993'].native_output_types = ['IMAGE']
    wf.nodes['993'].native_input_optional = [False, False]
    wf.nodes['994'].inputs = {}
    wf.nodes['994'].widgets = {}
    wf.nodes['994'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['994'].native_input_names = ['samples', 'vae']
    wf.nodes['994'].native_output_names = ['AUDIO']
    wf.nodes['994'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['994'].native_output_types = ['AUDIO']
    wf.nodes['994'].native_input_optional = [False, False]
    wf.nodes['995'].inputs = {'frame_rate': 24, 'loop_count': 0, 'filename_prefix': 'h3_preview/extension_02', 'format': 'video/h264-mp4', 'pix_fmt': 'yuv420p', 'crf': 19, 'save_metadata': False, 'trim_to_audio': True, 'pingpong': False, 'save_output': False, 'videopreview': {'hidden': False, 'paused': False, 'params': {}}}
    wf.nodes['995'].widgets = {}
    wf.nodes['995'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['995'].native_input_names = ['images', 'audio', 'meta_batch', 'vae']
    wf.nodes['995'].native_output_names = ['Filenames']
    wf.nodes['995'].native_input_types = ['IMAGE', 'AUDIO', 'VHS_BatchManager', 'VAE']
    wf.nodes['995'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['995'].native_input_optional = [False, True, True, True]
    wf.nodes['996'].inputs = {}
    wf.nodes['996'].widgets = {}
    wf.nodes['996'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['996'].native_input_names = ['samples', 'vae']
    wf.nodes['996'].native_output_names = ['IMAGE']
    wf.nodes['996'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['996'].native_output_types = ['IMAGE']
    wf.nodes['996'].native_input_optional = [False, False]
    wf.nodes['997'].inputs = {}
    wf.nodes['997'].widgets = {}
    wf.nodes['997'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['997'].native_input_names = ['samples', 'vae']
    wf.nodes['997'].native_output_names = ['AUDIO']
    wf.nodes['997'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['997'].native_output_types = ['AUDIO']
    wf.nodes['997'].native_input_optional = [False, False]
    wf.nodes['998'].inputs = {'frame_rate': 24, 'loop_count': 0, 'filename_prefix': 'h3_preview/extension_03', 'format': 'video/h264-mp4', 'pix_fmt': 'yuv420p', 'crf': 19, 'save_metadata': False, 'trim_to_audio': True, 'pingpong': False, 'save_output': False, 'videopreview': {'hidden': False, 'paused': False, 'params': {}}}
    wf.nodes['998'].widgets = {}
    wf.nodes['998'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['998'].native_input_names = ['images', 'audio', 'meta_batch', 'vae']
    wf.nodes['998'].native_output_names = ['Filenames']
    wf.nodes['998'].native_input_types = ['IMAGE', 'AUDIO', 'VHS_BatchManager', 'VAE']
    wf.nodes['998'].native_output_types = ['VHS_FILENAMES']
    wf.nodes['998'].native_input_optional = [False, True, True, True]
    wf.nodes['999'].inputs = {}
    wf.nodes['999'].widgets = {}
    wf.nodes['999'].metadata = {'schema_source': {'provider': '', 'path': None, 'cache_path': None, 'server_url': None, 'package': None, 'version': None, 'hash': None, 'confidence': 0.0}, 'provenance': 'untrusted_source'}
    wf.nodes['999'].native_input_names = ['samples', 'vae']
    wf.nodes['999'].native_output_names = ['IMAGE']
    wf.nodes['999'].native_input_types = ['LATENT', 'VAE']
    wf.nodes['999'].native_output_types = ['IMAGE']
    wf.nodes['999'].native_input_optional = [False, False]
    # Preserve the four source UI nodes the ready emitter cannot model as
    # typed public wrappers: three display-only notes and PreviewAny's
    # wildcard source.  They are part of the frozen full-IR custody proof.
    wf.add_node('Note', '900', uid='900')
    wf.add_node('Note', '1025', uid='1025')
    wf.add_node('Note', '1044', uid='1044')
    wf.add_node('PreviewAny', '1026', uid='1026')
    wf.connect('102.1', '1026.source')
    wf.metadata.update({
        'h3_source_repository': 'seitanism/ComfyUI-H3-Motion-Context-MultiRef',
        'h3_source_commit': '2ed4b27e5e262a996ad2670ac6d2fd2e505cf3a3',
        'h3_source_path': 'sources/h3-2ed4b27e5e262a996ad2670ac6d2fd2e505cf3a3.json',
        'h3_source_sha256': '3cbf9bdff20e50596c8034eb4446f487e523922847fe0fb6bc11b2a5a5c7bd08',
    })
    wf.inputs.clear()
    wf.register_input('model', '1', 'unet_name', 'minimax_h3_ref2va_pruned_int8_convrot.safetensors', type=None, default=None, required=False, range=None, aliases=(), media_semantics=None, allow_missing_target=False)
    wf.inputs['model'].default = None
    wf.register_input('seed', '120', 'noise_seed', 123456789, type=None, default=None, required=False, range=None, aliases=(), media_semantics=None, allow_missing_target=False)
    wf.inputs['seed'].default = None
    public_output_0 = wf.outputs[0]
    wf.outputs.clear()
    public_output_0.output_type = 'VHS_VideoCombine'
    public_output_0.name = None
    public_output_0.artifact_kind = None
    public_output_0.mime_type = None
    public_output_0.filename_prefix = None
    public_output_0.expected_cardinality = None
    wf.outputs.append(public_output_0)
    wf.requirements.models = ['minimax_h3_audio_vae_fp32.safetensors', 'minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors', 'minimax_h3_ref2va_pruned_int8_convrot.safetensors', 'minimax_h3_video_vae_int8_convrot.safetensors', 'qwen3vl_32b_minimax_h3_int8_convrot.safetensors']
    wf.requirements.custom_nodes = []
    wf.requirements.missing_models = []
    wf.requirements.missing_nodes = ['BasicGuider', 'BasicScheduler', 'CLIPLoader', 'ComfyMathExpression', 'KSamplerSelect', 'LoadAudio', 'LoadImage', 'LoraLoaderModelOnly', 'MiniMaxH3AVExtensionController', 'MiniMaxH3AVSourceAudioModeParam', 'MiniMaxH3AVStartModeParam', 'MiniMaxH3CropTo32', 'MiniMaxH3CustomKeyframes', 'MiniMaxH3FinalizeVHSOutput', 'MiniMaxH3GeneratedAVMaskedContext', 'MiniMaxH3LastActiveVHSPreviewBarrier', 'MiniMaxH3ReferenceToVideo', 'MiniMaxH3SigmaShift', 'MiniMaxH3SourceAudioPolicy', 'MiniMaxH3SourceAudioRegenLength', 'MiniMaxH3SourceAudioRegenMask', 'MiniMaxH3StartCanvasSelector', 'MiniMaxH3StartMaskedContext', 'MiniMaxH3StreamLiveExtensionAVToVHS', 'ModelAttentionBackend', 'Note', 'PreviewAny', 'PrimitiveFloat', 'PrimitiveInt', 'RandomNoise', 'Reroute', 'ResolutionSelector', 'SamplerCustomAdvanced', 'UNETLoader', 'VAEDecode', 'VAEDecodeAudio', 'VAELoader', 'VHS_LoadVideoFFmpeg', 'VHS_VideoCombine']
    wf.requirements.unsupported = []
    wf.strict_types = False
    return wf
