"""Agent, agent-delta, and apply-delta stage functions for the agent-edit pipeline.

These stages call the LLM provider (either through the standard agent turn or
the delta-specific path), and then apply the returned operations to the UI
graph with an optional lint gate.
"""

from __future__ import annotations

import os
import time
from typing import Any

from ...audit import write_json_artifact
from ...contracts import (
    FailureKind,
    StageResult,
    TurnContext,
)
from ..artifacts import (
    _normalize_test_client_response,
    _port_issue_to_dict,
)
from ..budget import _duration_ms
from ..client import DeepSeekClient
from ..messages import _lint_issue_to_dict
from ..paths import artifact as _artifact
from ..state import AgentEditState


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_provider_attr(name: str):
    """Look up a provider attribute from the edit facade namespace at call time.

    This exists so that monkeypatches applied to
    ``vibecomfy.comfy_nodes.agent.edit.<name>`` are visible inside the
    stage functions even after they were moved into the internal
    ``agent_edit.stages.agent_delta`` module.  If the edit module is not
    yet loaded (should never happen during normal operation), fall back to
    a direct import from the provider package.
    """
    import sys
    edit_mod = sys.modules.get("vibecomfy.comfy_nodes.agent.edit")
    if edit_mod is not None:
        return getattr(edit_mod, name)
    # Fallback: direct provider import (only reached in exotic import orders)
    from ...provider import (  # pragma: no cover
        build_delta_messages,
        build_messages,
        run_agent_turn,
        run_agent_turn_delta,
    )
    return locals()[name]


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


def _build_delta_audit(
    result: Any,
    delta_ops: tuple[Any, ...],
) -> dict[str, Any]:
    """Build a structured audit payload from a delta application result."""
    from vibecomfy.porting.edit.apply import (
        AppliedAddNodeSpec,
        ResolvedFieldRef,
        ResolvedRemoveNodePlan,
    )
    from vibecomfy.porting.edit.ops import op_to_dict

    automatic_link_removals: list[dict[str, Any]] = []
    re_stitches: list[dict[str, Any]] = []
    for _op, resolved_op in result.resolved_ops:
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
        "ops": [op_to_dict(op) for op in delta_ops],
        "diagnostics": [_port_issue_to_dict(issue) for issue in result.diagnostics],
        "automatic_link_removals": automatic_link_removals,
        "re_stitches": re_stitches,
        "guard_result": guard_payload,
        "normalize": normalize_payload,
    }


# ---------------------------------------------------------------------------
# Stage functions
# ---------------------------------------------------------------------------


def _stage_agent(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    build_messages = _resolve_provider_attr("build_messages")
    run_agent_turn = _resolve_provider_attr("run_agent_turn")
    start = time.monotonic()
    messages = build_messages(task=state.task, python_source=state.python_before, execution_mode="sandboxed_loose")
    write_json_artifact(state.model_request_path, {"messages": messages})
    if deepseek_client is not None:
        agent_result = _normalize_test_client_response(
            deepseek_client(messages)
        )
    else:
        agent_result = run_agent_turn(
            state.task,
            state.python_before,
            route=route,
            model=model,
        )
    state.python_after = agent_result.python
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    model_response_ref = write_json_artifact(
        state.model_response_path,
        agent_result.to_dict(),
    )
    return StageResult(
        stage="agent",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "provider_metadata": state.provider_metadata,
        },
    )


def _stage_agent_delta(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    from vibecomfy.porting.edit.ops import (
        EDIT_OP_RESPONSE_SCHEMA_V2,
        normalize_delta_test_client_response,
    )
    build_delta_messages = _resolve_provider_attr("build_delta_messages")
    run_agent_turn_delta = _resolve_provider_attr("run_agent_turn_delta")

    start = time.monotonic()
    messages = build_delta_messages(
        task=state.task,
        projection=state.projection_text,
        op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
    )
    write_json_artifact(
        state.model_request_path,
        {"messages": messages, "response_contract": "delta"},
    )
    if deepseek_client is not None:
        agent_result = normalize_delta_test_client_response(deepseek_client(messages))
    else:
        agent_result = run_agent_turn_delta(
            state.task,
            state.projection_text,
            op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
            route=route,
            model=model,
        )
    state.delta_ops = agent_result.delta
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    model_response_ref = write_json_artifact(
        state.model_response_path,
        agent_result.to_dict(),
    )
    return StageResult(
        stage="agent_delta",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "op_count": len(agent_result.delta),
            "provider_metadata": state.provider_metadata,
        },
    )


def _stage_apply_delta(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.apply import apply_delta
    from vibecomfy.porting.edit.ops import op_to_dict

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
    state.delta_audit = _build_delta_audit(result, state.delta_ops)
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
