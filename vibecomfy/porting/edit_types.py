from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_jsonish(v) for v in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw_jsonish(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw_jsonish(v) for v in value]
    return value


@dataclass(frozen=True)
class FieldChange:
    uid: str
    field_path: str
    old: Any = None
    new: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "old", _freeze_jsonish(self.old))
        object.__setattr__(self, "new", _freeze_jsonish(self.new))

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "field_path": self.field_path,
            "old": _thaw_jsonish(self.old),
            "new": _thaw_jsonish(self.new),
        }


__all__ = ["FieldChange"]
