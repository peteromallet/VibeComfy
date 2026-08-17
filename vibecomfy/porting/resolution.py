"""Shared resolution infrastructure for edit-lint and interpret.

Provides the NodeBackend protocol, the LintIndexBackend implementation,
the ResolutionContext class with all resolve_* methods, and shared helpers
build_lg_id_maps / _try_parse_lg_id.

Import graph constraint: this module does NOT import from edit.lint so the
dependency is one-directional and acyclic.  Mutation authority is interpret;
this module only resolves names against a lint/index snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Generic, Mapping, Protocol, TypeVar

from vibecomfy.porting.edit.ops import (
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
)
from vibecomfy.porting.endpoint_invariant import resolve_working_port
from vibecomfy.porting.report import PortIssue

T = TypeVar("T")
_OUTPUT_ALIAS_RE = re.compile(r"output_(\d+)\Z")


# ── node metadata ─────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class _NodeMeta:
    """Immutable snapshot of a node's identity and I/O surface.

    Used by LintIndexBackend.node_meta_for.
    """

    scope_path: str
    uid: str
    lg_id: int
    class_type: str
    input_names: tuple[str, ...]
    output_names: tuple[str, ...]
    output_slots: Mapping[str, int] = field(default_factory=dict)


# ── shared free functions ─────────────────────────────────────────────────────

def build_lg_id_maps(
    node_index: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[tuple[str, int], str], dict[tuple[str, str], int]]:
    """Build bidirectional LiteGraph-id ↔ canonical-uid maps per scope.

    Takes the ``node_index`` dict directly (``dict[(scope_path, uid) -> node]``)
    rather than a full graph index so it can be called from LintIndex.build.

    Returns ``(lg_id_to_uid, uid_to_lg_id)``.
    """
    lg_id_to_uid: dict[tuple[str, int], str] = {}
    uid_to_lg_id: dict[tuple[str, str], int] = {}
    for (scope_path, uid), node in node_index.items():
        lg_id = node.get("id")
        if isinstance(lg_id, int):
            lg_id_to_uid[(scope_path, lg_id)] = uid
            uid_to_lg_id[(scope_path, uid)] = lg_id
    return lg_id_to_uid, uid_to_lg_id


def _try_parse_lg_id(uid_str: str) -> int | None:
    """Return the integer if *uid_str* is a LiteGraph-id-like decimal string.

    Negative ids are not valid LiteGraph ids and return None.
    """
    stripped = uid_str.strip()
    if not stripped:
        return None
    try:
        parsed = int(stripped)
    except ValueError:
        return None
    if parsed < 0:
        return None
    return parsed


# ── node meta extraction ──────────────────────────────────────────────────────

def _extract_node_meta(
    node: dict[str, Any],
    scope_path: str,
    uid: str,
) -> _NodeMeta:
    """Extract _NodeMeta from a raw LiteGraph node dict."""
    lg_id: Any = node.get("id")
    if not isinstance(lg_id, int):
        lg_id = -1
    class_type: str = node.get("type") or node.get("class_type") or ""
    raw_inputs = node.get("inputs")
    input_names: tuple[str, ...] = ()
    if isinstance(raw_inputs, list):
        input_names = tuple(
            entry.get("name") or ""
            for entry in raw_inputs
            if isinstance(entry, dict)
        )
    raw_outputs = node.get("outputs")
    output_names: tuple[str, ...] = ()
    output_slots: dict[str, int] = {}
    if isinstance(raw_outputs, list):
        out_names: list[str] = []
        for entry in raw_outputs:
            if isinstance(entry, dict):
                name = entry.get("name") or ""
                out_names.append(name)
                slot = entry.get("slot_index")
                if isinstance(slot, int):
                    output_slots[name] = slot
        output_names = tuple(out_names)
    return _NodeMeta(
        scope_path=scope_path,
        uid=uid,
        lg_id=lg_id,
        class_type=class_type,
        input_names=input_names,
        output_names=output_names,
        output_slots=output_slots,
    )


# ── NodeBackend protocol ──────────────────────────────────────────────────────

class NodeBackend(Protocol):
    """Backend for node lookups — implemented by LintIndexBackend."""

    def node_for(self, scope_path: str, uid: str) -> dict[str, Any] | None: ...
    def node_exists(self, scope_path: str, uid: str) -> bool: ...
    def uid_for_lg_id(self, scope_path: str, lg_id: int) -> str | None: ...
    def node_meta_for(self, scope_path: str, uid: str) -> _NodeMeta | None: ...


# ── LintIndexBackend ──────────────────────────────────────────────────────────

class LintIndexBackend:
    """Thin NodeBackend wrapper around a LintIndex.

    Accepts any LintIndex-duck-typed object (no direct import of LintIndex to
    keep the dependency graph acyclic — edit_lint.py imports resolution.py, not
    the other way around).
    """

    def __init__(self, index: Any) -> None:
        self._index = index

    def node_for(self, scope_path: str, uid: str) -> dict[str, Any] | None:
        return self._index.node_by_uid(scope_path, uid)

    def node_exists(self, scope_path: str, uid: str) -> bool:
        return self._index.node_exists(scope_path, uid)

    def uid_for_lg_id(self, scope_path: str, lg_id: int) -> str | None:
        return self._index.uid_for_lg_id(scope_path, lg_id)

    def node_meta_for(self, scope_path: str, uid: str) -> _NodeMeta | None:
        return self._index.node_meta_for(scope_path, uid)


# ── ResolutionIssue and ResolveResult ────────────────────────────────────────

@dataclass(frozen=True)
class ResolutionIssue:
    """A single finding from a ResolutionContext resolve_* call."""

    code: str
    message: str
    severity: str = "error"
    scope_path: str | None = None
    uid: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolveResult(Generic[T]):
    """Outcome of a resolution operation — generic over the resolved value type."""

    value: T | None
    issues: list[ResolutionIssue] = field(default_factory=list)


# ── ResolvedEndpoint ──────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ResolvedEndpoint:
    """Resolved link endpoint from ResolutionContext.resolve_{source,target}_endpoint.

    Intentionally separate from edit_apply.ResolvedLinkEndpoint to keep the
    import graph acyclic; T4-T6 wiring adapts this to ResolvedLinkEndpoint.
    """

    scope_path: str
    uid: str
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None
    slot_index: int | None
    slot_name: str
    socket_type: str | None


# ── internal helpers ──────────────────────────────────────────────────────────

def _normalize_type(value: Any) -> str | None:
    """Normalise a socket-type label to uppercase, returning None for wildcards."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text in {"*", "UNKNOWN"}:
        return None
    return text


def _find_named_slot(slots: Any, name: str) -> dict[str, Any] | None:
    """Return the first slot dict whose 'name' key matches *name*, or None."""
    if not isinstance(slots, list):
        return None
    for item in slots:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None


def _positional_output_alias_index(output_slot: Any) -> int | None:
    if not isinstance(output_slot, str):
        return None
    match = _OUTPUT_ALIAS_RE.fullmatch(output_slot)
    if match is None:
        return None
    return int(match.group(1))


def _output_name_at(outputs: list[Any], index: int) -> str:
    output = outputs[index]
    if isinstance(output, Mapping):
        name = output.get("name")
        if isinstance(name, str) and name:
            return name
    return f"output_{index}"


def _output_type_at(outputs: list[Any], index: int) -> str | None:
    output = outputs[index]
    if isinstance(output, Mapping):
        return _normalize_type(output.get("type"))
    return None


def _available_output_names(outputs: list[Any]) -> list[str]:
    return [
        str(output.get("name"))
        for output in outputs
        if isinstance(output, Mapping) and isinstance(output.get("name"), str) and output.get("name")
    ]


def _make_issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    scope_path: str | None = None,
    uid: str | None = None,
    detail: dict[str, Any] | None = None,
) -> ResolutionIssue:
    return ResolutionIssue(
        code=code,
        message=message,
        severity=severity,
        scope_path=scope_path,
        uid=uid,
        detail=dict(detail or {}),
    )


# ── ResolutionContext ─────────────────────────────────────────────────────────

class ResolutionContext:
    """Unified resolution engine — backend-agnostic, used by lint.

    All methods are stateless: they take a NodeBackend (LintIndexBackend)
    plus the op reference, and return ResolveResult[T].
    The instance itself carries no per-graph state.
    """

    # -- uid resolution --------------------------------------------------------

    def resolve_uid(
        self,
        backend: NodeBackend,
        scope_path: str,
        uid_str: str,
    ) -> ResolveResult[str]:
        """Resolve a uid string to the canonical uid, handling LG-id aliases."""
        if backend.node_exists(scope_path, uid_str):
            return ResolveResult(uid_str, [])
        lg_id = _try_parse_lg_id(uid_str)
        if lg_id is not None:
            resolved = backend.uid_for_lg_id(scope_path, lg_id)
            if resolved is not None:
                return ResolveResult(resolved, [])
            return ResolveResult(None, [_make_issue(
                "unknown_target",
                f"LiteGraph id {lg_id} does not resolve to a known node.",
                scope_path=scope_path,
                detail={"lg_id": lg_id},
            )])
        return ResolveResult(None, [_make_issue(
            "unknown_target",
            f"'{uid_str}' does not match any known node.",
            scope_path=scope_path,
            uid=uid_str,
        )])

    # -- structured target resolution -----------------------------------------

    def resolve_node_target(
        self,
        backend: NodeBackend,
        target: NodeTarget,
    ) -> ResolveResult[NodeTarget]:
        """Resolve a NodeTarget, rewriting LG-id aliases to canonical uids."""
        result = self.resolve_uid(backend, target.scope_path, target.uid)
        if result.value is None:
            return ResolveResult(None, result.issues)
        if result.value == target.uid:
            return ResolveResult(target, [])
        return ResolveResult(
            NodeTarget(scope_path=target.scope_path, uid=result.value), []
        )

    def resolve_node_field_target(
        self,
        backend: NodeBackend,
        target: NodeFieldTarget,
    ) -> ResolveResult[NodeFieldTarget]:
        """Resolve a NodeFieldTarget, rewriting LG-id aliases to canonical uids."""
        result = self.resolve_uid(backend, target.scope_path, target.uid)
        if result.value is None:
            return ResolveResult(None, result.issues)
        if result.value == target.uid:
            return ResolveResult(target, [])
        return ResolveResult(
            NodeFieldTarget(
                scope_path=target.scope_path,
                uid=result.value,
                field_path=target.field_path,
            ),
            [],
        )

    def resolve_link_source(
        self,
        backend: NodeBackend,
        source: LinkSourceRef,
    ) -> ResolveResult[LinkSourceRef]:
        """Resolve source uid, normalising LG-id aliases to canonical uids."""
        result = self.resolve_uid(backend, source.scope_path, source.uid)
        if result.value is None:
            return ResolveResult(None, result.issues)
        if result.value == source.uid:
            return ResolveResult(source, [])
        return ResolveResult(
            LinkSourceRef(
                scope_path=source.scope_path,
                uid=result.value,
                output_slot=source.output_slot,
            ),
            [],
        )

    def resolve_link_target(
        self,
        backend: NodeBackend,
        target: LinkTargetRef,
    ) -> ResolveResult[LinkTargetRef]:
        """Resolve target uid, normalising LG-id aliases to canonical uids."""
        result = self.resolve_uid(backend, target.scope_path, target.uid)
        if result.value is None:
            return ResolveResult(None, result.issues)
        if result.value == target.uid:
            return ResolveResult(target, [])
        return ResolveResult(
            LinkTargetRef(
                scope_path=target.scope_path,
                uid=result.value,
                input_field=target.input_field,
            ),
            [],
        )

    # -- slot index resolution -------------------------------------------------

    def resolve_output_slot_index(
        self,
        backend: NodeBackend,
        scope_path: str,
        uid: str,
        output_slot: str | int,
        *,
        schema_provider: Any = None,
    ) -> ResolveResult[int]:
        """Resolve an output_slot (int index or str name) to a slot index."""
        node = backend.node_for(scope_path, uid)
        if node is None:
            return ResolveResult(None, [_make_issue(
                "unknown_target",
                f"Node '{uid}' not found in scope '{scope_path}'.",
                scope_path=scope_path, uid=uid,
            )])
        outputs = node.get("outputs")
        if not isinstance(outputs, list):
            return ResolveResult(None, [_make_issue(
                "missing_source_outputs",
                f"Node '{uid}' has no outputs.",
                scope_path=scope_path, uid=uid,
            )])
        if isinstance(output_slot, int):
            if 0 <= output_slot < len(outputs):
                return ResolveResult(output_slot, [])
            return ResolveResult(None, [_make_issue(
                "unknown_output_slot",
                f"Node '{uid}' has no output slot {output_slot}.",
                scope_path=scope_path, uid=uid,
                detail={"output_slot": output_slot},
            )])
        slot_str = str(output_slot)
        for index, entry in enumerate(outputs):
            if isinstance(entry, Mapping) and entry.get("name") == slot_str:
                return ResolveResult(index, [])
        alias_index = _positional_output_alias_index(output_slot)
        if alias_index is not None and 0 <= alias_index < len(outputs):
            if len(outputs) == 1:
                return ResolveResult(alias_index, [])
            return ResolveResult(None, [_make_issue(
                "ambiguous_output_alias",
                (
                    f"Node '{uid}' output {slot_str!r} is positional, but the node has "
                    "multiple named outputs; use the exact output slot name instead."
                ),
                scope_path=scope_path, uid=uid,
                detail={
                    "output_slot": output_slot,
                    "slot_index": alias_index,
                    "available_slots": _available_output_names(outputs),
                },
            )])
        schema = None
        if schema_provider is not None:
            class_type = str(node.get("type") or node.get("class_type") or "")
            if class_type:
                try:
                    from vibecomfy.schema import schema_for  # noqa: PLC0415

                    schema = schema_for(schema_provider, class_type)
                except ImportError:
                    schema = None
        port = resolve_working_port(node, "output", slot_str, schema=schema)
        if port.ok and isinstance(port.slot_index, int):
            return ResolveResult(port.slot_index, [])
        return ResolveResult(None, [_make_issue(
            port.code or "unknown_output_slot",
            port.message or f"Node '{uid}' has no output named {slot_str!r}.",
            scope_path=scope_path, uid=uid,
            detail={"output_slot": output_slot, **port.detail},
        )])

    def resolve_input_slot_index(
        self,
        backend: NodeBackend,
        scope_path: str,
        uid: str,
        input_field: str,
    ) -> ResolveResult[int]:
        """Resolve an input_field name to a slot index via node metadata."""
        meta = backend.node_meta_for(scope_path, uid)
        if meta is None:
            return ResolveResult(None, [_make_issue(
                "unknown_target",
                f"Node '{uid}' not found in scope '{scope_path}'.",
                scope_path=scope_path, uid=uid,
            )])
        try:
            idx = meta.input_names.index(input_field)
            return ResolveResult(idx, [])
        except ValueError:
            return ResolveResult(None, [_make_issue(
                "unknown_target_input",
                f"Node has no input named {input_field!r}.",
                scope_path=scope_path, uid=uid,
                detail={"input_field": input_field},
            )])

    # -- endpoint resolution ---------------------------------------------------

    def resolve_source_endpoint(
        self,
        backend: NodeBackend,
        ref: LinkSourceRef,
        *,
        schema_provider: Any = None,
    ) -> ResolveResult[ResolvedEndpoint]:
        """Resolve a LinkSourceRef to a full ResolvedEndpoint.

        Follows apply-side output-slot semantics: int slot by bounds, str slot
        by name scan with optional schema fallback.
        """
        uid_result = self.resolve_uid(backend, ref.scope_path, ref.uid)
        if uid_result.value is None:
            return ResolveResult(None, uid_result.issues)
        resolved_uid = uid_result.value

        node = backend.node_for(ref.scope_path, resolved_uid)
        if node is None:
            return ResolveResult(None, [_make_issue(
                "unknown_target",
                f"Node '{resolved_uid}' not found in scope '{ref.scope_path}'.",
                scope_path=ref.scope_path, uid=resolved_uid,
            )])

        class_type = str(node.get("type") or node.get("class_type") or "")
        node_id = node.get("id")
        outputs = node.get("outputs")
        if not isinstance(outputs, list):
            return ResolveResult(None, [_make_issue(
                "missing_source_outputs",
                f"{class_type} has no outputs to link from.",
                scope_path=ref.scope_path, uid=resolved_uid,
            )])

        slot_index = None
        slot_name = None
        socket_type = None

        if isinstance(ref.output_slot, int):
            if ref.output_slot < 0 or ref.output_slot >= len(outputs):
                return ResolveResult(None, [_make_issue(
                    "unknown_output_slot",
                    f"{class_type} has no output slot {ref.output_slot}.",
                    scope_path=ref.scope_path, uid=resolved_uid,
                    detail={"output_slot": ref.output_slot},
                )])
            slot_index = ref.output_slot
            output_entry = outputs[slot_index]
            if isinstance(output_entry, Mapping):
                slot_name = str(output_entry.get("name") or slot_index)
                socket_type = _normalize_type(output_entry.get("type"))
        else:
            for index, output_entry in enumerate(outputs):
                if isinstance(output_entry, Mapping) and output_entry.get("name") == ref.output_slot:
                    slot_index = index
                    slot_name = str(ref.output_slot)
                    socket_type = _normalize_type(output_entry.get("type"))
                    break
            alias_index = _positional_output_alias_index(ref.output_slot)
            if slot_index is None and alias_index is not None and 0 <= alias_index < len(outputs):
                if len(outputs) == 1:
                    slot_index = alias_index
                    slot_name = _output_name_at(outputs, alias_index)
                    socket_type = _output_type_at(outputs, alias_index)
                else:
                    return ResolveResult(None, [_make_issue(
                        "ambiguous_output_alias",
                        (
                            f"{class_type}.{ref.output_slot} is a positional output alias, but this node has "
                            "multiple named outputs; use the exact output slot name instead."
                        ),
                        scope_path=ref.scope_path,
                        uid=resolved_uid,
                        detail={
                            "output_slot": ref.output_slot,
                            "slot_index": alias_index,
                            "available_slots": _available_output_names(outputs),
                        },
                    )])
            if slot_index is None:
                schema = None
                if schema_provider is not None:
                    try:
                        from vibecomfy.schema import schema_for  # noqa: PLC0415
                        schema = schema_for(schema_provider, class_type)
                    except ImportError:
                        schema = None
                port = resolve_working_port(
                    node,
                    "output",
                    str(ref.output_slot),
                    schema=schema,
                    class_type=class_type,
                )
                if not port.ok or not isinstance(port.slot_index, int):
                    return ResolveResult(None, [_make_issue(
                        port.code or "unknown_output_slot",
                        port.message or f"{class_type} has no output named {ref.output_slot!r}.",
                        scope_path=ref.scope_path, uid=resolved_uid,
                        detail={"output_slot": ref.output_slot, **port.detail},
                    )])
                slot_index = port.slot_index
                slot_name = port.slot_name
                socket_type = _normalize_type(port.socket_type)

        if slot_name is None:
            slot_name = str(ref.output_slot)

        return ResolveResult(
            ResolvedEndpoint(
                scope_path=ref.scope_path,
                uid=resolved_uid,
                node=node,
                class_type=class_type,
                node_id=node_id,
                slot_index=slot_index,
                slot_name=slot_name,
                socket_type=socket_type,
            ),
            [],
        )

    def resolve_target_endpoint(
        self,
        backend: NodeBackend,
        ref: LinkTargetRef,
        *,
        schema_provider: Any = None,
    ) -> ResolveResult[ResolvedEndpoint]:
        """Resolve a LinkTargetRef to a full ResolvedEndpoint.

        Working-graph inputs are authoritative. Schema may enrich a present
        socket's type; a missing name is accepted only when the shared
        dynamic-port contract authorizes it.
        """
        uid_result = self.resolve_uid(backend, ref.scope_path, ref.uid)
        if uid_result.value is None:
            return ResolveResult(None, uid_result.issues)
        resolved_uid = uid_result.value

        node = backend.node_for(ref.scope_path, resolved_uid)
        if node is None:
            return ResolveResult(None, [_make_issue(
                "unknown_target",
                f"Node '{resolved_uid}' not found in scope '{ref.scope_path}'.",
                scope_path=ref.scope_path, uid=resolved_uid,
            )])

        class_type = str(node.get("type") or node.get("class_type") or "")
        node_id = node.get("id")
        schema = None
        schema_input = None
        if schema_provider is not None:
            try:
                from vibecomfy.schema import schema_for  # noqa: PLC0415
                schema = schema_for(schema_provider, class_type)
                if schema is not None:
                    schema_input = (getattr(schema, "inputs", {}) or {}).get(ref.input_field)
            except ImportError:
                schema = None

        port = resolve_working_port(
            node,
            "input",
            ref.input_field,
            schema=schema,
            class_type=class_type,
        )
        if not port.ok:
            return ResolveResult(None, [_make_issue(
                port.code or "unknown_target_input",
                port.message or f"{class_type} has no input named {ref.input_field!r}.",
                scope_path=ref.scope_path, uid=resolved_uid,
                detail={"input": ref.input_field, **port.detail},
            )])

        slot_index = port.slot_index
        socket_type = _normalize_type(port.socket_type)
        if socket_type is None and schema_input is not None:
            socket_type = _normalize_type(getattr(schema_input, "type", None))

        return ResolveResult(
            ResolvedEndpoint(
                scope_path=ref.scope_path,
                uid=resolved_uid,
                node=node,
                class_type=class_type,
                node_id=node_id,
                slot_index=slot_index,
                slot_name=ref.input_field,
                socket_type=socket_type,
            ),
            [],
        )


# ── adapter ───────────────────────────────────────────────────────────────────

def to_port_issues(result: ResolveResult[Any]) -> list[PortIssue]:
    """Extract a list[PortIssue] from a ResolveResult (adapter for apply shims)."""
    issues: list[PortIssue] = []
    for ri in result.issues:
        detail = dict(ri.detail)
        if ri.scope_path is not None:
            detail.setdefault("scope_path", ri.scope_path)
        if ri.uid is not None:
            detail.setdefault("uid", ri.uid)
        issues.append(PortIssue(
            code=ri.code,
            message=ri.message,
            severity=ri.severity,  # type: ignore[arg-type]
            node_id=ri.uid,
            detail=detail,
        ))
    return issues


