"""Paired full vs two-step pipeline-mode comparator (B07 Pro).

Deterministic bootstrap + fair paired comparison.  The classify decision is
classified ONCE (frozen in ``classification_lock.json``), then INJECTED
identically into both the ``full`` and ``two_step`` executor modes so the only
thing that varies is the pipeline mode — never the classification.

CLI
---
``python -m tests.live_agentic_harness.compare_pipeline_modes --validate-only``
    Validate the frozen lock + 50-manifest + injection wiring WITHOUT any model
    call.  This is the gate command.

``python -m tests.live_agentic_harness.compare_pipeline_modes --bootstrap``
    Regenerate ``classification_lock.json`` + ``two_step_50_manifest.json``
    deterministically (idempotent; must reproduce the committed bytes).

``python -m tests.live_agentic_harness.compare_pipeline_modes --run``
    Live paired run (host only).  Each included scenario runs ``full`` then
    ``two_step`` under separate durable session roots, with the locked decision
    injected into both.  Per-scenario + aggregate JSON/Markdown are written.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from . import classification as C
from .scenario_manifest import (
    DEFAULT_SCENARIOS_DIR,
    ScenarioManifestError,
    discover_manifest_scenarios,
)

HERE = Path(__file__).resolve().parent
DEFAULT_LOCK_PATH = HERE / "classification_lock.json"
DEFAULT_TWO_STEP_MANIFEST = HERE / "two_step_50_manifest.json"
DEFAULT_SCENFAILS57_MANIFEST = HERE / "scenfails57_manifest.json"
DEFAULT_OUTPUT_BASE = Path("out") / "compare-pipeline-modes"

# ── test-only classify injection ─────────────────────────────────────────────
#
# The lock stores a ROUTE per scenario; a route maps to the legacy boolean +
# intent/task fields that fully determine a ClassifyDecision.  Both modes are
# handed the IDENTICAL ClassifyDecision so the comparison isolates the pipeline
# mode.  ``requires_custom_nodes`` is normalized by the executor's install-intent
# migration (core._normalize_explicit_route) — the SAME normalized decision is
# injected into both modes, so parity still holds.

_ROUTE_PLAN_FIELDS: dict[str, dict[str, Any]] = {
    "clarify": {"research": False, "implement": False, "intent": "respond", "task": ""},
    "respond": {"research": False, "implement": False, "intent": "respond", "task": ""},
    "inspect": {"research": False, "implement": False, "intent": "explain_graph", "task": "inspect_graph"},
    "research": {"research": True, "implement": False, "intent": "research", "task": "research_nodes"},
    "requires_custom_nodes": {"research": False, "implement": False, "intent": "edit", "task": "edit_graph"},
    "revise": {"research": False, "implement": True, "intent": "edit", "task": "edit_graph"},
    "adapt": {"research": True, "implement": True, "intent": "edit", "task": "research_precedent"},
    "reorganise": {"research": False, "implement": True, "intent": "edit", "task": "layout_reorganise"},
}


def build_injected_plan(route: str) -> Any:
    """Build the frozen ClassifyDecision for a locked route (test-only)."""
    from vibecomfy.executor.contracts import ClassifyDecision  # noqa: PLC0415

    if route not in _ROUTE_PLAN_FIELDS:
        raise ValueError(f"unknown route {route!r}")
    return ClassifyDecision(route=route, reply=True, **_ROUTE_PLAN_FIELDS[route])


def injection_target() -> str:
    """The classify call patched by the comparator (documented seam)."""
    return "vibecomfy.executor.core._run_classify"


class _InjectClassify:
    """Context manager that forces ``_run_classify`` to return *plan*."""

    def __init__(self, plan: Any) -> None:
        self._plan = plan
        self._original = None

    def __enter__(self) -> "_InjectClassify":
        import vibecomfy.executor.core as core  # noqa: PLC0415

        self._original = core._run_classify
        core._run_classify = lambda *a, **k: self._plan  # type: ignore[assignment]
        return self

    def __exit__(self, *exc: Any) -> None:
        import vibecomfy.executor.core as core  # noqa: PLC0415

        core._run_classify = self._original


# ── frozen artifact loading ───────────────────────────────────────────────────


def load_lock(path: Path | None = None) -> dict[str, Any]:
    lock_path = path or DEFAULT_LOCK_PATH
    if not lock_path.is_file():
        raise C.ClassificationError(f"classification lock missing: {lock_path}")
    return json.loads(lock_path.read_text(encoding="utf-8"))


def load_in_57_ids() -> frozenset[str]:
    manifest = json.loads(DEFAULT_SCENFAILS57_MANIFEST.read_text(encoding="utf-8"))
    return frozenset(e["id"] for e in manifest["entries"])


def load_scenarios() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(DEFAULT_SCENARIOS_DIR.glob("*.json"))
    ]


# ── bootstrap ─────────────────────────────────────────────────────────────────


def bootstrap(lock_path: Path | None = None, manifest_path: Path | None = None) -> dict[str, Any]:
    """Regenerate + write the lock and 50-manifest (idempotent)."""
    scenarios = load_scenarios()
    in_57_ids = load_in_57_ids()
    lock = C.build_classification_lock(scenarios, in_57_ids=in_57_ids)
    manifest = C.build_two_step_manifest(lock)

    lock_target = lock_path or DEFAULT_LOCK_PATH
    manifest_target = manifest_path or DEFAULT_TWO_STEP_MANIFEST
    lock_target.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    manifest_target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"lock_path": str(lock_target), "manifest_path": str(manifest_target)}


# ── validate-only ─────────────────────────────────────────────────────────────


def validate_only(manifest_path: Path | None = None) -> dict[str, Any]:
    """Deterministic gate validation: lock + manifest + injection wiring."""
    manifest_target = manifest_path or DEFAULT_TWO_STEP_MANIFEST
    lock = load_lock()
    in_57_ids = load_in_57_ids()
    scenarios = load_scenarios()
    scenario_ids = frozenset(s["id"] for s in scenarios)

    # 1. The 50-manifest is strict: every included descriptor resolves + hashes.
    try:
        included_paths = discover_manifest_scenarios(
            DEFAULT_SCENARIOS_DIR, manifest_path=manifest_target
        )
    except ScenarioManifestError as exc:
        raise C.ClassificationError(f"manifest strict-validation failed: {exc}") from exc

    manifest = json.loads(manifest_target.read_text(encoding="utf-8"))
    entries = manifest["entries"]
    included_ids = [e["id"] for e in entries if e["inclusion_status"] == "included"]
    excluded_ids = [e["id"] for e in entries if e["inclusion_status"] == "excluded"]

    # 2. All 100 canonical descriptors are referenced exactly once, 50/50.
    if set(included_ids) | set(excluded_ids) != scenario_ids:
        raise C.ClassificationError("manifest does not reference all 100 canonical descriptors")
    if len(included_ids) != 50 or len(excluded_ids) != 50:
        raise C.ClassificationError("manifest must split 50 included / 50 excluded")
    if set(included_ids) != set(p.stem for p in included_paths):
        raise C.ClassificationError("manifest included set != strict-discovered set")

    # 3. Lock covers all 100 with valid dimensions + matches the 57-ledger.
    C.validate_lock(lock, scenario_ids=scenario_ids, in_57_ids=in_57_ids)

    # 4. The manifest selection hits the hard quotas exactly.
    C.validate_manifest_quotas(manifest, lock)

    # 5. The manifest pins descriptor + source hashes (already enforced by
    #    discover_manifest_scenarios) AND its classification block matches the
    #    frozen lock entry-for-entry.
    lock_by_id = {e["id"]: e for e in lock["entries"]}
    for entry in entries:
        cls = entry.get("classification") or {}
        lock_cls = lock_by_id[entry["id"]]
        for field in ("route", "behavior", "ledger", "graph_size", "media"):
            if cls.get(field) != lock_cls[field]:
                raise C.ClassificationError(
                    f"manifest classification drift for {entry['id']}: {field}"
                )

    # 6. Injection wiring: every locked route maps to a ClassifyDecision.
    plans = {}
    for route in C.ROUTES:
        plan = build_injected_plan(route)
        plans[route] = plan.effective_route
        if not isinstance(plan.to_dict(), dict):
            raise C.ClassificationError(f"injected plan for {route} is not serializable")

    return {
        "ok": True,
        "manifest": str(manifest_target),
        "included": len(included_ids),
        "excluded": len(excluded_ids),
        "scenario_count": len(scenario_ids),
        "quota_table": lock["quota_table"],
        "injected_plan_routes": plans,
    }


# ── live paired run (host only) ───────────────────────────────────────────────


def _mode_session_root(output_base: Path, mode: str, scenario_id: str) -> Path:
    """Separate durable session root per mode (no cross-contamination)."""
    return output_base / mode / scenario_id


def _cache_key(scenario_id: str, mode: str) -> str:
    return f"{scenario_id}::{mode}"


def load_cached_pair(cache_dir: Path, scenario_id: str) -> dict[str, Any] | None:
    """Return a cached (full, two_step) result pair, or None.

    The 50-lane shares billing with the 57-ledger for its 25 in-57 scenarios;
    a previously persisted pair (or single-mode result) is reused instead of a
    second model call.
    """
    path = cache_dir / f"{scenario_id}.pair.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _run_scenario_mode(
    scenario: Mapping[str, Any],
    *,
    mode: str,
    route: str,
    output_base: Path,
    tag: str,
    transport: str | None,
) -> dict[str, Any]:
    """Run one scenario in one pipeline mode with the locked decision injected."""
    from .adapter import run_headless_scenario  # noqa: PLC0415

    plan = build_injected_plan(route)
    mode_scenario = dict(scenario)
    mode_scenario["pipeline_mode"] = mode
    mode_scenario["session_id"] = f"{tag}-{mode}-{scenario['id']}"
    mode_scenario["profile"] = mode_scenario.get("profile") or "default"

    with _InjectClassify(plan):
        summary = run_headless_scenario(
            mode_scenario,
            output_base=output_base,
            tag=f"{tag}/{mode}",
            transport=transport,
        )
    summary["pipeline_mode"] = mode
    summary["injected_route"] = route
    summary["injected_effective_route"] = plan.effective_route
    return summary


def _canonical_graph_digest(graph: Any) -> str | None:
    """Canonical structural digest used as the pi_edit / Δ-replay parity proxy.

    The executor's true editable quotient (``pi_edit``) and accepted-Δ replay
    both reduce the candidate graph to a deterministic structural form.  For the
    paired comparison we use a stable structural digest of the post-edit graph
    (and of the original→final node/class delta) as a parity proxy: two modes
    that land the same edit produce identical digests.
    """
    if not isinstance(graph, dict):
        return None
    nodes = graph.get("nodes")
    if isinstance(nodes, dict):
        items = sorted(
            (str(nid), str(node.get("class_type", "")))
            for nid, node in nodes.items()
            if isinstance(node, dict)
        )
    elif isinstance(nodes, list):
        items = sorted(
            (str(node.get("id", "")), str(node.get("type", "") or node.get("class_type", "")))
            for node in nodes
            if isinstance(node, dict)
        )
    else:
        items = sorted(
            (str(k), str(v.get("class_type", "")))
            for k, v in graph.items()
            if isinstance(v, dict)
        )
    if not items:
        return None
    import hashlib

    return hashlib.sha256(json.dumps(items, sort_keys=True).encode("utf-8")).hexdigest()


def _graph_signature(output_dir: str | None) -> dict[str, Any]:
    """Read original/final UI graphs and return their structural signatures."""
    if not output_dir:
        return {}
    out = Path(str(output_dir))
    signature: dict[str, Any] = {}
    for name in ("original", "final"):
        path = out / f"{name}.ui.json"
        if not path.is_file():
            continue
        try:
            graph = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        signature[f"{name}_digest"] = _canonical_graph_digest(graph)
    return signature


def _assessment_signals(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Bucket the guard assessment issues into the comparison signal families."""
    guard = summary.get("guard") or {}
    assessment = guard.get("assessment") or {}
    issues = assessment.get("issues") or []
    signals: dict[str, int] = {}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        check = str(issue.get("check") or "")
        severity = str(issue.get("severity") or "")
        if check not in signals:
            signals[check] = 0
        signals[check] += 1
        signals.setdefault(f"severity:{severity}", 0)
        signals[f"severity:{severity}"] += 1
    judge_results = assessment.get("judge_results") or []
    return {
        "issue_checks": signals,
        "issue_count": assessment.get("issue_count"),
        "error_count": assessment.get("error_count"),
        "judge_results": judge_results,
        "ui_evidence": assessment.get("ui_evidence"),
    }


def _scenario_comparison(
    scenario: Mapping[str, Any],
    *,
    route: str,
    full: Mapping[str, Any],
    two_step: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract the paired comparison metrics for one scenario."""

    def _guard_metrics(summary: Mapping[str, Any]) -> dict[str, Any]:
        guard = summary.get("guard") or {}
        assessment = guard.get("assessment") or {}
        return {
            "live_agentic_success": guard.get("live_agentic_success"),
            "failure_class": guard.get("failure_class") or summary.get("failure_class"),
            "score_class": guard.get("score_class") or summary.get("score_class"),
            "verdict": assessment.get("verdict"),
            "passed": assessment.get("passed"),
            "signals": _assessment_signals(summary),
        }

    def _usage(summary: Mapping[str, Any]) -> dict[str, Any]:
        usage = summary.get("deepseek_usage") or {}
        return {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "est_cost_usd": summary.get("deepseek_est_cost_usd"),
        }

    def _attempts(summary: Mapping[str, Any]) -> dict[str, Any]:
        attempts = summary.get("model_attempts") or []
        return {
            "count": len(attempts),
            "failure_types": [a.get("failure_type") for a in attempts if isinstance(a, dict)],
        }

    full_guard = _guard_metrics(full)
    two_guard = _guard_metrics(two_step)
    full_graph = _graph_signature(full.get("output_dir"))
    two_graph = _graph_signature(two_step.get("output_dir"))
    graph_digest_equal = (
        full_graph.get("final_digest") == two_graph.get("final_digest")
        and full_graph.get("final_digest") is not None
    )
    return {
        "scenario_id": scenario["id"],
        "route": route,
        "full": {
            "ok": full.get("ok"),
            "status": full.get("status"),
            "guard": full_guard,
            "usage": _usage(full),
            "attempts": _attempts(full),
            "elapsed_s": full.get("elapsed_s"),
            "output_dir": full.get("output_dir"),
            "graph_signature": full_graph,
        },
        "two_step": {
            "ok": two_step.get("ok"),
            "status": two_step.get("status"),
            "guard": two_guard,
            "usage": _usage(two_step),
            "attempts": _attempts(two_step),
            "elapsed_s": two_step.get("elapsed_s"),
            "output_dir": two_step.get("output_dir"),
            "graph_signature": two_graph,
        },
        "delta": {
            "judge_outcome_equal": full_guard.get("verdict") == two_guard.get("verdict"),
            "live_success_equal": full_guard.get("live_agentic_success")
            == two_guard.get("live_agentic_success"),
            "failure_family_equal": full_guard.get("failure_class") == two_guard.get("failure_class"),
            "pi_edit_post_equal": graph_digest_equal,
            "canonical_delta_replay_equal": graph_digest_equal,
            "issue_checks_equal": full_guard["signals"]["issue_checks"]
            == two_guard["signals"]["issue_checks"],
        },
    }


def _aggregate(
    comparisons: list[dict[str, Any]],
    *,
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    included = len(comparisons)
    both_ok = sum(1 for c in comparisons if c["full"]["ok"] and c["two_step"]["ok"])
    judge_equal = sum(1 for c in comparisons if c["delta"]["judge_outcome_equal"])
    live_equal = sum(1 for c in comparisons if c["delta"]["live_success_equal"])
    full_cost = sum(
        (c["full"]["usage"].get("est_cost_usd") or 0.0) for c in comparisons
    )
    two_cost = sum(
        (c["two_step"]["usage"].get("est_cost_usd") or 0.0) for c in comparisons
    )
    full_tokens = sum(
        (c["full"]["usage"].get("total_tokens") or 0) for c in comparisons
    )
    two_tokens = sum(
        (c["two_step"]["usage"].get("total_tokens") or 0) for c in comparisons
    )
    return {
        "scenario_count": included,
        "both_ok": both_ok,
        "judge_outcome_equal": judge_equal,
        "judge_outcome_equal_rate": round(judge_equal / included, 4) if included else None,
        "live_success_equal": live_equal,
        "live_success_equal_rate": round(live_equal / included, 4) if included else None,
        "full": {"cost_usd": round(full_cost, 6), "total_tokens": full_tokens},
        "two_step": {"cost_usd": round(two_cost, 6), "total_tokens": two_tokens},
        "session_reuse_rate": _session_reuse_rate(comparisons),
    }


def _session_reuse_rate(comparisons: list[dict[str, Any]]) -> float | None:
    """Fraction of scenarios whose session dir was reused vs fresh-created."""
    reused = 0
    total = 0
    for c in comparisons:
        for mode in ("full", "two_step"):
            out = c[mode].get("output_dir")
            if not out:
                continue
            total += 1
            # A durable session root is "reused" when the evidence dir already
            # held a prior flow for the same scenario+mode (cache hit).
            marker = Path(str(out)) / "flow_metadata.json"
            if marker.is_file():
                reused += 1
    return round(reused / total, 4) if total else None


def run_comparison(
    manifest_path: Path,
    *,
    output_base: Path | None = None,
    cache_dir: Path | None = None,
    transport: str | None = None,
) -> dict[str, Any]:
    """Live paired run over the manifest's 50 included scenarios."""
    lock = load_lock()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    lock_by_id = {e["id"]: e for e in lock["entries"]}
    included = [e for e in manifest["entries"] if e["inclusion_status"] == "included"]

    base = output_base or DEFAULT_OUTPUT_BASE
    cache = cache_dir or (base / "cache")
    cache.mkdir(parents=True, exist_ok=True)
    scenario_by_id = {s["id"]: s for s in load_scenarios()}

    comparisons: list[dict[str, Any]] = []
    for entry in included:
        scenario_id = entry["id"]
        route = entry["classification"]["route"]
        scenario = scenario_by_id[scenario_id]

        cached = load_cached_pair(cache, scenario_id)
        if cached and cached.get("full") and cached.get("two_step"):
            comparisons.append(cached["comparison"])
            continue

        full = _run_scenario_mode(
            scenario, mode="full", route=route, output_base=base, tag="paired", transport=transport
        )
        two_step = _run_scenario_mode(
            scenario, mode="two_step", route=route, output_base=base, tag="paired", transport=transport
        )
        comparison = _scenario_comparison(scenario, route=route, full=full, two_step=two_step)
        comparisons.append(comparison)
        (cache / f"{scenario_id}.pair.json").write_text(
            json.dumps({"comparison": comparison, "full": full, "two_step": two_step}, indent=2, default=str),
            encoding="utf-8",
        )

    aggregate = _aggregate(comparisons, lock=lock)
    payload = {"aggregate": aggregate, "scenarios": comparisons}
    (base / "comparison.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    (base / "comparison.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


def _render_markdown(payload: Mapping[str, Any]) -> str:
    agg = payload["aggregate"]
    lines = [
        "# Pipeline-mode comparison (full vs two-step)",
        "",
        f"- scenarios: {agg['scenario_count']}",
        f"- both ok: {agg['both_ok']}",
        f"- judge outcome equal: {agg['judge_outcome_equal_rate']}",
        f"- live success equal: {agg['live_success_equal_rate']}",
        f"- session reuse rate: {agg['session_reuse_rate']}",
        f"- full cost (USD): {agg['full']['cost_usd']} / tokens {agg['full']['total_tokens']}",
        f"- two_step cost (USD): {agg['two_step']['cost_usd']} / tokens {agg['two_step']['total_tokens']}",
        "",
        "| scenario | route | full ok | two-step ok | judge equal |",
        "|---|---|---|---|---|",
    ]
    for c in payload["scenarios"]:
        lines.append(
            f"| {c['scenario_id']} | {c['route']} | {c['full']['ok']} | "
            f"{c['two_step']['ok']} | {c['delta']['judge_outcome_equal']} |"
        )
    return "\n".join(lines) + "\n"


# ── CLI ───────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.live_agentic_harness.compare_pipeline_modes"
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_TWO_STEP_MANIFEST),
        help="two-step 50-manifest (default: two_step_50_manifest.json)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate lock + manifest + injection wiring (no model calls)",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="regenerate classification_lock.json + two_step_50_manifest.json",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="run the live paired comparison (host only)",
    )
    parser.add_argument("--output-base", default=None, help="evidence output root")
    parser.add_argument(
        "--transport", choices=("openrouter", "native"), default=None,
        help="explicit model-call transport",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.bootstrap:
        result = bootstrap()
        print(json.dumps(result, indent=2))
        return 0

    if args.validate_only:
        try:
            result = validate_only(Path(args.manifest))
        except (C.ClassificationError, ScenarioManifestError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            return 1
        print(json.dumps(result, indent=2, default=str))
        return 0

    if args.run:
        payload = run_comparison(
            Path(args.manifest),
            output_base=Path(args.output_base) if args.output_base else None,
            transport=args.transport,
        )
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print("choose --validate-only, --bootstrap, or --run")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
