"""Selection and approval of one ephemeral runtime-eval candidate graph."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from vibecomfy.analysis.graph import upstream
from vibecomfy.errors import RuntimeNodeError
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
    if output_type == "LATENT":
        vae_node_id = _find_upstream_vae(workflow, nid, upstream_ids)
        if vae_node_id is None:
            raise _node_error("LATENT eval output has no upstream VAE and is plan-only/non-queueable", nid)
        selected_ids.add(vae_node_id)
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
        candidate.nodes[preview_id] = VibeNode(id=preview_id, uid=preview_id, class_type=class_type, inputs=inputs)
        candidate.edges.append(VibeEdge(from_node=from_node, from_output=from_output, to_node=preview_id, to_input=to_input))
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
    candidate_bundle = load_bundle(candidate)
    record = candidate_bundle.compile(
        variant=variant,
        run_inputs=None if run_inputs is None else dict(run_inputs),
        schema_provider=schema_provider,
    )
    return candidate_bundle, record


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


def _find_upstream_vae(workflow: VibeWorkflow, target_node_id: str, upstream_ids: set[str]) -> str | None:
    depths = _upstream_depths(workflow, target_node_id)
    candidates = [
        (depths.get(node_id, 1 << 30), node_id)
        for node_id in upstream_ids
        if node_id in workflow.nodes and workflow.nodes[node_id].class_type in VAE_EMITTER_CLASSES
    ]
    return min(candidates)[1] if candidates else None


def _upstream_depths(workflow: VibeWorkflow, node_id: str) -> dict[str, int]:
    from collections import deque

    reverse: dict[str, set[str]] = {}
    for edge in workflow.edges:
        reverse.setdefault(str(edge.to_node), set()).add(str(edge.from_node))
    depths = {str(node_id): 0}
    queue = deque([str(node_id)])
    while queue:
        current = queue.popleft()
        for parent in reverse.get(current, ()):
            if parent not in depths:
                depths[parent] = depths[current] + 1
                queue.append(parent)
    return depths


__all__ = ["approve_eval_subgraph", "select_eval_workflow"]
