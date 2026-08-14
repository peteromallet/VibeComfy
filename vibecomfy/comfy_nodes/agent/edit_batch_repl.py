"""EditBatchReplDeps — invocation-time dependency object for the agent batch REPL.

WHY A DEPENDENCY OBJECT
    The batch REPL is the agent-edit batch loop: the three stitched source
    fragments ``edit_batch_loop_intro`` / ``edit_batch_loop_apply`` /
    ``edit_batch_loop_finish`` (group 11 of the old exec-assembler source
    groups in ``vibecomfy/comfy_nodes/agent/edit.py``). The assembler exec'd
    every fragment into one shared namespace, so the loop resolves all its
    names from that globals dict. Once the loop is extracted into its own
    module (T-037)
    it CANNOT use normal imports: a scope-aware analysis of the three fragments
    shows 77 names they reference are not defined inside them, and 72 of those
    (55 private + 17 public) are defined in OTHER exec'd host fragments
    (edit_state, edit_humanize, edit_batch_reports, ...). Those hosts are
    themselves stitched by the same exec machinery, so their private helpers
    and classes are not importable as module attributes. The only reliable
    source of bindings is the assembled façade namespace itself — hence this
    dependency object.

HOW IT WORKS
    ``build_edit_batch_repl_deps(globals_dict)`` resolves every field AT
    INVOCATION TIME from the caller-supplied mapping (typically the edit
    façade module's ``globals()`` after assembly) and returns a frozen
    ``EditBatchReplDeps``. The factory is the only supported constructor.
    Missing names raise ``MissingEditBatchReplDepsError`` (a ``KeyError``
    subclass) whose message lists the missing names; the T-036 surface test
    relies on that error shape.

NO SINGLETON
    The façade namespace is rebuilt whenever the exec assembler re-runs, so a
    module-level snapshot would go stale (or capture a different namespace).
    There is deliberately no module-level ``EditBatchReplDeps`` instance and
    no cached build: every call re-resolves from the mapping handed to it,
    which also lets tests and alternate façade instances rebuild per
    invocation.

STDLIB-ONLY IMPORT POLICY
    This module imports only the stdlib (``dataclasses``, ``typing``). No
    package imports at module top level: all package-level name resolution
    happens through the passed-in globals at build time. ``json`` / ``time`` /
    ``importlib`` joined the stdlib import surface at T-037 when the extracted
    batch-loop body moved in below; they were excluded from the field set for
    exactly that reason. The loop body's former function-local
    ``from ... import ...`` statements were converted to runtime
    ``importlib.import_module`` / ``_import_from`` calls so this module keeps
    its stdlib-only import surface (enforced by the T-036 deps test).

THE 72-NAME FIELD SET
    Derived mechanically from the fragments' free names (scope-aware
    ``symtable`` analysis of the concatenated fragment source): 80 external
    names, of which 5 are stdlib-importable (``Any``, ``Mapping``,
    ``dataclasses``, ``json``, ``time``) and 72 are real dependencies — the S4
    ground truth: 55 private + 17 public across the 18 host fragment modules
    (19 modules counting the ``edit.py`` façade itself). Fields are grouped
    private-then-public, alphabetical, each annotated with the host fragment
    that defines it. Every field is ``Any``-typed on purpose: the concrete
    type of each binding is owned by its host fragment and cannot be known
    here without inventing an import dependency.

CONTRACT FOR T-037..T-041
    - T-037 (done): the batch-loop body now lives in this module as real
      functions. It references the façade only through ``deps.<name>``; the
      loop's own names (``_stage_agent_batch_repl`` and the 23 helper
      functions) stay local to this module and never appear as fields. The
      edit façade keeps ``_stage_agent_batch_repl`` as a thin delegate that
      passes its own ``globals()`` here at call time (no module-level
      singleton).
    - T-036: the surface test asserts the missing-name error below.
    - T-041: once the exec assembler is removed, the façade module passes its
      own ``globals()`` here; nothing else needs to change.
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import os
import time
from dataclasses import dataclass, fields
from typing import Any, Mapping


class MissingEditBatchReplDepsError(KeyError):
    """Façade globals lacked one or more names the batch REPL requires.

    Raised by :func:`build_edit_batch_repl_deps` when the supplied mapping
    does not contain every name in :data:`REQUIRED_DEPENDENCY_NAMES`. The
    message lists the missing names so callers (and the T-036 surface test)
    can report exactly what the façade failed to provide.
    """


@dataclass(frozen=True, slots=True)
class EditBatchReplDeps:
    """Resolved batch-REPL dependencies, bound to concrete façade objects.

    Every field is resolved at invocation time by
    :func:`build_edit_batch_repl_deps` from the assembled agent-edit
    namespace; see the module docstring for the design rationale.
    """

    # -- private façade helpers (55) --
    _BATCH_EXIT_BUDGET: Any  # host: _frag_batch_reports
    _BATCH_EXIT_DONE: Any  # host: _frag_batch_reports
    _BATCH_EXIT_EDIT_CLARIFY: Any  # host: _frag_batch_reports
    _BATCH_EXIT_NOOP: Any  # host: _frag_batch_reports
    _BATCH_EXIT_PURE_CLARIFY: Any  # host: _frag_batch_reports
    _BATCH_EXIT_STUCK: Any  # host: _frag_batch_reports
    _agent_edit_batch_repl_enabled: Any  # host: _frag_session_bundle
    _artifact: Any  # host: _frag_state
    _batch_budget_artifixer_report: Any  # host: _frag_batch_reports
    _batch_budget_failure_kind: Any  # host: _frag_batch_reports
    _batch_candidate_graph_changed: Any  # host: _frag_humanize
    _batch_research_memory_summary: Any  # host: _frag_batch_memory
    _build_graph_report: Any  # host: _frag_research
    _candidate_dict: Any  # host: _frag_research
    _candidate_stable_key: Any  # host: _frag_response_contract
    _canonical_agent_edit_route: Any  # host: _frag_research
    _compact_diag_to_dict: Any  # host: _frag_session_bundle
    _discovery_construction_nudge: Any  # host: _frag_state
    _discovery_stop_message: Any  # host: _frag_state
    _duplicate_search_cycle_feedback: Any  # host: _frag_batch_reports
    _duration_ms: Any  # host: _frag_state
    _edit_lint_enabled: Any  # host: _frag_session_bundle
    _edit_noop_requires_graph_evidence_feedback: Any  # host: _frag_batch_memory
    _effective_implementation_task: Any  # host: _frag_research
    _emit_agent_edit_turn_event: Any  # host: _frag_entrypoint
    _enrich_schema_provider_from_resolver_candidates: Any  # host: _frag_response_contract
    _extract_search_signatures: Any  # host: _frag_batch_reports
    _field_changes_payload: Any  # host: _frag_chat
    _finalize_revision_evidence_with_candidate: Any  # host: _frag_revision_stages
    _focus_types_from_research_brief: Any  # host: _frag_revision
    _format_available_node_names: Any  # host: _frag_batch_memory
    _format_batch_report: Any  # host: _frag_batch_reports
    _format_batch_report_json: Any  # host: _frag_batch_reports
    _format_node_variable_index: Any  # host: _frag_batch_memory
    _format_research_brief_for_prompt: Any  # host: _frag_state
    _hydrate_research_precedent_node_schemas: Any  # host: _frag_research
    _is_code_node_intent: Any  # host: _frag_research
    _is_graph_explain_intent: Any  # host: _frag_research
    _json_safe: Any  # host: _frag_chat
    _noop_field_changes: Any  # host: _frag_humanize
    _normalize_test_client_batch_response: Any  # host: _frag_batch_memory
    _prefetch_research_summary: Any  # host: _frag_research
    _premature_missing_custom_node_clarify_feedback: Any  # host: _frag_batch_memory
    _present_class_types: Any  # host: _frag_batch_memory
    _read_only_discovery_turn_count: Any  # host: _frag_state
    _real_field_changes: Any  # host: _frag_humanize
    _render_batch_diff: Any  # host: _frag_batch_memory
    _resolver_candidate_supports_class: Any  # host: _frag_research
    _resolver_candidates_from_batch_result: Any  # host: _frag_response_contract
    _revision_candidate_retry_hint: Any  # host: _frag_humanize
    _revision_evidence_prompt_json: Any  # host: _frag_revision_stages
    _selected_precedent_unknown_class_feedback: Any  # host: _frag_batch_memory
    _workflow_class_types_from_research_context: Any  # host: _frag_research
    _workflow_schema_candidates_from_research_context: Any  # host: _frag_research

    # -- public façade names (17) --
    AgentEditState: Any  # host: _frag_state
    DeepSeekClient: Any  # host: _frag_state
    FailureKind: Any  # host: _frag_state
    LOGGER: Any  # hosts: edit_state, edit_response_contract
    MalformedModelJSON: Any  # host: _frag_state
    MissingRequiredField: Any  # host: _frag_state
    StageResult: Any  # host: _frag_state
    TurnContext: Any  # host: _frag_state
    build_batch_messages: Any  # host: _frag_state
    ensure_sentence_message: Any  # host: _frag_state
    evaluate_execution_plan_for_state: Any  # host: _frag_state
    format_compact_plan_status: Any  # host: _frag_state
    repair_field_changes: Any  # host: _frag_state
    run_agent_turn_batch: Any  # host: _frag_state
    split_terminal_clarify: Any  # host: _frag_batch_reports
    structural_graph_hash: Any  # host: _frag_state
    write_json_artifact: Any  # host: _frag_state


REQUIRED_DEPENDENCY_NAMES: frozenset[str] = frozenset(
    field.name for field in fields(EditBatchReplDeps)
)


def build_edit_batch_repl_deps(globals_dict: Mapping[str, Any]) -> EditBatchReplDeps:
    """Resolve an :class:`EditBatchReplDeps` from a façade globals mapping.

    Resolution happens at call time against ``globals_dict`` (typically the
    assembled ``edit.py`` namespace, i.e. its ``globals()``); nothing is
    cached at module level, so the deps can be rebuilt per invocation.

    Args:
        globals_dict: Mapping of name -> binding from the assembled agent-edit
            façade. Missing names raise :class:`MissingEditBatchReplDepsError`
            listing them.

    Returns:
        A frozen :class:`EditBatchReplDeps` with every field bound to the
        value found in ``globals_dict``.
    """
    missing = sorted(REQUIRED_DEPENDENCY_NAMES - set(globals_dict))
    if missing:
        raise MissingEditBatchReplDepsError(
            f"build_edit_batch_repl_deps: {len(missing)} of {len(REQUIRED_DEPENDENCY_NAMES)} "
            f"required dependency names are missing from the façade globals: {missing}. "
            "Pass the assembled agent-edit namespace (the edit façade module's globals()); "
            "these names are defined inside other exec'd fragments and cannot be imported."
        )
    return EditBatchReplDeps(
        **{name: globals_dict[name] for name in REQUIRED_DEPENDENCY_NAMES}
    )




def _import_from(module_path: str, name: str) -> Any:
    """Runtime stand-in for ``from <module_path> import <name>``.

    The T-037 extraction keeps this module stdlib-only at import time, so the
    batch loop's former function-local package imports (``from vibecomfy.porting
    .edit import session`` etc.) are resolved lazily at call time instead. This
    helper is only ever called from inside the extracted loop functions.
    """
    return getattr(importlib.import_module(module_path), name)


# ── Research collection fold (B03) ──────────────────────────────────────────
# Transport plumbing only: cross-turn union of message/distillation sources and
# last-write-wins paragraphs, folded from each live StatementResult.detail right
# after resolve.  No ranking, no IDF, no "stronger row" selection, no latch, no
# evidence card, and no stop decision.  The agent already saw every row in
# query_output and judges relevance itself.



def _batch_protocol_parse_reason(exc: BaseException) -> str:
    explicit = getattr(exc, "parse_reason", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    text = str(exc).lower()
    if "empty" in text:
        return "empty"
    if "multiple" in text:
        return "multiple_batch_fences"
    if "must be a string" in text or "non_string" in text:
        return "non_string"
    if "batch fenced block" in text or "batch code block" in text:
        return "missing_batch_fence"
    return "malformed"


def _batch_protocol_retry_messages(
    messages: list[dict[str, str]],
    exc: BaseException | None = None,
) -> list[dict[str, str]]:
    from vibecomfy.comfy_nodes.agent._frag_batch_loop import _BATCH_PROTOCOL_RETRY_PROMPT  # noqa: PLC0415
    from vibecomfy.comfy_nodes.agent.edit import _malformed_model_json_detail  # noqa: PLC0415

    prompt = _BATCH_PROTOCOL_RETRY_PROMPT
    if exc is not None:
        detail = _malformed_model_json_detail(exc)
        raw_preview = detail.get("raw_response_preview")
        if raw_preview:
            prompt = (
                f"{prompt}\n\n"
                "Previous response preview, for correction only:\n"
                f"{raw_preview}"
            )
    return [*messages, {"role": "system", "content": prompt}]


def _evaluate_execution_plan_after_candidate_update(deps, state: AgentEditState) -> dict[str, Any]:
    if getattr(state, "execution_plan", None) is None:
        return {}
    if not isinstance(state.ui_payload, Mapping):
        return {}
    update = deps.evaluate_execution_plan_for_state(
        state,
        state.ui_payload,
        candidate_graph_hash=deps.structural_graph_hash(state.ui_payload),
    )
    return dict(update.compact_status or {})


def _execution_plan_status_for_prompt(deps, state: AgentEditState) -> dict[str, Any]:
    if getattr(state, "execution_plan", None) is None:
        return {}
    return deps.format_compact_plan_status(state.execution_plan, state.plan_evaluation)


def _execution_plan_done_refusal_hint(state: AgentEditState) -> str:
    evaluation = getattr(state, "plan_evaluation", None)
    if evaluation is None:
        return "the execution plan has not been evaluated yet."
    failed_condition_ids = [
        str(condition.get("condition_id") or condition.get("id") or "unknown_condition")
        for condition in getattr(evaluation, "failed_conditions", ()) or ()
        if isinstance(condition, Mapping)
    ]
    advisory_miss_ids = [
        str(item.get("step_id") or "unknown_step")
        for item in getattr(evaluation, "diagnostics", ()) or ()
        if isinstance(item, Mapping)
        and str(item.get("kind") or "") == "advisory_step_miss"
    ]
    parts = [
        "the execution plan's declared safety/invariant conditions still block completion.",
        f"plan_id={getattr(evaluation, 'plan_id', 'unknown')}",
    ]
    if failed_condition_ids:
        parts.append(
            "failed execution-plan condition ids: "
            + ", ".join(failed_condition_ids)
        )
    if advisory_miss_ids:
        parts.append(
            "advisory execution-plan step misses (these do NOT block done, "
            "but review whether the intended structure was built another way): "
            + ", ".join(advisory_miss_ids)
        )
    feedback = str(getattr(evaluation, "feedback", "") or "").strip()
    if feedback:
        parts.append(feedback)
    parts.append(
        "Fix the failing plan conditions (invariants) and call done() again."
    )
    return " ".join(parts)


def _done_validation_repair_hint(
    deps: "EditBatchReplDeps",
    done_diagnostics: tuple[Any, ...] | list[Any],
    *,
    limit: int = 5,
) -> str:
    """Render bounded done() validation diagnostics as a repair brief.

    Each diagnostic carries its code, message, target (node/input/id) and the
    declared choices so the model can repair the exact failing surface in the
    one allowed follow-up turn.
    """
    lines: list[str] = []
    shown = 0
    total = len(done_diagnostics or ())
    for diagnostic in done_diagnostics or ():
        if shown >= limit:
            lines.append(
                f"... and {total - shown} more diagnostic(s); fix every reported "
                "error before calling done() again."
            )
            break
        compact = deps._compact_diag_to_dict(diagnostic)
        detail = compact.get("detail")
        if not isinstance(detail, dict):
            detail = {}
        target_bits: list[str] = []
        class_type = detail.get("class_type")
        input_name = detail.get("input")
        node_id = detail.get("node_id")
        if isinstance(class_type, str) and class_type:
            target_bits.append(f"node={class_type}")
        if isinstance(input_name, str) and input_name:
            target_bits.append(f"input={input_name}")
        if node_id is not None:
            target_bits.append(f"id={node_id}")
        choices = detail.get("choices")
        line = f"[{compact.get('code')}] {compact.get('message')}"
        if target_bits:
            line += f" (target: {' '.join(target_bits)})"
        if isinstance(choices, (list, tuple)) and choices:
            line += (
                "; declared choices: "
                + ", ".join(str(choice) for choice in choices[:6])
            )
        lines.append(f"- {line}")
        shown += 1
    if not lines:
        return (
            "the candidate failed final validation; repair every reported "
            "validation error, then call done() again."
        )
    return (
        "the candidate failed final validation. Repair the following "
        "validation error(s), then call done() again:\n" + "\n".join(lines)
    )



def _manifest_is_complete(manifest: Any) -> bool:
    """Return True when *manifest* is a non-empty manifest mapping.

    Used to gate the manifest-preferred compact-notes path.  A None, missing,
    or empty manifest keeps the legacy compact-notes behavior byte-for-byte.
    """
    return isinstance(manifest, Mapping) and bool(manifest)


def _active_manifest_from_plan(deps,
    adaptation_plan: Any,
    *,
    route: str | None,
) -> tuple[bool, Mapping[str, Any] | None]:
    """Return ``(manifest_active, manifest)`` for the W-07 compact-notes path.

    The manifest path is active ONLY when the canonical route is ``adapt`` AND
    the plan carries a complete ``topology_manifest`` mapping.  REPAIR/DEBUG
    (``revise``) and any non-adapt route keep today's legacy behavior.  Returns
    ``(False, None)`` in those cases so the caller's compact notes are
    byte-identical to the legacy path.
    """
    if deps._canonical_agent_edit_route(route) != "adapt":
        return (False, None)
    if not isinstance(adaptation_plan, Mapping):
        return (False, None)
    manifest = adaptation_plan.get("topology_manifest")
    if not _manifest_is_complete(manifest):
        return (False, None)
    return (True, manifest)



def _dependency_graph_class_types(graph: Any) -> tuple[str, ...]:
    """Return class types from UI/API graphs in stable encounter order."""
    if not isinstance(graph, Mapping):
        return ()

    ordered: list[str] = []
    seen: set[str] = set()

    def add_node(node: Any) -> None:
        if not isinstance(node, Mapping):
            return
        raw = node.get("class_type") or node.get("type")
        class_type = str(raw or "").strip()
        if (
            class_type
            and class_type != "Unknown"
            and not _is_ui_only_annotation_class_type(class_type)
            and class_type not in seen
        ):
            seen.add(class_type)
            ordered.append(class_type)

    def visit(scope: Mapping[str, Any]) -> None:
        nodes = scope.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                add_node(node)
        elif isinstance(nodes, Mapping):
            for node in nodes.values():
                add_node(node)
        else:
            # Comfy API graphs store node records directly under numeric ids.
            for key, node in scope.items():
                if str(key).isdigit():
                    add_node(node)

        definitions = scope.get("definitions")
        if isinstance(definitions, Mapping):
            for definition in definitions.values():
                if isinstance(definition, Mapping):
                    visit(definition)

    visit(graph)
    return tuple(ordered)


def _is_ui_only_annotation_class_type(class_type: Any) -> bool:
    """Use the shared conservative annotation classifier."""
    is_ui_only_annotation_class_type = _import_from("vibecomfy.executor.contracts", "is_ui_only_annotation_class_type")

    return is_ui_only_annotation_class_type(class_type)


def _actionable_plan_ui_only_classes(plan: Mapping[str, Any]) -> tuple[str, ...]:
    """Return annotation classes ignored by dependency preflight."""
    ignored: list[str] = []

    def consider(raw: Any) -> None:
        class_type = str(raw or "").strip()
        if (
            class_type
            and _is_ui_only_annotation_class_type(class_type)
            and class_type not in ignored
        ):
            ignored.append(class_type)

    explicit = plan.get("required_new_nodes")
    if isinstance(explicit, (list, tuple)):
        for record in explicit:
            if isinstance(record, Mapping):
                consider(
                    record.get("class_type")
                    or record.get("node_type")
                    or record.get("type")
                )
    candidate_graph = plan.get("candidate_graph")
    if isinstance(candidate_graph, Mapping):
        nodes = candidate_graph.get("nodes")
        records = (
            nodes
            if isinstance(nodes, list)
            else nodes.values()
            if isinstance(nodes, Mapping)
            else candidate_graph.values()
        )
        for record in records:
            if isinstance(record, Mapping):
                consider(record.get("class_type") or record.get("type"))
    return tuple(ignored)


def _manifest_required_new_classes(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Derive runtime dependency classes from a complete manifest's nodes.

    Reads ONLY ``nodes[].canonical_class_type`` (the authoritative class set).
    Never introduces classes from goldens, filenames, fixture labels, or
    ``prior_path``.  UI-only annotation classes are filtered out via the shared
    conservative classifier.
    """
    if not isinstance(manifest, Mapping):
        return ()
    nodes_raw = manifest.get("nodes")
    if not isinstance(nodes_raw, (list, tuple)):
        return ()
    ordered: list[str] = []
    seen: set[str] = set()
    for node in nodes_raw:
        if not isinstance(node, Mapping):
            continue
        raw = node.get("canonical_class_type")
        class_type = str(raw or "").strip()
        if (
            class_type
            and class_type != "Unknown"
            and not _is_ui_only_annotation_class_type(class_type)
            and class_type not in seen
        ):
            seen.add(class_type)
            ordered.append(class_type)
    return tuple(ordered)


def _actionable_plan_required_new_classes(deps,
    state: AgentEditState,
    plan: Mapping[str, Any],
) -> tuple[str, ...]:
    """Derive new runtime classes from every concrete typed-plan witness.

    W-07 — when the plan carries a COMPLETE ``topology_manifest`` on the
    canonical ``adapt`` route, runtime dependency classes are derived from the
    manifest's ``nodes[].canonical_class_type`` (the authoritative class set),
    and the legacy candidate/slice class discovery is fallback-only.
    ``required_new_nodes`` is advisory and can be empty even when the typed
    candidate graph contains copied precedent nodes.  The candidate graph is
    therefore the primary completeness witness on the legacy path.  A selected
    slice is used only when no candidate graph or explicit node list exists.
    """
    target_graph = state.guard_original_ui or state.graph
    target_classes = set(_dependency_graph_class_types(target_graph))
    required: list[str] = []

    def add_class(raw: Any) -> None:
        class_type = str(raw or "").strip()
        if (
            class_type
            and class_type != "Unknown"
            and class_type not in target_classes
            and class_type not in required
        ):
            required.append(class_type)

    # W-07 — manifest-preferred dependency derivation.  When a complete
    # manifest is present on the adapt route, its canonical_class_type set is
    # the authoritative class set; legacy candidate/slice discovery runs as a
    # fallback ONLY when no complete manifest exists.
    manifest_active, manifest = _active_manifest_from_plan(deps,
        plan, route=state.route
    )
    if manifest_active and manifest is not None:
        manifest_classes = _manifest_required_new_classes(manifest)
        if manifest_classes:
            for class_type in manifest_classes:
                add_class(class_type)
            return tuple(required)
        # Empty manifest class set (all classes already on target or filtered)
        # — fall through to legacy discovery so we don't silently lose deps.

    explicit = plan.get("required_new_nodes")
    if isinstance(explicit, (list, tuple)):
        for record in explicit:
            if not isinstance(record, Mapping):
                continue
            add_class(
                record.get("class_type")
                or record.get("node_type")
                or record.get("type")
            )

    candidate_graph = plan.get("candidate_graph")
    if isinstance(candidate_graph, Mapping):
        for class_type in _dependency_graph_class_types(candidate_graph):
            add_class(class_type)
    elif not required:
        # Legacy typed plans may carry only their selected slice.  Treat its
        # node types as requirements only when no stronger concrete witness
        # exists, and subtract every class already present on the target.
        selected_slice = plan.get("selected_slice")
        if isinstance(selected_slice, Mapping):
            node_types = selected_slice.get("node_types")
            if isinstance(node_types, (list, tuple)):
                for class_type in node_types:
                    add_class(class_type)

    return tuple(required)


def _actionable_plan_dependency_status(deps,
    state: AgentEditState,
) -> tuple[dict[str, Any], ...]:
    """Classify planned new classes as live, registry-resolvable, or unresolved.

    Absence from the live ``/object_info`` provider is not itself a blocker:
    custom nodes may be authorable from registry/workflow evidence before the
    pack is installed.  Only a class with neither live schema nor an exact
    registry candidate is unresolved.
    """
    notes = state.execution_protocol_notes
    if not isinstance(notes, Mapping):
        return ()
    actionability = notes.get("adaptation_plan_actionability")
    plan = notes.get("adaptation_plan")
    if (
        not isinstance(actionability, Mapping)
        or actionability.get("actionability") != "actionable"
        or not isinstance(plan, Mapping)
    ):
        return ()
    schema_for = _import_from("vibecomfy.schema", "schema_for")

    dependencies: list[dict[str, Any]] = []
    for class_type in _actionable_plan_required_new_classes(deps, state, plan):
        if schema_for(state.schema_provider, class_type) is not None:
            dependencies.append(
                {"class_type": class_type, "availability": "live_available"}
            )
            continue

        candidates = [
            dict(candidate)
            for candidate in deps._workflow_schema_candidates_from_research_context(state)
            if deps._resolver_candidate_supports_class(candidate, class_type)
        ]
        warnings: list[str] = []
        attempted: list[str] = []
        try:
            resolve_missing_nodes = _import_from("vibecomfy.registry.pack_resolver", "resolve_missing_nodes")

            resolution = resolve_missing_nodes(class_type, query_intent="class_name")
            warnings.extend(
                str(item)
                for item in (getattr(resolution, "warnings", ()) or ())
                if str(item).strip()
            )
            registry_resolution_is_ambiguous = any(
                "ambiguous" in warning.casefold()
                for warning in warnings
            )
            attempted.extend(
                str(item)
                for item in (getattr(resolution, "source_tiers_attempted", ()) or ())
                if str(item).strip()
            )
            for raw_candidate in getattr(resolution, "candidates", ()) or ():
                candidate = deps._candidate_dict(raw_candidate)
                pack = candidate.get("pack") if isinstance(candidate, Mapping) else None
                source = (
                    str(pack.get("source") or "").strip().lower()
                    if isinstance(pack, Mapping)
                    else ""
                )
                if (
                    candidate is not None
                    and source
                    in {
                        "comfy-registry",
                        "comfy_registry",
                        "comfyui-manager",
                        "comfy-manager",
                    }
                    and (
                        deps._resolver_candidate_supports_class(candidate, class_type)
                        or (
                            source in {"comfy-registry", "comfy_registry"}
                            and not registry_resolution_is_ambiguous
                        )
                    )
                ):
                    if deps._candidate_stable_key(candidate) not in {
                        deps._candidate_stable_key(existing) for existing in candidates
                    }:
                        candidates.append(candidate)
        except Exception as exc:  # noqa: BLE001 - unresolved is the safe result
            warnings.append(f"{type(exc).__name__}: {exc}")

        record: dict[str, Any] = {
            "class_type": class_type,
            "availability": (
                "registry_resolvable" if candidates else "unresolved"
            ),
        }
        if candidates:
            record["resolver_candidates"] = candidates
        if attempted:
            record["source_tiers_attempted"] = list(dict.fromkeys(attempted))
        if warnings:
            record["warnings"] = list(dict.fromkeys(warnings))
        dependencies.append(record)
    return tuple(dependencies)


def _hydrate_actionable_registry_dependencies(deps, state: AgentEditState) -> None:
    candidates: list[dict[str, Any]] = []
    for dependency in state.runtime_dependencies:
        if dependency.get("availability") != "registry_resolvable":
            continue
        raw_candidates = dependency.get("resolver_candidates")
        if isinstance(raw_candidates, list):
            candidates.extend(
                dict(candidate)
                for candidate in raw_candidates
                if isinstance(candidate, Mapping)
            )
    new_candidates = [
        candidate
        for candidate in candidates
        if deps._candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return
    try:
        CompositeSchemaProvider, ProvisionalRegistrySchemaProvider = _import_from("vibecomfy.schema", "CompositeSchemaProvider"), _import_from("vibecomfy.schema", "ProvisionalRegistrySchemaProvider")
        with_provisional_gap_filler = _import_from("vibecomfy.schema", "with_provisional_gap_filler")

        provisional = ProvisionalRegistrySchemaProvider(new_candidates)
        if not provisional.schemas():
            return
        state.provisional_registry_candidate_hashes = frozenset(
            {
                *state.provisional_registry_candidate_hashes,
                *(deps._candidate_stable_key(candidate) for candidate in new_candidates),
            }
        )
        state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
    except Exception as exc:  # noqa: BLE001 - workflow evidence may still hydrate it
        deps.LOGGER.debug("planned registry dependency hydration unavailable: %s", exc)


def _stage_agent_batch_repl(globals_dict: Mapping[str, Any],
    state: AgentEditState,
    _context: TurnContext,
    *,
    deepseek_client: DeepSeekClient | None = None,
    route: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    client_id: str | None = None,
    conversation_messages: list[dict[str, Any]] | None = None,
) -> deps.StageResult:
    deps = build_edit_batch_repl_deps(globals_dict)
    edit_session_module = importlib.import_module("vibecomfy.porting.edit.session")
    ValueDefaultContext = _import_from("vibecomfy.porting.edit.apply_types", "ValueDefaultContext")

    start = time.monotonic()
    prepared_ui = state.guard_original_ui or state.graph
    state.runtime_dependencies = _actionable_plan_dependency_status(deps, state)
    unresolved_runtime_classes = tuple(
        str(dependency.get("class_type"))
        for dependency in state.runtime_dependencies
        if dependency.get("availability") == "unresolved"
    )
    if unresolved_runtime_classes:
        # Hard-block: planned runtime classes with neither a live schema nor an
        # exact registry candidate cannot be authored against.  Stop BEFORE the
        # model is called and surface a clarification (HEAD contract).  Do NOT
        # fall through to authoring and do NOT retry by discarding the plan —
        # there is nothing to retry with.  (W-07's dependency_preflight.json
        # diagnostic is preserved as a write-only artifact alongside the
        # clarification artifacts.)
        missing_text = ", ".join(unresolved_runtime_classes)
        message = (
            "This edit requires custom-node classes that could not be found in "
            f"the live ComfyUI runtime or Comfy Registry: {missing_text}. "
            "Install or identify the providing custom-node pack, restart ComfyUI, "
            "and then retry this edit."
        )
        deps.write_json_artifact(
            state.turn_dir / "dependency_preflight.json",
            {
                "ignored_ui_annotation_classes": list(
                    _actionable_plan_ui_only_classes(
                        state.execution_protocol_notes.get("adaptation_plan")
                        if isinstance(state.execution_protocol_notes, Mapping)
                        else None
                    )
                    if isinstance(state.execution_protocol_notes, Mapping)
                    else ()
                ),
                "unresolved_runtime_classes": list(unresolved_runtime_classes),
                "runtime_dependencies": list(state.runtime_dependencies),
                "retrying_synthesis": False,
            },
        )
        state.batch_exit_mode = deps._BATCH_EXIT_PURE_CLARIFY
        state.batch_final_summary = "Stopped before authoring because dependencies are unresolved."
        state.user_message = message
        state.report = {
            "clarification_required": True,
            "graph_unchanged": True,
            "queue_blockers": [],
            "authoring_blocker": {
                "reason": "unresolved_runtime_classes",
                "missing_runtime_classes": list(unresolved_runtime_classes),
                "runtime_dependencies": list(state.runtime_dependencies),
                "message": message,
            },
        }
        state.python_before = ""
        state.python_after = ""
        state.before_py_path.write_text("", encoding="utf-8")
        state.after_py_path.write_text("", encoding="utf-8")
        deps.write_json_artifact(state.model_request_path, {"turns": []})
        deps.write_json_artifact(
            state.model_response_path,
            {
                "turns": [],
                "clarification": {
                    "reason": "unresolved_runtime_classes",
                    "message": message,
                },
            },
        )
        deps.write_json_artifact(state.candidate_ui_path, prepared_ui)
        state.messages_path.write_text(
            json.dumps(
                {
                    "authoring_blocker": "unresolved_runtime_classes",
                    "clarification_required": message,
                    "message": message,
                    "missing_runtime_classes": list(unresolved_runtime_classes),
                    "runtime_dependencies": list(state.runtime_dependencies),
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return deps.StageResult(
            stage="agent_batch",
            ok=True,
            blocking=False,
            duration_ms=deps._duration_ms(start),
            artifacts=(
                deps._artifact(state.before_py_path),
                deps._artifact(state.after_py_path),
                deps._artifact(state.model_request_path),
                deps._artifact(state.model_response_path),
                deps._artifact(state.candidate_ui_path),
                deps._artifact(state.messages_path),
            ),
            value={
                "mode": "unresolved_runtime_classes",
                "graph_unchanged": True,
                "missing_runtime_classes": list(unresolved_runtime_classes),
                "runtime_dependencies": list(state.runtime_dependencies),
            },
        )
    _hydrate_actionable_registry_dependencies(deps, state)
    deps._hydrate_research_precedent_node_schemas(state)
    # D03: executor_precedent_slices / executor_adaptation_plan removed; the
    # adaptation plan rides in execution_protocol_notes (H03 hydration
    # source). Binding priors from legacy precedent slices no longer exist.
    protocol_notes = (
        state.execution_protocol_notes
        if isinstance(state.execution_protocol_notes, Mapping)
        else None
    )
    value_default_context = ValueDefaultContext.from_precedent_slices(
        (),
        adaptation_plan=(
            protocol_notes.get("adaptation_plan")
            if isinstance(protocol_notes, Mapping)
            else None
        ),
        user_overrides=state.request_payload.get("value_default_overrides"),
        user_request=f"{state.task}\n{state.request_payload.get('query') or ''}",
    )
    # Keep the user request available for exact-value extraction even when no
    # precedent bindings exist. The resolver treats absent or ineligible
    # bindings as a no-op, so an empty/partial context cannot gate construction.
    # B03: canonical_route / research_only_route are computed BEFORE the session
    # is built so the omit-site resolver (session.research_only) can default
    # omitted research() sources= to ("messages", "web") on the research route.
    canonical_route = deps._canonical_agent_edit_route(state.route or route)
    research_only_route = canonical_route == "research"
    session = edit_session_module.EditSession(
        prepared_ui,
        schema_provider=state.schema_provider,
        value_default_context=value_default_context,
    )
    session.research_only = research_only_route
    state.batch_session = session
    initial_render = session.render()
    present_types = deps._present_class_types(session)
    focus_types = set(present_types)
    effective_task = deps._effective_implementation_task(state)
    # D03: the research brief no longer seeds focus types; workflow classes
    # come from execution_protocol_notes.research_sources (authoring surface).
    focus_types.update(
        deps._workflow_class_types_from_research_context(
            state,
            max_classes=32,
            missing_only=False,
            custom_only=False,
        )
    )
    if deps._is_code_node_intent(effective_task):
        focus_types.add("vibecomfy.exec")
    signature_catalog = session.search(
        focus_types=sorted(focus_types),
        formatted=True,
        in_graph_nodes=session.working_ui,
    )
    available_node_names = deps._format_available_node_names(session.search(formatted=False))
    state.python_before = initial_render
    state.before_py_path.write_text(initial_render, encoding="utf-8")
    if isinstance(signature_catalog, str):
        state.batch_signature_catalog = signature_catalog

    # D03: the legacy prefetch/research-summary/research-brief/graph-report/
    # precedent-adaptation/SD3-scoped-context prompt assembly is REMOVED.
    # Research context enters the model request ONLY as compact ledger
    # entries + resolvable evidence IDs (the I01
    # _tool_evidence_ledger_records path rendered into evidence_ledger below);
    # full evidence stays in the evidence-pack artifact.

    max_batches = max(1, int(state.batch_max_turns or 1))
    max_consecutive_errors = max(1, int(state.batch_max_consecutive_errors or 1))
    state.batch_budget_state = {
        "max_batches": max_batches,
        "max_consecutive_errors": max_consecutive_errors,
        "remaining_batches": max_batches,
        "remaining_consecutive_errors": max_consecutive_errors,
    }
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "revision_evidence": str(state.revision_evidence_path),
        "messages": str(state.messages_path),
    }

    current_render = initial_render
    last_diff = ""
    initial_report_notes = [
        note
        for note in (
            deps._edit_noop_requires_graph_evidence_feedback(state),
        )
        if note
    ]
    last_report = "\n\n".join(initial_report_notes)
    last_landed_count: int | None = None
    previous_model_message = ""
    consecutive_errors = 0
    total_landed = 0
    done_noop_nudges = 0
    done_error_nudges = 0
    done_candidate_rejection_nudges = 0
    done_validation_repair_turns = 0
    failed_edit_turns = 0
    last_failed_edit_turn = -1
    last_successful_edit_turn_after_failure = -1
    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []
    # Duplicate-query cycle guard (Part C): track the prior turn's search
    # signature + whether it landed anything.  When the current turn repeats an
    # IDENTICAL search() signature AND the prior landed nothing, inject
    # deterministic feedback to break the cycle.  Never fires on a first search
    # or on a search that previously succeeded.
    prior_search_signatures: tuple[str, ...] | None = None
    prior_search_landed: bool = False
    _batch_journal_mod = importlib.import_module(
        "vibecomfy.comfy_nodes.agent.batch_rollback_journal"
    )
    _entry_mod = importlib.import_module(
        "vibecomfy.comfy_nodes.agent._frag_entrypoint"
    )

    # Phase-wide deadline for the agentic research phase (cluster A). The turn
    # timeout bounds ONE worker subprocess, but a research route can loop turn
    # after turn; a slow or repeatedly-hanging worker could otherwise burn the
    # whole scenario budget. Bound the entire research phase in wall-clock time
    # so the executor's reply phase still runs with whatever research was
    # collected. Configure with VIBECOMFY_RESEARCH_PHASE_DEADLINE (seconds;
    # 0 disables; default 600).
    research_phase_deadline: float | None = None
    research_phase_deadline_seconds = 0.0
    if research_only_route:
        try:
            research_phase_deadline_seconds = float(
                os.environ.get("VIBECOMFY_RESEARCH_PHASE_DEADLINE", "600") or 0
            )
        except ValueError:
            research_phase_deadline_seconds = 600.0
        if research_phase_deadline_seconds > 0:
            research_phase_deadline = (
                time.monotonic() + research_phase_deadline_seconds
            )

    for turn_number in range(max_batches):
        if (
            research_phase_deadline is not None
            and turn_number > 0
            and time.monotonic() >= research_phase_deadline
        ):
            # The research phase exceeded its wall-clock deadline. Stop cleanly
            # (successful noop — research never changes the graph) so the
            # executor reply phase can still answer from collected evidence.
            state.batch_exit_mode = deps._BATCH_EXIT_NOOP
            deadline_summary = (
                f"Research phase stopped after {state.batch_turn_count} turn(s); "
                f"phase deadline of {research_phase_deadline_seconds:g}s reached."
            )
            state.batch_final_summary = deadline_summary
            state.batch_done_summary = deadline_summary
            state.user_message = deadline_summary
            state.report = {
                "graph_unchanged": True,
                "queue_blockers": [],
                "phase_deadline": deadline_summary,
            }
            deps._emit_agent_edit_turn_event(
                state,
                _context,
                state.batch_turns[-1] if state.batch_turns else None,
                client_id=client_id,
                status="done",
            )
            return deps.StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=deps._duration_ms(start),
                artifacts=(
                    deps._artifact(state.before_py_path),
                    deps._artifact(state.after_py_path),
                    deps._artifact(state.model_request_path),
                    deps._artifact(state.model_response_path),
                    deps._artifact(state.candidate_ui_path),
                    deps._artifact(state.messages_path),
                ),
                value={
                    "mode": "research_phase_deadline",
                    "graph_unchanged": True,
                    "turn_count": state.batch_turn_count,
                },
            )
        _loop_entry_journal = _batch_journal_mod.capture_loop_entry_journal(
            session,
            state,
            turn_number=turn_number,
            context=_context,
        )
        budget_remaining = max_batches - turn_number
        include_full_render = turn_number == 0 or last_landed_count == 0
        node_variable_index = deps._format_node_variable_index(session)
        # D03/I01: cross-turn research context is ledger-only — compact ledger
        # entries + evidence IDs, never raw bodies/schemas. Full evidence stays
        # in the evidence-pack artifact behind the resolvable IDs. On the adapt
        # route the executor's C1 ledger (payload["research_ledger"]) is also
        # rendered here, so turn 0 shows the research conclusions/evidence the
        # implement agent adapts from instead of an empty block.
        evidence_ledger = deps._batch_research_memory_summary(state)
        discovery_nudge = (
            deps._discovery_construction_nudge(state)
            if not research_only_route
            else ""
        )
        report_for_prompt = last_report
        if discovery_nudge:
            report_for_prompt = (
                f"{report_for_prompt}\n\n{discovery_nudge}"
                if report_for_prompt
                else discovery_nudge
            )
        execution_plan_status = _execution_plan_status_for_prompt(deps, state)
        messages = deps.build_batch_messages(
            task=effective_task,
            turn_number=turn_number,
            python_source=(initial_render if turn_number == 0 else current_render)
            if include_full_render
            else "",
            node_variable_index=node_variable_index,
            previous_model_message=previous_model_message,
            signature_catalog=state.batch_signature_catalog if turn_number == 0 else "",
            available_node_names=available_node_names if turn_number == 0 else "",
            diff=last_diff,
            report=report_for_prompt,
            budget_remaining=budget_remaining,
            max_batches=max_batches,
            conversation_messages=conversation_messages if turn_number == 0 else None,
            research_only=research_only_route,
            evidence_ledger=evidence_ledger,
            revision_evidence_json=deps._revision_evidence_prompt_json(state)
            if turn_number == 0
            else "",
            execution_plan_status=execution_plan_status,
        )
        request_entry = {
            "turn_number": turn_number,
            "messages": messages,
            "budget_remaining": budget_remaining,
            "node_variable_index": node_variable_index,
            "included_full_render": include_full_render,
        }
        if discovery_nudge:
            request_entry["discovery_construction_nudge"] = True
        request_log.append(request_entry)
        deps.write_json_artifact(
            state.model_request_path,
            {"response_contract": "batch_repl", "turns": request_log},
        )

        try:
            try:
                if deepseek_client is not None:
                    turn_result = deps._normalize_test_client_batch_response(deepseek_client(messages))
                else:
                    turn_result = deps.run_agent_turn_batch(
                        state.task,
                        messages,
                        route=route,
                        model=model,
                        effort=effort,
                    )
            except (deps.MalformedModelJSON, deps.MissingRequiredField) as first_exc:
                from vibecomfy.comfy_nodes.agent.edit import _malformed_model_json_detail  # noqa: PLC0415

                retry_messages = _batch_protocol_retry_messages(messages, first_exc)
                first_detail = _malformed_model_json_detail(first_exc)
                retry_request_entry = {
                    "turn_number": turn_number,
                    "messages": retry_messages,
                    "budget_remaining": budget_remaining,
                    "node_variable_index": node_variable_index,
                    "included_full_render": include_full_render,
                    "protocol_retry": {
                        "attempt": 2,
                        "reason": _batch_protocol_parse_reason(first_exc),
                        "message": str(first_exc),
                    },
                }
                request_log.append(retry_request_entry)
                deps.write_json_artifact(
                    state.model_request_path,
                    {"response_contract": "batch_repl", "turns": request_log},
                )
                response_log.append(
                    {
                        "turn_number": turn_number,
                        "error": {
                            "type": type(first_exc).__name__,
                            "message": str(first_exc),
                            "parse_reason": _batch_protocol_parse_reason(first_exc),
                            "retrying": True,
                            "attempt": 1,
                            **first_detail,
                        },
                    }
                )
                deps.write_json_artifact(state.model_response_path, {"turns": response_log})
                if deepseek_client is not None:
                    turn_result = deps._normalize_test_client_batch_response(deepseek_client(retry_messages))
                else:
                    turn_result = deps.run_agent_turn_batch(
                        state.task,
                        retry_messages,
                        route=route,
                        model=model,
                        effort=effort,
                    )
                retry_metadata = dict(turn_result.audit_metadata or {})
                retry_metadata["batch_repl_protocol_retry"] = {
                    "count": 1,
                    "reason": str(first_exc),
                    "parse_reason": _batch_protocol_parse_reason(first_exc),
                }
                turn_result = dataclasses.replace(
                    turn_result,
                    audit_metadata=retry_metadata,
                )
        except (deps.MalformedModelJSON, deps.MissingRequiredField) as exc:
            parse_reason = _batch_protocol_parse_reason(exc)
            exc_detail = _malformed_model_json_detail(exc)
            malformed_diagnostic = {
                "code": "malformed_batch_response",
                "severity": "error",
                "parse_reason": parse_reason,
                "attempt_count": 2,
                "turn_number": turn_number,
                "response_contract": "batch_repl",
                **exc_detail,
            }
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                **exc_detail,
                "diagnostics": [malformed_diagnostic],
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "parse_reason": parse_reason,
                        "retrying": False,
                        "attempt": 2,
                        **exc_detail,
                        "diagnostics": [
                            malformed_diagnostic,
                        ],
                    },
                }
            )
            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            state.batch_exit_mode = "protocol_failure"
            state.batch_final_summary = (
                "Stopped because the model did not return a valid batch_repl response."
            )
            if state.batch_turns:
                deps._emit_agent_edit_turn_event(
                    state,
                    _context,
                    state.batch_turns[-1],
                    client_id=client_id,
                    status="error",
                )
            raise
        except Exception as exc:
            error_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": "",
                "batch": "",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "request_messages": messages,
            }
            response_log.append(
                {
                    "turn_number": turn_number,
                    "error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                }
            )
            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(error_record, sort_keys=True) + "\n"
            )
            raise

        state.provider_metadata = dict(turn_result.audit_metadata or {})
        state.user_message = turn_result.message
        # Preserve the first non-empty executor message before any clarify splitting
        # or normalization so it remains available as a debug/input artifact.
        if turn_result.message and not state.raw_executor_message:
            state.raw_executor_message = turn_result.message
        previous_model_message = turn_result.message
        clarify_split = deps.split_terminal_clarify(turn_result.batch)
        clarify_message = clarify_split.message
        editable_batch = clarify_split.batch if clarify_message is not None else turn_result.batch
        response_log.append(
            {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "status": "received",
            }
        )
        deps.write_json_artifact(state.model_response_path, {"turns": response_log})
        if clarify_message is not None and not editable_batch.strip():
            state.batch_turn_count = turn_number + 1
            state.batch_exit_mode = (
                deps._BATCH_EXIT_EDIT_CLARIFY
                if deps._batch_candidate_graph_changed(state)
                else deps._BATCH_EXIT_PURE_CLARIFY
            )
            state.batch_final_summary = (
                f"Clarification requested after {state.batch_turn_count} batch turn(s)."
            )
            state.batch_budget_state = {
                "max_batches": max_batches,
                "max_consecutive_errors": max_consecutive_errors,
                "remaining_batches": max_batches - state.batch_turn_count,
                "remaining_consecutive_errors": max_consecutive_errors,
                "consecutive_errors": consecutive_errors,
            }
            state.user_message = clarify_message
            state.python_after = current_render
            state.after_py_path.write_text(current_render, encoding="utf-8")
            state.ui_payload = json.loads(json.dumps(session.working_ui))
            deps.write_json_artifact(state.candidate_ui_path, state.ui_payload)
            state.report = {
                "clarification_required": True,
                "graph_unchanged": True,
                "queue_blockers": [],
            }
            turn_record = {
                "turn_number": turn_number,
                "batch": turn_result.batch,
                "message": turn_result.message,
                "route": turn_result.route,
                "model": turn_result.model,
                "provider_metadata": deps._json_safe(dict(turn_result.audit_metadata or {})),
                "clarification_required": True,
                "clarification_message": clarify_message,
                "field_changes": [],
            }
            state.batch_turns.append(turn_record)
            response_log[-1] = {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "clarification": turn_record,
            }
            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(
                    {
                        "turn_number": turn_number,
                        "task": state.task,
                        "message": turn_result.message,
                        "batch": turn_result.batch,
                        "clarification_required": clarify_message,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            state.artifacts = {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "revision_evidence": str(state.revision_evidence_path),
                "messages": str(state.messages_path),
            }
            deps._emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="clarify",
            )
            return deps.StageResult(
                stage="agent_batch",
                ok=True,
                blocking=False,
                duration_ms=deps._duration_ms(start),
                artifacts=(
                    deps._artifact(state.after_py_path),
                    deps._artifact(state.model_request_path),
                    deps._artifact(state.model_response_path),
                    deps._artifact(state.candidate_ui_path),
                    deps._artifact(state.messages_path),
                ),
                value={"mode": "clarification_required", "graph_unchanged": True},
                gate_updates={
                    "python_load_ok": True,
                    "lower_ok": True,
                    "ir_validate_ok": True,
                    "ui_emit_ok": True,
                    "ui_fidelity_ok": True,
                    "ui_load_safe_ok": True,
                    "state_match_ok": True,
                }
                if state.batch_exit_mode == deps._BATCH_EXIT_EDIT_CLARIFY
                else {},
            )

        _entry_mod.begin_turn_event_buffer()
        _journal_failed = False
        try:
            batch_result = session.apply_batch(editable_batch)
            _batch_journal_mod.maybe_inject_batch_fault("after_apply")
            deps._enrich_schema_provider_from_resolver_candidates(
                state,
                session,
                deps._resolver_candidates_from_batch_result(batch_result),
            )
            next_render = session.render()
            _batch_journal_mod.maybe_inject_batch_fault("after_render")
            state.python_after = next_render
            state.after_py_path.write_text(next_render, encoding="utf-8")
            state.ui_payload = json.loads(json.dumps(session.working_ui))
            deps.write_json_artifact(state.candidate_ui_path, state.ui_payload)
            _batch_journal_mod.maybe_inject_batch_fault("after_candidate_write")
            execution_plan_status = _evaluate_execution_plan_after_candidate_update(deps, state)

            # ── lint gate: post-apply no-op detection on landed ops ──────────
            lint_dropped_op_ids: frozenset[tuple[str, str]] | None = None
            lint_dropped_count = 0
            lint_diag_dicts: tuple[dict[str, Any], ...] = ()
            persisted_landed_ops = batch_result.landed_ops
            if (
                deps._edit_lint_enabled()
                and batch_result.landed_ops
                and deps._agent_edit_batch_repl_enabled()
            ):
                LintIndex, lint_delta = _import_from("vibecomfy.porting.edit.lint", "LintIndex"), _import_from("vibecomfy.porting.edit.lint", "lint_delta")
                RemoveLinkOp, SetModeOp, SetNodeFieldOp, UpsertLinkOp = _import_from("vibecomfy.porting.edit.ops", "RemoveLinkOp"), _import_from("vibecomfy.porting.edit.ops", "SetModeOp"), _import_from("vibecomfy.porting.edit.ops", "SetNodeFieldOp"), _import_from("vibecomfy.porting.edit.ops", "UpsertLinkOp")

                index = LintIndex.build(state.graph)
                lint_result = lint_delta(
                    batch_result.landed_ops,
                    index,
                    schema_provider=state.schema_provider,
                )

                landed_add_uids = {
                    str(item.detail.get("minted_uid"))
                    for item in batch_result.statements
                    if item.ok
                    and str(item.op_kind or "") == "node_call"
                    and isinstance(item.detail, Mapping)
                    and item.detail.get("minted_uid") is not None
                }

                # Build (uid, field_path) identities for lint-dropped ops.
                _dropped_keys: list[tuple[str, str]] = []
                for norm in lint_result.normalizations:
                    if norm.disposition != "dropped_noop":
                        continue
                    op = norm.op
                    key: tuple[str, str] | None = None
                    if isinstance(op, SetNodeFieldOp):
                        key = (op.target.uid, op.target.field_path)
                    elif isinstance(op, SetModeOp):
                        key = (op.target.uid, "mode")
                    elif isinstance(op, UpsertLinkOp):
                        key = (op.target.uid, op.target.input_field)
                    elif isinstance(op, RemoveLinkOp) and op.target is not None:
                        key = (op.target.uid, op.target.input_field)
                    if key is not None:
                        _dropped_keys.append(key)
                lint_dropped_op_ids = frozenset(_dropped_keys)
                lint_dropped_count = lint_result.dropped_count

                # Accumulate human-readable lint no-op messages
                _turn_noop_msgs: list[str] = []
                for norm in lint_result.normalizations:
                    if norm.disposition == "dropped_noop" and norm.issue is not None:
                        _turn_noop_msgs.append(norm.issue.message)
                state.lint_noop_messages = state.lint_noop_messages + tuple(_turn_noop_msgs)

                def _lint_issue_to_dict(issue: Any) -> dict[str, Any]:
                    return {
                        "code": issue.code,
                        "message": issue.message,
                        "severity": issue.severity,
                        "op_index": getattr(issue, "op_index", None),
                        "op_kind": getattr(issue, "op_kind", None),
                        "source": "lint",
                    }

                lint_issues = tuple(
                    issue
                    for issue in lint_result.issues
                    if not (
                        issue.code == "unknown_target"
                        and issue.uid in landed_add_uids
                    )
                )
                lint_diag_dicts = tuple(
                    _lint_issue_to_dict(issue) for issue in lint_issues
                )
                persisted_landed_ops = lint_result.surviving

            raw_landed = len(batch_result.landed_ops)
            effective_landed = raw_landed - lint_dropped_count
            landed_count = effective_landed
            total_landed += effective_landed
            last_landed_count = effective_landed
            # Compute this turn's search() signatures once; used for the duplicate-
            # cycle feedback (against the PRIOR turn's state) and to advance the
            # prior-search state for the NEXT turn.  "Landed" means ANY landed edit
            # this turn — a search followed by a successful edit is not a dead-end
            # and must not trigger the cycle guard on repeat.
            current_search_signatures = deps._extract_search_signatures(batch_result)
            if batch_result.landed_ops:
                DELTA_SCHEMA_VERSION, ensure_root_scoped_delta_envelope, op_to_dict = _import_from("vibecomfy.porting.edit.ops", "DELTA_SCHEMA_VERSION"), _import_from("vibecomfy.porting.edit.ops", "ensure_root_scoped_delta_envelope"), _import_from("vibecomfy.porting.edit.ops", "op_to_dict")

                delta_envelope_payload = ensure_root_scoped_delta_envelope(
                    {
                        "schema_version": DELTA_SCHEMA_VERSION,
                        "ops": [op_to_dict(op) for op in persisted_landed_ops],
                    },
                    strict=True,
                ).to_dict()
            else:
                delta_envelope_payload = None
            turn_is_read_only = effective_landed == 0 and all(
                str(item.op_kind or "") in {"query", "done", "clarify"}
                for item in batch_result.statements
            )

            turn_has_errors = (
                (not batch_result.ok)
                or bool(batch_result.diagnostics)
                or any(
                    d.get("severity") == "error" for d in lint_diag_dicts
                )
            )
            consecutive_errors = consecutive_errors + 1 if turn_has_errors else 0
            diff_text = deps._render_batch_diff(current_render, next_render)
            report_text = deps._format_batch_report(
                batch_result,
                consecutive_errors=consecutive_errors,
                budget_remaining=max_batches - (turn_number + 1),
                lint_dropped_count=lint_dropped_count,
                lint_diagnostics=lint_diag_dicts,
            )
            # Duplicate-query cycle guard (Part C): detect when the agent re-emits
            # an identical search() on consecutive turns after the prior search
            # landed nothing.  Reads the PRIOR turn's search record
            # (prior_search_signatures / prior_search_landed, init in the intro
            # loop); the advance for THIS turn happens just below so the next turn
            # sees this turn as its prior.
            duplicate_search_feedback = deps._duplicate_search_cycle_feedback(
                current_search_signatures,
                prior_search_signatures,
                prior_search_landed,
            )
            # Advance the prior-search state for the NEXT turn now that the feedback
            # (which reads the old prior state) has been computed.  A turn with no
            # search calls resets the tracker: the guard only fires on CONSECUTIVE
            # identical searches, so an intervening non-search turn breaks the chain.
            if current_search_signatures:
                prior_search_signatures = current_search_signatures
                prior_search_landed = effective_landed > 0
            else:
                prior_search_signatures = None
                prior_search_landed = False
            extra_feedback = "\n\n".join(
                note
                for note in (duplicate_search_feedback,)
                if note
            )
            if extra_feedback:
                report_text = f"{report_text}\n{extra_feedback}"
            report_json = deps._format_batch_report_json(
                batch_result,
                consecutive_errors=consecutive_errors,
                budget_remaining=max_batches - (turn_number + 1),
                lint_dropped_count=lint_dropped_count,
                lint_diagnostics=lint_diag_dicts,
            )
            field_changes = deps.repair_field_changes(
                state.graph,
                tuple(batch_result.field_changes),
            )
            real_field_changes = deps._real_field_changes(
                field_changes,
                lint_dropped_op_ids=lint_dropped_op_ids,
            )
            noop_field_changes = deps._noop_field_changes(
                field_changes,
                lint_dropped_op_ids=lint_dropped_op_ids,
            )
            state.batch_field_changes = state.batch_field_changes + real_field_changes
            state.batch_noop_field_changes = state.batch_noop_field_changes + noop_field_changes
            turn_record = {
                "turn_number": turn_number,
                "batch": turn_result.batch,
                "message": turn_result.message,
                "route": turn_result.route,
                "model": turn_result.model,
                "provider_metadata": deps._json_safe(dict(turn_result.audit_metadata or {})),
                "batch_ok": batch_result.ok,
                "statement_count": len(batch_result.statements),
                "landed_op_count": effective_landed,
                "raw_landed_op_count": raw_landed,
                "lint_dropped_op_count": lint_dropped_count,
                "diagnostics": report_json["diagnostics"],
                "statements": report_json["statements"],
                "field_changes": deps._field_changes_payload(real_field_changes),
                "diff": diff_text,
                "report": report_text,
            }
            if execution_plan_status:
                turn_record["execution_plan_status"] = execution_plan_status
            if delta_envelope_payload is not None:
                turn_record["delta_ops_envelope"] = delta_envelope_payload
                turn_record["delta_ops"] = list(delta_envelope_payload["ops"])
            if noop_field_changes:
                turn_record["noop_field_changes"] = deps._field_changes_payload(noop_field_changes)
            if clarify_message is not None:
                turn_record["clarification_required"] = True
                turn_record["clarification_message"] = clarify_message
            state.batch_turns.append(turn_record)
            state.batch_feedback = report_text
            state.batch_turn_count = turn_number + 1
            state.batch_budget_state = {
                "max_batches": max_batches,
                "max_consecutive_errors": max_consecutive_errors,
                "remaining_batches": max_batches - state.batch_turn_count,
                "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
                "consecutive_errors": consecutive_errors,
            }
            selected_precedent_unknown_class_feedback = (
                deps._selected_precedent_unknown_class_feedback(state, batch_result)
            )
            if selected_precedent_unknown_class_feedback and not deps._batch_candidate_graph_changed(state):
                turn_record["clarification_required"] = True
                turn_record["clarification_message"] = selected_precedent_unknown_class_feedback
                turn_record["authoring_blocker"] = "selected_precedent_unknown_class"

            response_log[-1] = {
                "turn_number": turn_number,
                "response": turn_result.to_dict(),
                "batch_result": turn_record,
            }
            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
            message_record = {
                "turn_number": turn_number,
                "task": state.task,
                "message": turn_result.message,
                "batch": turn_result.batch,
                "report": report_text,
            }
            if execution_plan_status:
                message_record["execution_plan_status"] = execution_plan_status
            if selected_precedent_unknown_class_feedback and not deps._batch_candidate_graph_changed(state):
                message_record["authoring_blocker"] = "selected_precedent_unknown_class"
                message_record["clarification_required"] = selected_precedent_unknown_class_feedback
            state.messages_path.open("a", encoding="utf-8").write(
                json.dumps(message_record, sort_keys=True)
                + "\n"
            )
            if selected_precedent_unknown_class_feedback and not deps._batch_candidate_graph_changed(state):
                state.batch_exit_mode = deps._BATCH_EXIT_PURE_CLARIFY
                state.batch_final_summary = (
                    f"Clarification requested after {state.batch_turn_count} batch turn(s)."
                )
                state.user_message = selected_precedent_unknown_class_feedback
                state.report = {
                    "clarification_required": True,
                    "graph_unchanged": True,
                    "queue_blockers": [],
                    "authoring_blocker": {
                        "reason": "selected_precedent_unknown_class",
                        "message": selected_precedent_unknown_class_feedback,
                    },
                }
                response_log[-1] = {
                    "turn_number": turn_number,
                    "response": turn_result.to_dict(),
                    "batch_result": turn_record,
                    "clarification": {
                        "message": selected_precedent_unknown_class_feedback,
                        "reason": "selected_precedent_unknown_class",
                    },
                }
                deps.write_json_artifact(state.model_response_path, {"turns": response_log})
                deps._emit_agent_edit_turn_event(
                    state,
                    _context,
                    turn_record,
                    client_id=client_id,
                    status="clarify",
                )
                return deps.StageResult(
                    stage="agent_batch",
                    ok=True,
                    blocking=False,
                    duration_ms=deps._duration_ms(start),
                    artifacts=(
                        deps._artifact(state.after_py_path),
                        deps._artifact(state.model_request_path),
                        deps._artifact(state.model_response_path),
                        deps._artifact(state.candidate_ui_path),
                        deps._artifact(state.messages_path),
                    ),
                    value={
                        "mode": "authoring_blocker",
                        "graph_unchanged": True,
                        "reason": "selected_precedent_unknown_class",
                    },
                )


            # Finish branches set the public state.user_message (deterministic text or
            # a per-turn response), but the raw executor message is preserved in
            # state.raw_executor_message from the intro and must not be overwritten.
            if clarify_message is not None:
                state.batch_exit_mode = (
                    deps._BATCH_EXIT_EDIT_CLARIFY
                    if deps._batch_candidate_graph_changed(state)
                    else deps._BATCH_EXIT_PURE_CLARIFY
                )
                state.batch_final_summary = (
                    f"Clarification requested after {state.batch_turn_count} batch turn(s)."
                )
                state.user_message = clarify_message
                state.report = {
                    "clarification_required": True,
                    "graph_unchanged": state.batch_exit_mode == deps._BATCH_EXIT_PURE_CLARIFY,
                    "queue_blockers": [],
                }
                deps._emit_agent_edit_turn_event(
                    state,
                    _context,
                    turn_record,
                    client_id=client_id,
                    status="clarify",
                )
                return deps.StageResult(
                    stage="agent_batch",
                    ok=True,
                    blocking=False,
                    duration_ms=deps._duration_ms(start),
                    artifacts=(
                        deps._artifact(state.after_py_path),
                        deps._artifact(state.model_request_path),
                        deps._artifact(state.model_response_path),
                        deps._artifact(state.candidate_ui_path),
                        deps._artifact(state.messages_path),
                    ),
                    value={
                        "mode": "clarification_required",
                        "graph_unchanged": state.batch_exit_mode == deps._BATCH_EXIT_PURE_CLARIFY,
                    },
                    gate_updates={
                        "python_load_ok": True,
                        "lower_ok": True,
                        "ir_validate_ok": True,
                        "ui_emit_ok": True,
                        "ui_fidelity_ok": True,
                        "ui_load_safe_ok": True,
                        "state_match_ok": True,
                    }
                    if state.batch_exit_mode == deps._BATCH_EXIT_EDIT_CLARIFY
                    else {},
                )

            current_render = next_render
            last_diff = diff_text
            last_report = report_text
            done_requested = any(
                item.ok and str(item.op_kind or "") == "done"
                for item in batch_result.statements
            )
            turn_failed_edit = any(
                (not item.ok)
                and str(item.op_kind or "") not in {"query", "done", "clarify"}
                for item in batch_result.statements
            )
            if turn_failed_edit:
                failed_edit_turns += 1
                last_failed_edit_turn = turn_number
            elif effective_landed > 0 and last_failed_edit_turn >= 0:
                last_successful_edit_turn_after_failure = turn_number
            unresolved_failed_edit = (
                last_failed_edit_turn >= 0
                and last_successful_edit_turn_after_failure < last_failed_edit_turn
            )
            turn_is_read_only = effective_landed == 0 and all(
                str(item.op_kind or "") in {"query", "done", "clarify"}
                for item in batch_result.statements
            )
            # Don't honor a premature done(): feed guidance back and let the model
            # self-correct. Two distinct cases, each separately bounded so a genuine
            # no-change request still commits and we can't loop forever:
            #  (1) NOTHING ever landed — committing would be an empty no-op. Causes:
            #      a wrong node signature, or a read-only search() then done().
            #  (2) Something landed but THIS (final) batch errored — some intended
            #      statements failed to land (e.g. a wrong output-slot name), so the
            #      edit is half-applied and likely broken (floating node / dangling
            #      wire). The diagnostics name the fix; force one more turn.
            refuse_done = False
            hint = ""
            if (
                done_requested
                and consecutive_errors < max_consecutive_errors
                and not research_only_route
            ):
                if total_landed == 0 and (turn_has_errors or failed_edit_turns > 0):
                    done_noop_nudges += 1
                    refuse_done = True
                    if turn_has_errors:
                        hint = (
                            "your edit statement(s) did NOT land (see the diagnostics above)"
                            " and nothing has been applied. Fix the failed statement — correct"
                            " the wrong field name or supply the required input;"
                            " call search(focus_types=[\"ClassName\"]) for the exact signature —"
                            " then call done()."
                        )
                    elif failed_edit_turns > 0:
                        hint = (
                            "earlier edit statement(s) failed and no edit has landed. A search()"
                            " is read-only and does NOT fix the failed edit. Use the diagnostics"
                            " above and construct a valid node/wire, or clarify the limitation;"
                            " do not report this as already done."
                        )
                    else:
                        hint = (
                            "you called done() without making any edit, so nothing was applied."
                            " A search() is read-only and does NOT change the graph. Now CONSTRUCT"
                            " and wire the node(s) the request needs (e.g. `up = NodeType(...)` then"
                            " `consumer.input = up.OUTPUT`), then call done(). If the graph"
                            " genuinely needs no change, call done() again to confirm."
                        )
                elif unresolved_failed_edit and turn_is_read_only:
                    done_noop_nudges += 1
                    refuse_done = True
                    hint = (
                        "an earlier edit batch failed after partially mutating the graph."
                        " A search() is read-only and does NOT repair that incomplete"
                        " candidate. Use the search result and diagnostics above to"
                        " construct and wire the missing node(s), then call done()."
                    )
                elif (
                    (turn_number + 1) < max_batches
                    and total_landed == 0
                    and done_noop_nudges < 2
                ):
                    done_noop_nudges += 1
                    refuse_done = True
                    hint = (
                        "you called done() without making any edit, so nothing was applied."
                        " A search() is read-only and does NOT change the graph. Now CONSTRUCT"
                        " and wire the node(s) the request needs (e.g. `up = NodeType(...)` then"
                        " `consumer.input = up.OUTPUT`), then call done(). If the graph"
                        " genuinely needs no change, call done() again to confirm."
                    )
                elif turn_has_errors and done_error_nudges < 2:
                    done_error_nudges += 1
                    refuse_done = True
                    hint = (
                        "some of your edit statements did NOT land (see the diagnostics above),"
                        " so the edit is INCOMPLETE — nodes the request needs may be left"
                        " unconnected or a consumer's input left dangling. Do NOT stop here."
                        " Fix ONLY the failed statement(s): use the exact output-slot/field names"
                        " the diagnostics list (e.g. an output is `.UPSCALE_MODEL`, not `.model`),"
                        " drop any kwarg the node does not declare, re-wire the consumer, then"
                        " call done()."
                    )
            if (
                done_requested
                and not refuse_done
                and not research_only_route
                and getattr(state, "execution_plan", None) is not None
            ):
                candidate_graph = (
                    state.ui_payload
                    if isinstance(state.ui_payload, Mapping)
                    else session.working_ui
                )
                update = deps.evaluate_execution_plan_for_state(
                    state,
                    candidate_graph,
                    candidate_graph_hash=deps.structural_graph_hash(candidate_graph),
                )
                execution_plan_status = dict(update.compact_status or {})
                if execution_plan_status:
                    turn_record["execution_plan_status"] = execution_plan_status
                    if response_log and isinstance(response_log[-1], dict):
                        batch_response_record = response_log[-1].get("batch_result")
                        if isinstance(batch_response_record, dict):
                            batch_response_record["execution_plan_status"] = execution_plan_status
                        deps.write_json_artifact(state.model_response_path, {"turns": response_log})
                evaluation = getattr(state, "plan_evaluation", None)
                plan_evaluation_blocks = _import_from(
                    "vibecomfy.comfy_nodes.agent.execution_plan",
                    "plan_evaluation_blocks",
                )
                if plan_evaluation_blocks(evaluation):
                    refuse_done = True
                    hint = _execution_plan_done_refusal_hint(state)
            if refuse_done:
                last_report = last_report + "\n\nNOTE: done() was NOT accepted — " + hint
                turn_record["report"] = last_report
                if state.batch_turns and state.batch_turns[-1] is turn_record:
                    state.batch_turns[-1]["report"] = last_report
                if response_log and isinstance(response_log[-1], dict):
                    batch_response_record = response_log[-1].get("batch_result")
                    if isinstance(batch_response_record, dict):
                        batch_response_record["report"] = last_report
                    deps.write_json_artifact(state.model_response_path, {"turns": response_log})
                continue
            if done_requested:
                done_result = session.done()
                _batch_journal_mod.maybe_inject_batch_fault("after_done")
                state.batch_turn_count = turn_number + 1
                state.batch_budget_state = {
                    "max_batches": max_batches,
                    "max_consecutive_errors": max_consecutive_errors,
                    "remaining_batches": max_batches - state.batch_turn_count,
                    "remaining_consecutive_errors": max(0, max_consecutive_errors - consecutive_errors),
                    "consecutive_errors": consecutive_errors,
                }
                state.batch_exit_mode = (
                    deps._BATCH_EXIT_DONE if deps._batch_candidate_graph_changed(state) else deps._BATCH_EXIT_NOOP
                )
                state.batch_done_summary = done_result.summary
                state.batch_final_summary = done_result.summary
                if not done_result.ok:
                    # PR-E: one bounded repair turn on done() validation
                    # failure.  Carry code/message/target/choices of every
                    # validation diagnostic into the next model request so the
                    # agent can repair the exact failing surface; a second
                    # failure still terminates with the blocking result.
                    if (
                        done_validation_repair_turns < 1
                        and (turn_number + 1) < max_batches
                        and not research_only_route
                    ):
                        done_validation_repair_turns += 1
                        repair_hint = _done_validation_repair_hint(
                            deps,
                            done_result.diagnostics,
                        )
                        last_report = (
                            last_report
                            + "\n\nNOTE: done() was NOT accepted — "
                            + repair_hint
                        )
                        turn_record["report"] = last_report
                        turn_record["done_validation_repair"] = {
                            "attempt": done_validation_repair_turns,
                            "diagnostics": [
                                dict(deps._compact_diag_to_dict(item))
                                for item in done_result.diagnostics
                            ],
                        }
                        if state.batch_turns and state.batch_turns[-1] is turn_record:
                            state.batch_turns[-1]["report"] = last_report
                            state.batch_turns[-1]["done_validation_repair"] = turn_record["done_validation_repair"]
                        if response_log and isinstance(response_log[-1], dict):
                            batch_response_record = response_log[-1].get("batch_result")
                            if isinstance(batch_response_record, dict):
                                batch_response_record["report"] = last_report
                                batch_response_record["done_validation_repair"] = turn_record["done_validation_repair"]
                            deps.write_json_artifact(state.model_response_path, {"turns": response_log})
                        # Not finalized: reset the done-exit state so the
                        # repair turn starts from a clean pending candidate.
                        state.batch_exit_mode = ""
                        state.batch_done_summary = ""
                        state.batch_final_summary = ""
                        continue
                    return deps.StageResult(
                        stage="agent_batch",
                        ok=False,
                        blocking=True,
                        duration_ms=deps._duration_ms(start),
                        artifacts=(
                            deps._artifact(state.before_py_path),
                            deps._artifact(state.after_py_path),
                            deps._artifact(state.model_request_path),
                            deps._artifact(state.model_response_path),
                            deps._artifact(state.candidate_ui_path),
                            deps._artifact(state.messages_path),
                        ),
                        issues=tuple(deps._compact_diag_to_dict(item) for item in done_result.diagnostics),
                        value={
                            "failure_kind": deps.FailureKind.VALIDATION_ERROR.value,
                            "turn_count": state.batch_turn_count,
                            "done_summary": done_result.summary,
                        },
                    )
                state.user_message = deps.ensure_sentence_message(
                    turn_result.message,
                    fallback="I made the requested workflow changes.",
                )
                state.report = {
                    "done_summary": done_result.summary,
                    "queue_blockers": [],
                }
                deps._finalize_revision_evidence_with_candidate(
                    state,
                    route=state.route,
                    conversation_messages=conversation_messages,
                )
                _batch_journal_mod.maybe_inject_batch_fault("after_finalize")
                scoped = (
                    state.revision_evidence.scoped_diff
                    if state.revision_evidence is not None
                    else None
                )
                retryable_revise_blockers = (
                    set(getattr(scoped, "eligibility_blockers", ()))
                    - {"target_mismatch", "target_scope_violation"}
                )
                if (
                    deps._canonical_agent_edit_route(state.route) == "revise"
                    and state.revision_evidence is not None
                    and state.revision_evidence.candidate_eligible is not True
                    and retryable_revise_blockers
                    and (turn_number + 1) < max_batches
                    and done_candidate_rejection_nudges < 2
                ):
                    done_candidate_rejection_nudges += 1
                    last_report = (
                        last_report
                        + "\n\nNOTE: done() was NOT accepted — "
                        + deps._revision_candidate_retry_hint(state)
                    )
                    continue
                state.artifacts = {
                    "request": str(state.request_path),
                    "original_ui": str(state.original_ui_path),
                    "before_python": str(state.before_py_path),
                    "after_python": str(state.after_py_path),
                    "python": str(state.after_py_path),
                    "model_request": str(state.model_request_path),
                    "model_response": str(state.model_response_path),
                    "candidate_ui": str(state.candidate_ui_path),
                    "revision_evidence": str(state.revision_evidence_path),
                    "messages": str(state.messages_path),
                }
                deps._emit_agent_edit_turn_event(
                    state,
                    _context,
                    turn_record,
                    client_id=client_id,
                    status="done",
                )
                return deps.StageResult(
                    stage="agent_batch",
                    ok=True,
                    blocking=False,
                    duration_ms=deps._duration_ms(start),
                    artifacts=(
                        deps._artifact(state.before_py_path),
                        deps._artifact(state.after_py_path),
                        deps._artifact(state.model_request_path),
                        deps._artifact(state.model_response_path),
                        deps._artifact(state.candidate_ui_path),
                        deps._artifact(state.messages_path),
                    ),
                    value={"mode": "done", "done_summary": done_result.summary},
                    gate_updates={
                        "python_load_ok": True,
                        "lower_ok": True,
                        "ir_validate_ok": True,
                        "ui_emit_ok": True,
                        "ui_fidelity_ok": True,
                        "ui_load_safe_ok": True,
                        "state_match_ok": True,
                    },
                )
            if (
                total_landed == 0
                and deps._read_only_discovery_turn_count(state) >= 3
                and not deps._batch_candidate_graph_changed(state)
            ):
                read_only_discovery_turns = deps._read_only_discovery_turn_count(state)
                if read_only_discovery_turns < 6:
                    continue
                state.batch_exit_mode = deps._BATCH_EXIT_PURE_CLARIFY
                state.batch_final_summary = (
                    f"Stopped after {state.batch_turn_count} discovery-only batch turn(s)."
                )
                state.user_message = deps._discovery_stop_message(state)
                state.report = {
                    "clarification_required": True,
                    "graph_unchanged": True,
                    "queue_blockers": [],
                    "discovery_stop": {
                        "turn_count": state.batch_turn_count,
                        "reason": "repeated_read_only_discovery",
                    },
                }
                deps._emit_agent_edit_turn_event(
                    state,
                    _context,
                    turn_record,
                    client_id=client_id,
                    status="clarify",
                )
                return deps.StageResult(
                    stage="agent_batch",
                    ok=True,
                    blocking=False,
                    duration_ms=deps._duration_ms(start),
                    artifacts=(
                        deps._artifact(state.after_py_path),
                        deps._artifact(state.model_request_path),
                        deps._artifact(state.model_response_path),
                        deps._artifact(state.candidate_ui_path),
                        deps._artifact(state.messages_path),
                    ),
                    value={
                        "mode": "discovery_stop",
                        "graph_unchanged": True,
                        "turn_count": state.batch_turn_count,
                    },
                )
            deps._emit_agent_edit_turn_event(
                state,
                _context,
                turn_record,
                client_id=client_id,
                status="in_progress",
            )
            if consecutive_errors >= max_consecutive_errors:
                break
        except Exception as _batch_exc:
            _journal_failed = True
            _batch_journal_mod.abort_journaled_batch(
                session=session,
                state=state,
                journal=_loop_entry_journal,
                exc=_batch_exc,
                context=_context,
                client_id=client_id,
                emit_turn_event=deps._emit_agent_edit_turn_event,
            )
            raise
        finally:
            if not _journal_failed:
                _entry_mod.commit_turn_event_buffer()

    failure_kind = deps._batch_budget_failure_kind(state.batch_turns)
    artifixer_report = deps._batch_budget_artifixer_report(state, failure_kind)
    state.batch_exit_mode = deps._BATCH_EXIT_BUDGET
    if consecutive_errors >= max_consecutive_errors:
        exit_code = "batch_consecutive_errors_exhausted"
        state.batch_final_summary = (
            f"Stopped after {state.batch_turn_count} turn(s) with "
            f"{consecutive_errors} consecutive error turn(s) "
            f"(limit {max_consecutive_errors})."
        )
    else:
        exit_code = "batch_budget_exhausted"
        state.batch_final_summary = (
            f"Stopped after {state.batch_turn_count} turn(s); "
            "0 turn(s) remaining."
        )
    if state.batch_turns:
        deps._emit_agent_edit_turn_event(
            state,
            _context,
            state.batch_turns[-1],
            client_id=client_id,
            status="budget_exhausted",
        )
    return deps.StageResult(
        stage="agent_batch",
        ok=False,
        blocking=True,
        duration_ms=deps._duration_ms(start),
        artifacts=(
            deps._artifact(state.before_py_path),
            deps._artifact(state.after_py_path),
            deps._artifact(state.model_request_path),
            deps._artifact(state.model_response_path),
            deps._artifact(state.candidate_ui_path),
            deps._artifact(state.messages_path),
        ),
        issues=(
            {
                "code": exit_code,
                "severity": "error",
                "failure_kind": failure_kind.value,
                "message": state.batch_final_summary,
                "detail": {
                    "turn_count": state.batch_turn_count,
                    "budget_state": dict(state.batch_budget_state),
                    "budget_classification": failure_kind.value,
                    "artifixer": artifixer_report,
                },
            },
        ),
        value={
            "failure_kind": failure_kind.value,
            "turn_count": state.batch_turn_count,
            "budget_state": dict(state.batch_budget_state),
            "budget_classification": failure_kind.value,
            "diagnostics": (
                {
                    "code": "artifixer_not_attempted",
                    "severity": "info",
                    "message": "Artifact repair was not attempted for this terminal batch stop.",
                    "detail": artifixer_report,
                },
            ),
        },
    )




__all__ = (

    "EditBatchReplDeps",
    "MissingEditBatchReplDepsError",
    "REQUIRED_DEPENDENCY_NAMES",
    "build_edit_batch_repl_deps",
)
