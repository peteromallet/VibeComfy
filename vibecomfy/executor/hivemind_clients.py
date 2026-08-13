"""Hivemind transport clients for the executor research phase.

Shared PostgREST GET against the public Banodoco Supabase backend, plus two
clients:

* ``_default_hivemind_client`` — workflow-precedent search on
  ``external_resources?kind=eq.workflow`` (moved from ``research.py``;
  byte-compatible: same URL shape, phrase-then-token-OR, JSONB semantic
  filters).
* ``_default_hivemind_messages_client`` — community-messages search on
  ``unified_feed`` (distillations first, then ``kind=eq.message``) with a
  channel-scoped ``message_feed`` fallback when raw hits are thin.

Determinism here is transport-only: table selection, query formulation, and
display order for a **single** model-authored query string.  There is no term
expansion, no relevance scoring as a found-predicate, no evidence thresholds,
no latches, and no early-stop.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode

_HIVEMIND_REST_ROOT = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1"
_DEFAULT_HIVEMIND_URL = f"{_HIVEMIND_REST_ROOT}/external_resources"
_DEFAULT_HIVEMIND_KEY = "sb_publishable_O38oPBafrBoFrpi_rlWJvA_UJrulFsx"
_DEFAULT_EXTERNAL_LIMIT = 10

# A Hivemind client is any callable (query: str, timeout: float) → dict.
HivemindClient = Callable[[str, float], dict[str, Any]]

_QUERY_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+._-]*")

_SEARCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "build",
    "can",
    "create",
    "for",
    "generate",
    "graph",
    "happen",
    "happening",
    "how",
    "image",
    "in",
    "is",
    "make",
    "of",
    "on",
    "please",
    "show",
    "the",
    "this",
    "to",
    "video",
    "what",
    "whats",
    "with",
}

# Extra words to drop when degrading a Hivemind query after a statement-timeout.
# These are generic classifier/task words that widen the ILIKE search without
# improving recall and can push the Supabase/PostgREST query over the statement
# timeout (HTTP 500 with Postgres SQLSTATE 57014).
_HIVEMIND_FALLBACK_STOPWORDS = {
    "research",
    "goal",
    "find",
    "finding",
    "working",
    "work",
    "include",
    "including",
    "required",
    "requires",
    "custom",
    "nodes",
    "node",
    "checkpoint",
    "checkpoints",
    "model",
    "models",
    "loader",
    "loaders",
    "latent",
    "sampling",
    "setup",
    "setups",
    "frame",
    "frames",
    "generate",
    "generating",
    "generation",
    "needed",
    "using",
    "use",
    "used",
    # Action verbs that describe the edit intent but carry no workflow identity.
    "switch",
    "switching",
    "switches",
    "change",
    "changing",
    "convert",
    "converting",
    "make",
    "making",
    "apply",
    "applying",
    "set",
    "setting",
    "add",
    "adding",
    "remove",
    "removing",
    "replace",
    "replacing",
    # Generic domain words that are cheap for local search but expensive/noisy
    # for a degraded Hivemind keyword query.
    "workflow",
    "workflows",
    "comfy",
    "comfyui",
    "video",
    "videos",
    "image",
    "images",
    "audio",
}

_HIVEMIND_SEMANTIC_FAMILY_TERMS: dict[str, tuple[str, ...]] = {
    "wan": ("wan", "wanvideo", "wan2", "wan_2", "wan 2", "wan2_1", "wan2.1", "wan2_2", "wan2.2"),
    "ltx": ("ltx", "ltxv", "lightricks"),
    "hotshot": ("hotshot", "hotshotxl", "hotshot xl"),
    "animatediff": ("animatediff", "animate diff"),
    "sdxl": ("sdxl", "sd_xl", "sd xl", "stable diffusion xl"),
    "sd3": ("sd3", "stable diffusion 3"),
    "flux": ("flux", "flux1", "flux.1"),
    "qwen": ("qwen",),
    "hunyuan": ("hunyuan", "hyvideo", "hunyuanvideo"),
    "cogvideo": ("cogvideo", "cog video"),
}

_HIVEMIND_SEMANTIC_TASK_TERMS: dict[str, tuple[str, ...]] = {
    "image_to_video": ("image_to_video", "image-to-video", "image to video", "img2vid", "i2v"),
    "text_to_video": ("text_to_video", "text-to-video", "text to video", "txt2vid", "t2v"),
    "video_to_video": ("video_to_video", "video-to-video", "video to video", "vid2vid", "v2v"),
    "audio_to_video": ("audio_to_video", "audio-to-video", "audio to video"),
    "image_to_image": ("image_to_image", "image-to-image", "image to image", "img2img", "i2i"),
    "text_to_image": ("text_to_image", "text-to-image", "text to image", "txt2img", "t2i"),
    "controlnet": ("controlnet", "control net"),
    "compositing": ("composite", "compositing"),
    "inpainting": ("inpaint", "inpainting"),
    "upscale": ("upscale", "upscaler", "upscaling"),
}


class HivemindError(Exception):
    """Non-fatal Hivemind error — caught by the research runner and converted
    to a warning rather than propagating as an exception."""


def _parse_json_response(body: str) -> Any:
    return json.loads(body)


def _hivemind_get_table(
    table: str,
    params: Mapping[str, str],
    *,
    timeout: float,
) -> Any:
    """GET {REST_ROOT}/{table}?{urlencode(params)} with the publishable anon key.

    ``table`` is one of: external_resources, unified_feed, message_feed.
    Raises :class:`HivemindError` on HTTP / timeout / invalid JSON. Never
    logs the key.
    """
    url = f"{_HIVEMIND_REST_ROOT}/{table}?{urlencode(dict(params))}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "apikey": _DEFAULT_HIVEMIND_KEY,
            "Authorization": f"Bearer {_DEFAULT_HIVEMIND_KEY}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return _parse_json_response(body)
    except urllib.error.HTTPError as exc:
        body = exc.read(800).decode("utf-8", errors="replace")
        raise HivemindError(
            f"Hivemind HTTP error {exc.code}: {exc.reason} ({body})"
        ) from exc
    except TimeoutError as exc:
        raise HivemindError(f"Hivemind request timed out after {timeout}s") from exc
    except urllib.error.URLError as exc:
        raise HivemindError(f"Hivemind HTTP error: {exc}") from exc
    except ValueError as exc:
        raise HivemindError(f"Hivemind returned invalid JSON: {exc}") from exc


def _query_tokens(query: str) -> list[str]:
    return [m.group(0) for m in _QUERY_TOKEN_RE.finditer(query)]


def _dedupe_hivemind_rows(rows: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("id") or f"{row.get('source')}:{row.get('external_id')}:{row.get('title')}")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _hivemind_search_terms(query: str, *, max_terms: int = 8) -> list[str]:
    """Return Hivemind-oriented search terms for *query*.

    Drops generic domain words (``video``, ``generation``, ``workflow``,
    ``comfyui``) in addition to common stopwords so the ``ilike`` query focuses
    on distinctive tokens such as ``Hotshot``, ``Wan``, ``LTX`` or ``VACE``.
    If nothing specific remains, fall back to the raw tokens so the query still
    returns results for very generic questions.
    """
    raw_tokens = _query_tokens(query)
    if not raw_tokens:
        return []
    stop = _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS
    tokens = [t for t in raw_tokens if t.casefold() not in stop]
    # Pure numbers like ``16`` are almost never distinctive enough to narrow
    # Hivemind results; they tend to match many frame-count widgets and drown
    # out the real named target (e.g. ``Hotshot``).
    tokens = [t for t in tokens if not t.isdigit()]
    if not tokens:
        tokens = [t for t in raw_tokens if not t.isdigit()]
    if not tokens:
        tokens = raw_tokens

    terms: list[str] = []
    for size in (3, 2):
        for i in range(0, max(0, len(tokens) - size + 1)):
            terms.append(" ".join(tokens[i : i + size]))
    terms.extend(tokens)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = term.casefold()
        if key not in seen:
            deduped.append(term)
            seen.add(key)
        if len(deduped) >= max_terms:
            break
    return deduped


def _hivemind_ilike_query(search_terms: list[str]) -> str | None:
    """Build a PostgREST ``ilike`` OR query string for title/body search.

    Each term becomes ``title.ilike.*<term>*`` and ``body.ilike.*<term>*``;
    all patterns are ORed together.  Terms are sanitized to alphanumerics plus
    a few safe punctuation characters to avoid breaking the PostgREST syntax.
    """
    patterns: list[str] = []
    seen: set[str] = set()
    for term in search_terms:
        for raw in term.split():
            token = re.sub(r"[^a-zA-Z0-9_-]", "", raw)
            if not token:
                continue
            key = token.casefold()
            if key in seen:
                continue
            seen.add(key)
            patterns.append(f"title.ilike.*{token}*")
            patterns.append(f"body.ilike.*{token}*")
    if not patterns:
        return None
    return "(" + ",".join(patterns[:16]) + ")"


def _hivemind_phrase_ilike_query(query: str) -> str | None:
    """Build a bounded high-precision title/body phrase query.

    The broad Hivemind query deliberately ORs individual tokens for recall.
    Since PostgREST limits that result set before Python can rank it, first
    fetching a multi-token phrase prevents a highly specific title from being
    crowded out by rows that match only one common token.
    """
    tokens = [
        token
        for token in _query_tokens(query)
        if token.casefold() not in _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS
        and not token.isdigit()
    ]
    if len(tokens) < 2:
        return None
    phrase = " ".join(tokens[:8])
    return f"(title.ilike.*{phrase}*,body.ilike.*{phrase}*)"


def _hivemind_semantic_filters(query: str) -> list[dict[str, Any]]:
    """Return JSONB containment filters for recognizable workflow semantics."""
    text = query.casefold()
    filters: list[dict[str, Any]] = []
    for family, aliases in _HIVEMIND_SEMANTIC_FAMILY_TERMS.items():
        if any(_semantic_alias_matches(text, alias) for alias in aliases):
            filters.append({"workflow_semantics": {"model_families": [family]}})
    for task, aliases in _HIVEMIND_SEMANTIC_TASK_TERMS.items():
        if any(_semantic_alias_matches(text, alias) for alias in aliases):
            filters.append({"workflow_semantics": {"task_type": task}})
    return filters[:6]


def _semantic_alias_matches(text: str, alias: str) -> bool:
    alias_low = alias.casefold()
    if re.search(r"[^a-z0-9]", alias_low):
        return alias_low in text
    return re.search(rf"(?<![a-z0-9]){re.escape(alias_low)}(?![a-z0-9])", text) is not None


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _workflow_semantics(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    semantics = metadata.get("workflow_semantics")
    return semantics if isinstance(semantics, dict) else {}


def _workflow_semantics_text(item: dict[str, Any]) -> str:
    semantics = _workflow_semantics(item)
    values: list[str] = []
    for key in ("media_type", "task_type"):
        value = semantics.get(key)
        if isinstance(value, str):
            values.append(value)
    for key in ("model_families", "searchable_aliases", "node_types", "custom_nodes", "models"):
        value = semantics.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item is not None)
    return " ".join(values)


def _coerce_tasks(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, tuple):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _excerpt(text: str, *, limit: int = 500) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _rank_hivemind_rows(rows: list[Any], query: str) -> list[dict[str, Any]]:
    # Score both multi-word phrases and individual tokens so that rows returned
    # by an OR-style full-text query still get credit for partial matches.
    # Use the same domain-stopword filtering as the Hivemind query builder so
    # intent words like ``switch`` do not outrank the actual named target.
    phrase_terms = _hivemind_search_terms(query, max_terms=12)
    token_terms = [
        t for t in _query_tokens(query)
        if t.casefold() not in _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS
        and len(t) > 1
    ]
    query_terms = list(dict.fromkeys(phrase_terms + token_terms))

    # Pre-compute how many rows each term matches so rare, specific terms
    # (e.g. ``hotshot``) outweigh common domain words (``video``,
    # ``generation``).
    term_doc_counts: dict[str, int] = {}
    row_haystacks: list[tuple[int, str, str, dict[str, Any]]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        title = _first_text(row, "title", "name", "class_type")
        body = _first_text(row, "body", "description", "content", "text")
        haystack = f"{title}\n{body}\n{_workflow_semantics_text(row)}".casefold()
        row_haystacks.append((index, title, haystack, row))
        for term in query_terms:
            needle = term.casefold()
            if needle and needle in haystack:
                term_doc_counts[needle] = term_doc_counts.get(needle, 0) + 1

    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, title, haystack, row in row_haystacks:
        score = 0
        reasons: list[str] = []
        if row.get("kind") == "workflow":
            score += 25
            reasons.append("hivemind:workflow resource")
        semantics = _workflow_semantics(row)
        gates = semantics.get("promotion_gates") if isinstance(semantics.get("promotion_gates"), dict) else {}
        if gates.get("parseable_workflow") is True:
            score += 40
            reasons.append("hivemind:parseable workflow")
        if gates.get("has_rich_nodes") is True:
            score += 30
            reasons.append("hivemind:rich nodes available")
        if semantics.get("task_type") in _HIVEMIND_SEMANTIC_TASK_TERMS:
            score += 10
        seen_reasons: set[str] = set()
        url = str(row.get("url") or row.get("source_url") or "").casefold()
        filename = url.rsplit("/", 1)[-1] if "/" in url else url
        for term in query_terms:
            needle = term.casefold()
            if not needle or needle not in haystack:
                continue
            is_phrase = " " in term
            in_title = needle in title.casefold()
            in_url = needle in url
            in_filename = needle in filename
            doc_count = term_doc_counts.get(needle, 1)
            # Rare terms score far more than common domain words.
            base_score = 300 if is_phrase else 200
            term_score = max(60, base_score // doc_count)
            if in_title:
                term_score += 100
            if in_url:
                term_score += 150
            if in_filename:
                term_score += 100
            score += term_score
            if in_title:
                location = "title"
            elif in_filename:
                location = "filename"
            elif in_url:
                location = "url"
            else:
                location = "body"
            reason = f"hivemind:{location} matched {term!r}"
            if reason not in seen_reasons:
                seen_reasons.add(reason)
                reasons.append(reason)
        if score <= 0:
            continue
        ranked = dict(row)
        ranked["score"] = max(int(row.get("score", 0) or 0), score)
        ranked["reasons"] = reasons or list(row.get("reasons", []) or [])
        scored.append((ranked["score"], -index, ranked))
    scored.sort(reverse=True)
    return [row for _, _, row in scored]


def _default_hivemind_client(query: str, timeout: float) -> dict[str, Any]:
    """Default direct-HTTP Hivemind client backed by Supabase/PostgREST.

    Searches the public ``external_resources`` table's ``title`` and ``body``
    columns using case-insensitive pattern matches (``ilike``), restricted to
    workflow resources.  ``external_resources`` is where the anonymous
    ``contribute-resource`` edge function writes VibeComfy external workflows;
    the old ``unified_feed`` table only indexes Discord chat messages, so
    workflow searches against it never returned results.

    The ``title`` and ``body`` columns in ``external_resources`` are plain text,
    not ``tsvector``, so Postgres full-text search (``fts``) matches nothing
    there.  We instead OR ``*term*`` ilike patterns across both columns.  With
    the small external-resources table and a tight ``limit`` this stays fast;
    it also avoids the leading-wildcard ``ilike`` statement timeouts that hit
    the much larger ``unified_feed`` table.

    Query handling balances precision and recall.  A bounded phrase query runs
    first for multi-token requests, then a broader token-OR query fills out the
    candidate pool.  This matters because PostgREST applies ``limit`` before
    local ranking: using only the broad query can omit an exact title from the
    returned page when a common token (for example ``Style``) has many matches.

    Raises :class:`HivemindError` on any HTTP-level or timeout failure so the
    caller can convert it to a warning.
    """
    terms = _hivemind_search_terms(query)
    semantic_filters = _hivemind_semantic_filters(query)
    if not terms and not semantic_filters:
        return {"results": []}

    def _search(search_terms: list[str]) -> dict[str, Any]:
        rows: list[Any] = []
        phrase_query = _hivemind_phrase_ilike_query(query)
        if phrase_query:
            params = {
                "select": "*",
                "or": phrase_query,
                "kind": "eq.workflow",
                "limit": str(_DEFAULT_EXTERNAL_LIMIT),
            }
            parsed = _hivemind_get_table("external_resources", params, timeout=timeout)
            if isinstance(parsed, dict):
                return parsed
            rows.extend(parsed if isinstance(parsed, list) else [])

        ilike_query = _hivemind_ilike_query(search_terms)
        if ilike_query:
            params = {
                "select": "*",
                "or": ilike_query,
                "kind": "eq.workflow",
                "limit": str(_DEFAULT_EXTERNAL_LIMIT * 3),
            }
            parsed = _hivemind_get_table("external_resources", params, timeout=timeout)
            if isinstance(parsed, dict):
                return parsed
            rows.extend(parsed if isinstance(parsed, list) else [])

        for semantic_filter in semantic_filters:
            params = {
                "select": "*",
                "kind": "eq.workflow",
                "metadata": f"cs.{json.dumps(semantic_filter, separators=(',', ':'))}",
                "limit": str(_DEFAULT_EXTERNAL_LIMIT * 2),
            }
            parsed = _hivemind_get_table("external_resources", params, timeout=timeout)
            rows.extend(parsed if isinstance(parsed, list) else [])

        return {"results": _rank_hivemind_rows(_dedupe_hivemind_rows(rows), query)[:_DEFAULT_EXTERNAL_LIMIT]}

    try:
        return _search(terms)
    except TimeoutError as exc:
        raise HivemindError(f"Hivemind request timed out after {timeout}s") from exc
    except urllib.error.URLError as exc:
        raise HivemindError(f"Hivemind HTTP error: {exc}") from exc
    except ValueError as exc:
        raise HivemindError(f"Hivemind returned invalid JSON: {exc}") from exc


# ── Messages research client ─────────────────────────────────────────────────
#
# Community-messages search is deliberately NOT the workflow client: it queries
# ``unified_feed`` (distillations first, then ``kind=eq.message``) and, when
# raw hits are thin, a channel-scoped ``message_feed``.  There is no FTS, no
# unfiltered ``limit=1000`` dump, no 3-gram expansion, and no
# ``external_resources`` message search.

_DAILY_SUMMARIES = ("daily_summaries",)

_CHANNEL_GROUPS: dict[str, tuple[str, ...]] = {
    "ltx": ("ltx_chatter", "ltx_resources", "ltx_gens", "ltx_training", "live_updates", "resources"),
    "wan": ("wan_chatter", "wan_comfyui", "wan_gens", "wan_resources", "live_updates", "resources"),
    "comfy": ("comfyui", "wan_comfyui", "ltx_chatter", "live_updates", "resources"),
    "minimax": ("minimax_h3_chatter", "ltx_chatter", "live_updates", "chatter", "art_sharing"),
    "training": ("training_control_loras", "ltx_training", "wan_training", "comfyui"),
    "general": ("chatter", "live_updates", "nsfw", "introductions", "art_sharing"),
}

_FAMILY_TO_GROUP = (
    (("ltx", "ltxv", "lightricks", "ltx 2.5", "ltx2.5"), "ltx"),
    (("wan", "wanvideo", "vace", "scail", "infinitetalk", "lightx2v"), "wan"),
    (("minimax", "minimax h3", "h3"), "minimax"),
    (("comfy", "comfyui", "kijai"), "comfy"),
)


def _channel_scope_for_query(query: str) -> tuple[str, ...]:
    """daily_summaries first, then matching topic groups, then general fallback.

    Never returns empty: at minimum (daily_summaries, chatter).
    Cap at 10 channel names so PostgREST ``in.()`` stays cheap.
    """
    text = query.casefold()
    channels: list[str] = ["daily_summaries"]
    matched_groups: list[str] = []
    for aliases, group in _FAMILY_TO_GROUP:
        if any(alias.casefold() in text for alias in aliases):
            matched_groups.append(group)
    if not matched_groups:
        matched_groups.append("general")
    seen: set[str] = set()
    for group in matched_groups:
        for channel in _CHANNEL_GROUPS[group]:
            if channel not in seen:
                seen.add(channel)
                channels.append(channel)
        if len(channels) >= 10:
            break
    return tuple(channels[:10])


def _distinctive_tokens(query: str) -> list[str]:
    """Tokens remaining after ``_SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS``.

    Uses the existing frozensets only (research.py:145-174 and :180+).
    Does **not** add question-word stopwords (people/think/about/new/do).
    Does **not** extract a family+version span (that would reintroduce
    expand_research_queries). Keep version-like tokens (contain a digit).
    Preserve original order. Cap at 8 tokens.
    """
    stop = _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS
    return [t for t in _query_tokens(query) if t.casefold() not in stop][:8]


def _hivemind_single_or_phrase_ilike(query: str) -> str | None:
    """Build ``or=(title.ilike.*Q*,body.ilike.*Q*)`` for this one query.

    ``Q`` is the distinctive tokens joined with a single space (one token
    if only one remains). Returns None only when no distinctive token remains.
    Never falls through to unscoped token-OR on unified_feed.
    Never emits a second variant. Never calls ``_hivemind_search_terms``.
    """
    tokens = _distinctive_tokens(query)
    if not tokens:
        return None
    q = " ".join(tokens)
    return f"(title.ilike.*{q}*,body.ilike.*{q}*)"


def _raw_message_hits_are_thin(rows: list[Mapping[str, Any]], query: str) -> bool:
    """True when A+B are not yet enough to skip message_feed.

    Operates on raw PostgREST dicts (``kind``, ``title``, ``body``/``content``,
    ``metadata.status``). Never reads ``source``. ``message_feed`` rows carry
    no ``kind`` column; they are messages by definition (``_hivemind_table``
    is stamped by the client).

    Not thin (skip Step C) when either:
      - any row has ``kind == "distillation"`` and
        ``(metadata or {}).get("status") == "approved"`` and a distinctive
        token appears in title/body, or
      - >= 3 rows with ``kind in {"message", "distillation"}`` whose
        title/body/content contain a distinctive token.
    Otherwise thin (run Step C). Empty rows are thin. Timeout is always thin.
    """
    distinctive = _distinctive_tokens(query)
    if not distinctive:
        return True

    matched = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        kind = str(row.get("kind") or "")
        if not kind and str(row.get("_hivemind_table") or "") == "message_feed":
            kind = "message"
        haystack = " ".join(
            str(row.get(key) or "") for key in ("title", "body", "content")
        ).casefold()
        has_token = any(t.casefold() in haystack for t in distinctive)
        if kind == "distillation":
            metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
            if str((metadata or {}).get("status") or "") == "approved" and has_token:
                return False
        if kind in {"message", "distillation"} and has_token:
            matched += 1
    return matched < 3


_MESSAGE_FEED_SELECT = "message_id,content,author_name,channel_name,channel_id,created_at"
_MESSAGE_FEED_LIMIT = 30
_UNIFIED_FEED_LIMIT = 20


def _stamp_rows(rows: list[Any], table: str, match_query: str) -> list[dict[str, Any]]:
    stamped: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out = dict(row)
        out["_hivemind_table"] = table
        out["_match_query"] = match_query
        stamped.append(out)
    return stamped


def _densest_topic_group(scope: tuple[str, ...]) -> tuple[str, ...]:
    """Pick the single topic group whose channels overlap most with *scope*.

    Still includes ``live_updates`` for LTX-family queries because the
    ``ltx`` group definition embeds it.
    """
    scope_set = set(scope)
    best: tuple[str, ...] = ()
    best_count = -1
    for channels in _CHANNEL_GROUPS.values():
        overlap = tuple(c for c in channels if c in scope_set)
        if len(overlap) > best_count:
            best_count = len(overlap)
            best = overlap
    return best


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _message_feed_with_recovery(
    scope: tuple[str, ...],
    *,
    timeout: float,
    content_ilike: str | None = None,
    token_or: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Channel-scoped ``message_feed`` GET with timeout recovery.

    On any :class:`HivemindError`: retry with only ``daily_summaries``, then
    with the single densest topic group (still including ``live_updates`` for
    LTX), then optionally narrowed to the last 90 days.  Remaining failure is
    converted to a warning entry (the client never raises to ``research()``).
    """
    def _fetch(channels: tuple[str, ...], extra: dict[str, str] | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {
            "select": _MESSAGE_FEED_SELECT,
            "channel_name": f"in.({','.join(channels)})",
            "order": "created_at.desc",
            "limit": str(_MESSAGE_FEED_LIMIT),
        }
        if content_ilike:
            params["content"] = content_ilike
        if token_or:
            params["or"] = token_or
        if extra:
            params.update(extra)
        parsed = _hivemind_get_table("message_feed", params, timeout=timeout)
        return parsed if isinstance(parsed, list) else []

    warnings: list[str] = []
    try:
        return _fetch(scope), warnings
    except HivemindError as exc:
        warnings.append(str(exc))
    try:
        return _fetch(_DAILY_SUMMARIES), warnings
    except HivemindError as exc:
        warnings.append(str(exc))
    dense = _densest_topic_group(scope)
    if dense:
        try:
            return _fetch(dense), warnings
        except HivemindError as exc:
            warnings.append(str(exc))
        try:
            return _fetch(dense, {"created_at": f"gte.{_iso_days_ago(90)}"}), warnings
        except HivemindError as exc:
            warnings.append(str(exc))
    return [], warnings


def _default_hivemind_messages_client(query: str, timeout: float) -> dict[str, Any]:
    """Search Banodoco community knowledge.

    Channel scope is computed inside via ``_channel_scope_for_query(query)``
    (includes ``live_updates`` for LTX / general / minimax groups). Returns
    ``{"results": [unified-shaped dicts...], "warnings": [...]}``.
    Each result keeps raw unified_feed / message_feed columns plus
    ``_hivemind_table`` and ``_match_query`` for audit.

    Step A: ``unified_feed`` distillations, Step B: ``unified_feed``
    ``kind=eq.message`` (same ilike), Step C: channel-scoped ``message_feed``
    when ``_raw_message_hits_are_thin``, Step D: channel-scoped individual
    token-OR fill when A+B+C are still thin or timed out. One query string,
    no expansion, no early-stop.
    """
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []

    tokens = _distinctive_tokens(query)
    if not tokens:
        return {"results": [], "warnings": warnings}
    q = " ".join(tokens)
    phrase_or = _hivemind_single_or_phrase_ilike(query)

    def _unified_feed(kind: str) -> list[dict[str, Any]]:
        params: dict[str, str] = {
            "select": "*",
            "kind": f"eq.{kind}",
            "limit": str(_UNIFIED_FEED_LIMIT),
        }
        if kind == "message":
            params["order"] = "created_at.desc"
        if phrase_or:
            params["or"] = phrase_or
        parsed = _hivemind_get_table("unified_feed", params, timeout=timeout)
        return parsed if isinstance(parsed, list) else []

    try:
        rows.extend(_stamp_rows(_unified_feed("distillation"), "unified_feed", q))
        rows.extend(_stamp_rows(_unified_feed("message"), "unified_feed", q))
        thin = _raw_message_hits_are_thin(rows, query)
    except HivemindError as exc:
        warnings.append(str(exc))
        thin = True

    if thin:
        channel_scope = _channel_scope_for_query(query)
        c_rows, c_warnings = _message_feed_with_recovery(
            channel_scope,
            timeout=timeout,
            content_ilike=f"ilike.*{q}*",
        )
        rows.extend(_stamp_rows(c_rows, "message_feed", q))
        warnings.extend(c_warnings)
        if _raw_message_hits_are_thin(rows, query):
            token_or = "(" + ",".join(f"content.ilike.*{t}*" for t in tokens) + ")"
            d_rows, d_warnings = _message_feed_with_recovery(
                channel_scope,
                timeout=timeout,
                token_or=token_or,
            )
            rows.extend(_stamp_rows(d_rows, "message_feed", " ".join(tokens)))
            warnings.extend(d_warnings)

    return {"results": rows, "warnings": warnings}


# ── Messages runner and display (normalize-only) ─────────────────────────────


def _hivemind_item_id(row: Mapping[str, Any]) -> str:
    raw = row.get("item_id", row.get("message_id", row.get("id")))
    return "" if raw is None else str(raw)


def _message_dedupe_key(row: Mapping[str, Any]) -> str:
    kind = str(row.get("kind") or "")
    item_id = _hivemind_item_id(row)
    if kind and item_id:
        return f"{kind}:{item_id}"
    return str(row.get("url") or f"{row.get('author')}:{row.get('body', '')[:80]}")


def _normalize_hivemind_message_source(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a unified_feed / message_feed row to the canonical source shape.

    Never fetches URLs. ``source`` is ``hivemind_message`` or
    ``hivemind_distillation``; item ids are strings (Discord snowflakes lose
    precision as JSON numbers above 2^53).
    """
    kind = item.get("kind") or "message"
    if kind != "distillation" and item.get("_hivemind_table") == "message_feed":
        kind = "message"
    title = _first_text(item, "title", "class_type")
    body = _first_text(item, "body", "content", "description", "text")
    if not title and body:
        title = _excerpt(body, limit=80)
    channel = (
        item.get("context")
        or item.get("channel_name")
        or item.get("channel")
        or ""
    )
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    source_kind = (
        "hivemind_distillation" if kind == "distillation" else "hivemind_message"
    )
    return {
        "class_type": title,
        "title": title,
        "score": item.get("score", 0),  # unused as a found-predicate
        "reasons": _coerce_tasks(item.get("reasons", [])),
        "source": source_kind,
        "kind": kind,
        "pack": channel or "banodoco-discord",
        "description": _excerpt(body),
        "tasks": [],
        "path": None,
        "hivemind_id": _hivemind_item_id(item),
        "url": _first_text(item, "url", "source_url", "permalink"),
        "author": _first_text(item, "author", "author_name"),
        "channel": channel if kind != "distillation" else "",
        "created_at": item.get("created_at"),
        "distillation_status": metadata.get("status"),
        "confidence": metadata.get("confidence"),
        "node_types": None,
        "workflow_schema": None,
    }


def _message_display_order(
    sources: tuple[dict[str, Any], ...],
    *,
    cap: int = 12,
) -> tuple[dict[str, Any], ...]:
    """Display order: approved distillations → pending → recency. Cap at 12.

    This is a display bound, not a found-predicate: rows are never dropped on
    an IDF / ``score <= 0`` bar. A low-IDF on-topic row stays visible.
    """
    def _bucket(source: Mapping[str, Any]) -> int:
        if source.get("source") == "hivemind_distillation":
            status = str(source.get("distillation_status") or "").casefold()
            return 0 if status == "approved" else 1
        return 2

    ordered = sorted(
        sources,
        key=lambda s: str(s.get("created_at") or ""),
        reverse=True,
    )
    ordered.sort(key=_bucket)  # stable: recency preserved inside each bucket
    return tuple(ordered[:cap])


def _run_hivemind_messages_research(
    query: str,
    *,
    client: HivemindClient,
    timeout: float,
) -> tuple[dict[str, Any], ...]:
    """Call ``client(query, timeout)`` and normalize only.

    No ``_hivemind_workflow_url_candidates``. No
    ``_fetch_external_workflow_json_source`` (Discord attachment URLs are
    never treated as workflow JSON). Channel scope lives inside the default
    client, not on this runner. One call, one query string. Rows are deduped
    by string id, ordered (approved → pending → recency), and capped at 12 for
    presentation.
    """
    response = client(query, timeout)
    items = response.get("results", response.get("sources", []))
    if not isinstance(items, list):
        return ()

    raw = [item for item in items if isinstance(item, dict)]
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        key = _message_dedupe_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    normalized = tuple(_normalize_hivemind_message_source(item) for item in deduped)
    return _message_display_order(normalized)


def format_community_summary(
    sources: tuple[Mapping[str, Any], ...],
    *,
    query: str = "",
) -> str:
    """Extractive display paragraph. No polarity, no strength, no stop_reason.

    Empty message/distillation sources →
      'No community discussion found for "<query>".'
    Otherwise list up to 6 items, cap ~800 chars:
      - hivemind_message: '{author} in #{channel}: {excerpt}'
      - hivemind_distillation: '{title} ({status}/{confidence}): {excerpt}'
    Never invents quotes.
    """
    community = [
        src
        for src in sources
        if isinstance(src, Mapping)
        and str(src.get("source") or "") in {"hivemind_message", "hivemind_distillation"}
    ]
    if not community:
        return f'No community discussion found for "{query}".'

    lines: list[str] = []
    for src in community[:6]:
        title = str(src.get("title") or src.get("class_type") or "").strip()
        excerpt = str(src.get("description") or "").strip()
        if src.get("source") == "hivemind_distillation":
            status = str(src.get("distillation_status") or "pending").strip() or "pending"
            confidence = src.get("confidence")
            conf = f"/{confidence}" if confidence not in (None, "") else ""
            line = f"{title} ({status}{conf})"
            if excerpt:
                line += f": {excerpt}"
            lines.append(line)
        else:
            author = str(src.get("author") or "").strip()
            channel = str(src.get("channel") or "").strip()
            if author and channel:
                prefix = f"{author} in #{channel}"
            elif author:
                prefix = author
            elif channel:
                prefix = f"#{channel}"
            else:
                prefix = ""
            lines.append(f"{prefix}: {excerpt}" if prefix and excerpt else (prefix or excerpt))

    text = "\n".join(lines)
    if len(text) > 800:
        text = text[:797].rstrip() + "…"
    return text
