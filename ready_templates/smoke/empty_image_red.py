# vibecomfy: manual
"""Minimal ready-template smoke used to validate the Python template runner."""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


READY_METADATA = {
    "ready_template": "smoke/empty_image_red",
    "workflow_template": "smoke_empty_image_red",
    "capability": "runtime_smoke",
    "source_role": "manual_ready_python_template",
    "source_workflow": None,
    "coverage_tier": "smoke",
    "approach": "minimal Python ready template for cloud/runtime/artifact validation",
    "runtime_note": "No model assets; use corpus/model matrices for production model coverage.",
}

READY_REQUIREMENTS = {"models": [], "custom_nodes": []}


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )
    image = wf.node("EmptyImage", width=64, height=64, batch_size=1, color=16711680)
    wf.node("SaveImage", images=image.out(0), filename_prefix="vibecomfy_ready_smoke_red")
    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf
