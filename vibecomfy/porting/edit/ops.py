from __future__ import annotations

"""Edit-op parsing plus canonical delta-envelope normalization.

The canonical persisted/runtime-facing V2 contract is
``{schema_version: "2.0.0", ops: [...]}`` with exactly six supported op kinds.

Legacy handling is explicit:

- Flat V2 op arrays are only accepted when a caller opts into the temporary
  ``allow_legacy_list`` bridge.
- Legacy wrapped mappings are rejected as ``legacy_delta_shape`` so consumers do
  not silently confuse audit metadata with canonical ops.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from vibecomfy.comfy_nodes.agent.provider import (
    MalformedModelJSON,
    MissingRequiredField,
)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_RELATIONS = frozenset({"near", "right_of", "left_of", "below", "between"})
_REORDER_AXES = frozenset({"widgets", "slots"})
_SET_MODE_VALUES = frozenset({0, 2, 4})
_FORBIDDEN_RAW_NODE_KEYS = frozenset({"node", "raw_node", "node_payload"})
_FORBIDDEN_RAW_LINK_KEYS = frozenset({"link", "raw_link", "link_payload"})
_ALLOWED_RESPONSE_KEYS = frozenset({"delta", "message"})
_CANONICAL_DELTA_KEYS = frozenset({"schema_version", "ops"})
_LEGACY_DELTA_WRAPPER_KEYS = frozenset(
    {
        "automatic_link_removals",
        "delta",
        "delta_ops",
        "diagnostics",
        "guard_result",
        "normalize",
        "ops",
        "re_stitches",
    }
)
_SCHEMA_DIR = Path(__file__).with_name("schemas") / "v2"

DELTA_SCHEMA_VERSION = "2.0.0"
DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta"
DELTA_DIAGNOSTIC_LEGACY_SHAPE = "legacy_delta_shape"
DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY = "unsupported_scoped_apply"
CANONICAL_DELTA_OP_NAMES = (
    "set_node_field",
    "set_mode",
    "add_node",
    "upsert_link",
    "remove_node",
    "remove_link",
)


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))


EDIT_OP_CANONICAL_ENVELOPE_SCHEMA_V2 = _load_schema("delta_envelope.schema.json")

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
                # The model-facing response bridge is still a flat ``delta`` list,
                # but the op vocabulary itself already matches the canonical six-op
                # contract. Canonical persistence moves to the envelope in T3.
                "properties": {
                    "op": {"enum": list(CANONICAL_DELTA_OP_NAMES)}
                },
                "oneOf": [
                    {"type": "object", "required": ["op", "target", "value"]},
                    {
                        "type": "object",
                        "required": [
                            "op",
                            "scope_path",
                            "uid",
                            "node_id",
                            "class_type",
                            "fields",
                            "inputs",
                        ],
                    },
                    {"type": "object", "required": ["op", "target"]},
                    {"type": "object", "required": ["op", "from", "to"]},
                    {
                        "oneOf": [
                            {"type": "object", "required": ["op", "id"]},
                            {"type": "object", "required": ["op", "to"]},
                        ]
                    },
                    {"type": "object", "required": ["op", "target", "mode"]},
                ],
            },
        },
    },
}


class EditOpParseError(ValueError):
    """Raised when an edit delta violates the typed or canonical contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str = DELTA_DIAGNOSTIC_MALFORMED,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code or DELTA_DIAGNOSTIC_MALFORMED)
        self.detail = dict(detail or {})


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
    relation: Literal["near", "right_of", "left_of", "below", "between"]
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
    uid: str | None = field(default=None, repr=False)
    node_id: str | None = field(default=None, repr=False)


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


@dataclass(frozen=True, slots=True)
class CanonicalDeltaEnvelope:
    ops: tuple[EditOp, ...]
    schema_version: Literal["2.0.0"] = DELTA_SCHEMA_VERSION
    legacy_bridge: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ops": [canonical_op_to_dict(op) for op in self.ops],
        }


@dataclass(frozen=True)
class AgentDeltaTurnResult:
    delta: tuple[EditOp, ...]
    message: str
    route: str
    model: str | None = None
    audit_metadata: Mapping[str, Any] | None = None

    def canonical_envelope(
        self,
        *,
        require_root_scope: bool = True,
    ) -> CanonicalDeltaEnvelope:
        payload = {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [canonical_op_to_dict(op) for op in self.delta],
        }
        if require_root_scope:
            return ensure_root_scoped_delta_envelope(payload)
        return normalize_delta_envelope(payload)

    def to_dict(self) -> dict[str, Any]:
        envelope = self.canonical_envelope().to_dict()
        return {
            "delta": list(envelope["ops"]),
            "delta_ops_envelope": envelope,
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
        # Models sometimes emit trailing prose or a second object after the
        # actual delta payload. Recover the first complete object rather than
        # discarding an otherwise valid response.
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
        field_name = _require_string(key, path=f"{path}.<key>")
        parsed[field_name] = _parse_link_source(ref, path=f"{path}.{field_name}")
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


def _parse_optional_identity(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, path=path)


def _normalize_link_wire_names(data: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    if "source" in normalized and "from" not in normalized:
        normalized["from"] = normalized["source"]
    if "target" in normalized and "to" not in normalized:
        normalized["to"] = normalized["target"]
    if "link_id" in normalized and "id" not in normalized:
        normalized["id"] = normalized["link_id"]
    return normalized


def parse_edit_op(payload: Mapping[str, Any]) -> EditOp:
    data = _normalize_link_wire_names(payload)
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
            uid=_parse_optional_identity(data.get("uid"), path="uid"),
            node_id=_parse_optional_identity(data.get("node_id"), path="node_id"),
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


def _canonicalize_add_node(op: AddNodeOp) -> dict[str, Any]:
    if op.uid is None:
        raise EditOpParseError(
            "Canonical add_node ops must include `uid`.",
            detail={"op": "add_node", "field": "uid"},
        )
    if op.node_id is None:
        raise EditOpParseError(
            "Canonical add_node ops must include `node_id`.",
            detail={"op": "add_node", "field": "node_id"},
        )
    payload = {
        "op": op.op,
        "scope_path": op.scope_path,
        "uid": op.uid,
        "node_id": op.node_id,
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


def canonical_op_to_dict(op: EditOp | Mapping[str, Any]) -> dict[str, Any]:
    parsed = parse_edit_op(op) if isinstance(op, Mapping) else op
    if isinstance(parsed, ReorderOp):
        raise EditOpParseError(
            "Canonical V2 deltas support exactly six op types; `reorder` is legacy-only.",
            detail={"op": "reorder"},
        )
    if isinstance(parsed, SetNodeFieldOp):
        return {
            "op": parsed.op,
            "target": [parsed.target.scope_path, parsed.target.uid, parsed.target.field_path],
            "value": parsed.value,
        }
    if isinstance(parsed, AddNodeOp):
        return _canonicalize_add_node(parsed)
    if isinstance(parsed, RemoveNodeOp):
        return {"op": parsed.op, "target": [parsed.target.scope_path, parsed.target.uid]}
    if isinstance(parsed, UpsertLinkOp):
        return {
            "op": parsed.op,
            "from": [parsed.source.scope_path, parsed.source.uid, parsed.source.output_slot],
            "to": [parsed.target.scope_path, parsed.target.uid, parsed.target.input_field],
        }
    if isinstance(parsed, RemoveLinkOp):
        payload: dict[str, Any] = {"op": parsed.op}
        if parsed.link_id is not None:
            payload["id"] = parsed.link_id
        if parsed.target is not None:
            payload["to"] = [parsed.target.scope_path, parsed.target.uid, parsed.target.input_field]
        return payload
    if isinstance(parsed, SetModeOp):
        return {
            "op": parsed.op,
            "target": [parsed.target.scope_path, parsed.target.uid],
            "mode": parsed.mode,
        }
    raise TypeError(f"Unsupported edit op instance: {type(parsed)!r}")


def _legacy_shape_error(payload: Mapping[str, Any], *, message: str) -> EditOpParseError:
    legacy_keys = sorted(key for key in payload if key in _LEGACY_DELTA_WRAPPER_KEYS)
    return EditOpParseError(
        message,
        code=DELTA_DIAGNOSTIC_LEGACY_SHAPE,
        detail={"keys": legacy_keys},
    )


def normalize_delta_envelope(
    payload: Any,
    *,
    allow_legacy_list: bool = False,
    strict: bool = True,
) -> CanonicalDeltaEnvelope:
    if isinstance(payload, CanonicalDeltaEnvelope):
        return payload

    if isinstance(payload, Mapping):
        data = dict(payload)
        if "delta_ops" in data:
            raise _legacy_shape_error(
                data,
                message="Legacy wrapped delta shapes under `delta_ops` are not canonical V2 envelopes.",
            )
        has_schema_version = "schema_version" in data
        has_ops = "ops" in data
        if has_ops and not has_schema_version:
            raise _legacy_shape_error(
                data,
                message="Legacy wrapped delta shapes must be migrated to `{schema_version, ops}`.",
            )
        if not has_schema_version and not has_ops:
            extras = sorted(data)
            raise EditOpParseError(
                "Canonical delta envelopes must be objects with `schema_version` and `ops`.",
                detail={"keys": extras},
            )
        extras = sorted(key for key in data if key not in _CANONICAL_DELTA_KEYS)
        if extras:
            if any(key in _LEGACY_DELTA_WRAPPER_KEYS for key in extras):
                raise _legacy_shape_error(
                    data,
                    message="Legacy wrapped delta metadata is not part of the canonical V2 envelope.",
                )
            raise EditOpParseError(
                "Canonical delta envelopes only accept `schema_version` and `ops`.",
                detail={"keys": extras},
            )
        schema_version = _require_string(data.get("schema_version"), path="schema_version")
        if schema_version != DELTA_SCHEMA_VERSION:
            raise EditOpParseError(
                f"Unsupported delta schema_version {schema_version!r}.",
                detail={"schema_version": schema_version},
            )
        parsed_ops = parse_edit_delta(data.get("ops"))
        if strict:
            # Canonicalization is deliberate: it rejects legacy-only ops and missing
            # add-node identity before downstream consumers see the payload.
            for op in parsed_ops:
                canonical_op_to_dict(op)
        return CanonicalDeltaEnvelope(ops=parsed_ops)

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        if not allow_legacy_list:
            raise EditOpParseError(
                "Flat V2 delta op arrays are a legacy bridge; wrap them in `{schema_version, ops}`.",
                code=DELTA_DIAGNOSTIC_LEGACY_SHAPE,
            )
        return CanonicalDeltaEnvelope(
            ops=parse_edit_delta(payload),
            legacy_bridge="flat_v2_ops",
        )

    raise EditOpParseError("Canonical delta envelopes must be an object or op list.")


def normalize_delta_ops(
    payload: Any,
    *,
    allow_legacy_list: bool = False,
) -> tuple[EditOp, ...]:
    return normalize_delta_envelope(payload, allow_legacy_list=allow_legacy_list).ops


def ensure_root_scoped_delta_envelope(
    payload: Any,
    *,
    allow_legacy_list: bool = False,
    strict: bool = True,
) -> CanonicalDeltaEnvelope:
    envelope = normalize_delta_envelope(payload, allow_legacy_list=allow_legacy_list, strict=strict)
    for op in envelope.ops:
        scoped_paths: list[str] = []
        if isinstance(op, SetNodeFieldOp):
            scoped_paths.append(op.target.scope_path)
        elif isinstance(op, AddNodeOp):
            scoped_paths.append(op.scope_path)
        elif isinstance(op, RemoveNodeOp):
            scoped_paths.append(op.target.scope_path)
        elif isinstance(op, UpsertLinkOp):
            scoped_paths.extend((op.source.scope_path, op.target.scope_path))
        elif isinstance(op, RemoveLinkOp) and op.target is not None:
            scoped_paths.append(op.target.scope_path)
        elif isinstance(op, SetModeOp):
            scoped_paths.append(op.target.scope_path)
        elif isinstance(op, ReorderOp):
            scoped_paths.append(op.target.scope_path)
        bad = sorted({path for path in scoped_paths if path})
        if bad:
            raise EditOpParseError(
                "Non-root scoped apply is unsupported for canonical delta consumers.",
                code=DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
                detail={"scope_paths": bad, "op": op.op},
            )
    return envelope


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

    raw_delta = payload["delta"]
    if isinstance(raw_delta, Mapping):
        parsed_delta = normalize_delta_envelope(raw_delta).ops
    else:
        # Bridge only: current model-facing transport is still a flat list.
        parsed_delta = parse_edit_delta(raw_delta)

    return AgentDeltaTurnResult(
        delta=parsed_delta,
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
    raw_delta = payload["delta"]
    if isinstance(raw_delta, Mapping):
        parsed_delta = normalize_delta_envelope(raw_delta).ops
    else:
        parsed_delta = parse_edit_delta(raw_delta)
    return AgentDeltaTurnResult(
        delta=parsed_delta,
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
        if op.uid is not None:
            payload["uid"] = op.uid
        if op.node_id is not None:
            payload["node_id"] = op.node_id
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
    "CANONICAL_DELTA_OP_NAMES",
    "CanonicalDeltaEnvelope",
    "DELTA_DIAGNOSTIC_LEGACY_SHAPE",
    "DELTA_DIAGNOSTIC_MALFORMED",
    "DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY",
    "DELTA_SCHEMA_VERSION",
    "EDIT_OP_CANONICAL_ENVELOPE_SCHEMA_V2",
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
    "canonical_op_to_dict",
    "ensure_root_scoped_delta_envelope",
    "normalize_delta_agent_response",
    "normalize_delta_envelope",
    "normalize_delta_ops",
    "normalize_delta_test_client_response",
    "op_to_dict",
    "parse_edit_delta",
    "parse_edit_op",
]
