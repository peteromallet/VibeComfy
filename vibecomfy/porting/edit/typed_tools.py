"""Thin typed-tool adapter into canonical edit ops.

This module owns no graph and applies nothing itself. It validates tool-shaped
arguments, resolves render-visible bindings against an ``EditSession``, lowers
them to canonical op dataclasses, then delegates to ``EditSession.apply_ops``.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)


EDIT_TOOL_NAMES = frozenset(
    {
        "edit_node",
        "add_node",
        "remove_node",
        "upsert_link",
        "remove_link",
        "set_node_mode",
        "edit_batch",
    }
)
_POSITIONAL = re.compile(r"^widget_\d+$")
_MODES = {"enabled": 0, "muted": 2, "bypassed": 4}


class EditToolError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _object(args: Any, *, tool: str) -> dict[str, Any]:
    if not isinstance(args, Mapping):
        raise EditToolError("invalid_arguments", f"{tool} requires an argument object.")
    return dict(args)


def _keys(
    args: Mapping[str, Any],
    *,
    tool: str,
    required: Sequence[str],
    optional: Sequence[str] = (),
) -> None:
    missing = [key for key in required if key not in args]
    unknown = sorted(set(args) - set(required) - set(optional))
    if missing:
        raise EditToolError(
            "invalid_arguments", f"{tool} requires: {', '.join(missing)}."
        )
    if unknown:
        raise EditToolError(
            "invalid_arguments", f"{tool} does not accept: {', '.join(unknown)}."
        )


def resolve_target(session: Any, target: Any) -> str:
    if not isinstance(target, str) or not target.strip():
        raise EditToolError("invalid_arguments", "target must be a non-empty binding or uid.")
    target = target.strip()
    nodes = tuple(getattr(getattr(session, "workflow", None), "nodes", {}).values())
    uid_matches = [
        str(node.uid)
        for node in nodes
        if str(getattr(node, "uid", "") or "") == target
    ]
    if len(uid_matches) == 1:
        return uid_matches[0]
    if len(uid_matches) > 1:
        raise EditToolError(
            "ambiguous_target", f"uid {target!r} resolves to multiple nodes.", retryable=False
        )
    uid = dict(getattr(session, "uid_by_name", {}) or {}).get(target)
    if uid is None:
        raise EditToolError("unknown_target", f"unknown render binding or uid {target!r}.")
    return str(uid)


def _source_ref(session: Any, payload: Any) -> LinkSourceRef:
    if isinstance(payload, str):
        source, output = payload, 0
    elif isinstance(payload, Mapping):
        _keys(payload, tool="link source", required=("source",), optional=("output",))
        source, output = payload["source"], payload.get("output", 0)
    elif isinstance(payload, (list, tuple)) and 1 <= len(payload) <= 2:
        source, output = payload[0], payload[1] if len(payload) == 2 else 0
    else:
        raise EditToolError(
            "invalid_arguments",
            "a link source must be a binding, {source, output}, or [source, output].",
        )
    return LinkSourceRef("", resolve_target(session, source), output)


def _lower_one(session: Any, tool: str, raw_args: Any) -> tuple[EditOp, ...]:
    if tool not in EDIT_TOOL_NAMES:
        raise EditToolError("unknown_tool", f"unknown typed edit tool {tool!r}.", retryable=False)
    args = _object(raw_args, tool=tool)
    if tool == "edit_batch":
        _keys(args, tool=tool, required=("ops",))
        raw_ops = args["ops"]
        if not isinstance(raw_ops, list) or not raw_ops:
            raise EditToolError("invalid_arguments", "edit_batch.ops must be a non-empty list.")
        lowered: list[EditOp] = []
        for index, item in enumerate(raw_ops):
            if not isinstance(item, Mapping) or not isinstance(item.get("op"), str):
                raise EditToolError(
                    "invalid_arguments", f"edit_batch.ops[{index}] requires a string `op`."
                )
            nested = str(item["op"])
            if nested == "edit_batch":
                raise EditToolError("invalid_arguments", "nested edit_batch calls are not allowed.")
            lowered.extend(_lower_one(session, nested, {k: v for k, v in item.items() if k != "op"}))
        return tuple(lowered)

    if tool == "edit_node":
        _keys(args, tool=tool, required=("target", "field", "value"))
        field = args["field"]
        if not isinstance(field, str) or not field or _POSITIONAL.match(field):
            raise EditToolError(
                "invalid_arguments", "field must be a non-positional render-visible name."
            )
        return (
            SetNodeFieldOp(
                "set_node_field",
                NodeFieldTarget("", resolve_target(session, args["target"]), field),
                args["value"],
            ),
        )

    if tool == "remove_node":
        _keys(args, tool=tool, required=("target",))
        return (RemoveNodeOp("remove_node", NodeTarget("", resolve_target(session, args["target"]))),)

    if tool == "set_node_mode":
        _keys(args, tool=tool, required=("target", "mode"))
        if args["mode"] not in _MODES:
            raise EditToolError("invalid_arguments", "mode must be enabled, muted, or bypassed.")
        return (
            SetModeOp(
                "set_mode",
                NodeTarget("", resolve_target(session, args["target"])),
                _MODES[args["mode"]],
            ),
        )

    if tool == "remove_link":
        _keys(args, tool=tool, required=("target", "target_input"))
        field = args["target_input"]
        if not isinstance(field, str) or not field:
            raise EditToolError("invalid_arguments", "target_input must be a name.")
        return (
            RemoveLinkOp(
                "remove_link",
                target=LinkTargetRef("", resolve_target(session, args["target"]), field),
            ),
        )

    if tool == "upsert_link":
        _keys(
            args,
            tool=tool,
            required=("source", "target", "target_input"),
            optional=("source_output",),
        )
        source = LinkSourceRef(
            "", resolve_target(session, args["source"]), args.get("source_output", 0)
        )
        target_input = args["target_input"]
        if not isinstance(target_input, str) or not target_input:
            raise EditToolError("invalid_arguments", "target_input must be a name.")
        return (
            UpsertLinkOp(
                "upsert_link",
                source,
                LinkTargetRef("", resolve_target(session, args["target"]), target_input),
            ),
        )

    # add_node
    _keys(
        args,
        tool=tool,
        required=("class_type",),
        optional=("fields", "widget_values", "inputs", "uid", "node_id"),
    )
    if not isinstance(args["class_type"], str) or not args["class_type"]:
        raise EditToolError("invalid_arguments", "class_type must be a non-empty string.")
    if "fields" in args and "widget_values" in args:
        raise EditToolError(
            "invalid_arguments", "add_node accepts fields or widget_values, not both."
        )
    fields = args.get("fields", args.get("widget_values", {}))
    inputs = args.get("inputs", {})
    if not isinstance(fields, Mapping) or not isinstance(inputs, Mapping):
        raise EditToolError("invalid_arguments", "add_node fields and inputs must be objects.")
    return (
        AddNodeOp(
            "add_node",
            "",
            args["class_type"],
            dict(fields),
            {str(name): _source_ref(session, value) for name, value in inputs.items()},
            uid=str(args["uid"]) if args.get("uid") is not None else None,
            node_id=str(args["node_id"]) if args.get("node_id") is not None else None,
        ),
    )


def lower_edit_tool_call(session: Any, tool: str, args: Any) -> tuple[EditOp, ...]:
    """Lower one typed tool call without mutating the session."""
    return _lower_one(session, tool, args)


def apply_edit_tool_call(
    session: Any,
    tool: str,
    args: Any,
    *,
    expected_revision: int | None = None,
) -> Any:
    """Lower and atomically apply a typed call through ``EditSession``."""
    return session.apply_ops(
        lower_edit_tool_call(session, tool, args),
        expected_revision=expected_revision,
    )


__all__ = [
    "EDIT_TOOL_NAMES",
    "EditToolError",
    "apply_edit_tool_call",
    "lower_edit_tool_call",
    "resolve_target",
]
