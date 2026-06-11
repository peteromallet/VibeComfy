"""Keyword argument extraction for ready-template emission."""

from __future__ import annotations

import keyword
from typing import Any

from vibecomfy._compile._graph import is_api_link
from vibecomfy.porting.formatting import format_value
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA, resolve_widget_name


def node_kwargs(node: Any, edges_in: dict, var_names: dict[str, str]) -> list[tuple[str, str]]:
    """Produce ordered (kwarg_name, repr_or_handle_expr) pairs for a node.

    Resolves links from BOTH `workflow.edges` (the canonical place) and
    `node.inputs` (for templates whose IR retained list-shaped link values
    because the upstream `convert_to_vibe_format` didn't strip dotted-id
    links).
    """
    cls = node.class_type

    schema = [name for name in WIDGET_SCHEMA.get(cls, []) if name is not None]
    schema_set = set(schema)

    # Build incoming map: edges first, then any list-shaped link still in inputs.
    incoming: dict[str, tuple[str, int]] = {}
    for edge in edges_in.get(node.id, []):
        incoming[edge.to_input] = (edge.from_node, int(edge.from_output))

    def _translate_widget(key: str) -> str | None:
        """Resolve a widget_N key to its canonical name, or None to drop it."""
        if not key.startswith("widget_"):
            return key
        try:
            idx = int(key.split("_", 1)[1])
        except ValueError:
            return key
        return resolve_widget_name(cls, idx)

    # Two-phase: collect raw keys and values, then optionally translate
    # widget_X keys to canonical names ONLY when the canonical isn't already
    # in the source (preserves dual-key noise from LEGACY API JSON like
    # `{audio: 'x.wav', widget_0: 'x.wav'}`).
    raw_inputs: dict[str, Any] = {}
    for key, value in node.inputs.items():
        if is_api_link(
            value,
            allow_tuple=False,
            require_string_node_id=True,
            require_numeric_node_id=True,
            allow_compound_node_id=True,
            require_int_slot=True,
        ):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            raw_inputs[key] = value
    for key, value in node.widgets.items():
        if is_api_link(
            value,
            allow_tuple=False,
            require_string_node_id=True,
            require_numeric_node_id=True,
            allow_compound_node_id=True,
            require_int_slot=True,
        ):
            translated_link = _translate_widget(key)
            if translated_link is not None:
                incoming.setdefault(translated_link, (str(value[0]), int(value[1])))
        else:
            if key not in raw_inputs:
                raw_inputs[key] = value

    static_inputs: dict[str, Any] = {}
    for key, value in raw_inputs.items():
        translated = _translate_widget(key)
        if translated is None:
            # UI-only widget (e.g. KSampler control_after_generate) -- drop entirely.
            continue
        if (
            translated != key
            and translated not in raw_inputs
            and translated not in static_inputs
            and translated not in incoming
        ):
            # Only the widget form exists -- promote to canonical for readability.
            static_inputs[translated] = value
        else:
            # Keep raw key (e.g. when canonical exists as link or in raw).
            static_inputs[key] = value

    # Order static inputs: schema order first, then anything else alphabetically.
    if schema:
        ordered_static_keys = [k for k in schema if k in static_inputs]
        ordered_static_keys += sorted(k for k in static_inputs if k not in schema_set)
    else:
        ordered_static_keys = sorted(static_inputs.keys())

    def _is_python_ident(name: str) -> bool:
        return name.isidentifier() and not keyword.iskeyword(name)

    out: list[tuple[str, str]] = []
    extras: list[tuple[str, str]] = []
    for key in ordered_static_keys:
        if key in incoming:
            continue
        if not _is_python_ident(key):
            extras.append((key, format_value(static_inputs[key])))
            continue
        out.append((key, format_value(static_inputs[key])))

    # Now emit incoming-edge kwargs, schema-ordered if applicable.
    if schema:
        ordered_incoming = [k for k in schema if k in incoming]
        ordered_incoming += sorted(k for k in incoming if k not in schema_set)
    else:
        ordered_incoming = sorted(incoming.keys())

    for to_input in ordered_incoming:
        from_node, from_slot = incoming[to_input]
        if from_node in var_names:
            expr = f"{var_names[from_node]}.out({from_slot})"
        else:
            expr = f"[{from_node!r}, {from_slot}]"
        if not _is_python_ident(to_input):
            extras.append((to_input, expr))
            continue
        out.append((to_input, expr))

    if extras:
        # Pass non-identifier kwargs as a dict literal via _extras kwarg,
        # which the `_node` helper applies post-construction.
        extras_repr = "{" + ", ".join(f"{k!r}: {v}" for k, v in extras) + "}"
        out.append(("_extras", extras_repr))

    return out


def apply_overrides(nodes: dict, edges_in: dict, patches: list[dict]) -> None:
    """Apply override JSON patches to the IR before emit."""
    for patch in patches:
        match = patch.get("match", {})
        target_ids: list[str] = []
        if "node_id" in match:
            target_ids = [str(match["node_id"])]
        elif "class_type" in match:
            class_target = match["class_type"]
            ordinal = match.get("node_index")
            matches = [nid for nid, n in nodes.items() if n.class_type == class_target]
            if ordinal is not None and 0 <= ordinal < len(matches):
                target_ids = [matches[ordinal]]
            else:
                target_ids = matches

        for tid in target_ids:
            node = nodes.get(tid)
            if node is None:
                continue
            for old, new in (patch.get("rename_inputs") or {}).items():
                if old in node.widgets:
                    node.widgets[new] = node.widgets.pop(old)
                if old in node.inputs:
                    node.inputs[new] = node.inputs.pop(old)
            for key, value in (patch.get("set_inputs") or {}).items():
                if key in node.widgets:
                    node.widgets[key] = value
                else:
                    node.inputs[key] = value
            for key in patch.get("remove_inputs") or []:
                node.widgets.pop(key, None)
                node.inputs.pop(key, None)


__all__ = ["apply_overrides", "node_kwargs"]
