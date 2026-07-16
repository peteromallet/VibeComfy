"""M1 typed graph authority contracts.

This is the Python semantic owner for projection, field, identity, root-scope,
prepared-authority, durable-undo, and legacy migration contracts.  V1 candidate
records remain historical/read-only; new authority is candidate_transaction_v2.
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import cmp_to_key
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Any

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
    "node.vibecomfy_uid": "derived_native", "node.id": "derived_native", "node.type": "execution_semantic", "node.mode": "native_defaulted", "node.fields": "execution_semantic", "node.widgets_values": "execution_semantic", "node.inputs": "derived_native", "node.outputs": "derived_native", "node.properties": "derived_native", "node.flags": "derived_native", "node.order": "derived_native", "node.pos": "layout_semantic", "node.size": "layout_semantic", "node.title": "layout_semantic", "node.color": "layout_semantic", "node.bgcolor": "layout_semantic", "node.boxcolor": "layout_semantic", "node.shape": "layout_semantic", "node.extensions": "opaque_extension",
    "group.vibecomfy_group_id": "derived_native", "group.id": "derived_native", "group.scope_path": "derived_native", "group.flags": "derived_native", "group.font_size": "layout_semantic", "group.title": "layout_semantic", "group.bounding": "layout_semantic", "group.color": "layout_semantic",
})
PROJECTIONS_V1 = MappingProxyType({"structural_v1": MappingProxyType({"allowed": True}), "layout_v1": MappingProxyType({"allowed": True}), "workflow_v1": MappingProxyType({"allowed": False, "reason": "forbidden_forward_agent_edit"})})
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

class ContractError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message); self.code = code

def _compare_utf16_keys(left: str, right: str) -> int:
    """Match JavaScript's UTF-16 code-unit object-key ordering exactly."""
    left_units = left.encode("utf-16-be", errors="surrogatepass")
    right_units = right.encode("utf-16-be", errors="surrogatepass")
    return (left_units > right_units) - (left_units < right_units)


def _order_json_objects_utf16(value: Any) -> Any:
    if isinstance(value, Mapping):
        ordered: dict[str, Any] = {}
        entries = sorted(
            ((str(key), entry) for key, entry in value.items()),
            key=cmp_to_key(lambda left, right: _compare_utf16_keys(left[0], right[0])),
        )
        for key, entry in entries:
            ordered[key] = _order_json_objects_utf16(entry)
        return ordered
    if isinstance(value, (list, tuple)):
        return [_order_json_objects_utf16(entry) for entry in value]
    return value


def canonical_json(value: Any, *, ensure_ascii: bool = True) -> str:
    """Canonical JSON with browser-equivalent UTF-16 object-key ordering."""
    return json.dumps(
        _order_json_objects_utf16(value),
        sort_keys=False,
        separators=(",", ":"),
        ensure_ascii=ensure_ascii,
    )


def canonical_json_bytes_v1(value: Any, *, ensure_ascii: bool = False) -> bytes:
    return canonical_json(value, ensure_ascii=ensure_ascii).encode("utf-8")

def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()

def field_category_v1(entity: str, path: str, node_type: str | None = None) -> str:
    if entity == "node" and node_type == "vibecomfy.exec" and path == "widgets_values.io": return "derived_native"
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
    if isinstance(raw, list): return list(raw)
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
    canonical = project_graph_v1(graph, projection)
    return {"kind": "projection_ref_v1", "projection": projection, "digest": _hash(canonical), "canonical": canonical}

def assert_projection_reference_v1(value: Any, expected: str | None = None) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or value.get("kind") != "projection_ref_v1" or not isinstance(value.get("projection"), str) or not isinstance(value.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["digest"]): raise ContractError("Expected typed projection reference", "invalid_projection_reference")
    projection_spec_v1(value["projection"])
    if expected and value["projection"] != expected: raise ContractError("Projection family mismatch", "projection_family_mismatch")
    if "canonical" in value:
        canonical = value.get("canonical")
        if not isinstance(canonical, Mapping) or canonical.get("projection") != value["projection"]:
            raise ContractError("Projection evidence has the wrong canonical family", "projection_canonical_mismatch")
        if _hash(canonical) != value["digest"]:
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

def _restoration(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("contract_version"), str) or not isinstance(value.get("digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["digest"]) or not ("payload" in value or "ref" in value): raise ContractError("Restoration strategy requires version, digest, payload or ref", "invalid_restoration_strategy")
    return value

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
    _restoration(raw.get("restoration_strategy"))
    return raw

def validate_candidate_authority_v1(raw: Any, *, freeze: bool = False) -> Any:
    _validate_candidate_authority_common(raw)
    if raw.get("contract_version") != CANDIDATE_AUTHORITY_V1: raise ContractError("Unsupported candidate authority version", "unknown_authority_version")
    if "generation" in raw or "lease_nonce" in raw: raise ContractError("Candidate authority cannot infer prepare-time identity", "unexpected_prepare_identity")
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

__all__ = [name for name in globals() if name.endswith("_V1") or name in {"ContractError", "DELTA_V1", "DELTA_WIRE_VERSION", "AUTHORITY_RECEIPT_CONTRACT_VERSION", "ROOT_SCOPE", "FIELD_CATEGORIES", "PROJECTIONS_V1", "canonical_json", "canonical_json_bytes_v1", "field_category_v1", "assert_root_scope_v1", "assert_root_graph_v1", "workflow_identity_v1", "node_identity_v1", "group_identity_v1", "issued_identity_v1", "project_graph_v1", "projection_reference_v1", "assert_projection_reference_v1", "build_structural_graph_projection", "structural_graph_hash_compat", "browser_layout_scope_issues_v1", "build_layout_graph_projection", "layout_graph_hash_compat", "validate_candidate_authority_v1", "validate_prepared_authority_v1", "validate_candidate_transaction_v2", "validate_journal_durable_v1", "classify_legacy_migration_v1"}]
