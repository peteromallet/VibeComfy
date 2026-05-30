from __future__ import annotations

import ast
import hashlib
import importlib
import json
import keyword
import logging
import pprint
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Mapping

from vibecomfy.errors import ConversionParityError
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy._workflow_helpers import RESOLVABLE_HELPER_CLASS_TYPES
from vibecomfy.porting.widget_aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.object_info import class_defaults, class_has_list_output, class_output_count
from vibecomfy.porting.object_info import output_names as class_output_names
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA
from vibecomfy.utils import repo_relative_path

# -- readability warning codes ------------------------------------------------
READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT = "avoidable_positional_output"
READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY = "output_name_ambiguity"
READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED = "schema_backed_widget_alias_not_resolved"
READABILITY_WARNING_HIDDEN_MODEL_FILENAME = "hidden_model_filename"
READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE = "local_helper_copy_in_strict_template"
READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL = "long_one_line_node_call"
READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED = "generated_template_not_formatted"
READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG = "generated_variable_name_too_long"
READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND = "subgraph_input_unbound"
READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS = "schema_unknown_kwarg_hidden_by_extras"

READABILITY_WARNING_CODES: frozenset[str] = frozenset(
    {
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
        READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
        READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
        READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
        READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
        READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
        READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
        READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
    }
)

EmissionSeverity = Literal["error", "warning", "info"]
logger = logging.getLogger(__name__)
_PROVENANCE_PATH_KEYS: frozenset[str] = frozenset({"source_path", "source_workflow_path", "source_workflow"})


@dataclass(slots=True)
class EmissionDiagnostic:
    """A readability diagnostic recorded during emission.

    These are always *warnings* (or info) - hard errors are surfaced through
    `PortConvertValidation` parity / schema failures, not here.
    """

    code: str
    message: str
    severity: EmissionSeverity = "warning"
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _PublicInputBinding:
    name: str
    node_id: str
    field: str
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    media_semantics: str | None = None


@dataclass(frozen=True, slots=True)
class _PublicInputSpec:
    name: str
    node_ref: str
    metadata_node_ref: str
    field: str
    default_expr: str
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    media_semantics: str | None = None


@dataclass(frozen=True, slots=True)
class _SubgraphPort:
    name: str
    type: str | None = None
    source_name: str | None = None
    external_ref: tuple[str, int] | None = None


@dataclass(frozen=True, slots=True)
class _SubgraphDef:
    id: str
    raw_name: str
    slug: str
    inputs: tuple[_SubgraphPort, ...]
    outputs: tuple[_SubgraphPort, ...]
    nodes: dict[str, Any]
    edges_in: dict[str, list[Any]]
    input_refs: dict[tuple[str, str], str]
    default_args: dict[str, Any]
    return_refs: tuple[tuple[str, int], ...]
    source_hash: str
    source_path: str | None = None


GENERATED_HEADER = (
    "# vibecomfy: generated\n"
    "# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>\n"
)

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
        return ast.literal_eval(default_expr)
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


_MODEL_FAMILY_CONSTANTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("melbandroformer",), "MEL_BAND_ROFORMER_NAME"),
    (("spatial-upscaler", "spatial_upscaler", "upscaler"), "SPATIAL_UPSCALER_NAME"),
    (("depth_anything", "depthanything"), "DEPTH_ANYTHING_NAME"),
)


def _model_path_parts(value: str) -> list[str]:
    return [part for part in re.split(r"[\\/]+", str(value)) if part]


def _model_basename(value: str) -> str:
    parts = _model_path_parts(value)
    return parts[-1] if parts else str(value)


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
            if not _is_schema_default(node.class_type, field, val, node_meta):
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


def _public_input_specs(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    *,
    registered_inputs: dict[str, tuple[str, str]] | None,
    constant_map: dict[tuple[str, str], str],
) -> list[_PublicInputSpec]:
    specs: list[_PublicInputSpec] = []
    used_names: set[str] = set()

    def add(binding: _PublicInputBinding) -> None:
        if binding.name in used_names:
            return
        node = workflow_nodes.get(str(binding.node_id))
        if node is None:
            return
        field_values = _resolved_field_values(node)
        if binding.field not in field_values:
            return
        default_value = _resolve_graph_field_get_string(
            field_values[binding.field],
            workflow_nodes,
        )
        default_expr = constant_map.get((str(binding.node_id), binding.field))
        if default_expr is None:
            default_expr = _format_value(default_value)
        # Blank placeholder filenames for LoadImage-family public inputs
        # (e.g. 'image (6).png' — the upstream workflow author's local file).
        if (
            binding.required
            and binding.field == "image"
            and str(node.class_type) in _LOAD_IMAGE_FAMILY
            and isinstance(default_value, str)
            and _looks_like_placeholder_filename(default_value)
        ):
            default_expr = "''"
        node_var = _first_output_var(output_var_names.get(str(binding.node_id))) or var_names.get(str(binding.node_id))
        node_ref = node_var if node_var is not None else repr(str(binding.node_id))
        metadata_node_ref = repr(str(binding.node_id))
        specs.append(
            _PublicInputSpec(
                name=binding.name,
                node_ref=node_ref,
                metadata_node_ref=metadata_node_ref,
                field=binding.field,
                default_expr=default_expr,
                type=binding.type,
                required=binding.required,
                aliases=binding.aliases,
                media_semantics=binding.media_semantics,
            )
        )
        used_names.add(binding.name)
        used_names.update(binding.aliases)

    for input_name, (old_id, field) in dict(registered_inputs or {}).items():
        resolved_field = field
        if field.startswith("widget_") and old_id in workflow_nodes:
            cls = workflow_nodes[old_id].class_type
            node = workflow_nodes[old_id]
            aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
            resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
            if resolved.name is not None:
                resolved_field = resolved.name
        add(_PublicInputBinding(name=input_name, node_id=str(old_id), field=resolved_field))

    inferred = _infer_public_input_bindings(workflow_nodes, edges_in, reserved_names=used_names)
    for binding in inferred:
        add(binding)
    return specs


def _format_public_inputs_block(specs: list[_PublicInputSpec], *, metadata: bool = False) -> list[str]:
    if not specs:
        return []
    lines = ["PUBLIC_INPUT_METADATA = {" if metadata else "    return {"]
    # Dedup by (node_ref, field): aliases for the same underlying binding collapse
    # to one entry under the canonical name with the others recorded as
    # aliases=(...).  Without this, both 'negative' and 'negative_prompt' end up as
    # separate dict keys for the same node/field, which silently duplicates state.
    seen: dict[tuple[str, str], str] = {}
    for spec in specs:
        node_ref = spec.metadata_node_ref if metadata else spec.node_ref
        key = (node_ref, spec.field)
        if key in seen:
            continue
        seen[key] = spec.name
        # Fold any other specs that share (node_ref, field) into the aliases tuple.
        extra_aliases: list[str] = []
        for other in specs:
            other_node = other.metadata_node_ref if metadata else other.node_ref
            if (other_node, other.field) != key:
                continue
            if other.name != spec.name and other.name not in extra_aliases:
                extra_aliases.append(other.name)
        aliases = tuple(spec.aliases or ())
        for alias in extra_aliases:
            if alias not in aliases:
                aliases = aliases + (alias,)
        args = [
            f"node={node_ref}",
            f"field={spec.field!r}",
            f"default={spec.default_expr}",
        ]
        if spec.type is not None:
            args.append(f"type={spec.type!r}")
        if spec.required:
            args.append("required=True")
        if aliases:
            args.append(f"aliases={aliases!r}")
        if spec.media_semantics is not None:
            args.append(f"media_semantics={spec.media_semantics!r}")
        lines.append(f"    {spec.name!r}: InputSpec({', '.join(args)}),")
    lines.append("}" if metadata else "    }")
    return lines


def _remap_public_inputs_for_materialized_subgraphs(
    specs: list[_PublicInputSpec],
    workflow_nodes: dict[str, Any],
    subgraphs: dict[str, _SubgraphDef],
) -> list[_PublicInputSpec]:
    if not specs or not subgraphs:
        return specs
    remapped: list[_PublicInputSpec] = []
    for spec in specs:
        try:
            node_id = ast.literal_eval(spec.metadata_node_ref)
        except Exception:
            remapped.append(spec)
            continue
        node = workflow_nodes.get(str(node_id))
        subgraph = subgraphs.get(str(getattr(node, "class_type", ""))) if node is not None else None
        if subgraph is None:
            remapped.append(spec)
            continue
        port_index = _subgraph_port_index_for_instance_field(node, subgraph, spec.field)
        if port_index is None:
            remapped.append(spec)
            continue
        port = subgraph.inputs[port_index]
        consumer = next(
            (
                (internal_node_id, internal_field)
                for (internal_node_id, internal_field), port_name in subgraph.input_refs.items()
                if port_name == port.name
            ),
            None,
        )
        if consumer is None:
            remapped.append(spec)
            continue
        internal_node_id, internal_field = consumer
        remapped.append(
            replace(
                spec,
                metadata_node_ref=repr(_subgraph_emitted_node_id(subgraph.id, internal_node_id)),
                field=internal_field,
            )
        )
    return remapped


def _subgraph_port_index_for_instance_field(node: Any, subgraph: _SubgraphDef, field: str) -> int | None:
    candidates = _subgraph_instance_port_candidate_names(node, subgraph)
    for index, names in candidates.items():
        if field in names:
            return index
    return None


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
    if keyword.iskeyword(base):
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


def _normalize_provenance_paths(provenance: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(provenance)
    for key in _PROVENANCE_PATH_KEYS:
        value = normalized.get(key)
        if isinstance(value, str) and value:
            normalized[key] = _repo_relative_provenance_path(value)
    return normalized


def _repo_relative_provenance_path(path: str) -> str:
    normalized = repo_relative_path(path)
    if Path(normalized).is_absolute():
        logger.warning("provenance path is outside the repo; keeping absolute path: %s", normalized)
    return normalized


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


def _lock_entries_by_class(lockfile_path: Path = Path("custom_nodes.lock")) -> dict[str, LockEntry]:
    by_class: dict[str, LockEntry] = {}
    try:
        entries = read_lockfile(lockfile_path)
    except (OSError, ValueError):
        return {}
    for entry in entries:
        for class_type in entry.class_set:
            by_class.setdefault(str(class_type), entry)
    return by_class


def _custom_node_packs_for_emit(
    workflow_nodes: Mapping[str, Any],
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    explicit = metadata.get("custom_node_packs")
    if isinstance(explicit, Mapping):
        return {str(key): dict(value) for key, value in explicit.items() if isinstance(value, Mapping)}

    by_class = _lock_entries_by_class()
    if not by_class:
        return {}

    requirement_names = {
        str(item)
        for key in ("custom_nodes", "custom_node_refs")
        for item in (requirements.get(key) or [])
        if item
    }
    grouped: dict[str, dict[str, Any]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        entry = by_class.get(class_type)
        if entry is None:
            continue
        commit = entry.commit or entry.git_commit_sha
        if not commit:
            continue
        row = grouped.setdefault(
            entry.name,
            {
                "commit": commit,
                "url": entry.url,
                "class_schema_sha256": entry.class_schema_sha256 or entry.schema_hash,
                "classes_used": [],
                "pip_packages": list(entry.pip_packages),
                "status": "pinned" if entry.name in requirement_names or entry.slug in requirement_names else "discovered",
            },
        )
        if class_type not in row["classes_used"]:
            row["classes_used"].append(class_type)

    for row in grouped.values():
        row["classes_used"] = sorted(row["classes_used"])
        row["pip_packages"] = sorted(row["pip_packages"])
        for key in ("url", "class_schema_sha256"):
            if row.get(key) is None:
                row.pop(key, None)
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def _format_ready_metadata_build(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
    *,
    has_models: bool,
    has_public_inputs: bool,
    custom_node_packs: Mapping[str, Any] | None = None,
    output_node_class_type: str | None = None,
) -> list[str]:
    template_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    raw_capability = str(metadata.get("capability") or "unknown")
    if raw_capability == "unknown" and output_node_class_type:
        from vibecomfy.templates import _derive_output_kind  # local import to avoid circular import at module load
        derived = _derive_output_kind(output_node_class_type)
        if derived:
            raw_capability = derived
    capability = raw_capability
    output_prefix = str(metadata.get("output_prefix") or template_id)
    lines = [
        "READY_METADATA = ReadyMetadata.build(",
        f"    capability={capability!r},",
    ]
    if has_public_inputs:
        lines.append("    inputs=PUBLIC_INPUT_METADATA,")
    if has_models:
        lines.append("    models=MODELS,")
    if output_prefix != template_id:
        lines.append(f"    output_prefix={output_prefix!r},")
    requirements_expr = _requirements_expr_for_emit(requirements, has_models=has_models)
    if requirements_expr is not None:
        lines.append(f"    requirements={requirements_expr},")
    if custom_node_packs:
        lines.append(f"    custom_node_packs={_format_value(dict(custom_node_packs))},")
    for key, value in _metadata_extras_for_emit(metadata).items():
        lines.append(f"    {key}={_format_value(value)},")
    lines.append(")")
    return lines


def _strip_unused_template_imports(source: str) -> str:
    tree = ast.parse(source)
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    target = "from vibecomfy.templates import "
    lines = source.splitlines()
    rewritten: list[str] = []
    for line in lines:
        if not line.startswith(target):
            rewritten.append(line)
            continue
        names = [name.strip() for name in line[len(target) :].split(",")]
        kept = [name for name in names if _import_binding_name(name) in used]
        if kept:
            rewritten.append(target + ", ".join(kept))
    return "\n".join(rewritten) + ("\n" if source.endswith("\n") else "")


def _import_binding_name(import_name: str) -> str:
    if " as " in import_name:
        return import_name.rsplit(" as ", 1)[1].strip()
    return import_name


def emit_ready_template_python(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    raw_workflow: dict[str, Any] | None = None,
) -> str:
    metadata = dict(ready_metadata)
    requirements = dict(ready_requirements)
    if apply_overrides:
        for key, value in (apply_overrides.get("metadata_overrides") or {}).items():
            metadata[key] = value
    _apply_ready_template_metadata_defaults(metadata, template_id)

    # Ensure sageattention is declared when SageAttention nodes are present.
    _sage_class_types = frozenset({
        "LTX2MemoryEfficientSageAttentionPatch",
        "PathchSageAttentionKJ",
    })
    if any(
        node.class_type in _sage_class_types
        for node in workflow.nodes.values()
    ):
        existing = metadata.get("runtime_packages")
        if not (
            isinstance(existing, list)
            and any(
                isinstance(pkg, dict) and pkg.get("name") == "sageattention"
                for pkg in existing
            )
        ):
            entry = {
                "name": "sageattention",
                "reason": (
                    "Required by LTX2MemoryEfficientSageAttentionPatch / "
                    "PathchSageAttentionKJ for memory-efficient attention on "
                    "compatible GPUs."
                ),
                "source": "SageAttention-ada",
            }
            if isinstance(existing, list):
                metadata["runtime_packages"] = [*existing, entry]
            else:
                metadata["runtime_packages"] = [entry]

    raw_workflow = raw_workflow or _raw_workflow_from_metadata(metadata)
    subgraph_definitions = _subgraph_definitions_from_raw(raw_workflow, source_path=_source_workflow_path(metadata))
    prepared = _prepare_workflow_for_emit(workflow, apply_overrides=apply_overrides, template_id=template_id)
    prepared["subgraph_definitions"] = subgraph_definitions
    _apply_subgraph_names_to_prepared(prepared)
    has_ltx_tail = _has_ltx_lowvram_tail(template_id)

    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
    var_names = prepared["var_names"]

    # Hoist constants and build section groups
    constant_lines, constant_map = _hoist_constants(workflow_nodes, edges_in, var_names)
    constant_lines, constant_map = _drop_output_prefix_constants(constant_lines, constant_map)
    section_groups = _build_section_groups(workflow_nodes, edges_in)
    wrapper_imports = _wrapper_imports_for_nodes(_all_nodes_for_imports(workflow_nodes, subgraph_definitions))
    output_var_names = prepared["output_var_names"]
    public_inputs = _public_input_specs(
        workflow_nodes,
        edges_in,
        var_names,
        output_var_names,
        registered_inputs=registered_inputs,
        constant_map=constant_map,
    )
    model_assets = _model_assets_for_emit(metadata, requirements)
    custom_node_packs = _custom_node_packs_for_emit(workflow_nodes, metadata, requirements)
    has_public_inputs = bool(public_inputs)
    metadata["_has_public_inputs_for_emit"] = has_public_inputs

    out_lines: list[str] = []
    out_lines.append(GENERATED_HEADER.rstrip("\n"))
    out_lines.append('"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append(
        "from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref"
    )
    for module_name, names in sorted(wrapper_imports.items()):
        out_lines.append(f"from vibecomfy.nodes.{module_name} import {', '.join(names)}")
    if has_ltx_tail:
        out_lines.extend(LTX2_3_TAIL_PATCHES)
    out_lines.append("")
    # -- constants section ----------------------------------------------------
    if constant_lines:
        out_lines.append("")
        out_lines.extend(constant_lines)
        out_lines.append("")
    model_lines = _format_models_block(model_assets)
    if model_lines:
        out_lines.append("")
        out_lines.extend(model_lines)
        out_lines.append("")
    public_inputs_for_metadata = _remap_public_inputs_for_materialized_subgraphs(
        public_inputs,
        workflow_nodes,
        subgraph_definitions,
    )
    # Compute which subgraph node IDs are referenced by PUBLIC_INPUT_METADATA.
    # Only those nodes need explicit _id= kwargs in emitted subgraph functions.
    required_ids_by_subgraph: dict[str, set[str]] = {}
    for spec in public_inputs_for_metadata:
        try:
            ref_str = ast.literal_eval(spec.metadata_node_ref)
        except Exception:
            continue
        if ":" not in ref_str:
            continue
        prefix, inner_id = ref_str.split(":", 1)
        for subgraph_id in subgraph_definitions:
            if _short_subgraph_id_prefix(subgraph_id) == prefix:
                required_ids_by_subgraph.setdefault(subgraph_id, set()).add(inner_id)
                break
    public_input_metadata_lines = _format_public_inputs_block(public_inputs_for_metadata, metadata=True)
    if public_input_metadata_lines:
        out_lines.append("")
        out_lines.extend(public_input_metadata_lines)
        out_lines.append("")
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    output_node_cls: str | None = (
        str(workflow_nodes[output_node_ids[0]].class_type) if output_node_ids and output_node_ids[0] in workflow_nodes else None
    )
    out_lines.extend(
        _format_ready_metadata_build(
            metadata,
            requirements,
            has_models=bool(model_assets),
            has_public_inputs=has_public_inputs,
            custom_node_packs=custom_node_packs,
            output_node_class_type=output_node_cls,
        )
    )
    out_lines.append("")
    subgraph_lines = _emit_subgraph_functions(
        prepared,
        diagnostics=diagnostics,
        constant_map=constant_map,
        required_ids_by_subgraph=required_ids_by_subgraph,
    )
    if subgraph_lines:
        out_lines.extend(subgraph_lines)
        out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr="READY_METADATA",
            source_path_expr="__file__",
            source_type="ready_template",
            source_provenance=None,
            registered_inputs=registered_inputs,
            public_inputs=public_inputs,
            tail_lines=_ready_template_tail_lines(
                has_ltx_tail,
                workflow_nodes,
                edges_in,
                var_names,
                output_var_names,
                metadata,
            ),
            diagnostics=diagnostics,
            use_shared_helpers=True,
            constant_map=constant_map,
            section_groups=section_groups,
        )
    )
    out_lines.append("")

    combined = "\n".join(out_lines) + "\n"
    combined = _strip_unused_template_imports(combined)

    # -- readability diagnostic: generated_template_not_formatted -------------
    if diagnostics is not None:
        _check_template_formatting(combined, workflow_nodes, section_groups, diagnostics)

    # Validate syntax with ast.parse
    try:
        ast.parse(combined)
    except SyntaxError as exc:
        raise RuntimeError(f"Generated ready-template code failed syntax check: {exc}") from exc
    return combined


def emit_scratchpad_python(
    workflow,
    *,
    workflow_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    keep_virtual_wires: bool = False,
) -> str:
    workflow_id = workflow_id or getattr(workflow, "id", "scratchpad")
    prepared = _prepare_workflow_for_emit(
        workflow, apply_overrides=apply_overrides, keep_virtual_wires=keep_virtual_wires
    )
    source_path_expr = repr(source_path) if source_path is not None else "__file__"

    out_lines: list[str] = []
    out_lines.append("# vibecomfy: generated scratchpad")
    out_lines.append('"""Auto-generated VibeComfy scratchpad."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append("from vibecomfy.workflow import VibeWorkflow, WorkflowSource")
    out_lines.append("")
    out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr=repr(workflow_id),
            source_path_expr=source_path_expr,
            source_type="scratchpad",
            source_provenance=provenance or {},
            registered_inputs=registered_inputs,
            public_inputs=None,
            tail_lines=["    wf.finalize_metadata()"],
            diagnostics=diagnostics,
        )
    )
    out_lines.append("")
    out_lines.append(_NODE_HELPER_SOURCE)
    return "\n".join(out_lines) + "\n"


_VIRTUAL_WIRE_EMITTER_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})


def _prepare_workflow_for_emit(
    workflow: Any,
    *,
    apply_overrides: dict[str, Any] | None,
    template_id: str | None = None,
    keep_virtual_wires: bool = False,
) -> dict[str, Any]:
    # Defensive assertion: resolver MUST have eliminated all helper nodes before emission.
    # If any RESOLVABLE_HELPER_CLASS_TYPES node survives, the resolver has a bug.
    # Exception: when keep_virtual_wires=True, GetNode/SetNode/Reroute are intentionally
    # kept and emitted as explicit wf.node(...) calls — they pass through the assertion.
    # VALUE_HELPER_CLASS_TYPES (PrimitiveBoolean, etc.) still raise unconditionally.
    for nid, node in getattr(workflow, 'nodes', {}).items():
        if node.class_type in RESOLVABLE_HELPER_CLASS_TYPES:
            if keep_virtual_wires and node.class_type in _VIRTUAL_WIRE_EMITTER_CLASS_TYPES:
                continue
            raise ConversionParityError(
                f"Resolver bug: unresolved helper node {nid} "
                f"(class_type={node.class_type!r}) survived to emission. "
                f"The resolver must eliminate all RESOLVABLE_HELPER_CLASS_TYPES nodes "
                f"before _prepare_workflow_for_emit is called."
            )
    workflow_nodes = {
        nid: node
        for nid, node in workflow.nodes.items()
        if node.class_type not in UI_ONLY_CLASS_TYPES
    }
    edges_in: dict[str, list[Any]] = {}
    for edge in workflow.edges:
        if edge.from_node not in workflow_nodes or edge.to_node not in workflow_nodes:
            continue
        edges_in.setdefault(edge.to_node, []).append(edge)

    if apply_overrides:
        _apply_overrides(workflow_nodes, edges_in, apply_overrides.get("patches") or [])

    workflow_nodes, edges_in = _prune_dead_branches_for_emit(
        workflow_nodes,
        edges_in,
        template_id=template_id,
    )

    from vibecomfy.workflow import VibeEdge as _Edge

    extracted_edges_for_naming: list[Any] = []
    for nid, node in workflow_nodes.items():
        for key, value in {**node.inputs, **node.widgets}.items():
            if _is_link(value):
                extracted_edges_for_naming.append(_Edge(str(value[0]), str(value[1]), str(nid), key))

    var_names = _compute_variable_names(
        workflow_nodes,
        [edge for edges in edges_in.values() for edge in edges] + extracted_edges_for_naming,
    )
    output_var_names = _compute_output_variable_names(
        workflow_nodes,
        var_names,
        [edge for edges in edges_in.values() for edge in edges] + extracted_edges_for_naming,
    )
    return {
        "nodes": workflow_nodes,
        "edges_in": edges_in,
        "var_names": var_names,
        "output_var_names": output_var_names,
    }


def _prune_dead_branches_for_emit(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    *,
    template_id: str | None,
) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    if not output_node_ids:
        return workflow_nodes, edges_in

    live: set[str] = set(output_node_ids)
    pending = list(output_node_ids)
    while pending:
        node_id = pending.pop()
        node = workflow_nodes.get(node_id)
        if node is None:
            continue
        for edge in edges_in.get(node_id, []):
            if _is_dead_optional_output_input(node, str(getattr(edge, "to_input", "")), template_id):
                continue
            from_node = str(getattr(edge, "from_node", ""))
            if from_node in workflow_nodes and from_node not in live:
                live.add(from_node)
                pending.append(from_node)
        for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
            if _is_dead_optional_output_input(node, str(key), template_id):
                continue
            if not _is_link(value):
                continue
            from_node = str(value[0])
            if from_node in workflow_nodes and from_node not in live:
                live.add(from_node)
                pending.append(from_node)

    pruned_nodes = {nid: node for nid, node in workflow_nodes.items() if nid in live}
    pruned_edges_in: dict[str, list[Any]] = {}
    for to_node, edges in edges_in.items():
        if str(to_node) not in pruned_nodes:
            continue
        kept = [
            edge
            for edge in edges
            if str(getattr(edge, "from_node", "")) in pruned_nodes
            and not _is_dead_optional_output_input(
                pruned_nodes[str(to_node)],
                str(getattr(edge, "to_input", "")),
                template_id,
            )
        ]
        if kept:
            pruned_edges_in[str(to_node)] = kept
    return pruned_nodes, pruned_edges_in


def _is_dead_optional_output_input(node: Any, input_name: str, template_id: str | None) -> bool:
    class_type = str(getattr(node, "class_type", ""))
    if not _ltx_travel_template_omits_synthetic_audio(template_id):
        return False
    return (
        (class_type == "VHS_VideoCombine" and input_name == "audio")
        or (class_type == "LTXVConcatAVLatent" and input_name == "audio_latent")
    )


def _ltx_travel_template_omits_synthetic_audio(template_id: str | None) -> bool:
    lowered = str(template_id or "").lower()
    if not lowered.startswith("video/ltx2_3"):
        return False
    if any(token in lowered for token in ("audio", "lipsync", "talk")):
        return False
    return "first_last" in lowered or "first_middle_last" in lowered or "travel" in lowered


def _source_workflow_path(metadata: Mapping[str, Any]) -> str | None:
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping):
        source = provenance.get("source_workflow") or provenance.get("source_path")
        if isinstance(source, str) and source:
            return source
    source = metadata.get("source_workflow")
    return source if isinstance(source, str) and source else None


def _raw_workflow_from_metadata(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    source = _source_workflow_path(metadata)
    if not source:
        return None
    path = Path(source)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _all_nodes_for_imports(workflow_nodes: dict[str, Any], subgraphs: dict[str, _SubgraphDef]) -> dict[str, Any]:
    nodes = dict(workflow_nodes)
    for subgraph in subgraphs.values():
        for nid, node in subgraph.nodes.items():
            nodes.setdefault(_subgraph_emitted_node_id(subgraph.id, nid), node)
    return nodes


def slugify_subgraph_name(name: str, fallback_uuid: str) -> str:
    if not name:
        return f"subgraph_{fallback_uuid[:8].lower()}"
    name = re.sub(r"(?<=[A-Za-z])\.(?=\d)", "", name)
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"subgraph_{slug}" if slug else f"subgraph_{fallback_uuid[:8].lower()}"
    if keyword.iskeyword(slug):
        slug = f"{slug}_"
    return slug


_GENERIC_SUBGRAPH_LABELS: frozenset[str] = frozenset(
    {
        "arg",
        "argument",
        "input",
        "inputs",
        "output",
        "outputs",
        "parameter",
        "param",
        "value",
    }
)


def _slugify_identifier(value: str) -> str:
    candidate = str(value or "").lower()
    candidate = re.sub(r"[^a-z0-9_]+", "_", candidate)
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    if keyword.iskeyword(candidate):
        candidate = f"{candidate}_"
    return candidate


def _safe_kwarg_name(name: str, *, fallback: str) -> str:
    candidate = _slugify_identifier(str(name or ""))
    if not candidate or candidate[0].isdigit():
        candidate = _slugify_identifier(fallback)
    if not candidate or candidate[0].isdigit():
        candidate = "arg"
    return candidate


def _subgraph_input_kwarg_name(item: Mapping[str, Any], *, fallback: str) -> str:
    raw_name = str(item.get("name") or "")
    name_slug = _safe_kwarg_name(raw_name, fallback=fallback)
    label_raw = str(item.get("label") or "")
    label_slug = _slugify_identifier(label_raw)
    if (
        label_raw
        and label_slug
        and not label_slug[0].isdigit()
        and label_slug != name_slug
        and label_slug not in _GENERIC_SUBGRAPH_LABELS
    ):
        return label_slug
    return name_slug


def _unique_port_name(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _subgraph_definitions_from_raw(raw_workflow: dict[str, Any] | None, *, source_path: str | None) -> dict[str, _SubgraphDef]:
    if not isinstance(raw_workflow, dict):
        return {}
    raw_defs = raw_workflow.get("definitions")
    if not isinstance(raw_defs, dict):
        return {}
    raw_subgraphs = raw_defs.get("subgraphs")
    if isinstance(raw_subgraphs, Mapping):
        subgraph_items = list(raw_subgraphs.values())
    elif isinstance(raw_subgraphs, list):
        subgraph_items = raw_subgraphs
    else:
        return {}

    raw_by_id = {str(item.get("id")): item for item in subgraph_items if isinstance(item, dict) and item.get("id")}
    slugs = _disambiguated_subgraph_slugs(raw_by_id)
    out: dict[str, _SubgraphDef] = {}
    for subgraph_id, raw in raw_by_id.items():
        out[subgraph_id] = _build_subgraph_def(raw, slug=slugs[subgraph_id], source_path=source_path)
    return out


def _disambiguated_subgraph_slugs(raw_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for subgraph_id, raw in raw_by_id.items():
        grouped.setdefault(slugify_subgraph_name(str(raw.get("name") or ""), subgraph_id), []).append((subgraph_id, raw))

    slugs: dict[str, str] = {}
    for base, entries in grouped.items():
        if len(entries) == 1:
            slugs[entries[0][0]] = base
            continue
        ordered = sorted(entries, key=lambda item: (len(item[1].get("inputs") or ()), item[0]))
        min_inputs = len(ordered[0][1].get("inputs") or ())
        dual_used = False
        for index, (subgraph_id, raw) in enumerate(ordered):
            if index == 0:
                slugs[subgraph_id] = base
                continue
            input_count = len(raw.get("inputs") or ())
            if input_count > min_inputs and not dual_used:
                slugs[subgraph_id] = f"{base}_dual"
                dual_used = True
            else:
                slugs[subgraph_id] = f"{base}_{subgraph_id[:8].lower()}"
    return slugs


def _build_subgraph_def(raw: Mapping[str, Any], *, slug: str, source_path: str | None) -> _SubgraphDef:
    from vibecomfy.ingest.normalize import normalize_to_api
    from vibecomfy.workflow import VibeEdge as _Edge, VibeNode as _Node

    subgraph_id = str(raw["id"])
    used_input_names: set[str] = set()
    input_ports: list[_SubgraphPort] = []
    for index, item in enumerate(raw.get("inputs") or ()):
        if not isinstance(item, Mapping):
            continue
        source_name = str(item.get("name") or f"input_{index}")
        emitted_name = _unique_port_name(
            _subgraph_input_kwarg_name(item, fallback=f"input_{index}"),
            used_input_names,
        )
        input_ports.append(
            _SubgraphPort(
                emitted_name,
                str(item.get("type") or "") or None,
                source_name=source_name,
            )
        )
    declared_inputs = tuple(input_ports)

    used_output_names: set[str] = set()
    output_ports: list[_SubgraphPort] = []
    for index, item in enumerate(raw.get("outputs") or ()):
        if not isinstance(item, Mapping):
            continue
        source_name = str(item.get("name") or f"output_{index}")
        emitted_name = _unique_port_name(
            _safe_kwarg_name(source_name, fallback=f"output_{index}"),
            used_output_names,
        )
        output_ports.append(
            _SubgraphPort(
                emitted_name,
                str(item.get("type") or "") or None,
                source_name=source_name,
            )
        )
    outputs = tuple(output_ports)

    api = normalize_to_api({"nodes": list(raw.get("nodes") or ()), "links": list(raw.get("links") or ())}, use_comfy_converter=False)
    nodes: dict[str, Any] = {}
    edges_in: dict[str, list[Any]] = {}
    input_refs: dict[tuple[str, str], str] = {}
    defaults = _subgraph_default_args(raw, declared_inputs)

    for node_id, node in api.items():
        class_type = str(node.get("class_type", "Unknown"))
        if class_type in UI_ONLY_CLASS_TYPES:
            continue
        raw_inputs = dict(node.get("inputs", {}))
        static_inputs: dict[str, Any] = {}
        widgets: dict[str, Any] = {}
        for key, value in raw_inputs.items():
            if _is_any_link(value) and str(value[0]) == "-10":
                static_inputs[str(key)] = value
                continue
            if _is_any_link(value):
                continue
            if str(key).startswith("widget_"):
                widgets[str(key)] = value
            else:
                static_inputs[str(key)] = value
        metadata = {key: value for key, value in node.items() if key not in {"class_type", "inputs"}}
        output_names = _ui_output_names(metadata.get("_ui"))
        if output_names:
            metadata.setdefault("output_names", output_names)
        nodes[str(node_id)] = _Node(str(node_id), class_type, inputs=static_inputs, widgets=widgets, metadata=metadata)

    for node_id, node in api.items():
        if not isinstance(node, Mapping):
            continue
        for key, value in dict(node.get("inputs", {})).items():
            if not _is_any_link(value):
                continue
            from_node, from_slot = str(value[0]), int(value[1])
            if from_node == "-10":
                if 0 <= from_slot < len(input_ports):
                    input_refs[(str(node_id), str(key))] = input_ports[from_slot].name
            else:
                if str(node_id) not in nodes:
                    continue
                if from_node not in nodes:
                    input_name = _unique_port_name(
                        _safe_kwarg_name(str(key), fallback=f"input_{len(input_ports)}"),
                        used_input_names,
                    )
                    input_ports.append(
                        _SubgraphPort(
                            input_name,
                            None,
                            source_name=str(key),
                            external_ref=(from_node, from_slot),
                        )
                    )
                    nodes[str(node_id)].inputs[str(key)] = ["-10", len(input_ports) - 1]
                    input_refs[(str(node_id), str(key))] = input_name
                    continue
                edge = _Edge(from_node, str(from_slot), str(node_id), str(key))
                edges_in.setdefault(str(node_id), []).append(edge)

    inputs = tuple(input_ports)

    return_refs: list[tuple[str, int]] = []
    links = [link for link in raw.get("links") or () if isinstance(link, Mapping)]
    for index, _output in enumerate(outputs):
        target = next((link for link in links if str(link.get("target_id")) == "-20" and int(link.get("target_slot", -1)) == index), None)
        if target is not None:
            return_refs.append((str(target.get("origin_id")), int(target.get("origin_slot", 0))))

    return _SubgraphDef(
        id=subgraph_id,
        raw_name=str(raw.get("name") or ""),
        slug=slug,
        inputs=inputs,
        outputs=outputs,
        nodes=nodes,
        edges_in=edges_in,
        input_refs=input_refs,
        default_args=defaults,
        return_refs=tuple(return_refs),
        source_hash=subgraph_source_hash(
            raw,
            slug=slug,
            input_names=[port.name for port in inputs],
            return_refs=return_refs,
            runtime_graph=api,
        ),
        source_path=source_path,
    )


def subgraph_source_hash(
    raw: Mapping[str, Any],
    *,
    slug: str | None = None,
    input_names: list[str] | None = None,
    return_refs: list[tuple[str, int]] | None = None,
    runtime_graph: Mapping[str, Any] | None = None,
) -> str:
    payload = {
        "id": str(raw.get("id") or ""),
        "name": str(raw.get("name") or ""),
        "slug": slug,
        "runtime_graph": runtime_graph or {},
        "inputs": raw.get("inputs") or [],
        "outputs": raw.get("outputs") or [],
        "nodes": raw.get("nodes") or [],
        "links": raw.get("links") or [],
        "emitted_input_names": input_names or [],
        "return_refs": return_refs or [],
    }
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _is_any_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[1], int)


def _ui_output_names(ui: Any) -> list[str]:
    if not isinstance(ui, Mapping):
        return []
    names: list[str] = []
    for item in ui.get("outputs") or ():
        if isinstance(item, Mapping):
            names.append(str(item.get("name") or ""))
    return names


def _subgraph_default_args(raw: Mapping[str, Any], inputs: tuple[_SubgraphPort, ...]) -> dict[str, Any]:
    nodes = {str(node.get("id")): node for node in raw.get("nodes") or () if isinstance(node, Mapping)}
    links = {int(link.get("id")): link for link in raw.get("links") or () if isinstance(link, Mapping) and link.get("id") is not None}
    defaults: dict[str, Any] = {}
    for index, input_item in enumerate(raw.get("inputs") or ()):
        if not isinstance(input_item, Mapping) or index >= len(inputs):
            continue
        for link_id in input_item.get("linkIds") or ():
            link = links.get(int(link_id))
            if link is None:
                continue
            node = nodes.get(str(link.get("target_id")))
            if node is None:
                continue
            value = _widget_default_for_target(node, int(link.get("target_slot", -1)))
            if value is not None:
                defaults[inputs[index].name] = value
                break
    return defaults


def _widget_default_for_target(node: Mapping[str, Any], target_slot: int) -> Any:
    input_items = [item for item in node.get("inputs") or () if isinstance(item, Mapping)]
    if target_slot < 0 or target_slot >= len(input_items):
        return None
    target_input = input_items[target_slot]
    widget = target_input.get("widget")
    if not isinstance(widget, Mapping):
        return None
    widget_name = str(widget.get("name") or target_input.get("name") or "")
    return _ui_widget_values_by_name(node).get(widget_name)


def _apply_subgraph_names_to_prepared(prepared: dict[str, Any]) -> None:
    subgraphs: dict[str, _SubgraphDef] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return
    used = {str(var) for var in prepared.get("var_names", {}).values()}
    var_names: dict[str, str] = prepared["var_names"]
    output_var_names: dict[str, dict[int, str]] = prepared.setdefault("output_var_names", {})
    for node_id, node in prepared["nodes"].items():
        subgraph = subgraphs.get(str(node.class_type))
        if subgraph is None:
            continue
        getattr(node, "metadata", {}).setdefault("output_names", [port.name for port in subgraph.outputs])
        old = var_names.get(str(node_id))
        if old in used:
            used.remove(old)
        if len(subgraph.outputs) > 1:
            slot_vars: dict[int, str] = {}
            for index, output in enumerate(subgraph.outputs):
                slot_vars[index] = _unique_var(_safe_var(output.name.lower()), used)
            output_var_names[str(node_id)] = slot_vars
            # Avoid collision: var name must not equal subgraph function name
            base = _subgraph_result_base(subgraph.slug)
            if base == subgraph.slug:
                base = f"{subgraph.slug}_result"
            var_names[str(node_id)] = _unique_var(base, used)
        else:
            base = _subgraph_result_base(subgraph.slug)
            if base == subgraph.slug:
                base = f"{subgraph.slug}_result"
            var_names[str(node_id)] = _unique_var(base, used)


def _subgraph_result_base(slug: str) -> str:
    if slug.startswith("image_edit"):
        return "edited_dual" if slug.endswith("_dual") else "edited"
    if slug.startswith("text_to_image"):
        return "edited"
    return slug


def _unique_var(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used or keyword.iskeyword(candidate):
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _infer_public_input_bindings(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    *,
    reserved_names: set[str] | None = None,
) -> list[_PublicInputBinding]:
    bindings: list[_PublicInputBinding] = []
    used_names: set[str] = set(reserved_names or set())

    def add(
        name: str,
        node_id: str,
        field: str,
        *,
        type: str | None = None,
        required: bool = False,
        aliases: tuple[str, ...] = (),
        media_semantics: str | None = None,
    ) -> None:
        candidate_names = {name, *aliases}
        if candidate_names & used_names:
            return
        node = workflow_nodes.get(node_id)
        if node is None:
            return
        fields = _resolved_field_values(node)
        available = set(fields)
        incoming = {str(getattr(edge, "to_input", "")) for edge in edges_in.get(node_id, [])}
        if field not in available or field in incoming:
            return
        used_names.update(candidate_names)
        bindings.append(
            _PublicInputBinding(
                name=name,
                node_id=node_id,
                field=field,
                type=type,
                required=required,
                aliases=aliases,
                media_semantics=media_semantics,
            )
        )

    prompt_candidate: tuple[str, str] | None = None
    negative_candidate: tuple[str, str] | None = None
    for node_id, node in sorted(workflow_nodes.items(), key=lambda item: _id_sort_key(item[0])):
        fields = _resolved_field_values(node)
        class_type = str(getattr(node, "class_type", ""))
        title = _node_title(node).lower()

        if class_type in {"CLIPTextEncode", "CLIPTextEncodeFlux", "CLIPTextEncodeSD3", "CLIPTextEncodeSDXL", "TextEncodeQwenImageEdit"}:
            value = _resolve_graph_field_get_string(fields.get("text"), workflow_nodes)
            if isinstance(value, str):
                if "negative" in title:
                    negative_candidate = negative_candidate or (str(node_id), "text")
                elif value.strip():
                    prompt_candidate = prompt_candidate or (str(node_id), "text")
        primitive_value = _resolve_graph_field_get_string(fields.get("value"), workflow_nodes)
        if class_type in {"PrimitiveStringMultiline", "PrimitiveString"} and isinstance(
            primitive_value,
            str,
        ) and primitive_value.strip():
            prompt_candidate = prompt_candidate or (str(node_id), "value")
        if class_type == "LoadImage" and "image" in fields:
            add("image", str(node_id), "image", type="IMAGE", required=True, aliases=("input_image",), media_semantics="image")
        if "seed" in fields and isinstance(fields["seed"], int) and not isinstance(fields["seed"], bool):
            add("seed", str(node_id), "seed", type="INT")
        if "noise_seed" in fields and isinstance(fields["noise_seed"], int) and not isinstance(fields["noise_seed"], bool):
            add("seed", str(node_id), "noise_seed", type="INT")
        if "width" in fields and isinstance(fields["width"], int):
            add("width", str(node_id), "width", type="INT")
        if "height" in fields and isinstance(fields["height"], int):
            add("height", str(node_id), "height", type="INT")
        if "length" in fields and isinstance(fields["length"], int):
            add("frames", str(node_id), "length", type="INT")
        if "frames" in fields and isinstance(fields["frames"], int):
            add("frames", str(node_id), "frames", type="INT")
        if "fps" in fields and isinstance(fields["fps"], (int, float)):
            add("fps", str(node_id), "fps", type="FLOAT")

    if prompt_candidate is not None:
        add("prompt", prompt_candidate[0], prompt_candidate[1], type="STRING", required=True, media_semantics="text")
    if negative_candidate is not None:
        add("negative_prompt", negative_candidate[0], negative_candidate[1], type="STRING", aliases=("negative",), media_semantics="text")
    return bindings


def _node_title(node: Any) -> str:
    ui = getattr(node, "metadata", {}).get("_ui")
    if isinstance(ui, dict):
        title = ui.get("title")
        if isinstance(title, str):
            return title
    return ""


def _resolved_field_values(node: Any) -> dict[str, Any]:
    class_type = str(getattr(node, "class_type", ""))
    aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
    values: dict[str, Any] = {}
    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
        translated = _translate_widget_for_key(str(key), aliases, class_type)
        if translated is not None:
            values[translated] = value
    return values


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


def _emit_build_function(
    prepared: dict[str, Any],
    *,
    workflow_id_expr: str,
    source_path_expr: str,
    source_type: str,
    source_provenance: dict[str, Any] | None,
    registered_inputs: dict[str, tuple[str, str]] | None,
    public_inputs: list[_PublicInputSpec] | None,
    tail_lines: list[str],
    diagnostics: list[EmissionDiagnostic] | None = None,
    use_shared_helpers: bool = False,
    constant_map: dict[tuple[str, str], str] | None = None,
    section_groups: dict[str, list[str]] | None = None,
    function_name: str = "build",
    function_signature: str | None = None,
    function_docstring: list[str] | None = None,
    return_refs: tuple[tuple[str, int], ...] = (),
    external_refs: dict[tuple[str, str], str] | None = None,
    node_id_prefix: str | None = None,
    required_ids: set[str] | None = None,
) -> list[str]:
    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
    var_names = prepared["var_names"]
    output_var_names = prepared.get("output_var_names", {}) if use_shared_helpers else {}

    if constant_map is None:
        constant_map = {}
    if section_groups is None:
        section_groups = {}
    var_to_nid = {var: nid for nid, var in var_names.items()}
    for output_nid, slot_vars in output_var_names.items():
        for output_var in slot_vars.values():
            var_to_nid[str(output_var)] = str(output_nid)
    live_output_slots = _live_output_slots_for_function(
        workflow_nodes,
        ordering_edges_in,
        output_var_names,
        return_refs=return_refs,
        tail_lines=tail_lines,
    )
    public_preserve_fields: dict[str, set[str]] = {}
    for spec in public_inputs or []:
        node_ref = spec.node_ref
        if node_ref.startswith("ref("):
            try:
                ref_name = ast.literal_eval(node_ref[4:-1])
            except Exception:
                continue
        else:
            ref_name = node_ref
        nid = var_to_nid.get(str(ref_name))
        if nid is not None:
            public_preserve_fields.setdefault(nid, set()).add(spec.field)

    # Build a set of node IDs covered by section groups for fast lookup
    section_nids: set[str] = set()
    for nids in section_groups.values():
        section_nids.update(nids)

    # Build ordered list of (section_name, nid) for topological-sorted nodes
    topo_order = _topological_node_order(workflow_nodes, ordering_edges_in)
    section_order_map: dict[str, str] = {}  # nid -> section_name
    for section_name in _SECTION_ORDER:
        for nid in section_groups.get(section_name, []):
            section_order_map[nid] = section_name

    is_subgraph_function = function_name != "build"
    out_lines: list[str] = []
    if function_signature is not None:
        out_lines.extend(function_signature.splitlines())
    else:
        out_lines.append("def build() -> VibeWorkflow:")
    if function_docstring is None:
        out_lines.append('    """Build the workflow (auto-generated)."""')
    elif function_docstring:
        out_lines.extend(function_docstring)
    provenance_part = ""
    if source_provenance is not None:
        provenance_part = f",\n            provenance={_format_value(source_provenance)}"

    if is_subgraph_function:
        body_indent = "    "
        continuation_indent = "        "
    elif use_shared_helpers:
        # new_workflow() eagerly binds the ContextVar, so emit a plain assignment
        # rather than wrapping the body in `with new_workflow(...) as wf:`.
        # finalize() releases the binding.
        if source_type != "ready_template":
            out_lines.append(
                f"    wf = new_workflow({workflow_id_expr}, source_path={source_path_expr}, source_type={source_type!r})"
            )
        else:
            out_lines.append(
                f"    wf = new_workflow({workflow_id_expr}, source_path={source_path_expr})"
            )
        body_indent = "    "
        continuation_indent = "        "
    else:
        out_lines.append(
            "    wf = VibeWorkflow(\n"
            f"        {workflow_id_expr},\n"
            "        WorkflowSource(\n"
            f"            id={workflow_id_expr},\n"
            f"            path={source_path_expr},\n"
            f"            source_type={source_type!r}"
            f"{provenance_part},\n"
            "        ),\n"
            "    )"
        )
        body_indent = "    "
        continuation_indent = "        "
    out_lines.append("")

    emitted_sections: set[str] = set()
    for nid in topo_order:
        node = workflow_nodes[nid]
        var = var_names[nid]

        # -- readability diagnostic: variable name too long -------------------
        if diagnostics is not None and len(var) > 40:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
                    message=(
                        f"Variable name {var!r} ({len(var)} chars) exceeds 40-character threshold; "
                        f"consider a shorter semantic name."
                    ),
                    severity="warning",
                    node_id=str(nid),
                    class_type=node.class_type,
                    detail={"variable_name": var, "length": len(var)},
                )
            )

        # Emit section comment if entering a new section group
        section = section_order_map.get(nid)
        if section is not None and section not in emitted_sections:
            if out_lines and out_lines[-1] != "":
                out_lines.append("")
            out_lines.append(f"{body_indent}# {section}")
            emitted_sections.add(section)

        wrapper_module = _wrapper_module_for_class(str(node.class_type)) if use_shared_helpers else None
        preserve_fields = {
            field
            for old_id, field in (registered_inputs or {}).values()
            if old_id == nid
        }
        preserve_fields.update(public_preserve_fields.get(nid, set()))
        kwargs = _node_kwargs(
            node, edges_in, var_names,
            workflow_nodes=workflow_nodes,
            output_var_names=output_var_names,
            diagnostics=diagnostics,
            constant_map=constant_map,
            use_ui_widget_aliases=use_shared_helpers,
            strip_schema_defaults=use_shared_helpers,
            omit_single_output_metadata=use_shared_helpers,
            bare_single_output_refs=use_shared_helpers,
            emit_reserved_keyword_args=wrapper_module is not None,
            preserve_fields=preserve_fields,
            external_refs=external_refs,
        )

        if use_shared_helpers:
            subgraph = (prepared.get("subgraph_definitions") or {}).get(str(node.class_type))
            if subgraph is not None:
                stmt_lines = _emit_subgraph_call_statement(
                    node,
                    subgraph,
                    edges_in,
                    var_names,
                    output_var_names,
                    workflow_nodes,
                    body_indent=body_indent,
                    continuation_indent=continuation_indent,
                    diagnostics=diagnostics,
                )
                # Subgraph calls share the node-call blank-line rhythm: multi-line
                # statements are surrounded by blank lines, single-line ones pack.
                is_multiline = len(stmt_lines) > 1
                if is_multiline:
                    prev = out_lines[-1] if out_lines else ""
                    if out_lines and prev != "" and not prev.lstrip().startswith("# "):
                        out_lines.append("")
                out_lines.extend(stmt_lines)
                if is_multiline:
                    out_lines.append("")
                continue

            use_wrapper = wrapper_module is not None
            ready_kwargs: list[tuple[str, str]] = []
            outputs_expr: str | None = None
            extras_expr: str | None = None
            for key, expr in kwargs:
                if key == "_outputs":
                    outputs_expr = expr
                elif key == "_extras":
                    extras_expr = expr
                else:
                    ready_kwargs.append((key, expr))

            # Durable node identity (M2, T13): carry _uid= through the
            # ready-template emission paths (typed wrapper + raw_call), mirroring
            # the scratchpad _node() mechanism. node()/raw_call apply it verbatim.
            uid_arg = ("_uid", repr(node.uid)) if node.uid else None

            if use_wrapper:
                all_args = []
                if is_subgraph_function and node_id_prefix is not None:
                    if _subgraph_node_id_required(node_id_prefix, nid, required_ids):
                        all_args.append(("_id", repr(_subgraph_emitted_node_id(node_id_prefix, nid))))
                elif not is_subgraph_function:
                    all_args.append(("_id", repr(str(nid))))
                all_args.extend((_wrapper_kwarg_name(key), expr) for key, expr in ready_kwargs)
                if uid_arg is not None:
                    all_args.append(uid_arg)
                # v2.6.4 Fix 3: drop _outputs= for schema-known typed wrappers.
                # The wrapper class already knows its output names from the
                # generated schema (vibecomfy/nodes/_generated/<pack>.py). Only
                # raw_call (UUID fallback, no schema) needs explicit _outputs.
                if extras_expr is not None:
                    all_args.append(("**", extras_expr))
                call_name = _wrapper_symbol_for_class(str(node.class_type)) or str(node.class_type)
                assignment_target = _assignment_target(
                    var,
                    output_var_names.get(str(nid)),
                    live_slots=live_output_slots.get(str(nid)),
                )
            else:
                all_args = []
                if outputs_expr is not None:
                    all_args.append(("_outputs", outputs_expr))
                all_args.extend(ready_kwargs)
                if uid_arg is not None:
                    all_args.append(uid_arg)
                if extras_expr is not None:
                    all_args.append(("_extras", extras_expr))
                call_name = "node"
                assignment_target = var

            # Multi-line formatting: use multi-line when >3 kwargs or any line would exceed ~88 chars
            kwarg_lines = [f"**{expr}" if key == "**" else f"{key}={expr}" for key, expr in all_args]
            if use_wrapper:
                call_args = ", ".join(kwarg_lines)
                call_expr = f"{call_name}({call_args})"
            else:
                # v2.6.4 Fix 5: raw_call reads wf from ContextVar (set by
                # new_workflow context manager); no need to pass wf positional.
                raw_node_id = _subgraph_emitted_node_id(node_id_prefix, nid) if is_subgraph_function and node_id_prefix is not None else nid
                call_args = ", ".join([repr(node.class_type), repr(raw_node_id), *kwarg_lines])
                call_expr = f"raw_call({call_args})"
            single_line = (
                f"{body_indent}{assignment_target} = {call_expr}"
                if assignment_target is not None
                else f"{body_indent}{call_expr}"
            )

            # -- readability diagnostic: long one-line node call ----------
            if diagnostics is not None and len(single_line) > 120:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
                        message=(
                            f"node call for {node.class_type!r} (node {nid}) would be a single "
                            f"line of {len(single_line)} chars (>120); multi-line formatting preferred."
                        ),
                        severity="warning",
                        node_id=str(nid),
                        class_type=node.class_type,
                        detail={"line_length": len(single_line)},
                    )
                )

            prefer_single_line_raw_call = not use_wrapper and len(all_args) <= 2 and len(single_line) <= 120
            if not prefer_single_line_raw_call and (len(all_args) > 3 or len(single_line) > 88):
                # v2.6.4 Fix 8 (refines Fix 2): multi-line statements are
                # SURROUNDED by blank lines (one before, one after) for
                # consistent vertical rhythm — including when followed by
                # single-line statements. Single-line statements still pack
                # together. Section comments stay attached to the first
                # multi-line that follows (no blank between).
                prev = out_lines[-1] if out_lines else ""
                is_section_comment = prev.lstrip().startswith("# ")
                if out_lines and prev != "" and not is_section_comment:
                    out_lines.append("")
                if use_wrapper:
                    head = f"{body_indent}{call_name}(" if assignment_target is None else f"{body_indent}{assignment_target} = {call_name}("
                    lines = [head]
                else:
                    # v2.6.4 Fix 5: drop wf positional from raw_call (ContextVar).
                    raw_node_id = _subgraph_emitted_node_id(node_id_prefix, nid) if is_subgraph_function and node_id_prefix is not None else nid
                    head = (
                        f"{body_indent}raw_call({node.class_type!r}, {raw_node_id!r},"
                        if assignment_target is None
                        else f"{body_indent}{assignment_target} = raw_call({node.class_type!r}, {raw_node_id!r},"
                    )
                    lines = [head]
                for key, expr in all_args:
                    if key == "**":
                        lines.append(f"{continuation_indent}**{expr},")
                    else:
                        lines.append(f"{continuation_indent}{key}={expr},")
                lines.append(f"{body_indent})")
                out_lines.extend(lines)
                out_lines.append("")
            else:
                out_lines.append(single_line)
        else:
            _uid_str = f", _uid={node.uid!r}" if node.uid else ""
            head = f"    {var} = _node(wf, {node.class_type!r}, {nid!r}{_uid_str}"
            if not kwargs:
                out_lines.append(f"{head})")
            else:
                out_lines.append(f"{head},")
                for key, expr in kwargs:
                    out_lines.append(f"        {key}={expr},")
                out_lines.append("    )")

    if use_shared_helpers:
        if out_lines and out_lines[-1] != "":
            out_lines.append("")
        if is_subgraph_function:
            out_lines.append(f"{body_indent}return {_subgraph_return_expr(return_refs, workflow_nodes, var_names, output_var_names, diagnostics)}")
        else:
            tail_lines = _with_id_map_tail_line(tail_lines, var_names)
            # tail_lines are pre-indented at 4 spaces ("    return wf.finalize(...)").
            # When use_shared_helpers emits a flat `wf = new_workflow(...)` form,
            # body_indent is 4, so emit tail lines verbatim.  When a `with`
            # wrapper is in use (body_indent == 8), prepend an extra 4 spaces.
            extra_indent = "    " if body_indent == "        " else ""
            out_lines.extend(extra_indent + line if line else line for line in tail_lines)
        return out_lines
    out_lines.append("")
    out_lines.extend(tail_lines)
    if registered_inputs:
        for input_name, (old_id, field) in registered_inputs.items():
            resolved_field = field
            if field.startswith("widget_") and old_id in workflow_nodes:
                cls = workflow_nodes[old_id].class_type
                node = workflow_nodes[old_id]
                aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
                resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
                if resolved.name is not None:
                    resolved_field = resolved.name
            descriptor_kwargs: list[str] = []
            if old_id in workflow_nodes:
                node = workflow_nodes[old_id]
                if resolved_field in node.inputs:
                    descriptor_kwargs.append(f"default={_format_value(node.inputs[resolved_field])}")
                elif resolved_field in node.widgets:
                    descriptor_kwargs.append(f"default={_format_value(node.widgets[resolved_field])}")
            if use_shared_helpers:
                suffix = ", " + ", ".join(descriptor_kwargs) if descriptor_kwargs else ""
                out_lines.append(f"    bind_input(wf, {input_name!r}, {_node_binding_expr(old_id, var_names)}, {resolved_field!r}{suffix})")
            else:
                suffix = ", " + ", ".join(descriptor_kwargs) if descriptor_kwargs else ""
                out_lines.append(
                    f"    wf.register_input({input_name!r}, {old_id!r}, {resolved_field!r}, "
                    f"wf.nodes[{old_id!r}].inputs.get({resolved_field!r}, wf.nodes[{old_id!r}].widgets.get({resolved_field!r})){suffix})"
                )

    out_lines.append("    return wf")
    return out_lines


def _with_id_map_tail_line(tail_lines: list[str], var_names: dict[str, str]) -> list[str]:
    # v2.6.4 fix: id_map is derived at runtime via wf.id_map() (returns
    # {ClassType#N: node_id}). The build() source is the authoritative
    # variable-name binding; storing it again at runtime via _set_id_map
    # was bloat that scaled linearly with node count (60+ entry one-line
    # dicts on LTX templates). Drop the emission entirely.
    return tail_lines


def _emit_subgraph_functions(
    prepared: dict[str, Any],
    *,
    diagnostics: list[EmissionDiagnostic] | None,
    constant_map: dict[tuple[str, str], str] | None,
    required_ids_by_subgraph: dict[str, set[str]] | None = None,
) -> list[str]:
    subgraphs: dict[str, _SubgraphDef] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return []
    lines = ["# === Subgraph functions ===", ""]
    for subgraph_id in _subgraph_topological_order(subgraphs):
        subgraph = subgraphs[subgraph_id]
        inner_prepared = {
            "nodes": subgraph.nodes,
            "edges_in": subgraph.edges_in,
            "var_names": _compute_variable_names(subgraph.nodes, [edge for edges in subgraph.edges_in.values() for edge in edges]),
            "subgraph_definitions": subgraphs,
        }
        inner_prepared["output_var_names"] = _compute_output_variable_names(
            subgraph.nodes,
            inner_prepared["var_names"],
            [edge for edges in subgraph.edges_in.values() for edge in edges],
        )
        _apply_subgraph_names_to_prepared(inner_prepared)
        signature = _subgraph_signature(subgraph)
        docstring = _subgraph_docstring(subgraph)
        lines.extend(
            _emit_build_function(
                inner_prepared,
                workflow_id_expr="READY_METADATA",
                source_path_expr="__file__",
                source_type="ready_template",
                source_provenance=None,
                registered_inputs=None,
                public_inputs=None,
                tail_lines=[],
                diagnostics=diagnostics,
                use_shared_helpers=True,
                constant_map=constant_map,
                section_groups={},
                function_name=subgraph.slug,
                function_signature=signature,
                function_docstring=docstring,
                return_refs=subgraph.return_refs,
                external_refs=subgraph.input_refs,
                node_id_prefix=subgraph.id,
                required_ids=required_ids_by_subgraph.get(subgraph.id, set()) if required_ids_by_subgraph is not None else None,
            )
        )
        lines.append("")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _subgraph_topological_order(subgraphs: dict[str, _SubgraphDef]) -> list[str]:
    deps = {
        subgraph_id: {
            str(node.class_type)
            for node in subgraph.nodes.values()
            if str(node.class_type) in subgraphs
        }
        for subgraph_id, subgraph in subgraphs.items()
    }
    temporary: set[str] = set()
    permanent: set[str] = set()
    ordered: list[str] = []

    def visit(subgraph_id: str, stack: list[str]) -> None:
        if subgraph_id in permanent:
            return
        if subgraph_id in temporary:
            cycle = " -> ".join([*stack, subgraph_id])
            raise RuntimeError(f"Circular subgraph reference detected: {cycle}")
        temporary.add(subgraph_id)
        for dep in sorted(deps.get(subgraph_id, ())):
            visit(dep, [*stack, subgraph_id])
        temporary.remove(subgraph_id)
        permanent.add(subgraph_id)
        ordered.append(subgraph_id)

    for subgraph_id in subgraphs:
        visit(subgraph_id, [])
    return ordered


def _short_subgraph_id_prefix(subgraph_id: str) -> str:
    if len(subgraph_id) >= 32 and "-" in subgraph_id:
        return subgraph_id[:8]
    return subgraph_id


def _subgraph_emitted_node_id(subgraph_id: str, node_id: str) -> str:
    return f"{_short_subgraph_id_prefix(subgraph_id)}:{node_id}"


def _subgraph_node_id_required(
    node_id_prefix: str | None,
    nid: str,
    required_ids: set[str] | None,
) -> bool:
    """Return True if a subgraph node's explicit _id= kwarg is load-bearing.

    When *required_ids* is None, all node IDs are considered required (backward
    compatibility for paths that do not supply the precomputed set).  Otherwise
    only nodes whose inner ID appears in the set need an explicit _id=.
    """
    if required_ids is None:
        return True
    return nid in required_ids


COMFY_TYPE_TO_PY_HINT = {
    "STRING": "str",
    "INT": "int",
    "FLOAT": "float",
    "BOOLEAN": "bool",
    "COMBO": "str",
}


def _subgraph_signature(subgraph: _SubgraphDef) -> str:
    if not subgraph.inputs:
        return f"def {subgraph.slug}():"
    lines = [f"def {subgraph.slug}("]
    lines.append("    *,")
    for port in subgraph.inputs:
        hint = COMFY_TYPE_TO_PY_HINT.get(str(port.type or "").upper())
        annotation = f": {hint}" if hint else ""
        lines.append(f"    {port.name}{annotation},")
    lines.append("):")
    return "\n".join(lines)


def _subgraph_docstring(subgraph: _SubgraphDef) -> list[str]:
    title = subgraph.raw_name or subgraph.slug.replace("_", " ").title()
    variant = ""
    image_inputs = sum(1 for port in subgraph.inputs if str(port.type or "").upper() == "IMAGE")
    if image_inputs == 1:
        variant = " - single-image variant"
    elif image_inputs > 1:
        variant = " - two-image variant" if image_inputs == 2 else f" - {image_inputs}-image variant"
    source = f" in {subgraph.source_path}" if subgraph.source_path else ""
    classes = [str(node.class_type) for node in subgraph.nodes.values()]
    class_counts = Counter(classes)
    inner = []
    seen: set[str] = set()
    for cls in classes:
        if cls in seen:
            continue
        seen.add(cls)
        count = class_counts[cls]
        inner.append(f"{cls}x{count}" if count > 1 else cls)
    lines = [
        f'    """{title}{variant}.',
        "",
        f"    Materialized from subgraph {subgraph.id}{source}.",
        f"    # vibecomfy source hash: sha256:{subgraph.source_hash}",
    ]
    if inner:
        lines.append(f"    Inner nodes: {', '.join(inner)}.")
    lines.append('    """')
    return lines


def _emit_subgraph_call_statement(
    node: Any,
    subgraph: _SubgraphDef,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    workflow_nodes: dict[str, Any],
    *,
    body_indent: str,
    continuation_indent: str,
    diagnostics: list[EmissionDiagnostic] | None,
) -> list[str]:
    live_output_slots = _live_output_slots_for_function(
        workflow_nodes,
        edges_in,
        output_var_names,
    )
    assignment_target = _assignment_target(
        var_names[str(node.id)],
        output_var_names.get(str(node.id)),
        live_slots=live_output_slots.get(str(node.id)),
    )
    kwargs = _subgraph_call_kwargs(
        node,
        subgraph,
        edges_in,
        var_names,
        output_var_names,
        workflow_nodes,
        diagnostics=diagnostics,
    )
    kwarg_lines = [f"{key}={expr}" for key, expr in kwargs]
    call_expr = f"{subgraph.slug}({', '.join(kwarg_lines)})"
    single_line = (
        f"{body_indent}{assignment_target} = {call_expr}"
        if assignment_target is not None
        else f"{body_indent}{call_expr}"
    )
    if len(kwargs) > 3 or len(single_line) > 88:
        head = f"{body_indent}{subgraph.slug}(" if assignment_target is None else f"{body_indent}{assignment_target} = {subgraph.slug}("
        lines = [head]
        for key, expr in kwargs:
            lines.append(f"{continuation_indent}{key}={expr},")
        lines.append(f"{body_indent})")
        return lines
    return [single_line]


def _subgraph_call_kwargs(
    node: Any,
    subgraph: _SubgraphDef,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    workflow_nodes: dict[str, Any],
    *,
    diagnostics: list[EmissionDiagnostic] | None,
) -> list[tuple[str, str]]:
    incoming: dict[str, tuple[str, int]] = {}
    for edge in edges_in.get(str(node.id), []):
        incoming[str(edge.to_input)] = (str(edge.from_node), int(edge.from_output))
    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
        if _is_link(value):
            incoming.setdefault(str(key), (str(value[0]), int(value[1])))

    static = {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}
    widget_values = _subgraph_instance_widget_values(node)
    port_candidate_names = _subgraph_instance_port_candidate_names(node, subgraph)
    kwargs: list[tuple[str, str]] = []
    for index, port in enumerate(subgraph.inputs):
        if port.external_ref is not None:
            src, slot = port.external_ref
            kwargs.append(
                (
                    port.name,
                    _edge_ref_expr(
                        workflow_nodes,
                        var_names,
                        output_var_names,
                        src,
                        slot,
                        bare_single_output_refs=True,
                        diagnostics=diagnostics,
                        target_node=node,
                        target_input=port.name,
                    ),
                )
            )
            continue
        candidate_names = port_candidate_names.get(index, (port.name, port.source_name or port.name))
        incoming_name = next((name for name in candidate_names if name in incoming), None)
        widget_name = next((name for name in candidate_names if name in widget_values), None)
        static_name = next((name for name in candidate_names if name in static), None)
        default_name = next((name for name in candidate_names if name in subgraph.default_args), None)
        if incoming_name is not None:
            src, slot = incoming[incoming_name]
            kwargs.append(
                (
                    port.name,
                    _edge_ref_expr(
                        workflow_nodes,
                        var_names,
                        output_var_names,
                        src,
                        slot,
                        bare_single_output_refs=True,
                        diagnostics=diagnostics,
                        target_node=node,
                        target_input=incoming_name,
                    ),
                )
            )
        elif widget_name is not None:
            kwargs.append((port.name, _format_value(widget_values[widget_name])))
        elif static_name is not None and not _is_link(static[static_name]):
            kwargs.append((port.name, _format_value(static[static_name])))
        elif default_name is not None:
            kwargs.append((port.name, _format_value(subgraph.default_args[default_name])))
        else:
            kwargs.append((port.name, "None"))
            if diagnostics is not None:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
                        message=(
                            f"Subgraph input {port.name!r} on node {node.id} "
                            f"({subgraph.id}) has no incoming edge or widget value; emitting None."
                        ),
                        severity="warning",
                        node_id=str(node.id),
                        class_type=str(getattr(node, "class_type", "")),
                        detail={"subgraph_id": subgraph.id, "input_name": port.name},
                    )
                )
    return kwargs


def _subgraph_instance_port_candidate_names(node: Any, subgraph: _SubgraphDef) -> dict[int, tuple[str, ...]]:
    ui = getattr(node, "metadata", {}).get("_ui")
    input_items = [item for item in (ui or {}).get("inputs") or () if isinstance(item, Mapping)] if isinstance(ui, Mapping) else []
    out: dict[int, tuple[str, ...]] = {}
    for index, port in enumerate(subgraph.inputs):
        names: list[str] = []

        def add(value: Any) -> None:
            name = str(value or "")
            if name and name not in names:
                names.append(name)

        add(port.name)
        add(port.source_name)
        for item in input_items:
            raw_name = str(item.get("name") or "")
            label_slug = _slugify_identifier(str(item.get("label") or ""))
            identity = {name for name in (raw_name, label_slug) if name}
            if port.name not in identity and (port.source_name or "") not in identity:
                continue
            add(raw_name)
            add(label_slug)
            if not raw_name and item.get("link") is not None:
                add(f"_un{item.get('link')}")
        out[index] = tuple(names)
    return out


def _subgraph_instance_widget_values(node: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
        if _is_link(value):
            continue
        translated = _translate_widget_for_key(str(key), aliases, str(getattr(node, "class_type", "")))
        values[translated or str(key)] = value

    ui = getattr(node, "metadata", {}).get("_ui")
    if not isinstance(ui, Mapping):
        return values
    values.update(_ui_widget_values_by_name(ui))
    input_items = [item for item in ui.get("inputs") or () if isinstance(item, Mapping)]
    for item in input_items:
        widget = item.get("widget")
        if not isinstance(widget, Mapping):
            continue
        input_name = str(item.get("name") or widget.get("name") or "")
        if not input_name or input_name in values:
            continue
        for value_key in ("value", "default", "default_value"):
            if value_key in item:
                values[input_name] = item[value_key]
                break
    return values


def _positional_ui_widget_names(ui_node: Mapping[str, Any], value_count: int) -> list[str | None]:
    """Return authoritative names for positional ``widgets_values`` slots.

    The list is intentionally keyed by widget-value position, not input-item
    position.  Callers must only consume positions with a real non-empty name so
    UI-only or anonymous widgets cannot shift later values into the wrong field.
    """
    names: list[str | None] = [None] * value_count
    blocked_indices: set[int] = set()
    class_type = str(ui_node.get("type") or ui_node.get("class_type") or "")

    def set_name(index: int, raw_name: Any) -> None:
        if index < 0 or index >= value_count:
            return
        if index in blocked_indices:
            return
        if names[index] is not None:
            return
        name = str(raw_name or "")
        if name:
            names[index] = name

    explicit_widgets = ui_node.get("widgets")
    if isinstance(explicit_widgets, list):
        for index, item in enumerate(explicit_widgets):
            if isinstance(item, Mapping):
                set_name(index, item.get("name"))
            else:
                set_name(index, item)

    explicit_inputs = ui_node.get("widget_inputs")
    if isinstance(explicit_inputs, list):
        for index, item in enumerate(explicit_inputs):
            if isinstance(item, Mapping):
                set_name(index, item.get("name"))
            else:
                set_name(index, item)

    aliases = ui_node.get("input_aliases")
    if not isinstance(aliases, (list, tuple)):
        properties = ui_node.get("properties")
        aliases = properties.get("input_aliases") if isinstance(properties, Mapping) else None
    if isinstance(aliases, (list, tuple)):
        for index, name in enumerate(aliases):
            set_name(index, name)

    properties = ui_node.get("properties")
    proxy_widgets = properties.get("proxyWidgets") if isinstance(properties, Mapping) else None
    if isinstance(proxy_widgets, list):
        for index, item in enumerate(proxy_widgets):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            set_name(index, item[1])

    schema = WIDGET_SCHEMA.get(class_type)
    if schema is not None:
        for index, name in enumerate(schema):
            if name is None and 0 <= index < value_count and names[index] is None:
                blocked_indices.add(index)
            else:
                set_name(index, name)

    try:
        from vibecomfy.porting.object_info.consume import object_info_widget_order

        object_info_names = object_info_widget_order(class_type)
    except Exception:
        object_info_names = []
    for index, name in enumerate(object_info_names):
        set_name(index, name)

    input_items = [item for item in ui_node.get("inputs") or () if isinstance(item, Mapping)]
    widget_index = 0
    for item in input_items:
        widget = item.get("widget")
        if not isinstance(widget, Mapping):
            continue
        widget_name = widget.get("name")
        if isinstance(widget_name, str) and widget_name:
            set_name(widget_index, widget_name)
            widget_index += 1
    return names


def _ui_widget_values_by_name(ui_node: Mapping[str, Any]) -> dict[str, Any]:
    raw_values = ui_node.get("widgets_values")
    if isinstance(raw_values, Mapping):
        return {str(key): value for key, value in raw_values.items()}
    if not isinstance(raw_values, list):
        return {}

    values: dict[str, Any] = {}
    for index, name in enumerate(_positional_ui_widget_names(ui_node, len(raw_values))):
        if name is not None:
            values[name] = raw_values[index]
    return values


def _subgraph_return_expr(
    return_refs: tuple[tuple[str, int], ...],
    workflow_nodes: dict[str, Any],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    diagnostics: list[EmissionDiagnostic] | None,
) -> str:
    refs = [
        _edge_ref_expr(
            workflow_nodes,
            var_names,
            output_var_names,
            node_id,
            slot,
            bare_single_output_refs=True,
            diagnostics=diagnostics,
            target_node=None,
            target_input="return",
        )
        for node_id, slot in return_refs
    ]
    if not refs:
        return "None"
    return ", ".join(refs)


_OUTPUT_CLASSES: dict[str, tuple[str, str]] = {
    "SaveImage": ("image", "image/png"),
    "PreviewImage": ("image", "image/png"),
    "SaveVideo": ("video", "video/mp4"),
    "VHS_VideoCombine": ("video", "video/mp4"),
    "SaveAudio": ("audio", "audio/wav"),
    "SaveAudioMP3": ("audio", "audio/mpeg"),
}


def _ready_template_tail_lines(
    has_ltx_tail: bool,
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    metadata: Mapping[str, Any],
) -> list[str]:
    finalize_args = _finalize_args(workflow_nodes, edges_in, var_names, output_var_names, metadata)
    input_expr = "PUBLIC_INPUT_METADATA" if metadata.get("_has_public_inputs_for_emit") else "{}"
    call = f"    return wf.finalize({input_expr}{finalize_args})"
    if has_ltx_tail:
        return [
            "    apply_ltx_lowvram(wf)",
            "    resolution(384, 256, 9).apply(wf)",
            "    ensure_custom_nodes(wf, READY_METADATA.get(\"requirements\", {}).get(\"custom_nodes\", []))",
            call,
        ]
    return [call]


def _finalize_args(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    metadata: Mapping[str, Any],
) -> str:
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    args: list[str] = []
    selected_id: str | None = output_node_ids[0] if output_node_ids else None
    if selected_id is not None:
        # Bind output_node to the specific node's emitter-assigned variable name
        # so the finalize call is self-documenting (and so downstream tooling can
        # introspect the chosen terminal node).
        output_var = _first_output_var(output_var_names.get(selected_id))
        args.append(f"output_node={output_var or var_names.get(selected_id, repr(selected_id))}")
    if selected_id is not None:
        node = workflow_nodes[selected_id]
        output_contract = _OUTPUT_CLASSES.get(str(node.class_type))
        if output_contract is not None:
            artifact_kind, mime_type = output_contract
            args.append(f"output_type={node.class_type!r}")
            args.append(f"name={artifact_kind!r}")
            args.append(f"artifact_kind={artifact_kind!r}")
            args.append(f"mime_type={mime_type!r}")
            args.append("expected_cardinality='one'")
        prefix_raw = node.inputs.get("filename_prefix", node.widgets.get("filename_prefix"))
        if prefix_raw is not None and prefix_raw != metadata.get("output_prefix"):
            args.append(f"filename_prefix={_format_value(prefix_raw)}")
    if not args:
        return ""
    return ", " + ", ".join(args)


def _terminal_output_node_ids(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> list[str]:
    outgoing = {
        str(edge.from_node)
        for edges in edges_in.values()
        for edge in edges
    }
    candidates = [
        nid
        for nid, node in workflow_nodes.items()
        if nid not in outgoing and _is_output_class(str(node.class_type))
    ]
    return sorted(candidates, key=_id_sort_key)


def _is_output_class(class_type: str) -> bool:
    if class_type in _OUTPUT_CLASSES:
        return True
    lowered = class_type.lower()
    return lowered.startswith(("save", "preview", "create")) or "save" in lowered or "preview" in lowered


def _node_binding_expr(node_id: str, var_names: dict[str, str]) -> str:
    var = var_names.get(str(node_id))
    if var is not None and _wrapper_module_for_class(var.split("_", 1)[0]) is not None:
        return f"{var}.node.id"
    if var is not None:
        return f"{var}.node.id"
    return repr(str(node_id))


def _edge_ref_expr(
    workflow_nodes: dict[str, Any] | None,
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    from_node_str: str,
    from_slot: int,
    *,
    bare_single_output_refs: bool,
    diagnostics: list[EmissionDiagnostic] | None,
    target_node: Any,
    target_input: str,
) -> str:
    if from_node_str in var_names:
        unpacked_ref = output_var_names.get(from_node_str, {}).get(from_slot)
        if unpacked_ref is not None:
            return unpacked_ref
        if bare_single_output_refs and _is_single_output_ref(workflow_nodes, from_node_str, from_slot):
            return var_names[from_node_str]
        safe_name = _safe_output_name(workflow_nodes, from_node_str, from_slot)
        if safe_name is not None:
            return f"{var_names[from_node_str]}.out({safe_name!r})"
        if diagnostics is not None and workflow_nodes is not None:
            _output_fallback_diagnostic(
                diagnostics, workflow_nodes, from_node_str, from_slot,
                target_node=target_node, target_input=target_input,
            )
        return f"{var_names[from_node_str]}.out({from_slot})"
    return f"[{from_node_str!r}, {from_slot}]"


def _wrapper_kwarg_name(name: str) -> str:
    return f"{name}_" if name in RESERVED_WRAPPER_INPUT_NAMES or keyword.iskeyword(name) else name


def _check_template_formatting(
    combined: str,
    workflow_nodes: dict[str, Any],
    section_groups: dict[str, list[str]],
    diagnostics: list[EmissionDiagnostic],
) -> None:
    """Check generated template for section comments and indentation hygiene.

    Two checks:
    1. If the workflow has >=8 nodes and section_groups are non-empty but no
       section comment lines appear in the output.
    2. If any line in the tail (after the build function body) is un-indented
       (does not start with 4 spaces, '#', blank, or a string-like line).
    """
    lines = combined.split("\n")

    # Check 1: missing section comments for large workflows
    if len(workflow_nodes) >= _SECTION_NODE_THRESHOLD and section_groups:
        has_section_comment = any(
            line.strip().startswith("# ") and any(
                line.strip().endswith(f"# {sec}")
                or line.strip() == f"# {sec}"
                or line.strip().startswith(f"# {sec}")
                for sec in _SECTION_ORDER
            )
            for line in lines
        )
        if not has_section_comment:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
                    message=(
                        f"Generated template has {len(workflow_nodes)} nodes but lacks section "
                        f"comments (e.g. # Inputs, # Loaders, # Conditioning). "
                        f"Section comments improve readability for large workflows."
                    ),
                    severity="warning",
                    detail={
                        "node_count": len(workflow_nodes),
                        "section_groups_present": bool(section_groups),
                    },
                )
            )

    # Check 2: un-indented tail lines (after build function)
    # Find the return wf line and check everything after it
    in_build = False
    past_return = False
    for line in lines:
        stripped = line.strip()
        if stripped == "def build() -> VibeWorkflow:":
            in_build = True
            continue
        if in_build and stripped.startswith("return wf"):
            past_return = True
            continue
        if past_return:
            # After return wf, lines should be empty or start with 4+ spaces
            # (internal to the build function) or be completely blank
            if stripped and not line.startswith("    ") and not stripped.startswith("#"):
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
                        message=(
                            f"Generated template has un-indented tail line: {stripped!r}. "
                            f"Lines after return wf should be blank or properly indented."
                        ),
                        severity="warning",
                        detail={"unindented_line": stripped},
                    )
                )
                break  # One diagnostic is enough


def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    return all(part.isdigit() for part in str(nid).split(":"))


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _safe_var(class_type: str) -> str:
    # v2.6.4 Fix 6: UUID class types (ComfyUI subgraphs) get a short, readable
    # variable name based on the first 8 chars of the UUID rather than the
    # full 36-char hyphen-replaced string. So
    # `7b34ab90-36f9-45ba-a665-71d418f0df18` becomes `subgraph_7b34ab90`
    # instead of `n_7b34ab90_36f9_45ba_a665_71d418f0df18`.
    if _UUID_RE.match(class_type):
        short = class_type.split("-", 1)[0].lower()
        return f"subgraph_{short}"
    name = re.sub(r"[^a-zA-Z0-9_]", "_", class_type.lower())
    if not name or name[0].isdigit():
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def _connection_role_name(workflow_nodes: dict[str, Any], edges_out: dict[str, list[tuple[str, str]]]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for src_node_id, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        for to_node, to_input in edges_out.get(src_node_id, []):
            target = workflow_nodes.get(to_node)
            if target is None:
                continue
            if target.class_type == "KSampler" and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
            if target.class_type in ("CFGGuider", "MultimodalGuider") and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
    return roles


def _empty_text_role(workflow_nodes: dict[str, Any]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for nid, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        text_value = node.inputs.get("text", node.widgets.get("text", node.widgets.get("widget_0")))
        if isinstance(text_value, str) and text_value.strip() == "":
            roles.setdefault(nid, "negative")
    return roles


def _id_sort_key(nid: str) -> tuple[Any, ...]:
    parts = str(nid).split(":")
    if all(part.isdigit() for part in parts):
        return tuple(int(part) for part in parts)
    return (1 << 31, str(nid))


def _topological_node_order(nodes: dict[str, Any], edges_in: dict[str, list[Any]]) -> list[str]:
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for nid, node in nodes.items():
        for edge in edges_in.get(nid, []):
            if edge.from_node in nodes:
                deps[nid].add(edge.from_node)
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if _is_link(value):
                src = str(value[0])
                if src in nodes:
                    deps[nid].add(src)

    pending = set(nodes.keys())
    out: list[str] = []
    while pending:
        ready = sorted((nid for nid in pending if not (deps[nid] - set(out))), key=_id_sort_key)
        if not ready:
            out.extend(sorted(pending, key=_id_sort_key))
            break
        for nid in ready:
            out.append(nid)
            pending.discard(nid)
    return out


def _format_value(value: Any) -> str:
    # Normalize Windows-style backslash separators to forward slashes in model
    # file paths (e.g. 'LTXVideo\\v2\\file.safetensors' → 'LTXVideo/v2/file.safetensors').
    # ComfyUI model loaders accept either separator.
    if isinstance(value, str) and "\\" in value:
        if value.endswith(_MODEL_FILE_SUFFIXES) or any(
            f"\\{ext[1:]}" in value for ext in _MODEL_FILE_SUFFIXES
        ):
            value = value.replace("\\", "/")
    return repr(value)


def _is_schema_default(class_type: str, key: str, value: Any, node_metadata: Mapping[str, Any] | dict[str, Any]) -> bool:
    keep = node_metadata.get("keep_defaults") or node_metadata.get("keep_kwargs") or ()
    if key in set(str(item) for item in keep):
        return False
    defaults = dict(_CURATED_SCHEMA_DEFAULTS.get(class_type, {}))
    try:
        defaults.update(class_defaults(class_type))
    except Exception:
        pass
    return key in defaults and value == defaults[key]


def _compute_variable_names(workflow_nodes: dict[str, Any], edges: list[Any]) -> dict[str, str]:
    edges_out: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        edges_out.setdefault(edge.from_node, []).append((edge.to_node, edge.to_input))

    role_conn = _connection_role_name(workflow_nodes, edges_out)
    role_empty = _empty_text_role(workflow_nodes)
    sorted_ids = sorted(workflow_nodes.keys(), key=_id_sort_key)

    used: dict[str, int] = {}
    var_names: dict[str, str] = {}
    for nid in sorted_ids:
        node = workflow_nodes[nid]
        base = role_conn.get(nid) or role_empty.get(nid) or _safe_var(node.class_type)
        used[base] = used.get(base, 0) + 1
        var_names[nid] = base if used[base] == 1 else f"{base}_{used[base]}"
    return var_names


def _compute_output_variable_names(
    workflow_nodes: dict[str, Any],
    var_names: dict[str, str],
    edges: list[Any],
) -> dict[str, dict[int, str]]:
    unpackable: dict[str, list[str]] = {}
    for nid, node in sorted(workflow_nodes.items(), key=lambda item: _id_sort_key(item[0])):
        if _wrapper_module_for_class(str(node.class_type)) is None:
            continue
        names = _schema_output_names_for_unpack(node)
        if len(names) <= 1:
            continue
        if _has_out_of_range_edge(str(nid), len(names), edges):
            continue
        unpackable[str(nid)] = names

    used = {
        var
        for nid, var in var_names.items()
        if str(nid) not in unpackable
    }
    output_vars: dict[str, dict[int, str]] = {}
    for nid, names in unpackable.items():
        node = workflow_nodes[nid]
        suffix = _class_collision_suffix(str(node.class_type))
        shadow_prefix = _shadowing_output_prefix(str(node.class_type))
        slot_vars: dict[int, str] = {}
        for index, name in enumerate(names):
            base = _safe_output_var_name(str(name), shadow_prefix)
            candidate = base
            if candidate in used:
                ordinal = 2
                while f"{base}_{ordinal}" in used:
                    ordinal += 1
                candidate = f"{base}_{ordinal}"
            used.add(candidate)
            slot_vars[index] = candidate
        output_vars[nid] = slot_vars
    return output_vars


_SHADOWING_OUTPUT_NAMES: frozenset[str] = frozenset(
    {
        "int",
        "float",
        "bool",
        "boolean",
        "str",
        "list",
        "bytes",
        "dict",
        "set",
        "type",
        "id",
        "input",
    }
)


_SHADOWING_OUTPUT_ALIASES: dict[str, str] = {
    "boolean": "bool",
}


def _shadowing_output_prefix(class_type: str) -> str:
    if class_type == "SimpleCalculatorKJ":
        return "calc"
    if class_type in {"SimpleMath", "SimpleMath+"}:
        return "math"
    return _class_collision_suffix(class_type)


def _safe_output_var_name(output_name: str, prefix: str) -> str:
    normalized = str(output_name).lower()
    base = _safe_var(normalized)
    if base in _SHADOWING_OUTPUT_NAMES:
        return f"{prefix}_{_SHADOWING_OUTPUT_ALIASES.get(base, base)}"
    return base


def _schema_output_names_for_unpack(node: Any) -> list[str]:
    metadata_names = _node_output_names(node)
    if metadata_names:
        return metadata_names
    try:
        return [str(name) for name in class_output_names(str(node.class_type)) if str(name)]
    except Exception:
        return []


def _has_out_of_range_edge(node_id: str, output_count: int, edges: list[Any]) -> bool:
    for edge in edges:
        if str(getattr(edge, "from_node", "")) != node_id:
            continue
        try:
            slot = int(getattr(edge, "from_output"))
        except (TypeError, ValueError):
            return True
        if slot < 0 or slot >= output_count:
            return True
    return False


def _class_collision_suffix(class_type: str) -> str:
    parts = re.findall(r"[A-Z]+(?=[A-Z][a-z]|$)|[A-Z]?[a-z]+|\d+", class_type)
    return _safe_var(parts[0] if parts else class_type)


def _live_output_slots_for_function(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    output_var_names: dict[str, dict[int, str]],
    *,
    return_refs: tuple[tuple[str, int], ...] = (),
    tail_lines: list[str] | None = None,
) -> dict[str, set[int]]:
    live: dict[str, set[int]] = {str(nid): set() for nid in output_var_names}

    def mark(from_node: str, from_slot: int) -> None:
        if from_node in live:
            live[from_node].add(from_slot)

    for edges in edges_in.values():
        for edge in edges:
            try:
                mark(str(edge.from_node), int(edge.from_output))
            except (TypeError, ValueError):
                continue
    for node in workflow_nodes.values():
        for value in list(getattr(node, "inputs", {}).values()) + list(getattr(node, "widgets", {}).values()):
            if _is_link(value):
                mark(str(value[0]), int(value[1]))
    for node_id, slot in return_refs:
        mark(str(node_id), int(slot))

    # The ready-template finalize tail may bind output_node to the first
    # unpacked output variable of a terminal output node.
    tail_text = "\n".join(tail_lines or ())
    if "output_node=" in tail_text:
        for node_id, slot_vars in output_var_names.items():
            first_var = _first_output_var(slot_vars)
            if first_var is not None and re.search(rf"\boutput_node\s*=\s*{re.escape(first_var)}\b", tail_text):
                live[node_id].add(min(slot_vars))
    return live


def _edges_in_with_subgraph_external_refs(
    prepared: dict[str, Any],
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> dict[str, list[Any]]:
    subgraphs: dict[str, _SubgraphDef] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return edges_in

    from vibecomfy.workflow import VibeEdge

    out = {str(node_id): list(edges) for node_id, edges in edges_in.items()}
    for node_id, node in workflow_nodes.items():
        subgraph = subgraphs.get(str(getattr(node, "class_type", "")))
        if subgraph is None:
            continue
        for port in subgraph.inputs:
            if port.external_ref is None:
                continue
            source_id, source_slot = port.external_ref
            if str(source_id) not in workflow_nodes:
                continue
            out.setdefault(str(node_id), []).append(
                VibeEdge(str(source_id), str(source_slot), str(node_id), port.name)
            )
    return out


def _assignment_target(
    var: str,
    output_vars: dict[int, str] | None,
    *,
    live_slots: set[int] | None = None,
) -> str | None:
    if not output_vars:
        return var
    ordered = sorted(output_vars)
    if live_slots is None:
        return ", ".join(output_vars[index] for index in ordered)
    if not any(index in live_slots for index in ordered):
        return None
    return ", ".join(output_vars[index] if index in live_slots else "_" for index in ordered)


def _first_output_var(output_vars: dict[int, str] | None) -> str | None:
    if not output_vars:
        return None
    first_slot = min(output_vars)
    return output_vars[first_slot]


def _node_kwargs(
    node: Any,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    *,
    workflow_nodes: dict[str, Any] | None = None,
    output_var_names: dict[str, dict[int, str]] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    constant_map: dict[tuple[str, str], str] | None = None,
    use_ui_widget_aliases: bool = False,
    strip_schema_defaults: bool = False,
    omit_single_output_metadata: bool = False,
    bare_single_output_refs: bool = False,
    emit_reserved_keyword_args: bool = False,
    preserve_fields: set[str] | None = None,
    external_refs: dict[tuple[str, str], str] | None = None,
) -> list[tuple[str, str]]:
    cls = node.class_type
    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
    schema_set = set(schema)

    # Per-node widget alias metadata populated by the schema provider during
    # convert_to_vibe_format.  Prefer this over the static WIDGET_SCHEMA so
    # that schema-source evidence wins - the static table is only a fallback.
    node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
    input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or (
        _ui_widget_aliases(node) if use_ui_widget_aliases else None
    )

    if constant_map is None:
        constant_map = {}
    if preserve_fields is None:
        preserve_fields = set()
    if external_refs is None:
        external_refs = {}

    incoming: dict[str, tuple[str, int]] = {}
    incoming_exprs: dict[str, str] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str, value: Any = None) -> str | None:
        if key.startswith("unused_widget_"):
            return None
        if cls == "Power Lora Loader (rgthree)":
            return _translate_power_lora_loader_widget(key, value)
        if not key.startswith("widget_"):
            return key
        return resolve_widget_key_with_provenance(cls, key, input_aliases=input_aliases).name

    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        elif key not in raw_inputs:
            raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key, value)
        if translated is None:
            continue
        value = _resolve_graph_field_get_string(value, workflow_nodes)
        if translated != key and translated not in raw_inputs and translated not in static_inputs:
            if translated not in incoming and translated not in incoming_exprs:
                static_inputs[translated] = value
            # else: translated name already connected via an edge — drop the shadow widget value
        else:
            static_inputs[key] = value

    if schema:
        ordered_static_keys = [key for key in schema if key in static_inputs]
        ordered_static_keys += sorted(key for key in static_inputs if key not in schema_set)
    else:
        ordered_static_keys = sorted(static_inputs.keys())

    def _is_python_ident(name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)

    def _format_static_value(key: str, value: Any) -> str:
        """Format a static value, substituting constant name if hoisted."""
        nid = getattr(node, "id", None)
        if nid is not None:
            const_name = constant_map.get((str(nid), key))
            if const_name is not None:
                return const_name
        return _format_value(value)

    out: list[tuple[str, str]] = []
    extras: list[tuple[str, str]] = []
    output_names = _node_output_names(node)
    if output_names and not (omit_single_output_metadata and _is_schema_confirmed_single_output(cls, output_names)):
        out.append(("_outputs", _format_value(tuple(output_names))))
    for key in ordered_static_keys:
        if key in incoming or key in incoming_exprs:
            continue
        if key not in preserve_fields and strip_schema_defaults and _is_schema_default(cls, key, static_inputs[key], node_metadata):
            continue
        if not _is_python_ident(key) and not (emit_reserved_keyword_args and key in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((key, _format_static_value(key, static_inputs[key])))
            continue
        if diagnostics is not None and schema and key not in schema_set and emit_reserved_keyword_args:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
                    message=(
                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown kwarg {key!r}; "
                        "typed wrappers accept it through **_extras, so verify the field is intentional."
                    ),
                    severity="warning",
                    node_id=str(getattr(node, "id", "")),
                    class_type=cls,
                    detail={"input": key, "schema_inputs": sorted(schema_set)},
                )
            )
        out.append((key, _format_static_value(key, static_inputs[key])))

    all_incoming_keys = set(incoming) | set(incoming_exprs)
    if schema:
        ordered_incoming = [key for key in schema if key in all_incoming_keys]
        ordered_incoming += sorted(key for key in all_incoming_keys if key not in schema_set)
    else:
        ordered_incoming = sorted(all_incoming_keys)

    for to_input in ordered_incoming:
        if to_input in incoming_exprs:
            expr = incoming_exprs[to_input]
        else:
            from_node, from_slot = incoming[to_input]
            from_node_str = str(from_node)
            expr = _edge_ref_expr(
                workflow_nodes,
                var_names,
                output_var_names or {},
                from_node_str,
                from_slot,
                bare_single_output_refs=bare_single_output_refs,
                diagnostics=diagnostics,
                target_node=node,
                target_input=to_input,
            )
        if not _is_python_ident(to_input) and not (emit_reserved_keyword_args and to_input in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((to_input, expr))
            continue
        if diagnostics is not None and schema and to_input not in schema_set and emit_reserved_keyword_args:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
                    message=(
                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown linked kwarg {to_input!r}; "
                        "typed wrappers accept it through **_extras, so verify the field is intentional."
                    ),
                    severity="warning",
                    node_id=str(getattr(node, "id", "")),
                    class_type=cls,
                    detail={"input": to_input, "schema_inputs": sorted(schema_set), "linked": True},
                )
            )
        out.append((to_input, expr))

    # -- readability diagnostics: positional output detection ------------
    if diagnostics is not None:
        emit_diags = _collect_emission_diagnostics(node, output_names, incoming, var_names)
        diagnostics.extend(emit_diags)

    if extras:
        extras_repr = "{" + ", ".join(f"{key!r}: {value}" for key, value in extras) + "}"
        out.append(("_extras", extras_repr))
    return out


def _translate_power_lora_loader_widget(key: str, value: Any) -> str | None:
    """Map rgthree Power Lora dynamic widget slots to stable kwargs.

    rgthree stores decorative header/separator widgets beside an open-ended
    list of LoRA option dictionaries. The committed object_info snapshot only
    exposes model/clip sockets, so normal widget aliasing cannot name these
    UI-saved values.
    """
    if key.startswith("unused_widget_"):
        return None
    if not key.startswith("widget_"):
        return key
    index = _power_lora_widget_index(key)
    if index is None:
        return key
    if not _is_power_lora_config(value):
        return None
    return f"lora_{max(1, index - 3)}"


def _power_lora_widget_index(key: str) -> int | None:
    if key.startswith("widget_"):
        suffix = key.removeprefix("widget_")
    elif key.startswith("unused_widget_"):
        suffix = key.removeprefix("unused_widget_")
    else:
        return None
    try:
        return int(suffix)
    except ValueError:
        return None


def _is_power_lora_config(value: Any) -> bool:
    return isinstance(value, dict) and {"on", "lora", "strength"}.issubset(value)


def _collect_emission_diagnostics(
    node: Any,
    output_names: list[str],
    incoming: dict[str, tuple[str, int]],
    var_names: dict[str, str],
) -> list[EmissionDiagnostic]:
    """Collect readability diagnostics for a single node during emission.

    This is called from `_node_kwargs` when a diagnostics collector is
    provided.  Currently flags:

    * **avoidable_positional_output** - the node has output names available
      (from schema metadata) but the emitter is using numeric `.out(n)`
      because one or more names are unsafe (blank, duplicate, conflicted).

    * **output_name_ambiguity** - output name is duplicated within the
      same node, forcing a numeric fallback.

    * **schema_backed_widget_alias_not_resolved** - one or more
      `widget_N` keys remain positional because no alias mapping could
      be resolved from schema / widget table evidence.
    """
    diags: list[EmissionDiagnostic] = []
    nid = getattr(node, "id", None)
    ctype = getattr(node, "class_type", None)
    metadata = getattr(node, "metadata", {}) or {}
    node_input_aliases = metadata.get("input_aliases")

    # 1. avoidable_positional_output / output_name_ambiguity
    if output_names:
        safe_names: set[str] = set()
        has_unsafe = False
        has_duplicate = False
        seen: set[str] = set()
        for name in output_names:
            if not name:
                has_unsafe = True
            elif name in seen:
                has_unsafe = True
                has_duplicate = True
            else:
                seen.add(name)
                safe_names.add(name)
        if has_unsafe:
            if has_duplicate:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
                        message=f"Node {nid} ({ctype}) has duplicate output names; falling back to numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
            else:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
                        message=f"Node {nid} ({ctype}) has partial/blank output names; some outputs use numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
    else:
        # No output names at all - check if schema has input_aliases available
        if not node_input_aliases:
            # Check if there are widget_N keys that could be aliased
            widget_keys = [
                k for k in getattr(node, "widgets", {}).keys()
                if k.startswith("widget_")
            ] + [
                k for k in getattr(node, "inputs", {}).keys()
                if k.startswith("widget_")
            ]
            if widget_keys:
                schema_source = metadata.get("schema_source")
                schema_available = schema_source is not None
                if schema_available:
                    diags.append(
                        EmissionDiagnostic(
                            code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                            message=f"Node {nid} ({ctype}) has {len(set(widget_keys))} unresolved widget_N keys despite schema being available.",
                            severity="warning",
                            node_id=str(nid) if nid is not None else None,
                            class_type=ctype,
                            detail={
                                "widget_keys": list(set(widget_keys)),
                                "schema_source": schema_source,
                            },
                        )
                    )

    # 3. schema_backed_widget_alias_not_resolved - when widget_N keys remain
    #    positional even though input_aliases could potentially cover them, or
    #    when the fallback to static WIDGET_SCHEMA was used.
    if node_input_aliases:
        # We have input_aliases - check if any widget_N index falls outside
        # the aliases list, forcing a fallback.
        widget_indices: list[int] = []
        for k in list(getattr(node, "widgets", {}).keys()) + list(getattr(node, "inputs", {}).keys()):
            if k.startswith("widget_"):
                try:
                    widget_indices.append(int(k.split("_", 1)[1]))
                except ValueError:
                    pass
        if widget_indices:
            max_idx = max(widget_indices)
            if max_idx >= len(node_input_aliases):
                unresolved = [
                    f"widget_{i}" for i in widget_indices
                    if i >= len(node_input_aliases)
                ]
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                        message=(
                            f"Node {nid} ({ctype}) has {len(unresolved)} widget_N key(s) "
                            f"({', '.join(unresolved)}) outside input_aliases range "
                            f"(len={len(node_input_aliases)}); keeping positional."
                        ),
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={
                            "unresolved_widgets": unresolved,
                            "input_aliases_length": len(node_input_aliases),
                        },
                    )
                )

    return diags


def _node_output_names(node: Any) -> list[str]:
    """Return output names for `_outputs` emission, preserving partial evidence.

    Unlike the old all-truthy gate, this always returns the full list from
    metadata so that `_outputs` is emitted even when some names are blank.
    The per-slot safety decision for `.out('name')` is made separately by
    `_safe_output_name` during incoming edge formatting.
    """
    output_names = getattr(node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return []
    result: list[str] = []
    for name in output_names:
        if isinstance(name, str) and name:
            result.append(name)
        else:
            result.append("")
    return result


def _safe_output_name(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> str | None:
    """Return the safe output name for a slot, or `None` if numeric fallback is needed.

    A name is *safe* for `.out('name')` when all of these hold:

    * *slot in range:* `from_slot` is a valid index into the source node's
      `output_names` metadata list.
    * *name non-empty:* the name at that index is a non-blank string.
    * *name unique:* the name appears exactly once in the source node's
      `output_names` list (no duplicates).
    * *name not conflicted:* the source node's metadata does not list the name
      in a `conflicted_outputs` key.
    """
    if workflow_nodes is None:
        return None
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return None
    output_names = getattr(src_node, "metadata", {}).get("output_names")
    if not isinstance(output_names, (list, tuple)):
        return None
    if from_slot < 0 or from_slot >= len(output_names):
        return None
    name = output_names[from_slot]
    if not isinstance(name, str) or not name:
        return None
    # Duplicate check: the name must appear exactly once.
    if list(output_names).count(name) > 1:
        return None
    # Conflicted check: the name must not be in the conflicted_outputs list.
    conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
    if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
        return None
    return name


def _output_fallback_diagnostic(
    diagnostics: list[EmissionDiagnostic],
    workflow_nodes: dict[str, Any],
    from_node: str,
    from_slot: int,
    *,
    target_node: Any,
    target_input: str,
) -> None:
    """Record a diagnostic explaining why `.out(n)` was used instead of `.out('name')`.

    Only fires when the source node *has* output_names metadata - otherwise
    numeric fallback is expected and not an avoidable concern.
    """
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return

    output_names = getattr(src_node, "metadata", {}).get("output_names")
    # If the source node has no output_names metadata at all, numeric fallback
    # is the only option - no diagnostic warranted.
    if not isinstance(output_names, (list, tuple)):
        return

    src_ctype = getattr(src_node, "class_type", None)
    tgt_nid = getattr(target_node, "id", None)
    tgt_ctype = getattr(target_node, "class_type", None)

    reason_parts: list[str] = []
    if from_slot < 0 or from_slot >= len(output_names):
        reason_parts.append(
            f"slot {from_slot} out of range (source has {len(output_names)} output(s))"
        )
    else:
        name = output_names[from_slot]
        if not isinstance(name, str) or not name:
            reason_parts.append(f"output_names[{from_slot}] is blank")
        elif list(output_names).count(name) > 1:
            reason_parts.append(
                f"output_names[{from_slot}]={name!r} is duplicated in source output_names"
            )
        else:
            conflicted = getattr(src_node, "metadata", {}).get("conflicted_outputs")
            if isinstance(conflicted, (list, tuple, set, frozenset)) and name in conflicted:
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is marked conflicted"
                )
            else:
                # Should not reach here - _safe_output_name would have succeeded.
                # Log it anyway as a safety net.
                reason_parts.append(
                    f"output_names[{from_slot}]={name!r} is not safe for named emission"
                )

    reason = "; ".join(reason_parts)
    diagnostics.append(
        EmissionDiagnostic(
            code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
            message=(
                f"Edge from {from_node} ({src_ctype}).out({from_slot}) to "
                f"{tgt_nid} ({tgt_ctype}).{target_input} uses numeric .out({from_slot}) "
                f"because: {reason}"
            ),
            severity="warning",
            node_id=str(tgt_nid) if tgt_nid is not None else None,
            class_type=tgt_ctype,
            detail={
                "from_node": from_node,
                "from_slot": from_slot,
                "target_input": target_input,
                "reason": reason,
                "output_names": list(output_names),
            },
        )
    )


def _format_metadata_dict(name: str, value: dict[str, Any]) -> str:
    formatted = pprint.pformat(value, width=110, sort_dicts=False)
    return f"{name} = {formatted}"


def _is_schema_confirmed_single_output(class_type: str, output_names: list[str] | tuple[str, ...]) -> bool:
    try:
        return class_output_count(class_type) == 1 and not class_has_list_output(class_type)
    except Exception:
        return len(output_names) == 1


def _is_single_output_ref(
    workflow_nodes: dict[str, Any] | None,
    from_node: str,
    from_slot: int,
) -> bool:
    if from_slot != 0 or workflow_nodes is None:
        return False
    src_node = workflow_nodes.get(from_node)
    if src_node is None:
        return False
    output_names = _node_output_names(src_node)
    if _UUID_RE.match(str(src_node.class_type)) and len(output_names) == 1:
        return True
    return _is_schema_confirmed_single_output(str(src_node.class_type), output_names)


def _has_ltx_lowvram_tail(category_id: str) -> bool:
    return category_id.startswith("video/ltx2_3_t2v") or category_id.startswith("video/ltx2_3_i2v")


def _apply_overrides(nodes: dict[str, Any], edges_in: dict[str, list[Any]], patches: list[dict[str, Any]]) -> None:
    for patch in patches:
        match = patch.get("match", {})
        target_ids: list[str] = []
        if "node_id" in match:
            target_ids = [str(match["node_id"])]
        elif "class_type" in match:
            class_target = match["class_type"]
            ordinal = match.get("node_index")
            matches = [nid for nid, node in nodes.items() if node.class_type == class_target]
            if ordinal is not None and 0 <= ordinal < len(matches):
                target_ids = [matches[ordinal]]
            else:
                target_ids = matches

        for tid in target_ids:
            node = nodes.get(tid)
            if node is None:
                continue
            for old, new in (patch.get("rename_inputs") or {}).items():
                if old in node.widgets:
                    node.widgets[new] = node.widgets.pop(old)
                if old in node.inputs:
                    node.inputs[new] = node.inputs.pop(old)
            for key, value in (patch.get("set_inputs") or {}).items():
                if key in node.widgets:
                    node.widgets[key] = value
                else:
                    node.inputs[key] = value
            for key in patch.get("remove_inputs") or []:
                node.widgets.pop(key, None)
                node.inputs.pop(key, None)


_NODE_HELPER_SOURCE = '''
def _node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: dict | None = None,
    _outputs: tuple[str, ...] | None = None,
    _uid: str | None = None,
    **kwargs,
):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _uid:
        builder.node.uid = _uid
    if _outputs is not None:
        builder.node.metadata["output_names"] = list(_outputs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
'''


__all__ = [
    "emit_ready_template_python",
    "emit_scratchpad_python",
    "EmissionDiagnostic",
    "EmissionSeverity",
    "READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT",
    "READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY",
    "READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED",
    "READABILITY_WARNING_HIDDEN_MODEL_FILENAME",
    "READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE",
    "READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL",
    "READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED",
    "READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG",
    "READABILITY_WARNING_CODES",
]
