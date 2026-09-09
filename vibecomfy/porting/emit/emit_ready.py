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
from dataclasses import replace
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.node_packs import LockEntry, read_lockfile
from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
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
) -> list[_PublicInputSpec]:
    specs: list[_PublicInputSpec] = []
    used_names: set[str] = set()
    used_targets: set[tuple[str, str]] = set()

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
        used_targets.add((str(binding.node_id), str(binding.field)))

    for input_name, (old_id, field) in dict(registered_inputs or {}).items():
        resolved_field = field
        if field.startswith("widget_") and old_id in workflow_nodes:
            cls = workflow_nodes[old_id].class_type
            node = workflow_nodes[old_id]
            metadata = getattr(node, "metadata", {})
            aliases = metadata.get("input_aliases") if isinstance(metadata, Mapping) else None
            resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
            if resolved.name is not None:
                resolved_field = resolved.name
        add(_PublicInputBinding(name=input_name, node_id=str(old_id), field=resolved_field))

    inferred = _infer_public_input_bindings(
        workflow_nodes,
        edges_in,
        reserved_names=used_names,
        reserved_targets=used_targets,
    )
    for binding in inferred:
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
        lines.append(f"    {spec.name!r}: InputSpec({', '.join(args)}),")
    lines.append("}" if metadata else "    }")
    return lines


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
    requirements_expr = _requirements_expr_for_emit(requirements, has_models=has_models)
    if requirements_expr is not None:
        lines.append(f"    requirements={requirements_expr},")
    if custom_node_packs:
        lines.append(f"    custom_node_packs={_format_value(dict(custom_node_packs))},")
    for key, value in _metadata_extras_for_emit(metadata).items():
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
) -> str:
    from vibecomfy.porting.emit.emit_prepare import _prepare_workflow_for_emit  # noqa: PLC0415
    _preflight_object_info_identity_resolution(workflow)
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
    # Connections are emitted once, explicitly, from ``workflow.edges``.
    # Imported IR may also retain a link-shaped value on the target input; do
    # not let the wrapper call turn that redundant view into a second edge.
    for edge in workflow.edges:
        target = emission_workflow.nodes.get(str(edge.to_node))
        if target is None:
            continue
        if str(edge.to_input) in target.inputs:
            target.inputs[str(edge.to_input)] = None
        if str(edge.to_input) in target.widgets:
            target.widgets[str(edge.to_input)] = None
    prepared = _prepare_workflow_for_emit(
        emission_workflow,
        apply_overrides=apply_overrides,
        template_id=template_id,
        diagnostics=diagnostics,
        project_execution_edges=False,
        keep_virtual_wires=True,
        prune_dead_branches=False,
    )
    prepared["subgraph_definitions"] = subgraph_definitions
    _apply_subgraph_names_to_prepared(prepared)
    has_ltx_tail = _has_ltx_lowvram_tail(template_id)

    workflow_nodes = door_nodes(prepared)
    edges_in = prepared["edges_in"]
    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
    var_names = prepared["var_names"]

    # Hoist constants and build section groups
    constant_lines, constant_map = _hoist_constants(
        workflow_nodes, edges_in, var_names, name_authority=prepared.get("name_authority")
    )
    constant_lines, constant_map = _drop_output_prefix_constants(constant_lines, constant_map)
    section_groups = _build_section_groups(workflow_nodes, edges_in)
    definition_lines, definitions_expr = _canonical_definition_helpers(
        workflow.definitions,
        interfaces=workflow.interfaces,
        boundary_ports=workflow.boundary_ports,
    )
    wrapper_imports = _wrapper_imports_for_nodes(_all_nodes_for_imports(workflow_nodes, subgraph_definitions))
    wrapper_imports = _merge_definition_wrapper_imports(
        wrapper_imports, workflow.definitions
    )
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
    out_lines.append("# vibecomfy: surface=canonical")
    out_lines.append('"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append(
        "from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref"
    )
    out_lines.append("from vibecomfy.workflow import VibeWorkflow")
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
    # Finalization releases the workflow context. Restore the exact authored
    # semantic IR afterwards so inferred ready-template metadata never becomes
    # a competing authority.
    tail_lines = [
        *(
            f"    {line}"
            for line in _canonical_connection_lines(
                workflow,
                retained_node_ids=set(workflow_nodes),
            )
        ),
        *tail_lines[:-1],
        tail_lines[-1].replace("return wf.finalize(", "wf = wf.finalize(", 1),
        *(
            f"    {line}"
            for line in _canonical_semantic_lines(
                workflow,
                workflow_nodes,
                registered_inputs=registered_inputs,
                definitions_expr=definitions_expr,
            )
        ),
        "    return wf",
    ]
    # Connections are emitted explicitly above. Keep the original edge view
    # for ordering/liveness, but do not duplicate links in kwargs.
    prepared["ordering_edges_in"] = edges_in
    prepared["live_edges_in"] = edges_in
    prepared["edges_in"] = {}
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
            emit_all_ids=True,
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


def _canonical_semantic_lines(
    workflow: Any,
    workflow_nodes: Mapping[str, Any],
    *,
    registered_inputs: Mapping[str, tuple[str, str]] | None,
    definitions_expr: str | None,
) -> list[str]:
    """Render authored semantic fields that wrappers cannot carry themselves.

    Public node wrappers intentionally own node construction and output ABI;
    recursive declarations, variant maps, and T04 native socket rosters belong
    to the workflow IR and therefore are restored explicitly on the freshly
    built workflow.  Values are detached before rendering so emission never
    mutates the caller or turns UI evidence into a source authority.
    """
    def render(value: Any) -> str:
        return _format_value(_plain_canonical_value(copy.deepcopy(value)))

    lines: list[str] = []
    for node_id in sorted(workflow.nodes, key=str):
        node = workflow.nodes[node_id]
        if str(node_id) not in workflow_nodes:
            continue
        node_expr = f"wf.nodes[{str(node_id)!r}]"
        lines.append(f"{node_expr}.inputs = {render(node.inputs)}")
        lines.append(f"{node_expr}.widgets = {render(node.widgets)}")
        semantic_metadata = workflow._semantic_node_metadata(node)
        runtime_metadata: dict[str, Any] = {}
        if semantic_metadata:
            runtime_metadata["semantic"] = semantic_metadata
        source_metadata = node.metadata if isinstance(node.metadata, Mapping) else {}
        for key in (
            "schema_source", "unresolved", "reconciliation", "diagnostics",
            "provenance", "input_names", "output_names", "input_types", "output_types",
            "keep_defaults",
        ):
            if key in source_metadata:
                runtime_metadata[key] = copy.deepcopy(source_metadata[key])
        lines.append(f"{node_expr}.metadata = {render(runtime_metadata)}")
        # Ready wrappers hydrate legacy schema carriers while they build.  The
        # emitted workflow is the authority, including an explicit absence, so
        # always overwrite every carrier rather than leaving wrapper evidence
        # behind when the authored node has ``None``.
        lines.append(f"{node_expr}.native_input_names = {render(node.native_input_names)}")
        lines.append(f"{node_expr}.native_output_names = {render(node.native_output_names)}")
        lines.append(f"{node_expr}.native_input_types = {render(node.native_input_types)}")
        lines.append(f"{node_expr}.native_output_types = {render(node.native_output_types)}")
        lines.append(f"{node_expr}.native_input_optional = {render(node.native_input_optional)}")
        lines.append(f"{node_expr}.native_input_asset_kinds = {render(node.native_input_asset_kinds)}")
        lines.append(f"{node_expr}.native_output_slots = {render(node.native_output_slots)}")
    for field_name in ("definitions", "interfaces", "boundary_ports", "virtual_wires"):
        value = copy.deepcopy(getattr(workflow, field_name, None))
        if value:
            value_expr = definitions_expr if field_name == "definitions" else None
            lines.append(f"wf.{field_name} = {value_expr or render(value)}")
    if workflow.variants:
        lines.append(f"wf.variants = {render(workflow.variants)}")
    if workflow.default_variant is not None:
        lines.append(f"wf.default_variant = {render(workflow.default_variant)}")
    # Public inputs are reconstructed through the IR's public registration
    # method.  This preserves aliases/ranges/media semantics without importing
    # workflow dataclasses that the restricted generated-source policy does
    # not expose.
    lines.append("wf.inputs.clear()")
    authored_inputs = dict(workflow.inputs)
    for name, target in sorted(dict(registered_inputs or {}).items()):
        if name in authored_inputs:
            continue
        node_id, field = str(target[0]), str(target[1])
        node = workflow.nodes.get(node_id)
        if node is None or (field not in node.inputs and field not in node.widgets):
            raise ValueError(
                f"public input {name!r} targets missing field {node_id}.{field}"
            )
        value = copy.deepcopy(node.inputs.get(field, node.widgets.get(field)))
        authored_inputs[name] = {
            "name": name,
            "node_id": node_id,
            "field": field,
            "value": value,
            "type": None,
            "default": value,
            "required": False,
            "range": None,
            "aliases": (),
            "media_semantics": None,
            "allow_missing_target": False,
        }
    def read_input(item: Any, key: str) -> Any:
        return item[key] if isinstance(item, Mapping) else getattr(item, key)

    descriptor_fields = (
        "node_id", "field", "value", "type", "default", "required", "range",
        "media_semantics", "allow_missing_target",
    )
    from vibecomfy.testing.canonical import canonical_bytes

    def descriptor_bytes(item: Any) -> bytes:
        return canonical_bytes(
            {field_name: read_input(item, field_name) for field_name in descriptor_fields}
        )

    materialized_alias_owners: dict[str, str] = {}
    for owner_name, owner in authored_inputs.items():
        for alias in tuple(read_input(owner, "aliases")):
            candidate = authored_inputs.get(alias)
            if candidate is None or tuple(read_input(candidate, "aliases")):
                continue
            if descriptor_bytes(candidate) == descriptor_bytes(owner):
                previous = materialized_alias_owners.setdefault(str(alias), str(owner_name))
                if previous != str(owner_name):
                    materialized_alias_owners.pop(str(alias), None)

    ordered_input_names = [
        *sorted(
            (name for name in authored_inputs if name not in materialized_alias_owners),
            key=str,
        ),
        *sorted(materialized_alias_owners, key=str),
    ]
    for name in ordered_input_names:
        item = authored_inputs[name]
        read = (
            (lambda key: item[key])
            if isinstance(item, Mapping)
            else (lambda key: getattr(item, key))
        )
        register_args = [
            repr(str(read("name"))),
            repr(str(read("node_id"))),
            repr(str(read("field"))),
            render(read("value")),
            f"type={render(read('type'))}",
            f"default={render(read('default'))}",
            f"required={render(read('required'))}",
            f"range={render(read('range'))}",
            f"aliases={render(tuple(read('aliases')))}",
            f"media_semantics={render(read('media_semantics'))}",
            f"allow_missing_target={render(read('allow_missing_target'))}",
        ]
        if name in materialized_alias_owners:
            register_args.append(
                f"materialized_alias_of={materialized_alias_owners[name]!r}"
            )
        lines.append(f"wf.register_input({', '.join(register_args)})")
        # ``register_input`` predates the distinction between an omitted
        # default and an explicitly-authored ``None`` and therefore falls
        # back to ``value`` whenever ``default is None``.  Canonical source
        # must preserve the exact VibeInput descriptor, so restore the
        # detached authored value after registration instead of broadening
        # the public API with a second sentinel/overload.
        if read("default") is None:
            lines.append(
                f"wf.inputs[{str(read('name'))!r}].default = {render(read('default'))}"
            )

    # finalize_metadata() already creates the public-output objects for every
    # supported terminal node.  Reuse those objects, select the authored set,
    # and restore the exact contract.  An output that cannot be bound through
    # that public lifecycle is rejected instead of being smuggled in through a
    # private dataclass constructor.
    from vibecomfy.metadata import OUTPUT_NODE_NAMES
    from vibecomfy.workflow import mode_to_litegraph

    inferred_output_ids = sorted(
        (
            str(node_id)
            for node_id, node in workflow.nodes.items()
            if node.class_type in OUTPUT_NODE_NAMES
            and mode_to_litegraph(node.mode) not in (2, 4)
        ),
        key=lambda item: (int(item) if item.isdigit() else 1 << 30, item),
    )
    authored_output_ids = [str(item.node_id) for item in workflow.outputs]
    duplicate_output_ids = sorted(
        node_id for node_id in set(authored_output_ids) if authored_output_ids.count(node_id) > 1
    )
    if duplicate_output_ids:
        raise ValueError(
            "duplicate public output binding(s) are not representable through the canonical "
            f"public lifecycle: {', '.join(duplicate_output_ids)}"
        )
    unbound_output_ids = sorted(set(authored_output_ids) - set(inferred_output_ids))
    if unbound_output_ids:
        raise ValueError(
            "public output binding(s) do not target supported terminal output nodes: "
            f"{', '.join(unbound_output_ids)}"
        )
    for index, item in enumerate(workflow.outputs):
        source_index = inferred_output_ids.index(str(item.node_id))
        lines.append(f"public_output_{index} = wf.outputs[{source_index}]")
    lines.append("wf.outputs.clear()")
    for index, item in enumerate(workflow.outputs):
        output_expr = f"public_output_{index}"
        lines.append(f"{output_expr}.output_type = {render(item.output_type)}")
        lines.append(f"{output_expr}.name = {render(item.name)}")
        lines.append(f"{output_expr}.artifact_kind = {render(item.artifact_kind)}")
        lines.append(f"{output_expr}.mime_type = {render(item.mime_type)}")
        lines.append(f"{output_expr}.filename_prefix = {render(item.filename_prefix)}")
        lines.append(
            f"{output_expr}.expected_cardinality = {render(item.expected_cardinality)}"
        )
        lines.append(f"wf.outputs.append({output_expr})")

    for field_name in (
        "models", "custom_nodes", "missing_models", "missing_nodes", "unsupported",
    ):
        value = copy.deepcopy(getattr(workflow.requirements, field_name))
        lines.append(f"wf.requirements.{field_name} = {render(value)}")
    lines.append(f"wf.strict_types = {render(bool(workflow.strict_types))}")
    return lines


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
) -> tuple[list[str], str | None]:
    """Render typed, readable recursive callables plus a literal IR expression.

    The callables are an inspectable Python-owned authoring view.  ``build``
    never calls them: its ``wf.definitions`` assignment is a detached literal,
    and recursive expansion remains solely in ``VibeWorkflow``'s compiler.
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

    def literal_container(source: Any) -> str:
        return render(source)

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
            records.append({"id": node_id, "class_type": class_type, "uid": raw.get("uid"), "values": values})
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
                    continue
                wrapper = _wrapper_symbol_for_class(class_type) if _wrapper_module_for_class(class_type) else None
                call_name = wrapper or "raw_call"
                args = ["wf"] if wrapper else ["wf", repr(class_type)]
                args.append(f"_id={node_id!r}")
                if record.get("uid"):
                    args.append(f"_uid={str(record['uid'])!r}")
                if not wrapper:
                    args.append("pass_raw=True")
                for field, value in record["values"].items():
                    parameter = boundary_inputs.get((node_id, field))
                    if parameter:
                        value_expr = parameter
                    elif isinstance(value, (list, tuple)) and len(value) >= 2 and isinstance(value[0], (str, int)) and isinstance(value[1], int):
                        continue
                    else:
                        value_expr = render(value)
                    if _keyword.iskeyword(field) or not field.isidentifier():
                        args.append(f"**{{{field!r}: {value_expr}}}")
                    else:
                        args.append(f"{field}={value_expr}")
                lines.append(f"    {var} = {call_name}({', '.join(args)})")
            for source, slot, target, field in link_records(definition, records):
                lines.append(f"    wf.connect({source + '.' + slot!r}, {target + '.' + field!r})")
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
                    output_exprs.append(f"{var}.out({int(field) if str(field).isdigit() else field!r})")
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
    [walk(item, ()) for item in top_entries]
    if lines and lines[-1] == "":
        lines.pop()
    # Build owns this literal expression.  No callable is invoked from build.
    return lines, literal_container(definitions)


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

        wrapper_module = _wrapper_module_for_class(str(node.class_type)) if use_shared_helpers else None
        preserve_fields = {
            field
            for old_id, field in (registered_inputs or {}).values()
            if old_id == nid
        }
        preserve_fields.update(public_preserve_fields.get(nid, set()))
        # Raw ``_ui`` is presentation evidence.  The kwargs builder also has
        # legacy compact-widget discovery, so give it a detached semantic copy
        # with that evidence removed; authored nodes remain untouched.
        semantic_node = node
        node_metadata = getattr(node, "metadata", None)
        if isinstance(node_metadata, Mapping) and "_ui" in node_metadata:
            semantic_node = copy.deepcopy(node)
            semantic_node.metadata.pop("_ui", None)
        kwargs = _node_kwargs(
            semantic_node, edges_in, var_names,
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
            name_authority=prepared.get("name_authority"),
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
            native_ports_arg = (
                "_native_ports",
                repr({
                    "native_input_names": copy.deepcopy(node.native_input_names),
                    "native_output_names": copy.deepcopy(node.native_output_names),
                    "native_input_types": copy.deepcopy(node.native_input_types),
                    "native_output_types": copy.deepcopy(node.native_output_types),
                    "native_input_optional": copy.deepcopy(node.native_input_optional),
                    "native_input_asset_kinds": copy.deepcopy(node.native_input_asset_kinds),
                    "native_output_slots": copy.deepcopy(node.native_output_slots),
                }),
            )

            if use_wrapper:
                all_args = []
                if is_subgraph_function and node_id_prefix is not None:
                    if _subgraph_node_id_required(node_id_prefix, nid, required_ids):
                        all_args.append(("_id", repr(_subgraph_emitted_node_id(node_id_prefix, nid))))
                elif emit_all_ids or emit_top_level_ids:
                    # Preserve source node ids only when emission order differs from
                    # the source id order; otherwise auto-assigned ids stay stable
                    # and the explicit _id noise is unnecessary.
                    all_args.append(("_id", repr(str(nid))))
                all_args.extend((_wrapper_kwarg_name(key), expr) for key, expr in ready_kwargs)
                if node_mode_expr is not None:
                    all_args.append(("_mode", node_mode_expr))
                if uid_arg is not None:
                    all_args.append(uid_arg)
                all_args.append(native_ports_arg)
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
                if node_mode_expr is not None:
                    all_args.append(("_mode", node_mode_expr))
                if uid_arg is not None:
                    all_args.append(uid_arg)
                all_args.append(native_ports_arg)
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
            # `_native_ports` is an internal custody payload that deliberately
            # makes every emitted call multiline.  Measure the authored call
            # surface without that payload so ordinary short nodes do not gain
            # spurious readability warnings, while genuinely long user values
            # keep the existing diagnostic.
            readable_kwarg_lines = [
                f"**{expr}" if key == "**" else f"{key}={expr}"
                for key, expr in all_args
                if key != "_native_ports"
            ]
            if use_wrapper:
                readable_expr = f"{call_name}({', '.join(readable_kwarg_lines)})"
            else:
                readable_expr = f"raw_call({', '.join([repr(node.class_type), repr(raw_node_id), *readable_kwarg_lines])})"
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
