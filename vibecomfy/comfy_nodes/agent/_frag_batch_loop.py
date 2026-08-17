"""
Batch REPL protocol, apply/lint pass, and exit branches (T-039 extraction of the edit_batch_loop fragment).

Extracted from the edit.py exec-assembled fragments (T-039, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Function bodies resolve their free
names from the assembled edit-module namespace at call time (marked with a
T-039 late import comment) so monkeypatches on edit.* stay visible exactly as
under the old exec assembly; guarded imports stay function-local.
"""
from __future__ import annotations

import dataclasses
import json
import time
from typing import Any, Mapping


from vibecomfy.ingest.door_access import door_get_nodes
_BATCH_PROTOCOL_RETRY_PROMPT = """Your previous response could not be applied because it did not include a valid batch block.

Reply in exactly this format:

One short sentence for the user.
```batch
# one or more edit statements, or clarify("question"), or done()
```

If you cannot safely edit the graph, still use the same format and put your question or blocker inside `clarify("...")` in the batch block.
Do not include markdown other than the single batch block."""


def _malformed_model_json_detail(exc: BaseException) -> dict[str, str]:
    detail: dict[str, str] = {}
    parse_reason = getattr(exc, "parse_reason", None)
    if isinstance(parse_reason, str) and parse_reason.strip():
        detail["parse_reason"] = parse_reason.strip()
    raw_preview = getattr(exc, "raw_response_preview", None)
    if isinstance(raw_preview, str) and raw_preview.strip():
        detail["raw_response_preview"] = raw_preview.strip()
    return detail


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
    # T-039 late import: host namespace lookup; resolved at call time.
    # The retry prompt constant lives in THIS module (top of file), not in
    # edit.py — import from here so the retry path can never NameError.
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


def _evaluate_execution_plan_after_candidate_update(state: AgentEditState) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (evaluate_execution_plan_for_state, structural_graph_hash)  # T-039 late import: host namespace lookup; resolved at call time
    if getattr(state, "execution_plan", None) is None:
        return {}
    if not isinstance(state.ui_payload, Mapping):
        return {}
    update = evaluate_execution_plan_for_state(
        state,
        state.ui_payload,
        candidate_graph_hash=structural_graph_hash(state.ui_payload),
    )
    return dict(update.compact_status or {})


def _execution_plan_status_for_prompt(state: AgentEditState) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (format_compact_plan_status)  # T-039 late import: host namespace lookup; resolved at call time
    if getattr(state, "execution_plan", None) is None:
        return {}
    return format_compact_plan_status(state.execution_plan, state.plan_evaluation)


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


_MAX_EXECUTION_PROTOCOL_SOURCES = 3
_MAX_EXECUTION_PROTOCOL_LIST_ITEMS = 16
_MAX_EXECUTION_PROTOCOL_STRING = 900

# W-07 — dedicated manifest-compactor budget.  The manifest contract (W-02)
# bounds a manifest to <=64 nodes / <=128 edges / <=16 anchors.  The dedicated
# compactor must be able to render a complete manifest of that size WITHOUT
# silently dropping nodes (a partial topology is worse than no topology).  The
# generic per-note list/depth limits above (16/4) would truncate a 40-node
# delta; the dedicated compactor is sized so it never truncates a valid
# manifest.  If a manifest would exceed even this dedicated budget, the
# manifest path is rejected and the legacy compact-notes path is used instead
# (no partial topology is ever emitted).
_MANIFEST_COMPACTOR_MAX_NODES = 64
_MANIFEST_COMPACTOR_MAX_EDGES = 128
_MANIFEST_COMPACTOR_MAX_ANCHORS = 16


def _manifest_compact_payload(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    from vibecomfy.comfy_nodes.agent.edit import (_MANIFEST_COMPACTOR_MAX_ANCHORS, _MANIFEST_COMPACTOR_MAX_EDGES, _MANIFEST_COMPACTOR_MAX_NODES)  # T-039 late import: host namespace lookup; resolved at call time
    """Render a complete manifest under the dedicated W-07 compactor budget.

    Returns the compact manifest dict when the manifest fits entirely within
    the dedicated budget (every node / edge / anchor preserved, no truncation).
    Returns ``None`` when the manifest is structurally empty or would exceed
    even the dedicated budget — callers MUST treat ``None`` as "reject the
    manifest path" (fall back to legacy) rather than emit a partial topology.

    Only ID-free selectors and hash-only provenance fields are carried.  No
    raw node ids, paths, goldens, fixture labels, or ``prior_path`` values.
    """
    if not isinstance(manifest, Mapping):
        return None

    nodes_raw = door_get_nodes(manifest)
    edges_raw = manifest.get("internal_edges")
    anchors_raw = manifest.get("boundary_anchors")
    if not isinstance(nodes_raw, (list, tuple)) or not nodes_raw:
        return None

    # ── reject (never silently truncate) when the manifest exceeds budget ──
    if len(nodes_raw) > _MANIFEST_COMPACTOR_MAX_NODES:
        return None
    if isinstance(edges_raw, (list, tuple)) and len(edges_raw) > _MANIFEST_COMPACTOR_MAX_EDGES:
        return None
    if isinstance(anchors_raw, (list, tuple)) and len(anchors_raw) > _MANIFEST_COMPACTOR_MAX_ANCHORS:
        return None

    def _compact_node(node: Any) -> dict[str, Any] | None:
        if not isinstance(node, Mapping):
            return None
        return {
            "symbol": str(node.get("symbol") or ""),
            "canonical_class_type": str(node.get("canonical_class_type") or ""),
            "resolver_status": str(node.get("resolver_status") or "unresolved"),
            "confidence": node.get("confidence"),
        }

    def _compact_edge(edge: Any) -> dict[str, Any] | None:
        if not isinstance(edge, Mapping):
            return None
        return {
            "from_symbol": str(edge.get("from_symbol") or ""),
            "output_socket": str(edge.get("output_socket") or ""),
            "to_symbol": str(edge.get("to_symbol") or ""),
            "input_socket": str(edge.get("input_socket") or ""),
            "confidence": edge.get("confidence"),
        }

    def _compact_anchor(anchor: Any) -> dict[str, Any] | None:
        if not isinstance(anchor, Mapping):
            return None
        return {
            "direction": str(anchor.get("direction") or "inbound"),
            "symbol": str(anchor.get("symbol") or ""),
            "symbol_socket": str(anchor.get("symbol_socket") or ""),
            "target_role": str(anchor.get("target_role") or ""),
            "target_class_type": str(anchor.get("target_class_type") or ""),
            "target_socket": str(anchor.get("target_socket") or ""),
            "confidence": anchor.get("confidence"),
        }

    compact_nodes = [_compact_node(n) for n in nodes_raw]
    if any(cn is None for cn in compact_nodes):
        # A malformed node entry means we cannot guarantee completeness.
        return None

    payload: dict[str, Any] = {
        "manifest_id": str(manifest.get("manifest_id") or ""),
        "nodes": compact_nodes,
    }
    if isinstance(edges_raw, (list, tuple)):
        compact_edges = [_compact_edge(e) for e in edges_raw]
        if any(ce is None for ce in compact_edges):
            return None
        payload["internal_edges"] = compact_edges
    if isinstance(anchors_raw, (list, tuple)):
        compact_anchors = [_compact_anchor(a) for a in anchors_raw]
        if any(ca is None for ca in compact_anchors):
            return None
        payload["boundary_anchors"] = compact_anchors
    validation = manifest.get("validation")
    if isinstance(validation, Mapping):
        payload["validation"] = {
            "verdict": str(validation.get("verdict") or "fail"),
            "class_resolution": str(validation.get("class_resolution") or ""),
        }
    payload["evidence_hash"] = str(manifest.get("evidence_hash") or "")
    payload["confidence"] = manifest.get("confidence")
    return payload


def _manifest_is_complete(manifest: Any) -> bool:
    """Return True when *manifest* is a non-empty manifest mapping.

    Used to gate the manifest-preferred compact-notes path.  A None, missing,
    or empty manifest keeps the legacy compact-notes behavior byte-for-byte.
    """
    return isinstance(manifest, Mapping) and bool(manifest)


def _active_manifest_from_plan(
    adaptation_plan: Any,
    *,
    route: str | None,
) -> tuple[bool, Mapping[str, Any] | None]:
    from vibecomfy.comfy_nodes.agent.edit import (_canonical_agent_edit_route, _manifest_is_complete)  # T-039 late import: host namespace lookup; resolved at call time
    """Return ``(manifest_active, manifest)`` for the W-07 compact-notes path.

    The manifest path is active ONLY when the canonical route is ``adapt`` AND
    the plan carries a complete ``topology_manifest`` mapping.  REPAIR/DEBUG
    (``revise``) and any non-adapt route keep today's legacy behavior.  Returns
    ``(False, None)`` in those cases so the caller's compact notes are
    byte-identical to the legacy path.
    """
    if _canonical_agent_edit_route(route) != "adapt":
        return (False, None)
    if not isinstance(adaptation_plan, Mapping):
        return (False, None)
    manifest = adaptation_plan.get("topology_manifest")
    if not _manifest_is_complete(manifest):
        return (False, None)
    return (True, manifest)


def _compact_protocol_string(value: Any, *, limit: int = _MAX_EXECUTION_PROTOCOL_STRING) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 18)].rstrip() + "\n... [truncated]"


def _compact_protocol_list(value: Any, *, limit: int = _MAX_EXECUTION_PROTOCOL_LIST_ITEMS) -> list[Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_compact_protocol_string)  # T-039 late import: host namespace lookup; resolved at call time
    if not isinstance(value, (list, tuple)):
        return []
    compacted: list[Any] = []
    for item in value[:limit]:
        if isinstance(item, str):
            compacted.append(_compact_protocol_string(item, limit=240))
        elif isinstance(item, (int, float, bool)) or item is None:
            compacted.append(item)
        else:
            compacted.append(_compact_protocol_string(item, limit=240))
    if len(value) > limit:
        compacted.append(f"... [{len(value) - limit} omitted]")
    return compacted


def _copy_compact_protocol_fields(
    source: Mapping[str, Any],
    keys: tuple[str, ...],
    *,
    string_limit: int = _MAX_EXECUTION_PROTOCOL_STRING,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_compact_protocol_list, _compact_protocol_string)  # T-039 late import: host namespace lookup; resolved at call time
    result: dict[str, Any] = {}
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if isinstance(value, str):
            result[key] = _compact_protocol_string(value, limit=string_limit)
        elif isinstance(value, (list, tuple)):
            result[key] = _compact_protocol_list(value)
        elif isinstance(value, Mapping):
            result[key] = {
                str(k): (
                    _compact_protocol_string(v, limit=240)
                    if isinstance(v, str)
                    else v
                )
                for k, v in list(value.items())[:12]
                if not isinstance(v, (dict, list, tuple))
            }
        elif value is not None:
            result[key] = value
    return result


def _compact_protocol_jsonish(value: Any, *, depth: int = 0) -> Any:
    from vibecomfy.comfy_nodes.agent.edit import (_MAX_EXECUTION_PROTOCOL_LIST_ITEMS, _compact_protocol_jsonish, _compact_protocol_string)  # T-039 late import: host namespace lookup; resolved at call time
    """Bound structured execution evidence without stringifying its records."""
    if isinstance(value, str):
        return _compact_protocol_string(value, limit=240)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if depth >= 4:
        return _compact_protocol_string(value, limit=240)
    if isinstance(value, Mapping):
        return {
            str(key): _compact_protocol_jsonish(item, depth=depth + 1)
            for key, item in list(value.items())[:16]
        }
    if isinstance(value, (list, tuple)):
        compacted = [
            _compact_protocol_jsonish(item, depth=depth + 1)
            for item in value[:_MAX_EXECUTION_PROTOCOL_LIST_ITEMS]
        ]
        if len(value) > _MAX_EXECUTION_PROTOCOL_LIST_ITEMS:
            compacted.append(
                f"... [{len(value) - _MAX_EXECUTION_PROTOCOL_LIST_ITEMS} omitted]"
            )
        return compacted
    return _compact_protocol_string(value, limit=240)


def _compact_research_source_for_prompt(source: Any) -> dict[str, Any] | None:
    from vibecomfy.comfy_nodes.agent.edit import (_MAX_EXECUTION_PROTOCOL_LIST_ITEMS, _compact_protocol_list, _copy_compact_protocol_fields)  # T-039 late import: host namespace lookup; resolved at call time
    if not isinstance(source, Mapping):
        return None
    compact = _copy_compact_protocol_fields(
        source,
        (
            "source",
            "source_type",
            "pack",
            "class_type",
            "name",
            "title",
            "url",
            "source_workflow_path",
            "description",
            "summary",
            "node_types",
            "workflow_schema_classes",
            "terminal_output_path",
            "minimal_spine",
            "model_families",
            "models",
            "reasons",
            "requested_terms",
            "promotion_gates",
        ),
    )
    if "workflow_schema" in source:
        schema = source.get("workflow_schema")
        if isinstance(schema, Mapping):
            compact["workflow_schema_classes"] = _compact_protocol_list(
                list(schema.keys()),
                limit=_MAX_EXECUTION_PROTOCOL_LIST_ITEMS,
            )
            compact["workflow_schema_omitted"] = (
                "omitted from prompt; exact classes are provisional authoring evidence when surfaced in signatures"
            )
    return compact or None


def _compact_execution_protocol_notes_for_prompt(
    notes: Mapping[str, Any],
    *,
    route: str | None = None,
) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent.edit import (_MAX_EXECUTION_PROTOCOL_SOURCES, _active_manifest_from_plan, _compact_protocol_jsonish, _compact_protocol_list, _compact_protocol_string, _compact_research_source_for_prompt, _copy_compact_protocol_fields, _manifest_compact_payload)  # T-039 late import: host namespace lookup; resolved at call time
    compact: dict[str, Any] = {}

    # W-07 — manifest-preferred compact protocol notes.  When the ADAPT-path
    # plan carries a COMPLETE topology_manifest, the manifest's authoritative
    # class set (nodes[].canonical_class_type) is rendered under the dedicated
    # manifest compactor so the generic per-note list/depth limits cannot
    # silently truncate a large delta.  If the manifest exceeds even the
    # dedicated budget, the manifest path is rejected and the legacy generic
    # compaction runs unchanged (no partial topology is emitted).
    adaptation_plan_raw = notes.get("adaptation_plan")
    manifest_active, manifest = _active_manifest_from_plan(
        adaptation_plan_raw, route=route
    )
    for key in (
        "research_goal",
        "workflow_precedent_status",
        "research_warnings",
    ):
        if key in notes:
            value = notes.get(key)
            if isinstance(value, str):
                compact[key] = _compact_protocol_string(value)
            elif isinstance(value, (list, tuple)):
                compact[key] = _compact_protocol_list(value, limit=8)
            else:
                compact[key] = value

    selected = notes.get("selected_precedent")
    if isinstance(selected, Mapping):
        compact["selected_precedent"] = _copy_compact_protocol_fields(
            selected,
            (
                "name",
                "source",
                "source_workflow_path",
                "minimal_spine",
                "terminal_output_path",
                "model_families",
                "models",
                "reasons",
                "requested_terms",
                "promotion_gates",
            ),
        )

    actionability = notes.get("adaptation_plan_actionability")
    if isinstance(actionability, Mapping):
        compact["adaptation_plan_actionability"] = _copy_compact_protocol_fields(
            actionability,
            (
                "actionability",
                "non_actionable_reason",
                "allowed_followups",
            ),
        )

    adaptation_plan = notes.get("adaptation_plan")
    if manifest_active:
        # W-07 — manifest-preferred compaction.  Render the complete manifest
        # under the dedicated manifest compactor (no generic truncation), and
        # carry the validation/status fields that the agent reads alongside
        # it.  If the manifest exceeds even the dedicated budget, fall back to
        # the legacy generic compaction below (no partial topology).
        compact_manifest = _manifest_compact_payload(manifest) if manifest is not None else None
        if compact_manifest is not None:
            compact_plan: dict[str, Any] = {
                "topology_manifest": compact_manifest,
            }
            if isinstance(adaptation_plan_raw, Mapping):
                for key in (
                    "structural_validation",
                    "semantic_validation",
                    "context_note",
                ):
                    if key in adaptation_plan_raw:
                        compact_plan[key] = _compact_protocol_jsonish(
                            adaptation_plan_raw[key]
                        )
            compact["adaptation_plan"] = compact_plan
            adaptation_plan = None  # legacy block skipped below
        # else: manifest rejected (oversize) -> fall through to legacy generic
        # compaction so notes are still emitted, without the manifest.
    if isinstance(adaptation_plan, Mapping):
        compact_plan = {
            key: _compact_protocol_jsonish(adaptation_plan[key])
            for key in (
                "selected_slice",
                "anchor_bindings",
                "required_new_nodes",
                "required_rewires",
                "edit_ops",
                "structural_validation",
                "semantic_validation",
                "warnings",
                "context_note",
            )
            if key in adaptation_plan
        }
        if compact_plan:
            compact["adaptation_plan"] = compact_plan

    sources = notes.get("research_sources")
    if isinstance(sources, (list, tuple)):
        compact_sources: list[dict[str, Any]] = []
        for source in sources[:_MAX_EXECUTION_PROTOCOL_SOURCES]:
            compact_source = _compact_research_source_for_prompt(source)
            if compact_source:
                compact_sources.append(compact_source)
        if compact_sources:
            compact["research_sources"] = compact_sources
        if len(sources) > _MAX_EXECUTION_PROTOCOL_SOURCES:
            compact["research_sources_omitted"] = len(sources) - _MAX_EXECUTION_PROTOCOL_SOURCES

    for key, value in notes.items():
        if key in compact or key in {
            "_discardability",
            "selected_precedent",
            "research_sources",
            "research_goal",
            "workflow_precedent_status",
            "research_warnings",
            "adaptation_plan",
        }:
            continue
        if isinstance(value, str):
            compact[key] = _compact_protocol_string(value, limit=500)
        elif isinstance(value, (list, tuple)):
            compact[key] = _compact_protocol_list(value, limit=8)
        elif isinstance(value, (int, float, bool)) or value is None:
            compact[key] = value
    return compact


def _dependency_graph_class_types(graph: Any) -> tuple[str, ...]:
    from vibecomfy.comfy_nodes.agent.edit import (_is_ui_only_annotation_class_type)  # T-039 late import: host namespace lookup; resolved at call time
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
        nodes = door_get_nodes(scope)
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
    from vibecomfy.executor.contracts import is_ui_only_annotation_class_type

    return is_ui_only_annotation_class_type(class_type)


def _actionable_plan_ui_only_classes(plan: Mapping[str, Any]) -> tuple[str, ...]:
    from vibecomfy.comfy_nodes.agent.edit import (_is_ui_only_annotation_class_type)  # T-039 late import: host namespace lookup; resolved at call time
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
        nodes = door_get_nodes(candidate_graph)
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
    from vibecomfy.comfy_nodes.agent.edit import (_is_ui_only_annotation_class_type)  # T-039 late import: host namespace lookup; resolved at call time
    """Derive runtime dependency classes from a complete manifest's nodes.

    Reads ONLY ``nodes[].canonical_class_type`` (the authoritative class set).
    Never introduces classes from goldens, filenames, fixture labels, or
    ``prior_path``.  UI-only annotation classes are filtered out via the shared
    conservative classifier.
    """
    if not isinstance(manifest, Mapping):
        return ()
    nodes_raw = door_get_nodes(manifest)
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


def _actionable_plan_required_new_classes(
    state: AgentEditState,
    plan: Mapping[str, Any],
) -> tuple[str, ...]:
    from vibecomfy.comfy_nodes.agent.edit import (_active_manifest_from_plan, _dependency_graph_class_types, _manifest_required_new_classes)  # T-039 late import: host namespace lookup; resolved at call time
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
    manifest_active, manifest = _active_manifest_from_plan(
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


def _actionable_plan_dependency_status(
    state: AgentEditState,
) -> tuple[dict[str, Any], ...]:
    from vibecomfy.comfy_nodes.agent.edit import (_actionable_plan_required_new_classes, _candidate_dict, _candidate_stable_key, _resolver_candidate_supports_class, _workflow_schema_candidates_from_research_context)  # T-039 late import: host namespace lookup; resolved at call time
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
    from vibecomfy.schema import schema_for

    dependencies: list[dict[str, Any]] = []
    for class_type in _actionable_plan_required_new_classes(state, plan):
        if schema_for(state.schema_provider, class_type) is not None:
            dependencies.append(
                {"class_type": class_type, "availability": "live_available"}
            )
            continue

        candidates = [
            dict(candidate)
            for candidate in _workflow_schema_candidates_from_research_context(state)
            if _resolver_candidate_supports_class(candidate, class_type)
        ]
        warnings: list[str] = []
        attempted: list[str] = []
        try:
            from vibecomfy.registry.pack_resolver import resolve_missing_nodes

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
                candidate = _candidate_dict(raw_candidate)
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
                        _resolver_candidate_supports_class(candidate, class_type)
                        or (
                            source in {"comfy-registry", "comfy_registry"}
                            and not registry_resolution_is_ambiguous
                        )
                    )
                ):
                    if _candidate_stable_key(candidate) not in {
                        _candidate_stable_key(existing) for existing in candidates
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


def _retry_after_dependency_preflight_failure(
    state: AgentEditState,
    unresolved_runtime_classes: tuple[str, ...],
) -> None:
    """Reject one poisoned synthesis while preserving evidence for a retry.

    The batch author still receives the inquiry, current graph, and retrieved
    precedent slices, but the unresolved candidate graph is removed so it
    cannot abort or prescribe the next attempt.
    """
    notes = (
        dict(state.execution_protocol_notes)
        if isinstance(state.execution_protocol_notes, Mapping)
        else {}
    )
    notes.pop("adaptation_plan", None)
    notes["adaptation_plan_actionability"] = {
        "actionability": "non_actionable",
        "non_actionable_reason": "dependency_preflight_failed_retry_synthesis",
    }
    notes["synthesis_retry"] = {
        "trigger": "dependency_preflight_failed",
        "rejected_class_types": list(unresolved_runtime_classes),
        "strategy": "choose another retrieved precedent or bounded direct edit",
    }
    state.execution_protocol_notes = notes
    state.executor_adaptation_plan = None


def _hydrate_actionable_registry_dependencies(state: AgentEditState) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (LOGGER, _candidate_stable_key)  # T-039 late import: host namespace lookup; resolved at call time
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
        if _candidate_stable_key(candidate) not in state.provisional_registry_candidate_hashes
    ]
    if not new_candidates:
        return
    try:
        from vibecomfy.schema import ProvisionalRegistrySchemaProvider, with_provisional_gap_filler

        provisional = ProvisionalRegistrySchemaProvider(new_candidates)
        if not provisional.schemas():
            return
        state.provisional_registry_candidate_hashes = frozenset(
            {
                *state.provisional_registry_candidate_hashes,
                *(_candidate_stable_key(candidate) for candidate in new_candidates),
            }
        )
        state.schema_provider = with_provisional_gap_filler(state.schema_provider, provisional)
    except Exception as exc:  # noqa: BLE001 - workflow evidence may still hydrate it
        LOGGER.debug("planned registry dependency hydration unavailable: %s", exc)


__all__ = (
    "_BATCH_PROTOCOL_RETRY_PROMPT",
    "_MANIFEST_COMPACTOR_MAX_ANCHORS",
    "_MANIFEST_COMPACTOR_MAX_EDGES",
    "_MANIFEST_COMPACTOR_MAX_NODES",
    "_MAX_EXECUTION_PROTOCOL_LIST_ITEMS",
    "_MAX_EXECUTION_PROTOCOL_SOURCES",
    "_MAX_EXECUTION_PROTOCOL_STRING",
    "_actionable_plan_dependency_status",
    "_actionable_plan_required_new_classes",
    "_actionable_plan_ui_only_classes",
    "_active_manifest_from_plan",
    "_batch_protocol_parse_reason",
    "_batch_protocol_retry_messages",
    "_compact_execution_protocol_notes_for_prompt",
    "_compact_protocol_jsonish",
    "_compact_protocol_list",
    "_compact_protocol_string",
    "_compact_research_source_for_prompt",
    "_copy_compact_protocol_fields",
    "_dependency_graph_class_types",
    "_evaluate_execution_plan_after_candidate_update",
    "_execution_plan_done_refusal_hint",
    "_execution_plan_status_for_prompt",
    "_hydrate_actionable_registry_dependencies",
    "_is_ui_only_annotation_class_type",
    "_malformed_model_json_detail",
    "_manifest_compact_payload",
    "_manifest_is_complete",
    "_manifest_required_new_classes",
    "_retry_after_dependency_preflight_failure",
)
