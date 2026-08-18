from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from types import MappingProxyType
from pathlib import Path
from typing import Any, Iterator, Mapping, Protocol
from urllib.parse import quote, urlencode, urlparse

import httpx

API_BASE_URL = "https://api.comfy.org"
MANAGER_NODE_MAP_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json"
MANAGER_NODE_LIST_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json"
GITHUB_API_BASE_URL = "https://api.github.com"
DEFAULT_CACHE_ROOT = Path(os.environ.get("VIBECOMFY_REGISTRY_CACHE", "~/.cache/vibecomfy/registry")).expanduser()
DEFAULT_TIMEOUT_SECONDS = 15.0

# R2-B2: hard per-request timeout cap so one hung endpoint cannot blow past
# the research-phase deadline.  Effective timeout = min(client timeout, this).
MAX_REQUEST_TIMEOUT_SECONDS = 5.0

# R2-B1: aggregate wall-clock sub-budget for one resolve_missing_nodes() call.
# Overridable with VIBECOMFY_REGISTRY_SUB_BUDGET (seconds; default 30; 0 disables).
DEFAULT_REGISTRY_SUB_BUDGET_SECONDS = 30.0

# R2-B2: rate-limit cooldown sentinel file (per cache root) and default cooldown
# when the server sends no Retry-After header.
COOLDOWN_FILE_NAME = ".cooldown.json"
COOLDOWN_LOCK_FILE_NAME = ".cooldown.lock"
DEFAULT_COOLDOWN_SECONDS = 60.0
# A persisted GitHub cooldown must not outlive one registry research budget.
MAX_COOLDOWN_SECONDS = DEFAULT_REGISTRY_SUB_BUDGET_SECONDS

# R2-B2: brief negative-cache TTL for GitHub 422 "validation failed" queries.
NEGATIVE_CACHE_TTL_SECONDS = 60.0
NEGATIVE_CACHE_MARKER = "_vibecomfy_negative"

# I-B: process-wide aggregate bound on the api.github.com/search/code tier.
# In the harness one process == one scenario attempt, so this caps the
# pre-first-attempt research hang even when many node classes each trigger
# their own resolve_missing_nodes() call (each with a fresh per-call
# sub-budget).  The per-call sub-budget alone is insufficient: N classes x 30s
# can still eat the whole 1200s scenario wall before a first model attempt.
# Env-overridable; 0 disables (VIBECOMFY_REGISTRY_GITHUB_SEARCH_BUDGET /
# VIBECOMFY_REGISTRY_GITHUB_SEARCH_MAX_REQUESTS).  A hard skip switch
# (VIBECOMFY_REGISTRY_SKIP_GITHUB) disables the entire GitHub tier — the
# harness sets it on the retry of a pre-first-attempt research-hang kill so
# the retry cannot become a second 1200s black hole.
DEFAULT_GITHUB_CODE_SEARCH_BUDGET_SECONDS = 45.0
DEFAULT_GITHUB_CODE_SEARCH_MAX_REQUESTS = 6
GITHUB_SEARCH_BUDGET_ENV = "VIBECOMFY_REGISTRY_GITHUB_SEARCH_BUDGET"
GITHUB_SEARCH_MAX_REQUESTS_ENV = "VIBECOMFY_REGISTRY_GITHUB_SEARCH_MAX_REQUESTS"
GITHUB_SKIP_ENV = "VIBECOMFY_REGISTRY_SKIP_GITHUB"


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


class _BudgetExceeded(PackResolverError):
    """Internal signal that the registry sub-budget (or outer deadline) expired.

    Raised by clients between HTTP requests so resolve_missing_nodes() can stop
    gracefully and return the partial evidence collected so far instead of
    hanging or raising.
    """


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


# ── Registry sub-budget (R2-B1) ──────────────────────────────────────────────
# resolve_missing_nodes() enforces an aggregate wall-clock budget (default 30s,
# env VIBECOMFY_REGISTRY_SUB_BUDGET) and an optional outer monotonic deadline.
# Clients raise _BudgetExceeded between requests; the resolver catches it and
# returns the partial evidence collected so far.


def _registry_sub_budget_seconds() -> float:
    try:
        seconds = float(os.environ.get("VIBECOMFY_REGISTRY_SUB_BUDGET", "") or DEFAULT_REGISTRY_SUB_BUDGET_SECONDS)
    except ValueError:
        seconds = DEFAULT_REGISTRY_SUB_BUDGET_SECONDS
    if seconds < 0:
        seconds = 0.0
    return seconds


def _registry_budget_end(*, deadline: float | None) -> float | None:
    """Absolute monotonic deadline for one resolution call.

    min(outer deadline, now + sub-budget).  A sub-budget of 0 disables the
    aggregate budget (only the outer deadline applies); both None → unbounded.
    """
    budget_seconds = _registry_sub_budget_seconds()
    if budget_seconds <= 0:
        return deadline
    end = time.monotonic() + budget_seconds
    if deadline is not None:
        end = min(end, deadline)
    return end


def _budget_exceeded(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def _bounded_request_timeout(timeout_seconds: float, deadline: float | None) -> float:
    """Clamp one request to both its hard cap and the remaining sub-budget."""
    timeout = min(timeout_seconds, MAX_REQUEST_TIMEOUT_SECONDS)
    if deadline is not None:
        timeout = min(timeout, max(0.001, deadline - time.monotonic()))
    return timeout


# ── Rate-limit cooldown circuit (R2-B2) ─────────────────────────────────────
# On GitHub 403/429 the resolver writes a shared cooldown sentinel (per cache
# root, keyed by endpoint) and honors Retry-After.  A process-wide mirror avoids
# re-reading the file on every request; a file lock makes the write single-flight
# across processes.  Cooldown is best-effort: any IO failure degrades to the
# in-memory flag only.

_PROCESS_COOLDOWNS: dict[str, float] = {}  # key → wall-clock epoch until blocked
_COOLDOWN_MUTEX = threading.Lock()


def _cooldown_key(cache_root: Path, endpoint: str) -> str:
    return f"{cache_root}::{endpoint}"


@contextlib.contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    """Cross-process single-flight file lock (POSIX flock); no-op elsewhere."""
    try:
        import fcntl
    except ImportError:  # pragma: no cover - non-POSIX
        yield
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON via temp file + rename so readers never see partial bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header: integer seconds or an HTTP date."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        seconds = float(text)
        return seconds if seconds > 0 else None
    except ValueError:
        pass
    try:
        stamp = parsedate_to_datetime(text).timestamp()
        return max(0.0, stamp - time.time())
    except (TypeError, ValueError):
        return None


def _cooldown_until(cache_root: Path, endpoint: str) -> float:
    """Wall-clock epoch until which *endpoint* is blocked (0.0 = not blocked)."""
    key = _cooldown_key(cache_root, endpoint)
    with _COOLDOWN_MUTEX:
        until = _PROCESS_COOLDOWNS.get(key, 0.0)
    if until > time.time():
        return until
    file_path = cache_root / COOLDOWN_FILE_NAME
    payload = _read_json_file(file_path)
    if not isinstance(payload, dict):
        return 0.0
    record = payload.get(endpoint)
    if not isinstance(record, dict):
        return 0.0
    try:
        until = float(record.get("until") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if until > time.time():
        with _COOLDOWN_MUTEX:
            _PROCESS_COOLDOWNS.setdefault(key, until)
        return until
    return 0.0


def _cooldown_active(cache_root: Path, endpoint: str) -> bool:
    return _cooldown_until(cache_root, endpoint) > time.time()


def _set_cooldown(cache_root: Path, endpoint: str, retry_after: float | None) -> None:
    """Record a rate-limit cooldown for *endpoint*, honoring Retry-After."""
    try:
        seconds = float(retry_after) if retry_after is not None else DEFAULT_COOLDOWN_SECONDS
    except (TypeError, ValueError):
        seconds = DEFAULT_COOLDOWN_SECONDS
    seconds = max(1.0, min(seconds, MAX_COOLDOWN_SECONDS))
    until = time.time() + seconds
    key = _cooldown_key(cache_root, endpoint)
    with _COOLDOWN_MUTEX:
        _PROCESS_COOLDOWNS[key] = until
    try:
        lock_path = cache_root / COOLDOWN_LOCK_FILE_NAME
        file_path = cache_root / COOLDOWN_FILE_NAME
        with _file_lock(lock_path):
            payload = _read_json_file(file_path)
            if not isinstance(payload, dict):
                payload = {}
            payload[endpoint] = {
                "until": until,
                "retry_after": seconds,
                "set_at": time.time(),
            }
            _atomic_write_json(file_path, payload)
    except OSError:
        pass  # Cooldown is best-effort; the in-process flag still applies.


# ── GitHub code-search process budget (I-B) ─────────────────────────────────
# api.github.com/search/code is the pre-first-attempt hang of record (v5-batch-3
# #1/#7): repeated 422/503 responses across MANY resolve_missing_nodes() calls
# burned the full 1200s scenario wall before a first model attempt.  Each call
# gets its own sub-budget, so the aggregate needed a process-wide bound: one
# process == one scenario attempt in the live harness.  The tier skips itself
# (with a typed warning) once the process has spent its wall budget or made its
# request budget of real HTTP calls; disk-cache hits are not charged.

_PROCESS_GITHUB_CODE_SEARCH_SPENT = 0.0
_PROCESS_GITHUB_CODE_SEARCH_REQUESTS = 0
_PROCESS_GITHUB_MUTEX = threading.Lock()


def _github_code_search_budget_seconds() -> float:
    try:
        seconds = float(
            os.environ.get(GITHUB_SEARCH_BUDGET_ENV, "")
            or DEFAULT_GITHUB_CODE_SEARCH_BUDGET_SECONDS
        )
    except ValueError:
        seconds = DEFAULT_GITHUB_CODE_SEARCH_BUDGET_SECONDS
    return max(0.0, seconds)


def _github_code_search_max_requests() -> int:
    try:
        requests = int(
            os.environ.get(GITHUB_SEARCH_MAX_REQUESTS_ENV, "")
            or DEFAULT_GITHUB_CODE_SEARCH_MAX_REQUESTS
        )
    except ValueError:
        requests = DEFAULT_GITHUB_CODE_SEARCH_MAX_REQUESTS
    return max(0, requests)


def _github_tier_disabled() -> bool:
    """True when the whole GitHub evidence tier is disabled for this process.

    The harness sets VIBECOMFY_REGISTRY_SKIP_GITHUB on the retry of a
    pre-first-attempt research-hang kill so the retry cannot become a second
    1200s black hole on api.github.com/search/code.
    """
    return bool(os.environ.get(GITHUB_SKIP_ENV))


def _github_code_search_allow() -> tuple[bool, str | None]:
    """True when the process-wide code-search budget allows one more attempt."""
    budget = _github_code_search_budget_seconds()
    max_requests = _github_code_search_max_requests()
    with _PROCESS_GITHUB_MUTEX:
        if max_requests > 0 and _PROCESS_GITHUB_CODE_SEARCH_REQUESTS >= max_requests:
            return False, (
                "GitHub code search skipped: process request budget exhausted "
                f"({_PROCESS_GITHUB_CODE_SEARCH_REQUESTS}/{max_requests})."
            )
        if budget > 0 and _PROCESS_GITHUB_CODE_SEARCH_SPENT >= budget:
            return False, (
                "GitHub code search skipped: process wall budget exhausted "
                f"({_PROCESS_GITHUB_CODE_SEARCH_SPENT:.1f}s/{budget:.1f}s)."
            )
    return True, None


def _charge_github_code_search(elapsed_seconds: float, *, http_request: bool) -> None:
    """Charge one code-search attempt against the process budget.

    Disk-cache hits (``http_request=False``) are ~0 wall time and are not
    counted so healthy repeated lookups never starve the tier.
    """
    global _PROCESS_GITHUB_CODE_SEARCH_SPENT, _PROCESS_GITHUB_CODE_SEARCH_REQUESTS
    with _PROCESS_GITHUB_MUTEX:
        _PROCESS_GITHUB_CODE_SEARCH_SPENT += max(0.0, elapsed_seconds)
        if http_request:
            _PROCESS_GITHUB_CODE_SEARCH_REQUESTS += 1


def _reset_process_github_code_search_budget() -> None:
    """Reset the process budget (test seam; also exported for daemon hosts)."""
    global _PROCESS_GITHUB_CODE_SEARCH_SPENT, _PROCESS_GITHUB_CODE_SEARCH_REQUESTS
    with _PROCESS_GITHUB_MUTEX:
        _PROCESS_GITHUB_CODE_SEARCH_SPENT = 0.0
        _PROCESS_GITHUB_CODE_SEARCH_REQUESTS = 0


# ── Negative cache (R2-B2) ───────────────────────────────────────────────────
# GitHub 422 "validation failed" responses are query-shape problems, not
# transient errors: sanitize and retry once, then briefly negative-cache so
# repeated identical queries short-circuit without hammering the API.


def _is_negative_cache(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get(NEGATIVE_CACHE_MARKER) is True
    )


def _write_negative_cache(cache_root: Path, url: str, params: dict[str, str] | None) -> None:
    digest = hashlib.sha256(_cache_key_text(url, params).encode("utf-8")).hexdigest()
    parsed = urlparse(url)
    basename = Path(parsed.path).name or "root"
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", basename)
    cache_file = cache_root / f"{safe}.{digest}.json"
    try:
        _atomic_write_json(
            cache_file,
            {
                NEGATIVE_CACHE_MARKER: True,
                "expires_at": time.time() + NEGATIVE_CACHE_TTL_SECONDS,
                "endpoint": url,
            },
        )
    except OSError:
        pass  # Negative cache is best-effort.


def _cache_key_text(url: str, params: dict[str, str] | None) -> str:
    query = urlencode(sorted((params or {}).items()))
    return f"{url}?{query}" if query else url


def _sanitize_github_search_query(query: str) -> str:
    """Strip characters GitHub code search rejects (quotes, colons, operators)."""
    text = re.sub(r"[^A-Za-z0-9_.\- ]+", " ", str(query))
    text = " ".join(text.split())[:200].strip()
    if text:
        return text
    fallback = " ".join(str(query).split())[:100].strip()
    return fallback or "ComfyUI"


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
    deadline: float | None = None,
) -> MissingNodeResolution:
    """Resolve missing custom-node evidence without importing, cloning, or installing packages.

    *deadline* is an absolute ``time.monotonic()`` value (usually the research
    phase deadline).  The resolver additionally enforces an aggregate sub-budget
    (``VIBECOMFY_REGISTRY_SUB_BUDGET``, default 30s) and a 5s per-request
    timeout cap; when the budget expires it stops gracefully and returns the
    partial evidence collected so far with a warning instead of raising.
    """
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("query must not be empty")
    intent = query_intent or ("class_name" if _looks_like_class_name(normalized_query) else "capability")
    cache = cache_root or DEFAULT_CACHE_ROOT
    budget_end = _registry_budget_end(deadline=deadline)
    registry = _ComfyRegistryClient(cache_root=cache, client=registry_client, deadline=budget_end)
    manager = _ManagerEvidenceClient(cache_root=cache, client=manager_client, deadline=budget_end)
    warnings: list[str] = []
    attempted: list[str] = []
    candidates: dict[str, ResolverCandidate] = {}

    attempted.append("comfyui-manager")
    if _budget_exceeded(budget_end):
        warnings.append("registry sub-budget exceeded before ComfyUI-Manager lookup; partial evidence.")
    else:
        try:
            for candidate in manager.resolve(normalized_query, query_intent=intent):
                _merge_candidate(candidates, candidate)
        except _BudgetExceeded:
            warnings.append("registry sub-budget exceeded during ComfyUI-Manager lookup; partial evidence.")

    attempted.append("comfy-registry")
    registry_refs: list[PackRef] = []
    if _budget_exceeded(budget_end):
        warnings.append("registry sub-budget exceeded before Comfy Registry lookup; partial evidence.")
    else:
        try:
            if intent == "class_name":
                resolution = registry.resolve_class(normalized_query)
                if resolution is not None:
                    registry_refs = [resolution.ref, *resolution.candidates]
            else:
                resolution = registry.resolve_slug_or_name(normalized_query)
                if resolution is not None:
                    registry_refs = [resolution.ref, *resolution.candidates]
        except _BudgetExceeded:
            warnings.append("registry sub-budget exceeded during Comfy Registry lookup; partial evidence.")
        except AmbiguousPackError as exc:
            registry_refs = list(exc.candidates)
            warnings.append(f"Comfy Registry returned ambiguous candidates for {normalized_query!r}.")
        except Exception as exc:
            warnings.append(f"Comfy Registry lookup failed: {type(exc).__name__}: {exc}")
    for ref in registry_refs:
        if _budget_exceeded(budget_end):
            warnings.append("registry sub-budget exceeded before schema fetch; partial evidence.")
            break
        try:
            _merge_candidate(candidates, registry.candidate_for_ref(ref))
        except _BudgetExceeded:
            warnings.append("registry sub-budget exceeded during schema fetch; partial evidence.")
            break

    attempted.append("github")
    github = _GitHubEvidenceClient(cache_root=cache, client=github_client, token=github_token, deadline=budget_end)
    if _budget_exceeded(budget_end):
        warnings.append("registry sub-budget exceeded before GitHub lookup; partial evidence.")
    else:
        try:
            github_candidates, github_warnings = github.resolve(normalized_query, candidates.values())
        except _BudgetExceeded:
            warnings.append("registry sub-budget exceeded during GitHub lookup; partial evidence.")
        else:
            warnings.extend(github_warnings)
            for candidate in github_candidates:
                _merge_candidate(candidates, candidate)

    raw_candidates = list(candidates.values())
    if intent != "class_name":
        anchored_candidates = [
            candidate
            for candidate in raw_candidates
            if _candidate_matches_query_anchor(normalized_query, candidate)
        ]
        dropped = len(raw_candidates) - len(anchored_candidates)
        if dropped:
            warnings.append(
                f"Dropped {dropped} unanchored candidate(s) that did not mention {normalized_query!r}."
            )
        raw_candidates = anchored_candidates

    ordered = sorted(raw_candidates, key=lambda candidate: (_candidate_rank(candidate), candidate.ref.slug.lower()))
    return MissingNodeResolution(
        query=normalized_query,
        query_intent=intent,
        candidates=tuple(ordered),
        warnings=tuple(warnings),
        source_tiers_attempted=tuple(attempted),
    )


class _ComfyRegistryClient:
    def __init__(
        self,
        *,
        cache_root: Path,
        client: RegistryHTTPClient | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        deadline: float | None = None,
    ):
        self.cache_root = cache_root
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        self.timeout_seconds = timeout_seconds
        self.deadline = deadline

    def _check_budget(self) -> None:
        if _budget_exceeded(self.deadline):
            raise _BudgetExceeded("registry sub-budget deadline reached")

    @property
    def _request_timeout(self) -> float:
        return _bounded_request_timeout(self.timeout_seconds, self.deadline)

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
            return _read_json_file(cache_file), True
        self._check_budget()
        url = f"{API_BASE_URL}{path}"
        response = self.client.get(url, params=params, timeout=self._request_timeout, follow_redirects=True)
        if response.status_code == 404:
            payload: Any = None
        else:
            response.raise_for_status()
            payload = response.json()
        _atomic_write_json(cache_file, payload)
        return payload, False

    def _cache_file(self, path: str, params: dict[str, str] | None) -> Path:
        query = urlencode(sorted((params or {}).items()))
        key = f"{path}?{query}" if query else path
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/") or "root")
        return self.cache_root / f"{safe}.{digest}.json"


class _ExternalJsonCache:
    def __init__(
        self,
        *,
        cache_root: Path,
        client: RegistryHTTPClient | None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        deadline: float | None = None,
    ):
        self.cache_root = cache_root
        self.client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=True)
        self.timeout_seconds = timeout_seconds
        self.deadline = deadline

    def _check_budget(self) -> None:
        if _budget_exceeded(self.deadline):
            raise _BudgetExceeded("registry sub-budget deadline reached")

    @property
    def _request_timeout(self) -> float:
        return _bounded_request_timeout(self.timeout_seconds, self.deadline)

    def _get_json_url(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[Any, bool, int, httpx.Headers]:
        """GET *url* with disk caching.

        Returns ``(payload, cache_hit, status_code, response_headers)``.
        A brief negative-cache marker (R2-B2) short-circuits repeated 422
        validation failures as ``(None, True, 422)`` with no HTTP call.
        """
        cache_file = self._cache_file_for_url(url, params)
        if cache_file.exists():
            cached = _read_json_file(cache_file)
            if _is_negative_cache(cached):
                try:
                    expires_at = float(cached.get("expires_at") or 0.0)
                except (TypeError, ValueError):
                    expires_at = 0.0
                if expires_at > time.time():
                    return None, True, 422, httpx.Headers()
                # Expired negative entry → refetch below (and overwrite on success).
            else:
                return cached, True, 200, httpx.Headers()
        self._check_budget()
        response = self.client.get(
            url,
            params=params,
            headers=headers,
            timeout=self._request_timeout,
            follow_redirects=True,
        )
        if response.status_code == 404:
            payload: Any = None
        else:
            if response.status_code >= 400:
                return None, False, response.status_code, response.headers
            payload = response.json()
        _atomic_write_json(cache_file, payload)
        return payload, False, response.status_code, response.headers

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
        node_map, map_cache_hit, _, _ = self._get_json_url(MANAGER_NODE_MAP_URL)
        node_list, list_cache_hit, _, _ = self._get_json_url(MANAGER_NODE_LIST_URL)
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
            evidence_detail = {
                "node_list_cache_hit": list_cache_hit,
                "node_map_cache_hit": map_cache_hit,
            }
            title = _first_string(dict(record), "title", "name", "display_name", "displayName")
            description = _first_string(dict(record), "description", "nickname", "files", "reference", "repository")
            if title:
                evidence_detail["title"] = title
            if description:
                evidence_detail["description"] = description
            evidence = ResolverEvidence(
                tier="comfyui-manager",
                source="custom-node-map" if expected else "custom-node-list",
                endpoint=MANAGER_NODE_MAP_URL if expected else MANAGER_NODE_LIST_URL,
                cache_hit=map_cache_hit if expected else list_cache_hit,
                matched_classes=expected,
                detail=evidence_detail,
            )
            candidates.append(ResolverCandidate(ref=ref, expected_classes=expected, evidence=(evidence,), warnings=tuple(warnings)))
        return candidates


class _GitHubEvidenceClient(_ExternalJsonCache):
    CODE_SEARCH_URL = f"{GITHUB_API_BASE_URL}/search/code"
    REPO_SEARCH_URL = f"{GITHUB_API_BASE_URL}/search/repositories"

    def __init__(
        self,
        *,
        cache_root: Path,
        client: RegistryHTTPClient | None,
        token: str | None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        deadline: float | None = None,
    ):
        super().__init__(cache_root=cache_root, client=client, timeout_seconds=timeout_seconds, deadline=deadline)
        self.token = _normalize_optional(token or os.environ.get("GITHUB_TOKEN"))
        self.configured = client is not None or self.token is not None

    def resolve(
        self,
        query: str,
        existing_candidates: Any,
    ) -> tuple[list[ResolverCandidate], list[str]]:
        warnings: list[str] = []
        # I-B: the harness hard-disables the GitHub tier on the retry of a
        # pre-first-attempt research-hang kill — one env var, whole tier off
        # (code search AND repository search), zero GitHub HTTP.
        if _github_tier_disabled():
            warnings.append(
                "GitHub tier skipped: VIBECOMFY_REGISTRY_SKIP_GITHUB is set "
                "(retry of a pre-first-attempt research hang)."
            )
            return (), warnings
        if not self.configured:
            return (), ("GitHub code search skipped: no token or configured client.",)
        headers = {"Accept": "application/vnd.github+json"}
        if self.token is not None:
            headers["Authorization"] = f"Bearer {self.token}"
        candidates = list(existing_candidates)
        code_candidates: list[ResolverCandidate] = []

        # R2-B2: honor a shared cooldown sentinel (process-wide + on-disk).
        # While a rate limit is active the GitHub tier is skipped entirely —
        # never a fall-through to repository search, which shares the quota.
        if _cooldown_active(self.cache_root, self.CODE_SEARCH_URL):
            warnings.append(
                "GitHub code search is rate-limited (cooldown active); skipping GitHub tier."
            )
            return (), warnings

        search_payload, cache_hit, status, response_headers = self._code_search(
            query, headers=headers, warnings=warnings
        )
        if status in {403, 429}:
            # Rate limit: write the cooldown sentinel honoring Retry-After and
            # stop.  Do NOT fall through to repository search.
            retry_after = _parse_retry_after(response_headers.get("Retry-After"))
            _set_cooldown(self.cache_root, self.CODE_SEARCH_URL, retry_after)
            warnings.append(
                f"GitHub code search rate-limited ({status}); GitHub tier skipped "
                f"for cooldown."
            )
            return (), warnings
        if status == 422:
            # Query-shape rejection: sanitize, retry once, negative-cache
            # briefly.  No exponential backoff, no repo-search fall-through.
            sanitized = _sanitize_github_search_query(query)
            if sanitized != query:
                self._check_budget()
                search_payload, cache_hit, status, response_headers = self._code_search(
                    sanitized, headers=headers, warnings=warnings
                )
                if status in {403, 429}:
                    retry_after = _parse_retry_after(response_headers.get("Retry-After"))
                    _set_cooldown(self.cache_root, self.CODE_SEARCH_URL, retry_after)
                    warnings.append(
                        f"GitHub code search rate-limited ({status}) on retry; "
                        f"GitHub tier skipped for cooldown."
                    )
                    return (), warnings
                if status == 422:
                    _write_negative_cache(
                        self.cache_root, self.CODE_SEARCH_URL, {"q": f"{sanitized} ComfyUI"}
                    )
                    _write_negative_cache(
                        self.cache_root, self.CODE_SEARCH_URL, {"q": f"{query} ComfyUI"}
                    )
                    warnings.append(
                        "GitHub code search rejected the query (422); skipping GitHub tier."
                    )
                    return (), warnings
            else:
                _write_negative_cache(
                    self.cache_root, self.CODE_SEARCH_URL, {"q": f"{query} ComfyUI"}
                )
                warnings.append(
                    "GitHub code search rejected the query (422); skipping GitHub tier."
                )
                return (), warnings
        elif status >= 400:
            # 401 (bad credentials) and other non-rate-limit failures may fall
            # back to repository search, which needs no code-search quota.
            warnings.append(f"GitHub code search unavailable ({status}); falling back to repository search.")
        else:
            code_candidates.extend(_github_candidates_from_code_payload(query, search_payload, cache_hit=cache_hit))

        if code_candidates:
            return code_candidates, warnings

        if _budget_exceeded(self.deadline):
            warnings.append("registry sub-budget exceeded before GitHub repository search; partial evidence.")
            return (), warnings
        self._check_budget()
        try:
            repo_payload, repo_cache_hit, repo_status, _ = self._get_json_url(
                self.REPO_SEARCH_URL,
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

    def _code_search(
        self,
        query: str,
        *,
        headers: dict[str, str],
        warnings: list[str],
    ) -> tuple[Any, bool, int, httpx.Headers]:
        # I-B: the process-wide code-search budget is checked before EVERY
        # attempt (original query and sanitized retry alike), so a cascade of
        # missing node classes cannot eat the scenario wall on this tier.
        allowed, reason = _github_code_search_allow()
        if not allowed:
            warnings.append(reason)
            return None, False, 599, httpx.Headers()
        started = time.monotonic()
        try:
            payload, cache_hit, status, response_headers = self._get_json_url(
                self.CODE_SEARCH_URL,
                params={"q": f"{query} ComfyUI"},
                headers=headers,
            )
        except httpx.HTTPError as exc:
            _charge_github_code_search(time.monotonic() - started, http_request=True)
            warnings.append(f"GitHub code search failed ({type(exc).__name__}); falling back to repository search.")
            return None, False, 599, httpx.Headers()
        _charge_github_code_search(time.monotonic() - started, http_request=not cache_hit)
        return payload, cache_hit, status, response_headers


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
        if isinstance(value, (dict, list, tuple, set)):
            continue
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


_CAPABILITY_ANCHOR_STOPWORDS = {
    "comfy",
    "comfyui",
    "custom",
    "node",
    "nodes",
    "registry",
    "workflow",
    "workflows",
    "video",
    "image",
    "xl",
    "sd",
    "sdxl",
}


def _candidate_matches_query_anchor(query: str, candidate: ResolverCandidate) -> bool:
    anchors = _capability_anchor_terms(query)
    if not anchors:
        return True
    query_key = _normalize_lookup_key(query)
    identity_text = " ".join(
        (
            candidate.ref.slug,
            candidate.ref.name or "",
            candidate.ref.url or "",
        )
    )
    identity_key = _normalize_lookup_key(identity_text)
    if candidate.ref.source == "github" and "comfyui" in query_key and "comfy" not in identity_key:
        return False
    text = " ".join(
        (
            identity_text,
            " ".join(candidate.expected_classes),
            " ".join(candidate.warnings),
            json.dumps([item.to_dict() for item in candidate.evidence], sort_keys=True, default=str),
            json.dumps(dict(candidate.provisional_schema or {}), sort_keys=True, default=str),
        )
    )
    haystack = _normalize_lookup_key(text)
    return any(anchor in haystack for anchor in anchors)


def _capability_anchor_terms(query: str) -> tuple[str, ...]:
    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", query)
        if token.casefold() not in _CAPABILITY_ANCHOR_STOPWORDS
        and not token.isdigit()
    ]
    terms: list[str] = []
    for token in tokens:
        normalized = _normalize_lookup_key(token)
        if len(normalized) >= 3:
            terms.append(normalized)
    if len(tokens) >= 2:
        for size in (3, 2):
            for i in range(0, max(0, len(tokens) - size + 1)):
                joined = _normalize_lookup_key("".join(tokens[i : i + size]))
                if len(joined) >= 3:
                    terms.append(joined)
    return _dedupe_strings(terms)


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
