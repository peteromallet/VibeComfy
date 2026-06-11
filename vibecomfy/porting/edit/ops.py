from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from vibecomfy.comfy_nodes.agent_provider import (
    MalformedModelJSON,
    MissingRequiredField,
)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_RELATIONS = frozenset({"near", "right_of", "below", "between"})
_REORDER_AXES = frozenset({"widgets", "slots"})
_SET_MODE_VALUES = frozenset({0, 2, 4})
_FORBIDDEN_RAW_NODE_KEYS = frozenset({"node", "raw_node", "node_payload"})
_FORBIDDEN_RAW_LINK_KEYS = frozenset({"link", "raw_link", "link_payload"})
_ALLOWED_RESPONSE_KEYS = frozenset({"delta", "message"})

EDIT_OP_RESPONSE_SCHEMA_V2: dict[str, Any] = {
    "type": "object",
    "required": ["delta", "message"],
    "additionalProperties": False,
    "properties": {
        "message": {"type": "string"},
        "delta": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["op"],
                # Enumerate the EXACT allowed op names. Without this the schema only
                # constrained op SHAPES (required keys), never the op vocabulary, so
                # models invented plausible-but-invalid names (e.g. "add_scoped_node"
                # instead of "add_node"), which the apply stage then rejected. The
                # enum + the per-shape oneOf together pin both the name and the shape.
                "properties": {
                    "op": {
                        "enum": [
                            "set_node_field",
                            "add_node",
                            "remove_node",
                            "upsert_link",
                            "remove_link",
                            "reorder",
                            "set_mode",
                        ]
                    }
                },
                "oneOf": [
                    {"type": "object", "required": ["op", "target", "value"]},
                    {"type": "object", "required": ["op", "scope_path", "class_type", "fields"]},
                    {"type": "object", "required": ["op", "target"]},
                    {"type": "object", "required": ["op", "from", "to"]},
                    {"type": "object", "required": ["op", "target", "axis", "order"]},
                    {"type": "object", "required": ["op", "target", "mode"]},
                ],
            },
        },
    },
}


class EditOpParseError(ValueError):
    """Raised when a v2 edit delta or response does not match the typed contract."""


@dataclass(frozen=True, slots=True)
class NodeTarget:
    scope_path: str
    uid: str


@dataclass(frozen=True, slots=True)
class NodeFieldTarget(NodeTarget):
    field_path: str


@dataclass(frozen=True, slots=True)
class LinkSourceRef:
    scope_path: str
    uid: str
    output_slot: str | int


@dataclass(frozen=True, slots=True)
class LinkTargetRef:
    scope_path: str
    uid: str
    input_field: str


@dataclass(frozen=True, slots=True)
class AnchorRef:
    relation: Literal["near", "right_of", "below", "between"]
    near: NodeTarget | None = None
    between: tuple[NodeTarget, NodeTarget] | None = None
    group_title: str | None = None


@dataclass(frozen=True, slots=True)
class SetNodeFieldOp:
    op: Literal["set_node_field"]
    target: NodeFieldTarget
    value: Any


@dataclass(frozen=True, slots=True)
class AddNodeOp:
    op: Literal["add_node"]
    scope_path: str
    class_type: str
    fields: Mapping[str, Any]
    inputs: Mapping[str, LinkSourceRef]
    anchor: AnchorRef | None = None


@dataclass(frozen=True, slots=True)
class RemoveNodeOp:
    op: Literal["remove_node"]
    target: NodeTarget


@dataclass(frozen=True, slots=True)
class UpsertLinkOp:
    op: Literal["upsert_link"]
    source: LinkSourceRef
    target: LinkTargetRef


@dataclass(frozen=True, slots=True)
class RemoveLinkOp:
    op: Literal["remove_link"]
    link_id: int | None = None
    target: LinkTargetRef | None = None


@dataclass(frozen=True, slots=True)
class ReorderOp:
    op: Literal["reorder"]
    target: NodeTarget
    axis: Literal["widgets", "slots"]
    order: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SetModeOp:
    op: Literal["set_mode"]
    target: NodeTarget
    mode: Literal[0, 2, 4]


EditOp = (
    SetNodeFieldOp
    | AddNodeOp
    | RemoveNodeOp
    | UpsertLinkOp
    | RemoveLinkOp
    | ReorderOp
    | SetModeOp
)


@dataclass(frozen=True)
class AgentDeltaTurnResult:
    delta: tuple[EditOp, ...]
    message: str
    route: str
    model: str | None = None
    audit_metadata: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "delta": [op_to_dict(op) for op in self.delta],
            "message": self.message,
            "route": self.route,
            "model": self.model,
            "audit_metadata": dict(self.audit_metadata or {}),
        }


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        match = _JSON_FENCE_RE.search(stripped)
        if match:
            stripped = match.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        # Models (esp. on complex edits) often emit the delta object followed by
        # EXTRA data — a second object, trailing prose, or stray reasoning — which
        # makes a strict json.loads raise "Extra data" and fail the whole turn.
        # Recover by decoding the FIRST complete JSON object from the first '{' and
        # ignoring the trailing content, rather than discarding a valid delta.
        start = stripped.find("{")
        if start == -1:
            raise MalformedModelJSON(
                "Agent response was not valid JSON with keys `delta` and `message`."
            ) from exc
        try:
            parsed, _ = json.JSONDecoder().raw_decode(stripped[start:])
        except json.JSONDecodeError:
            raise MalformedModelJSON(
                "Agent response was not valid JSON with keys `delta` and `message`."
            ) from exc
    if not isinstance(parsed, dict):
        raise MalformedModelJSON("Agent response must be a JSON object.")
    return parsed


def _require_mapping(value: Any, *, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EditOpParseError(f"{path} must be an object.")
    return dict(value)


def _require_string(value: Any, *, path: str, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise EditOpParseError(f"{path} must be a string.")
    if not allow_empty and not value:
        raise EditOpParseError(f"{path} must be a non-empty string.")
    return value


def _require_target_tuple(
    value: Any,
    *,
    path: str,
    expected_len: int,
) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EditOpParseError(f"{path} must be a list of length {expected_len}.")
    items = list(value)
    if len(items) != expected_len:
        raise EditOpParseError(f"{path} must be a list of length {expected_len}.")
    return items


def _parse_node_target(value: Any, *, path: str) -> NodeTarget:
    scope_path, uid = _require_target_tuple(value, path=path, expected_len=2)
    return NodeTarget(
        scope_path=_require_string(scope_path, path=f"{path}[0]", allow_empty=True),
        uid=_require_string(uid, path=f"{path}[1]"),
    )


def _parse_node_field_target(value: Any, *, path: str) -> NodeFieldTarget:
    scope_path, uid, field_path = _require_target_tuple(value, path=path, expected_len=3)
    return NodeFieldTarget(
        scope_path=_require_string(scope_path, path=f"{path}[0]", allow_empty=True),
        uid=_require_string(uid, path=f"{path}[1]"),
        field_path=_require_string(field_path, path=f"{path}[2]"),
    )


def _parse_link_source(value: Any, *, path: str) -> LinkSourceRef:
    scope_path, uid, output_slot = _require_target_tuple(value, path=path, expected_len=3)
    if isinstance(output_slot, bool) or not isinstance(output_slot, (int, str)):
        raise EditOpParseError(f"{path}[2] must be a slot name or integer.")
    if isinstance(output_slot, str) and not output_slot:
        raise EditOpParseError(f"{path}[2] must be a non-empty slot name.")
    return LinkSourceRef(
        scope_path=_require_string(scope_path, path=f"{path}[0]", allow_empty=True),
        uid=_require_string(uid, path=f"{path}[1]"),
        output_slot=output_slot,
    )


def _parse_link_target(value: Any, *, path: str) -> LinkTargetRef:
    scope_path, uid, input_field = _require_target_tuple(value, path=path, expected_len=3)
    return LinkTargetRef(
        scope_path=_require_string(scope_path, path=f"{path}[0]", allow_empty=True),
        uid=_require_string(uid, path=f"{path}[1]"),
        input_field=_require_string(input_field, path=f"{path}[2]"),
    )


def _parse_anchor(value: Any, *, path: str) -> AnchorRef:
    data = _require_mapping(value, path=path)
    relation = _require_string(data.get("relation"), path=f"{path}.relation")
    if relation not in _RELATIONS:
        allowed = ", ".join(sorted(_RELATIONS))
        raise EditOpParseError(f"{path}.relation must be one of: {allowed}.")
    group_title = data.get("group_title")
    if group_title is not None:
        group_title = _require_string(group_title, path=f"{path}.group_title")
    near = data.get("near")
    between = data.get("between")
    parsed_near = _parse_node_target(near, path=f"{path}.near") if near is not None else None
    parsed_between: tuple[NodeTarget, NodeTarget] | None = None
    if between is not None:
        items = _require_target_tuple(between, path=f"{path}.between", expected_len=2)
        parsed_between = (
            _parse_node_target(items[0], path=f"{path}.between[0]"),
            _parse_node_target(items[1], path=f"{path}.between[1]"),
        )
    if relation == "between":
        if parsed_between is None:
            raise EditOpParseError(f"{path}.between is required when relation is 'between'.")
    elif parsed_near is None and group_title is None:
        raise EditOpParseError(
            f"{path} must include `near` or `group_title` for relation {relation!r}."
        )
    return AnchorRef(
        relation=relation,  # type: ignore[arg-type]
        near=parsed_near,
        between=parsed_between,
        group_title=group_title,
    )


def _reject_forbidden_keys(data: Mapping[str, Any], *, path: str, keys: frozenset[str]) -> None:
    seen = sorted(key for key in data if key in keys)
    if seen:
        joined = ", ".join(seen)
        raise EditOpParseError(f"{path} contains unsupported raw payload field(s): {joined}.")


def _parse_fields(value: Any, *, path: str) -> dict[str, Any]:
    fields = _require_mapping(value, path=path)
    for key in fields:
        _require_string(key, path=f"{path}.<key>")
    return fields


def _parse_inputs(value: Any, *, path: str) -> dict[str, LinkSourceRef]:
    if value is None:
        return {}
    inputs = _require_mapping(value, path=path)
    parsed: dict[str, LinkSourceRef] = {}
    for key, ref in inputs.items():
        field = _require_string(key, path=f"{path}.<key>")
        parsed[field] = _parse_link_source(ref, path=f"{path}.{field}")
    return parsed


def _parse_reorder_order(value: Any, *, path: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EditOpParseError(f"{path} must be a list of field names.")
    parsed: list[str] = []
    for index, item in enumerate(value):
        parsed.append(_require_string(item, path=f"{path}[{index}]"))
    if not parsed:
        raise EditOpParseError(f"{path} must not be empty.")
    if len(set(parsed)) != len(parsed):
        raise EditOpParseError(f"{path} must not contain duplicate entries.")
    return tuple(parsed)


def parse_edit_op(payload: Mapping[str, Any]) -> EditOp:
    data = dict(payload)
    op_name = _require_string(data.get("op"), path="op")

    if op_name == "set_node_field":
        return SetNodeFieldOp(
            op="set_node_field",
            target=_parse_node_field_target(data.get("target"), path="target"),
            value=data.get("value"),
        )

    if op_name == "add_node":
        _reject_forbidden_keys(data, path="add_node", keys=_FORBIDDEN_RAW_NODE_KEYS)
        return AddNodeOp(
            op="add_node",
            scope_path=_require_string(data.get("scope_path"), path="scope_path", allow_empty=True),
            class_type=_require_string(data.get("class_type"), path="class_type"),
            fields=_parse_fields(data.get("fields"), path="fields"),
            inputs=_parse_inputs(data.get("inputs"), path="inputs"),
            anchor=_parse_anchor(data["anchor"], path="anchor") if "anchor" in data else None,
        )

    if op_name == "remove_node":
        return RemoveNodeOp(
            op="remove_node",
            target=_parse_node_target(data.get("target"), path="target"),
        )

    if op_name == "upsert_link":
        _reject_forbidden_keys(data, path="upsert_link", keys=_FORBIDDEN_RAW_LINK_KEYS)
        return UpsertLinkOp(
            op="upsert_link",
            source=_parse_link_source(data.get("from"), path="from"),
            target=_parse_link_target(data.get("to"), path="to"),
        )

    if op_name == "remove_link":
        _reject_forbidden_keys(data, path="remove_link", keys=_FORBIDDEN_RAW_LINK_KEYS)
        link_id = data.get("id")
        target = data.get("to")
        if link_id is None and target is None:
            raise EditOpParseError("remove_link requires either `id` or `to`.")
        if link_id is not None and target is not None:
            raise EditOpParseError("remove_link accepts only one of `id` or `to`.")
        if link_id is not None:
            if isinstance(link_id, bool) or not isinstance(link_id, int):
                raise EditOpParseError("remove_link.id must be an integer.")
        return RemoveLinkOp(
            op="remove_link",
            link_id=link_id,
            target=_parse_link_target(target, path="to") if target is not None else None,
        )

    if op_name == "reorder":
        axis = _require_string(data.get("axis"), path="axis")
        if axis not in _REORDER_AXES:
            allowed = ", ".join(sorted(_REORDER_AXES))
            raise EditOpParseError(f"axis must be one of: {allowed}.")
        return ReorderOp(
            op="reorder",
            target=_parse_node_target(data.get("target"), path="target"),
            axis=axis,  # type: ignore[arg-type]
            order=_parse_reorder_order(data.get("order"), path="order"),
        )

    if op_name == "set_mode":
        mode = data.get("mode")
        if isinstance(mode, bool) or not isinstance(mode, int) or mode not in _SET_MODE_VALUES:
            allowed = ", ".join(str(item) for item in sorted(_SET_MODE_VALUES))
            raise EditOpParseError(f"mode must be one of: {allowed}.")
        return SetModeOp(
            op="set_mode",
            target=_parse_node_target(data.get("target"), path="target"),
            mode=mode,  # type: ignore[arg-type]
        )

    raise EditOpParseError(f"Unsupported edit op {op_name!r}.")


def parse_edit_delta(payload: Any) -> tuple[EditOp, ...]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise EditOpParseError("delta must be a list of op objects.")
    parsed: list[EditOp] = []
    for index, item in enumerate(payload):
        parsed.append(parse_edit_op(_require_mapping(item, path=f"delta[{index}]")))
    return tuple(parsed)


def normalize_delta_agent_response(
    response: Any,
    *,
    route: str,
    model: str | None,
    audit_metadata: Mapping[str, Any] | None = None,
) -> AgentDeltaTurnResult:
    if isinstance(response, AgentDeltaTurnResult):
        return response
    if isinstance(response, str):
        payload = _extract_json_object(response)
    elif isinstance(response, Mapping):
        payload = dict(response)
        content = payload.get("content")
        if isinstance(content, str) and "delta" not in payload:
            payload = _extract_json_object(content)
    else:
        raise MalformedModelJSON("Agent response must be a JSON string or object.")

    extras = sorted(key for key in payload if key not in _ALLOWED_RESPONSE_KEYS)
    if extras:
        raise EditOpParseError(
            "Agent JSON for v2 edits only accepts `delta` and `message`; "
            f"found extra field(s): {', '.join(extras)}."
        )

    if "delta" not in payload:
        raise MissingRequiredField("Agent JSON must include key `delta`.")
    message = payload.get("message")
    if not isinstance(message, str):
        raise MissingRequiredField("Agent JSON must include string key `message`.")

    return AgentDeltaTurnResult(
        delta=parse_edit_delta(payload["delta"]),
        message=message,
        route=route,
        model=model,
        audit_metadata=audit_metadata or {},
    )


def normalize_delta_test_client_response(response: Mapping[str, Any]) -> AgentDeltaTurnResult:
    payload = dict(response)
    message = payload.get("message")
    if not isinstance(message, str):
        raise MissingRequiredField("Agent JSON must include string key `message`.")
    if "delta" not in payload:
        raise MissingRequiredField("Agent JSON must include key `delta`.")
    return AgentDeltaTurnResult(
        delta=parse_edit_delta(payload["delta"]),
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client"},
    )


def op_to_dict(op: EditOp) -> dict[str, Any]:
    if isinstance(op, SetNodeFieldOp):
        return {
            "op": op.op,
            "target": [op.target.scope_path, op.target.uid, op.target.field_path],
            "value": op.value,
        }
    if isinstance(op, AddNodeOp):
        payload: dict[str, Any] = {
            "op": op.op,
            "scope_path": op.scope_path,
            "class_type": op.class_type,
            "fields": dict(op.fields),
            "inputs": {
                key: [ref.scope_path, ref.uid, ref.output_slot]
                for key, ref in op.inputs.items()
            },
        }
        if op.anchor is not None:
            anchor: dict[str, Any] = {"relation": op.anchor.relation}
            if op.anchor.group_title is not None:
                anchor["group_title"] = op.anchor.group_title
            if op.anchor.near is not None:
                anchor["near"] = [op.anchor.near.scope_path, op.anchor.near.uid]
            if op.anchor.between is not None:
                anchor["between"] = [
                    [op.anchor.between[0].scope_path, op.anchor.between[0].uid],
                    [op.anchor.between[1].scope_path, op.anchor.between[1].uid],
                ]
            payload["anchor"] = anchor
        return payload
    if isinstance(op, RemoveNodeOp):
        return {"op": op.op, "target": [op.target.scope_path, op.target.uid]}
    if isinstance(op, UpsertLinkOp):
        return {
            "op": op.op,
            "from": [op.source.scope_path, op.source.uid, op.source.output_slot],
            "to": [op.target.scope_path, op.target.uid, op.target.input_field],
        }
    if isinstance(op, RemoveLinkOp):
        payload = {"op": op.op}
        if op.link_id is not None:
            payload["id"] = op.link_id
        if op.target is not None:
            payload["to"] = [op.target.scope_path, op.target.uid, op.target.input_field]
        return payload
    if isinstance(op, ReorderOp):
        return {
            "op": op.op,
            "target": [op.target.scope_path, op.target.uid],
            "axis": op.axis,
            "order": list(op.order),
        }
    if isinstance(op, SetModeOp):
        return {
            "op": op.op,
            "target": [op.target.scope_path, op.target.uid],
            "mode": op.mode,
        }
    raise TypeError(f"Unsupported edit op instance: {type(op)!r}")


__all__ = [
    "AddNodeOp",
    "AgentDeltaTurnResult",
    "AnchorRef",
    "EDIT_OP_RESPONSE_SCHEMA_V2",
    "EditOp",
    "EditOpParseError",
    "LinkSourceRef",
    "LinkTargetRef",
    "NodeFieldTarget",
    "NodeTarget",
    "RemoveLinkOp",
    "RemoveNodeOp",
    "ReorderOp",
    "SetModeOp",
    "SetNodeFieldOp",
    "UpsertLinkOp",
    "normalize_delta_agent_response",
    "normalize_delta_test_client_response",
    "op_to_dict",
    "parse_edit_delta",
    "parse_edit_op",
]
