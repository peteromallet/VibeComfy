"""Case state machine for demo_factory.

SELECTED→BASELINE_PROVING→BASELINE_PROVEN→MUTATING→FAULT_PROVEN→
FIXER_RUNNING→EVALUATING→terminal verdict.

Case IDs are opaque random identifiers (never encode the workflow, fault family,
locus, or expected repair) so nothing leaks to the fixer model.
"""
from __future__ import annotations

from vibecomfy.ingest.normalize import door_get_nodes
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from vibecomfy.demo_factory.baseline import (
    run_baseline,
    structural_check_graph,
    write_baseline_proof,
)
from vibecomfy.demo_factory.deltas import (
    FaultInjection,
    derive_repair_delta,
    inject_final_output_bypass_fault,
    inject_conditioning_swap_fault,
    inject_vae_output_bypass_fault,
    inject_latent_source_swap_fault,
    inject_wrong_output_slot_fault,
    inject_prompt_not_wired_fault,
    inject_disabled_control_preprocessor_fault,
    inject_denoise_too_high_fault,
    inject_cfg_too_high_fault,
    inject_steps_too_low_fault,
    inject_resolution_wrong_fault,
    inject_fps_framecount_desync_fault,
)
from vibecomfy.demo_factory.fixer import run_headless_fixer
from vibecomfy.demo_factory.inquiry import (
    author_synthetic_inquiry,
    check_leakage,
    write_leakage_check,
)
from vibecomfy.demo_factory.oracle import Oracle, OracleResult, Verdict


_FAILURE_FINGERPRINT_CODES = frozenset({
    "CLASSIFY_NO_RESEARCH",
    "SYNTHESIS_SEMANTIC_MISS",
    "SYNTHESIS_UNRESOLVABLE_CLASS",
    "GRAPH_DROPPED_STRUCTURAL",
    "TOPOLOGY_NOT_FORWARDED",
    "DEPENDENCY_UI_ONLY_BLOCKER",
})


def _read_attempt_json(attempt_dir: Path, name: str) -> dict[str, Any]:
    path = attempt_dir / name
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _walk_json(value: Any):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _json_contains_key(value: Any, key: str) -> bool:
    return any(
        isinstance(item, dict) and key in item
        for item in _walk_json(value)
    )


def _failure_fingerprint(
    attempt_dir: Path,
    *,
    fixer_failed: bool,
) -> dict[str, Any]:
    """Build a cheap lineage fingerprint from emitted attempt artifacts only."""
    classification = _read_attempt_json(attempt_dir, "classification.json")
    research = _read_attempt_json(attempt_dir, "research.json")
    implementation_payload = _read_attempt_json(
        attempt_dir,
        "implementation_payload.json",
    )
    request_payload = _read_attempt_json(attempt_dir, "request.json")
    dependency = _read_attempt_json(attempt_dir, "dependency_preflight.json")
    response = _read_attempt_json(attempt_dir, "response.json")
    implementation = _read_attempt_json(attempt_dir, "implementation_result.json")

    adaptation_plan = research.get("adaptation_plan")
    if not isinstance(adaptation_plan, dict):
        adaptation_plan = {}
    warnings = adaptation_plan.get("warnings")
    warning_records = [
        item for item in (warnings if isinstance(warnings, list) else [])
        if isinstance(item, dict)
    ]
    warning_codes = {
        str(item.get("code") or "")
        for item in warning_records
    }
    unresolved = sorted({
        str(class_type)
        for item in warning_records
        for class_type in (
            item.get("unresolved_class_types")
            if isinstance(item.get("unresolved_class_types"), list)
            else []
        )
        if str(class_type).strip()
    })

    clarify_dead_end = (
        classification.get("route") == "clarify"
        and classification.get("research") is not True
    )
    clarify_fallback = (
        "Headless additive repair cannot answer a clarification"
        in str(classification.get("plan_summary") or "")
    )
    clarify_blocked = clarify_dead_end or clarify_fallback
    structural_dropped = adaptation_plan.get("structural_validation") == "fail"
    semantic_miss = (
        adaptation_plan.get("semantic_validation") == "fail"
        or "synthesis_semantic_miss" in warning_codes
    )
    unresolvable = (
        bool(unresolved)
        or "synthesis_unresolvable_class" in warning_codes
    )
    candidate_in_research = isinstance(
        adaptation_plan.get("candidate_graph"),
        dict,
    )

    payloads = (request_payload, implementation_payload)
    topology_manifest = any(
        _json_contains_key(payload, "topology_manifest")
        for payload in payloads
    )
    candidate_forwarded = any(
        _json_contains_key(payload, "candidate_graph")
        for payload in payloads
    )
    if topology_manifest:
        consumption_mode = "topology_manifest"
    elif candidate_forwarded:
        consumption_mode = "dependency_only"
    else:
        consumption_mode = "none"

    unresolved_preflight = dependency.get("unresolved_runtime_classes")
    if not isinstance(unresolved_preflight, list):
        unresolved_preflight = []
    ignored_ui = dependency.get("ignored_ui_annotation_classes")
    if not isinstance(ignored_ui, list):
        ignored_ui = []
    # Backward-compatible inference for attempts produced before the explicit
    # dependency_preflight artifact existed.
    combined_result = {"response": response, "implementation": implementation}
    if not unresolved_preflight:
        for item in _walk_json(combined_result):
            if isinstance(item, dict):
                raw = item.get("missing_runtime_classes")
                if isinstance(raw, list):
                    unresolved_preflight = raw
                    break
    from vibecomfy.executor.contracts import is_ui_only_annotation_class_type

    ui_only_blocker = bool(unresolved_preflight) and all(
        is_ui_only_annotation_class_type(value)
        for value in unresolved_preflight
    )
    dependency_failed = bool(unresolved_preflight)
    rerearched = dependency.get("retrying_synthesis") is True

    lineage_events = [
        {
            "event": "clarify_route_blocked_research",
            "count": int(clarify_blocked),
        },
        {
            "event": "candidate_graph_dropped",
            "count": int(structural_dropped or semantic_miss or unresolvable),
            "structural_validation": adaptation_plan.get("structural_validation"),
            "semantic_validation": adaptation_plan.get("semantic_validation"),
        },
        {
            "event": "candidate_graph_consumption_mode",
            "count": 1,
            "mode": consumption_mode,
        },
        {
            "event": "fixer_re_researched_after_synthesis",
            "count": int(rerearched),
        },
        {
            "event": "dependency_preflight_failed",
            "count": int(dependency_failed),
            "unresolved_count": len(unresolved_preflight),
            "ui_annotation_ignored_count": len(ignored_ui),
        },
    ]

    primary: str | None = None
    if fixer_failed:
        if clarify_dead_end:
            primary = "CLASSIFY_NO_RESEARCH"
        elif unresolvable:
            primary = "SYNTHESIS_UNRESOLVABLE_CLASS"
        elif semantic_miss:
            primary = "SYNTHESIS_SEMANTIC_MISS"
        elif structural_dropped:
            primary = "GRAPH_DROPPED_STRUCTURAL"
        elif ui_only_blocker:
            primary = "DEPENDENCY_UI_ONLY_BLOCKER"
        elif candidate_in_research and consumption_mode != "topology_manifest":
            primary = "TOPOLOGY_NOT_FORWARDED"
    assert primary is None or primary in _FAILURE_FINGERPRINT_CODES
    return {
        "version": 1,
        "primary_reason_code": primary,
        "lineage_events": lineage_events,
    }


def _write_failure_fingerprint(case: "Case", fixer_result: Any) -> None:
    if case.case_dir is None or case.source != "multinode":
        return
    attempt_dir = case.case_dir / "attempts" / f"{case.attempt:03d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = _failure_fingerprint(
        attempt_dir,
        fixer_failed=not fixer_result.ok or fixer_result.candidate is None,
    )
    (attempt_dir / "failure_fingerprint.json").write_text(
        json.dumps(fingerprint, indent=2) + "\n",
        encoding="utf-8",
    )
    primary = fingerprint.get("primary_reason_code")
    if isinstance(primary, str):
        case.failure_fingerprint_primary = primary
        case.failure_fingerprint_counts[primary] = (
            case.failure_fingerprint_counts.get(primary, 0) + 1
        )


class CaseStage(Enum):
    """Case execution stages."""
    SELECTED = "selected"
    BASELINE_PROVING = "baseline_proving"
    BASELINE_PROVEN = "baseline_proven"
    MUTATING = "mutating"
    FAULT_PROVEN = "fault_proven"
    FIXER_RUNNING = "fixer_running"
    EVALUATING = "evaluating"
    COMPLETE = "complete"
    BASELINE_REJECTED = "baseline_rejected"
    REPAIR_FAILED = "repair_failed"
    INFRA_BLOCKED = "infra_blocked"


@dataclass
class CaseReceipt:
    """Immutable stage receipt written before advancing."""
    stage: CaseStage
    timestamp: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Case:
    """A single demo scenario case with state machine."""
    case_id: str
    stage: CaseStage = CaseStage.SELECTED
    case_dir: Path | None = None
    golden: dict[str, Any] | None = None
    broken: dict[str, Any] | None = None
    inquiry: str = ""
    injection: FaultInjection | None = None
    receipts: list[CaseReceipt] = field(default_factory=list)
    attempt: int = 1
    verdict: Verdict | None = None
    oracle_result: OracleResult | None = None
    source: str = "unknown"
    fault_family: str | None = None
    failure_fingerprint_primary: str | None = None
    failure_fingerprint_counts: dict[str, int] = field(default_factory=dict)

    def _write_receipt(self, stage: CaseStage, data: dict[str, Any]) -> None:
        receipt = CaseReceipt(stage=stage, timestamp=_timestamp(), data=data)
        self.receipts.append(receipt)
        if self.case_dir:
            receipt_dir = self.case_dir / "receipts"
            receipt_dir.mkdir(parents=True, exist_ok=True)
            (receipt_dir / f"{self.attempt:03d}_{stage.value}.json").write_text(
                json.dumps(
                    {"stage": stage.value, "timestamp": receipt.timestamp, "data": data},
                    indent=2,
                ),
                encoding="utf-8",
            )

    def advance_stage(self, new_stage: CaseStage, data: dict[str, Any] | None = None) -> None:
        self._write_receipt(new_stage, data or {})
        self.stage = new_stage

    def status_file_path(self) -> Path:
        if self.case_dir is None:
            raise ValueError("Case has no case_dir")
        return self.case_dir / "status.json"

    def write_status(self) -> None:
        if self.case_dir is None:
            return
        self.status_file_path().write_text(
            json.dumps(
                {
                    "case_id": self.case_id,
                    "stage": self.stage.value,
                    "attempt": self.attempt,
                    "verdict": self.verdict.value if self.verdict else None,
                    "inquiry": self.inquiry,
                    "source": self.source,
                    "fault_family": self.fault_family,
                    "failure_fingerprint": {
                        "primary_code": self.failure_fingerprint_primary,
                        "counts": dict(sorted(self.failure_fingerprint_counts.items())),
                    },
                    "timestamp": _timestamp(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def write_graph_artifacts(self) -> None:
        """Persist golden/broken UI graphs to the runbook layout."""
        if self.case_dir is None:
            return
        if self.golden is not None:
            d = self.case_dir / "source"
            d.mkdir(parents=True, exist_ok=True)
            (d / "golden.ui.json").write_text(json.dumps(self.golden, indent=2), encoding="utf-8")
        if self.broken is not None:
            d = self.case_dir / "broken"
            d.mkdir(parents=True, exist_ok=True)
            (d / "broken.ui.json").write_text(json.dumps(self.broken, indent=2), encoding="utf-8")

    @classmethod
    def from_status(cls, case_dir: Path) -> "Case":
        status_file = case_dir / "status.json"
        if not status_file.is_file():
            raise FileNotFoundError(f"No status.json in {case_dir}")
        sd = json.loads(status_file.read_text(encoding="utf-8"))
        return cls(
            case_id=sd["case_id"],
            stage=CaseStage(sd["stage"]),
            case_dir=case_dir,
            attempt=sd.get("attempt", 1),
            verdict=Verdict(sd["verdict"]) if sd.get("verdict") else None,
            inquiry=sd.get("inquiry", ""),
            source=sd.get("source", "unknown"),
            fault_family=sd.get("fault_family"),
            failure_fingerprint_primary=(
                sd.get("failure_fingerprint", {}).get("primary_code")
                if isinstance(sd.get("failure_fingerprint"), dict)
                else None
            ),
            failure_fingerprint_counts=(
                dict(sd.get("failure_fingerprint", {}).get("counts") or {})
                if isinstance(sd.get("failure_fingerprint"), dict)
                else {}
            ),
        )


def _new_case_id() -> str:
    """Opaque random case id (no encoded semantics)."""
    return uuid.uuid4().hex[:12]


def _cases_dir(output_base: Path | str) -> Path:
    d = Path(output_base) / "cases"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_fixer(case: Case, broken: dict[str, Any], inquiry: str, attempt_dir: Path | None = None, *, additive: bool = False) -> Any:
    # The live-agentic harness builds its evidence dir as
    # ``output_base / tag / scenario_id``. To get a FLAT ``case_dir/attempts/<N>/``
    # layout (not ``case_dir/attempts/<N>/attempts/<N>/``), pass the CASE dir as
    # the base and let the harness append ``attempts/<N>`` itself. The harness
    # returns the real output_dir, which ``_load_candidate`` reads from.
    output_base = case.case_dir if case.case_dir is not None else attempt_dir
    return run_headless_fixer(
        broken=broken,
        inquiry=inquiry,
        output_base=output_base,
        tag="attempts",
        scenario_id=f"{case.attempt:03d}",
        additive=additive,
    )


def _baseline_gate(case: Case, golden: dict[str, Any], case_dir: Path) -> bool:
    case.advance_stage(CaseStage.BASELINE_PROVING)
    result = run_baseline(golden)
    write_baseline_proof(result, case_dir)
    if not result.passed:
        case.advance_stage(
            CaseStage.BASELINE_REJECTED,
            {"reason": result.compile_error or "baseline failed"},
        )
        case.verdict = Verdict.BASELINE_REJECTED
        case.write_graph_artifacts()
        case.write_status()
        return False
    case.advance_stage(
        CaseStage.BASELINE_PROVEN,
        {"node_count": result.node_count, "link_count": result.link_count},
    )
    return True


def _fixer_gate(case: Case, fixer_result: Any) -> bool:
    _write_failure_fingerprint(case, fixer_result)
    if fixer_result.infra_blocked:
        case.advance_stage(CaseStage.INFRA_BLOCKED, {"error": fixer_result.error})
        case.verdict = Verdict.INFRA_BLOCKED
        case.write_status()
        return False
    if not fixer_result.ok or fixer_result.candidate is None:
        case.advance_stage(
            CaseStage.REPAIR_FAILED,
            {"error": fixer_result.error or "fixer failed", "status": fixer_result.status},
        )
        case.verdict = Verdict.FIXER_FAILED
        case.write_status()
        return False
    return True


def _evaluate(case: Case, candidate: dict[str, Any]) -> Case:
    case.advance_stage(CaseStage.EVALUATING)

    pre_existing_types = {
        str(node.get("type"))
        for graph in (case.golden, case.broken)
        if isinstance(graph, dict)
        for node in door_get_nodes(graph, [])
        if isinstance(node, dict) and str(node.get("type") or "").strip()
    }
    structural = structural_check_graph(
        candidate,
        pre_existing_types=pre_existing_types,
    )
    cand_ok = bool(structural["structural_safe"])
    cand_output_reachable = bool(structural["output_reachable"])
    hard_blockers = structural["hard_blockers"]
    cand_err = (
        "; ".join(
            f"{item.get('code', 'structural_blocker')}: "
            f"{json.dumps(item.get('detail') or {}, sort_keys=True, default=str)}"
            for item in hard_blockers[:3]
        )
        if hard_blockers
        else None
    )

    oracle = Oracle(
        fault_predicate=case.injection.fault_predicate,
        repaired_predicate=case.injection.repaired_predicate,
        broken=case.broken,
        golden=case.golden,
    )
    oracle_result = oracle.evaluate(
        candidate=candidate,
        execution_safe=cand_ok,
        compile_error=cand_err,
        output_reachable=cand_output_reachable,
    )

    case.oracle_result = oracle_result
    case.verdict = oracle_result.verdict
    case.advance_stage(
        CaseStage.COMPLETE,
        {
            "verdict": oracle_result.verdict.value,
            "gates_passed": sum(1 for g in oracle_result.gates if g.passed),
            "gates_total": len(oracle_result.gates),
            "candidate_execution_safe": cand_ok,
            "candidate_output_reachable": cand_output_reachable,
            "candidate_compile_error": cand_err,
            "candidate_schema_unavailable_classes": structural[
                "schema_unavailable_classes"
            ],
            "candidate_fixer_introduced_schema_unavailable_classes": structural[
                "fixer_introduced_schema_unavailable_classes"
            ],
        },
    )
    case.write_status()
    return case


def run_transcript_case(
    transcript_run_dir: Path,
    output_base: Path,
    tag: str = "demo-factory",
) -> Case:
    """Run a transcript-derived case through the state machine."""
    from vibecomfy.demo_factory.transcript import load_transcript_run_dir

    transcript = load_transcript_run_dir(transcript_run_dir)

    case_id = _new_case_id()
    case_dir = _cases_dir(output_base) / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    case = Case(
        case_id=case_id,
        case_dir=case_dir,
        golden=transcript.golden,
        broken=transcript.broken,
        inquiry=transcript.inquiry,
        source="transcript",
        fault_family=None,
    )

    case.advance_stage(
        CaseStage.SELECTED,
        {"source": "transcript", "transcript_dir": str(transcript_run_dir)},
    )

    if not _baseline_gate(case, transcript.golden, case_dir):
        return case

    case.advance_stage(CaseStage.MUTATING)
    injection = derive_repair_delta(transcript.broken, transcript.golden)
    case.injection = injection
    case.write_graph_artifacts()
    case.advance_stage(CaseStage.FAULT_PROVEN, {"repair_ops_count": len(injection.repair_delta)})

    case.advance_stage(CaseStage.FIXER_RUNNING)
    fixer_result = _run_fixer(case, transcript.broken, transcript.inquiry)
    if not _fixer_gate(case, fixer_result):
        return case

    leakage = check_leakage(transcript.inquiry)
    write_leakage_check(leakage, case_dir)
    return _evaluate(case, fixer_result.candidate)


_FAULT_SYMPTOMS: dict[str, tuple[str, str]] = {
    "final-output-bypass": ("image", "the saved output still matches the raw input instead of the processed result — it's as if the main processing step is being skipped before the export"),
    "vae-output-bypass": ("image", "the saved image looks like raw noise or the wrong stage — the decode step doesn't reach the final export"),
    "conditioning-swap": ("generation", "the result comes out wrong, like the prompt guidance is flipped — the negative prompt seems to be driving the image instead of the positive"),
    "latent-source-swap": ("generation", "the result doesn't match my input image at all — it's as if the generation started from the wrong source"),
    "wrong-output-slot": ("image", "the output doesn't reflect what I expected — it looks like one of the nodes is feeding the wrong output downstream"),
    "prompt-not-wired": ("generation", "the generation doesn't follow my prompt at all — it's as if the positive conditioning is missing, producing unrelated or default results"),
    "disabled-control-preprocessor": ("control", "the control signal doesn't affect the output — it's as if the ControlNet guidance is completely ignored"),
    "denoise-too-high": ("generation", "the output doesn't resemble my input image at all — it's as if the img2img strength is maxed out, generating a completely new image"),
    "cfg-too-high": ("generation", "the output looks oversaturated and has artifacts — it's as if the CFG scale is way too high, making the generation look harsh and unnatural"),
    "steps-too-low": ("quality", "the output looks unfinished and low quality — it's as if the generation didn't run enough steps, resulting in a blurry or underdeveloped image"),
    "resolution-wrong": ("output", "the output resolution is wrong — it's as if the latent dimensions were halved, producing a much smaller image than expected"),
    "fps-framecount-desync": ("video", "the video timing is off — it's as if the frame rate doesn't match the expected duration, causing sync issues"),
}


def _inquiry_for_fault(fault_family: str, fallback_effect: str) -> str:
    """Realistic, leak-free inquiry describing the fault's observable symptom."""
    capability, symptom = _FAULT_SYMPTOMS.get(
        fault_family,
        ("workflow", fallback_effect or "the output doesn't match what I expected"),
    )
    return (
        f"Something's off with the {capability} — {symptom} "
        f"Can you look at the workflow and fix it so the result comes out right?"
    )


def run_synthetic_case(
    golden: dict[str, Any],
    fault_family: str,
    output_base: Path,
    tag: str = "demo-factory",
) -> Case:
    """Run a synthetic fault injection case with up to 3 attempts."""
    case_id = _new_case_id()
    case_dir = _cases_dir(output_base) / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    case = Case(case_id=case_id, case_dir=case_dir, golden=golden, source="ready", fault_family=fault_family)
    case.advance_stage(CaseStage.SELECTED, {"source": "ready", "fault_family": fault_family})

    if not _baseline_gate(case, golden, case_dir):
        return case

    case.advance_stage(CaseStage.MUTATING)
    if fault_family == "final-output-bypass":
        injection = inject_final_output_bypass_fault(golden)
    elif fault_family == "conditioning-swap":
        injection = inject_conditioning_swap_fault(golden)
    elif fault_family == "vae-output-bypass":
        injection = inject_vae_output_bypass_fault(golden)
    elif fault_family == "latent-source-swap":
        injection = inject_latent_source_swap_fault(golden)
    elif fault_family == "wrong-output-slot":
        injection = inject_wrong_output_slot_fault(golden)
    elif fault_family == "prompt-not-wired":
        injection = inject_prompt_not_wired_fault(golden)
    elif fault_family == "disabled-control-preprocessor":
        injection = inject_disabled_control_preprocessor_fault(golden)
    elif fault_family == "denoise-too-high":
        injection = inject_denoise_too_high_fault(golden)
    elif fault_family == "cfg-too-high":
        injection = inject_cfg_too_high_fault(golden)
    elif fault_family == "steps-too-low":
        injection = inject_steps_too_low_fault(golden)
    elif fault_family == "resolution-wrong":
        injection = inject_resolution_wrong_fault(golden)
    elif fault_family == "fps-framecount-desync":
        injection = inject_fps_framecount_desync_fault(golden)
    else:
        raise ValueError(f"Unknown fault family: {fault_family}")

    case.injection = injection
    case.broken = injection.broken
    case.write_graph_artifacts()

    inquiry = _inquiry_for_fault(fault_family, injection.user_effect)
    case.inquiry = inquiry

    case.advance_stage(CaseStage.FAULT_PROVEN, {"repair_ops_count": len(injection.repair_delta)})

    # Try up to 3 attempts, keep case if ANY passes
    for attempt in range(1, 4):
        case.attempt = attempt
        attempts_dir = case_dir / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)
        attempt_dir = attempts_dir / f"{attempt:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        case.advance_stage(CaseStage.FIXER_RUNNING)
        fixer_result = _run_fixer(case, injection.broken, inquiry, attempt_dir)
        if not _fixer_gate(case, fixer_result):
            # Try next attempt if fixer failed
            if attempt < 3:
                continue
            return case

        leakage = check_leakage(inquiry)
        write_leakage_check(leakage, attempt_dir)
        evaluated_case = _evaluate(case, fixer_result.candidate)

        # If passed, return immediately
        if evaluated_case.verdict in (Verdict.ACCEPTED, Verdict.ALTERNATIVE_REPAIR):
            return evaluated_case

        # If failed and more attempts remain, try again
        if attempt < 3:
            continue

        return evaluated_case

    return case


def run_creative_case(
    golden: dict[str, Any],
    workflow_label: str,
    output_base: Path,
    tag: str = "demo-factory",
) -> Case:
    """Run a creative LLM-proposed bug injection case with up to 3 attempts.

    The creative engine uses DeepSeek to propose per-workflow, realistic,
    subtle, single-cause defects. Deterministic code validates and applies
    proposals, then derives repair predicates via derive_repair_delta.
    """
    from vibecomfy.demo_factory.creative import propose_bugs, judge, apply_bug
    from vibecomfy.demo_factory.deltas import derive_repair_delta

    case_id = _new_case_id()
    case_dir = _cases_dir(output_base) / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    case = Case(
        case_id=case_id,
        case_dir=case_dir,
        golden=golden,
        source="creative",
        fault_family="creative",
    )
    case.advance_stage(CaseStage.SELECTED, {"source": "creative", "workflow": workflow_label})

    if not _baseline_gate(case, golden, case_dir):
        return case

    case.advance_stage(CaseStage.MUTATING)

    # Propose bugs using DeepSeek
    proposals = propose_bugs(golden, n=10)

    # Judge and pick the best 1-2
    best = judge(proposals, golden)
    if not best:
        case.advance_stage(CaseStage.BASELINE_REJECTED, {"reason": "No applicable creative proposals"})
        case.verdict = Verdict.BASELINE_REJECTED
        case.write_status()
        return case

    # Try proposals in order until we find one that creates a real diff (non-empty fault locus)
    # This filters out NO-OP mutations where broken == golden
    proposal = None
    broken = None
    injection = None
    fault_family = None

    for prop in best:
        prop_broken = apply_bug(golden, prop)
        if prop_broken is None:
            continue

        # Derive repair delta to check if this creates a real fault
        prop_injection = derive_repair_delta(prop_broken, golden)

        # Check if fault locus is empty (NO-OP mutation)
        if not prop_injection.fault_predicate.get("locus"):
            # Empty locus means broken == golden at all meaningful positions
            # This is a NO-OP mutation - skip to next proposal
            continue

        # Found a real bug
        proposal = prop
        broken = prop_broken
        injection = prop_injection
        fault_family = f"creative:{proposal.summary}"
        break

    if broken is None or injection is None:
        case.advance_stage(CaseStage.BASELINE_REJECTED, {"reason": "All creative proposals were NO-OP mutations (broken == golden)"})
        case.verdict = Verdict.BASELINE_REJECTED
        case.write_status()
        return case

    case.injection = injection
    case.broken = broken
    case.fault_family = fault_family
    case.write_graph_artifacts()

    # Author the public inquiry. For additive (remove_feature) proposals the
    # generic user_symptom is too vague and the fixer just clarifies back, so
    # name the exact node type to re-add and where it reconnects. For repair
    # edits the proposal's user_symptom is already symptom-based and leak-free.
    if proposal.edit_type == "remove_feature":
        inquiry = _author_additive_inquiry(golden, broken, proposal)
    else:
        inquiry = proposal.user_symptom.strip()
    if not inquiry:
        inquiry = f"Something's wrong with the output — {proposal.why_realistic}"

    case.inquiry = inquiry

    # Additive (remove_feature) proposals ask the fixer to RE-ADD a node into a
    # graph that intentionally has a topology gap; flag it so the revise
    # pipeline treats the gap as the expected fault, not pre-existing damage.
    is_additive = proposal.edit_type == "remove_feature"

    # Store proposal metadata in case receipts
    case.advance_stage(CaseStage.FAULT_PROVEN, {
        "repair_ops_count": len(injection.repair_delta),
        "proposal_summary": proposal.summary,
        "proposal_why_realistic": proposal.why_realistic,
    })

    # Try up to 3 attempts, keep case if ANY passes
    for attempt in range(1, 4):
        case.attempt = attempt
        attempts_dir = case_dir / "attempts"
        attempts_dir.mkdir(parents=True, exist_ok=True)
        attempt_dir = attempts_dir / f"{attempt:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        case.advance_stage(CaseStage.FIXER_RUNNING)
        fixer_result = _run_fixer(
            case, injection.broken, inquiry, attempt_dir, additive=is_additive
        )
        if not _fixer_gate(case, fixer_result):
            # Try next attempt if fixer failed
            if attempt < 3:
                continue
            return case

        leakage = check_leakage(inquiry)
        write_leakage_check(leakage, attempt_dir)
        evaluated_case = _evaluate(case, fixer_result.candidate)

        # If passed, return immediately
        if evaluated_case.verdict in (Verdict.ACCEPTED, Verdict.ALTERNATIVE_REPAIR):
            return evaluated_case

        # If failed and more attempts remain, try again
        if attempt < 3:
            continue

        return evaluated_case

    return case


# Human-readable add-request templates keyed by the removed feature's node type
# prefix. Each names the exact comfy-core node class to re-add and the
# user-observable effect of its absence, so the fixer acts instead of clarifying.
_ADDITIVE_SYMPTOM = {
    "LatentUpscale": ("a LatentUpscale step", "the output is lower resolution than it should be — the final image lacks the extra detail the upscale pass used to add"),
    "UpscaleImage": ("an UpscaleImage step", "the output is lower resolution than it should be — it lost the extra detail the upscale pass used to add"),
    "ImageScale": ("an ImageScale resize step", "the output dimensions are wrong — the resize step that set the final size is missing"),
    "ImageScaleToTotalPixels": ("an ImageScaleToTotalPixels step", "the output resolution is wrong — the step that targeted the final pixel count is missing"),
    "ImageUpscaleWithModel": ("an ImageUpscaleWithModel step", "the output lost the sharpened, high-frequency detail the upscale model used to provide"),
    "ControlNetApply": ("a ControlNetApply step", "the structural/pose guidance from the ControlNet is completely absent — the output ignores the control reference"),
    "ControlNetApplyAdvanced": ("a ControlNetApplyAdvanced step", "the structural/pose guidance from the ControlNet is completely absent — the output ignores the control reference"),
    "LoraLoader": ("a LoraLoader step", "the style/character LoRA is no longer applied — the output lost the look that LoRA used to provide"),
    "LoraLoaderModelOnly": ("a LoraLoaderModelOnly step", "the style/character LoRA is no longer applied — the output lost the look that LoRA used to provide"),
    "VAEDecode": ("a VAEDecode step", "the latent never gets decoded to pixels — the pipeline can't produce a viewable image"),
    "VAEDecodeTiled": ("a VAEDecodeTiled step", "the tiled decode is missing — large images can't be decoded without it"),
}


def _author_additive_inquiry(
    golden: dict[str, Any], broken: dict[str, Any], proposal: Any
) -> str:
    """Specific, leak-aware add-request for a remove_feature fault.

    Names the exact node type to re-add (so the headless fixer resolves a
    comfy-core class instead of asking back) plus a user-observable symptom.
    """
    golden_ids = {str(n.get("id")) for n in door_get_nodes(golden, [])}
    broken_ids = {str(n.get("id")) for n in door_get_nodes(broken, [])}
    removed = [
        n for n in door_get_nodes(golden, [])
        if str(n.get("id")) in (golden_ids - broken_ids)
    ]
    # Prefer the feature's primary node type (the proposal's target if known).
    target_type = None
    if getattr(proposal, "target_node_id", None) is not None:
        for n in removed:
            if str(n.get("id")) == str(proposal.target_node_id):
                target_type = n.get("type")
                break
    if target_type is None and removed:
        target_type = removed[0].get("type")

    symptom_default = (
        "the step that used to refine the output is missing, so the result "
        "no longer matches what I expect"
    )
    add_phrase, symptom = symptom_default, symptom_default
    if target_type:
        for prefix, (phrase, symp) in _ADDITIVE_SYMPTOM.items():
            if target_type == prefix or target_type.startswith(prefix):
                add_phrase, symptom = phrase, symp
                break

    return (
        f"I had removed {add_phrase} from the workflow and now {symptom}. "
        f"Can you add that step back where it belongs so the output is restored? "
        f"(The node type to re-add is {target_type or 'the missing one'}.)"
    )


def _timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
