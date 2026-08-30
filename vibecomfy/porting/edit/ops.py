from __future__ import annotations

"""Edit-op parsing plus canonical delta-envelope normalization.

The canonical persisted/runtime-facing V2 contract is
``{schema_version: "2.0.0", ops: [...]}`` with seven supported op kinds
(``set_node_field``, ``set_mode``, ``add_node``, ``upsert_link``,
``remove_node``, ``remove_link``, ``subgraph_interface``).  ``reorder`` and
``set_title`` are not part of the designed grammar — they are rejected at
parse time.

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
from typing import TYPE_CHECKING, Any, Literal, Mapping, Sequence

if TYPE_CHECKING:
    from vibecomfy.schema import SchemaSnapshot

from vibecomfy.comfy_nodes.agent.provider import (
    MalformedModelJSON,
    MissingRequiredField,
)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_RELATIONS = frozenset({"near", "right_of", "left_of", "below", "between"})
_SET_MODE_VALUES = frozenset({0, 2, 4})
_FORBIDDEN_RAW_NODE_KEYS = frozenset({"node", "raw_node", "node_payload"})
_FORBIDDEN_RAW_LINK_KEYS = frozenset({"link", "raw_link", "link_payload"})
_ALLOWED_RESPONSE_KEYS = frozenset({"delta", "message"})
_CANONICAL_DELTA_KEYS = frozenset({"schema_version", "ops", "legacy_bridge"})
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
DELTA_CONTRACT_V1 = "delta_v1"
DELTA_DIAGNOSTIC_MALFORMED = "malformed_delta"
DELTA_DIAGNOSTIC_LEGACY_SHAPE = "legacy_delta_shape"
DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY = "unsupported_scoped_apply"
DELTA_DIAGNOSTIC_CORRUPTED = "corrupted_delta"
DELTA_DIAGNOSTIC_TRUNCATED = "truncated_delta"
DELTA_DIAGNOSTIC_ABSENT = "absent_delta"
DELTA_DIAGNOSTIC_REPLAY_MISMATCH = "replay_mismatch"
CANONICAL_DELTA_OP_NAMES = (
    "set_node_field",
    "set_mode",
    "add_node",
    "upsert_link",
    "remove_node",
    "remove_link",
    "subgraph_interface",
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
    # Explicit widget-channel classification for ``fields`` (batch 9 fix).
    # Set by ``diff`` for every add_node it emits so unknown-schema widget
    # fields survive the diff→interpret round-trip; the Python-surface path
    # leaves it empty and falls back to schema classification.
    widget_field_names: tuple[str, ...] = ()


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
class SetModeOp:
    op: Literal["set_mode"]
    target: NodeTarget
    mode: Literal[0, 2, 4]


@dataclass(frozen=True, slots=True)
class SubgraphInterfaceOp:
    """Definition-level subgraph signature statement (Law 3, batch 9 fix).

    ``diff`` emits these when pre/post ``metadata["definitions"]`` subgraph
    signatures differ; ``apply_edit_cow`` mirrors what ``interpret``'s
    ``subgraph_interface(...)`` source statement applies (append/remove/upsert
    into ``metadata["definitions"]["subgraphs"]``).  ``id`` is the stable
    identity key; ``name``/``inputs``/``outputs`` are the emitted signature.
    """

    op: Literal["subgraph_interface"]
    action: Literal["add", "remove", "change"]
    name: str
    inputs: tuple[tuple[str, Any], ...] = ()
    outputs: tuple[tuple[str, Any], ...] = ()
    id: str | None = None


EditOp = (
    SetNodeFieldOp
    | AddNodeOp
    | RemoveNodeOp
    | UpsertLinkOp
    | RemoveLinkOp
    | SetModeOp
    | SubgraphInterfaceOp
)


@dataclass(frozen=True, slots=True)
class CanonicalDeltaEnvelope:
    ops: tuple[EditOp, ...]
    schema_version: Literal["2.0.0"] = DELTA_SCHEMA_VERSION
    legacy_bridge: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "ops": [canonical_op_to_dict(op) for op in self.ops],
        }
        if self.legacy_bridge is not None:
            payload["legacy_bridge"] = self.legacy_bridge
        return payload


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
        ops = [canonical_op_to_dict(op) for op in self.delta]
        envelope = {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": ops,
        }
        return {
            # ``delta`` and ``delta_ops_envelope`` are the explicit bridge for
            # callers that still consume the model-facing response shape.  The
            # durable result remains ``accepted_batch``; both views are
            # canonicalized from the same typed ops.
            "delta": ops,
            "delta_ops_envelope": envelope,
            "accepted_batch": [{"op": op} for op in ops],
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


def _parse_optional_identity(value: Any, *, path: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, path=path)


def _require_port_list(value: Any, *, path: str) -> tuple[tuple[str, Any], ...]:
    """Parse a subgraph_interface ports payload into (name, type) pairs."""
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EditOpParseError(f"{path} must be a list of [name, type] pairs.")
    ports: list[tuple[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes)) or not item:
            raise EditOpParseError(f"{path}[{index}] must be a [name, type] pair.")
        name = _require_string(item[0], path=f"{path}[{index}][0]")
        ports.append((name, item[1] if len(item) > 1 else None))
    return tuple(ports)


def _normalize_link_wire_names(data: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    if "source" in normalized and "from" not in normalized:
        normalized["from"] = normalized["source"]
    if "target" in normalized and "to" not in normalized:
        normalized["to"] = normalized["target"]
    if "link_id" in normalized and "id" not in normalized:
        normalized["id"] = normalized["link_id"]
    return normalized

def _schema_snapshot_from_payload(payload: Mapping[str, Any] | SchemaSnapshot | None) -> Any | None:
    from vibecomfy.schema import SchemaSnapshot, schema_snapshot_from_payload

    if payload is None:
        return None
    if isinstance(payload, SchemaSnapshot):
        return payload
    if not isinstance(payload, Mapping):
        return None
    snapshot = payload.get("schema_snapshot") if "schema_snapshot" in payload else payload
    if snapshot is None:
        return None
    if isinstance(snapshot, SchemaSnapshot):
        return snapshot
    if isinstance(snapshot, Mapping) and snapshot.get("contract_version") == "schema-snapshot-v1":
        return schema_snapshot_from_payload(snapshot)
    return snapshot


def require_known_schema_for_operation(
    operation: Mapping[str, Any] | EditOp,
    schema_snapshot: Mapping[str, Any] | SchemaSnapshot | None,
) -> None:
    """Fail closed when an operation depends on unknown endpoint/node schema."""
    from vibecomfy.porting.edit.admit import AdmissionRejected, admit_operation
    from vibecomfy.schema import SchemaSnapshot, SchemaSnapshotError, require_known_touched_schema

    snapshot = schema_snapshot if isinstance(schema_snapshot, SchemaSnapshot) else _schema_snapshot_from_payload(
        schema_snapshot if isinstance(schema_snapshot, Mapping) else None
    )
    if snapshot is None:
        admitted = admit_operation(None, operation)
        if isinstance(admitted, AdmissionRejected):
            raise EditOpParseError(
                admitted.typed_reason,
                code=admitted.typed_reason,
                detail={"evidence_refs": list(admitted.evidence_refs), "op": getattr(operation, "op", None)},
            )
        # FAIL-CLOSED: missing schema evidence must never admit an operation
        # whose touched closure is schema-dependent. If admit allowed above,
        # re-check need; schema-dependent ops require rejection when snapshot is None.
        from vibecomfy.porting.edit.admit import _needs_schema_knowledge, _operation_mapping
        if _needs_schema_knowledge(_operation_mapping(operation)):
            raise EditOpParseError(
                "missing_touched_schema",
                code="missing_touched_schema",
                detail={"evidence_refs": ["reason:missing_touched_schema"], "op": getattr(operation, "op", None)},
            )
        return
    admitted = admit_operation(snapshot, operation)
    if isinstance(admitted, AdmissionRejected):
        raise EditOpParseError(
            admitted.typed_reason,
            code=admitted.typed_reason,
            detail={"evidence_refs": list(admitted.evidence_refs), "op": getattr(operation, "op", None)},
        )
    try:
        require_known_touched_schema(operation, snapshot)
    except SchemaSnapshotError as exc:
        raise EditOpParseError(str(exc), code=exc.code, detail={"op": getattr(operation, "op", None)}) from exc



def parse_edit_op(
    payload: Mapping[str, Any],
    *,
    schema_snapshot: Mapping[str, Any] | SchemaSnapshot | None = None,
) -> EditOp:
    data = _normalize_link_wire_names(payload)
    op_name = _require_string(data.get("op"), path="op")
    if schema_snapshot is not None:
        require_known_schema_for_operation(data, schema_snapshot)


    if op_name == "set_node_field":
        return SetNodeFieldOp(
            op="set_node_field",
            target=_parse_node_field_target(data.get("target"), path="target"),
            value=data.get("value"),
        )

    if op_name == "add_node":
        _reject_forbidden_keys(data, path="add_node", keys=_FORBIDDEN_RAW_NODE_KEYS)
        widget_field_names = data.get("widget_field_names")
        if widget_field_names is None:
            parsed_widget_field_names: tuple[str, ...] = ()
        else:
            if not isinstance(widget_field_names, Sequence) or isinstance(widget_field_names, (str, bytes)):
                raise EditOpParseError(
                    "add_node.widget_field_names must be a list of field names.",
                    detail={"path": "add_node.widget_field_names"},
                )
            parsed_widget_field_names = tuple(
                _require_string(item, path=f"add_node.widget_field_names[{index}]")
                for index, item in enumerate(widget_field_names)
            )
        return AddNodeOp(
            op="add_node",
            scope_path=_require_string(data.get("scope_path"), path="scope_path", allow_empty=True),
            class_type=_require_string(data.get("class_type"), path="class_type"),
            fields=_parse_fields(data.get("fields"), path="fields"),
            inputs=_parse_inputs(data.get("inputs"), path="inputs"),
            anchor=_parse_anchor(data["anchor"], path="anchor") if "anchor" in data else None,
            uid=_parse_optional_identity(data.get("uid"), path="uid"),
            node_id=_parse_optional_identity(data.get("node_id"), path="node_id"),
            widget_field_names=parsed_widget_field_names,
        )

    if op_name == "subgraph_interface":
        action = data.get("action")
        if action not in ("add", "remove", "change"):
            raise EditOpParseError(
                "subgraph_interface.action must be one of: add, remove, change.",
                detail={"path": "subgraph_interface.action"},
            )
        return SubgraphInterfaceOp(
            op="subgraph_interface",
            action=action,  # type: ignore[arg-type]
            name=_require_string(data.get("name"), path="subgraph_interface.name"),
            inputs=_require_port_list(data.get("inputs"), path="subgraph_interface.inputs"),
            outputs=_require_port_list(data.get("outputs"), path="subgraph_interface.outputs"),
            id=_parse_optional_identity(data.get("id"), path="subgraph_interface.id"),
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
    if op.widget_field_names:
        payload["widget_field_names"] = list(op.widget_field_names)
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
    if isinstance(parsed, SubgraphInterfaceOp):
        payload: dict[str, Any] = {
            "op": parsed.op,
            "action": parsed.action,
            "name": parsed.name,
        }
        if parsed.inputs:
            payload["inputs"] = [list(port) for port in parsed.inputs]
        if parsed.outputs:
            payload["outputs"] = [list(port) for port in parsed.outputs]
        if parsed.id is not None:
            payload["id"] = parsed.id
        return payload
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
                "Canonical delta envelopes only accept `schema_version`, `ops`, and optional `legacy_bridge`.",
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
        legacy_bridge = data.get("legacy_bridge")
        if isinstance(legacy_bridge, str) and legacy_bridge:
            return CanonicalDeltaEnvelope(ops=parsed_ops, legacy_bridge=legacy_bridge)
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


def normalize_delta_v1(payload: Any) -> CanonicalDeltaEnvelope:
    """Strict M1 authority entrypoint; legacy bridges are diagnostics only."""
    if not isinstance(payload, Mapping) or payload.get("delta_contract") != DELTA_CONTRACT_V1 or payload.get("wire_version") != DELTA_SCHEMA_VERSION or not isinstance(payload.get("ops"), list):
        raise EditOpParseError("delta_v1 requires explicit wire_version 2.0.0 and ops.")
    envelope = ensure_root_scoped_delta_envelope({"schema_version": payload["wire_version"], "ops": payload["ops"]}, strict=True)
    if envelope.legacy_bridge is not None:
        raise EditOpParseError("Legacy delta bridges are not authority.", code=DELTA_DIAGNOSTIC_LEGACY_SHAPE)
    return envelope


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
    if isinstance(op, SetModeOp):
        return {
            "op": op.op,
            "target": [op.target.scope_path, op.target.uid],
            "mode": op.mode,
        }
    raise TypeError(f"Unsupported edit op instance: {type(op)!r}")


def validate_delta_envelope_structure(
    payload: Any,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Validate the structural envelope shape without full normalization.

    Checks that the payload is a non-legacy V2 canonical envelope with the
    correct schema_version and a list of ops.  Does not parse individual ops
    (use `normalize_delta_envelope` for full validation), but catches
    corrupted, truncated, absent, and legacy whole-graph shapes early so
    consumers can fail closed before widening into Apply.

    Returns ``(is_valid, diagnostic_code, detail)``.
    """
    if payload is None:
        return False, DELTA_DIAGNOSTIC_ABSENT, {
            "reason": "Delta evidence is absent (None).",
        }

    if isinstance(payload, CanonicalDeltaEnvelope):
        return True, None, None

    if not isinstance(payload, Mapping):
        return False, DELTA_DIAGNOSTIC_CORRUPTED, {
            "reason": f"Delta envelope must be a mapping, got {type(payload).__name__}.",
            "type": type(payload).__name__,
        }

    data = dict(payload)

    # ── Legacy whole-graph shapes ───────────────────────────────────────────
    if "delta_ops" in data and "schema_version" not in data:
        return False, DELTA_DIAGNOSTIC_LEGACY_SHAPE, {
            "reason": "Legacy whole-graph delta_ops wrapper is not a canonical V2 envelope.",
            "keys": sorted(data),
        }

    if "ops" in data and "schema_version" not in data:
        return False, DELTA_DIAGNOSTIC_LEGACY_SHAPE, {
            "reason": "Legacy wrapped shape with `ops` but no `schema_version`.",
            "keys": sorted(data),
        }

    # ── Missing required fields ─────────────────────────────────────────────
    if "schema_version" not in data:
        return False, DELTA_DIAGNOSTIC_TRUNCATED, {
            "reason": "Delta envelope is missing required field `schema_version`.",
            "keys": sorted(data),
        }

    if "ops" not in data:
        return False, DELTA_DIAGNOSTIC_TRUNCATED, {
            "reason": "Delta envelope is missing required field `ops`.",
            "keys": sorted(data),
        }

    # ── Schema version check ────────────────────────────────────────────────
    schema_version = data.get("schema_version")
    if not isinstance(schema_version, str) or schema_version != DELTA_SCHEMA_VERSION:
        return False, DELTA_DIAGNOSTIC_MALFORMED, {
            "reason": (
                f"Unsupported schema_version {schema_version!r}; "
                f"expected {DELTA_SCHEMA_VERSION!r}."
            ),
            "schema_version": schema_version,
        }

    # ── Ops must be a list ──────────────────────────────────────────────────
    ops = data.get("ops")
    if not isinstance(ops, list):
        return False, DELTA_DIAGNOSTIC_TRUNCATED, {
            "reason": f"`ops` must be a list, got {type(ops).__name__}.",
            "ops_type": type(ops).__name__,
        }

    # ── Extra keys beyond canonical set ─────────────────────────────────────
    extras = sorted(key for key in data if key not in _CANONICAL_DELTA_KEYS)
    if extras:
        if any(key in _LEGACY_DELTA_WRAPPER_KEYS for key in extras):
            return False, DELTA_DIAGNOSTIC_LEGACY_SHAPE, {
                "reason": "Legacy wrapped delta metadata found in envelope.",
                "keys": extras,
            }
        return False, DELTA_DIAGNOSTIC_MALFORMED, {
            "reason": (
                "Canonical delta envelopes only accept `schema_version`, `ops`, "
                f"and optional `legacy_bridge`; found extra keys: {extras}."
            ),
            "keys": extras,
        }

    return True, None, None


def validate_apply_delta_evidence(
    payload: Any,
    *,
    allow_absent: bool = False,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Validate that delta evidence is sufficient for Apply eligibility.

    Performs structural validation and then full normalization (which
    parses and canonicalizes every op).  This is the authoritative gate
    that must pass before delta evidence can widen into Apply.

    Args:
        payload: The delta envelope to validate (dict or CanonicalDeltaEnvelope).
        allow_absent: If True, absent (None) evidence is treated as valid
            rather than a blocking diagnostic.  Use this for non-edit routes
            where delta evidence is not expected.

    Returns:
        ``(is_valid, diagnostic_code, detail)`` where *is_valid* is True
        only when the evidence passes all checks, and *diagnostic_code* is
        a stable ``DELTA_DIAGNOSTIC_*`` constant on failure.
    """
    # ── Absent evidence ─────────────────────────────────────────────────────
    if payload is None:
        if allow_absent:
            return True, None, None
        return False, DELTA_DIAGNOSTIC_ABSENT, {
            "reason": "Delta evidence is absent; cannot validate for Apply.",
        }

    # ── Structural validation ───────────────────────────────────────────────
    struct_valid, struct_code, struct_detail = validate_delta_envelope_structure(payload)
    if not struct_valid:
        return False, struct_code, struct_detail

    # ── Full normalization (parse + canonicalize every op) ──────────────────
    try:
        normalize_delta_envelope(payload, strict=True)
    except EditOpParseError as exc:
        return False, exc.code, dict(exc.detail or {}, reason=str(exc))
    except Exception as exc:
        return False, DELTA_DIAGNOSTIC_CORRUPTED, {
            "reason": f"Delta normalization failed: {exc}",
            "error_type": type(exc).__name__,
        }

    return True, None, None


def validate_delta_replay_equality(
    original: dict[str, Any] | None,
    replay: dict[str, Any] | None,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Verify that a replayed delta envelope matches the original.

    Both payloads are normalized through ``normalize_delta_envelope(strict=True)``
    and compared for structural equality.  Missing identity fields (uid/node_id)
    in the replay are treated as a mismatch because the canonical contract
    requires them for applyable turns.

    Returns ``(is_equal, diagnostic_code, detail)``.
    """
    if original is None and replay is None:
        return True, None, None

    if original is None:
        return False, DELTA_DIAGNOSTIC_REPLAY_MISMATCH, {
            "reason": "Original delta evidence is absent but replay has data.",
        }

    if replay is None:
        return False, DELTA_DIAGNOSTIC_REPLAY_MISMATCH, {
            "reason": "Replay delta evidence is absent but original had data.",
        }

    try:
        orig_env = normalize_delta_envelope(original, strict=True)
    except EditOpParseError as exc:
        return False, DELTA_DIAGNOSTIC_CORRUPTED, {
            "reason": f"Original delta envelope failed normalization: {exc}",
            "side": "original",
            "code": exc.code,
        }

    try:
        replay_env = normalize_delta_envelope(replay, strict=True)
    except EditOpParseError as exc:
        return False, DELTA_DIAGNOSTIC_REPLAY_MISMATCH, {
            "reason": f"Replay delta envelope failed normalization: {exc}",
            "side": "replay",
            "code": exc.code,
        }

    if orig_env.to_dict() != replay_env.to_dict():
        return False, DELTA_DIAGNOSTIC_REPLAY_MISMATCH, {
            "reason": "Replay delta envelope does not match original.",
            "original_ops_count": len(orig_env.ops),
            "replay_ops_count": len(replay_env.ops),
        }

    return True, None, None


__all__ = [
    "AddNodeOp",
    "AgentDeltaTurnResult",
    "AnchorRef",
    "CANONICAL_DELTA_OP_NAMES",
    "CanonicalDeltaEnvelope",
    "DELTA_DIAGNOSTIC_ABSENT",
    "DELTA_CONTRACT_V1",
    "DELTA_DIAGNOSTIC_CORRUPTED",
    "DELTA_DIAGNOSTIC_LEGACY_SHAPE",
    "DELTA_DIAGNOSTIC_MALFORMED",
    "DELTA_DIAGNOSTIC_REPLAY_MISMATCH",
    "DELTA_DIAGNOSTIC_TRUNCATED",
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
    "SetModeOp",
    "SetNodeFieldOp",
    "SubgraphInterfaceOp",
    "UpsertLinkOp",
    "canonical_op_to_dict",
    "ensure_root_scoped_delta_envelope",
    "normalize_delta_agent_response",
    "normalize_delta_envelope",
    "normalize_delta_v1",
    "normalize_delta_ops",
    "normalize_delta_test_client_response",
    "op_to_dict",
    "parse_edit_delta",
    "parse_edit_op",
    "require_known_schema_for_operation",
    "validate_apply_delta_evidence",
    "validate_delta_envelope_structure",
    "validate_delta_replay_equality",
]
