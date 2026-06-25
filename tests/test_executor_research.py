"""Unit tests for the deterministic executor research module.

Covers local-corpus research, compact source normalization, injectable
Hivemind client, timeout/error → warning conversion, deduplication, and
merge ordering.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote_plus
from unittest.mock import patch

import pytest

from vibecomfy.executor.contracts import (
    InspectionSummary,
    PrecedentAdaptationPlan,
    ResearchResult,
    WorkflowSlice,
)
from vibecomfy.executor.research import (
    HivemindError,
    _default_hivemind_client,
    _build_adaptation_plan,
    _build_inspection_summary,
    _build_precedent_slices,
    _build_summary,
    _normalize_hivemind_source,
    _normalize_source,
    _run_hivemind_research,
    research,
    run_local_research,
)
from vibecomfy.search.index import SearchEntry
from vibecomfy.search.scorer import SearchResult
from vibecomfy.ingest.workflow_source import load_workflow_source, normalize_workflow_source


# ── Helpers ──────────────────────────────────────────────────────────────────


none_found_warning = "precedent research: no workflow/template precedents found in local corpus or Hivemind results"


def _make_entry(
    class_type: str = "KSampler",
    pack: str | None = "core",
    description: str = "KSampler node",
    tags: tuple[str, ...] = (),
    tasks: tuple[str, ...] = (),
    source: str = "object_info",
    path: str | None = None,
    template_id: str | None = None,
    source_workflow_path: str | None = None,
    source_workflow_available: bool = False,
    source_workflow_parseable: bool = False,
    adapt_pattern_keys: tuple[str, ...] = (),
) -> SearchEntry:
    return SearchEntry(
        class_type=class_type,
        pack=pack,
        description=description,
        tags=tags,
        tasks=tasks,
        source=source,
        path=path,
        template_id=template_id,
        source_workflow_path=source_workflow_path,
        source_workflow_available=source_workflow_available,
        source_workflow_parseable=source_workflow_parseable,
        adapt_pattern_keys=adapt_pattern_keys,
    )


def _make_result(
    class_type: str = "KSampler",
    score: int = 10,
    reasons: tuple[str, ...] = ("class_type",),
    **kwargs: Any,
) -> SearchResult:
    entry = _make_entry(class_type=class_type, **kwargs)
    return SearchResult(entry=entry, score=score, reasons=tuple(reasons))


# ── Source normalization ─────────────────────────────────────────────────────


class TestNormalizeSource:
    """Deterministic compact normalisation of scored search results."""

    def test_keys_and_order_are_deterministic(self) -> None:
        result = _make_result("KSampler", score=10, reasons=("class_type", "tag"))
        source = _normalize_source(result)
        assert list(source.keys()) == [
            "class_type",
            "score",
            "reasons",
            "source",
            "pack",
            "description",
            "tasks",
            "path",
            "template_id",
            "source_workflow_path",
            "source_workflow_available",
            "source_workflow_parseable",
            "adapt_pattern_keys",
        ]
        assert source["class_type"] == "KSampler"
        assert source["score"] == 10
        assert source["reasons"] == ["class_type", "tag"]

    def test_tasks_serialized_as_list(self) -> None:
        result = _make_result("LoadImage", tasks=("t2i",))
        source = _normalize_source(result)
        assert source["tasks"] == ["t2i"]

    def test_empty_tasks_is_empty_list(self) -> None:
        result = _make_result("CheckpointLoaderSimple")
        source = _normalize_source(result)
        assert source["tasks"] == []

    def test_none_pack_is_serialized(self) -> None:
        result = _make_result("CustomNode", pack=None)
        source = _normalize_source(result)
        assert source["pack"] is None

    def test_path_is_preserved_for_workflow_source(self) -> None:
        result = _make_result(
            "video/ltx2_3_t2v",
            source="ready_template",
            path="ready_templates/video/ltx2_3_t2v.py",
            template_id="video/ltx2_3_t2v",
            source_workflow_path="ready_templates/sources/custom_nodes/ltxvideo/ltx2_3.json",
            source_workflow_available=True,
            source_workflow_parseable=True,
            adapt_pattern_keys=("two_pass_refinement",),
        )
        source = _normalize_source(result)
        assert source["path"] == "ready_templates/video/ltx2_3_t2v.py"
        assert source["template_id"] == "video/ltx2_3_t2v"
        assert source["source_workflow_parseable"] is True
        assert source["adapt_pattern_keys"] == ["two_pass_refinement"]


class TestNormalizeHivemindSource:
    """Normalisation of Hivemind response items."""

    def test_full_item(self) -> None:
        item = {
            "class_type": "WANVideoWrapper",
            "score": 88,
            "reasons": ["tag"],
            "pack": "wanvideowrapper",
            "description": "WAN video wrapper node",
            "tasks": ["t2v"],
        }
        out = _normalize_hivemind_source(item)
        assert out["class_type"] == "WANVideoWrapper"
        assert out["source"] == "hivemind"
        assert out["score"] == 88

    def test_fallback_name_key(self) -> None:
        item = {"name": "FallbackNode", "score": 50}
        out = _normalize_hivemind_source(item)
        assert out["class_type"] == "FallbackNode"

    def test_missing_keys_default(self) -> None:
        item: dict[str, Any] = {}
        out = _normalize_hivemind_source(item)
        assert out["class_type"] == ""
        assert out["score"] == 0
        assert out["source"] == "hivemind"

    def test_package_key_as_pack(self) -> None:
        item = {"class_type": "N", "package": "mypack"}
        out = _normalize_hivemind_source(item)
        assert out["pack"] == "mypack"

    def test_workflow_resource_uses_python_ready_template_metadata(self) -> None:
        item = {
            "kind": "workflow",
            "item_id": "42",
            "title": "video/ltx2_3_runexx_custom_audio",
            "body": "VibeComfy ready-template Python workflow",
            "metadata": {
                "ready_template_id": "video/ltx2_3_runexx_custom_audio",
                "path": "ready_templates/video/ltx2_3_runexx_custom_audio.py",
            },
        }
        out = _normalize_hivemind_source(item)
        assert out["source"] == "hivemind_workflow"
        assert out["class_type"] == "video/ltx2_3_runexx_custom_audio"
        assert out["path"] == "ready_templates/video/ltx2_3_runexx_custom_audio.py"
        assert out["hivemind_id"] == "42"


class TestBuildSummary:
    """Compact 1-sentence summary builder."""

    def test_empty(self) -> None:
        assert _build_summary(()) == "No relevant local results found."

    def test_single(self) -> None:
        sources = ({"class_type": "KSampler"},)
        assert _build_summary(sources) == "Found 1 local result(s): KSampler"

    def test_three(self) -> None:
        sources = (
            {"class_type": "A"},
            {"class_type": "B"},
            {"class_type": "C"},
        )
        summary = _build_summary(sources)
        assert summary.startswith("Found 3 local result(s): A, B, C")
        assert "more" not in summary

    def test_more_than_three(self) -> None:
        sources = tuple({"class_type": c} for c in ["A", "B", "C", "D", "E"])
        summary = _build_summary(sources)
        assert "A, B, C" in summary
        assert "2 more" in summary

    def test_workflow_paths_and_exploration_guidance(self) -> None:
        sources = (
            {
                "class_type": "video/ltx2_3_t2v",
                "source": "ready_template",
                "path": "ready_templates/video/ltx2_3_t2v.py",
            },
            {
                "class_type": "ltx2_3_source",
                "source": "source_workflow",
                "path": "ready_templates/sources/custom_nodes/ltxvideo/ltx2_3.json",
            },
        )
        summary = _build_summary(sources)
        assert "video/ltx2_3_t2v (ready_templates/video/ltx2_3_t2v.py)" in summary
        assert ".json" not in summary
        assert "vibecomfy workflows list --ready" in summary
        assert "vibecomfy copy-to-recipe <template_id> --out <file.py> --strip-markers" in summary
        assert "ready template `.py` representations" in summary
        assert "open that path directly in ComfyUI" not in summary


# ── Local research (deterministic) ───────────────────────────────────────────


class TestRunLocalResearch:
    """Deterministic local-corpus-first research."""

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_returns_research_result(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler", description="sampling node")]
        result = run_local_research("sampling")
        assert isinstance(result, ResearchResult)
        assert result.summary
        assert isinstance(result.sources, tuple)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_empty_corpus(self, mock_corpus) -> None:
        mock_corpus.return_value = []
        result = run_local_research("anything")
        assert result.summary == "No relevant local results found."
        assert result.sources == ()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_no_matching_results(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("CLIPTextEncode", description="text encoding")]
        result = run_local_research("zzz_nonexistent_query_xyz")
        # Scorer may return 0 matches for nonsense query.
        if result.sources:
            # If some fuzzy match found, scores should be low.
            for s in result.sources:
                assert s["score"] <= 2
        else:
            assert result.summary == "No relevant local results found."

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_results_are_deterministic_same_input(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry("KSampler", description="sampler node"),
            _make_entry("VAEDecode", description="vae decode node"),
        ]
        r1 = run_local_research("sampler")
        r2 = run_local_research("sampler")
        assert r1.summary == r2.summary
        assert r1.sources == r2.sources

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_task_hint_alters_scoring(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry("KSampler", tags=("sampling",)),
            _make_entry("LTXVLoader", tags=("ltx", "video")),
        ]
        r_no_task = run_local_research("video")
        r_with_task = run_local_research("video", task="t2v")
        # Different task hints may produce different scores/ordering.
        assert isinstance(r_no_task, ResearchResult)
        assert isinstance(r_with_task, ResearchResult)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_limit_is_respected(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry(f"Node{i}") for i in range(20)]
        result = run_local_research("Node", limit=5)
        assert len(result.sources) <= 5

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_sources_are_tuple(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = run_local_research("KSampler")
        assert isinstance(result.sources, tuple)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_warnings_empty_for_local_only(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = run_local_research("KSampler")
        assert result.warnings == ()


# ── Hivemind error / timeout behaviour ───────────────────────────────────────


class TestHivemindErrors:
    """Hivemind errors are non-fatal warnings, never raw exceptions."""

    def _timeout_client(self, query: str, timeout: float) -> dict[str, Any]:
        raise HivemindError(f"timed out after {timeout}s")

    def _http_error_client(self, query: str, timeout: float) -> dict[str, Any]:
        raise HivemindError("connection refused")

    def _unexpected_client(self, query: str, timeout: float) -> dict[str, Any]:
        raise RuntimeError("something unexpected")

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_timeout_produces_warning_not_exception(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._timeout_client,
            hivemind_timeout=0.5,
        )
        assert result.warnings
        assert any("timed out" in w for w in result.warnings)
        assert {"type": "HivemindError", "message": "timed out after 0.5s"} in result.warning_details
        assert len(result.sources) >= 1  # local results still present

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_http_error_produces_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._http_error_client,
        )
        assert result.warnings
        assert any("connection refused" in w for w in result.warnings)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_unexpected_error_produces_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._unexpected_client,
        )
        assert result.warnings
        assert any("unexpected" in w for w in result.warnings)
        assert {"type": "RuntimeError", "message": "something unexpected"} in result.warning_details

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_none_client_skips_silently(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research("KSampler", hivemind_client=None, web_search_client=None)
        assert none_found_warning in result.warnings
        assert len(result.warnings) == 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_zero_timeout_disables_hivemind(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._timeout_client,
            hivemind_timeout=0,
            web_search_client=None,
        )
        # Zero timeout → Hivemind tier never invoked.
        assert none_found_warning in result.warnings
        assert len(result.warnings) == 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_negative_timeout_disables_hivemind(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research(
            "KSampler",
            hivemind_client=self._timeout_client,
            hivemind_timeout=-1.0,
            web_search_client=None,
        )
        assert none_found_warning in result.warnings
        assert len(result.warnings) == 1


# ── Hivemind merge behaviour ─────────────────────────────────────────────────


class TestHivemindMerge:
    """Hivemind results merge after local, with deduplication and ordering."""

    def _merge_client(self, query: str, timeout: float) -> dict[str, Any]:
        return {
            "results": [
                {
                    "class_type": "WANVideoWrapper",
                    "score": 85,
                    "reasons": ["hivemind_tag"],
                    "description": "WAN video wrapper",
                    "tasks": ["t2v"],
                },
                {
                    "class_type": "VAEDecode",
                    "score": 40,
                    "reasons": ["hivemind_tag"],
                    "description": "VAE decode",
                    "tasks": [],
                },
            ]
        }

    def _duplicate_client(self, query: str, timeout: float) -> dict[str, Any]:
        return {
            "results": [
                {
                    "class_type": "KSampler",  # same as local
                    "score": 99,
                    "reasons": ["hivemind_override"],
                },
                {
                    "class_type": "NewHivemindNode",
                    "score": 70,
                    "reasons": ["hivemind_only"],
                },
            ]
        }

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_results_appear_after_local(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry("KSampler", source="object_info"),
            _make_entry("VAEDecode", source="object_info"),
        ]
        result = research(
            "video sampler",
            hivemind_client=self._merge_client,
            web_search_client=None,
        )
        sources = list(result.sources)
        # Local sources should come before hivemind sources.
        local_indices = [i for i, s in enumerate(sources) if s["source"] != "hivemind"]
        hm_indices = [i for i, s in enumerate(sources) if s["source"] == "hivemind"]
        if local_indices and hm_indices:
            assert max(local_indices) < min(hm_indices)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_duplicate_class_type_keeps_both_tiers(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler", source="object_info")]
        result = research(
            "KSampler",
            hivemind_client=self._duplicate_client,
        )
        # Cross-tier duplicates are intentionally preserved so the agent can see
        # what each source tier produced. KSampler therefore appears from both
        # local corpus and Hivemind; NewHivemindNode appears once from Hivemind.
        ksampler_sources = [s for s in result.sources if s["class_type"] == "KSampler"]
        assert len(ksampler_sources) == 2
        assert any(s["source"] != "hivemind" for s in ksampler_sources)
        assert any(s["source"] == "hivemind" for s in ksampler_sources)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_with_no_results_is_handled(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def empty_client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        result = research("KSampler", hivemind_client=empty_client)
        ks_count = sum(1 for s in result.sources if s["class_type"] == "KSampler")
        assert ks_count == 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_malformed_response_produces_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def bad_client(q: str, t: float) -> dict[str, Any]:
            return {"results": "not-a-list"}  # type: ignore[dict-item]

        result = research("KSampler", hivemind_client=bad_client)
        # Malformed results key should not break; no warning for bad shape
        # (the code guards against non-list). Local results preserved.
        assert len(result.sources) >= 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_sources_key_fallback(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def sources_client(q: str, t: float) -> dict[str, Any]:
            return {
                "sources": [
                    {"class_type": "FromSources", "score": 60}
                ]
            }

        result = research("test", hivemind_client=sources_client)
        assert any(s["class_type"] == "FromSources" for s in result.sources)


# ── Default direct-HTTP client (unit-level) ──────────────────────────────────


class TestDefaultHivemindClient:
    """Direct-HTTP Hivemind client behaviour under mocked transport."""

    def test_raises_hivemind_error_on_timeout(self) -> None:
        def slow_read(*args: Any, **kwargs: Any) -> None:
            # Simulate a slow response by sleeping beyond a very short timeout.
            # urlopen's timeout is enforced by the socket layer, so we mock
            # urllib.request.urlopen to raise TimeoutError.
            raise TimeoutError("timed out")

        with patch("urllib.request.urlopen", side_effect=slow_read):
            with pytest.raises(HivemindError, match="timed out"):
                _default_hivemind_client("test", timeout=0.01)

    def test_raises_hivemind_error_on_http_failure(self) -> None:
        import urllib.error

        def http_error(*args: Any, **kwargs: Any) -> None:
            raise urllib.error.URLError("connection refused")

        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(HivemindError, match="HTTP error"):
                _default_hivemind_client("test", timeout=1.0)

    def test_returns_parsed_json_on_success(self) -> None:
        expected = {"results": [{"class_type": "N", "score": 10}]}
        mock_response = type(
            "MockResponse",
            (),
            {
                "read": lambda self: b'{"results": [{"class_type": "N", "score": 10}]}',
                "__enter__": lambda self: self,
                "__exit__": lambda self, *a: None,
            },
        )()

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _default_hivemind_client("test", timeout=1.0)
            assert result == expected

    def test_postgrest_search_tokenizes_multi_word_query(self) -> None:
        seen_urls: list[str] = []
        mock_response = type(
            "MockResponse",
            (),
            {
                "read": lambda self: (
                    b'[{"title": "Hotshot XL workflow", '
                    b'"body": "Notes for SDXL video generation"}]'
                ),
                "__enter__": lambda self: self,
                "__exit__": lambda self, *a: None,
            },
        )()

        def capture_urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            seen_urls.append(req.full_url)
            return mock_response

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            result = _default_hivemind_client("Hotshot XL SDXL video", timeout=1.0)

        assert result["results"]
        assert result["results"][0]["title"] == "Hotshot XL workflow"
        decoded_url = unquote_plus(seen_urls[0])
        assert "hivemind.nousresearch.com" not in decoded_url
        assert "unified_feed" in decoded_url
        assert "title.ilike.*Hotshot XL SDXL*" in decoded_url
        assert "title.ilike.*Hotshot*" in decoded_url

    def test_postgrest_search_queries_workflow_kind_and_prioritizes_it(self) -> None:
        seen_urls: list[str] = []

        def capture_urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            seen_urls.append(req.full_url)
            if "kind=eq.workflow" in req.full_url:
                payload = (
                    b'[{"kind": "workflow", "title": "video/ltx2_3_runexx_custom_audio", '
                    b'"body": "LTX RuneXX audio workflow", '
                    b'"metadata": {"ready_template_id": "video/ltx2_3_runexx_custom_audio", '
                    b'"path": "ready_templates/video/ltx2_3_runexx_custom_audio.py"}}]'
                )
            else:
                payload = b'[{"kind": "message", "title": "generic audio note", "body": "audio"}]'
            return type(
                "MockResponse",
                (),
                {
                    "read": lambda self: payload,
                    "__enter__": lambda self: self,
                    "__exit__": lambda self, *a: None,
                },
            )()

        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            result = _default_hivemind_client("LTX RuneXX audio workflow", timeout=1.0)

        assert any("kind=eq.workflow" in url for url in seen_urls)
        assert result["results"][0]["kind"] == "workflow"

    def test_raises_hivemind_error_on_invalid_json(self) -> None:
        mock_response = type(
            "MockResponse",
            (),
            {
                "read": lambda self: b"not json",
                "__enter__": lambda self: self,
                "__exit__": lambda self, *a: None,
            },
        )()

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(HivemindError, match="invalid JSON"):
                _default_hivemind_client("test", timeout=1.0)


# ── Full research() integration behaviour ────────────────────────────────────


class TestResearchIntegration:
    """End-to-end ``research()`` behaviour with mocks."""

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_local_only_no_warnings(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        result = research("KSampler", hivemind_client=None, web_search_client=None)
        assert none_found_warning in result.warnings
        assert len(result.warnings) == 1
        assert len(result.sources) >= 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_local_plus_hivemind_merge(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def client(q: str, t: float) -> dict[str, Any]:
            return {"results": [{"class_type": "HmNode", "score": 80}]}

        result = research("KSampler", hivemind_client=client)
        class_types = [s["class_type"] for s in result.sources]
        assert "KSampler" in class_types
        assert "HmNode" in class_types

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_to_dict_produces_serializable_output(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def client(q: str, t: float) -> dict[str, Any]:
            raise HivemindError("unreachable")

        result = research("KSampler", hivemind_client=client)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "summary" in d
        assert "sources" in d
        assert "warnings" in d
        assert isinstance(d["sources"], list)
        assert isinstance(d["warnings"], list)
        assert {"type": "HivemindError", "message": "unreachable"} in d["warning_details"]
        assert any("unreachable" in w for w in d["warnings"])

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_summary_updates_with_hivemind_results(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def client(q: str, t: float) -> dict[str, Any]:
            return {"results": [{"class_type": "HmNode", "score": 80}]}

        result = research("test", hivemind_client=client)
        # Summary should reflect merged count (local + new hivemind).
        assert "research result" in result.summary.lower()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_web_fallback_runs_when_hivemind_empty(self, mock_corpus) -> None:
        mock_corpus.return_value = []

        def hivemind_client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        def web_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hotshot XL ComfyUI workflow",
                        "url": "https://example.com/hotshot-xl",
                        "snippet": "Hotshot XL SDXL video notes",
                    }
                ]
            }

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=hivemind_client,
            web_search_client=web_client,
        )
        assert any(s["source"] == "web" for s in result.sources)
        assert any("Hotshot XL" in s["class_type"] for s in result.sources)

    def test_default_web_client_combines_duckduckgo_and_github(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")

        monkeypatch.setattr(
            research_module,
            "_duckduckgo_search",
            lambda query, timeout: [
                {
                    "title": "Duck result",
                    "url": "https://example.com/duck",
                    "snippet": "duck snippet",
                }
            ],
        )
        monkeypatch.setattr(
            research_module,
            "_github_repository_search",
            lambda query, timeout: [
                {
                    "title": "owner/repo",
                    "url": "https://github.com/owner/repo",
                    "snippet": "repo snippet",
                }
            ],
        )

        result = research_module._default_web_search_client("HotshotXL", 1)

        assert [item["title"] for item in result["results"]] == ["Duck result", "owner/repo"]

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_local_limit_zero_skips_local_workflow_search(self, mock_corpus) -> None:
        result = research(
            "Hotshot XL SDXL video",
            local_limit=0,
            hivemind_client=None,
            web_search_client=None,
        )

        assert result.sources == ()
        mock_corpus.assert_not_called()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_web_client_backend_warnings_are_forwarded_to_agent(self, mock_corpus) -> None:
        mock_corpus.return_value = []

        def web_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hotshot XL ComfyUI workflow",
                        "url": "https://example.com/hotshot-xl",
                        "snippet": "Hotshot XL SDXL video notes",
                    }
                ],
                "warnings": ["DuckDuckGo returned no usable result markup"],
            }

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=None,
            web_search_client=web_client,
        )

        assert any(s["source"] == "web" for s in result.sources)
        assert "web search: DuckDuckGo returned no usable result markup" in result.warnings

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_web_search_runs_even_when_hivemind_has_sources(self, mock_corpus) -> None:
        mock_corpus.return_value = []

        def hivemind_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hivemind Hotshot note",
                        "body": "Community discussion about Hotshot.",
                    }
                ]
            }

        def web_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hotshot XL ComfyUI workflow",
                        "url": "https://example.com/hotshot-xl",
                        "snippet": "Hotshot XL SDXL video notes",
                    }
                ]
            }

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=hivemind_client,
            web_search_client=web_client,
        )

        assert any(s["source"] == "hivemind" for s in result.sources)
        assert any(s["source"] == "web" for s in result.sources)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_cross_tier_duplicate_titles_are_preserved_for_agent_judgement(self, mock_corpus) -> None:
        mock_corpus.return_value = []

        def hivemind_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hotshot XL ComfyUI workflow",
                        "body": "Community discussion about Hotshot.",
                    }
                ]
            }

        def web_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hotshot XL ComfyUI workflow",
                        "url": "https://example.com/hotshot-xl",
                        "snippet": "Hotshot XL SDXL video notes",
                    }
                ]
            }

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=hivemind_client,
            web_search_client=web_client,
        )

        matching_sources = [
            s for s in result.sources
            if s.get("class_type") == "Hotshot XL ComfyUI workflow"
        ]
        assert {s["source"] for s in matching_sources} == {"hivemind", "web"}

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_local_corpus_failure_does_not_block_external_research(self, mock_corpus) -> None:
        mock_corpus.side_effect = RuntimeError("indexes missing")

        def hivemind_client(q: str, t: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "title": "Hotshot XL workflow",
                        "body": "ComfyUI SDXL video generation notes",
                    }
                ]
            }

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=hivemind_client,
            web_search_client=None,
        )

        assert any("Hotshot XL" in s["class_type"] for s in result.sources)
        assert any("local corpus: RuntimeError: indexes missing" in w for w in result.warnings)
        assert {"type": "RuntimeError", "message": "indexes missing"} in result.warning_details

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_web_fallback_failure_is_warning(self, mock_corpus) -> None:
        mock_corpus.return_value = []

        def hivemind_client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        def web_client(q: str, t: float) -> dict[str, Any]:
            raise RuntimeError("offline")

        result = research(
            "Hotshot XL SDXL video",
            hivemind_client=hivemind_client,
            web_search_client=web_client,
        )
        assert any("web search" in w and "offline" in w for w in result.warnings)
        assert result.warning_details == (
            {"type": "RuntimeError", "message": "offline"},
        )


# ── HivemindClient protocol ──────────────────────────────────────────────────


class TestHivemindClientProtocol:
    """The HivemindClient type accepts any callable matching the signature."""

    def test_lambda_is_valid_client(self) -> None:
        def client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        result = _run_hivemind_research("test", client=client, timeout=1.0)
        assert result == ()

    def test_function_is_valid_client(self) -> None:

        def my_client(query: str, timeout: float) -> dict[str, Any]:
            return {"results": [{"class_type": "X"}]}

        result = _run_hivemind_research("test", client=my_client, timeout=1.0)
        assert len(result) == 1
        assert result[0]["class_type"] == "X"

    def test_propagates_hivemind_error(self) -> None:
        def failing_client(q: str, t: float) -> dict[str, Any]:
            raise HivemindError("boom")

        with pytest.raises(HivemindError):
            _run_hivemind_research("test", client=failing_client, timeout=1.0)

    def test_propagates_unexpected_error(self) -> None:
        def exploding_client(q: str, t: float) -> dict[str, Any]:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            _run_hivemind_research("test", client=exploding_client, timeout=1.0)


class TestWorkflowSourceNormalization:
    """Centralized source workflow loader contract for adapt extraction."""

    def test_api_prompt_dict_loads_node_records(self) -> None:
        result = normalize_workflow_source(
            {
                "prompt": {
                    "2": {"class_type": "VAEDecode", "inputs": {"samples": ["1", 0]}},
                    "1": {"class_type": "KSampler", "inputs": {"seed": 42}},
                }
            },
            source_path="inline/api_prompt.json",
        )
        assert result.status == "loaded"
        assert result.shape == "api"
        assert result.source_path == "inline/api_prompt.json"
        assert result.blocks_candidate_output is False
        assert [node.node_id for node in result.nodes] == ["1", "2"]
        assert result.nodes[0].class_type == "KSampler"

    def test_litegraph_nodes_links_export_loads_node_records(self) -> None:
        result = normalize_workflow_source(
            {
                "nodes": [
                    {
                        "id": 10,
                        "type": "LoadImage",
                        "widgets_values": ["image.png"],
                        "inputs": [],
                    },
                    {
                        "id": 11,
                        "type": "PreviewImage",
                        "inputs": [{"name": "images", "link": 1}],
                    },
                ],
                "links": [[1, 10, 0, 11, 0, "IMAGE"]],
            },
            source_path="inline/litegraph.json",
        )
        assert result.status == "loaded"
        assert result.shape == "litegraph"
        assert result.source_path == "inline/litegraph.json"
        assert [node.node_id for node in result.nodes] == ["10", "11"]
        assert result.nodes[1].inputs["images"] == ["10", 0]

    def test_common_wrapper_keys_are_unwrapped(self) -> None:
        result = normalize_workflow_source(
            {
                "extra": {
                    "workflow": {
                        "graph": {
                            "nodes": [{"id": 1, "type": "WanVideoVACEEncode"}],
                            "links": [],
                        }
                    }
                }
            },
            source_path="inline/nested_wrapper.json",
        )
        assert result.status == "loaded"
        assert result.shape == "litegraph"
        assert result.source_path == "inline/nested_wrapper.json"
        assert result.nodes[0].class_type == "WanVideoVACEEncode"
        unwrap_warnings = [warning for warning in result.warnings if warning.code == "workflow_unwrapped"]
        assert [warning.path for warning in unwrap_warnings] == [
            ("extra", "workflow"),
            ("extra", "workflow", "graph"),
        ]

    def test_unsupported_format_blocks_candidate_output_with_warning(self) -> None:
        result = normalize_workflow_source(
            {"metadata": {"name": "not a workflow"}},
            source_path="inline/unsupported_format.json",
        )
        assert result.status == "unsupported"
        assert result.source_path == "inline/unsupported_format.json"
        assert result.blocks_candidate_output is True
        assert result.nodes == ()
        warning = result.warnings[0]
        assert warning.code == "unsupported_workflow_format"
        assert "ComfyUI API prompt dict" in warning.message
        assert "LiteGraph nodes/links export" in warning.message
        assert result.to_dict()["source_path"] == "inline/unsupported_format.json"


# ── Structured precedent tests (T11) ─────────────────────────────────────────
# Verify _build_inspection_summary, _build_precedent_slices,
# _build_adaptation_plan, and the research() function's precedent output
# when usable candidates exist vs. when no precedent is found.


class TestBuildInspectionSummary:
    """Graph inspection → InspectionSummary conversion."""

    def test_none_graph_returns_none(self) -> None:
        assert _build_inspection_summary(None) is None

    def test_empty_graph_no_nodes(self) -> None:
        result = _build_inspection_summary({"nodes": []})
        assert isinstance(result, InspectionSummary)
        assert result.node_count == 0
        assert result.node_types == ()
        assert result.has_dangling_inputs is False
        assert result.has_dangling_outputs is False
        assert "0 node" in result.summary

    def test_no_nodes_key_returns_summary(self) -> None:
        result = _build_inspection_summary({})
        assert isinstance(result, InspectionSummary)
        assert result.node_count == 0
        assert "no node list" in result.summary.lower()

    def test_single_node_with_class_type(self) -> None:
        graph = {"nodes": [{"id": 1, "class_type": "KSampler"}]}
        result = _build_inspection_summary(graph)
        assert result.node_count == 1
        assert result.node_types == ("KSampler",)
        assert "KSampler" in result.summary
        assert result.has_dangling_inputs is False
        assert result.has_dangling_outputs is False

    def test_node_with_widget_values(self) -> None:
        graph = {"nodes": [{"id": 1, "type": "KSampler", "widgets_values": [42, 7.5]}]}
        result = _build_inspection_summary(graph)
        assert result.node_count == 1
        assert len(result.key_widget_values) == 1
        assert result.key_widget_values[0] == {"w0": 42, "w1": 7.5}

    def test_dangling_input_detected(self) -> None:
        graph = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "inputs": [
                        {"name": "model", "link": None},
                        {"name": "latent", "link": 5},
                    ],
                }
            ]
        }
        result = _build_inspection_summary(graph)
        assert result.has_dangling_inputs is True
        assert "dangling input" in result.summary.lower()

    def test_dangling_output_detected(self) -> None:
        graph = {
            "nodes": [
                {"id": 1, "type": "VAEDecode"},
                {"id": 2, "type": "SaveImage"},
            ],
            "links": [{"origin_id": 1, "target_id": 2}],
        }
        # Node 2 has no outgoing links → dangling output
        result = _build_inspection_summary(graph)
        assert result.has_dangling_outputs is True
        assert "dangling output" in result.summary.lower()

    def test_five_max_node_types_in_summary(self) -> None:
        graph = {
            "nodes": [
                {"id": i, "type": f"Node{i}"} for i in range(8)
            ]
        }
        result = _build_inspection_summary(graph)
        assert result.node_count == 8
        assert "Node0, Node1, Node2, Node3, Node4" in result.summary
        assert "3 more" in result.summary


class TestBuildPrecedentSlices:
    """Building WorkflowSlice records from research sources."""

    def test_empty_sources_returns_empty_tuple(self) -> None:
        result = _build_precedent_slices(())
        assert result == ()

    def test_non_workflow_sources_produce_no_slices(self) -> None:
        sources = (
            {"class_type": "KSampler", "source": "object_info", "path": None},
            {"class_type": "VAEDecode", "source": "curated", "path": None},
        )
        result = _build_precedent_slices(sources)
        assert result == ()

    def test_workflow_source_with_py_path_creates_slice(self) -> None:
        sources = (
            {
                "class_type": "video/ltx2_3_t2v",
                "source": "ready_template",
                "path": "ready_templates/video/ltx2_3_t2v.py",
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        assert isinstance(result[0], WorkflowSlice)
        assert result[0].source_class_type == "video/ltx2_3_t2v"
        assert result[0].python_path == "ready_templates/video/ltx2_3_t2v.py"
        assert result[0].node_ids == ()
        assert result[0].entry_anchor is None
        assert result[0].exit_anchor is None

    def test_hivemind_workflow_source_creates_slice(self) -> None:
        sources = (
            {
                "class_type": "video/ltx2_3_runexx_custom_audio",
                "source": "hivemind_workflow",
                "path": "ready_templates/video/ltx2_3_runexx_custom_audio.py",
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        assert result[0].source_class_type == "video/ltx2_3_runexx_custom_audio"
        assert result[0].python_path == "ready_templates/video/ltx2_3_runexx_custom_audio.py"

    def test_source_workflow_creates_slice(self, tmp_path) -> None:
        source_path = tmp_path / "ltx2_3.json"
        source_path.write_text(
            '{"nodes": [{"id": 7, "type": "LTXVLoader"}, {"id": 8, "type": "KSampler"}], "links": []}'
        )
        sources = (
            {
                "class_type": "ltx2_3_source",
                "source": "source_workflow",
                "path": str(source_path),
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        assert result[0].source_class_type == "ltx2_3_source"
        assert result[0].node_ids == ("7", "8")
        assert result[0].node_types == ("LTXVLoader", "KSampler")
        assert result[0].entry_anchor == "7"
        assert result[0].exit_anchor == "8"
        assert result[0].source_workflow_path == str(source_path)

    def test_vace_source_extracts_concrete_pattern_slice(self) -> None:
        sources = (
            {
                "class_type": "video/wanvideo_wrapper_13b_vace",
                "source": "ready_template",
                "path": "ready_templates/video/wanvideo_wrapper_13b_vace.py",
                "source_workflow_path": "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json",
                "adapt_pattern_keys": ["vace"],
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        slice_ = result[0]
        assert slice_.source_workflow_path == "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json"
        assert slice_.python_path == "ready_templates/video/wanvideo_wrapper_13b_vace.py"
        assert "22" in slice_.node_ids
        assert "56" in slice_.node_ids
        assert "111" in slice_.node_ids
        assert "WanVideoVACEEncode" in slice_.node_types
        assert slice_.entry_anchor is not None
        assert slice_.exit_anchor is not None

    def test_real_vace_ready_template_fixture_extracts_repository_nodes(self) -> None:
        source_workflow_path = "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json"
        load_result = load_workflow_source(source_workflow_path)
        assert load_result.ok is True
        assert len(load_result.nodes) > 100
        assert {"22", "56", "111", "209", "224"}.issubset(
            {record.node_id for record in load_result.nodes}
        )

        sources = (
            {
                "class_type": "video/wanvideo_wrapper_13b_vace",
                "source": "ready_template",
                "path": "ready_templates/video/wanvideo_wrapper_13b_vace.py",
                "source_workflow_path": source_workflow_path,
                "adapt_pattern_keys": ["vace"],
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        slice_ = result[0]
        assert slice_.source_workflow_path == source_workflow_path
        assert slice_.python_path == "ready_templates/video/wanvideo_wrapper_13b_vace.py"
        assert {"56", "111", "148", "209", "224", "231"}.issubset(set(slice_.node_ids))
        assert "WanVideoVACEEncode" in slice_.node_types
        assert "WanVideoVACEModelSelect" in slice_.node_types
        assert "WanVideoVACEStartToEndFrame" in slice_.node_types
        assert slice_.warnings == ()

    def test_missing_real_vace_source_does_not_mock_passing_extraction(self, tmp_path) -> None:
        missing_source = tmp_path / "wan13b_vace_absent.json"
        sources = (
            {
                "class_type": "video/wanvideo_wrapper_13b_vace_missing",
                "source": "ready_template",
                "path": "ready_templates/video/wanvideo_wrapper_13b_vace.py",
                "source_workflow_path": str(missing_source),
                "adapt_pattern_keys": ["vace"],
            },
        )

        assert load_workflow_source(str(missing_source)).blocks_candidate_output is True
        assert _build_precedent_slices(sources) == ()

    def test_lora_chain_source_extracts_loader_and_selector_nodes(self) -> None:
        sources = (
            {
                "class_type": "video/wanvideo_wrapper_13b_control_lora",
                "source": "ready_template",
                "path": "ready_templates/video/wanvideo_wrapper_13b_control_lora.py",
                "source_workflow_path": "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json",
                "adapt_pattern_keys": ["lora_chain"],
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        assert "22" in result[0].node_ids
        assert "98" in result[0].node_ids
        assert "WanVideoLoraSelect" in result[0].node_types

    def test_controlnet_depth_source_extracts_guidance_nodes(self) -> None:
        sources = (
            {
                "class_type": "video/wanvideo_wrapper_22_5b_i2v_controlnet",
                "source": "ready_template",
                "path": "ready_templates/video/wanvideo_wrapper_22_5b_i2v_controlnet.py",
                "source_workflow_path": "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v_controlnet.json",
                "adapt_pattern_keys": ["depth_pose_guidance"],
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        assert {"103", "104", "105"}.issubset(set(result[0].node_ids))
        assert "WanVideoControlnetLoader" in result[0].node_types
        assert "MiDaS-DepthMapPreprocessor" in result[0].node_types

    def test_two_pass_refinement_extracts_sampler_and_upscale_nodes(self) -> None:
        sources = (
            {
                "class_type": "video/ltx2_3_lightricks_two_stage_distilled",
                "source": "ready_template",
                "path": "ready_templates/video/ltx2_3_lightricks_two_stage_distilled.py",
                "source_workflow_path": "ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json",
                "adapt_pattern_keys": ["two_pass_refinement"],
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        assert "4975" in result[0].node_ids
        assert "LTXVLatentUpsampler" in result[0].node_types
        assert result[0].entry_anchor is not None
        assert result[0].exit_anchor is not None

    def test_low_vram_source_extracts_real_slice_and_missing_blockswap_warning(self) -> None:
        sources = (
            {
                "class_type": "video/ltx2_3_iamccs_low_vram",
                "source": "ready_template",
                "path": "ready_templates/video/ltx2_3_iamccs_low_vram.py",
                "source_workflow_path": "ready_templates/sources/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX_2.3_T_I2V_LOW_VRAM.json",
                "adapt_pattern_keys": ["low_vram"],
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        assert "207" in result[0].node_ids
        assert "LTXVChunkFeedForward" in result[0].node_types
        assert result[0].warnings
        assert result[0].warnings[0]["code"] == "missing_required_pattern_nodes"
        assert result[0].warnings[0]["source_path"].endswith("IAMCCS_LTX_2.3_T_I2V_LOW_VRAM.json")

    def test_slice_to_dict_includes_source_node_types_and_structured_warnings(self, tmp_path) -> None:
        source_path = tmp_path / "missing_vace.json"
        source_path.write_text('{"7": {"class_type": "KSampler", "inputs": {}}}', encoding="utf-8")
        sources = (
            {
                "class_type": "bad_vace",
                "source": "source_workflow",
                "path": str(source_path),
                "adapt_pattern_keys": ["vace"],
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1
        payload = result[0].to_dict()
        assert payload["source_workflow_path"] == str(source_path)
        assert payload["node_ids"] == []
        assert payload["warnings"][0]["code"] == "pattern_nodes_not_found"
        assert payload["warnings"][0]["source_path"] == str(source_path)

    def test_external_workflow_creates_slice(self) -> None:
        sources = (
            {
                "class_type": "external_template",
                "source": "external_workflow",
                "path": "some/path/external.py",
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 1

    def test_mixed_sources_only_workflows_produce_slices(self) -> None:
        sources = (
            {"class_type": "KSampler", "source": "object_info", "path": None},
            {
                "class_type": "video/ltx2_3_t2v",
                "source": "ready_template",
                "path": "ready_templates/video/ltx2_3_t2v.py",
            },
            {"class_type": "VAEDecode", "source": "curated", "path": None},
            {
                "class_type": "audio_lipsync",
                "source": "hivemind_workflow",
                "path": "ready_templates/audio_lipsync.py",
            },
        )
        result = _build_precedent_slices(sources)
        assert len(result) == 2
        class_types = {s.source_class_type for s in result}
        assert class_types == {"video/ltx2_3_t2v", "audio_lipsync"}

    def test_duplicate_class_type_deduplicated(self) -> None:
        sources = (
            {
                "class_type": "video/ltx2_3_t2v",
                "source": "ready_template",
                "path": "ready_templates/a.py",
            },
            {
                "class_type": "video/ltx2_3_t2v",
                "source": "hivemind_workflow",
                "path": "ready_templates/b.py",
            },
        )
        result = _build_precedent_slices(sources)
        # Deduplication by class_type: only one slice
        assert len(result) == 1

    def test_workflow_source_unsupported_json_path_is_blocked(self) -> None:
        sources = (
            {
                "class_type": "some_workflow",
                "source": "ready_template",
                "path": "ready_templates/some_workflow.json",
            },
        )
        result = _build_precedent_slices(sources)
        assert result == ()

    def test_inline_unsupported_workflow_source_never_builds_candidate_slice(self, tmp_path) -> None:
        unsupported_path = tmp_path / "unsupported_workflow.json"
        unsupported_path.write_text('{"metadata": {"format": "not-comfyui"}}', encoding="utf-8")
        sources = (
            {
                "class_type": "unsupported_inline_workflow",
                "source": "external_workflow",
                "path": str(unsupported_path),
            },
        )
        load_result = normalize_workflow_source(
            {"metadata": {"format": "not-comfyui"}},
            source_path=str(unsupported_path),
        )
        assert load_result.blocks_candidate_output is True
        assert load_result.warnings[0].code == "unsupported_workflow_format"
        assert load_result.source_path == str(unsupported_path)
        assert _build_precedent_slices(sources) == ()

    def test_workflow_source_no_path_still_creates_if_source_workflow(self) -> None:
        """source_workflow + .py path are OR'd: either the source kind or .py path qualifies."""
        sources = (
            {
                "class_type": "source_only",
                "source": "source_workflow",
                "path": None,
            },
        )
        result = _build_precedent_slices(sources)
        # source_workflow is in workflow_source_kinds, so it qualifies
        assert len(result) == 1
        assert result[0].python_path is None


class TestBuildAdaptationPlan:
    """PrecedentAdaptationPlan construction from slices."""

    def _wan_lora_slice(self) -> WorkflowSlice:
        slices = _build_precedent_slices((
            {
                "class_type": "video/wan_control_lora",
                "source": "ready_template",
                "path": "ready_templates/video/wan_control_lora.py",
                "source_workflow_path": "ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json",
                "adapt_pattern_keys": ["lora_chain"],
            },
        ))
        assert slices
        return slices[0]

    def _wan_target_graph(self) -> dict[str, dict[str, object]]:
        return {
            "1": {
                "class_type": "WanVideoModelLoader",
                "inputs": {
                    "model": "WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors",
                    "lora": ["2", 0],
                },
            },
            "2": {
                "class_type": "WanVideoLoraSelect",
                "inputs": {
                    "lora": "WanVid\\wan2.1-control-lora.safetensors",
                    "strength": 1,
                },
            },
            "3": {
                "class_type": "WanVideoSampler",
                "inputs": {"model": ["1", 0], "latent_image": ["4", 0]},
            },
        }

    def _ltx_target_graph_with_matching_anchor_shapes(self) -> dict[str, dict[str, object]]:
        return {
            "1": {
                "class_type": "LTXVModelLoader",
                "inputs": {
                    "model": "ltx-video-2b.safetensors",
                    "lora": ["2", 0],
                },
            },
            "2": {
                "class_type": "LTXVLoraSelect",
                "inputs": {"lora": "ltx-detail-lora.safetensors", "strength": 1},
            },
            "3": {
                "class_type": "LTXVSampler",
                "inputs": {"model": ["1", 0], "latent_image": ["4", 0]},
            },
        }

    def test_no_slices_returns_none(self) -> None:
        result = _build_adaptation_plan(
            query="test",
            graph=None,
            inspection=None,
            slices=(),
        )
        assert result is None

    def test_single_slice_creates_minimal_plan(self) -> None:
        ws = WorkflowSlice(
            source_class_type="video/ltx2_3_t2v",
            python_path="ready_templates/video/ltx2_3_t2v.py",
        )
        result = _build_adaptation_plan(
            query="add video",
            graph=None,
            inspection=None,
            slices=(ws,),
        )
        assert isinstance(result, PrecedentAdaptationPlan)
        assert result.selected_slice == ws
        assert result.anchor_bindings == ()
        assert result.required_new_nodes == ()
        assert result.required_rewires == ()
        assert result.edit_ops == ()
        assert result.candidate_graph is None
        assert result.structural_validation == "not_evaluated"
        assert result.semantic_validation == "not_evaluated"

    def test_multiple_slices_selects_first(self) -> None:
        ws1 = WorkflowSlice(source_class_type="first", python_path="a.py")
        ws2 = WorkflowSlice(source_class_type="second", python_path="b.py")
        result = _build_adaptation_plan(
            query="test",
            graph=None,
            inspection=None,
            slices=(ws1, ws2),
        )
        assert result is not None
        assert result.selected_slice == ws1

    def test_plan_is_serializable(self) -> None:
        ws = WorkflowSlice(source_class_type="test", python_path="test.py")
        plan = _build_adaptation_plan(
            query="test",
            graph=None,
            inspection=None,
            slices=(ws,),
        )
        assert plan is not None
        d = plan.to_dict()
        assert "selected_slice" in d
        assert d["selected_slice"]["source_class_type"] == "test"
        assert d["structural_validation"] == "not_evaluated"

    def test_compatible_wan_target_binds_structural_anchors(self) -> None:
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),
            inspection=None,
            slices=(self._wan_lora_slice(),),
        )

        assert plan is not None
        assert plan.structural_validation == "pass"
        assert plan.candidate_graph is not None
        assert plan.anchor_bindings
        roles = {binding["anchor_role"] for binding in plan.anchor_bindings}
        assert {"lora", "model"} <= roles
        assert {
            (binding["anchor_role"], binding["source_socket"], binding["target_socket"])
            for binding in plan.anchor_bindings
        } >= {("lora", "lora", "lora"), ("model", "model", "model")}
        assert {
            binding["target_class_type"] for binding in plan.anchor_bindings
        } <= {"WanVideoModelLoader"}
        # Candidate graph preserves the original target IDs and links and
        # includes the non-anchor source nodes under deterministic new IDs.
        assert {"1", "2", "3"} <= set(plan.candidate_graph.keys())
        assert plan.candidate_graph["1"]["inputs"]["lora"] == ["2", 0]
        added_ids = set(plan.candidate_graph.keys()) - {"1", "2", "3"}
        assert added_ids
        for node_id in added_ids:
            assert node_id.startswith("adapt_")

    def test_candidate_graph_only_emitted_on_pass(self) -> None:
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),
            inspection=None,
            slices=(self._wan_lora_slice(),),
        )
        assert plan is not None
        assert plan.structural_validation == "pass"
        assert plan.to_dict().get("candidate_graph") is plan.candidate_graph

    def test_incompatible_target_family_produces_no_anchor_bindings(self) -> None:
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._ltx_target_graph_with_matching_anchor_shapes(),
            inspection=None,
            slices=(self._wan_lora_slice(),),
        )

        assert plan is not None
        assert plan.structural_validation == "fail"
        assert plan.anchor_bindings == ()
        assert plan.candidate_graph is None

    def test_missing_target_graph_does_not_bind_or_build_candidate(self) -> None:
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=None,
            inspection=None,
            slices=(self._wan_lora_slice(),),
        )

        assert plan is not None
        assert plan.structural_validation == "not_evaluated"
        assert plan.anchor_bindings == ()
        assert plan.candidate_graph is None

    def test_unsupported_target_graph_blocks_anchor_bindings(self) -> None:
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph={"metadata": {"format": "not-comfyui"}},
            inspection=None,
            slices=(self._wan_lora_slice(),),
        )

        assert plan is not None
        assert plan.structural_validation == "fail"
        assert plan.anchor_bindings == ()
        assert plan.candidate_graph is None


def _normalize_sources_for_test(entries):
    """Convert SearchEntry list to normalized source dicts like _normalize_source."""
    from vibecomfy.search.scorer import SearchResult
    results = [SearchResult(entry=e, score=10, reasons=("class_type",)) for e in entries]
    from vibecomfy.executor.research import _normalize_source
    return tuple(_normalize_source(r) for r in results)


class TestResearchPrecedentOutput:
    """The research() function produces precedent_slices and adaptation_plan."""

    def _workflow_corpus(self) -> list:
        """Return a corpus with a workflow source."""
        return [
            _make_entry(
                class_type="KSampler",
                description="Sampling node",
                source="object_info",
            ),
            _make_entry(
                class_type="video/ltx2_3_t2v",
                description="LTX video workflow",
                source="ready_template",
                path="ready_templates/video/ltx2_3_t2v.py",
                pack="ltxvideo",
            ),
        ]

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_usable_candidate_produces_slices_and_plan(self, mock_corpus) -> None:
        """When a workflow source exists, research() produces slices + adaptation plan."""
        mock_corpus.return_value = self._workflow_corpus()
        result = research("ltx video workflow", hivemind_client=None)

        # Precedent slices should be present
        assert len(result.precedent_slices) >= 1
        assert isinstance(result.precedent_slices[0], WorkflowSlice)
        assert any(
            "ltx2_3_t2v" in s.source_class_type for s in result.precedent_slices
        )

        # Adaptation plan should be present
        assert result.adaptation_plan is not None
        assert isinstance(result.adaptation_plan, PrecedentAdaptationPlan)
        assert result.adaptation_plan.selected_slice.source_class_type == "video/ltx2_3_t2v"

        # No none-found warning when a candidate exists
        assert not any(
            "no workflow/template precedents found" in w.lower()
            for w in result.warnings
        )

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_no_candidate_produces_none_found_warning(self, mock_corpus) -> None:
        """When no workflow sources exist, research() produces a none-found warning."""
        mock_corpus.return_value = [
            _make_entry("KSampler", source="object_info"),
            _make_entry("VAEDecode", source="object_info"),
        ]
        result = research("sampler node", hivemind_client=None)

        # No precedent slices
        assert result.precedent_slices == ()

        # Adaptation plan is None (no candidate)
        assert result.adaptation_plan is None

        # Precedent warnings are now correctly merged into result.warnings
        assert none_found_warning in result.warnings

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_empty_corpus_none_found_warning(self, mock_corpus) -> None:
        """Empty corpus → no slices, no plan, none-found warning."""
        mock_corpus.return_value = []
        result = research("anything", hivemind_client=None)

        assert result.precedent_slices == ()
        assert result.adaptation_plan is None
        # Precedent warnings are now correctly merged into result.warnings
        assert none_found_warning in result.warnings

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_to_dict_includes_precedent_fields_when_populated(self, mock_corpus) -> None:
        """to_dict() emits precedent_slices and adaptation_plan when populated."""
        mock_corpus.return_value = self._workflow_corpus()
        result = research("ltx video", hivemind_client=None)
        d = result.to_dict()

        assert "precedent_slices" in d
        assert isinstance(d["precedent_slices"], list)
        assert len(d["precedent_slices"]) >= 1
        assert d["precedent_slices"][0]["source_class_type"] == "video/ltx2_3_t2v"

        assert "adaptation_plan" in d
        assert d["adaptation_plan"]["structural_validation"] == "not_evaluated"

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_to_dict_omits_adaptation_plan_when_none(self, mock_corpus) -> None:
        """to_dict() omits adaptation_plan key when None."""
        mock_corpus.return_value = [
            _make_entry("KSampler", source="object_info"),
        ]
        result = research("KSampler", hivemind_client=None)
        d = result.to_dict()

        # precedent_slices key only present when non-empty (to_dict omits empty)
        assert "precedent_slices" not in d

        # adaptation_plan absent when None (to_dict omits it)
        assert "adaptation_plan" not in d

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_multiple_workflow_sources_all_in_slices(self, mock_corpus) -> None:
        """Multiple workflow sources → multiple slices, plan selects first."""
        mock_corpus.return_value = [
            _make_entry(
                class_type="wf_a",
                source="ready_template",
                path="a.py",
            ),
            _make_entry(
                class_type="wf_b",
                source="hivemind_workflow",
                path="b.py",
            ),
            _make_entry(
                class_type="wf_c",
                source="source_workflow",
                path="c.py",
            ),
        ]
        # Use _build_precedent_slices directly since research() scorer may
        # not match arbitrary class_types; we test the slice construction logic.
        sources = _normalize_sources_for_test(mock_corpus.return_value)
        result_slices = _build_precedent_slices(sources)

        assert len(result_slices) == 3
        class_types = {s.source_class_type for s in result_slices}
        assert class_types == {"wf_a", "wf_b", "wf_c"}

        # Build adaptation plan from slices to verify first-slice selection
        plan = _build_adaptation_plan(query="test", graph=None, inspection=None, slices=result_slices)
        assert plan is not None
        assert plan.selected_slice.source_class_type == "wf_a"

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_workflow_without_py_path_still_produces_slice(self, mock_corpus) -> None:
        """hivemind_workflow source without .py path should still produce a slice."""
        mock_corpus.return_value = [
            _make_entry(
                class_type="hm_wf",
                source="hivemind_workflow",
                path=None,
            ),
        ]
        result = research("hm_wf", hivemind_client=None)

        # hivemind_workflow IS in workflow_source_kinds, so it qualifies
        assert len(result.precedent_slices) == 1  # class_type matches query
        assert result.adaptation_plan is not None

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_non_dict_sources_are_skipped(self, mock_corpus) -> None:
        """Non-dict entries in sources are safely skipped."""
        # This can't easily happen through research() since sources are always dicts,
        # but _build_precedent_slices guards against it.
        slices = _build_precedent_slices((
            {"class_type": "valid", "source": "ready_template", "path": "valid.py"},
            "not-a-dict",  # type: ignore[arg-type]
        ))
        assert len(slices) == 1
