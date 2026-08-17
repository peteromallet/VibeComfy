from __future__ import annotations

from dataclasses import dataclass
from math import inf
import re
from typing import Any, Mapping

from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget
from vibecomfy.porting.resolution import _normalize_type
from vibecomfy.porting.widgets.aliases import widget_names_for_class
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node
from vibecomfy.porting.widgets.settings_contract import node_settings_for
from vibecomfy.schema import socket_types_compatible


from vibecomfy.ingest.door_access import door_get_nodes, door_get_widgets_values
_WIDGET_KEY_RE = re.compile(r"widget_(\d+)$")


@dataclass(frozen=True, slots=True)
class AddFieldResolution:
    field_name: str
    known: bool


def resolve_set_node_field_alias(
    node: Mapping[str, Any],
    class_type: str,
    field_name: str,
    schema_inputs: Mapping[str, Any],
    *,
    schema_provider: Any | None,
) -> str:
    """Resolve a semantic field alias to the schema's canonical field when useful."""

    if field_name in schema_inputs:
        return field_name

    aliases = _semantic_aliases_for_node(
        node,
        class_type,
        schema_inputs,
        schema_provider,
    )
    widget_to_alias = _widget_to_alias(aliases)
    semantic_for_widget = widget_to_alias.get(field_name)
    if semantic_for_widget is not None and semantic_for_widget in schema_inputs:
        return semantic_for_widget

    target = aliases.get(field_name)
    if target is not None and target in schema_inputs:
        return target
    return field_name


def resolve_add_node_field_alias(
    class_type: str,
    field_name: str,
    schema_inputs: Mapping[str, Any],
    *,
    schema_provider: Any | None,
) -> AddFieldResolution:
    """Resolve add_node author-facing aliases against widget_N or semantic schemas."""

    if field_name in schema_inputs:
        return AddFieldResolution(field_name=field_name, known=True)

    aliases = _semantic_aliases_for_class(class_type, schema_inputs, schema_provider)
    widget_to_alias = _widget_to_alias(aliases)
    semantic_for_widget = widget_to_alias.get(field_name)
    if semantic_for_widget is not None:
        if semantic_for_widget in schema_inputs:
            return AddFieldResolution(field_name=semantic_for_widget, known=True)
        return AddFieldResolution(field_name=field_name, known=True)

    target = aliases.get(field_name)
    if target is None:
        return AddFieldResolution(field_name=field_name, known=False)
    if target in schema_inputs:
        return AddFieldResolution(field_name=target, known=True)
    return AddFieldResolution(field_name=field_name, known=True)


def field_diagnostics_for_node(
    node: Mapping[str, Any],
    class_type: str,
    schema_inputs: Mapping[str, Any],
    *,
    schema_provider: Any | None,
) -> dict[str, Any]:
    aliases = _semantic_aliases_for_node(node, class_type, schema_inputs, schema_provider)

    # ── compact field names from the shared settings helper ──────────────
    compact_names: list[str] = []
    try:
        settings_info = node_settings_for(node, class_type, schema_provider=schema_provider)
        compact_names = [f.name for f in settings_info.fields if f.name]
    except Exception:
        pass

    # ── determine which widget indices are covered by semantic names ────
    covered_indices: set[int] = set()
    for i, name in enumerate(compact_names):
        if name and not _is_widget_key(name):
            covered_indices.add(i)

    valid_fields: list[str] = []

    # 1. Compact (semantic) field names first.
    valid_fields.extend(compact_names)

    # 2. Socket input names.
    valid_fields.extend(_node_input_names(node))

    # 3. Schema-input names not already present (e.g. socket-only fields).
    for name in schema_inputs:
        s = str(name)
        if s not in valid_fields:
            valid_fields.append(s)

    # 4. Raw widget_N keys *only* for slots that do not have a semantic name.
    for key in _node_widget_keys(node):
        if key in valid_fields:
            continue  # already present via schema_inputs
        match = _WIDGET_KEY_RE.fullmatch(key)
        if match is not None and int(match.group(1)) in covered_indices:
            continue  # covered by a compact semantic name
        valid_fields.append(key)

    # 5. Aliases (preserve existing semantic and compatibility aliases).
    valid_fields.extend(aliases)
    for alias_target in aliases.values():
        # Omit alias targets that are covered widget_N (the semantic name
        # already appears in valid_fields via compact names).
        if _is_widget_key(alias_target):
            match = _WIDGET_KEY_RE.fullmatch(alias_target)
            if match is not None and int(match.group(1)) in covered_indices:
                continue
        valid_fields.append(alias_target)

    return _diagnostic_payload(valid_fields, aliases)


def field_diagnostics_for_class(
    class_type: str,
    schema_inputs: Mapping[str, Any],
    *,
    schema_provider: Any | None,
) -> dict[str, Any]:
    aliases = _semantic_aliases_for_class(class_type, schema_inputs, schema_provider)

    # ── determine which widget indices are covered by semantic names ────
    covered_indices: set[int] = set()
    for names in _known_compact_widget_name_sources(class_type, schema_inputs, schema_provider):
        for i, name in enumerate(names):
            if name and not _is_widget_key(str(name)):
                covered_indices.add(i)

    # Also cover indices where a non-widget-key alias maps to a widget_N target.
    for alias_name, target in aliases.items():
        if not _is_widget_key(alias_name) and _is_widget_key(target):
            match = _WIDGET_KEY_RE.fullmatch(target)
            if match is not None:
                covered_indices.add(int(match.group(1)))

    valid_fields: list[str] = []

    # 1. Schema-input names.
    valid_fields.extend(str(name) for name in schema_inputs)

    # 2. Widget keys, skipping those covered by semantic names.
    for key in _known_widget_keys_for_class(class_type, schema_inputs, schema_provider):
        if key in valid_fields:
            continue  # already present via schema_inputs
        match = _WIDGET_KEY_RE.fullmatch(key)
        if match is not None and int(match.group(1)) in covered_indices:
            continue  # covered by a semantic name
        valid_fields.append(key)

    # 3. Aliases (preserve existing semantic and compatibility aliases).
    valid_fields.extend(aliases)
    for alias_target in aliases.values():
        if _is_widget_key(alias_target):
            match = _WIDGET_KEY_RE.fullmatch(alias_target)
            if match is not None and int(match.group(1)) in covered_indices:
                continue
        valid_fields.append(alias_target)

    return _diagnostic_payload(valid_fields, aliases)


def format_valid_field_hint(detail: Mapping[str, Any]) -> str:
    valid_fields = _string_list(detail.get("valid_fields"))
    semantic_aliases = _alias_items(detail.get("semantic_aliases"))
    parts: list[str] = []
    if valid_fields:
        parts.append(f"Valid fields: {_format_values(valid_fields)}.")
    if semantic_aliases:
        parts.append(f"Semantic aliases: {_format_alias_items(semantic_aliases)}.")
    return " ".join(parts)


def socket_source_hint(
    graph: Mapping[str, Any],
    input_type: Any,
    *,
    target_node: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    normalized_type = _normalize_type(input_type)
    sources = compatible_source_hints(graph, normalized_type, target_node=target_node)
    if normalized_type:
        message = (
            f"Use a source node/wire producing {normalized_type} via add_node inputs or upsert_link."
        )
    else:
        message = "Use a source node/wire via add_node inputs or upsert_link."
    if sources:
        message += f" Compatible sources in this scope include {_format_values(sources)}."
    detail: dict[str, Any] = {"input_type": normalized_type or input_type}
    if sources:
        detail["compatible_source_classes"] = list(sources)
    return message, detail


def compatible_source_hints(
    graph: Mapping[str, Any],
    input_type: Any,
    *,
    target_node: Mapping[str, Any] | None = None,
    limit: int = 5,
) -> tuple[str, ...]:
    nodes = door_get_nodes(graph)
    if not isinstance(nodes, list):
        return ()
    target_id = target_node.get("id") if isinstance(target_node, Mapping) else None
    target_pos = _node_pos(target_node)
    candidates: list[tuple[float, int, str]] = []
    seen: set[str] = set()
    for order, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            continue
        if target_id is not None and node.get("id") == target_id:
            continue
        class_type = str(node.get("type") or node.get("class_type") or "")
        if not class_type:
            continue
        outputs = node.get("outputs")
        if not isinstance(outputs, list):
            continue
        for output_index, output in enumerate(outputs):
            if not isinstance(output, Mapping):
                continue
            output_type = _normalize_type(output.get("type"))
            if input_type and output_type and not socket_types_compatible(output_type, input_type):
                continue
            slot_name = output.get("name")
            label = f"{class_type}.{slot_name if isinstance(slot_name, str) and slot_name else output_index}"
            if output_type:
                label = f"{label} ({output_type})"
            if label in seen:
                continue
            seen.add(label)
            candidates.append((_distance(target_pos, _node_pos(node)), order, label))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return tuple(label for _, _, label in candidates[:limit])


def _semantic_aliases_for_node(
    node: Mapping[str, Any],
    class_type: str,
    schema_inputs: Mapping[str, Any],
    schema_provider: Any | None,
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    resolution = compact_widget_names_for_node(node, class_type, schema_provider=schema_provider)
    for index, name in enumerate(resolution.names):
        if not isinstance(name, str) or not name or _is_widget_key(name):
            continue
        target = name if name in schema_inputs else f"widget_{index}"
        aliases.setdefault(name, target)
    for alias, target in _semantic_aliases_for_class(class_type, schema_inputs, schema_provider).items():
        aliases.setdefault(alias, target)
    return aliases


def _semantic_aliases_for_class(
    class_type: str,
    schema_inputs: Mapping[str, Any],
    schema_provider: Any | None,
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for names in _known_compact_widget_name_sources(class_type, schema_inputs, schema_provider):
        for index, name in enumerate(names):
            if not isinstance(name, str) or not name or _is_widget_key(name):
                continue
            widget_key = f"widget_{index}"
            if name in schema_inputs:
                target = name
            elif widget_key in schema_inputs:
                target = widget_key
            else:
                target = name
            aliases.setdefault(name, target)
    return aliases


def _known_compact_widget_name_sources(
    class_type: str,
    schema_inputs: Mapping[str, Any],
    schema_provider: Any | None,
) -> list[list[str | None]]:
    sources: list[list[str | None]] = []
    committed = widget_names_for_class(class_type)
    if committed:
        sources.append(list(committed))

    provider_names = [
        str(name)
        for name, spec in schema_inputs.items()
        if input_spec_is_literal_widget(spec)
    ]
    if provider_names:
        sources.append(provider_names)

    provider = _schema_from_provider(schema_provider, class_type)
    provider_inputs = getattr(provider, "inputs", None)
    if isinstance(provider_inputs, Mapping) and provider_inputs is not schema_inputs:
        names = [
            str(name)
            for name, spec in provider_inputs.items()
            if input_spec_is_literal_widget(spec)
        ]
        if names:
            sources.append(names)

    try:
        from vibecomfy.porting.object_info.consume import object_info_widget_value_order  # noqa: PLC0415

        object_info_names = object_info_widget_value_order(class_type)
    except Exception:
        object_info_names = []
    if object_info_names:
        sources.append(list(object_info_names))
    return sources


def _known_widget_keys_for_class(
    class_type: str,
    schema_inputs: Mapping[str, Any],
    schema_provider: Any | None,
) -> list[str]:
    count = 0
    for names in _known_compact_widget_name_sources(class_type, schema_inputs, schema_provider):
        count = max(count, len(names))
    for name in schema_inputs:
        match = _WIDGET_KEY_RE.fullmatch(str(name))
        if match is not None:
            count = max(count, int(match.group(1)) + 1)
    return [f"widget_{index}" for index in range(count)]


def _diagnostic_payload(valid_fields: list[str], aliases: Mapping[str, str]) -> dict[str, Any]:
    compact_aliases = {
        str(alias): str(target)
        for alias, target in aliases.items()
        if alias and target and alias != target
    }
    return {
        "valid_fields": _dedupe_sorted(valid_fields),
        "semantic_aliases": dict(sorted(compact_aliases.items())),
    }


def _node_input_names(node: Mapping[str, Any]) -> list[str]:
    inputs = node.get("inputs")
    if not isinstance(inputs, list):
        return []
    names: list[str] = []
    for item in inputs:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _node_widget_keys(node: Mapping[str, Any]) -> list[str]:
    widgets_values = door_get_widgets_values(node)
    if isinstance(widgets_values, list):
        return [f"widget_{index}" for index in range(len(widgets_values))]
    if isinstance(widgets_values, Mapping):
        return [str(name) for name in widgets_values]
    return []


def _widget_to_alias(aliases: Mapping[str, str]) -> dict[str, str]:
    return {
        target: alias
        for alias, target in aliases.items()
        if _is_widget_key(target)
    }


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


def _is_widget_key(value: str) -> bool:
    return _WIDGET_KEY_RE.fullmatch(value) is not None


def _dedupe_sorted(values: list[str]) -> list[str]:
    return sorted({value for value in values if isinstance(value, str) and value})


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _alias_items(value: Any) -> list[tuple[str, str]]:
    if not isinstance(value, Mapping):
        return []
    items: list[tuple[str, str]] = []
    for key, target in value.items():
        if isinstance(key, str) and isinstance(target, str) and key and target:
            items.append((key, target))
    return sorted(items)


def _format_values(values: list[str] | tuple[str, ...], *, limit: int = 8) -> str:
    shown = list(values[:limit])
    rendered = ", ".join(repr(value) for value in shown)
    if len(values) > limit:
        rendered += f", ... (+{len(values) - limit} more)"
    return rendered


def _format_alias_items(items: list[tuple[str, str]], *, limit: int = 8) -> str:
    shown = items[:limit]
    rendered = ", ".join(f"{alias!r} -> {target!r}" for alias, target in shown)
    if len(items) > limit:
        rendered += f", ... (+{len(items) - limit} more)"
    return rendered


def _node_pos(node: Mapping[str, Any] | None) -> tuple[float, float] | None:
    if not isinstance(node, Mapping):
        return None
    pos = node.get("pos")
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        return None
    try:
        return (float(pos[0]), float(pos[1]))
    except (TypeError, ValueError):
        return None


def _distance(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if a is None or b is None:
        return inf
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


__all__ = [
    "AddFieldResolution",
    "field_diagnostics_for_class",
    "field_diagnostics_for_node",
    "format_valid_field_hint",
    "resolve_add_node_field_alias",
    "resolve_set_node_field_alias",
    "socket_source_hint",
]
