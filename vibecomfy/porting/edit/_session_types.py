from __future__ import annotations

import ast
from copy import copy, deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.porting.edit.ops import AnchorRef, LinkSourceRef
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.porting.emitter import EmissionDiagnostic


class _ConstantFoldError(Exception):
    """Raised by _apply_binop when a constant fold operation fails irrecoverably."""

    def __init__(self, message: str, detail: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.detail: dict[str, Any] = dict(detail or {})


@dataclass(frozen=True, slots=True)
class CompactDiagnostic:
    code: str
    message: str
    severity: str = "warning"
    detail: Mapping[str, Any] = field(default_factory=dict)
    teaching_hint: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", _freeze_report(self.detail))

    @classmethod
    def from_emission(cls, diagnostic: EmissionDiagnostic) -> "CompactDiagnostic":
        return cls(
            code=diagnostic.code,
            message=diagnostic.message,
            severity=diagnostic.severity,
            detail=dict(diagnostic.detail),
        )


def _freeze_report(value: Any) -> Any:
    """Detach nested transition evidence without exposing session state."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_report(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        # A ``list`` subclass cannot be made immutable: callers can bypass any
        # overridden ``append``/``__setitem__`` with the builtin descriptor
        # (``list.append(value, item)``).  Published report sequences are real
        # tuples; the wire serializers thaw them back to JSON arrays.
        return tuple(_freeze_report(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_report(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted((_freeze_report(item) for item in value), key=repr))
    if is_dataclass(value) and not isinstance(value, type):
        # A nested diagnostic may already contain MappingProxyType; shallow
        # copy avoids asking ``deepcopy`` to pickle the immutable proxy.
        clone = copy(value)
        for item in fields(clone):
            object.__setattr__(
                clone,
                item.name,
                _freeze_report(getattr(clone, item.name)),
            )
        return clone
    try:
        return deepcopy(value)
    except Exception:
        return repr(value)


def _freeze_normalized_operation(value: Any) -> Any:
    """Detach and recursively seal one canonical normalized operation."""
    return _freeze_report(value)


def _freeze_operation_tuple(values: Any) -> tuple[Any, ...]:
    """Detach canonical operations before durable/public publication."""
    return tuple(_freeze_normalized_operation(value) for value in (values or ()))


@dataclass(frozen=True, slots=True)
class OperationTransition:
    """Compact diagnostic for one ordered lint/application occurrence."""

    occurrence: int
    submitted: Any
    normalized: Any = None
    lowered: tuple[Any, ...] = ()
    outcome: str = "rejected"  # staged / noop / rejected
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    lint_disposition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "submitted", _freeze_report(self.submitted))
        object.__setattr__(
            self,
            "normalized",
            _freeze_normalized_operation(self.normalized),
        )
        object.__setattr__(
            self,
            "lowered",
            tuple(_freeze_report(item) for item in self.lowered),
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple(_freeze_report(item) for item in self.diagnostics),
        )
        if self.lint_disposition is not None:
            object.__setattr__(self, "lint_disposition", str(self.lint_disposition))

    @property
    def statement_index(self) -> int:
        """Route-facing spelling of the immutable occurrence identity."""
        return self.occurrence

    @property
    def reason(self) -> str:
        return "no_op" if self.outcome == "noop" else self.outcome


@dataclass(frozen=True, slots=True)
class StatementResult:
    statement_index: int
    source: str
    ok: bool
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    landed: bool = False
    op_kind: str | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)
    touched_uids: tuple[str, ...] = ()
    dependency_cause: str | None = None
    teaching_hint: str | None = None
    status: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnostics",
            tuple(_freeze_report(item) for item in self.diagnostics),
        )
        object.__setattr__(self, "detail", _freeze_report(self.detail))
        object.__setattr__(
            self,
            "touched_uids",
            tuple(str(uid) for uid in self.touched_uids),
        )


@dataclass(frozen=True, slots=True)
class BatchResult:
    ok: bool
    statements: tuple[StatementResult, ...] = ()
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    landed_ops: tuple[Any, ...] = ()
    field_changes: tuple[FieldChange, ...] = ()
    apply_eligible: bool = False
    transitions: tuple[OperationTransition, ...] = ()
    lint_result: Any = None
    occurrence_to_statement_index: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.lint_result is None:
            from vibecomfy.porting.edit.lint import LintResult
            object.__setattr__(self, "lint_result", LintResult((), (), ()))
        object.__setattr__(
            self,
            "statements",
            tuple(_freeze_report(item) for item in self.statements),
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple(_freeze_report(item) for item in self.diagnostics),
        )
        object.__setattr__(self, "landed_ops", _freeze_operation_tuple(self.landed_ops))
        object.__setattr__(
            self,
            "field_changes",
            tuple(_freeze_report(item) for item in self.field_changes),
        )
        object.__setattr__(self, "lint_result", _freeze_report(self.lint_result))
        transitions = tuple(self.transitions) or tuple(
            getattr(self.lint_result, "transitions", ()) or ()
        )
        object.__setattr__(
            self,
            "transitions",
            tuple(_freeze_report(item) for item in transitions),
        )
        occurrence_map = dict(self.occurrence_to_statement_index)
        if not occurrence_map:
            occurrence_map = {
                int(transition.occurrence): int(transition.statement_index)
                for transition in transitions
            }
        object.__setattr__(
            self,
            "occurrence_to_statement_index",
            MappingProxyType({int(key): int(value) for key, value in occurrence_map.items()}),
        )

    def render_diff(self) -> str:
        """Produce a compact diff view of the batch results.

        Returns a human-readable summary suitable for agent feedback.  Each
        landed operation is described with before→after values, driven by the
        same pattern used in ``_summarize_op``.  This method is
        presentation-only — it does not mutate any state.
        """
        # Local import to avoid circular dependency with edit_session module
        from vibecomfy.porting.edit._diff import _render_op_diff

        parts: list[str] = []
        # -- Diagnostic banner -------------------------------------------------
        if not self.ok and self.diagnostics:
            parts.append(f"@@ batch failed with {len(self.diagnostics)} diagnostic(s) @@")
            for diag in self.diagnostics:
                mark = "**" if diag.severity == "error" else ""
                parts.append(f"   [{diag.severity}] {mark}{diag.code}{mark}: {diag.message}")
            parts.append("")

        # -- Statement-level lines --------------------------------------------
        for stmt in self.statements:
            tag = "  " if stmt.ok else "!!"
            source = stmt.source.replace("\n", " ")
            parts.append(f"{tag} {source}")
            if stmt.diagnostics:
                for diag in stmt.diagnostics:
                    parts.append(f"      [{diag.code}] {diag.message}")

        # -- Landed operations diff -------------------------------------------
        if self.landed_ops:
            parts.append("")
            parts.append("--- landed operations ---")
            from vibecomfy.porting.edit.ops import (
                AddNodeOp,
                RemoveLinkOp,
                RemoveNodeOp,
                SetModeOp,
                SetNodeFieldOp,
                UpsertLinkOp,
            )
            # Build a (uid, field_path) → old_value lookup from field_changes
            # so _render_op_diff can produce unified diffs for source changes.
            fc_old: dict[tuple[str, str], Any] = {}
            for fc in self.field_changes:
                fc_old[(fc.uid, fc.field_path)] = fc.old
            for i, op in enumerate(self.landed_ops):
                old_val = None
                if isinstance(op, SetNodeFieldOp):
                    old_val = fc_old.get((op.target.uid, op.target.field_path))
                desc = _render_op_diff(op, old_value=old_val)
                parts.append(f"  [{i + 1}] {desc}")

        return "\n".join(parts)


@dataclass(slots=True)
class DoneResult:
    ok: bool
    summary: str = ""
    diagnostics: tuple[CompactDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyOpsResult:
    """Result of one typed-op transaction through :class:`EditSession`."""

    ok: bool
    reason: str = ""
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    workflow: Any = None
    graph: dict[str, Any] | None = None
    landed_ops: tuple[Any, ...] = ()
    delta_id: str | None = None
    revision: int | None = None
    retryable: bool = True
    transitions: tuple[OperationTransition, ...] = ()
    lint_result: Any = None
    occurrence_to_statement_index: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Seal reports before they can expose post-state literals."""
        object.__setattr__(
            self,
            "diagnostics",
            tuple(_freeze_report(item) for item in self.diagnostics),
        )
        object.__setattr__(self, "landed_ops", _freeze_operation_tuple(self.landed_ops))
        object.__setattr__(
            self,
            "transitions",
            tuple(_freeze_report(item) for item in self.transitions),
        )
        if self.lint_result is not None:
            object.__setattr__(self, "lint_result", _freeze_report(self.lint_result))
        object.__setattr__(
            self,
            "occurrence_to_statement_index",
            MappingProxyType(
                {
                    int(key): int(value)
                    for key, value in self.occurrence_to_statement_index.items()
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class _ResolvedGraphName:
    name: str
    uid: str
    scope_path: str
    node: Any
    class_type: str


@dataclass(frozen=True, slots=True)
class _ResolvedTargetField:
    node: _ResolvedGraphName
    field_name: str
    socket_type: str | None


@dataclass(frozen=True, slots=True)
class _ResolvedOutputEndpoint:
    node: _ResolvedGraphName
    slot_name: str
    slot_index: int | None
    socket_type: str | None


@dataclass(frozen=True, slots=True)
class _ResolvedAddNodeCall:
    target_name: str
    scope_path: str
    class_type: str
    fields: Mapping[str, Any]
    inputs: Mapping[str, LinkSourceRef]
    anchor: AnchorRef | None
    uid: str | None = None
    node_id: str | None = None


@dataclass(frozen=True, slots=True)
class InputSlotInfo:
    """Describes a single input slot on a node for ``describe()`` queries."""

    name: str
    socket_type: str | None = None
    link: int | None = None
    is_virtual: bool = False
    widget_index: int | None = None


@dataclass(frozen=True, slots=True)
class OutputSlotInfo:
    """Describes a single output slot on a node for ``describe()`` queries."""

    name: str
    slot_index: int
    socket_type: str | None = None
    link_count: int = 0


@dataclass(frozen=True, slots=True)
class NodeDescriptor:
    """Structured read-only description of one graph node.

    Returned by ``EditSession.describe(name)``.  Does not count as a landed
    operation and never mutates the retained IR or the emit-side snapshot.
    """

    name: str
    uid: str
    scope_path: str
    class_type: str
    mode: int
    mode_label: str
    is_virtual: bool
    is_helper: bool
    title: str | None = None
    pos: tuple[float, float] | None = None
    size: tuple[float, float] | None = None
    widget_values: tuple[Any, ...] = ()
    fields: tuple[InputSlotInfo, ...] = ()
    outputs: tuple[OutputSlotInfo, ...] = ()

    def __str__(self) -> str:
        """Render a human-readable block describing this node.

        This is a presentation-only method; it never mutates state.
        """
        lines: list[str] = []
        # Header line
        virtual_tag = " [VIRTUAL]" if self.is_virtual else ""
        helper_tag = " [HELPER]" if self.is_helper else ""
        tags = f"{virtual_tag}{helper_tag}"
        lines.append(f"Node: {self.name} ({self.class_type}){tags}")

        # Core properties
        pos_str = f"({self.pos[0]:.1f}, {self.pos[1]:.1f})" if self.pos else "none"
        size_str = f"({self.size[0]:.1f}, {self.size[1]:.1f})" if self.size else "none"
        lines.append(
            f"  uid: {self.uid}  mode: {self.mode_label} ({self.mode})  "
            f"pos: {pos_str}  size: {size_str}"
        )

        if self.title:
            lines.append(f"  Title: {self.title!r}")

        if self.widget_values:
            lines.append(f"  Widget Values: {self.widget_values!r}")

        # Inputs
        lines.append("  Inputs:")
        if self.fields:
            for f in self.fields:
                type_str = f" [{f.socket_type}]" if f.socket_type else ""
                link_str = f"linked (link_id={f.link})" if f.link is not None else "unlinked"
                virt = " [virtual]" if f.is_virtual else ""
                lines.append(f"    {f.name}{type_str} - {link_str}{virt}")
        else:
            lines.append("    (none)")

        # Outputs
        lines.append("  Outputs:")
        if self.outputs:
            for o in self.outputs:
                type_str = f" [{o.socket_type}]" if o.socket_type else ""
                count_str = f"{o.link_count} link{'s' if o.link_count != 1 else ''}"
                lines.append(f"    {o.name} (slot {o.slot_index}){type_str} -> {count_str}")
        else:
            lines.append("    (none)")

        return "\n".join(lines)


_TEACHING_HINTS: dict[str, str] = {
    "unbound_graph_name": "The add-node statement for this name did not land. Fix the node construction call or remove the dependent statement.",
    "unknown_graph_name": "This name is not known. Render the session to refresh name bindings, or check for typos.",
    "stale_graph_name": "The uid behind this name was removed. Render the session again to refresh bindings.",
    "unknown_target_field": "Check the available field and input names. Use describe(name) to see the node's shape.",
    "unknown_output_slot": "Check the available output slot names. Use describe(name) to see available outputs.",
    "unknown_target_input": "Check the available input names. Use describe(name) to see the node's sockets.",
    "source_slot_out_of_bounds": "The source output slot is not present on the working node. Use a named output that exists.",
    "target_slot_out_of_bounds": "The target input slot is not present on the working node. Use a named input that exists.",
    "undeclared_synthetic_port": "That input is not declared on the node. Dynamic ports must match the node's contract.",
    "ghost_schema_output": "The catalog lists that output, but the working node does not have it. Link a real working output.",
    "dynamic_port_out_of_range": "That dynamic port is outside the node's declared count or payload variables.",
    "helper_direction_mismatch": "GetNode is source-only, SetNode is target-only, and PrimitiveNode is source-only.",
    "ambiguous_bare_reference": "Use an explicit slot reference like node.output_name instead of a bare node name.",
    "scope_escape_not_allowed": "Nested attribute chains are not allowed. Use a flat name or single attribute like node.slot.",
    "original_virtual_node_immutable": "Original virtual substrate nodes cannot be mutated or deleted. Route around them instead.",
    "raw_coordinate_kwarg_not_allowed": "Use near=..., relation=..., and group=... instead of raw x/y coordinates.",
    "intent_class_construction_not_allowed": "vibecomfy.* intent classes are editor-only. For executable Python use vibecomfy.exec, not vibecomfy.code.",
    "anchor_target_missing": "When using relation=, include near=... or group=... to anchor placement.",
    "cross_scope_add_node_unsupported": "All link and anchor references must be in the same scope. Use nodes from a single subgraph.",
}


def _diag(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    detail: Mapping[str, Any] | None = None,
    teaching_hint: str | None = None,
) -> CompactDiagnostic:
    hint = teaching_hint
    if hint is None:
        hint = _TEACHING_HINTS.get(code)
    return CompactDiagnostic(
        code=code,
        message=message,
        severity=severity,
        detail=dict(detail or {}),
        teaching_hint=hint,
    )


def _extract_uid_name_pairs(source: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    try:
        module = ast.parse(source)
    except SyntaxError:
        return pairs
    source_lines = source.splitlines()
    for statement in module.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name):
            continue
        end_lineno = getattr(statement, "end_lineno", statement.lineno)
        if end_lineno <= 0 or end_lineno > len(source_lines):
            continue
        line = source_lines[end_lineno - 1]
        if "# uid:" not in line:
            continue
        uid = line.split("# uid:", 1)[1].strip().split()[0]
        if uid:
            pairs.append((uid, target.id))
    return pairs


@dataclass(frozen=True, slots=True)
class _ParsedBatch:
    statements: tuple[StatementResult, ...]
    expanded: tuple["_ExpandedStatement", ...]
    diagnostics: tuple[CompactDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class _ExpandedStatement:
    statement_index: int
    source: str
    op_kind: str
    node: ast.stmt
    env: Mapping[str, Any]
