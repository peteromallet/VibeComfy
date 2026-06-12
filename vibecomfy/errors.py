"""Structured exception hierarchy for VibeComfy framework.

All VibeComfyError subclasses inherit from RuntimeError so the CLI
catch tuple ``(OSError, RuntimeError, ValueError)`` in
``commands/run.py`` catches them.
"""

from __future__ import annotations


class VibeComfyError(RuntimeError):
    """Base exception for all VibeComfy framework errors.

    Accepts an optional ``next_action`` string that callers can use to
    suggest remediation steps.  When set, ``str(exc)`` appends
    `` next action: <value>`` to the original message.

    Provides an agent-facing diagnostic surface: ``severity`` classifies
    the error (``error`` / ``warning`` / ``info``), ``default_next_action``
    supplies a class-level remediation hint used when no explicit
    ``next_action`` is passed, and ``to_dict()`` renders a structured
    payload for programmatic / agentic consumption.
    """

    # Diagnostic surface (class-level defaults; subclasses may override).
    severity: str = "error"
    default_next_action: str | None = None

    def __init__(self, message: str, *, next_action: str | None = None) -> None:
        self.message: str = str(message)
        # Preserve legacy attribute name used by Block A code paths.
        self._orig_message: str = self.message
        # Fall back to the class-level hint when no explicit action is given.
        self.next_action: str | None = (
            next_action if next_action is not None else self.default_next_action
        )
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.next_action is None:
            return self.message
        return f"{self.message} next action: {self.next_action}"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self.message!r}, next_action={self.next_action!r})"
        )

    def to_dict(self) -> dict[str, object]:
        """Structured representation for agentic / JSON consumption."""
        return {
            "error": type(self).__name__,
            "message": self.message,
            "severity": self.severity,
            "next_action": self.next_action,
        }


# ---------------------------------------------------------------------------
# Block A error classes
# ---------------------------------------------------------------------------


class ModelAssetError(VibeComfyError):
    """A model asset referenced by the workflow could not be resolved."""


class SchemaValidationError(VibeComfyError):
    """Workflow failed schema validation."""


class QueueError(VibeComfyError):
    """Workflow queue operation failed (enqueue / wait / result)."""


class ContextVarBindingError(VibeComfyError):
    """Context variable binding is missing or incorrect (e.g. no active workflow)."""


class ConversionParityError(VibeComfyError):
    """Emitted code is not equivalent to the source workflow."""


class SubgraphFreshnessError(VibeComfyError):
    """A subgraph embedded in the workflow is stale relative to its source."""


class RuntimeNodeError(VibeComfyError):
    """A node failed during ComfyUI runtime execution."""


class DriftError(VibeComfyError):
    """Custom-node or model pins have drifted from the lockfile."""


# ---------------------------------------------------------------------------
# origin/main error classes
# ---------------------------------------------------------------------------


class WorkflowValidationError(VibeComfyError, ValueError):
    """Workflow validation failed before queue submission."""


class WorkflowBuildError(VibeComfyError, ValueError):
    """Workflow compilation or scratchpad construction failed."""


class WorkflowQueueError(VibeComfyError):
    """Prompt queue submission failed."""


class SessionBusyError(VibeComfyError):
    """A session rejected work because another operation is in flight."""


class SessionLifecycleError(VibeComfyError):
    """A session lifecycle operation failed or was refused."""


class NodePackInstallError(VibeComfyError):
    """Automatic custom-node pack installation failed."""


class RuntimeStartupError(VibeComfyError):
    """A managed runtime failed to start."""


# ---------------------------------------------------------------------------
# Agent-facing semantic subclasses
#
# These carry class-level ``default_next_action`` hints so an agent gets a
# remediation suggestion even when the raise site does not supply one.  They
# specialise the existing hierarchy (aliasing where shapes match) rather than
# introducing a parallel one.
# ---------------------------------------------------------------------------


MODEL_DOCTOR_NEXT_ACTION = "vibecomfy doctor <workflow> --models"


class MissingModelAssetError(ModelAssetError):
    """A model asset referenced by the workflow is missing and unresolved."""

    default_next_action = MODEL_DOCTOR_NEXT_ACTION


class SchemaMismatchError(SchemaValidationError):
    """A node's inputs/outputs do not match its schema."""

    default_next_action = "vibecomfy schema refresh"


class UnknownClassError(SchemaValidationError):
    """A workflow references a node class that is not known to the schema."""

    default_next_action = "vibecomfy schema refresh"


class ArityDisagreementError(SchemaValidationError):
    """Cached output arity disagrees with UI-declared output arity."""

    default_next_action = "vibecomfy schema refresh"

    def __init__(
        self,
        message: str,
        *,
        class_type: str,
        snapshot_pack: str | None,
        snapshot_version: str | None,
        snapshot_output_count: int,
        ui_output_count: int,
        next_action: str | None = None,
    ) -> None:
        self.class_type = class_type
        self.snapshot_pack = snapshot_pack
        self.snapshot_version = snapshot_version
        self.snapshot_output_count = snapshot_output_count
        self.ui_output_count = ui_output_count
        super().__init__(message, next_action=next_action)

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload.update(
            {
                "class_type": self.class_type,
                "snapshot_pack": self.snapshot_pack,
                "snapshot_version": self.snapshot_version,
                "snapshot_output_count": self.snapshot_output_count,
                "ui_output_count": self.ui_output_count,
            }
        )
        return payload


class ObjectInfoIdentityError(SchemaValidationError):
    """Identity-keyed object_info lookup could not be resolved unambiguously."""

    default_next_action = "vibecomfy schema refresh"


class ObjectInfoIdentityAmbiguityError(ObjectInfoIdentityError):
    """Multiple cached object_info entries matched one requested identity."""

    def __init__(
        self,
        message: str,
        *,
        class_type: str,
        pack_slug: str,
        git_commit: str | None,
        evidence_identity: str | None,
        matches: list[dict[str, object]],
        next_action: str | None = None,
    ) -> None:
        self.class_type = class_type
        self.pack_slug = pack_slug
        self.git_commit = git_commit
        self.evidence_identity = evidence_identity
        self.matches = matches
        super().__init__(message, next_action=next_action)

    def to_dict(self) -> dict[str, object]:
        payload = super().to_dict()
        payload.update(
            {
                "class_type": self.class_type,
                "pack_slug": self.pack_slug,
                "git_commit": self.git_commit,
                "evidence_identity": self.evidence_identity,
                "matches": self.matches,
            }
        )
        return payload


class UnknownNodeSchemaError(SchemaValidationError):
    """Code generation needs a node's output schema, but the node class is

    absent from both the object_info snapshot and the curated fallback table.

    Raised (fail-closed) instead of silently emitting structurally-broken
    Python with the wrong output arity. The message names the offending
    ``class_type`` and the snapshot version so a stale snapshot is the obvious
    remedy.
    """

    default_next_action = "vibecomfy schemas refresh"


class CanonicalParityFailure(ConversionParityError):
    """Emitted code lost parity with the canonical source workflow."""

    default_next_action = "vibecomfy port --reconvert <template>"


__all__ = [
    # base
    "VibeComfyError",
    # Block A
    "ContextVarBindingError",
    "ConversionParityError",
    "DriftError",
    "ModelAssetError",
    "QueueError",
    "RuntimeNodeError",
    "SchemaValidationError",
    "SchemaMismatchError",
    "SubgraphFreshnessError",
    "UnknownClassError",
    "ArityDisagreementError",
    "ObjectInfoIdentityAmbiguityError",
    "ObjectInfoIdentityError",
    "UnknownNodeSchemaError",
    # origin/main
    "NodePackInstallError",
    "RuntimeStartupError",
    "SessionBusyError",
    "SessionLifecycleError",
    "WorkflowBuildError",
    "WorkflowQueueError",
    "WorkflowValidationError",
]
