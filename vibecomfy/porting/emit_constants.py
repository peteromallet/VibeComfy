"""emit_constants.py — constant classification, model-path, and wrapper helpers.

This module is carved from :mod:`vibecomfy.porting.emitter` as part of the
M2 structural-decomposition epic (Step 6).  It is a leaf-level consumer of
:mod:`vibecomfy.porting.emit_kwargs`.

All names exported here remain importable from ``vibecomfy.porting.emitter``
via explicit re-exports so that existing callers are unaffected.
"""

from __future__ import annotations

import ast as _ast
import importlib
import keyword as _keyword
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.porting.emit_kwargs import (
    _format_value,
    _is_link,
    _is_schema_default,
    _topological_node_order,
)
from vibecomfy.porting._provenance_utils import _normalize_provenance_paths
from vibecomfy.porting.widget_aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

logger = logging.getLogger(__name__)

__all__ = [
    # module-level constants
    "UI_ONLY_CLASS_TYPES",
    "FALLBACK_CLASS_TYPES",
    "_STATIC_WRAPPER_MODULES",
    "_WRAPPER_CLASS_TO_MODULE",
    "_WRAPPER_CLASS_TO_SYMBOL",
    # wrapper helpers
    "_wrapper_modules",
    "_wrapper_class_to_module",
    "_wrapper_class_type_for_symbol",
    "_wrapper_class_name_candidate",
    "_wrapper_module_for_class",
    "_wrapper_symbol_for_class",
    "_wrapper_imports_for_nodes",
    # classification constants
    "_ROLE_CLASSIFICATION",
    "_SECTION_NODE_THRESHOLD",
    "_MODEL_FILE_SUFFIXES",
    "_PROMPT_INPUT_FIELDS",
    "_AGENT_EDIT_STRING_ELIDE_THRESHOLD",
    "_NEGATIVE_PROMPT_INPUT_FIELDS",
    "_SEED_INPUT_FIELDS",
    "_OUTPUT_PREFIX_FIELDS",
    "_DIMENSION_INPUT_FIELDS",
    "_FPS_INPUT_FIELDS",
    "_FRAMES_INPUT_FIELDS",
    "_GUIDE_INPUT_FIELDS",
    "_MODEL_FIELD_PATTERNS",
    "_LOAD_IMAGE_FAMILY",
    "_IMAGE_EXTENSIONS",
    # constant hoisting helpers
    "_looks_like_placeholder_filename",
    "_classify_value_category",
    "_classify_node_role",
    "_constant_name_base_for_category",
    "_constant_name_for_string_value",
    "_GRAPH_FIELD_GET_RE",
    "_MISSING",
    "_literal_default_from_graph_get",
    "_resolve_graph_field_get_string",
    # model-path helpers
    "_model_path_parts",
    "_model_basename",
    "_model_family_constant_name",
    "_canonical_prefixed_model_value",
    "_model_constant_base_priority",
    "_canonical_model_values_by_base",
    "_constant_name_for_model_value",
    "_build_section_groups",
    "_hoist_constants",
    "_translate_widget_for_key",
    "_drop_output_prefix_constants",
    "_ui_widget_aliases",
    # model assets / metadata
    "_model_assets_for_emit",
    "_model_key",
    "_model_role_key",
    "_format_models_block",
    "_filename_is_url_derived",
    "_apply_ready_template_metadata_defaults",
    "_metadata_extras_for_emit",
    "_is_derivable_provenance",
    "_MODEL_PATH_EXTS",
    "_normalize_model_path",
    "_requirements_expr_for_emit",
]


UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset(
    {"Note", "MarkdownNote", "Label (rgthree)", "PreviewAny", "easy showAnything"}
)
FALLBACK_CLASS_TYPES: frozenset[str] = frozenset({
    "Note",
    "MarkdownNote",
})
RESERVED_WRAPPER_INPUT_NAMES: frozenset[str] = frozenset({"class", "from", "type"})

_STATIC_WRAPPER_MODULES: tuple[str, ...] = (
    "core",
    "kjnodes",
    "ltxvideo",
    "videohelpersuite",
    "controlnet_aux",
    "depthanythingv2",
    "wanvideowrapper",
    "qwentts",
    "qwen3tts",
    "gguf",
    "rgthree",
    "sam2",
    "wananimatepreprocess",
    "ailab_audioduration",
    "custom_scripts",
    "florence2",
    "gimm_vfi",
    "melbandroformer",
    "vibecomfy_internal",
)

_CURATED_SCHEMA_DEFAULTS: dict[str, dict[str, Any]] = {
    "UNETLoader": {"weight_dtype": "default"},
    "CLIPLoader": {"device": "default"},
    "VAELoader": {},
    "KSampler": {"scheduler": "simple", "denoise": 1},
    "KSamplerAdvanced": {"scheduler": "simple"},
    "EmptyLatentImage": {"batch_size": 1},
    "EmptySD3LatentImage": {"batch_size": 1},
    "EmptyFlux2LatentImage": {"batch_size": 1},
    "ImageScale": {"crop": "none"},
    "ImageResizeKJv2": {"crop": "none"},
    "VHS_VideoCombine": {"format": "auto", "codec": "auto"},
    "WanVideoSampler": {"shift": 8},
}

LTX2_3_TAIL_PATCHES: tuple[str, ...] = (
    "from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram",
    "from vibecomfy.patches.requirements import ensure_custom_nodes",
    "from vibecomfy.patches.resolution import resolution",
)


_WRAPPER_CLASS_TO_MODULE: dict[str, str] | None = None
_WRAPPER_CLASS_TO_SYMBOL: dict[str, str] | None = None


def _wrapper_modules() -> tuple[str, ...]:
    try:
        generated = importlib.import_module("vibecomfy.nodes._generated")
    except ImportError:
        return _STATIC_WRAPPER_MODULES
    modules = getattr(generated, "MODULES", None)
    if isinstance(modules, (list, tuple)):
        return tuple(str(module) for module in modules if isinstance(module, str) and module)
    return _STATIC_WRAPPER_MODULES


def _wrapper_class_to_module() -> dict[str, str]:
    global _WRAPPER_CLASS_TO_MODULE, _WRAPPER_CLASS_TO_SYMBOL
    if _WRAPPER_CLASS_TO_MODULE is not None:
        return _WRAPPER_CLASS_TO_MODULE
    module_mapping: dict[str, str] = {}
    symbol_mapping: dict[str, str] = {}
    for module_name in _wrapper_modules():
        try:
            module = importlib.import_module(f"vibecomfy.nodes._generated.{module_name}")
        except ImportError:
            continue
        exported = getattr(module, "__all__", ())
        for name in exported:
            if isinstance(name, str):
                class_type = _wrapper_class_type_for_symbol(module, name)
                module_mapping.setdefault(class_type, module_name)
                symbol_mapping.setdefault(class_type, name)
    _WRAPPER_CLASS_TO_MODULE = module_mapping
    _WRAPPER_CLASS_TO_SYMBOL = symbol_mapping
    return module_mapping


def _wrapper_class_type_for_symbol(module: Any, symbol_name: str) -> str:
    class_types = getattr(module, "__vibecomfy_class_types__", None)
    if isinstance(class_types, dict):
        class_type = class_types.get(symbol_name)
        if isinstance(class_type, str) and class_type:
            return class_type
    func = getattr(module, symbol_name, None)
    if callable(func):
        code = getattr(func, "__code__", None)
        for value in getattr(code, "co_consts", ()):
            if isinstance(value, str) and value != symbol_name and _wrapper_class_name_candidate(value):
                return value
    return symbol_name


def _wrapper_class_name_candidate(value: str) -> bool:
    return (
        bool(value)
        and "\n" not in value
        and not value.endswith("() takes at most 1 positional argument, got ")
        and any(ch.isupper() or ch in " ()-" for ch in value)
    )


def _wrapper_module_for_class(class_type: str) -> str | None:
    if class_type in FALLBACK_CLASS_TYPES or class_type in UI_ONLY_CLASS_TYPES:
        return None
    return _wrapper_class_to_module().get(class_type)


def _wrapper_symbol_for_class(class_type: str) -> str | None:
    _wrapper_class_to_module()
    return (_WRAPPER_CLASS_TO_SYMBOL or {}).get(class_type)


def _wrapper_imports_for_nodes(workflow_nodes: dict[str, Any]) -> dict[str, list[str]]:
    imports: dict[str, set[str]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        module_name = _wrapper_module_for_class(class_type)
        symbol_name = _wrapper_symbol_for_class(class_type)
        if module_name is not None:
            imports.setdefault(module_name, set()).add(symbol_name or class_type)
    return {module: sorted(names) for module, names in imports.items()}
# -- node role classification for section comments ---------------------------

_ROLE_CLASSIFICATION: dict[str, str] = {
    "LoadImage": "Inputs",
    "PrimitiveInt": "Inputs",
    "PrimitiveFloat": "Inputs",
    "PrimitiveString": "Inputs",
    "CLIPLoader": "Loaders",
    "VAELoader": "Loaders",
    "DualCLIPLoader": "Loaders",
    "DualCLIPLoaderGGUF": "Loaders",
    "CLIPVisionLoader": "Loaders",
    "StyleModelLoader": "Loaders",
    "UNETLoader": "Loaders",
    "CheckpointLoaderSimple": "Loaders",
    "CLIPTextEncode": "Conditioning",
    "CLIPTextEncodeFlux": "Conditioning",
    "CLIPTextEncodeSD3": "Conditioning",
    "FluxGuidance": "Conditioning",
    "CFGGuider": "Conditioning",
    "MultimodalGuider": "Conditioning",
    "ConditioningSetTimestepRange": "Conditioning",
    "KSampler": "Sampling",
    "KSamplerAdvanced": "Sampling",
    "SamplerCustomAdvanced": "Sampling",
    "BasicScheduler": "Sampling",
    "Flux2Scheduler": "Sampling",
    "KSamplerSelect": "Sampling",
    "EmptySD3LatentImage": "Sampling",
    "EmptyFlux2LatentImage": "Sampling",
    "EmptyLTXVLatentVideo": "Sampling",
    "EmptyHunyuanLatentVideo": "Sampling",
    "VAEDecode": "Decode",
    "VAEDecodeTiled": "Decode",
    "LTXVDecoder": "Decode",
    "SaveImage": "Outputs",
    "SaveVideo": "Outputs",
    "VHS_VideoCombine": "Outputs",
    "PreviewImage": "Outputs",
    "SaveAudio": "Outputs",
    "SaveAudioMP3": "Outputs",
}

_SECTION_ORDER: tuple[str, ...] = (
    "Inputs",
    "Loaders",
    "Conditioning",
    "Sampling",
    "Decode",
    "Outputs",
)

_SECTION_NODE_THRESHOLD: int = 8

# --- constant hoisting patterns ---------------------------------------------

_MODEL_FILE_SUFFIXES: tuple[str, ...] = (
    ".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".gguf", ".onnx",
)

# Fields whose values are classified as prompts
_PROMPT_INPUT_FIELDS: frozenset[str] = frozenset({"text", "prompt", "positive_prompt"})

_AGENT_EDIT_STRING_ELIDE_THRESHOLD = 400

# Fields whose values are classified as negative prompts
_NEGATIVE_PROMPT_INPUT_FIELDS: frozenset[str] = frozenset({"negative_prompt"})

# Fields whose values are classified as seeds
_SEED_INPUT_FIELDS: frozenset[str] = frozenset({"seed", "noise_seed"})

# Fields whose values are output prefixes
_OUTPUT_PREFIX_FIELDS: frozenset[str] = frozenset({"filename_prefix"})

# Fields whose values are dimensions
_DIMENSION_INPUT_FIELDS: frozenset[str] = frozenset({"resolution", "resolutions"})

# Fields whose values are FPS
_FPS_INPUT_FIELDS: frozenset[str] = frozenset({"fps"})

# Fields whose values are frame counts
_FRAMES_INPUT_FIELDS: frozenset[str] = frozenset({"length", "frames", "num_frames"})

# Fields whose values are guide strengths
_GUIDE_INPUT_FIELDS: frozenset[str] = frozenset({"cfg", "guidance", "strength_model", "strength_clip"})

# Fields whose values are model names (by field name pattern, not just suffix)
_MODEL_FIELD_PATTERNS: tuple[str, ...] = (
    "ckpt_name", "clip_name", "clip_name1", "clip_name2",
    "vae_name", "unet_name", "lora_name", "model_name",
    "checkpoint", "model",
)

# LoadImage-family nodes whose 'image' field may carry a placeholder filename
# from the source workflow's author (e.g. 'image (6).png').
_LOAD_IMAGE_FAMILY: frozenset[str] = frozenset({
    "LoadImage", "LoadImageMask", "LoadImagePath",
})

_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp"})
def _looks_like_placeholder_filename(value: str) -> bool:
    """Return True if *value* looks like a local placeholder, not an intentional path."""
    if not value or "/" in value or "\\" in value:
        # Has a path component — probably intentional (e.g. 'inputs/ref.png').
        return False
    # Case 1: contains parenthesized digits (e.g. 'image (6).png')
    if re.search(r"\(\d+\)", value):
        return True
    # Case 2: short bare filename ending in an image extension
    _, ext = (value.rsplit(".", 1) if "." in value else (value, ""))
    if f".{ext}" in _IMAGE_EXTENSIONS and len(value) < 30:
        return True
    return False
# --- constant hoisting -------------------------------------------------------


def _classify_value_category(
    field: str,
    value: Any,
    node_class_type: str,
) -> str | None:
    """Classify a value into a constant category for hoisting.

    Returns one of: 'prompt', 'negative_prompt', 'seed', 'model', 'output_prefix',
    'size', 'fps', 'frames', 'guide', 'preset', or None (do not hoist).
    """
    if not isinstance(value, (str, int, float)):
        return None

    # Model filenames - check suffix patterns
    if isinstance(value, str):
        if value.endswith(_MODEL_FILE_SUFFIXES):
            return "model"
        if field in _MODEL_FIELD_PATTERNS:
            return "model"

    # Prompts - long text strings
    if isinstance(value, str):
        if field in _PROMPT_INPUT_FIELDS and len(value) > 30:
            return "prompt"
        if field in _NEGATIVE_PROMPT_INPUT_FIELDS and len(value) > 10:
            return "negative_prompt"

    # Seeds
    if isinstance(value, int) and field in _SEED_INPUT_FIELDS:
        return "seed"

    # Output prefixes
    if isinstance(value, str) and field in _OUTPUT_PREFIX_FIELDS:
        return "output_prefix"

    # Dimensions
    if isinstance(value, str) and field in _DIMENSION_INPUT_FIELDS:
        return "size"

    # FPS
    if isinstance(value, (int, float)) and field in _FPS_INPUT_FIELDS:
        return "fps"

    # Frames
    if isinstance(value, int) and field in _FRAMES_INPUT_FIELDS:
        return "frames"

    # Guide strengths
    if isinstance(value, (int, float)) and field in _GUIDE_INPUT_FIELDS:
        return "guide"

    return None


def _classify_node_role(node: Any) -> str | None:
    """Return the section role for a node, or None if unclassified."""
    return _ROLE_CLASSIFICATION.get(node.class_type)


def _constant_name_base_for_category(category: str, field: str) -> str:
    """Return the unsuffixed constant name for a hoisted field.

    For non-model categories, returns a canonical name (DEFAULT_PROMPT, etc.).
    For ``model``, derives the name from the field (e.g. ``clip_name`` →
    ``CLIP_NAME``, ``unet_name`` → ``UNET_NAME``, ``vae_name`` → ``VAE_NAME``,
    ``bbox_detector_name`` → ``BBOX_DETECTOR_NAME``).
    """
    if category != "model":
        return {
            "prompt": "DEFAULT_PROMPT",
            "negative_prompt": "DEFAULT_NEGATIVE",
            "seed": "DEFAULT_SEED",
            "output_prefix": "OUTPUT_PREFIX",
            "size": "DEFAULT_SIZE",
            "fps": "DEFAULT_FPS",
            "frames": "DEFAULT_FRAMES",
            "guide": "GUIDE_STRENGTH",
        }.get(category, "CONSTANT")

    normalized = re.sub(r"\d+$", "", field)
    if normalized == "lora":
        normalized = "lora_name"
    elif normalized == "text_encoder":
        normalized = "text_encoder_name"
    elif not normalized.endswith("_name"):
        normalized = f"{normalized}_name"

    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", normalized.upper())
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"MODEL_{sanitized}"
    return sanitized


def _constant_name_for_string_value(value: str) -> str:
    """Return an uppercase-slugified constant name derived from string VALUE.

    Used for "preset" hoisting (repeated non-categorized string values).
    Examples: ``'vae'`` → ``VAE``, ``'wan_i2v.safetensors'`` →
    ``WAN_I2V_SAFETENSORS``.  Numeric suffixes are added by callers only on
    real name collision.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", str(value).upper())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    if not sanitized:
        return "VALUE"
    if sanitized[0].isdigit():
        sanitized = f"V_{sanitized}"
    return sanitized
_GRAPH_FIELD_GET_RE = re.compile(
    r"^wf\.nodes\[(?P<node_quote>['\"])(?P<node_id>.+?)(?P=node_quote)\]"
    r"\.(?P<store>inputs|widgets)\.get\("
    r"(?P<field_quote>['\"])(?P<field>.+?)(?P=field_quote)"
    r"(?:,\s*(?P<default>.*))?\)$"
)


_MISSING = object()
def _literal_default_from_graph_get(default_expr: str | None) -> Any:
    if default_expr is None:
        return _MISSING
    try:
        return _ast.literal_eval(default_expr)
    except Exception:
        return _MISSING


def _resolve_graph_field_get_string(
    value: Any,
    workflow_nodes: Mapping[str, Any],
    *,
    _seen: frozenset[str] = frozenset(),
) -> Any:
    """Resolve serialized ``wf.nodes[...]`` field lookups captured as strings.

    Older generated templates could serialize build-time graph lookup
    expressions into node text fields.  Emitting those strings as prompt
    constants bakes source code into the template, so resolve the narrow
    expression form against the source workflow before formatting literals.
    """
    if not isinstance(value, str) or value in _seen:
        return value
    match = _GRAPH_FIELD_GET_RE.fullmatch(value.strip())
    if match is None:
        return value

    node_id = match.group("node_id")
    field = match.group("field")
    store = match.group("store")
    default = _literal_default_from_graph_get(match.group("default"))
    node = workflow_nodes.get(str(node_id))
    if node is None:
        return "" if default is _MISSING else default

    container = getattr(node, store, {}) or {}
    if field not in container:
        return "" if default is _MISSING else default

    resolved = container[field]
    if resolved == value:
        return "" if default is _MISSING else default
    if isinstance(resolved, str):
        return _resolve_graph_field_get_string(
            resolved,
            workflow_nodes,
            _seen=frozenset((*_seen, value)),
        )
    return resolved
def _model_path_parts(value: str) -> list[str]:
    return [part for part in re.split(r"[\\/]+", str(value)) if part]


def _model_basename(value: str) -> str:
    parts = _model_path_parts(value)
    return parts[-1] if parts else str(value)


_MODEL_FAMILY_CONSTANTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("melbandroformer",), "MEL_BAND_ROFORMER_NAME"),
    (("spatial-upscaler", "spatial_upscaler", "upscaler"), "SPATIAL_UPSCALER_NAME"),
    (("depth_anything", "depthanything"), "DEPTH_ANYTHING_NAME"),
)


def _model_family_constant_name(value: str, format_suffix: str = "") -> str | None:
    basename = _model_basename(value).lower()
    for keywords, constant_name in _MODEL_FAMILY_CONSTANTS:
        if any(keyword in basename for keyword in keywords):
            return f"{constant_name}{format_suffix}"
    return None


def _canonical_prefixed_model_value(values: list[str]) -> str | None:
    unique = sorted(set(values))
    if len(unique) < 2:
        return None

    prefixed = [
        value
        for value in unique
        if len(_model_path_parts(value)) > 1
    ]
    if not prefixed:
        return None

    parent_dirs = {
        "/".join(part.lower() for part in _model_path_parts(value)[:-1])
        for value in prefixed
    }
    if len(parent_dirs) > 1:
        return None

    return max(prefixed, key=lambda value: (len(_model_path_parts(value)), len(value), value))
_MODEL_CONSTANT_BASE_PRIORITY: tuple[str, ...] = (
    "MEL_BAND_ROFORMER_NAME",
    "SPATIAL_UPSCALER_NAME",
    "DEPTH_ANYTHING_NAME",
    "AUDIO_VAE_NAME",
    "VIDEO_VAE_NAME",
    "VAE_TAESD_NAME",
    "CLIP_PROJECTION_NAME",
    "CLIP_NAME",
    "UNET_NAME",
    "VAE_NAME",
    "CKPT_NAME",
)


def _model_constant_base_priority(base: str) -> tuple[int, str]:
    bare_base = base.removesuffix("_GGUF")
    try:
        return (_MODEL_CONSTANT_BASE_PRIORITY.index(bare_base), base)
    except ValueError:
        return (len(_MODEL_CONSTANT_BASE_PRIORITY), base)


def _canonical_model_values_by_base(
    candidates: list[tuple[str, str, Any, str]],
) -> dict[tuple[str, str], tuple[str, str]]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for _nid, field, value, category in candidates:
        if category != "model" or not isinstance(value, str):
            continue
        base = _constant_name_for_model_value(field, value)
        if base is None:
            base = _constant_name_base_for_category(category, field)
        grouped.setdefault(_model_basename(value).lower(), []).append((base, value))

    canonical_by_raw: dict[tuple[str, str], tuple[str, str]] = {}
    for records in grouped.values():
        values = [value for _base, value in records]
        unique_values = set(values)
        canonical = values[0] if len(unique_values) == 1 else _canonical_prefixed_model_value(values)
        if canonical is None:
            continue
        chosen_base = min({base for base, _value in records}, key=_model_constant_base_priority)
        for base, value in records:
            canonical_by_raw[(base, value)] = (chosen_base, canonical)
    return canonical_by_raw


def _constant_name_for_model_value(field: str, value: str) -> str | None:
    """Return a semantic model constant name from the field and filename hints."""
    field_base = _constant_name_base_for_category("model", field)
    lower = str(value).lower()
    path_leaf = _model_basename(value)
    leaf_lower = path_leaf.lower()
    format_suffix = "_GGUF" if lower.endswith(".gguf") else ""

    if "audio_vae" in lower:
        return f"AUDIO_VAE_NAME{format_suffix}"
    if "video_vae" in lower:
        return f"VIDEO_VAE_NAME{format_suffix}"
    if "taesd" in lower or "vae_approx" in lower or leaf_lower.startswith("tae"):
        return f"VAE_TAESD_NAME{format_suffix}"
    if "text_projection" in leaf_lower:
        return f"CLIP_PROJECTION_NAME{format_suffix}"

    family_name = _model_family_constant_name(value, format_suffix)
    if family_name is not None:
        return family_name

    if field_base != "MODEL_NAME":
        return f"{field_base}{format_suffix}"

    leaf_slug = _constant_name_for_string_value(path_leaf)
    if "clip" in lower or "text_encoder" in lower or "gemma" in lower or "t5" in lower:
        return f"CLIP_NAME{format_suffix}"
    if "unet" in lower or "diffusion" in lower:
        return f"UNET_NAME{format_suffix}"
    if "vae" in lower or leaf_slug.startswith("TAE"):
        return f"VAE_NAME{format_suffix}"
    return None
def _build_section_groups(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> dict[str, list[str]]:
    """Group node IDs by section role using topological order.

    Only returns groups when the workflow has >= _SECTION_NODE_THRESHOLD nodes.
    Groups are ordered by _SECTION_ORDER.
    """
    if len(workflow_nodes) < _SECTION_NODE_THRESHOLD:
        return {}

    topo_order = _topological_node_order(workflow_nodes, edges_in)
    groups: dict[str, list[str]] = {}

    for nid in topo_order:
        node = workflow_nodes.get(nid)
        if node is None:
            continue
        role = _classify_node_role(node)
        if role is not None:
            groups.setdefault(role, []).append(nid)

    # Filter out groups with fewer than 2 nodes for readability
    # (single-node groups don't need section comments)
    return {role: ids for role, ids in groups.items() if len(ids) >= 1}


def _hoist_constants(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
) -> tuple[list[str], dict[tuple[str, str], str]]:
    """Scan workflow nodes for hoistable constants.

    Returns (constant_lines, constant_map) where:
    - constant_lines: list of "NAME = value" lines to emit in the constants section
    - constant_map: mapping from (node_id, translated_field) to constant name
    """
    # Collect candidates: (node_id, translated_field, value, category)
    candidates: list[tuple[str, str, Any, str]] = []

    # Also track value occurrence count across all nodes for the "repeated" heuristic
    value_counts: Counter[tuple[str, Any]] = Counter()

    for nid, node in workflow_nodes.items():
        cls = node.class_type
        schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
        node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
        input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or _ui_widget_aliases(node)

        for key, value in node.inputs.items():
            if _is_link(value):
                continue
            translated = _translate_widget_for_key(key, input_aliases, cls)
            if translated is None:
                continue
            value = _resolve_graph_field_get_string(value, workflow_nodes)
            category = _classify_value_category(translated, value, cls)
            if category is not None:
                candidates.append((nid, translated, value, category))
                value_counts[(category, str(value))] += 1

        for key, value in node.widgets.items():
            if _is_link(value):
                continue
            translated = _translate_widget_for_key(key, input_aliases, cls)
            if translated is None:
                continue
            value = _resolve_graph_field_get_string(value, workflow_nodes)
            category = _classify_value_category(translated, value, cls)
            if category is not None:
                candidates.append((nid, translated, value, category))
                value_counts[(category, str(value))] += 1

    if not candidates:
        return [], {}

    # Decide what to hoist:
    # 1. Always hoist: model, prompt, negative_prompt, seed, output_prefix, size, fps, frames, guide
    #    (these are public defaults by definition)
    # 2. Hoist presets that appear 2+ times
    # 3. Hoist any value of a recognized category that appears 2+ times

    # Build constant names deterministically
    category_counters: dict[str, int] = {}
    constant_defs: dict[str, tuple[Any, str]] = {}  # name -> (value, category)
    constant_map: dict[tuple[str, str], str] = {}  # (nid, field) -> name

    # Value dedup: same (base, category, value string) -> same constant name
    value_to_name: dict[tuple[str, str, str], str] = {}
    canonical_model_values = _canonical_model_values_by_base(candidates)

    for nid, field, value, category in candidates:
        count_key = (category, str(value))
        count = value_counts[count_key]

        # Always hoist categories that represent public defaults
        always_hoist = category in ("model", "prompt", "negative_prompt", "seed",
                                    "output_prefix", "size", "fps", "frames", "guide")
        should_hoist = always_hoist or count >= 2

        if not should_hoist:
            continue

        if category == "model" and isinstance(value, str):
            base = _constant_name_for_model_value(field, value)
        else:
            base = _constant_name_base_for_category(category, field)
        if base is None:
            base = _constant_name_base_for_category(category, field)
        emit_value = value
        value_key_value = str(value)
        if category == "model" and isinstance(value, str):
            canonical_model = canonical_model_values.get((base, value))
            if canonical_model is not None:
                base, canonical_model_value = canonical_model
                emit_value = canonical_model_value
                value_key_value = _model_basename(value).lower()
        value_key = (base, category, value_key_value)
        if value_key in value_to_name:
            name = value_to_name[value_key]
        else:
            category_counters[base] = category_counters.get(base, 0) + 1
            cnt = category_counters[base]
            name = base if cnt == 1 else f"{base}_{cnt}"
            value_to_name[value_key] = name
            constant_defs[name] = (emit_value, category)

        constant_map[(nid, field)] = name

    # Also check for repeated presets (non-categorized values appearing 2+ times)
    # Scan for string values that appear 2+ times and hoist them
    all_values: Counter[tuple[str, Any]] = Counter()
    for nid, node in workflow_nodes.items():
        cls = node.class_type
        node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
        input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or _ui_widget_aliases(node)
        for key, value in {**node.inputs, **node.widgets}.items():
            if _is_link(value):
                continue
            translated = _translate_widget_for_key(key, input_aliases, cls)
            if translated is None:
                continue
            value = _resolve_graph_field_get_string(value, workflow_nodes)
            # Only track string values that are not already categorized
            if not isinstance(value, str):
                continue
            if not value:
                continue
            cat = _classify_value_category(translated, value, cls)
            if cat is not None:
                continue  # already handled above
            all_values[(translated, value)] += 1

    for (field, value), count in all_values.items():
        if count >= 2:
            # This is a repeated preset — name by value (uppercase-slugified)
            sanitized = _constant_name_for_string_value(value)
            value_key = (sanitized, "preset", str(value))
            if value_key in value_to_name:
                continue  # already named
            category_counters[sanitized] = category_counters.get(sanitized, 0) + 1
            cnt = category_counters[sanitized]
            name = sanitized if cnt == 1 else f"{sanitized}_{cnt}"
            value_to_name[value_key] = name
            constant_defs[name] = (value, "preset")
            # Map all occurrences
            for nid, node in workflow_nodes.items():
                if (nid, field) in constant_map:
                    continue
                # Check if this node has this value at this field
                node_val = node.inputs.get(field, node.widgets.get(field))
                if node_val == value:
                    constant_map[(nid, field)] = name

    # Prune constants whose ONLY references would be stripped by _is_schema_default
    # (e.g. '0, 0, 0' hoisted as a repeated preset but stripped from every _node_kwargs call).
    names_to_prune: set[str] = set()
    for name in list(constant_defs.keys()):
        ref_nodes = [(nid, field) for (nid, field), cname in constant_map.items() if cname == name]
        if not ref_nodes:
            names_to_prune.add(name)
            continue
        all_would_be_stripped = True
        for nid, field in ref_nodes:
            node = workflow_nodes.get(nid)
            if node is None:
                all_would_be_stripped = False
                break
            node_meta: dict[str, Any] = getattr(node, "metadata", None) or {}
            val = constant_defs[name][0]  # emit_value
            if not _is_schema_default(node.class_type, field, val, node_meta, node=node):
                all_would_be_stripped = False
                break
        if all_would_be_stripped:
            names_to_prune.add(name)

    for name in names_to_prune:
        del constant_defs[name]
        for key in [k for k, v in constant_map.items() if v == name]:
            del constant_map[key]

    # Build constant lines, sorted by name for determinism
    constant_lines: list[str] = []
    for name in sorted(constant_defs.keys()):
        value, category = constant_defs[name]
        constant_lines.append(f"{name} = {_format_value(value)}")

    return constant_lines, constant_map
def _translate_widget_for_key(
    key: str,
    input_aliases: list[str | None] | None,
    class_type: str,
) -> str | None:
    """Translate a widget_N key to its named field, or None if it should be dropped."""
    if key.startswith("unused_widget_"):
        return None
    if not key.startswith("widget_"):
        return key
    try:
        idx = int(key.split("_", 1)[1])
    except ValueError:
        return key
    return resolve_widget_key_with_provenance(
        class_type,
        key,
        input_aliases=input_aliases,
    ).name


def _drop_output_prefix_constants(
    constant_lines: list[str],
    constant_map: dict[tuple[str, str], str],
) -> tuple[list[str], dict[tuple[str, str], str]]:
    """Keep filename prefixes inline; READY_METADATA owns the public output prefix."""
    output_prefix_names = {
        line.split("=", 1)[0].strip()
        for line in constant_lines
        if line.split("=", 1)[0].strip().startswith("OUTPUT_PREFIX")
    }
    if not output_prefix_names:
        return constant_lines, constant_map
    return (
        [
            line
            for line in constant_lines
            if line.split("=", 1)[0].strip() not in output_prefix_names
        ],
        {
            key: value
            for key, value in constant_map.items()
            if value not in output_prefix_names
        },
    )
def _model_assets_for_emit(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    def usable(asset: Mapping[str, Any]) -> bool:
        return bool(asset.get("url"))

    raw_assets = metadata.get("model_assets")
    if isinstance(raw_assets, list):
        return [dict(asset) for asset in raw_assets if isinstance(asset, Mapping) and usable(asset)]
    raw_requirement_models = requirements.get("models") if isinstance(requirements, Mapping) else None
    if isinstance(raw_requirement_models, list):
        return [dict(asset) for asset in raw_requirement_models if isinstance(asset, Mapping) and usable(asset)]
    return []


def _model_key(asset: Mapping[str, Any], used: set[str]) -> str:
    role = _model_role_key(asset)
    if role:
        candidate = role
        index = 2
        while candidate in used:
            candidate = f"{role}_{index}"
            index += 1
        used.add(candidate)
        return candidate
    raw_name = str(asset.get("name") or asset.get("filename") or "model")
    base = re.sub(r"[^0-9a-zA-Z_]+", "_", raw_name.rsplit(".", 1)[0]).strip("_").lower() or "model"
    if base[0].isdigit():
        base = f"model_{base}"
    if _keyword.iskeyword(base):
        base = f"{base}_model"
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _model_role_key(asset: Mapping[str, Any]) -> str | None:
    subdir = str(asset.get("subdir") or asset.get("directory") or "").replace("\\", "/").strip("/")
    field = str(asset.get("field") or asset.get("input") or "").lower()
    role_by_subdir = {
        "checkpoints": "checkpoint",
        "clip_vision": "clip_vision",
        "controlnet": "controlnet",
        "diffusion_models": "diffusion_model",
        "latent_upscale_models": "upscale_model",
        "loras": "lora",
        "text_encoders": "text_encoder",
        "unet": "unet",
        "vae": "vae",
    }
    if field in {"ckpt_name", "checkpoint"}:
        return "checkpoint"
    if field in {"unet_name", "model_name"} and subdir in {"diffusion_models", "unet"}:
        return role_by_subdir.get(subdir, "model")
    if field in {"vae_name"}:
        return "vae"
    if field in {"clip_name", "clip_name1", "clip_name2", "text_encoder"}:
        return "text_encoder"
    return role_by_subdir.get(subdir)
def _format_models_block(model_assets: list[Mapping[str, Any]]) -> list[str]:
    if not model_assets:
        return []
    lines = ["MODELS = {"]
    used: set[str] = set()
    for asset in model_assets:
        key = _model_key(asset, used)
        filename = asset.get("filename", asset.get("name"))
        subdir = asset.get("subdir") or asset.get("directory") or "checkpoints"
        args: list[str] = []
        if filename is not None and not _filename_is_url_derived(str(filename), asset.get("url")):
            args.append(f"filename={_format_value(filename)}")
        for field_name in ("url", "target_path", "sha256", "hf_revision", "size_bytes", "gated"):
            value = asset.get(field_name)
            if value is not None:
                args.append(f"{field_name}={_format_value(value)}")
        if subdir is not None:
            args.append(f"subdir={_format_value(subdir)}")
        lines.append(f"    {key!r}: ModelAsset({', '.join(args)}),")
    lines.append("}")
    return lines


def _filename_is_url_derived(filename: str, url: Any) -> bool:
    if not isinstance(url, str) or not url:
        return False
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not path:
        return False
    return Path(path).name == filename


def _apply_ready_template_metadata_defaults(metadata: dict[str, Any], template_id: str) -> None:
    if template_id == "video/ltx2_3_runexx_first_last_frame":
        metadata.setdefault("comfy_configuration", {"memory_profile": 3, "fp8_e4m3fn_text_enc": True})


def _metadata_extras_for_emit(metadata: Mapping[str, Any]) -> dict[str, Any]:
    derived_keys = {
        "ready_template",
        "workflow_template",
        "capability",
        "output_prefix",
        "unbound_inputs",
        "model_assets",
        "edit_guide",
        "requirements",
        "id_map",
        "ready_template_path",
        "python_policy_applied",
        "source_role",
        "source_workflow",
        "vibecomfy_version",
        "comfy_core",
        "coverage_tier",
        "custom_node_packs",
        "_has_public_inputs_for_emit",
    }
    extras = {
        str(key): value
        for key, value in metadata.items()
        if key not in derived_keys and value is not None
    }
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping) and not _is_derivable_provenance(provenance):
        extras["provenance"] = _normalize_provenance_paths(provenance)
    return extras


def _is_derivable_provenance(provenance: Mapping[str, Any]) -> bool:
    """Return true when ReadyMetadata.build can recreate the provenance."""

    return set(provenance).issubset({"source_workflow", "source_role"})


_MODEL_PATH_EXTS = (".safetensors", ".ckpt", ".pt", ".pth", ".gguf", ".onnx", ".bin")


def _normalize_model_path(value: Any) -> Any:
    if isinstance(value, str) and "\\" in value and value.lower().endswith(_MODEL_PATH_EXTS):
        return value.replace("\\", "/")
    return value


def _requirements_expr_for_emit(requirements: Mapping[str, Any], *, has_models: bool) -> str | None:
    retained: dict[str, Any] = {}
    for key, value in dict(requirements).items():
        if key == "models" and has_models:
            continue
        if value:
            if key == "models" and isinstance(value, (list, tuple)):
                value = [_normalize_model_path(v) for v in value]
            retained[str(key)] = value
    if not retained:
        return None
    return _format_value(retained)


def _ui_widget_aliases(node: Any) -> list[str | None] | None:
    ui = getattr(node, "metadata", {}).get("_ui")
    if not isinstance(ui, dict):
        return None
    inputs = ui.get("inputs")
    if not isinstance(inputs, list):
        return None
    aliases: list[str | None] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        widget = item.get("widget")
        if not isinstance(widget, dict):
            continue
        name = widget.get("name")
        aliases.append(str(name) if isinstance(name, str) and name else None)
    widget_indices: list[int] = []
    for key in getattr(node, "widgets", {}):
        key_str = str(key)
        if not key_str.startswith("widget_"):
            continue
        try:
            widget_indices.append(int(key_str.split("_", 1)[1]))
        except ValueError:
            continue
    if widget_indices and len(aliases) <= max(widget_indices):
        return None
    return aliases or None
