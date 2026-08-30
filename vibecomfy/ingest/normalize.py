from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
from typing import Any, Mapping

# Door-owned LiteGraph accessors.  Defined before other vibecomfy
# imports so identity/aliases can import them without cycling.
_DOOR_MISSING = object()


def door_get_nodes(graph: Any, default: Any = None) -> Any:
    getter = getattr(graph, "get", None)
    if callable(getter):
        return getter("nodes", default)
    return default


def door_nodes(graph: Any) -> Any:
    return graph["nodes"]


def door_pop_nodes(graph: Any, default: Any = _DOOR_MISSING) -> Any:
    if default is _DOOR_MISSING:
        return graph.pop("nodes")
    return graph.pop("nodes", default)


def door_setdefault_nodes(graph: Any, default: Any = None) -> Any:
    return graph.setdefault("nodes", default)


def door_get_links(graph: Any, default: Any = None) -> Any:
    getter = getattr(graph, "get", None)
    if callable(getter):
        return getter("links", default)
    return default


def door_links(graph: Any) -> Any:
    return graph["links"]


def door_pop_links(graph: Any, default: Any = _DOOR_MISSING) -> Any:
    if default is _DOOR_MISSING:
        return graph.pop("links")
    return graph.pop("links", default)


def door_setdefault_links(graph: Any, default: Any = None) -> Any:
    return graph.setdefault("links", default)


def door_get_widgets_values(node: Any, default: Any = None) -> Any:
    getter = getattr(node, "get", None)
    if callable(getter):
        return getter("widgets_values", default)
    return default


def door_widgets_values(node: Any) -> Any:
    return node["widgets_values"]


def door_pop_widgets_values(node: Any, default: Any = _DOOR_MISSING) -> Any:
    if default is _DOOR_MISSING:
        return node.pop("widgets_values")
    return node.pop("widgets_values", default)


def door_setdefault_widgets_values(node: Any, default: Any = None) -> Any:
    return node.setdefault("widgets_values", default)


import warnings

from vibecomfy._compile._graph import is_canonical_api_link
from vibecomfy.comfy_backend import check_comfy_compatibility, require_comfy_compatibility
# vibecomfy.exec class type: mirrored as a literal to avoid a module-level import of
# vibecomfy.comfy_nodes.exec_node, which would re-execute comfy_nodes/__init__ (route
# registration side-effect) at boot and pull torch eagerly. Mirrors
# vibecomfy.comfy_nodes.exec_node.EXEC_CLASS_TYPE (see agent_session.py for the same pattern).
EXEC_CLASS_TYPE = "vibecomfy.exec"
from vibecomfy.metadata import (
    OUTPUT_NODE_NAMES,
    _infer_requirements,
    _register_common_inputs,
)
from vibecomfy.identity.uid import make_uid, mint_local_uid
from vibecomfy.porting.widgets.aliases import widget_names_for_class, widget_names_from_schema
from vibecomfy.schema import OutputSpec, SchemaProvider, schema_for
from vibecomfy.security.gate import untrusted_scope
from vibecomfy.security.provenance import PROVENANCE_KEY
from vibecomfy.workflow import (
    NodeMode,
    RawWidgetPayload,
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    VibeWorkflow,
    WorkflowRequirements,
    WorkflowSource,
    _embedded_api_link_details,
    _embedded_api_link_message,
    _graph_integrity_issues,
    litegraph_to_mode,
    mode_to_litegraph,
)

EXEC_SOURCE_MAX_BYTES = 48 * 1024
EXEC_SOURCE_MAX_TOTAL_BYTES = 768 * 1024

# Door-owned wire-retention key (Law 1: ``emit_ui(from_ui(J)) == J``).  The
# ingest boundary stashes the raw top-level fields and raw node payloads under
# this ``workflow.metadata`` key so the emit boundary can reproduce the
# original bytes for an UNTOUCHED graph.  The blob is door-owned wire data —
# per plan.md π_edit, positions/sizes/groups/opaque ``_ui``/wire metadata are
# excluded from the editable quotient and belong to the door law.  Only the
# door boundary (``ingest/normalize.py`` and ``porting/emit/ui.py``) reads or
# writes it; ``VibeWorkflow.to_envelope`` delegates the untouched-graph
# restore decision to this module rather than touching the blob itself.
_UI_DOOR_KEY = "_ui_door"

def _door_freeze(value: Any) -> Any:
    """Deterministic freeze of an editable IR value for the door fingerprint.

    Dicts/lists/tuples/sets are normalized to sorted tuples so the same
    logical value always fingerprints identically regardless of insertion
    order; ``RawWidgetPayload`` is reduced to its five payload fields.
    """
    if isinstance(value, RawWidgetPayload):
        return (
            "raw_widgets",
            _door_freeze(value.values),
            str(value.shape),
            str(value.source),
            bool(value.has_dict_rows),
            int(value.length),
        )
    if isinstance(value, dict):
        return tuple(sorted((str(key), _door_freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_door_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_door_freeze(item) for item in value))
    return value


def _door_signature_ports(entries: Any) -> tuple[Any, ...]:
    ports: list[tuple[Any, ...]] = []
    if not isinstance(entries, (list, tuple)):
        return ()
    for item in entries:
        if not isinstance(item, Mapping):
            continue
        ports.append(
            (
                str(item.get("name") or ""),
                item.get("type"),
                str(item.get("label") or ""),
            )
        )
    return tuple(ports)


def _door_definitions_fingerprint(workflow: "VibeWorkflow") -> tuple[Any, ...]:
    """Editable subgraph signatures for the door fingerprint.

    Covers id, name, and each port's name/type/label.  Inner nodes, links,
    and geometry stay door-owned and are not fingerprinted.
    """
    metadata = getattr(workflow, "metadata", None)
    if not isinstance(metadata, Mapping):
        return ()
    definitions = metadata.get("definitions")
    if not isinstance(definitions, Mapping):
        return ()
    subgraphs = definitions.get("subgraphs")
    if not isinstance(subgraphs, (list, tuple)):
        return ()
    return tuple(
        sorted(
            (
                str(entry.get("id") or entry.get("name") or ""),
                str(entry.get("name") or ""),
                _door_signature_ports(entry.get("inputs")),
                _door_signature_ports(entry.get("outputs")),
            )
            for entry in subgraphs
            if isinstance(entry, Mapping)
        )
    )


def _door_schema_status(metadata: Mapping[str, Any]) -> str:
    """Schema status derived from the IR-only ``schema_source`` metadata.

    Mirrors the pi_edit classification (known/provisional/unknown) but is
    computed WITHOUT a schema provider, so ingest and emit agree on the same
    IR.  Nodes ingested without a provider carry no ``schema_source`` and
    fingerprint as ``unknown``.
    """
    source = metadata.get("schema_source")
    if not isinstance(source, Mapping):
        return "unknown"
    provider = str(source.get("provider", "") or "")
    if provider in ("comfy_registry_provisional", "workflow_json_provisional"):
        return "provisional"
    return "known" if provider else "unknown"


def _door_node_fingerprint(workflow: "VibeWorkflow") -> tuple[Any, ...]:
    """Canonical fingerprint of the editable IR surface for the door law.

    Stored in the door blob at ingest and recomputed at emit.  Equal
    fingerprints prove the graph is UNTOUCHED since ingest, so the emit
    boundary may pass the captured raw wire bytes through unchanged.  The
    fingerprint covers the full editable quotient: every semantic edit through
    ANY path (``set_prompt``/``set_input``/``set_seed``, ``confirm_node``,
    direct input/widget/metadata/raw_widgets mutation) changes at least one
    component, so an edited graph is never byte-passthrough with the edit
    silently discarded.

    Inputs and widgets are fingerprinted as SEPARATE channels: a ``set_input``
    on a widget-backed field is a real edit even when the same field name
    exists in both channels.  ``node.metadata`` (which carries provenance and
    the schema source) is included in full — over-refusal on furniture-only
    metadata churn is conservative and acceptable, while the wire bytes
    themselves (pos/size/order/opaque ``_ui`` values) are still preserved
    verbatim for untouched graphs by the door restore.
    """
    nodes = tuple(
        (
            str(node_id),
            str(node.class_type),
            str(node.uid),
            mode_to_litegraph(node.mode),
            str(node.pack) if node.pack is not None else None,
            tuple(
                sorted(
                    (str(key), _door_freeze(value))
                    for key, value in node.inputs.items()
                )
            ),
            tuple(
                sorted(
                    (str(key), _door_freeze(value))
                    for key, value in node.widgets.items()
                )
            ),
            tuple(
                sorted(
                    (str(key), _door_freeze(value))
                    for key, value in node.metadata.items()
                )
            ),
            _door_freeze(node.raw_widgets),
            str(node.provenance),
            _door_schema_status(node.metadata),
        )
        for node_id, node in sorted(
            workflow.nodes.items(),
            key=lambda kv: (int(kv[0]) if kv[0].isdigit() else (1 << 30), kv[0]),
        )
    )
    edges = tuple(
        (str(e.from_node), str(e.from_output), str(e.to_node), str(e.to_input))
        for e in workflow.edges
    )
    public_inputs = tuple(
        sorted(
            (
                str(name),
                str(item.node_id),
                str(item.field),
                _door_freeze(item.value),
                str(item.type) if item.type is not None else None,
                _door_freeze(item.default),
                bool(item.required),
                _door_freeze(item.range),
                tuple(str(alias) for alias in item.aliases),
                str(item.media_semantics) if item.media_semantics is not None else None,
            )
            for name, item in workflow.inputs.items()
        )
    )
    public_outputs = tuple(
        sorted(
            (str(item.node_id), str(item.output_type), str(item.name))
            for item in workflow.outputs
        )
    )
    # Grammar-visible subgraph signatures (id, name, ports).  A
    # definitions-only edit that changes an emitted port (e.g. a subgraph
    # input label that becomes the Python kwarg) must flip this fingerprint
    # so the emit door cannot restore the captured original and discard it.
    # Inner bodies / furniture stay door-owned and are not fingerprinted.
    return (nodes, edges, public_inputs, public_outputs, _door_definitions_fingerprint(workflow))


def _capture_ui_door(
    raw: dict[str, Any],
    workflow: "VibeWorkflow",
    *,
    use_comfy_converter: bool = False,
) -> dict[str, Any]:
    """Capture the raw wire bytes at the ingest boundary (Law 1).

    ``top`` holds every top-level field verbatim (including opaque keys) except
    the ``nodes`` payload itself; ``nodes`` holds the raw per-node payloads
    keyed by string id; ``node_order`` preserves the raw node list order;
    ``top_order`` preserves the raw top-level key order (including where
    ``nodes`` sits); ``fingerprint`` freezes the editable IR surface so the
    emit boundary can prove a graph is untouched; ``shape`` records whether the
    raw was a litegraph UI envelope (``"ui"``) or a serialized Vibe envelope
    (``"envelope"``); ``use_comfy_converter`` records the ingest converter
    request so the emit boundary only byte-passes graphs whose IR provably
    derives from the offline normalizer (the comfy-converter ingest path is
    not guaranteed to normalize back to the same API, so it keeps the
    deterministic reconstruction path).
    """
    top = {
        key: deepcopy(value)
        for key, value in raw.items()
        if key != "nodes" and key != _UI_DOOR_KEY
    }
    nodes_raw = raw.get("nodes")
    node_payloads: dict[str, Any] = {}
    node_order: list[str] = []
    if isinstance(nodes_raw, list):
        for entry in nodes_raw:
            if not isinstance(entry, dict) or "id" not in entry:
                continue
            nid = str(entry["id"])
            node_payloads[nid] = deepcopy(entry)
            node_order.append(nid)
    elif isinstance(nodes_raw, dict):
        for key, entry in nodes_raw.items():
            if isinstance(entry, dict):
                node_payloads[str(key)] = deepcopy(entry)
                node_order.append(str(key))
    return {
        "top": top,
        "top_order": list(raw.keys()),
        "nodes": node_payloads,
        "node_order": node_order,
        "fingerprint": _door_node_fingerprint(workflow),
        "shape": "ui" if isinstance(nodes_raw, list) else "envelope",
        "use_comfy_converter": use_comfy_converter,
    }


def _restore_untouched_door(door: Mapping[str, Any]) -> dict[str, Any]:
    """Rebuild the original ingest bytes from the door blob (Law 1).

    Preserves the raw top-level key order (``top_order``), the raw top-level
    fields, and the raw node payloads in raw order.  The result is a detached
    deep copy — mutating it never touches the IR or the blob.  The door key
    itself is never wire data: a stale blob that captured it is stripped.
    """
    top = door.get("top")
    nodes_raw = door.get("nodes")
    order = door.get("node_order") or []
    if not isinstance(top, Mapping) or not isinstance(nodes_raw, Mapping):
        raise ValueError("door blob malformed: missing top/nodes")
    if door.get("shape") == "ui":
        nodes: Any = [deepcopy(nodes_raw[nid]) for nid in order if nid in nodes_raw]
    else:
        # Envelope shape: the rich ``nodes`` mapping is the stored wire shape.
        nodes = {nid: deepcopy(nodes_raw[nid]) for nid in order if nid in nodes_raw}
    envelope: dict[str, Any] = {}
    keys = list(door.get("top_order")) if isinstance(door.get("top_order"), list) else list(top)
    nodes_placed = False
    for key in keys:
        if key == "nodes":
            envelope["nodes"] = nodes
            nodes_placed = True
        elif key in top and key != _UI_DOOR_KEY:
            envelope[key] = deepcopy(top[key])
    for key, value in top.items():
        if key not in envelope and key != "nodes" and key != _UI_DOOR_KEY:
            envelope[key] = deepcopy(value)
    if not nodes_placed:
        envelope["nodes"] = nodes
    return envelope


def _restore_untouched_envelope(workflow: "VibeWorkflow") -> dict[str, Any] | None:
    """Door-owned Law-1 restore for the envelope serializer.

    Returns the raw ingest bytes verbatim when the IR is UNTOUCHED since
    ingest (door shape ``envelope`` and fingerprint match), else ``None`` so
    the serializer falls through to the plain IR rendering.  This keeps ALL
    door-blob inspection at the door boundary: ``workflow.py`` never reads the
    blob or compares fingerprints itself.
    """
    metadata = getattr(workflow, "metadata", None)
    door = metadata.get(_UI_DOOR_KEY) if isinstance(metadata, dict) else None
    if (
        isinstance(door, Mapping)
        and door.get("shape") == "envelope"
        and _door_node_fingerprint(workflow) == door.get("fingerprint")
    ):
        return _restore_untouched_door(door)
    return None


def detect_workflow_shape(raw: dict[str, Any]) -> str:
    """Private dispatcher helper. Not part of the public ingest API.

    Callers that know their input should use :func:`from_envelope`,
    :func:`from_ui`, or :func:`from_api`. This remains for
    :func:`normalize_to_api` and a few internal tags that still need a shape
    label. ``{prompt: API}`` is detected as ``prompt_api`` once; the wrapper
    is retained as sidecar by :func:`ingest_workflow_and_ui`.
    """
    if "prompt" in raw and isinstance(raw["prompt"], dict):
        inner = detect_workflow_shape(raw["prompt"])
        if inner == "api":
            return "prompt_api"
        return inner
    # ``compiled_api`` is optional execution evidence.  A versioned rich
    # envelope remains a Vibe envelope even when that evidence is absent or
    # malformed; structural shape is established by the rich nodes mapping.
    if isinstance(raw.get("nodes"), dict) and (
        "vibecomfy_format_version" in raw
        or isinstance(raw.get("compiled_api"), dict)
    ):
        return "vibe"
    if isinstance(raw.get("nodes"), list):
        return "ui"
    if raw == {}:
        return "api"
    if raw and all(isinstance(value, dict) and "class_type" in value for value in raw.values()):
        return "api"
    return "unknown"


def _attach_workflow_snapshot(
    workflow: "VibeWorkflow",
    raw: Mapping[str, Any] | None,
    *,
    source_representation: str,
) -> "VibeWorkflow":
    """Freeze a copy/handle of *workflow* as the retained ingest authority."""
    from vibecomfy.ingest.snapshot import (
        WORKFLOW_SNAPSHOT_METADATA_KEY,
        capture_workflow_snapshot,
    )

    workflow.metadata[WORKFLOW_SNAPSHOT_METADATA_KEY] = capture_workflow_snapshot(
        raw,
        workflow,
        source_representation=source_representation,
    )
    return workflow


def _ingest_unknown_shape(raw: Mapping[str, Any]) -> "VibeWorkflow":
    """Unknown shape stays unknown and fails closed."""
    raise ValueError("unsupported workflow shape for ingest: unknown")


def normalize_to_api(
    raw: dict[str, Any],
    *,
    schema_provider: SchemaProvider | None = None,
    use_comfy_converter: bool = True,
    comfy_converter_strict: bool = True,
) -> dict[str, Any]:
    """Convert a raw workflow dict (UI or API shape) to ComfyUI API format.

    By default this prefers the live ComfyUI converter and raises if
    ``convert_ui_to_api`` fails. Pass ``comfy_converter_strict=False`` to keep the
    legacy lenient fallback path when the converter is importable but errors. Pass
    ``use_comfy_converter=False`` for explicit offline normalization that never
    imports or calls the ComfyUI converter; in that mode
    ``comfy_converter_strict`` is ignored.
    """
    shape = detect_workflow_shape(raw)
    if shape == "api":
        api = raw.get("prompt", raw)
        _enforce_exec_source_limits(api, surface="api")
        return api
    if shape == "vibe":
        # The rich envelope (nodes mapping + edges list) is the only structural
        # authority. ``compiled_api`` is stale execution evidence and must never
        # decide which rich nodes exist — the API view is derived by decoding
        # the envelope into a VibeWorkflow and compiling it fresh.
        workflow = VibeWorkflow.from_envelope(raw)
        api = workflow.compile("api")
        _merge_vibe_node_widget_evidence(raw, api)
        _enforce_exec_source_limits(api, surface="vibe.compiled_api")
        return api
    if shape != "ui":
        raise ValueError(f"Unsupported workflow shape: {shape}")
    return _ui_graph_to_api(
        raw,
        schema_provider=schema_provider,
        use_comfy_converter=use_comfy_converter,
        comfy_converter_strict=comfy_converter_strict,
    )


def _ui_graph_to_api(
    raw: dict[str, Any],
    *,
    schema_provider: SchemaProvider | None = None,
    use_comfy_converter: bool = True,
    comfy_converter_strict: bool = True,
) -> dict[str, Any]:
    """LiteGraph list-nodes → Comfy prompt dict. Does not sniff shape."""
    if use_comfy_converter:
        try:
            from comfy.component_model.workflow_convert import convert_ui_to_api
        except ImportError:
            pass
        else:
            compatibility = check_comfy_compatibility()
            if not compatibility.ok:
                if comfy_converter_strict:
                    require_comfy_compatibility(compatibility)
                warnings.warn(
                    "normalize_to_api(): live ComfyUI compatibility check failed "
                    f"({compatibility.reason_code}); falling back to the offline "
                    "normalizer because comfy_converter_strict=False.",
                    stacklevel=3,
                )
                return _normalize_ui_to_api(raw, schema_provider=schema_provider)
            try:
                converted = convert_ui_to_api(raw)
            except Exception:
                if comfy_converter_strict:
                    raise
                warnings.warn(
                    "normalize_to_api(): ComfyUI convert_ui_to_api raised; "
                    "falling back to the offline normalizer because "
                    "comfy_converter_strict=False.",
                    stacklevel=3,
                )
            else:
                _enforce_exec_source_limits(converted, surface="ui.converter")
                if not _has_unknown_widget_inputs(converted):
                    _merge_slim_ui(raw, converted)
                    return converted
                return _normalize_ui_to_api(raw, schema_provider=schema_provider)

    return _normalize_ui_to_api(raw, schema_provider=schema_provider)


def _unique_input_name(used: set[str], name: str) -> str:
    """Return a dict key that does not collide with an earlier socket.

    Duplicate LiteGraph input names (ImageScale ``width`` x2, CutAndDragOnPath
    ``coordinates`` x2) must not overwrite each other in the API/IR dict.
    The first keeps its name; later copies become ``name_1``, ``name_2``, …
    """
    if name not in used:
        used.add(name)
        return name
    index = 1
    while f"{name}_{index}" in used:
        index += 1
    unique = f"{name}_{index}"
    used.add(unique)
    return unique


def _normalize_ui_to_api(raw: dict[str, Any], *, schema_provider: SchemaProvider | None = None) -> dict[str, Any]:
    nodes = {str(node["id"]): node for node in raw.get("nodes", []) if isinstance(node, dict) and "id" in node}
    links = raw.get("links", [])
    link_map: dict[int, tuple[str, int]] = {}
    for link in links:
        if isinstance(link, list) and len(link) >= 4:
            link_map[int(link[0])] = (str(link[1]), int(link[2]))
        elif isinstance(link, dict) and {"id", "origin_id", "origin_slot"} <= set(link):
            link_map[int(link["id"])] = (str(link["origin_id"]), int(link["origin_slot"]))

    api: dict[str, Any] = {}
    for node_id, node in nodes.items():
        inputs: dict[str, Any] = {}
        input_provenance: dict[str, str] = {}
        class_type = str(node.get("type") or node.get("class_type") or "Unknown")
        ui_widget_names: list[str] = []
        used_names: set[str] = set()
        for input_item in node.get("inputs", []) or []:
            if not isinstance(input_item, dict):
                continue
            name = input_item.get("name")
            link_id = input_item.get("link")
            widget = input_item.get("widget")
            if link_id is None and isinstance(name, str) and isinstance(widget, dict):
                ui_widget_names.append(str(widget.get("name") or name))
            if link_id is not None and link_id in link_map:
                if not name:
                    # Reroute / passthrough nodes may have empty-string input
                    # names — use a stable generated key to preserve the edge.
                    name = f"_un{link_id}"
                name = _unique_input_name(used_names, str(name))
                inputs[name] = [link_map[link_id][0], link_map[link_id][1]]
                input_provenance[str(name)] = "edge"
        widgets_present = "widgets_values" in node
        widgets = node.get("widgets_values", [])
        if isinstance(widgets, dict):
            for name, value in widgets.items():
                if name in inputs:
                    continue
                inputs[str(name)] = value
                input_provenance[str(name)] = "widget"
        elif isinstance(widgets, list):
            widget_names = _schema_input_names(schema_provider, class_type)
            for idx, value in enumerate(widgets):
                if idx < len(widget_names):
                    name = _normalize_widget_input_name(widget_names, idx, value)
                elif idx < len(ui_widget_names):
                    name = ui_widget_names[idx]
                else:
                    name = f"widget_{idx}"
                if name in inputs:
                    continue
                name = _unique_input_name(used_names, str(name))
                inputs[name] = value
                input_provenance[str(name)] = "widget"
        api_node = {
            "class_type": class_type,
            "inputs": inputs,
            "_ui": node,
            "_input_provenance": input_provenance,
        }
        if widgets_present:
            api_node["_raw_widgets"] = _raw_widget_payload_dict(widgets, source="ui.widgets_values")
        api[node_id] = api_node
    _enforce_exec_source_limits(api, surface="ui.offline")
    return api


def _raw_widget_payload_dict(values: Any, *, source: str) -> dict[str, Any]:
    if values is None:
        shape = "none"
        length = 0
    elif isinstance(values, dict):
        shape = "dict"
        length = len(values)
    elif isinstance(values, list):
        shape = "list"
        length = len(values)
    else:
        shape = "scalar"
        length = 1
    has_dict_rows = isinstance(values, dict) or (
        isinstance(values, list) and any(isinstance(item, dict) for item in values)
    )
    return {
        "values": deepcopy(values),
        "shape": shape,
        "source": source,
        "has_dict_rows": has_dict_rows,
        "length": length,
    }


def _merge_vibe_node_widget_evidence(raw: dict[str, Any], api: dict[str, Any]) -> None:
    """Carry rich Vibe node widget evidence into the compiled API graph.

    The rich ``nodes`` map is the sole structural authority of a serialized
    Vibe workflow; the executable API view is derived by compiling the IR
    (``compile("api")``), never read from stored data.  Widget-shape recovery
    needs the observed LiteGraph widget vector from the rich ``nodes`` map.
    """
    nodes = raw.get("nodes")
    if not isinstance(nodes, dict):
        return
    for node_id, rich_node in nodes.items():
        if not isinstance(rich_node, dict):
            continue
        api_node = api.get(str(node_id))
        if not isinstance(api_node, dict):
            continue
        raw_widgets = rich_node.get("raw_widgets") or rich_node.get("_raw_widgets")
        if isinstance(raw_widgets, dict):
            api_node.setdefault("_raw_widgets", deepcopy(raw_widgets))
        metadata = rich_node.get("metadata")
        raw_ui = metadata.get("_ui") if isinstance(metadata, dict) else rich_node.get("_ui")
        if (
            isinstance(raw_widgets, dict)
            and bool(raw_widgets.get("has_dict_rows"))
            and isinstance(raw_ui, dict)
            and "widgets_values" in raw_ui
        ):
            api_node.setdefault("_ui", deepcopy(raw_ui))
        if "_raw_widgets" in api_node:
            continue
        if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
            api_node["_raw_widgets"] = _raw_widget_payload_dict(
                raw_ui["widgets_values"],
                source="ui.widgets_values",
            )


def _coerce_raw_widget_payload(raw: Any) -> RawWidgetPayload | None:
    if isinstance(raw, RawWidgetPayload):
        return raw
    if not isinstance(raw, dict):
        return None
    if not {"values", "shape", "source", "has_dict_rows", "length"} <= set(raw):
        return None
    return RawWidgetPayload(
        values=deepcopy(raw["values"]),
        shape=str(raw["shape"]),
        source=str(raw["source"]),
        has_dict_rows=bool(raw["has_dict_rows"]),
        length=int(raw["length"]),
    )


def _merge_slim_ui(raw: dict[str, Any], converted: dict[str, Any]) -> None:
    """Merge slim _ui {id, pos, size, properties} from raw litegraph nodes onto converted API nodes.

    Called after convert_ui_to_api so pos/properties survive on the comfy-converter path.
    Verifies id preservation: if converted keys diverge from raw node ids, falls back to
    class_type+position matching and emits a warning (correctness-2 gate).
    """
    raw_nodes_by_id: dict[str, dict] = {
        str(node["id"]): node
        for node in raw.get("nodes", [])
        if isinstance(node, dict) and "id" in node
    }
    raw_ids = set(raw_nodes_by_id.keys())
    converted_ids = set(converted.keys())
    ids_diverge = bool(converted_ids - raw_ids)

    if ids_diverge:
        warnings.warn(
            "convert_ui_to_api produced node ids not present in raw litegraph nodes; "
            "falling back to class_type+order matching for _ui merge (correctness-2).",
            stacklevel=4,
        )
        # Build a lookup by (class_type, order_index) as a best-effort fallback
        raw_by_class_order: dict[tuple[str, int], dict] = {}
        for node in raw.get("nodes", []):
            if not isinstance(node, dict):
                continue
            class_type = str(node.get("type", ""))
            order = int(node.get("order", -1))
            raw_by_class_order[(class_type, order)] = node

        for node_id, node_data in converted.items():
            if not isinstance(node_data, dict) or "_ui" in node_data:
                continue
            class_type = str(node_data.get("class_type", ""))
            # Try to find a match; use first class_type match as a last resort
            matched = None
            for (ct, _order), raw_node in raw_by_class_order.items():
                if ct == class_type:
                    matched = raw_node
                    break
            if matched is not None:
                slim: dict = {
                    "id": matched.get("id"),
                    "pos": matched.get("pos"),
                    "size": matched.get("size"),
                    "properties": matched.get("properties", {}),
                }
                if "widgets_values" in matched:
                    slim["widgets_values"] = deepcopy(matched["widgets_values"])
                    node_data.setdefault(
                        "_raw_widgets",
                        _raw_widget_payload_dict(matched["widgets_values"], source="ui.widgets_values"),
                    )
                for _f in ("mode", "flags", "color", "bgcolor"):
                    if _f in matched:
                        slim[_f] = matched[_f]
                node_data["_ui"] = slim
            else:
                node_data["_ui"] = {}
    else:
        for node_id, node_data in converted.items():
            if not isinstance(node_data, dict) or "_ui" in node_data:
                continue
            raw_node = raw_nodes_by_id.get(node_id)
            if raw_node is not None:
                slim = {
                    "id": raw_node.get("id"),
                    "pos": raw_node.get("pos"),
                    "size": raw_node.get("size"),
                    "properties": raw_node.get("properties", {}),
                }
                if "widgets_values" in raw_node:
                    slim["widgets_values"] = deepcopy(raw_node["widgets_values"])
                    node_data.setdefault(
                        "_raw_widgets",
                        _raw_widget_payload_dict(raw_node["widgets_values"], source="ui.widgets_values"),
                    )
                for _f in ("mode", "flags", "color", "bgcolor"):
                    if _f in raw_node:
                        slim[_f] = raw_node[_f]
                node_data["_ui"] = slim
            else:
                node_data["_ui"] = {}


def _has_unknown_widget_inputs(api: dict[str, Any]) -> bool:
    for node in api.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if isinstance(inputs, dict) and "UNKNOWN" in inputs:
            return True
    return False


def _vibe_string_list(value: Any, label: str) -> list[str]:
    """Decode a serialized requirements list field: ``None`` → ``[]``, else a list of strings."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"serialized vibe envelope {label} must be a list of strings")
    return list(value)


def _vibe_groups(value: Any) -> list[dict[str, Any]]:
    """Decode the serialized graph-level ``groups`` field: ``None`` → ``[]``.

    Fail-closed like the rest of the envelope decoder: when present, ``groups``
    must be a list of group objects (LiteGraph ``{title, bounding, ...}``
    dicts).  Old envelopes without the key decode to an empty list.
    """
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("serialized vibe envelope 'groups' must be a list of group objects")
    return deepcopy(value)


def _node_mode_from_metadata(metadata: dict[str, Any]) -> NodeMode:
    """First-class mode value for a node: ``_ui.mode`` then legacy
    ``metadata[\"mode\"]``, else ENABLED.  Only ints are accepted from the
    raw substrate; the IR stores the semantic :class:`NodeMode`."""
    ui = metadata.get("_ui")
    if isinstance(ui, dict):
        ui_mode = ui.get("mode", 0)
        if isinstance(ui_mode, int):
            return litegraph_to_mode(ui_mode)
    meta_mode = metadata.get("mode")
    if isinstance(meta_mode, int):
        return litegraph_to_mode(meta_mode)
    if isinstance(meta_mode, str):
        try:
            return NodeMode(meta_mode)
        except ValueError:
            return NodeMode.ENABLED
    return NodeMode.ENABLED


def _decode_envelope_node_mode(
    entry: dict[str, Any], metadata: dict[str, Any]
) -> NodeMode | int:
    """Restore first-class envelope ``mode``; consult furniture only if absent.

    Integer wire values are preserved so corpus envelopes keep ``mode == 4``.
    Semantic :class:`NodeMode` values from ``to_envelope``'s dataclass walk,
    and their JSON strings (``"bypassed"``), are restored via
    :func:`litegraph_to_mode` and stay authoritative over stale ``_ui.mode``.
    """
    entry_mode = entry.get("mode")
    if isinstance(entry_mode, int):
        return entry_mode
    if entry_mode is not None:
        return litegraph_to_mode(entry_mode)
    return _node_mode_from_metadata(metadata)


def _geometry_pair(value: Any) -> list[float] | None:
    """Return a detached finite numeric pair, or ``None`` when invalid/absent.

    Real lists/tuples must be EXACTLY two finite numeric coordinates — a
    three-element list is malformed, not truncatable. The legacy
    objectified-array form some LiteGraph exports produce is accepted: a dict
    keyed by string indices (``{"0": x, "1": y}``; ``pos`` may carry a
    trailing ``"2"`` z element, which is dropped). Anything else (booleans,
    non-finite, non-numeric, wrong arity) is treated as absent rather than
    guessed.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        try:
            ordered = [value[str(i)] for i in range(len(value))]
        except (KeyError, ValueError):
            return None
        if len(ordered) < 2:
            return None
        value = ordered[:2]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) for coord in value):
        return None
    try:
        pair = [float(value[0]), float(value[1])]
    except (OverflowError, TypeError, ValueError):
        return None
    return pair if all(math.isfinite(coord) for coord in pair) else None


def _decode_envelope_geometry(
    entry: dict[str, Any], metadata: dict[str, Any], field_name: str, node_id: str
) -> list[float] | None:
    """Decode strict first-class geometry with an independent legacy ``_ui`` fallback."""
    if field_name in entry:
        node_value = entry[field_name]
        if node_value is None:
            return None
        pair = _geometry_pair(node_value)
        if pair is None:
            raise ValueError(
                f"node {node_id!r}: {field_name} must contain exactly two finite numeric coordinates or null"
            )
        return pair

    ui = metadata.get("_ui")
    legacy_value = ui.get(field_name) if isinstance(ui, dict) else None
    if legacy_value is None:
        return None
    pair = _geometry_pair(legacy_value)
    if pair is None:
        raise ValueError(
            f"node {node_id!r}: legacy _ui.{field_name} must contain exactly two finite numeric coordinates or null"
        )
    return pair


def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
    """Implementation of :meth:`VibeWorkflow.from_envelope`.

    Do not call this from new code — use ``VibeWorkflow.from_envelope`` (or
    the module-level ``from_envelope``).  The decoder is fail-closed and
    unrelaxed: the rich top-level ``nodes`` mapping and ``edges`` list are
    the ONLY structural authority; ``compiled_api`` is never consulted for
    which nodes exist.  Any malformed or mixed entry raises ``ValueError``
    and no partial graph is ever returned.

    Every field is deep-copied.  Node ``metadata`` is preserved verbatim
    (including ``metadata._ui``) except that ``metadata[PROVENANCE_KEY]`` is
    unconditionally enforced to ``"untrusted_source"`` at this external JSON
    boundary, and stable node ``uid`` values are preserved exactly.
    """
    if not isinstance(raw, dict):
        raise ValueError("serialized vibe envelope must be a JSON object")

    nodes_raw = raw.get("nodes")
    if not isinstance(nodes_raw, dict):
        raise ValueError("serialized vibe envelope 'nodes' must be a mapping of node objects")
    for key, entry in nodes_raw.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"node {key!r}: node entries must be mappings, got {type(entry).__name__}"
            )

    # ── top-level envelope fields ──────────────────────────────────────────
    source_raw = raw.get("source")
    if not isinstance(source_raw, dict):
        raise ValueError("serialized vibe envelope 'source' must be a mapping")
    source_id = source_raw.get("id")
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError("source.id must be a nonblank string")
    source_path = source_raw.get("path")
    if source_path is not None and not isinstance(source_path, str):
        raise ValueError("source.path must be a string or null")
    source_provenance = source_raw.get("provenance")
    if source_provenance is not None and not isinstance(source_provenance, dict):
        raise ValueError("source.provenance must be a mapping or null")
    source = WorkflowSource(
        id=source_id,
        path=source_path,
        source_type=str(source_raw.get("source_type", "unknown")),
        provenance=deepcopy(source_provenance) if isinstance(source_provenance, dict) else {},
    )

    workflow_id = raw.get("id")
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        workflow_id = source_id

    requirements_raw = raw.get("requirements")
    if not isinstance(requirements_raw, dict):
        raise ValueError("serialized vibe envelope 'requirements' must be a mapping")
    requirements = WorkflowRequirements(
        models=_vibe_string_list(
            requirements_raw.get("models"), "requirements.models"
        ),
        custom_nodes=_vibe_string_list(
            requirements_raw.get("custom_nodes"), "requirements.custom_nodes"
        ),
        missing_models=_vibe_string_list(
            requirements_raw.get("missing_models"), "requirements.missing_models"
        ),
        missing_nodes=_vibe_string_list(
            requirements_raw.get("missing_nodes"), "requirements.missing_nodes"
        ),
        unsupported=_vibe_string_list(
            requirements_raw.get("unsupported"), "requirements.unsupported"
        ),
    )

    metadata_raw = raw.get("metadata")
    if metadata_raw is not None and not isinstance(metadata_raw, dict):
        raise ValueError("serialized vibe envelope 'metadata' must be a mapping or null")

    strict_types = raw.get("strict_types", False)
    if not isinstance(strict_types, bool):
        raise ValueError("strict_types must be a boolean")

    groups = _vibe_groups(raw.get("groups"))

    workflow = VibeWorkflow(
        id=workflow_id,
        source=source,
        requirements=requirements,
        metadata=deepcopy(metadata_raw) if isinstance(metadata_raw, dict) else {},
        strict_types=strict_types,
        groups=groups,
    )

    # ── nodes ──────────────────────────────────────────────────────────────
    for key, entry in nodes_raw.items():
        node_id = entry.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"node {key!r}: id must be a nonblank string")
        class_type = entry.get("class_type")
        if not isinstance(class_type, str) or not class_type.strip():
            raise ValueError(f"node {node_id!r}: class_type must be a nonblank string")
        uid = entry.get("uid")
        if not isinstance(uid, str) or not uid.strip():
            raise ValueError(f"node {node_id!r}: uid must be a nonblank string")
        pack = entry.get("pack")
        if pack is not None and not isinstance(pack, str):
            raise ValueError(f"node {node_id!r}: pack must be a string or null")
        for field_name in ("inputs", "widgets", "metadata"):
            value = entry.get(field_name)
            if not isinstance(value, dict):
                raise ValueError(f"node {node_id!r}: {field_name} must be a mapping")
        raw_widgets = entry.get("raw_widgets")
        raw_widget_payload: RawWidgetPayload | None = None
        if raw_widgets is not None:
            if not isinstance(raw_widgets, dict) or not {
                "values",
                "shape",
                "source",
                "has_dict_rows",
                "length",
            } <= set(raw_widgets):
                raise ValueError(
                    f"node {node_id!r}: raw_widgets must be a RawWidgetPayload mapping or null"
                )
            length = raw_widgets["length"]
            if not isinstance(length, int) or isinstance(length, bool) or length < 0:
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.length must be a nonnegative integer"
                )
            shape = raw_widgets["shape"]
            source_name = raw_widgets["source"]
            has_dict_rows = raw_widgets["has_dict_rows"]
            if not isinstance(shape, str) or not shape.strip():
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.shape must be a nonblank string"
                )
            if not isinstance(source_name, str) or not source_name.strip():
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.source must be a nonblank string"
                )
            if not isinstance(has_dict_rows, bool):
                raise ValueError(
                    f"node {node_id!r}: raw_widgets.has_dict_rows must be a boolean"
                )
            raw_widget_payload = RawWidgetPayload(
                values=deepcopy(raw_widgets["values"]),
                shape=shape,
                source=source_name,
                has_dict_rows=has_dict_rows,
                length=length,
            )
        node_metadata = deepcopy(entry["metadata"])
        # S4 capability fence: ingest is the external-JSON boundary, so every
        # decoded node is tagged untrusted_source. Unconditional set — never
        # `setdefault` — so hostile JSON cannot pre-declare itself trusted.
        node_metadata[PROVENANCE_KEY] = "untrusted_source"
        # Mode is first-class: prefer the serialized node-level ``mode`` field
        # (written by to_envelope's dataclass walk), falling back to the legacy
        # ``_ui.mode`` / ``metadata["mode"]`` locations for old envelopes.
        # ``_ui`` stays verbatim so the emitter's furniture keeps re-emitting it.
        node_mode = _decode_envelope_node_mode(entry, node_metadata)
        node_pos = _decode_envelope_geometry(entry, node_metadata, "pos", node_id)
        node_size = _decode_envelope_geometry(entry, node_metadata, "size", node_id)
        workflow.nodes[str(key)] = VibeNode(
            id=node_id,
            class_type=class_type,
            pack=pack,
            inputs=deepcopy(entry["inputs"]),
            widgets=deepcopy(entry["widgets"]),
            metadata=node_metadata,
            uid=uid,
            raw_widgets=raw_widget_payload,
            mode=node_mode,
            pos=node_pos,
            size=node_size,
        )

    integrity_issues = _graph_integrity_issues(workflow.nodes, [])
    if integrity_issues:
        raise ValueError(integrity_issues[0].message)

    # ── edges ──────────────────────────────────────────────────────────────
    edges_raw = raw.get("edges")
    if not isinstance(edges_raw, list):
        raise ValueError("serialized vibe envelope 'edges' must be a list")
    for index, edge in enumerate(edges_raw):
        if not isinstance(edge, dict):
            raise ValueError(
                f"edge {index}: edge entries must be mappings, got {type(edge).__name__}"
            )
        for field_name in ("from_node", "from_output", "to_node", "to_input"):
            value = edge.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"edge {index}: {field_name} must be a nonblank string")
        workflow.edges.append(
            VibeEdge(
                from_node=edge["from_node"],
                from_output=edge["from_output"],
                to_node=edge["to_node"],
                to_input=edge["to_input"],
            )
        )

    integrity_issues = _graph_integrity_issues(workflow.nodes, workflow.edges)
    if integrity_issues:
        raise ValueError(integrity_issues[0].message)

    # ── top-level inputs / outputs ─────────────────────────────────────────
    embedded_links = _embedded_api_link_details(workflow)
    if embedded_links:
        raise ValueError(
            "embedded_api_link: "
            + _embedded_api_link_message(
                embedded_links[0], surface="serialized vibe envelope decode"
            )
        )

    inputs_raw = raw.get("inputs")
    if not isinstance(inputs_raw, dict):
        raise ValueError("serialized vibe envelope 'inputs' must be a mapping")
    for name, entry in inputs_raw.items():
        if not isinstance(entry, dict):
            raise ValueError(
                f"input {name!r}: input entries must be mappings, got {type(entry).__name__}"
            )
        input_name = entry.get("name")
        node_id = entry.get("node_id")
        field = entry.get("field")
        if not isinstance(input_name, str) or not input_name.strip():
            raise ValueError(f"input {name!r}: name must be a nonblank string")
        if str(name) != input_name:
            raise ValueError(
                f"input mapping key {name!r} must equal input.name {input_name!r}"
            )
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"input {name!r}: node_id must be a nonblank string")
        if node_id not in workflow.nodes:
            raise ValueError(f"input {name!r}: node_id {node_id!r} must exist in nodes")
        if not isinstance(field, str) or not field.strip():
            raise ValueError(f"input {name!r}: field must be a nonblank string")
        required = entry.get("required", False)
        if not isinstance(required, bool):
            raise ValueError(f"input {name!r}: required must be a boolean")
        aliases = entry.get("aliases", ())
        if not isinstance(aliases, (list, tuple)) or not all(
            isinstance(alias, str) for alias in aliases
        ):
            raise ValueError(f"input {name!r}: aliases must be a list of strings")
        media_semantics = entry.get("media_semantics")
        if media_semantics is not None and not isinstance(media_semantics, str):
            raise ValueError(f"input {name!r}: media_semantics must be a string or null")
        input_type = entry.get("type")
        if input_type is not None and not isinstance(input_type, str):
            raise ValueError(f"input {name!r}: type must be a string or null")
        allow_missing_target = entry.get("allow_missing_target", False)
        if not isinstance(allow_missing_target, bool):
            raise ValueError(f"input {name!r}: allow_missing_target must be a boolean")
        workflow.inputs[str(input_name)] = VibeInput(
            name=str(input_name),
            node_id=str(node_id),
            field=str(field),
            value=deepcopy(entry.get("value")),
            type=input_type,
            default=deepcopy(entry.get("default")),
            required=required,
            range=deepcopy(entry.get("range")),
            aliases=tuple(aliases),
            media_semantics=media_semantics,
            allow_missing_target=allow_missing_target,
        )

    outputs_raw = raw.get("outputs")
    if not isinstance(outputs_raw, list):
        raise ValueError("serialized vibe envelope 'outputs' must be a list")
    for index, entry in enumerate(outputs_raw):
        if not isinstance(entry, dict):
            raise ValueError(
                f"output {index}: output entries must be mappings, got {type(entry).__name__}"
            )
        node_id = entry.get("node_id")
        output_type = entry.get("output_type")
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"output {index}: node_id must be a nonblank string")
        if node_id not in workflow.nodes:
            raise ValueError(
                f"output {index}: node_id {node_id!r} must exist in nodes"
            )
        if not isinstance(output_type, str) or not output_type.strip():
            raise ValueError(f"output {index}: output_type must be a nonblank string")
        for field_name in ("name", "artifact_kind", "mime_type", "filename_prefix"):
            value = entry.get(field_name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"output {index}: {field_name} must be a string or null")
        workflow.outputs.append(
            VibeOutput(
                node_id=node_id,
                output_type=output_type,
                name=entry.get("name"),
                artifact_kind=entry.get("artifact_kind"),
                mime_type=entry.get("mime_type"),
                filename_prefix=entry.get("filename_prefix"),
                expected_cardinality=deepcopy(entry.get("expected_cardinality")),
            )
        )

    # The serialized snapshot is JSON-shaped (tuples became lists) and may have
    # been produced from an older derived execution view. Rehydrate this
    # derived evidence from the just-decoded rich graph so an untouched rich
    # envelope has no synthetic widget/link delta at its first canonical emit.
    # All non-derived workflow metadata remains preserved verbatim.
    from vibecomfy.ingest.snapshot import capture_ingest_snapshot

    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(raw, workflow)
    _attach_workflow_snapshot(workflow, raw, source_representation="vibe")
    # Law 1: stash the raw envelope bytes at the door so the envelope
    # serializer (``to_envelope``) reproduces them byte-for-byte for an
    # untouched envelope (``to_envelope(from_envelope(J)) == J``).
    workflow.metadata[_UI_DOOR_KEY] = _capture_ui_door(raw, workflow)

    return workflow


def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
    """Fail-closed lossless decode of a serialized Vibe envelope.

    The rich ``nodes`` mapping and ``edges`` list are the only structural
    authority. ``compiled_api`` is ignored. Same decoder as
    :meth:`VibeWorkflow.from_envelope`.
    """
    return VibeWorkflow.from_envelope(raw)


def from_ui(
    raw: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
    use_comfy_converter: bool = True,
    comfy_converter_strict: bool = True,
) -> VibeWorkflow:
    """Ingest a LiteGraph list-nodes graph into a :class:`VibeWorkflow`."""
    raw = deepcopy(raw)
    api = _ui_graph_to_api(
        raw,
        schema_provider=schema_provider,
        use_comfy_converter=use_comfy_converter,
        comfy_converter_strict=comfy_converter_strict,
    )
    workflow = from_api(
        api,
        source_path=source_path,
        workflow_id=workflow_id,
        schema_provider=schema_provider,
    )
    # Graph-level LiteGraph groups are first-class on the IR.  The API dict
    # produced by the converter drops them, so carry them across from the raw
    # graph here (fail-closed: a non-list groups is rejected).
    workflow.groups = _vibe_groups(raw.get("groups"))
    # Subgraph signatures are part of π_edit.  Copy them onto the IR BEFORE
    # the door fingerprint is captured so a later definitions-only edit is
    # distinguishable from the ingest snapshot.
    raw_definitions = raw.get("definitions")
    if isinstance(raw_definitions, dict):
        workflow.metadata["definitions"] = deepcopy(raw_definitions)
    # Law 1: stash the raw wire bytes at the door.  The emit boundary
    # reproduces them byte-for-byte for an untouched graph
    # (``emit_ui(from_ui(J)) == J``) and prefers them for edited graphs.
    workflow.metadata[_UI_DOOR_KEY] = _capture_ui_door(
        raw, workflow, use_comfy_converter=use_comfy_converter
    )
    _attach_workflow_snapshot(workflow, raw, source_representation="ui")
    return workflow


def from_api(
    api_workflow: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
) -> VibeWorkflow:
    """Ingest a Comfy prompt dict into a :class:`VibeWorkflow`."""
    with untrusted_scope():
        return _from_api_impl(
            api_workflow,
            source_path=source_path,
            workflow_id=workflow_id,
            schema_provider=schema_provider,
        )


def _is_vibe_envelope(raw: dict[str, Any]) -> bool:
    """True when *raw* is a versioned (or compiled_api-bearing) rich envelope."""
    return isinstance(raw.get("nodes"), dict) and (
        "vibecomfy_format_version" in raw
        or isinstance(raw.get("compiled_api"), dict)
    )


def _named_import(
    raw: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
    use_comfy_converter: bool = True,
    comfy_converter_strict: bool = True,
) -> VibeWorkflow:
    """Happy-path import: envelope, then UI, then API. Never ``compile()`` to reach IR."""
    if _is_vibe_envelope(raw):
        return from_envelope(raw)
    if isinstance(raw.get("nodes"), list):
        return from_ui(
            raw,
            source_path=source_path,
            workflow_id=workflow_id,
            schema_provider=schema_provider,
            use_comfy_converter=use_comfy_converter,
            comfy_converter_strict=comfy_converter_strict,
        )
    api = normalize_to_api(
        raw,
        schema_provider=schema_provider,
        use_comfy_converter=use_comfy_converter,
        comfy_converter_strict=comfy_converter_strict,
    )
    return from_api(
        api,
        source_path=source_path,
        workflow_id=workflow_id,
        schema_provider=schema_provider,
    )


def _from_api_impl(
    api_workflow: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
) -> VibeWorkflow:
    """Ingest a Comfy prompt dict. Caller holds :func:`untrusted_scope`."""
    _enforce_exec_source_limits(api_workflow, surface="api.ingest")
    source = WorkflowSource(
        id=workflow_id or (Path(source_path).stem if source_path else "workflow"),
        path=source_path,
        source_type="api",
    )
    workflow = VibeWorkflow(id=source.id, source=source)
    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        raw_inputs = dict(node.get("inputs", {}))
        input_provenance = node.get("_input_provenance")
        if not isinstance(input_provenance, dict):
            input_provenance = {}
        inputs: dict[str, Any] = {}
        widgets: dict[str, Any] = {}
        class_type = str(node.get("class_type", "Unknown"))
        for key, value in raw_inputs.items():
            if input_provenance.get(key) != "widget" and is_canonical_api_link(value):
                continue
            if key.startswith("widget_") or _is_exec_widget_key(class_type, key):
                widgets[key] = value
            else:
                inputs[key] = value
        raw_widgets = _coerce_raw_widget_payload(
            node.get("_raw_widgets", node.get("raw_widgets"))
        )
        if raw_widgets is None:
            raw_ui = node.get("_ui")
            if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
                raw_widgets = _coerce_raw_widget_payload(
                    _raw_widget_payload_dict(raw_ui["widgets_values"], source="ui.widgets_values")
                )
        # R2-D2: API-only widget-shape materialization.  Nodes without any raw
        # UI/raw-widget evidence carry their widget vector as named ``widget_N``
        # carriers in the prompt dict; materialize it so the widget-shape fence
        # sees complete deterministic evidence (named inputs + schema order)
        # instead of refusing an API-declared widget shape as overflow.
        if raw_widgets is None:
            raw_widgets = _materialize_api_widget_payload(widgets)
        metadata = {
            key: value
            for key, value in node.items()
            if key
            not in {
                "class_type",
                "inputs",
                "_raw_widgets",
                "raw_widgets",
                "_input_provenance",
            }
        }
        # ── retain control_after_generate (UI-only) into metadata ──
        # Captured here, before the compile-time `_is_ui_only_prompt_input` filter
        # (workflow.py:471) drops it from the compiled API dict, so the emitter can
        # re-render it. Metadata-only: it never re-enters `inputs`/`widgets`, so
        # `compile("api")` stays byte-for-byte identical. Never guessed — when no
        # recognized control token is present, metadata stays unset and the emitter
        # emits the documented `fixed` default itself.
        control_value = _capture_control_after_generate(node, class_type)
        if control_value is not None:
            metadata.setdefault("control_after_generate", control_value)
        # ── retain flags/color/bgcolor from _ui into top-level metadata ──
        # Both paths: pure-Python path stores the full raw node in _ui (line 99);
        # comfy-converter path stores a slim _ui enriched by _merge_slim_ui.
        # Captured as metadata DATA only — never enters inputs/widgets (K3 invariant).
        # mode is first-class on VibeNode (the compile mute/bypass signal): the
        # field is populated below from `_ui.mode` (fallback metadata["mode"]) and
        # `_ui.mode` is LEFT IN PLACE so emit_ui_json's furniture keeps re-emitting
        # it.  No duplicate metadata["mode"] is written on new ingests.
        _ui_raw = metadata.get("_ui")
        if isinstance(_ui_raw, dict):
            # The _ui dict may alias the input API node's _ui (pure-Python path);
            # deepcopy so the caller's node dict is never corrupted.
            # Only assign when a real _ui was present — do not invent {}.
            _ui_node = deepcopy(_ui_raw)
            metadata["_ui"] = _ui_node
            for _vis_field in ("flags", "color", "bgcolor"):
                if _vis_field in _ui_node:
                    metadata.setdefault(_vis_field, _ui_node[_vis_field])
        # ── enrich node metadata from schema ──
        output_names = _schema_output_names(schema_provider, class_type)
        if output_names:
            metadata.setdefault("output_names", output_names)
        output_types = _schema_output_types(schema_provider, class_type)
        if output_types:
            metadata.setdefault("output_types", output_types)
        input_aliases = _schema_input_aliases(schema_provider, class_type)
        if input_aliases:
            metadata.setdefault("input_aliases", input_aliases)
        schema_source = _schema_source_provenance(schema_provider, class_type)
        if schema_source is not None:
            metadata.setdefault("schema_source", schema_source)
        if class_type == EXEC_CLASS_TYPE:
            _rebuild_exec_reload_metadata(metadata, widgets.get("io"))
        # S4 capability fence: ingest is the external-JSON boundary, so every
        # ingested node is tagged untrusted_source. Unconditional set — never
        # `setdefault` — so a hostile JSON cannot pre-declare itself trusted.
        metadata[PROVENANCE_KEY] = "untrusted_source"
        workflow.nodes[str(node_id)] = VibeNode(
            id=str(node_id),
            class_type=class_type,
            inputs=inputs,
            widgets=widgets,
            metadata=metadata,
            uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
            raw_widgets=raw_widgets,
            mode=_node_mode_from_metadata(metadata),
            pos=_geometry_pair(_ui_node.get("pos")) if isinstance(_ui_raw, dict) else None,
            size=_geometry_pair(_ui_node.get("size")) if isinstance(_ui_raw, dict) else None,
        )
        _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
        if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
            workflow.outputs.append(VibeOutput(node_id=str(node_id), output_type=workflow.nodes[str(node_id)].class_type))
    workflow.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))

    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        input_provenance = node.get("_input_provenance")
        if not isinstance(input_provenance, dict):
            input_provenance = {}
        for name, value in dict(node.get("inputs", {})).items():
            if input_provenance.get(name) != "widget" and is_canonical_api_link(value):
                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))

    workflow.requirements = _infer_requirements(workflow)

    # Stash an ingest-time snapshot immediately after uid minting and edge setup.
    # Captured once here so downstream delta computation can detect edits.
    from vibecomfy.ingest.snapshot import capture_ingest_snapshot  # local to avoid circular at module level
    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(api_workflow, workflow)
    _attach_workflow_snapshot(workflow, api_workflow, source_representation="api")

    # ``workflow.metadata`` is ``dict[str, Any]`` and transparently accepts
    # any extra keys.  In particular, ``summary`` (a ``WorkflowSummary`` dict)
    # may be present when re-ingesting a corpus JSON that was enriched with
    # LLM-generated summaries.  It is left untouched here — no validation,
    # no stripping — so it survives round-trips through this pipeline intact.
    return workflow


def _is_exec_widget_key(class_type: str, key: str) -> bool:
    return class_type == EXEC_CLASS_TYPE and key in {"source", "io"}


def _materialize_api_widget_payload(widgets: Mapping[str, Any]) -> RawWidgetPayload | None:
    """Deterministically materialize a widget payload from ``widget_N`` carriers.

    API-origin prompt dicts carry a node's widget vector as named ``widget_N``
    inputs.  When no raw UI/raw widget evidence exists (API-only node), that
    carrier sequence IS the working graph's widget-shape proof: the widget-shape
    fence must see it instead of treating the schema-declared count as complete
    and refusing the API-declared shape as unmaterialized overflow.

    Only fires when the carriers are exactly ``widget_0..widget_{n-1}`` (a
    complete contiguous vector).  Partial or gapped carriers stay unmaterialized
    so the fence keeps treating that shape as genuinely unknown.
    """
    indices: list[int] = []
    for key in widgets:
        key_str = str(key)
        if not key_str.startswith("widget_"):
            continue
        try:
            indices.append(int(key_str.split("_", 1)[1]))
        except ValueError:
            continue
    if not indices:
        return None
    ordered = sorted(indices)
    if ordered != list(range(len(ordered))):
        return None
    values = [deepcopy(widgets[f"widget_{index}"]) for index in ordered]
    return RawWidgetPayload(
        values=values,
        shape="list",
        source="api.widgets",
        has_dict_rows=False,
        length=len(values),
    )


def _normalize_exec_io_metadata(io_value: Any) -> dict[str, list[list[str | None]]] | None:
    from vibecomfy.comfy_nodes.exec_node import ExecNodeContractError, parse_io

    try:
        io_spec = parse_io(io_value)
    except ExecNodeContractError:
        return None
    normalized: dict[str, list[list[str | None]]] = {"inputs": [], "outputs": []}
    for field in ("inputs", "outputs"):
        normalized[field] = [[name, type_name] for name, type_name in io_spec.get(field, ())]
    return normalized


def _rebuild_exec_reload_metadata(metadata: dict[str, Any], io_value: Any) -> None:
    ui = metadata.get("_ui")
    if not isinstance(ui, dict):
        ui = {}
        metadata["_ui"] = ui
    properties = ui.get("properties")
    if not isinstance(properties, dict):
        properties = {}
        ui["properties"] = properties
    vibecomfy = properties.get("vibecomfy")
    if not isinstance(vibecomfy, dict):
        vibecomfy = {}
        properties["vibecomfy"] = vibecomfy
    normalized_io = _normalize_exec_io_metadata(io_value)
    if normalized_io is None:
        vibecomfy.pop("io", None)
    else:
        vibecomfy["io"] = normalized_io


def _enforce_exec_source_limits(api_workflow: dict[str, Any], *, surface: str) -> None:
    total_bytes = 0
    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        if str(node.get("class_type", "")) != EXEC_CLASS_TYPE:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        source = inputs.get("source")
        if not isinstance(source, str):
            continue
        source_bytes = len(source.encode("utf-8"))
        if source_bytes > EXEC_SOURCE_MAX_BYTES:
            raise ValueError(
                f"{EXEC_CLASS_TYPE} source at node {node_id!r} exceeds {EXEC_SOURCE_MAX_BYTES} bytes on {surface}"
            )
        total_bytes += source_bytes
    if total_bytes > EXEC_SOURCE_MAX_TOTAL_BYTES:
        raise ValueError(
            f"{EXEC_CLASS_TYPE} source total exceeds {EXEC_SOURCE_MAX_TOTAL_BYTES} bytes on {surface}"
        )


# Recognized litegraph `control_after_generate` tokens. Capture is restricted to
# these so an arbitrary widget value is never mistaken for a control mode.
_CONTROL_AFTER_GENERATE_VALUES: frozenset[str] = frozenset(
    {"fixed", "randomize", "increment", "decrement"}
)


def _capture_control_after_generate(node: dict[str, Any], class_type: str) -> str | None:
    """Recover a node's ``control_after_generate`` value, if present.

    Looks in two places, both available at named-importer (``from_api`` /
    ``from_ui``) time and both examined BEFORE the ``_schema_input_names``
    None-strip (:185) can discard the value during ``_normalize_ui_to_api``:

    1. A named ``control_after_generate`` input (e.g. api-format prompts, or schemas
       like ``RandomNoise`` that name the position).
    2. The raw litegraph ``widgets_values`` carried on the node's ``_ui`` payload,
       located via the committed widget schema position whose name is ``None`` (the
       UI-only control slot) or literally ``control_after_generate``.

    Only recognized control tokens are returned; anything else yields ``None`` so the
    value is never guessed.
    """
    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        named = inputs.get("control_after_generate")
        if isinstance(named, str) and named in _CONTROL_AFTER_GENERATE_VALUES:
            return named

    raw_ui = node.get("_ui")
    widgets = raw_ui.get("widgets_values") if isinstance(raw_ui, dict) else None
    if isinstance(widgets, list):
        names = widget_names_for_class(class_type)
        if names:
            for idx, name in enumerate(names):
                if name is not None and name != "control_after_generate":
                    continue
                if idx < len(widgets):
                    candidate = widgets[idx]
                    if isinstance(candidate, str) and candidate in _CONTROL_AFTER_GENERATE_VALUES:
                        return candidate
    return None


def _schema_input_names(schema_provider: SchemaProvider | None, class_type: str) -> list[str]:
    schema = schema_for(schema_provider, class_type)
    names = widget_names_from_schema(class_type, schema)
    return [name if name is not None else f"unused_widget_{index}" for index, name in enumerate(names)]


def _normalize_widget_input_name(names: list[str], index: int, value: Any) -> str:
    name = names[index]
    if not name.startswith("unused_widget_"):
        return name
    if not (isinstance(value, str) and value in _CONTROL_AFTER_GENERATE_VALUES):
        return name
    previous = names[index - 1] if index > 0 else ""
    if previous in {"seed", "noise_seed", "value"}:
        return "control_after_generate"
    return name


def _schema_output_names(schema_provider: SchemaProvider | None, class_type: str) -> list[str]:
    """Return output names from schema, preserving blank entries for partial evidence.

    The emitter will decide per-slot safety later (e.g. blank/duplicate names
    fall back to numeric ``.out(n)``).  Never drop the whole list just because
    one entry is missing.
    """
    schema = schema_for(schema_provider, class_type)
    outputs = getattr(schema, "outputs", None) or []
    names: list[str] = []
    for output in outputs:
        name = output.name if isinstance(output, OutputSpec) else getattr(output, "name", None)
        names.append(name if isinstance(name, str) else "")
    return names


def _schema_output_types(schema_provider: SchemaProvider | None, class_type: str) -> list[str]:
    schema = schema_for(schema_provider, class_type)
    outputs = getattr(schema, "outputs", None) or []
    types: list[str] = []
    for output in outputs:
        typ = output.type if isinstance(output, OutputSpec) else getattr(output, "type", None)
        types.append(typ if isinstance(typ, str) else "")
    return types


def _schema_input_aliases(schema_provider: SchemaProvider | None, class_type: str) -> list[str | None]:
    """Build input aliases from schema, excluding link-only types so widget positions do not shift."""
    from vibecomfy.porting.widgets.aliases import LINK_ONLY_TYPES

    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return []
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return []
    aliases: list[str | None] = []
    for name, spec in inputs.items():
        input_type = str(getattr(spec, "type", "") or "").upper()
        if input_type in LINK_ONLY_TYPES:
            continue
        aliases.append(str(name))
    return aliases if aliases else []


def _schema_source_provenance(schema_provider: SchemaProvider | None, class_type: str) -> dict[str, Any] | None:
    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return None
    return {
        "provider": getattr(schema, "source_provider", "unknown"),
        "path": getattr(schema, "source_path", None),
        "cache_path": getattr(schema, "source_cache_path", None),
        "server_url": getattr(schema, "source_server_url", None),
        "package": getattr(schema, "source_package", None),
        "version": getattr(schema, "source_version", None),
        "hash": getattr(schema, "source_hash", None),
        "confidence": getattr(schema, "confidence", 1.0),
    }


def ingest_workflow_and_ui(
    graph: dict[str, Any],
    *,
    schema_provider: SchemaProvider | None = None,
) -> tuple[VibeWorkflow, dict[str, Any]]:
    """Named door: detect shape once, never mutate caller inputs, retain IR.

    UI list-nodes are deep-copied at the door so caller inputs stay immutable.
    ``{prompt: API}`` unwraps once; the wrapper is retained as snapshot sidecar.
    Envelope/API graphs are converted and re-emitted as canonical UI JSON.
    Unknown shape stays unknown and fails closed.
    """
    from vibecomfy.porting.emit.ui import emit_ui_json

    if not isinstance(graph, dict):
        raise ValueError("graph must be a mapping")
    shape = detect_workflow_shape(graph)
    if shape == "unknown":
        return _ingest_unknown_shape(graph), graph
    if shape == "ui":
        detached = deepcopy(graph)
        workflow = from_ui(detached, schema_provider=schema_provider)
        return workflow, detached
    if shape == "vibe":
        detached = deepcopy(graph)
        workflow = from_envelope(detached)
        return workflow, emit_ui_json(
            workflow,
            schema_provider=schema_provider,
            guard_original_ui=detached,
        )
    if shape == "prompt_api":
        prompt = graph.get("prompt")
        if not isinstance(prompt, dict):
            raise ValueError("prompt_api wrapper must contain a mapping prompt")
        detached_prompt = deepcopy(prompt)
        workflow = from_api(detached_prompt, schema_provider=schema_provider)
        _attach_workflow_snapshot(
            workflow,
            deepcopy(graph),
            source_representation="prompt_api",
        )
        return workflow, emit_ui_json(
            workflow,
            schema_provider=schema_provider,
            guard_original_ui=detached_prompt,
        )
    detached = deepcopy(graph)
    workflow = from_api(detached, schema_provider=schema_provider)
    return workflow, emit_ui_json(
        workflow,
        schema_provider=schema_provider,
        guard_original_ui=detached,
    )


# ── Door-owned subgraph helper resolution ──────────────────────────────────
# These helpers inspect and mutate subgraph definition JSON.  They live in
# the ingest door because that is the only allowed graph-JSON mutation
# surface besides the emit door.  convert() calls this after snapshotting
# the unresolved definitions onto the IR.

_SUBGRAPH_RESOLVABLE = frozenset({
    "GetNode", "SetNode", "Reroute", "PrimitiveNode",
    "PrimitiveBoolean", "PrimitiveInt", "PrimitiveFloat",
    "PrimitiveString", "PrimitiveStringMultiline",
})


def _subgraph_link_origin_id(link: Any) -> str:
    if isinstance(link, dict):
        return str(link.get("origin_id", ""))
    return str(link[1])


def _subgraph_link_origin_slot(link: Any) -> int:
    if isinstance(link, dict):
        return int(link.get("origin_slot", 0))
    return int(link[2])


def _subgraph_link_target_id(link: Any) -> str:
    if isinstance(link, dict):
        return str(link.get("target_id", ""))
    return str(link[3])


def _subgraph_set_link_origin(link: Any, node_id: str, slot: int) -> None:
    if isinstance(link, dict):
        link["origin_id"] = int(node_id) if node_id.isdigit() else node_id
        link["origin_slot"] = slot
    else:
        link[1] = int(node_id) if node_id.isdigit() else node_id
        link[2] = slot


def _subgraph_widget(node: dict[str, Any], idx: int = 0) -> Any:
    values = node.get("widgets_values", [])
    if isinstance(values, list) and idx < len(values):
        return values[idx]
    return None


def resolve_subgraph_helpers(
    raw_workflow: dict[str, Any] | None,
    top_level_nodes: dict[str, Any],
    top_level_edges: list[Any],
    pre_collected_broadcasts: dict[str, list[Any]] | None = None,
) -> None:
    """Door-owned: fold Get/Set/Reroute/Primitive helpers inside subgraph defs."""
    if not raw_workflow:
        return
    defs = raw_workflow.get("definitions")
    if not isinstance(defs, dict):
        return
    subgraphs = defs.get("subgraphs")
    if not isinstance(subgraphs, list):
        return

    if pre_collected_broadcasts is not None:
        top_broadcasts = pre_collected_broadcasts
    else:
        from vibecomfy._compile._helpers import collect_broadcast_sources
        top_broadcasts = collect_broadcast_sources(top_level_nodes, top_level_edges)

    for subgraph in subgraphs:
        if isinstance(subgraph, dict):
            _resolve_subgraph_definition(subgraph, top_broadcasts)


def _resolve_subgraph_definition(subgraph: dict[str, Any], top_broadcasts: dict[str, Any]) -> None:
    nodes_list = subgraph.get("nodes")
    if not isinstance(nodes_list, list):
        return
    links_list = subgraph.get("links")
    if not isinstance(links_list, list):
        links_list = []

    nodes_dict: dict[str, dict[str, Any]] = {}
    for node in nodes_list:
        if isinstance(node, dict) and "id" in node:
            nodes_dict[str(node["id"])] = node

    for _ in range(100):
        changed = False
        helper_ids = [
            str(node["id"]) for node in nodes_list
            if isinstance(node, dict) and node.get("type") in _SUBGRAPH_RESOLVABLE
        ]
        for node_id in helper_ids:
            node = nodes_dict.get(node_id)
            if node is None:
                continue
            class_type = node.get("type", "")
            if class_type == "GetNode":
                changed |= _resolve_subgraph_getnode(
                    nodes_dict, nodes_list, links_list, node_id, node, top_broadcasts
                )
            elif class_type in ("Reroute", "PrimitiveNode"):
                changed |= _resolve_subgraph_passthrough(
                    nodes_dict, nodes_list, links_list, node_id
                )
            elif isinstance(class_type, str) and class_type.startswith("Primitive"):
                changed |= _resolve_subgraph_primitive(
                    nodes_dict, nodes_list, links_list, node_id
                )
        if not changed:
            break

    subgraph["nodes"] = nodes_list
    subgraph["links"] = links_list


def _resolve_subgraph_getnode(
    nodes_dict: dict[str, dict[str, Any]],
    nodes_list: list[Any],
    links_list: list[Any],
    node_id: str,
    node: dict[str, Any],
    top_broadcasts: dict[str, Any],
) -> bool:
    name = _subgraph_widget(node, 0)
    if not name or str(name) not in top_broadcasts:
        return False
    source = top_broadcasts[str(name)]
    source_id, source_slot = str(source[0]), int(source[1])
    for link in [item for item in links_list if _subgraph_link_origin_id(item) == node_id]:
        _subgraph_set_link_origin(link, source_id, source_slot)
    nodes_dict.pop(node_id, None)
    nodes_list[:] = [item for item in nodes_list if str(item.get("id", "")) != node_id]
    return True


def _resolve_subgraph_passthrough(
    nodes_dict: dict[str, dict[str, Any]],
    nodes_list: list[Any],
    links_list: list[Any],
    node_id: str,
) -> bool:
    inbound = [item for item in links_list if _subgraph_link_target_id(item) == node_id]
    if not inbound:
        return False
    source_id = _subgraph_link_origin_id(inbound[0])
    source_slot = _subgraph_link_origin_slot(inbound[0])
    for link in [item for item in links_list if _subgraph_link_origin_id(item) == node_id]:
        _subgraph_set_link_origin(link, source_id, source_slot)
    nodes_dict.pop(node_id, None)
    nodes_list[:] = [item for item in nodes_list if str(item.get("id", "")) != node_id]
    links_list[:] = [item for item in links_list if _subgraph_link_target_id(item) != node_id]
    return True


def _resolve_subgraph_primitive(
    nodes_dict: dict[str, dict[str, Any]],
    nodes_list: list[Any],
    links_list: list[Any],
    node_id: str,
) -> bool:
    nodes_dict.pop(node_id, None)
    nodes_list[:] = [item for item in nodes_list if str(item.get("id", "")) != node_id]
    links_list[:] = [
        item for item in links_list
        if _subgraph_link_origin_id(item) != node_id and _subgraph_link_target_id(item) != node_id
    ]
    return True

