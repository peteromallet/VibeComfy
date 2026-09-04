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
from vibecomfy.identity.scope import compose_scope_path, sg_key
from vibecomfy.identity.uid import make_uid, mint_local_uid, validate_local_uid
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
            _door_freeze(node.native_input_names),
            _door_freeze(node.native_output_names),
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


def _validate_json_semantics(value: Any, *, path: str = "value") -> None:
    """Reject values which cannot be part of canonical JSON semantics."""
    if value is None or isinstance(value, (str, int, bool)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            # Geometry and raw UI furniture are presentation evidence, not
            # canonical semantic values; malformed furniture is retained for
            # diagnostics while semantic payloads fail closed.
            if "._ui." in path or ".pos" in path or ".size" in path:
                return
            raise ValueError(f"nonfinite semantic value at {path}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"non-string JSON key at {path}: {key!r}")
            _validate_json_semantics(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_json_semantics(item, path=f"{path}[{index}]")
        return
    raise ValueError(f"non-JSON semantic value at {path}: {type(value).__name__}")


def _validate_api_shape(api: Any) -> None:
    if not isinstance(api, Mapping):
        raise ValueError("API workflow must be a mapping")
    seen: set[str] = set()
    nodes_by_id: dict[str, Mapping[str, Any]] = {
        str(raw_id): node for raw_id, node in api.items()
        if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) and isinstance(node, Mapping)
    }
    for raw_id, node in api.items():
        if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)):
            raise ValueError(f"node id {raw_id!r} must be an integer or string")
        node_id = str(raw_id)
        validate_local_uid(node_id, field="API node id")
        if node_id in seen:
            raise ValueError(f"duplicate canonical node id {node_id!r}")
        seen.add(node_id)
        if not isinstance(node, Mapping):
            raise ValueError(f"node {node_id!r} must be a mapping")
        nodes_by_id[node_id] = node
        class_type = node.get("class_type")
        if not isinstance(class_type, str) or not class_type.strip():
            raise ValueError(f"node {node_id!r} class_type must be a nonblank string")
        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            raise ValueError(f"node {node_id!r} inputs must be a mapping")
        for name, value in inputs.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"node {node_id!r} input names must be nonblank strings")
            if is_canonical_api_link(value):
                if (not isinstance(value[0], str) or not value[0].strip()
                        or "#" in value[0] or "/" in value[0]
                        or value[0] in {"-10", "-20"}
                        or isinstance(value[1], bool) or not isinstance(value[1], int)
                        or value[1] < 0 or value[0] not in nodes_by_id):
                    raise ValueError(f"node {node_id!r} input {name!r} has malformed API link")


def _definition_entries(raw: Any, *, path: str) -> list[dict[str, Any]]:
    if isinstance(raw, Mapping) and "subgraphs" in raw:
        entries = raw["subgraphs"]
        if not isinstance(entries, (list, tuple)):
            raise ValueError(f"{path}.subgraphs must be a list")
    elif isinstance(raw, Mapping):
        entries = list(raw.values())
    elif isinstance(raw, (list, tuple)):
        entries = list(raw)
    else:
        raise ValueError(f"{path} must be a mapping or list")
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(f"{path}[{index}] definition must be a mapping")
        result.append(deepcopy(dict(entry)))
    return result


def _validate_recursive_node(node: Mapping[str, Any], *, scope: str, index: int) -> dict[str, Any]:
    raw_id = node.get("uid")
    if not isinstance(raw_id, str) or not raw_id.strip():
        raw_id = node.get("id")
    if raw_id is None or isinstance(raw_id, bool):
        raise ValueError(f"definition {scope!r} node {index}: id is required")
    local = validate_local_uid(str(raw_id), field=f"definition {scope!r} node uid")
    if "id" in node:
        validate_local_uid(str(node["id"]), field=f"definition {scope!r} node id")
    class_type = node.get("class_type", node.get("type"))
    if not isinstance(class_type, str) or not class_type.strip():
        raise ValueError(f"definition {scope!r} node {local!r}: class_type is required")
    normalized = deepcopy(dict(node))
    normalized["id"] = str(node.get("id", local))
    normalized["uid"] = local
    normalized["class_type"] = class_type
    for roster_name in ("native_input_names", "native_output_names"):
        if roster_name in normalized:
            roster = normalized[roster_name]
            if not isinstance(roster, (list, tuple)):
                raise ValueError(f"definition {scope!r} node {local!r} {roster_name} must be a list")
            seen_names: set[str] = set()
            clean_roster: list[str | None] = []
            for item in roster:
                if item is None:
                    clean_roster.append(None)
                elif isinstance(item, str) and item.strip() and item not in seen_names:
                    seen_names.add(item)
                    clean_roster.append(item)
                else:
                    raise ValueError(f"definition {scope!r} node {local!r} has malformed {roster_name}")
            normalized[roster_name] = clean_roster
    if "inputs" in normalized and not isinstance(normalized["inputs"], (Mapping, list, tuple)):
        raise ValueError(f"definition {scope!r} node {local!r}: inputs must be mapping or list")
    if "outputs" in normalized and not isinstance(normalized["outputs"], (list, tuple)):
        raise ValueError(f"definition {scope!r} node {local!r}: outputs must be a list")
    if "inputs" in normalized and isinstance(normalized["inputs"], (list, tuple)):
        for pos, item in enumerate(normalized["inputs"]):
            if not isinstance(item, Mapping):
                raise ValueError(f"definition {scope!r} node {local!r} input {pos} malformed")
    if "outputs" in normalized:
        for pos, item in enumerate(normalized["outputs"]):
            if not isinstance(item, Mapping):
                raise ValueError(f"definition {scope!r} node {local!r} output {pos} malformed")
    return normalized


def _validate_definition_links(
    definition: Mapping[str, Any],
    *,
    scope: str,
    node_ids: set[str],
    nodes_by_alias: Mapping[str, Mapping[str, Any]],
) -> None:
    links = definition.get("links", [])
    if links is None:
        links = []
    if not isinstance(links, (list, tuple)):
        raise ValueError(f"definition {scope!r} links must be a list")
    seen: set[int] = set()
    for index, link in enumerate(links):
        if isinstance(link, Mapping):
            required = {"id", "origin_id", "origin_slot", "target_id", "target_slot", "type"}
            if set(link) != required:
                raise ValueError(f"definition {scope!r} link {index} must contain the exact link fields")
            link_id, origin, origin_slot, target, target_slot, link_type = (link[k] for k in ("id", "origin_id", "origin_slot", "target_id", "target_slot", "type"))
        elif isinstance(link, (list, tuple)) and len(link) == 6:
            link_id, origin, origin_slot, target, target_slot, link_type = link
        else:
            raise ValueError(f"definition {scope!r} link {index} must be an exact six-field record")
        if not isinstance(link_type, str):
            raise ValueError(f"definition {scope!r} link {index} type must be a string")
        if isinstance(link_id, bool) or not isinstance(link_id, int) or link_id < 0 or link_id in seen:
            raise ValueError(f"definition {scope!r} link {index} has duplicate or invalid id")
        seen.add(link_id)
        for endpoint, label in ((origin, "origin"), (target, "target")):
            if isinstance(endpoint, bool) or not isinstance(endpoint, (str, int)):
                raise ValueError(f"definition {scope!r} link {label} endpoint must be a local id")
            text = str(endpoint)
            if text in {"-10", "-20"}:
                raise ValueError(f"unsupported_boundary_encoding: definition {scope!r} {label} uses native {text}")
            validate_local_uid(text, field=f"definition {scope!r} link {label} endpoint")
            if text not in node_ids:
                raise ValueError(f"definition {scope!r} link {label} endpoint {text!r} is unknown")
        for slot, label in ((origin_slot, "origin_slot"), (target_slot, "target_slot")):
            if isinstance(slot, bool) or not isinstance(slot, int) or slot < 0:
                raise ValueError(f"definition {scope!r} link {label} must be a nonnegative integer")
        origin_node = nodes_by_alias[str(origin)]
        target_node = nodes_by_alias[str(target)]
        output_roster = origin_node.get("native_output_names", origin_node.get("outputs", []))
        input_roster = target_node.get("native_input_names", target_node.get("inputs", []))
        if isinstance(output_roster, (list, tuple)) and origin_slot >= len(output_roster):
            raise ValueError(f"definition {scope!r} link {index} origin_slot exceeds output roster")
        if isinstance(input_roster, (list, tuple)) and target_slot >= len(input_roster):
            raise ValueError(f"definition {scope!r} link {index} target_slot exceeds input roster")
        if isinstance(origin_node.get("outputs"), (list, tuple)):
            output = origin_node["outputs"][origin_slot]
            if not isinstance(output, Mapping) or link_id not in (output.get("links") or []):
                raise ValueError(f"definition {scope!r} link {index} is orphaned from output record")
        if isinstance(target_node.get("inputs"), (list, tuple)):
            target_input = target_node["inputs"][target_slot]
            if not isinstance(target_input, Mapping) or target_input.get("link") != link_id:
                raise ValueError(f"definition {scope!r} link {index} does not match target input record")


def _normalize_recursive_definitions(raw: Any) -> dict[str, Any]:
    """Validate/canonicalize the existing JSON-shaped recursive IR in place."""
    if raw in (None, {}, []):
        return {}
    entries = _definition_entries(raw, path="definitions")
    result: list[dict[str, Any]] = []
    all_keys: set[str] = set()

    def walk(source: Mapping[str, Any], parent: tuple[str, ...], path: str) -> dict[str, Any]:
        key = sg_key(source)
        supplied = source.get("sg_key")
        if supplied is not None and supplied != key:
            raise ValueError(f"definition sg_key {supplied!r} does not match its structural identity")
        scope = compose_scope_path((*parent, key))
        if key in all_keys:
            raise ValueError(f"duplicate or colliding subgraph definition identity {key!r}")
        all_keys.add(key)
        values = source.get("nodes", [])
        if isinstance(values, Mapping):
            values = list(values.values())
        if not isinstance(values, (list, tuple)):
            raise ValueError(f"definition {scope!r} nodes must be a list or mapping")
        normalized_nodes: list[dict[str, Any]] = []
        ids: set[str] = set()
        for index, node in enumerate(values):
            if not isinstance(node, Mapping):
                raise ValueError(f"definition {scope!r} node {index} malformed")
            normalized = _validate_recursive_node(node, scope=scope, index=index)
            uid = normalized["uid"]
            if uid in ids:
                raise ValueError(f"duplicate_scoped_node_uid: {uid!r} in scope {scope!r}")
            ids.add(uid)
            normalized_nodes.append(normalized)
        normalized_nodes.sort(key=lambda item: item["uid"])
        aliases = set(ids)
        for node in normalized_nodes:
            aliases.add(str(node["id"]))
        nodes_by_alias = {}
        for node in normalized_nodes:
            nodes_by_alias[str(node["uid"])] = node
            nodes_by_alias[str(node["id"])] = node
        _validate_definition_links(
            source,
            scope=scope,
            node_ids=aliases,
            nodes_by_alias=nodes_by_alias,
        )
        out = deepcopy(dict(source))
        out.update({"sg_key": key, "scope_path": scope, "nodes": normalized_nodes})
        nested_raw = source.get("definitions")
        if nested_raw not in (None, {}, []):
            nested = _definition_entries(nested_raw, path=f"{scope}.definitions")
            nested_norm = [walk(item, (*parent, key), f"{scope}.definitions[{i}]") for i, item in enumerate(nested)]
            nested_norm.sort(key=lambda item: item["sg_key"])
            out["definitions"] = {"subgraphs": nested_norm}
        if "virtual_wires" in out:
            out["virtual_wires"] = _normalize_virtual_wires(out["virtual_wires"], scope=scope)
        return out

    for index, entry in enumerate(entries):
        result.append(walk(entry, (), f"definitions[{index}]"))
    result.sort(key=lambda item: item["sg_key"])
    return {"subgraphs": result}


def _normalize_virtual_wires(raw: Any, *, scope: str = "") -> dict[str, Any]:
    if raw in (None, {}):
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"virtual_wires at {scope!r} must be a mapping")
    result: dict[str, Any] = {}
    for name, value in sorted(raw.items(), key=lambda item: str(item[0])):
        if not isinstance(name, str) or not name.strip() or not isinstance(value, Mapping):
            raise ValueError(f"virtual wire {name!r} is malformed")
        if "channel" in value or "endpoints" in value:
            raise ValueError(f"legacy virtual wire {name!r} is not canonical")
        legs = value.get("legs")
        if not isinstance(legs, (list, tuple)):
            raise ValueError(f"virtual wire {name!r} requires explicit legs")
        normalized_legs: list[dict[str, Any]] = []
        seen: set[tuple[int, int]] = set()
        for index, leg in enumerate(legs):
            if not isinstance(leg, Mapping):
                raise ValueError(f"virtual wire {name!r} leg {index} is malformed")
            item = deepcopy(dict(leg))
            item_scope = item.get("scope_path", scope)
            if not isinstance(item_scope, str) or item_scope != scope:
                raise ValueError(f"virtual wire {name!r} leg {index} crosses scope")
            item["scope_path"] = item_scope
            li, oi = item.get("leg_index"), item.get("occurrence_index")
            if isinstance(li, bool) or not isinstance(li, int) or li < 0 or isinstance(oi, bool) or not isinstance(oi, int) or oi < 0:
                raise ValueError(f"virtual wire {name!r} leg {index} has invalid indexes")
            if (li, oi) in seen:
                raise ValueError(f"virtual wire {name!r} has duplicate leg occurrence {(li, oi)!r}")
            seen.add((li, oi))
            for prefix in ("from", "to"):
                endpoint = item.get(f"{prefix}_node", item.get(f"{prefix}_uid"))
                if endpoint is None:
                    endpoint = item.get(prefix, {}).get("uid") if isinstance(item.get(prefix), Mapping) else None
                if endpoint is None or not isinstance(endpoint, str) or not endpoint.strip() or "#" in endpoint or "/" in endpoint:
                    raise ValueError(f"virtual wire {name!r} leg {index} has invalid {prefix} endpoint")
            normalized_legs.append(item)
        normalized_legs.sort(key=lambda item: (item["leg_index"], item["occurrence_index"]))
        result[name] = {key: deepcopy(item) for key, item in value.items() if key != "legs"}
        result[name]["legs"] = normalized_legs
    return result


def _normalize_interfaces(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("interfaces must be a mapping")
    result: dict[str, Any] = {}
    for scope, value in sorted(raw.items(), key=lambda item: str(item[0])):
        if not isinstance(scope, str) or not scope.strip() or "sg0" in scope:
            raise ValueError(f"interface scope {scope!r} is malformed")
        if isinstance(value, Mapping):
            normalized = deepcopy(dict(value))
            for direction in ("inputs", "outputs"):
                members = normalized.get(direction, [])
                if not isinstance(members, (list, tuple)):
                    raise ValueError(f"interface {scope!r} {direction} must be a list")
                seen: set[str] = set()
                out: list[dict[str, Any]] = []
                for index, member in enumerate(members):
                    if not isinstance(member, Mapping):
                        raise ValueError(f"interface {scope!r} member {index} is malformed")
                    name = member.get("name", member.get("port", member.get("interface")))
                    if not isinstance(name, str) or not name.strip() or name in seen:
                        raise ValueError(f"interface {scope!r} has invalid or duplicate member {name!r}")
                    seen.add(name)
                    supplied_direction = member.get("direction")
                    if supplied_direction is not None and supplied_direction != direction[:-1]:
                        raise ValueError(f"interface {scope!r} member {index} has invalid direction")
                    item = deepcopy(dict(member))
                    item["name"] = name
                    item["direction"] = direction[:-1]
                    out.append(item)
                normalized[direction] = out
            result[scope] = normalized
        elif isinstance(value, (list, tuple)):
            members = []
            for index, member in enumerate(value):
                if not isinstance(member, Mapping):
                    raise ValueError(f"interface {scope!r} member {index} is malformed")
                name = member.get("name", member.get("port", member.get("interface")))
                direction = member.get("direction")
                if not isinstance(name, str) or not name.strip() or direction not in {"input", "output"}:
                    raise ValueError(f"interface {scope!r} member {index} has invalid direction/name")
                members.append(deepcopy(dict(member)))
            result[scope] = members
        else:
            raise ValueError(f"interface {scope!r} must be a mapping or list")
    return result


def _normalize_boundary_ports(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, (list, tuple)):
        raise ValueError("boundary_ports must be a list")
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, value in enumerate(raw):
        if not isinstance(value, Mapping):
            raise ValueError(f"boundary port {index} is malformed")
        scope = value.get("scope_path", "")
        name = value.get("name", value.get("port_name", value.get("interface")))
        direction = value.get("direction")
        node = value.get("node_uid", value.get("node_id", value.get("uid")))
        field_name = value.get("field", value.get("input", value.get("output", value.get("port"))))
        if not isinstance(scope, str) or not isinstance(name, str) or not name.strip() or direction not in {"input", "output"}:
            raise ValueError(f"boundary port {index} has malformed scope/name/direction")
        if node is None or not isinstance(field_name, str) or not field_name.strip():
            raise ValueError(f"boundary port {index} requires local node and field")
        local = validate_local_uid(str(node), field=f"boundary port {index} node")
        key = (scope, name, direction)
        if key in seen:
            raise ValueError(f"duplicate boundary port {key!r}")
        seen.add(key)
        item = deepcopy(dict(value))
        item.update({"scope_path": scope, "name": name, "direction": direction, "node_uid": local, "field": field_name})
        result.append(item)
    return sorted(result, key=lambda item: (item["scope_path"], item["name"], item["direction"]))


def _validate_recursive_contract_metadata(
    definitions: Any,
    interfaces: Mapping[str, Any],
    boundary_ports: list[dict[str, Any]],
) -> None:
    """Validate recursive interface ownership and local boundary endpoints."""
    owners: dict[str, tuple[str, dict[str, Mapping[str, Any]]]] = {}

    def walk(raw: Any, parent: tuple[str, ...]) -> None:
        for definition in _definition_entries(raw, path="definitions"):
            key = str(definition.get("sg_key") or sg_key(definition))
            scope = compose_scope_path((*parent, key))
            by_id: dict[str, Mapping[str, Any]] = {}
            for node in definition.get("nodes", ()):
                if not isinstance(node, Mapping):
                    continue
                local = str(node.get("uid", node.get("id", "")))
                by_id[local] = node
                by_id[str(node.get("id", local))] = node
            owners[key] = (scope, by_id)
            owners[scope] = (scope, by_id)
            nested = definition.get("definitions")
            if nested not in (None, {}, []):
                walk(nested, (*parent, key))

    if definitions not in (None, {}, []):
        walk(definitions, ())

    declared: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for raw_scope, raw_interface in interfaces.items():
        scope = str(raw_scope)
        owner = owners.get(scope)
        if owner is None:
            raise ValueError(f"interface {scope!r} has no indexed definition owner")
        if isinstance(raw_interface, Mapping):
            members: list[Mapping[str, Any]] = []
            for direction in ("inputs", "outputs"):
                values = raw_interface.get(direction, ())
                if not isinstance(values, (list, tuple)):
                    raise ValueError(f"interface {scope!r} {direction} must be a list")
                for member in values:
                    if not isinstance(member, Mapping):
                        raise ValueError(f"interface {scope!r} member must be a mapping")
                    supplied = member.get("direction")
                    if supplied is not None and supplied != direction[:-1]:
                        raise ValueError(f"interface {scope!r} member direction is inconsistent")
                    members.append({**dict(member), "direction": direction[:-1]})
        elif isinstance(raw_interface, (list, tuple)):
            members = []
            for member in raw_interface:
                if not isinstance(member, Mapping):
                    raise ValueError(f"interface {scope!r} member must be a mapping")
                members.append(member)
        else:
            raise ValueError(f"interface {scope!r} must be a mapping or list")
        for member in members:
            name = member.get("name", member.get("port", member.get("interface")))
            direction = member.get("direction")
            if not isinstance(name, str) or not name.strip() or direction not in {"input", "output"}:
                raise ValueError(f"interface {scope!r} member needs name and direction")
            if "type" in member and member["type"] is not None and not isinstance(member["type"], str):
                raise ValueError(f"interface {scope!r} member type must be a string")
            identity = (owner[0], name, direction)
            if identity in declared:
                raise ValueError(f"duplicate interface member {identity!r}")
            declared[identity] = member

    bound: set[tuple[str, str, str]] = set()
    for index, port in enumerate(boundary_ports):
        scope = port["scope_path"]
        owner = owners.get(scope)
        if owner is None:
            raise ValueError(f"boundary port {index} scope {scope!r} has no indexed definition owner")
        local = validate_local_uid(str(port["node_uid"]), field=f"boundary port {index} node")
        node = owner[1].get(local)
        if node is None:
            raise ValueError(f"boundary port {index} endpoint {local!r} is not local to scope {scope!r}")
        direction = port["direction"]
        field_name = port["field"]
        roster_key = "inputs" if direction == "input" else "outputs"
        roster = node.get(roster_key, ())
        names = {
            str(item.get("name"))
            for item in roster
            if isinstance(item, Mapping) and isinstance(item.get("name"), str)
        }
        if names and field_name not in names:
            raise ValueError(f"boundary port {index} field {field_name!r} is absent from local {roster_key} roster")
        identity = (owner[0], port["name"], direction)
        if identity in bound:
            raise ValueError(f"duplicate boundary binding {identity!r}")
        bound.add(identity)

    if bound:
        for identity in declared:
            if identity not in bound:
                raise ValueError(f"interface member {identity!r} has no local boundary binding")
        for identity in bound:
            if declared and identity not in declared:
                raise ValueError(f"boundary binding {identity!r} has no declared interface member")


def _capture_import_virtual_wires(workflow: VibeWorkflow) -> None:
    """Capture proven Set/Get legs without mutating authored helper nodes."""

    def node_channel(node: Any) -> str | None:
        values = getattr(node, "widgets", {})
        inputs = getattr(node, "inputs", {})
        value = inputs.get("widget_0", values.get("widget_0"))
        if value is None:
            value = inputs.get("name", values.get("name"))
        return value if isinstance(value, str) and value.strip() else None

    def capture(nodes: Mapping[str, Any], edges: list[VibeEdge], scope: str) -> dict[str, Any]:
        helper_types = {"SetNode", "GetNode", "Reroute", "PrimitiveNode"}
        by_id = {str(key): value for key, value in nodes.items()}
        incoming: dict[str, list[VibeEdge]] = {key: [] for key in by_id}
        outgoing: dict[str, list[VibeEdge]] = {key: [] for key in by_id}
        for edge in edges:
            if str(edge.from_node) not in by_id or str(edge.to_node) not in by_id:
                raise ValueError(f"virtual wire {scope!r} has an unknown edge endpoint")
            incoming[str(edge.to_node)].append(edge)
            outgoing[str(edge.from_node)].append(edge)
        sets: dict[str, list[tuple[str, VibeEdge]]] = {}
        gets: dict[str, list[str]] = {}
        for node_id, node in by_id.items():
            class_type = getattr(node, "class_type", "")
            if class_type not in {"SetNode", "GetNode"}:
                continue
            name = node_channel(node)
            if name is None:
                raise ValueError(f"{class_type} node {node_id!r} in scope {scope!r} has no named channel")
            if class_type == "SetNode":
                producer_edges = [edge for edge in incoming[node_id] if edge.to_input != "widget_0"]
                if len(producer_edges) != 1:
                    raise ValueError(f"SetNode {node_id!r} in scope {scope!r} needs exactly one data input")
                sets.setdefault(name, []).append((node_id, producer_edges[0]))
            else:
                gets.setdefault(name, []).append(node_id)
        wires: dict[str, Any] = {}
        for name, getters in gets.items():
            if name not in sets:
                raise ValueError(f"GetNode channel {name!r} in scope {scope!r} has no matching SetNode")
            if len(sets[name]) != 1:
                raise ValueError(f"ambiguous virtual wire channel {name!r} in scope {scope!r}: multiple SetNode producers")
            legs: list[dict[str, Any]] = []
            for _set_id, producer_edge in sets[name]:
                for get_id in getters:
                    consumers = [edge for edge in outgoing[get_id] if edge.to_input != "widget_0"]
                    if not consumers:
                        # ComfyUI may retain an unconnected GetNode while a user is
                        # editing.  It is not a capturable virtual-wire leg, but it
                        # is also not an ambiguous/missing-channel import error.
                        continue
                    for consumer in consumers:
                        source_id, source_output = str(producer_edge.from_node), producer_edge.from_output
                        target_id, target_input = str(consumer.to_node), consumer.to_input
                        # Traverse only evidenced helper passthroughs. This is
                        # capture, not lowering: authored nodes/edges remain.
                        seen: set[str] = set()
                        while by_id[source_id].class_type in {"Reroute", "PrimitiveNode"}:
                            if source_id in seen or len(incoming[source_id]) != 1:
                                raise ValueError(f"ambiguous virtual-wire source path at {source_id!r}")
                            seen.add(source_id)
                            prior = incoming[source_id][0]
                            source_id, source_output = str(prior.from_node), prior.from_output
                        seen.clear()
                        while by_id[target_id].class_type in {"Reroute", "PrimitiveNode"}:
                            if target_id in seen or len(outgoing[target_id]) != 1:
                                raise ValueError(f"ambiguous virtual-wire target path at {target_id!r}")
                            seen.add(target_id)
                            following = outgoing[target_id][0]
                            target_id, target_input = str(following.to_node), following.to_input
                        if by_id[source_id].class_type in helper_types or by_id[target_id].class_type in helper_types:
                            raise ValueError(f"virtual-wire {name!r} has no real producer/consumer")
                        legs.append({"scope_path": scope, "leg_index": len(legs), "occurrence_index": 0,
                                     "from_node": source_id, "from_output": source_output,
                                     "to_node": target_id, "to_input": target_input})
            if legs:
                wires[name] = {"legs": legs}
        return wires

    root = capture(workflow.nodes, workflow.edges, "")
    for name, value in root.items():
        workflow.virtual_wires.setdefault(name, value)

    def recursive(raw: Any, parent: tuple[str, ...]) -> None:
        if isinstance(raw, Mapping) and isinstance(raw.get("subgraphs"), (list, tuple)):
            entries = raw["subgraphs"]
        elif isinstance(raw, Mapping):
            entries = list(raw.values())
        elif isinstance(raw, (list, tuple)):
            entries = raw
        else:
            raise ValueError("definitions must be a mapping or list")
        for definition in entries:
            if not isinstance(definition, dict):
                raise ValueError("definition must be a mapping")
            key = str(definition.get("sg_key") or sg_key(definition))
            scope = compose_scope_path((*parent, key))
            nodes = definition.get("nodes", [])
            if isinstance(nodes, Mapping):
                nodes = list(nodes.values())
            local_nodes: dict[str, VibeNode] = {}
            for item in nodes:
                if isinstance(item, Mapping):
                    local = str(item.get("uid", item.get("id", "")))
                    raw_widgets = item.get("widgets")
                    if isinstance(raw_widgets, Mapping):
                        helper_widgets = dict(raw_widgets)
                    else:
                        values = item.get("widgets_values")
                        helper_widgets = {"widget_0": values[0]} if isinstance(values, list) and values else {}
                    local_nodes[local] = VibeNode(local, str(item.get("class_type", item.get("type", ""))),
                                                   inputs=dict(item.get("inputs", {})) if isinstance(item.get("inputs"), Mapping) else {},
                                                   widgets=helper_widgets)
            local_edges: list[VibeEdge] = []
            legacy_boundary = any(
                isinstance(link, (list, tuple)) and len(link) == 6 and (str(link[1]) in {"-10", "-20"} or str(link[3]) in {"-10", "-20"})
                or isinstance(link, Mapping) and (str(link.get("origin_id")) in {"-10", "-20"} or str(link.get("target_id")) in {"-10", "-20"})
                for link in definition.get("links", [])
            )
            for link in definition.get("links", []):
                if legacy_boundary:
                    break
                if isinstance(link, (list, tuple)):
                    local_edges.append(VibeEdge(str(link[1]), str(link[2]), str(link[3]), str(link[4])))
                elif isinstance(link, Mapping):
                    local_edges.append(VibeEdge(str(link["origin_id"]), str(link["origin_slot"]), str(link["target_id"]), str(link["target_slot"])))
            found = {} if legacy_boundary else capture(local_nodes, local_edges, scope)
            if found:
                definition["virtual_wires"] = found
            nested = definition.get("definitions")
            if nested not in (None, {}, []):
                recursive(nested, (*parent, key))
    if workflow.definitions:
        recursive(workflow.definitions, ())


def _validate_virtual_wire_endpoints(workflow: VibeWorkflow) -> None:
    """Ensure explicit virtual legs reference local authored endpoints."""
    def check(wires: Any, ids: set[str], scope: str) -> None:
        if not isinstance(wires, Mapping):
            return
        for name, value in wires.items():
            if not isinstance(value, Mapping):
                continue
            for index, leg in enumerate(value.get("legs", ())):
                if not isinstance(leg, Mapping):
                    continue
                for prefix in ("from", "to"):
                    endpoint = leg.get(f"{prefix}_node", leg.get(f"{prefix}_uid"))
                    if endpoint is None and isinstance(leg.get(prefix), Mapping):
                        endpoint = leg[prefix].get("uid", leg[prefix].get("id"))
                    if str(endpoint) not in ids:
                        raise ValueError(f"virtual wire {name!r} leg {index} endpoint {endpoint!r} is unknown in scope {scope!r}")
    check(workflow.virtual_wires, {str(node_id) for node_id in workflow.nodes} | {str(node.uid) for node in workflow.nodes.values()}, "")

    def recursive(raw: Any, parent: tuple[str, ...]) -> None:
        for definition in _definition_entries(raw, path="definitions"):
            key = str(definition.get("sg_key") or sg_key(definition))
            scope = compose_scope_path((*parent, key))
            values = definition.get("nodes", [])
            if isinstance(values, Mapping):
                values = list(values.values())
            ids = {str(item.get("id", item.get("uid"))) for item in values if isinstance(item, Mapping)} | {str(item.get("uid", item.get("id"))) for item in values if isinstance(item, Mapping)}
            check(definition.get("virtual_wires"), ids, scope)
            nested = definition.get("definitions")
            if nested not in (None, {}, []):
                recursive(nested, (*parent, key))
    if workflow.definitions:
        recursive(workflow.definitions, ())


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
    if not isinstance(raw, dict):
        raise ValueError("workflow source must be a mapping")
    # Inputs crossing this boundary are untrusted JSON evidence.  Validate and
    # detach before any converter can retain nested references.
    raw = deepcopy(raw)
    _validate_json_semantics(raw, path="workflow")
    shape = detect_workflow_shape(raw)
    if shape == "api":
        api = deepcopy(raw.get("prompt", raw))
        _enforce_exec_source_limits(api, surface="api")
        _validate_api_shape(api)
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
    _validate_raw_ui_node_identities(raw)
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


def _native_port_names(node: Mapping[str, Any], field_name: str) -> list[str | None] | None:
    """Capture only the exact serialized LiteGraph socket-name roster."""
    if field_name not in node:
        return None
    raw = node[field_name]
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"UI node {node.get('id')!r} {field_name} must be a list")
    names: list[str | None] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if item is None:
            names.append(None)
            continue
        if not isinstance(item, Mapping):
            raise ValueError(
                f"UI node {node.get('id')!r} {field_name}[{index}] must be an object or null"
            )
        name = item.get("name")
        # LiteGraph serializes an unnamed socket as an empty-name row.  It is
        # a positional hole in the canonical roster, not a usable address.
        if name == "":
            name = None
        if name is not None and (not isinstance(name, str) or not name.strip()):
            raise ValueError(
                f"UI node {node.get('id')!r} {field_name}[{index}].name must be a nonblank string or null"
            )
        if isinstance(name, str):
            if name in seen:
                raise ValueError(
                    f"UI node {node.get('id')!r} {field_name} contains duplicate name {name!r}"
                )
            seen.add(name)
        names.append(name)
    return names


def _normalize_ui_to_api(raw: dict[str, Any], *, schema_provider: SchemaProvider | None = None) -> dict[str, Any]:
    _validate_raw_ui_node_identities(raw)
    raw_nodes = raw.get("nodes")
    if not isinstance(raw_nodes, list):
        raise ValueError("UI nodes must be a list")
    nodes = {str(node["id"]): node for node in raw_nodes}
    links = raw.get("links", [])
    if not isinstance(links, list):
        raise ValueError("UI links must be a list")
    link_map: dict[int, tuple[str, int, str, int]] = {}
    for index, link in enumerate(links):
        if isinstance(link, list) and len(link) == 6:
            link_id, origin, origin_slot, target, target_slot, link_type = link
            if not isinstance(link_type, str):
                raise ValueError(f"UI link {index} type must be a string")
        elif isinstance(link, Mapping) and {"id", "origin_id", "origin_slot", "target_id", "target_slot", "type"} <= set(link):
            link_id, origin, origin_slot, target, target_slot, link_type = (link[k] for k in ("id", "origin_id", "origin_slot", "target_id", "target_slot", "type"))
            if link_type is not None and not isinstance(link_type, str):
                raise ValueError(f"UI link {index} type must be a string or null")
        else:
            raise ValueError(f"UI link {index} must be an exact six-field record")
        if isinstance(link_id, bool) or not isinstance(link_id, int) or link_id in link_map:
            raise ValueError(f"UI link {index} has duplicate or invalid id")
        if isinstance(origin, bool) or not isinstance(origin, (str, int)) or isinstance(target, bool) or not isinstance(target, (str, int)):
            raise ValueError(f"UI link {index} endpoints must be integer or string ids")
        origin_id, target_id = str(origin), str(target)
        if origin_id not in nodes or target_id not in nodes:
            raise ValueError(f"UI link {index} references unknown endpoint {origin_id!r}/{target_id!r}")
        if isinstance(origin_slot, bool) or not isinstance(origin_slot, int) or origin_slot < 0 or isinstance(target_slot, bool) or not isinstance(target_slot, int) or target_slot < 0:
            raise ValueError(f"UI link {index} slots must be nonnegative integers")
        link_map[link_id] = (origin_id, origin_slot, target_id, target_slot)

    api: dict[str, Any] = {}
    for node_id, node in nodes.items():
        inputs: dict[str, Any] = {}
        input_provenance: dict[str, str] = {}
        class_type = node.get("type") or node.get("class_type")
        if not isinstance(class_type, str) or not class_type.strip():
            raise ValueError(f"UI node {node_id!r} class_type is required")
        ui_widget_names: list[str] = []
        used_names: set[str] = set()
        raw_input_items = node.get("inputs", [])
        if not isinstance(raw_input_items, list):
            raise ValueError(f"UI node {node_id!r} inputs must be a list")
        for input_index, input_item in enumerate(raw_input_items):
            if input_item is None:
                continue
            if not isinstance(input_item, dict):
                raise ValueError(f"UI node {node_id!r} input entry must be a mapping or null hole")
            name = input_item.get("name")
            link_id = input_item.get("link")
            widget = input_item.get("widget")
            if link_id is None and isinstance(name, str) and isinstance(widget, dict):
                ui_widget_names.append(str(widget.get("name") or name))
            if link_id is not None:
                if isinstance(link_id, bool) or not isinstance(link_id, int) or link_id not in link_map:
                    raise ValueError(f"UI node {node_id!r} input {name!r} references unknown link {link_id!r}")
                _origin_id, _origin_slot, target_id, target_slot = link_map[link_id]
                if target_id != node_id or target_slot != input_item.get("slot_index", input_index):
                    raise ValueError(
                        f"UI node {node_id!r} input {name!r} does not match link {link_id!r} target"
                    )
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
            # LiteGraph's per-input ``widget.name`` roster is direct evidence
            # for the serialized ``widgets_values`` row.  Prefer it whenever
            # it covers the row exactly.  A schema may lead with a custom
            # socket type that the generic literal/socket classifier does not
            # know (for example Tripo's ``MODEL_TASK_ID``); using that broader
            # schema order shifts every literal right and can then drop the
            # first value when it collides with the linked socket.  Partial UI
            # rosters still fall back to schema evidence for compatibility
            # with UI-only controls such as ``control_after_generate``.
            widget_names = (
                ui_widget_names
                if len(ui_widget_names) == len(widgets)
                else _schema_input_names(schema_provider, class_type)
            )
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
            "native_input_names": _native_port_names(node, "inputs"),
            "native_output_names": _native_port_names(node, "outputs"),
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
    ids_diverge = converted_ids != raw_ids

    if ids_diverge:
        raise ValueError(
            "converter_identity_mismatch: converted node ids are not a unique bijection "
            "with source LiteGraph ids; reconciliation action: reopen with matching converter"
        )
    else:
        for node_id, node_data in converted.items():
            if not isinstance(node_data, dict):
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
                node_data.setdefault("_ui", slim)
                node_data["native_input_names"] = _native_port_names(raw_node, "inputs")
                node_data["native_output_names"] = _native_port_names(raw_node, "outputs")
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


def _validate_raw_ui_node_identities(raw: Mapping[str, Any]) -> None:
    """Reject ambiguous LiteGraph node identities before any path converts them."""
    nodes = raw.get("nodes")
    if not isinstance(nodes, list):
        return
    seen: dict[str, int] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            raise ValueError(f"node {index}: must be a mapping with an id")
        if "id" not in node:
            raise ValueError(f"node {index}: id is required")
        node_id = node["id"]
        if isinstance(node_id, bool) or not isinstance(node_id, (int, str)):
            raise ValueError(f"node {index}: id must be an integer or string")
        if isinstance(node_id, str) and not node_id.strip():
            raise ValueError(f"node {index}: id must be a nonblank string")
        class_type = node.get("type", node.get("class_type"))
        if not isinstance(class_type, str) or not class_type.strip():
            raise ValueError(f"node {index}: class_type is required")
        canonical_id = str(node_id)
        prior_index = seen.get(canonical_id)
        if prior_index is not None:
            raise ValueError(
                f"node {index}: duplicate canonical id {canonical_id!r} "
                f"(already used by node {prior_index})"
            )
        seen[canonical_id] = index


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
        native_input_names = entry.get("native_input_names")
        native_output_names = entry.get("native_output_names")
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
            native_input_names=deepcopy(native_input_names),
            native_output_names=deepcopy(native_output_names),
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
    detached = deepcopy(raw)
    _validate_json_semantics(detached, path="envelope")
    workflow = VibeWorkflow.from_envelope(detached)
    report = workflow.validate_identity()
    if not report.ok:
        raise ValueError(report.issues[0].message)
    raw_definitions = detached.get("definitions")
    if raw_definitions is not None:
        workflow.definitions = _normalize_recursive_definitions(raw_definitions)
    if detached.get("interfaces") is not None:
        workflow.interfaces = _normalize_interfaces(detached["interfaces"])
    if detached.get("boundary_ports") is not None:
        workflow.boundary_ports = _normalize_boundary_ports(detached["boundary_ports"])
    if detached.get("virtual_wires") is not None:
        workflow.virtual_wires = _normalize_virtual_wires(detached["virtual_wires"])
    _validate_recursive_contract_metadata(
        workflow.definitions, workflow.interfaces, workflow.boundary_ports
    )
    _capture_import_virtual_wires(workflow)
    _validate_virtual_wire_endpoints(workflow)
    return workflow


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
    if raw_definitions is not None:
        workflow.definitions = _normalize_recursive_definitions(raw_definitions)
        # Retain detached source evidence for the UI door only. Semantic
        # consumers use the typed ``workflow.definitions`` field above.
        workflow.metadata["definitions"] = deepcopy(raw_definitions)
        for definition in workflow.definitions.get("subgraphs", []):
            scope = str(definition["sg_key"])
            if scope not in workflow.interfaces and ("inputs" in definition or "outputs" in definition):
                workflow.interfaces[scope] = {
                    "inputs": [deepcopy(item) for item in definition.get("inputs", []) if isinstance(item, Mapping)],
                    "outputs": [deepcopy(item) for item in definition.get("outputs", []) if isinstance(item, Mapping)],
                }
            definition_ports = []
            for port in definition.get("boundary_ports", []):
                if isinstance(port, Mapping):
                    item = deepcopy(dict(port))
                    item.setdefault("scope_path", scope)
                    definition_ports.append(item)
                else:
                    definition_ports.append(port)
            if definition_ports:
                workflow.boundary_ports.extend(_normalize_boundary_ports(definition_ports))
    if raw.get("interfaces") is not None:
        workflow.interfaces = _normalize_interfaces(raw["interfaces"])
    if raw.get("boundary_ports") is not None:
        workflow.boundary_ports = _normalize_boundary_ports(raw["boundary_ports"])
    if raw.get("virtual_wires") is not None:
        workflow.virtual_wires = _normalize_virtual_wires(raw["virtual_wires"])
    _validate_recursive_contract_metadata(
        workflow.definitions, workflow.interfaces, workflow.boundary_ports
    )
    # Capture authored helper intent before the shared execution projection
    # lowers it. Helpers remain present as ordinary authored nodes.
    _capture_import_virtual_wires(workflow)
    _validate_virtual_wire_endpoints(workflow)
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
    api_workflow = deepcopy(api_workflow)
    _validate_json_semantics(api_workflow, path="api")
    _validate_api_shape(api_workflow)
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
                "native_input_names",
                "native_output_names",
            }
        }
        allowed_metadata = {
            "_ui", "control_after_generate", "flags", "color", "bgcolor",
            "output_names", "output_types", "input_aliases", "schema_source",
            "semantic", "semantic_metadata", "rejected", PROVENANCE_KEY,
            "_meta",
        }
        # ``metadata`` is not an opaque import escape hatch. A caller may use
        # the explicit semantic mapping, but sibling keys are rejected with a
        # stable reconciliation instruction.
        unknown_metadata = sorted(str(key) for key in metadata if key not in allowed_metadata)
        if unknown_metadata:
            supplied_source = metadata.get("schema_source")
            supplied_provider = (
                supplied_source.get("provider", "")
                if isinstance(supplied_source, Mapping)
                else ""
            )
            schema_status = "known" if schema_for(schema_provider, class_type) is not None else (
                "provisional"
                if str(supplied_provider) in {"comfy_registry_provisional", "workflow_json_provisional"}
                else ("known" if str(supplied_provider).strip() else "unknown")
            )
            if schema_status != "unknown":
                key = unknown_metadata[0]
                raise ValueError(
                    f"node {node_id!r} metadata key {key!r} is unclassified; "
                    "reconciliation action: remove it or classify it as semantic/presentation"
                )
            metadata = {key: value for key, value in metadata.items() if key in allowed_metadata}
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
        if not isinstance(metadata.get("schema_source"), Mapping):
            metadata["schema_source"] = deepcopy(schema_source)
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
            native_input_names=deepcopy(node.get("native_input_names")),
            native_output_names=deepcopy(node.get("native_output_names")),
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
    # Keep unresolved schema state actionable at the existing requirements
    # boundary; this is node-local provenance, not a global metadata escape
    # hatch or guessed runtime registry result.
    missing_nodes = set(str(item) for item in workflow.requirements.missing_nodes)
    for node in workflow.nodes.values():
        source = node.metadata.get("schema_source")
        if isinstance(source, Mapping) and not str(source.get("provider", "") or "").strip():
            missing_nodes.add(node.class_type)
    workflow.requirements.missing_nodes = sorted(missing_nodes)
    _capture_import_virtual_wires(workflow)
    _validate_virtual_wire_endpoints(workflow)

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
    from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget

    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return []
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return []
    aliases = [str(name) for name, spec in inputs.items() if input_spec_is_literal_widget(spec)]
    return aliases if aliases else []


def _schema_source_provenance(schema_provider: SchemaProvider | None, class_type: str) -> dict[str, Any] | None:
    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return {
            "provider": "",
            "path": None,
            "cache_path": None,
            "server_url": None,
            "package": None,
            "version": None,
            "hash": None,
            "confidence": 0.0,
        }
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
    use_comfy_converter: bool = False,
    comfy_converter_strict: bool = True,
) -> tuple[VibeWorkflow, dict[str, Any]]:
    """Named door: detect shape once, never mutate caller inputs, retain IR.

    UI list-nodes are deep-copied at the door so caller inputs stay immutable.
    ``{prompt: API}`` unwraps once; the wrapper is retained as snapshot sidecar.
    Envelope/API graphs are converted and re-emitted as canonical UI JSON.
    Unknown shape stays unknown and fails closed.

    The named door is offline by default.  In particular, do not import the
    optional ComfyUI converter while handling agent/executor inspection or
    edit requests: importing it executes ComfyUI node discovery and can pull
    incompatible optional dependencies into an otherwise pure-Python path.
    Callers that explicitly need live converter semantics may opt in with
    ``use_comfy_converter=True``.
    """
    from vibecomfy.porting.emit.ui import emit_ui_json

    if not isinstance(graph, dict):
        raise ValueError("graph must be a mapping")
    shape = detect_workflow_shape(graph)
    if shape == "unknown":
        return _ingest_unknown_shape(graph), graph
    if shape == "ui":
        detached = deepcopy(graph)
        workflow = from_ui(
            detached,
            schema_provider=schema_provider,
            use_comfy_converter=use_comfy_converter,
            comfy_converter_strict=comfy_converter_strict,
        )
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
    api = normalize_to_api(
        detached,
        schema_provider=schema_provider,
        use_comfy_converter=use_comfy_converter,
        comfy_converter_strict=comfy_converter_strict,
    )
    workflow = from_api(api, schema_provider=schema_provider)
    return workflow, emit_ui_json(
        workflow,
        schema_provider=schema_provider,
        guard_original_ui=detached,
    )
