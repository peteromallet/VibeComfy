"""HIVEMIND-SEARCH-SHAPE focused tests (operator directive §36, 2026-08-24).

Locks the lean query construction in the executor's hivemind client:

1. A representative free-text query builds <=4 ``content.ilike`` patterns on
   ``message_feed`` ONLY — no title/body doubling, no unified_feed text scope
   anywhere in built requests, tool default page limit <=5 preserved.
2. Distillation retrieval never goes through the text-search path: by id via
   ``hivemind_get`` or through non-text structured filters only.
3. The 429 Retry-After circuit and the SQLSTATE 57014 degrade path still
   function unchanged.
4. LIVE regression (directive-required): a representative multi-token query
   through the new construction completes <2s WITH hits.  Gated behind
   ``HIVEMIND_REGRESSION_LIVE=1`` and skipped when the endpoint is
   unreachable, so the default suite stays deterministic and isolated.

All transport except the live-gated test is mocked via ``urllib.request.urlopen``.
"""

from __future__ import annotations

import io
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any
from unittest.mock import patch
from urllib.parse import unquote_plus

import pytest

from vibecomfy.executor.hivemind_clients import (
    _SCOPE_FETCH_LIMIT,
    _SOURCE_TYPE_SCOPES,
    _hivemind_message_ilike,
)
from vibecomfy.executor.hivemind_tools import (
    _HIVEMIND_TOOL_DEFAULT_LIMIT,
    _HIVEMIND_TOOL_DEFAULT_TIMEOUT,
    hivemind_get,
    hivemind_search,
)
from vibecomfy.executor.tool_contracts import ToolStatus

_HIVEMIND_ROOT = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1"
_REPRESENTATIVE_QUERY = "wan animate workflow"


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
    def _urlopen(req: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(unquote_plus(req.full_url))
        if callable(responder):
            return responder(req, unquote_plus(req.full_url))
        return responder

    return _urlopen


def _message_row(item_id: int, content: str, created_at: str) -> dict[str, Any]:
    return {
        "message_id": item_id,
        "content": content,
        "author_name": "alice",
        "channel_name": "wan_chatter",
        "created_at": created_at,
        "permalink": "https://discord.com/channels/1/2/3",
    }


def _ilike_patterns(url: str) -> list[str]:
    """All ``*.ilike.*`` patterns appearing anywhere in a built request URL."""
    import re

    return re.findall(r"(?:title|body|content)\.ilike\.[^&()]*", url)


# ── 1. Lean shape of built requests ─────────────────────────────────────────


class TestLeanQueryShape:
    def test_representative_query_builds_single_lean_request(self) -> None:
        """S1/S2: a free-text query becomes ONE message_feed request whose
        text predicate is <=4 content.ilike ORs — no title/body doubling."""
        seen: list[str] = []
        rows = [
            _message_row(1, "wan animate workflow tips", "2026-08-01T00:00:00Z")
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response(rows)),
        ):
            result = hivemind_search(_REPRESENTATIVE_QUERY)
        assert result.status is ToolStatus.OK
        assert len(seen) == 1, seen
        url = seen[0]
        # Text search targets message_feed ONLY.
        assert f"{_HIVEMIND_ROOT}/message_feed?" in url
        assert "/unified_feed" not in url
        assert "/external_resources" not in url
        # content.ilike patterns only, at most 4 distinctive tokens.
        patterns = _ilike_patterns(url)
        assert patterns, url
        assert all(p.startswith("content.ilike.") for p in patterns)
        assert len(patterns) <= 4
        # The distinctive tokens survived; filler words did not consume them.
        assert any("wan" in p for p in patterns)
        assert any("animate" in p for p in patterns)
        # No title/body doubling anywhere in the request.
        assert "title.ilike" not in url and "body.ilike" not in url

    def test_token_cap_enforced_in_builder(self) -> None:
        """The message builder caps at the lean 4 content.ilike patterns even
        for token-rich queries."""
        built = _hivemind_message_ilike(
            "wan animate vace ltx hotshot sdxl qwen flux"
        )
        assert built is not None
        inner = built.strip("()")
        patterns = inner.split(",")
        assert len(patterns) <= 4
        assert all(p.startswith("content.ilike.*") for p in patterns)

    def test_no_unified_feed_text_scope_for_any_source_type(self) -> None:
        """S2: NO built request ever carries an ilike against unified_feed,
        for every source_type value including unscoped searches."""
        for source_type in (None, "workflow", "discord", "distillation"):
            seen: list[str] = []
            filters = {"source_type": source_type} if source_type else None
            with patch(
                "urllib.request.urlopen",
                side_effect=_capture_urlopen(seen, _json_response([])),
            ):
                hivemind_search(_REPRESENTATIVE_QUERY, filters=filters)
            for url in seen:
                if "/unified_feed" in url:
                    assert "ilike" not in url, (source_type, url)
                    assert "or=(" not in url, (source_type, url)
            # Free-text searches never even reach unified_feed.
            if source_type != "distillation":
                assert all("/unified_feed" not in u for u in seen), seen
            else:
                assert seen == []  # no non-text criteria -> scope skipped

    def test_default_page_limit_is_small(self) -> None:
        """S4: the default page size stays small (<=5); the bounded candidate
        pool is a separate internal fetch bound."""
        assert _HIVEMIND_TOOL_DEFAULT_LIMIT == 5
        assert _HIVEMIND_TOOL_DEFAULT_LIMIT <= 5
        assert _HIVEMIND_TOOL_DEFAULT_TIMEOUT >= 10.0
        # Pool is a fixed internal bound, independent of the page size.
        assert isinstance(_SCOPE_FETCH_LIMIT, int) and 0 < _SCOPE_FETCH_LIMIT <= 100

    def test_default_call_returns_at_most_five_hits(self) -> None:
        rows = [
            _message_row(i, f"wan animate hit {i}", "2026-08-01T00:00:00Z")
            for i in range(1, 9)
        ]
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen([], _json_response(rows)),
        ):
            result = hivemind_search(_REPRESENTATIVE_QUERY)
        assert result.status is ToolStatus.OK
        assert result.result["count"] <= 5

    def test_scopes_map_every_text_tier_to_message_feed_only(self) -> None:
        """Structural lock on the scope table: every tier's text surface is
        message_feed; unified_feed appears only as the distillation tier."""
        for tiers in _SOURCE_TYPE_SCOPES.values():
            for table, _kind in tiers:
                assert table in ("message_feed", "unified_feed")
        assert set(_SOURCE_TYPE_SCOPES["workflow"]) == {("message_feed", "message")}
        assert set(_SOURCE_TYPE_SCOPES["discord"]) == {("message_feed", "message")}


# ── 2. Distillation retrieval without text-search ───────────────────────────


class TestDistillationNonTextRetrieval:
    def test_distillation_by_id_is_a_lookup_not_a_search(self) -> None:
        """S3: hivemind_get resolves a distillation evidence id by its natural
        id column — a point lookup, never an ilike text query."""
        seen: list[str] = []
        row = {
            "item_id": 7,
            "kind": "distillation",
            "title": "Wan Animate roundup",
            "body": "curated answer",
            "created_at": "2026-08-03T00:00:00Z",
            "metadata": {"status": "approved", "confidence": 0.9},
        }
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([row])),
        ):
            result = hivemind_get("hivemind:unified_feed:7")
        assert result.status is ToolStatus.OK
        assert len(seen) == 1
        url = seen[0]
        assert "/unified_feed?" in url
        assert "item_id=eq.7" in url
        assert "ilike" not in url
        assert "or=(" not in url

    def test_distillation_structured_scope_carries_no_text_predicate(self) -> None:
        """The only way search touches unified_feed is structured filters;
        the built request contains kind + containment, zero wildcards."""
        seen: list[str] = []
        with patch(
            "urllib.request.urlopen",
            side_effect=_capture_urlopen(seen, _json_response([])),
        ):
            result = hivemind_search(
                _REPRESENTATIVE_QUERY,
                filters={"source_type": "distillation", "has_workflow": True},
            )
        assert result.status is ToolStatus.NO_RESULTS
        assert len(seen) == 1
        url = seen[0]
        assert "kind=eq.distillation" in url
        assert 'metadata=cs.{"has_workflow":true}' in url
        assert "ilike" not in url


# ── 3. Quota / statement-timeout resilience kept ────────────────────────────


class TestResiliencePathKept:
    def test_429_retry_after_circuit_still_opens(self, tmp_path: Any) -> None:
        """S5: a 429 with Retry-After types RATE_LIMITED and opens the shared
        cooldown circuit that short-circuits the next call."""
        calls = {"n": 0}

        def _boom(req: Any, *args: Any, **kwargs: Any) -> Any:
            calls["n"] += 1
            raise urllib.error.HTTPError(
                req.full_url,
                429,
                "Too Many Requests",
                {"Retry-After": "5"},
                io.BytesIO(b"{}"),
            )

        with patch("urllib.request.urlopen", side_effect=_boom):
            first = hivemind_search(_REPRESENTATIVE_QUERY, cache_root=tmp_path)
        assert first.status is ToolStatus.RATE_LIMITED
        assert first.retry_after_seconds == 5.0

        def _no_network(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("circuit must block network after 429")

        with patch("urllib.request.urlopen", side_effect=_no_network):
            second = hivemind_search(_REPRESENTATIVE_QUERY, cache_root=tmp_path)
        assert second.status is ToolStatus.RATE_LIMITED
        assert calls["n"] == 1

    def test_persistent_57014_degrades_then_types_soft_miss(self) -> None:
        """S5: persistent SQLSTATE 57014 gets exactly one degraded retry
        (prefix patterns, no leading wildcard) and remains a typed soft miss,
        never a hard failure."""
        calls: list[str] = []

        def _persistent(req: Any, *args: Any, **kwargs: Any) -> Any:
            calls.append(unquote_plus(req.full_url))
            raise urllib.error.HTTPError(
                req.full_url,
                500,
                "statement timeout",
                {},
                io.BytesIO(
                    b'{"code":"57014","message":"canceling statement due to statement timeout"}'
                ),
            )

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch("urllib.request.urlopen", side_effect=_persistent):
            result = hivemind_search(_REPRESENTATIVE_QUERY)
        assert result.status is ToolStatus.UNAVAILABLE
        assert result.diagnostics[0].code == "hivemind_statement_timeout"
        # two fat attempts + exactly one degraded attempt
        assert len(calls) == 3
        degraded = [u for u in calls if "ilike." in u and "ilike.*" not in u]
        assert len(degraded) == 1
        # Even the degraded retry stays on message_feed with content patterns.
        for url in calls:
            assert "/message_feed?" in url
            assert "title.ilike" not in url and "body.ilike" not in url

    def test_57014_recovery_on_degraded_query_returns_hits(self) -> None:
        """The degrade path ends in OK hits when the prefix query succeeds."""
        calls: list[str] = []

        def _fat_then_degraded(req: Any, *args: Any, **kwargs: Any) -> Any:
            url = unquote_plus(req.full_url)
            calls.append(url)
            if "ilike.*" in url:
                raise urllib.error.HTTPError(
                    req.full_url,
                    500,
                    "statement timeout",
                    {},
                    io.BytesIO(b'{"code":"57014"}'),
                )
            return _json_response(
                [_message_row(3, "wan animate degraded hit", "2026-08-02T00:00:00Z")]
            )

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch("urllib.request.urlopen", side_effect=_fat_then_degraded):
            result = hivemind_search(_REPRESENTATIVE_QUERY)
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 1
        assert result.evidence_ids == ("hivemind:message_feed:3",)
        assert any("content.ilike." in u and "ilike.*" not in u for u in calls)


# ── 4. LIVE regression (directive-required, env-gated) ──────────────────────


def _endpoint_reachable() -> str | None:
    """Return a skip reason when the public endpoint cannot be reached."""
    probe = (
        f"{_HIVEMIND_ROOT}/message_feed?select=message_id&limit=1"
        "&or=(content.ilike.*wan*)"
    )
    req = urllib.request.Request(probe, headers={"apikey": _anon_key()})
    try:
        with urllib.request.urlopen(req, timeout=5.0):
            return None
    except urllib.error.HTTPError:
        # Reachable but refused (quota/rate): live shape timing would flake.
        return "hivemind endpoint refused the probe request"
    except Exception:  # noqa: BLE001 - any transport failure means unreachable
        return "hivemind endpoint unreachable"


def _anon_key() -> str:
    from vibecomfy.executor.hivemind_clients import _DEFAULT_HIVEMIND_KEY

    return _DEFAULT_HIVEMIND_KEY


@pytest.mark.skipif(
    os.environ.get("HIVEMIND_REGRESSION_LIVE") != "1",
    reason="live regression gated: set HIVEMIND_REGRESSION_LIVE=1",
)
def test_live_multi_token_query_under_two_seconds_with_hits() -> None:
    """Directive-required live check: the representative multi-token query
    built by the new lean construction completes <2s WITH hits."""
    reason = _endpoint_reachable()
    if reason:
        pytest.skip(reason)

    from vibecomfy.executor.hivemind_clients import _DEFAULT_HIVEMIND_KEY  # noqa: F401

    started = time.monotonic()
    result = hivemind_search(_REPRESENTATIVE_QUERY, timeout=_HIVEMIND_TOOL_DEFAULT_TIMEOUT)
    elapsed = time.monotonic() - started

    assert result.status is ToolStatus.OK, (
        f"expected live hits, got status={result.status}, "
        f"diagnostics={[(d.code, d.message) for d in result.diagnostics]}"
    )
    hits = result.result["hits"]
    assert len(hits) > 0, "live regression requires at least one hit"
    assert elapsed < 2.0, f"lean query took {elapsed:.2f}s (must be <2s)"
    # And the hits really are message-feed rows resolved to evidence ids.
    for hit in hits:
        assert hit["evidence_id"].startswith("hivemind:message_feed:")
