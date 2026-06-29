from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from .agent_edit.artifacts import (
    _CHAT_REASONING_MAX_DIAGS,
    _CHAT_REASONING_MAX_OPERATIONS,
    _CHAT_REASONING_MAX_STEPS,
    _compact_chat_change_details,
    _compact_diag_to_dict,
    _latest_session_candidate_payload,
    _read_turn_response_payload,
    _stamped_message_outcome,
    _stamped_turn_response_outcome,
    _trim_chat_text,
    _write_turn_chat_artifact,
)
from .agent_edit.budget import _batch_budget_failure_kind, _batch_has_landed_edits, _field_changes_payload, _json_safe
from .agent_edit.clarify import (
    TerminalClarifySplit,
    _BATCH_EXIT_BUDGET,
    _BATCH_EXIT_DONE,
    _BATCH_EXIT_EDIT_CLARIFY,
    _BATCH_EXIT_NOOP,
    _BATCH_EXIT_PURE_CLARIFY,
    _CLARIFY_FORBIDDEN_RESPONSE_KEYS,
    _build_premature_clarify_turn_record,
    _compute_premature_clarify_feedback,
    _extract_clarify_message,
    _format_clarify_markdown_message,
    _sanitize_pure_clarify_response,
    _strip_clarify_forbidden_response_fields,
    split_terminal_clarify,
)
from .agent_edit.client import DeepSeekClient
from .agent_edit.entrypoint import (
    _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS,
    _WARNED_LEGACY_CONTRACTS,
    _agent_edit_batch_repl_enabled,
    _agent_edit_contract,
    _agent_edit_v2_enabled,
    _build_graph_report,
    _build_precedent_adaptation_prompt,
    _build_precedent_semantic_check_entries,
    _canonical_agent_edit_route,
    _failure_response,
    _is_code_node_intent,
    _is_graph_explain_intent,
    _is_provider_exception,
    _is_research_intent,
    _port_issue_to_dict,
    _prefetch_research_summary,
    _read_only_discovery_turn_count,
    _record,
    _route_blocks_apply,
    _route_change_focus_label,
    _run_batch_repl_product_path_impl,
    _run_delta_dev_path_impl,
    _run_full_dev_path_impl,
    _run_stage_impl,
    _semantic_validation_description,
    _stage_audit,
    _stage_agent_batch_repl,
    _stage_summarize,
    _stage_summarize_v2,
    _structural_validation_description,
    _task_mentions_any,
    _warn_ignored_public_protocol_envs_once,
    _warn_legacy_contract_once,
    handle_agent_edit_impl,
)
from .agent_edit.fields import _field_change_is_noop, _noop_field_changes, _real_field_changes, _repair_field_changes_from_original_ui
from .agent_edit.labels import (
    _article_for,
    _change_subject,
    _display_value,
    _first_link_source_label,
    _format_available_node_names,
    _format_node_variable_index,
    _format_query_output,
    _format_statement_source,
    _is_link_endpoint,
    _iter_ui_nodes,
    _join_human_list,
    _link_endpoint_parts,
    _looks_internal_uid,
    _node_class_label,
    _node_key_values,
    _node_label_by_uid,
    _node_phrase,
    _present_class_types,
    _resolve_endpoint_label,
    _resolve_output_slot_name,
    _structural_change_phrases,
    _ui_display_widget_value_for_field,
    _ui_node_by_uid,
)
from .agent_edit.lowering import _build_lowering_audit_entries, _inject_lowering_provenance
from .agent_edit.messages import (
    _batch_candidate_graph_changed,
    _batch_research_memory_summary,
    _batch_warning_sentence,
    _change_details_payload,
    _discovery_stop_message,
    _format_batch_report,
    _format_batch_report_json,
    _format_research_brief_for_prompt,
    _human_change_phrase,
    _humanized_edit_message,
    _humanized_noop_message,
    _landed_edit_lead,
    _lint_issue_to_dict,
    _normalize_test_client_batch_response,
    _normalize_test_client_response,
    _operation_detail_payload,
    _premature_missing_custom_node_clarify_feedback,
    _premature_workflow_schema_clarify_feedback,
    _render_batch_diff,
    _revision_candidate_retry_hint,
    _revision_rejected_candidate_message,
    _sentence_case,
    _summarize_precedent_packet,
    _synthesize_batch_repl_message,
    _terminal_answer_message,
    _total_landed_edit_count,
)
from .agent_edit.paths import _artifact, _safe_session_id
from .agent_edit.runtime_schema import (
    _RUNTIME_OBJECT_INFO_PATH,
    _build_object_info_in_process,
    _can_attempt_local_additive_revise,
    _default_runtime_schema_provider,
    _effective_implementation_task,
    _empty_graph_authoring_request,
    _executor_classification_text,
    _executor_requested_implementation,
    _extract_readiness_diagnostics,
    _extract_ready_metadata,
    _focus_types_from_research_brief,
    _graph_class_types_missing_from_schema,
    _hydrate_current_graph_unknown_node_schemas,
    _localized_additive_scoped_evidence,
    _request_no_gpu_detected,
    _revision_no_candidate_reason,
    _runtime_code_additive_request,
    _runtime_execution_requested,
    _schema_provider_available,
    _seed_focus_types_for_authoring,
    _session_reference_map_for_evidence,
    _stable_blocker_key,
    _state_runtime_execution_requested,
    _subtract_existing_blockers,
)
from .agent_edit.responses import (
    _build_batch_repl_failure_response,
    _build_batch_repl_response,
    _build_candidate_payload,
    _build_compatibility_response_fields,
    _build_dev_failure_response,
    _build_dev_success_response,
    _enrich_schema_provider_from_resolver_candidates,
    _legacy_failure_response,
    _product_failure_response,
    _resolver_candidates_from_batch_result,
    _resolver_candidates_from_batch_turns,
    _session_artifact_response_fields,
    _stage_snapshot_payloads,
    _validated_agent_edit_response,
    _workflow_schema_candidates_from_batch_result,
)
from .agent_edit.session_read import (
    _BUNDLE_MAX_FILE_BYTES,
    _BUNDLE_MAX_TOTAL_BYTES,
    _BUNDLE_TEXT_SUFFIXES,
    _conversation_with_candidate_reference,
    read_session_bundle,
    read_session_chat,
    read_session_json,
)
from .agent_edit.state import AgentEditState
from .agent_edit.stages.agent_delta import _edit_lint_enabled, _stage_agent, _stage_agent_delta, _stage_apply_delta
from .agent_edit.stages.apply_summarize_audit import _stage_apply_delta_impl, _stage_audit_impl, _stage_summarize_impl, _stage_summarize_v2_impl
from .agent_edit.stages.batch_repl import _stage_agent_batch_repl_impl
from .agent_edit.stages.ingest import _stage_convert, _stage_ingest, _stage_ingest_v2, _stage_project_v2, _stale_rebaseline_recovery_issue, _stamp_identity_on_original
from .agent_edit.stages.load_lower_validate_emit import _stage_emit, _stage_load_python, _stage_lower, _stage_validate
from .agent_edit.stages.revision import (
    _finalize_revision_evidence_with_candidate,
    _revision_evidence_artifact_payload,
    _revision_evidence_prompt_json,
    _revision_readonly_message,
    _revision_target_node_ids,
    _stage_revision_evidence,
    _stage_revision_readonly_report,
    _write_revision_evidence_artifact,
)
from .agent_edit.websocket import _agent_edit_turn_event_payload, _brief_batch_statements, _emit_agent_edit_turn_event, _ws_send
from .audit import write_audit
from .contracts import StageResult, TurnContext, _ABSENT_FIELD_OLD
from .diagnostics import lower_stage_result, queue_stage_result
from .gates import apply_stage_gate_updates, derive_gates, initialize_gates, update_state_match_gate
from .provider import (
    AgentTurnResult,
    BatchTurnResult,
    MalformedModelJSON,
    MissingRequiredField,
    _latest_clarification_context,
    build_batch_messages,
    build_delta_messages,
    build_messages,
    ensure_sentence_message,
    run_agent_turn,
    run_agent_turn_batch,
    run_agent_turn_delta,
)
from .session import allocate_turn, payload_hash, read_state, record_idempotent_response, session_dir_for, structural_graph_hash, turn_dir_for
from vibecomfy.porting.edit.types import FieldChange

_SESSION_ROOT = Path("out/editor_sessions")
DEFAULT_CHAT_DISPLAY_MESSAGES = 50
PROMPT_MEMORY_MESSAGES = 5
LOGGER = logging.getLogger(__name__)

# Contract pin for tests that compare the backend websocket event name to the frontend listener:
# _ws_send("vibecomfy.agent_edit.turn", ...)


class _StageBlocked(Exception):
    def __init__(self, result: StageResult, failure=None) -> None:
        super().__init__(result.stage)
        self.result = result
        self.failure = failure


def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _run_stage(name: str, state: AgentEditState, context: TurnContext, fn, *args: Any, **kwargs: Any) -> StageResult:
    return _run_stage_impl(name, state, context, fn, *args, **kwargs)


def _run_batch_repl_product_path(state: AgentEditState, context: TurnContext, **kwargs: Any) -> AgentEditState:
    return _run_batch_repl_product_path_impl(state, context, **kwargs)


def _run_delta_dev_path(state: AgentEditState, context: TurnContext, **kwargs: Any) -> AgentEditState:
    return _run_delta_dev_path_impl(state, context, **kwargs)


def _run_full_dev_path(state: AgentEditState, context: TurnContext, **kwargs: Any) -> AgentEditState:
    return _run_full_dev_path_impl(state, context, **kwargs)


def handle_agent_edit(payload: dict[str, Any], *, schema_provider: Any = None, deepseek_client: DeepSeekClient | None = None, session_root: Path | None = None, client_id: str | None = None) -> dict[str, Any]:
    root = session_root or _SESSION_ROOT
    return handle_agent_edit_impl(
        payload,
        schema_provider=schema_provider,
        deepseek_client=deepseek_client,
        session_root=root,
        client_id=client_id,
    )


__all__ = ["AgentEditState", "DeepSeekClient", "handle_agent_edit"]
