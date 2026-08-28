from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Literal

from vibecomfy.porting.authoring_surface import input_spec_is_literal_widget
from vibecomfy._compile._widgets import WIDGET_SCHEMA, WIDGET_SEMANTIC_NAMES


from vibecomfy.ingest.normalize import door_get_widgets_values

def _is_positional_widget_name(name: str | None) -> bool:
    if not isinstance(name, str) or not name:
        return False
    return bool(_WIDGET_KEY_RE.fullmatch(name))
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
# Batch-review RR2: roster-shape law.  ``metadata.input_aliases`` lists
# connection sockets INTERLEAVED with literal widgets in full input order,
# so a linked entry must be deleted (compact ``widgets_values`` holds
# literals only).  Every other candidate source is already a compact
# widget-only roster where deleting would shift later literals; there a
# linked entry becomes an unresolved positional hole instead.
_FULL_INPUT_ORDER_SOURCES = frozenset({"metadata.input_aliases"})



_FIELD_SNAPSHOT_SOURCE = "field_snapshot"


def _frozen_authority_names(
    node: Mapping[str, Any] | Any,
    name_authority: Mapping[str, Sequence[str | None]] | None,
) -> Sequence[str | None] | None:
    """Frozen per-uid names from the sealed ``WorkflowSnapshot`` table (R3).

    A hit is the sole name authority: ambient sources (metadata aliases,
    object_info, live providers) are never consulted for that node again.
    """
    if not isinstance(name_authority, Mapping) or not name_authority:
        return None
    uid = getattr(node, "uid", None)
    if not uid and isinstance(node, Mapping):
        uid = node.get("uid")
    if not uid:
        return None
    names = name_authority.get(str(uid))
    if names is None:
        return None
    return tuple(names)


def _iter_input_slots(node: Mapping[str, Any] | Any) -> list[tuple[str, Any]]:
    """Yield (name, payload) pairs for the node's input slots, both shapes."""
    inputs = getattr(node, "inputs", None)
    if isinstance(node, Mapping) and not isinstance(inputs, (Mapping, list)):
        inputs = node.get("inputs")
    slots: list[tuple[str, Any]] = []
    if isinstance(inputs, Mapping):
        slots.extend((str(name), value) for name, value in inputs.items())
    elif isinstance(inputs, list):
        for slot in inputs:
            if isinstance(slot, Mapping) and slot.get("name"):
                slots.append((str(slot["name"]), slot))
    metadata = _metadata(node)
    ui = metadata.get("_ui") if isinstance(metadata, Mapping) else None
    ui_inputs = ui.get("inputs") if isinstance(ui, Mapping) else None
    if isinstance(ui_inputs, list):
        for slot in ui_inputs:
            if isinstance(slot, Mapping) and slot.get("name"):
                slots.append((str(slot["name"]), slot))
    return slots


def _resolved_linked_input_names(
    node: Mapping[str, Any] | Any,
    linked_inputs: Collection[str] | None,
) -> frozenset[str]:
    """Union explicit caller evidence with the node's own link state (R1)."""
    linked = {str(name) for name in linked_inputs or ()}
    for name, payload in _iter_input_slots(node):
        if isinstance(payload, Mapping):
            # Litegraph/UI stub shape: a non-null link id means connected.
            if payload.get("link") is not None:
                linked.add(name)
        elif isinstance(payload, (list, tuple)) and len(payload) >= 2:
            # Retained IR / API shape: a [source_id, slot] pair is a link.
            linked.add(name)
    return frozenset(linked)


def _exclude_linked(
    names: list[str | None],
    linked: frozenset[str],
    *,
    full_input_order: bool,
) -> list[str | None]:
    """Compact linked sockets out of a candidate roster (R1, RR1-FIX-1).

    A full-input-order source (``metadata.input_aliases``) interleaves
    connection sockets with literal widgets, while compact ``widgets_values``
    holds literal widgets only. Dropping the linked entries — rather than
    nulling them in place — removes the positional holes BEFORE
    ``_align_names`` maps names onto compact slots, so a leading custom-typed
    socket can no longer shift every widget name right and truncate the tail.

    Batch-review RR2: an ALREADY-COMPACT widget roster (every other source)
    must NOT shrink. Deleting a linked entry there shifts every following
    literal left, so linking KSampler ``seed`` resolved position 0 as
    ``control_after_generate`` instead of the required ``widget_0`` hole.
    In a compact roster a linked entry becomes an unresolved positional
    placeholder (``None`` → honest ``widget_N`` addressing) and subsequent
    literals keep their positions.

    Unlinked socket-typed names cannot be distinguished from widgets here;
    they stay in the roster and the resulting ambiguity is rejected
    downstream (live/replay table equality + candidate-byte equality),
    never guessed.
    """
    if not linked:
        return names
    if full_input_order:
        return [
            name for name in names
            if not (isinstance(name, str) and name in linked)
        ]
    return [
        None if isinstance(name, str) and name in linked else name
        for name in names
    ]


def compact_widget_names_for_node(
    node: Mapping[str, Any] | Any,
    class_type: str | None = None,
    *,
    value_count: int | None = None,
    schema_provider: Any | None = None,
    allow_object_info_fallback: bool = True,
    name_authority: Mapping[str, Sequence[str | None]] | None = None,
    linked_inputs: Collection[str] | None = None,
) -> WidgetNameResolution:
    """Return names aligned 1:1 to compact ``widgets_values`` positions.

    P0-WIDGET-CANON:
    * ``name_authority`` — the frozen per-uid name table sealed onto
      ``WorkflowSnapshot.field_snapshot``.  A hit short-circuits every
      ambient source: the sealed table is the sole name authority.
    * ``linked_inputs`` — input names carried by a graph connection.  A
      linked socket never qualifies as a compact-widget name source (R1);
      its slot falls back to honest positional ``widget_N`` addressing.
    """

    class_type = class_type or _node_class_type(node)
    count = _compact_value_count(node, value_count)
    if count is None:
        count = 0

    authority_names = _frozen_authority_names(node, name_authority)
    if authority_names is not None:
        # S2 named-field emit: a frozen table that is all positional
        # ``widget_N`` placeholders carries no semantic names.  Treat it as
        # absent so the live schema provider / WIDGET_SCHEMA can supply
        # real field names.  A table containing at least one real name
        # remains authoritative (P0-WIDGET-CANON).
        has_named = any(
            isinstance(name, str) and name and not _is_positional_widget_name(name)
            for name in authority_names
        )
        if has_named:
            return _align_names(list(authority_names), count, _FIELD_SNAPSHOT_SOURCE)
        # All widget_N / None — fall through to live providers.

    linked = _resolved_linked_input_names(node, linked_inputs)
    for source, names in _candidate_name_sources(
        node,
        class_type,
        count,
        schema_provider=schema_provider,
        allow_object_info_fallback=allow_object_info_fallback,
    ):
        if not names:
            continue
        prepared = _name_ui_control_slots(
            node,
            class_type,
            _exclude_linked(
                names,
                linked,
                full_input_order=source in _FULL_INPUT_ORDER_SOURCES,
            ),
        )
        return _align_names(prepared, count, source)

    return _align_names([], count, "unresolved")


def widget_index_for_field(
    node: Mapping[str, Any] | Any,
    field_name: str,
    *,
    schema_provider: Any | None = None,
    name_authority: Mapping[str, Sequence[str | None]] | None = None,
) -> int | None:
    count = _compact_value_count(node, None)
    match = _WIDGET_KEY_RE.fullmatch(field_name)
    if match is not None:
        index = int(match.group(1))
        if count is None or 0 <= index < count:
            resolution = compact_widget_names_for_node(
                node, schema_provider=schema_provider, name_authority=name_authority
            )
            if _is_leading_null_padded_placeholder(node, resolution, index):
                return None
            return index
        return None

    resolution = compact_widget_names_for_node(
        node, schema_provider=schema_provider, name_authority=name_authority
    )
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
    name_authority: Mapping[str, Sequence[str | None]] | None = None,
) -> Any:
    values = _compact_values(node)
    if isinstance(values, Mapping):
        return values[field_name] if field_name in values else _MISSING_WIDGET_VALUE
    if isinstance(values, list):
        index = widget_index_for_field(
            node, field_name, schema_provider=schema_provider, name_authority=name_authority
        )
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

    # RR1-FIX-1: an explicit runtime-captured widget-slot order (serialized
    # through the schema snapshot) is exact evidence — literal widgets in UI
    # ``widgets_values`` order, sockets already excluded. It outranks
    # ``metadata.input_aliases``, which interleaves socket names with widget
    # names and can only be repaired heuristically by linked-hole compaction.
    explicit_order = _schema_explicit_widget_order(schema_provider, class_type)
    if explicit_order:
        sources.append(("schema_explicit_widget_order", list(explicit_order)))

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
    # Insert BEFORE tail-padding. Padding first made len(out)==len(values)
    # and hid the missing control slot as a trailing widget_N.
    if (
        isinstance(values, list)
        and "control_after_generate" not in out
        and len(values) == len(out) + 1
    ):
        insert_at = None
        for index, name in enumerate(out):
            if name in {"seed", "noise_seed", "value"}:
                insert_at = index + 1
                break
        if insert_at is None and class_type in _PRIMITIVE_CONTROL_WIDGET_CLASSES:
            insert_at = 1 if out else 0
        if insert_at is not None and insert_at < len(values):
            value = values[insert_at]
            if isinstance(value, str) and value in _CONTROL_AFTER_GENERATE_VALUES:
                out.insert(insert_at, "control_after_generate")
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


def _schema_explicit_widget_order(
    schema_provider: Any | None,
    class_type: str,
) -> tuple[str | None, ...]:
    """Return the schema's explicit literal-widget slot order (RR1-FIX-1).

    Non-empty only when the resolved schema carries runtime-captured evidence
    of which ordered inputs occupy ``widgets_values`` slots. Never guessed:
    providers that do not expose the split yield ``()`` and resolution falls
    through to the ambient sources.
    """
    schema = _schema_from_provider(schema_provider, class_type)
    order = getattr(schema, "widget_input_order", None) if schema is not None else None
    if isinstance(order, (tuple, list)) and order:
        return tuple(name if isinstance(name, str) else None for name in order)
    return ()


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
