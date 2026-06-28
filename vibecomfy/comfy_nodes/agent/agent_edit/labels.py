from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from vibecomfy.porting.edit.types import FieldChange

from ..contracts import (
    _MISSING_FIELD_CHANGE_OLD,
    _iter_ui_graph_nodes,
    _ui_node_uid,
    _ui_node_uid_aliases,
    _ui_widget_value_for_field,
)
from .budget import _json_safe


def _display_value(value: Any, *, limit: int = 48) -> str:
    if isinstance(value, str):
        text = value
    elif value is None:
        text = "null"
    elif isinstance(value, (int, float, bool)):
        text = str(value)
    else:
        try:
            text = json.dumps(_json_safe(value), sort_keys=True)
        except (TypeError, ValueError):
            text = str(value)
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: max(0, limit - 1)] + "\u2026"
    return text


def _node_label_by_uid(*graphs: Mapping[str, Any] | None) -> dict[str, str]:
    labels: dict[str, str] = {}
    for graph in graphs:
        if not isinstance(graph, Mapping):
            continue
        for node in _iter_ui_graph_nodes(graph):
            class_type = node.get("type") or node.get("class_type")
            title = node.get("title")
            label = title if isinstance(title, str) and title.strip() else class_type
            if isinstance(label, str) and label.strip():
                for uid in _ui_node_uid_aliases(node):
                    labels[str(uid)] = label.strip()
    return labels


def _change_subject(change: "FieldChange", labels: Mapping[str, str] | None = None) -> str:
    uid = str(change.uid or "node").strip() or "node"
    field = str(change.field_path or "field").strip() or "field"
    label = labels.get(uid) if labels else None
    if isinstance(label, str) and label.strip():
        return f"{label.strip()} {field}"
    if labels is not None and _looks_internal_uid(uid):
        return f"node {field}"
    return f"{uid}.{field}"


def _looks_internal_uid(uid: str) -> bool:
    return bool(re.fullmatch(r"n\d+|.*_\d+|\d+", uid.strip()))


def _link_endpoint_parts(value: Any) -> tuple[str, int | str] | None:
    """Return ``(uid, output_slot)`` for supported FieldChange link endpoint shapes.

    Accepts both ``list`` / ``tuple`` and the batch editor's mapping form because
    ``FieldChange.__post_init__`` freezes JSON-ish mappings into ``MappingProxyType``.
    """
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], (int, str))
        and isinstance(value[1], int)
    ):
        return str(value[0]), value[1]
    if isinstance(value, Mapping):
        uid = value.get("uid")
        output_slot = value.get("output_slot")
        if isinstance(uid, (int, str)) and isinstance(output_slot, (int, str)):
            return str(uid), output_slot
    return None


def _is_link_endpoint(value: Any) -> bool:
    return _link_endpoint_parts(value) is not None


def _resolve_output_slot_name(graph: Mapping[str, Any], uid: str, slot_index: int | str) -> str | None:
    """Return the human-readable output-slot name for *uid* / *slot_index*, or None."""
    if isinstance(slot_index, str):
        return slot_index
    for node in _iter_ui_graph_nodes(graph):
        if uid not in _ui_node_uid_aliases(node):
            continue
        outputs = node.get("outputs")
        if isinstance(outputs, list) and 0 <= slot_index < len(outputs):
            entry = outputs[slot_index]
            if isinstance(entry, Mapping):
                name = entry.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        break
    return None


def _resolve_endpoint_label(
    endpoint: Any,
    node_labels: Mapping[str, str],
    graph: Mapping[str, Any],
    *fallback_graphs: Mapping[str, Any] | None,
) -> str:
    """Resolve a link endpoint ``[uid, slot]`` to a label like ``'VAE Decode IMAGE'``."""
    parts = _link_endpoint_parts(endpoint)
    if parts is None:
        return "unknown source"
    uid, slot = parts
    node_label = node_labels.get(uid)
    slot_name = _resolve_output_slot_name(graph, uid, slot)
    if slot_name is None:
        for fallback_graph in fallback_graphs:
            if isinstance(fallback_graph, Mapping):
                slot_name = _resolve_output_slot_name(fallback_graph, uid, slot)
                if slot_name is not None:
                    break
    if node_label and slot_name:
        return f"{node_label} {slot_name}"
    if node_label:
        return node_label
    if slot_name:
        return slot_name
    return "unknown source"


def _ui_node_by_uid(graph: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(graph, Mapping):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    for node in _iter_ui_graph_nodes(graph):
        uid = _ui_node_uid(node)
        if uid:
            result[str(uid)] = node
    return result


def _node_class_label(node: Mapping[str, Any]) -> str:
    class_type = node.get("type") or node.get("class_type")
    if isinstance(class_type, str) and class_type.strip():
        return class_type.strip()
    title = node.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return "node"


def _ui_display_widget_value_for_field(node: Mapping[str, Any], field: str) -> Any:
    widgets = node.get("widgets")
    widgets_values = node.get("widgets_values")
    if isinstance(widgets, list) and isinstance(widgets_values, list):
        for index, widget in enumerate(widgets):
            if (
                isinstance(widget, Mapping)
                and widget.get("name") == field
                and index < len(widgets_values)
            ):
                return widgets_values[index]
    return _ui_widget_value_for_field(node, field)


def _node_key_values(node: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for field in ("scale_by", "scale", "upscale_method", "filename_prefix", "seed", "steps", "denoise"):
        value = _ui_display_widget_value_for_field(node, field)
        if value is _MISSING_FIELD_CHANGE_OLD:
            continue
        if field in {"scale_by", "scale"} and isinstance(value, (int, float)) and 0 < float(value) <= 1:
            values.append(f"{round(float(value) * 100):g}%")
        elif field == "filename_prefix":
            values.append(str(value))
        else:
            values.append(_display_value(value, limit=28))
    return values[:3]


def _node_phrase(node: Mapping[str, Any]) -> str:
    label = _node_class_label(node)
    values = _node_key_values(node)
    if values:
        return f"{label} ({', '.join(values)})"
    return label


def _article_for(text: str) -> str:
    first = text[:1].lower()
    return "an" if first in {"a", "e", "i", "o", "u"} else "a"


def _first_link_source_label(
    node: Mapping[str, Any],
    graph: Mapping[str, Any] | None,
    labels: Mapping[str, str],
) -> str | None:
    if not isinstance(graph, Mapping):
        return None
    inputs = node.get("inputs")
    links = graph.get("links")
    if not isinstance(inputs, list) or not isinstance(links, list):
        return None
    link_id = None
    for input_slot in inputs:
        if isinstance(input_slot, Mapping) and isinstance(input_slot.get("link"), (int, float)):
            link_id = int(input_slot["link"])
            break
    if link_id is None:
        return None
    by_id: dict[int, Any] = {}
    for link in links:
        if isinstance(link, Mapping) and isinstance(link.get("id"), (int, float)):
            by_id[int(link["id"])] = link
        elif isinstance(link, (list, tuple)) and link and isinstance(link[0], (int, float)):
            by_id[int(link[0])] = link
    link = by_id.get(link_id)
    if isinstance(link, Mapping):
        source_id = link.get("origin_id")
        source_slot = link.get("origin_slot", 0)
    elif isinstance(link, (list, tuple)) and len(link) >= 3:
        source_id = link[1]
        source_slot = link[2]
    else:
        return None
    source_uid = None
    for candidate in _iter_ui_graph_nodes(graph):
        if candidate.get("id") == source_id:
            source_uid = _ui_node_uid(candidate)
            break
    if not source_uid:
        return None
    return _resolve_endpoint_label({"uid": source_uid, "output_slot": source_slot}, labels, graph)


def _structural_change_phrases(state: "AgentEditState", labels: Mapping[str, str]) -> list[str]:
    before_by_uid = _ui_node_by_uid(state.graph)
    after_by_uid = _ui_node_by_uid(state.ui_payload)
    if not after_by_uid:
        return []
    added = [after_by_uid[uid] for uid in sorted(set(after_by_uid) - set(before_by_uid))]
    removed = [before_by_uid[uid] for uid in sorted(set(before_by_uid) - set(after_by_uid))]
    phrases: list[str] = []
    if added:
        parts: list[str] = []
        for node in added[:8]:
            node_text = _node_phrase(node)
            source = _first_link_source_label(node, state.ui_payload, labels)
            if source:
                node_text = f"{node_text} fed by {source}"
            parts.append(node_text)
        text = _join_human_list(parts)
        remaining = len(added) - len(parts)
        if remaining > 0:
            noun = "other node" if remaining == 1 else "other nodes"
            text = f"{text}, plus {remaining} {noun}"
        article = _article_for(parts[0]) if len(parts) == 1 else ""
        phrases.append(f"added {article + ' ' if article else ''}{text}")
    if removed:
        parts = [_node_phrase(node) for node in removed[:3]]
        phrases.append(f"removed {_join_human_list(parts)}")
    return phrases


def _join_human_list(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _format_statement_source(source: str, *, max_chars: int = 72) -> str:
    """Truncate a statement source string for inline display."""
    if len(source) <= max_chars:
        return source
    return source[: max(0, max_chars - 3)] + "..."


def _iter_ui_nodes(ui_payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Return root and nested UI node dictionaries from a LiteGraph payload."""
    found: list[Mapping[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            nodes = value.get("nodes")
            if isinstance(nodes, list):
                for node in nodes:
                    if isinstance(node, Mapping):
                        found.append(node)
                        visit(node)
            for key in ("graphs", "subgraphs"):
                nested = value.get(key)
                if isinstance(nested, list):
                    for item in nested:
                        visit(item)
                elif isinstance(nested, Mapping):
                    for item in nested.values():
                        visit(item)

    visit(ui_payload)
    return found


def _present_class_types(session: Any) -> list[str]:
    """Enumerate class types currently present in an EditSession working graph."""
    working_ui = getattr(session, "working_ui", None)
    if not isinstance(working_ui, Mapping):
        return []
    types: set[str] = set()
    for node in _iter_ui_nodes(working_ui):
        class_type = node.get("type") or node.get("class_type")
        if isinstance(class_type, str) and class_type:
            types.add(class_type)
    return sorted(types)


def _format_node_variable_index(session: Any) -> str:
    """Return ``var = ClassType`` lines for the current EditSession graph."""
    working_ui = getattr(session, "working_ui", None)
    name_by_uid = getattr(session, "name_by_uid", None)
    if not isinstance(working_ui, Mapping) or not isinstance(name_by_uid, Mapping):
        return ""
    rows: list[tuple[str, str, str]] = []
    for node in _iter_ui_nodes(working_ui):
        uid = _ui_node_uid(node)
        if not uid:
            continue
        name = name_by_uid.get(uid)
        class_type = node.get("type") or node.get("class_type")
        if isinstance(name, str) and name and isinstance(class_type, str) and class_type:
            rows.append((name, uid, class_type))
    rows.sort(key=lambda item: (item[0], item[1]))
    return "\n".join(f"{name} = {class_type}" for name, _uid, class_type in rows)


def _format_available_node_names(
    rows: Any,
    *,
    max_line_chars: int = 96,
    max_names: int = 80,
) -> str:
    """Format NodeSignatureRow-like objects as a bounded deterministic name list.

    Large ComfyUI installs can expose hundreds of node types. Dumping the full
    registry into the first edit prompt makes simple turns slow and brittle, and
    the batch REPL already has ``search(...)`` for exact schema lookup when a
    new type is needed.
    """
    names = sorted(
        {
            class_type
            for row in rows or []
            if isinstance((class_type := getattr(row, "class_type", None)), str)
            and class_type
        }
    )
    if not names:
        return ""
    total_count = len(names)
    if max_names > 0 and total_count > max_names:
        names = names[:max_names]
    lines: list[str] = []
    current = names[0]
    for name in names[1:]:
        candidate = f"{current}, {name}"
        if len(candidate) > max_line_chars:
            lines.append(current)
            current = name
        else:
            current = candidate
    lines.append(current)
    if total_count > len(names):
        lines.append(
            f"... [{total_count - len(names)} more node type names omitted; "
            "use search(...) for exact local schema lookup before adding an omitted type]"
        )
    return "\n".join(lines)


def _format_query_output(text: str, *, max_chars: int | None = 4000) -> str:
    """Bound read-only query output before it is included in agent feedback."""
    if max_chars is None:
        return text
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 18)].rstrip() + "\n... [truncated]"
