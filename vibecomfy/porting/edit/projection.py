from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Iterable, Mapping, Sequence

from .ledger import EditLedger, ScopeState
from .ops import NodeTarget
from vibecomfy.porting.widgets.schema import effective_widget_names_for_class
from vibecomfy.schema import schema_for


USER_STRING_FENCE = "VIBECOMFY_USER_STRING_JSON"
DEFAULT_MAX_TOKENS = 8000
DEFAULT_FULL_DETAIL_NODE_LIMIT = 40
HELPER_NODE_TYPES = frozenset({"Reroute", "GetNode", "SetNode", "Note", "MarkdownNote"})
MODE_LABELS = {0: "enabled", 2: "muted", 4: "bypassed"}


@dataclass(frozen=True, slots=True)
class ProjectionOptions:
    max_tokens: int = DEFAULT_MAX_TOKENS
    full_detail_node_limit: int = DEFAULT_FULL_DETAIL_NODE_LIMIT
    focus: tuple[NodeTarget, ...] = ()
    include_one_hop_neighbors: bool = True


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    text: str
    token_estimate: int
    node_count: int
    detailed_node_count: int
    truncated: bool = False


def render_edit_projection(
    ui_json: Mapping[str, Any],
    *,
    task: str | None = None,
    schema_provider: Any = None,
    options: ProjectionOptions | None = None,
) -> ProjectionResult:
    """Render an address-preserving, prompt-safe view of browser UI JSON.

    The projection is intentionally a read view of the LiteGraph substrate:
    every editable node address is emitted as ``[scope_path, uid]`` and every
    field/link address uses substrate names. Helper nodes remain visible.
    """

    opts = options or ProjectionOptions()
    ledger = EditLedger.ingest(ui_json)
    node_keys = _ordered_node_keys(ledger)
    detailed = _detailed_node_keys(ledger, node_keys, opts)
    text = _render(
        ledger,
        node_keys=node_keys,
        detailed=detailed,
        task=task,
        schema_provider=schema_provider,
        sparse_budget_mode=False,
    )
    estimate = estimate_tokens(text)
    truncated = False
    if estimate > opts.max_tokens:
        detailed = _focus_keys_with_neighbors(ledger, opts) if opts.focus else frozenset()
        text = _render(
            ledger,
            node_keys=node_keys,
            detailed=detailed,
            task=task,
            schema_provider=schema_provider,
            sparse_budget_mode=True,
        )
        estimate = estimate_tokens(text)
    if estimate > opts.max_tokens:
        text, estimate = _truncate_to_budget(text, opts.max_tokens)
        truncated = True

    # Append the available node-class catalog (after budgeting, so it is never
    # truncated). Without the list of real class_types the model invents
    # plausible-but-nonexistent classes for add_node (e.g. "UpscaleLatent" for the
    # real "LatentUpscale"), which apply_delta then rejects as
    # unknown_add_node_class_type. Feeding the real registry is the anti-hallucination
    # fix for node creation.
    catalog = _available_class_names(schema_provider)
    if catalog:
        text = (
            f"{text}\n\n## Available node class_types for add_node\n"
            "Use EXACTLY one of these names for any add_node `class_type`. Never invent a "
            "class name. If the node you want is not listed, do not add it — instead explain "
            "the limitation in `message`.\n"
            f"{', '.join(catalog)}\n"
        )
        estimate = estimate_tokens(text)

    return ProjectionResult(
        text=text,
        token_estimate=estimate,
        node_count=len(node_keys),
        detailed_node_count=len(detailed),
        truncated=truncated,
    )


def _available_class_names(schema_provider: Any) -> list[str]:
    """Best-effort list of every node class_type the schema provider knows."""
    if schema_provider is None:
        return []
    for attr in ("schemas", "all_schemas"):
        fn = getattr(schema_provider, attr, None)
        if callable(fn):
            try:
                data = fn()
                if isinstance(data, dict) and data:
                    return sorted(str(k) for k in data.keys())
            except Exception:
                pass
    return []


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _render(
    ledger: EditLedger,
    *,
    node_keys: Sequence[tuple[str, str]],
    detailed: frozenset[tuple[str, str]],
    task: str | None,
    schema_provider: Any,
    sparse_budget_mode: bool,
) -> str:
    lines: list[str] = [
        "# VibeComfy Agent-Edit Projection v1",
        "Return typed delta ops only. Use exactly these substrate addresses.",
        "Node target: [scope_path, uid]. Field target: [scope_path, uid, field_path].",
        "Link endpoints: from [scope_path, uid, output_slot] to [scope_path, uid, input_field].",
        "Helper nodes are real substrate nodes and are intentionally visible.",
        "Mode annotations are informational only; use set_mode to change enable/mute/bypass.",
    ]
    if task:
        lines.extend(["", "## User Task", _format_value(task)])
    if sparse_budget_mode:
        lines.extend(["", "## Budget Mode", "Sparse rendering is active; focused nodes retain detail, other nodes are summaries."])

    for scope_path, scope in _ordered_scopes(ledger):
        scope_node_keys = [key for key in node_keys if key[0] == scope_path]
        if not scope_node_keys:
            continue
        label = "<root>" if scope_path == "" else scope_path
        lines.extend(["", f"## Scope {json.dumps(label, ensure_ascii=True)}"])
        if scope.kind == "subgraph":
            lines.append(f"path_tokens={json.dumps(list(scope.path_tokens), ensure_ascii=True)}")
        for key in scope_node_keys:
            node = ledger.node_index[key]
            lines.extend(
                _render_node(
                    node,
                    scope=scope,
                    scope_path=scope_path,
                    uid=key[1],
                    detailed=key in detailed,
                    schema_provider=schema_provider,
                )
            )
        link_lines = _render_links(ledger, scope)
        if link_lines:
            lines.extend(["", "links:", *link_lines])

    diagnostics = [issue for issue in ledger.diagnostics if issue.severity != "info"]
    if diagnostics:
        lines.extend(["", "## Identity Diagnostics"])
        for issue in diagnostics:
            lines.append(f"- {issue.code}: {json.dumps(issue.detail, sort_keys=True, ensure_ascii=True)}")
    return "\n".join(lines).rstrip() + "\n"


def _render_node(
    node: Mapping[str, Any],
    *,
    scope: ScopeState,
    scope_path: str,
    uid: str,
    detailed: bool,
    schema_provider: Any,
) -> list[str]:
    node_id = node.get("id")
    class_type = str(node.get("type") or node.get("class_type") or "")
    mode = node.get("mode", 0)
    mode_text = MODE_LABELS.get(mode, f"mode={mode}")
    helper = " helper=true" if class_type in HELPER_NODE_TYPES else ""
    title = node.get("title")
    line = (
        f"- node target={json.dumps([scope_path, uid], ensure_ascii=True)} "
        f"id={json.dumps(node_id, ensure_ascii=True)} class={json.dumps(class_type, ensure_ascii=True)} "
        f"mode={json.dumps(mode, ensure_ascii=True)} ({mode_text}; informational)"
        f"{helper}"
    )
    if isinstance(title, str) and title:
        line += f" title={_format_value(title)}"
    lines = [line]
    if not detailed:
        input_count = len(node.get("inputs") or []) if isinstance(node.get("inputs"), list) else 0
        output_count = len(node.get("outputs") or []) if isinstance(node.get("outputs"), list) else 0
        # Show field NAMES, not just a count: in sparse/budget mode (large graphs) the
        # model otherwise can't see a node's settable field names and guesses wrong ones
        # (e.g. "seed" for RandomNoise, whose real widget is "noise_seed"), which
        # apply_delta then rejects as unknown_node_field. Listing the names — capped to
        # bound tokens — lets set_node_field target the exact field even on summary nodes.
        field_names = [row[0] for row in _field_rows(node, class_type)]
        shown = field_names[:14]
        suffix = "" if len(field_names) <= 14 else f", +{len(field_names) - 14} more"
        fields_repr = f"[{', '.join(shown)}{suffix}]" if field_names else "[]"
        lines.append(f"  summary: inputs={input_count} outputs={output_count} fields={fields_repr}")
        return lines

    fields = _field_rows(node, class_type)
    if fields:
        lines.append("  fields:")
        for name, value, source in fields:
            lines.append(
                f"    - target={json.dumps([scope_path, uid, name], ensure_ascii=True)} "
                f"source={source} value={_format_value(value)}"
            )
    schema_lines = _schema_hint_lines(class_type, schema_provider)
    if schema_lines:
        lines.extend(["  schema_hints:", *[f"    {line}" for line in schema_lines]])
    input_lines = _slot_lines(node.get("inputs"), direction="input")
    if input_lines:
        lines.extend(["  inputs:", *[f"    {line}" for line in input_lines]])
    output_lines = _slot_lines(node.get("outputs"), direction="output")
    if output_lines:
        lines.extend(["  outputs:", *[f"    {line}" for line in output_lines]])
    if scope.kind == "subgraph":
        lines.append(f"  scope_path_tokens={json.dumps(list(scope.path_tokens), ensure_ascii=True)}")
    return lines


def _field_rows(node: Mapping[str, Any], class_type: str) -> list[tuple[str, Any, str]]:
    rows: list[tuple[str, Any, str]] = []
    widgets = node.get("widgets_values")
    if isinstance(widgets, list):
        names = list(effective_widget_names_for_class(class_type, allow_object_info_fallback=True))
        if len(names) < len(widgets):
            recovered = _widget_names_from_inputs(node.get("inputs"))
            if len(recovered) >= len(widgets):
                names = recovered
        for index, value in enumerate(widgets):
            name = names[index] if index < len(names) and names[index] else f"widget_{index}"
            rows.append((str(name), value, f"widgets_values[{index}]"))
    inputs = node.get("inputs")
    if isinstance(inputs, list):
        seen = {name for name, _, _ in rows}
        for slot in inputs:
            if not isinstance(slot, Mapping):
                continue
            name = _widget_name_for_input(slot)
            if name and name not in seen and "link" not in slot:
                rows.append((name, slot.get("value"), "inputs[].widget"))
    return rows


def _schema_hint_lines(class_type: str, schema_provider: Any) -> list[str]:
    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return []
    lines: list[str] = []
    inputs = getattr(schema, "inputs", {}) or {}
    for name in sorted(inputs):
        spec = inputs[name]
        bits = [f"{name}: type={json.dumps(getattr(spec, 'type', None), ensure_ascii=True)}"]
        if getattr(spec, "required", False):
            bits.append("required=true")
        if getattr(spec, "default", None) is not None:
            bits.append(f"default={_format_value(getattr(spec, 'default'))}")
        choices = getattr(spec, "choices", None)
        if choices:
            preview = list(choices[:8]) if isinstance(choices, list) else list(choices)
            bits.append(f"choices={_format_value(preview)}")
        if getattr(spec, "min", None) is not None or getattr(spec, "max", None) is not None:
            bits.append(f"range=[{getattr(spec, 'min', None)}, {getattr(spec, 'max', None)}]")
        lines.append("- input " + " ".join(bits))
    outputs = getattr(schema, "outputs", None) or []
    for index, output in enumerate(outputs):
        lines.append(
            "- output "
            f"{index}: name={json.dumps(getattr(output, 'name', None), ensure_ascii=True)} "
            f"type={json.dumps(getattr(output, 'type', None), ensure_ascii=True)}"
        )
    return lines


def _slot_lines(slots: Any, *, direction: str) -> list[str]:
    if not isinstance(slots, list):
        return []
    lines: list[str] = []
    for index, slot in enumerate(slots):
        if not isinstance(slot, Mapping):
            continue
        name = slot.get("name")
        socket_type = slot.get("type")
        if direction == "input":
            lines.append(
                f"- {index}: name={json.dumps(name, ensure_ascii=True)} "
                f"type={json.dumps(socket_type, ensure_ascii=True)} link={json.dumps(slot.get('link'), ensure_ascii=True)}"
            )
        else:
            lines.append(
                f"- {index}: name={json.dumps(name, ensure_ascii=True)} "
                f"type={json.dumps(socket_type, ensure_ascii=True)} links={json.dumps(slot.get('links'), ensure_ascii=True)}"
            )
    return lines


def _render_links(ledger: EditLedger, scope: ScopeState) -> list[str]:
    links = scope.graph.get("links")
    if not isinstance(links, list):
        return []
    lines: list[str] = []
    for link in sorted(links, key=lambda item: (_link_id(item) is None, _link_id(item) or 0)):
        link_id = _link_id(link)
        origin_id, origin_slot, target_id, target_slot, link_type = _link_parts(link)
        origin = _node_uid_by_id(scope.graph, origin_id)
        target = _node_uid_by_id(scope.graph, target_id)
        origin_slot_name = _output_slot_name(scope.graph, origin_id, origin_slot)
        target_input_name = _input_slot_name(scope.graph, target_id, target_slot)
        lines.append(
            f"- id={json.dumps(link_id, ensure_ascii=True)} "
            f"from={json.dumps([scope.scope_path, origin or str(origin_id), origin_slot_name], ensure_ascii=True)} "
            f"to={json.dumps([scope.scope_path, target or str(target_id), target_input_name], ensure_ascii=True)} "
            f"type={json.dumps(link_type, ensure_ascii=True)}"
        )
    return lines


def _ordered_scopes(ledger: EditLedger) -> list[tuple[str, ScopeState]]:
    return sorted(ledger.scopes.items(), key=lambda item: (len(item[1].path_tokens), item[1].path_tokens, item[0]))


def _ordered_node_keys(ledger: EditLedger) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    for scope_path, scope in _ordered_scopes(ledger):
        nodes = scope.graph.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in sorted(
            [node for node in nodes if isinstance(node, Mapping)],
            key=lambda item: (item.get("order") if isinstance(item.get("order"), int) else 10**9, item.get("id") or 0),
        ):
            uid = _node_uid(node)
            if uid is not None:
                keys.append((scope_path, uid))
    return keys


def _detailed_node_keys(
    ledger: EditLedger,
    node_keys: Sequence[tuple[str, str]],
    options: ProjectionOptions,
) -> frozenset[tuple[str, str]]:
    if options.focus:
        return _focus_keys_with_neighbors(ledger, options)
    if len(node_keys) <= options.full_detail_node_limit:
        return frozenset(node_keys)
    helpers = {key for key in node_keys if _class_type(ledger.node_index[key]) in HELPER_NODE_TYPES}
    return frozenset(set(node_keys[: options.full_detail_node_limit]) | helpers)


def _focus_keys_with_neighbors(ledger: EditLedger, options: ProjectionOptions) -> frozenset[tuple[str, str]]:
    focus = {(target.scope_path, target.uid) for target in options.focus}
    if not options.include_one_hop_neighbors:
        return frozenset(focus)
    expanded = set(focus)
    id_to_key: dict[tuple[str, int], tuple[str, str]] = {}
    for key, node in ledger.node_index.items():
        node_id = node.get("id")
        if isinstance(node_id, int):
            id_to_key[(key[0], node_id)] = key
    for scope_path, scope in ledger.scopes.items():
        links = scope.graph.get("links")
        if not isinstance(links, list):
            continue
        for link in links:
            origin_id, _, target_id, _, _ = _link_parts(link)
            origin_key = id_to_key.get((scope_path, origin_id)) if isinstance(origin_id, int) else None
            target_key = id_to_key.get((scope_path, target_id)) if isinstance(target_id, int) else None
            if origin_key in focus and target_key is not None:
                expanded.add(target_key)
            if target_key in focus and origin_key is not None:
                expanded.add(origin_key)
    return frozenset(expanded)


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        encoded = json.dumps(value, ensure_ascii=True)
        return f"<<{USER_STRING_FENCE}\n{encoded}\n{USER_STRING_FENCE}"
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _truncate_to_budget(text: str, max_tokens: int) -> tuple[str, int]:
    max_chars = max(256, max_tokens * 4)
    suffix = "\n\n[projection truncated to token budget; refine focus for more detail]\n"
    if len(text) <= max_chars:
        return text, estimate_tokens(text)
    truncated = text[: max(0, max_chars - len(suffix))].rstrip() + suffix
    return truncated, estimate_tokens(truncated)


def _widget_name_for_input(slot: Any) -> str | None:
    if not isinstance(slot, Mapping):
        return None
    widget = slot.get("widget")
    if not isinstance(widget, Mapping):
        return None
    name = widget.get("name")
    return str(name) if isinstance(name, str) and name else None


def _widget_names_from_inputs(inputs: Any) -> list[str]:
    if not isinstance(inputs, list):
        return []
    names: list[str] = []
    for slot in inputs:
        name = _widget_name_for_input(slot)
        if name is not None:
            names.append(name)
    return names


def _node_uid(node: Mapping[str, Any]) -> str | None:
    properties = node.get("properties")
    if not isinstance(properties, Mapping):
        return None
    uid = properties.get("vibecomfy_uid")
    return uid if isinstance(uid, str) and uid else None


def _class_type(node: Mapping[str, Any]) -> str:
    return str(node.get("type") or node.get("class_type") or "")


def _link_id(link: Any) -> int | None:
    if isinstance(link, Mapping):
        return link.get("id") if isinstance(link.get("id"), int) else None
    if isinstance(link, Sequence) and not isinstance(link, (str, bytes)) and link and isinstance(link[0], int):
        return link[0]
    return None


def _link_parts(link: Any) -> tuple[int | None, int | None, int | None, int | None, Any]:
    if isinstance(link, Mapping):
        return (
            link.get("origin_id") if isinstance(link.get("origin_id"), int) else None,
            link.get("origin_slot") if isinstance(link.get("origin_slot"), int) else None,
            link.get("target_id") if isinstance(link.get("target_id"), int) else None,
            link.get("target_slot") if isinstance(link.get("target_slot"), int) else None,
            link.get("type"),
        )
    if isinstance(link, Sequence) and not isinstance(link, (str, bytes)) and len(link) >= 6:
        items = list(link)
        return (
            items[1] if isinstance(items[1], int) else None,
            items[2] if isinstance(items[2], int) else None,
            items[3] if isinstance(items[3], int) else None,
            items[4] if isinstance(items[4], int) else None,
            items[5],
        )
    return None, None, None, None, None


def _node_by_id(scope_graph: Mapping[str, Any], node_id: int | None) -> Mapping[str, Any] | None:
    if node_id is None:
        return None
    nodes = scope_graph.get("nodes")
    if not isinstance(nodes, list):
        return None
    for node in nodes:
        if isinstance(node, Mapping) and node.get("id") == node_id:
            return node
    return None


def _node_uid_by_id(scope_graph: Mapping[str, Any], node_id: int | None) -> str | None:
    node = _node_by_id(scope_graph, node_id)
    return _node_uid(node) if node is not None else None


def _output_slot_name(scope_graph: Mapping[str, Any], node_id: int | None, slot_index: int | None) -> str | int | None:
    if slot_index is None:
        return None
    node = _node_by_id(scope_graph, node_id)
    outputs = node.get("outputs") if node is not None else None
    if isinstance(outputs, list) and 0 <= slot_index < len(outputs):
        output = outputs[slot_index]
        if isinstance(output, Mapping) and isinstance(output.get("name"), str) and output.get("name"):
            return str(output["name"])
    return slot_index


def _input_slot_name(scope_graph: Mapping[str, Any], node_id: int | None, slot_index: int | None) -> str | int | None:
    if slot_index is None:
        return None
    node = _node_by_id(scope_graph, node_id)
    inputs = node.get("inputs") if node is not None else None
    if isinstance(inputs, list) and 0 <= slot_index < len(inputs):
        input_slot = inputs[slot_index]
        if isinstance(input_slot, Mapping) and isinstance(input_slot.get("name"), str) and input_slot.get("name"):
            return str(input_slot["name"])
    return slot_index


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "ProjectionOptions",
    "ProjectionResult",
    "USER_STRING_FENCE",
    "estimate_tokens",
    "render_edit_projection",
]
