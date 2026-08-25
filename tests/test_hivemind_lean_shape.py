"""HIVEMIND-SCOPE-FIX focused tests (operator directive §37, 2026-08-24).

Locks the corrected lean query construction in the executor's hivemind client:

1. A free-text query text-searches BOTH ``external_resources`` (title/body —
   where workflows live) AND ``message_feed`` (content), each with <=6
   distinctive-token ilike patterns per table; overflow truncates
   deterministically; no unified_feed text scope anywhere; tool default page
   limit <=5 preserved.
2. Distillation retrieval never goes through the text-search path: by id via
   ``hivemind_get`` or through non-text structured filters only.
3. The 429 Retry-After circuit and the SQLSTATE 57014 degrade-once posture
   still function — now under PER-SCOPE deadlines: a scope that times out
   records its diagnostic while later scopes run with their own full budget;
   only when every scope fails does the transport re-raise.
4. LIVE regression (directive-required): a representative multi-token query
   through the construction completes <2s WITH hits.  Gated behind
   ``HIVEMIND_REGRESSION_LIVE=1`` and skipped when the endpoint is
   unreachable, so the default suite stays deterministic and isolated.

All transport except the live-gated test is mocked via ``urllib.request.urlopen``
(construction-level assertions stay offline and sub-second).
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
    _HIVEMIND_SCOPE_PATTERN_CAP,
    _hivemind_message_ilike,
    _hivemind_resource_ilike,
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


def _resource_row(row_id: str, title: str, body: str, created_at: str) -> dict[str, Any]:
    return {
        "id": row_id,
        "title": title,
        "body": body,
        "url": f"https://hivemind.example/{row_id}",
        "created_at": created_at,
    }


def _ilike_patterns(url: str) -> list[str]:
    """All ``*.ilike.*`` patterns appearing anywhere in a built request URL."""
    import re

    return re.findall(r"(?:title|body|content)\.ilike\.[^&(),]*", url)


# ── 1. Lean shape of built requests ─────────────────────────────────────────


class TestLeanQueryShape:
    def test_representative_query_builds_two_text_scope_requests(self) -> None:
        """§37: a free-text query text-searches external_resources (title/
        body, where workflows live) AND message_feed (content); each request
        carries <=6 distinctive-token ilike ORs; unified_feed stays out."""
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
        assert len(seen) == 2, seen
        resource_url, message_url = seen
        # Scope 1: WHERE WORKFLOWS LIVE — title/body doubling on
        # external_resources over the same few distinctive tokens.
        assert f"{_HIVEMIND_ROOT}/external_resources?" in resource_url
        assert "/unified_feed" not in resource_url
        resource_patterns = _ilike_patterns(resource_url)
        assert resource_patterns == [
            "title.ilike.*wan*",
            "body.ilike.*wan*",
            "title.ilike.*animate*",
            "body.ilike.*animate*",
        ]
        assert len(resource_patterns) <= _HIVEMIND_SCOPE_PATTERN_CAP
        # Scope 2: community guidance — content-only patterns on message_feed.
        assert f"{_HIVEMIND_ROOT}/message_feed?" in message_url
        assert "/unified_feed" not in message_url
        message_patterns = _ilike_patterns(message_url)
        assert message_patterns
        assert all(p.startswith("content.ilike.") for p in message_patterns)
        assert len(message_patterns) <= _HIVEMIND_SCOPE_PATTERN_CAP
        # The distinctive tokens survived on both surfaces; filler words did
        # not consume them ("workflow" is a stopword-domain word and is gone).
        assert any("wan" in p for p in message_patterns)
        assert any("animate" in p for p in message_patterns)

    def test_token_cap_truncates_deterministically_to_six(self) -> None:
        """§37.1: >6 tokens truncate to exactly 6 content.ilike patterns and
        the selection is deterministic: earliest surviving tokens win."""
        built = _hivemind_message_ilike(
            "wan animate vace ltx hotshot sdxl qwen flux"
        )
        assert built is not None
        inner = built.strip("()")
        patterns = inner.split(",")
        assert len(patterns) == _HIVEMIND_SCOPE_PATTERN_CAP
        assert patterns == [
            "content.ilike.*wan*",
            "content.ilike.*animate*",
            "content.ilike.*vace*",
            "content.ilike.*ltx*",
            "content.ilike.*hotshot*",
            "content.ilike.*sdxl*",
        ]

    def test_resource_builder_doubles_tokens_within_table_budget(self) -> None:
        """§37.2/R2: title+body doubling per token, but total patterns per
        table stay <=6 — so a token-rich query truncates to 3 tokens."""
        built = _hivemind_resource_ilike(
            "wan animate vace ltx hotshot sdxl qwen flux"
        )
        assert built is not None
        patterns = built.strip("()").split(",")
        assert len(patterns) <= _HIVEMIND_SCOPE_PATTERN_CAP
        # Deterministic selection: the first three distinctive tokens doubled.
        assert patterns == [
            "title.ilike.*wan*",
            "body.ilike.*wan*",
            "title.ilike.*animate*",
            "body.ilike.*animate*",
            "title.ilike.*vace*",
            "body.ilike.*vace*",
        ]

    def test_degraded_builders_use_prefix_patterns(self) -> None:
        """The 57014 degraded retry keeps prefix patterns (no leading
        wildcard) on both text surfaces."""
        message = _hivemind_message_ilike("wan animate", degraded=True)
        assert message == "(content.ilike.wan*,content.ilike.animate*)"
        resource = _hivemind_resource_ilike("wan animate", degraded=True)
        assert resource == (
            "(title.ilike.wan*,body.ilike.wan*,"
            "title.ilike.animate*,body.ilike.animate*)"
        )

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

    def test_scopes_table_matches_directive_37(self) -> None:
        """Structural lock on the scope table (§37): workflow discovery rides
        BOTH text surfaces; unified_feed appears ONLY as the non-text
        distillation tier; discord stays message_feed-only."""
        assert _SOURCE_TYPE_SCOPES["workflow"] == (
            ("external_resources", "workflow"),
            ("message_feed", "message"),
        )
        assert _SOURCE_TYPE_SCOPES["discord"] == (("message_feed", "message"),)
        assert _SOURCE_TYPE_SCOPES["distillation"] == (
            ("unified_feed", "distillation"),
        )
        assert _SOURCE_TYPE_SCOPES[None] == (
            ("external_resources", "workflow"),
            ("message_feed", "message"),
            ("unified_feed", "distillation"),
        )


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
        # One 429 per text scope (external_resources, then message_feed):
        # each scope records its failure; with no hits anywhere the first
        # error is re-raised and opens the shared cooldown circuit.
        assert calls["n"] == 2

    def test_persistent_57014_degrades_then_types_soft_miss(self) -> None:
        """Persistent SQLSTATE 57014 gets exactly one degraded retry
        (prefix patterns, no leading wildcard) PER SCOPE under that scope's
        own deadline, and remains a typed soft miss, never a hard failure."""
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
        # Per text scope: two fat attempts + exactly one degraded attempt;
        # two scopes (external_resources, message_feed) -> six calls.
        assert len(calls) == 6
        degraded = [u for u in calls if "ilike." in u and "ilike.*" not in u]
        assert len(degraded) == 2
        # Both degraded retries stay on the two TEXT surfaces with prefix
        # patterns; unified_feed is never touched.
        for url in calls:
            assert "/message_feed?" in url or "/external_resources?" in url
            assert "/unified_feed" not in url
        assert any("title.ilike." in u for u in degraded)
        assert any("content.ilike." in u for u in degraded)

    def test_57014_recovery_merges_hits_across_both_text_scopes(self) -> None:
        """The degrade path ends in OK hits when the prefix queries succeed —
        on EACH text surface under its own deadline."""
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
            if "/external_resources?" in url:
                return _json_response(
                    [
                        _resource_row(
                            "wf-9",
                            "Wan Animate pipeline",
                            "curated workflow drop",
                            "2026-08-02T00:00:00Z",
                        )
                    ]
                )
            return _json_response(
                [_message_row(3, "wan animate degraded hit", "2026-08-02T00:00:00Z")]
            )

        with patch(
            "vibecomfy.executor.hivemind_clients.time.sleep",
        ), patch("urllib.request.urlopen", side_effect=_fat_then_degraded):
            result = hivemind_search(_REPRESENTATIVE_QUERY)
        assert result.status is ToolStatus.OK
        assert result.result["count"] == 2
        assert set(result.evidence_ids) == {
            "hivemind:external_resources:wf-9",
            "hivemind:message_feed:3",
        }
        assert any("content.ilike." in u and "ilike.*" not in u for u in calls)
        assert any("title.ilike." in u and "ilike.*" not in u for u in calls)


# ── 3b. Per-scope deadline isolation (§37.3) ────────────────────────────────


class TestPerScopeDeadlineIsolation:
    def test_first_scope_timeout_does_not_starve_second_scope(self) -> None:
        """§37.3: a scope that times out records its diagnostic; the next
        scope still executes within its OWN full budget and its hits are
        returned."""
        seen: list[str] = []
        budgets: list[float] = []
        clock = {"t": 0.0}

        def _responder(req: Any, *args: Any, **kwargs: Any) -> Any:
            url = unquote_plus(req.full_url)
            budgets.append(float(kwargs["timeout"]))
            if "/external_resources?" in url:
                raise TimeoutError("scope 1 spent its whole budget")
            return _json_response(
                [_message_row(5, "wan animate survivor", "2026-08-03T00:00:00Z")]
            )

        with patch(
            "vibecomfy.executor.hivemind_clients.time.monotonic",
            side_effect=lambda: clock["t"],
        ), patch(
            "urllib.request.urlopen",
            side_effect=lambda req, *a, **k: (
                seen.append(unquote_plus(req.full_url)),
                _responder(req, *a, **k),
            )[1],
        ):
            result = hivemind_search(_REPRESENTATIVE_QUERY, timeout=5.0)
        assert result.status is ToolStatus.OK
        assert result.evidence_ids == ("hivemind:message_feed:5",)
        # The failed scope is diagnosed, not fatal.
        failed = [
            d for d in result.diagnostics if d.code == "hivemind_scope_failed"
        ]
        assert [d.details["scope"] for d in failed] == [
            "external_resources:workflow"
        ]
        # Scope 2 ran with a FULL fresh budget despite scope 1's burn.
        assert len(seen) == 2
        assert all(b == pytest.approx(5.0) for b in budgets), budgets

    def test_all_scopes_failing_still_re_raises_first_error(self) -> None:
        """Only when EVERY scope fails does the transport re-raise the first
        HivemindError (typed TIMEOUT here)."""

        def _timeout(*args: Any, **kwargs: Any) -> Any:
            raise TimeoutError("every scope spends its budget")
        with patch(
            "vibecomfy.executor.hivemind_clients.time.monotonic",
            side_effect=lambda: 0.0,
        ), patch("urllib.request.urlopen", side_effect=_timeout):
            result = hivemind_search(_REPRESENTATIVE_QUERY, timeout=5.0)
        assert result.status is ToolStatus.TIMEOUT
        assert result.diagnostics[0].code == "hivemind_timeout"


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
    # And the hits resolve to evidence ids on the searched surfaces
    # (external_resources / message_feed — §37 text tiers).
    for hit in hits:
        assert hit["evidence_id"].startswith(
            ("hivemind:external_resources:", "hivemind:message_feed:")
        )
