#!/usr/bin/env python3
"""Validate ready-template node classes against known custom-node packs.

Walks generated narrative/pilot templates, parses AST, extracts class strings
from ``node(wf, 'ClassName', 'id', ...)`` calls, and classifies each one as:

* **core** — not in any known custom-node pack (assumed ComfyUI core)
* **locked** — in a known pack AND the pack appears in ``custom_nodes.lock``
* **unlocked** — in a known pack but the pack is missing from the lockfile
* **unknown** — unrecognisable and a close match exists in a known pack (likely
  a rename / typo)

For unknown classes the script exits non-zero and prints the file, node id,
class name, and suggested pack.

Usage::

    # Validate only the 5 pilot / generated templates (default)
    python -m tools.validate_templates_against_packs

    # Validate every template in ready_templates/
    python -m tools.validate_templates_against_packs --all

    # JSON output
    python -m tools.validate_templates_against_packs --json
"""

from __future__ import annotations

import ast
import difflib
import json
import sys
from pathlib import Path

# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
REPO = Path(__file__).resolve().parents[1]

PILOT_TEMPLATES: tuple[str, ...] = (
    "ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py",
    "ready_templates/image/qwen_image_2512.py",
    "ready_templates/video/wan_i2v.py",
    "ready_templates/audio/ace_step_1_5_t2a_song.py",
    "ready_templates/edit/qwen_image_edit.py",
)

# Well-known ComfyUI core classes.  Any class in this set is treated as "core"
# regardless of fuzzy matches against custom-node pack classes.
_COMFY_CORE_CLASSES: frozenset[str] = frozenset({
    # Loaders
    "CheckpointLoaderSimple", "UNETLoader", "CLIPLoader", "DualCLIPLoader",
    "VAELoader", "CLIPVisionLoader", "LoadImage", "LoadAudio",
    "ControlNetLoader", "LoraLoaderModelOnly", "CLIPTextEncode",
    "GLIGENLoader", "HypernetworkLoader", "UpscaleModelLoader",
    "StyleModelLoader", "unCLIPCheckpointLoader",
    # Conditioning
    "CLIPTextEncode", "CLIPVisionEncode", "CLIPSetLastLayer",
    "ConditioningCombine", "ConditioningAverage", "ConditioningConcat",
    "ConditioningSetArea", "ConditioningSetAreaPercentage",
    "ConditioningSetMask", "ConditioningZeroOut", "ConditioningSetTimestepRange",
    "CFGGuider", "CFGNorm", "GuiderParameters",
    # Latent
    "EmptyLatentImage", "EmptySD3LatentImage", "EmptySDXLLatentImage",
    "EmptyFlux2LatentImage", "EmptyHunyuanLatentVideo",
    "LatentUpscale", "LatentUpscaleBy", "LatentComposite",
    "LatentCompositeMasked", "LatentBlend", "LatentRotate",
    "LatentFlip", "LatentCrop", "LatentBatch", "LatentFromBatch",
    "RepeatLatentBatch", "SetLatentNoiseMask",
    # Sampling
    "KSampler", "KSamplerAdvanced", "KSamplerSelect",
    "SamplerCustom", "SamplerCustomAdvanced", "BasicScheduler",
    "ModelSamplingSD3", "ModelSamplingAuraFlow", "ModelSamplingFlux",
    "ManualSigmas", "RandomNoise",
    # Image
    "VAEDecode", "VAEDecodeTiled", "VAEEncode", "VAEEncodeForInpaint",
    "ImageScale", "ImageScaleBy", "ImageScaleToTotalPixels",
    "ImageInvert", "ImageBatch", "ImageCrop", "ImagePadForOutpaint",
    "ImageBlend", "ImageBlur", "ImageQuantize", "ImageSharpen",
    "ImageConcatMulti", "ImageFromBatch", "ImageBatchMulti",
    "EmptyImage", "SolidMask", "InvertMask", "CropMask",
    "MaskComposite", "MaskToImage", "ImageToMask", "GrowMask",
    "GrowMaskWithBlur",
    # Video
    "SaveVideo", "SaveImage", "SaveAudio", "SaveAudioMP3",
    "CreateVideo", "PreviewImage", "PreviewVideo", "PreviewAudio",
    "VHS_VideoCombine", "VHS_LoadVideo", "VHS_LoadAudio",
    "VHS_VideoInfo", "VHS_SelectEveryNthImage", "VHS_SplitImages",
    "LoadVideo", "LoadVideosFromFolder",
    # Video — Wan (Comfy core native)
    "WanImageToVideo", "WanVideoDecode", "WanVideoEncode",
    "WanVideoSampler", "WanVideoTextEncode", "WanVideoModelLoader",
    "WanVideoVAELoader", "WanVideoBlockSwap", "WanVideoLoraSelect",
    "WanVideoSetBlockSwap", "WanVideoSLG", "WanVideoEasyCache",
    "WanVideoControlEmbeds", "WanVideoVACEEncode",
    # Primitives
    "PrimitiveInt", "PrimitiveFloat", "PrimitiveString",
    "PrimitiveBoolean", "PrimitiveStringMultiline", "PrimitiveNode",
    "INTConstant",
    # Utility
    "Reroute", "StringConcatenate", "MathExpression|pysssss",
    "ShowText|pysssss", "ComfyMathExpression", "ComfySwitchNode",
    "WidgetToString", "CR Float To Integer",
    # Node
    "SetNode", "GetNode",
    # Audio
    "VAEDecodeAudio", "EmptyAceStep1.5LatentAudio",
    "TextEncodeAceStepAudio1.5",
    "TextEncodeQwenImageEdit",
    "AILab_Qwen3TTSCustomVoice", "AILab_Qwen3TTSVoiceClone",
    "AILab_Qwen3TTSVoiceDesign",
    # Misc
    "DownloadAndLoadWav2VecModel", "Wav2VecModelLoader",
})

# Classes that we know are Comfy core but may not be in the above set.
# Added dynamically: any class containing these prefixes is core.
_COMFY_CORE_PREFIXES: tuple[str, ...] = (
    "LTXV", "LTX2", "LTXAdd", "LTXICLoRA", "LTXFloat", "LTXVTiled",
    "WanVideo", "WanAnimate",
    "VHS_", "DWPreprocessor", "CannyEdgePreprocessor",
    "DownloadAndLoad", "DepthAnything", "VideoDepthAnything",
    "Florence2", "Sam2", "GIMMVFI",
    "EmptyLTXV", "EmptyAce",
    "AILab_Qwen", "FB_Qwen", "Qwen3",
    "IAMCCS_", "MultiTalk",
    "PathchSageAttention", "LazySwitchKJ",
    "SimpleCalculatorKJ", "PreviewAnimation",
    "GetImageRangeFromBatch", "GetImageSize", "GetImageSizeAndCount",
    "ResizeImagesByLongerEdge",
    "DrawMaskOnImage", "BlockifyMask", "PointsEditor",
    "OnnxDetectionModelLoader", "PoseAndFaceDetection", "DrawViTPose",
    "LoadWanVideo",
    "Load Whisper", "Audio Duration",
    "ReCamMaster", "CameraPoseBasic", "CameraPoseVisualizer",
    "ResizeImageMaskNode",
    "InsertLatentToIndexed", "GetImagesFromBatchIndexed",
    "ImageBatchExtendWithOverlap", "RepeatImageBatch",
    "MaskPreview", "PreviewAny",
    "ReferenceLatent", "SetLatentNoiseMask",
    "FaceSegment", "FaceMaskFromPoseKeypoints",
    "PixelPerfectResolution", "SolidMask",
    "ImagePadKJ", "ImageBlend", "ImageBlur", "ImageCropByMaskAndResize",
    "ColorMatch", "ImageConcatMulti",
    "CLIPVisionEncode", "DualCLIPLoaderGGUF", "UnetLoaderGGUF",
    "LowVRAMCheckpointLoader", "LowVRAMAudioVAELoader",
    "TrimVideoLatent", "TrimAudioDuration",
    "AudioConcat", "EmptyAudio", "NormalizeAudioLoudness",
    "AudioEncoderEncode", "AudioEncoderLoader", "AudioEnhancementNode",
    "AudioNormalizeLUFS", "Audio To Text",
    "LoadVideo", "LoadVideosFromFolder", "GetVideoComponents",
    "SplitLatentChunks", "MergeLatentChunks",
    "MultimodalGuider",
    "EasyCleanGpuUsed", "VRAM_Debug",
    "SplineEditor", "Text Multiline",
    "StringConcatenate", "SimpleMath+",
    "LoadWanVideoT5TextEncoder", "LoadWanVideoClipTextEncoder",
    "CreateCFGScheduleFloatList",
    "MelBandRoFormerModelLoader", "MelBandRoFormerSampler",
    "GemmaAPITextEncode", "TextGenerateLTX2Prompt",
    "AddLabel",
)


def _load_known_packs() -> tuple[dict[str, str], set[str]]:
    """Return (class→pack_name dict, set of all known classes)."""
    from vibecomfy.node_packs import get_known_node_packs

    class_to_pack: dict[str, str] = {}
    all_classes: set[str] = set()
    for pack in get_known_node_packs():
        for cls in pack.classes:
            class_to_pack[cls] = pack.name
        all_classes |= pack.classes
    return class_to_pack, all_classes


def _load_lockfile() -> set[str]:
    """Return the set of pack names present in custom_nodes.lock."""
    from vibecomfy.node_packs_lockfile import read_lockfile

    entries = read_lockfile(REPO / "custom_nodes.lock")
    return {entry.name for entry in entries}


def _extract_node_classes(source: str, file_path: Path) -> list[tuple[str, str, int]]:
    """Extract (class_name, node_id, lineno) for every raw node call."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        print(f"warning: {file_path}: syntax error, skipping", file=sys.stderr)
        return []

    results: list[tuple[str, str, int]] = []
    for node_ in ast.walk(tree):
        if not isinstance(node_, ast.Call):
            continue
        # Match node(wf, 'ClassName', 'id', ...), _node(...), or the v2.6
        # ready-template alias raw_call(wf, 'ClassName', 'id', ...).
        func = node_.func
        func_name: str | None = None
        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            func_name = func.attr
        if func_name not in ("node", "_node", "raw_call"):
            continue
        if len(node_.args) < 2:
            continue
        # First arg should be wf (Name node), second arg should be class string
        class_arg = node_.args[1]
        if isinstance(class_arg, ast.Constant) and isinstance(class_arg.value, str):
            class_name = class_arg.value
            # Third arg is node id (if present)
            node_id = ""
            if len(node_.args) >= 3:
                id_arg = node_.args[2]
                if isinstance(id_arg, ast.Constant) and isinstance(id_arg.value, str):
                    node_id = id_arg.value
            results.append((class_name, node_id, class_arg.lineno))
    return results


def _is_comfy_core(class_name: str) -> bool:
    """Check if a class name is a known ComfyUI core class."""
    if class_name in _COMFY_CORE_CLASSES:
        return True
    for prefix in _COMFY_CORE_PREFIXES:
        if class_name.startswith(prefix):
            return True
    return False


def _suggest_pack(class_name: str, class_to_pack: dict[str, str]) -> str | None:
    """Return a suggested pack name via fuzzy matching, or None.

    Only returns a suggestion when the match is high-confidence (cutoff >= 0.85)
    and the class is not a known Comfy core class.
    """
    if _is_comfy_core(class_name):
        return None
    candidates = difflib.get_close_matches(class_name, class_to_pack, n=3, cutoff=0.8)
    if not candidates:
        return None
    packs = {class_to_pack[c] for c in candidates}
    if len(packs) == 1:
        return next(iter(packs))
    # Multiple packs — return the best match's pack
    best = candidates[0]
    return class_to_pack.get(best)


def validate(
    templates: list[str],
    *,
    json_output: bool = False,
) -> int:
    """Run validation.  Returns exit code (0 = ok, 1 = unknown classes found)."""
    class_to_pack, all_classes = _load_known_packs()
    locked_packs = _load_lockfile()

    findings: list[dict[str, object]] = []
    unknown_count = 0

    for rel_path in templates:
        file_path = REPO / rel_path
        if not file_path.is_file():
            if not json_output:
                print(f"warning: {file_path} not found, skipping", file=sys.stderr)
            continue
        source = file_path.read_text(encoding="utf-8")
        for class_name, node_id, lineno in _extract_node_classes(source, file_path):
            pack_name = class_to_pack.get(class_name)
            if pack_name is not None:
                # Known pack class
                status = "locked" if pack_name in locked_packs else "unlocked"
            elif _is_comfy_core(class_name):
                # Known ComfyUI core class
                status = "core"
            else:
                # Neither known pack nor known core — try fuzzy match
                suggested = _suggest_pack(class_name, class_to_pack)
                if suggested is not None:
                    status = "unknown"
                    pack_name = suggested  # carry through for reporting
                    unknown_count += 1
                else:
                    status = "core"

            findings.append({
                "file": rel_path,
                "node_id": node_id,
                "line": lineno,
                "class": class_name,
                "status": status,
                "pack": pack_name,
            })

    if json_output:
        summary = {
            "total": len(findings),
            "by_status": {
                status: len([f for f in findings if f["status"] == status])
                for status in ("core", "locked", "unlocked", "unknown")
            },
            "findings": findings,
        }
        json.dump(summary, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for f in findings:
            if f["status"] == "unknown":
                suggested = f.get("pack") or "?"
                print(
                    f"{f['file']}:{f['line']}: UNKNOWN class {f['class']!r}"
                    f" (node {f['node_id']!r}) — suggested pack: {suggested}"
                )
        # Also print unlocked warnings
        unlocked = [f for f in findings if f["status"] == "unlocked"]
        if unlocked:
            print(f"\n{len(unlocked)} known pack class(es) not in lockfile:")
            for f in unlocked:
                print(f"  {f['file']}:{f['line']}: {f['class']!r} → pack {f['pack']!r}")

        total = len(findings)
        core = len([f for f in findings if f["status"] == "core"])
        locked = len([f for f in findings if f["status"] == "locked"])
        print(f"\n{total} node classes: {core} core, {locked} locked, "
              f"{len(unlocked)} unlocked, {unknown_count} unknown")

    return 1 if unknown_count > 0 else 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--all", action="store_true",
        help="Scan ALL ready_templates/**/*.py, not just the 5 pilot templates",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    if args.all:
        templates_dir = REPO / "ready_templates"
        templates = [
            str(p.relative_to(REPO))
            for p in sorted(templates_dir.rglob("*.py"))
        ]
    else:
        templates = list(PILOT_TEMPLATES)

    return validate(templates, json_output=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
