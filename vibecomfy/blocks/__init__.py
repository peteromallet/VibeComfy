from __future__ import annotations

from dataclasses import dataclass, field
from inspect import signature, stack
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol, TypeVar
import warnings

from vibecomfy.handles import Handle
from vibecomfy.workflow import VibeWorkflow

_RAW_HANDLE_WARNING_SITES: set[tuple[str, int]] = set()


@dataclass(frozen=True, init=False)
class Handles:
    values: Mapping[str, Handle] = field(default_factory=dict)

    def __init__(self, values: Mapping[str, Handle | str] | None = None, **kwargs: Handle | str) -> None:
        merged: dict[str, Handle] = {}
        caller = stack()[1]
        site = (caller.filename, caller.lineno)
        if values is not None:
            for key, value in values.items():
                merged[key] = _coerce_handle_value(key, value, site)
        for key, value in kwargs.items():
            merged[key] = _coerce_handle_value(key, value, site)
        object.__setattr__(self, "values", MappingProxyType(merged))

    def __getitem__(self, key: str) -> Handle:
        return self.values[key]

    def __getattr__(self, key: str) -> Handle:
        try:
            return self.values[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def get(self, key: str, default: Handle | None = None) -> Handle | None:
        return self.values.get(key, default)

    def as_dict(self) -> dict[str, Handle]:
        return dict(self.values)


def _coerce_handle_value(name: str, value: Handle | str, warning_site: tuple[str, int]) -> Handle:
    if isinstance(value, Handle):
        return value
    if not isinstance(value, str):
        raise TypeError(f"Handles values must be Handle instances, got {type(value).__name__} for {name!r}")
    _warn_raw_handle_string_once(warning_site)
    if "." in value:
        node_id, output_slot = value.split(".", 1)
    else:
        node_id, output_slot = value, 0
    return Handle(node_id=node_id, output_slot=output_slot, name=name)


def _warn_raw_handle_string_once(site: tuple[str, int]) -> None:
    if site in _RAW_HANDLE_WARNING_SITES:
        return
    _RAW_HANDLE_WARNING_SITES.add(site)
    warnings.warn(
        "Passing raw string refs to Handles is deprecated; pass vibecomfy.Handle instances instead.",
        DeprecationWarning,
        stacklevel=4,
    )


class Block(Protocol):
    def __call__(self, workflow: VibeWorkflow, **kwargs: Any) -> Handles:
        """Mutate the workflow as needed (any VibeWorkflow method) and return handles for downstream wiring."""


@dataclass(frozen=True)
class BlockSpec:
    name: str
    module: str
    qualname: str
    signature: str


BlockFn = TypeVar("BlockFn", bound=Callable[..., Handles])

_BLOCK_REGISTRY: dict[str, Block] = {}


def block(fn: BlockFn) -> BlockFn:
    sig = signature(fn)
    first_param = next(iter(sig.parameters.values()), None)
    if first_param is None or first_param.name != "workflow":
        raise TypeError(f"{fn.__module__}.{fn.__qualname__} must accept workflow as its first parameter")
    name = f"{fn.__module__}.{fn.__name__}"
    spec = BlockSpec(
        name=name,
        module=fn.__module__,
        qualname=fn.__qualname__,
        signature=str(sig),
    )
    setattr(fn, "__vibecomfy_block__", spec)
    _BLOCK_REGISTRY[name] = fn
    return fn


def block_spec(fn: Callable[..., Any]) -> BlockSpec | None:
    spec = getattr(fn, "__vibecomfy_block__", None)
    return spec if isinstance(spec, BlockSpec) else None


def registered_blocks() -> Mapping[str, Block]:
    return MappingProxyType(dict(_BLOCK_REGISTRY))


__all__ = ["Block", "BlockSpec", "Handle", "Handles", "block", "block_spec", "registered_blocks"]
