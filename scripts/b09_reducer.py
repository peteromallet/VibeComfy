"""B09 standalone reducer — report arithmetic reproduced from persisted evidence.

Reloads ONLY persisted artifacts (``run_summary.json`` + per-scenario
``agentic_summary.json`` + the D13 manifest + scenario descriptors) and
reproduces, deterministically:

* suite first-attempt and eventual rates over 100;
* product rates over 98 (63 edits + 35 semantic-answer; the 2 health controls
  are excluded and reported separately);
* the frozen infra-adjusted semantic rate: final passes / (100 - final typed
  persistent-empty failures); OTHER infra classes (timeout, capacity,
  no-summary, runner-exception) are reported separately, never removed;
* health-control results separately;
* refusal tri-state (pass/fail/undetermined) + judge availability;
* provenance and UI-artifact coverage;
* matched (97) vs D13-revised (3) subsets separately;
* remaining Class C/D ceiling (explicit, from documented hard-floor IDs).

Unknown values are labeled ``unknown``, never inferred. Output is fully
deterministic (stable sort, no timestamps), so running it twice yields
byte-identical ``b09_report.json`` and an idempotently stamped
``run_summary.json`` (commit/selection/configuration/corpus digests from
``b09_preflight.json``).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tests" / "live_agentic_harness"
MANIFEST_PATH = HARNESS / "scenario_manifest.json"
SCENARIOS_DIR = HARNESS / "scenarios"
DEFAULT_TAG = "megado-final"

# Documented Class D hard floor (unexpressible capabilities, from
# docs/failure-analysis/agentic-pipeline-improvement-2026-08.md §2/D7): these
# scenarios cannot pass without new product capabilities. D13 did not revise
# them; they remain matched descriptors whose queries target absent fields.
CLASS_D_HARD_FLOOR = [
    "3d-3d-model-generation-and-rigging-workflow-90a1d5",  # TripoRig: no joint control
    "3d-3d-model-generation-and-preview-workflow-cc0df7",  # Rodin: no model selector
    "image-inpainting-with-differential-diffusion-and-rea-1d414c",  # INPAINT: no denoise field
]

INFRA_CLASSES = (
    "infra_empty_response",
    "infra_timeout",
    "infra_provider_capacity",
    "infra_no_summary",
    "infra_runner_exception",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _summaries_from_run(run_summary: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios = run_summary.get("scenarios")
    if not isinstance(scenarios, list):
        return []
    return [s for s in scenarios if isinstance(s, dict)]


def _summaries_from_dir(run_dir: Path) -> list[dict[str, Any]]:
    """Reload canonical per-scenario summaries as an independent cross-check."""
    summaries: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("*/agentic_summary.json")):
        try:
            summaries.append(_load_json(path))
        except (OSError, json.JSONDecodeError):
            summaries.append({"scenario_id": path.parent.name, "unreadable": True})
    return summaries


def _entry_for(manifest: dict[str, Any], scenario_id: str) -> dict[str, Any] | None:
    for entry in manifest.get("entries", []):
        if entry.get("id") == scenario_id:
            return entry
    return None


def _scenario_descriptor(scenario_id: str) -> dict[str, Any] | None:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.is_file():
        return None
    try:
        return _load_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def _verdict(summary: dict[str, Any]) -> str:
    guard = summary.get("guard") or {}
    verdict = guard.get("verdict")
    if verdict in {"pass", "fail", "undetermined"}:
        return verdict
    if guard.get("live_agentic_success") is True:
        return "pass"
    return "fail"


def _score_class(summary: dict[str, Any]) -> str:
    guard = summary.get("guard") or {}
    if guard.get("verdict") == "undetermined":
        return "undetermined"
    if guard.get("score_class") == "undetermined":
        return "undetermined"
    explicit = summary.get("score_class") or guard.get("score_class")
    if explicit:
        return str(explicit)
    # Older summaries may not persist score_class. Preserve the assessor's
    # tri-state verdict instead of turning unavailable evidence into a product
    # failure merely because live_agentic_success is false.
    return "pass" if guard.get("live_agentic_success") is True else "product_fail"


def _failure_class(summary: dict[str, Any]) -> str:
    guard = summary.get("guard") or {}
    return (
        summary.get("failure_class")
        or guard.get("failure_class")
        or "product_or_assessment_failure"
    )


def _final_passes(summaries: list[dict[str, Any]]) -> int:
    return sum(1 for s in summaries if (s.get("guard") or {}).get("live_agentic_success") is True)


def _first_attempt_passes(summaries: list[dict[str, Any]]) -> int:
    return sum(
        1
        for s in summaries
        if s.get("raw_first_attempt_success", (s.get("guard") or {}).get("live_agentic_success"))
        is True
    )


def _infra_counts(summaries: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for summary in summaries:
        guard = summary.get("guard") or {}
        if guard.get("live_agentic_success") is True:
            continue
        cls = _failure_class(summary)
        if cls.startswith("infra_"):
            counts[cls] = counts.get(cls, 0) + 1
    return counts


def _refusal_stats(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Tri-state over scenarios that ran the grounded-refusal judge."""
    results = {"candidates": 0, "pass": 0, "fail": 0, "undetermined": 0, "judge_unavailable": 0}
    for summary in summaries:
        guard = summary.get("guard") or {}
        judge_results = (guard.get("assessment") or {}).get("judge_results") or []
        refusal = [
            j for j in judge_results if isinstance(j, dict) and j.get("judge") == "grounded_refusal"
        ]
        if not refusal:
            continue
        results["candidates"] += 1
        tri = refusal[-1].get("verdict")
        if tri == "pass":
            results["pass"] += 1
        elif tri == "fail":
            results["fail"] += 1
        else:
            results["undetermined"] += 1
            if refusal[-1].get("error"):
                results["judge_unavailable"] += 1
    return results


def _ui_coverage(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    original = final = 0
    for summary in summaries:
        ui = ((summary.get("guard") or {}).get("assessment") or {}).get("ui_evidence") or {}
        if ui.get("original") is True:
            original += 1
        if ui.get("final") is True:
            final += 1
    total = len(summaries) or 1
    return {
        "original_ui_present": original,
        "final_ui_present": final,
        "both_present": sum(
            1
            for s in summaries
            if (
                ((s.get("guard") or {}).get("assessment") or {}).get("ui_evidence") or {}
            ).get("original")
            is True
            and (
                ((s.get("guard") or {}).get("assessment") or {}).get("ui_evidence") or {}
            ).get("final")
            is True
        ),
        "rate": f"{original}/{total}",
    }


def _provenance_coverage(summaries: list[dict[str, Any]], run_dir: Path) -> dict[str, Any]:
    """Persisted evidence only: output dir + flow_metadata + typed model attempts."""
    present_flow = 0
    present_attempts = 0
    transport_openrouter = 0
    unknown = 0
    for summary in summaries:
        output_dir = summary.get("output_dir")
        if not output_dir:
            unknown += 1
            continue
        flow = Path(output_dir) / "flow_metadata.json"
        attempts = Path(output_dir) / "model_attempts.json"
        if flow.is_file():
            present_flow += 1
        if attempts.is_file():
            present_attempts += 1
        if summary.get("transport") == "openrouter":
            transport_openrouter += 1
    total = len(summaries) or 1
    return {
        "flow_metadata_present": present_flow,
        "model_attempts_present": present_attempts,
        "observed_transport_openrouter": transport_openrouter,
        "unknown_output_dirs": unknown,
        "rate": f"{present_flow}/{total}",
    }


def _group_rate(
    summaries: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    predicate,
    label: str,
) -> dict[str, Any]:
    group = [s for s in summaries if predicate(_entry_for(manifest, str(s.get("scenario_id"))))]
    total = len(group)
    if total == 0:
        return {"label": label, "n": 0, "final_passes": 0, "first_attempt_passes": 0, "rate": "0/0"}
    return {
        "label": label,
        "n": total,
        "final_passes": _final_passes(group),
        "first_attempt_passes": _first_attempt_passes(group),
        "rate": f"{_final_passes(group)}/{total}",
    }


def build_report(tag: str) -> dict[str, Any]:
    run_dir = REPO / "out" / "agentic" / tag
    run_summary_path = run_dir / "run_summary.json"
    preflight_path = run_dir / "b09_preflight.json"
    if not run_summary_path.is_file():
        raise SystemExit(f"run_summary.json missing: {run_summary_path}")
    run_summary = _load_json(run_summary_path)
    manifest = _load_json(MANIFEST_PATH)
    preflight = _load_json(preflight_path) if preflight_path.is_file() else {}

    summaries = _summaries_from_run(run_summary)
    # Independent reload of canonical per-scenario summaries (cross-check only).
    per_dir = _summaries_from_dir(run_dir)
    per_dir_ids = {str(s.get("scenario_id")) for s in per_dir}
    run_ids = {str(s.get("scenario_id")) for s in summaries}
    cross_check = {
        "run_summary_scenarios": len(summaries),
        "canonical_per_scenario_summaries": len(per_dir),
        "ids_match": per_dir_ids == run_ids,
        "complete": bool(run_summary.get("complete")),
        "declared_total": run_summary.get("total_scenarios"),
    }

    total = len(summaries)
    first_passes = _first_attempt_passes(summaries)
    final_passes = _final_passes(summaries)
    infra_counts = _infra_counts(summaries)
    persistent_empty = infra_counts.get("infra_empty_response", 0)

    def is_product(entry: dict[str, Any] | None) -> bool:
        return bool(entry) and entry.get("scenario_kind") in {"edit", "semantic_product"}

    def is_control(entry: dict[str, Any] | None) -> bool:
        return bool(entry) and entry.get("scenario_kind") == "health_control"

    def is_revised(entry: dict[str, Any] | None) -> bool:
        return bool(entry) and entry.get("revision_status") == "revised"

    def is_matched(entry: dict[str, Any] | None) -> bool:
        return bool(entry) and entry.get("revision_status") == "matched"

    product = _group_rate(summaries, manifest, predicate=is_product, label="products (98)")
    edits = _group_rate(summaries, manifest, predicate=lambda e: bool(e) and e.get("scenario_kind") == "edit", label="edits (63)")
    semantic = _group_rate(summaries, manifest, predicate=lambda e: bool(e) and e.get("scenario_kind") == "semantic_product", label="semantic-answer (35)")
    controls = _group_rate(summaries, manifest, predicate=is_control, label="health controls (2)")
    revised = _group_rate(summaries, manifest, predicate=is_revised, label="D13-revised (3)")
    matched = _group_rate(summaries, manifest, predicate=is_matched, label="matched (97)")

    product_denominator = max(product["n"], 1)
    infra_adjusted_denominator = total - persistent_empty
    infra_adjusted_numerator = final_passes

    report: dict[str, Any] = {
        "tag": tag,
        "evidence_sources": {
            "run_summary": "out/agentic/{tag}/run_summary.json",
            "per_scenario": "out/agentic/{tag}/<scenario_id>/agentic_summary.json",
            "manifest": "tests/live_agentic_harness/scenario_manifest.json",
        },
        "cross_check": cross_check,
        "suite": {
            "total": total,
            "complete": bool(run_summary.get("complete")),
            "first_attempt_passes": first_passes,
            "first_attempt_rate": f"{first_passes}/{total}",
            "eventual_passes": final_passes,
            "eventual_rate": f"{final_passes}/{total}",
        },
        "product_rates": {
            "products_98": product,
            "edits_63": edits,
            "semantic_answer_35": semantic,
            "health_controls_2": controls,
            "note": (
                "product rates exclude the 2 health controls; health controls "
                "are reported separately and are NOT in any product denominator."
            ),
        },
        "infra_adjusted": {
            "numerator_final_passes": infra_adjusted_numerator,
            "denominator": infra_adjusted_denominator,
            "rate": f"{infra_adjusted_numerator}/{infra_adjusted_denominator}",
            "denominator_formula": "100 - final typed persistent-empty failures (infra_empty_response)",
            "excluded_final_persistent_empty": persistent_empty,
            "other_infra_classes_shown_separately": {
                k: v for k, v in sorted(infra_counts.items()) if k != "infra_empty_response"
            },
            "all_infra_counts": dict(sorted(infra_counts.items())),
        },
        "health_controls": {
            "note": "separate from all product arithmetic",
            "details": [
                {
                    "scenario_id": str(s.get("scenario_id")),
                    "verdict": _verdict(s),
                    "score_class": _score_class(s),
                }
                for s in summaries
                if is_control(_entry_for(manifest, str(s.get("scenario_id"))))
            ],
        },
        "refusal": _refusal_stats(summaries),
        "coverage": {
            "ui_evidence": _ui_coverage(summaries),
            "provenance": _provenance_coverage(summaries, run_dir),
        },
        "matched_vs_revised": {
            "matched_97": matched,
            "revised_3": revised,
            "note": (
                "revised-subset gains are D13 scenario-correction gains, not "
                "pure product gains; no aggregate improvement is attributed to "
                "D13 changes as product quality."
            ),
        },
        "class_c_d_ceiling": {
            "documented_class_d_hard_floor": CLASS_D_HARD_FLOOR,
            "ceiling_explicit": (
                f"max achievable product passes = {product_denominator - len(CLASS_D_HARD_FLOOR)}/"
                f"{product_denominator} (98 products minus {len(CLASS_D_HARD_FLOOR)} documented "
                "Class-D unexpressible scenarios); the residual gap to that ceiling is the "
                "Class C model-output tail plus any Class D scenarios beyond the documented floor. "
                "Per-scenario C/D binning for THIS lane is not inferred: no failure-analysis "
                "subagent pass was run, so exact C/D attribution of final failures is 'unknown' "
                "unless directly evidenced by failure_class."
            ),
            "final_failures_by_class": {
                "infra": dict(sorted(infra_counts.items())),
                "product_or_assessment": sum(
                    1
                    for s in summaries
                    if (s.get("guard") or {}).get("live_agentic_success") is not True
                    and not _failure_class(s).startswith("infra_")
                ),
            },
        },
        "flaky": {
            "named_flaky_ids": [],
            "regression_vs_variance_claim": None,
            "note": (
                "historical out/agentic/ evidence is ABSENT -> no flaky-set "
                "derivation, no regression-versus-variance claim (B09 items 9/10)."
            ),
        },
        "digests": {
            "commit": preflight.get("commit"),
            "selection": preflight.get("selection"),
            "configuration": preflight.get("configuration"),
            "corpus": preflight.get("corpus"),
            "source_workflows": preflight.get("source_workflows"),
        },
    }
    return report


def stamp_run_summary(tag: str, report: dict[str, Any]) -> None:
    """Embed commit/selection/configuration/corpus digests in run_summary.json.

    Idempotent: re-running writes byte-identical content (same input, same
    dump style as the runner: indent=2, default=str, no sort_keys).
    """
    run_dir = REPO / "out" / "agentic" / tag
    run_summary_path = run_dir / "run_summary.json"
    run_summary = _load_json(run_summary_path)
    digests = {k: v for k, v in (report.get("digests") or {}).items() if v is not None}
    run_summary["b09_digests"] = digests
    tmp = run_summary_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(run_summary, indent=2, default=str) + "\n", encoding="utf-8")
    tmp.replace(run_summary_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--no-stamp", action="store_true", help="do not stamp run_summary.json")
    args = parser.parse_args(argv)
    report = build_report(args.tag)
    if not args.no_stamp:
        stamp_run_summary(args.tag, report)
    report_path = REPO / "out" / "agentic" / args.tag / "b09_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
