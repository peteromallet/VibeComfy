"""Evidence-gated reconciliation of historical compact widget slots.

The ordinary widget resolvers answer a deliberately smaller question: what
does a positional slot mean for the schema that is available now?  Import and
preparation sometimes need a stronger answer: whether a value captured from a
*historical* workflow may be moved to a field in today's target schema.

This module is the bounded admission seam for that stronger operation.  It
does not rewrite a node or create another resolver.  It requires an explicit
source roster and source identity, obtains the target roster through the
existing compact resolver, and returns immutable mapping records.  Missing,
conflicting, synthetic, or non-unique evidence is a refusal with repair
guidance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any


_POSITIONAL_NAME = re.compile(r"widget_(\d+)")


def _is_synthetic_name(name: object) -> bool:
    return isinstance(name, str) and _POSITIONAL_NAME.fullmatch(name) is not None


def _nonempty_text(value: object) -> str | None:
    return str(value) if isinstance(value, str) and value.strip() else None


def _safe_equal(left: object, right: object) -> bool:
    try:
        result = left == right
    except Exception:  # noqa: BLE001 - evidence comparison must fail closed
        return False
    return isinstance(result, bool) and result


def _tuple_values(value: object, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be a list or tuple")
    return tuple(deepcopy(item) for item in value)


@dataclass(frozen=True, slots=True)
class HistoricalWidgetEvidence:
    """One captured source roster for one node and source revision.

    ``None`` in ``source_widget_order`` is an intentional hole/UI-only slot.
    A ``widget_N`` spelling is retained as positional evidence but is never
    treated as a semantic field by the admission function.
    """

    source_node_id: str
    class_type: str
    source_widget_order: tuple[str | None, ...]
    source_widget_values: tuple[Any, ...]
    source_revision: str | None
    source_schema_digest: str | None
    source_schema_version: str | None
    source_span: str | None = None
    evidence_source: str = "captured_widget_roster"

    def __post_init__(self) -> None:
        node_id = _nonempty_text(self.source_node_id)
        class_type = _nonempty_text(self.class_type)
        if node_id is None or class_type is None:
            raise ValueError("historical widget evidence requires node id and class type")
        object.__setattr__(self, "source_node_id", node_id)
        object.__setattr__(self, "class_type", class_type)
        order: list[str | None] = []
        for name in self.source_widget_order:
            order.append(name if isinstance(name, str) and name else None)
        object.__setattr__(self, "source_widget_order", tuple(order))
        object.__setattr__(
            self,
            "source_widget_values",
            _tuple_values(self.source_widget_values, "source_widget_values"),
        )
        object.__setattr__(self, "source_revision", _nonempty_text(self.source_revision))
        object.__setattr__(self, "source_schema_digest", _nonempty_text(self.source_schema_digest))
        object.__setattr__(self, "source_schema_version", _nonempty_text(self.source_schema_version))
        object.__setattr__(self, "source_span", _nonempty_text(self.source_span))
        object.__setattr__(
            self,
            "evidence_source",
            _nonempty_text(self.evidence_source) or "captured_widget_roster",
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HistoricalWidgetEvidence":
        """Coerce the stable JSON-shaped evidence used by snapshots/receipts."""
        if not isinstance(value, Mapping):
            raise TypeError("historical widget evidence must be a mapping")
        schema = value.get("source_schema")
        schema = schema if isinstance(schema, Mapping) else {}
        source_revision = (
            value.get("source_revision")
            or value.get("revision")
            or value.get("source_digest")
        )
        return cls(
            source_node_id=(value.get("source_node_id") or value.get("node_id") or value.get("uid") or ""),
            class_type=(value.get("class_type") or value.get("type") or ""),
            source_widget_order=(
                value.get("source_widget_order")
                or value.get("widget_order")
                or value.get("widget_names")
                or value.get("roster")
                or ()
            ),
            source_widget_values=(
                value.get("source_widget_values")
                if value.get("source_widget_values") is not None
                else value.get("widget_values", value.get("values", ()))
            ),
            source_revision=source_revision,
            source_schema_digest=(
                value.get("source_schema_digest")
                or value.get("schema_digest")
                or schema.get("digest")
                or schema.get("hash")
                or schema.get("source_hash")
            ),
            source_schema_version=(
                value.get("source_schema_version")
                or value.get("schema_version")
                or schema.get("version")
                or schema.get("source_version")
            ),
            source_span=(
                value.get("source_span")
                or value.get("span")
                or value.get("python_span")
                or value.get("location")
            ),
            evidence_source=(
                value.get("evidence_source")
                or value.get("provenance_source")
                or value.get("source")
                or "captured_widget_roster"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "class_type": self.class_type,
            "source_widget_order": list(self.source_widget_order),
            "source_widget_values": deepcopy(list(self.source_widget_values)),
            "source_revision": self.source_revision,
            "source_schema_digest": self.source_schema_digest,
            "source_schema_version": self.source_schema_version,
            "source_span": self.source_span,
            "evidence_source": self.evidence_source,
        }


@dataclass(frozen=True, slots=True)
class PreservedWidgetSlot:
    """A source slot deliberately left untouched because it is not semantic."""

    source_widget_index: int
    source_value: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_widget_index": self.source_widget_index,
            "source_value": deepcopy(self.source_value),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class HistoricalWidgetMapping:
    """One uniquely admitted source-index → target-field mapping."""

    source_node_id: str
    class_type: str
    source_span: str | None
    source_revision: str
    source_schema_digest: str | None
    source_schema_version: str | None
    source_widget_index: int
    source_value: Any
    source_field: str
    target_schema_digest: str
    target_widget_order: tuple[str | None, ...]
    target_schema_generation: str
    target_widget_index: int
    target_field: str
    resolver_source: str
    evidence_sources: tuple[str, ...]
    status: str = "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "class_type": self.class_type,
            "source_span": self.source_span,
            "source_revision": self.source_revision,
            "source_schema_digest": self.source_schema_digest,
            "source_schema_version": self.source_schema_version,
            "source_widget_index": self.source_widget_index,
            "source_value": deepcopy(self.source_value),
            "source_field": self.source_field,
            "target_schema_digest": self.target_schema_digest,
            "target_widget_order": list(self.target_widget_order),
            "target_schema_generation": self.target_schema_generation,
            "target_widget_index": self.target_widget_index,
            "target_field": self.target_field,
            "resolver_source": self.resolver_source,
            "evidence_sources": list(self.evidence_sources),
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class HistoricalWidgetReconciliation:
    """Non-mutating admission result consumed by a later transaction."""

    source_node_id: str
    class_type: str
    source_revision: str
    source_revisions: tuple[str, ...]
    source_evidence: tuple[str, ...]
    target_schema_digest: str
    target_widget_order: tuple[str | None, ...]
    target_schema_generation: str
    mappings: tuple[HistoricalWidgetMapping, ...]
    preserved_slots: tuple[PreservedWidgetSlot, ...]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "class_type": self.class_type,
            "source_revision": self.source_revision,
            "source_revisions": list(self.source_revisions),
            "source_evidence": list(self.source_evidence),
            "target_schema_digest": self.target_schema_digest,
            "target_widget_order": list(self.target_widget_order),
            "target_schema_generation": self.target_schema_generation,
            "mappings": [mapping.to_dict() for mapping in self.mappings],
            "preserved_slots": [slot.to_dict() for slot in self.preserved_slots],
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class WidgetMappingRefusal:
    """Actionable, source-located refusal for an unsafe automatic mapping."""

    code: str
    source_node_id: str
    class_type: str
    source_span: str | None
    source_widget_index: int | None
    source_value: Any
    reason: str
    conflicting_evidence: tuple[str, ...]
    repair_options: tuple[str, ...]

    @property
    def message(self) -> str:
        location = self.source_span or "source span unavailable"
        slot = (
            f"widget_{self.source_widget_index}={self.source_value!r}"
            if self.source_widget_index is not None
            else "historical widget slot"
        )
        conflicts = "; ".join(self.conflicting_evidence) or "none recorded"
        repairs = "; ".join(self.repair_options)
        return (
            f"{self.code}: {self.class_type} node {self.source_node_id} at {location}: "
            f"{slot}; {self.reason}. Conflicting evidence: {conflicts}. "
            f"Repair options: {repairs}."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "source_node_id": self.source_node_id,
            "class_type": self.class_type,
            "source_span": self.source_span,
            "source_widget_index": self.source_widget_index,
            "source_value": deepcopy(self.source_value),
            "reason": self.reason,
            "conflicting_evidence": list(self.conflicting_evidence),
            "repair_options": list(self.repair_options),
            "message": self.message,
        }


class HistoricalWidgetMappingRefused(ValueError):
    """Raised when historical widget migration cannot be admitted safely."""

    def __init__(self, diagnostic: WidgetMappingRefusal) -> None:
        self.diagnostic = diagnostic
        self.code = diagnostic.code
        super().__init__(diagnostic.message)


def _coerce_evidence(
    source_evidence: HistoricalWidgetEvidence
    | Mapping[str, Any]
    | Sequence[HistoricalWidgetEvidence | Mapping[str, Any]],
) -> tuple[HistoricalWidgetEvidence, ...]:
    if isinstance(source_evidence, HistoricalWidgetEvidence):
        return (source_evidence,)
    if isinstance(source_evidence, Mapping):
        return (HistoricalWidgetEvidence.from_mapping(source_evidence),)
    if isinstance(source_evidence, Sequence) and not isinstance(source_evidence, (str, bytes, bytearray)):
        result: list[HistoricalWidgetEvidence] = []
        for item in source_evidence:
            if isinstance(item, HistoricalWidgetEvidence):
                result.append(item)
            elif isinstance(item, Mapping):
                result.append(HistoricalWidgetEvidence.from_mapping(item))
            else:
                raise TypeError("historical evidence entries must be mappings or HistoricalWidgetEvidence")
        return tuple(result)
    raise TypeError("source_evidence must be a mapping, sequence, or HistoricalWidgetEvidence")


def _repair_options(*, target: bool = False) -> tuple[str, ...]:
    options = [
        "provide a pinned historical widget roster/schema for the source revision",
        "edit the generated Python to use an explicit named field",
    ]
    if target:
        options.insert(1, "capture the active target schema with its digest and process generation")
    options.append("do not infer the mapping from the current schema or widget_N")
    return tuple(options)


def _refuse(
    *,
    code: str,
    evidence: Sequence[HistoricalWidgetEvidence],
    index: int | None,
    value: Any,
    reason: str,
    conflicting_evidence: Sequence[str] = (),
    target: bool = False,
) -> None:
    first = evidence[0] if evidence else None
    diagnostic = WidgetMappingRefusal(
        code=code,
        source_node_id=first.source_node_id if first is not None else "unknown",
        class_type=first.class_type if first is not None else "unknown",
        source_span=first.source_span if first is not None else None,
        source_widget_index=index,
        source_value=deepcopy(value),
        reason=reason,
        conflicting_evidence=tuple(str(item) for item in conflicting_evidence),
        repair_options=_repair_options(target=target),
    )
    raise HistoricalWidgetMappingRefused(diagnostic)


def _schema_provenance(provider: Any | None, class_type: str) -> tuple[str | None, str | None]:
    if provider is None:
        return None, None
    try:
        from vibecomfy.schema.provider import schema_for

        schema = schema_for(provider, class_type)
    except Exception:  # noqa: BLE001 - absence is handled as a refusal below
        schema = None
    digest = _nonempty_text(getattr(schema, "source_hash", None)) if schema is not None else None
    if digest is None:
        digest = _nonempty_text(getattr(provider, "_object_info_digest", None))
    snapshot = getattr(provider, "snapshot", None)
    generation = getattr(snapshot, "generation", None) if snapshot is not None else None
    if generation is None:
        generation = getattr(provider, "generation", None)
    return digest, str(generation) if generation is not None else None


def _target_roster(
    evidence: Sequence[HistoricalWidgetEvidence],
    *,
    target_node: Mapping[str, Any] | Any | None,
    target_schema_provider: Any | None,
    target_widget_order: Sequence[str | None] | None,
) -> tuple[tuple[str | None, ...], str]:
    if target_widget_order is not None:
        return (
            tuple(name if isinstance(name, str) and name else None for name in target_widget_order),
            "explicit_target_widget_order",
        )
    if target_node is None and target_schema_provider is None:
        _refuse(
            code="missing_target_schema_evidence",
            evidence=evidence,
            index=0,
            value=evidence[0].source_widget_values[0] if evidence[0].source_widget_values else None,
            reason="a target node or target schema provider is required",
            target=True,
        )
    class_type = evidence[0].class_type
    if target_node is None:
        target_node = {
            "class_type": class_type,
            "widgets_values": [None] * max(len(evidence[0].source_widget_order), 1),
        }
    from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node

    resolution = compact_widget_names_for_node(
        target_node,
        class_type,
        schema_provider=target_schema_provider,
        allow_object_info_fallback=False,
    )
    return tuple(resolution.names), resolution.source


def admit_historical_widget_mappings(
    source_evidence: HistoricalWidgetEvidence
    | Mapping[str, Any]
    | Sequence[HistoricalWidgetEvidence | Mapping[str, Any]],
    *,
    target_node: Mapping[str, Any] | Any | None = None,
    target_schema_provider: Any | None = None,
    target_widget_order: Sequence[str | None] | None = None,
    target_schema_digest: str | None = None,
    target_schema_generation: str | int | None = None,
) -> HistoricalWidgetReconciliation:
    """Admit only uniquely evidenced source-slot → target-field mappings.

    This is intentionally an admission check, not an edit.  The caller may
    stage/apply the returned records in a later transaction.  ``target_node``
    and ``target_schema_provider`` are both passed through the existing
    ``compact_widget_names_for_node`` and
    ``resolve_widget_name_with_provenance`` machinery.  A current target
    roster validates the destination; it never establishes the source meaning.
    """
    try:
        evidence = _coerce_evidence(source_evidence)
    except (TypeError, ValueError) as exc:
        raise HistoricalWidgetMappingRefused(
            WidgetMappingRefusal(
                code="malformed_historical_evidence",
                source_node_id="unknown",
                class_type="unknown",
                source_span=None,
                source_widget_index=None,
                source_value=None,
                reason=str(exc),
                conflicting_evidence=(),
                repair_options=_repair_options(),
            )
        ) from exc
    if not evidence:
        _refuse(
            code="missing_historical_evidence",
            evidence=(),
            index=None,
            value=None,
            reason="no captured source roster was supplied",
        )

    first = evidence[0]
    for other in evidence[1:]:
        if (other.source_node_id, other.class_type) != (first.source_node_id, first.class_type):
            _refuse(
                code="conflicting_historical_evidence",
                evidence=evidence,
                index=0,
                value=first.source_widget_values[0] if first.source_widget_values else None,
                reason="evidence records refer to different source nodes or classes",
                conflicting_evidence=(
                    f"{first.source_node_id}/{first.class_type}",
                    f"{other.source_node_id}/{other.class_type}",
                ),
            )

    for item in evidence:
        if item.source_revision is None or (
            item.source_schema_digest is None and item.source_schema_version is None
        ):
            _refuse(
                code="missing_historical_source_identity",
                evidence=evidence,
                index=0,
                value=item.source_widget_values[0] if item.source_widget_values else None,
                reason=(
                    "source revision/digest and source schema digest or version "
                    "are required before a historical value can be migrated"
                ),
            )
        if len(item.source_widget_values) > len(item.source_widget_order):
            index = len(item.source_widget_order)
            _refuse(
                code="historical_roster_shorter_than_values",
                evidence=evidence,
                index=index,
                value=item.source_widget_values[index],
                reason="the source roster cannot name every observed compact value",
            )
        if not item.source_widget_order and item.source_widget_values:
            _refuse(
                code="missing_historical_source_roster",
                evidence=evidence,
                index=0,
                value=item.source_widget_values[0],
                reason="the source roster is empty",
            )

    source_identities = {
        (item.source_revision, item.source_schema_digest, item.source_schema_version)
        for item in evidence
    }
    if len(source_identities) > 1:
        _refuse(
            code="conflicting_historical_evidence",
            evidence=evidence,
            index=0,
            value=evidence[0].source_widget_values[0] if evidence[0].source_widget_values else None,
            reason="source witnesses are not bound to one revision and schema identity",
            conflicting_evidence=tuple(
                f"revision={revision!r}, schema_digest={digest!r}, schema_version={version!r}"
                for revision, digest, version in sorted(source_identities, key=str)
            ),
        )

    observations: dict[int, tuple[str | None, Any, list[str]]] = {}
    for item in evidence:
        for index, value in enumerate(item.source_widget_values):
            name = item.source_widget_order[index]
            prior = observations.get(index)
            if prior is None:
                observations[index] = (name, deepcopy(value), [item.evidence_source])
                continue
            prior_name, prior_value, sources = prior
            if prior_name != name or not _safe_equal(prior_value, value):
                _refuse(
                    code="conflicting_historical_evidence",
                    evidence=evidence,
                    index=index,
                    value=value,
                    reason="source witnesses disagree on the historical field or value",
                    conflicting_evidence=(
                        f"{sources[0]} says {prior_name!r}={prior_value!r}",
                        f"{item.evidence_source} says {name!r}={value!r}",
                    ),
                )
            if item.evidence_source not in sources:
                sources.append(item.evidence_source)

    semantic_observations = {
        index: item
        for index, item in observations.items()
        if isinstance(item[0], str) and item[0] and not _is_synthetic_name(item[0])
    }
    if not semantic_observations:
        _refuse(
            code="unproven_historical_widget_meaning",
            evidence=evidence,
            index=0 if observations else None,
            value=next(iter(observations.values()))[1] if observations else None,
            reason="the source evidence contains no named semantic field; widget_N and holes are not proof",
        )
    seen_source_fields: dict[str, int] = {}
    for index, (name, value, _sources) in semantic_observations.items():
        assert name is not None
        previous = seen_source_fields.get(name)
        if previous is not None and previous != index:
            _refuse(
                code="ambiguous_historical_source_field",
                evidence=evidence,
                index=index,
                value=value,
                reason=f"historical field {name!r} appears at multiple source indices",
                conflicting_evidence=(f"index {previous}", f"index {index}"),
            )
        seen_source_fields[name] = index

    target_order, resolver_source = _target_roster(
        evidence,
        target_node=target_node,
        target_schema_provider=target_schema_provider,
        target_widget_order=target_widget_order,
    )
    derived_digest, derived_generation = _schema_provenance(target_schema_provider, first.class_type)
    final_target_digest = _nonempty_text(target_schema_digest) or derived_digest
    final_target_generation = (
        str(target_schema_generation)
        if target_schema_generation is not None
        else derived_generation
    )
    if final_target_digest is None or final_target_generation is None:
        _refuse(
            code="incomplete_target_schema_identity",
            evidence=evidence,
            index=0,
            value=first.source_widget_values[0] if first.source_widget_values else None,
            reason="target schema digest and active process generation are both required",
            target=True,
        )

    from vibecomfy.porting.widgets.aliases import resolve_widget_name_with_provenance

    mappings: list[HistoricalWidgetMapping] = []
    for index, (source_name, value, sources) in sorted(semantic_observations.items()):
        assert source_name is not None
        candidates = [target_index for target_index, name in enumerate(target_order) if name == source_name]
        if len(candidates) != 1:
            code = "target_field_missing" if not candidates else "target_field_ambiguous"
            reason = (
                f"target schema does not expose historical field {source_name!r}"
                if not candidates
                else f"target schema exposes historical field {source_name!r} more than once"
            )
            _refuse(
                code=code,
                evidence=evidence,
                index=index,
                value=value,
                reason=reason,
                conflicting_evidence=(f"target candidates={candidates}",),
                target=True,
            )
        target_index = candidates[0]
        resolved = resolve_widget_name_with_provenance(
            first.class_type,
            target_index,
            input_aliases=target_order,
            schema_provider=target_schema_provider,
            allow_object_info_fallback=False,
        )
        if not resolved.resolved or resolved.name != source_name:
            _refuse(
                code="target_resolver_refused",
                evidence=evidence,
                index=index,
                value=value,
                reason=(
                    f"existing target resolver did not uniquely admit {source_name!r} "
                    f"at target index {target_index}"
                ),
                conflicting_evidence=(f"resolver={resolved.source}, name={resolved.name!r}",),
                target=True,
            )
        mappings.append(
            HistoricalWidgetMapping(
                source_node_id=first.source_node_id,
                class_type=first.class_type,
                source_span=first.source_span,
                source_revision=first.source_revision or "",
                source_schema_digest=first.source_schema_digest,
                source_schema_version=first.source_schema_version,
                source_widget_index=index,
                source_value=deepcopy(value),
                source_field=source_name,
                target_schema_digest=final_target_digest,
                target_widget_order=target_order,
                target_schema_generation=final_target_generation,
                target_widget_index=target_index,
                target_field=source_name,
                resolver_source=resolved.source,
                evidence_sources=tuple(sources),
            )
        )

    preserved: list[PreservedWidgetSlot] = []
    observed_count = max((len(item.source_widget_values) for item in evidence), default=0)
    for index in range(observed_count):
        if index in semantic_observations:
            continue
        name, value, _sources = observations[index]
        preserved.append(
            PreservedWidgetSlot(
                source_widget_index=index,
                source_value=deepcopy(value),
                reason=("source hole/UI-only slot" if name is None else "synthetic positional widget_N has no proof"),
            )
        )
    max_roster = max((len(item.source_widget_order) for item in evidence), default=0)
    for index in range(observed_count, max_roster):
        if index not in observations:
            preserved.append(
                PreservedWidgetSlot(
                    source_widget_index=index,
                    source_value=None,
                    reason="partial source vector; unobserved slot retained",
                )
            )

    return HistoricalWidgetReconciliation(
        source_node_id=first.source_node_id,
        class_type=first.class_type,
        source_revision=first.source_revision or "",
        source_revisions=tuple(dict.fromkeys(item.source_revision or "" for item in evidence)),
        source_evidence=tuple(dict.fromkeys(item.evidence_source for item in evidence)),
        target_schema_digest=final_target_digest,
        target_widget_order=target_order,
        target_schema_generation=final_target_generation,
        mappings=tuple(mappings),
        preserved_slots=tuple(preserved),
        status="accepted_partial" if preserved else "accepted",
    )


reconcile_historical_widget_mappings = admit_historical_widget_mappings


__all__ = [
    "HistoricalWidgetEvidence",
    "HistoricalWidgetMapping",
    "HistoricalWidgetMappingRefused",
    "HistoricalWidgetReconciliation",
    "PreservedWidgetSlot",
    "WidgetMappingRefusal",
    "admit_historical_widget_mappings",
    "reconcile_historical_widget_mappings",
]
