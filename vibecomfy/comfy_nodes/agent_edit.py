from __future__ import annotations

import ast
import base64
import dataclasses
import difflib
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

from .agent_audit import (
    artifact_ref_for_path,
    normalize_agent_edit_v2_metadata,
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
    TurnOutcome,
    apply_eligibility_payload,
    classify_failure,
    derive_apply_eligibility,
    ensure_agent_edit_response_contract,
    failure_envelope,
    product_failure_envelope_fields,
    public_outcome_from_turn_outcome,
    success_envelope,
    turn_envelope,
)
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.porting.widgets.aliases import widget_names_for_class
from .agent_gates import (
    apply_stage_gate_updates,
    derive_gates,
    initialize_gates,
    update_state_match_gate,
)
from .agent_provider import (
    AgentTurnResult,
    BatchTurnResult,
    build_batch_messages,
    build_delta_messages,
    build_messages,
    ensure_sentence_message,
    run_agent_turn,
    run_agent_turn_batch,
    run_agent_turn_delta,
)
from .agent_diagnostics import lower_stage_result, queue_stage_result
from .agent_session import (
    allocate_turn,
    payload_hash,
    read_state,
    record_idempotent_response,
    session_dir_for,
    structural_graph_hash,
    turn_dir_for,
)

if TYPE_CHECKING:
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.workflow import VibeWorkflow

DeepSeekClient = Callable[[list[dict[str, str]]], dict[str, str]]

_SESSION_ROOT = Path("out/editor_sessions")
DEFAULT_CHAT_DISPLAY_MESSAGES = 50
PROMPT_MEMORY_MESSAGES = 5
LOGGER = logging.getLogger(__name__)
_WARNED_LEGACY_CONTRACTS: set[str] = set()
_WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS: set[str] = set()


@dataclass
class AgentEditState:
    task: str
    graph: dict[str, Any]
    request_payload: dict[str, Any]
    schema_provider: Any
    baseline_graph_hash: str | None
    submit_graph_hash: str | None
    submit_structural_graph_hash: str | None
    submitted_client_graph_hash: str | None
    submitted_client_structural_graph_hash: str | None
    session_dir: Path
    turn_dir: Path
    request_path: Path
    original_ui_path: Path
    before_py_path: Path
    after_py_path: Path
    projection_path: Path
    model_request_path: Path
    model_response_path: Path
    candidate_ui_path: Path
    messages_path: Path
    workflow: Any = None
    edited_workflow: Any = None
    original_intent_workflow: VibeWorkflow | None = None
    prior_store: Any = None
    guard_original_ui: dict[str, Any] | None = None
    python_before: str = ""
    python_after: str = ""
    user_message: str = ""
    lowering_evidence: list[dict[str, Any]] = field(default_factory=list)
    lowering_recovery_entries: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, Any] | None = None
    ui_payload: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    artifacts: dict[str, str] | None = None
    projection_text: str = ""
    delta_ops: tuple[Any, ...] = ()
    delta_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    delta_audit: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    # Batch REPL state (gated behind VIBECOMFY_AGENT_EDIT_BATCH_REPL=1)
    batch_session: EditSession | None = None
    batch_signature_catalog: str = ""
    batch_turns: list[dict[str, Any]] = field(default_factory=list)
    batch_field_changes: tuple[FieldChange, ...] = ()
    batch_noop_field_changes: tuple[FieldChange, ...] = ()
    batch_budget_state: dict[str, Any] = field(default_factory=dict)
    batch_turn_count: int = 0
    batch_max_turns: int = 20
    batch_max_consecutive_errors: int = 3
    batch_feedback: str = ""
    batch_final_summary: str = ""
    batch_exit_mode: str = ""
    batch_done_summary: str = ""
    lint_noop_messages: tuple[str, ...] = ()


class _StageBlocked(Exception):
    def __init__(self, result: StageResult, failure: FailureEnvelope | None = None) -> None:
        super().__init__(result.stage)
        self.result = result
        self.failure = failure



from .stages.humanize import (
    _ABSENT_FIELD_OLD,
    _MISSING_FIELD_CHANGE_OLD,
    _article_for,
    _batch_candidate_graph_changed,
    _batch_warning_sentence,
    _build_lowering_audit_entries,
    _build_lowering_change_entries,
    _build_lowering_recovery_entries,
    _change_details_payload,
    _change_subject,
    _compact_diag_to_dict,
    _display_value,
    _duration_ms,
    _field_change_is_noop,
    _field_changes_payload,
    _first_link_source_label,
    _format_available_node_names,
    _format_batch_report,
    _format_batch_report_json,
    _format_node_variable_index,
    _format_query_output,
    _format_statement_source,
    _human_change_phrase,
    _humanized_edit_message,
    _humanized_noop_message,
    _inject_lowering_provenance,
    _is_link_endpoint,
    _iter_ui_graph_nodes,
    _iter_ui_nodes,
    _join_human_list,
    _json_safe,
    _landed_edit_lead,
    _link_endpoint_parts,
    _looks_internal_uid,
    _node_class_label,
    _node_key_values,
    _node_label_by_uid,
    _node_phrase,
    _noop_field_changes,
    _normalize_test_client_batch_response,
    _normalize_test_client_response,
    _operation_detail_payload,
    _original_ui_field_value,
    _present_class_types,
    _real_field_changes,
    _render_batch_diff,
    _repair_field_changes_from_original_ui,
    _resolve_endpoint_label,
    _resolve_output_slot_name,
    _safe_session_id,
    _sentence_case,
    _structural_change_phrases,
    _synthesize_batch_repl_message,
    _total_landed_edit_count,
    _ui_display_widget_value_for_field,
    _ui_node_by_uid,
    _ui_node_uid,
    _ui_node_uid_aliases,
    _ui_widget_value_for_field,
    _widget_index_from_field_path,
    _artifact
)

from .stages.emit import (
    _edit_lint_enabled,
    _port_issue_to_dict,
    _stage_apply_delta,
    _stage_emit,
    _stage_lower,
    _stage_validate,
)

from .stages.agent import (
    _stage_agent,
    _stage_agent_delta,
)

from .stages.batch_repl import (
    _batch_budget_failure_kind,
    _batch_has_landed_edits,
    _stage_agent_batch_repl,
)

from .stages.summarize import (
    _stage_summarize,
    _stage_summarize_v2,
)

from .stages.audit import (
    _stage_audit,
    _write_unknown_transition_audits,
)

from .session_io import (
    _compact_chat_change_details,
    _latest_session_candidate_payload,
    _read_turn_response_payload,
    _stamped_message_outcome,
    _stamped_turn_response_outcome,
    _trim_chat_text,
    _write_turn_chat_artifact,
    read_session_bundle,
    read_session_chat,
    read_session_json,
)

_CLARIFY_CALL_RE = re.compile(
    r'(?m)^\s*clarify\("((?:[^"\\]|\\.)*)"\)\s*$'
)


_BATCH_EXIT_PURE_CLARIFY = "pure_clarify"
_BATCH_EXIT_EDIT_CLARIFY = "edit_clarify"
_BATCH_EXIT_DONE = "done"
_BATCH_EXIT_BUDGET = "budget"
_BATCH_EXIT_NOOP = "noop"


@dataclass(frozen=True)
class TerminalClarifySplit:
    batch: str
    message: str | None


def _extract_clarify_message(batch: str) -> str | None:
    matches = _CLARIFY_CALL_RE.findall(batch)
    if not matches:
        return None
    try:
        return json.loads(f'"{matches[0]}"')
    except json.JSONDecodeError:
        return matches[0]


def _is_terminal_clarify_expr(node: ast.stmt) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    call = node.value
    if not isinstance(call.func, ast.Name) or call.func.id != "clarify":
        return False
    return (
        len(call.args) == 1
        and not call.keywords
        and isinstance(call.args[0], ast.Constant)
        and isinstance(call.args[0].value, str)
    )


def _contains_clarify_call(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "clarify"
        for child in ast.walk(node)
    )


def _offset_from_ast_position(batch: str, lineno: int, col_offset: int) -> int:
    lines = batch.splitlines(keepends=True)
    if lineno <= 0:
        return 0
    before = sum(len(line) for line in lines[: lineno - 1])
    line = lines[lineno - 1] if lineno - 1 < len(lines) else ""
    # AST column offsets are UTF-8 byte offsets. Convert them back to Python
    # character offsets before slicing the original source string.
    char_col = len(line.encode("utf-8")[:col_offset].decode("utf-8", errors="ignore"))
    return before + char_col


def _decode_clarify_literal(raw: str) -> str:
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw


def _split_terminal_clarify_line_regex(batch: str) -> TerminalClarifySplit:
    matches = list(_CLARIFY_CALL_RE.finditer(batch))
    if not matches:
        return TerminalClarifySplit(batch=batch, message=None)
    terminal_match = matches[-1]
    if any(match.start() != terminal_match.start() for match in matches[:-1]):
        return TerminalClarifySplit(batch=batch, message=None)
    trailing_lines = batch[terminal_match.end() :].splitlines()
    if any(line.strip() and not line.lstrip().startswith("#") for line in trailing_lines):
        return TerminalClarifySplit(batch=batch, message=None)
    return TerminalClarifySplit(
        batch=batch[: terminal_match.start()].rstrip(),
        message=_decode_clarify_literal(terminal_match.group(1)),
    )


def split_terminal_clarify(batch: str) -> TerminalClarifySplit:
    """Split a final top-level clarify("...") call from editable batch code."""
    try:
        module = ast.parse(batch)
    except SyntaxError:
        return _split_terminal_clarify_line_regex(batch)
    if not module.body:
        return TerminalClarifySplit(batch=batch, message=None)

    terminal = module.body[-1]
    if not _is_terminal_clarify_expr(terminal):
        return TerminalClarifySplit(batch=batch, message=None)
    if any(_contains_clarify_call(stmt) for stmt in module.body[:-1]):
        return TerminalClarifySplit(batch=batch, message=None)

    call = terminal.value
    assert isinstance(call, ast.Call)
    message_node = call.args[0]
    assert isinstance(message_node, ast.Constant)
    start = _offset_from_ast_position(batch, terminal.lineno, terminal.col_offset)
    editable_batch = batch[:start].rstrip()
    if editable_batch.endswith(";"):
        editable_batch = editable_batch[:-1].rstrip()
    return TerminalClarifySplit(batch=editable_batch, message=message_node.value)


def _warn_legacy_contract_once(contract: str) -> None:
    if contract in _WARNED_LEGACY_CONTRACTS:
        return
    _WARNED_LEGACY_CONTRACTS.add(contract)
    LOGGER.warning(
        "agent-edit legacy contract '%s' selected via VIBECOMFY_AGENT_EDIT_LEGACY; "
        "this is deprecated and will be removed",
        contract,
    )


def _warn_ignored_public_protocol_envs_once(env_names: tuple[str, ...]) -> None:
    unseen = tuple(name for name in env_names if name not in _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS)
    if not unseen:
        return
    _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS.update(unseen)
    LOGGER.warning(
        "agent-edit ignoring legacy public protocol env vars (%s); product protocol is always "
        "'batch_repl'. For dev-only legacy protocols set "
        "VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS=1 and "
        "VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL=delta|full.",
        ", ".join(unseen),
    )


def _agent_edit_contract() -> str:
    ignored_public_envs = tuple(
        name
        for name in (
            "VIBECOMFY_AGENT_EDIT_LEGACY",
            "VIBECOMFY_AGENT_EDIT_V2",
            "VIBECOMFY_AGENT_EDIT_BATCH_REPL",
        )
        if os.getenv(name) is not None
    )
    if ignored_public_envs:
        _warn_ignored_public_protocol_envs_once(ignored_public_envs)
    if os.getenv("VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS") == "1":
        dev_protocol = os.getenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL")
        if dev_protocol in {"delta", "full"}:
            _warn_legacy_contract_once(dev_protocol)
            return dev_protocol
    return "batch_repl"


def _agent_edit_v2_enabled() -> bool:
    return _agent_edit_contract() == "delta"


def _agent_edit_batch_repl_enabled() -> bool:
    return _agent_edit_contract() == "batch_repl"


from .stages import _record

def _stamp_identity_on_original(graph: dict[str, Any], workflow: Any) -> int:
    """Phase 1 (concrete-tree migration): stamp the IR's stable uid onto the
    *original* UI nodes so the delta-scope guard (`guard_emit`) and pin-opaque
    can match on a user's FIRST edit. A hand-authored ComfyUI canvas carries no
    `properties.vibecomfy_uid`, so `guard_emit`'s scope (uids shared between the
    original and the candidate) is otherwise empty and the whole preserve/guard
    layer no-ops (blockers.md B12). The candidate inherits these same uids from
    the IR, so stamping the original makes the scope non-empty.

    See docs/agent_edit_concrete_tree.md. Match is by litegraph node id, which is
    stable across the round-trip.
    """
    by_id = {str(nid): node for nid, node in getattr(workflow, "nodes", {}).items()}
    stamped = 0
    for ui_node in graph.get("nodes") or []:
        if not isinstance(ui_node, dict):
            continue
        ir = by_id.get(str(ui_node.get("id")))
        uid = getattr(ir, "uid", "") if ir is not None else ""
        if not uid:
            continue
        props = ui_node.get("properties")
        if not isinstance(props, dict):
            props = {}
            ui_node["properties"] = props
        if not props.get("vibecomfy_uid"):
            props["vibecomfy_uid"] = uid
            stamped += 1
    return stamped


def _stale_rebaseline_recovery_issue(
    state: AgentEditState,
    gate_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "stale_state_recovery",
        "last_known_baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
        "client_structural_graph_hash": state.submitted_client_structural_graph_hash,
    }
    return {
        "code": "stale_state_mismatch",
        "severity": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "message": "Submitted graph no longer matches the current baseline.",
        "detail": dict(gate_evidence),
        "rebaseline_recovery": recovery,
    }


def _stage_ingest(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.layout_store import store_from_ui_json

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    original_ui_ref = write_json_artifact(state.original_ui_path, state.graph)
    state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
    state.prior_store = store_from_ui_json(state.graph)
    # Phase 1 (concrete-tree migration, docs/agent_edit_concrete_tree.md): give the
    # user's original graph stable identity so the delta-scope guard (guard_emit)
    # engages on the FIRST edit. Stamp a COPY — never mutate state.graph, which is
    # hashed/echoed/audited. The candidate inherits the same uids (verified: uid ==
    # node id, preserved across the scratchpad round-trip), so the guard scope
    # becomes non-empty.
    #
    # Gated OFF by default: with the guard engaged but the candidate still produced
    # by the LOSSY regeneration path (Phase 2 not yet landed), guard_emit correctly
    # refuses candidates that diverge from the original outside the intended delta.
    # Enabling identity is therefore only safe once Phase 2 (verbatim-preserve)
    # makes the candidate faithful. Toggle with VIBECOMFY_AGENT_EDIT_IDENTITY=1.
    if os.getenv("VIBECOMFY_AGENT_EDIT_IDENTITY") == "1":
        from copy import deepcopy as _deepcopy
        guard_original = _deepcopy(state.graph)
        _stamp_identity_on_original(guard_original, state.workflow)
        state.guard_original_ui = guard_original
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
    )


def _stage_ingest_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.ledger import EditLedger

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    ledger = EditLedger.ingest(state.graph)
    state.guard_original_ui = ledger.stamped_copy()
    original_ui_ref = write_json_artifact(state.original_ui_path, state.guard_original_ui)
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
        issues=tuple(issue.to_dict() for issue in ledger.diagnostics),
        value={
            "mode": "agent_edit_v2_delta",
            "node_count": len(ledger.node_index),
            "scope_count": len(ledger.scopes),
        },
    )


def _stage_convert(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.convert import port_convert_and_write, port_convert_workflow

    start = time.monotonic()
    conversion = port_convert_workflow(
        state.workflow,
        source_path=str(state.original_ui_path),
        schema_provider=state.schema_provider,
        raw_workflow=state.graph,
        # Editing a user's live canvas must preserve every node. Dead-branch
        # pruning is for authoring minimal templates; here it would silently
        # drop nodes that don't feed a recognized output (e.g. a GeminiNode
        # feeding only a PreviewAny passthrough) and corrupt the round-trip.
        prune_dead_branches=False,
    )
    # Keep the strict parity gate: with prune disabled + UI-only passthrough
    # preservation (emitter), a faithful user canvas round-trips and passes here,
    # while a genuinely-lossy conversion still fails honestly rather than applying
    # a corrupted candidate.
    port_convert_and_write(conversion, state.before_py_path)
    state.python_before = state.before_py_path.read_text(encoding="utf-8")
    return StageResult(
        stage="convert",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.before_py_path),),
    )


def _stage_project_v2(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.projection import render_edit_projection, ProjectionOptions

    start = time.monotonic()
    # The 8000-token default forces sparse mode on every real ComfyUI graph (140-200+
    # nodes), collapsing all nodes to summaries and starving the model of the field
    # names / slot types it needs to target edits and wire links correctly. Modern
    # models have 64K+ context, so render real graphs in FULL detail. Env-overridable.
    try:
        _proj_budget = int(os.getenv("VIBECOMFY_EDIT_PROJECTION_MAX_TOKENS", "256000"))
    except (TypeError, ValueError):
        _proj_budget = 256000
    projection = render_edit_projection(
        state.guard_original_ui or state.graph,
        task=state.task,
        schema_provider=state.schema_provider,
        options=ProjectionOptions(max_tokens=_proj_budget),
    )
    state.projection_text = projection.text
    state.projection_path.write_text(projection.text, encoding="utf-8")
    return StageResult(
        stage="project",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.projection_path),),
        value={
            "token_estimate": projection.token_estimate,
            "node_count": projection.node_count,
            "detailed_node_count": projection.detailed_node_count,
            "truncated": projection.truncated,
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


def _failure_response(
    state: AgentEditState,
    context: TurnContext,
    failure: FailureEnvelope,
    *,
    contract: str = "batch_repl",
) -> dict[str, Any]:
    if contract != "batch_repl":
        return _build_dev_failure_response(state, context, failure=failure)
    return _build_batch_repl_failure_response(state, context, failure=failure)


def _validated_agent_edit_response(
    response: Mapping[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    try:
        return ensure_agent_edit_response_contract(response, stage=stage)
    except Exception as exc:
        fallback = _product_failure_response(
            failure_envelope(
                FailureKind.VALIDATION_ERROR,
                stage,
                agent_failure_context={
                    "explanation": (
                        "Agent edit response contract validation failed before return: "
                        f"{exc}"
                    )
                },
            )
        )
        return ensure_agent_edit_response_contract(fallback, stage=stage)


def _product_failure_response(failure: FailureEnvelope) -> dict[str, Any]:
    response = failure.to_dict()
    response.update(product_failure_envelope_fields(failure))
    return response


def _build_compatibility_response_fields(state: AgentEditState) -> dict[str, Any]:
    candidate_graph_hash = payload_hash(state.ui_payload)
    candidate_structural_graph_hash = structural_graph_hash(state.ui_payload)
    return {
        "baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "submitted_client_graph_hash": state.submitted_client_graph_hash,
        "submitted_client_structural_graph_hash": state.submitted_client_structural_graph_hash,
        "candidate_graph_hash": candidate_graph_hash,
        "candidate_structural_graph_hash": candidate_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
    }


def _build_candidate_payload(
    state: AgentEditState,
    *,
    compatibility_fields: Mapping[str, Any],
    has_candidate: bool,
) -> dict[str, Any] | None:
    if not has_candidate:
        return None
    return {
        "state": "candidate",
        "graph": state.ui_payload,
        "graph_hash": compatibility_fields["candidate_graph_hash"],
        "structural_graph_hash": compatibility_fields["candidate_structural_graph_hash"],
        "baseline_graph_hash": compatibility_fields["baseline_graph_hash"],
        "submit_graph_hash": compatibility_fields["submit_graph_hash"],
        "submit_structural_graph_hash": compatibility_fields["submit_structural_graph_hash"],
    }


def _legacy_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: FailureEnvelope,
) -> dict[str, Any]:
    derive_gates(
        context,
        baseline_graph_hash=state.baseline_graph_hash,
        client_graph_hash=state.submit_structural_graph_hash,
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
    response = failure.to_dict()
    if failure.kind is FailureKind.STALE_STATE_MISMATCH:
        eligibility = derive_apply_eligibility(
            context,
            live_structural_graph_hash=state.baseline_graph_hash,
            submit_structural_graph_hash=state.submit_structural_graph_hash,
        )
    else:
        eligibility = derive_apply_eligibility(context, has_candidate=False)
    response.update(
        apply_eligibility_payload(
            eligibility,
            canvas_apply_allowed=context.canvas_apply_allowed,
            queue_allowed=context.queue_allowed,
        )
    )
    response.update(product_failure_envelope_fields(failure))
    failure_context = response.get("agent_failure_context")
    issues = failure_context.get("issues") if isinstance(failure_context, Mapping) else None
    if isinstance(issues, list):
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            recovery = issue.get("rebaseline_recovery")
            if isinstance(recovery, Mapping):
                response["rebaseline_recovery"] = dict(recovery)
                break
    response["internal_outcome"] = TurnOutcome.from_failure(failure).to_dict()
    return response


def _build_batch_repl_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: FailureEnvelope,
) -> dict[str, Any]:
    response = _legacy_failure_response(state, context, failure=failure)
    legacy_audit_ref = response.get("audit_ref")
    compatibility_fields = _build_compatibility_response_fields(state)
    response.update(compatibility_fields)
    response.update(product_failure_envelope_fields(failure))
    if legacy_audit_ref is not None:
        response["audit_ref"] = legacy_audit_ref
    response["eligibility"] = response["apply_eligibility"]
    response["message"] = _synthesize_batch_repl_message(state, failure=failure)
    response["debug"] = {
        **response["debug"],
        "gates": context.gate_snapshot(),
        "hashes": dict(compatibility_fields),
    }
    return response


def _build_dev_failure_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    failure: FailureEnvelope,
) -> dict[str, Any]:
    response = _legacy_failure_response(state, context, failure=failure)
    response.update(_build_compatibility_response_fields(state))
    return response


def _build_batch_repl_response(
    state: AgentEditState,
    context: TurnContext,
) -> dict[str, Any]:
    has_candidate = (
        state.batch_exit_mode in {_BATCH_EXIT_EDIT_CLARIFY, _BATCH_EXIT_DONE}
        and _batch_candidate_graph_changed(state)
    )
    compatibility_fields = _build_compatibility_response_fields(state)
    response_apply_eligibility = derive_apply_eligibility(
        context,
        has_candidate=has_candidate,
        candidate_state="candidate",
    )
    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
        apply_eligibility=response_apply_eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed if has_candidate else False,
        queue_allowed=context.queue_allowed if has_candidate else False,
    )
    candidate_payload = _build_candidate_payload(
        state,
        compatibility_fields=compatibility_fields,
        has_candidate=has_candidate,
    )
    if state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY:
        internal_outcome = TurnOutcome.clarify(question=state.user_message or None)
    elif state.batch_exit_mode == _BATCH_EXIT_EDIT_CLARIFY:
        question = state.user_message or None
        internal_outcome = TurnOutcome.edit_and_clarify(
            changes=_real_field_changes(state.batch_field_changes),
            question=question,
        )
    elif state.batch_exit_mode == _BATCH_EXIT_DONE:
        internal_outcome = TurnOutcome.edit(changes=_real_field_changes(state.batch_field_changes))
    elif state.batch_exit_mode == _BATCH_EXIT_BUDGET:
        internal_outcome = TurnOutcome.budget(reason=state.batch_final_summary or None)
    else:
        internal_outcome = TurnOutcome.noop(
            reason=state.batch_done_summary or state.user_message or None
        )
    public_outcome = public_outcome_from_turn_outcome(
        internal_outcome,
        response={"candidate": candidate_payload},
    )
    message = _synthesize_batch_repl_message(state, outcome=internal_outcome)
    change_details = _change_details_payload(state, context)
    response.update(
        turn_envelope(
            message=message,
            outcome=public_outcome,
            candidate=candidate_payload,
            eligibility=response_apply_eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
                "batch_repl": {
                    "turn_count": state.batch_turn_count,
                    "exit_mode": state.batch_exit_mode,
                    "done_summary": state.batch_done_summary,
                    "final_summary": state.batch_final_summary,
                    "budget_state": _json_safe(state.batch_budget_state),
                },
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    response["change_details"] = change_details
    response.update(compatibility_fields)
    if state.batch_exit_mode in {_BATCH_EXIT_PURE_CLARIFY, _BATCH_EXIT_EDIT_CLARIFY}:
        response["clarification_required"] = True
        response["graph_unchanged"] = state.batch_exit_mode == _BATCH_EXIT_PURE_CLARIFY
    elif state.batch_exit_mode == _BATCH_EXIT_NOOP:
        response["graph_unchanged"] = True
        if state.batch_done_summary:
            response["done_summary"] = state.batch_done_summary
    elif state.batch_done_summary:
        response["done_summary"] = state.batch_done_summary
    response["batch_turns"] = _json_safe(state.batch_turns)
    return response


def _build_dev_success_response(
    state: AgentEditState,
    context: TurnContext,
    *,
    contract: str,
) -> dict[str, Any]:
    compatibility_fields = _build_compatibility_response_fields(state)
    eligibility = derive_apply_eligibility(
        context,
        has_candidate=True,
        candidate_state="candidate",
    )
    response = success_envelope(
        context,
        message=state.user_message,
        graph=state.ui_payload,
        report=state.report,
        artifacts=state.artifacts,
        apply_eligibility=eligibility,
        canvas_apply_allowed=context.canvas_apply_allowed,
        queue_allowed=context.queue_allowed,
    )
    response.update(compatibility_fields)
    internal_outcome = TurnOutcome.edit()
    response.update(
        turn_envelope(
            message=state.user_message,
            outcome=public_outcome_from_turn_outcome(
                internal_outcome,
                response={"candidate": {"graph_hash": compatibility_fields["candidate_graph_hash"]}},
            ),
            candidate=_build_candidate_payload(
                state,
                compatibility_fields=compatibility_fields,
                has_candidate=True,
            ),
            eligibility=eligibility,
            audit_ref=None,
            debug={
                "gates": context.gate_snapshot(),
                "hashes": dict(compatibility_fields),
                "contract": contract,
            },
        )
    )
    response["internal_outcome"] = internal_outcome.to_dict()
    if contract == "delta":
        from vibecomfy.porting.edit.ops import op_to_dict

        response["delta_ops"] = [op_to_dict(op) for op in state.delta_ops]
    return response


def _run_stage(
    name: str,
    state: AgentEditState,
    context: TurnContext,
    **kwargs: Any,
) -> StageResult:
    fn = getattr(sys.modules[__name__], f"_stage_{name}")
    try:
        result = fn(state, context, **kwargs)
    except Exception as exc:
        failure_stage = (
            "agent_response"
            if name in {"agent", "agent_delta"}
            or (name in {"agent_batch", "agent_batch_repl"} and _is_provider_exception(exc))
            else name
        )
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
        if failure.kind is FailureKind.STALE_STATE_MISMATCH and name in {"ingest", "ingest_v2"}:
            failure = dataclasses.replace(
                failure,
                user_facing_message=(
                    "The canvas changed since the current backend baseline. "
                    "Rebaseline and resubmit from the current canvas."
                ),
            )
        raise _StageBlocked(result, failure)
    return result


def _is_provider_exception(exc: Exception) -> bool:
    provider_exception_names = {
        "AuthError",
        "MalformedModelJSON",
        "MissingRequiredField",
        "ProviderError",
    }
    return any(type_.__name__ in provider_exception_names for type_ in type(exc).__mro__)


def _run_batch_repl_product_path(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> AgentEditState:
    _run_stage("ingest_v2", state, context)
    _run_stage(
        "agent_batch_repl",
        state,
        context,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
        client_id=client_id,
        conversation_messages=conversation_messages,
    )
    return state


def _run_delta_dev_path(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> AgentEditState:
    _run_stage("ingest_v2", state, context)
    _run_stage("project_v2", state, context)
    _run_stage(
        "agent_delta",
        state,
        context,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
    )
    _run_stage("apply_delta", state, context)
    _run_stage("summarize_v2", state, context)
    return state


def _run_full_dev_path(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> AgentEditState:
    _run_stage("ingest", state, context)
    _run_stage("convert", state, context)
    _run_stage(
        "agent",
        state,
        context,
        deepseek_client=deepseek_client,
        route=route,
        model=model,
    )
    _run_stage("load_python", state, context)
    _run_stage("lower", state, context)
    _run_stage("validate", state, context)
    _run_stage("emit", state, context)
    _run_stage("summarize", state, context)
    return state


_RUNTIME_OBJECT_INFO_PATH: list[str] = []


def _build_object_info_in_process() -> dict[str, Any] | None:
    """Build ComfyUI /object_info IN-PROCESS from the live node registry.

    Mirrors ComfyUI server.py's ``node_info`` builder. We must NOT fetch /object_info
    over HTTP here: the agent-edit turn runs inside ComfyUI's event loop, so a blocking
    self-request deadlocks (the server can't answer while the loop is blocked) and times
    out, silently degrading to an empty schema provider. Reading the in-memory mappings
    avoids the loop entirely.
    """
    try:
        import nodes as comfy_nodes_registry  # ComfyUI global registry
    except Exception:
        return None
    mappings = getattr(comfy_nodes_registry, "NODE_CLASS_MAPPINGS", None)
    if not isinstance(mappings, dict) or not mappings:
        return None
    display = getattr(comfy_nodes_registry, "NODE_DISPLAY_NAME_MAPPINGS", {}) or {}
    out: dict[str, Any] = {}
    for name, cls in mappings.items():
        try:
            getv1 = getattr(cls, "GET_NODE_INFO_V1", None)
            if callable(getv1) and getattr(cls, "GET_NODE_INFO_V1", None) is not None:
                try:
                    out[name] = getv1()
                    continue
                except Exception:
                    pass
            info: dict[str, Any] = {}
            info["input"] = cls.INPUT_TYPES()
            rt = list(getattr(cls, "RETURN_TYPES", []) or [])
            info["output"] = rt
            info["output_name"] = list(getattr(cls, "RETURN_NAMES", rt) or rt)
            info["output_is_list"] = list(getattr(cls, "OUTPUT_IS_LIST", [False] * len(rt)) or [])
            info["name"] = name
            info["display_name"] = display.get(name, name)
            info["output_node"] = bool(getattr(cls, "OUTPUT_NODE", False))
            out[name] = info
        except Exception:
            # Some INPUT_TYPES() raise (missing models, etc.); skip those classes.
            continue
    return out or None


def _default_runtime_schema_provider() -> Any:
    """Schema provider for live edit turns: the LIVE in-process ComfyUI registry.

    The offline ``local`` provider reads an out/cache snapshot that is empty in a bare
    ComfyUI checkout, so it knows ZERO classes — which makes ``add_node`` reject every
    class as ``unknown_add_node_class_type`` (even a perfectly-installed ``PreviewImage``).
    ``RuntimeSchemaProvider`` (HTTP) can't be used here: it's either blocked inside the
    event loop, or a self-request deadlocks. So we build object_info IN-PROCESS from
    ``nodes.NODE_CLASS_MAPPINGS`` once, cache it to a temp file, and return the synchronous
    file-backed ``ObjectInfoSchemaProvider``. Falls back to ``local`` only if the registry
    is unavailable (i.e. not running inside ComfyUI).
    """
    from vibecomfy.schema import get_schema_provider

    try:
        if not (_RUNTIME_OBJECT_INFO_PATH and Path(_RUNTIME_OBJECT_INFO_PATH[0]).is_file()):
            data = _build_object_info_in_process()
            if data:
                import tempfile

                fd, path = tempfile.mkstemp(prefix="vibecomfy_object_info_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh)
                _RUNTIME_OBJECT_INFO_PATH[:] = [path]
        if _RUNTIME_OBJECT_INFO_PATH:
            from vibecomfy.schema.provider import ObjectInfoSchemaProvider

            return ObjectInfoSchemaProvider(_RUNTIME_OBJECT_INFO_PATH[0])
    except Exception:
        pass
    return get_schema_provider("local")


def handle_agent_edit(
    payload: dict[str, Any],
    *,
    schema_provider: Any = None,
    deepseek_client: DeepSeekClient | None = None,
    session_root: Path | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Convert current UI JSON to Python, ask the agent to edit it, emit UI JSON."""
    from vibecomfy.schema import get_schema_provider

    if not isinstance(payload, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")

    task = payload.get("task")
    graph = payload.get("graph")
    if not isinstance(task, str) or not task.strip():
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "`task` is required."},
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")
    if not isinstance(graph, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={
                "explanation": "`graph` must be a ComfyUI UI JSON object."
            },
        )
        return _validated_agent_edit_response(_product_failure_response(failure), stage="ingest")

    if schema_provider is None:
        schema_provider = _default_runtime_schema_provider()
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
        return _validated_agent_edit_response(allocation.replay.response, stage="replay")
    if allocation.conflict is not None:
        try:
            audit_ref = write_allocation_failure_audit(
                allocation.session_dir,
                session_id=session_id,
                failure=allocation.conflict.failure,
                request=payload,
            )
            failure = dataclasses.replace(allocation.conflict.failure, audit_ref=audit_ref)
        except Exception:
            failure = allocation.conflict.failure
        return _validated_agent_edit_response(
            _product_failure_response(failure),
            stage="allocation",
        )

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
    submit_structural_graph_hash = (
        turn_record.get("submit_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submit_structural_graph_hash"), str)
        else None
    )
    submitted_client_graph_hash = (
        turn_record.get("submitted_client_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_graph_hash"), str)
        else None
    )
    submitted_client_structural_graph_hash = (
        turn_record.get("submitted_client_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_structural_graph_hash"), str)
        else None
    )
    state = AgentEditState(
        task=task,
        graph=graph,
        request_payload=payload,
        schema_provider=schema_provider,
        baseline_graph_hash=baseline_graph_hash,
        submit_graph_hash=submit_graph_hash,
        submit_structural_graph_hash=submit_structural_graph_hash,
        submitted_client_graph_hash=submitted_client_graph_hash,
        submitted_client_structural_graph_hash=submitted_client_structural_graph_hash,
        session_dir=allocation.session_dir,
        turn_dir=turn_dir,
        request_path=turn_dir / "request.json",
        original_ui_path=turn_dir / "original.ui.json",
        before_py_path=turn_dir / "before.py",
        after_py_path=turn_dir / "after.py",
        model_request_path=turn_dir / "model_request.json",
        model_response_path=turn_dir / "model_response.json",
        candidate_ui_path=turn_dir / "candidate.ui.json",
        projection_path=turn_dir / "projection.txt",
        messages_path=turn_dir / "messages.jsonl",
    )
    if isinstance(payload.get("max_batches"), int) and payload["max_batches"] > 0:
        state.batch_max_turns = int(payload["max_batches"])
    if (
        isinstance(payload.get("max_consecutive_errors"), int)
        and payload["max_consecutive_errors"] > 0
    ):
        state.batch_max_consecutive_errors = int(payload["max_consecutive_errors"])

    contract = _agent_edit_contract()

    route = payload.get("route") if isinstance(payload.get("route"), str) else None
    model = payload.get("model") if isinstance(payload.get("model"), str) else None

    # Load session-local last-five conversation messages for prompt memory.
    # Only the batch_repl product path injects them (SD2); delta/full-dev
    # paths persist chat artifacts but do not receive prompt memory in this
    # slim v1 milestone.
    conversation_messages: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        try:
            chat = read_session_chat(root, session_id, max_messages=PROMPT_MEMORY_MESSAGES)
            if chat.get("ok") and isinstance(chat.get("messages"), list):
                conversation_messages = chat["messages"]
        except Exception:
            conversation_messages = None

    try:
        if contract == "batch_repl":
            state = _run_batch_repl_product_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=route,
                model=model,
                client_id=client_id,
                conversation_messages=conversation_messages,
            )
        elif contract == "delta":
            state = _run_delta_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=route,
                model=model,
            )
        else:
            state = _run_full_dev_path(
                state,
                context,
                deepseek_client=deepseek_client,
                route=route,
                model=model,
            )
    except _StageBlocked as blocked:
        stage_name = (
            blocked.failure.stage
            if blocked.failure is not None
            else blocked.result.stage
        )
        response = _validated_agent_edit_response(
            _failure_response(
                state,
                context,
                contract=contract,
                failure=blocked.failure
                or classify_failure(blocked.result.stage, blocked, context),
            ),
            stage=stage_name,
        )
        _write_turn_chat_artifact(state, context, response, contract)
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

    if contract == "delta":
        response = _validated_agent_edit_response(
            _build_dev_success_response(state, context, contract=contract),
            stage="submit",
        )
    elif contract == "batch_repl":
        response = _validated_agent_edit_response(
            _build_batch_repl_response(state, context),
            stage="submit",
        )
    else:
        response = _validated_agent_edit_response(
            _build_dev_success_response(state, context, contract=contract),
            stage="submit",
        )
    try:
        if contract == "delta":
            _record(
                context,
                StageResult(
                    stage="audit",
                    ok=True,
                    blocking=False,
                    value={"mode": "agent_edit_v2_delta"},
                ),
            )
        elif contract == "batch_repl":
            _record(
                context,
                StageResult(
                    stage="audit",
                    ok=True,
                    blocking=False,
                    value={"mode": state.batch_exit_mode or "batch_repl"},
                ),
            )
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
        return _validated_agent_edit_response(_product_failure_response(failure), stage="audit")
    response = _validated_agent_edit_response(response, stage="submit")
    _write_turn_chat_artifact(state, context, response, contract)
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


# ── WebSocket event helpers (best-effort, compact) ──────────────────────────


def _ws_send(event: str, payload: dict[str, Any], *, client_id: str | None = None) -> None:
    """Send a websocket event to a client, preferring send_sync, falling back to send_json.

    This is a best-effort adapter: failures are logged and swallowed so websocket issues
    never block the agent-edit control flow.
    """
    try:
        from server import PromptServer  # noqa: PLC0415
    except ImportError:
        return  # not running inside ComfyUI (tests, CLI, etc.)
    try:
        if hasattr(PromptServer.instance, "send_sync") and callable(
            PromptServer.instance.send_sync
        ):
            PromptServer.instance.send_sync(event, payload, sid=client_id)
        elif hasattr(PromptServer.instance, "send_json") and callable(
            PromptServer.instance.send_json
        ):
            PromptServer.instance.send_json(event, payload, sid=client_id)
    except Exception:
        LOGGER.debug("websocket send for event %r to client %r failed (best-effort)", event, client_id, exc_info=True)


def _brief_batch_statements(turn_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a compact, privacy-safe list of statement summaries from a batch turn record.

    Excludes: diff, raw batch/source, report text, provider metadata, and any raw JSON dumps.
    """
    if not isinstance(turn_record, dict):
        return []

    # Clarification turns have a different shape
    if turn_record.get("clarification_required"):
        return [
            {
                "clarification": True,
                "message": turn_record.get("clarification_message", ""),
            }
        ]

    statements = turn_record.get("statements")
    if not isinstance(statements, list) or not statements:
        # Fallback: build a minimal summary from turn-level fields
        return [
            {
                "ok": bool(turn_record.get("batch_ok")),
                "statement_count": int(turn_record.get("statement_count", 0)),
                "landed": int(turn_record.get("landed_op_count", 0)),
                "diagnostic_count": len(turn_record.get("diagnostics") or []),
            }
        ]

    brief: list[dict[str, Any]] = []
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        compact: dict[str, Any] = {
            "statement_index": stmt.get("statement_index"),
            "ok": stmt.get("ok"),
            "landed": stmt.get("landed"),
            "op_kind": stmt.get("op_kind"),
        }
        # Only include teaching_hint if present (it's compact guidance, not raw source)
        if stmt.get("teaching_hint"):
            compact["teaching_hint"] = stmt["teaching_hint"]
        if stmt.get("dependency_cause"):
            compact["dependency_cause"] = stmt["dependency_cause"]
        # Compact diagnostics: only code + message, no raw detail blobs
        diags = stmt.get("diagnostics")
        if isinstance(diags, list) and diags:
            compact["diagnostics"] = [
                {"code": d.get("code"), "message": d.get("message")}
                for d in diags
                if isinstance(d, dict)
            ][:5]
        # Touched uids are small identifiers, safe to include
        if stmt.get("touched_uids"):
            compact["touched_uids"] = list(stmt["touched_uids"])[:10]
        brief.append(compact)
    return brief


def _agent_edit_turn_event_payload(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    entry_type: str = "batch",
    status: str = "progress",
) -> dict[str, Any]:
    """Build a compact websocket event payload for a batch turn.

    Excludes: diff, raw batch/source text, file paths, provider metadata,
    and raw JSON blobs.  Only includes fields safe for wire transport.
    """
    payload: dict[str, Any] = {
        "session_id": context.session_id,
        "turn_id": context.turn_id,
        "turn_number": turn_record.get("turn_number"),
        "entry_type": entry_type,
        "status": status,
    }

    # Include a bounded user-facing message
    message = turn_record.get("message")
    if isinstance(message, str) and message:
        payload["message"] = message[:500] if len(message) > 500 else message

    if turn_record.get("clarification_required"):
        payload["clarification_required"] = True
        cm = turn_record.get("clarification_message")
        if isinstance(cm, str) and cm:
            payload["clarification_message"] = cm[:500] if len(cm) > 500 else cm
    else:
        payload["batch_ok"] = bool(turn_record.get("batch_ok"))
        payload["statement_count"] = int(turn_record.get("statement_count", 0))
        payload["landed_op_count"] = int(turn_record.get("landed_op_count", 0))

    # Compact statement summaries (privacy-safe)
    statements = _brief_batch_statements(turn_record)
    if statements:
        payload["statements"] = statements

    # Turn-level diagnostics (compact: code + message only)
    diags = turn_record.get("diagnostics")
    if isinstance(diags, list) and diags:
        payload["diagnostics"] = [
            {"code": d.get("code"), "message": d.get("message")}
            for d in diags
            if isinstance(d, dict)
        ][:5]

    # Exit mode info when present
    exit_mode = getattr(state, "batch_exit_mode", "")
    if exit_mode:
        payload["exit_mode"] = exit_mode
    if exit_mode in {_BATCH_EXIT_DONE, _BATCH_EXIT_NOOP} and getattr(state, "batch_done_summary", ""):
        payload["done_summary"] = str(state.batch_done_summary)[:500]

    # Budget snapshot
    budget = getattr(state, "batch_budget_state", None)
    if isinstance(budget, dict) and budget:
        payload["budget"] = {
            "remaining_batches": budget.get("remaining_batches"),
            "consecutive_errors": budget.get("consecutive_errors"),
        }

    return payload


def _emit_agent_edit_turn_event(
    state: "AgentEditState",
    context: "TurnContext",
    turn_record: dict[str, Any],
    *,
    client_id: str | None = None,
    entry_type: str = "batch",
    status: str = "progress",
) -> None:
    """Emit a compact websocket event for a batch turn.  Best-effort; never raises."""
    try:
        payload = _agent_edit_turn_event_payload(
            state, context, turn_record, entry_type=entry_type, status=status
        )
        _ws_send("vibecomfy.agent_edit.turn", payload, client_id=client_id)
    except Exception:
        LOGGER.debug("emit agent-edit turn event failed (best-effort)", exc_info=True)


__all__ = [
    "AgentEditState",
    "DeepSeekClient",
    "handle_agent_edit",
]
