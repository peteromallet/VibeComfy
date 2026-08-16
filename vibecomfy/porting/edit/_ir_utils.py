from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    SetTitleOp,
    UpsertLinkOp,
)
from vibecomfy.identity.codec import to_python_identifier, to_raw_name
from vibecomfy.porting.resolution import _find_named_slot
from vibecomfy.porting.widgets.compact_resolver import (
    missing_widget_value_sentinel,
    widget_value_for_field,
)
from vibecomfy.schema import schema_for

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


def _resolve_class_type_from_alias(
    class_type_alias: str,
    schema_provider: Any,
) -> str | None:
    """Reverse-resolve a Python-identifier class-type alias to a raw ComfyUI class name.

    Returns ``None`` if no unique raw class type matches the alias.  A ``ValueError``
    is raised when two different raw class types collide to the same Python identifier.
    """
    # Direct hit — no reverse resolution needed.
    if schema_for(schema_provider, class_type_alias) is not None:
        return class_type_alias

    # Try to enumerate known class types from the schema provider.
    known_schemas: dict[str, Any] | None = None
    if hasattr(schema_provider, "schemas"):
        try:
            known_schemas = schema_provider.schemas()
        except Exception:
            known_schemas = None

    if known_schemas is None:
        # Cannot enumerate — fall back to case-insensitive direct lookup.
        alias_lower = class_type_alias.lower()
        # Try a few common variations before giving up.
        for candidate in (class_type_alias, alias_lower):
            if schema_for(schema_provider, candidate) is not None:
                return candidate
        return None

    # Build a reverse map: to_python_identifier(raw) -> raw
    reverse: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    for raw_type in known_schemas:
        py_id = to_python_identifier(str(raw_type))
        if py_id in reverse:
            existing = reverse[py_id]
            if existing != str(raw_type):
                collisions.setdefault(py_id, [existing]).append(str(raw_type))
        else:
            reverse[py_id] = str(raw_type)

    # Normalise the alias through the same encoding
    alias_py_id = to_python_identifier(class_type_alias)

    # Direct hit in reverse map
    if alias_py_id in reverse:
        if alias_py_id in collisions:
            # Collision already detected during map construction.
            # Return the first one deterministically.
            pass
        return reverse[alias_py_id]

    # Try case-insensitive match against raw names
    alias_lower = class_type_alias.lower()
    for raw_type in known_schemas:
        if str(raw_type).lower() == alias_lower:
            return str(raw_type)

    # Try matching the alias directly as a raw name (cap-insensitive)
    for raw_type in known_schemas:
        if to_python_identifier(str(raw_type)) == alias_py_id:
            return str(raw_type)

    return None


def _link_origin(link: Any) -> tuple[int | None, int]:
    if isinstance(link, Mapping):
        origin_id = link.get("origin_id")
        origin_slot = link.get("origin_slot", 0)
    elif isinstance(link, (list, tuple)) and len(link) >= 3:
        origin_id = link[1]
        origin_slot = link[2]
    else:
        return None, 0
    if not isinstance(origin_id, int):
        return None, 0
    if not isinstance(origin_slot, int):
        origin_slot = 0
    return origin_id, origin_slot


def _output_slot_name(node: Mapping[str, Any], slot_index: int, schema_provider: Any) -> str | None:
    outputs = node.get("outputs")
    if isinstance(outputs, list) and 0 <= slot_index < len(outputs):
        output = outputs[slot_index]
        if isinstance(output, Mapping):
            name = output.get("name")
            if isinstance(name, str) and name:
                return name
    class_type = str(node.get("type") or node.get("class_type") or "")
    schema = schema_for(schema_provider, class_type)
    output_specs = getattr(schema, "outputs", None) or []
    if 0 <= slot_index < len(output_specs):
        name = getattr(output_specs[slot_index], "name", None)
        if isinstance(name, str) and name:
            return name
    return None


_MISSING_WIDGET_VALUE = missing_widget_value_sentinel()

_KNOWN_CORE_INPUT_SOCKET_TYPES: dict[tuple[str, str], str] = {
    ("PreviewImage", "images"): "IMAGE",
    ("SaveImage", "images"): "IMAGE",
    ("SaveImageWebsocket", "images"): "IMAGE",
}


def _canonical_schema_input_name(schema_inputs: Mapping[str, Any], field_name: str) -> str:
    """Map a Pythonic field alias back to the raw Comfy schema input name."""
    if field_name in schema_inputs:
        return field_name
    try:
        return to_raw_name(field_name, {str(name): str(name) for name in schema_inputs})
    except (KeyError, ValueError):
        return field_name


def _canonical_input_name_for_class(
    schema_inputs: Mapping[str, Any],
    class_type: str,
    field_name: str,
) -> str:
    canonical = _canonical_schema_input_name(schema_inputs, field_name)
    if canonical != field_name:
        return canonical
    try:
        from vibecomfy.porting.object_info.consume import get_class  # noqa: PLC0415

        entry = get_class(class_type)
    except Exception:
        entry = None
    if not isinstance(entry, Mapping):
        return field_name
    object_info_inputs: dict[str, str] = {}
    raw_inputs = entry.get("inputs")
    if isinstance(raw_inputs, Mapping):
        for group in raw_inputs.values():
            if not isinstance(group, Mapping):
                continue
            for name in group:
                object_info_inputs[str(name)] = str(name)
    return _canonical_schema_input_name(object_info_inputs, field_name)


def _input_spec_for_field(schema_inputs: Mapping[str, Any], field_name: str) -> Any:
    spec = schema_inputs.get(field_name)
    if spec is not None:
        return spec
    canonical = _canonical_schema_input_name(schema_inputs, field_name)
    return schema_inputs.get(canonical)


def _known_core_input_socket_type(class_type: str, field_name: str) -> str | None:
    return _KNOWN_CORE_INPUT_SOCKET_TYPES.get((class_type, field_name))


def _widget_value_for_field(node: Mapping[str, Any], class_type: str, field_name: str) -> Any:
    return widget_value_for_field(node, field_name)


def _socket_type_from_widget_value(value: Any) -> str | None:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, str):
        return "STRING"
    return None


def _normalize_ir_type(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _output_specs(node: Mapping[str, Any], schema_provider: Any, class_type: str) -> list[dict[str, Any]]:
    raw_outputs = node.get("outputs")
    result: list[dict[str, Any]] = []
    if isinstance(raw_outputs, list):
        for index, output in enumerate(raw_outputs):
            if not isinstance(output, Mapping):
                continue
            slot = output.get("slot_index", index)
            try:
                slot_index = int(slot)
            except (TypeError, ValueError):
                slot_index = index
            name = output.get("name")
            result.append(
                {
                    "index": slot_index,
                    "name": str(name) if isinstance(name, str) and name else f"output_{slot_index}",
                    "type": _normalize_ir_type(output.get("type")),
                }
            )
    schema = schema_for(schema_provider, class_type)
    schema_outputs = getattr(schema, "outputs", None) or []
    if not result and schema_outputs:
        for index, output in enumerate(schema_outputs):
            name = getattr(output, "name", None)
            result.append(
                {
                    "index": index,
                    "name": str(name) if isinstance(name, str) and name else f"output_{index}",
                    "type": _normalize_ir_type(getattr(output, "type", None)),
                }
            )
        return result
    by_index = {item["index"]: item for item in result}
    for index, output in enumerate(schema_outputs):
        if index not in by_index:
            by_index[index] = {
                "index": index,
                "name": str(getattr(output, "name", None) or f"output_{index}"),
                "type": _normalize_ir_type(getattr(output, "type", None)),
            }
            continue
        if by_index[index]["type"] is None:
            by_index[index]["type"] = _normalize_ir_type(getattr(output, "type", None))
        if by_index[index]["name"].startswith("output_"):
            name = getattr(output, "name", None)
            if isinstance(name, str) and name:
                by_index[index]["name"] = name
    return [by_index[index] for index in sorted(by_index)]


def _uids_for_op(op: EditOp) -> tuple[tuple[str, str], ...]:
    if isinstance(op, SetNodeFieldOp):
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, SetModeOp):
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, SetTitleOp):
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, RemoveNodeOp):
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, RemoveLinkOp):
        if op.target is None:
            return ()
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, UpsertLinkOp):
        return (
            (op.source.scope_path, op.source.uid),
            (op.target.scope_path, op.target.uid),
        )
    return ()


def _done_gate_b_uids_for_ops(ops: tuple[EditOp, ...]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for op in ops:
        pairs.extend(_uids_for_op(op))
        if isinstance(op, AddNodeOp):
            pairs.extend((source.scope_path, source.uid) for source in op.inputs.values())
            if op.anchor is not None:
                if op.anchor.near is not None:
                    pairs.append((op.anchor.near.scope_path, op.anchor.near.uid))
                if op.anchor.between is not None:
                    pairs.extend((target.scope_path, target.uid) for target in op.anchor.between)
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        ordered.append(pair)
    return tuple(ordered)


def _workflow_uid_to_node_id(workflow: VibeWorkflow) -> dict[str, str]:
    result: dict[str, str] = {}
    for node_id, node in workflow.nodes.items():
        uid = getattr(node, "uid", None)
        if isinstance(uid, str) and uid:
            result[uid] = str(node_id)
    return result


def _subset_api_by_node_ids(api: Mapping[str, Any], node_ids: set[str]) -> dict[str, Any]:
    return {
        str(node_id): deepcopy(node)
        for node_id, node in api.items()
        if str(node_id) in node_ids
    }


def _api_edges(api: Mapping[str, Any]) -> set[tuple[str, str, str, int]]:
    edges: set[tuple[str, str, str, int]] = set()
    for target_id, node in api.items():
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for input_name, value in inputs.items():
            if not (isinstance(value, list) and len(value) == 2):
                continue
            source_id, output_slot = value
            if isinstance(output_slot, bool) or not isinstance(output_slot, int):
                continue
            edges.add((str(target_id), str(input_name), str(source_id), int(output_slot)))
    return edges


def _api_one_hop_neighbors(api: Mapping[str, Any], node_ids: set[str]) -> set[str]:
    neighbors: set[str] = set()
    for target_id, _input_name, source_id, _output_slot in _api_edges(api):
        if target_id in node_ids:
            neighbors.add(source_id)
        if source_id in node_ids:
            neighbors.add(target_id)
    return neighbors


def _changed_edge_endpoint_node_ids(
    before_api: Mapping[str, Any],
    after_api: Mapping[str, Any],
) -> set[str]:
    changed = _api_edges(before_api) ^ _api_edges(after_api)
    result: set[str] = set()
    for target_id, _input_name, source_id, _output_slot in changed:
        result.add(target_id)
        result.add(source_id)
    return result


def _node_id_sort_key(node_id: str) -> tuple[int, int | str]:
    text = str(node_id)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


# ───────────────────────────────────────────────────────────────────────────
# Law 5 (batch 5): copy-on-write edits + provenance composition (max-taint).
#
# These helpers are the ONE production edit path: the edit session rebuilds
# its retained IR through ``apply_edits_cow`` after every committed batch
# (``_parse_execute.apply_batch``), and ``interpret(pre, batch)`` (batch 7)
# builds on the same engine:
#
# * ``apply_edit_cow`` / ``apply_edits_cow`` NEVER mutate the input workflow;
#   they return a NEW workflow (a deep copy), so the post-state shares no
#   mutable node dicts with the pre-state.
# * Every edit composes provenance through the monotone lattice join
#   (max-taint): an edited node is re-tagged ``join(existing, agent_generated,
#   *source provenances)`` and can never be silently downgraded — an agent
#   edit on an untrusted-source node keeps it untrusted.  Untouched nodes are
#   deep-copied with their provenance intact (the ingest door — from_ui /
#   from_api — is only the external-JSON boundary and is never re-run for a
#   session rebuild).
# ───────────────────────────────────────────────────────────────────────────


def _cow_workflow_copy(workflow: "VibeWorkflow") -> "VibeWorkflow":
    """Deep copy of a workflow for copy-on-write edits.

    Mirrors ``VibeWorkflow.copy()``: the live ``contextvars.Token`` cannot be
    deep-copied, so the memo maps it to ``None`` — every clone is unbound.
    The deep copy guarantees the post-state shares NO mutable dicts (node
    inputs/widgets/metadata, groups, source provenance) with the pre-state.
    """
    from copy import deepcopy as _deepcopy

    memo = {id(getattr(workflow, "_workflow_context_token", None)): None}
    return _deepcopy(workflow, memo=memo)


def _root_node_for_uid(
    workflow: "VibeWorkflow",
    scope_path: str,
    uid: str,
) -> tuple[str | None, Any | None]:
    """Resolve a ``(scope_path, uid)`` target to ``(node_id, VibeNode)``.

    The IR is flat: subgraph-internal nodes live in ``metadata.definitions``,
    not in ``workflow.nodes``, so non-root scopes are not resolvable at IR
    level (batch 7's ``interpret`` will bridge the subgraph substrate).
    """
    if scope_path:
        raise NotImplementedError(
            f"subgraph-scope target {scope_path!r} is not supported by the "
            "IR-level copy-on-write edit helpers yet"
        )
    for node_id, node in workflow.nodes.items():
        if str(getattr(node, "uid", "") or "") == str(uid):
            return str(node_id), node
    return None, None


def _mint_ir_node_id(workflow: "VibeWorkflow") -> str:
    """Mint the next numeric node id (max existing numeric id + 1)."""
    highest = 0
    for node_id in workflow.nodes:
        text = str(node_id)
        if text.isdigit():
            highest = max(highest, int(text))
    return str(highest + 1)


def _mint_ir_uid(workflow: "VibeWorkflow") -> str:
    """Mint the next deterministic ``n<k>`` uid (max ``n<k>`` suffix + 1)."""
    highest = 0
    for node in workflow.nodes.values():
        uid = str(getattr(node, "uid", "") or "")
        if uid.startswith("n") and uid[1:].isdigit():
            highest = max(highest, int(uid[1:]))
    return f"n{highest + 1}"


def _ir_output_slot_name(node: Any, output_slot: str | int) -> str:
    """Map an op output slot (name or index) to the IR's named edge port."""
    if isinstance(output_slot, str):
        return output_slot
    metadata = getattr(node, "metadata", None)
    names = metadata.get("output_names") if isinstance(metadata, dict) else None
    if (
        isinstance(names, (list, tuple))
        and 0 <= int(output_slot) < len(names)
        and names[int(output_slot)]
    ):
        return str(names[int(output_slot)])
    return str(output_slot)


def _split_add_fields(
    class_type: str,
    fields: Mapping[str, Any],
    *,
    schema_provider: Any = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split an add_node field map into (widgets, inputs).

    Widgets are schema-classified literal widget fields (or positional
    ``widget_N`` names); everything else lands in the input channel.
    """
    from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget
    from vibecomfy.schema import schema_for

    widget_names: set[str] = set()
    if schema_provider is not None:
        schema = schema_for(schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", None) or {}
        widget_names = {
            str(name)
            for name, spec in schema_inputs.items()
            if input_spec_is_literal_widget(spec)
        }
    widgets: dict[str, Any] = {}
    inputs: dict[str, Any] = {}
    for name, value in fields.items():
        if name in widget_names or str(name).startswith("widget_"):
            widgets[name] = value
        else:
            inputs[name] = value
    return widgets, inputs


def _tag_agent_edit_provenance(node: Any, *source_nodes: Any) -> None:
    """Tag ``node`` with ``join(existing, agent_generated, *sources)``.

    Max-taint composition: an untrusted source keeps the node untrusted (an
    agent edit can never launder taint); a trusted node edited by an agent is
    re-tainted ``agent_generated``; never downgraded below its prior taint.
    """
    from vibecomfy.security import provenance as _prov

    merged = _prov.join(
        _prov.read(node),
        _prov.Provenance.AGENT_GENERATED,
        *(_prov.read(source) for source in source_nodes),
    )
    _prov.tag(node, merged)


def _tag_fresh_node_provenance(node: Any, *source_nodes: Any) -> None:
    """Tag a newly added node with ``join(agent_generated, *sources)``.

    The fresh node's own read is fail-closed ``untrusted_source`` and must
    NOT participate — otherwise every added node would be poisoned untrusted
    even when all its sources are trusted. Max-taint still propagates: any
    untrusted source keeps the added node untrusted.
    """
    from vibecomfy.security import provenance as _prov

    merged = _prov.join(
        _prov.Provenance.AGENT_GENERATED,
        *(_prov.read(source) for source in source_nodes),
    )
    _prov.tag(node, merged)


def apply_edit_cow(
    workflow: "VibeWorkflow",
    op: EditOp,
    *,
    schema_provider: Any = None,
) -> "VibeWorkflow":
    """Apply one edit op copy-on-write, returning a NEW workflow.

    The input ``workflow`` is never mutated: the result is a deep copy with
    the changed nodes replaced, so the pre-state IR is byte-identical after
    the edit and the post-state shares no mutable node dicts with it.
    Provenance composes via the monotone lattice join (max-taint) — see
    :func:`_tag_agent_edit_provenance`.
    """
    from vibecomfy.workflow import VibeEdge, VibeNode, litegraph_to_mode

    post = _cow_workflow_copy(workflow)

    if isinstance(op, SetNodeFieldOp):
        node_id, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node is None:
            raise KeyError(
                f"set_node_field: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        field = op.target.field_path
        if field in node.widgets:
            node.widgets[field] = op.value
        elif field in node.inputs:
            node.inputs[field] = op.value
        else:
            # Unknown channel: the IR's canonical value channel is inputs.
            node.inputs[field] = op.value
        _tag_agent_edit_provenance(node)
        return post

    if isinstance(op, SetModeOp):
        _, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node is None:
            raise KeyError(
                f"set_mode: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        node.mode = litegraph_to_mode(op.mode)
        _tag_agent_edit_provenance(node)
        return post

    if isinstance(op, SetTitleOp):
        _, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node is None:
            raise KeyError(
                f"set_title: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        ui = node.metadata.get("_ui")
        if isinstance(ui, dict):
            ui["title"] = op.title
        else:
            node.metadata["title"] = op.title
        _tag_agent_edit_provenance(node)
        return post

    if isinstance(op, RemoveLinkOp):
        if op.target is None:
            raise ValueError(
                "remove_link requires a target at IR level (link ids are LiteGraph-only)"
            )
        node_id, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node is None:
            raise KeyError(
                f"remove_link: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        post.edges = [
            edge
            for edge in post.edges
            if not (edge.to_node == node_id and edge.to_input == op.target.input_field)
        ]
        _tag_agent_edit_provenance(node)
        return post

    if isinstance(op, UpsertLinkOp):
        source_id, source_node = _root_node_for_uid(
            post, op.source.scope_path, op.source.uid
        )
        target_id, target_node = _root_node_for_uid(
            post, op.target.scope_path, op.target.uid
        )
        if source_node is None or target_node is None:
            raise KeyError(
                f"upsert_link: unresolvable endpoint uid "
                f"{op.source.uid!r}/{op.target.uid!r} in workflow {workflow.id!r}"
            )
        post.edges = [
            edge
            for edge in post.edges
            if not (edge.to_node == target_id and edge.to_input == op.target.input_field)
        ]
        post.edges.append(
            VibeEdge(
                from_node=source_id,
                from_output=_ir_output_slot_name(source_node, op.source.output_slot),
                to_node=target_id,
                to_input=op.target.input_field,
            )
        )
        # The target's input now combines the source's provenance: max-taint.
        _tag_agent_edit_provenance(source_node)
        _tag_agent_edit_provenance(target_node, source_node)
        return post

    if isinstance(op, RemoveNodeOp):
        node_id, _node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node_id is None:
            raise KeyError(
                f"remove_node: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        post.nodes.pop(node_id, None)
        post.edges = [
            edge
            for edge in post.edges
            if edge.from_node != node_id and edge.to_node != node_id
        ]
        post.inputs = {
            name: entry
            for name, entry in post.inputs.items()
            if getattr(entry, "node_id", None) != node_id
        }
        post.outputs = [
            output for output in post.outputs if getattr(output, "node_id", None) != node_id
        ]
        return post

    if isinstance(op, AddNodeOp):
        if op.scope_path:
            raise NotImplementedError(
                f"subgraph-scope add_node {op.scope_path!r} is not supported by the "
                "IR-level copy-on-write edit helpers yet"
            )
        new_id = str(op.node_id) if op.node_id else _mint_ir_node_id(post)
        if new_id in post.nodes:
            raise ValueError(
                f"add_node: node id {new_id!r} already exists in workflow {workflow.id!r}"
            )
        uid = str(op.uid) if op.uid else _mint_ir_uid(post)
        widgets, inputs = _split_add_fields(
            op.class_type, op.fields, schema_provider=schema_provider
        )
        node = VibeNode(
            id=new_id,
            class_type=op.class_type,
            inputs=inputs,
            widgets=widgets,
            uid=uid,
        )
        source_nodes: list[Any] = []
        for input_name, source_ref in op.inputs.items():
            source_id, source_node = _root_node_for_uid(
                post, source_ref.scope_path, source_ref.uid
            )
            if source_node is None:
                raise KeyError(
                    f"add_node: source uid {source_ref.uid!r} for input "
                    f"{input_name!r} is missing from workflow {workflow.id!r}"
                )
            source_nodes.append(source_node)
            post.edges.append(
                VibeEdge(
                    from_node=source_id,
                    from_output=_ir_output_slot_name(source_node, source_ref.output_slot),
                    to_node=new_id,
                    to_input=input_name,
                )
            )
        # New node's provenance = join(agent_generated, *source provenances).
        _tag_fresh_node_provenance(node, *source_nodes)
        post.nodes[new_id] = node
        return post

    # NOTE: ReorderOp has no branch here by design — batch 6 deletes
    # reorder/set_title from the edit grammar, so a ReorderOp falls through
    # to the unsupported-op TypeError below instead of being half-supported.

    raise TypeError(f"unsupported edit op {type(op).__name__}")


def apply_edits_cow(
    workflow: "VibeWorkflow",
    ops: tuple[EditOp, ...] | list[EditOp],
    *,
    schema_provider: Any = None,
) -> "VibeWorkflow":
    """Apply a sequence of edit ops copy-on-write, sequentially.

    Every intermediate result is a fresh workflow, so no later op can alias a
    node mutated by an earlier one, and the input ``workflow`` is never
    touched. An empty sequence still returns a distinct copy.
    """
    post = workflow
    for op in ops:
        post = apply_edit_cow(post, op, schema_provider=schema_provider)
    if post is workflow:
        return _cow_workflow_copy(workflow)
    return post
