"""Public API surface for the edit/ sub-package."""

from __future__ import annotations

import importlib
from typing import Any

_EXPORT_MODULES = {
    "BatchResult": "vibecomfy.porting.edit.session",
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
    "FieldChange": "vibecomfy.porting.edit.types",
    "EditLedger": "vibecomfy.porting.edit.ledger",
    "ScopeState": "vibecomfy.porting.edit.ledger",
    "DEFAULT_MAX_TOKENS": "vibecomfy.porting.edit.projection",
    "ProjectionOptions": "vibecomfy.porting.edit.projection",
    "ProjectionResult": "vibecomfy.porting.edit.projection",
    "USER_STRING_FENCE": "vibecomfy.porting.edit.projection",
    "estimate_tokens": "vibecomfy.porting.edit.projection",
    "render_edit_projection": "vibecomfy.porting.edit.projection",
    "ApplyResult": "vibecomfy.porting.edit.apply",
    "ResolvedAddNodeSpec": "vibecomfy.porting.edit.apply",
    "ResolvedFieldRef": "vibecomfy.porting.edit.apply",
    "ResolvedLinkEndpoint": "vibecomfy.porting.edit.apply",
    "ResolvedNodeRef": "vibecomfy.porting.edit.apply",
    "ResolvedRemoveLinkRef": "vibecomfy.porting.edit.apply",
    "ResolveResult": "vibecomfy.porting.edit.apply",
    "apply_delta": "vibecomfy.porting.edit.apply",
    "resolve_delta": "vibecomfy.porting.edit.apply",
    "apply_edit_cow": "vibecomfy.porting.edit._ir_utils",
    "apply_edits_cow": "vibecomfy.porting.edit._ir_utils",
    "interpret": "vibecomfy.porting.edit.interpret",
    "InterpretationResult": "vibecomfy.porting.edit.interpret",
    "StatementOutcome": "vibecomfy.porting.edit.interpret",
    "EditableSurface": "vibecomfy.porting.edit.editable_surface",
    "editable_surface_for": "vibecomfy.porting.edit.editable_surface",
    "render_prompt_doc": "vibecomfy.porting.edit.grammar",
    "render_doc_table": "vibecomfy.porting.edit.grammar",
    "LintIndex": "vibecomfy.porting.edit.lint",
    "LintIssue": "vibecomfy.porting.edit.lint",
    "LintNormalization": "vibecomfy.porting.edit.lint",
    "LintResult": "vibecomfy.porting.edit.lint",
    "lint_delta": "vibecomfy.porting.edit.lint",
    "NORMALIZE_ALLOW_LIST": "vibecomfy.porting.edit.normalize",
    "is_normalize_available": "vibecomfy.porting.edit.normalize",
    "normalize_allow_list_matches": "vibecomfy.porting.edit.normalize",
    "normalize_compare": "vibecomfy.porting.edit.normalize",
    "normalize_ui_json": "vibecomfy.porting.edit.normalize",
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
