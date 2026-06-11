from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow


def ensure_resize_image_mask_schema(
    workflow: VibeWorkflow,
    node_ids: tuple[str, ...] | None = None,
) -> VibeWorkflow:
    """Populate dynamic resize inputs required by newer KJ/LTX runtimes.

    Some converted LTX workflows came from older UI graphs that used
    ImageResizeKJv2-style names such as ``width``/``height``/``crop_position``.
    Recent runtimes validate the same node family as ResizeImageMaskNode and
    require dynamic input names such as ``resize_type.width`` and
    ``resize_type.crop``. Keep both shapes so templates remain editable and
    runtime-valid across node-pack versions.
    """

    selected = {str(node_id) for node_id in node_ids} if node_ids else None
    for node_id, node in workflow.nodes.items():
        if selected is not None and node_id not in selected:
            continue
        if node.class_type not in {"ImageResizeKJv2", "ResizeImageMaskNode"}:
            continue

        inputs = node.inputs
        resize_type = inputs.get("resize_type") or inputs.get("widget_0") or "scale dimensions"
        inputs.setdefault("resize_type", resize_type)
        inputs.setdefault("scale_method", inputs.get("scale_method") or inputs.get("upscale_method") or inputs.get("widget_2") or "lanczos")
        inputs.setdefault("resize_type.crop", inputs.get("crop") or inputs.get("crop_position") or inputs.get("widget_3") or "center")

        if "width" in inputs:
            inputs.setdefault("resize_type.width", inputs["width"])
        if "height" in inputs:
            inputs.setdefault("resize_type.height", inputs["height"])
        if "widget_1" in inputs:
            if "dimension" in str(resize_type):
                inputs.setdefault("resize_type.width", inputs["widget_1"])
            elif "shorter" in str(resize_type):
                inputs.setdefault("resize_type.shorter_size", inputs["widget_1"])
            elif "longer" in str(resize_type):
                inputs.setdefault("resize_type.longer_size", inputs["widget_1"])

    _duplicate_resize_edges(workflow, "width", "resize_type.width", selected)
    _duplicate_resize_edges(workflow, "height", "resize_type.height", selected)
    return workflow


def _duplicate_resize_edges(
    workflow: VibeWorkflow,
    source_input: str,
    target_input: str,
    selected: set[str] | None,
) -> None:
    existing = {(edge.to_node, edge.to_input) for edge in workflow.edges}
    for edge in list(workflow.edges):
        if edge.to_input != source_input:
            continue
        if selected is not None and edge.to_node not in selected:
            continue
        node = workflow.nodes.get(edge.to_node)
        if node is None or node.class_type not in {"ImageResizeKJv2", "ResizeImageMaskNode"}:
            continue
        key = (edge.to_node, target_input)
        if key not in existing:
            workflow.connect(f"{edge.from_node}.{edge.from_output}", f"{edge.to_node}.{target_input}")
            existing.add(key)
