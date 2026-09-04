from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY_EXPORTS = {
    "Artifact": ("vibecomfy.artifacts", "Artifact"),
    "Image": ("vibecomfy.artifacts", "Image"),
    "Video": ("vibecomfy.artifacts", "Video"),
    "Audio": ("vibecomfy.artifacts", "Audio"),
    "Latent": ("vibecomfy.artifacts", "Latent"),
    "Mask": ("vibecomfy.artifacts", "Mask"),
    "Handle": ("vibecomfy.handles", "Handle"),
    "VibeWorkflow": ("vibecomfy.workflow", "VibeWorkflow"),
    "RawWidgetPayload": ("vibecomfy.workflow", "RawWidgetPayload"),
    "VibeNode": ("vibecomfy.workflow", "VibeNode"),
    "VibeEdge": ("vibecomfy.workflow", "VibeEdge"),
    "VibeInput": ("vibecomfy.workflow", "VibeInput"),
    "VibeOutput": ("vibecomfy.workflow", "VibeOutput"),
    "WorkflowRequirements": ("vibecomfy.workflow", "WorkflowRequirements"),
    "WorkflowSource": ("vibecomfy.workflow", "WorkflowSource"),
    "ValidationIssue": ("vibecomfy.workflow", "ValidationIssue"),
    "ValidationReport": ("vibecomfy.workflow", "ValidationReport"),
    "workflow_from_file": ("vibecomfy.registry.library", "workflow_from_file"),
    "workflow_from_id": ("vibecomfy.registry.library", "workflow_from_id"),
    "workflow_from_template": ("vibecomfy.registry.library", "workflow_from_template"),
    "workflow_from_ready": ("vibecomfy.registry.ready", "workflow_from_ready"),
    "ready_template_ids": ("vibecomfy.registry.ready", "ready_template_ids"),
    "load_workflow_any": ("vibecomfy.cli_loader", "load_workflow_any"),
    "load_bundle": ("vibecomfy.cli_loader", "load_bundle"),
    "ApprovedProjectionRecord": ("vibecomfy.workflow_bundle", "ApprovedProjectionRecord"),
    "load_workflow_json": ("vibecomfy.ingest.loader", "load_workflow_json"),
    "load_template": ("vibecomfy.ingest.loader", "load_template"),
    "find_repo_root": ("vibecomfy.utils", "find_repo_root"),
    "ensure_plugins_loaded": ("vibecomfy.extras", "ensure_plugins_loaded"),
    "image": ("vibecomfy.ops", "image"),
    "video": ("vibecomfy.ops", "video"),
    "blocks": ("vibecomfy.blocks", None),
    "patches": ("vibecomfy.patches", None),
    "router": ("vibecomfy.router", None),
    "run": ("vibecomfy.runtime.run", "run"),
    "run_sync": ("vibecomfy.runtime.run", "run_sync"),
    "run_embedded": ("vibecomfy.runtime.run", "run_embedded"),
    "run_embedded_sync": ("vibecomfy.runtime.run", "run_embedded_sync"),
}

__all__ = [
    "Artifact",
    "Image",
    "Video",
    "Audio",
    "Latent",
    "Mask",
    "Handle",
    "VibeWorkflow",
    "RawWidgetPayload",
    "VibeNode",
    "VibeEdge",
    "VibeInput",
    "VibeOutput",
    "WorkflowRequirements",
    "WorkflowSource",
    "ValidationIssue",
    "ValidationReport",
    "workflow_from_file",
    "workflow_from_id",
    "workflow_from_template",
    "workflow_from_ready",
    "ready_template_ids",
    "load_workflow_any",
    "load_bundle",
    "ApprovedProjectionRecord",
    "load_workflow_json",
    "load_template",
    "find_repo_root",
    "ensure_plugins_loaded",
    "image",
    "video",
    "blocks",
    "patches",
    "router",
    "run",
    "run_sync",
    "run_embedded",
    "run_embedded_sync",
]


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'vibecomfy' has no attribute {name!r}") from exc

    module = import_module(module_name)
    value = module if attr_name is None else getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *__all__})
