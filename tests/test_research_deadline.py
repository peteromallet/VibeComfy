"""R2-B1 cooperative research-phase deadline tests.

Covers the 60s wall-clock deadline wrapping the executor's synchronous
Phase-2 research wait: remaining time propagates through research() into the
external tiers, a slow resolver/HTTP client cannot blow past the deadline,
and the phase returns partial evidence gracefully instead of raising.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import patch

import httpx
import pytest

from vibecomfy.executor.research import (
    _run_registry_research,
    research,
)
from vibecomfy.registry.pack_resolver import (
    MissingNodeResolution,
    PackRef,
    ResolverCandidate,
    ResolverEvidence,
    resolve_missing_nodes,
)

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


def _evidence_only_candidate(slug: str) -> ResolverCandidate:
    return ResolverCandidate(
        ref=PackRef(slug=slug, source="comfy-registry", url=f"https://github.com/example/{slug}"),
        evidence=(
            ResolverEvidence(
                tier="comfy-registry",
                source="version-list",
                endpoint=f"/nodes/{slug}/versions",
            ),
        ),
    )


def test_research_returns_partial_evidence_within_deadline_when_resolver_slow() -> None:
    """A registry resolver slower than the deadline must not be re-invoked:
    research() returns the partial evidence from the first call, stops the
    remaining candidate queries, warns about the deadline, and never raises."""
    calls: list[str] = []

    def slow_resolver(query: str) -> MissingNodeResolution:
        calls.append(query)
        time.sleep(0.4)  # slower than the 0.1s deadline
        return MissingNodeResolution(
            query=query,
            query_intent="capability",
            candidates=(_evidence_only_candidate("comfyui-animatediff-evolved"),),
            source_tiers_attempted=("comfyui-manager", "comfy-registry"),
        )

    started = time.monotonic()
    result = research(
        "ADE_AnimateDiffLoaderWithContext ADE_UseEvolvedSampling ComfyUI nodes",
        hivemind_client=None,
        registry_resolver=slow_resolver,
        web_search_client=None,
        sources=("registry",),
        deadline=time.monotonic() + 0.1,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.9  # one slow call, no second candidate query
    assert len(calls) == 1
    assert any("deadline" in warning for warning in result.warnings)
    assert result.sources  # partial evidence from the first call is preserved


def test_resolve_missing_nodes_honors_deadline_with_slow_http_client(tmp_path: Path) -> None:
    """A slow registry HTTP client cannot blow past the phase deadline: the
    resolver checks its budget between requests, stops after the first slow
    request, and returns partial (empty) evidence with a warning."""
    calls: list[str] = []

    class SlowClient:
        def get(self, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(url)
            time.sleep(0.4)
            request = httpx.Request("GET", url)
            if "custom-node-map" in url:
                return httpx.Response(200, request=request, json={})
            if "custom-node-list" in url:
                return httpx.Response(200, request=request, json=[])
            return httpx.Response(404, request=request, json={"error": "not found"})

    result = resolve_missing_nodes(
        "ADE_AnimateDiffLoaderWithContext",
        cache_root=tmp_path,
        manager_client=SlowClient(),
        registry_client=SlowClient(),
        github_client=SlowClient(),
        deadline=time.monotonic() + 0.15,
    )

    assert len(calls) == 1  # only the first manager request; budget stopped the rest
    assert result.candidates == ()
    assert any("sub-budget" in warning or "budget" in warning for warning in result.warnings)


def test_registry_research_loop_stops_between_queries_when_deadline_expires() -> None:
    """The registry tier checks the deadline between candidate queries, so a
    resolver that only becomes slow on later calls is never invoked again."""
    calls: list[str] = []

    def resolver(query: str) -> MissingNodeResolution:
        calls.append(query)
        time.sleep(0.4)  # first call consumes the whole deadline
        return MissingNodeResolution(query=query, query_intent="capability")

    started = time.monotonic()
    sources, warnings = _run_registry_research(
        "ADE_AnimateDiffLoaderWithContext ADE_UseEvolvedSampling ComfyUI nodes",
        resolver=resolver,
        deadline=time.monotonic() + 0.1,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.9
    assert len(calls) == 1  # second query skipped because the deadline expired
    assert sources == ()
    assert any("deadline" in warning for warning in warnings)


def test_research_skips_external_tiers_when_deadline_already_expired() -> None:
    """When the deadline has already passed at phase start, every external tier
    is skipped with one warning and the phase still completes without raising."""
    def boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("external tier must not run after deadline expiry")

    with patch("vibecomfy.executor.research.build_search_corpus", return_value=[]):
        result = research(
            "Hotshot XL ComfyUI nodes",
            hivemind_client=boom,
            registry_resolver=boom,
            web_search_client=boom,
            hivemind_messages_client=boom,
            hivemind_timeout=0.5,
            web_search_timeout=0.5,
            deadline=time.monotonic() - 0.001,
        )

    assert any("deadline reached" in warning for warning in result.warnings)
    assert result.sources == ()


def test_phase_2_research_deadline_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """VIBECOMFY_RESEARCH_PHASE_DEADLINE controls the Phase-2 wall-clock
    deadline: default 60s, overridable, 0 disables."""
    from vibecomfy.executor.core import _phase_2_research_deadline

    monkeypatch.delenv("VIBECOMFY_RESEARCH_PHASE_DEADLINE", raising=False)
    deadline = _phase_2_research_deadline()
    assert deadline is not None
    assert 55.0 <= deadline - time.monotonic() <= 65.0

    monkeypatch.setenv("VIBECOMFY_RESEARCH_PHASE_DEADLINE", "0.05")
    deadline = _phase_2_research_deadline()
    assert deadline is not None
    assert 0.0 < deadline - time.monotonic() <= 0.15

    monkeypatch.setenv("VIBECOMFY_RESEARCH_PHASE_DEADLINE", "0")
    assert _phase_2_research_deadline() is None

    monkeypatch.setenv("VIBECOMFY_RESEARCH_PHASE_DEADLINE", "not-a-number")
    deadline = _phase_2_research_deadline()
    assert deadline is not None
    assert 55.0 <= deadline - time.monotonic() <= 65.0


def test_run_research_forwards_deadline_to_research_phase() -> None:
    """_run_research threads the Phase-2 deadline into run_research_phase."""
    from vibecomfy.executor import core as executor_core
    from vibecomfy.executor.contracts import ExecutorRequest, ResearchResult

    captured: dict[str, Any] = {}

    def fake_research_phase(*args: Any, **kwargs: Any) -> ResearchResult:
        captured["kwargs"] = kwargs
        return ResearchResult()

    with mock.patch.object(
        executor_core, "run_research_phase", side_effect=fake_research_phase
    ):
        result = executor_core._run_research(
            ExecutorRequest(query="test query"),
            None,
            deadline=123.0,
        )

    assert captured["kwargs"]["deadline"] == 123.0
    assert result.summary == ""


def test_registry_resolver_budget_uses_env_sub_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """VIBECOMFY_REGISTRY_SUB_BUDGET bounds the resolver even without an outer
    deadline: with a tiny budget, the slow second request is never attempted."""
    monkeypatch.setenv("VIBECOMFY_REGISTRY_SUB_BUDGET", "0.1")
    calls: list[str] = []

    class SlowClient:
        def get(self, url: str, **kwargs: Any) -> httpx.Response:
            calls.append(url)
            time.sleep(0.3)
            request = httpx.Request("GET", url)
            if "custom-node-map" in url:
                return httpx.Response(200, request=request, json={})
            if "custom-node-list" in url:
                return httpx.Response(200, request=request, json=[])
            return httpx.Response(404, request=request, json={"error": "not found"})

    started = time.monotonic()
    result = resolve_missing_nodes(
        "VHS_VideoCombine",
        cache_root=tmp_path,
        manager_client=SlowClient(),
        registry_client=SlowClient(),
        github_client=SlowClient(),
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.8
    assert len(calls) == 1
    assert any("sub-budget" in warning for warning in result.warnings)
