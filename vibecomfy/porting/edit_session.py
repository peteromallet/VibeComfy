from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from time import perf_counter
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.edit_apply import apply_delta
from vibecomfy.porting.edit_ledger import EditLedger
from vibecomfy.porting.edit_ops import (
    AddNodeOp,
    AnchorRef,
    EditOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.emitter import EmissionDiagnostic, emit_agent_edit_python
from vibecomfy.porting.edit_projection import HELPER_NODE_TYPES, MODE_LABELS
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    InferredAnchorHint,
    build_batch_placement_facts,
    infer_add_node_anchor_hint,
)
from vibecomfy.porting.slot_codec import to_raw_name
from vibecomfy.schema import get_schema_provider, schema_for, socket_types_compatible

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


_FORBIDDEN_CALL_NAMES = frozenset(
    {
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
        "open",
    }
)
_RAW_COORDINATE_HINT_NAMES = frozenset({"pos", "position", "coords", "x", "y"})
_SAFE_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
_SAFE_UNARYOPS = (ast.UAdd, ast.USub)
_MODE_LABEL_TO_VALUE = {str(label): mode for mode, label in MODE_LABELS.items()}


@dataclass(frozen=True, slots=True)
class CompactDiagnostic:
    code: str
    message: str
    severity: str = "warning"
    detail: dict[str, Any] = field(default_factory=dict)
    teaching_hint: str | None = None

    @classmethod
    def from_emission(cls, diagnostic: EmissionDiagnostic) -> "CompactDiagnostic":
        return cls(
            code=diagnostic.code,
            message=diagnostic.message,
            severity=diagnostic.severity,
            detail=dict(diagnostic.detail),
        )


@dataclass(slots=True)
class StatementResult:
    statement_index: int
    source: str
    ok: bool
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    landed: bool = False
    op_kind: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    touched_uids: tuple[str, ...] = ()
    dependency_cause: str | None = None
    teaching_hint: str | None = None


@dataclass(slots=True)
class BatchResult:
    ok: bool
    statements: tuple[StatementResult, ...] = ()
    diagnostics: tuple[CompactDiagnostic, ...] = ()
    landed_ops: tuple[Any, ...] = ()


@dataclass(slots=True)
class DoneResult:
    ok: bool
    summary: str = ""
    diagnostics: tuple[CompactDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class _ResolvedGraphName:
    name: str
    uid: str
    scope_path: str
    node: Mapping[str, Any]
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
    operation and never mutates ``working_ui``.
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


_TEACHING_HINTS: dict[str, str] = {
    "unbound_graph_name": "The add-node statement for this name did not land. Fix the node construction call or remove the dependent statement.",
    "unknown_graph_name": "This name is not known. Render the session to refresh name bindings, or check for typos.",
    "stale_graph_name": "The uid behind this name was removed. Render the session again to refresh bindings.",
    "unknown_target_field": "Check the available field and input names. Use describe(name) to see the node's shape.",
    "unknown_output_slot": "Check the available output slot names. Use describe(name) to see available outputs.",
    "ambiguous_bare_reference": "Use an explicit slot reference like node.output_name instead of a bare node name.",
    "scope_escape_not_allowed": "Nested attribute chains are not allowed. Use a flat name or single attribute like node.slot.",
    "original_virtual_node_immutable": "Original virtual substrate nodes cannot be mutated or deleted. Route around them instead.",
    "raw_coordinate_kwarg_not_allowed": "Use near=..., relation=..., and group=... instead of raw x/y coordinates.",
    "intent_class_construction_not_allowed": "vibecomfy.* intent classes are editor-only. Use a concrete node class type instead.",
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


class EditSession:
    """State shell for the offline Python edit surface.

    T8 only establishes the render/state contract. Parsing batches, resolving
    statements, and the final proof gates land in later tasks.
    """

    def __init__(
        self,
        raw_ui_json: Mapping[str, Any],
        *,
        schema_provider: Any | None = None,
        caps: frozenset[str] | set[str] | tuple[str, ...] = (),
        render_budget_ms: float | None = None,
        max_batch_bytes: int = 20_000,
        max_statements: int = 100,
        max_expanded_statements: int = 500,
        max_for_iterations: int = 100,
    ) -> None:
        self.original_ui: dict[str, Any] = deepcopy(dict(raw_ui_json))
        self.working_ui: dict[str, Any] = deepcopy(dict(raw_ui_json))
        self.original_ledger = EditLedger.ingest(self.original_ui)
        self.ledger = EditLedger.ingest(self.working_ui)
        self.landed_ops: list[Any] = []
        self.touched_uids: set[str] = set()
        self.touched_node_ids: set[str] = set()
        self.schema_provider = schema_provider or get_schema_provider("auto")
        self.caps: frozenset[str] = frozenset(str(cap) for cap in caps)
        self.render_budget_ms = render_budget_ms
        self.max_batch_bytes = max_batch_bytes
        self.max_statements = max_statements
        self.max_expanded_statements = max_expanded_statements
        self.max_for_iterations = max_for_iterations
        self.name_by_uid: dict[str, str] = {}
        self.uid_by_name: dict[str, str] = {}
        self.unbound_names: set[str] = set()
        self.render_count = 0
        self.last_rendered_source: str | None = None
        self.last_rendered_workflow: VibeWorkflow | None = None
        self.last_render_diagnostics: tuple[CompactDiagnostic, ...] = ()

    def render(self) -> str:
        self.ledger = EditLedger.ingest(self.working_ui)
        workflow = self._workflow_from_ui(self.working_ui)
        emission_diagnostics: list[EmissionDiagnostic] = []
        started = perf_counter()
        source = emit_agent_edit_python(
            workflow,
            diagnostics=emission_diagnostics,
            raw_workflow=self.working_ui,
            variable_name_locks=self.name_by_uid or None,
            strict_variable_name_locks=bool(self.name_by_uid),
        )
        elapsed_ms = (perf_counter() - started) * 1000.0
        parsed_names = _extract_uid_name_pairs(source)
        lock_diagnostics = self._seed_or_validate_name_locks(parsed_names)
        all_diagnostics = [CompactDiagnostic.from_emission(item) for item in emission_diagnostics]
        all_diagnostics.extend(lock_diagnostics)
        if self.render_budget_ms is not None and elapsed_ms > self.render_budget_ms:
            all_diagnostics.append(
                _diag(
                    "render_budget_exceeded",
                    (
                        f"EditSession.render exceeded the configured render budget "
                        f"({elapsed_ms:.1f}ms > {self.render_budget_ms:.1f}ms)."
                    ),
                    severity="warning",
                    detail={"elapsed_ms": elapsed_ms, "budget_ms": self.render_budget_ms},
                )
            )
        self.render_count += 1
        self.last_rendered_source = source
        self.last_rendered_workflow = workflow
        self.last_render_diagnostics = tuple(all_diagnostics)
        return source

    def apply_batch(self, code: str) -> BatchResult:
        parsed = _parse_and_validate_batch(
            code,
            max_batch_bytes=self.max_batch_bytes,
            max_statements=self.max_statements,
            max_expanded_statements=self.max_expanded_statements,
            max_for_iterations=self.max_for_iterations,
        )
        if parsed.diagnostics:
            return BatchResult(
                ok=False,
                statements=parsed.statements,
                diagnostics=parsed.diagnostics,
            )
        placement_facts = build_batch_placement_facts(
            parsed.expanded,
            graph_name_exists=self._graph_name_exists,
            estimate_add_node_width=self._estimate_add_node_width,
        )
        statement_results, landed_ops, diagnostics = self._execute_statements(
            parsed.expanded,
            placement_facts=placement_facts,
        )
        return BatchResult(
            ok=not diagnostics and all(statement.ok for statement in statement_results),
            statements=statement_results,
            diagnostics=diagnostics,
            landed_ops=landed_ops,
        )

    def done(self) -> DoneResult:
        """Finalize the session: run Gate A and Gate B proof checks.

        Gate A replays all landed ops over ``original_ui`` through the
        deterministic ``apply_delta`` path (which internally resolves,
        applies, and calls ``guard_full_ui``).  It then asserts the
        recomputed candidate is deep-equal to the current ``working_ui``.

        Gate B compiles the current working UI and recomputed candidate
        through the normal UI -> ``VibeWorkflow`` -> ``compile("api")`` oracle,
        narrows both API graphs to the touched region induced by landed ops,
        and compares them with ``parity.compile_equivalent``.

        If zero ops have landed, it verifies that ``working_ui`` is still
        identical to ``original_ui``.
        """
        ops = tuple(self.landed_ops)

        if not ops:
            if self.working_ui != self.original_ui:
                return DoneResult(
                    ok=False,
                    summary=(
                        "Gate A failed: working_ui differs from original_ui "
                        "even though zero ops were landed."
                    ),
                    diagnostics=(
                        _diag(
                            "done_gate_a_mismatch",
                            (
                                "Zero ops landed but working_ui != original_ui. "
                                "This means something mutated working_ui outside "
                                "the edit-op path."
                            ),
                            severity="error",
                        ),
                    ),
                )
            gate_b = self._done_gate_b(self.working_ui, self.working_ui, ops)
            if not gate_b.ok:
                return gate_b
            gate_c_summary = self._done_gate_c(ops)
            return DoneResult(
                ok=True,
                summary=(
                    "No edits applied — identity verified; Gate B passed. "
                    f"Summary: {gate_c_summary}"
                ),
            )

        applied = apply_delta(
            self.original_ui,
            ops,
            schema_provider=self.schema_provider,
        )

        if not applied.ok or applied.candidate is None:
            issue_diagnostics = tuple(
                self._compact_port_issue(issue) for issue in applied.diagnostics
            )
            guard_issues: tuple[CompactDiagnostic, ...] = ()
            if applied.guard_result is not None and applied.guard_result.diagnostics:
                guard_issues = tuple(
                    self._compact_port_issue(issue)
                    for issue in applied.guard_result.diagnostics
                )
            all_diags = issue_diagnostics + guard_issues
            return DoneResult(
                ok=False,
                summary=(
                    f"Gate A: apply_delta over original_ui failed "
                    f"({len(all_diags)} diagnostic(s))."
                ),
                diagnostics=all_diags,
            )

        candidate = applied.candidate
        if candidate != self.working_ui:
            return DoneResult(
                ok=False,
                summary=(
                    "Gate A: recomputed candidate does not match working_ui. "
                    "The landed ops do not deterministically reproduce "
                    "the current state from the original."
                ),
                diagnostics=(
                    _diag(
                        "done_gate_a_mismatch",
                        (
                            "Recomputing all landed ops over original_ui "
                            "produced a candidate that differs from working_ui. "
                            "Ops may have been applied out of order or "
                            "working_ui may have been mutated externally."
                        ),
                        severity="error",
                    ),
                ),
            )

        gate_b = self._done_gate_b(self.working_ui, candidate, ops)
        if not gate_b.ok:
            return gate_b

        gate_c_summary = self._done_gate_c(ops)
        return DoneResult(
            ok=True,
            summary=(
                f"Gate A passed: {len(ops)} edit operation(s) verified. "
                f"Gate B passed: touched compile region is isomorphic. "
                f"Summary: {gate_c_summary}"
            ),
        )

    # ------------------------------------------------------------------
    # Read-only queries (side-effect-free, never land ops)
    # ------------------------------------------------------------------

    def describe(self, name: str) -> NodeDescriptor:
        """Return a structured read-only description of the graph node named *name*.

        This method is side-effect-free: it does not mutate ``working_ui`` and
        does not record a landed operation.  It resolves *name* through the
        current ``uid_by_name`` / ``name_by_uid`` locks and the ledger.

        Returns a :class:`NodeDescriptor` with fields, inputs, outputs, socket
        types, mode, uid, placement, and virtual/helper status.
        """
        node_ref, issues = self._resolve_graph_name(name)
        if issues:
            raise LookupError(issues[0].message)
        assert node_ref is not None
        node = node_ref.node
        node_id = node.get("id")
        node_mode = node.get("mode", 0)
        mode_label = MODE_LABELS.get(node_mode, f"mode={node_mode}")
        class_type = node_ref.class_type
        is_helper = class_type in HELPER_NODE_TYPES

        # Virtual nodes are helpers that appear in the *original* ledger
        original_helper = False
        original_node = self.original_ledger.resolve_node(node_ref.scope_path, node_ref.uid)
        if original_node is not None:
            oc = str(original_node.get("type") or original_node.get("class_type") or "")
            original_helper = oc in HELPER_NODE_TYPES

        pos_raw = node.get("pos")
        pos: tuple[float, float] | None = None
        if isinstance(pos_raw, (list, tuple)) and len(pos_raw) == 2:
            try:
                pos = (float(pos_raw[0]), float(pos_raw[1]))
            except (TypeError, ValueError):
                pos = None

        size_raw = node.get("size")
        size: tuple[float, float] | None = None
        if isinstance(size_raw, (list, tuple)) and len(size_raw) == 2:
            try:
                size = (float(size_raw[0]), float(size_raw[1]))
            except (TypeError, ValueError):
                size = None

        title = node.get("title")
        if isinstance(title, str) and title:
            pass
        else:
            title = None

        widget_values_raw = node.get("widgets_values")
        if isinstance(widget_values_raw, list):
            widget_values = tuple(widget_values_raw)
        else:
            widget_values = ()

        # Build input slot info
        inputs_raw = node.get("inputs") or []
        fields: list[InputSlotInfo] = []
        schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        outgoing_links = self._outgoing_link_map(node_id)

        for idx, slot in enumerate(inputs_raw if isinstance(inputs_raw, list) else []):
            if not isinstance(slot, Mapping):
                continue
            slot_name = str(slot.get("name") or f"input_{idx}")
            slot_type = _normalize_type(slot.get("type"))
            slot_link = slot.get("link")
            if isinstance(slot_link, (int, float)):
                slot_link = int(slot_link)
            else:
                slot_link = None
            # Determine widget_index: link to widget_values by position
            widget_idx = None
            if slot_name in schema_inputs:
                widget_idx = getattr(schema_inputs[slot_name], "widget", None)
                if widget_idx is not None:
                    try:
                        widget_idx = int(widget_idx)
                    except (TypeError, ValueError):
                        widget_idx = None
            fields.append(
                InputSlotInfo(
                    name=slot_name,
                    socket_type=slot_type,
                    link=slot_link,
                    is_virtual=slot.get("virtual", False) is True,
                    widget_index=widget_idx,
                )
            )

        # Build output slot info
        output_specs = _output_specs(node, self.schema_provider, class_type)
        outputs: list[OutputSlotInfo] = []
        for spec in output_specs:
            out_name = spec["name"]
            out_index = spec["index"]
            out_type = spec["type"]
            link_count = len(outgoing_links.get(out_index, []))
            outputs.append(
                OutputSlotInfo(
                    name=out_name,
                    slot_index=out_index,
                    socket_type=out_type,
                    link_count=link_count,
                )
            )

        return NodeDescriptor(
            name=node_ref.name,
            uid=node_ref.uid,
            scope_path=node_ref.scope_path,
            class_type=class_type,
            mode=node_mode,
            mode_label=mode_label,
            is_virtual=is_helper or original_helper,
            is_helper=is_helper,
            title=title,
            pos=pos,
            size=size,
            widget_values=widget_values,
            fields=tuple(fields),
            outputs=tuple(outputs),
        )

    def search(
        self,
        *,
        focus_types: list[str] | None = None,
        compatible_input_type: str | None = None,
        compatible_output_type: str | None = None,
        formatted: bool = False,
    ) -> list[NodeSignatureRow] | str:
        """Query available node signatures from the session's schema provider.

        This method is side-effect-free: it does not mutate ``working_ui`` and
        does not record a landed operation.

        Delegates to :func:`emit_available_node_signatures` with the
        session's ``schema_provider``.  When *formatted* is ``True``, returns a
        deterministic text catalog via :func:`format_signature_rows`.

        Parameters
        ----------
        focus_types:
            Optional list of class-type strings for per-node lookups.
            When ``None``, enumerates every known schema.
        compatible_input_type:
            Filter to rows that have at least one output compatible with this type.
        compatible_output_type:
            Filter to rows that have at least one input compatible with this type.
        formatted:
            When ``True``, return a formatted text string instead of a list of rows.
        """
        from vibecomfy.porting.emitter import emit_available_node_signatures, format_signature_rows as fmt_rows

        rows = emit_available_node_signatures(
            self.schema_provider,
            focus_types=focus_types,
            compatible_input_type=compatible_input_type,
            compatible_output_type=compatible_output_type,
        )
        if formatted:
            return fmt_rows(rows)
        return rows

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _outgoing_link_map(self, node_id: Any) -> dict[int, list[int]]:
        """Build a map from output slot index to list of link ids."""
        result: dict[int, list[int]] = {}
        if node_id is None:
            return result
        links = self.working_ui.get("links") or []
        if not isinstance(links, list):
            return result
        for link in links:
            if not isinstance(link, Mapping):
                continue
            origin_id = link.get("origin_id")
            origin_slot = link.get("origin_slot")
            link_id = link.get("id")
            if origin_id == node_id and isinstance(link_id, (int, float)):
                slot = 0
                if isinstance(origin_slot, (int, float)):
                    slot = int(origin_slot)
                result.setdefault(slot, []).append(int(link_id))
        return result

    def _workflow_from_ui(self, ui_json: Mapping[str, Any]) -> VibeWorkflow:
        from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api

        api = normalize_to_api(
            deepcopy(dict(ui_json)),
            schema_provider=self.schema_provider,
            use_comfy_converter=False,
        )
        workflow = convert_to_vibe_format(
            api,
            schema_provider=self.schema_provider,
        )
        workflow.finalize_metadata()
        return workflow

    def _done_gate_b(
        self,
        working_ui: Mapping[str, Any],
        candidate_ui: Mapping[str, Any],
        ops: tuple[EditOp, ...],
    ) -> DoneResult:
        compiled_original = self._compile_ui_for_done_gate_b(self.original_ui, label="original")
        if isinstance(compiled_original, DoneResult):
            return compiled_original
        original_workflow, original_api = compiled_original

        compiled_working = self._compile_ui_for_done_gate_b(working_ui, label="working")
        if isinstance(compiled_working, DoneResult):
            return compiled_working
        working_workflow, working_api = compiled_working

        compiled_candidate = self._compile_ui_for_done_gate_b(candidate_ui, label="candidate")
        if isinstance(compiled_candidate, DoneResult):
            return compiled_candidate
        candidate_workflow, candidate_api = compiled_candidate

        region_ids = self._done_gate_b_region_node_ids(
            ops=ops,
            original_workflow=original_workflow,
            original_api=original_api,
            working_workflow=working_workflow,
            working_api=working_api,
            candidate_workflow=candidate_workflow,
            candidate_api=candidate_api,
        )
        working_region = _subset_api_by_node_ids(working_api, region_ids)
        candidate_region = _subset_api_by_node_ids(candidate_api, region_ids)

        from vibecomfy.porting import parity

        ok, diffs = parity.compile_equivalent(working_region, candidate_region)
        if ok:
            return DoneResult(ok=True, summary="Gate B passed.")
        return DoneResult(
            ok=False,
            summary=(
                "Gate B failed: current working UI and replayed candidate are "
                "not compile-equivalent over the touched region."
            ),
            diagnostics=(
                _diag(
                    "done_gate_b_compile_isomorphism_failed",
                    "Touched-region compile equivalence failed.",
                    severity="error",
                    detail={
                        "region_node_ids": tuple(sorted(region_ids, key=_node_id_sort_key)),
                        "working_region_node_ids": tuple(sorted(working_region, key=_node_id_sort_key)),
                        "candidate_region_node_ids": tuple(sorted(candidate_region, key=_node_id_sort_key)),
                        "diffs": tuple(diffs),
                    },
                ),
            ),
        )

    def _done_gate_c(self, ops: tuple[EditOp, ...]) -> str:
        """Gate C: generate a plain-language summary from landed ops and ledger state.

        Covers: added/removed nodes, field changes, rewired edges, mode changes,
        socket types, and adjacent same-type inputs.
        """
        if not ops:
            return "No operations were applied."

        parts: list[str] = []
        op_kinds: dict[str, int] = {}
        for op in ops:
            kind = type(op).__name__
            op_kinds[kind] = op_kinds.get(kind, 0) + 1

        for op in ops:
            sentence = self._summarize_op(op)
            if sentence:
                parts.append(sentence)

        if not parts:
            return (
                f"{len(ops)} operation(s) applied: "
                + ", ".join(f"{count} {kind}" for kind, count in op_kinds.items())
                + "."
            )

        return " ".join(parts)

    def _summarize_op(self, op: EditOp) -> str:
        """Generate a single-sentence summary for one edit operation."""
        if isinstance(op, SetNodeFieldOp):
            return self._summarize_set_node_field(op)
        if isinstance(op, AddNodeOp):
            return self._summarize_add_node(op)
        if isinstance(op, RemoveNodeOp):
            return self._summarize_remove_node(op)
        if isinstance(op, UpsertLinkOp):
            return self._summarize_upsert_link(op)
        if isinstance(op, RemoveLinkOp):
            return self._summarize_remove_link(op)
        if isinstance(op, SetModeOp):
            return self._summarize_set_mode(op)
        if isinstance(op, ReorderOp):
            return self._summarize_reorder(op)
        return ""

    def _summarize_set_node_field(self, op: SetNodeFieldOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        field = op.target.field_path
        old_value = self._original_node_field_value(op.target.scope_path, op.target.uid, field)
        new_value = op.value
        if old_value is not None:
            return f"Changed {name}.{field} from {old_value!r} to {new_value!r}."
        return f"Set {name}.{field} = {new_value!r}."

    def _summarize_add_node(self, op: AddNodeOp) -> str:
        name = self.name_by_uid.get(
            self._uid_for_scope(op.scope_path, op.class_type), op.class_type
        )
        detail_parts: list[str] = []
        if op.inputs:
            input_parts: list[str] = []
            for field_name, source_ref in op.inputs.items():
                src_name = self._node_display_name(source_ref.scope_path, source_ref.uid)
                socket_type = self._output_socket_type(source_ref.scope_path, source_ref.uid, source_ref.output_slot)
                slot_str = source_ref.output_slot
                if isinstance(slot_str, int):
                    slot_str = str(slot_str)
                type_hint = f" ({socket_type})" if socket_type else ""
                input_parts.append(f"{src_name}.{slot_str}{type_hint}")
                # Check for adjacent same-type inputs
                adj = self._adjacent_same_type_inputs(
                    op.scope_path if op.scope_path else "", field_name
                )
                if adj:
                    input_parts[-1] += f" (adjacent same-type: {adj})"
            detail_parts.append("with inputs: " + ", ".join(input_parts))
        if op.fields:
            field_parts = [f"{k}={v!r}" for k, v in op.fields.items()]
            detail_parts.append("with fields: " + ", ".join(field_parts))
        detail = "; ".join(detail_parts)
        if detail:
            return f"Added {op.class_type} node '{name}' {detail}."
        return f"Added {op.class_type} node '{name}'."

    def _summarize_remove_node(self, op: RemoveNodeOp) -> str:
        name = self.name_by_uid.get(op.target.uid, op.target.uid)
        class_type = self._original_node_class_type(op.target.scope_path, op.target.uid)
        ct_str = f"{class_type} " if class_type else ""
        return f"Removed {ct_str}node '{name}'."

    def _summarize_upsert_link(self, op: UpsertLinkOp) -> str:
        src_name = self._node_display_name(op.source.scope_path, op.source.uid)
        dst_name = self._node_display_name(op.target.scope_path, op.target.uid)
        src_slot = op.source.output_slot
        if isinstance(src_slot, int):
            src_slot = str(src_slot)
        dst_field = op.target.input_field
        socket_type = self._output_socket_type(op.source.scope_path, op.source.uid, op.source.output_slot)
        type_hint = f" ({socket_type})" if socket_type else ""

        # Check original ledger for a pre-existing link to determine new vs rewire
        prev_link = self._find_link_to_target_in_ledger(
            self.original_ledger, op.target.scope_path, op.target.uid, op.target.input_field
        )
        if prev_link is not None:
            # Rewire case: original ledger had a link
            pass
        else:
            # No original link — this is a new connection
            prev_link = None
        if prev_link is not None:
            prev_src_uid, prev_src_slot = prev_link
            prev_name = self._node_display_name(op.target.scope_path, prev_src_uid)
            prev_slot_str = str(prev_src_slot) if isinstance(prev_src_slot, int) else prev_src_slot
            return (
                f"Rewired {dst_name}.{dst_field}{type_hint} "
                f"from {prev_name}.{prev_slot_str} → {src_name}.{src_slot}."
            )
        return (
            f"Connected {src_name}.{src_slot}{type_hint} → "
            f"{dst_name}.{dst_field}."
        )

    def _summarize_remove_link(self, op: RemoveLinkOp) -> str:
        if op.target is None:
            return f"Removed link id={op.link_id}."
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        field = op.target.input_field
        prev_link = self._find_link_to_target(op.target.scope_path, op.target.uid, op.target.input_field)
        if prev_link is not None:
            prev_src_uid, prev_src_slot = prev_link
            prev_name = self._node_display_name(op.target.scope_path, prev_src_uid)
            return f"Disconnected {name}.{field} from {prev_name}.{prev_src_slot}."
        return f"Disconnected {name}.{field}."

    def _summarize_set_mode(self, op: SetModeOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        old_mode = self._original_node_mode(op.target.scope_path, op.target.uid)
        old_label = MODE_LABELS.get(old_mode, f"mode={old_mode}")
        new_label = MODE_LABELS.get(op.mode, f"mode={op.mode}")
        return f"Changed {name} mode from {old_label} to {new_label}."

    def _summarize_reorder(self, op: ReorderOp) -> str:
        name = self._node_display_name(op.target.scope_path, op.target.uid)
        return f"Reordered {name} {op.axis}."

    # -- Gate C helpers --

    def _node_display_name(self, scope_path: str, uid: str) -> str:
        """Return the human-facing name for a node, preferring locked names."""
        return self.name_by_uid.get(uid, uid)

    def _node_class_type(self, scope_path: str, uid: str) -> str | None:
        """Look up the class_type of a node by uid from the working ledger."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return str(node.get("type") or node.get("class_type") or "")
        return None

    def _original_node_class_type(self, scope_path: str, uid: str) -> str | None:
        """Look up the class_type of a node from the original ledger."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return str(node.get("type") or node.get("class_type") or "")
        return None

    def _original_node_field_value(
        self, scope_path: str, uid: str, field: str
    ) -> Any:
        """Look up a widget value from the original ledger by field name."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return None
        return self._resolve_widget_value(node, field)

    def _node_field_value(
        self, scope_path: str, uid: str, field: str
    ) -> Any:
        """Look up a widget value by field name from the working ledger."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return None
        return self._resolve_widget_value(node, field)

    def _resolve_widget_value(self, node: Mapping[str, Any], field: str) -> Any:
        """Resolve a widget value given a node dict and field name.

        Tries (a) node inputs slot ordering by name, (b) schema input ordering,
        since the schema may not carry ``widget`` metadata in test providers.
        """
        wv = node.get("widgets_values")
        if not isinstance(wv, list):
            return None
        # (a) Try inputs slot order first: find the slot named *field* and use its
        # positional index to index into widgets_values.
        inputs = node.get("inputs") or []
        if isinstance(inputs, list):
            for idx, slot in enumerate(inputs):
                if isinstance(slot, Mapping) and slot.get("name") == field:
                    if 0 <= idx < len(wv):
                        return wv[idx]
                    break
        # (b) Fall back to schema input ordering
        class_type = str(node.get("type") or node.get("class_type") or "")
        schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        if isinstance(schema_inputs, Mapping) and field in schema_inputs:
            # Get the positional index in the schema's input order
            ordered_names = list(schema_inputs.keys())
            try:
                idx = ordered_names.index(field)
                if 0 <= idx < len(wv):
                    return wv[idx]
            except ValueError:
                pass
        return None

    def _original_node_mode(self, scope_path: str, uid: str) -> int:
        """Look up the original mode of a node from the original ledger."""
        node = self.original_ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return node.get("mode", 0)
        return 0

    def _node_mode(self, scope_path: str, uid: str) -> int:
        """Look up the current mode of a node from the working ledger."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is not None:
            return node.get("mode", 0)
        return 0

    def _output_socket_type(
        self, scope_path: str, uid: str, output_slot: str | int
    ) -> str | None:
        """Look up the socket type of an output slot."""
        node = self.ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return None
        class_type = str(node.get("type") or node.get("class_type") or "")
        schema = schema_for(self.schema_provider, class_type)
        schema_outputs = getattr(schema, "outputs", []) or []
        if isinstance(slot_str := output_slot, int):
            if 0 <= slot_str < len(schema_outputs):
                return getattr(schema_outputs[slot_str], "type", None)
        else:
            for out in schema_outputs:
                if getattr(out, "name", None) == slot_str:
                    return getattr(out, "type", None)
        return None

    @staticmethod
    def _find_link_to_target_in_ledger(
        ledger: EditLedger, scope_path: str, uid: str, input_field: str
    ) -> tuple[str, str | int] | None:
        """Find the source (uid, output_slot) connected to a target input in a ledger.

        Returns None if no link exists.
        """
        node = ledger.resolve_node(scope_path or "", uid)
        if node is None:
            return None
        inputs = node.get("inputs") or []
        for slot in inputs:
            if not isinstance(slot, Mapping):
                continue
            if slot.get("name") == input_field:
                link = slot.get("link")
                if isinstance(link, (int, float)) and int(link) != 0:
                    link_id = int(link)
                    # Find the link in the graph
                    links = ledger.graph.get("links") or []
                    for l in links:
                        if not isinstance(l, list) or len(l) < 6:
                            continue
                        if l[0] == link_id:
                            src_uid = str(l[1])
                            src_slot = l[3]
                            return (src_uid, src_slot)
                break
        return None

    def _find_link_to_target(
        self, scope_path: str, uid: str, input_field: str
    ) -> tuple[str, str | int] | None:
        """Find the source (uid, output_slot) currently connected to a target input
        using the working ledger.

        Returns None if no link exists.
        """
        return self._find_link_to_target_in_ledger(
            self.ledger, scope_path, uid, input_field
        )

    def _adjacent_same_type_inputs(
        self, scope_path: str, exclude_field: str
    ) -> str | None:
        """If the working ledger has multiple inputs of the same type on any node,
        return a description of the adjacent same-type inputs for the given field.

        This is called during add-node summarization; it checks the target node
        being added to see if it has multiple inputs of the same type.
        """
        # This is harder to compute for add-node since the node isn't in the ledger yet.
        # We'll use the schema for the class_type of the node being constructed.
        return None

    def _uid_for_scope(self, scope_path: str, class_type: str) -> str:
        """Best-effort uid lookup for a newly added node by looking at the ledger."""
        # Look for nodes matching class_type that were recently added.
        # The simplest approach: check the most recently added node in the ledger.
        nodes = self.ledger.graph.get("nodes") or []
        for node in reversed(nodes):
            ct = str(node.get("type") or node.get("class_type") or "")
            if ct == class_type:
                uid = node.get("properties", {}).get("vibecomfy_uid", "")
                if uid and uid in self.name_by_uid:
                    return uid
        return ""

    def _compile_ui_for_done_gate_b(
        self,
        ui_json: Mapping[str, Any],
        *,
        label: str,
    ) -> tuple[VibeWorkflow, dict[str, Any]] | DoneResult:
        try:
            workflow = self._workflow_from_ui(ui_json)
            api = workflow.compile("api")
        except Exception as exc:
            return DoneResult(
                ok=False,
                summary=f"Gate B failed: {label} UI did not compile through the oracle.",
                diagnostics=(
                    _diag(
                        "done_gate_b_compile_failed",
                        f"Gate B could not compile {label} UI: {type(exc).__name__}: {exc}",
                        severity="error",
                        detail={"label": label, "exception_type": type(exc).__name__},
                    ),
                ),
            )
        return workflow, api

    def _done_gate_b_region_node_ids(
        self,
        *,
        ops: tuple[EditOp, ...],
        original_workflow: VibeWorkflow,
        original_api: Mapping[str, Any],
        working_workflow: VibeWorkflow,
        working_api: Mapping[str, Any],
        candidate_workflow: VibeWorkflow,
        candidate_api: Mapping[str, Any],
    ) -> set[str]:
        original_uid_to_node_id = _workflow_uid_to_node_id(original_workflow)
        working_uid_to_node_id = _workflow_uid_to_node_id(working_workflow)
        candidate_uid_to_node_id = _workflow_uid_to_node_id(candidate_workflow)

        original_ids = set(str(node_id) for node_id in original_api)
        working_ids = set(str(node_id) for node_id in working_api)
        candidate_ids = set(str(node_id) for node_id in candidate_api)
        live_ids = working_ids | candidate_ids
        region: set[str] = set()

        added_ids = live_ids - original_ids
        removed_ids = original_ids - live_ids
        region.update(added_ids)

        for scope_path, uid in _done_gate_b_uids_for_ops(ops):
            qualified_uid = self.ledger.qualified_uid(scope_path, uid)
            for mapping in (original_uid_to_node_id, working_uid_to_node_id, candidate_uid_to_node_id):
                node_id = mapping.get(qualified_uid)
                if node_id is not None:
                    region.add(str(node_id))

        for node_id in removed_ids:
            region.update(_api_one_hop_neighbors(original_api, {node_id}))

        region.update(_changed_edge_endpoint_node_ids(original_api, working_api))
        region.update(_changed_edge_endpoint_node_ids(original_api, candidate_api))

        expanded = set(region)
        expanded.update(_api_one_hop_neighbors(working_api, region))
        expanded.update(_api_one_hop_neighbors(candidate_api, region))
        expanded.update(_api_one_hop_neighbors(original_api, region | removed_ids))
        return {node_id for node_id in expanded if node_id in live_ids}

    def _seed_or_validate_name_locks(
        self,
        parsed_names: list[tuple[str, str]],
    ) -> list[CompactDiagnostic]:
        diagnostics: list[CompactDiagnostic] = []
        seen_render_uids: set[str] = set()
        seen_render_names: set[str] = set()
        for uid, name in parsed_names:
            seen_render_uids.add(uid)
            seen_render_names.add(name)
            self.unbound_names.discard(name)
            locked_name = self.name_by_uid.get(uid)
            locked_uid = self.uid_by_name.get(name)
            if locked_name is None and locked_uid is None:
                self.name_by_uid[uid] = name
                self.uid_by_name[name] = uid
                continue
            if locked_name is not None and locked_name != name:
                diagnostics.append(
                    _diag(
                        "render_name_lock_mismatch",
                        f"Uid {uid!r} re-rendered as {name!r} instead of locked name {locked_name!r}.",
                        severity="error",
                        detail={"uid": uid, "expected_name": locked_name, "actual_name": name},
                    )
                )
                continue
            if locked_uid is not None and locked_uid != uid:
                diagnostics.append(
                    _diag(
                        "render_uid_lock_mismatch",
                        f"Name {name!r} is already locked to uid {locked_uid!r}, not {uid!r}.",
                        severity="error",
                        detail={"name": name, "expected_uid": locked_uid, "actual_uid": uid},
                    )
                )
                continue
            self.name_by_uid.setdefault(uid, name)
            self.uid_by_name.setdefault(name, uid)

        if self.name_by_uid:
            missing_uids = sorted(uid for uid in self.name_by_uid if uid not in seen_render_uids)
            for uid in missing_uids:
                diagnostics.append(
                    _diag(
                        "render_locked_uid_missing",
                        f"Previously locked uid {uid!r} was absent from the latest render.",
                        severity="error",
                        detail={"uid": uid, "locked_name": self.name_by_uid[uid]},
                    )
                )
        if self.uid_by_name:
            missing_names = sorted(name for name in self.uid_by_name if name not in seen_render_names)
            for name in missing_names:
                diagnostics.append(
                    _diag(
                        "render_locked_name_missing",
                        f"Previously locked name {name!r} was absent from the latest render.",
                        severity="error",
                        detail={"name": name, "locked_uid": self.uid_by_name[name]},
                    )
                )
        return diagnostics

    def _execute_statements(
        self,
        statements: tuple["_ExpandedStatement", ...],
        *,
        placement_facts: BatchPlacementFacts,
    ) -> tuple[tuple[StatementResult, ...], tuple[EditOp, ...], tuple[CompactDiagnostic, ...]]:
        executed: list[StatementResult] = []
        landed_ops: list[EditOp] = []
        diagnostics: list[CompactDiagnostic] = []
        for item in statements:
            statement = self._resolve_statement(item, placement_facts=placement_facts)
            dep_cause = self._dependency_cause(statement)
            if statement.diagnostics:
                result = StatementResult(
                    statement_index=statement.statement_index,
                    source=statement.source,
                    ok=statement.ok,
                    landed=getattr(statement, "landed", False),
                    op_kind=statement.op_kind,
                    diagnostics=statement.diagnostics,
                    detail=dict(statement.detail),
                    dependency_cause=dep_cause,
                )
                executed.append(result)
                diagnostics.extend(statement.diagnostics)
                continue

            op, op_diagnostics = self._lower_statement_op(statement)
            if op_diagnostics:
                target_name = statement.detail.get("target_name")
                if statement.op_kind == "node_call" and isinstance(target_name, str):
                    self._mark_name_unbound(target_name)
                failed = StatementResult(
                    statement_index=statement.statement_index,
                    source=statement.source,
                    ok=False,
                    landed=False,
                    op_kind=statement.op_kind,
                    diagnostics=statement.diagnostics + tuple(op_diagnostics),
                    detail=dict(statement.detail),
                    dependency_cause=dep_cause,
                )
                executed.append(failed)
                diagnostics.extend(op_diagnostics)
                continue

            detail = dict(statement.detail)
            if op is None:
                executed.append(
                    StatementResult(
                        statement_index=statement.statement_index,
                        source=statement.source,
                        ok=statement.ok,
                        landed=False,
                        op_kind=statement.op_kind,
                        diagnostics=statement.diagnostics,
                        detail=detail,
                        dependency_cause=dep_cause,
                    )
                )
                continue

            detail["edit_op"] = op
            applied = apply_delta(
                self.working_ui,
                (op,),
                schema_provider=self.schema_provider,
            )
            if not applied.ok or applied.candidate is None:
                if isinstance(op, AddNodeOp):
                    target_name = detail.get("target_name")
                    if isinstance(target_name, str):
                        self._mark_name_unbound(target_name)
                issue_diagnostics = tuple(self._compact_port_issue(issue) for issue in applied.diagnostics)
                executed.append(
                    StatementResult(
                        statement_index=statement.statement_index,
                        source=statement.source,
                        ok=False,
                        landed=False,
                        op_kind=statement.op_kind,
                        diagnostics=statement.diagnostics + issue_diagnostics,
                        detail=detail,
                        dependency_cause=dep_cause,
                    )
                )
                diagnostics.extend(issue_diagnostics)
                continue

            self.working_ui = deepcopy(applied.candidate)
            self.ledger = EditLedger.ingest(self.working_ui)
            self.landed_ops.append(op)
            landed_ops.append(op)
            touched_uids, touched_node_ids = self._collect_touched_nodes((op,))
            self.touched_uids.update(touched_uids)
            self.touched_node_ids.update(touched_node_ids)

            if isinstance(op, AddNodeOp):
                target_name = detail.get("target_name")
                resolved = applied.resolved_ops[0][1] if applied.resolved_ops else None
                minted_uid = getattr(resolved, "uid", None)
                minted_scope_path = getattr(resolved, "scope_path", None)
                if isinstance(target_name, str) and isinstance(minted_uid, str) and isinstance(minted_scope_path, str):
                    self._bind_graph_name(target_name, minted_uid)
                    detail["minted_uid"] = minted_uid
                    detail["minted_scope_path"] = minted_scope_path

            executed.append(
                StatementResult(
                    statement_index=statement.statement_index,
                    source=statement.source,
                    ok=statement.ok,
                    landed=True,
                    op_kind=statement.op_kind,
                    diagnostics=statement.diagnostics,
                    detail=detail,
                    touched_uids=tuple(touched_uids),
                    dependency_cause=dep_cause,
                )
            )
        return tuple(executed), tuple(landed_ops), tuple(diagnostics)

    def _resolve_statement(
        self,
        item: "_ExpandedStatement",
        *,
        placement_facts: BatchPlacementFacts,
    ) -> StatementResult:
        statement = item.node
        source = item.source
        env = item.env
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            return StatementResult(
                statement_index=item.statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="done" if _call_name(statement.value) == "done" else "query",
            )
        if isinstance(statement, ast.Assign):
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                return self._resolve_add_node_statement(
                    statement_index=item.statement_index,
                    source=source,
                    target_name=target.id,
                    value=statement.value,
                    env=env,
                    placement_facts=placement_facts,
                )
            assert isinstance(target, ast.Attribute)
            field_target, target_issues = self._resolve_target_field(target)
            if target_issues:
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind=_assignment_op_kind(statement.value, target_attr=target.attr),
                    diagnostics=tuple(target_issues),
                )
            assert field_target is not None
            rhs = statement.value
            if isinstance(rhs, ast.Constant) and rhs.value is None:
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="remove_link",
                    detail={"resolved_target": field_target, "ast_node": statement, "constant_env": dict(env)},
                )
            if _is_graph_reference_value(rhs):
                endpoint, endpoint_issues = self._resolve_rhs_endpoint(rhs, target=field_target)
                if endpoint_issues:
                    return StatementResult(
                        statement_index=item.statement_index,
                        source=source,
                        ok=False,
                        landed=False,
                        op_kind=_assignment_op_kind(rhs, target_attr=target.attr),
                        diagnostics=tuple(endpoint_issues),
                    )
                assert endpoint is not None
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="upsert_link",
                    detail={"resolved_target": field_target, "resolved_endpoint": endpoint, "ast_node": statement, "constant_env": dict(env)},
                )
            return StatementResult(
                statement_index=item.statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="set_mode" if target.attr == "mode" else "set_node_field",
                detail={"resolved_target": field_target, "ast_node": statement, "constant_env": dict(env)},
            )
        assert isinstance(statement, ast.Delete)
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            node_ref, issues = self._resolve_graph_name(target.id)
        else:
            node_ref, issues = None, [_unsafe(target, "scope_escape_not_allowed", "Only bare graph names may be deleted.")]
        _ = node_ref
        return StatementResult(
            statement_index=item.statement_index,
            source=source,
            ok=not issues,
            landed=False,
            op_kind="remove_node",
            diagnostics=tuple(issues),
            detail={"resolved_node": node_ref, "ast_node": statement, "constant_env": dict(env)}
            if node_ref is not None
            else {"ast_node": statement, "constant_env": dict(env)},
        )

    def _lower_statement_op(
        self,
        statement: StatementResult,
    ) -> tuple[EditOp | None, tuple[CompactDiagnostic, ...]]:
        op_kind = statement.op_kind
        if op_kind in {None, "done", "query"}:
            return None, ()

        if op_kind == "node_call":
            resolved_call = statement.detail.get("resolved_add_node")
            if not isinstance(resolved_call, _ResolvedAddNodeCall):
                return None, (
                    _diag("missing_resolved_add_node", "Add-node statement was missing its resolved node-call payload.", severity="error"),
                )
            return (
                AddNodeOp(
                    op="add_node",
                    scope_path=resolved_call.scope_path,
                    class_type=resolved_call.class_type,
                    fields=dict(resolved_call.fields),
                    inputs=dict(resolved_call.inputs),
                    anchor=resolved_call.anchor,
                ),
                (),
            )

        if op_kind == "remove_node":
            node_ref = statement.detail.get("resolved_node")
            if not isinstance(node_ref, _ResolvedGraphName):
                return None, (_diag("missing_resolved_node", "Delete statement was missing its resolved node.", severity="error"),)
            immutable = self._original_virtual_mutation_diagnostics(node_ref, action="delete")
            if immutable:
                return None, immutable
            return RemoveNodeOp(op="remove_node", target=NodeTarget(node_ref.scope_path, node_ref.uid)), ()

        target = statement.detail.get("resolved_target")
        if not isinstance(target, _ResolvedTargetField):
            return None, (
                _diag("missing_resolved_target", "Assignment statement was missing its resolved target.", severity="error"),
            )

        immutable = self._original_virtual_mutation_diagnostics(target.node, action="mutate")
        if immutable:
            return None, immutable

        node_target = NodeTarget(target.node.scope_path, target.node.uid)
        field_target = NodeFieldTarget(target.node.scope_path, target.node.uid, target.field_name)
        ast_node = statement.detail.get("ast_node")
        constant_env = MappingProxyType(dict(statement.detail.get("constant_env", {})))
        assign_node = ast_node if isinstance(ast_node, ast.Assign) else None
        rhs = assign_node.value if assign_node is not None else None

        if op_kind == "remove_link":
            return (
                RemoveLinkOp(
                    op="remove_link",
                    target=LinkTargetRef(target.node.scope_path, target.node.uid, target.field_name),
                ),
                (),
            )
        if op_kind == "upsert_link":
            endpoint = statement.detail.get("resolved_endpoint")
            if not isinstance(endpoint, _ResolvedOutputEndpoint):
                return None, (
                    _diag("missing_resolved_endpoint", "Link assignment was missing its resolved source endpoint.", severity="error"),
                )
            source_slot: str | int = endpoint.slot_name if endpoint.slot_index is None else endpoint.slot_name
            return (
                UpsertLinkOp(
                    op="upsert_link",
                    source=LinkSourceRef(endpoint.node.scope_path, endpoint.node.uid, source_slot),
                    target=LinkTargetRef(target.node.scope_path, target.node.uid, target.field_name),
                ),
                (),
            )
        if op_kind == "set_mode":
            if rhs is None:
                return None, (
                    _diag("missing_mode_value", "Mode assignment was missing its right-hand side.", severity="error"),
                )
            mode_value, mode_issues = self._coerce_mode_value(rhs, env=constant_env)
            if mode_issues:
                return None, mode_issues
            assert mode_value is not None
            return SetModeOp(op="set_mode", target=node_target, mode=mode_value), ()

        if rhs is None:
            return None, (
                _diag("missing_literal_value", "Field assignment was missing its right-hand side.", severity="error"),
            )
        literal_value, literal_issue = _fold_constant(rhs, env=constant_env)
        if literal_issue is not None:
            return None, (literal_issue,)
        return SetNodeFieldOp(op="set_node_field", target=field_target, value=literal_value), ()

    def _coerce_mode_value(
        self,
        value: ast.expr,
        *,
        env: Mapping[str, Any],
    ) -> tuple[int | None, tuple[CompactDiagnostic, ...]]:
        literal_value, diagnostic = _fold_constant(value, env=env)
        if diagnostic is not None:
            return None, (diagnostic,)
        if isinstance(literal_value, str):
            mode = _MODE_LABEL_TO_VALUE.get(literal_value.strip().lower())
            if mode is None:
                return None, (
                    _diag(
                        "unknown_mode_label",
                        f"Unknown mode label {literal_value!r}. Expected one of: {', '.join(sorted(_MODE_LABEL_TO_VALUE))}.",
                        severity="error",
                        detail={"value": literal_value},
                    ),
                )
            return mode, ()
        if isinstance(literal_value, bool) or not isinstance(literal_value, int) or literal_value not in MODE_LABELS:
            return None, (
                _diag(
                    "invalid_mode_value",
                    "Mode assignments must use 0, 2, 4 or their MODE_LABELS-derived labels.",
                    severity="error",
                    detail={"value": literal_value},
                ),
            )
        return literal_value, ()

    def _original_virtual_mutation_diagnostics(
        self,
        node_ref: _ResolvedGraphName,
        *,
        action: str,
    ) -> tuple[CompactDiagnostic, ...]:
        original_node = self.original_ledger.resolve_node(node_ref.scope_path, node_ref.uid)
        if original_node is None:
            return ()
        class_type = str(original_node.get("type") or original_node.get("class_type") or "")
        if class_type not in HELPER_NODE_TYPES:
            return ()
        return (
            _diag(
                "original_virtual_node_immutable",
                f"Original virtual substrate node {node_ref.name!r} ({class_type}) cannot be {action}d in M1.",
                severity="error",
                detail={
                    "name": node_ref.name,
                    "uid": node_ref.uid,
                    "scope_path": node_ref.scope_path,
                    "class_type": class_type,
                    "action": action,
                },
            ),
        )

    def _collect_touched_nodes(
        self,
        ops: tuple[EditOp, ...],
    ) -> tuple[set[str], set[str]]:
        touched_uids: set[str] = set()
        touched_node_ids: set[str] = set()
        for op in ops:
            for scope_path, uid in _uids_for_op(op):
                touched_uids.add(self.ledger.qualified_uid(scope_path, uid))
                node = self.ledger.resolve_node(scope_path, uid)
                if node is None:
                    continue
                node_id = node.get("id")
                if node_id is not None:
                    touched_node_ids.add(str(node_id))
        return touched_uids, touched_node_ids

    def _bind_graph_name(self, name: str, uid: str) -> None:
        prior_uid = self.uid_by_name.get(name)
        if prior_uid is not None and self.name_by_uid.get(prior_uid) == name:
            self.name_by_uid.pop(prior_uid, None)
        prior_name = self.name_by_uid.get(uid)
        if prior_name is not None and self.uid_by_name.get(prior_name) == uid:
            self.uid_by_name.pop(prior_name, None)
        self.uid_by_name[name] = uid
        self.name_by_uid[uid] = name
        self.unbound_names.discard(name)

    def _mark_name_unbound(self, name: str) -> None:
        prior_uid = self.uid_by_name.pop(name, None)
        if prior_uid is not None and self.name_by_uid.get(prior_uid) == name:
            self.name_by_uid.pop(prior_uid, None)
        self.unbound_names.add(name)

    def _resolve_add_node_statement(
        self,
        *,
        statement_index: int,
        source: str,
        target_name: str,
        value: ast.expr,
        env: Mapping[str, Any],
        placement_facts: BatchPlacementFacts,
    ) -> StatementResult:
        if target_name.startswith("__"):
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=(
                    _diag("dunder_name_not_allowed", f"Graph name {target_name!r} is not allowed.", severity="error"),
                ),
                detail={"target_name": target_name},
            )
        if not isinstance(value, ast.Call):
            self._mark_name_unbound(target_name)
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=(
                    _diag("expression_not_call", "Only node-construction calls may be assigned to graph names.", severity="error"),
                ),
                detail={"target_name": target_name},
            )
        resolved_call, issues = self._resolve_add_node_call(
            target_name,
            value,
            env=env,
            placement_facts=placement_facts,
        )
        if issues:
            self._mark_name_unbound(target_name)
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="node_call",
                diagnostics=tuple(issues),
                detail={"target_name": target_name, "ast_node": value, "constant_env": dict(env)},
            )
        assert resolved_call is not None
        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="node_call",
            detail={
                "target_name": target_name,
                "ast_node": value,
                "constant_env": dict(env),
                "resolved_add_node": resolved_call,
            },
        )

    def _resolve_add_node_call(
        self,
        target_name: str,
        call: ast.Call,
        *,
        env: Mapping[str, Any],
        placement_facts: BatchPlacementFacts,
    ) -> tuple[_ResolvedAddNodeCall | None, list[CompactDiagnostic]]:
        func = call.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "vibecomfy":
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface.",
                )
            ]
        if not isinstance(func, ast.Name):
            return None, [_unsafe(func, "call_target_not_name", "Node construction calls must target a simple class name.")]
        class_type = func.id
        if class_type.startswith("vibecomfy."):
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface.",
                )
            ]

        schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        fake_target_node = _ResolvedGraphName(
            name=target_name,
            uid="<pending>",
            scope_path="",
            node={},
            class_type=class_type,
        )
        literal_fields: dict[str, Any] = {}
        linked_inputs: dict[str, LinkSourceRef] = {}
        anchor_near: NodeTarget | None = None
        relation: str | None = None
        group_title: str | None = None
        issues: list[CompactDiagnostic] = []

        for keyword in call.keywords:
            if keyword.arg is None:
                issues.append(_unsafe(keyword.value, "kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed."))
                continue
            name = keyword.arg
            if name in _RAW_COORDINATE_HINT_NAMES:
                issues.append(
                    _unsafe(
                        keyword.value,
                        "raw_coordinate_kwarg_not_allowed",
                        f"Raw coordinate kwarg {name!r} is not allowed; use near=..., relation=..., and group=... placement hints.",
                    )
                )
                continue
            if name == "near":
                if not isinstance(keyword.value, ast.Name):
                    issues.append(
                        _unsafe(keyword.value, "invalid_near_hint", "near= must reference a rendered graph name, not a slot or literal.")
                    )
                    continue
                node_ref, near_issues = self._resolve_graph_name(keyword.value.id)
                if near_issues:
                    issues.extend(near_issues)
                    continue
                assert node_ref is not None
                anchor_near = NodeTarget(node_ref.scope_path, node_ref.uid)
                continue
            if name == "relation":
                relation_value, relation_issue = _fold_constant(keyword.value, env=env)
                if relation_issue is not None:
                    issues.append(relation_issue)
                    continue
                if not isinstance(relation_value, str):
                    issues.append(_unsafe(keyword.value, "invalid_relation_hint", "relation= must be a string literal."))
                    continue
                relation = relation_value.strip()
                if relation not in {"near", "right_of", "below"}:
                    issues.append(
                        _unsafe(
                            keyword.value,
                            "invalid_relation_hint",
                            "relation= must be one of 'near', 'right_of', or 'below' for Python add-node statements.",
                        )
                    )
                continue
            if name == "group":
                group_value, group_issue = _fold_constant(keyword.value, env=env)
                if group_issue is not None:
                    issues.append(group_issue)
                    continue
                if not isinstance(group_value, str) or not group_value.strip():
                    issues.append(_unsafe(keyword.value, "invalid_group_hint", "group= must be a non-empty string literal."))
                    continue
                group_title = group_value
                continue
            if _is_graph_reference_value(keyword.value):
                socket_type = _normalize_type(getattr(schema_inputs.get(name), "type", None))
                target = _ResolvedTargetField(node=fake_target_node, field_name=name, socket_type=socket_type)
                endpoint, endpoint_issues = self._resolve_rhs_endpoint(keyword.value, target=target)
                if endpoint_issues:
                    issues.extend(endpoint_issues)
                    continue
                assert endpoint is not None
                linked_inputs[name] = LinkSourceRef(endpoint.node.scope_path, endpoint.node.uid, endpoint.slot_name)
                continue
            literal_value, literal_issue = _fold_constant(keyword.value, env=env)
            if literal_issue is not None:
                issues.append(literal_issue)
                continue
            literal_fields[name] = literal_value

        if relation is not None and anchor_near is None and group_title is None:
            issues.append(
                _diag(
                    "anchor_target_missing",
                    "relation= requires near=... or group=... to anchor the new node.",
                    severity="error",
                    detail={"class_type": class_type, "target_name": target_name},
                )
            )

        scope_paths = {ref.scope_path for ref in linked_inputs.values()}
        if anchor_near is not None:
            scope_paths.add(anchor_near.scope_path)
        if len(scope_paths) > 1:
            issues.append(
                _diag(
                    "cross_scope_add_node_unsupported",
                    "Add-node statements cannot mix link and anchor references from different scopes.",
                    severity="error",
                    detail={"target_name": target_name, "scope_paths": sorted(scope_paths)},
                )
            )
        if issues:
            return None, issues
        scope_path = next(iter(scope_paths), "")
        anchor = None
        if anchor_near is not None or group_title is not None:
            anchor = AnchorRef(
                relation=(relation or "near"),  # type: ignore[arg-type]
                near=anchor_near,
                group_title=group_title,
            )
        else:
            anchor = self._infer_add_node_anchor(
                target_name=target_name,
                scope_path=scope_path,
                resolved_inputs=linked_inputs,
                placement_facts=placement_facts,
            )
        return (
            _ResolvedAddNodeCall(
                target_name=target_name,
                scope_path=scope_path,
                class_type=class_type,
                fields=literal_fields,
                inputs=linked_inputs,
                anchor=anchor,
            ),
            [],
        )

    @staticmethod
    def _compact_port_issue(issue: Any) -> CompactDiagnostic:
        return CompactDiagnostic(
            code=str(getattr(issue, "code", "edit_apply_error")),
            message=str(getattr(issue, "message", "Edit apply failed.")),
            severity=str(getattr(issue, "severity", "error")),
            detail=dict(getattr(issue, "detail", {}) or {}),
        )

    def _estimate_add_node_width(self, class_type: str) -> int:
        from vibecomfy.porting.layout.sizing import estimate_node_size
        from vibecomfy.workflow import VibeNode

        schema = schema_for(self.schema_provider, class_type)
        return estimate_node_size(VibeNode(id="__batch__", class_type=class_type, uid="__batch__"), schema)[0]

    def _infer_add_node_anchor(
        self,
        *,
        target_name: str,
        scope_path: str,
        resolved_inputs: Mapping[str, LinkSourceRef],
        placement_facts: BatchPlacementFacts,
    ) -> AnchorRef | None:
        hint = infer_add_node_anchor_hint(
            target_name=target_name,
            resolved_inputs=resolved_inputs,
            placement_facts=placement_facts,
            current_input_source_ref=self._current_input_source_ref,
            uid_to_name=self.name_by_uid,
        )
        if hint is None:
            return None
        return self._materialize_inferred_anchor(scope_path=scope_path, hint=hint)

    def _materialize_inferred_anchor(
        self,
        *,
        scope_path: str,
        hint: InferredAnchorHint,
    ) -> AnchorRef | None:
        if hint.relation == "between" and hint.between_names is not None:
            left = self._resolve_graph_name_soft(hint.between_names[0])
            right = self._resolve_graph_name_soft(hint.between_names[1])
            if left is None or right is None or left.scope_path != scope_path or right.scope_path != scope_path:
                return None
            return AnchorRef(
                relation="between",
                between=(NodeTarget(left.scope_path, left.uid), NodeTarget(right.scope_path, right.uid)),
            )
        if hint.near_name is None:
            return None
        near = self._resolve_graph_name_soft(hint.near_name)
        if near is None or near.scope_path != scope_path:
            return None
        return AnchorRef(relation="right_of", near=NodeTarget(near.scope_path, near.uid))

    def _resolve_graph_name_soft(self, name: str) -> _ResolvedGraphName | None:
        node_ref, issues = self._resolve_graph_name(name)
        if issues:
            return None
        return node_ref

    def _graph_name_exists(self, name: str) -> bool:
        node_ref, issues = self._resolve_graph_name(name)
        return node_ref is not None and not issues

    def _current_input_source_ref(self, target_name: str, target_field: str) -> LinkSourceRef | None:
        target = self._resolve_graph_name_soft(target_name)
        if target is None:
            return None
        inputs = target.node.get("inputs")
        if not isinstance(inputs, list):
            return None
        input_slot = _find_named_slot(inputs, target_field)
        if input_slot is None:
            return None
        link_id = input_slot.get("link")
        if not isinstance(link_id, int):
            return None
        raw_link = self.ledger.resolve_link(target.scope_path, link_id)
        if raw_link is None:
            return None
        origin_id, origin_slot = _link_origin(raw_link)
        if origin_id is None:
            return None
        origin_node = self._node_by_id(target.scope_path, origin_id)
        if origin_node is None:
            return None
        origin_uid = str(origin_node.get("properties", {}).get("vibecomfy_uid") or origin_node.get("id"))
        slot_name = _output_slot_name(origin_node, origin_slot, self.schema_provider)
        output_slot: str | int = slot_name if slot_name is not None else origin_slot
        return LinkSourceRef(target.scope_path, origin_uid, output_slot)

    def _node_by_id(self, scope_path: str, node_id: int) -> Mapping[str, Any] | None:
        scope = self.ledger.scopes.get(scope_path)
        if scope is None:
            return None
        nodes = scope.graph.get("nodes")
        if not isinstance(nodes, list):
            return None
        for node in nodes:
            if isinstance(node, Mapping) and node.get("id") == node_id:
                return node
        return None

    @staticmethod
    def _dependency_cause(statement: StatementResult) -> str | None:
        for diagnostic in statement.diagnostics:
            if diagnostic.code == "unbound_graph_name":
                name = str(diagnostic.detail.get("name", "?"))
                return f"Statement depends on graph name {name!r} whose add-node statement did not land."
        return None

    def _resolve_graph_name(
        self,
        name: str,
    ) -> tuple[_ResolvedGraphName | None, list[CompactDiagnostic]]:
        if name.startswith("__"):
            return None, [_diag("dunder_name_not_allowed", f"Graph name {name!r} is not allowed.", severity="error")]
        if name in self.unbound_names:
            return None, [
                _diag(
                    "unbound_graph_name",
                    f"Graph name {name!r} is currently unbound because its add-node statement did not land.",
                    severity="error",
                    detail={"name": name},
                )
            ]
        uid = self.uid_by_name.get(name)
        if uid is None:
            return None, [
                _diag(
                    "unknown_graph_name",
                    f"Unknown graph name {name!r}. Render the session again if the canvas changed.",
                    severity="error",
                    detail={"name": name},
                )
            ]
        matches = [(scope_path, node) for (scope_path, node_uid), node in self.ledger.node_index.items() if node_uid == uid]
        if not matches:
            return None, [
                _diag(
                    "stale_graph_name",
                    f"Graph name {name!r} still points at uid {uid!r}, but that uid is no longer present.",
                    severity="error",
                    detail={"name": name, "uid": uid},
                )
            ]
        if len(matches) > 1:
            return None, [
                _diag(
                    "scope_escape_not_allowed",
                    f"Graph name {name!r} resolves to multiple scopes; explicit scope paths are not allowed in M1.",
                    severity="error",
                    detail={"name": name, "uid": uid, "scope_paths": [scope for scope, _ in matches]},
                )
            ]
        scope_path, node = matches[0]
        class_type = str(node.get("type") or node.get("class_type") or "")
        return _ResolvedGraphName(name=name, uid=uid, scope_path=scope_path, node=node, class_type=class_type), []

    def _resolve_target_field(
        self,
        target: ast.Attribute,
    ) -> tuple[_ResolvedTargetField | None, list[CompactDiagnostic]]:
        node_ref, issues = self._resolve_attribute_base(target, code_unknown="unknown_target_name")
        if issues:
            return None, issues
        assert node_ref is not None
        if target.attr.startswith("__"):
            return None, [_unsafe(target, "dunder_attribute_not_allowed", "Dunder target attributes are not allowed.")]
        schema = schema_for(self.schema_provider, node_ref.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        schema_input = schema_inputs.get(target.attr)
        raw_input = _find_named_slot(node_ref.node.get("inputs"), target.attr)
        if raw_input is None and schema_input is None and target.attr != "mode":
            return None, [
                _diag(
                    "unknown_target_field",
                    f"{node_ref.class_type} has no editable field or input named {target.attr!r}.",
                    severity="error",
                    detail={"name": node_ref.name, "uid": node_ref.uid, "field": target.attr},
                )
            ]
        socket_type = _normalize_type(
            getattr(schema_input, "type", None) if schema_input is not None else raw_input.get("type") if isinstance(raw_input, Mapping) else None
        )
        return _ResolvedTargetField(node=node_ref, field_name=target.attr, socket_type=socket_type), []

    def _resolve_rhs_endpoint(
        self,
        value: ast.expr,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        if isinstance(value, ast.Name):
            node_ref, issues = self._resolve_graph_name(value.id)
            if issues:
                return None, issues
            assert node_ref is not None
            return self._resolve_bare_output(node_ref, target=target)
        assert isinstance(value, ast.Attribute)
        node_ref, issues = self._resolve_attribute_base(value, code_unknown="unknown_source_name")
        if issues:
            return None, issues
        assert node_ref is not None
        if value.attr.startswith("__"):
            return None, [_unsafe(value, "dunder_attribute_not_allowed", "Dunder source attributes are not allowed.")]
        return self._resolve_named_output(node_ref, value.attr, target=target)

    def _resolve_attribute_base(
        self,
        attr: ast.Attribute,
        *,
        code_unknown: str,
    ) -> tuple[_ResolvedGraphName | None, list[CompactDiagnostic]]:
        if isinstance(attr.value, ast.Attribute):
            return None, [
                _unsafe(
                    attr,
                    "scope_escape_not_allowed",
                    "Only one attribute hop is allowed; nested attribute scope escapes are not allowed.",
                )
            ]
        if not isinstance(attr.value, ast.Name):
            return None, [_unsafe(attr, "attribute_base_not_name", "Attribute access must start from a rendered graph name.")]
        node_ref, issues = self._resolve_graph_name(attr.value.id)
        if issues and issues[0].code == "unknown_graph_name":
            issues = [
                _diag(
                    code_unknown,
                    issues[0].message,
                    severity=issues[0].severity,
                    detail=issues[0].detail,
                )
            ]
        return node_ref, issues

    def _resolve_named_output(
        self,
        node_ref: _ResolvedGraphName,
        slot_attr: str,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        raw_outputs = _output_specs(node_ref.node, self.schema_provider, node_ref.class_type)
        raw_name_map = {item["name"]: item["name"] for item in raw_outputs if item["name"]}
        try:
            raw_slot = slot_attr if slot_attr in raw_name_map else to_raw_name(slot_attr, context=raw_name_map)
        except (KeyError, ValueError):
            raw_slot = None
        if raw_slot is None:
            return None, [
                _diag(
                    "unknown_output_slot",
                    f"{node_ref.class_type} has no output named {slot_attr!r}.",
                    severity="error",
                    detail={
                        "name": node_ref.name,
                        "uid": node_ref.uid,
                        "slot": slot_attr,
                        "available_slots": [item["name"] for item in raw_outputs if item["name"]],
                    },
                )
            ]
        for item in raw_outputs:
            if item["name"] == raw_slot:
                return _ResolvedOutputEndpoint(
                    node=node_ref,
                    slot_name=raw_slot,
                    slot_index=item["index"],
                    socket_type=item["type"],
                ), []
        return None, [
            _diag(
                "unknown_output_slot",
                f"{node_ref.class_type} has no output named {raw_slot!r}.",
                severity="error",
                detail={"name": node_ref.name, "uid": node_ref.uid, "slot": raw_slot},
            )
        ]

    def _resolve_bare_output(
        self,
        node_ref: _ResolvedGraphName,
        *,
        target: _ResolvedTargetField,
    ) -> tuple[_ResolvedOutputEndpoint | None, list[CompactDiagnostic]]:
        if target.socket_type is None:
            return None, [
                _diag(
                    "ambiguous_bare_reference",
                    (
                        f"Bare reference {node_ref.name!r} cannot be resolved for "
                        f"{target.node.class_type}.{target.field_name} without a schema-backed target socket type."
                    ),
                    severity="error",
                    detail={"target_name": target.node.name, "target_field": target.field_name, "source_name": node_ref.name},
                )
            ]
        candidates = [
            item
            for item in _output_specs(node_ref.node, self.schema_provider, node_ref.class_type)
            if item["type"] is not None and socket_types_compatible(item["type"], target.socket_type)
        ]
        if len(candidates) != 1:
            return None, [
                _diag(
                    "ambiguous_bare_reference",
                    (
                        f"Bare reference {node_ref.name!r} is ambiguous for "
                        f"{target.node.class_type}.{target.field_name}; expected exactly one compatible output."
                    ),
                    severity="error",
                    detail={
                        "target_name": target.node.name,
                        "target_field": target.field_name,
                        "source_name": node_ref.name,
                        "target_socket_type": target.socket_type,
                        "candidate_slots": [item["name"] for item in candidates],
                    },
                )
            ]
        candidate = candidates[0]
        return _ResolvedOutputEndpoint(
            node=node_ref,
            slot_name=candidate["name"],
            slot_index=candidate["index"],
            socket_type=candidate["type"],
        ), []


__all__ = [
    "BatchResult",
    "CompactDiagnostic",
    "DoneResult",
    "EditSession",
    "StatementResult",
]


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


def _parse_and_validate_batch(
    code: str,
    *,
    max_batch_bytes: int,
    max_statements: int,
    max_expanded_statements: int,
    max_for_iterations: int,
) -> _ParsedBatch:
    byte_count = len(code.encode("utf-8"))
    if byte_count > max_batch_bytes:
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=(
                _diag(
                    "batch_byte_cap_exceeded",
                    "Edit batch exceeds the configured byte cap.",
                    severity="error",
                    detail={"bytes": byte_count, "max_bytes": max_batch_bytes},
                ),
            ),
        )
    try:
        module = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=(
                _diag(
                    "batch_syntax_error",
                    exc.msg,
                    severity="error",
                    detail={"line": exc.lineno, "offset": exc.offset},
                ),
            ),
        )

    if len(module.body) > max_statements:
        return _ParsedBatch(
            statements=(),
            expanded=(),
            diagnostics=(
                _diag(
                    "batch_statement_cap_exceeded",
                    "Edit batch exceeds the configured top-level statement cap.",
                    severity="error",
                    detail={"statements": len(module.body), "max_statements": max_statements},
                ),
            ),
        )

    statements: list[StatementResult] = []
    expanded_statements: list[_ExpandedStatement] = []
    diagnostics: list[CompactDiagnostic] = []
    expanded_count = 0
    for statement in module.body:
        expanded, issues = _expand_statement(
            statement,
            code,
            env=MappingProxyType({}),
            max_for_iterations=max_for_iterations,
        )
        diagnostics.extend(issues)
        if diagnostics:
            continue
        expanded_count += len(expanded)
        if expanded_count > max_expanded_statements:
            diagnostics.append(
                _diag(
                    "batch_expanded_statement_cap_exceeded",
                    "Edit batch exceeds the configured expanded statement cap.",
                    severity="error",
                    detail={
                        "expanded_statements": expanded_count,
                        "max_expanded_statements": max_expanded_statements,
                    },
                )
            )
            break
        statements.extend(expanded)
        expanded_statements.extend(
            _ExpandedStatement(
                statement_index=item.statement_index,
                source=item.source,
                op_kind=item.op_kind or "statement",
                node=item.detail["ast_node"],
                env=MappingProxyType(dict(item.detail.get("constant_env", {}))),
            )
            for item in expanded
        )

    if diagnostics:
        return _ParsedBatch(statements=tuple(statements), expanded=tuple(expanded_statements), diagnostics=tuple(diagnostics))
    return _ParsedBatch(statements=tuple(statements), expanded=tuple(expanded_statements), diagnostics=())


def _expand_statement(
    statement: ast.stmt,
    source: str,
    *,
    env: Mapping[str, Any],
    max_for_iterations: int,
) -> tuple[list[StatementResult], list[CompactDiagnostic]]:
    if isinstance(statement, ast.For):
        return _expand_for(statement, source, env=env, max_for_iterations=max_for_iterations)
    issues = _validate_planned_statement(statement, env=env)
    if issues:
        return [], issues
    segment = ast.get_source_segment(source, statement) or ""
    return [
        StatementResult(
            statement_index=getattr(statement, "lineno", 0),
            source=segment.strip(),
            ok=True,
            landed=False,
            op_kind=_statement_op_kind(statement),
            detail={
                "ast_node": statement,
                "constant_env": dict(env),
            },
        )
    ], []


def _expand_for(
    statement: ast.For,
    source: str,
    *,
    env: Mapping[str, Any],
    max_for_iterations: int,
) -> tuple[list[StatementResult], list[CompactDiagnostic]]:
    if not isinstance(statement.target, ast.Name):
        return [], [_unsafe(statement, "for_target_not_name", "Only simple for-loop targets are allowed.")]
    if statement.orelse:
        return [], [_unsafe(statement, "for_else_not_allowed", "for/else is not allowed.")]
    values, diagnostic = _constant_range_values(statement.iter, max_for_iterations=max_for_iterations)
    if diagnostic is not None:
        return [], [diagnostic]
    expanded: list[StatementResult] = []
    issues: list[CompactDiagnostic] = []
    for value in values:
        child_env = dict(env)
        child_env[statement.target.id] = value
        for child in statement.body:
            child_expanded, child_issues = _expand_statement(
                child,
                source,
                env=MappingProxyType(child_env),
                max_for_iterations=max_for_iterations,
            )
            issues.extend(child_issues)
            expanded.extend(child_expanded)
    return expanded, issues


def _constant_range_values(
    node: ast.expr,
    *,
    max_for_iterations: int,
) -> tuple[tuple[int, ...], CompactDiagnostic | None]:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "range":
        return (), _unsafe(node, "for_iter_not_range", "Only for-loops over range(...) are allowed.")
    if node.keywords or not 1 <= len(node.args) <= 3:
        return (), _unsafe(node, "range_shape_not_allowed", "range(...) must use one to three positional constants.")
    folded: list[Any] = []
    for arg in node.args:
        value, diagnostic = _fold_constant(arg, env=MappingProxyType({}))
        if diagnostic is not None:
            return (), diagnostic
        folded.append(value)
    if any(isinstance(item, bool) or not isinstance(item, int) for item in folded):
        return (), _unsafe(node, "range_non_integer", "range(...) bounds must be integers.")
    try:
        values = tuple(range(*folded))
    except ValueError as exc:
        return (), _unsafe(node, "range_invalid", str(exc))
    if len(values) > max_for_iterations:
        return (), _unsafe(
            node,
            "for_iteration_cap_exceeded",
            "for-loop exceeds the configured iteration cap.",
            detail={"iterations": len(values), "max_iterations": max_for_iterations},
        )
    return values, None


def _validate_planned_statement(
    statement: ast.stmt,
    *,
    env: Mapping[str, Any],
) -> list[CompactDiagnostic]:
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        return [_unsafe(statement, "import_not_allowed", "Imports are not allowed in edit batches.")]
    if isinstance(statement, ast.Assign):
        if len(statement.targets) != 1:
            return [_unsafe(statement, "assignment_target_not_allowed", "Only single-target assignments are allowed.")]
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            return _validate_call(statement.value, env=env, top_level=True)
        if isinstance(target, ast.Attribute):
            return _validate_edit_assignment(target, statement.value, env=env)
        return [_unsafe(statement, "assignment_target_not_allowed", "Only name or one-hop attribute assignments are allowed.")]
    if isinstance(statement, ast.Delete):
        if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            return [_unsafe(statement, "delete_target_not_allowed", "Only bare graph names may be deleted.")]
        if statement.targets[0].id.startswith("__"):
            return [_unsafe(statement.targets[0], "dunder_name_not_allowed", "Dunder graph names are not allowed.")]
        return []
    if isinstance(statement, ast.Expr):
        return _validate_call(statement.value, env=env, top_level=True)
    return [_unsafe(statement, "statement_not_allowed", f"{type(statement).__name__} statements are not allowed.")]


def _validate_call(
    node: ast.expr,
    *,
    env: Mapping[str, Any],
    top_level: bool,
) -> list[CompactDiagnostic]:
    if not isinstance(node, ast.Call):
        return [_unsafe(node, "expression_not_call", "Only planned top-level calls are allowed.")]
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "vibecomfy":
        return [
            _unsafe(
                node.func,
                "intent_class_construction_not_allowed",
                "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface.",
            )
        ]
    if not isinstance(node.func, ast.Name):
        return [_unsafe(node, "call_target_not_name", "Calls must target a simple function name.")]
    name = node.func.id
    if name in _FORBIDDEN_CALL_NAMES or name.startswith("__"):
        return [_unsafe(node, "call_not_allowed", f"Call to {name!r} is not allowed.")]
    if name == "range":
        return [_unsafe(node, "range_only_in_for", "range(...) is only allowed as a for-loop iterator.")]
    if name == "done":
        if node.args or node.keywords:
            return [_unsafe(node, "done_arguments_not_allowed", "done() does not accept arguments.")]
        return []
    if not top_level:
        return [_unsafe(node, "nested_call_not_allowed", "Nested calls are not allowed.")]
    if node.args:
        return [_unsafe(node, "positional_args_not_allowed", "Node calls must use keyword arguments.")]
    issues: list[CompactDiagnostic] = []
    for keyword in node.keywords:
        if keyword.arg is None:
            issues.append(_unsafe(keyword.value, "kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed."))
            continue
        if keyword.arg.startswith("__"):
            issues.append(
                _unsafe(keyword.value, "dunder_keyword_not_allowed", "Dunder keyword names are not allowed.")
            )
            continue
        if keyword.arg == "near":
            if isinstance(keyword.value, ast.Name):
                if keyword.value.id.startswith("__"):
                    issues.append(_unsafe(keyword.value, "dunder_name_not_allowed", "Dunder source graph names are not allowed."))
                continue
            issues.append(_unsafe(keyword.value, "invalid_near_hint", "near= must reference a rendered graph name."))
            continue
        if keyword.arg == "relation" or keyword.arg == "group" or keyword.arg in _RAW_COORDINATE_HINT_NAMES:
            value, diagnostic = _fold_constant(keyword.value, env=env)
            _ = value
            if diagnostic is not None:
                issues.append(diagnostic)
            continue
        issues.extend(_validate_node_call_value(keyword.value, env=env))
    return issues


def _validate_node_call_value(node: ast.expr, *, env: Mapping[str, Any]) -> list[CompactDiagnostic]:
    if _is_handle_ref(node):
        return []
    value, diagnostic = _fold_constant(node, env=env)
    if diagnostic is None:
        return []
    return [diagnostic]


def _is_handle_ref(node: ast.expr) -> bool:
    if not isinstance(node, ast.Attribute) or node.attr.startswith("__"):
        return False
    base = node.value
    return isinstance(base, ast.Name) and not base.id.startswith("__")


def _validate_edit_assignment(
    target: ast.Attribute,
    value: ast.expr,
    *,
    env: Mapping[str, Any],
) -> list[CompactDiagnostic]:
    issues = _validate_graph_attribute(target, role="target")
    if issues:
        return issues
    if target.attr == "mode":
        literal_value, diagnostic = _fold_constant(value, env=env)
        _ = literal_value
        if diagnostic is None:
            return []
        return [diagnostic]
    if isinstance(value, ast.Constant) and value.value is None:
        return []
    if isinstance(value, ast.Name) and value.id.startswith("__"):
        return [_unsafe(value, "dunder_name_not_allowed", "Dunder source graph names are not allowed.")]
    if isinstance(value, ast.Attribute):
        attr_issues = _validate_graph_attribute(value, role="source")
        if not attr_issues:
            return []
        return attr_issues
    if _is_graph_reference_value(value):
        return _validate_graph_reference_value(value)
    literal_value, diagnostic = _fold_constant(value, env=env)
    _ = literal_value
    if diagnostic is None:
        return []
    return [diagnostic]


def _validate_graph_attribute(attr: ast.Attribute, *, role: str) -> list[CompactDiagnostic]:
    if attr.attr.startswith("__"):
        return [_unsafe(attr, "dunder_attribute_not_allowed", f"Dunder {role} attributes are not allowed.")]
    if isinstance(attr.value, ast.Attribute):
        return [_unsafe(attr, "scope_escape_not_allowed", "Nested attribute scope escapes are not allowed.")]
    if not isinstance(attr.value, ast.Name):
        return [_unsafe(attr, "attribute_base_not_name", f"{role.capitalize()} attribute access must start from a graph name.")]
    if attr.value.id.startswith("__"):
        return [_unsafe(attr.value, "dunder_name_not_allowed", f"Dunder {role} graph names are not allowed.")]
    return []


def _is_graph_reference_value(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return not node.id.startswith("__")
    if isinstance(node, ast.Attribute):
        return not node.attr.startswith("__") and isinstance(node.value, ast.Name)
    return False


def _validate_graph_reference_value(node: ast.expr) -> list[CompactDiagnostic]:
    if isinstance(node, ast.Name):
        if node.id.startswith("__"):
            return [_unsafe(node, "dunder_name_not_allowed", "Dunder source graph names are not allowed.")]
        return []
    assert isinstance(node, ast.Attribute)
    return _validate_graph_attribute(node, role="source")


def _fold_constant(
    node: ast.expr,
    *,
    env: Mapping[str, Any],
) -> tuple[Any, CompactDiagnostic | None]:
    if isinstance(node, ast.Constant):
        return node.value, None
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id], None
    if isinstance(node, ast.List):
        return _fold_sequence(node, node.elts, list, env=env)
    if isinstance(node, ast.Tuple):
        return _fold_sequence(node, node.elts, tuple, env=env)
    if isinstance(node, ast.Set):
        return _fold_sequence(node, node.elts, set, env=env)
    if isinstance(node, ast.Dict):
        return _fold_dict(node, env=env)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, _SAFE_UNARYOPS):
        value, diagnostic = _fold_constant(node.operand, env=env)
        if diagnostic is not None:
            return None, diagnostic
        try:
            if isinstance(node.op, ast.UAdd):
                return +value, None
            return -value, None
        except Exception:
            return None, _unsafe(node, "constant_fold_failed", "Unary constant expression could not be folded.")
    if isinstance(node, ast.BinOp) and isinstance(node.op, _SAFE_BINOPS):
        left, left_diag = _fold_constant(node.left, env=env)
        if left_diag is not None:
            return None, left_diag
        right, right_diag = _fold_constant(node.right, env=env)
        if right_diag is not None:
            return None, right_diag
        try:
            return _apply_binop(node.op, left, right), None
        except Exception:
            return None, _unsafe(node, "constant_fold_failed", "Binary constant expression could not be folded.")
    if isinstance(node, ast.JoinedStr):
        return None, _unsafe(node, "f_string_not_allowed", "f-string interpolation is not allowed.")
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return None, _unsafe(node, "comprehension_not_allowed", "Comprehensions are not allowed.")
    if isinstance(node, ast.Lambda):
        return None, _unsafe(node, "lambda_not_allowed", "Lambdas are not allowed.")
    if isinstance(node, ast.Call):
        return None, _unsafe(node, "nested_call_not_allowed", "Non-constant calls are not allowed.")
    if isinstance(node, ast.Attribute) and (
        node.attr.startswith("__") or (isinstance(node.value, ast.Name) and node.value.id.startswith("__"))
    ):
        return None, _unsafe(node, "dunder_attribute_not_allowed", "Dunder attributes are not allowed.")
    return None, _unsafe(node, "expression_not_constant", f"{type(node).__name__} is not an allowed constant.")


def _fold_sequence(
    node: ast.expr,
    elements: list[ast.expr],
    factory: Any,
    *,
    env: Mapping[str, Any],
) -> tuple[Any, CompactDiagnostic | None]:
    values: list[Any] = []
    for element in elements:
        value, diagnostic = _fold_constant(element, env=env)
        if diagnostic is not None:
            return None, diagnostic
        values.append(value)
    try:
        return factory(values), None
    except TypeError:
        return None, _unsafe(node, "constant_fold_failed", "Container constant expression could not be folded.")


def _fold_dict(node: ast.Dict, *, env: Mapping[str, Any]) -> tuple[dict[Any, Any] | None, CompactDiagnostic | None]:
    folded: dict[Any, Any] = {}
    for key_node, value_node in zip(node.keys, node.values, strict=True):
        if key_node is None:
            return None, _unsafe(node, "dict_unpack_not_allowed", "Dictionary unpacking is not allowed.")
        key, key_diag = _fold_constant(key_node, env=env)
        if key_diag is not None:
            return None, key_diag
        value, value_diag = _fold_constant(value_node, env=env)
        if value_diag is not None:
            return None, value_diag
        try:
            folded[key] = value
        except TypeError:
            return None, _unsafe(node, "unhashable_dict_key", "Dictionary constant has an unhashable key.")
    return folded, None


def _apply_binop(op: ast.operator, left: Any, right: Any) -> Any:
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        return left / right
    if isinstance(op, ast.FloorDiv):
        return left // right
    if isinstance(op, ast.Mod):
        return left % right
    raise TypeError(type(op).__name__)


def _statement_op_kind(statement: ast.stmt) -> str | None:
    if isinstance(statement, ast.Assign):
        target = statement.targets[0]
        if isinstance(target, ast.Name) and isinstance(statement.value, ast.Call):
            return "node_call"
        if isinstance(target, ast.Attribute):
            return _assignment_op_kind(statement.value, target_attr=target.attr)
        return "assign"
    if isinstance(statement, ast.Delete):
        return "remove_node"
    if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
        if _call_name(statement.value) == "done":
            return "done"
        return "query"
    return None


def _assignment_op_kind(value: ast.expr, *, target_attr: str) -> str:
    if target_attr == "mode":
        return "set_mode"
    if isinstance(value, ast.Constant) and value.value is None:
        return "remove_link"
    if _is_graph_reference_value(value):
        return "upsert_link"
    return "set_node_field"


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _link_origin(link: Any) -> tuple[int | None, int]:
    if isinstance(link, Mapping):
        origin_id = link.get("origin_id")
        origin_slot = link.get("origin_slot", 0)
    elif isinstance(link, (list, tuple)) and len(link) >= 3:
        origin_id = link[1]
        origin_slot = link[2]
    else:
        return None, 0
    if not isinstance(origin_id, int):
        return None, 0
    if not isinstance(origin_slot, int):
        origin_slot = 0
    return origin_id, origin_slot


def _output_slot_name(node: Mapping[str, Any], slot_index: int, schema_provider: Any) -> str | None:
    outputs = node.get("outputs")
    if isinstance(outputs, list) and 0 <= slot_index < len(outputs):
        output = outputs[slot_index]
        if isinstance(output, Mapping):
            name = output.get("name")
            if isinstance(name, str) and name:
                return name
    class_type = str(node.get("type") or node.get("class_type") or "")
    schema = schema_for(schema_provider, class_type)
    output_specs = getattr(schema, "outputs", None) or []
    if 0 <= slot_index < len(output_specs):
        name = getattr(output_specs[slot_index], "name", None)
        if isinstance(name, str) and name:
            return name
    return None


def _find_named_slot(slots: Any, name: str) -> dict[str, Any] | None:
    if not isinstance(slots, list):
        return None
    for item in slots:
        if isinstance(item, Mapping) and item.get("name") == name:
            return dict(item)
    return None


def _normalize_type(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _output_specs(node: Mapping[str, Any], schema_provider: Any, class_type: str) -> list[dict[str, Any]]:
    raw_outputs = node.get("outputs")
    result: list[dict[str, Any]] = []
    if isinstance(raw_outputs, list):
        for index, output in enumerate(raw_outputs):
            if not isinstance(output, Mapping):
                continue
            slot = output.get("slot_index", index)
            try:
                slot_index = int(slot)
            except (TypeError, ValueError):
                slot_index = index
            name = output.get("name")
            result.append(
                {
                    "index": slot_index,
                    "name": str(name) if isinstance(name, str) and name else f"output_{slot_index}",
                    "type": _normalize_type(output.get("type")),
                }
            )
    schema = schema_for(schema_provider, class_type)
    schema_outputs = getattr(schema, "outputs", None) or []
    if not result and schema_outputs:
        for index, output in enumerate(schema_outputs):
            name = getattr(output, "name", None)
            result.append(
                {
                    "index": index,
                    "name": str(name) if isinstance(name, str) and name else f"output_{index}",
                    "type": _normalize_type(getattr(output, "type", None)),
                }
            )
        return result
    by_index = {item["index"]: item for item in result}
    for index, output in enumerate(schema_outputs):
        if index not in by_index:
            by_index[index] = {
                "index": index,
                "name": str(getattr(output, "name", None) or f"output_{index}"),
                "type": _normalize_type(getattr(output, "type", None)),
            }
            continue
        if by_index[index]["type"] is None:
            by_index[index]["type"] = _normalize_type(getattr(output, "type", None))
        if by_index[index]["name"].startswith("output_"):
            name = getattr(output, "name", None)
            if isinstance(name, str) and name:
                by_index[index]["name"] = name
    return [by_index[index] for index in sorted(by_index)]


def _unsafe(
    node: ast.AST,
    code: str,
    message: str,
    *,
    detail: Mapping[str, Any] | None = None,
) -> CompactDiagnostic:
    payload = dict(detail or {})
    lineno = getattr(node, "lineno", None)
    col_offset = getattr(node, "col_offset", None)
    if lineno is not None:
        payload.setdefault("line", lineno)
    if col_offset is not None:
        payload.setdefault("column", col_offset)
    return _diag(code, message, severity="error", detail=payload)


def _uids_for_op(op: EditOp) -> tuple[tuple[str, str], ...]:
    if isinstance(op, SetNodeFieldOp):
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, SetModeOp):
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, RemoveNodeOp):
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, RemoveLinkOp):
        if op.target is None:
            return ()
        return ((op.target.scope_path, op.target.uid),)
    if isinstance(op, UpsertLinkOp):
        return (
            (op.source.scope_path, op.source.uid),
            (op.target.scope_path, op.target.uid),
        )
    return ()


def _done_gate_b_uids_for_ops(ops: tuple[EditOp, ...]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for op in ops:
        pairs.extend(_uids_for_op(op))
        if isinstance(op, AddNodeOp):
            pairs.extend((source.scope_path, source.uid) for source in op.inputs.values())
            if op.anchor is not None:
                if op.anchor.near is not None:
                    pairs.append((op.anchor.near.scope_path, op.anchor.near.uid))
                if op.anchor.between is not None:
                    pairs.extend((target.scope_path, target.uid) for target in op.anchor.between)
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        ordered.append(pair)
    return tuple(ordered)


def _workflow_uid_to_node_id(workflow: VibeWorkflow) -> dict[str, str]:
    result: dict[str, str] = {}
    for node_id, node in workflow.nodes.items():
        uid = getattr(node, "uid", None)
        if isinstance(uid, str) and uid:
            result[uid] = str(node_id)
    return result


def _subset_api_by_node_ids(api: Mapping[str, Any], node_ids: set[str]) -> dict[str, Any]:
    return {
        str(node_id): deepcopy(node)
        for node_id, node in api.items()
        if str(node_id) in node_ids
    }


def _api_edges(api: Mapping[str, Any]) -> set[tuple[str, str, str, int]]:
    edges: set[tuple[str, str, str, int]] = set()
    for target_id, node in api.items():
        if not isinstance(node, Mapping):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, Mapping):
            continue
        for input_name, value in inputs.items():
            if not (isinstance(value, list) and len(value) == 2):
                continue
            source_id, output_slot = value
            if isinstance(output_slot, bool) or not isinstance(output_slot, int):
                continue
            edges.add((str(target_id), str(input_name), str(source_id), int(output_slot)))
    return edges


def _api_one_hop_neighbors(api: Mapping[str, Any], node_ids: set[str]) -> set[str]:
    neighbors: set[str] = set()
    for target_id, _input_name, source_id, _output_slot in _api_edges(api):
        if target_id in node_ids:
            neighbors.add(source_id)
        if source_id in node_ids:
            neighbors.add(target_id)
    return neighbors


def _changed_edge_endpoint_node_ids(
    before_api: Mapping[str, Any],
    after_api: Mapping[str, Any],
) -> set[str]:
    changed = _api_edges(before_api) ^ _api_edges(after_api)
    result: set[str] = set()
    for target_id, _input_name, source_id, _output_slot in changed:
        result.add(target_id)
        result.add(source_id)
    return result


def _node_id_sort_key(node_id: str) -> tuple[int, int | str]:
    text = str(node_id)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)
