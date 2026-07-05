from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Sequence

from vibecomfy.identity.uid import SCOPE_CHAIN_JOIN
from vibecomfy.identity.uid import parse_uid
from vibecomfy.porting.edit.ledger import EditLedger
from vibecomfy.porting.layout_store import migrate_store

from .assess import assess_layout_facts
from .classify import classify_layout_facts
from .compile import (
    LayoutCandidatePatch,
    LayoutCompileOptions,
    LayoutCompileResult,
    compile_layout_plan,
    structural_hash_for_layout_facts,
)
from .diagnostics import ReorganiseDiagnostic, ReorganiseDiagnosticReport
from .graph_facts import GraphInventoryFacts, extract_graph_facts
from .parse import LAYOUT_PLAN_SCHEMA_V1, LayoutPlanParseError, parse_layout_plan
from .plan_types import (
    HELPER_PLACEMENT_INSIDE_SECTION,
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
    UNASSIGNED_REJECT,
    AssessmentReport,
    CanonicalNodeRef,
    GraphFactsSummary,
    HelperPlacement,
    LayoutPlanV1,
    LayoutSection,
    RoleHint,
    SectionKind,
)
from .projection import (
    LayoutProjectionOptions,
    LayoutProjectionResult,
    render_layout_projection,
)
from .validate import validate_layout_plan

PlanSource = Literal["deterministic", "provided", "semantic_provider"]
SemanticLayoutPlanProvider = Callable[["SemanticLayoutPlanningRequest"], Any]
SecondStageLayoutPlanProvider = Callable[["SecondStageLayoutPlanningRequest"], Any]

_PATCH_ENTRY_KEYS = ("pos", "size", "flags", "color", "bgcolor", "mode", "properties")

_ROLE_TO_SECTION_KIND: Mapping[RoleHint, SectionKind] = {
    ROLE_HINT_LOADER: SECTION_KIND_LOADERS,
    ROLE_HINT_CONDITIONING: SECTION_KIND_CONDITIONING,
    ROLE_HINT_LATENT: SECTION_KIND_LATENT,
    ROLE_HINT_SAMPLER: SECTION_KIND_SAMPLING,
    ROLE_HINT_DECODE: SECTION_KIND_DECODE,
    ROLE_HINT_OUTPUT: SECTION_KIND_OUTPUT,
    ROLE_HINT_CONTROL: SECTION_KIND_CONTROL,
    ROLE_HINT_POSTPROCESS: SECTION_KIND_POSTPROCESS,
    ROLE_HINT_UTILITY: SECTION_KIND_UTILITY,
    ROLE_HINT_HELPER: SECTION_KIND_UTILITY,
    ROLE_HINT_UI: SECTION_KIND_UTILITY,
    ROLE_HINT_SHARED: SECTION_KIND_CUSTOM,
    ROLE_HINT_SUBGRAPH_CONTAINER: SECTION_KIND_CONTAINER,
    ROLE_HINT_UNKNOWN: SECTION_KIND_CUSTOM,
}
_SECTION_TITLES: Mapping[SectionKind, str] = {
    SECTION_KIND_LOADERS: "Loaders",
    SECTION_KIND_CONDITIONING: "Conditioning",
    SECTION_KIND_LATENT: "Latent",
    SECTION_KIND_SAMPLING: "Sampling",
    SECTION_KIND_DECODE: "Decode",
    SECTION_KIND_OUTPUT: "Output",
    SECTION_KIND_CONTROL: "Control",
    SECTION_KIND_POSTPROCESS: "Postprocess",
    SECTION_KIND_UTILITY: "Utility",
    SECTION_KIND_CONTAINER: "Container",
    SECTION_KIND_CUSTOM: "Custom",
}
_SECTION_ORDER = {
    SECTION_KIND_CONTAINER: 0,
    SECTION_KIND_LOADERS: 10,
    SECTION_KIND_CONDITIONING: 20,
    SECTION_KIND_LATENT: 30,
    SECTION_KIND_CONTROL: 40,
    SECTION_KIND_SAMPLING: 50,
    SECTION_KIND_DECODE: 60,
    SECTION_KIND_POSTPROCESS: 70,
    SECTION_KIND_OUTPUT: 80,
    SECTION_KIND_UTILITY: 90,
    SECTION_KIND_CUSTOM: 100,
}

_LAYOUT_PLAN_SCHEMA_REMINDER_V1: Mapping[str, Any] = {
    "name": "LayoutPlan v1",
    "schema": LAYOUT_PLAN_SCHEMA_V1,
    "strict": True,
    "instructions": (
        "Return only a JSON object matching LayoutPlan v1. Use canonical "
        "[scope_path, uid] refs from the projection. Do not include coordinates, "
        "node payloads, links, widgets, runtime values, topology rewrites, or "
        "candidate patch data."
    ),
}

_AMBIGUOUS_SAMPLER_RELATION_KINDS = frozenset(
    {"same_sampler_pair", "parallel_sampler_branch", "independent_samplers"}
)


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _freeze_jsonish(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_freeze_jsonish(item) for item in value]
    if isinstance(value, list):
        return [_freeze_jsonish(item) for item in value]
    return value


def _thaw_jsonish(value: Any) -> Any:
    return _freeze_jsonish(value)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _freeze_jsonish(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class ReorganisePreviewOptions:
    compile_options: LayoutCompileOptions = field(default_factory=LayoutCompileOptions)
    projection_options: LayoutProjectionOptions | None = None
    second_stage_options: "SecondStagePlanningOptions" = field(
        default_factory=lambda: SecondStagePlanningOptions()
    )

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "compile_options": self.compile_options.to_json(),
            "second_stage_options": self.second_stage_options.to_json(),
        }
        if self.projection_options is not None:
            payload["projection_options"] = {
                "max_tokens": self.projection_options.max_tokens,
                "max_canonical_refs": self.projection_options.max_canonical_refs,
                "max_node_facts_per_scope": self.projection_options.max_node_facts_per_scope,
                "max_edges_per_scope": self.projection_options.max_edges_per_scope,
                "max_terminal_paths_per_scope": self.projection_options.max_terminal_paths_per_scope,
                "max_furniture_facts": self.projection_options.max_furniture_facts,
                "max_group_facts_per_scope": self.projection_options.max_group_facts_per_scope,
            }
        return payload


@dataclass(frozen=True, slots=True)
class SecondStagePlanningOptions:
    large_group_node_count: int = 12
    high_edge_density: float = 1.5
    ambiguous_sampler_count: int = 2
    max_groups: int = 4

    def to_json(self) -> dict[str, Any]:
        return {
            "large_group_node_count": self.large_group_node_count,
            "high_edge_density": self.high_edge_density,
            "ambiguous_sampler_count": self.ambiguous_sampler_count,
            "max_groups": self.max_groups,
        }


@dataclass(frozen=True, slots=True)
class SemanticLayoutPlanningRequest:
    pythonic_projection: str
    graph_facts_summary: Mapping[str, Any]
    layout_plan_schema_reminder: Mapping[str, Any]
    compile_options: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "graph_facts_summary",
            _freeze_jsonish(self.graph_facts_summary),
        )
        object.__setattr__(
            self,
            "layout_plan_schema_reminder",
            _freeze_jsonish(self.layout_plan_schema_reminder),
        )
        object.__setattr__(self, "compile_options", _freeze_jsonish(self.compile_options))

    def to_json(self) -> dict[str, Any]:
        return {
            "pythonic_projection": self.pythonic_projection,
            "graph_facts_summary": _freeze_jsonish(self.graph_facts_summary),
            "layout_plan_schema_reminder": _freeze_jsonish(self.layout_plan_schema_reminder),
            "compile_options": _freeze_jsonish(self.compile_options),
        }


@dataclass(frozen=True, slots=True)
class SecondStagePlanningGroup:
    section_id: str
    section_title: str | None
    scope_path: str
    trigger_reasons: tuple[str, ...]
    group_node_refs: tuple[CanonicalNodeRef, ...]
    boundary_node_refs: tuple[CanonicalNodeRef, ...]
    internal_edge_count: int
    boundary_edge_count: int
    edge_density: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger_reasons", tuple(self.trigger_reasons))
        object.__setattr__(self, "group_node_refs", tuple(self.group_node_refs))
        object.__setattr__(self, "boundary_node_refs", tuple(self.boundary_node_refs))

    def to_json(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "section_title": self.section_title,
            "scope_path": self.scope_path,
            "trigger_reasons": list(self.trigger_reasons),
            "group_node_refs": [ref.to_json() for ref in self.group_node_refs],
            "boundary_node_refs": [ref.to_json() for ref in self.boundary_node_refs],
            "internal_edge_count": self.internal_edge_count,
            "boundary_edge_count": self.boundary_edge_count,
            "edge_density": self.edge_density,
        }


@dataclass(frozen=True, slots=True)
class SecondStageLayoutPlanningRequest:
    group: SecondStagePlanningGroup
    scoped_projection: str
    graph_facts_summary: Mapping[str, Any]
    layout_plan_schema_reminder: Mapping[str, Any]
    compile_options: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "graph_facts_summary",
            _freeze_jsonish(self.graph_facts_summary),
        )
        object.__setattr__(
            self,
            "layout_plan_schema_reminder",
            _freeze_jsonish(self.layout_plan_schema_reminder),
        )
        object.__setattr__(self, "compile_options", _freeze_jsonish(self.compile_options))

    def to_json(self) -> dict[str, Any]:
        return {
            "group": self.group.to_json(),
            "scoped_projection": self.scoped_projection,
            "graph_facts_summary": _freeze_jsonish(self.graph_facts_summary),
            "layout_plan_schema_reminder": _freeze_jsonish(self.layout_plan_schema_reminder),
            "compile_options": _freeze_jsonish(self.compile_options),
        }


@dataclass(frozen=True, slots=True)
class SecondStagePlanningResult:
    request: SecondStageLayoutPlanningRequest
    provider_diagnostics: tuple[ReorganiseDiagnostic, ...] = ()
    plan: LayoutPlanV1 | None = None
    parse_diagnostics: tuple[Any, ...] = ()
    validation_report: ReorganiseDiagnosticReport | None = None
    compile_diagnostics: tuple[ReorganiseDiagnostic, ...] = ()
    compile_ok: bool = False

    @property
    def ok(self) -> bool:
        return (
            not self.provider_diagnostics
            and not self.parse_diagnostics
            and self.validation_report is not None
            and self.validation_report.ok
            and self.compile_ok
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "request": self.request.to_json(),
            "provider_diagnostics": [
                diagnostic.to_json() for diagnostic in self.provider_diagnostics
            ],
            "plan_sha256": _sha256(self.plan.to_json()) if self.plan is not None else None,
            "parse_diagnostics": [
                diagnostic.to_json() if hasattr(diagnostic, "to_json") else diagnostic
                for diagnostic in self.parse_diagnostics
            ],
            "validation_report": (
                self.validation_report.to_json()
                if self.validation_report is not None
                else None
            ),
            "compile_diagnostics": [
                diagnostic.to_json() for diagnostic in self.compile_diagnostics
            ],
        }


@dataclass(frozen=True, slots=True)
class ReorganiseLoadedWorkflow:
    ui_json: Mapping[str, Any]
    source_label: str | None = None
    source_bytes_sha256: str | None = None
    source_canonical_sha256: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "source_label": self.source_label,
            "source_bytes_sha256": self.source_bytes_sha256,
            "source_canonical_sha256": self.source_canonical_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReorganiseApplyData:
    source_canonical_sha256: str
    source_bytes_sha256: str | None
    sidecar_sha256: str
    plan_sha256: str | None
    candidate_patch_sha256: str | None
    structural_hash_before: str | None
    structural_hash_after: str | None
    layout_only_structural_noop: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "source_canonical_sha256": self.source_canonical_sha256,
            "source_bytes_sha256": self.source_bytes_sha256,
            "sidecar_sha256": self.sidecar_sha256,
            "plan_sha256": self.plan_sha256,
            "candidate_patch_sha256": self.candidate_patch_sha256,
            "structural_hash_before": self.structural_hash_before,
            "structural_hash_after": self.structural_hash_after,
            "layout_only_structural_noop": self.layout_only_structural_noop,
        }


@dataclass(frozen=True, slots=True)
class ReorganisePatchApplyResult:
    ui_json: Mapping[str, Any]
    candidate_patch_sha256: str
    structural_hash_before: str
    structural_hash_after: str
    layout_only_structural_noop: bool
    applied_entry_keys: tuple[str, ...] = ()
    skipped_entry_keys: tuple[str, ...] = ()
    applied_group_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "ui_json", _freeze_jsonish(self.ui_json))
        object.__setattr__(self, "applied_entry_keys", tuple(self.applied_entry_keys))
        object.__setattr__(self, "skipped_entry_keys", tuple(self.skipped_entry_keys))
        object.__setattr__(self, "applied_group_scopes", tuple(self.applied_group_scopes))

    def to_json(self, *, include_ui_json: bool = False) -> dict[str, Any]:
        payload = {
            "candidate_patch_sha256": self.candidate_patch_sha256,
            "structural_hash_before": self.structural_hash_before,
            "structural_hash_after": self.structural_hash_after,
            "layout_only_structural_noop": self.layout_only_structural_noop,
            "applied_entry_keys": list(self.applied_entry_keys),
            "skipped_entry_keys": list(self.skipped_entry_keys),
            "applied_group_scopes": list(self.applied_group_scopes),
        }
        if include_ui_json:
            payload["ui_json"] = _freeze_jsonish(self.ui_json)
        return payload


@dataclass(frozen=True, slots=True)
class ReorganiseAssessmentResult:
    loaded: ReorganiseLoadedWorkflow
    sidecar_envelope: Mapping[str, Any]
    facts: GraphInventoryFacts
    assessment: AssessmentReport
    projection: LayoutProjectionResult
    graph_summary: GraphFactsSummary

    def to_json(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded.to_json(),
            "sidecar_sha256": _sha256(self.sidecar_envelope),
            "assessment": self.assessment.to_json(),
            "projection": {
                "text": self.projection.text,
                "token_estimate": self.projection.token_estimate,
                "scope_count": self.projection.scope_count,
                "canonical_ref_count": self.projection.canonical_ref_count,
                "summarized": self.projection.summarized,
                "truncated": self.projection.truncated,
            },
            "graph_summary": self.graph_summary.to_json(),
        }


@dataclass(frozen=True, slots=True)
class ReorganisePreviewResult:
    loaded: ReorganiseLoadedWorkflow
    sidecar_envelope: Mapping[str, Any]
    facts: GraphInventoryFacts
    assessment: AssessmentReport
    projection: LayoutProjectionResult
    graph_summary: GraphFactsSummary
    options: ReorganisePreviewOptions
    plan_source: PlanSource
    provider_diagnostics: tuple[ReorganiseDiagnostic, ...]
    plan: LayoutPlanV1 | None
    parse_diagnostics: tuple[Any, ...]
    validation_report: ReorganiseDiagnosticReport | None
    second_stage_results: tuple[SecondStagePlanningResult, ...]
    compile_diagnostics: tuple[ReorganiseDiagnostic, ...]
    compile_result: LayoutCompileResult | None
    apply_data: ReorganiseApplyData

    @property
    def ok(self) -> bool:
        return (
            self.compile_result is not None
            and self.compile_result.ok
            and all(result.ok for result in self.second_stage_results)
        )

    @property
    def candidate_patch(self) -> Mapping[str, Any] | None:
        if self.compile_result is None or not self.compile_result.ok:
            return None
        return self.compile_result.candidate_patch.to_json()

    @property
    def layout_trace(self) -> tuple[Mapping[str, Any], ...]:
        if self.compile_result is None or not self.compile_result.ok:
            return ()
        return tuple(entry.to_json() for entry in self.compile_result.trace_entries)

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "loaded": self.loaded.to_json(),
            "sidecar_sha256": _sha256(self.sidecar_envelope),
            "options": self.options.to_json(),
            "plan_source": self.plan_source,
            "provider_diagnostics": [
                diagnostic.to_json() for diagnostic in self.provider_diagnostics
            ],
            "plan": self.plan.to_json() if self.plan is not None else None,
            "parse_diagnostics": [
                diagnostic.to_json() if hasattr(diagnostic, "to_json") else diagnostic
                for diagnostic in self.parse_diagnostics
            ],
            "validation_report": (
                self.validation_report.to_json()
                if self.validation_report is not None
                else None
            ),
            "second_stage_results": [
                result.to_json() for result in self.second_stage_results
            ],
            "compile_diagnostics": [
                diagnostic.to_json() for diagnostic in self.compile_diagnostics
            ],
            "assessment": self.assessment.to_json(),
            "projection": {
                "text": self.projection.text,
                "token_estimate": self.projection.token_estimate,
                "scope_count": self.projection.scope_count,
                "canonical_ref_count": self.projection.canonical_ref_count,
                "summarized": self.projection.summarized,
                "truncated": self.projection.truncated,
            },
            "graph_summary": self.graph_summary.to_json(),
            "compile_result": (
                self.compile_result.to_json()
                if self.compile_result is not None and self.compile_result.ok
                else None
            ),
            "candidate_patch": self.candidate_patch,
            "layout_trace": list(self.layout_trace),
            "apply_data": self.apply_data.to_json(),
        }


def load_reorganise_ui_json(ui_json_or_path: Mapping[str, Any] | str | PathLike[str]) -> ReorganiseLoadedWorkflow:
    if isinstance(ui_json_or_path, Mapping):
        ui_json = copy.deepcopy(dict(ui_json_or_path))
        return ReorganiseLoadedWorkflow(
            ui_json=ui_json,
            source_canonical_sha256=_sha256(ui_json),
        )

    path = Path(ui_json_or_path)
    raw = path.read_bytes()
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, Mapping):
        raise ValueError("workflow UI JSON must be an object")
    ui_json = copy.deepcopy(dict(parsed))
    return ReorganiseLoadedWorkflow(
        ui_json=ui_json,
        source_label=path.name,
        source_bytes_sha256=hashlib.sha256(raw).hexdigest(),
        source_canonical_sha256=_sha256(ui_json),
    )


def load_layout_sidecar_envelope(sidecar: Mapping[str, Any] | str | PathLike[str] | None) -> dict[str, Any] | None:
    if sidecar is None:
        return None
    if isinstance(sidecar, Mapping):
        thawed = _freeze_jsonish(sidecar)
        return migrate_store(thawed if isinstance(thawed, dict) else {})
    path = Path(sidecar)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return migrate_store(data)


def build_or_preserve_layout_sidecar(
    ui_json: Mapping[str, Any],
    sidecar_envelope: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], GraphInventoryFacts]:
    preserved = (
        migrate_store(_freeze_jsonish(sidecar_envelope))
        if sidecar_envelope is not None
        else None
    )
    facts = extract_graph_facts(ui_json, sidecar_envelope=preserved)
    sidecar = _freeze_jsonish(facts.sidecar_envelope)
    return sidecar if isinstance(sidecar, dict) else {}, facts


def assess_reorganise_workflow(
    ui_json_or_path: Mapping[str, Any] | str | PathLike[str],
    *,
    sidecar_envelope: Mapping[str, Any] | str | PathLike[str] | None = None,
    projection_options: LayoutProjectionOptions | None = None,
) -> ReorganiseAssessmentResult:
    loaded = load_reorganise_ui_json(ui_json_or_path)
    sidecar = load_layout_sidecar_envelope(sidecar_envelope)
    built_sidecar, facts = build_or_preserve_layout_sidecar(loaded.ui_json, sidecar)
    assessment = assess_layout_facts(facts)
    projection = render_layout_projection(facts, options=projection_options)
    return ReorganiseAssessmentResult(
        loaded=loaded,
        sidecar_envelope=built_sidecar,
        facts=facts,
        assessment=assessment,
        projection=projection,
        graph_summary=facts.summary,
    )


def preview_reorganise_workflow(
    ui_json_or_path: Mapping[str, Any] | str | PathLike[str],
    *,
    sidecar_envelope: Mapping[str, Any] | str | PathLike[str] | None = None,
    plan_payload: Any | None = None,
    semantic_plan_provider: SemanticLayoutPlanProvider | None = None,
    second_stage_plan_provider: SecondStageLayoutPlanProvider | None = None,
    options: ReorganisePreviewOptions | None = None,
) -> ReorganisePreviewResult:
    opts = options or ReorganisePreviewOptions()
    loaded = load_reorganise_ui_json(ui_json_or_path)
    sidecar = load_layout_sidecar_envelope(sidecar_envelope)
    built_sidecar, facts = build_or_preserve_layout_sidecar(loaded.ui_json, sidecar)
    assessment = assess_layout_facts(facts)
    projection = render_layout_projection(facts, options=opts.projection_options)
    provider_diagnostics: tuple[ReorganiseDiagnostic, ...] = ()
    if semantic_plan_provider is not None and plan_payload is None:
        plan_source: PlanSource = "semantic_provider"
        request = build_semantic_layout_planning_request(
            projection=projection,
            graph_summary=facts.summary,
            compile_options=opts.compile_options,
        )
        try:
            plan_payload = semantic_plan_provider(request)
        except Exception as exc:  # noqa: BLE001 - provider failures must fail closed.
            provider_diagnostics = (
                ReorganiseDiagnostic(
                    code="semantic_provider_error",
                    message="Semantic layout plan provider failed before returning LayoutPlan v1 output.",
                    path=("semantic_plan_provider",),
                    detail={"exception_type": type(exc).__name__},
                ),
            )
    else:
        plan_source = "provided" if plan_payload is not None else "deterministic"

    parse_diagnostics: tuple[Any, ...] = ()
    plan: LayoutPlanV1 | None = None
    if plan_payload is None and not provider_diagnostics:
        plan_payload = build_deterministic_layout_plan(facts).to_json()
    if plan_payload is not None:
        try:
            plan = parse_layout_plan(plan_payload)
        except LayoutPlanParseError as exc:
            parse_diagnostics = exc.diagnostics

    validation_report: ReorganiseDiagnosticReport | None = None
    second_stage_results: tuple[SecondStagePlanningResult, ...] = ()
    compile_diagnostics: tuple[ReorganiseDiagnostic, ...] = ()
    compile_result: LayoutCompileResult | None = None
    if plan is not None:
        validation_report = validate_layout_plan(plan, facts)
        if validation_report.ok:
            if second_stage_plan_provider is not None:
                second_stage_results = run_second_stage_intra_group_planning(
                    plan=plan,
                    facts=facts,
                    provider=second_stage_plan_provider,
                    compile_options=opts.compile_options,
                    options=opts.second_stage_options,
                )
            second_stage_ok = all(result.ok for result in second_stage_results)
        else:
            second_stage_ok = False
        if validation_report.ok and second_stage_ok:
            compiled = compile_layout_plan(plan, facts, options=opts.compile_options)
            if not compiled.ok:
                fallback_compile_options = _small_wrapper_node_only_fallback_options(
                    facts,
                    opts.compile_options,
                )
                if fallback_compile_options is not None:
                    fallback_compiled = compile_layout_plan(
                        plan,
                        facts,
                        options=fallback_compile_options,
                    )
                    if fallback_compiled.ok:
                        compiled = fallback_compiled
            if compiled.ok:
                compile_result = compiled
            else:
                compile_diagnostics = _compile_failure_diagnostics(compiled)

    candidate_patch = (
        compile_result.candidate_patch.to_json()
        if compile_result is not None and compile_result.ok
        else None
    )
    apply_data = ReorganiseApplyData(
        source_canonical_sha256=loaded.source_canonical_sha256,
        source_bytes_sha256=loaded.source_bytes_sha256,
        sidecar_sha256=_sha256(built_sidecar),
        plan_sha256=_sha256(plan.to_json()) if plan is not None else None,
        candidate_patch_sha256=_sha256(candidate_patch) if candidate_patch is not None else None,
        structural_hash_before=compile_result.structural_hash_before if compile_result is not None else None,
        structural_hash_after=compile_result.structural_hash_after if compile_result is not None else None,
        layout_only_structural_noop=(
            compile_result is not None
            and compile_result.structural_hash_before == compile_result.structural_hash_after
        ),
    )
    return ReorganisePreviewResult(
        loaded=loaded,
        sidecar_envelope=built_sidecar,
        facts=facts,
        assessment=assessment,
        projection=projection,
        graph_summary=facts.summary,
        options=opts,
        plan_source=plan_source,
        provider_diagnostics=provider_diagnostics,
        plan=plan,
        parse_diagnostics=parse_diagnostics,
        validation_report=validation_report,
        second_stage_results=second_stage_results,
        compile_diagnostics=compile_diagnostics,
        compile_result=compile_result,
        apply_data=apply_data,
    )


def build_semantic_layout_planning_request(
    *,
    projection: LayoutProjectionResult,
    graph_summary: GraphFactsSummary,
    compile_options: LayoutCompileOptions,
) -> SemanticLayoutPlanningRequest:
    return SemanticLayoutPlanningRequest(
        pythonic_projection=projection.text,
        graph_facts_summary=graph_summary.to_json(),
        layout_plan_schema_reminder=_LAYOUT_PLAN_SCHEMA_REMINDER_V1,
        compile_options=compile_options.to_json(),
    )


def run_second_stage_intra_group_planning(
    *,
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    provider: SecondStageLayoutPlanProvider,
    compile_options: LayoutCompileOptions,
    options: SecondStagePlanningOptions | None = None,
) -> tuple[SecondStagePlanningResult, ...]:
    opts = options or SecondStagePlanningOptions()
    requests = build_second_stage_layout_planning_requests(
        plan=plan,
        facts=facts,
        compile_options=compile_options,
        options=opts,
    )
    results: list[SecondStagePlanningResult] = []
    for request in requests:
        provider_diagnostics: tuple[ReorganiseDiagnostic, ...] = ()
        plan_payload: Any | None = None
        try:
            plan_payload = provider(request)
        except Exception as exc:  # noqa: BLE001 - provider failures must fail closed.
            provider_diagnostics = (
                ReorganiseDiagnostic(
                    code="second_stage_provider_error",
                    message="Second-stage layout plan provider failed before returning LayoutPlan v1 output.",
                    path=("second_stage_plan_provider", request.group.section_id),
                    detail={"exception_type": type(exc).__name__},
                ),
            )
        results.append(
            _evaluate_second_stage_provider_output(
                request=request,
                plan_payload=plan_payload,
                facts=facts,
                compile_options=compile_options,
                provider_diagnostics=provider_diagnostics,
            )
        )
    return tuple(results)


def build_second_stage_layout_planning_requests(
    *,
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    compile_options: LayoutCompileOptions,
    options: SecondStagePlanningOptions | None = None,
) -> tuple[SecondStageLayoutPlanningRequest, ...]:
    opts = options or SecondStagePlanningOptions()
    groups = find_second_stage_planning_groups(plan=plan, facts=facts, options=opts)
    return tuple(
        SecondStageLayoutPlanningRequest(
            group=group,
            scoped_projection=_render_second_stage_scoped_projection(group, facts),
            graph_facts_summary=_scoped_graph_facts_summary(group, facts),
            layout_plan_schema_reminder=_LAYOUT_PLAN_SCHEMA_REMINDER_V1,
            compile_options=compile_options.to_json(),
        )
        for group in groups
    )


def find_second_stage_planning_groups(
    *,
    plan: LayoutPlanV1,
    facts: GraphInventoryFacts,
    options: SecondStagePlanningOptions | None = None,
) -> tuple[SecondStagePlanningGroup, ...]:
    opts = options or SecondStagePlanningOptions()
    if opts.max_groups <= 0:
        return ()

    groups: list[SecondStagePlanningGroup] = []
    for section in plan.sections:
        group_refs = tuple(section.nodes)
        if not group_refs:
            continue
        scopes = {ref.scope_path for ref in group_refs}
        if len(scopes) != 1:
            continue
        scope_path = next(iter(scopes))
        internal_edges, boundary_edges, boundary_refs = _section_edge_context(
            facts,
            group_refs,
            scope_path=scope_path,
        )
        density = internal_edges / max(1, len(group_refs))
        reasons: list[str] = []
        if len(group_refs) >= opts.large_group_node_count:
            reasons.append("large_group_node_count")
        if density >= opts.high_edge_density:
            reasons.append("high_edge_density")
        if _has_ambiguous_sampler_cluster(
            facts,
            group_refs,
            min_sampler_count=opts.ambiguous_sampler_count,
        ):
            reasons.append("ambiguous_multi_sampler_cluster")
        if not reasons:
            continue
        groups.append(
            SecondStagePlanningGroup(
                section_id=section.id,
                section_title=section.title,
                scope_path=scope_path,
                trigger_reasons=tuple(reasons),
                group_node_refs=tuple(sorted(group_refs, key=_ref_sort_key)),
                boundary_node_refs=tuple(sorted(boundary_refs, key=_ref_sort_key)),
                internal_edge_count=internal_edges,
                boundary_edge_count=boundary_edges,
                edge_density=round(density, 4),
            )
        )
    return tuple(
        sorted(
            groups,
            key=lambda group: (
                -len(group.trigger_reasons),
                -len(group.group_node_refs),
                -group.edge_density,
                group.section_id,
            ),
        )[: opts.max_groups]
    )


def _evaluate_second_stage_provider_output(
    *,
    request: SecondStageLayoutPlanningRequest,
    plan_payload: Any | None,
    facts: GraphInventoryFacts,
    compile_options: LayoutCompileOptions,
    provider_diagnostics: tuple[ReorganiseDiagnostic, ...],
) -> SecondStagePlanningResult:
    if provider_diagnostics:
        return SecondStagePlanningResult(
            request=request,
            provider_diagnostics=provider_diagnostics,
        )

    parse_diagnostics: tuple[Any, ...] = ()
    plan: LayoutPlanV1 | None = None
    if plan_payload is not None:
        try:
            plan = parse_layout_plan(plan_payload)
        except LayoutPlanParseError as exc:
            parse_diagnostics = exc.diagnostics
    else:
        parse_diagnostics = (
            ReorganiseDiagnostic(
                code="second_stage_missing_plan",
                message="Second-stage provider returned no LayoutPlan v1 output.",
                path=("second_stage_plan_provider", request.group.section_id),
            ),
        )

    validation_report: ReorganiseDiagnosticReport | None = None
    compile_diagnostics: tuple[ReorganiseDiagnostic, ...] = ()
    compile_ok = False
    if plan is not None:
        validation_report = validate_layout_plan(plan, facts)
        if validation_report.ok:
            compiled = compile_layout_plan(plan, facts, options=compile_options)
            compile_ok = compiled.ok
            if not compiled.ok:
                compile_diagnostics = _compile_failure_diagnostics(compiled)

    return SecondStagePlanningResult(
        request=request,
        plan=plan,
        parse_diagnostics=parse_diagnostics,
        validation_report=validation_report,
        compile_diagnostics=compile_diagnostics,
        compile_ok=compile_ok,
    )


def _section_edge_context(
    facts: GraphInventoryFacts,
    group_refs: Sequence[CanonicalNodeRef],
    *,
    scope_path: str,
) -> tuple[int, int, set[CanonicalNodeRef]]:
    group = set(group_refs)
    internal_edges = 0
    boundary_edges = 0
    boundary_refs: set[CanonicalNodeRef] = set()
    topology = _topology_for_scope(facts, scope_path)
    if topology is None:
        return 0, 0, boundary_refs
    for edge in topology.effective_edges:
        source_in = edge.source in group
        target_in = edge.target in group
        if source_in and target_in:
            internal_edges += 1
        elif source_in or target_in:
            boundary_edges += 1
            boundary_refs.add(edge.target if source_in else edge.source)
    return internal_edges, boundary_edges, boundary_refs


def _has_ambiguous_sampler_cluster(
    facts: GraphInventoryFacts,
    group_refs: Sequence[CanonicalNodeRef],
    *,
    min_sampler_count: int,
) -> bool:
    group = set(group_refs)
    sampler_count = sum(1 for ref in group if _is_sampler_ref(facts, ref))
    if sampler_count < min_sampler_count:
        return False
    for relation in facts.summary.sampler_relation_candidates:
        if relation.kind not in _AMBIGUOUS_SAMPLER_RELATION_KINDS:
            continue
        if set(relation.samplers).issubset(group):
            return True
    return False


def _render_second_stage_scoped_projection(
    group: SecondStagePlanningGroup,
    facts: GraphInventoryFacts,
) -> str:
    included_refs = set(group.group_node_refs) | set(group.boundary_node_refs)
    canonical = {fact.ref: fact for fact in facts.canonical_refs}
    furniture = {fact.ref: fact for fact in facts.node_furniture}
    topology = _topology_for_scope(facts, group.scope_path)
    label = "<root>" if group.scope_path == "" else group.scope_path
    lines = [
        "scoped_layout_reasoning_view:",
        "  contract:",
        "    kind: second_stage_intra_group_layout_facts",
        "    executable_python: false",
        "    coordinate_plan: false",
        "    refs: canonical arrays shaped [scope_path, uid]",
        "    scope_limit: complex_group_plus_boundary_nodes",
        "    runtime_mutation: forbidden",
        "  group:",
        f"    section_id: {_json(group.section_id)}",
        f"    title: {_json(group.section_title)}",
        f"    scope: {_json(label)}",
        f"    trigger_reasons: {_json(list(group.trigger_reasons))}",
        f"    group_node_refs: {_json([ref.to_json() for ref in group.group_node_refs])}",
        f"    boundary_node_refs: {_json([ref.to_json() for ref in group.boundary_node_refs])}",
        "  nodes:",
    ]
    for ref in sorted(included_refs, key=_ref_sort_key):
        fact = canonical.get(ref)
        if fact is None:
            continue
        role = "group" if ref in group.group_node_refs else "boundary"
        furniture_fact = furniture.get(ref)
        lines.append(
            "    - "
            f"ref: {_json(ref.to_json())} "
            f"role: {role} "
            f"class_type: {_json(fact.class_type)} "
            f"role_hint: {fact.role_hint} "
            f"helper: {_bool_text(fact.is_helper)}"
        )
        if furniture_fact is not None:
            lines.append(
                "      "
                f"observed_pos: {_json(_thaw_jsonish(furniture_fact.pos))} "
                f"observed_size: {_json(_thaw_jsonish(furniture_fact.size))}"
            )
    lines.append("  edges:")
    edge_lines: list[str] = []
    if topology is not None:
        for edge in sorted(topology.effective_edges, key=_edge_sort_key):
            if edge.source not in included_refs or edge.target not in included_refs:
                continue
            edge_role = (
                "internal"
                if edge.source in group.group_node_refs and edge.target in group.group_node_refs
                else "boundary"
            )
            edge_lines.append(
                "    - "
                f"role: {edge_role} "
                f"from: {_json(edge.source.to_json())}:{_json(edge.source_slot)} "
                f"to: {_json(edge.target.to_json())}:{_json(edge.target_slot)} "
                f"type: {_json(edge.socket_type)}"
            )
    lines.extend(edge_lines or ["    - none"])
    lines.append("  sampler_relation_candidates:")
    relation_lines = [
        "    - "
        f"kind: {relation.kind} "
        f"samplers: {_json([ref.to_json() for ref in relation.samplers])} "
        f"source: {_json(relation.source.to_json() if relation.source else None)} "
        f"target: {_json(relation.target.to_json() if relation.target else None)} "
        f"reason: {_json(relation.reason)}"
        for relation in facts.summary.sampler_relation_candidates
        if set(relation.samplers).issubset(included_refs)
    ]
    lines.extend(relation_lines or ["    - none"])
    return "\n".join(lines).rstrip() + "\n"


def _scoped_graph_facts_summary(
    group: SecondStagePlanningGroup,
    facts: GraphInventoryFacts,
) -> dict[str, Any]:
    included_refs = set(group.group_node_refs) | set(group.boundary_node_refs)
    canonical = [
        fact.to_json()
        for fact in sorted(facts.canonical_refs, key=lambda item: _ref_sort_key(item.ref))
        if fact.ref in included_refs
    ]
    helper_refs = [
        ref.to_json() for ref in sorted(facts.summary.helper_refs, key=_ref_sort_key)
        if ref in included_refs
    ]
    sampler_refs = [
        ref.to_json()
        for ref in sorted(
            (ref for ref in group.group_node_refs if _is_sampler_ref(facts, ref)),
            key=_ref_sort_key,
        )
    ]
    return {
        "scope_path": group.scope_path,
        "group": group.to_json(),
        "canonical_nodes": canonical,
        "scope": {
            "scope_path": group.scope_path,
            "node_count": len(included_refs),
            "group_node_count": len(group.group_node_refs),
            "boundary_node_count": len(group.boundary_node_refs),
            "internal_edge_count": group.internal_edge_count,
            "boundary_edge_count": group.boundary_edge_count,
            "helper_refs": helper_refs,
            "sampler_refs": sampler_refs,
        },
        "sampler_relation_candidates": [
            relation.to_json()
            for relation in facts.summary.sampler_relation_candidates
            if set(relation.samplers).issubset(included_refs)
        ],
        "truncated": facts.summary.truncated,
    }


def _topology_for_scope(
    facts: GraphInventoryFacts,
    scope_path: str,
) -> Any | None:
    return next(
        (topology for topology in facts.scope_topologies if topology.scope_path == scope_path),
        None,
    )


def _is_sampler_ref(facts: GraphInventoryFacts, ref: CanonicalNodeRef) -> bool:
    for fact in facts.canonical_refs:
        if fact.ref == ref:
            return "sampler" in fact.class_type.lower()
    return False


def _edge_sort_key(edge: Any) -> tuple[Any, ...]:
    return (
        _ref_sort_key(edge.source),
        str(edge.source_slot),
        _ref_sort_key(edge.target),
        str(edge.target_slot),
        str(edge.link_id),
    )


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _small_wrapper_node_only_fallback_options(
    facts: GraphInventoryFacts,
    options: LayoutCompileOptions,
) -> LayoutCompileOptions | None:
    if options.grouping_policy != "auto":
        return None
    node_count = len(facts.canonical_refs)
    root_node_count = next(
        (scope.node_count for scope in facts.summary.scopes if scope.scope_path == ""),
        node_count,
    )
    nested_scope_count = sum(1 for scope in facts.summary.scopes if scope.scope_path)
    if not nested_scope_count or root_node_count > 12:
        return None
    return LayoutCompileOptions(
        spacing_preset=options.spacing_preset,
        existing_group_policy=options.existing_group_policy,
        grouping_policy="none",
        force_regroup=options.force_regroup,
        pinned_refs=options.pinned_refs,
        preserve_node_sizes=options.preserve_node_sizes,
        minimize_setget_helpers=options.minimize_setget_helpers,
    )


def _compile_failure_diagnostics(
    compile_result: LayoutCompileResult,
) -> tuple[ReorganiseDiagnostic, ...]:
    diagnostics = tuple(
        diagnostic
        for diagnostic in compile_result.diagnostics
        if isinstance(diagnostic, ReorganiseDiagnostic)
    )
    if diagnostics:
        return diagnostics
    report = compile_result.report
    verdict = getattr(report, "verdict", None)
    return (
        ReorganiseDiagnostic(
            code="layout_compile_failed",
            message="LayoutPlan v1 did not pass compile gates.",
            detail={"report_verdict": verdict} if verdict is not None else {},
        ),
    )


def apply_layout_candidate_patch_to_ui(
    ui_json_or_path: Mapping[str, Any] | str | PathLike[str],
    candidate_patch: Mapping[str, Any] | LayoutCandidatePatch,
    *,
    require_structural_noop: bool = True,
) -> ReorganisePatchApplyResult:
    loaded = load_reorganise_ui_json(ui_json_or_path)
    patch = _candidate_patch_mapping(candidate_patch)
    structural_hash_before = structural_hash_for_layout_facts(
        extract_graph_facts(loaded.ui_json)
    )

    ledger = EditLedger.ingest(loaded.ui_json)
    graph = ledger.graph
    applied_entry_keys, skipped_entry_keys = _apply_candidate_entries(ledger, patch)
    applied_group_scopes = _apply_candidate_groups(ledger, patch)
    _apply_root_furniture_sections(graph, patch)

    structural_hash_after = structural_hash_for_layout_facts(extract_graph_facts(graph))
    layout_only_structural_noop = structural_hash_before == structural_hash_after
    if require_structural_noop and not layout_only_structural_noop:
        raise ValueError(
            "layout candidate patch changed workflow structure: "
            f"{structural_hash_before} != {structural_hash_after}"
        )

    return ReorganisePatchApplyResult(
        ui_json=graph,
        candidate_patch_sha256=_sha256(patch),
        structural_hash_before=structural_hash_before,
        structural_hash_after=structural_hash_after,
        layout_only_structural_noop=layout_only_structural_noop,
        applied_entry_keys=tuple(applied_entry_keys),
        skipped_entry_keys=tuple(skipped_entry_keys),
        applied_group_scopes=tuple(applied_group_scopes),
    )


def build_deterministic_layout_plan(facts: GraphInventoryFacts) -> LayoutPlanV1:
    classification = classify_layout_facts(facts)
    hints = {hint.ref: hint for hint in classification.hints}
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}
    helper_refs = {fact.ref for fact in facts.canonical_refs if fact.is_helper}
    container_parent_by_scope = _container_parent_sections(facts)
    container_refs = {section.nodes[0] for section in container_parent_by_scope.values() if section.nodes}

    refs_by_section: dict[str, list[CanonicalNodeRef]] = {}
    section_kind_by_id: dict[str, SectionKind] = {}
    section_role_by_id: dict[str, RoleHint | None] = {}
    section_parent_by_id: dict[str, str | None] = {}
    section_scope_by_id: dict[str, str] = {}

    for section in container_parent_by_scope.values():
        refs_by_section.setdefault(section.id, []).extend(section.nodes)
        section_kind_by_id[section.id] = section.kind
        section_role_by_id[section.id] = section.role_hint
        section_parent_by_id[section.id] = section.parent_id
        section_scope_by_id[section.id] = section.nodes[0].scope_path if section.nodes else ""

    for fact in sorted(facts.canonical_refs, key=lambda item: _ref_sort_key(item.ref)):
        if fact.ref in helper_refs or fact.ref in container_refs:
            continue
        role_hint = _effective_role(fact.ref, canonical_by_ref, hints)
        kind = _ROLE_TO_SECTION_KIND[role_hint]
        section_id = _section_id(fact.ref.scope_path, kind)
        refs_by_section.setdefault(section_id, []).append(fact.ref)
        section_kind_by_id.setdefault(section_id, kind)
        section_role_by_id.setdefault(section_id, role_hint)
        section_parent_by_id.setdefault(
            section_id,
            container_parent_by_scope.get(fact.ref.scope_path, None).id
            if fact.ref.scope_path in container_parent_by_scope
            else None,
        )
        section_scope_by_id.setdefault(section_id, fact.ref.scope_path)

    helper_placements: list[HelperPlacement] = []
    for ref in sorted(helper_refs, key=_ref_sort_key):
        section_id = _helper_section_id_for_scope(
            ref.scope_path,
            refs_by_section,
            section_kind_by_id,
            section_role_by_id,
            section_parent_by_id,
            section_scope_by_id,
            container_parent_by_scope,
        )
        helper_placements.append(
            HelperPlacement(
                helper=ref,
                kind=HELPER_PLACEMENT_INSIDE_SECTION,
                section_id=section_id,
            )
        )

    sections = [
        LayoutSection(
            id=section_id,
            kind=section_kind_by_id[section_id],
            nodes=tuple(sorted(refs_by_section.get(section_id, ()), key=_ref_sort_key)),
            title=_section_title(section_scope_by_id.get(section_id, ""), section_kind_by_id[section_id]),
            role_hint=section_role_by_id.get(section_id),
            parent_id=section_parent_by_id.get(section_id),
        )
        for section_id in sorted(
            section_kind_by_id,
            key=lambda item: (
                _scope_sort_key(section_scope_by_id.get(item, "")),
                _SECTION_ORDER.get(section_kind_by_id[item], 999),
                item,
            ),
        )
    ]
    plan = LayoutPlanV1(
        sections=tuple(sections),
        helper_placements=tuple(helper_placements),
        sampler_relations=facts.summary.sampler_relation_candidates,
        unassigned_policy=UNASSIGNED_REJECT,
        notes="Deterministic baseline generated from graph facts and role classification.",
    )
    return parse_layout_plan(plan.to_json())


def _candidate_patch_mapping(
    candidate_patch: Mapping[str, Any] | LayoutCandidatePatch,
) -> dict[str, Any]:
    if isinstance(candidate_patch, LayoutCandidatePatch):
        return candidate_patch.to_json()
    if not isinstance(candidate_patch, Mapping):
        raise TypeError("candidate_patch must be a mapping or LayoutCandidatePatch")
    return _freeze_jsonish(candidate_patch)


def _apply_candidate_entries(
    ledger: EditLedger,
    patch: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    raw_entries = patch.get("entries")
    entries = raw_entries if isinstance(raw_entries, Mapping) else {}
    applied: list[str] = []
    skipped: list[str] = []
    for raw_key, raw_entry in sorted(entries.items(), key=lambda item: str(item[0])):
        key = str(raw_key)
        if not isinstance(raw_entry, Mapping):
            skipped.append(key)
            continue
        scope_path, uid = parse_uid(key)
        node = ledger.resolve_node(scope_path, uid)
        if node is None:
            skipped.append(key)
            continue
        _apply_node_furniture_entry(node, raw_entry)
        applied.append(key)
    return applied, skipped


def _apply_node_furniture_entry(node: dict[str, Any], entry: Mapping[str, Any]) -> None:
    for key in _PATCH_ENTRY_KEYS:
        if key not in entry:
            continue
        if key == "properties":
            _apply_node_properties(node, entry.get(key))
            continue
        node[key] = _freeze_jsonish(entry.get(key))


def _apply_node_properties(node: dict[str, Any], value: Any) -> None:
    if not isinstance(value, Mapping):
        return
    existing = node.get("properties")
    existing_props = existing if isinstance(existing, dict) else {}
    patched = _freeze_jsonish(value)
    patched_props = patched if isinstance(patched, dict) else {}
    existing_uid = existing_props.get("vibecomfy_uid")
    if existing_uid is not None:
        patched_props["vibecomfy_uid"] = existing_uid
    node["properties"] = patched_props


def _apply_candidate_groups(
    ledger: EditLedger,
    patch: Mapping[str, Any],
) -> list[str]:
    raw_groups = patch.get("groups")
    if not isinstance(raw_groups, Sequence) or isinstance(raw_groups, (str, bytes)):
        return []

    groups_by_scope: dict[str, list[dict[str, Any]]] = {}
    for raw_group in raw_groups:
        if not isinstance(raw_group, Mapping):
            continue
        scope_path = _candidate_group_scope(raw_group)
        ui_group = _group_for_ui_scope(raw_group, scope_path, ledger)
        groups_by_scope.setdefault(scope_path, []).append(ui_group)

    applied: list[str] = []
    for scope_path, groups in sorted(groups_by_scope.items(), key=lambda item: _scope_sort_key(item[0])):
        scope = ledger.scopes.get(scope_path)
        if scope is None:
            continue
        scope.graph["groups"] = groups
        applied.append(scope_path)
    return applied


def _candidate_group_scope(group: Mapping[str, Any]) -> str:
    nodes = group.get("nodes")
    node_keys = nodes if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes)) else ()
    scopes = {parse_uid(str(node_key))[0] for node_key in node_keys}
    return scopes.pop() if len(scopes) == 1 else ""


def _group_for_ui_scope(
    group: Mapping[str, Any],
    scope_path: str,
    ledger: EditLedger,
) -> dict[str, Any]:
    ui_group = _freeze_jsonish(group)
    if not isinstance(ui_group, dict):
        ui_group = {}
    nodes = group.get("nodes")
    node_keys = nodes if isinstance(nodes, Sequence) and not isinstance(nodes, (str, bytes)) else ()
    ui_nodes: list[Any] = []
    for node_key in node_keys:
        node_scope, uid = parse_uid(str(node_key))
        if node_scope != scope_path:
            continue
        node = ledger.resolve_node(node_scope, uid)
        if node is None:
            continue
        ui_nodes.append(node.get("id", uid))
    ui_group["nodes"] = ui_nodes
    return ui_group


def _apply_root_furniture_sections(
    graph: dict[str, Any],
    patch: Mapping[str, Any],
) -> None:
    if isinstance(patch.get("extra"), Mapping):
        graph["extra"] = _freeze_jsonish(patch["extra"])
    elif "extra" in patch:
        graph["extra"] = {}

    if "virtual_wires" in patch:
        extra = graph.get("extra")
        extra_dict = extra if isinstance(extra, dict) else {}
        if isinstance(patch.get("virtual_wires"), Mapping) and patch.get("virtual_wires"):
            extra_dict["virtual_wires"] = _freeze_jsonish(patch["virtual_wires"])
        else:
            extra_dict.pop("virtual_wires", None)
        graph["extra"] = extra_dict

    if "lastRerouteId" in patch:
        if patch.get("lastRerouteId") is None:
            graph.pop("lastRerouteId", None)
        else:
            graph["lastRerouteId"] = _freeze_jsonish(patch["lastRerouteId"])


def _container_parent_sections(facts: GraphInventoryFacts) -> dict[str, LayoutSection]:
    by_parent_scope: dict[str, list[Any]] = {}
    for fact in facts.canonical_refs:
        if _is_subgraph_container_class(fact.class_type):
            by_parent_scope.setdefault(fact.ref.scope_path, []).append(fact)
    subgraph_id_by_scope = _subgraph_definition_id_by_scope(facts)
    canonical_by_ref = {fact.ref: fact for fact in facts.canonical_refs}

    result: dict[str, LayoutSection] = {}
    for scope in sorted(
        (scope.scope_path for scope in facts.summary.scopes if scope.scope_path),
        key=_scope_sort_key,
    ):
        parent_scope = _parent_scope(scope)
        candidates = sorted(by_parent_scope.get(parent_scope, ()), key=lambda item: _ref_sort_key(item.ref))
        definition_id = subgraph_id_by_scope.get(scope)
        if definition_id:
            explicit = tuple(
                fact
                for fact in sorted(facts.canonical_refs, key=lambda item: _ref_sort_key(item.ref))
                if fact.ref.scope_path == parent_scope and fact.class_type == definition_id
            )
            if explicit:
                candidates = list(explicit)
        if not candidates:
            fallback_refs = _uuid_like_subgraph_container_refs(facts, parent_scope)
            child_scopes = sorted(
                (
                    item.scope_path
                    for item in facts.summary.scopes
                    if item.scope_path and _parent_scope(item.scope_path) == parent_scope
                ),
                key=_scope_sort_key,
            )
            if scope in child_scopes:
                index = child_scopes.index(scope)
                if index < len(fallback_refs):
                    fact = canonical_by_ref.get(fallback_refs[index])
                    if fact is not None:
                        candidates = [fact]
        if not candidates:
            continue
        container_ref = candidates[0].ref
        result[scope] = LayoutSection(
            id=_section_id(parent_scope, SECTION_KIND_CONTAINER, suffix=container_ref.uid),
            kind=SECTION_KIND_CONTAINER,
            nodes=(container_ref,),
            title=_section_title(parent_scope, SECTION_KIND_CONTAINER),
            role_hint=ROLE_HINT_SUBGRAPH_CONTAINER,
        )
    return result


def _subgraph_definition_id_by_scope(facts: GraphInventoryFacts) -> dict[str, str]:
    definitions = facts.sidecar_envelope.get("definitions")
    rows: dict[str, str] = {}
    for definition in _iter_subgraph_definitions(definitions):
        name = definition.get("name")
        definition_id = definition.get("id")
        if isinstance(name, str) and isinstance(definition_id, str):
            rows[name] = definition_id
    result: dict[str, str] = {}
    for scope in facts.summary.scopes:
        if not scope.scope_path:
            continue
        scope_name = scope.scope_path.rsplit(":", 1)[0]
        definition_id = rows.get(scope_name)
        if definition_id:
            result[scope.scope_path] = definition_id
    return result


def _iter_subgraph_definitions(definitions: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(definitions, Mapping):
        subgraphs = definitions.get("subgraphs")
        if isinstance(subgraphs, Sequence) and not isinstance(subgraphs, (str, bytes)):
            return tuple(item for item in subgraphs if isinstance(item, Mapping))
        if isinstance(definitions.get("nodes"), Sequence):
            return (definitions,)
        return tuple(item for item in definitions.values() if isinstance(item, Mapping))
    if isinstance(definitions, Sequence) and not isinstance(definitions, (str, bytes)):
        return tuple(item for item in definitions if isinstance(item, Mapping))
    return ()


def _uuid_like_subgraph_container_refs(
    facts: GraphInventoryFacts,
    parent_scope: str,
) -> tuple[CanonicalNodeRef, ...]:
    return tuple(
        fact.ref
        for fact in sorted(facts.canonical_refs, key=lambda item: _ref_sort_key(item.ref))
        if fact.ref.scope_path == parent_scope and _looks_like_uuid(fact.class_type)
    )


def _looks_like_uuid(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value))


def _effective_role(ref: CanonicalNodeRef, canonical_by_ref: Mapping[CanonicalNodeRef, Any], hints: Mapping[CanonicalNodeRef, Any]) -> RoleHint:
    fact = canonical_by_ref.get(ref)
    if fact is not None and _is_subgraph_container_class(fact.class_type):
        return ROLE_HINT_SUBGRAPH_CONTAINER
    hint = hints.get(ref)
    if hint is not None:
        return hint.role_hint
    if fact is not None:
        return fact.role_hint
    return ROLE_HINT_UNKNOWN


def _helper_section_id_for_scope(
    scope_path: str,
    refs_by_section: dict[str, list[CanonicalNodeRef]],
    section_kind_by_id: dict[str, SectionKind],
    section_role_by_id: dict[str, RoleHint | None],
    section_parent_by_id: dict[str, str | None],
    section_scope_by_id: dict[str, str],
    container_parent_by_scope: Mapping[str, LayoutSection],
) -> str:
    section_ids = [
        section_id
        for section_id, section_scope in section_scope_by_id.items()
        if section_scope == scope_path
    ]
    if section_ids:
        return sorted(
            section_ids,
            key=lambda item: (_SECTION_ORDER.get(section_kind_by_id[item], 999), item),
        )[0]

    section_id = _section_id(scope_path, SECTION_KIND_UTILITY)
    refs_by_section.setdefault(section_id, [])
    section_kind_by_id[section_id] = SECTION_KIND_UTILITY
    section_role_by_id[section_id] = ROLE_HINT_UTILITY
    section_parent_by_id[section_id] = (
        container_parent_by_scope[scope_path].id
        if scope_path in container_parent_by_scope
        else None
    )
    section_scope_by_id[section_id] = scope_path
    return section_id


def _is_subgraph_container_class(class_type: str) -> bool:
    lowered = class_type.lower()
    return "subgraph" in lowered or lowered.endswith("container") or "container" in lowered


def _parent_scope(scope_path: str) -> str:
    if SCOPE_CHAIN_JOIN not in scope_path:
        return ""
    return scope_path.rsplit(SCOPE_CHAIN_JOIN, 1)[0]


def _section_id(scope_path: str, kind: SectionKind, *, suffix: str | None = None) -> str:
    label = "root" if not scope_path else _slug(scope_path)
    parts = [label, kind]
    if suffix:
        parts.append(_slug(suffix))
    return "__".join(parts)


def _section_title(scope_path: str, kind: SectionKind) -> str:
    prefix = "" if not scope_path else f"{scope_path} "
    return f"{prefix}{_SECTION_TITLES.get(kind, kind.title())}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()
    return slug or "root"


def _scope_sort_key(scope_path: str) -> tuple[int, str]:
    return (0, "") if scope_path == "" else (1, scope_path)


def _ref_sort_key(ref: CanonicalNodeRef) -> tuple[int, str, str]:
    return (0 if ref.scope_path == "" else 1, ref.scope_path, ref.uid)


orchestrate_reorganise_preview = preview_reorganise_workflow
prepare_reorganise_preview = preview_reorganise_workflow
build_baseline_layout_plan = build_deterministic_layout_plan


__all__ = [
    "PlanSource",
    "ReorganiseApplyData",
    "ReorganiseAssessmentResult",
    "ReorganiseLoadedWorkflow",
    "ReorganisePatchApplyResult",
    "ReorganisePreviewOptions",
    "ReorganisePreviewResult",
    "SecondStageLayoutPlanProvider",
    "SecondStageLayoutPlanningRequest",
    "SecondStagePlanningGroup",
    "SecondStagePlanningOptions",
    "SecondStagePlanningResult",
    "SemanticLayoutPlanProvider",
    "SemanticLayoutPlanningRequest",
    "assess_reorganise_workflow",
    "apply_layout_candidate_patch_to_ui",
    "build_baseline_layout_plan",
    "build_deterministic_layout_plan",
    "build_or_preserve_layout_sidecar",
    "build_semantic_layout_planning_request",
    "build_second_stage_layout_planning_requests",
    "find_second_stage_planning_groups",
    "load_layout_sidecar_envelope",
    "load_reorganise_ui_json",
    "orchestrate_reorganise_preview",
    "prepare_reorganise_preview",
    "preview_reorganise_workflow",
    "run_second_stage_intra_group_planning",
]
