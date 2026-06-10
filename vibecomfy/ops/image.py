from __future__ import annotations

from typing import Any

from vibecomfy.artifacts import Image
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.origin import stamp_workflow_origin
from vibecomfy.ops._common import first_output, set_prompt_preserving_registration
from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op
from vibecomfy.router import pick


def t2i(
    prompt: str,
    *,
    model: str | None = None,
    width: int = 1024,
    height: int = 1024,
    steps: int | None = None,
    seed: int | None = None,
    **overrides: Any,
) -> Image:
    return dispatch(
        "image",
        "t2i",
        prompt,
        model=model,
        width=width,
        height=height,
        steps=steps,
        seed=seed,
        **overrides,
    )


def _t2i(
    prompt: str,
    *,
    model: str | None = None,
    width: int = 1024,
    height: int = 1024,
    steps: int | None = None,
    seed: int | None = None,
    **overrides: Any,
) -> Image:
    result = pick("image", "t2i", model=model, width=width, height=height, steps=steps, seed=seed, **overrides)
    workflow = load_workflow_any(result.template_id)
    stamp_workflow_origin(workflow, "op", "ops/image.py:t2i")
    set_prompt_preserving_registration(workflow, prompt, result.explicit_patches)
    if seed is not None:
        workflow.set_seed(seed)
    if steps is not None:
        workflow.set_steps(steps)
    output = first_output(workflow, "SaveImage")
    return Image(
        workflow=workflow,
        node_id=output.node_id,
        output_slot=0,
        metadata={"template_id": result.template_id, "model": model},
    )


def __getattr__(name: str) -> Any:
    return namespace_getattr("image", name)


register_op("image", "t2i", _t2i)


__all__ = ["t2i"]
