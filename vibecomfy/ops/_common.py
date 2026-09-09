from __future__ import annotations

from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeInput, VibeOutput, VibeWorkflow


def set_prompt_preserving_registration(workflow: VibeWorkflow, prompt: str, patches: list[Patch]) -> None:
    prompt_target = workflow.inputs.get("prompt")
    workflow.set_prompt(prompt)
    for patch in patches:
        patch.apply(workflow)
    if prompt_target is not None:
        _restore_input(workflow, "prompt", prompt_target)
    workflow.set_prompt(prompt)


def bind_run_inputs(workflow: VibeWorkflow, run_inputs: dict[str, object]) -> None:
    """Apply validated public-input bindings onto a lazy op candidate."""
    for name, value in run_inputs.items():
        workflow.set_input(name, value)


def _restore_input(workflow: VibeWorkflow, name: str, target: VibeInput) -> None:
    if name in workflow.inputs or target.node_id not in workflow.nodes:
        return
    node = workflow.nodes[target.node_id]
    value = node.inputs.get(target.field, node.widgets.get(target.field, target.value))
    workflow.register_input(name, target.node_id, target.field, value)


def first_output(workflow: VibeWorkflow, output_type: str) -> VibeOutput:
    if not workflow.outputs:
        workflow.finalize_metadata()
    for output in workflow.outputs:
        if output.output_type == output_type:
            return output
    raise ValueError(f"Workflow has no {output_type} output")
