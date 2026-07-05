from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence

from .diagnostics import DIAGNOSTIC_SEVERITIES, DiagnosticSeverity, ReorganiseDiagnostic

LAYOUT_PLAN_VERSION = 1

SectionKind = Literal[
    "loaders",
    "conditioning",
    "latent",
    "sampling",
    "decode",
    "output",
    "control",
    "postprocess",
    "utility",
    "branch",
    "container",
    "custom",
]
SECTION_KIND_LOADERS: SectionKind = "loaders"
SECTION_KIND_CONDITIONING: SectionKind = "conditioning"
SECTION_KIND_LATENT: SectionKind = "latent"
SECTION_KIND_SAMPLING: SectionKind = "sampling"
SECTION_KIND_DECODE: SectionKind = "decode"
SECTION_KIND_OUTPUT: SectionKind = "output"
SECTION_KIND_CONTROL: SectionKind = "control"
SECTION_KIND_POSTPROCESS: SectionKind = "postprocess"
SECTION_KIND_UTILITY: SectionKind = "utility"
SECTION_KIND_BRANCH: SectionKind = "branch"
SECTION_KIND_CONTAINER: SectionKind = "container"
SECTION_KIND_CUSTOM: SectionKind = "custom"
SECTION_KINDS: frozenset[SectionKind] = frozenset(
    {
        SECTION_KIND_LOADERS,
        SECTION_KIND_CONDITIONING,
        SECTION_KIND_LATENT,
        SECTION_KIND_SAMPLING,
        SECTION_KIND_DECODE,
        SECTION_KIND_OUTPUT,
        SECTION_KIND_CONTROL,
        SECTION_KIND_POSTPROCESS,
        SECTION_KIND_UTILITY,
        SECTION_KIND_BRANCH,
        SECTION_KIND_CONTAINER,
        SECTION_KIND_CUSTOM,
    }
)

HelperPlacementKind = Literal["near-producer", "near-consumer", "edge-path", "inside-section"]
HELPER_PLACEMENT_NEAR_PRODUCER: HelperPlacementKind = "near-producer"
HELPER_PLACEMENT_NEAR_CONSUMER: HelperPlacementKind = "near-consumer"
HELPER_PLACEMENT_EDGE_PATH: HelperPlacementKind = "edge-path"
HELPER_PLACEMENT_INSIDE_SECTION: HelperPlacementKind = "inside-section"
HELPER_PLACEMENT_KINDS: frozenset[HelperPlacementKind] = frozenset(
    {
        HELPER_PLACEMENT_NEAR_PRODUCER,
        HELPER_PLACEMENT_NEAR_CONSUMER,
        HELPER_PLACEMENT_EDGE_PATH,
        HELPER_PLACEMENT_INSIDE_SECTION,
    }
)

UnassignedPolicy = Literal["classify_deterministically", "reject", "preserve_existing"]
UNASSIGNED_CLASSIFY_DETERMINISTICALLY: UnassignedPolicy = "classify_deterministically"
UNASSIGNED_REJECT: UnassignedPolicy = "reject"
UNASSIGNED_PRESERVE_EXISTING: UnassignedPolicy = "preserve_existing"
UNASSIGNED_POLICIES: frozenset[UnassignedPolicy] = frozenset(
    {
        UNASSIGNED_CLASSIFY_DETERMINISTICALLY,
        UNASSIGNED_REJECT,
        UNASSIGNED_PRESERVE_EXISTING,
    }
)

RoleHint = Literal[
    "loader",
    "conditioning",
    "latent",
    "sampler",
    "decode",
    "output",
    "control",
    "postprocess",
    "utility",
    "helper",
    "ui",
    "shared",
    "subgraph_container",
    "unknown",
]
ROLE_HINT_LOADER: RoleHint = "loader"
ROLE_HINT_CONDITIONING: RoleHint = "conditioning"
ROLE_HINT_LATENT: RoleHint = "latent"
ROLE_HINT_SAMPLER: RoleHint = "sampler"
ROLE_HINT_DECODE: RoleHint = "decode"
ROLE_HINT_OUTPUT: RoleHint = "output"
ROLE_HINT_CONTROL: RoleHint = "control"
ROLE_HINT_POSTPROCESS: RoleHint = "postprocess"
ROLE_HINT_UTILITY: RoleHint = "utility"
ROLE_HINT_HELPER: RoleHint = "helper"
ROLE_HINT_UI: RoleHint = "ui"
ROLE_HINT_SHARED: RoleHint = "shared"
ROLE_HINT_SUBGRAPH_CONTAINER: RoleHint = "subgraph_container"
ROLE_HINT_UNKNOWN: RoleHint = "unknown"
ROLE_HINTS: frozenset[RoleHint] = frozenset(
    {
        ROLE_HINT_LOADER,
        ROLE_HINT_CONDITIONING,
        ROLE_HINT_LATENT,
        ROLE_HINT_SAMPLER,
        ROLE_HINT_DECODE,
        ROLE_HINT_OUTPUT,
        ROLE_HINT_CONTROL,
        ROLE_HINT_POSTPROCESS,
        ROLE_HINT_UTILITY,
        ROLE_HINT_HELPER,
        ROLE_HINT_UI,
        ROLE_HINT_SHARED,
        ROLE_HINT_SUBGRAPH_CONTAINER,
        ROLE_HINT_UNKNOWN,
    }
)

LayoutBehavior = Literal["primary", "sidecar", "wall", "note", "unknown"]
LAYOUT_BEHAVIOR_PRIMARY: LayoutBehavior = "primary"
LAYOUT_BEHAVIOR_SIDECAR: LayoutBehavior = "sidecar"
LAYOUT_BEHAVIOR_WALL: LayoutBehavior = "wall"
LAYOUT_BEHAVIOR_NOTE: LayoutBehavior = "note"
LAYOUT_BEHAVIOR_UNKNOWN: LayoutBehavior = "unknown"
LAYOUT_BEHAVIORS: frozenset[LayoutBehavior] = frozenset(
    {
        LAYOUT_BEHAVIOR_PRIMARY,
        LAYOUT_BEHAVIOR_SIDECAR,
        LAYOUT_BEHAVIOR_WALL,
        LAYOUT_BEHAVIOR_NOTE,
        LAYOUT_BEHAVIOR_UNKNOWN,
    }
)

SamplerRelationKind = Literal[
    "same_sampler_pair",
    "parallel_sampler_branch",
    "sampler_refines",
    "sampler_precedes",
    "independent_samplers",
]
SAMPLER_RELATION_KINDS: frozenset[SamplerRelationKind] = frozenset(
    {
        "same_sampler_pair",
        "parallel_sampler_branch",
        "sampler_refines",
        "sampler_precedes",
        "independent_samplers",
    }
)

HELPER_CLASS_TYPES: frozenset[str] = frozenset(
    {"SetNode", "GetNode", "Reroute", "Note", "MarkdownNote"}
)


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_jsonish(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_jsonish(item) for item in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw_jsonish(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_jsonish(item) for item in value]
    return value


def _refs_json(refs: Sequence["CanonicalNodeRef"]) -> list[list[str]]:
    return [ref.to_json() for ref in refs]


@dataclass(frozen=True, slots=True)
class CanonicalNodeRef:
    """Durable node reference for LayoutPlan v1.

    JSON form is always the array ``[scope_path, uid]``. Raw LiteGraph integer
    IDs are intentionally not represented in this type.
    """

    scope_path: str
    uid: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope_path, str):
            raise TypeError("scope_path must be a string")
        if not isinstance(self.uid, str) or not self.uid:
            raise ValueError("uid must be a non-empty string")

    def to_json(self) -> list[str]:
        return [self.scope_path, self.uid]


@dataclass(frozen=True, slots=True)
class LayoutSection:
    id: str
    kind: SectionKind
    nodes: tuple[CanonicalNodeRef, ...] = ()
    title: str | None = None
    role_hint: RoleHint | None = None
    parent_id: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in SECTION_KINDS:
            raise ValueError(f"unknown section kind: {self.kind!r}")
        if self.role_hint is not None and self.role_hint not in ROLE_HINTS:
            raise ValueError(f"unknown role hint: {self.role_hint!r}")
        object.__setattr__(self, "nodes", tuple(self.nodes))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "nodes": _refs_json(self.nodes),
        }
        if self.title is not None:
            payload["title"] = self.title
        if self.role_hint is not None:
            payload["role_hint"] = self.role_hint
        if self.parent_id is not None:
            payload["parent_id"] = self.parent_id
        if self.notes is not None:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class SharedNodeHome:
    node: CanonicalNodeRef
    home: str
    label: str | None = None
    role_hint: RoleHint | None = None

    def __post_init__(self) -> None:
        if self.role_hint is not None and self.role_hint not in ROLE_HINTS:
            raise ValueError(f"unknown role hint: {self.role_hint!r}")

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "node": self.node.to_json(),
            "home": self.home,
        }
        if self.label is not None:
            payload["label"] = self.label
        if self.role_hint is not None:
            payload["role_hint"] = self.role_hint
        return payload


@dataclass(frozen=True, slots=True)
class HelperPlacement:
    helper: CanonicalNodeRef
    kind: HelperPlacementKind
    target: CanonicalNodeRef | None = None
    source: CanonicalNodeRef | None = None
    destination: CanonicalNodeRef | None = None
    section_id: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in HELPER_PLACEMENT_KINDS:
            raise ValueError(f"unknown helper placement kind: {self.kind!r}")

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "helper": self.helper.to_json(),
            "kind": self.kind,
        }
        if self.target is not None:
            payload["target"] = self.target.to_json()
        if self.source is not None:
            payload["from"] = self.source.to_json()
        if self.destination is not None:
            payload["to"] = self.destination.to_json()
        if self.section_id is not None:
            payload["section_id"] = self.section_id
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True, slots=True)
class SamplerRelationClaim:
    kind: SamplerRelationKind
    samplers: tuple[CanonicalNodeRef, ...]
    source: CanonicalNodeRef | None = None
    target: CanonicalNodeRef | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in SAMPLER_RELATION_KINDS:
            raise ValueError(f"unknown sampler relation kind: {self.kind!r}")
        object.__setattr__(self, "samplers", tuple(self.samplers))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind,
            "samplers": _refs_json(self.samplers),
        }
        if self.source is not None:
            payload["source"] = self.source.to_json()
        if self.target is not None:
            payload["target"] = self.target.to_json()
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True, slots=True)
class CanonicalNodeSummary:
    ref: CanonicalNodeRef
    class_type: str
    title: str | None = None
    role_hint: RoleHint = ROLE_HINT_UNKNOWN
    is_helper: bool = False

    def __post_init__(self) -> None:
        if self.role_hint not in ROLE_HINTS:
            raise ValueError(f"unknown role hint: {self.role_hint!r}")

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ref": self.ref.to_json(),
            "class_type": self.class_type,
            "role_hint": self.role_hint,
            "is_helper": self.is_helper,
        }
        if self.title is not None:
            payload["title"] = self.title
        return payload


@dataclass(frozen=True, slots=True)
class LayoutTraceEntry:
    """Per-node placement trace entry for ``layout_trace.json`` artifact.

    Captures classification and placement decisions for a single node
    across the compile phases.
    """

    ref: CanonicalNodeRef
    class_type: str
    role_hint: RoleHint = ROLE_HINT_UNKNOWN
    layout_behavior: LayoutBehavior = "unknown"
    section_id: str | None = None
    attachment_target: CanonicalNodeRef | None = None
    placement_choice: str | None = None
    x: float | None = None
    y: float | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.role_hint not in ROLE_HINTS:
            raise ValueError(f"unknown role hint: {self.role_hint!r}")
        if self.layout_behavior not in LAYOUT_BEHAVIORS:
            raise ValueError(f"unknown layout behavior: {self.layout_behavior!r}")

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ref": self.ref.to_json(),
            "class_type": self.class_type,
            "role_hint": self.role_hint,
            "layout_behavior": self.layout_behavior,
        }
        if self.section_id is not None:
            payload["section_id"] = self.section_id
        if self.attachment_target is not None:
            payload["attachment_target"] = self.attachment_target.to_json()
        if self.placement_choice is not None:
            payload["placement_choice"] = self.placement_choice
        if self.x is not None:
            payload["x"] = self.x
        if self.y is not None:
            payload["y"] = self.y
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True, slots=True)
class ScopeGraphSummary:
    scope_path: str
    node_count: int
    edge_count: int
    helper_count: int = 0
    wcc_count: int = 0
    scc_count: int = 0
    terminal_refs: tuple[CanonicalNodeRef, ...] = ()
    sampler_refs: tuple[CanonicalNodeRef, ...] = ()
    summarized: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "terminal_refs", tuple(self.terminal_refs))
        object.__setattr__(self, "sampler_refs", tuple(self.sampler_refs))

    def to_json(self) -> dict[str, Any]:
        return {
            "scope_path": self.scope_path,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "helper_count": self.helper_count,
            "wcc_count": self.wcc_count,
            "scc_count": self.scc_count,
            "terminal_refs": _refs_json(self.terminal_refs),
            "sampler_refs": _refs_json(self.sampler_refs),
            "summarized": self.summarized,
        }


@dataclass(frozen=True, slots=True)
class GraphFactsSummary:
    canonical_nodes: tuple[CanonicalNodeSummary, ...] = ()
    scopes: tuple[ScopeGraphSummary, ...] = ()
    helper_refs: tuple[CanonicalNodeRef, ...] = ()
    shared_node_refs: tuple[CanonicalNodeRef, ...] = ()
    sampler_relation_candidates: tuple[SamplerRelationClaim, ...] = ()
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "canonical_nodes", tuple(self.canonical_nodes))
        object.__setattr__(self, "scopes", tuple(self.scopes))
        object.__setattr__(self, "helper_refs", tuple(self.helper_refs))
        object.__setattr__(self, "shared_node_refs", tuple(self.shared_node_refs))
        object.__setattr__(
            self,
            "sampler_relation_candidates",
            tuple(self.sampler_relation_candidates),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "canonical_nodes": [node.to_json() for node in self.canonical_nodes],
            "scopes": [scope.to_json() for scope in self.scopes],
            "helper_refs": _refs_json(self.helper_refs),
            "shared_node_refs": _refs_json(self.shared_node_refs),
            "sampler_relation_candidates": [
                candidate.to_json() for candidate in self.sampler_relation_candidates
            ],
            "truncated": self.truncated,
        }


@dataclass(frozen=True, slots=True)
class AssessmentMetric:
    name: str
    value: int | float | str | bool
    threshold: int | float | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "value": self.value}
        if self.threshold is not None:
            payload["threshold"] = self.threshold
        return payload


@dataclass(frozen=True, slots=True)
class AssessmentIssue:
    code: str
    message: str
    severity: DiagnosticSeverity = "warning"
    refs: tuple[CanonicalNodeRef, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in DIAGNOSTIC_SEVERITIES:
            raise ValueError(f"unknown diagnostic severity: {self.severity!r}")
        object.__setattr__(self, "refs", tuple(self.refs))
        object.__setattr__(self, "detail", _freeze_jsonish(self.detail))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "refs": _refs_json(self.refs),
        }
        if self.detail:
            payload["detail"] = _thaw_jsonish(self.detail)
        return payload


@dataclass(frozen=True, slots=True)
class AssessmentReport:
    verdict: Literal["ok", "needs_reorganise", "blocked"]
    metrics: tuple[AssessmentMetric, ...] = ()
    issues: tuple[AssessmentIssue, ...] = ()
    diagnostics: tuple[ReorganiseDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    def to_json(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "metrics": [metric.to_json() for metric in self.metrics],
            "issues": [issue.to_json() for issue in self.issues],
            "diagnostics": [diagnostic.to_json() for diagnostic in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class LayoutPlanV1:
    sections: tuple[LayoutSection, ...]
    shared_nodes: tuple[SharedNodeHome, ...] = ()
    helper_placements: tuple[HelperPlacement, ...] = ()
    sampler_relations: tuple[SamplerRelationClaim, ...] = ()
    unassigned_policy: UnassignedPolicy = UNASSIGNED_CLASSIFY_DETERMINISTICALLY
    version: Literal[1] = LAYOUT_PLAN_VERSION
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.version != LAYOUT_PLAN_VERSION:
            raise ValueError(f"unsupported LayoutPlan version: {self.version!r}")
        if self.unassigned_policy not in UNASSIGNED_POLICIES:
            raise ValueError(f"unknown unassigned policy: {self.unassigned_policy!r}")
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "shared_nodes", tuple(self.shared_nodes))
        object.__setattr__(self, "helper_placements", tuple(self.helper_placements))
        object.__setattr__(self, "sampler_relations", tuple(self.sampler_relations))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": self.version,
            "sections": [section.to_json() for section in self.sections],
            "shared_nodes": [shared.to_json() for shared in self.shared_nodes],
            "helper_placements": [placement.to_json() for placement in self.helper_placements],
            "sampler_relations": [relation.to_json() for relation in self.sampler_relations],
            "unassigned_policy": self.unassigned_policy,
        }
        if self.notes is not None:
            payload["notes"] = self.notes
        return payload


__all__ = [
    "HELPER_CLASS_TYPES",
    "HELPER_PLACEMENT_EDGE_PATH",
    "HELPER_PLACEMENT_INSIDE_SECTION",
    "HELPER_PLACEMENT_KINDS",
    "HELPER_PLACEMENT_NEAR_CONSUMER",
    "HELPER_PLACEMENT_NEAR_PRODUCER",
    "LAYOUT_BEHAVIOR_NOTE",
    "LAYOUT_BEHAVIOR_PRIMARY",
    "LAYOUT_BEHAVIOR_SIDECAR",
    "LAYOUT_BEHAVIOR_UNKNOWN",
    "LAYOUT_BEHAVIOR_WALL",
    "LAYOUT_BEHAVIORS",
    "LAYOUT_PLAN_VERSION",
    "ROLE_HINTS",
    "ROLE_HINT_CONDITIONING",
    "ROLE_HINT_CONTROL",
    "ROLE_HINT_DECODE",
    "ROLE_HINT_HELPER",
    "ROLE_HINT_LATENT",
    "ROLE_HINT_LOADER",
    "ROLE_HINT_OUTPUT",
    "ROLE_HINT_POSTPROCESS",
    "ROLE_HINT_SAMPLER",
    "ROLE_HINT_SHARED",
    "ROLE_HINT_SUBGRAPH_CONTAINER",
    "ROLE_HINT_UI",
    "ROLE_HINT_UNKNOWN",
    "SAMPLER_RELATION_KINDS",
    "SECTION_KINDS",
    "SECTION_KIND_BRANCH",
    "SECTION_KIND_CONDITIONING",
    "SECTION_KIND_CONTAINER",
    "SECTION_KIND_CONTROL",
    "SECTION_KIND_CUSTOM",
    "SECTION_KIND_DECODE",
    "SECTION_KIND_LATENT",
    "SECTION_KIND_LOADERS",
    "SECTION_KIND_OUTPUT",
    "SECTION_KIND_POSTPROCESS",
    "SECTION_KIND_SAMPLING",
    "SECTION_KIND_UTILITY",
    "UNASSIGNED_CLASSIFY_DETERMINISTICALLY",
    "UNASSIGNED_POLICIES",
    "UNASSIGNED_PRESERVE_EXISTING",
    "UNASSIGNED_REJECT",
    "AssessmentIssue",
    "AssessmentMetric",
    "AssessmentReport",
    "CanonicalNodeRef",
    "CanonicalNodeSummary",
    "GraphFactsSummary",
    "HelperPlacement",
    "HelperPlacementKind",
    "LayoutBehavior",
    "LayoutPlanV1",
    "LayoutSection",
    "LayoutTraceEntry",
    "RoleHint",
    "SamplerRelationClaim",
    "SamplerRelationKind",
    "ScopeGraphSummary",
    "SectionKind",
    "SharedNodeHome",
    "UnassignedPolicy",
]
