from __future__ import annotations

from copy import deepcopy
import unicodedata
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    SubgraphInterfaceOp,
    UpsertLinkOp,
)
from vibecomfy.identity.codec import to_python_identifier, to_raw_name
from vibecomfy.ingest.normalize import door_get_links, door_get_nodes, door_get_widgets_values
from vibecomfy.porting.widgets.compact_resolver import (
    compact_widget_names_for_node,
    missing_widget_value_sentinel,
    widget_index_for_field,
    widget_value_for_field,
)
from vibecomfy.schema import schema_for, schemas_for

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


def _is_primitive_widget_alias_class(class_type: str) -> bool:
    """Return whether ``value`` and compact widget zero are one field."""
    return class_type in {"Float", "Int"} or class_type.startswith("Primitive")


def _has_frozen_name_row(
    node: Any,
    name_authority: Mapping[str, Sequence[str | None]] | None,
) -> bool:
    """Whether *node* has an explicit row in the supplied frozen table.

    Live editing may operate on a hand-built IR with no snapshot.  That path
    retains the historical schema fallback; a sealed row (including an empty
    unresolved row) must remain strict.  Replay itself checks missing rows
    before applying the delta, so this distinction does not reopen the gate.
    """
    if not isinstance(name_authority, Mapping):
        return False
    uid = str(getattr(node, "uid", "") or "")
    node_id = str(getattr(node, "id", "") or "")
    key = uid if uid in name_authority else node_id
    if key not in name_authority:
        return False
    row = name_authority.get(key)
    # A live authoring session may have captured an all-positional row for an
    # opaque class while the shipped object-info authority can still provide a
    # useful human field name.  Keep that authoring compatibility.  Receipt
    # replay remains strict because its artifact-backed rows carry a stable
    # source marker (or are checked by the frozen-domain gate).
    if isinstance(row, (list, tuple)) and row and all(
        value is None or (isinstance(value, str) and value.startswith("widget_"))
        for value in row
    ):
        metadata = getattr(node, "metadata", None)
        source = metadata.get("schema_source") if isinstance(metadata, Mapping) else None
        if not isinstance(source, Mapping) or source.get("provider") == "unknown":
            return False
    return True


def _write_compact_slot_mirrors(node: Any, index: int, value: Any) -> bool:
    """Write one compact slot across its parallel raw/UI carrier copies.

    ``node.widgets['widget_N']``, ``raw_widgets.values[N]`` and the retained
    ``metadata._ui`` widgets_values row are representations of the SAME
    positional slot; an assignment updates all of them or emit/compile see
    divergent values for one logical field.
    """
    wrote = False
    raw_widgets = getattr(node, "raw_widgets", None)
    raw_values = getattr(raw_widgets, "values", None)
    if isinstance(raw_values, list) and 0 <= index < len(raw_values):
        raw_values[index] = value
        wrote = True
    metadata = getattr(node, "metadata", None)
    raw_ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    ui_values = door_get_widgets_values(raw_ui) if isinstance(raw_ui, Mapping) else None
    if isinstance(ui_values, list) and 0 <= index < len(ui_values):
        ui_values[index] = value
        wrote = True
    return wrote


def _write_named_slot_aliases(
    node: Any,
    index: int,
    value: Any,
    *,
    schema_provider: Any = None,
    name_authority: Mapping[str, Sequence[str | None]] | None = None,
    strict_name_authority: bool = False,
) -> bool:
    """Keep named and positional literal carriers for one slot in sync.

    Mixed UI/API ingest can retain both ``inputs["prompt"]`` and a
    positional (or named) widget carrier for the same compact slot.  They are
    aliases of one editable field, not two independent values.  Updating only
    the first channel leaves a stale value for the agent-edit emitter to
    lower later.  Link payloads remain edge-owned and are deliberately not
    overwritten here.
    """
    resolution = compact_widget_names_for_node(
        node,
        schema_provider=schema_provider,
        name_authority=name_authority,
        strict_name_authority=strict_name_authority,
    )
    names = {f"widget_{index}"}
    if index < len(resolution.names):
        name = resolution.names[index]
        if isinstance(name, str) and name and not name.startswith("widget_"):
            names.add(name)
    wrote = False
    for channel_name in ("inputs", "widgets"):
        channel = getattr(node, channel_name, None)
        if not isinstance(channel, Mapping):
            continue
        for name in names:
            if name not in channel:
                continue
            current = channel[name]
            if isinstance(current, (list, tuple)) and len(current) == 2:
                continue
            channel[name] = value
            wrote = True
    return wrote


def _apply_primitive_widget_alias_write(
    node: Any,
    field: str,
    value: Any,
    *,
    schema_provider: Any,
    name_authority: Mapping[str, Sequence[str | None]] | None = None,
) -> bool:
    """Write every retained carrier for a primitive serialized widget.

    Primitive nodes commonly retain the same value as a named schema input,
    a positional widget, and a raw ``widgets_values`` row.  They are aliases,
    not independent fields, so an edit to either surface must update all of
    them atomically.
    """
    if not _is_primitive_widget_alias_class(str(node.class_type)):
        return False
    index = widget_index_for_field(
        node,
        field,
        schema_provider=schema_provider,
        name_authority=name_authority,
        strict_name_authority=_has_frozen_name_row(node, name_authority),
    )
    if index is None and field == "value":
        raw_values = getattr(getattr(node, "raw_widgets", None), "values", None)
        has_widget_zero = (
            "widget_0" in node.inputs
            or "widget_0" in node.widgets
            or (isinstance(raw_values, list) and bool(raw_values))
        )
        if has_widget_zero:
            index = 0
    if index is None:
        return False
    resolution = compact_widget_names_for_node(
        node,
        schema_provider=schema_provider,
        name_authority=name_authority,
        strict_name_authority=_has_frozen_name_row(node, name_authority),
    )
    named_field = resolution.names[index] if index < len(resolution.names) else None
    widget_field = f"widget_{index}"
    carrier_names = {widget_field, "value"}
    if isinstance(named_field, str) and not named_field.startswith("widget_"):
        carrier_names.add(named_field)

    wrote_carrier = False
    for carrier_name in carrier_names:
        if carrier_name in node.inputs:
            node.inputs[carrier_name] = value
            wrote_carrier = True
        if carrier_name in node.widgets:
            node.widgets[carrier_name] = value
            wrote_carrier = True

    if _write_compact_slot_mirrors(node, index, value):
        wrote_carrier = True
    return wrote_carrier


def _rewrite_positional_carrier(
    node: Any,
    field: str,
    value: Any,
    *,
    schema_provider: Any,
    name_authority: Mapping[str, Sequence[str | None]] | None = None,
) -> bool:
    """Assign a schema name onto its RETAINED positional carrier (R2).

    When ``field`` resolves to compact position N stored as
    ``widgets['widget_N']``, the rewrite targets that positional carrier
    itself.  A named key is NOT dual-written beside it: after every name
    assignment the slot has exactly one carrier.
    """
    index = widget_index_for_field(
        node,
        field,
        schema_provider=schema_provider,
        name_authority=name_authority,
        strict_name_authority=_has_frozen_name_row(node, name_authority),
    )
    if index is None:
        return False
    carrier = f"widget_{index}"
    if carrier not in getattr(node, "widgets", {}) and carrier not in getattr(
        node, "inputs", {}
    ):
        return False
    if carrier in getattr(node, "widgets", {}):
        node.widgets[carrier] = value
    elif carrier in getattr(node, "inputs", {}):
        node.inputs[carrier] = value
    _write_compact_slot_mirrors(node, index, value)
    return True


def _normalized_class_alias(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _class_alias_identifier(value: str) -> str:
    return to_python_identifier(_normalized_class_alias(value))


def _class_alias_casefold(value: str) -> str:
    return _normalized_class_alias(value).casefold()


def _resolve_class_type_from_alias(
    class_type_alias: str,
    schema_provider: Any,
    *,
    known_schemas: Mapping[str, Any] | None = None,
) -> str | None:
    """Reverse-resolve a Python-identifier class-type alias to a raw ComfyUI class name.

    Returns ``None`` if no unique raw class type matches the alias.  A ``ValueError``
    is raised when two different raw class types collide to the same Python identifier.
    """
    if known_schemas is None and hasattr(schema_provider, "schemas"):
        known_schemas = schemas_for(schema_provider)

    if isinstance(known_schemas, Mapping):
        raw_types = sorted({str(raw_type) for raw_type in known_schemas})
        by_identifier: dict[str, list[str]] = {}
        by_casefold: dict[str, list[str]] = {}
        for raw_type in raw_types:
            by_identifier.setdefault(_class_alias_identifier(raw_type), []).append(raw_type)
            by_casefold.setdefault(_class_alias_casefold(raw_type), []).append(raw_type)

        if class_type_alias in raw_types:
            return class_type_alias
        candidates = sorted(
            set(by_casefold.get(_class_alias_casefold(class_type_alias), ()))
            | set(by_identifier.get(_class_alias_identifier(class_type_alias), ()))
        )
        if len(candidates) > 1:
            raise ValueError(
                f"ambiguous class type alias {class_type_alias!r}: {', '.join(candidates)}"
            )
        if candidates:
            return candidates[0]
        if schema_for(schema_provider, class_type_alias) is not None:
            return class_type_alias

    if known_schemas is None or not isinstance(known_schemas, Mapping):
        # Cannot enumerate, so only direct or explicitly lower-case lookup is safe.
        alias_lower = class_type_alias.lower()
        for candidate in (class_type_alias, alias_lower):
            if schema_for(schema_provider, candidate) is not None:
                return candidate
        return None

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
    *,
    schema_provider: Any = None,
) -> str:
    canonical = _canonical_schema_input_name(schema_inputs, field_name)
    if canonical != field_name:
        return canonical
    if schema_provider is None:
        return field_name
    schema = schema_for(schema_provider, class_type)
    extra = getattr(schema, "inputs", None) or {}
    if not isinstance(extra, Mapping) or extra is schema_inputs:
        return field_name
    return _canonical_schema_input_name(extra, field_name)


def _input_spec_for_field(schema_inputs: Mapping[str, Any], field_name: str) -> Any:
    spec = schema_inputs.get(field_name)
    if spec is not None:
        return spec
    canonical = _canonical_schema_input_name(schema_inputs, field_name)
    return schema_inputs.get(canonical)


def _known_core_input_socket_type(class_type: str, field_name: str) -> str | None:
    return _KNOWN_CORE_INPUT_SOCKET_TYPES.get((class_type, field_name))


def _widget_value_for_field(
    node: Mapping[str, Any],
    class_type: str,
    field_name: str,
    *,
    schema_provider: Any = None,
) -> Any:
    return widget_value_for_field(node, field_name, schema_provider=schema_provider)


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
    if isinstance(op, AddNodeOp):
        pairs: list[tuple[str, str]] = []
        if op.uid:
            pairs.append((op.scope_path, str(op.uid)))
        pairs.extend(
            (source.scope_path, source.uid) for source in op.inputs.values()
        )
        return tuple(pairs)
    if isinstance(op, SubgraphInterfaceOp) and op.id:
        return (("", str(op.id)),)
    return ()


def _done_gate_b_uids_for_ops(ops: tuple[EditOp, ...]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for op in ops:
        pairs.extend(_uids_for_op(op))
        if isinstance(op, AddNodeOp):
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


def _subgraph_node_for_uid(
    workflow: "VibeWorkflow", scope_path: str, uid: str
) -> dict[str, Any] | None:
    """Resolve a retained raw subgraph node without rebuilding the IR.

    Subgraph definitions remain an opaque, lossless part of the retained IR;
    edits to their editor-native fields therefore apply copy-on-write to the
    definition payload and leave the root execution graph untouched.
    """
    from vibecomfy.identity.scope import sg_key

    definitions = getattr(workflow, "metadata", {}).get("definitions")
    if not isinstance(definitions, Mapping):
        return None
    graph: Mapping[str, Any] = definitions
    for segment in str(scope_path).split("/"):
        if not segment:
            continue
        subgraphs = graph.get("subgraphs") if isinstance(graph, Mapping) else None
        if not isinstance(subgraphs, list):
            return None
        match = next(
            (
                item
                for item in subgraphs
                if isinstance(item, Mapping) and sg_key(item) == segment
            ),
            None,
        )
        if not isinstance(match, Mapping):
            return None
        graph = match
    nodes = door_get_nodes(graph) if isinstance(graph, Mapping) else None
    if not isinstance(nodes, list):
        return None
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        properties = raw_node.get("properties")
        raw_uid = properties.get("vibecomfy_uid") if isinstance(properties, Mapping) else None
        if str(raw_uid if raw_uid is not None else raw_node.get("id")) == str(uid):
            return raw_node
    return None


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


def _edge_hint_key(from_node: Any, from_output: Any, to_node: Any, to_input: Any) -> str:
    return "\x1f".join((str(from_node), str(from_output), str(to_node), str(to_input)))


def _next_link_hint(workflow: "VibeWorkflow") -> int:
    highest = 0
    metadata = getattr(workflow, "metadata", {})
    raw_ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    if not isinstance(raw_ui, Mapping):
        door = metadata.get("_ui_door") if isinstance(metadata, Mapping) else None
        raw_ui = door.get("top") if isinstance(door, Mapping) else None
    raw_links = door_get_links(raw_ui) if isinstance(raw_ui, Mapping) else None
    if isinstance(raw_links, list):
        for link in raw_links:
            if isinstance(link, (list, tuple)) and link and isinstance(link[0], int):
                highest = max(highest, link[0])
            elif isinstance(link, Mapping) and isinstance(link.get("id"), int):
                highest = max(highest, link["id"])
    hints = metadata.get("_edit_link_id_hints") if isinstance(metadata, Mapping) else None
    if isinstance(hints, Mapping):
        highest = max((int(value) for value in hints.values() if str(value).isdigit()), default=highest)
    return highest + 1


def _record_link_hint(workflow: "VibeWorkflow", edge: Any, link_id: int) -> None:
    hints = workflow.metadata.setdefault("_edit_link_id_hints", {})
    hints[_edge_hint_key(edge.from_node, edge.from_output, edge.to_node, edge.to_input)] = int(link_id)


def _captured_link_id_for_edge(workflow: "VibeWorkflow", edge: Any) -> int | None:
    metadata = getattr(workflow, "metadata", {})
    raw_ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    door = None
    if not isinstance(raw_ui, Mapping):
        door = metadata.get("_ui_door") if isinstance(metadata, Mapping) else None
        raw_ui = door.get("top") if isinstance(door, Mapping) else None
    raw_links = door_get_links(raw_ui) if isinstance(raw_ui, Mapping) else None
    if not isinstance(raw_links, list):
        return None

    raw_nodes = door_get_nodes(raw_ui) if isinstance(raw_ui, Mapping) else None
    if not isinstance(raw_nodes, (list, Mapping)) and isinstance(door, Mapping):
        raw_nodes = door_get_nodes(door)

    def _slot_index(node_id: str, field: str, *, output: bool) -> int | None:
        if str(field).isdigit():
            return int(field)
        if not isinstance(raw_nodes, (list, Mapping)):
            return None
        node_values = raw_nodes.values() if isinstance(raw_nodes, Mapping) else raw_nodes
        for node in node_values:
            if not isinstance(node, Mapping) or str(node.get("id")) != str(node_id):
                continue
            entries = node.get("outputs" if output else "inputs")
            if not isinstance(entries, list):
                return None
            for index, entry in enumerate(entries):
                if isinstance(entry, Mapping) and str(entry.get("name")) == str(field):
                    return index
        return None

    source_slot = _slot_index(edge.from_node, edge.from_output, output=True)
    target_slot = _slot_index(edge.to_node, edge.to_input, output=False)
    for link in raw_links:
        if isinstance(link, (list, tuple)) and len(link) >= 6:
            if (
                str(link[1]) == str(edge.from_node)
                and source_slot is not None
                and int(link[2]) == source_slot
                and str(link[3]) == str(edge.to_node)
                and target_slot is not None
                and int(link[4]) == target_slot
            ):
                return int(link[0]) if isinstance(link[0], int) else None
    return None


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


def _ir_output_slot_index(node: Any, output_slot: str | int) -> str:
    """Map an IR edge output port back to a numeric slot index (as str).

    The compile oracle requires numeric output slots on runtime nodes, while
    interpret-written edges carry named ports (type-token aliases such as
    ``CONDITIONING_0`` or raw output names).  This resolves a named port to
    its positional index via the node's live metadata (``output_names``
    first, then the captured ``_ui`` outputs, then the ``output_types`` /
    ``_ui`` output ``type`` tokens for typed aliases whose trailing integer
    is the positional index).  Numeric ports pass through unchanged;
    unresolvable names stay as-is so the compile error is reported honestly.
    """
    if not isinstance(output_slot, str):
        return str(output_slot)
    if output_slot.isdigit():
        return output_slot
    metadata = getattr(node, "metadata", None)
    names: tuple | list = ()
    outputs: tuple | list = ()
    output_types: tuple | list = ()
    if isinstance(metadata, Mapping):
        raw_names = metadata.get("output_names")
        if isinstance(raw_names, (list, tuple)):
            names = raw_names
        raw_types = metadata.get("output_types")
        if isinstance(raw_types, (list, tuple)):
            output_types = raw_types
        ui = metadata.get("_ui")
        ui_outputs = ui.get("outputs") if isinstance(ui, Mapping) else None
        if isinstance(ui_outputs, (list, tuple)):
            outputs = ui_outputs

    def _find(name: str, *, casefold: bool = False) -> str | None:
        for index, candidate in enumerate(names):
            if str(candidate) == name or (
                casefold and str(candidate).casefold() == name.casefold()
            ):
                return str(index)
        for index, output in enumerate(outputs):
            if isinstance(output, Mapping):
                candidate = str(output.get("name", ""))
                if candidate == name or (
                    casefold and candidate.casefold() == name.casefold()
                ):
                    return str(index)
        return None

    found = _find(output_slot)
    if found is not None:
        return found
    import re as _re

    typed = _re.fullmatch(r"^([A-Za-z_][A-Za-z0-9_]*)_(\d+)$", output_slot)
    if typed is not None:
        base = typed.group(1)
        index = int(typed.group(2))
        # Type-token aliases are generated as ``f"{TYPE}_{position}"`` (see
        # interpret._agent_edit_output_ports), so the trailing integer IS the
        # positional output index.  Verify it against the live metadata so a
        # raw name that merely looks typed is not misread.
        if 0 <= index < len(output_types) and str(output_types[index]).casefold() == base.casefold():
            return str(index)
        if 0 <= index < len(outputs):
            output = outputs[index]
            if isinstance(output, Mapping) and str(output.get("type", "")).casefold() == base.casefold():
                return str(index)
        found = _find(base, casefold=True)
        if found is not None:
            return found
        # ``unknown_N`` is the renderer's positional alias for an output row
        # with no usable name/type evidence.  Reuse the canonical authority so
        # only an evidence-backed row is projected into compile's numeric-only
        # edge representation; invalid aliases remain visible to the compile
        # oracle and fail closed there.
        if base.casefold() == "unknown":
            from vibecomfy.porting.edit._interpret import canonical_renderer_output

            if canonical_renderer_output(node, output_slot) is not None:
                return str(index)
    return output_slot


def _compile_ready_workflow_copy(workflow: "VibeWorkflow") -> "VibeWorkflow":
    """Return a COW copy whose edges carry numeric output slots for compile.

    The retained IR is the authority and keeps named edge ports; the compile
    oracle (``VibeWorkflow.compile("api")``) requires numeric output slots on
    runtime nodes.  This projection rewrites only the edge ports on a copy so
    Gate B can compile the retained IR without mutating it.
    """
    from vibecomfy.workflow import VibeEdge

    post = _cow_workflow_copy(workflow)
    new_edges: list[Any] = []
    for edge in post.edges:
        source = post.nodes.get(str(getattr(edge, "from_node", "")))
        output = edge.from_output
        if source is not None:
            output = _ir_output_slot_index(source, output)
        new_edges.append(
            VibeEdge(edge.from_node, output, edge.to_node, edge.to_input)
        )
    post.edges = new_edges
    return post


def _split_add_fields(
    class_type: str,
    fields: Mapping[str, Any],
    *,
    schema_provider: Any = None,
    widget_field_names: Sequence[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split an add_node field map into (widgets, inputs).

    Widgets are schema-classified literal widget fields (or positional
    ``widget_N`` names).  ``widget_field_names`` (set by ``diff`` from the
    post node's instance widgets channel) takes precedence so unknown-schema
    widget fields survive the diff→interpret round-trip: the batch carries
    the channel classification the instance hydration (batch 6) yields, and
    this restores exactly those names to the widget channel.
    """
    from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget
    from vibecomfy.schema import schema_for

    explicit_widget_names = (
        frozenset(str(name) for name in widget_field_names)
        if widget_field_names
        else frozenset()
    )
    widget_names: set[str] = set(explicit_widget_names)
    if schema_provider is not None:
        schema = schema_for(schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", None) or {}
        widget_names.update(
            str(name)
            for name, spec in schema_inputs.items()
            if input_spec_is_literal_widget(spec)
        )
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
    # P0-WIDGET-CANON: the sealed snapshot table is the sole name authority
    # for name→slot resolution during apply (and therefore replay).
    from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid  # noqa: PLC0415

    name_authority = frozen_widget_names_by_uid(workflow)

    if isinstance(op, SetNodeFieldOp):
        node_id, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if op.target.scope_path:
            raise NotImplementedError(
                f"subgraph field target {op.target.scope_path!r} is not supported by "
                "the retained IR edit surface"
            )
        if node is None:
            raise KeyError(
                f"set_node_field: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        field = op.target.field_path
        # Keep named and positional aliases synchronized in the frozen domain.
        slot_index = widget_index_for_field(
            node,
            field,
            schema_provider=schema_provider,
            name_authority=name_authority,
            strict_name_authority=_has_frozen_name_row(node, name_authority),
        )
        if slot_index is not None:
            _write_compact_slot_mirrors(node, slot_index, op.value)
            _write_named_slot_aliases(
                node,
                slot_index,
                op.value,
                schema_provider=schema_provider,
                name_authority=name_authority,
                strict_name_authority=_has_frozen_name_row(node, name_authority),
            )
        # A literal assignment is also the explicit unlink operation for a
        # widget-backed input.  The retained IR has one edge authority, so
        # remove the incoming edge before materializing the literal value.
        post.edges = [
            edge
            for edge in post.edges
            if not (edge.to_node == node_id and edge.to_input == field)
        ]
        if _apply_primitive_widget_alias_write(
            node,
            field,
            op.value,
            schema_provider=schema_provider,
            name_authority=name_authority,
        ):
            pass
        elif field in node.widgets:
            node.widgets[field] = op.value
        elif field in node.inputs:
            node.inputs[field] = op.value
        elif _rewrite_positional_carrier(
            node,
            field,
            op.value,
            schema_provider=schema_provider,
            name_authority=name_authority,
        ):
            # R2: the schema name's slot was stored positionally; the
            # positional carrier itself was rewritten — no dual-write.
            pass
        else:
            # Unknown channel: the IR's canonical value channel is inputs.
            node.inputs[field] = op.value
        _tag_agent_edit_provenance(node)
        return post

    if isinstance(op, SetModeOp):
        if op.target.scope_path:
            raw_node = _subgraph_node_for_uid(post, op.target.scope_path, op.target.uid)
            if raw_node is None:
                raise KeyError(
                    f"set_mode: no retained subgraph node for uid {op.target.uid!r}"
                )
            raw_node["mode"] = int(op.mode)
            return post
        _, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node is None:
            raise KeyError(
                f"set_mode: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        node.mode = litegraph_to_mode(op.mode)
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
        replacement = VibeEdge(
            from_node=source_id,
            from_output=_ir_output_slot_name(source_node, op.source.output_slot),
            to_node=target_id,
            to_input=op.target.input_field,
        )
        post.edges.append(replacement)
        _record_link_hint(post, replacement, _next_link_hint(post))
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
        removed_class = str(getattr(_node, "class_type", "") or "")
        incoming = [edge for edge in post.edges if edge.to_node == node_id]
        outgoing = [edge for edge in post.edges if edge.from_node == node_id]
        post.nodes.pop(node_id, None)
        post.edges = [
            edge
            for edge in post.edges
            if edge.from_node != node_id and edge.to_node != node_id
        ]
        if removed_class == "Reroute" and incoming and outgoing:
            rewired_edges = [
                VibeEdge(
                    from_node=in_edge.from_node,
                    from_output=in_edge.from_output,
                    to_node=out_edge.to_node,
                    to_input=out_edge.to_input,
                )
                for in_edge in incoming
                for out_edge in outgoing
            ]
            post.edges.extend(rewired_edges)
            for rewired, outgoing_edge in zip(rewired_edges, outgoing):
                captured_id = _captured_link_id_for_edge(workflow, outgoing_edge)
                if captured_id is not None:
                    _record_link_hint(post, rewired, captured_id)
        post.inputs = {
            name: entry
            for name, entry in post.inputs.items()
            if getattr(entry, "node_id", None) != node_id
        }
        post.outputs = [
            output for output in post.outputs if getattr(output, "node_id", None) != node_id
        ]
        return post

    if isinstance(op, SubgraphInterfaceOp):
        definitions = post.metadata.get("definitions")
        if not isinstance(definitions, dict):
            definitions = {}
            post.metadata["definitions"] = definitions
        subgraphs = definitions.get("subgraphs")
        if not isinstance(subgraphs, list):
            subgraphs = []
            definitions["subgraphs"] = subgraphs
        subgraph_id = str(op.id) if op.id else op.name

        def _entry_key(entry: Any) -> str:
            if isinstance(entry, Mapping):
                return str(entry.get("id") or entry.get("name") or "")
            return str(entry)

        if op.action == "remove":
            definitions["subgraphs"] = [
                entry for entry in subgraphs if _entry_key(entry) != subgraph_id
            ]
            return post
        signature = {
            "id": subgraph_id,
            "name": op.name,
            "inputs": [
                {
                    "name": str(port[0]),
                    "type": port[1] if len(port) > 1 else None,
                    "label": str(port[0]),
                }
                for port in op.inputs
                if isinstance(port, (list, tuple)) and port
            ],
            "outputs": [
                {
                    "name": str(port[0]),
                    "type": port[1] if len(port) > 1 else None,
                }
                for port in op.outputs
                if isinstance(port, (list, tuple)) and port
            ],
        }
        if op.action == "change":
            replaced = False
            updated: list[Any] = []
            for existing in subgraphs:
                if _entry_key(existing) == subgraph_id:
                    merged = dict(existing) if isinstance(existing, Mapping) else {}
                    merged.update(signature)
                    updated.append(merged)
                    replaced = True
                else:
                    updated.append(existing)
            if not replaced:
                updated.append({**signature, "nodes": [], "links": []})
            definitions["subgraphs"] = updated
        else:  # add
            definitions["subgraphs"] = [
                *subgraphs,
                {**signature, "nodes": [], "links": []},
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
            op.class_type,
            op.fields,
            schema_provider=schema_provider,
            widget_field_names=op.widget_field_names,
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
            added_edge = VibeEdge(
                    from_node=source_id,
                    from_output=_ir_output_slot_name(source_node, source_ref.output_slot),
                    to_node=new_id,
                    to_input=input_name,
                )
            post.edges.append(added_edge)
            _record_link_hint(post, added_edge, _next_link_hint(post))
        # New node's provenance = join(agent_generated, *source provenances).
        _tag_fresh_node_provenance(node, *source_nodes)
        post.nodes[new_id] = node
        return post

    # NOTE: reorder / set_title are not part of the designed grammar and are
    # rejected at parse time; they have no branches here.

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
