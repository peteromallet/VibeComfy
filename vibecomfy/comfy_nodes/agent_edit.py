from __future__ import annotations

import dataclasses
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .agent_audit import (
    artifact_ref_for_path,
    write_allocation_failure_audit,
    write_audit,
    write_json_artifact,
)
from .agent_contracts import (
    ArtifactRef,
    FailureEnvelope,
    FailureKind,
    StageResult,
    TurnContext,
    classify_failure,
    failure_envelope,
    success_envelope,
)
from .agent_gates import (
    apply_stage_gate_updates,
    derive_gates,
    initialize_gates,
    update_state_match_gate,
)
from .agent_provider import AgentTurnResult, build_messages, run_agent_turn
from .agent_diagnostics import lower_stage_result, queue_stage_result
from .agent_session import allocate_turn, payload_hash, record_idempotent_response, turn_dir_for

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

DeepSeekClient = Callable[[list[dict[str, str]]], dict[str, str]]

_SESSION_ROOT = Path("out/editor_sessions")


@dataclass
class AgentEditState:
    task: str
    graph: dict[str, Any]
    request_payload: dict[str, Any]
    schema_provider: Any
    baseline_graph_hash: str | None
    submit_graph_hash: str | None
    submitted_client_graph_hash: str | None
    session_dir: Path
    turn_dir: Path
    request_path: Path
    original_ui_path: Path
    before_py_path: Path
    after_py_path: Path
    model_request_path: Path
    model_response_path: Path
    candidate_ui_path: Path
    messages_path: Path
    workflow: Any = None
    edited_workflow: Any = None
    original_intent_workflow: VibeWorkflow | None = None
    prior_store: Any = None
    python_before: str = ""
    python_after: str = ""
    user_message: str = ""
    lowering_evidence: list[dict[str, Any]] = field(default_factory=list)
    lowering_recovery_entries: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] | None = None
    ui_payload: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    artifacts: dict[str, str] | None = None


class _StageBlocked(Exception):
    def __init__(self, result: StageResult, failure: FailureEnvelope | None = None) -> None:
        super().__init__(result.stage)
        self.result = result
        self.failure = failure


def _build_lowering_recovery_entries(
    lowering_evidence: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in lowering_evidence:
        loop_node_id = item.get("loop_node_id")
        loop_uid = item.get("loop_uid")
        lowered_native_count = item.get("lowered_node_count", 0)
        entries.append(
            {
                "node_id": loop_node_id,
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": loop_uid,
                "lowered": True,
                "runtime_backed": False,
                "provider": "static_lowering",
                "confidence": 1.0,
                "diagnostic": f"statically lowered to {lowered_native_count} native node(s)",
                "lowered_native_count": lowered_native_count,
                "source_node_id": loop_node_id,
                "source_node_uid": loop_uid,
                "original_intent_hash": item.get("original_intent_hash"),
                "lowered_fragment_hash": item.get("lowered_fragment_hash"),
                "layout_policy": item.get("layout_policy"),
                "variable": item.get("variable"),
                "iterations": item.get("iterations"),
                "iteration_values": list(item.get("iteration_values") or ()),
            }
        )
    return entries


def _build_lowering_change_entries(
    lowering_evidence: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in lowering_evidence:
        loop_node_id = item.get("loop_node_id")
        loop_uid = item.get("loop_uid")
        entries.append(
            {
                "node_id": loop_node_id,
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": loop_uid,
                "lowered": True,
                "source_node_id": loop_node_id,
                "source_node_uid": loop_uid,
                "lowered_native_count": item.get("lowered_node_count", 0),
                "original_intent_hash": item.get("original_intent_hash"),
                "lowered_fragment_hash": item.get("lowered_fragment_hash"),
            }
        )
    return entries


def _build_lowering_audit_entries(
    lowering_evidence: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in lowering_evidence:
        entry = dict(item)
        if "lowered_node_count" in entry:
            entry["node_count"] = entry.pop("lowered_node_count")
        if "lowered_fragment_hash" in entry:
            entry["lowered_graph_fragment_hash"] = entry.pop("lowered_fragment_hash")
        entries.append(entry)
    return entries


def _inject_lowering_provenance(state: AgentEditState) -> None:
    if state.report is None or not state.lowering_evidence:
        state.lowering_recovery_entries = []
        return
    recovery_entries = _build_lowering_recovery_entries(state.lowering_evidence)
    state.lowering_recovery_entries = recovery_entries
    recovery_report = state.report.setdefault("recovery", [])
    if isinstance(recovery_report, list):
        recovery_report.extend(recovery_entries)
    change_report = state.report.setdefault("change", {})
    if isinstance(change_report, dict):
        change_report["lowered"] = _build_lowering_change_entries(state.lowering_evidence)


def _safe_session_id(value: str | None = None) -> str:
    if not value:
        return uuid.uuid4().hex
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
    return safe[:80] or uuid.uuid4().hex


def _artifact(path: Path) -> ArtifactRef:
    return artifact_ref_for_path(path)


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _normalize_test_client_response(response: dict[str, str]) -> AgentTurnResult:
    python = response.get("python")
    message = response.get("message")
    if not isinstance(python, str):
        raise ValueError("Agent JSON must include string key `python`.")
    if not isinstance(message, str):
        raise ValueError("Agent JSON must include string key `message`.")
    return AgentTurnResult(
        python=python,
        message=message,
        route="test_client",
        audit_metadata={"provider": "test_client"},
    )


def _record(context: TurnContext, result: StageResult) -> StageResult:
    context.stage_results[result.stage] = result
    apply_stage_gate_updates(context, result)
    return result


def _stage_ingest(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.layout_store import store_from_ui_json

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    original_ui_ref = write_json_artifact(state.original_ui_path, state.graph)
    state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
    state.prior_store = store_from_ui_json(state.graph)
    update_state_match_gate(
        context,
        baseline_graph_hash=state.baseline_graph_hash,
        client_graph_hash=state.submit_graph_hash,
        client_graph_hash_label="submit_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(
                {
                    "code": "stale_state_mismatch",
                    "severity": "error",
                    "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
                    "message": "Submitted graph no longer matches the current baseline.",
                    "detail": dict(state_match_gate.evidence),
                },
            ),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
    )


def _stage_convert(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.convert import port_convert_and_write, port_convert_workflow

    start = time.monotonic()
    conversion = port_convert_workflow(
        state.workflow,
        source_path=str(state.original_ui_path),
        schema_provider=state.schema_provider,
        raw_workflow=state.graph,
    )
    port_convert_and_write(conversion, state.before_py_path)
    state.python_before = state.before_py_path.read_text(encoding="utf-8")
    return StageResult(
        stage="convert",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.before_py_path),),
    )


def _stage_agent(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    start = time.monotonic()
    messages = build_messages(task=state.task, python_source=state.python_before)
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


def _stage_load_python(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.security.agent_generated_loader import load_agent_generated_scratchpad

    start = time.monotonic()
    state.after_py_path.write_text(state.python_after, encoding="utf-8")
    state.edited_workflow = load_agent_generated_scratchpad(state.after_py_path)
    return StageResult(
        stage="load_python",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.after_py_path),),
        gate_updates={"python_load_ok": True},
    )


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
    from .agent_diagnostics import validate_stage_result

    start = time.monotonic()
    result = validate_stage_result(state.edited_workflow, schema_provider=state.schema_provider)
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_emit(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.layout import evaluate_felt_delta
    from vibecomfy.porting.layout_store import store_from_ui_json, write_store
    from vibecomfy.porting.ui_emitter import emit_ui_json

    start = time.monotonic()
    recovery_report: list[dict[str, Any]] = []
    change_report_out: list[Any] = []
    ui_payload = emit_ui_json(
        state.edited_workflow,
        schema_provider=state.schema_provider,
        prior_store=state.prior_store,
        recovery_report=recovery_report,
        change_report_out=change_report_out,
        guard_original_ui=state.graph,
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


def _stage_summarize(state: AgentEditState, context: TurnContext) -> StageResult:
    start = time.monotonic()
    queue_result = queue_stage_result(
        recovery_report=(state.report or {}).get("recovery"),
        change_report=(state.report or {}).get("change"),
    )
    _record(context, queue_result)
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
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _stage_audit(
    state: AgentEditState,
    context: TurnContext,
    *,
    response: dict[str, Any] | None = None,
    failure: FailureEnvelope | None = None,
) -> ArtifactRef:
    return write_audit(
        state.turn_dir / "audit",
        context=context,
        turn_state="candidate",
        stage_results=context.stage_results,
        failure=failure,
        response=response,
        artifacts={
            name: Path(path)
            for name, path in (state.artifacts or {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "messages": str(state.messages_path),
            }).items()
            if Path(path).exists()
        },
        metadata={
            "provider": state.provider_metadata or {},
            "lowering": _build_lowering_audit_entries(state.lowering_evidence),
        },
    )


def _write_unknown_transition_audits(
    *,
    session_root: Path,
    session_id: str,
    baseline_turn_id: str | None,
    unknown_transitions: tuple[dict[str, Any], ...],
    request_payload: Mapping[str, Any],
) -> None:
    for transition in unknown_transitions:
        turn_id = transition.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        try:
            write_audit(
                turn_dir_for(session_root, session_id, turn_id) / "unknown_audit",
                context=TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    baseline_turn_id=baseline_turn_id,
                ),
                turn_state="unknown",
                artifacts={"request": dict(request_payload)},
                metadata={"action": "unknown", **transition},
            )
        except Exception:
            continue


def _failure_response(
    state: AgentEditState,
    context: TurnContext,
    failure: FailureEnvelope,
) -> dict[str, Any]:
    derive_gates(
        context,
        baseline_graph_hash=state.baseline_graph_hash,
        client_graph_hash=state.submit_graph_hash,
    )
    failure = dataclasses.replace(
        failure,
        canvas_apply_allowed=context.canvas_apply_allowed,
        queue_allowed=context.queue_allowed,
    )
    try:
        audit_ref = _stage_audit(state, context, failure=failure)
        failure = dataclasses.replace(failure, audit_ref=audit_ref)
    except Exception as audit_exc:
        failure = dataclasses.replace(failure, audit_error=str(audit_exc))
    return failure.to_dict()


def _run_stage(
    name: str,
    state: AgentEditState,
    context: TurnContext,
    fn: Callable[..., StageResult],
    *args: Any,
    **kwargs: Any,
) -> StageResult:
    try:
        result = fn(state, context, *args, **kwargs)
    except Exception as exc:
        failure_stage = "agent_response" if name == "agent" else name
        failure = classify_failure(failure_stage, exc, context)
        result = StageResult(
            stage=name,
            ok=False,
            blocking=True,
            issues=(failure.agent_failure_context,),
        )
        _record(context, result)
        raise _StageBlocked(result, failure) from exc
    _record(context, result)
    if result.blocking:
        failure_kind = None
        if isinstance(result.value, dict):
            failure_kind = result.value.get("failure_kind")
        failure = failure_envelope(
            failure_kind or FailureKind.VALIDATION_ERROR,
            name,
            context,
            agent_failure_context={
                "explanation": f"Stage {name} blocked the agent edit.",
                "issues": [dict(issue) for issue in result.issues if isinstance(issue, dict)],
            },
        )
        raise _StageBlocked(result, failure)
    return result


def handle_agent_edit(
    payload: dict[str, Any],
    *,
    schema_provider: Any = None,
    deepseek_client: DeepSeekClient | None = None,
    session_root: Path | None = None,
) -> dict[str, Any]:
    """Convert current UI JSON to Python, ask the agent to edit it, emit UI JSON."""
    from vibecomfy.schema import get_schema_provider

    if not isinstance(payload, dict):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        ).to_dict()

    task = payload.get("task")
    graph = payload.get("graph")
    if not isinstance(task, str) or not task.strip():
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "`task` is required."},
        ).to_dict()
    if not isinstance(graph, dict):
        return failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={
                "explanation": "`graph` must be a ComfyUI UI JSON object."
            },
        ).to_dict()

    if schema_provider is None:
        schema_provider = get_schema_provider("local")
    root = session_root or _SESSION_ROOT
    session_id = _safe_session_id(payload.get("session_id"))
    allocation = allocate_turn(
        session_root=root,
        session_id=session_id,
        request_payload=payload,
        idempotency_key=payload.get("idempotency_key")
        if isinstance(payload.get("idempotency_key"), str)
        else None,
    )
    if allocation.replay is not None:
        return allocation.replay.response
    if allocation.conflict is not None:
        try:
            audit_ref = write_allocation_failure_audit(
                allocation.session_dir,
                session_id=session_id,
                failure=allocation.conflict.failure,
                request=payload,
            )
            return dataclasses.replace(allocation.conflict.failure, audit_ref=audit_ref).to_dict()
        except Exception:
            return allocation.conflict.failure.to_dict()

    context = allocation.context
    context.client_graph_hash = payload.get("client_graph_hash") if isinstance(payload.get("client_graph_hash"), str) else None
    initialize_gates(context)
    _write_unknown_transition_audits(
        session_root=root,
        session_id=session_id,
        baseline_turn_id=context.baseline_turn_id,
        unknown_transitions=allocation.unknown_transitions,
        request_payload=payload,
    )
    turn_dir = allocation.turn_dir
    turn_record = allocation.state.get("turns", {}).get(context.turn_id)
    baseline_graph_hash = (
        allocation.state.get("baseline_graph_hash")
        if isinstance(allocation.state.get("baseline_graph_hash"), str)
        else None
    )
    submit_graph_hash = (
        turn_record.get("submit_graph_hash")
        if isinstance(turn_record, dict) and isinstance(turn_record.get("submit_graph_hash"), str)
        else None
    )
    submitted_client_graph_hash = (
        turn_record.get("submitted_client_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_graph_hash"), str)
        else None
    )
    state = AgentEditState(
        task=task,
        graph=graph,
        request_payload=payload,
        schema_provider=schema_provider,
        baseline_graph_hash=baseline_graph_hash,
        submit_graph_hash=submit_graph_hash,
        submitted_client_graph_hash=submitted_client_graph_hash,
        session_dir=allocation.session_dir,
        turn_dir=turn_dir,
        request_path=turn_dir / "request.json",
        original_ui_path=turn_dir / "original.ui.json",
        before_py_path=turn_dir / "before.py",
        after_py_path=turn_dir / "after.py",
        model_request_path=turn_dir / "model_request.json",
        model_response_path=turn_dir / "model_response.json",
        candidate_ui_path=turn_dir / "candidate.ui.json",
        messages_path=turn_dir / "messages.jsonl",
    )

    try:
        _run_stage("ingest", state, context, _stage_ingest)
        _run_stage("convert", state, context, _stage_convert)
        _run_stage(
            "agent",
            state,
            context,
            _stage_agent,
            deepseek_client=deepseek_client,
            route=payload.get("route") if isinstance(payload.get("route"), str) else None,
            model=payload.get("model") if isinstance(payload.get("model"), str) else None,
        )
        _run_stage("load_python", state, context, _stage_load_python)
        _run_stage("lower", state, context, _stage_lower)
        _run_stage("validate", state, context, _stage_validate)
        _run_stage("emit", state, context, _stage_emit)
        _run_stage("summarize", state, context, _stage_summarize)
    except _StageBlocked as blocked:
        response = _failure_response(state, context, blocked.failure or classify_failure(blocked.result.stage, blocked, context))
        record_idempotent_response(
            session_root=root,
            session_id=session_id,
            scope="edit",
            idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
            request_hash=allocation.request_hash,
            response=response,
            response_path=turn_dir / "response.json",
            operation="edit",
            turn_id=context.turn_id,
        )
        return response

    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
    )
    candidate_graph_hash = payload_hash(state.ui_payload)
    response.update(
        {
            "baseline_graph_hash": state.baseline_graph_hash,
            "submit_graph_hash": state.submit_graph_hash,
            "submitted_client_graph_hash": state.submitted_client_graph_hash,
            "candidate_graph_hash": candidate_graph_hash,
            "client_graph_hash": context.client_graph_hash,
        }
    )
    try:
        audit_ref = _stage_audit(state, context, response=response)
        response["audit_ref"] = audit_ref.to_dict()
    except Exception as exc:
        failure = failure_envelope(
            FailureKind.AUDIT_WRITE_FAILURE,
            "audit",
            context,
            agent_failure_context={"explanation": str(exc)},
            audit_error=str(exc),
        )
        return failure.to_dict()
    record_idempotent_response(
        session_root=root,
        session_id=session_id,
        scope="edit",
        idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
        request_hash=allocation.request_hash,
        response=response,
        response_path=turn_dir / "response.json",
        operation="edit",
        turn_id=context.turn_id,
    )
    return response


__all__ = [
    "AgentEditState",
    "DeepSeekClient",
    "handle_agent_edit",
]
