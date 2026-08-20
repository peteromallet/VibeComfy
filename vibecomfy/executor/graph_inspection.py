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
from typing import TYPE_CHECKING, Any

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
    link_id: int | None = None  # set for input slots connected to a link


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "widgets", tuple(self.widgets))
        object.__setattr__(self, "input_slots", tuple(self.input_slots))
        object.__setattr__(self, "output_slots", tuple(self.output_slots))


@dataclass(frozen=True)
class EdgeEvidence:
    """One link / edge in a ComfyUI graph."""

    link_id: int
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
    incoming: dict[str, dict[str, int]],
    outgoing: dict[str, set[str]],
) -> NodeEvidence:
    node_key = str(node.id)
    incoming_for_node = incoming.get(node_key, {})
    input_slots = tuple(
        SlotEvidence(name=name, slot_type="input", link_id=link_id)
        for name, link_id in sorted(incoming_for_node.items())
    )
    output_names = list(_declared_output_names(node))
    seen = set(output_names)
    for name in sorted(outgoing.get(node_key, set())):
        if name not in seen:
            output_names.append(name)
            seen.add(name)
    output_slots = tuple(SlotEvidence(name=name, slot_type="output") for name in output_names)
    return NodeEvidence(
        node_id=_evidence_id(node.id),
        class_type=node.class_type or "Unknown",
        title=_node_title(node),
        widgets=_widgets_from_ir(node),
        input_slots=input_slots,
        output_slots=output_slots,
        type_name=_node_type_name(node),
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
    """Node ids with no incoming linked edges (graph entry points)."""

    outputs: tuple[int | str, ...] = ()
    """Node ids with no outgoing edges (graph exit points)."""

    model_stack: tuple[int | str, ...] = ()
    """Node ids in the model-loading chain (CheckpointLoader* → MODEL consumers)."""

    dormant_branches: tuple[tuple[int | str, ...], ...] = ()
    """Disconnected subgraphs that are not reachable from the main output chain."""

    expensive_or_risky: tuple[tuple[int | str, str], ...] = ()
    """Nodes flagged as expensive or risky, each as ``(node_id, reason)``."""


def _outgoing_node_ids(evidence: GraphEvidence) -> set[int | str]:
    """Return the set of node ids that have at least one outgoing edge."""
    return {e.origin_node for e in evidence.edges}


def _incoming_linked_node_ids(evidence: GraphEvidence) -> set[int | str]:
    """Return the set of node ids that have at least one linked input slot."""
    linked: set[int | str] = set()
    for node in evidence.nodes:
        for slot in node.input_slots:
            if slot.link_id is not None:
                linked.add(node.node_id)
                break
    return linked


def derive_inputs(evidence: GraphEvidence) -> tuple[int | str, ...]:
    """Return node ids that have no linked incoming edges.

    A node is an input when none of its input slots carry a ``link_id``.
    This captures loader nodes (CheckpointLoaderSimple, LoadImage,
    EmptyLatentImage, …) and any node whose inputs are all unconnected.
    """
    linked = _incoming_linked_node_ids(evidence)
    result: list[int | str] = []
    for node in evidence.nodes:
        if node.node_id not in linked:
            result.append(node.node_id)
    return tuple(result)


def derive_outputs(evidence: GraphEvidence) -> tuple[int | str, ...]:
    """Return node ids that have no outgoing edges.

    A node is an output when no edge originates from it.  This naturally
    captures SaveImage, PreviewImage, and any terminal node.
    """
    outgoing = _outgoing_node_ids(evidence)
    result: list[int | str] = []
    for node in evidence.nodes:
        if node.node_id not in outgoing:
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


def derive_model_stack(evidence: GraphEvidence) -> tuple[int | str, ...]:
    """Return node ids in the model-loading chain.

    Starts from every node whose ``class_type`` begins with
    ``CheckpointLoader`` or ``UNETLoader`` and follows outgoing edges.
    The result is topologically sorted by discovery order (BFS).
    """
    seeds = _model_stack_seed_ids(evidence)
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
    _render_key_nodes_section(sections, evidence)

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
        # Summarize key data-flow chains
        edge_summaries: list[str] = []
        for edge in edges[:20]:
            src_label = _node_label(edge.origin_node, node_by_id)
            tgt_label = _node_label(edge.target_node, node_by_id)
            lt = f" ({edge.link_type})" if edge.link_type else ""
            edge_summaries.append(f"{src_label} → {tgt_label}{lt}")
        if edge_summaries:
            sections.append("- **Data-flow edges:**\n")
            for es in edge_summaries:
                sections.append(f"  - {es}\n")
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
) -> None:
    """Render per-node details."""
    if not evidence.nodes:
        sections.append("None detected\n")
        return

    for node in evidence.nodes:
        nid = node.node_id
        ct = node.class_type
        label = f"[{nid}] {ct}"
        if node.title:
            label += f" ({node.title})"
        sections.append(f"- **{label}**\n")
        identity = [f"class_type={ct}"]
        if node.type_name and node.type_name != ct:
            identity.append(f"type={node.type_name}")
        if node.title and node.title not in {ct, node.type_name}:
            identity.append(f"display_title={node.title}")
        sections.append(f"  - Identity: {', '.join(identity)}\n")

        # Widget values
        if node.widgets:
            widget_strs: list[str] = []
            unlabeled_count = 0
            for w in node.widgets:
                if w.name:
                    widget_strs.append(f"{w.name}={_format_widget_value(w.value)}")
                else:
                    unlabeled_count += 1
            if unlabeled_count:
                widget_strs.append(f"unlabeled_count={unlabeled_count}")
            sections.append(f"  - Widgets: {', '.join(widget_strs)}\n")
        else:
            sections.append("  - Widgets: none\n")

        # Input slots
        if node.input_slots:
            slot_strs: list[str] = []
            for slot in node.input_slots:
                if slot.link_id is not None:
                    slot_strs.append(f"{slot.name}=linked({slot.link_id})")
                else:
                    slot_strs.append(f"{slot.name}=open")
            sections.append(f"  - Input slots: {', '.join(slot_strs)}\n")
        else:
            sections.append("  - Input slots: none\n")

        # Output slots
        if node.output_slots:
            slot_names = [slot.name for slot in node.output_slots]
            sections.append(f"  - Output slots: {', '.join(slot_names)}\n")
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


def inspect_workflow(wf: VibeWorkflow) -> GraphEvidence:
    """Project structured evidence from an already-ingested :class:`VibeWorkflow`.

    Reads only IR fields (``wf.nodes``, ``wf.edges``, ``wf.widgets``,
    per-node ``raw_widgets`` / metadata furniture).  This is the product
    path; :func:`inspect_graph` is the raw-dict adapter that enters via
    the named ingest doors and then calls this function.
    """
    incoming: dict[str, dict[str, int]] = {}
    outgoing: dict[str, set[str]] = {}
    edges: list[EdgeEvidence] = []
    for index, edge in enumerate(wf.edges):
        from_node = str(edge.from_node)
        to_node = str(edge.to_node)
        to_input = str(edge.to_input)
        from_output = str(edge.from_output)
        incoming.setdefault(to_node, {})[to_input] = index
        outgoing.setdefault(from_node, set()).add(from_output)
        edges.append(
            EdgeEvidence(
                link_id=index,
                origin_node=_evidence_id(edge.from_node),
                origin_slot=_slot_index(edge.from_output),
                target_node=_evidence_id(edge.to_node),
                target_slot=_slot_index(edge.to_input),
                link_type=None,
            )
        )

    nodes = tuple(
        _node_from_ir(node, incoming, outgoing) for node in wf.nodes.values()
    )
    return GraphEvidence(node_count=len(nodes), nodes=nodes, edges=tuple(edges))


def _ingest_raw_graph(graph: dict[str, Any]) -> VibeWorkflow:
    """Enter a raw dict through the named ingest doors."""
    from vibecomfy.ingest.normalize import (
        detect_workflow_shape,
        from_api,
        from_envelope,
        from_ui,
    )

    # Dispatch by the named shape detector.  Trial-calling ``from_ui`` first
    # is unsafe because a flat API graph can be accepted as an empty UI graph,
    # silently turning a populated census into zero nodes.
    shape = detect_workflow_shape(graph)
    if shape == "api":
        # Standard ComfyUI queue/request envelopes wrap the actual API graph
        # under ``prompt``. The shape detector intentionally sees through
        # that wrapper, so the matching ingest door must do the same; passing
        # the outer envelope to ``from_api`` creates a single ``Unknown`` node.
        prompt = graph.get("prompt")
        return from_api(dict(prompt) if isinstance(prompt, dict) else graph)
    if shape == "ui":
        return from_ui(graph, use_comfy_converter=False)
    if shape == "vibe":
        return from_envelope(graph)
    raise ValueError(f"unsupported workflow shape for inspection: {shape}")


def inspect_graph(graph: dict[str, Any] | None) -> GraphEvidence:
    """Extract structured evidence from a raw workflow dict.

    Ingests *graph* through the named doors (``from_envelope`` /
    ``from_ui`` / ``from_api``) and projects via :func:`inspect_workflow`.
    ``None``, empty, or uningestible input yields empty evidence.
    """
    if not graph:
        return GraphEvidence(node_count=0)
    try:
        workflow = _ingest_raw_graph(dict(graph))
    except (TypeError, ValueError):
        return GraphEvidence(node_count=0)
    return inspect_workflow(workflow)


__all__ = [
    "EdgeEvidence",
    "GraphDerivations",
    "GraphEvidence",
    "NodeEvidence",
    "SlotEvidence",
    "WidgetEvidence",
    "compute_derivations",
    "derive_dormant_branches",
    "derive_expensive_or_risky",
    "derive_inputs",
    "derive_model_stack",
    "derive_outputs",
    "inspect_graph",
    "inspect_workflow",
    "normalise_links",
    "render_inspect_markdown",
]
