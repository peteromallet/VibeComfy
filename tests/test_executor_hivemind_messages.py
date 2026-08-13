"""Unit tests for the messages Hivemind client (B01).

Covers the shared PostgREST transport, the channel map / query formulation
helpers, the ``unified_feed`` + channel-scoped ``message_feed`` client steps,
the normalize-only runner, display order / dedupe / cap, and the community
summary formatter.  All transport is mocked via ``urllib.request.urlopen`` —
no live network.
"""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any
from unittest.mock import patch
from urllib.parse import unquote_plus

import pytest

from vibecomfy.executor.hivemind_clients import (
    HivemindError,
    _CHANNEL_GROUPS,
    _channel_scope_for_query,
    _default_hivemind_messages_client,
    _distinctive_tokens,
    _hivemind_get_table,
    _hivemind_item_id,
    _hivemind_single_or_phrase_ilike,
    _message_dedupe_key,
    _message_display_order,
    _normalize_hivemind_message_source,
    _raw_message_hits_are_thin,
    _run_hivemind_messages_research,
    format_community_summary,
)
from vibecomfy.executor.research import (
    WORKFLOW_RESEARCH_GUIDANCE,
    _TIER_TTL_MAP,
    _build_summary,
    _source_tier_for_source,
)

_HIVEMIND_ROOT = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1"


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


def _message_row(
    message_id: int = 882299448795242546,
    content: str = "MiniMax H3 is amazing",
    author: str = "alice",
    channel: str = "ltx_chatter",
    created_at: str = "2026-08-01T00:00:00Z",
) -> dict[str, Any]:
    return {
        "message_id": message_id,
        "content": content,
        "author_name": author,
        "channel_name": channel,
        "channel_id": 998877665544332211,
        "created_at": created_at,
    }


# ── Shared transport ─────────────────────────────────────────────────────────


class TestHivemindGetTable:
    def test_url_shape_and_headers(self) -> None:
        seen: list[tuple[str, dict[str, str]]] = []

        def _urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
            seen.append((unquote_plus(req.full_url), dict(req.headers)))
            return _json_response([{"id": 1}])

        with patch("urllib.request.urlopen", side_effect=_urlopen):
            result = _hivemind_get_table(
                "unified_feed",
                {"select": "*", "kind": "eq.message"},
                timeout=1.0,
            )
        assert result == [{"id": 1}]
        url, headers = seen[0]
        assert url.startswith(f"{_HIVEMIND_ROOT}/unified_feed?")
        assert "select=*" in url
        assert "kind=eq.message" in url
        assert headers["Accept"] == "application/json"
        apikey = next(v for k, v in headers.items() if k.casefold() == "apikey")
        assert apikey.startswith("sb_publishable_")
        assert headers["Authorization"] == f"Bearer {apikey}"

    def test_http_error_raises_hivemind_error(self) -> None:
        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            raise urllib.error.HTTPError(
                req.full_url, 500, "Internal Server Error", {}, io.BytesIO(b'{"code":"57014"}')
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            with pytest.raises(HivemindError, match="HTTP error 500"):
                _hivemind_get_table("unified_feed", {"select": "*"}, timeout=1.0)

    def test_timeout_raises_hivemind_error(self) -> None:
        def _slow(*args: Any, **kwargs: Any) -> Any:
            raise TimeoutError("timed out")

        with patch("urllib.request.urlopen", side_effect=_slow):
            with pytest.raises(HivemindError, match="timed out"):
                _hivemind_get_table("message_feed", {"select": "*"}, timeout=0.01)

    def test_invalid_json_raises_hivemind_error(self) -> None:
        with patch(
            "urllib.request.urlopen",
            return_value=_MockResponse(b"not json"),
        ):
            with pytest.raises(HivemindError, match="invalid JSON"):
                _hivemind_get_table("message_feed", {"select": "*"}, timeout=1.0)


# ── Channel map / query formulation ──────────────────────────────────────────


class TestChannelScope:
    def test_ltx_scope_includes_live_updates(self) -> None:
        scope = _channel_scope_for_query("what do people think about LTX 2.5?")
        assert scope[0] == "daily_summaries"
        assert "ltx_chatter" in scope
        assert "ltx_resources" in scope
        assert "live_updates" in scope

    def test_minimax_scope_includes_minimax_h3_chatter(self) -> None:
        scope = _channel_scope_for_query("MiniMax H3")
        assert scope[0] == "daily_summaries"
        assert "minimax_h3_chatter" in scope
        assert "live_updates" in scope

    def test_general_fallback_never_empty(self) -> None:
        scope = _channel_scope_for_query("what do people think?")
        assert scope[0] == "daily_summaries"
        assert "chatter" in scope
        assert "live_updates" in scope
        assert len(scope) <= 10

    def test_wan_scope(self) -> None:
        scope = _channel_scope_for_query("wan 2.2 vace")
        assert "wan_chatter" in scope
        assert "wan_resources" in scope

    def test_all_groups_are_known(self) -> None:
        scope = _channel_scope_for_query("ltx comfy minimax wan training")
        assert len(scope) <= 10
        assert all(
            channel in {c for group in _CHANNEL_GROUPS.values() for c in group}
            or channel == "daily_summaries"
            for channel in scope
        )


class TestDistinctiveTokens:
    def test_single_token_query_survives(self) -> None:
        assert _distinctive_tokens("ltx") == ["ltx"]
        assert _distinctive_tokens("minimax") == ["minimax"]

    def test_version_tokens_survive(self) -> None:
        assert _distinctive_tokens("ltx 2.5") == ["ltx", "2.5"]
        assert _distinctive_tokens("wan 2.2") == ["wan", "2.2"]

    def test_question_words_kept_and_stopwords_dropped(self) -> None:
        tokens = _distinctive_tokens(
            "What do people think about the new MiniMax H3 model?"
        )
        assert tokens == ["do", "people", "think", "about", "new", "MiniMax", "H3"]

    def test_capped_at_eight(self) -> None:
        tokens = _distinctive_tokens("one two three four five six seven eight nine ten")
        assert len(tokens) == 8

    def test_single_or_phrase_ilike(self) -> None:
        assert _hivemind_single_or_phrase_ilike("ltx 2.5") == (
            "(title.ilike.*ltx 2.5*,body.ilike.*ltx 2.5*)"
        )
        assert _hivemind_single_or_phrase_ilike("ltx") == (
            "(title.ilike.*ltx*,body.ilike.*ltx*)"
        )
        assert _hivemind_single_or_phrase_ilike("what is") is None


# ── Raw thinness predicate ───────────────────────────────────────────────────


class TestRawMessageHitsAreThin:
    def test_empty_rows_are_thin(self) -> None:
        assert _raw_message_hits_are_thin([], "MiniMax H3") is True

    def test_approved_distillation_with_token_is_not_thin(self) -> None:
        rows = [
            {
                "kind": "distillation",
                "title": "MiniMax H3 review",
                "body": "community consensus",
                "metadata": {"status": "approved"},
            }
        ]
        assert _raw_message_hits_are_thin(rows, "MiniMax H3") is False

    def test_approved_distillation_without_token_is_thin(self) -> None:
        rows = [
            {
                "kind": "distillation",
                "title": "unrelated",
                "body": "no mention",
                "metadata": {"status": "approved"},
            }
        ]
        assert _raw_message_hits_are_thin(rows, "MiniMax H3") is True

    def test_three_messages_with_token_are_not_thin(self) -> None:
        rows = [
            {"kind": "message", "title": f"post {i}", "body": "MiniMax H3 wow"}
            for i in range(3)
        ]
        assert _raw_message_hits_are_thin(rows, "MiniMax H3") is False

    def test_two_messages_are_thin(self) -> None:
        rows = [
            {"kind": "message", "title": f"post {i}", "body": "MiniMax H3 wow"}
            for i in range(2)
        ]
        assert _raw_message_hits_are_thin(rows, "MiniMax H3") is True

    def test_message_feed_rows_count_as_messages(self) -> None:
        rows = [
            {
                "_hivemind_table": "message_feed",
                "content": "MiniMax H3 is amazing",
                "channel_name": "minimax_h3_chatter",
            }
            for _ in range(3)
        ]
        assert _raw_message_hits_are_thin(rows, "MiniMax H3") is False

    def test_pending_distillations_count_toward_threshold(self) -> None:
        rows = [
            {
                "kind": "distillation",
                "title": "draft",
                "body": "MiniMax H3 discussion",
                "metadata": {"status": "pending"},
            }
            for _ in range(3)
        ]
        assert _raw_message_hits_are_thin(rows, "MiniMax H3") is False


# ── Messages client: table / parameter shapes ────────────────────────────────


class TestMessagesClientQueryShapes:
    def test_steps_a_b_c_d_urls(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = _default_hivemind_messages_client("MiniMax H3", timeout=1.0)

        assert result["results"] == []
        assert len(seen) == 4

        step_a = seen[0]
        assert "/unified_feed?" in step_a
        assert "kind=eq.distillation" in step_a
        assert "or=(title.ilike.*MiniMax H3*,body.ilike.*MiniMax H3*)" in step_a
        assert "limit=20" in step_a

        step_b = seen[1]
        assert "/unified_feed?" in step_b
        assert "kind=eq.message" in step_b
        assert "or=(title.ilike.*MiniMax H3*,body.ilike.*MiniMax H3*)" in step_b
        assert "order=created_at.desc" in step_b
        assert "limit=20" in step_b

        step_c = seen[2]
        assert "/message_feed?" in step_c
        assert "channel_name=in.(daily_summaries,minimax_h3_chatter,ltx_chatter,live_updates,chatter,art_sharing)" in step_c
        assert "content=ilike.*MiniMax H3*" in step_c
        assert "order=created_at.desc" in step_c
        assert "limit=30" in step_c

        step_d = seen[3]
        assert "/message_feed?" in step_d
        assert "or=(content.ilike.*MiniMax*,content.ilike.*H3*)" in step_d
        assert "channel_name=in.(daily_summaries,minimax_h3_chatter,ltx_chatter,live_updates,chatter,art_sharing)" in step_d
        assert "limit=30" in step_d

    def test_not_thin_skips_message_feed(self) -> None:
        seen: list[str] = []
        rows = [
            {"kind": "message", "title": f"post {i}", "body": "MiniMax H3 wow"}
            for i in range(3)
        ]

        def _responder(req: Any, url: str) -> _MockResponse:
            if "kind=eq.message" in url:
                return _json_response(rows)
            return _json_response([])

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _responder),
        ):
            result = _default_hivemind_messages_client("MiniMax H3", timeout=1.0)

        assert len(result["results"]) == 3
        assert len(seen) == 2  # Step A + Step B only
        assert all("/message_feed?" not in url for url in seen)

    def test_results_are_stamped_for_audit(self) -> None:
        seen: list[str] = []
        rows = [
            {"kind": "message", "title": f"post {i}", "body": "MiniMax H3 wow"}
            for i in range(3)
        ]

        def _responder(req: Any, url: str) -> _MockResponse:
            return _json_response(rows)

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _responder),
        ):
            result = _default_hivemind_messages_client("MiniMax H3", timeout=1.0)

        stamped = result["results"][0]
        assert stamped["_hivemind_table"] == "unified_feed"
        assert stamped["_match_query"] == "MiniMax H3"

    def test_step_d_individual_token_or_for_raw_minimax_question(self) -> None:
        """A raw NL MiniMax question must match via Step-D token OR."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            _default_hivemind_messages_client(
                "What do people think about the new MiniMax H3 model?",
                timeout=1.0,
            )

        step_d = seen[3]
        assert "or=(content.ilike.*do*,content.ilike.*people*,content.ilike.*think*,content.ilike.*about*,content.ilike.*new*,content.ilike.*MiniMax*,content.ilike.*H3*)" in step_d
        assert "channel_name=in.(daily_summaries,minimax_h3_chatter,ltx_chatter,live_updates,chatter,art_sharing)" in step_d

    def test_no_family_query_uses_general_scope(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            _default_hivemind_messages_client(
                "what do people think about this?",
                timeout=1.0,
            )

        step_c = seen[2]
        assert "channel_name=in.(daily_summaries,chatter,live_updates,nsfw,introductions,art_sharing)" in step_c

    def test_empty_tokens_short_circuits(self) -> None:
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = _default_hivemind_messages_client("what is the", timeout=1.0)
        assert result == {"results": [], "warnings": []}
        assert seen == []


# ── Messages client: timeout recovery ────────────────────────────────────────


class TestMessagesClientRecovery:
    def test_unified_timeout_is_thin_and_runs_message_feed(self) -> None:
        seen: list[str] = []

        def _responder(req: Any, url: str) -> Any:
            if "/unified_feed?" in url:
                raise TimeoutError("timed out")
            return _json_response([])

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _responder),
        ):
            result = _default_hivemind_messages_client("MiniMax H3", timeout=0.01)

        assert any("timed out" in w for w in result["warnings"])
        assert any("/message_feed?" in url for url in seen)

    def test_http_500_falls_back_to_daily_summaries(self) -> None:
        seen: list[str] = []
        daily_rows = [
            _message_row(message_id=100 + i, content="MiniMax H3 roundup", channel="daily_summaries")
            for i in range(3)
        ]

        def _responder(req: Any, url: str) -> Any:
            if "/unified_feed?" in url:
                return _json_response([])
            if "channel_name=in.(daily_summaries,minimax_h3_chatter" in url:
                raise urllib.error.HTTPError(
                    req.full_url, 500, "statement timeout", {}, io.BytesIO(b'{"code":"57014"}')
                )
            if "channel_name=in.(daily_summaries)" in url:
                return _json_response(daily_rows)
            return _json_response([])

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _responder),
        ):
            result = _default_hivemind_messages_client("MiniMax H3", timeout=1.0)

        assert any("HTTP error 500" in w for w in result["warnings"])
        daily_urls = [u for u in seen if "channel_name=in.(daily_summaries)" in u]
        assert daily_urls
        assert all(
            "channel_name=in.(daily_summaries)" in u and "minimax_h3_chatter" not in u
            for u in daily_urls
        )
        ids = {r["message_id"] for r in result["results"]}
        assert ids == {100, 101, 102}

    def test_full_failure_converts_to_warning(self) -> None:
        seen: list[str] = []

        def _responder(req: Any, url: str) -> Any:
            raise urllib.error.HTTPError(
                req.full_url, 500, "boom", {}, io.BytesIO(b"{}")
            )

        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _responder),
        ):
            result = _default_hivemind_messages_client("MiniMax H3", timeout=1.0)

        assert result["results"] == []
        assert len(result["warnings"]) >= 2
        # Recovery ladder: full scope -> daily_summaries -> densest group -> 90d
        assert len(seen) >= 4


# ── Item ids / dedupe keys ───────────────────────────────────────────────────


class TestStringSnowflakes:
    def test_hivemind_item_id_is_string(self) -> None:
        assert _hivemind_item_id({"message_id": 882299448795242546}) == "882299448795242546"
        assert _hivemind_item_id({"item_id": 42}) == "42"
        assert _hivemind_item_id({"id": "abc"}) == "abc"
        assert _hivemind_item_id({}) == ""

    def test_message_dedupe_key_uses_kind_and_string_id(self) -> None:
        key = _message_dedupe_key({"kind": "message", "message_id": 882299448795242546})
        assert key == "message:882299448795242546"
        assert isinstance(key, str)

    def test_dedupe_key_falls_back_to_url(self) -> None:
        key = _message_dedupe_key({"url": "https://example.com/x"})
        assert key == "https://example.com/x"


# ── Normalization (normalize-only runner) ────────────────────────────────────


class TestNormalizeMessageSource:
    def test_unified_feed_message_shape(self) -> None:
        item = {
            "kind": "message",
            "item_id": 882299448795242546,
            "title": "MiniMax H3 is amazing",
            "body": "made a music video with it",
            "author": "alice",
            "channel": "minimax_h3_chatter",
            "created_at": "2026-08-01T00:00:00Z",
            "url": "https://discord.com/channels/1/2/3",
        }
        out = _normalize_hivemind_message_source(item)
        assert out["source"] == "hivemind_message"
        assert out["title"] == "MiniMax H3 is amazing"
        assert out["class_type"] == "MiniMax H3 is amazing"
        assert out["author"] == "alice"
        assert out["channel"] == "minimax_h3_chatter"
        assert out["created_at"] == "2026-08-01T00:00:00Z"
        assert out["hivemind_id"] == "882299448795242546"
        assert out["url"] == "https://discord.com/channels/1/2/3"

    def test_distillation_shape(self) -> None:
        item = {
            "kind": "distillation",
            "item_id": 77,
            "title": "LTX 2.5 sentiment",
            "body": "fast and a clear improvement",
            "metadata": {"status": "approved", "confidence": 0.9},
        }
        out = _normalize_hivemind_message_source(item)
        assert out["source"] == "hivemind_distillation"
        assert out["distillation_status"] == "approved"
        assert out["confidence"] == 0.9
        assert out["channel"] == ""

    def test_message_feed_row_derives_title_from_content(self) -> None:
        item = {
            "_hivemind_table": "message_feed",
            "message_id": 882299448795242546,
            "content": "MiniMax H3 is amazing",
            "author_name": "alice",
            "channel_name": "minimax_h3_chatter",
            "created_at": "2026-08-01T00:00:00Z",
        }
        out = _normalize_hivemind_message_source(item)
        assert out["source"] == "hivemind_message"
        assert out["kind"] == "message"
        assert out["title"] == "MiniMax H3 is amazing"
        assert out["author"] == "alice"
        assert out["channel"] == "minimax_h3_chatter"

    def test_runner_never_fetches_workflow_json(self) -> None:
        """Discord attachment URLs must never be fetched as workflow JSON."""
        row = {
            "kind": "message",
            "item_id": 882299448795242546,
            "title": "look at this",
            "body": "workflow attached",
            "url": "https://cdn.discordapp.com/attachments/123/456/workflow.json",
            "author": "alice",
            "channel": "ltx_chatter",
        }

        def _fake_client(query: str, timeout: float) -> dict[str, Any]:
            return {"results": [row]}

        def _forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("runner must not open URLs")

        with patch("urllib.request.urlopen", side_effect=_forbidden):
            sources = _run_hivemind_messages_research(
                "ltx",
                client=_fake_client,
                timeout=1.0,
            )

        assert len(sources) == 1
        assert sources[0]["url"] == (
            "https://cdn.discordapp.com/attachments/123/456/workflow.json"
        )
        assert sources[0]["source"] == "hivemind_message"

    def test_runner_skips_non_dict_items(self) -> None:
        def _fake_client(query: str, timeout: float) -> dict[str, Any]:
            return {"results": ["junk", {"kind": "message", "item_id": 1, "body": "x"}]}

        sources = _run_hivemind_messages_research(
            "ltx",
            client=_fake_client,  # type: ignore[arg-type]
            timeout=1.0,
        )
        assert len(sources) == 1

    def test_runner_dedupes_by_string_id_and_caps_at_12(self) -> None:
        rows = [
            {"kind": "message", "item_id": i, "title": f"post {i}", "body": "ltx 2.5"}
            for i in range(13)
        ]
        # duplicate of row 0
        rows.append({"kind": "message", "item_id": 0, "title": "duplicate", "body": "ltx 2.5"})

        def _fake_client(query: str, timeout: float) -> dict[str, Any]:
            return {"results": rows}

        sources = _run_hivemind_messages_research(
            "ltx 2.5",
            client=_fake_client,  # type: ignore[arg-type]
            timeout=1.0,
        )
        assert len(sources) == 12
        ids = [s["hivemind_id"] for s in sources]
        assert len(ids) == len(set(ids))
        assert "0" in ids  # the duplicate survived exactly once


# ── Display order / low-IDF retention ────────────────────────────────────────


class TestMessageDisplayOrder:
    def _source(
        self,
        *,
        source: str,
        created_at: str,
        status: str | None = None,
        title: str = "t",
    ) -> dict[str, Any]:
        return {
            "class_type": title,
            "title": title,
            "source": source,
            "kind": "distillation" if source == "hivemind_distillation" else "message",
            "description": "body",
            "created_at": created_at,
            "distillation_status": status,
            "channel": "ltx_chatter" if source == "hivemind_message" else "",
        }

    def test_approved_then_pending_then_recency(self) -> None:
        sources = (
            self._source(source="hivemind_message", created_at="2026-08-03T00:00:00Z"),
            self._source(
                source="hivemind_distillation",
                created_at="2026-08-02T00:00:00Z",
                status="approved",
                title="approved old",
            ),
            self._source(
                source="hivemind_distillation",
                created_at="2026-08-04T00:00:00Z",
                status="pending",
                title="pending new",
            ),
        )
        ordered = _message_display_order(sources)
        assert [s["title"] for s in ordered] == [
            "approved old",
            "pending new",
            "t",
        ]

    def test_recency_inside_status_bucket(self) -> None:
        sources = (
            self._source(
                source="hivemind_distillation",
                created_at="2026-08-01T00:00:00Z",
                status="approved",
                title="old approved",
            ),
            self._source(
                source="hivemind_distillation",
                created_at="2026-08-05T00:00:00Z",
                status="approved",
                title="new approved",
            ),
            self._source(source="hivemind_message", created_at="2026-08-01T00:00:00Z", title="old msg"),
            self._source(source="hivemind_message", created_at="2026-08-06T00:00:00Z", title="new msg"),
        )
        ordered = _message_display_order(sources)
        assert [s["title"] for s in ordered] == [
            "new approved",
            "old approved",
            "new msg",
            "old msg",
        ]

    def test_low_idf_row_is_not_dropped(self) -> None:
        """A low-IDF on-topic row (title lacks every query token) stays visible."""
        low_idf = {
            "class_type": "It's great!",
            "title": "It's great!",
            "source": "hivemind_message",
            "kind": "message",
            "description": "MiniMax H3 works really well",
            "score": 0,
            "created_at": "2026-08-01T00:00:00Z",
            "channel": "ltx_chatter",
        }
        ordered = _message_display_order((low_idf,))
        assert ordered == (low_idf,)

    def test_runner_keeps_low_idf_row(self) -> None:
        def _fake_client(query: str, timeout: float) -> dict[str, Any]:
            return {
                "results": [
                    {
                        "kind": "message",
                        "item_id": 5,
                        "title": "agree!",
                        "body": "MiniMax H3 is sick",
                        "author": "bob",
                        "channel": "minimax_h3_chatter",
                    }
                ]
            }

        sources = _run_hivemind_messages_research(
            "MiniMax H3",
            client=_fake_client,  # type: ignore[arg-type]
            timeout=1.0,
        )
        assert len(sources) == 1
        assert sources[0]["title"] == "agree!"
        assert sources[0]["score"] == 0


# ── Community summary ────────────────────────────────────────────────────────


class TestFormatCommunitySummary:
    def test_empty_result_sentence(self) -> None:
        assert (
            format_community_summary((), query="ltx 2.5")
            == 'No community discussion found for "ltx 2.5".'
        )

    def test_workflow_sources_do_not_count_as_community(self) -> None:
        sources = ({"source": "hivemind_workflow", "title": "wf"},)
        assert (
            format_community_summary(sources, query="ltx")
            == 'No community discussion found for "ltx".'
        )

    def test_message_line(self) -> None:
        sources = (
            {
                "source": "hivemind_message",
                "title": "MiniMax H3 is amazing",
                "description": "made a music video with it",
                "author": "alice",
                "channel": "minimax_h3_chatter",
            },
        )
        text = format_community_summary(sources, query="MiniMax H3")
        assert "alice in #minimax_h3_chatter: made a music video with it" in text
        # Messages render as author/channel/excerpt — the title is not invented
        # into the line.
        assert "MiniMax H3 is amazing" not in text

    def test_distillation_line(self) -> None:
        sources = (
            {
                "source": "hivemind_distillation",
                "title": "LTX 2.5 sentiment",
                "description": "fast and a clear improvement",
                "distillation_status": "approved",
                "confidence": 0.9,
            },
        )
        text = format_community_summary(sources, query="ltx 2.5")
        assert "LTX 2.5 sentiment (approved/0.9): fast and a clear improvement" in text

    def test_six_item_and_char_bounds(self) -> None:
        sources = tuple(
            {
                "source": "hivemind_message",
                "title": f"post {i}",
                "description": "x" * 120,
                "author": f"u{i}",
                "channel": "ltx_chatter",
            }
            for i in range(10)
        )
        text = format_community_summary(sources, query="ltx")
        assert text.count("\n") + 1 <= 6
        assert len(text) <= 800


# ── research.py integration (B01 task 7) ─────────────────────────────────────


class TestResearchSummaryIntegration:
    def test_build_summary_community_branch(self) -> None:
        sources = (
            {
                "source": "hivemind_message",
                "class_type": "MiniMax H3 is amazing",
                "channel": "minimax_h3_chatter",
            },
            {
                "source": "hivemind_message",
                "class_type": "still falls short",
                "channel": "ltx_chatter",
            },
        )
        summary = _build_summary(sources)
        assert summary.startswith("Found 2 community result(s):")
        assert "MiniMax H3 is amazing" in summary
        assert "Channels: ltx_chatter, minimax_h3_chatter." in summary
        assert WORKFLOW_RESEARCH_GUIDANCE not in summary

    def test_build_summary_message_only_omits_workflow_guidance(self) -> None:
        sources = (
            {"source": "hivemind_message", "class_type": "so how do we feel about ltx 2.5"},
        )
        summary = _build_summary(sources)
        assert WORKFLOW_RESEARCH_GUIDANCE not in summary
        assert "vibecomfy workflows list --ready" not in summary

    def test_build_summary_local_behavior_unchanged(self) -> None:
        assert _build_summary(()) == "No relevant local results found."
        assert _build_summary(({"class_type": "KSampler"},)) == (
            "Found 1 local result(s): KSampler"
        )

    def test_source_tier_and_ttl_map(self) -> None:
        assert _source_tier_for_source({"source": "hivemind_message"}) == "hivemind_message"
        assert _source_tier_for_source({"source": "hivemind_distillation"}) == "hivemind_distillation"
        assert _TIER_TTL_MAP["hivemind_message"] == _TIER_TTL_MAP["hivemind"]
        assert _TIER_TTL_MAP["hivemind_distillation"] == _TIER_TTL_MAP["hivemind"]
