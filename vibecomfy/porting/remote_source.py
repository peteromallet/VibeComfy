"""Fetch one remote workflow source for the canonical importer."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


_MAX_SOURCE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RemoteSource:
    source_bytes: bytes
    url: str

    @property
    def provenance(self) -> dict[str, str]:
        digest = "sha256:" + hashlib.sha256(self.source_bytes).hexdigest()
        return {
            "origin_kind": "url",
            "origin_uri": self.url,
            "origin_pin": f"snapshot:{digest}",
            "source_digest": digest,
        }


def is_http_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def fetch_remote_source(url: str, *, timeout: float = 20.0) -> RemoteSource:
    if not is_http_url(url):
        raise ValueError("source URL must use http:// or https://")
    request = Request(url, headers={"User-Agent": "VibeComfy workflow importer"})
    deadline = time.monotonic() + timeout
    with urlopen(request, timeout=min(timeout, 1.0)) as response:  # noqa: S310 - explicit public URL import boundary
        resolved_url = response.geturl() if hasattr(response, "geturl") else url
        if not is_http_url(resolved_url):
            raise ValueError("remote workflow redirect must remain on http:// or https://")
        chunks: list[bytes] = []
        total = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("remote workflow download exceeded its time limit")
            chunk = response.read(min(1024 * 1024, _MAX_SOURCE_BYTES - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_SOURCE_BYTES:
                raise ValueError("remote workflow exceeds the 20 MiB import limit")
            chunks.append(chunk)
    return RemoteSource(source_bytes=b"".join(chunks), url=url)


__all__ = ["RemoteSource", "fetch_remote_source", "is_http_url"]
