# vibecomfy:generated
# pack: wanvideowrapper
# source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
# source_sha256: 04efdd145bc47962f58dbd06475874d8f960419f0c43c993014cbe33f5ae69ec
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 146
#
# DO NOT EDIT — regenerate with:
#   vibecomfy nodes generate-wrappers wanvideowrapper

"""Auto-generated public wrappers for the wanvideowrapper custom-node pack.

Each function wraps one ComfyUI node class and delegates through the
public ``vibecomfy.templates.node`` ABI.
"""

from __future__ import annotations

from typing import Any, Literal

from vibecomfy.templates import _current_workflow_or_raise, node
from vibecomfy.workflow import VibeWorkflow

class _Omitted:
    pass

_UNSET = _Omitted()

def CreateCFGScheduleFloatList(
    *args: VibeWorkflow,
    _id: str | None = None,
    cfg_scale_end: float | _Omitted = _UNSET,
    cfg_scale_start: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out'] | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``CreateCFGScheduleFloatList``.

    Display name: Create CFG Schedule Float List

    Category: WanVideoWrapper

    Helper node to generate a list of floats that can be used to schedule cfg scale for the steps, outside the set range cfg is set to 1.0

    Returns: float_list

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"CreateCFGScheduleFloatList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cfg_scale_end is not _UNSET:
        _kwargs['cfg_scale_end'] = cfg_scale_end
    if cfg_scale_start is not _UNSET:
        _kwargs['cfg_scale_start'] = cfg_scale_start
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    _kwargs.update(_extras)
    return node(wf, 'CreateCFGScheduleFloatList', _id, pass_raw=pass_raw, **_kwargs)

def CreateScheduleFloatList(
    *args: VibeWorkflow,
    _id: str | None = None,
    default_value: float | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    end_value: float | _Omitted = _UNSET,
    interpolation: Literal['linear', 'ease_in', 'ease_out'] | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    start_value: float | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``CreateScheduleFloatList``.

    Display name: Create Schedule Float List

    Category: WanVideoWrapper

    Helper node to generate a list of floats that can be used to schedule things like cfg and lora scale per step

    Returns: float_list

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"CreateScheduleFloatList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if default_value is not _UNSET:
        _kwargs['default_value'] = default_value
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if end_value is not _UNSET:
        _kwargs['end_value'] = end_value
    if interpolation is not _UNSET:
        _kwargs['interpolation'] = interpolation
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if start_value is not _UNSET:
        _kwargs['start_value'] = start_value
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    _kwargs.update(_extras)
    return node(wf, 'CreateScheduleFloatList', _id, pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadNLFModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    url: Literal['https://github.com/isarandi/nlf/releases/download/v0.3.2/nlf_l_multi_0.3.2.torchscript', 'https://github.com/isarandi/nlf/releases/download/v0.2.2/nlf_l_multi_0.2.2.torchscript'] | _Omitted = _UNSET,
    warmup: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DownloadAndLoadNLFModel``.

    Display name: (Download)Load NLF Model

    Category: WanVideoWrapper

    Returns: nlf_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadNLFModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if url is not _UNSET:
        _kwargs['url'] = url
    if warmup is not _UNSET:
        _kwargs['warmup'] = warmup
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadNLFModel', _id, pass_raw=pass_raw, **_kwargs)

def DownloadAndLoadWav2VecModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    model: Literal['TencentGameMate/chinese-wav2vec2-base', 'facebook/wav2vec2-base-960h'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DownloadAndLoadWav2VecModel``.

    Display name: (Down)load Wav2Vec Model

    Category: WanVideoWrapper

    Returns: wav2vec_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"DownloadAndLoadWav2VecModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'DownloadAndLoadWav2VecModel', _id, pass_raw=pass_raw, **_kwargs)

def DrawArcFaceLandmarks(
    *args: VibeWorkflow,
    _id: str | None = None,
    lynx_face_embeds: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DrawArcFaceLandmarks``.

    Display name: Draw ArcFace Landmarks

    Category: WanVideoWrapper

    Draw face landmarks on an image for visualization/debugging

    Returns: landmarked_image

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"DrawArcFaceLandmarks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if lynx_face_embeds is not _UNSET:
        _kwargs['lynx_face_embeds'] = lynx_face_embeds
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'DrawArcFaceLandmarks', _id, pass_raw=pass_raw, **_kwargs)

def DrawGaussianNoiseOnImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    device: Literal['cpu', 'gpu'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DrawGaussianNoiseOnImage``.

    Display name: Draw Gaussian Noise On Image

    Category: KJNodes/masking

    Fills the background (masked area) with Gaussian noise sampled using the mean and variance of the subject (unmasked) region.

    Returns: images

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"DrawGaussianNoiseOnImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if device is not _UNSET:
        _kwargs['device'] = device
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'DrawGaussianNoiseOnImage', _id, pass_raw=pass_raw, **_kwargs)

def DrawNLFPoses(
    *args: VibeWorkflow,
    _id: str | None = None,
    height: int | _Omitted = _UNSET,
    poses: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    point_radius: int | _Omitted = _UNSET,
    stick_width: float | _Omitted = _UNSET,
    style: Literal['original', 'scail'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DrawNLFPoses``.

    Display name: Draw NLF Poses

    Category: WanVideoWrapper

    Returns: image

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"DrawNLFPoses() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if height is not _UNSET:
        _kwargs['height'] = height
    if poses is not _UNSET:
        _kwargs['poses'] = poses
    if width is not _UNSET:
        _kwargs['width'] = width
    if point_radius is not _UNSET:
        _kwargs['point_radius'] = point_radius
    if stick_width is not _UNSET:
        _kwargs['stick_width'] = stick_width
    if style is not _UNSET:
        _kwargs['style'] = style
    _kwargs.update(_extras)
    return node(wf, 'DrawNLFPoses', _id, pass_raw=pass_raw, **_kwargs)

def DummyComfyWanModelObject(
    *args: VibeWorkflow,
    _id: str | None = None,
    shift: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``DummyComfyWanModelObject``.

    Display name: Dummy Comfy Wan Model Object

    Category: WanVideoWrapper

    Helper node to create empty Wan model to use with BasicScheduler -node to get sigmas

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"DummyComfyWanModelObject() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    _kwargs.update(_extras)
    return node(wf, 'DummyComfyWanModelObject', _id, pass_raw=pass_raw, **_kwargs)

def ExtractStartFramesForContinuations(
    *args: VibeWorkflow,
    _id: str | None = None,
    input_video_frames: Any | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``ExtractStartFramesForContinuations``.

    Display name: Extract Start Frames For Continuations

    Category: WanVideoWrapper

    Extracts the first N frames from a video sequence for continuations.

    Returns: start_frames

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"ExtractStartFramesForContinuations() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input_video_frames is not _UNSET:
        _kwargs['input_video_frames'] = input_video_frames
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    _kwargs.update(_extras)
    return node(wf, 'ExtractStartFramesForContinuations', _id, pass_raw=pass_raw, **_kwargs)

def FaceMaskFromPoseKeypoints(
    *args: VibeWorkflow,
    _id: str | None = None,
    person_index: int | _Omitted = _UNSET,
    pose_kps: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``FaceMaskFromPoseKeypoints``.

    Display name: Face Mask From Pose Keypoints

    Category: ControlNet Preprocessors/Pose Keypoint Postprocess

    Returns: MASK

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"FaceMaskFromPoseKeypoints() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if person_index is not _UNSET:
        _kwargs['person_index'] = person_index
    if pose_kps is not _UNSET:
        _kwargs['pose_kps'] = pose_kps
    _kwargs.update(_extras)
    return node(wf, 'FaceMaskFromPoseKeypoints', _id, pass_raw=pass_raw, **_kwargs)

def FantasyPortraitFaceDetector(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    portrait_model: Any | _Omitted = _UNSET,
    adapter_scale: float | _Omitted = _UNSET,
    device: Literal['cuda', 'cpu'] | _Omitted = _UNSET,
    emo_scale: float | _Omitted = _UNSET,
    mouth_scale: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``FantasyPortraitFaceDetector``.

    Display name: FantasyPortrait Face Detector

    Category: WanVideoWrapper

    Returns: portrait_embeds, bbox, landmarks

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"FantasyPortraitFaceDetector() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if portrait_model is not _UNSET:
        _kwargs['portrait_model'] = portrait_model
    if adapter_scale is not _UNSET:
        _kwargs['adapter_scale'] = adapter_scale
    if device is not _UNSET:
        _kwargs['device'] = device
    if emo_scale is not _UNSET:
        _kwargs['emo_scale'] = emo_scale
    if mouth_scale is not _UNSET:
        _kwargs['mouth_scale'] = mouth_scale
    _kwargs.update(_extras)
    return node(wf, 'FantasyPortraitFaceDetector', _id, pass_raw=pass_raw, **_kwargs)

def FantasyPortraitModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``FantasyPortraitModelLoader``.

    Display name: FantasyPortrait Model Loader

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"FantasyPortraitModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'FantasyPortraitModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def FantasyTalkingModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``FantasyTalkingModelLoader``.

    Display name: FantasyTalking Model Loader

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"FantasyTalkingModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'FantasyTalkingModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def FantasyTalkingWav2VecEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    audio_cfg_scale: float | _Omitted = _UNSET,
    audio_scale: float | _Omitted = _UNSET,
    fantasytalking_model: Any | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    wav2vec_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``FantasyTalkingWav2VecEmbeds``.

    Display name: FantasyTalking Wav2Vec Embeds

    Category: WanVideoWrapper

    Returns: fantasytalking_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"FantasyTalkingWav2VecEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if audio_cfg_scale is not _UNSET:
        _kwargs['audio_cfg_scale'] = audio_cfg_scale
    if audio_scale is not _UNSET:
        _kwargs['audio_scale'] = audio_scale
    if fantasytalking_model is not _UNSET:
        _kwargs['fantasytalking_model'] = fantasytalking_model
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if wav2vec_model is not _UNSET:
        _kwargs['wav2vec_model'] = wav2vec_model
    _kwargs.update(_extras)
    return node(wf, 'FantasyTalkingWav2VecEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def HuMoEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_cfg_scale: float | _Omitted = _UNSET,
    audio_end_percent: float | _Omitted = _UNSET,
    audio_scale: float | _Omitted = _UNSET,
    audio_start_percent: float | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    audio: Any | _Omitted = _UNSET,
    reference_images: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    whisper_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``HuMoEmbeds``.

    Display name: HuMo Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"HuMoEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_cfg_scale is not _UNSET:
        _kwargs['audio_cfg_scale'] = audio_cfg_scale
    if audio_end_percent is not _UNSET:
        _kwargs['audio_end_percent'] = audio_end_percent
    if audio_scale is not _UNSET:
        _kwargs['audio_scale'] = audio_scale
    if audio_start_percent is not _UNSET:
        _kwargs['audio_start_percent'] = audio_start_percent
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if width is not _UNSET:
        _kwargs['width'] = width
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if reference_images is not _UNSET:
        _kwargs['reference_images'] = reference_images
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if whisper_model is not _UNSET:
        _kwargs['whisper_model'] = whisper_model
    _kwargs.update(_extras)
    return node(wf, 'HuMoEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def LandmarksToImage(
    *args: VibeWorkflow,
    _id: str | None = None,
    height: int | _Omitted = _UNSET,
    landmarks: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LandmarksToImage``.

    Display name: Landmarks to Image

    Category: LivePortrait

    Returns: keypoints_image

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LandmarksToImage() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if height is not _UNSET:
        _kwargs['height'] = height
    if landmarks is not _UNSET:
        _kwargs['landmarks'] = landmarks
    if width is not _UNSET:
        _kwargs['width'] = width
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'LandmarksToImage', _id, pass_raw=pass_raw, **_kwargs)

def LoadLynxResampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LoadLynxResampler``.

    Display name: Load Lynx Resampler

    Category: WanVideoWrapper

    Returns: resampler

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LoadLynxResampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'LoadLynxResampler', _id, pass_raw=pass_raw, **_kwargs)

def LoadNLFModel(
    *args: VibeWorkflow,
    _id: str | None = None,
    nlf_model: Any | _Omitted = _UNSET,
    warmup: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LoadNLFModel``.

    Display name: Load NLF Model

    Category: WanVideoWrapper

    Returns: nlf_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LoadNLFModel() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if nlf_model is not _UNSET:
        _kwargs['nlf_model'] = nlf_model
    if warmup is not _UNSET:
        _kwargs['warmup'] = warmup
    _kwargs.update(_extras)
    return node(wf, 'LoadNLFModel', _id, pass_raw=pass_raw, **_kwargs)

def LoadVQVAE(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LoadVQVAE``.

    Display name: Load VQVAE

    Category: WanVideoWrapper

    Returns: vqvae

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LoadVQVAE() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    _kwargs.update(_extras)
    return node(wf, 'LoadVQVAE', _id, pass_raw=pass_raw, **_kwargs)

def LoadWanVideoClipTextEncoder(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LoadWanVideoClipTextEncoder``.

    Display name: WanVideo CLIP Text Encoder Loader

    Category: WanVideoWrapper

    Loads Wan clip_vision model from 'ComfyUI/models/clip_vision'

    Returns: wan_clip_vision

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LoadWanVideoClipTextEncoder() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    _kwargs.update(_extras)
    return node(wf, 'LoadWanVideoClipTextEncoder', _id, pass_raw=pass_raw, **_kwargs)

def LoadWanVideoT5TextEncoder(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp32', 'bf16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LoadWanVideoT5TextEncoder``.

    Display name: WanVideo T5 Text Encoder Loader

    Category: WanVideoWrapper

    Loads Wan text_encoder model from 'ComfyUI/models/LLM'

    Returns: wan_t5_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LoadWanVideoT5TextEncoder() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    _kwargs.update(_extras)
    return node(wf, 'LoadWanVideoT5TextEncoder', _id, pass_raw=pass_raw, **_kwargs)

def LynxEncodeFaceIP(
    *args: VibeWorkflow,
    _id: str | None = None,
    ip_image: Any | _Omitted = _UNSET,
    resampler: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LynxEncodeFaceIP``.

    Display name: Lynx Encode Face IP

    Category: WanVideoWrapper

    Returns: lynx_face_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LynxEncodeFaceIP() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ip_image is not _UNSET:
        _kwargs['ip_image'] = ip_image
    if resampler is not _UNSET:
        _kwargs['resampler'] = resampler
    _kwargs.update(_extras)
    return node(wf, 'LynxEncodeFaceIP', _id, pass_raw=pass_raw, **_kwargs)

def LynxInsightFaceCrop(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``LynxInsightFaceCrop``.

    Display name: Lynx InsightFace Crop

    Category: WanVideoWrapper

    Returns: ip_image, ref_image

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"LynxInsightFaceCrop() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'LynxInsightFaceCrop', _id, pass_raw=pass_raw, **_kwargs)

def MTVCrafterEncodePoses(
    *args: VibeWorkflow,
    _id: str | None = None,
    poses: Any | _Omitted = _UNSET,
    vqvae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MTVCrafterEncodePoses``.

    Display name: MTV Crafter Encode Poses

    Category: WanVideoWrapper

    Returns: mtvcrafter_motion, pose_results

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"MTVCrafterEncodePoses() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if poses is not _UNSET:
        _kwargs['poses'] = poses
    if vqvae is not _UNSET:
        _kwargs['vqvae'] = vqvae
    _kwargs.update(_extras)
    return node(wf, 'MTVCrafterEncodePoses', _id, pass_raw=pass_raw, **_kwargs)

def MochaEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    input_video: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    ref1: Any | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    ref2: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MochaEmbeds``.

    Display name: Mocha Embeds

    Category: WanVideoWrapper

    Input for MoCha model: https://github.com/Orange-3DV-Team/MoCha

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"MochaEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if input_video is not _UNSET:
        _kwargs['input_video'] = input_video
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if ref1 is not _UNSET:
        _kwargs['ref1'] = ref1
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if ref2 is not _UNSET:
        _kwargs['ref2'] = ref2
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    _kwargs.update(_extras)
    return node(wf, 'MochaEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def MultiTalkModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MultiTalkModelLoader``.

    Display name: Multi/InfiniteTalk Model Loader

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"MultiTalkModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def MultiTalkSilentEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    num_frames: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MultiTalkSilentEmbeds``.

    Display name: MultiTalk Silent Embeds

    Category: WanVideoWrapper

    Returns: multitalk_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"MultiTalkSilentEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkSilentEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def MultiTalkWav2VecEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_1: Any | _Omitted = _UNSET,
    audio_cfg_scale: float | _Omitted = _UNSET,
    audio_scale: float | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    multi_audio_type: Literal['para', 'add'] | _Omitted = _UNSET,
    normalize_loudness: bool | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    wav2vec_model: Any | _Omitted = _UNSET,
    add_noise_floor: bool | _Omitted = _UNSET,
    audio_2: Any | _Omitted = _UNSET,
    audio_3: Any | _Omitted = _UNSET,
    audio_4: Any | _Omitted = _UNSET,
    ref_target_masks: Any | _Omitted = _UNSET,
    smooth_transients: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``MultiTalkWav2VecEmbeds``.

    Display name: Multi/InfiniteTalk Wav2vec2 Embeds

    Category: WanVideoWrapper

    Returns: multitalk_embeds, audio, num_frames

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"MultiTalkWav2VecEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_1 is not _UNSET:
        _kwargs['audio_1'] = audio_1
    if audio_cfg_scale is not _UNSET:
        _kwargs['audio_cfg_scale'] = audio_cfg_scale
    if audio_scale is not _UNSET:
        _kwargs['audio_scale'] = audio_scale
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if multi_audio_type is not _UNSET:
        _kwargs['multi_audio_type'] = multi_audio_type
    if normalize_loudness is not _UNSET:
        _kwargs['normalize_loudness'] = normalize_loudness
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if wav2vec_model is not _UNSET:
        _kwargs['wav2vec_model'] = wav2vec_model
    if add_noise_floor is not _UNSET:
        _kwargs['add_noise_floor'] = add_noise_floor
    if audio_2 is not _UNSET:
        _kwargs['audio_2'] = audio_2
    if audio_3 is not _UNSET:
        _kwargs['audio_3'] = audio_3
    if audio_4 is not _UNSET:
        _kwargs['audio_4'] = audio_4
    if ref_target_masks is not _UNSET:
        _kwargs['ref_target_masks'] = ref_target_masks
    if smooth_transients is not _UNSET:
        _kwargs['smooth_transients'] = smooth_transients
    _kwargs.update(_extras)
    return node(wf, 'MultiTalkWav2VecEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def NLFPredict(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    per_batch: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``NLFPredict``.

    Display name: NLF Predict

    Category: WanVideoWrapper

    Returns: pose_results, bboxes

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"NLFPredict() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if model is not _UNSET:
        _kwargs['model'] = model
    if per_batch is not _UNSET:
        _kwargs['per_batch'] = per_batch
    _kwargs.update(_extras)
    return node(wf, 'NLFPredict', _id, pass_raw=pass_raw, **_kwargs)

def NormalizeAudioLoudness(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    lufs: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``NormalizeAudioLoudness``.

    Display name: Normalize Audio Loudness

    Category: WanVideoWrapper

    Returns: audio

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"NormalizeAudioLoudness() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if lufs is not _UNSET:
        _kwargs['lufs'] = lufs
    _kwargs.update(_extras)
    return node(wf, 'NormalizeAudioLoudness', _id, pass_raw=pass_raw, **_kwargs)

def OviMMAudioVAELoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    precision: Literal['bf16', 'fp16', 'fp32'] | _Omitted = _UNSET,
    vae: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    vocoder: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``OviMMAudioVAELoader``.

    Display name: Ovi MMAudio VAE Loader

    Category: WanVideoWrapper/Ovi

    Loads MMAudio VAE for Ovi audio generation

    Returns: mmaudio_vae

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"OviMMAudioVAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if vocoder is not _UNSET:
        _kwargs['vocoder'] = vocoder
    _kwargs.update(_extras)
    return node(wf, 'OviMMAudioVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def QwenLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    model: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'bf16', 'fp32'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``QwenLoader``.

    Display name: Qwen Loader

    Category: WanVideoWrapper

    Returns: QWENMODEL

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"QwenLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if model is not _UNSET:
        _kwargs['model'] = model
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'QwenLoader', _id, pass_raw=pass_raw, **_kwargs)

def ReCamMasterPoseVisualizer(
    *args: VibeWorkflow,
    _id: str | None = None,
    arrow_length: float | _Omitted = _UNSET,
    base_xval: float | _Omitted = _UNSET,
    camera_poses: Any | _Omitted = _UNSET,
    scale: float | _Omitted = _UNSET,
    zval: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``ReCamMasterPoseVisualizer``.

    Display name: ReCamMaster Pose Visualizer

    Category: WanVideoWrapper

    Visualizes the camera poses, from Animatediff-Evolved CameraCtrl Pose

    Returns: IMAGE

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"ReCamMasterPoseVisualizer() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if arrow_length is not _UNSET:
        _kwargs['arrow_length'] = arrow_length
    if base_xval is not _UNSET:
        _kwargs['base_xval'] = base_xval
    if camera_poses is not _UNSET:
        _kwargs['camera_poses'] = camera_poses
    if scale is not _UNSET:
        _kwargs['scale'] = scale
    if zval is not _UNSET:
        _kwargs['zval'] = zval
    _kwargs.update(_extras)
    return node(wf, 'ReCamMasterPoseVisualizer', _id, pass_raw=pass_raw, **_kwargs)

def TextImageEncodeQwenVL(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip: Any | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``TextImageEncodeQwenVL``.

    Category: WanVideoWrapper

    Returns: qwenvl_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"TextImageEncodeQwenVL() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip is not _UNSET:
        _kwargs['clip'] = clip
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if image is not _UNSET:
        _kwargs['image'] = image
    _kwargs.update(_extras)
    return node(wf, 'TextImageEncodeQwenVL', _id, pass_raw=pass_raw, **_kwargs)

def WanMove_native(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    track_coords: str | _Omitted = _UNSET,
    track_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanMove_native``.

    Display name: WanMove Native

    Category: WanVideoWrapper

    Returns: positive, tracks

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanMove_native() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if track_coords is not _UNSET:
        _kwargs['track_coords'] = track_coords
    if track_mask is not _UNSET:
        _kwargs['track_mask'] = track_mask
    _kwargs.update(_extras)
    return node(wf, 'WanMove_native', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoATITracks(
    *args: VibeWorkflow,
    _id: str | None = None,
    end_percent: float | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    temperature: float | _Omitted = _UNSET,
    topk: int | _Omitted = _UNSET,
    tracks: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoATITracks``.

    Display name: WanVideo ATI Tracks

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoATITracks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if height is not _UNSET:
        _kwargs['height'] = height
    if model is not _UNSET:
        _kwargs['model'] = model
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if topk is not _UNSET:
        _kwargs['topk'] = topk
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    if width is not _UNSET:
        _kwargs['width'] = width
    _kwargs.update(_extras)
    return node(wf, 'WanVideoATITracks', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoATITracksVisualize(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    max_radius: int | _Omitted = _UNSET,
    max_retain: int | _Omitted = _UNSET,
    min_radius: int | _Omitted = _UNSET,
    tracks: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoATITracksVisualize``.

    Display name: WanVideo ATI Tracks Visualize

    Category: WanVideoWrapper

    Returns: images

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoATITracksVisualize() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if max_radius is not _UNSET:
        _kwargs['max_radius'] = max_radius
    if max_retain is not _UNSET:
        _kwargs['max_retain'] = max_retain
    if min_radius is not _UNSET:
        _kwargs['min_radius'] = min_radius
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    _kwargs.update(_extras)
    return node(wf, 'WanVideoATITracksVisualize', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoATI_comfy(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    temperature: float | _Omitted = _UNSET,
    topk: int | _Omitted = _UNSET,
    tracks: str | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoATI_comfy``.

    Display name: WanVideo ATI Comfy

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoATI_comfy() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if height is not _UNSET:
        _kwargs['height'] = height
    if temperature is not _UNSET:
        _kwargs['temperature'] = temperature
    if topk is not _UNSET:
        _kwargs['topk'] = topk
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    if width is not _UNSET:
        _kwargs['width'] = width
    _kwargs.update(_extras)
    return node(wf, 'WanVideoATI_comfy', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddBindweaveEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    reference_latents: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    qwenvl_embeds_neg: Any | _Omitted = _UNSET,
    qwenvl_embeds_pos: Any | _Omitted = _UNSET,
    ref_masks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddBindweaveEmbeds``.

    Display name: WanVideo Add Bindweave Embeds

    Category: WanVideoWrapper

    Returns: image_embeds, image_embed_preview, mask_preview

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddBindweaveEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if reference_latents is not _UNSET:
        _kwargs['reference_latents'] = reference_latents
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if qwenvl_embeds_neg is not _UNSET:
        _kwargs['qwenvl_embeds_neg'] = qwenvl_embeds_neg
    if qwenvl_embeds_pos is not _UNSET:
        _kwargs['qwenvl_embeds_pos'] = qwenvl_embeds_pos
    if ref_masks is not _UNSET:
        _kwargs['ref_masks'] = ref_masks
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddBindweaveEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddControlEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    fun_ref_image: Any | _Omitted = _UNSET,
    latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddControlEmbeds``.

    Display name: WanVideo Add Control Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddControlEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if fun_ref_image is not _UNSET:
        _kwargs['fun_ref_image'] = fun_ref_image
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddControlEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddDualControlEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    first_frame_noise_level: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    dense: Any | _Omitted = _UNSET,
    prev_images: Any | _Omitted = _UNSET,
    sparse: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddDualControlEmbeds``.

    Display name: WanVideo Add Dual Control Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddDualControlEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if first_frame_noise_level is not _UNSET:
        _kwargs['first_frame_noise_level'] = first_frame_noise_level
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if dense is not _UNSET:
        _kwargs['dense'] = dense
    if prev_images is not _UNSET:
        _kwargs['prev_images'] = prev_images
    if sparse is not _UNSET:
        _kwargs['sparse'] = sparse
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddDualControlEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddExtraLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    extra_latents: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    latent_index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddExtraLatent``.

    Display name: WanVideo Add Extra Latent

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddExtraLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if latent_index is not _UNSET:
        _kwargs['latent_index'] = latent_index
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddExtraLatent', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddFantasyPortrait(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    portrait_cfg: float | _Omitted = _UNSET,
    portrait_embeds: Any | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddFantasyPortrait``.

    Display name: WanVideo Add Fantasy Portrait

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddFantasyPortrait() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if portrait_cfg is not _UNSET:
        _kwargs['portrait_cfg'] = portrait_cfg
    if portrait_embeds is not _UNSET:
        _kwargs['portrait_embeds'] = portrait_embeds
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddFantasyPortrait', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddFlashVSRInput(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddFlashVSRInput``.

    Display name: WanVideo Add FlashVSR Input

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddFlashVSRInput() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddFlashVSRInput', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddLucyEditLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    extra_latents: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddLucyEditLatents``.

    Display name: WanVideo Add LucyEdit Latents

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddLucyEditLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddLucyEditLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddLynxEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    ip_scale: float | _Omitted = _UNSET,
    lynx_cfg_scale: float | _Omitted = _UNSET,
    ref_scale: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    lynx_ip_embeds: Any | _Omitted = _UNSET,
    ref_blocks_to_use: str | _Omitted = _UNSET,
    ref_image: Any | _Omitted = _UNSET,
    ref_text_embed: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddLynxEmbeds``.

    Display name: WanVideo Add Lynx Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddLynxEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if ip_scale is not _UNSET:
        _kwargs['ip_scale'] = ip_scale
    if lynx_cfg_scale is not _UNSET:
        _kwargs['lynx_cfg_scale'] = lynx_cfg_scale
    if ref_scale is not _UNSET:
        _kwargs['ref_scale'] = ref_scale
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if lynx_ip_embeds is not _UNSET:
        _kwargs['lynx_ip_embeds'] = lynx_ip_embeds
    if ref_blocks_to_use is not _UNSET:
        _kwargs['ref_blocks_to_use'] = ref_blocks_to_use
    if ref_image is not _UNSET:
        _kwargs['ref_image'] = ref_image
    if ref_text_embed is not _UNSET:
        _kwargs['ref_text_embed'] = ref_text_embed
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddLynxEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddMTVMotion(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    mtv_crafter_motion: Any | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddMTVMotion``.

    Display name: WanVideo MTV Crafter Motion

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddMTVMotion() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if mtv_crafter_motion is not _UNSET:
        _kwargs['mtv_crafter_motion'] = mtv_crafter_motion
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddMTVMotion', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddOneToAllExtendEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    prev_latents: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    frames_processed: int | _Omitted = _UNSET,
    if_not_enough_frames: Literal['pad_with_last', 'error'] | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    window_size: int | _Omitted = _UNSET,
    pose_images: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddOneToAllExtendEmbeds``.

    Display name: WanVideo Add OneToAll Extend Embeds

    Category: WanVideoWrapper

    Returns: image_embeds, pose_slice

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddOneToAllExtendEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prev_latents is not _UNSET:
        _kwargs['prev_latents'] = prev_latents
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if frames_processed is not _UNSET:
        _kwargs['frames_processed'] = frames_processed
    if if_not_enough_frames is not _UNSET:
        _kwargs['if_not_enough_frames'] = if_not_enough_frames
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if window_size is not _UNSET:
        _kwargs['window_size'] = window_size
    if pose_images is not _UNSET:
        _kwargs['pose_images'] = pose_images
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddOneToAllExtendEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddOneToAllPoseEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_images: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pose_cfg_scale: float | _Omitted = _UNSET,
    pose_prefix_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddOneToAllPoseEmbeds``.

    Display name: WanVideo Add OneToAll Pose Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddOneToAllPoseEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_images is not _UNSET:
        _kwargs['pose_images'] = pose_images
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if pose_cfg_scale is not _UNSET:
        _kwargs['pose_cfg_scale'] = pose_cfg_scale
    if pose_prefix_image is not _UNSET:
        _kwargs['pose_prefix_image'] = pose_prefix_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddOneToAllPoseEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddOneToAllReferenceEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    ref_image: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    ref_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddOneToAllReferenceEmbeds``.

    Display name: WanVideo Add OneToAll Reference Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddOneToAllReferenceEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ref_image is not _UNSET:
        _kwargs['ref_image'] = ref_image
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if ref_mask is not _UNSET:
        _kwargs['ref_mask'] = ref_mask
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddOneToAllReferenceEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddOviAudioToLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_samples: Any | _Omitted = _UNSET,
    original_samples: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddOviAudioToLatents``.

    Display name: WanVideo Add MMAudio To Latents

    Category: WanVideoWrapper/Ovi

    Returns: samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddOviAudioToLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_samples is not _UNSET:
        _kwargs['audio_samples'] = audio_samples
    if original_samples is not _UNSET:
        _kwargs['original_samples'] = original_samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddOviAudioToLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddPusaNoise(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    noise_multipliers: float | _Omitted = _UNSET,
    noisy_steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddPusaNoise``.

    Display name: WanVideo Add Pusa Noise

    Category: WanVideoWrapper

    Adds latent and timestep noise multipliers when using flowmatch_pusa

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddPusaNoise() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if noise_multipliers is not _UNSET:
        _kwargs['noise_multipliers'] = noise_multipliers
    if noisy_steps is not _UNSET:
        _kwargs['noisy_steps'] = noisy_steps
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddPusaNoise', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddS2VEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio_scale: float | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    frame_window_size: int | _Omitted = _UNSET,
    pose_end_percent: float | _Omitted = _UNSET,
    pose_start_percent: float | _Omitted = _UNSET,
    audio_encoder_output: Any | _Omitted = _UNSET,
    enable_framepack: bool | _Omitted = _UNSET,
    pose_latent: Any | _Omitted = _UNSET,
    ref_latent: Any | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddS2VEmbeds``.

    Display name: WanVideo Add S2V Embeds

    Category: WanVideoWrapper

    Returns: image_embeds, audio_frame_count

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddS2VEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio_scale is not _UNSET:
        _kwargs['audio_scale'] = audio_scale
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if frame_window_size is not _UNSET:
        _kwargs['frame_window_size'] = frame_window_size
    if pose_end_percent is not _UNSET:
        _kwargs['pose_end_percent'] = pose_end_percent
    if pose_start_percent is not _UNSET:
        _kwargs['pose_start_percent'] = pose_start_percent
    if audio_encoder_output is not _UNSET:
        _kwargs['audio_encoder_output'] = audio_encoder_output
    if enable_framepack is not _UNSET:
        _kwargs['enable_framepack'] = enable_framepack
    if pose_latent is not _UNSET:
        _kwargs['pose_latent'] = pose_latent
    if ref_latent is not _UNSET:
        _kwargs['ref_latent'] = ref_latent
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddS2VEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddSCAILPoseEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_images: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddSCAILPoseEmbeds``.

    Display name: WanVideo Add SCAIL Pose Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddSCAILPoseEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_images is not _UNSET:
        _kwargs['pose_images'] = pose_images
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddSCAILPoseEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddSCAILReferenceEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    ref_image: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    clip_embeds: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddSCAILReferenceEmbeds``.

    Display name: WanVideo Add SCAIL Reference Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddSCAILReferenceEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ref_image is not _UNSET:
        _kwargs['ref_image'] = ref_image
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddSCAILReferenceEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddStandInLatent(
    *args: VibeWorkflow,
    _id: str | None = None,
    ip_image_latent: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    freq_offset: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddStandInLatent``.

    Display name: WanVideo Add StandIn Latent

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddStandInLatent() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ip_image_latent is not _UNSET:
        _kwargs['ip_image_latent'] = ip_image_latent
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if freq_offset is not _UNSET:
        _kwargs['freq_offset'] = freq_offset
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddStandInLatent', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddSteadyDancerEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_latents_positive: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    pose_strength_spatial: float | _Omitted = _UNSET,
    pose_strength_temporal: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    clip_vision_embeds: Any | _Omitted = _UNSET,
    pose_latents_negative: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddSteadyDancerEmbeds``.

    Display name: WanVideo Add SteadyDancer Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddSteadyDancerEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_latents_positive is not _UNSET:
        _kwargs['pose_latents_positive'] = pose_latents_positive
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if pose_strength_spatial is not _UNSET:
        _kwargs['pose_strength_spatial'] = pose_strength_spatial
    if pose_strength_temporal is not _UNSET:
        _kwargs['pose_strength_temporal'] = pose_strength_temporal
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if clip_vision_embeds is not _UNSET:
        _kwargs['clip_vision_embeds'] = clip_vision_embeds
    if pose_latents_negative is not _UNSET:
        _kwargs['pose_latents_negative'] = pose_latents_negative
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddSteadyDancerEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddStoryMemLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    memory_images: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    rope_negative_offset: bool | _Omitted = _UNSET,
    rope_negative_offset_frames: int | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddStoryMemLatents``.

    Display name: WanVideo Add StoryMem Latents

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddStoryMemLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if memory_images is not _UNSET:
        _kwargs['memory_images'] = memory_images
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if rope_negative_offset is not _UNSET:
        _kwargs['rope_negative_offset'] = rope_negative_offset
    if rope_negative_offset_frames is not _UNSET:
        _kwargs['rope_negative_offset_frames'] = rope_negative_offset_frames
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddStoryMemLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddTTMLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    mask: Any | _Omitted = _UNSET,
    reference_latents: Any | _Omitted = _UNSET,
    embeds: Any | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddTTMLatents``.

    Display name: WanVideo Add TTMLatents

    Category: WanVideoWrapper

    https://github.com/time-to-move/TTM

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddTTMLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if reference_latents is not _UNSET:
        _kwargs['reference_latents'] = reference_latents
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddTTMLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAddWanMoveTracks(
    *args: VibeWorkflow,
    _id: str | None = None,
    image_embeds: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    track_coords: str | _Omitted = _UNSET,
    track_mask: Any | _Omitted = _UNSET,
    tracks: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAddWanMoveTracks``.

    Display name: WanVideo Add WanMove Tracks

    Category: WanVideoWrapper

    Returns: image_embeds, tracks

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAddWanMoveTracks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image_embeds is not _UNSET:
        _kwargs['image_embeds'] = image_embeds
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if track_coords is not _UNSET:
        _kwargs['track_coords'] = track_coords
    if track_mask is not _UNSET:
        _kwargs['track_mask'] = track_mask
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAddWanMoveTracks', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoAnimateEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    colormatch: Literal['disabled', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = _UNSET,
    face_strength: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    frame_window_size: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    pose_strength: float | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    bg_images: Any | _Omitted = _UNSET,
    clip_embeds: Any | _Omitted = _UNSET,
    face_images: Any | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    pose_images: Any | _Omitted = _UNSET,
    ref_images: Any | _Omitted = _UNSET,
    start_ref_image: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoAnimateEmbeds``.

    Display name: WanVideo Animate Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoAnimateEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if colormatch is not _UNSET:
        _kwargs['colormatch'] = colormatch
    if face_strength is not _UNSET:
        _kwargs['face_strength'] = face_strength
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if frame_window_size is not _UNSET:
        _kwargs['frame_window_size'] = frame_window_size
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if pose_strength is not _UNSET:
        _kwargs['pose_strength'] = pose_strength
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if bg_images is not _UNSET:
        _kwargs['bg_images'] = bg_images
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    if face_images is not _UNSET:
        _kwargs['face_images'] = face_images
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if pose_images is not _UNSET:
        _kwargs['pose_images'] = pose_images
    if ref_images is not _UNSET:
        _kwargs['ref_images'] = ref_images
    if start_ref_image is not _UNSET:
        _kwargs['start_ref_image'] = start_ref_image
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoAnimateEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoApplyNAG(
    *args: VibeWorkflow,
    _id: str | None = None,
    nag_text_embeds: Any | _Omitted = _UNSET,
    original_text_embeds: Any | _Omitted = _UNSET,
    nag_alpha: float | _Omitted = _UNSET,
    nag_scale: float | _Omitted = _UNSET,
    nag_tau: float | _Omitted = _UNSET,
    inplace: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoApplyNAG``.

    Display name: WanVideo Apply NAG

    Category: WanVideoWrapper

    Adds NAG prompt embeds to original prompt embeds: 'https://github.com/ChenDarYen/Normalized-Attention-Guidance'

    Returns: text_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoApplyNAG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if nag_text_embeds is not _UNSET:
        _kwargs['nag_text_embeds'] = nag_text_embeds
    if original_text_embeds is not _UNSET:
        _kwargs['original_text_embeds'] = original_text_embeds
    if nag_alpha is not _UNSET:
        _kwargs['nag_alpha'] = nag_alpha
    if nag_scale is not _UNSET:
        _kwargs['nag_scale'] = nag_scale
    if nag_tau is not _UNSET:
        _kwargs['nag_tau'] = nag_tau
    if inplace is not _UNSET:
        _kwargs['inplace'] = inplace
    _kwargs.update(_extras)
    return node(wf, 'WanVideoApplyNAG', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoBlockList(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoBlockList``.

    Display name: WanVideo Block List

    Category: WanVideoWrapper

    Comma separated list of blocks to apply block swap to, can also use ranges like '0-5' or '0,2,3-5' etc., can be connected to the dense_blocks input of 'WanVideoSetRadialAttention' node

    Returns: block_list

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoBlockList() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs.update(_extras)
    return node(wf, 'WanVideoBlockList', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoBlockSwap(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks_to_swap: int | _Omitted = _UNSET,
    offload_img_emb: bool | _Omitted = _UNSET,
    offload_txt_emb: bool | _Omitted = _UNSET,
    block_swap_debug: bool | _Omitted = _UNSET,
    prefetch_blocks: int | _Omitted = _UNSET,
    use_non_blocking: bool | _Omitted = _UNSET,
    vace_blocks_to_swap: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoBlockSwap``.

    Display name: WanVideo Block Swap

    Category: WanVideoWrapper

    Settings for block swapping, reduces VRAM use by swapping blocks to CPU memory

    Returns: block_swap_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoBlockSwap() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if blocks_to_swap is not _UNSET:
        _kwargs['blocks_to_swap'] = blocks_to_swap
    if offload_img_emb is not _UNSET:
        _kwargs['offload_img_emb'] = offload_img_emb
    if offload_txt_emb is not _UNSET:
        _kwargs['offload_txt_emb'] = offload_txt_emb
    if block_swap_debug is not _UNSET:
        _kwargs['block_swap_debug'] = block_swap_debug
    if prefetch_blocks is not _UNSET:
        _kwargs['prefetch_blocks'] = prefetch_blocks
    if use_non_blocking is not _UNSET:
        _kwargs['use_non_blocking'] = use_non_blocking
    if vace_blocks_to_swap is not _UNSET:
        _kwargs['vace_blocks_to_swap'] = vace_blocks_to_swap
    _kwargs.update(_extras)
    return node(wf, 'WanVideoBlockSwap', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoClipVisionEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_vision: Any | _Omitted = _UNSET,
    image_1: Any | _Omitted = _UNSET,
    combine_embeds: Literal['average', 'sum', 'concat', 'batch'] | _Omitted = _UNSET,
    crop: Literal['center', 'disabled'] | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    strength_1: float | _Omitted = _UNSET,
    strength_2: float | _Omitted = _UNSET,
    image_2: Any | _Omitted = _UNSET,
    negative_image: Any | _Omitted = _UNSET,
    ratio: float | _Omitted = _UNSET,
    tiles: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoClipVisionEncode``.

    Display name: WanVideo ClipVision Encode

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoClipVisionEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_vision is not _UNSET:
        _kwargs['clip_vision'] = clip_vision
    if image_1 is not _UNSET:
        _kwargs['image_1'] = image_1
    if combine_embeds is not _UNSET:
        _kwargs['combine_embeds'] = combine_embeds
    if crop is not _UNSET:
        _kwargs['crop'] = crop
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if strength_1 is not _UNSET:
        _kwargs['strength_1'] = strength_1
    if strength_2 is not _UNSET:
        _kwargs['strength_2'] = strength_2
    if image_2 is not _UNSET:
        _kwargs['image_2'] = image_2
    if negative_image is not _UNSET:
        _kwargs['negative_image'] = negative_image
    if ratio is not _UNSET:
        _kwargs['ratio'] = ratio
    if tiles is not _UNSET:
        _kwargs['tiles'] = tiles
    _kwargs.update(_extras)
    return node(wf, 'WanVideoClipVisionEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoCombineEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds_1: Any | _Omitted = _UNSET,
    embeds_2: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoCombineEmbeds``.

    Display name: WanVideo Combine Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoCombineEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds_1 is not _UNSET:
        _kwargs['embeds_1'] = embeds_1
    if embeds_2 is not _UNSET:
        _kwargs['embeds_2'] = embeds_2
    _kwargs.update(_extras)
    return node(wf, 'WanVideoCombineEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoContextOptions(
    *args: VibeWorkflow,
    _id: str | None = None,
    context_frames: int | _Omitted = _UNSET,
    context_overlap: int | _Omitted = _UNSET,
    context_schedule: Literal['uniform_standard', 'uniform_looped', 'static_standard'] | _Omitted = _UNSET,
    context_stride: int | _Omitted = _UNSET,
    freenoise: bool | _Omitted = _UNSET,
    verbose: bool | _Omitted = _UNSET,
    fuse_method: Literal['linear', 'pyramid'] | _Omitted = _UNSET,
    reference_latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoContextOptions``.

    Display name: WanVideo Context Options

    Category: WanVideoWrapper

    Context options for WanVideo, allows splitting the video into context windows and attemps blending them for longer generations than the model and memory otherwise would allow.

    Returns: context_options

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoContextOptions() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if context_frames is not _UNSET:
        _kwargs['context_frames'] = context_frames
    if context_overlap is not _UNSET:
        _kwargs['context_overlap'] = context_overlap
    if context_schedule is not _UNSET:
        _kwargs['context_schedule'] = context_schedule
    if context_stride is not _UNSET:
        _kwargs['context_stride'] = context_stride
    if freenoise is not _UNSET:
        _kwargs['freenoise'] = freenoise
    if verbose is not _UNSET:
        _kwargs['verbose'] = verbose
    if fuse_method is not _UNSET:
        _kwargs['fuse_method'] = fuse_method
    if reference_latent is not _UNSET:
        _kwargs['reference_latent'] = reference_latent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoContextOptions', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoControlEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    fun_ref_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoControlEmbeds``.

    Display name: WanVideo Control Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoControlEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if fun_ref_image is not _UNSET:
        _kwargs['fun_ref_image'] = fun_ref_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoControlnet(
    *args: VibeWorkflow,
    _id: str | None = None,
    control_images: Any | _Omitted = _UNSET,
    control_end_percent: float | _Omitted = _UNSET,
    control_start_percent: float | _Omitted = _UNSET,
    control_stride: int | _Omitted = _UNSET,
    controlnet: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoControlnet``.

    Display name: WanVideo Controlnet Apply

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoControlnet() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if control_images is not _UNSET:
        _kwargs['control_images'] = control_images
    if control_end_percent is not _UNSET:
        _kwargs['control_end_percent'] = control_end_percent
    if control_start_percent is not _UNSET:
        _kwargs['control_start_percent'] = control_start_percent
    if control_stride is not _UNSET:
        _kwargs['control_stride'] = control_stride
    if controlnet is not _UNSET:
        _kwargs['controlnet'] = controlnet
    if model is not _UNSET:
        _kwargs['model'] = model
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlnet', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoControlnetLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp8_e4m3fn_fast_no_ffn'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoControlnetLoader``.

    Display name: WanVideo Controlnet Loader

    Category: WanVideoWrapper

    Loads ControlNet model from 'https://huggingface.co/collections/TheDenk/wan21-controlnets-68302b430411dafc0d74d2fc'

    Returns: controlnet

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoControlnetLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if model is not _UNSET:
        _kwargs['model'] = model
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    _kwargs.update(_extras)
    return node(wf, 'WanVideoControlnetLoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoDecode(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    enable_vae_tiling: bool | _Omitted = _UNSET,
    tile_stride_x: int | _Omitted = _UNSET,
    tile_stride_y: int | _Omitted = _UNSET,
    tile_x: int | _Omitted = _UNSET,
    tile_y: int | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    normalization: Literal['default', 'minmax', 'none'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoDecode``.

    Display name: WanVideo Decode

    Category: WanVideoWrapper

    Returns: images

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoDecode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if enable_vae_tiling is not _UNSET:
        _kwargs['enable_vae_tiling'] = enable_vae_tiling
    if tile_stride_x is not _UNSET:
        _kwargs['tile_stride_x'] = tile_stride_x
    if tile_stride_y is not _UNSET:
        _kwargs['tile_stride_y'] = tile_stride_y
    if tile_x is not _UNSET:
        _kwargs['tile_x'] = tile_x
    if tile_y is not _UNSET:
        _kwargs['tile_y'] = tile_y
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if normalization is not _UNSET:
        _kwargs['normalization'] = normalization
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDecode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoDecodeOviAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    mmaudio_vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoDecodeOviAudio``.

    Display name: WanVideo Decode Ovi Audio

    Category: WanVideoWrapper/Ovi

    Returns: audio

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoDecodeOviAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if mmaudio_vae is not _UNSET:
        _kwargs['mmaudio_vae'] = mmaudio_vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDecodeOviAudio', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoDiffusionForcingSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    text_embeds: Any | _Omitted = _UNSET,
    addnoise_condition: int | _Omitted = _UNSET,
    cfg: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    fps: float | _Omitted = _UNSET,
    image_embeds: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    scheduler: Literal['unipc', 'unipc/beta', 'euler', 'euler/beta', 'lcm', 'lcm/beta'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    cache_args: Any | _Omitted = _UNSET,
    denoise_strength: float | _Omitted = _UNSET,
    experimental_args: Any | _Omitted = _UNSET,
    prefix_samples: Any | _Omitted = _UNSET,
    rope_function: Literal['default', 'comfy'] | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    slg_args: Any | _Omitted = _UNSET,
    unianimate_poses: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoDiffusionForcingSampler``.

    Display name: WanVideo Diffusion Forcing Sampler

    Category: WanVideoWrapper

    Returns: samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoDiffusionForcingSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if text_embeds is not _UNSET:
        _kwargs['text_embeds'] = text_embeds
    if addnoise_condition is not _UNSET:
        _kwargs['addnoise_condition'] = addnoise_condition
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if fps is not _UNSET:
        _kwargs['fps'] = fps
    if image_embeds is not _UNSET:
        _kwargs['image_embeds'] = image_embeds
    if model is not _UNSET:
        _kwargs['model'] = model
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if cache_args is not _UNSET:
        _kwargs['cache_args'] = cache_args
    if denoise_strength is not _UNSET:
        _kwargs['denoise_strength'] = denoise_strength
    if experimental_args is not _UNSET:
        _kwargs['experimental_args'] = experimental_args
    if prefix_samples is not _UNSET:
        _kwargs['prefix_samples'] = prefix_samples
    if rope_function is not _UNSET:
        _kwargs['rope_function'] = rope_function
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if slg_args is not _UNSET:
        _kwargs['slg_args'] = slg_args
    if unianimate_poses is not _UNSET:
        _kwargs['unianimate_poses'] = unianimate_poses
    _kwargs.update(_extras)
    return node(wf, 'WanVideoDiffusionForcingSampler', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEasyCache(
    *args: VibeWorkflow,
    _id: str | None = None,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    easycache_thresh: float | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoEasyCache``.

    Display name: WanVideo EasyCache

    Category: WanVideoWrapper

    EasyCache for WanVideoWrapper, source https://github.com/H-EmbodVis/EasyCache

    Returns: cache_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEasyCache() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cache_device is not _UNSET:
        _kwargs['cache_device'] = cache_device
    if easycache_thresh is not _UNSET:
        _kwargs['easycache_thresh'] = easycache_thresh
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEasyCache', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEmptyEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    control_embeds: Any | _Omitted = _UNSET,
    extra_latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoEmptyEmbeds``.

    Display name: WanVideo Empty Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEmptyEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if width is not _UNSET:
        _kwargs['width'] = width
    if control_embeds is not _UNSET:
        _kwargs['control_embeds'] = control_embeds
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEmptyEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEmptyMMAudioLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    length: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoEmptyMMAudioLatents``.

    Display name: WanVideo Empty MMAudio Latents

    Category: WanVideoWrapper/Ovi

    Returns: samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEmptyMMAudioLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if length is not _UNSET:
        _kwargs['length'] = length
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEmptyMMAudioLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    enable_vae_tiling: bool | _Omitted = _UNSET,
    tile_stride_x: int | _Omitted = _UNSET,
    tile_stride_y: int | _Omitted = _UNSET,
    tile_x: int | _Omitted = _UNSET,
    tile_y: int | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    latent_strength: float | _Omitted = _UNSET,
    mask: Any | _Omitted = _UNSET,
    noise_aug_strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoEncode``.

    Display name: WanVideo Encode

    Category: WanVideoWrapper

    Returns: samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if enable_vae_tiling is not _UNSET:
        _kwargs['enable_vae_tiling'] = enable_vae_tiling
    if tile_stride_x is not _UNSET:
        _kwargs['tile_stride_x'] = tile_stride_x
    if tile_stride_y is not _UNSET:
        _kwargs['tile_stride_y'] = tile_stride_y
    if tile_x is not _UNSET:
        _kwargs['tile_x'] = tile_x
    if tile_y is not _UNSET:
        _kwargs['tile_y'] = tile_y
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if latent_strength is not _UNSET:
        _kwargs['latent_strength'] = latent_strength
    if mask is not _UNSET:
        _kwargs['mask'] = mask
    if noise_aug_strength is not _UNSET:
        _kwargs['noise_aug_strength'] = noise_aug_strength
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEncodeLatentBatch(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    enable_vae_tiling: bool | _Omitted = _UNSET,
    tile_stride_x: int | _Omitted = _UNSET,
    tile_stride_y: int | _Omitted = _UNSET,
    tile_x: int | _Omitted = _UNSET,
    tile_y: int | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoEncodeLatentBatch``.

    Display name: WanVideo Encode Latent Batch

    Category: WanVideoWrapper

    Encodes a batch of images individually to create a latent video batch where each video is a single frame, useful for I2V init purposes, for example as multiple context window inits

    Returns: samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEncodeLatentBatch() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if enable_vae_tiling is not _UNSET:
        _kwargs['enable_vae_tiling'] = enable_vae_tiling
    if tile_stride_x is not _UNSET:
        _kwargs['tile_stride_x'] = tile_stride_x
    if tile_stride_y is not _UNSET:
        _kwargs['tile_stride_y'] = tile_stride_y
    if tile_x is not _UNSET:
        _kwargs['tile_x'] = tile_x
    if tile_y is not _UNSET:
        _kwargs['tile_y'] = tile_y
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEncodeLatentBatch', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEncodeOviAudio(
    *args: VibeWorkflow,
    _id: str | None = None,
    audio: Any | _Omitted = _UNSET,
    mmaudio_vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoEncodeOviAudio``.

    Display name: WanVideo Encode Ovi Audio

    Category: WanVideoWrapper/Ovi

    Returns: samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEncodeOviAudio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if audio is not _UNSET:
        _kwargs['audio'] = audio
    if mmaudio_vae is not _UNSET:
        _kwargs['mmaudio_vae'] = mmaudio_vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEncodeOviAudio', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoEnhanceAVideo(
    *args: VibeWorkflow,
    _id: str | None = None,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    weight: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoEnhanceAVideo``.

    Display name: WanVideo Enhance-A-Video

    Category: WanVideoWrapper

    https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video

    Returns: feta_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoEnhanceAVideo() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if weight is not _UNSET:
        _kwargs['weight'] = weight
    _kwargs.update(_extras)
    return node(wf, 'WanVideoEnhanceAVideo', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoExperimentalArgs(
    *args: VibeWorkflow,
    _id: str | None = None,
    bidirectional_sampling: bool | _Omitted = _UNSET,
    cfg_zero_star: bool | _Omitted = _UNSET,
    fresca_freq_cutoff: int | _Omitted = _UNSET,
    fresca_scale_high: float | _Omitted = _UNSET,
    fresca_scale_low: float | _Omitted = _UNSET,
    raag_alpha: float | _Omitted = _UNSET,
    temporal_score_rescaling: bool | _Omitted = _UNSET,
    tsr_k: float | _Omitted = _UNSET,
    tsr_sigma: float | _Omitted = _UNSET,
    use_fresca: bool | _Omitted = _UNSET,
    use_tcfg: bool | _Omitted = _UNSET,
    use_zero_init: bool | _Omitted = _UNSET,
    video_attention_split_steps: str | _Omitted = _UNSET,
    zero_star_steps: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoExperimentalArgs``.

    Display name: WanVideo Experimental Args

    Category: WanVideoWrapper

    Experimental stuff

    Returns: exp_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoExperimentalArgs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if bidirectional_sampling is not _UNSET:
        _kwargs['bidirectional_sampling'] = bidirectional_sampling
    if cfg_zero_star is not _UNSET:
        _kwargs['cfg_zero_star'] = cfg_zero_star
    if fresca_freq_cutoff is not _UNSET:
        _kwargs['fresca_freq_cutoff'] = fresca_freq_cutoff
    if fresca_scale_high is not _UNSET:
        _kwargs['fresca_scale_high'] = fresca_scale_high
    if fresca_scale_low is not _UNSET:
        _kwargs['fresca_scale_low'] = fresca_scale_low
    if raag_alpha is not _UNSET:
        _kwargs['raag_alpha'] = raag_alpha
    if temporal_score_rescaling is not _UNSET:
        _kwargs['temporal_score_rescaling'] = temporal_score_rescaling
    if tsr_k is not _UNSET:
        _kwargs['tsr_k'] = tsr_k
    if tsr_sigma is not _UNSET:
        _kwargs['tsr_sigma'] = tsr_sigma
    if use_fresca is not _UNSET:
        _kwargs['use_fresca'] = use_fresca
    if use_tcfg is not _UNSET:
        _kwargs['use_tcfg'] = use_tcfg
    if use_zero_init is not _UNSET:
        _kwargs['use_zero_init'] = use_zero_init
    if video_attention_split_steps is not _UNSET:
        _kwargs['video_attention_split_steps'] = video_attention_split_steps
    if zero_star_steps is not _UNSET:
        _kwargs['zero_star_steps'] = zero_star_steps
    _kwargs.update(_extras)
    return node(wf, 'WanVideoExperimentalArgs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoExtraModelSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    extra_model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    prev_model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoExtraModelSelect``.

    Display name: WanVideo Extra Model Select

    Category: WanVideoWrapper

    Extra model to load and add to the main model, ie. VACE or MTV Crafter 'ComfyUI/models/diffusion_models'

    Returns: extra_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoExtraModelSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if extra_model is not _UNSET:
        _kwargs['extra_model'] = extra_model
    if prev_model is not _UNSET:
        _kwargs['prev_model'] = prev_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoExtraModelSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoFlashVSRDecoderLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoFlashVSRDecoderLoader``.

    Display name: WanVideo FlashVSR Decoder Loader

    Category: WanVideoWrapper

    Loads Wan VAE model from 'ComfyUI/models/vae'

    Returns: vae

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoFlashVSRDecoderLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'WanVideoFlashVSRDecoderLoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoFreeInitArgs(
    *args: VibeWorkflow,
    _id: str | None = None,
    freeinit_d_s: float | _Omitted = _UNSET,
    freeinit_d_t: float | _Omitted = _UNSET,
    freeinit_method: Literal['butterworth', 'ideal', 'gaussian', 'none'] | _Omitted = _UNSET,
    freeinit_n: int | _Omitted = _UNSET,
    freeinit_num_iters: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoFreeInitArgs``.

    Display name: WanVideo Free Init Args

    Category: WanVideoWrapper

    https://github.com/TianxingWu/FreeInit; FreeInit, a concise yet effective method to improve temporal consistency of videos generated by diffusion models

    Returns: freeinit_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoFreeInitArgs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if freeinit_d_s is not _UNSET:
        _kwargs['freeinit_d_s'] = freeinit_d_s
    if freeinit_d_t is not _UNSET:
        _kwargs['freeinit_d_t'] = freeinit_d_t
    if freeinit_method is not _UNSET:
        _kwargs['freeinit_method'] = freeinit_method
    if freeinit_n is not _UNSET:
        _kwargs['freeinit_n'] = freeinit_n
    if freeinit_num_iters is not _UNSET:
        _kwargs['freeinit_num_iters'] = freeinit_num_iters
    _kwargs.update(_extras)
    return node(wf, 'WanVideoFreeInitArgs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoFunCameraEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    end_percent: float | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    poses: Any | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoFunCameraEmbeds``.

    Display name: WanVideo FunCamera Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoFunCameraEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if height is not _UNSET:
        _kwargs['height'] = height
    if poses is not _UNSET:
        _kwargs['poses'] = poses
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if width is not _UNSET:
        _kwargs['width'] = width
    _kwargs.update(_extras)
    return node(wf, 'WanVideoFunCameraEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoImageClipEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    clip_vision: Any | _Omitted = _UNSET,
    image: Any | _Omitted = _UNSET,
    generation_height: int | _Omitted = _UNSET,
    generation_width: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    adjust_resolution: bool | _Omitted = _UNSET,
    clip_embed_strength: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    latent_strength: float | _Omitted = _UNSET,
    noise_aug_strength: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoImageClipEncode``.

    Display name: WanVideo ImageClip Encode (Deprecated)

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoImageClipEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if clip_vision is not _UNSET:
        _kwargs['clip_vision'] = clip_vision
    if image is not _UNSET:
        _kwargs['image'] = image
    if generation_height is not _UNSET:
        _kwargs['generation_height'] = generation_height
    if generation_width is not _UNSET:
        _kwargs['generation_width'] = generation_width
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if adjust_resolution is not _UNSET:
        _kwargs['adjust_resolution'] = adjust_resolution
    if clip_embed_strength is not _UNSET:
        _kwargs['clip_embed_strength'] = clip_embed_strength
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if latent_strength is not _UNSET:
        _kwargs['latent_strength'] = latent_strength
    if noise_aug_strength is not _UNSET:
        _kwargs['noise_aug_strength'] = noise_aug_strength
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageClipEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoImageResizeToClosest(
    *args: VibeWorkflow,
    _id: str | None = None,
    image: Any | _Omitted = _UNSET,
    aspect_ratio_preservation: Literal['keep_input', 'stretch_to_new', 'crop_to_new'] | _Omitted = _UNSET,
    generation_height: int | _Omitted = _UNSET,
    generation_width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoImageResizeToClosest``.

    Display name: WanVideo Image Resize To Closest

    Category: WanVideoWrapper

    Resizes image to the closest supported resolution based on aspect ratio and max pixels, according to the original code

    Returns: image, width, height

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoImageResizeToClosest() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if image is not _UNSET:
        _kwargs['image'] = image
    if aspect_ratio_preservation is not _UNSET:
        _kwargs['aspect_ratio_preservation'] = aspect_ratio_preservation
    if generation_height is not _UNSET:
        _kwargs['generation_height'] = generation_height
    if generation_width is not _UNSET:
        _kwargs['generation_width'] = generation_width
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageResizeToClosest', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoImageToVideoEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    end_latent_strength: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    noise_aug_strength: float | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    start_latent_strength: float | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    add_cond_latents: Any | _Omitted = _UNSET,
    augment_empty_frames: float | _Omitted = _UNSET,
    clip_embeds: Any | _Omitted = _UNSET,
    control_embeds: Any | _Omitted = _UNSET,
    empty_frame_pad_image: Any | _Omitted = _UNSET,
    end_image: Any | _Omitted = _UNSET,
    extra_latents: Any | _Omitted = _UNSET,
    fun_or_fl2v_model: bool | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    temporal_mask: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoImageToVideoEncode``.

    Display name: WanVideo ImageToVideo Encode

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoImageToVideoEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if end_latent_strength is not _UNSET:
        _kwargs['end_latent_strength'] = end_latent_strength
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if height is not _UNSET:
        _kwargs['height'] = height
    if noise_aug_strength is not _UNSET:
        _kwargs['noise_aug_strength'] = noise_aug_strength
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if start_latent_strength is not _UNSET:
        _kwargs['start_latent_strength'] = start_latent_strength
    if width is not _UNSET:
        _kwargs['width'] = width
    if add_cond_latents is not _UNSET:
        _kwargs['add_cond_latents'] = add_cond_latents
    if augment_empty_frames is not _UNSET:
        _kwargs['augment_empty_frames'] = augment_empty_frames
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    if control_embeds is not _UNSET:
        _kwargs['control_embeds'] = control_embeds
    if empty_frame_pad_image is not _UNSET:
        _kwargs['empty_frame_pad_image'] = empty_frame_pad_image
    if end_image is not _UNSET:
        _kwargs['end_image'] = end_image
    if extra_latents is not _UNSET:
        _kwargs['extra_latents'] = extra_latents
    if fun_or_fl2v_model is not _UNSET:
        _kwargs['fun_or_fl2v_model'] = fun_or_fl2v_model
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    if temporal_mask is not _UNSET:
        _kwargs['temporal_mask'] = temporal_mask
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageToVideoEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoImageToVideoMultiTalk(
    *args: VibeWorkflow,
    _id: str | None = None,
    colormatch: Literal['disabled', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    frame_window_size: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    motion_frame: int | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    clip_embeds: Any | _Omitted = _UNSET,
    mode: Literal['auto', 'multitalk', 'infinitetalk'] | _Omitted = _UNSET,
    output_path: str | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoImageToVideoMultiTalk``.

    Display name: WanVideo Long I2V Multi/InfiniteTalk

    Category: WanVideoWrapper

    Enables Multi/InfiniteTalk long video generation sampling method, the video is created in windows with overlapping frames. Not compatible or necessary to be used with context windows and many other features besides Multi/InfiniteTalk.

    Returns: image_embeds, output_path

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoImageToVideoMultiTalk() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if colormatch is not _UNSET:
        _kwargs['colormatch'] = colormatch
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if frame_window_size is not _UNSET:
        _kwargs['frame_window_size'] = frame_window_size
    if height is not _UNSET:
        _kwargs['height'] = height
    if motion_frame is not _UNSET:
        _kwargs['motion_frame'] = motion_frame
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if output_path is not _UNSET:
        _kwargs['output_path'] = output_path
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageToVideoMultiTalk', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoImageToVideoSkyreelsv3_audio(
    *args: VibeWorkflow,
    _id: str | None = None,
    colormatch: Literal['disabled', 'reinhard_torch', 'mkl', 'hm', 'reinhard', 'mvgd', 'hm-mvgd-hm', 'hm-mkl-hm'] | _Omitted = _UNSET,
    drop_frames: int | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    frame_window_size: int | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    motion_frame: int | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    clip_embeds: Any | _Omitted = _UNSET,
    output_path: str | _Omitted = _UNSET,
    reference_video: Any | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoImageToVideoSkyreelsv3_audio``.

    Display name: WanVideo Long SkyReelsV3 A2V

    Category: WanVideoWrapper

    Enables Multi/InfiniteTalk long video generation sampling method, the video is created in windows with overlapping frames. Not compatible or necessary to be used with context windows and many other features besides Multi/InfiniteTalk.

    Returns: image_embeds, output_path

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoImageToVideoSkyreelsv3_audio() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if colormatch is not _UNSET:
        _kwargs['colormatch'] = colormatch
    if drop_frames is not _UNSET:
        _kwargs['drop_frames'] = drop_frames
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if frame_window_size is not _UNSET:
        _kwargs['frame_window_size'] = frame_window_size
    if height is not _UNSET:
        _kwargs['height'] = height
    if motion_frame is not _UNSET:
        _kwargs['motion_frame'] = motion_frame
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if clip_embeds is not _UNSET:
        _kwargs['clip_embeds'] = clip_embeds
    if output_path is not _UNSET:
        _kwargs['output_path'] = output_path
    if reference_video is not _UNSET:
        _kwargs['reference_video'] = reference_video
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoImageToVideoSkyreelsv3_audio', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLatentReScale(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    direction: Literal['comfy_to_wrapper', 'wrapper_to_comfy'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoLatentReScale``.

    Display name: WanVideo Latent ReScale

    Category: WanVideoWrapper

    Rescale latents to match the expected range for encoding or decoding between native ComfyUI VAE and the WanVideoWrapper VAE.

    Returns: samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLatentReScale() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if direction is not _UNSET:
        _kwargs['direction'] = direction
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLatentReScale', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLongCatAvatarExtendEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    prev_latents: Any | _Omitted = _UNSET,
    audio_embeds: Any | _Omitted = _UNSET,
    frames_processed: int | _Omitted = _UNSET,
    if_not_enough_audio: Any | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    overlap: int | _Omitted = _UNSET,
    ref_frame_index: int | _Omitted = _UNSET,
    ref_mask_frame_range: int | _Omitted = _UNSET,
    ref_latent: Any | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoLongCatAvatarExtendEmbeds``.

    Category: WanVideoWrapper

    Returns: image_embeds, samples_slice

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLongCatAvatarExtendEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prev_latents is not _UNSET:
        _kwargs['prev_latents'] = prev_latents
    if audio_embeds is not _UNSET:
        _kwargs['audio_embeds'] = audio_embeds
    if frames_processed is not _UNSET:
        _kwargs['frames_processed'] = frames_processed
    if if_not_enough_audio is not _UNSET:
        _kwargs['if_not_enough_audio'] = if_not_enough_audio
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if overlap is not _UNSET:
        _kwargs['overlap'] = overlap
    if ref_frame_index is not _UNSET:
        _kwargs['ref_frame_index'] = ref_frame_index
    if ref_mask_frame_range is not _UNSET:
        _kwargs['ref_mask_frame_range'] = ref_mask_frame_range
    if ref_latent is not _UNSET:
        _kwargs['ref_latent'] = ref_latent
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLongCatAvatarExtendEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLoopArgs(
    *args: VibeWorkflow,
    _id: str | None = None,
    end_percent: float | _Omitted = _UNSET,
    shift_skip: int | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoLoopArgs``.

    Display name: WanVideo Loop Args

    Category: WanVideoWrapper

    Looping through latent shift as shown in https://github.com/YisuiTT/Mobius/

    Returns: loop_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLoopArgs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if shift_skip is not _UNSET:
        _kwargs['shift_skip'] = shift_skip
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoopArgs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLoraBlockEdit(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks_0: bool | _Omitted = _UNSET,
    blocks_1: bool | _Omitted = _UNSET,
    blocks_10: bool | _Omitted = _UNSET,
    blocks_11: bool | _Omitted = _UNSET,
    blocks_12: bool | _Omitted = _UNSET,
    blocks_13: bool | _Omitted = _UNSET,
    blocks_14: bool | _Omitted = _UNSET,
    blocks_15: bool | _Omitted = _UNSET,
    blocks_16: bool | _Omitted = _UNSET,
    blocks_17: bool | _Omitted = _UNSET,
    blocks_18: bool | _Omitted = _UNSET,
    blocks_19: bool | _Omitted = _UNSET,
    blocks_2: bool | _Omitted = _UNSET,
    blocks_20: bool | _Omitted = _UNSET,
    blocks_21: bool | _Omitted = _UNSET,
    blocks_22: bool | _Omitted = _UNSET,
    blocks_23: bool | _Omitted = _UNSET,
    blocks_24: bool | _Omitted = _UNSET,
    blocks_25: bool | _Omitted = _UNSET,
    blocks_26: bool | _Omitted = _UNSET,
    blocks_27: bool | _Omitted = _UNSET,
    blocks_28: bool | _Omitted = _UNSET,
    blocks_29: bool | _Omitted = _UNSET,
    blocks_3: bool | _Omitted = _UNSET,
    blocks_30: bool | _Omitted = _UNSET,
    blocks_31: bool | _Omitted = _UNSET,
    blocks_32: bool | _Omitted = _UNSET,
    blocks_33: bool | _Omitted = _UNSET,
    blocks_34: bool | _Omitted = _UNSET,
    blocks_35: bool | _Omitted = _UNSET,
    blocks_36: bool | _Omitted = _UNSET,
    blocks_37: bool | _Omitted = _UNSET,
    blocks_38: bool | _Omitted = _UNSET,
    blocks_39: bool | _Omitted = _UNSET,
    blocks_4: bool | _Omitted = _UNSET,
    blocks_5: bool | _Omitted = _UNSET,
    blocks_6: bool | _Omitted = _UNSET,
    blocks_7: bool | _Omitted = _UNSET,
    blocks_8: bool | _Omitted = _UNSET,
    blocks_9: bool | _Omitted = _UNSET,
    layer_filter: str | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoLoraBlockEdit``.

    Display name: WanVideo Lora Block Edit

    Category: WanVideoWrapper

    Returns: blocks

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLoraBlockEdit() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if blocks_0 is not _UNSET:
        _kwargs['blocks.0.'] = blocks_0
    if blocks_1 is not _UNSET:
        _kwargs['blocks.1.'] = blocks_1
    if blocks_10 is not _UNSET:
        _kwargs['blocks.10.'] = blocks_10
    if blocks_11 is not _UNSET:
        _kwargs['blocks.11.'] = blocks_11
    if blocks_12 is not _UNSET:
        _kwargs['blocks.12.'] = blocks_12
    if blocks_13 is not _UNSET:
        _kwargs['blocks.13.'] = blocks_13
    if blocks_14 is not _UNSET:
        _kwargs['blocks.14.'] = blocks_14
    if blocks_15 is not _UNSET:
        _kwargs['blocks.15.'] = blocks_15
    if blocks_16 is not _UNSET:
        _kwargs['blocks.16.'] = blocks_16
    if blocks_17 is not _UNSET:
        _kwargs['blocks.17.'] = blocks_17
    if blocks_18 is not _UNSET:
        _kwargs['blocks.18.'] = blocks_18
    if blocks_19 is not _UNSET:
        _kwargs['blocks.19.'] = blocks_19
    if blocks_2 is not _UNSET:
        _kwargs['blocks.2.'] = blocks_2
    if blocks_20 is not _UNSET:
        _kwargs['blocks.20.'] = blocks_20
    if blocks_21 is not _UNSET:
        _kwargs['blocks.21.'] = blocks_21
    if blocks_22 is not _UNSET:
        _kwargs['blocks.22.'] = blocks_22
    if blocks_23 is not _UNSET:
        _kwargs['blocks.23.'] = blocks_23
    if blocks_24 is not _UNSET:
        _kwargs['blocks.24.'] = blocks_24
    if blocks_25 is not _UNSET:
        _kwargs['blocks.25.'] = blocks_25
    if blocks_26 is not _UNSET:
        _kwargs['blocks.26.'] = blocks_26
    if blocks_27 is not _UNSET:
        _kwargs['blocks.27.'] = blocks_27
    if blocks_28 is not _UNSET:
        _kwargs['blocks.28.'] = blocks_28
    if blocks_29 is not _UNSET:
        _kwargs['blocks.29.'] = blocks_29
    if blocks_3 is not _UNSET:
        _kwargs['blocks.3.'] = blocks_3
    if blocks_30 is not _UNSET:
        _kwargs['blocks.30.'] = blocks_30
    if blocks_31 is not _UNSET:
        _kwargs['blocks.31.'] = blocks_31
    if blocks_32 is not _UNSET:
        _kwargs['blocks.32.'] = blocks_32
    if blocks_33 is not _UNSET:
        _kwargs['blocks.33.'] = blocks_33
    if blocks_34 is not _UNSET:
        _kwargs['blocks.34.'] = blocks_34
    if blocks_35 is not _UNSET:
        _kwargs['blocks.35.'] = blocks_35
    if blocks_36 is not _UNSET:
        _kwargs['blocks.36.'] = blocks_36
    if blocks_37 is not _UNSET:
        _kwargs['blocks.37.'] = blocks_37
    if blocks_38 is not _UNSET:
        _kwargs['blocks.38.'] = blocks_38
    if blocks_39 is not _UNSET:
        _kwargs['blocks.39.'] = blocks_39
    if blocks_4 is not _UNSET:
        _kwargs['blocks.4.'] = blocks_4
    if blocks_5 is not _UNSET:
        _kwargs['blocks.5.'] = blocks_5
    if blocks_6 is not _UNSET:
        _kwargs['blocks.6.'] = blocks_6
    if blocks_7 is not _UNSET:
        _kwargs['blocks.7.'] = blocks_7
    if blocks_8 is not _UNSET:
        _kwargs['blocks.8.'] = blocks_8
    if blocks_9 is not _UNSET:
        _kwargs['blocks.9.'] = blocks_9
    if layer_filter is not _UNSET:
        _kwargs['layer_filter'] = layer_filter
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraBlockEdit', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLoraSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    lora: Literal['ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    low_mem_load: bool | _Omitted = _UNSET,
    merge_loras: bool | _Omitted = _UNSET,
    prev_lora: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoLoraSelect``.

    Display name: WanVideo Lora Select

    Category: WanVideoWrapper

    Select a LoRA model from ComfyUI/models/loras

    Returns: lora

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLoraSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if low_mem_load is not _UNSET:
        _kwargs['low_mem_load'] = low_mem_load
    if merge_loras is not _UNSET:
        _kwargs['merge_loras'] = merge_loras
    if prev_lora is not _UNSET:
        _kwargs['prev_lora'] = prev_lora
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLoraSelectByName(
    *args: VibeWorkflow,
    _id: str | None = None,
    lora_name: str | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    low_mem_load: bool | _Omitted = _UNSET,
    merge_loras: bool | _Omitted = _UNSET,
    prev_lora: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoLoraSelectByName``.

    Display name: WanVideo Lora Select By Name

    Category: WanVideoWrapper

    Select a LoRA model from ComfyUI/models/loras

    Returns: lora

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLoraSelectByName() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if lora_name is not _UNSET:
        _kwargs['lora_name'] = lora_name
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if low_mem_load is not _UNSET:
        _kwargs['low_mem_load'] = low_mem_load
    if merge_loras is not _UNSET:
        _kwargs['merge_loras'] = merge_loras
    if prev_lora is not _UNSET:
        _kwargs['prev_lora'] = prev_lora
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraSelectByName', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoLoraSelectMulti(
    *args: VibeWorkflow,
    _id: str | None = None,
    lora_0: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    lora_1: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    lora_2: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    lora_3: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    lora_4: Literal['none', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'] | _Omitted = _UNSET,
    strength_0: float | _Omitted = _UNSET,
    strength_1: float | _Omitted = _UNSET,
    strength_2: float | _Omitted = _UNSET,
    strength_3: float | _Omitted = _UNSET,
    strength_4: float | _Omitted = _UNSET,
    blocks: Any | _Omitted = _UNSET,
    low_mem_load: bool | _Omitted = _UNSET,
    merge_loras: bool | _Omitted = _UNSET,
    prev_lora: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoLoraSelectMulti``.

    Display name: WanVideo Lora Select Multi

    Category: WanVideoWrapper

    Select a LoRA model from ComfyUI/models/loras

    Returns: lora

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoLoraSelectMulti() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if lora_0 is not _UNSET:
        _kwargs['lora_0'] = lora_0
    if lora_1 is not _UNSET:
        _kwargs['lora_1'] = lora_1
    if lora_2 is not _UNSET:
        _kwargs['lora_2'] = lora_2
    if lora_3 is not _UNSET:
        _kwargs['lora_3'] = lora_3
    if lora_4 is not _UNSET:
        _kwargs['lora_4'] = lora_4
    if strength_0 is not _UNSET:
        _kwargs['strength_0'] = strength_0
    if strength_1 is not _UNSET:
        _kwargs['strength_1'] = strength_1
    if strength_2 is not _UNSET:
        _kwargs['strength_2'] = strength_2
    if strength_3 is not _UNSET:
        _kwargs['strength_3'] = strength_3
    if strength_4 is not _UNSET:
        _kwargs['strength_4'] = strength_4
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if low_mem_load is not _UNSET:
        _kwargs['low_mem_load'] = low_mem_load
    if merge_loras is not _UNSET:
        _kwargs['merge_loras'] = merge_loras
    if prev_lora is not _UNSET:
        _kwargs['prev_lora'] = prev_lora
    _kwargs.update(_extras)
    return node(wf, 'WanVideoLoraSelectMulti', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoMagCache(
    *args: VibeWorkflow,
    _id: str | None = None,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    magcache_K: int | _Omitted = _UNSET,
    magcache_thresh: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoMagCache``.

    Display name: WanVideo MagCache

    Category: WanVideoWrapper

    MagCache for WanVideoWrapper, source https://github.com/Zehong-Ma/MagCache

    Returns: cache_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoMagCache() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cache_device is not _UNSET:
        _kwargs['cache_device'] = cache_device
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if magcache_K is not _UNSET:
        _kwargs['magcache_K'] = magcache_K
    if magcache_thresh is not _UNSET:
        _kwargs['magcache_thresh'] = magcache_thresh
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    _kwargs.update(_extras)
    return node(wf, 'WanVideoMagCache', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoMiniMaxRemoverEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    mask_latents: Any | _Omitted = _UNSET,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoMiniMaxRemoverEmbeds``.

    Display name: WanVideo MiniMax Remover Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoMiniMaxRemoverEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if mask_latents is not _UNSET:
        _kwargs['mask_latents'] = mask_latents
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if width is not _UNSET:
        _kwargs['width'] = width
    _kwargs.update(_extras)
    return node(wf, 'WanVideoMiniMaxRemoverEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_precision: Literal['fp32', 'bf16', 'fp16', 'fp16_fast'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e4m3fn_scaled', 'fp8_e4m3fn_scaled_fast', 'fp8_e5m2', 'fp8_e5m2_fast', 'fp8_e5m2_scaled', 'fp8_e5m2_scaled_fast'] | _Omitted = _UNSET,
    attention_mode: Literal['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled', 'sageattn_ultravico', 'comfy'] | _Omitted = _UNSET,
    block_swap_args: Any | _Omitted = _UNSET,
    compile_args: Any | _Omitted = _UNSET,
    extra_model: Any | _Omitted = _UNSET,
    fantasyportrait_model: Any | _Omitted = _UNSET,
    fantasytalking_model: Any | _Omitted = _UNSET,
    lora: Any | _Omitted = _UNSET,
    multitalk_model: Any | _Omitted = _UNSET,
    rms_norm_function: Literal['default', 'pytorch'] | _Omitted = _UNSET,
    vram_management_args: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoModelLoader``.

    Display name: WanVideo Model Loader

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if model is not _UNSET:
        _kwargs['model'] = model
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    if attention_mode is not _UNSET:
        _kwargs['attention_mode'] = attention_mode
    if block_swap_args is not _UNSET:
        _kwargs['block_swap_args'] = block_swap_args
    if compile_args is not _UNSET:
        _kwargs['compile_args'] = compile_args
    if extra_model is not _UNSET:
        _kwargs['extra_model'] = extra_model
    if fantasyportrait_model is not _UNSET:
        _kwargs['fantasyportrait_model'] = fantasyportrait_model
    if fantasytalking_model is not _UNSET:
        _kwargs['fantasytalking_model'] = fantasytalking_model
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    if multitalk_model is not _UNSET:
        _kwargs['multitalk_model'] = multitalk_model
    if rms_norm_function is not _UNSET:
        _kwargs['rms_norm_function'] = rms_norm_function
    if vram_management_args is not _UNSET:
        _kwargs['vram_management_args'] = vram_management_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoOviCFG(
    *args: VibeWorkflow,
    _id: str | None = None,
    original_text_embeds: Any | _Omitted = _UNSET,
    ovi_audio_cfg: float | _Omitted = _UNSET,
    ovi_negative_text_embeds: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoOviCFG``.

    Display name: WanVideo Ovi CFG

    Category: WanVideoWrapper/Ovi

    Adds Ovi negative text embeddings and audio CFG scale to the text embeddings dictionary

    Returns: text_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoOviCFG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if original_text_embeds is not _UNSET:
        _kwargs['original_text_embeds'] = original_text_embeds
    if ovi_audio_cfg is not _UNSET:
        _kwargs['ovi_audio_cfg'] = ovi_audio_cfg
    if ovi_negative_text_embeds is not _UNSET:
        _kwargs['ovi_negative_text_embeds'] = ovi_negative_text_embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoOviCFG', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoPassImagesFromSamples(
    *args: VibeWorkflow,
    _id: str | None = None,
    samples: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoPassImagesFromSamples``.

    Display name: WanVideo Pass Images From Samples

    Category: WanVideoWrapper

    Gets possible already decoded images from the samples dictionary, used with Multi/InfiniteTalk sampling

    Returns: images, output_path

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoPassImagesFromSamples() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoPassImagesFromSamples', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoPhantomEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    phantom_latent_1: Any | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    phantom_cfg_scale: float | _Omitted = _UNSET,
    phantom_end_percent: float | _Omitted = _UNSET,
    phantom_start_percent: float | _Omitted = _UNSET,
    phantom_latent_2: Any | _Omitted = _UNSET,
    phantom_latent_3: Any | _Omitted = _UNSET,
    phantom_latent_4: Any | _Omitted = _UNSET,
    vace_embeds: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoPhantomEmbeds``.

    Display name: WanVideo Phantom Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoPhantomEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if phantom_latent_1 is not _UNSET:
        _kwargs['phantom_latent_1'] = phantom_latent_1
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if phantom_cfg_scale is not _UNSET:
        _kwargs['phantom_cfg_scale'] = phantom_cfg_scale
    if phantom_end_percent is not _UNSET:
        _kwargs['phantom_end_percent'] = phantom_end_percent
    if phantom_start_percent is not _UNSET:
        _kwargs['phantom_start_percent'] = phantom_start_percent
    if phantom_latent_2 is not _UNSET:
        _kwargs['phantom_latent_2'] = phantom_latent_2
    if phantom_latent_3 is not _UNSET:
        _kwargs['phantom_latent_3'] = phantom_latent_3
    if phantom_latent_4 is not _UNSET:
        _kwargs['phantom_latent_4'] = phantom_latent_4
    if vace_embeds is not _UNSET:
        _kwargs['vace_embeds'] = vace_embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoPhantomEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoPreviewEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    embeds: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoPreviewEmbeds``.

    Display name: WanVideo Preview Embeds

    Category: WanVideoWrapper

    Returns: image_embeds, mask

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoPreviewEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if embeds is not _UNSET:
        _kwargs['embeds'] = embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoPreviewEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoPromptExtender(
    *args: VibeWorkflow,
    _id: str | None = None,
    device: Literal['gpu', 'cpu'] | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    max_new_tokens: int | _Omitted = _UNSET,
    prompt: str | _Omitted = _UNSET,
    qwen: Any | _Omitted = _UNSET,
    custom_system_prompt: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    system_prompt: Literal['T2V Movie Director (Chinese)', 'T2V Movie Director (English)', 'I2V Rewriter (Chinese)', 'I2V Rewriter (English)', 'I2V Imagination (Chinese)', 'I2V Imagination (English)'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoPromptExtender``.

    Display name: Wan Video Prompt Extender

    Category: WanVideoWrapper

    Returns: STRING

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoPromptExtender() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if device is not _UNSET:
        _kwargs['device'] = device
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if qwen is not _UNSET:
        _kwargs['qwen'] = qwen
    if custom_system_prompt is not _UNSET:
        _kwargs['custom_system_prompt'] = custom_system_prompt
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if system_prompt is not _UNSET:
        _kwargs['system_prompt'] = system_prompt
    _kwargs.update(_extras)
    return node(wf, 'WanVideoPromptExtender', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoPromptExtenderSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    max_new_tokens: int | _Omitted = _UNSET,
    model: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    system_prompt: Literal['T2V Movie Director (Chinese)', 'T2V Movie Director (English)', 'I2V Rewriter (Chinese)', 'I2V Rewriter (English)', 'I2V Imagination (Chinese)', 'I2V Imagination (English)'] | _Omitted = _UNSET,
    custom_system_prompt: str | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoPromptExtenderSelect``.

    Display name: Wan Video Prompt Extender Select

    Category: WanVideoWrapper

    Returns: extender_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoPromptExtenderSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if max_new_tokens is not _UNSET:
        _kwargs['max_new_tokens'] = max_new_tokens
    if model is not _UNSET:
        _kwargs['model'] = model
    if system_prompt is not _UNSET:
        _kwargs['system_prompt'] = system_prompt
    if custom_system_prompt is not _UNSET:
        _kwargs['custom_system_prompt'] = custom_system_prompt
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    _kwargs.update(_extras)
    return node(wf, 'WanVideoPromptExtenderSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterCameraEmbed(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    camera_poses: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoReCamMasterCameraEmbed``.

    Display name: WanVideo ReCamMaster Camera Embed

    Category: WanVideoWrapper

    https://github.com/KwaiVGI/ReCamMaster

    Returns: camera_embeds, camera_poses

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoReCamMasterCameraEmbed() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if camera_poses is not _UNSET:
        _kwargs['camera_poses'] = camera_poses
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterCameraEmbed', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterDefaultCamera(
    *args: VibeWorkflow,
    _id: str | None = None,
    latents: Any | _Omitted = _UNSET,
    camera_type: Literal['pan_right', 'pan_left', 'tilt_up', 'tilt_down', 'zoom_in', 'zoom_out', 'translate_up', 'translate_down', 'arc_left', 'arc_right'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoReCamMasterDefaultCamera``.

    Display name: WanVideo ReCamMaster Default Camera

    Category: WanVideoWrapper

    https://github.com/KwaiVGI/ReCamMaster

    Returns: camera_poses

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoReCamMasterDefaultCamera() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if latents is not _UNSET:
        _kwargs['latents'] = latents
    if camera_type is not _UNSET:
        _kwargs['camera_type'] = camera_type
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterDefaultCamera', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoReCamMasterGenerateOrbitCamera(
    *args: VibeWorkflow,
    _id: str | None = None,
    degrees: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoReCamMasterGenerateOrbitCamera``.

    Display name: WanVideo ReCamMaster Generate Orbit Camera

    Category: WanVideoWrapper

    https://github.com/KwaiVGI/ReCamMaster

    Returns: camera_poses

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoReCamMasterGenerateOrbitCamera() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if degrees is not _UNSET:
        _kwargs['degrees'] = degrees
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    _kwargs.update(_extras)
    return node(wf, 'WanVideoReCamMasterGenerateOrbitCamera', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoRealisDanceLatents(
    *args: VibeWorkflow,
    _id: str | None = None,
    ref_latent: Any | _Omitted = _UNSET,
    pose_cond_end_percent: float | _Omitted = _UNSET,
    pose_cond_start_percent: float | _Omitted = _UNSET,
    hamer_latent: Any | _Omitted = _UNSET,
    smpl_latent: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoRealisDanceLatents``.

    Display name: WanVideo RealisDance Latents

    Category: WanVideoWrapper

    Returns: add_cond_latents

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoRealisDanceLatents() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ref_latent is not _UNSET:
        _kwargs['ref_latent'] = ref_latent
    if pose_cond_end_percent is not _UNSET:
        _kwargs['pose_cond_end_percent'] = pose_cond_end_percent
    if pose_cond_start_percent is not _UNSET:
        _kwargs['pose_cond_start_percent'] = pose_cond_start_percent
    if hamer_latent is not _UNSET:
        _kwargs['hamer_latent'] = hamer_latent
    if smpl_latent is not _UNSET:
        _kwargs['smpl_latent'] = smpl_latent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoRealisDanceLatents', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoRoPEFunction(
    *args: VibeWorkflow,
    _id: str | None = None,
    ntk_scale_f: float | _Omitted = _UNSET,
    ntk_scale_h: float | _Omitted = _UNSET,
    ntk_scale_w: float | _Omitted = _UNSET,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoRoPEFunction``.

    Display name: WanVideo RoPE Function

    Category: WanVideoWrapper

    Returns: rope_function

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoRoPEFunction() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if ntk_scale_f is not _UNSET:
        _kwargs['ntk_scale_f'] = ntk_scale_f
    if ntk_scale_h is not _UNSET:
        _kwargs['ntk_scale_h'] = ntk_scale_h
    if ntk_scale_w is not _UNSET:
        _kwargs['ntk_scale_w'] = ntk_scale_w
    if rope_function is not _UNSET:
        _kwargs['rope_function'] = rope_function
    _kwargs.update(_extras)
    return node(wf, 'WanVideoRoPEFunction', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSLG(
    *args: VibeWorkflow,
    _id: str | None = None,
    blocks: str | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSLG``.

    Display name: WanVideo SLG

    Category: WanVideoWrapper

    Skips uncond on the selected blocks

    Returns: slg_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSLG() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSLG', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSVIProEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    anchor_samples: Any | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    motion_latent_count: int | _Omitted = _UNSET,
    prev_samples: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSVIProEmbeds``.

    Display name: WanVideo SVIPro Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSVIProEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if anchor_samples is not _UNSET:
        _kwargs['anchor_samples'] = anchor_samples
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if motion_latent_count is not _UNSET:
        _kwargs['motion_latent_count'] = motion_latent_count
    if prev_samples is not _UNSET:
        _kwargs['prev_samples'] = prev_samples
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSVIProEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSampler(
    *args: VibeWorkflow,
    _id: str | None = None,
    cfg: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    image_embeds: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    riflex_freq_index: int | _Omitted = _UNSET,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    add_noise_to_samples: bool | _Omitted = _UNSET,
    batched_cfg: bool | _Omitted = _UNSET,
    cache_args: Any | _Omitted = _UNSET,
    context_options: Any | _Omitted = _UNSET,
    denoise_strength: float | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    experimental_args: Any | _Omitted = _UNSET,
    fantasytalking_embeds: Any | _Omitted = _UNSET,
    feta_args: Any | _Omitted = _UNSET,
    flowedit_args: Any | _Omitted = _UNSET,
    freeinit_args: Any | _Omitted = _UNSET,
    loop_args: Any | _Omitted = _UNSET,
    multitalk_embeds: Any | _Omitted = _UNSET,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    slg_args: Any | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    text_embeds: Any | _Omitted = _UNSET,
    uni3c_embeds: Any | _Omitted = _UNSET,
    unianimate_poses: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSampler``.

    Display name: WanVideo Sampler

    Category: WanVideoWrapper

    Returns: samples, denoised_samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSampler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if image_embeds is not _UNSET:
        _kwargs['image_embeds'] = image_embeds
    if model is not _UNSET:
        _kwargs['model'] = model
    if riflex_freq_index is not _UNSET:
        _kwargs['riflex_freq_index'] = riflex_freq_index
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if add_noise_to_samples is not _UNSET:
        _kwargs['add_noise_to_samples'] = add_noise_to_samples
    if batched_cfg is not _UNSET:
        _kwargs['batched_cfg'] = batched_cfg
    if cache_args is not _UNSET:
        _kwargs['cache_args'] = cache_args
    if context_options is not _UNSET:
        _kwargs['context_options'] = context_options
    if denoise_strength is not _UNSET:
        _kwargs['denoise_strength'] = denoise_strength
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if experimental_args is not _UNSET:
        _kwargs['experimental_args'] = experimental_args
    if fantasytalking_embeds is not _UNSET:
        _kwargs['fantasytalking_embeds'] = fantasytalking_embeds
    if feta_args is not _UNSET:
        _kwargs['feta_args'] = feta_args
    if flowedit_args is not _UNSET:
        _kwargs['flowedit_args'] = flowedit_args
    if freeinit_args is not _UNSET:
        _kwargs['freeinit_args'] = freeinit_args
    if loop_args is not _UNSET:
        _kwargs['loop_args'] = loop_args
    if multitalk_embeds is not _UNSET:
        _kwargs['multitalk_embeds'] = multitalk_embeds
    if rope_function is not _UNSET:
        _kwargs['rope_function'] = rope_function
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if slg_args is not _UNSET:
        _kwargs['slg_args'] = slg_args
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if text_embeds is not _UNSET:
        _kwargs['text_embeds'] = text_embeds
    if uni3c_embeds is not _UNSET:
        _kwargs['uni3c_embeds'] = uni3c_embeds
    if unianimate_poses is not _UNSET:
        _kwargs['unianimate_poses'] = unianimate_poses
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSampler', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSamplerExtraArgs(
    *args: VibeWorkflow,
    _id: str | None = None,
    cache_args: Any | _Omitted = _UNSET,
    context_options: Any | _Omitted = _UNSET,
    experimental_args: Any | _Omitted = _UNSET,
    fantasytalking_embeds: Any | _Omitted = _UNSET,
    feta_args: Any | _Omitted = _UNSET,
    loop_args: Any | _Omitted = _UNSET,
    multitalk_embeds: Any | _Omitted = _UNSET,
    riflex_freq_index: int | _Omitted = _UNSET,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = _UNSET,
    slg_args: Any | _Omitted = _UNSET,
    uni3c_embeds: Any | _Omitted = _UNSET,
    unianimate_poses: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSamplerExtraArgs``.

    Display name: WanVideoSampler v2 Extra Args

    Category: WanVideoWrapper

    Returns: extra_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSamplerExtraArgs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cache_args is not _UNSET:
        _kwargs['cache_args'] = cache_args
    if context_options is not _UNSET:
        _kwargs['context_options'] = context_options
    if experimental_args is not _UNSET:
        _kwargs['experimental_args'] = experimental_args
    if fantasytalking_embeds is not _UNSET:
        _kwargs['fantasytalking_embeds'] = fantasytalking_embeds
    if feta_args is not _UNSET:
        _kwargs['feta_args'] = feta_args
    if loop_args is not _UNSET:
        _kwargs['loop_args'] = loop_args
    if multitalk_embeds is not _UNSET:
        _kwargs['multitalk_embeds'] = multitalk_embeds
    if riflex_freq_index is not _UNSET:
        _kwargs['riflex_freq_index'] = riflex_freq_index
    if rope_function is not _UNSET:
        _kwargs['rope_function'] = rope_function
    if slg_args is not _UNSET:
        _kwargs['slg_args'] = slg_args
    if uni3c_embeds is not _UNSET:
        _kwargs['uni3c_embeds'] = uni3c_embeds
    if unianimate_poses is not _UNSET:
        _kwargs['unianimate_poses'] = unianimate_poses
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSamplerExtraArgs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSamplerFromSettings(
    *args: VibeWorkflow,
    _id: str | None = None,
    sampler_inputs: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSamplerFromSettings``.

    Display name: WanVideo Sampler From Settings

    Category: WanVideoWrapper

    Utility node with no other functionality than to look cleaner, useful for the live preview as the main sampler node has become a messy monster

    Returns: samples, denoised_samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSamplerFromSettings() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sampler_inputs is not _UNSET:
        _kwargs['sampler_inputs'] = sampler_inputs
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSamplerFromSettings', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSamplerSettings(
    *args: VibeWorkflow,
    _id: str | None = None,
    cfg: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    image_embeds: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    riflex_freq_index: int | _Omitted = _UNSET,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    add_noise_to_samples: bool | _Omitted = _UNSET,
    batched_cfg: bool | _Omitted = _UNSET,
    cache_args: Any | _Omitted = _UNSET,
    context_options: Any | _Omitted = _UNSET,
    denoise_strength: float | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    experimental_args: Any | _Omitted = _UNSET,
    fantasytalking_embeds: Any | _Omitted = _UNSET,
    feta_args: Any | _Omitted = _UNSET,
    flowedit_args: Any | _Omitted = _UNSET,
    freeinit_args: Any | _Omitted = _UNSET,
    loop_args: Any | _Omitted = _UNSET,
    multitalk_embeds: Any | _Omitted = _UNSET,
    rope_function: Literal['default', 'comfy', 'comfy_chunked'] | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    slg_args: Any | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    text_embeds: Any | _Omitted = _UNSET,
    uni3c_embeds: Any | _Omitted = _UNSET,
    unianimate_poses: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSamplerSettings``.

    Display name: WanVideo Sampler Settings

    Category: WanVideoWrapper

    Node to output all settings and inputs for the WanVideoSamplerFromSettings -node

    Returns: sampler_inputs

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSamplerSettings() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if image_embeds is not _UNSET:
        _kwargs['image_embeds'] = image_embeds
    if model is not _UNSET:
        _kwargs['model'] = model
    if riflex_freq_index is not _UNSET:
        _kwargs['riflex_freq_index'] = riflex_freq_index
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if add_noise_to_samples is not _UNSET:
        _kwargs['add_noise_to_samples'] = add_noise_to_samples
    if batched_cfg is not _UNSET:
        _kwargs['batched_cfg'] = batched_cfg
    if cache_args is not _UNSET:
        _kwargs['cache_args'] = cache_args
    if context_options is not _UNSET:
        _kwargs['context_options'] = context_options
    if denoise_strength is not _UNSET:
        _kwargs['denoise_strength'] = denoise_strength
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if experimental_args is not _UNSET:
        _kwargs['experimental_args'] = experimental_args
    if fantasytalking_embeds is not _UNSET:
        _kwargs['fantasytalking_embeds'] = fantasytalking_embeds
    if feta_args is not _UNSET:
        _kwargs['feta_args'] = feta_args
    if flowedit_args is not _UNSET:
        _kwargs['flowedit_args'] = flowedit_args
    if freeinit_args is not _UNSET:
        _kwargs['freeinit_args'] = freeinit_args
    if loop_args is not _UNSET:
        _kwargs['loop_args'] = loop_args
    if multitalk_embeds is not _UNSET:
        _kwargs['multitalk_embeds'] = multitalk_embeds
    if rope_function is not _UNSET:
        _kwargs['rope_function'] = rope_function
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    if slg_args is not _UNSET:
        _kwargs['slg_args'] = slg_args
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if text_embeds is not _UNSET:
        _kwargs['text_embeds'] = text_embeds
    if uni3c_embeds is not _UNSET:
        _kwargs['uni3c_embeds'] = uni3c_embeds
    if unianimate_poses is not _UNSET:
        _kwargs['unianimate_poses'] = unianimate_poses
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSamplerSettings', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSamplerv2(
    *args: VibeWorkflow,
    _id: str | None = None,
    cfg: float | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    image_embeds: Any | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    scheduler: Any | _Omitted = _UNSET,
    seed: int | _Omitted = _UNSET,
    add_noise_to_samples: bool | _Omitted = _UNSET,
    extra_args: Any | _Omitted = _UNSET,
    samples: Any | _Omitted = _UNSET,
    text_embeds: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSamplerv2``.

    Display name: WanVideo Sampler v2

    Category: WanVideoWrapper

    Returns: samples, denoised_samples

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSamplerv2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cfg is not _UNSET:
        _kwargs['cfg'] = cfg
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if image_embeds is not _UNSET:
        _kwargs['image_embeds'] = image_embeds
    if model is not _UNSET:
        _kwargs['model'] = model
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if seed is not _UNSET:
        _kwargs['seed'] = seed
    if add_noise_to_samples is not _UNSET:
        _kwargs['add_noise_to_samples'] = add_noise_to_samples
    if extra_args is not _UNSET:
        _kwargs['extra_args'] = extra_args
    if samples is not _UNSET:
        _kwargs['samples'] = samples
    if text_embeds is not _UNSET:
        _kwargs['text_embeds'] = text_embeds
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSamplerv2', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoScheduler(
    *args: VibeWorkflow,
    _id: str | None = None,
    end_step: int | _Omitted = _UNSET,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    enhance_hf: bool | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoScheduler``.

    Display name: WanVideo Scheduler

    Category: WanVideoWrapper

    Returns: sigmas, steps, shift, scheduler, start_step, end_step

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoScheduler() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if enhance_hf is not _UNSET:
        _kwargs['enhance_hf'] = enhance_hf
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    _kwargs.update(_extras)
    return node(wf, 'WanVideoScheduler', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSchedulerv2(
    *args: VibeWorkflow,
    _id: str | None = None,
    end_step: int | _Omitted = _UNSET,
    scheduler: Literal['unipc', 'unipc/beta', 'dpm++', 'dpm++/beta', 'dpm++_sde', 'dpm++_sde/beta', 'euler', 'euler/beta', 'longcat_distill_euler', 'deis', 'lcm', 'lcm/beta', 'res_multistep', 'er_sde', 'flowmatch_causvid', 'flowmatch_distill', 'flowmatch_pusa', 'multitalk', 'sa_ode_stable', 'rcm', 'vibt_unipc'] | _Omitted = _UNSET,
    shift: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    steps: int | _Omitted = _UNSET,
    enhance_hf: bool | _Omitted = _UNSET,
    sigmas: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSchedulerv2``.

    Display name: WanVideo Scheduler v2

    Category: WanVideoWrapper

    Returns: scheduler

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSchedulerv2() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if scheduler is not _UNSET:
        _kwargs['scheduler'] = scheduler
    if shift is not _UNSET:
        _kwargs['shift'] = shift
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if steps is not _UNSET:
        _kwargs['steps'] = steps
    if enhance_hf is not _UNSET:
        _kwargs['enhance_hf'] = enhance_hf
    if sigmas is not _UNSET:
        _kwargs['sigmas'] = sigmas
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSchedulerv2', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSetAttentionModeOverride(
    *args: VibeWorkflow,
    _id: str | None = None,
    attention_mode: Literal['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled', 'sageattn_ultravico', 'comfy'] | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    verbose: bool | _Omitted = _UNSET,
    blocks: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSetAttentionModeOverride``.

    Display name: WanVideo Set Attention Mode Override

    Category: WanVideoWrapper

    Override the attention mode for the model for specific step and/or block range

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSetAttentionModeOverride() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if attention_mode is not _UNSET:
        _kwargs['attention_mode'] = attention_mode
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if model is not _UNSET:
        _kwargs['model'] = model
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if verbose is not _UNSET:
        _kwargs['verbose'] = verbose
    if blocks is not _UNSET:
        _kwargs['blocks'] = blocks
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetAttentionModeOverride', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSetBlockSwap(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    block_swap_args: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSetBlockSwap``.

    Display name: WanVideo Set BlockSwap

    Category: WanVideoWrapper

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSetBlockSwap() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if block_swap_args is not _UNSET:
        _kwargs['block_swap_args'] = block_swap_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetBlockSwap', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSetLoRAs(
    *args: VibeWorkflow,
    _id: str | None = None,
    model: Any | _Omitted = _UNSET,
    lora: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSetLoRAs``.

    Display name: WanVideo Set LoRAs

    Category: WanVideoWrapper

    Sets the LoRA weights to be used directly in linear layers of the model, this does NOT merge LoRAs

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSetLoRAs() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model is not _UNSET:
        _kwargs['model'] = model
    if lora is not _UNSET:
        _kwargs['lora'] = lora
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetLoRAs', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSetRadialAttention(
    *args: VibeWorkflow,
    _id: str | None = None,
    block_size: Literal['128', '64'] | _Omitted = _UNSET,
    decay_factor: float | _Omitted = _UNSET,
    dense_attention_mode: Literal['sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn', 'sparse_sage_attention'] | _Omitted = _UNSET,
    dense_blocks: int | _Omitted = _UNSET,
    dense_timesteps: int | _Omitted = _UNSET,
    dense_vace_blocks: int | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSetRadialAttention``.

    Display name: WanVideo Set Radial Attention

    Category: WanVideoWrapper

    Sets radial attention parameters, dense attention refers to normal attention

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSetRadialAttention() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if block_size is not _UNSET:
        _kwargs['block_size'] = block_size
    if decay_factor is not _UNSET:
        _kwargs['decay_factor'] = decay_factor
    if dense_attention_mode is not _UNSET:
        _kwargs['dense_attention_mode'] = dense_attention_mode
    if dense_blocks is not _UNSET:
        _kwargs['dense_blocks'] = dense_blocks
    if dense_timesteps is not _UNSET:
        _kwargs['dense_timesteps'] = dense_timesteps
    if dense_vace_blocks is not _UNSET:
        _kwargs['dense_vace_blocks'] = dense_vace_blocks
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSetRadialAttention', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoSigmaToStep(
    *args: VibeWorkflow,
    _id: str | None = None,
    sigma: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoSigmaToStep``.

    Display name: WanVideo Sigma To Step

    Category: WanVideoWrapper

    Simply passes a float value as an integer, used to set start/end steps with sigma threshold

    Returns: step

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoSigmaToStep() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if sigma is not _UNSET:
        _kwargs['sigma'] = sigma
    _kwargs.update(_extras)
    return node(wf, 'WanVideoSigmaToStep', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTeaCache(
    *args: VibeWorkflow,
    _id: str | None = None,
    cache_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    end_step: int | _Omitted = _UNSET,
    rel_l1_thresh: float | _Omitted = _UNSET,
    start_step: int | _Omitted = _UNSET,
    use_coefficients: bool | _Omitted = _UNSET,
    mode: Literal['e', 'e0'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoTeaCache``.

    Display name: WanVideo TeaCache

    Category: WanVideoWrapper

    Patch WanVideo model to use TeaCache. Speeds up inference by caching the output and

    Returns: cache_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTeaCache() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if cache_device is not _UNSET:
        _kwargs['cache_device'] = cache_device
    if end_step is not _UNSET:
        _kwargs['end_step'] = end_step
    if rel_l1_thresh is not _UNSET:
        _kwargs['rel_l1_thresh'] = rel_l1_thresh
    if start_step is not _UNSET:
        _kwargs['start_step'] = start_step
    if use_coefficients is not _UNSET:
        _kwargs['use_coefficients'] = use_coefficients
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTeaCache', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEmbedBridge(
    *args: VibeWorkflow,
    _id: str | None = None,
    positive: Any | _Omitted = _UNSET,
    negative: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoTextEmbedBridge``.

    Display name: WanVideo TextEmbed Bridge

    Category: WanVideoWrapper

    Bridge between ComfyUI native text embedding and WanVideoWrapper text embedding

    Returns: text_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTextEmbedBridge() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if positive is not _UNSET:
        _kwargs['positive'] = positive
    if negative is not _UNSET:
        _kwargs['negative'] = negative
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEmbedBridge', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    negative_prompt: str | _Omitted = _UNSET,
    positive_prompt: str | _Omitted = _UNSET,
    device: Literal['gpu', 'cpu'] | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    model_to_offload: Any | _Omitted = _UNSET,
    t5: Any | _Omitted = _UNSET,
    use_disk_cache: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoTextEncode``.

    Display name: WanVideo TextEncode

    Category: WanVideoWrapper

    Encodes text prompts into text embeddings. For rudimentary prompt travel you can input multiple prompts separated by '|', they will be equally spread over the video length

    Returns: text_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTextEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if negative_prompt is not _UNSET:
        _kwargs['negative_prompt'] = negative_prompt
    if positive_prompt is not _UNSET:
        _kwargs['positive_prompt'] = positive_prompt
    if device is not _UNSET:
        _kwargs['device'] = device
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if model_to_offload is not _UNSET:
        _kwargs['model_to_offload'] = model_to_offload
    if t5 is not _UNSET:
        _kwargs['t5'] = t5
    if use_disk_cache is not _UNSET:
        _kwargs['use_disk_cache'] = use_disk_cache
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncodeCached(
    *args: VibeWorkflow,
    _id: str | None = None,
    device: Literal['gpu', 'cpu'] | _Omitted = _UNSET,
    model_name: Literal['gemma_3_12B_it_fp4_mixed.safetensors', 'ltx-2.3_text_projection_bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors'] | _Omitted = _UNSET,
    negative_prompt: str | _Omitted = _UNSET,
    positive_prompt: str | _Omitted = _UNSET,
    precision: Literal['fp32', 'bf16'] | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn'] | _Omitted = _UNSET,
    use_disk_cache: bool | _Omitted = _UNSET,
    extender_args: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoTextEncodeCached``.

    Display name: WanVideo TextEncode Cached

    Category: WanVideoWrapper

    Encodes text prompts into text embeddings. This node loads and completely unloads the T5 after done,

    Returns: text_embeds, negative_text_embeds, positive_prompt

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTextEncodeCached() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if device is not _UNSET:
        _kwargs['device'] = device
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if negative_prompt is not _UNSET:
        _kwargs['negative_prompt'] = negative_prompt
    if positive_prompt is not _UNSET:
        _kwargs['positive_prompt'] = positive_prompt
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    if use_disk_cache is not _UNSET:
        _kwargs['use_disk_cache'] = use_disk_cache
    if extender_args is not _UNSET:
        _kwargs['extender_args'] = extender_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEncodeCached', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTextEncodeSingle(
    *args: VibeWorkflow,
    _id: str | None = None,
    prompt: str | _Omitted = _UNSET,
    device: Literal['gpu', 'cpu'] | _Omitted = _UNSET,
    force_offload: bool | _Omitted = _UNSET,
    model_to_offload: Any | _Omitted = _UNSET,
    t5: Any | _Omitted = _UNSET,
    use_disk_cache: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoTextEncodeSingle``.

    Display name: WanVideo TextEncodeSingle

    Category: WanVideoWrapper

    Encodes text prompt into text embedding.

    Returns: text_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTextEncodeSingle() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if prompt is not _UNSET:
        _kwargs['prompt'] = prompt
    if device is not _UNSET:
        _kwargs['device'] = device
    if force_offload is not _UNSET:
        _kwargs['force_offload'] = force_offload
    if model_to_offload is not _UNSET:
        _kwargs['model_to_offload'] = model_to_offload
    if t5 is not _UNSET:
        _kwargs['t5'] = t5
    if use_disk_cache is not _UNSET:
        _kwargs['use_disk_cache'] = use_disk_cache
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTextEncodeSingle', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTinyVAELoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Any | _Omitted = _UNSET,
    parallel: bool | _Omitted = _UNSET,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoTinyVAELoader``.

    Display name: WanVideo Tiny VAE Loader

    Category: WanVideoWrapper

    Loads Wan VAE model from 'ComfyUI/models/vae_approx'

    Returns: vae

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTinyVAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if parallel is not _UNSET:
        _kwargs['parallel'] = parallel
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTinyVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoTorchCompileSettings(
    *args: VibeWorkflow,
    _id: str | None = None,
    backend: Literal['inductor', 'cudagraphs'] | _Omitted = _UNSET,
    compile_transformer_blocks_only: bool | _Omitted = _UNSET,
    dynamic: bool | _Omitted = _UNSET,
    dynamo_cache_size_limit: int | _Omitted = _UNSET,
    fullgraph: bool | _Omitted = _UNSET,
    mode: Literal['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'] | _Omitted = _UNSET,
    allow_unmerged_lora_compile: bool | _Omitted = _UNSET,
    dynamo_recompile_limit: int | _Omitted = _UNSET,
    force_parameter_static_shapes: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoTorchCompileSettings``.

    Display name: WanVideo Torch Compile Settings

    Category: WanVideoWrapper

    torch.compile settings, when connected to the model loader, torch.compile of the selected layers is attempted. Requires Triton and torch > 2.7.0 is recommended

    Returns: torch_compile_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoTorchCompileSettings() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if backend is not _UNSET:
        _kwargs['backend'] = backend
    if compile_transformer_blocks_only is not _UNSET:
        _kwargs['compile_transformer_blocks_only'] = compile_transformer_blocks_only
    if dynamic is not _UNSET:
        _kwargs['dynamic'] = dynamic
    if dynamo_cache_size_limit is not _UNSET:
        _kwargs['dynamo_cache_size_limit'] = dynamo_cache_size_limit
    if fullgraph is not _UNSET:
        _kwargs['fullgraph'] = fullgraph
    if mode is not _UNSET:
        _kwargs['mode'] = mode
    if allow_unmerged_lora_compile is not _UNSET:
        _kwargs['allow_unmerged_lora_compile'] = allow_unmerged_lora_compile
    if dynamo_recompile_limit is not _UNSET:
        _kwargs['dynamo_recompile_limit'] = dynamo_recompile_limit
    if force_parameter_static_shapes is not _UNSET:
        _kwargs['force_parameter_static_shapes'] = force_parameter_static_shapes
    _kwargs.update(_extras)
    return node(wf, 'WanVideoTorchCompileSettings', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoUltraVicoSettings(
    *args: VibeWorkflow,
    _id: str | None = None,
    alpha: float | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoUltraVicoSettings``.

    Display name: WanVideo UltraVico Settings

    Category: WanVideoWrapper

    Set UltraVico parameters, attention mode still needs to be set to sageattn_ultravico, https://github.com/thu-ml/DiT-Extrapolation

    Returns: model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoUltraVicoSettings() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if alpha is not _UNSET:
        _kwargs['alpha'] = alpha
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoUltraVicoSettings', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoUni3C_ControlnetLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    attention_mode: Literal['sdpa', 'sageattn'] | _Omitted = _UNSET,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    quantization: Literal['disabled', 'fp8_e4m3fn', 'fp8_e5m2'] | _Omitted = _UNSET,
    compile_args: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoUni3C_ControlnetLoader``.

    Display name: WanVideo Uni3C Controlnet Loader

    Category: WanVideoWrapper

    Returns: controlnet

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoUni3C_ControlnetLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if attention_mode is not _UNSET:
        _kwargs['attention_mode'] = attention_mode
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if model is not _UNSET:
        _kwargs['model'] = model
    if quantization is not _UNSET:
        _kwargs['quantization'] = quantization
    if compile_args is not _UNSET:
        _kwargs['compile_args'] = compile_args
    _kwargs.update(_extras)
    return node(wf, 'WanVideoUni3C_ControlnetLoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoUni3C_embeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    controlnet: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    offload: bool | _Omitted = _UNSET,
    render_latent: Any | _Omitted = _UNSET,
    render_mask: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoUni3C_embeds``.

    Display name: WanVideo Uni3C Embeds

    Category: WanVideoWrapper

    Returns: uni3c_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoUni3C_embeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if controlnet is not _UNSET:
        _kwargs['controlnet'] = controlnet
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if offload is not _UNSET:
        _kwargs['offload'] = offload
    if render_latent is not _UNSET:
        _kwargs['render_latent'] = render_latent
    if render_mask is not _UNSET:
        _kwargs['render_mask'] = render_mask
    _kwargs.update(_extras)
    return node(wf, 'WanVideoUni3C_embeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoUniAnimateDWPoseDetector(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_images: Any | _Omitted = _UNSET,
    body_keypoint_size: int | _Omitted = _UNSET,
    colorspace: Literal['RGB', 'BGR'] | _Omitted = _UNSET,
    draw_body: bool | _Omitted = _UNSET,
    draw_feet: bool | _Omitted = _UNSET,
    draw_hands: bool | _Omitted = _UNSET,
    draw_head: bool | _Omitted = _UNSET,
    hand_keypoint_size: int | _Omitted = _UNSET,
    handle_not_detected: Literal['empty', 'repeat'] | _Omitted = _UNSET,
    score_threshold: float | _Omitted = _UNSET,
    stick_width: int | _Omitted = _UNSET,
    reference_pose_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoUniAnimateDWPoseDetector``.

    Display name: WanVideo UniAnimate DWPose Detector

    Category: WanVideoWrapper

    Returns: poses, reference_pose

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoUniAnimateDWPoseDetector() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_images is not _UNSET:
        _kwargs['pose_images'] = pose_images
    if body_keypoint_size is not _UNSET:
        _kwargs['body_keypoint_size'] = body_keypoint_size
    if colorspace is not _UNSET:
        _kwargs['colorspace'] = colorspace
    if draw_body is not _UNSET:
        _kwargs['draw_body'] = draw_body
    if draw_feet is not _UNSET:
        _kwargs['draw_feet'] = draw_feet
    if draw_hands is not _UNSET:
        _kwargs['draw_hands'] = draw_hands
    if draw_head is not _UNSET:
        _kwargs['draw_head'] = draw_head
    if hand_keypoint_size is not _UNSET:
        _kwargs['hand_keypoint_size'] = hand_keypoint_size
    if handle_not_detected is not _UNSET:
        _kwargs['handle_not_detected'] = handle_not_detected
    if score_threshold is not _UNSET:
        _kwargs['score_threshold'] = score_threshold
    if stick_width is not _UNSET:
        _kwargs['stick_width'] = stick_width
    if reference_pose_image is not _UNSET:
        _kwargs['reference_pose_image'] = reference_pose_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoUniAnimateDWPoseDetector', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoUniAnimatePoseInput(
    *args: VibeWorkflow,
    _id: str | None = None,
    pose_images: Any | _Omitted = _UNSET,
    end_percent: float | _Omitted = _UNSET,
    start_percent: float | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    reference_pose_image: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoUniAnimatePoseInput``.

    Display name: WanVideo UniAnimate Pose Input

    Category: WanVideoWrapper

    Returns: unianimate_poses

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoUniAnimatePoseInput() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if pose_images is not _UNSET:
        _kwargs['pose_images'] = pose_images
    if end_percent is not _UNSET:
        _kwargs['end_percent'] = end_percent
    if start_percent is not _UNSET:
        _kwargs['start_percent'] = start_percent
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if reference_pose_image is not _UNSET:
        _kwargs['reference_pose_image'] = reference_pose_image
    _kwargs.update(_extras)
    return node(wf, 'WanVideoUniAnimatePoseInput', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoUniLumosEmbeds(
    *args: VibeWorkflow,
    _id: str | None = None,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    background_latents: Any | _Omitted = _UNSET,
    foreground_latents: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoUniLumosEmbeds``.

    Display name: WanVideo UniLumos Embeds

    Category: WanVideoWrapper

    Returns: image_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoUniLumosEmbeds() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if width is not _UNSET:
        _kwargs['width'] = width
    if background_latents is not _UNSET:
        _kwargs['background_latents'] = background_latents
    if foreground_latents is not _UNSET:
        _kwargs['foreground_latents'] = foreground_latents
    _kwargs.update(_extras)
    return node(wf, 'WanVideoUniLumosEmbeds', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVACEEncode(
    *args: VibeWorkflow,
    _id: str | None = None,
    height: int | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    strength: float | _Omitted = _UNSET,
    vace_end_percent: float | _Omitted = _UNSET,
    vace_start_percent: float | _Omitted = _UNSET,
    vae: Any | _Omitted = _UNSET,
    width: int | _Omitted = _UNSET,
    input_frames: Any | _Omitted = _UNSET,
    input_masks: Any | _Omitted = _UNSET,
    prev_vace_embeds: Any | _Omitted = _UNSET,
    ref_images: Any | _Omitted = _UNSET,
    tiled_vae: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoVACEEncode``.

    Display name: WanVideo VACE Encode

    Category: WanVideoWrapper

    Returns: vace_embeds

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVACEEncode() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if height is not _UNSET:
        _kwargs['height'] = height
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if strength is not _UNSET:
        _kwargs['strength'] = strength
    if vace_end_percent is not _UNSET:
        _kwargs['vace_end_percent'] = vace_end_percent
    if vace_start_percent is not _UNSET:
        _kwargs['vace_start_percent'] = vace_start_percent
    if vae is not _UNSET:
        _kwargs['vae'] = vae
    if width is not _UNSET:
        _kwargs['width'] = width
    if input_frames is not _UNSET:
        _kwargs['input_frames'] = input_frames
    if input_masks is not _UNSET:
        _kwargs['input_masks'] = input_masks
    if prev_vace_embeds is not _UNSET:
        _kwargs['prev_vace_embeds'] = prev_vace_embeds
    if ref_images is not _UNSET:
        _kwargs['ref_images'] = ref_images
    if tiled_vae is not _UNSET:
        _kwargs['tiled_vae'] = tiled_vae
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEEncode', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVACEModelSelect(
    *args: VibeWorkflow,
    _id: str | None = None,
    vace_model: Literal['ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'] | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoVACEModelSelect``.

    Display name: WanVideo VACE Module Select

    Category: WanVideoWrapper

    VACE model to use when not using model that has it included, loaded from 'ComfyUI/models/diffusion_models'

    Returns: extra_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVACEModelSelect() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if vace_model is not _UNSET:
        _kwargs['vace_model'] = vace_model
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEModelSelect', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVACEStartToEndFrame(
    *args: VibeWorkflow,
    _id: str | None = None,
    empty_frame_level: float | _Omitted = _UNSET,
    num_frames: int | _Omitted = _UNSET,
    control_images: Any | _Omitted = _UNSET,
    end_image: Any | _Omitted = _UNSET,
    end_index: int | _Omitted = _UNSET,
    inpaint_mask: Any | _Omitted = _UNSET,
    start_image: Any | _Omitted = _UNSET,
    start_index: int | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoVACEStartToEndFrame``.

    Display name: WanVideo VACE Start To End Frame

    Category: WanVideoWrapper

    Helper node to create start/end frame batch and masks for VACE

    Returns: images, masks

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVACEStartToEndFrame() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if empty_frame_level is not _UNSET:
        _kwargs['empty_frame_level'] = empty_frame_level
    if num_frames is not _UNSET:
        _kwargs['num_frames'] = num_frames
    if control_images is not _UNSET:
        _kwargs['control_images'] = control_images
    if end_image is not _UNSET:
        _kwargs['end_image'] = end_image
    if end_index is not _UNSET:
        _kwargs['end_index'] = end_index
    if inpaint_mask is not _UNSET:
        _kwargs['inpaint_mask'] = inpaint_mask
    if start_image is not _UNSET:
        _kwargs['start_image'] = start_image
    if start_index is not _UNSET:
        _kwargs['start_index'] = start_index
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVACEStartToEndFrame', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVAELoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    model_name: Literal['taeltx2_3.safetensors', 'LTX23_video_vae_bf16.safetensors', 'wanvideo/Wan2_1_VAE_bf16.safetensors'] | _Omitted = _UNSET,
    compile_args: Any | _Omitted = _UNSET,
    precision: Literal['fp16', 'fp32', 'bf16'] | _Omitted = _UNSET,
    use_cpu_cache: bool | _Omitted = _UNSET,
    verbose: bool | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoVAELoader``.

    Display name: WanVideo VAE Loader

    Category: WanVideoWrapper

    Loads Wan VAE model from 'ComfyUI/models/vae'

    Returns: vae

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVAELoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if model_name is not _UNSET:
        _kwargs['model_name'] = model_name
    if compile_args is not _UNSET:
        _kwargs['compile_args'] = compile_args
    if precision is not _UNSET:
        _kwargs['precision'] = precision
    if use_cpu_cache is not _UNSET:
        _kwargs['use_cpu_cache'] = use_cpu_cache
    if verbose is not _UNSET:
        _kwargs['verbose'] = verbose
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVAELoader', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoVRAMManagement(
    *args: VibeWorkflow,
    _id: str | None = None,
    offload_percent: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoVRAMManagement``.

    Display name: WanVideo VRAM Management

    Category: WanVideoWrapper

    Alternative offloading method from DiffSynth-Studio, more aggressive in reducing memory use than block swapping, but can be slower

    Returns: vram_management_args

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoVRAMManagement() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if offload_percent is not _UNSET:
        _kwargs['offload_percent'] = offload_percent
    _kwargs.update(_extras)
    return node(wf, 'WanVideoVRAMManagement', _id, pass_raw=pass_raw, **_kwargs)

def WanVideoWanDrawWanMoveTracks(
    *args: VibeWorkflow,
    _id: str | None = None,
    images: Any | _Omitted = _UNSET,
    tracks: Any | _Omitted = _UNSET,
    circle_size: int | _Omitted = _UNSET,
    line_resolution: int | _Omitted = _UNSET,
    line_width: int | _Omitted = _UNSET,
    opacity: float | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WanVideoWanDrawWanMoveTracks``.

    Display name: WanVideo Draw WanMove Tracks

    Category: WanVideoWrapper

    Returns: image

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WanVideoWanDrawWanMoveTracks() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if images is not _UNSET:
        _kwargs['images'] = images
    if tracks is not _UNSET:
        _kwargs['tracks'] = tracks
    if circle_size is not _UNSET:
        _kwargs['circle_size'] = circle_size
    if line_resolution is not _UNSET:
        _kwargs['line_resolution'] = line_resolution
    if line_width is not _UNSET:
        _kwargs['line_width'] = line_width
    if opacity is not _UNSET:
        _kwargs['opacity'] = opacity
    _kwargs.update(_extras)
    return node(wf, 'WanVideoWanDrawWanMoveTracks', _id, pass_raw=pass_raw, **_kwargs)

def Wav2VecModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``Wav2VecModelLoader``.

    Display name: Wav2vec2 Model Loader

    Category: WanVideoWrapper

    Returns: wav2vec_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"Wav2VecModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'Wav2VecModelLoader', _id, pass_raw=pass_raw, **_kwargs)

def WhisperModelLoader(
    *args: VibeWorkflow,
    _id: str | None = None,
    base_precision: Literal['fp32', 'bf16', 'fp16'] | _Omitted = _UNSET,
    load_device: Literal['main_device', 'offload_device'] | _Omitted = _UNSET,
    model: Any | _Omitted = _UNSET,
    pass_raw: bool = False,
    **_extras: Any,
) -> Any:
    """Public wrapper for the ComfyUI node ``WhisperModelLoader``.

    Display name: Whisper Model Loader

    Category: WanVideoWrapper

    Returns: whisper_model

    Source: object_info cache ComfyUI-WanVideoWrapper@runpod-snapshot.json sha256:1d555466be88
    """
    if len(args) > 1:
        raise TypeError(f"WhisperModelLoader() takes at most 1 positional argument, got {len(args)}")
    wf = args[0] if args else _current_workflow_or_raise()
    _kwargs: dict[str, Any] = {}
    if base_precision is not _UNSET:
        _kwargs['base_precision'] = base_precision
    if load_device is not _UNSET:
        _kwargs['load_device'] = load_device
    if model is not _UNSET:
        _kwargs['model'] = model
    _kwargs.update(_extras)
    return node(wf, 'WhisperModelLoader', _id, pass_raw=pass_raw, **_kwargs)

__all__ = ['CreateCFGScheduleFloatList', 'CreateScheduleFloatList', 'DownloadAndLoadNLFModel', 'DownloadAndLoadWav2VecModel', 'DrawArcFaceLandmarks', 'DrawGaussianNoiseOnImage', 'DrawNLFPoses', 'DummyComfyWanModelObject', 'ExtractStartFramesForContinuations', 'FaceMaskFromPoseKeypoints', 'FantasyPortraitFaceDetector', 'FantasyPortraitModelLoader', 'FantasyTalkingModelLoader', 'FantasyTalkingWav2VecEmbeds', 'HuMoEmbeds', 'LandmarksToImage', 'LoadLynxResampler', 'LoadNLFModel', 'LoadVQVAE', 'LoadWanVideoClipTextEncoder', 'LoadWanVideoT5TextEncoder', 'LynxEncodeFaceIP', 'LynxInsightFaceCrop', 'MTVCrafterEncodePoses', 'MochaEmbeds', 'MultiTalkModelLoader', 'MultiTalkSilentEmbeds', 'MultiTalkWav2VecEmbeds', 'NLFPredict', 'NormalizeAudioLoudness', 'OviMMAudioVAELoader', 'QwenLoader', 'ReCamMasterPoseVisualizer', 'TextImageEncodeQwenVL', 'WanMove_native', 'WanVideoATITracks', 'WanVideoATITracksVisualize', 'WanVideoATI_comfy', 'WanVideoAddBindweaveEmbeds', 'WanVideoAddControlEmbeds', 'WanVideoAddDualControlEmbeds', 'WanVideoAddExtraLatent', 'WanVideoAddFantasyPortrait', 'WanVideoAddFlashVSRInput', 'WanVideoAddLucyEditLatents', 'WanVideoAddLynxEmbeds', 'WanVideoAddMTVMotion', 'WanVideoAddOneToAllExtendEmbeds', 'WanVideoAddOneToAllPoseEmbeds', 'WanVideoAddOneToAllReferenceEmbeds', 'WanVideoAddOviAudioToLatents', 'WanVideoAddPusaNoise', 'WanVideoAddS2VEmbeds', 'WanVideoAddSCAILPoseEmbeds', 'WanVideoAddSCAILReferenceEmbeds', 'WanVideoAddStandInLatent', 'WanVideoAddSteadyDancerEmbeds', 'WanVideoAddStoryMemLatents', 'WanVideoAddTTMLatents', 'WanVideoAddWanMoveTracks', 'WanVideoAnimateEmbeds', 'WanVideoApplyNAG', 'WanVideoBlockList', 'WanVideoBlockSwap', 'WanVideoClipVisionEncode', 'WanVideoCombineEmbeds', 'WanVideoContextOptions', 'WanVideoControlEmbeds', 'WanVideoControlnet', 'WanVideoControlnetLoader', 'WanVideoDecode', 'WanVideoDecodeOviAudio', 'WanVideoDiffusionForcingSampler', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEmptyMMAudioLatents', 'WanVideoEncode', 'WanVideoEncodeLatentBatch', 'WanVideoEncodeOviAudio', 'WanVideoEnhanceAVideo', 'WanVideoExperimentalArgs', 'WanVideoExtraModelSelect', 'WanVideoFlashVSRDecoderLoader', 'WanVideoFreeInitArgs', 'WanVideoFunCameraEmbeds', 'WanVideoImageClipEncode', 'WanVideoImageResizeToClosest', 'WanVideoImageToVideoEncode', 'WanVideoImageToVideoMultiTalk', 'WanVideoImageToVideoSkyreelsv3_audio', 'WanVideoLatentReScale', 'WanVideoLongCatAvatarExtendEmbeds', 'WanVideoLoopArgs', 'WanVideoLoraBlockEdit', 'WanVideoLoraSelect', 'WanVideoLoraSelectByName', 'WanVideoLoraSelectMulti', 'WanVideoMagCache', 'WanVideoMiniMaxRemoverEmbeds', 'WanVideoModelLoader', 'WanVideoOviCFG', 'WanVideoPassImagesFromSamples', 'WanVideoPhantomEmbeds', 'WanVideoPreviewEmbeds', 'WanVideoPromptExtender', 'WanVideoPromptExtenderSelect', 'WanVideoReCamMasterCameraEmbed', 'WanVideoReCamMasterDefaultCamera', 'WanVideoReCamMasterGenerateOrbitCamera', 'WanVideoRealisDanceLatents', 'WanVideoRoPEFunction', 'WanVideoSLG', 'WanVideoSVIProEmbeds', 'WanVideoSampler', 'WanVideoSamplerExtraArgs', 'WanVideoSamplerFromSettings', 'WanVideoSamplerSettings', 'WanVideoSamplerv2', 'WanVideoScheduler', 'WanVideoSchedulerv2', 'WanVideoSetAttentionModeOverride', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoSetRadialAttention', 'WanVideoSigmaToStep', 'WanVideoTeaCache', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTextEncodeCached', 'WanVideoTextEncodeSingle', 'WanVideoTinyVAELoader', 'WanVideoTorchCompileSettings', 'WanVideoUltraVicoSettings', 'WanVideoUni3C_ControlnetLoader', 'WanVideoUni3C_embeds', 'WanVideoUniAnimateDWPoseDetector', 'WanVideoUniAnimatePoseInput', 'WanVideoUniLumosEmbeds', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader', 'WanVideoVRAMManagement', 'WanVideoWanDrawWanMoveTracks', 'Wav2VecModelLoader', 'WhisperModelLoader']
__vibecomfy_class_types__ = {'CreateCFGScheduleFloatList': 'CreateCFGScheduleFloatList', 'CreateScheduleFloatList': 'CreateScheduleFloatList', 'DownloadAndLoadNLFModel': 'DownloadAndLoadNLFModel', 'DownloadAndLoadWav2VecModel': 'DownloadAndLoadWav2VecModel', 'DrawArcFaceLandmarks': 'DrawArcFaceLandmarks', 'DrawGaussianNoiseOnImage': 'DrawGaussianNoiseOnImage', 'DrawNLFPoses': 'DrawNLFPoses', 'DummyComfyWanModelObject': 'DummyComfyWanModelObject', 'ExtractStartFramesForContinuations': 'ExtractStartFramesForContinuations', 'FaceMaskFromPoseKeypoints': 'FaceMaskFromPoseKeypoints', 'FantasyPortraitFaceDetector': 'FantasyPortraitFaceDetector', 'FantasyPortraitModelLoader': 'FantasyPortraitModelLoader', 'FantasyTalkingModelLoader': 'FantasyTalkingModelLoader', 'FantasyTalkingWav2VecEmbeds': 'FantasyTalkingWav2VecEmbeds', 'HuMoEmbeds': 'HuMoEmbeds', 'LandmarksToImage': 'LandmarksToImage', 'LoadLynxResampler': 'LoadLynxResampler', 'LoadNLFModel': 'LoadNLFModel', 'LoadVQVAE': 'LoadVQVAE', 'LoadWanVideoClipTextEncoder': 'LoadWanVideoClipTextEncoder', 'LoadWanVideoT5TextEncoder': 'LoadWanVideoT5TextEncoder', 'LynxEncodeFaceIP': 'LynxEncodeFaceIP', 'LynxInsightFaceCrop': 'LynxInsightFaceCrop', 'MTVCrafterEncodePoses': 'MTVCrafterEncodePoses', 'MochaEmbeds': 'MochaEmbeds', 'MultiTalkModelLoader': 'MultiTalkModelLoader', 'MultiTalkSilentEmbeds': 'MultiTalkSilentEmbeds', 'MultiTalkWav2VecEmbeds': 'MultiTalkWav2VecEmbeds', 'NLFPredict': 'NLFPredict', 'NormalizeAudioLoudness': 'NormalizeAudioLoudness', 'OviMMAudioVAELoader': 'OviMMAudioVAELoader', 'QwenLoader': 'QwenLoader', 'ReCamMasterPoseVisualizer': 'ReCamMasterPoseVisualizer', 'TextImageEncodeQwenVL': 'TextImageEncodeQwenVL', 'WanMove_native': 'WanMove_native', 'WanVideoATITracks': 'WanVideoATITracks', 'WanVideoATITracksVisualize': 'WanVideoATITracksVisualize', 'WanVideoATI_comfy': 'WanVideoATI_comfy', 'WanVideoAddBindweaveEmbeds': 'WanVideoAddBindweaveEmbeds', 'WanVideoAddControlEmbeds': 'WanVideoAddControlEmbeds', 'WanVideoAddDualControlEmbeds': 'WanVideoAddDualControlEmbeds', 'WanVideoAddExtraLatent': 'WanVideoAddExtraLatent', 'WanVideoAddFantasyPortrait': 'WanVideoAddFantasyPortrait', 'WanVideoAddFlashVSRInput': 'WanVideoAddFlashVSRInput', 'WanVideoAddLucyEditLatents': 'WanVideoAddLucyEditLatents', 'WanVideoAddLynxEmbeds': 'WanVideoAddLynxEmbeds', 'WanVideoAddMTVMotion': 'WanVideoAddMTVMotion', 'WanVideoAddOneToAllExtendEmbeds': 'WanVideoAddOneToAllExtendEmbeds', 'WanVideoAddOneToAllPoseEmbeds': 'WanVideoAddOneToAllPoseEmbeds', 'WanVideoAddOneToAllReferenceEmbeds': 'WanVideoAddOneToAllReferenceEmbeds', 'WanVideoAddOviAudioToLatents': 'WanVideoAddOviAudioToLatents', 'WanVideoAddPusaNoise': 'WanVideoAddPusaNoise', 'WanVideoAddS2VEmbeds': 'WanVideoAddS2VEmbeds', 'WanVideoAddSCAILPoseEmbeds': 'WanVideoAddSCAILPoseEmbeds', 'WanVideoAddSCAILReferenceEmbeds': 'WanVideoAddSCAILReferenceEmbeds', 'WanVideoAddStandInLatent': 'WanVideoAddStandInLatent', 'WanVideoAddSteadyDancerEmbeds': 'WanVideoAddSteadyDancerEmbeds', 'WanVideoAddStoryMemLatents': 'WanVideoAddStoryMemLatents', 'WanVideoAddTTMLatents': 'WanVideoAddTTMLatents', 'WanVideoAddWanMoveTracks': 'WanVideoAddWanMoveTracks', 'WanVideoAnimateEmbeds': 'WanVideoAnimateEmbeds', 'WanVideoApplyNAG': 'WanVideoApplyNAG', 'WanVideoBlockList': 'WanVideoBlockList', 'WanVideoBlockSwap': 'WanVideoBlockSwap', 'WanVideoClipVisionEncode': 'WanVideoClipVisionEncode', 'WanVideoCombineEmbeds': 'WanVideoCombineEmbeds', 'WanVideoContextOptions': 'WanVideoContextOptions', 'WanVideoControlEmbeds': 'WanVideoControlEmbeds', 'WanVideoControlnet': 'WanVideoControlnet', 'WanVideoControlnetLoader': 'WanVideoControlnetLoader', 'WanVideoDecode': 'WanVideoDecode', 'WanVideoDecodeOviAudio': 'WanVideoDecodeOviAudio', 'WanVideoDiffusionForcingSampler': 'WanVideoDiffusionForcingSampler', 'WanVideoEasyCache': 'WanVideoEasyCache', 'WanVideoEmptyEmbeds': 'WanVideoEmptyEmbeds', 'WanVideoEmptyMMAudioLatents': 'WanVideoEmptyMMAudioLatents', 'WanVideoEncode': 'WanVideoEncode', 'WanVideoEncodeLatentBatch': 'WanVideoEncodeLatentBatch', 'WanVideoEncodeOviAudio': 'WanVideoEncodeOviAudio', 'WanVideoEnhanceAVideo': 'WanVideoEnhanceAVideo', 'WanVideoExperimentalArgs': 'WanVideoExperimentalArgs', 'WanVideoExtraModelSelect': 'WanVideoExtraModelSelect', 'WanVideoFlashVSRDecoderLoader': 'WanVideoFlashVSRDecoderLoader', 'WanVideoFreeInitArgs': 'WanVideoFreeInitArgs', 'WanVideoFunCameraEmbeds': 'WanVideoFunCameraEmbeds', 'WanVideoImageClipEncode': 'WanVideoImageClipEncode', 'WanVideoImageResizeToClosest': 'WanVideoImageResizeToClosest', 'WanVideoImageToVideoEncode': 'WanVideoImageToVideoEncode', 'WanVideoImageToVideoMultiTalk': 'WanVideoImageToVideoMultiTalk', 'WanVideoImageToVideoSkyreelsv3_audio': 'WanVideoImageToVideoSkyreelsv3_audio', 'WanVideoLatentReScale': 'WanVideoLatentReScale', 'WanVideoLongCatAvatarExtendEmbeds': 'WanVideoLongCatAvatarExtendEmbeds', 'WanVideoLoopArgs': 'WanVideoLoopArgs', 'WanVideoLoraBlockEdit': 'WanVideoLoraBlockEdit', 'WanVideoLoraSelect': 'WanVideoLoraSelect', 'WanVideoLoraSelectByName': 'WanVideoLoraSelectByName', 'WanVideoLoraSelectMulti': 'WanVideoLoraSelectMulti', 'WanVideoMagCache': 'WanVideoMagCache', 'WanVideoMiniMaxRemoverEmbeds': 'WanVideoMiniMaxRemoverEmbeds', 'WanVideoModelLoader': 'WanVideoModelLoader', 'WanVideoOviCFG': 'WanVideoOviCFG', 'WanVideoPassImagesFromSamples': 'WanVideoPassImagesFromSamples', 'WanVideoPhantomEmbeds': 'WanVideoPhantomEmbeds', 'WanVideoPreviewEmbeds': 'WanVideoPreviewEmbeds', 'WanVideoPromptExtender': 'WanVideoPromptExtender', 'WanVideoPromptExtenderSelect': 'WanVideoPromptExtenderSelect', 'WanVideoReCamMasterCameraEmbed': 'WanVideoReCamMasterCameraEmbed', 'WanVideoReCamMasterDefaultCamera': 'WanVideoReCamMasterDefaultCamera', 'WanVideoReCamMasterGenerateOrbitCamera': 'WanVideoReCamMasterGenerateOrbitCamera', 'WanVideoRealisDanceLatents': 'WanVideoRealisDanceLatents', 'WanVideoRoPEFunction': 'WanVideoRoPEFunction', 'WanVideoSLG': 'WanVideoSLG', 'WanVideoSVIProEmbeds': 'WanVideoSVIProEmbeds', 'WanVideoSampler': 'WanVideoSampler', 'WanVideoSamplerExtraArgs': 'WanVideoSamplerExtraArgs', 'WanVideoSamplerFromSettings': 'WanVideoSamplerFromSettings', 'WanVideoSamplerSettings': 'WanVideoSamplerSettings', 'WanVideoSamplerv2': 'WanVideoSamplerv2', 'WanVideoScheduler': 'WanVideoScheduler', 'WanVideoSchedulerv2': 'WanVideoSchedulerv2', 'WanVideoSetAttentionModeOverride': 'WanVideoSetAttentionModeOverride', 'WanVideoSetBlockSwap': 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs': 'WanVideoSetLoRAs', 'WanVideoSetRadialAttention': 'WanVideoSetRadialAttention', 'WanVideoSigmaToStep': 'WanVideoSigmaToStep', 'WanVideoTeaCache': 'WanVideoTeaCache', 'WanVideoTextEmbedBridge': 'WanVideoTextEmbedBridge', 'WanVideoTextEncode': 'WanVideoTextEncode', 'WanVideoTextEncodeCached': 'WanVideoTextEncodeCached', 'WanVideoTextEncodeSingle': 'WanVideoTextEncodeSingle', 'WanVideoTinyVAELoader': 'WanVideoTinyVAELoader', 'WanVideoTorchCompileSettings': 'WanVideoTorchCompileSettings', 'WanVideoUltraVicoSettings': 'WanVideoUltraVicoSettings', 'WanVideoUni3C_ControlnetLoader': 'WanVideoUni3C_ControlnetLoader', 'WanVideoUni3C_embeds': 'WanVideoUni3C_embeds', 'WanVideoUniAnimateDWPoseDetector': 'WanVideoUniAnimateDWPoseDetector', 'WanVideoUniAnimatePoseInput': 'WanVideoUniAnimatePoseInput', 'WanVideoUniLumosEmbeds': 'WanVideoUniLumosEmbeds', 'WanVideoVACEEncode': 'WanVideoVACEEncode', 'WanVideoVACEModelSelect': 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame': 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader': 'WanVideoVAELoader', 'WanVideoVRAMManagement': 'WanVideoVRAMManagement', 'WanVideoWanDrawWanMoveTracks': 'WanVideoWanDrawWanMoveTracks', 'Wav2VecModelLoader': 'Wav2VecModelLoader', 'WhisperModelLoader': 'WhisperModelLoader'}
