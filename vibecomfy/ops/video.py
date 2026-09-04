from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Union

from vibecomfy.artifacts import Artifact, Image, Video
from vibecomfy.cli_loader import load_bundle
from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op
from vibecomfy.router import pick

I2VImage = Union[Image, str, Path, bytes]


def t2v(
    prompt: str,
    *,
    model: str | None = None,
    width: int | None = None,
    height: int | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    return dispatch(
        "video",
        "t2v",
        prompt,
        model=model,
        width=width,
        height=height,
        length=length,
        fps=fps,
        seed=seed,
        **overrides,
    )


def _t2v(
    prompt: str,
    *,
    model: str | None = None,
    width: int | None = None,
    height: int | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    result = pick("video", "t2v", model=model, width=width, height=height, length=length, fps=fps, seed=seed, **overrides)
    bundle = load_bundle(result.template_id)
    workflow = bundle.workflow
    if workflow.inputs.get("prompt") is None:
        raise ValueError(f"video.t2v could not bind prompt input on template {result.template_id!r}")
    run_inputs: dict[str, object] = {"prompt": prompt}
    if seed is not None:
        if workflow.inputs.get("seed") is None:
            raise ValueError(f"video.t2v could not bind seed input on template {result.template_id!r}")
        run_inputs["seed"] = seed
    candidate = workflow.copy()
    for patch in result.explicit_patches:
        patch.apply(candidate)
    approved_bundle = load_bundle(candidate)
    _approved_record = approved_bundle.compile(run_inputs=run_inputs)
    raise RuntimeError(
        "video.t2v stopped: approved-record runtime transport is not available; "
        "use the T14 runtime boundary before executing this workflow"
    )


def i2v(
    image: Any,
    prompt: str,
    *,
    model: str | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    return dispatch(
        "video",
        "i2v",
        image,
        prompt,
        model=model,
        length=length,
        fps=fps,
        seed=seed,
        **overrides,
    )


def _i2v(
    image: Any,
    prompt: str,
    *,
    model: str | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    image_path = _resolve_i2v_image_path(image)
    result = pick("video", "i2v", model=model, image=image_path, length=length, fps=fps, seed=seed, **overrides)
    bundle = load_bundle(result.template_id)
    workflow = bundle.workflow
    if workflow.inputs.get("prompt") is None:
        raise ValueError(f"video.i2v could not bind prompt input on template {result.template_id!r}")
    if workflow.inputs.get("image") is None:
        raise ValueError(f"video.i2v could not bind image input on template {result.template_id!r}")
    run_inputs: dict[str, object] = {"prompt": prompt, "image": image_path}
    if seed is not None:
        if workflow.inputs.get("seed") is None:
            raise ValueError(f"video.i2v could not bind seed input on template {result.template_id!r}")
        run_inputs["seed"] = seed
    candidate = workflow.copy()
    for patch in result.explicit_patches:
        patch.apply(candidate)
    approved_bundle = load_bundle(candidate)
    _approved_record = approved_bundle.compile(run_inputs=run_inputs)
    raise RuntimeError(
        "video.i2v stopped: approved-record runtime transport is not available; "
        "use the T14 runtime boundary before executing this workflow"
    )


def _resolve_i2v_image_path(image: Any) -> str:
    if isinstance(image, Artifact):
        raise ValueError(
            "video.i2v requires a filesystem path for image input. "
            "Run the image workflow first and pass result.outputs[0]."
        )
    if isinstance(image, (str, os.PathLike)):
        value = _coerce_path(os.fspath(image))
    else:
        value = _path_attribute(image)
    if not value:
        raise ValueError("video.i2v requires a non-empty image path.")
    return value


def _path_attribute(value: Any) -> str | None:
    for attr in ("path", "file_path", "filepath", "filename"):
        candidate = getattr(value, attr, None)
        if isinstance(candidate, (str, os.PathLike)):
            return _coerce_path(os.fspath(candidate))
    return None


def _coerce_path(value: str | bytes) -> str:
    return os.fsdecode(value) if isinstance(value, bytes) else value


def __getattr__(name: str) -> Any:
    return namespace_getattr("video", name)


register_op("video", "t2v", _t2v)
register_op("video", "i2v", _i2v)


__all__ = ["i2v", "t2v"]
