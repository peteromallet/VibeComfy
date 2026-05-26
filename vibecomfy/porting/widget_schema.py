"""Widget-only positional schema shared by porting and conversion tools.

Entries map a ComfyUI class type to ordered `widgets_values` API input
names. Link-only sockets such as IMAGE, MODEL, CLIP, VAE, and LATENT are
intentionally excluded so positional widgets cannot be shifted by object_info
link inputs.
"""

from __future__ import annotations

WIDGET_SEMANTIC_NAMES: dict[str, dict[str, str]] = {
    "PrimitiveInt": {"widget_0": "value"},
    "PrimitiveString": {"widget_0": "value"},
    "PrimitiveStringMultiline": {"widget_0": "value"},
    "PrimitiveFloat": {"widget_0": "value"},
    "PrimitiveBoolean": {"widget_0": "value"},
}

WIDGET_SCHEMA: dict[str, list[str | None]] = {
    "BasicScheduler": ["scheduler", "steps", "denoise"],
    "CFGGuider": ["cfg"],
    "CheckpointLoaderSimple": ["ckpt_name"],
    "CLIPLoader": ["clip_name", "type", "device"],
    "CLIPTextEncode": ["text"],
    "CLIPTextEncodeFlux": ["clip_l", "t5xxl", "guidance"],
    "CLIPTextEncodeSD3": ["clip_l", "clip_g", "t5xxl", "empty_padding"],
    "ConditioningSetTimestepRange": ["start", "end"],
    "CreateVideo": ["fps"],
    "DualCLIPLoader": ["clip_name1", "clip_name2", "type", "device"],
    "DualCLIPLoaderGGUF": ["clip_name1", "clip_name2", "type"],
    "EmptyFlux2LatentImage": ["width", "height", "batch_size"],
    "EmptyHunyuanLatentVideo": ["width", "height", "length", "batch_size"],
    "EmptyLTXVLatentVideo": ["width", "height", "length", "batch_size"],
    "EmptySD3LatentImage": ["width", "height", "batch_size"],
    "FluxGuidance": ["guidance"],
    "Flux2Scheduler": ["steps", "width", "height"],
    "GetImageSize": [],
    "ImageResize": ["resize_mode", "resolutions", "interpolation", "aspect_ratio_tolerance"],
    "ImageScale": ["upscale_method", "width", "height", "crop"],
    "ImageScaleBy": ["upscale_method", "scale_by"],
    "ImageScaleToTotalPixels": ["upscale_method", "megapixels", "resolution_steps"],
    "KSampler": ["seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "KSamplerAdvanced": [
        "add_noise",
        "noise_seed",
        None,
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "start_at_step",
        "end_at_step",
        "return_with_leftover_noise",
    ],
    "KSamplerSelect": ["sampler_name"],
    # LoadAudio: object_info comfy_core@runpod-snapshot.json lists only ['audio'].
    # Source workflows store two extra trailing widget slots (preview / upload UI)
    # that have no runtime semantics. Recording them as None surfaces them as
    # unused_widget_1 / unused_widget_2 in generated templates rather than as
    # positional widget_N keys.
    "LoadAudio": ["audio", None, None],
    "LoadImage": ["image", None],
    "LoraLoaderModelOnly": ["lora_name", "strength_model"],
    "LTX2AttentionTunerPatch": [
        "blocks",
        "video_scale",
        "audio_scale",
        "video_to_audio_scale",
        "audio_to_video_scale",
        "triton_kernels",
    ],
    "LTX2MemoryEfficientSageAttentionPatch": ["triton_kernels"],
    "LTX2_NAG": ["nag_scale", "nag_alpha", "nag_tau", None],
    "LTX2SamplingPreviewOverride": ["preview_rate"],
    "LTXICLoRALoaderModelOnly": ["lora_name", "strength_model"],
    "LTXAddVideoICLoRAGuide": [
        "frame_idx",
        "strength",
        "crop",
        "use_tiled_encode",
        None,
        "tile_size",
        "tile_overlap",
    ],
    "LTXVConditioning": ["frame_rate"],
    "LTXVEmptyLatentAudio": ["frames_number", "frame_rate", "batch_size"],
    "LTXVAddGuide": ["frame_idx", "strength"],
    "LTXVChunkFeedForward": ["chunks", "dim_threshold"],
    "LTXVImgToVideoConditionOnly": ["strength", "bypass"],
    "LTXAVTextEncoderLoader": ["text_encoder", "ckpt_name", "device"],
    "LTXVPreprocess": ["img_compression"],
    "LTXFloatToInt": ["rounding"],
    "LTXVScheduler": ["steps", "max_shift", "base_shift", "stretch", "terminal"],
    # LTXVTiledVAEDecode: last two slots are working_device/working_dtype.
    # Source: object_info cache ComfyUI-LTXVideo@runpod-snapshot.json
    # (object_info_widget_order [None, None, 'horizontal_tiles', 'vertical_tiles',
    # 'overlap', 'last_frame_fix', 'working_device', 'working_dtype']).
    "LTXVTiledVAEDecode": [
        "horizontal_tiles",
        "vertical_tiles",
        "overlap",
        "last_frame_fix",
        "working_device",
        "working_dtype",
    ],
    "LatentUpscaleModelLoader": ["model_name"],
    "ManualSigmas": ["sigmas"],
    "ModelSamplingAuraFlow": ["shift"],
    "ModelSamplingFlux": ["max_shift", "base_shift", "width", "height"],
    "ModelSamplingSD3": ["shift"],
    "PrimitiveBoolean": ["value"],
    "PrimitiveFloat": ["value"],
    "PrimitiveInt": ["value"],
    "PrimitiveString": ["value"],
    "PrimitiveStringMultiline": ["value"],
    "PathchSageAttentionKJ": ["sage_attention", "allow_compile"],
    "Power Lora Loader (rgthree)": [None, None, None, None],
    "RandomNoise": ["noise_seed", "control_after_generate"],
    "ResizeImagesByLongerEdge": ["longer_edge"],
    "SamplerCustomAdvanced": [],
    "SaveAudio": ["filename_prefix"],
    "SaveAudioMP3": ["filename_prefix", "quality"],
    "SaveImage": ["filename_prefix"],
    "SaveVideo": ["filename_prefix", "format", "codec"],
    # SimpleCalculatorKJ: object_info order is ['expression', 'variables']; some
    # source workflows record a 3rd widget that holds the cached preview value.
    # Slot 2 stays None so it surfaces as unused_widget_2 instead of inventing a
    # name. Source: object_info ComfyUI-KJNodes@runpod-snapshot.json.
    "SimpleCalculatorKJ": ["expression", "variables", None],
    "TextEncodeAceStepAudio1.5": [
        "tags",
        "lyrics",
        "seed",
        None,
        "duration",
        "bpm",
        "timesignature",
        "language",
        "keyscale",
        "generate_audio_codes",
        "cfg_scale",
        "temperature",
        "top_p",
        "top_k",
        "min_p",
    ],
    "TextEncodeQwenImageEdit": ["prompt"],
    "TripleCLIPLoader": ["clip_name1", "clip_name2", "clip_name3"],
    "UNETLoader": ["unet_name", "weight_dtype"],
    "UnetLoaderGGUF": ["unet_name"],
    "VAEDecode": [],
    "VAEDecodeTiled": ["tile_size", "overlap", "temporal_size", "temporal_overlap"],
    "VAEEncode": [],
    "VAELoader": ["vae_name"],
    "VAELoaderKJ": ["vae_name", "device", "weight_dtype"],
    "LoadWanVideoT5TextEncoder": ["model_name", "precision", "load_device", "quantization"],
    "WanVideoTextEncode": ["positive_prompt", "negative_prompt", "force_offload", "use_disk_cache", "device"],
    "WanVideoTextEncodeCached": [
        "model_name",
        "precision",
        "positive_prompt",
        "negative_prompt",
        "quantization",
        "use_disk_cache",
        "device",
    ],
    "CLIPVisionLoader": ["clip_name"],
    "WanVideoModelLoader": ["model", "base_precision", "quantization", "load_device", "attention_mode", "rms_norm_function"],
    "WanVideoBlockSwap": [
        "blocks_to_swap",
        "offload_img_emb",
        "offload_txt_emb",
        "use_non_blocking",
        "vace_blocks_to_swap",
        "prefetch_blocks",
        "block_swap_debug",
    ],
    "WanVideoTorchCompileSettings": [
        "backend",
        "fullgraph",
        "mode",
        "dynamic",
        "dynamo_cache_size_limit",
        "compile_transformer_blocks_only",
        "dynamo_recompile_limit",
        "force_parameter_static_shapes",
        "allow_unmerged_lora_compile",
    ],
    "WanVideoLoraSelect": ["lora", "strength", "low_mem_load", "merge_loras"],
    "WanVideoLoraSelectMulti": [
        "lora_0",
        "strength_0",
        "lora_1",
        "strength_1",
        "lora_2",
        "strength_2",
        "lora_3",
        "strength_3",
        "lora_4",
        "strength_4",
        "low_mem_load",
        "merge_loras",
    ],
    "WanVideoImageToVideoEncode": [
        "width",
        "height",
        "num_frames",
        "noise_aug_strength",
        "start_latent_strength",
        "end_latent_strength",
        "force_offload",
        "tiled_vae",
        "fun_or_fl2v_model",
    ],
    "WanVideoVAELoader": ["model_name", "precision"],
    "WanVideoDecode": ["enable_vae_tiling", "tile_x", "tile_y", "tile_stride_x", "tile_stride_y", "normalization"],
    "WanVideoSampler": [
        "steps",
        "cfg",
        "shift",
        "seed",
        None,
        "force_offload",
        "scheduler",
        "riflex_freq_index",
        "denoise_strength",
        "batched_cfg",
        "rope_function",
        "start_step",
        "end_step",
        "add_noise_to_samples",
    ],
    "CreateCFGScheduleFloatList": [
        "steps",
        "cfg_scale_start",
        "cfg_scale_end",
        "interpolation",
        "start_percent",
        "end_percent",
    ],
    "WanVideoAnimateEmbeds": [
        "width",
        "height",
        "num_frames",
        "force_offload",
        "frame_window_size",
        "colormatch",
        "face_strength",
        "pose_strength",
        "unused_8",
    ],
    "WanVideoClipVisionEncode": [
        "strength_1",
        "strength_2",
        "crop",
        "combine_embeds",
        "force_offload",
        "tiles",
        "ratio",
    ],
    "WanVideoContextOptions": [
        "context_schedule",
        "context_frames",
        "context_stride",
        "context_overlap",
        "freenoise",
        "verbose",
        "fuse_method",
    ],
    "ImageResizeKJv2": [
        "width",
        "height",
        "upscale_method",
        "keep_proportion",
        "pad_color",
        "crop_position",
        "divisible_by",
        "device",
        None,
    ],
    "INTConstant": ["value"],
    "FloatConstant": ["value"],
    "ImageConcatMulti": ["inputcount", "direction", "match_image_size", "unused_3"],
    # Source: object_info ComfyUI-KJNodes@runpod-snapshot.json
    # (order [None, 'block_size', 'device']).
    "BlockifyMask": ["block_size", "device"],
    "CannyEdgePreprocessor": ["low_threshold", "high_threshold", "resolution"],
    "DrawMaskOnImage": ["color"],
    "GrowMask": ["expand", "tapered_corners"],
    "DWPreprocessor": [
        "detect_hand",
        "detect_body",
        "detect_face",
        "resolution",
        "bbox_detector",
        "pose_estimator",
        "scale_stick_for_xinsr_cn",
    ],
    "PointsEditor": [
        "points_store",
        "coordinates",
        "neg_coordinates",
        "bbox_store",
        "bboxes",
        "bbox_format",
        "width",
        "height",
        "normalize",
    ],
    "CLIPVisionEncode": ["crop"],
    "LoadVideo": ["file", None],
    "PixelPerfectResolution": ["resize_mode"],
    "GrowMaskWithBlur": [
        "expand",
        "incremental_expandrate",
        "tapered_corners",
        "flip_input",
        "blur_radius",
        "lerp_alpha",
        "decay_factor",
        "unused_7",
    ],
    "DownloadAndLoadSAM2Model": ["model", "segmentor", "device", "precision"],
    "Sam2Segmentation": ["keep_model_loaded", "individual_objects"],
    "OnnxDetectionModelLoader": ["vitpose_model", "yolo_model", "onnx_device"],
    "PoseAndFaceDetection": ["width", "height", "face_padding"],
    "DrawViTPose": ["width", "height", "retarget_padding", "body_stick_width", "hand_stick_width", "draw_head"],
    "ResizeImageMaskNode": ["resize_type", None, "scale_method"],
    # Widget-bearing utility / core nodes derived from object_info cache.
    # Each entry follows the compact widget-only ordering (link sockets removed):
    # the IR stores positional `widget_N` keys aligned to widgets_values, while
    # object_info_widget_order interleaves None placeholders for link sockets.
    # Sources are cited inline.
    # Source: object_info comfy_core@runpod-snapshot.json (order [None, None,
    # 'blend_factor', 'blend_mode'] -> compact ['blend_factor', 'blend_mode']).
    "ImageBlend": ["blend_factor", "blend_mode"],
    # Source: object_info comfy@runpod-snapshot.json (order [None, 'left', 'top',
    # 'right', 'bottom', 'feathering']).
    "ImagePadForOutpaint": ["left", "top", "right", "bottom", "feathering"],
    # Source: object_info comfy_core@runpod-snapshot.json (order [None, 'direction',
    # 'match_image_size', 'spacing_width', 'spacing_color', None]).
    "ImageStitch": ["direction", "match_image_size", "spacing_width", "spacing_color"],
    # Source: object_info comfy_core@runpod-snapshot.json (order [None, None, None,
    # 'strength', 'bypass']).
    "LTXVImgToVideoInplace": ["strength", "bypass"],
    # Source: object_info comfy_core@runpod-snapshot.json (order ['value', 'width',
    # 'height']).
    "SolidMask": ["value", "width", "height"],
    # Source: object_info comfy_core@runpod-snapshot.json (order ['string_a',
    # 'string_b', 'delimiter']).
    "StringConcatenate": ["string_a", "string_b", "delimiter"],
    # Source: object_info comfy_core@runpod-snapshot.json (order [None, 'prompt',
    # 'max_length', 'sampling_mode', None, 'thinking']). Source workflow widgets_values
    # have 5 entries -- the 5th is the StreamFix toggle which sits between sampling_mode
    # and thinking in older Comfy builds. Recorded as None to surface as unused_widget_3
    # rather than guessing a name.
    "TextGenerateLTX2Prompt": ["prompt", "max_length", "sampling_mode", None, "thinking"],
    # Source: object_info comfy_core@runpod-snapshot.json (order [None, 'start_index',
    # 'duration']).
    "TrimAudioDuration": ["start_index", "duration"],
    # Source: object_info comfy_core@runpod-snapshot.json (order ['switch', 'on_false',
    # 'on_true']).
    "ComfySwitchNode": ["switch", "on_false", "on_true"],
    # Source: object_info comfy_core@runpod-snapshot.json (order ['duration',
    # 'sample_rate', 'channels']).
    "EmptyAudio": ["duration", "sample_rate", "channels"],
    # Source: object_info ComfyUI-KJNodes@runpod-snapshot.json (order ['switch',
    # 'on_false', 'on_true']).
    "LazySwitchKJ": ["switch", "on_false", "on_true"],
    # DepthAnythingPreprocessor (comfyui_controlnet_aux pack). Source:
    # comfyui_controlnet_aux/node_wrappers/depth_anything.py INPUT_TYPES
    # ({required: {ckpt_name: (...)}, optional: {resolution: ('INT', ...)}}).
    # object_info cache stub is empty so curated entry takes the slot.
    "DepthAnythingPreprocessor": ["ckpt_name", "resolution"],
    # 'easy showAnything' is a UI display node (ComfyUI-Easy-Use). widget_0
    # stores the cached display string and has no committed input name from
    # upstream metadata; recorded as None so it surfaces as unused_widget_0.
    # TODO: schema unknown -- verify against ComfyUI-Easy-Use INPUT_TYPES if
    # the pack ships an object_info entry.
    "easy showAnything": [None],
    # rgthree helper broadcast nodes: widget_0 holds the broadcast variable name.
    # Source: rgthree-comfy node implementations (SetNode/GetNode store `name` as the
    # single widget value). Resolved by emission-time helper pre-pass when paired;
    # this entry only matters for the raw_call fallback when pairing cannot be
    # established (e.g. subgraph boundaries).
    "GetNode": ["name"],
    "SetNode": ["name"],
    # PrimitiveNode (ComfyUI UI primitive container): widget_0 is the cached
    # value; widget_1 holds `control_after_generate`, a UI-only seed control
    # that ComfyUI's own API submission omits. Schema length matches the
    # JSON's widget count so length validation passes, but widget_1 is
    # intentionally `None` to drop it from compile output and preserve
    # _normalize_ui_to_api parity. Helper-node elimination lives in Block A.
    "PrimitiveNode": ["value", None],
    "VHS_VideoCombine": [
        "frame_rate",
        "loop_count",
        "filename_prefix",
        "format",
        "pingpong",
        "save_output",
    ],
    # ── Audio tooling (ComfyUI-AudioTools, ComfyUI-MelBandRoformer) ──
    # Source: object_info ComfyUI-MelBandRoformer stub (input_order_all ['model']).
    "MelBandRoFormerModelLoader": ["model"],
    # Source: ComfyUI-AudioTools (Urabewe) audio_normalize.py INPUT_TYPES
    # (order [None, 'target_lufs', 'start_time', 'end_time', 'apply_to']).
    "AudioNormalizeLUFS": ["target_lufs", "start_time", "end_time", "apply_to"],
    # Source: ComfyUI-AudioTools (Urabewe) audio_enhance.py INPUT_TYPES
    # (order [None, 'enhancement_mode', 'enhancement_strength', 'harmonic_intensity',
    # 'stereo_width', 'dynamic_enhancement', 'bass_boost', 'presence_boost',
    # 'warmth', 'target_sample_rate', 'enable_noise_reduction',
    # 'noise_reduction_level', 'start_time', 'end_time', 'apply_to']).
    "AudioEnhancementNode": [
        "enhancement_mode",
        "enhancement_strength",
        "harmonic_intensity",
        "stereo_width",
        "dynamic_enhancement",
        "bass_boost",
        "presence_boost",
        "warmth",
        "target_sample_rate",
        "enable_noise_reduction",
        "noise_reduction_level",
        "start_time",
        "end_time",
        "apply_to",
    ],
    # ── LTX Video (ComfyUI-LTXVideo) ──
    # Source: object_info ComfyUI-LTXVideo@runpod-snapshot.json
    # (order [None, None, 'invert_input_masks', 'ignore_first_mask', 'pooling_method',
    # 'grow_mask', 'tapered_corners', 'clamp_min', 'clamp_max']).
    "LTXVPreprocessMasks": [
        "invert_input_masks",
        "ignore_first_mask",
        "pooling_method",
        "grow_mask",
        "tapered_corners",
        "clamp_min",
        "clamp_max",
    ],
    # Source: object_info ComfyUI-LTXVideo@runpod-snapshot.json
    # (order [None, None, None, None, None, 'latent_idx', 'strength']).
    "LTXVAddLatentGuide": ["latent_idx", "strength"],
    # ── KJNodes ──
    # Source: object_info ComfyUI-KJNodes@runpod-snapshot.json
    # (order ['video_fps', 'video_start_time', 'video_end_time', 'audio_start_time',
    # 'audio_end_time', 'max_length', None, None, 'existing_mask_mode']).
    "LTXVAudioVideoMask": [
        "video_fps",
        "video_start_time",
        "video_end_time",
        "audio_start_time",
        "audio_end_time",
        "max_length",
        "existing_mask_mode",
    ],
    # Source: object_info ComfyUI-KJNodes@runpod-snapshot.json
    # (order [None, 'overlap', 'overlap_side', 'overlap_mode', None]).
    "ImageBatchExtendWithOverlap": ["overlap", "overlap_side", "overlap_mode"],
    # Source: object_info ComfyUI-KJNodes@runpod-snapshot.json (DynamicCombo node;
    # widget_0=num_images selects dynamic inputs; for num_images='1' the dynamic
    # widgets are strength_1 and index_1).
    "LTXVImgToVideoInplaceKJ": ["num_images", "strength_1", "index_1"],
    # Source: object_info ComfyUI-KJNodes@runpod-snapshot.json
    # (order ['video', 'force_rate', 'custom_width', 'custom_height',
    # 'frame_load_cap', 'skip_first_frames', 'select_every_nth', 'output_type',
    # 'grid_max_columns', 'add_label']).
    "LoadVideosFromFolder": [
        "video",
        "force_rate",
        "custom_width",
        "custom_height",
        "frame_load_cap",
        "skip_first_frames",
        "select_every_nth",
        "output_type",
        "grid_max_columns",
        "add_label",
    ],
    # ── Core / comfy_extras ──
    # Source: object_info comfy_core@runpod-snapshot.json
    # (order [None, None, 'direction']).
    "AudioConcat": ["direction"],
    # Source: object_info comfy_extras@runpod-snapshot.json
    # (order ['start_index', 'num_frames', None, None]).
    "GetImageRangeFromBatch": ["start_index", "num_frames"],
    # ── VideoHelperSuite ──
    # Source: object_info ComfyUI-VideoHelperSuite@runpod-snapshot.json
    # (order ['video', 'force_rate', 'custom_width', 'custom_height',
    # 'frame_load_cap', 'skip_first_frames', 'select_every_nth', 'meta_batch',
    # None, 'format']).
    "VHS_LoadVideo": [
        "video",
        "force_rate",
        "custom_width",
        "custom_height",
        "frame_load_cap",
        "skip_first_frames",
        "select_every_nth",
        "meta_batch",
        "format",
    ],
    # ── WanVideoWrapper ──
    # Source: object_info ComfyUI-WanVideoWrapper@runpod-snapshot.json
    # (order [None, 'lufs']).
    "NormalizeAudioLoudness": ["lufs"],
    # ── AILab / Qwen TTS ──
    # Source: object_info AILab_QwenTTS@runpod-snapshot.json
    # (order ['target_text', 'model_size', 'language', None, 'reference_text',
    # 'x_vector_only', 'voice', 'unload_models', 'seed']).
    "AILab_Qwen3TTSVoiceClone": [
        "target_text",
        "model_size",
        "language",
        "reference_text",
        "x_vector_only",
        "voice",
        "unload_models",
        "seed",
    ],
    # ── ComfyUI-RMBG (1038lab) ──
    # Source: ComfyUI-RMBG/1038lab AILab_FaceSegment.py INPUT_TYPES
    # (15 face-class BOOLEAN toggles + process_res/mask_blur/mask_offset/
    # invert_output/background/background_color).
    "FaceSegment": [
        "skin",
        "nose",
        "eyeglasses",
        "left_eye",
        "right_eye",
        "left_eyebrow",
        "right_eyebrow",
        "left_ear",
        "right_ear",
        "mouth",
        "upper_lip",
        "lower_lip",
        "hair",
        "earring",
        "neck",
        "process_res",
        "mask_blur",
        "mask_offset",
        "invert_output",
        "background",
        "background_color",
    ],
    # ── ComfyUI-Custom-Scripts (pythongosssss) ──
    # TODO: schema unknown — MarkdownNote is a UI display node. widget_0 holds
    # the cached markdown string but we cannot verify the field name because
    # the node has no Python-side INPUT_TYPES definition (pure JavaScript).
    # Using None so it surfaces as unused_widget_0 until source is confirmed.
    "MarkdownNote": [None],
}


def effective_widget_names_for_class(
    class_type: str,
    *,
    allow_object_info_fallback: bool = False,
) -> list[str | None]:
    """Return the ordered widget names for *class_type*.

    Curated ``WIDGET_SCHEMA`` always wins when present.  When no curated
    static entry exists and *allow_object_info_fallback* is ``True``, the
    raw object_info widget order is returned as a fallback.

    … note::
        This helper is narrowly scoped for the v2.1 ``narrate_template.py``
        codemod.  It does **not** replace the direct ``WIDGET_SCHEMA.get(…)``
        lookups used by ``widget_aliases.py``, ``emitter.py``, or ``parity.py``
        — global conversion / emission / parity behaviour is unchanged.
    """
    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        return list(curated)

    if allow_object_info_fallback:
        # Lazy import to avoid circular dependency at module level
        from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

        return list(object_info_widget_order(class_type))

    return []


__all__ = ["WIDGET_SCHEMA", "effective_widget_names_for_class"]
