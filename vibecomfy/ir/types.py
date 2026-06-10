from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from vibecomfy.errors import VibeComfyError

from vibecomfy.ir.diagnostic import Diagnostic

# ── source_type literal ----------------------------------------------------
# Every observed value in the repo + the "unknown" default.
SourceType = Literal[
    "api",
    "fixture",
    "inline",
    "raw_json",
    "ready_template",
    "scratchpad",
    "unknown",
]


@dataclass(slots=True)
class WorkflowSource:
    id: str
    path: str | None = None
    source_type: SourceType = "unknown"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowRequirements:
    models: list[str] = field(default_factory=list)
    custom_nodes: list[str] = field(default_factory=list)
    missing_models: list[str] = field(default_factory=list)
    missing_nodes: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RawWidgetPayload:
    values: Any
    shape: str
    source: str
    has_dict_rows: bool
    length: int


@dataclass(slots=True)
class VibeNode:
    id: str
    class_type: str
    pack: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    widgets: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    uid: str = ""
    raw_widgets: RawWidgetPayload | None = None

    @property
    def provenance(self) -> str:
        """Read-through to the S4 provenance tag; fail-closed on missing/None."""
        from vibecomfy.security import provenance as _prov

        return _prov.read(self)


@dataclass(slots=True)
class VibeEdge:
    from_node: str
    from_output: str
    to_node: str
    to_input: str


@dataclass(slots=True)
class VibeInput:
    name: str
    node_id: str
    field: str
    value: Any = None
    type: str | None = None
    default: Any = None
    required: bool = False
    range: Any = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    media_semantics: str | None = None


@dataclass(slots=True)
class VibeOutput:
    node_id: str
    output_type: str
    name: str | None = None
    artifact_kind: str | None = None
    mime_type: str | None = None
    filename_prefix: str | None = None
    expected_cardinality: str | int | None = None


@dataclass(slots=True)
class ValidationIssue(Diagnostic):
    """Per-field or structural issue discovered during IR validation.

    Inherits ``code``, ``message``, ``severity``, and ``detail`` from
    :class:`Diagnostic`; adds no further fields.

    All parent fields are redeclared here because :class:`Diagnostic` is a
    plain class (not a dataclass), so the dataclass machinery does not
    automatically incorporate them into the generated ``__init__``.
    """

    code: str = field(default="")
    message: str = field(default="")
    severity: str = "error"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)


class WorkflowCompileError(VibeComfyError):
    """Compile-time graph assembly failure with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        next_action: str | None = None,
    ) -> None:
        self.code = code
        self.detail = detail or {}
        super().__init__(f"{code}: {message}", next_action=next_action)
