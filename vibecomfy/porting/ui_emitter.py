"""Emit a VibeWorkflow IR back to a litegraph (ComfyUI editor) JSON envelope.

This is the inverse direction of ingest: ``convert_to_vibe_format`` reads litegraph
JSON into the ``VibeWorkflow`` IR; :func:`emit_ui_json` renders an IR back out to the
litegraph shape that the ComfyUI web editor loads. It is a NEW standalone function and
deliberately NOT a ``VibeWorkflow.compile`` backend — ``compile("api")`` must stay
byte-for-byte identical and only ever produces the runtime API dict.

Identity preservation is **best-effort**, not lossless:

- ``properties["ir_node_id"]`` is the primary preserve key. It is stable for
  source-derived / raw-call nodes whose ids are explicit in the source graph (e.g.
  ``"98"``). It is NOT stable for typed-wrapper nodes whose ids are minted by
  ``VibeWorkflow._next_node_id`` — those renumber whenever a node is inserted ahead of
  them, so a round-trip can assign a different ``ir_node_id`` to the same logical node.
- ``properties["vibecomfy_id"]`` is a display-only forward label (the emitter's
  variable / role name). It renumbers on edits and must NEVER be used as a match key.
- ``properties["Node name for S&R"]`` is the litegraph node type, as the editor expects.

Node ids in the litegraph envelope are integers (the editor format requires it): digit
VibeNode ids keep their numeric value (``"98"`` → ``98``); non-digit ids are assigned
fresh integers above the highest digit id. ``properties["ir_node_id"]`` retains the
original string id as the preserve key, and parity is unaffected because the normalizer
``str()``-coerces every node id on read-back. The top-level ``links[]`` are 6-element
arrays ``[link_id, from_node, from_slot, to_node, to_slot, type]`` over those integer
ids; ``definitions.subgraphs[].links[]`` (emitted only when the IR carries definitions)
use the litegraph OBJECT shape. ``SetNode``/``GetNode`` broadcast helpers are resolved
into direct links via :func:`collect_broadcast_sources` and omitted from ``nodes``.

No promise of lossless preservation is made. The envelope is byte-deterministic for a
given IR: same IR in → same JSON out. All node geometry is stubbed and isolated in the
single :func:`_stub_layout` helper, which M2 will replace with real layout; this module
carries no layout-quality logic of its own.

``widgets_values`` emission rule (verified empirically against the parity oracle)
---------------------------------------------------------------------------------
The offline parity gate is ``_normalize_ui_to_api(emit_ui_json(wf))`` ==
``compile("api")`` (modulo node-id remapping, via ``parity.compile_equivalent``).
``_normalize_ui_to_api`` reads ``widgets_values`` *positionally* against the
**compacted** widget-name list ``_schema_input_names(provider, class_type)``, which
strips ``None``-named schema slots (the UI-only ``control_after_generate`` position).
Therefore the only array that round-trips is one laid out against that **same compacted
ordering**: position ``idx`` holds the value the node carries under
``compacted_names[idx]``, and any positions past the schema are filled from the node's
``widget_<N>`` keys at index ``N``. Trailing ``None`` is trimmed. Verified to reach
parity on every UI-shaped ``workflow_corpus/official`` workflow (13/13) and to match the
``flux2_klein_4b_t2i`` reference shape field-for-field for the round-tripping nodes.

``control_after_generate`` is **not** injected as a distinct positional element. The
normalizer's ``None``-strip means inserting it would shift every later read-back index
by one and break parity (confirmed empirically for a clean KSampler IR). When the source
graph carried a control value in its litegraph ``widgets_values``, ingest already folds
it into the compacted slot it occupied, so it rides back out at the correct litegraph
position automatically (e.g. wan_t2v KSampler ``'randomize'`` at index 1). The retained
``VibeNode.metadata["control_after_generate"]`` (T2) — or the documented ``"fixed"``
default when absent — is recorded in the recovery report under ``control_after_generate``
with a ``control_after_generate_defaulted`` flag, never silently guessed.

Input-slot ``widget`` objects: only inputs that are actually LINKED get an entry in the
node ``inputs`` array; an entry whose name is a widget-type input additionally carries
``"widget": {"name": <name>}`` (a widget converted to a link). Unlinked widget-type
inputs get NO input-slot entry — they live in ``widgets_values``.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

from vibecomfy._workflow_helpers import (
    broadcast_name,
    collect_broadcast_sources,
    is_broadcast_helper_class_type,
)
from vibecomfy.porting.widget_aliases import widget_names_for_class, widget_names_from_schema
from vibecomfy.workflow import VibeEdge

# Documented default control_after_generate mode when none is retained in metadata.
_CONTROL_AFTER_GENERATE_DEFAULT = "fixed"

# Stable namespace so a given workflow id always yields the same envelope id.
_ENVELOPE_ID_NAMESPACE = uuid.UUID("6f1d2c3a-4b5e-4a6c-8d9e-0f1a2b3c4d5e")

# Litegraph editor format version this emitter targets.
_LITEGRAPH_VERSION = 0.4

# Layout-schema version stamped into the breadcrumb (extra.vibecomfy.layout_version).
# M2 replaces _stub_layout with real layout and will bump this. M3 preserve-mode keys
# off the breadcrumb, so the version travels with the file.
_LAYOUT_VERSION = "m1"

# Default directory and subdirectory for emitted UI exports.
_DEFAULT_OUT_DIR = "out"
_UI_EXPORT_SUBDIR = "ui_export"

# Deterministic grid geometry constants used only by ``_stub_layout``.
_STUB_COLUMN_WIDTH = 400
_STUB_ROW_HEIGHT = 200
_STUB_COLUMNS = 4
_STUB_NODE_SIZE = [320, 180]

# Confidence threshold at or below which a node is considered low-confidence.
# widget_schema_fallback tier uses confidence=0.3; strict=True rejects it.
_LOW_CONFIDENCE_THRESHOLD = 0.3


def _stub_layout(order: int) -> dict[str, list[float]]:
    """Return deterministic placeholder geometry for the ``order``-th emitted node.

    ALL layout decisions live here. The grid is a pure function of emission order, so
    the same IR always produces identical positions. M2 replaces this helper with real
    layout; nothing elsewhere in the emitter reasons about geometry.
    """
    col = order % _STUB_COLUMNS
    row = order // _STUB_COLUMNS
    return {
        "pos": [float(col * _STUB_COLUMN_WIDTH), float(row * _STUB_ROW_HEIGHT)],
        "size": list(_STUB_NODE_SIZE),
    }


def _captured_geometry(node: Any) -> dict[str, list[float]] | None:
    """Return {pos, size} from ``node.metadata['_ui']``, or None when absent.

    The ``None`` fallthrough is intentional: callers should chain through to
    ``_stub_layout`` when no captured geometry exists (e.g. programmatic nodes
    or workflows loaded from a .py file without a sidecar).
    """
    _ui = getattr(node, "metadata", {}).get("_ui")
    if not isinstance(_ui, dict):
        return None
    pos = _ui.get("pos")
    size = _ui.get("size")
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        return None
    if not isinstance(size, (list, tuple)) or len(size) < 2:
        return None
    return {"pos": [float(pos[0]), float(pos[1])], "size": [float(size[0]), float(size[1])]}


def _envelope_id(wf: Any) -> str:
    """Deterministic envelope id derived from the workflow id."""
    return str(uuid.uuid5(_ENVELOPE_ID_NAMESPACE, str(getattr(wf, "id", "workflow"))))


def _source_template_name(wf: Any) -> str | None:
    """Best-effort source-template name for the breadcrumb / output path.

    Prefers an explicit source id, then the source file stem.  The ingest default
    id ``"workflow"`` (and an empty value) is treated as *unnamed* so the IR-hash
    fallback path takes over.  Returns ``None`` when no real name is available.
    """
    source = getattr(wf, "source", None)
    candidate = getattr(source, "id", None) if source is not None else None
    if isinstance(candidate, str) and candidate and candidate != "workflow":
        return candidate
    path = getattr(source, "path", None) if source is not None else None
    if isinstance(path, str) and path:
        stem = Path(path).stem
        if stem:
            return stem
    wf_id = getattr(wf, "id", None)
    if isinstance(wf_id, str) and wf_id and wf_id != "workflow":
        return wf_id
    return None


def _source_prior_path(wf: Any) -> str | None:
    """The originating file path (M3 preserve-mode reads extra.vibecomfy.prior_path)."""
    source = getattr(wf, "source", None)
    path = getattr(source, "path", None) if source is not None else None
    return path if isinstance(path, str) and path else None


def _ir_hash(wf: Any) -> str:
    """Stable short hash of the IR structure, for naming unnamed sources.

    Hashes a canonical, order-independent projection of nodes (id + class_type)
    and edges so the same IR always yields the same name and the path is never
    empty or raising.
    """
    nodes = sorted((nid, node.class_type) for nid, node in wf.nodes.items())
    edges = sorted(
        (e.from_node, e.from_output, e.to_node, e.to_input) for e in wf.edges
    )
    payload = json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _breadcrumb(wf: Any, source_template: str | None, prior_path: str | None) -> dict[str, Any]:
    """Build the ``extra.vibecomfy`` breadcrumb stamped on the envelope/subgraphs."""
    return {
        "layout_version": _LAYOUT_VERSION,
        "source_template": source_template if source_template is not None else _source_template_name(wf),
        "prior_path": prior_path if prior_path is not None else _source_prior_path(wf),
    }


def default_output_path(
    wf: Any,
    *,
    out: str | None = None,
    source_template: str | None = None,
    out_dir: str = _DEFAULT_OUT_DIR,
) -> Path:
    """Deterministic output path for an emitted UI export.

    ``--out`` (the ``out`` argument) overrides everything.  Otherwise the path is
    ``<out_dir>/ui_export/<source_template>.json`` when a source-template name is
    available, falling back to ``<out_dir>/ui_export/<ir-hash>.json`` for unnamed
    (programmatic) sources.  The fallback hash guarantees the path is never empty
    and never raises.
    """
    if out:
        return Path(out)
    name = source_template if source_template is not None else _source_template_name(wf)
    if name:
        safe = re.sub(r"[^A-Za-z0-9._/-]", "_", name)
        # Collapse path-traversal and leading separators so the name stays under out_dir.
        safe = safe.replace("..", "_").lstrip("/") or _ir_hash(wf)
    else:
        safe = _ir_hash(wf)
    return Path(out_dir) / _UI_EXPORT_SUBDIR / f"{safe}.json"


def _emission_order(wf: Any) -> list[str]:
    """Deterministic node emission order: numeric ids ascending, then lexical."""

    def key(node_id: str) -> tuple[int, str]:
        return (int(node_id), node_id) if node_id.isdigit() else (1 << 30, node_id)

    return sorted(wf.nodes.keys(), key=key)


def _build_id_remap(order_list: list[str]) -> dict[str, int]:
    """Map string VibeNode ids → litegraph integer node ids.

    Digit ids keep their numeric value (so source-derived ``"98"`` stays ``98`` and the
    envelope matches the litegraph reference field-for-field).  Non-digit ids (e.g.
    typed-wrapper labels) are assigned fresh integers above the highest digit id, never
    colliding with a preserved value.  ``properties["ir_node_id"]`` retains the original
    string id as the preserve key; this mapping only governs the litegraph ``id`` field
    and the node-id slots inside ``links[]``.
    """
    remap: dict[str, int] = {}
    used: set[int] = set()
    for node_id in order_list:
        if node_id.isdigit():
            value = int(node_id)
            remap[node_id] = value
            used.add(value)
    nxt = (max(used) + 1) if used else 1
    for node_id in order_list:
        if node_id in remap:
            continue
        while nxt in used:
            nxt += 1
        remap[node_id] = nxt
        used.add(nxt)
        nxt += 1
    return remap


def _resolve_broadcast_edges(wf: Any) -> tuple[list[Any], set[str]]:
    """Resolve SetNode/GetNode broadcast indirection into direct edges.

    Reuses :func:`collect_broadcast_sources` (porting/helpers.py) — the broadcast
    resolution is NOT reimplemented here.  A ``SetNode`` captures the value on its input
    under a broadcast name; each ``GetNode`` re-emits that name to one or more consumers
    (one source → many links).  For the litegraph envelope we drop the helper nodes and
    rewire every ``GetNode``-origin edge to the captured real source, so a fan-out of N
    consumers becomes N direct links.  Edges feeding a helper are dropped; an unresolved
    ``GetNode`` reference drops its dangling edges.

    Returns ``(effective_edges, helper_node_ids)``.  When the IR carries no helper nodes
    (the common case) the original edge list is returned unchanged, so emission stays
    byte-identical.
    """
    helper_ids = {
        node_id
        for node_id, node in wf.nodes.items()
        if is_broadcast_helper_class_type(node.class_type)
    }
    if not helper_ids:
        return list(wf.edges), helper_ids

    sources = collect_broadcast_sources(wf.nodes, wf.edges)
    get_source: dict[str, tuple[str, str]] = {}
    for node_id in helper_ids:
        node = wf.nodes[node_id]
        if node.class_type != "GetNode":
            continue
        name = broadcast_name(node)
        src = sources.get(name) if name else None
        if src is not None:
            get_source[node_id] = (str(src[0]), str(src[1]))

    effective: list[Any] = []
    for edge in wf.edges:
        if edge.to_node in helper_ids:
            continue  # edge into a SetNode/GetNode helper — not a runtime link
        if edge.from_node in helper_ids:
            redirect = get_source.get(edge.from_node)
            if redirect is None:
                continue  # unresolved broadcast — drop the dangling edge
            effective.append(VibeEdge(redirect[0], redirect[1], edge.to_node, edge.to_input))
        else:
            effective.append(edge)
    return effective, helper_ids


def _array_link_to_object(link: list[Any]) -> dict[str, Any]:
    """Convert a 6-element array link to litegraph subgraph OBJECT-link shape."""
    return {
        "id": link[0],
        "origin_id": link[1],
        "origin_slot": link[2],
        "target_id": link[3],
        "target_slot": link[4],
        "type": link[5],
    }


def _emit_definitions(wf: Any) -> dict[str, Any] | None:
    """Emit ``definitions.subgraphs[]`` from IR metadata, if any are carried.

    Subgraph links use the litegraph OBJECT shape (``id``/``origin_id``/``origin_slot``/
    ``target_id``/``target_slot``/``type``) rather than the 6-element arrays used at the
    top level; array-style links present in metadata are converted.  Each subgraph's
    ``state.lastRerouteId`` is ensured (default ``0``).  Returns ``None`` when the IR
    carries no definitions (the common post-ingest case), so the envelope omits both
    ``definitions`` and the top-level ``state`` and stays byte-identical.
    """
    metadata = getattr(wf, "metadata", None)
    defs = metadata.get("definitions") if isinstance(metadata, dict) else None
    subgraphs = defs.get("subgraphs") if isinstance(defs, dict) else None
    if not subgraphs:
        return None
    out_subgraphs: list[dict[str, Any]] = []
    for raw_sg in subgraphs:
        sg = dict(raw_sg)
        links = sg.get("links")
        if isinstance(links, list):
            sg["links"] = [
                link if isinstance(link, dict) else _array_link_to_object(link)
                for link in links
            ]
        state = dict(sg.get("state") or {})
        state.setdefault("lastRerouteId", 0)
        sg["state"] = state
        out_subgraphs.append(sg)
    return {"subgraphs": out_subgraphs}


def _resolve_output_slot_and_type(
    from_output: str,
    class_type: str,
    schema_cache: dict[str, Any],
) -> tuple[int, str]:
    """Return (slot_index, socket_type) for a VibeEdge.from_output value.

    ``from_output`` may be a numeric string (use directly) or an output NAME
    (look up list position in the schema's OutputSpec list).  UUID class types
    (subgraph nodes) pass through: if ``from_output`` is numeric it works as-is;
    if it is a name and no schema exists we return slot 0 with an empty type.
    """
    schema = schema_cache.get(class_type)
    if from_output.isdigit():
        slot = int(from_output)
        if schema is not None:
            outputs = getattr(schema, "outputs", None) or []
            if slot < len(outputs):
                return slot, outputs[slot].type or ""
        return slot, ""
    # Name lookup against OutputSpec list position
    if schema is not None:
        outputs = getattr(schema, "outputs", None) or []
        for idx, out_spec in enumerate(outputs):
            if out_spec.name == from_output:
                return idx, out_spec.type or ""
    # Unresolvable name: best-effort slot 0, empty type
    return 0, ""


def _get_node_schema_provenance(
    class_type: str,
    schema: Any,
) -> dict[str, Any]:
    """Return a provenance dict describing how the schema was sourced."""
    if schema is None:
        return {
            "provider": None,
            "confidence": None,
            "schema_less": True,
        }
    confidence = getattr(schema, "confidence", 1.0)
    provider = getattr(schema, "source_provider", "unknown")
    return {
        "provider": provider,
        "confidence": confidence,
        "schema_less": False,
    }


def _compacted_widget_names(class_type: str, schema: Any) -> list[str]:
    """Return the compacted widget-name list the normalizer reads back.

    Identical to ``_schema_input_names`` (committed table first, else provider
    schema, ``None``-named slots stripped).  Going through the same function the
    normalizer uses guarantees the emitted ``widgets_values`` ordering matches the
    read-back exactly.
    """
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return [name for name in committed if name is not None]
    return [name for name in widget_names_from_schema(class_type, schema) if name is not None]


def _full_widget_name_count(class_type: str, schema: Any) -> int | None:
    """Schema widget-slot count (including ``None`` UI-only slots), or ``None``.

    ``None`` means the class is schema-less for widget purposes (no committed
    table and no provider widget names) so the length assertion is skipped.
    """
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return len(committed)
    names = widget_names_from_schema(class_type, schema)
    return len(names) if names else None


def _build_widget_values(node: Any, compacted_names: list[str]) -> list[Any]:
    """Reverse the normalizer's positional widget read-back.

    The value pool is the node's widget-sourced data: ``node.widgets`` (``widget_<N>``
    carriers) plus ``node.inputs`` (non-link named values; link inputs never land
    here — ingest routes them to edges).  Position ``idx`` takes the value under
    ``compacted_names[idx]`` when present, else the ``widget_<idx>`` carrier; positions
    past the schema come straight from ``widget_<idx>``.  Trailing ``None`` is trimmed
    so the array matches the litegraph reference length.
    """
    pool: dict[str, Any] = {}
    pool.update(node.widgets)
    pool.update(node.inputs)

    widget_idxs: list[int] = []
    for key in pool:
        if key.startswith("widget_"):
            try:
                widget_idxs.append(int(key.split("_", 1)[1]))
            except ValueError:
                continue
    max_widget = (max(widget_idxs) + 1) if widget_idxs else 0

    length = max(len(compacted_names), max_widget)
    values: list[Any] = []
    for idx in range(length):
        if idx < len(compacted_names) and compacted_names[idx] in pool:
            values.append(pool[compacted_names[idx]])
        elif f"widget_{idx}" in pool:
            values.append(pool[f"widget_{idx}"])
        else:
            values.append(None)

    while values and values[-1] is None:
        values.pop()
    return values


def emit_ui_json(
    wf: Any,
    *,
    schema_provider: Any = None,
    layout: Any = None,
    strict: bool = False,
    recovery_report: list[dict[str, Any]] | None = None,
    source_template: str | None = None,
    prior_path: str | None = None,
) -> dict[str, Any]:
    """Render ``wf`` (a ``VibeWorkflow``) to a litegraph JSON envelope.

    Args:
        wf: The IR workflow to emit.
        schema_provider: Schema source used for slot/type resolution.  Consulted
            via ``get_schema(class_type)`` for each node.  Pass ``None`` to skip
            schema resolution (all edges emit with slot 0 and empty type).
        layout: Reserved layout hook for M2. Ignored by the stub geometry.
        strict: When ``True``, raises ``ValueError`` if any node has a schema-less
            class type (``get_schema() == None``) or a low-confidence schema
            (``confidence <= 0.3``, i.e. the ``widget_schema_fallback`` tier).
        recovery_report: Optional mutable list.  If provided, one provenance dict
            is appended per node with keys ``node_id``, ``class_type``,
            ``provider``, ``confidence``, ``schema_less``.  This is the
            **authoritative** record of which schema tier supplied each node's
            output/input resolution.

    Returns:
        A litegraph envelope dict: ``version``, deterministic ``id``,
        ``last_node_id``, ``last_link_id``, ``groups``, ``nodes``, and ``links``.
        Every node carries stamped ``properties`` and stub geometry.  Node outputs
        include ``slot_index``, ``name``, ``type``, and ``links`` (``null`` for
        unwired outputs).  The global ``links`` list holds 6-element arrays
        ``[link_id, from_node, from_slot, to_node, to_slot, type]``.
    """
    layout = layout or {}

    # Resolve SetNode/GetNode broadcast indirection into direct edges and identify the
    # helper nodes to omit from emission (no-op when the IR carries no helpers).
    effective_edges, helper_ids = _resolve_broadcast_edges(wf)

    order_list = [nid for nid in _emission_order(wf) if nid not in helper_ids]

    # Remap string node ids → litegraph integer ids (digit ids preserve their value).
    id_remap = _build_id_remap(order_list)

    # Build schema cache (one get_schema call per unique class_type)
    schema_cache: dict[str, Any] = {}
    if schema_provider is not None:
        for node_id in order_list:
            ct = wf.nodes[node_id].class_type
            if ct not in schema_cache:
                schema_cache[ct] = schema_provider.get_schema(ct)

    # Per-node provenance (keyed by node_id)
    node_prov: dict[str, dict[str, Any]] = {}
    for node_id in order_list:
        ct = wf.nodes[node_id].class_type
        schema = schema_cache.get(ct)
        prov = _get_node_schema_provenance(ct, schema)
        prov["node_id"] = node_id
        prov["class_type"] = ct
        node_prov[node_id] = prov

    # Strict check: fail early if any node is low-confidence or schema-less
    if strict:
        failures: list[str] = []
        for node_id in order_list:
            p = node_prov[node_id]
            conf = p["confidence"]
            if p["schema_less"] or (conf is not None and conf <= _LOW_CONFIDENCE_THRESHOLD):
                reason = "schema-less" if p["schema_less"] else f"confidence={conf}"
                failures.append(f"{node_id}({p['class_type']}): {reason}")
        if failures:
            raise ValueError(f"strict=True: low-confidence or schema-less nodes: {failures}")

    # Sort edges deterministically (from_node asc, from_output, to_node, to_input)
    sorted_edges = sorted(
        effective_edges,
        key=lambda e: (e.from_node.zfill(20), e.from_output, e.to_node.zfill(20), e.to_input),
    )

    # Assign deterministic link IDs (1-indexed)
    EdgeKey = tuple[str, str, str, str]
    link_id_map: dict[EdgeKey, int] = {
        (e.from_node, e.from_output, e.to_node, e.to_input): idx
        for idx, e in enumerate(sorted_edges, start=1)
    }
    last_link_id = len(sorted_edges)

    # Edge lookup by node
    edges_from: dict[str, list[Any]] = defaultdict(list)
    edges_to: dict[str, list[Any]] = defaultdict(list)
    for edge in sorted_edges:
        edges_from[edge.from_node].append(edge)
        edges_to[edge.to_node].append(edge)

    # Build nodes
    nodes: list[dict[str, Any]] = []
    last_node_id = max(id_remap.values()) if id_remap else 0

    for order, node_id in enumerate(order_list):
        node = wf.nodes[node_id]
        geometry = layout.get(node.uid) or _captured_geometry(node) or _stub_layout(order)
        schema = schema_cache.get(node.class_type)
        schema_outputs = list(getattr(schema, "outputs", None) or []) if schema else []

        # --- outputs list ---
        outputs: list[dict[str, Any]] = []
        # Build a set of (from_output_val) → links for this node from edges
        output_links_by_slot: dict[int, list[int]] = defaultdict(list)
        for edge in edges_from[node_id]:
            slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
            eid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
            output_links_by_slot[slot].append(eid)

        if schema_outputs:
            for slot_idx, out_spec in enumerate(schema_outputs):
                link_list = sorted(output_links_by_slot.get(slot_idx, []))
                outputs.append({
                    "name": out_spec.name or f"output_{slot_idx}",
                    "type": out_spec.type or "",
                    "links": link_list if link_list else None,
                    "slot_index": slot_idx,
                })
        elif edges_from[node_id]:
            # Schema-less best-effort: emit one output entry per distinct from_output value,
            # ordered by numeric slot if numeric or by appearance order otherwise.
            seen: dict[str, int] = {}
            for edge in edges_from[node_id]:
                fo = edge.from_output
                if fo not in seen:
                    seen[fo] = int(fo) if fo.isdigit() else len(seen)

            for fo, slot_idx in sorted(seen.items(), key=lambda kv: kv[1]):
                link_list = sorted(output_links_by_slot.get(slot_idx, []))
                outputs.append({
                    "name": fo if not fo.isdigit() else f"output_{slot_idx}",
                    "type": fo.upper() if not fo.isdigit() else "",
                    "links": link_list if link_list else None,
                    "slot_index": slot_idx,
                })
            # Record schema-less diagnostic in recovery_report (populated below)
            if recovery_report is not None:
                pass  # appended after the loop; diagnostic is in the provenance entry

        # --- widget metadata for this class ---
        compacted_names = _compacted_widget_names(node.class_type, schema)
        widget_name_set = set(compacted_names)
        full_committed = widget_names_for_class(node.class_type)
        if full_committed is not None:
            widget_name_set.update(n for n in full_committed if n is not None)

        # --- inputs list (sorted by to_input for determinism) ---
        # Only LINKED inputs get an input-slot entry; a linked input whose name is a
        # widget-type input additionally carries widget:{name:...} (widget→link).
        incoming_sorted = sorted(edges_to[node_id], key=lambda e: e.to_input)
        inputs: list[dict[str, Any]] = []
        for edge in incoming_sorted:
            from_class = wf.nodes[edge.from_node].class_type if edge.from_node in wf.nodes else ""
            _, socket_type = _resolve_output_slot_and_type(edge.from_output, from_class, schema_cache)
            lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
            slot: dict[str, Any] = {
                "name": edge.to_input,
                "type": socket_type or "UNKNOWN",
                "link": lid,
            }
            if edge.to_input in widget_name_set:
                slot["widget"] = {"name": edge.to_input}
            inputs.append(slot)

        # --- properties ---
        prov = node_prov[node_id]
        properties: dict[str, Any] = {
            "ir_node_id": node.id,
            "vibecomfy_id": f"{node.class_type}_{order}",
            "Node name for S&R": node.class_type,
        }
        # Optional debug stamp (provider tier)
        if not prov["schema_less"]:
            properties["_vibecomfy_schema_provider"] = prov.get("provider", "unknown")

        # ── uid stamp (M1.5): every node with a non-empty uid carries its frozen identity ──
        if node.uid:
            properties["vibecomfy_uid"] = node.uid

        # --- widgets_values (verified compacted-ordering rule; see module docstring) ---
        widget_values = _build_widget_values(node, compacted_names)

        # control_after_generate: retain from metadata or document the `fixed` default.
        retained_control = node.metadata.get("control_after_generate")
        if isinstance(retained_control, str):
            prov["control_after_generate"] = retained_control
            prov["control_after_generate_defaulted"] = False
        else:
            prov["control_after_generate"] = _CONTROL_AFTER_GENERATE_DEFAULT
            prov["control_after_generate_defaulted"] = True

        # Length validation: assert against the schema widget-slot count when the
        # class has a schema; skip + record for schema-less classes.
        expected_widget_count = _full_widget_name_count(node.class_type, schema)
        if expected_widget_count is None:
            prov["widget_length_check"] = "skipped: schema-less"
        else:
            if len(widget_values) > expected_widget_count:
                overflow_msg = f"overflow {len(widget_values)}>{expected_widget_count}"
                prov["widget_length_check"] = overflow_msg
            else:
                prov["widget_length_check"] = (
                    f"{len(widget_values)}<={expected_widget_count}"
                )

        nodes.append(
            {
                "id": id_remap[node_id],
                "type": node.class_type,
                "pos": geometry["pos"],
                "size": geometry["size"],
                "flags": {},
                "order": order,
                "mode": 0,
                "inputs": inputs,
                "outputs": outputs,
                "properties": properties,
                "widgets_values": widget_values,
            }
        )

    # Build global links array: [link_id, from_node, from_slot, to_node, to_slot, type]
    links: list[list[Any]] = []
    for edge in sorted_edges:
        from_class = wf.nodes[edge.from_node].class_type if edge.from_node in wf.nodes else ""
        from_slot, socket_type = _resolve_output_slot_and_type(edge.from_output, from_class, schema_cache)
        # to_slot = index of this input in the to-node's sorted inputs array
        incoming_sorted = sorted(edges_to[edge.to_node], key=lambda e: e.to_input)
        to_slot = next(
            (
                i
                for i, e in enumerate(incoming_sorted)
                if e.to_input == edge.to_input
                and e.from_node == edge.from_node
                and e.from_output == edge.from_output
            ),
            0,
        )
        lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
        links.append(
            [lid, id_remap[edge.from_node], from_slot, id_remap[edge.to_node], to_slot, socket_type or ""]
        )

    links.sort(key=lambda lnk: lnk[0])

    # Populate recovery_report
    if recovery_report is not None:
        for node_id in order_list:
            p = node_prov[node_id]
            entry: dict[str, Any] = {
                "node_id": node_id,
                "class_type": p["class_type"],
                "provider": p.get("provider"),
                "confidence": p.get("confidence"),
                "schema_less": p["schema_less"],
                "control_after_generate": p.get("control_after_generate"),
                "control_after_generate_defaulted": p.get("control_after_generate_defaulted"),
                "widget_length_check": p.get("widget_length_check"),
            }
            if p["schema_less"]:
                entry["diagnostic"] = "schema-less: emitting best-effort slots from link appearance order"
            elif p.get("confidence") is not None and p["confidence"] <= _LOW_CONFIDENCE_THRESHOLD:
                entry["diagnostic"] = f"low-confidence ({p['confidence']}): widget_schema_fallback"
            recovery_report.append(entry)

    # Warn for schema-less nodes when not strict
    if not strict:
        for node_id in order_list:
            p = node_prov[node_id]
            if p["schema_less"]:
                warnings.warn(
                    f"emit_ui_json: schema-less node {node_id}({p['class_type']}); "
                    "emitting best-effort slots. Pass strict=True to hard-fail.",
                    stacklevel=2,
                )

    breadcrumb = _breadcrumb(wf, source_template, prior_path)
    envelope: dict[str, Any] = {
        "id": _envelope_id(wf),
        "version": _LITEGRAPH_VERSION,
        "last_node_id": last_node_id,
        "last_link_id": last_link_id,
        "groups": [],
        "nodes": nodes,
        "links": links,
        "extra": {"vibecomfy": dict(breadcrumb)},
    }

    # Subgraph definitions (object-style links + state.lastRerouteId), if the IR carries
    # any.  When present, the top-level envelope also gains a state block carrying
    # lastRerouteId alongside the node/link counters.
    definitions = _emit_definitions(wf)
    if definitions is not None:
        for sg in definitions["subgraphs"]:
            sg_extra = dict(sg.get("extra") or {})
            sg_extra["vibecomfy"] = dict(breadcrumb)
            sg["extra"] = sg_extra
        envelope["definitions"] = definitions
        envelope["state"] = {
            "lastNodeId": last_node_id,
            "lastLinkId": last_link_id,
            "lastRerouteId": 0,
        }

    return envelope


def offline_parity_check(
    wf: Any,
    *,
    schema_provider: Any = None,
) -> tuple[bool, list[str]]:
    """Offline wiring-parity gate: emit → normalize → compare against compile("api").

    Runs ``_normalize_ui_to_api(emit_ui_json(wf))`` and compares it to
    ``wf.compile("api")`` with :func:`parity.compile_equivalent` (node-id-agnostic).
    This NEVER imports ComfyUI — it calls the pure-Python ``_normalize_ui_to_api``
    fallback directly rather than ``normalize_to_api`` (which would try the comfy
    converter).  Returns ``(equivalent, diffs)``.
    """
    from vibecomfy.ingest.normalize import _normalize_ui_to_api
    from vibecomfy.porting.parity import compile_equivalent

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, schema_provider=schema_provider)
    api = wf.compile("api")
    normalized = _normalize_ui_to_api(ui, schema_provider=schema_provider)
    return compile_equivalent(normalized, api)


def _node_schema_for_structural(
    class_type: str,
    schema_provider: Any,
    cache: dict[str, Any],
) -> Any:
    if class_type not in cache:
        cache[class_type] = (
            schema_provider.get_schema(class_type) if schema_provider is not None else None
        )
    return cache[class_type]


def structural_validate(
    envelope: dict[str, Any],
    *,
    schema_provider: Any = None,
) -> dict[str, Any]:
    """Structural-validation pass over an emitted litegraph envelope.

    Checks performed:

    - **Link endpoints exist.** Every ``links[]`` entry's ``from_node``/``to_node``
      must be a node in the envelope, and ``from_slot``/``to_slot`` must index into
      that node's ``outputs``/``inputs`` arrays.
    - **Slot counts vs schema** and **widgets_values length vs widget count** — ONLY
      for nodes that have a schema (committed widget table or provider schema).  For
      schema-less nodes these assertions are SKIPPED and the skip is recorded.

    Returns a report dict ``{"ok": bool, "errors": [...], "skipped": [...]}``.  ``ok``
    is ``True`` iff ``errors`` is empty; the caller decides whether to raise.
    """
    errors: list[str] = []
    skipped: list[dict[str, Any]] = []
    nodes_by_id = {n["id"]: n for n in envelope.get("nodes", [])}

    # 1) Link endpoints (node + slot) exist.
    for link in envelope.get("links", []):
        lid, from_node, from_slot, to_node, to_slot = link[0], link[1], link[2], link[3], link[4]
        src = nodes_by_id.get(from_node)
        dst = nodes_by_id.get(to_node)
        if src is None:
            errors.append(f"link {lid}: from_node {from_node} not in nodes")
        elif not (0 <= from_slot < len(src.get("outputs", []))):
            errors.append(
                f"link {lid}: from_slot {from_slot} out of range for node {from_node} "
                f"({len(src.get('outputs', []))} outputs)"
            )
        if dst is None:
            errors.append(f"link {lid}: to_node {to_node} not in nodes")
        elif not (0 <= to_slot < len(dst.get("inputs", []))):
            errors.append(
                f"link {lid}: to_slot {to_slot} out of range for node {to_node} "
                f"({len(dst.get('inputs', []))} inputs)"
            )

    # 2) Per-node slot/widget-length assertions for nodes WITH a schema only.
    cache: dict[str, Any] = {}
    for node in envelope.get("nodes", []):
        class_type = node["type"]
        schema = _node_schema_for_structural(class_type, schema_provider, cache)
        widget_count = _full_widget_name_count(class_type, schema)
        schema_outputs = list(getattr(schema, "outputs", None) or []) if schema else None

        if widget_count is None and not schema_outputs:
            # Schema-less for both widget and output purposes: skip + record.
            skipped.append(
                {
                    "node_id": node["id"],
                    "class_type": class_type,
                    "reason": "schema-less: slot/widget-length assertions skipped",
                }
            )
            continue

        if widget_count is not None:
            wv_len = len(node.get("widgets_values", []))
            if wv_len > widget_count:
                errors.append(
                    f"node {node['id']}({class_type}): widgets_values length {wv_len} "
                    f"exceeds schema widget count {widget_count}"
                )
        else:
            skipped.append(
                {
                    "node_id": node["id"],
                    "class_type": class_type,
                    "reason": "no widget schema: widgets_values length check skipped",
                }
            )

        if schema_outputs is not None:
            if len(node.get("outputs", [])) != len(schema_outputs):
                errors.append(
                    f"node {node['id']}({class_type}): output slot count "
                    f"{len(node.get('outputs', []))} != schema output count {len(schema_outputs)}"
                )

    return {"ok": not errors, "errors": errors, "skipped": skipped}


__all__ = [
    "emit_ui_json",
    "offline_parity_check",
    "structural_validate",
    "default_output_path",
]
