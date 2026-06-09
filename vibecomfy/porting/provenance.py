from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

_HELPER_UI_CLASS_TYPES: frozenset[str] = frozenset(
    {
        "Note",
        "MarkdownNote",
        "Label (rgthree)",
        "PreviewAny",
        "easy showAnything",
        "GetNode",
        "SetNode",
        "Reroute",
    }
)


@dataclass(frozen=True, slots=True)
class ProvenanceVersionPin:
    identity_key: str
    locator_key: str
    version: str
    node_ids: tuple[str, ...]
    class_types: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProvenanceWarning:
    code: str
    message: str
    identity_key: str | None = None
    locator_key: str | None = None
    node_ids: tuple[str, ...] = ()
    class_types: tuple[str, ...] = ()
    low_confidence: bool = False

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProvenanceConflict:
    code: str
    message: str
    locator_key: str
    versions: tuple[str, ...]
    node_ids: tuple[str, ...]
    class_types: tuple[str, ...]

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProvenanceRequirement:
    identity_key: str
    locator_key: str
    resolver_kind: str
    cnr_id: str | None = None
    aux_id: str | None = None
    version_pin: ProvenanceVersionPin | None = None
    node_ids: tuple[str, ...] = ()
    class_types: tuple[str, ...] = ()
    low_confidence: bool = False

    @property
    def pack_slug(self) -> str | None:
        return self.cnr_id

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.version_pin is not None:
            payload["version_pin"] = self.version_pin.to_json()
        return payload


@dataclass(slots=True)
class ProvenanceRecord:
    node_id: str
    class_type: str
    scope: str
    cnr_id: str | None = None
    aux_id: str | None = None
    ver: str | None = None
    subgraph_id: str | None = None
    subgraph_index: int | None = None
    execution_looking: bool = True
    identity_key: str = ""
    locator_key: str = ""
    resolver_kind: str = "none"

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProvenanceReport:
    records: list[ProvenanceRecord] = field(default_factory=list)
    requirements: list[ProvenanceRequirement] = field(default_factory=list)
    warnings: list[ProvenanceWarning] = field(default_factory=list)
    conflicts: list[ProvenanceConflict] = field(default_factory=list)
    version_pins: list[ProvenanceVersionPin] = field(default_factory=list)
    required_pack_slugs: set[str] = field(default_factory=set)
    aux_only: list[ProvenanceRecord] = field(default_factory=list)
    unprovenanced: list[ProvenanceRecord] = field(default_factory=list)
    core_slug_non_core: list[ProvenanceRecord] = field(default_factory=list)
    low_confidence: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "records": [record.to_json() for record in self.records],
            "requirements": [requirement.to_json() for requirement in self.requirements],
            "warnings": [warning.to_json() for warning in self.warnings],
            "conflicts": [conflict.to_json() for conflict in self.conflicts],
            "version_pins": [version_pin.to_json() for version_pin in self.version_pins],
            "required_pack_slugs": sorted(self.required_pack_slugs),
            "aux_only": [record.to_json() for record in self.aux_only],
            "unprovenanced": [record.to_json() for record in self.unprovenanced],
            "core_slug_non_core": [record.to_json() for record in self.core_slug_non_core],
            "low_confidence": self.low_confidence,
        }


def extract_provenance(workflow: Mapping[str, Any] | str | Path) -> ProvenanceReport:
    from vibecomfy.node_packs_install import CORE_COMFY_CLASSES

    raw = _load_workflow(workflow)
    subgraph_ids = {
        str(subgraph.get("id"))
        for subgraph in _subgraphs(raw)
        if isinstance(subgraph, Mapping) and subgraph.get("id") is not None
    }
    report = ProvenanceReport()
    report.records.extend(
        _records_from_nodes(raw.get("nodes"), scope="top_level", subgraph_ids=subgraph_ids)
    )
    for index, subgraph in enumerate(_subgraphs(raw)):
        subgraph_id = str(subgraph.get("id")) if subgraph.get("id") is not None else None
        report.records.extend(
            _records_from_nodes(
                subgraph.get("nodes"),
                scope="subgraph",
                subgraph_ids=subgraph_ids,
                subgraph_id=subgraph_id,
                subgraph_index=index,
            )
        )

    for record in report.records:
        if record.cnr_id:
            report.required_pack_slugs.add(record.cnr_id)
        if record.aux_id and not record.cnr_id:
            report.aux_only.append(record)
            report.warnings.append(
                ProvenanceWarning(
                    code="aux_only_git_provenance",
                    message=f"{record.class_type} has aux_id provenance without cnr_id",
                    identity_key=record.identity_key,
                    locator_key=record.locator_key,
                    node_ids=(record.node_id,),
                    class_types=(record.class_type,),
                )
            )
        if not record.cnr_id and not record.aux_id and record.execution_looking:
            report.unprovenanced.append(record)
            report.low_confidence = True
            report.warnings.append(
                ProvenanceWarning(
                    code="unprovenanced_execution_node",
                    message=f"{record.class_type} has no cnr_id or aux_id provenance",
                    identity_key=record.identity_key,
                    locator_key=record.locator_key,
                    node_ids=(record.node_id,),
                    class_types=(record.class_type,),
                    low_confidence=True,
                )
            )
        if (
            record.cnr_id == "comfy-core"
            and record.execution_looking
            and record.class_type not in CORE_COMFY_CLASSES
        ):
            report.core_slug_non_core.append(record)
            report.conflicts.append(
                ProvenanceConflict(
                    code="suspicious_comfy_core",
                    message=f"{record.class_type} is tagged with cnr_id='comfy-core' but is not a known core class",
                    locator_key=record.locator_key,
                    versions=(record.ver,) if record.ver else (),
                    node_ids=(record.node_id,),
                    class_types=(record.class_type,),
                )
            )
        if not record.execution_looking and record.class_type in _HELPER_UI_CLASS_TYPES:
            report.warnings.append(
                ProvenanceWarning(
                    code="helper_ui_node",
                    message=f"{record.class_type} is helper/UI-only and is excluded from execution provenance requirements",
                    identity_key=record.identity_key,
                    locator_key=record.locator_key,
                    node_ids=(record.node_id,),
                    class_types=(record.class_type,),
                )
            )

    report.version_pins.extend(_build_version_pins(report.records))
    report.requirements.extend(_build_requirements(report.records, report.version_pins))
    report.conflicts.extend(_build_version_conflicts(report.records))
    report.low_confidence = report.low_confidence or any(
        warning.low_confidence for warning in report.warnings
    )
    return report


def _load_workflow(workflow: Mapping[str, Any] | str | Path) -> Mapping[str, Any]:
    if isinstance(workflow, Mapping):
        return workflow
    path = Path(workflow)
    return json.loads(path.read_text(encoding="utf-8"))


def _subgraphs(raw: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    definitions = raw.get("definitions")
    if not isinstance(definitions, Mapping):
        return []
    subgraphs = definitions.get("subgraphs")
    if not isinstance(subgraphs, list):
        return []
    return [subgraph for subgraph in subgraphs if isinstance(subgraph, Mapping)]


def _records_from_nodes(
    nodes: Any,
    *,
    scope: str,
    subgraph_ids: set[str],
    subgraph_id: str | None = None,
    subgraph_index: int | None = None,
) -> list[ProvenanceRecord]:
    if not isinstance(nodes, list):
        return []
    records: list[ProvenanceRecord] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        class_type = str(node.get("type") or node.get("class_type") or "")
        if not class_type:
            continue
        properties = node.get("properties")
        props = properties if isinstance(properties, Mapping) else {}
        cnr_id = _as_str_or_none(props.get("cnr_id"))
        aux_id = _as_str_or_none(props.get("aux_id"))
        ver = _as_str_or_none(props.get("ver"))
        execution_looking = _is_execution_looking(class_type, subgraph_ids)
        records.append(
            ProvenanceRecord(
                node_id=str(node.get("id")),
                class_type=class_type,
                scope=scope,
                cnr_id=cnr_id,
                aux_id=aux_id,
                ver=ver,
                subgraph_id=subgraph_id,
                subgraph_index=subgraph_index,
                execution_looking=execution_looking,
                identity_key=_identity_key(cnr_id=cnr_id, aux_id=aux_id, ver=ver),
                locator_key=_locator_key(cnr_id=cnr_id, aux_id=aux_id),
                resolver_kind=_resolver_kind(
                    class_type=class_type,
                    cnr_id=cnr_id,
                    aux_id=aux_id,
                    execution_looking=execution_looking,
                ),
            )
        )
    return records


def _build_version_pins(records: Iterable[ProvenanceRecord]) -> list[ProvenanceVersionPin]:
    grouped: dict[str, list[ProvenanceRecord]] = {}
    for record in records:
        if not record.execution_looking or not record.ver:
            continue
        if not record.cnr_id and not record.aux_id:
            continue
        grouped.setdefault(record.identity_key, []).append(record)
    pins: list[ProvenanceVersionPin] = []
    for identity_key, members in sorted(grouped.items()):
        locator_key = members[0].locator_key
        pins.append(
            ProvenanceVersionPin(
                identity_key=identity_key,
                locator_key=locator_key,
                version=members[0].ver or "",
                node_ids=tuple(sorted(record.node_id for record in members)),
                class_types=tuple(sorted({record.class_type for record in members})),
            )
        )
    return pins


def _build_requirements(
    records: Iterable[ProvenanceRecord],
    version_pins: Iterable[ProvenanceVersionPin],
) -> list[ProvenanceRequirement]:
    version_pin_by_identity = {pin.identity_key: pin for pin in version_pins}
    grouped: dict[str, list[ProvenanceRecord]] = {}
    for record in records:
        if not record.execution_looking:
            continue
        if not record.cnr_id and not record.aux_id:
            continue
        grouped.setdefault(record.identity_key, []).append(record)

    requirements: list[ProvenanceRequirement] = []
    for identity_key, members in sorted(grouped.items()):
        sample = members[0]
        requirements.append(
            ProvenanceRequirement(
                identity_key=identity_key,
                locator_key=sample.locator_key,
                resolver_kind=sample.resolver_kind,
                cnr_id=sample.cnr_id,
                aux_id=sample.aux_id,
                version_pin=version_pin_by_identity.get(identity_key),
                node_ids=tuple(sorted(record.node_id for record in members)),
                class_types=tuple(sorted({record.class_type for record in members})),
                low_confidence=sample.resolver_kind == "aux_git",
            )
        )
    return requirements


def _build_version_conflicts(records: Iterable[ProvenanceRecord]) -> list[ProvenanceConflict]:
    grouped: dict[str, list[ProvenanceRecord]] = {}
    for record in records:
        if not record.execution_looking:
            continue
        if not record.cnr_id and not record.aux_id:
            continue
        grouped.setdefault(record.locator_key, []).append(record)

    conflicts: list[ProvenanceConflict] = []
    for locator_key, members in sorted(grouped.items()):
        versions = sorted({record.ver for record in members if record.ver})
        if len(versions) < 2:
            continue
        conflicts.append(
            ProvenanceConflict(
                code="conflicting_authored_versions",
                message=f"multiple authored versions declared for {locator_key}",
                locator_key=locator_key,
                versions=tuple(versions),
                node_ids=tuple(sorted(record.node_id for record in members)),
                class_types=tuple(sorted({record.class_type for record in members})),
            )
        )
    return conflicts


def _identity_key(*, cnr_id: str | None, aux_id: str | None, ver: str | None) -> str:
    return "|".join(
        (
            f"cnr:{cnr_id or '-'}",
            f"aux:{aux_id or '-'}",
            f"ver:{ver or '-'}",
        )
    )


def _locator_key(*, cnr_id: str | None, aux_id: str | None) -> str:
    return "|".join((f"cnr:{cnr_id or '-'}", f"aux:{aux_id or '-'}"))


def _resolver_kind(
    *,
    class_type: str,
    cnr_id: str | None,
    aux_id: str | None,
    execution_looking: bool,
) -> str:
    if not execution_looking and class_type in _HELPER_UI_CLASS_TYPES:
        return "helper_ui"
    if cnr_id == "comfy-core":
        return "comfy_core"
    if cnr_id:
        return "registry"
    if aux_id:
        return "aux_git"
    if execution_looking:
        return "unprovenanced"
    return "none"


def _is_execution_looking(class_type: str, subgraph_ids: Iterable[str]) -> bool:
    if class_type in _HELPER_UI_CLASS_TYPES:
        return False
    return class_type not in set(subgraph_ids)


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "ProvenanceConflict",
    "ProvenanceRecord",
    "ProvenanceReport",
    "ProvenanceRequirement",
    "ProvenanceVersionPin",
    "ProvenanceWarning",
    "extract_provenance",
]
