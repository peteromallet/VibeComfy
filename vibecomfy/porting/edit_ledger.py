from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence

from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.scope import compose_scope_path, sg_key
from vibecomfy.porting.uid import make_uid


_MINTED_UID_RE = re.compile(r"^n(\d+)$")


def _issue(
    code: str,
    message: str,
    *,
    severity: Literal["error", "warning", "info"] = "warning",
    detail: Mapping[str, Any] | None = None,
) -> PortIssue:
    return PortIssue(code=code, message=message, severity=severity, detail=dict(detail or {}))


def _node_id_set(nodes: Sequence[Any]) -> set[int]:
    ids: set[int] = set()
    for node in nodes:
        if isinstance(node, Mapping):
            node_id = node.get("id")
            if isinstance(node_id, int):
                ids.add(node_id)
    return ids


def _link_id_set(links: Sequence[Any]) -> set[int]:
    ids: set[int] = set()
    for link in links:
        if isinstance(link, Mapping):
            link_id = link.get("id")
            if isinstance(link_id, int):
                ids.add(link_id)
            continue
        if isinstance(link, Sequence) and not isinstance(link, (str, bytes)):
            if link and isinstance(link[0], int):
                ids.add(link[0])
    return ids


def _counter_seed(explicit: Any, used_ids: set[int]) -> int:
    if isinstance(explicit, int):
        return explicit
    return max(used_ids, default=0)


def _uid_counter_seed(local_uids: Iterable[str]) -> int:
    highest = 0
    for uid in local_uids:
        match = _MINTED_UID_RE.match(uid)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest


def _iter_subgraph_defs(definitions: Any) -> Iterable[tuple[int, dict[str, Any]]]:
    if not isinstance(definitions, Mapping):
        return
    subgraphs = definitions.get("subgraphs")
    if not isinstance(subgraphs, list):
        return
    for index, definition in enumerate(subgraphs):
        if isinstance(definition, dict):
            yield index, definition


def _unique_scope_segment(base: str, seen: dict[str, int]) -> str:
    count = seen.get(base, 0) + 1
    seen[base] = count
    if count == 1:
        return base
    return f"{base}@{count}"


@dataclass(slots=True)
class ScopeState:
    scope_path: str
    graph: dict[str, Any]
    path_tokens: tuple[str, ...]
    kind: Literal["root", "subgraph"]
    node_counter: int
    link_counter: int
    uid_counter: int
    used_node_ids: set[int]
    used_link_ids: set[int]
    used_local_uids: set[str]


@dataclass(slots=True)
class EditLedger:
    graph: dict[str, Any]
    diagnostics: tuple[PortIssue, ...]
    scopes: dict[str, ScopeState]
    node_index: dict[tuple[str, str], dict[str, Any]]
    link_index: dict[tuple[str, int], Any]
    global_node_counter: int
    global_link_counter: int
    used_node_ids: set[int]
    used_link_ids: set[int]

    @classmethod
    def ingest(cls, raw_graph: Mapping[str, Any]) -> "EditLedger":
        graph = copy.deepcopy(dict(raw_graph))
        diagnostics: list[PortIssue] = []
        scopes: dict[str, ScopeState] = {}
        node_index: dict[tuple[str, str], dict[str, Any]] = {}
        link_index: dict[tuple[str, int], Any] = {}
        used_node_ids: set[int] = set()
        used_link_ids: set[int] = set()

        def visit_scope(
            scope_graph: dict[str, Any],
            *,
            scope_path: str,
            path_tokens: tuple[str, ...],
            kind: Literal["root", "subgraph"],
        ) -> None:
            nodes = scope_graph.get("nodes")
            node_list = nodes if isinstance(nodes, list) else []
            links = scope_graph.get("links")
            link_list = links if isinstance(links, list) else []

            local_uid_counts: dict[str, int] = {}
            stamped_local_uids: list[str] = []
            local_node_ids = _node_id_set(node_list)
            local_link_ids = _link_id_set(link_list)
            used_node_ids.update(local_node_ids)
            used_link_ids.update(local_link_ids)

            for node in node_list:
                if not isinstance(node, dict):
                    continue
                properties = node.get("properties")
                if not isinstance(properties, dict):
                    properties = {}
                    node["properties"] = properties

                requested_uid = properties.get("vibecomfy_uid")
                if requested_uid is None:
                    node_id = node.get("id")
                    requested_uid = str(node_id) if node_id is not None else "node"
                else:
                    requested_uid = str(requested_uid)

                occurrence = local_uid_counts.get(requested_uid, 0) + 1
                local_uid_counts[requested_uid] = occurrence
                stamped_uid = requested_uid if occurrence == 1 else f"{requested_uid}~{occurrence}"
                if occurrence > 1:
                    diagnostics.append(
                        _issue(
                            "duplicate_scope_uid",
                            "Duplicate vibecomfy_uid in scope was deterministically suffixed.",
                            detail={
                                "scope_path": scope_path,
                                "path_tokens": list(path_tokens),
                                "requested_uid": requested_uid,
                                "assigned_uid": stamped_uid,
                                "occurrence": occurrence,
                                "node_id": node.get("id"),
                            },
                        )
                    )
                properties["vibecomfy_uid"] = stamped_uid
                stamped_local_uids.append(stamped_uid)
                node_index[(scope_path, stamped_uid)] = node

            for link in link_list:
                link_id: int | None = None
                if isinstance(link, Mapping) and isinstance(link.get("id"), int):
                    link_id = link["id"]
                elif isinstance(link, Sequence) and not isinstance(link, (str, bytes)):
                    if link and isinstance(link[0], int):
                        link_id = link[0]
                if link_id is not None:
                    link_index[(scope_path, link_id)] = link

            if kind == "root":
                node_seed = _counter_seed(scope_graph.get("last_node_id"), local_node_ids)
                link_seed = _counter_seed(scope_graph.get("last_link_id"), local_link_ids)
            else:
                state = scope_graph.get("state")
                state = state if isinstance(state, Mapping) else {}
                node_seed = _counter_seed(state.get("lastNodeId"), local_node_ids)
                link_seed = _counter_seed(state.get("lastLinkId"), local_link_ids)

            scopes[scope_path] = ScopeState(
                scope_path=scope_path,
                graph=scope_graph,
                path_tokens=path_tokens,
                kind=kind,
                node_counter=node_seed,
                link_counter=link_seed,
                uid_counter=_uid_counter_seed(stamped_local_uids),
                used_node_ids=set(local_node_ids),
                used_link_ids=set(local_link_ids),
                used_local_uids=set(stamped_local_uids),
            )

            seen_segments: dict[str, int] = {}
            for index, definition in _iter_subgraph_defs(scope_graph.get("definitions")):
                segment = _unique_scope_segment(sg_key(definition), seen_segments)
                child_scope_path = compose_scope_path(
                    [part for part in (scope_path, segment) if part]
                )
                child_tokens = (*path_tokens, "definitions", "subgraphs", str(index))
                visit_scope(
                    definition,
                    scope_path=child_scope_path,
                    path_tokens=child_tokens,
                    kind="subgraph",
                )

        visit_scope(graph, scope_path="", path_tokens=(), kind="root")

        global_node_counter = max(
            max(used_node_ids, default=0),
            max((scope.node_counter for scope in scopes.values()), default=0),
        )
        global_link_counter = max(
            max(used_link_ids, default=0),
            max((scope.link_counter for scope in scopes.values()), default=0),
        )

        return cls(
            graph=graph,
            diagnostics=tuple(diagnostics),
            scopes=scopes,
            node_index=node_index,
            link_index=link_index,
            global_node_counter=global_node_counter,
            global_link_counter=global_link_counter,
            used_node_ids=used_node_ids,
            used_link_ids=used_link_ids,
        )

    def stamped_copy(self) -> dict[str, Any]:
        return copy.deepcopy(self.graph)

    def resolve_node(self, scope_path: str, uid: str) -> dict[str, Any] | None:
        return self.node_index.get((scope_path, uid))

    def resolve_link(self, scope_path: str, link_id: int) -> Any | None:
        return self.link_index.get((scope_path, link_id))

    def qualified_uid(self, scope_path: str, uid: str) -> str:
        return make_uid(scope_path, uid)

    def mint_uid(self, scope_path: str) -> str:
        scope = self.scopes[scope_path]
        while True:
            scope.uid_counter += 1
            candidate = f"n{scope.uid_counter}"
            if candidate not in scope.used_local_uids:
                scope.used_local_uids.add(candidate)
                return candidate

    def mint_node_id(self, scope_path: str) -> int:
        scope = self.scopes[scope_path]
        while True:
            candidate = max(scope.node_counter, self.global_node_counter) + 1
            scope.node_counter = candidate
            self.global_node_counter = candidate
            if candidate not in self.used_node_ids:
                self.used_node_ids.add(candidate)
                scope.used_node_ids.add(candidate)
                return candidate

    def mint_link_id(self, scope_path: str) -> int:
        scope = self.scopes[scope_path]
        while True:
            candidate = max(scope.link_counter, self.global_link_counter) + 1
            scope.link_counter = candidate
            self.global_link_counter = candidate
            if candidate not in self.used_link_ids:
                self.used_link_ids.add(candidate)
                scope.used_link_ids.add(candidate)
                return candidate


__all__ = ["EditLedger", "ScopeState"]
