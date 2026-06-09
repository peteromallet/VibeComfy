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

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProvenanceReport:
    records: list[ProvenanceRecord] = field(default_factory=list)
    required_pack_slugs: set[str] = field(default_factory=set)
    aux_only: list[ProvenanceRecord] = field(default_factory=list)
    unprovenanced: list[ProvenanceRecord] = field(default_factory=list)
    core_slug_non_core: list[ProvenanceRecord] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "records": [record.to_json() for record in self.records],
            "required_pack_slugs": sorted(self.required_pack_slugs),
            "aux_only": [record.to_json() for record in self.aux_only],
            "unprovenanced": [record.to_json() for record in self.unprovenanced],
            "core_slug_non_core": [record.to_json() for record in self.core_slug_non_core],
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
        if not record.cnr_id and not record.aux_id and record.execution_looking:
            report.unprovenanced.append(record)
        if (
            record.cnr_id == "comfy-core"
            and record.execution_looking
            and record.class_type not in CORE_COMFY_CLASSES
        ):
            report.core_slug_non_core.append(record)
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
        record = ProvenanceRecord(
            node_id=str(node.get("id")),
            class_type=class_type,
            scope=scope,
            cnr_id=_as_str_or_none(props.get("cnr_id")),
            aux_id=_as_str_or_none(props.get("aux_id")),
            ver=_as_str_or_none(props.get("ver")),
            subgraph_id=subgraph_id,
            subgraph_index=subgraph_index,
            execution_looking=_is_execution_looking(class_type, subgraph_ids),
        )
        records.append(record)
    return records


def _is_execution_looking(class_type: str, subgraph_ids: Iterable[str]) -> bool:
    if class_type in _HELPER_UI_CLASS_TYPES:
        return False
    return class_type not in set(subgraph_ids)


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = ["ProvenanceRecord", "ProvenanceReport", "extract_provenance"]
