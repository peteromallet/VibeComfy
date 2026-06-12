from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.handles import Handle
from vibecomfy.custom_node_refs import normalize_custom_node_requirements
from vibecomfy.workflow import VibeOutput, VibeWorkflow, WorkflowSource


def build_api_ready_workflow(
    api_workflow: dict[str, Any],
    ready_metadata: Mapping[str, Any],
    *,
    source_path: str,
    workflow_id: str | None = None,
    requirements: Mapping[str, list[Any]] | None = None,
) -> VibeWorkflow:
    metadata = dict(ready_metadata)
    workflow = convert_to_vibe_format(
        api_workflow,
        source_path=source_path,
        workflow_id=workflow_id or metadata.get("ready_template") or Path(source_path).stem,
    )
    return apply_ready_template_policy(
        workflow,
        metadata,
        source_path=source_path,
        requirements=requirements,
    )


def apply_ready_template_policy(
    workflow: VibeWorkflow,
    ready_metadata: Mapping[str, Any],
    *,
    source_path: str,
    requirements: Mapping[str, list[Any]] | None = None,
) -> VibeWorkflow:
    warnings.warn(
        "apply_ready_template_policy is deprecated for generated ready templates. "
        "Use vibecomfy.templates.finalize() instead.",
        PendingDeprecationWarning,
        stacklevel=2,
    )
    metadata = dict(ready_metadata)
    template_id = metadata.get("ready_template")
    if isinstance(template_id, str) and "/" not in template_id:
        path = Path(source_path)
        if path.parent.name and path.parent.parent.name == "ready_templates":
            metadata["ready_template"] = f"{path.parent.name}/{template_id}"
            metadata["workflow_template"] = template_id
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping):
        metadata.update({str(key): value for key, value in provenance.items() if key not in metadata})
    workflow.metadata.update(metadata)
    workflow.metadata["ready_template_path"] = source_path
    workflow.metadata["python_policy_applied"] = True
    if not workflow.nodes:
        raise ValueError("ready template produced no nodes")
    if requirements:
        _merge_requirements(workflow, requirements)
    return workflow


def apply_authored_metadata(
    workflow: VibeWorkflow,
    ready_metadata: Mapping[str, Any],
    *,
    requirements: Mapping[str, list[Any]] | None = None,
    source_path: str,
) -> VibeWorkflow:
    workflow.finalize_metadata()
    return apply_ready_template_policy(
        workflow,
        ready_metadata,
        source_path=source_path,
        requirements=requirements,
    )


def build_authored_ready_workflow(
    nodes: tuple[tuple[str, str, dict[str, Any]], ...],
    ready_metadata: Mapping[str, Any],
    *,
    source_path: str,
    workflow_id: str | None = None,
    requirements: Mapping[str, list[Any]] | None = None,
    registered_inputs: Mapping[str, tuple[str, str]] | None = None,
) -> VibeWorkflow:
    metadata = dict(ready_metadata)
    workflow = VibeWorkflow(
        workflow_id or str(metadata.get("ready_template") or Path(source_path).stem),
        WorkflowSource(
            id=workflow_id or str(metadata.get("ready_template") or Path(source_path).stem),
            path=source_path,
            source_type="ready_template",
        ),
    )
    node_ids = {old_id for old_id, _, _ in nodes}
    handles: dict[tuple[str, int], Handle] = {}
    old_to_new: dict[str, str] = {}

    for old_id, class_type, inputs in nodes:
        kwargs = {
            name: _authored_value(value, handles, node_ids)
            for name, value in dict(inputs).items()
        }
        builder = workflow.node(class_type, **kwargs)
        temp_id = builder.id
        if temp_id != old_id:
            node = workflow.nodes.pop(temp_id)
            node.id = old_id
            workflow.nodes[old_id] = node
            for edge in workflow.edges:
                if edge.to_node == temp_id:
                    edge.to_node = old_id
        old_to_new[old_id] = old_id
        for slot in _referenced_output_slots(nodes, old_id):
            handles[(old_id, slot)] = builder.out(slot)
        handles.setdefault((old_id, 0), builder.out(0))

    apply_authored_metadata(workflow, metadata, source_path=source_path, requirements=requirements)
    for input_name, (old_id, field) in dict(registered_inputs or {}).items():
        new_id = old_to_new[old_id]
        node = workflow.nodes[new_id]
        value = node.inputs.get(field, node.widgets.get(field))
        workflow.register_input(input_name, new_id, field, value)
    return workflow


def _authored_value(value: Any, handles: Mapping[tuple[str, int], Handle], node_ids: set[str]) -> Any:
    if _is_authored_link(value, node_ids):
        key = (str(value[0]), int(value[1]))
        return handles.get(key) or Handle(node_id=key[0], output_slot=key[1])
    return value


def _referenced_output_slots(nodes: tuple[tuple[str, str, dict[str, Any]], ...], old_id: str) -> set[int]:
    node_ids = {node_id for node_id, _, _ in nodes}
    slots = {0}
    for _, _, inputs in nodes:
        for value in inputs.values():
            if _is_authored_link(value, node_ids) and str(value[0]) == old_id:
                slots.add(int(value[1]))
    return slots


def _is_authored_link(value: Any, node_ids: set[str]) -> bool:
    return isinstance(value, list) and len(value) == 2 and str(value[0]) in node_ids and isinstance(value[1], int)


def _merge_requirements(workflow: VibeWorkflow, requirements: Mapping[str, list[Any]]) -> None:
    normalized, _warnings = normalize_custom_node_requirements(requirements)
    for model in requirements.get("models", []):
        if isinstance(model, Mapping):
            name = model.get("name")
            if not isinstance(name, str) or not name:
                continue
            if name not in workflow.requirements.models:
                workflow.requirements.models.append(name)
            _append_model_asset(workflow, model)
        elif isinstance(model, str) and model not in workflow.requirements.models:
            workflow.requirements.models.append(model)
    for custom_node in normalized.get("custom_nodes", []):
        if custom_node not in workflow.requirements.custom_nodes:
            workflow.requirements.custom_nodes.append(custom_node)
    workflow.requirements.models.sort()
    workflow.requirements.custom_nodes.sort()
    if normalized.get("custom_node_refs"):
        meta_reqs = workflow.metadata.setdefault("requirements", {})
        if isinstance(meta_reqs, dict):
            existing_refs = list(meta_reqs.get("custom_node_refs") or [])
            meta_reqs["custom_node_refs"] = [*existing_refs, *normalized["custom_node_refs"]]
            meta_reqs["custom_nodes"] = sorted(set(workflow.requirements.custom_nodes))


def _append_model_asset(workflow: VibeWorkflow, asset: Mapping[str, Any]) -> None:
    model_assets = workflow.metadata.setdefault("model_assets", [])
    if not isinstance(model_assets, list):
        model_assets = []
        workflow.metadata["model_assets"] = model_assets
    key = (asset.get("name"), asset.get("subdir"))
    if any(isinstance(existing, Mapping) and (existing.get("name"), existing.get("subdir")) == key for existing in model_assets):
        return
    model_assets.append(dict(asset))


_MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".gguf", ".pt", ".bin", ".pth")


def _referenced_model_filenames(workflow: VibeWorkflow) -> set[str]:
    filenames: set[str] = set()
    for node in workflow.nodes.values():
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if isinstance(value, str) and value.endswith(_MODEL_EXTENSIONS):
                filenames.add(value)
                filenames.add(Path(value.replace("\\", "/")).name)
    return filenames


def ready_workflow(
    workflow_id: str,
    *,
    source_path: str,
    source_type: str = "ready_template",
    provenance: Mapping[str, Any] | None = None,
) -> VibeWorkflow:
    """Create a VibeWorkflow with a properly populated WorkflowSource.

    This is the canonical constructor for emitted ready-template code,
    replacing the inline ``VibeWorkflow(...)`` / ``WorkflowSource(...)``
    boilerplate.
    """
    return VibeWorkflow(
        workflow_id,
        WorkflowSource(
            id=workflow_id,
            path=source_path,
            source_type=source_type,
            provenance=dict(provenance) if provenance else {},
        ),
    )


def ready_node(
    wf: VibeWorkflow,
    class_type: str,
    *,
    source_id: str | None = None,
    outputs: tuple[str, ...] | None = None,
    extras: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    """Create a node, preserving a source-side *source_id* when provided.

    Semantically equivalent to the old ``_node()`` helper but lives in the
    shared registry so generated ready templates don't need to inline it.

    * *source_id* -- if given and different from the auto-assigned node id,
      the node is renamed in ``wf.nodes`` and all edge references are updated.
    * *outputs* -- attaches ``output_names`` metadata to the node so later
      ``.out('name')`` calls work.
    * *extras* -- dict of kwargs whose names are not valid Python identifiers
      (e.g. ``\"resize_type.multiple\"``).  Handle values in *extras* are
      connected as edges; plain values are set as inputs.
    """
    from vibecomfy.handles import Handle

    builder = wf.node(class_type, **kwargs)
    if outputs is not None:
        builder.node.metadata["output_names"] = list(outputs)
    if source_id is not None:
        builder.node.metadata["source_id"] = str(source_id)
        if not str(source_id).isdigit():
            builder.node.metadata["source_id_nonnumeric"] = True
        wf.metadata.setdefault("id_map", {})[str(source_id)] = builder.node.id
    if extras:
        for key, value in extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if source_id is not None and builder.node.id != source_id:
        old_id = builder.node.id
        # If ``source_id`` is already occupied by a *different* node (e.g. an
        # auto-id-allocated node such as a subgraph-materialized VAEDecode that
        # happened to claim the numeric id this node wants to reclaim from its
        # source), relocate that occupant to a fresh id first instead of
        # silently overwriting it. Overwriting would drop a real node and leave
        # dangling/self-referential edges.
        occupant = wf.nodes.get(source_id)
        if occupant is not None and occupant is not builder.node:
            relocated_id = wf._next_node_id()
            wf.nodes.pop(source_id)
            occupant.id = relocated_id
            wf.nodes[relocated_id] = occupant
            for edge in wf.edges:
                if edge.to_node == source_id:
                    edge.to_node = relocated_id
                if edge.from_node == source_id:
                    edge.from_node = relocated_id
            for key, mapped in list(wf.metadata.get("id_map", {}).items()):
                if mapped == source_id:
                    wf.metadata["id_map"][key] = relocated_id
        node = wf.nodes.pop(old_id)
        node.id = source_id
        wf.nodes[source_id] = node
        wf.metadata.setdefault("id_map", {})[str(source_id)] = source_id
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = source_id
            if edge.from_node == old_id:
                edge.from_node = source_id
    return builder


def finalize_ready_template(
    wf: VibeWorkflow,
    ready_metadata: Mapping[str, Any],
    *,
    source_path: str,
    requirements: Mapping[str, list[Any]] | None = None,
) -> VibeWorkflow:
    """Call ``finalize_metadata()`` then ``apply_ready_template_policy()``.

    The order remains conventional for generated templates: finalize first to
    infer graph metadata, then bind any explicit public inputs/outputs.
    """
    wf.finalize_metadata()
    return apply_ready_template_policy(
        wf,
        ready_metadata,
        source_path=source_path,
        requirements=requirements,
    )


def bind_input(
    wf: VibeWorkflow,
    name: str,
    node_id: str,
    field: str,
    *,
    type: str | None = None,
    default: Any = None,
    required: bool = False,
    range: Any = None,
    aliases: list[str] | tuple[str, ...] | None = None,
    media_semantics: str | None = None,
    media: str | None = None,
) -> VibeWorkflow:
    """Register a public input binding **after** ``finalize_ready_template()``.

    Validates that *node_id* exists in ``wf.nodes`` and that *field* is a
    known input/widget key on that node.  Raises ``ValueError`` with a
    descriptive message when either check fails.
    """
    warnings.warn(
        "bind_input is deprecated for generated ready templates. "
        "Use InputSpec.register() inside vibecomfy.templates.finalize() instead.",
        PendingDeprecationWarning,
        stacklevel=2,
    )
    if node_id not in wf.nodes:
        raise ValueError(
            f"bind_input({name!r}): target node {node_id!r} does not exist "
            f"in workflow {wf.id!r}"
        )
    node = wf.nodes[node_id]
    if field not in node.inputs and field not in node.widgets:
        raise ValueError(
            f"bind_input({name!r}): field {field!r} not found in "
            f"node {node_id!r} ({node.class_type}) inputs or widgets"
        )
    if media_semantics is not None and media is not None and media_semantics != media:
        raise ValueError(
            f"bind_input({name!r}): media_semantics and legacy media "
            "must match when both are provided"
        )
    value = node.inputs.get(field, node.widgets.get(field))
    return wf.register_input(
        name,
        node_id,
        field,
        value,
        type=type,
        default=value if default is None else default,
        required=required,
        range=range,
        aliases=aliases,
        media_semantics=media_semantics if media_semantics is not None else media,
    )


def bind_output(
    wf: VibeWorkflow,
    node_id: str,
    *,
    output_type: str | None = None,
    name: str | None = None,
    artifact_kind: str | None = None,
    mime_type: str | None = None,
    filename_prefix: str | None = None,
    expected_cardinality: str | int | None = None,
) -> VibeWorkflow:
    """Register or update a public output binding.

    If the workflow already has a ``VibeOutput`` for *node_id*, its fields
    are updated in-place.  Otherwise a new ``VibeOutput`` is appended.

    This should be called **after** ``finalize_ready_template()`` so that
    the binding survives finalization.
    """
    warnings.warn(
        "bind_output is deprecated for generated ready templates. "
        "Use vibecomfy.templates.finalize() instead.",
        PendingDeprecationWarning,
        stacklevel=2,
    )
    output_type = output_type or ""
    for existing in wf.outputs:
        if existing.node_id == node_id:
            if name is not None:
                existing.name = name
            if artifact_kind is not None:
                existing.artifact_kind = artifact_kind
            if mime_type is not None:
                existing.mime_type = mime_type
            if filename_prefix is not None:
                existing.filename_prefix = filename_prefix
            if expected_cardinality is not None:
                existing.expected_cardinality = expected_cardinality
            if output_type and not existing.output_type:
                existing.output_type = output_type
            return wf
    wf.outputs.append(
        VibeOutput(
            node_id=node_id,
            output_type=output_type,
            name=name,
            artifact_kind=artifact_kind,
            mime_type=mime_type,
            filename_prefix=filename_prefix,
            expected_cardinality=expected_cardinality,
        )
    )
    return wf


def finalise_model_assets(workflow: VibeWorkflow) -> None:
    referenced = _referenced_model_filenames(workflow)
    raw_assets = workflow.metadata.get("model_assets", [])
    extra_assets = workflow.metadata.pop("model_assets_extra", [])
    replaced_by_policy = set(workflow.metadata.pop("model_assets_replaced_by_policy", []))
    filtered = [
        asset
        for asset in raw_assets
        if isinstance(asset, dict)
        and isinstance(asset.get("name"), str)
        and asset["name"] not in replaced_by_policy
        and (asset["name"] in referenced or _asset_name_appears_in_workflow_text(workflow, asset["name"]))
    ]
    combined = filtered + [asset for asset in extra_assets if isinstance(asset, dict)]
    final_assets: list[dict[str, Any]] = []
    seen: set[tuple[object, object]] = set()
    for asset in combined:
        key = (asset.get("name"), asset.get("subdir"))
        if key in seen:
            continue
        seen.add(key)
        final_assets.append(asset)
    workflow.metadata["model_assets"] = final_assets


finalize_model_assets = finalise_model_assets


def _asset_name_appears_in_workflow_text(workflow: VibeWorkflow, name: str) -> bool:
    for node in workflow.nodes.values():
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if isinstance(value, str) and name in value:
                return True
    return False


_finalise_model_assets = finalise_model_assets


__all__ = [
    "apply_authored_metadata",
    "apply_ready_template_policy",
    "bind_input",
    "bind_output",
    "build_authored_ready_workflow",
    "build_api_ready_workflow",
    "finalize_ready_template",
    "finalize_model_assets",
    "finalise_model_assets",
    "ready_node",
    "ready_workflow",
    "_finalise_model_assets",
]
