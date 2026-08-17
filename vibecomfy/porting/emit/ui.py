"""Emit a VibeWorkflow IR back to a litegraph (ComfyUI editor) JSON envelope.

This is the inverse direction of ingest: ``from_ui`` reads litegraph
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

from vibecomfy._compile._helpers import (
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
from vibecomfy.identity.uid import mint_local_uid
from vibecomfy.porting.endpoint_invariant import schema_input_sockets_for_unwired_node
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.porting.widgets.aliases import widget_names_for_class, widget_names_from_schema
from vibecomfy.workflow import VibeEdge, VibeNode, _get_node_mode, _raise_embedded_api_links

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

# Door-owned wire-retention metadata key (mirror of
# ``vibecomfy.ingest.normalize._UI_DOOR_KEY``).  Only the door boundary reads
# or writes the blob; this literal avoids importing normalize at module level.
_UI_DOOR_KEY = "_ui_door"


def _door_ui_passthrough_applicable(
    wf: Any,
    door: Any,
    *,
    include_virtual_wires: bool,
    include_main_positions: bool,
    extra: Mapping[str, Any] | None,
    definitions: Mapping[str, Any] | None,
    prior_store: Mapping[str, Any] | None,
    layout: Any,
    strict: bool,
) -> bool:
    """Law 1 passthrough gate: may this UNTOUCHED graph be re-emitted verbatim?

    The door blob is consulted only when the caller asks for the default output
    shape (no flat/virtual-wire toggle, no main positions, no explicit
    extra/definitions/prior_store/layout overrides, no strict request) and the
    graph was ingested through the OFFLINE normalizer (``use_comfy_converter``
    is recorded at ingest).  Comfy-converter ingest is not guaranteed to
    normalize back to the same API, so those graphs keep the deterministic
    reconstruction path.  The final fingerprint comparison proves the graph is
    untouched since ingest; anything else takes the reconstruction path (where
    captured wire values are still preferred for unaffected parts).
    """
    if not isinstance(door, Mapping):
        return False
    if door.get("shape") != "ui":
        return False
    if door.get("use_comfy_converter") is not False:
        return False
    if not include_virtual_wires or include_main_positions or strict:
        return False
    if extra is not None or definitions is not None:
        return False
    if prior_store or layout:
        return False
    if not isinstance(door.get("top"), Mapping) or not isinstance(door.get("nodes"), Mapping):
        return False
    if not isinstance(door.get("node_order"), list):
        return False
    from vibecomfy.ingest.normalize import _door_node_fingerprint  # noqa: PLC0415

    return _door_node_fingerprint(wf) == door.get("fingerprint")


def _emit_untouched_door_ui(door: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the original litegraph envelope byte-for-byte from the door blob.

    Preserves the raw top-level key order, every raw top-level field (id,
    version, counters, links with ids/order/type, extra, definitions, state,
    config, revision, opaque keys), and the raw node payloads in raw order —
    node geometry, ``order``, ``properties``, ``widgets_values``, input/output
    link refs included.  The result is a detached deep copy.
    """
    from vibecomfy.ingest.normalize import _restore_untouched_door  # noqa: PLC0415

    return _restore_untouched_door(door)


def _door_top(door: Any) -> Mapping[str, Any] | None:
    """Return the door blob's captured top-level fields, or None."""
    if not isinstance(door, Mapping):
        return None
    top = door.get("top")
    return top if isinstance(top, Mapping) else None


def _wire_id(wf: Any, door: Any) -> str:
    """Envelope id: the captured wire id when present, else the deterministic id."""
    top = _door_top(door)
    if isinstance(top, Mapping) and isinstance(top.get("id"), str) and top["id"]:
        return top["id"]
    return _envelope_id(wf)


def _wire_version(door: Any) -> Any:
    """Envelope ``version``: the captured wire value when present."""
    top = _door_top(door)
    if isinstance(top, Mapping) and isinstance(top.get("version"), (int, float)) and not isinstance(
        top["version"], bool
    ):
        return top["version"]
    return _LITEGRAPH_VERSION


def _wire_counter(door: Any, key: str, computed: int) -> int:
    """Counter field: captured value when still consistent (>= computed), else recomputed."""
    top = _door_top(door)
    captured = top.get(key) if isinstance(top, Mapping) else None
    if isinstance(captured, int) and not isinstance(captured, bool) and captured >= computed:
        return captured
    return computed


def _captured_link_id_map(
    door: Any,
) -> dict[tuple[str, str, str, str], int]:
    """Map IR edge keys ``(from_node, from_output, to_node, to_input)`` to the
    ORIGINAL litegraph link ids captured at ingest.

    Endpoints resolve through the captured raw node payloads: each captured
    link id is located in the captured to-node's ``inputs`` (name) and the
    captured from-node's ``outputs`` (``slot_index``).  Links that cannot be
    resolved (helper endpoints, missing slots) are simply absent from the map —
    the emitter mints fresh ids for those.  This lets an edited graph keep the
    original ids for structurally unchanged links (Law 1, wire preference).
    """
    if not isinstance(door, Mapping):
        return {}
    top = _door_top(door)
    links = top.get("links") if isinstance(top, Mapping) else None
    nodes = door.get("nodes") if isinstance(door.get("nodes"), Mapping) else {}
    if not isinstance(links, list):
        return {}
    input_name_by_link: dict[int, tuple[str, str]] = {}
    output_slot_by_link: dict[int, tuple[str, str]] = {}
    for nid, payload in nodes.items():
        if not isinstance(payload, Mapping):
            continue
        for entry in payload.get("inputs") or []:
            if not isinstance(entry, Mapping):
                continue
            link_ref = entry.get("link")
            if isinstance(link_ref, int):
                input_name_by_link[link_ref] = (str(nid), str(entry.get("name", "")))
        for entry in payload.get("outputs") or []:
            if not isinstance(entry, Mapping):
                continue
            slot = entry.get("slot_index")
            if slot is None:
                continue
            try:
                slot_int = int(slot)
            except (TypeError, ValueError):
                continue
            for link_ref in entry.get("links") or []:
                if isinstance(link_ref, int):
                    output_slot_by_link[link_ref] = (str(nid), str(slot_int))
    result: dict[tuple[str, str, str, str], int] = {}
    for link in links:
        if not isinstance(link, (list, tuple)) or len(link) < 5:
            continue
        lid = link[0]
        if not isinstance(lid, int):
            continue
        from_node, to_node = str(link[1]), str(link[3])
        in_info = input_name_by_link.get(lid)
        out_info = output_slot_by_link.get(lid)
        if in_info is None or out_info is None:
            continue
        if in_info[0] != to_node or out_info[0] != from_node:
            continue
        result[(from_node, out_info[1], to_node, in_info[1])] = lid
    return result


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
_PRIMITIVE_CONTROL_WIDGET_CLASSES = frozenset(
    {"PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt"}
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
    explicit_widget_overflow: bool = False
    raw_widget_length_recovered: bool = False
    value_domain: str = "compact"


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
    """Resolve display furniture while taking mode only from the IR node.

    This is a SEPARATE path from the pos/size geometry chain
    (:func:`_captured_geometry`).  Precedence:

    1. Sidecar entry (``layout_entry``) for flags, colors, properties, and title.
    2. ``node.metadata['_ui']`` for those same fields when no sidecar exists.
    3. :func:`vibecomfy.workflow._get_node_mode` for mode.  This is the exact
       authority used by compilation, including its single legacy ``_ui.mode``
       fallback.
    4. Fixed defaults (``flags={}``, ``color=None``, ``bgcolor=None``,
       ``properties={}``, ``title=None``).

    Returns a dict with keys ``flags``, ``color``, ``bgcolor``, ``mode``,
    ``properties``, ``title``.
    """
    # Source 1: sidecar entry (authoritative)
    if layout_entry:
        flags = layout_entry.get("flags")
        color = layout_entry.get("color")
        bgcolor = layout_entry.get("bgcolor")
        properties = layout_entry.get("properties")
        title = layout_entry.get("title")
    else:
        # Source 2: node.metadata['_ui'] (direct-ingest fallback)
        _ui = getattr(node, "metadata", {}).get("_ui")
        if isinstance(_ui, dict):
            flags = _ui.get("flags")
            color = _ui.get("color")
            bgcolor = _ui.get("bgcolor")
            properties = _ui.get("properties")
            title = _ui.get("title")
        else:
            flags = None
            color = None
            bgcolor = None
            properties = None
            title = None

    # Source 3: fixed defaults
    if not isinstance(flags, dict):
        flags = {}
    if not isinstance(properties, dict):
        properties = {}
    # title stays None for absent/default — the caller decides whether to emit it

    return {
        "flags": flags,
        "color": color,
        "bgcolor": bgcolor,
        "mode": _get_node_mode(node),
        "properties": properties,
        "title": title,
    }


def _captured_geometry(node: Any) -> dict[str, list[float]] | None:
    """Return first-class ``{pos, size}``, or ``None`` when either is absent.

    The ``None`` fallthrough is intentional: callers should chain through to
    ``_stub_layout`` when no captured geometry exists (e.g. programmatic nodes
    or workflows loaded from a .py file without a sidecar).
    """
    pos = getattr(node, "pos", None)
    size = getattr(node, "size", None)
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


def _flat_layout_workflow(
    wf: Any,
    virtual_wire_ids: set[str],
    flat_edges: list[Any],
) -> Any:
    """Return a shallow flat-graph view of *wf* for layout computation.

    Flat mode (``include_virtual_wires=False``) drops virtual-wire nodes
    (SetNode/GetNode/Reroute) from the emitted node list and resolves their
    edges into direct links.  The layout engine must therefore compute
    positions against the same flat projection — otherwise a workflow whose
    helpers were retained in the IR (``--keep-virtual-wires``) would lay out
    real nodes at different layers/lanes than an identical flat graph whose
    helpers were resolved during conversion, breaking flat round-trip
    byte-equivalence (``test_keep_virtual_wires_round_trip``).

    The view is a shallow ``dataclasses.replace``: node objects, inputs and
    metadata are shared with the original workflow (never mutated by the
    engine); only the node dict and edge list are the flat projection.  Node
    uids are preserved, so ``engine_positions[uid]`` still resolves for every
    surviving node in the caller's ``order_list``.
    """
    import dataclasses  # noqa: PLC0415

    flat_nodes = {
        node_id: node
        for node_id, node in wf.nodes.items()
        if node_id not in virtual_wire_ids
    }
    flat_inputs = {
        name: value
        for name, value in (getattr(wf, "inputs", None) or {}).items()
        if str(getattr(value, "node_id", "") or "") in flat_nodes
    }
    return dataclasses.replace(
        wf,
        nodes=flat_nodes,
        edges=list(flat_edges),
        inputs=flat_inputs,
    )


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


def _remap_ir_groups(
    wf: Any,
    order_list: list[str],
    id_remap: Mapping[str, int],
) -> list[dict[str, Any]]:
    """Deep-copy IR groups and resolve live members to LiteGraph integer ids.

    Group membership may have been captured at different boundaries, so each
    live node contributes aliases for its workflow mapping key, ``node.id``,
    stable uid, and captured ``_ui.id``.  Numeric aliases accept either their
    integer or decimal-string form.  Ambiguous aliases and stale members are
    omitted instead of emitting a dangling reference.
    """
    candidates: dict[tuple[str, Any], set[int]] = defaultdict(set)

    def add_alias(value: Any, emitted_id: int) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            candidates[("int", value)].add(emitted_id)
            candidates[("str", str(value))].add(emitted_id)
        elif isinstance(value, str) and value:
            candidates[("str", value)].add(emitted_id)
            if value.isdigit():
                candidates[("int", int(value))].add(emitted_id)

    for workflow_node_id in order_list:
        node = wf.nodes[workflow_node_id]
        emitted_id = id_remap[workflow_node_id]
        add_alias(workflow_node_id, emitted_id)
        add_alias(getattr(node, "id", None), emitted_id)
        add_alias(getattr(node, "uid", None), emitted_id)
        raw_ui = getattr(node, "metadata", {}).get("_ui")
        if isinstance(raw_ui, dict):
            add_alias(raw_ui.get("id"), emitted_id)

    aliases = {key: next(iter(ids)) for key, ids in candidates.items() if len(ids) == 1}
    remapped: list[dict[str, Any]] = []
    for raw_group in deepcopy(getattr(wf, "groups", [])):
        group = dict(raw_group)
        members = group.get("nodes")
        if isinstance(members, list):
            resolved: list[int] = []
            for member in members:
                if isinstance(member, bool):
                    continue
                key = (
                    ("int", member)
                    if isinstance(member, int)
                    else ("str", member)
                    if isinstance(member, str)
                    else None
                )
                if key is not None and key in aliases:
                    resolved.append(aliases[key])
            group["nodes"] = resolved
        elif "nodes" in group:
            group["nodes"] = []
        remapped.append(group)
    return remapped


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
        # Detached copy: stamping uids/state below must never mutate the IR's
        # metadata definitions (``dict(raw_sg)`` alone would alias the inner
        # ``nodes`` list into the caller's data).
        sg = deepcopy(raw_sg)
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


def _canonical_emitted_output_name(from_output: Any, slot: int) -> str:
    """Canonical socket name an emitted output carries for *from_output*."""
    text = str(from_output)
    return f"output_{slot}" if text.isdigit() else text


def _emitted_socket_slot_for_link(
    sockets: list[dict[str, Any]] | None,
    slot: int,
    canonical_name: str,
) -> int | None:
    """Resolve a link endpoint against the node's *emitted* socket array.

    Working-graph sockets are authoritative.  An in-range slot is kept whenever
    the socket plausibly corresponds to the link (name match, ``None``-named
    UI-only slot, or a matching ``slot_index`` label); a phantom/absent slot is
    resolved to the socket whose canonical name matches, else ``None`` so the
    caller can deterministically drop the dangling link with a diagnostic
    instead of projecting a port the emitted graph does not have.
    """
    if not isinstance(sockets, list) or not isinstance(slot, int):
        return None
    if 0 <= slot < len(sockets):
        socket = sockets[slot]
        if not isinstance(socket, dict):
            return slot
        name = socket.get("name")
        if name == canonical_name or name in (None, "") or socket.get("slot_index") == slot:
            return slot
    for index, socket in enumerate(sockets):
        if isinstance(socket, dict) and socket.get("name") == canonical_name:
            return index
    for index, socket in enumerate(sockets):
        if isinstance(socket, dict) and socket.get("slot_index") == slot:
            return index
    return None


def _emitted_socket_array_evidence(
    sockets: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Project an emitted socket array into JSONable refusal evidence.

    Each entry records the physical ``slot`` index plus whatever identity the
    emitted socket carries (``name`` and/or ``slot_index``).  ``None``/non-list
    inputs (no emitted sockets for the node) project to ``[]``.
    """
    if not isinstance(sockets, list):
        return []
    out: list[dict[str, Any]] = []
    for index, socket in enumerate(sockets):
        if isinstance(socket, dict):
            out.append(
                {
                    "slot": index,
                    "name": socket.get("name"),
                    "slot_index": socket.get("slot_index"),
                }
            )
        else:
            out.append({"slot": index, "name": socket})
    return out


def _remap_attempts_evidence(
    sockets: list[dict[str, Any]] | None,
    slot: int,
    canonical_name: str,
) -> list[dict[str, Any]]:
    """Reconstruct the deterministic remap strategies tried for a phantom endpoint.

    Mirrors :func:`_emitted_socket_slot_for_link` — in-range slot acceptance,
    then a canonical-name scan, then a ``slot_index`` scan.  This is called
    only after that function returned ``None``, so every ``found_at`` list is
    empty by construction: the evidence documents what was attempted (and
    rejected) for the refusal, not a second lookup.
    """
    if not isinstance(sockets, list):
        return [
            {
                "strategy": "invalid_socket_array",
                "detail": type(sockets).__name__,
            }
        ]
    in_range: dict[str, Any] | None = None
    in_range_rejected: str | None = None
    if isinstance(slot, int) and 0 <= slot < len(sockets):
        socket = sockets[slot]
        if isinstance(socket, dict):
            in_range = {
                "slot": slot,
                "name": socket.get("name"),
                "slot_index": socket.get("slot_index"),
            }
            name = socket.get("name")
            if name != canonical_name and name not in (None, "") and socket.get("slot_index") != slot:
                in_range_rejected = (
                    f"name {name!r} != canonical {canonical_name!r} and slot_index != {slot}"
                )
        else:
            in_range = {"slot": slot, "name": socket}
    return [
        {
            "strategy": "in_range_slot",
            "requested_slot": slot,
            "socket_at_slot": in_range,
            "out_of_range": not (isinstance(slot, int) and 0 <= slot < len(sockets)),
            "rejected_reason": in_range_rejected,
        },
        {
            "strategy": "canonical_name_scan",
            "sought_name": canonical_name,
            "found_at": [
                index
                for index, socket in enumerate(sockets)
                if isinstance(socket, dict) and socket.get("name") == canonical_name
            ],
        },
        {
            "strategy": "slot_index_scan",
            "sought_slot": slot,
            "found_at": [
                index
                for index, socket in enumerate(sockets)
                if isinstance(socket, dict) and socket.get("slot_index") == slot
            ],
        },
    ]


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


def _ordered_incoming_edges(
    edges: list[Any],
    schema: Any | None,
) -> list[Any]:
    """Order linked inputs by their physical ComfyUI socket position.

    LiteGraph link records address a target by *input-array index*, not by
    input name.  Alphabetizing linked fields therefore corrupts any node whose
    authoring names do not happen to match its physical socket order (notably
    KSampler: ``model, positive, negative, latent_image``).  Runtime schema
    input order mirrors ComfyUI's declared order, so use it whenever present;
    retain a deterministic name-based fallback for schema-less nodes.
    """
    schema_inputs = getattr(schema, "inputs", None)
    ordered_names = list(schema_inputs) if isinstance(schema_inputs, Mapping) else []
    position = {name: index for index, name in enumerate(ordered_names)}
    unknown_offset = len(position)
    return sorted(
        edges,
        key=lambda edge: (
            position.get(edge.to_input, unknown_offset),
            edge.to_input,
            edge.from_node,
            edge.from_output,
        ),
    )


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


def _widget_names_for_emission(
    class_type: str,
    schema: Any,
    *,
    node: Any | None = None,
    schema_provider: Any | None = None,
) -> list[str | None]:
    """Return widget names in the value domain this node can safely emit."""
    from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

    committed = widget_names_for_class(class_type)
    object_info_order = object_info_widget_order(class_type)
    if _widget_value_domain_for_emission(node, committed, object_info_order) == "raw_object_info":
        if committed is not None and any(name is None for name in committed):
            return list(committed)
        if object_info_order:
            return list(object_info_order)
        if committed is not None:
            return list(committed)

    if node is not None:
        count = _compact_widget_count_for_emission(node)
        if count:
            return list(
                compact_widget_names_for_node(
                    node,
                    class_type,
                    value_count=count,
                    schema_provider=schema_provider,
                ).names
            )

    if committed is not None:
        return list(committed)
    return list(widget_names_from_schema(class_type, schema))


def _widget_value_domain_for_emission(
    node: Any | None,
    committed: list[str | None] | None,
    object_info_order: list[str | None],
) -> str:
    if committed is not None and any(name is None for name in committed):
        return "raw_object_info"
    raw_count = _captured_raw_widget_count(node)
    if raw_count is not None and object_info_order and raw_count == len(object_info_order):
        return "raw_object_info"
    return "compact"


def _compact_widget_count_for_emission(node: Any) -> int:
    raw_count = _captured_raw_widget_count(node)
    widget_key_count = _widget_key_count(getattr(node, "widgets", None))
    if raw_count is not None and widget_key_count and raw_count == widget_key_count:
        return raw_count
    if widget_key_count:
        return widget_key_count
    return raw_count or 0


def _captured_raw_widget_count(node: Any | None) -> int | None:
    if node is None:
        return None
    raw_ui = getattr(node, "metadata", {}).get("_ui", {})
    raw_widgets = raw_ui.get("widgets_values") if isinstance(raw_ui, dict) else None
    if isinstance(raw_widgets, list):
        return len(raw_widgets)
    raw_widget_payload = getattr(node, "raw_widgets", None)
    length = getattr(raw_widget_payload, "length", None)
    if isinstance(length, int):
        return length
    values = getattr(raw_widget_payload, "values", None)
    if isinstance(values, list):
        return len(values)
    return None


def _widget_key_count(values: Any) -> int:
    if not isinstance(values, Mapping):
        return 0
    indices: list[int] = []
    for key in values:
        key_str = str(key)
        if not key_str.startswith("widget_"):
            continue
        try:
            indices.append(int(key_str.split("_", 1)[1]))
        except ValueError:
            continue
    if not indices:
        return 0
    expected = list(range(max(indices) + 1))
    return max(indices) + 1 if sorted(indices) == expected else 0


def _object_info_order_safely_extends_committed(
    committed: list[str | None],
    object_info_order: list[str | None],
) -> bool:
    if not object_info_order or len(object_info_order) <= len(committed):
        return False
    if any(name is None for name in committed):
        return False
    committed_names = [name for name in committed if isinstance(name, str)]
    object_info_names = [name for name in object_info_order if isinstance(name, str)]
    return object_info_names == committed_names


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
    # 1. Committed table, extended only by reconciled object_info metadata when
    # it is clearly the same named order plus UI-only slots.
    committed = widget_names_for_class(class_type)
    if committed is not None:
        from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

        object_info_order = object_info_widget_order(class_type)
        if _object_info_order_safely_extends_committed(committed, object_info_order):
            return len(object_info_order)
        return len(committed)

    # 2. Raw object_info_widget_order from the provider (nulls included).
    raw = _raw_widget_order_from_provider(class_type, schema_provider)
    if raw is not None and len(raw) > 0:
        return len(raw)

    # 3. Provider schema (null-free)
    names = widget_names_from_schema(class_type, schema)
    return len(names) if names else None


def _build_widget_values(
    node: Any,
    widget_names: list[str | None],
    *,
    default_values: Mapping[str, Any] | None = None,
    value_domain: str = "compact",
) -> list[Any]:
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
    defaults = dict(default_values or {})
    use_schema_defaults = bool(defaults)

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
        raw_widget_payload = getattr(node, "raw_widgets", None)
        raw_widget_values = getattr(raw_widget_payload, "values", None)
        raw_widgets = list(raw_widget_values) if isinstance(raw_widget_values, list) else []

    preserve_observed_widget_carriers = _preserve_observed_widget_carriers(
        node,
        raw_widgets=raw_widgets,
    )
    has_seed_control_slot = any(
        isinstance(name, str) and name in _SEED_INPUT_NAMES
        for name in widget_names
    )
    if value_domain == "compact":
        length = max(len(widget_names), max_widget, len(raw_widgets))
    elif use_schema_defaults:
        length = max(len(widget_names), len(raw_widgets))
    else:
        length = max(len(widget_names), max_widget, len(raw_widgets))
    values: list[Any] = []
    for idx in range(length):
        name = widget_names[idx] if idx < len(widget_names) else None
        if isinstance(name, str) and name in pool:
            values.append(pool[name])
        elif (
            use_schema_defaults
            and preserve_observed_widget_carriers
            and f"widget_{idx}" in pool
        ):
            values.append(pool[f"widget_{idx}"])
        elif not use_schema_defaults and f"widget_{idx}" in pool:
            values.append(pool[f"widget_{idx}"])
        elif isinstance(name, str) and name in defaults:
            values.append(deepcopy(defaults[name]))
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


def _preserve_observed_widget_carriers(
    node: Any,
    *,
    raw_widgets: list[Any],
) -> bool:
    if raw_widgets:
        return True
    raw_widget_payload = getattr(node, "raw_widgets", None)
    raw_widget_values = getattr(raw_widget_payload, "values", None)
    if isinstance(raw_widget_values, list) and raw_widget_values:
        return True
    metadata = getattr(node, "metadata", {})
    if not isinstance(metadata, Mapping):
        return False
    raw_ui = metadata.get("_ui")
    if isinstance(raw_ui, Mapping) and isinstance(raw_ui.get("widgets_values"), list):
        return True
    return bool(metadata.get("provenance"))


def _schema_outputs_for_unwired_node(schema: Any | None) -> list[dict[str, Any]]:
    schema_outputs = list(getattr(schema, "outputs", None) or []) if schema else []
    return [
        {
            "name": out_spec.name or f"output_{slot_idx}",
            "type": out_spec.type or "",
            "links": None,
            "slot_index": slot_idx,
        }
        for slot_idx, out_spec in enumerate(schema_outputs)
    ]


def _exec_node_field(node: Any, key: str) -> Any:
    """Return a vibecomfy.exec field from widgets first, then inputs."""
    node_widgets = getattr(node, "widgets", None)
    if isinstance(node_widgets, Mapping) and key in node_widgets:
        return node_widgets[key]
    node_inputs = getattr(node, "inputs", None)
    if isinstance(node_inputs, Mapping) and key in node_inputs:
        return node_inputs[key]
    return None


def _normalize_exec_io_entries(value: Any) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    raw_items: Any
    if isinstance(value, Mapping):
        raw_items = [[name, socket_type] for name, socket_type in value.items()]
    elif isinstance(value, list):
        raw_items = value
    else:
        return entries
    for index, item in enumerate(raw_items):
        name: Any
        socket_type: Any
        if isinstance(item, Mapping):
            name = item.get("name")
            socket_type = item.get("type")
        elif isinstance(item, (list, tuple)) and len(item) >= 1:
            name = item[0]
            socket_type = item[1] if len(item) >= 2 else None
        else:
            continue
        clean_name = str(name or f"value_{index}").strip() or f"value_{index}"
        clean_type = str(socket_type or "*").strip() or "*"
        entries.append((clean_name, clean_type))
    return entries


def _normalize_exec_io(value: Any) -> dict[str, list[tuple[str, str]]] | None:
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return None
        if not isinstance(parsed, Mapping):
            return None
        return _normalize_exec_io(parsed)
    if not isinstance(value, Mapping):
        return None
    inputs = _normalize_exec_io_entries(value.get("inputs"))
    outputs = _normalize_exec_io_entries(value.get("outputs"))
    if not inputs and not outputs:
        return None
    return {"inputs": inputs, "outputs": outputs}


def _exec_io_for_node(node: Any) -> dict[str, list[tuple[str, str]]] | None:
    if getattr(node, "class_type", None) != "vibecomfy.exec":
        return None
    return _normalize_exec_io(_exec_node_field(node, "io"))


def _exec_io_properties_payload(io: dict[str, list[tuple[str, str]]]) -> dict[str, list[list[str]]]:
    return {
        "inputs": [[name, socket_type] for name, socket_type in io["inputs"]],
        "outputs": [[name, socket_type] for name, socket_type in io["outputs"]],
    }


def _exec_dynamic_inputs(
    io: dict[str, list[tuple[str, str]]],
    incoming_by_input: Mapping[str, list[int]],
) -> list[dict[str, Any]]:
    inputs: list[dict[str, Any]] = []
    for slot_idx, (name, socket_type) in enumerate(io["inputs"]):
        slot_name = f"in_{slot_idx}"
        link_ids = sorted(incoming_by_input.get(slot_name, []))
        entry: dict[str, Any] = {
            "name": slot_name,
            "label": f"{name}: {socket_type}",
            "type": socket_type,
        }
        if link_ids:
            entry["link"] = link_ids[0]
        inputs.append(entry)
    return inputs


def _exec_dynamic_outputs(
    io: dict[str, list[tuple[str, str]]],
    output_links_by_slot: Mapping[int, list[int]],
) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for slot_idx, (name, socket_type) in enumerate(io["outputs"]):
        link_list = sorted(output_links_by_slot.get(slot_idx, []))
        outputs.append(
            {
                "name": f"out_{slot_idx}",
                "label": f"{name}: {socket_type}",
                "type": socket_type,
                "links": link_list if link_list else None,
                "slot_index": slot_idx,
            }
        )
    return outputs


def _emit_litegraph_node_dict(
    node: Any,
    *,
    litegraph_node_id: int,
    order: int,
    geometry: Mapping[str, Any],
    furniture: Mapping[str, Any],
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    schema: Any | None,
    include_main_positions: bool,
    widget_default_values: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    widget_names = _widget_names_for_emission(node.class_type, schema, node=node)

    # Step 6 (T8): re-stamp the verbatim captured properties blob as the base,
    # then overlay the IR identity keys.  When no captured blob exists (e.g.
    # programmatic workflows), fall back to fresh-construction — no regression.
    captured_blob = furniture.get("properties")
    if isinstance(captured_blob, dict) and captured_blob:
        properties = dict(captured_blob)
    else:
        properties = {}

    # ── IR identity keys ALWAYS win (merged ON TOP of any captured value) ──
    # Scrub stale ir_node_id from captured blobs (demoted in M5).
    properties.pop("ir_node_id", None)
    properties["vibecomfy_id"] = f"{node.class_type}_{order}"
    properties["Node name for S&R"] = node.class_type

    if schema is not None:
        properties["_vibecomfy_schema_provider"] = getattr(schema, "source_provider", "unknown")

    if node.uid:
        properties["vibecomfy_uid"] = node.uid

    if node.class_type == "vibecomfy.exec":
        exec_io = _exec_io_for_node(node)
        exec_source = _exec_node_field(node, "source")
        if exec_io is not None:
            vibecomfy_props = properties.get("vibecomfy")
            if not isinstance(vibecomfy_props, dict):
                vibecomfy_props = {}
                properties["vibecomfy"] = vibecomfy_props
            vibecomfy_props["kind"] = "code"
            vibecomfy_props["io"] = _exec_io_properties_payload(exec_io)
            intent_props = vibecomfy_props.get("intent")
            if not isinstance(intent_props, dict):
                intent_props = {}
                vibecomfy_props["intent"] = intent_props
            if isinstance(exec_source, str):
                intent_props["source"] = exec_source

    from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

    value_domain = _widget_value_domain_for_emission(
        node,
        widget_names_for_class(node.class_type),
        object_info_widget_order(node.class_type),
    )
    node_dict: dict[str, Any] = {
        "id": litegraph_node_id,
        "type": node.class_type,
        "pos": geometry["pos"],
        "size": geometry["size"],
        "flags": furniture["flags"],
        "order": order,
        "mode": furniture["mode"],
        "inputs": inputs,
        "outputs": outputs,
        "properties": properties,
        "widgets_values": _build_widget_values(
            node,
            widget_names,
            default_values=widget_default_values,
            value_domain=value_domain,
        ),
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
    return node_dict


def materialize_litegraph_node(
    class_type: str,
    fields: Mapping[str, Any],
    schema: Any | None,
    node_id: int,
    uid: str,
    pos: list[float] | tuple[float, float],
) -> dict[str, Any]:
    """Materialize one unlinked LiteGraph node using emitter-equivalent defaults.

    This is the creation-path substrate helper for agent-edit v2. It deliberately
    reuses the same widget ordering, property stamping, size defaults, and output
    slot construction that :func:`emit_ui_json` uses for a single node.
    """
    merged_fields: dict[str, Any] = {}
    schema_inputs = getattr(schema, "inputs", None)
    if isinstance(schema_inputs, dict):
        for name, spec in schema_inputs.items():
            default = getattr(spec, "default", None)
            if default is not None:
                merged_fields[name] = deepcopy(default)
    merged_fields.update(dict(fields))

    metadata: dict[str, Any] = {}
    retained_control = merged_fields.pop("control_after_generate", None)
    if isinstance(retained_control, str):
        metadata["control_after_generate"] = retained_control

    node = VibeNode(
        id=str(node_id),
        class_type=class_type,
        inputs=merged_fields,
        metadata=metadata,
        uid=uid,
    )
    geometry = {
        "pos": [
            _canonicalize_coord(float(pos[0])),
            _canonicalize_coord(float(pos[1])),
        ],
        "size": [_canonicalize_coord(s) for s in _STUB_NODE_SIZE],
    }
    furniture = _resolve_furniture(node, None)
    inputs: list[dict[str, Any]] = schema_input_sockets_for_unwired_node(
        schema,
        class_type,
        fields=merged_fields,
    )
    outputs: list[dict[str, Any]] = _schema_outputs_for_unwired_node(schema)
    if class_type == "vibecomfy.exec":
        exec_io = _exec_io_for_node(node)
        if exec_io is not None:
            inputs = _exec_dynamic_inputs(exec_io, {})
            outputs = _exec_dynamic_outputs(exec_io, {})
    return _emit_litegraph_node_dict(
        node,
        litegraph_node_id=int(node_id),
        order=0,
        geometry=geometry,
        furniture=furniture,
        inputs=inputs,
        outputs=outputs,
        schema=schema,
        include_main_positions=False,
    )


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
        length = getattr(raw_widgets, "length", None)
        shape = getattr(raw_widgets, "shape", None)
        has_dict_rows = bool(getattr(raw_widgets, "has_dict_rows", False))
        if length is None:
            length, recovered_shape, recovered_has_dict_rows = _raw_widget_shape_from_value(
                getattr(raw_widgets, "values", None)
            )
            if shape is None:
                shape = recovered_shape
            has_dict_rows = has_dict_rows or recovered_has_dict_rows
        return (
            int(length) if length is not None else None,
            str(shape or "unknown"),
            has_dict_rows,
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


def _widget_shape_identity_match(
    node_id: str,
    node: Any,
    matched_entries: Mapping[str, Mapping[str, Any]],
    raw_ui_node: Mapping[str, Any] | None,  # noqa: ARG001
) -> bool:
    uid = getattr(node, "uid", "")
    key = uid or node_id
    return key in matched_entries


def _has_object_info_widget_schema(
    class_type: str,
    schema_provider: Any | None,
) -> bool:
    raw_order = _raw_widget_order_from_provider(class_type, schema_provider)
    if raw_order:
        return True
    from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

    return bool(object_info_widget_order(class_type))


def _has_schema_default_regeneration_basis(
    node: Any,
    schema: Any | None,
    schema_provider: Any | None,
) -> bool:
    if _has_object_info_widget_schema(node.class_type, schema_provider):
        return True
    committed = widget_names_for_class(node.class_type)
    if committed is not None:
        return True
    schema_inputs = getattr(schema, "inputs", None)
    if isinstance(schema_inputs, dict) and schema_inputs:
        return True
    return bool(_schema_default_widget_values_for_node(node, schema))


def _schema_default_widget_values_for_node(
    node: Any,
    schema: Any | None,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    schema_inputs = getattr(schema, "inputs", None)
    if isinstance(schema_inputs, dict):
        for name, spec in schema_inputs.items():
            default = getattr(spec, "default", None)
            if default is not None:
                defaults[str(name)] = deepcopy(default)
    from vibecomfy.porting.object_info.consume import class_defaults  # noqa: PLC0415

    for name, value in class_defaults(node.class_type).items():
        defaults.setdefault(str(name), deepcopy(value))
    return defaults


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
        "explicit_widget_overflow": evidence.explicit_widget_overflow,
        "raw_widget_length_recovered": evidence.raw_widget_length_recovered,
        "value_domain": evidence.value_domain,
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
    for key in ("incoming_edge_sig", "outgoing_edge_sig", "semantic_link_set"):
        if key in delta:
            link_delta[key] = delta[key]
    for key, value in delta.items():
        if key not in {
            "widget_values_sig",
            "public_input_binding",
            "incoming_edge_sig",
            "outgoing_edge_sig",
            "semantic_link_set",
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
        "value_domain": getattr(getattr(verdict, "evidence", None), "value_domain", None),
        "has_raw_ui_payload": has_raw_ui_payload,
    }
    entry.update(_widget_shape_report_fields(verdict))
    recovery = getattr(verdict, "recovery", None)
    if getattr(verdict, "evidence", None) is not None and getattr(
        verdict.evidence, "raw_widget_length_recovered", False
    ):
        recovery = "raw_widgets_values_length"
    if recovery is not None:
        entry["widget_shape_recovery"] = recovery
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


def _pinned_uid_refusal(
    node_id: str,
    class_type: str,
    *,
    axis: str,
    reason: str,
    details: Mapping[str, Any],
) -> None:
    from vibecomfy.porting.refuse import RefusedEmit  # noqa: PLC0415

    raise RefusedEmit(
        f"Refusing to emit pinned raw UI node {node_id}: {reason}",
        diff={
            str(node_id): {
                "axis": axis,
                "node_id": str(node_id),
                "class_type": class_type,
                "reason": reason,
                "details": {**dict(details)},
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

    # Rich edges are structural authority. Extra/stale/nameless captured
    # input links are dropped; IR-only incoming edges are appended. Duplicate
    # captured names keep the first slot and clear the rest.
    seen_linked_inputs: set[str] = set()
    for raw_input in raw_inputs:
        if not isinstance(raw_input, dict) or raw_input.get("link") is None:
            continue
        input_name = raw_input.get("name")
        if input_name is None or str(input_name) == "":
            raw_input["link"] = None
            continue
        input_key = str(input_name)
        if input_key in seen_linked_inputs:
            raw_input["link"] = None
            continue
        current_link_ids = list(incoming_link_ids_by_input.get(input_key, []))
        if len(current_link_ids) == 1:
            raw_input["link"] = current_link_ids[0]
            seen_linked_inputs.add(input_key)
        elif current_link_ids:
            raw_input["link"] = current_link_ids[0]
            seen_linked_inputs.add(input_key)
        else:
            raw_input["link"] = None

    for input_name, link_ids in incoming_link_ids_by_input.items():
        if not link_ids or input_name in seen_linked_inputs:
            continue
        raw_inputs.append(
            {
                "name": input_name,
                "type": "*",
                "link": link_ids[0],
            }
        )
        seen_linked_inputs.add(input_name)

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
        slot_raw = raw_output.get("slot_index", idx)
        try:
            slot = int(idx if slot_raw is None else slot_raw)
        except (TypeError, ValueError):
            slot = idx
        raw_output["slot_index"] = slot
        raw_link_refs = _coerce_link_refs(raw_output.get("links"))
        current_link_ids = sorted(outgoing_link_ids_by_slot.get(slot, []))
        if raw_link_refs or current_link_ids:
            # Rich-edge authority: always stamp the IR's current ids.
            # Extra captured output links are stale and are dropped.
            # Missing captured output links are filled from the IR.
            raw_output["links"] = current_link_ids or None
            seen_output_slots.add(slot)

    missing_output_slots = sorted(
        slot
        for slot, link_ids in outgoing_link_ids_by_slot.items()
        if link_ids and slot not in seen_output_slots
    )
    for slot in missing_output_slots:
        raw_outputs.append(
            {
                "name": f"output_{slot}",
                "type": "*",
                "links": sorted(outgoing_link_ids_by_slot.get(slot, [])),
                "slot_index": slot,
            }
        )
    return node_dict


def _raw_ui_payload_for_pin(
    raw_ui_node: Mapping[str, Any],
    *,
    node_id: str,
    class_type: str,
    canonical_uid: str,
    litegraph_node_id: int,
    order: int,
    incoming_link_ids_by_input: Mapping[str, list[int]],
    outgoing_link_ids_by_slot: Mapping[int, list[int]],
) -> dict[str, Any]:
    # Stable-UID gate: a pinned raw node is only emitted under an explicit
    # canonical uid from the VibeNode. Never fall back to captured properties,
    # node id, or stale captured identity — fail closed instead.
    if not isinstance(canonical_uid, str) or not canonical_uid.strip():
        _pinned_uid_refusal(
            node_id,
            class_type,
            axis="pinned_stable_uid",
            reason="missing_stable_uid",
            details={
                "canonical_uid_type": type(canonical_uid).__name__,
                "canonical_uid": canonical_uid if isinstance(canonical_uid, str) else None,
            },
        )

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

    # Properties gate: the copied payload must expose a dict to stamp into.
    properties = node_dict.get("properties")
    if properties is None:
        properties = {}
        node_dict["properties"] = properties
    elif not isinstance(properties, dict):
        _pinned_uid_refusal(
            node_id,
            class_type,
            axis="pinned_properties",
            reason="invalid_captured_properties",
            details={"properties_type": type(properties).__name__},
        )

    # Canonical identity overlay: scrub the demoted stale key, then stamp the
    # canonical uid so it always wins over missing/stale captured values.
    properties.pop("ir_node_id", None)
    properties["vibecomfy_uid"] = canonical_uid
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
    widget_names = _widget_names_for_emission(
        node.class_type,
        schema,
        node=node,
        schema_provider=schema_provider,
    )
    from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

    value_domain = _widget_value_domain_for_emission(
        node,
        widget_names_for_class(node.class_type),
        object_info_widget_order(node.class_type),
    )
    candidate_widget_count = len(
        _build_widget_values(node, widget_names, value_domain=value_domain)
    )
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
    primitive_control_widget = (
        node.class_type in _PRIMITIVE_CONTROL_WIDGET_CLASSES
        and schema_widget_count == 1
        and candidate_widget_count == 2
        and programmatic_widget_count == 2
        and raw_widget_count is None
        and isinstance(node_widgets, dict)
        and node_widgets.get("widget_1") in {"fixed", "randomize", "increment", "decrement"}
    )
    overflow = False
    explicit_widget_overflow = False
    if schema_widget_count is not None and not provenance["schema_less"]:
        if has_dict_rows:
            overflow = largest_observed_count > schema_widget_count
        elif primitive_control_widget:
            overflow = False
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
            explicit_widget_overflow = True
        else:
            overflow = largest_observed_count > schema_widget_count
            explicit_widget_overflow = (
                programmatic_widget_count > schema_widget_count
                and not (
                    raw_widget_count is not None
                    and programmatic_widget_count <= raw_widget_count
                )
            )

    raw_widget_length_recovered = False
    raw_widgets = getattr(node, "raw_widgets", None)
    if raw_widgets is not None and getattr(raw_widgets, "length", None) is None:
        raw_widget_length_recovered = raw_widget_count is not None

    return WidgetShapeEvidence(
        node_id=str(node.id),
        class_type=str(node.class_type),
        schema_less=bool(provenance["schema_less"]),
        confidence=provenance.get("confidence"),
        raw_widget_count=raw_widget_count,
        candidate_widget_count=candidate_widget_count,
        schema_widget_count=schema_widget_count,
        compacted_widget_names=tuple(
            name
            for index, name in enumerate(widget_names)
            if name is not None and name != f"widget_{index}"
        ),
        raw_widget_shape=raw_widget_shape,
        has_dict_rows=has_dict_rows,
        overflow=overflow,
        provider=provenance.get("provider"),
        explicit_widget_overflow=explicit_widget_overflow,
        raw_widget_length_recovered=raw_widget_length_recovered,
        value_domain=value_domain,
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
    extra: dict[str, Any] | None = None,
    definitions: dict[str, Any] | None = None,
    change_report_out: list | None = None,
    guard_original_ui: Mapping[str, Any] | None = None,
    guard_resolved_ops: Any = None,
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
    _raise_embedded_api_links(wf, surface="UI serialization")

    # ── Law 1 door passthrough (batch 2) ───────────────────────────────────
    # An UNTOUCHED graph (fingerprint unchanged since offline ingest) is
    # re-emitted byte-faithfully from the wire data captured at the ingest
    # boundary: original id/version/counters, link ids/order/type,
    # extra/definitions/state, groups, node geometry/order/properties, and
    # opaque keys.  A semantic edit (node/widget/edge change) takes the
    # deterministic reconstruction path below instead.  The passthrough is
    # bypassed whenever the caller asks for a different output shape (flat/
    # virtual-wire toggle, include_main_positions, explicit extra/definitions/
    # prior_store/layout overrides, strict) or the graph was ingested through
    # the comfy converter.  ``guard_original_ui`` (guard_full_ui) is still
    # enforced on the passthrough envelope — the exit fidelity is not weakened.
    _door = (wf.metadata or {}).get(_UI_DOOR_KEY)
    if _door_ui_passthrough_applicable(
        wf,
        _door,
        include_virtual_wires=include_virtual_wires,
        include_main_positions=include_main_positions,
        extra=extra,
        definitions=definitions,
        prior_store=prior_store,
        layout=layout,
        strict=strict,
    ):
        envelope = _emit_untouched_door_ui(_door)
        if guard_original_ui is not None:
            from vibecomfy.porting.layout.delta import compute_field_delta  # noqa: PLC0415
            from vibecomfy.porting.refuse import guard_emit as _guard_emit  # noqa: PLC0415

            _snap = (wf.metadata or {}).get("_ingest_snapshot", {})
            _delta = compute_field_delta(_snap, wf) if _snap else {}
            _guard_emit(guard_original_ui, envelope, _delta, resolved_ops=guard_resolved_ops)
        return envelope

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

    # Flat mode (include_virtual_wires=False): the layout engine must compute
    # positions against the FLAT execution graph — virtual-wire nodes removed,
    # broadcast/Reroute edges already resolved — so emitted geometry is a pure
    # function of the flat graph.  Without this, a workflow whose helpers were
    # retained in the IR (--keep-virtual-wires) would lay out real nodes at
    # different layers/lanes than the same flat graph whose helpers were
    # resolved during conversion, breaking flat round-trip byte-equivalence.
    _layout_wf = wf
    if not include_virtual_wires and virtual_wire_ids:
        _layout_wf = _flat_layout_workflow(wf, virtual_wire_ids, display_edges)

    _engine_result = _compute_layout(
        _layout_wf,
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
    widget_shape_default_values: dict[str, Mapping[str, Any] | None] = {}
    new_node_keys: set[str] = set(reconcile_result.new)
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
        identity_matched = _widget_shape_identity_match(
            node_id,
            node,
            matched_entries,
            raw_ui_node,
        )
        field_delta, link_delta = _split_widget_shape_deltas(_field_delta_by_uid, node_id, node)
        layout_entry = _layout_entry_for_widget_shape(node_id, node, matched_entries)
        allow_schema_defaults = (
            raw_ui_node is None
            and not identity_matched
            and schema is not None
            and not prov["schema_less"]
            and prov.get("provider") == "object_info_index"
            and expected_widget_count is not None
            and expected_widget_count > 1
            and (prov.get("confidence") is None or prov["confidence"] > _LOW_CONFIDENCE_THRESHOLD)
            and not evidence.has_dict_rows
            and _has_schema_default_regeneration_basis(node, schema, schema_provider)
        )
        verdict = _decide_widget_shape(
            evidence,
            raw_widget_payloads={node_id: getattr(node, "raw_widgets", None)},
            raw_payloads={node_id: raw_ui_node} if raw_ui_node is not None else {},
            layout_entries={node_id: layout_entry} if layout_entry is not None else {},
            field_deltas={node_id: field_delta} if field_delta else {},
            link_deltas={node_id: link_delta} if link_delta else {},
            identity_matched=identity_matched,
            allow_schema_default_regenerate=allow_schema_defaults,
            is_new_node=(
                (node.uid or node_id) in new_node_keys
                and getattr(node, "raw_widgets", None) is None
                and raw_ui_node is None
            ),
        )
        widget_shape_verdicts[node_id] = verdict
        widget_shape_default_values[node_id] = (
            _schema_default_widget_values_for_node(node, schema)
            if getattr(verdict, "use_schema_defaults", False)
            else None
        )

    refused_verdicts = [
        verdict
        for verdict in widget_shape_verdicts.values()
        if verdict.refuse
    ]
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

    # Assign link IDs: prefer the captured wire ids for structurally unchanged
    # links (Law 1 wire preference); mint fresh ids above the captured maximum
    # for changed/added links.  Non-door workflows keep the deterministic
    # 1-indexed numbering (the captured map is empty there).
    EdgeKey = tuple[str, str, str, str]
    captured_link_ids = _captured_link_id_map(_door)
    used_link_ids: set[int] = set()
    link_id_map: dict[EdgeKey, int] = {}
    next_link_id = max(captured_link_ids.values(), default=0) + 1
    for edge in sorted_edges:
        key = (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
        captured = captured_link_ids.get(key)
        if captured is not None and captured not in used_link_ids:
            link_id_map[key] = captured
            used_link_ids.add(captured)
            continue
        while next_link_id in used_link_ids:
            next_link_id += 1
        link_id_map[key] = next_link_id
        used_link_ids.add(next_link_id)
        next_link_id += 1
    last_link_id = max(used_link_ids) if used_link_ids else 0

    # Edge lookup by node
    edges_from: dict[str, list[Any]] = defaultdict(list)
    edges_to: dict[str, list[Any]] = defaultdict(list)
    for edge in sorted_edges:
        edges_from[edge.from_node].append(edge)
        edges_to[edge.to_node].append(edge)

    # Build nodes
    nodes: list[dict[str, Any]] = []
    last_node_id = max(id_remap.values()) if id_remap else 0
    # Emitted socket arrays per node, captured so the link loop below can repair
    # dangling endpoints against the sockets the emitted graph actually has
    # (R2-D1: working-graph sockets are authoritative; never project a phantom
    # port).
    emitted_outputs_by_node: dict[str, list[dict[str, Any]]] = {}
    emitted_inputs_by_node: dict[str, list[dict[str, Any]]] = {}

    for order, node_id in enumerate(order_list):
        node = wf.nodes[node_id]
        key = _node_key(node_id)
        verdict = widget_shape_verdicts[node_id]
        if verdict.pin_opaque and _exec_io_for_node(node) is None:
            incoming_link_ids_by_input: dict[str, list[int]] = defaultdict(list)
            for edge in edges_to[node_id]:
                lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
                incoming_link_ids_by_input[edge.to_input].append(lid)
            outgoing_link_ids_by_slot: dict[int, list[int]] = defaultdict(list)
            for edge in edges_from[node_id]:
                slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
                lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
                outgoing_link_ids_by_slot[slot].append(lid)
            pinned = _raw_ui_payload_for_pin(
                verdict.raw_ui_node or {},
                node_id=node_id,
                class_type=node.class_type,
                canonical_uid=node.uid,
                litegraph_node_id=id_remap[node_id],
                order=order,
                incoming_link_ids_by_input=incoming_link_ids_by_input,
                outgoing_link_ids_by_slot=outgoing_link_ids_by_slot,
            )
            # The pinned raw copy comes from raw UI evidence and may lack mode;
            # stamp the same IR-authoritative mode used by compilation.
            pinned["mode"] = _resolve_furniture(node, matched_entries.get(key))["mode"]
            emitted_outputs_by_node[node_id] = pinned.get("outputs") or []
            emitted_inputs_by_node[node_id] = pinned.get("inputs") or []
            nodes.append(pinned)
            continue
        matched_entry = matched_entries.get(key)
        # T9b: reconcile-driven merge.
        #   matched → verbatim pos/size/flags/color/properties/group/title from the entry;
        #             mode remains IR-authoritative.
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
            # First-class node geometry is the direct-ingest source of truth; the
            # engine owns geometry only when no complete captured pair exists.
            geometry = (
                _captured_geometry(node)
                or engine_positions.get(node.uid)
                or _stub_layout(order)
            )
            furniture = _resolve_furniture(node, None)
        schema = schema_cache.get(node.class_type)
        schema_outputs = list(getattr(schema, "outputs", None) or []) if schema else []
        exec_io = _exec_io_for_node(node)

        # --- outputs list ---
        outputs: list[dict[str, Any]] = []
        # Build a set of (from_output_val) → links for this node from edges
        output_links_by_slot: dict[int, list[int]] = defaultdict(list)
        for edge in edges_from[node_id]:
            slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
            eid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
            output_links_by_slot[slot].append(eid)

        if exec_io is not None:
            outputs = _exec_dynamic_outputs(exec_io, output_links_by_slot)
        elif schema_outputs:
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
        widget_names = _widget_names_for_emission(
            node.class_type,
            schema,
            node=node,
            schema_provider=schema_provider,
        )
        widget_name_set = {name for name in widget_names if name is not None}
        full_committed = widget_names_for_class(node.class_type)
        if full_committed is not None:
            widget_name_set.update(n for n in full_committed if n is not None)

        # --- inputs list (physical ComfyUI socket order) ---
        # Only LINKED inputs get an input-slot entry; a linked input whose name is a
        # widget-type input additionally carries widget:{name:...} (widget→link).
        incoming_sorted = _ordered_incoming_edges(edges_to[node_id], schema)
        incoming_link_ids_by_input: dict[str, list[int]] = defaultdict(list)
        for edge in incoming_sorted:
            lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
            incoming_link_ids_by_input[edge.to_input].append(lid)
        inputs: list[dict[str, Any]] = []
        if exec_io is not None:
            inputs = _exec_dynamic_inputs(exec_io, incoming_link_ids_by_input)
        else:
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

        emitted_outputs_by_node[node_id] = outputs
        emitted_inputs_by_node[node_id] = inputs
        nodes.append(
            _emit_litegraph_node_dict(
                node,
                litegraph_node_id=id_remap[node_id],
                order=order,
                geometry=geometry,
                furniture=furniture,
                inputs=inputs,
                outputs=outputs,
                schema=schema,
                include_main_positions=include_main_positions,
                widget_default_values=widget_shape_default_values[node_id],
            )
        )

    # Build global links array: [link_id, from_node, from_slot, to_node, to_slot, type]
    links: list[list[Any]] = []
    dangling_links: list[dict[str, Any]] = []
    for edge in sorted_edges:
        from_class = wf.nodes[edge.from_node].class_type if edge.from_node in wf.nodes else ""
        from_slot, socket_type = _resolve_output_slot_and_type(edge.from_output, from_class, schema_cache)
        from_exec_io = _exec_io_for_node(wf.nodes[edge.from_node]) if edge.from_node in wf.nodes else None
        if from_exec_io is not None:
            try:
                candidate_slot = int(edge.from_output.split("_", 1)[1]) if edge.from_output.startswith("out_") else int(edge.from_output)
            except (TypeError, ValueError):
                candidate_slot = from_slot
            if 0 <= candidate_slot < len(from_exec_io["outputs"]):
                from_slot = candidate_slot
                socket_type = from_exec_io["outputs"][candidate_slot][1]
        # to_slot = index of this input in the to-node's physical input array.
        to_exec_io = _exec_io_for_node(wf.nodes[edge.to_node]) if edge.to_node in wf.nodes else None
        if to_exec_io is not None and edge.to_input.startswith("in_"):
            try:
                to_slot = int(edge.to_input.split("_", 1)[1])
            except ValueError:
                to_slot = 0
        else:
            target_schema = schema_cache.get(wf.nodes[edge.to_node].class_type)
            incoming_sorted = _ordered_incoming_edges(edges_to[edge.to_node], target_schema)
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
        if (
            to_exec_io is not None
            and 0 <= to_slot < len(to_exec_io["inputs"])
            and (not socket_type or socket_type in {"*", "UNKNOWN"})
        ):
            socket_type = to_exec_io["inputs"][to_slot][1]
        # R2-D1: repair malformed endpoints BEFORE projection.  The working
        # graph's emitted sockets are authoritative — never emit a link whose
        # source/target port does not exist in the emitted node.  Remap the
        # phantom slot to the matching emitted socket by canonical name.  When
        # no remap exists the edge is NOT dropped: it accumulates into a single
        # RefusedEmit (B2) so every input edge is either emitted/remapped or the
        # whole emit is refused with full endpoint evidence.
        emitted_outputs = emitted_outputs_by_node.get(edge.from_node)
        emitted_inputs = emitted_inputs_by_node.get(edge.to_node)
        source_endpoint: dict[str, Any] = {
            "node_id": edge.from_node,
            "requested_output": edge.from_output,
            "requested_slot": from_slot,
            "emitted_sockets": _emitted_socket_array_evidence(emitted_outputs),
        }
        target_endpoint: dict[str, Any] = {
            "node_id": edge.to_node,
            "requested_input": edge.to_input,
            "requested_slot": to_slot,
            "emitted_sockets": _emitted_socket_array_evidence(emitted_inputs),
        }
        source_socket_missing = False
        target_socket_missing = False
        if emitted_outputs is not None:
            canonical_from_name = _canonical_emitted_output_name(
                edge.from_output, from_slot
            )
            remapped = _emitted_socket_slot_for_link(
                emitted_outputs, from_slot, canonical_from_name
            )
            if remapped is None:
                source_socket_missing = True
                source_endpoint["canonical_socket_name"] = canonical_from_name
                source_endpoint["attempted_remaps"] = _remap_attempts_evidence(
                    emitted_outputs, from_slot, canonical_from_name
                )
            else:
                from_slot = remapped
        if emitted_inputs is not None:
            remapped = _emitted_socket_slot_for_link(
                emitted_inputs, to_slot, edge.to_input
            )
            if remapped is None:
                target_socket_missing = True
                target_endpoint["attempted_remaps"] = _remap_attempts_evidence(
                    emitted_inputs, to_slot, edge.to_input
                )
            else:
                to_slot = remapped
        if source_socket_missing or target_socket_missing:
            missing = (
                "source_socket"
                if target_socket_missing is False
                else "target_socket"
                if source_socket_missing is False
                else "source_and_target_socket"
            )
            dangling_links.append(
                {
                    "key": (
                        f"{edge.from_node}.{edge.from_output} "
                        f"-> {edge.to_node}.{edge.to_input}"
                    ),
                    "evidence": {
                        "source": source_endpoint,
                        "target": target_endpoint,
                        "missing": missing,
                    },
                }
            )
            continue
        lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
        links.append(
            [lid, id_remap[edge.from_node], from_slot, id_remap[edge.to_node], to_slot, socket_type or ""]
        )

    if dangling_links:
        from vibecomfy.porting.refuse import (  # noqa: PLC0415
            refused_dangling_links as _refused_dangling_links,
        )

        raise _refused_dangling_links(dangling_links)

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
    # ``extra`` has exactly ONE storage owner per emit: the caller's explicit
    # ``extra`` kwarg XOR the door-captured wire ``extra`` — never both.  When
    # the caller supplies ``extra`` it is the sole source (sidecar/ds state);
    # otherwise the door-captured wire ``extra`` is the sole source so
    # ds/frontendVersion/VHS_* and opaque keys survive re-emission (Law 1
    # wire preference).  The fresh breadcrumb is stamped on top either way.
    merged_extra: dict[str, Any] = {}
    if extra:
        merged_extra.update(dict(extra))
    else:
        captured_extra = _door_top(_door).get("extra") if isinstance(_door_top(_door), Mapping) else None
        if isinstance(captured_extra, Mapping):
            merged_extra.update(dict(captured_extra))
    merged_extra["vibecomfy"] = dict(breadcrumb)

    # When include_main_positions=True, ensure extra.ds (canvas drag/scale state) is
    # present, falling back to a fixed machine-independent default.  The lean default
    # (include_main_positions=False) omits ds entirely.
    if include_main_positions and "ds" not in merged_extra:
        merged_extra["ds"] = dict(_DEFAULT_DS)

    # --- groups: merge remapped IR groups with engine-generated subgraph groups ---
    #   Order: IR groups first, then engine_groups (suppressing duplicates whose
    #   ``title`` matches an IR group title).  All groups are
    #   canonicalized when ``include_main_positions=True``.
    ir_groups = _remap_ir_groups(wf, order_list, id_remap)
    ir_titles: set[str] = {g.get("title", "") for g in ir_groups if g.get("title")}
    emitted_groups: list[dict[str, Any]] = list(ir_groups)
    for eg in engine_groups:
        if eg.get("title", "") not in ir_titles:
            emitted_groups.append(eg)
    if include_main_positions and emitted_groups:
        _canonicalize_group_geometry(emitted_groups)

    envelope: dict[str, Any] = {
        "id": _wire_id(wf, _door),
        "version": _wire_version(_door),
        "last_node_id": _wire_counter(_door, "last_node_id", last_node_id),
        "last_link_id": _wire_counter(_door, "last_link_id", last_link_id),
        "groups": emitted_groups,
        "nodes": nodes,
        "links": links,
        "extra": merged_extra,
    }

    # Subgraph definitions: caller-provided `definitions` (from sidecar envelope)
    # takes precedence.  When the retained IR definitions differ from the
    # door-captured blob (a definitions-only edit: label, ports, add/remove),
    # emit from the IR so the edit is not silently discarded.  Otherwise keep
    # the captured wire blob so untouched subgraph bodies stay byte-stable.
    effective_defs = definitions
    if effective_defs is None:
        captured_defs = (
            _door_top(_door).get("definitions")
            if isinstance(_door_top(_door), Mapping)
            else None
        )
        metadata = getattr(wf, "metadata", None)
        ir_defs = metadata.get("definitions") if isinstance(metadata, Mapping) else None
        from vibecomfy.ingest.normalize import _door_freeze  # noqa: PLC0415

        if (
            isinstance(ir_defs, Mapping)
            and isinstance(captured_defs, Mapping)
            and _door_freeze(ir_defs) != _door_freeze(captured_defs)
        ):
            effective_defs = _emit_definitions(wf)
            if effective_defs is None:
                effective_defs = deepcopy(ir_defs)
        else:
            effective_defs = (
                deepcopy(captured_defs) if isinstance(captured_defs, Mapping) else _emit_definitions(wf)
            )
    if effective_defs is not None:
        if effective_defs is definitions:
            effective_defs = deepcopy(effective_defs)
        for sg in effective_defs.get("subgraphs", []):
            sg_extra = dict(sg.get("extra") or {})
            sg_extra["vibecomfy"] = dict(breadcrumb)
            sg["extra"] = sg_extra
        envelope["definitions"] = effective_defs
        envelope["state"] = {
            "lastNodeId": _wire_counter(_door, "last_node_id", last_node_id),
            "lastLinkId": _wire_counter(_door, "last_link_id", last_link_id),
            "lastRerouteId": 0,
        }

    # When include_main_positions=True, always emit state counters even if there
    # are no definitions (the lean default ties state to definitions presence).
    if include_main_positions and "state" not in envelope:
        envelope["state"] = {
            "lastNodeId": _wire_counter(_door, "last_node_id", last_node_id),
            "lastLinkId": _wire_counter(_door, "last_link_id", last_link_id),
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
        _guard_emit(guard_original_ui, envelope, _delta, resolved_ops=guard_resolved_ops)

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
            emitted_outputs = len(node.get("outputs", []))
            schema_output_count = len(schema_outputs)
            if emitted_outputs > schema_output_count:
                errors.append(
                    f"node {node['id']}({class_type}): output slot count "
                    f"{emitted_outputs} != schema output count {schema_output_count}"
                )
            elif emitted_outputs < schema_output_count:
                # Source-faithful pin (SaveImage/SaveVideo often emit
                # outputs=[] while the schema lists a dummy socket).
                skipped.append(
                    {
                        "node_id": node["id"],
                        "class_type": class_type,
                        "reason": (
                            f"source-faithful output count {emitted_outputs} "
                            f"< schema {schema_output_count}"
                        ),
                    }
                )

    return {"ok": not errors, "errors": errors, "skipped": skipped}


__all__ = [
    "WidgetShapeEvidence",
    "derive_widget_shape_evidence",
    "extract_raw_ui_node_map",
    "materialize_litegraph_node",
    "_normalize_pinned_node_link_refs",
    "_raw_ui_payload_for_pin",
    "emit_ui_json",
    "offline_emitter_normalizer_self_consistency_check",
    "structural_validate",
    "default_output_path",
    "ExitGuardResult",
    "guard_exit_ui",
    "pin_untouched_ui",
]


# ── Emit-exit fidelity guard (batch 15) ──
"""Independent emit-exit fidelity guard.

Validates that ``emit(workflow)`` differs from the original ingest UI only
where the accepted Δ (landed ops) attributes a change.  This is the
IR/emit successor of the raw-JSON ``guard_full_ui`` invariant: untouched
nodes, links, and scope fields stay byte-identical.
"""

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    EditOp,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.report import PortIssue


def _issue(
    code: str,
    message: str,
    *,
    severity: Literal["error", "warning", "info"] = "error",
    detail: Mapping[str, Any] | None = None,
) -> PortIssue:
    return PortIssue(code=code, message=message, severity=severity, detail=dict(detail or {}))


@dataclass(frozen=True, slots=True)
class ExitGuardResult:
    ok: bool
    diagnostics: tuple[PortIssue, ...] = ()
    normalize_fallback_used: bool = False
    normalize_allow_list_used: bool = False


def _node_uid(node: Mapping[str, Any]) -> str | None:
    properties = node.get("properties")
    if isinstance(properties, Mapping):
        uid = properties.get("vibecomfy_uid")
        if isinstance(uid, str) and uid:
            return uid
    node_id = node.get("id")
    if node_id is None:
        return None
    text = str(node_id)
    return text or None


def _link_id(link: Any) -> int | None:
    if isinstance(link, Mapping) and isinstance(link.get("id"), int):
        return link["id"]
    if isinstance(link, Sequence) and not isinstance(link, (str, bytes)):
        if link and isinstance(link[0], int):
            return link[0]
    return None


def _iter_scopes(graph: Mapping[str, Any], scope_path: str = "") -> list[tuple[str, Mapping[str, Any]]]:
    scopes: list[tuple[str, Mapping[str, Any]]] = [(scope_path, graph)]
    definitions = graph.get("definitions")
    if not isinstance(definitions, Mapping):
        return scopes
    subgraphs = definitions.get("subgraphs")
    if not isinstance(subgraphs, list):
        return scopes
    for index, definition in enumerate(subgraphs):
        if isinstance(definition, Mapping):
            child = f"{scope_path}/sg{index}" if scope_path else f"sg{index}"
            scopes.extend(_iter_scopes(definition, child))
    return scopes


def _index_nodes(graph: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for scope_path, scope in _iter_scopes(graph):
        nodes = scope.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            uid = _node_uid(node)
            if uid is not None:
                index[(scope_path, uid)] = node
    return index


def _index_links(graph: Mapping[str, Any]) -> dict[tuple[str, int], Any]:
    index: dict[tuple[str, int], Any] = {}
    for scope_path, scope in _iter_scopes(graph):
        links = scope.get("links")
        if not isinstance(links, list):
            continue
        for link in links:
            link_id = _link_id(link)
            if link_id is not None:
                index[(scope_path, link_id)] = link
    return index


def _scope_node_uids(scope_graph: Mapping[str, Any]) -> list[str]:
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return []
    result: list[str] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        uid = _node_uid(node)
        if uid is not None:
            result.append(uid)
    return result


def _value_diff_paths(original: Any, candidate: Any, prefix: str = "") -> list[str]:
    if original == candidate:
        return []
    if isinstance(original, Mapping) and isinstance(candidate, Mapping):
        paths: list[str] = []
        for key in sorted(set(original) | set(candidate)):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_value_diff_paths(original.get(key), candidate.get(key), child_prefix))
        return paths
    if isinstance(original, list) and isinstance(candidate, list):
        paths: list[str] = []
        max_len = max(len(original), len(candidate))
        for index in range(max_len):
            child_prefix = f"{prefix}[{index}]"
            left = original[index] if index < len(original) else None
            right = candidate[index] if index < len(candidate) else None
            paths.extend(_value_diff_paths(left, right, child_prefix))
        return paths
    return [prefix or "<root>"]


# Emit may materialize derived identity/layout furniture on every node
# even when the accepted Δ did not touch that node.  These paths are not
# editable-quotient changes and must not fail the exit guard closed.
_EMIT_FURNITURE_PREFIXES = (
    "order",
    "properties.vibecomfy_id",
    "properties._vibecomfy_schema_provider",
)
_EMIT_SCOPE_FURNITURE = frozenset({"version", "id", "extra", "config"})


def _path_is_at_or_below(path: str, allowed: str) -> bool:
    return path == allowed or path.startswith(f"{allowed}.") or path.startswith(f"{allowed}[")


def _is_emit_furniture_path(path: str) -> bool:
    return any(
        path == prefix or path.startswith(f"{prefix}.") or path.startswith(f"{prefix}[")
        for prefix in _EMIT_FURNITURE_PREFIXES
    )


def _all_diffs_op_allowed(diffs: list[str], allowed_paths: set[str]) -> bool:
    if not allowed_paths:
        return False
    return all(any(_path_is_at_or_below(diff, allowed) for allowed in allowed_paths) for diff in diffs)


def _counter_advanced_or_materialized(original: Any, candidate: Any) -> bool:
    if isinstance(candidate, int) and original is None:
        return True
    if isinstance(original, int) and isinstance(candidate, int) and candidate >= original:
        return True
    return False


def _attribution(ops: Iterable[EditOp]) -> dict[str, Any]:
    node_paths: dict[tuple[str, str], set[str]] = {}
    scope_field_paths: dict[str, set[str]] = {}
    removed_nodes: set[tuple[str, str]] = set()
    new_nodes: set[tuple[str, str]] = set()
    touched_scopes: set[str] = set()
    link_ops: set[str] = set()

    def allow_node_paths(scope_path: str, uid: str, *paths: str) -> None:
        node_paths.setdefault((scope_path, uid), set()).update(paths)
        touched_scopes.add(scope_path)

    for op in ops:
        if isinstance(op, SetNodeFieldOp):
            allow_node_paths(op.target.scope_path, op.target.uid, "widgets_values", "inputs", "properties")
            continue
        if isinstance(op, SetModeOp):
            allow_node_paths(op.target.scope_path, op.target.uid, "mode")
            continue
        if isinstance(op, UpsertLinkOp):
            allow_node_paths(op.source.scope_path, op.source.uid, "outputs")
            allow_node_paths(op.target.scope_path, op.target.uid, "inputs")
            link_ops.add(op.target.scope_path)
            continue
        if isinstance(op, RemoveLinkOp):
            allow_node_paths(op.target.scope_path, op.target.uid, "inputs", "outputs")
            link_ops.add(op.target.scope_path)
            continue
        if isinstance(op, RemoveNodeOp):
            removed_nodes.add((op.target.scope_path, op.target.uid))
            link_ops.add(op.target.scope_path)
            continue
        if isinstance(op, AddNodeOp):
            uid = op.uid or ""
            if uid:
                new_nodes.add((op.scope_path, uid))
                allow_node_paths(op.scope_path, uid, "widgets_values", "inputs", "outputs", "pos", "size", "properties", "mode", "type", "id", "order", "flags")
            if op.inputs:
                for source in op.inputs.values():
                    allow_node_paths(source.scope_path, source.uid, "outputs")
            scope_field_paths.setdefault(op.scope_path, set()).update({"groups", "last_node_id", "last_link_id"})
            link_ops.add(op.scope_path)
    return {
        "node_paths": node_paths,
        "scope_field_paths": scope_field_paths,
        "removed_nodes": removed_nodes,
        "new_nodes": new_nodes,
        "touched_scopes": touched_scopes,
        "link_ops": link_ops,
    }


def _guard_counter(scope_path: str, field: str, original: Any, candidate: Any) -> list[PortIssue]:
    if original == candidate:
        return []
    if _counter_advanced_or_materialized(original, candidate):
        return []
    return [
        _issue(
            "full_ui_counter_changed_unattributed",
            "Candidate changed a LiteGraph id counter except for monotonic advancement.",
            detail={"scope_path": scope_path, "field": field, "original": original, "candidate": candidate},
        )
    ]


def _guard_subgraph_state(scope_path: str, original: Any, candidate: Any) -> list[PortIssue]:
    if original == candidate:
        return []
    original_state = original if isinstance(original, Mapping) else {}
    candidate_state = candidate if isinstance(candidate, Mapping) else {}
    diagnostics: list[PortIssue] = []
    keys = set(original_state) | set(candidate_state)
    for key in sorted(keys):
        if key in {"lastNodeId", "lastLinkId"}:
            diagnostics.extend(_guard_counter(scope_path, f"state.{key}", original_state.get(key), candidate_state.get(key)))
            continue
        if original_state.get(key) != candidate_state.get(key):
            diagnostics.append(
                _issue(
                    "full_ui_scope_field_changed_unattributed",
                    "Candidate changed a subgraph state field without an attributed operation.",
                    detail={"scope_path": scope_path, "field": f"state.{key}"},
                )
            )
    return diagnostics


def pin_untouched_ui(
    original_ui: Mapping[str, Any],
    candidate_ui: Mapping[str, Any],
    ops: Sequence[EditOp] = (),
) -> dict[str, Any]:
    """Restore original node/link JSON for anything the accepted Δ did not touch.

    Reconstructive emit rewrites every node.  The exit snapshot must keep
    unattributed nodes and links byte-identical to the ingest UI so
    ``guard_exit_ui`` can fail closed on real drift.
    """
    attribution = _attribution(ops)
    attributed_nodes = set(attribution["node_paths"]) | set(attribution["new_nodes"])
    pinned = deepcopy(dict(candidate_ui))
    original_nodes = _index_nodes(original_ui)
    original_scopes = dict(_iter_scopes(original_ui))
    for scope_path, scope in _iter_scopes(pinned):
        if not isinstance(scope, dict):
            continue
        nodes = scope.get("nodes")
        if isinstance(nodes, list):
            for index, node in enumerate(nodes):
                if not isinstance(node, Mapping):
                    continue
                uid = _node_uid(node)
                if uid is None:
                    continue
                key = (scope_path, uid)
                original_node = original_nodes.get(key)
                if original_node is None:
                    continue
                if key in attributed_nodes:
                    allowed = attribution["node_paths"].get(key, set())
                    merged = deepcopy(dict(original_node))
                    for field in allowed:
                        if field in node:
                            merged[field] = deepcopy(node[field])
                    nodes[index] = merged
                    continue
                nodes[index] = deepcopy(dict(original_node))
        original_scope = original_scopes.get(scope_path)
        if original_scope is None:
            continue
        if scope_path not in attribution["link_ops"] and "links" in original_scope:
            scope["links"] = deepcopy(original_scope.get("links") or [])
        allowed_scope = attribution["scope_field_paths"].get(scope_path, set())
        for key in list(scope):
            if key in {"nodes", "links", "definitions", "last_node_id", "last_link_id"}:
                continue
            if key == "groups" and "groups" in allowed_scope:
                continue
            if key in original_scope:
                scope[key] = deepcopy(original_scope[key])
            elif key in _EMIT_SCOPE_FURNITURE or key in {"extra", "config", "groups"}:
                del scope[key]
    return pinned


def guard_exit_ui(
    original_ui: Mapping[str, Any],
    candidate_ui: Mapping[str, Any],
    ops: Sequence[EditOp] = (),
) -> ExitGuardResult:
    """Refuse emit candidates that change UI outside the accepted Δ."""
    attribution = _attribution(ops)
    diagnostics: list[PortIssue] = []
    original_scopes = dict(_iter_scopes(original_ui))
    candidate_scopes = dict(_iter_scopes(candidate_ui))

    for scope_path, original_scope in original_scopes.items():
        candidate_scope = candidate_scopes.get(scope_path)
        if candidate_scope is None:
            diagnostics.append(
                _issue(
                    "full_ui_scope_removed",
                    "Candidate removed a UI scope without an attributed operation.",
                    detail={"scope_path": scope_path},
                )
            )
            continue
        ignored = {"nodes", "links", "definitions"}
        keys = (set(original_scope) | set(candidate_scope)) - ignored
        allowed_scope_paths = attribution["scope_field_paths"].get(scope_path, set())
        for key in sorted(keys):
            if key == "last_node_id":
                diagnostics.extend(_guard_counter(scope_path, key, original_scope.get(key), candidate_scope.get(key)))
                continue
            if key == "last_link_id":
                diagnostics.extend(_guard_counter(scope_path, key, original_scope.get(key), candidate_scope.get(key)))
                continue
            if key == "state":
                diagnostics.extend(_guard_subgraph_state(scope_path, original_scope.get(key), candidate_scope.get(key)))
                continue
            if key in _EMIT_SCOPE_FURNITURE or (
                key == "groups" and not original_scope.get("groups")
            ):
                continue
            if key == "groups":
                diffs = _value_diff_paths(original_scope.get(key), candidate_scope.get(key), "groups")
                if not diffs or _all_diffs_op_allowed(diffs, allowed_scope_paths):
                    continue
            if original_scope.get(key) != candidate_scope.get(key):
                diagnostics.append(
                    _issue(
                        "full_ui_scope_field_changed_unattributed",
                        "Candidate changed a scope-level UI field without an attributed operation.",
                        detail={"scope_path": scope_path, "field": key},
                    )
                )

        original_order = [
            uid for uid in _scope_node_uids(original_scope)
            if (scope_path, uid) not in attribution["removed_nodes"]
        ]
        candidate_order = [
            uid for uid in _scope_node_uids(candidate_scope)
            if (scope_path, uid) not in attribution["new_nodes"]
        ]
        if original_order != candidate_order:
            diagnostics.append(
                _issue(
                    "full_ui_node_order_changed_unattributed",
                    "Candidate changed the relative order of existing nodes without an attributed operation.",
                    detail={"scope_path": scope_path, "original": original_order, "candidate": candidate_order},
                )
            )

        original_links = {
            _link_id(link): link
            for link in (original_scope.get("links") or [])
            if _link_id(link) is not None
        }
        candidate_links = {
            _link_id(link): link
            for link in (candidate_scope.get("links") or [])
            if _link_id(link) is not None
        }
        scope_has_link_ops = scope_path in attribution["link_ops"]
        for link_id, original_link in original_links.items():
            if link_id not in candidate_links:
                if scope_has_link_ops:
                    continue
                diagnostics.append(
                    _issue(
                        "full_ui_link_removed_unattributed",
                        "Candidate removed a link without an attributed operation.",
                        detail={"scope_path": scope_path, "link_id": link_id},
                    )
                )
                continue
            if candidate_links[link_id] == original_link:
                continue
            if scope_has_link_ops:
                continue
            diagnostics.append(
                _issue(
                    "full_ui_link_changed_unattributed",
                    "Candidate changed a link without an attributed operation.",
                    detail={"scope_path": scope_path, "link_id": link_id},
                )
            )
        for link_id in candidate_links:
            if link_id in original_links:
                continue
            if scope_has_link_ops:
                continue
            diagnostics.append(
                _issue(
                    "full_ui_link_added_unattributed",
                    "Candidate added a link without an attributed operation.",
                    detail={"scope_path": scope_path, "link_id": link_id},
                )
            )

    for scope_path in candidate_scopes:
        if scope_path not in original_scopes:
            diagnostics.append(
                _issue(
                    "full_ui_scope_added",
                    "Candidate added a UI scope without an attributed operation.",
                    detail={"scope_path": scope_path},
                )
            )

    original_nodes = _index_nodes(original_ui)
    candidate_nodes = _index_nodes(candidate_ui)
    for key, original_node in original_nodes.items():
        scope_path, uid = key
        candidate_node = candidate_nodes.get(key)
        if candidate_node is None:
            if key in attribution["removed_nodes"]:
                continue
            diagnostics.append(
                _issue(
                    "full_ui_node_removed_unattributed",
                    "Candidate removed an out-of-delta node.",
                    detail={"scope_path": scope_path, "uid": uid},
                )
            )
            continue
        if candidate_node == original_node:
            continue
        diffs = [
            path
            for path in _value_diff_paths(original_node, candidate_node)
            if not _is_emit_furniture_path(path)
        ]
        if not diffs:
            continue
        allowed_paths = attribution["node_paths"].get(key, set())
        if _all_diffs_op_allowed(diffs, allowed_paths):
            continue
        diagnostics.append(
            _issue(
                "full_ui_node_changed_unattributed",
                "Candidate changed an out-of-delta node.",
                detail={"scope_path": scope_path, "uid": uid, "field_paths": diffs[:20]},
            )
        )

    for key in candidate_nodes:
        if key in original_nodes:
            continue
        if key in attribution["new_nodes"]:
            continue
        diagnostics.append(
            _issue(
                "full_ui_node_added_unattributed",
                "Candidate added a node without an attributed add_node operation.",
                detail={"scope_path": key[0], "uid": key[1]},
            )
        )

    return ExitGuardResult(
        ok=not any(issue.severity == "error" for issue in diagnostics),
        diagnostics=tuple(diagnostics),
    )



