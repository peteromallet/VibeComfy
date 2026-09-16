"""Canonical workflow source bundles.

This module is deliberately a small binding around :class:`VibeWorkflow`.
The workflow remains the only semantic authority; a bundle only records where
it was loaded from, the optional presentation candidate, and deterministic
digests for that candidate revision.  In particular, this is not an approval
or execution registry.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import os
import shlex
import shutil
import tempfile
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.security.provenance import Provenance
from vibecomfy.testing.canonical import canonical_digest, canonical_json
from vibecomfy.identity.uid import make_uid, validate_local_uid
from vibecomfy.identity.uid import parse_uid
from vibecomfy.workflow import (
    VibeWorkflow,
    WorkflowCompileError,
    WorkflowSource,
    _port_index_for_node,
    _resolve_virtual_wire_legs,
    canonical_ir_projection,
)
from vibecomfy.model_assets import reconcile_model_requirements


class WorkflowBundleError(ValueError):
    """Raised when a bundle cannot be loaded or fails a closed boundary."""


class WorkflowReconciliationError(WorkflowBundleError):
    """A canonical graph cannot compile until its missing classes are resolved."""

    def __init__(self, missing_classes: tuple[str, ...]) -> None:
        self._missing_classes = tuple(sorted(set(missing_classes)))
        super().__init__(
            "workflow contains unresolved class types: " + ", ".join(self._missing_classes)
        )

    @property
    def missing_classes(self) -> tuple[str, ...]:
        return self._missing_classes


class WorkflowAuthorityError(WorkflowBundleError):
    """Raised when compatibility evidence reaches a canonical consumer."""


def _workflow_authority_error(workflow: VibeWorkflow, action: str) -> WorkflowAuthorityError:
    source_path = getattr(workflow.source, "path", None)
    source = str(source_path or workflow.id)
    quoted_source = shlex.quote(source)
    stem = Path(source).stem or "workflow"
    return WorkflowAuthorityError(
        f"{action} requires canonical Python workflow authority; raw UI/API JSON "
        "is import evidence only. "
        f"Import it first: vibecomfy import {quoted_source}. "
        f"Then validate the bundle with `vibecomfy validate workflows/{shlex.quote(stem)}`."
    )


def _freeze_json(value: Any) -> Any:
    """Detach and recursively freeze one strict JSON-shaped value."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WorkflowBundleError("approved projection cannot contain NaN or infinity")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise WorkflowBundleError("approved projection object keys must be strings")
            if key in frozen:
                raise WorkflowBundleError(f"duplicate approved projection key {key!r}")
            frozen[key] = _freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    raise WorkflowBundleError(
        f"approved projection contains unsupported value {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    """Return a detached ordinary JSON-shaped copy of a frozen value."""
    if isinstance(value, Mapping):
        return {str(key): _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


_IDENTITY_KEYS = frozenset(
    {
        "workflow_id",
        "workflow_identity",
        "source_id",
        "source_identity",
        "bind_id",
        "registry_id",
        "import_id",
        "capture_id",
    }
)
_CONTAINER_ID_KEYS = frozenset(
    {"source", "bind", "registry", "import", "capture", "lineage", "provenance"}
)
_OPERATIONS = frozenset({"authored", "imported", "captured", "ephemeral"})

# This is intentionally a small closed schema.  In particular, do not add a
# catch-all ``properties``/``extra`` member here: those are legacy UI payloads
# and are not an authored source of presentation state.
_SIDECAR_KEYS = frozenset({"format_version", "bind", "nodes", "links", "groups", "canvas"})
_BIND_KEYS = frozenset({"workflow_identity", "semantic_digest"})
# ``class_type`` is required only for a presentation-only node that was
# intentionally stripped from the canonical Python IR.  It is a witness for
# the closed UI-only roster, never an executable/source field.
_NODE_KEYS = frozenset({"id", "pos", "size", "collapsed", "color", "bgcolor", "title", "z_order", "group", "class_type"})
_LINK_KEYS = frozenset({"edge_ref", "virtual_wire_ref", "occurrence_index", "id", "reroute"})
_EDGE_REF_KEYS = frozenset({"scope_path", "from_uid", "from_port", "to_uid", "to_port"})
_VIRTUAL_REF_KEYS = frozenset({"scope_path", "name", "leg_index"})
_GROUP_KEYS = frozenset({"scope_path", "presentation_id", "bounds", "title", "color", "z_order"})
_CANVAS_KEYS = frozenset({"zoom", "pan"})
_ANNOTATION_KEYS = frozenset({
    "annotation_id", "scope_path", "owner", "class_type", "title", "content",
})
_ANNOTATION_OWNER_KEYS = frozenset({"kind", "uid"})
_ANNOTATION_OWNER_KINDS = frozenset({"workflow", "definition", "instance", "node", "group"})

_V2_KEYS = frozenset({"format_version", "bind", "custody", "presentation"})
_V2_BIND_KEYS = frozenset({"workflow_identity", "generation_id", "custody_digest"})
_V2_CUSTODY_KEYS = frozenset({"scopes", "definitions"})
_V2_SCOPE_KEYS = frozenset({"scope_path", "nodes", "helpers"})
_V2_NODE_KEYS = frozenset({
    "label", "id", "uid", "class_type", "native_ports", "metadata",
    "widget_channels", "none_input_fields", "none_widget_fields",
    "output_slot_names", "construction_output_names",
})
_V2_HELPER_KEYS = frozenset({"id", "uid", "class_type", "provenance", "native_ports", "pos", "size"})
_V2_MARKER_KEYS = frozenset({"format_version", "generation_id", "custody_digest"})
_V2_PRESENTATION_KEYS = frozenset({"nodes", "links", "groups", "canvas", "annotations"})
_V2_RECURSIVE_DEFINITION_KEYS = frozenset({
    "id", "name", "_scope_key", "_constructor_nodes", "definitions",
})
_V2_RECURSIVE_RECORD_KEYS = frozenset({
    "id", "uid", "class_type", "node_field", "input_shape", "output_shape",
    "native_input_names", "native_output_names", "native_input_types",
    "native_output_types", "native_input_optional", "native_input_asset_kinds",
    "native_output_slots",
})
_V2_RECURSIVE_SHAPE_KEYS = frozenset({
    "name", "type", "slot", "_has_link", "_has_value",
})
_V2_SCOPE_NODES_KEY = "nodes"
_V2_SCOPE_HELPERS_KEY = "helpers"
_V2_PRESENTATION_NODES_KEY = "nodes"
_V2_PRESENTATION_LINKS_KEY = "links"
_V2_PRESENTATION_GROUPS_KEY = "groups"
_V2_PRESENTATION_CANVAS_KEY = "canvas"


@dataclass(frozen=True, slots=True)
class _CompanionLoadContext:
    logical_python_path: Path
    companion: Mapping[str, Any]


_COMPANION_LOAD_CONTEXT: ContextVar[_CompanionLoadContext | None] = ContextVar(
    "vibecomfy_companion_load_context", default=None
)


def _closed_keys(value: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise WorkflowBundleError(f"{where} contains unknown field(s): {', '.join(unknown)}")


def _integer(value: Any, where: str, *, nonnegative: bool = False) -> int:
    if type(value) is not int or (nonnegative and value < 0):
        suffix = " non-negative" if nonnegative else ""
        raise WorkflowBundleError(f"{where} must be a{suffix} integer")
    return value


def _coerce_pair(value: Any) -> list[float] | None:
    """Return [x, y] from a 2+ numeric sequence; None if unusable.

    Loaded Comfy graphs sometimes carry size/pos with extra members. Taking
    the first two finite numbers lets capture proceed instead of aborting
    implement apply.
    """
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    a, b = value[0], value[1]
    if isinstance(a, bool) or isinstance(b, bool):
        return None
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    result = [float(a), float(b)]
    if any(not math.isfinite(x) for x in result):
        return None
    return result


def _pair(value: Any, where: str) -> list[float]:
    coerced = _coerce_pair(value)
    if coerced is None:
        raise WorkflowBundleError(f"{where} must contain exactly two numeric values")
    return coerced


def _rectangle(value: Any, where: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise WorkflowBundleError(f"{where} must contain x, y, width, and height")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)) for x in value):
        raise WorkflowBundleError(f"{where} must contain finite numeric values")
    return [float(x) for x in value]


def _semantic_edges(workflow: VibeWorkflow) -> set[tuple[str, str, int, str, int]]:
    """Derive sidecar foreign keys from Python-owned edges only."""
    by_id = {str(node_id): node for node_id, node in workflow.nodes.items()}
    by_uid = {str(node.uid): node for node in workflow.nodes.values() if node.uid}

    result: set[tuple[str, str, int, str, int]] = set()
    for edge in workflow.edges:
        source = by_id.get(str(edge.from_node)) or by_uid.get(str(edge.from_node))
        target = by_id.get(str(edge.to_node)) or by_uid.get(str(edge.to_node))
        if source is None or target is None:
            continue
        source_uid = str(source.uid or source.id)
        target_uid = str(target.uid or target.id)
        source_scope, source_local = parse_uid(source_uid)
        target_scope, target_local = parse_uid(target_uid)
        if source_scope != target_scope:
            raise WorkflowBundleError("ordinary cross-scope edge must be represented by a Python virtual wire")
        try:
            source_port = _port_index_for_node(
                source, edge.from_output, "output", "edge from_port", require_roster=True
            )
            target_port = _port_index_for_node(
                target, edge.to_input, "input", "edge to_port", require_roster=True
            )
        except WorkflowCompileError as exc:
            raise WorkflowBundleError(str(exc)) from exc
        result.add((source_scope, source_local, source_port, target_local, target_port))

    # Definitions are existing Python JSON-shaped semantics.  Derive their
    # structural scope through sg_key, never through ordinal UI indexes.
    from vibecomfy.identity.scope import compose_scope_path, sg_key
    from vibecomfy.ingest.normalize import canonical_definition_links, canonical_definition_nodes

    def definition_entries(raw: Any) -> list[Mapping[str, Any]]:
        if isinstance(raw, Mapping) and isinstance(raw.get("subgraphs"), (list, tuple)):
            return [x for x in raw["subgraphs"] if isinstance(x, Mapping)]
        if isinstance(raw, Mapping):
            return [x for x in raw.values() if isinstance(x, Mapping)]
        if isinstance(raw, (list, tuple)):
            return [x for x in raw if isinstance(x, Mapping)]
        return []

    def walk(definitions: Any, parent: tuple[str, ...]) -> None:
        for definition in definition_entries(definitions):
            key = sg_key(definition)
            scope = compose_scope_path((*parent, key))
            raw_nodes = canonical_definition_nodes(definition)
            entries = list(raw_nodes.values()) if isinstance(raw_nodes, Mapping) else list(raw_nodes) if isinstance(raw_nodes, (list, tuple)) else []
            by_local: dict[str, Mapping[str, Any]] = {}
            for node in entries:
                if not isinstance(node, Mapping): continue
                local = node.get("uid", node.get("id"))
                if local is not None:
                    by_local[str(local)] = node
                if node.get("id") is not None:
                    by_local[str(node["id"])] = node
            raw_links = canonical_definition_links(definition)
            link_values = raw_links.values() if isinstance(raw_links, Mapping) else raw_links if isinstance(raw_links, (list, tuple)) else []
            for link in link_values:
                if isinstance(link, Mapping):
                    from_id, from_port = link.get("from_uid", link.get("origin_id")), link.get("from_port", link.get("origin_slot"))
                    to_id, to_port = link.get("to_uid", link.get("target_id")), link.get("to_port", link.get("target_slot"))
                elif isinstance(link, (list, tuple)) and len(link) >= 5:
                    _, from_id, from_port, to_id, to_port = link[:5]
                else:
                    raise WorkflowBundleError(f"malformed definition edge in {scope!r}")
                if str(from_id) not in by_local or str(to_id) not in by_local:
                    raise WorkflowBundleError(f"definition edge endpoint {from_id!r}/{to_id!r} is not local to {scope!r}")
                from_uid = str(by_local[str(from_id)].get("uid", by_local[str(from_id)].get("id")))
                to_uid = str(by_local[str(to_id)].get("uid", by_local[str(to_id)].get("id")))
                result.add((scope, from_uid, _integer(from_port, "definition from_port", nonnegative=True), to_uid, _integer(to_port, "definition to_port", nonnegative=True)))
            walk(definition.get("definitions"), (*parent, key))

    walk(workflow.definitions or getattr(workflow, "metadata", {}).get("definitions", {}), ())
    return result


def _virtual_legs(workflow: VibeWorkflow) -> dict[tuple[str, str], tuple[tuple[str, str, int, str, int, int, int], ...]]:
    """Project shared resolved records into the legacy sidecar tuple shape."""
    from vibecomfy.workflow import _resolve_workflow_virtual_wire_records

    try:
        records = _resolve_workflow_virtual_wire_records(workflow)
    except WorkflowCompileError as exc:
        raise WorkflowBundleError(str(exc)) from exc
    return {
        key: tuple(
            (
                item.scope_path,
                item.from_node.split("#", 1)[-1],
                item.from_port,
                item.to_node.split("#", 1)[-1],
                item.to_port,
                item.leg_index,
                item.occurrence_index,
            )
            for item in legs
        )
        for key, legs in records.items()
    }


def _validate_annotations(
    value: Any,
    workflow: VibeWorkflow,
    *,
    valid_scopes: set[str] | None = None,
    valid_node_refs: set[tuple[str, str]] | None = None,
    valid_groups: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    from vibecomfy.porting.emit.emit_constants import UI_ONLY_CLASS_TYPES

    if not isinstance(value, list):
        raise WorkflowBundleError("workflow presentation annotations must be a list")
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(value):
        where = f"workflow presentation annotation {index}"
        if not isinstance(raw, Mapping):
            raise WorkflowBundleError(f"{where} must be an object")
        _closed_keys(raw, _ANNOTATION_KEYS, where)
        if set(raw) != _ANNOTATION_KEYS:
            raise WorkflowBundleError(f"{where} must contain exactly {_ANNOTATION_KEYS}")
        scope_path = raw.get("scope_path")
        annotation_id = raw.get("annotation_id")
        if not isinstance(scope_path, str) or any(
            part in {"sg0", "sg1"} for part in scope_path.split("/")
        ):
            raise WorkflowBundleError(f"{where}.scope_path is invalid")
        if valid_scopes is not None and scope_path not in valid_scopes:
            raise WorkflowBundleError(f"{where}.scope_path does not match a structural workflow scope")
        if not isinstance(annotation_id, str) or not annotation_id.strip():
            raise WorkflowBundleError(f"{where}.annotation_id must be nonblank")
        identity = (scope_path, annotation_id)
        if identity in seen:
            raise WorkflowBundleError(f"duplicate workflow presentation annotation {identity!r}")
        seen.add(identity)
        owner = raw.get("owner")
        if not isinstance(owner, Mapping):
            raise WorkflowBundleError(f"{where}.owner must be an object")
        _closed_keys(owner, _ANNOTATION_OWNER_KEYS, f"{where}.owner")
        if set(owner) != _ANNOTATION_OWNER_KEYS:
            raise WorkflowBundleError(f"{where}.owner must contain exactly kind and uid")
        if owner.get("kind") not in _ANNOTATION_OWNER_KINDS:
            raise WorkflowBundleError(f"{where}.owner.kind is unsupported")
        if not isinstance(owner.get("uid"), str) or not owner["uid"].strip():
            raise WorkflowBundleError(f"{where}.owner.uid must be nonblank")
        owner_uid = str(owner["uid"])
        kind = str(owner["kind"])
        if kind in {"node", "instance"}:
            # Captured note annotations may be the sole presentation record;
            # in that representation the annotation id is its self-owned
            # synthetic node key.  Still require the closed UI-only class.
            self_owned_note = (
                kind == "node"
                and owner_uid == str(annotation_id)
                and raw.get("class_type") in UI_ONLY_CLASS_TYPES
            )
            if not self_owned_note and (
                valid_node_refs is None or (scope_path, owner_uid) not in valid_node_refs
            ):
                raise WorkflowBundleError(f"{where}.owner does not identify a node in its scope")
        elif kind == "group":
            if valid_groups is None or (scope_path, owner_uid) not in valid_groups:
                raise WorkflowBundleError(f"{where}.owner does not identify a group in its scope")
        elif kind == "workflow":
            if scope_path != "" or owner_uid != workflow.id:
                raise WorkflowBundleError(f"{where}.owner does not identify this workflow")
        elif kind == "definition":
            if not scope_path or owner_uid != scope_path:
                raise WorkflowBundleError(f"{where}.owner does not identify its definition scope")
        if raw.get("class_type") not in UI_ONLY_CLASS_TYPES:
            raise WorkflowBundleError(f"{where}.class_type must be an allowlisted note class")
        for field in ("title", "content"):
            if not isinstance(raw.get(field), str):
                raise WorkflowBundleError(f"{where}.{field} must be a string")
        result.append(copy.deepcopy(dict(raw)))
    return result


def _validate_v1_sidecar(
    sidecar: Any,
    workflow: VibeWorkflow,
    *,
    allow_annotations: bool = False,
) -> dict[str, Any]:
    """Validate and canonically normalize one legacy presentation sidecar."""
    if not isinstance(sidecar, Mapping):
        raise WorkflowBundleError("workflow sidecar must contain a JSON object")
    try:
        projection = canonical_ir_projection(workflow)
    except (TypeError, ValueError, KeyError) as exc:
        raise WorkflowBundleError(f"Python semantic projection is invalid: {exc}") from exc
    allowed_keys = _SIDECAR_KEYS | ({"annotations"} if allow_annotations else set())
    _closed_keys(sidecar, frozenset(allowed_keys), "workflow sidecar")
    if set(sidecar) != _SIDECAR_KEYS and not (
        allow_annotations and set(sidecar) == _SIDECAR_KEYS | {"annotations"}
    ):
        raise WorkflowBundleError("workflow sidecar must contain exactly format_version, bind, nodes, links, groups, canvas")
    if type(sidecar["format_version"]) is not int or sidecar["format_version"] != 1:
        raise WorkflowBundleError("workflow sidecar format_version must be integer 1")
    bind = sidecar["bind"]
    if not isinstance(bind, Mapping):
        raise WorkflowBundleError("workflow sidecar bind must be a mapping")
    _closed_keys(bind, _BIND_KEYS, "workflow sidecar bind")
    if set(bind) != _BIND_KEYS:
        raise WorkflowBundleError(
            "workflow sidecar bind must contain workflow_identity and semantic_digest"
        )
    if bind["workflow_identity"] != workflow.id:
        raise WorkflowBundleError("workflow sidecar bind workflow_identity does not match workflow")
    # The sidecar is presentation custody bound to the workflow identity.
    # Emit/load normalization can change the Python semantic projection while
    # leaving a representable edit and its identity intact; that digest drift
    # is diagnostic evidence, not authority to reject the pair.  Structural
    # sidecar validation below still fail-closes on identities, nodes, links,
    # scopes, and native port rosters, so this does not bless a divergent graph.
    # Preserve the supplied digest unchanged as revision diagnostic evidence.
    from vibecomfy.porting.emit.ui import capture_presentation_graph_records

    presentation = capture_presentation_graph_records(sidecar)
    nodes = presentation.nodes
    if not isinstance(nodes, Mapping):
        raise WorkflowBundleError("workflow sidecar nodes must be a UID-keyed object")
    canonical_nodes: dict[str, Any] = {}
    native_node_ids: set[tuple[str, int]] = set()
    workflow_uids = {
        make_uid(str(item.get("scope_path", "")), str(item["uid"]))
        for item in projection.get("nodes", ())
        if isinstance(item, Mapping)
    }
    workflow_nodes_by_uid = {
        str(node.uid): node for node in workflow.nodes.values() if node.uid
    }
    for uid, entry in nodes.items():
        if not isinstance(uid, str) or not uid.strip():
            raise WorkflowBundleError("workflow sidecar node UID must be a nonblank string")
        if not isinstance(entry, Mapping):
            raise WorkflowBundleError(f"workflow sidecar node {uid!r} must be an object")
        _closed_keys(entry, _NODE_KEYS, f"workflow sidecar node {uid!r}")
        sidecar_class = entry.get("class_type")
        owner = workflow_nodes_by_uid.get(uid)
        if uid not in workflow_uids:
            # UI-only nodes are presentation custody, not executable graph
            # members.  Require their explicit class witness so an arbitrary
            # unknown node cannot be smuggled through this exception.
            from vibecomfy.porting.emit.emit_constants import UI_ONLY_CLASS_TYPES

            if not isinstance(sidecar_class, str) or sidecar_class not in UI_ONLY_CLASS_TYPES:
                raise WorkflowBundleError(f"workflow sidecar node {uid!r} does not match a Python node")
        elif sidecar_class is not None:
            if not isinstance(sidecar_class, str) or owner is None or sidecar_class != str(owner.class_type):
                raise WorkflowBundleError(f"workflow sidecar node {uid!r} class_type does not match Python authority")
        out = dict(entry)
        if "id" in out:
            native_id = _integer(out["id"], f"node {uid} id")
            node_scope, _ = parse_uid(uid)
            native_key = (node_scope, native_id)
            if native_key in native_node_ids: raise WorkflowBundleError(f"duplicate native node id {native_key!r}")
            native_node_ids.add(native_key)
        for field in ("pos", "size"):
            if field in out:
                coerced = _coerce_pair(out[field])
                if coerced is None:
                    out.pop(field, None)
                else:
                    out[field] = coerced
        if "collapsed" in out and type(out["collapsed"]) is not bool: raise WorkflowBundleError(f"node {uid} collapsed must be boolean")
        for field in ("color", "bgcolor", "title", "group"):
            if field in out and not isinstance(out[field], str): raise WorkflowBundleError(f"node {uid} {field} must be a string")
        if "z_order" in out: _integer(out["z_order"], f"node {uid} z_order")
        canonical_nodes[uid] = out
    expected = _semantic_edges(workflow)
    virtual = _virtual_legs(workflow)
    valid_scopes = {str(item["scope_path"]) for item in projection.get("nodes", ()) if isinstance(item, Mapping)}
    valid_scopes.update(
        str(item["scope_path"])
        for item in projection.get("definitions", ())
        if isinstance(item, Mapping) and isinstance(item.get("scope_path"), str)
    )
    raw_links = presentation.links
    if not isinstance(raw_links, list):
        raise WorkflowBundleError("workflow sidecar links must be a list")
    canonical_links: list[dict[str, Any]] = []
    seen_occ: dict[Any, list[int]] = {}
    native_ids: dict[tuple[str, int], Any] = {}
    for index, entry in enumerate(raw_links):
        if not isinstance(entry, Mapping): raise WorkflowBundleError(f"sidecar link {index} must be an object")
        _closed_keys(entry, _LINK_KEYS, f"sidecar link {index}")
        has_edge, has_virtual = "edge_ref" in entry, "virtual_wire_ref" in entry
        if has_edge == has_virtual: raise WorkflowBundleError(f"sidecar link {index} must contain exactly one semantic foreign key")
        ref = entry["edge_ref"] if has_edge else entry["virtual_wire_ref"]
        if not isinstance(ref, Mapping): raise WorkflowBundleError(f"sidecar link {index} reference must be an object")
        allowed = _EDGE_REF_KEYS if has_edge else _VIRTUAL_REF_KEYS
        _closed_keys(ref, allowed, f"sidecar link {index} reference")
        scope = ref.get("scope_path")
        if not isinstance(scope, str): raise WorkflowBundleError(f"sidecar link {index} scope_path must be a string")
        if scope not in valid_scopes or any(part in {"sg0", "sg1"} for part in scope.split("/")):
            raise WorkflowBundleError(f"sidecar link {index} scope_path is not a structural definition path")
        if has_edge:
            for field in ("from_uid", "to_uid"):
                try: validate_local_uid(ref[field], field=f"sidecar link {index} {field}")
                except (KeyError, ValueError) as exc: raise WorkflowBundleError(str(exc)) from exc
            from_port = _integer(ref.get("from_port"), f"sidecar link {index} from_port")
            to_port = _integer(ref.get("to_port"), f"sidecar link {index} to_port")
            if scope == "":
                source_node = workflow_nodes_by_uid.get(ref["from_uid"])
                target_node = workflow_nodes_by_uid.get(ref["to_uid"])
                for node, port_index, direction in (
                    (source_node, from_port, "output"),
                    (target_node, to_port, "input"),
                ):
                    try:
                        _port_index_for_node(
                            node,
                            port_index,
                            direction,
                            f"sidecar link {index}",
                            require_roster=True,
                            allow_numeric_string=False,
                        )
                    except WorkflowCompileError as exc:
                        raise WorkflowBundleError(str(exc)) from exc
            key = (scope, ref["from_uid"], from_port, ref["to_uid"], to_port)
            if key not in expected: raise WorkflowBundleError(f"sidecar link {index} edge_ref does not match a Python semantic edge")
        else:
            if not isinstance(ref.get("name"), str) or not ref["name"].strip(): raise WorkflowBundleError(f"sidecar link {index} virtual wire name must be nonblank")
            leg_index = _integer(ref.get("leg_index"), f"sidecar link {index} leg_index", nonnegative=True)
            legs = virtual.get((scope, ref["name"]))
            if legs is None or not any(leg[5] == leg_index for leg in legs):
                raise WorkflowBundleError(f"sidecar link {index} virtual_wire_ref does not match a Python materialized leg")
            key = (scope, ref["name"], leg_index)
        occurrence = _integer(entry.get("occurrence_index"), f"sidecar link {index} occurrence_index", nonnegative=True)
        if has_virtual:
            legs = virtual.get((scope, ref["name"]))
            if legs is None or not any(leg[5] == key[2] and leg[6] == occurrence for leg in legs):
                raise WorkflowBundleError(f"sidecar link {index} virtual_wire_ref does not match a Python materialized occurrence")
        seen_occ.setdefault(key, []).append(occurrence)
        if "id" in entry:
            native = _integer(entry["id"], f"sidecar link {index} id")
            native_key = (scope, native)
            if native_key in native_ids: raise WorkflowBundleError(f"duplicate or conflicting native link id {native_key!r}")
            native_ids[native_key] = key
        if "reroute" in entry:
            reroute = entry["reroute"]
            if not isinstance(reroute, list) or any(not isinstance(point, (list, tuple)) or len(point) != 2 for point in reroute):
                raise WorkflowBundleError(f"sidecar link {index} reroute must be a list of coordinate pairs")
            for point in reroute: _pair(point, f"sidecar link {index} reroute point")
        out = dict(entry); out["occurrence_index"] = occurrence
        canonical_links.append(out)
    for key, occurrences in seen_occ.items():
        if sorted(occurrences) != list(range(len(occurrences))): raise WorkflowBundleError(f"sidecar link occurrences for {key!r} must be contiguous from zero")
    def link_key(item: Mapping[str, Any]) -> Any:
        ref = item.get("edge_ref", item.get("virtual_wire_ref"))
        return (0, tuple(ref[k] for k in ("scope_path", "from_uid", "from_port", "to_uid", "to_port"))) if "edge_ref" in item else (1, tuple(ref[k] for k in ("scope_path", "name", "leg_index")), item["occurrence_index"])
    canonical_links.sort(key=lambda item: (*link_key(item), item["occurrence_index"]))
    groups = sidecar["groups"]
    if not isinstance(groups, list): raise WorkflowBundleError("workflow sidecar groups must be a list")
    canonical_groups: list[dict[str, Any]] = []
    group_ids: set[tuple[str, str]] = set()
    for index, group in enumerate(groups):
        if not isinstance(group, Mapping): raise WorkflowBundleError(f"sidecar group {index} must be an object")
        _closed_keys(group, _GROUP_KEYS, f"sidecar group {index}")
        if not isinstance(group.get("scope_path"), str) or any(part in {"sg0", "sg1"} for part in str(group.get("scope_path", "")).split("/")):
            raise WorkflowBundleError(f"sidecar group {index} has invalid structural scope path")
        if str(group.get("scope_path")) not in valid_scopes:
            raise WorkflowBundleError(f"sidecar group {index} scope path does not match Python definitions")
        if not isinstance(group.get("presentation_id"), str) or not group["presentation_id"]: raise WorkflowBundleError(f"sidecar group {index} has invalid identity")
        group_key = (group["scope_path"], group["presentation_id"])
        if group_key in group_ids:
            raise WorkflowBundleError(f"duplicate scoped group presentation id {group_key!r}")
        group_ids.add(group_key)
        if "bounds" in group: _rectangle(group["bounds"], f"sidecar group {index} bounds")
        for field in ("title", "color"):
            if field in group and not isinstance(group[field], str): raise WorkflowBundleError(f"sidecar group {index} {field} must be a string")
        if "z_order" in group: _integer(group["z_order"], f"sidecar group {index} z_order")
        normalized_group = dict(group)
        if "bounds" in normalized_group:
            normalized_group["bounds"] = _rectangle(normalized_group["bounds"], f"sidecar group {index} bounds")
        canonical_groups.append(normalized_group)
    group_keys = {(str(item["scope_path"]), str(item["presentation_id"])) for item in canonical_groups}
    for uid, entry in canonical_nodes.items():
        if "group" not in entry:
            continue
        scope, _ = parse_uid(uid)
        if (scope, str(entry["group"])) not in group_keys:
            raise WorkflowBundleError(f"sidecar node {uid!r} references unknown group presentation id")
    canonical_groups.sort(key=lambda item: (item["scope_path"], item["presentation_id"]))
    canvas = sidecar["canvas"]
    if not isinstance(canvas, Mapping): raise WorkflowBundleError("workflow sidecar canvas must be an object")
    _closed_keys(canvas, _CANVAS_KEYS, "workflow sidecar canvas")
    if "zoom" in canvas and (isinstance(canvas["zoom"], bool) or not isinstance(canvas["zoom"], (int, float)) or not math.isfinite(float(canvas["zoom"]))): raise WorkflowBundleError("sidecar canvas zoom must be finite numeric")
    if "pan" in canvas: _pair(canvas["pan"], "sidecar canvas pan")
    result = {
        "format_version": 1,
        "bind": dict(bind),
        "nodes": canonical_nodes,
        "links": canonical_links,
        "groups": canonical_groups,
        "canvas": dict(canvas),
    }
    if allow_annotations:
        annotations = _validate_annotations(sidecar.get("annotations", []), workflow)
        for index, annotation in enumerate(annotations):
            owner = annotation["owner"]
            if owner["kind"] == "node" and owner["uid"] not in canonical_nodes:
                raise WorkflowBundleError(
                    f"workflow presentation annotation {index} references an unknown node"
                )
        result["annotations"] = annotations
    return result


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkflowBundleError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_json_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                WorkflowBundleError(f"{label} contains non-finite number {value}")
            ),
        )
    except WorkflowBundleError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowBundleError(f"could not read {label} {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkflowBundleError(f"{label} must contain a JSON object")
    return raw


def _validate_v2_marker(marker: Any) -> dict[str, Any]:
    if not isinstance(marker, Mapping):
        raise WorkflowBundleError("READY_METADATA source_bundle must be an object")
    _closed_keys(marker, _V2_MARKER_KEYS, "READY_METADATA source_bundle")
    if set(marker) != _V2_MARKER_KEYS or marker.get("format_version") != 2:
        raise WorkflowBundleError(
            "READY_METADATA source_bundle must contain format_version 2, generation_id, and custody_digest"
        )
    for field in ("generation_id", "custody_digest"):
        value = marker.get(field)
        if not isinstance(value, str) or not value.strip():
            raise WorkflowBundleError(f"READY_METADATA source_bundle {field} must be nonblank")
    return dict(marker)


def _validate_native_ports(value: Any, where: str) -> dict[str, Any]:
    allowed = frozenset({
        "native_input_names", "native_output_names", "native_input_types",
        "native_output_types", "native_input_optional", "native_input_asset_kinds",
        "native_output_slots",
    })
    if not isinstance(value, Mapping):
        raise WorkflowBundleError(f"{where} must be an object")
    _closed_keys(value, allowed, where)
    result = copy.deepcopy(dict(value))
    for key, items in result.items():
        if items is not None and not isinstance(items, list):
            raise WorkflowBundleError(f"{where}.{key} must be a list or null")
    for key in ("native_input_names", "native_output_names"):
        names = result.get(key)
        if names is not None and any(
            item is not None and (type(item) is not str or not item.strip())
            for item in names
        ):
            raise WorkflowBundleError(f"{where}.{key} must contain nonblank strings or null")
    for key in ("native_input_types", "native_output_types", "native_input_asset_kinds"):
        items = result.get(key)
        if items is not None and any(item is not None and type(item) is not str for item in items):
            raise WorkflowBundleError(f"{where}.{key} must contain strings or null")
    optional = result.get("native_input_optional")
    if optional is not None and any(type(item) is not bool for item in optional):
        raise WorkflowBundleError(f"{where}.native_input_optional must contain booleans")
    input_names = result.get("native_input_names")
    if isinstance(input_names, list):
        for key in ("native_input_types", "native_input_optional", "native_input_asset_kinds"):
            items = result.get(key)
            if items is not None and len(items) != len(input_names):
                raise WorkflowBundleError(f"{where}.{key} length must match native_input_names")
    output_names = result.get("native_output_names")
    if isinstance(output_names, list):
        for key in ("native_output_types",):
            items = result.get(key)
            if items is not None and len(items) != len(output_names):
                raise WorkflowBundleError(f"{where}.{key} length must match native_output_names")
    slots = result.get("native_output_slots")
    if isinstance(slots, list):
        if any(type(item) is not int or item < 0 for item in slots):
            raise WorkflowBundleError(f"{where}.native_output_slots must contain non-negative integers")
        if len(set(slots)) != len(slots):
            raise WorkflowBundleError(f"{where}.native_output_slots must be unique")
    return result


_GENERATED_PROVENANCE_KEYS = frozenset({
    "source_path", "source_id", "source_type", "source_workflow_path", "source_ref",
    "source_kind", "indexed_id", "workflow_source_id", "workflow_source_type",
    "raw_workflow_shape", "source_hash", "workflow_shape", "output_mode",
})
_GENERATED_SHAPE_KEYS = frozenset({
    "nodes", "runtime_nodes", "helper_nodes", "edges", "inputs", "outputs",
})


def _validate_generated_provenance(value: Any, where: str) -> Any:
    """Accept only the scalar/closed provenance witness, never graph payloads."""
    if isinstance(value, str):
        if not value.strip():
            raise WorkflowBundleError(f"{where} must be nonblank")
        return value
    if not isinstance(value, Mapping):
        raise WorkflowBundleError(f"{where} must be a scalar tag or closed object")
    _closed_keys(value, _GENERATED_PROVENANCE_KEYS, where)
    for key, item in value.items():
        if key == "workflow_shape":
            if not isinstance(item, Mapping):
                raise WorkflowBundleError(f"{where}.workflow_shape must be an object")
            _closed_keys(item, _GENERATED_SHAPE_KEYS, f"{where}.workflow_shape")
            if any(type(nested) is not int or nested < 0 for nested in item.values()):
                raise WorkflowBundleError(f"{where}.workflow_shape must contain non-negative integers")
        elif isinstance(item, (Mapping, list, tuple)):
            raise WorkflowBundleError(f"{where}.{key} must be scalar-valued")
    return copy.deepcopy(dict(value))


def _validate_v2_custody(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowBundleError("workflow companion custody must be an object")
    _closed_keys(value, _V2_CUSTODY_KEYS, "workflow companion custody")
    if "scopes" not in value or not isinstance(value.get("scopes"), list):
        raise WorkflowBundleError("workflow companion custody must contain a scopes list")
    scopes: list[dict[str, Any]] = []
    seen_scopes: set[str] = set()
    for scope_index, raw_scope in enumerate(value["scopes"]):
        where = f"workflow companion custody scope {scope_index}"
        if not isinstance(raw_scope, Mapping):
            raise WorkflowBundleError(f"{where} must be an object")
        _closed_keys(raw_scope, _V2_SCOPE_KEYS, where)
        if set(raw_scope) != _V2_SCOPE_KEYS:
            raise WorkflowBundleError(f"{where} must contain scope_path, nodes, and helpers")
        scope_path = raw_scope.get("scope_path")
        if not isinstance(scope_path, str) or any(part in {"sg0", "sg1"} for part in scope_path.split("/")):
            raise WorkflowBundleError(f"{where}.scope_path is invalid")
        if scope_path in seen_scopes:
            raise WorkflowBundleError(f"duplicate workflow companion custody scope {scope_path!r}")
        seen_scopes.add(scope_path)
        raw_nodes = raw_scope.get(_V2_SCOPE_NODES_KEY)
        raw_helpers = raw_scope.get(_V2_SCOPE_HELPERS_KEY)
        if not isinstance(raw_nodes, list) or not isinstance(raw_helpers, list):
            raise WorkflowBundleError(f"{where} nodes and helpers must be lists")
        nodes: list[dict[str, Any]] = []
        labels: set[str] = set()
        ids: set[str] = set()
        uids: set[str] = set()
        for node_index, raw_node in enumerate(raw_nodes):
            node_where = f"{where} node {node_index}"
            if not isinstance(raw_node, Mapping):
                raise WorkflowBundleError(f"{node_where} must be an object")
            _closed_keys(raw_node, _V2_NODE_KEYS, node_where)
            required = {"label", "id", "uid", "class_type"}
            if not required.issubset(raw_node):
                raise WorkflowBundleError(f"{node_where} is missing a required identity field")
            node = copy.deepcopy(dict(raw_node))
            for field in required:
                if not isinstance(node[field], str) or not node[field].strip():
                    raise WorkflowBundleError(f"{node_where}.{field} must be nonblank")
            for field, seen in (("label", labels), ("id", ids), ("uid", uids)):
                if node[field] in seen:
                    raise WorkflowBundleError(f"duplicate {field} {node[field]!r} in scope {scope_path!r}")
                seen.add(node[field])
            if "native_ports" in node:
                node["native_ports"] = _validate_native_ports(
                    node["native_ports"], f"{node_where}.native_ports"
                )
            for field in ("metadata", "widget_channels", "output_slot_names"):
                if field in node and not isinstance(node[field], Mapping):
                    raise WorkflowBundleError(f"{node_where}.{field} must be an object")
            if "widget_channels" in node and any(
                type(key) is not str or type(item) is not str
                for key, item in node["widget_channels"].items()
            ):
                raise WorkflowBundleError(f"{node_where}.widget_channels must map strings to strings")
            if "output_slot_names" in node and any(
                type(key) is not str or not key.isdecimal() or type(item) is not str
                for key, item in node["output_slot_names"].items()
            ):
                raise WorkflowBundleError(f"{node_where}.output_slot_names has malformed entries")
            if "metadata" in node:
                metadata = node["metadata"]
                metadata_allowed = frozenset({
                    "semantic", "semantic_metadata", "schema_source", "unresolved",
                    "reconciliation", "diagnostics", "provenance", "input_names",
                    "output_names", "input_types", "output_types", "keep_defaults",
                })
                _closed_keys(metadata, metadata_allowed, f"{node_where}.metadata")
                for key, item in metadata.items():
                    if key == "schema_source":
                        if not isinstance(item, Mapping):
                            raise WorkflowBundleError(f"{node_where}.metadata.schema_source must be an object")
                        _closed_keys(item, frozenset({
                            "provider", "path", "cache_path", "server_url", "package",
                            "version", "hash", "confidence",
                        }), f"{node_where}.metadata.schema_source")
                        if any(isinstance(nested, (Mapping, list, tuple)) for nested in item.values()):
                            raise WorkflowBundleError(f"{node_where}.metadata.schema_source must be scalar-valued")
                    elif key == "provenance":
                        _validate_generated_provenance(
                            item, f"{node_where}.metadata.provenance"
                        )
                    elif isinstance(item, Mapping):
                        raise WorkflowBundleError(
                            f"{node_where}.metadata.{key} cannot contain nested objects"
                        )
                    elif isinstance(item, list) and any(isinstance(nested, (Mapping, list, tuple)) for nested in item):
                        raise WorkflowBundleError(
                            f"{node_where}.metadata.{key} must be a scalar list"
                        )
            for field in ("none_input_fields", "none_widget_fields", "construction_output_names"):
                if field in node and (
                    not isinstance(node[field], list)
                    or not all(isinstance(item, str) for item in node[field])
                ):
                    raise WorkflowBundleError(f"{node_where}.{field} must be a string list")
            canonical_digest(node)
            nodes.append(node)
        helpers: list[dict[str, Any]] = []
        helper_ids: set[str] = set()
        helper_uids: set[str] = set()
        for helper_index, raw_helper in enumerate(raw_helpers):
            helper_where = f"{where} helper {helper_index}"
            if not isinstance(raw_helper, Mapping):
                raise WorkflowBundleError(f"{helper_where} must be an object")
            _closed_keys(raw_helper, _V2_HELPER_KEYS, helper_where)
            helper = copy.deepcopy(dict(raw_helper))
            for field in ("id", "uid", "class_type"):
                if not isinstance(helper.get(field), str) or not helper[field].strip():
                    raise WorkflowBundleError(f"{helper_where}.{field} must be nonblank")
            if helper["id"] in helper_ids or helper["uid"] in helper_uids:
                raise WorkflowBundleError(f"duplicate helper identity in scope {scope_path!r}")
            helper_ids.add(helper["id"])
            helper_uids.add(helper["uid"])
            if "native_ports" in helper:
                helper["native_ports"] = _validate_native_ports(
                    helper["native_ports"], f"{helper_where}.native_ports"
                )
            if "provenance" in helper:
                helper["provenance"] = _validate_generated_provenance(
                    helper["provenance"], f"{helper_where}.provenance"
                )
            for field in ("pos", "size"):
                if field in helper:
                    helper[field] = _pair(helper[field], f"{helper_where}.{field}")
            canonical_digest(helper)
            helpers.append(helper)
        scopes.append({"scope_path": scope_path, "nodes": nodes, "helpers": helpers})
    if "" not in seen_scopes:
        raise WorkflowBundleError("workflow companion custody must contain the root scope")
    result: dict[str, Any] = {"scopes": scopes}
    if "definitions" in value:
        definitions = value["definitions"]
        if not isinstance(definitions, Mapping) or set(definitions) != {"subgraphs"}:
            raise WorkflowBundleError(
                "workflow companion recursive custody must contain only subgraphs"
            )

        def validate_shape(value: Any, where: str) -> list[dict[str, Any]] | None:
            if value is None:
                return None
            if not isinstance(value, list):
                raise WorkflowBundleError(f"{where} must be a list or null")
            result: list[dict[str, Any]] = []
            for index, raw_shape in enumerate(value):
                shape_where = f"{where}[{index}]"
                if not isinstance(raw_shape, Mapping):
                    raise WorkflowBundleError(f"{shape_where} must be an object")
                _closed_keys(raw_shape, _V2_RECURSIVE_SHAPE_KEYS, shape_where)
                if "name" not in raw_shape or not isinstance(raw_shape["name"], str) or not raw_shape["name"].strip():
                    raise WorkflowBundleError(f"{shape_where}.name must be nonblank")
                if "type" in raw_shape and raw_shape["type"] is not None and not isinstance(raw_shape["type"], str):
                    raise WorkflowBundleError(f"{shape_where}.type must be a string or null")
                if "slot" in raw_shape and (
                    type(raw_shape["slot"]) is not int or raw_shape["slot"] < 0
                ):
                    raise WorkflowBundleError(f"{shape_where}.slot must be a non-negative integer")
                for field in ("_has_link", "_has_value"):
                    if field in raw_shape and type(raw_shape[field]) is not bool:
                        raise WorkflowBundleError(f"{shape_where}.{field} must be boolean")
                result.append(copy.deepcopy(dict(raw_shape)))
            return result

        def validate_record(record: Any, where: str) -> dict[str, Any]:
            if not isinstance(record, Mapping):
                raise WorkflowBundleError(f"{where} must be an object")
            _closed_keys(record, _V2_RECURSIVE_RECORD_KEYS, where)
            required = {"id", "uid", "class_type", "node_field", "input_shape", "output_shape"}
            if set(record) & required != required:
                raise WorkflowBundleError(f"{where} is missing a required constructor field")
            for field in ("id", "class_type", "node_field"):
                if not isinstance(record[field], str) or not record[field].strip():
                    raise WorkflowBundleError(f"{where}.{field} must be nonblank")
            if record["node_field"] not in {"type", "class_type"}:
                raise WorkflowBundleError(f"{where}.node_field is invalid")
            if record["uid"] is not None and (not isinstance(record["uid"], str) or not record["uid"].strip()):
                raise WorkflowBundleError(f"{where}.uid must be nonblank or null")
            normalized = copy.deepcopy(dict(record))
            normalized["input_shape"] = validate_shape(record["input_shape"], f"{where}.input_shape")
            normalized["output_shape"] = validate_shape(record["output_shape"], f"{where}.output_shape")
            native_fields = {
                field: copy.deepcopy(record[field])
                for field in _V2_RECURSIVE_RECORD_KEYS
                if field.startswith("native_") and field in record
            }
            if native_fields:
                normalized_native = _validate_native_ports(native_fields, f"{where}.native_ports")
                for field, item in normalized_native.items():
                    normalized[field] = item
            return normalized

        def validate_recursive(value: Any, where: str) -> None:
            entries = value.get("subgraphs") if isinstance(value, Mapping) else None
            if not isinstance(entries, list):
                raise WorkflowBundleError(f"{where}.subgraphs must be a list")
            for index, definition in enumerate(entries):
                item_where = f"{where}.subgraphs[{index}]"
                if not isinstance(definition, Mapping):
                    raise WorkflowBundleError(f"{item_where} must be an object")
                _closed_keys(definition, _V2_RECURSIVE_DEFINITION_KEYS, item_where)
                for key in ("_scope_key", "_constructor_nodes"):
                    if key not in definition:
                        raise WorkflowBundleError(f"{item_where} is missing {key}")
                if (
                    not isinstance(definition["_scope_key"], str)
                    or not definition["_scope_key"].strip()
                    or "/" in definition["_scope_key"]
                ):
                    raise WorkflowBundleError(f"{item_where}._scope_key must be nonblank")
                for key in ("id", "name"):
                    if key in definition and (
                        not isinstance(definition[key], str) or not definition[key].strip()
                    ):
                        raise WorkflowBundleError(f"{item_where}.{key} must be nonblank")
                records = definition["_constructor_nodes"]
                if not isinstance(records, list):
                    raise WorkflowBundleError(f"{item_where}._constructor_nodes must be a list")
                for record_index, record in enumerate(records):
                    record_where = f"{item_where}._constructor_nodes[{record_index}]"
                    validate_record(record, record_where)
                nested = definition.get("definitions")
                if nested is not None:
                    if not isinstance(nested, Mapping) or set(nested) != {"subgraphs"}:
                        raise WorkflowBundleError(
                            f"{item_where}.definitions must contain only subgraphs"
                        )
                    validate_recursive(nested, f"{item_where}.definitions")

        validate_recursive(definitions, "workflow companion custody.definitions")
        from vibecomfy.identity.scope import compose_scope_path

        structural_scopes: set[str] = set()

        def collect_scope_paths(value: Any, parents: tuple[str, ...]) -> None:
            entries = value.get("subgraphs") if isinstance(value, Mapping) else None
            if not isinstance(entries, list):
                return
            for definition in entries:
                if not isinstance(definition, Mapping):
                    continue
                key = str(definition["_scope_key"])
                scope_path = compose_scope_path((*parents, key))
                structural_scopes.add(scope_path)
                collect_scope_paths(definition.get("definitions"), (*parents, key))

        collect_scope_paths(definitions, ())
        observed_scopes = seen_scopes - {""}
        if observed_scopes != structural_scopes:
            missing = sorted(structural_scopes - observed_scopes)
            extra = sorted(observed_scopes - structural_scopes)
            detail = f"missing={missing!r}" if missing else f"extra={extra!r}"
            raise WorkflowBundleError(
                f"workflow companion recursive custody scopes do not match definitions ({detail})"
            )
        result["definitions"] = copy.deepcopy(dict(definitions))
    return result


def _validate_v2_sidecar(
    sidecar: Any,
    workflow: VibeWorkflow,
    *,
    marker: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(sidecar, Mapping):
        raise WorkflowBundleError("workflow companion must contain a JSON object")
    _closed_keys(sidecar, _V2_KEYS, "workflow companion")
    if set(sidecar) != _V2_KEYS or sidecar.get("format_version") != 2:
        raise WorkflowBundleError(
            "workflow companion v2 must contain exactly format_version, bind, custody, and presentation"
        )
    bind = sidecar.get("bind")
    if not isinstance(bind, Mapping):
        raise WorkflowBundleError("workflow companion bind must be an object")
    _closed_keys(bind, _V2_BIND_KEYS, "workflow companion bind")
    if set(bind) != _V2_BIND_KEYS:
        raise WorkflowBundleError("workflow companion bind is incomplete")
    if bind.get("workflow_identity") != workflow.id:
        raise WorkflowBundleError("workflow companion identity does not match Python authority")
    for field in ("generation_id", "custody_digest"):
        if not isinstance(bind.get(field), str) or not bind[field].strip():
            raise WorkflowBundleError(f"workflow companion bind {field} must be nonblank")
    custody = _validate_v2_custody(sidecar.get("custody"))
    if canonical_digest(custody) != bind["custody_digest"]:
        raise WorkflowBundleError("workflow companion custody digest does not match custody")
    if marker is not None:
        checked_marker = _validate_v2_marker(marker)
        if checked_marker["generation_id"] != bind["generation_id"]:
            raise WorkflowBundleError("workflow companion generation does not match Python")
        if checked_marker["custody_digest"] != bind["custody_digest"]:
            raise WorkflowBundleError("workflow companion custody digest does not match Python")
    presentation = sidecar.get("presentation")
    if not isinstance(presentation, Mapping) or set(presentation) != _V2_PRESENTATION_KEYS:
        raise WorkflowBundleError(
            "workflow companion presentation must contain exactly nodes, links, groups, canvas, and annotations"
        )
    presentation_nodes = presentation.get(_V2_PRESENTATION_NODES_KEY)
    presentation_groups = presentation.get(_V2_PRESENTATION_GROUPS_KEY)
    projection = canonical_ir_projection(workflow)
    valid_scopes = {
        str(item["scope_path"])
        for item in [*(projection.get("nodes", ()) or ()), *(projection.get("definitions", ()) or ())]
        if isinstance(item, Mapping) and isinstance(item.get("scope_path"), str)
    }
    valid_scopes.add("")
    valid_node_refs: set[tuple[str, str]] = {
        (str(item["scope_path"]), str(item["uid"]))
        for item in projection.get("nodes", ())
        if isinstance(item, Mapping)
        and isinstance(item.get("scope_path"), str)
        and isinstance(item.get("uid"), str)
    }
    if isinstance(presentation_nodes, Mapping):
        from vibecomfy.identity.uid import parse_uid

        for uid in presentation_nodes:
            if isinstance(uid, str):
                valid_node_refs.add(parse_uid(uid))
    valid_groups = {
        (str(group.get("scope_path")), str(group.get("presentation_id")))
        for group in presentation_groups if isinstance(group, Mapping)
    } if isinstance(presentation_groups, list) else set()
    annotations = _validate_annotations(
        presentation.get("annotations"), workflow,
        valid_scopes=valid_scopes,
        valid_node_refs=valid_node_refs,
        valid_groups=valid_groups,
    )
    # v2 materialization has one supported annotation form: a UI-only node
    # owned by itself in the presentation map.  Keep this stricter than the
    # legacy annotation adapter so an annotation cannot name a different
    # owner or disappear during canonical export.
    for index, annotation in enumerate(annotations):
        where = f"workflow presentation annotation {index}"
        owner = annotation["owner"]
        if owner["kind"] != "node" or annotation["annotation_id"] != owner["uid"]:
            raise WorkflowBundleError(f"{where} must be a self-owned node annotation")
        entry = presentation_nodes.get(owner["uid"]) if isinstance(presentation_nodes, Mapping) else None
        if not isinstance(entry, Mapping) or entry.get("class_type") != annotation["class_type"]:
            raise WorkflowBundleError(f"{where} does not match a presentation node")
    # API-only captures have no canvas furniture to validate.  Their empty
    # presentation is intentional; requiring UI foreign keys here would turn
    # a semantic-only graph (which may still contain executable edges) into a
    # false malformed-sidecar refusal.
    if (
        presentation[_V2_PRESENTATION_NODES_KEY] == {}
        and presentation[_V2_PRESENTATION_LINKS_KEY] == []
        and presentation[_V2_PRESENTATION_GROUPS_KEY] == []
        and presentation[_V2_PRESENTATION_CANVAS_KEY] == {}
    ):
        validated_presentation = {
            "nodes": {},
            "links": [],
            "groups": [],
            "canvas": {},
        }
    else:
        validated_presentation = _validate_v1_sidecar(
            {
                "format_version": 1,
                "bind": {
                    "workflow_identity": workflow.id,
                    "semantic_digest": workflow.semantic_digest(),
                },
                **{
                    key: value
                    for key, value in presentation.items()
                    if key != "annotations"
                },
            },
            workflow,
        )
    return {
        "format_version": 2,
        "bind": dict(bind),
        "custody": custody,
        "presentation": {
            key: validated_presentation[key]
            for key in ("nodes", "links", "groups", "canvas")
        } | {"annotations": annotations},
    }


def validate_sidecar(sidecar: Any, workflow: VibeWorkflow) -> dict[str, Any]:
    """Validate and canonically normalize a v1 presentation or v2 companion."""
    if isinstance(sidecar, Mapping) and sidecar.get("format_version") == 2:
        marker = None
        metadata = getattr(workflow, "metadata", {})
        if isinstance(metadata, Mapping):
            marker = metadata.get("source_bundle")
        return _validate_v2_sidecar(sidecar, workflow, marker=marker)
    return _validate_v1_sidecar(
        sidecar,
        workflow,
        allow_annotations=isinstance(sidecar, Mapping) and "annotations" in sidecar,
    )


@contextmanager
def _staged_companion_context(
    logical_python_path: Path,
    companion: Mapping[str, Any],
):
    token = _COMPANION_LOAD_CONTEXT.set(
        _CompanionLoadContext(logical_python_path.resolve(), copy.deepcopy(dict(companion)))
    )
    try:
        yield
    finally:
        _COMPANION_LOAD_CONTEXT.reset(token)


def _v2_companion_for_build(
    metadata: Mapping[str, Any],
    source_path: str | Path | None,
) -> dict[str, Any] | None:
    """Load and validate marked custody before the first workflow constructor."""
    marker_value = metadata.get("source_bundle")
    if marker_value is None:
        return None
    marker = _validate_v2_marker(marker_value)
    if source_path is None:
        raise WorkflowBundleError("v2 workflow source has no path for its required companion")
    logical_path = Path(source_path).resolve()
    context = _COMPANION_LOAD_CONTEXT.get()
    if context is not None:
        if context.logical_python_path != logical_path:
            raise WorkflowBundleError("staged companion context does not match logical Python path")
        sidecar = copy.deepcopy(dict(context.companion))
    else:
        candidate = _sidecar_path(logical_path)
        if not candidate.is_file():
            raise WorkflowBundleError(f"v2 workflow companion is missing: {candidate}")
        sidecar = _read_json_object(candidate, label="workflow companion")
    if sidecar.get("format_version") != 2:
        raise WorkflowBundleError("marked v2 Python requires a format_version 2 companion")
    bind = sidecar.get("bind")
    if not isinstance(bind, Mapping):
        raise WorkflowBundleError("workflow companion bind must be an object")
    if bind.get("workflow_identity") != (
        metadata.get("ready_template") or metadata.get("workflow_template")
    ):
        raise WorkflowBundleError("workflow companion identity does not match READY_METADATA")
    custody = _validate_v2_custody(sidecar.get("custody"))
    if canonical_digest(custody) != marker["custody_digest"] or bind.get("custody_digest") != marker["custody_digest"]:
        raise WorkflowBundleError("workflow companion custody digest mismatch")
    if bind.get("generation_id") != marker["generation_id"]:
        raise WorkflowBundleError("workflow companion generation mismatch")
    return {
        "format_version": 2,
        "bind": dict(bind),
        "custody": custody,
        "presentation": copy.deepcopy(sidecar.get("presentation")),
    }


def _identity_declarations(value: Any, *, container: str = "") -> list[tuple[str, Any]]:
    """Find repeated identity declarations in source-shaped mappings.

    Native node/API dictionaries have many unrelated ``id`` fields, so plain
    ``id`` is intentionally considered only inside an explicitly named
    source/bind/registry/import/capture container.
    """
    found: list[tuple[str, Any]] = []
    if not isinstance(value, Mapping):
        return found
    for key, item in value.items():
        name = str(key)
        lowered = name.casefold()
        if lowered in _IDENTITY_KEYS:
            found.append((f"{container}.{name}" if container else name, item))
        elif lowered == "id" and container.casefold().rsplit(".", 1)[-1] in _CONTAINER_ID_KEYS:
            found.append((f"{container}.{name}", item))
        if isinstance(item, Mapping):
            next_container = name if lowered in _CONTAINER_ID_KEYS else container
            found.extend(_identity_declarations(item, container=next_container))
    return found


def _check_identity(workflow: VibeWorkflow, *declarations: Any) -> None:
    """Validate all known repeated identities before any digest/materialization."""
    report = workflow.validate_identity()
    if not report.ok:
        raise WorkflowBundleError(report.issues[0].message)

    values: list[tuple[str, Any]] = []
    values.extend(_identity_declarations(getattr(workflow, "metadata", {}), container="metadata"))
    values.extend(_identity_declarations(getattr(workflow.source, "provenance", {}), container="source.provenance"))
    for declaration in declarations:
        values.extend(_identity_declarations(declaration))
    for label, value in values:
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise WorkflowBundleError(f"{label} must be a nonblank workflow identity")
        if value != workflow.id:
            raise WorkflowBundleError(
                f"workflow identity mismatch: {label} {value!r} must equal {workflow.id!r}"
            )


def _first(mapping: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _source_provenance(provenance: Any) -> Any:
    """Return stable provenance suitable for regenerated Python source.

    Derived revision chains stay out of generated Python so a load/save cycle
    does not grow history. Preserve only the explicit parent witness required
    to reload this exact successor revision; it is stable provenance and does
    not name the current bundle as its own parent.
    """
    if not isinstance(provenance, Mapping):
        return provenance
    result = dict(provenance)
    evidence = result.pop("revision_evidence", None)
    parent_revision = result.get("parent_revision")
    if isinstance(parent_revision, str) and parent_revision:
        if isinstance(evidence, Mapping):
            candidates = list(evidence.values())
        elif isinstance(evidence, (list, tuple)):
            candidates = list(evidence)
        else:
            candidates = []
        parent_records = [
            dict(item) for item in candidates
            if isinstance(item, Mapping) and item.get("revision_id") == parent_revision
        ]
        if parent_records:
            result["revision_evidence"] = [parent_records[-1]]
    if result.get("parent_revision") == "":
        result.pop("parent_revision")
    return result


def filter_provenance(
    provenance: Any,
    *,
    default_operation: str,
) -> dict[str, Any]:
    """Return the closed, deterministic provenance object used by revisions.

    Operational timestamps, local paths, process/session identifiers and
    unknown extension keys are deliberately omitted.  An unsupported
    operation is an error, rather than a new implicit authority.
    """
    if not isinstance(default_operation, str) or default_operation not in _OPERATIONS:
        raise WorkflowBundleError(f"unsupported bundle operation {default_operation!r}")
    if provenance is None:
        raw: Mapping[str, Any] = {}
    elif isinstance(provenance, Mapping):
        raw = provenance
    elif isinstance(provenance, str) and provenance in {
        "user_confirmed",
        "agent_authored",
        "agent_generated",
        "untrusted_source",
    }:
        # Existing loader provenance tags are trust tags, not bundle metadata.
        # Keep the operation closed and avoid making the tag a revision input.
        raw = {}
    else:
        raise WorkflowBundleError(
            f"unsupported provenance value {type(provenance).__name__}; expected a mapping"
        )

    operation = _first(raw, "operation", "operation_kind", "kind")
    if operation is None:
        operation = default_operation
    if not isinstance(operation, str) or operation not in _OPERATIONS:
        raise WorkflowBundleError(f"unsupported provenance operation {operation!r}")

    result: dict[str, Any] = {"operation": operation}
    artifact_class = raw.get("artifact_class")
    if artifact_class is not None:
        if artifact_class not in {"open_draft", "execution_ready_candidate"}:
            raise WorkflowBundleError(f"unsupported provenance artifact_class {artifact_class!r}")
        result["artifact_class"] = artifact_class
    execution_ready = raw.get("execution_ready")
    if execution_ready is not None:
        if type(execution_ready) is not bool:
            raise WorkflowBundleError("provenance execution_ready must be a boolean")
        result["execution_ready"] = execution_ready
    origin = raw.get("origin")
    if isinstance(origin, Mapping):
        origin_kind = _first(origin, "kind", "origin_kind")
        origin_uri = _first(origin, "uri", "origin_uri")
    else:
        origin_kind = _first(raw, "origin_kind")
        origin_uri = _first(raw, "origin_uri", "uri")
    for key, value in (("origin_kind", origin_kind), ("origin_uri", origin_uri)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise WorkflowBundleError(f"provenance {key} must be a nonblank string")
            result[key] = value

    pin = _first(raw, "origin_pin", "immutable_origin_pin", "pin")
    source_digest = _first(raw, "source_digest", "origin_digest")
    for key, value in (("origin_pin", pin), ("source_digest", source_digest)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise WorkflowBundleError(f"provenance {key} must be a nonblank string")
            result[key] = value

    author = _first(raw, "author_id", "author")
    producer = _first(raw, "producer_id", "producer")
    for key, value in (("author_id", author), ("producer_id", producer)):
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise WorkflowBundleError(f"provenance {key} must be a nonblank string")
            result[key] = value

    tools = _first(raw, "tool_versions", "transformation_tool_versions", "tools")
    if tools is not None:
        # canonical_digest performs the strict JSON-value check.  Store a
        # detached value so caller mutation cannot change a returned bundle.
        try:
            canonical_digest(tools)
        except (TypeError, ValueError) as exc:
            raise WorkflowBundleError(f"invalid provenance tool_versions: {exc}") from exc
        result["tool_versions"] = copy.deepcopy(tools)
    # Imported workflows carry a closed, source-authored provenance report
    # (from porting.provenance.extract_provenance). Retain it through bundle
    # revisions so re-emission cannot silently replace mixed pins with a
    # runtime-resolved version. Validate as canonical JSON without imposing a
    # second schema here; the extractor owns that report shape.
    source_provenance = raw.get("source_provenance")
    if source_provenance is not None:
        try:
            canonical_digest(source_provenance)
        except (TypeError, ValueError) as exc:
            raise WorkflowBundleError(f"invalid source_provenance: {exc}") from exc
        result["source_provenance"] = copy.deepcopy(source_provenance)
    return result


def _sidecar_path(source: Path) -> Path:
    return source.with_suffix(".vibe.json")


def _read_sidecar(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    legacy = path.with_suffix(".layout.json")
    if legacy.is_file():
        raise WorkflowBundleError(
            f"legacy layout sidecar {legacy} is not an approved source; "
            "re-import the source with `vibecomfy import` and export its presentation "
            "through the canonical `.vibe.json` companion"
        )
    candidate = _sidecar_path(path)
    if not candidate.is_file():
        return None
    return _read_json_object(candidate, label="workflow sidecar")


def _ui_candidate_sidecar(workflow: VibeWorkflow, candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Delegate LiteGraph capture to the named presentation boundary."""
    from vibecomfy.porting.emit.ui import capture_ui_candidate_sidecar

    return capture_ui_candidate_sidecar(workflow, candidate)


def _presentation_payload(
    workflow: VibeWorkflow,
    candidate: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if candidate is None:
        return {"nodes": {}, "links": [], "groups": [], "canvas": {}, "annotations": []}
    if candidate.get("format_version") == 2:
        presentation = candidate.get("presentation")
        if not isinstance(presentation, Mapping):
            raise WorkflowBundleError("workflow companion presentation must be an object")
        result = copy.deepcopy(dict(presentation))
        result.setdefault("annotations", [])
        return result
    v1 = (
        dict(candidate)
        if set(candidate) >= _SIDECAR_KEYS
        else _ui_candidate_sidecar(workflow, candidate)
    )
    annotations = v1.pop("annotations", [])
    validated = _validate_v1_sidecar(v1, workflow)
    return {
        key: copy.deepcopy(validated[key])
        for key in ("nodes", "links", "groups", "canvas")
    } | {"annotations": _validate_annotations(annotations, workflow)}


def _canonicalize_for_v2_pair(
    workflow: VibeWorkflow,
    candidate: Mapping[str, Any] | None,
    *,
    path: Path,
    provenance: Any,
    operation: str,
    parent_revision: str,
    preserve_authored_graph: bool = False,
) -> tuple[VibeWorkflow, Mapping[str, Any] | None]:
    """Materialize the clean Python identity before publishing its companion.

    Importers may retain native node ids and socket rosters so a captured UI
    candidate can be reconciled.  The public source intentionally does not
    carry that bookkeeping in every constructor call: the v2 companion owns
    it.  A short in-memory staged build applies that companion once, yielding
    the exact canonical workflow whose digest the final pair will publish.
    """
    if candidate is not None and candidate.get("format_version") == 2:
        return workflow, candidate

    provisional = _build_v2_sidecar(
        workflow,
        candidate,
        provenance=provenance,
        operation=operation,
        parent_revision=parent_revision,
        preserve_authored_graph=preserve_authored_graph,
    )
    # Establish the semantic expectation before asking the generated source to
    # rebuild it.  The staged load is a publication preflight, not an
    # authority that is allowed to define what the first build meant.  This
    # catches accidental value/topology loss while the original candidate is
    # still available and leaves the visible pair untouched on refusal.
    # Imported API-shaped graphs may retain a redundant ``[node, slot]`` view
    # beside the authoritative VibeEdge.  The canonical emitter deliberately
    # drops that duplicate view, so establish the pre-build expectation from
    # the admitted workflow after applying only that lossless normalization.
    expected_workflow = workflow.copy()
    from vibecomfy.workflow import _embedded_api_link_details
    from vibecomfy.ingest.snapshot import frozen_widget_names_by_uid

    # Normalize only aliases sealed by ingest. Ambient schema/object-info
    # guesses must never change the digest expectation; unresolved slots stay
    # positional and therefore fail closed if the staged source changes them.
    names_by_uid = frozen_widget_names_by_uid(workflow)
    for node_id, node in expected_workflow.nodes.items():
        if str(getattr(node, "class_type", "")) != "TripoImageToModelNode":
            continue
        names = names_by_uid.get(str(getattr(node, "uid", "") or node_id), ())
        for key in list(node.widgets):
            if not key.startswith("widget_"):
                continue
            try:
                index = int(key.split("_", 1)[1])
            except ValueError:
                continue
            alias = names[index] if index < len(names) else None
            if not isinstance(alias, str) or alias.startswith("widget_"):
                continue
            if alias in node.widgets and node.widgets[alias] != node.widgets[key]:
                continue
            node.widgets[alias] = node.widgets.pop(key)

    # A linked Preview3D model is authoritative over the UI's positional
    # preview payload. The normal scratchpad loader already drops those
    # duplicate/opaque slots; mirror that one proven source-backed rule in
    # the expectation so admission compares the same semantics. Unlinked
    # previews and unknown node classes remain fail-closed.
    node_ids = {str(node_id) for node_id in expected_workflow.nodes}
    linked_preview_models = {
        str(edge.to_node)
        for edge in expected_workflow.edges
        if str(edge.to_input) == "model_file" and str(edge.to_node) in node_ids
    }
    for node_id, node in expected_workflow.nodes.items():
        if str(node_id) not in linked_preview_models:
            continue
        if str(getattr(node, "class_type", "")) != "Preview3D":
            continue
        # The linked model collision makes the positional preview payload
        # non-authoritative; the loader retains only the empty camera slot.
        node.inputs["camera_info"] = ""
        for key in list(node.inputs):
            if key.startswith("widget_"):
                node.inputs.pop(key)

    for detail in _embedded_api_link_details(expected_workflow):
        if detail["edge_collision"] != "identical":
            raise WorkflowBundleError(
                "canonical first-build candidate contains conflicting embedded API link"
            )
        node = expected_workflow.nodes[str(detail["node_id"])]
        storage = getattr(node, detail["storage"])
        storage.pop(str(detail["input_name"]), None)
    # Finalize canonically refreshes a non-empty model requirement witness from
    # the source-backed picker values.  Establish the same expectation before
    # the staged rebuild so the independent first-build check compares like
    # with like while retaining duplicate picker occurrences and explicit
    # empty requirements.
    from vibecomfy.model_assets import _referenced_model_values

    if expected_workflow.requirements.models:
        expected_models = [
            str(item["value"])
            for item in _referenced_model_values(expected_workflow)
            if isinstance(item, Mapping) and item.get("value")
        ]
        if expected_models:
            expected_workflow.requirements.models = reconcile_model_requirements(
                expected_workflow.requirements.models,
                expected_models,
            )
    expected_semantic_digest = expected_workflow.semantic_digest()
    from vibecomfy.porting.emit import emit_scratchpad_python
    from vibecomfy.scratchpad_loader import load_scratchpad

    logical_path = path.resolve()
    emitted_workflow = workflow.copy()
    emitted_workflow.metadata["source_bundle"] = _v2_marker(provisional)
    provenance_payload = dict(provenance) if isinstance(provenance, Mapping) else {}
    source = emit_scratchpad_python(
        emitted_workflow,
        workflow_id=workflow.id,
        source_path=str(logical_path),
        provenance=provenance_payload,
        external_custody=True,
        preserve_authored_graph=preserve_authored_graph,
    )
    with tempfile.TemporaryDirectory(prefix="vibecomfy-v2-canonicalize-") as temp_dir:
        staged_path = Path(temp_dir) / path.name
        staged_path.write_text(source, encoding="utf-8")
        with _staged_companion_context(logical_path, provisional):
            normalized = load_scratchpad(
                staged_path,
                provenance_override=Provenance.USER_CONFIRMED,
                logical_path=logical_path,
            )
    if normalized.semantic_digest() != expected_semantic_digest:
        raise WorkflowBundleError(
            "canonical first-build semantic digest differs from admitted candidate"
        )
    return normalized, candidate


def _apply_candidate_node_identity(
    workflow: VibeWorkflow,
    candidate: Mapping[str, Any] | None,
) -> VibeWorkflow:
    """Carry durable UI node identity into the canonical pair before staging.

    A generated Python candidate intentionally uses compact local construction
    identities while it is being built.  When that candidate came from a
    LiteGraph capture, the captured node id (or its explicit
    ``properties.vibecomfy_uid``) is the source-backed identity witness for
    layout, edits, and export.  Adopt it on a detached workflow copy before
    the v2 custody digest is made; otherwise the companion would faithfully
    preserve a newly minted ``n1`` identity and lose the original UI mapping.
    """
    if candidate is None or candidate.get("format_version") == 2:
        return workflow
    from vibecomfy.ingest.normalize import canonical_ui_node_identities

    try:
        captured_identities = canonical_ui_node_identities(candidate)
    except ValueError as exc:
        raise WorkflowBundleError(str(exc)) from exc
    by_source_id = dict(captured_identities)

    if not by_source_id:
        return workflow
    detached = workflow.copy()
    assigned: set[str] = set()
    for node_id, node in detached.nodes.items():
        uid = by_source_id.get(str(node_id))
        if uid is None:
            continue
        if uid in assigned:
            raise WorkflowBundleError(f"captured UI identity maps multiple workflow nodes to {uid!r}")
        node.uid = uid
        assigned.add(uid)
    return detached


def _build_v2_sidecar(
    workflow: VibeWorkflow,
    candidate: Mapping[str, Any] | None,
    *,
    provenance: Any,
    operation: str,
    parent_revision: str,
    preserve_authored_graph: bool = False,
) -> dict[str, Any]:
    """Build one deterministic publication capsule around Python semantics."""
    from vibecomfy.porting.emit.emit_ready import canonical_v2_custody

    custody = canonical_v2_custody(workflow, preserve_authored_graph=preserve_authored_graph)
    custody_digest = canonical_digest(custody)
    presentation = _presentation_payload(workflow, candidate)
    generation_id = canonical_digest(
        {
            "workflow_identity": workflow.id,
            "semantic_digest": workflow.semantic_digest(),
            "custody_digest": custody_digest,
            "presentation_digest": canonical_digest(presentation),
            "provenance": filter_provenance(provenance, default_operation=operation),
            "parent_revision": parent_revision,
        }
    )
    sidecar = {
        "format_version": 2,
        "bind": {
            "workflow_identity": workflow.id,
            "generation_id": generation_id,
            "custody_digest": custody_digest,
        },
        "custody": custody,
        "presentation": presentation,
    }
    return _validate_v2_sidecar(sidecar, workflow)


def _v2_marker(sidecar: Mapping[str, Any]) -> dict[str, Any]:
    bind = sidecar.get("bind")
    if sidecar.get("format_version") != 2 or not isinstance(bind, Mapping):
        raise WorkflowBundleError("cannot mark Python from a non-v2 companion")
    return {
        "format_version": 2,
        "generation_id": bind["generation_id"],
        "custody_digest": bind["custody_digest"],
    }


def _check_sidecar_identity(sidecar: Mapping[str, Any] | None, workflow: VibeWorkflow) -> None:
    if sidecar is None:
        return
    bind = sidecar.get("bind")
    if bind is not None and not isinstance(bind, Mapping):
        raise WorkflowBundleError("workflow sidecar bind must be a mapping")
    if isinstance(bind, Mapping):
        declared = bind.get("workflow_identity")
        if declared is not None and declared != workflow.id:
            raise WorkflowBundleError(
                f"workflow identity mismatch: bind.workflow_identity {declared!r} must equal {workflow.id!r}"
            )


def _lineage_records(workflow: VibeWorkflow) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    sources = [getattr(workflow, "metadata", {}), getattr(workflow.source, "provenance", {})]
    for source in sources:
        if not isinstance(source, Mapping):
            continue
        for key in ("revision_evidence",):
            value = source.get(key)
            if isinstance(value, Mapping):
                if isinstance(value.get("revision_id"), str):
                    records.append(value)
                else:
                    records.extend(item for item in value.values() if isinstance(item, Mapping))
            elif isinstance(value, (list, tuple)):
                records.extend(item for item in value if isinstance(item, Mapping))
    return records


def _resolve_parent(
    workflow: VibeWorkflow,
    parent_revision: str,
    parent_evidence: Mapping[str, Any] | None = None,
) -> str:
    if not isinstance(parent_revision, str):
        raise WorkflowBundleError("parent_revision must be a revision string")
    if not parent_revision:
        return ""
    records = _lineage_records(workflow)
    if parent_evidence is not None:
        if not isinstance(parent_evidence, Mapping):
            raise WorkflowBundleError("parent evidence must be a mapping")
        records.append(parent_evidence)
    for record in records:
        if record.get("revision_id") != parent_revision:
            continue
        identity = record.get("workflow_identity", record.get("workflow_id"))
        if identity != workflow.id:
            raise WorkflowBundleError("parent revision workflow identity does not match child workflow")
        return parent_revision
    raise WorkflowBundleError(f"unknown parent revision {parent_revision!r}")


_APPROVED_RECORD_KEYS = frozenset(
    {
        "revision_id",
        "selected_variant",
        "input_binding",
        "api_projection",
        "ui_projection",
        "api_digest",
    }
)


@dataclass(frozen=True, slots=True)
class ApprovedProjectionRecord:
    """Detached, recursively immutable value, not production authority.

    Construction and decoding only produce a value.  A production consumer
    must call :meth:`assert_matches` against a current bundle before use.
    """

    revision_id: str
    selected_variant: str | None
    input_binding: Mapping[str, Any]
    api_projection: Mapping[str, Any]
    ui_projection: Mapping[str, Any]
    api_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.revision_id, str) or not self.revision_id.strip():
            raise WorkflowBundleError("approved projection revision_id must be nonblank")
        if self.selected_variant is not None and not isinstance(self.selected_variant, str):
            raise WorkflowBundleError("approved projection selected_variant must be a string or null")
        for name in ("input_binding", "api_projection", "ui_projection"):
            value = getattr(self, name)
            if not isinstance(value, Mapping):
                raise WorkflowBundleError(f"approved projection {name} must be an object")
            object.__setattr__(self, name, _freeze_json(value))
        if not isinstance(self.api_digest, str):
            raise WorkflowBundleError("approved projection api_digest must be a string")
        actual = canonical_digest(_thaw_json(self.api_projection))
        if self.api_digest != actual:
            raise WorkflowBundleError("approved projection api_digest does not match api_projection")

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON object with exactly the six record keys."""
        return {
            "revision_id": self.revision_id,
            "selected_variant": self.selected_variant,
            "input_binding": _thaw_json(self.input_binding),
            "api_projection": _thaw_json(self.api_projection),
            "ui_projection": _thaw_json(self.ui_projection),
            "api_digest": self.api_digest,
        }

    def to_canonical_bytes(self) -> bytes:
        return canonical_json(self.to_dict()).encode("utf-8")

    @classmethod
    def from_dict(cls, value: Any) -> "ApprovedProjectionRecord":
        """Decode a strict value; this does not authorize execution."""
        if not isinstance(value, Mapping) or set(value) != _APPROVED_RECORD_KEYS:
            raise WorkflowBundleError(
                "approved projection record must contain exactly the six required fields"
            )
        revision_id = value["revision_id"]
        selected_variant = value["selected_variant"]
        input_binding = value["input_binding"]
        api_projection = value["api_projection"]
        ui_projection = value["ui_projection"]
        api_digest = value["api_digest"]
        if not isinstance(revision_id, str):
            raise WorkflowBundleError("approved projection revision_id must be a string")
        if selected_variant is not None and not isinstance(selected_variant, str):
            raise WorkflowBundleError("approved projection selected_variant must be a string or null")
        if not isinstance(input_binding, Mapping):
            raise WorkflowBundleError("approved projection input_binding must be an object")
        if not isinstance(api_projection, Mapping):
            raise WorkflowBundleError("approved projection api_projection must be an object")
        if not isinstance(ui_projection, Mapping):
            raise WorkflowBundleError("approved projection ui_projection must be an object")
        if not isinstance(api_digest, str):
            raise WorkflowBundleError("approved projection api_digest must be a string")
        return cls(
            revision_id,
            selected_variant,
            input_binding,
            api_projection,
            ui_projection,
            api_digest,
        )

    @classmethod
    def from_canonical_bytes(cls, value: bytes) -> "ApprovedProjectionRecord":
        if not isinstance(value, bytes):
            raise WorkflowBundleError("approved projection bytes must be bytes")
        try:
            decoded = json.loads(value.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowBundleError(f"invalid approved projection bytes: {exc}") from exc
        if canonical_json(decoded).encode("utf-8") != value:
            raise WorkflowBundleError("approved projection bytes are not canonical")
        return cls.from_dict(decoded)

    def assert_matches(
        self,
        bundle: "WorkflowBundle",
        variant: str | None = None,
        run_inputs: Mapping[str, Any] | None = None,
        api_projection: Mapping[str, Any] | None = None,
        ui_projection: Mapping[str, Any] | None = None,
    ) -> None:
        """Revalidate this record against a current bundle and fresh projections."""
        if not isinstance(bundle, WorkflowBundle):
            raise WorkflowBundleError("approved projection must be bound to a WorkflowBundle")
        current = _rebind_current_bundle(bundle)
        if current.revision_id != bundle.revision_id or current.revision_id != self.revision_id:
            raise WorkflowBundleError("approved projection revision does not match bundle")
        selected_variant = bundle.workflow.default_variant if variant is None else variant
        if selected_variant != self.selected_variant:
            raise WorkflowBundleError("approved projection variant binding does not match")
        binding = {} if run_inputs is None else run_inputs
        if not isinstance(binding, Mapping):
            raise WorkflowBundleError("run_inputs must be an object")
        try:
            binding_snapshot = _thaw_json(_freeze_json(binding))
        except WorkflowBundleError as exc:
            raise WorkflowBundleError(f"run_inputs are not JSON-safe: {exc}") from exc
        if canonical_json(_thaw_json(self.input_binding)) != canonical_json(binding_snapshot):
            raise WorkflowBundleError("approved projection input binding does not match")
        if not isinstance(api_projection, Mapping):
            raise WorkflowBundleError("approved projection API projection is required")
        if not isinstance(ui_projection, Mapping):
            raise WorkflowBundleError("approved projection UI projection is required")
        try:
            api_snapshot = _thaw_json(_freeze_json(api_projection))
            ui_snapshot = _thaw_json(_freeze_json(ui_projection))
        except WorkflowBundleError as exc:
            raise WorkflowBundleError(f"fresh projections are not JSON-safe: {exc}") from exc
        if canonical_json(_thaw_json(self.api_projection)) != canonical_json(api_snapshot):
            raise WorkflowBundleError("approved projection API projection does not match")
        if canonical_json(_thaw_json(self.ui_projection)) != canonical_json(ui_snapshot):
            raise WorkflowBundleError("approved projection UI projection does not match")
        if self.api_digest != canonical_digest(_thaw_json(self.api_projection)):
            raise WorkflowBundleError("approved projection API digest is invalid")
        # Caller-supplied projections are not current-bundle evidence.  Recompile
        # the live Python API graph so a digest-consistent forged record cannot
        # authorize a different queued semantic payload.
        try:
            fresh_api = current.workflow.compile(
                "api",
                variant=self.selected_variant,
                run_inputs=_thaw_json(self.input_binding),
            )
        except Exception as exc:
            raise WorkflowBundleError(
                f"approved projection could not recompile current bundle: {type(exc).__name__}: {exc}"
            ) from exc
        if canonical_json(_thaw_json(self.api_projection)) != canonical_json(fresh_api):
            raise WorkflowBundleError(
                "approved projection API projection does not match current bundle"
            )


def _rebind_current_bundle(bundle: "WorkflowBundle") -> "WorkflowBundle":
    """Rebuild current revision state without compiling or changing bindings."""
    operation = str(bundle.provenance.get("operation", "authored"))
    bound_current = _make_bundle(
        bundle.workflow,
        python_path=bundle.python_path,
        ui_sidecar=bundle.ui_sidecar,
        provenance=bundle.provenance,
        operation=operation,
        authority_kind=bundle.authority_kind,
        parent_revision=bundle.parent_revision,
        parent_evidence={
            "revision_id": bundle.parent_revision,
            "workflow_identity": bundle.workflow.id,
        }
        if bundle.parent_revision
        else None,
    )
    if bound_current.revision_id != bundle.revision_id:
        raise WorkflowBundleError("workflow bundle revision is stale; bound provenance changed")

    source_provenance = getattr(bundle.workflow.source, "provenance", None)
    if source_provenance is None or source_provenance == {}:
        return bound_current
    if not isinstance(source_provenance, Mapping):
        raise WorkflowBundleError("workflow source provenance must be a mapping")
    live_provenance = dict(source_provenance)
    # The operation is a bound property of the bundle, not a mutable source
    # override.  Keep the other bound identity inputs exactly as loaded.
    live_provenance["operation"] = operation
    live_current = _make_bundle(
        bundle.workflow,
        python_path=bundle.python_path,
        ui_sidecar=bundle.ui_sidecar,
        provenance=live_provenance,
        operation=operation,
        authority_kind=bundle.authority_kind,
        parent_revision=bundle.parent_revision,
        parent_evidence={
            "revision_id": bundle.parent_revision,
            "workflow_identity": bundle.workflow.id,
        }
        if bundle.parent_revision
        else None,
    )
    if live_current.revision_id != bundle.revision_id:
        raise WorkflowBundleError("workflow bundle revision is stale; live source provenance differs")
    return live_current


def _approval_preconditions(
    workflow: VibeWorkflow,
    schema_provider: Any,
    *,
    models_root: str | Path | None = None,
) -> None:
    """Run local, read-only requirement, schema-identity, and model gates."""
    requirements = getattr(workflow, "requirements", None)
    for field_name in ("missing_models", "missing_nodes", "unsupported"):
        values = getattr(requirements, field_name, ()) if requirements is not None else ()
        if values:
            raise WorkflowBundleError(
                f"workflow requirements contain unresolved {field_name}: "
                + ", ".join(sorted(str(value) for value in values))
            )

    try:
        from vibecomfy.node_packs import CORE_COMFY_CLASSES, get_known_node_packs, read_lockfile

        # Bind both local pack authorities to the repository containing this
        # implementation.  In particular, never branch on a caller's CWD or
        # invoke the legacy helper's ambient/on-demand schema path.
        repo_root = Path(__file__).resolve().parents[1]
        lock_path = repo_root / "custom_nodes.lock"
        lock_entries = read_lockfile(lock_path)
        known_packs = get_known_node_packs(lock_path)
        known_pack_classes = {
            str(class_type)
            for pack in known_packs
            for class_type in pack.classes
        }
        get_schema = getattr(schema_provider, "get_schema", None)
        if not callable(get_schema):
            get_schema = getattr(schema_provider, "get", None)
        schema_classes = {
            str(node.class_type)
            for node in workflow.nodes.values()
            if callable(get_schema) and get_schema(str(node.class_type)) is not None
        }
        missing_classes = sorted(
            {str(node.class_type) for node in workflow.nodes.values()}
            - schema_classes
            - known_pack_classes
            - set(CORE_COMFY_CLASSES)
        )
    except Exception as exc:
        raise WorkflowBundleError(
            f"local node-pack reconciliation failed: {type(exc).__name__}: {exc}"
        ) from exc
    if missing_classes:
        raise WorkflowReconciliationError(tuple(missing_classes))

    metadata = getattr(workflow, "metadata", {})
    reconciliation = metadata.get("reconciliation") if isinstance(metadata, Mapping) else None
    if reconciliation is not None and not isinstance(reconciliation, Mapping):
        raise WorkflowBundleError("workflow reconciliation evidence is malformed")

    def _reconciliation_blocker(value: Any) -> str | None:
        if isinstance(value, Mapping):
            status = value.get("status")
            if status in {"blocked", "error", "failed", "stale", "unknown", "restart_required"}:
                return str(status)
            if value.get("severity") == "error":
                return "error diagnostic"
            for item in value.values():
                blocker = _reconciliation_blocker(item)
                if blocker:
                    return blocker
        elif isinstance(value, (list, tuple)):
            for item in value:
                blocker = _reconciliation_blocker(item)
                if blocker:
                    return blocker
        return None

    blocker = _reconciliation_blocker(reconciliation)
    if blocker:
        raise WorkflowBundleError(f"workflow reconciliation is not approved: {blocker}")

    identity_table = metadata.get("object_info_identities") if isinstance(metadata, Mapping) else None
    if identity_table is not None and not isinstance(identity_table, Mapping):
        raise WorkflowBundleError("object-info identity evidence is malformed")
    try:
        from vibecomfy.porting.object_info import resolve_class_entry

        pack_by_class = {
            str(class_type): pack
            for pack in known_packs
            for class_type in pack.classes
        }
        lock_by_name = {str(entry.name): entry for entry in lock_entries}
        lock_by_slug = {str(entry.slug or entry.name): entry for entry in lock_entries}

        for node_id, node in sorted(workflow.nodes.items(), key=lambda item: str(item[0])):
            source = node.metadata.get("schema_source") if isinstance(node.metadata, Mapping) else None
            identity = node.metadata.get("object_info_identity") if isinstance(node.metadata, Mapping) else None
            if identity is None and isinstance(identity_table, Mapping):
                identity = identity_table.get(str(node_id), identity_table.get(node_id))
            # Ready templates are materialized from the repository's pinned
            # schema cache, but their generated node metadata intentionally
            # does not carry a per-node object-info identity.  Remember that
            # distinction before deriving the pack's lock identity below;
            # authored/captured workflows must remain fail-closed when an
            # exact identity cannot be resolved.
            has_explicit_identity = identity is not None or (
                isinstance(source, Mapping)
                and any(
                    key in source
                    for key in (
                        "pack_slug", "pack", "package", "git_commit",
                        "commit", "evidence_identity",
                    )
                )
            )
            pack = pack_by_class.get(str(node.class_type))
            pack_name = str(pack.name) if pack is not None else None
            lock_entry = lock_by_name.get(pack_name) if pack_name is not None else None
            if lock_entry is None and isinstance(source, Mapping):
                source_pack = source.get("pack_slug") or source.get("pack") or source.get("package")
                if isinstance(source_pack, str):
                    lock_entry = lock_by_name.get(source_pack) or lock_by_slug.get(source_pack)

            explicit_identities: list[Any] = []
            if isinstance(source, Mapping) and any(
                key in source
                for key in ("pack_slug", "pack", "package", "git_commit", "commit", "evidence_identity")
            ):
                explicit_identities.append(source)
            if identity is not None:
                explicit_identities.append(identity)
            if lock_entry is not None and explicit_identities:
                lock_slug = str(lock_entry.slug or lock_entry.name)
                lock_name = str(lock_entry.name)
                lock_commit = lock_entry.commit or lock_entry.git_commit_sha
                for explicit in explicit_identities:
                    if isinstance(explicit, Mapping):
                        explicit_pack = explicit.get("pack_slug") or explicit.get("pack") or explicit.get("package")
                        explicit_commit = explicit.get("git_commit") or explicit.get("commit")
                        explicit_evidence = explicit.get("evidence_identity")
                    else:
                        explicit_pack = getattr(explicit, "pack_slug", None)
                        explicit_commit = getattr(explicit, "git_commit", None)
                        explicit_evidence = getattr(explicit, "evidence_identity", None)
                    if explicit_pack is not None and str(explicit_pack) not in {lock_slug, lock_name}:
                        raise WorkflowBundleError(
                            f"object-info identity pack conflicts with lock for {node.class_type} ({node_id})"
                        )
                    if lock_commit is not None:
                        for pin in (explicit_commit, explicit_evidence):
                            if pin is not None and str(pin) != str(lock_commit):
                                raise WorkflowBundleError(
                                    f"object-info identity pin conflicts with lock for {node.class_type} ({node_id})"
                                )

            # A schema_source is provenance, not an identity by itself.  Use
            # only its explicit identity fields or an actual lock commit; do
            # not invent a value from provider/path/hash text.
            if identity is None and isinstance(source, Mapping):
                source_pack = source.get("pack_slug") or source.get("pack") or source.get("package")
                source_commit = source.get("git_commit") or source.get("commit")
                source_evidence = source.get("evidence_identity")
                if source_pack and source_commit:
                    identity = {"pack_slug": str(source_pack), "git_commit": str(source_commit)}
                elif source_pack and source_evidence:
                    identity = {"pack_slug": str(source_pack), "evidence_identity": str(source_evidence)}
            if lock_entry is not None:
                commit = lock_entry.commit or lock_entry.git_commit_sha
                if commit:
                    identity = {
                        "pack_slug": str(lock_entry.slug or lock_entry.name),
                        "git_commit": str(commit),
                    }
            if identity is None:
                if pack is not None:
                    raise WorkflowBundleError(
                        f"object-info identity is unavailable for {node.class_type} ({node_id})"
                    )
                continue
            result = resolve_class_entry(
                str(node.class_type), identity=identity, allow_class_fallback=False
            )
            if result.entry is None:
                # A generated ready template has already been bound to a
                # concrete schema provider.  The local object-info cache
                # may only have a class-only entry for that same provider
                # (for example, a custom node whose object-info snapshot
                # is stored under the core cache).  Accept that bounded
                # fallback only when the provider package agrees with the
                # cache entry package, and only for this materialized
                # ready-template path.  Explicit identities and ordinary
                # captured/authored workflows still require an exact
                # lock-pinned identity.
                source_role = (
                    metadata.get("source_role")
                    if isinstance(metadata, Mapping)
                    else None
                )
                if not has_explicit_identity and source_role == "materialized_ready_python_template":
                    provider_schema = get_schema(str(node.class_type)) if callable(get_schema) else None
                    provider_package = getattr(provider_schema, "source_package", None)
                    fallback = resolve_class_entry(
                        str(node.class_type), identity=identity, allow_class_fallback=True
                    )
                    fallback_entry = fallback.entry
                    fallback_package = (
                        fallback_entry.get("pack_slug") or fallback_entry.get("pack")
                        if isinstance(fallback_entry, Mapping)
                        else None
                    )
                    if (
                        fallback.source == "class_fallback"
                        and fallback_entry is not None
                        and provider_package
                        and fallback_package
                        and str(provider_package) == str(fallback_package)
                    ):
                        continue
                raise WorkflowBundleError(
                    f"object-info identity does not resolve for {node.class_type} ({node_id})"
                )
    except WorkflowBundleError:
        raise
    except Exception as exc:
        raise WorkflowBundleError(
            f"local object-info identity check failed: {type(exc).__name__}: {exc}"
        ) from exc

    try:
        from vibecomfy.fetch import is_present, verify
        from vibecomfy.model_assets import _referenced_model_values
        from vibecomfy.registry.models_loader import load_registry, resolve_model_entry

        references: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add_reference(value: Any, subdir: Any = "") -> None:
            if not isinstance(value, str) or not value.strip():
                raise WorkflowBundleError("workflow model reference is malformed")
            if subdir is not None and not isinstance(subdir, str):
                raise WorkflowBundleError("workflow model reference subdir is malformed")
            normalized_value = value.replace("\\", "/")
            normalized_subdir = (subdir or "").replace("\\", "/")
            key = (normalized_value, normalized_subdir)
            if key not in seen:
                seen.add(key)
                references.append({"value": normalized_value, "subdir": normalized_subdir})

        for reference in _referenced_model_values(workflow):
            if not isinstance(reference, Mapping):
                raise WorkflowBundleError("workflow model reference is malformed")
            add_reference(reference.get("value"), reference.get("subdir", ""))

        if isinstance(metadata, Mapping) and "model_assets" in metadata:
            assets = metadata["model_assets"]
            if not isinstance(assets, list):
                raise WorkflowBundleError("workflow model_assets are malformed")
            for asset in assets:
                if not isinstance(asset, Mapping):
                    raise WorkflowBundleError("workflow model asset is malformed")
                add_reference(asset.get("name"), asset.get("subdir", asset.get("directory", "")))

        declared_models = getattr(requirements, "models", ()) if requirements is not None else ()
        if declared_models is None:
            declared_models = ()
        for value in declared_models:
            if isinstance(value, Mapping):
                # ReadyMetadata may carry a source-backed model asset rather
                # than flattening it to a filename.  Reconcile the same
                # deterministic (name, subdir) witness used by model_assets;
                # optional URL/hash fields remain metadata, not approval input.
                add_reference(
                    value.get("name"),
                    value.get("subdir", value.get("directory", "")),
                )
            elif isinstance(value, str):
                add_reference(value)
            else:
                raise WorkflowBundleError("workflow requirements.models contains a malformed entry")
        if not references:
            return
        registry = load_registry()
        authored_assets = (
            [asset for asset in metadata.get("model_assets", []) if isinstance(asset, Mapping)]
            if isinstance(metadata, Mapping) and isinstance(metadata.get("model_assets"), list)
            else []
        )

        def authored_asset(value: str, subdir: str) -> Mapping[str, Any] | None:
            for asset in authored_assets:
                name = asset.get("name", asset.get("filename"))
                asset_subdir = asset.get("subdir", asset.get("directory", ""))
                if str(name) == value and str(asset_subdir or "") == subdir:
                    return asset
            return None

        for reference in references:
            value = reference.get("value")
            subdir = reference.get("subdir")
            entry = resolve_model_entry(value, registry=registry, subdir=subdir or None)
            if entry is None:
                local_asset = authored_asset(str(value), str(subdir or ""))
                if local_asset is None:
                    raise WorkflowBundleError(f"model reference is not locally registered: {value}")
                if local_asset.get("gated") is not True and not local_asset.get("url"):
                    raise WorkflowBundleError(
                        f"model reference is not locally registered and has no source URL: {value}"
                    )
                local_root = Path(models_root) if models_root is not None else None
                try:
                    if not is_present(
                        {"name": value, "subdir": subdir or ""}, root=local_root
                    ):
                        raise WorkflowBundleError(
                            f"workflow-local model is not present locally: {value}"
                        )
                    verify(local_asset, root=local_root)
                except WorkflowBundleError:
                    raise
                except Exception as exc:
                    raise WorkflowBundleError(
                        f"workflow-local model verification failed for {value}: {exc}"
                    ) from exc
                continue
            effective_subdir = subdir
            if not effective_subdir and entry.targets:
                target_path = str(entry.targets[0].path).replace("\\", "/")
                effective_subdir = target_path.rsplit("/", 1)[0] if "/" in target_path else ""
            if not effective_subdir:
                raise WorkflowBundleError(f"model reference has no deterministic local target: {value}")
            root = Path(models_root) if models_root is not None else None
            if isinstance(metadata, Mapping) and metadata.get("models_root") is not None:
                raw_root = metadata["models_root"]
                if not isinstance(raw_root, (str, Path)) or not Path(raw_root).is_absolute():
                    raise WorkflowBundleError("workflow models_root must be an absolute path")
                if root is None:
                    root = Path(raw_root)
            if not is_present({"name": value, "subdir": effective_subdir}, root=root):
                raise WorkflowBundleError(f"registered model is not present locally: {value}")
    except WorkflowBundleError:
        raise
    except Exception as exc:
        raise WorkflowBundleError(
            f"local model reconciliation failed: {type(exc).__name__}: {exc}"
        ) from exc


@dataclass(frozen=True)
class WorkflowBundle:
    """One candidate source revision bound to a :class:`VibeWorkflow`."""

    workflow: VibeWorkflow
    python_path: Path | None
    ui_sidecar: Mapping[str, Any] | None
    semantic_digest: str
    ui_digest: str
    provenance: Mapping[str, Any]
    parent_revision: str = ""
    revision_id: str = ""
    authority_kind: str = "canonical"

    @property
    def workflow_identity(self) -> str:
        """Read-only identity derived from the workflow, never independently stored."""
        return self.workflow.id

    def require_canonical_authority(self, action: str) -> None:
        """Reject compatibility imports before any canonical consumer."""
        if self.authority_kind == "canonical":
            return
        if self.authority_kind != "import_evidence":
            raise WorkflowBundleError(
                f"{action} rejected unknown workflow authority kind "
                f"{self.authority_kind!r}"
            )
        raise _workflow_authority_error(self.workflow, action)

    def materialize_ui(self, *, schema_provider: Any = None, strict: bool = False) -> dict[str, Any]:
        """Materialize this bundle's UI projection through the one UI boundary.

        Validation is intentionally repeated immediately before emitter
        invocation.  A bundle may be held while its detached sidecar mapping is
        mutated by a caller; such a mutation must fail closed and must never
        reach the emitter or a legacy/raw UI fallback.
        """
        self.require_canonical_authority("UI materialization")
        return materialize_ui_json(
            self.workflow,
            self.ui_sidecar,
            schema_provider=schema_provider,
            strict=strict,
        )

    def compile(
        self,
        variant: str | None = None,
        run_inputs: dict[str, Any] | None = None,
        *,
        schema_provider: Any = None,
        models_root: str | Path | None = None,
    ) -> ApprovedProjectionRecord:
        """Compile this unchanged candidate into one detached approval record."""
        self.require_canonical_authority("workflow compilation")
        current = _rebind_current_bundle(self)
        if current.revision_id != self.revision_id:
            raise WorkflowBundleError("workflow bundle revision is stale; reload before approval")
        if not self.workflow.nodes:
            raise WorkflowBundleError("workflow is empty; approval requires at least one node")
        if schema_provider is None:
            from vibecomfy.schema import get_authoring_schema_provider

            schema_provider = get_authoring_schema_provider(on_demand_schemas=False)
        _approval_preconditions(self.workflow, schema_provider, models_root=models_root)
        binding = {} if run_inputs is None else run_inputs
        if not isinstance(binding, Mapping):
            raise WorkflowBundleError("run_inputs must be an object")
        try:
            binding_snapshot = _thaw_json(_freeze_json(binding))
        except WorkflowBundleError as exc:
            raise WorkflowBundleError(f"run_inputs are not JSON-safe: {exc}") from exc
        selected_variant = self.workflow.default_variant if variant is None else variant
        try:
            api_projection = self.workflow.compile(
                "api", variant=variant, run_inputs=binding_snapshot
            )
        except Exception as exc:
            raise WorkflowBundleError(
                f"workflow API projection failed: {type(exc).__name__}: {exc}"
            ) from exc
        try:
            from vibecomfy.schema.validate import (
                validate_api_against_schema,
                validate_api_link_shapes,
            )

            schema_issues = [
                *validate_api_against_schema(api_projection, schema_provider),
                *validate_api_link_shapes(api_projection, schema_provider),
            ]
        except Exception as exc:
            raise WorkflowBundleError(
                f"local schema validation failed: {type(exc).__name__}: {exc}"
            ) from exc
        errors = [issue for issue in schema_issues if getattr(issue, "severity", "error") == "error"]
        if errors:
            raise WorkflowBundleError(str(errors[0].message))
        ui_projection = self.materialize_ui(schema_provider=schema_provider)
        return ApprovedProjectionRecord(
            revision_id=self.revision_id,
            selected_variant=selected_variant,
            input_binding=binding_snapshot,
            api_projection=api_projection,
            ui_projection=ui_projection,
            api_digest=canonical_digest(api_projection),
        )


def materialize_ui_json(
    workflow: VibeWorkflow,
    sidecar: Mapping[str, Any] | None = None,
    *,
    schema_provider: Any = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Bundle-owned UI materialization convenience boundary.

    The strict sidecar is validated here, before importing or invoking the
    existing emitter.  The emitter performs semantic regeneration and the
    allowlist-only presentation overlay; it is not a second compiler.
    """
    source_path = getattr(workflow.source, "path", None)
    if isinstance(source_path, (str, Path)) and Path(source_path).suffix.lower() == ".json":
        raise _workflow_authority_error(workflow, "UI materialization")
    validated = validate_sidecar(sidecar, workflow) if sidecar is not None else None
    presentation = (
        validated.get("presentation")
        if isinstance(validated, Mapping) and validated.get("format_version") == 2
        else validated
    )
    if isinstance(validated, Mapping) and validated.get("format_version") == 2:
        # The lower-level UI emitter owns the legacy presentation overlay
        # contract.  Keep the v2 companion boundary here, but hand that owner
        # the same closed v1 envelope it already validates rather than the
        # bare presentation payload.
        presentation = {
            "format_version": 1,
            "bind": {
                "workflow_identity": workflow.id,
                "semantic_digest": workflow.semantic_digest(),
            },
            **dict(presentation or {}),
        }
    from vibecomfy.porting.emit.ui import materialize_ui_json as _materialize_ui_json

    return _materialize_ui_json(
        workflow,
        presentation,
        schema_provider=schema_provider,
        strict=strict,
    )

def _make_bundle(
    workflow: VibeWorkflow,
    *,
    python_path: Path | None,
    ui_sidecar: Mapping[str, Any] | None,
    provenance: Any,
    operation: str,
    authority_kind: str | None = None,
    parent_revision: str = "",
    parent_evidence: Mapping[str, Any] | None = None,
) -> WorkflowBundle:
    # This ordering is intentional: identity checks precede sidecar checks,
    # semantic digesting, UI digesting, revision creation, and source writes.
    # Sidecar identity is checked by its dedicated closed-boundary validator;
    # walking arbitrary node UID keys as generic ``source`` declarations would
    # mistake a perfectly valid node named ``source`` for a repeated identity.
    _check_identity(workflow, provenance)
    _check_sidecar_identity(ui_sidecar, workflow)
    semantic_digest = workflow.semantic_digest()
    sidecar = validate_sidecar(ui_sidecar, workflow) if ui_sidecar is not None else None
    ui_digest = _sidecar_ui_digest(sidecar)
    filtered = filter_provenance(provenance, default_operation=operation)
    parent = _resolve_parent(workflow, parent_revision, parent_evidence)
    bound_authority = (
        "import_evidence" if operation == "imported" else "canonical"
    ) if authority_kind is None else authority_kind
    if bound_authority not in {"canonical", "import_evidence"}:
        raise WorkflowBundleError(f"unknown workflow authority kind {bound_authority!r}")
    revision_preimage = [workflow.id, semantic_digest, ui_digest, filtered, parent]
    if bound_authority == "import_evidence":
        revision_preimage.append("import_evidence")
    revision_id = canonical_digest(revision_preimage)
    # Keep the lineage needed to reload this exact pair in the generated
    # Python source provenance.  This is identity evidence only; it is not
    # executable workflow state and is excluded from the revision digest by
    # ``filter_provenance``.
    bound_provenance = dict(filtered)
    lineage: list[dict[str, Any]] = []
    for record in _lineage_records(workflow):
        revision = record.get("revision_id")
        identity = record.get("workflow_identity", record.get("workflow_id"))
        if isinstance(revision, str) and isinstance(identity, str):
            lineage.append({"revision_id": revision, "workflow_identity": identity})
    if isinstance(parent_evidence, Mapping):
        lineage.append(
            {
                "revision_id": parent_evidence.get("revision_id"),
                "workflow_identity": parent_evidence.get(
                    "workflow_identity", parent_evidence.get("workflow_id")
                ),
            }
        )
    lineage.append({"revision_id": revision_id, "workflow_identity": workflow.id})
    # Deduplicate while preserving deterministic order.
    seen_lineage: set[tuple[Any, Any]] = set()
    bound_provenance["revision_evidence"] = []
    for record in lineage:
        key = (record.get("revision_id"), record.get("workflow_identity"))
        if key in seen_lineage or not all(isinstance(item, str) for item in key):
            continue
        seen_lineage.add(key)
        bound_provenance["revision_evidence"].append(record)
    bound_provenance["parent_revision"] = parent
    bundle = WorkflowBundle(
        workflow=workflow,
        python_path=python_path,
        ui_sidecar=sidecar,
        semantic_digest=semantic_digest,
        ui_digest=ui_digest,
        provenance=bound_provenance,
        parent_revision=parent,
        revision_id=revision_id,
        authority_kind=bound_authority,
    )
    return bundle


def _sidecar_ui_digest(sidecar: Mapping[str, Any] | None) -> str:
    """Digest presentation state without making custody part of UI identity."""
    if sidecar is None:
        return ""
    if sidecar.get("format_version") == 2 and isinstance(sidecar.get("presentation"), Mapping):
        return canonical_digest(sidecar["presentation"])
    return canonical_digest(sidecar)


def _resolve_reference(reference: str | Path) -> tuple[str | Path, Path | None, str]:
    value = Path(reference) if isinstance(reference, Path) else Path(str(reference))
    if value.suffix.lower() == ".vibe.json":
        python = value.with_suffix("").with_suffix(".py")
        return python, python if python.is_file() else None, "authored"
    if value.is_dir():
        # A workflow folder is a convenient locator for the canonical source;
        # resolve to workflow.py so its sibling companion remains bound to the
        # same logical path during scratchpad loading.
        from vibecomfy.commands._workflow_path import resolve_workflow_path

        python = Path(resolve_workflow_path(str(value)))
        return python, python, "authored"
    if value.is_file() and value.suffix.lower() in {".py", ".json"}:
        return value, value if value.suffix.lower() == ".py" else None, (
            "authored" if value.suffix.lower() == ".py" else "imported"
        )
    return str(reference), None, "authored"


def _is_api_node_mapping(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("class_type"), str) and isinstance(value.get("inputs"), Mapping)


def _is_identity_mapping(value: Any) -> bool:
    if not isinstance(value, Mapping) or _is_api_node_mapping(value):
        return False
    return any(isinstance(value.get(key), str) and value[key].strip() for key in ("id", "workflow_id", "workflow_identity"))


def _split_import_api(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Separate only positively identified API metadata from node IDs."""
    prompt = raw.get("prompt")
    if prompt is not None:
        if not isinstance(prompt, Mapping) or (prompt and not all(_is_api_node_mapping(item) for item in prompt.values())):
            raise WorkflowBundleError("ambiguous prompt API envelope")
        return dict(prompt)
    payload: dict[str, Any] = {}
    identity_keys = {"workflow_id", "workflow_identity", "id"}
    for key, value in raw.items():
        if key not in identity_keys and key != "source":
            payload[key] = value
            continue
        if _is_api_node_mapping(value):
            payload[key] = value
        elif key in identity_keys and (value is None or isinstance(value, str)):
            continue
        elif key == "source" and _is_identity_mapping(value):
            continue
        else:
            raise WorkflowBundleError(f"ambiguous API envelope field {key!r}")
    return payload


def _import_identity(raw: Mapping[str, Any], *, source_kind: str) -> str:
    """Extract an authored identity before crossing a JSON import boundary."""
    source = raw.get("source")
    if source_kind == "ui":
        candidates = (_first(raw, "workflow_identity", "workflow_id", "id"),)
    else:
        candidates = (
            _first(raw, "workflow_identity", "workflow_id", "id"),
            _first(source, "id", "workflow_identity", "workflow_id")
            if isinstance(source, Mapping) and not _is_api_node_mapping(source)
            else None,
        )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value
    raise WorkflowBundleError(
        "imported workflow has no explicit durable identity; add workflow_id "
        "(or an envelope source.id) before loading a canonical bundle"
    )


def load_bundle(
    reference: str | Path | VibeWorkflow,
    trust: Provenance | None = None,
    *,
    schema_provider: Any = None,
) -> WorkflowBundle:
    """Load one canonical Python/compatibility reference as a candidate bundle."""
    if isinstance(reference, VibeWorkflow):
        source_path = getattr(reference.source, "path", None)
        inherited_import = isinstance(source_path, (str, Path)) and Path(
            source_path
        ).suffix.lower() == ".json"
        return _make_bundle(
            reference,
            python_path=None,
            ui_sidecar=None,
            provenance={"operation": "imported" if inherited_import else "ephemeral"},
            operation="imported" if inherited_import else "ephemeral",
            authority_kind="import_evidence" if inherited_import else "canonical",
        )
    if not isinstance(reference, (str, Path)):
        raise TypeError(
            f"load_bundle requires a path, workflow id, or VibeWorkflow, got {type(reference).__name__}"
        )
    resolved, python_path, operation = _resolve_reference(reference)
    declared_identity: str | None = None
    if python_path is not None:
        from vibecomfy.scratchpad_loader import load_scratchpad

        # The compatibility CLI defaults to user confirmation.  Bundles keep
        # the actual typed trust value and let the restricted loader decide.
        workflow = load_scratchpad(python_path, provenance_override=trust)
    elif isinstance(resolved, Path) and resolved.suffix.lower() == ".json":
        if schema_provider is None:
            from vibecomfy.schema import get_authoring_schema_provider

            schema_provider = get_authoring_schema_provider(on_demand_schemas=False)
        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise WorkflowBundleError(f"could not read workflow source {resolved}: {exc}") from exc
        if not isinstance(raw, Mapping):
            raise WorkflowBundleError("imported workflow source must contain a JSON object")
        from vibecomfy.ingest.normalize import door_import_source_kind

        source_kind = door_import_source_kind(raw)
        declared_identity = _import_identity(raw, source_kind=source_kind)
        if source_kind == "api":
            # Imported compatibility JSON may carry the durable identity in a
            # thin envelope (including Comfy's ``{"prompt": API}`` wrapper).
            # Keep that identity at the bundle boundary; it is not a node in
            # the API projection and must not reach the normalizer as one.
            from vibecomfy.ingest.normalize import _named_import

            import_payload = _split_import_api(raw)
            workflow = _named_import(
                import_payload,
                source_path=str(resolved),
                workflow_id=declared_identity,
                schema_provider=schema_provider,
            )
        else:
            from vibecomfy.cli_loader import _load_workflow_path

            workflow = _load_workflow_path(
                resolved,
                workflow_id=declared_identity,
                schema_provider=schema_provider,
            )
    else:
        from vibecomfy.registry.ready import (
            ready_template_discovery,
            resolve_ready_template,
            workflow_from_ready,
        )

        discovery = ready_template_discovery()
        try:
            ready_record = resolve_ready_template(str(reference), discovery)
        except KeyError:
            if schema_provider is None:
                from vibecomfy.schema import get_authoring_schema_provider

                schema_provider = get_authoring_schema_provider(on_demand_schemas=False)
            from vibecomfy.registry.library import workflow_from_id

            workflow = workflow_from_id(str(reference), schema_provider=schema_provider)
        else:
            declared_identity = ready_record.template_id
            workflow = workflow_from_ready(
                str(reference), _discovery=discovery
            )
        source = getattr(workflow, "source", None)
        source_path = getattr(source, "path", None)
        if isinstance(source_path, str) and source_path:
            candidate = Path(source_path)
            if candidate.suffix.lower() == ".py":
                python_path = candidate
            elif candidate.suffix.lower() == ".json":
                operation = "imported"
    sidecar = _read_sidecar(python_path or (Path(resolved) if isinstance(resolved, Path) else None))
    source_provenance = getattr(getattr(workflow, "source", None), "provenance", {})
    # A ready/template reference is a declared identity, including aliases;
    # check it before any digesting so a registry stem cannot become identity.
    declarations = ({"workflow_identity": declared_identity},) if declared_identity else ()
    _check_identity(workflow, *declarations)
    loaded_parent = (
        source_provenance.get("parent_revision", "")
        if isinstance(source_provenance, Mapping)
        else ""
    )
    return _make_bundle(
        workflow,
        python_path=python_path,
        ui_sidecar=sidecar,
        provenance=source_provenance,
        operation=operation,
        parent_revision=loaded_parent,
        parent_evidence=None,
    )


def _destination_path(destination: str | Path, workflow: VibeWorkflow) -> Path:
    path = Path(destination)
    if path.exists() and path.is_dir():
        return path / f"{workflow.id}.py"
    if path.suffix.lower() != ".py":
        return path / f"{workflow.id}.py"
    return path


def emit_bundle(
    workflow: VibeWorkflow,
    destination: str | Path,
    provenance: Any,
    parent_revision: str = "",
) -> WorkflowBundle:
    """Write a canonical ``build()`` source candidate and return its bundle."""
    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(f"emit_bundle requires VibeWorkflow, got {type(workflow).__name__}")
    path = _destination_path(destination, workflow)
    # Preserve an already-present strict presentation candidate when replacing
    # the Python source.  A legacy .layout.json is deliberately not consulted.
    existing_sidecar = _read_sidecar(path)
    workflow, existing_sidecar = _canonicalize_for_v2_pair(
        workflow,
        existing_sidecar,
        path=path,
        provenance=provenance,
        operation="authored",
        parent_revision=parent_revision,
    )
    sidecar = _build_v2_sidecar(
        workflow,
        existing_sidecar,
        provenance=provenance,
        operation="authored",
        parent_revision=parent_revision,
    )
    bundle = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=sidecar,
        provenance=provenance,
        operation="authored",
        parent_revision=parent_revision,
    )
    from vibecomfy.porting.emit import emit_scratchpad_python

    path.parent.mkdir(parents=True, exist_ok=True)
    emitted_workflow = workflow.copy()
    emitted_workflow.metadata["source_bundle"] = _v2_marker(sidecar)
    source = emit_scratchpad_python(
        emitted_workflow,
        workflow_id=workflow.id,
        source_path=str(path),
        provenance=_source_provenance(bundle.provenance),
        external_custody=True,
    )
    _atomic_publish_pair(path, source, bundle.ui_sidecar, expected=bundle)
    return bundle


def _atomic_publish_pair(
    path: Path,
    source: str | bytes,
    sidecar: Mapping[str, Any] | None,
    *,
    expected: WorkflowBundle | None = None,
    expected_members: Mapping[str | Path, str | None] | None = None,
    extra_members: Mapping[str | Path, bytes] | None = None,
) -> None:
    """Validate staged bytes, then publish a complete bundle with rollback.

    ``expected_members`` is a best-effort compare-and-swap precondition checked
    after staging/backup and immediately before the first visible replacement.
    It is not a cross-process lock: a writer that ignores this publisher can
    still race in the tiny interval between the check and replacement.
    ``extra_members`` lets a caller publish immutable bundle evidence (such as
    the original ``source.json``) in the same recoverable replacement set.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []
    backup_paths: list[Path] = []
    backup_contents: dict[Path, bytes] = {}
    replaced: set[Path] = set()
    def cleanup(paths: list[Path]) -> list[str]:
        errors: list[str] = []
        for item in paths:
            if not item.exists():
                continue
            try:
                item.unlink()
            except OSError as exc:
                errors.append(f"{item}: {exc}")
        return errors

    def rollback(exc: BaseException) -> None:
        errors: list[str] = []
        errors.extend(cleanup([temporary for temporary, _ in staged]))
        backed = {destination for _, destination in backups}
        errors.extend(cleanup([destination for _, destination in staged if destination in replaced and destination.exists() and destination not in backed]))
        for backup, destination in reversed(backups):
            if destination not in replaced:
                # Never restore the precondition snapshot over a concurrent
                # writer when compare-and-swap fails before our first visible
                # replacement.
                continue
            try:
                if backup.exists():
                    os.replace(backup, destination)
                elif destination in backup_contents:
                    destination.write_bytes(backup_contents[destination])
                else:
                    raise OSError("backup bytes unavailable")
            except OSError as restore_exc:
                errors.append(f"restore {destination} from {backup}: {restore_exc}")
        errors.extend(cleanup(backup_paths))
        if errors:
            raise WorkflowBundleError(f"publication failed: {exc}; rollback/cleanup failed: {'; '.join(errors)}") from exc

    try:
        source_payload = source.encode("utf-8") if isinstance(source, str) else source
        if not isinstance(source_payload, bytes):
            raise TypeError("workflow Python source must be str or bytes")
        members: list[tuple[Path, bytes]] = [(path, source_payload)]
        if sidecar is not None:
            members.append((_sidecar_path(path), canonical_json(sidecar).encode("utf-8")))
        if extra_members is not None:
            for raw_destination, payload in extra_members.items():
                destination = Path(raw_destination)
                if not isinstance(payload, bytes):
                    raise TypeError("extra bundle member payloads must be bytes")
                if destination in {member for member, _ in members}:
                    raise WorkflowBundleError(
                        f"extra bundle member conflicts with canonical pair member {destination}"
                    )
                members.append((destination, payload))
        for destination, payload in members:
            fd, raw_tmp = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=destination.suffix or ".tmp", dir=str(path.parent))
            temporary = Path(raw_tmp)
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException as write_exc:
                try: temporary.unlink()
                except OSError as cleanup_exc:
                    raise WorkflowBundleError(
                        f"staged member write failed: {write_exc}; temporary cleanup failed: {cleanup_exc}"
                    ) from write_exc
                raise
            staged.append((temporary, destination))
        # Validate the actual staged Python before the first visible replace.
        if expected is not None:
            from vibecomfy.scratchpad_loader import load_scratchpad

            staged_sidecar_payload = None
            if sidecar is not None:
                staged_sidecar_path = next(item for item, destination in staged if destination == _sidecar_path(path))
                staged_sidecar_payload = _read_json_object(
                    staged_sidecar_path, label="staged workflow sidecar"
                )
            companion_context = (
                _staged_companion_context(path, staged_sidecar_payload)
                if staged_sidecar_payload is not None
                else nullcontext()
            )
            with companion_context:
                staged_workflow = load_scratchpad(
                    staged[0][0],
                    provenance_override=Provenance.USER_CONFIRMED,
                    logical_path=path,
                )
            if staged_workflow.id != expected.workflow.id:
                raise WorkflowBundleError("staged Python identity differs from intended bundle")
            if staged_workflow.semantic_digest() != expected.semantic_digest:
                raise WorkflowBundleError("staged Python semantic digest differs from intended bundle")
            staged_sidecar = validate_sidecar(staged_sidecar_payload, staged_workflow) if sidecar is not None else None
            staged_ui_digest = _sidecar_ui_digest(staged_sidecar)
            if staged_ui_digest != expected.ui_digest:
                raise WorkflowBundleError("staged sidecar digest differs from intended bundle")

        # A backup makes a failure after either visible replacement recoverable.
        for _, destination in staged:
            if destination.exists():
                fd, raw_backup = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".bak", dir=str(path.parent))
                os.close(fd)
                backup = Path(raw_backup)
                backup_paths.append(backup)
                shutil.copy2(destination, backup)
                backup_contents[destination] = destination.read_bytes()
                backups.append((backup, destination))
        # Compare all original bundle members after potentially slow staging
        # and backup work, immediately before making any replacement visible.
        # A missing member is represented by ``None`` so first publication
        # into an output location cannot silently overwrite an existing file.
        if expected_members is not None:
            for raw_member, expected_digest in expected_members.items():
                member = Path(raw_member)
                try:
                    payload = member.read_bytes()
                except FileNotFoundError:
                    actual_digest = None
                except OSError as exc:
                    raise WorkflowBundleError(
                        f"could not recheck workflow bundle member {member}: {exc}"
                    ) from exc
                else:
                    actual_digest = hashlib.sha256(payload).hexdigest()
                if actual_digest != expected_digest:
                    raise WorkflowBundleError(
                        f"workflow bundle changed before publication: {member}; "
                        "reload it or choose an explicit --out destination"
                    )
        for temporary, destination in staged:
            os.replace(temporary, destination)
            replaced.add(destination)
        cleanup_errors = cleanup([temporary for temporary, _ in staged] + backup_paths)
        if cleanup_errors:
            raise WorkflowBundleError(f"publication cleanup failed: {'; '.join(cleanup_errors)}")
    except BaseException as exc:
        rollback(exc)
        raise


def capture_bundle(
    ui_graph: Mapping[str, Any] | VibeWorkflow,
    destination: str | Path,
    provenance: Any,
    parent_revision: str = "",
    parent_evidence: Mapping[str, Any] | None = None,
    *,
    schema_provider: Any = None,
) -> WorkflowBundle:
    """Convert a captured UI/API graph into a candidate canonical revision.

    ``schema_provider`` is capture-time authority, not a compile-time fallback.
    Callers that already froze schema evidence may supply that provider so the
    emitted canonical source retains resolved-node requirements and provenance.
    """
    if isinstance(ui_graph, VibeWorkflow):
        workflow = ui_graph
        candidate: Mapping[str, Any] | None = None
    elif isinstance(ui_graph, Mapping):
        # The provisional path is only used to pass the source location to
        # the compatibility importer; the imported workflow id is authoritative.
        destination_path = Path(destination)
        if destination_path.suffix.lower() != ".py":
            destination_path = destination_path / "capture.py"
        from vibecomfy.ingest.normalize import door_import_source_kind

        source_kind = door_import_source_kind(ui_graph)
        declared = _import_identity(ui_graph, source_kind=source_kind)
        from vibecomfy.ingest.normalize import _named_import

        import_payload = dict(ui_graph)
        # Identity is a capture envelope, not part of the API graph shape.
        import_payload.pop("workflow_id", None)
        import_payload.pop("workflow_identity", None)
        workflow = _named_import(
            import_payload,
            source_path=str(destination_path),
            workflow_id=declared,
            schema_provider=schema_provider,
        )
        # API-shaped captures carry semantics only; their identity envelope is
        # not presentation and must not be fed to the sidecar converter.
        candidate = ui_graph if source_kind in {"ui", "envelope"} else None
    else:
        raise TypeError(f"capture_bundle requires a UI mapping, got {type(ui_graph).__name__}")
    return emit_bundle_with_candidate(
        workflow,
        destination,
        provenance,
        candidate,
        parent_revision=parent_revision,
        parent_evidence=parent_evidence,
        operation="captured",
    )


def _generated_metadata_expressions(
    source: bytes,
) -> tuple[dict[str, ast.AST], dict[str, Any]]:
    """Find the generated READY_METADATA fields that bind a published pair."""
    try:
        module = ast.parse(source)
    except (SyntaxError, ValueError, UnicodeError) as exc:
        raise WorkflowBundleError(f"Python source cannot be parsed safely: {exc}") from exc

    assignments: list[ast.AST] = []
    for statement in module.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == "READY_METADATA" for target in targets):
            assignments.append(statement)
    if len(assignments) != 1:
        raise WorkflowBundleError(
            "expected exactly one generated READY_METADATA assignment"
        )
    assignment = assignments[0]
    value = assignment.value
    if not isinstance(value, ast.Call):
        raise WorkflowBundleError("READY_METADATA is not a generated metadata call")
    function = value.func
    if not (
        isinstance(function, ast.Attribute)
        and function.attr == "build"
        and isinstance(function.value, ast.Name)
        and function.value.id == "ReadyMetadata"
    ):
        raise WorkflowBundleError("READY_METADATA is not built by ReadyMetadata.build")
    expressions: dict[str, ast.AST] = {}
    values: dict[str, Any] = {}
    for name in ("operation", "provenance", "source_bundle"):
        matches = [keyword.value for keyword in value.keywords if keyword.arg == name]
        if len(matches) != 1:
            raise WorkflowBundleError(f"READY_METADATA must contain one {name} field")
        expressions[name] = matches[0]
        try:
            values[name] = ast.literal_eval(matches[0])
        except (ValueError, TypeError, SyntaxError) as exc:
            raise WorkflowBundleError(f"READY_METADATA {name} field is not a literal") from exc
    if not isinstance(values["operation"], str) or values["operation"] not in _OPERATIONS:
        raise WorkflowBundleError("READY_METADATA operation field is invalid")
    if not isinstance(values["provenance"], Mapping):
        raise WorkflowBundleError("READY_METADATA provenance field is not an object")
    try:
        values["source_bundle"] = _validate_v2_marker(values["source_bundle"])
    except WorkflowBundleError as exc:
        raise WorkflowBundleError(f"source_bundle marker is invalid: {exc}") from exc
    return expressions, values


def _preserve_python_source_with_marker(
    original_source: bytes,
    canonical_source: str,
) -> bytes:
    """Keep captured Python bytes, replacing only the generated v2 marker.

    Direct capture executes source under the normal confirmation boundary, but
    the VibeWorkflow model cannot represent extra user-authored Python. A
    capture therefore retains the original program and updates only the
    custody marker that binds it to the newly published companion. The caller
    publishes the returned bytes through the regular staged pair validator.
    """
    try:
        original_expressions, _old_values = _generated_metadata_expressions(original_source)
        canonical_bytes = canonical_source.encode("utf-8")
        canonical_expressions, _new_values = _generated_metadata_expressions(canonical_bytes)
    except WorkflowBundleError as exc:
        raise WorkflowBundleError(
            f"cannot preserve direct Python capture safely: {exc}"
        ) from exc

    def span(source: bytes, expression: ast.AST) -> tuple[int, int]:
        if (
            expression.lineno is None
            or expression.end_lineno is None
            or expression.end_col_offset is None
        ):
            raise WorkflowBundleError("source_bundle marker has no complete source span")
        lines = source.splitlines(keepends=True)
        start = sum(len(line) for line in lines[: expression.lineno - 1]) + expression.col_offset
        end = sum(len(line) for line in lines[: expression.end_lineno - 1]) + expression.end_col_offset
        if start < 0 or end < start or end > len(source):
            raise WorkflowBundleError("source_bundle marker span is outside the Python source")
        return start, end

    replacements: list[tuple[int, int, bytes]] = []
    for name in ("operation", "provenance", "source_bundle"):
        old_start, old_end = span(original_source, original_expressions[name])
        new_start, new_end = span(canonical_bytes, canonical_expressions[name])
        replacement = canonical_bytes[new_start:new_end]
        if not replacement.isascii():
            raise WorkflowBundleError(
                f"canonical READY_METADATA {name} field is not ASCII"
            )
        replacements.append((old_start, old_end, replacement))
    result = original_source
    for start, end, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def emit_bundle_with_candidate(
    workflow: VibeWorkflow,
    destination: str | Path,
    provenance: Any,
    candidate: Mapping[str, Any] | None,
    *,
    parent_revision: str = "",
    parent_evidence: Mapping[str, Any] | None = None,
    operation: str = "authored",
    source_provenance: Mapping[str, Any] | None = None,
    source_format: str = "scratchpad",
    expected_members: Mapping[str | Path, str | None] | None = None,
    extra_members: Mapping[str | Path, bytes] | None = None,
    preserved_python_source: bytes | None = None,
    preserve_authored_graph: bool = False,
) -> WorkflowBundle:
    """Internal shared writer for emit/capture candidate bundles.

    ``source_format`` only selects the existing canonical renderer.  Pair
    construction, custody, validation, and publication stay shared.
    """
    if source_format not in {"scratchpad", "ready_template"}:
        raise ValueError(f"unsupported canonical source format {source_format!r}")
    path = _destination_path(destination, workflow)
    # A UI candidate is the only source-backed witness available to bridge the
    # temporary generated-Python ids back to the captured graph.  Perform the
    # bridge before projecting the candidate into presentation storage so the
    # same durable ids feed custody, layout, and export.
    workflow = _apply_candidate_node_identity(workflow, candidate)
    existing_candidate = (
        _ui_candidate_sidecar(workflow, candidate)
        if candidate is not None and candidate.get("format_version") != 2
        else candidate
        if candidate is not None
        else _read_sidecar(path)
    )
    workflow, existing_candidate = _canonicalize_for_v2_pair(
        workflow,
        existing_candidate,
        path=path,
        provenance=provenance,
        operation=operation,
        parent_revision=parent_revision,
        preserve_authored_graph=preserve_authored_graph,
    )
    sidecar = _build_v2_sidecar(
        workflow,
        existing_candidate,
        provenance=provenance,
        operation=operation,
        parent_revision=parent_revision,
        preserve_authored_graph=preserve_authored_graph,
    )
    bundle = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=sidecar,
        provenance=provenance,
        operation=operation,
        parent_revision=parent_revision,
        parent_evidence=parent_evidence,
    )
    from vibecomfy.porting.emit import emit_scratchpad_python

    path.parent.mkdir(parents=True, exist_ok=True)
    emitted_workflow = workflow.copy()
    emitted_workflow.metadata["source_bundle"] = _v2_marker(sidecar)
    if source_format == "ready_template":
        from vibecomfy.porting.convert import _ready_requirements
        from vibecomfy.porting.emit.emit_ready import emit_ready_template_python

        # Ready promotion uses the namespaced id as the published workflow
        # identity. Keep the source workflow id as upstream provenance while
        # aligning the compatibility projection that ReadyMetadata.build()
        # exposes at both the root and nested provenance levels.
        ready_metadata = dict(emitted_workflow.metadata)
        previous_template_id = ready_metadata.get("ready_template")
        if ready_metadata.get("output_prefix") in {
            previous_template_id,
            emitted_workflow.id,
        }:
            ready_metadata["output_prefix"] = emitted_workflow.id
        ready_provenance = ready_metadata.get("provenance")
        if isinstance(ready_provenance, Mapping):
            ready_provenance = dict(ready_provenance)
            ready_id = ready_provenance.get("ready_id")
            if ready_id is None and isinstance(source_provenance, Mapping):
                ready_id = source_provenance.get("ready_id")
            ready_provenance["source_id"] = emitted_workflow.id
            if ready_id is not None:
                ready_provenance["ready_id"] = str(ready_id)
            ready_metadata["provenance"] = ready_provenance
            # ReadyMetadata.build() also publishes provenance fields at the
            # metadata root for legacy consumers. Keep that compatibility
            # projection aligned with the v2 pair identity.
            ready_metadata["source_id"] = emitted_workflow.id
            if ready_id is not None:
                ready_metadata["ready_id"] = str(ready_id)

        source = emit_ready_template_python(
            emitted_workflow,
            ready_metadata=ready_metadata,
            ready_requirements=_ready_requirements(emitted_workflow),
            template_id=str(
                emitted_workflow.metadata.get("ready_template") or emitted_workflow.id
            ),
            registered_inputs={
                str(name): (str(item.node_id), str(item.field))
                for name, item in emitted_workflow.inputs.items()
            },
            external_custody=True,
            preserve_node_ids=preserve_authored_graph,
            preserve_authored_graph=preserve_authored_graph,
        )
    else:
        source = emit_scratchpad_python(
            emitted_workflow,
            workflow_id=workflow.id,
            source_path=str(path),
            provenance=_source_provenance(source_provenance or bundle.provenance),
            external_custody=True,
            preserve_node_ids=preserve_authored_graph,
            preserve_authored_graph=preserve_authored_graph,
        )
    if preserved_python_source is not None:
        source = _preserve_python_source_with_marker(preserved_python_source, source)
    _atomic_publish_pair(
        path,
        source,
        bundle.ui_sidecar,
        expected=bundle,
        expected_members=expected_members,
        extra_members=extra_members,
    )
    return bundle


__all__ = [
    "ApprovedProjectionRecord",
    "WorkflowBundle",
    "WorkflowBundleError",
    "capture_bundle",
    "emit_bundle",
    "filter_provenance",
    "load_bundle",
    "materialize_ui_json",
    "validate_sidecar",
]
