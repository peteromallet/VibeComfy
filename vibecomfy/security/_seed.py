"""Literal mirrors of output-class lists from metadata.py and porting/emitter.py.

These lists are intentionally copied verbatim — never imported from their
source modules — so that security/ has no dependency on analysis, runtime,
porting, or registry.  Any update to the originals must be reflected here
manually (enforced by tests/security/test_capabilities.py).
"""
from __future__ import annotations

# Mirror of vibecomfy/metadata.py OUTPUT_NODE_NAMES (set literal at line 12).
OUTPUT_NODE_NAMES: frozenset[str] = frozenset({
    "SaveImage",
    "PreviewImage",
    "SaveAnimatedWEBP",
    "SaveWEBM",
    "VHS_VideoCombine",
    "SaveVideo",
    "SaveAudio",
    "SaveAudioMP3",
})

# Mirror of vibecomfy/porting/emitter.py _OUTPUT_CLASSES keys (dict at line ~3196).
OUTPUT_CLASS_NAMES: frozenset[str] = frozenset({
    "SaveImage",
    "PreviewImage",
    "SaveVideo",
    "VHS_VideoCombine",
    "SaveAudio",
    "SaveAudioMP3",
})

# Well-known core ComfyUI nodes that are definitively passthrough (no side effects).
# These are enumerated explicitly so that capabilities_for() returns passthrough for
# them rather than the quarantine default that fires for truly unknown classes.
KNOWN_PASSTHROUGH: frozenset[str] = frozenset({
    # Encoding / conditioning
    "CLIPTextEncode",
    "CLIPTextEncodeSDXL",
    "CLIPVisionEncode",
    "ConditioningAverage",
    "ConditioningCombine",
    "ConditioningConcat",
    "ConditioningSetArea",
    "ConditioningSetMask",
    "ConditioningZeroOut",
    # Sampling
    "KSampler",
    "KSamplerAdvanced",
    "SamplerCustom",
    "SamplerCustomAdvanced",
    # Loaders (read-only at the ComfyUI side-effect level)
    "CheckpointLoaderSimple",
    "CLIPLoader",
    "ControlNetLoader",
    "DualCLIPLoader",
    "IPAdapterModelLoader",
    "LoraLoader",
    "LoraLoaderModelOnly",
    "UNETLoader",
    "VAELoader",
    # Decode / encode
    "VAEDecode",
    "VAEDecodeTiled",
    "VAEEncode",
    "VAEEncodeTiled",
    # Latent utilities
    "EmptyLatentImage",
    "EmptySD3LatentImage",
    "LatentBlend",
    "LatentComposite",
    "LatentFlip",
    "LatentRotate",
    "LatentUpscale",
    "LatentUpscaleBy",
    # Image utilities
    "ImageScale",
    "ImageScaleBy",
    "ImageUpscaleWithModel",
    "UpscaleModelLoader",
    # Misc
    "Note",
    "PrimitiveNode",
})

# Union of all lists — the full seeded corpus.
ALL_SEEDED: frozenset[str] = OUTPUT_NODE_NAMES | OUTPUT_CLASS_NAMES | KNOWN_PASSTHROUGH
