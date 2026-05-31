from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import warnings

from vibecomfy._graph_utils import is_api_link
from vibecomfy.metadata import (
    OUTPUT_NODE_NAMES,
    _infer_requirements,
    _register_common_inputs,
)
from vibecomfy.porting.uid import make_uid, mint_local_uid
from vibecomfy.porting.widget_aliases import widget_names_for_class, widget_names_from_schema
from vibecomfy.schema import OutputSpec, SchemaProvider, schema_for
from vibecomfy.security.gate import untrusted_scope
from vibecomfy.security.provenance import PROVENANCE_KEY
from vibecomfy.workflow import RawWidgetPayload, VibeEdge, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource


def detect_workflow_shape(raw: dict[str, Any]) -> str:
    if "prompt" in raw and isinstance(raw["prompt"], dict):
        return detect_workflow_shape(raw["prompt"])
    if isinstance(raw.get("nodes"), list):
        return "ui"
    if raw and all(isinstance(value, dict) and "class_type" in value for value in raw.values()):
        return "api"
    return "unknown"


def normalize_to_api(
    raw: dict[str, Any],
    *,
    schema_provider: SchemaProvider | None = None,
    use_comfy_converter: bool = True,
    comfy_converter_strict: bool = False,
) -> dict[str, Any]:
    """Convert a raw workflow dict (UI or API shape) to ComfyUI API format.

    ``comfy_converter_strict`` is only meaningful when ``use_comfy_converter=True``
    AND the comfy package is importable.  When ``True``, any exception raised by
    ``convert_ui_to_api`` propagates instead of silently falling back to the
    offline converter.  When ``use_comfy_converter=False``, ``comfy_converter_strict``
    is a no-op — the comfy converter is never attempted.  The offline default
    (``comfy_converter_strict=False``) preserves the existing tolerant fallback.
    """
    shape = detect_workflow_shape(raw)
    if shape == "api":
        return raw.get("prompt", raw)
    if shape != "ui":
        raise ValueError(f"Unsupported workflow shape: {shape}")

    if use_comfy_converter:
        try:
            from comfy.component_model.workflow_convert import convert_ui_to_api
        except ImportError:
            pass
        else:
            try:
                converted = convert_ui_to_api(raw)
            except Exception:
                if comfy_converter_strict:
                    raise
            else:
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
        widgets_present = "widgets_values" in node
        widgets = node.get("widgets_values", [])
        if isinstance(widgets, dict):
            for name, value in widgets.items():
                if name in inputs:
                    continue
                inputs[str(name)] = value
        elif isinstance(widgets, list):
            widget_names = _schema_input_names(schema_provider, class_type)
            for idx, value in enumerate(widgets):
                if idx < len(widget_names):
                    name = widget_names[idx]
                elif idx < len(ui_widget_names):
                    name = ui_widget_names[idx]
                else:
                    name = f"widget_{idx}"
                if name in inputs:
                    continue
                inputs[name] = value
        api_node = {"class_type": class_type, "inputs": inputs, "_ui": node}
        if widgets_present:
            api_node["_raw_widgets"] = _raw_widget_payload_dict(widgets, source="ui.widgets_values")
        api[node_id] = api_node
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
    if detect_workflow_shape(api_workflow) != "api":
        api_workflow = normalize_to_api(api_workflow, schema_provider=schema_provider)
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
        inputs: dict[str, Any] = {}
        widgets: dict[str, Any] = {}
        for key, value in raw_inputs.items():
            if is_api_link(
                value,
                allow_tuple=False,
                require_string_node_id=False,
                require_numeric_node_id=True,
                require_int_slot=False,
            ):
                continue
            if key.startswith("widget_"):
                widgets[key] = value
            else:
                inputs[key] = value
        class_type = str(node.get("class_type", "Unknown"))
        raw_widgets = _coerce_raw_widget_payload(node.get("_raw_widgets"))
        if raw_widgets is None:
            raw_ui = node.get("_ui")
            if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
                raw_widgets = _coerce_raw_widget_payload(
                    _raw_widget_payload_dict(raw_ui["widgets_values"], source="ui.widgets_values")
                )
        metadata = {key: value for key, value in node.items() if key not in {"class_type", "inputs", "_raw_widgets"}}
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
        _ui_node = metadata.get("_ui") or {}
        for _vis_field in ("mode", "flags", "color", "bgcolor"):
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
        for name, value in dict(node.get("inputs", {})).items():
            if is_api_link(
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

    return workflow


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
    from vibecomfy.porting.widget_aliases import LINK_ONLY_TYPES

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
