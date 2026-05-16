from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibecomfy.metadata import (
    OUTPUT_NODE_NAMES,
    _infer_requirements,
    _register_common_inputs,
)
from vibecomfy.porting.widget_aliases import widget_names_from_schema
from vibecomfy.workflow import VibeEdge, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource

if TYPE_CHECKING:
    # `vibecomfy.schema.provider` top-imports the runtime; importing it
    # eagerly here breaks the cheap-import contract for `vibecomfy.testing`.
    # `SchemaProvider` is annotation-only, and the runtime callables
    # (`OutputSpec`, `schema_for`) are imported lazily inside the helpers
    # below.
    from vibecomfy.schema import OutputSpec, SchemaProvider  # noqa: F401


def _schema_for(provider, class_type):
    """Lazy proxy for `vibecomfy.schema.schema_for`."""
    from vibecomfy.schema import schema_for as _impl  # noqa: PLC0415

    return _impl(provider, class_type)


def _output_spec_cls():
    """Lazy accessor for the `OutputSpec` class."""
    from vibecomfy.schema import OutputSpec as _OutputSpec  # noqa: PLC0415

    return _OutputSpec


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
) -> dict[str, Any]:
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
                pass
            else:
                if not _has_unknown_widget_inputs(converted):
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
        for input_item in node.get("inputs", []) or []:
            if not isinstance(input_item, dict):
                continue
            name = input_item.get("name")
            link_id = input_item.get("link")
            if name and link_id in link_map:
                inputs[name] = [link_map[link_id][0], link_map[link_id][1]]
        widgets = node.get("widgets_values", [])
        if isinstance(widgets, dict):
            for name, value in widgets.items():
                if name in inputs:
                    continue
                inputs[str(name)] = value
        elif isinstance(widgets, list):
            widget_names = _schema_input_names(schema_provider, class_type)
            for idx, value in enumerate(widgets):
                name = widget_names[idx] if idx < len(widget_names) else f"widget_{idx}"
                if name in inputs:
                    continue
                inputs[name] = value
        api[node_id] = {"class_type": class_type, "inputs": inputs, "_ui": node}
    return api


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
            if _is_link(value):
                continue
            if key.startswith("widget_"):
                widgets[key] = value
            else:
                inputs[key] = value
        class_type = str(node.get("class_type", "Unknown"))
        metadata = {key: value for key, value in node.items() if key not in {"class_type", "inputs"}}
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
        workflow.nodes[str(node_id)] = VibeNode(
            id=str(node_id),
            class_type=class_type,
            inputs=inputs,
            widgets=widgets,
            metadata=metadata,
        )
        _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
        if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
            workflow.outputs.append(VibeOutput(node_id=str(node_id), output_type=workflow.nodes[str(node_id)].class_type))
    workflow.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))

    for node_id, node in api_workflow.items():
        if not isinstance(node, dict):
            continue
        for name, value in dict(node.get("inputs", {})).items():
            if _is_link(value):
                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))

    workflow.requirements = _infer_requirements(workflow)
    return workflow


def _is_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and str(value[0]).isdigit()


def _schema_input_names(schema_provider: SchemaProvider | None, class_type: str) -> list[str]:
    schema = _schema_for(schema_provider, class_type)
    return [name for name in widget_names_from_schema(class_type, schema) if name is not None]


def _schema_output_names(schema_provider: SchemaProvider | None, class_type: str) -> list[str]:
    """Return output names from schema, preserving blank entries for partial evidence.

    The emitter will decide per-slot safety later (e.g. blank/duplicate names
    fall back to numeric ``.out(n)``).  Never drop the whole list just because
    one entry is missing.
    """
    schema = _schema_for(schema_provider, class_type)
    outputs = getattr(schema, "outputs", None) or []
    OutputSpec = _output_spec_cls()
    names: list[str] = []
    for output in outputs:
        name = output.name if isinstance(output, OutputSpec) else getattr(output, "name", None)
        names.append(name if isinstance(name, str) else "")
    return names


def _schema_output_types(schema_provider: SchemaProvider | None, class_type: str) -> list[str]:
    schema = _schema_for(schema_provider, class_type)
    outputs = getattr(schema, "outputs", None) or []
    OutputSpec = _output_spec_cls()
    types: list[str] = []
    for output in outputs:
        typ = output.type if isinstance(output, OutputSpec) else getattr(output, "type", None)
        types.append(typ if isinstance(typ, str) else "")
    return types


def _schema_input_aliases(schema_provider: SchemaProvider | None, class_type: str) -> list[str | None]:
    """Build input aliases from schema, excluding link-only types so widget positions do not shift."""
    from vibecomfy.porting.widget_aliases import LINK_ONLY_TYPES

    schema = _schema_for(schema_provider, class_type)
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
    schema = _schema_for(schema_provider, class_type)
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
