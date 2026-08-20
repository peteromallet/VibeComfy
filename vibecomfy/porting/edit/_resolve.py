from __future__ import annotations

import ast
import importlib
import json
import re
import textwrap
import time
from typing import Any, Mapping

from vibecomfy.executor.evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    EvidenceLedgerEntry,
)
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus
from vibecomfy.porting.edit.ops import (
    AnchorRef,
    LinkSourceRef,
    NodeTarget,
)
from vibecomfy.porting.layout.placement import (
    BatchPlacementFacts,
    InferredAnchorHint,
    infer_add_node_anchor_hint,
)
from vibecomfy.identity.codec import to_raw_name
from vibecomfy.porting.authoring_names import class_type_for_constructor_name
from vibecomfy.porting.authoring_surface import input_spec_is_socket_only
from vibecomfy.schema import schema_for, socket_types_compatible

from vibecomfy.porting.edit._session_types import (
    CompactDiagnostic,
    StatementResult,
    _ResolvedAddNodeCall,
    _ResolvedGraphName,
    _ResolvedOutputEndpoint,
    _ResolvedTargetField,
    _ExpandedStatement,
    _diag,
)
from vibecomfy.porting.edit._parse import (
    _AGENT_TOOL_CALL_NAMES,
    _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES,
    _RAW_COORDINATE_HINT_NAMES,
    _call_name,
    _fold_constant,
    _is_graph_reference_value,
    _resolve_vibecomfy_constructor,
    _unsafe,
)
from vibecomfy.porting.edit.grammar import op_kind_for_assignment
from vibecomfy.executor.tool_specs import (
    PHASE_IMPLEMENT,
    PHASE_RESEARCH,
    TOOL_SPEC_BY_NAME,
    TOOL_SPECS,
    invoke_tool,
    phase_allows,
    project_tool_evidence,
    _shorten_query_text,
    _tool_arg_summary,
)
from vibecomfy.porting.edit._ir_utils import (
    _MISSING_WIDGET_VALUE,
    _canonical_input_name_for_class,
    _input_spec_for_field,
    _known_core_input_socket_type,
    _link_origin,
    _normalize_ir_type,
    _output_slot_name,
    _output_specs,
    _resolve_class_type_from_alias,
    _socket_type_from_widget_value,
    _widget_value_for_field,
)
from vibecomfy.porting.edit.apply_field_aliases import field_diagnostics_for_node
from vibecomfy.porting.edit.widget_slots import _canonical_ui_only_widget_field
from vibecomfy.porting.resolution import _find_named_slot

_EXEC_CLASS_TYPE = "vibecomfy.exec"
# Named typed ports (Law 5, batch 4): ``LATENT_0`` / ``IMAGE_1`` — the
# deterministic synthetic names the emitter produces.  Positional
# ``output_N`` aliases are never emitted and no longer resolved.
_TYPED_PORT_RE = re.compile(r"^[A-Z][A-Z0-9_]*_(\d+)\Z")


def _normalize_exec_io_entries(value: Any) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    raw_items: Any
    if isinstance(value, Mapping):
        raw_items = [[name, socket_type] for name, socket_type in value.items()]
    elif isinstance(value, list):
        raw_items = value
    else:
        return entries
    for index, item in enumerate(raw_items):
        name: Any
        socket_type: Any
        if isinstance(item, Mapping):
            name = item.get("name")
            socket_type = item.get("type")
        elif isinstance(item, (list, tuple)) and len(item) >= 1:
            name = item[0]
            socket_type = item[1] if len(item) >= 2 else None
        else:
            continue
        clean_name = str(name or f"value_{index}").strip() or f"value_{index}"
        clean_type = str(socket_type or "*").strip() or "*"
        entries.append((clean_name, clean_type))
    return entries


def _normalize_exec_io(value: Any) -> dict[str, list[tuple[str, str]]] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, Mapping):
        return None
    return {
        "inputs": _normalize_exec_io_entries(value.get("inputs")),
        "outputs": _normalize_exec_io_entries(value.get("outputs")),
    }


def _infer_exec_output_names_from_source(source: Any) -> list[tuple[str, str]]:
    """Best-effort parse of a vibecomfy.exec source body for `return {...}` keys."""
    if not isinstance(source, str) or not source.strip():
        return []
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return []
    keys: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        for key in value.keys:
            name: str | None = None
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                name = key.value
            elif hasattr(ast, "Str") and isinstance(key, ast.Str):  # pragma: no cover - py<3.8
                name = key.s
            if name:
                keys.append((name, "*"))
    return keys


def _infer_exec_io(
    source: Any,
    linked_inputs: Mapping[str, LinkSourceRef],
) -> dict[str, list[tuple[str, str]]] | None:
    """Infer a minimal exec `io` contract from source return keys and wired inputs.

    This is a fallback for agents that omit `io` or leave it empty.  Output names
    are taken from the source body's `return {...}` keys, and input names mirror
    the physical slot names the agent actually wired (``in_0``, ``in_1``, ...),
    which keeps the runtime wrapper signature compatible with the source.
    """
    outputs = _infer_exec_output_names_from_source(source)
    inputs: list[tuple[str, str]] = []
    for slot_name in sorted(linked_inputs.keys()):
        if slot_name.startswith("in_"):
            inputs.append((slot_name, "*"))
    if not inputs and not outputs:
        return None
    return {"inputs": inputs, "outputs": outputs}


def _exec_semantic_slot_name(
    class_type: str,
    io_value: Any,
    slot_name: str,
    *,
    direction: str,
) -> str:
    if class_type != _EXEC_CLASS_TYPE or not isinstance(slot_name, str) or not slot_name:
        return slot_name
    normalized = _normalize_exec_io(io_value)
    if normalized is None:
        return slot_name
    entries = normalized["inputs" if direction == "input" else "outputs"]
    for index, (semantic_name, _socket_type) in enumerate(entries):
        if semantic_name == slot_name:
            prefix = "in" if direction == "input" else "out"
            return f"{prefix}_{index}"
    return slot_name


def _exec_semantic_slot_name_for_node(
    node: Mapping[str, Any],
    class_type: str,
    slot_name: str,
    *,
    direction: str,
) -> str:
    return _exec_semantic_slot_name(
        class_type,
        _widget_value_for_field(node, class_type, "io"),
        slot_name,
        direction=direction,
    )


def _format_compact_sequence(values: Any, *, max_items: int = 16, max_chars: int = 420) -> str:
    if not isinstance(values, (list, tuple)):
        return ""
    rendered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in rendered:
            rendered.append(text)
        if len(rendered) >= max_items:
            break
    suffix = ""
    if len(values) > len(rendered):
        suffix = f", and {len(values) - len(rendered)} more"
    return _shorten_query_text(", ".join(rendered) + suffix, max_chars=max_chars)


# ── I01: Wave-A agent tool surface (budgets + F01 ledger) ────────────────────
# The batch protocol admits ten named agent-invoked tool calls
# (_AGENT_TOOL_CALL_NAMES).  Each call is resolved here: argument folding and
# shape validation, effort-budget enforcement (typed refusal, evidence
# preserved), invocation of the Wave-A tool module, and recording of a compact
# F01 EvidenceLedger entry plus evidence artifacts on the per-session
# _AgentToolSurface.  Tool output crosses turns ONLY as ledger entries and
# evidence IDs — never as raw result bodies.

# Effort budgets (I01): 3 searches, 6 fetches, 1 registry batch, ~90s phase
# deadline.  These constants are the single source of truth for the enforceable
# budget; the prompt prose in provider.build_batch_messages mirrors them.
TOOL_SEARCH_BUDGET = 3
TOOL_FETCH_BUDGET = 6
TOOL_REGISTRY_BUDGET = 1
TOOL_PHASE_DEADLINE_SECONDS = 90.0

# The per-tool argument contract and budget class live ONCE in the declarative
# ToolSpec registry (_tool_specs.TOOL_SPECS): ``spec.positional_names`` /
# ``spec.keywords`` / ``spec.required`` describe the call surface and
# ``spec.budget_class`` ("search"/"fetch"/"registry"/None) the effort pool.
# Nothing below re-declares a tool.

_TOOL_REFUSAL_MESSAGES: dict[str, str] = {
    "tool_search_budget_exhausted": (
        f"Search budget exhausted ({TOOL_SEARCH_BUDGET} searches per session); "
        "further search tools are refused. Gathered evidence is preserved in the ledger."
    ),
    "tool_fetch_budget_exhausted": (
        f"Fetch budget exhausted ({TOOL_FETCH_BUDGET} fetches per session); "
        "further fetch tools are refused. Gathered evidence is preserved in the ledger."
    ),
    "tool_registry_budget_exhausted": (
        f"Registry batch budget exhausted ({TOOL_REGISTRY_BUDGET} registry lookup "
        "per session). Gathered evidence is preserved in the ledger."
    ),
    "tool_deadline_exceeded": (
        f"Tool-phase deadline exceeded (about {TOOL_PHASE_DEADLINE_SECONDS:g}s); "
        "further tool calls are refused. Gathered evidence is preserved in the ledger."
    ),
    "tool_phase_not_allowed": (
        "This tool is not available in the current pipeline phase. Research phase "
        "tools and implement phase tools are strictly partitioned; use only the "
        "tools documented for your phase and synthesize from the ledger."
    ),
}


class _AgentToolSurface:
    """Per-session effort budget plus F01 evidence ledger for agent tool calls.

    Created lazily on the first tool-call resolution and reused for the whole
    session (every model turn of one batch-REPL run), so budgets accumulate
    and the ledger persists across turns.  The ledger holds compact
    :class:`EvidenceLedgerEntry` values; full bodies live behind stable
    evidence IDs in :attr:`artifacts` and never enter the prompt.
    """

    def __init__(
        self,
        *,
        search_budget: int | None = None,
        fetch_budget: int | None = None,
        registry_budget: int | None = None,
        deadline_seconds: float | None = None,
        deadline: float | None = None,
    ) -> None:
        self.searches_remaining = int(
            search_budget if search_budget is not None else TOOL_SEARCH_BUDGET
        )
        self.fetches_remaining = int(
            fetch_budget if fetch_budget is not None else TOOL_FETCH_BUDGET
        )
        self._registry_remaining = int(
            registry_budget if registry_budget is not None else TOOL_REGISTRY_BUDGET
        )
        if deadline is None:
            deadline = time.monotonic() + float(
                deadline_seconds if deadline_seconds is not None else TOOL_PHASE_DEADLINE_SECONDS
            )
        self.deadline = float(deadline)
        self.ledger: EvidenceLedger = EvidenceLedger()
        self.artifacts: dict[str, EvidenceArtifact] = {}

    @property
    def registry_remaining(self) -> int:
        return self._registry_remaining

    @property
    def deadline_exceeded(self) -> bool:
        return time.monotonic() > self.deadline

    def snapshot(self) -> dict[str, Any]:
        """Compact budget + evidence accounting (JSON-safe, for statement detail)."""
        return {
            "searches_remaining": self.searches_remaining,
            "fetches_remaining": self.fetches_remaining,
            "registry_remaining": self.registry_remaining,
            "deadline_exceeded": self.deadline_exceeded,
            "ledger_entries": len(self.ledger.entries),
            "evidence_ids": len(self.artifacts),
        }

    def ledger_evidence_ids(self, *, cap: int = 20) -> tuple[str, ...]:
        return tuple(self.ledger.evidence_ids[:cap])

    def append(self, entry: dict[str, Any], artifacts: Mapping[str, EvidenceArtifact]) -> None:
        """Record one ledger entry + its evidence artifacts (first-seen wins)."""
        normalized = EvidenceLedgerEntry.from_dict(entry)
        self.ledger = EvidenceLedger(entries=self.ledger.entries + (normalized,))
        for evidence_id, artifact in artifacts.items():
            if evidence_id not in self.artifacts:
                self.artifacts[evidence_id] = artifact


def _session_phase(session: Any) -> str | None:
    """Resolve the session's pipeline phase for tool-call enforcement.

    The live batch REPL sets ``session.research_only`` for every route
    (``edit_batch_repl``), so the phase is always known there.  ``None``
    (offline/standalone validation without a phase marker) is permissive.
    """
    research_only = getattr(session, "research_only", None)
    if research_only is True:
        return PHASE_RESEARCH
    if research_only is False:
        return PHASE_IMPLEMENT
    return None


def _validate_tool_call_shape(
    call_name: str,
    args: Mapping[str, Any],
    kwargs: Mapping[str, Any],
) -> list[CompactDiagnostic]:
    """Shape-check one tool call (arity, allowed keywords, required args)."""
    spec = TOOL_SPEC_BY_NAME[call_name]
    diagnostics: list[CompactDiagnostic] = []
    if len(args) > len(spec.positional_names):
        diagnostics.append(
            _diag(
                "tool_too_many_args",
                f"{call_name}(...) accepts at most {len(spec.positional_names)} "
                "positional argument(s).",
                severity="error",
            )
        )
    unknown = sorted(set(kwargs) - spec.keywords)
    if unknown:
        diagnostics.append(
            _diag(
                "tool_unknown_keyword",
                f"{call_name}(...) does not accept keyword(s): {', '.join(unknown)}.",
                severity="error",
                detail={"keyword": unknown, "allowed": sorted(spec.keywords)},
            )
        )
    duplicated = sorted(set(kwargs) & set(args))
    if duplicated:
        diagnostics.append(
            _diag(
                "tool_arg_duplicated",
                f"{call_name}(...) argument(s) passed both positionally and by keyword: "
                + ", ".join(duplicated)
                + ".",
                severity="error",
            )
        )
    missing = sorted(set(spec.required) - set(args) - set(kwargs))
    if missing:
        diagnostics.append(
            _diag(
                "tool_arg_required",
                f"{call_name}(...) requires argument(s): {', '.join(missing)}.",
                severity="error",
                detail={"required": list(spec.required)},
            )
        )
    return diagnostics


def _consume_tool_budget(
    spec: ToolSpec,
    surface: _AgentToolSurface,
) -> tuple[str | None, Any]:
    """Consume the tool's budget class; return (refusal_code, payload).

    A non-None ``refusal_code`` refuses the call (typed) and consumes nothing.
    ``payload`` is a one-shot ``RegistryLookupBudget`` for ``registry_lookup``
    (already consumed here); None for every other tool.
    """
    if surface.deadline_exceeded:
        return "tool_deadline_exceeded", None
    budget_class = spec.budget_class
    if budget_class is None:
        return None, None
    if budget_class == "search":
        if surface.searches_remaining <= 0:
            return "tool_search_budget_exhausted", None
        surface.searches_remaining -= 1
        return None, None
    if budget_class == "fetch":
        if surface.fetches_remaining <= 0:
            return "tool_fetch_budget_exhausted", None
        surface.fetches_remaining -= 1
        return None, None
    if surface.registry_remaining <= 0:
        return "tool_registry_budget_exhausted", None
    surface._registry_remaining -= 1
    lookup_tools = importlib.import_module("vibecomfy.executor.lookup_tools")
    return None, lookup_tools.RegistryLookupBudget(remaining=1)


def _format_tool_phase_refusal_output(
    call_name: str, args: Mapping[str, Any], phase: str, surface: _AgentToolSurface
) -> str:
    summary = _tool_arg_summary(args)
    allowed = ", ".join(sorted(spec.name for spec in TOOL_SPECS if spec.phase == phase))
    return (
        f"{call_name}({summary}) — refused: tool_phase_not_allowed\n"
        f"  {_TOOL_REFUSAL_MESSAGES['tool_phase_not_allowed']}\n"
        f"  Tools available in the {phase} phase: {allowed}.\n"
        f"  Gathered evidence is preserved: {surface.snapshot()['ledger_entries']} ledger "
        f"entry/entries — synthesize from the ledger and call done()."
    )


def _format_tool_refusal_output(
    call_name: str, args: Mapping[str, Any], code: str, surface: _AgentToolSurface
) -> str:
    summary = _tool_arg_summary(args)
    budget = surface.snapshot()
    return (
        f"{call_name}({summary}) — refused: {code}\n"
        f"  {_TOOL_REFUSAL_MESSAGES[code]}\n"
        f"  Budget now: {budget['searches_remaining']} search(es), "
        f"{budget['fetches_remaining']} fetch(es), {budget['registry_remaining']} registry "
        f"batch(es) remaining; deadline exceeded: {budget['deadline_exceeded']}.\n"
        f"  Gathered evidence is preserved: {budget['ledger_entries']} ledger entry/entries, "
        f"{budget['evidence_ids']} evidence id(s) — synthesize from the ledger and call done()."
    )


class _ResolveMixin:
    """Symbolic-name resolution methods — the named M4 seam."""

    def _uid_for_scope(self, scope_path: str, class_type: str) -> str:
        """Best-effort uid lookup for a newly added node from the retained IR."""
        workflow = getattr(self, "workflow", None)
        nodes = list((getattr(workflow, "nodes", None) or {}).values())
        for node in reversed(nodes):
            if str(getattr(node, "class_type", "") or "") != class_type:
                continue
            uid = str(getattr(node, "uid", "") or "")
            if uid and uid in self.name_by_uid:
                return uid
        return ""

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
            call_name = _call_name(statement.value)
            if call_name == "done":
                return StatementResult(
                    statement_index=item.statement_index,
                    source=source,
                    ok=True,
                    landed=False,
                    op_kind="done",
                )
            return self._resolve_query_statement(
                statement_index=item.statement_index,
                source=source,
                call=statement.value,
                env=env,
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
                    op_kind=op_kind_for_assignment(statement.value, target_attr=target.attr),
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
                        op_kind=op_kind_for_assignment(rhs, target_attr=target.attr),
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
                op_kind=(
                    "set_mode" if target.attr == "mode"
                    else "set_node_field"
                ),
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

    def _resolve_query_statement(
        self,
        *,
        statement_index: int,
        source: str,
        call: ast.Call,
        env: Mapping[str, Any],
    ) -> StatementResult:
        call_name = _call_name(call)
        if call_name not in {"search", "research", "python"} and call_name not in _AGENT_TOOL_CALL_NAMES:
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "unsupported_query_call",
                        "Only search(...), python(), done(), and the ten "
                        "agent tool calls (hivemind_search, hivemind_get, registry_lookup, "
                        "ready_template_list, ready_template_load, rank_edit_targets, "
                        "suggest_seed_nodes, layout_hints, web_search) are supported as "
                        "top-level query calls.",
                        severity="error",
                        detail={"call": call_name},
                    ),
                ),
            )

        if call_name in _AGENT_TOOL_CALL_NAMES:
            return self._resolve_tool_call_statement(
                statement_index=statement_index,
                source=source,
                call=call,
                env=env,
                call_name=call_name,
            )

        if call_name == "python":
            diagnostics: list[CompactDiagnostic] = []
            if call.args:
                diagnostics.append(
                    _diag("python_arguments_not_allowed", "python() does not accept arguments.", severity="error")
                )
            for keyword in call.keywords:
                if keyword.arg is None:
                    diagnostics.append(
                        _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                    )
                else:
                    diagnostics.append(
                        _diag(
                            "unsupported_python_keyword",
                            f"python() does not accept keyword {keyword.arg!r}.",
                            severity="error",
                            detail={"keyword": keyword.arg},
                        )
                    )
            if diagnostics:
                return StatementResult(
                    statement_index=statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind="query",
                    diagnostics=tuple(diagnostics),
                    detail={"query": "python"},
                )
            try:
                output = self.python()
            except Exception as exc:  # noqa: BLE001 - report query failures in-band
                return StatementResult(
                    statement_index=statement_index,
                    source=source,
                    ok=False,
                    landed=False,
                    op_kind="query",
                    diagnostics=(
                        _diag(
                            "python_query_failed",
                            f"python() failed: {exc}",
                            severity="error",
                        ),
                    ),
                    detail={"query": "python"},
                )
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="query",
                detail={"query": "python", "query_output": str(output)},
            )

        if call_name == "research":
            # Wave D: the deterministic research engine is gone; the agent-owned
            # research surface is the named tool calls.  This legacy statement is
            # an unconditional typed refusal — no argument validation, no source
            # machinery.  A best-effort constant fold keeps the query in the
            # detail for consumers that pinned the legacy refusal shape.
            query: str | None = None
            if call.args:
                value, _ = _fold_constant(call.args[0], env=env)
                if isinstance(value, str) and value.strip():
                    query = value.strip()
            detail: dict[str, Any] = {"query": "research"}
            if query is not None:
                detail["research_query"] = query
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "research_query_failed",
                        "research(...) is no longer supported: the deterministic research "
                        "engine was removed (agent-judgment rework). Use the named tool "
                        "statements instead: hivemind_search/hivemind_get/registry_lookup/"
                        "node_schema/ready_template_list/ready_template_load/"
                        "rank_edit_targets/suggest_seed_nodes/layout_hints/web_search.",
                        severity="error",
                    ),
                ),
                detail=detail,
            )

        allowed = {"focus_types", "compatible_input_type", "compatible_output_type", "formatted"}
        kwargs: dict[str, Any] = {}
        diagnostics: list[CompactDiagnostic] = []
        for keyword in call.keywords:
            if keyword.arg is None:
                diagnostics.append(
                    _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                )
                continue
            if keyword.arg not in allowed:
                diagnostics.append(
                    _diag(
                        "unsupported_search_keyword",
                        f"search(...) does not accept keyword {keyword.arg!r}.",
                        severity="error",
                        detail={"keyword": keyword.arg, "allowed": sorted(allowed)},
                    )
                )
                continue
            value, diagnostic = _fold_constant(keyword.value, env=env)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
                continue
            kwargs[keyword.arg] = value
        if diagnostics:
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=tuple(diagnostics),
                detail={"query": "search"},
            )

        try:
            output = self.search(
                focus_types=kwargs.get("focus_types"),
                compatible_input_type=kwargs.get("compatible_input_type"),
                compatible_output_type=kwargs.get("compatible_output_type"),
                formatted=True,
                in_graph_nodes=getattr(self, "workflow", None),
            )
        except Exception as exc:  # noqa: BLE001 - report query failures in-band
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "search_query_failed",
                        f"search(...) failed: {exc}",
                        severity="error",
                    ),
                ),
                detail={"query": "search"},
            )

        output_text = str(output)
        focus_types = kwargs.get("focus_types")
        missing_classes: list[str] = []
        if isinstance(focus_types, (list, tuple)):
            get_schema = getattr(self.schema_provider, "get_schema", None)
            if callable(get_schema):
                for raw_class_type in focus_types:
                    class_type = str(raw_class_type or "").strip()
                    if (
                        class_type
                        and class_type not in missing_classes
                        and get_schema(class_type) is None
                    ):
                        missing_classes.append(class_type)
        if (
            missing_classes
            and "No node signature found" in output_text
        ):
            exact_focus = ", ".join(missing_classes)
            output_text += (
                "\nThis local schema miss does not prove the named external workflow "
                f"or model family is unavailable. Missing class name(s): {exact_focus}. "
                "Do not broaden this into guessed branded constructors. Use workflow "
                "precedent as pattern evidence, but only instantiate classes that appear "
                "in the current signature catalog or another authoring surface exposed "
                "by this edit session."
            )

        detail: dict[str, Any] = {"query": "search", "query_output": output_text}
        if missing_classes:
            # Exact focus-type misses are structured proof from the active
            # schema provider.  Response shaping may use this only when the
            # user named the same class and the batch ends in a real choice.
            detail["missing_classes"] = missing_classes
        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="query",
            detail=detail,
        )

    def _resolve_tool_call_statement(
        self,
        *,
        statement_index: int,
        source: str,
        call: ast.Call,
        env: Mapping[str, Any],
        call_name: str,
    ) -> StatementResult:
        """Resolve one agent tool call (I01/C01).

        Folds arguments (constants only — parse already validated), shape
        checks the declarative :class:`ToolSpec`, enforces the per-phase
        allowlist (research vs implement — a tool outside the session's phase
        is a typed refusal, never a leak), enforces the effort budget (typed
        refusal, evidence preserved), invokes the tool through its registered
        handler, and records a compact F01 ledger entry plus evidence
        artifacts on the session's :class:`_AgentToolSurface`.  The statement
        detail carries the typed status, ledger entry, budget snapshot, and a
        compact current-turn digest — never the raw result body.
        """
        spec = TOOL_SPEC_BY_NAME[call_name]
        positional_names = spec.positional_names
        args: dict[str, Any] = {}
        kwargs: dict[str, Any] = {}
        diagnostics: list[CompactDiagnostic] = []
        for index, arg_node in enumerate(call.args):
            if index >= len(positional_names):
                diagnostics.append(
                    _diag(
                        "tool_too_many_args",
                        f"{call_name}(...) accepts at most {len(positional_names)} "
                        "positional argument(s).",
                        severity="error",
                    )
                )
                break
            value, diagnostic = _fold_constant(arg_node, env=env)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
                continue
            args[positional_names[index]] = value
        for keyword in call.keywords:
            if keyword.arg is None:
                diagnostics.append(
                    _diag("kwargs_unpack_not_allowed", "**kwargs unpacking is not allowed.", severity="error")
                )
                continue
            value, diagnostic = _fold_constant(keyword.value, env=env)
            if diagnostic is not None:
                diagnostics.append(diagnostic)
                continue
            kwargs[keyword.arg] = value
        diagnostics.extend(_validate_tool_call_shape(call_name, args, kwargs))
        if diagnostics:
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=tuple(diagnostics),
                detail={"query": call_name, "tool_call": call_name},
            )
        merged = dict(args)
        merged.update(kwargs)
        surface = self._agent_tool_surface()
        phase = _session_phase(self)
        if phase is not None and not phase_allows(phase, call_name):
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=True,
                landed=False,
                op_kind="query",
                detail={
                    "query": call_name,
                    "tool_call": call_name,
                    "tool_status": ToolStatus.REFUSED.value,
                    "tool_code": "tool_phase_not_allowed",
                    "tool_message": _TOOL_REFUSAL_MESSAGES["tool_phase_not_allowed"],
                    "tool_evidence_ids": list(surface.ledger_evidence_ids()),
                    "ledger_entry": None,
                    "tool_budget": surface.snapshot(),
                    "query_output": _format_tool_phase_refusal_output(
                        call_name, merged, phase, surface
                    ),
                },
            )
        refusal_code, budget_payload = _consume_tool_budget(spec, surface)
        if refusal_code is not None:
            return self._tool_refusal_statement(
                statement_index=statement_index,
                source=source,
                call_name=call_name,
                args=merged,
                surface=surface,
                refusal_code=refusal_code,
            )
        try:
            result = invoke_tool(spec, self, merged, budget_payload)
        except Exception as exc:  # noqa: BLE001 - report tool failures in-band
            return StatementResult(
                statement_index=statement_index,
                source=source,
                ok=False,
                landed=False,
                op_kind="query",
                diagnostics=(
                    _diag(
                        "tool_call_failed",
                        f"{call_name}() failed: {exc}",
                        severity="error",
                    ),
                ),
                detail={"query": call_name, "tool_call": call_name},
            )
        artifacts, entry, digest = project_tool_evidence(spec, merged, result, self)
        surface.append(entry, artifacts)
        code = result.diagnostics[0].code if result.diagnostics else None
        message = result.diagnostics[0].message if result.diagnostics else ""
        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="query",
            detail={
                "query": call_name,
                "tool_call": call_name,
                "tool_status": result.status.value,
                "tool_code": code,
                "tool_message": message,
                "tool_evidence_ids": list(entry["evidence_ids"]),
                "ledger_entry": entry,
                "tool_budget": surface.snapshot(),
                "query_output": digest,
            },
        )

    def _tool_refusal_statement(
        self,
        *,
        statement_index: int,
        source: str,
        call_name: str,
        args: Mapping[str, Any],
        surface: _AgentToolSurface,
        refusal_code: str,
    ) -> StatementResult:
        """Typed, non-error refusal for an exhausted budget/deadline.

        ``ok=True`` with no diagnostics so a refusal never counts as a failed
        turn or triggers consecutive-error stops; the typed state rides in the
        detail (and query_output) and gathered evidence is preserved.
        """
        return StatementResult(
            statement_index=statement_index,
            source=source,
            ok=True,
            landed=False,
            op_kind="query",
            detail={
                "query": call_name,
                "tool_call": call_name,
                "tool_status": ToolStatus.REFUSED.value,
                "tool_code": refusal_code,
                "tool_message": _TOOL_REFUSAL_MESSAGES[refusal_code],
                "tool_evidence_ids": list(surface.ledger_evidence_ids()),
                "ledger_entry": None,
                "tool_budget": surface.snapshot(),
                "query_output": _format_tool_refusal_output(call_name, args, refusal_code, surface),
            },
        )

    def _agent_tool_surface(self) -> _AgentToolSurface:
        """Lazily create the per-session tool surface on first tool call."""
        surface = getattr(self, "_tool_surface", None)
        if surface is None:
            surface = _AgentToolSurface()
            self._tool_surface = surface
        return surface

    def _mark_name_unbound(self, name: str) -> None:
        self.unbound_names.add(name)

    def _register_transient_name(self, name: str, uid: str) -> None:
        """Transient within-batch name registration (Law 5, batch 4).

        Bridges an add-node statement's ``target_name`` to its minted uid
        for LATER statements in the SAME batch.  Nothing is written to the
        ledger/working_ui and the pure naming function never consults this
        index, so no stored binding and no session lock exists.
        """
        self._transient_name_index[name] = uid
        self._transient_uid_index[uid] = name
        self.unbound_names.discard(name)

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
        class_type, dotted_vibecomfy = _resolve_vibecomfy_constructor(func)
        if dotted_vibecomfy and class_type not in _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES:
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface. Use vibecomfy.exec for executable Python code nodes.",
                )
            ]
        if class_type is None:
            return None, [_unsafe(func, "call_target_not_name", "Node construction calls must target a simple class name.")]
        if class_type.startswith("vibecomfy.") and class_type not in _ALLOWED_VIBECOMFY_CONSTRUCTION_CLASS_TYPES:
            return None, [
                _unsafe(
                    func,
                    "intent_class_construction_not_allowed",
                    "Editor-only vibecomfy.* intent classes cannot be constructed from the Python edit surface. Use vibecomfy.exec for executable Python code nodes.",
                )
            ]

        resolved_class_type = _resolve_class_type_from_alias(class_type, self.schema_provider)
        if resolved_class_type is not None and resolved_class_type != class_type:
            class_type = resolved_class_type
        schema = schema_for(self.schema_provider, class_type)
        if schema is None:
            raw_class_type = class_type_for_constructor_name(self.schema_provider, class_type)
            if raw_class_type is not None:
                class_type = raw_class_type
                schema = schema_for(self.schema_provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        fake_target_node = _ResolvedGraphName(
            name=target_name,
            uid="<pending>",
            scope_path="",
            node={},
            class_type=class_type,
        )
        exec_io_value: Any = None
        if class_type == _EXEC_CLASS_TYPE:
            for keyword in call.keywords:
                if keyword.arg != "io":
                    continue
                exec_io_value, _ = _fold_constant(keyword.value, env=env)
                break
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
                if relation not in {"near", "right_of", "left_of", "below"}:
                    issues.append(
                        _unsafe(
                            keyword.value,
                            "invalid_relation_hint",
                            "relation= must be one of 'near', 'right_of', 'left_of', or 'below' for Python add-node statements.",
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
            if class_type == _EXEC_CLASS_TYPE:
                name = _exec_semantic_slot_name(
                    class_type,
                    exec_io_value,
                    name,
                    direction="input",
                )
            else:
                name = _canonical_input_name_for_class(schema_inputs, class_type, name)
            if _is_graph_reference_value(keyword.value):
                socket_type = _normalize_ir_type(getattr(_input_spec_for_field(schema_inputs, name), "type", None))
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
            spec = _input_spec_for_field(schema_inputs, name)
            if input_spec_is_socket_only(spec):
                issues.append(
                    _diag(
                        "socket_input_not_literal_widget",
                        f"{class_type}.{name} is an input socket, not a widget; connect a source node instead.",
                        severity="error",
                        detail={
                            "class_type": class_type,
                            "input": name,
                            "target_name": target_name,
                            "input_type": getattr(spec, "type", None),
                        },
                    )
                )
                continue
            literal_fields[name] = literal_value

        if class_type == _EXEC_CLASS_TYPE:
            normalized_io = _normalize_exec_io(exec_io_value)
            if normalized_io is None or (not normalized_io["inputs"] and not normalized_io["outputs"]):
                inferred_io = _infer_exec_io(literal_fields.get("source"), linked_inputs)
                if inferred_io is not None:
                    literal_fields["io"] = {
                        "inputs": [[name, socket_type] for name, socket_type in inferred_io["inputs"]],
                        "outputs": [[name, socket_type] for name, socket_type in inferred_io["outputs"]],
                    }

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
            target_has_any_link=self._target_has_any_link,
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
        return AnchorRef(relation=hint.relation, near=NodeTarget(near.scope_path, near.uid))

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
        workflow = getattr(self, "workflow", None)
        if workflow is None:
            return None
        target_id = str(getattr(target.node, "id", "") or "")
        for edge in getattr(workflow, "edges", ()) or ():
            if str(getattr(edge, "to_node", "") or "") != target_id:
                continue
            if str(getattr(edge, "to_input", "") or "") != target_field:
                continue
            source = workflow.nodes.get(str(getattr(edge, "from_node", "") or ""))
            if source is None:
                return None
            return LinkSourceRef(
                target.scope_path,
                str(getattr(source, "uid", "") or ""),
                getattr(edge, "from_output", ""),
            )
        return None

    def _target_has_any_link(self, target_name: str) -> bool:
        target = self._resolve_graph_name_soft(target_name)
        if target is None:
            return False
        workflow = getattr(self, "workflow", None)
        if workflow is None:
            return False
        target_id = str(getattr(target.node, "id", "") or "")
        return any(
            str(getattr(edge, "to_node", "") or "") == target_id
            for edge in getattr(workflow, "edges", ()) or ()
        )

    def _node_by_id(self, scope_path: str, node_id: int) -> Any | None:
        workflow = getattr(self, "workflow", None)
        if workflow is None:
            return None
        return (getattr(workflow, "nodes", None) or {}).get(str(node_id))

    @staticmethod
    def _dependency_cause(statement: StatementResult) -> str | None:
        for diagnostic in statement.diagnostics:
            if diagnostic.code == "unbound_graph_name":
                name = str(diagnostic.detail.get("name", "?"))
                return f"Statement depends on graph name {name!r} whose add-node statement did not land."
        return None

    def _uid_if_present(self, name: str) -> str | None:
        """Return *name* when it is already a live node uid."""
        if not name:
            return None
        workflow = getattr(self, "workflow", None)
        nodes = getattr(workflow, "nodes", None) or {}
        for node in nodes.values():
            if str(getattr(node, "uid", "") or "") == name:
                return name
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
            # Batch 4 (Law 5): transient within-batch registration for a
            # node minted by an earlier add-node statement in this batch.
            uid = self._transient_name_index.get(name)
        if uid is None:
            # Designed identity fallback: the uid comment is always a valid
            # address.  This is not a session lock — the uid is the IR key.
            uid = self._uid_if_present(name)
        if uid is None:
            return None, [
                _diag(
                    "unknown_graph_name",
                    f"Unknown graph name {name!r}. Render the session again if the canvas changed.",
                    severity="error",
                    detail={"name": name},
                )
            ]
        workflow = getattr(self, "workflow", None)
        ir_node = None
        for node in (getattr(workflow, "nodes", None) or {}).values():
            if str(getattr(node, "uid", "") or "") == uid:
                ir_node = node
                break
        if ir_node is None:
            return None, [
                _diag(
                    "stale_graph_name",
                    f"Graph name {name!r} still points at uid {uid!r}, but that uid is no longer present.",
                    severity="error",
                    detail={"name": name, "uid": uid},
                )
            ]
        class_type = str(getattr(ir_node, "class_type", "") or "")
        return _ResolvedGraphName(name=name, uid=uid, scope_path="", node=ir_node, class_type=class_type), []

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
        field_name = _exec_semantic_slot_name_for_node(
            node_ref.node,
            node_ref.class_type,
            target.attr,
            direction="input",
        )
        schema = schema_for(self.schema_provider, node_ref.class_type)
        schema_inputs = getattr(schema, "inputs", {}) or {}
        field_name = _canonical_input_name_for_class(schema_inputs, node_ref.class_type, field_name)
        ui_only_alias = _canonical_ui_only_widget_field(
            node_ref.node,
            field_name,
            schema_provider=self.schema_provider,
        )
        if ui_only_alias is not None:
            field_name = ui_only_alias[0]
        schema_input = _input_spec_for_field(schema_inputs, field_name)
        raw_input = _find_named_slot(node_ref.node.get("inputs"), field_name)
        widget_value = _widget_value_for_field(
            node_ref.node,
            node_ref.class_type,
            field_name,
            schema_provider=self.schema_provider,
        )
        if (
            raw_input is None
            and schema_input is None
            and widget_value is _MISSING_WIDGET_VALUE
            and field_name not in {"mode", "title"}
        ):
            detail: dict[str, Any] = {"name": node_ref.name, "uid": node_ref.uid, "field": target.attr}
            try:
                fd = field_diagnostics_for_node(
                    node_ref.node,
                    node_ref.class_type,
                    schema_inputs,
                    schema_provider=self.schema_provider,
                )
                if fd.get("valid_fields"):
                    detail["valid_fields"] = fd["valid_fields"]
            except Exception:
                pass
            return None, [
                _diag(
                    "unknown_target_field",
                    f"{node_ref.class_type} has no editable field or input named {target.attr!r}.",
                    severity="error",
                    detail=detail,
                )
            ]
        socket_type = _normalize_ir_type(
            getattr(schema_input, "type", None) if schema_input is not None else raw_input.get("type") if isinstance(raw_input, Mapping) else None
        )
        if socket_type is None and widget_value is not _MISSING_WIDGET_VALUE:
            socket_type = _socket_type_from_widget_value(widget_value)
        if socket_type is None or socket_type == "UNKNOWN":
            socket_type = _known_core_input_socket_type(node_ref.class_type, field_name) or socket_type
        return _ResolvedTargetField(node=node_ref, field_name=field_name, socket_type=socket_type), []

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
        slot_attr = _exec_semantic_slot_name_for_node(
            node_ref.node,
            node_ref.class_type,
            slot_attr,
            direction="output",
        )
        raw_outputs = _output_specs(node_ref.node, self.schema_provider, node_ref.class_type)
        raw_name_map = {item["name"]: item["name"] for item in raw_outputs if item["name"]}
        try:
            raw_slot = slot_attr if slot_attr in raw_name_map else to_raw_name(slot_attr, context=raw_name_map)
        except (KeyError, ValueError):
            raw_slot = None
        if raw_slot is None:
            port_match = _TYPED_PORT_RE.fullmatch(slot_attr)
            if port_match is not None:
                port_index = int(port_match.group(1))
                by_index = {item["index"]: item for item in raw_outputs}
                item = by_index.get(port_index)
                if item is not None:
                    raw_slot = item["name"] or f"output_{port_index}"
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
