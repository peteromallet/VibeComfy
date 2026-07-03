from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from math import hypot
from types import MappingProxyType
from typing import Any, Literal, Mapping, Sequence

from vibecomfy.identity.uid import make_uid
from vibecomfy.porting.canonical_coords import snap_pos, snap_size
from vibecomfy.porting.layout_store import STORE_VERSION

from .classify import ClassificationReport, classify_layout_facts
from .diagnostics import ReorganiseDiagnosticReport
from .graph_facts import GraphInventoryFacts, GroupFact, NodeFurnitureFact, extract_graph_facts
from .plan_types import (
    HELPER_PLACEMENT_EDGE_PATH,
    HELPER_PLACEMENT_INSIDE_SECTION,
    HELPER_PLACEMENT_NEAR_CONSUMER,
    HELPER_PLACEMENT_NEAR_PRODUCER,
    ROLE_HINT_CONDITIONING,
    ROLE_HINT_CONTROL,
    ROLE_HINT_DECODE,
    ROLE_HINT_HELPER,
    ROLE_HINT_LATENT,
    ROLE_HINT_LOADER,
    ROLE_HINT_OUTPUT,
    ROLE_HINT_POSTPROCESS,
    ROLE_HINT_SAMPLER,
    ROLE_HINT_SHARED,
    ROLE_HINT_SUBGRAPH_CONTAINER,
    ROLE_HINT_UI,
    ROLE_HINT_UNKNOWN,
    ROLE_HINT_UTILITY,
    SECTION_KIND_BRANCH,
    SECTION_KIND_CONDITIONING,
    SECTION_KIND_CONTAINER,
    SECTION_KIND_CONTROL,
    SECTION_KIND_CUSTOM,
    SECTION_KIND_DECODE,
    SECTION_KIND_LATENT,
    SECTION_KIND_LOADERS,
    SECTION_KIND_OUTPUT,
    SECTION_KIND_POSTPROCESS,
    SECTION_KIND_SAMPLING,
    SECTION_KIND_UTILITY,
    UNASSIGNED_CLASSIFY_DETERMINISTICALLY,
    UNASSIGNED_PRESERVE_EXISTING,
    UNASSIGNED_REJECT,
    AssessmentIssue,
    AssessmentMetric,
    CanonicalNodeRef,
    LayoutPlanV1,
    LayoutSection,
    RoleHint,
    SamplerRelationClaim,
    SectionKind,
)
from .report import build_assessment_report
from .validate import validate_layout_plan

SpacingPreset = Literal["compact", "balanced", "wide"]
ExistingGroupPolicy = Literal[
    "preserve",
    "rename_only",
    "resize_only",
    "rename_and_resize",
    "semantic_preserve",
    "dissolve_with_warning",
    "force_regroup",
]
SectionTemplate = Literal[
    "single",
    "pair",
    "row",
    "pipeline",
    "fan_in",
    "fan_out",
    "parallel_branches",
    "alternatives",
    "grid",
    "hub_and_spokes",
    "notes_sidebar",
]

DEFAULT_NODE_WIDTH = 260
DEFAULT_NODE_HEIGHT = 100
DEFAULT_GROUP_HEADER_HEIGHT = 36
MIN_NODE_GUTTER = 32
MIN_GROUP_GUTTER = 32
EXISTING_GROUP_SCORE_THRESHOLD = 0.65
EXISTING_GROUP_MIN_NODE_COVERAGE = 0.66
EXISTING_GROUP_MIN_ROLE_OR_TOPOLOGY = 0.65
EXISTING_GROUP_CONTAINMENT_WEIGHT = 0.35
EXISTING_GROUP_TOPOLOGY_WEIGHT = 0.25
EXISTING_GROUP_TITLE_ROLE_WEIGHT = 0.25
EXISTING_GROUP_NODE_COVERAGE_WEIGHT = 0.15

# Compile-local huge workflow defaults. These deliberately stay outside
# LayoutPlan v1 so the plan remains semantic-only.
COMPILE_HUGE_WORKFLOW_NODE_THRESHOLD = 32
COMPILE_HUGE_WORKFLOW_EDGE_THRESHOLD = 48
COMPILE_HUGE_WORKFLOW_PROJECTION_TOKEN_THRESHOLD = 4000
COMPILE_LARGE_SECTION_CLUSTER_SIZE = 10

COMPILE_METRIC_NODE_LAYOUT_COUNT = "compiled_node_layout_count"
COMPILE_METRIC_GROUP_LAYOUT_COUNT = "compiled_group_layout_count"
COMPILE_METRIC_HELPER_LAYOUT_COUNT = "compiled_helper_layout_count"
COMPILE_METRIC_NODE_OVERLAP_COUNT = "compiled_node_overlap_count"
COMPILE_METRIC_GROUP_OVERLAP_COUNT = "compiled_group_overlap_count"
COMPILE_METRIC_BACKWARD_EDGE_RATIO = "compiled_backward_edge_ratio"
COMPILE_METRIC_CROSSING_PROXY_COUNT = "compiled_crossing_proxy_count"
COMPILE_METRIC_MINIMUM_GUTTER = "compiled_minimum_gutter"
COMPILE_METRIC_HELPER_DISTANCE_MAX = "compiled_helper_distance_max"
COMPILE_METRIC_IDEMPOTENCE_DELTA = "compiled_idempotence_delta"
COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED = "structural_hash_unchanged"
COMPILE_ISSUE_NODE_OVERLAP = "compiler_node_overlap"
COMPILE_ISSUE_GROUP_OVERLAP = "compiler_group_overlap"
COMPILE_ISSUE_BACKWARD_EDGE_RATIO_HIGH = "compiler_backward_edge_ratio_high"
COMPILE_ISSUE_CROSSING_PROXY_HIGH = "compiler_crossing_proxy_high"
COMPILE_ISSUE_MINIMUM_GUTTER = "compiler_minimum_gutter_violation"
COMPILE_ISSUE_HELPER_DISTANCE_HIGH = "compiler_helper_distance_high"
COMPILE_ISSUE_IDEMPOTENCE_DELTA = "compiler_idempotence_delta"
COMPILE_ISSUE_STRUCTURAL_HASH_CHANGED = "compiler_structural_hash_changed"
COMPILE_ISSUE_EXISTING_GROUP_DISSOLVED = "existing_group_dissolved"
COMPILE_ISSUE_EXISTING_GROUP_REBUILT = "existing_group_rebuilt"
COMPILE_BACKWARD_EDGE_RATIO_THRESHOLD = 0.15
COMPILE_BACKWARD_EDGE_X_TOLERANCE = 8.0
COMPILE_CROSSING_PROXY_THRESHOLD = 0
COMPILE_HELPER_DISTANCE_THRESHOLD = 420.0
COMPILE_IDEMPOTENCE_DELTA_THRESHOLD = 0
COMPILE_METRIC_ORDER = (
    COMPILE_METRIC_NODE_LAYOUT_COUNT,
    COMPILE_METRIC_GROUP_LAYOUT_COUNT,
    COMPILE_METRIC_HELPER_LAYOUT_COUNT,
    COMPILE_METRIC_NODE_OVERLAP_COUNT,
    COMPILE_METRIC_GROUP_OVERLAP_COUNT,
    COMPILE_METRIC_BACKWARD_EDGE_RATIO,
    COMPILE_METRIC_CROSSING_PROXY_COUNT,
    COMPILE_METRIC_MINIMUM_GUTTER,
    COMPILE_METRIC_HELPER_DISTANCE_MAX,
    COMPILE_METRIC_IDEMPOTENCE_DELTA,
    COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED,
)
COMPILE_ISSUE_ORDER = (
    COMPILE_ISSUE_NODE_OVERLAP,
    COMPILE_ISSUE_GROUP_OVERLAP,
    COMPILE_ISSUE_BACKWARD_EDGE_RATIO_HIGH,
    COMPILE_ISSUE_CROSSING_PROXY_HIGH,
    COMPILE_ISSUE_MINIMUM_GUTTER,
    COMPILE_ISSUE_HELPER_DISTANCE_HIGH,
    COMPILE_ISSUE_IDEMPOTENCE_DELTA,
    COMPILE_ISSUE_STRUCTURAL_HASH_CHANGED,
    COMPILE_ISSUE_EXISTING_GROUP_DISSOLVED,
    COMPILE_ISSUE_EXISTING_GROUP_REBUILT,
)

_ENTRY_KEYS = ("pos", "size", "flags", "color", "bgcolor", "mode", "properties")
_SECTION_KEYS = (
    "entries",
    "groups",
    "extra",
    "lastRerouteId",
    "definitions",
    "virtual_wires",
)

_ROLE_COLORS: Mapping[str, str] = MappingProxyType(
    {
        SECTION_KIND_LOADERS: "#3f6f8f",
        SECTION_KIND_CONDITIONING: "#7b5ea7",
        SECTION_KIND_LATENT: "#6b8f5a",
        SECTION_KIND_SAMPLING: "#9a6a3a",
        SECTION_KIND_DECODE: "#4f7f72",
        SECTION_KIND_OUTPUT: "#8a5f68",
        SECTION_KIND_CONTROL: "#5f6f9a",
        SECTION_KIND_POSTPROCESS: "#7a7560",
        SECTION_KIND_UTILITY: "#686f78",
        SECTION_KIND_BRANCH: "#6f6a9a",
        SECTION_KIND_CONTAINER: "#5f7470",
        SECTION_KIND_CUSTOM: "#646464",
    }
)

_SECTION_MIN_RANKS: Mapping[SectionKind, int] = MappingProxyType(
    {
        SECTION_KIND_LOADERS: 0,
        SECTION_KIND_CONDITIONING: 1,
        SECTION_KIND_LATENT: 1,
        SECTION_KIND_CONTROL: 2,
        SECTION_KIND_SAMPLING: 3,
        SECTION_KIND_BRANCH: 3,
        SECTION_KIND_DECODE: 4,
        SECTION_KIND_POSTPROCESS: 5,
        SECTION_KIND_OUTPUT: 6,
        SECTION_KIND_UTILITY: 2,
        SECTION_KIND_CONTAINER: 0,
        SECTION_KIND_CUSTOM: 2,
    }
)

_ROLE_TO_SECTION_KIND: Mapping[RoleHint, SectionKind] = MappingProxyType(
    {
        ROLE_HINT_LOADER: SECTION_KIND_LOADERS,
        ROLE_HINT_CONDITIONING: SECTION_KIND_CONDITIONING,
        ROLE_HINT_LATENT: SECTION_KIND_LATENT,
        ROLE_HINT_SAMPLER: SECTION_KIND_SAMPLING,
        ROLE_HINT_DECODE: SECTION_KIND_DECODE,
        ROLE_HINT_OUTPUT: SECTION_KIND_OUTPUT,
        ROLE_HINT_CONTROL: SECTION_KIND_CONTROL,
        ROLE_HINT_POSTPROCESS: SECTION_KIND_POSTPROCESS,
        ROLE_HINT_HELPER: SECTION_KIND_UTILITY,
        ROLE_HINT_UI: SECTION_KIND_UTILITY,
        ROLE_HINT_SHARED: SECTION_KIND_CUSTOM,
        ROLE_HINT_SUBGRAPH_CONTAINER: SECTION_KIND_CONTAINER,
        ROLE_HINT_UNKNOWN: SECTION_KIND_CUSTOM,
    }
)

_SECTION_TITLE_TOKENS: Mapping[SectionKind, frozenset[str]] = MappingProxyType(
    {
        SECTION_KIND_LOADERS: frozenset({"loader", "load", "model", "checkpoint", "clip", "lora", "vae"}),
        SECTION_KIND_CONDITIONING: frozenset({"conditioning", "condition", "prompt", "text", "negative", "positive", "clip"}),
        SECTION_KIND_LATENT: frozenset({"latent", "empty", "noise"}),
        SECTION_KIND_SAMPLING: frozenset({"sampling", "sample", "sampler", "diffusion", "denoise"}),
        SECTION_KIND_DECODE: frozenset({"decode", "decoder", "vae", "image"}),
        SECTION_KIND_OUTPUT: frozenset({"output", "save", "preview", "result", "image"}),
        SECTION_KIND_CONTROL: frozenset({"control", "controlnet", "adapter", "reference"}),
        SECTION_KIND_POSTPROCESS: frozenset({"postprocess", "post", "upscale", "resize", "filter"}),
        SECTION_KIND_UTILITY: frozenset({"utility", "helper", "note", "reroute"}),
        SECTION_KIND_BRANCH: frozenset({"branch", "alternative", "parallel"}),
        SECTION_KIND_CONTAINER: frozenset({"container", "scope", "subgraph"}),
        SECTION_KIND_CUSTOM: frozenset({"custom", "group"}),
    }
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


def _candidate_schema_hash() -> str:
    payload = json.dumps(
        {"entry_keys": list(_ENTRY_KEYS), "section_keys": list(_SECTION_KEYS)},
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.blake2b(payload, digest_size=8).hexdigest()


@dataclass(frozen=True, slots=True)
class LayoutCompileOptions:
    spacing_preset: SpacingPreset = "balanced"
    existing_group_policy: ExistingGroupPolicy = "semantic_preserve"
    force_regroup: bool = False
    pinned_refs: tuple[CanonicalNodeRef, ...] = ()
    preserve_node_sizes: bool = True

    def __post_init__(self) -> None:
        if self.spacing_preset not in {"compact", "balanced", "wide"}:
            raise ValueError(f"unknown spacing preset: {self.spacing_preset!r}")
        if self.existing_group_policy not in {
            "preserve",
            "rename_only",
            "resize_only",
            "rename_and_resize",
            "semantic_preserve",
            "dissolve_with_warning",
            "force_regroup",
        }:
            raise ValueError(f"unknown existing group policy: {self.existing_group_policy!r}")
        object.__setattr__(self, "pinned_refs", tuple(self.pinned_refs))

    def to_json(self) -> dict[str, Any]:
        return {
            "spacing_preset": self.spacing_preset,
            "existing_group_policy": self.existing_group_policy,
            "force_regroup": self.force_regroup,
            "pinned_refs": [ref.to_json() for ref in self.pinned_refs],
            "preserve_node_sizes": self.preserve_node_sizes,
        }


@dataclass(frozen=True, slots=True)
class CompiledNodeLayout:
    ref: CanonicalNodeRef
    section_id: str
    role_hint: RoleHint
    x: int
    y: int
    width: int = DEFAULT_NODE_WIDTH
    height: int = DEFAULT_NODE_HEIGHT
    pinned: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "ref": self.ref.to_json(),
            "section_id": self.section_id,
            "role_hint": self.role_hint,
            "pos": [self.x, self.y],
            "size": [self.width, self.height],
            "pinned": self.pinned,
        }


@dataclass(frozen=True, slots=True)
class CompiledGroupLayout:
    id: str
    scope_path: str
    title: str
    kind: SectionKind
    node_refs: tuple[CanonicalNodeRef, ...]
    x: int
    y: int
    width: int
    height: int
    color: str
    role_hint: RoleHint | None = None
    template: SectionTemplate | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_refs", tuple(self.node_refs))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "scope_path": self.scope_path,
            "title": self.title,
            "kind": self.kind,
            "nodes": [ref.to_json() for ref in self.node_refs],
            "bounding": [self.x, self.y, self.width, self.height],
            "color": self.color,
        }
        if self.role_hint is not None:
            payload["role_hint"] = self.role_hint
        if self.template is not None:
            payload["template"] = self.template
        return payload


@dataclass(frozen=True, slots=True)
class CompiledSectionTopology:
    section_id: str
    scope_path: str
    island_index: int
    rank: int
    scc_id: str
    auto_name: str
    predecessor_ids: tuple[str, ...] = ()
    successor_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "predecessor_ids", tuple(self.predecessor_ids))
        object.__setattr__(self, "successor_ids", tuple(self.successor_ids))

    def to_json(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "scope_path": self.scope_path,
            "island_index": self.island_index,
            "rank": self.rank,
            "scc_id": self.scc_id,
            "auto_name": self.auto_name,
            "predecessor_ids": list(self.predecessor_ids),
            "successor_ids": list(self.successor_ids),
        }


@dataclass(frozen=True, slots=True)
class CompiledSamplerRelation:
    kind: Literal["sequential", "parallel", "independent", "mixed"]
    samplers: tuple[CanonicalNodeRef, ...]
    section_ids: tuple[str, ...]
    auto_name: str
    source: CanonicalNodeRef | None = None
    target: CanonicalNodeRef | None = None
    bridge_path: tuple[CanonicalNodeRef, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "samplers", tuple(self.samplers))
        object.__setattr__(self, "section_ids", tuple(self.section_ids))
        object.__setattr__(self, "bridge_path", tuple(self.bridge_path))
        object.__setattr__(self, "reasons", tuple(self.reasons))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind,
            "samplers": [ref.to_json() for ref in self.samplers],
            "section_ids": list(self.section_ids),
            "auto_name": self.auto_name,
            "bridge_path": [ref.to_json() for ref in self.bridge_path],
            "reasons": list(self.reasons),
        }
        if self.source is not None:
            payload["source"] = self.source.to_json()
        if self.target is not None:
            payload["target"] = self.target.to_json()
        return payload


@dataclass(frozen=True, slots=True)
class LayoutCandidatePatch:
    entries: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    groups: tuple[Mapping[str, Any], ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)
    last_reroute_id: Any = None
    definitions: Mapping[str, Any] = field(default_factory=dict)
    virtual_wires: Mapping[str, Any] = field(default_factory=dict)
    store_version: int = STORE_VERSION
    vibecomfy_version: str = "0"
    schema_hash: str = field(default_factory=_candidate_schema_hash)
    unkeyed: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "entries",
            MappingProxyType(
                {str(key): _freeze_jsonish(value) for key, value in self.entries.items()}
            ),
        )
        object.__setattr__(self, "groups", tuple(_freeze_jsonish(group) for group in self.groups))
        object.__setattr__(self, "extra", _freeze_jsonish(self.extra))
        object.__setattr__(self, "definitions", _freeze_jsonish(self.definitions))
        object.__setattr__(self, "virtual_wires", _freeze_jsonish(self.virtual_wires))
        object.__setattr__(self, "unkeyed", tuple(self.unkeyed))

    def to_json(self) -> dict[str, Any]:
        return {
            "store_version": self.store_version,
            "vibecomfy_version": self.vibecomfy_version,
            "schema_hash": self.schema_hash,
            "entries": _thaw_jsonish(self.entries),
            "groups": [_thaw_jsonish(group) for group in self.groups],
            "extra": _thaw_jsonish(self.extra),
            "lastRerouteId": self.last_reroute_id,
            "definitions": _thaw_jsonish(self.definitions),
            "virtual_wires": _thaw_jsonish(self.virtual_wires),
            "unkeyed": list(self.unkeyed),
        }


@dataclass(frozen=True, slots=True)
class LayoutCompileResult:
    ok: bool
    options: LayoutCompileOptions
    node_layouts: tuple[CompiledNodeLayout, ...]
    group_layouts: tuple[CompiledGroupLayout, ...]
    section_topologies: tuple[CompiledSectionTopology, ...]
    sampler_relations: tuple[CompiledSamplerRelation, ...]
    candidate_patch: LayoutCandidatePatch
    validation_report: ReorganiseDiagnosticReport
    report: Any
    structural_hash_before: str
    structural_hash_after: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_layouts", tuple(self.node_layouts))
        object.__setattr__(self, "group_layouts", tuple(self.group_layouts))
        object.__setattr__(self, "section_topologies", tuple(self.section_topologies))
        object.__setattr__(self, "sampler_relations", tuple(self.sampler_relations))

    @property
    def diagnostics(self) -> tuple[Any, ...]:
        return self.report.diagnostics

    @property
    def metrics(self) -> tuple[AssessmentMetric, ...]:
        return self.report.metrics

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "options": self.options.to_json(),
            "structural_hash_before": self.structural_hash_before,
            "structural_hash_after": self.structural_hash_after,
            "node_layouts": [layout.to_json() for layout in self.node_layouts],
            "group_layouts": [layout.to_json() for layout in self.group_layouts],
            "section_topologies": [topology.to_json() for topology in self.section_topologies],
            "sampler_relations": [relation.to_json() for relation in self.sampler_relations],
            "candidate_patch": self.candidate_patch.to_json(),
            "validation_report": self.validation_report.to_json(),
            "report": self.report.to_json(),
        }


@dataclass(frozen=True, slots=True)
class _Spacing:
    section_gap_x: int
    island_gap_x: int
    band_gap_y: int
    section_gap_y: int
    node_gap_y: int
    group_padding: int


@dataclass(frozen=True, slots=True)
class _CompileSection:
    id: str
    kind: SectionKind
    title: str
    role_hint: RoleHint | None
    node_refs: tuple[CanonicalNodeRef, ...]
    parent_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_refs", tuple(self.node_refs))


@dataclass(frozen=True, slots=True)
class _GeneratedSection:
    kind: SectionKind
    title: str
    role_hint: RoleHint | None = None


@dataclass(frozen=True, slots=True)
class _ExistingGroupScore:
    scope_path: str
    index: int
    title: str | None
    section_kind: SectionKind
    member_refs: tuple[CanonicalNodeRef, ...]
    contained_refs: tuple[CanonicalNodeRef, ...]
    containment: float
    topology: float
    title_role: float
    node_coverage: float
    score: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_refs", tuple(self.member_refs))
        object.__setattr__(self, "contained_refs", tuple(self.contained_refs))

    @property
    def coherent(self) -> bool:
        return (
            self.score >= EXISTING_GROUP_SCORE_THRESHOLD
            and self.containment > 0.0
            and self.node_coverage >= EXISTING_GROUP_MIN_NODE_COVERAGE
            and (
                self.title_role >= EXISTING_GROUP_MIN_ROLE_OR_TOPOLOGY
                or self.topology >= EXISTING_GROUP_MIN_ROLE_OR_TOPOLOGY
            )
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "scope_path": self.scope_path,
            "index": self.index,
            "title": self.title,
            "section_kind": self.section_kind,
            "member_refs": [ref.to_json() for ref in self.member_refs],
            "contained_refs": [ref.to_json() for ref in self.contained_refs],
            "containment": round(self.containment, 4),
            "topology": round(self.topology, 4),
            "title_role": round(self.title_role, 4),
            "node_coverage": round(self.node_coverage, 4),
            "score": round(self.score, 4),
            "coherent": self.coherent,
        }


@dataclass(frozen=True, slots=True)
class _ExistingGroupRect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class _CompileRect:
    key: str
    x: float
    y: float
    width: float
    height: float
    ref: CanonicalNodeRef | None = None
    group: CompiledGroupLayout | None = None

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)


@dataclass(frozen=True, slots=True)
class _SectionPlacement:
    rank: int
    band: int
    row: int
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class _LocalSectionLayout:
    template: SectionTemplate
    offsets: Mapping[CanonicalNodeRef, tuple[int, int]]
    width: int
    height: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "offsets", MappingProxyType(dict(self.offsets)))


def compile_layout_plan(
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    *,
    options: LayoutCompileOptions | None = None,
) -> LayoutCompileResult:
    opts = options or LayoutCompileOptions()
    validation_report = validate_layout_plan(plan, facts)
    structural_hash = structural_hash_for_layout_facts(facts)
    if not validation_report.ok:
        candidate_patch = LayoutCandidatePatch()
        report = _build_report(
            node_layouts=(),
            group_layouts=(),
            facts=facts,
            candidate_patch=candidate_patch,
            structural_hash_before=structural_hash,
            structural_hash_after=structural_hash,
            diagnostics=validation_report.diagnostics,
        )
        return LayoutCompileResult(
            ok=False,
            options=opts,
            node_layouts=(),
            group_layouts=(),
            section_topologies=(),
            sampler_relations=(),
            candidate_patch=candidate_patch,
            validation_report=validation_report,
            report=report,
            structural_hash_before=structural_hash,
            structural_hash_after=structural_hash,
        )

    classification = classify_layout_facts(facts)
    sections = _compile_sections(plan, facts, classification, opts)
    section_topologies = _compile_section_topologies(sections, facts)
    sampler_relations = _normalize_sampler_relations(plan, facts, sections)
    node_layouts, group_layouts = _layout_sections(
        plan,
        sections,
        section_topologies,
        facts,
        opts,
        classification,
    )
    group_layouts, policy_issues = _apply_existing_group_policy(
        group_layouts,
        facts,
        opts,
        classification,
    )
    candidate_patch = _candidate_patch(node_layouts, group_layouts, facts, opts)
    report = _build_report(
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        facts=facts,
        candidate_patch=candidate_patch,
        structural_hash_before=structural_hash,
        structural_hash_after=structural_hash,
        diagnostics=validation_report.diagnostics,
        issues=policy_issues,
    )
    return LayoutCompileResult(
        ok=validation_report.ok and report.verdict != "blocked",
        options=opts,
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        section_topologies=section_topologies,
        sampler_relations=sampler_relations,
        candidate_patch=candidate_patch,
        validation_report=validation_report,
        report=report,
        structural_hash_before=structural_hash,
        structural_hash_after=structural_hash,
    )


def compile_layout_plan_from_ui(
    plan: LayoutPlanV1,
    ui_json: Mapping[str, Any],
    *,
    sidecar_envelope: Mapping[str, Any] | None = None,
    options: LayoutCompileOptions | None = None,
) -> LayoutCompileResult:
    facts = extract_graph_facts(ui_json, sidecar_envelope=sidecar_envelope)
    return compile_layout_plan(plan, facts, options=options)


def structural_hash_for_layout_facts(facts: GraphInventoryFacts) -> str:
    """Return a deterministic runtime-structure hash for compiler invariance.

    Layout-store furniture sections such as entries, groups, extra,
    lastRerouteId, definitions payloads, and virtual_wires payloads are
    intentionally excluded. The hash is over canonical node identities, classes,
    helper status, and effective topology facts available to the compiler.
    """

    payload = {
        "canonical_refs": [
            {
                "ref": fact.ref.to_json(),
                "class_type": fact.class_type,
                "is_helper": fact.is_helper,
            }
            for fact in sorted(facts.canonical_refs, key=lambda fact: _ref_sort_key(fact.ref))
        ],
        "scope_topologies": [
            topology.to_json()
            for topology in sorted(facts.scope_topologies, key=lambda topology: topology.scope_path)
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.blake2b(raw, digest_size=16).hexdigest()


def _compile_sections(
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    classification: ClassificationReport,
    options: LayoutCompileOptions,
) -> tuple[_CompileSection, ...]:
    section_defs = {section.id: section for section in plan.sections}
    generated_defs: dict[str, _GeneratedSection] = {}
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}

    primary_owned: dict[CanonicalNodeRef, str] = {}
    for section in plan.sections:
        for ref in section.nodes:
            if ref not in helper_refs:
                primary_owned[ref] = section.id
    for shared in plan.shared_nodes:
        if shared.node not in helper_refs:
            primary_owned[shared.node] = shared.home

    helper_targets: dict[CanonicalNodeRef, str] = {}
    for placement in plan.helper_placements:
        helper_targets[placement.helper] = _helper_section_id(placement, primary_owned)

    owned: dict[CanonicalNodeRef, str] = dict(primary_owned)
    for helper_ref in helper_refs:
        owned[helper_ref] = helper_targets.get(helper_ref, "__helpers__")

    unassigned = tuple(
        fact.ref
        for fact in sorted(facts.canonical_refs, key=lambda item: _ref_sort_key(item.ref))
        if fact.ref not in primary_owned and fact.ref not in helper_refs
    )
    if plan.unassigned_policy == UNASSIGNED_PRESERVE_EXISTING and _can_preserve_existing_groups(options):
        preserved = _preserved_existing_ownership(
            facts,
            unassigned_refs=unassigned,
            assigned_refs=set(primary_owned),
            classification=classification,
        )
        for ref, generated in preserved.items():
            owned[ref] = generated[0]
            generated_defs.setdefault(generated[0], generated[1])

    if plan.unassigned_policy in {
        UNASSIGNED_CLASSIFY_DETERMINISTICALLY,
        UNASSIGNED_PRESERVE_EXISTING,
    }:
        for ref in unassigned:
            if ref in owned:
                continue
            fact = canonical_by_ref.get(ref)
            hint = classification.hint_for(ref)
            role = hint.role_hint if hint is not None else fact.role_hint if fact is not None else ROLE_HINT_UNKNOWN
            owned[ref] = _section_for_role(role, section_defs)
    elif plan.unassigned_policy == UNASSIGNED_REJECT:
        pass

    refs_by_section: dict[str, list[CanonicalNodeRef]] = {}
    for ref, section_id in sorted(owned.items(), key=lambda item: _ref_sort_key(item[0])):
        refs_by_section.setdefault(section_id, []).append(ref)

    section_ids_to_emit = set(refs_by_section)
    parent_ids = {
        section.parent_id
        for section in plan.sections
        if section.parent_id is not None
    }
    for section in plan.sections:
        if section.kind == SECTION_KIND_CONTAINER or section.id in parent_ids:
            section_ids_to_emit.add(section.id)

    sections: list[_CompileSection] = []
    for section_id in sorted(
        section_ids_to_emit,
        key=lambda item: _section_sort_key(item, section_defs.get(item), refs_by_section.get(item, ())),
    ):
        refs = refs_by_section.get(section_id, [])
        section = section_defs.get(section_id)
        generated = generated_defs.get(section_id)
        kind = (
            section.kind
            if section is not None
            else generated.kind
            if generated is not None
            else _generated_section_kind(section_id)
        )
        title = (
            section.title
            if section is not None and section.title is not None
            else generated.title
            if generated is not None
            else _title_for(section_id, kind)
        )
        sections.append(
            _CompileSection(
                id=section_id,
                kind=kind,
                title=title,
                role_hint=section.role_hint if section is not None else generated.role_hint if generated is not None else None,
                node_refs=tuple(sorted(refs, key=_ref_sort_key)),
                parent_id=section.parent_id if section is not None else None,
            )
        )
    return tuple(sections)


def _compile_section_topologies(
    sections: Sequence[_CompileSection],
    facts: GraphInventoryFacts,
) -> tuple[CompiledSectionTopology, ...]:
    section_by_id = {section.id: section for section in sections}
    ref_to_section = {
        ref: section.id
        for section in sections
        for ref in section.node_refs
    }
    section_edges: dict[str, set[str]] = {section.id: set() for section in sections}
    for topology in facts.scope_topologies:
        for edge in topology.effective_edges:
            source_section = ref_to_section.get(edge.source)
            target_section = ref_to_section.get(edge.target)
            if source_section is None or target_section is None or source_section == target_section:
                continue
            section_edges.setdefault(source_section, set()).add(target_section)
            section_edges.setdefault(target_section, set())

    scc_by_section, members_by_scc = _section_sccs(section_edges)
    component_edges = _component_edges(section_edges, scc_by_section)
    island_by_component = _component_islands(component_edges, members_by_scc, section_by_id)
    rank_by_component = _component_ranks(component_edges, island_by_component, members_by_scc, section_by_id)
    predecessor_ids = {section.id: set() for section in sections}
    successor_ids = {section.id: set(section_edges.get(section.id, ())) for section in sections}
    for source, targets in section_edges.items():
        for target in targets:
            predecessor_ids.setdefault(target, set()).add(source)

    topologies: list[CompiledSectionTopology] = []
    for section in sections:
        scc_id = scc_by_section[section.id]
        topologies.append(
            CompiledSectionTopology(
                section_id=section.id,
                scope_path=_common_scope(section.node_refs),
                island_index=island_by_component[scc_id],
                rank=rank_by_component[scc_id],
                scc_id=scc_id,
                auto_name=_stable_auto_name(section, scc_id),
                predecessor_ids=tuple(sorted(predecessor_ids.get(section.id, ()), key=_id_sort_key)),
                successor_ids=tuple(sorted(successor_ids.get(section.id, ()), key=_id_sort_key)),
            )
        )
    return tuple(sorted(topologies, key=lambda item: (item.scope_path, item.island_index, item.rank, item.scc_id, item.section_id)))


def _normalize_sampler_relations(
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    sections: Sequence[_CompileSection],
) -> tuple[CompiledSamplerRelation, ...]:
    sampler_refs = tuple(
        sorted(
            (
                fact.ref
                for fact in facts.canonical_refs
                if "sampler" in fact.class_type.lower()
            ),
            key=_ref_sort_key,
        )
    )
    if len(sampler_refs) < 2:
        return ()

    ref_to_section = {
        ref: section.id
        for section in sections
        for ref in section.node_refs
    }
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    adjacency = _effective_ref_adjacency(facts)
    relation_claims = tuple(plan.sampler_relations) + tuple(facts.summary.sampler_relation_candidates)
    claims_by_pair: dict[frozenset[CanonicalNodeRef], list[SamplerRelationClaim]] = {}
    for claim in relation_claims:
        if len(claim.samplers) != 2:
            continue
        claims_by_pair.setdefault(frozenset(claim.samplers), []).append(claim)

    relations: list[CompiledSamplerRelation] = []
    pair_kinds: dict[frozenset[CanonicalNodeRef], str] = {}
    for index, left in enumerate(sampler_refs):
        for right in sampler_refs[index + 1:]:
            pair = (left, right)
            claims = tuple(sorted(claims_by_pair.get(frozenset(pair), ()), key=_sampler_claim_sort_key))
            relation = _normalized_sampler_pair(
                pair,
                claims,
                adjacency,
                ref_to_section,
                canonical_by_ref,
            )
            relations.append(relation)
            pair_kinds[frozenset(pair)] = relation.kind

    aggregate = _mixed_sampler_aggregate(relations, ref_to_section)
    if aggregate is not None:
        relations.append(aggregate)
    return tuple(sorted(relations, key=_compiled_sampler_relation_sort_key))


def _layout_sections(
    plan: LayoutPlanV1,
    sections: Sequence[_CompileSection],
    section_topologies: Sequence[CompiledSectionTopology],
    facts: GraphInventoryFacts,
    options: LayoutCompileOptions,
    classification: ClassificationReport,
) -> tuple[tuple[CompiledNodeLayout, ...], tuple[CompiledGroupLayout, ...]]:
    spacing = _spacing(options.spacing_preset)
    furniture_by_ref = {fact.ref: fact for fact in facts.node_furniture}
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    pinned_refs = _effective_pinned_refs(facts, options, classification)
    topology_by_section = {topology.section_id: topology for topology in section_topologies}
    placements = _section_placements(sections, section_topologies, facts, spacing, furniture_by_ref, options)
    node_layouts: list[CompiledNodeLayout] = []
    for section in sorted(
        sections,
        key=lambda section: _section_placement_sort_key(section, placements, topology_by_section),
    ):
        placement = placements[section.id]
        x = placement.x
        y = placement.y
        local_layout = _local_section_layout(section, facts, furniture_by_ref, options, spacing, plan)
        for ref in section.node_refs:
            furniture = furniture_by_ref.get(ref)
            width, height = _node_size(furniture, preserve=options.preserve_node_sizes)
            local_x, local_y = local_layout.offsets[ref]
            node_x = x + spacing.group_padding + local_x
            node_y = y + spacing.group_padding + DEFAULT_GROUP_HEADER_HEIGHT + local_y
            if ref in pinned_refs and furniture is not None:
                pinned_pos = _pos(furniture.pos)
                if pinned_pos is not None:
                    node_x, node_y = pinned_pos
            hint = classification.hint_for(ref)
            fact = canonical_by_ref.get(ref)
            layout = CompiledNodeLayout(
                ref=ref,
                section_id=section.id,
                role_hint=(
                    hint.role_hint
                    if hint is not None
                    else fact.role_hint
                    if fact is not None
                    else ROLE_HINT_UNKNOWN
                ),
                x=node_x,
                y=node_y,
                width=width,
                height=height,
                pinned=ref in pinned_refs,
            )
            node_layouts.append(layout)
    node_layouts = list(_apply_floating_helper_positions(plan, node_layouts, spacing))
    node_layouts = list(_resolve_node_collisions(node_layouts, facts, spacing))
    group_layouts = _compiled_group_layouts(sections, node_layouts, facts, spacing)
    return tuple(sorted(node_layouts, key=lambda layout: _ref_sort_key(layout.ref))), group_layouts


def _section_placements(
    sections: Sequence[_CompileSection],
    section_topologies: Sequence[CompiledSectionTopology],
    facts: GraphInventoryFacts,
    spacing: _Spacing,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: LayoutCompileOptions,
) -> dict[str, _SectionPlacement]:
    topology_by_section = {topology.section_id: topology for topology in section_topologies}
    effective_ranks = _effective_section_ranks(sections, section_topologies)
    raw_band_by_section = {
        section.id: _section_band(section, facts)
        for section in sections
    }
    band_y_index = _normalized_band_indices(sections, topology_by_section, raw_band_by_section)
    next_y_by_lane: dict[tuple[str, int, int, int], int] = {}
    row_by_lane: dict[tuple[str, int, int, int], int] = {}
    placements: dict[str, _SectionPlacement] = {}
    for section in sorted(
        sections,
        key=lambda item: (
            _topology_for(item, topology_by_section).scope_path,
            _topology_for(item, topology_by_section).island_index,
            effective_ranks[item.id],
            raw_band_by_section[item.id],
            *_section_semantic_sort_key(item),
        ),
    ):
        topology = _topology_for(section, topology_by_section)
        rank = effective_ranks[section.id]
        band = raw_band_by_section[section.id]
        lane = (topology.scope_path, topology.island_index, rank, band)
        row = row_by_lane.get(lane, 0)
        base_y = band_y_index[(topology.scope_path, topology.island_index, band)] * spacing.band_gap_y
        y = base_y + next_y_by_lane.get(lane, 0)
        x = topology.island_index * spacing.island_gap_x + rank * spacing.section_gap_x
        placements[section.id] = _SectionPlacement(rank=rank, band=band, row=row, x=x, y=y)
        next_y_by_lane[lane] = (
            next_y_by_lane.get(lane, 0)
            + _estimated_section_height(section, facts, furniture_by_ref, options, spacing)
            + spacing.section_gap_y
        )
        row_by_lane[lane] = row + 1
    return placements


def _effective_section_ranks(
    sections: Sequence[_CompileSection],
    section_topologies: Sequence[CompiledSectionTopology],
) -> dict[str, int]:
    topology_by_section = {topology.section_id: topology for topology in section_topologies}
    scc_members: dict[str, list[_CompileSection]] = {}
    for section in sections:
        topology = _topology_for(section, topology_by_section)
        scc_members.setdefault(topology.scc_id, []).append(section)

    rank_by_scc: dict[str, int] = {}
    for scc_id, members in sorted(scc_members.items()):
        rank_by_scc[scc_id] = max(
            max(
                topology_by_section.get(member.id, CompiledSectionTopology(member.id, _common_scope(member.node_refs), 0, 0, scc_id, member.id)).rank,
                _SECTION_MIN_RANKS.get(member.kind, _SECTION_MIN_RANKS[SECTION_KIND_CUSTOM]),
            )
            for member in members
        )

    scc_edges: dict[str, set[str]] = {scc_id: set() for scc_id in scc_members}
    for topology in section_topologies:
        for successor_id in topology.successor_ids:
            successor = topology_by_section.get(successor_id)
            if successor is None or successor.scc_id == topology.scc_id:
                continue
            scc_edges.setdefault(topology.scc_id, set()).add(successor.scc_id)
            scc_edges.setdefault(successor.scc_id, set())

    for _iteration in range(len(scc_edges) + 1):
        changed = False
        for source_scc in sorted(scc_edges, key=_id_sort_key):
            source_rank = rank_by_scc.get(source_scc, 0)
            for target_scc in sorted(scc_edges[source_scc], key=_id_sort_key):
                target_rank = rank_by_scc.get(target_scc, 0)
                if target_rank < source_rank + 1:
                    rank_by_scc[target_scc] = source_rank + 1
                    changed = True
        if not changed:
            break

    return {
        section.id: rank_by_scc[_topology_for(section, topology_by_section).scc_id]
        for section in sections
    }


def _topology_for(
    section: _CompileSection,
    topology_by_section: Mapping[str, CompiledSectionTopology],
) -> CompiledSectionTopology:
    topology = topology_by_section.get(section.id)
    if topology is not None:
        return topology
    return CompiledSectionTopology(
        section_id=section.id,
        scope_path=_common_scope(section.node_refs),
        island_index=0,
        rank=0,
        scc_id=section.id,
        auto_name=_stable_auto_name(section, section.id),
    )


def _section_band(section: _CompileSection, facts: GraphInventoryFacts) -> int:
    if _is_model_pipe_section(section, facts):
        return -1
    if section.kind in {SECTION_KIND_UTILITY, SECTION_KIND_CUSTOM} or section.role_hint in {
        ROLE_HINT_HELPER,
        ROLE_HINT_UI,
        ROLE_HINT_UTILITY,
    }:
        return 1
    return 0


def _is_model_pipe_section(section: _CompileSection, facts: GraphInventoryFacts) -> bool:
    if section.kind != SECTION_KIND_LOADERS:
        return False
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    for ref in section.node_refs:
        fact = canonical_by_ref.get(ref)
        class_type = str(getattr(fact, "class_type", "")).lower()
        if any(token in class_type for token in ("checkpoint", "clip", "lora", "unet", "vae", "model")):
            return True
    return False


def _normalized_band_indices(
    sections: Sequence[_CompileSection],
    topology_by_section: Mapping[str, CompiledSectionTopology],
    raw_band_by_section: Mapping[str, int],
) -> dict[tuple[str, int, int], int]:
    bands_by_island: dict[tuple[str, int], set[int]] = {}
    for section in sections:
        topology = _topology_for(section, topology_by_section)
        bands_by_island.setdefault((topology.scope_path, topology.island_index), set()).add(
            raw_band_by_section[section.id]
        )
    indices: dict[tuple[str, int, int], int] = {}
    for island_key, bands in sorted(bands_by_island.items()):
        for index, band in enumerate(sorted(bands)):
            indices[(*island_key, band)] = index
    return indices


def _estimated_section_height(
    section: _CompileSection,
    facts: GraphInventoryFacts,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: LayoutCompileOptions,
    spacing: _Spacing,
) -> int:
    local_layout = _local_section_layout(section, facts, furniture_by_ref, options, spacing, None)
    return (
        DEFAULT_GROUP_HEADER_HEIGHT
        + spacing.group_padding * 2
        + local_layout.height
    )


def _local_section_layout(
    section: _CompileSection,
    facts: GraphInventoryFacts,
    furniture_by_ref: Mapping[CanonicalNodeRef, NodeFurnitureFact],
    options: LayoutCompileOptions,
    spacing: _Spacing,
    plan: LayoutPlanV1 | None,
) -> _LocalSectionLayout:
    refs = tuple(section.node_refs)
    sizes = {
        ref: _node_size(furniture_by_ref.get(ref), preserve=options.preserve_node_sizes)
        for ref in refs
    }
    if not refs:
        return _LocalSectionLayout(template="single", offsets={}, width=0, height=0)

    edges = _section_effective_edges(facts, refs)
    if _use_large_section_clusters(section, facts, edges):
        template = "grid"
        offsets = _large_section_cluster_offsets(refs, edges, facts, sizes, spacing)
    else:
        template = _select_section_template(section, facts, edges)
        offsets = _offsets_for_template(template, refs, edges, facts, sizes, spacing)
    if plan is not None:
        offsets = _apply_local_helper_offsets(section, plan, offsets, sizes, spacing)
    for ref in refs:
        if ref not in offsets:
            offsets = {**offsets, ref: (0, len(offsets) * (sizes[ref][1] + spacing.node_gap_y))}
    width, height = _local_bounds(offsets, sizes)
    return _LocalSectionLayout(template=template, offsets=offsets, width=width, height=height)


def _select_section_template(
    section: _CompileSection,
    facts: GraphInventoryFacts,
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> SectionTemplate:
    refs = tuple(section.node_refs)
    if len(refs) == 1:
        return "single"
    if _note_refs(refs, facts):
        return "notes_sidebar"
    if section.kind == SECTION_KIND_BRANCH and _parallel_branch_candidate(refs, facts) is not None:
        return "parallel_branches"
    if _is_alternatives_section(section, facts, edges):
        return "alternatives"
    if _hub_ref(refs, edges) is not None:
        return "hub_and_spokes"
    if _fan_in_ref(refs, edges) is not None:
        return "fan_in"
    if _fan_out_ref(refs, edges) is not None:
        return "fan_out"
    if _is_pipeline(refs, edges):
        return "pipeline"
    if len(refs) == 2:
        return "pair"
    if len(refs) <= 4:
        return "row"
    return "grid"


def _offsets_for_template(
    template: SectionTemplate,
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
    facts: GraphInventoryFacts,
    sizes: Mapping[CanonicalNodeRef, tuple[int, int]],
    spacing: _Spacing,
) -> dict[CanonicalNodeRef, tuple[int, int]]:
    ordered = tuple(sorted(refs, key=lambda ref: _local_ref_sort_key(ref, facts)))
    gap_x = spacing.node_gap_y
    gap_y = spacing.node_gap_y

    if template == "single":
        return {ordered[0]: (0, 0)}
    if template in {"pair", "alternatives"}:
        return _layout_columns((ordered,), sizes, gap_x, gap_y)
    if template == "row":
        return _layout_columns(tuple((ref,) for ref in ordered), sizes, gap_x, gap_y)
    if template == "grid":
        return _layout_grid(ordered, sizes, gap_x, gap_y)
    if template == "pipeline":
        return _layout_columns(_local_layers(ordered, edges, facts), sizes, gap_x, gap_y)
    if template == "fan_in":
        sink = _fan_in_ref(ordered, edges)
        if sink is not None:
            predecessors = tuple(sorted({source for source, target in edges if target == sink}, key=lambda ref: _local_ref_sort_key(ref, facts)))
            remainder = tuple(ref for ref in ordered if ref != sink and ref not in predecessors)
            return _layout_columns(((*predecessors, *remainder), (sink,)), sizes, gap_x, gap_y)
    if template == "fan_out":
        source = _fan_out_ref(ordered, edges)
        if source is not None:
            successors = tuple(sorted({target for item_source, target in edges if item_source == source}, key=lambda ref: _local_ref_sort_key(ref, facts)))
            remainder = tuple(ref for ref in ordered if ref != source and ref not in successors)
            return _layout_columns(((source,), (*successors, *remainder)), sizes, gap_x, gap_y)
    if template == "hub_and_spokes":
        hub = _hub_ref(ordered, edges)
        if hub is not None:
            inputs = tuple(sorted({source for source, target in edges if target == hub}, key=lambda ref: _local_ref_sort_key(ref, facts)))
            outputs = tuple(sorted({target for source, target in edges if source == hub}, key=lambda ref: _local_ref_sort_key(ref, facts)))
            remainder = tuple(ref for ref in ordered if ref != hub and ref not in inputs and ref not in outputs)
            return _layout_columns((inputs, (hub, *remainder), outputs), sizes, gap_x, gap_y)
    if template == "parallel_branches":
        candidate = _parallel_branch_candidate(ordered, facts)
        if candidate is not None:
            source, roots, terminals = candidate
            used = {source, *roots, *terminals}
            remainder = tuple(ref for ref in ordered if ref not in used)
            terminal_column = terminals if terminals else remainder
            middle_column = (*roots, *(() if terminals else remainder))
            tail_column = terminal_column if terminals else ()
            columns = tuple(column for column in ((source,), middle_column, tail_column) if column)
            return _layout_columns(columns, sizes, gap_x, gap_y)
    if template == "notes_sidebar":
        notes = _note_refs(ordered, facts)
        main = tuple(ref for ref in ordered if ref not in notes)
        main_offsets = _layout_columns(_local_layers(main, edges, facts) if main else (), sizes, gap_x, gap_y) if main else {}
        main_width, _main_height = _local_bounds(main_offsets, sizes)
        note_offsets = _layout_columns((notes,), sizes, gap_x, gap_y)
        return {
            **main_offsets,
            **{ref: (main_width + gap_x + x, y) for ref, (x, y) in note_offsets.items()},
        }
    return _layout_grid(ordered, sizes, gap_x, gap_y)


def _use_large_section_clusters(
    section: _CompileSection,
    facts: GraphInventoryFacts,
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> bool:
    if section.kind == SECTION_KIND_CONTAINER or len(section.node_refs) < 2:
        return False
    if len(section.node_refs) >= COMPILE_HUGE_WORKFLOW_NODE_THRESHOLD:
        return True
    if len(edges) >= COMPILE_HUGE_WORKFLOW_EDGE_THRESHOLD:
        return True
    return _facts_projection_token_estimate(facts) >= COMPILE_HUGE_WORKFLOW_PROJECTION_TOKEN_THRESHOLD


def _facts_projection_token_estimate(facts: GraphInventoryFacts) -> int:
    payload = {
        "summary": facts.summary.to_json(),
        "scope_topologies": [
            {
                "scope_path": topology.scope_path,
                "node_count": len(topology.node_topology),
                "edge_count": len(topology.effective_edges),
                "truncated": topology.truncated,
            }
            for topology in facts.scope_topologies
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return max(1, (len(raw) + 3) // 4)


def _large_section_cluster_offsets(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
    facts: GraphInventoryFacts,
    sizes: Mapping[CanonicalNodeRef, tuple[int, int]],
    spacing: _Spacing,
) -> dict[CanonicalNodeRef, tuple[int, int]]:
    clusters_by_row = _large_section_clusters(refs, edges, facts)
    offsets: dict[CanonicalNodeRef, tuple[int, int]] = {}
    row_y = 0
    cluster_gap_x = max(spacing.section_gap_x, spacing.node_gap_y * 2)
    cluster_gap_y = max(spacing.section_gap_y, spacing.node_gap_y)
    for row in clusters_by_row:
        cluster_x = 0
        row_height = 0
        for cluster in row:
            y = 0
            cluster_width = max((sizes[ref][0] for ref in cluster), default=0)
            for ref in cluster:
                offsets[ref] = (cluster_x, row_y + y)
                y += sizes[ref][1] + spacing.node_gap_y
            row_height = max(row_height, max(0, y - spacing.node_gap_y))
            cluster_x += cluster_width + cluster_gap_x
        row_y += row_height + cluster_gap_y
    return offsets


def _large_section_clusters(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
    facts: GraphInventoryFacts,
) -> tuple[tuple[tuple[CanonicalNodeRef, ...], ...], ...]:
    ordered_refs = tuple(sorted(refs, key=lambda ref: _local_ref_sort_key(ref, facts)))
    topology_by_ref = {
        node.ref: node
        for topology in facts.scope_topologies
        for node in topology.node_topology
    }
    row_keys = sorted(
        {
            (
                ref.scope_path,
                str(getattr(topology_by_ref.get(ref), "wcc_id", _entry_key(ref))),
            )
            for ref in ordered_refs
        },
        key=lambda item: (0 if item[0] == "" else 1, item[0], _id_sort_key(item[1])),
    )
    rows: list[tuple[tuple[CanonicalNodeRef, ...], ...]] = []
    for row_key in row_keys:
        row_refs = tuple(
            ref
            for ref in ordered_refs
            if (
                ref.scope_path,
                str(getattr(topology_by_ref.get(ref), "wcc_id", _entry_key(ref))),
            )
            == row_key
        )
        if not row_refs:
            continue
        rows.append(_large_section_row_clusters(row_refs, edges, facts))
    return tuple(rows)


def _large_section_row_clusters(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
    facts: GraphInventoryFacts,
) -> tuple[tuple[CanonicalNodeRef, ...], ...]:
    clusters: list[tuple[CanonicalNodeRef, ...]] = []
    current: list[CanonicalNodeRef] = []
    for layer in _local_layers(refs, edges, facts):
        layer_refs = tuple(ref for ref in layer if ref in refs)
        if not layer_refs:
            continue
        if current and len(current) + len(layer_refs) > COMPILE_LARGE_SECTION_CLUSTER_SIZE:
            clusters.append(tuple(current))
            current = []
        for ref in layer_refs:
            current.append(ref)
            if len(current) >= COMPILE_LARGE_SECTION_CLUSTER_SIZE:
                clusters.append(tuple(current))
                current = []
    if current:
        clusters.append(tuple(current))
    return tuple(clusters)


def _apply_local_helper_offsets(
    section: _CompileSection,
    plan: LayoutPlanV1,
    offsets: Mapping[CanonicalNodeRef, tuple[int, int]],
    sizes: Mapping[CanonicalNodeRef, tuple[int, int]],
    spacing: _Spacing,
) -> dict[CanonicalNodeRef, tuple[int, int]]:
    adjusted = dict(offsets)
    section_refs = set(section.node_refs)
    anchor_gap = max(24, spacing.node_gap_y // 2)
    for placement in sorted(plan.helper_placements, key=lambda item: _ref_sort_key(item.helper)):
        helper = placement.helper
        if helper not in section_refs or helper not in sizes:
            continue
        if placement.kind == HELPER_PLACEMENT_INSIDE_SECTION:
            continue
        helper_width, helper_height = sizes[helper]
        if placement.kind == HELPER_PLACEMENT_EDGE_PATH:
            source = placement.source
            destination = placement.destination
            if source in adjusted and destination in adjusted and source in sizes and destination in sizes:
                source_center = _offset_center(adjusted[source], sizes[source])
                target_center = _offset_center(adjusted[destination], sizes[destination])
                adjusted[helper] = (
                    round((source_center[0] + target_center[0] - helper_width) / 2),
                    round((source_center[1] + target_center[1] - helper_height) / 2),
                )
            continue
        target = placement.target
        if target not in adjusted or target not in sizes:
            continue
        target_x, target_y = adjusted[target]
        target_width, target_height = sizes[target]
        y = target_y + max(0, (target_height - helper_height) // 2)
        if placement.kind == HELPER_PLACEMENT_NEAR_PRODUCER:
            adjusted[helper] = (target_x + target_width + anchor_gap, y)
        elif placement.kind == HELPER_PLACEMENT_NEAR_CONSUMER:
            adjusted[helper] = (target_x - helper_width - anchor_gap, y)
    return adjusted


def _offset_center(
    offset: tuple[int, int],
    size: tuple[int, int],
) -> tuple[float, float]:
    return (offset[0] + size[0] / 2, offset[1] + size[1] / 2)


def _section_effective_edges(
    facts: GraphInventoryFacts,
    refs: Sequence[CanonicalNodeRef],
) -> tuple[tuple[CanonicalNodeRef, CanonicalNodeRef], ...]:
    ref_set = set(refs)
    edges: set[tuple[CanonicalNodeRef, CanonicalNodeRef]] = set()
    for topology in facts.scope_topologies:
        for edge in topology.effective_edges:
            if edge.source in ref_set and edge.target in ref_set and edge.source != edge.target:
                edges.add((edge.source, edge.target))
    return tuple(sorted(edges, key=lambda item: (_ref_sort_key(item[0]), _ref_sort_key(item[1]))))


def _note_refs(
    refs: Sequence[CanonicalNodeRef],
    facts: GraphInventoryFacts,
) -> tuple[CanonicalNodeRef, ...]:
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    notes = []
    for ref in refs:
        fact = canonical_by_ref.get(ref)
        class_type = str(getattr(fact, "class_type", "")).lower()
        if "note" in class_type or "markdown" in class_type or "annotation" in class_type:
            notes.append(ref)
    return tuple(sorted(notes, key=lambda ref: _local_ref_sort_key(ref, facts)))


def _parallel_branch_candidate(
    refs: Sequence[CanonicalNodeRef],
    facts: GraphInventoryFacts,
) -> tuple[CanonicalNodeRef, tuple[CanonicalNodeRef, ...], tuple[CanonicalNodeRef, ...]] | None:
    ref_set = set(refs)
    candidates: list[tuple[CanonicalNodeRef, tuple[CanonicalNodeRef, ...], tuple[CanonicalNodeRef, ...]]] = []
    for topology in facts.scope_topologies:
        for candidate in topology.parallel_branch_candidates:
            roots = tuple(root for root in sorted(candidate.branch_roots, key=lambda ref: _local_ref_sort_key(ref, facts)) if root in ref_set)
            if candidate.source not in ref_set or len(roots) < 2:
                continue
            terminals = tuple(
                terminal
                for terminal in sorted(candidate.terminal_refs, key=lambda ref: _local_ref_sort_key(ref, facts))
                if terminal in ref_set
            )
            candidates.append((candidate.source, roots, terminals))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (_ref_sort_key(item[0]), tuple(_ref_sort_key(ref) for ref in item[1])))[0]


def _is_alternatives_section(
    section: _CompileSection,
    facts: GraphInventoryFacts,
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> bool:
    if edges or len(section.node_refs) < 2 or len(section.node_refs) > 4:
        return False
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    roles = {
        getattr(canonical_by_ref.get(ref), "role_hint", ROLE_HINT_UNKNOWN)
        for ref in section.node_refs
    }
    classes = {
        str(getattr(canonical_by_ref.get(ref), "class_type", "")).lower()
        for ref in section.node_refs
    }
    return len(roles) == 1 or len(classes) == 1 or section.kind == SECTION_KIND_BRANCH


def _hub_ref(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> CanonicalNodeRef | None:
    incoming, outgoing = _local_degree_maps(refs, edges)
    candidates = [
        ref
        for ref in refs
        if len(incoming.get(ref, ())) > 0 and len(outgoing.get(ref, ())) > 0 and len(incoming.get(ref, ())) + len(outgoing.get(ref, ())) >= 3
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda ref: (-(len(incoming.get(ref, ())) + len(outgoing.get(ref, ()))), _ref_sort_key(ref)))[0]


def _fan_in_ref(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> CanonicalNodeRef | None:
    incoming, outgoing = _local_degree_maps(refs, edges)
    candidates = [
        ref
        for ref in refs
        if len(incoming.get(ref, ())) >= 2 and len(outgoing.get(ref, ())) == 0
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda ref: (-len(incoming.get(ref, ())), _ref_sort_key(ref)))[0]


def _fan_out_ref(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> CanonicalNodeRef | None:
    incoming, outgoing = _local_degree_maps(refs, edges)
    candidates = [
        ref
        for ref in refs
        if len(outgoing.get(ref, ())) >= 2 and len(incoming.get(ref, ())) == 0
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda ref: (-len(outgoing.get(ref, ())), _ref_sort_key(ref)))[0]


def _local_degree_maps(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> tuple[dict[CanonicalNodeRef, set[CanonicalNodeRef]], dict[CanonicalNodeRef, set[CanonicalNodeRef]]]:
    incoming = {ref: set() for ref in refs}
    outgoing = {ref: set() for ref in refs}
    for source, target in edges:
        outgoing.setdefault(source, set()).add(target)
        incoming.setdefault(target, set()).add(source)
    return incoming, outgoing


def _is_pipeline(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
) -> bool:
    if len(refs) < 3 or len(edges) < len(refs) - 1:
        return False
    incoming, outgoing = _local_degree_maps(refs, edges)
    starts = [ref for ref in refs if not incoming.get(ref)]
    ends = [ref for ref in refs if not outgoing.get(ref)]
    return (
        len(starts) == 1
        and len(ends) == 1
        and all(len(incoming.get(ref, ())) <= 1 and len(outgoing.get(ref, ())) <= 1 for ref in refs)
    )


def _local_layers(
    refs: Sequence[CanonicalNodeRef],
    edges: Sequence[tuple[CanonicalNodeRef, CanonicalNodeRef]],
    facts: GraphInventoryFacts,
) -> tuple[tuple[CanonicalNodeRef, ...], ...]:
    if not refs:
        return ()
    ref_set = set(refs)
    incoming = {ref: set() for ref in refs}
    outgoing = {ref: set() for ref in refs}
    for source, target in edges:
        if source in ref_set and target in ref_set:
            outgoing[source].add(target)
            incoming[target].add(source)
    pending = sorted((ref for ref in refs if not incoming[ref]), key=lambda ref: _local_ref_sort_key(ref, facts))
    processed: set[CanonicalNodeRef] = set()
    layer_by_ref: dict[CanonicalNodeRef, int] = {}
    while pending:
        ref = pending.pop(0)
        if ref in processed:
            continue
        processed.add(ref)
        layer_by_ref[ref] = max((layer_by_ref.get(source, 0) + 1 for source in incoming[ref]), default=0)
        for target in sorted(outgoing[ref], key=lambda item: _local_ref_sort_key(item, facts)):
            if target not in processed and all(source in processed for source in incoming[target]):
                pending.append(target)
    for ref in sorted((ref for ref in refs if ref not in processed), key=lambda item: _local_ref_sort_key(item, facts)):
        layer_by_ref[ref] = max(layer_by_ref.values(), default=-1) + 1
    layers: dict[int, list[CanonicalNodeRef]] = {}
    for ref, layer in layer_by_ref.items():
        layers.setdefault(layer, []).append(ref)
    return tuple(
        tuple(sorted(items, key=lambda ref: _local_ref_sort_key(ref, facts)))
        for _layer, items in sorted(layers.items())
    )


def _layout_columns(
    columns: Sequence[Sequence[CanonicalNodeRef]],
    sizes: Mapping[CanonicalNodeRef, tuple[int, int]],
    gap_x: int,
    gap_y: int,
) -> dict[CanonicalNodeRef, tuple[int, int]]:
    offsets: dict[CanonicalNodeRef, tuple[int, int]] = {}
    x = 0
    for column in columns:
        refs = tuple(column)
        if not refs:
            continue
        y = 0
        column_width = max(sizes[ref][0] for ref in refs)
        for ref in refs:
            offsets[ref] = (x, y)
            y += sizes[ref][1] + gap_y
        x += column_width + gap_x
    return offsets


def _layout_grid(
    refs: Sequence[CanonicalNodeRef],
    sizes: Mapping[CanonicalNodeRef, tuple[int, int]],
    gap_x: int,
    gap_y: int,
) -> dict[CanonicalNodeRef, tuple[int, int]]:
    if not refs:
        return {}
    columns = 1
    while columns * columns < len(refs):
        columns += 1
    rows = (len(refs) + columns - 1) // columns
    column_widths = [
        max((sizes[refs[row * columns + column]][0] for row in range(rows) if row * columns + column < len(refs)), default=0)
        for column in range(columns)
    ]
    row_heights = [
        max((sizes[refs[row * columns + column]][1] for column in range(columns) if row * columns + column < len(refs)), default=0)
        for row in range(rows)
    ]
    column_x = [sum(column_widths[:column]) + column * gap_x for column in range(columns)]
    row_y = [sum(row_heights[:row]) + row * gap_y for row in range(rows)]
    return {
        ref: (column_x[index % columns], row_y[index // columns])
        for index, ref in enumerate(refs)
    }


def _local_bounds(
    offsets: Mapping[CanonicalNodeRef, tuple[int, int]],
    sizes: Mapping[CanonicalNodeRef, tuple[int, int]],
) -> tuple[int, int]:
    if not offsets:
        return (0, 0)
    width = max(x + sizes[ref][0] for ref, (x, _y) in offsets.items())
    height = max(y + sizes[ref][1] for ref, (_x, y) in offsets.items())
    return (width, height)


def _local_ref_sort_key(ref: CanonicalNodeRef, facts: GraphInventoryFacts) -> tuple[Any, ...]:
    topology_by_ref = {
        node.ref: node
        for topology in facts.scope_topologies
        for node in topology.node_topology
    }
    topology = topology_by_ref.get(ref)
    if topology is None:
        return (0, 0, 0, *_ref_sort_key(ref))
    return (
        getattr(topology, "topological_rank", 0),
        getattr(topology, "lane_band", 0),
        getattr(topology, "lane_index", 0),
        *_ref_sort_key(ref),
    )


def _effective_pinned_refs(
    facts: GraphInventoryFacts,
    options: LayoutCompileOptions,
    classification: ClassificationReport,
) -> set[CanonicalNodeRef]:
    if _force_existing_regroup(options):
        return set()
    pinned_refs = set(options.pinned_refs)
    for furniture in facts.node_furniture:
        if _truthy_flag(furniture.flags, "pinned") or _truthy_flag(furniture.sidecar_entry, "pinned"):
            pinned_refs.add(furniture.ref)
    return pinned_refs


def _truthy_flag(value: Any, key: str) -> bool:
    if not isinstance(value, Mapping):
        return False
    item = value.get(key)
    return isinstance(item, bool) and item


def _force_existing_regroup(options: LayoutCompileOptions) -> bool:
    return options.force_regroup or options.existing_group_policy == "force_regroup"


def _apply_existing_group_policy(
    group_layouts: Sequence[CompiledGroupLayout],
    facts: GraphInventoryFacts,
    options: LayoutCompileOptions,
    classification: ClassificationReport,
) -> tuple[tuple[CompiledGroupLayout, ...], tuple[AssessmentIssue, ...]]:
    policy: ExistingGroupPolicy = "force_regroup" if _force_existing_regroup(options) else options.existing_group_policy
    baseline = tuple(group_layouts)
    baseline_by_id = {group.id: group for group in baseline}
    baseline_by_nodes: dict[tuple[str, tuple[CanonicalNodeRef, ...]], CompiledGroupLayout] = {}
    for group in baseline:
        if group.node_refs:
            baseline_by_nodes.setdefault(
                (group.scope_path, tuple(sorted(group.node_refs, key=_ref_sort_key))),
                group,
            )

    groups_by_id = dict(baseline_by_id)
    issues: list[AssessmentIssue] = []
    for group, score in _scored_existing_groups(facts, classification):
        match = _matching_compiled_group(group, score, baseline_by_id, baseline_by_nodes)
        if not score.coherent:
            if policy == "semantic_preserve":
                continue
            action = "dissolved" if policy == "dissolve_with_warning" or match is None else "rebuilt"
            issues.append(_existing_group_policy_issue(group, score, policy=policy, action=action))
            continue
        if policy in {"dissolve_with_warning", "force_regroup"}:
            continue
        replacement = _policy_group_layout(group, score, match, policy)
        groups_by_id[replacement.id] = replacement

    return (
        tuple(sorted(groups_by_id.values(), key=lambda layout: (-_scope_depth(layout.scope_path), layout.scope_path, layout.id))),
        tuple(issues),
    )


def _existing_group_scores(
    facts: GraphInventoryFacts,
    classification: ClassificationReport,
) -> tuple[_ExistingGroupScore, ...]:
    return tuple(score for _group, score in _scored_existing_groups(facts, classification))


def _scored_existing_groups(
    facts: GraphInventoryFacts,
    classification: ClassificationReport,
) -> tuple[tuple[GroupFact, _ExistingGroupScore], ...]:
    scored: list[tuple[GroupFact, _ExistingGroupScore]] = []
    for scope in sorted(facts.scope_furniture, key=lambda item: item.scope_path):
        for group in sorted(scope.groups, key=lambda item: item.index):
            score = _score_existing_group(facts, group, classification)
            if score is not None:
                scored.append((group, score))
    return tuple(scored)


def _matching_compiled_group(
    group: GroupFact,
    score: _ExistingGroupScore,
    baseline_by_id: Mapping[str, CompiledGroupLayout],
    baseline_by_nodes: Mapping[tuple[str, tuple[CanonicalNodeRef, ...]], CompiledGroupLayout],
) -> CompiledGroupLayout | None:
    existing_id = _existing_group_section_id(group.scope_path, group.index)
    match = baseline_by_id.get(existing_id)
    if match is not None:
        return match
    return baseline_by_nodes.get((group.scope_path, tuple(sorted(score.member_refs, key=_ref_sort_key))))


def _policy_group_layout(
    group: GroupFact,
    score: _ExistingGroupScore,
    baseline: CompiledGroupLayout | None,
    policy: ExistingGroupPolicy,
) -> CompiledGroupLayout:
    existing_rect = _group_rect(group.bounding)
    if policy in {"resize_only", "rename_and_resize"} and baseline is not None:
        x, y, width, height = baseline.x, baseline.y, baseline.width, baseline.height
    elif existing_rect is not None:
        x, y = snap_pos((existing_rect.x, existing_rect.y))
        width, height = snap_size((existing_rect.width, existing_rect.height))
    elif baseline is not None:
        x, y, width, height = baseline.x, baseline.y, baseline.width, baseline.height
    else:
        x, y, width, height = 0, 0, DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT + DEFAULT_GROUP_HEADER_HEIGHT

    use_semantic_title = policy in {"rename_only", "rename_and_resize"}
    title = (
        baseline.title
        if use_semantic_title and baseline is not None
        else group.title
        if isinstance(group.title, str) and group.title
        else baseline.title
        if baseline is not None
        else _title_for(_existing_group_section_id(group.scope_path, group.index), score.section_kind)
    )
    kind = baseline.kind if baseline is not None else score.section_kind
    return CompiledGroupLayout(
        id=baseline.id if baseline is not None else _existing_group_section_id(group.scope_path, group.index),
        scope_path=group.scope_path,
        title=title,
        kind=kind,
        role_hint=baseline.role_hint if baseline is not None else None,
        node_refs=score.member_refs,
        x=x,
        y=y,
        width=max(1, width),
        height=max(1, height),
        color=group.color if isinstance(group.color, str) and group.color else baseline.color if baseline is not None else _ROLE_COLORS.get(kind, _ROLE_COLORS[SECTION_KIND_CUSTOM]),
        template=baseline.template if baseline is not None else None,
    )


def _existing_group_policy_issue(
    group: GroupFact,
    score: _ExistingGroupScore,
    *,
    policy: ExistingGroupPolicy,
    action: Literal["dissolved", "rebuilt"],
) -> AssessmentIssue:
    code = (
        COMPILE_ISSUE_EXISTING_GROUP_REBUILT
        if action == "rebuilt"
        else COMPILE_ISSUE_EXISTING_GROUP_DISSOLVED
    )
    title = group.title if isinstance(group.title, str) and group.title else f"group {group.index}"
    return AssessmentIssue(
        code=code,
        message=f"Existing group {title!r} was {action} because it is incoherent.",
        severity="warning",
        refs=score.member_refs,
        detail={
            "scope_path": group.scope_path,
            "group_index": group.index,
            "title": group.title,
            "policy": policy,
            "action": action,
            "score": round(score.score, 4),
            "containment": round(score.containment, 4),
            "topology": round(score.topology, 4),
            "title_role": round(score.title_role, 4),
            "node_coverage": round(score.node_coverage, 4),
        },
    )


def _candidate_patch(
    node_layouts: Sequence[CompiledNodeLayout],
    group_layouts: Sequence[CompiledGroupLayout],
    facts: GraphInventoryFacts,
    options: LayoutCompileOptions,
) -> LayoutCandidatePatch:
    furniture_by_ref = {fact.ref: fact for fact in facts.node_furniture}
    entries: dict[str, Mapping[str, Any]] = {}
    for layout in sorted(node_layouts, key=lambda item: _entry_key(item.ref)):
        furniture = furniture_by_ref.get(layout.ref)
        entries[_entry_key(layout.ref)] = _entry_for_layout(layout, furniture)

    groups = tuple(_sidecar_group(group) for group in sorted(group_layouts, key=lambda item: (item.scope_path, item.id)))
    sidecar = facts.sidecar_envelope
    root_scope = next((scope for scope in facts.scope_furniture if scope.scope_path == ""), None)
    extra = sidecar.get("extra") if isinstance(sidecar.get("extra"), Mapping) else None
    if extra is None and root_scope is not None:
        extra = root_scope.extra
    last_reroute_id = sidecar.get("lastRerouteId")
    if last_reroute_id is None and root_scope is not None:
        last_reroute_id = root_scope.last_reroute_id
    return LayoutCandidatePatch(
        entries=entries,
        groups=groups,
        extra=extra or {},
        last_reroute_id=last_reroute_id,
        definitions=sidecar.get("definitions") if isinstance(sidecar.get("definitions"), Mapping) else {},
        virtual_wires=_candidate_virtual_wires(facts),
        store_version=STORE_VERSION,
        vibecomfy_version=str(sidecar.get("vibecomfy_version", "0")),
        schema_hash=_candidate_schema_hash(),
        unkeyed=_candidate_unkeyed(sidecar),
    )


def _candidate_virtual_wires(facts: GraphInventoryFacts) -> Mapping[str, Any]:
    sidecar = facts.sidecar_envelope
    if isinstance(sidecar.get("virtual_wires"), Mapping):
        return sidecar["virtual_wires"]
    return {
        wire.key: _thaw_jsonish(wire.payload)
        for wire in sorted(facts.virtual_wires, key=lambda item: (item.source, item.key))
    }


def _candidate_unkeyed(sidecar: Mapping[str, Any]) -> tuple[Any, ...]:
    unkeyed = sidecar.get("unkeyed", ())
    if isinstance(unkeyed, Sequence) and not isinstance(unkeyed, (str, bytes)):
        return tuple(unkeyed)
    return ()


def _build_report(
    *,
    node_layouts: Sequence[CompiledNodeLayout],
    group_layouts: Sequence[CompiledGroupLayout],
    facts: GraphInventoryFacts,
    candidate_patch: LayoutCandidatePatch,
    structural_hash_before: str,
    structural_hash_after: str,
    diagnostics: Sequence[Any],
    issues: Sequence[AssessmentIssue] = (),
) -> Any:
    helper_count = sum(
        1
        for layout in node_layouts
        if layout.role_hint in {ROLE_HINT_HELPER, ROLE_HINT_UI}
    )
    gate_metrics, gate_issues = _compile_gate_metrics_and_issues(
        node_layouts=node_layouts,
        group_layouts=group_layouts,
        facts=facts,
        candidate_patch=candidate_patch,
        structural_hash_before=structural_hash_before,
        structural_hash_after=structural_hash_after,
    )
    metrics = (
        AssessmentMetric(name=COMPILE_METRIC_NODE_LAYOUT_COUNT, value=len(node_layouts)),
        AssessmentMetric(name=COMPILE_METRIC_GROUP_LAYOUT_COUNT, value=len(group_layouts)),
        AssessmentMetric(name=COMPILE_METRIC_HELPER_LAYOUT_COUNT, value=helper_count),
        *gate_metrics,
        AssessmentMetric(
            name=COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED,
            value=structural_hash_before == structural_hash_after,
        ),
    )
    return build_assessment_report(
        metrics=metrics,
        issues=(*tuple(issues), *gate_issues),
        diagnostics=diagnostics,
        metric_order=COMPILE_METRIC_ORDER,
        issue_order=COMPILE_ISSUE_ORDER,
    )


def _compile_gate_metrics_and_issues(
    *,
    node_layouts: Sequence[CompiledNodeLayout],
    group_layouts: Sequence[CompiledGroupLayout],
    facts: GraphInventoryFacts,
    candidate_patch: LayoutCandidatePatch,
    structural_hash_before: str,
    structural_hash_after: str,
) -> tuple[tuple[AssessmentMetric, ...], tuple[AssessmentIssue, ...]]:
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    node_rects = _node_rects(node_layouts)
    primary_rects = {
        ref: rect
        for ref, rect in node_rects.items()
        if ref not in helper_refs
    }
    group_rects = _group_metric_rects(group_layouts, node_rects)
    node_overlaps = _rect_overlap_pairs(primary_rects)
    group_overlaps = _unintended_group_overlap_pairs(group_rects)
    backward_count, measured_edges = _compiled_backward_edge_counts(facts, node_rects)
    backward_ratio = _ratio_float(backward_count, measured_edges)
    crossings = _compiled_crossing_proxy_pairs(facts, node_rects)
    minimum_gutter, gutter_violations = _compiled_minimum_gutter(primary_rects, group_rects)
    helper_distance_max, helper_distance_violations = _compiled_helper_distance_violations(facts, node_rects, helper_refs)
    idempotence_delta, idempotence_detail = _compiled_idempotence_delta(facts, candidate_patch)

    metrics = (
        AssessmentMetric(
            name=COMPILE_METRIC_NODE_OVERLAP_COUNT,
            value=len(node_overlaps),
            threshold=0,
        ),
        AssessmentMetric(
            name=COMPILE_METRIC_GROUP_OVERLAP_COUNT,
            value=len(group_overlaps),
            threshold=0,
        ),
        AssessmentMetric(
            name=COMPILE_METRIC_BACKWARD_EDGE_RATIO,
            value=round(backward_ratio, 4),
            threshold=COMPILE_BACKWARD_EDGE_RATIO_THRESHOLD,
        ),
        AssessmentMetric(
            name=COMPILE_METRIC_CROSSING_PROXY_COUNT,
            value=len(crossings),
            threshold=COMPILE_CROSSING_PROXY_THRESHOLD,
        ),
        AssessmentMetric(
            name=COMPILE_METRIC_MINIMUM_GUTTER,
            value=round(minimum_gutter, 2),
            threshold=MIN_NODE_GUTTER,
        ),
        AssessmentMetric(
            name=COMPILE_METRIC_HELPER_DISTANCE_MAX,
            value=round(helper_distance_max, 2),
            threshold=COMPILE_HELPER_DISTANCE_THRESHOLD,
        ),
        AssessmentMetric(
            name=COMPILE_METRIC_IDEMPOTENCE_DELTA,
            value=round(idempotence_delta, 2),
            threshold=COMPILE_IDEMPOTENCE_DELTA_THRESHOLD,
        ),
    )

    issues: list[AssessmentIssue] = []
    if node_overlaps:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_NODE_OVERLAP,
                message="Compiled primary node boxes overlap.",
                severity="error",
                refs=tuple(ref for left, right in node_overlaps for ref in (left.ref, right.ref) if ref is not None),
                detail={
                    "count": len(node_overlaps),
                    "pairs": [
                        [_rect_ref_json(left), _rect_ref_json(right)]
                        for left, right in node_overlaps
                    ],
                },
            )
        )
    if group_overlaps:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_GROUP_OVERLAP,
                message="Compiled group boxes overlap without containment.",
                severity="error",
                refs=tuple(
                    ref
                    for left, right in group_overlaps
                    for group in (left.group, right.group)
                    if group is not None
                    for ref in group.node_refs
                ),
                detail={
                    "count": len(group_overlaps),
                    "pairs": [
                        [_rect_group_json(left), _rect_group_json(right)]
                        for left, right in group_overlaps
                    ],
                },
            )
        )
    if backward_ratio > COMPILE_BACKWARD_EDGE_RATIO_THRESHOLD:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_BACKWARD_EDGE_RATIO_HIGH,
                message="Compiled edge direction frequently moves backward on the x axis.",
                severity="error",
                detail={
                    "backward_edges": backward_count,
                    "measured_edges": measured_edges,
                    "ratio": round(backward_ratio, 4),
                    "threshold": COMPILE_BACKWARD_EDGE_RATIO_THRESHOLD,
                },
            )
        )
    if len(crossings) > COMPILE_CROSSING_PROXY_THRESHOLD:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_CROSSING_PROXY_HIGH,
                message="Compiled edge crossing proxy exceeded the threshold.",
                severity="error",
                refs=tuple(ref for pair in crossings for edge in pair for ref in (edge.source, edge.target)),
                detail={
                    "count": len(crossings),
                    "threshold": COMPILE_CROSSING_PROXY_THRESHOLD,
                    "edge_pairs": [
                        [_edge_ref_json(left), _edge_ref_json(right)]
                        for left, right in crossings
                    ],
                },
            )
        )
    if gutter_violations:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_MINIMUM_GUTTER,
                message="Compiled layout violates minimum node or group gutters.",
                severity="error",
                refs=tuple(
                    ref
                    for violation in gutter_violations
                    for ref in violation.get("refs", ())
                    if isinstance(ref, CanonicalNodeRef)
                ),
                detail={
                    "minimum_gutter": round(minimum_gutter, 2),
                    "threshold": MIN_NODE_GUTTER,
                    "violations": [_gutter_violation_json(violation) for violation in gutter_violations],
                },
            )
        )
    if helper_distance_violations:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_HELPER_DISTANCE_HIGH,
                message="Compiled helper node is too far from its connected layout context.",
                severity="error",
                refs=tuple(violation["helper_ref"] for violation in helper_distance_violations),
                detail={
                    "max_distance": round(helper_distance_max, 2),
                    "threshold": COMPILE_HELPER_DISTANCE_THRESHOLD,
                    "violations": [_helper_distance_violation_json(violation) for violation in helper_distance_violations],
                },
            )
        )
    if idempotence_delta > COMPILE_IDEMPOTENCE_DELTA_THRESHOLD:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_IDEMPOTENCE_DELTA,
                message="Compiler-owned layout sidecar changed on recompilation.",
                severity="error",
                detail={
                    **idempotence_detail,
                    "delta": round(idempotence_delta, 2),
                    "threshold": COMPILE_IDEMPOTENCE_DELTA_THRESHOLD,
                },
            )
        )
    if structural_hash_before != structural_hash_after:
        issues.append(
            AssessmentIssue(
                code=COMPILE_ISSUE_STRUCTURAL_HASH_CHANGED,
                message="Compiler changed the runtime structural hash.",
                severity="error",
                detail={
                    "before": structural_hash_before,
                    "after": structural_hash_after,
                },
            )
        )
    return metrics, tuple(issues)


def _node_rects(node_layouts: Sequence[CompiledNodeLayout]) -> dict[CanonicalNodeRef, _CompileRect]:
    return {
        layout.ref: _CompileRect(
            key=json.dumps(layout.ref.to_json(), ensure_ascii=True),
            ref=layout.ref,
            x=layout.x,
            y=layout.y,
            width=layout.width,
            height=layout.height,
        )
        for layout in node_layouts
    }


def _group_rects(group_layouts: Sequence[CompiledGroupLayout]) -> dict[str, _CompileRect]:
    return {
        group.id: _CompileRect(
            key=group.id,
            group=group,
            x=group.x,
            y=group.y,
            width=group.width,
            height=group.height,
        )
        for group in group_layouts
    }


def _group_metric_rects(
    group_layouts: Sequence[CompiledGroupLayout],
    node_rects: Mapping[CanonicalNodeRef, _CompileRect],
) -> dict[str, _CompileRect]:
    rects: dict[str, _CompileRect] = {}
    for group in group_layouts:
        primary_rects = tuple(node_rects[ref] for ref in group.node_refs if ref in node_rects)
        if not primary_rects:
            rects[group.id] = _CompileRect(
                key=group.id,
                group=group,
                x=group.x,
                y=group.y,
                width=group.width,
                height=group.height,
            )
            continue
        left = min(rect.x for rect in primary_rects)
        top = min(rect.y for rect in primary_rects)
        right = max(rect.right for rect in primary_rects)
        bottom = max(rect.bottom for rect in primary_rects)
        rects[group.id] = _CompileRect(
            key=group.id,
            group=group,
            x=left,
            y=top,
            width=right - left,
            height=bottom - top,
        )
    return rects


def _rect_overlap_pairs(
    rects: Mapping[Any, _CompileRect],
) -> tuple[tuple[_CompileRect, _CompileRect], ...]:
    ordered = sorted(rects.values(), key=lambda rect: rect.key)
    pairs: list[tuple[_CompileRect, _CompileRect]] = []
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            if _rects_overlap(left, right):
                pairs.append((left, right))
    return tuple(pairs)


def _unintended_group_overlap_pairs(
    rects: Mapping[str, _CompileRect],
) -> tuple[tuple[_CompileRect, _CompileRect], ...]:
    pairs: list[tuple[_CompileRect, _CompileRect]] = []
    for left, right in _rect_overlap_pairs(rects):
        if _rect_contains(left, right) or _rect_contains(right, left):
            continue
        pairs.append((left, right))
    return tuple(pairs)


def _rects_overlap(left: _CompileRect, right: _CompileRect) -> bool:
    return (
        left.x < right.right
        and left.right > right.x
        and left.y < right.bottom
        and left.bottom > right.y
    )


def _rect_contains(container: _CompileRect, child: _CompileRect) -> bool:
    return (
        child.x >= container.x
        and child.y >= container.y
        and child.right <= container.right
        and child.bottom <= container.bottom
    )


def _rect_gap(left: _CompileRect, right: _CompileRect) -> float:
    dx = max(left.x - right.right, right.x - left.right, 0.0)
    dy = max(left.y - right.bottom, right.y - left.bottom, 0.0)
    return hypot(dx, dy)


def _compiled_backward_edge_counts(
    facts: GraphInventoryFacts,
    rects: Mapping[CanonicalNodeRef, _CompileRect],
) -> tuple[int, int]:
    backward = 0
    measured = 0
    for edge in _compiled_effective_edges(facts):
        source = rects.get(edge.source)
        target = rects.get(edge.target)
        if source is None or target is None:
            continue
        measured += 1
        if target.center[0] < source.center[0] - COMPILE_BACKWARD_EDGE_X_TOLERANCE:
            backward += 1
    return backward, measured


def _compiled_crossing_proxy_pairs(
    facts: GraphInventoryFacts,
    rects: Mapping[CanonicalNodeRef, _CompileRect],
) -> tuple[tuple[Any, Any], ...]:
    edges = [
        edge
        for edge in _compiled_effective_edges(facts)
        if edge.source in rects and edge.target in rects and edge.source != edge.target
    ]
    pairs: list[tuple[Any, Any]] = []
    for index, left in enumerate(edges):
        left_refs = {left.source, left.target}
        for right in edges[index + 1:]:
            if left_refs & {right.source, right.target}:
                continue
            if _segments_cross(
                rects[left.source].center,
                rects[left.target].center,
                rects[right.source].center,
                rects[right.target].center,
            ):
                pairs.append((left, right))
    return tuple(sorted(pairs, key=lambda pair: (_edge_sort_key(pair[0]), _edge_sort_key(pair[1]))))


def _segments_cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    def orientation(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    first = orientation(a, b, c)
    second = orientation(a, b, d)
    third = orientation(c, d, a)
    fourth = orientation(c, d, b)
    return (
        (first > 0 and second < 0 or first < 0 and second > 0)
        and (third > 0 and fourth < 0 or third < 0 and fourth > 0)
    )


def _compiled_minimum_gutter(
    primary_rects: Mapping[CanonicalNodeRef, _CompileRect],
    group_rects: Mapping[str, _CompileRect],
) -> tuple[float, tuple[dict[str, Any], ...]]:
    minimum = float(MIN_NODE_GUTTER)
    measured = False
    violations: list[dict[str, Any]] = []

    for left, right in _rect_pairs(primary_rects.values()):
        gap = _rect_gap(left, right)
        minimum = min(minimum, gap)
        measured = True
        if gap < MIN_NODE_GUTTER:
            violations.append(
                {
                    "kind": "node",
                    "gap": gap,
                    "threshold": MIN_NODE_GUTTER,
                    "left": left,
                    "right": right,
                    "refs": tuple(ref for ref in (left.ref, right.ref) if ref is not None),
                }
            )
    for left, right in _rect_pairs(group_rects.values()):
        if _rect_contains(left, right) or _rect_contains(right, left):
            continue
        gap = _rect_gap(left, right)
        minimum = min(minimum, gap)
        measured = True
        if gap < MIN_GROUP_GUTTER:
            violations.append(
                {
                    "kind": "group",
                    "gap": gap,
                    "threshold": MIN_GROUP_GUTTER,
                    "left": left,
                    "right": right,
                    "refs": tuple(
                        ref
                        for group in (left.group, right.group)
                        if group is not None
                        for ref in group.node_refs
                    ),
                }
            )
    return (minimum if measured else float(MIN_NODE_GUTTER)), tuple(
        sorted(violations, key=lambda item: (str(item["kind"]), float(item["gap"]), item["left"].key, item["right"].key))
    )


def _rect_pairs(rects: Sequence[_CompileRect] | Any) -> tuple[tuple[_CompileRect, _CompileRect], ...]:
    ordered = sorted(tuple(rects), key=lambda rect: rect.key)
    pairs: list[tuple[_CompileRect, _CompileRect]] = []
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            pairs.append((left, right))
    return tuple(pairs)


def _compiled_helper_distance_violations(
    facts: GraphInventoryFacts,
    rects: Mapping[CanonicalNodeRef, _CompileRect],
    helper_refs: set[CanonicalNodeRef],
) -> tuple[float, tuple[dict[str, Any], ...]]:
    max_distance = 0.0
    violations: list[dict[str, Any]] = []
    for helper_ref in sorted(helper_refs, key=_ref_sort_key):
        helper_rect = rects.get(helper_ref)
        if helper_rect is None:
            continue
        neighbor_refs = _compiled_helper_neighbor_refs(helper_ref, facts, helper_refs)
        neighbor_rects = [rects[ref] for ref in neighbor_refs if ref in rects]
        if not neighbor_rects:
            continue
        distance = min(hypot(helper_rect.center[0] - rect.center[0], helper_rect.center[1] - rect.center[1]) for rect in neighbor_rects)
        max_distance = max(max_distance, distance)
        if distance > COMPILE_HELPER_DISTANCE_THRESHOLD:
            violations.append(
                {
                    "helper_ref": helper_ref,
                    "distance": distance,
                    "neighbor_refs": tuple(rect.ref for rect in neighbor_rects if rect.ref is not None),
                }
            )
    return max_distance, tuple(violations)


def _compiled_helper_neighbor_refs(
    helper_ref: CanonicalNodeRef,
    facts: GraphInventoryFacts,
    helper_refs: set[CanonicalNodeRef],
) -> tuple[CanonicalNodeRef, ...]:
    refs: set[CanonicalNodeRef] = set()
    for topology in facts.scope_topologies:
        for edge in topology.raw_edges:
            if edge.source == helper_ref and edge.target not in helper_refs:
                refs.add(edge.target)
            if edge.target == helper_ref and edge.source not in helper_refs:
                refs.add(edge.source)
    return tuple(sorted(refs, key=_ref_sort_key))


def _compiled_idempotence_delta(
    facts: GraphInventoryFacts,
    candidate_patch: LayoutCandidatePatch,
) -> tuple[float, dict[str, Any]]:
    sidecar = facts.sidecar_envelope
    if sidecar.get("schema_hash") != _candidate_schema_hash() or sidecar.get("reorganise_compiler") is not True:
        return 0.0, {"measured": False, "reason": "input sidecar was not marked compiler-owned"}
    patch = candidate_patch.to_json()
    max_delta = 0.0
    changed: list[dict[str, Any]] = []
    for key, compiled in sorted(patch.get("entries", {}).items()):
        current = sidecar.get("entries", {}).get(key) if isinstance(sidecar.get("entries"), Mapping) else None
        delta = _entry_layout_delta(current, compiled)
        if delta > 0:
            changed.append({"kind": "entry", "key": key, "delta": round(delta, 2)})
        max_delta = max(max_delta, delta)
    current_groups = sidecar.get("groups") if isinstance(sidecar.get("groups"), Sequence) and not isinstance(sidecar.get("groups"), (str, bytes)) else ()
    current_groups_by_key = {
        _candidate_group_match_key(group): group
        for group in current_groups
        if isinstance(group, Mapping)
    }
    for group in patch.get("groups", ()):
        if not isinstance(group, Mapping):
            continue
        group_key = _candidate_group_match_key(group)
        delta = _group_layout_delta(current_groups_by_key.get(group_key), group)
        if delta > 0:
            changed.append({"kind": "group", "key": group_key, "delta": round(delta, 2)})
        max_delta = max(max_delta, delta)
    return max_delta, {"measured": True, "changed": changed[:8], "changed_count": len(changed)}


def _candidate_group_match_key(group: Mapping[str, Any]) -> str:
    if group.get("id") is not None:
        return f"id:{group.get('id')}"
    nodes = group.get("nodes") if isinstance(group.get("nodes"), Sequence) and not isinstance(group.get("nodes"), (str, bytes)) else ()
    return json.dumps(
        {
            "title": group.get("title"),
            "nodes": list(nodes),
        },
        sort_keys=True,
        ensure_ascii=True,
    )


def _entry_layout_delta(current: Any, compiled: Any) -> float:
    if not isinstance(current, Mapping) or not isinstance(compiled, Mapping):
        return float(COMPILE_IDEMPOTENCE_DELTA_THRESHOLD + 1)
    return max(
        _sequence_delta(current.get("pos"), compiled.get("pos")),
        _sequence_delta(current.get("size"), compiled.get("size")),
    )


def _group_layout_delta(current: Any, compiled: Any) -> float:
    if not isinstance(current, Mapping) or not isinstance(compiled, Mapping):
        return float(COMPILE_IDEMPOTENCE_DELTA_THRESHOLD + 1)
    return _sequence_delta(current.get("bounding"), compiled.get("bounding"))


def _sequence_delta(left: Any, right: Any) -> float:
    if not isinstance(left, Sequence) or isinstance(left, (str, bytes)):
        return float(COMPILE_IDEMPOTENCE_DELTA_THRESHOLD + 1)
    if not isinstance(right, Sequence) or isinstance(right, (str, bytes)):
        return float(COMPILE_IDEMPOTENCE_DELTA_THRESHOLD + 1)
    if len(left) != len(right):
        return float(COMPILE_IDEMPOTENCE_DELTA_THRESHOLD + 1)
    deltas: list[float] = []
    for left_item, right_item in zip(left, right):
        left_number = _number_float(left_item)
        right_number = _number_float(right_item)
        if left_number is None or right_number is None:
            return float(COMPILE_IDEMPOTENCE_DELTA_THRESHOLD + 1)
        deltas.append(abs(left_number - right_number))
    return max(deltas, default=0.0)


def _compiled_effective_edges(facts: GraphInventoryFacts) -> tuple[Any, ...]:
    edges = [
        edge
        for topology in facts.scope_topologies
        for edge in topology.effective_edges
    ]
    return tuple(sorted(edges, key=_edge_sort_key))


def _edge_sort_key(edge: Any) -> tuple[Any, ...]:
    return (
        getattr(edge, "scope_path", ""),
        *_ref_sort_key(edge.source),
        *_ref_sort_key(edge.target),
        str(getattr(edge, "source_slot", "")),
        str(getattr(edge, "target_slot", "")),
        str(getattr(edge, "link_id", "")),
    )


def _rect_ref_json(rect: _CompileRect) -> Any:
    return rect.ref.to_json() if rect.ref is not None else rect.key


def _rect_group_json(rect: _CompileRect) -> dict[str, Any]:
    group = rect.group
    if group is None:
        return {"id": rect.key}
    return {
        "id": group.id,
        "title": group.title,
        "scope_path": group.scope_path,
        "bounding": [group.x, group.y, group.width, group.height],
    }


def _edge_ref_json(edge: Any) -> dict[str, Any]:
    return {
        "source": edge.source.to_json(),
        "target": edge.target.to_json(),
        "scope_path": getattr(edge, "scope_path", ""),
    }


def _gutter_violation_json(violation: Mapping[str, Any]) -> dict[str, Any]:
    left = violation["left"]
    right = violation["right"]
    return {
        "kind": violation["kind"],
        "gap": round(float(violation["gap"]), 2),
        "threshold": violation["threshold"],
        "left": _rect_ref_json(left) if left.ref is not None else _rect_group_json(left),
        "right": _rect_ref_json(right) if right.ref is not None else _rect_group_json(right),
    }


def _helper_distance_violation_json(violation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "helper_ref": violation["helper_ref"].to_json(),
        "distance": round(float(violation["distance"]), 2),
        "threshold": COMPILE_HELPER_DISTANCE_THRESHOLD,
        "neighbor_refs": [ref.to_json() for ref in violation["neighbor_refs"]],
    }


def _apply_floating_helper_positions(
    plan: LayoutPlanV1,
    node_layouts: Sequence[CompiledNodeLayout],
    spacing: _Spacing,
) -> tuple[CompiledNodeLayout, ...]:
    layout_by_ref = {layout.ref: layout for layout in node_layouts}
    placement_by_helper = {
        placement.helper: placement
        for placement in plan.helper_placements
    }
    adjusted: list[CompiledNodeLayout] = []
    for layout in node_layouts:
        if layout.section_id != "__helpers__":
            adjusted.append(layout)
            continue
        placement = placement_by_helper.get(layout.ref)
        if placement is None:
            adjusted.append(layout)
            continue
        pos = _floating_helper_pos(placement, layout, layout_by_ref, spacing)
        if pos is None:
            adjusted.append(layout)
            continue
        adjusted.append(
            CompiledNodeLayout(
                ref=layout.ref,
                section_id=layout.section_id,
                role_hint=layout.role_hint,
                x=pos[0],
                y=pos[1],
                width=layout.width,
                height=layout.height,
                pinned=layout.pinned,
            )
        )
    return tuple(adjusted)


def _floating_helper_pos(
    placement: Any,
    helper: CompiledNodeLayout,
    layout_by_ref: Mapping[CanonicalNodeRef, CompiledNodeLayout],
    spacing: _Spacing,
) -> tuple[int, int] | None:
    anchor_gap = max(24, spacing.node_gap_y // 2)
    if placement.kind == HELPER_PLACEMENT_EDGE_PATH:
        source = layout_by_ref.get(placement.source)
        destination = layout_by_ref.get(placement.destination)
        if source is None or destination is None:
            return None
        source_center = _layout_center(source)
        target_center = _layout_center(destination)
        return (
            round((source_center[0] + target_center[0] - helper.width) / 2),
            round((source_center[1] + target_center[1] - helper.height) / 2),
        )
    target = layout_by_ref.get(placement.target)
    if target is None:
        return None
    y = target.y + max(0, (target.height - helper.height) // 2)
    if placement.kind == HELPER_PLACEMENT_NEAR_PRODUCER:
        return (target.x + target.width + anchor_gap, y)
    if placement.kind == HELPER_PLACEMENT_NEAR_CONSUMER:
        return (target.x - helper.width - anchor_gap, y)
    return None


def _layout_center(layout: CompiledNodeLayout) -> tuple[float, float]:
    return (layout.x + layout.width / 2, layout.y + layout.height / 2)


def _resolve_node_collisions(
    node_layouts: Sequence[CompiledNodeLayout],
    facts: GraphInventoryFacts,
    spacing: _Spacing,
) -> tuple[CompiledNodeLayout, ...]:
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    rounded = tuple(_rounded_node_layout(layout) for layout in node_layouts)
    pinned = tuple(sorted((layout for layout in rounded if layout.pinned), key=_node_collision_sort_key))
    movable = tuple(sorted((layout for layout in rounded if not layout.pinned), key=_node_collision_sort_key))
    resolved: dict[CanonicalNodeRef, CompiledNodeLayout] = {layout.ref: layout for layout in pinned}
    obstacles = list(pinned)

    for layout in movable:
        if layout.ref in helper_refs:
            candidate = _nudge_layout_clear_of_obstacles(
                layout,
                obstacles,
                same_section_gutter=MIN_NODE_GUTTER,
                cross_section_gutter=MIN_NODE_GUTTER,
            )
        else:
            primary_obstacles = [obstacle for obstacle in obstacles if obstacle.ref not in helper_refs]
            candidate = _nudge_layout_clear_of_obstacles(
                layout,
                primary_obstacles,
                same_section_gutter=MIN_NODE_GUTTER,
                cross_section_gutter=_cross_section_node_gutter(spacing),
            )
        resolved[candidate.ref] = candidate
        obstacles.append(candidate)

    return tuple(resolved[layout.ref] for layout in rounded)


def _rounded_node_layout(layout: CompiledNodeLayout) -> CompiledNodeLayout:
    x, y = snap_pos((layout.x, layout.y))
    width, height = snap_size((layout.width, layout.height))
    return CompiledNodeLayout(
        ref=layout.ref,
        section_id=layout.section_id,
        role_hint=layout.role_hint,
        x=x,
        y=y,
        width=max(1, width),
        height=max(1, height),
        pinned=layout.pinned,
    )


def _nudge_layout_clear_of_obstacles(
    layout: CompiledNodeLayout,
    obstacles: Sequence[CompiledNodeLayout],
    *,
    same_section_gutter: int,
    cross_section_gutter: int,
) -> CompiledNodeLayout:
    candidate = layout
    for _pass in range(len(obstacles) + 1):
        colliding = [
            obstacle
            for obstacle in obstacles
            if _layouts_violate_gutter(
                candidate,
                obstacle,
                same_section_gutter
                if candidate.section_id == obstacle.section_id
                else cross_section_gutter,
            )
        ]
        if not colliding:
            return candidate
        next_y = max(
            obstacle.y
            + obstacle.height
            + (
                same_section_gutter
                if candidate.section_id == obstacle.section_id
                else cross_section_gutter
            )
            for obstacle in colliding
        )
        if next_y <= candidate.y:
            next_y = candidate.y + same_section_gutter
        candidate = CompiledNodeLayout(
            ref=candidate.ref,
            section_id=candidate.section_id,
            role_hint=candidate.role_hint,
            x=candidate.x,
            y=next_y,
            width=candidate.width,
            height=candidate.height,
            pinned=candidate.pinned,
        )
    return candidate


def _layouts_violate_gutter(
    left: CompiledNodeLayout,
    right: CompiledNodeLayout,
    gutter: int,
) -> bool:
    return not (
        left.x + left.width + gutter <= right.x
        or right.x + right.width + gutter <= left.x
        or left.y + left.height + gutter <= right.y
        or right.y + right.height + gutter <= left.y
    )


def _cross_section_node_gutter(spacing: _Spacing) -> int:
    return max(
        MIN_NODE_GUTTER,
        MIN_GROUP_GUTTER + DEFAULT_GROUP_HEADER_HEIGHT + spacing.group_padding * 2,
    )


def _node_collision_sort_key(layout: CompiledNodeLayout) -> tuple[Any, ...]:
    return (
        0 if layout.pinned else 1,
        layout.y,
        layout.x,
        layout.section_id,
        *_ref_sort_key(layout.ref),
    )


def _compiled_group_layouts(
    sections: Sequence[_CompileSection],
    node_layouts: Sequence[CompiledNodeLayout],
    facts: GraphInventoryFacts,
    spacing: _Spacing,
) -> tuple[CompiledGroupLayout, ...]:
    layouts_by_section: dict[str, list[CompiledNodeLayout]] = {}
    for layout in node_layouts:
        layouts_by_section.setdefault(layout.section_id, []).append(layout)
    section_by_id = {section.id: section for section in sections}
    templates = {
        section.id: _local_section_layout(
            section,
            facts,
            {fact.ref: fact for fact in facts.node_furniture},
            LayoutCompileOptions(),
            spacing,
            None,
        ).template
        for section in sections
        if section.node_refs
    }
    groups_by_id: dict[str, CompiledGroupLayout] = {}
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    for section in sections:
        section_nodes = tuple(layouts_by_section.get(section.id, ()))
        if not section_nodes or section.id == "__helpers__":
            continue
        primary_nodes = tuple(layout for layout in section_nodes if layout.ref not in helper_refs)
        group_node_refs = (
            tuple(layout.ref for layout in primary_nodes)
            if primary_nodes
            else tuple(layout.ref for layout in section_nodes)
        )
        groups_by_id[section.id] = _group_for_section(
            section,
            section_nodes,
            spacing,
            templates.get(section.id, "single"),
            group_node_refs=group_node_refs,
        )

    plan_sections = {section.id: section for section in sections}
    pending = True
    while pending:
        pending = False
        for section in sorted(sections, key=lambda item: _section_depth(item, plan_sections), reverse=True):
            children = tuple(
                groups_by_id[child.id]
                for child in sections
                if child.id in groups_by_id and _plan_parent_id(child, plan_sections) == section.id
            )
            if not children:
                continue
            current = groups_by_id.get(section.id)
            if current is None:
                groups_by_id[section.id] = _group_for_container(section, children, spacing)
                pending = True
            else:
                expanded = _expand_group_for_children(current, children, spacing)
                if expanded != current:
                    groups_by_id[section.id] = expanded
                    pending = True

    return tuple(
        sorted(
            groups_by_id.values(),
            key=lambda layout: (-_scope_depth(layout.scope_path), layout.scope_path, layout.id),
        )
    )


def _group_for_section(
    section: _CompileSection,
    nodes: Sequence[CompiledNodeLayout],
    spacing: _Spacing,
    template: SectionTemplate,
    *,
    group_node_refs: Sequence[CanonicalNodeRef] | None = None,
) -> CompiledGroupLayout:
    left = min(node.x for node in nodes) - spacing.group_padding
    top = min(node.y for node in nodes) - spacing.group_padding - DEFAULT_GROUP_HEADER_HEIGHT
    right = max(node.x + node.width for node in nodes) + spacing.group_padding
    bottom = max(node.y + node.height for node in nodes) + spacing.group_padding
    scope_path = _common_scope(section.node_refs)
    return CompiledGroupLayout(
        id=section.id,
        scope_path=scope_path,
        title=section.title,
        kind=section.kind,
        role_hint=section.role_hint,
        node_refs=tuple(sorted(group_node_refs if group_node_refs is not None else section.node_refs, key=_ref_sort_key)),
        x=left,
        y=top,
        width=right - left,
        height=bottom - top,
        color=_ROLE_COLORS.get(section.kind, _ROLE_COLORS[SECTION_KIND_CUSTOM]),
        template=template,
    )


def _group_for_container(
    section: _CompileSection,
    children: Sequence[CompiledGroupLayout],
    spacing: _Spacing,
) -> CompiledGroupLayout:
    left = min(child.x for child in children) - spacing.group_padding
    top = min(child.y for child in children) - spacing.group_padding - DEFAULT_GROUP_HEADER_HEIGHT
    right = max(child.x + child.width for child in children) + spacing.group_padding
    bottom = max(child.y + child.height for child in children) + spacing.group_padding
    return CompiledGroupLayout(
        id=section.id,
        scope_path=_common_scope(section.node_refs) if section.node_refs else _common_group_scope(children),
        title=section.title,
        kind=section.kind,
        role_hint=section.role_hint,
        node_refs=(),
        x=left,
        y=top,
        width=right - left,
        height=bottom - top,
        color=_ROLE_COLORS.get(section.kind, _ROLE_COLORS[SECTION_KIND_CUSTOM]),
        template=None,
    )


def _expand_group_for_children(
    group: CompiledGroupLayout,
    children: Sequence[CompiledGroupLayout],
    spacing: _Spacing,
) -> CompiledGroupLayout:
    left = min([group.x, *(child.x - spacing.group_padding for child in children)])
    top = min([group.y, *(child.y - spacing.group_padding for child in children)])
    right = max([group.x + group.width, *(child.x + child.width + spacing.group_padding for child in children)])
    bottom = max([group.y + group.height, *(child.y + child.height + spacing.group_padding for child in children)])
    return CompiledGroupLayout(
        id=group.id,
        scope_path=group.scope_path,
        title=group.title,
        kind=group.kind,
        role_hint=group.role_hint,
        node_refs=group.node_refs,
        x=left,
        y=top,
        width=right - left,
        height=bottom - top,
        color=group.color,
        template=group.template,
    )


def _section_sccs(
    section_edges: Mapping[str, set[str]],
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    nodes = sorted(section_edges, key=_id_sort_key)
    raw_root_by_node = _tarjan(nodes, {node: tuple(sorted(section_edges.get(node, ()), key=_id_sort_key)) for node in nodes})
    roots = sorted(set(raw_root_by_node.values()), key=_id_sort_key)
    root_to_members = {
        root: tuple(node for node in nodes if raw_root_by_node[node] == root)
        for root in roots
    }
    ordered_roots = sorted(roots, key=lambda root: tuple(_id_sort_key(node) for node in root_to_members[root]))
    root_to_scc = {root: f"scc{index}" for index, root in enumerate(ordered_roots)}
    scc_by_section = {node: root_to_scc[root] for node, root in raw_root_by_node.items()}
    members_by_scc = {
        root_to_scc[root]: root_to_members[root]
        for root in ordered_roots
    }
    return scc_by_section, members_by_scc


def _tarjan(
    nodes: Sequence[str],
    adjacency: Mapping[str, Sequence[str]],
) -> dict[str, str]:
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    root_by_node: dict[str, str] = {}

    def strongconnect(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in adjacency.get(node, ()):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

        if lowlinks[node] != indices[node]:
            return
        members: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            members.append(member)
            if member == node:
                break
        root = sorted(members, key=_id_sort_key)[0]
        for member in members:
            root_by_node[member] = root

    for node in nodes:
        if node not in indices:
            strongconnect(node)
    return root_by_node


def _component_edges(
    section_edges: Mapping[str, set[str]],
    scc_by_section: Mapping[str, str],
) -> dict[str, set[str]]:
    component_edges = {scc: set() for scc in scc_by_section.values()}
    for source, targets in section_edges.items():
        source_scc = scc_by_section[source]
        for target in targets:
            target_scc = scc_by_section[target]
            if source_scc != target_scc:
                component_edges.setdefault(source_scc, set()).add(target_scc)
                component_edges.setdefault(target_scc, set())
    return component_edges


def _component_islands(
    component_edges: Mapping[str, set[str]],
    members_by_scc: Mapping[str, tuple[str, ...]],
    section_by_id: Mapping[str, _CompileSection],
) -> dict[str, int]:
    undirected = {component: set(targets) for component, targets in component_edges.items()}
    for source, targets in component_edges.items():
        for target in targets:
            undirected.setdefault(target, set()).add(source)
            undirected.setdefault(source, set())

    seen: set[str] = set()
    islands: list[tuple[tuple[Any, ...], tuple[str, ...]]] = []
    for component in sorted(undirected, key=_id_sort_key):
        if component in seen:
            continue
        pending = [component]
        members: set[str] = set()
        while pending:
            current = pending.pop(0)
            if current in members:
                continue
            members.add(current)
            pending.extend(sorted(undirected.get(current, ()), key=_id_sort_key))
        seen.update(members)
        key = min(
            _component_sort_key(item, members_by_scc, section_by_id)
            for item in members
        )
        islands.append((key, tuple(sorted(members, key=_id_sort_key))))
    island_by_component: dict[str, int] = {}
    for index, (_key, components) in enumerate(sorted(islands, key=lambda item: item[0])):
        for component in components:
            island_by_component[component] = index
    return island_by_component


def _component_ranks(
    component_edges: Mapping[str, set[str]],
    island_by_component: Mapping[str, int],
    members_by_scc: Mapping[str, tuple[str, ...]],
    section_by_id: Mapping[str, _CompileSection],
) -> dict[str, int]:
    incoming: dict[str, set[str]] = {component: set() for component in component_edges}
    for source, targets in component_edges.items():
        for target in targets:
            incoming.setdefault(target, set()).add(source)
    ranks: dict[str, int] = {}
    for island in sorted(set(island_by_component.values())):
        components = sorted(
            (component for component, item in island_by_component.items() if item == island),
            key=lambda component: _component_sort_key(component, members_by_scc, section_by_id),
        )
        pending = [component for component in components if not incoming.get(component)]
        if not pending:
            pending = list(components)
        while pending:
            current = pending.pop(0)
            if current in ranks:
                continue
            predecessors = incoming.get(current, set())
            if any(predecessor not in ranks for predecessor in predecessors if predecessor in components):
                pending.append(current)
                continue
            ranks[current] = (
                max((ranks[predecessor] + 1 for predecessor in predecessors if predecessor in ranks), default=0)
            )
            for target in sorted(component_edges.get(current, ()), key=lambda component: _component_sort_key(component, members_by_scc, section_by_id)):
                if target in components and target not in ranks and target not in pending:
                    pending.append(target)
    return ranks


def _component_sort_key(
    component: str,
    members_by_scc: Mapping[str, tuple[str, ...]],
    section_by_id: Mapping[str, _CompileSection],
) -> tuple[Any, ...]:
    members = members_by_scc.get(component, ())
    return min((_section_semantic_sort_key(section_by_id[section_id]) for section_id in members), default=(component,))


def _section_layout_sort_key(
    section: _CompileSection,
    topology_by_section: Mapping[str, CompiledSectionTopology],
) -> tuple[Any, ...]:
    topology = topology_by_section.get(section.id)
    if topology is None:
        return (*_section_semantic_sort_key(section), section.id)
    return (
        topology.scope_path,
        topology.island_index,
        topology.rank,
        topology.scc_id,
        *_section_semantic_sort_key(section),
    )


def _section_placement_sort_key(
    section: _CompileSection,
    placements: Mapping[str, _SectionPlacement],
    topology_by_section: Mapping[str, CompiledSectionTopology],
) -> tuple[Any, ...]:
    topology = _topology_for(section, topology_by_section)
    placement = placements[section.id]
    return (
        topology.scope_path,
        topology.island_index,
        placement.rank,
        placement.band,
        placement.row,
        *_section_semantic_sort_key(section),
    )


def _section_semantic_sort_key(section: _CompileSection) -> tuple[Any, ...]:
    node_ranks = tuple(_ref_sort_key(ref) for ref in section.node_refs)
    return (_common_scope(section.node_refs), section.kind, section.id, node_ranks)


def _plan_parent_id(
    section: _CompileSection,
    section_by_id: Mapping[str, _CompileSection],
) -> str | None:
    parent_id = section.parent_id
    if parent_id is not None and parent_id in section_by_id:
        return parent_id
    return None


def _section_depth(
    section: _CompileSection,
    section_by_id: Mapping[str, _CompileSection],
) -> int:
    depth = 0
    seen: set[str] = set()
    parent_id = _plan_parent_id(section, section_by_id)
    while parent_id is not None and parent_id not in seen:
        seen.add(parent_id)
        depth += 1
        parent = section_by_id.get(parent_id)
        if parent is None:
            break
        parent_id = _plan_parent_id(parent, section_by_id)
    return depth


def _stable_auto_name(section: _CompileSection, scc_id: str) -> str:
    raw = section.title or section.id
    slug = "".join(char.lower() if char.isalnum() else "_" for char in raw).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    if not slug:
        slug = "section"
    digest_payload = "|".join([section.id, section.kind, scc_id, *(_entry_key(ref) for ref in section.node_refs)])
    digest = hashlib.blake2b(digest_payload.encode("utf-8"), digest_size=4).hexdigest()
    return f"{slug}_{digest}"


def _effective_ref_adjacency(facts: GraphInventoryFacts) -> dict[CanonicalNodeRef, tuple[CanonicalNodeRef, ...]]:
    adjacency: dict[CanonicalNodeRef, set[CanonicalNodeRef]] = {
        fact.ref: set()
        for fact in facts.canonical_refs
    }
    for topology in facts.scope_topologies:
        for edge in topology.effective_edges:
            adjacency.setdefault(edge.source, set()).add(edge.target)
            adjacency.setdefault(edge.target, set())
    return {
        ref: tuple(sorted(targets, key=_ref_sort_key))
        for ref, targets in adjacency.items()
    }


def _normalized_sampler_pair(
    pair: tuple[CanonicalNodeRef, CanonicalNodeRef],
    claims: Sequence[SamplerRelationClaim],
    adjacency: Mapping[CanonicalNodeRef, Sequence[CanonicalNodeRef]],
    ref_to_section: Mapping[CanonicalNodeRef, str],
    canonical_by_ref: Mapping[CanonicalNodeRef, Any],
) -> CompiledSamplerRelation:
    left, right = pair
    left_path = _path_between_refs(left, right, adjacency)
    right_path = _path_between_refs(right, left, adjacency)
    directional: list[tuple[CanonicalNodeRef, CanonicalNodeRef, tuple[CanonicalNodeRef, ...]]] = []
    if left_path:
        directional.append((left, right, left_path))
    if right_path:
        directional.append((right, left, right_path))
    for claim in claims:
        if claim.kind in {"sampler_precedes", "sampler_refines"} and claim.source is not None and claim.target is not None:
            path = _path_between_refs(claim.source, claim.target, adjacency)
            directional.append((claim.source, claim.target, path or (claim.source, claim.target)))

    relation_kinds = {_claim_normalized_kind(claim) for claim in claims}
    relation_kinds.discard(None)
    bridge_path: tuple[CanonicalNodeRef, ...] = ()
    source: CanonicalNodeRef | None = None
    target: CanonicalNodeRef | None = None
    reasons = tuple(
        sorted(
            {
                claim.reason or claim.kind
                for claim in claims
            }
        )
    )

    if len({(item[0], item[1]) for item in directional}) > 1:
        kind: Literal["sequential", "parallel", "independent", "mixed"] = "mixed"
        source, target, bridge_path = sorted(directional, key=lambda item: (_ref_sort_key(item[0]), _ref_sort_key(item[1])))[0]
    elif directional:
        source, target, bridge_path = directional[0]
        if _bridge_path_whitelisted(bridge_path, canonical_by_ref):
            kind = "sequential"
        else:
            kind = "mixed"
        if relation_kinds and relation_kinds - {"sequential"}:
            kind = "mixed"
    elif "mixed" in relation_kinds:
        kind = "mixed"
    elif "parallel" in relation_kinds:
        kind = "parallel"
    elif "independent" in relation_kinds:
        kind = "independent"
    else:
        kind = "independent"

    section_ids = tuple(ref_to_section.get(ref, "__unowned__") for ref in pair)
    return CompiledSamplerRelation(
        kind=kind,
        samplers=pair,
        section_ids=section_ids,
        auto_name=_sampler_auto_name(kind, pair, source, target),
        source=source,
        target=target,
        bridge_path=bridge_path,
        reasons=reasons,
    )


def _claim_normalized_kind(claim: SamplerRelationClaim) -> str | None:
    if claim.kind in {"sampler_precedes", "sampler_refines"}:
        return "sequential"
    if claim.kind == "parallel_sampler_branch":
        return "parallel"
    if claim.kind == "independent_samplers":
        return "independent"
    if claim.kind == "same_sampler_pair":
        return "mixed"
    return None


def _path_between_refs(
    source: CanonicalNodeRef,
    target: CanonicalNodeRef,
    adjacency: Mapping[CanonicalNodeRef, Sequence[CanonicalNodeRef]],
) -> tuple[CanonicalNodeRef, ...]:
    pending: list[tuple[CanonicalNodeRef, tuple[CanonicalNodeRef, ...]]] = [
        (neighbor, (source, neighbor))
        for neighbor in adjacency.get(source, ())
    ]
    seen: set[CanonicalNodeRef] = set()
    while pending:
        ref, path = pending.pop(0)
        if ref == target:
            return path
        if ref in seen:
            continue
        seen.add(ref)
        for neighbor in adjacency.get(ref, ()):
            if neighbor not in seen:
                pending.append((neighbor, (*path, neighbor)))
    return ()


def _bridge_path_whitelisted(
    path: Sequence[CanonicalNodeRef],
    canonical_by_ref: Mapping[CanonicalNodeRef, Any],
) -> bool:
    if len(path) <= 2:
        return True
    return all(_is_bridge_ref(ref, canonical_by_ref) for ref in path[1:-1])


def _is_bridge_ref(
    ref: CanonicalNodeRef,
    canonical_by_ref: Mapping[CanonicalNodeRef, Any],
) -> bool:
    fact = canonical_by_ref.get(ref)
    if fact is None:
        return False
    if getattr(fact, "is_helper", False):
        return True
    class_type = str(getattr(fact, "class_type", "")).lower()
    role_hint = getattr(fact, "role_hint", ROLE_HINT_UNKNOWN)
    if role_hint in {
        ROLE_HINT_LATENT,
        ROLE_HINT_DECODE,
        ROLE_HINT_CONTROL,
        ROLE_HINT_POSTPROCESS,
        ROLE_HINT_HELPER,
        ROLE_HINT_UI,
        ROLE_HINT_UTILITY,
        ROLE_HINT_UNKNOWN,
    }:
        return True
    return any(token in class_type for token in ("latent", "upscale", "reroute", "pipe", "bridge"))


def _mixed_sampler_aggregate(
    relations: Sequence[CompiledSamplerRelation],
    ref_to_section: Mapping[CanonicalNodeRef, str],
) -> CompiledSamplerRelation | None:
    non_independent = [relation for relation in relations if relation.kind != "independent"]
    non_independent_kinds = {relation.kind for relation in non_independent}
    if len(non_independent_kinds) < 2:
        return None
    sampler_refs = tuple(
        sorted(
            {ref for relation in non_independent for ref in relation.samplers},
            key=_ref_sort_key,
        )
    )
    return CompiledSamplerRelation(
        kind="mixed",
        samplers=sampler_refs,
        section_ids=tuple(ref_to_section.get(ref, "__unowned__") for ref in sampler_refs),
        auto_name=_sampler_auto_name("mixed", sampler_refs, None, None),
        reasons=("sampler graph contains multiple non-independent relation kinds",),
    )


def _sampler_auto_name(
    kind: str,
    samplers: Sequence[CanonicalNodeRef],
    source: CanonicalNodeRef | None,
    target: CanonicalNodeRef | None,
) -> str:
    ordered = tuple(sorted(samplers, key=_ref_sort_key))
    direction = ""
    if source is not None and target is not None:
        direction = f"_{_entry_key(source)}_to_{_entry_key(target)}"
    raw = "_".join(_entry_key(ref) for ref in ordered)
    digest_payload = "|".join([kind, direction, *(_entry_key(ref) for ref in ordered)])
    digest = hashlib.blake2b(digest_payload.encode("utf-8"), digest_size=4).hexdigest()
    return f"samplers_{kind}_{raw}{direction}_{digest}"


def _sampler_claim_sort_key(claim: SamplerRelationClaim) -> tuple[Any, ...]:
    source = claim.source.to_json() if claim.source is not None else []
    target = claim.target.to_json() if claim.target is not None else []
    return (
        claim.kind,
        [ref.to_json() for ref in sorted(claim.samplers, key=_ref_sort_key)],
        source,
        target,
        claim.reason or "",
    )


def _compiled_sampler_relation_sort_key(relation: CompiledSamplerRelation) -> tuple[Any, ...]:
    source = relation.source.to_json() if relation.source is not None else []
    target = relation.target.to_json() if relation.target is not None else []
    return (
        1 if len(relation.samplers) > 2 else 0,
        relation.kind,
        [ref.to_json() for ref in relation.samplers],
        source,
        target,
    )


def _entry_for_layout(
    layout: CompiledNodeLayout,
    furniture: NodeFurnitureFact | None,
) -> Mapping[str, Any]:
    flags = _thaw_jsonish(furniture.flags) if furniture is not None else {}
    properties = _thaw_jsonish(furniture.properties) if furniture is not None else {}
    mode = furniture.mode if furniture is not None and isinstance(furniture.mode, int) else 0
    return {
        "pos": snap_pos((layout.x, layout.y)),
        "size": snap_size((layout.width, layout.height)),
        "flags": flags,
        "color": furniture.color if furniture is not None else None,
        "bgcolor": furniture.bgcolor if furniture is not None else None,
        "mode": mode,
        "properties": properties if isinstance(properties, dict) else {},
    }


def _sidecar_group(group: CompiledGroupLayout) -> Mapping[str, Any]:
    return {
        "title": group.title,
        "bounding": [group.x, group.y, group.width, group.height],
        "color": group.color,
        "nodes": [_entry_key(ref) for ref in group.node_refs],
    }


def _spacing(preset: SpacingPreset) -> _Spacing:
    if preset == "compact":
        return _Spacing(
            section_gap_x=360,
            island_gap_x=3200,
            band_gap_y=640,
            section_gap_y=72,
            node_gap_y=96,
            group_padding=32,
        )
    if preset == "wide":
        return _Spacing(
            section_gap_x=560,
            island_gap_x=5200,
            band_gap_y=1120,
            section_gap_y=144,
            node_gap_y=180,
            group_padding=64,
        )
    return _Spacing(
        section_gap_x=440,
        island_gap_x=4000,
        band_gap_y=840,
        section_gap_y=96,
        node_gap_y=140,
        group_padding=48,
    )


def _node_size(
    furniture: NodeFurnitureFact | None,
    *,
    preserve: bool,
) -> tuple[int, int]:
    if preserve and furniture is not None:
        size = _size(furniture.size)
        if size is not None:
            return size
    return (DEFAULT_NODE_WIDTH, DEFAULT_NODE_HEIGHT)


def _pos(value: Any) -> tuple[int, int] | None:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        left, top = value[0], value[1]
        if _is_number(left) and _is_number(top):
            return (round(left), round(top))
    return None


def _size(value: Any) -> tuple[int, int] | None:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        width, height = value[0], value[1]
        if _is_number(width) and _is_number(height) and width > 0 and height > 0:
            return (round(width), round(height))
    return None


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _helper_section_id(
    placement: Any,
    primary_owned: Mapping[CanonicalNodeRef, str],
) -> str:
    if placement.section_id is not None:
        return placement.section_id
    if placement.kind in {HELPER_PLACEMENT_NEAR_PRODUCER, HELPER_PLACEMENT_NEAR_CONSUMER}:
        if placement.target in primary_owned:
            return primary_owned[placement.target]
        return "__helpers__"
    if placement.kind == HELPER_PLACEMENT_EDGE_PATH:
        source_section = primary_owned.get(placement.source)
        destination_section = primary_owned.get(placement.destination)
        if source_section is not None and source_section == destination_section:
            return source_section
        return "__helpers__"
    if placement.kind == HELPER_PLACEMENT_INSIDE_SECTION:
        for ref in (placement.target, placement.source, placement.destination):
            if ref in primary_owned:
                return primary_owned[ref]
    return "__helpers__"


def _can_preserve_existing_groups(options: LayoutCompileOptions) -> bool:
    return not _force_existing_regroup(options) and options.existing_group_policy not in {
        "dissolve_with_warning",
    }


def _preserved_existing_ownership(
    facts: GraphInventoryFacts,
    *,
    unassigned_refs: Sequence[CanonicalNodeRef],
    assigned_refs: set[CanonicalNodeRef],
    classification: ClassificationReport,
) -> dict[CanonicalNodeRef, tuple[str, _GeneratedSection]]:
    unassigned = set(unassigned_refs)
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    ownership: dict[CanonicalNodeRef, tuple[str, _GeneratedSection]] = {}

    for scope in sorted(facts.scope_furniture, key=lambda item: item.scope_path):
        for group in sorted(scope.groups, key=lambda item: item.index):
            group_score = _score_existing_group(facts, group, classification)
            if group_score is None or not group_score.coherent:
                continue
            primary_refs = tuple(ref for ref in group_score.member_refs if ref not in helper_refs)
            if not primary_refs:
                continue
            if any(ref in assigned_refs for ref in primary_refs):
                continue
            group_refs = tuple(ref for ref in primary_refs if ref in unassigned and ref not in ownership)
            if not group_refs or len(group_refs) != len(primary_refs):
                continue
            section_id = _existing_group_section_id(group.scope_path, group.index)
            title = group.title if isinstance(group.title, str) and group.title else _title_for(section_id, SECTION_KIND_CUSTOM)
            generated = _GeneratedSection(
                kind=group_score.section_kind,
                title=title,
            )
            for ref in sorted(group_refs, key=_ref_sort_key):
                ownership[ref] = (section_id, generated)
    return ownership


def _score_existing_group(
    facts: GraphInventoryFacts,
    group: GroupFact,
    classification: ClassificationReport,
) -> _ExistingGroupScore | None:
    refs = _group_node_refs(facts, group.scope_path, group.nodes)
    if refs is None:
        return None
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    member_refs = tuple(ref for ref in refs if ref not in helper_refs)
    if not member_refs:
        return None

    rects = _node_rects_by_ref(facts.node_furniture)
    group_rect = _group_rect(group.bounding)
    contained_refs = _contained_group_refs(group.scope_path, group_rect, rects, helper_refs)
    member_set = set(member_refs)
    contained_set = set(contained_refs)
    containment = _ratio_float(len(member_set & contained_set), len(member_refs))
    node_coverage = _ratio_float(len(member_set & contained_set), len(member_set | contained_set))
    topology = _existing_group_topology_coherence(member_refs, facts)
    section_kind = _common_section_kind(member_refs, classification, facts)
    title_role = _existing_group_title_role_match(group.title, member_refs, section_kind, classification, facts)
    score = (
        EXISTING_GROUP_CONTAINMENT_WEIGHT * containment
        + EXISTING_GROUP_TOPOLOGY_WEIGHT * topology
        + EXISTING_GROUP_TITLE_ROLE_WEIGHT * title_role
        + EXISTING_GROUP_NODE_COVERAGE_WEIGHT * node_coverage
    )
    return _ExistingGroupScore(
        scope_path=group.scope_path,
        index=group.index,
        title=group.title,
        section_kind=section_kind,
        member_refs=tuple(sorted(member_refs, key=_ref_sort_key)),
        contained_refs=tuple(sorted(contained_refs, key=_ref_sort_key)),
        containment=containment,
        topology=topology,
        title_role=title_role,
        node_coverage=node_coverage,
        score=score,
    )


def _node_rects_by_ref(
    node_furniture: Sequence[NodeFurnitureFact],
) -> dict[CanonicalNodeRef, _ExistingGroupRect]:
    rects: dict[CanonicalNodeRef, _ExistingGroupRect] = {}
    for furniture in node_furniture:
        pos = _pos_float(furniture.pos)
        size = _size_float(furniture.size)
        if pos is None or size is None:
            continue
        rects[furniture.ref] = _ExistingGroupRect(pos[0], pos[1], size[0], size[1])
    return rects


def _contained_group_refs(
    scope_path: str,
    group_rect: _ExistingGroupRect | None,
    rects: Mapping[CanonicalNodeRef, _ExistingGroupRect],
    helper_refs: set[CanonicalNodeRef],
) -> tuple[CanonicalNodeRef, ...]:
    if group_rect is None:
        return ()
    return tuple(
        sorted(
            (
                ref
                for ref, rect in rects.items()
                if ref.scope_path == scope_path
                and ref not in helper_refs
                and _rect_contains(group_rect, rect)
            ),
            key=_ref_sort_key,
        )
    )


def _existing_group_topology_coherence(
    member_refs: Sequence[CanonicalNodeRef],
    facts: GraphInventoryFacts,
) -> float:
    member_set = set(member_refs)
    incident = 0
    internal = 0
    seen: set[tuple[CanonicalNodeRef, CanonicalNodeRef]] = set()
    for topology in facts.scope_topologies:
        for edge in topology.effective_edges:
            if edge.source not in member_set and edge.target not in member_set:
                continue
            edge_key = tuple(sorted((edge.source, edge.target), key=_ref_sort_key))
            if edge_key in seen:
                continue
            seen.add(edge_key)
            incident += 1
            if edge.source in member_set and edge.target in member_set:
                internal += 1
    if incident == 0:
        return 1.0 if len(member_refs) == 1 else 0.0
    return _ratio_float(internal, incident)


def _existing_group_title_role_match(
    title: str | None,
    member_refs: Sequence[CanonicalNodeRef],
    section_kind: SectionKind,
    classification: ClassificationReport,
    facts: GraphInventoryFacts,
) -> float:
    if not isinstance(title, str) or not title.strip() or not member_refs:
        return 0.0
    title_tokens = _text_tokens(title)
    if not title_tokens:
        return 0.0
    member_kinds = [
        _section_kind_for_ref(ref, classification, facts)
        for ref in member_refs
    ]
    dominant_count = sum(1 for kind in member_kinds if kind == section_kind)
    homogeneity = _ratio_float(dominant_count, len(member_kinds))
    role_tokens = set(_SECTION_TITLE_TOKENS.get(section_kind, ()))
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    for ref in member_refs:
        if _section_kind_for_ref(ref, classification, facts) != section_kind:
            continue
        fact = canonical_by_ref.get(ref)
        if fact is None:
            continue
        role_tokens.update(_text_tokens(getattr(fact, "class_type", "")))
        role_tokens.update(_text_tokens(getattr(fact, "display", "")))
        role_tokens.update(_text_tokens(getattr(fact, "title", "") or ""))
    title_match = 1.0 if title_tokens & role_tokens else 0.0
    return homogeneity * title_match


def _section_kind_for_ref(
    ref: CanonicalNodeRef,
    classification: ClassificationReport,
    facts: GraphInventoryFacts,
) -> SectionKind:
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    fact = canonical_by_ref.get(ref)
    hint = classification.hint_for(ref)
    role = hint.role_hint if hint is not None else fact.role_hint if fact is not None else ROLE_HINT_UNKNOWN
    return _ROLE_TO_SECTION_KIND.get(role, SECTION_KIND_CUSTOM)


def _text_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    token = ""
    for char in value.lower():
        if char.isalnum():
            token += char
            continue
        if token:
            tokens.add(_normalize_token(token))
            token = ""
    if token:
        tokens.add(_normalize_token(token))
    return {item for item in tokens if item}


def _normalize_token(token: str) -> str:
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _group_rect(value: Any) -> _ExistingGroupRect | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 4:
        return None
    x = _number_float(value[0])
    y = _number_float(value[1])
    width = _number_float(value[2])
    height = _number_float(value[3])
    if x is None or y is None or width is None or height is None:
        return None
    if width <= 0.0 or height <= 0.0:
        return None
    return _ExistingGroupRect(x, y, width, height)


def _pos_float(value: Any) -> tuple[float, float] | None:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        x = _number_float(value[0])
        y = _number_float(value[1])
        if x is not None and y is not None:
            return (x, y)
    return None


def _size_float(value: Any) -> tuple[float, float] | None:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        width = _number_float(value[0])
        height = _number_float(value[1])
        if width is not None and height is not None and width > 0.0 and height > 0.0:
            return (width, height)
    return None


def _number_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _rect_contains(container: _ExistingGroupRect, child: _ExistingGroupRect) -> bool:
    return (
        child.x >= container.x
        and child.y >= container.y
        and child.right <= container.right
        and child.bottom <= container.bottom
    )


def _ratio_float(numerator: int | float, denominator: int | float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _group_node_refs(
    facts: GraphInventoryFacts,
    scope_path: str,
    group_nodes: Sequence[Any],
) -> tuple[CanonicalNodeRef, ...] | None:
    by_token: dict[Any, CanonicalNodeRef] = {}
    for fact in facts.canonical_refs:
        ref = fact.ref
        if ref.scope_path != scope_path:
            continue
        by_token[ref.uid] = ref
        by_token[_entry_key(ref)] = ref
        if fact.litegraph_id is not None:
            by_token[fact.litegraph_id] = ref
            by_token[str(fact.litegraph_id)] = ref
    refs: list[CanonicalNodeRef] = []
    seen: set[CanonicalNodeRef] = set()
    for raw in group_nodes:
        ref = by_token.get(raw)
        if ref is None:
            return None
        if ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return tuple(sorted(refs, key=_ref_sort_key))


def _existing_group_section_id(scope_path: str, index: int) -> str:
    scope_label = "root" if scope_path == "" else scope_path.replace("/", "_").replace(":", "_")
    return f"__existing_{scope_label}_{index}__"


def _common_section_kind(
    refs: Sequence[CanonicalNodeRef],
    classification: ClassificationReport,
    facts: GraphInventoryFacts,
) -> SectionKind:
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    counts: dict[SectionKind, int] = {}
    for ref in refs:
        fact = canonical_by_ref.get(ref)
        hint = classification.hint_for(ref)
        role = hint.role_hint if hint is not None else fact.role_hint if fact is not None else ROLE_HINT_UNKNOWN
        kind = _ROLE_TO_SECTION_KIND.get(role, SECTION_KIND_CUSTOM)
        counts[kind] = counts.get(kind, 0) + 1
    if not counts:
        return SECTION_KIND_CUSTOM
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _section_for_role(
    role: RoleHint,
    section_defs: Mapping[str, LayoutSection],
) -> str:
    kind = _ROLE_TO_SECTION_KIND.get(role, SECTION_KIND_CUSTOM)
    for section_id, section in sorted(section_defs.items()):
        if section.kind == kind:
            return section_id
    return f"__{kind}__"


def _generated_section_kind(section_id: str) -> SectionKind:
    if section_id == "__helpers__":
        return SECTION_KIND_UTILITY
    if section_id.startswith("__") and section_id.endswith("__"):
        raw_kind = section_id[2:-2]
        if raw_kind in _ROLE_COLORS:
            return raw_kind  # type: ignore[return-value]
    return SECTION_KIND_CUSTOM


def _title_for(section_id: str, kind: SectionKind) -> str:
    if section_id.startswith("__") and section_id.endswith("__"):
        return kind.replace("_", " ").title()
    return section_id.replace("_", " ").replace("-", " ").title()


def _section_sort_key(
    section_id: str,
    section: LayoutSection | None,
    refs: Sequence[CanonicalNodeRef],
) -> tuple[str, str, str]:
    scope_key = _common_scope(refs)
    kind = section.kind if section is not None else _generated_section_kind(section_id)
    return (scope_key, kind, section_id)


def _common_scope(refs: Sequence[CanonicalNodeRef]) -> str:
    if not refs:
        return ""
    scopes = {ref.scope_path for ref in refs}
    return scopes.pop() if len(scopes) == 1 else ""


def _common_group_scope(groups: Sequence[CompiledGroupLayout]) -> str:
    if not groups:
        return ""
    scopes = {group.scope_path for group in groups}
    return scopes.pop() if len(scopes) == 1 else ""


def _scope_depth(scope_path: str) -> int:
    if not scope_path:
        return 0
    return scope_path.count("/") + 1


def _ref_sort_key(ref: CanonicalNodeRef) -> tuple[int, str, str]:
    return (0 if ref.scope_path == "" else 1, ref.scope_path, ref.uid)


def _id_sort_key(value: str) -> tuple[int, str]:
    return (0, value.zfill(20)) if value.isdigit() else (1, value)


def _entry_key(ref: CanonicalNodeRef) -> str:
    return make_uid(ref.scope_path, ref.uid)


__all__ = [
    "COMPILE_METRIC_GROUP_LAYOUT_COUNT",
    "COMPILE_METRIC_HELPER_LAYOUT_COUNT",
    "COMPILE_METRIC_NODE_LAYOUT_COUNT",
    "COMPILE_METRIC_ORDER",
    "COMPILE_METRIC_STRUCTURAL_HASH_UNCHANGED",
    "CompiledGroupLayout",
    "CompiledNodeLayout",
    "CompiledSamplerRelation",
    "CompiledSectionTopology",
    "ExistingGroupPolicy",
    "LayoutCandidatePatch",
    "LayoutCompileOptions",
    "LayoutCompileResult",
    "SectionTemplate",
    "SpacingPreset",
    "compile_layout_plan",
    "compile_layout_plan_from_ui",
    "structural_hash_for_layout_facts",
]
