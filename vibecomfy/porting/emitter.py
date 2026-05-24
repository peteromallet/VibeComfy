from __future__ import annotations

import ast
import hashlib
import importlib
import json
import keyword
import pprint
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping

from vibecomfy.errors import ConversionParityError, SchemaValidationError
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy.porting.widget_aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.object_info import class_defaults, class_has_list_output, class_output_count
from vibecomfy.porting.object_info import output_names as class_output_names
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

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
READABILITY_WARNING_OPAQUE_COMPONENT_RAW_CALL = "opaque_component_raw_call"

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
        READABILITY_WARNING_OPAQUE_COMPONENT_RAW_CALL,
    }
)

EmissionSeverity = Literal["error", "warning", "info"]

# Regex for opaque UUID-class components (Family I policy: materialize-as-inline,
# fallback to raw_call + strict_ready exception if no subgraph definition).
_OPAQUE_COMPONENT_CLASS_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


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

UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset({"Note", "MarkdownNote"})
FALLBACK_CLASS_TYPES: frozenset[str] = frozenset({
    "SetNode",
    "GetNode",
    "Note",
    "MarkdownNote",
    "Reroute",
    "PrimitiveNode",
})
RESERVED_WRAPPER_INPUT_NAMES: frozenset[str] = frozenset({"class", "from", "type"})

_WRAPPER_MODULES: tuple[str, ...] = (
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


def _wrapper_class_to_module() -> dict[str, str]:
    global _WRAPPER_CLASS_TO_MODULE
    if _WRAPPER_CLASS_TO_MODULE is not None:
        return _WRAPPER_CLASS_TO_MODULE
    mapping: dict[str, str] = {}
    for module_name in _WRAPPER_MODULES:
        try:
            module = importlib.import_module(f"vibecomfy.nodes._generated.{module_name}")
        except ImportError:
            continue
        exported = getattr(module, "__all__", ())
        for name in exported:
            if isinstance(name, str):
                mapping.setdefault(name, module_name)
    _WRAPPER_CLASS_TO_MODULE = mapping
    return mapping


def _wrapper_module_for_class(class_type: str) -> str | None:
    if class_type in FALLBACK_CLASS_TYPES or class_type in UI_ONLY_CLASS_TYPES:
        return None
    return _wrapper_class_to_module().get(class_type)


def _wrapper_imports_for_nodes(workflow_nodes: dict[str, Any]) -> dict[str, list[str]]:
    imports: dict[str, set[str]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        module_name = _wrapper_module_for_class(class_type)
        if module_name is not None:
            imports.setdefault(module_name, set()).add(class_type)
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

_SUPPRESSED_SECTION_COMMENTS: frozenset[str] = frozenset({"Loaders", "Sampling"})

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
    """Return the unsuffixed constant name for a hoisted field."""
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

    # Value dedup: same category + same value string -> same constant name
    value_to_name: dict[tuple[str, str, str], str] = {}  # (base, category, str(value)) -> name

    for nid, field, value, category in candidates:
        count_key = (category, str(value))
        count = value_counts[count_key]

        # Always hoist categories that represent public defaults
        always_hoist = category in ("model", "prompt", "negative_prompt", "seed",
                                    "output_prefix", "size", "fps", "frames", "guide")
        should_hoist = always_hoist or count >= 2

        if not should_hoist:
            continue

        base = _constant_name_base_for_category(category, field)
        value_key = (base, category, str(value))
        if value_key in value_to_name:
            name = value_to_name[value_key]
        else:
            category_counters[base] = category_counters.get(base, 0) + 1
            cnt = category_counters[base]
            name = base if cnt == 1 else f"{base}_{cnt}"
            value_to_name[value_key] = name
            constant_defs[name] = (value, category)

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
            # Only track string values that are not already categorized
            if not isinstance(value, str):
                continue
            cat = _classify_value_category(translated, value, cls)
            if cat is not None:
                continue  # already handled above
            all_values[(translated, value)] += 1

    for (field, value), count in all_values.items():
        if count >= 2:
            # This is a repeated preset
            sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", field.upper())
            if not sanitized or sanitized[0].isdigit():
                sanitized = f"P_{sanitized}"
            value_key = (sanitized, "preset", str(value))
            if value_key in value_to_name:
                continue  # already named
            # Deterministic name: field name ALL_CAPS_ style
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
        default_expr = constant_map.get((str(binding.node_id), binding.field))
        if default_expr is None:
            default_expr = _format_value(field_values[binding.field])
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


def _build_public_lookup(public_inputs: list[_PublicInputSpec]) -> dict[tuple[str, str], list[_PublicInputSpec]]:
    """Build lookup from (node_id, field) → list of _PublicInputSpec.

    Multiple specs can target the same (node_id, field) when aliases are
    registered or when inference picks up the same binding.
    """
    import ast as _ast

    lookup: dict[tuple[str, str], list[_PublicInputSpec]] = {}
    for spec in public_inputs:
        # metadata_node_ref is always repr(str(node_id)) e.g. "'42'"
        try:
            nid = _ast.literal_eval(spec.metadata_node_ref)
        except Exception:
            continue
        lookup.setdefault((str(nid), spec.field), []).append(spec)
    return lookup


def _format_public_call(specs: list[_PublicInputSpec], default_expr: str) -> str:
    """Format a public(...) call wrapping a default value expression.

    When multiple specs map to the same (node_id, field), the first spec's
    name is primary and all other names become aliases.  Exact duplicates
    (same name, default) are collapsed with an inline comment.
    """
    if not specs:
        return default_expr

    # Deduplicate by (name, default_expr)
    seen: dict[tuple[str, str], _PublicInputSpec] = {}
    for spec in specs:
        key = (spec.name, spec.default_expr)
        if key not in seen:
            seen[key] = spec

    primary_spec = specs[0]  # first registered
    primary_name = primary_spec.name

    # Collect all alias names (other spec names + their aliases)
    all_aliases: list[str] = []
    for spec in specs:
        if spec.name != primary_name:
            all_aliases.append(spec.name)
        all_aliases.extend(spec.aliases)

    # Deduplicate aliases preserving order
    deduped_aliases: list[str] = []
    seen_aliases: set[str] = {primary_name}
    for alias in all_aliases:
        if alias not in seen_aliases:
            seen_aliases.add(alias)
            deduped_aliases.append(alias)

    args = [f"default={default_expr}"]
    if primary_spec.type is not None:
        args.append(f"type={primary_spec.type!r}")
    if primary_spec.required:
        args.append("required=True")
    if deduped_aliases:
        args.append(f"aliases={tuple(deduped_aliases)!r}")
    if primary_spec.media_semantics is not None:
        args.append(f"media_semantics={primary_spec.media_semantics!r}")

    if len(seen) < len(specs):
        # Collapsed duplicates — add inline comment
        return f"public({primary_name!r}, {', '.join(args)})  # {len(specs) - len(seen)} duplicate(s) collapsed"
    return f"public({primary_name!r}, {', '.join(args)})"


def _check_unemitted_public_specs(
    public_lookup: dict[tuple[str, str], list],
    emitted_keys: set[tuple[str, str]],
    diagnostics: list,
) -> None:
    """Add diagnostics for public-input specs whose (node_id, field) was never emitted.

    This catches the silent-drop risk: a public input registered against a field
    that ends up connected via edge (so _node_kwargs never sees it as static).
    """
    for lookup_key in sorted(public_lookup):
        if lookup_key not in emitted_keys:
            nid, field = lookup_key
            spec_names = ", ".join(s.name for s in public_lookup[lookup_key])
            diagnostics.append(
                EmissionDiagnostic(
                    code="public_input_not_emitted",
                    message=(
                        f"Public input(s) [{spec_names}] targeting node {nid!r} field {field!r} "
                        f"were never emitted as literal kwargs. The field may be connected via "
                        f"an edge (Handle ref) instead of a static value."
                    ),
                    severity="warning",
                    node_id=nid,
                    detail={"field": field, "public_names": [s.name for s in public_lookup[lookup_key]]},
                )
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
        "_has_output_spec_for_emit",
    }
    extras = {
        str(key): value
        for key, value in metadata.items()
        if key not in derived_keys and value is not None
    }
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping) and not _is_derivable_provenance(provenance):
        extras["provenance"] = dict(provenance)
    return extras


def _is_derivable_provenance(provenance: Mapping[str, Any]) -> bool:
    """Return true when ReadyMetadata.build can recreate the provenance."""

    return set(provenance).issubset({"source_workflow", "source_role"})


def _requirements_expr_for_emit(requirements: Mapping[str, Any], *, has_models: bool) -> str | None:
    retained: dict[str, Any] = {}
    for key, value in dict(requirements).items():
        if key == "models" and has_models:
            continue
        if value:
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
    custom_node_packs: Mapping[str, Any] | None = None,
) -> list[str]:
    template_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    capability = str(metadata.get("capability") or "unknown")
    output_prefix = str(metadata.get("output_prefix") or template_id)
    lines = [
        "READY_METADATA = ReadyMetadata.build(",
        f"    capability={capability!r},",
    ]
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

    raw_workflow = raw_workflow or _raw_workflow_from_metadata(metadata)
    subgraph_definitions = _subgraph_definitions_from_raw(raw_workflow, source_path=_source_workflow_path(metadata))
    prepared = _prepare_workflow_for_emit(workflow, apply_overrides=apply_overrides)
    prepared["subgraph_definitions"] = subgraph_definitions
    _apply_subgraph_names_to_prepared(prepared)
    has_ltx_tail = _has_ltx_lowvram_tail(template_id)

    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
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
    public_lookup = _build_public_lookup(public_inputs) if public_inputs else {}

    out_lines: list[str] = []
    out_lines.append(GENERATED_HEADER.rstrip("\n"))
    out_lines.append('"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append(
        "from vibecomfy.templates import InputSpec, ModelAsset, OutputSpec, ReadyMetadata, finalize, new_workflow, node as raw_call, public"
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
    output_spec_lines = _format_output_spec_block(workflow_nodes, edges_in)
    has_output_spec = bool(output_spec_lines)
    metadata["_has_output_spec_for_emit"] = has_output_spec
    if output_spec_lines:
        out_lines.append("")
        out_lines.extend(output_spec_lines)
        out_lines.append("")
    out_lines.extend(
        _format_ready_metadata_build(
            metadata,
            requirements,
            has_models=bool(model_assets),
            custom_node_packs=custom_node_packs,
        )
    )
    out_lines.append("")
    subgraph_lines = _emit_subgraph_functions(prepared, diagnostics=diagnostics, constant_map=constant_map)
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
            public_lookup=public_lookup,
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
        raise ConversionParityError(
            f"Generated ready-template code failed syntax check: {exc}",
            next_action="Check the generated code for syntax errors; the AST parse failure details are in the exception message.",
        ) from exc
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
    raw_workflow: dict[str, Any] | None = None,
) -> str:
    workflow_id = workflow_id or getattr(workflow, "id", "scratchpad")
    prepared = _prepare_workflow_for_emit(workflow, apply_overrides=apply_overrides)

    # Subgraph definitions — empty when raw_workflow is None (documented limitation)
    subgraph_definitions = _subgraph_definitions_from_raw(raw_workflow, source_path=source_path)
    prepared["subgraph_definitions"] = subgraph_definitions
    _apply_subgraph_names_to_prepared(prepared)

    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    var_names = prepared["var_names"]

    # Hoist constants and build section groups (shared typed-wrapper path)
    constant_lines, constant_map = _hoist_constants(workflow_nodes, edges_in, var_names)
    constant_lines, constant_map = _drop_output_prefix_constants(constant_lines, constant_map)
    section_groups = _build_section_groups(workflow_nodes, edges_in)
    wrapper_imports = _wrapper_imports_for_nodes(_all_nodes_for_imports(workflow_nodes, subgraph_definitions))

    source_path_expr = repr(source_path) if source_path is not None else "__file__"

    out_lines: list[str] = []
    out_lines.append("# vibecomfy: generated scratchpad")
    out_lines.append('"""Auto-generated VibeComfy scratchpad."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    templates_imports = ["new_workflow", "node as raw_call", "ref"]
    if registered_inputs:
        templates_imports.insert(0, "bind_input")
    out_lines.append(f"from vibecomfy.templates import {', '.join(templates_imports)}")
    for module_name, names in sorted(wrapper_imports.items()):
        out_lines.append(f"from vibecomfy.nodes.{module_name} import {', '.join(names)}")
    out_lines.append("")

    # -- constants section ----------------------------------------------------
    if constant_lines:
        out_lines.append("")
        out_lines.extend(constant_lines)
        out_lines.append("")

    # Build inline metadata dict for workflow_id_expr (provenance embedded, not separate kwarg)
    _metadata_dict: dict[str, Any] = {"workflow_template": workflow_id}
    if provenance:
        _metadata_dict["provenance"] = provenance
    workflow_id_expr = _format_value(_metadata_dict)

    # Subgraph functions
    subgraph_lines = _emit_subgraph_functions(prepared, diagnostics=diagnostics, constant_map=constant_map)
    if subgraph_lines:
        out_lines.extend(subgraph_lines)
        out_lines.append("")

    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr=workflow_id_expr,
            source_path_expr=source_path_expr,
            source_type="scratchpad",
            source_provenance=None,
            registered_inputs=registered_inputs,
            public_inputs=None,
            tail_lines=["    return wf.finalize_metadata()"],
            diagnostics=diagnostics,
            use_shared_helpers=True,
            constant_map=constant_map,
            section_groups=section_groups,
        )
    )

    combined = "\n".join(out_lines) + "\n"
    combined = _strip_unused_template_imports(combined)

    # Validate syntax with ast.parse
    try:
        ast.parse(combined)
    except SyntaxError as exc:
        raise ConversionParityError(
            f"Generated scratchpad code failed syntax check: {exc}",
            next_action="Check the generated code for syntax errors; the AST parse failure details are in the exception message.",
        ) from exc

    return combined


def _prepare_workflow_for_emit(workflow: Any, *, apply_overrides: dict[str, Any] | None) -> dict[str, Any]:
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
            nodes.setdefault(f"{subgraph.id}:{nid}", node)
    return nodes


# Slugs that would shadow build() or other top-level names in the emitted template.
_SUBGRAPH_RESERVED_SLUGS: frozenset[str] = frozenset({"build"})


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
    if slug in _SUBGRAPH_RESERVED_SLUGS:
        slug = f"_subgraph_{slug}"
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
    inputs = tuple(input_ports)

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
    defaults = _subgraph_default_args(raw, inputs)

    for node_id, node in api.items():
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
        nodes[str(node_id)] = _Node(str(node_id), str(node.get("class_type", "Unknown")), inputs=static_inputs, widgets=widgets, metadata=metadata)

    for node_id, node in api.items():
        if not isinstance(node, Mapping):
            continue
        for key, value in dict(node.get("inputs", {})).items():
            if not _is_any_link(value):
                continue
            from_node, from_slot = str(value[0]), int(value[1])
            if from_node == "-10":
                if 0 <= from_slot < len(inputs):
                    input_refs[(str(node_id), str(key))] = inputs[from_slot].name
            else:
                edge = _Edge(from_node, str(from_slot), str(node_id), str(key))
                edges_in.setdefault(str(node_id), []).append(edge)

    return_refs: list[tuple[str, int]] = []
    # Family D fix: normalize raw links to Mapping form regardless of whether they
    # are stored as dicts or as ComfyUI array format [id, origin_id, origin_slot, target_id, target_slot, type].
    def _normalize_raw_link(link: Any) -> "Mapping[str, Any] | None":
        if isinstance(link, Mapping):
            return link
        if isinstance(link, (list, tuple)) and len(link) >= 5:
            return {"id": link[0], "origin_id": link[1], "origin_slot": link[2], "target_id": link[3], "target_slot": link[4]}
        return None

    links = [m for link in (raw.get("links") or ()) for m in [_normalize_raw_link(link)] if m is not None]
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
    values = node.get("widgets_values")
    if isinstance(values, Mapping):
        return values.get(widget_name)
    if not isinstance(values, list):
        return None
    widget_names = [
        str(item.get("widget", {}).get("name") or item.get("name") or "")
        for item in input_items
        if isinstance(item.get("widget"), Mapping)
    ]
    try:
        return values[widget_names.index(widget_name)]
    except (ValueError, IndexError):
        return None


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
            var_names[str(node_id)] = _unique_var(subgraph.slug, used)
        else:
            result_base = _subgraph_result_base(subgraph.slug)
            # Avoid Python UnboundLocalError: if result var would have the same name as
            # the subgraph function (slug), assignment `x = x(...)` in build() marks x as
            # local before the RHS call, crashing at runtime.
            if result_base == subgraph.slug:
                result_base = f"{subgraph.slug}_result"
            var_names[str(node_id)] = _unique_var(result_base, used)


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
            value = fields.get("text")
            if isinstance(value, str):
                if "negative" in title:
                    negative_candidate = negative_candidate or (str(node_id), "text")
                elif value.strip():
                    prompt_candidate = prompt_candidate or (str(node_id), "text")
        if class_type in {"PrimitiveStringMultiline", "PrimitiveString"} and isinstance(fields.get("value"), str):
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
    public_lookup: dict[tuple[str, str], list[_PublicInputSpec]] | None = None,
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
) -> list[str]:
    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    var_names = prepared["var_names"]
    output_var_names = prepared.get("output_var_names", {}) if use_shared_helpers else {}

    if constant_map is None:
        constant_map = {}
    if section_groups is None:
        section_groups = {}
    if public_lookup is None:
        public_lookup = {}
    # Build preserve-fields from public_lookup (which uses (node_id, field) keys)
    public_preserve_fields: dict[str, set[str]] = {}
    for (nid, field) in public_lookup:
        public_preserve_fields.setdefault(nid, set()).add(field)

    # Track which public-input (node_id, field) keys get wrapped by _node_kwargs
    emitted_public_keys: set[tuple[str, str]] = set()

    # Build a set of node IDs covered by section groups for fast lookup
    section_nids: set[str] = set()
    for nids in section_groups.values():
        section_nids.update(nids)

    # Pre-emission resolver: remove SetNode/GetNode/Reroute helpers and rewrite their consumer
    # edges before topo_order is built so resolved helper nodes never reach the topo loop.
    # FALLBACK_CLASS_TYPES stays intact as a raw_call safety net for unresolved instances.
    if use_shared_helpers:
        _resolve_helper_nodes_for_emission(workflow_nodes, edges_in)

    # Build ordered list of (section_name, nid) for topological-sorted nodes
    topo_order = _topological_node_order(workflow_nodes, edges_in)
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
        if source_type != "ready_template":
            out_lines.append(f"    with new_workflow({workflow_id_expr}, source_path={source_path_expr}, source_type={source_type!r}) as wf:")
        else:
            out_lines.append(f"    with new_workflow({workflow_id_expr}, source_path={source_path_expr}) as wf:")
        body_indent = "        "
        continuation_indent = "            "
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
        if (
            section is not None
            and section not in _SUPPRESSED_SECTION_COMMENTS
            and section not in emitted_sections
        ):
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
            public_lookup=public_lookup,
            emitted_public_keys=emitted_public_keys,
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
                out_lines.extend(
                    _emit_subgraph_call_statement(
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
                )
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

            if use_wrapper:
                all_args = []
                all_args.extend((_wrapper_kwarg_name(key), expr) for key, expr in ready_kwargs)
                # v2.6.4 Fix 3: drop _outputs= for schema-known typed wrappers.
                # The wrapper class already knows its output names from the
                # generated schema (vibecomfy/nodes/_generated/<pack>.py). Only
                # raw_call (UUID fallback, no schema) needs explicit _outputs.
                if extras_expr is not None:
                    all_args.append(("**", extras_expr))
                call_name = str(node.class_type)
                assignment_target = _assignment_target(var, output_var_names.get(str(nid)))
            else:
                all_args = []
                if outputs_expr is not None:
                    all_args.append(("_outputs", outputs_expr))
                all_args.extend(ready_kwargs)
                if extras_expr is not None:
                    all_args.append(("_extras", extras_expr))
                call_name = "node"
                assignment_target = var

            # Multi-line formatting: use multi-line when >3 kwargs or any line would exceed ~88 chars
            kwarg_lines = [f"**{expr}" if key == "**" else f"{key}={expr}" for key, expr in all_args]
            if use_wrapper:
                call_args = ", ".join(kwarg_lines)
                single_line = f"{body_indent}{assignment_target} = {call_name}({call_args})"
            else:
                # v2.6.4 Fix 5: raw_call reads wf from ContextVar (set by
                # new_workflow context manager); no need to pass wf positional.
                call_args = ", ".join([repr(node.class_type), repr(nid), *kwarg_lines])
                single_line = f"{body_indent}{assignment_target} = raw_call({call_args})"

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

            # -- readability diagnostic: opaque component raw_call ----------
            # Family I policy (SD1): opaque UUID-class components are
            # materialized as inline Python functions when a subgraph
            # definition is available; otherwise they fall back to raw_call
            # and must be documented as strict-ready exceptions.
            if (
                diagnostics is not None
                and not use_wrapper
                and _OPAQUE_COMPONENT_CLASS_RE.match(str(node.class_type))
            ):
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_OPAQUE_COMPONENT_RAW_CALL,
                        message=(
                            f"Node {nid} with opaque UUID component class "
                            f"{node.class_type!r} emitted as raw_call; no "
                            f"subgraph definition or typed wrapper available. "
                            f"This component cannot be materialized as an "
                            f"inline Python function."
                        ),
                        severity="warning",
                        node_id=str(nid),
                        class_type=node.class_type,
                        detail={
                            "category": "opaque_component",
                            "resolution": "raw_call_fallback",
                        },
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
                    lines = [f"{body_indent}{assignment_target} = {call_name}("]
                else:
                    # v2.6.4 Fix 5: drop wf positional from raw_call (ContextVar).
                    lines = [f"{body_indent}{assignment_target} = raw_call({node.class_type!r}, {nid!r},"]
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
            head = f"    {var} = _node(wf, {node.class_type!r}, {nid!r}"
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
            # -- registered_inputs for scratchpad (SD2: gated behind public_inputs is None) --
            # Must emit BEFORE tail_lines so bind_input calls precede the return statement.
            if registered_inputs and public_inputs is None:
                out_lines.append("")
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
                    suffix = ", " + ", ".join(descriptor_kwargs) if descriptor_kwargs else ""
                    out_lines.append(f"{body_indent}bind_input(wf, {input_name!r}, {_node_binding_expr(old_id, var_names, output_var_names)}, {resolved_field!r}{suffix})")
            # -- _FILENAME_KWARGS public inputs for ready templates --
            # Model-name fields (unet_name, vae_name, etc.) cannot use public()
            # wrapping because coerce_node_kwargs rejects PublicSentinel on those
            # fields.  Emit explicit bind_input calls instead.
            if public_inputs:
                import ast as _ast

                from vibecomfy.templates import _FILENAME_KWARGS

                filename_specs: list[tuple[str, str, str, str]] = []  # (name, node_id, field, default_expr)
                seen_fk: set[tuple[str, str, str]] = set()  # (name, node_id, field)
                for spec in public_inputs:
                    if spec.field not in _FILENAME_KWARGS:
                        continue
                    try:
                        nid = str(_ast.literal_eval(spec.metadata_node_ref))
                    except Exception:
                        continue
                    key = (spec.name, nid, spec.field)
                    if key in seen_fk:
                        continue
                    seen_fk.add(key)
                    filename_specs.append((spec.name, nid, spec.field, spec.default_expr))
                if filename_specs:
                    out_lines.append("")
                    for name, nid, field, default_expr in filename_specs:
                        # Family A fix: use the variable binding expr so the emitted code
                        # references the actual built node (e.g. unetloader.node.id), not the
                        # raw source JSON id which may not exist in the built workflow.
                        node_id_expr = _node_binding_expr(nid, var_names, output_var_names)
                        out_lines.append(
                            f"{body_indent}wf.register_input({name!r}, {node_id_expr}, {field!r}, {default_expr})"
                        )
            tail_lines = _with_id_map_tail_line(tail_lines, var_names)
            out_lines.extend("    " + line if line else line for line in tail_lines)
        # -- diagnostic: public input specs never emitted as literal kwargs -----
        if diagnostics is not None and public_lookup:
            _check_unemitted_public_specs(public_lookup, emitted_public_keys, diagnostics)
        return out_lines
    out_lines.append("")
    out_lines.extend(tail_lines)
    # -- diagnostic: public input specs never emitted as literal kwargs ---------
    if diagnostics is not None and public_lookup:
        _check_unemitted_public_specs(public_lookup, emitted_public_keys, diagnostics)
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
                out_lines.append(f"    bind_input(wf, {input_name!r}, {_node_binding_expr(old_id, var_names, output_var_names)}, {resolved_field!r}{suffix})")
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
            raise SchemaValidationError(
                f"Circular subgraph reference detected: {cycle}",
                next_action="Break the circular reference in your subgraph dependency chain.",
            )
        temporary.add(subgraph_id)
        for dep in sorted(deps.get(subgraph_id, ())):
            visit(dep, [*stack, subgraph_id])
        temporary.remove(subgraph_id)
        permanent.add(subgraph_id)
        ordered.append(subgraph_id)

    for subgraph_id in subgraphs:
        visit(subgraph_id, [])
    return ordered


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


def _resolve_helper_nodes_for_emission(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> None:
    """Pre-emission resolver: rewrite GetNode consumer edges to their broadcast source and
    remove SetNode/GetNode/resolved-Reroute before topo_order is built.

    SetNode/GetNode/Reroute remain in FALLBACK_CLASS_TYPES as a raw_call safety net for
    unresolved instances the resolver cannot reach. This pass is distinct from the
    compile-time broadcast resolution in workflow.py (SD3); both call collect_broadcast_sources
    but operate on different representations and must stay separate.
    """
    from vibecomfy.porting.helpers import (
        RESOLVER_HELPER_CLASS_TYPES,
        broadcast_name as _broadcast_name,
        collect_broadcast_sources,
    )
    from vibecomfy.workflow import VibeEdge as _Edge

    flat_edges = [edge for edges in edges_in.values() for edge in edges]

    # --- SetNode/GetNode broadcast resolution ---
    broadcast_sources = collect_broadcast_sources(workflow_nodes, flat_edges)
    resolved_getnode_sources: dict[str, tuple[str, str]] = {}  # getnode_id -> (src_node, src_slot)
    removed_ids: set[str] = set()

    # Build SetNode → input-source map before marking for removal.
    # SetNode is a passthrough: other nodes may connect directly to SetNode's OUTPUT
    # (not only via GetNode broadcast), so we redirect those direct output edges too.
    resolved_setnode_output_sources: dict[str, tuple[str, str]] = {}
    for node_id, node in workflow_nodes.items():
        if str(getattr(node, "class_type", "")) != "SetNode":
            continue
        name = _broadcast_name(node)
        if name is not None and name in broadcast_sources:
            source = broadcast_sources[name]
            resolved_setnode_output_sources[node_id] = (str(source[0]), str(source[1]))

    for node_id, node in list(workflow_nodes.items()):
        cls = str(getattr(node, "class_type", ""))
        if cls == "SetNode":
            removed_ids.add(node_id)
        elif cls == "GetNode":
            name = _broadcast_name(node)
            if name is not None and name in broadcast_sources:
                source = broadcast_sources[name]
                resolved_getnode_sources[node_id] = (str(source[0]), str(source[1]))
                removed_ids.add(node_id)

    # Rewrite consumer edges: edges from a resolved GetNode or from a SetNode's direct
    # output both redirect to the broadcast source (SetNode's input).
    _all_setnode_rewrites = {**resolved_setnode_output_sources}
    if _all_setnode_rewrites or resolved_getnode_sources:
        for consumer_id in list(edges_in.keys()):
            new_edges = []
            for edge in edges_in[consumer_id]:
                from_node = str(edge.from_node)
                if from_node in resolved_getnode_sources:
                    src_node, src_slot = resolved_getnode_sources[from_node]
                    new_edges.append(_Edge(src_node, src_slot, edge.to_node, edge.to_input))
                elif from_node in _all_setnode_rewrites:
                    src_node, src_slot = _all_setnode_rewrites[from_node]
                    new_edges.append(_Edge(src_node, src_slot, edge.to_node, edge.to_input))
                else:
                    new_edges.append(edge)
            edges_in[consumer_id] = new_edges

    # --- Reroute resolution (additive; governed by RESOLVER_HELPER_CLASS_TYPES) ---
    # New set intentionally separate from BROADCAST_HELPER_CLASS_TYPES so consumers of
    # HELPER_CLASS_TYPES / is_broadcast_helper remain byte-identical (SD3).
    resolved_reroute_sources: dict[str, tuple[str, str]] = {}  # reroute_id -> (src_node, src_slot)
    for node_id, node in list(workflow_nodes.items()):
        if str(getattr(node, "class_type", "")) not in RESOLVER_HELPER_CLASS_TYPES:
            continue
        for edge in edges_in.get(node_id, []):
            resolved_reroute_sources[node_id] = (str(edge.from_node), str(edge.from_output))
            break  # Reroute has exactly one input

    if resolved_reroute_sources:
        for consumer_id in list(edges_in.keys()):
            new_edges = []
            for edge in edges_in[consumer_id]:
                from_node = str(edge.from_node)
                if from_node in resolved_reroute_sources:
                    src_node, src_slot = resolved_reroute_sources[from_node]
                    new_edges.append(_Edge(src_node, src_slot, edge.to_node, edge.to_input))
                else:
                    new_edges.append(edge)
            edges_in[consumer_id] = new_edges
        removed_ids.update(resolved_reroute_sources.keys())

    # Remove resolved nodes from workflow_nodes and their inbound edge lists
    for node_id in removed_ids:
        workflow_nodes.pop(node_id, None)
        edges_in.pop(node_id, None)


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
    assignment_target = _assignment_target(var_names[str(node.id)], output_var_names.get(str(node.id)))
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
    single_line = f"{body_indent}{assignment_target} = {subgraph.slug}({', '.join(kwarg_lines)})"
    if len(kwargs) > 3 or len(single_line) > 88:
        lines = [f"{body_indent}{assignment_target} = {subgraph.slug}("]
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
    kwargs: list[tuple[str, str]] = []
    for port in subgraph.inputs:
        candidate_names = (port.name, port.source_name or port.name)
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

    # proxyWidgets provides the authoritative named mapping for subgraph instances.
    # Honor the outer node's proxyWidgets ordering instead of walking inner widgets positionally.
    props = ui.get("properties")
    proxy_widgets = props.get("proxyWidgets") if isinstance(props, Mapping) else None
    if isinstance(proxy_widgets, list):
        widgets_values_raw = ui.get("widgets_values")
        if isinstance(widgets_values_raw, list):
            for i, entry in enumerate(proxy_widgets):
                if isinstance(entry, (list, tuple)) and len(entry) >= 2 and i < len(widgets_values_raw):
                    input_name = str(entry[1])
                    if input_name:
                        values[input_name] = widgets_values_raw[i]
            return values

    input_items = [item for item in ui.get("inputs") or () if isinstance(item, Mapping)]
    widgets_values = ui.get("widgets_values")
    if isinstance(widgets_values, Mapping):
        for item in input_items:
            widget = item.get("widget")
            if not isinstance(widget, Mapping):
                continue
            input_name = str(item.get("name") or widget.get("name") or "")
            widget_name = str(widget.get("name") or input_name)
            if input_name and widget_name in widgets_values:
                values.setdefault(input_name, widgets_values[widget_name])
        return values
    if isinstance(widgets_values, list):
        widget_index = 0
        for item in input_items:
            widget = item.get("widget")
            if not isinstance(widget, Mapping):
                continue
            input_name = str(item.get("name") or widget.get("name") or "")
            if input_name and widget_index < len(widgets_values):
                values.setdefault(input_name, widgets_values[widget_index])
            widget_index += 1
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


def _format_output_spec_block(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> list[str]:
    """Emit ``OUTPUT_SPEC = OutputSpec(...)`` when a resolvable terminal output node exists."""
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    if not output_node_ids:
        return []
    selected_id = output_node_ids[0]
    if selected_id is None:
        return []
    node = workflow_nodes[selected_id]
    output_contract = _OUTPUT_CLASSES.get(str(node.class_type))
    if output_contract is None:
        return []
    artifact_kind, mime_type = output_contract
    name = artifact_kind
    return [
        f"OUTPUT_SPEC = OutputSpec(name={name!r}, artifact_kind={artifact_kind!r}, mime_type={mime_type!r}, expected_cardinality='one')",
    ]


def _ready_template_tail_lines(
    has_ltx_tail: bool,
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    metadata: Mapping[str, Any],
) -> list[str]:
    finalize_args = _finalize_args(workflow_nodes, edges_in, var_names, output_var_names, metadata)
    input_expr = "{}"
    if metadata.get("_has_output_spec_for_emit"):
        finalize_args = finalize_args + ", spec=OUTPUT_SPEC"
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
    if len(output_node_ids) > 1 and selected_id is not None:
        output_var = _first_output_var(output_var_names.get(selected_id))
        args.append(f"output_node={output_var or var_names.get(selected_id, repr(selected_id))}")
    if selected_id is not None:
        node = workflow_nodes[selected_id]
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


def _node_binding_expr(
    node_id: str,
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]] | None = None,
) -> str:
    # For tuple-unpacked multi-output nodes the base var_names entry (e.g.
    # 'lowvramcheckpointloader') is never assigned — only the unpacked output
    # variables (e.g. 'model', 'clip', 'vae') exist as Handle objects.
    # Handle.node_id gives the node ID; use the first output var.
    # For non-unpacked nodes the assignment target is a _NodeBuilder; use .node.id.
    if output_var_names:
        slot_vars = output_var_names.get(str(node_id))
        if slot_vars:
            first_var = next(iter(slot_vars.values()), None)
            if first_var is not None:
                return f"{first_var}.node_id"  # Handle attribute, not _NodeBuilder.node.id
    var = var_names.get(str(node_id))
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
    visible_sections = [sec for sec in _SECTION_ORDER if sec not in _SUPPRESSED_SECTION_COMMENTS]
    has_visible_section_groups = any(section_groups.get(sec) for sec in visible_sections)
    if len(workflow_nodes) >= _SECTION_NODE_THRESHOLD and has_visible_section_groups:
        has_section_comment = any(
            line.strip().startswith("# ") and any(
                line.strip().endswith(f"# {sec}")
                or line.strip() == f"# {sec}"
                or line.strip().startswith(f"# {sec}")
                for sec in visible_sections
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
        slot_vars: dict[int, str] = {}
        for index, name in enumerate(names):
            base = _safe_var(str(name).lower())
            candidate = base
            if candidate in used:
                candidate = f"{base}_{suffix}"
            if candidate in used:
                ordinal = 2
                while f"{candidate}_{ordinal}" in used:
                    ordinal += 1
                candidate = f"{candidate}_{ordinal}"
            used.add(candidate)
            slot_vars[index] = candidate
        output_vars[nid] = slot_vars
    return output_vars


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


def _assignment_target(var: str, output_vars: dict[int, str] | None) -> str:
    if not output_vars:
        return var
    return ", ".join(output_vars[index] for index in sorted(output_vars))


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
    public_lookup: dict[tuple[str, str], list] | None = None,
    emitted_public_keys: set | None = None,
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
    if public_lookup is None:
        public_lookup = {}
    if emitted_public_keys is not None:
        emitted_public_keys_local = emitted_public_keys
    else:
        emitted_public_keys_local = set()
    if preserve_fields is None:
        preserve_fields = set()
    if external_refs is None:
        external_refs = {}

    incoming: dict[str, tuple[str, int]] = {}
    incoming_exprs: dict[str, str] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str) -> str | None:
        if not key.startswith("widget_"):
            return key
        return resolve_widget_key_with_provenance(cls, key, input_aliases=input_aliases).name

    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        elif key not in raw_inputs:
            raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key)
        if translated is None:
            continue
        if translated != key and translated not in raw_inputs and translated not in static_inputs and translated not in incoming:
            static_inputs[translated] = value
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

    def _wrap_public(key: str, base_expr: str) -> str:
        """Wrap a static value with public() if it targets a public input.

        Fields in ``_FILENAME_KWARGS`` (unet_name, vae_name, clip_name, etc.)
        are NOT wrapped — their public inputs are registered via explicit
        ``wf.register_input()`` calls emitted by ``_emit_build_function``.
        """
        # Lazy import to avoid circular dependency at module level.
        from vibecomfy.templates import _FILENAME_KWARGS

        if key in _FILENAME_KWARGS:
            return base_expr
        lookup_key = (str(getattr(node, "id", "")), key)
        specs = public_lookup.get(lookup_key)
        if specs:
            emitted_public_keys_local.add(lookup_key)
            return _format_public_call(specs, base_expr)
        return base_expr

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
        val_expr = _format_static_value(key, static_inputs[key])
        if not _is_python_ident(key) and not (emit_reserved_keyword_args and key in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((key, _wrap_public(key, val_expr)))
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
        out.append((key, _wrap_public(key, val_expr)))

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
    **kwargs,
):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
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
