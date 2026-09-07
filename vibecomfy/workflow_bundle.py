"""Canonical workflow source bundles.

This module is deliberately a small binding around :class:`VibeWorkflow`.
The workflow remains the only semantic authority; a bundle only records where
it was loaded from, the optional presentation candidate, and deterministic
digests for that candidate revision.  In particular, this is not an approval
or execution registry.
"""

from __future__ import annotations

import copy
import json
import math
import os
import shlex
import shutil
import tempfile
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
    quoted_output = shlex.quote(f"out/scratchpads/{stem}.py")
    return WorkflowAuthorityError(
        f"{action} requires canonical Python workflow authority; raw UI/API JSON "
        "is import evidence only. "
        f"First: vibecomfy port check {quoted_source} --json. "
        f"Then: vibecomfy port convert {quoted_source} --out {quoted_output}"
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
_NODE_KEYS = frozenset({"id", "pos", "size", "collapsed", "color", "bgcolor", "title", "z_order", "group"})
_LINK_KEYS = frozenset({"edge_ref", "virtual_wire_ref", "occurrence_index", "id", "reroute"})
_EDGE_REF_KEYS = frozenset({"scope_path", "from_uid", "from_port", "to_uid", "to_port"})
_VIRTUAL_REF_KEYS = frozenset({"scope_path", "name", "leg_index"})
_GROUP_KEYS = frozenset({"scope_path", "presentation_id", "bounds", "title", "color", "z_order"})
_CANVAS_KEYS = frozenset({"zoom", "pan"})


def _closed_keys(value: Mapping[str, Any], allowed: frozenset[str], where: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise WorkflowBundleError(f"{where} contains unknown field(s): {', '.join(unknown)}")


def _integer(value: Any, where: str, *, nonnegative: bool = False) -> int:
    if type(value) is not int or (nonnegative and value < 0):
        suffix = " non-negative" if nonnegative else ""
        raise WorkflowBundleError(f"{where} must be a{suffix} integer")
    return value


def _pair(value: Any, where: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise WorkflowBundleError(f"{where} must contain exactly two numeric values")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in value):
        raise WorkflowBundleError(f"{where} must contain exactly two numeric values")
    result = [float(x) for x in value]
    if any(not math.isfinite(x) for x in result):
        raise WorkflowBundleError(f"{where} must contain finite numeric values")
    return result


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


def validate_sidecar(sidecar: Any, workflow: VibeWorkflow) -> dict[str, Any]:
    """Validate and canonically normalize one strict ``.vibe.json`` object."""
    if not isinstance(sidecar, Mapping):
        raise WorkflowBundleError("workflow sidecar must contain a JSON object")
    try:
        projection = canonical_ir_projection(workflow)
    except (TypeError, ValueError, KeyError) as exc:
        raise WorkflowBundleError(f"Python semantic projection is invalid: {exc}") from exc
    semantic_digest = canonical_digest(projection)
    _closed_keys(sidecar, _SIDECAR_KEYS, "workflow sidecar")
    if set(sidecar) != _SIDECAR_KEYS:
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
    if bind["semantic_digest"] != semantic_digest:
        raise WorkflowBundleError("workflow sidecar semantic digest does not match Python semantic digest")
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
        if uid not in workflow_uids:
            raise WorkflowBundleError(f"workflow sidecar node {uid!r} does not match a Python node")
        if not isinstance(entry, Mapping):
            raise WorkflowBundleError(f"workflow sidecar node {uid!r} must be an object")
        _closed_keys(entry, _NODE_KEYS, f"workflow sidecar node {uid!r}")
        out = dict(entry)
        if "id" in out:
            native_id = _integer(out["id"], f"node {uid} id")
            node_scope, _ = parse_uid(uid)
            native_key = (node_scope, native_id)
            if native_key in native_node_ids: raise WorkflowBundleError(f"duplicate native node id {native_key!r}")
            native_node_ids.add(native_key)
        for field in ("pos", "size"):
            if field in out: out[field] = _pair(out[field], f"node {uid} {field}")
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
    return {"format_version": 1, "bind": dict(bind), "nodes": canonical_nodes, "links": canonical_links, "groups": canonical_groups, "canvas": dict(canvas)}


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
            f"run `vibecomfy port convert {path.with_suffix('.json')} --out {path}` "
            "to migrate its presentation fields to the same-basename .vibe.json"
        )
    candidate = _sidecar_path(path)
    if not candidate.is_file():
        return None
    try:
        raw = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WorkflowBundleError(f"could not read workflow sidecar {candidate}: {exc}") from exc
    if not isinstance(raw, dict):
        raise WorkflowBundleError("workflow sidecar must contain a JSON object")
    return raw


def _ui_candidate_sidecar(workflow: VibeWorkflow, candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a captured UI envelope into presentation-only sidecar data."""
    if set(candidate) >= _SIDECAR_KEYS:
        return dict(candidate)
    from vibecomfy.porting.emit.ui import capture_presentation_graph_records

    presentation = capture_presentation_graph_records(candidate)
    raw_nodes = presentation.nodes
    if not isinstance(raw_nodes, list):
        raise WorkflowBundleError("captured candidate is not a strict sidecar or LiteGraph UI envelope")
    ids: dict[str, str] = {}
    nodes: dict[str, Any] = {}
    workflow_by_id = {str(key): node for key, node in workflow.nodes.items()}
    workflow_by_uid = {str(node.uid): node for node in workflow.nodes.values() if node.uid}
    from vibecomfy.porting.emit.emit_prepare import _schema_status_from_node

    standard_properties = {
        "vibecomfy_uid", "vibecomfy_id", "Node name for S&R", "cnr_id",
        "aux_id", "ver", "_vibecomfy_schema_provider", "vibecomfy",
    }
    raw_groups = presentation.groups if presentation.groups_present else []
    if not isinstance(raw_groups, list):
        raise WorkflowBundleError("captured groups must be a list")
    group_for_node: dict[str, str] = {}
    for group in raw_groups:
        if not isinstance(group, Mapping):
            raise WorkflowBundleError("captured group is malformed")
        group_id = group.get("vibecomfy_group_id", group.get("id"))
        if group_id is None:
            raise WorkflowBundleError("captured group has no stable presentation id")
        members = group.get("nodes", [])
        if not isinstance(members, list):
            raise WorkflowBundleError("captured group nodes must be a list")
        for member in members:
            member_key = str(member)
            prior = group_for_node.get(member_key)
            if prior is not None and prior != str(group_id):
                raise WorkflowBundleError(f"captured node {member_key!r} has ambiguous group membership")
            group_for_node[member_key] = str(group_id)
    for node in raw_nodes:
        if not isinstance(node, Mapping) or type(node.get("id")) is not int:
            raise WorkflowBundleError("captured node must contain an integer native id")
        properties = node.get("properties")
        if "properties" in node and not isinstance(properties, Mapping):
            raise WorkflowBundleError("captured node properties must be a mapping")
        native_id = str(node["id"])
        if native_id in ids:
            raise WorkflowBundleError(f"duplicate captured native node id {native_id}")
        explicit_uid = properties.get("vibecomfy_uid") if isinstance(properties, Mapping) else None
        owner = workflow_by_uid.get(explicit_uid) if isinstance(explicit_uid, str) else None
        if explicit_uid is None:
            owner = workflow_by_id.get(native_id)
        if owner is None or not owner.uid:
            raise WorkflowBundleError(f"captured node {native_id!r} cannot be mapped to one Python node")
        uid = str(owner.uid)
        if uid in nodes:
            raise WorkflowBundleError(f"duplicate captured node UID {uid!r}")
        ids[native_id] = uid
        if isinstance(properties, Mapping):
            unknown_properties = set(properties) - standard_properties
            if _schema_status_from_node(owner) != "unknown" and unknown_properties:
                keys = ", ".join(sorted(str(key) for key in unknown_properties))
                raise WorkflowBundleError(f"known node {uid!r} property {keys!r} is unclassified; reconcile the node metadata")
            if properties.get("rejected"):
                raise WorkflowBundleError(f"known node {uid!r} contains rejected metadata; reconcile the node metadata")
        entry: dict[str, Any] = {}
        for key in ("id", "pos", "size", "color", "bgcolor", "title"):
            if key not in node:
                continue
            value = node[key]
            if key in {"color", "bgcolor", "title"} and not isinstance(value, str):
                continue
            entry[key] = copy.deepcopy(value)
        if "order" in node:
            entry["z_order"] = copy.deepcopy(node["order"])
        elif "z_order" in node:
            entry["z_order"] = copy.deepcopy(node["z_order"])
        flags = node.get("flags")
        if isinstance(flags, Mapping) and "collapsed" in flags:
            entry["collapsed"] = flags["collapsed"]
        elif "collapsed" in node:
            entry["collapsed"] = node["collapsed"]
        group = group_for_node.get(native_id)
        if group is not None:
            entry["group"] = str(group)
        nodes[uid] = entry
    links: list[dict[str, Any]] = []
    for link in presentation.links if isinstance(presentation.links, list) else ():
        if isinstance(link, Mapping):
            allowed_link = {"id", "origin_id", "origin_slot", "target_id", "target_slot", "type", "reroute"}
            unknown_link = set(link) - allowed_link
            if unknown_link:
                raise WorkflowBundleError(f"captured link contains unsupported field(s): {', '.join(sorted(str(key) for key in unknown_link))}")
            if type(link.get("id")) is not int:
                raise WorkflowBundleError("captured link must contain an integer native id")
            if "reroute" in link:
                raise WorkflowBundleError("captured link reroute geometry is unsupported; use a Reroute node")
            link = [link["id"], link.get("origin_id"), link.get("origin_slot"), link.get("target_id"), link.get("target_slot"), link.get("type", "")]
        if not isinstance(link, (list, tuple)) or len(link) not in (5, 6):
            raise WorkflowBundleError("captured link is malformed")
        if type(link[0]) is not int:
            raise WorkflowBundleError("captured link must contain an integer native id")
        if len(link) > 5 and not isinstance(link[5], str):
            raise WorkflowBundleError("captured link sixth member is not a supported presentation field")
        source, target = ids.get(str(link[1])), ids.get(str(link[3]))
        if source is None or target is None:
            raise WorkflowBundleError("captured link endpoint does not match a captured node")
        ref = {"scope_path": "", "from_uid": source, "from_port": link[2], "to_uid": target, "to_port": link[4]}
        item: dict[str, Any] = {
            "edge_ref": ref,
            "occurrence_index": sum(1 for prior in links if prior["edge_ref"] == ref),
        }
        item["id"] = link[0]
        links.append(item)
    groups: list[dict[str, Any]] = []
    for group_index, group in enumerate(raw_groups):
        if not isinstance(group, Mapping):
            raise WorkflowBundleError("captured group is malformed")
        presentation_id = group.get("presentation_id", group.get("vibecomfy_group_id", group.get("id")))
        if presentation_id is None:
            raise WorkflowBundleError("captured group has no stable presentation id")
        item = {"scope_path": str(group.get("scope_path", "")), "presentation_id": str(presentation_id)}
        bounds = group.get("bounds", group.get("bounding"))
        if bounds is not None:
            item["bounds"] = copy.deepcopy(bounds)
        for key in ("title", "color"):
            if key not in group:
                continue
            value = group[key]
            if not isinstance(value, str):
                continue
            item[key] = copy.deepcopy(value)
        item["z_order"] = copy.deepcopy(group.get("order", group.get("z_order", group_index)))
        groups.append(item)
    canvas: dict[str, Any] = {}
    raw_canvas = candidate.get("canvas")
    if isinstance(raw_canvas, Mapping):
        for key in ("zoom", "pan"):
            if key in raw_canvas:
                canvas[key] = copy.deepcopy(raw_canvas[key])
    extra = candidate.get("extra")
    ds = extra.get("ds") if isinstance(extra, Mapping) else None
    if isinstance(ds, Mapping):
        canvas.setdefault("zoom", ds.get("scale"))
        canvas.setdefault("pan", ds.get("offset"))
    return {
        "format_version": 1,
        "bind": {"workflow_identity": workflow.id, "semantic_digest": workflow.semantic_digest()},
        "nodes": nodes,
        "links": links,
        "groups": groups,
        "canvas": canvas,
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


def _approval_preconditions(workflow: VibeWorkflow, schema_provider: Any) -> None:
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
        from vibecomfy.fetch import is_present
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
            if not isinstance(value, str):
                raise WorkflowBundleError("workflow requirements.models contains a malformed entry")
            add_reference(value)
        if not references:
            return
        registry = load_registry()
        for reference in references:
            value = reference.get("value")
            subdir = reference.get("subdir")
            entry = resolve_model_entry(value, registry=registry, subdir=subdir or None)
            if entry is None:
                raise WorkflowBundleError(f"model reference is not locally registered: {value}")
            effective_subdir = subdir
            if not effective_subdir and entry.targets:
                target_path = str(entry.targets[0].path).replace("\\", "/")
                effective_subdir = target_path.rsplit("/", 1)[0] if "/" in target_path else ""
            if not effective_subdir:
                raise WorkflowBundleError(f"model reference has no deterministic local target: {value}")
            root = None
            if isinstance(metadata, Mapping) and metadata.get("models_root") is not None:
                raw_root = metadata["models_root"]
                if not isinstance(raw_root, (str, Path)) or not Path(raw_root).is_absolute():
                    raise WorkflowBundleError("workflow models_root must be an absolute path")
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
        _approval_preconditions(self.workflow, schema_provider)
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
    from vibecomfy.porting.emit.ui import materialize_ui_json as _materialize_ui_json

    return _materialize_ui_json(
        workflow,
        validated,
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
    ui_digest = canonical_digest(sidecar) if sidecar is not None else ""
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


def _resolve_reference(reference: str | Path) -> tuple[str | Path, Path | None, str]:
    value = Path(reference) if isinstance(reference, Path) else Path(str(reference))
    if value.suffix.lower() == ".vibe.json":
        python = value.with_suffix("").with_suffix(".py")
        return python, python if python.is_file() else None, "authored"
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
    bundle = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=existing_sidecar,
        provenance=provenance,
        operation="authored",
        parent_revision=parent_revision,
    )
    from vibecomfy.porting.emit import emit_scratchpad_python

    path.parent.mkdir(parents=True, exist_ok=True)
    source = emit_scratchpad_python(
        workflow,
        workflow_id=workflow.id,
        source_path=str(path),
        provenance=dict(bundle.provenance),
    )
    _atomic_publish_pair(path, source, bundle.ui_sidecar, expected=bundle)
    return bundle


def _atomic_publish_pair(
    path: Path,
    source: str,
    sidecar: Mapping[str, Any] | None,
    *,
    expected: WorkflowBundle | None = None,
) -> None:
    """Validate staged bytes, then publish a complete pair with explicit rollback."""
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
        members = [(path, source)]
        if sidecar is not None:
            members.append((_sidecar_path(path), canonical_json(sidecar)))
        for destination, payload in members:
            fd, raw_tmp = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=destination.suffix or ".tmp", dir=str(path.parent))
            temporary = Path(raw_tmp)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
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

            staged_workflow = load_scratchpad(staged[0][0], provenance_override=Provenance.USER_CONFIRMED)
            staged_semantic = staged_workflow.semantic_digest()
            if staged_workflow.id != expected.workflow.id or staged_semantic != expected.semantic_digest:
                raise WorkflowBundleError("staged Python identity or semantic digest differs from intended bundle")
            staged_sidecar_payload = None
            if sidecar is not None:
                staged_sidecar_path = next(item for item, destination in staged if destination == _sidecar_path(path))
                try:
                    staged_sidecar_payload = json.loads(staged_sidecar_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as load_exc:
                    raise WorkflowBundleError(f"could not read staged workflow sidecar: {load_exc}") from load_exc
            staged_sidecar = validate_sidecar(staged_sidecar_payload, staged_workflow) if sidecar is not None else None
            staged_ui_digest = canonical_digest(staged_sidecar) if staged_sidecar is not None else ""
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


def emit_bundle_with_candidate(
    workflow: VibeWorkflow,
    destination: str | Path,
    provenance: Any,
    candidate: Mapping[str, Any] | None,
    *,
    parent_revision: str = "",
    parent_evidence: Mapping[str, Any] | None = None,
    operation: str = "authored",
) -> WorkflowBundle:
    """Internal shared writer for emit/capture candidate bundles."""
    path = _destination_path(destination, workflow)
    candidate = _ui_candidate_sidecar(workflow, candidate) if candidate is not None else _read_sidecar(path)
    bundle = _make_bundle(
        workflow,
        python_path=path,
        ui_sidecar=candidate,
        provenance=provenance,
        operation=operation,
        parent_revision=parent_revision,
        parent_evidence=parent_evidence,
    )
    from vibecomfy.porting.emit import emit_scratchpad_python

    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_publish_pair(
        path,
        emit_scratchpad_python(
            workflow,
            workflow_id=workflow.id,
            source_path=str(path),
            provenance=dict(bundle.provenance),
        ),
        bundle.ui_sidecar,
        expected=bundle,
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
