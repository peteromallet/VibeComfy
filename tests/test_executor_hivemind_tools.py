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

from vibecomfy.executor.hivemind_clients import (
    _evidence_id,
    _hivemind_scope_params,
    _order_hivemind_rows,
    _parse_evidence_id,
    _query_model_family,
    _rank_hivemind_rows,
    _row_model_families,
    _validated_bucket,
)
from vibecomfy.executor.hivemind_tools import (
    HIVE_MIND_GET_TOOL,
    HIVE_MIND_SEARCH_TOOL,
    hivemind_get,
    hivemind_search,
    serve_hivemind_record,
)
from vibecomfy.executor.contracts import HivemindRecordView
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
    # REC-D: the discord scope reads the raw message_feed table, whose native
    # columns are message_id / content / channel_name / author_name (no
    # title/body/kind/item_id).  The hit projector maps content -> body and
    # channel_name -> channel.
    row: dict[str, Any] = {
        "message_id": item_id,
        "content": f"{title}: community chatter about ltx",
        "author_name": "alice",
        "channel_name": "ltx_chatter",
        "created_at": created_at,
        "permalink": "https://discord.com/channels/1/2/3",
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


def _ui_workflow_json() -> dict[str, Any]:
    """A small LiteGraph UI-shape workflow (LoadAudio -> ConditioningCombine)."""
    return {
        "last_node_id": 2,
        "nodes": [
            {
                "id": 1,
                "type": "LoadAudio",
                "pos": [0, 0],
                "size": [300, 100],
                "widgets_values": ["audio.mp3"],
                "outputs": [{"name": "AUDIO", "type": "AUDIO", "links": [2]}],
            },
            {
                "id": 2,
                "type": "ConditioningCombine",
                "pos": [400, 0],
                "size": [300, 100],
                "widgets_values": [],
                "inputs": [{"name": "conditioning_1", "type": "CONDITIONING", "link": 2}],
                "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": None}],
            },
        ],
        "links": [[2, 1, 0, 2, 0, "AUDIO"]],
        "groups": [],
    }


def _envelope_workflow_json() -> dict[str, Any]:
    """A versioned rich-envelope workflow serialized from the UI fixture."""
    from vibecomfy.ingest.normalize import from_ui

    return from_ui(_ui_workflow_json(), use_comfy_converter=False).to_envelope()


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
    """Directive §37: external_resources + message_feed are the text
    surfaces; unified_feed stays the non-text distillation tier."""

    def test_source_type_workflow_text_searches_both_surfaces(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "workflow"}, limit=5
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 2
        resource_url, message_url = seen
        # WHERE WORKFLOWS LIVE: title/body doubling on external_resources.
        assert "/external_resources?" in resource_url
        assert "/unified_feed" not in resource_url
        assert "or=(title.ilike.*ltx*,body.ilike.*ltx*)" in resource_url
        assert "select=*" in resource_url
        assert "limit=20" in resource_url  # bounded candidate pool, not page size
        assert "order=created_at.desc" in resource_url
        # Community guidance surface keeps content-only patterns.
        assert "/message_feed?" in message_url
        assert "/unified_feed" not in message_url
        assert "or=(content.ilike.*ltx*)" in message_url

    def test_source_type_discord_queries_raw_message_feed(self) -> None:
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
        assert "/message_feed?" in url
        assert "content.ilike.*ltx*" in url
        assert "order=created_at.desc" in url

    def test_source_type_distillation_free_text_makes_no_request(self) -> None:
        """Distillations are never text-searched (S2/S3): a free-text-only
        distillation request has no non-text criteria and is skipped."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _no_network),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "distillation"}, limit=5
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert seen == []

    def test_no_source_type_runs_both_text_scopes_skipping_unified(self) -> None:
        """The corpus-wide search issues exactly TWO requests — the lean
        external_resources title/body query and the message_feed content
        query; the unified_feed tier contributes no criteria for
        free-text-only searches and is skipped."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search("ltx", limit=5)
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 2
        assert "/external_resources?" in seen[0]
        assert "/message_feed?" in seen[1]
        assert all("/unified_feed" not in u for u in seen)

    def test_filler_only_query_skips_all_scopes(self) -> None:
        """A question-shaped query with no distinctive token narrows nothing:
        no request at all instead of an unbounded recent dump."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search("what do people think", limit=5)
        assert result.status is ToolStatus.NO_RESULTS
        assert seen == []

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

    def test_channel_filter_applies_only_to_message_scope_of_workflow_tier(self) -> None:
        """§37: source_type='workflow' rides BOTH surfaces; channel/author are
        message_feed columns, so they scope only that request — the
        external_resources request is untouched by them."""
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
        assert len(seen) == 2
        resource_url, message_url = seen
        assert "/external_resources?" in resource_url
        assert "channel_name" not in resource_url
        assert "/message_feed?" in message_url
        assert "channel_name=eq.wan_chatter" in message_url


class TestSearchFilterTranslation:
    def test_distillation_structured_filters_are_non_text(self) -> None:
        """S3: the unified_feed distillation tier is reachable through
        structured filters only — has_workflow narrows it, and NO text
        predicate (or/ilike) is ever built for it."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={"source_type": "distillation", "has_workflow": True},
            )
        assert len(seen) == 1
        url = seen[0]
        assert "/unified_feed?" in url
        assert "kind=eq.distillation" in url
        assert 'metadata=cs.{"has_workflow":true}' in url
        assert "ilike" not in url
        assert "or=(" not in url

    def test_distillation_tier_ignores_text_aliases(self) -> None:
        """Even with family/capability/node filters set, the distillation
        request carries structured criteria only — no title/body/content
        wildcard translation anywhere."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={
                    "source_type": "distillation",
                    "model_family": "ltx",
                    "capability": "text_to_video",
                    "node_class": "LTXVLoader",
                    "has_workflow": False,
                },
            )
        assert len(seen) == 1
        url = seen[0]
        assert "/unified_feed?" in url
        assert 'metadata=cs.{"has_workflow":false}' in url
        assert "ilike" not in url

    def test_message_feed_family_translates_to_content_or_groups(self) -> None:
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
        assert "and=(or:(content.ilike.*ltx*)" in url
        assert "content.ilike.*ltxv*" in url
        assert "content.ilike.*lightricks*" in url

    def test_message_feed_channel_author_dates(self) -> None:
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
        assert "channel_name=eq.wan_chatter" in url
        assert "author_name=eq.alice" in url
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
        # HIVEMIND-SCOPE-FIX-REV: the family alias `ltx` deduplicates against
        # the query token instead of emitting a second identical pattern.
        assert (
            "or:(content.ilike.*ltx*),"
            "or:(content.ilike.*ltxv*,content.ilike.*lightricks*)" in url
        )
        assert "content.ilike.*ltxv*" in url
        assert "created_at.gte.2026-08-01,created_at.lte.2026-08-10)" in url

    def test_scope_params_return_none_without_criteria(self) -> None:
        params = _hivemind_scope_params(
            table="message_feed",
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
            _message_row(1, title="LTX 2.5 pipeline", created_at="2026-08-05T00:00:00Z"),
            _message_row(2, title="LTX fast mode", created_at="2026-08-04T00:00:00Z"),
        ]
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "discord", "sort": "recent"}
            )
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 2
        assert result.result["has_more"] is False
        hits = result.result["hits"]
        assert [h["evidence_id"] for h in hits] == [
            "hivemind:message_feed:1",
            "hivemind:message_feed:2",
        ]
        # The ToolResult's evidence_ids mirror the hits and are resolvable.
        assert result.evidence_ids == tuple(h["evidence_id"] for h in hits)
        for evidence_id in result.evidence_ids:
            table, row_id = _parse_evidence_id(evidence_id)
            assert (table, row_id) == ("message_feed", evidence_id.rsplit(":", 1)[-1])

    def test_relevance_sort_ranks_matching_first(self) -> None:
        rows = [
            _message_row(
                1,
                content="ltx vace workflow tips",
                created_at="2026-08-04T00:00:00Z",
            ),
            _message_row(
                2,
                content="someone asked about ltx once",
                created_at="2026-08-05T00:00:00Z",
            ),
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx vace", filters={"source_type": "discord", "sort": "relevance"}
            )
        assert result.status is ToolStatus.OK
        hits = result.result["hits"]
        assert [h["evidence_id"] for h in hits] == [
            "hivemind:message_feed:1",
            "hivemind:message_feed:2",
        ]
        # The title-matching row outranks the newer body-only mention.
        assert hits[0]["score"] > hits[1]["score"]

    def test_relevance_drops_non_matching_discord_rows(self) -> None:
        rows = [
            _message_row(1, title="ltx chatter", created_at="2026-08-05T00:00:00Z"),
            _message_row(
                2,
                title="unrelated photo",
                content="just a photo of a cat",
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
            "hivemind:message_feed:1"
        ]

    def test_validated_sort_buckets_by_validation_state(self) -> None:
        """Deterministic validated ordering over a mixed pool: approved
        distillation first, parseable workflow second, raw messages last."""
        pool = [
            {
                **_message_row(1, created_at="2026-08-02T00:00:00Z"),
                "_hivemind_table": "message_feed",
            },
            {
                **_distillation_row(2, status="approved", created_at="2026-08-03T00:00:00Z"),
                "_hivemind_table": "unified_feed",
            },
            {
                **_workflow_row(
                    "wf-1",
                    created_at="2026-08-01T00:00:00Z",
                    metadata={
                        "has_workflow_json": True,
                        "workflow_semantics": {
                            "promotion_gates": {"parseable_workflow": True}
                        },
                    },
                ),
                "_hivemind_table": "external_resources",
            },
        ]
        ordered = _order_hivemind_rows(pool, sort="validated", query="ltx")
        buckets = [_validated_bucket(row) for row in ordered]
        assert buckets == sorted(buckets)
        assert str(ordered[0].get("kind")) == "distillation"

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
        assert result.result["hits"][0]["evidence_id"] == "hivemind:message_feed:42"

    def test_opaque_cursor_pages_deterministically(self) -> None:
        rows = [
            _message_row(i, title=f"LTX entry {i}", created_at=f"2026-08-{10 - i:02d}T00:00:00Z")
            for i in range(1, 6)
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            page1 = hivemind_search(
                "ltx", filters={"source_type": "discord", "sort": "recent"}, limit=2
            )
            assert page1.status is ToolStatus.OK
            assert page1.result["count"] == 2
            assert page1.result["has_more"] is True
            next_cursor = page1.result["next_cursor"]
            assert isinstance(next_cursor, str) and next_cursor

            page2 = hivemind_search(
                "ltx",
                filters={"source_type": "discord", "sort": "recent"},
                cursor=next_cursor,
                limit=2,
            )
            assert page2.status is ToolStatus.OK
            assert page2.result["count"] == 2
            assert page2.result["has_more"] is True

            page3 = hivemind_search(
                "ltx",
                filters={"source_type": "discord", "sort": "recent"},
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
        assert ids == [f"hivemind:message_feed:{i}" for i in range(1, 6)]

    def test_cursor_beyond_end_returns_no_results(self) -> None:
        rows = [_message_row(1, title="LTX entry", created_at="2026-08-05T00:00:00Z")]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx",
                filters={"source_type": "discord", "sort": "recent"},
                cursor=_cursor(100),
            )
        assert result.status is ToolStatus.NO_RESULTS

    def test_no_results_on_empty_corpus(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([])),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "discord"}
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert result.result is None
        assert result.evidence_ids == ()


class TestTransportOnlyGuarantee:
    def test_hit_shape_is_stable_and_free_of_judgment(self) -> None:
        rows = [
            _message_row(
                7,
                title="LTX pipeline",
                created_at="2026-08-01T00:00:00Z",
            )
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "discord"}
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
        assert hit["evidence_id"] == "hivemind:message_feed:7"
        assert hit["source_type"] == "discord"
        assert hit["semantics"] is None
        assert hit["created_at"] == "2026-08-01T00:00:00Z"
        # No task classification / winner / enough-check / stop fields.
        for key in ("decision", "winner", "enough", "stop_reason", "classification"):
            assert key not in result.result

    def test_partial_scope_failure_degrades_with_diagnostics(self) -> None:
        """With structured criteria present, the corpus search runs BOTH text
        scopes and the non-text distillation scope; a persistent 57014 on a
        scope degrades to a per-scope diagnostic while the others still
        contribute hits."""

        def _responder(req: Any, url: str) -> Any:
            if "/message_feed?" in url:
                return _json_response(
                    [_message_row(1, title="LTX workflow", created_at="2026-08-05T00:00:00Z")]
                )
            return _statement_timeout_error(req)

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _responder),
        ):
            result = hivemind_search("ltx", filters={"has_workflow": True}, limit=10)
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 1
        codes = {d.code for d in result.diagnostics}
        assert codes == {"hivemind_scope_failed"}
        assert result.diagnostics[0].details["scope"] == "external_resources:workflow"
        assert result.diagnostics[1].details["scope"] == "unified_feed:distillation"

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

    def test_resolves_message_feed_message_and_unified_distillation(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([_message_row(42)])),
        ):
            result = hivemind_get("hivemind:message_feed:42")
        assert result.status is ToolStatus.OK
        assert result.result["source_type"] == "discord"
        assert result.result["table"] == "message_feed"
        assert "message_id=eq.42" in seen[0]

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


# ── Batch 13: IR-shaped record serving (surface lens / typed evidence) ───────


class TestServeRecordView:
    """Record matrix: workflow (UI/API/envelope) → surface lens; message →
    typed non-workflow; malformed → typed malformed; all with evidence IDs."""

    def test_workflow_ui_shape_serves_surface_lens(self) -> None:
        row = _workflow_row("wf-ui", payload={"workflow_json": _ui_workflow_json()})
        view = serve_hivemind_record(
            row, evidence_id="hivemind:external_resources:wf-ui"
        )
        assert isinstance(view, HivemindRecordView)
        assert view.record_type == "workflow"
        assert view.shape == "ui"
        assert view.evidence_id == "hivemind:external_resources:wf-ui"
        assert view.source_type == "workflow"
        # The served content is the IR surface lens (the Python view), not the
        # raw JSON: node assignments with named sockets, no raw graph keys.
        assert "loadaudio = LoadAudio(" in view.surface_lens
        assert "conditioning_1=loadaudio.AUDIO_0" in view.surface_lens
        assert '"nodes"' not in view.surface_lens
        assert '"links"' not in view.surface_lens
        assert "workflow_json" not in view.surface_lens
        assert view.content is None and view.error is None

    def test_workflow_api_shape_serves_surface_lens(self) -> None:
        row = _workflow_row(
            "wf-api",
            payload={
                "workflow_json": {"3": {"class_type": "KSampler", "inputs": {"seed": 42}}}
            },
        )
        view = serve_hivemind_record(
            row, evidence_id="hivemind:external_resources:wf-api"
        )
        assert view.record_type == "workflow"
        assert view.shape == "api"
        assert "ksampler = KSampler(seed=42)" in view.surface_lens

    def test_workflow_envelope_shape_serves_surface_lens(self) -> None:
        row = _workflow_row(
            "wf-env", payload={"workflow_json": _envelope_workflow_json()}
        )
        view = serve_hivemind_record(
            row, evidence_id="hivemind:external_resources:wf-env"
        )
        assert view.record_type == "workflow"
        assert view.shape == "vibe"
        assert "loadaudio = LoadAudio(" in view.surface_lens

    def test_message_row_is_typed_non_workflow_with_content(self) -> None:
        row = _message_row(42)
        view = serve_hivemind_record(row, evidence_id="hivemind:message_feed:42")
        assert view.record_type == "non_workflow"
        assert view.source_type == "discord"
        # The agent sees the record type + its actual content (text/body).
        assert view.content == "ltx discussion: community chatter about ltx"
        assert view.surface_lens is None and view.error is None

    def test_distillation_row_is_typed_non_workflow_with_content(self) -> None:
        row = _distillation_row(7)
        view = serve_hivemind_record(row, evidence_id="hivemind:unified_feed:7")
        assert view.record_type == "non_workflow"
        assert view.source_type == "distillation"
        assert view.content == "distilled ltx knowledge"

    def test_workflow_kind_without_json_is_typed_malformed(self) -> None:
        row = _workflow_row("wf-nojson")
        view = serve_hivemind_record(
            row, evidence_id="hivemind:external_resources:wf-nojson"
        )
        assert view.record_type == "malformed_record"
        assert "no workflow JSON" in view.error
        # Never pretended to be a workflow; never normalized with a fake shape.
        assert view.surface_lens is None and view.content is None

    def test_non_object_workflow_json_is_typed_malformed(self) -> None:
        # A workflow_json that is a string is never normalized with a fake
        # shape — it is a workflow-shaped record that cannot be normalized.
        row = _workflow_row("wf-str", payload={"workflow_json": "not an object"})
        view = serve_hivemind_record(
            row, evidence_id="hivemind:external_resources:wf-str"
        )
        assert view.record_type == "malformed_record"
        assert "no workflow JSON" in view.error

    def test_unknown_shape_fails_named_door_normalization_typed_malformed(self) -> None:
        # A workflow-shaped JSON object whose shape no named door accepts.
        row = _workflow_row(
            "wf-unknown", payload={"workflow_json": {"nodes": "garbage", "links": []}}
        )
        view = serve_hivemind_record(
            row, evidence_id="hivemind:external_resources:wf-unknown"
        )
        assert view.record_type == "malformed_record"
        assert "unsupported workflow shape" in view.error
        assert view.surface_lens is None


class TestGetTypedRecordView:
    """hivemind_get returns the typed record view; the raw row stays under
    ``row`` (the evidence artifact side) and never leaks into the view."""

    def test_get_returns_typed_surface_lens_for_workflow(self) -> None:
        row = _workflow_row(
            "wf-ui", title="LTX pipeline", payload={"workflow_json": _ui_workflow_json()}
        )
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([row])),
        ):
            result = hivemind_get("hivemind:external_resources:wf-ui")
        assert result.status is ToolStatus.OK
        view = result.result["record_view"]
        assert view["record_type"] == "workflow"
        assert view["shape"] == "ui"
        assert view["evidence_id"] == "hivemind:external_resources:wf-ui"
        assert "loadaudio = LoadAudio(" in view["surface_lens"]
        # The raw source row is retained (the evidence artifact side) ...
        assert result.result["row"]["id"] == "wf-ui"
        assert result.result["row"]["payload"]["workflow_json"]["nodes"]
        # ... and the model-facing view carries no raw JSON: no payload, no
        # raw graph keys, no workflow_json key.
        assert "payload" not in view
        assert "row" not in view
        assert "workflow_json" not in view["surface_lens"]
        assert '"nodes"' not in view["surface_lens"]

    def test_get_returns_typed_non_workflow_for_message(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([_message_row(42)])),
        ):
            result = hivemind_get("hivemind:message_feed:42")
        assert result.status is ToolStatus.OK
        view = result.result["record_view"]
        assert view["record_type"] == "non_workflow"
        assert view["content"] == "ltx discussion: community chatter about ltx"
        # The raw row is still resolvable as the evidence artifact side.
        assert result.result["row"]["content"] == (
            "ltx discussion: community chatter about ltx"
        )

    def test_get_returns_typed_malformed_for_workflow_without_json(self) -> None:
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response([_workflow_row("wf-nojson")])),
        ):
            result = hivemind_get("hivemind:external_resources:wf-nojson")
        assert result.status is ToolStatus.OK
        view = result.result["record_view"]
        assert view["record_type"] == "malformed_record"
        assert "no workflow JSON" in view["error"]
        assert "surface_lens" not in view

    def test_record_view_round_trips_through_contract(self) -> None:
        row = _workflow_row("wf-ui", payload={"workflow_json": _ui_workflow_json()})
        view = serve_hivemind_record(
            row, evidence_id="hivemind:external_resources:wf-ui"
        )
        rebuilt = HivemindRecordView.from_dict(view.to_dict())
        assert rebuilt == view
        assert rebuilt.surface_lens == view.surface_lens


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

    def test_partial_scope_429_keeps_hits_and_opens_cooldown(self, tmp_path: Path) -> None:
        """Review C4 (HIVEMIND-SCOPE-FIX-REV): a 429 on ONE scope plus hits
        from another returns OK with the merged hits AND opens the shared
        R2-B2 cooldown circuit (previously the partial-success path skipped
        cooldown entirely)."""

        def _responder(req: Any, *args: Any, **kwargs: Any) -> Any:
            if "/external_resources?" in unquote_plus(req.full_url):
                raise urllib.error.HTTPError(
                    req.full_url,
                    429,
                    "Too Many Requests",
                    {"Retry-After": "7"},
                    io.BytesIO(b"{}"),
                )
            return _json_response([_message_row(11)])

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _responder),
        ):
            first = hivemind_search(
                "ltx", filters={"source_type": "workflow"}, cache_root=tmp_path
            )
        # This call keeps its merged hits and OK status...
        assert first.status is ToolStatus.OK
        assert first.result["count"] == 1
        assert first.evidence_ids == ("hivemind:message_feed:11",)
        # ...with the 429's Retry-After metadata preserved in diagnostics...
        rate_diags = [
            d for d in first.diagnostics if d.code == "hivemind_rate_limited"
        ]
        assert len(rate_diags) == 1
        assert rate_diags[0].details["scope"] == "external_resources:workflow"
        assert rate_diags[0].details["status_code"] == 429
        assert rate_diags[0].details["retry_after_seconds"] == 7.0
        # ...and the circuit is open: the NEXT call is blocked, no network.
        with patch("urllib.request.urlopen", side_effect=_no_network):
            second = hivemind_search("ltx", cache_root=tmp_path)
        assert second.status is ToolStatus.RATE_LIMITED
        assert second.retry_after_seconds is not None
        assert 0.0 < second.retry_after_seconds <= 7.0

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
        rows = [_message_row(1, title="LTX pipeline")]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(
                "ltx", filters={"source_type": "discord"}
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
            return _json_response([_message_row(1, title="LTX workflow")])

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ) as sleep, patch("urllib.request.urlopen", side_effect=_flaky):
            result = hivemind_search("ltx", filters={"source_type": "discord"})
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 1
        assert calls["n"] == 2
        sleep.assert_called_once()

    def test_57014_on_fat_query_succeeds_on_degraded_query(self) -> None:
        """RC1: persistent 57014 on the leading-wildcard query retries the
        degraded (no leading ``*``) query and returns hits."""
        from urllib.parse import unquote

        calls: list[str] = []

        def _fat_then_degraded(req: Any, *args: Any, **kwargs: Any) -> Any:
            url = unquote(req.full_url)
            calls.append(url)
            if "ilike.*" in url:
                raise urllib.error.HTTPError(
                    req.full_url,
                    500,
                    "statement timeout",
                    {},
                    io.BytesIO(
                        b'{"code":"57014","message":"canceling statement due to statement timeout"}'
                    ),
                )
            return _json_response([_message_row(9, title="LTX workflow")])

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch("urllib.request.urlopen", side_effect=_fat_then_degraded):
            result = hivemind_search("ltx video generation workflow")
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 1
        assert any("ilike.*" in url for url in calls)
        assert any("ilike." in url and "ilike.*" not in url for url in calls)

    def test_persistent_57014_is_soft_miss_not_hard_failure(self) -> None:
        calls: list[str] = []

        def _persistent(req: Any, *args: Any, **kwargs: Any) -> Any:
            calls.append(unquote_plus(req.full_url))
            return _statement_timeout_error(req, *args, **kwargs)

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch("urllib.request.urlopen", side_effect=_persistent):
            result = hivemind_search("ltx")
        assert result.status is ToolStatus.UNAVAILABLE
        assert result.diagnostics[0].code == "hivemind_statement_timeout"
        assert result.evidence_ids == ()
        assert result.result is None
        assert len(calls) == 6  # per text scope: two fat attempts + one degraded
        degraded = [url for url in calls if "ilike." in url and "ilike.*" not in url]
        assert len(degraded) == 2

    def test_per_scope_deadline_gives_each_scope_full_budget(self) -> None:
        """§37.3: deadlines are computed PER SCOPE — a scope that spends its
        whole budget cannot starve later scopes; each attempt is offered the
        full timeout, and only when EVERY scope fails does the first error
        surface."""
        clock = {"t": 0.0}
        calls: list[float] = []

        def _timeout(req: Any, *args: Any, **kwargs: Any) -> Any:
            calls.append(float(kwargs["timeout"]))
            clock["t"] = 5.0
            raise TimeoutError("spent the operation budget")

        with patch(
            "vibecomfy.executor.hivemind_clients.time.monotonic",
            side_effect=lambda: clock["t"],
        ), patch("urllib.request.urlopen", side_effect=_timeout):
            result = hivemind_search("ltx", timeout=5.0)
        assert result.status is ToolStatus.TIMEOUT
        assert result.diagnostics[0].code == "hivemind_timeout"
        # BOTH text scopes were attempted, each with its own full budget.
        assert calls == [5.0, 5.0]

    def test_partial_rows_survive_later_scope_deadlines(self) -> None:
        """§37.3: scopes that complete contribute hits even when other scopes
        spend their whole budgets — no shared clock starves the merge."""
        clock = {"t": 0.0}
        seen: list[str] = []

        def _partial(req: Any, *args: Any, **kwargs: Any) -> Any:
            url = unquote_plus(req.full_url)
            seen.append(url)
            if "/message_feed?" in url:
                clock["t"] = 1.0
                return _json_response([_message_row(5, title="before timeout")])
            clock["t"] = 5.0
            raise TimeoutError("later scope spent the remaining budget")

        with patch(
            "vibecomfy.executor.hivemind_clients.time.monotonic",
            side_effect=lambda: clock["t"],
        ), patch("urllib.request.urlopen", side_effect=_partial):
            result = hivemind_search("ltx", filters={"has_workflow": True}, timeout=5.0)
        assert result.status is ToolStatus.OK
        assert result.evidence_ids == (
            "hivemind:message_feed:5",
        )
        assert len(seen) == 3  # external_resources, message_feed, unified_feed
        assert "/external_resources?" in seen[0]
        assert any("/message_feed?" in url for url in seen)
        assert any("kind=eq.distillation" in url for url in seen)

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
        assert calls["n"] == 2  # one attempt per text scope, no retry on a generic 500


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
        """An explicit model_family filter ANDs an alias OR-group into the
        lean message-feed content query."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            hivemind_search(
                "ltx",
                filters={"source_type": "workflow", "model_family": "ltx"},
            )
        assert len(seen) == 2
        # Family alias translation stays a message_feed content concern;
        # external_resources carries the plain title/body token query.
        resource_url, message_url = seen
        assert "/external_resources?" in resource_url
        assert "or=(title.ilike.*ltx*,body.ilike.*ltx*)" in resource_url
        assert "ltxv" not in resource_url
        assert "/message_feed?" in message_url
        assert "and=(or:(content.ilike.*ltx*)" in message_url
        assert "content.ilike.*ltxv*" in message_url


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
            _message_row(1, title="LTX pipeline"),
            {
                # A message row without its natural message_id column:
                # parseable-looking, but hivemind_get could never resolve it.
                "content": "orphan message",
                "channel_name": "ltx_chatter",
                "created_at": "2026-08-06T00:00:00Z",
            },
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search("ltx", filters={"source_type": "discord"})
        assert result.status is ToolStatus.OK
        assert [h["evidence_id"] for h in result.result["hits"]] == [
            "hivemind:message_feed:1"
        ]
        assert result.evidence_ids == ("hivemind:message_feed:1",)

    def test_returned_ids_all_resolve_through_get(self) -> None:
        rows = [
            _message_row(1, title="LTX pipeline"),
            _message_row(2, title="LTX fast mode"),
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            search = hivemind_search("ltx", filters={"source_type": "discord"})
        assert search.status is ToolStatus.OK
        for evidence_id in search.evidence_ids:
            row_id = evidence_id.rsplit(":", 1)[-1]
            with patch(
                "urllib.request.urlopen",
                side_effect=_capture_urlopen(
                    [],
                    _json_response([_message_row(int(row_id))]),
                ),
            ):
                got = hivemind_get(evidence_id)
            assert got.status is ToolStatus.OK, evidence_id
            assert got.result["evidence_id"] == evidence_id
