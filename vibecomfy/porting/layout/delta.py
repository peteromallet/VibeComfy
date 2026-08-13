"""Field-level delta computation between an ingest snapshot and the current IR.

``compute_field_delta`` compares a stored ``_ingest_snapshot`` (captured at
ingest time by ``vibecomfy.ingest.snapshot.capture_ingest_snapshot``) against
the live IR state of a ``VibeWorkflow``.

Ordinary field/link changes on nodes absent from *snapshot* (added after
ingest) are omitted from the result — downstream logic treats them as
``'snapshot-absent'``.  Resolution issues are the exception: they are always
surfaced so emission can fail closed before touching an unresolved endpoint.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from vibecomfy.porting.lowering import clone_uid

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

_SNAPSHOT_FIELDS = (
    "class_type",
    "widget_values_sig",
    "public_input_binding",
)

SemanticLink = tuple[str, str, str, str]
SemanticNode = tuple[str, str, str | None]
_SEMANTIC_HELPERS = frozenset({"SetNode", "GetNode", "Reroute"})

# Hard bound on the number of helper hops (Reroute/GetNode/SetNode) resolved in
# a single terminal-source walk.  Every hop is memoized, so a healthy graph
# resolves each helper at most once; this cap is a fail-closed backstop so the
# semantic traversal is bounded for any input, however pathological.
_MAX_SEMANTIC_WALK = 10_000


def canonical_semantic_link_set(
    nodes: Mapping[str, SemanticNode],
    links: Iterable[SemanticLink],
    *,
    consumer_uid_aliases: Mapping[str, str] | None = None,
) -> tuple[tuple[SemanticLink, ...], tuple[str, ...]]:
    """Return a deduplicated semantic link set and deterministic resolution issues.

    ``nodes`` maps graph-local node ids to ``(stable_uid, class_type,
    broadcast_name)``. ``links`` preserves both endpoint ports as
    ``(source_id, source_output, consumer_id, consumer_input)``. Set/Get and
    Reroute plumbing is resolved to its terminal source; loop-cloned consumer
    UIDs are collapsed to the source consumer UID. Ambiguous, missing, orphaned,
    or cyclic paths are reported instead of being silently discarded.
    """
    semantic, issues, _attribution = _canonical_semantic_link_set(
        nodes,
        links,
        consumer_uid_aliases=consumer_uid_aliases,
    )
    return semantic, issues


def _canonical_semantic_link_set(
    nodes: Mapping[str, SemanticNode],
    links: Iterable[SemanticLink],
    *,
    consumer_uid_aliases: Mapping[str, str] | None = None,
) -> tuple[tuple[SemanticLink, ...], tuple[str, ...], dict[str, frozenset[str]]]:
    """Resolution core: returns ``(links, issues, issue_attribution)``.

    ``issue_attribution`` maps each canonical consumer uid to the resolution
    issues that involve it: issues recorded while resolving one of the
    consumer's inbound edges plus issues that name one of its graph-local
    ids.  ``compute_field_delta`` uses this map so a single global issue
    never fans out into a per-node delta on every snapshot node.
    """
    aliases = {
        str(uid): str(canonical)
        for uid, canonical in (consumer_uid_aliases or {}).items()
    }
    normalized_nodes = {
        str(node_id): (str(spec[0]), str(spec[1]), spec[2])
        for node_id, spec in nodes.items()
    }
    link_rows = sorted(
        {
            (str(source), str(source_output), str(consumer), str(consumer_input))
            for source, source_output, consumer, consumer_input in links
        }
    )
    issues: set[str] = set()
    # canonical consumer uid -> resolution issues that involve it.
    attribution: dict[str, set[str]] = defaultdict(set)

    def record_issue(issue: str) -> None:
        if issue in issues:
            return
        issues.add(issue)

    uids: dict[str, str] = {}
    for node_id, (uid, _class_type, _channel) in sorted(
        normalized_nodes.items(), key=lambda item: (item[1][0], item[0])
    ):
        prior_id = uids.get(uid)
        if prior_id is not None and prior_id != node_id:
            record_issue(f"duplicate_uid:{uid}:{min(prior_id, node_id)}:{max(prior_id, node_id)}")
        else:
            uids[uid] = node_id

    inbound: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for source, source_output, consumer, consumer_input in link_rows:
        if source not in normalized_nodes:
            record_issue(f"unknown_source:{source}")
            consumer_spec = normalized_nodes.get(consumer)
            if consumer_spec is not None:
                attribution[
                    aliases.get(str(consumer_spec[0]), str(consumer_spec[0]))
                ].add(f"unknown_source:{source}")
        if consumer not in normalized_nodes:
            record_issue(f"unknown_consumer:{consumer}")
            # The consumer is ghost, but the SOURCE endpoint is known — the
            # issue belongs on the source's uid so it lands on a
            # snapshot-present fence target and refuses (B03 rework7).
            source_spec = normalized_nodes.get(source)
            if source_spec is not None:
                attribution[
                    aliases.get(str(source_spec[0]), str(source_spec[0]))
                ].add(f"unknown_consumer:{consumer}")
        # Keep the helper endpoint's input identity until ambiguity has been
        # decided.  Two edges from the same source/output into different
        # helper inputs are still two distinct candidates and must fail closed.
        inbound[consumer].append((source, source_output, consumer_input))

    setters_by_channel: dict[str, list[str]] = defaultdict(list)
    for node_id, (_uid, class_type, channel) in normalized_nodes.items():
        if class_type == "SetNode" and channel:
            setters_by_channel[str(channel)].append(node_id)

    # Iterative terminal-source resolution with memoization.
    #
    # Each helper hop (Reroute passthrough, GetNode→SetNode broadcast hop,
    # SetNode-as-source passthrough) follows exactly one candidate or fails
    # closed, so the walk is a simple chain.  The result of every visited
    # (node_id, output_port) key is cached,
    # making the whole traversal linear in the helper graph and immune to
    # repeated fan-out re-walks.  Re-entering a key that is still on the
    # current path means the graph is cyclic: the walk terminates immediately
    # and the path is reported via ``cyclic_path:`` (fail closed).  The hard
    # ``_MAX_SEMANTIC_WALK`` hop cap guarantees bounded time even for
    # adversarial inputs, so every call returns a deterministic verdict.
    # ``(result, issues)`` where ``issues`` are the resolution issues recorded
    # while first resolving that key (replayed on memo hits so every consuming
    # edge of a failed key is attributed the same fail-closed diagnostics).
    memo: dict[tuple[str, str], tuple[tuple[str, str] | None, frozenset[str]]] = {}
    in_progress: set[tuple[str, str]] = set()

    def terminal_source(
        node_id: str,
        output_port: str,
    ) -> tuple[tuple[str, str] | None, frozenset[str]]:
        start = (node_id, output_port)
        if start in memo:
            return memo[start]
        path: list[tuple[str, str]] = []
        current = start
        result: tuple[str, str] | None = None
        issues_for_key: frozenset[str] = frozenset()
        walk_issues: set[str] = set()

        def record_walk_issue(issue: str) -> None:
            # Global diagnostics dedupe by text, but every failed walk still
            # needs its own attribution even when another walk recorded the
            # same issue first.
            record_issue(issue)
            walk_issues.add(issue)

        while True:
            key = current
            if key in memo:
                result, issues_for_key = memo[key]
                break
            if key in in_progress:
                cycle_nodes = {
                    hop[0] for hop in path[path.index(key):]
                } | {key[0]}
                record_walk_issue(f"cyclic_path:{':'.join(sorted(cycle_nodes))}")
                result = None
                break
            spec = normalized_nodes.get(key[0])
            if spec is None:
                issue = f"unknown_source:{key[0]}"
                record_walk_issue(issue)
                result = None
                break
            uid, class_type, channel = spec
            if class_type not in _SEMANTIC_HELPERS:
                result = (uid, key[1])
                break
            if class_type == "Reroute":
                candidates = sorted(set(inbound.get(key[0], ())))
                if not candidates:
                    # A Reroute with no inbound terminal is opaque display
                    # plumbing: its outbound edge carries no resolvable source,
                    # so the helper degenerates to an opaque terminal at its
                    # own (uid, port).  This is a stable property of the graph,
                    # not a change — recording ``reroute_source_count:*:0``
                    # here fabricated a link delta on every downstream consumer
                    # of unchanged schema-less nodes (B03 rework6).  Two or
                    # more inbound candidates remain genuine ambiguity and fail
                    # closed below.
                    result = (uid, key[1])
                    break
                if len(candidates) != 1:
                    record_walk_issue(f"reroute_source_count:{key[0]}:{len(candidates)}")
                    result = None
                    break
                next_node, next_port, _target_input = candidates[0]
            elif class_type == "GetNode":
                if not channel:
                    record_walk_issue(f"broadcast_name_missing:{key[0]}")
                    result = None
                    break
                setters = sorted(set(setters_by_channel.get(str(channel), ())))
                if not setters:
                    # No SetNode backs this channel: the GetNode is an unbacked
                    # display device whose outbound value is opaque.  It
                    # degenerates to an opaque terminal at its own (uid, port)
                    # instead of fabricating ``broadcast_setter_count:*:0`` on
                    # unchanged consumers (B03 rework6).  Multiple setters for
                    # one channel remain genuine ambiguity and fail closed below.
                    result = (uid, key[1])
                    break
                if len(setters) != 1:
                    record_walk_issue(
                        f"broadcast_setter_count:{key[0]}:{channel}:{len(setters)}"
                    )
                    result = None
                    break
                setter_id = setters[0]
                candidates = sorted(set(inbound.get(setter_id, ())))
                if not candidates:
                    # The channel's sole SetNode has no inbound terminal: the
                    # setter itself is the opaque value source.  Same degenerate
                    # rule as the source-less SetNode-as-source case below.
                    setter_uid = normalized_nodes[setter_id][0]
                    result = (setter_uid, key[1])
                    break
                if len(candidates) != 1:
                    record_walk_issue(f"broadcast_source_count:{setter_id}:{len(candidates)}")
                    result = None
                    break
                next_node, next_port, _target_input = candidates[0]
            else:  # SetNode used as a source resolves passthrough through its
                # unique inbound terminal, exactly as the compiler resolves the
                # same case (_compile/_resolve.py:172).  A source-less SetNode
                # (zero inbound) degenerates to an opaque terminal at its own
                # uid (B03 rework6); two or more inbound candidates are
                # genuinely ambiguous and fail closed below.
                candidates = sorted(set(inbound.get(key[0], ())))
                if not candidates:
                    result = (uid, key[1])
                    break
                if len(candidates) != 1:
                    record_walk_issue(f"setnode_as_source:{key[0]}:{len(candidates)}")
                    result = None
                    break
                next_node, next_port, _target_input = candidates[0]
            in_progress.add(key)
            path.append(key)
            if len(path) > _MAX_SEMANTIC_WALK:
                record_walk_issue(f"semantic_walk_limit:{key[0]}")
                result = None
                break
            current = (next_node, next_port)
        if result is None:
            # A failure may have been replayed from a memoized key; either way
            # the issues that blocked this resolution belong to every consumer
            # of it, so the full set is cached on each visited key.
            issues_for_key = frozenset(walk_issues) | issues_for_key
        for visited_key in path:
            memo[visited_key] = (result, issues_for_key)
            in_progress.discard(visited_key)
        memo[start] = (result, issues_for_key)
        return result, issues_for_key

    semantic: set[SemanticLink] = set()
    for source, source_output, consumer, consumer_input in link_rows:
        consumer_spec = normalized_nodes.get(consumer)
        if consumer_spec is None:
            continue
        consumer_uid, consumer_class_type, _channel = consumer_spec
        if consumer_class_type in {"SetNode", "Reroute"}:
            continue
        consumer_key = aliases.get(consumer_uid, consumer_uid)
        if consumer_class_type == "GetNode":
            if consumer_input == "broadcast_out":
                # An edge entering a GetNode through its channel input is a
                # display edge: the compiler resolves the GetNode's outbound
                # through its channel and removes the helper-touching display
                # edge (_compile/_resolve.py:136). Resolving the channel here
                # means a resolvable chain never emits helper_input_unsupported;
                # genuinely unresolvable channels (missing name, non-unique
                # setter, non-unique setter inbound, cycles) still fail closed
                # with the specific issue recorded by the walk.
                _terminal, term_issues = terminal_source(consumer, source_output)
                attribution[consumer_key].update(term_issues)
                continue
            record_issue(f"helper_input_unsupported:{consumer}")
            attribution[consumer_key].add(f"helper_input_unsupported:{consumer}")
            continue
        terminal, term_issues = terminal_source(source, source_output)
        attribution[consumer_key].update(term_issues)
        if terminal is None:
            continue
        semantic.add(
            (
                terminal[0],
                terminal[1],
                aliases.get(consumer_uid, consumer_uid),
                consumer_input,
            )
        )

    # Named-node attribution: an issue that names a graph-local node also
    # belongs on that node's own uid, even when the failing walk was first
    # observed from a different consumer (memoized resolution).
    for issue in issues:
        for mentioned_uid in _issue_mentioned_uids(issue, normalized_nodes):
            attribution[mentioned_uid].add(issue)

    return (
        tuple(sorted(semantic)),
        tuple(sorted(issues)),
        {uid: frozenset(issue_set) for uid, issue_set in attribution.items()},
    )


def _issue_mentioned_uids(
    issue: str,
    nodes: Mapping[str, SemanticNode],
) -> frozenset[str]:
    """Map the graph-local node ids named by a resolution issue to stable uids.

    ``unknown_source``/``unknown_consumer`` name ghost ids absent from
    ``nodes`` by construction; they are attributed at record time instead of
    here — ``unknown_source`` to the consuming edge's uid and
    ``unknown_consumer`` to the known source's uid (B03 rework7).
    """
    code, _, rest = issue.partition(":")
    parts = rest.split(":") if rest else []
    if code == "duplicate_uid" and len(parts) >= 3:
        # duplicate_uid:<uid>:<id_a>:<id_b>
        mentioned = {parts[0]}
        for node_id in parts[1:3]:
            spec = nodes.get(node_id)
            mentioned.add(spec[0] if spec else node_id)
        return frozenset(mentioned)
    if code == "cyclic_path":
        node_ids = parts
    elif code in {"unknown_source", "unknown_consumer"} or not parts:
        return frozenset()
    else:
        node_ids = (parts[0],)
    mentioned: set[str] = set()
    for node_id in node_ids:
        spec = nodes.get(node_id)
        mentioned.add(spec[0] if spec else node_id)
    return frozenset(mentioned)


def _snapshot_channel(snapshot_entry: Mapping[str, Any]) -> str | None:
    for field_name, value_repr in snapshot_entry.get("widget_values_sig", ()):
        if str(field_name) not in {"widget_0", "name"}:
            continue
        try:
            value = ast.literal_eval(str(value_repr))
        except (SyntaxError, ValueError):
            value = value_repr
        if value is not None:
            return str(value)
    return None


def _snapshot_semantic_graph(
    snapshot: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, SemanticNode], list[SemanticLink]]:
    nodes = {
        str(uid): (
            str(uid),
            str(entry.get("class_type", "")),
            _snapshot_channel(entry),
        )
        for uid, entry in snapshot.items()
    }
    links: list[SemanticLink] = []
    for source_uid, entry in snapshot.items():
        for source_output, target in entry.get("outgoing_edge_sig", ()):
            target_uid, target_input = target
            links.append(
                (str(source_uid), str(source_output), str(target_uid), str(target_input))
            )
        for target_input, source in entry.get("incoming_edge_sig", ()):
            incoming_source_uid, source_output = source
            links.append(
                (
                    str(incoming_source_uid),
                    str(source_output),
                    str(source_uid),
                    str(target_input),
                )
            )
    # A partial snapshot deliberately omits some node records while retained
    # signatures may still name those peers. They remain valid opaque semantic
    # endpoints; only the live graph must resolve every graph-local node id.
    for source_uid, _source_output, target_uid, _target_input in links:
        nodes.setdefault(source_uid, (source_uid, "", None))
        nodes.setdefault(target_uid, (target_uid, "", None))
    return nodes, links


def _snapshot_consumer_uid_aliases(
    nodes: Mapping[str, SemanticNode],
    validated_live_aliases: Mapping[str, str],
) -> dict[str, str]:
    """Return only snapshot aliases corroborated by live lowering provenance.

    A clone-shaped UID is ordinary user data unless the live node carries a
    validated ``vibecomfy.lowering`` record whose ``clone_uid`` round-trip
    matches it.  Requiring that validated alias *and* the exact UID in the
    snapshot gives both sides independent evidence and prevents textual UID
    shape alone from fabricating snapshot topology.
    """
    snapshot_uids = {str(spec[0]) for spec in nodes.values()}
    return {
        str(uid): str(source_uid)
        for uid, source_uid in validated_live_aliases.items()
        if str(uid) in snapshot_uids
    }


def _workflow_semantic_graph(
    current_ir: "VibeWorkflow",
) -> tuple[dict[str, SemanticNode], list[SemanticLink], dict[str, str]]:
    nodes: dict[str, SemanticNode] = {}
    consumer_uid_aliases: dict[str, str] = {}
    for node_id, node in current_ir.nodes.items():
        channel = None
        if node.class_type in {"SetNode", "GetNode"}:
            value = node.inputs.get("widget_0", node.widgets.get("widget_0"))
            if value is None:
                value = node.inputs.get("name")
            if value is not None:
                channel = str(value)
        stable_uid = str(node.uid if node.uid else node_id)
        nodes[str(node_id)] = (
            stable_uid,
            str(node.class_type),
            channel,
        )
        lowering = node.metadata.get("vibecomfy.lowering")
        if isinstance(lowering, Mapping):
            source_uid = lowering.get("source_uid")
            loop_uid = lowering.get("loop_uid")
            iteration_index = lowering.get("iteration_index")
            if (
                isinstance(source_uid, str)
                and isinstance(loop_uid, str)
                and isinstance(iteration_index, int)
                and clone_uid(loop_uid, source_uid, iteration_index) == stable_uid
            ):
                consumer_uid_aliases[stable_uid] = source_uid
    links = [
        (str(edge.from_node), str(edge.from_output), str(edge.to_node), str(edge.to_input))
        for edge in current_ir.edges
    ]
    return nodes, links, consumer_uid_aliases


def compute_field_delta(
    snapshot: dict[str, Any],
    current_ir: "VibeWorkflow",
) -> dict[str, dict[str, Any]]:
    """Compute field-level changes between a stored snapshot and the current IR.

    Parameters
    ----------
    snapshot:
        A ``{uid: NodeFieldSnapshot}`` dict as returned by
        ``capture_ingest_snapshot``.  This is the *before* state.
    current_ir:
        The live ``VibeWorkflow`` to compare against.  This is the *after* state.

    Returns
    -------
    ``{uid: {field_name: delta}}`` — only nodes and fields where something
    changed. Scalar fields use ``(old_value, new_value)``; link changes use a
    ``semantic_link_set`` record carrying canonical before/after sets and
    resolution issues. Nodes absent from *snapshot* are omitted unless a
    canonical resolution issue is attributed to them (or is globally
    unresolved), in which case an issue-only semantic record is emitted.
    Nodes in *snapshot* but absent from *current_ir* (removed nodes) are also
    omitted; callers that need to detect removals should diff snapshot keys against
    the current IR's uid set directly.
    """
    # Build uid → node lookup for the current IR.
    uid_to_node = {
        (node.uid if node.uid else node_id): node
        for node_id, node in current_ir.nodes.items()
    }

    # Recompute current signatures inline to avoid a round-trip through capture.
    nodes = current_ir.nodes
    workflow_inputs = current_ir.inputs

    public_bindings: dict[str, list] = {node_id: [] for node_id in nodes}
    for input_name, vibe_input in workflow_inputs.items():
        if vibe_input.node_id in public_bindings:
            public_bindings[vibe_input.node_id].append((input_name, vibe_input.field))

    after_nodes, after_links, after_aliases = _workflow_semantic_graph(current_ir)
    before_nodes, before_links = _snapshot_semantic_graph(snapshot)
    # Snapshot aliasing requires corroboration from both representations: the
    # exact clone UID must exist in the snapshot and the corresponding live
    # node must carry validated lowering metadata.  The after graph may also
    # contain newly lowered clones absent from the snapshot, so it retains the
    # complete validated live alias map.
    before_aliases = _snapshot_consumer_uid_aliases(before_nodes, after_aliases)
    canonical_before, before_issues, before_attribution = _canonical_semantic_link_set(
        before_nodes,
        before_links,
        consumer_uid_aliases=before_aliases,
    )
    canonical_after, after_issues, after_attribution = _canonical_semantic_link_set(
        after_nodes,
        after_links,
        consumer_uid_aliases=after_aliases,
    )
    # Issues with no per-uid attribution target (both endpoints ghost, e.g.
    # ``unknown_source`` + ``unknown_consumer`` on a fully missing edge) cannot
    # land on any single fence target.  They are surfaced on EVERY live
    # uid's ``semantic_link_set`` record so the widget-shape fence
    # fails closed with a typed ``RefusedEmit`` instead of letting the
    # unresolved ghost edge crash the emitter with a bare ``KeyError``
    # (B03 rework7).  Attributable issues never fan out (rework5 guarantee).
    # Only attribution targets that can actually receive a delta count as
    # surfaced.  In particular, newly-added live nodes are valid targets, while
    # issues attributed solely to a removed node fall back to the global bucket.
    live_uids = {str(uid) for uid in uid_to_node}
    before_targets = {before_aliases.get(uid, uid) for uid in live_uids}
    after_targets = {after_aliases.get(uid, uid) for uid in live_uids}
    attributed_before = frozenset().union(
        *(before_attribution.get(uid, frozenset()) for uid in before_targets)
    )
    attributed_after = frozenset().union(
        *(after_attribution.get(uid, frozenset()) for uid in after_targets)
    )
    global_before_issues = tuple(sorted(set(before_issues) - attributed_before))
    global_after_issues = tuple(sorted(set(after_issues) - attributed_after))

    delta: dict[str, dict[str, Any]] = {}
    # Preserve snapshot order, then add live snapshot-absent nodes in workflow
    # order.  New nodes still omit ordinary deltas; this wider target set exists
    # solely so their attributed/global resolution issues reach the fence.
    candidate_uids = tuple(dict.fromkeys((*snapshot.keys(), *uid_to_node.keys())))
    for uid in candidate_uids:
        node = uid_to_node.get(uid)
        if node is None:
            # Node removed after snapshot — omit per spec (caller diffs keys directly).
            continue

        old_snap = snapshot.get(uid)

        # Recompute the current signature for this node.
        all_values = {**node.widgets, **node.inputs}
        current: dict[str, Any] = {
            "class_type": node.class_type,
            "widget_values_sig": tuple(sorted((k, repr(v)) for k, v in all_values.items())),
            "public_input_binding": tuple(sorted(public_bindings.get(node.id, []))),
        }

        node_delta: dict[str, Any] = {}
        if old_snap is not None:
            for field_name in _SNAPSHOT_FIELDS:
                old_val = old_snap[field_name]
                new_val = current[field_name]
                if old_val != new_val:
                    node_delta[field_name] = (old_val, new_val)

        before_uid_key = before_aliases.get(str(uid), str(uid))
        after_uid_key = after_aliases.get(str(uid), str(uid))
        before_incident = tuple(
            link
            for link in canonical_before
            if link[0] == before_uid_key or link[2] == before_uid_key
        )
        after_incident = tuple(
            link
            for link in canonical_after
            if link[0] == after_uid_key or link[2] == after_uid_key
        )
        # Resolution issues are attached only to the live nodes actually
        # involved (known endpoint uids plus consumers of failing walks), so
        # a single ambiguous helper never fabricates a semantic-link delta on
        # unrelated pins (B03 oracle finding 3 fan-out amplification).
        before_uid_issues = tuple(sorted(before_attribution.get(before_uid_key, ())))
        after_uid_issues = tuple(sorted(after_attribution.get(after_uid_key, ())))
        if (
            (old_snap is not None and before_incident != after_incident)
            or before_uid_issues
            or after_uid_issues
            or global_before_issues
            or global_after_issues
        ):
            node_delta["semantic_link_set"] = {
                "before": before_incident,
                "after": after_incident,
                "before_resolution_issues": before_uid_issues,
                "after_resolution_issues": after_uid_issues,
                # Unattributed global issues (fully ghost endpoints) ride on
                # every live fence target (B03 rework7/rework8).
                "global_before_resolution_issues": global_before_issues,
                "global_after_resolution_issues": global_after_issues,
            }

        if node_delta:
            delta[uid] = node_delta

    # A graph containing only ghost endpoints has no live node on which to
    # hang the global diagnostics.  Preserve the public invariant anyway:
    # canonical resolution issues must never collapse to an empty delta.
    if not delta and (before_issues or after_issues):
        delta["unresolved"] = {
            "semantic_link_set": {
                "before": (),
                "after": (),
                "before_resolution_issues": (),
                "after_resolution_issues": (),
                "global_before_resolution_issues": tuple(before_issues),
                "global_after_resolution_issues": tuple(after_issues),
            }
        }

    return delta


__all__ = ["SemanticLink", "SemanticNode", "canonical_semantic_link_set", "compute_field_delta"]
