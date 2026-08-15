"""Unit tests for the A01 Hivemind search/get tools.

Covers input validation, PostgREST query translation (scopes + filters),
stable resolvable evidence IDs, opaque cursor paging, deterministic sorts,
typed transport failures (429/Retry-After + R2-B2 cooldown circuit, timeout,
unavailable, invalid request), and the no-results path.  All transport is
mocked via ``urllib.request.urlopen`` — no live network.
"""

from __future__ import annotations

import io
import json
import urllib.error
import base64
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.parse import unquote_plus

import pytest

from vibecomfy.executor.hivemind_clients import (
    _evidence_id,
    _hivemind_scope_params,
    _parse_evidence_id,
    _query_model_family,
    _rank_hivemind_rows,
    _row_model_families,
)
from vibecomfy.executor.hivemind_tools import (
    HIVE_MIND_GET_TOOL,
    HIVE_MIND_SEARCH_TOOL,
    hivemind_get,
    hivemind_search,
)
from vibecomfy.executor.tool_contracts import ToolResult, ToolStatus

_HIVEMIND_ROOT = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1"


def _cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(
        json.dumps({"offset": offset}).encode("utf-8")
    ).decode("ascii")


# ── Helpers ──────────────────────────────────────────────────────────────────


class _MockResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        return self._payload

    def __enter__(self) -> "_MockResponse":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


def _json_response(payload: Any) -> _MockResponse:
    return _MockResponse(json.dumps(payload).encode("utf-8"))


def _capture_urlopen(seen: list[str], responder: Any) -> Any:
    """Return a urlopen side_effect that records decoded URLs and responds."""

    def _urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(unquote_plus(req.full_url))
        if callable(responder):
            return responder(req, unquote_plus(req.full_url))
        return responder

    return _urlopen


def _no_network(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError(f"no network expected, got urlopen({args!r}, {kwargs!r})")


def _workflow_row(
    row_id: str,
    title: str = "LTX workflow",
    created_at: str = "2026-08-01T00:00:00Z",
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": row_id,
        "kind": "workflow",
        "source": "vibecomfy",
        "external_id": f"vibecomfy:{row_id}",
        "title": title,
        "body": f"Body for {title}",
        "url": f"https://example.com/wf/{row_id}.json",
        "created_at": created_at,
    }
    row.update(extra)
    return row


def _message_row(
    item_id: int,
    title: str = "ltx discussion",
    created_at: str = "2026-08-02T00:00:00Z",
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "item_id": item_id,
        "kind": "message",
        "title": title,
        "body": "community chatter about ltx",
        "author": "alice",
        "channel": "ltx_chatter",
        "created_at": created_at,
        "url": "https://discord.com/channels/1/2/3",
    }
    row.update(extra)
    return row


def _distillation_row(
    item_id: int,
    title: str = "LTX roundup",
    created_at: str = "2026-08-03T00:00:00Z",
    status: str = "approved",
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "item_id": item_id,
        "kind": "distillation",
        "title": title,
        "body": "distilled ltx knowledge",
        "author": "banodoco",
        "created_at": created_at,
        "metadata": {"status": status, "confidence": 0.9},
    }
    row.update(extra)
    return row


# ── Validation: all failures are typed INVALID_REQUEST, no network ──────────


class TestSearchValidation:
    def test_empty_query_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search("   ", cache_root=tmp_path)
        assert result.status is ToolStatus.INVALID_REQUEST
        assert result.diagnostics[0].code == "query_required"

    def test_non_string_query_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search(42, cache_root=tmp_path)  # type: ignore[arg-type]
        assert result.status is ToolStatus.INVALID_REQUEST

    def test_unknown_filter_key_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search(
                "ltx", filters={"winner": "ltx"}, cache_root=tmp_path
            )
        assert result.status is ToolStatus.INVALID_REQUEST
        assert result.diagnostics[0].code == "unknown_filter"

    def test_filters_must_be_mapping(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search("ltx", filters=["ltx"], cache_root=tmp_path)
        assert result.status is ToolStatus.INVALID_REQUEST
        assert result.diagnostics[0].code == "filters_object"

    def test_bad_source_type_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search(
                "ltx", filters={"source_type": "chat"}, cache_root=tmp_path
            )
        assert result.status is ToolStatus.INVALID_REQUEST

    def test_bad_sort_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search(
                "ltx", filters={"sort": "best"}, cache_root=tmp_path
            )
        assert result.status is ToolStatus.INVALID_REQUEST

    def test_limit_bounds_rejected(self, tmp_path: Path) -> None:
        for bad in (0, 21, -1, "5", 2.5):
            with patch("urllib.request.urlopen", side_effect=_no_network):
                result = hivemind_search("ltx", limit=bad, cache_root=tmp_path)
            assert result.status is ToolStatus.INVALID_REQUEST, bad
            assert result.diagnostics[0].code == "limit_invalid"

    def test_bad_date_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search(
                "ltx", filters={"date_from": "not-a-date"}, cache_root=tmp_path
            )
        assert result.status is ToolStatus.INVALID_REQUEST
        assert result.diagnostics[0].code == "invalid_filter"

    def test_inverted_date_range_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search(
                "ltx",
                filters={"date_from": "2026-08-10", "date_to": "2026-08-01"},
                cache_root=tmp_path,
            )
        assert result.status is ToolStatus.INVALID_REQUEST
        assert result.diagnostics[0].code == "date_range_inverted"

    def test_bad_cursor_rejected(self, tmp_path: Path) -> None:
        for bad in ("garbage", "aGk=", "W10="):  # "[]" decodes but is not an offset
            with patch("urllib.request.urlopen", side_effect=_no_network):
                result = hivemind_search("ltx", cursor=bad, cache_root=tmp_path)
            assert result.status is ToolStatus.INVALID_REQUEST, bad
            assert result.diagnostics[0].code == "invalid_filter"

    def test_has_workflow_must_be_bool(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search(
                "ltx", filters={"has_workflow": "yes"}, cache_root=tmp_path
            )
        assert result.status is ToolStatus.INVALID_REQUEST

    def test_bad_timeout_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_search("ltx", timeout=0, cache_root=tmp_path)
        assert result.status is ToolStatus.INVALID_REQUEST


# ── Query translation: scopes and filters become PostgREST params ───────────


class TestSearchScopeTranslation:
    def test_source_type_workflow_queries_external_resources_only(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "workflow"}, limit=5
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 1
        url = seen[0]
        assert "/external_resources?" in url
        assert "kind=eq.workflow" in url
        assert "select=*" in url
        assert "limit=20" in url  # fixed candidate pool, not the page size
        assert "order=created_at.desc" in url

    def test_source_type_discord_queries_unified_feed_messages(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "discord"}, limit=5
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 1
        url = seen[0]
        assert "/unified_feed?" in url
        assert "kind=eq.message" in url

    def test_source_type_distillation_queries_unified_feed_distillations(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "distillation"}, limit=5
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 1
        assert "kind=eq.distillation" in seen[0]

    def test_no_source_type_queries_all_three_scopes(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search("ltx", limit=5)
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 3
        assert any("/external_resources?" in u for u in seen)
        assert any("kind=eq.message" in u for u in seen)
        assert any("kind=eq.distillation" in u for u in seen)

    def test_stopword_only_query_runs_only_external_scope(self) -> None:
        """external_resources falls back to raw tokens; unified_feed has no
        distinctive tokens and is skipped."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search("what is this", limit=5)
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 1
        assert "/external_resources?" in seen[0]

    def test_stopword_only_query_with_discord_source_type_skips_all(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search(
                "what is this", filters={"source_type": "discord"}, limit=5
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert seen == []

    def test_punctuation_only_query_skips_all_scopes(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search("???", limit=5)
        assert result.status is ToolStatus.NO_RESULTS
        assert seen == []

    def test_channel_filter_skips_workflow_scope(self) -> None:
        """external_resources has no channel column: the scope is skipped."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search(
                "ltx",
                filters={"source_type": "workflow", "channel": "wan_chatter"},
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert seen == []


class TestSearchFilterTranslation:
    def test_workflow_model_family_metadata_containment(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={"source_type": "workflow", "model_family": "ltx"},
            )
        url = seen[0]
        assert (
            'metadata=cs.{"workflow_semantics":{"model_families":["ltx"]}}' in url
        )

    def test_workflow_capability_and_node_class_and_has_workflow(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={
                    "source_type": "workflow",
                    "capability": "text_to_video",
                    "node_class": "LTXVLoader",
                    "has_workflow": True,
                },
            )
        url = seen[0]
        # One combined containment requires every translated predicate.
        assert (
            'metadata=cs.{"workflow_semantics":{"model_families":["ltx"]'
            not in url
        )
        assert 'cs.{"workflow_semantics":{"task_type":"text_to_video"' in url
        assert '"node_types":["LTXVLoader"]' in url
        assert '"has_workflow_json":true' in url

    def test_unified_feed_family_translates_to_ilike_or_groups(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={"source_type": "discord", "model_family": "ltx"},
            )
        url = seen[0]
        # text query AND family aliases -> nested or: groups inside and=
        assert "and=(or:(title.ilike.*ltx*,body.ilike.*ltx*)" in url
        assert "title.ilike.*ltxv*" in url
        assert "title.ilike.*lightricks*" in url

    def test_unified_feed_channel_author_dates(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={
                    "source_type": "discord",
                    "channel": "wan_chatter",
                    "author": "alice",
                    "date_from": "2026-08-01",
                    "date_to": "2026-08-10",
                },
            )
        url = seen[0]
        assert "channel=eq.wan_chatter" in url
        assert "author=eq.alice" in url
        assert (
            "and=(created_at.gte.2026-08-01,created_at.lte.2026-08-10)"
            in url
        )

    def test_date_pair_merges_into_existing_and_group(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={
                    "source_type": "discord",
                    "model_family": "ltx",
                    "date_from": "2026-08-01",
                    "date_to": "2026-08-10",
                },
            )
        url = seen[0]
        assert url.count("and=(") == 1
        assert "or:(title.ilike.*ltx*,body.ilike.*ltx*,title.ilike.*ltxv*" in url
        assert "created_at.gte.2026-08-01,created_at.lte.2026-08-10)" in url

    def test_scope_params_return_none_without_criteria(self) -> None:
        params = _hivemind_scope_params(
            table="unified_feed",
            kind="message",
            query="what is this",
            model_family=None,
            capability=None,
            node_class=None,
            channel=None,
            author=None,
            date_from=None,
            date_to=None,
            has_workflow=None,
            limit=20,
        )
        assert params is None


# ── Results: stable evidence IDs, hits, sorts, paging ───────────────────────


class TestSearchResults:
    def test_hits_have_stable_resolvable_evidence_ids(self) -> None:
        rows = [
            _workflow_row("wf-1", title="LTX 2.5 pipeline", created_at="2026-08-05T00:00:00Z"),
            _workflow_row("wf-2", title="LTX fast mode", created_at="2026-08-04T00:00:00Z"),
        ]
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "workflow", "sort": "recent"}
            )
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 2
        assert result.result["has_more"] is False
        hits = result.result["hits"]
        assert [h["evidence_id"] for h in hits] == [
            "hivemind:external_resources:wf-1",
            "hivemind:external_resources:wf-2",
        ]
        # The ToolResult's evidence_ids mirror the hits and are resolvable.
        assert result.evidence_ids == tuple(h["evidence_id"] for h in hits)
        for evidence_id in result.evidence_ids:
            table, row_id = _parse_evidence_id(evidence_id)
            assert (table, row_id) == ("external_resources", evidence_id.rsplit(":", 1)[-1])

    def test_relevance_sort_ranks_matching_first(self) -> None:
        rows = [
            _workflow_row("wf-a", title="LTX video pipeline", created_at="2026-08-05T00:00:00Z"),
            _workflow_row("wf-b", title="comfy sampler tweaks", created_at="2026-08-04T00:00:00Z"),
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "workflow", "sort": "relevance"}
            )
        assert result.status is ToolStatus.OK
        hits = result.result["hits"]
        assert [h["evidence_id"] for h in hits] == [
            "hivemind:external_resources:wf-a",
            "hivemind:external_resources:wf-b",
        ]
        # The ranker scores the matching row above the workflow-kind baseline.
        assert hits[0]["score"] > hits[1]["score"]

    def test_relevance_drops_non_matching_discord_rows(self) -> None:
        rows = [
            _message_row(1, title="ltx chatter", created_at="2026-08-05T00:00:00Z"),
            _message_row(
                2,
                title="unrelated photo",
                body="just a photo of a cat",
                created_at="2026-08-04T00:00:00Z",
            ),
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "discord", "sort": "relevance"}
            )
        assert result.status is ToolStatus.OK
        assert [h["evidence_id"] for h in result.result["hits"]] == [
            "hivemind:unified_feed:1"
        ]

    def test_validated_sort_prefers_approved_distillations(self) -> None:
        def _responder(req: Any, url: str) -> Any:
            if "/external_resources?" in url:
                return _json_response(
                    [
                        _workflow_row(
                            "wf-1",
                            title="LTX parseable workflow",
                            created_at="2026-08-01T00:00:00Z",
                            metadata={
                                "has_workflow_json": True,
                                "workflow_semantics": {
                                    "promotion_gates": {"parseable_workflow": True}
                                },
                            },
                        )
                    ]
                )
            if "kind=eq.message" in url:
                return _json_response(
                    [_message_row(1, created_at="2026-08-02T00:00:00Z")]
                )
            return _json_response(
                [_distillation_row(2, created_at="2026-08-03T00:00:00Z")]
            )

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _responder),
        ):
            result = hivemind_search(
                "ltx", filters={"sort": "validated"}, limit=10
            )
        assert result.status is ToolStatus.OK
        order = [h["source_type"] for h in result.result["hits"]]
        assert order == ["distillation", "workflow", "discord"]

    def test_dedupe_within_scope_by_evidence_id(self) -> None:
        rows = [
            _message_row(42, title="ltx chatter", created_at="2026-08-05T00:00:00Z"),
            _message_row(42, title="ltx chatter dup", created_at="2026-08-04T00:00:00Z"),
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "discord", "sort": "recent"}
            )
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 1
        assert result.result["hits"][0]["evidence_id"] == "hivemind:unified_feed:42"

    def test_opaque_cursor_pages_deterministically(self) -> None:
        rows = [
            _workflow_row(f"wf-{i}", title=f"LTX entry {i}", created_at=f"2026-08-{10 - i:02d}T00:00:00Z")
            for i in range(5)
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            page1 = hivemind_search(
                "ltx", filters={"source_type": "workflow", "sort": "recent"}, limit=2
            )
            assert page1.status is ToolStatus.OK
            assert page1.result["count"] == 2
            assert page1.result["has_more"] is True
            next_cursor = page1.result["next_cursor"]
            assert isinstance(next_cursor, str) and next_cursor

            page2 = hivemind_search(
                "ltx",
                filters={"source_type": "workflow", "sort": "recent"},
                cursor=next_cursor,
                limit=2,
            )
            assert page2.status is ToolStatus.OK
            assert page2.result["count"] == 2
            assert page2.result["has_more"] is True

            page3 = hivemind_search(
                "ltx",
                filters={"source_type": "workflow", "sort": "recent"},
                cursor=page2.result["next_cursor"],
                limit=2,
            )
            assert page3.status is ToolStatus.OK
            assert page3.result["count"] == 1
            assert page3.result["has_more"] is False
            assert page3.result["next_cursor"] is None

        ids = (
            [h["evidence_id"] for h in page1.result["hits"]]
            + [h["evidence_id"] for h in page2.result["hits"]]
            + [h["evidence_id"] for h in page3.result["hits"]]
        )
        assert ids == [f"hivemind:external_resources:wf-{i}" for i in range(5)]

    def test_cursor_beyond_end_returns_no_results(self) -> None:
        rows = [_workflow_row("wf-1", title="LTX entry", created_at="2026-08-05T00:00:00Z")]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx",
                filters={"source_type": "workflow", "sort": "recent"},
                cursor=_cursor(100),
            )
        assert result.status is ToolStatus.NO_RESULTS

    def test_no_results_on_empty_corpus(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([])),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "workflow"}
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert result.result is None
        assert result.evidence_ids == ()


class TestTransportOnlyGuarantee:
    def test_hit_shape_is_stable_and_free_of_judgment(self) -> None:
        rows = [
            _workflow_row(
                "wf-1",
                title="LTX pipeline",
                metadata={
                    "has_workflow_json": True,
                    "workflow_semantics": {"model_families": ["ltx"]},
                },
            )
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "workflow"}
            )
        hit = result.result["hits"][0]
        assert set(hit) == {
            "evidence_id",
            "source_type",
            "table",
            "title",
            "body",
            "url",
            "author",
            "channel",
            "created_at",
            "score",
            "status",
            "confidence",
            "semantics",
        }
        assert hit["evidence_id"] == "hivemind:external_resources:wf-1"
        assert hit["source_type"] == "workflow"
        # ToolResult freezes JSON: lists arrive as tuples.
        assert tuple(hit["semantics"]["model_families"]) == ("ltx",)
        assert hit["created_at"] == "2026-08-01T00:00:00Z"
        # No task classification / winner / enough-check / stop fields.
        for key in ("decision", "winner", "enough", "stop_reason", "classification"):
            assert key not in result.result

    def test_partial_scope_failure_degrades_with_diagnostics(self) -> None:
        def _responder(req: Any, url: str) -> Any:
            if "/external_resources?" in url:
                return _json_response(
                    [_workflow_row("wf-1", title="LTX workflow", created_at="2026-08-05T00:00:00Z")]
                )
            if "kind=eq.message" in url:
                raise urllib.error.HTTPError(
                    req.full_url, 500, "statement timeout", {}, io.BytesIO(b'{"code":"57014"}')
                )
            return _json_response([])

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _responder),
        ):
            result = hivemind_search("ltx", limit=10)
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 1
        codes = {d.code for d in result.diagnostics}
        assert codes == {"hivemind_scope_failed"}
        assert result.diagnostics[0].details["scope"] == "unified_feed:message"

    def test_all_scopes_failed_returns_typed_failure(self) -> None:
        def _responder(req: Any, url: str) -> Any:
            raise urllib.error.HTTPError(
                req.full_url, 500, "boom", {}, io.BytesIO(b"{}")
            )

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _responder),
        ):
            result = hivemind_search("ltx", limit=10)
        assert result.status is ToolStatus.UNAVAILABLE


# ── hivemind_get: evidence ID resolution ────────────────────────────────────


class TestGet:
    def test_resolves_external_resources_row(self) -> None:
        row = _workflow_row("wf-1", title="LTX pipeline")
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([row])),
        ):
            result = hivemind_get("hivemind:external_resources:wf-1")
        assert result.status is ToolStatus.OK
        assert result.evidence_ids == ("hivemind:external_resources:wf-1",)
        assert result.result["source_type"] == "workflow"
        assert result.result["table"] == "external_resources"
        assert result.result["row"] == row
        assert "id=eq.wf-1" in seen[0]

    def test_resolves_unified_feed_message_and_distillation(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([_message_row(42)])),
        ):
            result = hivemind_get("hivemind:unified_feed:42")
        assert result.status is ToolStatus.OK
        assert result.result["source_type"] == "discord"

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([_distillation_row(7)])),
        ):
            result = hivemind_get("hivemind:unified_feed:7")
        assert result.status is ToolStatus.OK
        assert result.result["source_type"] == "distillation"

    def test_missing_row_returns_no_results(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([])),
        ):
            result = hivemind_get("hivemind:external_resources:missing")
        assert result.status is ToolStatus.NO_RESULTS

    def test_malformed_evidence_ids_rejected(self, tmp_path: Path) -> None:
        for bad in ("nope", "hivemind:nope:x", "hivemind:external_resources:", "hivemind:unified_feed:a b"):
            with patch("urllib.request.urlopen", side_effect=_no_network):
                result = hivemind_get(bad, cache_root=tmp_path)
            assert result.status is ToolStatus.INVALID_REQUEST, bad
            assert result.diagnostics[0].code == "invalid_evidence_id"

    def test_empty_string_evidence_id_rejected(self, tmp_path: Path) -> None:
        with patch("urllib.request.urlopen", side_effect=_no_network):
            result = hivemind_get("   ", cache_root=tmp_path)
        assert result.status is ToolStatus.INVALID_REQUEST
        assert result.diagnostics[0].code == "evidence_id_required"


# ── Typed transport failures: 429/Retry-After + circuit, timeout, etc. ──────


class TestTypedFailures:
    def test_429_with_retry_after_returns_rate_limited(self, tmp_path: Path) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "10"},
                io.BytesIO(b"{}"),
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_search("ltx", cache_root=tmp_path)
        assert result.status is ToolStatus.RATE_LIMITED
        assert result.retry_after_seconds == 10.0
        assert result.diagnostics[0].code == "hivemind_rate_limited"

    def test_cooldown_circuit_short_circuits_next_call(self, tmp_path: Path) -> None:
        """After a 429 the R2-B2 circuit blocks further network calls."""
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "10"},
                io.BytesIO(b"{}"),
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            first = hivemind_search("ltx", cache_root=tmp_path)
        assert first.status is ToolStatus.RATE_LIMITED
        assert first.retry_after_seconds == 10.0

        # Second call: circuit active -> RATE_LIMITED without any network I/O.
        with patch("urllib.request.urlopen", side_effect=_no_network):
            second = hivemind_search("ltx", cache_root=tmp_path)
        assert second.status is ToolStatus.RATE_LIMITED
        assert second.retry_after_seconds is not None
        assert 0.0 < second.retry_after_seconds <= 10.0
        assert second.diagnostics[0].code == "hivemind_rate_limited"

    def test_429_without_retry_after_uses_default_cooldown(self, tmp_path: Path) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"{}")
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_search("ltx", cache_root=tmp_path)
        assert result.status is ToolStatus.RATE_LIMITED
        assert result.retry_after_seconds is None

        with patch("urllib.request.urlopen", side_effect=_no_network):
            second = hivemind_search("ltx", cache_root=tmp_path)
        assert second.status is ToolStatus.RATE_LIMITED

    def test_429_on_get_also_rate_limited_and_shares_circuit(self, tmp_path: Path) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "5"},
                io.BytesIO(b"{}"),
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_get("hivemind:external_resources:wf-1", cache_root=tmp_path)
        assert result.status is ToolStatus.RATE_LIMITED
        assert result.retry_after_seconds == 5.0

        with patch("urllib.request.urlopen", side_effect=_no_network):
            blocked = hivemind_get("hivemind:external_resources:wf-1", cache_root=tmp_path)
        assert blocked.status is ToolStatus.RATE_LIMITED

    def test_timeout_returns_typed_timeout(self) -> None:
        def _slow(*args: Any, **kwargs: Any) -> Any:
            raise TimeoutError("timed out")

        with patch("urllib.request.urlopen", side_effect=_slow):
            result = hivemind_search("ltx")
        assert result.status is ToolStatus.TIMEOUT
        assert result.diagnostics[0].code == "hivemind_timeout"

    def test_http_500_returns_unavailable(self) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url, 500, "boom", {}, io.BytesIO(b"{}")
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_search("ltx")
        assert result.status is ToolStatus.UNAVAILABLE
        assert result.diagnostics[0].code == "hivemind_unavailable"

    def test_http_400_returns_invalid_request(self) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url, 400, "bad query", {}, io.BytesIO(b"{}")
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_search("ltx")
        assert result.status is ToolStatus.INVALID_REQUEST
        assert result.diagnostics[0].code == "hivemind_bad_request"

    def test_http_404_returns_unavailable(self) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url, 404, "not found", {}, io.BytesIO(b"{}")
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_search("ltx")
        assert result.status is ToolStatus.UNAVAILABLE

    def test_urlerror_returns_unavailable(self) -> None:
        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise urllib.error.URLError("connection refused")

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_search("ltx")
        assert result.status is ToolStatus.UNAVAILABLE

    def test_invalid_json_returns_unavailable(self) -> None:
        with patch(
            "urllib.request.urlopen",
            return_value=_MockResponse(b"not json"),
        ):
            result = hivemind_search("ltx")
        assert result.status is ToolStatus.UNAVAILABLE


# ── F01 contract conformance ────────────────────────────────────────────────


class TestToolResultContract:
    def test_ok_result_round_trips_through_contract(self) -> None:
        rows = [_workflow_row("wf-1", title="LTX pipeline")]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "workflow"}
            )
        assert isinstance(result, ToolResult)
        assert result.tool_name == HIVE_MIND_SEARCH_TOOL
        assert result.status is ToolStatus.OK
        assert result.to_dict()["status"] == "ok"
        rebuilt = ToolResult.from_dict(result.to_dict())
        assert rebuilt == result

    def test_rate_limited_result_round_trips_through_contract(self, tmp_path: Path) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "7"},
                io.BytesIO(b"{}"),
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_get("hivemind:external_resources:wf-1", cache_root=tmp_path)
        assert result.tool_name == HIVE_MIND_GET_TOOL
        assert result.status is ToolStatus.RATE_LIMITED
        assert result.retry_after_seconds == 7.0
        rebuilt = ToolResult.from_dict(result.to_dict())
        assert rebuilt == result


# ── REC-A: statement-timeout (57014) retry-once + soft-miss typing ──────────


def _statement_timeout_error(req: Any, *args: Any, **kwargs: Any) -> Any:
    raise urllib.error.HTTPError(
        req.full_url,
        500,
        "statement timeout",
        {},
        io.BytesIO(b'{"code":"57014","message":"canceling statement due to statement timeout"}'),
    )


class TestStatementTimeoutRetry:
    def test_57014_retried_once_then_ok(self) -> None:
        calls = {"n": 0}

        def _flaky(req: Any, *args: Any, **kwargs: Any) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.HTTPError(
                    req.full_url,
                    500,
                    "statement timeout",
                    {},
                    io.BytesIO(b'{"code":"57014","message":"canceling statement due to statement timeout"}'),
                )
            return _json_response([_workflow_row("wf-1", title="LTX workflow")])

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ) as sleep, patch("urllib.request.urlopen", side_effect=_flaky):
            result = hivemind_search("ltx", filters={"source_type": "workflow"})
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 1
        assert calls["n"] == 2
        sleep.assert_called_once()

    def test_persistent_57014_is_soft_miss_not_hard_failure(self) -> None:
        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch("urllib.request.urlopen", side_effect=_statement_timeout_error):
            result = hivemind_search("ltx", filters={"source_type": "workflow"})
        assert result.status is ToolStatus.UNAVAILABLE
        assert result.diagnostics[0].code == "hivemind_statement_timeout"
        assert result.evidence_ids == ()
        assert result.result is None

    def test_57014_on_get_also_soft_miss(self) -> None:
        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch("urllib.request.urlopen", side_effect=_statement_timeout_error):
            result = hivemind_get("hivemind:external_resources:wf-1")
        assert result.status is ToolStatus.UNAVAILABLE
        assert result.diagnostics[0].code == "hivemind_statement_timeout"

    def test_generic_500_not_retried(self) -> None:
        calls = {"n": 0}

        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            calls["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, io.BytesIO(b"{}"))

        with patch("urllib.request.urlopen", side_effect=_boom):
            result = hivemind_search("ltx", filters={"source_type": "workflow"})
        assert result.status is ToolStatus.UNAVAILABLE
        assert result.diagnostics[0].code == "hivemind_unavailable"
        assert calls["n"] == 1  # no retry on a generic 500


# ── REC-A: model-family / capability relevance (off-family demotion) ────────


class TestFamilyRelevance:
    def test_query_family_detection(self) -> None:
        assert _query_model_family("LTXV blurry video upscaling") == "ltx"
        assert _query_model_family("SDXL refiner LoRA placement") == "sdxl"
        assert _query_model_family("want to build a workflow") is None
        assert _query_model_family("switch wan to ltx") is None  # two families -> neutral

    def test_row_family_prefers_title_over_mislabeled_metadata(self) -> None:
        # The corpus labels MiniMax H3 workflows with model_families ["ltx"];
        # the title is the authoritative signal.
        minimax = _workflow_row(
            "2823",
            title="MiniMax H3 Turbo Video Generation with Audio and Upscaling",
            metadata={
                "workflow_semantics": {
                    "model_families": ["ltx", "controlnet"],
                    "searchable_aliases": ["minimax-h3", "i2v"],
                }
            },
        )
        assert _row_model_families(minimax) == frozenset({"minimax"})

        ltx = _workflow_row(
            "2773",
            title="External workflow: 011326 LTX2 AudioSync i2v WIP.json",
            metadata={
                "workflow_semantics": {
                    "model_families": ["ltx", "controlnet"],
                    "searchable_aliases": ["ltx", "ltxv", "ltx-video"],
                }
            },
        )
        assert _row_model_families(ltx) == frozenset({"ltx"})

    def test_relevance_ranks_matching_family_first_demotes_wrong(self) -> None:
        rows = [
            _workflow_row("2823", title="MiniMax H3 Video Generation with Audio and Upscaling"),
            _workflow_row("2773", title="External workflow: 011326 LTX2 AudioSync i2v WIP.json"),
            _workflow_row("2771", title="External workflow: generic pipeline"),
        ]
        ranked = _rank_hivemind_rows(rows, "LTXV blurry video upscaling")
        order = [row["id"] for row in ranked]
        # Wrong-family (minimax) hit is demoted below the family match AND the
        # family-neutral row; the family match leads.
        assert order[0] == "2773"
        assert "2823" not in order[:2]
        assert ranked[0]["score"] > ranked[1]["score"]
        assert any("family" in r for r in ranked[0]["reasons"])

    def test_explicit_family_filter_still_translated(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={"source_type": "workflow", "model_family": "ltx"},
            )
        assert 'metadata=cs.{"workflow_semantics":{"model_families":["ltx"]}}' in seen[0]


# ── REC-A: evidence-ID resolvability (no fabricated fallback IDs) ───────────


class TestEvidenceIdResolvability:
    def test_evidence_id_requires_natural_id_column(self) -> None:
        row = _workflow_row("wf-1", title="LTX pipeline")
        assert _evidence_id("external_resources", row) == "hivemind:external_resources:wf-1"
        # A row missing its natural id must NOT fabricate an ID from
        # external_id/url/title — those parse but never resolve.
        broken = {
            "external_id": "vibecomfy:wf-1",
            "url": "https://example.com/wf-1.json",
            "title": "LTX pipeline",
        }
        assert _evidence_id("external_resources", broken) is None

    def test_search_drops_unresolvable_rows(self) -> None:
        rows = [
            _workflow_row("wf-1", title="LTX pipeline"),
            {
                "external_id": "vibecomfy:orphan",
                "url": "https://example.com/orphan.json",
                "title": "orphan workflow",
                "kind": "workflow",
                "created_at": "2026-08-06T00:00:00Z",
            },
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search("ltx", filters={"source_type": "workflow"})
        assert result.status is ToolStatus.OK
        assert [h["evidence_id"] for h in result.result["hits"]] == [
            "hivemind:external_resources:wf-1"
        ]
        assert result.evidence_ids == ("hivemind:external_resources:wf-1",)

    def test_returned_ids_all_resolve_through_get(self) -> None:
        rows = [
            _workflow_row("wf-1", title="LTX pipeline"),
            _workflow_row("wf-2", title="LTX fast mode"),
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            search = hivemind_search("ltx", filters={"source_type": "workflow"})
        assert search.status is ToolStatus.OK
        for evidence_id in search.evidence_ids:
            with patch(
                "urllib.request.urlopen",
                side_effect=_capture_urlopen(
                    [],
                    _json_response([_workflow_row(evidence_id.rsplit(":", 1)[-1])]),
                ),
            ):
                got = hivemind_get(evidence_id)
            assert got.status is ToolStatus.OK, evidence_id
            assert got.result["evidence_id"] == evidence_id
