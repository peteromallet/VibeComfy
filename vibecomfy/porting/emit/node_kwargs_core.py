"""Node keyword argument and widget-schema translation helpers."""

from __future__ import annotations

import keyword
from typing import Any, Mapping

from vibecomfy.porting.emit.constants_hoist import _resolve_graph_field_get_string
from vibecomfy.porting.emit.diagnostics import (
    EmissionDiagnostic,
    READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
    READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
)
from vibecomfy.porting.emit.format_values import _format_value
from vibecomfy.porting.emit.naming_codegen import (
    _edge_ref_expr,
    _is_schema_confirmed_single_output,
    _node_output_names,
)
from vibecomfy.porting.emit.wrappers import RESERVED_WRAPPER_INPUT_NAMES
from vibecomfy.porting.object_info import class_defaults
from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA

_CURATED_SCHEMA_DEFAULTS: dict[str, dict[str, Any]] = {
    "UNETLoader": {"weight_dtype": "default"},
    "CLIPLoader": {"device": "default"},
    "VAELoader": {},
    "KSampler": {"scheduler": "simple", "denoise": 1},
    "KSamplerAdvanced": {"scheduler": "simple"},
    "EmptyLatentImage": {"batch_size": 1},
    "EmptySD3LatentImage": {"batch_size": 1},
    "EmptyFlux2LatentImage": {"batch_size": 1},
    "ImageScale": {"crop": "none"},
    "ImageResizeKJv2": {"crop": "none"},
    "VHS_VideoCombine": {"format": "auto", "codec": "auto"},
    "WanVideoSampler": {"shift": 8},
}


def _is_any_link(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and isinstance(value[1], int)


def _is_link(value: Any) -> bool:
    if not (isinstance(value, list) and len(value) == 2):
        return False
    nid, slot = value
    if not isinstance(slot, int):
        return False
    return all(part.isdigit() for part in str(nid).split(":"))


def _is_schema_default(class_type: str, key: str, value: Any, node_metadata: Mapping[str, Any] | dict[str, Any]) -> bool:
    keep = node_metadata.get("keep_defaults") or node_metadata.get("keep_kwargs") or ()
    if key in set(str(item) for item in keep):
        return False
    defaults = dict(_CURATED_SCHEMA_DEFAULTS.get(class_type, {}))
    try:
        defaults.update(class_defaults(class_type))
    except Exception:
        pass
    return key in defaults and value == defaults[key]


def _node_kwargs(
    node: Any,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    *,
    workflow_nodes: dict[str, Any] | None = None,
    output_var_names: dict[str, dict[int, str]] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    constant_map: dict[tuple[str, str], str] | None = None,
    use_ui_widget_aliases: bool = False,
    strip_schema_defaults: bool = False,
    omit_single_output_metadata: bool = False,
    bare_single_output_refs: bool = False,
    emit_reserved_keyword_args: bool = False,
    preserve_fields: set[str] | None = None,
    external_refs: dict[tuple[str, str], str] | None = None,
) -> list[tuple[str, str]]:
    cls = node.class_type
    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
    schema_set = set(schema)

    node_metadata: dict[str, Any] = getattr(node, "metadata", None) or {}
    input_aliases: list[str | None] | None = node_metadata.get("input_aliases") or (
        _ui_widget_aliases(node) if use_ui_widget_aliases else None
    )

    if constant_map is None:
        constant_map = {}
    if preserve_fields is None:
        preserve_fields = set()
    if external_refs is None:
        external_refs = {}

    incoming: dict[str, tuple[str, int]] = {}
    incoming_exprs: dict[str, str] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str, value: Any = None) -> str | None:
        if key.startswith("unused_widget_"):
            return None
        if cls == "Power Lora Loader (rgthree)":
            return _translate_power_lora_loader_widget(key, value)
        if not key.startswith("widget_"):
            return key
        return resolve_widget_key_with_provenance(cls, key, input_aliases=input_aliases).name

    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if _is_any_link(value) and str(value[0]) == "-10":
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                expr = external_refs.get((str(getattr(node, "id", "")), translated_link))
                if expr is not None:
                    incoming_exprs[translated_link] = expr
        elif _is_link(value):
            translated_link = _translate_widget(key, value)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        elif key not in raw_inputs:
            raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key, value)
        if translated is None:
            continue
        value = _resolve_graph_field_get_string(value, workflow_nodes)
        if translated != key and translated not in raw_inputs and translated not in static_inputs:
            if translated not in incoming and translated not in incoming_exprs:
                static_inputs[translated] = value
        else:
            static_inputs[key] = value

    if schema:
        ordered_static_keys = [key for key in schema if key in static_inputs]
        ordered_static_keys += sorted(key for key in static_inputs if key not in schema_set)
    else:
        ordered_static_keys = sorted(static_inputs.keys())

    def _is_python_ident(name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)

    def _format_static_value(key: str, value: Any) -> str:
        nid = getattr(node, "id", None)
        if nid is not None:
            const_name = constant_map.get((str(nid), key))
            if const_name is not None:
                return const_name
        return _format_value(value)

    out: list[tuple[str, str]] = []
    extras: list[tuple[str, str]] = []
    output_names = _node_output_names(node)
    if output_names and not (omit_single_output_metadata and _is_schema_confirmed_single_output(cls, output_names)):
        out.append(("_outputs", _format_value(tuple(output_names))))
    for key in ordered_static_keys:
        if key in incoming or key in incoming_exprs:
            continue
        if key not in preserve_fields and strip_schema_defaults and _is_schema_default(cls, key, static_inputs[key], node_metadata):
            continue
        if not _is_python_ident(key) and not (emit_reserved_keyword_args and key in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((key, _format_static_value(key, static_inputs[key])))
            continue
        if diagnostics is not None and schema and key not in schema_set and emit_reserved_keyword_args:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
                    message=(
                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown kwarg {key!r}; "
                        "typed wrappers accept it through **_extras, so verify the field is intentional."
                    ),
                    severity="warning",
                    node_id=str(getattr(node, "id", "")),
                    class_type=cls,
                    detail={"input": key, "schema_inputs": sorted(schema_set)},
                )
            )
        out.append((key, _format_static_value(key, static_inputs[key])))

    all_incoming_keys = set(incoming) | set(incoming_exprs)
    if schema:
        ordered_incoming = [key for key in schema if key in all_incoming_keys]
        ordered_incoming += sorted(key for key in all_incoming_keys if key not in schema_set)
    else:
        ordered_incoming = sorted(all_incoming_keys)

    for to_input in ordered_incoming:
        if to_input in incoming_exprs:
            expr = incoming_exprs[to_input]
        else:
            from_node, from_slot = incoming[to_input]
            from_node_str = str(from_node)
            expr = _edge_ref_expr(
                workflow_nodes,
                var_names,
                output_var_names or {},
                from_node_str,
                from_slot,
                bare_single_output_refs=bare_single_output_refs,
                diagnostics=diagnostics,
                target_node=node,
                target_input=to_input,
            )
        if not _is_python_ident(to_input) and not (emit_reserved_keyword_args and to_input in RESERVED_WRAPPER_INPUT_NAMES):
            extras.append((to_input, expr))
            continue
        if diagnostics is not None and schema and to_input not in schema_set and emit_reserved_keyword_args:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
                    message=(
                        f"Node {getattr(node, 'id', None)} ({cls}) emits schema-unknown linked kwarg {to_input!r}; "
                        "typed wrappers accept it through **_extras, so verify the field is intentional."
                    ),
                    severity="warning",
                    node_id=str(getattr(node, "id", "")),
                    class_type=cls,
                    detail={"input": to_input, "schema_inputs": sorted(schema_set), "linked": True},
                )
            )
        out.append((to_input, expr))

    if diagnostics is not None:
        diagnostics.extend(_collect_emission_diagnostics(node, output_names, incoming, var_names))

    if extras:
        extras_repr = "{" + ", ".join(f"{key!r}: {value}" for key, value in extras) + "}"
        out.append(("_extras", extras_repr))
    return out


def _translate_power_lora_loader_widget(key: str, value: Any) -> str | None:
    """Map rgthree Power Lora dynamic widget slots to stable kwargs."""
    if key.startswith("unused_widget_"):
        return None
    if not key.startswith("widget_"):
        return key
    index = _power_lora_widget_index(key)
    if index is None:
        return key
    if not _is_power_lora_config(value):
        return None
    return f"lora_{max(1, index - 3)}"


def _power_lora_widget_index(key: str) -> int | None:
    if key.startswith("widget_"):
        suffix = key.removeprefix("widget_")
    elif key.startswith("unused_widget_"):
        suffix = key.removeprefix("unused_widget_")
    else:
        return None
    try:
        return int(suffix)
    except ValueError:
        return None


def _is_power_lora_config(value: Any) -> bool:
    return isinstance(value, dict) and {"on", "lora", "strength"}.issubset(value)


def _collect_emission_diagnostics(
    node: Any,
    output_names: list[str],
    incoming: dict[str, tuple[str, int]],
    var_names: dict[str, str],
) -> list[EmissionDiagnostic]:
    """Collect readability diagnostics for a single node during emission."""
    del incoming, var_names
    diags: list[EmissionDiagnostic] = []
    nid = getattr(node, "id", None)
    ctype = getattr(node, "class_type", None)
    metadata = getattr(node, "metadata", {}) or {}
    node_input_aliases = metadata.get("input_aliases")

    if output_names:
        has_unsafe = False
        has_duplicate = False
        seen: set[str] = set()
        for name in output_names:
            if not name:
                has_unsafe = True
            elif name in seen:
                has_unsafe = True
                has_duplicate = True
            else:
                seen.add(name)
        if has_unsafe:
            if has_duplicate:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
                        message=f"Node {nid} ({ctype}) has duplicate output names; falling back to numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
            else:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
                        message=f"Node {nid} ({ctype}) has partial/blank output names; some outputs use numeric .out(n).",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={"output_names": output_names},
                    )
                )
    elif not node_input_aliases:
        widget_keys = [
            key for key in getattr(node, "widgets", {}).keys()
            if key.startswith("widget_")
        ] + [
            key for key in getattr(node, "inputs", {}).keys()
            if key.startswith("widget_")
        ]
        if widget_keys:
            schema_source = metadata.get("schema_source")
            if schema_source is not None:
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                        message=f"Node {nid} ({ctype}) has {len(set(widget_keys))} unresolved widget_N keys despite schema being available.",
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={
                            "widget_keys": list(set(widget_keys)),
                            "schema_source": schema_source,
                        },
                    )
                )

    if node_input_aliases:
        widget_indices: list[int] = []
        for key in list(getattr(node, "widgets", {}).keys()) + list(getattr(node, "inputs", {}).keys()):
            if key.startswith("widget_"):
                try:
                    widget_indices.append(int(key.split("_", 1)[1]))
                except ValueError:
                    pass
        if widget_indices:
            max_idx = max(widget_indices)
            if max_idx >= len(node_input_aliases):
                unresolved = [
                    f"widget_{index}" for index in widget_indices
                    if index >= len(node_input_aliases)
                ]
                diags.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
                        message=(
                            f"Node {nid} ({ctype}) has {len(unresolved)} widget_N key(s) "
                            f"({', '.join(unresolved)}) outside input_aliases range "
                            f"(len={len(node_input_aliases)}); keeping positional."
                        ),
                        severity="warning",
                        node_id=str(nid) if nid is not None else None,
                        class_type=ctype,
                        detail={
                            "unresolved_widgets": unresolved,
                            "input_aliases_length": len(node_input_aliases),
                        },
                    )
                )

    return diags


def _ui_widget_aliases(node: Any) -> list[str | None] | None:
    ui = getattr(node, "metadata", {}).get("_ui")
    if not isinstance(ui, dict):
        return None
    inputs = ui.get("inputs")
    if not isinstance(inputs, list):
        return None
    aliases: list[str | None] = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        widget = item.get("widget")
        if not isinstance(widget, dict):
            continue
        name = widget.get("name")
        aliases.append(str(name) if isinstance(name, str) and name else None)
    widget_indices: list[int] = []
    for key in getattr(node, "widgets", {}):
        key_str = str(key)
        if not key_str.startswith("widget_"):
            continue
        try:
            widget_indices.append(int(key_str.split("_", 1)[1]))
        except ValueError:
            continue
    if widget_indices and len(aliases) <= max(widget_indices):
        return None
    return aliases or None


def _positional_ui_widget_names(ui_node: Mapping[str, Any], value_count: int) -> list[str | None]:
    """Return authoritative names for positional ``widgets_values`` slots.

    The list is intentionally keyed by widget-value position, not input-item
    position. Callers must only consume positions with a real non-empty name so
    UI-only or anonymous widgets cannot shift later values into the wrong field.
    """
    names: list[str | None] = [None] * value_count
    blocked_indices: set[int] = set()
    class_type = str(ui_node.get("type") or ui_node.get("class_type") or "")

    def set_name(index: int, raw_name: Any) -> None:
        if index < 0 or index >= value_count:
            return
        if index in blocked_indices:
            return
        if names[index] is not None:
            return
        name = str(raw_name or "")
        if name:
            names[index] = name

    explicit_widgets = ui_node.get("widgets")
    if isinstance(explicit_widgets, list):
        for index, item in enumerate(explicit_widgets):
            if isinstance(item, Mapping):
                set_name(index, item.get("name"))
            else:
                set_name(index, item)

    explicit_inputs = ui_node.get("widget_inputs")
    if isinstance(explicit_inputs, list):
        for index, item in enumerate(explicit_inputs):
            if isinstance(item, Mapping):
                set_name(index, item.get("name"))
            else:
                set_name(index, item)

    aliases = ui_node.get("input_aliases")
    if not isinstance(aliases, (list, tuple)):
        properties = ui_node.get("properties")
        aliases = properties.get("input_aliases") if isinstance(properties, Mapping) else None
    if isinstance(aliases, (list, tuple)):
        for index, name in enumerate(aliases):
            set_name(index, name)

    properties = ui_node.get("properties")
    proxy_widgets = properties.get("proxyWidgets") if isinstance(properties, Mapping) else None
    if isinstance(proxy_widgets, list):
        for index, item in enumerate(proxy_widgets):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            set_name(index, item[1])

    schema = WIDGET_SCHEMA.get(class_type)
    if schema is not None:
        for index, name in enumerate(schema):
            if name is None and 0 <= index < value_count and names[index] is None:
                blocked_indices.add(index)
            else:
                set_name(index, name)

    try:
        from vibecomfy.porting.object_info.consume import object_info_widget_order

        object_info_names = object_info_widget_order(class_type)
    except Exception:
        object_info_names = []
    for index, name in enumerate(object_info_names):
        set_name(index, name)

    input_items = [item for item in ui_node.get("inputs") or () if isinstance(item, Mapping)]
    widget_index = 0
    for item in input_items:
        widget = item.get("widget")
        if not isinstance(widget, Mapping):
            continue
        widget_name = widget.get("name")
        if isinstance(widget_name, str) and widget_name:
            set_name(widget_index, widget_name)
            widget_index += 1

    return names


def _ui_widget_values_by_name(ui_node: Mapping[str, Any]) -> dict[str, Any]:
    raw_values = ui_node.get("widgets_values")
    if isinstance(raw_values, Mapping):
        return {str(key): value for key, value in raw_values.items()}
    if not isinstance(raw_values, list):
        return {}

    values: dict[str, Any] = {}
    for index, name in enumerate(_positional_ui_widget_names(ui_node, len(raw_values))):
        if name is not None:
            values[name] = raw_values[index]
    return values


__all__ = [
    "_CURATED_SCHEMA_DEFAULTS",
    "_collect_emission_diagnostics",
    "_is_any_link",
    "_is_link",
    "_is_power_lora_config",
    "_is_schema_default",
    "_node_kwargs",
    "_positional_ui_widget_names",
    "_power_lora_widget_index",
    "_translate_power_lora_loader_widget",
    "_ui_widget_aliases",
    "_ui_widget_values_by_name",
]
