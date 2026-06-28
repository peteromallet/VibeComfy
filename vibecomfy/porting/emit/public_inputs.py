from __future__ import annotations

import ast
import re
from dataclasses import dataclass, replace
from typing import Any, Callable

from vibecomfy.porting.emit.format_values import _format_value
from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance

_LOAD_IMAGE_FAMILY: frozenset[str] = frozenset({
    "LoadImage", "LoadImageMask", "LoadImagePath",
})

_IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp"})


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


def _public_input_specs(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    *,
    registered_inputs: dict[str, tuple[str, str]] | None,
    constant_map: dict[tuple[str, str], str],
    resolve_graph_field_get_string: Callable[[Any, dict[str, Any]], Any],
    resolved_field_values: Callable[[Any], dict[str, Any]],
    first_output_var: Callable[[dict[int, str] | None], str | None],
    ui_widget_aliases: Callable[[Any], list[str | None] | None],
    infer_public_input_bindings: Callable[[dict[str, Any], dict[str, list[Any]], set[str]], list[_PublicInputBinding]],
) -> list[_PublicInputSpec]:
    specs: list[_PublicInputSpec] = []
    used_names: set[str] = set()

    def add(binding: _PublicInputBinding) -> None:
        if binding.name in used_names:
            return
        node = workflow_nodes.get(str(binding.node_id))
        if node is None:
            return
        field_values = resolved_field_values(node)
        if binding.field not in field_values:
            return
        default_value = resolve_graph_field_get_string(
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
        node_var = first_output_var(output_var_names.get(str(binding.node_id))) or var_names.get(str(binding.node_id))
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
            aliases = getattr(node, "metadata", {}).get("input_aliases") or ui_widget_aliases(node)
            resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
            if resolved.name is not None:
                resolved_field = resolved.name
        add(_PublicInputBinding(name=input_name, node_id=str(old_id), field=resolved_field))

    inferred = infer_public_input_bindings(workflow_nodes, edges_in, used_names)
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
    subgraphs: dict[str, Any],
    *,
    subgraph_port_index_for_instance_field: Callable[[Any, Any, str], int | None],
    subgraph_emitted_node_id: Callable[[str, str], str],
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
        port_index = subgraph_port_index_for_instance_field(node, subgraph, spec.field)
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
                metadata_node_ref=repr(subgraph_emitted_node_id(subgraph.id, internal_node_id)),
                field=internal_field,
            )
        )
    return remapped
