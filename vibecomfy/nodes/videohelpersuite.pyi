# vibecomfy:generated
# pack: videohelpersuite
# source: object_info cache ComfyUI-VideoHelperSuite@runpod-snapshot.json sha256:c47f0c44d97e
# source_sha256: 77d8fc8c4abaf3c904b367f3e232ec42b4e262a14d40f97060e1c9e22da683f2
# generator_version: 2.0.0
# generated_at: 1970-01-01T00:00:00+00:00
# classes: 40

"""Type stubs for generated public node wrappers."""
from __future__ import annotations

from typing import Any, Literal

from vibecomfy.workflow import VibeWorkflow

class _Omitted: ...
_UNSET: _Omitted

def VHS_AudioToVHSAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_BatchManager(
    *args: VibeWorkflow,
    _id: str | None = ...,
    frames_per_batch: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_DuplicateImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    multiply_by: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_DuplicateLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    multiply_by: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_DuplicateMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    multiply_by: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_GetImageCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_GetLatentCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_GetMaskCount(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio_file: str | _Omitted = ...,
    duration: float | _Omitted = ...,
    seek_seconds: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadAudioUpload(
    *args: VibeWorkflow,
    _id: str | None = ...,
    audio: Any | _Omitted = ...,
    duration: float | _Omitted = ...,
    start_time: float | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadImagePath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    custom_height: int | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    image: str | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    directory: Literal['3d'] | _Omitted = ...,
    image_load_cap: int | _Omitted = ...,
    meta_batch: Any | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_images: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadImagesPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    directory: str | _Omitted = ...,
    image_load_cap: int | _Omitted = ...,
    meta_batch: Any | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_images: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadVideo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    custom_height: int | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    force_rate: float | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_frames: int | _Omitted = ...,
    video: Any | _Omitted = ...,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = ...,
    meta_batch: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadVideoFFmpeg(
    *args: VibeWorkflow,
    _id: str | None = ...,
    custom_height: int | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    force_rate: float | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    start_time: float | _Omitted = ...,
    video: Any | _Omitted = ...,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = ...,
    meta_batch: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadVideoFFmpegPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    custom_height: int | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    force_rate: float | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    start_time: float | _Omitted = ...,
    video: str | _Omitted = ...,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = ...,
    meta_batch: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_LoadVideoPath(
    *args: VibeWorkflow,
    _id: str | None = ...,
    custom_height: int | _Omitted = ...,
    custom_width: int | _Omitted = ...,
    force_rate: float | _Omitted = ...,
    frame_load_cap: int | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_frames: int | _Omitted = ...,
    video: str | _Omitted = ...,
    format: Literal['None', 'AnimateDiff', 'Mochi', 'LTXV', 'Hunyuan', 'Cosmos', 'Wan'] | _Omitted = ...,
    meta_batch: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_MergeImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images_A: Any | _Omitted = ...,
    images_B: Any | _Omitted = ...,
    crop: Literal['disabled', 'center'] | _Omitted = ...,
    merge_strategy: Literal['match A', 'match B', 'match smaller', 'match larger'] | _Omitted = ...,
    scale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_MergeLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents_A: Any | _Omitted = ...,
    latents_B: Any | _Omitted = ...,
    crop: Literal['disabled', 'center'] | _Omitted = ...,
    merge_strategy: Literal['match A', 'match B', 'match smaller', 'match larger'] | _Omitted = ...,
    scale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_MergeMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask_A: Any | _Omitted = ...,
    mask_B: Any | _Omitted = ...,
    crop: Literal['disabled', 'center'] | _Omitted = ...,
    merge_strategy: Literal['match A', 'match B', 'match smaller', 'match larger'] | _Omitted = ...,
    scale_method: Literal['nearest-exact', 'bilinear', 'area', 'bicubic', 'bislerp'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_PruneOutputs(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filenames: Any | _Omitted = ...,
    options: Literal['Intermediate', 'Intermediate and Utility'] | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectEveryNthImage(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_images: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectEveryNthLatent(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_latents: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectEveryNthMask(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    select_every_nth: int | _Omitted = ...,
    skip_first_masks: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectFilename(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filenames: Any | _Omitted = ...,
    index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    image: Any | _Omitted = ...,
    err_if_empty: bool | _Omitted = ...,
    err_if_missing: bool | _Omitted = ...,
    indexes: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latent: Any | _Omitted = ...,
    err_if_empty: bool | _Omitted = ...,
    err_if_missing: bool | _Omitted = ...,
    indexes: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectLatest(
    *args: VibeWorkflow,
    _id: str | None = ...,
    filename_postfix: str | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SelectMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    err_if_empty: bool | _Omitted = ...,
    err_if_missing: bool | _Omitted = ...,
    indexes: str | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SplitImages(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    split_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SplitLatents(
    *args: VibeWorkflow,
    _id: str | None = ...,
    latents: Any | _Omitted = ...,
    split_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_SplitMasks(
    *args: VibeWorkflow,
    _id: str | None = ...,
    mask: Any | _Omitted = ...,
    split_index: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_Unbatch(
    *args: VibeWorkflow,
    _id: str | None = ...,
    batched: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_VAEDecodeBatched(
    *args: VibeWorkflow,
    _id: str | None = ...,
    samples: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    per_batch: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_VAEEncodeBatched(
    *args: VibeWorkflow,
    _id: str | None = ...,
    pixels: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    per_batch: int | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_VHSAudioToAudio(
    *args: VibeWorkflow,
    _id: str | None = ...,
    vhs_audio: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_VideoCombine(
    *args: VibeWorkflow,
    _id: str | None = ...,
    images: Any | _Omitted = ...,
    filename_prefix: str | _Omitted = ...,
    format: Literal['image/gif', 'image/webp', 'video/16bit-png', 'video/8bit-png', 'video/ProRes', 'video/av1-webm', 'video/ffmpeg-gif', 'video/ffv1-mkv', 'video/h264-mp4', 'video/h265-mp4', 'video/nvenc_av1-mp4', 'video/nvenc_h264-mp4', 'video/nvenc_hevc-mp4', 'video/webm'] | _Omitted = ...,
    frame_rate: float | _Omitted = ...,
    loop_count: int | _Omitted = ...,
    pingpong: bool | _Omitted = ...,
    save_output: bool | _Omitted = ...,
    audio: Any | _Omitted = ...,
    meta_batch: Any | _Omitted = ...,
    vae: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_VideoInfo(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video_info: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_VideoInfoLoaded(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video_info: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

def VHS_VideoInfoSource(
    *args: VibeWorkflow,
    _id: str | None = ...,
    video_info: Any | _Omitted = ...,
    pass_raw: bool = ...,
    **_extras: Any,
) -> Any: ...

__all__ = ['VHS_AudioToVHSAudio', 'VHS_BatchManager', 'VHS_DuplicateImages', 'VHS_DuplicateLatents', 'VHS_DuplicateMasks', 'VHS_GetImageCount', 'VHS_GetLatentCount', 'VHS_GetMaskCount', 'VHS_LoadAudio', 'VHS_LoadAudioUpload', 'VHS_LoadImagePath', 'VHS_LoadImages', 'VHS_LoadImagesPath', 'VHS_LoadVideo', 'VHS_LoadVideoFFmpeg', 'VHS_LoadVideoFFmpegPath', 'VHS_LoadVideoPath', 'VHS_MergeImages', 'VHS_MergeLatents', 'VHS_MergeMasks', 'VHS_PruneOutputs', 'VHS_SelectEveryNthImage', 'VHS_SelectEveryNthLatent', 'VHS_SelectEveryNthMask', 'VHS_SelectFilename', 'VHS_SelectImages', 'VHS_SelectLatents', 'VHS_SelectLatest', 'VHS_SelectMasks', 'VHS_SplitImages', 'VHS_SplitLatents', 'VHS_SplitMasks', 'VHS_Unbatch', 'VHS_VAEDecodeBatched', 'VHS_VAEEncodeBatched', 'VHS_VHSAudioToAudio', 'VHS_VideoCombine', 'VHS_VideoInfo', 'VHS_VideoInfoLoaded', 'VHS_VideoInfoSource']
