from __future__ import annotations

from typing import Any

from vibecomfy.artifacts import Image
from vibecomfy.cli_loader import load_bundle
from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op
from vibecomfy.origin import stamp_workflow_origin
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
    run_inputs = _public_run_inputs(
        workflow,
        result.template_id,
        {"prompt": prompt, "model": model, "width": width, "height": height, "steps": steps, "seed": seed},
        overrides,
        defaults={"width": 1024, "height": 1024},
    )
    candidate = workflow.copy()
    stamp_workflow_origin(candidate, "op", "ops/image.py:t2i")
    for patch in result.explicit_patches:
        patch.apply(candidate)
    approved_bundle = load_bundle(candidate)
    _approved_record = approved_bundle.compile(run_inputs=run_inputs)
    raise RuntimeError(
        "image.t2i stopped: approved-record runtime transport is not available; "
        "use the T14 runtime boundary before executing this workflow"
    )


def _public_run_inputs(
    workflow: Any,
    template_id: str,
    values: dict[str, object],
    overrides: dict[str, object],
    *,
    defaults: dict[str, object],
) -> dict[str, object]:
    public = workflow.inputs
    run_inputs: dict[str, object] = {}
    for name, value in values.items():
        if value is None:
            continue
        if name == "model" and public.get("model") is None:
            continue
        if name not in public:
            if name == "prompt" or name not in defaults or value != defaults[name]:
                raise ValueError(
                    f"image.t2i override {name!r} is not a public input on template {template_id!r}"
                )
            continue
        run_inputs[name] = value
    if "prompt" not in run_inputs:
        raise ValueError(f"image.t2i could not bind prompt input on template {template_id!r}")
    for name, value in overrides.items():
        if name not in public:
            raise ValueError(
                f"image.t2i override {name!r} is not a public input on template {template_id!r}"
            )
        run_inputs[name] = value
    return run_inputs


def __getattr__(name: str) -> Any:
    return namespace_getattr("image", name)


register_op("image", "t2i", _t2i)


__all__ = ["t2i"]
