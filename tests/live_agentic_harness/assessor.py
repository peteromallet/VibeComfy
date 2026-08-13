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
* (when enabled) an LLM intent judge that scores the edit against the query

The deterministic checks run first; the LLM judge is called afterward for
scenarios that expect a graph change.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.executor.graph_facts import GraphFieldTarget, compare_effective_field

from .intent_judge import judge_edit_intent, judge_grounded_refusal

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


def _collect_hard_diagnostics(response: Mapping[str, Any]) -> list[str]:
    """Return messages from any object with severity error/fatal."""
    issues: list[str] = []
    skip_failed_batch_turns = _has_successful_candidate(response)
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


def _allowed_safe_refusal_outcome_kinds(scenario: Mapping[str, Any] | None) -> set[str]:
    """Return no-edit outcome kinds accepted as safe refusals for edit scenarios."""
    if scenario is None:
        return set()
    assessment = scenario.get("assessment")
    if not isinstance(assessment, Mapping):
        return set()
    raw = assessment.get("allow_safe_refusal_outcome_kinds")
    if raw is None:
        raw = assessment.get("allow_safe_refusal_outcome_kind")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {item for item in raw if isinstance(item, str)}
    return set()


def _assessment_config(scenario: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return the scenario assessment config, if present."""
    if scenario is None:
        return {}
    assessment = scenario.get("assessment")
    return assessment if isinstance(assessment, Mapping) else {}


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


def _model_request_text(output_dir: Path) -> str | None:
    """Return copied model_request.json text when the headless run produced it."""
    path = output_dir / "model_request.json"
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _assess_model_request_artifact(
    output_dir: Path,
    scenario: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Apply optional prompt-size/content guardrails from scenario assessment.

    Supported scenario fields:

    * ``assessment.max_model_request_bytes`` — fail when copied
      ``model_request.json`` is larger than this many bytes.
    * ``assessment.forbid_model_request_substrings`` — fail when any listed
      substring appears in copied ``model_request.json``.
    """
    assessment = _assessment_config(scenario)
    max_bytes = assessment.get("max_model_request_bytes")
    forbidden_raw = assessment.get("forbid_model_request_substrings")
    has_size_check = isinstance(max_bytes, int) and not isinstance(max_bytes, bool)
    forbidden = [item for item in forbidden_raw or [] if isinstance(item, str)]
    if not has_size_check and not forbidden:
        return []

    path = output_dir / "model_request.json"
    if not path.is_file():
        return [
            {
                "check": "model_request_artifact",
                "severity": "error",
                "detail": "Scenario requires model_request.json checks, but the artifact is missing.",
            }
        ]

    issues: list[dict[str, Any]] = []
    if has_size_check:
        actual_size = path.stat().st_size
        if actual_size > max_bytes:
            issues.append(
                {
                    "check": "model_request_size",
                    "severity": "error",
                    "detail": (
                        f"model_request.json is {actual_size} bytes; "
                        f"limit is {max_bytes} bytes."
                    ),
                }
            )

    if forbidden:
        text = _model_request_text(output_dir)
        if text is None:
            issues.append(
                {
                    "check": "model_request_artifact",
                    "severity": "error",
                    "detail": "model_request.json could not be read.",
                }
            )
        else:
            decoded: Any = None
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                decoded = None
            for substring in forbidden:
                found_in_decoded_string = any(
                    isinstance(node, str) and substring in node
                    for node in _walk(decoded)
                )
                if substring in text or found_in_decoded_string:
                    issues.append(
                        {
                            "check": "model_request_forbidden_substring",
                            "severity": "error",
                            "detail": (
                                "model_request.json contains forbidden substring "
                                f"{substring!r}."
                            ),
                        }
                    )
    return issues


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

        allow_shared_source = target.get("allow_shared_source_edit") is True
        if (
            change.effective_changed is True
            and not allow_shared_source
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
                        "Set allow_shared_source_edit when the shared edit is intentional."
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

    * ``passed`` — True iff no error-level issues were found.
    * ``expect_graph_changed`` — whether the scenario expected an edit.
    * ``issue_count`` / ``error_count`` — counts.
    * ``issues`` — list of ``{"check", "severity", "detail"}`` dicts.
    """
    output_dir = Path(output_dir)
    response = _load_json(output_dir / "response.json")
    impl_result = _load_json(output_dir / "implementation_result.json")

    issues: list[dict[str, Any]] = []
    expect_graph_changed = _expects_graph_changed(scenario, response)
    expected_outcome_kinds = _expected_outcome_kinds(scenario)
    allowed_safe_refusal_outcome_kinds = _allowed_safe_refusal_outcome_kinds(scenario)
    safe_refusal_accepted = False

    if response is not None:
        outcome = response.get("outcome") or {}
        outcome_kind = outcome.get("kind")
        safe_refusal_accepted = (
            expect_graph_changed
            and response.get("graph_unchanged") is True
            and isinstance(outcome_kind, str)
            and outcome_kind in allowed_safe_refusal_outcome_kinds
        )

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
            if not safe_refusal_accepted and no_reason in {"no_changes", "no_candidate"}:
                issues.append(
                    {
                        "check": "no_candidate_reason",
                        "severity": "error",
                        "detail": f"Expected edit but no_candidate_reason={no_reason!r}.",
                    }
                )

            if not safe_refusal_accepted and outcome_kind in {"noop", "requires_custom_nodes"}:
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
            if false_gates and not safe_refusal_accepted:
                issues.append(
                    {
                        "check": "gates",
                        "severity": "error",
                        "detail": f"Expected edit but gates failed: {', '.join(sorted(false_gates))}.",
                    }
                )

            if not safe_refusal_accepted:
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

        # LLM intent judge: score the candidate edit against the query when the
        # scenario expects a graph change.  This runs by default; set
        # ``assessment.skip_intent_judge: true`` in the scenario to disable it.
        # A DESIRED edit must never pass on an allowlisted refusal label
        # without an active grounded-refusal judge: the judge runs and must
        # confirm the refusal is grounded (supported blocker, no representable
        # edit, specific next action, no fabricated inability), and it FAILS
        # CLOSED when the judge is unavailable.  graph_unchanged=false plus a
        # refusal label is never a safe refusal (safe_refusal_accepted requires
        # graph_unchanged=true), so it is still scored by the structural guards
        # and — for desired scenarios — fails closed without a judge verdict.
        # Non-desired edit-or-refuse scenarios keep the historical bypass.
        if (
            expect_graph_changed
            and not scenario.get("assessment", {}).get("skip_intent_judge")
        ):
            if safe_refusal_accepted and scenario.get("desired"):
                verdict = judge_grounded_refusal(output_dir, scenario)
                if verdict.get("pass_") is False:
                    issues.append(
                        {
                            "check": "grounded_refusal",
                            "severity": "error",
                            "detail": (
                                f"Refusal not grounded: {verdict.get('rationale', 'no rationale')} "
                                f"criteria={verdict.get('criteria')}"
                            ),
                        }
                    )
                elif verdict.get("pass_") is True:
                    issues.append(
                        {
                            "check": "grounded_refusal",
                            "severity": "info",
                            "detail": (
                                f"Grounded refusal confirmed: {verdict.get('rationale', 'no rationale')} "
                                f"criteria={verdict.get('criteria')}"
                            ),
                        }
                    )
                else:
                    issues.append(
                        {
                            "check": "grounded_refusal",
                            # A desired block is an active acceptance rubric;
                            # an absent grounded-refusal judge fails closed.
                            "severity": "error",
                            "detail": (
                                "Grounded-refusal judge could not run: "
                                f"{verdict.get('error')}"
                            ),
                        }
                    )
            elif not safe_refusal_accepted:
                verdict = judge_edit_intent(output_dir, scenario)
                if verdict.get("pass_") is False:
                    issues.append(
                        {
                            "check": "intent_judge",
                            "severity": "error",
                            "detail": (
                                f"LLM intent judge failed: {verdict.get('rationale', 'no rationale')} "
                                f"criteria={verdict.get('criteria')}"
                            ),
                        }
                    )
                elif verdict.get("pass_") is True:
                    issues.append(
                        {
                            "check": "intent_judge",
                            "severity": "info",
                            "detail": (
                                f"LLM intent judge passed: {verdict.get('rationale', 'no rationale')} "
                                f"criteria={verdict.get('criteria')}"
                            ),
                        }
                    )
                else:
                    issues.append(
                        {
                            "check": "intent_judge",
                            # A desired block is an active acceptance rubric, not
                            # optional context. Fail closed if its judge is absent.
                            "severity": "error" if scenario.get("desired") else "warning",
                            "detail": f"LLM intent judge could not run: {verdict.get('error')}",
                        }
                    )

        # Any hard diagnostic anywhere in the response envelope.
        for msg in _collect_hard_diagnostics(response):
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

        # Critical upstream failures (Hivemind 500, etc.). When a successful
        # candidate exists, a recovered research-side upstream error should stay
        # visible but not invalidate an otherwise valid edit.
        upstream_severity = "warning" if _has_successful_candidate(response) else "error"
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

    issues.extend(_assess_model_request_artifact(output_dir, scenario))

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
    return {
        "passed": len(errors) == 0,
        "expect_graph_changed": expect_graph_changed,
        "expected_outcome_kinds": sorted(expected_outcome_kinds),
        "allow_safe_refusal_outcome_kinds": sorted(allowed_safe_refusal_outcome_kinds),
        "issue_count": len(deduped),
        "error_count": len(errors),
        "issues": deduped,
    }
