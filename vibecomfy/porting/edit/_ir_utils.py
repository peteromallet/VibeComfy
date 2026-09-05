from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
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


class RecursiveEditError(ValueError):
    """A recursive edit that cannot be proved against canonical typed IR."""

    def __init__(self, code: str, message: str, *, detail: Mapping[str, Any] | None = None) -> None:
        self.code = str(code)
        self.detail = dict(detail or {})
        super().__init__(message)


_RECURSIVE_GUIDANCE = "capture -> port through canonical Python -> reopen/reload"
_NATIVE_BOUNDARY_SENTINELS = frozenset({"-10", "-20"})


@dataclass(slots=True)
class RecursiveNodeRef:
    scope_path: str
    uid: str
    node: Any
    node_id: str


@dataclass(slots=True)
class RecursiveScopeRef:
    scope_path: str
    sg_key: str | None
    definition: dict[str, Any] | None
    nodes: dict[str, RecursiveNodeRef]
    ui_scope_path: str = ""


@dataclass(slots=True)
class RecursiveEditIndex:
    """Ephemeral lookup over live canonical definition objects.

    This deliberately contains references into ``workflow.definitions``; it
    is not a second graph model and never normalizes or serializes nodes.
    """

    scopes: dict[str, RecursiveScopeRef]

    @property
    def ui_scope_aliases(self) -> dict[str, str]:
        """Return disposable emitted ``sgN`` paths for guard attribution only."""
        return {
            scope_path: scope.ui_scope_path
            for scope_path, scope in self.scopes.items()
        }

    def scope(self, scope_path: str) -> RecursiveScopeRef:
        if not isinstance(scope_path, str):
            raise RecursiveEditError("invalid_scope", "scope_path must be a string")
        from vibecomfy.identity.scope import compose_scope_path

        parts = tuple(scope_path.split("/")) if scope_path else ()
        try:
            canonical = compose_scope_path(parts)
        except ValueError as exc:
            raise RecursiveEditError("invalid_scope", f"{exc}; {_RECURSIVE_GUIDANCE}", detail={"scope_path": scope_path}) from exc
        if canonical != scope_path:
            raise RecursiveEditError("invalid_scope", f"scope_path {scope_path!r} is not canonical; {_RECURSIVE_GUIDANCE}")
        try:
            return self.scopes[scope_path]
        except KeyError as exc:
            raise RecursiveEditError(
                "scope_unknown",
                f"unknown recursive scope {scope_path!r}; {_RECURSIVE_GUIDANCE}",
                detail={"scope_path": scope_path},
            ) from exc

    def node(self, scope_path: str, uid: str) -> RecursiveNodeRef:
        scope = self.scope(scope_path)
        try:
            return scope.nodes[str(uid)]
        except KeyError as exc:
            raise RecursiveEditError(
                "unknown_target", f"no node {uid!r} in scope {scope_path!r}",
                detail={"scope_path": scope_path, "uid": str(uid)},
            ) from exc


def _recursive_entries(raw: Any) -> list[Any]:
    if not raw:
        return []
    if isinstance(raw, Mapping) and isinstance(raw.get("subgraphs"), (list, tuple)):
        return list(raw["subgraphs"])
    if isinstance(raw, Mapping):
        return list(raw.values())
    if isinstance(raw, (list, tuple)):
        return list(raw)
    raise RecursiveEditError("definitions_malformed", "definitions must be a mapping or sequence")


def _recursive_node_entries(definition: Mapping[str, Any]) -> list[Any]:
    raw = definition.get("nodes", ())
    if isinstance(raw, Mapping):
        return list(raw.values())
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if raw in (None, ()):
        return []
    raise RecursiveEditError("nodes_malformed", "definition nodes must be a mapping or sequence")


def _recursive_node_identity(node: Mapping[str, Any], scope_path: str, index: int) -> tuple[str, str]:
    from vibecomfy.identity.uid import UIDValidationError, validate_local_uid

    uid = node.get("uid")
    if not isinstance(uid, str) or not uid.strip():
        props = node.get("properties")
        uid = props.get("vibecomfy_uid") if isinstance(props, Mapping) else None
    if not isinstance(uid, str) or not uid.strip():
        uid = node.get("id")
    try:
        local_uid = validate_local_uid(str(uid), field=f"definition {scope_path!r} node[{index}] uid")
        node_id = validate_local_uid(str(node.get("id", local_uid)), field="definition node id")
    except UIDValidationError as exc:
        raise RecursiveEditError("invalid_node_uid", str(exc), detail={"scope_path": scope_path}) from exc
    return local_uid, node_id


def build_recursive_edit_index(workflow: "VibeWorkflow") -> RecursiveEditIndex:
    """Index root and typed definitions by canonical ``scope_path``/local UID."""
    from vibecomfy.identity.scope import compose_scope_path, sg_key

    scopes: dict[str, RecursiveScopeRef] = {
        "": RecursiveScopeRef("", None, None, {}, "")
    }
    root = scopes[""]
    root_aliases: dict[str, str] = {}
    for node_id, node in (getattr(workflow, "nodes", {}) or {}).items():
        uid = str(getattr(node, "uid", "") or node_id)
        if uid in root_aliases or str(node_id) in root_aliases:
            raise RecursiveEditError("occurrence_collision", f"duplicate root node identity {uid!r}")
        ref = RecursiveNodeRef("", uid, node, str(node_id))
        root.nodes[uid] = ref
        root_aliases[uid] = uid
        root_aliases[str(node_id)] = uid

    seen_keys: set[str] = set()
    active: set[int] = set()

    def walk(raw: Any, parent: tuple[str, ...], ui_parent: str) -> None:
        for index, definition in enumerate(_recursive_entries(raw)):
            if not isinstance(definition, dict):
                raise RecursiveEditError("definitions_malformed", "each definition must be a mapping")
            identity = id(definition)
            if identity in active:
                raise RecursiveEditError("recursive_definition_cycle", "recursive definition object graph cannot be edited")
            active.add(identity)
            derived = sg_key(definition)
            supplied = definition.get("sg_key")
            if supplied is not None and supplied != derived:
                raise RecursiveEditError("definition_scope_collision", "definition sg_key does not match its structural identity")
            if derived in seen_keys:
                raise RecursiveEditError("definition_scope_collision", f"duplicate definition sg_key {derived!r}")
            try:
                path = compose_scope_path((*parent, derived))
            except ValueError as exc:
                raise RecursiveEditError("invalid_scope", str(exc)) from exc
            if path in scopes:
                raise RecursiveEditError("definition_scope_collision", f"duplicate definition scope {path!r}")
            ui_path = f"{ui_parent}/sg{index}" if ui_parent else f"sg{index}"
            scope = RecursiveScopeRef(path, derived, definition, {}, ui_path)
            scopes[path] = scope
            seen_keys.add(derived)
            aliases: dict[str, str] = {}
            for index, node in enumerate(_recursive_node_entries(definition)):
                if not isinstance(node, dict):
                    raise RecursiveEditError("nodes_malformed", f"node {index} in {path!r} is not a mapping")
                uid, node_id = _recursive_node_identity(node, path, index)
                if uid in scope.nodes or uid in aliases or node_id in aliases:
                    raise RecursiveEditError("occurrence_collision", f"duplicate node identity {uid!r} in {path!r}")
                ref = RecursiveNodeRef(path, uid, node, node_id)
                scope.nodes[uid] = ref
                aliases[uid] = uid
                aliases[node_id] = uid
            # Validate and canonicalize topology through the same helper used
            # by diff and apply-gate signatures. Link IDs and order are not
            # semantic; scoped UID/slot/type endpoints are.
            recursive_scope_topology(scope)
            _validate_recursive_carriers(scope)
            walk(definition.get("definitions"), (*parent, derived), ui_path)
            active.remove(identity)

    walk(getattr(workflow, "definitions", None), (), "")

    # Compiler/materializer interfaces may be keyed by a globally unique
    # definition ``sg_key`` (the legacy/native-compatible spelling) or by the
    # canonical nested path.  The edit vocabulary remains path-only: these
    # aliases are used solely to validate existing typed carriers and are
    # never accepted as operation scope paths.
    scope_aliases: dict[str, str] = {"": ""}
    for scope_path, scope in scopes.items():
        if scope_path and scope.sg_key:
            scope_aliases[str(scope.sg_key)] = scope_path

    def canonical_carrier_scope(raw_scope: Any, kind: str) -> str:
        scope_path = str(raw_scope or "")
        if not scope_path:
            return ""
        if scope_path.startswith("sg") and scope_path[2:].isdigit():
            raise RecursiveEditError(
                "invalid_scope",
                f"ordinal scope path {scope_path!r} is not canonical; {_RECURSIVE_GUIDANCE}",
            )
        if scope_path in scopes:
            return scope_path
        alias = scope_aliases.get(scope_path)
        if alias is not None:
            return alias
        try:
            canonical = compose_scope_path(tuple(scope_path.split("/")))
        except ValueError as exc:
            raise RecursiveEditError(
                "invalid_scope",
                f"{exc}; {_RECURSIVE_GUIDANCE}",
                detail={"scope_path": scope_path},
            ) from exc
        if canonical in scopes:
            return canonical
        raise RecursiveEditError(
            "scope_unknown",
            f"{kind} scope {scope_path!r} is not indexed; {_RECURSIVE_GUIDANCE}",
        )

    # These are canonical references, not copied records.  Scope-check their
    # selectors so an interface/boundary/wire cannot silently bind another
    # definition; their object mutation remains unsupported in this task.
    interfaces = getattr(workflow, "interfaces", {})
    if interfaces and not isinstance(interfaces, Mapping):
        raise RecursiveEditError("interfaces_malformed", "interfaces must be a mapping")
    for scope_path in (interfaces or {}):
        canonical_carrier_scope(scope_path, "interface")
    boundary_ports = getattr(workflow, "boundary_ports", [])
    if boundary_ports and not isinstance(boundary_ports, (list, tuple)):
        raise RecursiveEditError("boundary_ports_malformed", "boundary_ports must be a sequence")

    for port in boundary_ports or ():
        if not isinstance(port, Mapping):
            raise RecursiveEditError("boundary_ports_malformed", "boundary port must be a mapping")
        scope_path = str(port.get("scope_path", ""))
        scope_path = canonical_carrier_scope(scope_path, "boundary")
        _reject_native_carrier_values(port, context="boundary_ports")
    virtual_wires = getattr(workflow, "virtual_wires", {})
    if virtual_wires and not isinstance(virtual_wires, Mapping):
        raise RecursiveEditError("virtual_wires_malformed", "virtual_wires must be a mapping")
    for raw in (virtual_wires or {}).values():
        if not isinstance(raw, Mapping):
            raise RecursiveEditError("virtual_wires_malformed", "virtual wire must be a mapping")
        legs = raw.get("legs", ())
        if not isinstance(legs, (list, tuple)):
            raise RecursiveEditError("virtual_wires_malformed", "virtual wire legs must be a sequence")
        for leg in legs:
            if not isinstance(leg, Mapping):
                raise RecursiveEditError("virtual_wires_malformed", "virtual wire leg must be a mapping")
            scope_path = str(leg.get("scope_path", raw.get("scope_path", "")))
            scope_path = canonical_carrier_scope(scope_path, "virtual wire")
            _reject_native_carrier_values(leg, context="virtual_wires")

    if interfaces or boundary_ports or virtual_wires:
        try:
            workflow._execution_projection()
        except Exception as exc:
            raise RecursiveEditError(
                str(getattr(exc, "code", "recursive_contract_invalid")),
                str(exc),
                detail=getattr(exc, "detail", {}),
            ) from exc
    return RecursiveEditIndex(scopes)


def _reject_native_carrier_values(value: Any, *, context: str) -> None:
    """Reject LiteGraph's native boundary sentinels in carrier records."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            if key_text in {"link", "links", "from_port", "to_port", "from_output",
                            "to_input", "origin_slot", "target_slot", "inputNode", "outputNode"}:
                values = item if key_text == "links" and isinstance(item, (list, tuple)) else (item,)
                for candidate in values:
                    if str(candidate) in _NATIVE_BOUNDARY_SENTINELS:
                        raise RecursiveEditError(
                            "unsupported_boundary_encoding",
                            f"native -10/-20 carrier in {context}; {_RECURSIVE_GUIDANCE}",
                        )
            _reject_native_carrier_values(item, context=context)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_native_carrier_values(item, context=context)


def _validate_recursive_carriers(scope: RecursiveScopeRef) -> None:
    for ref in scope.nodes.values():
        _reject_native_carrier_values(ref.node.get("inputs"), context=f"{scope.scope_path} inputs")
        _reject_native_carrier_values(ref.node.get("outputs"), context=f"{scope.scope_path} outputs")
    _reject_native_carrier_values(
        (scope.definition or {}).get("virtual_wires"), context=f"{scope.scope_path} virtual_wires"
    )


def _recursive_link_parts(link: Any) -> tuple[Any, Any, Any, Any, Any, Any] | None:
    if isinstance(link, Mapping):
        return (link.get("id"), link.get("origin_id"), link.get("origin_slot", 0), link.get("target_id"), link.get("target_slot", 0), link.get("type", ""))
    if isinstance(link, (list, tuple)) and len(link) >= 6:
        return tuple(link[:6])  # type: ignore[return-value]
    return None


def recursive_scope_topology(scope: RecursiveScopeRef) -> tuple[tuple[str, str, str, str, str], ...]:
    """Canonical same-scope topology, omitting volatile link IDs/order."""
    by_identity = {
        str(identity): ref.uid
        for ref in scope.nodes.values()
        for identity in (ref.uid, ref.node_id)
    }
    records: list[tuple[str, str, str, str, str]] = []
    for link in (scope.definition or {}).get("links", ()) or ():
        parts = _recursive_link_parts(link)
        if parts is None:
            raise RecursiveEditError("links_malformed", f"malformed link in {scope.scope_path!r}")
        _link_id, origin, origin_slot, target, target_slot, link_type = parts
        if str(origin) in _NATIVE_BOUNDARY_SENTINELS or str(target) in _NATIVE_BOUNDARY_SENTINELS:
            raise RecursiveEditError(
                "unsupported_boundary_encoding",
                "native -10/-20 boundary links are unproven; "
                "capture -> port through canonical Python -> reopen/reload",
            )
        origin_uid = by_identity.get(str(origin))
        target_uid = by_identity.get(str(target))
        if origin_uid is None or target_uid is None:
            raise RecursiveEditError(
                "unknown_target",
                f"link endpoint is not local to {scope.scope_path!r}",
            )
        records.append(
            (
                origin_uid,
                str(origin_slot),
                target_uid,
                str(target_slot),
                str(link_type),
            )
        )
    return tuple(sorted(records))


def _operation_scope_paths(op: EditOp) -> tuple[str, ...]:
    """Extract every operation-owned scope reference, including AddNode refs."""
    paths: list[str] = []
    direct = getattr(op, "scope_path", None)
    if direct is not None:
        paths.append(str(direct))
    for attr in ("target", "source"):
        ref = getattr(op, attr, None)
        if ref is not None:
            paths.append(str(getattr(ref, "scope_path", "") or ""))
    if isinstance(op, AddNodeOp):
        paths.extend(str(getattr(ref, "scope_path", "") or "") for ref in op.inputs.values())
        anchor = getattr(op, "anchor", None)
        if anchor is not None:
            near = getattr(anchor, "near", None)
            if near is not None:
                paths.append(str(getattr(near, "scope_path", "") or ""))
            paths.extend(
                str(getattr(ref, "scope_path", "") or "")
                for ref in (getattr(anchor, "between", None) or ())
            )
    return tuple(paths)


def _has_recursive_scope(ops: Sequence[EditOp]) -> bool:
    return any(bool(path) for op in ops for path in _operation_scope_paths(op))


def _has_mixed_recursive_scope(ops: Sequence[EditOp]) -> bool:
    scoped = [_has_recursive_scope((op,)) for op in ops]
    return bool(scoped) and any(scoped) and not all(scoped)


def _recursive_field_entries(
    node: Mapping[str, Any],
) -> tuple[tuple[str, str, Any, bool], ...]:
    """Collect authored recursive fields from mapping and normalized list channels.

    The normalized definition IR retains LiteGraph input sockets as records
    (``[{name, type, link, value?}]``), while authored widgets may remain a
    positional ``widgets_values`` list.  This is one shared field authority
    for validation, COW, and diff; it never serializes or copies a node.
    """
    entries: list[tuple[str, str, Any, bool]] = []
    seen: set[str] = set()

    def add(name: Any, channel: str, value: Any, linked: bool) -> None:
        key = str(name)
        if key in seen:
            return
        seen.add(key)
        entries.append((key, channel, value, linked))

    for channel in ("inputs", "widgets", "semantic"):
        values = node.get(channel)
        if isinstance(values, Mapping):
            for name, value in values.items():
                add(name, channel, value, False)
        elif isinstance(values, (list, tuple)):
            for item in values:
                if not isinstance(item, Mapping) or item.get("name") is None:
                    continue
                add(
                    item["name"],
                    channel,
                    item.get("value"),
                    item.get("link") is not None,
                )
    values = node.get("widgets_values")
    if isinstance(values, (list, tuple)):
        for index, value in enumerate(values):
            add(f"widget_{index}", "widgets_values", value, False)
    return tuple(entries)


def _freeze(value: Any) -> Any:
    """Freeze JSON-shaped authored state for quotient comparison."""
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


def recursive_state_snapshot(
    workflow: "VibeWorkflow",
    *,
    index: RecursiveEditIndex | None = None,
) -> tuple[Any, ...]:
    """Return the one immutable recursive state/topology quotient.

    Both diff and replay-gate consume this snapshot. It contains authored
    fields plus interface, boundary, virtual-wire, and group visibility, but
    omits presentation/provenance and volatile link IDs/order.
    """
    indexed = index or build_recursive_edit_index(workflow)
    definitions: list[Any] = []
    nodes: list[Any] = []
    topology: list[Any] = []
    for scope_path, scope in sorted(indexed.scopes.items()):
        if not scope_path:
            continue
        definition = scope.definition or {}
        definitions.append((scope_path, str(scope.sg_key or ""), tuple(
            (field, _freeze(definition.get(field)))
            for field in ("interface", "interfaces", "boundary_ports",
                          "virtual_wires", "inputs", "outputs", "groups")
        )))
        for uid, ref in sorted(scope.nodes.items()):
            node = ref.node
            fields = tuple((str(field), str(channel), _freeze(value), bool(linked))
                           for field, channel, value, linked in _recursive_field_entries(node))
            nodes.append((scope_path, str(uid), str(node.get("type", node.get("class_type", ""))),
                          int(node.get("mode", 0) or 0), _freeze(node.get("group")), fields))
        topology.extend((scope_path, *record) for record in recursive_scope_topology(scope))
    carriers = (
        ("interfaces", _freeze(getattr(workflow, "interfaces", {}))),
        ("boundary_ports", _freeze(getattr(workflow, "boundary_ports", ()))),
        ("virtual_wires", _freeze(getattr(workflow, "virtual_wires", {}))),
        ("groups", _freeze(getattr(workflow, "groups", ()))),
    )
    return (
        tuple(definitions),
        tuple(nodes),
        tuple(sorted(topology)),
        carriers,
    )


def _is_primitive_widget_alias_class(class_type: str) -> bool:
    """Return whether ``value`` and compact widget zero are one field."""
    return class_type in {"Float", "Int"} or class_type.startswith("Primitive")


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
        node, field, schema_provider=schema_provider, name_authority=name_authority
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
        node, field, schema_provider=schema_provider, name_authority=name_authority
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
        return ((str(getattr(op, "scope_path", "") or ""), str(op.id)),)
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

    Root VibeNode resolution remains the existing COW path; typed recursive
    definitions are resolved by ``build_recursive_edit_index``.
    """
    if scope_path:
        raise RecursiveEditError(
            "unsupported_structural_scope",
            f"subgraph-scope target {scope_path!r} is not a supported root edit; "
            "capture the current canvas/export, port through canonical Python, "
            "then reopen/reload the resulting workflow",
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


def _tag_edit_provenance(node: Any, *source_nodes: Any, fresh: bool = False) -> None:
    """Compose one provenance policy across VibeNodes and typed mappings."""
    from vibecomfy.security import provenance as _prov

    sources = tuple(_prov.read(source) for source in source_nodes)
    if isinstance(node, Mapping):
        metadata = node.get("metadata")
        if metadata is None:
            metadata = {}
            node["metadata"] = metadata  # type: ignore[index]
        if not isinstance(metadata, dict):
            raise RecursiveEditError(
                "provenance_unavailable",
                "recursive edit cannot establish canonical provenance; "
                "capture -> port through canonical Python -> reopen/reload",
            )
        metadata[_prov.PROVENANCE_KEY] = _prov.join(
            metadata.get(_prov.PROVENANCE_KEY),
            _prov.Provenance.AGENT_GENERATED,
            *sources,
        )
        return
    prior = () if fresh else (_prov.read(node),)
    _prov.tag(node, _prov.join(*prior, _prov.Provenance.AGENT_GENERATED, *sources))


def _recursive_field(node: Mapping[str, Any], field: str) -> tuple[str, Any] | None:
    """Resolve only authored definition fields; never invent a sidecar field."""
    if field in {
        "type", "class_type", "id", "uid", "properties", "metadata",
        "outputs", "links", "pos", "size", "flags", "order", "groups", "group",
        "inputs", "widgets", "widgets_values",
    }:
        return ("structural", node.get(field))
    if field == "mode":
        return ("mode", node.get("mode", 0))
    if field in node and field not in {"type", "class_type", "id", "uid", "properties", "metadata"}:
        return (field, node[field])
    for name, channel, value, _linked in _recursive_field_entries(node):
        if name == field:
            return (f"{channel}.{field}", value)
    return None


def _set_recursive_field(node: dict[str, Any], field: str, value: Any) -> None:
    if field in {
        "type", "class_type", "id", "uid", "properties", "metadata",
        "outputs", "links", "pos", "size", "flags", "order", "groups", "group",
        "inputs", "widgets", "widgets_values",
    }:
        raise RecursiveEditError("unsupported_structural_scope", f"field {field!r} changes definition identity")
    if field == "mode":
        node["mode"] = int(value)
        return
    if field in node and field not in {"inputs", "widgets", "metadata", "semantic", "widgets_values"}:
        node[field] = deepcopy(value)
        return
    for channel in ("inputs", "widgets", "semantic"):
        values = node.get(channel)
        if isinstance(values, dict) and field in values:
            values[field] = deepcopy(value)
            return
        if isinstance(values, list):
            for item in values:
                if isinstance(item, dict) and str(item.get("name", "")) == field:
                    if item.get("link") not in (None,):
                        raise RecursiveEditError("unsupported_structural_scope", "linked input edits require a canonical link transaction")
                    item["value"] = deepcopy(value)
                    return
    values = node.get("widgets_values")
    if isinstance(values, list) and field.startswith("widget_") and field[7:].isdigit():
        index = int(field[7:])
        if index < len(values):
            values[index] = deepcopy(value)
            return
    raise RecursiveEditError("unknown_field", f"field {field!r} is not authored in the recursive node")


def _unsupported_recursive_structure(op: EditOp) -> RecursiveEditError:
    scope = next((path for path in _operation_scope_paths(op) if path), "")
    return RecursiveEditError(
        "unsupported_structural_scope",
        f"{getattr(op, 'op', type(op).__name__)} at scope {scope!r} changes unsupported recursive structure; "
        "capture the current canvas/export, port through canonical Python, "
        "then reopen/reload the resulting workflow",
        detail={"scope_path": scope, "operation": getattr(op, "op", type(op).__name__)},
    )


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
    Provenance is composed by the shared edit provenance helper.
    """
    from vibecomfy.workflow import VibeEdge, VibeNode, litegraph_to_mode

    if isinstance(op, AddNodeOp) and any(_operation_scope_paths(op)):
        raise _unsupported_recursive_structure(op)
    if isinstance(op, AddNodeOp) and getattr(op.anchor, "group_title", None):
        raise RecursiveEditError(
            "unsupported_operation",
            "group/layout edits are unsupported; capture the current canvas/export, "
            "port through canonical Python, then reopen/reload the resulting workflow",
        )

    post = _cow_workflow_copy(workflow)
    # P0-WIDGET-CANON: the sealed snapshot table is the sole name authority
    # for name→slot resolution during apply (and therefore replay).
    from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid  # noqa: PLC0415

    name_authority = frozen_widget_names_by_uid(workflow)

    if isinstance(op, SetNodeFieldOp):
        if op.target.scope_path:
            ref = build_recursive_edit_index(post).node(op.target.scope_path, op.target.uid)
            resolved = _recursive_field(ref.node, op.target.field_path)
            if resolved is None:
                raise RecursiveEditError("unknown_field", f"field {op.target.field_path!r} is not authored in the recursive node")
            if resolved[1] == op.value:
                raise ValueError(f"set_node_field: {op.target.field_path!r} is already set to that value")
            _set_recursive_field(ref.node, op.target.field_path, op.value)
            _tag_edit_provenance(ref.node)
            return post
        node_id, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node is None:
            raise KeyError(
                f"set_node_field: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        field = op.target.field_path
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
        _tag_edit_provenance(node)
        return post

    if isinstance(op, SetModeOp):
        if op.target.scope_path:
            ref = build_recursive_edit_index(post).node(op.target.scope_path, op.target.uid)
            current = int(ref.node.get("mode", 0) or 0)
            if current == int(op.mode):
                raise ValueError(f"set_mode: node {op.target.uid!r} already has mode {op.mode}")
            ref.node["mode"] = int(op.mode)
            _tag_edit_provenance(ref.node)
            return post
        _, node = _root_node_for_uid(post, op.target.scope_path, op.target.uid)
        if node is None:
            raise KeyError(
                f"set_mode: no IR node for uid {op.target.uid!r} in workflow {workflow.id!r}"
            )
        node.mode = litegraph_to_mode(op.mode)
        _tag_edit_provenance(node)
        return post

    if isinstance(op, RemoveLinkOp):
        if op.target is not None and op.target.scope_path:
            raise _unsupported_recursive_structure(op)
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
        _tag_edit_provenance(node)
        return post

    if isinstance(op, UpsertLinkOp):
        if op.source.scope_path or op.target.scope_path:
            raise _unsupported_recursive_structure(op)
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
        _tag_edit_provenance(source_node)
        _tag_edit_provenance(target_node, source_node)
        return post

    if isinstance(op, RemoveNodeOp):
        if op.target.scope_path:
            raise _unsupported_recursive_structure(op)
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
        if getattr(op, "scope_path", ""):
            raise _unsupported_recursive_structure(op)
        if getattr(workflow, "definitions", None):
            raise _unsupported_recursive_structure(op)
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
        if op.action == "remove":
            definitions["subgraphs"] = [
                entry for entry in subgraphs if _entry_key(entry) != subgraph_id
            ]
            return post
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
        else:
            definitions["subgraphs"] = [
                *subgraphs,
                {**signature, "nodes": [], "links": []},
            ]
        return post

    if isinstance(op, AddNodeOp):
        if op.scope_path:
            build_recursive_edit_index(post).scope(op.scope_path)
            raise _unsupported_recursive_structure(op)
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
        _tag_edit_provenance(node, *source_nodes, fresh=True)
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
