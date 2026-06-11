from __future__ import annotations

import dataclasses
import json
import os
import time
from typing import TYPE_CHECKING, Any, Mapping

from ..agent_audit import write_json_artifact
from ..agent_contracts import (
    FailureKind,
    StageResult,
    TurnContext,
)
from ..agent_diagnostics import lower_stage_result, validate_stage_result
from .humanize import _artifact, _duration_ms, _inject_lowering_provenance

if TYPE_CHECKING:
    from ..agent_edit import AgentEditState


def _port_issue_to_dict(issue: Any) -> dict[str, Any]:
    to_json = getattr(issue, "to_json", None)
    if callable(to_json):
        rendered = to_json()
        if isinstance(rendered, dict):
            return rendered
    if isinstance(issue, Mapping):
        return dict(issue)
    return {"code": type(issue).__name__, "message": str(issue), "severity": "error"}


def _edit_lint_enabled() -> bool:
    """Return True unless VIBECOMFY_AGENT_EDIT_LINT is explicitly disabled.

    Accepts ``0``, ``false``, ``off``, or ``no`` (case-insensitive) as disabled
    values.  Defaults to ON (enabled) when the env var is unset or set to any
    other value.

    Rollout flag / off-switch
    -------------------------
    Setting ``VIBECOMFY_AGENT_EDIT_LINT=0`` disables the entire lint gate in
    ``_stage_apply_delta`` and ``_stage_agent_batch_repl``.  When lint is off the
    pipeline falls back to pre-lint behaviour: ``apply_delta()`` receives every
    op unchecked, no-ops are not pre-filtered, and diagnostics come from
    ``resolve_delta`` / ``apply_delta`` rather than from ``lint_delta()``.  This
    flag is intended as an emergency off-switch; the default path is *enabled*.
    """
    raw = os.getenv("VIBECOMFY_AGENT_EDIT_LINT")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "off", "no"}


def _stage_lower(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.lowering import lower_workflow

    start = time.monotonic()
    original_workflow = state.edited_workflow
    lowering = lower_workflow(state.edited_workflow, schema_provider=state.schema_provider)
    result = lower_stage_result(lowering)
    if result.ok:
        if lowering.lowered_count > 0:
            if lowering.workflow is not None:
                state.edited_workflow = lowering.workflow
            state.original_intent_workflow = original_workflow
        else:
            state.edited_workflow = original_workflow
        state.lowering_evidence = [dict(dataclasses.asdict(item)) for item in lowering.evidence]
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_validate(state: AgentEditState, _context: TurnContext) -> StageResult:
    start = time.monotonic()
    result = validate_stage_result(state.edited_workflow, schema_provider=state.schema_provider)
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_emit(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.layout import evaluate_felt_delta
    from vibecomfy.porting.layout_store import store_from_ui_json, write_store
    from vibecomfy.porting.emit.ui import emit_ui_json

    start = time.monotonic()
    recovery_report: list[dict[str, Any]] = []
    change_report_out: list[Any] = []
    ui_payload = emit_ui_json(
        state.edited_workflow,
        schema_provider=state.schema_provider,
        prior_store=state.prior_store,
        recovery_report=recovery_report,
        change_report_out=change_report_out,
        guard_original_ui=state.guard_original_ui or state.graph,
    )
    state.candidate_ui_path.write_text(
        json.dumps(ui_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_store(state.after_py_path, store_from_ui_json(ui_payload))
    state.ui_payload = ui_payload

    reroute_uids = frozenset(
        (node.uid or node_id)
        for node_id, node in state.edited_workflow.nodes.items()
        if node.class_type == "Reroute"
    )
    felt_report = (
        evaluate_felt_delta(
            state.prior_store,
            ui_payload,
            change_report_out[0],
            reroute_uids=reroute_uids,
        )
        if change_report_out
        else None
    )
    state.report = {
        "change": dataclasses.asdict(change_report_out[0]) if change_report_out else {},
        "recovery": recovery_report,
        "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
    }
    _inject_lowering_provenance(state)
    return StageResult(
        stage="emit",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.candidate_ui_path),),
        gate_updates={
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    )


def _stage_apply_delta(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.apply import apply_delta
    from vibecomfy.porting.edit.apply import (
        AppliedAddNodeSpec,
        ResolvedFieldRef,
        ResolvedRemoveNodePlan,
    )
    from vibecomfy.porting.edit.ops import op_to_dict

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
                _port_issue_to_dict(issue) for issue in (guard.diagnostics if guard is not None else ())
            ],
        }
        normalize_payload = {
            "fallback_used": bool(getattr(guard, "normalize_fallback_used", False)),
            "allow_list_used": bool(getattr(guard, "normalize_allow_list_used", False)),
        }
        return {
            "ops": [op_to_dict(op) for op in state.delta_ops],
            "diagnostics": [_port_issue_to_dict(issue) for issue in result.diagnostics],
            "automatic_link_removals": automatic_link_removals,
            "re_stitches": re_stitches,
            "guard_result": guard_payload,
            "normalize": normalize_payload,
        }

    start = time.monotonic()

    # ── lint gate (VIBECOMFY_AGENT_EDIT_LINT defaults ON) ──────────────────
    original_ui = state.guard_original_ui or state.graph
    if _edit_lint_enabled() and state.delta_ops:
        from vibecomfy.porting.edit.lint import LintIndex, lint_delta

        index = LintIndex.build(original_ui)
        lint_result = lint_delta(
            state.delta_ops,
            index,
            schema_provider=state.schema_provider,
        )

        def _lint_issue_to_dict(issue: Any) -> dict[str, Any]:
            return {
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
                "op_index": getattr(issue, "op_index", None),
                "op_kind": getattr(issue, "op_kind", None),
            }

        lint_issue_dicts = tuple(
            _lint_issue_to_dict(issue) for issue in lint_result.issues
        )

        # Rejected ops → fail before mutation
        if lint_result.rejected_count > 0:
            error_issues = tuple(
                i for i in lint_issue_dicts if i.get("severity") == "error"
            )
            return StageResult(
                stage="apply_delta",
                ok=False,
                blocking=True,
                duration_ms=_duration_ms(start),
                issues=error_issues or lint_issue_dicts,
                value={
                    "failure_kind": FailureKind.VALIDATION_ERROR.value,
                    "mutation_started": 0,
                    "op_count": len(state.delta_ops),
                    "lint_rejected": lint_result.rejected_count,
                    "lint_dropped": lint_result.dropped_count,
                },
            )

        # All ops dropped as no-ops → clean no-op turn
        if lint_result.passed_count == 0:
            state.ui_payload = original_ui
            state.delta_diagnostics = [
                dict(d) for d in lint_issue_dicts
            ]
            # Collect human-readable no-op messages for user-facing display
            _noop_msgs: list[str] = []
            for norm in lint_result.normalizations:
                if norm.disposition == "dropped_noop" and norm.issue is not None:
                    _noop_msgs.append(norm.issue.message)
            state.lint_noop_messages = tuple(_noop_msgs)
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
                duration_ms=_duration_ms(start),
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

        # Surviving ops proceed to apply
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
    issues = tuple(_port_issue_to_dict(issue) for issue in result.diagnostics)
    if not result.ok or result.candidate is None:
        return StageResult(
            stage="apply_delta",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
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
    state.delta_diagnostics = [_port_issue_to_dict(issue) for issue in result.diagnostics]
    state.guard_result = {
        "ok": bool(result.guard_result.ok) if result.guard_result is not None else True,
        "diagnostics": [
            _port_issue_to_dict(issue)
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
        duration_ms=_duration_ms(start),
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
