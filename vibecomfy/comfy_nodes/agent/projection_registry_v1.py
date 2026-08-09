"""M1 typed graph authority contracts.

This is the Python semantic owner for projection, field, identity, root-scope,
prepared-authority, durable-undo, and legacy migration contracts.  V1 candidate
records remain historical/read-only; new authority is candidate_transaction_v2.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

# Shared canonical-hash identity lives in the zero-dependency leaf
# ``_canonical_contract_primitives``.  These symbols are relocated *verbatim*
# (no logic change) and re-exported here with identical identity so every
# existing ``from projection_registry_v1 import ...`` caller resolves to the
# same objects.  The new cross-language contract modules
# (``layout_operation_v1``, ``mutation_materialization_v1``) import the leaf
# directly to avoid the import cycle that would otherwise form between those
# modules and this registry's common authority validator.
from ._canonical_contract_primitives import (
    ContractError,
    _compare_utf16_keys,
    _hash,
    _order_json_objects_utf16,
    canonical_json,
    canonical_json_bytes_v1,
    canonicalize_contract_numeric,
)
# One-way dependency: the registry imports the cross-language contract modules
# (they import only the zero-dependency leaf), so there is no import cycle.  The
# common authority validator calls their assert_* entrypoints directly.
from .layout_operation_v1 import assert_layout_operation_envelope
from .mutation_materialization_v1 import (
    assert_mutation_materialization_envelope,
)

PROJECTION_REGISTRY_V1 = "projection_registry_v1"
FIELD_REGISTRY_V1 = "field_registry_v1"
IDENTITY_CONTRACT_V1 = "identity_contract_v1"
ROOT_SCOPE_V1 = "root_scope_v1"
PREPARED_AUTHORITY_V1 = "prepared_authority_v1"
CANDIDATE_AUTHORITY_V1 = "candidate_authority_v1"
JOURNAL_DURABLE_V1 = "journal_durable_v1"
CANDIDATE_TRANSACTION_V2 = "candidate_transaction_v2"
DELTA_V1 = "delta_v1"
DELTA_WIRE_VERSION = "2.0.0"
AUTHORITY_RECEIPT_CONTRACT_VERSION = "authority_receipt_v2"
ROOT_SCOPE = MappingProxyType({"kind": "root", "path": ""})
FIELD_CATEGORIES = frozenset({"execution_semantic", "layout_semantic", "native_defaulted", "derived_native", "opaque_extension", "unsupported"})
_RULES = MappingProxyType({
    "node.vibecomfy_uid": "derived_native", "node.id": "derived_native", "node.type": "execution_semantic", "node.mode": "native_defaulted", "node.fields": "execution_semantic", "node.widgets_values": "execution_semantic", "node.inputs": "derived_native", "node.outputs": "derived_native", "node.properties": "derived_native", "node.flags": "derived_native", "node.order": "derived_native", "node.showAdvanced": "derived_native", "node.pos": "layout_semantic", "node.size": "layout_semantic", "node.title": "layout_semantic", "node.color": "layout_semantic", "node.bgcolor": "layout_semantic", "node.boxcolor": "layout_semantic", "node.shape": "layout_semantic", "node.extensions": "opaque_extension",
    "group.vibecomfy_group_id": "derived_native", "group.id": "derived_native", "group.scope_path": "derived_native", "group.flags": "derived_native", "group.font_size": "layout_semantic", "group.title": "layout_semantic", "group.bounding": "layout_semantic", "group.color": "layout_semantic", "group.nodes": "layout_semantic",
})
PROJECTIONS_V1 = MappingProxyType({"structural_v1": MappingProxyType({"allowed": True}), "layout_v1": MappingProxyType({"allowed": True}), "workflow_v1": MappingProxyType({"allowed": False, "reason": "forbidden_forward_agent_edit"})})
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def field_category_v1(entity: str, path: str, node_type: str | None = None) -> str:
    if entity == "node" and node_type == "vibecomfy.exec" and path == "widgets_values.io": return "derived_native"
    # LoadImage has one backend-semantic input. ``image_upload`` metadata adds
    # auxiliary frontend widget values during native node construction; those
    # browser carriers are not part of typed workflow authority.
    if entity == "node" and node_type == "LoadImage" and re.fullmatch(r"widgets_values\.[1-9]\d*", path): return "derived_native"
    return _RULES.get(f"{entity}.{path}", "unsupported")

def _supported(entity: str, value: Any, node_type: str | None = None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ContractError(f"{entity} must be an object", "malformed_graph")
    for key in value:
        if field_category_v1(entity, str(key), node_type) == "unsupported": raise ContractError(f"Unsupported {entity} field {key}", "unsupported_field")
    return value

def assert_root_scope_v1(scope: Any) -> Mapping[str, str]:
    if not isinstance(scope, Mapping) or dict(scope) != dict(ROOT_SCOPE): raise ContractError("Only root_scope_v1 is supported", "unsupported_scope")
    return ROOT_SCOPE

def assert_root_graph_v1(graph: Any) -> Mapping[str, Any]:
    if not isinstance(graph, Mapping): raise ContractError("graph must be an object", "malformed_graph")
    definitions = graph.get("definitions")
    if isinstance(definitions, Mapping) and definitions: raise ContractError("Definitions/subgraphs are unsupported", "unsupported_scope")
    for group in graph.get("groups", ()) if isinstance(graph.get("groups", ()), Sequence) else ():
        if isinstance(group, Mapping) and str(group.get("scope_path", "")) != "": raise ContractError("Nested group scope is unsupported", "unsupported_scope")
    return graph

def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value: raise ContractError(f"Missing stable {name}", "missing_identity")
    return value

def workflow_identity_v1(value: Any) -> str:
    if not isinstance(value, str) or not _UUID.fullmatch(value): raise ContractError("workflow_id must be a stable Comfy workflow UUID", "invalid_workflow_identity")
    return value

def node_identity_v1(node: Mapping[str, Any]) -> str:
    properties = node.get("properties")
    nested = properties.get("vibecomfy_uid") if isinstance(properties, Mapping) else None
    return _required(node.get("vibecomfy_uid") if node.get("vibecomfy_uid") is not None else nested, "node vibecomfy_uid")


def group_identity_v1(group: Mapping[str, Any]) -> str:
    value = group.get("vibecomfy_group_id")
    return _required(value if value is not None else group.get("id"), "group stable id")
def issued_identity_v1(value: Any, kind: str) -> str: return _required(value, kind)

def _link_identity(link: Any) -> dict[str, Any]:
    if not isinstance(link, Mapping): raise ContractError("link must be an object", "malformed_link")
    source, target = link.get("from"), link.get("to")
    if not isinstance(source, Mapping) or not isinstance(target, Mapping): raise ContractError("link endpoints are required", "malformed_link")
    return {"from": {"node_uid": _required(source.get("node_uid"), "link source node"), "port": _required(source.get("port"), "link source port")}, "to": {"node_uid": _required(target.get("node_uid"), "link target node"), "port": _required(target.get("port"), "link target port")}}


def _native_port_name(node: Mapping[str, Any], direction: str, slot: Any) -> str:
    sockets = node.get("outputs") if direction == "from" else node.get("inputs")
    if not isinstance(slot, int) or not isinstance(sockets, list) or slot < 0 or slot >= len(sockets):
        return _required(None, f"link {direction} port")
    socket = sockets[slot]
    return _required(socket.get("name") if isinstance(socket, Mapping) else None, f"link {direction} port")


def _graph_link_identities(graph: Mapping[str, Any], nodes: list[Any]) -> list[dict[str, Any]]:
    by_native_id = {
        str(node.get("id")): node
        for node in nodes
        if isinstance(node, Mapping) and node.get("id") is not None
    }
    result: list[dict[str, Any]] = []
    for link in graph.get("links", []) if isinstance(graph.get("links"), list) else []:
        if isinstance(link, Mapping) and isinstance(link.get("from"), Mapping) and isinstance(link.get("to"), Mapping):
            result.append(_link_identity(link))
            continue
        if isinstance(link, list) and len(link) == 6:
            _, origin_id, origin_slot, target_id, target_slot, _ = link
        elif isinstance(link, Mapping):
            origin_id, origin_slot = link.get("origin_id"), link.get("origin_slot")
            target_id, target_slot = link.get("target_id"), link.get("target_slot")
        else:
            raise ContractError("link must be a stable endpoint object or native six-tuple", "malformed_link")
        origin = by_native_id.get(str(origin_id))
        target = by_native_id.get(str(target_id))
        if not isinstance(origin, Mapping) or not isinstance(target, Mapping):
            raise ContractError("native link endpoint cannot be resolved", "malformed_link")
        result.append({
            "from": {"node_uid": node_identity_v1(origin), "port": _native_port_name(origin, "from", origin_slot)},
            "to": {"node_uid": node_identity_v1(target), "port": _native_port_name(target, "to", target_slot)},
        })
    return result

def projection_spec_v1(name: Any) -> Mapping[str, Any]:
    if not isinstance(name, str) or name not in PROJECTIONS_V1: raise ContractError("Unknown projection version", "unknown_projection_version")
    return PROJECTIONS_V1[name]

def assert_forward_projection_v1(name: Any) -> Mapping[str, Any]:
    spec = projection_spec_v1(name)
    if not spec["allowed"]: raise ContractError("workflow_v1 is forbidden for forward Agent Edit", "forbidden_projection")
    return spec

def _widgets(node: Mapping[str, Any]) -> Any:
    raw = node.get("widgets_values", {})
    if isinstance(raw, list):
        values = [
            value for index, value in enumerate(raw)
            if field_category_v1("node", f"widgets_values.{index}", node.get("type") if isinstance(node.get("type"), str) else None) != "derived_native"
        ]
        return values if values else {}
    if raw is None: return {}
    if not isinstance(raw, Mapping): raise ContractError("widgets_values must be object or list", "malformed_graph")
    result = dict(raw)
    if field_category_v1("node", "widgets_values.io", node.get("type") if isinstance(node.get("type"), str) else None) == "derived_native": result.pop("io", None)
    return result

def _sort(values: list[Any]) -> list[Any]: return sorted(values, key=canonical_json)

def project_graph_v1(graph: Any, projection: Any) -> dict[str, Any]:
    assert_forward_projection_v1(projection); graph = assert_root_graph_v1(graph)
    nodes = graph.get("nodes", [])
    if not isinstance(nodes, list): raise ContractError("nodes must be a list", "malformed_graph")
    if projection == "structural_v1":
        result_nodes = []
        for node in nodes:
            node = _supported("node", node, node.get("type") if isinstance(node, Mapping) else None)
            result = {"uid": node_identity_v1(node), "type": node.get("type") if isinstance(node.get("type"), str) else None, "mode": node.get("mode", 0) if node.get("mode") is not None else 0, "fields": node.get("fields") if node.get("fields") is not None else {}, "widgets_values": _widgets(node)}
            if node.get("extensions") is not None: result["extensions"] = node["extensions"]
            result_nodes.append(result)
        links = graph.get("links", [])
        if not isinstance(links, list): raise ContractError("links must be a list", "malformed_graph")
        return {"projection": projection, "nodes": _sort(result_nodes), "links": _sort(_graph_link_identities(graph, nodes))}
    groups = graph.get("groups", [])
    if not isinstance(groups, list): raise ContractError("groups must be a list", "malformed_graph")
    result_nodes = []
    for node in nodes:
        node = _supported("node", node, node.get("type") if isinstance(node, Mapping) else None)
        result_nodes.append({"uid": node_identity_v1(node), "pos": list(node["pos"][:2]) if isinstance(node.get("pos"), list) else None, "size": list(node["size"][:2]) if isinstance(node.get("size"), list) else None})
    result_groups = []
    for group in groups:
        group = _supported("group", group)
        result_groups.append({"id": group_identity_v1(group), "bounding": list(group["bounding"][:4]) if isinstance(group.get("bounding"), list) else None, "color": group.get("color"), "title": group.get("title")})
    return {"projection": projection, "nodes": _sort(result_nodes), "groups": _sort(result_groups)}

def projection_reference_v1(graph: Any, projection: str) -> dict[str, Any]:
    # JSON has a single Number type in the browser: integral floats such as
    # 7.0 are parsed and serialized as 7. Normalize before both publication
    # and hashing so Python and JavaScript bind identical projection bytes.
    canonical = canonicalize_contract_numeric(
        project_graph_v1(graph, projection),
        finite_error_code="non_finite_projection",
        allow_bool=True,
    )
    return {"kind": "projection_ref_v1", "projection": projection, "digest": _hash(canonical), "canonical": canonical}

def assert_projection_reference_v1(value: Any, expected: str | None = None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or value.get("kind") != "projection_ref_v1" or not isinstance(value.get("projection"), str) or not isinstance(value.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["digest"]): raise ContractError("Expected typed projection reference", "invalid_projection_reference")
    projection_spec_v1(value["projection"])
    if expected and value["projection"] != expected: raise ContractError("Projection family mismatch", "projection_family_mismatch")
    if "canonical" in value:
        canonical = value.get("canonical")
        if not isinstance(canonical, Mapping) or canonical.get("projection") != value["projection"]:
            raise ContractError("Projection evidence has the wrong canonical family", "projection_canonical_mismatch")
        normalized_canonical = canonicalize_contract_numeric(
            canonical,
            finite_error_code="non_finite_projection",
            allow_bool=True,
        )
        if _hash(normalized_canonical) != value["digest"]:
            raise ContractError("Projection evidence digest does not bind its canonical payload", "projection_digest_mismatch")
    return value


# ---------------------------------------------------------------------------
# Compatibility projection profile
# ---------------------------------------------------------------------------
# These functions preserve the M0 browser/session hash shape while keeping all
# of its field selection, normalization, identity, ordering, and hashing in the
# registry owner. They are not typed candidate_transaction_v2 authority.

LEGACY_LAYOUT_VERIFICATION_PROJECTION = "browser_layout_v1"


def _legacy_natural_id_key(value: Any) -> tuple[int, int | str]:
    text = str(value if value is not None else "")
    matched = re.fullmatch(r"-?\d+", text)
    if matched:
        return (0, int(matched.group(0)))
    return (1, text)


def _legacy_is_preview_like_key(key: Any) -> bool:
    return re.search(r"(?:^|_)(?:video)?preview(?:_|$)", str(key or ""), re.I) is not None


def _legacy_normalize_structural_widget_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_legacy_normalize_structural_widget_value(entry) for entry in value]
    if isinstance(value, Mapping):
        return {
            key: _legacy_normalize_structural_widget_value(entry)
            for key, entry in sorted(value.items(), key=lambda item: str(item[0]))
            if not _legacy_is_preview_like_key(key)
        }
    if isinstance(value, float) and not isinstance(value, bool):
        if value == value and value not in (float("inf"), float("-inf")) and value.is_integer():
            return int(value)
    return value


def _legacy_normalize_node_widget_values(node: Mapping[str, Any]) -> Any:
    values = node.get("widgets_values", [])
    if node.get("type") == "LoadImage" and isinstance(values, list):
        return [
            _legacy_normalize_structural_widget_value(entry)
            for index, entry in enumerate(values)
            if field_category_v1(
                "node", f"widgets_values.{index}", "LoadImage"
            ) != "derived_native"
        ]
    if node.get("type") != "vibecomfy.exec":
        return _legacy_normalize_structural_widget_value(values)
    if isinstance(values, Mapping):
        return {
            key: _legacy_normalize_structural_widget_value(entry)
            for key, entry in sorted(values.items(), key=lambda item: str(item[0]))
            if key != "io" and not _legacy_is_preview_like_key(key)
        }
    if isinstance(values, list):
        return [
            _legacy_normalize_structural_widget_value(entry)
            for index, entry in enumerate(values)
            if index != 1
        ]
    return _legacy_normalize_structural_widget_value(values)


def build_structural_graph_projection(graph: Any) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        return {"nodes": [], "links": []}
    raw_nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    input_names: dict[Any, list[Any]] = {}
    output_names: dict[Any, list[Any]] = {}
    for node in raw_nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = node.get("id")
        input_names[node_id] = [
            item.get("name") if isinstance(item, Mapping) else None
            for item in (node.get("inputs") if isinstance(node.get("inputs"), list) else [])
        ]
        output_names[node_id] = [
            item.get("name") if isinstance(item, Mapping) else None
            for item in (node.get("outputs") if isinstance(node.get("outputs"), list) else [])
        ]

    nodes: list[dict[str, Any]] = []
    for raw_node in raw_nodes:
        node = raw_node if isinstance(raw_node, Mapping) else {}
        nodes.append({
            "id": node.get("id"),
            "type": node.get("type"),
            "mode": 0 if node.get("mode") is None else node.get("mode"),
            "inputs": sorted(
                str(item.get("name"))
                for item in (node.get("inputs") if isinstance(node.get("inputs"), list) else [])
                if isinstance(item, Mapping)
                and item.get("link") is not None
                and item.get("name") is not None
            ),
            "outputs": sorted(
                str(item.get("name"))
                for item in (node.get("outputs") if isinstance(node.get("outputs"), list) else [])
                if isinstance(item, Mapping) and item.get("links") and item.get("name") is not None
            ),
            "widgets_values": _legacy_normalize_node_widget_values(node),
        })
    nodes.sort(key=lambda node: (_legacy_natural_id_key(node.get("id")), str(node.get("type") or "")))

    def slot_name(names: list[Any], slot: Any) -> Any:
        if isinstance(slot, int) and 0 <= slot < len(names):
            return names[slot]
        return slot

    links: list[dict[str, Any]] = []
    for link in (graph.get("links") if isinstance(graph.get("links"), list) else []):
        if isinstance(link, list) and len(link) >= 6:
            origin_id, origin_slot, target_id, target_slot, link_type = link[1:6]
        elif isinstance(link, Mapping):
            origin_id, origin_slot = link.get("origin_id"), link.get("origin_slot")
            target_id, target_slot = link.get("target_id"), link.get("target_slot")
            link_type = link.get("type")
        else:
            continue
        links.append({
            "from": origin_id,
            "out": slot_name(output_names.get(origin_id, []), origin_slot),
            "to": target_id,
            "in": slot_name(input_names.get(target_id, []), target_slot),
            "type": link_type,
        })
    links.sort(key=lambda link: canonical_json(link, ensure_ascii=False))
    return {"nodes": nodes, "links": links}


def structural_graph_hash_compat(graph: Any) -> str | None:
    if not isinstance(graph, Mapping):
        return None
    return hashlib.sha256(
        canonical_json_bytes_v1(build_structural_graph_projection(graph), ensure_ascii=False)
    ).hexdigest()


def _legacy_layout_number(value: Any) -> Any:
    if isinstance(value, float) and not isinstance(value, bool):
        if value == value and value not in (float("inf"), float("-inf")) and value.is_integer():
            return int(value)
    return value


def _legacy_layout_vector(value: Any, length: int) -> list[Any] | None:
    if not isinstance(value, (list, tuple)) or len(value) < length:
        return None
    return [_legacy_layout_number(entry) for entry in value[:length]]


def browser_layout_scope_issues_v1(graph: Any) -> list[dict[str, str]]:
    if not isinstance(graph, Mapping):
        return []
    issues: list[dict[str, str]] = []
    definitions = graph.get("definitions")
    if isinstance(definitions, Mapping) and definitions:
        issues.append({"scope_path": "definitions", "reason": "nested_definitions"})
    groups = graph.get("groups")
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            scope_path = str(group.get("scope_path") or "")
            if scope_path:
                issues.append({"scope_path": scope_path, "reason": "nested_group"})
    return issues


def build_layout_graph_projection(graph: Any) -> dict[str, Any]:
    if not isinstance(graph, Mapping):
        return {
            "contract_version": LEGACY_LAYOUT_VERIFICATION_PROJECTION,
            "nodes": [],
            "groups": [],
        }
    issues = browser_layout_scope_issues_v1(graph)
    if issues:
        raise ValueError(f"unsupported_nested_layout_scope:{issues!r}")
    raw_nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    nodes = [
        {
            "id": node.get("id"),
            "pos": _legacy_layout_vector(node.get("pos"), 2),
            "size": _legacy_layout_vector(node.get("size"), 2),
        }
        for node in raw_nodes
        if isinstance(node, Mapping)
    ]
    nodes.sort(key=lambda node: _legacy_natural_id_key(node.get("id")))
    groups = [
        {
            "id": group.get("id"),
            "scope_path": str(group.get("scope_path") or ""),
            "title": group.get("title"),
            "bounding": _legacy_layout_vector(group.get("bounding"), 4),
            "color": group.get("color"),
        }
        for group in (graph.get("groups") if isinstance(graph.get("groups"), list) else [])
        if isinstance(group, Mapping)
    ]
    groups.sort(key=lambda group: canonical_json(group.get("id"), ensure_ascii=False))
    return {
        "contract_version": LEGACY_LAYOUT_VERIFICATION_PROJECTION,
        "nodes": nodes,
        "groups": groups,
    }


def layout_graph_hash_compat(graph: Any) -> str | None:
    if not isinstance(graph, Mapping):
        return None
    try:
        projection = build_layout_graph_projection(graph)
    except ValueError:
        return None
    return hashlib.sha256(canonical_json_bytes_v1(projection, ensure_ascii=False)).hexdigest()

def _strict_delta(ops: Any) -> list[Any]:
    from vibecomfy.porting.edit.ops import ensure_root_scoped_delta_envelope
    envelope = ensure_root_scoped_delta_envelope({"schema_version": DELTA_WIRE_VERSION, "ops": ops}, strict=True)
    if envelope.legacy_bridge is not None: raise ContractError("Legacy delta bridge is not authority", "legacy_delta_shape")
    return [item for item in ops]

RESTORATION_STRATEGY_TAGS = frozenset({
    "inverse_delta_v1",
    "inverse_delta_v2",
    "inverse_layout_operation_v1",
    "baseline_snapshot_v1",
})
RESTORATION_COMPENSATION_CONTRACT_V1 = "baseline_snapshot_v1"
RESTORATION_COMPENSATION_WIRE_VERSION = "1.0.0"
_FENCE_KEYS = frozenset({
    "transaction_id", "candidate_id", "plan_hash", "lease_nonce",
    "generation", "pre_projection_digest", "post_projection_digest",
})


def _link_to(op: Mapping[str, Any]) -> Any:
    """Stable endpoint identity for link ops (the `to` field tuple)."""
    to = op.get("to")
    if isinstance(to, (list, tuple)):
        return tuple(to)
    return None


def _link_forward_key(link_op_name: str, op: Mapping[str, Any]) -> tuple[str, str, Any]:
    """Forward uniqueness identity for a link op: (op class, destination `to`).

    A ComfyUI input (`to`) holds exactly one inbound link, so `to` is the stable
    endpoint.  But a canonical rewire is ``remove_link(to=X)`` followed by
    ``upsert_link(from=new, to=X)`` — two distinct causal ops at the same ``to``.
    Including the op class keeps both ops (the rewire is valid) while still
    rejecting a true duplicate: two ``upsert_link``s to the same ``to``, or two
    ``remove_link``s of the same ``to``, collide on ``(op, to)``.

    Canonical ``remove_link`` carries only ``to`` (no ``from``): the prior source
    it disconnects is restored by the inverse ``upsert_link``, not recorded here.
    """
    return ("link", link_op_name, _link_to(op))


def _delta_op_identity(op: Mapping[str, Any]) -> tuple[str, Any]:
    name = op.get("op")
    if name == "set_node_field":
        target = op.get("target")
        return ("set_node_field", tuple(target[1:]) if isinstance(target, (list, tuple)) else None)
    if name == "set_mode":
        target = op.get("target")
        return ("set_mode", target[1] if isinstance(target, (list, tuple)) and len(target) > 1 else None)
    if name == "add_node":
        return ("node", op.get("uid"))
    if name == "remove_node":
        target = op.get("target")
        return ("node", target[1] if isinstance(target, (list, tuple)) and len(target) > 1 else None)
    if name in ("upsert_link", "remove_link"):
        return _link_forward_key(name, op)
    if name == "set_node_geometry":
        return ("set_node_geometry", op.get("uid"))
    if name == "add_group":
        return ("group", op.get("id"))
    if name == "set_group_geometry":
        return ("set_group_geometry", op.get("id"))
    if name == "remove_group":
        return ("group", op.get("id"))
    return (name or "", None)


def _inverse_bindable_forward_keys(
    inv: Mapping[str, Any], forward_by_id: Mapping[tuple[str, Any], Mapping[str, Any]]
) -> list[tuple[str, Any]]:
    """Return all class-valid forward identities at the inverse op's locus."""
    name = inv.get("op")
    if name in ("remove_link", "upsert_link"):
        keys: list[tuple[str, Any]] = []
        for forward_name in ("upsert_link", "remove_link"):
            key = _link_forward_key(forward_name, inv)
            if key in forward_by_id and name in _mandated_inverse_class(forward_name):
                keys.append(key)
        return keys
    key = _delta_op_identity(inv)
    forward = forward_by_id.get(key)
    return [key] if forward is not None and name in _mandated_inverse_class(forward.get("op")) else []


def _forward_keys_at_locus(
    inv: Mapping[str, Any], forward_by_id: Mapping[tuple[str, Any], Mapping[str, Any]]
) -> list[tuple[str, Any]]:
    if inv.get("op") in ("remove_link", "upsert_link"):
        return [
            key
            for key in (
                _link_forward_key("upsert_link", inv),
                _link_forward_key("remove_link", inv),
            )
            if key in forward_by_id
        ]
    key = _delta_op_identity(inv)
    return [key] if key in forward_by_id else []


def _complete_matchings(
    adjacency: list[list[tuple[str, Any]]], forward_count: int
) -> list[list[tuple[str, Any]]]:
    """Enumerate at most two complete bipartite matchings (zero/one/many)."""
    used: set[tuple[str, Any]] = set()
    assignments: list[list[tuple[str, Any]]] = []

    def visit(index: int, current: list[tuple[str, Any]]) -> None:
        if len(assignments) > 1:
            return
        if index == len(adjacency):
            if len(used) == forward_count:
                assignments.append(list(current))
            return
        for key in adjacency[index]:
            if key in used:
                continue
            used.add(key)
            current.append(key)
            visit(index + 1, current)
            current.pop()
            used.remove(key)

    visit(0, [])
    return assignments


def _assert_inverse_relation(
    forward_ops: Any,
    inverse_ops: Any,
    family: str,
    *,
    prior_link_witnesses: list[Mapping[str, Any]] | None = None,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Require exactly one order-independent complete causal matching."""
    forward = forward_ops if isinstance(forward_ops, list) else []
    inverse = inverse_ops if isinstance(inverse_ops, list) else []
    forward_by_id: dict[tuple[str, Any], Mapping[str, Any]] = {}
    for op in forward:
        if not isinstance(op, Mapping):
            continue
        identity = _delta_op_identity(op)
        if identity in forward_by_id:
            raise ContractError("Duplicate forward identity in delta", "duplicate_identity")
        forward_by_id[identity] = op
    for inv in inverse:
        if not isinstance(inv, Mapping):
            raise ContractError("Inverse op is not an object", "inverse_missing_prior_state")
    if not inverse and forward:
        raise ContractError("Inverse shares no identity with forward", "inverse_unrelated")
    adjacency = [_inverse_bindable_forward_keys(inv, forward_by_id) for inv in inverse]
    matches = _complete_matchings(adjacency, len(forward_by_id))
    if not matches:
        for index, candidates in enumerate(adjacency):
            if candidates:
                continue
            if _forward_keys_at_locus(inverse[index], forward_by_id):
                raise ContractError("Inverse class is not mandated at its forward locus", "inverse_class_mismatch")
            if not forward_by_id:
                raise ContractError("Inverse shares no identity with forward", "inverse_unrelated")
            raise ContractError("Inverse op identity is not bound to any forward op", "inverse_identity_unbound")
        raise ContractError("Forward op has no matching inverse", "inverse_coverage_gap")
    if len(matches) > 1:
        raise ContractError("Inverse relation admits multiple complete matchings", "inverse_multiple_match")

    witness_by_to = {
        _link_to(witness): witness for witness in (prior_link_witnesses or [])
    }
    pairs: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for index, inverse_op in enumerate(inverse):
        forward_op = forward_by_id[matches[0][index]]
        _check_prior_state_binding(str(forward_op.get("op")), forward_op, inverse_op)
        if forward_op.get("op") == "remove_link" and prior_link_witnesses is not None:
            witness = witness_by_to.get(_link_to(forward_op))
            if (
                witness is None
                or tuple(witness.get("from", ())) != tuple(inverse_op.get("from", ()))
                or _link_to(witness) != _link_to(inverse_op)
            ):
                raise ContractError("Inverse upsert_link does not match prior-link witness", "inverse_missing_prior_state")
        pairs.append((forward_op, inverse_op))
    return pairs


def _mandated_inverse_class(forward_name: str) -> frozenset[str]:
    return {
        "set_node_field": frozenset({"set_node_field"}),
        "set_mode": frozenset({"set_mode"}),
        "add_node": frozenset({"remove_node"}),
        "remove_node": frozenset({"add_node"}),
        "upsert_link": frozenset({"remove_link", "upsert_link"}),
        "remove_link": frozenset({"upsert_link"}),
        # layout ops
        "set_node_geometry": frozenset({"set_node_geometry"}),
        "add_group": frozenset({"remove_group"}),
        "set_group_geometry": frozenset({"set_group_geometry"}),
        "remove_group": frozenset({"add_group"}),
    }.get(forward_name, frozenset())


def _check_prior_state_binding(forward_name: str, forward_op: Mapping[str, Any], inverse_op: Mapping[str, Any]) -> None:
    if forward_name == "set_node_field":
        if inverse_op.get("value") == forward_op.get("value"):
            raise ContractError(
                "Inverse set_node_field carries the forward value, not the prior value",
                "invalid_inverse_strategy",
            )
    elif forward_name == "set_mode":
        if inverse_op.get("mode") == forward_op.get("mode"):
            raise ContractError(
                "Inverse set_mode carries the forward mode, not the prior mode",
                "invalid_inverse_strategy",
            )
    elif forward_name == "add_node":
        # Inverse is remove_node targeting the same uid; no prior payload.
        target = inverse_op.get("target")
        if not isinstance(target, (list, tuple)) or len(target) < 2 or target[1] != forward_op.get("uid"):
            raise ContractError("Inverse remove_node does not bind the added uid", "inverse_missing_prior_state")
    elif forward_name == "remove_node":
        # Inverse is add_node reconstructing the node.  The forward remove_node
        # op carries only target=[_, uid]; the pre-removal payload (node_id,
        # class_type, fields, inputs) comes from authoritative captured state
        # and is bound on the inverse add_node — not verifiable from the forward
        # op alone.  Verify the uid binds.
        target = forward_op.get("target")
        forward_uid = target[1] if isinstance(target, (list, tuple)) and len(target) > 1 else None
        if inverse_op.get("uid") != forward_uid:
            raise ContractError(
                "Inverse add_node does not bind the removed uid",
                "inverse_missing_prior_state",
            )
    elif forward_name == "upsert_link":
        if inverse_op.get("op") == "remove_link":
            if _link_to(inverse_op) != _link_to(forward_op):
                raise ContractError("Inverse remove_link endpoint mismatch", "inverse_missing_prior_state")
        # upsert_link inverse restores prior endpoints (accepted structurally).
    elif forward_name == "remove_link":
        if _link_to(inverse_op) != _link_to(forward_op):
            raise ContractError("Inverse upsert_link endpoint mismatch", "inverse_missing_prior_state")
    elif forward_name in ("set_node_geometry", "set_group_geometry"):
        # Self-class inverse must carry the prior value(s); reject an exact
        # clone (self-inverse with the forward value).
        if _dict_without_op(forward_op) == _dict_without_op(inverse_op):
            raise ContractError(
                "Inverse geometry op is a verbatim clone of the forward op",
                "invalid_inverse_strategy",
            )
    # add_group -> remove_group / remove_group -> add_group: identity-bound only.


def _dict_without_op(op: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in op.items() if k != "op"}


def forward_operation_digest(forward_ops: Any) -> str:
    """Bind inverse_delta_v2 to the exact canonical forward operation list."""
    normalized_ops = _strict_delta(forward_ops)
    return _hash(canonicalize_contract_numeric({
        "delta_contract": DELTA_V1,
        "wire_version": DELTA_WIRE_VERSION,
        "ops": normalized_ops,
    }, finite_error_code="non_finite_materialization", allow_bool=True))


def _root_endpoint(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and value[0] == ""
        and isinstance(value[1], str)
        and bool(value[1])
        and isinstance(value[2], str)
        and bool(value[2])
    )


def _restoration(value: Any, *, family: str | None = None, forward_ops: list | None = None) -> Mapping[str, Any]:
    """Validate the mandatory ``restoration_strategy`` slot (closed tag set).

    Accepts versioned structural inverse payloads, the layout inverse payload,
    or the grandfathered
    ``baseline_snapshot_v1`` ref tag.  ``payload`` and ``ref`` are mutually
    exclusive.  Digests are recomputed over the shared hash owner.
    """
    if not isinstance(value, Mapping):
        raise ContractError("Restoration strategy must be an object", "malformed_restoration_payload")
    tag = value.get("contract_version")
    if tag not in RESTORATION_STRATEGY_TAGS:
        raise ContractError("Unknown restoration strategy tag", "unknown_restoration_strategy")
    has_payload = "payload" in value
    has_ref = "ref" in value
    if has_payload and has_ref:
        raise ContractError("Restoration payload and ref are mutually exclusive", "malformed_restoration_payload")
    if not has_payload and not has_ref:
        raise ContractError("Restoration requires payload or ref", "malformed_restoration_payload")
    if not isinstance(value.get("digest"), str) or not _HEX64.fullmatch(value["digest"]):
        raise ContractError("Restoration digest must be hex64", "malformed_restoration_payload")
    if tag == "baseline_snapshot_v1":
        # Grandfathered ref shape (the sole permitted ref tag).
        if not has_ref:
            raise ContractError("baseline_snapshot_v1 restoration must use ref", "malformed_restoration_payload")
        ref = value.get("ref")
        if not isinstance(ref, str) or not ref:
            raise ContractError("baseline_snapshot_v1 ref must be a non-empty string", "malformed_restoration_payload")
        expected = _hash({"contract_version": tag, "ref": ref})
        if value["digest"] != expected:
            raise ContractError("Restoration digest mismatch", "restoration_digest_mismatch")
        return value
    # Payload-tagged inverse restoration.
    if not has_payload:
        raise ContractError("inverse restoration must use payload", "malformed_restoration_payload")
    if family is not None:
        allowed_tags = (
            {"inverse_layout_operation_v1"}
            if family == "layout"
            else {"inverse_delta_v1", "inverse_delta_v2"}
        )
        if tag not in allowed_tags:
            raise ContractError("Restoration family mismatch", "restoration_family_mismatch")
    payload = value.get("payload")
    if not isinstance(payload, Mapping):
        raise ContractError("Restoration payload must be an object", "malformed_restoration_payload")
    normalized_payload = canonicalize_contract_numeric(payload, finite_error_code="non_finite_materialization", allow_bool=True)
    expected = _hash({"contract_version": tag, "payload": normalized_payload})
    if value["digest"] != expected:
        raise ContractError("Restoration digest mismatch", "restoration_digest_mismatch")
    _validate_restoration_payload(tag, payload, family, forward_ops)
    return value


def _validate_restoration_payload(tag: str, payload: Mapping[str, Any], family: str | None, forward_ops: list | None) -> None:
    if tag in ("inverse_delta_v1", "inverse_delta_v2"):
        is_v2 = tag == "inverse_delta_v2"
        allowed = {"ops", "mutation_materialization", "mutation_materialization_digest"}
        if is_v2:
            allowed.update({"forward_operation_digest", "prior_link_witnesses"})
        extras = sorted(k for k in payload if k not in allowed)
        if extras:
            raise ContractError(f"{tag} payload has extra keys", "malformed_restoration_payload")
        ops = payload.get("ops")
        if not isinstance(ops, list):
            raise ContractError(f"{tag} payload requires ops", "malformed_restoration_payload")
        _strict_delta(ops)
        has_add_node = any(isinstance(o, Mapping) and o.get("op") == "add_node" for o in ops)
        has_mat = "mutation_materialization" in payload
        has_mat_digest = "mutation_materialization_digest" in payload
        if has_mat != has_mat_digest:
            raise ContractError("mutation_materialization presence parity violated", "malformed_restoration_payload")
        if has_add_node and not has_mat:
            raise ContractError("add_node inverse requires materialization", "malformed_restoration_payload")
        if not has_add_node and has_mat:
            raise ContractError("materialization without add_node inverse", "malformed_restoration_payload")
        if has_mat:
            mat = payload.get("mutation_materialization")
            assert_mutation_materialization_envelope(mat, accompanying_ops=ops)
            if payload.get("mutation_materialization_digest") != mat.get("digest"):
                raise ContractError("mutation_materialization_digest mismatch", "restoration_digest_mismatch")
        witnesses: list[Mapping[str, Any]] | None = None
        if is_v2:
            forward_digest = payload.get("forward_operation_digest")
            if not isinstance(forward_digest, str) or not _HEX64.fullmatch(forward_digest):
                raise ContractError("forward_operation_digest must be hex64", "malformed_restoration_payload")
            raw_witnesses = payload.get("prior_link_witnesses")
            if not isinstance(raw_witnesses, list):
                raise ContractError("prior_link_witnesses must be an array", "malformed_restoration_payload")
            witnesses = []
            witness_destinations: set[Any] = set()
            for witness in raw_witnesses:
                if (
                    not isinstance(witness, Mapping)
                    or set(witness) != {"from", "to"}
                    or not _root_endpoint(witness.get("from"))
                    or not _root_endpoint(witness.get("to"))
                ):
                    raise ContractError("prior-link witness must be exactly {from,to} root endpoints", "malformed_restoration_payload")
                destination = _link_to(witness)
                if destination in witness_destinations:
                    raise ContractError("duplicate prior-link witness destination", "malformed_restoration_payload")
                witness_destinations.add(destination)
                witnesses.append(witness)
        if family is not None and forward_ops is not None:
            if is_v2 and payload.get("forward_operation_digest") != forward_operation_digest(forward_ops):
                raise ContractError("forward_operation_digest mismatch", "forward_operation_digest_mismatch")
            if is_v2:
                remove_destinations = {
                    _link_to(op)
                    for op in forward_ops
                    if isinstance(op, Mapping) and op.get("op") == "remove_link"
                }
                witness_destinations = {_link_to(witness) for witness in (witnesses or [])}
                if remove_destinations != witness_destinations:
                    raise ContractError("prior-link witnesses do not exactly cover forward remove_link ops", "inverse_missing_prior_state")
            _assert_inverse_relation(
                forward_ops,
                ops,
                family,
                prior_link_witnesses=witnesses,
            )
    elif tag == "inverse_layout_operation_v1":
        allowed = {"layout_operation", "layout_operation_digest"}
        extras = sorted(k for k in payload if k not in allowed)
        if extras:
            raise ContractError("inverse_layout_operation_v1 payload has extra keys", "malformed_restoration_payload")
        layout = payload.get("layout_operation")
        if not isinstance(layout, Mapping):
            raise ContractError("inverse_layout_operation_v1 requires layout_operation", "malformed_restoration_payload")
        assert_layout_operation_envelope(layout)
        if payload.get("layout_operation_digest") != layout.get("digest"):
            raise ContractError("layout_operation_digest mismatch", "restoration_digest_mismatch")


def family_ops_for_inverse(family: str, _unused: Any) -> Any:
    """Forward ops are supplied by the caller via the bound authority operation.

    The inverse-relation check is invoked from the prepared-authority validator
    where the forward ``operation.ops`` is available; this indirection keeps the
    restoration validator decoupled from the authority envelope.
    """
    # The actual forward ops binding is performed in
    # _validate_candidate_authority_common which passes operation.ops directly.
    return []


def _restoration_compensation(value: Any, *, authority: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate the prepare-owned optional ``restoration_strategy_compensation``.

    Carries a ``baseline_snapshot_v1`` compensation-only ref bound to the
    prepared authority's own identity/projection fence.  Separately digested.
    """
    if not isinstance(value, Mapping):
        raise ContractError("restoration_strategy_compensation must be an object", "malformed_restoration_compensation")
    extras = sorted(k for k in value if k not in {"contract_version", "wire_version", "ref", "fence", "digest"})
    if extras:
        raise ContractError("restoration_strategy_compensation has extra keys", "malformed_restoration_compensation")
    if value.get("contract_version") != RESTORATION_COMPENSATION_CONTRACT_V1:
        raise ContractError("compensation must use baseline_snapshot_v1", "unknown_restoration_strategy")
    if value.get("wire_version") != RESTORATION_COMPENSATION_WIRE_VERSION:
        raise ContractError("compensation wire version mismatch", "unsupported_wire_version")
    ref = value.get("ref")
    if not isinstance(ref, str) or not ref:
        raise ContractError("compensation ref must be a non-empty string", "malformed_restoration_compensation")
    fence = value.get("fence")
    if not isinstance(fence, Mapping):
        raise ContractError("compensation fence must be an object", "malformed_restoration_compensation")
    fence_extras = sorted(k for k in fence if k not in _FENCE_KEYS)
    missing = sorted(k for k in _FENCE_KEYS if k not in fence)
    if fence_extras or missing:
        raise ContractError("compensation fence key set is not closed", "malformed_restoration_compensation")
    if not isinstance(fence.get("generation"), int) or isinstance(fence.get("generation"), bool) or fence["generation"] <= 0:
        raise ContractError("compensation generation must be a positive int", "malformed_restoration_compensation")
    for key in ("transaction_id", "candidate_id", "plan_hash", "lease_nonce"):
        if not isinstance(fence.get(key), str) or not fence[key]:
            raise ContractError(f"compensation fence {key} must be non-empty string", "malformed_restoration_compensation")
    for key in ("pre_projection_digest", "post_projection_digest"):
        if not isinstance(fence.get(key), str) or not _HEX64.fullmatch(fence[key]):
            raise ContractError(f"compensation fence {key} must be hex64", "malformed_restoration_compensation")
    # Fence binding: every value must equal the enclosing prepared authority.
    bindings = {
        "transaction_id": authority.get("transaction_id"),
        "candidate_id": authority.get("candidate_id"),
        "plan_hash": authority.get("plan_hash"),
        "lease_nonce": authority.get("lease_nonce"),
        "generation": authority.get("generation"),
        "pre_projection_digest": authority.get("precondition", {}).get("digest") if isinstance(authority.get("precondition"), Mapping) else None,
        "post_projection_digest": authority.get("postcondition", {}).get("digest") if isinstance(authority.get("postcondition"), Mapping) else None,
    }
    for key, expected in bindings.items():
        if fence.get(key) != expected:
            raise ContractError("compensation fence is not bound to this authority", "compensation_fence_unbound")
    # Digest (separate from restoration_strategy.digest).
    normalized_fence = canonicalize_contract_numeric(fence, finite_error_code="non_finite_materialization", allow_bool=True)
    expected_digest = _hash({
        "contract_version": RESTORATION_COMPENSATION_CONTRACT_V1,
        "wire_version": RESTORATION_COMPENSATION_WIRE_VERSION,
        "ref": ref,
        "fence": normalized_fence,
    })
    if not isinstance(value.get("digest"), str) or value["digest"] != expected_digest:
        raise ContractError("compensation digest mismatch", "compensation_digest_mismatch")
    return value


def assert_restoration_strategy_compensation(value: Any, *, authority: Mapping[str, Any]) -> Mapping[str, Any]:
    """Public entrypoint for the prepare-owned compensation validator."""
    return _restoration_compensation(value, authority=authority)


def _frozen(value: Any) -> Any:
    if isinstance(value, Mapping): return MappingProxyType({str(k): _frozen(v) for k, v in value.items()})
    if isinstance(value, list): return tuple(_frozen(v) for v in value)
    return value

def _validate_candidate_authority_common(raw: Any) -> Any:
    if not isinstance(raw, Mapping) or raw.get("contract_version") not in {CANDIDATE_AUTHORITY_V1, PREPARED_AUTHORITY_V1}: raise ContractError("Unsupported authority version", "unknown_authority_version")
    for key in ("transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash"): issued_identity_v1(raw.get(key), key)
    if raw.get("authority_receipt_contract_version") != AUTHORITY_RECEIPT_CONTRACT_VERSION:
        raise ContractError("Authority receipt contract version must be explicit", "unknown_authority_receipt_version")
    if raw.get("authority_receipt_delta_schema") != DELTA_WIRE_VERSION:
        raise ContractError("Authority receipt delta schema must match delta_v1", "authority_receipt_delta_schema_mismatch")
    if not isinstance(raw.get("authority_receipt_digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", raw["authority_receipt_digest"]):
        raise ContractError("Authority receipt digest must be exact lowercase SHA-256", "invalid_authority_receipt_digest")
    workflow_identity_v1(raw.get("workflow_id")); assert_root_scope_v1(raw.get("scope"))
    operation = raw.get("operation")
    if not isinstance(operation, Mapping) or operation.get("delta_contract") != DELTA_V1 or operation.get("wire_version") != DELTA_WIRE_VERSION or not isinstance(operation.get("ops"), list): raise ContractError("Operation must explicitly bind delta_v1 to wire 2.0.0", "invalid_delta_contract")
    _strict_delta(operation["ops"])
    family = raw.get("operation_family")
    if family not in {"structural", "layout"}: raise ContractError("Unknown operation family", "unknown_operation_family")
    expected = "layout_v1" if family == "layout" else "structural_v1"
    assert_projection_reference_v1(raw.get("precondition"), expected); assert_projection_reference_v1(raw.get("postcondition"), expected)
    if raw.get("rollback_projection") != expected: raise ContractError("Rollback projection must equal forward family", "rollback_projection_mismatch")
    if family == "layout":
        witness = assert_projection_reference_v1(raw.get("structural_witness"), "structural_v1")
        if witness.get("precondition_digest") != witness.get("postcondition_digest"): raise ContractError("Layout requires structural no-op witness", "layout_structural_witness_mismatch")
    _bind_family_contracts(raw, family)
    _restoration(raw.get("restoration_strategy"), family=family, forward_ops=operation["ops"])
    # Prepare-owned optional compensation slot: validated only on prepared
    # authority (candidate presence is rejected by validate_candidate_authority_v1).
    if "restoration_strategy_compensation" in raw and raw.get("contract_version") == PREPARED_AUTHORITY_V1:
        _restoration_compensation(raw["restoration_strategy_compensation"], authority=raw)
    return raw


def _bind_family_contracts(raw: Mapping[str, Any], family: str) -> None:
    """Bind layout_operation / mutation_materialization per §1.5 / §2.5."""
    operation = raw.get("operation")
    ops = operation.get("ops") if isinstance(operation, Mapping) else None
    if family == "layout":
        if operation.get("ops"):
            raise ContractError("Layout family requires empty structural ops", "layout_family_requires_empty_structural_ops")
        layout = operation.get("layout_operation")
        if layout is None:
            raise ContractError("Layout family requires layout_operation", "missing_layout_operation")
        assert_layout_operation_envelope(layout)
        if operation.get("layout_operation_digest") != layout.get("digest"):
            raise ContractError("layout_operation_digest mismatch", "layout_operation_digest_mismatch")
        if "mutation_materialization" in operation:
            raise ContractError("Layout family must not carry mutation_materialization", "unexpected_materialization")
    else:  # structural
        if "layout_operation" in operation:
            raise ContractError("Structural family must not carry layout_operation", "unexpected_layout_operation")
        has_add_node = any(isinstance(o, Mapping) and o.get("op") == "add_node" for o in (ops or []))
        has_mat = "mutation_materialization" in operation
        if has_add_node and not has_mat:
            raise ContractError("Structural family with add_node requires mutation_materialization", "missing_materialization")
        if not has_add_node and has_mat:
            raise ContractError("Structural family without add_node must not carry mutation_materialization", "unexpected_materialization")
        if has_mat:
            mat = operation.get("mutation_materialization")
            assert_mutation_materialization_envelope(mat, accompanying_ops=ops)
            if operation.get("mutation_materialization_digest") != mat.get("digest"):
                raise ContractError("mutation_materialization_digest mismatch", "mutation_materialization_digest_mismatch")

def validate_candidate_authority_v1(raw: Any, *, freeze: bool = False) -> Any:
    _validate_candidate_authority_common(raw)
    if raw.get("contract_version") != CANDIDATE_AUTHORITY_V1: raise ContractError("Unsupported candidate authority version", "unknown_authority_version")
    if "generation" in raw or "lease_nonce" in raw: raise ContractError("Candidate authority cannot infer prepare-time identity", "unexpected_prepare_identity")
    if "restoration_strategy_compensation" in raw: raise ContractError("Candidate authority may not carry restoration_strategy_compensation", "candidate_compensation_forbidden")
    clean = json.loads(json.dumps(raw))
    return _frozen(clean) if freeze else clean

def validate_prepared_authority_v1(raw: Any, *, freeze: bool = False) -> Any:
    _validate_candidate_authority_common(raw)
    if raw.get("contract_version") != PREPARED_AUTHORITY_V1: raise ContractError("Unsupported prepared authority version", "unknown_authority_version")
    issued_identity_v1(raw.get("lease_nonce"), "lease_nonce")
    if not isinstance(raw.get("generation"), int) or raw["generation"] <= 0: raise ContractError("generation must be positive", "invalid_generation")
    clean = json.loads(json.dumps(raw))
    return _frozen(clean) if freeze else clean

def validate_candidate_transaction_v2(value: Any) -> Any:
    """Validate the explicit candidate-ready/prepared v2 authority stages.

    Candidate publication intentionally has no generation or lease.  Those are
    minted exactly once by prepare, then recorded in a prepared authority.  A
    caller cannot fill either field later by inference.
    """
    if not isinstance(value, Mapping) or value.get("contract_version") != CANDIDATE_TRANSACTION_V2:
        raise ContractError("Unsupported candidate transaction version", "unsupported_candidate_transaction")
    state = value.get("state")
    candidate = value.get("candidate_authority")
    if candidate is None:
        raise ContractError("candidate_transaction_v2 requires candidate_authority_v1", "missing_candidate_authority")
    candidate = validate_candidate_authority_v1(candidate)
    prepared = value.get("prepared_authority")
    if state in {"candidate_ready", "recoverable_error"}:
        if prepared is not None: raise ContractError("Candidate-ready authority cannot carry prepare identity", "unexpected_prepared_authority")
    elif state in {"prepared", "canvas_verified", "finalized", "rollback_complete", "superseded"}:
        prepared = validate_prepared_authority_v1(prepared)
        for key in ("transaction_id", "candidate_id", "session_id", "turn_id", "plan_hash", "workflow_id", "scope", "operation", "operation_family", "precondition", "postcondition", "rollback_projection", "restoration_strategy", "authority_receipt_contract_version", "authority_receipt_delta_schema", "authority_receipt_digest"):
            if prepared.get(key) != candidate.get(key): raise ContractError("Prepared authority changed candidate-time authority", "prepared_authority_transition_mismatch")
        # restoration_strategy_compensation: sole prepare-owned additive key.
        # Candidate presence is forbidden (caught above); prepared absence is
        # legal; prepared presence must be byte-identical across transitions.
        candidate_has_comp = "restoration_strategy_compensation" in candidate
        prepared_has_comp = "restoration_strategy_compensation" in prepared
        if candidate_has_comp:
            raise ContractError("Candidate authority carries restoration_strategy_compensation", "candidate_compensation_forbidden")
        if prepared_has_comp and prepared.get("restoration_strategy_compensation") is None:
            raise ContractError("restoration_strategy_compensation may not be null", "malformed_restoration_compensation")
    elif state == "discarded":
        if prepared is not None: raise ContractError("Discarded unprepared candidate cannot carry prepared authority", "unexpected_prepared_authority")
    else:
        raise ContractError("Unknown candidate transaction state", "invalid_candidate_transaction_state")
    return json.loads(json.dumps(value))

def validate_journal_durable_v1(record: Any) -> Mapping[str, Any]:
    if (
        not isinstance(record, Mapping)
        or record.get("contract_version") != JOURNAL_DURABLE_V1
        or record.get("state") != "finalized"
    ):
        raise ContractError("Invalid journal_durable_v1 record", "invalid_journal_durable")
    workflow_identity_v1(record.get("workflow_id"))
    baseline = record.get("baseline")
    fence = record.get("identity_fence")
    restoration = record.get("inverse_or_restore")
    if not all(isinstance(value, Mapping) for value in (baseline, fence, restoration)):
        raise ContractError("Invalid journal_durable_v1 record", "invalid_journal_durable")
    if any(not _HEX64.fullmatch(str(baseline.get(key, ""))) for key in ("structural_hash_before", "structural_hash_after")):
        raise ContractError("Durable journal requires exact baseline projection digests", "invalid_journal_durable")
    if any(not isinstance(fence.get(key), str) or not fence.get(key) for key in ("transaction_id", "candidate_id", "plan_hash", "lease_nonce")) or not isinstance(fence.get("generation"), int) or fence.get("generation") <= 0:
        raise ContractError("Durable journal requires a complete identity fence", "invalid_journal_durable")
    if (
        not isinstance(restoration.get("contract_version"), str)
        or not _HEX64.fullmatch(str(restoration.get("digest", "")))
        or not ("ref" in restoration or "payload" in restoration)
    ):
        raise ContractError("Durable journal requires bound inverse/restore authority", "invalid_journal_durable")
    return _frozen(json.loads(json.dumps(record)))

def classify_legacy_migration_v1(value: Any) -> dict[str, Any]:
    terminal = {"finalized", "discarded", "rollback_complete", "superseded", "accepted", "rejected", "rolled_back", "cancelled"}
    if isinstance(value, Mapping) and value.get("contract_version") == "candidate_transaction_v1":
        if value.get("state") in terminal: return {"classification": "legacy_terminal_read_only", "actions": ["audit"]}
        exact = isinstance(value.get("exact_restoration_strategy"), Mapping) and bool(value["exact_restoration_strategy"].get("original_contract"))
        return {"classification": "legacy_prepared_nonresumable", "actions": ["rebaseline", "cancel"], "rollback_allowed": exact}
    return {"classification": "legacy_non_resumable", "actions": ["rebaseline", "cancel"], "rollback_allowed": False}

__all__ = [name for name in globals() if name.endswith("_V1") or name in {"ContractError", "DELTA_V1", "DELTA_WIRE_VERSION", "AUTHORITY_RECEIPT_CONTRACT_VERSION", "ROOT_SCOPE", "FIELD_CATEGORIES", "PROJECTIONS_V1", "RESTORATION_STRATEGY_TAGS", "canonical_json", "canonical_json_bytes_v1", "canonicalize_contract_numeric", "field_category_v1", "assert_root_scope_v1", "assert_root_graph_v1", "workflow_identity_v1", "node_identity_v1", "group_identity_v1", "issued_identity_v1", "project_graph_v1", "projection_reference_v1", "assert_projection_reference_v1", "build_structural_graph_projection", "structural_graph_hash_compat", "browser_layout_scope_issues_v1", "build_layout_graph_projection", "layout_graph_hash_compat", "forward_operation_digest", "validate_candidate_authority_v1", "validate_prepared_authority_v1", "validate_candidate_transaction_v2", "validate_journal_durable_v1", "classify_legacy_migration_v1"}]
