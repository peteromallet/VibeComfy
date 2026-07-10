"""Read-only structured helper for editable node fields.

Returns compact widget field metadata (names, slot indexes, types, enum
choices, numeric bounds, output slots) without any prompt text formatting.
Prompt assembly stays in ``edit_batch_memory.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vibecomfy._compile._widgets import WIDGET_SCHEMA
from vibecomfy.porting.widgets.compact_resolver import (
    WidgetNameResolution,
    compact_widget_names_for_node,
)

# ── structured field info ────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class NodeFieldInfo:
    """Structured metadata for a single editable widget field on a node.

    Every field maps to a ``widgets_values`` slot.  UI-only controls (like
    ``control_after_generate``) are included with ``ui_only=True`` so consumers
    can decide whether to expose them.
    """

    name: str
    """Compact widget name, e.g. ``seed``, ``steps``, ``control_after_generate``."""

    slot_index: int
    """Zero-based index into ``widgets_values``."""

    kind: str
    """Field kind: ``int``, ``float``, ``string``, ``bool``, ``enum``, or ``unknown``."""

    default: Any = None
    """Default value from the schema, if available."""

    min_value: int | float | None = None
    """Numeric lower bound (inclusive), if available."""

    max_value: int | float | None = None
    """Numeric upper bound (inclusive), if available."""

    choices: tuple[str, ...] | None = None
    """Ordered enum choice labels, if this is a COMBO/ENUM kind."""

    ui_only: bool = False
    """True when the slot does not correspond to a named schema input
    (e.g. ``control_after_generate`` on KSampler)."""

    aliases: tuple[str, ...] = ()
    """Alternative names for this field, if any."""


# ── aggregate settings info ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class NodeSettingsInfo:
    """Structured settings contract for a single node.

    This is the read-only data contract shared between prompt assembly and
    engine diagnostics.  It carries no prompt formatting — that stays in
    ``edit_batch_memory.py``.
    """

    class_type: str
    """ComfyUI class type, e.g. ``KSampler``."""

    fields: tuple[NodeFieldInfo, ...]
    """Ordered editable fields (aligned to ``widgets_values`` positions)."""

    output_slots: tuple[str, ...]
    """Output slot names, if any."""

    source: str
    """Resolution source, e.g. ``committed_widget_schema``."""


# ── helpers ──────────────────────────────────────────────────────────────────

_CONTROL_AFTER_GENERATE_VALUES: frozenset[str] = frozenset(
    {"fixed", "randomize", "increment", "decrement"}
)

_SEED_WIDGET_NAMES: frozenset[str] = frozenset({"seed", "noise_seed", "value"})


def _infer_kind(input_type: str | None) -> str:
    """Map a schema input type string to a compact field kind."""
    if input_type is None:
        return "unknown"
    t = input_type.upper()
    if t in {"INT", "INTEGER"}:
        return "int"
    if t in {"FLOAT", "DOUBLE"}:
        return "float"
    if t in {"STRING", "STR", "TEXT"}:
        return "string"
    if t in {"BOOLEAN", "BOOL"}:
        return "bool"
    if t in {"COMBO", "ENUM"}:
        return "enum"
    return "unknown"


def _coerce_choices(raw: list[Any] | tuple[Any, ...] | None) -> tuple[str, ...] | None:
    """Normalise choice labels into a deterministic tuple of strings."""
    if raw is None:
        return None
    result: list[str] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            result.append(str(item[0]))
        elif isinstance(item, (list, tuple)):
            continue
        else:
            result.append(str(item))
    return tuple(result) if result else None


def _output_names_for_class(class_type: str) -> tuple[str, ...]:
    """Return cached output slot names for known class types."""
    try:
        from vibecomfy.porting.object_info.consume import get_class
    except ImportError:
        return ()
    try:
        entry = get_class(class_type)
    except Exception:
        return ()
    if not isinstance(entry, Mapping):
        return ()
    outputs = entry.get("outputs")
    if not isinstance(outputs, list):
        return ()
    names: list[str] = []
    for out in outputs:
        if isinstance(out, Mapping):
            name = out.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        elif isinstance(out, str):
            names.append(out)
    return tuple(names)


def _resolve_ui_only_fields(
    names: list[str | None],
    class_type: str,
    raw_names: list[str | None],
) -> list[str | None]:
    """Annotate UI-only slots that are not in the schema but are known controls.

    Mirrors the logic in ``compact_resolver._name_ui_control_slots`` but works
    on the already-resolved names from ``compact_widget_names_for_node``.
    """
    out = list(names)
    for index, name in enumerate(out):
        if name is not None and not name.startswith("widget_"):
            continue
        # Check if this slot looks like a control_after_generate widget.
        if index > 0 and out[index - 1] in _SEED_WIDGET_NAMES:
            # At this point we don't have the value — the consumer can set
            # kind="enum" / choices when it has the value.  We'll mark it with
            # the name so structured consumers see it.
            if name is None or name.startswith("widget_"):
                out[index] = "control_after_generate"
    return out


def _build_field(
    name: str | None,
    index: int,
    raw_name: str | None,
    schema_inputs: Mapping[str, Any] | None,
    class_type: str,
) -> NodeFieldInfo:
    """Build a single ``NodeFieldInfo`` from available evidence."""
    display_name = str(name) if isinstance(name, str) and name else f"widget_{index}"
    ui_only = name is None or (isinstance(raw_name, str) and raw_name is None)

    # ── schema evidence ────────────────────────────────────────────────
    input_spec = None
    if isinstance(schema_inputs, Mapping) and isinstance(name, str) and name:
        input_spec = schema_inputs.get(name)

    # Determine kind and enrich from spec.
    kind = "unknown"
    default: Any = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    choices: tuple[str, ...] | None = None
    aliases: tuple[str, ...] = ()

    if input_spec is not None:
        spec_type = getattr(input_spec, "type", None)
        kind = _infer_kind(str(spec_type) if spec_type else None)
        default = getattr(input_spec, "default", None)
        raw_min = getattr(input_spec, "min", None)
        raw_max = getattr(input_spec, "max", None)
        if isinstance(raw_min, (int, float)):
            min_value = raw_min
        if isinstance(raw_max, (int, float)):
            max_value = raw_max
        raw_choices = getattr(input_spec, "choices", None)
        if isinstance(raw_choices, (list, tuple)):
            choices = _coerce_choices(raw_choices)
            if choices and kind == "unknown":
                kind = "enum"

    # Handle control_after_generate UI-only slots.
    if display_name == "control_after_generate":
        ui_only = True
        kind = "enum"
        choices = tuple(sorted(_CONTROL_AFTER_GENERATE_VALUES))
        default = "fixed"

    return NodeFieldInfo(
        name=display_name,
        slot_index=index,
        kind=kind,
        default=default,
        min_value=min_value,
        max_value=max_value,
        choices=choices,
        ui_only=ui_only,
        aliases=aliases,
    )


# ── public API ───────────────────────────────────────────────────────────────


def node_settings_for(
    node: Mapping[str, Any] | Any,
    class_type: str | None = None,
    *,
    schema_provider: Any | None = None,
) -> NodeSettingsInfo:
    """Return structured editable-field info for a node.

    Uses ``compact_widget_names_for_node`` for field name resolution, then
    enriches each field with schema-input metadata (type, bounds, choices,
    default) where available.
    """
    ct = class_type or _node_class_type(node)

    # ── 1. Resolve compact widget names ──────────────────────────────────
    resolution: WidgetNameResolution = compact_widget_names_for_node(
        node,
        ct,
        schema_provider=schema_provider,
    )

    # ── 2. Get curated raw schema names (for ui_only detection) ─────────
    raw_names = WIDGET_SCHEMA.get(ct)

    # ── 3. Resolve UI-only field names ──────────────────────────────────
    resolved = list(resolution.names)
    resolved = _resolve_ui_only_fields(resolved, ct, list(raw_names) if raw_names else [])

    # ── 4. Get node schema for input specs ──────────────────────────────
    schema_inputs: Mapping[str, Any] | None = None
    try:
        if schema_provider is not None:
            schema = _schema_from_provider(schema_provider, ct)
        else:
            from vibecomfy.schema import get_authoring_schema_provider

            schema = get_authoring_schema_provider().get_schema(ct)
    except Exception:
        schema = None
    if schema is not None:
        schema_inputs = getattr(schema, "inputs", None)

    # ── 5. Build field info ─────────────────────────────────────────────
    fields: list[NodeFieldInfo] = []
    for index, name in enumerate(resolved):
        raw_name_at = raw_names[index] if raw_names and 0 <= index < len(raw_names) else None
        fields.append(_build_field(name, index, raw_name_at, schema_inputs, ct))

    # ── 6. Output slots ─────────────────────────────────────────────────
    output_slots = _output_names_for_class(ct)

    return NodeSettingsInfo(
        class_type=ct,
        fields=tuple(fields),
        output_slots=output_slots,
        source=resolution.source,
    )


def compact_field_names_for_node(
    node: Mapping[str, Any] | Any,
    class_type: str | None = None,
    *,
    schema_provider: Any | None = None,
) -> tuple[str, ...]:
    """Return the ordered tuple of compact widget field names for a node.

    This is the minimal contract: just the ordered list of editable field names
    aligned to ``widgets_values`` positions.  Call ``node_settings_for`` when
    you need enum choices, numeric bounds, or output slots.
    """
    info = node_settings_for(node, class_type, schema_provider=schema_provider)
    return tuple(f.name for f in info.fields)


# ── internal helpers ─────────────────────────────────────────────────────────


def _node_class_type(node: Mapping[str, Any] | Any) -> str:
    if isinstance(node, Mapping):
        return str(node.get("type") or node.get("class_type") or "")
    return str(getattr(node, "class_type", "") or getattr(node, "type", "") or "")


def _schema_from_provider(schema_provider: Any, class_type: str) -> Any | None:
    getter = (
        getattr(schema_provider, "get_schema", None)
        or getattr(schema_provider, "get", None)
    )
    if not callable(getter):
        return None
    try:
        return getter(class_type)
    except Exception:
        return None


__all__ = [
    "NodeFieldInfo",
    "NodeSettingsInfo",
    "compact_field_names_for_node",
    "node_settings_for",
]
