from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from vibecomfy.runtime.client import ComfyClient
from vibecomfy.runtime.server import comfy_server

from .cache import load_object_info_cache, object_info_cache_path, runtime_fingerprint, write_object_info_cache
from .object_info import schemas_from_object_info
from .types import NodeSchema


class RuntimeSchemaProvider:
    def __init__(
        self,
        *,
        server_url: str | None = None,
        cache_dir: str | Path = "out/cache",
        log_path: str | Path | None = None,
    ) -> None:
        self.server_url = server_url
        self.cache_path = object_info_cache_path(server_url=server_url, cache_dir=cache_dir)
        self.log_path = log_path
        self._object_info: dict[str, Any] | None = None
        self._schemas: dict[str, NodeSchema] | None = None

    def get(self, class_type: str) -> NodeSchema | None:
        return self.schemas().get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        if self._schemas is None:
            self._schemas = schemas_from_object_info(self.object_info())
        return self._schemas

    def object_info(self) -> dict[str, Any]:
        if self._object_info is None:
            cached = load_object_info_cache(self.cache_path)
            if cached is not None:
                self._object_info = cached
            else:
                self._object_info = run_async(self.object_info_async())
        return self._object_info

    async def object_info_async(self) -> dict[str, Any]:
        cached = load_object_info_cache(self.cache_path)
        if cached is not None:
            return cached
        server_factory = _provider_compat_attr("comfy_server", comfy_server)
        client_cls = _provider_compat_attr("ComfyClient", ComfyClient)
        async with server_factory(server_url=self.server_url, log_path=self.log_path) as active_url:
            data = await client_cls(active_url).object_info()
        write_object_info_cache(
            self.cache_path,
            data,
            runtime_fingerprint=runtime_fingerprint(self.server_url),
            server_url=active_url,
        )
        return data


def run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    coro.close()
    raise RuntimeError("RuntimeSchemaProvider synchronous access cannot run inside an active event loop; use object_info_async().")


def _provider_compat_attr(name: str, fallback):
    provider_module = sys.modules.get("vibecomfy.schema.provider")
    if provider_module is not None and hasattr(provider_module, name):
        return getattr(provider_module, name)
    return fallback
