"""Emit a VibeWorkflow IR back to a litegraph (ComfyUI editor) JSON envelope.

This is the inverse direction of ingest: ``convert_to_vibe_format`` reads litegraph
JSON into the ``VibeWorkflow`` IR; :func:`emit_ui_json` renders an IR back out to the
litegraph shape that the ComfyUI web editor loads. It is a NEW standalone function and
deliberately NOT a ``VibeWorkflow.compile`` backend — ``compile("api")`` must stay
byte-for-byte identical and only ever produces the runtime API dict.

Identity preservation is **best-effort**, not lossless:

- ``properties["vibecomfy_uid"]`` is the stable identity key for nodes that carry a uid
  (source-derived nodes ingested from litegraph JSON). Use this for round-trip lookup.
- ``properties["vibecomfy_id"]`` is a display-only forward label (the emitter's
  variable / role name, ``{class_type}_{order}``). It renumbers on edits and must NEVER
  be used as a match key. Always present as a fallback when uid is absent.
- ``properties["Node name for S&R"]`` is the litegraph node type, as the editor expects.
- ``properties["ir_node_id"]`` is **no longer emitted** (demoted in M5). Any stale
  ``ir_node_id`` value from a captured properties blob is scrubbed before emission.
  Use :func:`vibecomfy.porting.ui_keys.node_lookup_key` to obtain the canonical key.

Node ids in the litegraph envelope are integers (the editor format requires it): digit
VibeNode ids keep their numeric value (``"98"`` → ``98``); non-digit ids are assigned
fresh integers above the highest digit id. Parity is unaffected because the normalizer
``str()``-coerces every node id on read-back. The top-level ``links[]`` are 6-element
arrays ``[link_id, from_node, from_slot, to_node, to_slot, type]`` over those integer
ids; ``definitions.subgraphs[].links[]`` (emitted only when the IR carries definitions)
use the litegraph OBJECT shape. ``SetNode``/``GetNode`` broadcast helpers are resolved
into direct links via :func:`collect_broadcast_sources` and omitted from ``nodes``.

No promise of lossless preservation is made. The envelope is byte-deterministic for a
given IR: same IR in → same JSON out. All node geometry is stubbed and isolated in the
single :func:`_stub_layout` helper, which M2 will replace with real layout; this module
carries no layout-quality logic of its own.

``widgets_values`` emission rule (verified empirically against the Comfy oracle)
-------------------------------------------------------------------------------
ComfyUI's ``convert_ui_to_api`` reads ``widgets_values`` *positionally* against the
raw object-info widget order, including ``None``-named UI-only slots such as
KSampler's ``control_after_generate`` position. Therefore the emitted array is laid
out against that raw order: named positions take the node's current value, ``None``
positions preserve the captured source value when available, and seed control slots
fall back to the documented ``"fixed"`` value. Trailing ``None`` is trimmed.

The retained ``VibeNode.metadata["control_after_generate"]`` — or the documented
``"fixed"`` default when absent — is recorded in the recovery report under
``control_after_generate`` with a ``control_after_generate_defaulted`` flag.

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
from copy import deepcopy
from pathlib import Path
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vibecomfy._workflow_helpers import (
    broadcast_name,
    collect_broadcast_sources,
    is_broadcast_helper_class_type,
)
from vibecomfy.contracts.intent_nodes import (
    CLASS_TYPE_TO_KIND,
    KIND_TO_CLASS_TYPE,
    is_intent_class_type,
    intent_node_payload_from_metadata,
    validate_intent_node_contract,
    validate_runtime_code_contract,
)
from vibecomfy.porting.uid import mint_local_uid
from vibecomfy.porting.widget_aliases import widget_names_for_class, widget_names_from_schema
from vibecomfy.workflow import VibeEdge

# Documented default control_after_generate mode when none is retained in metadata.
_CONTROL_AFTER_GENERATE_DEFAULT = "fixed"

# Stable namespace so a given workflow id always yields the same envelope id.
_ENVELOPE_ID_NAMESPACE = uuid.UUID("6f1d2c3a-4b5e-4a6c-8d9e-0f1a2b3c4d5e")

# Litegraph editor format version this emitter targets.
_LITEGRAPH_VERSION = 1.0

# Layout-schema version stamped into the breadcrumb (extra.vibecomfy.layout_version).
# M2 replaces _stub_layout with real layout and will bump this. M3 preserve-mode keys
# off the breadcrumb, so the version travels with the file.
_LAYOUT_VERSION = "m4"

# Default directory and subdirectory for emitted UI exports.
_DEFAULT_OUT_DIR = "out"
_UI_EXPORT_SUBDIR = "ui_export"

# Deterministic grid geometry constants used only by ``_stub_layout``.
_STUB_COLUMN_WIDTH = 400
_STUB_ROW_HEIGHT = 200
_STUB_COLUMNS = 4
_STUB_NODE_SIZE = [320, 180]

# M2 canonicalization precision (2 decimal places) for all emitted coordinates.
# Every pos/size/group-bounding value is rounded through this precision so two
# machines emit byte-identical JSON regardless of CWD, env, or float quirks.
_M2_PRECISION = 2

# Fixed default canvas drag/scale state for ``extra.ds`` when
# ``include_main_positions=True`` and no sidecar ``extra`` provides overrides.
_DEFAULT_DS = {"scale": 1.0, "offset": [0.0, 0.0]}


def _intent_recovery_fields(node: Any) -> dict[str, Any]:
    class_type = str(getattr(node, "class_type", ""))
    payload = intent_node_payload_from_metadata(getattr(node, "metadata", None))
    intent_result = validate_intent_node_contract(
        node_id=str(getattr(node, "id", "")),
        class_type=class_type,
        metadata=getattr(node, "metadata", None),
    )
    runtime_result = validate_runtime_code_contract(
        class_type=class_type,
        payload=payload,
        require_runtime=True,
    )
    runtime_backed = (
        class_type == KIND_TO_CLASS_TYPE["code"]
        and intent_result.ok
        and runtime_result.ok
    )
    return {
        "uid": getattr(node, "uid", None) or intent_result.vibecomfy_uid,
        "kind": intent_result.kind or CLASS_TYPE_TO_KIND.get(class_type),
        "lowered": False,
        "runtime_backed": runtime_backed,
        "runtime_contract_valid": runtime_result.ok,
        "intent_contract_valid": intent_result.ok,
        "contract_problem_codes": [
            problem.code for problem in (*intent_result.problems, *runtime_result.problems)
        ],
    }

# Confidence threshold at or below which a node is considered low-confidence.
# widget_schema_fallback tier uses confidence=0.3; strict=True rejects it.
_LOW_CONFIDENCE_THRESHOLD = 0.3
_STATIC_WIDGET_OVERFLOW_TOLERANCE = 4
_STATIC_RAW_WIDGET_SLACK_CLASSES = frozenset(
    {"CheckpointLoaderSimple", "KSampler", "KSamplerAdvanced"}
)


@dataclass(frozen=True, slots=True)
class WidgetShapeEvidence:
    node_id: str
    class_type: str
    schema_less: bool
    confidence: float | None
    raw_widget_count: int | None
    candidate_widget_count: int
    schema_widget_count: int | None
    compacted_widget_names: tuple[str, ...]
    raw_widget_shape: str | None
    has_dict_rows: bool
    overflow: bool
    provider: str | None


def _canonicalize_coord(value: float) -> float:
    """Round a coordinate value to M2 precision (2 decimal places).

    Every pos/size/group-bounding value emitted by this module passes through this
    helper so two machines produce byte-identical JSON regardless of CWD, env,
    or minor float-representation differences.
    """
    return round(value, _M2_PRECISION)


def _canonicalize_group_geometry(groups: list[dict[str, Any]]) -> None:
    """Canonicalize ``bounding`` arrays in-place for every group in ``groups``.

    Each group's ``bounding`` is ``[x, y, width, height]`` — all four values are
    rounded to M2 precision.  Groups without a valid ``bounding`` are left alone.
    This guarantees byte-identical group geometry across machines when
    ``include_main_positions=True``.
    """
    for g in groups:
        bbox = g.get("bounding")
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            g["bounding"] = [
                _canonicalize_coord(float(bbox[0])),
                _canonicalize_coord(float(bbox[1])),
                _canonicalize_coord(float(bbox[2])),
                _canonicalize_coord(float(bbox[3])),
            ]


def _stub_layout(order: int) -> dict[str, list[float]]:
    """Return deterministic placeholder geometry for the ``order``-th emitted node.

    ALL layout decisions live here. The grid is a pure function of emission order, so
    the same IR always produces identical positions. M2 replaces this helper with real
    layout; nothing elsewhere in the emitter reasons about geometry.
    """
    col = order % _STUB_COLUMNS
    row = order // _STUB_COLUMNS
    return {
        "pos": [
            _canonicalize_coord(float(col * _STUB_COLUMN_WIDTH)),
            _canonicalize_coord(float(row * _STUB_ROW_HEIGHT)),
        ],
        "size": [_canonicalize_coord(s) for s in _STUB_NODE_SIZE],
    }


def _extract_geometry(layout_entry: dict | None) -> dict[str, list[float]] | None:
    """Extract {pos, size} from a layout-store entry, or None.

    This isolates the pos/size geometry chain from the furniture resolver so the
    two paths never accidentally couple.  A layout entry that is ``None`` or
    lacks a valid ``pos`` returns ``None``, letting the caller fall through to
    ``_captured_geometry`` or ``_stub_layout``.
    """
    if not isinstance(layout_entry, dict):
        return None
    pos = layout_entry.get("pos")
    size = layout_entry.get("size")
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        return None
    if not isinstance(size, (list, tuple)) or len(size) < 2:
        return None
    return {
        "pos": [_canonicalize_coord(float(pos[0])), _canonicalize_coord(float(pos[1]))],
        "size": [_canonicalize_coord(float(size[0])), _canonicalize_coord(float(size[1]))],
    }


def _resolve_furniture(
    node: Any,
    layout_entry: dict | None,
) -> dict[str, Any]:
    """Resolve furniture (flags, color, bgcolor, mode, properties, title) from sidecar or metadata.

    This is a SEPARATE path from the pos/size geometry chain
    (:func:`_captured_geometry`).  Precedence:

    1. Sidecar entry (``layout_entry``) — the authoritative source when a
       ``.layout.json`` sidecar exists.
    2. ``node.metadata['_ui']`` — the raw litegraph node dict captured during
       ingest (the direct-ingest / comfy-gate fallback).
    3. Fixed defaults (``flags={}``, ``mode=0``, ``color=None``, ``bgcolor=None``,
       ``properties={}``, ``title=None``).

    Returns a dict with keys ``flags``, ``color``, ``bgcolor``, ``mode``,
    ``properties``, ``title``.
    """
    # Source 1: sidecar entry (authoritative)
    if layout_entry:
        flags = layout_entry.get("flags")
        color = layout_entry.get("color")
        bgcolor = layout_entry.get("bgcolor")
        mode = layout_entry.get("mode")
        properties = layout_entry.get("properties")
        title = layout_entry.get("title")
    else:
        # Source 2: node.metadata['_ui'] (direct-ingest fallback)
        _ui = getattr(node, "metadata", {}).get("_ui")
        if isinstance(_ui, dict):
            flags = _ui.get("flags")
            color = _ui.get("color")
            bgcolor = _ui.get("bgcolor")
            mode = _ui.get("mode")
            properties = _ui.get("properties")
            title = _ui.get("title")
        else:
            flags = None
            color = None
            bgcolor = None
            mode = None
            properties = None
            title = None

    # Source 3: fixed defaults
    if not isinstance(flags, dict):
        flags = {}
    if mode is None or not isinstance(mode, int):
        mode = 0
    if not isinstance(properties, dict):
        properties = {}
    # title stays None for absent/default — the caller decides whether to emit it

    return {
        "flags": flags,
        "color": color,
        "bgcolor": bgcolor,
        "mode": mode,
        "properties": properties,
        "title": title,
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
    return {
        "pos": [_canonicalize_coord(float(pos[0])), _canonicalize_coord(float(pos[1]))],
        "size": [_canonicalize_coord(float(size[0])), _canonicalize_coord(float(size[1]))],
    }


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
    colliding with a preserved value.  This mapping only governs the litegraph ``id`` field
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


# ── Virtual-wire classification ────────────────────────────────────────────
# Get/Set broadcast wires + Reroute passthrough are the virtual-wire nodes
# whose stable channel name (not the edge) is the routing key.
_VIRTUAL_WIRE_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})


def _resolve_broadcast_edges(
    wf: Any,
) -> tuple[list[Any], set[str], set[str]]:
    """Resolve SetNode/GetNode broadcast indirection into direct edges.

    Reuses :func:`collect_broadcast_sources` (porting/helpers.py) — the broadcast
    resolution is NOT reimplemented here.  A ``SetNode`` captures the value on its input
    under a broadcast name; each ``GetNode`` re-emits that name to one or more consumers
    (one source → many links).  For the litegraph envelope we drop the helper nodes and
    rewire every ``GetNode``-origin edge to the captured real source, so a fan-out of N
    consumers becomes N direct links.  Edges feeding a helper are dropped; an unresolved
    ``GetNode`` reference drops its dangling edges.

    Returns ``(effective_edges, broadcast_helper_ids, orphaned_get_ids)`` where
    *orphaned_get_ids* are GetNode IDs whose broadcast name could not be resolved
    to a SetNode source (used for the recovery report in display mode).  When the
    IR carries no broadcast helpers (the common case) the original edge list is
    returned unchanged, so emission stays byte-identical.
    """
    helper_ids = {
        node_id
        for node_id, node in wf.nodes.items()
        if is_broadcast_helper_class_type(node.class_type)
    }
    if not helper_ids:
        return list(wf.edges), helper_ids, set()

    sources = collect_broadcast_sources(wf.nodes, wf.edges)
    get_source: dict[str, tuple[str, str]] = {}
    orphaned: set[str] = set()
    for node_id in helper_ids:
        node = wf.nodes[node_id]
        if node.class_type != "GetNode":
            continue
        name = broadcast_name(node)
        src = sources.get(name) if name else None
        if src is not None:
            get_source[node_id] = (str(src[0]), str(src[1]))
        else:
            orphaned.add(node_id)

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
    return effective, helper_ids, orphaned


def _resolve_reroute_edges(
    edges: list[Any],
    nodes: dict[str, Any],
) -> list[Any]:
    """Passthrough Reroute nodes: A→Reroute→B becomes A→B (transitive chains).

    Returns a new edge list where every edge that originates from a Reroute is
    rewritten to originate from the terminal non-Reroute source, and edges into
    Reroutes are dropped.  When no Reroute nodes exist the list is returned
    unchanged.
    """
    reroute_ids = {nid for nid, n in nodes.items() if n.class_type == "Reroute"}
    if not reroute_ids:
        return list(edges)

    # Build inbound map: reroute_id → [(from_node, from_output), ...]
    inbound: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        if edge.to_node in reroute_ids:
            inbound.setdefault(edge.to_node, []).append(
                (edge.from_node, edge.from_output)
            )

    # Recursive terminal-source lookup (follows Reroute chains transitively)
    def _terminal(nid: str, visited: frozenset[str]) -> tuple[str, str] | None:
        if nid in visited:
            return None
        ins = inbound.get(nid, [])
        if not ins:
            return None
        src_id, src_out = ins[0]
        if src_id in reroute_ids:
            return _terminal(src_id, visited | {nid})
        return (src_id, src_out)

    result: list[Any] = []
    for edge in edges:
        if edge.from_node in reroute_ids:
            terminal = _terminal(edge.from_node, frozenset())
            if terminal is None:
                continue  # orphaned Reroute — drop
            result.append(
                VibeEdge(terminal[0], terminal[1], edge.to_node, edge.to_input)
            )
        elif edge.to_node in reroute_ids:
            continue  # edge into a Reroute — dropped
        else:
            result.append(edge)
    return result


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
    ``state.lastRerouteId`` is ensured (default ``0``).

    Step 6 (T8): Every inner subgraph node has ``properties['vibecomfy_uid']`` stamped
    via ``mint_local_uid`` (pre-existing uid wins, otherwise the inner integer id).
    Returns ``None`` when the IR carries no definitions (the common post-ingest case),
    so the envelope omits both ``definitions`` and the top-level ``state`` and stays
    byte-identical.
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
        # ── T8: stamp vibecomfy_uid on every inner subgraph node ──
        inner_nodes = sg.get("nodes")
        if isinstance(inner_nodes, list):
            for inner_node in inner_nodes:
                if isinstance(inner_node, dict):
                    props = inner_node.get("properties")
                    if not isinstance(props, dict):
                        props = {}
                        inner_node["properties"] = props
                    if "vibecomfy_uid" not in props:
                        local_uid = mint_local_uid(
                            inner_node, str(inner_node.get("id", ""))
                        )
                        props["vibecomfy_uid"] = local_uid
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


def _widget_names_for_emission(class_type: str, schema: Any) -> list[str | None]:
    """Return the raw widget-name list ComfyUI reads positionally.

    ComfyUI's ``convert_ui_to_api`` consumes ``widgets_values`` against the raw
    object-info widget order, including ``None`` UI-only positions such as
    KSampler's control-after-generate slot.  Emitting a compacted list shifts
    later values into the wrong fields.
    """
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return list(committed)
    return list(widget_names_from_schema(class_type, schema))


def _raw_widget_order_from_provider(
    class_type: str,
    schema_provider: Any | None,
) -> list[str | None] | None:
    """Return the raw ``object_info_widget_order`` including ``None`` entries.

    Probes the provider for a ``raw_widget_order`` method (added to
    ``ObjectInfoIndexSchemaProvider``) or, when the provider is a
    ``ConversionSchemaProvider``, reaches into its ``_object_info_index``
    delegate.  Returns ``None`` when no raw order is available.
    """
    if schema_provider is None:
        return None
    # Direct method (e.g. ObjectInfoIndexSchemaProvider.raw_widget_order)
    raw_method = getattr(schema_provider, "raw_widget_order", None)
    if callable(raw_method):
        try:
            result = raw_method(class_type)
            if isinstance(result, list):
                return result
        except Exception:
            pass
    # ConversionSchemaProvider delegates to _object_info_index
    obj_idx = getattr(schema_provider, "_object_info_index", None)
    if obj_idx is not None:
        raw_method = getattr(obj_idx, "raw_widget_order", None)
        if callable(raw_method):
            try:
                result = raw_method(class_type)
                if isinstance(result, list):
                    return result
            except Exception:
                pass
    return None


# Schema inputs whose type suggests a seed-bearing INT field that ComfyUI
# pairs with a ``control_after_generate`` widget slot.
_SEED_INPUT_NAMES: frozenset[str] = frozenset({"seed", "noise_seed"})

# Input-name suffixes that signal an upload widget slot.
_UPLOAD_SUFFIXES: tuple[str, ...] = ("_upload",)


def _extra_widgets_after(
    class_type: str,
    schema: Any | None,
    schema_provider: Any | None = None,
) -> list[str | None]:
    """Offline heuristic: extra widget slots beyond the schema/widget table.

    Only fires when the *snapshot* lacks the class (raw_widget_order is None
    or empty).  Heuristics:

    - ``control_after_generate`` (``None``-named UI-only slot) appended when
      any input is an INT ``seed`` or ``noise_seed``.
    - An upload slot (``None``-named) appended when any input name ends with
      ``_upload`` and its type is ``IMAGE``, ``VIDEO``, or ``AUDIO``.

    These are marked as informational ``guess`` entries in the recovery report
    and do NOT trigger ``--strict`` failures.
    """
    raw = _raw_widget_order_from_provider(class_type, schema_provider)
    if raw is not None and len(raw) > 0:
        # Snapshot HAS the class — raw order is authoritative, no guessing.
        return []

    # Snapshot lacks the class — apply heuristics (informational only).
    hints: list[str | None] = []

    # control_after_generate for INT seed/noise_seed fields
    has_seed = False
    if schema is not None:
        inputs = getattr(schema, "inputs", None)
        if isinstance(inputs, dict):
            for name, spec in inputs.items():
                input_type = str(getattr(spec, "type", "") or "").upper()
                if name in _SEED_INPUT_NAMES and input_type == "INT":
                    has_seed = True
                    break
    if has_seed:
        hints.append(None)  # control_after_generate is a None-named slot

    # Upload slot for image/video/audio+_upload input names
    upload_types = frozenset({"IMAGE", "VIDEO", "AUDIO"})
    if schema is not None:
        inputs = getattr(schema, "inputs", None)
        if isinstance(inputs, dict):
            for name, spec in inputs.items():
                input_type = str(getattr(spec, "type", "") or "").upper()
                if name.endswith(_UPLOAD_SUFFIXES) and input_type in upload_types:
                    hints.append(None)  # upload is a None-named slot
                    break

    return hints


def _full_widget_name_count(
    class_type: str,
    schema: Any,
    *,
    schema_provider: Any | None = None,
) -> int | None:
    """Schema widget-slot count (including ``None`` UI-only slots), or ``None``.

    Precedence:
    1. Raw ``object_info_widget_order`` from the provider (nulls included)
       — the authoritative slot count when the snapshot has the class.
    2. Committed ``WIDGET_SCHEMA`` table.
    3. Provider schema (null-free by construction).

    ``None`` means the class is schema-less for widget purposes so the
    length assertion is skipped.
    """
    # 1. Raw object_info_widget_order (authoritative, nulls included)
    raw = _raw_widget_order_from_provider(class_type, schema_provider)
    if raw is not None and len(raw) > 0:
        return len(raw)

    # 2. Committed table
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return len(committed)

    # 3. Provider schema (null-free)
    names = widget_names_from_schema(class_type, schema)
    return len(names) if names else None


def _build_widget_values(node: Any, widget_names: list[str | None]) -> list[Any]:
    """Reverse the normalizer's positional widget read-back.

    The value pool is the node's widget-sourced data: ``node.widgets`` (``widget_<N>``
    carriers) plus ``node.inputs`` (non-link named values; link inputs never land
    here — ingest routes them to edges).  Position ``idx`` takes the value under
    ``widget_names[idx]`` when present, else the captured raw widget value at that
    position, else the ``widget_<idx>`` carrier.  ``None`` slots are UI-only widget
    positions; preserve their captured value, or emit the retained/default
    control-after-generate value when available.  Trailing ``None`` is trimmed so
    the array matches the litegraph reference length.
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

    raw_ui = getattr(node, "metadata", {}).get("_ui", {})
    raw_widgets = raw_ui.get("widgets_values") if isinstance(raw_ui, dict) else None
    if not isinstance(raw_widgets, list):
        raw_widgets = []

    has_seed_control_slot = any(
        isinstance(name, str) and name in _SEED_INPUT_NAMES
        for name in widget_names
    )
    length = max(len(widget_names), max_widget, len(raw_widgets))
    values: list[Any] = []
    for idx in range(length):
        name = widget_names[idx] if idx < len(widget_names) else None
        if isinstance(name, str) and name in pool:
            values.append(pool[name])
        elif f"widget_{idx}" in pool:
            values.append(pool[f"widget_{idx}"])
        elif idx < len(raw_widgets):
            values.append(raw_widgets[idx])
        elif name is None and isinstance(node.metadata.get("control_after_generate"), str):
            values.append(node.metadata["control_after_generate"])
        elif name is None and has_seed_control_slot:
            values.append(_CONTROL_AFTER_GENERATE_DEFAULT)
        else:
            values.append(None)

    while values and values[-1] is None:
        values.pop()
    return values


def _schema_for_provider(schema_provider: Any | None, class_type: str) -> Any | None:
    if schema_provider is None:
        return None
    getter = getattr(schema_provider, "get_schema", None) or getattr(schema_provider, "get", None)
    if not callable(getter):
        return None
    return getter(class_type)


def _raw_widget_shape_from_value(values: Any) -> tuple[int, str, bool]:
    if values is None:
        return 0, "none", False
    if isinstance(values, dict):
        return len(values), "dict", True
    if isinstance(values, list):
        return len(values), "list", any(isinstance(item, dict) for item in values)
    return 1, "scalar", False


def _raw_widget_shape_from_node(node: Any) -> tuple[int | None, str | None, bool]:
    raw_widgets = getattr(node, "raw_widgets", None)
    if raw_widgets is not None:
        return (
            int(getattr(raw_widgets, "length", 0)),
            str(getattr(raw_widgets, "shape", "unknown")),
            bool(getattr(raw_widgets, "has_dict_rows", False)),
        )

    raw_ui = getattr(node, "metadata", {}).get("_ui")
    if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
        count, shape, has_dict_rows = _raw_widget_shape_from_value(raw_ui.get("widgets_values"))
        return count, shape, has_dict_rows

    return None, None, False


def extract_raw_ui_node_map(
    ui_payload: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return full raw LiteGraph node payloads keyed by stable lookup ids.

    This is deliberately separate from ``prior_store``.  The layout store is a
    furniture/identity envelope built by :func:`store_from_ui_json`; it must not
    become evidence that a dynamic widget node can be preserved opaque.  Pinning
    decisions need the original full node dict from an actual UI JSON payload.
    """
    if not isinstance(ui_payload, Mapping):
        return {}
    nodes = ui_payload.get("nodes")
    if not isinstance(nodes, list):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        node_copy = dict(raw_node)
        node_id = raw_node.get("id")
        if node_id is not None:
            out[str(node_id)] = node_copy
        props = raw_node.get("properties")
        if isinstance(props, Mapping):
            uid = props.get("vibecomfy_uid")
            if uid:
                out[str(uid)] = node_copy
    return out


def _raw_ui_node_for_node(
    node_id: str,
    node: Any,
    raw_ui_node_map: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    uid = getattr(node, "uid", "")
    if raw_ui_node_map:
        if uid and uid in raw_ui_node_map:
            return raw_ui_node_map[uid]
        if node_id in raw_ui_node_map:
            return raw_ui_node_map[node_id]
    raw_ui = getattr(node, "metadata", {}).get("_ui")
    if isinstance(raw_ui, Mapping) and "widgets_values" in raw_ui:
        return raw_ui
    return None


def _layout_entry_for_widget_shape(
    node_id: str,
    node: Any,
    matched_entries: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    uid = getattr(node, "uid", "")
    key = uid or node_id
    entry = matched_entries.get(key)
    if entry is not None:
        return entry
    raw_ui = getattr(node, "metadata", {}).get("_ui")
    if isinstance(raw_ui, Mapping):
        return raw_ui
    return None


def _jsonable_widget_shape_value(value: Any) -> Any:
    raw_value = getattr(value, "value", value)
    if isinstance(raw_value, Mapping):
        return {str(k): _jsonable_widget_shape_value(v) for k, v in raw_value.items()}
    if isinstance(raw_value, tuple):
        return [_jsonable_widget_shape_value(v) for v in raw_value]
    if isinstance(raw_value, list):
        return [_jsonable_widget_shape_value(v) for v in raw_value]
    if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
        return raw_value
    return repr(raw_value)


def _widget_shape_evidence_summary(evidence: WidgetShapeEvidence) -> dict[str, Any]:
    return {
        "node_id": evidence.node_id,
        "class_type": evidence.class_type,
        "schema_less": evidence.schema_less,
        "confidence": evidence.confidence,
        "raw_widget_count": evidence.raw_widget_count,
        "candidate_widget_count": evidence.candidate_widget_count,
        "schema_widget_count": evidence.schema_widget_count,
        "raw_widget_shape": evidence.raw_widget_shape,
        "has_dict_rows": evidence.has_dict_rows,
        "overflow": evidence.overflow,
        "provider": evidence.provider,
    }


def _widget_shape_report_fields(verdict: Any) -> dict[str, Any]:
    reasons = [_jsonable_widget_shape_value(reason) for reason in getattr(verdict, "reasons", ())]
    fields: dict[str, Any] = {
        "widget_shape_verdict": _jsonable_widget_shape_value(getattr(verdict, "decision", None)),
    }
    if reasons:
        fields["widget_shape_reasons"] = reasons
    if getattr(verdict, "pin_opaque", False) or getattr(verdict, "refuse", False):
        details: dict[str, Any] = {
            "reasons": reasons,
            "evidence": _widget_shape_evidence_summary(verdict.evidence),
        }
        if getattr(verdict, "field_delta", None):
            details["field_delta"] = _jsonable_widget_shape_value(verdict.field_delta)
        if getattr(verdict, "link_delta", None):
            details["link_delta"] = _jsonable_widget_shape_value(verdict.link_delta)
        fields["widget_shape_details"] = details
    return fields


def _node_delta(
    deltas: Mapping[str, Mapping[str, Any]],
    node_id: str,
    node: Any,
) -> Mapping[str, Any]:
    uid = getattr(node, "uid", "")
    if uid and uid in deltas:
        return deltas[uid]
    return deltas.get(node_id, {})


def _split_widget_shape_deltas(
    deltas: Mapping[str, Mapping[str, Any]],
    node_id: str,
    node: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    delta = dict(_node_delta(deltas, node_id, node))
    field_delta: dict[str, Any] = {}
    link_delta: dict[str, Any] = {}
    if "widget_values_sig" in delta:
        field_delta["widgets_values"] = delta["widget_values_sig"]
    if "public_input_binding" in delta:
        field_delta["public_input_binding"] = delta["public_input_binding"]
    for key in ("incoming_edge_sig", "outgoing_edge_sig"):
        if key in delta:
            link_delta[key] = delta[key]
    for key, value in delta.items():
        if key not in {
            "widget_values_sig",
            "public_input_binding",
            "incoming_edge_sig",
            "outgoing_edge_sig",
        }:
            field_delta[key] = value
    return field_delta, link_delta


def _build_recovery_entry(
    p: Mapping[str, Any],
    verdict: Any,
    *,
    has_raw_ui_payload: bool,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "node_id": p["node_id"],
        "class_type": p["class_type"],
        "provider": p.get("provider"),
        "confidence": p.get("confidence"),
        "schema_less": p["schema_less"],
        "control_after_generate": p.get("control_after_generate"),
        "control_after_generate_defaulted": p.get("control_after_generate_defaulted"),
        "widget_length_check": p.get("widget_length_check"),
        "has_raw_ui_payload": has_raw_ui_payload,
    }
    entry.update(_widget_shape_report_fields(verdict))
    if p.get("widget_order_guesses"):
        entry["widget_order_guesses"] = p["widget_order_guesses"]
    if p["schema_less"]:
        entry["diagnostic"] = "schema-less: emitting best-effort slots from link appearance order"
    elif p.get("confidence") is not None and p["confidence"] <= _LOW_CONFIDENCE_THRESHOLD:
        entry["diagnostic"] = f"low-confidence ({p['confidence']}): widget_schema_fallback"
    return entry


def _pinned_link_ref_refusal(
    node_id: str,
    class_type: str,
    reason: str,
    *,
    details: Mapping[str, Any],
) -> None:
    from vibecomfy.porting.refuse import RefusedEmit  # noqa: PLC0415

    typed_reason = (
        "pinned_link_id_mismatch"
        if reason
        in {
            "unmappable_input_link",
            "ambiguous_input_link",
            "missing_raw_input_link",
            "unmappable_output_links",
            "output_link_count_mismatch",
            "missing_raw_output_links",
            "missing_raw_output_slot",
        }
        else "pinned_link_surface_changed"
    )

    raise RefusedEmit(
        f"Refusing to emit pinned raw UI node {node_id}: {typed_reason}",
        diff={
            str(node_id): {
                "axis": "pinned_link_refs",
                "node_id": str(node_id),
                "class_type": class_type,
                "reason": typed_reason,
                "details": {**dict(details), "original_reason": reason},
            }
        },
    )


def _coerce_link_refs(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _normalize_pinned_node_link_refs(
    node_dict: dict[str, Any],
    *,
    node_id: str,
    class_type: str,
    incoming_link_ids_by_input: Mapping[str, list[int]],
    outgoing_link_ids_by_slot: Mapping[int, list[int]],
) -> dict[str, Any]:
    """Rewrite copied pinned-node link refs to the emitted global ``links[]`` ids."""
    raw_inputs = node_dict.get("inputs") or []
    if not isinstance(raw_inputs, list):
        _pinned_link_ref_refusal(
            node_id,
            class_type,
            "invalid_raw_inputs",
            details={"raw_inputs_type": type(raw_inputs).__name__},
        )

    seen_linked_inputs: set[str] = set()
    for idx, raw_input in enumerate(raw_inputs):
        if not isinstance(raw_input, dict) or raw_input.get("link") is None:
            continue
        input_name = raw_input.get("name")
        if input_name is None:
            _pinned_link_ref_refusal(
                node_id,
                class_type,
                "unmappable_input_link",
                details={"input_index": idx, "raw_link": raw_input.get("link")},
            )
        input_key = str(input_name)
        if input_key in seen_linked_inputs:
            _pinned_link_ref_refusal(
                node_id,
                class_type,
                "ambiguous_input_link",
                details={"input_name": input_key},
            )
        current_link_ids = list(incoming_link_ids_by_input.get(input_key, []))
        if len(current_link_ids) != 1:
            _pinned_link_ref_refusal(
                node_id,
                class_type,
                "unmappable_input_link",
                details={
                    "input_name": input_key,
                    "raw_link": raw_input.get("link"),
                    "current_link_ids": current_link_ids,
                },
            )
        raw_input["link"] = current_link_ids[0]
        seen_linked_inputs.add(input_key)

    missing_inputs = sorted(
        input_name
        for input_name, link_ids in incoming_link_ids_by_input.items()
        if link_ids and input_name not in seen_linked_inputs
    )
    if missing_inputs:
        _pinned_link_ref_refusal(
            node_id,
            class_type,
            "missing_raw_input_link",
            details={"input_names": missing_inputs},
        )

    raw_outputs = node_dict.get("outputs") or []
    if not isinstance(raw_outputs, list):
        _pinned_link_ref_refusal(
            node_id,
            class_type,
            "invalid_raw_outputs",
            details={"raw_outputs_type": type(raw_outputs).__name__},
        )

    seen_output_slots: set[int] = set()
    for idx, raw_output in enumerate(raw_outputs):
        if not isinstance(raw_output, dict):
            continue
        try:
            slot = int(raw_output.get("slot_index", idx))
        except (TypeError, ValueError):
            _pinned_link_ref_refusal(
                node_id,
                class_type,
                "unmappable_output_links",
                details={"output_index": idx, "slot_index": raw_output.get("slot_index")},
            )
        raw_link_refs = _coerce_link_refs(raw_output.get("links"))
        current_link_ids = sorted(outgoing_link_ids_by_slot.get(slot, []))
        if raw_link_refs:
            if not current_link_ids:
                _pinned_link_ref_refusal(
                    node_id,
                    class_type,
                    "unmappable_output_links",
                    details={"slot_index": slot, "raw_links": raw_link_refs},
                )
            if len(raw_link_refs) != len(current_link_ids):
                _pinned_link_ref_refusal(
                    node_id,
                    class_type,
                    "output_link_count_mismatch",
                    details={
                        "slot_index": slot,
                        "raw_links": raw_link_refs,
                        "current_link_ids": current_link_ids,
                    },
                )
            raw_output["links"] = current_link_ids
            seen_output_slots.add(slot)
        elif current_link_ids:
            _pinned_link_ref_refusal(
                node_id,
                class_type,
                "missing_raw_output_links",
                details={"slot_index": slot, "current_link_ids": current_link_ids},
            )

    missing_output_slots = sorted(
        slot
        for slot, link_ids in outgoing_link_ids_by_slot.items()
        if link_ids and slot not in seen_output_slots
    )
    if missing_output_slots:
        _pinned_link_ref_refusal(
            node_id,
            class_type,
            "missing_raw_output_slot",
            details={"slot_indexes": missing_output_slots},
        )
    return node_dict


def _raw_ui_payload_for_pin(
    raw_ui_node: Mapping[str, Any],
    *,
    node_id: str,
    class_type: str,
    litegraph_node_id: int,
    order: int,
    incoming_link_ids_by_input: Mapping[str, list[int]],
    outgoing_link_ids_by_slot: Mapping[int, list[int]],
) -> dict[str, Any]:
    node_dict = deepcopy(dict(raw_ui_node))
    _normalize_pinned_node_link_refs(
        node_dict,
        node_id=node_id,
        class_type=class_type,
        incoming_link_ids_by_input=incoming_link_ids_by_input,
        outgoing_link_ids_by_slot=outgoing_link_ids_by_slot,
    )
    node_dict["id"] = litegraph_node_id
    node_dict["order"] = order
    return node_dict


def derive_widget_shape_evidence(
    node: Any,
    schema_provider: Any | None,
) -> WidgetShapeEvidence:
    """Derive widget-shape proof for one node before UI widget regeneration.

    The candidate count intentionally goes through the same compacted-name vector
    and ``_build_widget_values`` logic that emission uses, so fresh programmatic
    ``widget_N`` overflow is visible even when no raw UI payload exists.
    """
    schema = _schema_for_provider(schema_provider, node.class_type)
    provenance = _get_node_schema_provenance(node.class_type, schema)
    widget_names = _widget_names_for_emission(node.class_type, schema)
    candidate_widget_count = len(_build_widget_values(node, widget_names))
    schema_widget_count = _full_widget_name_count(
        node.class_type,
        schema,
        schema_provider=schema_provider,
    )
    raw_widget_count, raw_widget_shape, has_dict_rows = _raw_widget_shape_from_node(node)
    schema_inputs = getattr(schema, "inputs", None)
    provider_widget_count = len(schema_inputs) if isinstance(schema_inputs, dict) else None
    if (
        has_dict_rows
        and provider_widget_count is not None
        and schema_widget_count is not None
        and _raw_widget_order_from_provider(node.class_type, schema_provider) is None
    ):
        schema_widget_count = min(schema_widget_count, provider_widget_count)
    elif (
        provider_widget_count is not None
        and schema_widget_count is not None
        and _raw_widget_order_from_provider(node.class_type, schema_provider) is None
    ):
        schema_widget_count = max(schema_widget_count, provider_widget_count)
    largest_observed_count = candidate_widget_count
    if raw_widget_count is not None:
        largest_observed_count = max(largest_observed_count, raw_widget_count)
    programmatic_widget_count = 0
    node_widgets = getattr(node, "widgets", None)
    if isinstance(node_widgets, dict):
        widget_idxs: list[int] = []
        for key in node_widgets:
            if str(key).startswith("widget_"):
                try:
                    widget_idxs.append(int(str(key).split("_", 1)[1]))
                except ValueError:
                    continue
        if widget_idxs:
            programmatic_widget_count = max(widget_idxs) + 1
    overflow = False
    if schema_widget_count is not None and not provenance["schema_less"]:
        if has_dict_rows:
            overflow = largest_observed_count > schema_widget_count
        elif (
            node.class_type in _STATIC_RAW_WIDGET_SLACK_CLASSES
            and candidate_widget_count <= schema_widget_count + _STATIC_WIDGET_OVERFLOW_TOLERANCE
            and (
                raw_widget_count is not None
                or programmatic_widget_count <= schema_widget_count
            )
            and (
                raw_widget_count is None
                or programmatic_widget_count <= raw_widget_count
            )
        ):
            overflow = False
        elif (
            programmatic_widget_count > schema_widget_count
            and not (raw_widget_count is not None and programmatic_widget_count <= raw_widget_count)
        ):
            overflow = True
        else:
            overflow = largest_observed_count > schema_widget_count

    return WidgetShapeEvidence(
        node_id=str(node.id),
        class_type=str(node.class_type),
        schema_less=bool(provenance["schema_less"]),
        confidence=provenance.get("confidence"),
        raw_widget_count=raw_widget_count,
        candidate_widget_count=candidate_widget_count,
        schema_widget_count=schema_widget_count,
        compacted_widget_names=tuple(name for name in widget_names if name is not None),
        raw_widget_shape=raw_widget_shape,
        has_dict_rows=has_dict_rows,
        overflow=overflow,
        provider=provenance.get("provider"),
    )


def emit_ui_json(
    wf: Any,
    *,
    schema_provider: Any = None,
    prior_store: Mapping[str, Any] | None = None,
    layout: Any = None,
    anchors: dict[str, Any] | None = None,
    strict: bool = False,
    recovery_report: list[dict[str, Any]] | None = None,
    source_template: str | None = None,
    prior_path: str | None = None,
    include_main_positions: bool = False,
    include_virtual_wires: bool = True,
    groups: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
    definitions: dict[str, Any] | None = None,
    change_report_out: list | None = None,
    guard_original_ui: Mapping[str, Any] | None = None,
    prior_ui_payload: Mapping[str, Any] | None = None,
    force_drop_editor_only: bool = False,
) -> dict[str, Any]:
    """Render ``wf`` (a ``VibeWorkflow``) to a litegraph JSON envelope.

    Args:
        wf: The IR workflow to emit.
        schema_provider: Schema source used for slot/type resolution.  Consulted
            via ``get_schema(class_type)`` for each node.  Pass ``None`` to skip
            schema resolution (all edges emit with slot 0 and empty type).
        prior_store: Full prior-store envelope (``{entries, groups, extra,
            definitions, virtual_wires}``) from a previously written sidecar.
            ``entries`` (keyed by node uid) feeds the legacy
            ``_resolve_furniture`` precedence chain and is passed as ``pinned``
            to the layout engine.  The full envelope is also handed to
            :func:`reconcile` once at the top of the function; the resulting
            ``ReconcileResult`` is exposed to the per-node loop as a local
            (``reconcile_result``) for later steps (Step 9b+).
        anchors: New-node placement hints ``{new_uid: anchor_uid, ...}``.
            Routed to :func:`~vibecomfy.porting.layout.placement.place_constrained`
            in the engine (Phase 8) as a dedicated kwarg.  Passing ``None`` or
            ``{}`` leaves existing behavior unchanged.
        strict: When ``True``, raises ``ValueError`` if any node has a schema-less
            class type (``get_schema() == None``) or a low-confidence schema
            (``confidence <= 0.3``, i.e. the ``widget_schema_fallback`` tier).
        recovery_report: Optional mutable list.  If provided, one provenance dict
            is appended per node with keys ``node_id``, ``class_type``,
            ``provider``, ``confidence``, ``schema_less``.  This is the
            **authoritative** record of which schema tier supplied each node's
            output/input resolution.
        groups: Optional graph-level groups list.  When provided (e.g. from a
            ``.layout.json`` sidecar), emitted directly as the top-level
            ``groups`` array; otherwise ``[]``.
        extra: Optional ``extra`` dict (canvas drag/scale state under ``extra.ds``).
            When provided, merged with the ``vibecomfy`` breadcrumb; otherwise
            only the breadcrumb is emitted.
        definitions: Optional subgraph definitions blob.  When provided from a
            sidecar envelope, used directly instead of re-emitting from IR
            metadata via ``_emit_definitions``.  The caller is responsible for
            passing definitions as they appear in the sidecar's envelope.
        prior_ui_payload: Optional full raw LiteGraph UI JSON used only as raw
            node evidence for future dynamic widget pin/refuse decisions.
            ``prior_store`` remains furniture-only and is not treated as a raw
            node payload source.

    Returns:
        A litegraph envelope dict: ``version``, deterministic ``id``,
        ``last_node_id``, ``last_link_id``, ``groups``, ``nodes``, and ``links``.
        Every node carries stamped ``properties`` and stub geometry.  Node outputs
        include ``slot_index``, ``name``, ``type``, and ``links`` (``null`` for
        unwired outputs).  The global ``links`` list holds 6-element arrays
        ``[link_id, from_node, from_slot, to_node, to_slot, type]``.
    """
    # T9a: prior_store is the full envelope ({entries, groups, extra, definitions,
    # virtual_wires}); reconcile() is called once at top and the result exposed to
    # the per-node loop as a local. The legacy ``_resolve_furniture`` chain still
    # reads from ``layout`` (= prior_store['entries']) for this batch — Step 9b
    # will replace that precedence chain with ``reconcile_result.matched``.
    from vibecomfy.porting.layout.reconcile import reconcile as _reconcile  # noqa: PLC0415
    _prior_store: dict[str, Any] = dict(prior_store) if prior_store else {}
    raw_ui_node_map = extract_raw_ui_node_map(prior_ui_payload)
    # Back-compat: callers that still pass the flat ``layout=`` kwarg are wrapped
    # into a minimal envelope so reconcile() sees the entries. Step 9b retires
    # ``layout`` entirely once all call sites migrate to prior_store.
    if layout is not None and not _prior_store:
        _prior_store = {"entries": dict(layout) if isinstance(layout, dict) else {}}
    reconcile_result = _reconcile(wf, _prior_store)
    layout = _prior_store.get("entries", {}) or {}
    anchors = anchors or {}

    # ── Editor-ahead detection (T3) ───────────────────────────────────────────
    # When guard_original_ui is supplied, detect editor-only uids early (before
    # expensive emission) and raise EditorAheadError so the caller can abort.
    # An editor-only uid is in the prior store, absent from the IR, and NOT in
    # the VibeComfy-authored set.
    #
    # Authored-uid heuristic: if the prior-store breadcrumb's prior_path matches
    # the current workflow's source path, all prior-store uids were authored by a
    # previous VibeComfy emit of this file → treat them all as authored.
    # If no breadcrumb or path mismatch → authored set is EMPTY so every
    # prior-only uid is conservatively flagged as editor-added.
    if guard_original_ui is not None:
        _prior_store_uids: set[str] = set(_prior_store.get("entries", {}).keys())
        _ir_uids: set[str] = set(wf.nodes.keys())
        _prior_breadcrumb: dict = (_prior_store.get("extra") or {}).get("vibecomfy") or {}
        _bc_prior_path = _prior_breadcrumb.get("prior_path")
        _wf_source_path = _source_prior_path(wf)
        if (
            _bc_prior_path is not None
            and _wf_source_path is not None
            and _bc_prior_path == _wf_source_path
        ):
            _vibecomfy_authored: set[str] = set(_prior_store_uids)
        else:
            _vibecomfy_authored = set()
        _editor_only: set[str] = _prior_store_uids - _ir_uids - _vibecomfy_authored
        if _editor_only:
            _entries = _prior_store.get("entries", {})
            if force_drop_editor_only:
                # Suppress the editor-ahead error: fold editor-only uids into
                # reconcile_result.removed so build_change_report can populate
                # removed_named with class_type information.
                _sorted_editor_only = sorted(_editor_only)
                reconcile_result.removed.extend(_sorted_editor_only)
            else:
                from vibecomfy.porting.refuse import EditorAheadError as _EditorAheadError  # noqa: PLC0415
                raise _EditorAheadError(
                    [
                        {"uid": u, "class_type": _entries.get(u, {}).get("class_type", "")}
                        for u in sorted(_editor_only)
                    ]
                )

    # Build ChangeReport if the caller requested it via change_report_out.
    _change_report_ref: list = []  # mutable container so we can set stripped_helpers later
    if change_report_out is not None:
        from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
        from vibecomfy.porting.layout.reconcile import build_change_report  # noqa: PLC0415
        _snapshot = (wf.metadata or {}).get("_ingest_snapshot", {})
        _field_delta = compute_field_delta(_snapshot, wf) if _snapshot else {}
        _report = build_change_report(
            reconcile_result,
            _field_delta,
            prior_store_entries=_prior_store.get("entries"),
        )
        change_report_out.append(_report)
        _change_report_ref.append(_report)

    # ── Resolve broadcast helpers (SetNode / GetNode) into direct edges ────
    # effective_edges: direct links for the EXECUTION (flat) graph
    # broadcast_ids: SetNode/GetNode node ids to drop from flat graph
    # orphaned_get_ids: GetNode ids whose broadcast name has no SetNode source
    effective_edges, broadcast_ids, orphaned_get_ids = _resolve_broadcast_edges(wf)

    # Collect the full set of virtual-wire node ids (broadcast + Reroute)
    reroute_ids = {
        node_id
        for node_id, node in wf.nodes.items()
        if node.class_type == "Reroute"
    }
    virtual_wire_ids: set[str] = broadcast_ids | reroute_ids

    # Populate stripped_helpers on the change report (now that virtual_wire_ids is computed).
    if _change_report_ref:
        _change_report_ref[0].content_edits.stripped_helpers = sorted(virtual_wire_ids) if virtual_wire_ids else []

    # ── Choose edge list and node filter based on virtual-wire toggle ───────
    if include_virtual_wires:
        # DISPLAY mode: keep all nodes, use ALL original edges (helpers visible)
        order_list = _emission_order(wf)
        display_edges = list(wf.edges)
    else:
        # EXECUTION (flat) mode: drop virtual-wire nodes, resolve edges
        order_list = [
            nid for nid in _emission_order(wf) if nid not in virtual_wire_ids
        ]
        # First resolve broadcast indirection, then passthrough Reroutes
        flat_edges = _resolve_reroute_edges(effective_edges, wf.nodes)
        display_edges = flat_edges

    # Remap string node ids → litegraph integer ids (digit ids preserve their value).
    id_remap = _build_id_remap(order_list)

    # Build schema cache (one get_schema call per unique class_type)
    schema_cache: dict[str, Any] = {}
    if schema_provider is not None:
        for node_id in order_list:
            ct = wf.nodes[node_id].class_type
            if ct not in schema_cache:
                schema_cache[ct] = schema_provider.get_schema(ct)

    # ── Layout engine: compute fresh positions for every node ───────────────
    # T9b: reconcile-driven merge.
    #   pinned   = {uid: {pos,size} for uid in reconcile_result.matched}
    #              → engine never re-positions matched nodes.
    #   anchors  = caller-supplied anchors ∪ computed_anchors, where
    #              computed_anchors[new_uid] = nearest_wired_neighbor_uid(new_node, matched).
    #              unmatched_legacy / removed-then-readded nodes (i.e. nodes whose
    #              key is neither matched nor in reconcile_result.new but were once
    #              in the store) route through the engine WITHOUT anchors.
    from vibecomfy.porting.layout import layout as _compute_layout  # noqa: PLC0415
    from vibecomfy.porting.layout.reconcile import (  # noqa: PLC0415
        nearest_wired_neighbor_uid as _nearest_wired_neighbor_uid,
    )

    matched_entries: dict[str, dict[str, Any]] = reconcile_result.matched

    def _node_key(node_id: str) -> str:
        n = wf.nodes.get(node_id)
        return (n.uid or node_id) if n is not None else node_id

    pinned_for_engine: dict[str, dict[str, Any]] = {}
    for uid_key, m_entry in matched_entries.items():
        if isinstance(m_entry, dict) and "pos" in m_entry and "size" in m_entry:
            pinned_for_engine[uid_key] = {"pos": m_entry["pos"], "size": m_entry["size"]}

    computed_anchors: dict[str, Any] = {}
    new_keys_set: set[str] = set(reconcile_result.new)
    for node_id in order_list:
        key = _node_key(node_id)
        if key not in new_keys_set:
            continue
        anchor = _nearest_wired_neighbor_uid(node_id, wf, matched_entries)
        if anchor is not None:
            computed_anchors[key] = anchor

    effective_anchors: dict[str, Any] = dict(anchors) if anchors else {}
    for k, v in computed_anchors.items():
        effective_anchors.setdefault(k, v)

    _engine_result = _compute_layout(
        wf,
        schema_provider=schema_provider,
        schema_cache=schema_cache,
        pinned=pinned_for_engine,
        anchors=effective_anchors,
    )
    engine_positions: dict[str, Any] = _engine_result.positions
    engine_groups: list[dict[str, Any]] = _engine_result.groups  # used in T8 group merge

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

    # Widget-shape fence pre-pass: evidence -> verdict happens before any node is
    # emitted. Refusals abort before ``nodes.append(...)`` can return a partial
    # invalid envelope; safe nodes regenerate widgets inside the node loop; pinned
    # nodes copy their raw LiteGraph payload without rebuilding widgets.
    from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
    from vibecomfy.porting.refuse import refused_widget_shape as _refused_widget_shape  # noqa: PLC0415
    from vibecomfy.porting.widget_shape_fence import decide_widget_shape as _decide_widget_shape  # noqa: PLC0415

    _snapshot = (wf.metadata or {}).get("_ingest_snapshot", {})
    _field_delta_by_uid = compute_field_delta(_snapshot, wf) if _snapshot else {}
    widget_shape_verdicts: dict[str, Any] = {}
    widget_shape_raw_payloads: dict[str, Mapping[str, Any] | None] = {}
    for node_id in order_list:
        node = wf.nodes[node_id]
        schema = schema_cache.get(node.class_type)
        prov = node_prov[node_id]

        retained_control = node.metadata.get("control_after_generate")
        if isinstance(retained_control, str):
            prov["control_after_generate"] = retained_control
            prov["control_after_generate_defaulted"] = False
        else:
            prov["control_after_generate"] = _CONTROL_AFTER_GENERATE_DEFAULT
            prov["control_after_generate_defaulted"] = True

        expected_widget_count = _full_widget_name_count(
            node.class_type, schema, schema_provider=schema_provider
        )
        extra_hints = _extra_widgets_after(
            node.class_type, schema, schema_provider=schema_provider
        )
        if extra_hints:
            prov["widget_order_guesses"] = [
                "(control_after_generate)" if name is None else name
                for name in extra_hints
            ]

        evidence = derive_widget_shape_evidence(node, schema_provider)
        if expected_widget_count is None:
            prov["widget_length_check"] = "skipped: schema-less"
        elif evidence.overflow:
            prov["widget_length_check"] = (
                f"overflow {evidence.candidate_widget_count}>{expected_widget_count}"
            )
        else:
            prov["widget_length_check"] = (
                f"{evidence.candidate_widget_count}<={expected_widget_count}"
            )

        raw_ui_node = _raw_ui_node_for_node(node_id, node, raw_ui_node_map)
        widget_shape_raw_payloads[node_id] = raw_ui_node
        field_delta, link_delta = _split_widget_shape_deltas(_field_delta_by_uid, node_id, node)
        layout_entry = _layout_entry_for_widget_shape(node_id, node, matched_entries)
        verdict = _decide_widget_shape(
            evidence,
            raw_widget_payloads={node_id: getattr(node, "raw_widgets", None)},
            raw_payloads={node_id: raw_ui_node} if raw_ui_node is not None else {},
            layout_entries={node_id: layout_entry} if layout_entry is not None else {},
            field_deltas={node_id: field_delta} if field_delta else {},
            link_deltas={node_id: link_delta} if link_delta else {},
        )
        widget_shape_verdicts[node_id] = verdict

    refused_verdicts = [verdict for verdict in widget_shape_verdicts.values() if verdict.refuse]
    if refused_verdicts:
        if recovery_report is not None:
            for node_id in order_list:
                recovery_report.append(
                    _build_recovery_entry(
                        node_prov[node_id],
                        widget_shape_verdicts[node_id],
                        has_raw_ui_payload=widget_shape_raw_payloads[node_id] is not None,
                    )
                )
        raise _refused_widget_shape(refused_verdicts)

    # Sort edges deterministically (from_node asc, from_output, to_node, to_input)
    sorted_edges = sorted(
        display_edges,
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
        key = _node_key(node_id)
        verdict = widget_shape_verdicts[node_id]
        if verdict.pin_opaque:
            incoming_link_ids_by_input: dict[str, list[int]] = defaultdict(list)
            for edge in edges_to[node_id]:
                lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
                incoming_link_ids_by_input[edge.to_input].append(lid)
            outgoing_link_ids_by_slot: dict[int, list[int]] = defaultdict(list)
            for edge in edges_from[node_id]:
                slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
                lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
                outgoing_link_ids_by_slot[slot].append(lid)
            nodes.append(
                _raw_ui_payload_for_pin(
                    verdict.raw_ui_node or {},
                    node_id=node_id,
                    class_type=node.class_type,
                    litegraph_node_id=id_remap[node_id],
                    order=order,
                    incoming_link_ids_by_input=incoming_link_ids_by_input,
                    outgoing_link_ids_by_slot=outgoing_link_ids_by_slot,
                )
            )
            continue
        matched_entry = matched_entries.get(key)
        # T9b: reconcile-driven merge.
        #   matched → verbatim pos/size/mode/flags/color/properties/group/title from the entry.
        #   else    → engine_positions (already incorporates anchors / pinning), else _stub.
        if matched_entry is not None:
            geometry = (
                _extract_geometry(matched_entry)
                or engine_positions.get(node.uid)
                or _stub_layout(order)
            )
            furniture = _resolve_furniture(node, matched_entry)
        else:
            # Unmatched (new / unmatched_legacy / removed-then-readded).
            # The captured _ui inline on the node (direct-ingest fallback) is the
            # source of truth when present; the engine owns geometry only when
            # no captured _ui exists (programmatic / scratchpad path).
            geometry = (
                _captured_geometry(node)
                or engine_positions.get(node.uid)
                or _stub_layout(order)
            )
            furniture = _resolve_furniture(node, None)
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
        widget_names = _widget_names_for_emission(node.class_type, schema)
        widget_name_set = {name for name in widget_names if name is not None}
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
        # Step 6 (T8): re-stamp the verbatim captured properties blob as the base,
        # then overlay the IR identity keys.  When no captured blob exists (e.g.
        # programmatic workflows), fall back to fresh-construction — no regression.
        prov = node_prov[node_id]
        captured_blob: dict[str, Any] | None = furniture.get("properties") if furniture else None
        if captured_blob:
            # Verbatim captured blob (cnr_id / ver / mask-data / etc.) from the
            # layout-store entry (``_build_entry``) or ``node.metadata['_ui']``.
            properties = dict(captured_blob)
        else:
            # No captured blob → fresh construction (programmatic / scratchpad path).
            properties = {}

        # ── IR identity keys ALWAYS win (merged ON TOP of any captured value) ──
        # Scrub stale ir_node_id from captured blobs (demoted in M5).
        properties.pop("ir_node_id", None)
        properties["vibecomfy_id"] = f"{node.class_type}_{order}"
        properties["Node name for S&R"] = node.class_type

        # Optional debug stamp (provider tier)
        if not prov["schema_less"]:
            properties["_vibecomfy_schema_provider"] = prov.get("provider", "unknown")

        # ── uid stamp (M1.5): every node with a non-empty uid carries its frozen identity ──
        if node.uid:
            properties["vibecomfy_uid"] = node.uid

        # --- widgets_values (verified raw ComfyUI ordering; see module docstring) ---
        widget_values = _build_widget_values(node, widget_names)

        # Properties are now built by re-stamping the verbatim captured blob
        # (or fresh-construction fallback) with IR identity keys overlaid
        # — see the properties-construction block above.  No separate merge needed.


        node_dict: dict[str, Any] = {
            "id": id_remap[node_id],
            "type": node.class_type,
            "pos": geometry["pos"],
            "size": geometry["size"],
            "flags": furniture["flags"],
            "order": order,
            "mode": furniture["mode"],
            "inputs": inputs,
            "outputs": outputs,
            "properties": properties,
            "widgets_values": widget_values,
        }
        # Emit color / bgcolor only when non-None (litegraph convention: absent = default)
        if furniture["color"] is not None:
            node_dict["color"] = furniture["color"]
        if furniture["bgcolor"] is not None:
            node_dict["bgcolor"] = furniture["bgcolor"]
        # Node title: emit only when include_main_positions=True and non-None,
        # so the lean default (include_main_positions=False) omits it entirely.
        if include_main_positions and furniture["title"] is not None:
            node_dict["title"] = furniture["title"]

        nodes.append(node_dict)

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
            entry = _build_recovery_entry(
                node_prov[node_id],
                widget_shape_verdicts[node_id],
                has_raw_ui_payload=widget_shape_raw_payloads[node_id] is not None,
            )
            node = wf.nodes.get(node_id)
            if node is not None and is_intent_class_type(node.class_type):
                entry.update(_intent_recovery_fields(node))
            recovery_report.append(entry)

        # ── Orphaned virtual-wire routes (display mode) ─────────────────
        if include_virtual_wires and orphaned_get_ids:
            for gid in sorted(orphaned_get_ids):
                node = wf.nodes.get(gid)
                name = broadcast_name(node) if node else None
                recovery_report.append({
                    "node_id": gid,
                    "class_type": "GetNode",
                    "provider": None,
                    "confidence": None,
                    "schema_less": False,
                    "diagnostic": (
                        f"orphaned virtual-wire: GetNode {gid} "
                        f"(broadcast name={name!r}) has no matching SetNode source — "
                        "emitted as visible node with dangling links in display graph"
                    ),
                    "orphaned_route": True,
                    "broadcast_name": name,
                    "widget_shape_verdict": "not_applicable",
                })

        # ── Stripped virtual-wire helpers summary (T7) ───────────────────
        # Always append this entry (zero-count or non-zero) so JSON-mode
        # consumers can detect the emit-mode. Text mode prints only when N > 0.
        recovery_report.append({
            "stripped_helpers": sorted(virtual_wire_ids),
            "count": len(virtual_wire_ids),
            "widget_shape_verdict": "not_applicable",
        })

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

    # --- extra: merge caller-provided extra (e.g. sidecar ds) with vibecomfy breadcrumb ---
    merged_extra: dict[str, Any] = dict(extra) if extra else {}
    merged_extra["vibecomfy"] = dict(breadcrumb)

    # When include_main_positions=True, ensure extra.ds (canvas drag/scale state) is
    # present, falling back to a fixed machine-independent default.  The lean default
    # (include_main_positions=False) omits ds entirely.
    if include_main_positions and "ds" not in merged_extra:
        merged_extra["ds"] = dict(_DEFAULT_DS)

    # --- groups: merge caller-passed groups with engine-generated subgraph groups ---
    #   Order: caller-passed groups first, then engine_groups (suppressing duplicates
    #   whose ``title`` matches a caller-passed group title).  All groups are
    #   canonicalized when ``include_main_positions=True``.
    caller_groups: list[dict[str, Any]] = list(groups) if groups is not None else []
    caller_titles: set[str] = {g.get("title", "") for g in caller_groups if g.get("title")}
    emitted_groups: list[dict[str, Any]] = list(caller_groups)
    for eg in engine_groups:
        if eg.get("title", "") not in caller_titles:
            emitted_groups.append(eg)
    if include_main_positions and emitted_groups:
        _canonicalize_group_geometry(emitted_groups)

    envelope: dict[str, Any] = {
        "id": _envelope_id(wf),
        "version": _LITEGRAPH_VERSION,
        "last_node_id": last_node_id,
        "last_link_id": last_link_id,
        "groups": emitted_groups,
        "nodes": nodes,
        "links": links,
        "extra": merged_extra,
    }

    # Subgraph definitions: caller-provided `definitions` (from sidecar envelope)
    # takes precedence over re-emitting from IR metadata.
    effective_defs = definitions if definitions else _emit_definitions(wf)
    if effective_defs is not None:
        for sg in effective_defs.get("subgraphs", []):
            sg_extra = dict(sg.get("extra") or {})
            sg_extra["vibecomfy"] = dict(breadcrumb)
            sg["extra"] = sg_extra
        envelope["definitions"] = effective_defs
        envelope["state"] = {
            "lastNodeId": last_node_id,
            "lastLinkId": last_link_id,
            "lastRerouteId": 0,
        }

    # When include_main_positions=True, always emit state counters even if there
    # are no definitions (the lean default ties state to definitions presence).
    if include_main_positions and "state" not in envelope:
        envelope["state"] = {
            "lastNodeId": last_node_id,
            "lastLinkId": last_link_id,
            "lastRerouteId": 0,
        }

    # M5 Step 16: refusal-spine on APPLIED re-emit. When the caller supplies the
    # pre-edit UI JSON as guard_original_ui, run convert_ui_to_api over both
    # original and candidate (this envelope) and refuse if any uid-matched,
    # snapshot-present node diverges outside snapshot_delta. RefusedEmit bubbles
    # up so the caller can abort the write.
    if guard_original_ui is not None:
        from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
        from vibecomfy.porting.refuse import guard_emit as _guard_emit  # noqa: PLC0415

        _snap = (wf.metadata or {}).get("_ingest_snapshot", {})
        _delta = compute_field_delta(_snap, wf) if _snap else {}
        _guard_emit(guard_original_ui, envelope, _delta)

    return envelope


def offline_emitter_normalizer_self_consistency_check(
    wf: Any,
    *,
    schema_provider: Any = None,
) -> tuple[bool, list[str]]:
    """Self-consistency check: emitter and normalizer agree on the same IR.

    Proves that ``emit_ui_json`` and ``_normalize_ui_to_api`` are inverses of
    each other on the given workflow — NOT that the result is correct relative
    to ComfyUI's own output.  After compile('api') drops muted/bypassed nodes,
    the compare is against the potentially-smaller compiled graph.

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
        widget_count = _full_widget_name_count(class_type, schema, schema_provider=schema_provider)
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
    "WidgetShapeEvidence",
    "derive_widget_shape_evidence",
    "extract_raw_ui_node_map",
    "_normalize_pinned_node_link_refs",
    "_raw_ui_payload_for_pin",
    "emit_ui_json",
    "offline_emitter_normalizer_self_consistency_check",
    "structural_validate",
    "default_output_path",
]
