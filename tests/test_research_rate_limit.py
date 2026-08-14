"""R2-B2 resolver rate-limit circuit tests.

Covers the GitHub 403/429 cooldown sentinel (Retry-After honored, no
fall-through to repository search), 422 sanitize-retry-once with brief
negative caching, and the per-node fan-out cap on registry candidate queries.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from vibecomfy.executor.research import _run_registry_research, research
from vibecomfy.registry.pack_resolver import (
    MissingNodeResolution,
    PackRef,
    ResolverCandidate,
    ResolverEvidence,
    resolve_missing_nodes,
)

CODE_SEARCH_URL = "https://api.github.com/search/code"
REPO_SEARCH_URL = "https://api.github.com/search/repositories"
MANAGER_MAP = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-map.json"
MANAGER_LIST = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json"


class FakeClient:
    """Route-driven httpx-like client for the resolver's injected clients."""

    def __init__(self, routes: dict[tuple[str, tuple[tuple[str, str], ...]], Any]):
        self.routes = routes
        self.calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        params = tuple(sorted((kwargs.get("params") or {}).items()))
        key = (url, params)
        self.calls.append(key)
        request = httpx.Request("GET", url)
        payload = self.routes.get(key)
        if isinstance(payload, httpx.Response):
            return payload
        if payload is None:
            return httpx.Response(404, request=request, json={"error": "not found"})
        return httpx.Response(200, request=request, json=payload)


class NoRepoSearchClient:
    """GitHub client that hard-fails if repository search is attempted."""

    def __init__(self, code_response: httpx.Response):
        self.code_response = code_response
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append(url)
        if url == CODE_SEARCH_URL:
            return self.code_response
        raise AssertionError(f"repository search must not run after a code-search rate limit: {url}")


class BoomClient:
    """GitHub client that fails if ANY request is attempted."""

    def __init__(self):
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append(url)
        raise AssertionError(f"no GitHub request expected, got {url}")


class Flaky422Client:
    """GitHub client that rejects every code-search query with 422."""

    def __init__(self):
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append(url)
        if url == CODE_SEARCH_URL:
            request = httpx.Request("GET", url)
            return httpx.Response(422, request=request, json={"message": "Validation Failed"})
        raise AssertionError(f"repository search must not run after a 422: {url}")


def _manager_client() -> FakeClient:
    return FakeClient(
        {
            (MANAGER_MAP, ()): {},
            (MANAGER_LIST, ()): [],
        }
    )


@pytest.mark.parametrize("status", [403, 429])
def test_github_rate_limit_writes_cooldown_and_skips_repo_search(
    tmp_path: Path, status: int
) -> None:
    """403/429 code-search responses write a shared cooldown sentinel honoring
    Retry-After and never fall through to repository search."""
    response = httpx.Response(
        status,
        request=httpx.Request("GET", CODE_SEARCH_URL),
        headers={"Retry-After": "10"},
        json={"message": "rate limited"},
    )
    github = NoRepoSearchClient(response)

    result = resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=_manager_client(),
        registry_client=FakeClient({}),
        github_client=github,
    )

    assert github.calls == [CODE_SEARCH_URL]  # no repository-search fall-through
    assert result.candidates == ()
    assert any("rate-limited" in warning or "rate limit" in warning for warning in result.warnings)
    cooldown_file = tmp_path / ".cooldown.json"
    assert cooldown_file.exists()
    payload = json.loads(cooldown_file.read_text(encoding="utf-8"))
    assert CODE_SEARCH_URL in payload
    assert payload[CODE_SEARCH_URL]["retry_after"] == 10.0


def test_github_cooldown_honored_across_calls_in_process(tmp_path: Path) -> None:
    """After a 429, a second resolution against the same cache root skips the
    GitHub tier entirely (process-wide + on-disk sentinel) — zero HTTP."""
    response = httpx.Response(
        429,
        request=httpx.Request("GET", CODE_SEARCH_URL),
        headers={"Retry-After": "10"},
        json={"message": "rate limited"},
    )
    resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=_manager_client(),
        registry_client=FakeClient({}),
        github_client=NoRepoSearchClient(response),
    )

    github = BoomClient()
    result = resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=_manager_client(),
        registry_client=FakeClient({}),
        github_client=github,
    )

    assert github.calls == []  # cooldown honored before any HTTP
    assert result.candidates == ()
    assert any("cooldown" in warning for warning in result.warnings)


def test_github_422_sanitizes_retries_once_and_negative_caches(tmp_path: Path) -> None:
    """422 query-shape rejections are sanitized and retried exactly once, then
    briefly negative-cached so identical queries short-circuit without HTTP."""
    github = Flaky422Client()
    query = 'VHS_VideoCombine "weird:query"'

    result = resolve_missing_nodes(
        query,
        cache_root=tmp_path,
        manager_client=_manager_client(),
        registry_client=FakeClient({}),
        github_client=github,
    )

    # Original attempt + one sanitized retry; no repository search.
    assert github.calls == [CODE_SEARCH_URL, CODE_SEARCH_URL]
    assert result.candidates == ()
    assert any("422" in warning for warning in result.warnings)

    # Second resolution: both the original and sanitized queries are
    # negative-cached, so zero code-search HTTP calls.
    github2 = Flaky422Client()
    resolve_missing_nodes(
        query,
        cache_root=tmp_path,
        manager_client=_manager_client(),
        registry_client=FakeClient({}),
        github_client=github2,
    )
    assert github2.calls == []


def test_registry_fanout_capped_at_three_queries_per_missing_node() -> None:
    """A single missing-node query with many class tokens expands to at most
    three resolver queries (R2-B2 fan-out cap)."""
    calls: list[str] = []

    def resolver(query: str) -> MissingNodeResolution:
        calls.append(query)
        return MissingNodeResolution(query=query, query_intent="capability")

    _run_registry_research(
        "ADE_AnimateDiffLoaderWithContext ADE_AnimateDiffUniformContextOptions "
        "ADE_UseEvolvedSampling HotshotLoader ComfyUI nodes",
        resolver=resolver,
    )

    assert len(calls) <= 3


def test_registry_fanout_stops_on_exact_class_validatable_evidence() -> None:
    """The registry loop stops as soon as exact class-validatable evidence
    arrives (Manager/Registry candidate carrying concrete classes)."""
    calls: list[str] = []

    def resolver(query: str) -> MissingNodeResolution:
        calls.append(query)
        return MissingNodeResolution(
            query=query,
            query_intent="class_name",
            candidates=(
                ResolverCandidate(
                    ref=PackRef(slug="comfyui-animatediff-evolved", source="comfy-registry"),
                    expected_classes=("ADE_AnimateDiffLoaderWithContext",),
                    evidence=(
                        ResolverEvidence(
                            tier="comfy-registry",
                            source="schema",
                            endpoint="/nodes/comfyui-animatediff-evolved/versions/1.0.0/schema",
                            matched_classes=("ADE_AnimateDiffLoaderWithContext",),
                        ),
                    ),
                ),
            ),
            source_tiers_attempted=("comfyui-manager", "comfy-registry"),
        )

    sources, warnings = _run_registry_research(
        "ADE_AnimateDiffLoaderWithContext ComfyUI nodes",
        resolver=resolver,
    )

    assert len(calls) == 1  # exact evidence on the first query stops the loop
    assert sources
    assert warnings == ()


def test_research_registry_fanout_capped_through_research() -> None:
    """End to end: a research() call with five missing-node tokens invokes the
    resolver at most three times."""
    calls: list[str] = []

    def resolver(query: str) -> MissingNodeResolution:
        calls.append(query)
        return MissingNodeResolution(query=query, query_intent="capability")

    with patch("vibecomfy.executor.research.build_search_corpus", return_value=[]):
        result = research(
            "ADE_AnimateDiffLoaderWithContext ADE_AnimateDiffUniformContextOptions "
            "ADE_UseEvolvedSampling HotshotLoader ComfyUI nodes",
            hivemind_client=None,
            registry_resolver=resolver,
            web_search_client=None,
            sources=("registry",),
        )

    assert len(calls) <= 3
    assert result.sources == ()
