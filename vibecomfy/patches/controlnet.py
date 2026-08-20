from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow


CUSTOM_NODE_PACK = "ComfyUI-ControlNet"
_PATCH_MARKER_KEY = "vibecomfy_patch"
_PATCH_MARKER_NAME = "controlnet"


@dataclass(frozen=True)
class ControlNetSettings:
    control_net_name: str = "depth.safetensors"
    image_node_id: str | None = None
    strength: float = 1.0


@dataclass(frozen=True)
class _ControlNetSplice:
    sampler_id: str
    loader_id: str
    positive_id: str
    negative_id: str | None = None


def _find_ksampler_id(workflow: VibeWorkflow) -> str | None:
    for node_id, node in workflow.nodes.items():
        if node.class_type == "KSampler":
            return node_id
    return None


def _find_edge_into(
    workflow: VibeWorkflow,
    node_id: str,
    input_name: str,
) -> VibeEdge | None:
    for edge in workflow.edges:
        if str(edge.to_node) == str(node_id) and edge.to_input == input_name:
            return edge
    return None


def _is_node_class(workflow: VibeWorkflow, node_id: str, class_type: str) -> bool:
    node = workflow.nodes.get(str(node_id))
    return node is not None and node.class_type == class_type


def _marked_for(node: VibeNode, *, role: str, sampler_id: str) -> bool:
    marker = node.metadata.get(_PATCH_MARKER_KEY)
    return (
        isinstance(marker, dict)
        and marker.get("name") == _PATCH_MARKER_NAME
        and marker.get("role") == role
        and str(marker.get("sampler_id")) == str(sampler_id)
    )


def _mark_node(node: VibeNode, *, role: str, sampler_id: str) -> None:
    node.metadata[_PATCH_MARKER_KEY] = {
        "name": _PATCH_MARKER_NAME,
        "role": role,
        "sampler_id": str(sampler_id),
    }


def _find_marked_node_id(
    workflow: VibeWorkflow,
    *,
    role: str,
    sampler_id: str,
) -> str | None:
    for node_id, node in workflow.nodes.items():
        if _marked_for(node, role=role, sampler_id=sampler_id):
            return str(node_id)
    return None


def _find_existing_splice(
    workflow: VibeWorkflow,
    sampler_id: str,
) -> _ControlNetSplice | None:
    """Recognize this patch after round trips, including pre-marker graphs.

    Markers provide an unambiguous fast path.  The structural fallback is
    deliberately strict: the sampler must be fed by a ControlNet apply node,
    and that node must itself be fed by a ControlNet loader plus an original
    positive-conditioning edge.  This prevents an ordinary node-type match
    elsewhere in the workflow from suppressing the patch.
    """
    sampler_pos = _find_edge_into(workflow, sampler_id, "positive")
    if sampler_pos is None:
        return None

    marked_positive = _find_marked_node_id(
        workflow, role="positive", sampler_id=sampler_id
    )
    positive_id = marked_positive or str(sampler_pos.from_node)
    if str(sampler_pos.from_node) != positive_id or not _is_node_class(
        workflow, positive_id, "ControlNetApplyAdvanced"
    ):
        return None
    if _find_edge_into(workflow, positive_id, "positive") is None:
        return None

    control_edge = _find_edge_into(workflow, positive_id, "control_net")
    if control_edge is None:
        return None
    loader_id = str(control_edge.from_node)
    marked_loader = _find_marked_node_id(
        workflow, role="loader", sampler_id=sampler_id
    )
    if marked_loader is not None and marked_loader != loader_id:
        return None
    if not _is_node_class(workflow, loader_id, "ControlNetLoader"):
        return None

    negative_id: str | None = None
    sampler_neg = _find_edge_into(workflow, sampler_id, "negative")
    if sampler_neg is not None:
        candidate_id = str(sampler_neg.from_node)
        candidate_control = _find_edge_into(workflow, candidate_id, "control_net")
        if (
            _is_node_class(workflow, candidate_id, "ControlNetApplyAdvanced")
            and _find_edge_into(workflow, candidate_id, "negative") is not None
            and candidate_control is not None
            and str(candidate_control.from_node) == loader_id
        ):
            negative_id = candidate_id

    return _ControlNetSplice(
        sampler_id=str(sampler_id),
        loader_id=loader_id,
        positive_id=positive_id,
        negative_id=negative_id,
    )


def applies_to(workflow: VibeWorkflow) -> bool:
    sampler_id = _find_ksampler_id(workflow)
    if sampler_id is None:
        return False
    return (
        _find_edge_into(workflow, sampler_id, "positive") is not None
        and _find_existing_splice(workflow, sampler_id) is None
    )


def apply(workflow: VibeWorkflow) -> VibeWorkflow:
    return _apply_with_settings(workflow, ControlNetSettings())


def _apply_with_settings(workflow: VibeWorkflow, settings: ControlNetSettings) -> VibeWorkflow:
    sampler_id = _find_ksampler_id(workflow)
    if sampler_id is None:
        return workflow

    pos_edge = _find_edge_into(workflow, sampler_id, "positive")
    neg_edge = _find_edge_into(workflow, sampler_id, "negative")
    if pos_edge is None:
        return workflow

    existing = _find_existing_splice(workflow, sampler_id)
    if existing is not None:
        _configure_existing_splice(workflow, existing, settings)
        ensure_custom_nodes(workflow, (CUSTOM_NODE_PACK,))
        return workflow

    # Add the new ControlNet support nodes.
    loader = workflow.add_node("ControlNetLoader")
    loader.widgets["control_net_name"] = settings.control_net_name
    _mark_node(loader, role="loader", sampler_id=sampler_id)

    apply_pos = workflow.add_node("ControlNetApplyAdvanced")
    _configure_apply_node(apply_pos, settings)
    _mark_node(apply_pos, role="positive", sampler_id=sampler_id)

    # Wire ControlNetLoader -> ControlNetApplyAdvanced.control_net.
    workflow.connect(f"{loader.id}.0", f"{apply_pos.id}.control_net")

    # Splice on the positive chain:
    #   original_pos_source -> apply_pos.positive
    #   apply_pos.0         -> sampler.positive
    original_pos_from = f"{pos_edge.from_node}.{pos_edge.from_output}"
    workflow.connect(original_pos_from, f"{apply_pos.id}.positive")
    workflow.replace_edge(f"{sampler_id}.positive", f"{apply_pos.id}.0")

    # Mirror the splice on the negative chain when present.
    if neg_edge is not None:
        apply_neg = workflow.add_node("ControlNetApplyAdvanced")
        _configure_apply_node(apply_neg, settings)
        _mark_node(apply_neg, role="negative", sampler_id=sampler_id)
        workflow.connect(f"{loader.id}.0", f"{apply_neg.id}.control_net")
        original_neg_from = f"{neg_edge.from_node}.{neg_edge.from_output}"
        workflow.connect(original_neg_from, f"{apply_neg.id}.negative")
        workflow.replace_edge(f"{sampler_id}.negative", f"{apply_neg.id}.0")
        if settings.image_node_id is not None:
            workflow.connect(f"{settings.image_node_id}.0", f"{apply_neg.id}.image")

    if settings.image_node_id is not None:
        workflow.connect(f"{settings.image_node_id}.0", f"{apply_pos.id}.image")

    ensure_custom_nodes(workflow, (CUSTOM_NODE_PACK,))

    return workflow


def _configure_apply_node(node: VibeNode, settings: ControlNetSettings) -> None:
    node.widgets.update(
        {
            "strength": settings.strength,
            "start_percent": 0.0,
            "end_percent": 1.0,
        }
    )


def _upsert_edge(
    workflow: VibeWorkflow,
    *,
    from_node: str,
    from_output: str,
    to_node: str,
    to_input: str,
) -> None:
    current = _find_edge_into(workflow, to_node, to_input)
    if (
        current is not None
        and str(current.from_node) == str(from_node)
        and str(current.from_output) == str(from_output)
    ):
        return
    workflow.replace_edge(
        f"{to_node}.{to_input}",
        f"{from_node}.{from_output}",
    )


def _configure_existing_splice(
    workflow: VibeWorkflow,
    splice: _ControlNetSplice,
    settings: ControlNetSettings,
) -> None:
    loader = workflow.nodes[splice.loader_id]
    positive = workflow.nodes[splice.positive_id]
    loader.widgets["control_net_name"] = settings.control_net_name
    _configure_apply_node(positive, settings)
    _mark_node(loader, role="loader", sampler_id=splice.sampler_id)
    _mark_node(positive, role="positive", sampler_id=splice.sampler_id)

    negative_id = splice.negative_id
    sampler_neg = _find_edge_into(workflow, splice.sampler_id, "negative")
    if negative_id is None and sampler_neg is not None:
        negative = workflow.add_node("ControlNetApplyAdvanced")
        negative_id = negative.id
        _configure_apply_node(negative, settings)
        _mark_node(negative, role="negative", sampler_id=splice.sampler_id)
        workflow.connect(f"{splice.loader_id}.0", f"{negative_id}.control_net")
        workflow.connect(
            f"{sampler_neg.from_node}.{sampler_neg.from_output}",
            f"{negative_id}.negative",
        )
        workflow.replace_edge(
            f"{splice.sampler_id}.negative",
            f"{negative_id}.0",
        )
    elif negative_id is not None:
        negative = workflow.nodes[negative_id]
        _configure_apply_node(negative, settings)
        _mark_node(negative, role="negative", sampler_id=splice.sampler_id)

    if settings.image_node_id is not None:
        _upsert_edge(
            workflow,
            from_node=settings.image_node_id,
            from_output="0",
            to_node=splice.positive_id,
            to_input="image",
        )
        if negative_id is not None:
            _upsert_edge(
                workflow,
                from_node=settings.image_node_id,
                from_output="0",
                to_node=negative_id,
                to_input="image",
            )


def rationale(workflow: VibeWorkflow) -> str:
    return "KSampler with conditioning detected; ControlNet can splice extra conditioning into the positive/negative chain."


def controlnet_patch(
    *,
    control_net_name: str = "depth.safetensors",
    image_node_id: str | None = None,
    strength: float = 1.0,
) -> Patch:
    settings = ControlNetSettings(
        control_net_name=control_net_name,
        image_node_id=image_node_id,
        strength=strength,
    )

    def configured_apply(workflow: VibeWorkflow) -> VibeWorkflow:
        return _apply_with_settings(workflow, settings)

    suffix = control_net_name
    if image_node_id is not None:
        suffix = f"{suffix}:{image_node_id}"
    if strength != 1.0:
        suffix = f"{suffix}:{strength:g}"
    return Patch(f"controlnet:{suffix}", applies_to, configured_apply, rationale)


patch = Patch("controlnet", applies_to, apply, rationale)


__all__ = ["CUSTOM_NODE_PACK", "ControlNetSettings", "applies_to", "apply", "controlnet_patch", "patch", "rationale"]
