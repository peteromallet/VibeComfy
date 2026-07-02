from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Mapping, Sequence

from vibecomfy.identity.uid import SCOPE_CHAIN_JOIN

from .classify import classify_layout_facts
from .diagnostics import (
    DIAGNOSTIC_SEVERITY_INFO,
    ReorganiseDiagnostic,
    ReorganiseDiagnosticReport,
)
from .graph_facts import GraphInventoryFacts, extract_graph_facts
from .plan_types import (
    HELPER_PLACEMENT_EDGE_PATH,
    HELPER_PLACEMENT_INSIDE_SECTION,
    HELPER_PLACEMENT_NEAR_CONSUMER,
    HELPER_PLACEMENT_NEAR_PRODUCER,
    SECTION_KIND_CONTAINER,
    UNASSIGNED_CLASSIFY_DETERMINISTICALLY,
    UNASSIGNED_PRESERVE_EXISTING,
    UNASSIGNED_REJECT,
    CanonicalNodeRef,
    LayoutPlanV1,
)


@dataclass(frozen=True, slots=True)
class _OwnershipClaim:
    ref: CanonicalNodeRef
    section_id: str
    path: tuple[str | int, ...]
    channel: str


@dataclass(frozen=True, slots=True)
class _SectionSemantic:
    section_id: str
    kind: str
    parent_id: str | None
    node_refs: tuple[CanonicalNodeRef, ...]
    path: tuple[str | int, ...]


_FORBIDDEN_SEMANTIC_PAYLOAD_KEYS = frozenset(
    {
        "coords",
        "edges",
        "flow",
        "flows",
        "input",
        "inputs",
        "link",
        "links",
        "node_payload",
        "output",
        "outputs",
        "pos",
        "position",
        "raw_link",
        "raw_node",
        "size",
        "topology",
        "widget",
        "widgets",
        "x",
        "y",
    }
)


def validate_layout_plan(
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
) -> ReorganiseDiagnosticReport:
    """Validate LayoutPlan v1 references, ownership, and semantic claims.

    This pass is intentionally read-only. It does not infer coordinates,
    rewrite graph topology, or mutate the parsed plan or graph facts.
    """

    diagnostics: list[ReorganiseDiagnostic] = []
    _validate_forbidden_payloads(plan, diagnostics)
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    known_refs = set(canonical_by_ref)
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    section_ids = _section_ids(plan, diagnostics)
    sections = _section_semantics(plan)
    ownerships: list[_OwnershipClaim] = []

    for section_index, section in enumerate(plan.sections):
        section_path = ("sections", section_index)
        section_id = getattr(section, "id", None)
        if not isinstance(section_id, str) or not section_id:
            continue
        parent_id = getattr(section, "parent_id", None)
        if parent_id is not None and parent_id not in section_ids:
            diagnostics.append(
                _diag(
                    "unknown_section_id",
                    f"Section parent_id {parent_id!r} does not refer to a known section.",
                    path=(*section_path, "parent_id"),
                    detail={"section_id": parent_id},
                )
            )
        for node_index, raw_ref in enumerate(getattr(section, "nodes", ())):
            path = (*section_path, "nodes", node_index)
            ref = _validate_ref(raw_ref, path=path, known_refs=known_refs, diagnostics=diagnostics)
            if ref is None:
                continue
            if ref in helper_refs:
                diagnostics.append(
                    _diag(
                        "helper_primary_ownership",
                        "Helper/UI nodes must use helper_placements, not primary section ownership.",
                        path=path,
                        detail={"ref": ref.to_json(), "section_id": section_id},
                    )
                )
                continue
            ownerships.append(
                _OwnershipClaim(
                    ref=ref,
                    section_id=section_id,
                    path=path,
                    channel="sections.nodes",
                )
            )

    for shared_index, raw_shared in enumerate(plan.shared_nodes):
        shared_path = ("shared_nodes", shared_index)
        if _has_backend_consumers(raw_shared):
            diagnostics.append(
                _diag(
                    "backend_owned_field",
                    "shared_nodes.consumers is backend-derived and is not agent-authored in LayoutPlan v1.",
                    path=(*shared_path, "consumers"),
                    detail={"field": "consumers"},
                )
            )
        ref = _validate_ref(
            _field(raw_shared, "node"),
            path=(*shared_path, "node"),
            known_refs=known_refs,
            diagnostics=diagnostics,
        )
        home = _field(raw_shared, "home")
        if not isinstance(home, str) or not home:
            diagnostics.append(
                _diag(
                    "invalid_section_id",
                    "shared_nodes.home must be a non-empty section id.",
                    path=(*shared_path, "home"),
                    detail={"value": home},
                )
            )
            home = None
        elif home not in section_ids:
            diagnostics.append(
                _diag(
                    "unknown_section_id",
                    f"shared_nodes.home {home!r} does not refer to a known section.",
                    path=(*shared_path, "home"),
                    detail={"section_id": home},
                )
            )
        if ref is None or home is None:
            continue
        if ref in helper_refs:
            diagnostics.append(
                _diag(
                    "helper_primary_ownership",
                    "Helper/UI nodes must use helper_placements, not shared-node primary ownership.",
                    path=(*shared_path, "node"),
                    detail={"ref": ref.to_json(), "section_id": home},
                )
            )
            continue
        ownerships.append(
            _OwnershipClaim(
                ref=ref,
                section_id=home,
                path=(*shared_path, "node"),
                channel="shared_nodes.home",
            )
        )

    _validate_helper_placements(plan, sections, section_ids, known_refs, helper_refs, diagnostics)
    _validate_section_scope_boundaries(sections, diagnostics)
    _validate_sampler_relations(plan, facts, canonical_by_ref, known_refs, diagnostics)
    _validate_ownership_counts(plan, facts, ownerships, helper_refs, diagnostics)

    return ReorganiseDiagnosticReport(ok=not _has_error(diagnostics), diagnostics=tuple(diagnostics))


def validate_layout_plan_from_ui(
    plan: LayoutPlanV1,
    ui_json: Mapping[str, Any],
    *,
    sidecar_envelope: Mapping[str, Any] | None = None,
) -> ReorganiseDiagnosticReport:
    return validate_layout_plan(
        plan,
        extract_graph_facts(ui_json, sidecar_envelope=sidecar_envelope),
    )


def _section_ids(
    plan: LayoutPlanV1,
    diagnostics: list[ReorganiseDiagnostic],
) -> frozenset[str]:
    seen: dict[str, tuple[str | int, ...]] = {}
    ids: set[str] = set()
    for index, section in enumerate(plan.sections):
        path = ("sections", index, "id")
        section_id = getattr(section, "id", None)
        if not isinstance(section_id, str) or not section_id:
            diagnostics.append(
                _diag(
                    "invalid_section_id",
                    "Section id must be a non-empty string.",
                    path=path,
                    detail={"value": section_id},
                )
            )
            continue
        if section_id in seen:
            diagnostics.append(
                _diag(
                    "duplicate_section_id",
                    f"Section id {section_id!r} is declared more than once.",
                    path=path,
                    detail={"section_id": section_id, "first_path": list(seen[section_id])},
                )
            )
        else:
            seen[section_id] = path
        ids.add(section_id)
    return frozenset(ids)


def _section_semantics(plan: LayoutPlanV1) -> tuple[_SectionSemantic, ...]:
    sections: list[_SectionSemantic] = []
    for index, section in enumerate(plan.sections):
        section_id = _field(section, "id")
        kind = _field(section, "kind")
        if not isinstance(section_id, str) or not section_id:
            continue
        nodes = _field(section, "nodes")
        refs = tuple(ref for ref in nodes if isinstance(ref, CanonicalNodeRef)) if _is_sequence(nodes) else ()
        sections.append(
            _SectionSemantic(
                section_id=section_id,
                kind=kind if isinstance(kind, str) else "",
                parent_id=_field(section, "parent_id") if isinstance(_field(section, "parent_id"), str) else None,
                node_refs=refs,
                path=("sections", index),
            )
        )
    return tuple(sections)


def _validate_helper_placements(
    plan: LayoutPlanV1,
    sections: Sequence[_SectionSemantic],
    section_ids: frozenset[str],
    known_refs: set[CanonicalNodeRef],
    helper_refs: set[CanonicalNodeRef],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    section_scope_by_id = {
        section.section_id: section.node_refs[0].scope_path
        for section in sections
        if len({ref.scope_path for ref in section.node_refs}) == 1 and section.node_refs
    }
    for index, placement in enumerate(plan.helper_placements):
        base = ("helper_placements", index)
        helper = _validate_ref(
            _field(placement, "helper"),
            path=(*base, "helper"),
            known_refs=known_refs,
            diagnostics=diagnostics,
        )
        if helper is not None and helper not in helper_refs:
            diagnostics.append(
                _diag(
                    "invalid_helper_placement_helper",
                    "helper_placements.helper must refer to a helper/UI node.",
                    path=(*base, "helper"),
                    detail={"ref": helper.to_json()},
                )
            )

        target = _validate_optional_endpoint(
            placement,
            "target",
            (*base, "target"),
            known_refs,
            helper_refs,
            diagnostics,
        )
        source = _validate_optional_endpoint(
            placement,
            "source",
            (*base, "from"),
            known_refs,
            helper_refs,
            diagnostics,
        )
        destination = _validate_optional_endpoint(
            placement,
            "destination",
            (*base, "to"),
            known_refs,
            helper_refs,
            diagnostics,
        )

        section_id = _field(placement, "section_id")
        if section_id is not None:
            if not isinstance(section_id, str) or not section_id:
                diagnostics.append(
                    _diag(
                        "invalid_section_id",
                        "helper_placements.section_id must be a non-empty section id.",
                        path=(*base, "section_id"),
                        detail={"value": section_id},
                    )
                )
            elif section_id not in section_ids:
                diagnostics.append(
                    _diag(
                        "unknown_section_id",
                        f"helper_placements.section_id {section_id!r} does not refer to a known section.",
                        path=(*base, "section_id"),
                        detail={"section_id": section_id},
                    )
                )
        kind = _field(placement, "kind")
        _validate_helper_shape(kind, placement, base, diagnostics)
        if helper is not None and section_id in section_scope_by_id:
            section_scope = section_scope_by_id[section_id]
            if helper.scope_path != section_scope:
                diagnostics.append(
                    _diag(
                        "helper_scope_mismatch",
                        "helper_placements.helper must stay inside the section scope it is placed in.",
                        path=(*base, "helper"),
                        detail={
                            "helper": helper.to_json(),
                            "section_id": section_id,
                            "section_scope": section_scope,
                        },
                    )
                )
        if source is not None and destination is not None:
            if source == destination or source.scope_path != destination.scope_path:
                diagnostics.append(
                    _diag(
                        "invalid_helper_target",
                        "edge-path helper endpoints must be distinct non-helper nodes in the same scope.",
                        path=base,
                        detail={"from": source.to_json(), "to": destination.to_json()},
                    )
                )
        if helper is not None:
            for field_name, endpoint in (
                ("target", target),
                ("from", source),
                ("to", destination),
            ):
                if endpoint is not None and endpoint.scope_path != helper.scope_path:
                    diagnostics.append(
                        _diag(
                            "helper_scope_mismatch",
                            "helper placement endpoints must stay in the helper node scope.",
                            path=(*base, field_name),
                            detail={"helper": helper.to_json(), "endpoint": endpoint.to_json()},
                        )
                    )


def _validate_optional_endpoint(
    placement: Any,
    attr_name: str,
    path: tuple[str | int, ...],
    known_refs: set[CanonicalNodeRef],
    helper_refs: set[CanonicalNodeRef],
    diagnostics: list[ReorganiseDiagnostic],
) -> CanonicalNodeRef | None:
    ref = _field(placement, attr_name)
    if ref is None:
        return None
    parsed = _validate_ref(ref, path=path, known_refs=known_refs, diagnostics=diagnostics)
    if parsed is not None and parsed in helper_refs:
        diagnostics.append(
            _diag(
                "invalid_helper_target",
                "helper placement targets must refer to non-helper graph nodes.",
                path=path,
                detail={"ref": parsed.to_json()},
            )
        )
    return parsed


def _validate_helper_shape(
    kind: Any,
    placement: Any,
    base: tuple[str | int, ...],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    present = {
        name
        for name in ("target", "source", "destination", "section_id")
        if _field(placement, name) is not None
    }
    if kind in {HELPER_PLACEMENT_NEAR_PRODUCER, HELPER_PLACEMENT_NEAR_CONSUMER}:
        required = {"target"}
        allowed = {"target"}
    elif kind == HELPER_PLACEMENT_EDGE_PATH:
        required = {"source", "destination"}
        allowed = {"source", "destination"}
    elif kind == HELPER_PLACEMENT_INSIDE_SECTION:
        required = {"section_id"}
        allowed = {"section_id"}
    else:
        return
    missing = sorted(required - present)
    extra = sorted(present - allowed)
    if missing or extra:
        diagnostics.append(
            _diag(
                "invalid_helper_placement_shape",
                "helper placement fields do not match the declared placement kind.",
                path=base,
                detail={
                    "kind": kind,
                    "missing": [_json_field_name(item) for item in missing],
                    "forbidden": [_json_field_name(item) for item in extra],
                },
            )
        )


def _validate_section_scope_boundaries(
    sections: Sequence[_SectionSemantic],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    by_id = {section.section_id: section for section in sections}
    for section in sections:
        scopes = {ref.scope_path for ref in section.node_refs}
        if len(scopes) > 1:
            diagnostics.append(
                _diag(
                    "cross_scope_primary_ownership",
                    "Primary section ownership must not mix nodes from different graph scopes.",
                    path=(*section.path, "nodes"),
                    detail={"section_id": section.section_id, "scopes": sorted(scopes)},
                )
            )
            continue
        if not scopes:
            continue
        scope_path = next(iter(scopes))
        if scope_path == "":
            continue
        parent = by_id.get(section.parent_id or "")
        parent_scope = _parent_scope(scope_path)
        parent_scopes = {ref.scope_path for ref in parent.node_refs} if parent is not None else set()
        if (
            parent is None
            or parent.kind != SECTION_KIND_CONTAINER
            or parent_scopes != {parent_scope}
        ):
            diagnostics.append(
                _diag(
                    "subgraph_boundary_violation",
                    "Subgraph-scoped primary sections must sit under a parent-scope container section.",
                    path=(*section.path, "parent_id"),
                    detail={
                        "section_id": section.section_id,
                        "scope_path": scope_path,
                        "expected_parent_scope": parent_scope,
                        "parent_id": section.parent_id,
                    },
                )
            )


def _validate_sampler_relations(
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    canonical_by_ref: Mapping[CanonicalNodeRef, Any],
    known_refs: set[CanonicalNodeRef],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    topology_relations = _topology_sampler_relations(facts)
    for relation_index, relation in enumerate(plan.sampler_relations):
        base = ("sampler_relations", relation_index)
        samplers = _field(relation, "samplers")
        parsed_samplers: list[CanonicalNodeRef] = []
        if isinstance(samplers, Sequence) and not isinstance(samplers, (str, bytes)):
            for sampler_index, raw_ref in enumerate(samplers):
                ref = _validate_ref(
                    raw_ref,
                    path=(*base, "samplers", sampler_index),
                    known_refs=known_refs,
                    diagnostics=diagnostics,
                )
                if ref is not None:
                    parsed_samplers.append(ref)
        else:
            diagnostics.append(
                _diag(
                    "bare_ref_not_allowed",
                    "sampler_relations.samplers must contain canonical [scope_path, uid] refs parsed into CanonicalNodeRef values.",
                    path=(*base, "samplers"),
                    detail={"value": samplers},
                )
            )
        raw_source = _field(relation, "source")
        raw_target = _field(relation, "target")
        source = (
            _validate_ref(
                raw_source,
                path=(*base, "source"),
                known_refs=known_refs,
                diagnostics=diagnostics,
            )
            if raw_source is not None
            else None
        )
        target = (
            _validate_ref(
                raw_target,
                path=(*base, "target"),
                known_refs=known_refs,
                diagnostics=diagnostics,
            )
            if raw_target is not None
            else None
        )
        _validate_sampler_relation_shape(relation, parsed_samplers, source, target, base, diagnostics)
        for ref in parsed_samplers:
            fact = canonical_by_ref.get(ref)
            if fact is not None and "sampler" not in fact.class_type.lower():
                diagnostics.append(
                    _diag(
                        "invalid_sampler_relation_target",
                        "sampler_relations.samplers must refer to sampler nodes.",
                        path=base,
                        detail={"ref": ref.to_json(), "class_type": fact.class_type},
                    )
                )
        if len(parsed_samplers) != 2 or len(set(parsed_samplers)) != 2:
            continue
        if len({ref.scope_path for ref in parsed_samplers}) != 1:
            diagnostics.append(
                _diag(
                    "cross_scope_sampler_relation",
                    "Sampler relation claims cannot cross graph scope boundaries.",
                    path=base,
                    detail={"samplers": [ref.to_json() for ref in parsed_samplers]},
                )
            )
            continue
        _validate_sampler_relation_contradiction(
            relation,
            parsed_samplers,
            source,
            target,
            topology_relations,
            base,
            diagnostics,
        )


def _validate_ownership_counts(
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    ownerships: Sequence[_OwnershipClaim],
    helper_refs: set[CanonicalNodeRef],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    claims_by_ref: dict[CanonicalNodeRef, list[_OwnershipClaim]] = {}
    for claim in ownerships:
        claims_by_ref.setdefault(claim.ref, []).append(claim)

    for ref in sorted(claims_by_ref, key=lambda item: item.to_json()):
        claims = claims_by_ref[ref]
        if len(claims) <= 1:
            continue
        diagnostics.append(
            _diag(
                "duplicate_primary_ownership",
                "Non-helper nodes must have exactly one primary owner.",
                path=claims[1].path,
                detail={
                    "ref": ref.to_json(),
                    "owners": [
                        {
                            "section_id": claim.section_id,
                            "channel": claim.channel,
                            "path": list(claim.path),
                        }
                        for claim in claims
                    ],
                },
            )
        )

    owned_refs = set(claims_by_ref)
    missing_refs = [
        fact.ref
        for fact in facts.canonical_refs
        if fact.ref not in helper_refs and fact.ref not in owned_refs
    ]
    policy = getattr(plan, "unassigned_policy", UNASSIGNED_CLASSIFY_DETERMINISTICALLY)
    if policy == UNASSIGNED_REJECT:
        for ref in missing_refs:
            diagnostics.append(
                _diag(
                    "missing_primary_ownership",
                    "Non-helper node is not owned by any primary section.",
                    detail={"ref": ref.to_json(), "unassigned_policy": policy},
                )
            )
        return
    if policy == UNASSIGNED_CLASSIFY_DETERMINISTICALLY and missing_refs:
        hints = classify_layout_facts(facts, candidate_refs=tuple(missing_refs))
        for hint in hints.hints:
            diagnostics.append(
                _diag(
                    "unassigned_classified_deterministically",
                    "Non-helper node is unassigned and will be handled by deterministic classification.",
                    severity=DIAGNOSTIC_SEVERITY_INFO,
                    detail={
                        "ref": hint.ref.to_json(),
                        "role_hint": hint.role_hint,
                        "confidence": hint.confidence,
                        "reason_codes": list(hint.reason_codes),
                    },
                )
        )
        return
    if policy == UNASSIGNED_PRESERVE_EXISTING:
        for ref in missing_refs:
            diagnostics.append(
                _diag(
                    "unassigned_preserve_existing",
                    "Non-helper node is unassigned and will preserve existing layout ownership.",
                    severity=DIAGNOSTIC_SEVERITY_INFO,
                    detail={"ref": ref.to_json(), "unassigned_policy": policy},
                )
            )


def _validate_forbidden_payloads(
    plan: LayoutPlanV1,
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    for path, key, value in _iter_forbidden_payloads(plan):
        diagnostics.append(
            _diag(
                "forbidden_layout_payload",
                "LayoutPlan v1 is semantic only and must not contain topology or coordinate payloads.",
                path=(*path, key),
                detail={"field": key, "value": value},
            )
        )


def _iter_forbidden_payloads(value: Any) -> list[tuple[tuple[str | int, ...], str, Any]]:
    found: list[tuple[tuple[str | int, ...], str, Any]] = []

    def visit(item: Any, path: tuple[str | int, ...], seen: set[int]) -> None:
        marker = id(item)
        if marker in seen:
            return
        seen.add(marker)
        if isinstance(item, Mapping):
            for key, child in item.items():
                key_text = str(key)
                if key_text in _FORBIDDEN_SEMANTIC_PAYLOAD_KEYS:
                    found.append((path, key_text, child))
                visit(child, (*path, key_text), seen)
            return
        if is_dataclass(item) and not isinstance(item, type):
            for field in fields(item):
                visit(getattr(item, field.name), (*path, _json_field_name(field.name)), seen)
            return
        if _is_sequence(item):
            for index, child in enumerate(item):
                visit(child, (*path, index), seen)

    visit(value, (), set())
    return sorted(found, key=lambda row: _path_sort_key((*row[0], row[1])))


def _validate_sampler_relation_shape(
    relation: Any,
    samplers: Sequence[CanonicalNodeRef],
    source: CanonicalNodeRef | None,
    target: CanonicalNodeRef | None,
    base: tuple[str | int, ...],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    kind = _field(relation, "kind")
    has_source = source is not None
    has_target = target is not None
    errors: list[str] = []
    if len(samplers) != 2 or len(set(samplers)) != 2:
        errors.append("samplers must contain exactly two distinct refs")
    if kind in {"sampler_precedes", "sampler_refines"}:
        if not has_source or not has_target:
            errors.append("source and target are required")
        elif source not in samplers or target not in samplers or source == target:
            errors.append("source and target must be distinct members of samplers")
    elif has_source or has_target:
        errors.append("source and target are only allowed for directed sampler relations")
    if errors:
        diagnostics.append(
            _diag(
                "invalid_sampler_relation_shape",
                "sampler relation fields do not match the declared relation kind.",
                path=base,
                detail={"kind": kind, "errors": errors},
            )
        )


def _validate_sampler_relation_contradiction(
    relation: Any,
    samplers: Sequence[CanonicalNodeRef],
    source: CanonicalNodeRef | None,
    target: CanonicalNodeRef | None,
    topology_relations: Mapping[frozenset[CanonicalNodeRef], tuple[Any, ...]],
    base: tuple[str | int, ...],
    diagnostics: list[ReorganiseDiagnostic],
) -> None:
    key = frozenset(samplers)
    proven = topology_relations.get(key, ())
    if not proven:
        return
    kind = _field(relation, "kind")
    for candidate in proven:
        if _sampler_relation_compatible(kind, source, target, candidate):
            return
    first = proven[0]
    diagnostics.append(
        _diag(
            "sampler_relation_contradiction",
            "Sampler relation claim contradicts topology-derived sampler facts.",
            path=base,
            detail={
                "claimed_kind": kind,
                "claimed_source": source.to_json() if source is not None else None,
                "claimed_target": target.to_json() if target is not None else None,
                "proven": [candidate.to_json() for candidate in proven],
                "scope_path": first.samplers[0].scope_path if first.samplers else "",
            },
        )
    )


def _sampler_relation_compatible(
    kind: Any,
    source: CanonicalNodeRef | None,
    target: CanonicalNodeRef | None,
    candidate: Any,
) -> bool:
    candidate_kind = _field(candidate, "kind")
    if kind in {"sampler_precedes", "sampler_refines"}:
        candidate_source = _field(candidate, "source")
        candidate_target = _field(candidate, "target")
        return (
            candidate_kind == "sampler_precedes"
            and source is not None
            and target is not None
            and candidate_source == source
            and candidate_target == target
        )
    return kind == candidate_kind


def _topology_sampler_relations(
    facts: GraphInventoryFacts,
) -> dict[frozenset[CanonicalNodeRef], tuple[Any, ...]]:
    rows: dict[frozenset[CanonicalNodeRef], list[Any]] = {}
    for topology in facts.scope_topologies:
        for candidate in topology.sampler_relation_candidates:
            if len(candidate.samplers) != 2:
                continue
            rows.setdefault(frozenset(candidate.samplers), []).append(candidate)
    return {
        key: tuple(sorted(values, key=lambda value: _sampler_relation_sort_key(value)))
        for key, values in rows.items()
    }


def _sampler_relation_sort_key(relation: Any) -> tuple[str, str, str, list[list[str]]]:
    source = _field(relation, "source")
    target = _field(relation, "target")
    return (
        str(_field(relation, "kind")),
        _ref_sort_label(source),
        _ref_sort_label(target),
        [ref.to_json() for ref in _field(relation, "samplers") or ()],
    )


def _validate_ref(
    raw_ref: Any,
    *,
    path: tuple[str | int, ...],
    known_refs: set[CanonicalNodeRef],
    diagnostics: list[ReorganiseDiagnostic],
) -> CanonicalNodeRef | None:
    if not isinstance(raw_ref, CanonicalNodeRef):
        diagnostics.append(
            _diag(
                "bare_ref_not_allowed",
                "Node references must be canonical [scope_path, uid] refs parsed into CanonicalNodeRef values.",
                path=path,
                detail={"value": raw_ref},
            )
        )
        return None
    if raw_ref not in known_refs:
        diagnostics.append(
            _diag(
                "unknown_ref",
                "Node reference does not exist in extracted graph facts.",
                path=path,
                detail={"ref": raw_ref.to_json()},
            )
        )
        return None
    return raw_ref


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        if name == "source":
            return value.get("source", value.get("from"))
        if name == "destination":
            return value.get("destination", value.get("to"))
        return value.get(name)
    return getattr(value, name, None)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _json_field_name(name: str) -> str:
    if name == "source":
        return "from"
    if name == "destination":
        return "to"
    return name


def _parent_scope(scope_path: str) -> str:
    if SCOPE_CHAIN_JOIN not in scope_path:
        return ""
    return scope_path.rsplit(SCOPE_CHAIN_JOIN, 1)[0]


def _path_sort_key(path: Sequence[str | int]) -> tuple[str, ...]:
    return tuple(str(item).zfill(8) if isinstance(item, int) else str(item) for item in path)


def _ref_sort_label(ref: Any) -> str:
    if isinstance(ref, CanonicalNodeRef):
        return "\0".join(ref.to_json())
    return ""


def _has_backend_consumers(value: Any) -> bool:
    if isinstance(value, Mapping):
        return "consumers" in value
    return hasattr(value, "consumers")


def _diag(
    code: str,
    message: str,
    *,
    severity: str = "error",
    path: tuple[str | int, ...] = (),
    detail: Mapping[str, Any] | None = None,
) -> ReorganiseDiagnostic:
    return ReorganiseDiagnostic(
        code=code,
        message=message,
        severity=severity,  # type: ignore[arg-type]
        path=path,
        detail=detail or {},
    )


def _has_error(diagnostics: Sequence[ReorganiseDiagnostic]) -> bool:
    return any(diagnostic.severity == "error" for diagnostic in diagnostics)


__all__ = [
    "validate_layout_plan",
    "validate_layout_plan_from_ui",
]
