from __future__ import annotations

from collections.abc import Mapping
from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Literal

from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget
from vibecomfy._compile._widgets import WIDGET_SCHEMA, WIDGET_SEMANTIC_NAMES


from vibecomfy.ingest.normalize import door_get_widgets_values
@dataclass(frozen=True, slots=True)
class WidgetNameResolution:
    names: tuple[str | None, ...]
    source: str
    complete: bool
    aligned_to: Literal["compact_widgets_values"] = "compact_widgets_values"
    warnings: tuple[str, ...] = ()


_WIDGET_KEY_RE = re.compile(r"widget_(\d+)")
# Law 5 (batch 4): positional widget_N/slot_N aliases are never emitted and
# carry no resolver — an unnameable widget is addressed by its named field
# or fails loudly as widget_unknown, never by a positional shim.
_MISSING_WIDGET_VALUE = object()
_CONTROL_AFTER_GENERATE_VALUES = {"fixed", "randomize", "increment", "decrement"}
_PRIMITIVE_CONTROL_WIDGET_CLASSES = {"PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt"}


def compact_widget_names_for_node(
    node: Mapping[str, Any] | Any,
    class_type: str | None = None,
    *,
    value_count: int | None = None,
    schema_provider: Any | None = None,
    allow_object_info_fallback: bool = True,
) -> WidgetNameResolution:
    """Return names aligned 1:1 to compact ``widgets_values`` positions."""

    class_type = class_type or _node_class_type(node)
    count = _compact_value_count(node, value_count)
    if count is None:
        count = 0

    for source, names in _candidate_name_sources(
        node,
        class_type,
        count,
        schema_provider=schema_provider,
        allow_object_info_fallback=allow_object_info_fallback,
    ):
        if not names:
            continue
        return _align_names(names, count, source)

    return _align_names([], count, "unresolved")


def widget_index_for_field(
    node: Mapping[str, Any] | Any,
    field_name: str,
    *,
    schema_provider: Any | None = None,
) -> int | None:
    count = _compact_value_count(node, None)
    match = _WIDGET_KEY_RE.fullmatch(field_name)
    if match is not None:
        index = int(match.group(1))
        if count is None or 0 <= index < count:
            resolution = compact_widget_names_for_node(node, schema_provider=schema_provider)
            if _is_leading_null_padded_placeholder(node, resolution, index):
                return None
            return index
        return None

    resolution = compact_widget_names_for_node(node, schema_provider=schema_provider)
    duplicates = {
        name
        for name, total in Counter(name for name in resolution.names if name).items()
        if total > 1
    }
    if field_name in duplicates:
        return None
    for index, name in enumerate(resolution.names):
        if name == field_name:
            return index
    return None


def widget_value_for_field(
    node: Mapping[str, Any] | Any,
    field_name: str,
    *,
    schema_provider: Any | None = None,
) -> Any:
    values = _compact_values(node)
    if isinstance(values, Mapping):
        return values[field_name] if field_name in values else _MISSING_WIDGET_VALUE
    if isinstance(values, list):
        index = widget_index_for_field(node, field_name, schema_provider=schema_provider)
        if index is not None and 0 <= index < len(values):
            return values[index]
    return _MISSING_WIDGET_VALUE


def missing_widget_value_sentinel() -> object:
    return _MISSING_WIDGET_VALUE


def _candidate_name_sources(
    node: Mapping[str, Any] | Any,
    class_type: str,
    value_count: int,
    *,
    schema_provider: Any | None,
    allow_object_info_fallback: bool,
) -> list[tuple[str, list[str | None]]]:
    sources: list[tuple[str, list[str | None]]] = []

    metadata = _metadata(node)
    aliases = metadata.get("input_aliases")
    if isinstance(aliases, (list, tuple)):
        sources.append(("metadata.input_aliases", _coerce_names(aliases)))

    ui_names = _ui_widget_names(metadata.get("_ui"))
    if ui_names:
        sources.append(("_ui.widgets", ui_names))

    ui_aliases = _ui_widget_aliases_covering_compact_keys(node, value_count)
    if ui_aliases:
        sources.append(("_ui.inputs[].widget", ui_aliases))

    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        sources.append(("committed_widget_schema", _name_ui_control_slots(node, class_type, list(curated))))

    semantic_names = _semantic_names_for_count(class_type, value_count)
    if semantic_names:
        sources.append(("semantic_widget_names", semantic_names))

    if not _object_info_entry_is_workflow_stub(class_type):
        provider_names = _provider_compact_aliases(schema_provider, class_type)
        if provider_names:
            padded = _leading_null_padded_names(node, provider_names, value_count)
            if padded:
                sources.append(("schema_provider_leading_null_padding", padded))
            sources.append(("schema_provider", provider_names))

        if allow_object_info_fallback:
            try:
                from vibecomfy.porting.object_info.consume import object_info_widget_value_order  # noqa: PLC0415

                object_info_names = object_info_widget_value_order(class_type)
            except Exception:
                object_info_names = []
            if object_info_names:
                object_info_names = _name_ui_control_slots(node, class_type, list(object_info_names))
                padded = _leading_null_padded_names(node, list(object_info_names), value_count)
                if padded:
                    sources.append(("object_info_widget_value_order_leading_null_padding", padded))
                sources.append(("object_info_widget_value_order", list(object_info_names)))

    return sources


def _name_ui_control_slots(
    node: Mapping[str, Any] | Any,
    class_type: str,
    names: list[str | None],
) -> list[str | None]:
    values = _compact_values(node)
    if not isinstance(values, (list, Mapping)):
        return names
    out = list(names)
    if isinstance(values, list):
        value_count = len(values)
    else:
        indices = _widget_indices(values)
        value_count = max(indices) + 1 if indices else len(values)
    if value_count > len(out):
        out.extend([None] * (value_count - len(out)))
    for index, name in enumerate(out):
        if name is not None:
            continue
        if isinstance(values, list):
            if index >= len(values):
                continue
            value = values[index]
        else:
            key = f"widget_{index}"
            if key not in values:
                continue
            value = values[key]
        if not (isinstance(value, str) and value in _CONTROL_AFTER_GENERATE_VALUES):
            continue
        previous = out[index - 1] if index > 0 else None
        if previous in {"seed", "noise_seed", "value"} or (
            class_type in _PRIMITIVE_CONTROL_WIDGET_CLASSES and index == 1
        ):
            out[index] = "control_after_generate"
    return out


def _leading_null_padded_names(
    node: Mapping[str, Any] | Any,
    names: list[str | None],
    value_count: int,
) -> list[str | None]:
    values = _compact_values(node)
    if not isinstance(values, list):
        return []
    prefix_count = value_count - len(names)
    if prefix_count <= 0:
        return []
    if prefix_count >= value_count:
        return []
    if any(values[index] is not None for index in range(prefix_count)):
        return []
    return [None] * prefix_count + list(names)


def _is_leading_null_padded_placeholder(
    node: Mapping[str, Any] | Any,
    resolution: WidgetNameResolution,
    index: int,
) -> bool:
    if not resolution.source.endswith("_leading_null_padding"):
        return False
    values = _compact_values(node)
    if not isinstance(values, list) or not 0 <= index < len(values):
        return False
    if values[index] is not None:
        return False
    if index >= len(resolution.names):
        return False
    return resolution.names[index] == f"widget_{index}"


def _align_names(
    names: list[str | None],
    value_count: int,
    source: str,
) -> WidgetNameResolution:
    warnings: list[str] = []
    if len(names) < value_count:
        warnings.append(f"{source}: fewer names ({len(names)}) than compact values ({value_count})")
    elif len(names) > value_count:
        warnings.append(f"{source}: more names ({len(names)}) than compact values ({value_count}); truncated")

    aligned: list[str | None] = []
    for index in range(value_count):
        name = names[index] if index < len(names) else None
        aligned.append(str(name) if isinstance(name, str) and name else f"widget_{index}")

    duplicates = sorted(
        name
        for name, total in Counter(name for name in aligned if isinstance(name, str)).items()
        if total > 1
    )
    if duplicates:
        warnings.append(f"{source}: duplicate widget names require explicit widget_N addressing: {duplicates}")
        duplicate_set = set(duplicates)
        aligned = [
            f"widget_{index}" if name in duplicate_set else name
            for index, name in enumerate(aligned)
        ]

    complete = not warnings and all(
        isinstance(name, str) and not name.startswith("widget_")
        for name in aligned
    )
    return WidgetNameResolution(
        names=tuple(aligned),
        source=source if names else "unresolved",
        complete=complete,
        warnings=tuple(warnings),
    )


def _node_class_type(node: Mapping[str, Any] | Any) -> str:
    if isinstance(node, Mapping):
        return str(node.get("type") or node.get("class_type") or "")
    return str(getattr(node, "class_type", "") or getattr(node, "type", "") or "")


def _metadata(node: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    metadata = node.get("metadata") if isinstance(node, Mapping) else getattr(node, "metadata", None)
    return metadata if isinstance(metadata, Mapping) else {}


def _compact_values(node: Mapping[str, Any] | Any) -> Any:
    if isinstance(node, Mapping):
        values = door_get_widgets_values(node)
        if isinstance(values, (list, Mapping)):
            return values
        widgets = node.get("widgets")
        if isinstance(widgets, Mapping):
            widget_indices = _widget_indices(widgets)
            if widget_indices and widget_indices == list(range(max(widget_indices) + 1)):
                return [widgets[f"widget_{index}"] for index in widget_indices]
            if widgets:
                return widgets
        raw_widgets = node.get("raw_widgets") or node.get("_raw_widgets")
        if isinstance(raw_widgets, Mapping):
            values = raw_widgets.get("values")
            if isinstance(values, list):
                return values
        metadata = node.get("metadata")
    else:
        metadata = getattr(node, "metadata", None)
        widgets = getattr(node, "widgets", None)
        if isinstance(widgets, Mapping):
            widget_indices = _widget_indices(widgets)
            if widget_indices and widget_indices == list(range(max(widget_indices) + 1)):
                return [widgets[f"widget_{index}"] for index in widget_indices]
            if widgets:
                return widgets
        raw_widgets = getattr(node, "raw_widgets", None)
        values = getattr(raw_widgets, "values", None)
        if isinstance(values, list):
            return values
    if isinstance(metadata, Mapping):
        ui = metadata.get("_ui")
        if isinstance(ui, Mapping):
            values = door_get_widgets_values(ui)
            if isinstance(values, list):
                return values
    return None


def _compact_value_count(node: Mapping[str, Any] | Any, value_count: int | None) -> int | None:
    if value_count is not None:
        return max(0, value_count)
    values = _compact_values(node)
    if isinstance(values, list):
        return len(values)
    if isinstance(values, Mapping):
        indices = _widget_indices(values)
        if indices:
            return max(indices) + 1
        return len(values)

    widgets = getattr(node, "widgets", None)
    if isinstance(widgets, Mapping):
        indices = _widget_indices(widgets)
        if indices:
            return max(indices) + 1
    return None


def _widget_indices(values: Mapping[Any, Any]) -> list[int]:
    indices: list[int] = []
    for key in values:
        match = _WIDGET_KEY_RE.fullmatch(str(key))
        if match is not None:
            indices.append(int(match.group(1)))
    return sorted(indices)


def _ui_widget_names(ui: Any) -> list[str | None]:
    if not isinstance(ui, Mapping):
        return []
    widget_names = ui.get("widget_names")
    if isinstance(widget_names, (list, tuple)):
        return _coerce_names(widget_names)
    widgets = ui.get("widgets")
    if isinstance(widgets, (list, tuple)):
        names: list[str | None] = []
        for item in widgets:
            if isinstance(item, Mapping):
                names.append(_coerce_name(item.get("name")))
            else:
                names.append(_coerce_name(item))
        return names
    return []


def _ui_widget_aliases_covering_compact_keys(
    node: Mapping[str, Any] | Any,
    value_count: int,
) -> list[str | None]:
    metadata = _metadata(node)
    ui = metadata.get("_ui")
    if isinstance(ui, Mapping):
        inputs = ui.get("inputs")
    elif isinstance(node, Mapping):
        inputs = node.get("inputs")
    else:
        inputs = None
    if not isinstance(inputs, list):
        return []
    aliases: list[str | None] = []
    for item in inputs:
        if not isinstance(item, Mapping):
            continue
        if item.get("link") is not None:
            # A linked widget-converted socket is a graph edge, not a compact
            # widgets_values position: its widget name must never claim a slot.
            continue
        widget = item.get("widget")
        if not isinstance(widget, Mapping):
            continue
        aliases.append(_coerce_name(widget.get("name")))
    if not aliases:
        return []
    if len(aliases) != value_count:
        return []
    indices = _observed_widget_key_indices(node)
    if indices and len(aliases) <= max(indices):
        return []
    return aliases


def _observed_widget_key_indices(node: Mapping[str, Any] | Any) -> list[int]:
    pools: list[Mapping[Any, Any]] = []
    if isinstance(node, Mapping):
        for key in ("widgets", "inputs"):
            value = node.get(key)
            if isinstance(value, Mapping):
                pools.append(value)
    else:
        for key in ("widgets", "inputs"):
            value = getattr(node, key, None)
            if isinstance(value, Mapping):
                pools.append(value)
    indices: list[int] = []
    for pool in pools:
        indices.extend(_widget_indices(pool))
    return sorted(set(indices))


def _semantic_names_for_count(class_type: str, value_count: int) -> list[str | None]:
    semantic = WIDGET_SEMANTIC_NAMES.get(class_type)
    if not semantic:
        return []
    names: list[str | None] = [None] * value_count
    for key, name in semantic.items():
        match = _WIDGET_KEY_RE.fullmatch(str(key))
        if match is None:
            continue
        index = int(match.group(1))
        if 0 <= index < value_count:
            names[index] = str(name)
    return names if any(name is not None for name in names) else []


def _provider_compact_aliases(schema_provider: Any | None, class_type: str) -> list[str | None]:
    schema = _schema_from_provider(schema_provider, class_type)
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, Mapping):
        return []
    names: list[str | None] = []
    for name, spec in inputs.items():
        if not _provider_input_spec_is_widget_value(spec):
            continue
        names.append(str(name))
    return names


def _provider_input_spec_is_widget_value(spec: Any) -> bool:
    return input_spec_is_literal_widget(spec)


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


def _object_info_entry_is_workflow_stub(class_type: str) -> bool:
    try:
        from vibecomfy.porting.object_info.consume import get_class  # noqa: PLC0415

        entry = get_class(class_type)
    except Exception:
        entry = None
    if not isinstance(entry, Mapping):
        return False
    source_kind = str(entry.get("source_kind") or "")
    category = str(entry.get("category") or "")
    pack_version = str(entry.get("pack_version") or "")
    return source_kind == "workflow_json_stub" or category.endswith("/stub") or pack_version == "stub"


def _coerce_names(values: list[Any] | tuple[Any, ...]) -> list[str | None]:
    return [_coerce_name(value) for value in values]


def _coerce_name(value: Any) -> str | None:
    return str(value) if isinstance(value, str) and value else None


__all__ = [
    "WidgetNameResolution",
    "compact_widget_names_for_node",
    "missing_widget_value_sentinel",
    "widget_index_for_field",
    "widget_value_for_field",
]
