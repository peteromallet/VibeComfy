from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import warnings

from vibecomfy._compile._graph import is_api_link
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
    RawWidgetPayload,
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    VibeWorkflow,
    WorkflowRequirements,
    WorkflowSource,
)

EXEC_SOURCE_MAX_BYTES = 48 * 1024
EXEC_SOURCE_MAX_TOTAL_BYTES = 768 * 1024


def detect_workflow_shape(raw: dict[str, Any]) -> str:
    if "prompt" in raw and isinstance(raw["prompt"], dict):
        return detect_workflow_shape(raw["prompt"])
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
                    stacklevel=2,
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
                    stacklevel=2,
                )
            else:
                _enforce_exec_source_limits(converted, surface="ui.converter")
                if not _has_unknown_widget_inputs(converted):
                    _merge_slim_ui(raw, converted)
                    return converted
                return _normalize_ui_to_api(raw, schema_provider=schema_provider)

    return _normalize_ui_to_api(raw, schema_provider=schema_provider)


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
        class_type = str(node.get("type", "Unknown"))
        ui_widget_names: list[str] = []
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

    workflow = VibeWorkflow(
        id=workflow_id,
        source=source,
        requirements=requirements,
        metadata=deepcopy(metadata_raw) if isinstance(metadata_raw, dict) else {},
        strict_types=strict_types,
    )

    # ── nodes ──────────────────────────────────────────────────────────────
    for key, entry in nodes_raw.items():
        node_id = entry.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"node {key!r}: id must be a nonblank string")
        if str(key) != node_id:
            raise ValueError(f"node mapping key {key!r} must equal node.id {node_id!r}")
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
        workflow.nodes[node_id] = VibeNode(
            id=node_id,
            class_type=class_type,
            pack=pack,
            inputs=deepcopy(entry["inputs"]),
            widgets=deepcopy(entry["widgets"]),
            metadata=node_metadata,
            uid=uid,
            raw_widgets=raw_widget_payload,
        )

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
        if edge["from_node"] not in workflow.nodes or edge["to_node"] not in workflow.nodes:
            raise ValueError(
                f"edge {index}: endpoint node ids {edge['from_node']!r}/{edge['to_node']!r} "
                "must exist in nodes"
            )
        workflow.edges.append(
            VibeEdge(
                from_node=edge["from_node"],
                from_output=edge["from_output"],
                to_node=edge["to_node"],
                to_input=edge["to_input"],
            )
        )

    # ── top-level inputs / outputs ─────────────────────────────────────────
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

    return workflow


def convert_to_vibe_format(
    api_workflow: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
) -> VibeWorkflow:
    with untrusted_scope():
        return _convert_to_vibe_format_impl(
            api_workflow,
            source_path=source_path,
            workflow_id=workflow_id,
            schema_provider=schema_provider,
        )


def _convert_to_vibe_format_impl(
    api_workflow: dict[str, Any],
    *,
    source_path: str | None = None,
    workflow_id: str | None = None,
    schema_provider: SchemaProvider | None = None,
) -> VibeWorkflow:
    """Ingest a raw workflow dict (api/ui/vibe shapes) into a ``VibeWorkflow``.

    Serialized rich Vibe envelopes (shape ``"vibe"``) are decoded directly and
    losslessly by :meth:`VibeWorkflow.from_envelope` — the rich ``nodes``
    mapping is the only authority for which nodes exist.  API and UI shapes
    keep the existing compile-path ingest (``normalize_to_api`` → node
    extraction).
    """
    if detect_workflow_shape(api_workflow) == "vibe":
        # Serialized rich Vibe envelope: decode it directly and losslessly. The
        # rich ``nodes`` mapping is the only authority for which nodes exist;
        # ``compiled_api`` (and the api-derived path below) is never consulted
        # for the rich node set.
        return VibeWorkflow.from_envelope(api_workflow)
    if detect_workflow_shape(api_workflow) != "api":
        api_workflow = normalize_to_api(
            api_workflow,
            schema_provider=schema_provider,
            comfy_converter_strict=True,
        )
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
            if input_provenance.get(key) != "widget" and is_api_link(
                value,
                allow_tuple=False,
                require_string_node_id=False,
                require_numeric_node_id=True,
                require_int_slot=False,
            ):
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
        # ── retain mode/flags/color/bgcolor from _ui into top-level metadata ──
        # Both paths: pure-Python path stores the full raw node in _ui (line 99);
        # comfy-converter path stores a slim _ui enriched by _merge_slim_ui.
        # Captured as metadata DATA only — never enters inputs/widgets (K3 invariant).
        _ui_raw = metadata.get("_ui")
        if isinstance(_ui_raw, dict):
            # The _ui dict is a shallow alias of the input API node's _ui
            # (pure-Python path); deepcopy before mutating so the caller's
            # node dict is never corrupted by the mode pop below.
            # Only assign when a real _ui was present — do not invent {}.
            _ui_node = deepcopy(_ui_raw)
            metadata["_ui"] = _ui_node
            for _vis_field in ("mode", "flags", "color", "bgcolor"):
                if _vis_field in _ui_node:
                    metadata.setdefault(_vis_field, _ui_node[_vis_field])
            # Ingest furniture mode is NOT the compile mute/bypass signal — live
            # _ui.mode set on the IR node is (workflow._get_node_mode). Pop the
            # furniture copy so a captured mode can never trip compile bypass/mute;
            # metadata['mode'] (copied above) still feeds the emitter's furniture.
            _ui_node.pop("mode", None)
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
            if input_provenance.get(name) != "widget" and is_api_link(
                value,
                allow_tuple=False,
                require_string_node_id=False,
                require_numeric_node_id=True,
                require_int_slot=False,
            ):
                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))

    workflow.requirements = _infer_requirements(workflow)

    # Stash an ingest-time snapshot immediately after uid minting and edge setup.
    # Captured once here so downstream delta computation can detect edits.
    from vibecomfy.ingest.snapshot import capture_ingest_snapshot  # local to avoid circular at module level
    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(api_workflow, workflow)

    # ``workflow.metadata`` is ``dict[str, Any]`` and transparently accepts
    # any extra keys.  In particular, ``summary`` (a ``WorkflowSummary`` dict)
    # may be present when re-ingesting a corpus JSON that was enriched with
    # LLM-generated summaries.  It is left untouched here — no validation,
    # no stripping — so it survives round-trips through this pipeline intact.
    return workflow


def _is_exec_widget_key(class_type: str, key: str) -> bool:
    return class_type == EXEC_CLASS_TYPE and key in {"source", "io"}


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

    Looks in two places, both available at ``convert_to_vibe_format`` time and both
    examined BEFORE the ``_schema_input_names`` None-strip (:185) can discard the
    value during ``_normalize_ui_to_api``:

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
