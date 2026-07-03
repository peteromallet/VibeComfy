"""Reconcile a current VibeWorkflow against a prior layout store.

``reconcile`` is a pure function — it never touches the filesystem.  The caller
(CLI handler or test fixture) owns loading the store envelope (via ``read_store``,
``--from``, or a sidecar).

Stage 1 matching strategy: exact uid match.  A uid present in both the current
workflow and ``prior_store["entries"]`` is matched and its furniture is carried
verbatim.

Stage 2 matching strategy: legacy structural-hash bridge.  For every current node
whose uid is empty (pre-uid files), a SHA-256 hash of its structural signature is
computed via ``legacy_hash`` and looked up in ``prior_store["entries"]``.  On a hit
a fresh uid is minted via ``mint_local_uid``, assigned to the IR node, and the entry
is moved from ``unmatched_legacy`` to ``matched``/``bridge_minted``.

Stage 3 matching strategy: stable bipartite assignment for hash collisions.  When
multiple current uid-less nodes share the same ``legacy_hash``, and multiple prior
store entries carry a ``_legacy_hash`` annotation matching that value, a min-cost
bipartite assignment minimising Σ|pos delta| (Euclidean) is run.  Tiebreaks use the
Kahn topological rank from ``compute_layers``.  This ensures twin/cloned nodes are
assigned to their nearest prior positions without scatter or swap.

Stage 4 matching strategy: subgraph inner-node preserve.  For each UUID-typed
subgraph container node in the current workflow, a ``content_hash`` is derived from
its visible definition (class_type + inputs schema + ver property).  The prior_store
``definitions`` key is searched for an entry keyed by ``<subgraph_name>:<content_hash>``.

- **Hit** (same hash): inner node furniture is carried verbatim from
  ``definitions[key]["inner_entries"]`` into ``matched`` using scoped UIDs of the form
  ``<subgraph_name>:<content_hash>:<inner_source_id>`` (M2 K5 lock key scheme).
- **Miss** (hash changed or no prior entry): the subgraph name is added to
  ``definition_relayout``.  If the prior store carried a bounding box for an earlier
  version, that box is recorded in ``definition_prior_bounding`` so the layout engine
  can place fresh inner nodes inside it; the fallback to M4 clean placement is
  indicated by an absent key.

``legacy_hash`` is rank-free — layer/position information is intentionally excluded
so the same file hashes identically across layout changes.
"""
from __future__ import annotations

import hashlib
import itertools
import re as _re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from vibecomfy.porting.layout.layering import compute_layers
from vibecomfy.identity.uid import mint_local_uid

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

# UUID pattern for subgraph container nodes (ComfyUI opaque subgraph type).
_UUID_RE = _re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    _re.IGNORECASE,
)


@dataclass
class ReconcileResult:
    """Result of reconciling a current workflow against a prior layout store."""

    # uid → verbatim furniture entry from prior_store["entries"] for uid-matched nodes
    matched: dict[str, dict[str, Any]]
    # uids in current_wf but absent from prior_store (newly added nodes)
    new: list[str]
    # uids in prior_store but absent from current_wf (deleted nodes)
    removed: list[str]
    # virtual wires from prior_store with at least one endpoint uid in removed
    degraded_virtual_wires: list[dict[str, Any]]
    # newly minted bridge entries (empty in stage 1; populated by later stages)
    bridge_minted: list[dict[str, Any]] = field(default_factory=list)
    # prior_store entry uids that failed uid-exact matching (equals removed in stage 1)
    unmatched_legacy: list[str] = field(default_factory=list)
    # subgraph names (class_type UUID) whose content_hash changed — inner nodes need
    # fresh layout (stage 4 miss path).
    definition_relayout: list[str] = field(default_factory=list)
    # subgraph_name → prior bounding box [x, y, w, h] for definition_relayout entries
    # that had a prior box; absent key → M4 clean placement fallback.
    definition_prior_bounding: dict[str, list[float]] = field(default_factory=dict)


@dataclass
class ContentEdits:
    """What happened to node content between the prior and current workflow."""
    preserved: list[str]       # matched uids with zero field delta
    edited: list[str]          # matched uids with ≥1 field delta
    new_auto_placed: list[str] # uids in new (engine-placed)
    removed: list[str]         # uids absent from current wf (deleted)
    virtual_wires_degraded: list[dict[str, Any]]  # degraded virtual wire descriptors
    removed_named: list[dict[str, str]] = field(default_factory=list)
    stripped_helpers: list[str] = field(default_factory=list)


@dataclass
class IdentityStabilization:
    """Identity bookkeeping events — NOT content changes."""
    bridge_minted: list[dict[str, Any]]  # legacy-hash bridge entries
    unmatched_legacy: list[str]          # store keys that couldn't be matched
    definition_relayout: list[str]       # subgraph names needing fresh inner layout


@dataclass
class ChangeReport:
    """Typed summary of what changed between a prior layout store and the current emit.

    ``content_edits`` covers only node *content* (fields, edges, binding) changes
    and geometry events visible to the user.  ``identity_stabilization`` covers
    internal bookkeeping (uid bridging, unmatched entries, subgraph relayout) that
    does NOT imply the user edited a node.
    """
    content_edits: ContentEdits
    identity_stabilization: IdentityStabilization


def build_change_report(
    reconcile_result: "ReconcileResult",
    field_delta: "dict[str, dict[str, tuple]]",
    prior_store_entries: "dict[str, dict] | None" = None,
) -> "ChangeReport":
    """Build a :class:`ChangeReport` from a reconcile result and field delta.

    Parameters
    ----------
    reconcile_result:
        Result of :func:`reconcile`.
    field_delta:
        Output of ``compute_field_delta`` — ``{uid: {field: (old, new)}}`` for
        nodes whose content changed since ingest.  Pass ``{}`` when no snapshot
        is available (all matched nodes are treated as preserved).
    prior_store_entries:
        Prior store ``entries`` dict (keyed by uid).  When supplied, each
        removed uid is annotated with its class_type from the prior entry
        (looked up via ``properties["Node name for S&R"]``).  Optional;
        ``removed_named`` stays empty when ``None``.
    """
    matched_uids = set(reconcile_result.matched)
    edited_uids = matched_uids & set(field_delta)
    preserved_uids = matched_uids - edited_uids

    # ── Build removed_named when prior entries are available ──────────────
    removed_named: list[dict[str, str]] = []
    if prior_store_entries:
        for uid in reconcile_result.removed:
            entry = prior_store_entries.get(uid) or {}
            # Prefer an explicit class_type key; fall back to the litegraph
            # "Node name for S&R" property when the entry carries properties.
            ct = entry.get("class_type", "")
            if not ct:
                props = entry.get("properties", {}) or {}
                ct = props.get("Node name for S&R", "") if isinstance(props, dict) else ""
            removed_named.append({"uid": uid, "class_type": ct or "unknown"})

    return ChangeReport(
        content_edits=ContentEdits(
            preserved=sorted(preserved_uids),
            edited=sorted(edited_uids),
            new_auto_placed=list(reconcile_result.new),
            removed=list(reconcile_result.removed),
            virtual_wires_degraded=list(reconcile_result.degraded_virtual_wires),
            removed_named=removed_named,
        ),
        identity_stabilization=IdentityStabilization(
            bridge_minted=list(reconcile_result.bridge_minted),
            unmatched_legacy=list(reconcile_result.unmatched_legacy),
            definition_relayout=list(reconcile_result.definition_relayout),
        ),
    )


# ---------------------------------------------------------------------------
# Legacy structural-hash bridge (stage 2)
# ---------------------------------------------------------------------------


def legacy_hash(
    node_id: str,
    wf: "VibeWorkflow",
    _cache: dict[str, str] | None = None,
) -> str:
    """Return the SHA-256 structural hash for *node_id* in *wf*.

    The hash covers, in canonical order:

    - ``class_type``
    - Sorted incoming ``(peer_ref, src_slot)`` tuples
    - Sorted ``(field, repr(value))`` widget/input scalar pairs
    - Sorted ``(public_input_name, bound_field)`` public-input bindings

    ``peer_ref`` is the peer node's uid when it is non-empty; otherwise the
    peer's own ``legacy_hash`` is used (recursive, bottom-up, cycle-safe via
    ``"__cycle__"`` sentinel that does not embed the peer node_id).

    Outgoing edges are intentionally excluded: including them creates circular
    hash dependencies for any pair of connected uid-less nodes, making the hash
    order-dependent and defeating the structural-identity goal.  Incoming edges
    alone fully capture a node's position in the upstream graph.  Rank/position
    information is excluded so the hash is layout-invariant.
    """
    if _cache is None:
        _cache = {}
    return _compute_hash(node_id, wf, _cache, frozenset())


def _peer_ref(
    peer_id: str,
    wf: "VibeWorkflow",
    cache: dict[str, str],
    visiting: frozenset[str],
) -> str:
    """Return uid if non-empty, else legacy_hash, for *peer_id*."""
    peer = wf.nodes.get(peer_id)
    if peer is None:
        return peer_id  # orphan reference — use raw id as opaque token
    if peer.uid:
        return peer.uid
    if peer_id in visiting:
        # Use a fixed sentinel that does NOT embed peer_id so the hash is
        # independent of numeric node_id assignments (rank-free invariant).
        return "__cycle__"
    return _compute_hash(peer_id, wf, cache, visiting)


def _compute_hash(
    node_id: str,
    wf: "VibeWorkflow",
    cache: dict[str, str],
    visiting: frozenset[str],
) -> str:
    if node_id in cache:
        return cache[node_id]

    node = wf.nodes.get(node_id)
    if node is None:
        h = hashlib.sha256(f"__missing__{node_id}".encode()).hexdigest()
        cache[node_id] = h
        return h

    visiting = visiting | {node_id}

    # Incoming edges: (peer_ref, src_slot)
    # Outgoing edges are intentionally excluded — see legacy_hash docstring.
    incoming: list[tuple[str, str]] = []
    for edge in wf.edges:
        if edge.to_node == node_id:
            p = _peer_ref(edge.from_node, wf, cache, visiting)
            incoming.append((p, edge.from_output))
    incoming.sort()

    # Scalar widget/input values (links are already in edges, not in inputs/widgets)
    scalar_values: list[tuple[str, str]] = sorted(
        (k, repr(v)) for k, v in {**node.inputs, **node.widgets}.items()
    )

    # Public input bindings
    public_bindings: list[tuple[str, str]] = sorted(
        (name, inp.field)
        for name, inp in wf.inputs.items()
        if inp.node_id == node_id
    )

    canonical = repr((
        node.class_type,
        tuple(incoming),
        tuple(scalar_values),
        tuple(public_bindings),
    ))
    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    cache[node_id] = h
    return h


# ---------------------------------------------------------------------------
# Stage 3 helpers: bipartite assignment for multi-candidate hash groups
# ---------------------------------------------------------------------------


def _pos_from_node(node: Any) -> tuple[float, float]:
    """Extract (x, y) from node.metadata['_ui']['pos'], fallback to (0, 0)."""
    ui = node.metadata.get("_ui", {}) if hasattr(node, "metadata") else {}
    pos = ui.get("pos", [0.0, 0.0])
    try:
        return (float(pos[0]), float(pos[1]))
    except (TypeError, IndexError, ValueError):
        return (0.0, 0.0)


def _euclidean(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return (dx * dx + dy * dy) ** 0.5


# Maximum safe size for exact exhaustive assignment and the corresponding
# permutation budget (8! = 40320).  Above these thresholds a deterministic
# greedy nearest-neighbour fallback is used to keep reconcile fast and
# predictable on large hash-collision groups.
_SAFE_K = 8
_SAFE_PERM_BUDGET = 40320  # math.perm(8, 8)


def _permutation_count(n: int, m: int) -> int:
    """Return the number of permutations for the n×m assignment problem.

    When *n* ≤ *m* this is P(m, n); otherwise P(n, m).  Returns 1 when the
    smaller dimension is 0 (no assignment to make).
    """
    k = min(n, m)
    if k == 0:
        return 1
    top = max(n, m)
    # Product of (top - i) for i in 0..k-1
    count = 1
    for i in range(k):
        count *= (top - i)
        if count > _SAFE_PERM_BUDGET:
            break
    return count


def _use_exhaustive(n: int, m: int) -> bool:
    """Return True when the (n,m) assignment is small enough for exact search."""
    k = min(n, m)
    if k > _SAFE_K:
        return False
    return _permutation_count(n, m) <= _SAFE_PERM_BUDGET


def _exhaustive_assign(
    n: int,
    m: int,
    costs: list[list[float]],
    c_layers: list[int],
) -> list[tuple[int, int]]:
    """Exact min-cost bipartite assignment via permutation enumeration.

    Only called when the search space has been confirmed safe by
    :func:`_use_exhaustive`.
    """
    best_cost: float = float("inf")
    best_secondary: int = 0
    best_assignment: list[tuple[int, int]] = []

    if n <= m:
        for perm in itertools.permutations(range(m), n):
            cost = sum(costs[i][perm[i]] for i in range(n))
            secondary = sum(c_layers[i] * perm[i] for i in range(n))
            if cost < best_cost or (cost == best_cost and secondary < best_secondary):
                best_cost = cost
                best_secondary = secondary
                best_assignment = [(i, perm[i]) for i in range(n)]
    else:
        for perm in itertools.permutations(range(n), m):
            cost = sum(costs[perm[j]][j] for j in range(m))
            secondary = sum(c_layers[perm[j]] * j for j in range(m))
            if cost < best_cost or (cost == best_cost and secondary < best_secondary):
                best_cost = cost
                best_secondary = secondary
                best_assignment = [(perm[j], j) for j in range(m)]

    return best_assignment


def _greedy_assign(
    n: int,
    m: int,
    costs: list[list[float]],
    c_layers: list[int],
) -> list[tuple[int, int]]:
    """Deterministic greedy nearest-neighbour fallback assignment.

    When the search space is too large for exact enumeration (see
    :func:`_use_exhaustive`), this function produces a stable, repeatable
    assignment in O(n·m·min(n,m)) time.

    Strategy
    --------
    * Sort current items by Kahn layer rank (lower = upstream first), with
      index as a secondary tiebreak for determinism.
    * Process each current item in that order and assign it to the *nearest
      unmatched* prior entry, using the same Euclidean+cost tiebreak as the
      exact path.
    * When there are more prior than current entries the direction is the same
      (assign each current to a distinct prior).  When there are more current
      than prior entries the roles are reversed: sort prior entries stably and
      assign each to the nearest unmatched current.

    Returns a list of ``(current_index, prior_index)`` pairs.
    """
    k = min(n, m)
    if k == 0:
        return []

    assignment: list[tuple[int, int]] = []

    if n <= m:
        # Assign each current to a distinct prior.
        order = sorted(range(n), key=lambda i: (c_layers[i], i))
        used_prior: set[int] = set()
        for ci in order:
            best_j = -1
            best_cost = float("inf")
            best_secondary = 0
            for j in range(m):
                if j in used_prior:
                    continue
                cost = costs[ci][j]
                secondary = c_layers[ci] * j
                if cost < best_cost or (cost == best_cost and secondary < best_secondary):
                    best_cost = cost
                    best_secondary = secondary
                    best_j = j
            if best_j >= 0:
                used_prior.add(best_j)
                assignment.append((ci, best_j))
    else:
        # More current than prior — assign each prior to a distinct current.
        order = sorted(range(m), key=lambda j: j)  # stable: index order
        used_current: set[int] = set()
        for pj in order:
            best_i = -1
            best_cost = float("inf")
            best_secondary = 0
            for i in range(n):
                if i in used_current:
                    continue
                cost = costs[i][pj]
                secondary = c_layers[i] * pj
                if cost < best_cost or (cost == best_cost and secondary < best_secondary):
                    best_cost = cost
                    best_secondary = secondary
                    best_i = i
            if best_i >= 0:
                used_current.add(best_i)
                assignment.append((best_i, pj))

    return assignment


def _min_cost_assign(
    current_items: list[tuple[str, Any]],   # (node_id, node)
    prior_items: list[tuple[str, dict]],     # (store_uid, entry)
    layers: dict[str, int],
) -> list[tuple[int, int]]:
    """Return min-cost assignment of current nodes to prior store entries.

    Minimises Σ Euclidean(current_pos, prior_pos).  Tiebreaks prefer
    assignments where lower-layer (upstream) current nodes are matched to
    lower-ranked prior entries (sorted by store uid).

    Uses exact exhaustive search for small groups (≤ *SAFE_K* items and
    within the safe permutation budget) and falls back to a deterministic
    greedy nearest-neighbour algorithm for larger groups to keep reconcile
    fast and predictable.

    Returns a list of ``(current_index, prior_index)`` pairs covering
    ``min(len(current_items), len(prior_items))`` nodes.
    """
    n = len(current_items)
    m = len(prior_items)
    k = min(n, m)
    if k == 0:
        return []

    c_pos = [_pos_from_node(node) for _, node in current_items]
    p_pos: list[tuple[float, float]] = []
    for _, entry in prior_items:
        raw = entry.get("pos", [0.0, 0.0])
        try:
            p_pos.append((float(raw[0]), float(raw[1])))
        except (TypeError, IndexError, ValueError):
            p_pos.append((0.0, 0.0))

    costs = [[_euclidean(c_pos[i], p_pos[j]) for j in range(m)] for i in range(n)]

    # Kahn-rank tiebreak weights: lower layer = lower weight = preferred earlier
    c_layers = [layers.get(node.uid or nid, 0) for nid, node in current_items]

    if _use_exhaustive(n, m):
        return _exhaustive_assign(n, m, costs, c_layers)
    else:
        return _greedy_assign(n, m, costs, c_layers)


# ---------------------------------------------------------------------------
# Stage 4 helpers: subgraph inner-node preserve (content-hash keying)
# ---------------------------------------------------------------------------


def _is_subgraph_type(class_type: str) -> bool:
    """Return True if *class_type* is a UUID subgraph container node."""
    return bool(_UUID_RE.match(class_type))


def _subgraph_content_hash(node: Any) -> str:
    """Return a short content hash for a subgraph container node.

    Derived from the node's visible definition: class_type, sorted input
    names/types (from ``_ui.inputs``), and the ``ver`` property.  Position
    and size are excluded so the hash is layout-invariant.
    """
    ui = node.metadata.get("_ui", {}) if hasattr(node, "metadata") else {}
    ui = ui if isinstance(ui, dict) else {}
    props = ui.get("properties", {}) or {}
    ver = props.get("ver", "") if isinstance(props, dict) else ""
    raw_inputs = ui.get("inputs") or []
    inputs_schema: list[tuple[str, str]] = sorted(
        (str(inp.get("name", "")), str(inp.get("type", "")))
        for inp in raw_inputs
        if isinstance(inp, dict)
    )
    canonical = repr((node.class_type, tuple(inputs_schema), ver))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def nearest_wired_neighbor_uid(
    new_node_id: str,
    wf: "VibeWorkflow",
    matched: dict[str, Any] | set[str] | list[str],
) -> str | None:
    """Return the matched-uid of the nearest BFS neighbor of *new_node_id*.

    Walks the undirected IR edge graph starting from *new_node_id* and returns
    the first matched-uid encountered (uid-keyed in ``matched``).  When several
    matched neighbors live at the same BFS distance, ties are broken by lowest
    Kahn topological rank from :func:`compute_layers` (uid lex order as a
    secondary tiebreak).  Returns ``None`` if no matched neighbor is reachable.

    *matched* may be a dict (e.g. ``ReconcileResult.matched``), a set, or a
    list — only its membership is used.
    """
    from collections import defaultdict
    matched_uids: set[str] = set(matched) if not isinstance(matched, set) else matched

    adj: dict[str, set[str]] = defaultdict(set)
    for edge in wf.edges:
        adj[edge.from_node].add(edge.to_node)
        adj[edge.to_node].add(edge.from_node)

    def _key_for(node_id: str) -> str:
        peer = wf.nodes.get(node_id)
        return (peer.uid or node_id) if peer is not None else node_id

    visited: set[str] = {new_node_id}
    frontier: list[str] = [new_node_id]
    layers_cache: dict[str, int] | None = None
    while frontier:
        next_frontier: list[str] = []
        candidates: list[str] = []
        for nid in frontier:
            for peer_id in adj.get(nid, ()):
                if peer_id in visited:
                    continue
                visited.add(peer_id)
                peer_key = _key_for(peer_id)
                if peer_key in matched_uids:
                    candidates.append(peer_key)
                else:
                    next_frontier.append(peer_id)
        if candidates:
            if layers_cache is None:
                layers_cache = compute_layers(wf)
            candidates.sort(key=lambda u: (layers_cache.get(u, 0), u))
            return candidates[0]
        frontier = next_frontier
    return None


def inner_node_uid(subgraph_name: str, content_hash: str, inner_id: str) -> str:
    """Return the scoped UID for an inner node.

    Format: ``<subgraph_name>:<content_hash>:<inner_source_id>``
    This is the M2 K5 lock key scheme for inner nodes.
    """
    return f"{subgraph_name}:{content_hash}:{inner_id}"


def reconcile(
    current_wf: "VibeWorkflow",
    prior_store: dict[str, Any],
) -> ReconcileResult:
    """Reconcile *current_wf* against a prior layout store envelope.

    Runs two matching stages in sequence:

    **Stage 1 — uid-exact match.**  Every current node uid present in
    ``entries`` is matched and its furniture carried verbatim.

    **Stage 2 — legacy-hash bridge.**  For each remaining current node whose
    uid is empty (pre-uid files), a structural hash is computed via
    :func:`legacy_hash` and looked up in ``entries``.  On a hit a fresh uid is
    minted via :func:`~vibecomfy.identity.uid.mint_local_uid`, assigned to the
    IR node in-place, and the entry migrates from ``unmatched_legacy`` to
    ``matched``/``bridge_minted``.

    Parameters
    ----------
    current_wf:
        The live ``VibeWorkflow`` to reconcile.  Stage 2 mutates
        ``node.uid`` in-place for bridge-minted nodes; all other state is
        read-only.
    prior_store:
        Full store envelope.  Expected keys (all optional — missing keys
        default to empty):

        ``entries``
            ``{key: {pos, size, mode, flags, color, properties, group}}``
            keyed by ``vibecomfy_uid`` (uid-bearing workflows) or
            ``legacy_hash`` (pre-uid workflows).
        ``groups``
            List of group definitions from the prior save.
        ``extra``
            Arbitrary extra metadata preserved across saves.
        ``definitions``
            Node definition overrides or annotations.
        ``virtual_wires``
            List of virtual wire descriptors
            (``{source: uid, target: uid, ...}``).

    Returns
    -------
    :class:`ReconcileResult` with:

    ``matched``
        key → verbatim furniture for all uid-matched (stage 1) and
        bridge-matched (stage 2) nodes.  The key for bridge-minted nodes is
        the freshly minted uid, not the legacy hash.
    ``new``
        Sorted list of current-node keys absent from the store after both
        stages.
    ``removed``
        Sorted list of store keys absent from *current_wf* after both stages.
    ``degraded_virtual_wires``
        Virtual wires whose ``source`` or ``target`` appears in ``removed``.
    ``bridge_minted``
        One entry per stage-2 match: ``{uid, legacy_hash}``.
    ``unmatched_legacy``
        Store keys that could not be matched by any method.
    """
    entries: dict[str, dict[str, Any]] = prior_store.get("entries", {})
    _raw_vw = prior_store.get("virtual_wires", [])
    # The store encodes virtual_wires as a dict keyed by uid (store_from_ui_json)
    # or a list of {source, target} descriptors.  Normalise to the list form here.
    if isinstance(_raw_vw, dict):
        virtual_wires: list[dict[str, Any]] = []
        for _vw_uid, _vw_entry in _raw_vw.items():
            if isinstance(_vw_entry, dict):
                _ep = _vw_entry.get("endpoints")
                if isinstance(_ep, list):
                    for _ep_uid in _ep:
                        virtual_wires.append({"source": _vw_uid, "target": str(_ep_uid)})
    elif isinstance(_raw_vw, list):
        virtual_wires = _raw_vw
    else:
        virtual_wires = []

    # Build current uid set from the live IR.
    current_uids: set[str] = {
        (node.uid if node.uid else node_id)
        for node_id, node in current_wf.nodes.items()
    }
    store_uids: set[str] = set(entries)

    # ── Stage 1: exact uid match ──────────────────────────────────────────────
    matched_uids = current_uids & store_uids
    new_set: set[str] = current_uids - store_uids
    unmatched_store: set[str] = store_uids - current_uids

    # Carry furniture verbatim for all uid-matched nodes.
    matched: dict[str, dict[str, Any]] = {uid: dict(entries[uid]) for uid in matched_uids}

    bridge_minted: list[dict[str, Any]] = []

    # ── Stage 2: legacy structural-hash bridge for uid-less nodes ────────────
    # Identify current nodes with empty uid that are not yet matched.
    uid_less: list[tuple[str, Any]] = [
        (node_id, node)
        for node_id, node in current_wf.nodes.items()
        if not node.uid and node_id in new_set
    ]

    if uid_less and unmatched_store:
        hash_cache: dict[str, str] = {}
        for node_id, node in uid_less:
            h = _compute_hash(node_id, current_wf, hash_cache, frozenset())
            if h not in unmatched_store:
                continue
            # Bridge match: mint a fresh uid, persist to IR, carry furniture.
            fresh_uid = mint_local_uid(node.metadata.get("_ui"), node_id)
            node.uid = fresh_uid
            new_entry = dict(entries[h])
            new_entry["_legacy_hash"] = h  # annotate so stage 3 can build reverse index
            matched[fresh_uid] = new_entry
            bridge_minted.append({"uid": fresh_uid, "legacy_hash": h})
            new_set.discard(node_id)
            unmatched_store.discard(h)

    # ── Stage 3: bipartite assignment for multi-candidate same-hash groups ────
    # Build reverse index: hash → [(store_uid, entry)] for entries annotated
    # with _legacy_hash (set by a prior stage-2 bridge-minting run).
    hash_to_prior: dict[str, list[tuple[str, dict]]] = {}
    for store_uid in unmatched_store:
        entry = entries.get(store_uid, {})
        lh = entry.get("_legacy_hash")
        if lh:
            hash_to_prior.setdefault(lh, []).append((store_uid, entry))

    if hash_to_prior:
        # Collect remaining uid-less current nodes still in new_set.
        uid_less_s3: list[tuple[str, Any]] = [
            (node_id, node)
            for node_id, node in current_wf.nodes.items()
            if not node.uid and node_id in new_set
        ]

        if uid_less_s3:
            # Temporarily assign node_id as uid so compute_layers works.
            _tmp_restored: list[tuple[Any, str]] = []
            for node_id, node in uid_less_s3:
                if not node.uid:
                    _tmp_restored.append((node, node.uid))
                    node.uid = node_id
            try:
                layers = compute_layers(current_wf)
            finally:
                for node, old_uid in _tmp_restored:
                    node.uid = old_uid

            hash_cache_s3: dict[str, str] = {}
            hash_to_current: dict[str, list[tuple[str, Any]]] = {}
            for node_id, node in uid_less_s3:
                h = _compute_hash(node_id, current_wf, hash_cache_s3, frozenset())
                if h in hash_to_prior:
                    hash_to_current.setdefault(h, []).append((node_id, node))

            for h, current_group in hash_to_current.items():
                prior_group = hash_to_prior.get(h, [])
                if not prior_group:
                    continue

                assignment = _min_cost_assign(current_group, prior_group, layers)

                for c_idx, p_idx in assignment:
                    node_id, node = current_group[c_idx]
                    store_uid, entry = prior_group[p_idx]

                    fresh_uid = mint_local_uid(node.metadata.get("_ui"), node_id)
                    node.uid = fresh_uid
                    new_entry = dict(entry)
                    new_entry["_legacy_hash"] = h
                    matched[fresh_uid] = new_entry
                    bridge_minted.append({"uid": fresh_uid, "legacy_hash": h})
                    new_set.discard(node_id)
                    unmatched_store.discard(store_uid)

    removed_list = sorted(unmatched_store)
    removed_set = set(removed_list)

    # Degrade virtual wires whose source or target uid no longer exists.
    degraded = [
        vw for vw in virtual_wires
        if vw.get("source") in removed_set or vw.get("target") in removed_set
    ]

    # ── Stage 4: subgraph inner-node definition matching ─────────────────────
    # For each UUID-typed subgraph container in the current workflow, look up
    # its inner node furniture in prior_store["definitions"].  Inner nodes are
    # keyed by their scoped UID (<subgraph_name>:<content_hash>:<inner_id>).
    # On a content_hash miss the subgraph is added to definition_relayout and
    # any available prior bounding box is recorded for layout fallback.
    defs: dict[str, Any] = prior_store.get("definitions", {})
    definition_relayout: list[str] = []
    definition_prior_bounding: dict[str, list[float]] = {}

    if defs:
        for _node_id, node in current_wf.nodes.items():
            if not _is_subgraph_type(node.class_type):
                continue
            current_hash = _subgraph_content_hash(node)
            def_key = f"{node.class_type}:{current_hash}"
            if def_key in defs:
                # Hit: carry inner node furniture verbatim.
                prior_def = defs[def_key]
                for inner_id, inner_entry in (prior_def.get("inner_entries") or {}).items():
                    scoped_uid = inner_node_uid(node.class_type, current_hash, str(inner_id))
                    matched[scoped_uid] = dict(inner_entry)
            else:
                # Miss: content changed or never seen.  Find prior bounding box
                # for any earlier version of this subgraph so the layout engine
                # can place fresh inner nodes inside it (M4 fallback if absent).
                definition_relayout.append(node.class_type)
                for k, v in defs.items():
                    if isinstance(k, str) and k.startswith(f"{node.class_type}:"):
                        bounding = (v or {}).get("bounding")
                        if isinstance(bounding, (list, tuple)) and len(bounding) >= 4:
                            definition_prior_bounding[node.class_type] = list(bounding)
                        break

    return ReconcileResult(
        matched=matched,
        new=sorted(new_set),
        removed=removed_list,
        degraded_virtual_wires=degraded,
        bridge_minted=bridge_minted,
        unmatched_legacy=removed_list,
        definition_relayout=definition_relayout,
        definition_prior_bounding=definition_prior_bounding,
    )
