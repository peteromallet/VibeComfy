from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

from vibecomfy.contracts.intent_nodes import (
    CLASS_TYPE_TO_KIND,
    INTENT_NODE_CONTRACT_INVALID_CODE,
    INTENT_NODE_QUEUE_BLOCKER_CODE,
    is_intent_class_type,
)
from vibecomfy.porting.lowering import LoweringDiagnostic, LoweringResult
from vibecomfy.schema.validate import validate_against_schema, validate_api_link_shapes
from vibecomfy.workflow import ValidationIssue, VibeWorkflow

from .contracts import FailureKind, StageResult

UNSATISFIED_INPUT_CODES = frozenset(
    {
        "missing_required_input",
        "missing_input",
    }
)
UNSUPPORTED_NON_DAG_CODES = frozenset(
    {
        "opaque_component_class_type",
        "unsupported_non_dag",
        "subgraph_freshness_error",
    }
)
INTENT_CONTRACT_INVALID_CODES = frozenset({INTENT_NODE_CONTRACT_INVALID_CODE})


@dataclass(frozen=True)
class ValidateDiagnostics:
    ok: bool
    blocking: bool
    failure_kind: FailureKind | None
    issues: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class QueueDiagnostics:
    ok: bool
    blocking: bool
    failure_kind: FailureKind | None
    issues: tuple[dict[str, Any], ...]


def _issue_to_dict(issue: ValidationIssue, *, source: str) -> dict[str, Any]:
    return {
        "source": source,
        "code": issue.code,
        "message": issue.message,
        "severity": issue.severity,
        "detail": dict(issue.detail),
    }


def _lowering_issue_to_dict(issue: LoweringDiagnostic) -> dict[str, Any]:
    detail = dict(issue.detail)
    if issue.loop_uid is not None:
        detail.setdefault("loop_uid", issue.loop_uid)
    detail.setdefault("loop_node_id", issue.loop_node_id)
    return {
        "source": "lower_workflow",
        "code": issue.code,
        "message": issue.message,
        "severity": "error",
        "detail": detail,
    }


def _dedupe(issues: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for issue in issues:
        key = (
            issue.get("source"),
            issue.get("code"),
            issue.get("message"),
            jsonish_key(issue.get("detail", {})),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return tuple(result)


def jsonish_key(value: Any) -> str:
    import json

    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return repr(value)


def classify_validation_issues(issues: tuple[dict[str, Any], ...]) -> FailureKind | None:
    hard = [issue for issue in issues if issue.get("severity", "error") == "error"]
    if not hard:
        return None
    hard_codes = {str(issue.get("code")) for issue in hard}
    if hard_codes & UNSUPPORTED_NON_DAG_CODES:
        return FailureKind.UNSUPPORTED_NON_DAG
    if hard_codes & INTENT_CONTRACT_INVALID_CODES:
        return FailureKind.VALIDATION_ERROR
    if hard_codes & UNSATISFIED_INPUT_CODES:
        return FailureKind.UNSATISFIED_INPUT_ERROR
    return FailureKind.VALIDATION_ERROR


def _queue_issue(
    *,
    code: str,
    message: str,
    detail: dict[str, Any],
    failure_kind: FailureKind,
) -> dict[str, Any]:
    return {
        "source": "agent_diagnostics.queue_stage",
        "code": code,
        "message": message,
        "severity": "error",
        "detail": detail,
        "failure_kind": failure_kind.value,
    }


def _intent_node_runtime_flags(
    class_type: str,
    entry: dict[str, Any],
) -> tuple[bool | None, bool | None, bool | None]:
    lowered = entry.get("lowered")
    runtime_backed = entry.get("runtime_backed")
    class_runtime_backed = None
    try:
        from vibecomfy.comfy_nodes import NODE_CLASS_MAPPINGS
    except Exception:
        return (
            lowered if isinstance(lowered, bool) else None,
            runtime_backed if isinstance(runtime_backed, bool) else None,
            class_runtime_backed,
        )
    node_cls = NODE_CLASS_MAPPINGS.get(class_type)
    if node_cls is not None:
        class_runtime_backed = getattr(node_cls, "VIBECOMFY_RUNTIME_BACKED", None)
    return (
        lowered
        if isinstance(lowered, bool)
        else (getattr(node_cls, "VIBECOMFY_LOWERED", None) if node_cls is not None else None),
        runtime_backed
        if isinstance(runtime_backed, bool)
        else class_runtime_backed,
        class_runtime_backed if isinstance(class_runtime_backed, bool) else None,
    )


def _intent_node_queue_ready(
    *,
    class_type: str,
    entry: dict[str, Any],
    lowered: bool | None,
    runtime_backed: bool | None,
    class_runtime_backed: bool | None,
    confidence: Any,
) -> bool:
    if lowered is True:
        return True
    if class_type != "vibecomfy.code":
        return False
    return (
        runtime_backed is True
        and class_runtime_backed is True
        and entry.get("runtime_contract_valid") is True
        and entry.get("intent_contract_valid") is True
        and entry.get("schema_less") is not True
        and isinstance(confidence, (int, float))
        and confidence > 0.3
    )


def classify_queue_issues(issues: tuple[dict[str, Any], ...]) -> FailureKind | None:
    for issue in issues:
        raw_kind = issue.get("failure_kind")
        if isinstance(raw_kind, str):
            return FailureKind(raw_kind)
    return None


def validate_stage_diagnostics(
    workflow: VibeWorkflow,
    *,
    schema_provider: Any = None,
) -> ValidateDiagnostics:
    issues: list[dict[str, Any]] = []
    report = workflow.validate(schema_provider=None)
    issues.extend(_issue_to_dict(issue, source="workflow.validate") for issue in report.issues)

    if schema_provider is not None:
        issues.extend(
            _issue_to_dict(issue, source="validate_against_schema")
            for issue in validate_against_schema(workflow, schema_provider)
        )
        try:
            api_dict = workflow.compile("api")
        except Exception:
            api_dict = None
        if api_dict is not None:
            issues.extend(
                _issue_to_dict(issue, source="validate_api_link_shapes")
                for issue in validate_api_link_shapes(api_dict, schema_provider)
            )

    issues.extend(
        _issue_to_dict(issue, source="workflow.helper_diagnostics")
        for issue in workflow.helper_diagnostics()
    )

    deduped = _dedupe(issues)
    failure_kind = classify_validation_issues(deduped)
    return ValidateDiagnostics(
        ok=failure_kind is None,
        blocking=failure_kind is not None,
        failure_kind=failure_kind,
        issues=deduped,
    )


def validate_stage_result(
    workflow: VibeWorkflow,
    *,
    schema_provider: Any = None,
) -> StageResult:
    diagnostics = validate_stage_diagnostics(workflow, schema_provider=schema_provider)
    return StageResult(
        stage="validate",
        ok=diagnostics.ok,
        blocking=diagnostics.blocking,
        value={
            "failure_kind": diagnostics.failure_kind.value
            if diagnostics.failure_kind is not None
            else None,
        },
        issues=diagnostics.issues,
        gate_updates={"ir_validate_ok": diagnostics.ok},
    )


def lower_stage_result(result: LoweringResult) -> StageResult:
    if result.ok:
        return StageResult(
            stage="lower",
            ok=True,
            blocking=False,
            value={
                "failure_kind": None,
                "lowered_count": result.lowered_count,
                "evidence": [dict(dataclasses.asdict(item)) for item in result.evidence],
            },
            gate_updates={"lower_ok": True},
        )
    return StageResult(
        stage="lower",
        ok=False,
        blocking=True,
        value={
            "failure_kind": FailureKind.LOWERING_FAILURE.value,
            "lowered_count": result.lowered_count,
        },
        issues=tuple(_lowering_issue_to_dict(issue) for issue in result.diagnostics),
        gate_updates={"lower_ok": False},
    )


def queue_stage_diagnostics(
    *,
    recovery_report: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    change_report: dict[str, Any] | None = None,
) -> QueueDiagnostics:
    issues: list[dict[str, Any]] = []
    per_node_entries = [
        entry
        for entry in recovery_report or ()
        if isinstance(entry, dict) and entry.get("node_id") is not None
    ]
    for entry in per_node_entries:
        node_id = str(entry.get("node_id"))
        class_type = str(entry.get("class_type"))
        confidence = entry.get("confidence")
        if is_intent_class_type(class_type):
            lowered, runtime_backed, class_runtime_backed = _intent_node_runtime_flags(class_type, entry)
            if _intent_node_queue_ready(
                class_type=class_type,
                entry=entry,
                lowered=lowered,
                runtime_backed=runtime_backed,
                class_runtime_backed=class_runtime_backed,
                confidence=confidence,
            ):
                continue
            issues.append(
                _queue_issue(
                    code=INTENT_NODE_QUEUE_BLOCKER_CODE,
                    message=(
                        f"Node {node_id} ({class_type}) is an editor-only intent node and cannot be queued until it is lowered."
                    ),
                    detail={
                        "node_id": node_id,
                        "class_type": class_type,
                        "kind": entry.get("kind") or CLASS_TYPE_TO_KIND.get(class_type),
                        "uid": entry.get("uid"),
                        "lowered": lowered,
                        "runtime_backed": runtime_backed,
                        "class_runtime_backed": class_runtime_backed,
                        "runtime_contract_valid": entry.get("runtime_contract_valid"),
                        "intent_contract_valid": entry.get("intent_contract_valid"),
                        "contract_problem_codes": entry.get("contract_problem_codes"),
                        "provider": entry.get("provider"),
                        "confidence": confidence,
                        "diagnostic": entry.get("diagnostic"),
                    },
                    failure_kind=FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER,
                )
            )
            continue
        if entry.get("schema_less") is True:
            issues.append(
                _queue_issue(
                    code="schema_less_queue_blocker",
                    message=(
                        f"Node {node_id} ({class_type}) is schema-less and cannot be queued safely."
                    ),
                    detail={
                        "node_id": node_id,
                        "class_type": class_type,
                        "provider": entry.get("provider"),
                        "confidence": confidence,
                        "diagnostic": entry.get("diagnostic"),
                    },
                    failure_kind=FailureKind.SCHEMA_LESS_QUEUE_BLOCKER,
                )
            )
            continue
        if isinstance(confidence, (int, float)) and confidence <= 0.3:
            issues.append(
                _queue_issue(
                    code="low_confidence_queue_blocker",
                    message=(
                        f"Node {node_id} ({class_type}) has low-confidence schema evidence and cannot be queued safely."
                    ),
                    detail={
                        "node_id": node_id,
                        "class_type": class_type,
                        "provider": entry.get("provider"),
                        "confidence": confidence,
                        "diagnostic": entry.get("diagnostic"),
                    },
                    failure_kind=FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER,
                )
            )
            continue
        if confidence is None and not entry.get("schema_less"):
            issues.append(
                _queue_issue(
                    code="low_confidence_queue_blocker",
                    message=(
                        f"Node {node_id} ({class_type}) has unresolved model/widget evidence and cannot be queued safely."
                    ),
                    detail={
                        "node_id": node_id,
                        "class_type": class_type,
                        "provider": entry.get("provider"),
                        "confidence": None,
                        "diagnostic": "unresolved model/widget: confidence could not be determined",
                    },
                    failure_kind=FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER,
                )
            )
    content_edits = change_report.get("content_edits", {}) if isinstance(change_report, dict) else {}
    stripped_helpers = content_edits.get("stripped_helpers", [])
    if isinstance(stripped_helpers, list) and stripped_helpers:
        issues.append(
            _queue_issue(
                code="editor_only_node_queue_blocker",
                message="Editor-only helper nodes would be stripped from the queued API graph.",
                detail={"stripped_helpers": list(stripped_helpers)},
                failure_kind=FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER,
            )
        )

    deduped = _dedupe(issues)
    return QueueDiagnostics(
        ok=not deduped,
        blocking=False,
        failure_kind=classify_queue_issues(deduped),
        issues=deduped,
    )


def queue_stage_result(
    *,
    recovery_report: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    change_report: dict[str, Any] | None = None,
) -> StageResult:
    diagnostics = queue_stage_diagnostics(
        recovery_report=recovery_report,
        change_report=change_report,
    )
    return StageResult(
        stage="queue_validate",
        ok=diagnostics.ok,
        blocking=diagnostics.blocking,
        value={
            "failure_kind": diagnostics.failure_kind.value
            if diagnostics.failure_kind is not None
            else None,
        },
        issues=diagnostics.issues,
        gate_updates={"queue_validate_ok": diagnostics.ok},
    )


__all__ = [
    "QueueDiagnostics",
    "UNSATISFIED_INPUT_CODES",
    "UNSUPPORTED_NON_DAG_CODES",
    "ValidateDiagnostics",
    "classify_queue_issues",
    "classify_validation_issues",
    "queue_stage_diagnostics",
    "queue_stage_result",
    "validate_stage_diagnostics",
    "validate_stage_result",
]
