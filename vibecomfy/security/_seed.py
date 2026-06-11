"""
Mirrored seed data for the capability taxonomy.

This module contains LITERAL copies of class lists from other packages
so that ``vibecomfy.security`` never imports from ``vibecomfy.porting``,
``vibecomfy.runtime``, ``vibecomfy.registry``, or ``vibecomfy.analysis``.

The one-way dependency rule is enforced by the subprocess import-isolation
test in ``tests/security/test_no_cross_layer_import.py``.

DO NOT import from vibecomfy.porting, .runtime, .registry, or .analysis here.
"""

from __future__ import annotations

import re

# ── Literal copy of OUTPUT_NODE_NAMES from vibecomfy/metadata.py:12 ──────────
OUTPUT_NODE_NAMES: frozenset[str] = frozenset(
    {
        "SaveImage",
        "PreviewImage",
        "SaveAnimatedWEBP",
        "SaveWEBM",
        "VHS_VideoCombine",
        "SaveVideo",
        "SaveAudio",
        "SaveAudioMP3",
    }
)

# ── Literal copy of _OUTPUT_CLASSES.keys() from vibecomfy/porting/emitter.py:3196 ─
_OUTPUT_CLASSES_KEYS: frozenset[str] = frozenset(
    {
        "SaveImage",
        "PreviewImage",
        "SaveVideo",
        "VHS_VideoCombine",
        "SaveAudio",
        "SaveAudioMP3",
    }
)

# Back-compat alias from the main hardening branch.
OUTPUT_CLASS_NAMES: frozenset[str] = _OUTPUT_CLASSES_KEYS

# ── Literal copy of all class names from _STATIC_NODE_PACKS in vibecomfy/node_packs.py:19 ─
ALL_STATIC_PACK_CLASSES: frozenset[str] = frozenset(
    {
        # comfy-core-fallback
        "PrimitiveNode",
        "Reroute",
        # ComfyUI-WanVideoWrapper
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
        # ComfyUI-LTXVideo
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
        # ComfyUI-KJNodes
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
        # ComfyUI-VideoHelperSuite
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
        # ComfyUI-segment-anything-2
        "DownloadAndLoadSAM2Model",
        "Sam2Segmentation",
        "Sam2AutoSegmentation",
        "Sam2VideoSegmentation",
        "Sam2VideoSegmentationAddPoints",
        "Florence2toCoordinates",
        # ComfyUI-WanAnimatePreprocess
        "OnnxDetectionModelLoader",
        "PoseAndFaceDetection",
        "DrawViTPose",
        "PoseRetargetPromptHelper",
        "PoseDetectionOneToAllAnimation",
        # comfyui_controlnet_aux
        "DWPreprocessor",
        "CannyEdgePreprocessor",
        "DepthAnythingPreprocessor",
        # ComfyUI-DepthAnythingV2
        "DownloadAndLoadDepthAnythingV2Model",
        "DepthAnything_V2",
        "LoadVideoDepthAnythingModel",
        "VideoDepthAnythingProcess",
        "VideoDepthAnythingOutput",
        # ComfyUI-MelBandRoformer
        "MelBandRoFormerModelLoader",
        "MelBandRoFormerSampler",
        # ComfyUI-Florence2
        "DownloadAndLoadFlorence2Model",
        "Florence2Run",
        # ComfyUI-GIMM-VFI
        "DownloadAndLoadGIMMVFIModel",
        "GIMMVFI_interpolate",
        # ComfyUI-Custom-Scripts
        "ShowText|pysssss",
        "MathExpression|pysssss",
        # ComfyUI-Easy-Use
        "easy showAnything",
        "easy cleanGpuUsed",
        # ComfyUI_Comfyroll_CustomNodes
        "CR Float To Integer",
        # comfy_mtb
        "Audio Duration (mtb)",
        "Audio To Text (mtb)",
        "Load Whisper (mtb)",
        # ComfyUI-GGUF
        "DualCLIPLoaderGGUF",
        "UnetLoaderGGUF",
        # rgthree-comfy
        "Any Switch (rgthree)",
        "Fast Groups Bypasser (rgthree)",
        "Fast Groups Muter (rgthree)",
        "GetNode",
        "Label (rgthree)",
        "Power Lora Loader (rgthree)",
        "Seed (rgthree)",
        "SetNode",
        # ComfyUI-Qwen3-TTS
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
        # ComfyUI-QwenTTS
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
)

# ── Union of all seeded class names ──────────────────────────────────────────
ALL_SEEDED: frozenset[str] = OUTPUT_NODE_NAMES | OUTPUT_CLASS_NAMES | ALL_STATIC_PACK_CLASSES

# ── Curated keyword pattern for side-effecting node detection ─────────────────
# Matches nodes whose CLASS NAME indicates side effects at edit time.
# The regex is anchored at both ends to avoid partial false positives.
# Corrected from the literal task pattern ^(Save|Preview|…) to ^(Save.*|Preview.*)
# so that SaveImage, SaveVideo, PreviewAnimation, etc. are all matched.
_SIDE_EFFECTING_RE: re.Pattern[str] = re.compile(
    r"^(Save.*|Preview.*|Download.*Load|.*Expression|.*Eval|VHS_VideoCombine|VHS_LoadVideo.*)$"
)

# ── Well-known core ComfyUI passthrough nodes ───────────────────────────────
# These are explicitly tagged passthrough because they are pure graph nodes
# with no dangerous I/O or eval surface at add time (see capability_taxonomy.md §1).
# They are needed here so the taxonomy can return passthrough for common built-in
# class types that are not in _STATIC_NODE_PACKS (which only covers custom-node packs).
KNOWN_PASSTHROUGH: frozenset[str] = frozenset(
    {
        "CLIPTextEncode",
        "CLIPTextEncodeSDXL",
        "CLIPTextEncodeFlux",
        "KSampler",
        "KSamplerAdvanced",
        "SamplerCustom",
        "SamplerCustomAdvanced",
        "VAEDecode",
        "VAEDecodeTiled",
        "VAEEncode",
        "VAEEncodeForInpaint",
        "VAEEncodeTiled",
        "CheckpointLoaderSimple",
        "CheckpointLoader",
        "CLIPLoader",
        "DualCLIPLoader",
        "UNETLoader",
        "ControlNetLoader",
        "LoraLoader",
        "LoraLoaderModelOnly",
        "CLIPSetLastLayer",
        "ConditioningCombine",
        "ConditioningAverage",
        "ConditioningConcat",
        "ConditioningSetArea",
        "ConditioningSetMask",
        "EmptyLatentImage",
        "LatentUpscale",
        "LatentUpscaleBy",
        "LatentComposite",
        "LatentCompositeMasked",
        "LatentRotate",
        "LatentFlip",
        "LatentCrop",
        "ImageScale",
        "ImageScaleBy",
        "ImageUpscaleWithModel",
        "UpscaleModelLoader",
        "LoadImage",
        "InvertMask",
        "CropMask",
        "FeatherMask",
        "GrowMask",
        "MaskComposite",
        "ImageCompositeMasked",
        "ImageBlend",
        "ImageBatch",
        "ImageToMask",
        "MaskToImage",
        "SetLatentNoiseMask",
        "FreeU",
        "FreeU_V2",
        "ModelSamplingDiscrete",
        "ModelSamplingContinuousEDM",
        "ModelSamplingStableCascade",
        "ModelSamplingSD3",
        "ModelSamplingAuraFlow",
        "ModelSamplingFlux",
        "BasicScheduler",
        "BasicGuider",
        "RandomNoise",
        "DisableNoise",
        "SplitSigmas",
        "SplitSigmasDenoise",
        "UNETSelfAttentionMultiply",
        "UNETCrossAttentionMultiply",
        "UNETTemporalAttentionMultiply",
        "StableCascade_StageB_Conditioning",
        "StableCascade_StageC_VAEEncode",
        "StableCascade_SuperResolutionControlnet",
        "StyleModelLoader",
        "StyleModelApply",
        "unCLIPConditioning",
        "GLIGENLoader",
        "GLIGENTextBoxApply",
        "PerturbedAttentionGuidance",
        "VideoLinearCFGGuidance",
        "ConditioningZeroOut",
        "ConditioningSetTimestepRange",
        "ConditioningSetAreaPercentage",
        "ConditioningSetAreaStrength",
        "HypernetworkLoader",
        "Note",
        "PrimitiveNode",
        "Reroute",
        "CR Float To Integer",
        "Fast Groups Bypasser (rgthree)",
        "Fast Groups Muter (rgthree)",
        "Any Switch (rgthree)",
        "Label (rgthree)",
        "Seed (rgthree)",
        "LazySwitchKJ",
        "WidgetToString",
        "INTConstant",
        "FloatConstant",
    }
)


def is_side_effecting_pattern(class_type: str) -> bool:
    """Return True if the class_type matches the side-effecting keyword pattern."""
    return bool(_SIDE_EFFECTING_RE.match(class_type))
