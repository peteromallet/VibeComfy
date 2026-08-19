"""
Python load/lower/validate/emit/apply-delta/summarize/audit stages (T-039 extraction of the edit_transform_stages fragment).

Extracted from the edit.py exec-assembled fragments (T-039, ORACLE-6).
The fragment SOURCE string stays in edit.py until T-041 removes the machinery;
this module is the live implementation. Function bodies resolve their free
names from the assembled edit-module namespace at call time (marked with a
T-039 late import comment) so monkeypatches on edit.* stay visible exactly as
under the old exec assembly; guarded imports stay function-local.
"""
from __future__ import annotations

from pathlib import Path
import dataclasses
import json
import time
from typing import Any, Mapping


from vibecomfy.ingest.normalize import door_get_links, door_get_nodes, door_get_widgets_values
def load_agent_generated_scratchpad(path: Any) -> Any:
    """T-039 required_post_split surface: top-level edit-module attr.

    Lazy facade for :func:`vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad`
    that keeps the guarded import function-local (the loader must stay out of
    the eager module-load path); re-exported by edit.py at top level while the
    frozen 472-name __all__ stays unchanged.
    """
    from vibecomfy.security.agent_generated_loader import load_agent_generated_scratchpad as _load

    return _load(path)


def _stage_load_python(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (StageResult, _artifact, _duration_ms)  # T-039 late import: host namespace lookup; resolved at call time
    from vibecomfy.security.agent_generated_loader import load_agent_generated_scratchpad

    start = time.monotonic()
    state.after_py_path.write_text(state.python_after, encoding="utf-8")
    state.edited_workflow = load_agent_generated_scratchpad(state.after_py_path)
    return StageResult(
        stage="load_python",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.after_py_path),),
        gate_updates={"python_load_ok": True},
    )


def _stage_lower(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (_duration_ms, lower_stage_result)  # T-039 late import: host namespace lookup; resolved at call time
    from vibecomfy.porting.lowering import lower_workflow

    start = time.monotonic()
    original_workflow = state.edited_workflow
    lowering = lower_workflow(state.edited_workflow, schema_provider=state.schema_provider)
    result = lower_stage_result(lowering)
    if result.ok:
        if lowering.lowered_count > 0:
            if lowering.workflow is not None:
                state.edited_workflow = lowering.workflow
            state.original_intent_workflow = original_workflow
        else:
            state.edited_workflow = original_workflow
        state.lowering_evidence = [dict(dataclasses.asdict(item)) for item in lowering.evidence]
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_validate(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (ValidationIssue, _duration_ms, validation_errors_payload)  # T-039 late import: host namespace lookup; resolved at call time
    from .diagnostics import validate_stage_result

    start = time.monotonic()
    result = validate_stage_result(state.edited_workflow, schema_provider=state.schema_provider)
    if result.blocking:
        validation_issues: list[ValidationIssue] = []
        for issue in result.issues:
            if not isinstance(issue, Mapping):
                continue
            detail = issue.get("detail")
            validation_issues.append(
                ValidationIssue(
                    code=str(issue.get("code", "validation_error")),
                    message=str(issue.get("message", "Validation error.")),
                    severity=str(issue.get("severity", "error")),
                    detail=dict(detail) if isinstance(detail, Mapping) else {},
                )
            )
        if validation_issues:
            value = dict(result.value or {})
            value["validation_errors"] = validation_errors_payload(validation_issues)
            result = dataclasses.replace(result, value=value)
    return dataclasses.replace(result, duration_ms=_duration_ms(start))


def _stage_emit(state: AgentEditState, _context: TurnContext) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (StageResult, _artifact, _duration_ms, _inject_lowering_provenance)  # T-039 late import: host namespace lookup; resolved at call time
    from vibecomfy.porting.layout import evaluate_felt_delta
    from vibecomfy.porting.layout_store import store_from_ui_json, write_store
    from vibecomfy.porting.emit.ui import emit_ui_json

    start = time.monotonic()
    recovery_report: list[dict[str, Any]] = []
    change_report_out: list[Any] = []
    ui_payload = emit_ui_json(
        state.edited_workflow,
        schema_provider=state.schema_provider,
        prior_store=state.prior_store,
        recovery_report=recovery_report,
        change_report_out=change_report_out,
        guard_original_ui=state.guard_original_ui or state.graph,
        guard_resolved_ops=state.emit_guard_resolved_ops,
        prior_ui_payload=state.guard_original_ui or state.graph,
    )
    state.candidate_ui_path.write_text(
        json.dumps(ui_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_store(state.after_py_path, store_from_ui_json(ui_payload))
    state.ui_payload = ui_payload

    reroute_uids = frozenset(
        (node.uid or node_id)
        for node_id, node in state.edited_workflow.nodes.items()
        if node.class_type == "Reroute"
    )
    felt_report = (
        evaluate_felt_delta(
            state.prior_store,
            ui_payload,
            change_report_out[0],
            reroute_uids=reroute_uids,
        )
        if change_report_out
        else None
    )
    state.report = {
        "change": dataclasses.asdict(change_report_out[0]) if change_report_out else {},
        "recovery": recovery_report,
        "felt": dataclasses.asdict(felt_report) if felt_report is not None else {},
    }
    _inject_lowering_provenance(state)
    return StageResult(
        stage="emit",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.candidate_ui_path),),
        gate_updates={
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
        },
    )


def _ensure_canonical_delta_ops(
    delta_ops: tuple[Any, ...],
    *,
    strict: bool = False,
) -> tuple[Any, ...]:
    from vibecomfy.porting.edit.ops import (
        DELTA_SCHEMA_VERSION,
        ensure_root_scoped_delta_envelope,
        op_to_dict,
    )

    envelope = ensure_root_scoped_delta_envelope(
        {
            "schema_version": DELTA_SCHEMA_VERSION,
            "ops": [op_to_dict(op) for op in delta_ops],
        },
        strict=strict,
    )
    return envelope.ops


def _stage_summarize(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (StageResult, _artifact, _duration_ms, _queue_recovery_report_for_candidate, _record, derive_gates, queue_stage_result)  # T-039 late import: host namespace lookup; resolved at call time
    start = time.monotonic()
    recovery_report = _queue_recovery_report_for_candidate(
        ui_payload=state.ui_payload,
        schema_provider=state.schema_provider,
        original_ui_payload=state.graph,
        existing_recovery_report=(state.report or {}).get("recovery"),
    )
    if state.report is None:
        state.report = {}
    state.report["recovery"] = recovery_report
    queue_result = queue_stage_result(
        recovery_report=recovery_report,
        change_report=(state.report or {}).get("change"),
    )
    _record(context, queue_result)
    derive_gates(
        context,
        queue_blockers=queue_result.issues,
        require_probe_receipt=False,  # offline authoring validation; no live runtime probe here
    )
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "before_python": str(state.before_py_path),
        "after_python": str(state.after_py_path),
        "python": str(state.after_py_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _recovery_report_from_ui_payload(
    ui_payload: Mapping[str, Any] | None,
    schema_provider: Any,
    *,
    original_ui_payload: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build a queue-diagnostics recovery report by re-resolving each UI node.

    The batch-REPL product path does not run ``emit_ui_json``, so it has no
    emit-time recovery report.  This fallback lets the final summarize stage
    still detect schema-less or low-confidence nodes before declaring the
    candidate queue-safe.
    """
    recovery: list[dict[str, Any]] = []
    if ui_payload is None or schema_provider is None:
        return recovery
    nodes = door_get_nodes(ui_payload)
    if not isinstance(nodes, list):
        return recovery
    get_schema = getattr(schema_provider, "get_schema", None)
    if not callable(get_schema):
        return recovery

    def _connection_signature(node: Mapping[str, Any]) -> tuple[Any, ...]:
        inputs = node.get("inputs")
        outputs = node.get("outputs")

        def _input_signature(item: Any) -> tuple[Any, ...] | None:
            if not isinstance(item, Mapping):
                return None
            return (
                item.get("name"),
                item.get("type"),
                item.get("link"),
            )

        def _output_signature(item: Any) -> tuple[Any, ...] | None:
            if not isinstance(item, Mapping):
                return None
            links = door_get_links(item)
            if isinstance(links, list):
                links_sig: Any = tuple(links)
            else:
                links_sig = links
            return (
                item.get("name"),
                item.get("type"),
                item.get("slot_index"),
                links_sig,
            )

        return (
            tuple(
                sig
                for sig in (
                    _input_signature(item)
                    for item in (inputs if isinstance(inputs, list) else [])
                )
                if sig is not None
            ),
            tuple(
                sig
                for sig in (
                    _output_signature(item)
                    for item in (outputs if isinstance(outputs, list) else [])
                )
                if sig is not None
            ),
        )

    def _linked_input_signature(
        node: Mapping[str, Any],
        *,
        links_by_id: Mapping[Any, Any],
        nodes_by_id: Mapping[str, Mapping[str, Any]],
    ) -> tuple[tuple[Any, str], ...]:
        """Return linked input names and their stable destination node uids."""

        linked: list[tuple[Any, str]] = []
        for item in node.get("inputs") if isinstance(node.get("inputs"), list) else []:
            if not isinstance(item, Mapping) or item.get("link") is None:
                continue
            link = links_by_id.get(item.get("link"))
            destination_id: Any = None
            if isinstance(link, list) and len(link) >= 3:
                destination_id = link[3] if len(link) >= 5 else node.get("id")
            elif isinstance(link, Mapping):
                destination_id = link.get("target_id", link.get("to_node", node.get("id")))
            destination_node = nodes_by_id.get(str(destination_id))
            destination_uid = (
                _stable_node_uid(destination_node)
                if destination_node is not None
                else str(destination_id)
            )
            linked.append((item.get("name"), destination_uid))
        return tuple(sorted(linked, key=lambda value: (str(value[0]), value[1])))

    def _node_widget_signature(node: Mapping[str, Any]) -> Any:
        def _stable(value: Any) -> str:
            return json.dumps(value, sort_keys=True, default=str)

        widgets = door_get_widgets_values(node)
        if isinstance(widgets, list):
            return tuple(_stable(value) for value in widgets)
        if isinstance(widgets, Mapping):
            return tuple(
                (str(key), _stable(value))
                for key, value in sorted(widgets.items(), key=lambda item: str(item[0]))
            )
        return None

    def _node_widget_shape_signature(node: Mapping[str, Any]) -> Any:
        widgets = door_get_widgets_values(node)
        if isinstance(widgets, list):
            return ("list", len(widgets))
        if isinstance(widgets, Mapping):
            return (
                "mapping",
                tuple(sorted((str(key) for key in widgets), key=str)),
            )
        return (type(widgets).__name__,)

    def _original_ui_node(node: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return the LiteGraph surface nested in an ingested IR node, if any."""
        metadata = node.get("metadata")
        if isinstance(metadata, Mapping):
            raw_ui = metadata.get("_ui")
            if isinstance(raw_ui, Mapping):
                return raw_ui
        return node

    def _stable_node_uid(node: Mapping[str, Any]) -> str:
        properties = node.get("properties")
        if isinstance(properties, Mapping):
            uid = properties.get("vibecomfy_uid")
            if uid is not None and str(uid):
                return str(uid)
        uid = node.get("uid")
        if uid is not None and str(uid):
            return str(uid)
        return str(node.get("id", ""))

    def _node_output_slots(node: Mapping[str, Any]) -> dict[tuple[Any, Any, Any], set[Any]]:
        outputs = node.get("outputs")
        slots: dict[tuple[Any, Any, Any], set[Any]] = {}
        if not isinstance(outputs, list):
            return slots
        for item in outputs:
            if not isinstance(item, Mapping):
                continue
            key = (item.get("name"), item.get("type"), item.get("slot_index"))
            links = door_get_links(item)
            slots[key] = set(links if isinstance(links, list) else [])
        return slots

    def _ui_links_by_id(ui_payload: Mapping[str, Any] | None) -> dict[Any, Any]:
        links = door_get_links(ui_payload) if isinstance(ui_payload, Mapping) else None
        if not isinstance(links, list):
            return {}
        result: dict[Any, Any] = {}
        for link in links:
            if isinstance(link, list) and link:
                result[link[0]] = link
            elif isinstance(link, Mapping) and "id" in link:
                result[link.get("id")] = link
        return result

    def _link_destination(link: Any) -> tuple[str, Any] | None:
        if isinstance(link, list) and len(link) >= 5:
            return (str(link[3]), link[4])
        if isinstance(link, Mapping):
            target_id = link.get("target_id", link.get("to_node"))
            target_slot = link.get("target_slot", link.get("to_slot"))
            if target_id is not None:
                return (str(target_id), target_slot)
        return None

    def _output_destinations(
        output_links: set[Any],
        links_by_id: Mapping[Any, Any],
    ) -> dict[tuple[str, Any], Any]:
        destinations: dict[tuple[str, Any], Any] = {}
        for link_id in output_links:
            destination = _link_destination(links_by_id.get(link_id))
            if destination is not None:
                destinations[destination] = link_id
        return destinations

    def _node_output_link_ids(node: Mapping[str, Any]) -> set[Any]:
        outputs = node.get("outputs")
        if not isinstance(outputs, list):
            return set()
        link_ids: set[Any] = set()
        for output in outputs:
            if not isinstance(output, Mapping):
                continue
            links = door_get_links(output)
            if isinstance(links, list):
                link_ids.update(links)
        return link_ids

    def _transitive_path_nodes_to_destination(
        *,
        start_links: set[Any],
        destination: tuple[str, Any],
        candidate_links_by_id: Mapping[Any, Any],
        candidate_nodes_by_id: Mapping[str, Mapping[str, Any]],
    ) -> tuple[str, ...] | None:
        queue: list[tuple[Any, tuple[str, ...]]] = [
            (link_id, ()) for link_id in sorted(start_links, key=lambda value: str(value))
        ]
        visited_links: set[Any] = set()
        while queue:
            link_id, path_nodes = queue.pop(0)
            if link_id in visited_links:
                continue
            visited_links.add(link_id)
            link = candidate_links_by_id.get(link_id)
            if link is None:
                continue
            current_destination = _link_destination(link)
            if current_destination is None:
                continue
            destination_node_id, _destination_slot = current_destination
            next_path = (*path_nodes, destination_node_id)
            if current_destination == destination:
                return next_path
            if destination_node_id in path_nodes:
                continue
            next_node = candidate_nodes_by_id.get(destination_node_id)
            if next_node is None:
                continue
            for next_link_id in sorted(_node_output_link_ids(next_node), key=lambda value: str(value)):
                if next_link_id not in visited_links:
                    queue.append((next_link_id, next_path))
        return None

    def _preexisting_schema_less_queue_safe(
        *,
        original_node: Mapping[str, Any] | None,
        candidate_node: Mapping[str, Any],
        original_links_by_id: Mapping[Any, Any],
        candidate_links_by_id: Mapping[Any, Any],
        original_nodes_by_id: Mapping[str, Mapping[str, Any]],
        candidate_node_ids: set[str],
        candidate_nodes_by_id: Mapping[str, Mapping[str, Any]],
        schema_less_transitive_intermediates: set[str],
    ) -> tuple[bool, str]:
        if original_node is None:
            candidate_node_id = str(candidate_node.get("id", ""))
            if candidate_node_id in schema_less_transitive_intermediates:
                return (True, "transitive_reroute_intermediate")
            return (False, "new_schema_less_node")
        if original_node.get("type") != candidate_node.get("type"):
            return (False, "schema_less_class_changed")
        if _node_widget_shape_signature(original_node) != _node_widget_shape_signature(
            candidate_node
        ):
            return (False, "schema_less_widget_shape_changed")
        linked_inputs_unchanged = _linked_input_signature(
            original_node,
            links_by_id=original_links_by_id,
            nodes_by_id=original_nodes_by_id,
        ) == _linked_input_signature(
            candidate_node,
            links_by_id=candidate_links_by_id,
            nodes_by_id=candidate_nodes_by_id,
        )
        if not linked_inputs_unchanged:
            return (False, "schema_less_inputs_changed")
        original_slots = _node_output_slots(original_node)
        candidate_slots = _node_output_slots(candidate_node)
        # RC5: compare output *names* only. Link-id / slot_index churn after
        # inserting a downstream node is not a schema-less slot rename.
        if {key[0] for key in original_slots} != {key[0] for key in candidate_slots}:
            return (False, "schema_less_output_slots_changed")
        widgets_changed = _node_widget_signature(original_node) != _node_widget_signature(
            candidate_node
        )
        if (
            not widgets_changed
            and _connection_signature(original_node) == _connection_signature(candidate_node)
        ):
            return (True, "connection_shape_unchanged")
        def _links_for_slot_name(
            slots: Mapping[tuple[Any, Any, Any], set[Any]],
            slot_name: Any,
        ) -> set[Any]:
            combined: set[Any] = set()
            for key, links in slots.items():
                if key[0] == slot_name:
                    combined.update(links)
            return combined

        for key, original_links in original_slots.items():
            candidate_links = _links_for_slot_name(candidate_slots, key[0])
            original_destinations = _output_destinations(
                original_links,
                original_links_by_id,
            )
            candidate_destinations = _output_destinations(
                candidate_links,
                candidate_links_by_id,
            )
            for destination in set(original_destinations) - set(candidate_destinations):
                destination_node_id, _ = destination
                if destination_node_id in candidate_node_ids:
                    path_nodes = _transitive_path_nodes_to_destination(
                        start_links=candidate_links,
                        destination=destination,
                        candidate_links_by_id=candidate_links_by_id,
                        candidate_nodes_by_id=candidate_nodes_by_id,
                    )
                    if path_nodes is not None:
                        continue
                    return (False, "schema_less_existing_output_links_removed")
        if widgets_changed:
            # Schema-less emit may reorder linked inputs, remint their types to
            # UNKNOWN, and omit unlinked optionals. Stable linked input names,
            # destination uids, and output destinations prove that this remains a
            # bounded value-only edit rather than a topology change.
            return (True, "preexisting_schema_less_widget_values_changed")
        for key, original_links in original_slots.items():
            candidate_links = candidate_slots.get(key, set())
            original_destinations = _output_destinations(
                original_links,
                original_links_by_id,
            )
            candidate_destinations = _output_destinations(
                candidate_links,
                candidate_links_by_id,
            )
            if set(original_destinations) - set(candidate_destinations):
                return (True, "transitive_output_destinations_safe")
        return (True, "preexisting_output_destinations_safe")

    def _schema_less_transitive_reroute_intermediates() -> set[str]:
        intermediates: set[str] = set()
        for node_id, original_node in original_nodes_by_id.items():
            candidate_node = candidate_nodes_by_id.get(node_id)
            if candidate_node is None:
                continue
            if str(original_node.get("type", "")) != str(candidate_node.get("type", "")):
                continue
            original_slots = _node_output_slots(original_node)
            candidate_slots = _node_output_slots(candidate_node)
            if set(original_slots) != set(candidate_slots):
                continue
            for key, original_links in original_slots.items():
                candidate_links = candidate_slots.get(key, set())
                original_destinations = _output_destinations(
                    original_links,
                    original_links_by_id,
                )
                candidate_destinations = _output_destinations(
                    candidate_links,
                    candidate_links_by_id,
                )
                for destination in set(original_destinations) - set(candidate_destinations):
                    path_nodes = _transitive_path_nodes_to_destination(
                        start_links=candidate_links,
                        destination=destination,
                        candidate_links_by_id=candidate_links_by_id,
                        candidate_nodes_by_id=candidate_nodes_by_id,
                    )
                    if path_nodes is None:
                        continue
                    destination_node_id, _ = destination
                    intermediates.update(
                        path_node
                        for path_node in path_nodes
                        if path_node not in {node_id, destination_node_id}
                    )
        return intermediates

    def _local_node_schema_evidence(class_type: str) -> dict[str, Any] | None:
        try:
            from vibecomfy.comfy_nodes import NODE_CLASS_MAPPINGS  # noqa: PLC0415
        except Exception:
            return None
        node_cls = NODE_CLASS_MAPPINGS.get(class_type)
        if node_cls is None:
            return None
        input_types = getattr(node_cls, "INPUT_TYPES", None)
        if not callable(input_types):
            return None
        try:
            input_types()
        except Exception:
            return None
        return {
            "provider": "vibecomfy_local_node_mapping",
            "confidence": 1.0,
            "schema_less": False,
            "diagnostic": "trusted local VibeComfy node class schema",
        }

    original_node_classes: dict[str, str] = {}
    original_node_connections: dict[str, tuple[Any, ...]] = {}
    original_nodes_by_id: dict[str, Mapping[str, Any]] = {}
    original_nodes_by_uid: dict[str, Mapping[str, Any]] = {}
    candidate_nodes_by_id: dict[str, Mapping[str, Any]] = {}
    original_links_by_id = _ui_links_by_id(original_ui_payload)
    candidate_links_by_id = _ui_links_by_id(ui_payload)
    candidate_node_ids: set[str] = set()
    original_nodes = (
        door_get_nodes(original_ui_payload)
        if isinstance(original_ui_payload, Mapping)
        else None
    )
    if isinstance(original_nodes, list):
        for original_node in original_nodes:
            if not isinstance(original_node, Mapping):
                continue
            original_surface = _original_ui_node(original_node)
            original_node_id = str(
                original_surface.get("id", original_node.get("id", original_node.get("uid", "")))
            )
            original_class_type = str(
                original_surface.get("type", original_node.get("class_type", ""))
            )
            if original_node_id and original_class_type:
                original_uid = _stable_node_uid(original_surface)
                original_node_classes[original_uid] = original_class_type
                original_nodes_by_id[original_node_id] = original_surface
                original_nodes_by_uid[original_uid] = original_surface
                original_node_connections[original_uid] = _connection_signature(
                    original_surface
                )
    for candidate_node in nodes:
        if isinstance(candidate_node, Mapping):
            candidate_node_id = str(candidate_node.get("id", ""))
            if candidate_node_id:
                candidate_node_ids.add(candidate_node_id)
                candidate_nodes_by_id[candidate_node_id] = candidate_node
    schema_less_transitive_intermediates = _schema_less_transitive_reroute_intermediates()

    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        node_id = str(node.get("id", ""))
        class_type = str(node.get("type", ""))
        if not class_type:
            continue
        stable_uid = _stable_node_uid(node)
        preexisting_ui_node = original_node_classes.get(stable_uid) == class_type
        ui_connection_shape_unchanged = (
            preexisting_ui_node
            and original_node_connections.get(stable_uid) == _connection_signature(node)
        )
        schema = get_schema(class_type)
        if schema is None:
            local_schema_evidence = _local_node_schema_evidence(class_type)
            if local_schema_evidence is not None:
                recovery.append(
                    {
                        "node_id": node_id,
                        "stable_uid": stable_uid,
                        "class_type": class_type,
                        **local_schema_evidence,
                        "preexisting_ui_node": preexisting_ui_node,
                        "ui_connection_shape_unchanged": ui_connection_shape_unchanged,
                        "schema_less_safety": "local_node_schema",
                        "widget_shape_verdict": "not_applicable",
                    }
                )
                continue
            schema_less_safe, schema_less_reason = _preexisting_schema_less_queue_safe(
                original_node=original_nodes_by_uid.get(stable_uid)
                if preexisting_ui_node
                else None,
                candidate_node=node,
                original_links_by_id=original_links_by_id,
                candidate_links_by_id=candidate_links_by_id,
                original_nodes_by_id=original_nodes_by_id,
                candidate_node_ids=candidate_node_ids,
                candidate_nodes_by_id=candidate_nodes_by_id,
                schema_less_transitive_intermediates=schema_less_transitive_intermediates,
            )
            recovery.append(
                {
                    "node_id": node_id,
                    "stable_uid": stable_uid,
                    "class_type": class_type,
                    "provider": None,
                    "confidence": None,
                    "schema_less": True,
                    "preexisting_ui_node": preexisting_ui_node,
                    "ui_connection_shape_unchanged": ui_connection_shape_unchanged,
                    "schema_less_queue_safe": schema_less_safe,
                    "schema_less_safety": schema_less_reason,
                    "schema_less_queue_schema": {
                        "inputs": [
                            {"name": item.get("name"), "type": item.get("type")}
                            for item in (
                                node.get("inputs")
                                if isinstance(node.get("inputs"), list)
                                else []
                            )
                            if isinstance(item, Mapping)
                        ],
                        "outputs": [
                            {
                                "name": item.get("name"),
                                "type": item.get("type"),
                                "slot_index": item.get("slot_index"),
                            }
                            for item in (
                                node.get("outputs")
                                if isinstance(node.get("outputs"), list)
                                else []
                            )
                            if isinstance(item, Mapping)
                        ],
                    },
                    "widget_shape_verdict": "not_applicable",
                    "diagnostic": "schema-less: no schema provider evidence for node",
                }
            )
        else:
            recovery.append(
                {
                    "node_id": node_id,
                    "stable_uid": stable_uid,
                    "class_type": class_type,
                    "provider": getattr(schema, "source_provider", None),
                    "confidence": getattr(schema, "confidence", None),
                    "schema_less": False,
                    "preexisting_ui_node": preexisting_ui_node,
                    "ui_connection_shape_unchanged": ui_connection_shape_unchanged,
                    "widget_shape_verdict": "not_applicable",
                }
            )
    return recovery


def _queue_recovery_report_for_candidate(
    *,
    ui_payload: Mapping[str, Any] | None,
    schema_provider: Any,
    original_ui_payload: Mapping[str, Any] | None = None,
    existing_recovery_report: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> list[dict[str, Any]]:
    from vibecomfy.comfy_nodes.agent.edit import (_recovery_report_from_ui_payload)  # T-039 late import: host namespace lookup; resolved at call time
    resolved_recovery = _recovery_report_from_ui_payload(
        ui_payload,
        schema_provider,
        original_ui_payload=original_ui_payload,
    )
    if not resolved_recovery:
        return list(existing_recovery_report or ())
    if not existing_recovery_report:
        return resolved_recovery

    def _recovery_identity(entry: Mapping[str, Any]) -> tuple[str, str] | None:
        node_identity = entry.get("stable_uid", entry.get("uid", entry.get("node_id")))
        class_type = entry.get("class_type")
        if node_identity is None or class_type is None:
            return None
        return (str(node_identity), str(class_type))

    resolved_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in resolved_recovery:
        if not isinstance(entry, Mapping):
            continue
        key = _recovery_identity(entry)
        if key is None:
            continue
        resolved_by_key[key] = dict(entry)

    queue_fields = (
        "provider",
        "confidence",
        "schema_less",
        "stable_uid",
        "preexisting_ui_node",
        "ui_connection_shape_unchanged",
        "schema_less_queue_safe",
        "schema_less_safety",
        "schema_less_queue_schema",
    )
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for existing in existing_recovery_report:
        if not isinstance(existing, Mapping):
            continue
        merged_entry = dict(existing)
        key = _recovery_identity(merged_entry)
        if key is None:
            merged.append(merged_entry)
            continue
        seen.add(key)
        overlay = resolved_by_key.get(key)
        if overlay is not None:
            for field in queue_fields:
                if field in overlay:
                    merged_entry[field] = overlay[field]
            if merged_entry.get("diagnostic") is None and overlay.get("diagnostic") is not None:
                merged_entry["diagnostic"] = overlay["diagnostic"]
        merged.append(merged_entry)

    for key, overlay in resolved_by_key.items():
        if key in seen:
            continue
        merged.append(dict(overlay))
    return merged


def _stage_summarize_v2(state: AgentEditState, context: TurnContext) -> StageResult:
    from vibecomfy.comfy_nodes.agent.edit import (StageResult, _artifact, _duration_ms, _queue_recovery_report_for_candidate, _record, derive_gates, queue_stage_result)  # T-039 late import: host namespace lookup; resolved at call time
    start = time.monotonic()
    recovery_report = _queue_recovery_report_for_candidate(
        ui_payload=state.ui_payload,
        schema_provider=state.schema_provider,
        original_ui_payload=state.graph,
        existing_recovery_report=(state.report or {}).get("recovery"),
    )
    if state.report is None:
        state.report = {}
    state.report["recovery"] = recovery_report
    queue_result = queue_stage_result(
        recovery_report=recovery_report,
        change_report=(state.report or {}).get("change"),
    )
    _record(context, queue_result)
    derive_gates(
        context,
        queue_blockers=queue_result.issues,
        require_probe_receipt=False,  # offline authoring validation; no live runtime probe here
    )
    state.report["queue_blockers"] = [dict(issue) for issue in queue_result.issues]
    state.messages_path.open("a", encoding="utf-8").write(
        json.dumps({"task": state.task, "message": state.user_message}, sort_keys=True) + "\n"
    )
    state.artifacts = {
        "request": str(state.request_path),
        "original_ui": str(state.original_ui_path),
        "projection": str(state.projection_path),
        "model_request": str(state.model_request_path),
        "model_response": str(state.model_response_path),
        "candidate_ui": str(state.candidate_ui_path),
        "messages": str(state.messages_path),
    }
    return StageResult(
        stage="summarize",
        ok=True,
        blocking=False,
        duration_ms=_duration_ms(start),
        artifacts=(_artifact(state.messages_path),),
        value={
            "mode": "agent_edit_v2_delta",
            "queue_validate_ok": queue_result.ok,
            "queue_blockers": [dict(issue) for issue in queue_result.issues],
        },
    )


def _stage_audit(
    state: AgentEditState,
    context: TurnContext,
    *,
    response: dict[str, Any] | None = None,
    failure: FailureEnvelope | None = None,
) -> ArtifactRef:
    from vibecomfy.comfy_nodes.agent.edit import (_agent_edit_batch_repl_enabled, _build_lowering_audit_entries, _canonical_delta_ops_envelope_payload, _json_safe, normalize_agent_edit_v2_metadata, write_audit)  # T-039 late import: host namespace lookup; resolved at call time
    metadata: dict[str, Any] = {
        "provider": state.provider_metadata or {},
        "lowering": _build_lowering_audit_entries(state.lowering_evidence),
    }
    if _agent_edit_batch_repl_enabled():
        metadata["batch_repl"] = {
            "enabled": True,
            "turn_count": state.batch_turn_count,
            "signature_catalog_available": bool(state.batch_signature_catalog),
            "feedback": state.batch_feedback,
            "final_summary": state.batch_final_summary,
            "exit_mode": state.batch_exit_mode,
            "done_summary": state.batch_done_summary,
            "budget_state": _json_safe(state.batch_budget_state),
        }
    if state.revision_evidence is not None:
        metadata["revision_evidence"] = state.revision_evidence.to_dict()
    return write_audit(
        state.turn_dir / "audit",
        context=context,
        turn_state="candidate",
        stage_results=context.stage_results,
        failure=failure,
        response=response,
        artifacts={
            name: Path(path)
            for name, path in (state.artifacts or {
                "request": str(state.request_path),
                "original_ui": str(state.original_ui_path),
                "before_python": str(state.before_py_path),
                "after_python": str(state.after_py_path),
                "python": str(state.after_py_path),
                "model_request": str(state.model_request_path),
                "model_response": str(state.model_response_path),
                "candidate_ui": str(state.candidate_ui_path),
                "messages": str(state.messages_path),
            }).items()
            if Path(path).exists()
        },
        metadata=metadata,
    )


def _write_unknown_transition_audits(
    *,
    session_root: Path,
    session_id: str,
    baseline_turn_id: str | None,
    unknown_transitions: tuple[dict[str, Any], ...],
    request_payload: Mapping[str, Any],
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (TurnContext, turn_dir_for, write_audit)  # T-039 late import: host namespace lookup; resolved at call time
    for transition in unknown_transitions:
        turn_id = transition.get("turn_id")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        try:
            write_audit(
                turn_dir_for(session_root, session_id, turn_id) / "unknown_audit",
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


__all__ = (
    "_ensure_canonical_delta_ops",
    "_queue_recovery_report_for_candidate",
    "_recovery_report_from_ui_payload",
    "_stage_audit",
    "_stage_emit",
    "_stage_load_python",
    "_stage_lower",
    "_stage_summarize",
    "_stage_summarize_v2",
    "_stage_validate",
    "_write_unknown_transition_audits",
)
