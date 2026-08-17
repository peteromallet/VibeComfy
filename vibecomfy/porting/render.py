"""Composable model-facing graph renderer (Law 4, batch 11).

One renderer, composable lenses — replacing per-stage projections and the
truncated text-summary authority::

    render(wf, "surface")                      -> str
    render(wf, lenses=("surface", "topology")) -> dict of lens values
    render_text(wf, ("surface", "topology"))   -> str  (model-facing text)

Lenses
------
``census``
    Node count + class list + reference map (what classify sees).
``surface``
    The Python-surface view: ``emit_agent_edit_python`` output — node
    inventory with named fields/sockets and explicit schema status.
``topology``
    Computed adjacency/index derived from IR edges: orphans, out/in degree,
    class index, and every edge with named endpoints.  COMPLETE — no
    truncation caps; the structured value is a tuple of
    ``(origin_uid, origin_socket, target_uid, target_input)`` facts.
``diff(Δ)``
    The accepted-batch-derived change summary (canonical Δ renders only what
    the batch contains — nothing more, nothing inferred).

The renderer is the single entry point for model-facing graph text.  A stage
requests exactly the lens set it is allowed to see — and Law 4 is ENFORCED at
this boundary, not assumed: the harness passes the reply stage's lens set as
``ceiling=`` and any requested lens outside that set raises
:class:`LensSubsetViolation` (``judge_lens ⊆ reply_lens``; the reply's lens
set is the ceiling).  ``render``/``render_text`` never return a lens the
caller did not request.

Inputs may be a :class:`~vibecomfy.workflow.VibeWorkflow` (the IR) or a raw
graph dict (converted through the ingest door — never read structurally
here).  Every lens is a pure, deterministic function of the workflow: the
same workflow renders the same string every time.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from vibecomfy.workflow import VibeWorkflow

# ── lens names ────────────────────────────────────────────────────────────────

LENS_CENSUS = "census"
LENS_SURFACE = "surface"
LENS_TOPOLOGY = "topology"
LENS_DIFF = "diff"
SUPPORTED_LENSES: frozenset[str] = frozenset(
    {LENS_CENSUS, LENS_SURFACE, LENS_TOPOLOGY, LENS_DIFF}
)

_TOPOLOGY_SOURCE_KEY = "topology_source"
_TOPOLOGY_SOURCE_COMPUTED = "computed"

_MODE_LABELS = {0: "enabled", 2: "muted", 4: "bypassed"}


class LensSubsetViolation(ValueError):
    """Law 4: a stage requested a lens the reply stage did not receive.

    Raised at the render/request boundary when ``ceiling=`` is supplied (the
    reply stage's lens set) and the requested lens set is not a subset of it.
    The reply's lens set is the ceiling: the judge cannot request a lens the
    reply didn't get.
    """


def _require_lens(name: str) -> None:
    if name not in SUPPORTED_LENSES:
        raise ValueError(
            f"Unknown render lens {name!r}; supported lenses: "
            + ", ".join(sorted(SUPPORTED_LENSES))
        )


def _enforce_ceiling(names: Iterable[str], ceiling: Iterable[str] | None) -> None:
    """Law 4: every requested lens must be within the reply's lens set.

    *names* is the requesting stage's lens set (the judge's request);
    *ceiling* is the reply stage's lens set.  When *ceiling* is ``None`` no
    enforcement applies; when supplied, any requested lens outside it is a
    typed :class:`LensSubsetViolation`.
    """
    if ceiling is None:
        return
    ceiling_set = frozenset(ceiling)
    missing = [name for name in names if name not in ceiling_set]
    if missing:
        raise LensSubsetViolation(
            "Law 4: requested lens(es) "
            + ", ".join(repr(name) for name in missing)
            + " not in the reply stage's lens set "
            + "("
            + ", ".join(sorted(ceiling_set))
            + "); judge_lens must be a subset of reply_lens — the reply's "
            "lens set is the ceiling."
        )


# ── input coercion (through the ingest door only) ─────────────────────────────


def _coerce_workflow(wf: VibeWorkflow | Mapping[str, Any]) -> VibeWorkflow:
    """Return a :class:`VibeWorkflow` for *wf*.

    ``VibeWorkflow`` inputs pass through untouched.  Raw graph dicts are
    converted through the ingest door (``from_envelope`` / ``from_ui`` /
    ``from_api``) so the renderer never reads raw graph keys itself — the
    IR is the only structural authority.
    """
    if isinstance(wf, VibeWorkflow):
        return wf
    if not isinstance(wf, Mapping):
        raise TypeError(
            "render requires a VibeWorkflow or a raw graph dict, got "
            f"{type(wf).__name__}."
        )
    from vibecomfy.ingest.normalize import (
        detect_workflow_shape,
        from_api,
        from_envelope,
        from_ui,
    )

    shape = detect_workflow_shape(dict(wf))
    if shape == "vibe":
        return from_envelope(dict(wf))
    if shape == "ui":
        # Offline normalizer only: the renderer must stay deterministic
        # without a live ComfyUI install.
        return from_ui(dict(wf), use_comfy_converter=False)
    if shape == "api":
        return from_api(dict(wf))
    raise TypeError(
        "render could not determine the shape of the raw graph dict "
        f"(detected {shape!r})."
    )


def _normalise_delta(delta: Any) -> tuple[Any, ...]:
    """Return the accepted batch as a tuple of edit ops (never None).

    Typed edit ops pass through untouched.  Canonical dict-form ops (the
    ``{"op": ...}`` mappings a durable envelope carries) are parsed through
    the edit-op grammar so the diff lens renders them with named endpoints
    (``set_node_field uid.field = value``, ``upsert_link a.X -> b.y``, ...).
    A batch that fails to parse falls back to the raw items — the renderer
    never raises on a malformed batch; it renders an unknown-op line.
    """
    if delta is None:
        return ()
    if isinstance(delta, tuple):
        items = delta
    elif isinstance(delta, Sequence) and not isinstance(delta, (str, bytes)):
        items = tuple(delta)
    else:
        items = (delta,)
    if items and all(isinstance(item, Mapping) for item in items):
        from vibecomfy.porting.edit.ops import parse_edit_delta

        try:
            return parse_edit_delta(list(items))
        except Exception:
            return items
    return items


# ── public API ────────────────────────────────────────────────────────────────


def render(
    wf: VibeWorkflow | Mapping[str, Any],
    lens: str | None = None,
    *,
    lenses: Iterable[str] | None = None,
    delta: Any = (),
    ceiling: Iterable[str] | None = None,
) -> str | tuple[tuple[str, str, str, str], ...] | dict[str, Any]:
    """Render *wf* through exactly the requested lens (set).

    Single-lens form (``lens=``) returns the lens value directly — a
    deterministic string for ``census``/``surface``/``diff`` and the
    structured tuple of edge facts for ``topology``.

    Lens-set form (``lenses=``) returns a dict keyed by lens name with the
    same per-lens values.  When ``topology`` is requested the dict also
    carries ``topology_source: "computed"``.  A lens requested is a lens
    returned — never more (Law 4: judge lens ⊆ reply lens).

    Law 4 is enforced here, not assumed: pass the reply stage's lens set as
    ``ceiling=`` and any requested lens outside it raises
    :class:`LensSubsetViolation` — the judge cannot request a lens the reply
    didn't get; the reply's lens set is the ceiling.
    """
    if lens is not None and lenses is not None:
        raise TypeError("render() accepts lens= or lenses=, not both.")
    if lens is None and lenses is None:
        raise TypeError("render() requires one of lens= or lenses=.")
    workflow = _coerce_workflow(wf)
    batch = _normalise_delta(delta)

    if lens is not None:
        _require_lens(lens)
        _enforce_ceiling((lens,), ceiling)
        return _render_lens_value(workflow, lens, batch)

    names = tuple(lenses or ())
    for name in names:
        _require_lens(name)
    _enforce_ceiling(names, ceiling)
    result: dict[str, Any] = {}
    for name in names:
        result[name] = _render_lens_value(workflow, name, batch)
    if LENS_TOPOLOGY in result:
        result[_TOPOLOGY_SOURCE_KEY] = _TOPOLOGY_SOURCE_COMPUTED
    return result


def render_text(
    wf: VibeWorkflow | Mapping[str, Any] | None,
    lenses: Iterable[str] = (LENS_SURFACE, LENS_TOPOLOGY),
    *,
    delta: Any = (),
    ceiling: Iterable[str] | None = None,
) -> str | None:
    """Render the model-facing text for the requested lens set.

    This is the single entry point stages consume for graph text.  The
    topology contribution is the COMPLETE computed view (every node, every
    edge, computed index) — no truncation.  Returns ``None`` for no graph.

    Law 4 is enforced here too: with ``ceiling=`` (the reply stage's lens
    set), any requested lens outside it raises
    :class:`LensSubsetViolation`.
    """
    if wf is None:
        return None
    workflow = _coerce_workflow(wf)
    batch = _normalise_delta(delta)
    names = tuple(lenses)
    for name in names:
        _require_lens(name)
    _enforce_ceiling(names, ceiling)
    parts: list[str] = []
    for name in names:
        if name == LENS_TOPOLOGY:
            parts.append(_render_topology_text(workflow))
        else:
            parts.append(str(_render_lens_value(workflow, name, batch)))
    return "\n\n".join(parts)


def _render_lens_value(
    workflow: VibeWorkflow,
    name: str,
    delta: tuple[Any, ...],
) -> str | tuple[tuple[str, str, str, str], ...]:
    if name == LENS_CENSUS:
        return _render_census(workflow)
    if name == LENS_SURFACE:
        return _render_surface(workflow)
    if name == LENS_TOPOLOGY:
        return _render_topology_facts(workflow)
    if name == LENS_DIFF:
        return _render_diff_summary(delta)
    raise ValueError(f"Unknown render lens {name!r}.")  # pragma: no cover


# ── node / edge helpers (pure IR reads) ───────────────────────────────────────


def _node_ref(node: Any, node_id: str) -> str:
    """Stable reference for a node: uid when present, else its node id."""
    uid = str(getattr(node, "uid", "") or "")
    return uid or str(node_id)


def _sorted_nodes(workflow: VibeWorkflow) -> list[tuple[str, Any]]:
    return sorted(workflow.nodes.items(), key=lambda item: str(item[0]))


def _sorted_edges(workflow: VibeWorkflow) -> list[Any]:
    def key(edge: Any) -> tuple[str, str, str, str]:
        return (
            str(edge.from_node),
            str(edge.from_output),
            str(edge.to_node),
            str(edge.to_input),
        )

    return sorted(workflow.edges, key=key)


def _edge_facts(workflow: VibeWorkflow) -> tuple[tuple[str, str, str, str], ...]:
    """Compute every edge as ``(origin_uid, origin_socket, target_uid, target_input)``.

    Pure function of the IR edges — nothing is truncated, nothing is
    inferred from prose.
    """
    refs: dict[str, str] = {
        str(nid): _node_ref(node, str(nid)) for nid, node in workflow.nodes.items()
    }
    facts: list[tuple[str, str, str, str]] = []
    for edge in _sorted_edges(workflow):
        origin = refs.get(str(edge.from_node), str(edge.from_node))
        target = refs.get(str(edge.to_node), str(edge.to_node))
        facts.append(
            (origin, str(edge.from_output), target, str(edge.to_input))
        )
    return tuple(facts)


def _binding_names(workflow: VibeWorkflow) -> dict[str, str]:
    """node id → emitted binding (the same pure (class, uid-order) function)."""
    from vibecomfy.porting.emit.emit_kwargs import _compute_variable_names

    return _compute_variable_names(workflow.nodes, list(workflow.edges))


# ── census lens ───────────────────────────────────────────────────────────────


def _render_census(workflow: VibeWorkflow) -> str:
    """Node count + class list + reference map (what classify sees)."""
    nodes = _sorted_nodes(workflow)
    edge_count = len(workflow.edges)
    lines = [f"## Census", f"{len(nodes)} node(s), {edge_count} edge(s)"]

    class_counts: dict[str, int] = {}
    for _, node in nodes:
        class_counts[str(node.class_type)] = class_counts.get(str(node.class_type), 0) + 1
    if class_counts:
        ordered = sorted(class_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        lines.append("class list: " + ", ".join(f"{ct} ({count})" for ct, count in ordered))
    else:
        lines.append("class list: <empty>")

    bindings = _binding_names(workflow)
    lines.append("reference map:")
    if not nodes:
        lines.append("  <empty>")
    for nid, node in nodes:
        ref = _node_ref(node, str(nid))
        binding = bindings.get(str(nid))
        suffix = f" (binding: {binding})" if binding else ""
        lines.append(f"  {ref}: {node.class_type}{suffix}")
    return "\n".join(lines)


# ── surface lens ──────────────────────────────────────────────────────────────


def _render_surface(workflow: VibeWorkflow) -> str:
    """The Python-surface view (emit_agent_edit_python output)."""
    from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python

    return emit_agent_edit_python(workflow)


# ── topology lens ─────────────────────────────────────────────────────────────


def _render_topology_facts(workflow: VibeWorkflow) -> tuple[tuple[str, str, str, str], ...]:
    """The structured topology value: every edge as a computed fact tuple."""
    return _edge_facts(workflow)


def _degree_index(workflow: VibeWorkflow) -> tuple[dict[str, int], dict[str, int]]:
    out_degree: dict[str, int] = {}
    in_degree: dict[str, int] = {}
    for edge in workflow.edges:
        out_degree[str(edge.from_node)] = out_degree.get(str(edge.from_node), 0) + 1
        in_degree[str(edge.to_node)] = in_degree.get(str(edge.to_node), 0) + 1
    return out_degree, in_degree


def _render_topology_text(workflow: VibeWorkflow) -> str:
    """Complete computed topology view: orphans, degrees, class index, edges.

    Every node and every edge is rendered — the topology lens never applies
    a ``[:5]`` / ``[:6]`` / ``[:20]`` cap.  If context length is a concern,
    that is an explicit lens/subset decision by the caller, never a silent
    truncation here.
    """
    nodes = _sorted_nodes(workflow)
    refs: dict[str, str] = {
        str(nid): _node_ref(node, str(nid)) for nid, node in nodes
    }
    facts = _edge_facts(workflow)
    out_degree, in_degree = _degree_index(workflow)
    edge_count = len(facts)

    lines = [
        f"## Topology",
        f"{len(nodes)} node(s), {edge_count} edge(s)",
    ]

    connected = set(out_degree) | set(in_degree)
    orphans = [str(nid) for nid, _ in nodes if str(nid) not in connected]
    if orphans:
        lines.append("orphans: " + ", ".join(refs.get(nid, nid) for nid in orphans))
    else:
        lines.append("orphans: <none>")

    lines.append("out_degree:")
    if nodes:
        for nid, _ in nodes:
            lines.append(f"  {refs.get(nid, nid)}: {out_degree.get(nid, 0)}")
    else:
        lines.append("  <empty>")

    lines.append("in_degree:")
    if nodes:
        for nid, _ in nodes:
            lines.append(f"  {refs.get(nid, nid)}: {in_degree.get(nid, 0)}")
    else:
        lines.append("  <empty>")

    class_index: dict[str, list[str]] = {}
    for nid, node in nodes:
        class_index.setdefault(str(node.class_type), []).append(refs.get(nid, nid))
    lines.append("class_index:")
    if class_index:
        for class_type in sorted(class_index):
            lines.append(f"  {class_type}: " + ", ".join(class_index[class_type]))
    else:
        lines.append("  <empty>")

    lines.append("edges:")
    if facts:
        for origin, origin_socket, target, target_input in facts:
            lines.append(
                f"  {origin} -> {target} ({origin}.{origin_socket} -> "
                f"{target}.{target_input})"
            )
    else:
        lines.append("  <none>")
    return "\n".join(lines)


# ── diff lens ─────────────────────────────────────────────────────────────────


def _format_diff_value(value: Any) -> str:
    if isinstance(value, str):
        return repr(value)
    return repr(value)


def _diff_op_line(op: Any) -> str:
    """One deterministic line per accepted-batch operation."""
    kind = str(getattr(op, "op", ""))
    if kind == "set_node_field":
        target = op.target
        return (
            f"set_node_field {target.uid}.{target.field_path} = "
            f"{_format_diff_value(op.value)}"
        )
    if kind == "add_node":
        fields = ", ".join(
            f"{key}={_format_diff_value(value)}"
            for key, value in sorted((op.fields or {}).items())
        )
        inputs = ", ".join(
            f"{key}={ref.uid}.{ref.output_slot}"
            for key, ref in sorted((op.inputs or {}).items())
        )
        bits = [f"add_node {op.class_type}"]
        if fields:
            bits.append(f"fields({fields})")
        if inputs:
            bits.append(f"inputs({inputs})")
        if getattr(op, "uid", None):
            bits.append(f"uid:{op.uid}")
        return " ".join(bits)
    if kind == "remove_node":
        return f"remove_node {op.target.uid}"
    if kind == "upsert_link":
        return (
            f"upsert_link {op.source.uid}.{op.source.output_slot} -> "
            f"{op.target.uid}.{op.target.input_field}"
        )
    if kind == "remove_link":
        if getattr(op, "link_id", None) is not None:
            return f"remove_link #{op.link_id}"
        if op.target is not None:
            return f"remove_link {op.target.uid}.{op.target.input_field}"
        return "remove_link"
    if kind == "set_mode":
        label = _MODE_LABELS.get(op.mode, str(op.mode))
        return f"set_mode {op.target.uid} = {label}"
    if kind == "subgraph_interface":
        return (
            f"subgraph_interface {op.action} {op.name!r} "
            f"inputs={tuple(op.inputs)!r} outputs={tuple(op.outputs)!r}"
        )
    return f"{kind} <op>"


def _render_diff_summary(delta: tuple[Any, ...]) -> str:
    """The accepted-batch-derived change summary (canonical Δ only)."""
    lines = ["## Diff"]
    if not delta:
        lines.append("No changes.")
        return "\n".join(lines)
    lines.append(f"{len(delta)} change(s):")
    for op in delta:
        lines.append("  " + _diff_op_line(op))
    return "\n".join(lines)


# ── fact pack (B04: stable IDs over canonical lens items) ────────────────────
#
# A fact pack is a flat, ID-addressable projection of the canonical lens
# items — NOT a new graph representation.  Text lenses contribute one fact
# per canonical rendered line; the topology lens contributes one fact per
# canonical edge tuple ``(origin_uid, origin_socket, target_uid, target_input)``
# (the exact items ``render(wf, "topology")`` returns).  Fact IDs are stable
# content hashes over ``(lens, index, canonical item)`` so the same workflow
# always yields the same IDs, and a cited ID always references the canonical
# item it was derived from.
#
# This is intentionally separate from the canonical topology renderer
# (:func:`_render_topology_facts` / :func:`_render_topology_text`): those keep
# Law 4's complete-topology contract (every node, every edge, no truncation),
# while the fact pack only *references* their items.  The Law 4 lens ceiling
# is enforced here exactly as in :func:`render`.


@dataclass(frozen=True)
class FactRef:
    """One stable reference to a canonical lens item (never a graph of its own)."""

    fact_id: str
    lens: str
    content: Any  # str (text line) or tuple (topology edge fact)


def _fact_id(lens: str, index: int, content: Any) -> str:
    raw = json.dumps(
        {"lens": lens, "index": index, "content": content},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return f"{lens}:{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def render_fact_pack(
    wf: VibeWorkflow | Mapping[str, Any],
    lenses: Iterable[str] = (LENS_SURFACE, LENS_TOPOLOGY),
    *,
    ceiling: Iterable[str] | None = None,
) -> tuple[FactRef, ...]:
    """Return stable fact references for the requested canonical lens items.

    The pack is a flat tuple of :class:`FactRef` in canonical order.  The
    topology lens contributes the complete canonical edge tuples (same items
    as ``render(wf, "topology")``); every other lens contributes its canonical
    rendered lines.  ``ceiling=`` enforces Law 4 exactly like :func:`render`:
    a requested lens outside the reply's lens set raises
    :class:`LensSubsetViolation`.
    """
    workflow = _coerce_workflow(wf)
    names = tuple(lenses)
    for name in names:
        _require_lens(name)
    _enforce_ceiling(names, ceiling)

    facts: list[FactRef] = []
    for name in names:
        if name == LENS_TOPOLOGY:
            for index, edge in enumerate(_edge_facts(workflow)):
                facts.append(FactRef(_fact_id(name, index, edge), name, edge))
            continue
        rendered = str(_render_lens_value(workflow, name, ()))
        for index, line in enumerate(rendered.splitlines()):
            facts.append(FactRef(_fact_id(name, index, line), name, line))
    return tuple(facts)


__all__ = [
    "FactRef",
    "LENS_CENSUS",
    "LENS_DIFF",
    "LENS_SURFACE",
    "LENS_TOPOLOGY",
    "LensSubsetViolation",
    "SUPPORTED_LENSES",
    "render",
    "render_fact_pack",
    "render_text",
]
