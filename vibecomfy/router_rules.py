from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from vibecomfy.patches.ltx_lowvram import patch as ltx_lowvram
from vibecomfy.patches.resolution import resolution
from vibecomfy.patches.types import Patch


Predicate = Callable[[dict[str, Any]], bool]
PatchesFactory = Callable[[dict[str, Any]], tuple[Patch, ...]]


@dataclass(frozen=True, slots=True)
class Rule:
    verb_kind: str
    verb_name: str
    predicate: Predicate
    template_id: str
    patches_factory: PatchesFactory


_RULES: list[Rule] = []


def register_route(
    verb_kind: str,
    verb_name: str,
    predicate: Predicate,
    template_id: str,
    patches: tuple[Patch, ...] | list[Patch] | PatchesFactory = (),
) -> Rule:
    if callable(patches):
        patches_factory = patches
    else:
        explicit_patches = tuple(patches)
        patches_factory = lambda inputs: explicit_patches
    rule = Rule(verb_kind, verb_name, predicate, template_id, patches_factory)
    _RULES.append(rule)
    return rule


def rules() -> tuple[Rule, ...]:
    return tuple(_RULES)


def _model_is(*names: str | None) -> Predicate:
    return lambda inputs: inputs.get("model") in set(names)


register_route("image", "t2i", _model_is("z_image", None), "image/z_image")
register_route("image", "t2i", _model_is("flux2_klein_4b"), "image/flux2_klein_4b_t2i")
register_route("video", "t2v", _model_is("wan", None), "video/wan_t2v")
register_route(
    "video",
    "t2v",
    _model_is("ltx"),
    "video/ltx2_3_t2v",
    lambda inputs: (ltx_lowvram, resolution(384, 256, 9)),
)
register_route("video", "i2v", _model_is("wan", None), "video/wan_i2v")
register_route(
    "video",
    "i2v",
    _model_is("ltx"),
    "video/ltx2_3_i2v",
    lambda inputs: (ltx_lowvram, resolution(384, 256, 9)),
)


__all__ = ["Rule", "register_route", "rules"]
