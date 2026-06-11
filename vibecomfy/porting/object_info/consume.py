"""Lazy consumer for the structured object_info cache.

Reads per-pack JSON files and ``index.json`` on first access.
All public functions are deterministic and do not require ComfyUI or network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CACHE_DIR: Path = Path(__file__).resolve().parent.parent / "cache" / "object_info"
INDEX_PATH: Path = CACHE_DIR / "index.json"

# ``comfy_metadata.json`` lives at the package root (vibecomfy/) and pins the
# ComfyUI snapshot the object_info cache was captured against. Used only to make
# fail-closed schema errors actionable ("refresh the snapshot").
METADATA_PATH: Path = Path(__file__).resolve().parent.parent.parent / "comfy_metadata.json"

# ComfyUI types that are link-only sockets — NOT widget controls.
# These are excluded from object_info_widget_order.
_WIDGET_LIKE_TYPES: frozenset[str] = frozenset({
    "MODEL", "CLIP", "VAE", "IMAGE", "LATENT", "CONDITIONING", "MASK",
    "AUDIO", "VIDEO", "hidden",
})

_CURATED_WIDGET_ORDERS: dict[str, list[str | None]] = {
    # The checked-in object_info cache does not include LTX2_NAG in all
    # environments. Curate only the missing fallback slot; WIDGET_SCHEMA owns
    # the first three widget names and asks object_info for index 3.
    "LTX2_NAG": ["nag_scale", "nag_alpha", "nag_tau", "inplace"],
}

_CURATED_OUTPUTS: dict[str, list[dict[str, str]]] = {
    # Core classes used by checked-in tests and v2.3 generated templates. These
    # labels are stable ComfyUI socket names and keep named handles available
    # when the large generated object_info cache is not committed.
    "CLIPTextEncode": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "CLIPLoader": [{"name": "CLIP", "type": "CLIP"}],
    "CLIPVisionEncode": [{"name": "CLIP_VISION_OUTPUT", "type": "CLIP_VISION_OUTPUT"}],
    "CLIPVisionLoader": [{"name": "CLIP_VISION", "type": "CLIP_VISION"}],
    "CFGGuider": [{"name": "GUIDER", "type": "GUIDER"}],
    "CFGNorm": [{"name": "patched_model", "type": "MODEL"}],
    "ComfySwitchNode": [{"name": "output", "type": "*"}],
    "ConditioningZeroOut": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "CreateVideo": [{"name": "VIDEO", "type": "VIDEO"}],
    "DepthAnything_V2": [{"name": "image", "type": "IMAGE"}],
    "DownloadAndLoadDepthAnythingV2Model": [{"name": "da_v2_model", "type": "MODEL"}],
    "DualCLIPLoader": [{"name": "CLIP", "type": "CLIP"}],
    "EmptyAceStep1.5LatentAudio": [{"name": "LATENT", "type": "LATENT"}],
    "EmptyLTXVLatentVideo": [{"name": "LATENT", "type": "LATENT"}],
    "EmptySD3LatentImage": [{"name": "LATENT", "type": "LATENT"}],
    "GetVideoComponents": [{"name": "images", "type": "IMAGE"}],
    "ImageResizeKJv2": [{"name": "IMAGE", "type": "IMAGE"}],
    "ImageScaleToTotalPixels": [{"name": "IMAGE", "type": "IMAGE"}],
    "INTConstant": [{"name": "value", "type": "INT"}],
    "KSampler": [{"name": "LATENT", "type": "LATENT"}],
    "KSamplerSelect": [{"name": "SAMPLER", "type": "SAMPLER"}],
    "LoadImage": [{"name": "IMAGE", "type": "IMAGE"}],
    "LoadVideo": [{"name": "VIDEO", "type": "VIDEO"}],
    "LoraLoaderModelOnly": [{"name": "MODEL", "type": "MODEL"}],
    "ManualSigmas": [{"name": "SIGMAS", "type": "SIGMAS"}],
    "ModelSamplingAuraFlow": [{"name": "MODEL", "type": "MODEL"}],
    "ModelSamplingSD3": [{"name": "MODEL", "type": "MODEL"}],
    "PathchSageAttentionKJ": [{"name": "MODEL", "type": "MODEL"}],
    "PrimitiveBoolean": [{"name": "BOOLEAN", "type": "BOOLEAN"}],
    "PrimitiveFloat": [{"name": "FLOAT", "type": "FLOAT"}],
    "PrimitiveInt": [{"name": "INT", "type": "INT"}],
    "RandomNoise": [{"name": "NOISE", "type": "NOISE"}],
    "SamplerCustomAdvanced": [{"name": "output", "type": "LATENT"}],
    "TextEncodeAceStepAudio1.5": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "TextEncodeQwenImageEdit": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "UNETLoader": [{"name": "MODEL", "type": "MODEL"}],
    "VAEDecode": [{"name": "IMAGE", "type": "IMAGE"}],
    "VAEDecodeAudio": [{"name": "AUDIO", "type": "AUDIO"}],
    "VAEDecodeTiled": [{"name": "IMAGE", "type": "IMAGE"}],
    "VAEEncode": [{"name": "LATENT", "type": "LATENT"}],
    "VAELoader": [{"name": "VAE", "type": "VAE"}],
    "WanImageToVideo": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTX2AttentionTunerPatch": [{"name": "model", "type": "MODEL"}],
    "LTX2_NAG": [{"name": "model", "type": "MODEL"}],
    "LTXAddVideoICLoRAGuide": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTXFloatToInt": [{"name": "INT", "type": "INT"}],
    "LTXICLoRALoaderModelOnly": [
        {"name": "model", "type": "MODEL"},
        {"name": "latent_downscale_factor", "type": "FLOAT"},
    ],
    "LTXVAudioVAELoader": [{"name": "Audio VAE", "type": "VAE"}],
    "LTXVChunkFeedForward": [{"name": "model", "type": "MODEL"}],
    "LTXVConcatAVLatent": [{"name": "latent", "type": "LATENT"}],
    "LTXVConditioning": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
    ],
    "LTXVCropGuides": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTXVEmptyLatentAudio": [{"name": "Latent", "type": "LATENT"}],
    "LTXVImgToVideoInplaceKJ": [{"name": "latent", "type": "LATENT"}],
    "LTXVPreprocess": [{"name": "output_image", "type": "IMAGE"}],
    "LTXVSeparateAVLatent": [
        {"name": "video_latent", "type": "LATENT"},
        {"name": "audio_latent", "type": "LATENT"},
    ],
    # controlnet_aux classes used by the v2.3 pilot. These packs were absent
    # from the local object_info cache during the audit, but their single image
    # output is stable and needed by both codemod readability and Handle.out().
    "CannyEdgePreprocessor": [{"name": "IMAGE", "type": "IMAGE"}],
    "DWPreprocessor": [{"name": "IMAGE", "type": "IMAGE"}],
}

# ---------------------------------------------------------------------------
# Internal lazy state
# ---------------------------------------------------------------------------

_index: dict[str, str] | None = None
_pack_cache: dict[str, dict[str, dict[str, Any]]] = {}


def _normalize_output_name(name: str) -> str:
    cleaned = name.strip().replace(" ", "_")
    return cleaned.upper()


def _load_index() -> dict[str, str]:
    global _index
    if _index is None:
        if INDEX_PATH.is_file():
            with open(INDEX_PATH, "r", encoding="utf-8") as fh:
                _index = json.load(fh)
        else:
            _index = {}
    return _index


def _load_pack(filename: str) -> dict[str, dict[str, Any]]:
    if filename not in _pack_cache:
        filepath = CACHE_DIR / filename
        if filepath.is_file():
            with open(filepath, "r", encoding="utf-8") as fh:
                _pack_cache[filename] = json.load(fh)
        else:
            _pack_cache[filename] = {}
    return _pack_cache[filename]


def _resolve_class_type(class_type: str) -> dict[str, Any] | None:
    idx = _load_index()
    filename = idx.get(class_type)
    if filename is None:
        return None
    pack = _load_pack(filename)
    return pack.get(class_type)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_class(class_type: str) -> dict[str, Any] | None:
    """Return the normalized cache entry for *class_type*, or ``None``.

    The returned dict has keys:
    ``pack``, ``pack_version``, ``python_module``, ``category``, ``name``,
    ``display_name``, ``description``, ``inputs``, ``input_order``,
    ``input_order_all``, ``object_info_widget_order``, ``outputs``, ``function``.
    """
    entry = _resolve_class_type(class_type)
    if entry is not None:
        return entry
    curated_outputs = _CURATED_OUTPUTS.get(class_type)
    if curated_outputs is None:
        return None
    return {"outputs": curated_outputs}


def object_info_widget_order(class_type: str) -> list[str | None]:
    """Return the ordered widget names (excluding link-only sockets) for *class_type*.

    Returns an empty list when the class is not found in the cache.
    This is a raw object_info fallback — callers should prefer the curated
    ``WIDGET_SCHEMA`` table and only use this when no curated entry exists.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return list(_CURATED_WIDGET_ORDERS.get(class_type, []))
    order = list(entry.get("object_info_widget_order", []))
    if class_type in _CURATED_WIDGET_ORDERS and "apply_to_all" not in order:
        return list(_CURATED_WIDGET_ORDERS[class_type])
    return order


def effective_widget_names_for_class(class_type: str, *, allow_object_info_fallback: bool = False) -> list[str | None]:
    """Return curated widget names, optionally falling back to cached object_info."""
    from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        return list(curated)
    if allow_object_info_fallback:
        return object_info_widget_order(class_type)
    return []


def output_names(class_type: str) -> list[str]:
    """Return ordered output names for *class_type* (e.g. ``["MODEL"]``).

    Returns an empty list when the class is not found in the cache.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return [o["name"] for o in _CURATED_OUTPUTS.get(class_type, [])]
    names = [o.get("name", "") for o in entry.get("outputs", [])]
    return names or [o["name"] for o in _CURATED_OUTPUTS.get(class_type, [])]


def output_types(class_type: str) -> list[str]:
    """Return ordered output types for *class_type* (e.g. ``["MODEL"]``).

    Returns an empty list when the class is not found in the cache.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return [o["type"] for o in _CURATED_OUTPUTS.get(class_type, [])]
    types = [o.get("type", "") for o in entry.get("outputs", [])]
    return types or [o["type"] for o in _CURATED_OUTPUTS.get(class_type, [])]


def class_defaults(class_type: str) -> dict[str, Any]:
    """Return schema default values by input name for *class_type*.

    Only inputs with an explicit object_info ``default`` are returned. The
    lookup is offline and deterministic; unknown classes return ``{}``.
    """
    entry = get_class(class_type)
    if entry is None:
        return {}
    defaults: dict[str, Any] = {}
    for name, spec in _iter_input_specs(entry):
        metadata = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        if "default" in metadata:
            defaults[name] = metadata["default"]
    return defaults


def class_input_types(class_type: str) -> dict[str, str]:
    """Return best-effort input type names by input name for *class_type*."""
    entry = get_class(class_type)
    if entry is None:
        return {}
    return {
        name: _normalize_input_type(spec[0] if spec else None)
        for name, spec in _iter_input_specs(entry)
    }


def class_output_count(class_type: str) -> int:
    """Return the number of declared outputs for *class_type*.

    Fails OPEN: an unknown class (absent from both the object_info snapshot and
    the curated fallback) reports ``0``. Codegen sites that rely on the count to
    determine output arity must use :func:`require_class_output_count` instead so
    a genuinely-unknown node fails CLOSED with a named, actionable error.
    """
    return len(output_names(class_type))


def class_is_known(class_type: str) -> bool:
    """Return True when *class_type* has a usable output schema.

    A class is "known" when it resolves in the object_info snapshot OR has a
    curated ``_CURATED_OUTPUTS`` fallback. Unknown classes are exactly the ones
    for which :func:`output_names` / :func:`class_output_count` fail open with an
    empty list / zero.
    """
    if _resolve_class_type(class_type) is not None:
        return True
    return class_type in _CURATED_OUTPUTS


def snapshot_version() -> str:
    """Return the ComfyUI version string the object_info snapshot was captured

    against, read from ``comfy_metadata.json``. Best-effort: returns
    ``"unknown"`` if the metadata file is absent or unreadable.
    """
    try:
        with open(METADATA_PATH, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return "unknown"
    version = meta.get("version") if isinstance(meta, dict) else None
    return str(version) if version else "unknown"


def require_class_output_count(class_type: str) -> int:
    """Return the declared output count for *class_type*, failing CLOSED.

    Unlike :func:`class_output_count` (which fails open to ``0`` for unknown
    classes), this raises :class:`UnknownNodeSchemaError` when *class_type* is in
    neither the object_info snapshot nor the curated fallback. Use this at
    codegen/arity-determining sites where a wrong (silently-zero) count produces
    structurally-broken Python that fails far downstream with an opaque
    ``ValueError: not enough values to unpack``.
    """
    if not class_is_known(class_type):
        from vibecomfy.errors import UnknownNodeSchemaError

        version = snapshot_version()
        raise UnknownNodeSchemaError(
            f"node {class_type!r} is not present in the object_info snapshot "
            f"(comfy_core {version}); the snapshot may be stale — refresh it with "
            f"'vibecomfy schemas refresh' before porting this workflow."
        )
    return len(output_names(class_type))


def class_has_list_output(class_type: str) -> bool:
    """Return True when any declared output is marked OUTPUT_IS_LIST."""
    entry = get_class(class_type)
    if entry is None:
        return any(bool(o.get("is_list")) for o in _CURATED_OUTPUTS.get(class_type, []))
    return any(bool(o.get("is_list")) for o in entry.get("outputs", []))


def list_classes() -> list[str]:
    """Return all class types in the cache, sorted deterministically."""
    idx = _load_index()
    if idx:
        return sorted(idx.keys())
    return sorted(_CURATED_OUTPUTS)


def _iter_input_specs(entry: dict[str, Any]) -> list[tuple[str, list[Any]]]:
    inputs = entry.get("inputs")
    if not isinstance(inputs, dict):
        return []
    ordered = entry.get("input_order_all")
    names: list[str] = [str(name) for name in ordered] if isinstance(ordered, list) else []
    by_name: dict[str, list[Any]] = {}
    for section in ("required", "optional"):
        values = inputs.get(section)
        if not isinstance(values, dict):
            continue
        for name, spec in values.items():
            if isinstance(spec, list):
                by_name[str(name)] = spec
            elif isinstance(spec, str):
                by_name[str(name)] = [spec]
    if not names:
        names = sorted(by_name)
    return [(name, by_name[name]) for name in names if name in by_name]


def _normalize_input_type(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "ENUM"
    if value is None:
        return ""
    return str(value)


def cache_stats() -> dict[str, Any]:
    """Return summary stats about the loaded cache (for debugging)."""
    idx = _load_index()
    return {
        "total_classes": len(idx),
        "packs_cached": len(_pack_cache),
        "cache_dir": str(CACHE_DIR),
    }
