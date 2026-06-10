from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.edit_ops import (
    AddNodeOp,
    EditOp,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.resolution import _find_named_slot
from vibecomfy.porting.widget_schema import effective_widget_names_for_class
from vibecomfy.schema import schema_for

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


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


_MISSING_WIDGET_VALUE = object()


def _widget_value_for_field(node: Mapping[str, Any], class_type: str, field_name: str) -> Any:
    widgets_values = node.get("widgets_values")
    if isinstance(widgets_values, Mapping):
        return widgets_values[field_name] if field_name in widgets_values else _MISSING_WIDGET_VALUE
    if isinstance(widgets_values, list):
        widget_names = effective_widget_names_for_class(class_type, allow_object_info_fallback=True)
        for index, name in enumerate(widget_names):
            if name == field_name and index < len(widgets_values):
                return widgets_values[index]
    return _MISSING_WIDGET_VALUE


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
