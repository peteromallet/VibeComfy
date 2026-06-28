from __future__ import annotations

import keyword
from typing import Any, Mapping

from vibecomfy._compile._helpers import RESOLVABLE_HELPER_CLASS_TYPES
from vibecomfy.errors import ArityDisagreementError, ConversionParityError
from vibecomfy.porting.object_info import require_class_output_count
from vibecomfy.porting.object_info import output_names as class_output_names
from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.emit.emit_kwargs import _declared_ui_output_names
from vibecomfy.porting.emit.format_values import _format_value
from vibecomfy.porting.emit.naming_codegen import (
    _apply_locked_variable_names,
    _compute_output_variable_names,
    _compute_variable_names,
    _id_sort_key,
    _safe_var,
    _topological_node_order,
)
from vibecomfy.porting.emit.node_kwargs_core import _is_link, _ui_widget_aliases
from vibecomfy.porting.emit.subgraph_defs import _SubgraphDef
from vibecomfy.porting.emit.subgraph_defs import _subgraph_emitted_node_id
from vibecomfy.porting.emit.wrappers import UI_ONLY_CLASS_TYPES


_AGENT_EDIT_STRING_ELIDE_THRESHOLD = 400


_OUTPUT_CLASSES: dict[str, tuple[str, str]] = {
    "SaveImage": ("image", "image/png"),
    "PreviewImage": ("image", "image/png"),
    "SaveVideo": ("video", "video/mp4"),
    "VHS_VideoCombine": ("video", "video/mp4"),
    "SaveAudio": ("audio", "audio/wav"),
    "SaveAudioMP3": ("audio", "audio/mpeg"),
}


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


_VIRTUAL_WIRE_EMITTER_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})


def _prepare_workflow_for_emit(
    workflow: Any,
    *,
    apply_overrides: dict[str, Any] | None,
    template_id: str | None = None,
    keep_virtual_wires: bool = False,
    prune_dead_branches: bool = True,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
    diagnostics: list[EmissionDiagnostic] | None = None,
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
        from vibecomfy.porting.emit.emit_ready import _apply_overrides  # noqa: PLC0415

        _apply_overrides(workflow_nodes, edges_in, apply_overrides.get("patches") or [])

    # Dead-branch pruning produces minimal templates for authoring, but it drops
    # nodes that don't feed a recognized output (e.g. a GeminiNode whose only
    # consumer is a PreviewAny). When emitting a faithful scratchpad of a user's
    # live canvas (agent-edit), pruning must be disabled so every node survives.
    if prune_dead_branches:
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
            source_alias = output_aliases.get(str(edge.from_node), {}).get(from_slot)
            if source_alias is None:
                source_alias = to_python_identifier(f"output_{from_slot}")
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
                aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
                resolved = resolve_widget_key_with_provenance(str(node.class_type), raw_key, input_aliases=aliases)
                if resolved.name is not None:
                    resolved_key = resolved.name
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


def _agent_edit_output_aliases(node: Any) -> dict[int, str]:
    from vibecomfy.identity.codec import encode_slot_names, to_python_identifier

    output_names = _agent_edit_raw_output_names(node)
    if not output_names:
        ui_names = _declared_ui_output_names(node)
        ui_output_count = len(ui_names) if ui_names else None
        count = _node_local_arity_check(node, ui_output_count) or 0
        output_names = {slot: f"output_{slot}" for slot in range(count)}
    encoded = encode_slot_names(output_names.values())
    return {
        slot: encoded.get(raw_name, to_python_identifier(raw_name))
        for slot, raw_name in output_names.items()
    }


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
        raise ArityDisagreementError(
            (
                f"output arity disagreement for {node.class_type}: metadata declares "
                f"{len(metadata_names)} outputs but UI declares {len(ui_names)}. "
                "Refresh the object_info schema snapshot."
            ),
            class_type=str(node.class_type),
            snapshot_pack=None,
            snapshot_version=None,
            snapshot_output_count=len(metadata_names),
            ui_output_count=len(ui_names),
        )
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
    schema_names = class_output_names(str(node.class_type))
    return {index: name for index, name in enumerate(schema_names) if isinstance(name, str) and name}


def _declared_exec_outputs(node: Any) -> list[tuple[str, str | None]] | None:
    from vibecomfy.porting.emit.emit_ready import _declared_exec_outputs as _impl  # noqa: PLC0415

    return _impl(node)


def _node_local_output_names(node: Any) -> list[str]:
    from vibecomfy.porting.emit.emit_ready import _node_local_output_names as _impl  # noqa: PLC0415

    return _impl(node)


def _node_local_arity_check(node: Any, ui_output_count: int | None) -> int:
    from vibecomfy.porting.emit.emit_ready import _node_local_arity_check as _impl  # noqa: PLC0415

    return _impl(node, ui_output_count)


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
    parts: list[str] = []
    for slot, raw_name in sorted(_agent_edit_raw_output_names(node).items()):
        alias = output_aliases.get(slot)
        if alias and alias != raw_name:
            parts.append(f"{alias}={raw_name!r}")
    return parts


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
