"""Field-level delta computation between an ingest snapshot and the current IR.

``compute_field_delta`` compares a stored ``_ingest_snapshot`` (captured at
ingest time by ``vibecomfy.ingest.snapshot.capture_ingest_snapshot``) against
the live IR state of a ``VibeWorkflow``.

Nodes absent from *snapshot* (added after ingest) are omitted from the result —
downstream logic treats them as ``'snapshot-absent'``.
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

    uids: dict[str, str] = {}
    for node_id, (uid, _class_type, _channel) in normalized_nodes.items():
        prior_id = uids.get(uid)
        if prior_id is not None and prior_id != node_id:
            issues.add(f"duplicate_uid:{uid}:{min(prior_id, node_id)}:{max(prior_id, node_id)}")
        else:
            uids[uid] = node_id

    inbound: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for source, source_output, consumer, _consumer_input in link_rows:
        if source not in normalized_nodes:
            issues.add(f"unknown_source:{source}")
        if consumer not in normalized_nodes:
            issues.add(f"unknown_consumer:{consumer}")
        inbound[consumer].append((source, source_output))

    setters_by_channel: dict[str, list[str]] = defaultdict(list)
    for node_id, (_uid, class_type, channel) in normalized_nodes.items():
        if class_type == "SetNode" and channel:
            setters_by_channel[str(channel)].append(node_id)

    # Iterative terminal-source resolution with memoization.
    #
    # Each helper hop (Reroute passthrough, GetNode→SetNode broadcast hop)
    # follows exactly one candidate or fails closed, so the walk is a simple
    # chain.  The result of every visited (node_id, output_port) key is cached,
    # making the whole traversal linear in the helper graph and immune to
    # repeated fan-out re-walks.  Re-entering a key that is still on the
    # current path means the graph is cyclic: the walk terminates immediately
    # and the path is reported via ``cyclic_path:`` (fail closed).  The hard
    # ``_MAX_SEMANTIC_WALK`` hop cap guarantees bounded time even for
    # adversarial inputs, so every call returns a deterministic verdict.
    memo: dict[tuple[str, str], tuple[str, str] | None] = {}
    in_progress: set[tuple[str, str]] = set()

    def terminal_source(
        node_id: str,
        output_port: str,
    ) -> tuple[str, str] | None:
        start = (node_id, output_port)
        if start in memo:
            return memo[start]
        path: list[tuple[str, str]] = []
        current = start
        result: tuple[str, str] | None = None
        while True:
            key = current
            if key in memo:
                result = memo[key]
                break
            if key in in_progress:
                cycle_nodes = {
                    hop[0] for hop in path[path.index(key):]
                } | {key[0]}
                issues.add(f"cyclic_path:{':'.join(sorted(cycle_nodes))}")
                result = None
                break
            spec = normalized_nodes.get(key[0])
            if spec is None:
                issues.add(f"unknown_source:{key[0]}")
                result = None
                break
            uid, class_type, channel = spec
            if class_type not in _SEMANTIC_HELPERS:
                result = (uid, key[1])
                break
            if class_type == "Reroute":
                candidates = sorted(set(inbound.get(key[0], ())))
                if len(candidates) != 1:
                    issues.add(f"reroute_source_count:{key[0]}:{len(candidates)}")
                    result = None
                    break
                next_node, next_port = candidates[0]
            elif class_type == "GetNode":
                if not channel:
                    issues.add(f"broadcast_name_missing:{key[0]}")
                    result = None
                    break
                setters = sorted(set(setters_by_channel.get(str(channel), ())))
                if len(setters) != 1:
                    issues.add(
                        f"broadcast_setter_count:{key[0]}:{channel}:{len(setters)}"
                    )
                    result = None
                    break
                setter_id = setters[0]
                candidates = sorted(set(inbound.get(setter_id, ())))
                if len(candidates) != 1:
                    issues.add(f"broadcast_source_count:{setter_id}:{len(candidates)}")
                    result = None
                    break
                next_node, next_port = candidates[0]
            else:  # SetNode used as a source is not resolvable.
                issues.add(f"setnode_as_source:{key[0]}")
                result = None
                break
            in_progress.add(key)
            path.append(key)
            if len(path) > _MAX_SEMANTIC_WALK:
                issues.add(f"semantic_walk_limit:{key[0]}")
                result = None
                break
            current = (next_node, next_port)
        for visited_key in path:
            memo[visited_key] = result
            in_progress.discard(visited_key)
        memo[start] = result
        return result

    semantic: set[SemanticLink] = set()
    for source, source_output, consumer, consumer_input in link_rows:
        consumer_spec = normalized_nodes.get(consumer)
        if consumer_spec is None:
            continue
        consumer_uid, consumer_class_type, _channel = consumer_spec
        if consumer_class_type in {"SetNode", "Reroute"}:
            continue
        if consumer_class_type == "GetNode":
            issues.add(f"helper_input_unsupported:{consumer}")
            continue
        terminal = terminal_source(source, source_output)
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

    return tuple(sorted(semantic)), tuple(sorted(issues))


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
    resolution issues. Nodes absent from *snapshot* are omitted.
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

    before_nodes, before_links = _snapshot_semantic_graph(snapshot)
    after_nodes, after_links, after_aliases = _workflow_semantic_graph(current_ir)
    canonical_before, before_issues = canonical_semantic_link_set(before_nodes, before_links)
    canonical_after, after_issues = canonical_semantic_link_set(
        after_nodes,
        after_links,
        consumer_uid_aliases=after_aliases,
    )

    delta: dict[str, dict[str, Any]] = {}
    for uid, old_snap in snapshot.items():
        node = uid_to_node.get(uid)
        if node is None:
            # Node removed after snapshot — omit per spec (caller diffs keys directly).
            continue

        # Recompute the current signature for this node.
        all_values = {**node.widgets, **node.inputs}
        current: dict[str, Any] = {
            "class_type": node.class_type,
            "widget_values_sig": tuple(sorted((k, repr(v)) for k, v in all_values.items())),
            "public_input_binding": tuple(sorted(public_bindings.get(node.id, []))),
        }

        node_delta: dict[str, Any] = {}
        for field_name in _SNAPSHOT_FIELDS:
            old_val = old_snap[field_name]
            new_val = current[field_name]
            if old_val != new_val:
                node_delta[field_name] = (old_val, new_val)

        uid_key = str(uid)
        before_incident = tuple(
            link for link in canonical_before if link[0] == uid_key or link[2] == uid_key
        )
        after_incident = tuple(
            link for link in canonical_after if link[0] == uid_key or link[2] == uid_key
        )
        if before_incident != after_incident or before_issues or after_issues:
            node_delta["semantic_link_set"] = {
                "before": before_incident,
                "after": after_incident,
                "before_resolution_issues": before_issues,
                "after_resolution_issues": after_issues,
            }

        if node_delta:
            delta[uid] = node_delta

    return delta


__all__ = ["SemanticLink", "SemanticNode", "canonical_semantic_link_set", "compute_field_delta"]
