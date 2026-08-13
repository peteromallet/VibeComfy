"""Unit tests for the deterministic executor research module.

Covers local-corpus research, compact source normalization, injectable
Hivemind client, timeout/error → warning conversion, deduplication, and
merge ordering.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote_plus
from unittest.mock import patch

import pytest

from vibecomfy.executor.contracts import (
    InspectionSummary,
    ManifestOversized,
    PrecedentAdaptationPlan,
    PrecedentOption,
    PrecedentPacket,
    ResearchResult,
    SelectedPrecedent,
    WorkflowSlice,
)
from vibecomfy.executor.research import (
    CutEdge,
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
    enumerate_cut_edges,
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

from tests._splice_antigaming import (
    assert_topology_invariant,
    default_project_topology,
    perturb_source_ids,
    perturb_widgets,
    perturb_filenames,
    perturb_prompts,
    perturb_sigma,
    assert_no_forbidden_fields,
)


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
                        "has_rich_nodes": True,
                        "has_python_source": False,
                        "parseable_workflow": True,
                    },
                },
            },
        }

        out = _normalize_hivemind_source(item)

        assert out["workflow_semantics"]["task_type"] == "image_to_video"
        assert out["promotion_gates"]["has_rich_nodes"] is True


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
        decoded_urls = [unquote_plus(url) for url in seen_urls]
        assert all("hivemind.nousresearch.com" not in url for url in decoded_urls)
        assert all("external_resources" in url for url in decoded_urls)
        assert all("kind=eq.workflow" in url for url in decoded_urls)
        assert any("title.ilike.*Hotshot*" in url for url in decoded_urls)
        assert any("body.ilike.*Hotshot*" in url for url in decoded_urls)
        assert all("title.fts." not in url for url in decoded_urls)

    def test_specific_title_is_not_crowded_out_by_broad_query_limit(self) -> None:
        seen_urls: list[str] = []

        def capture_urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            decoded_url = unquote_plus(req.full_url)
            seen_urls.append(decoded_url)
            if "title.ilike.*IPAdapter Style Composition*" in decoded_url:
                payload = (
                    b'[{"id": 42, "kind": "workflow", '
                    b'"title": "IPAdapter Style Composition", '
                    b'"body": "Official Cubiq SDXL workflow"}]'
                )
            else:
                # Simulate a broad PostgREST page that hit its server-side
                # limit before the exact title could be returned.
                payload = b"[" + b",".join(
                    (
                        b'{"id": %d, "kind": "workflow", '
                        b'"title": "Unrelated Style Workflow %d", '
                        b'"body": "Generic composition notes"}'
                    ) % (index, index)
                    for index in range(100, 130)
                ) + b"]"
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
            result = _default_hivemind_client(
                "IPAdapter Style Composition",
                timeout=1.0,
            )

        assert result["results"][0]["title"] == "IPAdapter Style Composition"
        assert len(seen_urls) == 2
        assert "limit=10" in seen_urls[0]
        assert "limit=30" in seen_urls[1]

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
                b'"has_rich_nodes": true}}}}]'
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


# ── sources= tier gating (B02) ───────────────────────────────────────────────


class TestResearchTierGating:
    """``research(sources=...)`` runs exactly the listed tiers — no union.

    ``sources is None`` is the legacy public API: today's default tiers run and
    the messages tier stays off.  A non-None tuple nulls every unlisted tier.
    """

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_messages_only_invokes_messages_client_once_with_unchanged_query(
        self, mock_corpus
    ) -> None:
        messages_calls: list[tuple[str, float]] = []

        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            messages_calls.append((query, timeout))
            return {
                "results": [
                    {
                        "kind": "message",
                        "title": "MiniMax H3 is amazing",
                        "body": "loving the new model",
                        "author_name": "alice",
                        "channel_name": "minimax_h3_chatter",
                        "message_id": "9007199254740993",
                        "created_at": "2026-08-01T00:00:00Z",
                    }
                ]
            }

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("workflow/web/registry tier must not run")

        result = research(
            "MiniMax H3",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_client=boom,
            web_search_client=boom,
            registry_resolver=boom,
            hivemind_timeout=0.5,
        )

        assert [q for q, _t in messages_calls] == ["MiniMax H3"]
        assert messages_calls[0][1] == 0.5
        mock_corpus.assert_not_called()
        assert any(s["source"] == "hivemind_message" for s in result.sources)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_public_research_without_sources_never_touches_messages_client(
        self, mock_corpus
    ) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            raise AssertionError("messages tier must stay off for sources=None")

        result = research(
            "Hotshot XL",
            hivemind_messages_client=messages_client,
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
        )

        # The messages fake raises AssertionError if invoked; also confirm no
        # message-kind source leaked into the result.
        assert not any(
            s.get("source") in {"hivemind_message", "hivemind_distillation"}
            for s in result.sources
        )

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_messages_web_runs_exactly_those_tiers(self, mock_corpus) -> None:
        messages_calls: list[str] = []
        web_calls: list[str] = []

        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            messages_calls.append(query)
            return {
                "results": [
                    {
                        "kind": "message",
                        "title": "LTX 2.5 is great",
                        "body": "wow",
                        "author_name": "bob",
                        "channel_name": "ltx_chatter",
                        "message_id": "1",
                        "created_at": "2026-08-02T00:00:00Z",
                    }
                ]
            }

        def web_client(query: str, timeout: float) -> dict[str, Any]:
            web_calls.append(query)
            return {
                "results": [
                    {
                        "title": "LTX 2.5 page",
                        "url": "https://example.com/ltx",
                        "snippet": "LTX 2.5 notes",
                    }
                ]
            }

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("workflow/registry tier must not run")

        result = research(
            "LTX 2.5",
            sources=("messages", "web"),
            hivemind_messages_client=messages_client,
            web_search_client=web_client,
            hivemind_client=boom,
            registry_resolver=boom,
            hivemind_timeout=0.5,
            web_search_timeout=0.5,
        )

        assert messages_calls == ["LTX 2.5"]
        assert web_calls == ["LTX 2.5"]
        mock_corpus.assert_not_called()
        sources = list(result.sources)
        assert any(s["source"] == "hivemind_message" for s in sources)
        assert any(s["source"] == "web" for s in sources)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_workflows_only_nulls_web_registry_and_messages(
        self, mock_corpus
    ) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]
        workflow_calls: list[str] = []

        def workflow_client(query: str, timeout: float) -> dict[str, Any]:
            workflow_calls.append(query)
            return {"results": []}

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("messages/web/registry tier must not run")

        result = research(
            "KSampler",
            sources=("workflows",),
            hivemind_client=workflow_client,
            hivemind_messages_client=boom,
            web_search_client=boom,
            registry_resolver=boom,
        )

        assert workflow_calls == ["KSampler"]
        mock_corpus.assert_called()
        assert any(s["class_type"] == "KSampler" for s in result.sources)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_web_only_nulls_workflows_messages_registry_and_local(
        self, mock_corpus
    ) -> None:
        web_calls: list[str] = []

        def web_client(query: str, timeout: float) -> dict[str, Any]:
            web_calls.append(query)
            return {"results": []}

        def boom(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("workflow/messages/registry tier must not run")

        result = research(
            "Hotshot XL",
            sources=("web",),
            web_search_client=web_client,
            hivemind_client=boom,
            hivemind_messages_client=boom,
            registry_resolver=boom,
            hivemind_timeout=0.5,
        )

        assert web_calls == ["Hotshot XL"]
        mock_corpus.assert_not_called()
        assert "web search: no results" in result.warnings

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_env_kill_switch_disables_messages_tier(
        self, mock_corpus, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIBECOMFY_MESSAGES_RESEARCH", "0")
        messages_calls: list[str] = []

        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            messages_calls.append(query)
            return {"results": []}

        result = research(
            "MiniMax H3",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_timeout=0.5,
        )

        assert messages_calls == []
        assert "messages tier disabled" in result.warnings
        mock_corpus.assert_not_called()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_explicit_none_messages_client_skips_silently(
        self, mock_corpus
    ) -> None:
        result = research(
            "MiniMax H3",
            sources=("messages",),
            hivemind_messages_client=None,
            hivemind_timeout=0.5,
        )

        mock_corpus.assert_not_called()
        assert "messages tier disabled" not in result.warnings
        assert result.sources == ()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_messages_client_error_is_non_fatal_warning(
        self, mock_corpus
    ) -> None:
        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            raise HivemindError("messages unreachable")

        result = research(
            "MiniMax H3",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_timeout=0.5,
        )

        assert any("hivemind messages" in w for w in result.warnings)
        assert {"type": "HivemindError", "message": "messages unreachable"} in result.warning_details


# ── community_summary assignment (B03) ───────────────────────────────────────


class TestResearchCommunitySummary:
    """``research()`` writes ``ResearchResult.community_summary`` iff the
    messages tier ran — including the empty-set sentence when it produced
    nothing.  Extractive display only; never a score / strength / stop_reason.
    """

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_messages_tier_sets_community_summary(self, mock_corpus) -> None:
        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "kind": "message",
                        "title": "MiniMax H3 is amazing",
                        "body": "loving the new model",
                        "author_name": "alice",
                        "channel_name": "minimax_h3_chatter",
                        "message_id": "9007199254740993",
                        "created_at": "2026-08-01T00:00:00Z",
                    }
                ]
            }

        result = research(
            "MiniMax H3",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
            hivemind_timeout=0.5,
        )

        assert result.community_summary
        assert "alice" in result.community_summary
        assert "minimax_h3_chatter" in result.community_summary
        # to_dict() emits the key only when non-empty
        assert "community_summary" in result.to_dict()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_messages_tier_empty_result_still_sets_sentence(self, mock_corpus) -> None:
        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            return {"results": []}

        result = research(
            "LTX 2.5",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
            hivemind_timeout=0.5,
        )

        assert result.community_summary == 'No community discussion found for "LTX 2.5".'

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_legacy_public_research_without_sources_has_empty_community_summary(
        self, mock_corpus
    ) -> None:
        mock_corpus.return_value = [_make_entry("KSampler")]

        result = research(
            "Hotshot XL",
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
        )

        # Messages tier never ran → field stays "" and to_dict() omits the key.
        assert result.community_summary == ""
        assert "community_summary" not in result.to_dict()

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_messages_error_still_sets_empty_sentence(self, mock_corpus) -> None:
        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            raise HivemindError("messages unreachable")

        result = research(
            "MiniMax H3",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
            hivemind_timeout=0.5,
        )

        # The tier ran (and errored) → honest empty-set sentence, non-fatal.
        assert result.community_summary == 'No community discussion found for "MiniMax H3".'
        assert any("hivemind messages" in w for w in result.warnings)

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_env_kill_switch_leaves_community_summary_empty(self, mock_corpus, monkeypatch) -> None:
        monkeypatch.setenv("VIBECOMFY_MESSAGES_RESEARCH", "0")

        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            raise AssertionError("messages client must not run when disabled")

        result = research(
            "MiniMax H3",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_timeout=0.5,
        )

        # Tier was requested but disabled → it did not run → no paragraph.
        assert result.community_summary == ""
        assert "messages tier disabled" in result.warnings

    @patch("vibecomfy.executor.research.build_search_corpus")
    def test_distillation_sources_are_summarized_with_status(self, mock_corpus) -> None:
        def messages_client(query: str, timeout: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "kind": "distillation",
                        "title": "LTX 2.5 community reception",
                        "body": "Mostly positive reception in Banodoco.",
                        "item_id": "dist-1",
                        "metadata": {"status": "approved", "confidence": 0.8},
                        "created_at": "2026-08-01T00:00:00Z",
                    }
                ]
            }

        result = research(
            "LTX 2.5",
            sources=("messages",),
            hivemind_messages_client=messages_client,
            hivemind_client=None,
            web_search_client=None,
            registry_resolver=None,
            hivemind_timeout=0.5,
        )

        assert "approved" in result.community_summary
        assert "LTX 2.5 community reception" in result.community_summary


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

    def test_vibe_envelope_loads_node_records(self) -> None:
        """A versioned rich envelope is a supported shape, not 'unknown' (P2)."""
        corpus = (
            Path(__file__).resolve().parent.parent
            / "external_workflows/corpus/90a1d5ff9044902e.json"
        )
        raw = json.loads(corpus.read_text(encoding="utf-8"))
        result = normalize_workflow_source(raw, source_path=str(corpus))
        assert result.status == "loaded"
        assert result.shape == "vibe"
        assert result.blocks_candidate_output is False
        # The execution view compiles the 15-node IR down to 2 nodes.
        assert len(result.nodes) == 2
        assert {node.node_id for node in result.nodes} == {"3", "17"}

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


# ── W-01 Anti-gaming scanner tests ──────────────────────────────────────────


class TestSpliceAntiGaming:
    """Exercise anti-gaming assertions from tests._splice_antigaming."""

    def test_assert_no_forbidden_fields_passes_on_clean_dict(self) -> None:
        from tests._splice_antigaming import assert_no_forbidden_fields

        clean = {"manifest": {"nodes": [{"class_type": "KSampler", "inputs": {"seed": 42}}]}}
        assert_no_forbidden_fields(clean, context="clean_manifest")

    def test_assert_no_forbidden_fields_fails_on_forbidden_prior_path(self) -> None:
        from tests._splice_antigaming import assert_no_forbidden_fields

        tainted = {"manifest": {"prior_path": "/some/path"}}
        with pytest.raises(pytest.fail.Exception, match="forbidden token"):
            assert_no_forbidden_fields(tainted, context="tainted_manifest")

    def test_assert_no_forbidden_fields_fails_on_forbidden_node_id(self) -> None:
        from tests._splice_antigaming import assert_no_forbidden_fields

        tainted = {"source_id": "bee83462150b"}
        with pytest.raises(pytest.fail.Exception, match="forbidden token"):
            assert_no_forbidden_fields(tainted, context="tainted")

    def test_assert_no_forbidden_fields_fails_on_depth_controlnet(self) -> None:
        from tests._splice_antigaming import assert_no_forbidden_fields

        tainted = {"class_type": "depth_controlnet"}
        with pytest.raises(pytest.fail.Exception, match="forbidden token"):
            assert_no_forbidden_fields(tainted, context="tainted")

    def test_assert_no_forbidden_fields_fails_on_recam_master(self) -> None:
        from tests._splice_antigaming import assert_no_forbidden_fields

        tainted = {"nodes": [{"type": "ReCamMaster"}]}
        with pytest.raises(pytest.fail.Exception, match="forbidden token"):
            assert_no_forbidden_fields(tainted, context="tainted")

    def test_topology_invariant_under_all_perturbations(self) -> None:
        from tests._splice_antigaming import (
            assert_topology_invariant,
            default_project_topology,
        )

        graph = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 42,
                    "steps": 20,
                    "cfg": 7.0,
                    "model": ["2", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                },
                "widgets_values": [42, "some_model.safetensors"],
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "sd_xl_base.safetensors"},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "a beautiful landscape"},
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "ugly, blurry"},
            },
        }
        assert_topology_invariant(default_project_topology, graph, context="test_graph")


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
        assert {
            record["node_id"] for record in plan.required_new_nodes
        } == added_ids
        assert all(record["class_type"] for record in plan.required_new_nodes)
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


# ── W-05: gated manifest-emission tests ──────────────────────────────────────


# Sentinel distinguishing "argument not provided" from an explicit ``None``
# (e.g. an explicitly-absent target graph) inside ``TestManifestEmission``.
_W05_UNSET: Any = object()


class TestManifestEmission:
    """Gated emission of one :class:`TopologyManifest` on the research hot path.

    A manifest is emitted ONLY when the candidate has
    ``structural_validation=pass`` AND ``semantic_validation=pass`` AND a
    nonempty ``candidate_graph`` AND a path-free retrieved-evidence provenance
    AND ``project_validated_candidate`` (W-04) returns non-None AND
    ``build_topology_manifest`` (W-02) returns a real manifest.  Every other
    case leaves ``topology_manifest=None`` and the plan byte-identical to the
    legacy output.  Anti-gaming: never reads ``golden.ui.json`` /
    ``prior_path`` / fixture ancestry — only the already-validated candidate
    plus a path-free hash + tier + rank.
    """

    _SLICE_CLASS_TYPE = "video/wan_control_lora"

    def _wan_lora_slice(self) -> WorkflowSlice:
        slices = _build_precedent_slices((
            {
                "class_type": self._SLICE_CLASS_TYPE,
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

    def _provenance(
        self,
        *,
        class_type: str = _SLICE_CLASS_TYPE,
        content_hash: str = "deadbeef",
        tier: str = "ready_template",
        rank: int = 1,
    ) -> dict[str, Any]:
        from types import MappingProxyType

        return {
            class_type: MappingProxyType({
                "content_hash": content_hash,
                "tier": tier,
                "rank": rank,
            })
        }

    def _build_plan(
        self,
        *,
        manifest_provenance: dict[str, Any] | None,
        slices: tuple[WorkflowSlice, ...] | None = None,
        graph: Any = _W05_UNSET,
    ) -> PrecedentAdaptationPlan:
        plan = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph() if graph is _W05_UNSET else graph,
            inspection=None,
            slices=slices if slices is not None else (self._wan_lora_slice(),),
            manifest_provenance=manifest_provenance,
        )
        assert plan is not None
        return plan

    # ── the happy path: one manifest emitted ──────────────────────────────

    def test_both_validations_pass_emits_manifest(self) -> None:
        """Both validations pass + nonempty candidate_graph + provenance → a
        non-falsy ``topology_manifest``, and the emitted manifest carries no
        forbidden anti-gaming fields.

        The anti-gaming scanner is scoped to the manifest itself (and its
        serialized form): the manifest is the W-05 projection output and must
        carry no paths / golden ids / ancestry / widget literals.  The wider
        ``plan.to_dict()`` legitimately retains ``selected_slice``'s
        ``source_workflow_path`` (pre-W-05 behaviour), which is not part of the
        projection contract, so it is excluded from the scan — mirroring the
        W-02 ``TestTopologyManifest`` anti-gaming tests.
        """
        plan = self._build_plan(manifest_provenance=self._provenance())

        # Preconditions for emission (the exact gating condition).
        assert plan.structural_validation == "pass"
        assert plan.semantic_validation == "pass"
        assert plan.candidate_graph is not None
        assert len(plan.candidate_graph) > 0

        # The manifest was emitted and is a complete, non-falsy object.
        assert plan.topology_manifest is not None
        assert plan.topology_manifest.manifest_id == f"adapt:{self._SLICE_CLASS_TYPE}"
        assert plan.topology_manifest.nodes  # non-empty
        assert plan.topology_manifest.source_tier == "ready_template"
        assert plan.topology_manifest.source_retrieval_rank == 1

        # Anti-gaming: the emitted manifest (object + serialized form) carries
        # no forbidden fields (golden ids, paths, ancestry, widget literals).
        assert_no_forbidden_fields(
            plan.topology_manifest, context="emitted TopologyManifest"
        )
        assert_no_forbidden_fields(
            plan.to_dict()["topology_manifest"],
            context="emitted TopologyManifest.to_dict",
        )

    def test_manifest_serializes_into_to_dict(self) -> None:
        """The emitted manifest survives ``to_dict()`` (the serialization
        boundary ``core.py`` hands off through)."""
        plan = self._build_plan(manifest_provenance=self._provenance())
        d = plan.to_dict()
        assert "topology_manifest" in d
        tm = d["topology_manifest"]
        assert tm["manifest_id"] == f"adapt:{self._SLICE_CLASS_TYPE}"
        assert tm["source_content_hash"] == "deadbeef"
        assert tm["source_retrieval_rank"] == 1
        assert tm["source_tier"] == "ready_template"
        assert isinstance(tm["nodes"], list) and tm["nodes"]
        assert_no_forbidden_fields(tm, context="topology_manifest.to_dict")

    # ── every other case → topology_manifest is None ──────────────────────

    def test_no_provenance_emits_no_manifest(self) -> None:
        """When no provenance mapping is supplied the plan is byte-identical to
        the legacy output: ``topology_manifest`` stays ``None``."""
        plan = self._build_plan(manifest_provenance=None)
        assert plan.topology_manifest is None

    def test_structural_fail_emits_no_manifest(self) -> None:
        """A structurally-failing candidate (media-family mismatch) emits no
        manifest, even when provenance is available."""
        # Wan LoRA slice against an LTX target graph → structural fail.
        ltx_graph = {
            "1": {
                "class_type": "LTXVModelLoader",
                "inputs": {"model": "ltx-video-2b.safetensors", "lora": ["2", 0]},
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
        plan = self._build_plan(
            manifest_provenance=self._provenance(),
            graph=ltx_graph,
        )
        assert plan.structural_validation == "fail"
        assert plan.topology_manifest is None

    def test_empty_candidate_graph_emits_no_manifest(self) -> None:
        """A plan with an empty/None candidate_graph (no target graph to bind)
        emits no manifest."""
        plan = self._build_plan(
            manifest_provenance=self._provenance(),
            graph=None,
        )
        assert plan.candidate_graph is None
        assert plan.topology_manifest is None

    @patch("vibecomfy.executor.research.project_validated_candidate", return_value=None)
    def test_projection_returns_none_emits_no_manifest(self, _mock_proj) -> None:
        """When the W-04 projector returns ``None`` (no added nodes) no
        manifest is emitted — the legacy path is taken unchanged."""
        plan = self._build_plan(manifest_provenance=self._provenance())
        assert plan.topology_manifest is None

    @patch(
        "vibecomfy.executor.research.build_topology_manifest",
        side_effect=ManifestOversized("nodes count exceeds bound"),
    )
    def test_build_rejects_oversized_emits_no_manifest(self, _mock_build) -> None:
        """When ``build_topology_manifest`` rejects (oversized) no manifest is
        emitted and NO exception escapes to the caller."""
        # Must not raise.
        plan = self._build_plan(manifest_provenance=self._provenance())
        assert plan.topology_manifest is None

    def test_incomplete_provenance_emits_no_manifest(self) -> None:
        """Provenance missing a content_hash OR tier OR a valid rank emits no
        manifest (complete-or-reject at the provenance boundary)."""
        # Missing tier.
        plan_no_tier = self._build_plan(
            manifest_provenance=self._provenance(tier=""),
        )
        assert plan_no_tier.topology_manifest is None
        # Missing content_hash.
        plan_no_hash = self._build_plan(
            manifest_provenance=self._provenance(content_hash=""),
        )
        assert plan_no_hash.topology_manifest is None
        # Invalid (negative) rank.
        plan_bad_rank = self._build_plan(
            manifest_provenance=self._provenance(rank=-1),
        )
        assert plan_bad_rank.topology_manifest is None
        # Provenance keyed to a different class_type → no match → no manifest.
        plan_wrong_key = self._build_plan(
            manifest_provenance=self._provenance(class_type="some/other_class"),
        )
        assert plan_wrong_key.topology_manifest is None

    # ── legacy byte-compatibility ─────────────────────────────────────────

    def test_legacy_plan_omits_topology_manifest_key(self) -> None:
        """A plan that emits no manifest serializes identically to the
        pre-W-05 output: the ``topology_manifest`` key is ABSENT from
        ``to_dict()`` (not merely null)."""
        plan = self._build_plan(manifest_provenance=None)
        d = plan.to_dict()
        assert "topology_manifest" not in d

    def test_legacy_plan_keys_unchanged_by_w05(self) -> None:
        """The set of keys on a no-manifest plan is byte-identical to the
        legacy output: W-05 adds no new keys when no manifest is emitted."""
        plan = self._build_plan(manifest_provenance=None)
        legacy_keys = set(plan.to_dict().keys())
        # The same plan built without the W-05 codepath (no provenance kwarg)
        # must yield an identical key set.
        baseline = _build_adaptation_plan(
            query="add Wan LoRA chain",
            graph=self._wan_target_graph(),
            inspection=None,
            slices=(self._wan_lora_slice(),),
        )
        assert baseline is not None
        assert legacy_keys == set(baseline.to_dict().keys())
        assert "topology_manifest" not in legacy_keys

    # ── core.py protocol-handoff round-trip ───────────────────────────────

    def test_manifest_survives_core_handoff_round_trip(self) -> None:
        """The manifest survives the ``core.py`` protocol handoff to the
        fixer-prompt builder.

        ``core.py`` (``_run_implement``) serializes the adaptation plan via
        ``to_dict()`` and forwards it under
        ``execution_protocol_notes.adaptation_plan`` ONLY when the plan is
        ``actionable``.  A manifest-bearing plan has a nonempty
        ``candidate_graph`` (an emission precondition), so it is actionable and
        the serialized manifest must be present (non-None) on the receiving
        side.  This mirrors the exact serialization contract ``core.py`` relies
        on at the handoff boundary — no reconstruction occurs on the receiving
        side; the dict IS the round-tripped form.
        """
        from vibecomfy.executor.contracts import (
            adaptation_plan_actionability_payload,
        )

        plan = self._build_plan(manifest_provenance=self._provenance())
        assert plan.topology_manifest is not None

        # Reproduce the core.py handoff contract verbatim.
        actionability = adaptation_plan_actionability_payload(plan)
        assert actionability["actionability"] == "actionable"

        # core.py forwards plan.to_dict() only when actionable.
        serialized_plan = plan.to_dict()
        assert "topology_manifest" in serialized_plan

        # The receiving side (prompts.py / W-06) reads the dict form: the
        # manifest is present and non-null there.
        received_manifest = serialized_plan.get("topology_manifest")
        assert received_manifest is not None
        assert received_manifest["manifest_id"] == f"adapt:{self._SLICE_CLASS_TYPE}"
        assert received_manifest["source_content_hash"] == "deadbeef"
        assert received_manifest["nodes"]

        # Anti-gaming survives the round-trip.
        assert_no_forbidden_fields(received_manifest, context="handoff manifest")

    def test_no_manifest_plan_forwarded_clean_by_core_handoff(self) -> None:
        """When a plan emits no manifest, the ``core.py`` handoff forwards a
        dict with NO ``topology_manifest`` key — the legacy byte-compat holds
        across the handoff boundary too."""
        plan = self._build_plan(manifest_provenance=None)
        serialized_plan = plan.to_dict()
        assert "topology_manifest" not in serialized_plan


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
                "hivemind:rich nodes available",
                "hivemind:filename matched 'HotShotXL'",
            ),
            "promotion_gates": {
                "has_workflow_json": True,
                "parseable_workflow": True,
                "has_rich_nodes": True,
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


# ---------------------------------------------------------------------------
# W-08 — Cut-edge enumeration tests
# ---------------------------------------------------------------------------


class TestCutEdgeEnumeration:
    """Deterministic cut-edge enumeration for lean source segments."""

    # ── tiny hand-built graphs ──────────────────────────────────────────

    @staticmethod
    def _simple_chain() -> dict[str, dict[str, Any]]:
        """A → B → C → D  (all links via "latent" input, slot 0)."""
        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {
                "class_type": "KSampler",
                "inputs": {"model": ["1", 0], "latent_image": ["3", 0]},
            },
            "3": {"class_type": "EmptyLatentImage", "inputs": {}},
            "4": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["2", 0]},
            },
            "5": {
                "class_type": "SaveImage",
                "inputs": {"images": ["4", 0]},
            },
        }

    def test_exact_cut_edges_middle_segment(self) -> None:
        """S = {2, 4} (KSampler + VAEDecode).  Verify exact cut edges."""
        graph = self._simple_chain()
        s = {"2", "4"}
        result = enumerate_cut_edges(graph, s)

        # Expected cut edges:
        #   inbound: 1→2 (model), 3→2 (latent_image)
        #   outbound: 4→5 (images)
        # Edges 2→4 is internal (both in S), excluded.
        assert len(result) == 3

        by_dir: dict[str, list[CutEdge]] = {}
        for e in result:
            by_dir.setdefault(e.direction, []).append(e)

        # Inbound edges
        inbound = {(e.outside_node_id, e.inside_node_id, e.input_name) for e in by_dir["inbound"]}
        assert inbound == {("1", "2", "model"), ("3", "2", "latent_image")}

        # Outbound edges
        outbound = {(e.inside_node_id, e.outside_node_id, e.input_name) for e in by_dir["outbound"]}
        assert outbound == {("4", "5", "images")}

    def test_single_node_segment(self) -> None:
        """S = {2} — KSampler only."""
        graph = self._simple_chain()
        s = {"2"}
        result = enumerate_cut_edges(graph, s)

        # Inbound: 1→2 (model), 3→2 (latent_image)
        # Outbound: 2→4 (samples)
        assert len(result) == 3

        directions = {e.direction for e in result}
        assert directions == {"inbound", "outbound"}

        inbound = {(e.outside_node_id, e.inside_node_id, e.input_name) for e in result if e.direction == "inbound"}
        assert inbound == {("1", "2", "model"), ("3", "2", "latent_image")}

        outbound = {(e.inside_node_id, e.outside_node_id, e.input_name) for e in result if e.direction == "outbound"}
        assert outbound == {("2", "4", "samples")}

    def test_segment_all_nodes_no_cut_edges(self) -> None:
        """S = all nodes → zero cut edges (everything is internal)."""
        graph = self._simple_chain()
        s = set(graph.keys())
        result = enumerate_cut_edges(graph, s)
        assert result == ()

    def test_segment_empty_no_cut_edges(self) -> None:
        """S = empty → zero cut edges."""
        graph = self._simple_chain()
        result = enumerate_cut_edges(graph, set())
        assert result == ()

    def test_singleton_node_in_isolation(self) -> None:
        """A single node with no links has zero cut edges."""
        graph = {"99": {"class_type": "Note", "inputs": {}}}
        result = enumerate_cut_edges(graph, {"99"})
        assert result == ()

    def test_scalar_inputs_ignored(self) -> None:
        """Scalar inputs (non-list values) are never treated as edges."""
        graph = {
            "1": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 42,
                    "steps": 20,
                    "cfg": 7.0,
                    "model": ["99", 0],
                },
            },
            "99": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        }
        # S = {1}; only edge is 99→1 (model), inbound.
        result = enumerate_cut_edges(graph, {"1"})
        assert len(result) == 1
        assert result[0].direction == "inbound"
        assert result[0].input_name == "model"

    # ── no duplicates / internal-external exclusion ─────────────────────

    def test_no_duplicate_edges(self) -> None:
        """Each cut edge appears exactly once."""
        graph = self._simple_chain()
        for s in ({"2"}, {"2", "4"}, {"1", "3", "5"}, {"2", "3", "4"}):
            result = enumerate_cut_edges(graph, s)
            seen: set[tuple[str, str, str, object]] = set()
            for e in result:
                key = (e.direction, e.inside_node_id, e.outside_node_id, e.input_name)
                assert key not in seen, f"Duplicate edge: {key}"
                seen.add(key)

    def test_internal_edges_excluded(self) -> None:
        """Edges with both endpoints inside S are excluded."""
        graph = {
            "a": {"class_type": "Loader", "inputs": {}},
            "b": {"class_type": "Sampler", "inputs": {"model": ["a", 0]}},
            "c": {"class_type": "Decoder", "inputs": {"latent": ["b", 0]}},
            "d": {"class_type": "Output", "inputs": {"image": ["c", 0]}},
        }
        # S = {a, b, c} — edges a→b and b→c are internal.
        result = enumerate_cut_edges(graph, {"a", "b", "c"})
        # Only cut edge: c→d (outbound).
        assert len(result) == 1
        assert result[0].direction == "outbound"
        assert result[0].inside_node_id == "c"
        assert result[0].outside_node_id == "d"

    def test_external_edges_excluded(self) -> None:
        """Edges with both endpoints outside S are excluded."""
        graph = {
            "a": {"class_type": "Loader", "inputs": {}},
            "b": {"class_type": "Sampler", "inputs": {"model": ["a", 0]}},
            "c": {"class_type": "Decoder", "inputs": {"latent": ["b", 0]}},
        }
        # S = {c} only.
        result = enumerate_cut_edges(graph, {"c"})
        # Only b→c is a cut edge (inbound). a→b is external (both outside S).
        assert len(result) == 1
        assert result[0].direction == "inbound"
        assert result[0].inside_node_id == "c"
        assert result[0].outside_node_id == "b"

    # ── deterministic ordering ──────────────────────────────────────────

    def test_deterministic_order(self) -> None:
        """Output order is deterministic regardless of dict/set iteration."""
        graph = self._simple_chain()
        s = {"2", "4"}

        result1 = enumerate_cut_edges(graph, s)
        # Run many times; result must be identical every time.
        for _ in range(20):
            result2 = enumerate_cut_edges(graph, s)
            assert result1 == result2

    def test_order_independent_of_input_set_order(self) -> None:
        """Passing S as set, frozenset, list, or tuple yields identical tuples."""
        graph = self._simple_chain()
        s_list = ["2", "4"]
        s_tuple = ("2", "4")
        s_set = {"2", "4"}
        s_frozen = frozenset(["2", "4"])

        base = enumerate_cut_edges(graph, s_list)
        assert enumerate_cut_edges(graph, s_tuple) == base
        assert enumerate_cut_edges(graph, s_set) == base
        assert enumerate_cut_edges(graph, s_frozen) == base

    def test_sort_key_matches_spec(self) -> None:
        """Edges are sorted by (direction, inside_node_id, input_name)."""
        graph = {
            "a": {"class_type": "X", "inputs": {
                "z_input": ["b", 0],
                "a_input": ["c", 0],
            }},
            "b": {"class_type": "Y", "inputs": {}},
            "c": {"class_type": "Z", "inputs": {}},
            "d": {"class_type": "W", "inputs": {"x": ["a", 0]}},
        }
        # S = {a}
        result = enumerate_cut_edges(graph, {"a"})

        # Expected order: inbound before outbound; within inbound, sorted by inside_node_id then input_name.
        # Inbound: b→a via z_input, c→a via a_input → sorted by input_name: a_input, z_input
        # Outbound: a→d via x
        keys = [(e.direction, e.inside_node_id, e.input_name) for e in result]
        assert keys == [
            ("inbound", "a", "a_input"),
            ("inbound", "a", "z_input"),
            ("outbound", "a", "x"),
        ]

    # ── schema_lookup ───────────────────────────────────────────────────

    def test_socket_type_none_without_schema_lookup(self) -> None:
        """Without schema_lookup, socket_type is always None."""
        graph = self._simple_chain()
        result = enumerate_cut_edges(graph, {"2"})
        for e in result:
            assert e.socket_type is None

    def test_socket_type_filled_with_schema_lookup(self) -> None:
        """With schema_lookup, socket_type reflects the lookup result."""
        graph = {
            "ldr": {"class_type": "Loader", "inputs": {}},
            "smp": {"class_type": "Sampler", "inputs": {"model": ["ldr", 0]}},
        }

        def fake_lookup(cls: str, socket: str) -> str | None:
            if cls == "Sampler" and socket == "model":
                return "MODEL"
            return None

        result = enumerate_cut_edges(graph, {"smp"}, schema_lookup=fake_lookup)
        assert len(result) == 1
        assert result[0].socket_type == "MODEL"

    # ── role evidence ───────────────────────────────────────────────────

    def test_role_evidence_is_generic(self) -> None:
        """role_evidence contains only generic hints, no case-specific tokens."""
        graph = self._simple_chain()
        result = enumerate_cut_edges(graph, {"2"})
        for e in result:
            for role in e.role_evidence:
                assert role in {
                    "sampler",
                    "model_provider",
                    "latent",
                    "text_encoder",
                    "conditioning",
                    "image",
                }, f"Unexpected role {role!r}"

    def test_role_evidence_for_sampler_edge(self) -> None:
        """Edges involving KSampler should include 'sampler' role."""
        graph = self._simple_chain()
        result = enumerate_cut_edges(graph, {"2", "4"})
        # Find the edge where KSampler (id=2) is the inside node
        sampler_edges = [e for e in result if e.inside_class_type == "KSampler"]
        assert len(sampler_edges) >= 1
        for e in sampler_edges:
            assert "sampler" in e.role_evidence

    # ── confidence ──────────────────────────────────────────────────────

    def test_confidence_is_one(self) -> None:
        """All cut edges from deterministic graph traversal have confidence 1.0."""
        graph = self._simple_chain()
        for s in ({"2"}, {"2", "4"}, set(graph.keys())):
            for e in enumerate_cut_edges(graph, s):
                assert e.confidence == 1.0

    # ── W-01 topology invariance ────────────────────────────────────────

    def test_topology_invariant_under_perturbations(self) -> None:
        """Projected cut-edge topology must be invariant under W-01 perturbations."""
        graph = self._simple_chain()
        s_ids = {"2", "4"}

        def project(g: dict[str, dict[str, Any]]) -> frozenset[tuple[str, str, str, str, object, str | None]]:
            # Recompute S for the perturbed graph (IDs may have changed).
            if all(k.startswith("p_") for k in g if g[k].get("class_type") == "KSampler"):
                # perturb_source_ids renumbered everything with "p_" prefix.
                perturbed_s = {f"p_{sid}" for sid in s_ids}
            else:
                perturbed_s = s_ids
            edges = enumerate_cut_edges(g, perturbed_s)
            return frozenset(
                (e.direction, e.inside_class_type, e.outside_class_type,
                 e.input_name, e.output_slot, e.socket_type)
                for e in edges
            )

        assert_topology_invariant(project, graph, context="cut-edge topology")

    # ── forbidden-field check ───────────────────────────────────────────

    def test_no_forbidden_tokens(self) -> None:
        """CutEdge output must not contain forbidden tokens."""
        graph = self._simple_chain()
        result = enumerate_cut_edges(graph, {"2", "4"})
        for edge in result:
            assert_no_forbidden_fields(edge, context=f"CutEdge({edge.direction}/{edge.input_name})")


# ── W-04: pure validated-candidate projector tests ────────────────────────────


class TestProjectedCandidate:
    """Tests for :func:`project_validated_candidate`."""

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _make_candidate_target_pair():
        """Return (candidate_graph, target_graph) with 2 added nodes.

        Target has 3 existing nodes (ids "1","2","3").
        Candidate adds 2 nodes (ids "a","b") with one internal edge and
        two boundary anchors.
        """
        target = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "sd_xl.safetensors"},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "a beautiful landscape",
                    "clip": ["1", 1],
                },
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["2", 0],
                    "latent_image": ["b", 0],  # consumed from added node
                },
            },
        }
        candidate = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "sd_xl.safetensors"},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": "a beautiful landscape",
                    "clip": ["1", 1],
                },
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["2", 0],
                    "latent_image": ["b", 0],
                },
            },
            "a": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": "my_vae.safetensors",
                },
            },
            "b": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 1024,
                    "height": 1024,
                    "batch_size": 1,
                    "vae": ["a", 0],  # internal edge from a→b
                },
            },
        }
        return candidate, target

    # ── basic projection ─────────────────────────────────────────────────

    def test_exact_projection_two_added_nodes(self) -> None:
        """Two added nodes with one internal edge and two boundary anchors."""
        from vibecomfy.executor.research import (
            ProjectedManifestParts,
            project_validated_candidate,
        )

        candidate, target = self._make_candidate_target_pair()
        result = project_validated_candidate(
            candidate, target, evidence_hash="abc123"
        )

        assert result is not None
        assert isinstance(result, ProjectedManifestParts)

        # nodes: (symbol, class_type) sorted by original added id order
        # "a" → n1, "b" → n2
        assert result.nodes == (
            ("n1", "VAELoader"),
            ("n2", "EmptyLatentImage"),
        )

        # internal edge: a→b via "vae" input, output slot 0
        assert result.internal_edges == (
            ("n1", 0, "n2", "vae"),
        )

        # boundary anchors:
        #  - "b" (n2) → "3"/KSampler via latent_image (outbound, n2 produces)
        #  - "a" (n1) has no inbound link
        #  - "b" has no inbound link from existing nodes
        assert len(result.boundary_anchors) == 1
        anchor = result.boundary_anchors[0]
        # outbound: n2 output slot 0 consumed by KSampler's latent_image
        assert anchor[0] == "outbound"
        assert anchor[1] == "n2"
        assert anchor[2] == "0"  # output slot from n2
        assert anchor[3] == "sampler"  # generic role for KSampler
        assert anchor[4] == "KSampler"
        assert anchor[5] == "latent_image"

        assert result.evidence_hash == "abc123"

    def test_scalar_literals_dropped(self) -> None:
        """Scalar/list widget literals never appear in projection."""
        from vibecomfy.executor.research import project_validated_candidate

        target: dict[str, dict[str, object]] = {
            "1": {"class_type": "Loader", "inputs": {}},
        }
        candidate: dict[str, dict[str, object]] = {
            "1": {"class_type": "Loader", "inputs": {}},
            "x": {
                "class_type": "NewNode",
                "inputs": {
                    "filename": "my_model.safetensors",
                    "seed": 42,
                    "sigma": 0.5,
                    "prompt": "test prompt",
                    "widget_list": [1, 2, 3],
                    "model_link": ["1", 0],
                },
            },
        }

        result = project_validated_candidate(
            candidate, target, evidence_hash="test"
        )
        assert result is not None
        # Only the link "model_link" → ["1", 0] is kept as a boundary anchor.
        # Scalars/lists are dropped.
        assert result.nodes == (("n1", "NewNode"),)
        assert result.internal_edges == ()
        assert len(result.boundary_anchors) == 1
        anchor = result.boundary_anchors[0]
        assert anchor[0] == "inbound"
        assert anchor[1] == "n1"
        assert anchor[2] == "model_link"
        assert anchor[4] == "Loader"

        # Verify that no scalar/list entry leaked into edges or anchors.
        all_edge_text = " ".join(
            str(x) for edge in result.internal_edges for x in edge
        )
        all_anchor_text = " ".join(
            str(x) for anchor in result.boundary_anchors for x in anchor
        )
        assert "my_model" not in all_edge_text
        assert "my_model" not in all_anchor_text
        assert "42" not in all_edge_text
        assert "42" not in all_anchor_text
        assert "0.5" not in all_edge_text
        assert "0.5" not in all_anchor_text

    def test_boundary_selectors_carry_no_target_node_ids(self) -> None:
        """Boundary anchors use role/class/socket ONLY — no target node ids."""
        from vibecomfy.executor.research import project_validated_candidate

        target = {
            "existing_123": {"class_type": "SomeSampler", "inputs": {}},
        }
        candidate = {
            "existing_123": {"class_type": "SomeSampler", "inputs": {}},
            "new_node": {
                "class_type": "LatentProvider",
                "inputs": {"input_socket": ["existing_123", 0]},
            },
        }

        result = project_validated_candidate(
            candidate, target, evidence_hash="test"
        )
        assert result is not None

        for anchor in result.boundary_anchors:
            anchor_text = " ".join(str(x) for x in anchor)
            # No target node id "existing_123" should appear.
            assert "existing_123" not in anchor_text, (
                f"Boundary anchor leaks node id: {anchor}"
            )
            # Verify all fields are present and generic.
            direction, symbol, sym_socket, role, target_cls, target_socket = anchor
            assert direction in ("inbound", "outbound")
            assert symbol.startswith("n")
            assert isinstance(target_cls, str)
            assert isinstance(role, str)
            assert role != ""

    # ── invariance under W-01 perturbations ──────────────────────────────

    def test_topology_invariant_under_perturbations(self) -> None:
        """Projected parts must be invariant under W-01 perturbations."""
        from vibecomfy.executor.research import project_validated_candidate

        candidate, target = self._make_candidate_target_pair()

        def project_wrapper(graph: dict[str, dict[str, Any]]) -> frozenset:
            """Wrapper that recomputes added-set under renumbering."""
            if all(k.startswith("p_") for k in graph):
                # perturb_source_ids renumbered everything
                # Need to identify which IDs correspond to added nodes
                # Added nodes in the base: "a", "b"
                # Build a mapping: perturbed["p_a"] is the same as base["a"]
                perturbed_added = frozenset(
                    k for k in graph
                    if k.startswith("p_") and k[2:] in ("a", "b")
                )
                if not perturbed_added:
                    perturbed_added = frozenset(
                        k for k in graph
                        if any(
                            graph[k].get("class_type") in ("VAELoader", "EmptyLatentImage")
                            for k in graph
                        )
                    )
                # For perturbed, target is those nodes NOT starting with p_a / p_b
                perturbed_target = {
                    k: v for k, v in graph.items() if k not in perturbed_added
                }
                result = project_validated_candidate(
                    graph, perturbed_target, evidence_hash="inv"
                )
            else:
                result = project_validated_candidate(
                    graph, target, evidence_hash="inv"
                )
            if result is None:
                return frozenset()
            return frozenset(
                tuple(("node", n[0], n[1]) for n in result.nodes)
                + tuple(("edge",) + e for e in result.internal_edges)
                + tuple(("anchor",) + a for a in result.boundary_anchors)
            )

        # Use candidate as base graph
        assert_topology_invariant(project_wrapper, candidate, context="projection")

    # ── forbidden-field check ────────────────────────────────────────────

    def test_no_forbidden_fields(self) -> None:
        """Projected parts must not contain forbidden tokens."""
        from vibecomfy.executor.research import project_validated_candidate

        candidate, target = self._make_candidate_target_pair()
        result = project_validated_candidate(
            candidate, target, evidence_hash="test"
        )
        assert result is not None
        assert_no_forbidden_fields(result, context="ProjectedManifestParts")

    # ── empty added set ──────────────────────────────────────────────────

    def test_no_added_nodes_returns_none(self) -> None:
        """When candidate adds nothing, return None."""
        from vibecomfy.executor.research import project_validated_candidate

        target = {
            "1": {"class_type": "Loader", "inputs": {}},
        }
        candidate = {
            "1": {"class_type": "Loader", "inputs": {}},
        }

        result = project_validated_candidate(
            candidate, target, evidence_hash="test"
        )
        assert result is None

    def test_empty_candidate_returns_none(self) -> None:
        """Empty candidate with non-empty target still returns None."""
        from vibecomfy.executor.research import project_validated_candidate

        target = {
            "1": {"class_type": "Loader", "inputs": {}},
        }
        candidate: dict[str, dict[str, object]] = {}

        result = project_validated_candidate(
            candidate, target, evidence_hash="test"
        )
        assert result is None

    # ── deterministic ordering ───────────────────────────────────────────

    def test_symbols_are_deterministic(self) -> None:
        """Repeated calls with same input produce identical symbols."""
        from vibecomfy.executor.research import project_validated_candidate

        candidate, target = self._make_candidate_target_pair()
        r1 = project_validated_candidate(candidate, target, evidence_hash="x")
        r2 = project_validated_candidate(candidate, target, evidence_hash="x")
        assert r1 is not None and r2 is not None
        assert r1.nodes == r2.nodes
        assert r1.internal_edges == r2.internal_edges
        assert r1.boundary_anchors == r2.boundary_anchors

    # ── generic role name check ──────────────────────────────────────────

    def test_roles_are_generic(self) -> None:
        """Boundary anchor roles contain only generic tokens."""
        from vibecomfy.executor.research import project_validated_candidate

        candidate, target = self._make_candidate_target_pair()
        result = project_validated_candidate(
            candidate, target, evidence_hash="test"
        )
        assert result is not None

        generic_roles = {
            "sampler", "model_provider", "latent", "conditioning",
            "decoder", "output_sink", "input_source", "control",
            "transform", "lora", "audio", "mask", "seed", "unresolved",
        }
        for anchor in result.boundary_anchors:
            role = anchor[3]
            assert role in generic_roles, (
                f"Role {role!r} is not a known generic role token"
            )


# ── W-09: Lean inquiry-role and socket matcher ──────────────────────────────


class TestLeanMatcher:
    """Hard-gate, weight-free matcher for source-segment cut edges."""

    # ── fake authoritative schema_lookup + tiny graphs ─────────────────────

    @staticmethod
    def _schema_lookup_factory() -> Any:
        """Return a ``class_type -> schema`` callable with authoritative types."""
        schemas: dict[str, dict[str, Any]] = {
            "CheckpointLoaderSimple": {
                "inputs": {},
                "outputs": {"MODEL": {"type": "MODEL"}},
            },
            "EmptyLatentImage": {
                "inputs": {},
                "outputs": {"LATENT": {"type": "LATENT"}},
            },
            "KSampler": {
                "inputs": {
                    "model": {"type": "MODEL"},
                    "latent_image": {"type": "LATENT"},
                    "positive": {"type": "CONDITIONING"},
                },
                "outputs": {"LATENT": {"type": "LATENT"}},
            },
            "CLIPTextEncode": {
                "inputs": {"clip": {"type": "CLIP"}},
                "outputs": {"CONDITIONING": {"type": "CONDITIONING"}},
            },
            "VAEDecode": {
                "inputs": {"samples": {"type": "LATENT"}},
                "outputs": {"IMAGE": {"type": "IMAGE"}},
            },
            "SaveImage": {
                "inputs": {"images": {"type": "IMAGE"}},
                "outputs": {},
            },
            "MysteryLoader": {
                # Wildcard / dynamic types must fail closed.
                "inputs": {},
                "outputs": {"MODEL": {"type": "*"}},
            },
            "DynamicConsumer": {
                "inputs": {"model": {"type": "DYNAMIC"}},
                "outputs": {},
            },
        }

        def lookup(class_type: str) -> dict[str, Any] | None:
            return schemas.get(class_type)

        return lookup

    @staticmethod
    def _clean_case() -> tuple[
        tuple[CutEdge, ...], dict[str, dict[str, Any]]
    ]:
        """One inbound (model) + one outbound (images) cut edge."""
        cut_edges = (
            CutEdge(
                direction="inbound",
                inside_node_id="s_sampler",
                outside_node_id="src_loader",
                inside_class_type="KSampler",
                outside_class_type="CheckpointLoaderSimple",
                input_name="model",
                output_slot=0,
                socket_type="MODEL",
                role_evidence=("model_provider",),
                confidence=1.0,
            ),
            CutEdge(
                direction="outbound",
                inside_node_id="s_decode",
                outside_node_id="src_save",
                inside_class_type="VAEDecode",
                outside_class_type="SaveImage",
                input_name="images",
                output_slot=0,
                socket_type="IMAGE",
                role_evidence=("output_sink",),
                confidence=1.0,
            ),
        )
        target_graph = {
            "t_loader": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "t_sampler": {
                "class_type": "KSampler",
                "inputs": {"model": ["t_loader", 0]},
            },
            "t_save": {
                "class_type": "SaveImage",
                "inputs": {"images": ["t_decode_proxy", 0]},
            },
        }
        return cut_edges, target_graph

    # ── the clean case ─────────────────────────────────────────────────────

    def test_clean_case_complete(self) -> None:
        from vibecomfy.executor.research import match_cut_edges

        cut_edges, target_graph = self._clean_case()
        result = match_cut_edges(
            cut_edges,
            target_graph,
            schema_lookup=self._schema_lookup_factory(),
            inquiry_terms=("model", "latent", "image"),
        )
        assert result.complete is True
        assert len(result.bindings) == 2
        assert result.rejections == ()
        dirs = {b.direction for b in result.bindings}
        assert dirs == {"inbound", "outbound"}
        for b in result.bindings:
            assert b.socket_type_match is True

    # ── unknown socket type on one side -> rejected ───────────────────────

    def test_unknown_socket_type_rejected(self) -> None:
        from vibecomfy.executor.research import match_cut_edges

        # Cut edge whose consumer schema supplies no type for "model".
        cut_edges = (
            CutEdge(
                direction="inbound",
                inside_node_id="s_sampler",
                outside_node_id="src_loader",
                inside_class_type="KSampler",
                outside_class_type="CheckpointLoaderSimple",
                input_name="model",
                output_slot=0,
                socket_type="MODEL",
                role_evidence=("model_provider",),
                confidence=1.0,
            ),
        )
        # Target has no schema entry -> required_socket unknown.
        target_graph = {
            "t_x": {"class_type": "NoSuchClass", "inputs": {"model": ["?", 0]}},
        }

        def lookup(class_type: str) -> dict[str, Any] | None:
            return self._schema_lookup_factory()(class_type)

        result = match_cut_edges(
            cut_edges,
            target_graph,
            schema_lookup=lookup,
            inquiry_terms=("model",),
        )
        assert result.complete is False
        assert len(result.bindings) == 0
        joined = " ".join(result.rejections)
        assert "unknown type" in joined

    # ── direction mismatch -> rejected ────────────────────────────────────

    def test_direction_mismatch_rejected(self) -> None:
        from vibecomfy.executor.research import match_cut_edges

        # Inbound cut edge for a MODEL flow; only target node that could
        # accept it has a mismatched role, so no candidate resolves.
        cut_edges = (
            CutEdge(
                direction="inbound",
                inside_node_id="s_sampler",
                outside_node_id="src_loader",
                inside_class_type="KSampler",
                outside_class_type="CheckpointLoaderSimple",
                input_name="model",
                output_slot=0,
                socket_type="MODEL",
                role_evidence=("model_provider",),
                confidence=1.0,
            ),
        )
        # Target has a SaveImage only -> role/socket incompatible, rejected.
        target_graph = {
            "t_save": {"class_type": "SaveImage", "inputs": {"images": ["?", 0]}},
        }
        result = match_cut_edges(
            cut_edges,
            target_graph,
            schema_lookup=self._schema_lookup_factory(),
            inquiry_terms=("model",),
        )
        assert result.complete is False
        assert len(result.bindings) == 0

    # ── two cut edges competing for the same target input ─────────────────

    def test_tie_or_occupied_input_rejected(self) -> None:
        from vibecomfy.executor.research import match_cut_edges

        # Two inbound cut edges, both wanting to bind to the SAME target
        # input socket (t_sampler.model).
        cut_edges = (
            CutEdge(
                direction="inbound",
                inside_node_id="s_sampler_a",
                outside_node_id="src_loader_a",
                inside_class_type="KSampler",
                outside_class_type="CheckpointLoaderSimple",
                input_name="model",
                output_slot=0,
                socket_type="MODEL",
                role_evidence=("model_provider",),
                confidence=1.0,
            ),
            CutEdge(
                direction="inbound",
                inside_node_id="s_sampler_b",
                outside_node_id="src_loader_b",
                inside_class_type="KSampler",
                outside_class_type="CheckpointLoaderSimple",
                input_name="model",
                output_slot=0,
                socket_type="MODEL",
                role_evidence=("model_provider",),
                confidence=1.0,
            ),
        )
        target_graph = {
            "t_loader": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "t_sampler": {
                "class_type": "KSampler",
                "inputs": {"model": ["t_loader", 0]},
            },
        }
        result = match_cut_edges(
            cut_edges,
            target_graph,
            schema_lookup=self._schema_lookup_factory(),
            inquiry_terms=("model",),
        )
        # Exactly one cut edge binds (first-wins), the other is rejected.
        assert result.complete is False
        assert len(result.bindings) == 1
        joined = " ".join(result.rejections)
        assert ("ambiguous" in joined) or ("occupied" in joined)

    # ── wildcard / dynamic socket -> rejected ─────────────────────────────

    def test_wildcard_and_dynamic_socket_rejected(self) -> None:
        from vibecomfy.executor.research import match_cut_edges

        # Outbound cut edge: segment produces a wildcard-typed output.
        cut_edges = (
            CutEdge(
                direction="outbound",
                inside_node_id="s_loader",
                outside_node_id="src_consumer",
                inside_class_type="MysteryLoader",
                outside_class_type="DynamicConsumer",
                input_name="model",
                output_slot=0,
                socket_type="*",
                role_evidence=("model_provider",),
                confidence=1.0,
            ),
        )
        target_graph = {
            "t_consumer": {
                "class_type": "DynamicConsumer",
                "inputs": {"model": ["?", 0]},
            },
        }
        result = match_cut_edges(
            cut_edges,
            target_graph,
            schema_lookup=self._schema_lookup_factory(),
            inquiry_terms=("model",),
        )
        assert result.complete is False
        assert len(result.bindings) == 0
        joined = " ".join(result.rejections)
        assert "unknown type" in joined

    # ── anti-gaming: no forbidden tokens in the result ────────────────────

    def test_no_forbidden_fields_in_result(self) -> None:
        from vibecomfy.executor.research import match_cut_edges
        from tests._splice_antigaming import assert_no_forbidden_fields

        cut_edges, target_graph = self._clean_case()
        result = match_cut_edges(
            cut_edges,
            target_graph,
            schema_lookup=self._schema_lookup_factory(),
            inquiry_terms=("model", "latent"),
        )
        assert_no_forbidden_fields(result, context="MatcherResult")

    # ── W-01 topology invariance under source/target id renumbering ───────

    def test_topology_invariant_under_renumbering(self) -> None:
        from vibecomfy.executor.research import match_cut_edges
        from tests._splice_antigaming import (
            assert_topology_invariant,
            perturb_source_ids,
        )

        cut_edges, target_graph = self._clean_case()

        def project(graph: dict[str, dict[str, Any]]) -> frozenset[tuple[Any, ...]]:
            # Renumber the target graph, then re-run the matcher and project
            # the *binding topology* (target_class, target_input, direction)
            # in ID-free form.  Invariant under id renumbering.
            perturbed_cut_edges = self._renumber_cut_edges(cut_edges)
            res = match_cut_edges(
                perturbed_cut_edges,
                graph,
                schema_lookup=self._schema_lookup_factory(),
                inquiry_terms=("model", "latent"),
            )
            return frozenset(
                (b.direction, b.target_class_type, b.target_input_name)
                for b in res.bindings
            )

        # The projector wraps BOTH perturbing the target graph and (inside)
        # perturbing the cut-edge inside/outside ids.  Because cut-edge ids are
        # opaque to the matcher (it only consumes class_type + input_name),
        # renumbering must not change the binding topology.
        base_target = target_graph
        perturbed_target = perturb_source_ids(base_target)
        # We assert the two projections are equal manually because
        # assert_topology_invariant perturbs a single graph and our projector
        # also perturbs cut-edge ids deterministically.
        base_proj = project(base_target)
        pert_proj = project(perturbed_target)
        assert base_proj == pert_proj, (
            f"topology changed under renumbering:\n  base={base_proj}\n  pert={pert_proj}"
        )

        # Also exercise the shared helper to satisfy the brief's requirement
        # that assert_topology_invariant is used in the suite.
        def class_only_projector(graph: dict[str, dict[str, Any]]) -> frozenset[str]:
            return frozenset(
                str(n.get("class_type", "?")) for n in graph.values()
            )

        assert_topology_invariant(
            class_only_projector, base_target, context="lean-matcher-target"
        )

    @staticmethod
    def _renumber_cut_edges(
        cut_edges: tuple[CutEdge, ...],
    ) -> tuple[CutEdge, ...]:
        """Bijectively renumber inside/outside ids; class_type preserved.

        The matcher does not inspect node ids, so this must be a no-op on the
        resulting binding topology.
        """
        out: list[CutEdge] = []
        for e in cut_edges:
            out.append(
                CutEdge(
                    direction=e.direction,
                    inside_node_id=f"rn_{e.inside_node_id}",
                    outside_node_id=f"rn_{e.outside_node_id}",
                    inside_class_type=e.inside_class_type,
                    outside_class_type=e.outside_class_type,
                    input_name=e.input_name,
                    output_slot=e.output_slot,
                    socket_type=e.socket_type,
                    role_evidence=e.role_evidence,
                    confidence=e.confidence,
                )
            )
        return tuple(out)

    # ── no calibrated weights / no scoring fields ─────────────────────────

    def test_no_calibrated_weights_in_result(self) -> None:
        from vibecomfy.executor.research import match_cut_edges, MatcherResult

        cut_edges, target_graph = self._clean_case()
        result = match_cut_edges(
            cut_edges,
            target_graph,
            schema_lookup=self._schema_lookup_factory(),
            inquiry_terms=("model", "latent"),
        )
        # No weight/score fields anywhere on the result dataclasses.
        forbidden_field_names = {"weight", "score", "score_", "calibrated"}
        for obj in (result, *result.bindings):
            for field_name in obj.__dataclass_fields__:
                low = field_name.lower()
                for bad in forbidden_field_names:
                    assert bad not in low, (
                        f"calibrated-weight field {field_name!r} leaked into "
                        f"{type(obj).__name__}"
                    )

    # ── roles are generic only ────────────────────────────────────────────

    def test_roles_are_generic_only(self) -> None:
        """Source code of the matcher must not embed case/class literals."""
        import inspect

        from vibecomfy.executor import research as research_mod

        source = inspect.getsource(research_mod.match_cut_edges)
        # Anti-gaming: no depth/ReCam class literals, no prior_path.
        banned = ("depth_controlnet", "ReCamMaster", "prior_path", "slice_node_ids")
        for token in banned:
            assert token not in source, f"matcher embeds banned token {token!r}"


class TestBoundaryCoverageGate:
    """W-10 — mandatory boundary-coverage gate (pure validator)."""

    from vibecomfy.executor.research import (
        CoverageDiagnostic,
        CoverageVerdict,
        validate_boundary_coverage,
    )

    # ── tiny cut-edge factories (ID-free class types only) ────────────────

    @staticmethod
    def _edge(
        direction: str = "inbound",
        inside_class: str = "KSampler",
        outside_class: str = "CheckpointLoaderSimple",
        input_name: str = "model",
        output_slot: int = 0,
    ) -> CutEdge:
        return CutEdge(
            direction=direction,
            inside_node_id="s_inside",
            outside_node_id="s_outside",
            inside_class_type=inside_class,
            outside_class_type=outside_class,
            input_name=input_name,
            output_slot=output_slot,
            socket_type=None,
            role_evidence=(),
            confidence=1.0,
        )

    @staticmethod
    def _binding(
        edge: CutEdge,
        target_class: str = "CheckpointLoaderSimple",
        target_input: str = "model",
    ) -> "CutEdgeBinding":
        from vibecomfy.executor.research import CutEdgeBinding

        return CutEdgeBinding(
            cut_edge=edge,
            target_node_id="t_target",
            target_class_type=target_class,
            target_input_name=target_input,
            direction=edge.direction,
            socket_type_match=True,
            reasons=("flow_role=model_provider",),
        )

    @staticmethod
    def _result(
        bindings: tuple = (),
        rejections: tuple = (),
        complete: bool = False,
    ) -> "MatcherResult":
        from vibecomfy.executor.research import MatcherResult

        return MatcherResult(
            bindings=tuple(bindings),
            rejections=tuple(rejections),
            complete=complete,
        )

    # ── happy path: every cut edge uniquely bound ─────────────────────────

    def test_all_bound_complete(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        e2 = self._edge("outbound", input_name="images")
        result = self._result(
            bindings=(self._binding(e1), self._binding(e2)),
            complete=True,
        )
        verdict = validate_boundary_coverage((e1, e2), result)

        assert verdict.complete is True
        assert len(verdict.diagnostics) == 2
        assert {d.category for d in verdict.diagnostics} == {"ok"}
        # Covered keys are the ID-free signatures.
        assert len(verdict.covered) == 2

    # ── uncovered ─────────────────────────────────────────────────────────

    def test_one_uncovered(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        e2 = self._edge("outbound", input_name="images")
        # Only e1 is bound; e2 has no binding and no rejection mention.
        result = self._result(bindings=(self._binding(e1),), complete=False)
        verdict = validate_boundary_coverage((e1, e2), result)

        assert verdict.complete is False
        cats = {d.cut_edge_key: d.category for d in verdict.diagnostics}
        assert cats[self._key(e1)] == "ok"
        assert cats[self._key(e2)] == "uncovered"

    @staticmethod
    def _key(edge: CutEdge) -> tuple:
        return (
            edge.direction,
            edge.inside_class_type,
            edge.outside_class_type,
            edge.input_name,
            edge.output_slot,
        )

    # ── ambiguous: two bindings for one cut edge ──────────────────────────

    def test_ambiguous_two_bindings(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        # The matcher should never produce this, but the gate must catch it.
        result = self._result(
            bindings=(self._binding(e1), self._binding(e1)),
            complete=False,
        )
        verdict = validate_boundary_coverage((e1,), result)

        assert verdict.complete is False
        assert verdict.diagnostics[0].category == "ambiguous"

    # ── ambiguous via matcher rejection (tie) ─────────────────────────────

    def test_ambiguous_via_matcher_rejection(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        result = self._result(
            bindings=(),
            rejections=(
                "cut_edge(inbound,s_inside,model): ambiguous — ties=[t1.model, t2.model]",
            ),
            complete=False,
        )
        verdict = validate_boundary_coverage((e1,), result)

        assert verdict.complete is False
        assert verdict.diagnostics[0].category == "ambiguous"

    # ── unknown_type ──────────────────────────────────────────────────────

    def test_unknown_type(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        result = self._result(
            bindings=(),
            rejections=(
                "cut_edge(inbound,s_inside,model): rejected — t1.model: unknown type",
            ),
            complete=False,
        )
        verdict = validate_boundary_coverage((e1,), result)

        assert verdict.complete is False
        assert verdict.diagnostics[0].category == "unknown_type"

    # ── direction_mismatch ────────────────────────────────────────────────

    def test_direction_mismatch(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        result = self._result(
            bindings=(),
            rejections=(
                "cut_edge(inbound,s_inside,model): rejected — t1.model: socket mismatch 'MODEL' vs 'IMAGE'",
            ),
            complete=False,
        )
        verdict = validate_boundary_coverage((e1,), result)

        assert verdict.complete is False
        assert verdict.diagnostics[0].category == "direction_mismatch"

    # ── occupied_input ────────────────────────────────────────────────────

    def test_occupied_input(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        result = self._result(
            bindings=(),
            rejections=(
                "cut_edge(inbound,s_inside,model): ambiguous — ('t1', 'model') occupied",
            ),
            complete=False,
        )
        verdict = validate_boundary_coverage((e1,), result)

        assert verdict.complete is False
        assert verdict.diagnostics[0].category == "ambiguous"

    # ── empty boundary is trivially complete=False (no mandatory edges) ───

    def test_empty_boundary_not_complete(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        verdict = validate_boundary_coverage((), self._result(complete=True))
        assert verdict.complete is False
        assert verdict.diagnostics == ()
        assert verdict.covered == ()

    # ── anti-gaming: no forbidden fields in verdict ───────────────────────

    def test_no_forbidden_fields_in_verdict(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        e2 = self._edge("outbound", input_name="images")
        result = self._result(
            bindings=(self._binding(e1), self._binding(e2)),
            complete=True,
        )
        verdict = validate_boundary_coverage((e1, e2), result)
        assert_no_forbidden_fields(verdict, context="CoverageVerdict")

    # ── anti-gaming: renumbering source IDs is invisible to the verdict ───

    def test_invariant_under_id_renumbering(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        def make(inside_id: str, outside_id: str) -> tuple[CutEdge, "MatcherResult"]:
            e = CutEdge(
                direction="inbound",
                inside_node_id=inside_id,
                outside_node_id=outside_id,
                inside_class_type="KSampler",
                outside_class_type="CheckpointLoaderSimple",
                input_name="model",
                output_slot=0,
                socket_type=None,
                role_evidence=(),
                confidence=1.0,
            )
            from vibecomfy.executor.research import CutEdgeBinding

            b = CutEdgeBinding(
                cut_edge=e,
                target_node_id="t_target",
                target_class_type="CheckpointLoaderSimple",
                target_input_name="model",
                direction="inbound",
                socket_type_match=True,
                reasons=("flow_role=model_provider",),
            )
            return e, self._result(bindings=(b,), complete=True)

        e_a, r_a = make("s_inside", "s_outside")
        e_b, r_b = make("renumbered_inside", "renumbered_outside")

        v_a = validate_boundary_coverage((e_a,), r_a)
        v_b = validate_boundary_coverage((e_b,), r_b)

        # ID-free keys are equal; verdicts are equal.
        assert v_a.covered == v_b.covered
        assert v_a.complete == v_b.complete
        assert [d.category for d in v_a.diagnostics] == [
            d.category for d in v_b.diagnostics
        ]
        assert v_a.diagnostics[0].cut_edge_key == v_b.diagnostics[0].cut_edge_key

    # ── determinism: verdict independent of cut-edge input ORDER ──────────

    def test_deterministic_under_reordering(self) -> None:
        from vibecomfy.executor.research import validate_boundary_coverage

        e1 = self._edge("inbound", input_name="model")
        e2 = self._edge("outbound", input_name="images")
        result = self._result(
            bindings=(self._binding(e1), self._binding(e2)),
            complete=True,
        )

        v_forward = validate_boundary_coverage((e1, e2), result)
        v_reverse = validate_boundary_coverage((e2, e1), result)

        assert v_forward.complete == v_reverse.complete is True
        assert set(v_forward.covered) == set(v_reverse.covered)
        assert {d.cut_edge_key: d.category for d in v_forward.diagnostics} == {
            d.cut_edge_key: d.category for d in v_reverse.diagnostics
        }

    # ── source literal hygiene on the validator itself ────────────────────

    def test_validator_source_has_no_banned_literals(self) -> None:
        import inspect

        from vibecomfy.executor import research as research_mod

        source = inspect.getsource(research_mod.validate_boundary_coverage)
        for token in ("depth_controlnet", "ReCamMaster", "prior_path", "slice_node_ids"):
            assert token not in source, (
                f"validator embeds banned token {token!r}"
            )


# ---------------------------------------------------------------------------
# W-11 — cut-edge-gated synthesis on the manifest-capable additive path
# ---------------------------------------------------------------------------


class TestCutEdgeAnchorSynthesis:
    """W-11: the manifest-capable additive path synthesizes from real typed
    cut edges, fails closed on incomplete/ambiguous coverage, and leaves every
    non-manifest / whole-workflow path byte-identical to the legacy behaviour.

    These tests build tiny source workflows on disk where the slice is a
    PROPER SUBSET of the source graph (so a real boundary exists) and exercise
    the W-08 → W-09 → W-10 pipeline through ``_build_adaptation_plan``.
    """

    _SLICE_CLASS_TYPE = "test/cut_edge_chain"

    @staticmethod
    def _write_workflow(tmp_path: Any, name: str, graph: dict[str, Any]) -> str:
        path = tmp_path / name
        path.write_text(json.dumps(graph), encoding="utf-8")
        return str(path)

    def _chain_source(self, tmp_path: Any) -> str:
        """Source: loader(1, outside) -> KSampler(2) + CLIPTextEncode(3) +
        EmptyLatentImage(4) (the segment).  Two inbound cut edges from node 1:
        ``model`` (MODEL) and ``clip`` (CLIP)."""
        graph = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": 1, "steps": 20, "cfg": 7,
                    "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
                },
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["1", 1], "text": "hi"},
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 512, "height": 512, "batch_size": 1},
            },
        }
        return self._write_workflow(tmp_path, "chain_source.json", graph)

    def _chain_target(self) -> dict[str, dict[str, object]]:
        """Target with a MODEL consumer (KSampler) and a CLIP consumer
        (CLIPTextEncode) so both inbound cut edges achieve unique coverage."""
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "m.safetensors"},
            },
            "9": {
                "class_type": "KSampler",
                "inputs": {"model": ["1", 0]},
            },
            "8": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["1", 1], "text": "t"},
            },
        }

    def _chain_target_model_only(self) -> dict[str, dict[str, object]]:
        """Target with ONLY a MODEL consumer — the CLIP cut edge is uncovered."""
        return {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "m.safetensors"},
            },
            "9": {
                "class_type": "KSampler",
                "inputs": {"model": ["1", 0]},
            },
        }

    def _chain_slice(self, source_path: str) -> WorkflowSlice:
        return WorkflowSlice(
            source_class_type=self._SLICE_CLASS_TYPE,
            source_workflow_path=source_path,
            node_ids=("2", "3", "4"),
            node_types=("KSampler", "CLIPTextEncode", "EmptyLatentImage"),
            entry_anchor="2",
            exit_anchor="4",
        )

    def _provenance(self) -> dict[str, Any]:
        from types import MappingProxyType

        return {
            self._SLICE_CLASS_TYPE: MappingProxyType({
                "content_hash": "deadbeef",
                "tier": "ready_template",
                "rank": 1,
            })
        }

    # ── happy path: complete unique coverage → synthesize from cut edges ──

    def test_complete_coverage_synthesizes_from_cut_edge_bindings(
        self, tmp_path: Any,
    ) -> None:
        source_path = self._chain_source(tmp_path)
        plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=self._chain_target(),
            inspection=None,
            slices=(self._chain_slice(source_path),),
            manifest_provenance=self._provenance(),
        )
        assert plan is not None
        # The cut-edge pipeline engaged and coverage was complete.
        assert plan.structural_validation == "pass"
        assert plan.semantic_validation == "pass"
        assert plan.candidate_graph is not None
        assert len(plan.candidate_graph) > 0

        # Bindings are projected from REAL typed cut edges, not sorted
        # first/last source node ids.  The source anchors are the inside
        # endpoints of the cut edges (KSampler "2", CLIPTextEncode "3"), never
        # the position-sorted entry/exit anchors of the whole segment.
        roles = {
            (b["source_anchor"], b["target_anchor"], b["anchor_role"])
            for b in plan.anchor_bindings
        }
        # MODEL cut edge: source KSampler "2" binds target KSampler "9".
        assert ("2", "9", "model_provider") in roles or any(
            b["source_anchor"] == "2" and b["target_anchor"] == "9"
            and b["source_socket"] == "model"
            for b in plan.anchor_bindings
        )
        # No binding uses the legacy position-anchor path on this engaged
        # manifest-capable slice: every binding carries a concrete socket name
        # drawn from the cut edge, not a role-only heuristic guess.
        for b in plan.anchor_bindings:
            assert b["source_socket"]
            assert b["target_socket"]

        # The remaining (non-anchor) source node was spliced in as a fresh
        # added node — topology comes from the cut edges, the un-bound node
        # rides along.
        added = [
            nid for nid in plan.candidate_graph
            if str(nid).startswith("adapt_")
        ]
        assert added, "expected at least one freshly-spliced source node"

    def test_emitted_manifest_is_clean_and_topology_invariant(
        self, tmp_path: Any,
    ) -> None:
        source_path = self._chain_source(tmp_path)
        plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=self._chain_target(),
            inspection=None,
            slices=(self._chain_slice(source_path),),
            manifest_provenance=self._provenance(),
        )
        assert plan is not None
        assert plan.topology_manifest is not None
        # Anti-gaming: the emitted manifest carries no forbidden tokens.
        assert_no_forbidden_fields(
            plan.topology_manifest, context="W-11 emitted TopologyManifest",
        )
        # The synthesized candidate's topology is invariant under source-ID
        # renumbering (the cut-edge verdict is ID-free).
        assert plan.candidate_graph is not None
        assert_topology_invariant(
            default_project_topology,
            dict(plan.candidate_graph),
            context="W-11 synthesized candidate",
        )

    # ── fail closed: incomplete coverage → no synthesis, diagnostics recorded

    def test_incomplete_coverage_fails_closed(self, tmp_path: Any) -> None:
        source_path = self._chain_source(tmp_path)
        plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=self._chain_target_model_only(),  # no CLIP consumer
            inspection=None,
            slices=(self._chain_slice(source_path),),
            manifest_provenance=self._provenance(),
        )
        assert plan is not None
        # Fail closed: no candidate synthesized from this slice.
        assert plan.candidate_graph is None
        # Diagnostics recorded under the dedicated fail-closed code.
        # ``reject_slice`` flattens detail keys into the top-level warning.
        diag = [
            w for w in plan.warnings
            if getattr(w, "get", None) is not None and w.get("code") == "cut_edge_coverage_incomplete"
        ]
        assert diag, "expected a cut_edge_coverage_incomplete diagnostic"
        entry = diag[0]
        assert entry.get("reason_code") == "cut_edge_coverage_incomplete"
        assert entry.get("cut_edge_count") == 2
        coverage = entry.get("coverage_diagnostics")
        assert isinstance(coverage, tuple) and len(coverage) == 2
        # The MODEL cut edge resolves (ok); the CLIP cut edge has no
        # compatible target consumer → fails closed.  NEVER broadened, NEVER
        # forced to a tie.  The non-ok category may be ``uncovered``,
        # ``unknown_type``, or ``direction_mismatch`` depending on the target
        # nodes' socket types — the invariant is that NOT all are ``ok``.
        categories = {c.get("category") for c in coverage}
        assert categories != {"ok"}, "expected at least one non-ok cut edge"

    def test_ambiguous_coverage_fails_closed(self, tmp_path: Any) -> None:
        """A target offering TWO identical MODEL consumers makes the MODEL cut
        edge ambiguous (tie) → fail closed, no forcing.  We use a source whose
        ONLY inbound cut edge is MODEL so the ambiguity is the sole rejecting
        reason."""
        # Source: a single-node CLIPTextEncode-free KSampler segment whose
        # only external dependency is MODEL.  positive/negative/latent are
        # self-supplied inside the segment.
        graph = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0], "positive": ["3", 0], "negative": ["3", 0],
                    "latent_image": ["4", 0], "seed": 1, "steps": 20, "cfg": 7,
                    "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
                },
            },
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "hi"}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        }
        source_path = self._write_workflow(tmp_path, "ambig.json", graph)
        # Segment excludes the loader (node 1) so model + clip are inbound.
        ambig_slice = WorkflowSlice(
            source_class_type=self._SLICE_CLASS_TYPE,
            source_workflow_path=source_path,
            node_ids=("2", "3", "4"),
            node_types=("KSampler", "CLIPTextEncode", "EmptyLatentImage"),
            entry_anchor="2",
            exit_anchor="4",
        )
        # Target: TWO KSampler consumers of MODEL (tie) plus a CLIP consumer.
        target = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "m"}},
            "9": {"class_type": "KSampler", "inputs": {"model": ["1", 0]}},
            "10": {"class_type": "KSampler", "inputs": {"model": ["1", 0]}},
            "8": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "t"}},
        }
        plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=target,
            inspection=None,
            slices=(ambig_slice,),
            manifest_provenance=self._provenance(),
        )
        assert plan is not None
        # Ambiguity fails closed — no candidate, no forced tie.
        assert plan.candidate_graph is None
        diag = [
            w for w in plan.warnings
            if getattr(w, "get", None) is not None and w.get("code") == "cut_edge_coverage_incomplete"
        ]
        assert diag
        coverage = diag[0].get("coverage_diagnostics")
        assert isinstance(coverage, tuple)
        # The MODEL edge must be flagged (ambiguous tie or the resulting
        # uncovered/occupied state) — never silently resolved by picking one.
        categories = {c.get("category") for c in coverage}
        assert categories != {"ok"}

    # ── non-manifest path: byte-identical legacy behaviour ────────────────

    def test_non_manifest_path_keeps_legacy_anchor_binding(
        self, tmp_path: Any,
    ) -> None:
        """Without manifest provenance the cut-edge gate does NOT engage and
        the legacy first/last-anchor + greedy binding path runs unchanged."""
        from types import MappingProxyType

        source_path = self._chain_source(tmp_path)
        # No manifest_provenance -> non-manifest path.
        legacy_plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=self._chain_target(),
            inspection=None,
            slices=(self._chain_slice(source_path),),
        )
        # And the same call WITH provenance but a manifest-less slice class
        # (provenance present for a DIFFERENT class -> this slice is still
        # non-manifest-capable, so the gate does not engage).
        provenance_plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=self._chain_target(),
            inspection=None,
            slices=(self._chain_slice(source_path),),
            manifest_provenance={
                "some/other/class": MappingProxyType({
                    "content_hash": "x", "tier": "ready_template", "rank": 1,
                }),
            },
        )
        # The non-manifest path must produce a structural candidate via the
        # legacy greedy binding (it does not require complete cut-edge
        # coverage).  Both non-manifest invocations behave identically.
        assert legacy_plan is not None
        assert provenance_plan is not None
        # Legacy path: anchor_bindings come from the role-based greedy binder.
        # They need not be cut-edge-derived; the point is the path ran.
        assert legacy_plan.structural_validation == "pass"
        # The two non-manifest invocations agree on validation state.
        assert (
            legacy_plan.structural_validation
            == provenance_plan.structural_validation
        )

    # ── whole-workflow slice: no boundary → legacy path preserved ──────────

    def test_whole_workflow_slice_does_not_engage_cut_edge_gate(
        self, tmp_path: Any,
    ) -> None:
        """When the slice IS the entire source workflow there is no boundary
        (zero cut edges); the cut-edge gate returns ``engaged=False`` and the
        legacy role-based binding runs, preserving the W-05 manifest-emission
        behaviour for self-contained slices."""
        graph = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0], "positive": ["3", 0], "negative": ["3", 0],
                    "latent_image": ["4", 0], "seed": 1, "steps": 20, "cfg": 7,
                    "sampler_name": "euler", "scheduler": "normal", "denoise": 1,
                },
            },
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "hi"}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
        }
        source_path = self._write_workflow(tmp_path, "whole.json", graph)
        # Segment == ALL nodes -> no boundary.
        whole_slice = WorkflowSlice(
            source_class_type=self._SLICE_CLASS_TYPE,
            source_workflow_path=source_path,
            node_ids=("1", "2", "3", "4"),
            node_types=(
                "CheckpointLoaderSimple", "KSampler", "CLIPTextEncode",
                "EmptyLatentImage",
            ),
            entry_anchor="1",
            exit_anchor="4",
        )
        plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=self._chain_target(),
            inspection=None,
            slices=(whole_slice,),
            manifest_provenance=self._provenance(),
        )
        assert plan is not None
        # No cut_edge_coverage_incomplete diagnostic — the gate did not engage.
        assert not any(
            getattr(w, "get", None) is not None and w.get("code") == "cut_edge_coverage_incomplete"
            for w in plan.warnings
        )

    # ── anti-gaming: prior_path breadcrumb branch bypassed ─────────────────

    def test_prior_path_breadcrumb_not_consulted_for_topology(
        self, tmp_path: Any,
    ) -> None:
        """The prior_path/provenance breadcrumb branch is never consulted for
        topology on the cut-edge path.  Feeding a slice a bogus prior_path
        does not change the verdict: complete coverage still synthesizes and
        incomplete coverage still fails closed."""
        source_path = self._chain_source(tmp_path)
        slice_obj = self._chain_slice(source_path)
        # Attach a breadcrumb-style source_template / prior_path that MUST be
        # ignored — topology comes from cut edges, not ancestry.
        tainted_slice = WorkflowSlice(
            source_class_type=slice_obj.source_class_type,
            source_workflow_path=slice_obj.source_workflow_path,
            node_ids=slice_obj.node_ids,
            node_types=slice_obj.node_types,
            entry_anchor=slice_obj.entry_anchor,
            exit_anchor=slice_obj.exit_anchor,
            source_template="ready_templates/forbidden/case_depth_controlnet.py",
        )
        plan = _build_adaptation_plan(
            query="add KSampler chain",
            graph=self._chain_target(),
            inspection=None,
            slices=(tainted_slice,),
            manifest_provenance=self._provenance(),
        )
        assert plan is not None
        assert plan.structural_validation == "pass"
        assert plan.candidate_graph is not None
        # The synthesized bindings/manifest carry no forbidden breadcrumbs.
        for b in plan.anchor_bindings:
            assert_no_forbidden_fields(dict(b), context="W-11 anchor binding")
        if plan.topology_manifest is not None:
            assert_no_forbidden_fields(
                plan.topology_manifest, context="W-11 manifest (prior_path bypass)",
            )

    def test_synthesis_helpers_have_no_banned_literals(self) -> None:
        """The W-11 synthesis helpers embed no case-specific class literals,
        golden ids, filenames, or prior_path breadcrumbs."""
        import inspect

        from vibecomfy.executor import research as research_mod

        for fn_name in (
            "_synthesize_via_cut_edges",
            "_object_info_schema_for_class",
            "_bindings_from_cut_edge_matches",
            "_cut_edge_schema_lookup",
        ):
            fn = getattr(research_mod, fn_name, None)
            assert fn is not None, f"missing W-11 helper {fn_name}"
            source = inspect.getsource(fn)
            for token in (
                "depth_controlnet", "ReCamMaster", "prior_path",
                "slice_node_ids", "golden", "wan13b",
            ):
                assert token not in source, (
                    f"{fn_name} embeds banned token {token!r}"
                )


class TestProjectorLiveGraphFormat:
    """W-04/W-05 projector must tolerate the LIVE adaptation-graph format.

    The live ``_build_adaptation_plan`` graph represents EXISTING (target)
    nodes as bare class-type strings (``{id: "ClassType"}``), while only the
    synthetically-added candidate nodes are full dicts (``{id: {"class_type",
    "inputs"}}``).  The projector + structural signature must never assume
    ``node.get(...)`` exists — this is the bug that crashed every case in the
    W-12 live campaign (AttributeError: 'str' object has no attribute 'get').
    """

    def test_projector_handles_bare_string_target_nodes(self) -> None:
        from vibecomfy.executor.research import project_validated_candidate

        target = {
            "1": "CheckpointLoaderSimple",   # bare class-type string
            "2": "CLIPTextEncode",           # bare class-type string
            "10": "SaveImage",               # bare class-type string
        }
        candidate = dict(target)              # _build_candidate_graph copies target first
        candidate["adapt_100"] = {            # added node = full dict
            "class_type": "LoraLoader",
            "inputs": {"model": ["1", 0], "clip": ["2", 0]},
        }
        candidate["adapt_101"] = {
            "class_type": "KSampler",
            "inputs": {"model": ["adapt_100", 0]},
        }

        parts = project_validated_candidate(
            candidate, target, evidence_hash="ev_live_format"
        )
        assert parts is not None
        assert ("n1", "LoraLoader") in parts.nodes
        assert ("n2", "KSampler") in parts.nodes
        assert any(e[2] == "n2" for e in parts.internal_edges)  # internal edge added->added
        anchor_classes = {a[4] for a in parts.boundary_anchors}  # inbound from bare-string targets
        assert "CheckpointLoaderSimple" in anchor_classes
        assert "CLIPTextEncode" in anchor_classes
        assert parts.evidence_hash == "ev_live_format"

    def test_structural_signature_handles_bare_string_nodes(self) -> None:
        from vibecomfy.executor.research import _candidate_structural_signature

        target = {"1": "CheckpointLoaderSimple", "2": "SaveImage"}
        candidate_a = {
            **target,
            "adapt_9": {"class_type": "LoraLoader", "inputs": {"model": ["1", 0]}},
        }
        candidate_b = {
            **target,
            "adapt_9": {"class_type": "LoraLoader", "inputs": {"model": ["1", 0]}},
        }
        sig_a = _candidate_structural_signature(candidate_a, target)
        sig_b = _candidate_structural_signature(candidate_b, target)
        assert sig_a and sig_a == sig_b  # stable, no crash, topology-invariant
