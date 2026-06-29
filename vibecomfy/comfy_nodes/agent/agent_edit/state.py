from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibecomfy.executor.contracts import RevisionEvidence
from vibecomfy.porting.edit.types import FieldChange

if TYPE_CHECKING:
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.workflow import VibeWorkflow


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
    revision_evidence_path: Path = Path("revision_evidence.json")
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
    revision_evidence: RevisionEvidence | None = None
    revision_evidence_payload: dict[str, Any] | None = None
    ui_payload: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    artifacts: dict[str, str] | None = None
    projection_text: str = ""
    delta_ops: tuple[Any, ...] = ()
    delta_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    delta_audit: dict[str, Any] | None = None
    guard_result: dict[str, Any] | None = None
    batch_session: EditSession | None = None
    batch_signature_catalog: str = ""
    executor_research_summary: str = ""
    executor_research_warnings: tuple[str, ...] = ()
    executor_research_sources: tuple[dict[str, Any], ...] = ()
    executor_precedent_slices: tuple[dict[str, Any], ...] = ()
    executor_adaptation_plan: dict[str, Any] | None = None
    executor_research_brief: dict[str, Any] | None = None
    execution_protocol_notes: dict[str, Any] | None = None
    research_context_packet: dict[str, Any] | None = None
    graph_facts: dict[str, Any] | None = None
    batch_turns: list[dict[str, Any]] = field(default_factory=list)
    batch_field_changes: tuple[FieldChange, ...] = ()
    batch_noop_field_changes: tuple[FieldChange, ...] = ()
    batch_budget_state: dict[str, Any] = field(default_factory=dict)
    batch_turn_count: int = 0
    batch_max_turns: int = 50
    batch_max_consecutive_errors: int = 3
    batch_feedback: str = ""
    batch_final_summary: str = ""
    batch_exit_mode: str = ""
    batch_done_summary: str = ""
    lint_noop_messages: tuple[str, ...] = ()
    provisional_registry_candidate_hashes: frozenset[str] = frozenset()
    route: str | None = None
