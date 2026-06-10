"""VibeComfy IR (Intermediate Representation) package.

This package holds the canonical IR data model, compile helpers, and the
VibeWorkflow class.  Module-level imports must never pull from
``vibecomfy.workflow``, ``vibecomfy.handles``, ``vibecomfy.contracts``, or
``vibecomfy.security`` — keep those inside lazy (function/method) imports.
"""

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
from vibecomfy.ir.workflow import VibeWorkflow, _NodeBuilder
from vibecomfy.ir.diagnostic import Diagnostic

__all__ = [
    "Diagnostic",
    "RawWidgetPayload",
    "ValidationIssue",
    "ValidationReport",
    "VibeEdge",
    "VibeInput",
    "VibeNode",
    "VibeOutput",
    "VibeWorkflow",
    "WorkflowCompileError",
    "WorkflowRequirements",
    "WorkflowSource",
]
