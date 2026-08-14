from __future__ import annotations

import copy
import time
from typing import Any, Mapping

from .ledger import EditLedger, ScopeState
from .ops import AddNodeOp, EditOp, RemoveLinkOp, RemoveNodeOp, ReorderOp, SetModeOp, SetNodeFieldOp, SetTitleOp, UpsertLinkOp
from vibecomfy.porting.edit.apply_links import _link_endpoints, _link_id, _link_ids_targeting_input, _node_by_id
from vibecomfy.porting.edit.apply_slots import _find_named_slot_index
from vibecomfy.porting.edit.apply_types import AppliedAddNodeSpec, GuardResult, ResolvedFieldRef, ResolvedLinkEndpoint, ResolvedNodeRef, ResolvedOp, ResolvedRemoveLinkRef, ResolvedRemoveNodePlan, _issue
from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _find_named_slot


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
        from .normalize import is_normalize_available, normalize_ui_json

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
                # R2-D1b: the linked-widget override deletes the target input
                # slot, so every other link targeting the same node at a higher
                # slot is deterministically re-slotted down by one.  Attribute
                # those re-slots so the full-UI guard accepts the compacted
                # candidate instead of flagging an unattributed link change.
                original_scope = original_ledger.scopes.get(op.target.scope_path)
                if (
                    original_scope is not None
                    and isinstance(resolved.node_id, int)
                    and isinstance(resolved.input_slot_index, int)
                ):
                    for link in original_scope.graph.get("links") or []:
                        _origin_id, _origin_slot, target_id, target_slot = _link_endpoints(link)
                        if (
                            target_id == resolved.node_id
                            and isinstance(target_slot, int)
                            and target_slot > resolved.input_slot_index
                        ):
                            link_id = _link_id(link)
                            if link_id is not None:
                                touched_links.add((op.target.scope_path, link_id))
            continue
        if isinstance(op, SetModeOp):
            allow_node_paths(op.target.scope_path, op.target.uid, "mode")
            continue
        if isinstance(op, SetTitleOp):
            allow_node_paths(op.target.scope_path, op.target.uid, "title")
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
                original_scope = original_ledger.scopes.get(op.target.scope_path)
                original_node_id = original_target.get("id")
                original_target_slot = _find_named_slot_index(
                    original_target.get("inputs"),
                    target.slot_name,
                )
                if (
                    original_scope is not None
                    and isinstance(original_node_id, int)
                    and isinstance(original_target_slot, int)
                ):
                    for old_link_id in _link_ids_targeting_input(
                        original_scope,
                        original_node_id,
                        original_target_slot,
                    ):
                        removed_links.add((op.target.scope_path, old_link_id))
                        allow_link_endpoint_paths(op.target.scope_path, old_link_id)
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
        from .normalize import normalize_allow_list_matches
    except Exception:
        return False
    return all(normalize_allow_list_matches(node_class, field_path) is not None for field_path in diffs)


def _all_diffs_op_allowed(diffs: list[str], allowed_paths: set[str]) -> bool:
    if not allowed_paths:
        return False
    return all(any(_path_is_at_or_below(diff, allowed) for allowed in allowed_paths) for diff in diffs)


def _path_is_at_or_below(path: str, allowed: str) -> bool:
    return path == allowed or path.startswith(f"{allowed}.") or path.startswith(f"{allowed}[")
