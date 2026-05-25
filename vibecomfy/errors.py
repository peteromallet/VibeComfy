"""Structured exception hierarchy for VibeComfy framework.

All VibeComfyError subclasses inherit from RuntimeError so the CLI
catch tuple ``(OSError, RuntimeError, ValueError)`` in
``commands/run.py:163`` catches them.
"""

from __future__ import annotations

from typing import Any


class VibeComfyError(RuntimeError):
    """Base exception for all VibeComfy framework errors.

    Accepts an optional ``next_action`` string that callers can use to
    suggest remediation steps.  When a subclass defines
    ``default_next_action``, that value is used as the fallback when no
    explicit ``next_action`` is provided.

    Every error carries a ``severity`` (``"error"`` / ``"warning"`` /
    ``"info"``) and a ``to_dict()`` method for agent-facing structured
    consumption.
    """

    default_next_action: str | None = None

    def __init__(
        self,
        message: str,
        *,
        next_action: str | None = None,
        severity: str = "error",
    ) -> None:
        self._orig_message: str = message
        self.severity: str = severity
        self.next_action: str | None = (
            next_action if next_action is not None else self.default_next_action
        )
        super().__init__(message)

    def __str__(self) -> str:
        msg = self._orig_message
        if self.next_action is not None:
            msg = f"{msg} next action: {self.next_action}"
        return msg

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self._orig_message!r},"
            f" next_action={self.next_action!r}, severity={self.severity!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a structured dict for agent-facing consumption."""
        return {
            "type": type(self).__name__,
            "message": self._orig_message,
            "severity": self.severity,
            "next_action": self.next_action,
        }


class ModelAssetError(VibeComfyError):
    """A model asset referenced by the workflow could not be resolved."""

    default_next_action = "vibecomfy doctor --models"


class SchemaValidationError(VibeComfyError):
    """Workflow failed schema validation."""

    default_next_action = "vibecomfy port validate-call <class_type> --kwargs '<dict>'"


class QueueError(VibeComfyError):
    """Workflow queue operation failed (enqueue / wait / result)."""

    default_next_action = "vibecomfy runtime doctor"


class ContextVarBindingError(VibeComfyError):
    """Context variable binding is missing or incorrect (e.g. no active workflow)."""

    default_next_action = "vibecomfy doctor"


class ConversionParityError(VibeComfyError):
    """Emitted code is not equivalent to the source workflow."""

    default_next_action = "vibecomfy port convert <wf> --dry-run --diff"


class SubgraphFreshnessError(VibeComfyError):
    """A subgraph embedded in the workflow is stale relative to its source."""

    default_next_action = "vibecomfy port --reconvert <template>"


class RuntimeNodeError(VibeComfyError):
    """A node failed during ComfyUI runtime execution."""

    default_next_action = "vibecomfy inspect <wf> --node <id>"


class DriftError(VibeComfyError):
    """Custom-node or model pins have drifted from the lockfile."""

    default_next_action = "vibecomfy doctor --lockfile"


__all__ = [
    "ContextVarBindingError",
    "ConversionParityError",
    "DriftError",
    "ModelAssetError",
    "QueueError",
    "RuntimeNodeError",
    "SchemaValidationError",
    "SubgraphFreshnessError",
    "VibeComfyError",
]
