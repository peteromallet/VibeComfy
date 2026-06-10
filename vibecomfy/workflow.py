from __future__ import annotations

# Module-level aliases — tests access these as vibecomfy.workflow.X (SD3)
from vibecomfy import _helper_resolve as helper_resolve
from vibecomfy import _widget_aliases as widget_aliases
from vibecomfy import _workflow_helpers as workflow_helpers

# Private re-exports — tests reach in via module attribute access
from vibecomfy.ir.compile import (
    _compute_dropped_bypassed_ids,
    _get_node_mode,
    _is_intent_node_class_type,
)

# IR types
from vibecomfy.ir.types import (
    RawWidgetPayload,
    ValidationIssue,
    ValidationReport,
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    WorkflowCompileError,
    WorkflowRequirements,
    WorkflowSource,
)

# VibeWorkflow and _NodeBuilder
from vibecomfy.ir.workflow import _NodeBuilder, VibeWorkflow

# Contracts re-exports — existing importers use vibecomfy.workflow.OPAQUE_COMPONENT_CLASS_RE
from vibecomfy.contracts.validation import (  # noqa: E402
    OPAQUE_COMPONENT_CLASS_RE,
    comfyui_node_issue_specs,
)

__all__ = [
    "OPAQUE_COMPONENT_CLASS_RE",
    "RawWidgetPayload",
    "ValidationIssue",
    "ValidationReport",
    "VibeEdge",
    "VibeInput",
    "VibeNode",
    "VibeOutput",
    "VibeWorkflow",
    "WorkflowRequirements",
    "WorkflowSource",
]
