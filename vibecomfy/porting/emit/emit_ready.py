"""emit_ready.py — ready-template backend and public-input infrastructure.

Houses:
- _PublicInputBinding, _PublicInputSpec       (public-input data types)
- _public_input_specs                         (build public-input spec list)
- _format_public_inputs_block                 (render PUBLIC_INPUT_METADATA dict)
- _remap_public_inputs_for_materialized_subgraphs
- _subgraph_port_index_for_instance_field
- _infer_public_input_bindings                (auto-detect prompt/seed/etc.)
- _node_title, _resolved_field_values         (per-node field helpers)
- GENERATED_HEADER                            (header comment for generated files)
- _lock_entries_by_class, _custom_node_packs_for_emit
- _format_ready_metadata_build
- _strip_unused_template_imports, _import_binding_name
- emit_ready_template_python                  (public entry point)
- _emit_ready_template_python_inner
- _emit_build_function                        (shared by ready + scratchpad)
- _with_id_map_tail_line
- _OUTPUT_CLASSES, _ready_template_tail_lines, _finalize_args
- _terminal_output_node_ids, _is_output_class
- _check_template_formatting, _has_ltx_lowvram_tail
- _apply_overrides
- _prune_dead_branches_for_emit, _is_dead_optional_output_input
- _ltx_travel_template_omits_synthetic_audio
- _all_nodes_for_imports

Part of the M2 structural decomposition of vibecomfy/porting/emitter.py.
"""
from __future__ import annotations

from vibecomfy.ingest.normalize import canonical_definition_links, canonical_definition_nodes, canonical_node_widgets, canonical_node_widgets_values

from vibecomfy.ingest.normalize import door_nodes
import ast
import copy
import json
import keyword as _keyword
import textwrap
import unicodedata
from dataclasses import replace
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from vibecomfy._compile._helpers import RESOLVABLE_HELPER_CLASS_TYPES
from vibecomfy.node_packs import LockEntry, read_lockfile
from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA
from vibecomfy.porting.emit.emit_constants import (
    _LOAD_IMAGE_FAMILY,
    _looks_like_placeholder_filename,
    _apply_ready_template_metadata_defaults,
    _metadata_extras_for_emit,
    _requirements_expr_for_emit,
    _format_models_block,
    _model_assets_for_emit,
    _wrapper_imports_for_nodes,
    _wrapper_module_for_class,
    _wrapper_symbol_for_class,
    _hoist_constants,
    _build_section_groups,
    _drop_output_prefix_constants,
    _translate_widget_for_key,
    _ui_widget_aliases,
    _resolve_graph_field_get_string,
    LTX2_3_TAIL_PATCHES,
    _SECTION_ORDER,
    _SECTION_NODE_THRESHOLD,
)
from vibecomfy.porting.emit.emit_kwargs import (
    _format_value,
    _first_output_var,
    _id_sort_key,
    _is_link,
    _format_metadata_dict,
    _node_output_names,
    _safe_output_name,
    _output_fallback_diagnostic,
    _is_schema_confirmed_single_output,
    _is_single_output_ref,
    _node_binding_expr,
    _edge_ref_expr,
    _wrapper_kwarg_name,
    _assignment_target,
    _live_output_slots_for_function,
    _edges_in_with_subgraph_external_refs,
    _topological_node_order,
    _node_kwargs,
)
from vibecomfy.porting.emit.emit_subgraph import (
    _SubgraphDef,
    _subgraph_emitted_node_id,
    _subgraph_node_id_required,
    _apply_subgraph_names_to_prepared,
    _emit_subgraph_call_statement,
    _subgraph_instance_port_candidate_names,
    _subgraph_return_expr,
)
from vibecomfy.porting._provenance_utils import _normalize_provenance_paths


# ---------------------------------------------------------------------------
# Public-input data types
# ---------------------------------------------------------------------------

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
    range: Any = None
    allow_missing_target: bool = False
    infer_type: bool = True
    materialize_aliases: bool = True


# ---------------------------------------------------------------------------
# Generated-file header
# ---------------------------------------------------------------------------

GENERATED_HEADER = (
    "# vibecomfy: generated\n"
    "# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>\n"
)


# ---------------------------------------------------------------------------
# Per-node field helpers
# ---------------------------------------------------------------------------

def _node_title(node: Any) -> str:
    ui = getattr(node, "metadata", {}).get("_ui")
    if isinstance(ui, dict):
        title = ui.get("title")
        if isinstance(title, str):
            return title
    return ""


def _resolved_field_values(node: Any) -> dict[str, Any]:
    class_type = str(getattr(node, "class_type", ""))
    metadata = getattr(node, "metadata", {})
    aliases = metadata.get("input_aliases") if isinstance(metadata, Mapping) else None
    if not isinstance(aliases, (list, tuple)):
        # Public-input inference must use the same source-backed compact
        # widget roster as Python emission.  This names proven seed slots
        # (including custom-node schemas) without inventing names for opaque
        # widgets such as UltraShapeSaveGLB.
        aliases = compact_widget_names_for_node(node, class_type).names
    values: dict[str, Any] = {}
    # ``inputs`` is the semantic channel and wins only after translating both
    # channels to their canonical field names.  This mirrors direct compile's
    # widgets-then-inputs precedence without consulting presentation ``_ui`` or
    # silently selecting widgets for a same-name collision.
    for key, value in getattr(node, "inputs", {}).items():
        translated = _translate_widget_for_key(str(key), aliases, class_type)
        if translated is not None:
            values[translated] = value
    for key, value in getattr(node, "widgets", {}).items():
        translated = _translate_widget_for_key(str(key), aliases, class_type)
        if translated is not None and translated not in values:
            values[translated] = value
    return values


def _has_proven_schema_type(node: Any) -> bool:
    """Whether a node carries source-backed type evidence for inference."""
    metadata = getattr(node, "metadata", {})
    source = metadata.get("schema_source") if isinstance(metadata, Mapping) else None
    confidence = source.get("confidence") if isinstance(source, Mapping) else None
    return isinstance(confidence, (int, float)) and confidence > 0


# ---------------------------------------------------------------------------
# Public-input inference
# ---------------------------------------------------------------------------

def _infer_public_input_bindings(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    *,
    reserved_names: set[str] | None = None,
    reserved_targets: set[tuple[str, str]] | None = None,
) -> list[_PublicInputBinding]:
    bindings: list[_PublicInputBinding] = []
    used_names: set[str] = set(reserved_names or set())
    used_targets: set[tuple[str, str]] = set(reserved_targets or set())

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
        target = (str(node_id), str(field))
        # A retained public-input descriptor owns its target even when its
        # authored name differs from the heuristic role name.  Inference must
        # not create a second semantic name for that same field and later fold
        # it into the retained descriptor's aliases.
        if target in used_targets:
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
        used_targets.add(target)
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

        if class_type in {"CLIPTextEncode", "CLIPTextEncodeFlux", "CLIPTextEncodeSD3", "CLIPTextEncodeSDXL", "TextEncodeQwenImageEdit"}:
            value = _resolve_graph_field_get_string(fields.get("text"), workflow_nodes)
            if isinstance(value, str):
                metadata = getattr(node, "metadata", {})
                semantic = metadata.get("semantic", metadata.get("semantic_metadata", {})) if isinstance(metadata, Mapping) else {}
                role = semantic.get("role", semantic.get("prompt_role")) if isinstance(semantic, Mapping) else None
                target_available = (str(node_id), "text") not in used_targets
                if isinstance(role, str) and "negative" in role.lower() and target_available:
                    negative_candidate = negative_candidate or (str(node_id), "text")
                elif value.strip() and target_available:
                    prompt_candidate = prompt_candidate or (str(node_id), "text")
        primitive_value = _resolve_graph_field_get_string(fields.get("value"), workflow_nodes)
        if class_type in {"PrimitiveStringMultiline", "PrimitiveString"} and isinstance(
            primitive_value,
            str,
        ) and primitive_value.strip() and (str(node_id), "value") not in used_targets:
            prompt_candidate = prompt_candidate or (str(node_id), "value")
        if class_type == "LoadImage" and "image" in fields:
            add("image", str(node_id), "image", type="IMAGE", required=True, aliases=("input_image",), media_semantics="image")
        if (
            "seed" in fields
            and isinstance(fields["seed"], int)
            and not isinstance(fields["seed"], bool)
            and _has_proven_schema_type(node)
        ):
            add("seed", str(node_id), "seed", type="INT")
        if (
            "noise_seed" in fields
            and isinstance(fields["noise_seed"], int)
            and not isinstance(fields["noise_seed"], bool)
            and _has_proven_schema_type(node)
        ):
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


# ---------------------------------------------------------------------------
# Public-input spec builder
# ---------------------------------------------------------------------------

def _public_input_specs(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    *,
    registered_inputs: dict[str, tuple[str, str]] | None,
    constant_map: dict[tuple[str, str], str],
    authored_inputs: Mapping[str, Any] | None = None,
) -> list[_PublicInputSpec]:
    specs: list[_PublicInputSpec] = []
    used_names: set[str] = set()
    used_targets: set[tuple[str, str]] = set()

    def add(
        binding: _PublicInputBinding,
        *,
        retained_node_ref: str | None = None,
    ) -> None:
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
        authored = (authored_inputs or {}).get(binding.name)
        if authored is not None:
            read = (
                (lambda key, fallback=None: authored.get(key, fallback))
                if isinstance(authored, Mapping)
                else (lambda key, fallback=None: getattr(authored, key, fallback))
            )
            authored_default = copy.deepcopy(read("default"))
            binding = replace(
                binding,
                type=read("type"),
                required=bool(read("required", False)),
                aliases=tuple(read("aliases", ()) or ()),
                media_semantics=read("media_semantics"),
            )
        else:
            read = lambda key, fallback=None: fallback
            authored_default = default_value
        default_expr = (
            None
            if authored is not None
            else constant_map.get((str(binding.node_id), binding.field))
        )
        if default_expr is None:
            default_expr = _format_value(authored_default)
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
        metadata_node_ref = (
            retained_node_ref
            if retained_node_ref is not None
            else (
                repr(str(binding.node_id))
                if registered_inputs is not None
                else (f"ref({node_var!r})" if node_var is not None else repr(str(binding.node_id)))
            )
        )
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
                range=copy.deepcopy(read("range")),
                allow_missing_target=bool(read("allow_missing_target", False)),
                infer_type=authored is None,
                materialize_aliases=(
                    authored is None
                    or all(alias in (authored_inputs or {}) for alias in binding.aliases)
                ),
            )
        )
        used_names.add(binding.name)
        used_names.update(binding.aliases)
        used_targets.add((str(binding.node_id), str(binding.field)))

    for input_name, (old_id, field) in dict(registered_inputs or {}).items():
        resolved_field = field
        if field.startswith("widget_") and old_id in workflow_nodes:
            cls = workflow_nodes[old_id].class_type
            node = workflow_nodes[old_id]
            metadata = getattr(node, "metadata", {})
            aliases = metadata.get("input_aliases") if isinstance(metadata, Mapping) else None
            resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
            if resolved.resolved and resolved.name is not None:
                resolved_field = resolved.name
        if resolved_field.startswith("widget_"):
            continue
        add(
            _PublicInputBinding(name=input_name, node_id=str(old_id), field=resolved_field),
            retained_node_ref=repr(str(old_id)),
        )

    # A supplied retained map (including an explicitly empty one) permits
    # ordinary inference for targets it does not occupy.  ``None`` means the
    # caller did not request retained-input reconciliation and preserves the
    # legacy no-inference surface.
    if registered_inputs is not None:
        inferred = _infer_public_input_bindings(
            workflow_nodes,
            edges_in,
            reserved_names=used_names,
            reserved_targets=used_targets,
        )
        for binding in inferred:
            # Retained-input reconciliation fills the role-based controls
            # that can be safely inferred without changing unrelated asset or
            # output configuration bindings supplied by the caller.
            if binding.name in {"prompt", "negative_prompt", "seed"}:
                add(binding)
    return specs


# ---------------------------------------------------------------------------
# Public-input block formatter
# ---------------------------------------------------------------------------

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
        if spec.range is not None:
            args.append(f"range={spec.range!r}")
        if spec.allow_missing_target:
            args.append("allow_missing_target=True")
        if not spec.infer_type:
            args.append("infer_type=False")
        if not spec.materialize_aliases:
            args.append("materialize_aliases=False")
        lines.append(f"    {spec.name!r}: InputSpec({', '.join(args)}),")
    lines.append("}" if metadata else "    }")
    return lines


def _share_public_input_values(
    specs: list[_PublicInputSpec],
    workflow_nodes: Mapping[str, Any],
    var_names: Mapping[str, str],
    *,
    constant_lines: list[str],
    constant_map: dict[tuple[str, str], str],
) -> tuple[list[str], list[_PublicInputSpec]]:
    """Name a value shared by a constructor and its public descriptor once."""
    if not specs:
        return constant_lines, specs
    node_by_var = {str(variable): str(node_id) for node_id, variable in var_names.items()}
    used_names: set[str] = set()
    if constant_lines:
        try:
            used_names.update(
                target.id
                for statement in ast.parse("\n".join(constant_lines)).body
                if isinstance(statement, (ast.Assign, ast.AnnAssign))
                for target in (
                    statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                )
                if isinstance(target, ast.Name)
            )
        except SyntaxError:
            pass

    rewritten: list[_PublicInputSpec] = []
    additions: list[str] = []
    for spec in specs:
        node_id = node_by_var.get(str(spec.node_ref))
        node = workflow_nodes.get(node_id) if node_id is not None else None
        fields = _resolved_field_values(node) if node is not None else {}
        if spec.field not in fields:
            rewritten.append(spec)
            continue
        current_expr = _format_value(fields[spec.field])
        if current_expr != spec.default_expr:
            rewritten.append(spec)
            continue
        expression = constant_map.get((node_id, spec.field))
        if expression is None:
            stem = "".join(
                character if character.isalnum() else "_"
                for character in str(spec.name).upper()
            ).strip("_") or "INPUT"
            base = f"DEFAULT_{stem}"
            expression = base
            suffix = 2
            while expression in used_names:
                expression = f"{base}_{suffix}"
                suffix += 1
            used_names.add(expression)
            additions.append(f"{expression} = {current_expr}")
            constant_map[(str(node_id), spec.field)] = expression
        rewritten.append(replace(spec, default_expr=expression))
    return [*constant_lines, *additions], rewritten


# ---------------------------------------------------------------------------
# Subgraph port index helper
# ---------------------------------------------------------------------------

def _subgraph_port_index_for_instance_field(node: Any, subgraph: _SubgraphDef, field: str) -> int | None:
    candidates = _subgraph_instance_port_candidate_names(node, subgraph)
    for index, names in candidates.items():
        if field in names:
            return index
    return None


# ---------------------------------------------------------------------------
# Remap public inputs through materialized subgraphs
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Lockfile / custom-node-pack helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Ready-metadata build formatter
# ---------------------------------------------------------------------------

def _format_ready_metadata_build(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
    *,
    has_models: bool,
    has_public_inputs: bool,
    custom_node_packs: Mapping[str, Any] | None = None,
    output_node_class_type: str | None = None,
    external_custody: bool = False,
    preserve_empty_models: bool = False,
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
        f"    template_id={template_id!r},",
    ]
    if has_public_inputs:
        lines.append("    inputs=PUBLIC_INPUT_METADATA,")
    if has_models:
        lines.append("    models=MODELS,")
    if output_prefix != template_id:
        lines.append(f"    output_prefix={output_prefix!r},")
    requirements_expr = _requirements_expr_for_emit(
        requirements,
        has_models=has_models,
        preserve_empty_models=preserve_empty_models,
    )
    if requirements_expr is not None:
        lines.append(f"    requirements={requirements_expr},")
    if custom_node_packs:
        lines.append(f"    custom_node_packs={_format_value(dict(custom_node_packs))},")
    for key, value in _metadata_extras_for_emit(
        metadata, external_custody=external_custody
    ).items():
        lines.append(f"    {key}={_format_value(value)},")
    lines.append(")")
    return lines


# ---------------------------------------------------------------------------
# Template import stripping
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Ready-template entry point
# ---------------------------------------------------------------------------

def emit_ready_template_python(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[Any] | None = None,
    raw_workflow: dict[str, Any] | None = None,
    object_info_identities: dict[str, Any] | None = None,
    omit_terminal_ui_only: bool = False,
    keep_virtual_wires: bool = False,
    preserve_node_ids: bool = False,
    external_custody: bool = False,
    preserve_authored_graph: bool = False,
) -> str:
    from vibecomfy.porting.emitter import _use_object_info_identities, _drain_lookup_warning_diagnostics  # noqa: PLC0415
    with _use_object_info_identities(object_info_identities):
        result_text = _emit_ready_template_python_inner(
            workflow,
            ready_metadata=ready_metadata,
            ready_requirements=ready_requirements,
            template_id=template_id,
            registered_inputs=registered_inputs,
            apply_overrides=apply_overrides,
            diagnostics=diagnostics,
            raw_workflow=raw_workflow,
            omit_terminal_ui_only=omit_terminal_ui_only,
            keep_virtual_wires=keep_virtual_wires,
            preserve_node_ids=preserve_node_ids,
            external_custody=external_custody,
            preserve_authored_graph=preserve_authored_graph,
        )
        lookup_warnings = _drain_lookup_warning_diagnostics(diagnostics)
        if lookup_warnings:
            raise ValueError(
                "schema_reconciliation_required: canonical emission encountered "
                "an unprovenanced or mismatched object-info lookup"
            )
    return result_text


def _emit_ready_template_python_inner(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[Any] | None = None,
    raw_workflow: dict[str, Any] | None = None,
    omit_terminal_ui_only: bool = False,
    keep_virtual_wires: bool = False,
    preserve_node_ids: bool = False,
    external_custody: bool = False,
    preserve_authored_graph: bool = False,
) -> str:
    from vibecomfy.porting.emit.emit_prepare import _prepare_workflow_for_emit  # noqa: PLC0415
    _preflight_object_info_identity_resolution(workflow)
    # Bundle publication opts into the compact companion-backed form. Direct
    # ready-template conversion remains independently buildable and may retain
    # the recursive helper's structural witness locally; published pairs keep
    # that witness in the sibling companion instead.
    metadata = dict(ready_metadata)
    metadata["ready_template"] = str(workflow.id)
    metadata["workflow_template"] = str(workflow.id).rsplit("/", 1)[-1]
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

    # Canonical executable source is derived exclusively from the authored
    # VibeWorkflow IR. ``raw_workflow`` remains an accepted migration input,
    # but never becomes a second semantic authority during emission.
    subgraph_definitions: dict[str, _SubgraphDef] = {}
    emission_workflow = workflow.copy()
    # Retain ``_ui`` through preparation because its output-slot roster is
    # required to reconcile emitted tuple arity for an already-loaded graph.
    # ``_emit_function_body`` removes it from a detached semantic-node copy
    # immediately before kwargs emission, so presentation data still cannot
    # become call arguments or workflow semantics.
    _validate_named_output_edges(workflow)
    prepared = _prepare_workflow_for_emit(
        emission_workflow,
        apply_overrides=apply_overrides,
        template_id=template_id,
        diagnostics=diagnostics,
        project_execution_edges=not preserve_authored_graph,
        omit_terminal_ui_only=omit_terminal_ui_only,
        keep_virtual_wires=keep_virtual_wires,
        prune_dead_branches=False,
    )
    # UI widget labels/titles are presentation evidence, not constructor-name
    # authority.  Retained native/schema metadata remains available to the
    # compact resolver without consulting the raw UI name table.
    prepared["name_authority"] = {}
    prepared["subgraph_definitions"] = subgraph_definitions
    _apply_subgraph_names_to_prepared(prepared)
    # The canonical workflow already contains the effective result of any
    # template-specific preparation. Reapplying a legacy build tail would be
    # a second semantic authority and can override visible constructor edits.
    has_ltx_tail = False

    workflow_nodes = door_nodes(prepared)
    edges_in = prepared["edges_in"]
    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
    var_names = prepared["var_names"]
    python_definition_lines, python_authoring_aliases = _python_authoring_definitions(workflow_nodes)
    python_source_lines, python_source_aliases, python_source_outputs = _python_source_declarations(
        workflow_nodes,
        reserved_names=set(python_authoring_aliases.values()),
    )
    prepared["python_authoring_aliases"] = python_authoring_aliases
    prepared["python_source_aliases"] = python_source_aliases
    prepared["python_source_outputs"] = python_source_outputs

    # Hoist constants and build section groups
    constant_lines, constant_map = _hoist_constants(
        workflow_nodes,
        edges_in,
        var_names,
        name_authority=prepared.get("name_authority"),
        resolve_graph_strings=False,
    )
    constant_lines, constant_map = _drop_output_prefix_constants(constant_lines, constant_map)
    section_groups = _build_section_groups(workflow_nodes, edges_in)
    definition_lines, definitions_expr = _canonical_definition_helpers(
        workflow.definitions,
        interfaces=workflow.interfaces,
        boundary_ports=workflow.boundary_ports,
        external_custody=external_custody,
    )
    wrapper_imports = _wrapper_imports_for_nodes(_all_nodes_for_imports(workflow_nodes, subgraph_definitions))
    wrapper_imports = _merge_definition_wrapper_imports(
        wrapper_imports, workflow.definitions
    )
    output_var_names = prepared["output_var_names"]
    # Keep every constructed node bound to one stable Python variable.  Named
    # ``.out(...)`` handles express fanout/slot selection without discarding
    # the builder object needed by compact identity custody.
    output_var_names = {}
    prepared["output_var_names"] = output_var_names
    public_inputs = _public_input_specs(
        workflow_nodes,
        edges_in,
        var_names,
        output_var_names,
        registered_inputs=registered_inputs,
        constant_map=constant_map,
        authored_inputs=workflow.inputs,
    )
    constant_lines, public_inputs = _share_public_input_values(
        public_inputs,
        workflow_nodes,
        var_names,
        constant_lines=constant_lines,
        constant_map=constant_map,
    )
    model_assets = _model_assets_for_emit(metadata, requirements)
    # An explicitly empty requirements.models list is meaningful for an
    # editable draft even when a model-picker widget is already present.  It
    # is only serialized when the graph proves that such a picker exists;
    # ordinary model-free workflows stay as clean as before.
    from vibecomfy.model_assets import _referenced_model_values
    preserve_empty_models = (
        not model_assets
        and requirements.get("models") == []
        and bool(_referenced_model_values(workflow))
    )
    custom_node_packs = _custom_node_packs_for_emit(workflow_nodes, metadata, requirements)
    has_public_inputs = bool(public_inputs)
    metadata["_has_public_inputs_for_emit"] = has_public_inputs

    out_lines: list[str] = []
    out_lines.append(GENERATED_HEADER.rstrip("\n"))
    out_lines.append("# vibecomfy: surface=canonical")
    out_lines.append('"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append(
        "from vibecomfy.templates import InputSpec, ModelAsset, OutputSpec, ReadyMetadata, authored_channel, finalize, new_workflow, node as raw_call, recursive_definition_scope, ref"
    )
    out_lines.append("from vibecomfy.workflow import VibeWorkflow")
    if python_definition_lines or python_source_lines:
        out_lines.append("from vibecomfy import python_node")
    def _has_capsule_source(node: Any) -> bool:
        metadata = getattr(node, "metadata", {})
        payload = metadata.get("python_source") if isinstance(metadata, Mapping) else None
        return isinstance(payload, Mapping) and payload.get("format") == "vibecomfy.python_capsule/v1"

    if python_source_lines and any(_has_capsule_source(node) for node in workflow_nodes.values()):
        out_lines.append("from vibecomfy import SourceCapsule")
    if python_source_lines and any(
        "result=" in line or "outputs=outputs(" in line for line in python_source_lines
    ):
        out_lines.append("from vibecomfy.python_authoring import outputs")
    for module_name, names in sorted(wrapper_imports.items()):
        out_lines.append(f"from vibecomfy.nodes.{module_name} import {', '.join(names)}")
    if has_ltx_tail:
        out_lines.extend(LTX2_3_TAIL_PATCHES)
    out_lines.append("")
    if python_definition_lines:
        out_lines.extend(python_definition_lines)
        out_lines.append("")
    if python_source_lines:
        out_lines.extend(python_source_lines)
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
    # Direct spec inspection keeps the retained source node id (needed by the
    # remapper and its unit contract); emitted Python metadata binds the
    # corresponding canonical node object.
    node_ids_by_var = {str(variable): str(node_id) for node_id, variable in var_names.items()}
    public_inputs_for_metadata = [
        replace(
            spec,
            metadata_node_ref=(
                f"ref({spec.node_ref!r})"
                if spec.metadata_node_ref == repr(node_ids_by_var.get(spec.node_ref))
                else spec.metadata_node_ref
            ),
        )
        for spec in public_inputs_for_metadata
    ]
    public_input_metadata_lines = _format_public_inputs_block(public_inputs_for_metadata, metadata=True)
    if public_input_metadata_lines:
        out_lines.append("")
        out_lines.extend(public_input_metadata_lines)
        out_lines.append("")
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
            external_custody=external_custody,
            preserve_empty_models=preserve_empty_models,
        )
    )
    out_lines.append("")
    if definition_lines:
        out_lines.extend(definition_lines)
        out_lines.append("")
    tail_lines = _ready_template_tail_lines(
        has_ltx_tail,
        workflow_nodes,
        edges_in,
        var_names,
        output_var_names,
        metadata,
    )
    input_expr = "PUBLIC_INPUT_METADATA" if has_public_inputs else "{}"
    if external_custody:
        # The v2 source uses the concise companion-backed output declaration.
        tail_lines[-1] = f"    return wf.finalize({input_expr})"
    finalize_line = tail_lines[-1].replace("return wf.finalize(", "wf = wf.finalize(", 1)
    if not finalize_line.endswith(")"):
        raise RuntimeError("canonical finalize line is malformed")
    input_expr = "PUBLIC_INPUT_METADATA" if has_public_inputs else "{}"
    # Use one typed output spelling for direct and companion-backed renders.
    # It preserves explicit multi-output contracts and makes an output-less
    # direct graph unambiguous without reintroducing the legacy output-node
    # argument bundle.
    finalize_line = f"    wf = wf.finalize({input_expr}{_v2_output_args(workflow, var_names, metadata)})"
    # Finalization owns compact identity/schema rebinding.  Runtime values and
    # topology are already authoritative in the constructor calls above.
    tail_lines = [
        *tail_lines[:-1],
        finalize_line,
        *(
            f"    {line}"
            for line in _canonical_graph_semantic_lines(
                workflow,
                definitions_expr=definitions_expr,
            )
        ),
        "    return wf",
    ]
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr="READY_METADATA",
            source_path_expr="__file__",
            source_type="ready_template",
            source_provenance=None,
            registered_inputs=registered_inputs,
            public_inputs=public_inputs,
            tail_lines=tail_lines,
            diagnostics=diagnostics,
            use_shared_helpers=True,
            # CLI bundle preflight needs a temporary source-id witness so its
            # rebuilt candidate can be joined back to the captured UI graph.
            # The published source leaves this false and keeps identity in the
            # sibling sidecar instead of making the Python noisy.
            emit_all_ids=preserve_node_ids,
            constant_map=constant_map,
            section_groups=section_groups,
            external_custody=external_custody,
            preserve_authored_graph=preserve_authored_graph,
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


def _canonical_graph_semantic_lines(
    workflow: Any,
    *,
    definitions_expr: str | None,
) -> list[str]:
    """Render graph-level authored declarations not owned by node calls."""
    def render(value: Any) -> str:
        return _format_value(_plain_canonical_value(copy.deepcopy(value)))

    lines: list[str] = []
    # Virtual wires are an ingestion/presentation witness. Their legs are
    # already materialized into ordinary constructor edges by the shared
    # execution projection. Replaying that roster in Python would create a
    # second connectivity authority (and duplicate edges on reload); the v2
    # companion retains the presentation/custody evidence.
    for field_name in ("definitions", "interfaces", "boundary_ports"):
        value = copy.deepcopy(getattr(workflow, field_name, None))
        if value:
            value_expr = definitions_expr if field_name == "definitions" else None
            lines.append(f"wf.{field_name} = {value_expr or render(value)}")
    if workflow.variants:
        lines.append(f"wf.variants = {render(workflow.variants)}")
    if workflow.default_variant is not None:
        lines.append(f"wf.default_variant = {render(workflow.default_variant)}")
    lines.append(f"wf.strict_types = {render(bool(workflow.strict_types))}")
    return lines


def _canonical_node_custody(
    workflow_nodes: Mapping[str, Any],
    var_names: Mapping[str, str],
    *,
    edges_in: Mapping[str, list[Any]],
    name_authority: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return the compact non-runtime custody manifest for emitted nodes."""
    custody: dict[str, dict[str, Any]] = {}
    allowed_metadata = (
        "semantic", "semantic_metadata", "schema_source", "unresolved",
        "reconciliation", "diagnostics", "provenance", "input_names",
        "output_names", "input_types", "output_types", "keep_defaults",
    )
    for node_id in _topological_node_order(workflow_nodes, dict(edges_in)):
        node = workflow_nodes[node_id]
        label = str(var_names[node_id])
        metadata = getattr(node, "metadata", {})
        retained_metadata = _v2_custody_metadata(metadata, allowed_metadata)
        widget_channels = _canonical_widget_channels(node, name_authority)
        linked_inputs = {
            str(edge.to_input)
            for edge in edges_in.get(str(node_id), ())
        }
        output_slot_names: dict[str, str] = {}
        output_names = getattr(node, "native_output_names", None)
        if not isinstance(output_names, (list, tuple)):
            output_names = metadata.get("output_names") if isinstance(metadata, Mapping) else None
        if isinstance(output_names, (list, tuple)):
            for incoming_edges in edges_in.values():
                for edge in incoming_edges:
                    if str(edge.from_node) != str(node_id):
                        continue
                    raw_output = str(edge.from_output)
                    if raw_output.isdigit():
                        continue
                    matches = [
                        index for index, name in enumerate(output_names)
                        if isinstance(name, str) and name.casefold() == raw_output.casefold()
                    ]
                    if len(matches) != 1:
                        raise ValueError(
                            f"malformed_named_output_schema: {node.class_type} output {raw_output!r} "
                            "does not identify exactly one retained slot"
                        )
                    output_slot_names[str(matches[0])] = raw_output
        custody[label] = {
            "id": str(node_id),
            "uid": str(node.uid),
            "class_type": str(node.class_type),
            "native_ports": {
                "native_input_names": copy.deepcopy(node.native_input_names),
                "native_output_names": copy.deepcopy(node.native_output_names),
                "native_input_types": copy.deepcopy(node.native_input_types),
                "native_output_types": copy.deepcopy(node.native_output_types),
                "native_input_optional": copy.deepcopy(node.native_input_optional),
                "native_input_asset_kinds": copy.deepcopy(node.native_input_asset_kinds),
                "native_output_slots": copy.deepcopy(node.native_output_slots),
            },
            "metadata": retained_metadata,
            "widget_channels": widget_channels,
            "none_input_fields": sorted(
                key for key, value in node.inputs.items()
                if value is None and key in linked_inputs
            ),
            "none_widget_fields": sorted(
                key for key, value in node.widgets.items()
                if value is None and key in linked_inputs
            ),
            "output_slot_names": output_slot_names,
        }
        construction_output_names = _node_output_names(node)
        if node.native_output_names is None and construction_output_names:
            custody[label]["construction_output_names"] = construction_output_names
    return custody


def canonical_v2_custody(
    workflow: Any,
    *,
    preserve_authored_graph: bool = False,
) -> dict[str, Any]:
    """Project the emitted constructor roster into the closed v2 capsule.

    This deliberately reuses the canonical execution preparation and label
    assignment used by the Python renderer.  The returned records contain no
    runtime values or semantic edges.
    """
    from vibecomfy.porting.emit.emit_prepare import _prepare_workflow_for_emit

    prepared = _prepare_workflow_for_emit(
        workflow.copy(),
        apply_overrides=None,
        template_id=str(workflow.id),
        diagnostics=None,
        project_execution_edges=not preserve_authored_graph,
        omit_terminal_ui_only=False,
        keep_virtual_wires=True,
        prune_dead_branches=False,
    )
    prepared["name_authority"] = {}
    nodes = door_nodes(prepared)
    records = _canonical_node_custody(
        nodes,
        prepared["var_names"],
        edges_in=prepared["edges_in"],
        name_authority=prepared["name_authority"],
    )
    result: dict[str, Any] = {
        "scopes": [
            {
                "scope_path": "",
                "nodes": [
                    {"label": label, **copy.deepcopy(record)}
                    for label, record in records.items()
                ],
                "helpers": _canonical_helper_custody(workflow),
            }
        ]
    }
    recursive_custody = _recursive_constructor_custody(
        getattr(workflow, "definitions", None)
    )
    if recursive_custody is not None:
        result["scopes"].extend(_recursive_scope_custody(recursive_custody))
        result["definitions"] = recursive_custody
    return result


def _canonical_helper_custody(workflow: Any) -> list[dict[str, Any]]:
    """Retain provenance for lowered helpers without retaining their values."""

    def position_pair(value: Any) -> list[float] | None:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        first, second = value[:2]
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in (first, second)):
            return None
        return [float(first), float(second)]

    records: list[dict[str, Any]] = []
    for node_id, node in sorted(workflow.nodes.items(), key=lambda item: _id_sort_key(str(item[0]))):
        if str(node.class_type) not in RESOLVABLE_HELPER_CLASS_TYPES:
            continue
        metadata = getattr(node, "metadata", {})
        provenance = metadata.get("provenance") if isinstance(metadata, Mapping) else None
        record: dict[str, Any] = {
            "id": str(node_id),
            "uid": str(node.uid),
            "class_type": str(node.class_type),
        }
        safe_provenance = _v2_custody_provenance(provenance)
        if safe_provenance is not None:
            record["provenance"] = safe_provenance
        for field in ("pos", "size"):
            pair = position_pair(getattr(node, field, None))
            if pair is None and isinstance(metadata, Mapping):
                ui_record = metadata.get("_ui")
                if isinstance(ui_record, Mapping):
                    pair = position_pair(ui_record.get(field))
            if pair is not None:
                record[field] = pair
        native_ports = {
            "native_input_names": copy.deepcopy(node.native_input_names),
            "native_output_names": copy.deepcopy(node.native_output_names),
            "native_input_types": copy.deepcopy(node.native_input_types),
            "native_output_types": copy.deepcopy(node.native_output_types),
            "native_input_optional": copy.deepcopy(node.native_input_optional),
            "native_input_asset_kinds": copy.deepcopy(node.native_input_asset_kinds),
            "native_output_slots": copy.deepcopy(node.native_output_slots),
        }
        if any(value is not None for value in native_ports.values()):
            record["native_ports"] = native_ports
        records.append(record)
    # A v2 rebuild removes UI-only/value helpers from the executable node
    # roster, but finalize() has already retained their source-backed custody
    # in metadata.  Merge both witnesses so a second publication cannot turn
    # a four-helper source into an empty companion.  Identity conflicts are a
    # refusal, never a last-write-wins repair.
    metadata = getattr(workflow, "metadata", {})
    retained = metadata.get("resolver_helper_custody") if isinstance(metadata, Mapping) else None
    if isinstance(retained, (list, tuple)):
        records.extend(copy.deepcopy(dict(item)) for item in retained if isinstance(item, Mapping))
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    by_id: dict[str, tuple[str, str]] = {}
    by_uid: dict[str, tuple[str, str]] = {}
    for record in records:
        identity = (str(record.get("id")), str(record.get("uid")))
        prior_id = by_id.get(identity[0])
        prior_uid = by_uid.get(identity[1])
        if prior_id is not None and prior_id != identity:
            raise ValueError(f"conflicting helper custody id {identity[0]!r}")
        if prior_uid is not None and prior_uid != identity:
            raise ValueError(f"conflicting helper custody uid {identity[1]!r}")
        by_id[identity[0]] = identity
        by_uid[identity[1]] = identity
        previous = by_identity.get(identity)
        if previous is None:
            by_identity[identity] = copy.deepcopy(record)
            continue
        merged = copy.deepcopy(previous)
        for field, value in record.items():
            if field in merged and merged[field] != value:
                raise ValueError(f"conflicting helper custody for identity {identity!r}")
            merged.setdefault(field, copy.deepcopy(value))
        by_identity[identity] = merged
    return [
        by_identity[key]
        for key in sorted(by_identity, key=lambda item: (item[0], item[1]))
    ]


def _recursive_constructor_custody(source: Any) -> Any:
    """Return structural recursive custody for the v2 companion.

    Recursive constructor products remain the editable/value authority.  This
    companion witness contains only the definition boundary roster and the
    stable constructor identities needed to materialize those products after a
    clean source rebuild; it intentionally contains no node values or links.
    """
    from vibecomfy.identity.scope import sg_key
    from vibecomfy.ingest.normalize import canonical_definition_nodes

    def entries(value: Any) -> list[Any]:
        if isinstance(value, Mapping) and "subgraphs" in value:
            return list(value["subgraphs"])
        if isinstance(value, Mapping):
            return list(value.values())
        return list(value) if isinstance(value, (list, tuple)) else []

    def roster(value: Any) -> Any:
        if not isinstance(value, (list, tuple)):
            return None
        result: list[Any] = []
        for item in value:
            if not isinstance(item, Mapping):
                result.append(item)
                continue
            result.append({
                **{
                    key: copy.deepcopy(item[key])
                    for key in ("name", "type", "slot")
                    if key in item
                },
                "_has_link": "link" in item,
                "_has_value": "value" in item,
            })
        return result

    def records(definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        raw_nodes = canonical_definition_nodes(definition)
        values = raw_nodes.values() if isinstance(raw_nodes, Mapping) else raw_nodes
        if not isinstance(values, (list, tuple)):
            raise ValueError("recursive_definition_nodes_malformed: nodes must be a sequence or mapping")
        result: list[dict[str, Any]] = []
        for index, raw in enumerate(values):
            if not isinstance(raw, Mapping):
                raise ValueError("recursive_definition_nodes_malformed: node must be a mapping")
            node_id = str(raw.get("uid") or raw.get("id") or f"node_{index}")
            class_type = str(raw.get("class_type", raw.get("type", "")))
            if not class_type:
                raise ValueError(f"recursive_definition_nodes_malformed: node {node_id!r} has no class type")
            raw_inputs = raw.get("inputs")
            raw_outputs = raw.get("outputs")
            row: dict[str, Any] = {
                "id": node_id,
                "uid": raw.get("uid"),
                "class_type": class_type,
                "node_field": "type" if "type" in raw and "class_type" not in raw else "class_type",
                "input_shape": roster(raw_inputs),
                "output_shape": roster(raw_outputs),
            }
            for field in (
                "native_input_names", "native_output_names", "native_input_types",
                "native_output_types", "native_input_optional", "native_input_asset_kinds",
                "native_output_slots",
            ):
                if field in raw:
                    row[field] = copy.deepcopy(raw[field])
            result.append(row)
        return result

    def build(definition: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(definition, Mapping):
            raise ValueError("recursive definition entries must be mappings")
        # Only the readable identity label crosses into the companion.  The
        # constructor roster below is the structural witness; source nodes,
        # links, values, layout, and arbitrary vendor payload stay in the
        # executed constructors or the presentation sidecar.
        result = {
            str(key): copy.deepcopy(definition[key])
            for key in ("id", "name")
            if key in definition
        }
        result["_scope_key"] = sg_key(definition)
        ordered = records(definition)
        result["_constructor_nodes"] = ordered
        nested = definition.get("definitions")
        if nested not in (None, {}, []):
            result["definitions"] = {"subgraphs": [
                build(item) for item in entries(nested) if isinstance(item, Mapping)
            ]}
        return result

    if source in (None, {}, []):
        return None
    return {"subgraphs": [build(item) for item in entries(source) if isinstance(item, Mapping)]}


def _recursive_scope_custody(source: Any) -> list[dict[str, Any]]:
    """Project structural recursive custody into the v2 scope roster."""
    from vibecomfy.identity.scope import compose_scope_path

    scopes: list[dict[str, Any]] = []

    def walk(value: Any, parents: tuple[str, ...]) -> None:
        for definition in value.get("subgraphs", []) if isinstance(value, Mapping) and isinstance(value.get("subgraphs"), list) else ():
            if not isinstance(definition, Mapping):
                continue
            key = str(definition.get("_scope_key"))
            scope_path = compose_scope_path((*parents, key))
            nodes: list[dict[str, Any]] = []
            for record in definition.get("_constructor_nodes", ()):
                if not isinstance(record, Mapping):
                    continue
                node_id = str(record.get("id"))
                node = {
                    "label": node_id,
                    "id": node_id,
                    "uid": str(record.get("uid") or node_id),
                    "class_type": str(record.get("class_type")),
                }
                native_ports = {
                    field: copy.deepcopy(record[field])
                    for field in (
                        "native_input_names", "native_output_names", "native_input_types",
                        "native_output_types", "native_input_optional", "native_input_asset_kinds",
                        "native_output_slots",
                    )
                    if field in record
                }
                if native_ports:
                    node["native_ports"] = native_ports
                nodes.append(node)
            scopes.append({"scope_path": scope_path, "nodes": nodes, "helpers": []})
            walk(definition.get("definitions"), (*parents, key))

    walk(source, ())
    return scopes


_V2_CUSTODY_PROVENANCE_KEYS = frozenset({
    "source_path", "source_id", "source_type", "source_workflow_path", "source_ref",
    "source_kind", "indexed_id", "workflow_source_id", "workflow_source_type",
    "raw_workflow_shape", "source_hash", "workflow_shape", "output_mode",
})
_V2_CUSTODY_SHAPE_KEYS = frozenset({
    "nodes", "runtime_nodes", "helper_nodes", "edges", "inputs", "outputs",
})
_V2_CUSTODY_SCHEMA_KEYS = frozenset({
    "provider", "path", "cache_path", "server_url", "package", "version", "hash", "confidence",
})


def _v2_custody_provenance(value: Any) -> Any:
    """Keep only the closed provenance witness accepted by the v2 companion."""
    if isinstance(value, str):
        return value if value.strip() else None
    if not isinstance(value, Mapping):
        return None
    if any(str(key) not in _V2_CUSTODY_PROVENANCE_KEYS for key in value):
        return None
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"workflow_shape", "raw_workflow_shape"}:
            if not isinstance(item, Mapping) or any(
                str(shape_key) not in _V2_CUSTODY_SHAPE_KEYS
                or type(shape_value) is not int
                or shape_value < 0
                for shape_key, shape_value in item.items()
            ):
                return None
            result[str(key)] = {
                str(shape_key): int(shape_value)
                for shape_key, shape_value in item.items()
            }
        elif isinstance(item, (Mapping, list, tuple)):
            return None
        else:
            result[str(key)] = copy.deepcopy(item)
    return result


def _v2_custody_metadata(
    metadata: Any,
    allowed_metadata: tuple[str, ...],
) -> dict[str, Any]:
    """Project node metadata into the closed, non-runtime v2 custody shape."""
    if not isinstance(metadata, Mapping):
        return {}
    result: dict[str, Any] = {}
    for key in allowed_metadata:
        if key not in metadata:
            continue
        value = metadata[key]
        if key == "provenance":
            safe = _v2_custody_provenance(value)
            if safe is not None:
                result[key] = safe
        elif key == "schema_source":
            if isinstance(value, Mapping) and not any(
                str(source_key) not in _V2_CUSTODY_SCHEMA_KEYS
                or isinstance(source_value, (Mapping, list, tuple))
                for source_key, source_value in value.items()
            ):
                result[key] = copy.deepcopy(dict(value))
        # Native type/name rosters are already represented in native_ports.
        # Keeping the list-valued metadata copies would duplicate authority
        # and rejects nested provider shapes such as per-input type lists.
        elif key in {"input_types", "output_types"}:
            continue
        elif isinstance(value, Mapping):
            continue
        elif isinstance(value, (list, tuple)) and any(
            isinstance(item, (Mapping, list, tuple)) for item in value
        ):
            continue
        else:
            result[key] = copy.deepcopy(value)
    return result


def _format_helper_custody(custody: list[dict[str, Any]]) -> list[str]:
    plain = _plain_canonical_value(copy.deepcopy(custody))
    return _format_metadata_dict("HELPER_CUSTODY", plain).splitlines()


def _canonical_widget_channels(
    node: Any,
    name_authority: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Map constructor field names back to their authored widget channel."""
    from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node

    # ``_ui`` is presentation/provenance evidence, never naming authority for
    # generated Python.  A detached copy keeps the importer-owned metadata
    # available to the custody manifest while preventing UI aliases from
    # changing the canonical widget roster used by the emitter.
    semantic_node = node
    metadata = getattr(node, "metadata", None)
    if isinstance(metadata, Mapping) and "_ui" in metadata:
        semantic_node = copy.deepcopy(node)
        semantic_node.metadata.pop("_ui", None)
    resolution = compact_widget_names_for_node(
        semantic_node,
        str(semantic_node.class_type),
        name_authority=name_authority,
    )
    aliases = list(resolution.names)
    result: dict[str, str] = {}
    for authored_name in semantic_node.widgets:
        constructed_name = str(authored_name)
        if constructed_name.startswith("widget_"):
            resolved = resolve_widget_key_with_provenance(
                str(semantic_node.class_type),
                constructed_name,
                input_aliases=aliases or None,
            ).name
            if resolved is None:
                continue
            constructed_name = resolved
        existing = result.get(constructed_name)
        if existing is not None and existing != str(authored_name):
            raise ValueError(
                "ambiguous_authored_channel: "
                f"{semantic_node.class_type}.{constructed_name} maps to both {existing!r} "
                f"and {authored_name!r}"
            )
        result[constructed_name] = str(authored_name)
    return result


def _exceptional_authored_channels(
    node: Any,
    edges_in: Mapping[str, list[Any]],
    name_authority: Mapping[str, Any] | None,
) -> dict[str, tuple[str, Any, bool, Any]]:
    """Return widget channels shadowed by a distinct effective input channel."""
    channels = _canonical_widget_channels(node, name_authority)
    incoming_fields = {
        str(edge.to_input) for edge in edges_in.get(str(node.id), ())
    }
    input_fields = set(node.inputs) | incoming_fields
    exceptional: dict[str, tuple[str, Any, bool, Any]] = {}
    for constructed_name, authored_name in channels.items():
        if constructed_name not in input_fields:
            continue
        value = node.widgets.get(authored_name)
        if _is_link(value):
            raise ValueError(
                "ambiguous_authored_channel: linked widget shadow for "
                f"{node.class_type}.{constructed_name} cannot be represented once"
            )
        exceptional[constructed_name] = (
            authored_name,
            copy.deepcopy(value),
            constructed_name in incoming_fields and constructed_name in node.inputs,
            copy.deepcopy(node.inputs.get(constructed_name)),
        )
    return exceptional


def _format_authored_channel(
    effective_expr: str,
    record: tuple[str, Any, bool, Any],
) -> str:
    authored_name, widget_value, retain_input_default, input_default = record
    extras = ""
    if retain_input_default:
        if input_default == widget_value:
            extras = ", retain_input_default=True"
        else:
            extras = f", input_default={_format_value(input_default)}"
    return (
        f"authored_channel({effective_expr}, widget={_format_value(widget_value)}, "
        f"name={authored_name!r}{extras})"
    )


def _format_canonical_custody(custody: Mapping[str, Any]) -> list[str]:
    plain = _plain_canonical_value(copy.deepcopy(dict(custody)))
    return _format_metadata_dict("CANONICAL_CUSTODY", plain).splitlines()


def _canonical_outputs_expr(
    workflow: Any,
    var_names: Mapping[str, str],
) -> str:
    records: list[str] = []
    for item in workflow.outputs:
        node_id = str(item.node_id)
        binding = var_names.get(node_id)
        if binding is None:
            raise ValueError(
                f"public output {node_id!r} does not survive canonical execution projection"
            )
        fields = {
            "output_type": item.output_type,
            "name": item.name,
            "artifact_kind": item.artifact_kind,
            "mime_type": item.mime_type,
            "filename_prefix": item.filename_prefix,
            "expected_cardinality": item.expected_cardinality,
        }
        parts = [f"'node': {binding}"]
        parts.extend(f"{key!r}: {_format_value(value)}" for key, value in fields.items())
        records.append("{" + ", ".join(parts) + "}")
    return "[" + ", ".join(records) + "]"


def _v2_output_args(
    workflow: Any,
    var_names: Mapping[str, str],
    metadata: Mapping[str, Any],
) -> str:
    """Render the concise typed output declaration for a v2 source."""
    outputs = list(workflow.outputs)
    if not outputs:
        return ", outputs=[]"

    def binding(item: Any) -> str:
        value = var_names.get(str(item.node_id))
        if value is None:
            raise ValueError(
                f"public output {item.node_id!r} does not survive canonical execution projection"
            )
        return value

    if len(outputs) == 1:
        item = outputs[0]
        node = workflow.nodes.get(str(item.node_id))
        derived_kind = None
        if node is not None:
            from vibecomfy.templates import _derive_output_kind

            derived_kind = _derive_output_kind(str(node.class_type))
        if (
            node is not None
            and _is_output_class(str(node.class_type))
            and item.output_type == str(node.class_type)
            and item.name is None
            and item.artifact_kind == derived_kind
            and item.mime_type is None
            # wf.finalize(..., output_node=...) injects READY_METADATA's
            # output_prefix.  Compact only when that is already the exact
            # declared value; an explicit null prefix must remain an
            # OutputSpec rather than acquire inferred metadata on rebuild.
            and item.filename_prefix == metadata.get("output_prefix")
            and item.expected_cardinality is None
        ):
            return f", output_node={binding(item)}"
        if (
            node is not None
            and item.output_type == str(node.class_type)
            and item.name is None
            and item.artifact_kind is None
            and item.mime_type is None
            and item.filename_prefix is None
            and item.expected_cardinality is None
        ):
            # Preserve an explicit null artifact kind without expanding the
            # declaration into an importer-shaped record.  ``output_node``
            # intentionally infers an artifact kind, so this typed minimum is
            # the lossless concise form for legacy/opaque outputs.
            return f", outputs=[OutputSpec(node={binding(item)})]"

    records: list[str] = []
    for item in outputs:
        fields = (
            ("output_type", item.output_type),
            ("name", item.name),
            ("artifact_kind", item.artifact_kind),
            ("mime_type", item.mime_type),
            ("filename_prefix", item.filename_prefix),
            ("expected_cardinality", item.expected_cardinality),
        )
        args = [f"node={binding(item)}"]
        # None is the typed OutputSpec default.  Omitting it keeps a
        # multi-output finalizer readable without changing its semantics.
        args.extend(
            f"{name}={_format_value(value)}"
            for name, value in fields
            if value is not None
        )
        records.append(f"OutputSpec({', '.join(args)})")
    if len(outputs) > 1:
        return ", outputs=[\n        " + ",\n        ".join(records) + ",\n    ]"
    return ", outputs=[" + records[0] + "]"


def _plain_canonical_value(value: Any) -> Any:
    """Lower semantic values to deterministic Python literals."""
    if isinstance(value, Enum):
        return _plain_canonical_value(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): _plain_canonical_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_plain_canonical_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_plain_canonical_value(item) for item in value)
    return value


def _merge_definition_wrapper_imports(
    imports: Mapping[str, list[str]], definitions: Any
) -> dict[str, list[str]]:
    """Add public wrapper imports required by IR-owned definition-local nodes."""
    from types import SimpleNamespace

    nodes: dict[str, Any] = {}

    def walk(value: Any, prefix: str) -> None:
        if not isinstance(value, Mapping):
            return
        entries = canonical_definition_nodes(value)
        if isinstance(entries, (list, tuple)):
            for index, raw in enumerate(entries):
                if not isinstance(raw, Mapping):
                    continue
                class_type = raw.get("class_type", raw.get("type"))
                if class_type:
                    nodes[f"{prefix}:{index}"] = SimpleNamespace(class_type=str(class_type))
        nested = value.get("definitions")
        if isinstance(nested, Mapping):
            children = nested.get("subgraphs", nested.values())
        else:
            children = nested
        if isinstance(children, (list, tuple)):
            for index, child in enumerate(children):
                walk(child, f"{prefix}/{index}")

    if isinstance(definitions, Mapping):
        entries = definitions.get("subgraphs", definitions.values())
    else:
        entries = definitions
    if isinstance(entries, (list, tuple)):
        for index, definition in enumerate(entries):
            walk(definition, str(index))
    additions = _wrapper_imports_for_nodes(nodes)
    merged = {module: sorted(names) for module, names in imports.items()}
    for module, names in additions.items():
        merged[module] = sorted({*merged.get(module, []), *names})
    return merged


def _canonical_definition_helpers(
    definitions: Any,
    *,
    interfaces: Mapping[str, Any] | None = None,
    boundary_ports: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    external_custody: bool = False,
) -> tuple[list[str], str | None]:
    """Render the authoritative recursive constructor helpers.

    Definition-local values are lowered through the same constructor kernel as
    root nodes.  The returned expression is a helper call so editing a helper
    body changes the rebuilt definition rather than being shadowed by a
    detached replay literal.
    """
    if definitions in (None, {}, []):
        return [], None

    from vibecomfy.identity.scope import compose_scope_path, sg_key

    lines: list[str] = []
    used_names: set[str] = set()
    active_definition_ids: set[int] = set()
    interface_map = dict(interfaces or {}) if isinstance(interfaces, Mapping) else {}

    def entries(source: Any) -> list[Any]:
        if isinstance(source, Mapping):
            if "subgraphs" in source:
                values = source["subgraphs"]
                if not isinstance(values, (list, tuple)):
                    raise ValueError("recursive definitions 'subgraphs' must be a list")
                return list(values)
            return list(source.values())
        if isinstance(source, (list, tuple)):
            return list(source)
        raise ValueError("recursive definitions must be a JSON-shaped mapping or sequence")

    # Index structural identities before emitting source so malformed boundary
    # records fail closed instead of becoming an ordinal/short-prefix fallback.
    known_scopes: set[str] = set()
    definitions_by_alias: dict[str, tuple[Mapping[str, Any], tuple[str, ...]]] = {}
    indexing_definition_ids: set[int] = set()

    def index_definition(definition: Any, parents: tuple[str, ...]) -> None:
        if not isinstance(definition, Mapping):
            raise ValueError("recursive definition entries must be mappings")
        identity = id(definition)
        if identity in indexing_definition_ids:
            raise ValueError("recursive_definition_cycle: definition object graph contains a cycle")
        indexing_definition_ids.add(identity)
        try:
            key = sg_key(definition)
            supplied_key = definition.get("sg_key")
            if supplied_key is not None and str(supplied_key) != key:
                raise ValueError(
                    f"definition sg_key {supplied_key!r} does not match structural identity {key!r}"
                )
            scope = compose_scope_path((*parents, key))
            known_scopes.update((key, scope))
            definitions_by_alias[key] = (definition, (*parents, key))
            if definition.get("id") is not None:
                definitions_by_alias.setdefault(str(definition["id"]), (definition, (*parents, key)))
            nested = definition.get("definitions")
            for child in entries(nested) if nested not in (None, {}, []) else ():
                index_definition(child, (*parents, key))
        finally:
            indexing_definition_ids.remove(identity)

    top_entries = entries(definitions)
    for definition in top_entries:
        index_definition(definition, ())

    if boundary_ports is not None:
        if not isinstance(boundary_ports, (list, tuple)):
            raise ValueError("boundary_port_malformed: boundary_ports must be a sequence")
        seen_boundaries: set[tuple[str, str, str]] = set()
        for port in boundary_ports:
            if not isinstance(port, Mapping):
                raise ValueError("boundary_port_malformed: each boundary port must be a mapping")
            scope = port.get("scope_path", port.get("scope"))
            name = port.get("name", port.get("interface", port.get("port_name")))
            direction = str(port.get("direction", "")).lower()
            if not isinstance(scope, str) or not scope or scope not in known_scopes:
                raise ValueError(f"boundary_port_malformed: unknown scope_path {scope!r}")
            if not isinstance(name, str) or not name.strip() or direction not in {"input", "output"}:
                raise ValueError(f"boundary_port_malformed: invalid boundary port {port!r}")
            key = (scope, name, direction)
            if key in seen_boundaries:
                raise ValueError(f"boundary_port_malformed: duplicate boundary port {key!r}")
            seen_boundaries.add(key)

    def interface_members(key: str, scope: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        raw = interface_map.get(key, interface_map.get(scope))
        if raw is None:
            return [], []
        if isinstance(raw, Mapping):
            raw_inputs, raw_outputs = raw.get("inputs", ()), raw.get("outputs", ())
            if not isinstance(raw_inputs, (list, tuple)) or not isinstance(raw_outputs, (list, tuple)):
                raise ValueError(f"interface_malformed: interface {key!r} inputs/outputs must be sequences")
            inputs = list(raw_inputs)
            outputs = list(raw_outputs)
        elif isinstance(raw, (list, tuple)):
            inputs = [item for item in raw if isinstance(item, Mapping) and str(item.get("direction", "")).lower() == "input"]
            outputs = [item for item in raw if isinstance(item, Mapping) and str(item.get("direction", "")).lower() == "output"]
        else:
            raise ValueError(f"interface_malformed: interface {key!r} must be a mapping or sequence")
        for direction, members in (("input", inputs), ("output", outputs)):
            names: set[str] = set()
            for member in members:
                if not isinstance(member, Mapping) or not isinstance(member.get("name"), str) or not member.get("name"):
                    raise ValueError(f"interface_malformed: interface {key!r} {direction} member is invalid")
                if member["name"] in names:
                    raise ValueError(f"interface_duplicate: interface {key!r} {direction} member {member['name']!r}")
                names.add(member["name"])
        if boundary_ports is not None:
            for member, direction in [(item, "input") for item in inputs] + [(item, "output") for item in outputs]:
                matches = [
                    port for port in boundary_ports
                    if isinstance(port, Mapping)
                    and str(port.get("scope_path", port.get("scope"))) in {key, scope}
                    and str(port.get("name", port.get("interface", port.get("port_name")))) == member["name"]
                    and str(port.get("direction", "")).lower() == direction
                ]
                if len(matches) != 1:
                    raise ValueError(
                        f"boundary_port_unbound: interface {key!r} {direction} {member['name']!r} must bind exactly once"
                    )
        return inputs, outputs

    def render(value: Any) -> str:
        return _format_value(_plain_canonical_value(copy.deepcopy(value)))

    def identifier(scope_path: str) -> str:
        slug = "".join(char if char.isalnum() else "_" for char in scope_path).strip("_")
        name = f"_definition_{slug or 'anonymous'}"
        if name in used_names:
            raise ValueError(
                f"duplicate recursive definition helper identity for {scope_path!r}"
            )
        used_names.add(name)
        return name

    def constructor_custody(source: Any) -> Any:
        """Retain shape/identity custody, leaving values to constructors."""
        def structural_roster(value: Any) -> Any:
            if not isinstance(value, (list, tuple)):
                return None
            return [
                {
                    **{key: copy.deepcopy(item[key]) for key in ("name", "type", "slot") if key in item},
                    "_has_link": "link" in item,
                    "_has_value": "value" in item,
                }
                if isinstance(item, Mapping) else item
                for item in value
            ]

        if isinstance(source, Mapping):
            if "subgraphs" in source:
                return {"subgraphs": [constructor_custody(item) for item in entries(source["subgraphs"])]}
            result = {
                str(key): copy.deepcopy(source[key])
                for key in ("id", "name")
                if key in source
            }
            result["_scope_key"] = sg_key(source)
            records = node_records(source)
            local_links = link_records(source, records)
            deps = {item["id"]: set() for item in records}
            for origin, _slot, target, _field in local_links:
                if origin in deps and target in deps:
                    deps[target].add(origin)
            ordered_records: list[dict[str, Any]] = []
            remaining = list(records)
            while remaining:
                ready = [item for item in remaining if not (deps[item["id"]] & {other["id"] for other in remaining})]
                if not ready:
                    raise ValueError("recursive_definition_links_malformed: cyclic local topology")
                ordered_records.extend(ready)
                remaining = [item for item in remaining if item not in ready]
            records = ordered_records
            result["_constructor_nodes"] = [
                {
                    **{
                        "id": item["id"],
                        "uid": item.get("uid"),
                        "class_type": item["class_type"],
                        "node_field": item.get("node_field", "class_type"),
                        "input_shape": structural_roster(item.get("input_shape")),
                        "output_shape": structural_roster(item.get("output_shape")),
                    },
                    **{
                        field: copy.deepcopy(item[field])
                        for field in (
                            "native_input_names", "native_output_names", "native_input_types",
                            "native_output_types", "native_input_optional", "native_input_asset_kinds",
                            "native_output_slots",
                        )
                        if field in item
                    },
                }
                for item in records
            ]
            nested = source.get("definitions")
            if nested not in (None, {}, []):
                result["definitions"] = {
                    "subgraphs": [constructor_custody(item) for item in entries(nested)]
                }
            return result
        if isinstance(source, (list, tuple)):
            return [constructor_custody(item) for item in source]
        return copy.deepcopy(source)

    def safe_name(value: Any, fallback: str) -> str:
        candidate = "".join(char if char.isalnum() else "_" for char in str(value or ""))
        candidate = candidate.strip("_") or fallback
        if candidate[0].isdigit():
            candidate = f"_{candidate}"
        return candidate

    def type_hint(member: Mapping[str, Any]) -> str:
        return {"INT": "int", "FLOAT": "float", "STRING": "str", "BOOLEAN": "bool"}.get(
            str(member.get("type") or "").upper(), "Any"
        )

    def capture_placeholder(member: Mapping[str, Any]) -> str:
        """Return a type-safe temporary value for recursive capture only."""
        member_type = str(member.get("type") or "").upper()
        if member_type in {"STRING", "COMBO"}:
            return repr("capture")
        if member_type == "INT":
            return "0"
        if member_type == "FLOAT":
            return "0.0"
        if member_type == "BOOLEAN":
            return "False"
        return "None"

    def node_records(definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        raw_nodes = canonical_definition_nodes(definition)
        raw_entries = raw_nodes.values() if isinstance(raw_nodes, Mapping) else raw_nodes
        if not isinstance(raw_entries, (list, tuple)):
            raise ValueError("recursive_definition_nodes_malformed: nodes must be a sequence or mapping")
        records: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_entries):
            if not isinstance(raw, Mapping):
                raise ValueError("recursive_definition_nodes_malformed: node must be a mapping")
            node_id = str(raw.get("uid") or raw.get("id") or f"node_{index}")
            class_type = str(raw.get("class_type", raw.get("type", "")))
            if not class_type:
                raise ValueError(f"recursive_definition_nodes_malformed: node {node_id!r} has no class type")
            values: dict[str, Any] = {}
            raw_inputs = raw.get("inputs", {})
            if isinstance(raw_inputs, Mapping):
                values.update({str(key): value for key, value in raw_inputs.items()})
            elif isinstance(raw_inputs, (list, tuple)):
                for item in raw_inputs:
                    if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
                        raise ValueError(f"recursive_definition_nodes_malformed: node {node_id!r} has invalid input row")
                    if item.get("link") is None:
                        values[str(item["name"])] = item.get("value")
            else:
                raise ValueError(f"recursive_definition_nodes_malformed: node {node_id!r} inputs are invalid")
            if isinstance(raw.get("widgets"), Mapping):
                for key, value in raw["widgets"].items():
                    values.setdefault(str(key), value)
            raw_widget_values = canonical_node_widgets_values(raw)
            primitive_classes = {
                "PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt",
                "PrimitiveString", "PrimitiveStringMultiline",
            }
            if class_type in primitive_classes:
                if isinstance(raw_widget_values, Mapping):
                    for key, value in raw_widget_values.items():
                        values.setdefault(str(key), copy.deepcopy(value))
                elif isinstance(raw_widget_values, (list, tuple)):
                    widget_names = WIDGET_SCHEMA.get(class_type, ())
                    for widget_name, value in zip(widget_names, raw_widget_values):
                        if isinstance(widget_name, str):
                            values.setdefault(widget_name, copy.deepcopy(value))
            input_shape = copy.deepcopy(raw_inputs) if isinstance(raw_inputs, (list, tuple)) else None
            if isinstance(input_shape, list):
                for item in input_shape:
                    if not isinstance(item, Mapping):
                        continue
                    field = item.get("name")
                    if (
                        isinstance(field, str)
                        and item.get("link") is None
                        and "value" not in item
                        and field in values
                    ):
                        item["value"] = copy.deepcopy(values[field])
            widget_channels = (
                {str(key): copy.deepcopy(value) for key, value in raw["widgets"].items()}
                if isinstance(raw.get("widgets"), Mapping) else {}
            )
            raw_outputs = raw.get("outputs")
            outputs = tuple(
                str(item.get("name", item.get("slot", index)))
                if isinstance(item, Mapping) else str(item)
                for index, item in enumerate(raw_outputs)
            ) if isinstance(raw_outputs, (list, tuple)) else ()
            # Normalization adds ``class_type`` to legacy ``type`` rows.  A
            # surviving type key is therefore the strongest authored spelling
            # witness for the emitted definition source.
            node_field = "type" if "type" in raw and "class_type" not in raw else "class_type"
            record = {"id": node_id, "class_type": class_type, "node_field": node_field, "uid": raw.get("uid"), "values": values, "widget_channels": widget_channels, "outputs": outputs,
                      "input_shape": input_shape,
                      "output_shape": copy.deepcopy(raw_outputs) if isinstance(raw_outputs, (list, tuple)) else None}
            for field in (
                "native_input_names", "native_output_names", "native_input_types",
                "native_output_types", "native_input_optional", "native_input_asset_kinds",
                "native_output_slots",
            ):
                if field in raw:
                    record[field] = raw[field]
            records.append(record)
        return records

    def link_records(definition: Mapping[str, Any], records: list[dict[str, Any]]) -> list[tuple[str, str, str, str]]:
        links: list[tuple[str, str, str, str]] = []
        raw_links = canonical_definition_links(definition)
        if not isinstance(raw_links, (list, tuple)):
            raise ValueError("recursive_definition_links_malformed: links must be a sequence")
        for link in raw_links:
            if isinstance(link, Mapping):
                source = link.get("from_node", link.get("origin_id"))
                slot = link.get("from_output", link.get("origin_slot", 0))
                target = link.get("to_node", link.get("target_id"))
                field = link.get("to_input", link.get("target_slot"))
            elif isinstance(link, (list, tuple)) and len(link) >= 5:
                source, slot, target, field = link[1], link[2], link[3], link[4]
            else:
                raise ValueError(f"recursive_definition_links_malformed: invalid link {link!r}")
            if source is None or target is None or field is None:
                raise ValueError(f"recursive_definition_links_malformed: incomplete link {link!r}")
            target_record = next((item for item in records if item["id"] == str(target)), None)
            if target_record is not None and isinstance(target_record.get("input_shape"), (list, tuple)) and str(field).isdigit():
                target_inputs = target_record["input_shape"]
                target_index = int(field)
                if 0 <= target_index < len(target_inputs) and isinstance(target_inputs[target_index], Mapping):
                    field = target_inputs[target_index].get("name", field)
            links.append((str(source), str(slot), str(target), str(field)))
        return links

    def walk(definition: Any, parents: tuple[str, ...]) -> str:
        if not isinstance(definition, Mapping):
            raise ValueError("recursive definition entries must be mappings")
        identity = id(definition)
        if identity in active_definition_ids:
            raise ValueError("recursive_definition_cycle: definition object graph contains a cycle")
        active_definition_ids.add(identity)
        key = sg_key(definition)
        supplied_key = definition.get("sg_key")
        if supplied_key is not None and str(supplied_key) != key:
            raise ValueError(
                f"definition sg_key {supplied_key!r} does not match structural identity {key!r}"
            )
        scope_path = compose_scope_path((*parents, key))
        nested = definition.get("definitions")
        nested_entries = entries(nested) if nested not in (None, {}, []) else []
        try:
            child_names = [walk(item, (*parents, key)) for item in nested_entries]
            function_name = identifier(scope_path)
            input_members, output_members = interface_members(key, scope_path)
            parameter_names: dict[str, str] = {}
            used_parameters = {"wf"}
            signature_parts = ["wf: VibeWorkflow"]
            for index, member in enumerate(input_members):
                source_name = str(member["name"])
                parameter = safe_name(source_name, f"input_{index}")
                while parameter in used_parameters:
                    parameter += "_"
                used_parameters.add(parameter)
                parameter_names[source_name] = parameter
                signature_parts.append(f"{parameter}: {type_hint(member)}")
            if len(output_members) == 0:
                return_hint = "None"
            elif len(output_members) == 1:
                return_hint = type_hint(output_members[0])
            else:
                return_hint = "tuple[" + ", ".join(type_hint(item) for item in output_members) + "]"
            lines.append(f"def {function_name}({', '.join(signature_parts)}) -> {return_hint}:")
            lines.append(f"    \"\"\"Typed recursive definition {key}.\"\"\"")
            records = node_records(definition)
            local_vars: dict[str, str] = {}
            captured_vars: list[str] = []
            child_by_alias = {
                alias: (child, child_names[index])
                for index, child in enumerate(nested_entries)
                for alias in {str(child.get("id")), sg_key(child)}
            }
            boundary_inputs = {
                (
                    str(port.get("node_uid")),
                    str(port.get("field")),
                ): parameter_names.get(str(port.get("name")), "")
                for port in (boundary_ports or ())
                if isinstance(port, Mapping)
                and str(port.get("scope_path", port.get("scope"))) in {key, scope_path}
                and str(port.get("direction", "")).lower() == "input"
            }
            local_link_values = {
                (target, field): (source, slot)
                for source, slot, target, field in link_records(definition, records)
            }
            # Normalization orders authored definition nodes by identity, not
            # execution dependency.  Constructor handles must nevertheless be
            # bound only after their source variable exists.
            local_edges = link_records(definition, records)
            dependencies = {record["id"]: set() for record in records}
            for source, _slot, target, _field in local_edges:
                if source in dependencies and target in dependencies:
                    dependencies[target].add(source)
            ordered: list[dict[str, Any]] = []
            remaining = list(records)
            while remaining:
                ready = [record for record in remaining if not (dependencies[record["id"]] & {item["id"] for item in remaining})]
                if not ready:
                    raise ValueError("recursive_definition_links_malformed: cyclic local topology")
                ordered.extend(ready)
                remaining = [record for record in remaining if record not in ready]
            records = ordered
            for index, record in enumerate(records):
                node_id = record["id"]
                var = safe_name(node_id, f"local_{index}")
                while var in local_vars.values() or var == "wf":
                    var += "_"
                local_vars[node_id] = var
                class_type = record["class_type"]
                child = child_by_alias.get(class_type)
                if child is not None:
                    child_def, child_function = child
                    child_inputs, _child_outputs = interface_members(sg_key(child_def), compose_scope_path((*parents, key, sg_key(child_def))))
                    child_args = [parameter_names.get(str(item.get("name")), "None") for item in child_inputs]
                    lines.append(f"    {var} = {child_function}(wf{', ' if child_args else ''}{', '.join(child_args)})")
                    captured_vars.append(var)
                    continue
                wrapper = _wrapper_symbol_for_class(class_type) if _wrapper_module_for_class(class_type) else None
                call_name = wrapper or "raw_call"
                args = [] if wrapper else [repr(class_type)]
                if not wrapper:
                    args.append("pass_raw=True")
                    if record.get("outputs"):
                        args.append(f"_outputs={render(record['outputs'])}")
                if isinstance(record.get("input_shape"), (list, tuple)):
                    shaped_fields = [
                        (str(item.get("name")), item.get("value"))
                        for item in record["input_shape"]
                        if isinstance(item, Mapping) and isinstance(item.get("name"), str)
                    ]
                    shaped_names = {field for field, _value in shaped_fields}
                    authored_fields = shaped_fields + [
                        (field, value)
                        for field, value in record["values"].items()
                        if field not in shaped_names
                    ]
                else:
                    authored_fields = list(record["values"].items())
                for field, value in authored_fields:
                    parameter = boundary_inputs.get((node_id, field))
                    if parameter:
                        value_expr = parameter
                    elif (node_id, field) in local_link_values:
                        source, slot = local_link_values[(node_id, field)]
                        source_var = local_vars.get(source)
                        if source_var is None:
                            raise ValueError(f"recursive_definition_links_malformed: unknown source {source!r}")
                        value_expr = f"{source_var}.out({int(slot) if str(slot).isdigit() else 0!r})"
                    elif isinstance(value, (list, tuple)) and len(value) >= 2 and isinstance(value[0], (str, int)) and isinstance(value[1], int):
                        continue
                    else:
                        value_expr = render(value)
                    if field in record.get("widget_channels", {}):
                        value_expr = (
                            f"authored_channel({value_expr}, "
                            f"widget={render(record['widget_channels'][field])}, "
                            f"name={field!r})"
                        )
                    if (
                        _keyword.iskeyword(field)
                        or not field.isidentifier()
                        or unicodedata.normalize("NFKC", field) != field
                    ):
                        args.append(f"**{{{field!r}: {value_expr}}}")
                    else:
                        args.append(f"{field}={value_expr}")
                lines.append(f"    {var} = {call_name}({', '.join(args)})")
                captured_vars.append(var)
            captured_expr = "(" + ", ".join(captured_vars) + (",)" if captured_vars else ")")
            lines.append(
                f"    wf._recursive_definition_captures.append(({scope_path!r}, "
                f"tuple(item for item in {captured_expr})))"
            )
            boundary_outputs = {
                str(port.get("name")): (str(port.get("node_uid")), str(port.get("field", "0")))
                for port in (boundary_ports or ())
                if isinstance(port, Mapping)
                and str(port.get("scope_path", port.get("scope"))) in {key, scope_path}
                and str(port.get("direction", "")).lower() == "output"
            }
            output_exprs: list[str] = []
            for member in output_members:
                output_name = str(member["name"])
                node_id, field = boundary_outputs.get(output_name, (None, None))
                if node_id is None or node_id not in local_vars:
                    raise ValueError(f"boundary_port_unbound: output {output_name!r} has no local node")
                var = local_vars[node_id]
                if node_id in {record["id"] for record in records if record["class_type"] in child_by_alias}:
                    child_def = next(record for record in records if record["id"] == node_id)
                    child_key = sg_key(next(item for item in nested_entries if str(item.get("id")) == child_def["class_type"] or sg_key(item) == child_def["class_type"]))
                    child_inputs, child_outputs = interface_members(child_key, compose_scope_path((*parents, key, child_key)))
                    slot = next((i for i, item in enumerate(child_outputs) if str(item.get("name")) == field), 0)
                    output_exprs.append(f"{var}[{slot}]" if len(child_outputs) != 1 else var)
                else:
                    output_slot = int(field) if str(field).isdigit() else 0
                    output_exprs.append(f"{var}.out({output_slot!r})")
            if not output_exprs:
                lines.append("    return None")
            elif len(output_exprs) == 1:
                lines.append(f"    return {output_exprs[0]}")
            else:
                lines.append("    return (" + ", ".join(output_exprs) + ",)")
            lines.append("")
            return function_name
        finally:
            active_definition_ids.remove(identity)

    if not top_entries:
        return [], None
    top_function_names = [walk(item, ()) for item in top_entries]
    if lines and lines[-1] == "":
        lines.pop()
    helper_name = "_build_recursive_definitions"
    custody_expr = (
        "wf._canonical_v2_recursive_custody"
        if external_custody
        else render(constructor_custody(definitions))
    )
    lines.extend([
        f"def {helper_name}(wf: VibeWorkflow) -> dict[str, Any]:",
        "    with recursive_definition_scope(wf):",
    ])
    for function_name, definition in zip(top_function_names, top_entries):
        key = sg_key(definition)
        input_members, _ = interface_members(key, key)
        args = ", ".join(capture_placeholder(member) for member in input_members)
        lines.append(f"        {function_name}(wf{', ' if args else ''}{args})")
    lines.extend([
        "        _definition_result = wf._materialize_recursive_definitions(",
        "            wf._recursive_definition_captures,",
        f"            {custody_expr},",
        "        )",
        "    return _definition_result",
        "",
    ])
    return lines, f"{helper_name}(wf)"


def _canonical_connection_lines(
    workflow: Any,
    *,
    retained_node_ids: set[str],
) -> list[str]:
    """Render authored edges whose endpoints survive canonical preparation."""
    return [
        f"wf.connect({f'{edge.from_node}.{edge.from_output}'!r}, "
        f"{f'{edge.to_node}.{edge.to_input}'!r})"
        for edge in workflow.edges
        if str(edge.from_node) in retained_node_ids
        and str(edge.to_node) in retained_node_ids
    ]


def _preflight_object_info_identity_resolution(workflow: Any) -> None:
    """Resolve bound object-info identities before default lookup can swallow errors."""
    from vibecomfy.porting.emitter import _identity_for_node  # noqa: PLC0415
    from vibecomfy.porting.object_info import resolve_class_entry  # noqa: PLC0415

    for node_id in sorted(workflow.nodes, key=str):
        node = workflow.nodes[node_id]
        identity = _identity_for_node(node)
        if identity is not None:
            resolve_class_entry(
                str(node.class_type), identity=identity, allow_class_fallback=True
            )


def _validate_named_output_edges(workflow: Any) -> None:
    """Reject edge references that would otherwise downgrade named outputs."""
    for edge in workflow.edges:
        source = workflow.nodes.get(str(edge.from_node))
        if source is None:
            continue
        # Native rosters are the authoritative socket contract.  Metadata is
        # only a fallback for older imported workflows that have not retained
        # the native declaration on the node itself.
        names = getattr(source, "native_output_names", None)
        if not isinstance(names, (list, tuple)) or not names:
            names = source.metadata.get("output_names") if isinstance(source.metadata, Mapping) else None
        if not isinstance(names, (list, tuple)) or not names:
            continue
        output_ref = str(edge.from_output)
        if output_ref.isdigit():
            slot = int(output_ref)
            if slot >= len(names):
                raise ValueError(
                    f"malformed_named_output_schema: {source.class_type} has no named output for slot {slot}"
                )
            continue
        if output_ref not in names:
            raise ValueError(
                f"malformed_named_output_schema: {source.class_type} has no named output {output_ref!r}"
            )


# ---------------------------------------------------------------------------
# Dead-branch pruning
# ---------------------------------------------------------------------------

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


def _all_nodes_for_imports(workflow_nodes: dict[str, Any], subgraphs: dict[str, _SubgraphDef]) -> dict[str, Any]:
    nodes = dict(workflow_nodes)
    for subgraph in subgraphs.values():
        for nid, node in subgraph.nodes.items():
            nodes.setdefault(_subgraph_emitted_node_id(subgraph.id, nid), node)
    return nodes


def _python_authoring_definitions(
    workflow_nodes: Mapping[str, Any],
) -> tuple[list[str], dict[str, str]]:
    """Collect readable function definitions for first-class exec nodes.

    The lowered graph remains the execution authority. This is only the
    reverse source projection for nodes created by the python_node decorator;
    legacy hand-authored exec bodies continue through the explicit raw-body
    escape hatch.
    """
    definitions: list[str] = []
    aliases: dict[str, str] = {}
    emitted: dict[tuple[str, str], str] = {}
    used_names: set[str] = set()

    def safe_name(value: str) -> str:
        candidate = "".join(
            ch if (ch.isalnum() or ch == "_") else "_" for ch in value
        )
        if not candidate or candidate[0].isdigit() or _keyword.iskeyword(candidate):
            candidate = f"python_node_{candidate}"
        return candidate

    for node_id, node in sorted(workflow_nodes.items(), key=lambda item: str(item[0])):
        metadata = getattr(node, "metadata", {})
        info = metadata.get("python_authoring") if isinstance(metadata, Mapping) else None
        if not isinstance(info, Mapping):
            continue
        source = info.get("source")
        identity = str(info.get("identity") or "")
        if not isinstance(source, str) or not source.strip() or not identity:
            continue
        try:
            source_text = textwrap.dedent(source)
            tree = ast.parse(source_text)
            function = next(
                item for item in tree.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            function_source = ast.get_source_segment(source_text, function)
        except (SyntaxError, StopIteration, TypeError):
            continue
        if not isinstance(function_source, str) or not function_source.strip():
            continue
        key = (identity, source)
        alias = emitted.get(key)
        if alias is None:
            base = safe_name(str(function.name))
            alias = base
            suffix = 2
            while alias in used_names:
                alias = f"{base}_{suffix}"
                suffix += 1
            used_names.add(alias)
            emitted[key] = alias
            raw_inputs = info.get("inputs", ())
            raw_outputs = info.get("outputs", ())
            input_specs = {
                str(item.get("name")): str(item.get("type") or "*")
                for item in raw_inputs
                if isinstance(item, Mapping) and isinstance(item.get("name"), str)
            }
            output_specs = {
                str(item.get("name")): str(item.get("type") or "*")
                for item in raw_outputs
                if isinstance(item, Mapping) and isinstance(item.get("name"), str)
            }
            decorated = (
                f"@python_node(inputs={input_specs!r}, outputs={output_specs!r})\n"
                f"{function_source.strip()}"
            )
            definitions.extend([decorated, ""])
        aliases[str(node_id)] = alias
    while definitions and definitions[-1] == "":
        definitions.pop()
    return definitions, aliases


def _python_source_declarations(
    workflow_nodes: Mapping[str, Any],
    *,
    reserved_names: set[str] | None = None,
) -> tuple[list[str], dict[str, str], dict[str, tuple[str, ...]]]:
    """Emit readable declarations for complete source/installed exec nodes.

    The capsule remains embedded in the ordinary exec payload for standalone
    JSON/API transport.  In generated Python it is lifted into a named source
    declaration so the graph-building calls stay short and editable.
    """
    import pprint

    lines: list[str] = []
    aliases: dict[str, str] = {}
    output_names: dict[str, tuple[str, ...]] = {}
    used = set(reserved_names or ())
    emitted: dict[str, str] = {}

    def safe_name(value: str) -> str:
        candidate = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in value)
        if not candidate or candidate[0].isdigit() or _keyword.iskeyword(candidate):
            candidate = f"python_source_{candidate}"
        return candidate

    def io_mapping(node: Any) -> tuple[dict[str, str], dict[str, str]]:
        raw = getattr(node, "inputs", {}).get("io")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raw = {}
        if not isinstance(raw, Mapping):
            raw = {}

        def normalize(value: Any) -> dict[str, str]:
            if isinstance(value, Mapping):
                return {str(name): str(type_name or "*") for name, type_name in value.items()}
            if isinstance(value, (list, tuple)):
                return {
                    str(item[0]): str(item[1] or "*")
                    for item in value
                    if isinstance(item, (list, tuple)) and item and isinstance(item[0], str)
                }
            return {}

        return normalize(raw.get("inputs")), normalize(raw.get("outputs"))

    for node_id, node in sorted(workflow_nodes.items(), key=lambda item: str(item[0])):
        metadata = getattr(node, "metadata", {})
        payload = metadata.get("python_source") if isinstance(metadata, Mapping) else None
        if not isinstance(payload, Mapping):
            continue
        fmt = payload.get("format")
        if fmt not in {"vibecomfy.python_capsule/v1", "vibecomfy.python_installed/v1"}:
            continue
        inputs, outputs_map = io_mapping(node)
        result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
        if not outputs_map:
            raw_result_outputs = result.get("outputs")
            outputs_map = normalize_result_outputs(raw_result_outputs)
        names = tuple(outputs_map)
        identity = json.dumps(
            {"payload": payload, "inputs": inputs, "outputs": outputs_map},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        alias = emitted.get(identity)
        if alias is None:
            source_id = str(payload.get("source_id") or payload.get("entrypoint") or "source")
            base = "source_" + safe_name(source_id)
            alias = base
            suffix = 2
            while alias in used:
                alias = f"{base}_{suffix}"
                suffix += 1
            used.add(alias)
            emitted[identity] = alias
            if fmt == "vibecomfy.python_capsule/v1":
                capsule_payload = {
                    key: value
                    for key, value in payload.items()
                    if key != "result"
                }
                capsule_name = f"{alias}_capsule"
                lines.extend([
                    f"{capsule_name} = SourceCapsule.from_payload(",
                    pprint.pformat(capsule_payload, sort_dicts=True, width=88),
                    ")",
                ])
                source_call = "python_node.from_source"
                source_args = [f"source={capsule_name}"]
            else:
                source_call = "python_node.from_installed"
                source_args = []
                dependencies = payload.get("dependencies")
                source_args.append(f"entrypoint={str(payload.get('entrypoint') or '')!r}")
                if isinstance(payload.get("revision"), str):
                    source_args.append(f"revision={payload['revision']!r}")
                if isinstance(dependencies, list) and dependencies:
                    source_args.append(f"dependencies={dependencies!r}")
            source_args.extend([f"entrypoint={str(payload.get('entrypoint') or '')!r}"] if fmt == "vibecomfy.python_capsule/v1" else [])
            source_args.append(f"inputs={inputs!r}")
            mode = str(result.get("mode", "mapping"))
            if mode == "mapping":
                source_args.append(f"outputs={outputs_map!r}")
            else:
                output_expr = ", ".join(repr(name) for name in names)
                if len(names) == 1:
                    output_expr += ","
                source_args.append(f"outputs=outputs({output_expr}, mode={mode!r})")
            lines.append(f"{alias} = {source_call}(")
            lines.extend(f"    {argument}," for argument in source_args)
            lines.extend([")", ""])
        aliases[str(node_id)] = alias
        output_names[str(node_id)] = names
    while lines and lines[-1] == "":
        lines.pop()
    return lines, aliases, output_names


def normalize_result_outputs(value: Any) -> dict[str, str]:
    if isinstance(value, Mapping):
        return {str(name): str(type_name or "*") for name, type_name in value.items()}
    if isinstance(value, (list, tuple)):
        return {str(name): "*" for name in value if isinstance(name, str)}
    return {}


# ---------------------------------------------------------------------------
# _emit_build_function — shared by ready-template and scratchpad backends
# ---------------------------------------------------------------------------

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
    diagnostics: list[Any] | None = None,
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
    emit_all_ids: bool = False,
    external_custody: bool = False,
    preserve_authored_graph: bool = False,
) -> list[str]:
    from vibecomfy.porting.emitter import (  # noqa: PLC0415
        EmissionDiagnostic,
        READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
        READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
    )
    if not use_shared_helpers:
        raise ValueError(
            "private scratchpad emitter removed; use the canonical public-wrapper emitter"
        )
    workflow_nodes = door_nodes(prepared)
    edges_in = prepared["edges_in"]
    ordering_source = prepared.get("ordering_edges_in", edges_in)
    ordering_edges_in = _edges_in_with_subgraph_external_refs(
        prepared, workflow_nodes, ordering_source
    )
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
        prepared.get("live_edges_in", ordering_edges_in),
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
    sorted_id_order = sorted(workflow_nodes, key=_id_sort_key)
    section_order_map: dict[str, str] = {}  # nid -> section_name
    for section_name in _SECTION_ORDER:
        for nid in section_groups.get(section_name, []):
            section_order_map[nid] = section_name

    is_subgraph_function = function_name != "build"
    emit_top_level_ids = use_shared_helpers and not is_subgraph_function and topo_order != sorted_id_order
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
    else:
        # Scope the eager new_workflow() binding with its existing context
        # manager. finalize() releases it on success; __exit__ releases it
        # when a constructor or validation step fails.
        # Root identity is recovered from constructor calls for direct renders
        # and from the validated sibling companion for bundle publication.
        custody_argument = ""
        if source_type != "ready_template":
            out_lines.append(
                f"    with new_workflow({workflow_id_expr}, source_path={source_path_expr}, source_type={source_type!r}{custody_argument}) as wf:"
            )
        else:
            out_lines.append(
                f"    with new_workflow({workflow_id_expr}, source_path={source_path_expr}{custody_argument}) as wf:"
            )
        body_indent = "        "
        continuation_indent = "            "
    out_lines.append("")

    emitted_sections: set[str] = set()
    for nid in topo_order:
        node = workflow_nodes[nid]
        var = var_names[nid]
        from vibecomfy.workflow import mode_to_litegraph  # noqa: PLC0415

        node_mode = mode_to_litegraph(getattr(node, "mode", 0))
        node_mode_expr = repr(node_mode) if node_mode else None

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

        python_alias = None
        source_alias = None
        if use_shared_helpers:
            python_alias = prepared.get("python_authoring_aliases", {}).get(str(nid))
            source_alias = prepared.get("python_source_aliases", {}).get(str(nid))
        if python_alias or source_alias:
            authoring = getattr(node, "metadata", {}).get("python_authoring", {})
            if isinstance(authoring, Mapping):
                raw_inputs = authoring.get("inputs", ())
            else:
                raw_inputs = ()
            if not raw_inputs and source_alias:
                raw_io = getattr(node, "inputs", {}).get("io")
                if isinstance(raw_io, str):
                    try:
                        raw_io = json.loads(raw_io)
                    except (TypeError, ValueError):
                        raw_io = {}
                raw_inputs = raw_io.get("inputs", ()) if isinstance(raw_io, Mapping) else ()
            input_names = [
                str(item.get("name"))
                for item in raw_inputs
                if isinstance(item, Mapping) and isinstance(item.get("name"), str)
            ]
            if not input_names and isinstance(raw_inputs, Mapping):
                input_names = [str(name) for name in raw_inputs]
            incoming_by_slot = {
                str(getattr(edge, "to_input", "")): edge
                for edge in edges_in.get(nid, ())
            }
            call_args: list[str] = []
            for index, input_name in enumerate(input_names):
                edge = incoming_by_slot.get(f"in_{index}")
                if edge is not None:
                    from_slot = getattr(edge, "from_output", 0)
                    try:
                        from_slot = int(from_slot)
                    except (TypeError, ValueError):
                        from_slot = 0
                    source_node_id = str(edge.from_node)
                    source_node_alias = (
                        prepared.get("python_authoring_aliases", {}).get(source_node_id)
                        if use_shared_helpers
                        else None
                    )
                    if not source_node_alias and use_shared_helpers:
                        source_node_alias = prepared.get("python_source_aliases", {}).get(source_node_id)
                    if source_node_alias:
                        source_info = getattr(
                            workflow_nodes[source_node_id], "metadata", {}
                        ).get("python_authoring", {})
                        source_outputs = (
                            source_info.get("outputs", ())
                            if isinstance(source_info, Mapping)
                            else prepared.get("python_source_outputs", {}).get(source_node_id, ())
                        )
                        if not source_outputs and source_node_alias:
                            source_outputs = prepared.get("python_source_outputs", {}).get(source_node_id, ())
                        output_name = (
                            source_outputs[from_slot].get("name")
                            if from_slot < len(source_outputs)
                            and isinstance(source_outputs[from_slot], Mapping)
                            else None
                        )
                        if output_name is None and from_slot < len(source_outputs):
                            output_name = source_outputs[from_slot]
                        if isinstance(output_name, str) and output_name.isidentifier():
                            value_expr = f"{var_names[source_node_id]}.{output_name}"
                        else:
                            value_expr = (
                                f"{var_names[source_node_id]}.values[{output_name!r}]"
                            )
                    else:
                        value_expr = _edge_ref_expr(
                            workflow_nodes,
                            var_names,
                            output_var_names,
                            source_node_id,
                            from_slot,
                            bare_single_output_refs=False,
                            diagnostics=diagnostics,
                            target_node=node,
                            target_input=f"in_{index}",
                        )
                else:
                    value_expr = _format_value(node.inputs.get(f"in_{index}"))
                call_args.append(f"{input_name}={value_expr}")
            if emit_all_ids:
                call_args.extend([
                    f"_id={str(nid)!r}",
                    f"_uid={str(getattr(node, 'uid', ''))!r}",
                ])
            call_expr = f"{python_alias or source_alias}(wf"
            if call_args:
                call_expr += ", " + ", ".join(call_args)
            call_expr += ")"
            single_line = f"{body_indent}{var} = {call_expr}"
            if len(single_line) > 88 or len(call_args) > 3:
                out_lines.append("")
                out_lines.append(f"{body_indent}{var} = {python_alias}(")
                out_lines.append(f"{continuation_indent}wf,")
                out_lines.extend(
                    f"{continuation_indent}{item},"
                    for item in call_args
                )
                out_lines.append(f"{body_indent})")
                out_lines.append("")
            else:
                out_lines.append(single_line)
            continue

        wrapper_module = _wrapper_module_for_class(str(node.class_type)) if use_shared_helpers else None
        preserve_fields = {
            field
            for old_id, field in (registered_inputs or {}).values()
            if old_id == nid
        }
        preserve_fields.update(public_preserve_fields.get(nid, set()))
        preserve_fields.update(
            _canonical_widget_channels(node, prepared.get("name_authority")).keys()
        )
        # Raw ``_ui`` is presentation evidence.  The kwargs builder also has
        # legacy compact-widget discovery, so give it a detached semantic copy
        # with that evidence removed; authored nodes remain untouched.
        semantic_node = node
        node_metadata = getattr(node, "metadata", None)
        if isinstance(node_metadata, Mapping) and "_ui" in node_metadata:
            semantic_node = copy.deepcopy(node)
            semantic_node.metadata.pop("_ui", None)
        exceptional_channels = _exceptional_authored_channels(
            node, edges_in, prepared.get("name_authority")
        )
        kwargs = _node_kwargs(
            semantic_node, edges_in, var_names,
            workflow_nodes=workflow_nodes,
            output_var_names=output_var_names,
            diagnostics=diagnostics,
            constant_map=constant_map,
            use_ui_widget_aliases=use_shared_helpers,
            # Canonical Python is an authored-value surface.  A value equal to
            # today's provider default is still explicit source authority and
            # must not disappear when schemas change or are unavailable.
            strip_schema_defaults=False,
            # Typed wrappers already carry their schema output roster.  A raw
            # call does not, so it must retain even a single native output in
            # ``_outputs`` for rebuilt handles to resolve deterministically.
            omit_single_output_metadata=use_shared_helpers and wrapper_module is not None,
            bare_single_output_refs=False,
            emit_reserved_keyword_args=wrapper_module is not None,
            preserve_fields=preserve_fields,
            external_refs=external_refs,
            name_authority=prepared.get("name_authority"),
            resolve_graph_strings=False,
            skip_widget_fields={record[0] for record in exceptional_channels.values()},
            emit_native_ports=emit_all_ids,
        )
        if exceptional_channels:
            present = {key for key, _expr in kwargs}
            missing = sorted(set(exceptional_channels) - present)
            if missing:
                raise ValueError(
                    "ambiguous_authored_channel: effective field "
                    f"{node.class_type}.{missing[0]} was omitted during emission"
                )
            kwargs = [
                (
                    key,
                    (
                        _format_authored_channel(expr, exceptional_channels[key])
                        if key in exceptional_channels
                        else expr
                    ),
                )
                for key, expr in kwargs
            ]

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

            if use_wrapper:
                all_args = []
                all_args.extend((_wrapper_kwarg_name(key), expr) for key, expr in ready_kwargs)
                if emit_all_ids:
                    all_args.append(("_id", repr(str(nid))))
                    if preserve_authored_graph:
                        all_args.append(("_uid", repr(str(node.uid))))
                if node_mode_expr is not None:
                    all_args.append(("_mode", node_mode_expr))
                # v2.6.4 Fix 3: drop _outputs= for schema-known typed wrappers.
                # The wrapper class already knows its output names from the
                # generated schema (vibecomfy/nodes/<pack>.py). Only
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
                if emit_all_ids and preserve_authored_graph:
                    all_args.append(("_uid", repr(str(node.uid))))
                if node_mode_expr is not None:
                    all_args.append(("_mode", node_mode_expr))
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
                raw_prefix = [repr(node.class_type)]
                if emit_all_ids:
                    raw_prefix.append(repr(str(nid)))
                call_args = ", ".join([*raw_prefix, *kwarg_lines])
                call_expr = f"raw_call({call_args})"
            single_line = (
                f"{body_indent}{assignment_target} = {call_expr}"
                if assignment_target is not None
                else f"{body_indent}{call_expr}"
            )

            # -- readability diagnostic: long one-line node call ----------
            readable_kwarg_lines = [
                f"**{expr}" if key == "**" else f"{key}={expr}"
                for key, expr in all_args
            ]
            if use_wrapper:
                readable_expr = f"{call_name}({', '.join(readable_kwarg_lines)})"
            else:
                    readable_prefix = [repr(node.class_type)]
                    if emit_all_ids:
                        readable_prefix.append(repr(str(nid)))
                    readable_expr = f"raw_call({', '.join([*readable_prefix, *readable_kwarg_lines])})"
            readable_single_line = (
                f"{body_indent}{assignment_target} = {readable_expr}"
                if assignment_target is not None
                else f"{body_indent}{readable_expr}"
            )
            if diagnostics is not None and len(readable_single_line) > 120:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
                        message=(
                            f"node call for {node.class_type!r} (node {nid}) would be a single "
                            f"line of {len(readable_single_line)} chars (>120); multi-line formatting preferred."
                        ),
                        severity="warning",
                        node_id=str(nid),
                        class_type=node.class_type,
                        detail={"line_length": len(readable_single_line)},
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
                    raw_id = f" {str(nid)!r}," if emit_all_ids else ""
                    head = (
                        f"{body_indent}raw_call({node.class_type!r},{raw_id}"
                        if assignment_target is None
                        else f"{body_indent}{assignment_target} = raw_call({node.class_type!r},{raw_id}"
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
# ---------------------------------------------------------------------------
# _with_id_map_tail_line
# ---------------------------------------------------------------------------

def _with_id_map_tail_line(tail_lines: list[str], var_names: dict[str, str]) -> list[str]:
    # v2.6.4 fix: id_map is derived at runtime via wf.id_map() (returns
    # {ClassType#N: node_id}). The build() source is the authoritative
    # variable-name binding; storing it again at runtime via _set_id_map
            # was bloat that scaled linearly with node count (60+ entry one-line
    # dicts on LTX templates). Drop the emission entirely.
    return tail_lines


# ---------------------------------------------------------------------------
# Output class registry and terminal-node detection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Template formatting check
# ---------------------------------------------------------------------------

def _check_template_formatting(
    combined: str,
    workflow_nodes: dict[str, Any],
    section_groups: dict[str, list[str]],
    diagnostics: list[Any],
) -> None:
    """Check generated template for section comments and indentation hygiene.

    Two checks:
    1. If the workflow has >=8 nodes and section_groups are non-empty but no
       section comment lines appear in the output.
    2. If any line in the tail (after the build function body) is un-indented
       (does not start with 4 spaces, '#', blank, or a string-like line).
    """
    from vibecomfy.porting.emitter import EmissionDiagnostic, READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED  # noqa: PLC0415
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


def _has_ltx_lowvram_tail(category_id: str) -> bool:
    return category_id.startswith("video/ltx2_3_t2v") or category_id.startswith("video/ltx2_3_i2v")


# ---------------------------------------------------------------------------
# _apply_overrides — patch-list mutator
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Node-local identity-aware output helpers
# ---------------------------------------------------------------------------

def _retained_output_names(node: Any) -> list[str] | None:
    """Return the output roster already bound to this retained IR node.

    Native names are captured at ingest from the selected schema/UI witness;
    metadata names are the older retained representation.  Either is stronger
    than a process-global object-info catalog and must prevent a later ambient
    class lookup from changing arity mid-session.
    """
    native_names = getattr(node, "native_output_names", None)
    if isinstance(native_names, (list, tuple)):
        return [str(name) if name is not None else "" for name in native_names]
    metadata = getattr(node, "metadata", None)
    metadata_names = metadata.get("output_names") if isinstance(metadata, Mapping) else None
    if isinstance(metadata_names, (list, tuple)):
        return [str(name) if name is not None else "" for name in metadata_names]
    return None


def _node_local_output_names(node: Any) -> list[str]:
    """Retained output names for *node*, then identity/class fallback."""
    retained_names = _retained_output_names(node)
    if retained_names is not None:
        return retained_names

    from vibecomfy.porting.emitter import _identity_for_node, _record_lookup_warning  # noqa: PLC0415
    from vibecomfy.errors import ObjectInfoIdentityError  # noqa: PLC0415
    from vibecomfy.porting.object_info import output_names as _class_output_names, resolve_class_entry  # noqa: PLC0415
    class_type = str(node.class_type)
    declared_exec_outputs = _declared_exec_outputs(node)
    if declared_exec_outputs is not None:
        return [name for name, _type_name in declared_exec_outputs]
    identity = _identity_for_node(node)
    if identity is not None:
        try:
            result = resolve_class_entry(class_type, identity=identity, allow_class_fallback=True)
        except ObjectInfoIdentityError:
            raise
        except Exception:
            return list(_class_output_names(class_type))
        _record_lookup_warning(node, class_type, result.warning)
        entry = result.entry
        if entry is not None:
            outputs = entry.get("outputs") or []
            names = [str(o.get("name", "")) for o in outputs if isinstance(o, Mapping)]
            if names:
                return names
    return list(_class_output_names(class_type))


def _reconcile_emit_arity(
    snapshot_count: int,
    ui_output_count: int | None,
) -> int:
    """Pick an emit arity without aborting a loaded graph.

    Agent-edit emit of an already-authored graph must not fail-closed because
    object_info and UI metadata disagree. Prefer the UI count when present
    (those are the slots the graph already uses); otherwise the snapshot.
    """
    if ui_output_count is None:
        return snapshot_count
    return ui_output_count


def _node_local_arity_check(node: Any, ui_output_count: int | None) -> int:
    """Retained arity consensus check for *node*; identity/class fallback.

    A node-local roster is the session's captured authority and is checked
    without touching process-global object-info state.  Only nodes lacking
    retained evidence use the historical identity/class lookup path.
    Snapshot/UI disagreements are reconciled rather than raised: aborting
    emit blocked representable live edits of existing graphs.
    """
    class_type = str(node.class_type)
    retained_names = _retained_output_names(node)
    if retained_names is not None:
        retained_count = len(retained_names)
        return _reconcile_emit_arity(retained_count, ui_output_count)

    from vibecomfy.porting.emitter import _identity_for_node, _record_lookup_warning  # noqa: PLC0415
    from vibecomfy.errors import ObjectInfoIdentityError  # noqa: PLC0415
    from vibecomfy.porting.object_info import (  # noqa: PLC0415
        class_is_known,
        class_output_count,
        resolve_class_entry,
    )
    def _class_fallback_count() -> int:
        cached_count = class_output_count(class_type)
        if ui_output_count is not None and class_is_known(class_type):
            return _reconcile_emit_arity(cached_count, ui_output_count)
        return cached_count

    declared_exec_outputs = _declared_exec_outputs(node)
    if declared_exec_outputs is not None:
        declared_count = len(declared_exec_outputs)
        return _reconcile_emit_arity(declared_count, ui_output_count)
    identity = _identity_for_node(node)
    if identity is not None:
        try:
            result = resolve_class_entry(
                class_type, identity=identity, allow_class_fallback=True
            )
        except ObjectInfoIdentityError:
            raise
        except Exception:
            return _class_fallback_count()
        _record_lookup_warning(node, class_type, result.warning)
        entry = result.entry
        if entry is None:
            return _class_fallback_count()
        cached_count = len(entry.get("outputs") or [])
        return _reconcile_emit_arity(cached_count, ui_output_count)
    return _class_fallback_count()


def _exec_node_field(node: Any, key: str) -> Any:
    node_widgets = getattr(node, "widgets", None)
    if isinstance(node_widgets, Mapping) and key in node_widgets:
        return node_widgets[key]
    node_inputs = getattr(node, "inputs", None)
    if isinstance(node_inputs, Mapping) and key in node_inputs:
        return node_inputs[key]
    return None


def _declared_exec_outputs(node: Any) -> list[tuple[str, str | None]] | None:
    """Return declared ``vibecomfy.exec`` outputs from inline ``io`` when present."""
    if getattr(node, "class_type", None) != "vibecomfy.exec":
        return None
    raw_io = _exec_node_field(node, "io")
    if isinstance(raw_io, str):
        try:
            raw_io = json.loads(raw_io)
        except (TypeError, ValueError):
            return None
    if not isinstance(raw_io, Mapping):
        return None
    raw_outputs = raw_io.get("outputs")
    if isinstance(raw_outputs, Mapping):
        raw_outputs = [[name, type_name] for name, type_name in raw_outputs.items()]
    if not isinstance(raw_outputs, list):
        return None
    outputs: list[tuple[str, str | None]] = []
    for item in raw_outputs:
        if isinstance(item, Mapping):
            name = item.get("name")
            output_type = item.get("type")
        elif isinstance(item, (list, tuple)) and 1 <= len(item) <= 2:
            name = item[0]
            output_type = item[1] if len(item) == 2 else None
        else:
            return None
        if not isinstance(name, str) or not name:
            return None
        if output_type is not None and not isinstance(output_type, str):
            return None
        outputs.append((name, output_type if isinstance(output_type, str) and output_type else None))
    return outputs
