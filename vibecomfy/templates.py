from __future__ import annotations

import warnings
import json
import re
import tomllib
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import inspect
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping
from urllib.parse import urlsplit

from vibecomfy.handles import Handle
from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_input, bind_output, ready_node, ready_workflow
from vibecomfy.utils import find_repo_root
from vibecomfy.workflow import VibeInput, VibeOutput, VibeWorkflow
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
from vibecomfy.workflow_context import _current_workflow_or_raise
from vibecomfy.ingest.normalize import (
    door_links,
    door_setdefault_links,
    door_setdefault_nodes,
)
from vibecomfy.model_assets import reconcile_model_requirements


_COMPANION_SCOPE_NODES_KEY = "nodes"


def _record_recursive_definition_capture(
    workflow: VibeWorkflow,
    scope_path: str,
    nodes: tuple[Any, ...],
) -> None:
    """Capture constructor products for the canonical recursive emitter.

    This is deliberately a small bridge over the existing ``VibeWorkflow``
    constructor kernel.  It records object references, never a second node or
    link model; :func:`materialize_recursive_definitions` turns those objects
    into the ordinary JSON-shaped definition payload after all constructors
    have run.
    """
    captured = getattr(workflow, "_recursive_definition_captures", None)
    if captured is None:
        return
    captured.append((str(scope_path), tuple(getattr(item, "node", item) for item in nodes)))


@contextmanager
def recursive_definition_scope(workflow: VibeWorkflow):
    """Temporarily collect recursive constructor products on one workflow.

    The generated source uses this small public context boundary so failed
    recursive builds restore the caller's capture state without embedding
    general-purpose exception machinery in the readable Python surface.
    """
    previous = getattr(workflow, "_recursive_definition_captures", None)
    original_nodes = dict(workflow.nodes)
    original_edges = list(workflow.edges)
    original_inputs = dict(workflow.inputs)
    original_outputs = list(workflow.outputs)
    original_id_map = dict(workflow._id_map)
    original_uid_counter = workflow._uid_counter
    rebound = workflow._workflow_context_token is None
    if rebound:
        workflow.__enter__()
    workflow._recursive_definition_captures = []
    try:
        yield
    finally:
        # Recursive constructors execute through the normal node kernel, which
        # necessarily appends their temporary products to the active workflow.
        # Keep those objects available to materialization, then restore the
        # caller's root IR so nested nodes cannot masquerade as root nodes.
        workflow.nodes = original_nodes
        workflow.edges = original_edges
        workflow.inputs = original_inputs
        workflow.outputs = original_outputs
        workflow._id_map = original_id_map
        workflow._uid_counter = original_uid_counter
        workflow._recursive_definition_captures = previous
        if rebound:
            workflow.__exit__(None, None, None)


def materialize_recursive_definitions(
    workflow: VibeWorkflow,
    captures: list[tuple[str, tuple[Any, ...]]],
    custody: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build recursive definitions from executed constructor products.

    ``custody`` contains only definition shape and stable identity fields.  All
    semantic node values and topology below ``nodes``/``links`` come from the
    temporary workflow populated by the emitted helper functions, so changing
    a nested constructor or default cannot be shadowed by a replay literal.
    A direct renderer preview has no companion; in that narrow case derive a
    minimal structural witness from the captured constructor objects rather
    than putting a second graph-shaped manifest in generated Python.
    """
    by_scope = {scope: tuple(nodes) for scope, nodes in captures}

    def entries(value: Any) -> list[Any]:
        if isinstance(value, Mapping) and "subgraphs" in value:
            return list(value["subgraphs"])
        if isinstance(value, Mapping):
            return list(value.values())
        return list(value) if isinstance(value, (list, tuple)) else []

    def structural_roster(value: Any) -> list[Any] | None:
        if not isinstance(value, (list, tuple)):
            return None
        return [
            {
                **{
                    key: deepcopy(item[key])
                    for key in ("name", "type", "slot")
                    if key in item
                },
                "_has_link": "link" in item,
                "_has_value": "value" in item,
            }
            if isinstance(item, Mapping) else item
            for item in value
        ]

    def source_records(definition: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Project an inline source definition into constructor identity custody."""
        from vibecomfy.ingest.normalize import canonical_definition_links, canonical_definition_nodes

        raw_nodes = canonical_definition_nodes(definition)
        values = raw_nodes.values() if isinstance(raw_nodes, Mapping) else raw_nodes
        if not isinstance(values, (list, tuple)):
            return []
        records: list[dict[str, Any]] = []
        for index, raw in enumerate(values):
            if not isinstance(raw, Mapping):
                continue
            node_id = str(raw.get("uid") or raw.get("id") or f"node_{index}")
            class_type = str(raw.get("class_type", raw.get("type", "")))
            if not class_type:
                continue
            raw_inputs = raw.get("inputs")
            records.append({
                "id": node_id,
                "uid": raw.get("uid"),
                "class_type": class_type,
                "node_field": "type" if "type" in raw and "class_type" not in raw else "class_type",
                "input_shape": structural_roster(raw_inputs),
                "output_shape": structural_roster(raw.get("outputs")),
            })

        # Match the constructor helper's stable dependency order so captured
        # runtime products zip to the same source identities on a standalone
        # conversion that has no sibling companion.
        # Source metadata may preserve UI order; normalized definitions begin
        # from canonical lexical-id order before dependency ordering.
        records.sort(key=lambda record: record["id"])
        raw_links = canonical_definition_links(definition)
        dependencies = {record["id"]: set() for record in records}
        for link in raw_links if isinstance(raw_links, (list, tuple)) else ():
            if isinstance(link, Mapping):
                source = link.get("from_node", link.get("origin_id"))
                target = link.get("to_node", link.get("target_id"))
            elif isinstance(link, (list, tuple)) and len(link) >= 5:
                source, target = link[1], link[3]
            else:
                continue
            source_key, target_key = str(source), str(target)
            if source_key in dependencies and target_key in dependencies:
                dependencies[target_key].add(source_key)
        ordered: list[dict[str, Any]] = []
        remaining = list(records)
        while remaining:
            ready = [
                record for record in remaining
                if not (dependencies[record["id"]] & {item["id"] for item in remaining})
            ]
            if not ready:
                return records
            ordered.extend(ready)
            remaining = [record for record in remaining if record not in ready]
        return ordered

    def source_custody(value: Any) -> dict[str, Any] | None:
        """Create compact structural custody from existing inline metadata."""
        from vibecomfy.identity.scope import sg_key

        if value is None or value == {} or value == []:
            return None

        def build(definition: Mapping[str, Any]) -> dict[str, Any]:
            key = sg_key(definition)
            result = {
                str(field): deepcopy(definition[field])
                for field in ("id", "name")
                if field in definition
            }
            result["_scope_key"] = key
            result["_constructor_nodes"] = source_records(definition)
            nested = definition.get("definitions")
            if nested not in (None, {}, []):
                result["definitions"] = {
                    "subgraphs": [
                        build(item)
                        for item in entries(nested)
                        if isinstance(item, Mapping)
                    ]
                }
            return result

        return {"subgraphs": [
            build(item) for item in entries(value) if isinstance(item, Mapping)
        ]}

    if custody is None:
        # Standalone previews are intentionally companion-free.  The captured
        # builders still provide the stable local order, ids and classes needed
        # to materialize a definition; the full source-backed shapes are only
        # required by the published v2 companion path.
        local_edges = list(workflow.edges)

        def preview_shape(node: Any, *, output: bool) -> list[dict[str, Any]] | None:
            source_node = getattr(node, "node", node)
            node_id = str(getattr(source_node, "id", ""))
            if output and not any(str(edge.from_node) == node_id for edge in local_edges):
                return None
            if not output and not any(str(edge.to_node) == node_id for edge in local_edges):
                return None
            if output:
                names = getattr(source_node, "native_output_names", None)
                types = getattr(source_node, "native_output_types", None)
                if not isinstance(names, (list, tuple)):
                    slots = sorted({
                        int(edge.from_output)
                        for edge in local_edges
                        if str(edge.from_node) == node_id
                        and str(edge.from_output).isdigit()
                    })
                    if not slots:
                        return None
                    names = [str(slot) for slot in range(max(slots) + 1)]
                rows = []
                for slot, name in enumerate(names):
                    row: dict[str, Any] = {"name": name}
                    if isinstance(types, (list, tuple)) and slot < len(types) and types[slot] is not None:
                        row["type"] = types[slot]
                    if any(
                        str(edge.from_node) == node_id
                        and str(edge.from_output) == str(slot)
                        for edge in local_edges
                    ):
                        row["_has_link"] = True
                    rows.append(row)
                return rows
            inputs = getattr(source_node, "inputs", {})
            names = getattr(source_node, "native_input_names", None)
            types = getattr(source_node, "native_input_types", None)
            if not isinstance(names, (list, tuple)):
                names = list(inputs) if isinstance(inputs, Mapping) else []
            rows = []
            for slot, name in enumerate(names):
                if name is None:
                    continue
                field = str(name)
                row = {"name": name}
                if isinstance(types, (list, tuple)) and slot < len(types) and types[slot] is not None:
                    row["type"] = types[slot]
                has_link = any(
                    str(edge.to_node) == node_id
                    and str(edge.to_input) == field
                    for edge in local_edges
                )
                if has_link:
                    row["_has_link"] = True
                if isinstance(inputs, Mapping) and field in inputs:
                    row["_has_value"] = True
                rows.append(row)
            return rows or None

        metadata_definitions = getattr(workflow, "metadata", {}).get("definitions")
        if metadata_definitions is None or metadata_definitions == {} or metadata_definitions == []:
            # Direct callers may retain the canonical recursive source on the
            # workflow itself without wrapping it in ready-template metadata.
            # That source is still the authority; synthetic capture is only a
            # last resort when neither representation exists.
            metadata_definitions = getattr(workflow, "definitions", None)
        custody = source_custody(metadata_definitions)

        synthetic_root: dict[str, Any] = {"subgraphs": []}
        by_path: dict[tuple[str, ...], dict[str, Any]] = {}
        if custody is None:
            for scope_path, captured_nodes in captures:
                parts = tuple(part for part in str(scope_path).split("/") if part)
                if not parts:
                    continue
                for depth in range(1, len(parts) + 1):
                    path = parts[:depth]
                    if path in by_path:
                        continue
                    definition = {
                        "_scope_key": path[-1],
                        "_constructor_nodes": [],
                    }
                    by_path[path] = definition
                    if depth == 1:
                        synthetic_root["subgraphs"].append(definition)
                    else:
                        parent = by_path[path[:-1]]
                        parent.setdefault("definitions", {"subgraphs": []})["subgraphs"].append(definition)
                definition = by_path[parts]
                definition["_constructor_nodes"] = [
                    {
                        "id": str(getattr(getattr(node, "node", node), "id", index)),
                        "uid": str(getattr(getattr(node, "node", node), "uid", "")) or None,
                        "class_type": str(getattr(getattr(node, "node", node), "class_type", "")),
                        "node_field": "type",
                        "input_shape": preview_shape(node, output=False),
                        "output_shape": preview_shape(node, output=True),
                    }
                    for index, node in enumerate(captured_nodes)
                ]
            custody = synthetic_root

    def node_payload(node: Any, identity: Mapping[str, Any], link_by_target: Mapping[tuple[str, str], int], links_by_source: Mapping[tuple[str, str], list[int]]) -> dict[str, Any]:
        is_handle = hasattr(node, "node_id") and hasattr(node, "output_slot")
        source_node = None if is_handle else getattr(node, "node", node)
        values = deepcopy(getattr(source_node, "inputs", {})) if source_node is not None else {}
        widgets = deepcopy(getattr(source_node, "widgets", {})) if source_node is not None else {}
        input_shape = identity.get("input_shape")
        if isinstance(input_shape, (list, tuple)) and input_shape:
            rows = []
            for item in input_shape:
                if not isinstance(item, Mapping):
                    continue
                row = deepcopy(dict(item))
                field = str(item.get("name"))
                link_id = link_by_target.get((str(identity.get("id")), field))
                if link_id is not None or row.get("_has_link"):
                    row["link"] = link_id
                if row.get("_has_value") or (
                    row.get("_has_link")
                    and link_id is None
                    and str(identity.get("class_type")) in {
                        "PrimitiveBoolean", "PrimitiveFloat", "PrimitiveInt",
                        "PrimitiveString", "PrimitiveStringMultiline",
                    }
                    and isinstance(values, Mapping)
                    and field in values
                ):
                    row["value"] = deepcopy(values.get(field)) if isinstance(values, Mapping) else None
                row.pop("_has_link", None)
                row.pop("_has_value", None)
                rows.append(row)
            values = rows
        payload = {
            "id": identity.get("id"),
            "inputs": values,
        }
        if widgets:
            payload["widgets"] = widgets
        node_field = str(identity.get("node_field", "class_type"))
        payload[node_field] = str(getattr(source_node, "class_type", identity.get("class_type", "")))
        if identity.get("uid") is not None:
            payload["uid"] = identity["uid"]
        if isinstance(identity.get("output_shape"), (list, tuple)):
            payload["outputs"] = []
            for slot, item in enumerate(identity["output_shape"]):
                row = deepcopy(item) if isinstance(item, Mapping) else {"name": item}
                source_links = links_by_source.get((str(identity.get("id")), str(slot)))
                if source_links:
                    if "links" in row:
                        door_links(row)[:] = list(source_links)
                    else:
                        door_setdefault_links(row, list(source_links))
                payload["outputs"].append(row)
        for field in (
            "native_input_names", "native_output_names", "native_input_types",
            "native_output_types", "native_input_optional", "native_input_asset_kinds",
            "native_output_slots",
        ):
            value = getattr(node, field, None)
            if field in identity and value is not None:
                payload[field] = deepcopy(value)
        return payload

    def build_definition(definition: Mapping[str, Any], parents: tuple[str, ...]) -> dict[str, Any]:
        key = str(definition.get("_scope_key") or definition.get("sg_key") or definition.get("id") or definition.get("name"))
        scope = "/".join((*parents, key))
        result = {
            key_name: deepcopy(value)
            for key_name, value in definition.items()
            if key_name not in {"nodes", "links", "definitions"} and not str(key_name).startswith("_")
        }
        result["_scope_key"] = key
        identities = definition.get("_constructor_nodes", ())
        runtime_nodes = list(by_scope.get(scope, ()))
        if not isinstance(identities, (list, tuple)):
            identities = ()
        runtime_ids = {
            str(getattr(node, "id", getattr(node, "node_id", "")))
            for node in runtime_nodes
            if not (hasattr(node, "node_id") and hasattr(node, "output_slot"))
        }
        remap = {
            str(getattr(node, "id", getattr(node, "node_id", ""))): str(identity.get("id"))
            for node, identity in zip(runtime_nodes, identities)
            if isinstance(identity, Mapping)
        }
        links: list[list[Any]] = []
        link_by_target: dict[tuple[str, str], int] = {}
        links_by_source: dict[tuple[str, str], list[int]] = {}
        for index, edge in enumerate(workflow.edges):
            source = str(edge.from_node)
            target = str(edge.to_node)
            if source in runtime_ids and target in runtime_ids:
                link_id = len(links) + 1
                link_by_target[(remap[target], str(edge.to_input))] = link_id
                links_by_source.setdefault((remap[source], str(edge.from_output)), []).append(link_id)
                target_identity = next(
                    (item for item in identities if isinstance(item, Mapping) and str(item.get("id")) == remap[target]),
                    {},
                )
                source_identity = next(
                    (item for item in identities if isinstance(item, Mapping) and str(item.get("id")) == remap[source]),
                    {},
                )
                target_slot: Any = edge.to_input
                link_type: Any = None
                target_shape = target_identity.get("input_shape")
                if isinstance(target_shape, (list, tuple)):
                    for slot, item in enumerate(target_shape):
                        if isinstance(item, Mapping) and str(item.get("name")) == str(edge.to_input):
                            target_slot = slot
                            break
                source_shape = source_identity.get("output_shape")
                if isinstance(source_shape, (list, tuple)):
                    source_slot = int(edge.from_output) if str(edge.from_output).isdigit() else None
                    if source_slot is not None and 0 <= source_slot < len(source_shape):
                        source_item = source_shape[source_slot]
                        if isinstance(source_item, Mapping):
                            link_type = source_item.get("type")
                links.append([
                    link_id,
                    remap[source],
                    int(edge.from_output) if str(edge.from_output).isdigit() else edge.from_output,
                    remap[target],
                    target_slot,
                    link_type,
                ])
        door_setdefault_nodes(result, [
            node_payload(node, identity, link_by_target, links_by_source)
            for node, identity in zip(runtime_nodes, identities)
            if isinstance(identity, Mapping)
        ])
        door_setdefault_links(result, links)
        nested = definition.get("definitions")
        if nested not in (None, {}, []):
            result["definitions"] = {"subgraphs": [
                build_definition(child, (*parents, key))
                for child in entries(nested)
                if isinstance(child, Mapping)
            ]}
        return result

    return {"subgraphs": [
        build_definition(definition, ())
        for definition in entries(custody)
        if isinstance(definition, Mapping)
    ]}


_OUTPUT_KIND_HEURISTIC: dict[str, str] = {
    "SaveImage": "image",
    "PreviewImage": "image",
    "SaveVideo": "video",
    "VHS_VideoCombine": "video",
    "CreateVideo": "video",
    "SaveAudio": "audio",
    "SaveAudioMP3": "audio",
    "PreviewAudio": "audio",
}

_MODEL_DISAGREEMENT_WARNED = False
_SYMBOLIC_REF_DEPRECATION_WARNED = False
_FILENAME_KWARGS = frozenset({
    "unet_name",
    "vae_name",
    "clip_name",
    "clip_name1",
    "clip_name2",
    "lora_name",
    "ckpt_name",
})


def _category_qualified_template_id(template_id: str, source_path: str | None) -> str:
    if "/" in template_id or not source_path:
        return template_id
    path = Path(source_path)
    if path.parent.name and path.parent.parent.name == "ready_templates":
        return f"{path.parent.name}/{template_id}"
    return template_id


def _derive_output_kind(class_type: str | None) -> str | None:
    if not class_type:
        return None
    if class_type in _OUTPUT_KIND_HEURISTIC:
        return _OUTPUT_KIND_HEURISTIC[class_type]
    lowered = class_type.lower()
    if "video" in lowered:
        return "video"
    if "audio" in lowered:
        return "audio"
    if "image" in lowered:
        return "image"
    return None


def new_workflow(
    metadata: Mapping[str, Any],
    *,
    source_path: str | None = None,
    source_type: str | None = None,
    canonical_custody: Mapping[str, Any] | None = None,
) -> VibeWorkflow:
    """Create a ready-template workflow and apply module metadata.

    Convenience wrapper for template authoring; for runtime use see
    ``vibecomfy.registry.ready_template``. Generated templates should pass
    ``source_path=__file__`` because the fallback here is this helper module.

    The returned workflow eagerly binds the ``workflow_context`` ContextVar so
    that subsequent ``node(...)`` / typed-wrapper calls at module body can
    discover the active workflow without an enclosing ``with`` block.
    ``finalize()`` releases the binding.  The workflow also supports use as a
    context manager (``with new_workflow(...) as wf:``) for callers that prefer
    explicit scoping.
    """
    from vibecomfy.workflow_bundle import _v2_companion_for_build

    companion = _v2_companion_for_build(metadata, source_path)
    raw_workflow_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    workflow_id = _category_qualified_template_id(raw_workflow_id, source_path)
    metadata = dict(metadata)
    metadata.pop("source_bundle", None)
    metadata["ready_template"] = workflow_id
    metadata["workflow_template"] = workflow_id.rsplit("/", 1)[-1]
    provenance = metadata.get("provenance")
    wf = ready_workflow(
        workflow_id,
        source_path=source_path or __file__,
        provenance=provenance if isinstance(provenance, Mapping) else None,
    )
    # Keep the generated canonical source companion-aware without requiring a
    # reflection call in the readable Python.  Bundle loading replaces this
    # sentinel with validated recursive custody; standalone previews let the
    # materializer derive its minimal witness from captured constructors.
    wf._canonical_v2_recursive_custody = None
    wf.metadata.update(metadata)
    if companion is not None:
        if canonical_custody is not None:
            raise ValueError("v2 companion custody cannot be combined with embedded custody")
        root_scope = next(
            scope
            for scope in companion["custody"]["scopes"]
            if scope["scope_path"] == ""
        )
        canonical_custody = {
            record["label"]: {
                key: deepcopy(value)
                for key, value in record.items()
                if key != "label"
            }
            for record in root_scope[_COMPANION_SCOPE_NODES_KEY]
        }
        wf._canonical_v2_custody = canonical_custody
        wf._canonical_v2_helpers = deepcopy(root_scope["helpers"])
        wf._canonical_v2_recursive_custody = deepcopy(
            companion["custody"].get("definitions")
        )
        wf._canonical_v2_companion = companion
        wf._canonical_construction_objects = []
    if canonical_custody is not None:
        if not isinstance(canonical_custody, Mapping):
            raise TypeError("canonical custody must be a mapping")
        wf._canonical_construction_custody = list(canonical_custody.values())
        wf._canonical_construction_index = 0

    # Eagerly bind the ContextVar so that node()/typed-wrapper calls in the
    # caller's body can find the active workflow.  finalize() releases this
    # binding.  Skipping if the workflow is already bound (e.g. caller is using
    # ``with new_workflow(...) as wf:``); the ``with`` form will then re-bind a
    # fresh token in __enter__.
    if wf._workflow_context_token is None:
        from vibecomfy.workflow_context import active_workflow, bind_workflow

        # Defensive: if a *different* previous workflow leaked its binding
        # (e.g. its build() raised before finalize() could release the token),
        # clear it so a brand-new template can be built.  Only do this when the
        # leaked workflow itself has no token attribute — a sign that its owner
        # has been garbage-collected and can never run __exit__.  Genuine nested
        # ``with new_workflow(...) as wf:`` blocks where the outer workflow is
        # still held by the caller will fall through to bind_workflow() and
        # raise ``Nested workflow contexts not supported``, preserving Block A's
        # contract.
        existing = active_workflow()
        if existing is not None and existing is not wf:
            existing_token = existing._workflow_context_token
            if existing_token is None:
                from vibecomfy.workflow_context import _CURRENT_WORKFLOW

                _CURRENT_WORKFLOW.set(None)

        wf._workflow_context_token = bind_workflow(wf)

    return wf


def node(
    *args: Any,
    _id: str | None = None,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a ready-template node.

    v2.6.4 Fix 5: ``wf`` is now optional — reads from the ContextVar set by
    ``new_workflow(...)`` when omitted. This matches the typed-wrapper
    convention, so ``raw_call('<uuid>', '<id>', ...)`` works inside a
    ``with new_workflow(...) as wf:`` block without passing ``wf`` explicitly.

    Backward compat: legacy ``node(wf, class_type, source_id, ...)`` and the
    v2.5 id-free ``node(wf, class_type, ...)`` forms still work — the first
    positional arg can be either a VibeWorkflow or the class_type str.
    """
    # Disambiguate: first positional may be a VibeWorkflow (legacy) or the
    # class_type (new ContextVar form).
    if args and isinstance(args[0], VibeWorkflow):
        wf = args[0]
        rest = args[1:]
    else:
        wf = _current_workflow_or_raise()
        rest = args
    if not rest:
        raise TypeError("node() requires a class_type argument")
    class_type = rest[0]
    if not isinstance(class_type, str):
        raise TypeError(f"node() class_type must be str, got {type(class_type).__name__}")
    # Optional positional source id (legacy form: node(wf, class_type, source_id, ...))
    if len(rest) >= 2 and _id is None:
        _id = str(rest[1]) if rest[1] is not None else None
    elif len(rest) > 2:
        raise TypeError(f"node() got too many positional args: {len(rest)}")

    explicit_outputs = kwargs.pop("_outputs", None)
    explicit_native_ports = kwargs.pop("_native_ports", None)
    explicit_mode = kwargs.pop("_mode", None)
    # Durable node identity (M2): a carried _uid is applied verbatim to the
    # created node so the ready-template round-trip preserves uids. Popped before
    # coercion so it never reaches the graph as an input/widget.
    _uid = kwargs.pop("_uid", None)
    pass_raw = bool(kwargs.pop("pass_raw", False))
    # The generated Python call is retained source evidence for every input it
    # actually supplies, including dynamic custom-node keys missing from an
    # older offline object_info snapshot.  Capture those names before value
    # coercion and before the internal pass_raw control is reinserted.
    authored_input_names = tuple(str(name) for name in kwargs)
    authored_channels: dict[str, AuthoredChannel] = {}
    for field_name, field_value in tuple(kwargs.items()):
        if isinstance(field_value, AuthoredChannel):
            authored_channels[str(field_name)] = field_value
            kwargs[field_name] = field_value.value
    construction_custody = getattr(wf, "_canonical_construction_custody", None)
    construction_index = getattr(wf, "_canonical_construction_index", 0)
    if construction_custody is not None:
        if construction_index >= len(construction_custody):
            raise ValueError("canonical construction created more nodes than its custody manifest")
        construction_record = construction_custody[construction_index]
        if not isinstance(construction_record, Mapping):
            raise TypeError("canonical construction custody record must be a mapping")
        expected_class = construction_record.get("class_type")
        if expected_class != class_type:
            raise ValueError(
                f"canonical construction expected {expected_class!r}, got {class_type!r}"
            )
        retained_ports = construction_record.get("native_ports")
        if explicit_native_ports is None:
            explicit_native_ports = deepcopy(retained_ports)
            construction_output_names = construction_record.get("construction_output_names")
            if construction_output_names:
                if not isinstance(explicit_native_ports, Mapping):
                    explicit_native_ports = {}
                explicit_native_ports = dict(explicit_native_ports)
                explicit_native_ports["native_output_names"] = list(construction_output_names)
                if explicit_native_ports.get("native_output_types") is None:
                    explicit_native_ports["native_output_types"] = [None] * len(construction_output_names)
        wf._canonical_construction_index = construction_index + 1
    if explicit_outputs is not None:
        outputs = tuple(explicit_outputs)
    elif explicit_native_ports is not None:
        outputs = _output_names_from_native_port_payload(explicit_native_ports)
    else:
        outputs = _normalized_output_names(class_type)
    kwargs = coerce_node_kwargs(wf, class_type, kwargs, pass_raw=pass_raw)
    if pass_raw:
        kwargs["pass_raw"] = True
    if explicit_native_ports is not None:
        kwargs["_native_ports"] = explicit_native_ports
    builder = ready_node(wf, class_type, source_id=str(_id) if _id is not None else None, outputs=outputs or None, extras=_extras, **kwargs)
    construction_objects = getattr(wf, "_canonical_construction_objects", None)
    if construction_objects is not None:
        construction_objects.append(builder)
    for field_name, channel in authored_channels.items():
        has_edge = any(
            str(edge.to_node) == str(builder.node.id) and str(edge.to_input) == field_name
            for edge in wf.edges
        )
        if field_name not in builder.node.inputs and not has_edge:
            raise ValueError(
                f"authored channel {class_type}.{field_name} did not produce an input channel"
            )
        if channel.retain_input_default:
            builder.node.inputs[field_name] = deepcopy(channel.widget)
        elif channel.input_default is not _MISSING_AUTHORED_DEFAULT:
            builder.node.inputs[field_name] = deepcopy(channel.input_default)
        builder.node.widgets[channel.name] = deepcopy(channel.widget)
    if authored_input_names:
        # Preserve the exact fields explicitly present in Python source across
        # subsequent canonical emission, even when their value equals a
        # provider default.  This authoring provenance is deliberately outside
        # the execution semantic digest; the compiled inputs carry the value.
        builder.node.metadata["keep_defaults"] = sorted(set(authored_input_names))
    if explicit_native_ports is None:
        _hydrate_native_schema_carriers(
            builder.node,
            class_type,
            outputs,
            authored_input_names=authored_input_names,
        )
    if _uid:
        builder.node.uid = str(_uid)
    if explicit_mode is not None:
        from vibecomfy.workflow import litegraph_to_mode

        builder.node.mode = litegraph_to_mode(explicit_mode)
    return builder


_NATIVE_PORT_CARRIER_KEYS = frozenset({
    "native_input_names", "native_output_names", "native_input_types",
    "native_output_types", "native_input_optional", "native_input_asset_kinds",
    "native_output_slots",
})


def _output_names_from_native_port_payload(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, Mapping):
        raise TypeError("_native_ports must be a mapping")
    unknown = set(payload) - _NATIVE_PORT_CARRIER_KEYS
    if unknown:
        raise ValueError(f"_native_ports contains unknown field {sorted(unknown)[0]!r}")
    names = payload.get("native_output_names")
    if not isinstance(names, (list, tuple)):
        return ()
    return tuple(
        name.strip().replace(" ", "_").upper()
        for name in names
        if isinstance(name, str) and name.strip()
    )


def _apply_explicit_native_port_carriers(node: Any, payload: Any) -> None:
    """Apply emitted, source-owned carriers without consulting any provider."""
    _output_names_from_native_port_payload(payload)  # closed-key/type check
    for field_name in _NATIVE_PORT_CARRIER_KEYS:
        setattr(node, field_name, deepcopy(payload.get(field_name)))
    # Reuse VibeNode's single carrier validator, including aligned lengths.
    node.__post_init__()


def _hydrate_native_schema_carriers(
    node: Any,
    class_type: str,
    outputs: tuple[str, ...],
    *,
    authored_input_names: tuple[str, ...],
) -> None:
    """Attach retained wrapper and offline-schema port authority.

    Legacy generated ready sources predate explicit emitted roster assignments.
    The public wrapper's declared outputs and inputs actually present in its
    generated Python call are source witnesses for names.  The offline schema
    supplies types, optionality, and asset kinds only for exact known ports.
    Missing schema fields therefore remain untyped and make no optionality
    claim instead of being discarded or guessed.
    """
    carrier = _ready_native_schema_carrier(class_type)
    if carrier is None:
        if authored_input_names:
            node.native_input_names = list(authored_input_names)
            node.native_input_types = [None] * len(authored_input_names)
        if outputs:
            node.native_output_names = list(outputs)
            node.native_output_types = [None] * len(outputs)
        node.__post_init__()
        return
    (
        input_names, input_types, input_optional, input_assets,
        output_names, output_types, _output_is_list,
    ) = carrier
    merged_input_names = list(input_names)
    dynamic_names = [name for name in authored_input_names if name not in merged_input_names]
    merged_input_names.extend(dynamic_names)
    node.native_input_names = merged_input_names
    node.native_input_types = list(input_types) + [None] * len(dynamic_names)
    # A stale schema cannot establish whether newly observed source ports are
    # optional.  Withhold the whole aligned claim so projection remains closed.
    node.native_input_optional = None if dynamic_names else list(input_optional)
    merged_assets = list(input_assets) + [None] * len(dynamic_names)
    node.native_input_asset_kinds = merged_assets if any(merged_assets) else None

    authoritative_output_names = list(outputs) if outputs else list(output_names)
    if authoritative_output_names:
        schema_output_types = {
            str(name).strip().replace(" ", "_").upper(): output_type
            for name, output_type in zip(output_names, output_types)
            if isinstance(name, str) and name.strip()
        }
        node.native_output_names = authoritative_output_names
        node.native_output_types = [
            schema_output_types.get(str(name).strip().replace(" ", "_").upper())
            for name in authoritative_output_names
        ]
    node.__post_init__()


@lru_cache(maxsize=None)
def _ready_native_schema_carrier(class_type: str) -> tuple[Any, ...] | None:
    """Freeze one class's offline ready-wrapper carrier for this process."""
    schema = _ready_schema_provider().get_schema(class_type)
    if schema is None:
        return None
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, Mapping):
        inputs = {}
    input_names = tuple(str(name) for name in inputs)
    input_types = tuple(
        str(getattr(inputs[name], "type")) if getattr(inputs[name], "type", None) is not None else None
        for name in inputs
    )
    input_optional = tuple(
        not bool(getattr(inputs[name], "required", False)) for name in inputs
    )
    input_assets = tuple(
        str(getattr(inputs[name], "asset_kind")) if getattr(inputs[name], "asset_kind", None) is not None else None
        for name in inputs
    )
    schema_outputs = tuple(getattr(schema, "outputs", None) or ())
    output_names = tuple(
        str(getattr(spec, "name")) if getattr(spec, "name", None) is not None else None
        for spec in schema_outputs
    )
    output_types = tuple(
        str(getattr(spec, "type")) if getattr(spec, "type", None) is not None else None
        for spec in schema_outputs
    )
    output_is_list = tuple(getattr(schema, "output_is_list", ()) or ())
    return (
        input_names, input_types, input_optional, input_assets,
        output_names, output_types, output_is_list,
    )


@lru_cache(maxsize=1)
def _ready_schema_provider() -> Any:
    from vibecomfy.schema import get_authoring_schema_provider

    return get_authoring_schema_provider(on_demand_schemas=False)


def coerce_node_kwargs(
    wf: VibeWorkflow,
    class_type: str,
    kwargs: Mapping[str, Any],
    *,
    pass_raw: bool = False,
) -> dict[str, Any]:
    """Normalize v2.5 natural-form values before a node is created.

    This is deliberately shared by ready-template ``node(...)`` and raw
    ``wf.node(...)`` so generated wrappers remain thin and behavior is uniform.
    """
    if pass_raw:
        return dict(kwargs)
    coerced: dict[str, Any] = {}
    for key, value in kwargs.items():
        if _is_node_builder(value):
            value = _auto_resolve_node_builder(value)
        elif isinstance(value, list) and len(value) == 2:
            # Keep legacy authored sources readable and executable when they
            # still spell a previously constructed connection as a Comfy API
            # pair.  The canonical representation is a Handle/VibeEdge; this
            # bounded coercion only applies when the referenced node already
            # exists, so ordinary two-item widget lists remain literals.
            from vibecomfy._compile._graph import is_canonical_api_link

            if is_canonical_api_link(value) and str(value[0]) in wf.nodes:
                value = Handle(node_id=str(value[0]), output_slot=int(value[1]))
        if isinstance(value, ModelAsset) and key in _FILENAME_KWARGS:
            value = value.filename
        elif isinstance(value, InputSpec):
            if key in _FILENAME_KWARGS:
                raise TypeError(
                    f"expected str for {key}, got InputSpec; did you mean InputSpec.default?"
                )
            value = value.default
        if key in _FILENAME_KWARGS and not isinstance(value, str):
            raise TypeError(f"expected str for {key}, got {type(value).__name__}")
        coerced[key] = value
    return coerced


def _is_node_builder(value: Any) -> bool:
    node = getattr(value, "node", None)
    return node is not None and hasattr(node, "class_type") and hasattr(node, "id") and callable(getattr(value, "out", None))


def _auto_resolve_node_builder(value: Any) -> Handle:
    node = value.node
    class_type = str(node.class_type)
    names = [
        str(name).strip().replace(" ", "_").upper()
        for name in (node.native_output_names or ())
        if isinstance(name, str) and name.strip()
    ]
    count = len(node.native_output_names or ())
    carrier = _ready_native_schema_carrier(class_type)
    list_flags = carrier[6] if carrier is not None else ()
    if any(list_flags):
        raise ValueError(
            f"{class_type} node {node.id!r} has list outputs; specify .out('NAME') explicitly"
        )
    if count == 1:
        return value.out(0)
    if count > 1:
        detail = ", ".join(names) if names else f"{count} outputs"
        raise ValueError(
            f"{class_type} node {node.id!r} has {count} outputs ({detail}); "
            "specify .out('NAME') explicitly"
        )
    # Legacy and community nodes often lack object_info output schema in local
    # indexes. Generated templates historically treated those as single-output
    # nodes unless they supplied _outputs explicitly, so keep that compatibility
    # path while still rejecting known multi-output/list-output schemas above.
    return value.out(0)


def _at(
    wf: VibeWorkflow,
    _id: str,
    class_type: str,
    _extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Narrative-form alias of ``node`` with ``_id`` in position 2.

    .. deprecated::
        Prefer ``node(wf, class_type, _id, ...)``.  ``_at`` is retained as a
        compatibility alias for hand-authored templates that use the older
        ``_at(wf, ID["role"], "Class", ...)`` calling convention.  Generated
        ready-templates always use ``node``.

    Semantically identical to ``node(wf, class_type, _id, ...)``.
    """
    return node(wf, class_type, _id, _extras=_extras, **kwargs)


def _normalized_output_names(class_type: str) -> tuple[str, ...]:
    # Public-wrapper authoring already freezes one offline schema carrier for
    # the node.  Reuse that same evidence instead of consulting the separate
    # object-info consumer, whose per-call cache witness scan can turn a
    # provider-free ready inventory into repeated ambient filesystem work.
    carrier = _ready_native_schema_carrier(class_type)
    if carrier is not None:
        output_names = carrier[4]
        return tuple(
            name.strip().replace(" ", "_").upper()
            for name in output_names
            if isinstance(name, str) and name.strip()
        )
    try:
        from vibecomfy.porting.object_info.consume import output_names
    except ImportError:
        return ()
    return tuple(
        name.strip().replace(" ", "_").upper()
        for name in output_names(class_type)
        if isinstance(name, str) and name.strip()
    )


@dataclass(frozen=True)
class SymbolicNodeRef:
    """Module-level public-input binding resolved from build() locals."""

    label: str

    def resolve(self, namespace: Mapping[str, Any], wf: VibeWorkflow) -> str:
        value = namespace.get(self.label)
        node_id = _node_id_from_binding(value)
        if node_id is None or node_id not in wf.nodes:
            raise ValueError(
                f"SymbolicNodeRef({self.label!r}) could not be resolved to a node "
                f"in workflow {wf.id!r}"
            )
        wf.metadata.setdefault("id_map", {})[self.label] = node_id
        return node_id


def ref(label: str) -> SymbolicNodeRef:
    global _SYMBOLIC_REF_DEPRECATION_WARNED
    if not _SYMBOLIC_REF_DEPRECATION_WARNED:
        warnings.warn(
            "vibecomfy.templates.ref('name') is a legacy generated-template fallback; "
            "new generated templates bind InputSpec.node to node objects inside build().",
            PendingDeprecationWarning,
            stacklevel=2,
        )
        _SYMBOLIC_REF_DEPRECATION_WARNED = True
    return SymbolicNodeRef(label)


def _node_id_from_binding(value: Any) -> str | None:
    if isinstance(value, Handle):
        return str(value.node_id)
    node = getattr(value, "node", None)
    if node is not None and hasattr(node, "id"):
        return str(node.id)
    if hasattr(value, "id"):
        return str(value.id)
    if isinstance(value, str):
        return value
    return None


def _is_schema_default_input(class_type: str, field: str, value: Any) -> bool:
    try:
        from vibecomfy.porting.object_info import class_defaults

        defaults = class_defaults(class_type)
    except Exception:
        return False
    return field in defaults and value == defaults[field]


_MISSING_AUTHORED_DEFAULT = object()


@dataclass(frozen=True)
class AuthoredChannel:
    """One effective kwarg plus a distinct retained widget-channel default."""

    value: Any
    widget: Any
    name: str
    input_default: Any = _MISSING_AUTHORED_DEFAULT
    retain_input_default: bool = False


@dataclass(frozen=True)
class OutputSpec:
    """Small typed declaration for an exact public workflow output."""

    node: Any
    output_type: str | None = None
    name: str | None = None
    artifact_kind: str | None = None
    mime_type: str | None = None
    filename_prefix: str | None = None
    expected_cardinality: str | None = None


def authored_channel(
    value: Any,
    *,
    widget: Any,
    name: str,
    input_default: Any = _MISSING_AUTHORED_DEFAULT,
    retain_input_default: bool = False,
) -> AuthoredChannel:
    if not isinstance(name, str) or not name:
        raise ValueError("authored channel widget name must be a nonblank string")
    if input_default is not _MISSING_AUTHORED_DEFAULT and retain_input_default:
        raise ValueError(
            "authored channel cannot supply input_default and retain_input_default together"
        )
    return AuthoredChannel(
        value=value,
        widget=widget,
        name=name,
        input_default=input_default,
        retain_input_default=retain_input_default,
    )


@dataclass(frozen=True)
class InputSpec:
    node: str | SymbolicNodeRef | Any
    field: str
    default: Any
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    description: str | None = None
    media_semantics: str | None = None
    omit_if_schema_default: bool = False
    range: Any = None
    allow_missing_target: bool = False
    infer_type: bool = True
    materialize_aliases: bool = True

    def register(self, wf: VibeWorkflow, name: str, namespace: Mapping[str, Any] | None = None) -> None:
        node_id = self.resolve_node_id(wf, namespace=namespace)
        node = wf.nodes.get(node_id)
        if node is None:
            raise ValueError(
                f"InputSpec.register({name!r}): target node {node_id!r} does not exist "
                f"in workflow {wf.id!r}"
            )
        allow_missing_target = False
        if self.field in node.inputs:
            value = node.inputs[self.field]
        elif self.field in node.widgets:
            value = node.widgets[self.field]
        elif self.omit_if_schema_default:
            if not _is_schema_default_input(node.class_type, self.field, self.default):
                raise ValueError(
                    f"InputSpec.register({name!r}): {node.class_type}.{self.field} "
                    f"default {self.default!r} is not the schema default"
                )
            value = self.default
            allow_missing_target = True
        else:
            raise ValueError(
                f"InputSpec.register({name!r}): field {self.field!r} not found in "
                f"node {node_id!r} ({node.class_type}) inputs or widgets"
            )
        if self.omit_if_schema_default:
            if not _is_schema_default_input(node.class_type, self.field, self.default):
                raise ValueError(
                    f"InputSpec.register({name!r}): {node.class_type}.{self.field} "
                    f"default {self.default!r} is not the schema default"
                )
            # The node may retain the default explicitly for faithful source
            # regeneration, while the runtime is still allowed to omit the
            # target field because Comfy supplies the same schema default.
            allow_missing_target = value == self.default
        input_type = self.type
        if input_type is None and self.infer_type:
            input_type = _derive_input_type(node.class_type, self.field)
        wf.register_input(
            name,
            node_id,
            self.field,
            value,
            type=input_type,
            default=self.default,
            required=self.required,
            aliases=self.aliases,
            media_semantics=self.media_semantics,
            range=self.range,
            allow_missing_target=self.allow_missing_target or allow_missing_target,
        )
        # ``VibeWorkflow.register_input`` retains a historical ``None`` means
        # omitted fallback.  InputSpec is an explicit descriptor, so its
        # authored default (including None) remains authoritative.
        wf.inputs[name].default = deepcopy(self.default)
        for alias in self.aliases if self.materialize_aliases else ():
            if alias in wf.inputs:
                continue
            wf.inputs[alias] = VibeInput(
                name=alias,
                node_id=node_id,
                field=self.field,
                value=value,
                type=input_type,
                default=self.default,
                required=self.required,
                aliases=(),
                media_semantics=self.media_semantics,
                range=deepcopy(self.range),
                allow_missing_target=self.allow_missing_target or allow_missing_target,
            )

    def resolve_node_id(self, wf: VibeWorkflow, namespace: Mapping[str, Any] | None = None) -> str:
        if isinstance(self.node, SymbolicNodeRef):
            return self.node.resolve(namespace or {}, wf)
        node_id = _node_id_from_binding(self.node)
        if node_id is None:
            node_id = str(self.node)
        # If the literal source-workflow ID doesn't exist in the freshly-built
        # workflow (typical when emitter auto-assigns IDs that differ from the
        # source-JSON IDs), fall back to searching ``namespace`` for a local
        # variable that resolves to a matching node — this is how the legacy
        # ``def PUBLIC_INPUTS(**nodes):`` factory bridged the gap.
        node = wf.nodes.get(node_id)
        node_missing_or_wrong_field = node is None or (
            self.field not in node.inputs and self.field not in node.widgets
        )
        if node_missing_or_wrong_field and namespace:
            for value in namespace.values():
                candidate = _node_id_from_binding(value)
                if candidate is not None and candidate in wf.nodes:
                    candidate_node = wf.nodes[candidate]
                    if self.field in candidate_node.inputs or self.field in candidate_node.widgets:
                        return candidate
        return node_id


def _derive_input_type(class_type: str, field: str) -> str | None:
    try:
        from vibecomfy.porting.object_info import class_input_types
    except ImportError:
        return None
    return class_input_types(class_type).get(field)


@dataclass(frozen=True, init=False)
class ModelAsset:
    filename: str
    url: str | None
    subdir: str
    target_path: str | None = None
    sha256: str | None = None
    hf_revision: str | None = None
    size_bytes: int | None = None
    gated: bool = False

    def __init__(
        self,
        filename: str | None = None,
        url: str | None = None,
        subdir: str | None = None,
        *,
        target_path: str | None = None,
        sha256: str | None = None,
        hf_revision: str | None = None,
        size_bytes: int | None = None,
        gated: bool = False,
    ) -> None:
        if subdir is None:
            raise TypeError("ModelAsset requires subdir=...")
        if sha256 == "gated" or hf_revision == "gated":
            raise ValueError("Use ModelAsset(..., gated=True) instead of sha256='gated' or hf_revision='gated'.")
        if url is None:
            if not isinstance(filename, str) or not filename:
                raise TypeError("unresolved ModelAsset requires an explicit filename")
            if not _safe_model_relative_path(filename, field="filename"):
                raise ValueError("unresolved ModelAsset filename must be a safe relative path")
            if not _safe_model_relative_path(subdir, field="subdir"):
                raise ValueError("unresolved ModelAsset subdir must be a safe relative path")
        elif not isinstance(url, str) or not url:
            raise TypeError("ModelAsset url must be a non-empty string or None")
        elif not isinstance(subdir, str) or not subdir:
            raise TypeError("ModelAsset requires a non-empty subdir")
        derived_filename = filename or Path(urlsplit(url).path).name
        if not derived_filename:
            raise ValueError("ModelAsset filename could not be derived from url")
        object.__setattr__(self, "filename", derived_filename)
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "subdir", subdir)
        object.__setattr__(self, "target_path", target_path)
        object.__setattr__(self, "sha256", sha256)
        object.__setattr__(self, "hf_revision", hf_revision)
        object.__setattr__(self, "size_bytes", size_bytes)
        object.__setattr__(self, "gated", bool(gated))


def _safe_model_relative_path(value: Any, *, field: str) -> bool:
    """Return whether an authored unresolved model path is fetch-safe.

    The downloader owns the final authorization check.  Keeping the same
    inexpensive lexical boundary in the authoring type prevents an unresolved
    placeholder from representing an absolute path or traversal.
    """
    if not isinstance(value, str) or not value or "\x00" in value:
        return False
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    return not (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or bool(windows.root)
        or ".." in posix.parts
        or ".." in windows.parts
        or "\\" in value
        or value.endswith(("/", "\\"))
        or value.rstrip("/").rsplit("/", 1)[-1] == "."
    )


class ReadyMetadata:
    @classmethod
    def build(
        cls,
        *,
        capability: str,
        template_id: str | None = None,
        inputs: dict[str, InputSpec] | None = None,
        models: dict[str, ModelAsset] | None = None,
        output_prefix: str | None = None,
        edit_guide_extra: str | None = None,
        requirements: Mapping[str, Any] | None = None,
        custom_node_packs: Mapping[str, Any] | None = None,
        **extras: Any,
    ) -> dict[str, Any]:
        source_path = _caller_source_path()
        template_id = _derive_template_id(template_id, source_path)
        qualified_template_id = _category_qualified_template_id(template_id, str(source_path) if source_path else None)
        inputs = dict(inputs or {})
        models = dict(models or {})
        output_prefix = output_prefix or qualified_template_id
        coverage_row = _coverage_manifest_row(qualified_template_id)
        model_assets = [
            _model_asset_metadata(model)
            for model in models.values()
        ]
        derived_requirements = _requirements_with_models(requirements, model_assets)
        metadata: dict[str, Any] = {
            "ready_template": qualified_template_id,
            "workflow_template": qualified_template_id.rsplit("/", 1)[-1],
            "capability": capability,
            "output_prefix": output_prefix,
            "unbound_inputs": {
                name: spec.default
                for name, spec in inputs.items()
            },
            "model_assets": model_assets,
            "edit_guide": _derive_edit_guide(inputs, edit_guide_extra),
            "requirements": derived_requirements,
            "source_role": "materialized_ready_python_template",
        }
        if custom_node_packs:
            metadata["custom_node_packs"] = {
                str(name): dict(value)
                for name, value in custom_node_packs.items()
                if isinstance(value, Mapping)
            }
        if "coverage_tier" not in extras and isinstance(coverage_row.get("coverage_tier"), str):
            metadata["coverage_tier"] = coverage_row["coverage_tier"]
        source_workflow = _derive_source_workflow(extras, coverage_row, source_path)
        if source_workflow:
            metadata["source_workflow"] = source_workflow
        metadata["vibecomfy_version"] = extras.pop("vibecomfy_version", None) or _project_version()
        metadata["comfy_core"] = extras.pop("comfy_core", None) or _comfy_core_metadata()
        provenance = extras.get("provenance")
        if not isinstance(provenance, Mapping) and source_workflow:
            provenance = {"source_workflow": source_workflow}
            extras["provenance"] = provenance
        elif isinstance(provenance, Mapping) and source_workflow and "source_workflow" not in provenance:
            provenance = {**dict(provenance), "source_workflow": source_workflow}
            extras["provenance"] = provenance
        if isinstance(provenance, Mapping):
            metadata.update({
                key: value
                for key, value in provenance.items()
                if key not in metadata
            })
        metadata.update({
            key: value
            for key, value in extras.items()
            if value is not None
        })
        return metadata


def finalize(
    wf: VibeWorkflow,
    inputs: dict[str, InputSpec],
    metadata: dict[str, Any],
    *,
    output_node: Any = None,
    output_kind: str | None = None,
    **bind_kwargs: Any,
) -> VibeWorkflow:
    """Backward-compatible free-function shim for ``VibeWorkflow.finalize``."""
    return wf.finalize(inputs, metadata=metadata, output_node=output_node, output_kind=output_kind, **bind_kwargs)


_CANONICAL_CUSTODY_NODE_KEYS = frozenset({
    "id", "uid", "class_type", "native_ports", "metadata", "widget_channels",
    "none_input_fields", "none_widget_fields", "output_slot_names", "construction_output_names",
})
_UNSPECIFIED_OUTPUTS = object()


def _apply_canonical_custody(
    wf: VibeWorkflow,
    custody: Mapping[str, Any],
    bindings: Mapping[str, Any],
) -> None:
    """Atomically rebind generated variables to retained node custody.

    Generated constructor calls remain ordinary editable Python.  This is the
    single post-construction authority for source IDs, durable UIDs, retained
    schema provenance, and native socket rosters; runtime values and topology
    are intentionally not accepted here.
    """
    if not isinstance(custody, Mapping):
        raise TypeError("canonical custody must be a mapping")
    if not isinstance(bindings, Mapping):
        raise TypeError("canonical custody bindings must be a mapping")

    resolved: list[tuple[str, str, Any, Mapping[str, Any]]] = []
    seen_current: set[str] = set()
    seen_target: set[str] = set()
    for label, raw_record in custody.items():
        if not isinstance(label, str) or not label:
            raise ValueError("canonical custody labels must be nonblank strings")
        if not isinstance(raw_record, Mapping):
            raise TypeError(f"canonical custody record {label!r} must be a mapping")
        unknown = set(raw_record) - _CANONICAL_CUSTODY_NODE_KEYS
        if unknown:
            raise ValueError(
                f"canonical custody record {label!r} contains unsupported field "
                f"{sorted(unknown)[0]!r}"
            )
        binding = bindings.get(label)
        current_id = _node_id_from_binding(binding)
        if current_id is None or current_id not in wf.nodes:
            raise ValueError(
                f"canonical custody binding {label!r} does not resolve to a constructed node"
            )
        target_id = raw_record.get("id")
        if not isinstance(target_id, str) or not target_id:
            raise ValueError(f"canonical custody record {label!r} has an invalid id")
        if raw_record.get("class_type") != wf.nodes[current_id].class_type:
            raise ValueError(f"canonical custody record {label!r} class does not match its binding")
        if current_id in seen_current:
            raise ValueError(f"canonical custody binding {label!r} aliases another node")
        if target_id in seen_target:
            raise ValueError(f"canonical custody id {target_id!r} is duplicated")
        seen_current.add(current_id)
        seen_target.add(target_id)
        resolved.append((label, current_id, wf.nodes[current_id], raw_record))

    if seen_current != set(wf.nodes):
        missing = sorted(set(wf.nodes) - seen_current)
        raise ValueError(
            "canonical custody does not bind every constructed node: " + ", ".join(missing)
        )
    construction_custody = getattr(wf, "_canonical_construction_custody", None)
    if construction_custody is not None and getattr(wf, "_canonical_construction_index", 0) != len(construction_custody):
        raise ValueError("canonical construction did not consume every custody record")

    # Validate detached candidate nodes first so malformed custody cannot leave
    # the workflow half rebound.
    candidates: dict[str, Any] = {}
    old_to_new: dict[str, str] = {}
    for label, current_id, node, record in resolved:
        candidate = deepcopy(node)
        target_id = str(record["id"])
        candidate.id = target_id
        uid = record.get("uid")
        if not isinstance(uid, str) or not uid:
            raise ValueError(f"canonical custody record {label!r} has an invalid uid")
        candidate.uid = uid
        metadata = record.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise TypeError(f"canonical custody metadata {label!r} must be a mapping")
        candidate.metadata.update(deepcopy(dict(metadata)))
        native_ports = record.get("native_ports", {})
        _apply_explicit_native_port_carriers(candidate, native_ports)
        widget_channels = record.get("widget_channels", {})
        if not isinstance(widget_channels, Mapping):
            raise TypeError(f"canonical custody widget channels {label!r} must be a mapping")
        for constructed_name, authored_name in widget_channels.items():
            if not isinstance(constructed_name, str) or not isinstance(authored_name, str):
                raise TypeError(f"canonical custody widget channel {label!r} must use strings")
            if authored_name in candidate.widgets:
                continue
            if authored_name in candidate.inputs:
                candidate.widgets[authored_name] = candidate.inputs.pop(authored_name)
            elif constructed_name in candidate.inputs:
                candidate.widgets[authored_name] = candidate.inputs.pop(constructed_name)
            else:
                raise ValueError(
                    f"canonical custody widget channel {label!r}.{constructed_name} is absent"
                )
        for field_name, channel in (
            ("none_input_fields", candidate.inputs),
            ("none_widget_fields", candidate.widgets),
        ):
            names = record.get(field_name, ())
            if not isinstance(names, (list, tuple)) or not all(isinstance(name, str) for name in names):
                raise TypeError(f"canonical custody {field_name} {label!r} must be a string sequence")
            for name in names:
                channel.setdefault(name, None)
        candidates[target_id] = candidate
        old_to_new[current_id] = target_id

    # Commit the already-validated detached replacement in one bounded step.
    wf.nodes = candidates
    for edge in wf.edges:
        edge.from_node = old_to_new.get(str(edge.from_node), str(edge.from_node))
        edge.to_node = old_to_new.get(str(edge.to_node), str(edge.to_node))
        source_record = next(
            (record for _label, _old, _node, record in resolved if str(record["id"]) == edge.from_node),
            None,
        )
        slot_names = source_record.get("output_slot_names", {}) if source_record else {}
        if not isinstance(slot_names, Mapping):
            raise TypeError("canonical custody output_slot_names must be a mapping")
        edge.from_output = str(slot_names.get(str(edge.from_output), edge.from_output))
    for item in wf.inputs.values():
        item.node_id = old_to_new.get(str(item.node_id), str(item.node_id))
    for item in wf.outputs:
        item.node_id = old_to_new.get(str(item.node_id), str(item.node_id))
    wf._set_id_map({label: str(record["id"]) for label, _old, _node, record in resolved})

    report = wf.validate_identity()
    if not report.ok:
        raise ValueError(report.issues[0].message)


def _finalize_impl(
    wf: VibeWorkflow,
    inputs: dict[str, InputSpec],
    metadata: dict[str, Any],
    *,
    output_node: Any = None,
    output_kind: str | None = None,
    **bind_kwargs: Any,
) -> VibeWorkflow:
    """Finalize ready-template metadata, public inputs, and output binding.

    When ``output_kind`` is omitted, it is inferred best-effort from the
    output node class type, then from ``output_type`` if present. If
    ``output_node`` is omitted, a single terminal Save/Create/Preview node is
    selected; multiple candidates require an explicit output binding.
    """
    # Release the eager ContextVar binding that ``new_workflow()`` set, BEFORE
    # any work that might raise — otherwise an exec_failed/validate path leaves
    # the binding stuck across the next template's build() and the regen tool
    # cascades into ``ContextVarBindingError``.  ``new_workflow()`` exists to
    # let module-body node() calls discover the active workflow; by the time we
    # reach finalize, that purpose is served.
    token = wf._workflow_context_token
    if token is not None:
        try:
            from vibecomfy.workflow_context import reset_workflow

            reset_workflow(token)
        except Exception:
            pass
        wf._workflow_context_token = None

    source_path = bind_kwargs.pop("source_path", None)
    canonical_custody = bind_kwargs.pop("canonical_custody", None)
    canonical_bindings = bind_kwargs.pop("canonical_bindings", None)
    canonical_outputs = bind_kwargs.pop("canonical_outputs", None)
    canonical_requirements = bind_kwargs.pop("canonical_requirements", None)
    canonical_helpers = bind_kwargs.pop("canonical_helpers", None)
    declared_outputs = bind_kwargs.pop("outputs", _UNSPECIFIED_OUTPUTS)
    if canonical_outputs is not None and declared_outputs is not _UNSPECIFIED_OUTPUTS:
        raise ValueError("legacy canonical_outputs cannot be combined with typed outputs")
    if output_node is not None and declared_outputs is not _UNSPECIFIED_OUTPUTS:
        raise ValueError("output_node cannot be combined with typed outputs")
    external_custody = getattr(wf, "_canonical_v2_custody", None)
    if external_custody is not None:
        if canonical_custody is not None or canonical_bindings is not None:
            raise ValueError("v2 companion custody cannot be combined with embedded custody")
        canonical_custody = external_custody
        external_locals = _caller_build_locals()
        canonical_bindings = {
            label: external_locals.get(label)
            for label in canonical_custody
        }
        construction_objects = getattr(wf, "_canonical_construction_objects", ())
        if len(construction_objects) != len(canonical_custody):
            raise ValueError("v2 construction binding count does not match custody")
        for (label, _record), constructed in zip(
            canonical_custody.items(), construction_objects
        ):
            if _node_id_from_binding(canonical_bindings[label]) != _node_id_from_binding(constructed):
                raise ValueError(
                    f"v2 construction label {label!r} does not bind its constructed object; regenerate the pair"
                )
        canonical_helpers = getattr(wf, "_canonical_v2_helpers", ())
    if (canonical_custody is None) != (canonical_bindings is None):
        raise ValueError("canonical custody and bindings must be supplied together")
    requirements = bind_kwargs.pop("requirements", None)
    if requirements is None:
        # READY_METADATA is the compact JSON-shaped authority for a generated
        # source.  Preserve its complete requirement witness on a standalone
        # build as well as on a v2 pair; otherwise a direct SDK round-trip can
        # silently drop missing-node or explicit-empty declarations before the
        # companion writer ever gets a chance to retain them.
        metadata_requirements = metadata.get("requirements")
        if isinstance(metadata_requirements, Mapping):
            requirements = metadata_requirements
    if external_custody is not None and requirements is None:
        # v2 keeps the compact requirements declaration in READY_METADATA;
        # use it as the source-side requirement witness without reintroducing
        # a large finalize argument or an embedded custody manifest.
        metadata_requirements = metadata.get("requirements")
        if isinstance(metadata_requirements, Mapping):
            requirements = metadata_requirements
    if source_path is None:
        source_path = wf.source.path or str(Path.cwd())

    # Merge metadata['requirements'] custom_nodes into explicit requirements.
    meta_reqs = metadata.get("requirements")
    if isinstance(meta_reqs, dict) and (meta_reqs.get("custom_nodes") or meta_reqs.get("custom_node_refs")):
        meta_normalized, _warnings = normalize_custom_node_requirements(meta_reqs)
        meta_custom = list(meta_normalized["custom_nodes"])
        if requirements is None:
            requirements = {}
        existing_custom = list(requirements.get("custom_nodes") or [])
        requirements["custom_nodes"] = sorted(set(existing_custom + meta_custom))
        if meta_normalized.get("custom_node_refs"):
            existing_refs = list(requirements.get("custom_node_refs") or [])
            requirements["custom_node_refs"] = [*existing_refs, *meta_normalized["custom_node_refs"]]

    # Fall back to metadata output_prefix when filename_prefix not provided.
    if "filename_prefix" not in bind_kwargs:
        output_prefix_fallback = metadata.get("output_prefix")
        if output_prefix_fallback is not None:
            bind_kwargs["filename_prefix"] = output_prefix_fallback

    caller_locals = _caller_build_locals()
    if (
        canonical_outputs is not None
        or declared_outputs is not _UNSPECIFIED_OUTPUTS
    ) and output_node is None:
        output_node_id = None
    else:
        try:
            output_node_id = _resolve_output_node(wf, output_node, caller_locals)
        except ValueError as exc:
            if output_node is not None or "could not be auto-detected" not in str(exc):
                raise
            output_node_id = None

    output_class_type = wf.nodes.get(output_node_id).class_type if output_node_id in wf.nodes else None
    derived_output_kind = output_kind or _derive_output_kind(output_class_type)
    if derived_output_kind is None:
        derived_output_kind = _derive_output_kind(str(bind_kwargs.get("output_type") or ""))

    wf.finalize_metadata()
    # Recompute inferred requirements before applying ready metadata.  Edits
    # to model-picker fields must win over the source template's old witness.
    if external_custody is not None and isinstance(requirements, Mapping):
        # The companion stores the original requirement witness, but model
        # picker values remain ordinary editable constructor inputs.  Refresh
        # only the model field from the rebuilt IR so editing a loader cannot
        # silently leave a stale model declaration behind.
        from vibecomfy.model_assets import _referenced_model_values

        existing_models = requirements.get("models")
        current_models = [
            str(item["value"])
            for item in _referenced_model_values(wf)
            if isinstance(item, Mapping) and item.get("value")
        ]
        if current_models and isinstance(existing_models, (list, tuple)) and existing_models:
            requirements = dict(requirements)
            requirements["models"] = reconcile_model_requirements(
                existing_models,
                current_models,
            )
    derived_model_assets = metadata.get("model_assets", [])
    if external_custody is not None and isinstance(requirements, Mapping):
        current_names = {
            str(item["value"])
            for item in _referenced_model_values(wf)
            if isinstance(item, Mapping) and item.get("value")
        }
        derived_model_assets = [
            item for item in derived_model_assets
            if isinstance(item, Mapping)
            and str(item.get("name", item.get("filename", ""))) in current_names
        ]
    requirements = _requirements_with_models(requirements, derived_model_assets)
    if canonical_custody is None or wf.nodes:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            apply_ready_template_policy(wf, metadata, source_path=str(source_path), requirements=requirements)

    if external_custody is None and isinstance(requirements, Mapping):
        # A standalone generated source has no companion to restore the
        # non-runtime requirement fields after ``finalize_metadata`` infers
        # its local view.  Reapply only fields explicitly present in the
        # compact READY_METADATA witness; absent fields remain inferred.
        for key in ("models", "custom_nodes", "missing_models", "missing_nodes", "unsupported"):
            if key not in requirements:
                continue
            value = requirements[key]
            if not isinstance(value, (list, tuple)):
                raise TypeError(f"requirements {key!r} must be a sequence")
            setattr(wf.requirements, key, deepcopy(list(value)))

    if canonical_custody is not None:
        # Canonical source carries the complete retained public interface.
        # Ready-template policy inference is useful for handwritten templates,
        # but must not invent another interface during a canonical rebuild.
        wf.inputs = {}
        wf._manual_input_names.clear()
    for name, spec in inputs.items():
        spec.register(wf, name, namespace=caller_locals)

    _drop_shadowed_auto_inputs(wf, inputs, namespace=caller_locals)
    _assert_public_input_invariant(wf, inputs, namespace=caller_locals)

    if output_node_id is not None:
        artifact_kind = bind_kwargs.pop("artifact_kind", None) or derived_output_kind
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            bind_output(
                wf,
                output_node_id,
                artifact_kind=artifact_kind,
                **bind_kwargs,
            )
    if canonical_outputs is not None:
        if not isinstance(canonical_outputs, (list, tuple)):
            raise TypeError("canonical outputs must be a sequence")
        rebound_outputs: list[VibeOutput] = []
        allowed_output_keys = {
            "node", "output_type", "name", "artifact_kind", "mime_type",
            "filename_prefix", "expected_cardinality",
        }
        for index, record in enumerate(canonical_outputs):
            if not isinstance(record, Mapping):
                raise TypeError(f"canonical output {index} must be a mapping")
            unknown = set(record) - allowed_output_keys
            if unknown:
                raise ValueError(
                    f"canonical output {index} contains unsupported field {sorted(unknown)[0]!r}"
                )
            node_id = _node_id_from_binding(record.get("node"))
            if node_id is None or node_id not in wf.nodes:
                raise ValueError(f"canonical output {index} does not bind a constructed node")
            rebound_outputs.append(
                VibeOutput(
                    node_id=node_id,
                    output_type=str(record.get("output_type") or wf.nodes[node_id].class_type),
                    name=record.get("name"),
                    artifact_kind=record.get("artifact_kind"),
                    mime_type=record.get("mime_type"),
                    filename_prefix=record.get("filename_prefix"),
                    expected_cardinality=record.get("expected_cardinality"),
                )
            )
        wf.outputs = rebound_outputs
    if declared_outputs is not _UNSPECIFIED_OUTPUTS:
        if not isinstance(declared_outputs, (list, tuple)):
            raise TypeError("typed outputs must be a sequence")
        rebound_outputs = []
        for index, record in enumerate(declared_outputs):
            if not isinstance(record, OutputSpec):
                raise TypeError(f"typed output {index} must be an OutputSpec")
            node_id = _node_id_from_binding(record.node)
            if node_id is None or node_id not in wf.nodes:
                raise ValueError(f"typed output {index} does not bind a constructed node")
            rebound_outputs.append(
                VibeOutput(
                    node_id=node_id,
                    output_type=record.output_type or wf.nodes[node_id].class_type,
                    name=record.name,
                    artifact_kind=record.artifact_kind,
                    mime_type=record.mime_type,
                    filename_prefix=record.filename_prefix,
                    expected_cardinality=record.expected_cardinality,
                )
            )
        wf.outputs = rebound_outputs
    if canonical_requirements is not None:
        if not isinstance(canonical_requirements, Mapping):
            raise TypeError("canonical requirements must be a mapping")
        allowed_requirement_keys = {
            "models", "custom_nodes", "missing_models", "missing_nodes", "unsupported",
        }
        unknown = set(canonical_requirements) - allowed_requirement_keys
        if unknown:
            raise ValueError(
                f"canonical requirements contain unsupported field {sorted(unknown)[0]!r}"
            )
        for key in allowed_requirement_keys:
            value = canonical_requirements.get(key, [])
            if not isinstance(value, (list, tuple)):
                raise TypeError(f"canonical requirements {key!r} must be a sequence")
            setattr(wf.requirements, key, deepcopy(list(value)))
    elif external_custody is not None and isinstance(requirements, Mapping):
        # The legacy ready-template policy infers requirements while it
        # rebuilds nodes.  A v2 pair has already captured the complete
        # requirement witness in READY_METADATA, including an intentional
        # empty list, so restore all five fields exactly.  This keeps an
        # authored pair's semantic digest stable without reintroducing the
        # large custody manifest into generated Python.
        for key in ("models", "custom_nodes", "missing_models", "missing_nodes", "unsupported"):
            value = requirements.get(key, [])
            if not isinstance(value, (list, tuple)):
                raise TypeError(f"v2 requirements {key!r} must be a sequence")
            setattr(wf.requirements, key, deepcopy(list(value)))
    if canonical_custody is not None:
        _apply_canonical_custody(wf, canonical_custody, canonical_bindings)
    if canonical_helpers is not None:
        if not isinstance(canonical_helpers, (list, tuple)):
            raise TypeError("canonical helper custody must be a sequence")
        allowed_helper_keys = {"id", "uid", "class_type", "provenance", "native_ports", "pos", "size"}
        retained_helpers: list[dict[str, Any]] = []
        for index, record in enumerate(canonical_helpers):
            if not isinstance(record, Mapping):
                raise TypeError(f"canonical helper custody {index} must be a mapping")
            unknown = set(record) - allowed_helper_keys
            if unknown:
                raise ValueError(
                    f"canonical helper custody {index} contains unsupported field "
                    f"{sorted(unknown)[0]!r}"
                )
            for required in ("id", "uid", "class_type"):
                if not isinstance(record.get(required), str) or not record[required]:
                    raise ValueError(
                        f"canonical helper custody {index} has an invalid {required}"
                    )
            retained_helpers.append(deepcopy(dict(record)))
        wf.metadata["resolver_helper_custody"] = retained_helpers
    for transient in (
        "_canonical_construction_custody",
        "_canonical_construction_index",
        "_canonical_construction_objects",
        "_canonical_v2_custody",
        "_canonical_v2_helpers",
        "_canonical_v2_companion",
    ):
        if hasattr(wf, transient):
            delattr(wf, transient)
    return wf


def _resolve_output_node(wf: VibeWorkflow, output_node: Any, namespace: Mapping[str, Any]) -> str:
    if output_node is None:
        return _autodetect_output_node(wf)
    if isinstance(output_node, SymbolicNodeRef):
        return output_node.resolve(namespace, wf)
    node_id = _node_id_from_binding(output_node)
    if node_id is not None:
        return node_id
    return str(output_node)


def _autodetect_output_node(wf: VibeWorkflow) -> str:
    outgoing = {str(edge.from_node) for edge in wf.edges}
    candidates = [
        str(node_id)
        for node_id, node in wf.nodes.items()
        if str(node_id) not in outgoing and _is_terminal_output_class(node.class_type)
    ]
    candidates.sort(key=lambda item: (int(item) if item.isdigit() else 1 << 30, item))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError("output_node could not be auto-detected; specify explicitly")
    detail = ", ".join(f"{node_id}:{wf.nodes[node_id].class_type}" for node_id in candidates)
    raise ValueError(f"ambiguous output_node; specify explicitly ({detail})")


def _is_terminal_output_class(class_type: str) -> bool:
    if class_type in _OUTPUT_KIND_HEURISTIC:
        return True
    lowered = class_type.lower()
    return (
        lowered.startswith(("save", "preview", "create"))
        or "save" in lowered
        or "preview" in lowered
    )


def _caller_build_locals() -> Mapping[str, Any]:
    frame = inspect.currentframe()
    try:
        cursor = frame.f_back if frame is not None else None
        while cursor is not None:
            if cursor.f_code.co_name == "build":
                return dict(cursor.f_locals)
            cursor = cursor.f_back
        return {}
    finally:
        del frame


def finalize_ready(
    wf: VibeWorkflow,
    metadata: Mapping[str, Any],
    *,
    source_path: str,
    requirements: Mapping[str, Any] | None = None,
) -> VibeWorkflow:
    """Finalize a hand-authored ready template without exposing legacy helpers."""
    _release_workflow_context(wf)
    wf.finalize_metadata()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        apply_ready_template_policy(wf, metadata, source_path=source_path, requirements=requirements)
    return wf


def _release_workflow_context(wf: VibeWorkflow) -> None:
    """Release the eager ``new_workflow()`` binding before finalization work."""
    token = wf._workflow_context_token
    if token is None:
        return
    from vibecomfy.workflow_context import reset_workflow

    try:
        reset_workflow(token)
    finally:
        wf._workflow_context_token = None


def template_input(wf: VibeWorkflow, name: str, node_id: str, field: str, *args: Any, **kwargs: Any) -> None:
    """Bind a public input from a hand-authored ready template."""
    if args:
        if len(args) > 1 or "default" in kwargs:
            raise TypeError("template_input accepts at most one positional default")
        kwargs["default"] = args[0]
    node = wf.nodes.get(str(node_id))
    if field == "widget_0" and node is not None and field not in node.inputs and field not in node.widgets:
        if "value" in node.inputs or "value" in node.widgets:
            field = "value"
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        bind_input(wf, name, node_id, field, **kwargs)


def template_output(wf: VibeWorkflow, node_id: str, **kwargs: Any) -> None:
    """Bind a public output from a hand-authored ready template."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
        bind_output(wf, node_id, **kwargs)


def _derive_edit_guide(inputs: Mapping[str, InputSpec], extra: str | None = None) -> str:
    if not inputs and not extra:
        return ""
    lines = ["Public inputs:"]
    for name, spec in inputs.items():
        description = spec.description or f"Controls {name}."
        lines.append(f"- {name}: {description}")
    if extra:
        lines.append(str(extra))
    return "\n".join(lines)


def _requirements_with_models(
    requirements: Mapping[str, Any] | None,
    model_assets: Any,
) -> dict[str, Any]:
    derived_models = [
        dict(asset)
        for asset in model_assets
        if isinstance(asset, Mapping)
    ]
    merged: dict[str, Any] = dict(requirements or {})
    merged, _warnings = normalize_custom_node_requirements(merged)
    existing_models = merged.get("models")
    if "models" in merged and existing_models == []:
        return merged
    if existing_models and derived_models:
        _warn_on_model_requirement_disagreement(existing_models, derived_models)
        merged["models"] = reconcile_model_requirements(existing_models, derived_models)
    elif derived_models:
        merged["models"] = derived_models
    return merged


def _model_requirement_names(models: Any) -> set[str]:
    names: set[str] = set()
    for model in models or []:
        if isinstance(model, Mapping):
            name = model.get("name")
        else:
            name = model
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _warn_on_model_requirement_disagreement(existing_models: Any, derived_models: list[dict[str, Any]]) -> None:
    global _MODEL_DISAGREEMENT_WARNED
    if _MODEL_DISAGREEMENT_WARNED:
        return
    existing_names = _model_requirement_names(existing_models)
    derived_names = _model_requirement_names(derived_models)
    if existing_names != derived_names:
        warnings.warn(
            "ReadyMetadata.build requirements['models'] differs from MODELS-derived model assets",
            stacklevel=3,
        )
        _MODEL_DISAGREEMENT_WARNED = True


def _model_asset_metadata(model: ModelAsset) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": model.filename,
        "url": model.url,
        "subdir": model.subdir,
    }
    if model.target_path is not None:
        data["target_path"] = model.target_path
    if model.sha256 is not None:
        data["sha256"] = model.sha256
    if model.hf_revision is not None:
        data["hf_revision"] = model.hf_revision
    if model.size_bytes is not None:
        data["size_bytes"] = model.size_bytes
    if model.gated:
        data["gated"] = True
    return data


def _repo_root() -> Path:
    return find_repo_root()


def _caller_source_path() -> Path | None:
    this_file = Path(__file__).resolve()
    frame = inspect.currentframe()
    try:
        cursor = frame.f_back if frame is not None else None
        while cursor is not None:
            filename = cursor.f_code.co_filename
            if filename and filename not in {"<string>", "<stdin>"}:
                path = Path(filename).resolve()
                if path != this_file:
                    return path
            cursor = cursor.f_back
        return None
    finally:
        del frame


def _derive_template_id(template_id: str | None, source_path: Path | None) -> str:
    if template_id:
        return template_id
    if source_path is not None:
        try:
            return source_path.resolve().relative_to(_repo_root() / "ready_templates").with_suffix("").as_posix()
        except ValueError:
            return source_path.stem
    return "ready_template"


def _coverage_manifest_row(template_id: str) -> dict[str, Any]:
    path = _repo_root() / "ready_templates/sources" / "manifests" / "coverage.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    rows = data.get("workflows") if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        rows = data if isinstance(data, list) else []
    short_id = template_id.rsplit("/", 1)[-1]
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        candidates = {
            str(row.get("ready_template") or ""),
            str(row.get("template_id") or ""),
            str(row.get("id") or ""),
        }
        media = row.get("media")
        row_id = row.get("id")
        if isinstance(media, str) and isinstance(row_id, str):
            candidates.add(f"{media}/{row_id}")
        if template_id in candidates or short_id in candidates:
            return dict(row)
    return {}


def _derive_source_workflow(
    extras: Mapping[str, Any],
    coverage_row: Mapping[str, Any],
    source_path: Path | None,
) -> str | None:
    provenance = extras.get("provenance")
    if isinstance(provenance, Mapping) and isinstance(provenance.get("source_workflow"), str):
        return provenance["source_workflow"]
    explicit = extras.get("source_workflow")
    if isinstance(explicit, str):
        return explicit
    for key in ("path", "source_workflow", "workflow_path"):
        value = coverage_row.get(key)
        if isinstance(value, str) and value:
            return value
    if source_path is not None:
        try:
            text = source_path.read_text(encoding="utf-8")
        except OSError:
            return None
        match = re.search(r"^\s*#\s*ported from\s+(.+?)\s*$", text, flags=re.MULTILINE)
        if match:
            return match.group(1).split(" (", 1)[0].strip()
        match = re.search(r"^\s*Source:\s*(.+?)\s*$", text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _project_version() -> str:
    try:
        data = tomllib.loads((_repo_root() / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "0"
    project = data.get("project") if isinstance(data, Mapping) else None
    version = project.get("version") if isinstance(project, Mapping) else None
    return str(version) if version else "0"


def _comfy_core_metadata() -> dict[str, Any]:
    try:
        data = json.loads((_repo_root() / "vibecomfy" / "comfy_metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, Mapping):
        return {}
    core = data.get("core") if isinstance(data.get("core"), Mapping) else data
    return {
        key: value
        for key, value in core.items()
        if key in {"version", "commit", "tested_at", "status"}
    }


def _assert_public_input_invariant(
    wf: VibeWorkflow,
    inputs: Mapping[str, InputSpec],
    namespace: Mapping[str, Any] | None = None,
) -> None:
    specs = {
        name: (spec.resolve_node_id(wf, namespace=namespace), spec.field)
        for name, spec in inputs.items()
    }
    alias_names = {
        str(alias)
        for spec in inputs.values()
        for alias in spec.aliases
    }
    for name, (node_id, field) in specs.items():
        registered = wf.inputs.get(name)
        if registered is None:
            raise AssertionError(f"public input {name!r} was not registered")
        if (str(registered.node_id), registered.field) != (node_id, field):
            raise AssertionError(
                f"public input {name!r} target drift: "
                f"expected {node_id}.{field}, got {registered.node_id}.{registered.field}"
            )

    unexpected = {
            name
            for name, registered in wf.inputs.items()
            if name not in specs
            and name not in alias_names
            and (str(registered.node_id), registered.field) in set(specs.values())
        }
    if unexpected:
        raise AssertionError(
            "registered inputs target PUBLIC_INPUTS nodes but are not declared: "
            + ", ".join(sorted(unexpected))
        )


def _drop_shadowed_auto_inputs(
    wf: VibeWorkflow,
    inputs: Mapping[str, InputSpec],
    namespace: Mapping[str, Any] | None = None,
) -> None:
    specs = {
        name: (spec.resolve_node_id(wf, namespace=namespace), spec.field)
        for name, spec in inputs.items()
    }
    alias_names = {
        str(alias)
        for spec in inputs.values()
        for alias in spec.aliases
    }
    explicit_targets = set(specs.values())
    for name, registered in list(wf.inputs.items()):
        if name in specs or name in alias_names:
            continue
        if (str(registered.node_id), registered.field) in explicit_targets:
            del wf.inputs[name]


__all__ = [
    "InputSpec",
    "ModelAsset",
    "OutputSpec",
    "ReadyMetadata",
    "_at",
    "_current_workflow_or_raise",
    "_derive_output_kind",
    "finalize",
    "finalize_ready",
    "new_workflow",
    "node",
    "template_input",
    "template_output",
]
