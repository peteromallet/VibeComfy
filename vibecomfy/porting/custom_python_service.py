"""Small shared service for canonical ``vibecomfy.exec`` graph operations.

The service is deliberately not a second edit surface.  Preparation creates
the existing :class:`AddNodeOp`; adding delegates that operation to
``EditSession.apply_ops`` and inspection delegates node lookup to
``EditSession.describe``.  Source provenance returned here is ephemeral
preparation/inspection data because the canonical add-node operation has no
arbitrary metadata channel.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from vibecomfy.comfy_nodes.exec_node import EXEC_CLASS_TYPE, parse_io
from vibecomfy.porting.edit.ops import AddNodeOp, LinkSourceRef
from vibecomfy.porting.edit.typed_tools import apply_edit_tool_call
from vibecomfy.schema import schema_for


ExecSourceMode = Literal["inline", "installed_entrypoint"]


class _BuiltinAwareProvider:
    """Expose the built-in exec contract to a frozen edit session.

    The normal local/object-info providers intentionally enumerate only
    installed packs.  ``vibecomfy.exec`` is VibeComfy's own node, so it must
    still be available to the canonical edit gate when a caller creates a
    minimal provider-free session (a common CLI/test path).
    """

    def __init__(self, base: Any) -> None:
        self._base = base

    def get_schema(self, class_type: str) -> Any:
        builtin = schema_for(None, class_type)
        if builtin is not None:
            return builtin
        getter = getattr(self._base, "get_schema", None) or getattr(self._base, "get", None)
        return getter(class_type) if callable(getter) else None

    def schemas(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        getter = getattr(self._base, "schemas", None)
        if callable(getter):
            value = getter()
            if isinstance(value, Mapping):
                result.update(value)
        builtin = schema_for(None, EXEC_CLASS_TYPE)
        if builtin is not None:
            result[EXEC_CLASS_TYPE] = builtin
        return result

@dataclass(frozen=True, slots=True)
class ExecSourceMetadata:
    """The source identity accompanying one exec-node preparation."""

    source: str
    io: Mapping[str, Any]
    source_digest: str
    mode: ExecSourceMode = "inline"
    entrypoint: str | None = None


@dataclass(frozen=True, slots=True)
class ExecNodePreparation:
    """Prepared canonical operation and its source identity metadata."""

    operation: AddNodeOp
    metadata: ExecSourceMetadata


@dataclass(frozen=True, slots=True)
class ExecNodeInspection:
    """Read-only exec-node inspection result."""

    descriptor: Any
    metadata: ExecSourceMetadata


def _source_digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _validate_mode(mode: str, entrypoint: str | None) -> ExecSourceMode:
    if mode not in ("inline", "installed_entrypoint"):
        raise ValueError("mode must be 'inline' or 'installed_entrypoint'")
    if mode == "installed_entrypoint" and not entrypoint:
        raise ValueError("installed_entrypoint mode requires entrypoint")
    if entrypoint is not None and (not isinstance(entrypoint, str) or not entrypoint.strip()):
        raise ValueError("entrypoint must be a non-empty string when provided")
    return mode  # type: ignore[return-value]


def prepare_exec_source_node(
    source: str,
    io: Any,
    *,
    uid: str,
    node_id: str | None = None,
    inputs: Mapping[str, LinkSourceRef] | None = None,
    mode: ExecSourceMode = "inline",
    entrypoint: str | None = None,
) -> ExecNodePreparation:
    """Validate source/IO and build one canonical ``AddNodeOp``.

    ``inputs`` is already in canonical link-reference form.  Callers with
    typed-tool-shaped links should use :func:`add_exec_source_node`, which
    keeps target resolution in the existing typed-tool adapter.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not isinstance(uid, str) or not uid or uid != uid.strip():
        raise ValueError("uid must be a non-empty stable string without surrounding whitespace")
    normalized_io = parse_io(io)
    normalized_mode = _validate_mode(mode, entrypoint)
    metadata = ExecSourceMetadata(
        source=source,
        io=normalized_io,
        source_digest=_source_digest(source),
        mode=normalized_mode,
        entrypoint=entrypoint,
    )
    operation = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type=EXEC_CLASS_TYPE,
        fields={"source": source, "io": normalized_io},
        inputs=dict(inputs or {}),
        uid=uid,
        node_id=node_id,
    )
    return ExecNodePreparation(operation=operation, metadata=metadata)


def add_exec_source_node(
    session: Any,
    source: str,
    io: Any,
    *,
    uid: str,
    node_id: str | None = None,
    inputs: Mapping[str, Any] | None = None,
    mode: ExecSourceMode = "inline",
    entrypoint: str | None = None,
    expected_revision: int | None = None,
) -> tuple[ExecNodePreparation, Any]:
    """Add an exec node through the canonical typed-tool/session gateway."""
    preparation = prepare_exec_source_node(
        source,
        io,
        uid=uid,
        node_id=node_id,
        mode=mode,
        entrypoint=entrypoint,
    )
    # Ensure the existing shared evaluator sees the built-in exec schema.  We
    # do this at the gateway rather than teaching the general provider to
    # pretend VibeComfy's own node is an installed custom pack.
    base_provider = getattr(session, "schema_provider", None)
    if base_provider is not None and not isinstance(base_provider, _BuiltinAwareProvider):
        session.schema_provider = _BuiltinAwareProvider(base_provider)
    args: dict[str, Any] = {
        "class_type": EXEC_CLASS_TYPE,
        "fields": {"source": source, "io": preparation.metadata.io},
        "uid": uid,
    }
    if node_id is not None:
        args["node_id"] = node_id
    if inputs:
        args["inputs"] = dict(inputs)
    result = apply_edit_tool_call(
        session,
        "add_node",
        args,
        expected_revision=expected_revision,
    )
    return preparation, result


def inspect_exec_source_node(session: Any, target: str) -> ExecNodeInspection:
    """Inspect one existing exec node without mutating the session."""
    from vibecomfy.ingest.normalize import door_get_widgets_values

    descriptor = session.describe(target)
    if descriptor.class_type != EXEC_CLASS_TYPE:
        raise ValueError(f"target {target!r} is {descriptor.class_type!r}, not {EXEC_CLASS_TYPE!r}")
    node = session.node_ui(descriptor.uid, descriptor.scope_path)
    if node is None:
        raise LookupError(f"exec node {target!r} has no inspectable UI projection")
    widgets = door_get_widgets_values(node)
    if not isinstance(widgets, (list, tuple)) or len(widgets) < 2:
        raise ValueError(f"exec node {target!r} has no source/IO widget metadata")
    source, io = widgets[0], widgets[1]
    if not isinstance(source, str):
        raise ValueError(f"exec node {target!r} has non-string source metadata")
    normalized_io = parse_io(io)
    metadata = getattr(getattr(session, "workflow", None), "nodes", {}).get(str(node.get("id")))
    node_metadata = getattr(metadata, "metadata", {}) if metadata is not None else {}
    exec_metadata = node_metadata.get("vibecomfy_exec", {}) if isinstance(node_metadata, Mapping) else {}
    mode = exec_metadata.get("mode", "inline") if isinstance(exec_metadata, Mapping) else "inline"
    entrypoint = exec_metadata.get("entrypoint") if isinstance(exec_metadata, Mapping) else None
    normalized_mode = _validate_mode(mode, entrypoint)
    return ExecNodeInspection(
        descriptor=descriptor,
        metadata=ExecSourceMetadata(
            source=source,
            io=normalized_io,
            source_digest=_source_digest(source),
            mode=normalized_mode,
            entrypoint=entrypoint,
        ),
    )


__all__ = [
    "ExecNodeInspection",
    "ExecNodePreparation",
    "ExecSourceMetadata",
    "add_exec_source_node",
    "inspect_exec_source_node",
    "prepare_exec_source_node",
]
