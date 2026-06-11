from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ._lockfile import LockEntry

# read_lockfile is imported lazily inside _rich_lock_packs() so that
# monkeypatching node_packs.read_lockfile (the package-level attribute)
# correctly affects resolve_node_packs / get_known_node_packs behaviour.
# A module-level ``from ._lockfile import read_lockfile`` would bypass the
# package namespace and break the existing test suite's patching pattern.


@dataclass(frozen=True, slots=True)
class CustomNodePack:
    name: str
    repo: str
    classes: frozenset[str]
    pip_packages: tuple[str, ...] = ()
    class_schema_sha256: str | None = None


_STATIC_NODE_PACKS: tuple[CustomNodePack, ...] = (
    # comfy-core-fallback: Comfy built-in node types that have no object_info schema
    # but are handled by the emitter as FALLBACK_CLASS_TYPES.  Declaring them here
    # keeps `unresolved_class_types` quiet so port check does not emit false-positive
    # `unresolved_runtime_class` errors for these well-known built-in handles.
    #
    # Value primitives (PrimitiveBoolean, PrimitiveInt, PrimitiveFloat,
    # PrimitiveString, PrimitiveStringMultiline) are intentionally NOT declared
    # here because they are conversion-stripped by the resolver+emitter
    # double-gate: the resolver folds their literal values into consumer inputs
    # during port_convert_workflow, and the emitter's _prepare_workflow_for_emit
    # raises ConversionParityError if any RESOLVABLE_HELPER_CLASS_TYPES survive
    # to emission.  Declaring them in the fallback pack would mask a resolver bug.
    CustomNodePack(
        name="comfy-core-fallback",
        repo="https://github.com/comfyanonymous/ComfyUI.git",
        classes=frozenset(
            {
                "PrimitiveNode",
                "Reroute",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-WanVideoWrapper",
        repo="https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
        classes=frozenset(
            {
                "LoadWanVideoT5TextEncoder",
                "CreateCFGScheduleFloatList",
                "WanVideoBlockSwap",
                "WanVideoEncode",
                "WanVideoVAELoader",
                "WanVideoTorchCompileSettings",
                "WanVideoModelLoader",
                "WanVideoEmptyEmbeds",
                "WanVideoImageToVideoEncode",
                "WanVideoDecode",
                "WanVideoExperimentalArgs",
                "WanVideoEasyCache",
                "WanVideoSampler",
                "WanVideoTextEncode",
                "WanVideoTextEncodeCached",
                "WanVideoTextEmbedBridge",
                "WanVideoLoraSelect",
                "WanVideoLoraSelectMulti",
                "WanVideoSetBlockSwap",
                "WanVideoSetLoRAs",
                "WanVideoSLG",
                "WanVideoControlEmbeds",
                "WanVideoVACEEncode",
                "WanVideoVACEModelSelect",
                "WanVideoVACEStartToEndFrame",
                # Additional classes confirmed from object_info snapshot
                "WanVideoTeaCache",
                "WanVideoVRAMManagement",
                "WanVideoAddS2VEmbeds",
                "WanVideoClipVisionEncode",
                "WanVideoContextOptions",
                "WanVideoImageToVideoMultiTalk",
                "WanVideoReCamMasterCameraEmbed",
                "WanVideoReCamMasterDefaultCamera",
                "WanVideoReCamMasterGenerateOrbitCamera",
                "ReCamMasterPoseVisualizer",
                "MultiTalkModelLoader",
                "MultiTalkWav2VecEmbeds",
                "MultiTalkSilentEmbeds",
                "FantasyTalkingWav2VecEmbeds",
                "Wav2VecModelLoader",
                "DownloadAndLoadWav2VecModel",
                "NormalizeAudioLoudness",
            }
        ),
        pip_packages=("onnx", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="ComfyUI-LTXVideo",
        repo="https://github.com/Lightricks/ComfyUI-LTXVideo.git",
        classes=frozenset(
            {
                "LTXAVTextEncoderLoader",
                "LTX2AttentionTunerPatch",
                "LTX2_NAG",
                "LTXVConditioning",
                "LTXVImgToVideo",
                "LTXVImgToVideoInplaceKJ",
                "EmptyLTXVLatentVideo",
                "LTXVAudioVAELoader",
                "LTXVAudioVAEDecode",
                "LTXVChunkFeedForward",
                "LTXVConcatAVLatent",
                "LTXVCropGuides",
                "LTXVEmptyLatentAudio",
                "LTXVPreprocess",
                "LTXVScheduler",
                "LTXVSeparateAVLatent",
                "LatentUpscaleModelLoader",
                # Additional classes confirmed from object_info snapshot
                "GemmaAPITextEncode",
                "GetVideoComponents",
                "LTXAddVideoICLoRAGuide",
                "LTXAddVideoICLoRAGuideAdvanced",
                "LTXFloatToInt",
                "LTXICLoRALoaderModelOnly",
                "LTXVAddGuideAdvanced",
                "LTXVAddGuideAdvancedAttention",
                "LTXVAddLatentGuide",
                "LTXVAddLatents",
                "LTXVAudioVideoMask",
                "LTXVGemmaCLIPModelLoader",
                "LTXVImgToVideoConditionOnly",
                "LTXVLatentUpsampler",
                "LTXVPreprocessMasks",
                "LTXVSetVideoLatentNoiseMasks",
                "LTXVTiledVAEDecode",
                "LTXVAddGuideMulti",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-KJNodes",
        repo="https://github.com/kijai/ComfyUI-KJNodes.git",
        classes=frozenset(
            {
                "BlockifyMask",
                "DrawMaskOnImage",
                "ImageResizeKJv2",
                "PreviewAnimation",
                "GetImageRangeFromBatch",
                "GetImageSize",
                "GetImageSizeAndCount",
                "INTConstant",
                "LTXVAddGuide",
                "PathchSageAttentionKJ",
                "PointsEditor",
                "ResizeImagesByLongerEdge",
                "SimpleCalculatorKJ",
                "VAELoaderKJ",
                # Additional classes confirmed from object_info snapshot
                "AddLabel",
                "ColorMatch",
                "FloatConstant",
                "ImageBatchExtendWithOverlap",
                "ImageBatchMulti",
                "ImageConcatFromBatch",
                "ImageConcatMulti",
                "ImagePadKJ",
                "ImagePadForOutpaintMasked",
                "ImagePadForOutpaintTargetSize",
                "ImageResizeKJ",
                "InsertLatentToIndexed",
                "LazySwitchKJ",
                "LTX2MemoryEfficientSageAttentionPatch",
                "LTX2SamplingPreviewOverride",
                "LTXVAudioVideoMask",
                "LoadAndResizeImage",
                "LoadVideosFromFolder",
                "MaskPreview",
                "VRAM_Debug",
                "WidgetToString",
            }
        ),
        pip_packages=("matplotlib",),
    ),
    CustomNodePack(
        name="ComfyUI-VideoHelperSuite",
        repo="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        classes=frozenset({
            "VHS_LoadVideo",
            "VHS_VideoCombine",
            "VHS_LoadAudio",
            "VHS_LoadAudioUpload",
            "VHS_LoadVideoFFmpeg",
            "VHS_LoadVideoFFmpegPath",
            "VHS_SelectEveryNthImage",
            "VHS_SelectEveryNthLatent",
            "VHS_SelectEveryNthMask",
            "VHS_SplitImages",
            "VHS_VideoInfo",
            "VHS_VideoInfoLoaded",
            "VHS_VideoInfoSource",
        }),
    ),
    CustomNodePack(
        name="ComfyUI-segment-anything-2",
        repo="https://github.com/kijai/ComfyUI-segment-anything-2.git",
        classes=frozenset(
            {
                "DownloadAndLoadSAM2Model",
                "Sam2Segmentation",
                "Sam2AutoSegmentation",
                "Sam2VideoSegmentation",
                "Sam2VideoSegmentationAddPoints",
                "Florence2toCoordinates",
            }
        ),
        pip_packages=("opencv-python-headless",),
    ),
    CustomNodePack(
        name="ComfyUI-WanAnimatePreprocess",
        repo="https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git",
        classes=frozenset(
            {
                "OnnxDetectionModelLoader",
                "PoseAndFaceDetection",
                "DrawViTPose",
                "PoseRetargetPromptHelper",
                "PoseDetectionOneToAllAnimation",
            }
        ),
        pip_packages=("onnx", "onnxruntime-gpu", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="comfyui_controlnet_aux",
        repo="https://github.com/Fannovel16/comfyui_controlnet_aux.git",
        classes=frozenset({
            "DWPreprocessor",
            "CannyEdgePreprocessor",
            "DepthAnythingPreprocessor",
        }),
        pip_packages=("onnxruntime", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="ComfyUI-DepthAnythingV2",
        repo="https://github.com/kijai/ComfyUI-DepthAnythingV2.git",
        classes=frozenset(
            {
                "DownloadAndLoadDepthAnythingV2Model",
                "DepthAnything_V2",
                "LoadVideoDepthAnythingModel",
                "VideoDepthAnythingProcess",
                "VideoDepthAnythingOutput",
            }
        ),
        pip_packages=("transformers", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="ComfyUI-MelBandRoformer",
        repo="https://github.com/kijai/ComfyUI-MelBandRoformer.git",
        classes=frozenset(
            {
                "MelBandRoFormerModelLoader",
                "MelBandRoFormerSampler",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-Florence2",
        repo="https://github.com/kijai/ComfyUI-Florence2.git",
        classes=frozenset(
            {
                "DownloadAndLoadFlorence2Model",
                "Florence2Run",
            }
        ),
        pip_packages=("transformers", "einops", "timm"),
    ),
    CustomNodePack(
        name="ComfyUI-GIMM-VFI",
        repo="https://github.com/kijai/ComfyUI-GIMM-VFI.git",
        classes=frozenset(
            {
                "DownloadAndLoadGIMMVFIModel",
                "GIMMVFI_interpolate",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-Custom-Scripts",
        repo="https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git",
        classes=frozenset(
            {
                "ShowText|pysssss",
                "MathExpression|pysssss",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-Easy-Use",
        repo="https://github.com/yolain/ComfyUI-Easy-Use.git",
        classes=frozenset(
            {
                "easy showAnything",
                "easy cleanGpuUsed",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI_Comfyroll_CustomNodes",
        repo="https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git",
        classes=frozenset(
            {
                "CR Float To Integer",
            }
        ),
    ),
    CustomNodePack(
        name="comfy_mtb",
        repo="https://github.com/melMass/comfy_mtb.git",
        classes=frozenset(
            {
                "Audio Duration (mtb)",
                "Audio To Text (mtb)",
                "Load Whisper (mtb)",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-GGUF",
        repo="https://github.com/city96/ComfyUI-GGUF.git",
        classes=frozenset({"DualCLIPLoaderGGUF", "UnetLoaderGGUF"}),
        pip_packages=("gguf",),
    ),
    CustomNodePack(
        name="rgthree-comfy",
        repo="https://github.com/rgthree/rgthree-comfy.git",
        classes=frozenset(
            {
                "Any Switch (rgthree)",
                "Fast Groups Bypasser (rgthree)",
                "Fast Groups Muter (rgthree)",
                "GetNode",
                "Label (rgthree)",
                "Power Lora Loader (rgthree)",
                "Seed (rgthree)",
                "SetNode",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-Qwen3-TTS",
        repo="https://github.com/DarioFT/ComfyUI-Qwen3-TTS.git",
        classes=frozenset(
            {
                "Qwen3Loader",
                "Qwen3CustomVoice",
                "Qwen3VoiceDesign",
                "Qwen3VoiceClone",
                "Qwen3PromptMaker",
                "Qwen3SavePrompt",
                "Qwen3LoadPrompt",
                "Qwen3DatasetFromFolder",
                "Qwen3DataPrep",
                "Qwen3FineTune",
                "Qwen3AudioCompare",
            }
        ),
        pip_packages=("qwen-tts", "modelscope", "soundfile", "librosa", "accelerate"),
    ),
    CustomNodePack(
        name="ComfyUI-QwenTTS",
        repo="https://github.com/1038lab/ComfyUI-QwenTTS.git",
        classes=frozenset(
            {
                "AILab_Qwen3TTSCustomVoice",
                "AILab_Qwen3TTSCustomVoice_Advanced",
                "AILab_Qwen3TTSVoiceDesign",
                "AILab_Qwen3TTSVoiceDesign_Advanced",
                "AILab_Qwen3TTSVoiceClone",
                "AILab_Qwen3TTSVoiceClone_Advanced",
                "AILab_Qwen3TTSVoicesLibrary",
                "AILab_Qwen3TTSLoadVoice",
                "AILab_Qwen3TTSWhisperSTT",
                "AILab_Qwen3TTSVoiceInstruct",
                "AILab_Qwen3TTSVoiceInstructZH",
            }
        ),
        pip_packages=("qwen-tts", "openai-whisper", "soundfile", "librosa", "tiktoken", "accelerate"),
    ),
)


def _pack_from_lock_entry(entry: LockEntry) -> CustomNodePack | None:
    if not entry.class_set:
        return None
    repo = entry.url or entry.path
    if not repo:
        return None
    return CustomNodePack(
        name=entry.name,
        repo=repo,
        classes=frozenset(entry.class_set),
        pip_packages=tuple(entry.pip_packages),
        class_schema_sha256=entry.class_schema_sha256 or entry.schema_hash,
    )


def _rich_lock_packs(lockfile_path: Path = Path("custom_nodes.lock")) -> tuple[CustomNodePack, ...]:
    from vibecomfy.node_packs import read_lockfile  # see module-level comment

    try:
        entries = read_lockfile(lockfile_path)
    except (OSError, ValueError):
        return ()
    return tuple(pack for entry in entries if (pack := _pack_from_lock_entry(entry)) is not None)


def _known_node_packs(lockfile_path: Path = Path("custom_nodes.lock")) -> tuple[CustomNodePack, ...]:
    by_name = {pack.name: pack for pack in _STATIC_NODE_PACKS}
    for pack in _rich_lock_packs(lockfile_path):
        by_name[pack.name] = pack
    return tuple(sorted(by_name.values(), key=lambda pack: pack.name.lower()))


def _lockfile_fingerprint(lockfile_path: Path) -> tuple[str, bool, int, int]:
    resolved = lockfile_path.expanduser().resolve(strict=False)
    try:
        stat = resolved.stat()
    except OSError:
        return (str(resolved), False, 0, 0)
    return (str(resolved), True, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=16)
def _cached_known_node_packs(
    resolved_lockfile_path: str,
    exists: bool,
    mtime_ns: int,
    size: int,
) -> tuple[CustomNodePack, ...]:
    del exists, mtime_ns, size
    return _known_node_packs(Path(resolved_lockfile_path))


def get_known_node_packs(lockfile_path: Path = Path("custom_nodes.lock")) -> tuple[CustomNodePack, ...]:
    """Return known custom-node packs with lockfile-aware in-process caching.

    ``custom_nodes.lock`` changes are reflected in the same interpreter when the
    resolved file path, existence, ``mtime_ns``, or size changes. Edits to this
    module's static pack seed list still require a process restart because that
    source is imported only once per interpreter.
    """
    return _cached_known_node_packs(*_lockfile_fingerprint(lockfile_path))


def clear_known_node_packs_cache() -> None:
    """Clear the lazy node-pack catalog cache for tests and diagnostics."""
    _cached_known_node_packs.cache_clear()


def resolve_node_packs(class_types: set[str]) -> list[CustomNodePack]:
    packs = [pack for pack in get_known_node_packs() if class_types & pack.classes]
    return sorted(packs, key=lambda pack: pack.name.lower())


def unresolved_class_types(class_types: set[str]) -> list[str]:
    packs = get_known_node_packs()
    covered = set().union(*(pack.classes for pack in packs)) if packs else set()
    return sorted(class_types - covered)
