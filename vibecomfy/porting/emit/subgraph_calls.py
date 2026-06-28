"""Subgraph call, signature, and return-expression helpers."""

from __future__ import annotations

import keyword
from collections import Counter
from typing import Any, Mapping

from vibecomfy.porting.emit.constants_hoist import _translate_widget_for_key
from vibecomfy.porting.emit.diagnostics import (
    EmissionDiagnostic,
    READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
)
from vibecomfy.porting.emit.format_values import _format_value
from vibecomfy.porting.emit.naming_codegen import (
    _assignment_target,
    _edge_ref_expr,
    _live_output_slots_for_function,
    _safe_var,
)
from vibecomfy.porting.emit.node_kwargs_core import (
    _is_link,
    _ui_widget_aliases,
    _ui_widget_values_by_name,
)
from vibecomfy.porting.emit.subgraph_defs import (
    _SubgraphDef,
    _slugify_identifier,
)


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
            # Avoid collision: var name must not equal subgraph function name.
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


def _subgraph_node_id_required(
    node_id_prefix: str | None,
    nid: str,
    required_ids: set[str] | None,
) -> bool:
    """Return True if a subgraph node's explicit _id= kwarg is load-bearing.

    When *required_ids* is None, all node IDs are considered required (backward
    compatibility for paths that do not supply the precomputed set). Otherwise
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
