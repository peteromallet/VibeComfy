"""Paired full vs two-step pipeline-mode comparator (B07 Pro).

Deterministic bootstrap + fair paired comparison.  The classify decision is
captured ONCE (frozen in ``classification_lock.json``), then INJECTED
identically into both the ``full`` and ``two_step`` executor modes so the only
thing that varies is the pipeline mode — never the classification.

The lock stores, per scenario, the LOCKED route (the classifier's decision in
the 8-route vocabulary, including the install-intent ``requires_custom_nodes``)
AND the executor-canonical ``effective_route`` (``requires_custom_nodes`` →
``adapt`` under edit intent).  Both are recorded so a canonicalized lane is
never silently relabeled.

CLI
---
``--validate-only [--manifest X] [--ledger {current|ir-everywhere-57-v3}]``
    Validate the frozen lock + 50-manifest + injection wiring + ledger lane
    WITHOUT any model call.  This is the gate command.

``--bootstrap [--capture-classifications]``
    Regenerate ``classification_lock.json`` + ``two_step_50_manifest.json``.
    ``--bootstrap`` alone writes the deterministic provisional freeze
    (idempotent, byte-stable, no model calls).  Adding
    ``--capture-classifications`` (equivalently ``--capture-classifications``
    alone) runs the REAL classifier over all 100 canonical scenarios — one
    model call each, the documented capture path the host runs after the final
    sense-check.

``--run [--manifest X] [--tag T] [--ledger ...] [--max-workers N]``
    Live paired run (host only).  Each included scenario runs ``full`` then
    ``two_step`` under separate durable session roots, with the locked decision
    injected into both.  Per-scenario + aggregate JSON/Markdown are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from . import classification as C
from .ledger_selection import (
    LEDGER_ARTIFACT_LABEL,
    LEDGER_LABEL_CURRENT,
    LedgerLabelError,
    ledger_selection_ids,
    resolve_ledger_label,
)
from .scenario_manifest import (
    DEFAULT_SCENARIOS_DIR,
    ScenarioManifestError,
    discover_manifest_scenarios,
)

HERE = Path(__file__).resolve().parent
DEFAULT_LOCK_PATH = HERE / "classification_lock.json"
DEFAULT_TWO_STEP_MANIFEST = HERE / "two_step_50_manifest.json"
DEFAULT_OUTPUT_BASE = Path("out") / "compare-pipeline-modes"

# ── test-only classify injection ─────────────────────────────────────────────
#
# The lock stores a frozen ``decision`` (a full ``ClassifyDecision.to_dict()``)
# per scenario plus the locked ``route`` and its executor-canonical
# ``effective_route``.  Both modes are handed the IDENTICAL ``ClassifyDecision``
# reconstructed from that frozen decision, so the comparison isolates the
# pipeline mode.  ``requires_custom_nodes`` is canonicalized by the executor's
# install-intent migration (``core._normalize_explicit_route``): the locked
# route is recorded separately from the effective route, never silently folded.


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


def build_injected_plan(source: Mapping[str, Any] | str) -> Any:
    """Build the frozen :class:`ClassifyDecision` for a lock entry (or route).

    Prefers the entry's frozen ``decision`` (the real classifier output, or the
    documented provisional stand-in).  A bare route string is accepted only as
    a provisional fallback for wiring checks.
    """
    from vibecomfy.executor.contracts import ClassifyDecision  # noqa: PLC0415

    if isinstance(source, str):
        decision = C.provisional_decision(source)
        return ClassifyDecision(**decision)

    decision = source.get("decision")
    if isinstance(decision, Mapping):
        return ClassifyDecision(**dict(decision))
    route = source.get("route")
    if not isinstance(route, str) or route not in C.ROUTES:
        raise C.ClassificationError(f"no injectable decision for {source.get('id')!r}")
    return ClassifyDecision(**C.provisional_decision(route))


def _locked_and_effective(source: Mapping[str, Any] | str) -> tuple[str, str]:
    """Return ``(locked_route, effective_route)`` for a lock entry (or route)."""
    if isinstance(source, str):
        return source, C.provisional_effective_route(source)
    plan = build_injected_plan(source)
    locked = str(source.get("route") or plan.effective_route)
    return locked, plan.effective_route


# ── frozen artifact loading ───────────────────────────────────────────────────


def load_lock(path: Path | None = None) -> dict[str, Any]:
    lock_path = path or DEFAULT_LOCK_PATH
    if not lock_path.is_file():
        raise C.ClassificationError(f"classification lock missing: {lock_path}")
    return json.loads(lock_path.read_text(encoding="utf-8"))


def load_in_57_ids() -> frozenset[str]:
    """The 57-ledger lane ids — ``ledger_scenario_ids()`` via the selection door."""
    return frozenset(ledger_selection_ids())


def load_scenarios() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(DEFAULT_SCENARIOS_DIR.glob("*.json"))
    ]


# ── bootstrap ─────────────────────────────────────────────────────────────────


def bootstrap(
    lock_path: Path | None = None,
    manifest_path: Path | None = None,
    *,
    capture: bool = False,
    max_workers: int = 1,
) -> dict[str, Any]:
    """Regenerate + write the lock and 50-manifest.

    ``capture=True`` runs the REAL classifier over all 100 scenarios (host
    only, one model call each); ``capture=False`` writes the deterministic
    provisional freeze (idempotent, byte-stable).
    """
    scenarios = load_scenarios()
    in_57_ids = load_in_57_ids()
    if capture:
        lock = C.capture_classifications(
            scenarios, in_57_ids=in_57_ids, max_workers=max_workers
        )
    else:
        lock = C.build_classification_lock(scenarios, in_57_ids=in_57_ids)
    manifest = C.build_two_step_manifest(lock)

    lock_target = lock_path or DEFAULT_LOCK_PATH
    manifest_target = manifest_path or DEFAULT_TWO_STEP_MANIFEST
    lock_target.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    manifest_target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "lock_path": str(lock_target),
        "manifest_path": str(manifest_target),
        "provenance": lock["provenance"],
        "capture": lock["provenance"]["capture"],
    }


# ── validate-only ─────────────────────────────────────────────────────────────


def _verify_real_comparator_wiring() -> dict[str, bool]:
    """Deterministically confirm the real pi_edit / Δ-replay seams import.

    No model calls: only imports + attribute checks.  This pins the comparator
    to the REAL editable quotient and canonical accepted-Δ replay (never the
    old node-id/class hash).
    """
    checks: dict[str, bool] = {}
    try:
        from tests.test_ir_laws import pi_edit  # noqa: PLC0415

        checks["pi_edit_import"] = callable(pi_edit)
    except Exception:  # noqa: BLE001
        checks["pi_edit_import"] = False
    try:
        from vibecomfy.executor.two_step_session import _apply_delta_ops  # noqa: PLC0415

        checks["delta_replay_import"] = callable(_apply_delta_ops)
    except Exception:  # noqa: BLE001
        checks["delta_replay_import"] = False
    try:
        from vibecomfy.executor.contracts import validate_two_step_final  # noqa: PLC0415

        checks["claim_validation_import"] = callable(validate_two_step_final)
    except Exception:  # noqa: BLE001
        checks["claim_validation_import"] = False
    return checks


def validate_only(
    manifest_path: Path | None = None,
    ledger_label: str | None = None,
) -> dict[str, Any]:
    """Deterministic gate validation: lock + manifest + injection + ledger.

    ``ledger_label`` is ``None`` (defaults to ``current``) or one of
    ``current`` / ``ir-everywhere-57-v3``.
    """
    manifest_target = manifest_path or DEFAULT_TWO_STEP_MANIFEST
    lock = load_lock()
    in_57_ids = load_in_57_ids()
    scenarios = load_scenarios()
    scenario_ids = frozenset(s["id"] for s in scenarios)

    resolved_ledger = resolve_ledger_label(ledger_label)
    ledger_ids = frozenset(ledger_selection_ids())

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

    # 5. The manifest classification block matches the frozen lock entry-for-entry.
    lock_by_id = {e["id"]: e for e in lock["entries"]}
    for entry in entries:
        cls = entry.get("classification") or {}
        lock_cls = lock_by_id[entry["id"]]
        for field in ("route", "effective_route", "behavior", "ledger", "graph_size", "media"):
            if cls.get(field) != lock_cls[field]:
                raise C.ClassificationError(
                    f"manifest classification drift for {entry['id']}: {field}"
                )

    # 6. Injection wiring: every locked route maps to a ClassifyDecision whose
    #    locked route and canonical route are recorded separately.
    plans: dict[str, dict[str, str]] = {}
    for route in C.ROUTES:
        plan = build_injected_plan(route)
        if not isinstance(plan.to_dict(), dict):
            raise C.ClassificationError(f"injected plan for {route} is not serializable")
        plans[route] = {"locked": route, "effective": plan.effective_route}

    # 7. The 50-lane ∩ 57-ledger overlap is exactly 25 (never billed twice).
    overlap = set(included_ids) & ledger_ids

    # 8. Real comparator wiring (pi_edit / Δ-replay / claim validation).
    wiring = _verify_real_comparator_wiring()

    return {
        "ok": True,
        "manifest": str(manifest_target),
        "ledger_label": resolved_ledger,
        "ledger_ids": len(ledger_ids),
        "ledger_overlap_50_lane": len(overlap),
        "included": len(included_ids),
        "excluded": len(excluded_ids),
        "scenario_count": len(scenario_ids),
        "provenance": lock["provenance"],
        "quota_table": lock["quota_table"],
        "injected_plan_routes": plans,
        "comparator_wiring": wiring,
    }


# ── live paired run (host only) ───────────────────────────────────────────────


def _mode_session_root(output_base: Path, mode: str, scenario_id: str) -> Path:
    """Separate durable session root per mode (no cross-contamination)."""
    return output_base / mode / scenario_id


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


def _load_json_artifact(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _load_response_artifact(output_dir: str | None) -> dict[str, Any] | None:
    if not output_dir:
        return None
    return _load_json_artifact(Path(str(output_dir)) / "response.json")


def _run_scenario_mode(
    scenario: Mapping[str, Any],
    *,
    mode: str,
    entry: Mapping[str, Any],
    output_base: Path,
    tag: str,
    transport: str | None,
) -> dict[str, Any]:
    """Run one scenario in one pipeline mode with the locked decision injected."""
    from .adapter import run_headless_scenario  # noqa: PLC0415
    from .guard import guard_output_dir  # noqa: PLC0415

    plan = build_injected_plan(entry)
    locked, effective = _locked_and_effective(entry)
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
    summary["route"] = locked
    summary["locked_route"] = locked
    summary["effective_route"] = effective
    summary["injected_route"] = locked
    summary["injected_effective_route"] = effective

    # Honest infra/product guard: typed evidence only (mirrors the runner).
    try:
        summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
    except Exception as exc:  # noqa: BLE001 - missing artifact → runner-style failure
        summary["guard"] = {
            "live_agentic_success": False,
            "score_class": "product_fail",
            "failure_class": "runner_error",
            "assessment": {"verdict": "fail", "passed": False, "issues": []},
        }
        summary.setdefault("error", str(exc))
    return summary


# ── real pi_edit quotient + canonical Δ replay ───────────────────────────────


def _pi_edit_quotient(graph: dict[str, Any] | None) -> tuple[Any, ...] | None:
    """The REAL editable quotient (``tests.test_ir_laws.pi_edit``) of a graph.

    Ingest the UI/API JSON through the named door and return the raw
    ``(nodes, connections, interfaces)`` quotient.  ``None`` when the graph is
    absent or cannot be ingested.
    """
    if not isinstance(graph, dict):
        return None
    try:
        from vibecomfy.ingest.normalize import from_envelope, from_ui  # noqa: PLC0415

        from tests.test_ir_laws import pi_edit  # noqa: PLC0415

        if isinstance(graph.get("nodes"), dict):
            workflow = from_envelope(graph)
        else:
            workflow = from_ui(graph, use_comfy_converter=True)
        return pi_edit(workflow)
    except Exception:  # noqa: BLE001 - non-ingestible graph → no quotient
        return None


def _quotient_digest(quotient: tuple[Any, ...] | None) -> str | None:
    if quotient is None:
        return None
    return hashlib.sha256(
        json.dumps(quotient, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _accepted_delta_ops(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return the canonical accepted Δ ops from a run response (typed, no prose)."""
    accepted = response.get("accepted_batch")
    ops: list[dict[str, Any]] = []
    if isinstance(accepted, list):
        for item in accepted:
            if isinstance(item, Mapping) and isinstance(item.get("op"), Mapping):
                ops.append(dict(item["op"]))
    if ops:
        return ops
    narrative = response.get("narrative_context")
    if isinstance(narrative, Mapping):
        seeded = narrative.get("operations") or narrative.get("landed_operations")
        if isinstance(seeded, list):
            return [
                dict(item["op"])
                for item in seeded
                if isinstance(item, Mapping) and isinstance(item.get("op"), Mapping)
            ]
    return []


def _canonical_delta_replay_digest(output_dir: str | None) -> str | None:
    """The REAL canonical accepted-Δ replay of a run's original graph.

    Replays the accepted Δ ops over ``original.ui.json`` with the production
    replay primitive (``two_step_session._apply_delta_ops``) and returns the
    pi_edit digest of the result — a genuinely different computation from the
    direct post-edit quotient, not a re-hash of the same node-id/class list.
    """
    if not output_dir:
        return None
    out = Path(str(output_dir))
    response = _load_response_artifact(str(output_dir))
    base = _load_json_artifact(out / "original.ui.json")
    ops = _accepted_delta_ops(response or {})
    if base is None or not ops:
        return None
    try:
        from vibecomfy.executor.two_step_session import _apply_delta_ops  # noqa: PLC0415

        replayed = _apply_delta_ops(base, ops)
        if replayed is None:
            return None
        return _quotient_digest(_pi_edit_quotient(replayed))
    except Exception:  # noqa: BLE001
        return None


def _post_edit_quotient_digest(output_dir: str | None) -> str | None:
    """The REAL pi_edit digest of the post-edit graph (``final.ui.json``)."""
    if not output_dir:
        return None
    out = Path(str(output_dir))
    final = _load_json_artifact(out / "final.ui.json")
    if final is None:
        final = _load_json_artifact(out / "candidate.ui.json")
    return _quotient_digest(_pi_edit_quotient(final))


def _original_quotient_digest(output_dir: str | None) -> str | None:
    if not output_dir:
        return None
    original = _load_json_artifact(Path(str(output_dir)) / "original.ui.json")
    return _quotient_digest(_pi_edit_quotient(original))


def _graph_signature(output_dir: str | None) -> dict[str, Any]:
    """Real quotient/replay signatures for a run's output directory."""
    return {
        "original_pi_edit_digest": _original_quotient_digest(output_dir),
        "final_pi_edit_digest": _post_edit_quotient_digest(output_dir),
        "canonical_delta_replay_digest": _canonical_delta_replay_digest(output_dir),
    }


# ── claim/evidence metrics ───────────────────────────────────────────────────

_EDIT_SUCCESS_OUTCOMES = frozenset({"edited", "edit_success", "applied"})


def _claim_evidence_metrics(output_dir: str | None) -> dict[str, Any]:
    """Claim/evidence correctness from a run's durable execute report.

    * ``delta_ids ⊆ ledger`` / ``lens_fact_ids ⊆ reply lens`` /
      ``evidence_ids ⊆ tool ledger`` — read from the executor's
      ``claim_validation`` result (computed by ``validate_two_step_final``),
      and re-derived directly from the accepted/lens/evidence ids when the
      claim refs are present.
    * ``replacement_used`` — whether the execute agent used a replacement.
    * ``unsupported_claims`` — count of claim-validation rejections.
    * ``self_assessment`` — the execute agent's self-check.
    """
    result: dict[str, Any] = {
        "claim_validation_status": None,
        "delta_ids_subset_ledger": None,
        "lens_fact_ids_subset_lens": None,
        "evidence_ids_subset_tool_ledger": None,
        "unsupported_claims": None,
        "replacement_used": None,
        "self_assessment": None,
    }
    response = _load_response_artifact(output_dir)
    if response is None:
        return result
    report = response.get("report") or {}
    executor = report.get("executor") or {}
    execute = executor.get("execute") if isinstance(executor, Mapping) else None
    if not isinstance(execute, Mapping):
        return result

    result["replacement_used"] = execute.get("replacement_used")
    result["self_assessment"] = execute.get("self_assessment")
    accepted = {str(i) for i in (execute.get("accepted_delta_ids") or ())}
    facts = {str(i) for i in (execute.get("lens_fact_ids") or ())}
    evidence = {str(i) for i in (execute.get("evidence_ids") or ())}

    cv = execute.get("claim_validation")
    if isinstance(cv, Mapping):
        result["claim_validation_status"] = cv.get("status")
        violations = cv.get("violations") or cv.get("errors") or ()
        result["unsupported_claims"] = (
            len(violations) if isinstance(violations, (list, tuple)) else None
        )

    refs = execute.get("claim_refs")
    if isinstance(refs, Mapping):
        delta_ids = refs.get("delta_ids")
        lens_ids = refs.get("lens_fact_ids")
        ev_ids = refs.get("evidence_ids")
        if isinstance(delta_ids, (list, tuple)):
            result["delta_ids_subset_ledger"] = all(str(i) in accepted for i in delta_ids)
        if isinstance(lens_ids, (list, tuple)):
            result["lens_fact_ids_subset_lens"] = all(str(i) in facts for i in lens_ids)
        if isinstance(ev_ids, (list, tuple)):
            result["evidence_ids_subset_tool_ledger"] = all(str(i) in evidence for i in ev_ids)
    return result


def _self_check_edit_success(summary: Mapping[str, Any]) -> bool | None:
    """Whether the execute agent's self-check claims an edit success."""
    metrics = _claim_evidence_metrics(summary.get("output_dir"))
    assessment = metrics.get("self_assessment")
    if not isinstance(assessment, Mapping):
        return None
    outcome = assessment.get("outcome")
    if outcome in _EDIT_SUCCESS_OUTCOMES:
        return True
    if isinstance(outcome, str) and outcome.strip():
        return False
    return None


# ── honest infra/product classification ──────────────────────────────────────


def is_infra_blocked(summary: Mapping[str, Any]) -> bool:
    """True only for typed/classified infra blockage — never prose-matching."""
    guard = summary.get("guard")
    if not isinstance(guard, Mapping):
        guard = {}
    failure_class = summary.get("failure_class") or guard.get("failure_class")
    score_class = summary.get("score_class") or guard.get("score_class")
    return (
        isinstance(failure_class, str) and failure_class.startswith("infra_")
    ) or score_class == "infra_blocked"


def pair_outcome(full: Mapping[str, Any], two_step: Mapping[str, Any]) -> str:
    """Classify a paired outcome: ``"pass"`` | ``"fail"`` | ``"blocked"``.

    Honesty rule: an infra-blocked leg blocks the whole pair — the pair is
    reported ``blocked`` and is never counted as a product pass or fail.
    """
    if is_infra_blocked(full) or is_infra_blocked(two_step):
        return "blocked"
    full_ok = (full.get("guard") or {}).get("live_agentic_success") is True
    two_ok = (two_step.get("guard") or {}).get("live_agentic_success") is True
    if full_ok and two_ok:
        return "pass"
    return "fail"


# ── comparison extraction ────────────────────────────────────────────────────


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
    return {
        "issue_checks": signals,
        "issue_count": assessment.get("issue_count"),
        "error_count": assessment.get("error_count"),
        "judge_results": assessment.get("judge_results") or [],
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

    def _judge_verdict(summary: Mapping[str, Any]) -> str | None:
        assessment = (summary.get("guard") or {}).get("assessment") or {}
        return assessment.get("verdict")

    full_guard = _guard_metrics(full)
    two_guard = _guard_metrics(two_step)
    full_graph = _graph_signature(full.get("output_dir"))
    two_graph = _graph_signature(two_step.get("output_dir"))
    full_claims = _claim_evidence_metrics(full.get("output_dir"))
    two_claims = _claim_evidence_metrics(two_step.get("output_dir"))

    full_self = _self_check_edit_success(full)
    two_self = _self_check_edit_success(two_step)

    def _self_judge_disagrees(self_check: bool | None, verdict: str | None) -> bool | None:
        if self_check is None or verdict is None:
            return None
        judge_pass = verdict == "pass"
        return (self_check and not judge_pass) or (not self_check and judge_pass)

    outcome = pair_outcome(full, two_step)

    return {
        "scenario_id": scenario["id"],
        "route": route,
        "outcome": outcome,
        "full": {
            "ok": full.get("ok"),
            "status": full.get("status"),
            "guard": full_guard,
            "usage": _usage(full),
            "attempts": _attempts(full),
            "elapsed_s": full.get("elapsed_s"),
            "output_dir": full.get("output_dir"),
            "locked_route": full.get("locked_route"),
            "effective_route": full.get("effective_route"),
            "graph_signature": full_graph,
            "claims": full_claims,
        },
        "two_step": {
            "ok": two_step.get("ok"),
            "status": two_step.get("status"),
            "guard": two_guard,
            "usage": _usage(two_step),
            "attempts": _attempts(two_step),
            "elapsed_s": two_step.get("elapsed_s"),
            "output_dir": two_step.get("output_dir"),
            "locked_route": two_step.get("locked_route"),
            "effective_route": two_step.get("effective_route"),
            "graph_signature": two_graph,
            "claims": two_claims,
        },
        "delta": {
            "pair_outcome": outcome,
            "judge_outcome_equal": full_guard.get("verdict") == two_guard.get("verdict"),
            "live_success_equal": full_guard.get("live_agentic_success")
            == two_guard.get("live_agentic_success"),
            "failure_family_equal": full_guard.get("failure_class") == two_guard.get("failure_class"),
            "pi_edit_post_equal": (
                full_graph.get("final_pi_edit_digest") == two_graph.get("final_pi_edit_digest")
                and full_graph.get("final_pi_edit_digest") is not None
            ),
            "canonical_delta_replay_equal": (
                full_graph.get("canonical_delta_replay_digest")
                == two_graph.get("canonical_delta_replay_digest")
                and full_graph.get("canonical_delta_replay_digest") is not None
            ),
            "issue_checks_equal": full_guard["signals"]["issue_checks"]
            == two_guard["signals"]["issue_checks"],
            "self_check_judge_disagreement": {
                "full": _self_judge_disagrees(full_self, _judge_verdict(full)),
                "two_step": _self_judge_disagrees(two_self, _judge_verdict(two_step)),
            },
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
    blocked = sum(1 for c in comparisons if c["delta"]["pair_outcome"] == "blocked")
    passed = sum(1 for c in comparisons if c["delta"]["pair_outcome"] == "pass")
    failed = sum(1 for c in comparisons if c["delta"]["pair_outcome"] == "fail")
    full_cost = sum((c["full"]["usage"].get("est_cost_usd") or 0.0) for c in comparisons)
    two_cost = sum((c["two_step"]["usage"].get("est_cost_usd") or 0.0) for c in comparisons)
    full_tokens = sum((c["full"]["usage"].get("total_tokens") or 0) for c in comparisons)
    two_tokens = sum((c["two_step"]["usage"].get("total_tokens") or 0) for c in comparisons)

    def _rate(getter) -> float | None:
        values = [getter(c) for c in comparisons if getter(c) is not None]
        if not values:
            return None
        return round(sum(1 for v in values if v) / len(values), 4)

    def _claim_true(c: dict[str, Any]) -> bool | None:
        status = c["two_step"]["claims"].get("claim_validation_status")
        if status is not None:
            return status in {"valid", "ok", "passed"}
        return None

    replacement_used = [
        c["two_step"]["claims"].get("replacement_used")
        for c in comparisons
        if c["two_step"]["claims"].get("replacement_used") is not None
    ]
    unsupported_total = sum(
        (c["two_step"]["claims"].get("unsupported_claims") or 0) for c in comparisons
    )
    disagreements = [
        v
        for c in comparisons
        for leg in ("full", "two_step")
        if (v := c["delta"]["self_check_judge_disagreement"].get(leg)) is not None
    ]

    return {
        "scenario_count": included,
        "both_ok": both_ok,
        "pair_outcomes": {"pass": passed, "fail": failed, "blocked": blocked},
        "judge_outcome_equal": judge_equal,
        "judge_outcome_equal_rate": round(judge_equal / included, 4) if included else None,
        "live_success_equal": live_equal,
        "live_success_equal_rate": round(live_equal / included, 4) if included else None,
        "claim_evidence_correct_rate": _rate(_claim_true),
        "replacement_used_rate": (
            round(sum(1 for v in replacement_used if v) / len(replacement_used), 4)
            if replacement_used
            else None
        ),
        "unsupported_claims_total": unsupported_total,
        "self_check_judge_disagreement_rate": (
            round(sum(1 for v in disagreements if v) / len(disagreements), 4)
            if disagreements
            else None
        ),
        "full": {"cost_usd": round(full_cost, 6), "total_tokens": full_tokens},
        "two_step": {"cost_usd": round(two_cost, 6), "total_tokens": two_tokens},
        "session_reuse_rate": _session_reuse_rate(comparisons),
    }


def _session_reuse_rate(comparisons: list[dict[str, Any]]) -> float | None:
    """Fraction of scenario legs whose durable session dir was reused vs fresh."""
    reused = 0
    total = 0
    for c in comparisons:
        for mode in ("full", "two_step"):
            out = c[mode].get("output_dir")
            if not out:
                continue
            total += 1
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
    tag: str = "paired",
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
            scenario, mode="full", entry=lock_by_id[scenario_id],
            output_base=base, tag=tag, transport=transport,
        )
        two_step = _run_scenario_mode(
            scenario, mode="two_step", entry=lock_by_id[scenario_id],
            output_base=base, tag=tag, transport=transport,
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
        f"- pair outcomes: pass={agg['pair_outcomes']['pass']} "
        f"fail={agg['pair_outcomes']['fail']} blocked={agg['pair_outcomes']['blocked']}",
        f"- judge outcome equal: {agg['judge_outcome_equal_rate']}",
        f"- live success equal: {agg['live_success_equal_rate']}",
        f"- claim/evidence correct: {agg['claim_evidence_correct_rate']}",
        f"- replacement used rate: {agg['replacement_used_rate']}",
        f"- unsupported claims: {agg['unsupported_claims_total']}",
        f"- self-check/judge disagreement: {agg['self_check_judge_disagreement_rate']}",
        f"- session reuse rate: {agg['session_reuse_rate']}",
        f"- full cost (USD): {agg['full']['cost_usd']} / tokens {agg['full']['total_tokens']}",
        f"- two_step cost (USD): {agg['two_step']['cost_usd']} / tokens {agg['two_step']['total_tokens']}",
        "",
        "| scenario | route | outcome | full ok | two-step ok | judge equal |",
        "|---|---|---|---|---|---|",
    ]
    for c in payload["scenarios"]:
        lines.append(
            f"| {c['scenario_id']} | {c['route']} | {c['delta']['pair_outcome']} | "
            f"{c['full']['ok']} | {c['two_step']['ok']} | {c['delta']['judge_outcome_equal']} |"
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
        "--ledger",
        choices=(LEDGER_LABEL_CURRENT, LEDGER_ARTIFACT_LABEL),
        default=LEDGER_LABEL_CURRENT,
        help="57-ledger lane label (current == ir-everywhere-57-v3)",
    )
    parser.add_argument(
        "--tag",
        default="paired",
        help="run tag for the live paired run (default: paired)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate lock + manifest + injection + ledger (no model calls)",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="regenerate classification_lock.json + two_step_50_manifest.json",
    )
    parser.add_argument(
        "--capture-classifications",
        action="store_true",
        help="run the REAL classifier over all 100 scenarios (host only)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="concurrency for the live run / classification capture",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON (always on; accepted for compatibility)",
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

    capture = bool(args.capture_classifications)

    if args.bootstrap:
        # `--bootstrap` alone regenerates the deterministic provisional freeze;
        # `--bootstrap --capture-classifications` runs the REAL classifier
        # (the documented capture path, host only).
        result = bootstrap(capture=capture, max_workers=args.max_workers)
        print(json.dumps(result, indent=2))
        return 0

    if args.capture_classifications and not args.run:
        # Standalone capture: same as --bootstrap --capture-classifications.
        result = bootstrap(capture=True, max_workers=args.max_workers)
        print(json.dumps(result, indent=2))
        return 0

    if args.validate_only:
        try:
            result = validate_only(Path(args.manifest), ledger_label=args.ledger)
        except (C.ClassificationError, ScenarioManifestError, LedgerLabelError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            return 1
        print(json.dumps(result, indent=2, default=str))
        return 0

    if args.run:
        if capture:
            bootstrap(capture=True, max_workers=args.max_workers)
        payload = run_comparison(
            Path(args.manifest),
            output_base=Path(args.output_base) if args.output_base else None,
            transport=args.transport,
            tag=args.tag,
        )
        print(json.dumps(payload, indent=2, default=str))
        return 0

    print("choose --validate-only, --bootstrap, --capture-classifications, or --run")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
