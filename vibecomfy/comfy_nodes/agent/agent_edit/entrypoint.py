from __future__ import annotations

import dataclasses
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from ..audit import (
    write_allocation_failure_audit,
    write_audit,
    write_json_artifact,
)
from ..contracts import (
    FailureEnvelope,
    FailureKind,
    StageResult,
    TurnContext,
    classify_failure,
    failure_envelope,
)
from .client import DeepSeekClient
from .runtime_schema import (
    _build_object_info_in_process,
    _can_attempt_local_additive_revise,
    _default_runtime_schema_provider,
)
from .state import AgentEditState
from .stages.agent_delta import _edit_facade
from .websocket import _emit_agent_edit_turn_event
from vibecomfy.executor.contracts import RevisionEvidence

_WARNED_LEGACY_CONTRACTS: set[str] = set()
_WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS: set[str] = set()


def _resolve_edit_attr(name: str) -> Any:
    return getattr(_edit_facade(), name)

def _duration_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))
def _read_only_discovery_turn_count(state: AgentEditState) -> int:
    count = 0
    for turn in state.batch_turns:
        statements = turn.get("statements")
        if not isinstance(statements, list) or not statements:
            continue
        landed = turn.get("landed_op_count")
        if isinstance(landed, int) and landed > 0:
            continue
        if all(
            isinstance(statement, Mapping)
            and str(statement.get("op_kind") or "") == "query"
            for statement in statements
        ):
            count += 1
    return count
def _port_issue_to_dict(issue: Any) -> dict[str, Any]:
    to_json = getattr(issue, "to_json", None)
    if callable(to_json):
        rendered = to_json()
        if isinstance(rendered, dict):
            return rendered
    if isinstance(issue, Mapping):
        return dict(issue)
    return {"code": type(issue).__name__, "message": str(issue), "severity": "error"}


def _warn_legacy_contract_once(contract: str) -> None:
    if contract in _WARNED_LEGACY_CONTRACTS:
        return
    _WARNED_LEGACY_CONTRACTS.add(contract)
    _resolve_edit_attr("LOGGER").warning(
        "agent-edit legacy contract '%s' selected via VIBECOMFY_AGENT_EDIT_LEGACY; "
        "this is deprecated and will be removed",
        contract,
    )


def _warn_ignored_public_protocol_envs_once(env_names: tuple[str, ...]) -> None:
    unseen = tuple(name for name in env_names if name not in _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS)
    if not unseen:
        return
    _WARNED_IGNORED_PUBLIC_PROTOCOL_ENVS.update(unseen)
    _resolve_edit_attr("LOGGER").warning(
        "agent-edit ignoring legacy public protocol env vars (%s); product protocol is always "
        "'batch_repl'. For dev-only legacy protocols set "
        "VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS=1 and "
        "VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL=delta|full.",
        ", ".join(unseen),
    )


def _agent_edit_contract() -> str:
    ignored_public_envs = tuple(
        name
        for name in (
            "VIBECOMFY_AGENT_EDIT_LEGACY",
            "VIBECOMFY_AGENT_EDIT_V2",
            "VIBECOMFY_AGENT_EDIT_BATCH_REPL",
        )
        if os.getenv(name) is not None
    )
    if ignored_public_envs:
        _warn_ignored_public_protocol_envs_once(ignored_public_envs)
    if os.getenv("VIBECOMFY_AGENT_EDIT_ALLOW_DEV_PROTOCOLS") == "1":
        dev_protocol = os.getenv("VIBECOMFY_AGENT_EDIT_DEV_PROTOCOL")
        if dev_protocol in {"delta", "full"}:
            _warn_legacy_contract_once(dev_protocol)
            return dev_protocol
    return "batch_repl"


def _agent_edit_v2_enabled() -> bool:
    return _agent_edit_contract() == "delta"


def _agent_edit_batch_repl_enabled() -> bool:
    return _agent_edit_contract() == "batch_repl"


def _edit_lint_enabled() -> bool:
    """Return True unless VIBECOMFY_AGENT_EDIT_LINT is explicitly disabled.

    Accepts ``0``, ``false``, ``off``, or ``no`` (case-insensitive) as disabled
    values.  Defaults to ON (enabled) when the env var is unset or set to any
    other value.

    Rollout flag / off-switch
    -------------------------
    Setting ``VIBECOMFY_AGENT_EDIT_LINT=0`` disables the entire lint gate in
    ``_stage_apply_delta`` and ``_stage_agent_batch_repl``.  When lint is off the
    pipeline falls back to pre-lint behaviour: ``apply_delta()`` receives every
    op unchecked, no-ops are not pre-filtered, and diagnostics come from
    ``resolve_delta`` / ``apply_delta`` rather than from ``lint_delta()``.  This
    flag is intended as an emergency off-switch; the default path is *enabled*.
    """
    raw = os.getenv("VIBECOMFY_AGENT_EDIT_LINT")
    if raw is None:
        return True
    return raw.strip().lower() not in {"0", "false", "off", "no"}


def _prefetch_research_summary(effective_task: str) -> str:
    """Return a pre-fetched research summary for graph-explain intents.

    Called as a fallback when ``state.executor_research_summary`` is empty
    and the effective task matches a graph-explain pattern.
    """
    return ""


def _record(context: TurnContext, result: StageResult) -> StageResult:
    context.stage_results[result.stage] = result
    _resolve_edit_attr("apply_stage_gate_updates")(context, result)
    return result


def _stamp_identity_on_original(graph: dict[str, Any], workflow: Any) -> int:
    """Phase 1 (concrete-tree migration): stamp the IR's stable uid onto the
    *original* UI nodes so the delta-scope guard (`guard_emit`) and pin-opaque
    can match on a user's FIRST edit. A hand-authored ComfyUI canvas carries no
    `properties.vibecomfy_uid`, so `guard_emit`'s scope (uids shared between the
    original and the candidate) is otherwise empty and the whole preserve/guard
    layer no-ops (blockers.md B12). The candidate inherits these same uids from
    the IR, so stamping the original makes the scope non-empty.

    See docs/agent-edit/concrete-tree.md. Match is by litegraph node id, which is
    stable across the round-trip.
    """
    by_id = {str(nid): node for nid, node in getattr(workflow, "nodes", {}).items()}
    stamped = 0
    for ui_node in graph.get("nodes") or []:
        if not isinstance(ui_node, dict):
            continue
        ir = by_id.get(str(ui_node.get("id")))
        uid = getattr(ir, "uid", "") if ir is not None else ""
        if not uid:
            continue
        props = ui_node.get("properties")
        if not isinstance(props, dict):
            props = {}
            ui_node["properties"] = props
        if not props.get("vibecomfy_uid"):
            props["vibecomfy_uid"] = uid
            stamped += 1
    return stamped


def _stale_rebaseline_recovery_issue(
    state: AgentEditState,
    gate_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "stale_state_recovery",
        "last_known_baseline_graph_hash": state.baseline_graph_hash,
        "submit_graph_hash": state.submit_graph_hash,
        "submit_structural_graph_hash": state.submit_structural_graph_hash,
        "client_graph_hash": state.submitted_client_graph_hash,
        "client_structural_graph_hash": state.submitted_client_structural_graph_hash,
    }
    return {
        "code": "stale_state_mismatch",
        "severity": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "message": "Submitted graph no longer matches the current baseline.",
        "detail": dict(gate_evidence),
        "rebaseline_recovery": recovery,
    }


def _stage_ingest(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.layout_store import store_from_ui_json

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    original_ui_ref = write_json_artifact(state.original_ui_path, state.graph)
    state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
    state.prior_store = store_from_ui_json(state.graph)
    # Phase 1 (concrete-tree migration, docs/agent-edit/concrete-tree.md): give the
    # user's original graph stable identity so the delta-scope guard (guard_emit)
    # engages on the FIRST edit. Stamp a COPY — never mutate state.graph, which is
    # hashed/echoed/audited. The candidate inherits the same uids (verified: uid ==
    # node id, preserved across the scratchpad round-trip), so the guard scope
    # becomes non-empty.
    #
    # Gated OFF by default: with the guard engaged but the candidate still produced
    # by the LOSSY regeneration path (Phase 2 not yet landed), guard_emit correctly
    # refuses candidates that diverge from the original outside the intended delta.
    # Enabling identity is therefore only safe once Phase 2 (verbatim-preserve)
    # makes the candidate faithful. Toggle with VIBECOMFY_AGENT_EDIT_IDENTITY=1.
    if os.getenv("VIBECOMFY_AGENT_EDIT_IDENTITY") == "1":
        from copy import deepcopy as _deepcopy
        guard_original = _deepcopy(state.graph)
        _stamp_identity_on_original(guard_original, state.workflow)
        state.guard_original_ui = guard_original
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
    )


def _stage_ingest_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.ledger import EditLedger

    start = time.monotonic()
    request_ref = write_json_artifact(state.request_path, state.request_payload)
    # The EditLedger walks a UI ``nodes`` array. An API-format (compiled_api)
    # source has no ``nodes`` key, so every edit op would die on ``stale_graph_name``
    # ("uid no longer present"). When the source is not already UI format,
    # re-serialize the canonical VibeWorkflow (which ingests both formats) to a UI
    # envelope so the ledger sees the nodes. UI-format inputs already have ``nodes``
    # and are left untouched — re-serializing them is lossy and breaks the path that
    # already works. ``state.graph`` is hashed/echoed/audited, so all downstream
    # consumers share this one canonical view.
    from vibecomfy.ingest.normalize import convert_to_vibe_format, detect_workflow_shape
    from vibecomfy.porting.emit.ui import emit_ui_json

    if detect_workflow_shape(state.graph) != "ui":
        state.workflow = convert_to_vibe_format(state.graph, schema_provider=state.schema_provider)
        state.graph = emit_ui_json(
            state.workflow,
            schema_provider=state.schema_provider,
            guard_original_ui=state.graph,
        )
    ledger = EditLedger.ingest(state.graph)
    state.guard_original_ui = ledger.stamped_copy()
    original_ui_ref = write_json_artifact(state.original_ui_path, state.guard_original_ui)
    # Auto-rebaseline on submit: the live canvas the user submitted is always
    # authoritative for an edit, so submit does NOT enforce a pinned baseline
    # (baseline_graph_hash=None => the gate never blocks on canvas drift). The
    # stale-state guard is retained on the APPLY path, where applying a candidate
    # computed against an older canvas could clobber later manual edits.
    update_state_match_gate(
        context,
        baseline_graph_hash=None,
        client_graph_hash=state.submit_structural_graph_hash,
        client_graph_hash_label="submit_structural_graph_hash",
    )
    state_match_gate = context.gate_results["state_match_ok"]
    if not state_match_gate.ok:
        stale_issue = _stale_rebaseline_recovery_issue(state, state_match_gate.evidence)
        return StageResult(
            stage="ingest",
            ok=False,
            blocking=True,
            duration_ms=_duration_ms(start),
            artifacts=(request_ref, original_ui_ref),
            issues=(stale_issue,),
            value={"failure_kind": FailureKind.STALE_STATE_MISMATCH.value},
        )
    return StageResult(
        stage="ingest",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(request_ref, original_ui_ref),
        issues=tuple(issue.to_dict() for issue in ledger.diagnostics),
        value={
            "mode": "agent_edit_v2_delta",
            "node_count": len(ledger.node_index),
            "scope_count": len(ledger.scopes),
        },
    )


def _stage_convert(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.convert import port_convert_and_write, port_convert_workflow

    start = time.monotonic()
    conversion = port_convert_workflow(
        state.workflow,
        source_path=str(state.original_ui_path),
        schema_provider=state.schema_provider,
        raw_workflow=state.graph,
        # Editing a user's live canvas must preserve every node. Dead-branch
        # pruning is for authoring minimal templates; here it would silently
        # drop nodes that don't feed a recognized output (e.g. a GeminiNode
        # feeding only a PreviewAny passthrough) and corrupt the round-trip.
        prune_dead_branches=False,
    )
    # Keep the strict parity gate: with prune disabled + UI-only passthrough
    # preservation (emitter), a faithful user canvas round-trips and passes here,
    # while a genuinely-lossy conversion still fails honestly rather than applying
    # a corrupted candidate.
    port_convert_and_write(conversion, state.before_py_path)
    state.python_before = state.before_py_path.read_text(encoding="utf-8")
    return StageResult(
        stage="convert",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.before_py_path),),
    )


def _stage_project_v2(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.porting.edit.projection import ProjectionOptions, render_edit_projection

    start = time.monotonic()
    # The 8000-token default forces sparse mode on every real ComfyUI graph (140-200+
    # nodes), collapsing all nodes to summaries and starving the model of the field
    # names / slot types it needs to target edits and wire links correctly. Modern
    # models have 64K+ context, so render real graphs in FULL detail. Env-overridable.
    try:
        _proj_budget = int(os.getenv("VIBECOMFY_EDIT_PROJECTION_MAX_TOKENS", "256000"))
    except (TypeError, ValueError):
        _proj_budget = 256000
    projection = render_edit_projection(
        state.guard_original_ui or state.graph,
        task=state.task,
        schema_provider=state.schema_provider,
        options=ProjectionOptions(max_tokens=_proj_budget),
    )
    state.projection_text = projection.text
    state.projection_path.write_text(projection.text, encoding="utf-8")
    return StageResult(
        stage="project",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.projection_path),),
        value={
            "token_estimate": projection.token_estimate,
            "node_count": projection.node_count,
            "detailed_node_count": projection.detailed_node_count,
            "truncated": projection.truncated,
        },
    )


def _stage_agent(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    start = time.monotonic()
    messages = build_messages(task=state.task, python_source=state.python_before, execution_mode="sandboxed_loose")
    write_json_artifact(state.model_request_path, {"messages": messages})
    if deepseek_client is not None:
        agent_result = _normalize_test_client_response(
            deepseek_client(messages)
        )
    else:
        agent_result = run_agent_turn(
            state.task,
            state.python_before,
            route=route,
            model=model,
        )
    state.python_after = agent_result.python
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    model_response_ref = write_json_artifact(
        state.model_response_path,
        agent_result.to_dict(),
    )
    return StageResult(
        stage="agent",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "provider_metadata": state.provider_metadata,
        },
    )


def _stage_agent_delta(
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> StageResult:
    from vibecomfy.porting.edit.ops import (
        EDIT_OP_RESPONSE_SCHEMA_V2,
        normalize_delta_test_client_response,
    )

    start = time.monotonic()
    messages = build_delta_messages(
        task=state.task,
        projection=state.projection_text,
        op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
    )
    write_json_artifact(
        state.model_request_path,
        {"messages": messages, "response_contract": "delta"},
    )
    if deepseek_client is not None:
        agent_result = normalize_delta_test_client_response(deepseek_client(messages))
    else:
        agent_result = run_agent_turn_delta(
            state.task,
            state.projection_text,
            op_schema=EDIT_OP_RESPONSE_SCHEMA_V2,
            route=route,
            model=model,
        )
    state.delta_ops = agent_result.delta
    state.user_message = agent_result.message
    state.provider_metadata = dict(agent_result.audit_metadata or {})
    model_response_ref = write_json_artifact(
        state.model_response_path,
        agent_result.to_dict(),
    )
    return StageResult(
        stage="agent_delta",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.model_request_path), model_response_ref),
        value={
            "route": agent_result.route,
            "model": agent_result.model,
            "op_count": len(agent_result.delta),
            "provider_metadata": state.provider_metadata,
        },
    )


_RESEARCH_TRIGGER_TERMS = (
    "look up", "lookup", "research", "find out", "how does", "how do", "what is",
    "what are", "explain how", "how can", "how to", "information about",
)

_GRAPH_EXPLAIN_TRIGGER_TERMS = (
    "what's happening", "what is happening", "what's going on", "what is going on",
    "explain this graph", "explain the graph", "describe this graph",
    "describe the graph", "analyze this graph", "analyze the graph",
    "inspect this graph", "inspect the graph", "what does this graph do",
)

_CODE_NODE_TRIGGER_TERMS = (
    "code node",
    "python",
    "pil",
    "pillow",
    "custom image-processing",
    "custom image processing",
    "process images",
    "image processing",
)


def _task_mentions_any(task: str, terms: tuple[str, ...]) -> bool:
    lowered = task.lower()
    return any(term in lowered for term in terms)


def _is_research_intent(task: str) -> bool:
    return _task_mentions_any(task, _RESEARCH_TRIGGER_TERMS)


def _is_graph_explain_intent(task: str) -> bool:
    return _task_mentions_any(task, _GRAPH_EXPLAIN_TRIGGER_TERMS)


def _is_code_node_intent(task: str) -> bool:
    return _task_mentions_any(task, _CODE_NODE_TRIGGER_TERMS)


def _build_graph_report(graph: dict[str, Any] | None) -> str:
    """Legacy: build a compact text report from a raw ComfyUI graph dict.

    .. deprecated::
        The executor now handles graph inspection for **inspect** routes via
        :mod:`vibecomfy.executor.graph_inspection` (structured evidence +
        Markdown renderer).  This function is kept for internal agent-edit
        tests and for the batch-REPL prompt building when graph context is
        injected into edit (revise / adapt) operations.
    """
    if not graph:
        return "No graph attached."
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return "Empty graph (0 nodes)."

    lines: list[str] = []
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or node.get("type") or "Unknown"
        node_id = node.get("id", i)
        parts: list[str] = [f"[{node_id}] {ct}"]
        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and widgets:
            widget_parts = []
            for j, w in enumerate(widgets[:5]):
                if w is not None and str(w).strip():
                    widget_parts.append(f"w{j}={str(w)[:80]}")
            if widget_parts:
                parts.append("values=(" + ", ".join(widget_parts) + ")")
        inputs = node.get("inputs")
        if isinstance(inputs, list):
            slot_info = []
            for inp in inputs:
                if isinstance(inp, dict):
                    name = inp.get("name", "?")
                    link = inp.get("link")
                    slot_info.append(
                        f"{name}=linked({link})" if link is not None else f"{name}=open"
                    )
            if slot_info:
                parts.append("inputs=(" + "; ".join(slot_info[:6]) + ")")
        lines.append(" ".join(parts))

    links = graph.get("links")
    if isinstance(links, list) and links:
        edge_lines: list[str] = []
        for link in links[:40]:
            if isinstance(link, dict):
                src = link.get("origin_id", "?")
                tgt = link.get("target_id", "?")
                edge_lines.append(f"  {src} -> {tgt}")
            elif isinstance(link, list) and len(link) >= 4:
                edge_lines.append(f"  {link[1]} -> {link[3]}")
        if edge_lines:
            lines.append("Edges:")
            lines.extend(edge_lines)

    return f"{len(nodes)} node(s):\n" + "\n".join(lines)



def _build_precedent_adaptation_prompt(
    adaptation_plan: dict[str, Any] | None,
    precedent_slices: tuple[dict[str, Any], ...] = (),
) -> str:
    """Build a compact precedent adaptation prompt for batch REPL injection.

    Only invoked for the `precedent_research` route.  Includes anchors,
    required nodes/rewires, socket evidence, avoid patterns, and semantic
    checks from the structured adaptation plan, but never the full
    candidate_graph to avoid biasing the model toward a single solution.

    All precedent material is neutral context — it is NOT a winner,
    recommendation, or required implementation.  The adaptation agent
    evaluates all available slices independently.
    """
    if not adaptation_plan:
        return ""

    parts: list[str] = []

    # ── context note (neutrality disclaimer) ──
    context_note = adaptation_plan.get("context_note")
    if isinstance(context_note, str) and context_note.strip():
        parts.append(f"IMPORTANT: {context_note.strip()}")

    # ── selected slice (presentation context only — not a winner) ──
    selected_slice = adaptation_plan.get("selected_slice")
    if isinstance(selected_slice, dict):
        source_class = selected_slice.get("source_class_type", "")
        node_ids = selected_slice.get("node_ids") or []
        entry = selected_slice.get("entry_anchor")
        exit_ = selected_slice.get("exit_anchor")
        py_path = selected_slice.get("python_path")
        slice_desc = f"Source: {source_class}" if source_class else "Source: (unnamed)"
        if isinstance(node_ids, list) and node_ids:
            slice_desc += f", {len(node_ids)} node(s): [{', '.join(str(n) for n in node_ids[:8])}]"
            if len(node_ids) > 8:
                slice_desc += f" (+{len(node_ids) - 8} more)"
        if entry:
            slice_desc += f", entry_anchor={entry}"
        if exit_:
            slice_desc += f", exit_anchor={exit_}"
        if py_path:
            slice_desc += f", path={py_path}"
        parts.append(f"Reference slice (presentation context only — NOT a winner): {slice_desc}")

    # ── all available slices (neutral summary) ──
    all_slices = adaptation_plan.get("all_slices")
    if isinstance(all_slices, list) and all_slices:
        slice_summaries = []
        for i, s in enumerate(all_slices[:12]):
            if isinstance(s, dict):
                ct = s.get("source_class_type") or "unnamed"
                nids = s.get("node_ids") or []
                n = len(nids) if isinstance(nids, (list, tuple)) else 0
                entry_a = s.get("entry_anchor")
                exit_a = s.get("exit_anchor")
                desc = f"{ct} ({n} nodes"
                if entry_a:
                    desc += f", entry={entry_a}"
                if exit_a:
                    desc += f", exit={exit_a}"
                desc += ")"
                slice_summaries.append(desc)
        if slice_summaries:
            if len(all_slices) > 12:
                slice_summaries.append(f"(+{len(all_slices) - 12} more slices)")
            parts.append("All available precedent slices (neutral context): " + "; ".join(slice_summaries))

    # ── anchor bindings ──
    anchor_bindings = adaptation_plan.get("anchor_bindings")
    if isinstance(anchor_bindings, list) and anchor_bindings:
        binding_lines = []
        for b in anchor_bindings:
            if isinstance(b, dict):
                binding_lines.append(", ".join(f"{k} → {v}" for k, v in b.items()))
        if binding_lines:
            parts.append("Anchor bindings: " + "; ".join(binding_lines))

    # ── required new nodes ──
    required_new_nodes = adaptation_plan.get("required_new_nodes")
    if isinstance(required_new_nodes, list) and required_new_nodes:
        node_lines = []
        for n in required_new_nodes[:10]:
            if isinstance(n, dict):
                class_type = n.get("class_type") or n.get("type") or "node"
                node_id = n.get("id") or n.get("node_id") or "?"
                slot_info = ""
                inputs = n.get("inputs")
                if isinstance(inputs, dict):
                    slot_info = ", ".join(f"{k}={v}" for k, v in list(inputs.items())[:3])
                desc = f"{class_type}(id={node_id}"
                if n.get("widget_values"):
                    desc += f", values={json.dumps(n['widget_values'])[:80]}"
                if slot_info:
                    desc += f", inputs={{{slot_info}}}"
                desc += ")"
                node_lines.append(desc)
        if node_lines:
            parts.append("Required new nodes: " + "; ".join(node_lines))

    # ── required rewires ──
    required_rewires = adaptation_plan.get("required_rewires")
    if isinstance(required_rewires, list) and required_rewires:
        rewire_lines = []
        for r in required_rewires[:6]:
            if isinstance(r, dict):
                src = r.get("from") or r.get("source") or "?"
                tgt = r.get("to") or r.get("target") or "?"
                slot = r.get("slot") or r.get("input_slot") or ""
                desc = f"{src} → {tgt}"
                if slot:
                    desc += f".{slot}"
                rewire_lines.append(desc)
        if rewire_lines:
            parts.append("Required rewires: " + "; ".join(rewire_lines))

    # ── edit ops (compact) ──
    edit_ops = adaptation_plan.get("edit_ops")
    if isinstance(edit_ops, list) and edit_ops:
        op_lines = []
        for op in edit_ops[:6]:
            if isinstance(op, dict):
                op_kind = op.get("kind") or op.get("op") or "edit"
                op_target = op.get("target") or op.get("node_id") or "?"
                op_value = op.get("value")
                desc = f"{op_kind} {op_target}"
                if op_value is not None:
                    desc += f"={json.dumps(op_value)[:40]}"
                op_lines.append(desc)
        if op_lines:
            parts.append("Edit ops: " + "; ".join(op_lines))

    # ── socket evidence (from slices) ──
    if precedent_slices:
        socket_lines = []
        for s in precedent_slices[:4]:
            if isinstance(s, dict):
                class_type = s.get("source_class_type") or "node"
                entry = s.get("entry_anchor")
                exit_ = s.get("exit_anchor")
                node_ids = s.get("node_ids") or []
                desc = class_type
                if entry or exit_:
                    anchors = []
                    if entry:
                        anchors.append(f"in={entry}")
                    if exit_:
                        anchors.append(f"out={exit_}")
                    desc += f" ({', '.join(anchors)})"
                socket_lines.append(desc)
        if socket_lines:
            parts.append("Socket evidence (workflow slices): " + "; ".join(socket_lines))

    # ── avoid patterns (derived from structural validation) ──
    structural_val = adaptation_plan.get("structural_validation", "")
    if structural_val == "fail":
        parts.append("AVOID: structural validation FAILED — the precedent slice may not be structurally compatible. Prefer a different precedent or adapt conservatively.")
    elif structural_val == "advisory":
        parts.append("NOTE: structural validation has advisories — verify wiring compatibility before landing edits.")

    # ── semantic checks ──
    semantic_val = adaptation_plan.get("semantic_validation", "")
    if semantic_val == "pass":
        parts.append("Semantic validation: PASS — the adaptation is semantically sound.")
    elif semantic_val == "fail":
        parts.append("AVOID: semantic validation FAILED — the precedent may not produce the expected behavior. Consider an alternative.")
    elif semantic_val == "advisory":
        parts.append("Semantic validation advisories present — review model compatibility and slot types.")

    if not parts:
        return ""

    return "\n".join(parts)


def _route_blocks_apply(route: str | None) -> bool:
    """Return True when *route* forbids Apply eligibility.

    Non-applyable routes (clarify, respond, inspect, research) do not
    produce edits and must never carry a candidate, apply_eligible flag,
    or apply-eligibility payload.  Only revise and adapt are apply-eligible.
    """
    return _canonical_agent_edit_route(route) in {"clarify", "respond", "inspect", "research"}


def _canonical_agent_edit_route(route: str | None) -> str | None:
    """Normalize executor-facing route labels to the canonical vocabulary."""
    if not isinstance(route, str):
        return None
    normalized = route.strip()
    if not normalized:
        return None
    aliases = {
        "inspect_only": "inspect",
        "direct_edit": "revise",
        "diagnose_repair": "revise",
        "precedent_research": "adapt",
    }
    return aliases.get(normalized, normalized)


def _route_change_focus_label(route: str | None) -> str:
    """Return a short change-focus label for *route* when reporting edits.

    revise is a focused, targeted change — the label makes that
    explicit in user-facing summaries.
    """
    if _canonical_agent_edit_route(route) == "revise":
        return "Focused change"
    return ""


def _build_precedent_semantic_check_entries(
    state: "AgentEditState",
) -> list[dict[str, Any]]:
    """Build task-satisfaction entries from the precedent adaptation plan.

    Semantic and structural validation fields are mapped to task satisfaction
    entries with a satisfaction key of advisory (for advisory warnings)
    or not_evaluated (for fields the plan did not evaluate).  These entries
    provide route-level observability without blocking Apply or Queue.
    """
    plan = state.executor_adaptation_plan
    if not isinstance(plan, dict):
        return []

    entries: list[dict[str, Any]] = []

    structural_val = plan.get("structural_validation")
    if structural_val in ("pass", "fail", "advisory", "not_evaluated"):
        entries.append(
            {
                "check": "structural_validation",
                "status": structural_val,
                "satisfaction": structural_val if structural_val != "not_evaluated" else "not_evaluated",
                "description": _structural_validation_description(structural_val),
            }
        )

    semantic_val = plan.get("semantic_validation")
    if semantic_val in ("pass", "fail", "advisory", "not_evaluated"):
        entries.append(
            {
                "check": "semantic_validation",
                "status": semantic_val,
                "satisfaction": semantic_val if semantic_val != "not_evaluated" else "not_evaluated",
                "description": _semantic_validation_description(semantic_val),
            }
        )

    return entries


def _structural_validation_description(status: str) -> str:
    if status == "pass":
        return "Precedent slice is structurally compatible with the current graph."
    if status == "fail":
        return "Precedent slice has structural incompatibilities — adapt conservatively."
    if status == "advisory":
        return "Precedent slice has structural advisories — verify wiring compatibility."
    return "Structural validation was not evaluated for the precedent slice."


def _semantic_validation_description(status: str) -> str:
    if status == "pass":
        return "Precedent adaptation is semantically sound."
    if status == "fail":
        return "Precedent may not produce expected behavior — consider alternatives."
    if status == "advisory":
        return "Semantic advisories present — review model compatibility and slot types."
    return "Semantic validation was not evaluated for the precedent adaptation."



def _stage_agent_batch_repl(
    state: AgentEditState,
    context: TurnContext,
    **kwargs: Any,
) -> StageResult:
    return _resolve_edit_attr("_stage_agent_batch_repl_impl")(state, context, **kwargs)


def _stage_summarize(state: AgentEditState, context: TurnContext) -> StageResult:
    return _resolve_edit_attr("_stage_summarize_impl")(state, context)


def _stage_summarize_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    return _resolve_edit_attr("_stage_summarize_v2_impl")(state, context)


def _stage_audit(
    state: AgentEditState,
    context: TurnContext,
    *,
    response: dict[str, Any] | None = None,
    failure: FailureEnvelope | None = None,
):
    return _resolve_edit_attr("_stage_audit_impl")(state, context, response=response, failure=failure)

def _write_unknown_transition_audits(
    *,
    session_root: Path,
    session_id: str,
    baseline_turn_id: str | None,
    unknown_transitions: tuple[dict[str, Any], ...],
    request_payload: Mapping[str, Any],
) -> None:
    for transition in unknown_transitions:
        turn_id = transition.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        try:
            _resolve_edit_attr("write_audit")(
                _resolve_edit_attr("turn_dir_for")(session_root, session_id, turn_id) / "unknown_audit",
                context=TurnContext(
                    session_id=session_id,
                    turn_id=turn_id,
                    baseline_turn_id=baseline_turn_id,
                ),
                turn_state="unknown",
                artifacts={"request": dict(request_payload)},
                metadata={"action": "unknown", **transition},
            )
        except Exception:
            continue



def _failure_response(
    state: AgentEditState,
    context: TurnContext,
    failure: FailureEnvelope,
    *,
    contract: str = "batch_repl",
) -> dict[str, Any]:
    if contract != "batch_repl":
        return _resolve_edit_attr("_build_dev_failure_response")(state, context, failure=failure)
    return _resolve_edit_attr("_build_batch_repl_failure_response")(state, context, failure=failure)


def _run_stage_impl(
    name: str,
    state: AgentEditState,
    context: TurnContext,
    fn: Callable[..., StageResult],
    *args: Any,
    **kwargs: Any,
) -> StageResult:
    stage_blocked = _resolve_edit_attr("_StageBlocked")
    try:
        result = fn(state, context, *args, **kwargs)
    except Exception as exc:
        failure_stage = (
            "agent_response"
            if name in {"agent", "agent_delta"}
            or (name in {"agent_batch", "agent_batch_repl"} and _is_provider_exception(exc))
            else name
        )
        failure = classify_failure(failure_stage, exc, context)
        result = StageResult(
            stage=name,
            ok=False,
            blocking=True,
            issues=(failure.agent_failure_context,),
        )
        _record(context, result)
        raise stage_blocked(result, failure) from exc
    _record(context, result)
    if result.blocking:
        failure_kind = None
        if isinstance(result.value, dict):
            failure_kind = result.value.get("failure_kind")
        public_stage = name
        issue_codes = {
            str(issue.get("code"))
            for issue in result.issues
            if isinstance(issue, dict) and issue.get("code") is not None
        }
        diagnostic_codes: set[str] = set()
        if name == "agent_batch_repl":
            for turn in state.batch_turns:
                if not isinstance(turn, Mapping):
                    continue
                diagnostics = list(turn.get("diagnostics") or [])
                for statement in turn.get("statements") or []:
                    if isinstance(statement, Mapping):
                        diagnostics.extend(statement.get("diagnostics") or [])
                diagnostic_codes.update(
                    str(diagnostic.get("code"))
                    for diagnostic in diagnostics
                    if isinstance(diagnostic, Mapping) and diagnostic.get("code") is not None
                )
        parse_or_query_codes = {
            "batch_syntax_error",
            "nested_call_not_allowed",
            "unsupported_query_call",
        }
        if (
            name == "agent_batch_repl"
            and "batch_budget_exhausted" in issue_codes
            and not diagnostic_codes.intersection(parse_or_query_codes)
        ):
            public_stage = "agent_batch"
        failure = failure_envelope(
            failure_kind or FailureKind.VALIDATION_ERROR,
            public_stage,
            context,
            agent_failure_context={
                "explanation": f"Stage {public_stage} blocked the agent edit.",
                "issues": [dict(issue) for issue in result.issues if isinstance(issue, dict)],
            },
        )
        if failure.kind is FailureKind.STALE_STATE_MISMATCH and public_stage in {"ingest", "ingest_v2"}:
            failure = dataclasses.replace(
                failure,
                user_facing_message=(
                    "The canvas changed since the current backend baseline. "
                    "Rebaseline and resubmit from the current canvas."
                ),
            )
        raise stage_blocked(result, failure)
    return result


def _is_provider_exception(exc: Exception) -> bool:
    provider_exception_names = {
        "AuthError",
        "MalformedModelJSON",
        "MissingRequiredField",
        "ProviderError",
    }
    return any(type_.__name__ in provider_exception_names for type_ in type(exc).__mro__)


def _run_batch_repl_product_path_impl(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> AgentEditState:
    run_stage = _resolve_edit_attr("_run_stage")
    run_stage("ingest", state, context, _resolve_edit_attr("_stage_ingest_v2"))
    run_stage(
        "revision_evidence",
        state,
        context,
        _resolve_edit_attr("_stage_revision_evidence"),
        route=state.route,
        conversation_messages=conversation_messages,
    )
    if (
        state.revision_evidence is not None
        and not state.revision_evidence.safe_candidate_possible
        and not _can_attempt_local_additive_revise(state)
    ):
        run_stage(
            "agent_batch",
            state,
            context,
            _resolve_edit_attr("_stage_revision_readonly_report"),
            route=state.route,
            conversation_messages=conversation_messages,
        )
        return state
    run_stage(
        "agent_batch",
        state,
        context,
        _resolve_edit_attr("_stage_agent_batch_repl"),
        deepseek_client=deepseek_client,
        route=route,
        model=model,
        client_id=client_id,
        conversation_messages=conversation_messages,
    )
    return state


def _run_delta_dev_path_impl(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> AgentEditState:
    run_stage = _resolve_edit_attr("_run_stage")
    run_stage("ingest", state, context, _resolve_edit_attr("_stage_ingest_v2"))
    run_stage("project", state, context, _resolve_edit_attr("_stage_project_v2"))
    run_stage(
        "agent_delta",
        state,
        context,
        _resolve_edit_attr("_stage_agent_delta"),
        deepseek_client=deepseek_client,
        route=route,
        model=model,
    )
    run_stage("apply_delta", state, context, _resolve_edit_attr("_stage_apply_delta"))
    run_stage("summarize", state, context, _resolve_edit_attr("_stage_summarize_v2"))
    return state


def _run_full_dev_path_impl(
    state: AgentEditState,
    context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
) -> AgentEditState:
    run_stage = _resolve_edit_attr("_run_stage")
    run_stage("ingest", state, context, _resolve_edit_attr("_stage_ingest"))
    run_stage("convert", state, context, _resolve_edit_attr("_stage_convert"))
    run_stage(
        "agent",
        state,
        context,
        _resolve_edit_attr("_stage_agent"),
        deepseek_client=deepseek_client,
        route=route,
        model=model,
    )
    run_stage("load_python", state, context, _resolve_edit_attr("_stage_load_python"))
    run_stage("lower", state, context, _resolve_edit_attr("_stage_lower"))
    run_stage("validate", state, context, _resolve_edit_attr("_stage_validate"))
    run_stage("emit", state, context, _resolve_edit_attr("_stage_emit"))
    run_stage("summarize", state, context, _resolve_edit_attr("_stage_summarize"))
    return state


def handle_agent_edit_impl(
    payload: dict[str, Any],
    *,
    schema_provider: Any = None,
    deepseek_client: DeepSeekClient | None = None,
    session_root: Path,
    client_id: str | None = None,
) -> dict[str, Any]:
    validated_response = _resolve_edit_attr("_validated_agent_edit_response")
    product_failure_response = _resolve_edit_attr("_product_failure_response")
    safe_session_id = _resolve_edit_attr("_safe_session_id")
    allocate_turn = _resolve_edit_attr("allocate_turn")
    initialize_gates = _resolve_edit_attr("initialize_gates")
    record_idempotent_response = _resolve_edit_attr("record_idempotent_response")
    read_session_chat = _resolve_edit_attr("read_session_chat")
    conversation_with_candidate_reference = _resolve_edit_attr("_conversation_with_candidate_reference")
    agent_edit_contract = _resolve_edit_attr("_agent_edit_contract")
    canonical_route = _resolve_edit_attr("_canonical_agent_edit_route")
    run_batch = _resolve_edit_attr("_run_batch_repl_product_path")
    run_delta = _resolve_edit_attr("_run_delta_dev_path")
    run_full = _resolve_edit_attr("_run_full_dev_path")
    build_dev_success = _resolve_edit_attr("_build_dev_success_response")
    build_batch_response = _resolve_edit_attr("_build_batch_repl_response")
    record_stage = _resolve_edit_attr("_record")
    stage_audit = _resolve_edit_attr("_stage_audit")
    write_turn_chat_artifact = _resolve_edit_attr("_write_turn_chat_artifact")
    stage_blocked_type = _resolve_edit_attr("_StageBlocked")
    prompt_memory_messages = _resolve_edit_attr("PROMPT_MEMORY_MESSAGES")

    if not isinstance(payload, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        )
        return validated_response(product_failure_response(failure), stage="ingest")

    task = payload.get("task")
    graph = payload.get("graph")
    if not isinstance(task, str) or not task.strip():
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "`task` is required."},
        )
        return validated_response(product_failure_response(failure), stage="ingest")
    if not isinstance(graph, dict):
        failure = failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "ingest",
            agent_failure_context={"explanation": "`graph` must be a ComfyUI UI JSON object."},
        )
        return validated_response(product_failure_response(failure), stage="ingest")

    if schema_provider is None:
        schema_provider = _default_runtime_schema_provider()
    session_id = safe_session_id(payload.get("session_id"))
    allocation = allocate_turn(
        session_root=session_root,
        session_id=session_id,
        request_payload=payload,
        idempotency_key=payload.get("idempotency_key")
        if isinstance(payload.get("idempotency_key"), str)
        else None,
    )
    if allocation.replay is not None:
        return validated_response(allocation.replay.response, stage="replay")
    if allocation.conflict is not None:
        try:
            audit_ref = write_allocation_failure_audit(
                allocation.session_dir,
                session_id=session_id,
                failure=allocation.conflict.failure,
                request=payload,
            )
            failure = dataclasses.replace(allocation.conflict.failure, audit_ref=audit_ref)
        except Exception:
            failure = allocation.conflict.failure
        return validated_response(product_failure_response(failure), stage="allocation")

    context = allocation.context
    context.client_graph_hash = payload.get("client_graph_hash") if isinstance(payload.get("client_graph_hash"), str) else None
    initialize_gates(context)
    _write_unknown_transition_audits(
        session_root=session_root,
        session_id=session_id,
        baseline_turn_id=context.baseline_turn_id,
        unknown_transitions=allocation.unknown_transitions,
        request_payload=payload,
    )
    turn_dir = allocation.turn_dir
    turn_record = allocation.state.get("turns", {}).get(context.turn_id)
    baseline_graph_hash = (
        allocation.state.get("baseline_graph_hash")
        if isinstance(allocation.state.get("baseline_graph_hash"), str)
        else None
    )
    submit_graph_hash = (
        turn_record.get("submit_graph_hash")
        if isinstance(turn_record, dict) and isinstance(turn_record.get("submit_graph_hash"), str)
        else None
    )
    submit_structural_graph_hash = (
        turn_record.get("submit_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submit_structural_graph_hash"), str)
        else None
    )
    submitted_client_graph_hash = (
        turn_record.get("submitted_client_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_graph_hash"), str)
        else None
    )
    submitted_client_structural_graph_hash = (
        turn_record.get("submitted_client_structural_graph_hash")
        if isinstance(turn_record, dict)
        and isinstance(turn_record.get("submitted_client_structural_graph_hash"), str)
        else None
    )
    state = AgentEditState(
        task=task,
        graph=graph,
        request_payload=payload,
        schema_provider=schema_provider,
        baseline_graph_hash=baseline_graph_hash,
        submit_graph_hash=submit_graph_hash,
        submit_structural_graph_hash=submit_structural_graph_hash,
        submitted_client_graph_hash=submitted_client_graph_hash,
        submitted_client_structural_graph_hash=submitted_client_structural_graph_hash,
        session_dir=allocation.session_dir,
        turn_dir=turn_dir,
        request_path=turn_dir / "request.json",
        original_ui_path=turn_dir / "original.ui.json",
        before_py_path=turn_dir / "before.py",
        after_py_path=turn_dir / "after.py",
        model_request_path=turn_dir / "model_request.json",
        model_response_path=turn_dir / "model_response.json",
        candidate_ui_path=turn_dir / "candidate.ui.json",
        revision_evidence_path=turn_dir / "revision_evidence.json",
        projection_path=turn_dir / "projection.txt",
        messages_path=turn_dir / "messages.jsonl",
    )
    research_summary = payload.get("research_summary")
    if isinstance(research_summary, str) and research_summary.strip():
        state.executor_research_summary = research_summary.strip()
    research_warnings: list[str] = []
    raw_research_warnings = payload.get("research_warnings")
    if isinstance(raw_research_warnings, list):
        research_warnings.extend(
            warning.strip()
            for warning in raw_research_warnings
            if isinstance(warning, str) and warning.strip()
        )
    executor_research = payload.get("executor_research")
    if isinstance(executor_research, dict):
        raw_executor_warnings = executor_research.get("warnings")
        if isinstance(raw_executor_warnings, list):
            research_warnings.extend(
                warning.strip()
                for warning in raw_executor_warnings
                if isinstance(warning, str) and warning.strip()
            )
    if research_warnings:
        state.executor_research_warnings = tuple(dict.fromkeys(research_warnings))
    research_sources = payload.get("research_sources")
    if isinstance(research_sources, list):
        state.executor_research_sources = tuple(
            source for source in research_sources if isinstance(source, dict)
        )
    precedent_slices = payload.get("precedent_slices")
    if isinstance(precedent_slices, list):
        state.executor_precedent_slices = tuple(
            s for s in precedent_slices if isinstance(s, dict)
        )
    adaptation_plan = payload.get("adaptation_plan")
    if isinstance(adaptation_plan, dict):
        state.executor_adaptation_plan = adaptation_plan
    research_brief = payload.get("research_brief")
    if isinstance(research_brief, dict):
        state.executor_research_brief = research_brief
    protocol_notes = payload.get("execution_protocol_notes")
    if isinstance(protocol_notes, dict):
        state.execution_protocol_notes = protocol_notes
    context_packet = payload.get("research_context_packet")
    if isinstance(context_packet, dict):
        state.research_context_packet = context_packet
    if isinstance(payload.get("max_batches"), int) and payload["max_batches"] > 0:
        state.batch_max_turns = int(payload["max_batches"])
    if (
        isinstance(payload.get("max_consecutive_errors"), int)
        and payload["max_consecutive_errors"] > 0
    ):
        state.batch_max_consecutive_errors = int(payload["max_consecutive_errors"])

    contract = agent_edit_contract()

    raw_route = payload.get("route") if isinstance(payload.get("route"), str) else None
    executor_route = payload.get("executor_route") if isinstance(payload.get("executor_route"), str) else raw_route
    provider_route = payload.get("provider_route") if isinstance(payload.get("provider_route"), str) else raw_route
    route = canonical_route(executor_route)
    model = payload.get("model") if isinstance(payload.get("model"), str) else None
    state.route = route

    conversation_messages: list[dict[str, Any]] | None = None
    if contract == "batch_repl":
        try:
            chat = read_session_chat(session_root, session_id, max_messages=prompt_memory_messages)
            if chat.get("ok") and isinstance(chat.get("messages"), list):
                conversation_messages = chat["messages"]
                conversation_messages = conversation_with_candidate_reference(
                    conversation_messages,
                    chat.get("latest_candidate"),
                )
        except Exception:
            conversation_messages = None

    try:
        if contract == "batch_repl":
            state = run_batch(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
                client_id=client_id,
                conversation_messages=conversation_messages,
            )
        elif contract == "delta":
            state = run_delta(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
            )
        else:
            state = run_full(
                state,
                context,
                deepseek_client=deepseek_client,
                route=provider_route,
                model=model,
            )
    except stage_blocked_type as blocked:
        stage_name = blocked.failure.stage if blocked.failure is not None else blocked.result.stage
        response = validated_response(
            _failure_response(
                state,
                context,
                contract=contract,
                failure=blocked.failure or classify_failure(blocked.result.stage, blocked, context),
            ),
            stage=stage_name,
        )
        write_turn_chat_artifact(state, context, response, contract)
        record_idempotent_response(
            session_root=session_root,
            session_id=session_id,
            scope="edit",
            idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
            request_hash=allocation.request_hash,
            response=response,
            response_path=turn_dir / "response.json",
            operation="edit",
            turn_id=context.turn_id,
        )
        return response

    state.route = route

    if contract == "delta":
        response = validated_response(build_dev_success(state, context, contract=contract), stage="submit")
    elif contract == "batch_repl":
        response = validated_response(build_batch_response(state, context), stage="submit")
    else:
        response = validated_response(build_dev_success(state, context, contract=contract), stage="submit")
    try:
        if contract == "delta":
            record_stage(
                context,
                StageResult(stage="audit", ok=True, blocking=False, value={"mode": "agent_edit_v2_delta"}),
            )
        elif contract == "batch_repl":
            record_stage(
                context,
                StageResult(stage="audit", ok=True, blocking=False, value={"mode": state.batch_exit_mode or "batch_repl"}),
            )
        audit_ref = stage_audit(state, context, response=response)
        response["audit_ref"] = audit_ref.to_dict()
    except Exception as exc:
        failure = failure_envelope(
            FailureKind.AUDIT_WRITE_FAILURE,
            "audit",
            context,
            agent_failure_context={"explanation": str(exc)},
            audit_error=str(exc),
        )
        return validated_response(product_failure_response(failure), stage="audit")
    response = validated_response(response, stage="submit")
    write_turn_chat_artifact(state, context, response, contract)
    record_idempotent_response(
        session_root=session_root,
        session_id=session_id,
        scope="edit",
        idempotency_key=payload.get("idempotency_key") if isinstance(payload.get("idempotency_key"), str) else None,
        request_hash=allocation.request_hash,
        response=response,
        response_path=turn_dir / "response.json",
        operation="edit",
        turn_id=context.turn_id,
    )
    return response
