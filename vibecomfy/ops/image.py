from __future__ import annotations

from typing import Any

from vibecomfy.artifacts import Image
from vibecomfy.cli_loader import load_bundle
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
    bundle = load_bundle(result.template_id)
    workflow = bundle.workflow
    if workflow.inputs.get("prompt") is None:
        raise ValueError(f"image.t2i could not bind prompt input on template {result.template_id!r}")
    run_inputs: dict[str, object] = {"prompt": prompt}
    if seed is not None:
        if workflow.inputs.get("seed") is None:
            raise ValueError(f"image.t2i could not bind seed input on template {result.template_id!r}")
        run_inputs["seed"] = seed
    if steps is not None:
        if workflow.inputs.get("steps") is None:
            raise ValueError(f"image.t2i could not bind steps input on template {result.template_id!r}")
        run_inputs["steps"] = steps
    candidate = workflow.copy()
    for patch in result.explicit_patches:
        patch.apply(candidate)
    approved_bundle = load_bundle(candidate)
    _approved_record = approved_bundle.compile(run_inputs=run_inputs)
    raise RuntimeError(
        "image.t2i stopped: approved-record runtime transport is not available; "
        "use the T14 runtime boundary before executing this workflow"
    )


def __getattr__(name: str) -> Any:
    return namespace_getattr("image", name)


register_op("image", "t2i", _t2i)


__all__ = ["t2i"]
