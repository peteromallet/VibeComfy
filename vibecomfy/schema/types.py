from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class InputSpec:
    type: str | None = None
    required: bool = False
    default: Any = None
    choices: list[Any] | None = None
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class OutputSpec:
    type: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class NodeSchema:
    class_type: str
    pack: str | None
    inputs: dict[str, InputSpec]
    outputs: list[OutputSpec]
    # -- provenance fields (defaults so existing code works unchanged) ------
    source_provider: str = "unknown"
    source_path: str | None = None
    source_cache_path: str | None = None
    source_server_url: str | None = None
    source_package: str | None = None
    source_version: str | None = None
    source_hash: str | None = None
    confidence: float = 1.0
    conflicts: tuple[str, ...] = ()
    ignored_evidence: tuple[str, ...] = ()


class SchemaIndexError(ValueError):
    def __init__(self, path: Path, cause: Exception) -> None:
        super().__init__(f"{path} could not be read: {type(cause).__name__}: {cause}")
        self.path = path
        self.cause = cause


@runtime_checkable
class SchemaProvider(Protocol):
    def get_schema(self, class_type: str) -> NodeSchema | None: ...
