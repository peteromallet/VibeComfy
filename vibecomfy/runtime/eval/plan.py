"""Descriptive eval planning; no compiler and no queue authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.analysis.graph import upstream
from vibecomfy.errors import RuntimeNodeError
from vibecomfy.workflow_bundle import WorkflowBundle, WorkflowBundleError

from .core import _detect_output_type, _resolve_upstream_vae_handle
from .preview_types import PREVIEW_MAP, VIDEO_FALLBACK


SAVE_OR_PREVIEW_CLASSES = {
    "PreviewImage", "PreviewAudio", "PreviewVideo", "PreviewMask", "SaveImage",
    "SaveAnimatedWEBP", "SaveAudio", "SaveVideo", "VHS_VideoCombine",
}


@dataclass(frozen=True)
class EvalNodePlan:
    workflow: str
    node_id: str
    dry_run: bool
    execution_mode: str
    queueable: bool
    lookup: dict[str, Any]
    retained_node_ids: list[str]
    dropped_node_ids: list[str]
    skipped_terminal_node_ids: list[str]
    dependencies_run: list[str]
    outputs: dict[str, dict[str, Any]]
    preview_injections: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    truncated_api: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow, "node_id": self.node_id, "dry_run": self.dry_run,
            "execution_mode": self.execution_mode, "queueable": self.queueable,
            "lookup": self.lookup, "retained_node_ids": self.retained_node_ids,
            "dropped_node_ids": self.dropped_node_ids,
            "skipped_terminal_node_ids": self.skipped_terminal_node_ids,
            "dependencies_run": self.dependencies_run, "outputs": self.outputs,
            "preview_injections": list(self.preview_injections),
            "warnings": list(self.warnings), "truncated_api": {},
        }


def plan_eval_node(bundle: WorkflowBundle, node_id: str, *, dry_run: bool = True) -> EvalNodePlan:
    """Describe a root node and its preview classification without compiling."""
    if not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError(
            "eval planning requires a WorkflowBundle; load the source with "
            "load_bundle(...) before calling plan_eval_node"
        )
    workflow = bundle.workflow
    node_key = str(node_id)
    mode = "dry_run" if dry_run else "planned_only"
    warnings: list[dict[str, Any]] = []
    if "#" in node_key or "/" in node_key:
        warnings.append({"code": "qualified_node_id", "message": "root node ids only are supported"})
        return _empty_plan(workflow.id, node_key, dry_run, mode, warnings)
    if node_key not in workflow.nodes:
        warnings.append({"code": "unknown_node_id", "message": f"Node {node_key} is not present in the root workflow."})
        return _empty_plan(workflow.id, node_key, dry_run, mode, warnings)

    node = workflow.nodes[node_key]
    retained = upstream(workflow, node_key) | {node_key}
    dropped = set(workflow.nodes) - retained
    output_type = _detect_output_type(workflow, node)
    vae_handle = None
    vae_error: RuntimeNodeError | None = None
    if output_type == "LATENT":
        try:
            vae_handle = _resolve_upstream_vae_handle(workflow, retained - {node_key})
        except RuntimeNodeError as exc:
            vae_error = exc
    has_vae = vae_handle is not None
    preview = PREVIEW_MAP.get(output_type) or (VIDEO_FALLBACK if output_type == "VIDEO" else None)
    queueable = preview is not None or (output_type == "LATENT" and has_vae)
    output = {
        "output_0": {
            "slot": 0, "comfy_type": output_type, "previewable": queueable,
            **({"reason": "upstream VAE required"} if output_type == "LATENT" and not has_vae else {}),
        }
    }
    injections: list[dict[str, Any]] = []
    if preview is not None:
        injections.append({"slot": "output_0", "slot_index": 0, "comfy_type": output_type,
                           "wrapped_via": preview.class_type, "source": [node_key, 0]})
    elif output_type == "LATENT" and has_vae:
        injections.append({"slot": "output_0", "slot_index": 0, "comfy_type": output_type,
                           "wrapped_via": "VAEDecode+PreviewImage", "source": [node_key, 0],
                           "vae_source": [vae_handle.node_id, vae_handle.output_slot]})
    if not queueable:
        code = "vae_source_ambiguous" if vae_error is not None and "vae_source_ambiguous" in str(vae_error) else "vae_handle_unresolved" if output_type == "LATENT" else "non_visualizable"
        warnings.append({"code": code, "message": str(vae_error) if vae_error is not None else f"Node {node_key} has no queueable preview output."})
    dependencies = sorted(retained - {node_key}, key=_node_sort_key)
    return EvalNodePlan(
        workflow.id, node_key, dry_run, mode, queueable,
        {"found": True, "node_id": node_key, "class_type": node.class_type},
        sorted(retained, key=_node_sort_key), sorted(dropped, key=_node_sort_key),
        sorted((set(dropped) & {n for n, item in workflow.nodes.items() if item.class_type in SAVE_OR_PREVIEW_CLASSES}), key=_node_sort_key),
        dependencies, output, preview_injections=injections, warnings=warnings, truncated_api={},
    )


def _empty_plan(workflow_id: str, node_id: str, dry_run: bool, mode: str, warnings: list[dict[str, Any]]) -> EvalNodePlan:
    return EvalNodePlan(workflow_id, node_id, dry_run, mode, False, {"found": False, "node_id": node_id}, [], [], [], [], {}, warnings=warnings, truncated_api={})


def _node_sort_key(node_id: str) -> tuple[int, int | str]:
    return (0, int(node_id)) if str(node_id).isdigit() else (1, str(node_id))


__all__ = ["EvalNodePlan", "plan_eval_node"]
