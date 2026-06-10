from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlencode

import httpx

API_BASE_URL = "https://api.comfy.org"
DEFAULT_CACHE_ROOT = Path(os.environ.get("VIBECOMFY_REGISTRY_CACHE", "~/.cache/vibecomfy/registry")).expanduser()
DEFAULT_TIMEOUT_SECONDS = 15.0


class PackResolverError(RuntimeError):
    """Base error for custom-node pack resolution failures."""


class PackNotFoundError(PackResolverError):
    """Raised when no registry, git, or local candidate resolves."""


class AmbiguousPackError(PackResolverError):
    def __init__(self, query: str, candidates: list[PackRef]):
        self.query = query
        self.candidates = candidates
        choices = ", ".join(candidate.slug for candidate in candidates)
        super().__init__(f"ambiguous pack lookup for {query!r}: {choices}")


@dataclass(frozen=True)
class PackRef:
    slug: str
    source: str
    version: str | None = None
    commit: str | None = None
    url: str | None = None
    path: str | None = None
    name: str | None = None
    registry_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class PackResolution:
    query: str
    query_type: str
    ref: PackRef
    candidates: tuple[PackRef, ...] = ()
    cache_hit: bool = False
    endpoint: str | None = None


class RegistryHTTPClient(Protocol):
    def get(self, url: str, **kwargs: Any) -> httpx.Response: ...


def resolve_pack(
    class_name_or_slug: str,
    *,
    version_pin: str | None = None,
    aux_id: str | None = None,
    local_metadata: PackRef | dict[str, Any] | None = None,
    allow_remote_lookup: bool = True,
    cache_root: Path | None = None,
    client: RegistryHTTPClient | None = None,
) -> PackResolution:
    """Resolve a ComfyUI class name or pack slug/name to a structured pack ref."""
    query = class_name_or_slug.strip()
    normalized_aux_id = _normalize_optional(aux_id)
    if not query:
        raise ValueError("class_name_or_slug must not be empty")
    if _looks_like_local_path(query):
        return PackResolution(
            query=query,
            query_type="local",
            ref=_apply_version_pin(
                PackRef(slug=Path(query).name, source="local", path=query),
                version_pin=version_pin,
                local_metadata=local_metadata,
            ),
        )
    if _looks_like_git_url(query):
        return PackResolution(
            query=query,
            query_type="git",
            ref=_apply_version_pin(
                PackRef(slug=_slug_from_git_url(query), source="git", url=query),
                version_pin=version_pin,
                local_metadata=local_metadata,
            ),
        )
    if normalized_aux_id is not None:
        return PackResolution(
            query=query,
            query_type="aux_git",
            ref=_apply_version_pin(
                PackRef(
                    slug=_slug_from_aux_id(normalized_aux_id),
                    source="aux-git",
                    url=_git_url_from_aux_id(normalized_aux_id),
                    name=query,
                ),
                version_pin=version_pin,
                local_metadata=local_metadata,
            ),
        )
    if not allow_remote_lookup:
        raise PackNotFoundError(f"remote lookup disabled for {query!r}")

    registry = _ComfyRegistryClient(cache_root=cache_root or DEFAULT_CACHE_ROOT, client=client)
    if _looks_like_class_name(query):
        resolution = registry.resolve_class(query)
        if resolution is not None:
            return _resolution_with_pin(resolution, version_pin=version_pin, local_metadata=local_metadata)
    resolution = registry.resolve_slug_or_name(query)
    if resolution is not None:
        return _resolution_with_pin(resolution, version_pin=version_pin, local_metadata=local_metadata)
    raise PackNotFoundError(f"unknown pack or class: {query}")


def lookup_class_candidates(
    class_name: str,
    *,
    cache_root: Path | None = None,
    client: RegistryHTTPClient | None = None,
) -> list[PackRef]:
    """Return registry candidate packs for a class-name search."""
    return _ComfyRegistryClient(cache_root=cache_root or DEFAULT_CACHE_ROOT, client=client).search_class(class_name)


class _ComfyRegistryClient:
    def __init__(self, *, cache_root: Path, client: RegistryHTTPClient | None = None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self.cache_root = cache_root
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        self.timeout_seconds = timeout_seconds

    def resolve_class(self, class_name: str) -> PackResolution | None:
        exact_path = f"/comfy-nodes/{quote(class_name, safe='')}/node"
        payload, cache_hit = self._get_json(exact_path)
        ref = _pack_ref_from_payload(payload)
        if ref is not None:
            return PackResolution(query=class_name, query_type="class", ref=ref, cache_hit=cache_hit, endpoint=exact_path)

        candidates = self.search_class(class_name)
        if len(candidates) == 1:
            return PackResolution(
                query=class_name,
                query_type="class",
                ref=candidates[0],
                candidates=tuple(candidates),
                endpoint="/nodes/search?comfy_node_search=...",
            )
        if len(candidates) > 1:
            raise AmbiguousPackError(class_name, candidates)
        return None

    def search_class(self, class_name: str) -> list[PackRef]:
        path = "/nodes/search"
        payload, _cache_hit = self._get_json(path, params={"comfy_node_search": class_name})
        return _pack_refs_from_search_payload(payload)

    def resolve_slug_or_name(self, slug_or_name: str) -> PackResolution | None:
        if _looks_like_registry_id(slug_or_name):
            id_path = f"/nodes/{quote(slug_or_name, safe='')}"
            payload, cache_hit = self._get_json(id_path)
            ref = _pack_ref_from_payload(payload)
            if ref is not None:
                return PackResolution(query=slug_or_name, query_type="slug", ref=ref, cache_hit=cache_hit, endpoint=id_path)

        search_path = "/nodes/search"
        payload, cache_hit = self._get_json(search_path, params={"search": slug_or_name})
        candidates = _pack_refs_from_search_payload(payload)
        if not candidates:
            return None
        exact = _select_exact_slug_or_name(slug_or_name, candidates)
        if exact is not None:
            return PackResolution(query=slug_or_name, query_type="slug", ref=exact, candidates=tuple(candidates), cache_hit=cache_hit, endpoint=search_path)
        if len(candidates) == 1:
            return PackResolution(
                query=slug_or_name,
                query_type="slug",
                ref=candidates[0],
                candidates=tuple(candidates),
                cache_hit=cache_hit,
                endpoint=search_path,
            )
        raise AmbiguousPackError(slug_or_name, candidates)

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> tuple[Any, bool]:
        cache_file = self._cache_file(path, params)
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8")), True
        url = f"{API_BASE_URL}{path}"
        response = self.client.get(url, params=params, timeout=self.timeout_seconds, follow_redirects=True)
        if response.status_code == 404:
            payload: Any = None
        else:
            response.raise_for_status()
            payload = response.json()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return payload, False

    def _cache_file(self, path: str, params: dict[str, str] | None) -> Path:
        query = urlencode(sorted((params or {}).items()))
        key = f"{path}?{query}" if query else path
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/") or "root")
        return self.cache_root / f"{safe}.{digest}.json"


def _pack_refs_from_search_payload(payload: Any) -> list[PackRef]:
    refs: list[PackRef] = []
    for item in _iter_records(payload):
        ref = _pack_ref_from_payload(item)
        if ref is not None:
            refs.append(ref)
    deduped: dict[str, PackRef] = {}
    for ref in refs:
        deduped.setdefault(_ref_identity(ref), ref)
    return [deduped[key] for key in sorted(deduped)]


def _pack_ref_from_payload(payload: Any) -> PackRef | None:
    if not isinstance(payload, dict):
        return None
    record = _first_mapping(
        payload,
        "node",
        "comfy_node",
        "comfyNode",
        "pack",
        "publisher_node",
        "publisherNode",
        "result",
    )
    if record is None:
        record = payload

    slug = _first_string(record, "id", "slug", "name", "comfy_node_name", "comfyNodeName")
    if not slug:
        return None
    name = _first_string(record, "name", "display_name", "displayName", "comfy_node_name", "comfyNodeName")
    version = _first_string(record, "latest_version", "latestVersion", "version", "tag")
    commit = _first_string(record, "commit", "commit_sha", "commitSha", "git_commit_sha", "gitCommitSha")
    url = _first_string(record, "repository", "repository_url", "repositoryUrl", "repo", "repo_url", "repoUrl", "url")
    registry_id = _first_string(record, "id", "node_id", "nodeId")
    return PackRef(
        slug=slug,
        source="comfy-registry",
        version=version,
        commit=commit,
        url=url,
        name=name,
        registry_id=registry_id,
    )


def _iter_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("nodes", "items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _iter_records(value)
            if nested:
                return nested
    return [payload]


def _first_mapping(record: dict[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, dict):
            return value
    return None


def _first_string(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _select_exact_slug_or_name(query: str, candidates: list[PackRef]) -> PackRef | None:
    normalized_query = _normalize_lookup_key(query)
    matches = [
        candidate
        for candidate in candidates
        if normalized_query in {_normalize_lookup_key(candidate.slug), _normalize_lookup_key(candidate.name or "")}
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousPackError(query, matches)
    return None


def _normalize_lookup_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _resolution_with_pin(
    resolution: PackResolution,
    *,
    version_pin: str | None,
    local_metadata: PackRef | dict[str, Any] | None,
) -> PackResolution:
    return PackResolution(
        query=resolution.query,
        query_type=resolution.query_type,
        ref=_apply_version_pin(resolution.ref, version_pin=version_pin, local_metadata=local_metadata),
        candidates=resolution.candidates,
        cache_hit=resolution.cache_hit,
        endpoint=resolution.endpoint,
    )


def _apply_version_pin(
    ref: PackRef,
    *,
    version_pin: str | None,
    local_metadata: PackRef | dict[str, Any] | None,
) -> PackRef:
    metadata = _normalize_local_metadata(local_metadata)
    pinned_version = _normalize_optional(version_pin)
    commit = metadata.get("commit") or metadata.get("git_commit") or ref.commit
    if pinned_version is not None and _looks_like_commit_pin(pinned_version):
        commit = pinned_version
    if metadata.get("version") is not None:
        version = str(metadata["version"])
    elif pinned_version is not None:
        version = pinned_version
    else:
        version = ref.version
    return PackRef(
        slug=str(metadata.get("slug") or ref.slug),
        source=str(metadata.get("source") or ref.source),
        version=version,
        commit=commit,
        url=str(metadata.get("url") or ref.url) if metadata.get("url") or ref.url else None,
        path=str(metadata.get("path") or ref.path) if metadata.get("path") or ref.path else None,
        name=str(metadata.get("name") or ref.name) if metadata.get("name") or ref.name else None,
        registry_id=str(metadata.get("registry_id") or ref.registry_id) if metadata.get("registry_id") or ref.registry_id else None,
    )


def _normalize_local_metadata(local_metadata: PackRef | dict[str, Any] | None) -> dict[str, Any]:
    if local_metadata is None:
        return {}
    if isinstance(local_metadata, PackRef):
        return local_metadata.to_dict()
    return {str(key): value for key, value in local_metadata.items() if value is not None}


def _ref_identity(ref: PackRef) -> str:
    return f"{ref.source}:{ref.slug}:{ref.registry_id or ''}"


def _looks_like_class_name(value: str) -> bool:
    return bool(re.match(r"^[A-Z][A-Za-z0-9_]*$", value))


def _looks_like_registry_id(value: str) -> bool:
    return bool(re.match(r"^[0-9a-fA-F-]{24,}$", value))


def _looks_like_git_url(value: str) -> bool:
    return value.startswith(("git@", "ssh://")) or value.endswith(".git") or "github.com/" in value


def _looks_like_commit_pin(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", value))


def _looks_like_local_path(value: str) -> bool:
    return value.startswith(("./", "../", "/", "~"))


def _slug_from_git_url(url: str) -> str:
    stripped = url.rstrip("/").removesuffix(".git")
    return stripped.rsplit("/", 1)[-1]


def _git_url_from_aux_id(aux_id: str) -> str:
    return f"https://github.com/{aux_id}.git"


def _slug_from_aux_id(aux_id: str) -> str:
    return aux_id.rsplit("/", 1)[-1]
