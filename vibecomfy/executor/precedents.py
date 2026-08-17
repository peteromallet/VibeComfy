"""Bounded precedent-topology projection (B04).

A fetched precedent record (a Hivemind workflow row, or a workflow-valued
ready template) is served to the agent as an *immutable* surface+topology
view — never the raw workflow JSON.  The surface is the canonical Python
surface lens (:func:`vibecomfy.porting.render.render(wf, "surface")`); the
topology is a *bounded* projection produced here.

This projection is deliberately NOT the Law-4 complete-topology lens.  Law 4's
``render(wf, "topology")`` contract is complete — every node and every edge,
no truncation.  A precedent record, however, can be arbitrarily large, so its
topology is bounded:

* ``max_nodes`` / ``max_edges`` caps (128 / 256 by default);
* ranking: exact query/class matches first, then 1-hop neighbors, then 2-hop
  neighbors, then the rest — with the stable tie ``(class_type, uid)``;
* only *induced* edges (both endpoints in the selected node set);
* a 64 KiB byte ceiling on the rendered output.

The result always carries ``omitted_node_count``, ``omitted_edge_count`` and
``global_topology_complete=False`` so a consumer can never mistake a bounded
precedent view for the complete topology contract.
"""

from __future__ import annotations

from typing import Any, Mapping

PRECEDENT_MAX_RENDERED_BYTES = 64 * 1024  # 64 KiB
PRECEDENT_MAX_NODES = 128
PRECEDENT_MAX_EDGES = 256

_TOPOLOGY_KEY_NODES = "nodes"
_TOPOLOGY_KEY_EDGES = "edges"
_TOPOLOGY_KEY_OMITTED_NODES = "omitted_node_count"
_TOPOLOGY_KEY_OMITTED_EDGES = "omitted_edge_count"
_TOPOLOGY_KEY_COMPLETE = "global_topology_complete"


def _uid_ref(node: Any, node_id: Any) -> str:
    """Stable node reference: uid when present, else the node id."""
    uid = str(getattr(node, "uid", "") or "")
    return uid or str(node_id)


def _class_type(node: Any) -> str:
    return str(getattr(node, "class_type", "") or "")


def _query_matches(query: str, class_type: str) -> bool:
    """Exact class match, or a class containing the (single-token) query."""
    q = query.strip().casefold()
    if not q:
        return False
    ct = class_type.casefold()
    return ct == q or q in ct


def _rank_key(node: Any, node_id: Any) -> tuple[str, str]:
    """Stable tie ``(class_type, uid)``."""
    return (_class_type(node), _uid_ref(node, node_id))


def project_precedent_topology(
    workflow: Any,
    *,
    query: str = "",
    max_nodes: int = PRECEDENT_MAX_NODES,
    max_edges: int = PRECEDENT_MAX_EDGES,
    max_bytes: int = PRECEDENT_MAX_RENDERED_BYTES,
) -> dict[str, Any]:
    """Project a bounded topology view for one precedent workflow.

    *workflow* is a :class:`~vibecomfy.workflow.VibeWorkflow` (the IR).  The
    result is a plain JSON-safe mapping:

    * ``nodes`` — ranked node refs ``"<uid> (<ClassType>)"`` (≤ ``max_nodes``);
    * ``edges`` — induced edges ``"<uid>.<OUTPUT> -> <uid>.<input>"``
      (≤ ``max_edges``);
    * ``omitted_node_count`` / ``omitted_edge_count`` — how many of the full
      graph's nodes/edges were left out of the projection;
    * ``global_topology_complete`` — always ``False`` (bounded view).

    ``max_bytes`` is honored by :func:`render_precedent_topology`, not by the
    structured lists (which are already capped by ``max_nodes``/``max_edges``).
    """
    nodes = sorted(workflow.nodes.items(), key=lambda item: _rank_key(item[1], item[0]))
    refs = {str(nid): _uid_ref(node, nid) for nid, node in nodes}
    total_nodes = len(nodes)

    # ── adjacency over the canonical IR edges ────────────────────────────────
    adjacency: dict[str, set[str]] = {str(nid): set() for nid, _ in nodes}
    for edge in workflow.edges:
        origin = str(edge.from_node)
        target = str(edge.to_node)
        adjacency.setdefault(origin, set()).add(target)
        adjacency.setdefault(target, set()).add(origin)

    # ── rank: exact query/class matches → 1-hop → 2-hop → rest ──────────────
    seed_ids = {
        str(nid)
        for nid, node in nodes
        if _query_matches(query, _class_type(node))
    }
    rank: dict[str, int] = {}
    for nid in seed_ids:
        rank[nid] = 0
    hop1 = {neighbor for nid in seed_ids for neighbor in adjacency.get(nid, ())}
    for nid in hop1:
        rank.setdefault(nid, 1)
    hop2 = {neighbor for nid in hop1 for neighbor in adjacency.get(nid, ())}
    for nid in hop2:
        rank.setdefault(nid, 2)
    for nid, _node in nodes:
        rank.setdefault(str(nid), 3)

    def _order_key(item: tuple[str, Any]) -> tuple[int, str, str]:
        nid, node = item
        return (rank.get(str(nid), 3), _class_type(node), _uid_ref(node, nid))

    ordered = sorted(nodes, key=_order_key)
    selected_ids = {str(nid) for nid, _node in ordered[:max_nodes]}
    selected_nodes = [
        f"{_uid_ref(node, nid)} ({_class_type(node) or '?'})"
        for nid, node in ordered[:max_nodes]
    ]

    # ── induced edges only (both endpoints selected), stable order ───────────
    edge_key = lambda e: (  # noqa: E731
        refs.get(str(e.from_node), str(e.from_node)),
        str(e.from_output),
        refs.get(str(e.to_node), str(e.to_node)),
        str(e.to_input),
    )
    induced = sorted(
        (
            edge
            for edge in workflow.edges
            if str(edge.from_node) in selected_ids and str(edge.to_node) in selected_ids
        ),
        key=edge_key,
    )
    total_edges = len(workflow.edges)
    selected_edges = [
        (
            f"{refs.get(str(edge.from_node), str(edge.from_node))}."
            f"{edge.from_output} -> "
            f"{refs.get(str(edge.to_node), str(edge.to_node))}."
            f"{edge.to_input}"
        )
        for edge in induced[:max_edges]
    ]

    return {
        _TOPOLOGY_KEY_NODES: selected_nodes,
        _TOPOLOGY_KEY_EDGES: selected_edges,
        _TOPOLOGY_KEY_OMITTED_NODES: total_nodes - len(selected_nodes),
        _TOPOLOGY_KEY_OMITTED_EDGES: total_edges - len(selected_edges),
        _TOPOLOGY_KEY_COMPLETE: False,
    }


def render_precedent_topology(
    topology: Mapping[str, Any],
    *,
    max_bytes: int = PRECEDENT_MAX_RENDERED_BYTES,
) -> str:
    """Render a projected topology mapping as bounded model-facing text.

    Trims the rendered output to ``max_bytes`` UTF-8 bytes so an oversized
    precedent can never blow out the agent context window.  The omission
    counters are always echoed in the header.
    """
    nodes = [str(item) for item in (topology.get(_TOPOLOGY_KEY_NODES) or ())]
    edges = [str(item) for item in (topology.get(_TOPOLOGY_KEY_EDGES) or ())]
    omitted_nodes = int(topology.get(_TOPOLOGY_KEY_OMITTED_NODES) or 0)
    omitted_edges = int(topology.get(_TOPOLOGY_KEY_OMITTED_EDGES) or 0)

    lines = [
        "## Precedent Topology",
        f"{len(nodes)} node(s), {len(edges)} edge(s) "
        f"(omitted nodes: {omitted_nodes}, omitted edges: {omitted_edges}, "
        "complete: false)",
    ]
    lines.append("nodes:")
    lines.extend(f"  {node}" for node in nodes)
    lines.append("edges:")
    lines.extend(f"  {edge}" for edge in edges)

    text = "\n".join(lines)
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    # Trim to the byte ceiling without splitting a UTF-8 sequence.
    encoded = text.encode("utf-8")[:max_bytes]
    while encoded:
        try:
            return encoded.decode("utf-8")
        except UnicodeDecodeError:
            encoded = encoded[:-1]
    return ""


def sanitize_workflow_text(
    content: str,
    *,
    query: str = "",
) -> dict[str, Any] | None:
    """Sanitize workflow-valued *content* into a surface+topology view.

    Returns ``None`` when *content* is not a workflow JSON (e.g. Python
    source, prose, or malformed JSON).  When it IS a workflow JSON of a known
    shape, it is normalized through the named ingest door and projected into
    ``{"surface_lens", "topology", "shape"}`` — the raw workflow JSON never
    rides in the returned view.  Used to apply the B04 precedent sanitization
    to workflow-valued ready-template observations.
    """
    import json as _json

    try:
        payload = _json.loads(content)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, Mapping):
        return None

    from vibecomfy.ingest.normalize import (  # noqa: PLC0415
        detect_workflow_shape,
        from_api,
        from_envelope,
        from_ui,
    )
    from vibecomfy.porting.render import render  # noqa: PLC0415

    try:
        shape = detect_workflow_shape(dict(payload))
        if shape == "vibe":
            workflow = from_envelope(dict(payload))
        elif shape == "ui":
            workflow = from_ui(dict(payload), use_comfy_converter=False)
        elif shape == "api":
            workflow = from_api(dict(payload))
        else:
            return None
    except Exception:  # noqa: BLE001 - not a workflow; return None
        return None
    return {
        "surface_lens": render(workflow, "surface"),
        "topology": project_precedent_topology(workflow, query=query),
        "shape": shape,
    }


__all__ = [
    "PRECEDENT_MAX_EDGES",
    "PRECEDENT_MAX_NODES",
    "PRECEDENT_MAX_RENDERED_BYTES",
    "project_precedent_topology",
    "render_precedent_topology",
    "sanitize_workflow_text",
]
