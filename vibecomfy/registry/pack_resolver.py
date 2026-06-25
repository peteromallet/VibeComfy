from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from types import MappingProxyType
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import quote, urlencode, urlparse

import httpx

API_BASE_URL = "https://api.comfy.org"
MANAGER_NODE_MAP_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json"
MANAGER_NODE_LIST_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json"
GITHUB_API_BASE_URL = "https://api.github.com"
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


@dataclass(frozen=True)
class ResolverEvidence:
    tier: str
    source: str
    endpoint: str
    cache_hit: bool = False
    detail: Mapping[str, Any] | None = None
    matched_classes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "matched_classes", _dedupe_strings(self.matched_classes))
        object.__setattr__(self, "detail", MappingProxyType(dict(self.detail or {})))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tier": self.tier,
            "source": self.source,
            "endpoint": self.endpoint,
            "cache_hit": self.cache_hit,
        }
        if self.detail:
            payload["detail"] = dict(self.detail)
        if self.matched_classes:
            payload["matched_classes"] = list(self.matched_classes)
        return payload


@dataclass(frozen=True)
class ResolverCandidate:
    ref: PackRef
    expected_classes: tuple[str, ...] = ()
    validation_mode: str = "evidence_only"
    evidence: tuple[ResolverEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    provisional_schema: Mapping[str, Any] | None = None
    runnable: bool = False

    def __post_init__(self) -> None:
        expected_classes = _dedupe_strings(self.expected_classes)
        validation_mode = "class_validatable" if expected_classes else "evidence_only"
        object.__setattr__(self, "expected_classes", expected_classes)
        object.__setattr__(self, "validation_mode", validation_mode)
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "warnings", _dedupe_strings(self.warnings))
        object.__setattr__(self, "provisional_schema", MappingProxyType(dict(self.provisional_schema or {})))
        object.__setattr__(self, "runnable", False)

    @property
    def stable_install_hash(self) -> str:
        identity = {
            "slug": self.ref.slug,
            "source": self.ref.source,
            "version": self.ref.version,
            "commit": self.ref.commit,
            "url": self.ref.url,
            "registry_id": self.ref.registry_id,
            "expected_classes": list(self.expected_classes),
            "validation_mode": self.validation_mode,
        }
        raw = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack": self.ref.to_dict(),
            "expected_classes": list(self.expected_classes),
            "validation_mode": self.validation_mode,
            "evidence": [item.to_dict() for item in self.evidence],
            "warnings": list(self.warnings),
            "provisional_schema": dict(self.provisional_schema or {}),
            "runnable": False,
            "stable_install_hash": self.stable_install_hash,
        }


@dataclass(frozen=True)
class MissingNodeResolution:
    query: str
    query_intent: str
    candidates: tuple[ResolverCandidate, ...] = ()
    warnings: tuple[str, ...] = ()
    source_tiers_attempted: tuple[str, ...] = ()
    runnable: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "warnings", _dedupe_strings(self.warnings))
        object.__setattr__(self, "source_tiers_attempted", _dedupe_strings(self.source_tiers_attempted))
        object.__setattr__(self, "runnable", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "query_intent": self.query_intent,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "warnings": list(self.warnings),
            "source_tiers_attempted": list(self.source_tiers_attempted),
            "runnable": False,
        }


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


def resolve_missing_nodes(
    query: str,
    *,
    query_intent: str | None = None,
    cache_root: Path | None = None,
    registry_client: RegistryHTTPClient | None = None,
    manager_client: RegistryHTTPClient | None = None,
    github_client: RegistryHTTPClient | None = None,
    github_token: str | None = None,
) -> MissingNodeResolution:
    """Resolve missing custom-node evidence without importing, cloning, or installing packages."""
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    intent = query_intent or ("class_name" if _looks_like_class_name(normalized_query) else "capability")
    cache = cache_root or DEFAULT_CACHE_ROOT
    registry = _ComfyRegistryClient(cache_root=cache, client=registry_client)
    manager = _ManagerEvidenceClient(cache_root=cache, client=manager_client)
    warnings: list[str] = []
    attempted: list[str] = []
    candidates: dict[str, ResolverCandidate] = {}

    attempted.append("comfyui-manager")
    for candidate in manager.resolve(normalized_query, query_intent=intent):
        _merge_candidate(candidates, candidate)

    attempted.append("comfy-registry")
    registry_refs: list[PackRef] = []
    try:
        if intent == "class_name":
            resolution = registry.resolve_class(normalized_query)
            if resolution is not None:
                registry_refs = [resolution.ref, *resolution.candidates]
        else:
            resolution = registry.resolve_slug_or_name(normalized_query)
            if resolution is not None:
                registry_refs = [resolution.ref, *resolution.candidates]
    except AmbiguousPackError as exc:
        registry_refs = list(exc.candidates)
        warnings.append(f"Comfy Registry returned ambiguous candidates for {normalized_query!r}.")
    except Exception as exc:
        warnings.append(f"Comfy Registry lookup failed: {type(exc).__name__}: {exc}")
    for ref in registry_refs:
        _merge_candidate(candidates, registry.candidate_for_ref(ref))

    attempted.append("github")
    github = _GitHubEvidenceClient(cache_root=cache, client=github_client, token=github_token)
    github_candidates, github_warnings = github.resolve(normalized_query, candidates.values())
    warnings.extend(github_warnings)
    for candidate in github_candidates:
        _merge_candidate(candidates, candidate)

    ordered = sorted(candidates.values(), key=lambda candidate: (_candidate_rank(candidate), candidate.ref.slug.lower()))
    return MissingNodeResolution(
        query=normalized_query,
        query_intent=intent,
        candidates=tuple(ordered),
        warnings=tuple(warnings),
        source_tiers_attempted=tuple(attempted),
    )


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

    def candidate_for_ref(self, ref: PackRef) -> ResolverCandidate:
        evidence: list[ResolverEvidence] = []
        warnings: list[str] = []
        expected_classes: list[str] = []
        provisional_schema: dict[str, Any] = {}
        versions_path = f"/nodes/{quote(ref.registry_id or ref.slug, safe='')}/versions"
        version = _concrete_registry_version(ref.version)
        if version is None:
            payload, cache_hit = self._get_json(versions_path)
            version = _version_from_versions_payload(payload)
            evidence.append(ResolverEvidence(
                tier="comfy-registry",
                source="version-list",
                endpoint=versions_path,
                cache_hit=cache_hit,
            ))
        if version is None:
            warnings.append(f"Comfy Registry has no concrete version for {ref.slug}.")
            evidence.append(ResolverEvidence(
                tier="comfy-registry",
                source="package",
                endpoint=f"/nodes/{quote(ref.registry_id or ref.slug, safe='')}",
                detail={"slug": ref.slug},
            ))
            return ResolverCandidate(ref=ref, evidence=tuple(evidence), warnings=tuple(warnings))

        schema_path = f"/nodes/{quote(ref.registry_id or ref.slug, safe='')}/versions/{quote(version, safe='')}/schema"
        payload, cache_hit = self._get_json(schema_path)
        if payload is None:
            warnings.append(f"Comfy Registry has no schema for {ref.slug} at {version}.")
        else:
            expected_classes = list(_classes_from_schema_payload(payload))
            provisional_schema = {"version": version, "schema": payload, "runnable": False}
        evidence.append(ResolverEvidence(
            tier="comfy-registry",
            source="schema",
            endpoint=schema_path,
            cache_hit=cache_hit,
            matched_classes=tuple(expected_classes),
            detail={"version": version},
        ))
        ref_with_version = PackRef(
            slug=ref.slug,
            source=ref.source,
            version=version,
            commit=ref.commit,
            url=ref.url,
            path=ref.path,
            name=ref.name,
            registry_id=ref.registry_id,
        )
        return ResolverCandidate(
            ref=ref_with_version,
            expected_classes=tuple(expected_classes),
            evidence=tuple(evidence),
            warnings=tuple(warnings),
            provisional_schema=provisional_schema,
        )

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


class _ExternalJsonCache:
    def __init__(self, *, cache_root: Path, client: RegistryHTTPClient | None, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
        self.cache_root = cache_root
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        self.timeout_seconds = timeout_seconds

    def _get_json_url(self, url: str, *, params: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> tuple[Any, bool, int]:
        cache_file = self._cache_file_for_url(url, params)
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8")), True, 200
        response = self.client.get(url, params=params, headers=headers, timeout=self.timeout_seconds, follow_redirects=True)
        if response.status_code == 404:
            payload: Any = None
        else:
            if response.status_code >= 400:
                return None, False, response.status_code
            payload = response.json()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return payload, False, response.status_code

    def _cache_file_for_url(self, url: str, params: dict[str, str] | None) -> Path:
        query = urlencode(sorted((params or {}).items()))
        key = f"{url}?{query}" if query else url
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        parsed = urlparse(url)
        basename = Path(parsed.path).name or "root"
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", basename)
        return self.cache_root / f"{safe}.{digest}.json"


class _ManagerEvidenceClient(_ExternalJsonCache):
    def resolve(self, query: str, *, query_intent: str) -> list[ResolverCandidate]:
        node_map, map_cache_hit, _ = self._get_json_url(MANAGER_NODE_MAP_URL)
        node_list, list_cache_hit, _ = self._get_json_url(MANAGER_NODE_LIST_URL)
        class_to_packs = _manager_class_to_packs(node_map)
        metadata = _manager_pack_metadata(node_list)
        matched_slugs: set[str] = set()
        exact_classes: dict[str, list[str]] = {}
        normalized_query = _normalize_lookup_key(query)
        if query_intent == "class_name" and query in class_to_packs:
            for slug in class_to_packs[query]:
                matched_slugs.add(slug)
                exact_classes.setdefault(slug, []).append(query)
        else:
            for class_name, slugs in class_to_packs.items():
                if normalized_query and normalized_query in _normalize_lookup_key(class_name):
                    for slug in slugs:
                        matched_slugs.add(slug)
                        exact_classes.setdefault(slug, []).append(class_name)
            for slug, record in metadata.items():
                haystack = " ".join(_manager_search_terms(slug, record, class_to_packs)).lower()
                if query.lower() in haystack or normalized_query in _normalize_lookup_key(haystack):
                    matched_slugs.add(slug)

        candidates: list[ResolverCandidate] = []
        for slug in sorted(matched_slugs):
            record = metadata.get(slug, {})
            expected = tuple(exact_classes.get(slug) or _manager_classes_for_pack(slug, class_to_packs))
            warnings: list[str] = []
            if not expected:
                warnings.append(f"ComfyUI-Manager matched {slug} but did not provide concrete node classes.")
            ref = _pack_ref_from_manager_record(slug, record)
            evidence = ResolverEvidence(
                tier="comfyui-manager",
                source="custom-node-map" if expected else "custom-node-list",
                endpoint=MANAGER_NODE_MAP_URL if expected else MANAGER_NODE_LIST_URL,
                cache_hit=map_cache_hit if expected else list_cache_hit,
                matched_classes=expected,
                detail={"node_list_cache_hit": list_cache_hit, "node_map_cache_hit": map_cache_hit},
            )
            candidates.append(ResolverCandidate(ref=ref, expected_classes=expected, evidence=(evidence,), warnings=tuple(warnings)))
        return candidates


class _GitHubEvidenceClient(_ExternalJsonCache):
    def __init__(
        self,
        *,
        cache_root: Path,
        client: RegistryHTTPClient | None,
        token: str | None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        super().__init__(cache_root=cache_root, client=client, timeout_seconds=timeout_seconds)
        self.token = _normalize_optional(token or os.environ.get("GITHUB_TOKEN"))
        self.configured = client is not None or self.token is not None

    def resolve(
        self,
        query: str,
        existing_candidates: Any,
    ) -> tuple[list[ResolverCandidate], list[str]]:
        warnings: list[str] = []
        if not self.configured:
            return (), ("GitHub code search skipped: no token or configured client.",)
        headers = {"Accept": "application/vnd.github+json"}
        if self.token is not None:
            headers["Authorization"] = f"Bearer {self.token}"
        candidates = list(existing_candidates)
        code_candidates: list[ResolverCandidate] = []
        try:
            search_payload, cache_hit, status = self._get_json_url(
                f"{GITHUB_API_BASE_URL}/search/code",
                params={"q": f"{query} ComfyUI"},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            warnings.append(f"GitHub code search failed ({type(exc).__name__}); falling back to repository search.")
            search_payload, cache_hit, status = None, False, 599
        if status in {401, 403, 429}:
            warnings.append(f"GitHub code search unavailable ({status}); falling back to repository search.")
        elif status >= 400:
            warnings.append(f"GitHub code search failed ({status}); falling back to repository search.")
        else:
            code_candidates.extend(_github_candidates_from_code_payload(query, search_payload, cache_hit=cache_hit))

        if code_candidates:
            return code_candidates, warnings

        try:
            repo_payload, repo_cache_hit, repo_status = self._get_json_url(
                f"{GITHUB_API_BASE_URL}/search/repositories",
                params={"q": f"{query} ComfyUI"},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            warnings.append(f"GitHub repository search failed ({type(exc).__name__}).")
            return (), warnings
        if repo_status >= 400:
            warnings.append(f"GitHub repository search failed ({repo_status}).")
            return (), warnings
        repo_candidates = _github_candidates_from_repo_payload(query, repo_payload, cache_hit=repo_cache_hit)
        if repo_candidates:
            return repo_candidates, warnings
        fallback = [_github_candidate_from_existing(query, candidate) for candidate in candidates if candidate.ref.url]
        return [candidate for candidate in fallback if candidate is not None], warnings


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


def _manager_class_to_packs(payload: Any) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    if not isinstance(payload, dict):
        return result
    for raw_class, raw_value in payload.items():
        class_name = str(raw_class).strip()
        if not class_name:
            continue
        slugs: list[str] = []
        if isinstance(raw_value, str):
            slugs.append(raw_value.strip())
        elif isinstance(raw_value, list):
            for item in raw_value:
                slugs.extend(_manager_slugs_from_value(item))
        elif isinstance(raw_value, dict):
            slugs.extend(_manager_slugs_from_value(raw_value))
        result[class_name] = _dedupe_strings(slugs)
    return result


def _manager_slugs_from_value(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()]
    if not isinstance(value, dict):
        return []
    return [
        text
        for text in (
            _first_string(value, "title", "name", "id", "slug", "custom_node_name", "customNodeName"),
            _slug_from_manager_url(_first_string(value, "files", "reference", "repository", "url") or ""),
        )
        if text
    ]


def _manager_pack_metadata(payload: Any) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    records = _iter_records(payload)
    if isinstance(payload, dict) and not records:
        records = [value for value in payload.values() if isinstance(value, dict)]
    for record in records:
        slug = _first_string(record, "title", "name", "id", "slug", "custom_node_name", "customNodeName")
        if not slug:
            slug = _slug_from_manager_url(_first_string(record, "files", "reference", "repository", "url") or "")
        if slug:
            metadata.setdefault(slug, record)
    if isinstance(payload, dict):
        for key, value in payload.items():
            if isinstance(value, dict):
                metadata.setdefault(str(key), value)
    return metadata


def _pack_ref_from_manager_record(slug: str, record: Mapping[str, Any]) -> PackRef:
    url = _first_string(dict(record), "repository", "repo", "url", "reference", "files")
    return PackRef(
        slug=slug,
        source="comfyui-manager",
        url=url,
        name=_first_string(dict(record), "title", "name", "display_name", "displayName") or slug,
        registry_id=_first_string(dict(record), "id"),
    )


def _manager_search_terms(slug: str, record: Mapping[str, Any], class_to_packs: Mapping[str, tuple[str, ...]]) -> list[str]:
    terms = [slug]
    for key in ("title", "name", "description", "nickname", "author", "files", "reference", "repository"):
        value = record.get(key)
        if isinstance(value, str):
            terms.append(value)
        elif isinstance(value, list):
            terms.extend(str(item) for item in value)
    terms.extend(class_name for class_name, slugs in class_to_packs.items() if slug in slugs)
    return terms


def _manager_classes_for_pack(slug: str, class_to_packs: Mapping[str, tuple[str, ...]]) -> tuple[str, ...]:
    return _dedupe_strings(class_name for class_name, slugs in class_to_packs.items() if slug in slugs)


def _slug_from_manager_url(value: str) -> str | None:
    if not value:
        return None
    text = str(value).strip().rstrip("/").removesuffix(".git")
    if not text:
        return None
    return text.rsplit("/", 1)[-1]


def _concrete_registry_version(version: str | None) -> str | None:
    text = _normalize_optional(version)
    if text is None or text.lower() == "latest":
        return None
    return text


def _version_from_versions_payload(payload: Any) -> str | None:
    for record in _iter_records(payload):
        version = _first_string(record, "version", "name", "tag", "id")
        if version and version.lower() != "latest":
            return version
    if isinstance(payload, dict):
        for key in ("version", "latest_version", "latestVersion"):
            version = _first_string(payload, key)
            if version and version.lower() != "latest":
                return version
    return None


def _classes_from_schema_payload(payload: Any) -> tuple[str, ...]:
    classes: list[str] = []
    if isinstance(payload, dict):
        for key in ("class_type", "class", "name", "node_class", "nodeClass"):
            value = payload.get(key)
            if isinstance(value, str) and _looks_like_class_name(value):
                classes.append(value)
        for key in ("nodes", "classes", "schemas", "object_info", "objectInfo"):
            value = payload.get(key)
            if isinstance(value, dict):
                classes.extend(str(name) for name in value if _looks_like_class_name(str(name)))
                for item in value.values():
                    classes.extend(_classes_from_schema_payload(item))
            elif isinstance(value, list):
                for item in value:
                    classes.extend(_classes_from_schema_payload(item))
    elif isinstance(payload, list):
        for item in payload:
            classes.extend(_classes_from_schema_payload(item))
    return _dedupe_strings(classes)


def _github_candidates_from_code_payload(query: str, payload: Any, *, cache_hit: bool) -> list[ResolverCandidate]:
    candidates: list[ResolverCandidate] = []
    for item in _iter_records(payload):
        repo = item.get("repository") if isinstance(item.get("repository"), dict) else {}
        full_name = _first_string(repo, "full_name", "name") or _first_string(item, "name", "path") or query
        url = _first_string(repo, "html_url", "url")
        classes = _dedupe_strings(_class_names_from_text(json.dumps(item, sort_keys=True)))
        ref = PackRef(slug=full_name.rsplit("/", 1)[-1], source="github", url=url, name=full_name)
        evidence = ResolverEvidence(
            tier="github",
            source="code-search",
            endpoint=f"{GITHUB_API_BASE_URL}/search/code",
            cache_hit=cache_hit,
            matched_classes=classes,
        )
        candidates.append(ResolverCandidate(ref=ref, expected_classes=classes, evidence=(evidence,)))
    return candidates


def _github_candidates_from_repo_payload(query: str, payload: Any, *, cache_hit: bool) -> list[ResolverCandidate]:
    candidates: list[ResolverCandidate] = []
    for item in _iter_records(payload):
        slug = _first_string(item, "name", "full_name") or query
        url = _first_string(item, "html_url", "clone_url", "url")
        text = " ".join(str(item.get(key, "")) for key in ("name", "full_name", "description"))
        classes = _dedupe_strings(_class_names_from_text(text))
        warnings = () if classes else (f"GitHub repository search matched {slug} without concrete class evidence.",)
        evidence = ResolverEvidence(
            tier="github",
            source="repository-search",
            endpoint=f"{GITHUB_API_BASE_URL}/search/repositories",
            cache_hit=cache_hit,
            matched_classes=classes,
        )
        candidates.append(ResolverCandidate(
            ref=PackRef(slug=slug, source="github", url=url, name=_first_string(item, "full_name")),
            expected_classes=classes,
            evidence=(evidence,),
            warnings=warnings,
        ))
    return candidates


def _github_candidate_from_existing(query: str, candidate: ResolverCandidate) -> ResolverCandidate | None:
    classes = _dedupe_strings(_class_names_from_text(query))
    evidence = ResolverEvidence(
        tier="github",
        source="repository-fallback",
        endpoint=candidate.ref.url or "",
        matched_classes=classes,
    )
    return ResolverCandidate(ref=candidate.ref, expected_classes=classes, evidence=(evidence,))


def _class_names_from_text(text: str) -> tuple[str, ...]:
    return _dedupe_strings(match.group(0) for match in re.finditer(r"\b[A-Z][A-Za-z0-9_]{2,}\b", text))


def _iter_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("nodes", "items", "results", "data", "versions"):
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


def _merge_candidate(candidates: dict[str, ResolverCandidate], candidate: ResolverCandidate) -> None:
    key = _normalize_lookup_key(candidate.ref.slug)
    existing = candidates.get(key)
    if existing is None:
        candidates[key] = candidate
        return
    ref = _prefer_ref(existing.ref, candidate.ref)
    expected_classes = _dedupe_strings((*existing.expected_classes, *candidate.expected_classes))
    evidence = (*existing.evidence, *candidate.evidence)
    warnings = _dedupe_strings((*existing.warnings, *candidate.warnings))
    provisional_schema = dict(existing.provisional_schema or {})
    provisional_schema.update(dict(candidate.provisional_schema or {}))
    candidates[key] = ResolverCandidate(
        ref=ref,
        expected_classes=expected_classes,
        evidence=evidence,
        warnings=warnings,
        provisional_schema=provisional_schema,
    )


def _prefer_ref(left: PackRef, right: PackRef) -> PackRef:
    return PackRef(
        slug=left.slug or right.slug,
        source=left.source if left.source != "github" else right.source,
        version=left.version or right.version,
        commit=left.commit or right.commit,
        url=left.url or right.url,
        path=left.path or right.path,
        name=left.name or right.name,
        registry_id=left.registry_id or right.registry_id,
    )


def _candidate_rank(candidate: ResolverCandidate) -> tuple[int, int]:
    return (0 if candidate.validation_mode == "class_validatable" else 1, -len(candidate.evidence))


def _dedupe_strings(values: Any) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


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
