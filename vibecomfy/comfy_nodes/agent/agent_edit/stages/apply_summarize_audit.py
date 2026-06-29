from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path
from typing import Any, Mapping

from ...audit import normalize_agent_edit_v2_metadata, write_json_artifact
from ...contracts import FailureEnvelope, FailureKind, StageResult, TurnContext
from ...gates import derive_gates
from ..budget import _json_safe
from ..lowering import _build_lowering_audit_entries, _inject_lowering_provenance
from ..messages import _lint_issue_to_dict
from ..paths import _artifact
from ..state import AgentEditState


def _edit_facade():
    from ... import edit as facade

    return facade


def _stage_apply_delta_impl(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.apply import apply_delta
    from vibecomfy.porting.edit.apply import (
        AppliedAddNodeSpec,
        ResolvedFieldRef,
        ResolvedRemoveNodePlan,
    )
    from vibecomfy.porting.edit.ops import op_to_dict

    facade = _edit_facade()

    def _build_delta_audit(result: Any) -> dict[str, Any]:
        automatic_link_removals: list[dict[str, Any]] = []
        re_stitches: list[dict[str, Any]] = []
        for op, resolved_op in result.resolved_ops:
            if isinstance(resolved_op, ResolvedFieldRef) and resolved_op.automatic_link_removal is not None:
                automatic_link_removals.append(
                    {
                        "scope_path": resolved_op.target.scope_path,
                        "uid": resolved_op.target.uid,
                        "field_path": resolved_op.target.field_path,
                        "link_id": resolved_op.automatic_link_removal,
                    }
                )
            elif isinstance(resolved_op, ResolvedRemoveNodePlan) and resolved_op.link_rewires:
                re_stitches.append(
                    {
                        "scope_path": resolved_op.node_ref.target.scope_path,
                        "uid": resolved_op.node_ref.target.uid,
                        "class_type": resolved_op.node_ref.class_type,
                        "link_rewrites": [
                            {
                                "scope_path": rewire.scope_path,
                                "link_id": rewire.link_id,
                                "old_origin_id": rewire.old_origin_id,
                                "new_origin_id": rewire.new_origin_id,
                                "new_origin_slot": rewire.new_origin_slot,
                            }
                            for rewire in resolved_op.link_rewires
                        ],
                    }
                )
            elif isinstance(resolved_op, AppliedAddNodeSpec):
                continue
        guard = result.guard_result
        guard_payload = {
            "ok": bool(guard.ok) if guard is not None else True,
            "diagnostics": [
                facade._port_issue_to_dict(issue)
                for issue in (guard.diagnostics if guard is not None else ())
            ],
        }
        normalize_payload = {
            "fallback_used": bool(getattr(guard, "normalize_fallback_used", False)),
            "allow_list_used": bool(getattr(guard, "normalize_allow_list_used", False)),
        }
        return {
            "ops": [op_to_dict(op) for op in state.delta_ops],
            "diagnostics": [facade._port_issue_to_dict(issue) for issue in result.diagnostics],
            "automatic_link_removals": automatic_link_removals,
            "re_stitches": re_stitches,
            "guard_result": guard_payload,
            "normalize": normalize_payload,
        }

    start = time.monotonic()

    original_ui = state.guard_original_ui or state.graph
    if facade._edit_lint_enabled() and state.delta_ops:
        from vibecomfy.porting.edit.lint import LintIndex, lint_delta

        index = LintIndex.build(original_ui)
        lint_result = lint_delta(
            state.delta_ops,
            index,
            schema_provider=state.schema_provider,
        )

        lint_issue_dicts = tuple(_lint_issue_to_dict(issue) for issue in lint_result.issues)

        if lint_result.rejected_count > 0:
            error_issues = tuple(i for i in lint_issue_dicts if i.get("severity") == "error")
            return StageResult(
                stage="apply_delta",
                ok=False,
                blocking=True,
                duration_ms=facade._duration_ms(start),
                issues=error_issues or lint_issue_dicts,
                value={
                    "failure_kind": FailureKind.VALIDATION_ERROR.value,
                    "mutation_started": 0,
                    "op_count": len(state.delta_ops),
                    "lint_rejected": lint_result.rejected_count,
                    "lint_dropped": lint_result.dropped_count,
                },
            )

        if lint_result.passed_count == 0:
            state.ui_payload = original_ui
            state.delta_diagnostics = [dict(d) for d in lint_issue_dicts]
            noop_messages: list[str] = []
            for norm in lint_result.normalizations:
                if norm.disposition == "dropped_noop" and norm.issue is not None:
                    noop_messages.append(norm.issue.message)
            state.lint_noop_messages = tuple(noop_messages)
            state.report = {
                "change": {
                    "mode": "agent_edit_v2_delta",
                    "op_count": len(state.delta_ops),
                    "ops": [],
                    "mutation_started": 0,
                    "lint_noop": True,
                },
                "recovery": [],
                "felt": {},
                "diagnostics": lint_issue_dicts,
            }
            return StageResult(
                stage="apply_delta",
                ok=True,
                blocking=False,
                duration_ms=facade._duration_ms(start),
                issues=lint_issue_dicts,
                value={
                    "mode": "agent_edit_v2_delta",
                    "op_count": 0,
                    "mutation_started": 0,
                    "lint_noop": True,
                    "lint_dropped": lint_result.dropped_count,
                },
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                },
            )

        state.delta_ops = lint_result.surviving
        state.delta_lint = {
            "issues": [dict(d) for d in lint_issue_dicts],
            "dropped": lint_result.dropped_count,
            "rejected": lint_result.rejected_count,
            "passed": lint_result.passed_count,
        }

    result = apply_delta(
        original_ui,
        state.delta_ops,
        schema_provider=state.schema_provider,
    )
    issues = tuple(facade._port_issue_to_dict(issue) for issue in result.diagnostics)
    if not result.ok or result.candidate is None:
        return StageResult(
            stage="apply_delta",
            ok=False,
            blocking=True,
            duration_ms=facade._duration_ms(start),
            issues=issues,
            value={
                "failure_kind": FailureKind.VALIDATION_ERROR.value,
                "mutation_started": result.mutation_started,
                "op_count": len(state.delta_ops),
            },
        )

    state.ui_payload = result.candidate
    candidate_ui_ref = write_json_artifact(state.candidate_ui_path, state.ui_payload)
    ops = [op_to_dict(op) for op in state.delta_ops]
    state.delta_diagnostics = [facade._port_issue_to_dict(issue) for issue in result.diagnostics]
    state.guard_result = {
        "ok": bool(result.guard_result.ok) if result.guard_result is not None else True,
        "diagnostics": [
            facade._port_issue_to_dict(issue)
            for issue in (result.guard_result.diagnostics if result.guard_result is not None else ())
        ],
        "normalize": {
            "fallback_used": bool(getattr(result.guard_result, "normalize_fallback_used", False)),
            "allow_list_used": bool(getattr(result.guard_result, "normalize_allow_list_used", False)),
        },
    }
    state.delta_audit = _build_delta_audit(result)
    state.report = {
        "change": {
            "mode": "agent_edit_v2_delta",
            "op_count": len(ops),
            "ops": ops,
            "mutation_started": result.mutation_started,
        },
        "recovery": [],
        "felt": {},
        "diagnostics": [issue for issue in issues if issue.get("severity") != "info"],
    }
    return StageResult(
        stage="apply_delta",
        ok=True,
        blocking=False,
        duration_ms=facade._duration_ms(start),
        artifacts=(candidate_ui_ref,),
        issues=issues,
        value={
            "mode": "agent_edit_v2_delta",
            "op_count": len(ops),
            "mutation_started": result.mutation_started,
        },
        gate_updates={
            "python_load_ok": True,
            "lower_ok": True,
            "ir_validate_ok": True,
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    )


def _stage_summarize_impl(state: AgentEditState, context: TurnContext) -> StageResult:
    facade = _edit_facade()
    start = time.monotonic()
    queue_result = facade.queue_stage_result(
        recovery_report=(state.report or {}).get("recovery"),
        change_report=(state.report or {}).get("change"),
    )
    facade._record(context, queue_result)
    derive_gates(context, queue_blockers=queue_result.issues)
    if state.report is None:
        state.report = {}
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=facade._duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _recovery_report_from_ui_payload(
    ui_payload: Mapping[str, Any] | None,
    schema_provider: Any,
) -> list[dict[str, Any]]:
    recovery: list[dict[str, Any]] = []
    if ui_payload is None or schema_provider is None:
        return recovery
    nodes = ui_payload.get("nodes")
    if not isinstance(nodes, list):
        return recovery
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema):
        return recovery
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("id", ""))
        class_type = str(node.get("type", ""))
        if not class_type:
            continue
        schema = get_schema(class_type)
        if schema is None:
            recovery.append(
                {
                    "node_id": node_id,
                    "class_type": class_type,
                    "provider": None,
                    "confidence": None,
                    "schema_less": True,
                    "widget_shape_verdict": "not_applicable",
                    "diagnostic": "schema-less: no schema provider evidence for node",
                }
            )
        else:
            recovery.append(
                {
                    "node_id": node_id,
                    "class_type": class_type,
                    "provider": getattr(schema, "source_provider", None),
                    "confidence": getattr(schema, "confidence", None),
                    "schema_less": False,
                    "widget_shape_verdict": "not_applicable",
                }
            )
    return recovery


def _stage_summarize_v2_impl(state: AgentEditState, context: TurnContext) -> StageResult:
    facade = _edit_facade()
    start = time.monotonic()
    recovery_report = (state.report or {}).get("recovery")
    if not recovery_report and state.ui_payload is not None:
        recovery_report = _recovery_report_from_ui_payload(state.ui_payload, state.schema_provider)
    queue_result = facade.queue_stage_result(
        recovery_report=recovery_report,
        change_report=(state.report or {}).get("change"),
    )
    facade._record(context, queue_result)
    derive_gates(context, queue_blockers=queue_result.issues)
    if state.report is None:
        state.report = {}
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "projection": str(state.projection_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=facade._duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "mode": "agent_edit_v2_delta",
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _stage_audit_impl(
    state: AgentEditState,
    context: TurnContext,
    *,
    response: dict[str, Any] | None = None,
    failure: FailureEnvelope | None = None,
):
    facade = _edit_facade()
    metadata: dict[str, Any] = {
        "provider": state.provider_metadata or {},
        "lowering": _build_lowering_audit_entries(state.lowering_evidence),
    }
    if facade._agent_edit_v2_enabled():
        metadata["agent_edit_v2"] = normalize_agent_edit_v2_metadata(
            {
                "enabled": True,
                "op_count": len(state.delta_ops),
                "delta_ops": state.delta_audit or {},
            }
        )
    if facade._agent_edit_batch_repl_enabled():
        metadata["batch_repl"] = {
            "enabled": True,
            "turn_count": state.batch_turn_count,
            "signature_catalog_available": bool(state.batch_signature_catalog),
            "feedback": state.batch_feedback,
            "final_summary": state.batch_final_summary,
            "exit_mode": state.batch_exit_mode,
            "done_summary": state.batch_done_summary,
            "budget_state": _json_safe(state.batch_budget_state),
        }
    if state.revision_evidence is not None:
        metadata["revision_evidence"] = state.revision_evidence.to_dict()
    return facade.write_audit(
        state.turn_dir / "audit",
        context=context,
        turn_state="candidate",
        stage_results=context.stage_results,
        failure=failure,
        response=response,
        artifacts={
            name: Path(path)
            for name, path in (
                state.artifacts
                or {
                    "request": str(state.request_path),
                    "original_ui": str(state.original_ui_path),
                    "before_python": str(state.before_py_path),
                    "after_python": str(state.after_py_path),
                    "python": str(state.after_py_path),
                    "model_request": str(state.model_request_path),
                    "model_response": str(state.model_response_path),
                    "candidate_ui": str(state.candidate_ui_path),
                    "messages": str(state.messages_path),
                }
            ).items()
            if Path(path).exists()
        },
        metadata=metadata,
    )
