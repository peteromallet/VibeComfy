"""Selection and approval of one ephemeral runtime-eval candidate graph."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from vibecomfy.analysis.graph import upstream
from vibecomfy.errors import RuntimeNodeError
from vibecomfy.handles import Handle
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundle,
    WorkflowBundleError,
    load_bundle,
)

from .preview_types import PREVIEW_MAP, VAE_EMITTER_CLASSES, VIDEO_FALLBACK


def _node_error(message: str, node_id: str) -> RuntimeNodeError:
    return RuntimeNodeError(message, next_action=f"vibecomfy inspect <workflow> --node {node_id}")


def select_eval_workflow(bundle: WorkflowBundle, target_node_id: str) -> VibeWorkflow:
    """Return a copied upstream graph with deterministic preview nodes."""
    if not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError(
            "eval selection requires a WorkflowBundle; load the source with "
            "load_bundle(...) before calling select_eval_workflow"
        )
    bundle.require_canonical_authority("runtime evaluation")
    workflow = bundle.workflow
    nid = str(target_node_id)
    if "#" in nid or "/" in nid:
        raise _node_error("qualified eval node ids are not supported; select a root node", nid)
    if nid not in workflow.nodes:
        raise _node_error(f"eval node {nid!r} is not present in the root workflow", nid)

    target = workflow.nodes[nid]
    output_type = _detect_output_type(workflow, target)
    upstream_ids = upstream(workflow, nid)
    selected_ids: set[str] = {nid, *upstream_ids}
    latent_vae_handle: Handle | None = None
    if output_type == "LATENT":
        latent_vae_handle = _resolve_upstream_vae_handle(workflow, upstream_ids)
        injections = (
            (f"{nid}_vaedecode", "VAEDecode", {}, nid, "0", "samples"),
            (f"{nid}_preview", "PreviewImage", {}, f"{nid}_vaedecode", "0", "images"),
        )
    else:
        preview = PREVIEW_MAP.get(output_type)
        if preview is None and output_type == "VIDEO":
            preview = VIDEO_FALLBACK
        if preview is None:
            raise _node_error(f"node {nid!r} has non-visualizable output {output_type!r}; eval is plan-only", nid)
        injections = (
            (f"{nid}_preview", preview.class_type, copy.deepcopy(preview.extra_inputs or {}), nid, "0", preview.output_input_slot),
        )

    for preview_id, _class_type, _inputs, _from, _output, _to in injections:
        if preview_id in workflow.nodes or preview_id in {str(node.uid) for node in workflow.nodes.values()}:
            raise _node_error(f"preview node identity {preview_id!r} collides with source graph", nid)

    candidate = workflow.copy()
    candidate.nodes = {
        node_id: copy.deepcopy(candidate.nodes[node_id])
        for node_id in sorted(selected_ids)
        if node_id in candidate.nodes
    }
    candidate.edges = [
        copy.deepcopy(edge)
        for edge in candidate.edges
        if edge.from_node in selected_ids and edge.to_node in selected_ids
    ]
    candidate.inputs = {name: copy.deepcopy(item) for name, item in candidate.inputs.items() if str(item.node_id) in selected_ids}
    candidate.outputs = [copy.deepcopy(item) for item in candidate.outputs if str(item.node_id) in selected_ids]
    candidate.groups = []
    candidate.definitions = {}
    candidate.interfaces = {}
    candidate.boundary_ports = []
    candidate.virtual_wires = {}
    for preview_id, class_type, inputs, from_node, from_output, to_input in injections:
        is_decoder = class_type == "VAEDecode"
        candidate.nodes[preview_id] = VibeNode(
            id=preview_id,
            uid=preview_id,
            class_type=class_type,
            inputs=inputs,
            native_input_names=["samples", "vae"] if is_decoder else [to_input],
            native_output_names=["IMAGE"] if is_decoder else [],
            native_input_types=["LATENT", "VAE"] if is_decoder else None,
            native_output_types=["IMAGE"] if is_decoder else [],
        )
        candidate.edges.append(VibeEdge(from_node=from_node, from_output=from_output, to_node=preview_id, to_input=to_input))
    if latent_vae_handle is not None:
        candidate.edges.append(
            VibeEdge(
                from_node=latent_vae_handle.node_id,
                from_output=str(latent_vae_handle.output_slot),
                to_node=f"{nid}_vaedecode",
                to_input="vae",
            )
        )
    return candidate


def approve_eval_subgraph(
    bundle: WorkflowBundle,
    target_node_id: str,
    *,
    variant: str | None = None,
    run_inputs: Mapping[str, Any] | None = None,
    schema_provider: Any = None,
) -> tuple[WorkflowBundle, ApprovedProjectionRecord]:
    """Select, ephemerally bind, and approve one eval candidate graph."""
    candidate = select_eval_workflow(bundle, target_node_id)
    if schema_provider is not None:
        _retain_explicit_provider_ports(candidate, schema_provider)
    candidate_bundle = load_bundle(candidate)
    record = candidate_bundle.compile(
        variant=variant,
        run_inputs=None if run_inputs is None else dict(run_inputs),
        schema_provider=schema_provider,
    )
    return candidate_bundle, record


def _retain_explicit_provider_ports(
    workflow: VibeWorkflow,
    schema_provider: Any,
) -> None:
    """Freeze exact supplied-schema ports onto an eval candidate before approval."""
    for node in workflow.nodes.values():
        schema = schema_provider.get_schema(node.class_type)
        if schema is None:
            continue
        inputs = getattr(schema, "inputs", None)
        if node.native_input_names is None and isinstance(inputs, Mapping):
            node.native_input_names = [str(name) for name in inputs]
            node.native_input_types = [
                str(getattr(spec, "type"))
                if getattr(spec, "type", None) is not None
                else None
                for spec in inputs.values()
            ]
            node.native_input_optional = [
                not bool(getattr(spec, "required", False))
                for spec in inputs.values()
            ]
            assets = [
                str(getattr(spec, "asset_kind"))
                if getattr(spec, "asset_kind", None) is not None
                else None
                for spec in inputs.values()
            ]
            node.native_input_asset_kinds = assets if any(assets) else None
        outputs = getattr(schema, "outputs", None)
        if node.native_output_names is None and isinstance(outputs, (list, tuple)):
            node.native_output_names = [
                str(getattr(spec, "name"))
                if getattr(spec, "name", None) is not None
                else None
                for spec in outputs
            ]
            node.native_output_types = [
                str(getattr(spec, "type"))
                if getattr(spec, "type", None) is not None
                else None
                for spec in outputs
            ]
        node.__post_init__()


def _detect_output_type(workflow: VibeWorkflow, target: VibeNode) -> str:
    nid = str(target.id)
    for output in workflow.outputs:
        if str(output.node_id) == nid:
            return str(output.output_type).upper()
    ct = target.class_type.lower()
    if "vae" in ct and "decode" in ct:
        return "IMAGE"
    if "vae" in ct and ("encode" in ct or "loader" in ct):
        return "LATENT"
    if "ksampler" in ct or "latent" in ct or "sampler" in ct:
        return "LATENT"
    if "preview" in ct or "save" in ct or "image" in ct or "img" in ct:
        return "MASK" if "mask" in ct else "VIDEO" if "video" in ct else "AUDIO" if "audio" in ct else "IMAGE"
    if "mask" in ct:
        return "MASK"
    if "video" in ct:
        return "VIDEO"
    if "audio" in ct:
        return "AUDIO"
    return "UNKNOWN"


def _resolve_upstream_vae_handle(
    workflow: VibeWorkflow,
    upstream_ids: set[str],
) -> Handle:
    """Resolve exactly one closed-contract upstream generic VAE output."""
    candidates: list[Handle] = []
    for node_id in sorted(upstream_ids):
        node = workflow.nodes.get(node_id)
        if node is None:
            continue
        descriptor = VAE_EMITTER_CLASSES.get(node.class_type)
        if descriptor is None or not _valid_vae_rosters(node, descriptor.output_slot, descriptor.name, descriptor.output_type):
            continue
        candidates.append(
            Handle(
                node_id=str(node_id),
                output_slot=descriptor.output_slot,
                output_type=descriptor.output_type,
                name=descriptor.name,
            )
        )
    if not candidates:
        raise RuntimeNodeError(
            "vae_handle_unresolved: no valid upstream generic VAE handle; eval is plan-only",
            next_action="add one valid VAELoader or CheckpointLoaderSimple upstream of the target",
        )
    if len(candidates) > 1:
        source_ids = [f"{item.node_id}:{item.output_slot}" for item in candidates]
        raise RuntimeNodeError(
            f"vae_source_ambiguous: multiple valid upstream VAE handles: {source_ids}",
            next_action="leave exactly one generic VAE emitter on the selected upstream path",
        )
    return candidates[0]


def _valid_vae_rosters(node: VibeNode, output_slot: int, name: str, output_type: str) -> bool:
    """Validate every source-attached output roster without schema lookup."""
    sources: list[tuple[str, Any, str]] = []
    native = node.native_output_names
    if native is not None:
        sources.append(("native_output_names", native, "name"))
    metadata = node.metadata if isinstance(node.metadata, dict) else {}
    if "output_names" in metadata and metadata["output_names"] is not None:
        sources.append(("output_names", metadata["output_names"], "name"))
    if "output_types" in metadata and metadata["output_types"] is not None:
        sources.append(("output_types", metadata["output_types"], "type"))
    for source_name, roster, kind in sources:
        if not isinstance(roster, (list, tuple)) or len(roster) <= output_slot:
            return False
        if any(not isinstance(item, str) or not item.strip() for item in roster):
            return False
        if len(set(roster)) != len(roster):
            return False
        if kind == "name" and roster[output_slot] != name:
            return False
        if kind == "type" and roster[output_slot] != output_type:
            return False
    return True


__all__ = ["approve_eval_subgraph", "select_eval_workflow"]
