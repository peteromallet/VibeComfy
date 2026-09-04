from __future__ import annotations

from typing import Any

import httpx


def _format_response_body(body: str, *, max_chars: int = 20000) -> str:
    body = body.strip()
    if len(body) <= max_chars:
        return body
    head_chars = 2000
    tail_chars = max_chars - head_chars - 80
    return (
        body[:head_chars]
        + f"\n... response body truncated; omitted {len(body) - head_chars - tail_chars} chars ...\n"
        + body[-tail_chars:]
    )


def _raise_for_status_with_body(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = _format_response_body(response.text)
        if body:
            raise RuntimeError(f"{exc}; response body: {body}") from exc
        raise


class ComfyClient:
    def __init__(self, server_url: str) -> None:
        self.server_url = server_url.rstrip("/")

    async def ready(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.server_url}/system_stats")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def _post_prompt(self, prompt: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.server_url}/prompt", json={"prompt": prompt})
            _raise_for_status_with_body(response)
            return response.json()

    async def free(self, *, unload_models: bool = True, free_memory: bool = True) -> dict[str, Any]:
        """Queue an async Comfy free request; effects apply at a prompt boundary."""
        payload = {"unload_models": unload_models, "free_memory": free_memory}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.server_url}/api/free", json=payload)
            _raise_for_status_with_body(response)
            if not getattr(response, "content", b""):
                return {}
            return response.json()

    async def object_info(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.server_url}/object_info")
            _raise_for_status_with_body(response)
            return response.json()

    async def history(self, prompt_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.server_url}/history/{prompt_id}")
            _raise_for_status_with_body(response)
            return response.json()
