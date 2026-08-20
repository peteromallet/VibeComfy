"""Unit tests for the surviving Hivemind transport helpers.

Covers the shared PostgREST transport (``_hivemind_get_table``), the
distinctive-token / phrase-query formulation used by the agent search tool,
and the community summary formatter (moved to the agent response contract,
where the research route consumes it).  The legacy workflow/messages clients
and their ranking/recovery machinery were deleted with the shadow research
phase; their tests are gone with them.  All transport is mocked via
``urllib.request.urlopen`` — no live network.
"""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any
from unittest.mock import patch
from urllib.parse import unquote_plus

import pytest

from vibecomfy.comfy_nodes.agent._frag_response_contract import format_community_summary
from vibecomfy.executor.hivemind_clients import (
    HivemindError,
    _distinctive_tokens,
    _hivemind_get_table,
    _hivemind_single_or_phrase_ilike,
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


# ── Distinctive tokens / phrase query formulation ────────────────────────────


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
        # REC-C: per-token OR (index-friendly) instead of one multi-word
        # leading-wildcard phrase, which timed out on unified_feed (57014).
        assert _hivemind_single_or_phrase_ilike("ltx 2.5") == (
            "(title.ilike.*ltx*,body.ilike.*ltx*,title.ilike.*2.5*,body.ilike.*2.5*)"
        )
        assert _hivemind_single_or_phrase_ilike("ltx") == (
            "(title.ilike.*ltx*,body.ilike.*ltx*)"
        )
        assert _hivemind_single_or_phrase_ilike("what is") is None


# ── Community summary (agent response contract) ──────────────────────────────


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
