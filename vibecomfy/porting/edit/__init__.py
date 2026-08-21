"""Public API surface for the edit/ sub-package."""

from __future__ import annotations

import importlib
from typing import Any

_EXPORT_MODULES = {
    "BatchResult": "vibecomfy.porting.edit.session",
    "ApplyOpsResult": "vibecomfy.porting.edit.session",
    "CompactDiagnostic": "vibecomfy.porting.edit.session",
    "DoneResult": "vibecomfy.porting.edit.session",
    "EditSession": "vibecomfy.porting.edit.session",
    "InputSlotInfo": "vibecomfy.porting.edit.session",
    "NodeDescriptor": "vibecomfy.porting.edit.session",
    "OutputSlotInfo": "vibecomfy.porting.edit.session",
    "StatementResult": "vibecomfy.porting.edit.session",
    "AddNodeOp": "vibecomfy.porting.edit.ops",
    "AgentDeltaTurnResult": "vibecomfy.porting.edit.ops",
    "AnchorRef": "vibecomfy.porting.edit.ops",
    "EDIT_OP_RESPONSE_SCHEMA_V2": "vibecomfy.porting.edit.ops",
    "EditOp": "vibecomfy.porting.edit.ops",
    "EditOpParseError": "vibecomfy.porting.edit.ops",
    "LinkSourceRef": "vibecomfy.porting.edit.ops",
    "LinkTargetRef": "vibecomfy.porting.edit.ops",
    "NodeFieldTarget": "vibecomfy.porting.edit.ops",
    "NodeTarget": "vibecomfy.porting.edit.ops",
    "RemoveLinkOp": "vibecomfy.porting.edit.ops",
    "RemoveNodeOp": "vibecomfy.porting.edit.ops",
    "SetModeOp": "vibecomfy.porting.edit.ops",
    "SetNodeFieldOp": "vibecomfy.porting.edit.ops",
    "UpsertLinkOp": "vibecomfy.porting.edit.ops",
    "normalize_delta_agent_response": "vibecomfy.porting.edit.ops",
    "normalize_delta_test_client_response": "vibecomfy.porting.edit.ops",
    "op_to_dict": "vibecomfy.porting.edit.ops",
    "parse_edit_delta": "vibecomfy.porting.edit.ops",
    "parse_edit_op": "vibecomfy.porting.edit.ops",
    "AdmissionAllowed": "vibecomfy.porting.edit.admit",
    "AdmissionRejected": "vibecomfy.porting.edit.admit",
    "AdmissionSnapshot": "vibecomfy.porting.edit.admit",
    "TouchedScope": "vibecomfy.porting.edit.admit",
    "admit_operation": "vibecomfy.porting.edit.admit",
    "admit_operations": "vibecomfy.porting.edit.admit",
    "admission_snapshot_for": "vibecomfy.porting.edit.admit",
    "FieldChange": "vibecomfy.porting.edit.types",
    "apply_edit_cow": "vibecomfy.porting.edit._ir_utils",
    "apply_edits_cow": "vibecomfy.porting.edit._ir_utils",
    "interpret": "vibecomfy.porting.edit._interpret",
    "InterpretationResult": "vibecomfy.porting.edit._interpret",
    "StatementOutcome": "vibecomfy.porting.edit._interpret",
    "diff": "vibecomfy.porting.edit._diff",
    "EditableSurface": "vibecomfy.porting.edit.editable_surface",
    "editable_surface_for": "vibecomfy.porting.edit.editable_surface",
    "render_prompt_doc": "vibecomfy.porting.edit.grammar",
    "render_doc_table": "vibecomfy.porting.edit.grammar",
    "LintIndex": "vibecomfy.porting.edit.lint",
    "LintIssue": "vibecomfy.porting.edit.lint",
    "LintNormalization": "vibecomfy.porting.edit.lint",
    "LintResult": "vibecomfy.porting.edit.lint",
    "lint_delta": "vibecomfy.porting.edit.lint",
    "guard_exit_ui": "vibecomfy.porting.emit.ui",
    "ExitGuardResult": "vibecomfy.porting.emit.ui",
    "HELPER_NODE_TYPES": "vibecomfy.porting.edit.constants",
    "MODE_LABELS": "vibecomfy.porting.edit.constants",
    "ValueDefaultContext": "vibecomfy.porting.edit.value_defaults",
    "EDIT_TOOL_NAMES": "vibecomfy.porting.edit.typed_tools",
    "EditToolError": "vibecomfy.porting.edit.typed_tools",
    "apply_edit_tool_call": "vibecomfy.porting.edit.typed_tools",
    "lower_edit_tool_call": "vibecomfy.porting.edit.typed_tools",
    "resolve_target": "vibecomfy.porting.edit.typed_tools",
    "AcceptedDelta": "vibecomfy.porting.edit.checkpoint",
    "ClaimReferenceError": "vibecomfy.porting.edit.checkpoint",
    "ClaimReferences": "vibecomfy.porting.edit.checkpoint",
    "TerminalCheckpoint": "vibecomfy.porting.edit.checkpoint",
    "TerminalProjection": "vibecomfy.porting.edit.checkpoint",
    "accepted_delta_id": "vibecomfy.porting.edit.checkpoint",
    "close_terminal_checkpoint": "vibecomfy.porting.edit.checkpoint",
    "CheckpointLineage": "vibecomfy.porting.edit.checkpoint",
    "LineageError": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATES": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATE_APPLIED": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATE_AUTHORITY_REJECTED": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATE_CLARIFY": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATE_INFRA_FAILURE": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATE_NO_CANDIDATE": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATE_NO_OP": "vibecomfy.porting.edit.checkpoint",
    "TERMINAL_STATE_UNDETERMINED": "vibecomfy.porting.edit.checkpoint",
    "TerminalCloseError": "vibecomfy.porting.edit.checkpoint",
    "checkpoint_to_evidence": "vibecomfy.porting.edit.checkpoint",
    "coerce_lineage": "vibecomfy.porting.edit.checkpoint",
    "infer_terminal_state": "vibecomfy.porting.edit.checkpoint",
    "project_terminal_checkpoint": "vibecomfy.porting.edit.checkpoint",
    "recover_terminal_checkpoint": "vibecomfy.porting.edit.checkpoint",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
