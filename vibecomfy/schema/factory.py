from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Literal

from .local import LocalSchemaProvider
from .object_info import ObjectInfoFileSchemaProvider
from .runtime import RuntimeSchemaProvider


def get_schema_provider(
    prefer: Literal["runtime", "local", "auto", "object_info", "object_info_file"] = "auto",
    *,
    server_url: str | None = None,
    object_info_path: str | Path | None = None,
    object_info_cache_path: str | Path | None = None,
) -> RuntimeSchemaProvider | LocalSchemaProvider | ObjectInfoFileSchemaProvider:
    if prefer not in {"runtime", "local", "auto", "object_info", "object_info_file"}:
        raise ValueError(f"Unknown schema provider preference: {prefer}")
    explicit_object_info_path = object_info_path or object_info_cache_path
    if explicit_object_info_path is not None:
        return schema_provider_from_object_info_file(explicit_object_info_path)
    if prefer in {"object_info", "object_info_file"}:
        raise ValueError("object_info schema provider requires object_info_path")
    if prefer == "runtime":
        return RuntimeSchemaProvider(server_url=server_url)
    if prefer == "local":
        return LocalSchemaProvider()
    if server_url:
        return RuntimeSchemaProvider(server_url=server_url)
    if Path("node_index.json").exists():
        return LocalSchemaProvider()
    if _which("comfyui"):
        return RuntimeSchemaProvider(server_url=server_url)
    return LocalSchemaProvider()


def schema_provider_from_object_info_file(path: str | Path) -> ObjectInfoFileSchemaProvider:
    return ObjectInfoFileSchemaProvider(path)


def _which(command: str) -> str | None:
    provider_module = sys.modules.get("vibecomfy.schema.provider")
    provider_shutil = getattr(provider_module, "shutil", None) if provider_module is not None else None
    provider_which = getattr(provider_shutil, "which", None)
    if callable(provider_which):
        return provider_which(command)
    return shutil.which(command)
