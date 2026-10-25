from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from vibecomfy._compile._widgets import (
    COMPILE_WIDGET_ALIAS_CLASS_TYPES,
    LINK_ONLY_TYPES,
    WIDGET_SCHEMA,
    WIDGET_SEMANTIC_NAMES,
)
from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget
from vibecomfy.schema import schema_for


@dataclass(frozen=True, slots=True)
class WidgetResolution:
    """Result of resolving a positional ``widget_N`` field.

    ``name`` is ``None`` when a schema says the slot is UI-only and should be
    dropped. ``resolved=False`` means the resolver deliberately kept the
    original positional key because no trustworthy schema source named it.
    """

    key: str
    index: int | None
    name: str | None
    source: str
    resolved: bool


def _input_alias_from_schema(schema: Any | None) -> list[str | None]:
    explicit_order = getattr(schema, "widget_input_order", None)
    if isinstance(explicit_order, (list, tuple)) and explicit_order:
        return [str(name) if isinstance(name, str) and name else None for name in explicit_order]
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return []
    return [str(name) for name, spec in inputs.items() if input_spec_is_literal_widget(spec)]


def _schema_from_provider(schema_provider: Any | None, class_type: str) -> Any | None:
    if schema_provider is None:
        return None
    return schema_for(schema_provider, class_type)


def resolve_widget_name_with_provenance(
    class_type: str,
    idx: int,
    *,
    input_aliases: list[str | None] | tuple[str | None, ...] | None = None,
    schema_provider: Any | None = None,
    allow_object_info_fallback: bool = True,
) -> WidgetResolution:
    key = f"widget_{idx}"
    if idx < 0:
        return WidgetResolution(key=key, index=idx, name=key, source="invalid_widget_index", resolved=False)

    # 1. Per-node metadata captured from the source workflow or schema provider.
    if isinstance(input_aliases, (list, tuple)) and 0 <= idx < len(input_aliases):
        return WidgetResolution(key=key, index=idx, name=input_aliases[idx], source="input_aliases", resolved=True)

    # 2. Repo-curated table. This is where known UI-only sentinels live.
    names = WIDGET_SCHEMA.get(class_type)
    if names is not None and 0 <= idx < len(names):
        return WidgetResolution(key=key, index=idx, name=names[idx], source="committed_widget_schema", resolved=True)

    # 3. Explicit semantic patches for classes whose schema is incomplete.
    semantic_names = WIDGET_SEMANTIC_NAMES.get(class_type)
    if semantic_names is not None:
        semantic = semantic_names.get(key)
        if semantic is not None:
            return WidgetResolution(key=key, index=idx, name=semantic, source="semantic_widget_names", resolved=True)

    # 4. Caller-provided schema provider. This may be a captured cache, a
    # runtime /object_info provider, or source-parsed custom-node INPUT_TYPES.
    schema = _schema_from_provider(schema_provider, class_type)
    provider_names = _input_alias_from_schema(schema)
    if 0 <= idx < len(provider_names):
        source = str(getattr(schema, "source_provider", None) or "schema_provider")
        return WidgetResolution(key=key, index=idx, name=provider_names[idx], source=source, resolved=True)

    # 5. Checked-in normalized object_info cache. This is deterministic and
    # offline; use it only after curated/schema-provider evidence misses.
    if allow_object_info_fallback:
        try:
            from vibecomfy.porting.object_info.consume import object_info_widget_order

            object_info_names = object_info_widget_order(class_type)
        except Exception:
            object_info_names = []
        if 0 <= idx < len(object_info_names) and _object_info_position_is_safe(object_info_names, idx):
            return WidgetResolution(key=key, index=idx, name=object_info_names[idx], source="object_info_index", resolved=True)

    # 6. Final fallback: preserve the positional key and make unresolved state
    # explicit. Callers can warn/fail without silently guessing.
    return WidgetResolution(key=key, index=idx, name=key, source="unresolved", resolved=False)


def _object_info_position_is_safe(names: list[str | None], idx: int) -> bool:
    """Return whether an object_info widget position is safe to auto-apply.

    Some Comfy object_info entries include link/hidden sentinels in the widget
    order while UI ``widgets_values`` only contains actual widgets. If a
    sentinel appears before the requested slot, automatic renaming can shift
    every value by one. In that case object_info is still useful as a
    suggestion, but not safe enough for an automatic rewrite.
    """

    if idx >= len(names):
        return False
    if names[idx] is None:
        return False
    return all(name is not None for name in names[:idx])


def resolve_widget_name(class_type: str, idx: int) -> str | None:
    return resolve_widget_name_with_provenance(class_type, idx).name


def widget_names_for_class(class_type: str) -> list[str | None] | None:
    names = WIDGET_SCHEMA.get(class_type)
    return list(names) if names is not None else None


def apply_positional_widget_aliases(
    inputs: dict[str, Any],
    class_type: str,
    *,
    input_aliases: list[str | None] | tuple[str | None, ...] | None = None,
    schema_provider: Any | None = None,
) -> None:
    if class_type not in COMPILE_WIDGET_ALIAS_CLASS_TYPES and not input_aliases and schema_provider is None:
        return
    widget_keys = sorted(
        [key for key in inputs if key.startswith("widget_")],
        key=lambda key: _widget_index(key),
    )
    for widget_key in widget_keys:
        index = _widget_index(widget_key)
        if index < 0:
            continue
        resolution = resolve_widget_name_with_provenance(
            class_type,
            index,
            input_aliases=input_aliases,
            schema_provider=schema_provider,
        )
        if not resolution.resolved:
            continue
        name = resolution.name
        if name is None:
            inputs.pop(widget_key, None)
            continue
        if name not in inputs and widget_key in inputs:
            inputs[name] = inputs[widget_key]
        if name != widget_key:
            inputs.pop(widget_key, None)


def _ui_widget_aliases(node: Mapping[str, Any]) -> list[str]:
    metadata = node.get("metadata")
    ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    raw_inputs = ui.get("inputs") if isinstance(ui, Mapping) else None
    if not isinstance(raw_inputs, list):
        return []
    return [
        str(item["widget"]["name"])
        for item in raw_inputs
        if isinstance(item, Mapping)
        and isinstance(item.get("widget"), Mapping)
        and isinstance(item["widget"].get("name"), str)
        and item["widget"]["name"]
    ]


def promote_positional_widget_aliases(
    node: dict[str, Any],
    class_type: str,
) -> None:
    """Promote only absent positional carriers using source-backed evidence.

    The object-info roster is compact (link-only inputs are already ``None``
    and omitted); UI widget names are independent witness anchors.  A shorter
    roster leaves the remaining positional carriers untouched, preserving
    unresolved holes and their authority.  Existing names are never replaced;
    duplicate positional aliases are rejected instead of guessed through.
    """
    widgets = node.get("widgets")
    inputs = node.get("inputs")
    if not isinstance(widgets, dict) or not isinstance(inputs, dict):
        return
    ui_names = _ui_widget_aliases(node)
    try:
        from vibecomfy.porting.object_info.consume import object_info_widget_value_order

        schema_names = object_info_widget_value_order(class_type)
    except Exception:
        schema_names = []
    if ui_names and schema_names:
        positions = [schema_names.index(name) for name in ui_names if name in schema_names]
        if len(positions) != len(ui_names) or positions != sorted(positions):
            schema_names = []
    names = schema_names or ui_names
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate positional widget aliases for {class_type!r}")
    for key in sorted(widgets, key=_widget_index):
        if not key.startswith("widget_"):
            continue
        index = _widget_index(key)
        if index < 0 or index >= len(names):
            continue
        name = names[index]
        if not isinstance(name, str) or not name or name == key:
            continue
        if name in inputs:
            # An explicitly named carrier owns the value; preserve the
            # unresolved positional carrier instead of guessing through it.
            continue
        if name in widgets:
            raise ValueError(
                f"duplicate positional widget alias {key!r} -> {name!r} for {class_type!r}"
            )
        inputs[name] = widgets.pop(key)


def resolve_widget_key(class_type: str, key: str) -> str | None:
    if not key.startswith("widget_"):
        return key
    try:
        idx = int(key.split("_", 1)[1])
    except ValueError:
        return key
    return resolve_widget_name(class_type, idx)


def resolve_widget_key_with_provenance(
    class_type: str,
    key: str,
    *,
    input_aliases: list[str | None] | tuple[str | None, ...] | None = None,
    schema_provider: Any | None = None,
    allow_object_info_fallback: bool = True,
) -> WidgetResolution:
    if not key.startswith("widget_"):
        return WidgetResolution(key=key, index=None, name=key, source="named_input", resolved=True)
    try:
        idx = int(key.split("_", 1)[1])
    except ValueError:
        return WidgetResolution(key=key, index=None, name=key, source="invalid_widget_key", resolved=False)
    return resolve_widget_name_with_provenance(
        class_type,
        idx,
        input_aliases=input_aliases,
        schema_provider=schema_provider,
        allow_object_info_fallback=allow_object_info_fallback,
    )


def widget_names_from_schema(
    class_type: str,
    schema: Any | None,
    values: Sequence[Any] | None = None,
) -> list[str | None]:
    """Widget names in ``widgets_values`` order.

    With ``values`` (the node's saved widgets_values), a dynamic combo's
    chosen option contributes its own widgets right after the controller,
    as dotted names.  A live schema that has dynamic combos wins over the
    committed table, whose rows predate them (SaveVideo, TextGenerateLTX2Prompt).
    """
    committed = widget_names_for_class(class_type)
    names = _input_alias_from_schema(schema)
    if committed is not None and not _has_dynamic_combo(schema):
        # A committed row that is an exact prefix of the live schema's widget
        # order predates widgets the node has since gained (CreateVideo
        # ["fps"] before bit_depth/color_space/codec).  When the saved row is
        # longer than the committed one, the live schema names the rest.
        if (
            values is not None
            and len(committed) < len(values) <= len(names)
            and list(names[: len(committed)]) == list(committed)
        ):
            return names
        return committed
    if values is None or not _has_dynamic_combo(schema):
        return names
    return expand_dynamic_combo_names(schema, names, values)


def _has_dynamic_combo(schema: Any | None) -> bool:
    inputs = getattr(schema, "inputs", None)
    return isinstance(inputs, Mapping) and any(
        getattr(spec, "dynamic_options", None) for spec in inputs.values()
    )


def expand_dynamic_combo_names(
    schema: Any | None,
    names: Sequence[str | None],
    values: Sequence[Any],
) -> list[str | None]:
    """Splice each dynamic combo's chosen-option widget names after it.

    ComfyUI's frontend stores the option key, then that option's widgets
    (recursively for nested combos), before the node's next widget; the
    API names them ``<controller>.<field>`` (comfy_api finalize_prefix).
    """
    from vibecomfy.schema.provider import DYNAMIC_COMBO_TYPE, _parse_input_spec

    inputs = getattr(schema, "inputs", None)
    inputs = inputs if isinstance(inputs, Mapping) else {}
    out: list[str | None] = []
    position = 0

    def option_names(option_inputs: Any, prefix: str) -> None:
        nonlocal position
        if not isinstance(option_inputs, Mapping):
            return
        for group in ("required", "optional"):
            rows = option_inputs.get(group)
            if not isinstance(rows, Mapping):
                continue
            for sub_name, sub_raw in rows.items():
                full = f"{prefix}{sub_name}"
                spec = _parse_input_spec(sub_raw, required=group == "required", name=full)
                if not input_spec_is_literal_widget(spec):
                    continue
                out.append(full)
                value = values[position] if position < len(values) else None
                position += 1
                attrs = sub_raw[1] if isinstance(sub_raw, (list, tuple)) and len(sub_raw) > 1 else {}
                if isinstance(attrs, Mapping) and attrs.get("control_after_generate"):
                    out.append(f"{prefix}control_after_generate")
                    position += 1
                if spec.type == DYNAMIC_COMBO_TYPE:
                    option_names((spec.dynamic_options or {}).get(value), f"{full}.")

    for name in names:
        out.append(name)
        value = values[position] if position < len(values) else None
        position += 1
        spec = inputs.get(name) if isinstance(name, str) else None
        options = getattr(spec, "dynamic_options", None)
        if options:
            option_names(options.get(value), f"{name}.")
    return out


def unresolved_widget_aliases(
    api_prompt: dict[str, Any] | None,
    *,
    schema_provider: Any | None = None,
) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    if api_prompt is None:
        return unresolved
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        class_type = str(node.get("class_type", ""))
        for input_name in sorted(inputs):
            if not input_name.startswith("widget_"):
                continue
            resolved = resolve_widget_key_with_provenance(
                class_type,
                input_name,
                schema_provider=schema_provider,
            )
            if resolved.resolved:
                continue
            unresolved.append(
                {
                    "node_id": str(node_id),
                    "class_type": class_type,
                    "input": input_name,
                    "source": resolved.source,
                }
            )
    return unresolved


def widget_alias_analysis(
    api_prompt: dict[str, Any] | None,
    *,
    raw_workflow: dict[str, Any] | None = None,
    schema_provider: Any | None = None,
) -> dict[str, Any]:
    unresolved = unresolved_widget_aliases(api_prompt, schema_provider=schema_provider)
    return {
        "unresolved_widget_aliases": unresolved,
        "suggestions": _widget_alias_suggestions(
            api_prompt,
            unresolved,
            raw_workflow=raw_workflow,
            schema_provider=schema_provider,
        ),
    }


def _widget_alias_suggestions(
    api_prompt: dict[str, Any] | None,
    unresolved: list[dict[str, Any]],
    *,
    raw_workflow: dict[str, Any] | None,
    schema_provider: Any | None,
) -> list[dict[str, Any]]:
    if not unresolved:
        return []

    from vibecomfy.ingest.normalize import door_nodes

    raw_ui_nodes = _raw_ui_nodes_by_id(raw_workflow)
    groups: dict[str, dict[str, Any]] = {}
    for alias in unresolved:
        class_type = str(alias["class_type"])
        node_id = str(alias["node_id"])
        node = api_prompt.get(node_id, {}) if isinstance(api_prompt, dict) else {}
        widget_values = _widget_values_for_node(node_id, node, raw_ui_nodes)
        observed_count = max(_widget_index(alias["input"]) + 1, len(widget_values))
        group = groups.setdefault(
            class_type,
            {
                "class_type": class_type,
                "nodes": {},
                "observed_widget_count": 0,
                "schema_source": "unavailable",
                "suggested_schema_entry": None,
            },
        )
        group["observed_widget_count"] = max(group["observed_widget_count"], observed_count)
        node_entry = door_nodes(group).setdefault(
            node_id,
            {
                "node_id": node_id,
                "unresolved_inputs": [],
                "widgets_values": widget_values,
            },
        )
        node_entry["unresolved_inputs"].append(alias["input"])

    for class_type, group in groups.items():
        source, names = _schema_entry_for_class(class_type, schema_provider)
        group["schema_source"] = source
        if names is not None:
            suggested = list(names)
            if group["observed_widget_count"] > len(suggested):
                suggested.extend([None] * (group["observed_widget_count"] - len(suggested)))
            group["suggested_schema_entry"] = suggested
            group["python"] = _format_widget_schema_entry(class_type, suggested)
        group["nodes"] = [door_nodes(group)[node_id] for node_id in sorted(door_nodes(group), key=_sort_key)]

    return [groups[class_type] for class_type in sorted(groups)]


def _schema_entry_for_class(class_type: str, schema_provider: Any | None) -> tuple[str, list[str | None] | None]:
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return "committed_widget_schema", committed
    schema = _schema_from_provider(schema_provider, class_type)
    names = _input_alias_from_schema(schema)
    if names:
        source = str(getattr(schema, "source_provider", None) or "schema_provider")
        return ("schema_provider" if source == "unknown" else source), names
    try:
        from vibecomfy.porting.object_info.consume import object_info_widget_order

        object_info_names = object_info_widget_order(class_type)
    except Exception:
        object_info_names = []
    if object_info_names:
        return "object_info_index", object_info_names
    return "unavailable", None


def _raw_ui_nodes_by_id(raw_workflow: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_workflow, dict):
        return {}
    from vibecomfy.ingest.normalize import door_get_nodes

    raw = raw_workflow.get("prompt") if isinstance(raw_workflow.get("prompt"), dict) else raw_workflow
    nodes = door_get_nodes(raw) if isinstance(raw, dict) else None
    if not isinstance(nodes, list):
        return {}
    return {str(node["id"]): node for node in nodes if isinstance(node, dict) and "id" in node}


def _widget_values_for_node(node_id: str, api_node: Any, raw_ui_nodes: dict[str, dict[str, Any]]) -> list[Any]:
    raw_ui = raw_ui_nodes.get(node_id)
    if raw_ui is None and isinstance(api_node, dict) and isinstance(api_node.get("_ui"), dict):
        raw_ui = api_node["_ui"]
    from vibecomfy.ingest.normalize import door_get_widgets_values, door_widgets_values

    if isinstance(raw_ui, dict) and isinstance(door_get_widgets_values(raw_ui), list):
        return list(door_widgets_values(raw_ui))
    if not isinstance(api_node, dict) or not isinstance(api_node.get("inputs"), dict):
        return []
    values: list[Any] = []
    for key, value in api_node["inputs"].items():
        if not key.startswith("widget_"):
            continue
        idx = _widget_index(key)
        if idx < 0:
            continue
        while len(values) <= idx:
            values.append(None)
        values[idx] = value
    return values


def _widget_index(input_name: str) -> int:
    if not input_name.startswith("widget_"):
        return -1
    try:
        return int(input_name.split("_", 1)[1])
    except ValueError:
        return -1


def _format_widget_schema_entry(class_type: str, names: list[str | None]) -> str:
    rendered = ", ".join("None" if name is None else repr(name) for name in names)
    return f"{class_type!r}: [{rendered}]"


def _sort_key(value: Any) -> tuple[int, str]:
    try:
        return (int(value), str(value))
    except (TypeError, ValueError):
        return (10**12, str(value))


__all__ = [
    "COMPILE_WIDGET_ALIAS_CLASS_TYPES",
    "LINK_ONLY_TYPES",
    "apply_positional_widget_aliases",
    "resolve_widget_key",
    "resolve_widget_key_with_provenance",
    "resolve_widget_name",
    "resolve_widget_name_with_provenance",
    "widget_alias_analysis",
    "WidgetResolution",
    "unresolved_widget_aliases",
    "widget_names_for_class",
    "widget_names_from_schema",
]
