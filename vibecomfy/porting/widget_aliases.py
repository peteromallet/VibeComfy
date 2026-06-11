from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vibecomfy._compile._widgets import (
    COMPILE_WIDGET_ALIAS_CLASS_TYPES,
    LINK_ONLY_TYPES,
    WIDGET_SCHEMA,
    WIDGET_SEMANTIC_NAMES,
)


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
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return []
    names: list[str | None] = []
    for name, spec in inputs.items():
        input_type = str(getattr(spec, "type", "") or "").upper()
        if input_type in LINK_ONLY_TYPES:
            continue
        names.append(str(name))
    return names


def _schema_from_provider(schema_provider: Any | None, class_type: str) -> Any | None:
    if schema_provider is None:
        return None
    getter = getattr(schema_provider, "get_schema", None) or getattr(schema_provider, "get", None)
    if not callable(getter):
        return None
    try:
        return getter(class_type)
    except Exception:
        return None


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


def widget_names_from_schema(class_type: str, schema: Any | None) -> list[str | None]:
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return committed
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return []
    names: list[str | None] = []
    for name, spec in inputs.items():
        input_type = str(getattr(spec, "type", "") or "").upper()
        if input_type in LINK_ONLY_TYPES:
            continue
        names.append(str(name))
    return names


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
        node_entry = group["nodes"].setdefault(
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
        group["nodes"] = [group["nodes"][node_id] for node_id in sorted(group["nodes"], key=_sort_key)]

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
    raw = raw_workflow.get("prompt") if isinstance(raw_workflow.get("prompt"), dict) else raw_workflow
    nodes = raw.get("nodes") if isinstance(raw, dict) else None
    if not isinstance(nodes, list):
        return {}
    return {str(node["id"]): node for node in nodes if isinstance(node, dict) and "id" in node}


def _widget_values_for_node(node_id: str, api_node: Any, raw_ui_nodes: dict[str, dict[str, Any]]) -> list[Any]:
    raw_ui = raw_ui_nodes.get(node_id)
    if raw_ui is None and isinstance(api_node, dict) and isinstance(api_node.get("_ui"), dict):
        raw_ui = api_node["_ui"]
    if isinstance(raw_ui, dict) and isinstance(raw_ui.get("widgets_values"), list):
        return list(raw_ui["widgets_values"])
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
