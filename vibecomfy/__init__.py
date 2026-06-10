from typing import Any

from .handles import Handle
from .ir import (
    ValidationIssue,
    ValidationReport,
    VibeEdge,
    VibeInput,
    VibeNode,
    VibeOutput,
    VibeWorkflow,
    WorkflowRequirements,
    WorkflowSource,
)
from . import blocks, patches, router
from .artifacts import Artifact, Audio, Image, Latent, Mask, Video
from .cli_loader import load_workflow_any
from .extras import ensure_plugins_loaded
from .ingest.loader import load_template, load_workflow_json
from .ops import image, video
from .registry.library import workflow_from_file, workflow_from_id, workflow_from_template
from .registry.ready import ready_template_ids, workflow_from_ready
# Runtime exports are loaded lazily via PEP 562 module __getattr__ to keep
# `import vibecomfy.testing` cheap: the dry-run runtime in
# `vibecomfy.testing.dry_run` must not transitively load
# `vibecomfy.runtime.client`, `vibecomfy.runtime.server`, or
# `vibecomfy.comfy_command` (verified by T5's import-cost subprocess test).
_RUNTIME_EXPORTS = {"run", "run_embedded", "run_embedded_sync", "run_sync"}


def __getattr__(name: str) -> Any:  # noqa: D401 — PEP 562 hook
    if name in _RUNTIME_EXPORTS:
        from .runtime.run import run, run_embedded, run_embedded_sync, run_sync

        globals().update(
            {
                "run": run,
                "run_embedded": run_embedded,
                "run_embedded_sync": run_embedded_sync,
                "run_sync": run_sync,
            }
        )
        return globals()[name]
    raise AttributeError(f"module 'vibecomfy' has no attribute {name!r}")

__all__ = [
    "Artifact",
    "Image",
    "Video",
    "Audio",
    "Latent",
    "Mask",
    "Handle",
    "VibeWorkflow",
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
    "load_workflow_json",
    "load_template",
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
