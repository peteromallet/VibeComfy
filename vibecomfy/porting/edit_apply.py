from __future__ import annotations

import copy
from dataclasses import dataclass
import time
from typing import Any, Mapping

from vibecomfy.porting.edit_ledger import EditLedger, ScopeState
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
    ReorderOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.object_info.consume import output_names as cached_output_names
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.ui_emitter import materialize_litegraph_node
from vibecomfy.porting.widget_schema import effective_widget_names_for_class
from vibecomfy.schema import InputSpec, schema_for, socket_types_compatible


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    detail: Mapping[str, Any] | None = None,
) -> PortIssue:
    return PortIssue(code=code, message=message, severity=severity, detail=dict(detail or {}))


@dataclass(frozen=True, slots=True)
class ResolvedFieldRef:
    target: NodeFieldTarget
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None
    input_name: str | None
    input_slot_index: int | None
    widget_index: int | None
    widget_key: str | None
    schema_input: InputSpec | None
    automatic_link_removal: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedNodeRef:
    target: NodeTarget
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None


@dataclass(frozen=True, slots=True)
class ResolvedLinkEndpoint:
    ref: LinkSourceRef | LinkTargetRef
    node: Mapping[str, Any]
    class_type: str
    node_id: int | str | None
    slot_index: int | None
    slot_name: str
    socket_type: str | None


@dataclass(frozen=True, slots=True)
class ResolvedRemoveLinkRef:
    scope_path: str
    link_id: int
    link: Any


@dataclass(frozen=True, slots=True)
class ResolvedLinkRewire:
    scope_path: str
    link_id: int
    old_origin_id: int
    new_origin_id: int
    new_origin_slot: int


@dataclass(frozen=True, slots=True)
class ResolvedRemoveNodePlan:
    node_ref: ResolvedNodeRef
    link_ids_to_remove: tuple[int, ...]
    link_rewires: tuple[ResolvedLinkRewire, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedAddNodeSpec:
    op: AddNodeOp
    scope: ScopeState
    schema: Any
    schema_inputs: Mapping[str, InputSpec]
    resolved_inputs: Mapping[str, ResolvedLinkEndpoint]
    anchor_near: ResolvedNodeRef | None = None
    anchor_between: tuple[ResolvedNodeRef, ResolvedNodeRef] | None = None
    anchor_group_index: int | None = None
    anchor_group_title: str | None = None


@dataclass(frozen=True, slots=True)
class AppliedAddNodeSpec:
    op: AddNodeOp
    scope_path: str
    uid: str
    node_id: int
    link_ids: tuple[int, ...]
    source_uids: tuple[str, ...]
    group_index: int | None = None


ResolvedOp = (
    ResolvedFieldRef
    | ResolvedNodeRef
    | tuple[ResolvedLinkEndpoint, ResolvedLinkEndpoint]
    | ResolvedRemoveLinkRef
    | ResolvedRemoveNodePlan
    | ResolvedAddNodeSpec
    | AppliedAddNodeSpec
)


@dataclass(frozen=True, slots=True)
class ResolveResult:
    ok: bool
    ledger: EditLedger
    diagnostics: tuple[PortIssue, ...]
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyResult:
    ok: bool
    candidate: dict[str, Any] | None
    diagnostics: tuple[PortIssue, ...]
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...] = ()
    mutation_started: bool = False
    guard_result: GuardResult | None = None


@dataclass(frozen=True, slots=True)
class GuardResult:
    ok: bool
    diagnostics: tuple[PortIssue, ...]
    normalize_fallback_used: bool = False
    normalize_allow_list_used: bool = False


def resolve_delta(
    original_ui: Mapping[str, Any],
    delta: tuple[EditOp, ...],
    *,
    schema_provider: Any = None,
) -> ResolveResult:
    ledger = EditLedger.ingest(original_ui)
    diagnostics: list[PortIssue] = list(ledger.diagnostics)
    resolved_ops: list[tuple[EditOp, ResolvedOp]] = []

    for op in delta:
        resolved, issues = _resolve_op(ledger, op, schema_provider=schema_provider)
        diagnostics.extend(issues)
        if any(issue.severity == "error" for issue in issues):
            return ResolveResult(
                ok=False,
                ledger=ledger,
                diagnostics=tuple(diagnostics),
                resolved_ops=tuple(resolved_ops),
            )
        assert resolved is not None
        if isinstance(op, AddNodeOp):
            applied_resolved, apply_diagnostics = _apply_resolved_op(ledger, op, resolved)
            diagnostics.extend(apply_diagnostics)
            resolved_ops.append((op, applied_resolved))
            continue
        resolved_ops.append((op, resolved))

    if delta:
        _sync_scope_counters(ledger)

    return ResolveResult(
        ok=True,
        ledger=ledger,
        diagnostics=tuple(diagnostics),
        resolved_ops=tuple(resolved_ops),
    )


def apply_delta(
    original_ui: Mapping[str, Any],
    delta: tuple[EditOp, ...],
    *,
    schema_provider: Any = None,
) -> ApplyResult:
    stamped_before = EditLedger.ingest(original_ui).stamped_copy() if delta else None
    resolved = resolve_delta(original_ui, delta, schema_provider=schema_provider)
    if not resolved.ok:
        return ApplyResult(
            ok=False,
            candidate=None,
            diagnostics=resolved.diagnostics,
            resolved_ops=resolved.resolved_ops,
            mutation_started=False,
        )
    if delta:
        candidate_ledger = resolved.ledger
        diagnostics = list(resolved.diagnostics)
        applied_resolved_ops: list[tuple[EditOp, ResolvedOp]] = []
        for op, resolved_op in resolved.resolved_ops:
            if isinstance(op, AddNodeOp):
                assert isinstance(resolved_op, AppliedAddNodeSpec)
                applied_resolved_ops.append((op, resolved_op))
                continue
            applied_resolved, apply_diagnostics = _apply_resolved_op(candidate_ledger, op, resolved_op)
            diagnostics.extend(apply_diagnostics)
            applied_resolved_ops.append((op, applied_resolved))
        _sync_scope_counters(candidate_ledger)
        assert stamped_before is not None
        guard = guard_full_ui(stamped_before, candidate_ledger.graph, tuple(applied_resolved_ops))
        diagnostics.extend(guard.diagnostics)
        if not guard.ok:
            return ApplyResult(
                ok=False,
                candidate=None,
                diagnostics=tuple(diagnostics),
                resolved_ops=tuple(applied_resolved_ops),
                mutation_started=True,
                guard_result=guard,
            )
        return ApplyResult(
            ok=True,
            candidate=candidate_ledger.graph,
            diagnostics=tuple(diagnostics),
            resolved_ops=tuple(applied_resolved_ops),
            mutation_started=True,
            guard_result=guard,
        )
    return ApplyResult(
        ok=True,
        candidate=copy.deepcopy(dict(original_ui)),
        diagnostics=resolved.diagnostics,
        resolved_ops=resolved.resolved_ops,
        mutation_started=False,
        guard_result=None,
    )


def _apply_resolved_op(
    ledger: EditLedger,
    op: EditOp,
    resolved_op: ResolvedOp,
) -> tuple[ResolvedOp, list[PortIssue]]:
    if isinstance(op, SetNodeFieldOp):
        assert isinstance(resolved_op, ResolvedFieldRef)
        return resolved_op, _apply_set_node_field(ledger, resolved_op, op.value)
    if isinstance(op, SetModeOp):
        assert isinstance(resolved_op, ResolvedNodeRef)
        _apply_set_mode(resolved_op, op.mode)
        return resolved_op, []
    if isinstance(op, RemoveLinkOp):
        assert isinstance(resolved_op, ResolvedRemoveLinkRef)
        return resolved_op, _apply_remove_link(ledger, resolved_op)
    if isinstance(op, RemoveNodeOp):
        assert isinstance(resolved_op, ResolvedRemoveNodePlan)
        return resolved_op, _apply_remove_node(ledger, resolved_op)
    if isinstance(op, UpsertLinkOp):
        assert isinstance(resolved_op, tuple)
        source, target = resolved_op
        assert isinstance(source, ResolvedLinkEndpoint)
        assert isinstance(target, ResolvedLinkEndpoint)
        return resolved_op, _apply_upsert_link(ledger, source, target)
    if isinstance(op, AddNodeOp):
        assert isinstance(resolved_op, ResolvedAddNodeSpec)
        return _apply_add_node(ledger, resolved_op)
    assert isinstance(op, ReorderOp)
    assert isinstance(resolved_op, ResolvedNodeRef)
    return resolved_op, _apply_reorder(resolved_op, op)


def guard_full_ui(
    stamped_original_ui: Mapping[str, Any],
    candidate_ui: Mapping[str, Any],
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...],
    *,
    normalize_timeout_ms: int = 200,
) -> GuardResult:
    original_norm, candidate_norm, allow_fallback_paths = _normalize_for_guard(
        stamped_original_ui,
        candidate_ui,
        timeout_ms=normalize_timeout_ms,
    )
    original_ledger = EditLedger.ingest(original_norm)
    candidate_ledger = EditLedger.ingest(candidate_norm)
    _align_candidate_scope_paths(original_ledger, candidate_ledger)
    attribution = _guard_attribution(original_ledger, candidate_ledger, resolved_ops)
    diagnostics: list[PortIssue] = []

    for scope_path, original_scope in original_ledger.scopes.items():
        candidate_scope = candidate_ledger.scopes.get(scope_path)
        if candidate_scope is None:
            diagnostics.append(
                _issue(
                    "full_ui_scope_removed",
                    "Candidate removed a UI scope without an attributed operation.",
                    detail={"scope_path": scope_path},
                )
            )
            continue
        diagnostics.extend(
            _guard_scope_fields(
                scope_path,
                original_scope.graph,
                candidate_scope.graph,
                allowed_paths=attribution["scope_field_paths"].get(scope_path, set()),
            )
        )
        diagnostics.extend(
            _guard_scope_links(
                scope_path,
                original_scope.graph,
                candidate_scope.graph,
                removed_links=attribution["removed_links"],
                new_links=attribution["new_links"],
                touched_links=attribution["touched_links"],
            )
        )
        diagnostics.extend(
            _guard_node_order(
                scope_path,
                original_scope.graph,
                candidate_scope.graph,
                removed_nodes=attribution["removed_nodes"],
                new_nodes=attribution["new_nodes"],
            )
        )

    for scope_path in candidate_ledger.scopes:
        if scope_path not in original_ledger.scopes:
            diagnostics.append(
                _issue(
                    "full_ui_scope_added",
                    "Candidate added a UI scope without an attributed operation.",
                    detail={"scope_path": scope_path},
                )
            )

    original_nodes = original_ledger.node_index
    candidate_nodes = candidate_ledger.node_index
    for key, original_node in original_nodes.items():
        scope_path, uid = key
        candidate_node = candidate_nodes.get(key)
        if candidate_node is None:
            if key in attribution["removed_nodes"]:
                continue
            diagnostics.append(
                _issue(
                    "full_ui_node_removed_unattributed",
                    "Candidate removed an out-of-delta node.",
                    detail={"scope_path": scope_path, "uid": uid},
                )
            )
            continue
        if candidate_node == original_node:
            continue
        diffs = _value_diff_paths(original_node, candidate_node)
        allowed_paths = attribution["node_paths"].get(key, set())
        if diffs and _all_diffs_op_allowed(diffs, allowed_paths):
            continue
        if allow_fallback_paths and diffs and _all_diffs_normalize_allowed(original_node, candidate_node, diffs):
            diagnostics.append(
                _issue(
                    "full_ui_normalize_allow_list_used",
                    "Allowed fallback-only cosmetic node churn from the measured normalize allow-list.",
                    severity="info",
                    detail={"scope_path": scope_path, "uid": uid, "field_paths": diffs},
                )
            )
            continue
        diagnostics.append(
            _issue(
                "full_ui_node_changed_unattributed",
                "Candidate changed an out-of-delta node.",
                detail={"scope_path": scope_path, "uid": uid, "field_paths": diffs[:20]},
            )
        )

    for key in candidate_nodes:
        if key in original_nodes:
            continue
        if key in attribution["new_nodes"]:
            continue
        diagnostics.append(
            _issue(
                "full_ui_node_added_unattributed",
                "Candidate added a node without an attributed add_node operation.",
                detail={"scope_path": key[0], "uid": key[1]},
            )
        )

    return GuardResult(
        ok=not any(issue.severity == "error" for issue in diagnostics),
        diagnostics=tuple(diagnostics),
        normalize_fallback_used=allow_fallback_paths,
        normalize_allow_list_used=any(
            issue.code == "full_ui_normalize_allow_list_used" for issue in diagnostics
        ),
    )


def _normalize_for_guard(
    stamped_original_ui: Mapping[str, Any],
    candidate_ui: Mapping[str, Any],
    *,
    timeout_ms: int,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    original = copy.deepcopy(dict(stamped_original_ui))
    candidate = copy.deepcopy(dict(candidate_ui))
    try:
        from vibecomfy.porting.agent_edit_normalize import is_normalize_available, normalize_ui_json

        preferred_available = is_normalize_available()
        started = time.monotonic()
        original_norm = normalize_ui_json(
            original,
            timeout_ms=timeout_ms,
            _lgraph_available=preferred_available,
        )
        candidate_norm = normalize_ui_json(
            candidate,
            timeout_ms=timeout_ms,
            _lgraph_available=preferred_available,
        )
        elapsed_ms = (time.monotonic() - started) * 1000
        fallback_used = not preferred_available or elapsed_ms > timeout_ms
        return original_norm, candidate_norm, fallback_used
    except Exception:
        return original, candidate, True


def _guard_attribution(
    original_ledger: EditLedger,
    candidate_ledger: EditLedger,
    resolved_ops: tuple[tuple[EditOp, ResolvedOp], ...],
) -> dict[str, set[Any]]:
    node_paths: dict[tuple[str, str], set[str]] = {}
    scope_field_paths: dict[str, set[str]] = {}
    removed_nodes: set[tuple[str, str]] = set()
    new_nodes: set[tuple[str, str]] = set()
    removed_links: set[tuple[str, int]] = set()
    new_links: set[tuple[str, int]] = set()
    touched_links: set[tuple[str, int]] = set()

    def allow_node_paths(scope_path: str, uid: str, *paths: str) -> None:
        node_paths.setdefault((scope_path, uid), set()).update(paths)

    def allow_scope_field_paths(scope_path: str, *paths: str) -> None:
        scope_field_paths.setdefault(scope_path, set()).update(paths)

    def allow_node_paths_by_id(scope_path: str, node_id: int | None, *paths: str) -> None:
        if node_id is None:
            return
        scope = original_ledger.scopes.get(scope_path)
        if scope is None:
            return
        node = _node_by_id(scope.graph, node_id)
        if not isinstance(node, Mapping):
            return
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            return
        uid = properties.get("vibecomfy_uid")
        if isinstance(uid, str) and uid:
            allow_node_paths(scope_path, uid, *paths)

    def allow_link_endpoint_paths(scope_path: str, link_id: int) -> None:
        link = original_ledger.resolve_link(scope_path, link_id)
        origin_id, _, target_id, _ = _link_endpoints(link)
        allow_node_paths_by_id(scope_path, origin_id, "outputs")
        allow_node_paths_by_id(scope_path, target_id, "inputs")

    def allow_candidate_link_endpoint_paths(scope_path: str, link_id: int) -> None:
        link = candidate_ledger.resolve_link(scope_path, link_id)
        origin_id, _, target_id, _ = _link_endpoints(link)
        allow_node_paths_by_id(scope_path, origin_id, "outputs")
        allow_node_paths_by_id(scope_path, target_id, "inputs")

    for op, resolved in resolved_ops:
        if isinstance(op, SetNodeFieldOp):
            assert isinstance(resolved, ResolvedFieldRef)
            if resolved.widget_key is not None:
                paths = [f"widgets_values.{resolved.widget_key}"]
            else:
                paths = [f"widgets_values[{resolved.widget_index}]"]
            if resolved.input_name is not None:
                paths.append("inputs")
            allow_node_paths(op.target.scope_path, op.target.uid, *paths)
            if resolved.automatic_link_removal is not None:
                removed_links.add((op.target.scope_path, resolved.automatic_link_removal))
                allow_link_endpoint_paths(op.target.scope_path, resolved.automatic_link_removal)
            continue
        if isinstance(op, SetModeOp):
            allow_node_paths(op.target.scope_path, op.target.uid, "mode")
            continue
        if isinstance(op, ReorderOp):
            allow_node_paths(op.target.scope_path, op.target.uid, "widgets_values")
            continue
        if isinstance(op, UpsertLinkOp):
            assert isinstance(resolved, tuple)
            source, target = resolved
            assert isinstance(source, ResolvedLinkEndpoint)
            assert isinstance(target, ResolvedLinkEndpoint)
            allow_node_paths(op.source.scope_path, op.source.uid, "outputs")
            allow_node_paths(op.target.scope_path, op.target.uid, "inputs")
            raw_input = _find_named_slot(target.node.get("inputs"), target.slot_name)
            if isinstance(raw_input, Mapping) and isinstance(raw_input.get("link"), int):
                new_link_id = raw_input["link"]
                new_links.add((op.target.scope_path, new_link_id))
                allow_candidate_link_endpoint_paths(op.target.scope_path, new_link_id)
            original_target = original_ledger.resolve_node(op.target.scope_path, op.target.uid)
            if isinstance(original_target, Mapping):
                original_input = _find_named_slot(original_target.get("inputs"), target.slot_name)
                if isinstance(original_input, Mapping) and isinstance(original_input.get("link"), int):
                    old_link_id = original_input["link"]
                    removed_links.add((op.target.scope_path, old_link_id))
                    allow_link_endpoint_paths(op.target.scope_path, old_link_id)
            continue
        if isinstance(op, RemoveLinkOp):
            assert isinstance(resolved, ResolvedRemoveLinkRef)
            removed_links.add((resolved.scope_path, resolved.link_id))
            allow_link_endpoint_paths(resolved.scope_path, resolved.link_id)
            continue
        if isinstance(op, RemoveNodeOp):
            assert isinstance(resolved, ResolvedRemoveNodePlan)
            removed_nodes.add((op.target.scope_path, op.target.uid))
            for link_id in resolved.link_ids_to_remove:
                removed_links.add((op.target.scope_path, link_id))
                allow_link_endpoint_paths(op.target.scope_path, link_id)
            for rewire in resolved.link_rewires:
                touched_links.add((rewire.scope_path, rewire.link_id))
                allow_link_endpoint_paths(rewire.scope_path, rewire.link_id)
                allow_node_paths_by_id(rewire.scope_path, rewire.new_origin_id, "outputs")
            continue
        if isinstance(op, AddNodeOp):
            assert isinstance(resolved, AppliedAddNodeSpec)
            new_nodes.add((resolved.scope_path, resolved.uid))
            if resolved.group_index is not None:
                allow_scope_field_paths(resolved.scope_path, f"groups[{resolved.group_index}].bounding")
            for source_uid in resolved.source_uids:
                allow_node_paths(resolved.scope_path, source_uid, "outputs")
            for link_id in resolved.link_ids:
                new_links.add((resolved.scope_path, link_id))
                allow_candidate_link_endpoint_paths(resolved.scope_path, link_id)

    return {
        "node_paths": node_paths,
        "scope_field_paths": scope_field_paths,
        "removed_nodes": removed_nodes,
        "new_nodes": new_nodes,
        "removed_links": removed_links,
        "new_links": new_links,
        "touched_links": touched_links,
    }


def _align_candidate_scope_paths(original_ledger: EditLedger, candidate_ledger: EditLedger) -> None:
    original_by_tokens = {
        scope.path_tokens: scope_path
        for scope_path, scope in original_ledger.scopes.items()
    }
    candidate_path_map: dict[str, str] = {}
    for candidate_path, candidate_scope in candidate_ledger.scopes.items():
        candidate_path_map[candidate_path] = original_by_tokens.get(candidate_scope.path_tokens, candidate_path)

    if all(candidate_path == aligned_path for candidate_path, aligned_path in candidate_path_map.items()):
        return

    scopes: dict[str, ScopeState] = {}
    for candidate_path, candidate_scope in candidate_ledger.scopes.items():
        aligned_path = candidate_path_map[candidate_path]
        candidate_scope.scope_path = aligned_path
        scopes[aligned_path] = candidate_scope
    candidate_ledger.scopes = scopes

    candidate_ledger.node_index = {
        (candidate_path_map.get(scope_path, scope_path), uid): node
        for (scope_path, uid), node in candidate_ledger.node_index.items()
    }
    candidate_ledger.link_index = {
        (candidate_path_map.get(scope_path, scope_path), link_id): link
        for (scope_path, link_id), link in candidate_ledger.link_index.items()
    }


def _guard_scope_fields(
    scope_path: str,
    original_scope: Mapping[str, Any],
    candidate_scope: Mapping[str, Any],
    *,
    allowed_paths: set[str],
) -> list[PortIssue]:
    diagnostics: list[PortIssue] = []
    ignored = {"nodes", "links", "definitions"}
    keys = (set(original_scope) | set(candidate_scope)) - ignored
    for key in sorted(keys):
        if key == "last_node_id":
            diagnostics.extend(_guard_counter(scope_path, key, original_scope.get(key), candidate_scope.get(key)))
            continue
        if key == "last_link_id":
            diagnostics.extend(_guard_counter(scope_path, key, original_scope.get(key), candidate_scope.get(key)))
            continue
        if key == "state":
            diagnostics.extend(_guard_subgraph_state(scope_path, original_scope.get(key), candidate_scope.get(key)))
            continue
        if key == "groups":
            diffs = _value_diff_paths(original_scope.get(key), candidate_scope.get(key), "groups")
            if diffs and _all_diffs_op_allowed(diffs, allowed_paths):
                continue
        if original_scope.get(key) != candidate_scope.get(key):
            diagnostics.append(
                _issue(
                    "full_ui_scope_field_changed_unattributed",
                    "Candidate changed a scope-level UI field without an attributed operation.",
                    detail={"scope_path": scope_path, "field": key},
                )
            )
    return diagnostics


def _guard_scope_links(
    scope_path: str,
    original_scope: Mapping[str, Any],
    candidate_scope: Mapping[str, Any],
    *,
    removed_links: set[tuple[str, int]],
    new_links: set[tuple[str, int]],
    touched_links: set[tuple[str, int]],
) -> list[PortIssue]:
    diagnostics: list[PortIssue] = []
    original_links = _links_by_id(original_scope.get("links"))
    candidate_links = _links_by_id(candidate_scope.get("links"))
    for link_id, original_link in original_links.items():
        key = (scope_path, link_id)
        if link_id not in candidate_links:
            if key in removed_links:
                continue
            diagnostics.append(
                _issue(
                    "full_ui_link_removed_unattributed",
                    "Candidate removed a link without an attributed operation.",
                    detail={"scope_path": scope_path, "link_id": link_id},
                )
            )
            continue
        if candidate_links[link_id] == original_link:
            continue
        if key in touched_links:
            continue
        diagnostics.append(
            _issue(
                "full_ui_link_changed_unattributed",
                "Candidate changed a link without an attributed operation.",
                detail={"scope_path": scope_path, "link_id": link_id},
            )
        )
    for link_id in candidate_links:
        key = (scope_path, link_id)
        if link_id in original_links:
            continue
        if key in new_links:
            continue
        diagnostics.append(
            _issue(
                "full_ui_link_added_unattributed",
                "Candidate added a link without an attributed operation.",
                detail={"scope_path": scope_path, "link_id": link_id},
            )
        )
    return diagnostics


def _links_by_id(links: Any) -> dict[int, Any]:
    if not isinstance(links, list):
        return {}
    result: dict[int, Any] = {}
    for link in links:
        link_id = _link_id(link)
        if link_id is not None:
            result[link_id] = link
    return result


def _guard_counter(scope_path: str, field: str, original: Any, candidate: Any) -> list[PortIssue]:
    if original == candidate:
        return []
    if _counter_advanced_or_materialized(original, candidate):
        return []
    return [
        _issue(
            "full_ui_counter_changed_unattributed",
            "Candidate changed a LiteGraph id counter except for monotonic advancement.",
            detail={"scope_path": scope_path, "field": field, "original": original, "candidate": candidate},
        )
    ]


def _guard_subgraph_state(scope_path: str, original: Any, candidate: Any) -> list[PortIssue]:
    if original == candidate:
        return []
    original_state = original if isinstance(original, Mapping) else {}
    candidate_state = candidate if isinstance(candidate, Mapping) else {}
    diagnostics: list[PortIssue] = []
    keys = set(original_state) | set(candidate_state)
    for key in sorted(keys):
        if key in {"lastNodeId", "lastLinkId"}:
            diagnostics.extend(_guard_counter(scope_path, f"state.{key}", original_state.get(key), candidate_state.get(key)))
            continue
        if original_state.get(key) != candidate_state.get(key):
            diagnostics.append(
                _issue(
                    "full_ui_scope_field_changed_unattributed",
                    "Candidate changed a subgraph state field without an attributed operation.",
                    detail={"scope_path": scope_path, "field": f"state.{key}"},
                )
            )
    return diagnostics


def _counter_advanced_or_materialized(original: Any, candidate: Any) -> bool:
    if isinstance(candidate, int) and original is None:
        return True
    if isinstance(original, int) and isinstance(candidate, int) and candidate >= original:
        return True
    return False


def _guard_node_order(
    scope_path: str,
    original_scope: Mapping[str, Any],
    candidate_scope: Mapping[str, Any],
    *,
    removed_nodes: set[tuple[str, str]],
    new_nodes: set[tuple[str, str]],
) -> list[PortIssue]:
    original_order = [
        uid
        for uid in _scope_node_uids(original_scope)
        if (scope_path, uid) not in removed_nodes
    ]
    candidate_order = [
        uid
        for uid in _scope_node_uids(candidate_scope)
        if (scope_path, uid) not in new_nodes
    ]
    if original_order == candidate_order:
        return []
    return [
        _issue(
            "full_ui_node_order_changed_unattributed",
            "Candidate changed the relative order of existing nodes without an attributed operation.",
            detail={"scope_path": scope_path, "original": original_order, "candidate": candidate_order},
        )
    ]


def _scope_node_uids(scope_graph: Mapping[str, Any]) -> list[str]:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return []
    result: list[str] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        properties = node.get("properties")
        if not isinstance(properties, Mapping):
            continue
        uid = properties.get("vibecomfy_uid")
        if isinstance(uid, str) and uid:
            result.append(uid)
    return result


def _value_diff_paths(original: Any, candidate: Any, prefix: str = "") -> list[str]:
    if original == candidate:
        return []
    if isinstance(original, Mapping) and isinstance(candidate, Mapping):
        paths: list[str] = []
        for key in sorted(set(original) | set(candidate)):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_value_diff_paths(original.get(key), candidate.get(key), child_prefix))
        return paths
    if isinstance(original, list) and isinstance(candidate, list):
        paths = []
        max_len = max(len(original), len(candidate))
        for index in range(max_len):
            child_prefix = f"{prefix}[{index}]"
            left = original[index] if index < len(original) else None
            right = candidate[index] if index < len(candidate) else None
            paths.extend(_value_diff_paths(left, right, child_prefix))
        return paths
    return [prefix or "<root>"]


def _all_diffs_normalize_allowed(
    original_node: Mapping[str, Any],
    candidate_node: Mapping[str, Any],
    diffs: list[str],
) -> bool:
    node_class = str(original_node.get("type") or original_node.get("class_type") or "")
    candidate_class = str(candidate_node.get("type") or candidate_node.get("class_type") or "")
    if not node_class or node_class != candidate_class:
        return False
    try:
        from vibecomfy.porting.agent_edit_normalize import normalize_allow_list_matches
    except Exception:
        return False
    return all(normalize_allow_list_matches(node_class, field_path) is not None for field_path in diffs)


def _all_diffs_op_allowed(diffs: list[str], allowed_paths: set[str]) -> bool:
    if not allowed_paths:
        return False
    return all(any(_path_is_at_or_below(diff, allowed) for allowed in allowed_paths) for diff in diffs)


def _path_is_at_or_below(path: str, allowed: str) -> bool:
    return path == allowed or path.startswith(f"{allowed}.") or path.startswith(f"{allowed}[")


def _resolve_op(
    ledger: EditLedger,
    op: EditOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if isinstance(op, SetNodeFieldOp):
        return _resolve_set_node_field(ledger, op, schema_provider=schema_provider)
    if isinstance(op, SetModeOp):
        return _resolve_node_only(ledger, op.target)
    if isinstance(op, RemoveNodeOp):
        return _resolve_remove_node(ledger, op.target)
    if isinstance(op, UpsertLinkOp):
        return _resolve_upsert_link(ledger, op, schema_provider=schema_provider)
    if isinstance(op, RemoveLinkOp):
        return _resolve_remove_link(ledger, op)
    if isinstance(op, AddNodeOp):
        return _resolve_add_node(ledger, op, schema_provider=schema_provider)
    if isinstance(op, ReorderOp):
        return _resolve_reorder(ledger, op)
    return None, [_issue("unsupported_edit_op", f"Unsupported edit op {type(op).__name__}.")]


def _resolve_scope(ledger: EditLedger, scope_path: str) -> tuple[ScopeState | None, list[PortIssue]]:
    scope = ledger.scopes.get(scope_path)
    if scope is None:
        return None, [
            _issue(
                "unknown_scope_path",
                f"Unknown scope_path {scope_path!r}.",
                detail={"scope_path": scope_path},
            )
        ]
    return scope, []


def _resolve_node(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedNodeRef | None, list[PortIssue]]:
    scope, issues = _resolve_scope(ledger, target.scope_path)
    if issues:
        return None, issues
    assert scope is not None
    node = ledger.resolve_node(target.scope_path, target.uid)
    if node is None:
        return None, [
            _issue(
                "unknown_node_target",
                f"Unknown node target {target.uid!r} in scope {target.scope_path!r}.",
                detail={"scope_path": target.scope_path, "uid": target.uid},
            )
        ]
    class_type = str(node.get("type") or node.get("class_type") or "")
    return (
        ResolvedNodeRef(
            target=target,
            node=node,
            class_type=class_type,
            node_id=node.get("id"),
        ),
        [],
    )


def _resolve_node_only(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    resolved, issues = _resolve_node(ledger, target)
    return resolved, issues


def _resolve_remove_node(
    ledger: EditLedger,
    target: NodeTarget,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    node_ref, issues = _resolve_node(ledger, target)
    if issues:
        return None, issues
    assert node_ref is not None
    node_id = node_ref.node_id if isinstance(node_ref.node_id, int) else None
    if node_id is None:
        return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=()), []

    scope = ledger.scopes[target.scope_path]
    inbound_links = _collect_links_for_target(scope.graph, node_id)
    outbound_links = _collect_links_for_origin(scope.graph, node_id)
    connected_link_ids = tuple(
        sorted(
            {
                link_id
                for link in [*inbound_links, *outbound_links]
                if (link_id := _link_id(link)) is not None
            }
        )
    )

    if node_ref.class_type == "Reroute":
        source, helper_issues = _resolve_passthrough_source(scope.graph, node_id, target.scope_path)
        if helper_issues:
            return None, helper_issues
        if source is None:
            return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []
        rewires = _build_rewires(
            target.scope_path,
            outbound_links,
            old_origin_id=node_id,
            new_origin_id=source[0],
            new_origin_slot=source[1],
        )
        return ResolvedRemoveNodePlan(
            node_ref=node_ref,
            link_ids_to_remove=_link_ids(inbound_links),
            link_rewires=rewires,
        ), []

    if node_ref.class_type == "GetNode":
        source, helper_issues = _resolve_getnode_source(scope.graph, node_ref.node, target.scope_path)
        if helper_issues:
            return None, helper_issues
        if source is None:
            return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []
        rewires = _build_rewires(
            target.scope_path,
            outbound_links,
            old_origin_id=node_id,
            new_origin_id=source[0],
            new_origin_slot=source[1],
        )
        return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=(), link_rewires=rewires), []

    if node_ref.class_type == "SetNode":
        source, helper_issues = _resolve_passthrough_source(scope.graph, node_id, target.scope_path)
        if helper_issues:
            return None, helper_issues
        if source is None:
            return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []
        rewires = _build_rewires_for_setnode_gets(scope.graph, node_ref.node, target.scope_path, source)
        return ResolvedRemoveNodePlan(
            node_ref=node_ref,
            link_ids_to_remove=_link_ids(inbound_links),
            link_rewires=rewires,
        ), []

    return ResolvedRemoveNodePlan(node_ref=node_ref, link_ids_to_remove=connected_link_ids), []


def _resolve_set_node_field(
    ledger: EditLedger,
    op: SetNodeFieldOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    resolved_node, issues = _resolve_node(ledger, NodeTarget(op.target.scope_path, op.target.uid))
    if issues:
        return None, issues
    assert resolved_node is not None
    if op.target.field_path == "mode":
        return None, [
            _issue(
                "set_mode_requires_set_mode_op",
                "Node mode must be edited with set_mode, not set_node_field.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid},
            )
        ]

    node = resolved_node.node
    class_type = resolved_node.class_type
    input_name = None
    widget_index = None
    automatic_link_removal = None

    schema = schema_for(schema_provider, class_type)
    schema_inputs = getattr(schema, "inputs", {}) or {}
    schema_input = schema_inputs.get(op.target.field_path)

    raw_input = _find_named_slot(node.get("inputs"), op.target.field_path)
    raw_input_index = _find_named_slot_index(node.get("inputs"), op.target.field_path)
    widgets_values = node.get("widgets_values")
    widget_key = op.target.field_path if isinstance(widgets_values, Mapping) and op.target.field_path in widgets_values else None
    if raw_input is not None:
        input_name = op.target.field_path
        if isinstance(raw_input.get("link"), int):
            automatic_link_removal = raw_input["link"]

    widget_index = _widget_index_for_field(class_type, op.target.field_path)
    widget_stub_name = _widget_name_for_input(raw_input)
    used_schema_less_widget_recovery = False
    if widget_index is None and widget_stub_name == op.target.field_path:
        widget_index = _widget_index_from_input_stubs(node.get("inputs"), op.target.field_path)
        used_schema_less_widget_recovery = widget_index is not None

    if input_name is None and widget_index is None and widget_key is None and schema_input is None:
        return None, [
            _issue(
                "unknown_node_field",
                f"{class_type} does not expose field {op.target.field_path!r}.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "class_type": class_type,
                },
            )
        ]
    if widget_index is None and widget_key is None:
        return None, [
            _issue(
                "non_widget_field_not_editable",
                f"{class_type}.{op.target.field_path} is not editable through set_node_field because it has no widget-backed literal surface.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "class_type": class_type,
                },
            )
        ]

    value_issues = _validate_literal_value(
        value=op.value,
        spec=schema_input,
        class_type=class_type,
        input_name=op.target.field_path,
        context="set_node_field",
    )
    if value_issues:
        return None, value_issues

    issues = []
    if used_schema_less_widget_recovery:
        issues.append(
            _issue(
                "schema_less_linked_widget_recovery",
                "Recovered widget position from linked input stubs because schema/object_info widget order was unavailable.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "class_type": class_type,
                    "widget_index": widget_index,
                },
            )
        )
    if automatic_link_removal is not None:
        issues.append(
            _issue(
                "automatic_link_removal",
                "set_node_field will remove the overriding input link before applying the widget value.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "field_path": op.target.field_path,
                    "link_id": automatic_link_removal,
                },
            )
        )
    return (
        ResolvedFieldRef(
            target=op.target,
            node=node,
            class_type=class_type,
            node_id=node.get("id"),
            input_name=input_name,
            input_slot_index=raw_input_index,
            widget_index=widget_index,
            widget_key=widget_key,
            schema_input=schema_input,
            automatic_link_removal=automatic_link_removal,
        ),
        issues,
    )


def _resolve_upsert_link(
    ledger: EditLedger,
    op: UpsertLinkOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.source.scope_path != op.target.scope_path:
        return None, [
            _issue(
                "cross_scope_link_unsupported",
                "Link endpoints must resolve within the same scope.",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "to_scope_path": op.target.scope_path,
                },
            )
        ]
    source, source_issues = _resolve_source_endpoint(ledger, op.source, schema_provider=schema_provider)
    if source_issues:
        return None, source_issues
    target, target_issues = _resolve_target_endpoint(ledger, op.target, schema_provider=schema_provider)
    if target_issues:
        return None, target_issues
    assert source is not None and target is not None
    if not isinstance(source.node_id, int) or not isinstance(target.node_id, int):
        return None, [
            _issue(
                "non_numeric_link_endpoint",
                "Link endpoints must have numeric LiteGraph node ids.",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "from_uid": op.source.uid,
                    "from_node_id": source.node_id,
                    "to_scope_path": op.target.scope_path,
                    "to_uid": op.target.uid,
                    "to_node_id": target.node_id,
                },
            )
        ]
    if source.socket_type and target.socket_type and not socket_types_compatible(source.socket_type, target.socket_type):
        return None, [
            _issue(
                "incompatible_socket_types",
                f"Cannot connect {source.class_type}.{source.slot_name} ({source.socket_type}) to "
                f"{target.class_type}.{target.slot_name} ({target.socket_type}).",
                detail={
                    "from_scope_path": op.source.scope_path,
                    "from_uid": op.source.uid,
                    "from_slot": source.slot_name,
                    "from_type": source.socket_type,
                    "to_scope_path": op.target.scope_path,
                    "to_uid": op.target.uid,
                    "to_input": target.slot_name,
                    "to_type": target.socket_type,
                },
            )
        ]
    return (source, target), []


def _resolve_remove_link(
    ledger: EditLedger,
    op: RemoveLinkOp,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.link_id is not None:
        matches = [
            ResolvedRemoveLinkRef(scope_path=scope_path, link_id=link_id, link=link)
            for (scope_path, link_id), link in ledger.link_index.items()
            if link_id == op.link_id
        ]
        if not matches:
            return None, [
                _issue(
                    "unknown_link_id",
                    f"Unknown link id {op.link_id}.",
                    detail={"link_id": op.link_id},
                )
            ]
        if len(matches) > 1:
            return None, [
                _issue(
                    "ambiguous_link_id",
                    f"Link id {op.link_id} exists in multiple scopes.",
                    detail={"link_id": op.link_id, "scope_paths": [item.scope_path for item in matches]},
                )
            ]
        return matches[0], []

    assert op.target is not None
    node_ref, issues = _resolve_node(ledger, NodeTarget(op.target.scope_path, op.target.uid))
    if issues:
        return None, issues
    assert node_ref is not None
    raw_input = _find_named_slot(node_ref.node.get("inputs"), op.target.input_field)
    if raw_input is None:
        return None, [
            _issue(
                "unknown_link_target_input",
                f"{node_ref.class_type} does not expose input {op.target.input_field!r}.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "input": op.target.input_field,
                },
            )
        ]
    link_id = raw_input.get("link")
    if not isinstance(link_id, int):
        return None, [
            _issue(
                "missing_link_to_remove",
                f"{node_ref.class_type}.{op.target.input_field} has no incoming link to remove.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "input": op.target.input_field,
                },
            )
        ]
    link = ledger.resolve_link(op.target.scope_path, link_id)
    if link is None:
        return None, [
            _issue(
                "dangling_link_reference",
                f"Input {op.target.input_field!r} references missing link id {link_id}.",
                detail={"scope_path": op.target.scope_path, "link_id": link_id},
            )
        ]
    return ResolvedRemoveLinkRef(scope_path=op.target.scope_path, link_id=link_id, link=link), []


def _resolve_add_node(
    ledger: EditLedger,
    op: AddNodeOp,
    *,
    schema_provider: Any,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    scope, issues = _resolve_scope(ledger, op.scope_path)
    if issues:
        return None, issues
    assert scope is not None

    schema = schema_for(schema_provider, op.class_type)
    if schema is None:
        return None, [
            _issue(
                "unknown_add_node_class_type",
                f"Unknown class_type {op.class_type!r} for add_node.",
                detail={"scope_path": op.scope_path, "class_type": op.class_type},
            )
        ]

    schema_inputs = getattr(schema, "inputs", {}) or {}
    issues = []
    for input_name, spec in schema_inputs.items():
        required = bool(getattr(spec, "required", False))
        default = getattr(spec, "default", None)
        if required and input_name not in op.fields and input_name not in op.inputs and default is None:
            issues.append(
                _issue(
                    "missing_required_add_node_input",
                    f"{op.class_type} requires input {input_name!r} for add_node.",
                    # Per the v2 spec, required-input completeness is a queue-validate
                    # WARNING, not a fidelity failure: adding a node and wiring it in a
                    # later step (or after manual review) is a legitimate flow. Surfacing
                    # this as a hard error blocked the natural "add a node, then connect
                    # it" pattern. The node is still added; queue-validate flags the gap.
                    severity="warning",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "input": input_name},
                )
            )
    for field_name, value in op.fields.items():
        spec = schema_inputs.get(field_name)
        if spec is None:
            issues.append(
                _issue(
                    "unknown_add_node_field",
                    f"{op.class_type} does not declare field {field_name!r}.",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "field": field_name},
                )
            )
            continue
        issues.extend(
            _validate_literal_value(
                value=value,
                spec=spec,
                class_type=op.class_type,
                input_name=field_name,
                context="add_node",
            )
        )
    # Block only on errors; carry warnings (e.g. missing required input) forward so the
    # node is still added and the gap surfaces as a non-blocking queue-validate warning.
    if any(issue.severity == "error" for issue in issues):
        return None, issues

    resolved_inputs: dict[str, ResolvedLinkEndpoint] = {}
    for input_name, source in op.inputs.items():
        if source.scope_path != op.scope_path:
            return None, [
                _issue(
                    "cross_scope_link_unsupported",
                    "add_node input endpoints must resolve within the same scope.",
                    detail={
                        "from_scope_path": source.scope_path,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                    },
                )
            ]
        spec = schema_inputs.get(input_name)
        if spec is None:
            return None, [
                _issue(
                    "unknown_add_node_input",
                    f"{op.class_type} does not declare input {input_name!r}.",
                    detail={"scope_path": op.scope_path, "class_type": op.class_type, "input": input_name},
                )
            ]
        source_ref, source_issues = _resolve_source_endpoint(ledger, source, schema_provider=schema_provider)
        if source_issues:
            return None, source_issues
        assert source_ref is not None
        if not isinstance(source_ref.node_id, int):
            return None, [
                _issue(
                    "non_numeric_link_endpoint",
                    "add_node input sources must have numeric LiteGraph node ids.",
                    detail={
                        "from_scope_path": source.scope_path,
                        "from_uid": source.uid,
                        "from_node_id": source_ref.node_id,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                    },
                )
            ]
        target_type = _normalize_type(getattr(spec, "type", None))
        if source_ref.socket_type and target_type and not socket_types_compatible(source_ref.socket_type, target_type):
            return None, [
                _issue(
                    "incompatible_socket_types",
                    f"Cannot connect {source_ref.class_type}.{source_ref.slot_name} ({source_ref.socket_type}) to "
                    f"{op.class_type}.{input_name} ({target_type}).",
                    detail={
                        "from_scope_path": source.scope_path,
                        "from_uid": source.uid,
                        "from_slot": source_ref.slot_name,
                        "from_type": source_ref.socket_type,
                        "to_scope_path": op.scope_path,
                        "to_class_type": op.class_type,
                        "to_input": input_name,
                        "to_type": target_type,
                    },
                )
            ]
        resolved_inputs[input_name] = source_ref

    anchor_near = None
    anchor_between = None
    anchor_group_index = None
    anchor_group_title = None
    if op.anchor is not None:
        anchor_issues: list[PortIssue] = []
        anchor_near, anchor_between, anchor_group_index, anchor_group_title, anchor_issues = _resolve_add_node_anchor(
            ledger,
            op.scope_path,
            op.anchor,
        )
        if anchor_issues:
            return None, anchor_issues

    return (
        ResolvedAddNodeSpec(
            op=op,
            scope=scope,
            schema=schema,
            schema_inputs=schema_inputs,
            resolved_inputs=resolved_inputs,
            anchor_near=anchor_near,
            anchor_between=anchor_between,
            anchor_group_index=anchor_group_index,
            anchor_group_title=anchor_group_title,
        ),
        list(issues),
    )


def _resolve_reorder(
    ledger: EditLedger,
    op: ReorderOp,
) -> tuple[ResolvedOp | None, list[PortIssue]]:
    if op.axis != "widgets":
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder supports only cosmetic unlinked widget value permutations; structural slot reorder is rejected.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    node_ref, issues = _resolve_node(ledger, op.target)
    if issues:
        return None, issues
    assert node_ref is not None
    raw = node_ref.node.get("widgets_values")
    if not isinstance(raw, list):
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no reorderable widget surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    names = _reorder_names(node_ref.node, node_ref.class_type, op.axis)
    if names is None:
        return None, [
            _issue(
                "unsupported_reorder_axis",
                f"{node_ref.class_type} has no named reorderable {op.axis} surface.",
                detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "axis": op.axis},
            )
        ]
    if tuple(op.order) == tuple(names):
        return node_ref, []
    if len(op.order) != len(names) or set(op.order) != set(names):
        return None, [
            _issue(
                "unsupported_reorder_form",
                "reorder must be a complete permutation of the existing named widget or output slots.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "expected": list(names),
                    "actual": list(op.order),
                },
            )
        ]
    linked_widgets = _linked_widget_names(node_ref.node.get("inputs"))
    linked_ordered_widgets = [name for name in op.order if name in linked_widgets]
    if linked_ordered_widgets:
        return None, [
            _issue(
                "unsupported_reorder_form",
                "Phase 1 reorder only supports unlinked widget values; linked widget inputs must be edited with link ops first.",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "axis": op.axis,
                    "linked_widgets": linked_ordered_widgets,
                },
            )
        ]
    return node_ref, []


def _resolve_add_node_anchor(
    ledger: EditLedger,
    scope_path: str,
    anchor: AnchorRef,
) -> tuple[
    ResolvedNodeRef | None,
    tuple[ResolvedNodeRef, ResolvedNodeRef] | None,
    int | None,
    str | None,
    list[PortIssue],
]:
    if anchor.group_title is not None:
        group_index = _group_index_by_title(ledger.scopes[scope_path].graph, anchor.group_title)
        if group_index is None:
            return None, None, None, None, [
                _issue(
                    "unknown_group_anchor",
                    f"Unknown group title {anchor.group_title!r} for add_node anchor.",
                    detail={"scope_path": scope_path, "group_title": anchor.group_title},
                )
            ]
    else:
        group_index = None

    near_ref = None
    if anchor.near is not None:
        if anchor.near.scope_path != scope_path:
            return None, None, None, None, [
                _issue(
                    "cross_scope_anchor_unsupported",
                    "add_node anchors must reference nodes in the same scope.",
                    detail={"scope_path": scope_path, "anchor_scope_path": anchor.near.scope_path},
                )
            ]
        near_ref, issues = _resolve_node(ledger, anchor.near)
        if issues:
            return None, None, None, None, issues

    between_ref = None
    if anchor.between is not None:
        resolved: list[ResolvedNodeRef] = []
        for target in anchor.between:
            if target.scope_path != scope_path:
                return None, None, None, None, [
                    _issue(
                        "cross_scope_anchor_unsupported",
                        "add_node anchors must reference nodes in the same scope.",
                        detail={"scope_path": scope_path, "anchor_scope_path": target.scope_path},
                    )
                ]
            node_ref, issues = _resolve_node(ledger, target)
            if issues:
                return None, None, None, None, issues
            assert node_ref is not None
            resolved.append(node_ref)
        between_ref = (resolved[0], resolved[1])

    return near_ref, between_ref, group_index, anchor.group_title, []


def _resolve_source_endpoint(
    ledger: EditLedger,
    ref: LinkSourceRef,
    *,
    schema_provider: Any,
) -> tuple[ResolvedLinkEndpoint | None, list[PortIssue]]:
    node_ref, issues = _resolve_node(ledger, NodeTarget(ref.scope_path, ref.uid))
    if issues:
        return None, issues
    assert node_ref is not None
    outputs = node_ref.node.get("outputs")
    if not isinstance(outputs, list):
        return None, [
            _issue(
                "missing_source_outputs",
                f"{node_ref.class_type} has no outputs to link from.",
                detail={"scope_path": ref.scope_path, "uid": ref.uid},
            )
        ]
    slot_index = None
    slot_name = None
    socket_type = None
    if isinstance(ref.output_slot, int):
        if ref.output_slot < 0 or ref.output_slot >= len(outputs):
            return None, [
                _issue(
                    "unknown_output_slot",
                    f"{node_ref.class_type} has no output slot {ref.output_slot}.",
                    detail={"scope_path": ref.scope_path, "uid": ref.uid, "output_slot": ref.output_slot},
                )
            ]
        slot_index = ref.output_slot
        output_entry = outputs[slot_index]
        if isinstance(output_entry, Mapping):
            slot_name = str(output_entry.get("name") or slot_index)
            socket_type = _normalize_type(output_entry.get("type"))
    else:
        for index, output_entry in enumerate(outputs):
            if isinstance(output_entry, Mapping) and output_entry.get("name") == ref.output_slot:
                slot_index = index
                slot_name = str(ref.output_slot)
                socket_type = _normalize_type(output_entry.get("type"))
                break
        if slot_index is None:
            schema = schema_for(schema_provider, node_ref.class_type)
            output_specs = getattr(schema, "outputs", None) or []
            for index, output_spec in enumerate(output_specs):
                if getattr(output_spec, "name", None) == ref.output_slot:
                    slot_index = index
                    slot_name = str(ref.output_slot)
                    socket_type = _normalize_type(getattr(output_spec, "type", None))
                    break
        if slot_index is None:
            return None, [
                _issue(
                    "unknown_output_slot",
                    f"{node_ref.class_type} has no output named {ref.output_slot!r}.",
                    detail={"scope_path": ref.scope_path, "uid": ref.uid, "output_slot": ref.output_slot},
                )
            ]
    if slot_name is None:
        slot_name = str(ref.output_slot)
    if socket_type is None:
        socket_type = _schema_output_type(schema_provider, node_ref.class_type, slot_index, slot_name)
    return (
        ResolvedLinkEndpoint(
            ref=ref,
            node=node_ref.node,
            class_type=node_ref.class_type,
            node_id=node_ref.node_id,
            slot_index=slot_index,
            slot_name=slot_name,
            socket_type=socket_type,
        ),
        [],
    )


def _resolve_target_endpoint(
    ledger: EditLedger,
    ref: LinkTargetRef,
    *,
    schema_provider: Any,
) -> tuple[ResolvedLinkEndpoint | None, list[PortIssue]]:
    node_ref, issues = _resolve_node(ledger, NodeTarget(ref.scope_path, ref.uid))
    if issues:
        return None, issues
    assert node_ref is not None
    raw_input = _find_named_slot(node_ref.node.get("inputs"), ref.input_field)
    schema = schema_for(schema_provider, node_ref.class_type)
    schema_input = (getattr(schema, "inputs", {}) or {}).get(ref.input_field) if schema is not None else None
    if raw_input is None and schema_input is None:
        return None, [
            _issue(
                "unknown_target_input",
                f"{node_ref.class_type} has no input named {ref.input_field!r}.",
                detail={"scope_path": ref.scope_path, "uid": ref.uid, "input": ref.input_field},
            )
        ]
    slot_index = None
    socket_type = None
    if raw_input is not None:
        inputs = node_ref.node.get("inputs")
        if isinstance(inputs, list):
            slot_index = inputs.index(raw_input)
        socket_type = _normalize_type(raw_input.get("type"))
    if socket_type is None and schema_input is not None:
        socket_type = _normalize_type(getattr(schema_input, "type", None))
    return (
        ResolvedLinkEndpoint(
            ref=ref,
            node=node_ref.node,
            class_type=node_ref.class_type,
            node_id=node_ref.node_id,
            slot_index=slot_index,
            slot_name=ref.input_field,
            socket_type=socket_type,
        ),
        [],
    )


def _find_named_slot(slots: Any, name: str) -> dict[str, Any] | None:
    if not isinstance(slots, list):
        return None
    for item in slots:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None


def _find_named_slot_index(slots: Any, name: str) -> int | None:
    if not isinstance(slots, list):
        return None
    for index, item in enumerate(slots):
        if isinstance(item, dict) and item.get("name") == name:
            return index
    return None


def _widget_name_for_input(slot: Any) -> str | None:
    if not isinstance(slot, Mapping):
        return None
    widget = slot.get("widget")
    if not isinstance(widget, Mapping):
        return None
    name = widget.get("name")
    return str(name) if isinstance(name, str) and name else None


def _widget_index_for_field(class_type: str, field_name: str) -> int | None:
    widget_names = effective_widget_names_for_class(class_type, allow_object_info_fallback=True)
    for index, name in enumerate(widget_names):
        if name == field_name:
            return index
    return None


def _widget_index_from_input_stubs(inputs: Any, field_name: str) -> int | None:
    if not isinstance(inputs, list):
        return None
    widget_index = 0
    for slot in inputs:
        widget_name = _widget_name_for_input(slot)
        if widget_name is None:
            continue
        if widget_name == field_name:
            return widget_index
        widget_index += 1
    return None


_NODE_H_GAP = 80.0
_NODE_V_GAP = 36.0
_GROUP_PAD = 24.0
_COLLISION_NUDGE_X = 24.0
_COLLISION_NUDGE_Y = 32.0
_MAX_COLLISION_NUDGES = 64


def _place_add_node(
    ledger: EditLedger,
    spec: ResolvedAddNodeSpec,
    size: tuple[float, float],
) -> tuple[list[float], int | None, bool, list[PortIssue]]:
    scope_graph = spec.scope.graph
    desired_x, desired_y = _default_add_node_position(scope_graph, size)
    target_group_index, group_issues = _target_group_index(scope_graph, spec, size)
    if spec.op.anchor is not None:
        desired_x, desired_y = _anchor_position(scope_graph, spec.op.anchor, spec, size, (desired_x, desired_y))
    elif spec.resolved_inputs:
        primary = next(iter(sorted(spec.resolved_inputs.items())))[1]
        desired_x, desired_y = _right_of_rect(_node_rect(primary.node), size)
    if target_group_index is not None:
        desired_x, desired_y = _clamp_position_to_group(scope_graph, target_group_index, desired_x, desired_y, size)
    pos = _nudge_to_open_slot(scope_graph, [desired_x, desired_y], size, within_group=target_group_index)
    grew_group = False
    if target_group_index is not None:
        grew_group = _grow_group_to_fit(scope_graph, target_group_index, pos, size)
    return pos, target_group_index, grew_group, group_issues


def _anchor_position(
    scope_graph: Mapping[str, Any],
    anchor: AnchorRef,
    spec: ResolvedAddNodeSpec,
    size: tuple[float, float],
    fallback: tuple[float, float],
) -> tuple[float, float]:
    if anchor.relation == "between" and spec.anchor_between is not None:
        return _between_rects(_node_rect(spec.anchor_between[0].node), _node_rect(spec.anchor_between[1].node), size)
    if spec.anchor_near is not None:
        rect = _node_rect(spec.anchor_near.node)
        if anchor.relation == "below":
            return rect[0], rect[1] + rect[3] + _NODE_V_GAP
        if anchor.relation == "right_of":
            return _right_of_rect(rect, size)
        return _right_of_rect(rect, size)
    if anchor.group_title is not None:
        group_index = _group_index_by_title(scope_graph, anchor.group_title)
        if group_index is not None:
            group = _group_bounding(scope_graph, group_index)
            if group is not None:
                return group[0] + _GROUP_PAD, group[1] + _GROUP_PAD
    return fallback


def _target_group_index(
    scope_graph: Mapping[str, Any],
    spec: ResolvedAddNodeSpec,
    size: tuple[float, float],
) -> tuple[int | None, list[PortIssue]]:
    if spec.anchor_group_index is not None:
        return spec.anchor_group_index, []
    if spec.anchor_near is not None:
        return _group_index_for_node(scope_graph, spec.anchor_near.node), []
    if spec.anchor_between is not None:
        downstream_ref = spec.anchor_between[1]
        upstream_ref = spec.anchor_between[0]
        downstream = _group_index_for_node(scope_graph, downstream_ref.node)
        upstream = _group_index_for_node(scope_graph, upstream_ref.node)
        if downstream is not None:
            return downstream, []
        if upstream is not None:
            return upstream, []
        # Neither has a group — leave ungrouped with a diagnostic
        downstream_uid = str(downstream_ref.node.get("properties", {}).get("vibecomfy_uid", downstream_ref.node.get("id", "?")))
        upstream_uid = str(upstream_ref.node.get("properties", {}).get("vibecomfy_uid", upstream_ref.node.get("id", "?")))
        return None, [
            _issue(
                "splice_anchor_no_group",
                f"Splice-placed node of type '{spec.op.class_type}': neither downstream "
                f"'{downstream_uid}' nor upstream '{upstream_uid}' belongs to a group; "
                f"leaving ungrouped.",
                severity="info",
                detail={
                    "class_type": spec.op.class_type,
                    "downstream_uid": downstream_uid,
                    "upstream_uid": upstream_uid,
                },
            )
        ]
    if spec.resolved_inputs:
        primary = next(iter(sorted(spec.resolved_inputs.items())))[1]
        return _group_index_for_node(scope_graph, primary.node), []
    pos = _default_add_node_position(scope_graph, size)
    return _group_index_for_rect(scope_graph, [pos[0], pos[1], size[0], size[1]]), []


def _default_add_node_position(
    scope_graph: Mapping[str, Any],
    size: tuple[float, float],
) -> tuple[float, float]:
    max_right = 0.0
    min_top = 0.0
    seen = False
    nodes = scope_graph.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            x, y, width, _ = _node_rect(node)
            max_right = max(max_right, x + width)
            min_top = y if not seen else min(min_top, y)
            seen = True
    if seen:
        return max_right + _NODE_H_GAP, min_top
    return 0.0, 0.0


def _nudge_to_open_slot(
    scope_graph: Mapping[str, Any],
    pos: list[float],
    size: tuple[float, float],
    *,
    within_group: int | None,
) -> list[float]:
    x, y = pos
    for _ in range(_MAX_COLLISION_NUDGES):
        rect = [x, y, size[0], size[1]]
        if not _rect_overlaps_any_node(scope_graph, rect):
            return [_round_pos(x), _round_pos(y)]
        x += _COLLISION_NUDGE_X
        y += _COLLISION_NUDGE_Y
        if within_group is not None:
            x, y = _clamp_position_to_group(scope_graph, within_group, x, y, size)
    return [_round_pos(x), _round_pos(y)]


def _clamp_position_to_group(
    scope_graph: Mapping[str, Any],
    group_index: int,
    x: float,
    y: float,
    size: tuple[float, float],
) -> tuple[float, float]:
    group = _group_bounding(scope_graph, group_index)
    if group is None:
        return x, y
    min_x = group[0] + _GROUP_PAD
    min_y = group[1] + _GROUP_PAD
    return max(min_x, x), max(min_y, y)


def _grow_group_to_fit(
    scope_graph: Mapping[str, Any],
    group_index: int,
    pos: list[float],
    size: tuple[float, float],
) -> bool:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list) or not (0 <= group_index < len(groups)):
        return False
    group = groups[group_index]
    if not isinstance(group, dict):
        return False
    bounding = group.get("bounding")
    if not isinstance(bounding, list) or len(bounding) != 4:
        return False
    min_x = float(bounding[0])
    min_y = float(bounding[1])
    width = float(bounding[2])
    height = float(bounding[3])
    needed_right = pos[0] + size[0] + _GROUP_PAD
    needed_bottom = pos[1] + size[1] + _GROUP_PAD
    right = min_x + width
    bottom = min_y + height
    grew = False
    if needed_right > right:
        bounding[2] = _round_pos(needed_right - min_x)
        grew = True
    if needed_bottom > bottom:
        bounding[3] = _round_pos(needed_bottom - min_y)
        grew = True
    return grew


def _rect_overlaps_any_node(scope_graph: Mapping[str, Any], rect: list[float]) -> bool:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return False
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        if _rectangles_overlap(rect, _node_rect(node)):
            return True
    return False


def _group_index_for_node(scope_graph: Mapping[str, Any], node: Mapping[str, Any]) -> int | None:
    return _group_index_for_rect(scope_graph, _node_rect(node))


def _group_index_for_rect(scope_graph: Mapping[str, Any], rect: list[float]) -> int | None:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list):
        return None
    center_x = rect[0] + rect[2] / 2
    center_y = rect[1] + rect[3] / 2
    best: tuple[float, int] | None = None
    for index, group in enumerate(groups):
        bbox = _group_bounding(scope_graph, index)
        if bbox is None:
            continue
        if bbox[0] <= center_x <= bbox[0] + bbox[2] and bbox[1] <= center_y <= bbox[1] + bbox[3]:
            area = bbox[2] * bbox[3]
            if best is None or area < best[0]:
                best = (area, index)
    return best[1] if best is not None else None


def _group_index_by_title(scope_graph: Mapping[str, Any], title: str) -> int | None:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list):
        return None
    for index, group in enumerate(groups):
        if isinstance(group, Mapping) and group.get("title") == title:
            return index
    return None


def _group_bounding(scope_graph: Mapping[str, Any], group_index: int) -> list[float] | None:
    groups = scope_graph.get("groups")
    if not isinstance(groups, list) or not (0 <= group_index < len(groups)):
        return None
    group = groups[group_index]
    if not isinstance(group, Mapping):
        return None
    bounding = group.get("bounding")
    if not isinstance(bounding, (list, tuple)) or len(bounding) != 4:
        return None
    return [float(bounding[0]), float(bounding[1]), float(bounding[2]), float(bounding[3])]


def _right_of_rect(rect: list[float], size: tuple[float, float]) -> tuple[float, float]:
    return rect[0] + rect[2] + _NODE_H_GAP, rect[1]


def _between_rects(
    left: list[float],
    right: list[float],
    size: tuple[float, float],
) -> tuple[float, float]:
    gap_left = left[0] + left[2]
    gap_right = right[0]
    if gap_right > gap_left:
        x = gap_left + max(0.0, (gap_right - gap_left - size[0]) / 2)
    else:
        left_center = left[0] + left[2] / 2
        right_center = right[0] + right[2] / 2
        x = ((left_center + right_center) / 2) - size[0] / 2
    y = ((left[1] + right[1]) / 2)
    return x, y


def _node_rect(node: Mapping[str, Any]) -> list[float]:
    pos = node.get("pos")
    size = node.get("size")
    x = float(pos[0]) if isinstance(pos, (list, tuple)) and len(pos) >= 2 else 0.0
    y = float(pos[1]) if isinstance(pos, (list, tuple)) and len(pos) >= 2 else 0.0
    width = float(size[0]) if isinstance(size, (list, tuple)) and len(size) >= 2 else 320.0
    height = float(size[1]) if isinstance(size, (list, tuple)) and len(size) >= 2 else 180.0
    return [x, y, width, height]


def _node_size(node: Mapping[str, Any]) -> tuple[float, float]:
    rect = _node_rect(node)
    return rect[2], rect[3]


def _rectangles_overlap(left: list[float], right: list[float]) -> bool:
    return not (
        left[0] + left[2] <= right[0]
        or right[0] + right[2] <= left[0]
        or left[1] + left[3] <= right[1]
        or right[1] + right[3] <= left[1]
    )


def _next_node_order(scope_graph: Mapping[str, Any]) -> int:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return 0
    max_order = -1
    for node in nodes:
        if isinstance(node, Mapping) and isinstance(node.get("order"), int):
            max_order = max(max_order, int(node["order"]))
    return max_order + 1


def _round_pos(value: float) -> float:
    return round(value, 2)


def _apply_set_mode(node_ref: ResolvedNodeRef, mode: int) -> None:
    node = node_ref.node
    if isinstance(node, dict):
        node["mode"] = mode


def _apply_remove_link(
    ledger: EditLedger,
    link_ref: ResolvedRemoveLinkRef,
) -> list[PortIssue]:
    removed = _remove_link_from_scope(
        ledger,
        scope_path=link_ref.scope_path,
        link_id=link_ref.link_id,
    )
    if removed:
        return []
    return [
        _issue(
            "remove_link_missing_at_apply",
            "Resolved link target was already absent by the time mutation applied.",
            severity="warning",
            detail={"scope_path": link_ref.scope_path, "link_id": link_ref.link_id},
        )
    ]


def _apply_remove_node(
    ledger: EditLedger,
    plan: ResolvedRemoveNodePlan,
) -> list[PortIssue]:
    node_ref = plan.node_ref
    node_id = node_ref.node_id if isinstance(node_ref.node_id, int) else None
    if node_id is None:
        return [
            _issue(
                "remove_node_missing_numeric_id",
                "Resolved node has no numeric LiteGraph id, so remove_node could not update link substrate safely.",
                severity="warning",
                detail={
                    "scope_path": node_ref.target.scope_path,
                    "uid": node_ref.target.uid,
                    "class_type": node_ref.class_type,
                },
            )
        ]
    scope = ledger.scopes[node_ref.target.scope_path]
    diagnostics: list[PortIssue] = []
    for rewire in plan.link_rewires:
        _rewire_link_origin(
            ledger,
            scope_path=rewire.scope_path,
            link_id=rewire.link_id,
            old_origin_id=rewire.old_origin_id,
            new_origin_id=rewire.new_origin_id,
            new_origin_slot=rewire.new_origin_slot,
        )
        diagnostics.append(
            _issue(
                "remove_node_passthrough_rewire",
                "remove_node re-stitched a helper passthrough link to its resolved source.",
                severity="info",
                detail={
                    "scope_path": rewire.scope_path,
                    "uid": node_ref.target.uid,
                    "class_type": node_ref.class_type,
                    "removed_node_id": node_id,
                    "link_id": rewire.link_id,
                    "old_origin_id": rewire.old_origin_id,
                    "new_origin_id": rewire.new_origin_id,
                    "new_origin_slot": rewire.new_origin_slot,
                },
            )
        )
    for link_id in plan.link_ids_to_remove:
        link = ledger.link_index.get((node_ref.target.scope_path, link_id))
        origin_id, _, target_id, _ = _link_endpoints(link) if link is not None else (None, None, None, None)
        _remove_link_from_scope(ledger, scope_path=node_ref.target.scope_path, link_id=link_id)
        diagnostics.append(
            _issue(
                "remove_node_link_cleanup",
                "remove_node cascade-removed a connected link.",
                severity="info",
                detail={
                    "scope_path": node_ref.target.scope_path,
                    "uid": node_ref.target.uid,
                    "class_type": node_ref.class_type,
                    "node_id": node_id,
                    "link_id": link_id,
                    "origin_id": origin_id,
                    "target_id": target_id,
                },
            )
        )
    _remove_node_from_scope(scope.graph, node_id)
    ledger.node_index.pop((node_ref.target.scope_path, node_ref.target.uid), None)
    return diagnostics


def _apply_upsert_link(
    ledger: EditLedger,
    source: ResolvedLinkEndpoint,
    target: ResolvedLinkEndpoint,
) -> list[PortIssue]:
    assert isinstance(source.ref, LinkSourceRef)
    assert isinstance(target.ref, LinkTargetRef)
    scope_path = source.ref.scope_path
    scope = ledger.scopes[scope_path]
    diagnostics: list[PortIssue] = []
    existing = _find_named_slot(target.node.get("inputs"), target.slot_name)
    if isinstance(existing, dict) and isinstance(existing.get("link"), int):
        old_link_id = existing["link"]
        if _remove_link_from_scope(ledger, scope_path=scope_path, link_id=old_link_id):
            diagnostics.append(
                _issue(
                    "upsert_link_replaced_existing",
                    "upsert_link removed the previous incoming link for the target input.",
                    severity="info",
                    detail={
                        "scope_path": scope_path,
                        "to_uid": target.ref.uid,
                        "to_input": target.slot_name,
                        "removed_link_id": old_link_id,
                    },
                )
            )

    link_id = ledger.mint_link_id(scope_path)
    target_slot = _ensure_input_slot(target.node, target.slot_name, target.socket_type)
    link_type = source.socket_type or target.socket_type or "*"
    link = _new_link_for_scope(
        scope,
        link_id=link_id,
        origin_id=source.node_id,
        origin_slot=source.slot_index or 0,
        target_id=target.node_id,
        target_slot=target_slot,
        link_type=link_type,
    )
    links = scope.graph.get("links")
    if not isinstance(links, list):
        links = []
        scope.graph["links"] = links
    links.append(link)
    ledger.link_index[(scope_path, link_id)] = link
    _ensure_output_link_reference(scope.graph, source.node_id, source.slot_index or 0, link_id)
    _set_input_link_reference(target.node, target_slot, link_id)
    return diagnostics


def _apply_add_node(
    ledger: EditLedger,
    spec: ResolvedAddNodeSpec,
) -> tuple[AppliedAddNodeSpec, list[PortIssue]]:
    scope_path = spec.op.scope_path
    node_id = ledger.mint_node_id(scope_path)
    uid = ledger.mint_uid(scope_path)
    provisional = materialize_litegraph_node(
        spec.op.class_type,
        spec.op.fields,
        spec.schema,
        node_id,
        uid,
        [0.0, 0.0],
    )
    size = _node_size(provisional)
    pos, group_index, grew_group, group_issues = _place_add_node(ledger, spec, size)
    node = materialize_litegraph_node(
        spec.op.class_type,
        spec.op.fields,
        spec.schema,
        node_id,
        uid,
        pos,
    )
    node["order"] = _next_node_order(spec.scope.graph)
    nodes = spec.scope.graph.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
        spec.scope.graph["nodes"] = nodes
    nodes.append(node)
    ledger.node_index[(scope_path, uid)] = node

    link_ids: list[int] = []
    diagnostics: list[PortIssue] = list(group_issues)
    for input_name in sorted(spec.resolved_inputs):
        source = spec.resolved_inputs[input_name]
        target_type = _normalize_type(getattr(spec.schema_inputs.get(input_name), "type", None))
        target_slot = _ensure_input_slot(node, input_name, target_type)
        link_id = ledger.mint_link_id(scope_path)
        link = _new_link_for_scope(
            spec.scope,
            link_id=link_id,
            origin_id=source.node_id,
            origin_slot=source.slot_index or 0,
            target_id=node_id,
            target_slot=target_slot,
            link_type=source.socket_type or target_type or "*",
        )
        links = spec.scope.graph.get("links")
        if not isinstance(links, list):
            links = []
            spec.scope.graph["links"] = links
        links.append(link)
        ledger.link_index[(scope_path, link_id)] = link
        link_ids.append(link_id)
        _ensure_output_link_reference(spec.scope.graph, source.node_id, source.slot_index or 0, link_id)
        _set_input_link_reference(node, target_slot, link_id)

    diagnostics.append(
        _issue(
            "add_node_applied",
            "add_node materialized a new LiteGraph node with deterministic ledger ids and placement.",
            severity="info",
            detail={
                "scope_path": scope_path,
                "class_type": spec.op.class_type,
                "node_id": node_id,
                "uid": uid,
                "pos": list(node.get("pos") or []),
                "group_index": group_index,
                "link_ids": link_ids,
            },
        )
    )
    if grew_group and group_index is not None:
        diagnostics.append(
            _issue(
                "add_node_group_growth",
                "add_node grew the target group bounding box minimally to contain the new node.",
                severity="info",
                detail={"scope_path": scope_path, "group_index": group_index, "uid": uid},
            )
        )

    return (
        AppliedAddNodeSpec(
            op=spec.op,
            scope_path=scope_path,
            uid=uid,
            node_id=node_id,
            link_ids=tuple(link_ids),
            source_uids=tuple(source.ref.uid for source in spec.resolved_inputs.values()),
            group_index=group_index if grew_group else None,
        ),
        diagnostics,
    )


def _apply_reorder(node_ref: ResolvedNodeRef, op: ReorderOp) -> list[PortIssue]:
    names = _reorder_names(node_ref.node, node_ref.class_type, op.axis)
    if names is None or tuple(names) == tuple(op.order):
        return []
    if op.axis == "widgets":
        values = node_ref.node.get("widgets_values")
        if not isinstance(values, list):
            return []
        index_by_name = {name: index for index, name in enumerate(names)}
        node_ref.node["widgets_values"] = [values[index_by_name[name]] for name in op.order]
        return [
            _issue(
                "reorder_widgets_applied",
                "Reordered widget values by the requested complete field-name permutation.",
                severity="info",
                detail={
                    "scope_path": op.target.scope_path,
                    "uid": op.target.uid,
                    "order": list(op.order),
                },
            )
        ]

    outputs = node_ref.node.get("outputs")
    if not isinstance(outputs, list):
        return []
    index_by_name = {name: index for index, name in enumerate(names)}
    node_ref.node["outputs"] = [outputs[index_by_name[name]] for name in op.order]
    for index, output in enumerate(node_ref.node["outputs"]):
        if isinstance(output, dict):
            output["slot_index"] = index
    return [
        _issue(
            "reorder_slots_applied",
            "Reordered output slots by the requested complete slot-name permutation.",
            severity="info",
            detail={"scope_path": op.target.scope_path, "uid": op.target.uid, "order": list(op.order)},
        )
    ]


def _apply_set_node_field(
    ledger: EditLedger,
    field_ref: ResolvedFieldRef,
    value: Any,
) -> list[PortIssue]:
    diagnostics: list[PortIssue] = []
    node = field_ref.node
    if not isinstance(node, dict):
        return diagnostics
    if field_ref.automatic_link_removal is not None:
        removed = _remove_link_from_scope(
            ledger,
            scope_path=field_ref.target.scope_path,
            link_id=field_ref.automatic_link_removal,
        )
        if not removed:
            diagnostics.append(
                _issue(
                    "automatic_link_removal_missing_link",
                    "Linked widget override referenced a missing link during apply; cleared the target slot anyway.",
                    severity="warning",
                    detail={
                        "scope_path": field_ref.target.scope_path,
                        "uid": field_ref.target.uid,
                        "field_path": field_ref.target.field_path,
                        "link_id": field_ref.automatic_link_removal,
                    },
                )
        )
        _clear_linked_input_surface(node, field_ref)
    _write_widget_value(node, field_ref, value)
    return diagnostics


def _clear_linked_input_surface(node: dict[str, Any], field_ref: ResolvedFieldRef) -> None:
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        return
    if field_ref.input_slot_index is None or field_ref.input_slot_index >= len(inputs):
        return
    slot = inputs[field_ref.input_slot_index]
    if not isinstance(slot, dict):
        return
    if _widget_name_for_input(slot) == field_ref.target.field_path:
        del inputs[field_ref.input_slot_index]
        return
    if "link" in slot:
        slot["link"] = None


def _write_widget_value(node: dict[str, Any], field_ref: ResolvedFieldRef, value: Any) -> None:
    widgets_values = node.get("widgets_values")
    if field_ref.widget_key is not None:
        if isinstance(widgets_values, dict):
            widgets_values[field_ref.widget_key] = value
            return
        if isinstance(widgets_values, Mapping):
            widgets_values = dict(widgets_values)
            widgets_values[field_ref.widget_key] = value
            node["widgets_values"] = widgets_values
            return
    assert field_ref.widget_index is not None
    if not isinstance(widgets_values, list):
        widgets_values = []
        node["widgets_values"] = widgets_values
    while len(widgets_values) <= field_ref.widget_index:
        widgets_values.append(None)
    widgets_values[field_ref.widget_index] = value


def _reorder_names(node: Mapping[str, Any], class_type: str, axis: str) -> tuple[str, ...] | None:
    if axis == "widgets":
        values = node.get("widgets_values")
        if not isinstance(values, list):
            return None
        names = list(effective_widget_names_for_class(class_type, allow_object_info_fallback=True))
        if len(names) < len(values):
            recovered = _widget_names_from_input_stubs(node.get("inputs"))
            if len(recovered) >= len(values):
                names = recovered
        if len(names) != len(values) or any(not name for name in names):
            return None
        return tuple(names)

    outputs = node.get("outputs")
    if not isinstance(outputs, list):
        return None
    names: list[str] = []
    for output in outputs:
        if not isinstance(output, Mapping):
            return None
        name = output.get("name")
        if not isinstance(name, str) or not name:
            return None
        names.append(name)
    if len(set(names)) != len(names):
        return None
    return tuple(names)


def _widget_names_from_input_stubs(inputs: Any) -> list[str]:
    if not isinstance(inputs, list):
        return []
    names: list[str] = []
    for slot in inputs:
        name = _widget_name_for_input(slot)
        if name is not None:
            names.append(name)
    return names


def _linked_widget_names(inputs: Any) -> set[str]:
    if not isinstance(inputs, list):
        return set()
    names: set[str] = set()
    for slot in inputs:
        if not isinstance(slot, Mapping):
            continue
        if not isinstance(slot.get("link"), int):
            continue
        name = _widget_name_for_input(slot)
        if name is not None:
            names.add(name)
    return names


def _link_ids(links: list[Any]) -> tuple[int, ...]:
    return tuple(sorted(link_id for link in links if (link_id := _link_id(link)) is not None))


def _collect_links_for_origin(scope_graph: Mapping[str, Any], node_id: int) -> list[Any]:
    links = scope_graph.get("links")
    if not isinstance(links, list):
        return []
    return [link for link in links if _link_endpoints(link)[0] == node_id]


def _collect_links_for_target(scope_graph: Mapping[str, Any], node_id: int) -> list[Any]:
    links = scope_graph.get("links")
    if not isinstance(links, list):
        return []
    return [link for link in links if _link_endpoints(link)[2] == node_id]


def _build_rewires(
    scope_path: str,
    links: list[Any],
    *,
    old_origin_id: int,
    new_origin_id: int,
    new_origin_slot: int,
) -> tuple[ResolvedLinkRewire, ...]:
    return tuple(
        ResolvedLinkRewire(
            scope_path=scope_path,
            link_id=link_id,
            old_origin_id=old_origin_id,
            new_origin_id=new_origin_id,
            new_origin_slot=new_origin_slot,
        )
        for link in links
        if (link_id := _link_id(link)) is not None
    )


def _build_rewires_for_setnode_gets(
    scope_graph: Mapping[str, Any],
    set_node: Mapping[str, Any],
    scope_path: str,
    source: tuple[int, int],
) -> tuple[ResolvedLinkRewire, ...]:
    name = _helper_broadcast_name(set_node)
    if not name:
        return ()
    rewires: list[ResolvedLinkRewire] = []
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return ()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if str(node.get("type") or node.get("class_type") or "") != "GetNode":
            continue
        if _helper_broadcast_name(node) != name:
            continue
        get_id = node.get("id")
        if not isinstance(get_id, int):
            continue
        rewires.extend(
            _build_rewires(
                scope_path,
                _collect_links_for_origin(scope_graph, get_id),
                old_origin_id=get_id,
                new_origin_id=source[0],
                new_origin_slot=source[1],
            )
        )
    return tuple(rewires)


def _resolve_getnode_source(
    scope_graph: Mapping[str, Any],
    node: Mapping[str, Any],
    scope_path: str,
) -> tuple[tuple[int, int] | None, list[PortIssue]]:
    name = _helper_broadcast_name(node)
    if not name:
        return None, []
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return None, []
    matches = [
        candidate
        for candidate in nodes
        if isinstance(candidate, dict)
        and str(candidate.get("type") or candidate.get("class_type") or "") == "SetNode"
        and _helper_broadcast_name(candidate) == name
    ]
    if len(matches) > 1:
        return None, [
            _issue(
                "remove_node_getnode_ambiguous_source",
                "GetNode remove_node passthrough requires exactly one matching SetNode source.",
                detail={
                    "scope_path": scope_path,
                    "channel": name,
                    "matching_set_node_ids": [candidate.get("id") for candidate in matches],
                },
            )
        ]
    if len(matches) != 1:
        return None, []
    set_id = matches[0].get("id")
    if not isinstance(set_id, int):
        return None, []
    return _resolve_passthrough_source(scope_graph, set_id, scope_path)


def _resolve_passthrough_source(
    scope_graph: Mapping[str, Any],
    node_id: int,
    scope_path: str,
    *,
    visited: frozenset[int] = frozenset(),
) -> tuple[tuple[int, int] | None, list[PortIssue]]:
    if node_id in visited:
        return None, []
    inbound_links = _collect_links_for_target(scope_graph, node_id)
    if not inbound_links:
        return None, []
    if len(inbound_links) > 1:
        node = _node_by_id(scope_graph, node_id)
        class_type = str(node.get("type") or node.get("class_type") or "") if isinstance(node, dict) else ""
        return None, [
            _issue(
                "remove_node_helper_fan_in_unsupported",
                f"{class_type or 'Helper'} remove_node passthrough only supports a single inbound source.",
                detail={
                    "scope_path": scope_path,
                    "node_id": node_id,
                    "class_type": class_type,
                    "inbound_link_ids": list(_link_ids(inbound_links)),
                },
            )
        ]
    origin_id, origin_slot, _, _ = _link_endpoints(inbound_links[0])
    if not isinstance(origin_id, int):
        return None, []
    origin_node = _node_by_id(scope_graph, origin_id)
    origin_class = str(origin_node.get("type") or origin_node.get("class_type") or "") if isinstance(origin_node, dict) else ""
    if origin_class == "Reroute":
        return _resolve_passthrough_source(scope_graph, origin_id, scope_path, visited=visited | {node_id})
    if origin_class == "GetNode":
        return _resolve_getnode_source(scope_graph, origin_node, scope_path)
    if origin_class == "SetNode":
        return _resolve_passthrough_source(scope_graph, origin_id, scope_path, visited=visited | {node_id})
    return (origin_id, origin_slot or 0), []


def _helper_broadcast_name(node: Mapping[str, Any]) -> str | None:
    widgets_values = node.get("widgets_values")
    if isinstance(widgets_values, list) and widgets_values:
        name = widgets_values[0]
        if isinstance(name, str) and name:
            return name
    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        value = inputs.get("widget_0") or inputs.get("name")
        if isinstance(value, str) and value:
            return value
    return None


def _remove_link_from_scope(ledger: EditLedger, *, scope_path: str, link_id: int) -> bool:
    scope = ledger.scopes[scope_path]
    links = scope.graph.get("links")
    if not isinstance(links, list):
        return False
    for index, link in enumerate(list(links)):
        if _link_id(link) != link_id:
            continue
        links.pop(index)
        origin_id, origin_slot, target_id, target_slot = _link_endpoints(link)
        if isinstance(origin_id, int):
            _remove_output_link_reference(scope.graph, origin_id, origin_slot, link_id)
        if isinstance(target_id, int):
            _clear_input_link_reference(scope.graph, target_id, target_slot, link_id)
        ledger.link_index.pop((scope_path, link_id), None)
        return True
    return False


def _rewire_link_origin(
    ledger: EditLedger,
    *,
    scope_path: str,
    link_id: int,
    old_origin_id: int,
    new_origin_id: int,
    new_origin_slot: int,
) -> bool:
    scope = ledger.scopes[scope_path]
    links = scope.graph.get("links")
    if not isinstance(links, list):
        return False
    for link in links:
        if _link_id(link) != link_id:
            continue
        old_origin_slot = _link_endpoints(link)[1]
        _remove_output_link_reference(scope.graph, old_origin_id, old_origin_slot, link_id)
        _set_link_origin(link, new_origin_id, new_origin_slot)
        _ensure_output_link_reference(scope.graph, new_origin_id, new_origin_slot, link_id)
        ledger.link_index[(scope_path, link_id)] = link
        return True
    return False


def _set_link_origin(link: Any, node_id: int, slot: int) -> None:
    if isinstance(link, Mapping):
        link["origin_id"] = node_id
        link["origin_slot"] = slot
        return
    if isinstance(link, list) and len(link) >= 3:
        link[1] = node_id
        link[2] = slot


def _new_link_for_scope(
    scope: ScopeState,
    *,
    link_id: int,
    origin_id: int,
    origin_slot: int,
    target_id: int,
    target_slot: int,
    link_type: str,
) -> Any:
    if _scope_uses_dict_links(scope):
        return {
            "id": link_id,
            "origin_id": origin_id,
            "origin_slot": origin_slot,
            "target_id": target_id,
            "target_slot": target_slot,
            "type": link_type,
        }
    return [link_id, origin_id, origin_slot, target_id, target_slot, link_type]


def _scope_uses_dict_links(scope: ScopeState) -> bool:
    links = scope.graph.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, Mapping):
                return True
            if isinstance(link, list):
                return False
    return scope.kind == "subgraph"


def _ensure_input_slot(node: Mapping[str, Any], input_name: str, socket_type: str | None) -> int:
    if not isinstance(node, dict):
        return 0
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        inputs = []
        node["inputs"] = inputs
    index = _find_named_slot_index(inputs, input_name)
    if index is not None:
        return index
    inputs.append({"name": input_name, "type": socket_type or "*", "link": None})
    return len(inputs) - 1


def _set_input_link_reference(node: Mapping[str, Any], slot_index: int, link_id: int) -> None:
    if not isinstance(node, dict):
        return
    inputs = node.get("inputs")
    if not isinstance(inputs, list) or not (0 <= slot_index < len(inputs)):
        return
    slot = inputs[slot_index]
    if isinstance(slot, dict):
        slot["link"] = link_id


def _ensure_output_link_reference(
    scope_graph: Mapping[str, Any],
    node_id: int,
    slot_index: int,
    link_id: int,
) -> None:
    node = _node_by_id(scope_graph, node_id)
    if node is None:
        return
    outputs = node.get("outputs")
    if not isinstance(outputs, list) or not (0 <= slot_index < len(outputs)):
        return
    output = outputs[slot_index]
    if not isinstance(output, dict):
        return
    links = output.get("links")
    if not isinstance(links, list):
        links = []
        output["links"] = links
    if link_id not in links:
        links.append(link_id)


def _sync_scope_counters(ledger: EditLedger) -> None:
    for scope in ledger.scopes.values():
        if scope.kind == "root":
            scope.graph["last_node_id"] = max(scope.node_counter, max(scope.used_node_ids, default=0))
            scope.graph["last_link_id"] = max(scope.link_counter, max(scope.used_link_ids, default=0))
            continue
        state = scope.graph.get("state")
        if not isinstance(state, dict):
            state = {}
            scope.graph["state"] = state
        state["lastNodeId"] = max(scope.node_counter, max(scope.used_node_ids, default=0))
        state["lastLinkId"] = max(scope.link_counter, max(scope.used_link_ids, default=0))


def _link_id(link: Any) -> int | None:
    if isinstance(link, Mapping):
        return link.get("id") if isinstance(link.get("id"), int) else None
    if isinstance(link, list) and link and isinstance(link[0], int):
        return link[0]
    return None


def _link_endpoints(link: Any) -> tuple[int | None, int | None, int | None, int | None]:
    if isinstance(link, Mapping):
        return (
            link.get("origin_id") if isinstance(link.get("origin_id"), int) else None,
            link.get("origin_slot") if isinstance(link.get("origin_slot"), int) else None,
            link.get("target_id") if isinstance(link.get("target_id"), int) else None,
            link.get("target_slot") if isinstance(link.get("target_slot"), int) else None,
        )
    if (
        isinstance(link, list)
        and len(link) >= 5
        and isinstance(link[1], int)
        and isinstance(link[2], int)
        and isinstance(link[3], int)
        and isinstance(link[4], int)
    ):
        return link[1], link[2], link[3], link[4]
    return None, None, None, None


def _node_by_id(scope_graph: Mapping[str, Any], node_id: int) -> dict[str, Any] | None:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, dict) and node.get("id") == node_id:
            return node
    return None


def _remove_node_from_scope(scope_graph: Mapping[str, Any], node_id: int) -> bool:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return False
    for index, node in enumerate(list(nodes)):
        if isinstance(node, dict) and node.get("id") == node_id:
            nodes.pop(index)
            return True
    return False


def _remove_output_link_reference(
    scope_graph: Mapping[str, Any],
    node_id: int,
    slot_index: int | None,
    link_id: int,
) -> None:
    if slot_index is None:
        return
    node = _node_by_id(scope_graph, node_id)
    if node is None:
        return
    outputs = node.get("outputs")
    if not isinstance(outputs, list) or not (0 <= slot_index < len(outputs)):
        return
    output = outputs[slot_index]
    if not isinstance(output, dict):
        return
    links = output.get("links")
    if not isinstance(links, list):
        return
    output["links"] = [item for item in links if item != link_id]


def _clear_input_link_reference(
    scope_graph: Mapping[str, Any],
    node_id: int,
    slot_index: int | None,
    link_id: int,
) -> None:
    if slot_index is None:
        return
    node = _node_by_id(scope_graph, node_id)
    if node is None:
        return
    inputs = node.get("inputs")
    if not isinstance(inputs, list) or not (0 <= slot_index < len(inputs)):
        return
    input_slot = inputs[slot_index]
    if isinstance(input_slot, dict) and input_slot.get("link") == link_id:
        input_slot["link"] = None


def _schema_output_type(
    schema_provider: Any,
    class_type: str,
    slot_index: int | None,
    slot_name: str,
) -> str | None:
    schema = schema_for(schema_provider, class_type)
    outputs = getattr(schema, "outputs", None) or []
    if slot_index is not None and 0 <= slot_index < len(outputs):
        return _normalize_type(getattr(outputs[slot_index], "type", None))
    for output in outputs:
        if getattr(output, "name", None) == slot_name:
            return _normalize_type(getattr(output, "type", None))
    cached_names = cached_output_names(class_type)
    if slot_index is not None and slot_index < len(cached_names):
        return _normalize_type(cached_names[slot_index])
    return None


def _validate_literal_value(
    *,
    value: Any,
    spec: InputSpec | None,
    class_type: str,
    input_name: str,
    context: str,
) -> list[PortIssue]:
    if spec is None:
        return []
    issues: list[PortIssue] = []
    choices = getattr(spec, "choices", None) or []
    if choices and value not in choices and _coerce_choice_value(value, choices) is _NO_MATCH:
        issues.append(
            _issue(
                "value_not_in_enum",
                f"{context} rejected {class_type}.{input_name}: value {value!r} is not in the declared enum.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                    "choices": list(choices),
                },
            )
        )
    min_value = getattr(spec, "min", None)
    max_value = getattr(spec, "max", None)
    if min_value is not None or max_value is not None:
        numeric = _as_number(value)
        if numeric is not None and (
            (min_value is not None and numeric < float(min_value))
            or (max_value is not None and numeric > float(max_value))
        ):
            issues.append(
                _issue(
                    "value_out_of_range",
                    f"{context} rejected {class_type}.{input_name}: value {value!r} is outside the declared range.",
                    detail={
                        "class_type": class_type,
                        "input": input_name,
                        "value": value,
                        "min": min_value,
                        "max": max_value,
                    },
                )
            )
    expected_type = _primitive_expected_type(getattr(spec, "type", None))
    if expected_type is not None and not _matches_primitive_type(value, expected_type):
        issues.append(
            _issue(
                "value_type_mismatch",
                f"{context} rejected {class_type}.{input_name}: expected {expected_type}, got {type(value).__name__}.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
            )
        )
    return issues


def _normalize_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text == "*":
        return None
    return text


def _primitive_expected_type(value: Any) -> str | None:
    normalized = _normalize_type(value)
    if normalized in {"INT", "INTEGER"}:
        return "INT"
    if normalized in {"FLOAT", "DOUBLE"}:
        return "FLOAT"
    if normalized in {"BOOL", "BOOLEAN"}:
        return "BOOLEAN"
    if normalized in {"STR", "STRING", "TEXT"}:
        return "STRING"
    return None


def _matches_primitive_type(value: Any, expected_type: str) -> bool:
    if expected_type == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "FLOAT":
        return ((isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float))
    if expected_type == "BOOLEAN":
        return isinstance(value, bool)
    if expected_type == "STRING":
        return isinstance(value, str)
    return True


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_NO_MATCH = object()


def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        for choice in choices:
            if isinstance(choice, str) and choice.replace("\\", "/") == normalized:
                return choice
    return _NO_MATCH


__all__ = [
    "ApplyResult",
    "ResolvedAddNodeSpec",
    "ResolvedFieldRef",
    "ResolvedLinkEndpoint",
    "ResolvedNodeRef",
    "ResolvedRemoveLinkRef",
    "ResolveResult",
    "apply_delta",
    "resolve_delta",
]
