"""emit_prepare.py — workflow preparation and agent-edit emission.

Houses:
- _VIRTUAL_WIRE_EMITTER_CLASS_TYPES  (constant)
- _prepare_workflow_for_emit          (cascade-breaker / emission-prep function)
- _emit_agent_edit_lines              (agent-edit scratchpad emitter)
- Private helpers only used by the above (_agent_edit_output_aliases, etc.)

Part of the M2 structural decomposition of vibecomfy/porting/emitter.py.
Public-input helpers and ready-template backend live in emit_ready.py (T8).
"""
from __future__ import annotations

import keyword
import re
import warnings
from typing import Any, Mapping

from vibecomfy.errors import ConversionParityError
from vibecomfy._compile._helpers import RESOLVABLE_HELPER_CLASS_TYPES
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.porting.emit.emit_constants import (
    UI_ONLY_CLASS_TYPES,
    _AGENT_EDIT_STRING_ELIDE_THRESHOLD,
    _ui_widget_aliases,
)
from vibecomfy.porting.emit.emit_kwargs import (
    _is_link,
    _safe_var,
    _topological_node_order,
    _compute_variable_names,
    _apply_locked_variable_names,
    _compute_output_variable_names,
    _edges_in_with_subgraph_external_refs,
    _format_value,
    _declared_ui_output_names,
)
from vibecomfy.porting.emit.emit_ready import (
    _declared_exec_outputs,
    _node_local_arity_check,
    _node_local_output_names,
)

# ---------------------------------------------------------------------------
# Module-level constant
# ---------------------------------------------------------------------------

_VIRTUAL_WIRE_EMITTER_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})


# ---------------------------------------------------------------------------
# _prepare_workflow_for_emit
# ---------------------------------------------------------------------------

def _prepare_workflow_for_emit(
    workflow: Any,
    *,
    apply_overrides: dict[str, Any] | None,
    template_id: str | None = None,
    keep_virtual_wires: bool = False,
    prune_dead_branches: bool = True,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
    diagnostics: list[Any] | None = None,
    scope_path: str = "",
) -> dict[str, Any]:
    # Preserve fully disconnected canvases. Dead-branch pruning is useful when
    # trimming a real graph, but on a no-edge workflow it collapses the emission
    # to arbitrary terminal nodes and drops section/comment coverage entirely.
    if prune_dead_branches and not getattr(workflow, "edges", ()):
        prune_dead_branches = False

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
    # UI-only classes (Note/MarkdownNote/PreviewAny/…) are normally decorative and
    # stripped. But some — notably PreviewAny — are wired as live PASSTHROUGHS
    # (their output feeds a real node). In fidelity mode (agent-edit,
    # prune_dead_branches=False) stripping such a node severs that edge and drops
    # the data it carried (e.g. GeminiNode → PreviewAny → ByteDance.model.prompt).
    # Keep a UI-only node when it has an output edge into a non-UI-only node.
    ui_only_passthroughs: set[str] = set()
    if not prune_dead_branches:
        for edge in workflow.edges:
            src = workflow.nodes.get(str(edge.from_node))
            dst = workflow.nodes.get(str(edge.to_node))
            if (
                src is not None
                and dst is not None
                and src.class_type in UI_ONLY_CLASS_TYPES
                and dst.class_type not in UI_ONLY_CLASS_TYPES
            ):
                ui_only_passthroughs.add(str(edge.from_node))
    workflow_nodes = {
        nid: node
        for nid, node in workflow.nodes.items()
        if node.class_type not in UI_ONLY_CLASS_TYPES or str(nid) in ui_only_passthroughs
    }
    _sync_declared_exec_output_metadata(workflow_nodes)
    edges_in: dict[str, list[Any]] = {}
    for edge in workflow.edges:
        if edge.from_node not in workflow_nodes or edge.to_node not in workflow_nodes:
            continue
        edges_in.setdefault(edge.to_node, []).append(edge)

    if apply_overrides:
        # Lazy import to avoid circular dependency
        from vibecomfy.porting.emit.emit_ready import _apply_overrides  # noqa: PLC0415
        _apply_overrides(workflow_nodes, edges_in, apply_overrides.get("patches") or [])

    # Dead-branch pruning produces minimal templates for authoring, but it drops
    # nodes that don't feed a recognized output (e.g. a GeminiNode whose only
    # consumer is a PreviewAny). When emitting a faithful scratchpad of a user's
    # live canvas (agent-edit), pruning must be disabled so every node survives.
    if prune_dead_branches:
        # Lazy import to avoid circular dependency
        from vibecomfy.porting.emit.emit_ready import _prune_dead_branches_for_emit  # noqa: PLC0415
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
    _apply_locked_variable_names(
        workflow_nodes,
        var_names,
        variable_name_locks=variable_name_locks,
        strict=strict_variable_name_locks,
        diagnostics=diagnostics,
        scope_path=scope_path,
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


# ---------------------------------------------------------------------------
# Agent-edit helpers (only used by _emit_agent_edit_lines)
# ---------------------------------------------------------------------------

# Schema-status derivation shared with resolution (batch 4, Law 5): the
# slots comment carries the explicit status for every named typed port.
_PROVISIONAL_SCHEMA_SOURCES: frozenset[str] = frozenset(
    {"comfy_registry_provisional", "workflow_json_provisional"}
)
_PORT_TYPE_TOKEN_RE = re.compile(r"[^A-Z0-9_]+")


def _schema_status_from_node(node: Any) -> str:
    """Schema status (known/provisional/unknown) derivable from the IR node."""
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, Mapping):
        return "unknown"
    source = str(metadata.get("schema_source") or "")
    ignored = metadata.get("schema_ignored") or metadata.get("ignored_evidence") or ()
    ignored = {str(item) for item in ignored}
    if source in _PROVISIONAL_SCHEMA_SOURCES or "not_runtime_validated" in ignored:
        return "provisional"
    if source:
        return "known"
    return "unknown"


def _port_type_token(socket_type: Any) -> str | None:
    """Normalize a socket type into the typed-port token (``LATENT``)."""
    if socket_type is None:
        return None
    token = _PORT_TYPE_TOKEN_RE.sub("_", str(socket_type).strip().upper()).strip("_")
    return token or None


def _node_output_specs(node: Any) -> list[dict[str, Any]]:
    """Per-slot output specs (index/name/type) from the IR node alone.

    Merges the wire ``_ui.outputs`` rows with schema-backed
    ``metadata[\"output_names\"]`` / ``metadata[\"output_types\"]`` so the
    typed port names are deterministic and provider-free at emission.
    """
    metadata = getattr(node, "metadata", None)
    if not isinstance(metadata, Mapping):
        metadata = {}
    raw_ui = metadata.get("_ui")
    ui_outputs = raw_ui.get("outputs") if isinstance(raw_ui, Mapping) else None
    schema_names = metadata.get("output_names")
    schema_types = metadata.get("output_types")
    if not isinstance(schema_names, (list, tuple)):
        schema_names = []
    if not isinstance(schema_types, (list, tuple)):
        schema_types = []

    specs: dict[int, dict[str, Any]] = {}
    if isinstance(ui_outputs, list):
        for index, output in enumerate(ui_outputs):
            if not isinstance(output, Mapping):
                continue
            slot = output.get("slot_index", index)
            try:
                slot_index = int(slot)
            except (TypeError, ValueError):
                slot_index = index
            name = output.get("name")
            specs[slot_index] = {
                "index": slot_index,
                "name": str(name) if isinstance(name, str) and name else "",
                "type": str(output.get("type") or "").strip() or None,
            }
    for index, name in enumerate(schema_names):
        entry = specs.setdefault(index, {"index": index, "name": "", "type": None})
        if not entry["name"] and isinstance(name, str) and name:
            entry["name"] = name
    for index, type_name in enumerate(schema_types):
        entry = specs.setdefault(index, {"index": index, "name": "", "type": None})
        if entry["type"] is None and type_name not in (None, "*", ""):
            entry["type"] = str(type_name)
    if not specs:
        return []
    return [specs[index] for index in sorted(specs)]


def _agent_edit_output_ports(node: Any) -> dict[int, str]:
    """Deterministic named typed ports for a node: slot -> ``LATENT_0``.

    The port name embeds the socket type (``IMAGE_0``, ``LATENT_1``) so the
    edit surface carries the type on every synthetic output reference.
    Positional ``output_N`` aliases are never emitted (Law 5, batch 4).
    """
    ports: dict[int, str] = {}
    for spec in _node_output_specs(node):
        token = _port_type_token(spec["type"])
        if token is None:
            name_token = _port_type_token(spec["name"])
            token = name_token if name_token is not None else "PORT"
        ports[spec["index"]] = f"{token}_{spec['index']}"
    return ports


def _agent_edit_output_aliases(node: Any) -> dict[int, str]:
    return _agent_edit_output_ports(node)


def _agent_edit_raw_output_names(node: Any) -> dict[int, str]:
    ui_names = _declared_ui_output_names(node)
    metadata_names = getattr(node, "metadata", {}).get("output_names") if hasattr(node, "metadata") else None
    declared_exec_outputs = _declared_exec_outputs(node)
    if declared_exec_outputs is not None:
        ui_output_count = len(ui_names) if ui_names else None
        _node_local_arity_check(node, ui_output_count)
        if ui_names:
            return {index: name for index, name in enumerate(ui_names) if name}
        return {
            index: name
            for index, (name, _type_name) in enumerate(declared_exec_outputs)
            if name
        }
    if ui_names and isinstance(metadata_names, (list, tuple)) and len(ui_names) != len(metadata_names):
        warnings.warn(
            (
                f"output arity disagreement for {node.class_type}: metadata declares "
                f"{len(metadata_names)} outputs but UI declares {len(ui_names)}. "
                "continuing with the UI output names because live/UI object_info "
                "takes precedence over stale embedded metadata."
            ),
            stacklevel=2,
        )
        return {index: name for index, name in enumerate(ui_names) if name}
    ui_output_count = len(ui_names) if ui_names else None
    _node_local_arity_check(node, ui_output_count)
    if ui_names:
        return {index: name for index, name in enumerate(ui_names) if name}
    result: dict[int, str] = {}
    if isinstance(metadata_names, (list, tuple)):
        for index, name in enumerate(metadata_names):
            if isinstance(name, str) and name:
                result[index] = name
    if result:
        return result
    schema_names = _node_local_output_names(node)
    return {index: name for index, name in enumerate(schema_names) if isinstance(name, str) and name}


def _sync_declared_exec_output_metadata(workflow_nodes: Mapping[str, Any]) -> None:
    """Keep ``vibecomfy.exec`` metadata aligned with its declared inline ``io``."""
    for node in workflow_nodes.values():
        declared_exec_outputs = _declared_exec_outputs(node)
        if declared_exec_outputs is None:
            continue
        metadata = getattr(node, "metadata", None)
        if not isinstance(metadata, dict):
            continue
        metadata["output_names"] = [name for name, _type_name in declared_exec_outputs]
        metadata["output_types"] = [output_type or "*" for _name, output_type in declared_exec_outputs]


def _title_canonical(s: str) -> str:
    return "".join(ch for ch in s.casefold() if ch.isalnum())


def _meaningful_title(
    title: str,
    class_type: str,
    var_name: str | None,
) -> str | None:
    canonical = _title_canonical(title)
    if not canonical:
        return None
    if canonical == _title_canonical(class_type):
        return None
    if var_name is not None and canonical == _title_canonical(var_name):
        return None
    return f"title:{repr(title)[1:-1]}"


def _agent_edit_comment(
    nid: str,
    node: Any,
    output_aliases: Mapping[int, str],
    *,
    var_name: str | None = None,
) -> str:
    parts: list[str] = []
    uid = str(getattr(node, "uid", "") or "")
    if uid:
        parts.append(f"uid:{uid}")
    if str(node.class_type) in _VIRTUAL_WIRE_EMITTER_CLASS_TYPES:
        parts.append("[virtual]")
    raw_ui = getattr(node, "metadata", {}).get("_ui") if hasattr(node, "metadata") else None
    if isinstance(raw_ui, Mapping):
        title = raw_ui.get("title") or raw_ui.get("name")
        if isinstance(title, str) and title:
            meaningful = _meaningful_title(title, str(node.class_type), var_name)
            if meaningful is not None:
                parts.append(meaningful)
    slot_parts = _agent_edit_slot_alias_parts(node, output_aliases)
    if slot_parts:
        parts.append("slots " + ", ".join(slot_parts))
    if not parts:
        parts.append(f"node:{nid}")
    return "  # " + " ".join(parts)


def _agent_edit_slot_alias_parts(node: Any, output_aliases: Mapping[int, str]) -> list[str]:
    """Named typed ports with explicit schema status: ``LATENT_0='LATENT' known``."""
    status = _schema_status_from_node(node)
    parts: list[str] = []
    for slot, raw_name in sorted(_agent_edit_raw_output_names(node).items()):
        port = output_aliases.get(slot)
        if port is None:
            continue
        parts.append(f"{port}={raw_name!r} {status}")
    if not parts:
        for slot, port in sorted(output_aliases.items()):
            parts.append(f"{port} {status}")
    return parts


# ---------------------------------------------------------------------------
# _emit_agent_edit_lines
# ---------------------------------------------------------------------------

def _emit_agent_edit_lines(prepared: dict[str, Any]) -> list[str]:
    from vibecomfy.identity.codec import encode_slot_names, to_python_identifier

    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
    var_names = prepared["var_names"]
    output_aliases = {
        nid: _agent_edit_output_aliases(node)
        for nid, node in workflow_nodes.items()
    }

    lines = [
        "# vibecomfy: agent-edit",
        "# Edit node assignments only; uid comments are the stable identity fallback.",
        "",
    ]
    for nid in _topological_node_order(workflow_nodes, ordering_edges_in):
        node = workflow_nodes[nid]
        var = var_names[nid]
        edge_fields = {str(edge.to_input) for edge in edges_in.get(nid, [])}
        raw_fields = [
            str(edge.to_input)
            for edge in edges_in.get(nid, [])
        ]
        raw_fields.extend(str(key) for key in node.inputs if str(key) not in edge_fields)
        raw_fields.extend(str(key) for key in node.widgets if str(key) not in edge_fields and str(key) not in node.inputs)
        input_aliases = encode_slot_names(raw_fields)

        kwargs: list[tuple[str, str, str]] = []
        for edge in sorted(edges_in.get(nid, []), key=lambda item: str(item.to_input)):
            raw_name = str(edge.to_input)
            alias = input_aliases.get(raw_name, to_python_identifier(raw_name))
            source_var = var_names.get(str(edge.from_node), _safe_var(str(edge.from_node)))
            try:
                from_slot = int(edge.from_output)
            except (TypeError, ValueError):
                from_slot = 0
            source_ports = _agent_edit_output_ports(workflow_nodes[str(edge.from_node)])
            source_alias = source_ports.get(from_slot, f"PORT_{from_slot}")
            kwargs.append((alias, f"{source_var}.{source_alias}", raw_name))

        for raw_name, value in sorted(node.inputs.items(), key=lambda item: str(item[0])):
            raw_key = str(raw_name)
            if raw_key in edge_fields or _is_link(value):
                continue
            alias = input_aliases.get(raw_key, to_python_identifier(raw_key))
            kwargs.append((alias, _format_value(value, elide_strings_over=_AGENT_EDIT_STRING_ELIDE_THRESHOLD), raw_key))

        for raw_name, value in sorted(node.widgets.items(), key=lambda item: str(item[0])):
            raw_key = str(raw_name)
            if raw_key in edge_fields:
                continue
            resolved_key = raw_key
            if raw_key.startswith("widget_"):
                try:
                    index = int(raw_key.split("_", 1)[1])
                except ValueError:
                    index = -1
                if index >= 0:
                    names = compact_widget_names_for_node(node, str(node.class_type)).names
                    if index < len(names) and names[index] is not None:
                        resolved_key = str(names[index])
                    else:
                        # Positional widget_N aliases are never emitted
                        # (Law 5, batch 4): deterministic slot_N fallback.
                        resolved_key = f"slot_{index}"
            alias = input_aliases.get(raw_key) or input_aliases.get(resolved_key) or to_python_identifier(resolved_key)
            kwargs.append((alias, _format_value(value, elide_strings_over=_AGENT_EDIT_STRING_ELIDE_THRESHOLD), resolved_key))

        comment = _agent_edit_comment(nid, node, output_aliases.get(nid, {}), var_name=var)
        call_name = str(node.class_type)
        dotted_parts = call_name.split(".")
        dotted_callable = (
            len(dotted_parts) > 1
            and all(part.isidentifier() and not keyword.iskeyword(part) for part in dotted_parts)
        )
        if (
            call_name.isidentifier()
            and not keyword.iskeyword(call_name)
        ) or dotted_callable:
            call_head = f"{var} = {call_name}("
            positional: list[str] = []
        else:
            call_head = f"{var} = node("
            positional = [_format_value(call_name)]  # call_name is a short class id; elision intentionally not applied
        rendered_args = [*positional, *[f"{alias}={expr}" for alias, expr, _raw in kwargs]]
        if not rendered_args:
            lines.append(f"{call_head}){comment}")
            continue
        single_line = f"{call_head}{', '.join(rendered_args)}){comment}"
        if len(single_line) <= 118:
            lines.append(single_line)
            continue
        lines.append(call_head)
        for arg in rendered_args:
            lines.append(f"    {arg},")
        lines.append(f"){comment}")
    return lines
