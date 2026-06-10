"""emit_subgraph.py — subgraph definition, naming, and emission helpers.

This module is carved from :mod:`vibecomfy.porting.emitter` as part of the
M2 structural-decomposition epic (Step 5).

All names exported here remain importable from ``vibecomfy.porting.emitter``
via explicit re-exports so that existing callers are unaffected.
"""

from __future__ import annotations

import hashlib
import json
import keyword as _keyword
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Mapping

from vibecomfy.porting.emit_constants import (
    UI_ONLY_CLASS_TYPES,
    _translate_widget_for_key,
    _ui_widget_aliases,
)
from vibecomfy.porting.emit_kwargs import (
    _apply_locked_variable_names,
    _assignment_target,
    _compute_output_variable_names,
    _compute_variable_names,
    _edge_ref_expr,
    _edges_in_with_subgraph_external_refs,
    _first_output_var,
    _format_metadata_dict,
    _format_value,
    _is_any_link,
    _is_link,
    _live_output_slots_for_function,
    _node_kwargs,
    _node_output_names,
    _safe_output_name,
    _safe_var,
    _topological_node_order,
    _ui_output_names,
)
from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

if TYPE_CHECKING:
    from vibecomfy.porting.emitter import EmissionDiagnostic

logger = logging.getLogger(__name__)

READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND = "subgraph_input_unbound"

__all__ = [
    "_SubgraphPort",
    "_SubgraphDef",
    "slugify_subgraph_name",
    "_slugify_identifier",
    "_safe_kwarg_name",
    "_subgraph_input_kwarg_name",
    "_unique_port_name",
    "_subgraph_definitions_from_raw",
    "_disambiguated_subgraph_slugs",
    "_build_subgraph_def",
    "subgraph_source_hash",
    "_subgraph_default_args",
    "_widget_default_for_target",
    "_apply_subgraph_names_to_prepared",
    "_subgraph_result_base",
    "_unique_var",
    "COMFY_TYPE_TO_PY_HINT",
    "_emit_subgraph_functions",
    "_subgraph_topological_order",
    "_short_subgraph_id_prefix",
    "_subgraph_emitted_node_id",
    "_subgraph_node_id_required",
    "_subgraph_signature",
    "_subgraph_docstring",
    "_emit_subgraph_call_statement",
    "_subgraph_call_kwargs",
    "_subgraph_instance_port_candidate_names",
    "_subgraph_instance_widget_values",
    "_positional_ui_widget_names",
    "_ui_widget_values_by_name",
    "_subgraph_return_expr",
]


@dataclass(frozen=True, slots=True)
class _SubgraphPort:
    name: str
    type: str | None = None
    source_name: str | None = None
    external_ref: tuple[str, int] | None = None


@dataclass(frozen=True, slots=True)
class _SubgraphDef:
    id: str
    raw_name: str
    slug: str
    inputs: tuple[_SubgraphPort, ...]
    outputs: tuple[_SubgraphPort, ...]
    nodes: dict[str, Any]
    edges_in: dict[str, list[Any]]
    input_refs: dict[tuple[str, str], str]
    default_args: dict[str, Any]
    return_refs: tuple[tuple[str, int], ...]
    source_hash: str
    source_path: str | None = None
def slugify_subgraph_name(name: str, fallback_uuid: str) -> str:
    if not name:
        return f"subgraph_{fallback_uuid[:8].lower()}"
    name = re.sub(r"(?<=[A-Za-z])\.(?=\d)", "", name)
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug or slug[0].isdigit():
        slug = f"subgraph_{slug}" if slug else f"subgraph_{fallback_uuid[:8].lower()}"
    if _keyword.iskeyword(slug):
        slug = f"{slug}_"
    return slug


_GENERIC_SUBGRAPH_LABELS: frozenset[str] = frozenset(
    {
        "arg",
        "argument",
        "input",
        "inputs",
        "output",
        "outputs",
        "parameter",
        "param",
        "value",
    }
)


def _slugify_identifier(value: str) -> str:
    candidate = str(value or "").lower()
    candidate = re.sub(r"[^a-z0-9_]+", "_", candidate)
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    if _keyword.iskeyword(candidate):
        candidate = f"{candidate}_"
    return candidate


def _safe_kwarg_name(name: str, *, fallback: str) -> str:
    candidate = _slugify_identifier(str(name or ""))
    if not candidate or candidate[0].isdigit():
        candidate = _slugify_identifier(fallback)
    if not candidate or candidate[0].isdigit():
        candidate = "arg"
    return candidate


def _subgraph_input_kwarg_name(item: Mapping[str, Any], *, fallback: str) -> str:
    raw_name = str(item.get("name") or "")
    name_slug = _safe_kwarg_name(raw_name, fallback=fallback)
    label_raw = str(item.get("label") or "")
    label_slug = _slugify_identifier(label_raw)
    if (
        label_raw
        and label_slug
        and not label_slug[0].isdigit()
        and label_slug != name_slug
        and label_slug not in _GENERIC_SUBGRAPH_LABELS
    ):
        return label_slug
    return name_slug


def _unique_port_name(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _subgraph_definitions_from_raw(raw_workflow: dict[str, Any] | None, *, source_path: str | None) -> dict[str, _SubgraphDef]:
    if not isinstance(raw_workflow, dict):
        return {}
    raw_defs = raw_workflow.get("definitions")
    if not isinstance(raw_defs, dict):
        return {}
    raw_subgraphs = raw_defs.get("subgraphs")
    if isinstance(raw_subgraphs, Mapping):
        subgraph_items = list(raw_subgraphs.values())
    elif isinstance(raw_subgraphs, list):
        subgraph_items = raw_subgraphs
    else:
        return {}

    raw_by_id = {str(item.get("id")): item for item in subgraph_items if isinstance(item, dict) and item.get("id")}
    slugs = _disambiguated_subgraph_slugs(raw_by_id)
    out: dict[str, _SubgraphDef] = {}
    for subgraph_id, raw in raw_by_id.items():
        out[subgraph_id] = _build_subgraph_def(raw, slug=slugs[subgraph_id], source_path=source_path)
    return out


def _disambiguated_subgraph_slugs(raw_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    grouped: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for subgraph_id, raw in raw_by_id.items():
        grouped.setdefault(slugify_subgraph_name(str(raw.get("name") or ""), subgraph_id), []).append((subgraph_id, raw))

    slugs: dict[str, str] = {}
    for base, entries in grouped.items():
        if len(entries) == 1:
            slugs[entries[0][0]] = base
            continue
        ordered = sorted(entries, key=lambda item: (len(item[1].get("inputs") or ()), item[0]))
        min_inputs = len(ordered[0][1].get("inputs") or ())
        dual_used = False
        for index, (subgraph_id, raw) in enumerate(ordered):
            if index == 0:
                slugs[subgraph_id] = base
                continue
            input_count = len(raw.get("inputs") or ())
            if input_count > min_inputs and not dual_used:
                slugs[subgraph_id] = f"{base}_dual"
                dual_used = True
            else:
                slugs[subgraph_id] = f"{base}_{subgraph_id[:8].lower()}"
    return slugs


def _build_subgraph_def(raw: Mapping[str, Any], *, slug: str, source_path: str | None) -> _SubgraphDef:
    from vibecomfy.ingest.normalize import normalize_to_api
    from vibecomfy.porting.uid import make_uid, mint_local_uid
    from vibecomfy.workflow import VibeEdge as _Edge, VibeNode as _Node

    subgraph_id = str(raw["id"])
    used_input_names: set[str] = set()
    input_ports: list[_SubgraphPort] = []
    for index, item in enumerate(raw.get("inputs") or ()):
        if not isinstance(item, Mapping):
            continue
        source_name = str(item.get("name") or f"input_{index}")
        emitted_name = _unique_port_name(
            _subgraph_input_kwarg_name(item, fallback=f"input_{index}"),
            used_input_names,
        )
        input_ports.append(
            _SubgraphPort(
                emitted_name,
                str(item.get("type") or "") or None,
                source_name=source_name,
            )
        )
    declared_inputs = tuple(input_ports)

    used_output_names: set[str] = set()
    output_ports: list[_SubgraphPort] = []
    for index, item in enumerate(raw.get("outputs") or ()):
        if not isinstance(item, Mapping):
            continue
        source_name = str(item.get("name") or f"output_{index}")
        emitted_name = _unique_port_name(
            _safe_kwarg_name(source_name, fallback=f"output_{index}"),
            used_output_names,
        )
        output_ports.append(
            _SubgraphPort(
                emitted_name,
                str(item.get("type") or "") or None,
                source_name=source_name,
            )
        )
    outputs = tuple(output_ports)

    api = normalize_to_api({"nodes": list(raw.get("nodes") or ()), "links": list(raw.get("links") or ())}, use_comfy_converter=False)
    nodes: dict[str, Any] = {}
    edges_in: dict[str, list[Any]] = {}
    input_refs: dict[tuple[str, str], str] = {}
    defaults = _subgraph_default_args(raw, declared_inputs)

    for node_id, node in api.items():
        class_type = str(node.get("class_type", "Unknown"))
        if class_type in UI_ONLY_CLASS_TYPES:
            continue
        raw_inputs = dict(node.get("inputs", {}))
        static_inputs: dict[str, Any] = {}
        widgets: dict[str, Any] = {}
        for key, value in raw_inputs.items():
            if _is_any_link(value) and str(value[0]) == "-10":
                static_inputs[str(key)] = value
                continue
            if _is_any_link(value):
                continue
            if str(key).startswith("widget_"):
                widgets[str(key)] = value
            else:
                static_inputs[str(key)] = value
        metadata = {key: value for key, value in node.items() if key not in {"class_type", "inputs"}}
        output_names = _ui_output_names(metadata.get("_ui"))
        if output_names:
            metadata.setdefault("output_names", output_names)
        nodes[str(node_id)] = _Node(
            str(node_id),
            class_type,
            inputs=static_inputs,
            widgets=widgets,
            metadata=metadata,
            uid=make_uid(subgraph_id, mint_local_uid(metadata.get("_ui"), str(node_id))),
        )

    for node_id, node in api.items():
        if not isinstance(node, Mapping):
            continue
        for key, value in dict(node.get("inputs", {})).items():
            if not _is_any_link(value):
                continue
            from_node, from_slot = str(value[0]), int(value[1])
            if from_node == "-10":
                if 0 <= from_slot < len(input_ports):
                    input_refs[(str(node_id), str(key))] = input_ports[from_slot].name
            else:
                if str(node_id) not in nodes:
                    continue
                if from_node not in nodes:
                    input_name = _unique_port_name(
                        _safe_kwarg_name(str(key), fallback=f"input_{len(input_ports)}"),
                        used_input_names,
                    )
                    input_ports.append(
                        _SubgraphPort(
                            input_name,
                            None,
                            source_name=str(key),
                            external_ref=(from_node, from_slot),
                        )
                    )
                    nodes[str(node_id)].inputs[str(key)] = ["-10", len(input_ports) - 1]
                    input_refs[(str(node_id), str(key))] = input_name
                    continue
                edge = _Edge(from_node, str(from_slot), str(node_id), str(key))
                edges_in.setdefault(str(node_id), []).append(edge)

    inputs = tuple(input_ports)

    return_refs: list[tuple[str, int]] = []
    links = [link for link in raw.get("links") or () if isinstance(link, Mapping)]
    for index, _output in enumerate(outputs):
        target = next((link for link in links if str(link.get("target_id")) == "-20" and int(link.get("target_slot", -1)) == index), None)
        if target is not None:
            return_refs.append((str(target.get("origin_id")), int(target.get("origin_slot", 0))))

    return _SubgraphDef(
        id=subgraph_id,
        raw_name=str(raw.get("name") or ""),
        slug=slug,
        inputs=inputs,
        outputs=outputs,
        nodes=nodes,
        edges_in=edges_in,
        input_refs=input_refs,
        default_args=defaults,
        return_refs=tuple(return_refs),
        source_hash=subgraph_source_hash(
            raw,
            slug=slug,
            input_names=[port.name for port in inputs],
            return_refs=return_refs,
            runtime_graph=api,
        ),
        source_path=source_path,
    )


def subgraph_source_hash(
    raw: Mapping[str, Any],
    *,
    slug: str | None = None,
    input_names: list[str] | None = None,
    return_refs: list[tuple[str, int]] | None = None,
    runtime_graph: Mapping[str, Any] | None = None,
) -> str:
    payload = {
        "id": str(raw.get("id") or ""),
        "name": str(raw.get("name") or ""),
        "slug": slug,
        "runtime_graph": runtime_graph or {},
        "inputs": raw.get("inputs") or [],
        "outputs": raw.get("outputs") or [],
        "nodes": raw.get("nodes") or [],
        "links": raw.get("links") or [],
        "emitted_input_names": input_names or [],
        "return_refs": return_refs or [],
    }
    rendered = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _subgraph_default_args(raw: Mapping[str, Any], inputs: tuple[_SubgraphPort, ...]) -> dict[str, Any]:
    nodes = {str(node.get("id")): node for node in raw.get("nodes") or () if isinstance(node, Mapping)}
    links = {int(link.get("id")): link for link in raw.get("links") or () if isinstance(link, Mapping) and link.get("id") is not None}
    defaults: dict[str, Any] = {}
    for index, input_item in enumerate(raw.get("inputs") or ()):
        if not isinstance(input_item, Mapping) or index >= len(inputs):
            continue
        for link_id in input_item.get("linkIds") or ():
            link = links.get(int(link_id))
            if link is None:
                continue
            node = nodes.get(str(link.get("target_id")))
            if node is None:
                continue
            value = _widget_default_for_target(node, int(link.get("target_slot", -1)))
            if value is not None:
                defaults[inputs[index].name] = value
                break
    return defaults


def _widget_default_for_target(node: Mapping[str, Any], target_slot: int) -> Any:
    input_items = [item for item in node.get("inputs") or () if isinstance(item, Mapping)]
    if target_slot < 0 or target_slot >= len(input_items):
        return None
    target_input = input_items[target_slot]
    widget = target_input.get("widget")
    if not isinstance(widget, Mapping):
        return None
    widget_name = str(widget.get("name") or target_input.get("name") or "")
    return _ui_widget_values_by_name(node).get(widget_name)


def _apply_subgraph_names_to_prepared(prepared: dict[str, Any]) -> None:
    subgraphs: dict[str, _SubgraphDef] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return
    used = {str(var) for var in prepared.get("var_names", {}).values()}
    var_names: dict[str, str] = prepared["var_names"]
    output_var_names: dict[str, dict[int, str]] = prepared.setdefault("output_var_names", {})
    for node_id, node in prepared["nodes"].items():
        subgraph = subgraphs.get(str(node.class_type))
        if subgraph is None:
            continue
        getattr(node, "metadata", {}).setdefault("output_names", [port.name for port in subgraph.outputs])
        old = var_names.get(str(node_id))
        if old in used:
            used.remove(old)
        if len(subgraph.outputs) > 1:
            slot_vars: dict[int, str] = {}
            for index, output in enumerate(subgraph.outputs):
                slot_vars[index] = _unique_var(_safe_var(output.name.lower()), used)
            output_var_names[str(node_id)] = slot_vars
            # Avoid collision: var name must not equal subgraph function name
            base = _subgraph_result_base(subgraph.slug)
            if base == subgraph.slug:
                base = f"{subgraph.slug}_result"
            var_names[str(node_id)] = _unique_var(base, used)
        else:
            base = _subgraph_result_base(subgraph.slug)
            if base == subgraph.slug:
                base = f"{subgraph.slug}_result"
            var_names[str(node_id)] = _unique_var(base, used)


def _subgraph_result_base(slug: str) -> str:
    if slug.startswith("image_edit"):
        return "edited_dual" if slug.endswith("_dual") else "edited"
    if slug.startswith("text_to_image"):
        return "edited"
    return slug


def _unique_var(base: str, used: set[str]) -> str:
    candidate = base
    index = 2
    while candidate in used or _keyword.iskeyword(candidate):
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate
COMFY_TYPE_TO_PY_HINT = {
    "STRING": "str",
    "INT": "int",
    "FLOAT": "float",
    "BOOLEAN": "bool",
    "COMBO": "str",
}


def _emit_subgraph_functions(
    prepared: dict[str, Any],
    *,
    diagnostics: list[EmissionDiagnostic] | None,
    constant_map: dict[tuple[str, str], str] | None,
    required_ids_by_subgraph: dict[str, set[str]] | None = None,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
) -> list[str]:
    # Deferred import to avoid circular dependency (emitter ↔ emit_subgraph).
    from vibecomfy.porting.emitter import _emit_build_function  # noqa: PLC0415

    subgraphs: dict[str, _SubgraphDef] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return []
    lines = ["# === Subgraph functions ===", ""]
    for subgraph_id in _subgraph_topological_order(subgraphs):
        subgraph = subgraphs[subgraph_id]
        inner_prepared = {
            "nodes": subgraph.nodes,
            "edges_in": subgraph.edges_in,
            "var_names": _compute_variable_names(subgraph.nodes, [edge for edges in subgraph.edges_in.values() for edge in edges]),
            "subgraph_definitions": subgraphs,
        }
        _apply_locked_variable_names(
            subgraph.nodes,
            inner_prepared["var_names"],
            variable_name_locks=variable_name_locks,
            strict=strict_variable_name_locks,
            diagnostics=diagnostics,
            scope_path=subgraph.id,
        )
        inner_prepared["output_var_names"] = _compute_output_variable_names(
            subgraph.nodes,
            inner_prepared["var_names"],
            [edge for edges in subgraph.edges_in.values() for edge in edges],
        )
        _apply_subgraph_names_to_prepared(inner_prepared)
        signature = _subgraph_signature(subgraph)
        docstring = _subgraph_docstring(subgraph)
        lines.extend(
            _emit_build_function(
                inner_prepared,
                workflow_id_expr="READY_METADATA",
                source_path_expr="__file__",
                source_type="ready_template",
                source_provenance=None,
                registered_inputs=None,
                public_inputs=None,
                tail_lines=[],
                diagnostics=diagnostics,
                use_shared_helpers=True,
                constant_map=constant_map,
                section_groups={},
                function_name=subgraph.slug,
                function_signature=signature,
                function_docstring=docstring,
                return_refs=subgraph.return_refs,
                external_refs=subgraph.input_refs,
                node_id_prefix=subgraph.id,
                required_ids=required_ids_by_subgraph.get(subgraph.id, set()) if required_ids_by_subgraph is not None else None,
            )
        )
        lines.append("")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines
def _subgraph_topological_order(subgraphs: dict[str, _SubgraphDef]) -> list[str]:
    deps = {
        subgraph_id: {
            str(node.class_type)
            for node in subgraph.nodes.values()
            if str(node.class_type) in subgraphs
        }
        for subgraph_id, subgraph in subgraphs.items()
    }
    temporary: set[str] = set()
    permanent: set[str] = set()
    ordered: list[str] = []

    def visit(subgraph_id: str, stack: list[str]) -> None:
        if subgraph_id in permanent:
            return
        if subgraph_id in temporary:
            cycle = " -> ".join([*stack, subgraph_id])
            raise RuntimeError(f"Circular subgraph reference detected: {cycle}")
        temporary.add(subgraph_id)
        for dep in sorted(deps.get(subgraph_id, ())):
            visit(dep, [*stack, subgraph_id])
        temporary.remove(subgraph_id)
        permanent.add(subgraph_id)
        ordered.append(subgraph_id)

    for subgraph_id in subgraphs:
        visit(subgraph_id, [])
    return ordered
def _short_subgraph_id_prefix(subgraph_id: str) -> str:
    if len(subgraph_id) >= 32 and "-" in subgraph_id:
        return subgraph_id[:8]
    return subgraph_id
def _subgraph_emitted_node_id(subgraph_id: str, node_id: str) -> str:
    return f"{_short_subgraph_id_prefix(subgraph_id)}:{node_id}"
def _subgraph_node_id_required(
    node_id_prefix: str | None,
    nid: str,
    required_ids: set[str] | None,
) -> bool:
    """Return True if a subgraph node's explicit _id= kwarg is load-bearing.

    When *required_ids* is None, all node IDs are considered required (backward
    compatibility for paths that do not supply the precomputed set).  Otherwise
    only nodes whose inner ID appears in the set need an explicit _id=.
    """
    if required_ids is None:
        return True
    return nid in required_ids
def _subgraph_signature(subgraph: _SubgraphDef) -> str:
    if not subgraph.inputs:
        return f"def {subgraph.slug}():"
    lines = [f"def {subgraph.slug}("]
    lines.append("    *,")
    for port in subgraph.inputs:
        hint = COMFY_TYPE_TO_PY_HINT.get(str(port.type or "").upper())
        annotation = f": {hint}" if hint else ""
        lines.append(f"    {port.name}{annotation},")
    lines.append("):")
    return "\n".join(lines)
def _subgraph_docstring(subgraph: _SubgraphDef) -> list[str]:
    title = subgraph.raw_name or subgraph.slug.replace("_", " ").title()
    variant = ""
    image_inputs = sum(1 for port in subgraph.inputs if str(port.type or "").upper() == "IMAGE")
    if image_inputs == 1:
        variant = " - single-image variant"
    elif image_inputs > 1:
        variant = " - two-image variant" if image_inputs == 2 else f" - {image_inputs}-image variant"
    source = f" in {subgraph.source_path}" if subgraph.source_path else ""
    classes = [str(node.class_type) for node in subgraph.nodes.values()]
    class_counts = Counter(classes)
    inner = []
    seen: set[str] = set()
    for cls in classes:
        if cls in seen:
            continue
        seen.add(cls)
        count = class_counts[cls]
        inner.append(f"{cls}x{count}" if count > 1 else cls)
    lines = [
        f'    """{title}{variant}.',
        "",
        f"    Materialized from subgraph {subgraph.id}{source}.",
        f"    # vibecomfy source hash: sha256:{subgraph.source_hash}",
    ]
    if inner:
        lines.append(f"    Inner nodes: {', '.join(inner)}.")
    lines.append('    """')
    return lines
def _emit_subgraph_call_statement(
    node: Any,
    subgraph: _SubgraphDef,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    workflow_nodes: dict[str, Any],
    *,
    body_indent: str,
    continuation_indent: str,
    diagnostics: list[EmissionDiagnostic] | None,
) -> list[str]:
    live_output_slots = _live_output_slots_for_function(
        workflow_nodes,
        edges_in,
        output_var_names,
    )
    assignment_target = _assignment_target(
        var_names[str(node.id)],
        output_var_names.get(str(node.id)),
        live_slots=live_output_slots.get(str(node.id)),
    )
    kwargs = _subgraph_call_kwargs(
        node,
        subgraph,
        edges_in,
        var_names,
        output_var_names,
        workflow_nodes,
        diagnostics=diagnostics,
    )
    kwarg_lines = [f"{key}={expr}" for key, expr in kwargs]
    call_expr = f"{subgraph.slug}({', '.join(kwarg_lines)})"
    single_line = (
        f"{body_indent}{assignment_target} = {call_expr}"
        if assignment_target is not None
        else f"{body_indent}{call_expr}"
    )
    if len(kwargs) > 3 or len(single_line) > 88:
        head = f"{body_indent}{subgraph.slug}(" if assignment_target is None else f"{body_indent}{assignment_target} = {subgraph.slug}("
        lines = [head]
        for key, expr in kwargs:
            lines.append(f"{continuation_indent}{key}={expr},")
        lines.append(f"{body_indent})")
        return lines
    return [single_line]
def _subgraph_call_kwargs(
    node: Any,
    subgraph: _SubgraphDef,
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    workflow_nodes: dict[str, Any],
    *,
    diagnostics: list[EmissionDiagnostic] | None,
) -> list[tuple[str, str]]:
    incoming: dict[str, tuple[str, int]] = {}
    for edge in edges_in.get(str(node.id), []):
        incoming[str(edge.to_input)] = (str(edge.from_node), int(edge.from_output))
    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
        if _is_link(value):
            incoming.setdefault(str(key), (str(value[0]), int(value[1])))

    static = {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}
    widget_values = _subgraph_instance_widget_values(node)
    port_candidate_names = _subgraph_instance_port_candidate_names(node, subgraph)
    kwargs: list[tuple[str, str]] = []
    for index, port in enumerate(subgraph.inputs):
        if port.external_ref is not None:
            src, slot = port.external_ref
            kwargs.append(
                (
                    port.name,
                    _edge_ref_expr(
                        workflow_nodes,
                        var_names,
                        output_var_names,
                        src,
                        slot,
                        bare_single_output_refs=True,
                        diagnostics=diagnostics,
                        target_node=node,
                        target_input=port.name,
                    ),
                )
            )
            continue
        candidate_names = port_candidate_names.get(index, (port.name, port.source_name or port.name))
        incoming_name = next((name for name in candidate_names if name in incoming), None)
        widget_name = next((name for name in candidate_names if name in widget_values), None)
        static_name = next((name for name in candidate_names if name in static), None)
        default_name = next((name for name in candidate_names if name in subgraph.default_args), None)
        if incoming_name is not None:
            src, slot = incoming[incoming_name]
            kwargs.append(
                (
                    port.name,
                    _edge_ref_expr(
                        workflow_nodes,
                        var_names,
                        output_var_names,
                        src,
                        slot,
                        bare_single_output_refs=True,
                        diagnostics=diagnostics,
                        target_node=node,
                        target_input=incoming_name,
                    ),
                )
            )
        elif widget_name is not None:
            kwargs.append((port.name, _format_value(widget_values[widget_name])))
        elif static_name is not None and not _is_link(static[static_name]):
            kwargs.append((port.name, _format_value(static[static_name])))
        elif default_name is not None:
            kwargs.append((port.name, _format_value(subgraph.default_args[default_name])))
        else:
            kwargs.append((port.name, "None"))
            if diagnostics is not None:
                from vibecomfy.porting.emitter import EmissionDiagnostic  # noqa: PLC0415
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
                        message=(
                            f"Subgraph input {port.name!r} on node {node.id} "
                            f"({subgraph.id}) has no incoming edge or widget value; emitting None."
                        ),
                        severity="warning",
                        node_id=str(node.id),
                        class_type=str(getattr(node, "class_type", "")),
                        detail={"subgraph_id": subgraph.id, "input_name": port.name},
                    )
                )
    return kwargs
def _subgraph_instance_port_candidate_names(node: Any, subgraph: _SubgraphDef) -> dict[int, tuple[str, ...]]:
    ui = getattr(node, "metadata", {}).get("_ui")
    input_items = [item for item in (ui or {}).get("inputs") or () if isinstance(item, Mapping)] if isinstance(ui, Mapping) else []
    out: dict[int, tuple[str, ...]] = {}
    for index, port in enumerate(subgraph.inputs):
        names: list[str] = []

        def add(value: Any) -> None:
            name = str(value or "")
            if name and name not in names:
                names.append(name)

        add(port.name)
        add(port.source_name)
        for item in input_items:
            raw_name = str(item.get("name") or "")
            label_slug = _slugify_identifier(str(item.get("label") or ""))
            identity = {name for name in (raw_name, label_slug) if name}
            if port.name not in identity and (port.source_name or "") not in identity:
                continue
            add(raw_name)
            add(label_slug)
            if not raw_name and item.get("link") is not None:
                add(f"_un{item.get('link')}")
        out[index] = tuple(names)
    return out
def _subgraph_instance_widget_values(node: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
        if _is_link(value):
            continue
        translated = _translate_widget_for_key(str(key), aliases, str(getattr(node, "class_type", "")))
        values[translated or str(key)] = value

    ui = getattr(node, "metadata", {}).get("_ui")
    if not isinstance(ui, Mapping):
        return values
    values.update(_ui_widget_values_by_name(ui))
    input_items = [item for item in ui.get("inputs") or () if isinstance(item, Mapping)]
    for item in input_items:
        widget = item.get("widget")
        if not isinstance(widget, Mapping):
            continue
        input_name = str(item.get("name") or widget.get("name") or "")
        if not input_name or input_name in values:
            continue
        for value_key in ("value", "default", "default_value"):
            if value_key in item:
                values[input_name] = item[value_key]
                break
    return values
def _positional_ui_widget_names(ui_node: Mapping[str, Any], value_count: int) -> list[str | None]:
    """Return authoritative names for positional ``widgets_values`` slots.

    The list is intentionally keyed by widget-value position, not input-item
    position.  Callers must only consume positions with a real non-empty name so
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
def _subgraph_return_expr(
    return_refs: tuple[tuple[str, int], ...],
    workflow_nodes: dict[str, Any],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    diagnostics: list[EmissionDiagnostic] | None,
) -> str:
    refs = [
        _edge_ref_expr(
            workflow_nodes,
            var_names,
            output_var_names,
            node_id,
            slot,
            bare_single_output_refs=True,
            diagnostics=diagnostics,
            target_node=None,
            target_input="return",
        )
        for node_id, slot in return_refs
    ]
    if not refs:
        return "None"
    return ", ".join(refs)
