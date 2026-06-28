"""Subgraph definition parsing and identity helpers."""

from __future__ import annotations

import hashlib
import json
import keyword
import re
from dataclasses import dataclass
from typing import Any, Mapping

from vibecomfy.porting.emit.node_kwargs_core import _is_any_link, _ui_widget_values_by_name
from vibecomfy.porting.emit.wrappers import UI_ONLY_CLASS_TYPES


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
    if keyword.iskeyword(slug):
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
    if keyword.iskeyword(candidate):
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
    from vibecomfy.identity.uid import make_uid, mint_local_uid
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


def _ui_output_names(ui: Any) -> list[str]:
    if not isinstance(ui, Mapping):
        return []
    names: list[str] = []
    for item in ui.get("outputs") or ():
        if isinstance(item, Mapping):
            names.append(str(item.get("name") or ""))
    return names


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
