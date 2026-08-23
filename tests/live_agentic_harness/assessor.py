"""Deep assessment of live agentic run artifacts.

The live agentic harness already verifies flow metadata (real dispatcher,
agentic model behavior, status == success).  This module inspects the actual
run artifacts to catch failures that metadata alone cannot:

* response.ok == false or response.error set
* readiness blockers
* graph unchanged when an edit was expected
* hard diagnostics (severity == error) from agent-edit turns
* upstream dependency failures such as Hivemind HTTP 500
* implementation_result.ok == false
* validation gates that failed for an apply/edit route
* (when enabled) assessment-first research rules: question-before-search,
  query relevance, required-Hivemind invocation, citation resolution to
  returned evidence IDs, no-local-search research path, and evidence-pack
  capture
* (when enabled) an LLM intent judge that scores the edit against the query

The deterministic checks run first. Judges run afterward: grounded-refusal
for allowlisted no-edit candidates, edit-intent for expected graph changes,
and a rubric-driven semantic-answer judge for D13 non-edits. Outages are
undetermined; only ``pass`` satisfies a scenario.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.executor.graph_facts import GraphFieldTarget, compare_effective_field

from .intent_judge import (
    judge_edit_intent,
    judge_grounded_refusal,
    judge_semantic_answer,
)
from .research_assessment import assess_research_evidence
from .lineage_check import assess_artifact_lineage


_ERROR_SEVERITIES = {"error", "fatal"}

# Critical upstream failures that should always fail a live run.
_UPSTREAM_FAILURE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Hivemind HTTP error.*500", re.IGNORECASE),
    re.compile(r"HTTP Error 500", re.IGNORECASE),
    re.compile(r"Internal Server Error", re.IGNORECASE),
]

# Soft capacity warnings: surfaced so humans see them, but not treated as hard
# failures on their own (the run may still succeed via fallback evidence).
_SOFT_WARNING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"HTTP Error 429", re.IGNORECASE),
    re.compile(r"Too Many Requests", re.IGNORECASE),
]

# Canonical public route vocabulary (mirrors vibecomfy.executor.contracts).
# Edit routes may land graph changes; non-edit routes never do.  Exemption
# from the landed-count guard is decided from the envelope's canonical route,
# never from the agent's self-declared outcome/reason labels.
_EDIT_ROUTES = frozenset({"revise", "adapt", "reorganise"})
_NON_EDIT_ROUTES = frozenset({
    "clarify",
    "respond",
    "inspect",
    "research",
    "requires_custom_nodes",
})


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load a JSON artifact if it exists and is valid."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _walk(obj: Any) -> Any:
    """Recursively yield every dict/string node in a JSON-like structure."""
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)
    else:
        yield obj


def _has_successful_candidate(response: Mapping[str, Any]) -> bool:
    """Return true when the response produced an applied candidate graph."""
    if response.get("ok") is not True:
        return False
    if response.get("graph_unchanged") is not False:
        return False
    return isinstance(response.get("candidate_graph"), Mapping) or isinstance(
        response.get("candidate"), Mapping
    )


def _queue_validate_skipped_for_successful_candidate(response: Mapping[str, Any]) -> bool:
    """Return true when queue validation is absent, not failed.

    ``queue_validate_ok`` is fail-closed in the agent-edit gate map.  Some live
    batch paths can return a real changed candidate without running the queue
    stage at all; that missing stage should not be scored the same as a
    concrete queue blocker.
    """
    if not _has_successful_candidate(response):
        return False
    gates = response.get("gates")
    if not isinstance(gates, Mapping) or gates.get("queue_validate_ok") is not False:
        return False
    debug = response.get("debug")
    if not isinstance(debug, Mapping):
        return False
    stage_snapshots = debug.get("stage_snapshots")
    if not isinstance(stage_snapshots, list):
        return False
    stage_names = {
        str(item.get("stage"))
        for item in stage_snapshots
        if isinstance(item, Mapping) and item.get("stage") is not None
    }
    if "queue_validate" in stage_names:
        return False

    def _has_queue_blockers(value: Any) -> bool:
        if isinstance(value, list):
            return bool(value)
        if isinstance(value, tuple):
            return bool(value)
        return False

    report = response.get("report")
    if isinstance(report, Mapping) and _has_queue_blockers(report.get("queue_blockers")):
        return False
    if _has_queue_blockers(debug.get("queue_blockers")):
        return False
    return True


def _batch_turn_failed(turn: Mapping[str, Any]) -> bool:
    """Return true for exploratory batch turns that did not contribute edits."""
    if turn.get("batch_ok") is False:
        return True
    if (turn.get("landed_op_count") or 0) == 0 and (turn.get("raw_landed_op_count") or 0) == 0:
        for diagnostic in turn.get("diagnostics") or []:
            if isinstance(diagnostic, Mapping) and diagnostic.get("severity") in _ERROR_SEVERITIES:
                return True
    return False


def _walk_hard_diagnostic_scope(obj: Any, *, skip_failed_batch_turns: bool) -> Any:
    """Yield nodes for hard-diagnostic checks, excluding failed scratch turns.

    Agent-edit may keep a full transcript of exploratory batch attempts in
    ``change_details.batch_turns`` even when the executor ultimately returns a
    successful candidate from an earlier safe edit. Those failed attempts are
    useful audit trail, but they are not active defects in the applied graph.
    """
    if isinstance(obj, dict):
        yield obj
        for key, value in obj.items():
            if (
                skip_failed_batch_turns
                and key == "batch_turns"
                and isinstance(value, list)
            ):
                for item in value:
                    if isinstance(item, Mapping) and _batch_turn_failed(item):
                        continue
                    yield from _walk_hard_diagnostic_scope(
                        item,
                        skip_failed_batch_turns=skip_failed_batch_turns,
                    )
                continue
            yield from _walk_hard_diagnostic_scope(
                value,
                skip_failed_batch_turns=skip_failed_batch_turns,
            )
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_hard_diagnostic_scope(
                item,
                skip_failed_batch_turns=skip_failed_batch_turns,
            )
    else:
        yield obj


def _collect_hard_diagnostics(
    response: Mapping[str, Any],
    *,
    accepted_safe_refusal: bool = False,
) -> list[str]:
    """Return messages from any object with severity error/fatal."""
    issues: list[str] = []
    skip_failed_batch_turns = (
        _has_successful_candidate(response) or accepted_safe_refusal
    )
    for node in _walk_hard_diagnostic_scope(
        response,
        skip_failed_batch_turns=skip_failed_batch_turns,
    ):
        if not isinstance(node, dict):
            continue
        if node.get("severity") not in _ERROR_SEVERITIES:
            continue
        message = node.get("message")
        if not isinstance(message, str):
            detail = node.get("detail")
            message = json.dumps(detail, sort_keys=True) if isinstance(detail, dict) else str(node)
        message = message.strip()
        if message and message not in issues:
            issues.append(message)
    return issues


def _collect_pattern_matches(
    response: Mapping[str, Any],
    patterns: list[re.Pattern[str]],
) -> list[str]:
    """Return distinct string values matching any of the supplied patterns."""
    issues: list[str] = []
    seen: set[str] = set()
    for node in _walk(response):
        if not isinstance(node, str):
            continue
        for pattern in patterns:
            if pattern.search(node):
                if node not in seen:
                    seen.add(node)
                    issues.append(node)
                break
    return issues


def _canonical_route(response: Mapping[str, Any]) -> str:
    """Return the canonical public route carried by the response envelope.

    The authoritative field is the top-level ``route`` (written by
    ``AgentTurnResult.to_dict`` in vibecomfy.executor.contracts); the same
    public route is mirrored in ``evidence.classification.route`` and
    ``report.executor.plan.route``.  Missing/non-string routes resolve to
    the empty string so an envelope without a route can never claim a
    non-edit exemption (fail closed).
    """
    route = response.get("route")
    if isinstance(route, str):
        return route
    evidence = response.get("evidence")
    if isinstance(evidence, Mapping):
        classification = evidence.get("classification")
        if isinstance(classification, Mapping) and isinstance(classification.get("route"), str):
            return classification["route"]
    report = response.get("report")
    if isinstance(report, Mapping):
        executor = report.get("executor")
        if isinstance(executor, Mapping):
            plan = executor.get("plan")
            if isinstance(plan, Mapping) and isinstance(plan.get("route"), str):
                return plan["route"]
    return ""


def _explicitly_non_edit_route(response: Mapping[str, Any]) -> bool:
    """Return True when the envelope's canonical route is a non-edit route.

    The route is read from the envelope (``response.route``) — never from the
    agent's self-declared ``no_candidate_reason`` / ``outcome.kind``.  An
    edit-route envelope self-labeling ``outcome.kind=clarify`` or
    ``no_candidate_reason=route_not_applyable`` is NOT exempt: a claimed edit
    (graph_unchanged=false) must still be backed by a positive landed count.
    These routes are scored by their own structured checks
    (``no_candidate_reason`` / ``outcome_kind``) and by the route/graph
    consistency check; demanding a positive landed operation count for them
    would be wrong — a truthful non-edit route has no operations to count.
    """
    return _canonical_route(response) in _NON_EDIT_ROUTES


def _landed_operation_count(response: Mapping[str, Any]) -> Any:
    """Return ``change_details.landed_operation_count`` (any JSON value)."""
    change_details = response.get("change_details")
    if isinstance(change_details, Mapping):
        return change_details.get("landed_operation_count")
    return None


def _expects_graph_changed(
    scenario: Mapping[str, Any] | None,
    response: Mapping[str, Any] | None,
) -> bool:
    """Decide whether this scenario should have produced a graph change.

    Explicit scenario configuration wins, then we fall back to reading the
    agent's own classification/plan from the response.
    """
    if scenario is not None:
        assessment = scenario.get("assessment")
        if isinstance(assessment, dict) and "expect_graph_changed" in assessment:
            return bool(assessment["expect_graph_changed"])

    if response is None:
        return False

    plan = response.get("report", {}).get("executor", {}).get("plan") or {}
    if plan.get("implement") is True and plan.get("route") in {"adapt", "revise"}:
        return True

    return False


def _expected_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
    """Return explicitly accepted public outcome kinds for this scenario."""
    if scenario is None:
        return set()
    assessment = scenario.get("assessment")
    if not isinstance(assessment, Mapping):
        return set()
    raw = assessment.get("expected_outcome_kinds")
    if raw is None:
        raw = assessment.get("expected_outcome_kind")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    return set()


_SAFE_REFUSAL_DEFAULT_KINDS = frozenset({"clarify", "requires_custom_nodes"})


def _scenario_requires_custom_nodes(scenario: Mapping[str, Any] | None) -> bool:
    if not isinstance(scenario, Mapping):
        return False
    tags = scenario.get("_tags")
    return isinstance(tags, Mapping) and tags.get("requires_custom_nodes") is True


def _response_proves_class_absence(response: Mapping[str, Any] | None) -> bool:
    """True when the run proved a named class is absent from schema/runtime."""
    if not isinstance(response, Mapping):
        return False
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        missing = outcome.get("missing_classes")
        if isinstance(missing, (list, tuple)) and any(missing):
            return True
    report = response.get("report")
    if isinstance(report, Mapping):
        blocker = report.get("authoring_blocker")
        if isinstance(blocker, Mapping):
            missing = blocker.get("missing_runtime_classes")
            if isinstance(missing, (list, tuple)) and any(missing):
                return True
    return False


def _allowed_safe_refusal_outcome_kinds(
    scenario: Mapping[str, Any] | None,
    response: Mapping[str, Any] | None = None,
) -> set[str]:
    """Return no-edit outcome kinds accepted as safe refusals for edit scenarios.

    An explicit scenario allowlist always wins (including an empty list).
    Otherwise default ``clarify`` / ``requires_custom_nodes`` only when the
    scenario is tagged ``requires_custom_nodes`` or the run proved a named
    class is absent. Not a blanket default on every edit scenario.
    """
    if scenario is None:
        return set()
    assessment = scenario.get("assessment")
    raw = None
    if isinstance(assessment, Mapping):
        raw = assessment.get("allow_safe_refusal_outcome_kinds")
        if raw is None:
            raw = assessment.get("allow_safe_refusal_outcome_kind")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    if _scenario_requires_custom_nodes(scenario) or _response_proves_class_absence(
        response
    ):
        return set(_SAFE_REFUSAL_DEFAULT_KINDS)
    return set()


def _assessment_config(scenario: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return the scenario assessment config, if present."""
    if scenario is None:
        return {}
    assessment = scenario.get("assessment")
    return assessment if isinstance(assessment, Mapping) else {}


def _scenario_kind(scenario: Mapping[str, Any] | None) -> str:
    """Classify the scenario as edit, semantic_product, or health_control."""
    if scenario is None:
        return "unknown"
    classification = scenario.get("classification")
    if isinstance(classification, Mapping):
        kind = classification.get("kind")
        if kind in {"health_control", "semantic_product", "edit"}:
            return str(kind)
    if scenario.get("answer_rubric"):
        return "semantic_product"
    return "edit"


def _excluded_from_semantic_product_rates(scenario: Mapping[str, Any] | None) -> bool:
    if scenario is None:
        return False
    classification = scenario.get("classification")
    if isinstance(classification, Mapping) and (
        classification.get("excluded_from_semantic_product_rates") is True
        or classification.get("kind") == "health_control"
    ):
        return True
    return False


def _answer_rubric(scenario: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if scenario is None:
        return None
    rubric = scenario.get("answer_rubric")
    return rubric if isinstance(rubric, Mapping) else None


def _research_payloads(
    output_dir: Path,
    response: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    """Return every structured research payload captured for this turn."""
    payloads: list[Mapping[str, Any]] = []
    evidence = response.get("evidence")
    if isinstance(evidence, Mapping) and isinstance(evidence.get("research"), Mapping):
        payloads.append(evidence["research"])
    report = response.get("report")
    executor = report.get("executor") if isinstance(report, Mapping) else None
    if isinstance(executor, Mapping) and isinstance(executor.get("research"), Mapping):
        payloads.append(executor["research"])
    artifact = _load_json(output_dir / "research.json")
    if isinstance(artifact, Mapping):
        payloads.append(artifact)
    return payloads


def _assess_executed_research(
    output_dir: Path,
    response: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Require model, tool, and evidence activity for research controls."""
    config = _assessment_config(scenario)
    if config.get("require_executed_research") is not True:
        return []

    report = response.get("report")
    executor = report.get("executor") if isinstance(report, Mapping) else None
    usage = executor.get("deepseek_usage") if isinstance(executor, Mapping) else None
    n_calls = usage.get("n_calls") if isinstance(usage, Mapping) else None
    attempts = executor.get("model_attempts") if isinstance(executor, Mapping) else None
    has_model_call = (
        isinstance(n_calls, int)
        and not isinstance(n_calls, bool)
        and n_calls > 0
    ) or (isinstance(attempts, list) and len(attempts) > 0)

    payloads = _research_payloads(output_dir, response)
    tool_calls = max(
        (
            int(payload.get("tool_calls_executed", 0))
            for payload in payloads
            if isinstance(payload.get("tool_calls_executed", 0), int)
            and not isinstance(payload.get("tool_calls_executed", 0), bool)
        ),
        default=0,
    )
    attempts_seen = {
        str(payload.get("research_attempt", "")).strip().casefold()
        for payload in payloads
    }
    has_evidence = any(
        (
            isinstance(payload.get("evidence_artifacts"), int)
            and not isinstance(payload.get("evidence_artifacts"), bool)
            and payload["evidence_artifacts"] > 0
        )
        or bool(payload.get("citations"))
        or bool(payload.get("evidence_pack"))
        for payload in payloads
    )

    issues: list[dict[str, Any]] = []
    if not has_model_call:
        issues.append({
            "check": "research_model_call",
            "severity": "error",
            "detail": "Research-purpose scenario executed no model call (n_calls=0).",
        })
    if tool_calls <= 0:
        issues.append({
            "check": "research_tool_execution",
            "severity": "error",
            "detail": "Research-purpose scenario executed no research tool call.",
        })
    if not payloads or attempts_seen <= {"", "never"} or not has_evidence:
        issues.append({
            "check": "research_evidence_present",
            "severity": "error",
            "detail": (
                "Research-purpose scenario captured no executed research evidence "
                "(missing/never attempt or empty evidence ledger)."
            ),
        })
    return issues


def _assess_graph_census_consistency(
    response: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Reject explicit empty-graph prose against a non-empty locked graph."""
    if _assessment_config(scenario).get("require_graph_census_consistency") is not True:
        return []
    graph = scenario.get("graph") if isinstance(scenario, Mapping) else None
    if not isinstance(graph, dict):
        return []
    from vibecomfy.executor.core import _reply_claims_empty_graph
    from vibecomfy.executor.graph_inspection import inspect_graph

    evidence = inspect_graph(graph)
    reply = response.get("reply") or response.get("message") or ""
    if (
        evidence.node_count > 0
        and isinstance(reply, str)
        and _reply_claims_empty_graph(reply)
    ):
        return [{
            "check": "graph_census_consistency",
            "severity": "error",
            "detail": (
                f"Reply claimed an empty/zero graph, but deterministic inspection "
                f"found {evidence.node_count} nodes and {len(evidence.edges)} edges."
            ),
        }]
    return []


def _tri_state_from_judge(verdict: Mapping[str, Any]) -> str:
    """Map a judge return value to pass|fail|undetermined.

    ``pass_`` True is pass. ``pass_`` False is fail, including malformed
    parsed verdicts. ``pass_`` None (outage, missing evidence, unparsable
    JSON) is undetermined.
    """
    if verdict.get("pass_") is True:
        return "pass"
    if verdict.get("pass_") is False:
        return "fail"
    return "undetermined"


def _record_judge_result(
    *,
    issues: list[dict[str, Any]],
    judge_results: list[dict[str, Any]],
    check: str,
    judge_name: str,
    verdict: Mapping[str, Any],
) -> str:
    """Append a judge result and a matching issue. Return the tri-state."""
    tri = _tri_state_from_judge(verdict)
    judge_results.append(
        {
            "judge": judge_name,
            "verdict": tri,
            "pass_": verdict.get("pass_"),
            "criteria": verdict.get("criteria") or {},
            "rationale": verdict.get("rationale", ""),
            "error": verdict.get("error"),
            # §28 fix 3: additive typed metadata (e.g. verdict class
            # "applied_unverified") so outcome classes survive into the
            # recorded assessment without renaming the tri-state vocabulary.
            "metadata": dict(verdict.get("metadata") or {}),
        }
    )
    if tri == "fail":
        issues.append(
            {
                "check": check,
                "severity": "error",
                "detail": (
                    f"{judge_name} failed: {verdict.get('rationale', 'no rationale')} "
                    f"criteria={verdict.get('criteria')}"
                ),
            }
        )
    elif tri == "pass":
        issues.append(
            {
                "check": check,
                "severity": "info",
                "detail": (
                    f"{judge_name} passed: {verdict.get('rationale', 'no rationale')} "
                    f"criteria={verdict.get('criteria')}"
                ),
            }
        )
    else:
        issues.append(
            {
                "check": check,
                "severity": "undetermined",
                "detail": f"{judge_name} could not run: {verdict.get('error')}",
            }
        )
    return tri


def _effective_edit_targets(scenario: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """Return explicit effective-value targets required by the scenario."""
    assessment = _assessment_config(scenario)
    raw = assessment.get("effective_edit_targets")
    if raw is None:
        raw = assessment.get("effective_targets")
    if isinstance(raw, Mapping):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, Mapping)]
    return []


def _ui_artifact_path(
    output_dir: Path,
    response: Mapping[str, Any],
    artifact_name: str,
    fallback_name: str,
) -> Path:
    artifacts = response.get("artifacts")
    if isinstance(artifacts, Mapping) and isinstance(artifacts.get(artifact_name), str):
        return Path(artifacts[artifact_name])
    return output_dir / fallback_name


def _load_ui_artifact(
    output_dir: Path,
    response: Mapping[str, Any],
    artifact_name: str,
    fallback_name: str,
) -> Mapping[str, Any] | None:
    path = _ui_artifact_path(output_dir, response, artifact_name, fallback_name)
    loaded = _load_json(path)
    return loaded if isinstance(loaded, Mapping) else None


def _graph_field_target(target: Mapping[str, Any]) -> GraphFieldTarget | None:
    node_id = target.get("node_id")
    if node_id is None:
        return None
    widget_index = target.get("widget_index")
    if isinstance(widget_index, bool) or not isinstance(widget_index, int):
        widget_index = None
    field_name = target.get("field_name") or target.get("input_name") or target.get("widget_name")
    if not isinstance(field_name, str) or not field_name:
        field_name = None
    if field_name is None and widget_index is None:
        return None
    return GraphFieldTarget(node_id=node_id, field_name=field_name, widget_index=widget_index)


def _assess_effective_edit_targets(
    output_dir: Path,
    response: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Fail when a claimed parameter target has no effective value change."""
    targets = _effective_edit_targets(scenario)
    if not targets:
        return []

    original_ui = _load_ui_artifact(output_dir, response, "original_ui", "original.ui.json")
    candidate_ui = _load_ui_artifact(output_dir, response, "candidate_ui", "candidate.ui.json")
    if original_ui is None or candidate_ui is None:
        return [
            {
                "check": "effective_edit",
                "severity": "error",
                "detail": "Scenario requires effective edit checks, but UI artifacts are missing.",
            }
        ]

    issues: list[dict[str, Any]] = []
    for target in targets:
        label = str(
            target.get("label")
            or target.get("input_name")
            or target.get("widget_name")
            or target.get("node_id")
            or "target"
        )
        graph_target = _graph_field_target(target)
        if graph_target is None:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": f"Could not resolve effective edit target {label!r}.",
                }
            )
            continue

        try:
            change = compare_effective_field(original_ui, candidate_ui, graph_target)
        except (KeyError, ValueError) as exc:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": f"Could not resolve effective edit target {label!r}: {exc}.",
                }
            )
            continue

        # B12/B13: a change that lands through a shared linked source is a
        # valid edit — the agent may intentionally edit one source feeding
        # several consumers.  Only when the scenario explicitly opts into
        # isolation (assessment.isolate_shared_effective_sources) is a
        # multi-consumer source change treated as an error.
        isolate_shared_sources = (
            _assessment_config(scenario).get("isolate_shared_effective_sources") is True
        )
        if (
            change.effective_changed is True
            and isolate_shared_sources
            and change.before.source is not None
            and change.after.source is not None
            and str(change.before.source.node_id) == str(change.after.source.node_id)
            and change.before.source.output_slot == change.after.source.output_slot
            and max(
                change.before.source.outgoing_link_count,
                change.after.source.outgoing_link_count,
            )
            > 1
        ):
            issues.append(
                {
                    "check": "shared_effective_source_edit",
                    "severity": "error",
                    "detail": (
                        f"Target {label!r} changed through linked source "
                        f"{change.after.source.node_id!r} output "
                        f"{change.after.source.output_slot}, which has "
                        f"{change.after.source.outgoing_link_count} consumers. "
                        "The scenario requires an isolated source; set "
                        "assessment.isolate_shared_effective_sources=false to allow "
                        "intentional shared-source edits."
                    ),
                }
            )
            continue

        if change.effective_changed is True:
            continue

        if (
            change.raw_changed is True
            and (change.before.overridden or change.after.overridden)
            and change.effective_changed is False
        ):
            issues.append(
                {
                    "check": "inert_effective_edit",
                    "severity": "error",
                    "detail": (
                        f"Changed static widget for linked target {label!r} "
                        f"from {change.before.raw_value!r} to {change.after.raw_value!r}, "
                        f"but the effective linked value remained "
                        f"{change.after.effective_value!r}."
                    ),
                }
            )
        elif change.effective_changed is None:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": (
                        f"Could not prove effective value changed for target {label!r}; "
                        "one or both effective values were unknown."
                    ),
                }
            )
        else:
            issues.append(
                {
                    "check": "effective_edit",
                    "severity": "error",
                    "detail": (
                        f"Expected effective value change for target {label!r}, "
                        f"but it remained {change.after.effective_value!r}."
                    ),
                }
            )
    return issues


def assess_live_output_dir(
    output_dir: Path | str,
    scenario: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect live artifacts under *output_dir* and return an assessment.

    The returned dict has:

    * ``passed`` — True iff ``verdict`` is ``pass``.
    * ``verdict`` — ``pass``, ``fail``, or ``undetermined`` (stable vocabulary).
    * ``outcome_class`` — additive honest class for the leg: ``safe_refusal``,
      ``applied-unverified`` (landed + replay-verified edit proven by the FULLY
      BOUND persisted transaction/receipt pair — DEEP-AUDIT-FIX-2-REVISION-2 —
      without an accepted Δ), ``non_edit_route_answered`` (canonical
      research/inspect/respond route correctly made no edit), or ``None``.
    * ``expect_graph_changed`` — whether the scenario expected an edit.
    * ``issue_count`` / ``error_count`` — counts.
    * ``issues`` — list of ``{"check", "severity", "detail"}`` dicts.
    * ``judge_results`` — one entry per judge that ran.
    """
    output_dir = Path(output_dir)
    response = _load_json(output_dir / "response.json")
    impl_result = _load_json(output_dir / "implementation_result.json")

    issues: list[dict[str, Any]] = []
    judge_results: list[dict[str, Any]] = []
    expect_graph_changed = _expects_graph_changed(scenario, response)
    expected_outcome_kinds = _expected_outcome_kinds(scenario)
    allowed_safe_refusal_outcome_kinds = _allowed_safe_refusal_outcome_kinds(
        scenario, response=response
    )
    assessment_cfg = _assessment_config(scenario)
    skip_intent_judge = bool(assessment_cfg.get("skip_intent_judge"))
    skip_semantic_judge = bool(assessment_cfg.get("skip_semantic_judge"))
    safe_refusal_accepted = False
    refusal_outage = False
    outcome_kind: Any = None
    non_edit_route = False
    answered_without_edit = False
    lineage_assessment: dict[str, Any] = {
        "issues": [],
        "present": False,
        "manifest_digest": None,
        "binding": {},
        "provenance": "absent",
    }

    if response is not None:
        # §28 fix 3: canonical non-edit route recognition.  The envelope's
        # canonical route (research/inspect/respond/clarify/
        # requires_custom_nodes) decides whether a no-edit run is a legitimate
        # outcome class rather than a missing edit; the route is read exactly
        # as everywhere else in this module (_canonical_route machinery).
        non_edit_route = _explicitly_non_edit_route(response)
        answered_without_edit = (
            non_edit_route and response.get("graph_unchanged") is True
        )
        if answered_without_edit:
            issues.append(
                {
                    "check": "non_edit_route_no_edit",
                    "severity": "info",
                    "detail": (
                        f"Canonical non-edit route {non_edit_route!r} completed "
                        "without a graph edit; scored by its structured "
                        "non-edit checks (research evidence, census, rubric), "
                        "not by the expected-edit guards."
                    ),
                }
            )
        outcome = response.get("outcome") or {}
        outcome_kind = outcome.get("kind")
        refusal_candidate = (
            expect_graph_changed
            and response.get("graph_unchanged") is True
            and isinstance(outcome_kind, str)
            and outcome_kind in allowed_safe_refusal_outcome_kinds
        )

        # Universal grounded-refusal adjudication: an allowlisted label is
        # only a candidate. The judge decides pass/fail/undetermined.
        if refusal_candidate:
            refusal_verdict = judge_grounded_refusal(output_dir, scenario or {})
            refusal_tri = _record_judge_result(
                issues=issues,
                judge_results=judge_results,
                check="grounded_refusal",
                judge_name="grounded_refusal",
                verdict=refusal_verdict,
            )
            if refusal_tri == "pass":
                safe_refusal_accepted = True
            elif refusal_tri == "undetermined":
                refusal_outage = True

        # Top-level response health.
        if response.get("ok") is False:
            issues.append(
                {
                    "check": "response_ok",
                    "severity": "error",
                    "detail": f"response.ok is False: {response.get('error') or response.get('message')}",
                }
            )
        elif response.get("error"):
            issues.append(
                {
                    "check": "response_error_field",
                    "severity": "error",
                    "detail": f"response.error set: {response['error']}",
                }
            )

        # Readiness is also captured in flow_metadata, but surface it here if
        # the response carries it (e.g. blocked-prerequisite runs).
        readiness = response.get("readiness") or {}
        if readiness.get("ready") is False:
            issues.append(
                {
                    "check": "response_readiness",
                    "severity": "error",
                    "detail": f"Readiness not ready: {readiness.get('reason')}",
                }
            )

        if expect_graph_changed:
            if safe_refusal_accepted:
                issues.append(
                    {
                        "check": "safe_refusal",
                        "severity": "info",
                        "detail": f"Accepted safe refusal outcome.kind={outcome_kind!r}.",
                    }
                )
                # G5-B4-MUST-007: a grounded refusal is honest evidence, but
                # this scenario's obligation requires an EDITED product. The
                # leg records ``undetermined`` — never a pass.
                issues.append(
                    {
                        "check": "safe_refusal_edit_obligation",
                        "severity": "undetermined",
                        "detail": (
                            "scenario obligation requires an edited product; "
                            "an accepted safe refusal records undetermined "
                            "and can never grade pass"
                        ),
                    }
                )
            elif refusal_outage:
                # Outage cannot satisfy the scenario, but must not collapse
                # to a structural graph_changed product-fail.
                pass
            elif response.get("graph_unchanged") is True:
                issues.append(
                    {
                        "check": "graph_changed",
                        "severity": "error",
                        "detail": "Expected graph change but response.graph_unchanged is True.",
                    }
                )

            # G0R structural expected-edit guard: a claimed edit
            # (graph_unchanged is False) must be backed by a positive integer
            # change_details.landed_operation_count.  Missing, malformed, or
            # zero counts fail closed.  Accepted grounded refusals
            # (safe_refusal_accepted) and canonical non-edit routes are
            # exempt — they are scored by their own structured checks.
            route = _canonical_route(response)
            if (
                not safe_refusal_accepted
                and not refusal_outage
                and response.get("graph_unchanged") is False
                and not _explicitly_non_edit_route(response)
            ):
                landed_count = _landed_operation_count(response)
                if not (
                    isinstance(landed_count, int)
                    and not isinstance(landed_count, bool)
                    and landed_count > 0
                ):
                    issues.append(
                        {
                            "check": "landed_operation_count",
                            "severity": "error",
                            "detail": (
                                "Expected edit but change_details.landed_operation_count "
                                f"is {landed_count!r}; a positive integer is required "
                                "when graph_unchanged is false."
                            ),
                        }
                    )

            # G0R route/graph consistency: a canonical non-edit route must
            # never claim graph_unchanged=false.  Non-edit routes are exempt
            # from the landed-count guard only when the graph really is
            # unchanged (or the refusal is authorized above); an edit-route
            # envelope self-relabeled as clarify/respond/failure cannot
            # bypass the structural checks by relabeling alone.
            if (
                not safe_refusal_accepted
                and not refusal_outage
                and response.get("graph_unchanged") is False
                and route in _NON_EDIT_ROUTES
            ):
                issues.append(
                    {
                        "check": "route_graph_consistency",
                        "severity": "error",
                        "detail": (
                            f"Non-edit route {route!r} claimed graph_unchanged=false; "
                            "a non-edit route cannot change the graph."
                        ),
                    }
                )

            no_reason = response.get("no_candidate_reason")
            if (
                not safe_refusal_accepted
                and not refusal_outage
                and no_reason in {"no_changes", "no_candidate"}
            ):
                issues.append(
                    {
                        "check": "no_candidate_reason",
                        "severity": "error",
                        "detail": f"Expected edit but no_candidate_reason={no_reason!r}.",
                    }
                )

            if (
                not safe_refusal_accepted
                and not refusal_outage
                and outcome_kind in {"noop", "requires_custom_nodes"}
            ):
                issues.append(
                    {
                        "check": "outcome_kind",
                        "severity": "error",
                        "detail": f"Expected edit but outcome.kind={outcome_kind!r}.",
                    }
                )

            gates = response.get("gates") or {}
            false_gates = [name for name, value in gates.items() if value is False]
            queue_validate_skipped = _queue_validate_skipped_for_successful_candidate(response)
            if queue_validate_skipped and "queue_validate_ok" in false_gates:
                false_gates = [name for name in false_gates if name != "queue_validate_ok"]
                issues.append(
                    {
                        "check": "queue_validate_skipped",
                        "severity": "warning",
                        "detail": (
                            "queue_validate_ok was false, but the response contains a changed "
                            "candidate and no queue_validate stage ran; treating this as missing "
                            "queue evidence rather than a concrete queue blocker."
                        ),
                    }
                )
            if false_gates and not safe_refusal_accepted and not refusal_outage:
                issues.append(
                    {
                        "check": "gates",
                        "severity": "error",
                        "detail": f"Expected edit but gates failed: {', '.join(sorted(false_gates))}.",
                    }
                )

            if not safe_refusal_accepted and not refusal_outage:
                issues.extend(_assess_effective_edit_targets(output_dir, response, scenario))
        elif expected_outcome_kinds:
            outcome = response.get("outcome") or {}
            outcome_kind = outcome.get("kind")
            if outcome_kind not in expected_outcome_kinds:
                issues.append(
                    {
                        "check": "outcome_kind",
                        "severity": "error",
                        "detail": (
                            f"Expected outcome.kind in {sorted(expected_outcome_kinds)!r} "
                            f"but got {outcome_kind!r}."
                        ),
                    }
                )

        # Edit-intent judge: score the candidate when an edit is expected and
        # this is not a refusal candidate (refusals were already judged above).
        # Outage is undetermined and cannot satisfy the scenario. Malformed
        # parsed verdicts fail. graph_unchanged=false plus a refusal label is
        # never a safe refusal, so it still hits structural guards and the
        # edit-intent judge.
        if (
            expect_graph_changed
            and not skip_intent_judge
            and not refusal_candidate
        ):
            _record_judge_result(
                issues=issues,
                judge_results=judge_results,
                check="intent_judge",
                judge_name="edit_intent",
                verdict=judge_edit_intent(output_dir, scenario or {}),
            )

        # Any hard diagnostic anywhere in the response envelope.
        for msg in _collect_hard_diagnostics(
            response,
            accepted_safe_refusal=safe_refusal_accepted,
        ):
            issues.append(
                {
                    "check": "hard_diagnostic",
                    "severity": "error",
                    "detail": msg,
                }
            )

        # G0-T2: the deterministic message-artifact prose matcher is removed.
        # Scoring is structured-only — prose never gates a scenario. The
        # agent's message always ships as written; the structured
        # cross-checks (graph_changed, outcome_kind, gates, landed counts,
        # effective edits) above remain fully authoritative.

        # Critical upstream failures (Hivemind 500, etc.). Infra is not a
        # product fail: semantic_product rows, successful candidates, and —
        # §28 fix 3 — canonical non-edit-route runs that correctly made no
        # edit keep these as warnings (RC9 / B6 S7).  A research/inspect leg
        # whose question was answered on a truthful non-edit route must not
        # product-fail because transient infra noise crossed the envelope.
        if (
            _scenario_kind(scenario) == "semantic_product"
            or _has_successful_candidate(response)
            or answered_without_edit
        ):
            upstream_severity = "warning"
        else:
            upstream_severity = "error"
        for msg in _collect_pattern_matches(response, _UPSTREAM_FAILURE_PATTERNS):
            issues.append(
                {
                    "check": "upstream_failure",
                    "severity": upstream_severity,
                    "detail": msg,
                }
            )

        # Capacity/soft warnings: surfaced, but not counted as errors.
        for msg in _collect_pattern_matches(response, _SOFT_WARNING_PATTERNS):
            issues.append(
                {
                    "check": "soft_warning",
                    "severity": "warning",
                    "detail": msg,
                }
            )

        # B12/B13 assessment-first research rules (enabled by
        # assessment.research): question-before-search, query relevance,
        # required-Hivemind invocation, citation resolution to returned
        # evidence IDs, no-local-search research path, and evidence-pack
        # capture.  All are structured-evidence checks — prose never gates.
        issues.extend(assess_research_evidence(response, scenario))
        issues.extend(_assess_executed_research(output_dir, response, scenario))
        issues.extend(_assess_graph_census_consistency(response, scenario))

        # T5.1: digest-linked artifact lineage — validity, scenario binding,
        # and fallback-impersonation checks. Structured evidence only.
        # G5-B4-MUST-003: lineage absence/mismatch is undetermined ONLY for
        # edit scenarios (C11). Health controls and semantic_product without
        # an expected edit do not carry edit authority and are exempt from
        # the lineage-presence gate; fallback-impersonation and binding
        # errors remain hard failures regardless.
        lineage_assessment = assess_artifact_lineage(
            output_dir, response, scenario
        )
        lineage_issues = lineage_assessment["issues"]
        kind = _scenario_kind(scenario)
        expect_edit = bool(_assessment_config(scenario).get("expect_graph_changed"))
        if (
            kind in ("health_control", "semantic_product") and not expect_edit
        ) or answered_without_edit:
            # §28 fix 3: a canonical non-edit route that truthfully reports an
            # unchanged graph carries no edit authority either, so the
            # lineage-presence gate cannot apply to it (same parity as the
            # health_control / semantic_product exemption above).
            lineage_issues = [
                iss
                for iss in lineage_issues
                if iss.get("check")
                not in ("artifact_lineage_absent", "artifact_lineage_sidecar_unverified")
            ]

    # Semantic-answer judge runs for every D13 rubric scenario regardless
    # of edit expectation or response presence. Health controls are
    # structurally scored only.
    if (
        _answer_rubric(scenario) is not None
        and not _excluded_from_semantic_product_rates(scenario)
        and not skip_semantic_judge
    ):
        _record_judge_result(
            issues=issues,
            judge_results=judge_results,
            check="semantic_answer",
            judge_name="semantic_answer",
            verdict=judge_semantic_answer(output_dir, scenario or {}),
        )

    if impl_result is not None:
        # G0R: the residual "unchanged" substring gate over the
        # implementation_result message is removed — prose never gates
        # scoring.  Only the structured ok flag is authoritative.
        if impl_result.get("ok") is False:
            issues.append(
                {
                    "check": "implementation_result_ok",
                    "severity": "error",
                    "detail": (
                        "implementation_result.ok is False: "
                        f"{impl_result.get('error') or impl_result.get('message', '')}"
                    ),
                }
            )

    # Deduplicate while preserving order.
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = (issue["check"], issue["severity"], issue["detail"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)

    errors = [issue for issue in deduped if issue["severity"] == "error"]
    undetermined_issues = [
        issue for issue in deduped if issue["severity"] == "undetermined"
    ]
    if errors:
        verdict = "fail"
    elif undetermined_issues:
        verdict = "undetermined"
    else:
        verdict = "pass"

    # §28 fix 3: additive outcome-class attribution.  The verdict vocabulary
    # (pass/fail/undetermined) is unchanged; this field only records WHICH
    # honest class the leg fell into so research/inspect no-edit runs and
    # landed-but-not-re-derivable edits are distinguishable from bare
    # undetermined rows.  New classes are additions, never renames.
    if safe_refusal_accepted:
        outcome_class = "safe_refusal"
    elif any(
        isinstance(judge.get("metadata"), Mapping)
        and judge["metadata"].get("verdict") == "applied_unverified"
        for judge in judge_results
    ):
        outcome_class = "applied-unverified"
    elif answered_without_edit:
        outcome_class = "non_edit_route_answered"
    else:
        outcome_class = None

    original_ui_path = output_dir / "original.ui.json"
    final_ui_path = output_dir / "final.ui.json"
    assessment = {
        "passed": verdict == "pass",
        "verdict": verdict,
        "outcome_class": outcome_class,
        "expected_outcome_kinds": sorted(expected_outcome_kinds),
        "allow_safe_refusal_outcome_kinds": sorted(allowed_safe_refusal_outcome_kinds),
        "issue_count": len(deduped),
        "error_count": len(errors),
        "issues": deduped,
        "judge_results": judge_results,
        "scenario_kind": _scenario_kind(scenario),
        "excluded_from_semantic_product_rates": _excluded_from_semantic_product_rates(
            scenario
        ),
        "artifact_lineage": {
            "present": lineage_assessment["present"],
            "manifest_digest": lineage_assessment["manifest_digest"],
            "binding": lineage_assessment["binding"],
            "provenance": lineage_assessment["provenance"],
        },
        "ui_evidence": {
            "original": original_ui_path.is_file(),
            "final": final_ui_path.is_file(),
        },
    }
    try:
        (output_dir / "assessment.json").write_text(
            json.dumps(assessment, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    return assessment
