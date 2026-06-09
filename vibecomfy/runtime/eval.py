"""Preview subgraph compilation for ``vibecomfy runtime eval-node``.

Provides :func:`compile_eval_subgraph` which traces upstream dependencies
of a single target node, builds a minimal subgraph, and injects preview
nodes for visualizable output types.  LATENT outputs with no discoverable
upstream VAE fall back to metadata-only per SD1.


"""

from __future__ import annotations

import logging
from typing import Any


from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow

from .preview_types import PREVIEW_MAP, VAE_EMITTER_CLASSES, VIDEO_FALLBACK

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compile_eval_subgraph(
    workflow: VibeWorkflow,
    target_node_id: str,
    *,
    backend: str = "api",
) -> dict[str, Any]:
    """Compile a minimal subgraph that evaluates *target_node_id*.

    Traces upstream dependencies, builds a temporary :class:`VibeWorkflow`
    containing only the required nodes + edges, and calls
    :meth:`VibeWorkflow.compile` on it.

    Parameters:
        workflow:
            The full source workflow.
        target_node_id:
            The node whose output should be previewed.
        backend:
            Compilation backend (``\"api\"`` or ``\"graphbuilder\"``).

    Returns:
        Either an API dict (for visualizable / preview-injectable outputs)
        *or* a metadata dict ``{type, shape?, node_id, class_type,
        previewable: false, plan_only?: true}`` for non-visualizable
        outputs.

    Raises:
        KeyError: if *target_node_id* is not in *workflow*.
        RuntimeNodeError: if no runtime is available at eval time
            (caller should catch and suggest ``vibecomfy runtime doctor``).
    """
    nid = str(target_node_id)
    if nid not in workflow.nodes:
        raise KeyError(nid)

    target_node = workflow.nodes[nid]
    output_type = _detect_output_type(workflow, target_node)

    # --- Trace upstream ------------------------------------------------------
    from vibecomfy.analysis.graph import upstream

    upstream_ids = upstream(workflow, nid)
    selected_ids: set[str] = {nid} | upstream_ids

    # --- Handle LATENT with VAE discovery ------------------------------------
    if output_type == "LATENT":
        vae_node_id = _find_upstream_vae(workflow, nid, upstream_ids)
        if vae_node_id is not None:
            # Inject VAEDecode + PreviewImage
            selected_ids.add(vae_node_id)
            return _build_latent_preview_subgraph(
                workflow, nid, vae_node_id, selected_ids, backend=backend
            )
        else:
            # SD1: metadata fallback — no upstream VAE
            return _latent_metadata_fallback(workflow, nid, target_node)

    # --- Visualizable output types -------------------------------------------
    preview = PREVIEW_MAP.get(output_type)
    if preview is not None:
        return _build_preview_subgraph(
            workflow, nid, preview, selected_ids, backend=backend
        )

    # VIDEO fallback if primary not in map
    if output_type == "VIDEO":
        return _build_preview_subgraph(
            workflow, nid, VIDEO_FALLBACK, selected_ids, backend=backend
        )

    # --- Non-visualizable ----------------------------------------------------
    return _non_visualizable_metadata(target_node, nid)



# ---------------------------------------------------------------------------
# Output type detection
# ---------------------------------------------------------------------------


def _detect_output_type(
    workflow: VibeWorkflow,
    target_node: VibeNode,
) -> str:
    """Best-effort detection of the output category for *target_node*.

    Heuristic order:
    1. Check workflow outputs for a label matching this node_id.
    2. Check class_type name for known patterns (VAEDecode → IMAGE,
       KSampler → LATENT, etc.).
    3. Default to ``\"UNKNOWN\"``.
    """
    nid = str(target_node.id)

    # Check explicit workflow outputs
    for output in workflow.outputs:
        if str(output.node_id) == nid:
            return output.output_type.upper()

    # Class-type heuristics
    ct = target_node.class_type.lower()
    if "vae" in ct and "decode" in ct:
        return "IMAGE"
    if "vae" in ct and ("encode" in ct or "loader" in ct):
        return "LATENT"
    if "ksampler" in ct or "latent" in ct or "sampler" in ct:
        return "LATENT"
    if "preview" in ct or "save" in ct:
        # Preview/SaveImage, PreviewMask, etc. — return the suffix
        if "mask" in ct:
            return "MASK"
        if "video" in ct:
            return "VIDEO"
        if "audio" in ct:
            return "AUDIO"
        return "IMAGE"
    if "image" in ct or "img" in ct:
        return "IMAGE"
    if "mask" in ct:
        return "MASK"
    if "video" in ct:
        return "VIDEO"
    if "audio" in ct:
        return "AUDIO"
    if "latent" in ct:
        return "LATENT"

    return "UNKNOWN"


# ---------------------------------------------------------------------------
# VAE discovery (upstream only — SD1 / FLAG-001)
# ---------------------------------------------------------------------------


def _find_upstream_vae(
    workflow: VibeWorkflow,
    target_node_id: str,
    upstream_ids: set[str],
) -> str | None:
    """Find a VAE-emitting node among the upstream dependencies.

    Returns the node_id of the closest VAE-emitting node, or ``None``.
    Only walks upstream dependencies (edges reversed: ``edge.to_node →
    edge.from_node``).  Sibling VAE loaders outside the upstream path are
    out of scope per FLAG-001.
    """
    vae_candidates: list[tuple[int, str]] = []
    # Compute BFS depth from target to each upstream node
    depths = _upstream_depths(workflow, target_node_id)

    for uid in upstream_ids:
        if uid not in workflow.nodes:
            continue
        node = workflow.nodes[uid]
        if node.class_type in VAE_EMITTER_CLASSES:
            depth = depths.get(uid, 1 << 30)
            vae_candidates.append((depth, uid))

    vae_candidates.sort()
    return vae_candidates[0][1] if vae_candidates else None


def _upstream_depths(
    workflow: VibeWorkflow,
    node_id: str,
) -> dict[str, int]:
    """BFS depth of each node from *node_id* (following edges in reverse)."""
    from collections import deque

    reverse: dict[str, set[str]] = {}
    for edge in workflow.edges:
        reverse.setdefault(edge.to_node, set()).add(edge.from_node)

    depths: dict[str, int] = {str(node_id): 0}
    queue: deque[str] = deque([str(node_id)])
    visited: set[str] = {str(node_id)}

    while queue:
        current = queue.popleft()
        current_depth = depths[current]
        for upstream_node in reverse.get(current, ()):
            if upstream_node not in visited:
                visited.add(upstream_node)
                depths[upstream_node] = current_depth + 1
                queue.append(upstream_node)

    return depths


# ---------------------------------------------------------------------------
# Subgraph builders
# ---------------------------------------------------------------------------


def _build_preview_subgraph(
    workflow: VibeWorkflow,
    target_node_id: str,
    preview: Any,  # PreviewInjection
    selected_ids: set[str],
    *,
    backend: str = "api",
) -> dict[str, Any]:
    """Build a subgraph API dict with a preview node injected."""
    nid = str(target_node_id)

    # Build temporary subgraph workflow
    sub_nodes: dict[str, VibeNode] = {}
    for node_id in selected_ids:
        if node_id in workflow.nodes:
            sub_nodes[node_id] = workflow.nodes[node_id]

    # Filter edges to only those where both endpoints are in selected_ids
    sub_edges: list[VibeEdge] = []
    for edge in workflow.edges:
        if edge.from_node in selected_ids and edge.to_node in selected_ids:
            sub_edges.append(edge)

    # Add preview node
    preview_id = f"{nid}_preview"
    preview_node = VibeNode(
        id=preview_id,
        class_type=preview.class_type,
        inputs=(
            {preview.output_input_slot: [nid, 0]}
            | (preview.extra_inputs or {})
        ),
    )
    sub_nodes[preview_id] = preview_node
    sub_edges.append(
        VibeEdge(
            from_node=nid,
            from_output="0",
            to_node=preview_id,
            to_input=preview.output_input_slot,
        )
    )

    # Build temporary VibeWorkflow and compile
    temp_wf = VibeWorkflow(
        id=f"{workflow.id}_eval_{nid}",
        source=workflow.source,
        nodes=sub_nodes,
        edges=sub_edges,
    )
    return temp_wf.compile(backend=backend)


def _build_latent_preview_subgraph(
    workflow: VibeWorkflow,
    target_node_id: str,
    vae_node_id: str,
    selected_ids: set[str],
    *,
    backend: str = "api",
) -> dict[str, Any]:
    """Build a subgraph with VAEDecode → PreviewImage for LATENT output."""
    nid = str(target_node_id)

    all_ids = selected_ids.copy()

    # Build temporary subgraph workflow
    sub_nodes: dict[str, VibeNode] = {}
    for node_id in all_ids:
        if node_id in workflow.nodes:
            sub_nodes[node_id] = workflow.nodes[node_id]

    # Filter edges
    sub_edges: list[VibeEdge] = []
    for edge in workflow.edges:
        if edge.from_node in all_ids and edge.to_node in all_ids:
            sub_edges.append(edge)

    # Add VAEDecode node
    decode_id = f"{nid}_vaedecode"
    decode_node = VibeNode(
        id=decode_id,
        class_type="VAEDecode",
        inputs={
            "samples": [nid, 0],
            "vae": [vae_node_id, 0],
        },
    )
    sub_nodes[decode_id] = decode_node
    sub_edges.append(
        VibeEdge(from_node=nid, from_output="0", to_node=decode_id, to_input="samples")
    )
    sub_edges.append(
        VibeEdge(from_node=vae_node_id, from_output="0", to_node=decode_id, to_input="vae")
    )

    # Add PreviewImage node after VAEDecode
    preview_id = f"{nid}_preview"
    preview_node = VibeNode(
        id=preview_id,
        class_type="PreviewImage",
        inputs={"images": [decode_id, 0]},
    )
    sub_nodes[preview_id] = preview_node
    sub_edges.append(
        VibeEdge(from_node=decode_id, from_output="0", to_node=preview_id, to_input="images")
    )

    # Build temporary VibeWorkflow and compile
    temp_wf = VibeWorkflow(
        id=f"{workflow.id}_eval_{nid}",
        source=workflow.source,
        nodes=sub_nodes,
        edges=sub_edges,
    )
    return temp_wf.compile(backend=backend)


def _latent_metadata_fallback(
    workflow: VibeWorkflow,
    target_node_id: str,
    target_node: VibeNode,
) -> dict[str, Any]:
    """Return metadata dict for LATENT without discoverable upstream VAE."""
    return {
        "type": "LATENT",
        "shape": _infer_latent_shape(workflow, target_node_id, target_node),
        "node_id": str(target_node_id),
        "class_type": target_node.class_type,
        "previewable": False,
        "plan_only": True,
    }


def _non_visualizable_metadata(
    target_node: VibeNode,
    node_id: str,
) -> dict[str, Any]:
    """Return metadata dict for non-visualizable outputs."""
    return {
        "type": target_node.class_type,
        "node_id": str(node_id),
        "class_type": target_node.class_type,
        "previewable": False,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _infer_latent_shape(
    workflow: VibeWorkflow,
    target_node_id: str,
    target_node: VibeNode,
) -> dict[str, Any] | None:
    """Try to infer latent shape from node inputs."""
    # Look for width/height inputs on the target node or its upstream
    shape: dict[str, Any] = {}
    for key in ("width", "height", "latent_width", "latent_height", "batch_size"):
        if key in target_node.inputs:
            shape[key] = target_node.inputs[key]

    if not shape:
        # Try upstream empty latent node
        from vibecomfy.analysis.graph import upstream

        for uid in upstream(workflow, target_node_id):
            if uid not in workflow.nodes:
                continue
            node = workflow.nodes[uid]
            if "empty" in node.class_type.lower() and "latent" in node.class_type.lower():
                for key in ("width", "height", "batch_size"):
                    if key in node.inputs:
                        shape[key] = node.inputs[key]
                break

    return shape if shape else None
