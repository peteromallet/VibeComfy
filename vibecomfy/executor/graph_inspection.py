"""Deterministic graph-inspection evidence extraction.

Product-path inspection projects from the IR (:class:`VibeWorkflow`).
Raw LiteGraph / envelope dicts enter only through the named ingest
doors (``from_ui`` / ``from_envelope`` / ``from_api``) and are then
read as ``wf.nodes``, ``wf.edges``, and ``wf.widgets``.

Every public function is pure: it never mutates the workflow or the
raw dict.  Failures during ingest yield empty evidence so callers can
treat inspection as best-effort.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeNode, VibeWorkflow


# ── typed evidence structures ────────────────────────────────────────────────


@dataclass(frozen=True)
class WidgetEvidence:
    """One widget value extracted from a node's ``widgets_values`` list."""

    index: int
    value: Any
    name: str | None = None


@dataclass(frozen=True)
class SlotEvidence:
    """One input or output slot on a node."""

    name: str
    slot_type: str  # "input" | "output"
    # Input direction: the retained LiteGraph link id connected to this slot.
    link_id: int | None = None
    # Output direction: retained LiteGraph link ids leaving this slot
    # (RRSYN-3 — both endpoint directions carry real identities).
    link_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class NodeEvidence:
    """Structured evidence for one node in a ComfyUI graph."""

    node_id: int | str
    class_type: str
    title: str | None = None
    widgets: tuple[WidgetEvidence, ...] = ()
    input_slots: tuple[SlotEvidence, ...] = ()
    output_slots: tuple[SlotEvidence, ...] = ()
    type_name: str | None = None
    # Retained LiteGraph mode integer (0 enabled / 2 muted / 4 bypassed);
    # ``None`` when unknown.  RRSYN-3: bypassed state must be exposed,
    # never silently dropped.
    mode: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "widgets", tuple(self.widgets))
        object.__setattr__(self, "input_slots", tuple(self.input_slots))
        object.__setattr__(self, "output_slots", tuple(self.output_slots))


@dataclass(frozen=True)
class EdgeEvidence:
    """One link / edge in a ComfyUI graph.

    ``link_id`` is the RETAINED LiteGraph link id.  ``None`` means the
    original identity was unavailable (no UI-format sidecar) — it is never
    invented from enumeration order (RRSYN-3 fail-closed rule).
    """

    link_id: int | None
    origin_node: int | str
    origin_slot: int
    target_node: int | str
    target_slot: int
    link_type: str | None = None


@dataclass(frozen=True)
class GraphEvidence:
    """Complete structured evidence extracted from a ComfyUI graph dict."""

    node_count: int
    nodes: tuple[NodeEvidence, ...] = ()
    edges: tuple[EdgeEvidence, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "edges", tuple(self.edges))


# ── link normalisation ───────────────────────────────────────────────────────


def _normalise_link(link: dict | list, index: int = 0) -> EdgeEvidence:
    """Convert a single link element to a uniform :class:`EdgeEvidence`.

    ComfyUI represents links in two shapes:

    **List shape** (positional)::

        [link_id, origin_node, origin_slot, target_node, target_slot, link_type]

    **Dict shape** (named)::

        {
            "id": …,
            "origin_id": …,   "origin_slot": …,
            "target_id": …,   "target_slot": …,
            "type": …,
        }

    Returns an :class:`EdgeEvidence` with deterministic field extraction for
    either shape.
    """
    if isinstance(link, list):
        lid = int(link[0]) if len(link) > 0 else index
        src_node = link[1] if len(link) > 1 else 0
        src_slot = int(link[2]) if len(link) > 2 else 0
        tgt_node = link[3] if len(link) > 3 else 0
        tgt_slot = int(link[4]) if len(link) > 4 else 0
        ltype: str | None = str(link[5]) if len(link) > 5 and link[5] is not None else None
        return EdgeEvidence(
            link_id=lid,
            origin_node=src_node,
            origin_slot=src_slot,
            target_node=tgt_node,
            target_slot=tgt_slot,
            link_type=ltype,
        )
    # dict shape
    lid = int(link.get("id", link.get("link_id", index)))
    return EdgeEvidence(
        link_id=lid,
        origin_node=link.get("origin_id", 0),
        origin_slot=int(link.get("origin_slot", 0)),
        target_node=link.get("target_id", 0),
        target_slot=int(link.get("target_slot", 0)),
        link_type=link.get("type"),
    )


def normalise_links(links: list) -> tuple[EdgeEvidence, ...]:
    """Normalise a list of link elements into a tuple of :class:`EdgeEvidence`.

    Accepts a list of either list-shaped or dict-shaped link elements and
    returns a deterministic, typed tuple suitable for evidence consumers.
    """
    return tuple(_normalise_link(link, idx) for idx, link in enumerate(links))


# ── node extraction ──────────────────────────────────────────────────────────


def _sort_widget_name(name: str) -> tuple[int, Any]:
    if name.startswith("widget_"):
        suffix = name.split("_", 1)[1]
        if suffix.isdigit():
            return (0, int(suffix))
    return (1, name)


def _evidence_id(value: Any) -> int | str:
    """Prefer an int node id when the IR id is a digit string."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    text = str(value)
    if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
        return int(text)
    return value if isinstance(value, str) else text


def _slot_index(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _node_title(node: VibeNode) -> str | None:
    metadata = node.metadata
    if not isinstance(metadata, dict):
        return None
    raw_ui = metadata.get("_ui")
    if not isinstance(raw_ui, dict):
        return None
    for key in ("title", "name"):
        title = raw_ui.get(key)
        if isinstance(title, str) and title.strip():
            return title
    return None


def _node_type_name(node: VibeNode) -> str | None:
    metadata = node.metadata
    if not isinstance(metadata, dict):
        return None
    raw_ui = metadata.get("_ui")
    if not isinstance(raw_ui, dict):
        return None
    type_name = raw_ui.get("type")
    if isinstance(type_name, str) and type_name.strip():
        return type_name
    return None


def _declared_output_names(node: VibeNode) -> tuple[str, ...]:
    metadata = node.metadata
    if not isinstance(metadata, dict):
        return ()
    names: list[str] = []
    seen: set[str] = set()

    def _add(name: Any) -> None:
        text = str(name)
        if not text or text in seen:
            return
        seen.add(text)
        names.append(text)

    declared = metadata.get("output_names")
    if isinstance(declared, (list, tuple)):
        for name in declared:
            _add(name)
    raw_ui = metadata.get("_ui")
    if isinstance(raw_ui, dict):
        outputs = raw_ui.get("outputs")
        if isinstance(outputs, list):
            for item in outputs:
                if isinstance(item, dict):
                    _add(item.get("name"))
                elif isinstance(item, str):
                    _add(item)
    return tuple(names)


def _schema_widget_names_for_node(node: VibeNode) -> tuple[str, ...]:
    """Schema field names for this instance, positional-index aligned (RC8-A)."""
    try:
        from vibecomfy.porting.widgets.schema import effective_widget_names_for_class

        names = effective_widget_names_for_class(
            str(node.class_type),
            allow_object_info_fallback=True,
        )
        return tuple(str(name) for name in names if name)
    except Exception:
        return ()


def _widgets_from_ir(node: VibeNode) -> tuple[WidgetEvidence, ...]:
    from vibecomfy.porting.widgets.compact_resolver import (
        compact_widget_names_for_node,
        widget_index_for_field,
    )

    def _named_or_none(name: Any) -> str | None:
        if not isinstance(name, str) or not name or name.startswith("widget_"):
            return None
        return name

    raw = node.raw_widgets
    values = getattr(raw, "values", None)
    resolution = compact_widget_names_for_node(node)
    if isinstance(values, list):
        return tuple(
            WidgetEvidence(
                index=index,
                name=_named_or_none(
                    resolution.names[index] if index < len(resolution.names) else None
                ),
                value=value,
            )
            for index, value in enumerate(values)
        )

    named: list[WidgetEvidence] = []
    widgets = node.widgets
    if isinstance(widgets, dict) and widgets:
        for offset, name in enumerate(sorted((str(key) for key in widgets), key=_sort_widget_name)):
            index = widget_index_for_field(node, name)
            if index is None:
                index = offset
            resolved_name = (
                resolution.names[index] if index < len(resolution.names) else name
            )
            named.append(
                WidgetEvidence(
                    index=index,
                    name=_named_or_none(resolved_name),
                    value=widgets[name],
                )
            )
    inputs = node.inputs
    if isinstance(inputs, dict):
        base = len(named)
        for offset, name in enumerate(sorted(str(key) for key in inputs)):
            value = inputs[name]
            if isinstance(value, (dict, list, tuple)):
                continue
            named.append(WidgetEvidence(index=base + offset, name=str(name), value=value))
    return tuple(named)


def _node_from_ir(
    node: VibeNode,
    incoming: dict[str, dict[str, int | None]],
    outgoing: dict[str, set[str]],
    outgoing_links: dict[str, dict[str, list[int | None]]] | None = None,
) -> NodeEvidence:
    from vibecomfy.workflow import mode_to_litegraph

    node_key = str(node.id)
    incoming_for_node = incoming.get(node_key, {})
    input_slots = tuple(
        SlotEvidence(name=name, slot_type="input", link_id=link_id)
        for name, link_id in sorted(incoming_for_node.items())
    )
    outgoing_for_node = outgoing_links.get(node_key, {}) if outgoing_links else {}
    declared = list(_declared_output_names(node))

    def _slot_ids(index: int, name: str) -> tuple[int, ...]:
        # Edges address their origin either by declared output NAME or by
        # its numeric slot spelling; merge both so ids land on the real slot.
        ids: list[int] = []
        for key in (name, str(index)):
            for lid in outgoing_for_node.get(key, ()):
                if lid is not None and lid not in ids:
                    ids.append(lid)
        return tuple(ids)

    output_names = list(declared)
    seen = set(declared)
    for name in sorted(outgoing.get(node_key, set())):
        if name in seen:
            continue
        if name.isdigit() and int(name) < len(declared):
            continue  # index spelling of an already-declared slot
        output_names.append(name)
        seen.add(name)
    output_slots = tuple(
        SlotEvidence(
            name=name,
            slot_type="output",
            link_ids=_slot_ids(index, name),
        )
        for index, name in enumerate(output_names)
    )
    return NodeEvidence(
        node_id=_evidence_id(node.id),
        class_type=node.class_type or "Unknown",
        title=_node_title(node),
        widgets=_widgets_from_ir(node),
        input_slots=input_slots,
        output_slots=output_slots,
        type_name=_node_type_name(node),
        mode=mode_to_litegraph(node.mode) or None,
    )


# ── deterministic derivations ────────────────────────────────────────────────


@dataclass(frozen=True)
class GraphDerivations:
    """Deterministic graph-inspection derivations computed from topology evidence.

    Every field is derived purely from :class:`GraphEvidence` nodes, edges,
    class-type names, and visible widget values — no model calls, no external
    lookups.
    """

    inputs: tuple[int | str, ...] = ()
    """Entry-point node ids that feed an executed output chain (orphans excluded)."""

    outputs: tuple[int | str, ...] = ()
    """Node ids with no outgoing edges (graph exit points)."""

    model_stack: tuple[int | str, ...] = ()
    """Model-loading chain node ids (CheckpointLoader*/UNETLoader* feeding an executed output chain)."""

    dormant_branches: tuple[tuple[int | str, ...], ...] = ()
    """Disconnected subgraphs that are not reachable from the main output chain."""

    expensive_or_risky: tuple[tuple[int | str, str], ...] = ()
    """Nodes flagged as expensive or risky, each as ``(node_id, reason)``."""


def _outgoing_node_ids(evidence: GraphEvidence) -> set[int | str]:
    """Return the set of node ids that have at least one outgoing edge."""
    return {e.origin_node for e in evidence.edges}


def _incoming_linked_node_ids(evidence: GraphEvidence) -> set[int | str]:
    """Return the set of node ids that have at least one linked input slot.

    Input slots are only emitted for CONNECTED inputs, so presence — not the
    numeric id — is the connectivity signal.  A ``None`` link_id means the
    connection exists but its retained identity was unrecoverable; that node
    is still linked (RRSYN-3).
    """
    linked: set[int | str] = set()
    for node in evidence.nodes:
        for slot in node.input_slots:
            if slot.slot_type == "input":
                linked.add(node.node_id)
                break
    return linked


def derive_inputs(evidence: GraphEvidence) -> tuple[int | str, ...]:
    """Return entry-point node ids on an executed output chain.

    A node is an input when none of its input slots carry a ``link_id``.
    This captures loader nodes (CheckpointLoaderSimple, LoadImage,
    EmptyLatentImage, …) and any node whose inputs are all unconnected —
    but only when the node structurally feeds an executed output chain.
    Nodes that reach no output (P6 :func:`derive_orphans`) are never
    advertised as inputs: an orphan loader would otherwise be presented
    as the carrier of a value the executed graph does not read.
    """
    linked = _incoming_linked_node_ids(evidence)
    orphans = set(derive_orphans(evidence))
    result: list[int | str] = []
    for node in evidence.nodes:
        if node.node_id not in linked and node.node_id not in orphans:
            result.append(node.node_id)
    return tuple(result)

def derive_outputs(evidence: GraphEvidence) -> tuple[int | str, ...]:
    """Return exit-point node ids that have no outgoing edges.

    A node is an output when no edge originates from it.  This naturally
    captures SaveImage, PreviewImage, and any terminal node — but never a
    P6 orphan: a node that feeds no executed output chain is not an exit
    point of the executed graph and is not advertised as one.
    """
    outgoing = _outgoing_node_ids(evidence)
    orphans = set(derive_orphans(evidence))
    result: list[int | str] = []
    for node in evidence.nodes:
        if node.node_id not in outgoing and node.node_id not in orphans:
            result.append(node.node_id)
    return tuple(result)

def _model_stack_seed_ids(evidence: GraphEvidence) -> list[int | str]:
    """Return node ids whose class_type suggests a model-loader."""
    seeds: list[int | str] = []
    for node in evidence.nodes:
        ct = node.class_type.lower()
        if ct.startswith("checkpointloader") or ct.startswith("unetloader"):
            seeds.append(node.node_id)
    return seeds


def _reachable_from(
    seed_ids: set[int | str],
    edges: tuple[EdgeEvidence, ...],
) -> set[int | str]:
    """BFS over edges; return all node ids reachable from *seed_ids*."""
    adjacency: dict[int | str, list[int | str]] = {}
    for e in edges:
        adjacency.setdefault(e.origin_node, []).append(e.target_node)
    visited: set[int | str] = set()
    queue: list[int | str] = list(seed_ids)
    while queue:
        cur = queue.pop(0)
        if cur in visited:
            continue
        visited.add(cur)
        for nxt in adjacency.get(cur, []):
            if nxt not in visited:
                queue.append(nxt)
    return visited

def _output_reachable_ids(evidence: GraphEvidence) -> set[int | str]:
    """Return node ids on a structural path into an executed output chain.

    Output seeds are nodes with no outgoing edges that receive at least one
    link — terminals that actually consume the graph.  Fully isolated nodes
    seed nothing.  The closure walks edges backwards from those seeds.
    """
    outgoing = _outgoing_node_ids(evidence)
    receives = {e.target_node for e in evidence.edges}
    seeds = {
        node.node_id
        for node in evidence.nodes
        if node.node_id not in outgoing and node.node_id in receives
    }
    if not seeds:
        return set()
    reverse: dict[int | str, list[int | str]] = {}
    for e in evidence.edges:
        reverse.setdefault(e.target_node, []).append(e.origin_node)
    visited: set[int | str] = set()
    queue: list[int | str] = list(seeds)
    while queue:
        cur = queue.pop()
        if cur in visited:
            continue
        visited.add(cur)
        for prev in reverse.get(cur, ()):
            if prev not in visited:
                queue.append(prev)
    return visited


def derive_orphans(evidence: GraphEvidence) -> tuple[int | str, ...]:
    """Return node ids structurally disconnected from every output chain.

    An orphan is a node from which no directed path reaches an output node
    (P6-CORPUS-G1-ORPHAN).  Detection is purely structural — backward
    reachability from the consuming terminals; widget values and node
    mode/bypass state are deliberately ignored.  Orphans must not be
    advertised as value carriers (inputs, model stack): leg 11 applied a
    checkpoint swap to an edge-less UNETLoader because ``graph.inputs``
    named it as the checkpoint carrier while the executed chain read the
    same value from a live generator node.

    When no output chain exists at all (no linked terminal anywhere),
    nothing is provably orphaned and every node is kept.
    """
    all_ids = [node.node_id for node in evidence.nodes]
    if not all_ids:
        return ()
    live = _output_reachable_ids(evidence)
    if not live:
        return ()
    return tuple(sorted((nid for nid in all_ids if nid not in live), key=str))


def derive_model_stack(evidence: GraphEvidence) -> tuple[int | str, ...]:
    """Return node ids in the model-loading chain.

    Starts from every node whose ``class_type`` begins with
    ``CheckpointLoader`` or ``UNETLoader`` and follows outgoing edges.
    Loaders that feed no executed output chain (:func:`derive_orphans`)
    are skipped so an orphan loader is never advertised as the model
    carrier.  The result is topologically sorted by discovery order (BFS).
    """
    seeds = _model_stack_seed_ids(evidence)
    if not seeds:
        return ()
    live = _output_reachable_ids(evidence)
    if live:
        seeds = [nid for nid in seeds if nid in live]
    if not seeds:
        return ()
    reachable = _reachable_from(set(seeds), evidence.edges)
    # Preserve BFS discovery order
    result: list[int | str] = []
    for nid in reachable:
        result.append(nid)
    return tuple(result)


# Class-type substrings that identify a "terminal" output node — a node that
# produces a displayable/saveable result.  Components that do *not* contain
# any terminal output are considered dormant branches.
_TERMINAL_OUTPUT_PATTERNS: tuple[str, ...] = (
    "saveimage",
    "previewimage",
    "vhsvideocombine",
    "saveanimatedwebp",
    "savegif",
)


def _has_terminal_output(component_nodes: set[int | str], evidence: GraphEvidence) -> bool:
    """Return True if any node in *component_nodes* is a terminal output."""
    for node in evidence.nodes:
        if node.node_id not in component_nodes:
            continue
        ct = node.class_type.lower()
        for pat in _TERMINAL_OUTPUT_PATTERNS:
            if pat in ct:
                return True
    return False


def _weakly_connected_components(
    evidence: GraphEvidence,
) -> list[set[int | str]]:
    """Partition all nodes into weakly-connected components (undirected edges).

    Edges referencing node ids not present in *evidence.nodes* are silently
    skipped — this can happen when a link references a node that was removed
    or belongs to a different sub-graph.
    """
    all_ids = {n.node_id for n in evidence.nodes}
    if not all_ids:
        return []

    # Build undirected adjacency, skipping edges with missing endpoints
    neighbours: dict[int | str, set[int | str]] = {nid: set() for nid in all_ids}
    for e in evidence.edges:
        if e.origin_node not in all_ids or e.target_node not in all_ids:
            continue
        neighbours[e.origin_node].add(e.target_node)
        neighbours[e.target_node].add(e.origin_node)

    visited: set[int | str] = set()
    components: list[set[int | str]] = []
    for nid in sorted(all_ids, key=str):
        if nid in visited:
            continue
        comp: set[int | str] = set()
        stack = [nid]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            for nb in neighbours.get(cur, ()):
                if nb not in visited:
                    stack.append(nb)
        components.append(comp)
    return components


def derive_dormant_branches(
    evidence: GraphEvidence,
) -> tuple[tuple[int | str, ...], ...]:
    """Find connected components with no terminal-output node.

    A *dormant branch* is a maximal weakly-connected component of the
    graph that does **not** contain any ``SaveImage``, ``PreviewImage``,
    ``VHSVideoCombine``, ``SaveAnimatedWEBP``, or ``SaveGIF`` node —
    **only when at least one other component does** contain a terminal
    output.  If no component has a terminal output, the graph may be
    incomplete but we do not flag every component as dormant.

    Components that *do* contain a terminal output are considered part of
    the main deliverable graph and are excluded.

    Returns one tuple per dormant component, each sorted by node id.
    """
    components = _weakly_connected_components(evidence)
    if not components:
        return ()

    # Only flag dormant branches when there is at least one component that
    # *does* contain a terminal output — otherwise the graph is just
    # incomplete, not dormant.
    has_output_component = any(
        _has_terminal_output(comp, evidence) for comp in components
    )
    if not has_output_component:
        return ()

    result: list[tuple[int | str, ...]] = []
    for comp in components:
        if not _has_terminal_output(comp, evidence):
            sorted_comp = sorted(comp, key=str)
            result.append(tuple(sorted_comp))
    return tuple(result)


# ── expensive / risky heuristics ──────────────────────────────────────────────

# Class-type substrings that signal an expensive or risky node, mapped to a
# short human-readable reason.
_EXPENSIVE_RISKY_PATTERNS: dict[str, str] = {
    "upscale": "high-resolution upscale (memory-intensive)",
    "facedetailer": "face detailer pipeline (extra sampling pass)",
    "hdr": "HDR processing (multi-pass)",
    "batch": "batch processing",
}


def _widget_steps(node: NodeEvidence) -> int | None:
    """Heuristic: return the steps count from a named or positional widget."""
    for widget in node.widgets:
        if widget.name == "steps" and isinstance(widget.value, (int, float)) and widget.value > 0:
            return int(widget.value)
    if len(node.widgets) > 2:
        val = node.widgets[2].value
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    return None


def derive_expensive_or_risky(
    evidence: GraphEvidence,
) -> tuple[tuple[int | str, str], ...]:
    """Flag nodes that are computationally expensive or risky.

    Heuristics (deterministic, no model calls):

    * Class-type name contains a known expensive sub-string (upscale,
      facedetailer, hdr, batch).
    * ``KSampler`` nodes with steps > 30 (from widget index 2).
    * ``KSampler`` nodes with any step count are noted as the primary
      sampling step.
    """
    result: list[tuple[int | str, str]] = []
    for node in evidence.nodes:
        ct_lower = node.class_type.lower()
        # Known expensive class patterns
        for pattern, reason in _EXPENSIVE_RISKY_PATTERNS.items():
            if pattern in ct_lower:
                result.append((node.node_id, reason))
                break
        else:
            # KSampler-specific heuristics
            if ct_lower == "ksampler":
                steps = _widget_steps(node)
                if steps is not None and steps > 30:
                    result.append(
                        (node.node_id, f"sampling with {steps} steps (>30)")
                    )
                else:
                    result.append((node.node_id, "core sampling step"))
    return tuple(result)


def compute_derivations(evidence: GraphEvidence) -> GraphDerivations:
    """Compute all deterministic derivations from *evidence*.

    This is the single entry point for downstream consumers that need the
    full set of inspect derivations.  Every return value is derived from
    topology, class names, and widget values only.
    """
    return GraphDerivations(
        inputs=derive_inputs(evidence),
        outputs=derive_outputs(evidence),
        model_stack=derive_model_stack(evidence),
        dormant_branches=derive_dormant_branches(evidence),
        expensive_or_risky=derive_expensive_or_risky(evidence),
    )


# ── inspect Markdown renderer ─────────────────────────────────────────────────


def render_inspect_markdown(
    evidence: GraphEvidence,
    derivations: GraphDerivations | None = None,
) -> str:
    """Render stable inspect Markdown from graph evidence and derivations.

    Produces deterministic Markdown with the following sections for
    non-trivial graphs (≥1 node):

    * ``## Overview`` — node/edge count summary
    * ``## Stages / Data Flow`` — data-flow description
    * ``## Model Stack`` — model-loading chain
    * ``## Key Nodes`` — per-node details (id, class, title, widgets, slots)
    * ``## Inputs / Outputs`` — entry and exit points
    * ``## Dormant Branches`` — disconnected components without terminal outputs
    * ``## Expensive / Risky Areas`` — nodes flagged as expensive or risky

    Empty optional sections are rendered as ``None detected``.  The renderer
    never includes repair suggestions, Apply/Reject guidance, or external
    model-family claims.

    Parameters
    ----------
    evidence:
        Structured graph evidence from :func:`inspect_graph`.
    derivations:
        Optional pre-computed derivations.  When ``None``, derivations are
        computed automatically via :func:`compute_derivations`.

    Returns
    -------
    str
        Deterministic Markdown suitable for the inspect reply envelope.
    """
    if derivations is None:
        derivations = compute_derivations(evidence)

    # Build a lookup from node_id → NodeEvidence for fast access
    node_by_id: dict[int | str, NodeEvidence] = {}
    for node in evidence.nodes:
        node_by_id[node.node_id] = node

    sections: list[str] = []

    # ── ## Overview ───────────────────────────────────────────────
    sections.append("## Overview\n")
    if evidence.node_count == 0:
        sections.append("Empty graph (0 nodes).\n")
        return "".join(sections)

    edge_count = len(evidence.edges)
    summary = f"{evidence.node_count} node(s), {edge_count} edge(s)."
    # Include a brief class-type census
    class_counts: dict[str, int] = {}
    for node in evidence.nodes:
        class_counts[node.class_type] = class_counts.get(node.class_type, 0) + 1
    census = ", ".join(
        f"{ct} ({c})" for ct, c in sorted(class_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    sections.append(f"{summary}  Class types: {census}.\n")

    # ── ## Stages / Data Flow ─────────────────────────────────────
    sections.append("\n## Stages / Data Flow\n")
    _render_data_flow_section(sections, evidence, derivations, node_by_id)

    # ── ## Model Stack ────────────────────────────────────────────
    sections.append("\n## Model Stack\n")
    _render_model_stack_section(sections, derivations, node_by_id)

    # ── ## Key Nodes ──────────────────────────────────────────────
    sections.append("\n## Key Nodes\n")
    _render_key_nodes_section(sections, evidence, derivations)

    # ── ## Inputs / Outputs ───────────────────────────────────────
    sections.append("\n## Inputs / Outputs\n")
    _render_inputs_outputs_section(sections, derivations, node_by_id)

    # ── ## Dormant Branches ───────────────────────────────────────
    sections.append("\n## Dormant Branches\n")
    _render_dormant_branches_section(sections, derivations, node_by_id)

    # ── ## Expensive / Risky Areas ────────────────────────────────
    sections.append("\n## Expensive / Risky Areas\n")
    _render_expensive_risky_section(sections, derivations, node_by_id)

    return "".join(sections)


# ── section render helpers ────────────────────────────────────────────────────


def _node_label(nid: int | str, node_by_id: dict[int | str, NodeEvidence]) -> str:
    """Return a compact label for a node id: ``[id] ClassType``."""
    node = node_by_id.get(nid)
    if node is None:
        return f"[{nid}] (not found)"
    ct = node.class_type
    return f"[{nid}] {ct}"


def _node_label_with_title(
    nid: int | str, node_by_id: dict[int | str, NodeEvidence]
) -> str:
    """Return a label for a node id, appending the title when present."""
    node = node_by_id.get(nid)
    if node is None:
        return f"[{nid}] (not found)"
    ct = node.class_type
    if node.title:
        return f"[{nid}] {ct} ({node.title})"
    return f"[{nid}] {ct}"


def _render_data_flow_section(
    sections: list[str],
    evidence: GraphEvidence,
    derivations: GraphDerivations,
    node_by_id: dict[int | str, NodeEvidence],
) -> None:
    """Describe the data flow from inputs through processing to outputs."""
    inputs = derivations.inputs
    outputs = derivations.outputs
    edges = evidence.edges

    if not edges and evidence.node_count <= 1:
        sections.append(
            "Single node with no edges — no data flow to describe.\n"
        )
        return

    # Build a simple adjacency description
    if inputs:
        input_labels = [_node_label(nid, node_by_id) for nid in inputs]
        sections.append(
            "- **Inputs:** "
            + "; ".join(input_labels)
            + "\n"
        )

    if outputs:
        output_labels = [_node_label(nid, node_by_id) for nid in outputs]
        sections.append(
            "- **Outputs:** "
            + "; ".join(output_labels)
            + "\n"
        )

    if edges:
        # RRSYN-3: every edge is rendered — no silent cap.  Each edge
        # carries its retained LiteGraph link id; an unavailable identity is
        # marked explicitly instead of being replaced with an invented one.
        sections.append(
            f"- **Data-flow edges ({len(edges)}):**\n"
        )
        for edge in edges:
            src_label = _node_label(edge.origin_node, node_by_id)
            tgt_label = _node_label(edge.target_node, node_by_id)
            lt = f" ({edge.link_type})" if edge.link_type else ""
            lid = (
                f"link #{edge.link_id}"
                if isinstance(edge.link_id, int)
                else "link id unavailable"
            )
            sections.append(
                f"  - {src_label} → {tgt_label}{lt} [{lid}]\n"
            )
    else:
        sections.append("- No data-flow edges detected.\n")


def _render_model_stack_section(
    sections: list[str],
    derivations: GraphDerivations,
    node_by_id: dict[int | str, NodeEvidence],
) -> None:
    """Render the model-loading chain."""
    stack = derivations.model_stack
    if not stack:
        sections.append("None detected\n")
        return

    sections.append(
        f"The following nodes participate in the model-loading chain "
        f"({len(stack)} node(s)):\n"
    )
    for nid in stack:
        label = _node_label_with_title(nid, node_by_id)
        sections.append(f"- {label}\n")


def _render_key_nodes_section(
    sections: list[str],
    evidence: GraphEvidence,
    derivations: GraphDerivations | None = None,
) -> None:
    """Render per-node details."""
    if not evidence.nodes:
        sections.append("None detected\n")
        return

    # S3: deprioritize 0 in/out-degree nodes (orphans) — LTX 5175
    # Build orphan set for flagging; orphans have zero in/out-degree and
    # edits to them have no downstream effect.
    orphans: set[int | str] = set()
    if derivations is not None:
        try:
            orphans = set(derivations.orphans)
        except Exception:
            orphans = set()
    # Sort nodes: non-orphans first (by class name), orphans last deprioritized
    sorted_nodes = sorted(
        evidence.nodes,
        key=lambda n: (1 if n.node_id in orphans else 0, str(n.class_type), str(n.node_id)),
    )
    for node in sorted_nodes:
        nid = node.node_id
        ct = node.class_type
        label = f"[{nid}] {ct}"
        if node.title:
            label += f" ({node.title})"
        # S3: explicit orphan flag
        if nid in orphans:
            label += " [ORPHAN: 0 in/out-degree — edits have no downstream effect, deprioritized]"
        sections.append(f"- **{label}**\n")
        identity = [f"class_type={ct}"]
        if node.type_name and node.type_name != ct:
            identity.append(f"type={node.type_name}")
        if node.title and node.title not in {ct, node.type_name}:
            identity.append(f"display_title={node.title}")
        sections.append(f"  - Identity: {', '.join(identity)}\n")

        # Execution state (RRSYN-3): bypassed/muted nodes must never be
        # silently rendered as ordinary participants in the graph.
        if node.mode == 4:
            sections.append("  - State: bypassed (mode=4)\n")
        elif node.mode == 2:
            sections.append("  - State: muted (mode=2)\n")

        # Widget values.  RRSYN-3: unnamed widgets each render an explicit
        # redacted opaque placeholder — the count-only `unlabeled_count`
        # shape hid the fact that real values exist at those positions.
        # Raw values stay redacted (existing bounded preview preserved for
        # named widgets).
        if node.widgets:
            widget_strs: list[str] = []
            for w in node.widgets:
                if w.name:
                    widget_strs.append(f"{w.name}={_format_widget_value(w.value)}")
                else:
                    widget_strs.append(
                        f"widget_{w.index}={_format_opaque_value(w.value)}"
                    )
            sections.append(f"  - Widgets: {', '.join(widget_strs)}\n")
        else:
            sections.append("  - Widgets: none\n")

        # Input slots.  Every rendered input slot is connected; an identity
        # that could not be recovered from the retained sidecar says so
        # explicitly instead of inventing a numeric id (RRSYN-3).
        if node.input_slots:
            slot_strs: list[str] = []
            for slot in node.input_slots:
                if isinstance(slot.link_id, int):
                    slot_strs.append(f"{slot.name}=linked({slot.link_id})")
                else:
                    slot_strs.append(f"{slot.name}=linked(id unavailable)")
            sections.append(f"  - Input slots: {', '.join(slot_strs)}\n")
        else:
            sections.append("  - Input slots: none\n")

        # Output slots (RRSYN-3: both endpoint directions carry link ids)
        if node.output_slots:
            slot_strs_out: list[str] = []
            for slot in node.output_slots:
                if slot.link_ids:
                    links = ",".join(str(lid) for lid in slot.link_ids)
                    slot_strs_out.append(f"{slot.name}=links({links})")
                else:
                    slot_strs_out.append(slot.name)
            sections.append(f"  - Output slots: {', '.join(slot_strs_out)}\n")
        else:
            sections.append("  - Output slots: none\n")


def _render_inputs_outputs_section(
    sections: list[str],
    derivations: GraphDerivations,
    node_by_id: dict[int | str, NodeEvidence],
) -> None:
    """Render inputs and outputs."""
    inputs = derivations.inputs
    outputs = derivations.outputs

    if inputs:
        sections.append(f"- **Inputs ({len(inputs)}):**\n")
        for nid in inputs:
            label = _node_label_with_title(nid, node_by_id)
            sections.append(f"  - {label}\n")
    else:
        sections.append("- **Inputs:** None detected\n")

    if outputs:
        sections.append(f"- **Outputs ({len(outputs)}):**\n")
        for nid in outputs:
            label = _node_label_with_title(nid, node_by_id)
            sections.append(f"  - {label}\n")
    else:
        sections.append("- **Outputs:** None detected\n")


def _render_dormant_branches_section(
    sections: list[str],
    derivations: GraphDerivations,
    node_by_id: dict[int | str, NodeEvidence],
) -> None:
    """Render dormant (disconnected, no-terminal-output) branches."""
    branches = derivations.dormant_branches
    if not branches:
        sections.append("None detected\n")
        return

    sections.append(
        f"The following {len(branches)} disconnected component(s) do not "
        f"connect to a terminal output:\n"
    )
    for i, branch in enumerate(branches, 1):
        labels = [_node_label(nid, node_by_id) for nid in branch]
        sections.append(f"- Branch {i}: {' → '.join(labels)}\n")


def _render_expensive_risky_section(
    sections: list[str],
    derivations: GraphDerivations,
    node_by_id: dict[int | str, NodeEvidence],
) -> None:
    """Render expensive/risky flagged nodes."""
    flagged = derivations.expensive_or_risky
    if not flagged:
        sections.append("None detected\n")
        return

    for nid, reason in flagged:
        label = _node_label(nid, node_by_id)
        sections.append(f"- {label}: {reason}\n")


def _format_opaque_value(value: Any) -> str:
    """Redacted opaque rendering for UNNAMED widget values (RRSYN-3).

    Unnamed widgets carry real values the agent must know exist, but their
    content cannot be classified against a schema — so the value is rendered
    as a type/shape placeholder, never raw.  Named widgets keep the existing
    bounded preview in :func:`_format_widget_value`.
    """
    if value is None:
        return "<opaque:null>"
    if isinstance(value, bool):
        return "<opaque:bool>"
    if isinstance(value, int):
        return "<opaque:int>"
    if isinstance(value, float):
        return "<opaque:float>"
    if isinstance(value, str):
        return f"<opaque:str len={len(value)}>"
    if isinstance(value, (list, tuple)):
        return f"<opaque:list n={len(value)}>"
    if isinstance(value, dict):
        return f"<opaque:dict n={len(value)}>"
    return f"<opaque:{type(value).__name__}>"


def _format_widget_value(value: Any) -> str:
    """Format a widget value for Markdown rendering."""
    if value is None:
        return "(empty)"
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return "(empty)"
        if len(s) > 80:
            return s[:77] + "..."
        return s
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value == int(value) and abs(value) < 1e12:
            return str(int(value))
        return str(value)
    return str(value)[:80]


# ── public API ───────────────────────────────────────────────────────────────


def inspect_workflow(
    wf: VibeWorkflow,
    *,
    link_identity: Mapping[tuple[str, str, str, str], int] | None = None,
) -> GraphEvidence:
    """Project structured evidence from an already-ingested :class:`VibeWorkflow`.

    Reads only IR fields (``wf.nodes``, ``wf.edges``, ``wf.widgets``,
    per-node ``raw_widgets`` / metadata furniture).  This is the product
    path; :func:`inspect_graph` is the raw-dict adapter that enters via
    the named ingest doors and then calls this function.

    RRSYN-3: edge/slot identities are the RETAINED LiteGraph link ids, not
    enumeration indices.  ``link_identity`` maps ``(origin_node, output_name,
    target_node, input_name)`` → original id; when omitted it is recovered
    from the retained snapshot's lossless raw sidecar.  Endpoints whose id
    cannot be recovered carry ``None`` — never a fabricated index.
    """
    if link_identity is None:
        from vibecomfy.ingest.snapshot import raw_link_identity, snapshot_of

        retained = snapshot_of(wf)
        link_identity = raw_link_identity(retained) if retained is not None else {}
    incoming: dict[str, dict[str, int | None]] = {}
    outgoing: dict[str, set[str]] = {}
    outgoing_links: dict[str, dict[str, list[int | None]]] = {}
    edges: list[EdgeEvidence] = []
    for edge in wf.edges:
        from_node = str(edge.from_node)
        to_node = str(edge.to_node)
        to_input = str(edge.to_input)
        from_output = str(edge.from_output)
        real_id = link_identity.get((from_node, from_output, to_node, to_input))
        if real_id is None:
            # Index-spelling fallbacks address raw nodes that carry no
            # declared output names.  The id still comes from the retained
            # link element — never from enumeration order.
            from_slot = str(_slot_index(from_output))
            to_slot = str(_slot_index(to_input))
            for fallback_key in (
                (from_node, from_slot, to_node, to_input),
                (from_node, from_output, to_node, to_slot),
                (from_node, from_slot, to_node, to_slot),
            ):
                real_id = link_identity.get(fallback_key)
                if real_id is not None:
                    break
        incoming.setdefault(to_node, {})[to_input] = real_id
        outgoing.setdefault(from_node, set()).add(from_output)
        outgoing_links.setdefault(from_node, {}).setdefault(from_output, []).append(
            real_id
        )
        edges.append(
            EdgeEvidence(
                link_id=real_id,
                origin_node=_evidence_id(edge.from_node),
                origin_slot=_slot_index(edge.from_output),
                target_node=_evidence_id(edge.to_node),
                target_slot=_slot_index(edge.to_input),
                link_type=None,
            )
        )

    nodes = tuple(
        _node_from_ir(node, incoming, outgoing, outgoing_links)
        for node in wf.nodes.values()
    )
    return GraphEvidence(node_count=len(nodes), nodes=nodes, edges=tuple(edges))


def _ingest_raw_snapshot(graph: dict[str, Any]):
    """Enter a raw dict through the named ingest door once.

    Prefer a retained :class:`WorkflowSnapshot` when the caller already
    ingested. Never re-decode raw after that ingest.

    Returns the retained snapshot (carrying the lossless raw sidecar), or
    ``None`` when no snapshot could be retained.
    """
    from vibecomfy.ingest.normalize import ingest_workflow_and_ui
    from vibecomfy.ingest.snapshot import snapshot_of

    snapshot = snapshot_of(graph)
    if snapshot is not None:
        return snapshot
    workflow, _canonical = ingest_workflow_and_ui(graph)
    return snapshot_of(workflow)


def inspect_graph(graph: dict[str, Any] | None) -> GraphEvidence:
    """Extract structured evidence from a raw workflow or retained snapshot.

    Ingests *graph* through the named door once (or consumes a retained
    :class:`WorkflowSnapshot`) and projects via :func:`inspect_workflow`.
    ``None``, empty, or uningestible input yields empty evidence. Unknown
    shape stays unknown and fails closed to empty evidence.

    RRSYN-3: the retained snapshot's raw sidecar supplies the original
    LiteGraph link ids; the retained IR copy intentionally hides its own
    snapshot metadata, so the identity is resolved HERE and passed down.
    """
    from vibecomfy.ingest.snapshot import WorkflowSnapshot, raw_link_identity

    if isinstance(graph, WorkflowSnapshot):
        return inspect_workflow(
            graph.workflow, link_identity=raw_link_identity(graph)
        )
    if not graph:
        return GraphEvidence(node_count=0)
    try:
        snapshot = _ingest_raw_snapshot(graph)
    except (TypeError, ValueError):
        return GraphEvidence(node_count=0)
    if snapshot is None:
        return inspect_workflow_from_ingest(graph)
    return inspect_workflow(
        snapshot.workflow, link_identity=raw_link_identity(snapshot)
    )


def inspect_workflow_from_ingest(graph: dict[str, Any]) -> GraphEvidence:
    """Fail-closed fallback: project without link identities (all ``None``)."""
    from vibecomfy.ingest.snapshot import snapshot_of

    retained = snapshot_of(graph)
    workflow = retained.workflow if retained is not None else graph
    try:
        return inspect_workflow(workflow)
    except (TypeError, ValueError):
        return GraphEvidence(node_count=0)




__all__ = [
    "EdgeEvidence",
    "GraphDerivations",
    "GraphEvidence",
    "NodeEvidence",
    "SlotEvidence",
    "compute_derivations",
    "derive_dormant_branches",
    "derive_expensive_or_risky",
    "derive_inputs",
    "derive_model_stack",
    "derive_orphans",
    "derive_outputs",
    "inspect_graph",
    "inspect_workflow",
    "normalise_links",
    "render_inspect_markdown",
]
