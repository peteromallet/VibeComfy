"""SCC-aware layer assignment for the fresh-layout engine.

Phase 1 Step 2: :func:`compute_layers` produces a ``dict[str, int]``
mapping every node uid to its integer layer (0 = sources/orphans).

The algorithm is a textbook iterative Tarjan SCC collapse followed by
Kahn longest-path depth on the resulting DAG.  Determinism is guaranteed
by sorting neighbour uids with ``uid.zfill(20)`` at every branching point.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role precedence for deterministic crossing-reduction tie-break  (T21)
# ---------------------------------------------------------------------------

# Toggle gate: when True the barycenter sweep adds a role-precedence rank
# between bary_score and uid in the sort key (positive-before-negative).
_ROLE_CROSSING_REDUCTION_TIEBREAK = True

# Node class-type families that are treated as "positive" (source / input).
_POSITIVE_ROLE_FAMILIES: frozenset[str] = frozenset({
    "LoadImage",
    "LoadImageMask",
    "LoadAudio",
    "LoadVideo",
    "VHS_LoadVideo",
    "PrimitiveNode",
    "PrimitiveString",
    "PrimitiveInt",
    "PrimitiveFloat",
    "IntegerPrimitive",
    "StringConstant",
    "FloatConstant",
    "Note",
    "MarkdownNote",
})

# Node class-type families that are treated as "negative" (output / sink).
_NEGATIVE_ROLE_FAMILIES: frozenset[str] = frozenset({
    "SaveImage",
    "SaveImageWebsocket",
    "PreviewImage",
    "PreviewVideo",
    "VHS_VideoCombine",
    "SaveVideo",
    "SaveAnimatedWEBP",
    "SaveAnimatedPNG",
    "SaveAudio",
    "UploadImage",
    "UploadVideo",
    "UploadAudio",
})


def _role_precedence_rank(class_type: str) -> int:
    """Return 0 for positive (source), 2 for negative (sink), 1 for neutral.

    This is used as a deterministic tie-break in the barycenter sweep:
    nodes with equal barycentre scores are ordered positive-first,
    then neutral, then negative, then by uid.
    """
    if class_type in _POSITIVE_ROLE_FAMILIES:
        return 0
    if class_type in _NEGATIVE_ROLE_FAMILIES:
        return 2
    return 1


def compute_layers(wf: Any) -> dict[str, int]:
    """Return ``{uid: layer, ...}`` for every node in *wf*.

    The workflow object is expected to have ``wf.nodes`` (``dict[str, VibeNode]``)
    and ``wf.edges`` (``list[VibeEdge]``).  Every edge's ``from_node`` / ``to_node``
    is translated through ``id_to_uid`` before adjacency construction, so orphan
    endpoints are dropped with a debug log.

    The result is total: any uid present in ``wf.nodes`` that was not reached by
    the longest-path walk receives layer ``0`` via ``setdefault`` and a warning.
    """
    # ── Build id → uid translation table ──────────────────────────────
    id_to_uid: dict[str, str] = {
        n.id: n.uid for n in wf.nodes.values()
    }

    # ── Build adjacency (uid → set of uid) ────────────────────────────
    # We store neighbours as sorted lists to guarantee deterministic iteration.
    uid_neighbors: dict[str, list[str]] = {}
    referenced_uids: set[str] = set()

    for node in wf.nodes.values():
        uid_neighbors.setdefault(node.uid, [])

    for edge in wf.edges:
        from_uid = id_to_uid.get(edge.from_node)
        to_uid = id_to_uid.get(edge.to_node)
        if from_uid is None:
            logger.debug("compute_layers: unknown from_node=%r in edge; dropping", edge.from_node)
            continue
        if to_uid is None:
            logger.debug("compute_layers: unknown to_node=%r in edge; dropping", edge.to_node)
            continue
        referenced_uids.add(from_uid)
        referenced_uids.add(to_uid)
        if to_uid not in uid_neighbors.setdefault(from_uid, []):
            uid_neighbors.setdefault(from_uid, []).append(to_uid)

    # Sort neighbour lists for deterministic ordering.
    # Only process referenced uids through Tarjan; unreferenced orphans
    # land in layer 0 via the soft-totality safety net below.
    all_uids = sorted(referenced_uids, key=lambda u: u.zfill(20))
    for uid in all_uids:
        uid_neighbors[uid].sort(key=lambda u: u.zfill(20))

    # ── Iterative Tarjan SCC ─────────────────────────────────────────
    scc_id = _tarjan_scc_iterative(uid_neighbors, all_uids)

    # ── Build SCC DAG ────────────────────────────────────────────────
    # scc_members: scc_root → list of member uids
    scc_members: dict[str, list[str]] = {}
    for uid in all_uids:
        root = scc_id[uid]
        scc_members.setdefault(root, []).append(uid)

    # SCC adjacency: edges between different SCCs
    scc_adj: dict[str, set[str]] = {root: set() for root in scc_members}
    for uid in all_uids:
        src_root = scc_id[uid]
        for neighbor in uid_neighbors.get(uid, []):
            dst_root = scc_id[neighbor]
            if dst_root != src_root:
                scc_adj[src_root].add(dst_root)

    # ── Indegree for Kahn (on SCC DAG) ────────────────────────────────
    indegree: dict[str, int] = {root: 0 for root in scc_members}
    for src_root, dst_roots in scc_adj.items():
        for dst_root in dst_roots:
            indegree[dst_root] += 1

    # ── Kahn longest-path depth processing ────────────────────────────
    scc_depth: dict[str, int] = {}
    queue: deque[str] = deque()
    for root in sorted(scc_members.keys(), key=lambda r: r.zfill(20)):
        if indegree[root] == 0:
            scc_depth[root] = 0
            queue.append(root)

    while queue:
        src = queue.popleft()
        for dst in sorted(scc_adj.get(src, set()), key=lambda r: r.zfill(20)):
            new_depth = scc_depth[src] + 1
            if new_depth > scc_depth.get(dst, -1):
                scc_depth[dst] = new_depth
            indegree[dst] -= 1
            if indegree[dst] == 0:
                queue.append(dst)

    # ── Expand SCC depth to individual nodes ─────────────────────────
    result: dict[str, int] = {}
    for root, members in scc_members.items():
        depth = scc_depth.get(root, 0)
        for uid in members:
            result[uid] = depth

    # ── Soft totality: guarantee every uid has a layer ────────────────
    missed: list[str] = []
    for node in wf.nodes.values():
        if node.uid not in result:
            result.setdefault(node.uid, 0)
            missed.append(node.uid)

    if missed:
        logger.warning(
            "compute_layers: %d uid(s) not reached by SCC/longest-path walk; "
            "assigned layer 0: %s",
            len(missed),
            ", ".join(sorted(missed, key=lambda u: u.zfill(20))),
        )

    return result


# ---------------------------------------------------------------------------
# Iterative Tarjan SCC (explicit stack, NO recursion)
# ---------------------------------------------------------------------------


def _tarjan_scc_iterative(
    uid_neighbors: dict[str, list[str]],
    all_uids: list[str],
) -> dict[str, str]:
    """Return ``{uid: scc_root, ...}`` for every uid in *all_uids*.

    ``scc_root`` is the lexicographically smallest ``uid.zfill(20)`` member
    of the strongly-connected component.
    """
    index_counter = 0
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    scc_root: dict[str, str] = {}

    # State for each node in the iterative DFS.
    # 0 = unvisited, 1 = entering, 2 = processing children, 3 = done
    state: dict[str, int] = {uid: 0 for uid in all_uids}
    # Per-node iterator over neighbours.
    iterators: dict[str, Any] = {}
    # The DFS call stack (list of uids, in push order).
    call_stack: list[str] = []

    for start_uid in sorted(all_uids, key=lambda u: u.zfill(20)):
        if state[start_uid] != 0:
            continue

        # Push start node.
        call_stack.append(start_uid)
        state[start_uid] = 1
        index_counter += 1
        index[start_uid] = index_counter
        lowlink[start_uid] = index_counter
        stack.append(start_uid)
        on_stack[start_uid] = True
        iterators[start_uid] = iter(
            uid_neighbors.get(start_uid, [])
        )

        while call_stack:
            uid = call_stack[-1]
            if state[uid] == 1:
                # Just entered — move to processing children.
                state[uid] = 2

            if state[uid] == 2:
                # Process next child.
                try:
                    neighbor = next(iterators[uid])
                except StopIteration:
                    # All children processed.
                    state[uid] = 3
                    continue

                if state[neighbor] == 0:
                    # Unvisited child — push it.
                    call_stack.append(neighbor)
                    state[neighbor] = 1
                    index_counter += 1
                    index[neighbor] = index_counter
                    lowlink[neighbor] = index_counter
                    stack.append(neighbor)
                    on_stack[neighbor] = True
                    iterators[neighbor] = iter(
                        uid_neighbors.get(neighbor, [])
                    )
                elif on_stack.get(neighbor, False):
                    # Back edge — update lowlink.
                    if index[neighbor] < lowlink[uid]:
                        lowlink[uid] = index[neighbor]
                continue

            if state[uid] == 3:
                call_stack.pop()
                # After returning from child, update lowlink.
                if call_stack:
                    parent = call_stack[-1]
                    if lowlink[uid] < lowlink[parent]:
                        lowlink[parent] = lowlink[uid]

                # If uid is SCC root, pop component.
                if lowlink[uid] == index[uid]:
                    component: list[str] = []
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        component.append(w)
                        if w == uid:
                            break
                    # SCC root is lexicographically smallest uid.zfill(20)
                    root = min(component, key=lambda u: u.zfill(20))
                    for member in component:
                        scc_root[member] = root

    return scc_root
