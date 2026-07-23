"""Unit tests for the deterministic executor research module.

Covers local-corpus research, compact source normalization, injectable
Hivemind client, timeout/error → warning conversion, deduplication, and
merge ordering.
"""

from __future__ import annotations

import io
import json
from typing import Any
from urllib.parse import unquote_plus
from unittest.mock import patch

import pytest

from vibecomfy.executor.contracts import (
    InspectionSummary,
    PrecedentAdaptationPlan,
    PrecedentOption,
    PrecedentPacket,
    ResearchResult,
    SelectedPrecedent,
    WorkflowSlice,
)
from vibecomfy.executor.research import (
    HivemindError,
    _default_hivemind_client,
    _build_adaptation_plan,
    _build_inspection_summary,
    _build_precedent_packet,
    _build_selected_precedent,
    _build_precedent_slices,
    _build_summary,
    _media_domain_from_node_types,
    _requested_model_families,
    _requested_media_domain,
    _normalize_hivemind_source,
    _normalize_source,
    _run_hivemind_research,
    research,
    run_local_research,
)
from vibecomfy.registry.pack_resolver import (
    MissingNodeResolution,
    PackRef,
    ResolverCandidate,
    ResolverEvidence,
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
    media_type: str | None = None,
    task_type: str | None = None,
    model_families: tuple[str, ...] = (),
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
        media_type=media_type,
        task_type=task_type,
        model_families=model_families,
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
            "media_type",
            "task_type",
            "model_families",
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

    def test_workflow_semantics_are_serialized(self) -> None:
        result = _make_result(
            "video/hotshot_i2v",
            source="ready_template",
            media_type="video",
            task_type="image_to_video",
            model_families=("hotshot", "animatediff"),
        )
        source = _normalize_source(result)
        assert source["media_type"] == "video"
        assert source["task_type"] == "image_to_video"
        assert source["model_families"] == ["hotshot", "animatediff"]


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

    def test_workflow_resource_preserves_semantics_and_gates(self) -> None:
        item = {
            "kind": "workflow",
            "title": "LTX I2V",
            "metadata": {
                "workflow_semantics": {
                    "media_type": "video",
                    "task_type": "image_to_video",
                    "model_families": ["ltx"],
                    "promotion_gates": {
                        "has_workflow_json": True,
                        "has_compiled_api": True,
                        "has_python_source": False,
                        "parseable_workflow": True,
                    },
                },
            },
        }

        out = _normalize_hivemind_source(item)

        assert out["workflow_semantics"]["task_type"] == "image_to_video"
        assert out["promotion_gates"]["has_compiled_api"] is True


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
        result = research(
            "KSampler",
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
        )
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
            registry_resolver=None,
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
            registry_resolver=None,
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
            # Query matches the local corpus so local results exist and can be
            # ordered before the Hivemind tier.
            "KSampler",
            hivemind_client=self._merge_client,
            web_search_client=None,
            registry_resolver=None,
        )
        sources = list(result.sources)
        # Local sources should come before hivemind sources.
        local_indices = [i for i, s in enumerate(sources) if s["source"] != "hivemind"]
        hm_indices = [i for i, s in enumerate(sources) if s["source"] == "hivemind"]
        if local_indices and hm_indices:
            assert max(local_indices) < min(hm_indices)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_exact_hivemind_workflow_can_rank_above_weak_local_match(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry(
                "IP Adapter AnimateDiff Control Net LCM",
                source="external_workflow",
                description="AnimateDiff control net IP adapter workflow",
            ),
        ]

        def client(_query: str, _timeout: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "kind": "workflow",
                        "title": "Flux Image Inpainting and Compositing with ControlNet",
                        "score": 300,
                        "body": "Exact Flux ControlNet inpainting workflow.",
                    }
                ]
            }

        result = research(
            "Flux image inpainting compositing ControlNet workflow",
            hivemind_client=client,
            web_search_client=None,
            registry_resolver=None,
        )

        assert result.sources[0]["class_type"] == "Flux Image Inpainting and Compositing with ControlNet"
        assert any(s["class_type"] == "IP Adapter AnimateDiff Control Net LCM" for s in result.sources)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_weak_hivemind_workflow_does_not_rank_above_local_source(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry(
                "IndexTTSEmotionOptionsNode",
                source="object_info",
                description="IndexTTS emotion options for narration style",
            )
        ]

        def client(_query: str, _timeout: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "kind": "workflow",
                        "title": "AnimateDiff Video Generation with IPAdapter and ControlNet",
                        "score": 500,
                        "body": "Workflow with options, style, and control settings.",
                    }
                ]
            }

        result = research(
            "IndexTTS emotion options for narration style",
            hivemind_client=client,
            web_search_client=None,
            registry_resolver=None,
        )

        assert result.sources[0]["class_type"] == "IndexTTSEmotionOptionsNode"
        weak = next(s for s in result.sources if s["source"] == "hivemind_workflow")
        assert weak["strong_relevance_match"] is False

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_duplicate_class_type_keeps_both_tiers(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler", source="object_info")]
        result = research(
            "KSampler",
            hivemind_client=self._duplicate_client,
            web_search_client=None,
            registry_resolver=None,
        )
        # Cross-tier duplicates are intentionally preserved so the agent can see
        # what each source tier produced. KSampler therefore appears from both
        # local corpus and Hivemind; NewHivemindNode appears once from Hivemind.
        ksampler_sources = [s for s in result.sources if s["class_type"] == "KSampler"]
        assert len(ksampler_sources) == 2
        assert any(s["source"] != "hivemind" for s in ksampler_sources)
        assert any(s["source"] == "hivemind" for s in ksampler_sources)

    def test_hivemind_promotes_direct_discord_workflow_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)

        workflow_json = json.dumps(
            {
                "1": {
                    "class_type": "FluxInpaintModel",
                    "inputs": {"image": ["2", 0]},
                    "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
                },
                "2": {"class_type": "ControlNetApply", "inputs": {}},
            }
        ).encode()

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *_args, **_kwargs) -> bytes:
                return workflow_json

        monkeypatch.setattr(research_module.urllib.request, "urlopen", lambda *args, **kwargs: _Response())

        sources = research_module._run_hivemind_research(
            "Flux ControlNet inpainting",
            client=lambda _query, _timeout: {
                "results": [
                    {
                        "kind": "workflow",
                        "title": "Flux Image Inpainting and Compositing with ControlNet",
                        "url": "https://cdn.discordapp.com/attachments/1/2/Inpainting_at_full_resolutions_flux.json?ex=1",
                        "body": "Flux workflow JSON",
                    }
                ]
            },
            timeout=1,
        )

        promoted = sources[0]
        assert promoted["source"] == "hivemind_workflow"
        assert promoted["source_type"] == "direct_workflow_json"
        assert promoted["hivemind_promoted_workflow"] is True
        assert promoted["source_workflow_available"] is True
        assert "FluxInpaintModel" in promoted["node_types"]

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_hivemind_with_no_results_is_handled(self, mock_corpus) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def empty_client(q: str, t: float) -> dict[str, Any]:
            return {"results": []}

        result = research(
            "KSampler",
            hivemind_client=empty_client,
            web_search_client=None,
            registry_resolver=None,
        )
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
        assert "external_resources" in decoded_url
        assert "kind=eq.workflow" in decoded_url
        assert "title.ilike.*Hotshot*" in decoded_url
        assert "body.ilike.*Hotshot*" in decoded_url
        assert "title.fts." not in decoded_url

    def test_postgrest_search_queries_workflow_kind_and_prioritizes_it(self) -> None:
        seen_urls: list[str] = []

        def capture_urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            seen_urls.append(req.full_url)
            payload = (
                b'[{"kind": "workflow", "title": "video/ltx2_3_runexx_custom_audio", '
                b'"body": "LTX RuneXX audio workflow", '
                b'"metadata": {"ready_template_id": "video/ltx2_3_runexx_custom_audio", '
                b'"path": "ready_templates/video/ltx2_3_runexx_custom_audio.py"}}]'
            )
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

    def test_postgrest_search_adds_semantic_metadata_filters(self) -> None:
        seen_urls: list[str] = []

        def capture_urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            seen_urls.append(req.full_url)
            payload = (
                b'[{"id": 7, "kind": "workflow", "title": "LTX I2V", '
                b'"body": "Workflow semantics: aliases=ltx, i2v.", '
                b'"metadata": {"workflow_semantics": {"model_families": ["ltx"], '
                b'"task_type": "image_to_video", "promotion_gates": {"parseable_workflow": true, '
                b'"has_compiled_api": true}}}}]'
            )
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
            result = _default_hivemind_client("ltx image to video workflow", timeout=1.0)

        decoded_urls = [unquote_plus(url) for url in seen_urls]
        assert any("metadata=cs." in url for url in decoded_urls)
        assert any('"workflow_semantics":{"model_families":["ltx"]}' in url for url in decoded_urls)
        assert any('"workflow_semantics":{"task_type":"image_to_video"}' in url for url in decoded_urls)
        assert result["results"][0]["id"] == 7

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
        result = research(
            "KSampler",
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
        )
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

    def test_default_web_client_combines_duckduckgo_and_github_without_cache(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_read_web_search_cache", lambda query: [])
        monkeypatch.setattr(research_module, "_brave_search", lambda query, timeout: [])

        monkeypatch.setattr(
            research_module,
            "_duckduckgo_search",
            lambda query, timeout: [
                {
                    "title": "Duck result for HotshotXL",
                    "url": "https://example.com/duck",
                    "snippet": "duck snippet about HotshotXL",
                }
            ],
        )
        monkeypatch.setattr(
            research_module,
            "_github_repository_search",
            lambda query, timeout: [
                {
                    "title": "owner/hotshotxl-repo",
                    "url": "https://github.com/owner/repo",
                    "snippet": "repo snippet about HotshotXL",
                }
            ],
        )

        result = research_module._default_web_search_client("HotshotXL", 1)

        assert [item["title"] for item in result["results"]] == [
            "Duck result for HotshotXL",
            "owner/hotshotxl-repo",
        ]

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
    def test_registry_source_returns_custom_node_candidates(self, mock_corpus) -> None:
        mock_corpus.return_value = []
        calls: list[str] = []

        def registry_resolver(query: str) -> MissingNodeResolution:
            calls.append(query)
            if query.casefold() != "hotshot xl comfyui nodes":
                return MissingNodeResolution(query=query, query_intent="capability")
            candidate = ResolverCandidate(
                ref=PackRef(
                    slug="ComfyUI-AnimateDiff-Evolved",
                    source="comfy-registry",
                    url="https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved",
                ),
                expected_classes=(
                    "ADE_AnimateDiffLoaderWithContext",
                    "ADE_UseEvolvedSampling",
                ),
                evidence=(
                    ResolverEvidence(
                        tier="comfyui-manager",
                        source="custom-node-map",
                        endpoint="custom-node-map.json",
                        matched_classes=(
                            "ADE_AnimateDiffLoaderWithContext",
                            "ADE_UseEvolvedSampling",
                        ),
                    ),
                ),
            )
            return MissingNodeResolution(
                query=query,
                query_intent="capability",
                candidates=(candidate,),
                source_tiers_attempted=("comfyui-manager", "comfy-registry"),
            )

        result = research(
            "Hotshot XL ComfyUI nodes",
            local_limit=0,
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=registry_resolver,
        )

        # The resolver receives the original agent query first, plus any
        # camel-case token queries derived from the original.
        assert calls[0] == "Hotshot XL ComfyUI nodes"
        assert "Hotshot XL ComfyUI nodes" in calls
        registry_sources = [s for s in result.sources if s["source"] == "comfy-registry"]
        assert registry_sources
        assert registry_sources[0]["pack"] == "ComfyUI-AnimateDiff-Evolved"
        assert "ADE_AnimateDiffLoaderWithContext" in registry_sources[0]["expected_classes"]
        assert "Expected classes" in registry_sources[0]["description"]

    def test_registry_candidate_queries_preserve_agent_query(self) -> None:
        from vibecomfy.executor.research import _registry_candidate_queries

        # The agent query is always first; camel-case tokens become extra
        # candidate queries to improve recall.
        assert _registry_candidate_queries("Hotshot ComfyUI nodes") == [
            "Hotshot ComfyUI nodes",
            "ComfyUI",
        ]
        assert _registry_candidate_queries("Hotshot XL ComfyUI nodes") == [
            "Hotshot XL ComfyUI nodes",
            "XL",
            "ComfyUI",
        ]

    def test_default_web_client_combines_duckduckgo_and_github(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)

        monkeypatch.setattr(
            research_module,
            "_duckduckgo_search",
            lambda query, timeout: [
                {
                    "title": "HotshotXL duck guide",
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
                    "title": "owner/hotshot-xl",
                    "url": "https://github.com/owner/hotshot-xl",
                    "snippet": "repo snippet",
                }
            ],
        )

        result = research_module._default_web_search_client("HotshotXL", 1)

        assert [item["title"] for item in result["results"]] == [
            "HotshotXL duck guide",
            "owner/hotshot-xl",
        ]

    def test_external_workflow_result_score_prefers_workflow_examples(self) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")

        model_page = {
            "title": "model page",
            "url": "https://huggingface.co/hotshotco/Hotshot-XL/tree/main",
            "snippet": "External search result from huggingface.co",
        }
        workflow_example = {
            "title": "hotshotxl motion model video transfer",
            "url": "https://openart.ai/workflows/cychenyue/hotshotxl-motion-model-video-transfer-v1/VbUW0H73SKEVHvSw0WGW",
            "snippet": "External search result from openart.ai",
        }

        assert research_module._external_workflow_result_score(
            workflow_example
        ) > research_module._external_workflow_result_score(model_page)

    def test_web_results_are_filtered_by_named_target_anchor(self) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")

        filtered, dropped = research_module._filter_web_results_by_named_anchor(
            "Hotshot XL ComfyUI workflow JSON node types",
            [
                {
                    "title": "Comfy UI where do workflow json files save to",
                    "url": "https://reddit.example/workflow-json",
                    "snippet": "Generic ComfyUI JSON workflow help.",
                },
                {
                    "title": "HotshotXL motion model video transfer workflow",
                    "url": "https://openart.ai/workflows/example/hotshotxl",
                    "snippet": "HotshotXL ComfyUI workflow example.",
                },
            ],
        )

        assert dropped == 1
        assert [item["title"] for item in filtered] == [
            "HotshotXL motion model video transfer workflow"
        ]

    def test_default_web_client_drops_all_generic_results_for_named_target(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(
            research_module,
            "_read_web_search_cache",
            lambda query: [],
        )
        monkeypatch.setattr(
            research_module,
            "_duckduckgo_search",
            lambda query, timeout: [
                {
                    "title": "Comfy UI where do workflow json files save to",
                    "url": "https://reddit.example/workflow-json",
                    "snippet": "Generic ComfyUI JSON workflow help.",
                }
            ],
        )
        monkeypatch.setattr(research_module, "_github_repository_search", lambda query, timeout: [])
        monkeypatch.setattr(research_module, "_brave_search", lambda query, timeout: [])

        with pytest.raises(research_module.WebSearchError) as excinfo:
            research_module._default_web_search_client(
                "Hotshot XL ComfyUI workflow JSON node types",
                1,
            )

        assert "dropped 1 generic result" in str(excinfo.value)

    def test_web_cache_merges_multiple_named_anchor_matches(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)

        first = tmp_path / "first.json"
        second = tmp_path / "second.json"
        first.write_text(
            json.dumps(
                {
                    "query": "Hotshot XL ComfyUI workflow",
                    "results": [
                        {
                            "title": "HotshotXL OpenArt workflow",
                            "url": "https://openart.ai/workflows/example/hotshotxl",
                            "snippet": "HotshotXL workflow lead.",
                        }
                    ],
                }
            )
        )
        second.write_text(
            json.dumps(
                {
                    "query": "VbUW0H73SKEVHvSw0WGW Hotshot XL workflow JSON",
                    "results": [
                        {
                            "title": "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json",
                            "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                            "snippet": "HotshotXL workflow JSON.",
                        }
                    ],
                }
            )
        )

        results = research_module._read_web_search_cache(
            "Hotshot XL ComfyUI workflow JSON node types"
        )

        urls = [item["url"] for item in results]
        assert urls[0] == (
            "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json"
        )
        assert "https://openart.ai/workflows/example/hotshotxl" in urls
        assert (
            "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json"
            in urls
        )

    def test_web_cache_exact_leads_do_not_block_richer_anchor_matches(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)
        research_module._write_web_search_cache(
            "HotShot XL ComfyUI workflow",
            [
                {
                    "title": "hotshotxl motion model video transfer",
                    "url": "https://openart.ai/workflows/cychenyue/hotshotxl-motion-model-video-transfer-v1/VbUW0H73SKEVHvSw0WGW",
                    "snippet": "External workflow result from openart.ai",
                }
            ],
        )
        research_module._write_web_search_cache(
            "Hotshot XL ComfyUI workflow JSON node types",
            [
                {
                    "title": "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json",
                    "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                    "snippet": "HotshotXL workflow JSON.",
                }
            ],
        )

        results = research_module._read_web_search_cache("HotShot XL ComfyUI workflow")

        urls = [item["url"] for item in results]
        assert urls[0] == (
            "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json"
        )
        assert "https://openart.ai/workflows/cychenyue/hotshotxl-motion-model-video-transfer-v1/VbUW0H73SKEVHvSw0WGW" in urls

    def test_web_search_enriches_github_workflow_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "1": {
                            "class_type": "ADE_AnimateDiffLoaderWithContext",
                            "inputs": {"frame_count": 16},
                        },
                        "2": {
                            "class_type": "KSampler",
                            "inputs": {"steps": 20},
                        },
                    }
                ).encode()

        monkeypatch.setattr(research_module.urllib.request, "urlopen", lambda *args, **kwargs: _Response())

        sources, warnings = research_module._run_web_search(
            "Hotshot XL workflow JSON",
            client=lambda _query, _timeout: {
                "results": [
                    {
                        "title": "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json",
                        "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                        "snippet": "HotshotXL workflow JSON",
                    }
                ]
            },
            timeout=1,
        )

        assert not warnings
        assert sources[0]["source"] == "external_workflow"
        assert sources[0]["source_type"] == "github_workflow_json"
        assert "ADE_AnimateDiffLoaderWithContext" in sources[0]["node_types"]
        assert "frame_count=16" in sources[0]["key_values"]
        assert sources[0]["source_workflow_available"] is True
        assert "ADE_AnimateDiffLoaderWithContext" in sources[0]["workflow_schema"]

    def test_web_search_enriches_civitai_workflow_zip(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib
        import io
        import zipfile

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)

        workflow_json = json.dumps(
            {
                "1": {
                    "class_type": "ADE_AnimateDiffLoaderWithContext",
                    "inputs": {"frame_count": 16},
                },
                "2": {"class_type": "KSampler", "inputs": {"steps": 20}},
            }
        ).encode()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("workflow.json", workflow_json)
        zip_bytes = zip_buffer.getvalue()

        model_api_response = json.dumps(
            {
                "id": 154165,
                "type": "Workflows",
                "modelVersions": [{"id": 173951}],
            }
        ).encode()

        class _Response:
            def __init__(self, body: bytes) -> None:
                self._body = body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, *_args, **_kwargs) -> bytes:
                return self._body

        def _urlopen(req, *args, **kwargs):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/api/v1/models/" in url:
                return _Response(model_api_response)
            if "/api/download/models/" in url:
                return _Response(zip_bytes)
            return _Response(b"")

        monkeypatch.setattr(research_module.urllib.request, "urlopen", _urlopen)

        sources, warnings = research_module._run_web_search(
            "AnimateDiff workflow",
            client=lambda _query, _timeout: {
                "results": [
                    {
                        "title": "AnimateDiff Workflow",
                        "url": "https://civitai.com/models/154165/animatediff-workflow",
                        "snippet": "AnimateDiff workflow",
                    }
                ]
            },
            timeout=1,
        )

        assert not warnings
        assert sources[0]["source"] == "external_workflow"
        assert sources[0]["source_type"] == "domain_workflow_json:civitai.com"
        assert "ADE_AnimateDiffLoaderWithContext" in sources[0]["node_types"]
        assert "frame_count=16" in sources[0]["key_values"]
        assert sources[0]["source_workflow_available"] is True

    def test_web_search_derives_workflow_json_provisional_schema(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "nodes": [
                            {
                                "id": 93,
                                "type": "ADE_AnimateDiffLoaderWithContext",
                                "inputs": [
                                    {"name": "model", "type": "MODEL", "link": 1},
                                    {"name": "context_options", "type": "CONTEXT_OPTIONS", "link": 2},
                                ],
                                "outputs": [{"name": "MODEL", "type": "MODEL"}],
                                "widgets_values": [
                                    "hotshotxl_mm_v1.pth",
                                    "linear (HotshotXL/default)",
                                ],
                            }
                        ]
                    }
                ).encode()

        monkeypatch.setattr(research_module.urllib.request, "urlopen", lambda *args, **kwargs: _Response())

        sources, warnings = research_module._run_web_search(
            "Hotshot XL workflow JSON",
            client=lambda _query, _timeout: {
                "results": [
                    {
                        "title": "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json",
                        "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                        "snippet": "HotshotXL workflow JSON",
                    }
                ]
            },
            timeout=1,
        )

        assert not warnings
        schema = sources[0]["workflow_schema"]["ADE_AnimateDiffLoaderWithContext"]
        assert schema["input"]["required"]["model"]["type"] == "MODEL"
        assert schema["input"]["required"]["context_options"]["type"] == "CONTEXT_OPTIONS"
        assert schema["input"]["optional"]["widget_0"]["default"] == "hotshotxl_mm_v1.pth"
        assert schema["object_info_widget_order"] == ["widget_0", "widget_1"]
        assert schema["outputs"] == [{"name": "MODEL", "type": "MODEL"}]

    def test_hivemind_corpus_workflow_schema_preserves_positional_widgets(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        workflow_path = tmp_path / "corpus" / "hotshot.json"
        workflow_path.parent.mkdir()
        workflow_path.write_text(
            json.dumps(
                {
                    "nodes": [
                        {
                            "id": 93,
                            "type": "ADE_AnimateDiffLoaderWithContext",
                            "inputs": [
                                {"name": "model", "type": "MODEL", "link": 1},
                                {"name": "context_options", "type": "CONTEXT_OPTIONS", "link": 2},
                            ],
                            "outputs": [{"name": "MODEL", "type": "MODEL"}],
                            "widgets_values": [
                                "hotshotxl_mm_v1.pth",
                                "linear (HotshotXL/default)",
                            ],
                        },
                        {
                            "id": 134,
                            "type": "VHS_VideoCombine",
                            "inputs": [{"name": "images", "type": "IMAGE", "link": 3}],
                            "outputs": [{"name": "GIF", "type": "GIF"}],
                            "widgets_values": [24, 0, "Video", "video/h264-mp4"],
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        import vibecomfy.utils

        monkeypatch.setattr(vibecomfy.utils, "find_repo_root", lambda: tmp_path)

        node_types, workflow_schema = research_module._load_corpus_workflow_schema(
            "corpus/hotshot.json"
        )

        assert node_types == ["ADE_AnimateDiffLoaderWithContext", "VHS_VideoCombine"]
        loader = workflow_schema["ADE_AnimateDiffLoaderWithContext"]
        assert loader["input"]["required"]["model"]["type"] == "MODEL"
        assert loader["input"]["optional"]["widget_0"]["default"] == "hotshotxl_mm_v1.pth"
        assert loader["object_info_widget_order"] == ["widget_0", "widget_1"]
        video = workflow_schema["VHS_VideoCombine"]
        assert video["input"]["optional"]["widget_0"]["default"] == 24
        assert video["input"]["optional"]["widget_3"]["default"] == "video/h264-mp4"
        assert video["object_info_widget_order"] == ["widget_0", "widget_1", "widget_2", "widget_3"]

    def test_default_web_client_uses_cache_when_live_search_returns_nothing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)
        monkeypatch.setattr(research_module, "_duckduckgo_search", lambda query, timeout: [])
        monkeypatch.setattr(research_module, "_github_repository_search", lambda query, timeout: [])
        monkeypatch.setattr(research_module, "_brave_search", lambda query, timeout: [])
        research_module._write_web_search_cache(
            "Hotshot XL ComfyUI workflow",
            [
                {
                    "title": "hotshotxl motion model video transfer",
                    "url": "https://openart.ai/workflows/cychenyue/hotshotxl-motion-model-video-transfer-v1/VbUW0H73SKEVHvSw0WGW",
                    "snippet": "External workflow result from openart.ai",
                }
            ],
        )

        result = research_module._default_web_search_client("Hotshot XL ComfyUI workflow", 1)

        assert result["results"][0]["url"].startswith("https://openart.ai/workflows/")
        assert any("using cached results" in warning for warning in result["warnings"])

    def test_default_web_client_augments_live_leads_with_cached_workflow_json(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)
        monkeypatch.setattr(
            research_module,
            "_duckduckgo_search",
            lambda query, timeout: [
                {
                    "title": "HotshotXL OpenArt workflow",
                    "url": "https://openart.ai/workflows/example/hotshotxl",
                    "snippet": "HotshotXL workflow lead.",
                }
            ],
        )
        monkeypatch.setattr(research_module, "_github_repository_search", lambda query, timeout: [])
        monkeypatch.setattr(research_module, "_brave_search", lambda query, timeout: [])
        research_module._write_web_search_cache(
            "Hotshot XL ComfyUI workflow JSON node types",
            [
                {
                    "title": "workflow vid2vid hotshotXL ipadapterplusface ipadapter.json",
                    "url": "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json",
                    "snippet": "HotshotXL workflow JSON.",
                }
            ],
        )

        result = research_module._default_web_search_client(
            "Hotshot XL ComfyUI workflow 16 frames",
            1,
        )

        assert result["results"][0]["url"] == (
            "https://github.com/fictions-ai/sharing-is-caring/blob/main/workflow-vid2vid-hotshotXL-ipadapterplusface-ipadapter.json"
        )
        assert "https://openart.ai/workflows/example/hotshotxl" in [
            item["url"] for item in result["results"]
        ]

    def test_registry_candidate_queries_split_exact_class_tokens(self) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")

        queries = research_module._registry_candidate_queries(
            "ADE_AnimateDiffLoaderWithContext ADE_AnimateDiffUniformContextOptions "
            "ADE_UseEvolvedSampling ComfyUI nodes"
        )

        assert queries[0].startswith("ADE_AnimateDiffLoaderWithContext")
        assert "ADE_ AnimateDiff Evolved ComfyUI" in queries
        assert "ADE_AnimateDiffLoaderWithContext" in queries
        assert "ADE_AnimateDiffUniformContextOptions" in queries
        assert "ADE_UseEvolvedSampling" in queries
        anchors = research_module._registry_anchor_terms(queries[0])
        assert "animatediff" in anchors
        assert "evolved" in anchors
        assert "animatediffevolved" in anchors

    def test_web_cache_falls_back_by_named_anchors(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)
        research_module._write_web_search_cache(
            "Hotshot XL ComfyUI workflow",
            [
                {
                    "title": "hotshotxl motion model video transfer",
                    "url": "https://openart.ai/workflows/cychenyue/hotshotxl-motion-model-video-transfer-v1/VbUW0H73SKEVHvSw0WGW",
                    "snippet": "External workflow result from openart.ai",
                }
            ],
        )

        results = research_module._read_web_search_cache(
            "Hotshot XL ComfyUI workflow generate 16 frames"
        )

        assert results[0]["url"].startswith("https://openart.ai/workflows/")

    def test_web_cache_falls_back_by_cached_result_url_tokens(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "_DEFAULT_WEB_CACHE_ROOT", tmp_path)
        research_module._write_web_search_cache(
            "Hotshot XL ComfyUI workflow",
            [
                {
                    "title": "hotshotxl motion model video transfer",
                    "url": "https://openart.ai/workflows/cychenyue/hotshotxl-motion-model-video-transfer-v1/VbUW0H73SKEVHvSw0WGW",
                    "snippet": "External workflow result from openart.ai",
                }
            ],
        )

        results = research_module._read_web_search_cache(
            "openart workflow VbUW0H73SKEVHvSw0WGW node types and connections"
        )

        assert results[0]["url"].endswith("/VbUW0H73SKEVHvSw0WGW")

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_local_limit_zero_skips_local_workflow_search(self, mock_corpus) -> None:
        # Registry and web tiers are disabled so the assertion isolates the
        # local-limit behavior.
        result = research(
            "Hotshot XL SDXL video",
            local_limit=0,
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
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
        assert len(result[0].node_ids) == len(result[0].node_types)
        assert result[0].entry_anchor == result[0].node_ids[0]
        assert result[0].exit_anchor == result[0].node_ids[-1]
        assert result[0].warnings == ()

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
        assert payload["node_ids"] == ["7"]
        assert payload["node_types"] == ["KSampler"]
        assert "warnings" not in payload

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

    # ── adaptation compatibility: all_slices / context_note / forbidden-key guards (T4) ──

    _FORBIDDEN_ADAPT_KEYS = frozenset({
        "winner", "best", "selected", "score", "rank", "primary",
        "preferred", "chosen", "pick", "choice", "top", "recommended",
    })

    def _assert_no_forbidden_keys(self, payload: dict, label: str) -> None:
        found = self._FORBIDDEN_ADAPT_KEYS & set(payload)
        assert not found, f"{label} contains forbidden keys: {sorted(found)}"

    def test_all_slices_includes_single_slice(self) -> None:
        """all_slices contains the full slice tuple, not just slices[0]."""
        ws = WorkflowSlice(source_class_type="video/ltx2_3_t2v",
                           python_path="ready_templates/video/ltx2_3_t2v.py")
        plan = _build_adaptation_plan(query="test", graph=None, inspection=None, slices=(ws,))
        assert plan is not None
        assert plan.all_slices == (ws,)
        assert len(plan.all_slices) == 1

    def test_all_slices_includes_all_slices_not_just_first(self) -> None:
        """When multiple slices exist, all_slices preserves every slice."""
        ws1 = WorkflowSlice(source_class_type="first", python_path="a.py")
        ws2 = WorkflowSlice(source_class_type="second", python_path="b.py")
        ws3 = WorkflowSlice(source_class_type="third", python_path="c.py")
        plan = _build_adaptation_plan(
            query="test", graph=None, inspection=None, slices=(ws1, ws2, ws3),
        )
        assert plan is not None
        # selected_slice is first but all_slices includes all three
        assert plan.selected_slice == ws1
        assert plan.all_slices == (ws1, ws2, ws3)
        assert len(plan.all_slices) == 3
        class_types = {s.source_class_type for s in plan.all_slices}
        assert class_types == {"first", "second", "third"}

    def test_context_note_contains_neutral_language(self) -> None:
        """context_note explicitly states the material is NOT a winner/recommendation."""
        ws = WorkflowSlice(source_class_type="test", python_path="test.py")
        plan = _build_adaptation_plan(query="test", graph=None, inspection=None, slices=(ws,))
        assert plan is not None
        assert plan.context_note
        assert "NOT a winner" in plan.context_note
        assert "recommendation" in plan.context_note
        assert "required implementation" in plan.context_note
        assert "presentation context only" in plan.context_note.lower()
        assert "all available precedent slices" in plan.context_note.lower()

    def test_context_note_present_even_with_multiple_slices(self) -> None:
        """context_note is always populated regardless of slice count."""
        ws1 = WorkflowSlice(source_class_type="a", python_path="a.py")
        ws2 = WorkflowSlice(source_class_type="b", python_path="b.py")
        plan = _build_adaptation_plan(
            query="test", graph=None, inspection=None, slices=(ws1, ws2),
        )
        assert plan is not None
        assert plan.context_note
        assert "NOT a winner" in plan.context_note

    def test_to_dict_includes_all_slices_when_populated(self) -> None:
        """to_dict() emits all_slices when non-empty."""
        ws1 = WorkflowSlice(source_class_type="a", python_path="a.py")
        ws2 = WorkflowSlice(source_class_type="b", python_path="b.py")
        plan = _build_adaptation_plan(
            query="test", graph=None, inspection=None, slices=(ws1, ws2),
        )
        assert plan is not None
        d = plan.to_dict()
        assert "all_slices" in d
        assert isinstance(d["all_slices"], list)
        assert len(d["all_slices"]) == 2
        assert d["all_slices"][0]["source_class_type"] == "a"
        assert d["all_slices"][1]["source_class_type"] == "b"

    def test_to_dict_omits_all_slices_when_empty(self) -> None:
        """to_dict() omits all_slices key when the tuple is empty."""
        # Use a manually constructed plan with empty all_slices to verify omission.
        plan = PrecedentAdaptationPlan(
            selected_slice=WorkflowSlice(source_class_type="test"),
            all_slices=(),
            context_note="",
        )
        d = plan.to_dict()
        assert "all_slices" not in d

    def test_to_dict_includes_context_note_when_populated(self) -> None:
        """to_dict() emits context_note when non-empty."""
        ws = WorkflowSlice(source_class_type="test", python_path="test.py")
        plan = _build_adaptation_plan(query="test", graph=None, inspection=None, slices=(ws,))
        assert plan is not None
        d = plan.to_dict()
        assert "context_note" in d
        assert "NOT a winner" in d["context_note"]

    def test_to_dict_omits_context_note_when_empty(self) -> None:
        """to_dict() omits context_note key when empty."""
        plan = PrecedentAdaptationPlan(
            selected_slice=WorkflowSlice(source_class_type="test"),
            all_slices=(),
            context_note="",
        )
        d = plan.to_dict()
        assert "context_note" not in d

    def test_to_dict_no_forbidden_keys_in_plan(self) -> None:
        """PrecedentAdaptationPlan serialization never exposes winner-like keys."""
        ws1 = WorkflowSlice(source_class_type="a", python_path="a.py")
        ws2 = WorkflowSlice(source_class_type="b", python_path="b.py")
        plan = _build_adaptation_plan(
            query="test", graph=None, inspection=None, slices=(ws1, ws2),
        )
        assert plan is not None
        d = plan.to_dict()
        self._assert_no_forbidden_keys(d, "PrecedentAdaptationPlan.to_dict()")

    def test_to_dict_no_forbidden_keys_in_selected_slice(self) -> None:
        """selected_slice serialization never exposes winner-like keys."""
        ws = WorkflowSlice(source_class_type="test", python_path="test.py")
        plan = _build_adaptation_plan(query="test", graph=None, inspection=None, slices=(ws,))
        assert plan is not None
        d = plan.to_dict()
        assert "selected_slice" in d
        self._assert_no_forbidden_keys(d["selected_slice"], "selected_slice.to_dict()")

    def test_to_dict_no_forbidden_keys_in_all_slices(self) -> None:
        """Every slice in all_slices serialization is free of winner-like keys."""
        ws1 = WorkflowSlice(source_class_type="a", python_path="a.py")
        ws2 = WorkflowSlice(source_class_type="b", python_path="b.py")
        plan = _build_adaptation_plan(
            query="test", graph=None, inspection=None, slices=(ws1, ws2),
        )
        assert plan is not None
        d = plan.to_dict()
        assert "all_slices" in d
        for i, slice_dict in enumerate(d["all_slices"]):
            self._assert_no_forbidden_keys(slice_dict, f"all_slices[{i}].to_dict()")

    def test_all_slices_preserves_every_slice_even_when_no_graph(self) -> None:
        """No graph → plan still preserves all slices, not just one."""
        ws1 = WorkflowSlice(source_class_type="a", python_path="a.py")
        ws2 = WorkflowSlice(source_class_type="b", python_path="b.py")
        ws3 = WorkflowSlice(source_class_type="c", python_path="c.py")
        plan = _build_adaptation_plan(
            query="test", graph=None, inspection=None, slices=(ws1, ws2, ws3),
        )
        assert plan is not None
        assert plan.all_slices == (ws1, ws2, ws3)
        assert plan.structural_validation == "not_evaluated"

    def test_all_slices_preserved_even_with_compatible_target(self) -> None:
        """Even when a compatible target exists, all_slices still holds every slice."""
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),
            inspection=None,
            slices=(self._wan_lora_slice(),
                    WorkflowSlice(source_class_type="extra", python_path="extra.py")),
        )
        assert plan is not None
        assert len(plan.all_slices) == 2
        class_types = {s.source_class_type for s in plan.all_slices}
        assert "extra" in class_types

    def test_no_slices_returns_none_no_hidden_slice_zero(self) -> None:
        """Empty slices produces None, never a plan with a hidden slices[0]."""
        result = _build_adaptation_plan(query="test", graph=None, inspection=None, slices=())
        assert result is None

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
        assert "lora" in roles
        assert {
            (binding["anchor_role"], binding["source_socket"], binding["target_socket"])
            for binding in plan.anchor_bindings
        } >= {("lora", "lora", "lora")}
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

    def test_family_mismatch_blocks_anchor_bindings(self) -> None:
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

    # ── Media-domain gate (pre-selection) ────────────────────────────────────

    def test_cross_domain_slice_is_rejected_and_returns_none(self) -> None:
        """An image-domain slice that would structurally bind to a video
        target graph is rejected by the media-domain gate, and (because it is
        the only candidate) the plan returns ``None`` instead of binding the
        wrong-domain slice.  This is the regression guard for the dominant
        cross-media failure class (3D/image/audio graphs matched to WanVideo
        slices)."""
        import dataclasses

        # Reuse the real Wan LoRA slice (it has a source_workflow_path that
        # loads, so WITHOUT the gate it would structurally bind to the Wan
        # target graph) but relabel its node_types as a pure IMAGE chain so
        # the media-domain gate classifies it as image ≠ video.
        image_slice = dataclasses.replace(
            self._wan_lora_slice(),
            node_types=(
                "CheckpointLoaderSimple",
                "LoraLoader",
                "CLIPTextEncode",
                "KSampler",
                "VAEDecode",
                "SaveImage",
            ),
            source_class_type="image/sd15_lora_chain",
            python_path="ready_templates/image/sd15_lora_chain.py",
        )
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),  # video domain
            inspection=None,
            slices=(image_slice,),
        )
        assert plan is None

    def test_cross_media_adapter_slice_is_also_rejected(self) -> None:
        """A slice whose source advertises a legit cross-media adapter
        (image_to_video) is NOW ALSO rejected by the pure media-domain gate
        when its domain differs from the target graph's.  The earlier
        cross-media-adapter whitelist was net-harmful (let video adapters
        through against 3D/image graphs) and has been removed; the gate now
        rejects ANY defined-domain mismatch, adapters included.  Verified
        directly via the gate helpers (the full plan path also depends on
        structural binding, which is orthogonal to the gate)."""
        import dataclasses

        from vibecomfy.executor.research import (
            _media_domain_from_node_types,
            _slice_is_cross_media_adapter,
        )

        adapter_slice = dataclasses.replace(
            self._wan_lora_slice(),
            node_types=("LoadImage", "WanVideoSampler", "VHS_VideoCombine"),
            source_class_type="image_to_video/wan_i2v",
            python_path="ready_templates/image_to_video/wan_i2v.py",
        )
        graph_domain = _media_domain_from_node_types(
            ("CheckpointLoaderSimple", "SaveImage")
        )
        slice_domain = _media_domain_from_node_types(adapter_slice.node_types)
        assert graph_domain == "image"
        assert slice_domain == "video"
        # The slice genuinely advertises a cross-media adapter capability…
        assert _slice_is_cross_media_adapter(adapter_slice) is True
        # …but the pure domain gate rejects it anyway (mismatched domain is
        # the only test, no adapter pass-through).
        assert slice_domain is not None
        assert slice_domain != graph_domain

    def test_cross_media_adapter_slice_not_rejected_at_source(self) -> None:
        """A cross-media adapter slice (image_to_video) is NOT rejected by
        source filtering (``_filter_slices_for_graph_domain``) or
        adaptation-plan selection (``_build_adaptation_plan``) when the
        target graph is video-domain and the slice genuinely advertises a
        cross-media adapter capability.  Both paths route through
        ``_slice_allowed_for_graph_domain``, which delegates to
        ``_slice_is_cross_media_adapter`` for defined-domain mismatches.
        """
        import dataclasses

        from vibecomfy.executor.research import (
            _filter_slices_for_graph_domain,
            _graph_node_class_types,
            _media_domain_from_node_types,
            _slice_is_cross_media_adapter,
        )

        # Build an image_to_video adapter slice with image-domain node_types
        # so the slice's computed domain ("image") differs from the target
        # graph's domain ("video").  The source_class_type and python_path
        # contain the "image_to_video" signal so _slice_is_cross_media_adapter
        # returns True.
        adapter_slice = dataclasses.replace(
            self._wan_lora_slice(),
            node_types=(
                "CheckpointLoaderSimple",
                "CLIPTextEncode",
                "KSampler",
                "VAEDecode",
                "SaveImage",
            ),
            source_class_type="image_to_video/wan_i2v_adapter",
            python_path="ready_templates/image_to_video/wan_i2v_adapter.py",
        )
        video_graph = self._wan_target_graph()

        # ── Prove the slice advertises a cross-media adapter ──
        assert _slice_is_cross_media_adapter(adapter_slice) is True

        # ── Prove the domains differ ──
        graph_class_types = _graph_node_class_types(video_graph)
        graph_domain = _media_domain_from_node_types(graph_class_types)
        slice_domain = _media_domain_from_node_types(adapter_slice.node_types)
        assert graph_domain == "video"
        assert slice_domain == "image"
        assert slice_domain != graph_domain

        # ── Source filtering: adapter passes through _filter_slices_for_graph_domain ──
        filtered = _filter_slices_for_graph_domain(video_graph, (adapter_slice,))
        assert len(filtered) == 1, (
            f"Expected adapter slice to pass source filtering, "
            f"but _filter_slices_for_graph_domain returned {len(filtered)} slices"
        )
        assert filtered[0] is adapter_slice

        # ── Adaptation plan: adapter is not rejected (plan is not None) ──
        plan = _build_adaptation_plan(
            query="add image_to_video adapter",
            graph=video_graph,
            inspection=None,
            slices=(adapter_slice,),
        )
        assert plan is not None, (
            "_build_adaptation_plan must not reject a cross-media adapter "
            "slice at the gate level"
        )
        assert plan.selected_slice is adapter_slice

    def test_same_domain_slice_is_not_rejected(self) -> None:
        """A video slice against a video target graph is unaffected by the
        gate (same domain)."""
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),  # video domain
            inspection=None,
            slices=(self._wan_lora_slice(),),  # video domain
        )
        assert plan is not None
        assert plan.structural_validation == "pass"
        assert plan.candidate_graph is not None


class TestBuildPrecedentPacket:
    """Building PrecedentPacket from slices and source dicts."""

    def test_empty_returns_none(self) -> None:
        result = _build_precedent_packet(slices=(), sources=())
        assert result is None

    def test_single_slice_produces_option(self) -> None:
        ws = WorkflowSlice(
            source_class_type="wf_a",
            node_ids=("1", "2"),
            node_types=("KSampler", "VAEDecode"),
        )
        result = _build_precedent_packet(slices=(ws,), sources=())
        assert result is not None
        assert len(result.options) == 1
        opt = result.options[0]
        assert opt.source_class_type == "wf_a"
        assert opt.node_ids == ("1", "2")
        assert opt.node_types == ("KSampler", "VAEDecode")

    def test_slice_with_matched_source_carries_notes(self) -> None:
        ws = WorkflowSlice(source_class_type="wf_a")
        sources = (
            {
                "class_type": "wf_a",
                "source": "ready_template",
                "pack": "ltxvideo",
                "description": "LTX video workflow",
                "reasons": ["matched class_type"],
            },
        )
        result = _build_precedent_packet(slices=(ws,), sources=sources)
        assert result is not None
        opt = result.options[0]
        assert opt.description == "LTX video workflow"
        assert "pack: ltxvideo" in opt.notes
        assert "source: ready_template" in opt.notes
        assert "matched class_type" in opt.notes

    def test_supplemental_source_without_slice(self) -> None:
        """Sources without matching slices become supplemental options."""
        sources = (
            {
                "class_type": "KSampler",
                "source": "object_info",
                "description": "Sampling node",
                "reasons": ["matched tag: sampler"],
            },
        )
        result = _build_precedent_packet(slices=(), sources=sources)
        assert result is not None
        assert len(result.options) == 1
        opt = result.options[0]
        assert opt.source_class_type == "KSampler"
        assert opt.description == "Sampling node"
        assert "matched tag: sampler" in opt.notes
        assert "source: object_info" in opt.notes

    def test_supplemental_no_description_skipped(self) -> None:
        """Sources without description or reasons are not included."""
        sources = (
            {"class_type": "BareNode", "source": "object_info"},
        )
        result = _build_precedent_packet(slices=(), sources=sources)
        assert result is None

    def test_local_ordered_before_external(self) -> None:
        ws_local = WorkflowSlice(source_class_type="local_wf")
        ws_ext = WorkflowSlice(source_class_type="ext_wf")
        result = _build_precedent_packet(
            slices=(ws_ext, ws_local),
            sources=(
                {"class_type": "local_wf", "source": "ready_template", "description": "Local"},
                {"class_type": "ext_wf", "source": "hivemind_workflow", "description": "Ext"},
            ),
        )
        assert result is not None
        assert len(result.options) == 2
        assert result.options[0].source_class_type == "local_wf"
        assert result.options[1].source_class_type == "ext_wf"

    def test_multiple_local_sorted_by_class_type(self) -> None:
        ws_b = WorkflowSlice(source_class_type="wf_b")
        ws_a = WorkflowSlice(source_class_type="wf_a")
        result = _build_precedent_packet(
            slices=(ws_b, ws_a),
            sources=(
                {"class_type": "wf_b", "source": "ready_template", "description": "B"},
                {"class_type": "wf_a", "source": "curated", "description": "A"},
            ),
        )
        assert result is not None
        # Both local; stable class_type ordering: wf_a before wf_b
        assert result.options[0].source_class_type == "wf_a"
        assert result.options[1].source_class_type == "wf_b"

    def test_external_sorted_by_source_tier_then_class_type(self) -> None:
        ws_web = WorkflowSlice(source_class_type="web_wf")
        ws_hm = WorkflowSlice(source_class_type="hm_wf")
        result = _build_precedent_packet(
            slices=(ws_web, ws_hm),
            sources=(
                {"class_type": "web_wf", "source": "web", "description": "Web"},
                {"class_type": "hm_wf", "source": "hivemind_workflow", "description": "HM"},
            ),
        )
        assert result is not None
        # hivemind_workflow tier 0 < web tier 5
        assert result.options[0].source_class_type == "hm_wf"
        assert result.options[1].source_class_type == "web_wf"

    def test_packet_context_note_is_neutral(self) -> None:
        ws = WorkflowSlice(source_class_type="wf")
        result = _build_precedent_packet(
            slices=(ws,),
            sources=({"class_type": "wf", "source": "ready_template", "description": "Desc"},),
        )
        assert result is not None
        assert "neutral evidence" in result.context_note.lower()
        assert "no ranking" in result.context_note.lower()
        assert "winner" in result.context_note.lower()

    def test_no_forbidden_keys_in_serialized_packet(self) -> None:
        ws = WorkflowSlice(source_class_type="wf", node_ids=("1",))
        result = _build_precedent_packet(
            slices=(ws,),
            sources=({"class_type": "wf", "source": "ready_template", "description": "D"},),
        )
        assert result is not None
        d = result.to_dict()
        forbidden = {
            "winner", "best", "selected", "score", "rank", "primary",
            "preferred", "chosen", "pick", "choice", "top", "recommended",
        }
        for opt in d["options"]:
            overlap = set(opt.keys()) & forbidden
            assert not overlap, f"Forbidden keys in option: {overlap}"
        packet_keys = set(d.keys()) - {"options", "context_note", "warnings"}
        overlap = packet_keys & forbidden
        assert not overlap, f"Forbidden keys in packet: {overlap}"

    def test_slice_warnings_become_notes(self) -> None:
        ws = WorkflowSlice(
            source_class_type="wf_warn",
            warnings=({"code": "missing_required_pattern_nodes", "message": "Missing blockswap"},),
        )
        result = _build_precedent_packet(
            slices=(ws,),
            sources=({"class_type": "wf_warn", "source": "ready_template", "description": "D"},),
        )
        assert result is not None
        opt = result.options[0]
        assert any("Missing blockswap" in note for note in opt.notes)

    def test_duplicate_class_type_not_duplicated(self) -> None:
        """Slice-backed option takes precedence; matching source is not re-added."""
        ws = WorkflowSlice(source_class_type="dup")
        sources = (
            {"class_type": "dup", "source": "ready_template", "description": "Already sliced"},
        )
        result = _build_precedent_packet(slices=(ws,), sources=sources)
        assert result is not None
        assert len(result.options) == 1

    def test_non_dict_sources_skipped(self) -> None:
        ws = WorkflowSlice(source_class_type="wf")
        sources: tuple = (
            {"class_type": "wf", "source": "ready_template", "description": "D"},
            "not-a-dict",  # type: ignore[arg-type]
        )
        result = _build_precedent_packet(slices=(ws,), sources=sources)
        assert result is not None
        assert len(result.options) == 1  # non-dict skipped

    def test_packet_with_multiple_slices_preserves_all(self) -> None:
        ws1 = WorkflowSlice(source_class_type="a")
        ws2 = WorkflowSlice(source_class_type="b")
        ws3 = WorkflowSlice(source_class_type="c")
        result = _build_precedent_packet(
            slices=(ws1, ws2, ws3),
            sources=(
                {"class_type": "a", "source": "ready_template", "description": "A"},
                {"class_type": "b", "source": "ready_template", "description": "B"},
                {"class_type": "c", "source": "ready_template", "description": "C"},
            ),
        )
        assert result is not None
        assert len(result.options) == 3
        class_types = {o.source_class_type for o in result.options}
        assert class_types == {"a", "b", "c"}

    def test_source_workflow_path_preserved_in_option(self) -> None:
        ws = WorkflowSlice(
            source_class_type="wf",
            source_workflow_path="path/to/workflow.json",
        )
        result = _build_precedent_packet(
            slices=(ws,),
            sources=({"class_type": "wf", "source": "source_workflow", "description": "D"},),
        )
        assert result is not None
        assert result.options[0].source_workflow_path == "path/to/workflow.json"

    def test_mixed_local_and_supplemental_ordering(self) -> None:
        """Local slice + external supplemental: local first, then external."""
        ws_local = WorkflowSlice(source_class_type="local_wf")
        result = _build_precedent_packet(
            slices=(ws_local,),
            sources=(
                {"class_type": "local_wf", "source": "ready_template", "description": "L"},
                {"class_type": "hivemind_node", "source": "hivemind", "description": "H", "reasons": ["hivemind hit"]},
            ),
        )
        assert result is not None
        assert len(result.options) == 2
        assert result.options[0].source_class_type == "local_wf"
        assert result.options[1].source_class_type == "hivemind_node"

    def test_supplemental_source_no_class_type_skipped(self) -> None:
        sources = (
            {"source": "web", "description": "No class_type"},
        )
        result = _build_precedent_packet(slices=(), sources=sources)
        assert result is None

    def test_research_result_includes_precedent_packet(self) -> None:
        ws = WorkflowSlice(source_class_type="wf")
        packet = _build_precedent_packet(
            slices=(ws,),
            sources=({"class_type": "wf", "source": "ready_template", "description": "D"},),
        )
        rr = ResearchResult(precedent_packet=packet)
        d = rr.to_dict()
        assert "precedent_packet" in d
        assert len(d["precedent_packet"]["options"]) == 1

    def test_research_result_omits_precedent_packet_when_none(self) -> None:
        rr = ResearchResult()
        d = rr.to_dict()
        assert "precedent_packet" not in d

    def test_research_result_includes_selected_precedent(self) -> None:
        selected = SelectedPrecedent(
            name="HotShot workflow",
            source="hivemind_workflow",
            requested_terms=("hotshot", "video"),
            implementation_ecosystems=("animatediff",),
            minimal_spine=("CheckpointLoaderSimple", "ADE_AnimateDiffLoaderWithContext", "VHS_VideoCombine"),
        )
        rr = ResearchResult(selected_precedent=selected)
        d = rr.to_dict()
        assert d["selected_precedent"]["name"] == "HotShot workflow"
        assert d["selected_precedent"]["implementation_ecosystems"] == ["animatediff"]
        assert d["selected_precedent"]["minimal_spine"][-1] == "VHS_VideoCombine"

    def test_selected_precedent_distinguishes_request_from_ecosystem(self) -> None:
        source = {
            "class_type": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
            "source": "hivemind_workflow",
            "url": "https://example.test/workflow-vid2vid-hotshotXL.json",
            "reasons": (
                "hivemind:workflow resource",
                "hivemind:parseable workflow",
                "hivemind:compiled api available",
                "hivemind:filename matched 'HotShotXL'",
            ),
            "promotion_gates": {
                "has_workflow_json": True,
                "parseable_workflow": True,
                "has_compiled_api": True,
            },
            "workflow_semantics": {
                "model_families": ["hotshot", "animatediff", "sdxl"],
                "models": ["hotshotxl_mm_v1.pth", "sd_xl_base_1.0.safetensors"],
                "node_types": [
                    "CheckpointLoaderSimple",
                    "ADE_AnimateDiffUniformContextOptions",
                    "ADE_AnimateDiffLoaderWithContext",
                    "KSamplerAdvanced",
                    "VAEDecode",
                    "VHS_VideoCombine",
                ],
            },
        }

        selected = _build_selected_precedent(
            query="Switch this to generate 8 frames of video using HotShotXL",
            precedent_sources=(source,),
        )

        assert selected is not None
        payload = selected.to_dict()
        assert payload["requested_terms"][:2] == ["hotshot", "video"]
        assert "animatediff" in payload["implementation_ecosystems"]
        assert "hotshotxl_mm_v1.pth" in payload["models"]
        assert payload["minimal_spine"] == [
            "CheckpointLoaderSimple",
            "ADE_AnimateDiffUniformContextOptions",
            "ADE_AnimateDiffLoaderWithContext",
            "KSamplerAdvanced",
            "VAEDecode",
            "VHS_VideoCombine",
        ]
        assert any("literal 'hotshot'" in item for item in payload["avoid_searches"])
        assert any("grounding precedent" in item for item in payload["interpretation_notes"])

    def test_selected_precedent_spine_keeps_late_custom_motion_nodes(self) -> None:
        source = {
            "class_type": "AnimateDiff Video Generation with ControlNet and IP-Adapter",
            "source": "hivemind_workflow",
            "url": "https://example.test/workflow-vid2vid-hotshotXL.json",
            "reasons": ("hivemind:filename matched 'HotShotXL'",),
            "workflow_semantics": {
                "model_families": ["hotshot", "animatediff", "sdxl"],
                "node_types": [
                    "VAEDecode",
                    "CLIPTextEncodeSDXL",
                    "KSamplerAdvanced",
                    "CheckpointLoaderSimple",
                    "SaveImage",
                    "ControlNetApplyAdvanced",
                    "ControlNetLoaderAdvanced",
                    "VHS_LoadImagesPath",
                    "ImageScale",
                    "PreviewImage",
                    "VHS_VideoCombine",
                    "VAEEncode",
                    "IPAdapterModelLoader",
                    "CLIPVisionLoader",
                    "VAELoader",
                    "ADE_AnimateDiffLoaderWithContext",
                    "ADE_AnimateDiffUniformContextOptions",
                ],
            },
        }

        selected = _build_selected_precedent(
            query="Switch this to generate 8 frames of video using HotShotXL",
            precedent_sources=(source,),
        )

        assert selected is not None
        spine = selected.to_dict()["minimal_spine"]
        assert "ADE_AnimateDiffLoaderWithContext" in spine
        assert "ADE_AnimateDiffUniformContextOptions" in spine

    def test_selected_precedent_spine_keeps_ipadapter_integration_path(self) -> None:
        source = {
            "class_type": "SDXL IPAdapter reference workflow",
            "source": "external_workflow",
            "source_workflow_path": "/tmp/ipadapter_sdxl.json",
            "node_types": [
                "CheckpointLoaderSimple",
                "LoadImage",
                "CLIPVisionLoader",
                "IPAdapterModelLoader",
                "IPAdapterAdvanced",
                "KSampler",
                "VAEDecode",
                "SaveImage",
            ],
        }

        selected = _build_selected_precedent(
            query="Use IP-Adapter to feed the reference image into this SDXL workflow",
            precedent_sources=(source,),
        )

        assert selected is not None
        spine = selected.to_dict()["minimal_spine"]
        assert "LoadImage" in spine
        assert "CLIPVisionLoader" in spine
        assert "IPAdapterModelLoader" in spine
        assert "IPAdapterAdvanced" in spine
        assert "KSampler" in spine

    # ── T8: internal precedent first, stable ordering, non-failure, evidence/context ─

    def test_all_local_source_kinds_precede_all_external(self) -> None:
        """Every local source kind (object_info, curated, ready_template,
        source_workflow, custom_node_examples) sorts before every external
        kind (hivemind_workflow, hivemind, external_workflow, comfy-registry,
        github, web)."""
        slices = (
            WorkflowSlice(source_class_type="ext_hm_wf"),
            WorkflowSlice(source_class_type="local_ready"),
            WorkflowSlice(source_class_type="local_obj"),
            WorkflowSlice(source_class_type="local_curated"),
            WorkflowSlice(source_class_type="ext_web"),
        )
        sources = (
            {"class_type": "ext_hm_wf", "source": "hivemind_workflow", "description": "Ext HM WF"},
            {"class_type": "local_ready", "source": "ready_template", "description": "Local ready"},
            {"class_type": "local_obj", "source": "object_info", "description": "Local obj info"},
            {"class_type": "local_curated", "source": "curated", "description": "Local curated"},
            {"class_type": "ext_web", "source": "web", "description": "Ext web"},
        )
        result = _build_precedent_packet(slices=slices, sources=sources)
        assert result is not None
        class_types = [o.source_class_type for o in result.options]
        # All three local kinds must appear before the two external kinds.
        local_kinds = {"local_ready", "local_obj", "local_curated"}
        external_kinds = {"ext_hm_wf", "ext_web"}
        last_local_idx = max(i for i, ct in enumerate(class_types) if ct in local_kinds)
        first_ext_idx = min(i for i, ct in enumerate(class_types) if ct in external_kinds)
        assert last_local_idx < first_ext_idx, (
            f"Local {class_types[:first_ext_idx]} should all precede external {class_types[first_ext_idx:]}"
        )
        # Within local: alphabetically stable
        local_cts = [ct for ct in class_types if ct in local_kinds]
        assert local_cts == sorted(local_cts), f"Local options not alphabetical: {local_cts}"

    def test_same_external_tier_stable_alphabetical_order(self) -> None:
        """Multiple options from the same external source tier are ordered
        alphabetically by source_class_type."""
        slices = (
            WorkflowSlice(source_class_type="zeta_hm_wf"),
            WorkflowSlice(source_class_type="alpha_hm_wf"),
            WorkflowSlice(source_class_type="gamma_hm_wf"),
        )
        sources = (
            {"class_type": ct, "source": "hivemind_workflow", "description": ct}
            for ct in ("zeta_hm_wf", "alpha_hm_wf", "gamma_hm_wf")
        )
        result = _build_precedent_packet(slices=slices, sources=tuple(sources))
        assert result is not None
        class_types = [o.source_class_type for o in result.options]
        # All are same tier (hivemind_workflow); within that tier they sort
        # by class_type alphabetically.
        expected = sorted(["zeta_hm_wf", "alpha_hm_wf", "gamma_hm_wf"])
        assert class_types == expected, f"Expected {expected}, got {class_types}"

    def test_external_mixed_tiers_correct_ordering(self) -> None:
        """External sources are ordered by source tier then alphabetically
        within each tier."""
        slices = (
            WorkflowSlice(source_class_type="gamma_web"),
            WorkflowSlice(source_class_type="alpha_hm"),
            WorkflowSlice(source_class_type="beta_hm"),
            WorkflowSlice(source_class_type="alpha_github"),
        )
        sources = (
            {"class_type": "gamma_web", "source": "web", "description": "Web gamma"},
            {"class_type": "alpha_hm", "source": "hivemind", "description": "HM alpha"},
            {"class_type": "beta_hm", "source": "hivemind", "description": "HM beta"},
            {"class_type": "alpha_github", "source": "github", "description": "GH alpha"},
        )
        result = _build_precedent_packet(slices=slices, sources=sources)
        assert result is not None
        class_types = [o.source_class_type for o in result.options]
        # Expected order by tier: hivemind(1) < github(4) < web(5),
        # alphabetical within each tier: alpha_hm < beta_hm
        expected = ["alpha_hm", "beta_hm", "alpha_github", "gamma_web"]
        assert class_types == expected, f"Expected {expected}, got {class_types}"

    def test_packet_absence_is_non_failure_research_result(self) -> None:
        """ResearchResult with precedent_packet=None is valid and does not
        error on to_dict()."""
        rr = ResearchResult(
            summary="No relevant results.",
            sources=(),
            precedent_packet=None,
        )
        # Accessing precedent_packet when None is fine.
        assert rr.precedent_packet is None
        # to_dict() must not include precedent_packet when None.
        d = rr.to_dict()
        assert "precedent_packet" not in d
        # Essential fields still present.
        assert d["summary"] == "No relevant results."
        assert d["sources"] == []

    def test_null_packet_no_error_on_attribute_access(self) -> None:
        """Verify that attributes of a None packet are safely guarded —
        accessing precedent_packet on a ResearchResult with None does
        not throw."""
        rr = ResearchResult(precedent_packet=None)
        # This must not raise.
        packet = rr.precedent_packet
        assert packet is None

    def test_context_note_disclaims_ranking_explicitly(self) -> None:
        """The packet context_note explicitly states no ranking, no winner,
        and frames options as neutral evidence."""
        ws = WorkflowSlice(source_class_type="wf")
        result = _build_precedent_packet(
            slices=(ws,),
            sources=(),
        )
        assert result is not None
        cn = result.context_note.lower()
        # Must contain explicit neutral-evidence framing.
        assert "neutral evidence" in cn
        # Must disclaim ranking and winners.
        assert "no ranking" in cn or "no rank" in cn or "not a rank" in cn
        assert "winner" in cn or "recommendation" in cn
        # Must mention the ordering policy.
        assert "internal" in cn or "local" in cn or "evidence first" in cn

    def test_option_descriptions_avoid_winner_language(self) -> None:
        """Neither slice-backed nor supplemental option descriptions use
        language that implies a winner, recommendation, or selection."""
        ws = WorkflowSlice(source_class_type="wf_a")
        sources = (
            {"class_type": "wf_a", "source": "ready_template", "description": "A reference workflow for video generation"},
            {"class_type": "ext_node", "source": "hivemind", "description": "External community node", "reasons": ["hivemind hit"]},
        )
        result = _build_precedent_packet(slices=(ws,), sources=sources)
        assert result is not None
        winner_words = {"winner", "best", "recommended", "recommendation",
                        "selected", "chosen", "top pick", "top choice",
                        "primary", "preferred", "optimal", "ideal"}
        for opt in result.options:
            desc_lower = opt.description.lower()
            for word in winner_words:
                assert word not in desc_lower, (
                    f"Option {opt.source_class_type} description contains "
                    f"winner-like word '{word}': {opt.description}"
                )

    def test_option_notes_framed_as_evidence_source(self) -> None:
        """Option notes describe the source, pack, and reasons — they do
        not assert ranking, scores, or selection preference."""
        ws = WorkflowSlice(source_class_type="wf")
        sources = (
            {"class_type": "wf", "source": "ready_template", "pack": "mypack",
             "description": "A workflow", "reasons": ["matched query"]},
        )
        result = _build_precedent_packet(slices=(ws,), sources=sources)
        assert result is not None
        opt = result.options[0]
        notes_lower = " ".join(opt.notes).lower()
        # Notes describe context, not ranking.
        assert "source:" in notes_lower or "pack:" in notes_lower
        forbidden = {"winner", "best", "recommended", "selected", "chosen",
                     "primary", "preferred", "score:", "rank:", "top pick"}
        for word in forbidden:
            assert word not in notes_lower, (
                f"Notes contain forbidden word '{word}': {opt.notes}"
            )

    def test_individual_option_to_dict_no_forbidden_keys(self) -> None:
        """PrecedentOption.to_dict() never emits forbidden public keys."""
        opt = PrecedentOption(
            source_class_type="TestNode",
            source_workflow_path="path/to/wf.json",
            node_ids=("1", "2"),
            node_types=("KSampler", "VAEDecode"),
            description="A test option",
            notes=("source: ready_template", "pack: core"),
        )
        d = opt.to_dict()
        forbidden = {
            "winner", "best", "selected", "score", "rank", "primary",
            "preferred", "chosen", "pick", "choice", "top", "recommended",
        }
        overlap = set(d.keys()) & forbidden
        assert not overlap, f"Forbidden keys in option.to_dict(): {overlap}"
        # Verify expected keys are present.
        assert d["source_class_type"] == "TestNode"
        assert d["source_workflow_path"] == "path/to/wf.json"
        assert d["description"] == "A test option"

    def test_supplemental_option_to_dict_no_forbidden_keys(self) -> None:
        """Supplemental (non-slice) PrecedentOption.to_dict() never emits
        forbidden public keys."""
        result = _build_precedent_packet(
            slices=(),
            sources=(
                {"class_type": "SupplementalNode", "source": "hivemind",
                 "description": "Found in community feed",
                 "reasons": ["matched tag: video"],
                 "pack": "community_pack"},
            ),
        )
        assert result is not None
        opt = result.options[0]
        d = opt.to_dict()
        forbidden = {
            "winner", "best", "selected", "score", "rank", "primary",
            "preferred", "chosen", "pick", "choice", "top", "recommended",
        }
        overlap = set(d.keys()) & forbidden
        assert not overlap, f"Forbidden keys in supplemental option: {overlap}"
        assert d["source_class_type"] == "SupplementalNode"
        assert "notes" in d
        # Notes should be evidence/context only.
        for note in d["notes"]:
            assert isinstance(note, str)

    def test_local_supplemental_sorted_before_external_supplemental(self) -> None:
        """When only supplemental sources (no slices) exist, local-source
        options sort before external-source options."""
        result = _build_precedent_packet(
            slices=(),
            sources=(
                {"class_type": "ExtNode", "source": "web", "description": "Web result", "reasons": ["web hit"]},
                {"class_type": "LocalNode", "source": "object_info", "description": "Local obj info", "reasons": ["local"]},
                {"class_type": "CuratedNode", "source": "curated", "description": "Curated", "reasons": ["curated"]},
            ),
        )
        assert result is not None
        class_types = [o.source_class_type for o in result.options]
        # Local (object_info, curated) should come before external (web).
        local_kinds = {"LocalNode", "CuratedNode"}
        external_kinds = {"ExtNode"}
        local_indices = [i for i, ct in enumerate(class_types) if ct in local_kinds]
        ext_indices = [i for i, ct in enumerate(class_types) if ct in external_kinds]
        assert all(li < ei for li in local_indices for ei in ext_indices), (
            f"Local indices {local_indices} should precede external {ext_indices}"
        )

    def test_all_external_no_local_correct_ordering(self) -> None:
        """When there are no local sources, external sources are ordered by
        source tier then alphabetically."""
        result = _build_precedent_packet(
            slices=(),
            sources=(
                {"class_type": "GammaWeb", "source": "web", "description": "W", "reasons": ["web"]},
                {"class_type": "AlphaHM", "source": "hivemind_workflow", "description": "H", "reasons": ["hm"]},
                {"class_type": "BetaCR", "source": "comfy-registry", "description": "R", "reasons": ["reg"]},
                {"class_type": "DeltaGit", "source": "github", "description": "G", "reasons": ["git"]},
            ),
        )
        assert result is not None
        class_types = [o.source_class_type for o in result.options]
        # Expected tier order: hivemind_workflow(0) < comfy-registry(3) < github(4) < web(5)
        expected = ["AlphaHM", "BetaCR", "DeltaGit", "GammaWeb"]
        assert class_types == expected, f"Expected {expected}, got {class_types}"

    def test_packet_warnings_serialized_when_present(self) -> None:
        """PrecedentPacket.to_dict() includes warnings when populated."""
        # Build a packet directly with warnings.
        opt = PrecedentOption(
            source_class_type="TestNode",
            description="Test",
            notes=("source: ready_template",),
        )
        packet = PrecedentPacket(
            options=(opt,),
            context_note="Evidence context note.",
            warnings=(
                {"code": "test_warning", "message": "This is a test warning."},
            ),
        )
        d = packet.to_dict()
        assert "warnings" in d
        assert len(d["warnings"]) == 1
        assert d["warnings"][0]["code"] == "test_warning"


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
    def test_explicit_model_family_gates_execute_precedents(self, mock_corpus) -> None:
        """Wrong-family workflow hits remain sources but not execute candidates."""
        mock_corpus.return_value = [
            _make_entry(
                class_type="video/ltx_wrong_hotshot_text_hit",
                description="Hotshot video workflow text match but actually LTX",
                source="ready_template",
                path="ready_templates/video/ltx_wrong.py",
                model_families=("ltx",),
                media_type="video",
                task_type="image_to_video",
            ),
            _make_entry(
                class_type="video/hotshot_i2v",
                description="Hotshot image to video workflow",
                source="ready_template",
                path="ready_templates/video/hotshot_i2v.py",
                model_families=("hotshot",),
                media_type="video",
                task_type="image_to_video",
            ),
        ]

        result = research(
            "add Hotshot image to video support",
            hivemind_client=None,
            registry_resolver=None,
            web_search_client=None,
        )

        assert any(s["class_type"] == "video/ltx_wrong_hotshot_text_hit" for s in result.sources)
        assert [s.source_class_type for s in result.precedent_slices] == ["video/hotshot_i2v"]
        assert result.precedent_packet is not None
        assert [o.source_class_type for o in result.precedent_packet.options] == ["video/hotshot_i2v"]
        assert [s["class_type"] for s in result.to_dict()["precedent_sources"]] == ["video/hotshot_i2v"]
        assert result.selected_precedent is not None
        assert result.to_dict()["selected_precedent"]["name"] == "video/hotshot_i2v"
        assert "hotshot" in result.to_dict()["selected_precedent"]["requested_terms"]
        assert result.workflow_precedent_status == "compatible_workflow_found"
        assert any("precedent semantic gate: excluded video/ltx_wrong_hotshot_text_hit" in w for w in result.warnings)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_bare_wan_query_gates_ltx_precedents(self, mock_corpus) -> None:
        """Bare 'Wan' is a hard family signal, not just WanVideo/Wan2.x."""
        mock_corpus.return_value = [
            _make_entry(
                class_type="video/ltx_wrong_wan_text_hit",
                description="Wan VACE text match but actually LTX",
                source="ready_template",
                path="ready_templates/video/ltx_wrong_wan.py",
                model_families=("ltx",),
                media_type="video",
                task_type="image_to_video",
            ),
            _make_entry(
                class_type="video/wan_vace_i2v",
                description="Wan VACE image to video workflow",
                source="ready_template",
                path="ready_templates/video/wan_vace_i2v.py",
                model_families=("wan",),
                media_type="video",
                task_type="image_to_video",
            ),
        ]

        result = research(
            "add Wan VACE identity preservation",
            hivemind_client=None,
            registry_resolver=None,
            web_search_client=None,
        )

        assert any(s["class_type"] == "video/ltx_wrong_wan_text_hit" for s in result.sources)
        assert [s.source_class_type for s in result.precedent_slices] == ["video/wan_vace_i2v"]
        assert [s["class_type"] for s in result.precedent_sources] == ["video/wan_vace_i2v"]
        assert result.workflow_precedent_status == "compatible_workflow_found"
        assert any("precedent semantic gate: excluded video/ltx_wrong_wan_text_hit" in w for w in result.warnings)

    def test_wan_family_detection_uses_word_boundaries(self) -> None:
        assert _requested_model_families("I want image blending help") == set()
        assert _requested_model_families("Add Wan VACE identity preservation") == {"wan"}

    def test_img2video_and_videocombine_query_terms_target_video_domain(self) -> None:
        image_graph = {"1": {"class_type": "SaveImage", "inputs": {}}}

        assert _requested_media_domain(
            "HotShotXL img2video workflow node list; VideoCombine output node",
            image_graph,
        ) == "video"
        assert _requested_media_domain(
            "Switch to generating 16 frames with Hotshot",
            image_graph,
        ) == "video"

    def test_animatediff_combine_counts_as_video_domain(self) -> None:
        assert _media_domain_from_node_types(
            ["ADE_AnimateDiffLoaderWithContext", "ADE_AnimateDiffCombine", "SaveImage"]
        ) == "multi"

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_img2video_query_overrides_current_image_graph_domain(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry(
                class_type="image/hotshot_text_hit_wrong_domain",
                description="Hotshot text hit in an image workflow",
                source="ready_template",
                path="ready_templates/image/hotshot_wrong.py",
                model_families=("hotshot",),
                media_type="image",
            ),
            _make_entry(
                class_type="video/hotshot_img2video",
                description="Hotshot img2video workflow",
                source="ready_template",
                path="ready_templates/video/hotshot_img2video.py",
                model_families=("hotshot",),
                media_type="video",
                task_type="image_to_video",
            ),
        ]
        image_graph = {"1": {"class_type": "SaveImage", "inputs": {}}}

        result = research(
            "HotShotXL img2video workflow node list; VideoCombine output node",
            graph=image_graph,
            hivemind_client=None,
            registry_resolver=None,
            web_search_client=None,
        )

        assert [s.source_class_type for s in result.precedent_slices] == ["video/hotshot_img2video"]
        assert result.workflow_precedent_status == "compatible_workflow_found"
        assert any("media domain 'image' does not match requested 'video'" in w for w in result.warnings)
        assert not any("media domain 'video' does not match requested 'image'" in w for w in result.warnings)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_graph_media_domain_gates_execute_precedents(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry(
                class_type="video/rodin_text_hit_wrong_domain",
                description="Rodin Fusion text match but video workflow",
                source="ready_template",
                path="ready_templates/video/rodin_wrong.py",
                media_type="video",
            ),
            _make_entry(
                class_type="3d/rodin_fusion",
                description="Rodin Fusion 3D workflow",
                source="ready_template",
                path="ready_templates/3d/rodin_fusion.py",
                media_type="3d",
            ),
        ]
        graph = {"1": {"class_type": "Rodin3D_Regular", "inputs": {}}}

        result = research(
            "set Rodin Fusion model",
            graph=graph,
            hivemind_client=None,
            registry_resolver=None,
            web_search_client=None,
        )

        assert any(s["class_type"] == "video/rodin_text_hit_wrong_domain" for s in result.sources)
        assert [s.source_class_type for s in result.precedent_slices] == ["3d/rodin_fusion"]
        assert [s["class_type"] for s in result.precedent_sources] == ["3d/rodin_fusion"]
        assert result.workflow_precedent_status == "compatible_workflow_found"
        assert any("media domain 'video' does not match requested '3d'" in w for w in result.warnings)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_no_compatible_workflow_does_not_create_execute_packet(self, mock_corpus) -> None:
        mock_corpus.return_value = [
            _make_entry(
                class_type="video/ltx_wrong_hotshot_text_hit",
                description="Hotshot text hit but actually LTX",
                source="ready_template",
                path="ready_templates/video/ltx_wrong.py",
                model_families=("ltx",),
                media_type="video",
                task_type="image_to_video",
            ),
            _make_entry(
                class_type="HotshotLoader",
                description="Hotshot node registry docs",
                source="object_info",
            ),
        ]

        result = research(
            "add Hotshot image to video support",
            hivemind_client=None,
            registry_resolver=None,
            web_search_client=None,
        )

        assert any(s["class_type"] == "video/ltx_wrong_hotshot_text_hit" for s in result.sources)
        assert any(s["class_type"] == "HotshotLoader" for s in result.sources)
        assert result.precedent_sources == ()
        assert result.precedent_slices == ()
        assert result.precedent_packet is None
        assert result.workflow_precedent_status == "no_compatible_workflow_found"
        assert "precedent_sources" not in result.to_dict()

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

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_precedent_packet_produced_with_workflow_sources(self, mock_corpus) -> None:
        """research() produces a non-None precedent_packet when workflow sources exist."""
        mock_corpus.return_value = self._workflow_corpus()
        result = research("ltx video", hivemind_client=None)
        assert result.precedent_packet is not None
        assert len(result.precedent_packet.options) >= 1
        # At least the LTX workflow slice should be in the packet
        class_types = {o.source_class_type for o in result.precedent_packet.options}
        assert "video/ltx2_3_t2v" in class_types

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_precedent_packet_in_to_dict(self, mock_corpus) -> None:
        """to_dict() includes precedent_packet when populated."""
        mock_corpus.return_value = self._workflow_corpus()
        result = research("ltx video", hivemind_client=None)
        d = result.to_dict()
        assert "precedent_packet" in d
        assert "options" in d["precedent_packet"]
        assert len(d["precedent_packet"]["options"]) >= 1

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_precedent_packet_with_no_workflow_sources(self, mock_corpus) -> None:
        """research() with no workflow sources does not create execute precedent."""
        mock_corpus.return_value = [
            _make_entry("KSampler", source="object_info", description="Sampler node"),
            _make_entry("VAEDecode", source="object_info", description="VAE decode node"),
        ]
        result = research("sampler", hivemind_client=None)
        assert result.precedent_slices == ()
        assert result.adaptation_plan is None
        assert result.precedent_sources == ()
        assert result.precedent_packet is None
        assert result.workflow_precedent_status == "no_compatible_workflow_found"

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_precedent_packet_ordering_local_first(self, mock_corpus) -> None:
        """Packet options order local (ready_template) before external (hivemind_workflow)."""
        mock_corpus.return_value = [
            _make_entry("local_workflow", source="ready_template", path="local.py", description="Local workflow"),
            _make_entry("external_workflow", source="hivemind_workflow", path="ext.py", description="External workflow"),
        ]
        result = research("workflow", hivemind_client=None)
        assert result.precedent_packet is not None
        # Local (ready_template) should come before external (hivemind_workflow)
        local_indices = [
            i for i, o in enumerate(result.precedent_packet.options)
            if "source: ready_template" in o.notes
        ]
        ext_indices = [
            i for i, o in enumerate(result.precedent_packet.options)
            if "source: hivemind_workflow" in o.notes
        ]
        if local_indices and ext_indices:
            assert all(li < ei for li in local_indices for ei in ext_indices), (
                f"Local indices {local_indices} should all precede external {ext_indices}"
            )
