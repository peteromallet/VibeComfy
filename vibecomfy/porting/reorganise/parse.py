"""Strict parser for the M1 ``LayoutPlan v1`` agent contract.

The accepted JSON envelope is intentionally small and documented by
``LAYOUT_PLAN_SCHEMA_V1`` below. M1 uses frozen dataclasses plus this custom
parser/validator path instead of pydantic so diagnostics stay deterministic and
the contract follows the existing manual parser style in
``vibecomfy.porting.edit.ops``.

Important contract boundaries:

* Top-level JSON is ``{"version": 1, "sections": [...]}``.
* Durable node references are canonical arrays shaped ``[scope_path, uid]``;
  bare LiteGraph ids, integer ids, and UID strings are rejected.
* Backend-owned data such as coordinates, topology, links, widgets, node
  payloads, generated consumers, and graph flow fields is never agent-authored.
* Helper/UI nodes use ``helper_placements`` rather than primary section
  ownership.
* LiteGraph UI JSON and the optional layout-store sidecar envelope remain the
  apply-time source of truth. This parser only accepts semantic layout claims;
  it does not compile coordinates, mutate topology, expose CLI/API surfaces, or
  call an LLM.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import ReorganiseDiagnostic
from .plan_types import (
    HELPER_PLACEMENT_EDGE_PATH,
    HELPER_PLACEMENT_INSIDE_SECTION,
    HELPER_PLACEMENT_KINDS,
    HELPER_PLACEMENT_NEAR_CONSUMER,
    HELPER_PLACEMENT_NEAR_PRODUCER,
    LAYOUT_PLAN_VERSION,
    ROLE_HINTS,
    SAMPLER_RELATION_KINDS,
    SECTION_KINDS,
    UNASSIGNED_CLASSIFY_DETERMINISTICALLY,
    UNASSIGNED_POLICIES,
    CanonicalNodeRef,
    HelperPlacement,
    LayoutPlanV1,
    LayoutSection,
    SamplerRelationClaim,
    SharedNodeHome,
)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

_TOP_LEVEL_KEYS = frozenset(
    {
        "version",
        "sections",
        "shared_nodes",
        "helper_placements",
        "sampler_relations",
        "unassigned_policy",
        "notes",
    }
)
_SECTION_KEYS = frozenset({"id", "kind", "nodes", "title", "role_hint", "parent_id", "notes"})
_SHARED_NODE_KEYS = frozenset({"node", "home", "label", "role_hint"})
_HELPER_PLACEMENT_KEYS = frozenset(
    {"helper", "kind", "target", "from", "to", "section_id", "reason"}
)
_SAMPLER_RELATION_KEYS = frozenset({"kind", "samplers", "source", "target", "reason"})
_BACKEND_OWNED_KEYS = frozenset(
    {
        "class_type",
        "consumers",
        "coords",
        "flow",
        "flows",
        "id",
        "link",
        "links",
        "node",
        "node_payload",
        "pos",
        "position",
        "raw_link",
        "raw_node",
        "size",
        "widgets",
        "x",
        "y",
    }
)

LAYOUT_PLAN_SCHEMA_V1: dict[str, Any] = {
    "type": "object",
    "required": ["version", "sections"],
    "additionalProperties": False,
    "properties": {
        "version": {"const": LAYOUT_PLAN_VERSION},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "kind", "nodes"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "kind": {"enum": sorted(SECTION_KINDS)},
                    "nodes": {"type": "array", "items": {"$ref": "#/$defs/canonicalNodeRef"}},
                    "title": {"type": "string"},
                    "role_hint": {"enum": sorted(ROLE_HINTS)},
                    "parent_id": {"type": "string"},
                    "notes": {"type": "string"},
                },
            },
        },
        "shared_nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["node", "home"],
                "additionalProperties": False,
                "properties": {
                    "node": {"$ref": "#/$defs/canonicalNodeRef"},
                    "home": {"type": "string", "minLength": 1},
                    "label": {"type": "string"},
                    "role_hint": {"enum": sorted(ROLE_HINTS)},
                },
            },
        },
        "helper_placements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["helper", "kind"],
                "additionalProperties": False,
                "properties": {
                    "helper": {"$ref": "#/$defs/canonicalNodeRef"},
                    "kind": {"enum": sorted(HELPER_PLACEMENT_KINDS)},
                    "target": {"$ref": "#/$defs/canonicalNodeRef"},
                    "from": {"$ref": "#/$defs/canonicalNodeRef"},
                    "to": {"$ref": "#/$defs/canonicalNodeRef"},
                    "section_id": {"type": "string", "minLength": 1},
                    "reason": {"type": "string"},
                },
            },
        },
        "sampler_relations": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["kind", "samplers"],
                "additionalProperties": False,
                "properties": {
                    "kind": {"enum": sorted(SAMPLER_RELATION_KINDS)},
                    "samplers": {"type": "array", "items": {"$ref": "#/$defs/canonicalNodeRef"}},
                    "source": {"$ref": "#/$defs/canonicalNodeRef"},
                    "target": {"$ref": "#/$defs/canonicalNodeRef"},
                    "reason": {"type": "string"},
                },
            },
        },
        "unassigned_policy": {"enum": sorted(UNASSIGNED_POLICIES)},
        "notes": {"type": "string"},
    },
    "$defs": {
        "canonicalNodeRef": {
            "type": "array",
            "prefixItems": [
                {"type": "string", "description": "scope path; empty string means root scope"},
                {"type": "string", "minLength": 1, "description": "stable node uid"},
            ],
            "minItems": 2,
            "maxItems": 2,
        }
    },
}


class LayoutPlanParseError(ValueError):
    """Raised when LayoutPlan v1 JSON does not match the strict contract."""

    def __init__(self, diagnostics: Sequence[ReorganiseDiagnostic]):
        self.diagnostics = tuple(diagnostics)
        message = self.diagnostics[0].message if self.diagnostics else "Invalid LayoutPlan v1."
        super().__init__(message)

    def to_json(self) -> dict[str, Any]:
        return {"diagnostics": [diagnostic.to_json() for diagnostic in self.diagnostics]}


def _path_label(path: Sequence[str | int]) -> str:
    if not path:
        return "$"
    label = "$"
    for item in path:
        if isinstance(item, int):
            label += f"[{item}]"
        else:
            label += f".{item}"
    return label


def _diag(
    code: str,
    message: str,
    *,
    path: Sequence[str | int] = (),
    detail: Mapping[str, Any] | None = None,
) -> ReorganiseDiagnostic:
    return ReorganiseDiagnostic(code=code, message=message, path=tuple(path), detail=detail or {})


def _extract_json_object(text: str) -> dict[str, Any] | list[Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        match = _JSON_FENCE_RE.search(stripped)
        if match:
            stripped = match.group(1).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        start = stripped.find("{")
        if start == -1:
            raise LayoutPlanParseError(
                (
                    _diag(
                        "invalid_json",
                        "LayoutPlan v1 response was not valid JSON.",
                    ),
                )
            ) from exc
        try:
            parsed, _ = json.JSONDecoder().raw_decode(stripped[start:])
        except json.JSONDecodeError:
            raise LayoutPlanParseError(
                (
                    _diag(
                        "invalid_json",
                        "LayoutPlan v1 response was not valid JSON.",
                    ),
                )
            ) from exc
    if not isinstance(parsed, (dict, list)):
        raise LayoutPlanParseError(
            (
                _diag(
                    "invalid_plan_object",
                    "LayoutPlan v1 response must be a JSON object.",
                ),
            )
        )
    return parsed


def _as_mapping(value: Any, *, path: Sequence[str | int], diagnostics: list[ReorganiseDiagnostic]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        diagnostics.append(
            _diag(
                "invalid_object",
                f"{_path_label(path)} must be an object.",
                path=path,
                detail={"actual_type": type(value).__name__},
            )
        )
        return None
    return dict(value)


def _as_array(value: Any, *, path: Sequence[str | int], diagnostics: list[ReorganiseDiagnostic]) -> list[Any] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        diagnostics.append(
            _diag(
                "invalid_array",
                f"{_path_label(path)} must be an array.",
                path=path,
                detail={"actual_type": type(value).__name__},
            )
        )
        return None
    return list(value)


def _string(
    value: Any,
    *,
    path: Sequence[str | int],
    diagnostics: list[ReorganiseDiagnostic],
    allow_empty: bool = False,
) -> str | None:
    if not isinstance(value, str):
        diagnostics.append(
            _diag(
                "invalid_string",
                f"{_path_label(path)} must be a string.",
                path=path,
                detail={"actual_type": type(value).__name__},
            )
        )
        return None
    if not allow_empty and not value:
        diagnostics.append(
            _diag(
                "empty_string",
                f"{_path_label(path)} must be a non-empty string.",
                path=path,
            )
        )
        return None
    return value


def _optional_string(
    data: Mapping[str, Any],
    key: str,
    *,
    path: Sequence[str | int],
    diagnostics: list[ReorganiseDiagnostic],
) -> str | None:
    if key not in data or data[key] is None:
        return None
    return _string(data[key], path=(*path, key), diagnostics=diagnostics)


def _missing(
    data: Mapping[str, Any],
    key: str,
    *,
    path: Sequence[str | int],
    diagnostics: list[ReorganiseDiagnostic],
) -> bool:
    if key in data:
        return False
    diagnostics.append(
        _diag(
            "missing_required_field",
            f"{_path_label((*path, key))} is required.",
            path=(*path, key),
        )
    )
    return True


def _reject_keys(
    data: Mapping[str, Any],
    *,
    allowed: frozenset[str],
    path: Sequence[str | int],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    for key in data:
        if key in allowed:
            continue
        if key in _BACKEND_OWNED_KEYS:
            diagnostics.append(
                _diag(
                    "backend_owned_field",
                    f"{_path_label((*path, key))} is backend-owned and is not part of LayoutPlan v1.",
                    path=(*path, key),
                    detail={"field": key},
                )
            )
            continue
        diagnostics.append(
            _diag(
                "unknown_field",
                f"{_path_label((*path, key))} is not allowed in LayoutPlan v1.",
                path=(*path, key),
                detail={"field": key},
            )
        )


def _parse_ref(
    value: Any,
    *,
    path: Sequence[str | int],
    diagnostics: list[ReorganiseDiagnostic],
) -> CanonicalNodeRef | None:
    if isinstance(value, str) or (isinstance(value, int) and not isinstance(value, bool)):
        diagnostics.append(
            _diag(
                "bare_ref_not_allowed",
                f"{_path_label(path)} must be a canonical [scope_path, uid] ref array.",
                path=path,
            )
        )
        return None
    items = _as_array(value, path=path, diagnostics=diagnostics)
    if items is None:
        return None
    if len(items) != 2:
        diagnostics.append(
            _diag(
                "invalid_ref",
                f"{_path_label(path)} must be a canonical [scope_path, uid] ref array.",
                path=path,
                detail={"expected_length": 2, "actual_length": len(items)},
            )
        )
        return None
    scope_path = _string(items[0], path=(*path, 0), diagnostics=diagnostics, allow_empty=True)
    uid = _string(items[1], path=(*path, 1), diagnostics=diagnostics)
    if scope_path is None or uid is None:
        return None
    return CanonicalNodeRef(scope_path=scope_path, uid=uid)


def _parse_ref_array(
    value: Any,
    *,
    path: Sequence[str | int],
    diagnostics: list[ReorganiseDiagnostic],
) -> tuple[CanonicalNodeRef, ...]:
    items = _as_array(value, path=path, diagnostics=diagnostics)
    if items is None:
        return ()
    parsed: list[CanonicalNodeRef] = []
    for index, item in enumerate(items):
        ref = _parse_ref(item, path=(*path, index), diagnostics=diagnostics)
        if ref is not None:
            parsed.append(ref)
    return tuple(parsed)


def _parse_role_hint(
    data: Mapping[str, Any],
    *,
    path: Sequence[str | int],
    diagnostics: list[ReorganiseDiagnostic],
) -> str | None:
    if "role_hint" not in data or data["role_hint"] is None:
        return None
    role_hint = _string(data["role_hint"], path=(*path, "role_hint"), diagnostics=diagnostics)
    if role_hint is None:
        return None
    if role_hint not in ROLE_HINTS:
        diagnostics.append(
            _diag(
                "unknown_role_hint",
                f"{_path_label((*path, 'role_hint'))} must be one of: {', '.join(sorted(ROLE_HINTS))}.",
                path=(*path, "role_hint"),
                detail={"value": role_hint},
            )
        )
        return None
    return role_hint


def _parse_sections(value: Any, *, diagnostics: list[ReorganiseDiagnostic]) -> tuple[LayoutSection, ...]:
    items = _as_array(value, path=("sections",), diagnostics=diagnostics)
    if items is None:
        return ()
    parsed: list[LayoutSection] = []
    for index, item in enumerate(items):
        path = ("sections", index)
        data = _as_mapping(item, path=path, diagnostics=diagnostics)
        if data is None:
            continue
        _reject_keys(data, allowed=_SECTION_KEYS, path=path, diagnostics=diagnostics)
        has_required_issue = any(
            _missing(data, key, path=path, diagnostics=diagnostics)
            for key in ("id", "kind", "nodes")
        )
        section_id = _string(data.get("id"), path=(*path, "id"), diagnostics=diagnostics) if "id" in data else None
        kind = _string(data.get("kind"), path=(*path, "kind"), diagnostics=diagnostics) if "kind" in data else None
        if kind is not None and kind not in SECTION_KINDS:
            diagnostics.append(
                _diag(
                    "unknown_section_kind",
                    f"{_path_label((*path, 'kind'))} must be one of: {', '.join(sorted(SECTION_KINDS))}.",
                    path=(*path, "kind"),
                    detail={"value": kind},
                )
            )
            kind = None
        nodes = _parse_ref_array(data.get("nodes"), path=(*path, "nodes"), diagnostics=diagnostics) if "nodes" in data else ()
        role_hint = _parse_role_hint(data, path=path, diagnostics=diagnostics)
        title = _optional_string(data, "title", path=path, diagnostics=diagnostics)
        parent_id = _optional_string(data, "parent_id", path=path, diagnostics=diagnostics)
        notes = _optional_string(data, "notes", path=path, diagnostics=diagnostics)
        if has_required_issue or section_id is None or kind is None:
            continue
        parsed.append(
            LayoutSection(
                id=section_id,
                kind=kind,  # type: ignore[arg-type]
                nodes=nodes,
                title=title,
                role_hint=role_hint,  # type: ignore[arg-type]
                parent_id=parent_id,
                notes=notes,
            )
        )
    return tuple(parsed)


def _parse_shared_nodes(value: Any, *, diagnostics: list[ReorganiseDiagnostic]) -> tuple[SharedNodeHome, ...]:
    if value is None:
        return ()
    items = _as_array(value, path=("shared_nodes",), diagnostics=diagnostics)
    if items is None:
        return ()
    parsed: list[SharedNodeHome] = []
    for index, item in enumerate(items):
        path = ("shared_nodes", index)
        data = _as_mapping(item, path=path, diagnostics=diagnostics)
        if data is None:
            continue
        _reject_keys(data, allowed=_SHARED_NODE_KEYS, path=path, diagnostics=diagnostics)
        has_required_issue = any(
            _missing(data, key, path=path, diagnostics=diagnostics) for key in ("node", "home")
        )
        node = _parse_ref(data.get("node"), path=(*path, "node"), diagnostics=diagnostics) if "node" in data else None
        home = _string(data.get("home"), path=(*path, "home"), diagnostics=diagnostics) if "home" in data else None
        label = _optional_string(data, "label", path=path, diagnostics=diagnostics)
        role_hint = _parse_role_hint(data, path=path, diagnostics=diagnostics)
        if has_required_issue or node is None or home is None:
            continue
        parsed.append(
            SharedNodeHome(
                node=node,
                home=home,
                label=label,
                role_hint=role_hint,  # type: ignore[arg-type]
            )
        )
    return tuple(parsed)


def _parse_helper_placements(value: Any, *, diagnostics: list[ReorganiseDiagnostic]) -> tuple[HelperPlacement, ...]:
    if value is None:
        return ()
    items = _as_array(value, path=("helper_placements",), diagnostics=diagnostics)
    if items is None:
        return ()
    parsed: list[HelperPlacement] = []
    for index, item in enumerate(items):
        path = ("helper_placements", index)
        data = _as_mapping(item, path=path, diagnostics=diagnostics)
        if data is None:
            continue
        _reject_keys(data, allowed=_HELPER_PLACEMENT_KEYS, path=path, diagnostics=diagnostics)
        has_required_issue = any(
            _missing(data, key, path=path, diagnostics=diagnostics) for key in ("helper", "kind")
        )
        helper = _parse_ref(data.get("helper"), path=(*path, "helper"), diagnostics=diagnostics) if "helper" in data else None
        kind = _string(data.get("kind"), path=(*path, "kind"), diagnostics=diagnostics) if "kind" in data else None
        if kind is not None and kind not in HELPER_PLACEMENT_KINDS:
            diagnostics.append(
                _diag(
                    "unknown_helper_placement_kind",
                    f"{_path_label((*path, 'kind'))} must be one of: {', '.join(sorted(HELPER_PLACEMENT_KINDS))}.",
                    path=(*path, "kind"),
                    detail={"value": kind},
                )
            )
            kind = None
        target = _parse_ref(data["target"], path=(*path, "target"), diagnostics=diagnostics) if "target" in data else None
        source = _parse_ref(data["from"], path=(*path, "from"), diagnostics=diagnostics) if "from" in data else None
        destination = _parse_ref(data["to"], path=(*path, "to"), diagnostics=diagnostics) if "to" in data else None
        section_id = _optional_string(data, "section_id", path=path, diagnostics=diagnostics)
        reason = _optional_string(data, "reason", path=path, diagnostics=diagnostics)
        if kind in {HELPER_PLACEMENT_NEAR_PRODUCER, HELPER_PLACEMENT_NEAR_CONSUMER} and "target" not in data:
            diagnostics.append(
                _diag(
                    "missing_helper_target",
                    f"{_path_label((*path, 'target'))} is required for helper placement kind {kind!r}.",
                    path=(*path, "target"),
                    detail={"kind": kind},
                )
            )
        if kind == HELPER_PLACEMENT_EDGE_PATH:
            for key in ("from", "to"):
                if key not in data:
                    diagnostics.append(
                        _diag(
                            "missing_helper_edge_endpoint",
                            f"{_path_label((*path, key))} is required for helper placement kind 'edge-path'.",
                            path=(*path, key),
                            detail={"kind": kind},
                        )
                    )
        if kind == HELPER_PLACEMENT_INSIDE_SECTION and "section_id" not in data:
            diagnostics.append(
                _diag(
                    "missing_helper_section",
                    f"{_path_label((*path, 'section_id'))} is required for helper placement kind 'inside-section'.",
                    path=(*path, "section_id"),
                    detail={"kind": kind},
                )
            )
        if has_required_issue or helper is None or kind is None:
            continue
        parsed.append(
            HelperPlacement(
                helper=helper,
                kind=kind,  # type: ignore[arg-type]
                target=target,
                source=source,
                destination=destination,
                section_id=section_id,
                reason=reason,
            )
        )
    return tuple(parsed)


def _parse_sampler_relations(value: Any, *, diagnostics: list[ReorganiseDiagnostic]) -> tuple[SamplerRelationClaim, ...]:
    if value is None:
        return ()
    items = _as_array(value, path=("sampler_relations",), diagnostics=diagnostics)
    if items is None:
        return ()
    parsed: list[SamplerRelationClaim] = []
    for index, item in enumerate(items):
        path = ("sampler_relations", index)
        data = _as_mapping(item, path=path, diagnostics=diagnostics)
        if data is None:
            continue
        _reject_keys(data, allowed=_SAMPLER_RELATION_KEYS, path=path, diagnostics=diagnostics)
        has_required_issue = any(
            _missing(data, key, path=path, diagnostics=diagnostics) for key in ("kind", "samplers")
        )
        kind = _string(data.get("kind"), path=(*path, "kind"), diagnostics=diagnostics) if "kind" in data else None
        if kind is not None and kind not in SAMPLER_RELATION_KINDS:
            diagnostics.append(
                _diag(
                    "unknown_sampler_relation_kind",
                    f"{_path_label((*path, 'kind'))} must be one of: {', '.join(sorted(SAMPLER_RELATION_KINDS))}.",
                    path=(*path, "kind"),
                    detail={"value": kind},
                )
            )
            kind = None
        samplers = _parse_ref_array(data.get("samplers"), path=(*path, "samplers"), diagnostics=diagnostics) if "samplers" in data else ()
        source = _parse_ref(data["source"], path=(*path, "source"), diagnostics=diagnostics) if "source" in data else None
        target = _parse_ref(data["target"], path=(*path, "target"), diagnostics=diagnostics) if "target" in data else None
        reason = _optional_string(data, "reason", path=path, diagnostics=diagnostics)
        if has_required_issue or kind is None:
            continue
        parsed.append(
            SamplerRelationClaim(
                kind=kind,  # type: ignore[arg-type]
                samplers=samplers,
                source=source,
                target=target,
                reason=reason,
            )
        )
    return tuple(parsed)


def parse_layout_plan(payload: Any) -> LayoutPlanV1:
    if isinstance(payload, str):
        raw = _extract_json_object(payload)
    else:
        raw = payload

    diagnostics: list[ReorganiseDiagnostic] = []
    data = _as_mapping(raw, path=(), diagnostics=diagnostics)
    if data is None:
        raise LayoutPlanParseError(diagnostics)

    _reject_keys(data, allowed=_TOP_LEVEL_KEYS, path=(), diagnostics=diagnostics)
    for key in ("version", "sections"):
        _missing(data, key, path=(), diagnostics=diagnostics)

    version = data.get("version")
    if "version" in data:
        if isinstance(version, bool) or not isinstance(version, int):
            diagnostics.append(
                _diag(
                    "invalid_version",
                    "$.version must be integer 1.",
                    path=("version",),
                    detail={"value": version},
                )
            )
            version = None
        elif version != LAYOUT_PLAN_VERSION:
            diagnostics.append(
                _diag(
                    "unsupported_version",
                    "$.version must be 1.",
                    path=("version",),
                    detail={"value": version},
                )
            )
            version = None

    sections = _parse_sections(data.get("sections"), diagnostics=diagnostics) if "sections" in data else ()
    shared_nodes = _parse_shared_nodes(data.get("shared_nodes"), diagnostics=diagnostics)
    helper_placements = _parse_helper_placements(data.get("helper_placements"), diagnostics=diagnostics)
    sampler_relations = _parse_sampler_relations(data.get("sampler_relations"), diagnostics=diagnostics)

    unassigned_policy = data.get("unassigned_policy", UNASSIGNED_CLASSIFY_DETERMINISTICALLY)
    if "unassigned_policy" in data:
        parsed_policy = _string(
            unassigned_policy,
            path=("unassigned_policy",),
            diagnostics=diagnostics,
        )
        if parsed_policy is not None and parsed_policy not in UNASSIGNED_POLICIES:
            diagnostics.append(
                _diag(
                    "unknown_unassigned_policy",
                    f"$.unassigned_policy must be one of: {', '.join(sorted(UNASSIGNED_POLICIES))}.",
                    path=("unassigned_policy",),
                    detail={"value": parsed_policy},
                )
            )
            parsed_policy = None
        unassigned_policy = parsed_policy

    notes = _optional_string(data, "notes", path=(), diagnostics=diagnostics)
    if diagnostics:
        raise LayoutPlanParseError(diagnostics)

    return LayoutPlanV1(
        version=version,
        sections=sections,
        shared_nodes=shared_nodes,
        helper_placements=helper_placements,
        sampler_relations=sampler_relations,
        unassigned_policy=unassigned_policy or UNASSIGNED_CLASSIFY_DETERMINISTICALLY,
        notes=notes,
    )


__all__ = [
    "LAYOUT_PLAN_SCHEMA_V1",
    "LayoutPlanParseError",
    "parse_layout_plan",
]
