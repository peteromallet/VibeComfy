"""Hivemind transport for the executor research phase (A01).

Shared PostgREST GET against the public Banodoco Supabase backend, plus the
agent-tool search/get transport: table selection, PostgREST filter
translation, deterministic ordering and paging for one model-authored query
string.  There is no term expansion, no winner selection, no evidence
thresholds, no latches, and no early-stop.

Lean query shape (operator directive §37, HIVEMIND-SCOPE-FIX): free-text
search runs against ``external_resources`` (title/body — where workflows
live) and ``message_feed`` (content) with FEW distinctive tokens per table
(<=6 ilike patterns); each scope gets its OWN deadline so one slow scope
cannot starve the others.  ``unified_feed`` is never text-searched (its
UNION scan trips Postgres SQLSTATE 57014); distillations are reached by id
or through non-text structured filters.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Mapping
from urllib.parse import urlencode

# R2-B2: reuse the pack resolver's Retry-After parser (seconds or HTTP date)
# so rate-limit headers translate identically across the executor's HTTP tiers.
from vibecomfy.registry.pack_resolver import _parse_retry_after

_HIVEMIND_REST_ROOT = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1"
_DEFAULT_HIVEMIND_KEY = "sb_publishable_O38oPBafrBoFrpi_rlWJvA_UJrulFsx"

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

# REC-A: Postgres statement-timeout (SQLSTATE 57014) surfaces as HTTP 500 with
# a body like ``{"code":"57014",...,"message":"canceling statement due to
# statement timeout"}``.  These queries are valid — the backend just hit its
# per-statement time budget — so retry ONCE with a short backoff, then RC1
# tries one degraded query before typing the failure as a soft miss.  A
# persistent 57014 is still a soft miss
# (UNAVAILABLE / ``hivemind_statement_timeout``), never a hard error.
_HIVEMIND_STATEMENT_TIMEOUT_RETRIES = 1
_HIVEMIND_STATEMENT_TIMEOUT_BACKOFF_SECONDS = 0.5
_HIVEMIND_DEGRADED_LIMIT = 20

# REC-A: off-family demotion vocabulary for relevance ranking.  Beyond the
# semantic family terms above, recognize the model families that actually
# pollute video/audio/3D searches (MiniMax H3 workflows drowning LTX/SDXL
# questions in the live corpus) so wrong-family hits can be demoted when the
# query or the brief names a specific family.
_HIVEMIND_RANK_FAMILY_MARKERS: dict[str, tuple[str, ...]] = {
    "wan": ("wan", "wan2", "wanvideo", "wan_2"),
    "ltx": ("ltx", "ltxv", "lightricks", "ltx2"),
    "hotshot": ("hotshot", "hotshotxl"),
    "animatediff": ("animatediff",),
    "sdxl": ("sdxl", "sd_xl", "sd xl", "stable diffusion xl"),
    "sd3": ("sd3", "stable diffusion 3"),
    "flux": ("flux", "flux1", "flux.1"),
    "qwen": ("qwen",),
    "hunyuan": ("hunyuan", "hyvideo"),
    "cogvideo": ("cogvideo",),
    "minimax": ("minimax", "mini-max", "h3"),
    "kling": ("kling",),
    "veo": ("veo",),
    "sora": ("sora",),
    "runway": ("runway",),
    "moonvalley": ("moonvalley", "moon valley"),
    "pixverse": ("pixverse",),
    "krea": ("krea",),
    "acestep": ("acestep", "ace step"),
    "stable_audio": ("stable audio", "stableaudio"),
}


class HivemindError(Exception):
    """Non-fatal Hivemind error — caught by the research runner and converted
    to a warning rather than propagating as an exception.

    Transport classification rides on the exception so typed tool layers
    (``hivemind_tools``) can map failures without parsing messages:

    * ``reason`` — ``"http"`` (server responded with a bad status),
      ``"timeout"``, ``"unavailable"`` (connection / URL failure), or
      ``"invalid_json"`` (protocol failure).
    * ``status_code`` — HTTP status when ``reason == "http"``.
    * ``retry_after_seconds`` — parsed ``Retry-After`` header when the server
      sent one (rate limits).
    * ``statement_timeout`` — True when an HTTP 500 carried Postgres
      SQLSTATE 57014 (statement timeout) after the retry budget was spent;
      the tool layer maps this to a soft miss, never a hard error.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str | None = None,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
        statement_timeout: bool = False,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.statement_timeout = statement_timeout


def _parse_json_response(body: str) -> Any:
    return json.loads(body)


def _is_statement_timeout(body: str, status_code: int) -> bool:
    """True when an HTTP error body carries Postgres SQLSTATE 57014.

    PostgREST returns 500 for a statement timeout; the body embeds the
    Postgres error as ``{"code":"57014","message":"canceling statement due
    to statement timeout"}``.  Match on either the SQLSTATE or the message.
    """
    if status_code != 500:
        return False
    return '"57014"' in body or "canceling statement due to statement timeout" in body


def _hivemind_get_table(
    table: str,
    params: Mapping[str, str],
    *,
    timeout: float,
    deadline: float | None = None,
    statement_timeout_retries: int = _HIVEMIND_STATEMENT_TIMEOUT_RETRIES,
) -> Any:
    """GET {REST_ROOT}/{table}?{urlencode(params)} with the publishable anon key.

    ``table`` is one of: external_resources, unified_feed, message_feed.
    Raises :class:`HivemindError` on HTTP / timeout / invalid JSON. Never
    logs the key.

    ``timeout`` is the total operation wall-clock budget when ``deadline`` is
    omitted.  Search passes each scope its own fresh deadline (§37.3); the
    scope's fat attempt and its one 57014 degraded retry share that budget.

    REC-A resilience: a Postgres statement-timeout (HTTP 500 + SQLSTATE
    57014) is retried ONCE with a short backoff — the query is valid, the
    backend just hit its statement budget.  A persistent 57014 still raises,
    but flags ``statement_timeout=True`` so the tool layer types it as a
    soft miss rather than a hard failure.
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
    operation_deadline = (
        time.monotonic() + timeout if deadline is None else float(deadline)
    )
    attempts = 1 + max(0, int(statement_timeout_retries))
    for attempt in range(attempts):
        remaining = operation_deadline - time.monotonic()
        if remaining <= 0:
            raise HivemindError(
                f"Hivemind operation timed out after {timeout}s",
                reason="timeout",
            )
        try:
            with urllib.request.urlopen(req, timeout=min(timeout, remaining)) as resp:
                body = resp.read().decode("utf-8")
                return _parse_json_response(body)
        except urllib.error.HTTPError as exc:
            body = exc.read(800).decode("utf-8", errors="replace")
            retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
            statement_timeout = _is_statement_timeout(body, exc.code)
            if statement_timeout and attempt < statement_timeout_retries:
                remaining = operation_deadline - time.monotonic()
                if remaining <= 0:
                    raise HivemindError(
                        f"Hivemind operation timed out after {timeout}s",
                        reason="timeout",
                    ) from exc
                time.sleep(
                    min(_HIVEMIND_STATEMENT_TIMEOUT_BACKOFF_SECONDS, remaining)
                )
                continue
            raise HivemindError(
                f"Hivemind HTTP error {exc.code}: {exc.reason} ({body})",
                reason="http",
                status_code=exc.code,
                retry_after_seconds=retry_after,
                statement_timeout=statement_timeout,
            ) from exc
        except TimeoutError as exc:
            raise HivemindError(
                f"Hivemind request timed out after {timeout}s",
                reason="timeout",
            ) from exc
        except urllib.error.URLError as exc:
            raise HivemindError(
                f"Hivemind HTTP error: {exc}",
                reason="unavailable",
            ) from exc
        except ValueError as exc:
            raise HivemindError(
                f"Hivemind returned invalid JSON: {exc}",
                reason="invalid_json",
            ) from exc
    raise AssertionError("unreachable")  # pragma: no cover - retry loop bounded


def _query_tokens(query: str) -> list[str]:
    return [m.group(0) for m in _QUERY_TOKEN_RE.finditer(query)]


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


def _distinctive_tokens(query: str) -> list[str]:
    """Tokens remaining after ``_SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS``.

    Preserve original order; cap at 8 tokens.  Used as the relevance signal
    for deterministic ordering; the message-feed query builder caps its
    content patterns at the lean 2-4 distinctive tokens.
    """
    stop = _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS
    return [t for t in _query_tokens(query) if t.casefold() not in stop][:8]


# Question/conversation words that survive the generic stopword sets but
# never narrow a Hivemind search.  Dropped before the per-table token cap so
# question-shaped queries keep their distinctive tokens (e.g. "MiniMax H3")
# instead of "do people think about" (directive §37 lean shape).
_HIVEMIND_QUERY_FILLER_WORDS = frozenset({
    "do", "does", "did", "is", "are", "was", "were", "what", "which",
    "how", "why", "when", "where", "who", "whom", "people", "think",
    "about", "with", "without", "into", "from", "this", "that", "these",
    "those", "there", "their", "have", "has", "had", "will", "would",
    "should", "could", "can", "need", "want", "get", "got", "use",
    "used", "using", "make", "made", "work", "works", "working", "anyone",
    "someone", "please", "thanks", "help", "good", "better", "best",
    "new", "old", "know",
})


# Per-table ilike OR-pattern budget (§37.1): FEW DISTINCTIVE TOKENS — at most
# 6 patterns per table per request, enforced where the terms are distilled so
# overflow truncates deterministically to the query's most distinctive
# (earliest non-stopword) tokens.  On ``message_feed`` this is ONE SHARED
# budget across ALL text criteria in the request — free-text tokens, then
# family/capability alias translations, then node_class, deduplicated before
# emission — never independent per-group caps that sum past the table budget
# (HIVEMIND-SCOPE-FIX-REV).
_HIVEMIND_SCOPE_PATTERN_CAP = 6


def _hivemind_scope_tokens(query: str) -> list[str]:
    """Distinctive scope-query tokens, original order preserved.

    Generic stopwords, domain fallback words, and question/filler words are
    dropped first so the per-table caps keep the query's distinctive tokens.
    """
    stop = (
        _SEARCH_STOPWORDS
        | _HIVEMIND_FALLBACK_STOPWORDS
        | _HIVEMIND_QUERY_FILLER_WORDS
    )
    return [t for t in _query_tokens(query) if t.casefold() not in stop]


def _hivemind_message_or(tokens: list[str], *, degraded: bool = False) -> str | None:
    """Emit ONE ``content.ilike`` OR group from explicit tokens.

    Emission only: token selection, dedup, and the shared pattern budget
    live in :func:`_hivemind_scope_params` (HIVEMIND-SCOPE-FIX-REV).
    """
    patterns = [
        f"content.ilike.{token}*" if degraded else f"content.ilike.*{token}*"
        for token in tokens
    ]
    if not patterns:
        return None
    return "(" + ",".join(patterns) + ")"


def _hivemind_message_ilike(query: str, *, degraded: bool = False) -> str | None:
    """Build the lean per-token content query for ``message_feed``.

    §37.1: at most :data:`_HIVEMIND_SCOPE_PATTERN_CAP` distinctive tokens,
    each one ``content.ilike.*<token>*`` ORed together on the index-backed
    raw message table.  No phrase explosion; overflow truncates to the first
    (most distinctive) surviving tokens.  Degraded mode (57014 recovery)
    drops the leading wildcard so the planner can use a prefix scan.
    """
    return _hivemind_message_or(
        _hivemind_scope_tokens(query)[:_HIVEMIND_SCOPE_PATTERN_CAP],
        degraded=degraded,
    )


def _hivemind_resource_ilike(query: str, *, degraded: bool = False) -> str | None:
    """Build the title/body text query for ``external_resources``.

    WHERE WORKFLOWS LIVE (§37.2): each distinctive token doubles across the
    table's two searchable columns — ``title.ilike.*<t>*`` and
    ``body.ilike.*<t>*`` ORed together — so at most half the per-table
    pattern budget in tokens keeps total patterns <=6.  Degraded mode uses
    prefix patterns like the message builder.
    """
    tokens = _hivemind_scope_tokens(query)[: _HIVEMIND_SCOPE_PATTERN_CAP // 2]
    patterns: list[str] = []
    for token in tokens:
        for column in ("title", "body"):
            if degraded:
                patterns.append(f"{column}.ilike.{token}*")
            else:
                patterns.append(f"{column}.ilike.*{token}*")
    if not patterns:
        return None
    return "(" + ",".join(patterns) + ")"


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _workflow_semantics(item: Mapping[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
    semantics = metadata.get("workflow_semantics")
    return dict(semantics) if isinstance(semantics, Mapping) else {}


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


def _excerpt(text: str, *, limit: int = 500) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# REC-A: relevance demotion.  ``_query_model_family`` names the single model
# family the query points at (LTXV -> ltx, SDXL refiner -> sdxl); when exactly
# one family is named, ``_rank_hivemind_rows`` buckets rows: family-matching
# hits first, family-neutral rows second, wrong-family hits last.  This fixes
# the live failure where MiniMax H3 video workflows drowned LTX / SDXL queries
# because their generic "video/upscaling" tokens outranked the real match.

def _query_model_family(query: str) -> str | None:
    """Canonical family the query names, or None when it names none or many.

    Only a SINGLE named family triggers demotion — a "switch wan to ltx"
    question names two on-topic families and must not demote either.
    Markers match on word boundaries so ``wan`` is not triggered by
    ``want`` while ``wan2.1`` / ``wanvideo`` still hit their own markers.
    """
    haystack = query.casefold()
    named: list[str] = []
    for family, markers in _HIVEMIND_RANK_FAMILY_MARKERS.items():
        for marker in markers:
            pattern = re.compile(rf"\b{re.escape(marker.casefold())}\b")
            if pattern.search(haystack):
                named.append(family)
                break
    return named[0] if len(named) == 1 else None


def _row_model_families(row: Mapping[str, Any]) -> frozenset[str]:
    """Families a row itself names, with truthful signals taking precedence.

    The corpus labels MiniMax H3 workflows with ``model_families: ["ltx"]``
    (pipeline metadata/aliases are unreliable — the live failure shows a
    MiniMax workflow carrying ltx metadata).  The row TITLE is the most
    authoritative family identity; the body DESCRIPTION region (before the
    embedded workflow JSON) is the second signal.  Signals:

    1. title word-boundary marker matches;
    2. else body-prefix (first ~800 chars, description region) matches;
    3. else ``searchable_aliases`` substring matches;
    4. else ``workflow_semantics.model_families`` (weakest, known-mislabeled).

    A row naming no family yields an empty set (family-neutral).
    """

    def _match(text: str) -> frozenset[str]:
        haystack = text.casefold()
        found: set[str] = set()
        for family, markers in _HIVEMIND_RANK_FAMILY_MARKERS.items():
            for marker in markers:
                pattern = re.compile(rf"\b{re.escape(marker.casefold())}\b")
                if pattern.search(haystack):
                    found.add(family)
                    break
        return frozenset(found)

    title = _first_text(row, "title", "name", "class_type")
    if title:
        title_families = _match(title)
        if title_families:
            return title_families
    body = _first_text(row, "body", "content", "description", "text")
    if body:
        body_families = _match(body[:800])
        if body_families:
            return body_families
    semantics = _workflow_semantics(row)
    for alias in semantics.get("searchable_aliases") or ():
        if not isinstance(alias, str):
            continue
        alias_lower = alias.casefold()
        for family, markers in _HIVEMIND_RANK_FAMILY_MARKERS.items():
            if any(marker.casefold() in alias_lower for marker in markers):
                return frozenset({family})
    found: set[str] = set()
    for raw_family in semantics.get("model_families") or ():
        if not isinstance(raw_family, str):
            continue
        key = raw_family.casefold()
        for family, markers in _HIVEMIND_RANK_FAMILY_MARKERS.items():
            if key == family or any(marker.casefold() == key for marker in markers):
                found.add(family)
    return frozenset(found)


# Score offsets applied when the query names exactly one model family.
_HIVEMIND_FAMILY_MATCH_OFFSET = 10_000
_HIVEMIND_FAMILY_MISMATCH_OFFSET = -10_000


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
    query_family = _query_model_family(query)

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
        if query_family is not None:
            row_families = _row_model_families(row)
            if query_family in row_families:
                score += _HIVEMIND_FAMILY_MATCH_OFFSET
                reasons.append(f"hivemind:family matches query ({query_family})")
            elif row_families:
                # Wrong-family hits are demoted below family-neutral rows so
                # off-topic corpora (MiniMax H3 flooding an LTX query) cannot
                # outrank genuinely matching or neutral evidence.
                score += _HIVEMIND_FAMILY_MISMATCH_OFFSET
                reasons.append(
                    "hivemind:wrong family demoted "
                    f"({', '.join(sorted(row_families))})"
                )
        if score <= 0:
            continue
        ranked = dict(row)
        ranked["score"] = max(int(row.get("score", 0) or 0), score)
        ranked["reasons"] = reasons or list(row.get("reasons", []) or [])
        scored.append((ranked["score"], -index, ranked))
    scored.sort(reverse=True)
    return [row for _, _, row in scored]


# ── Agent tool transport: search / get (A01) ────────────────────────────────
#
# Transport + query translation ONLY.  Table selection, PostgREST filter
# translation, deterministic ordering and paging live here; input validation,
# rate-limit policy (the R2-B2 cooldown circuit), typed status mapping, and
# ToolResult construction live in ``hivemind_tools``.  There is no task
# classification, no winner selection, no enough-check, and no stop decision
# anywhere on this path.

_HIVEMIND_EVIDENCE_PREFIX = "hivemind"

_HIVEMIND_TABLE_ID_COLUMNS = {
    "external_resources": "id",
    "unified_feed": "item_id",
    "message_feed": "message_id",
}

# source_type -> ordered (table, kind) scopes.  Operator directive §37
# (HIVEMIND-SCOPE-FIX, supersedes §36 S1/S2): workflows are DISCOVERED via
# ``external_resources`` and community guidance lives in ``message_feed``, so
# BOTH tables are text-searched with few distinctive tokens per table (<=6
# ilike patterns; the §36 "message_feed only" posture made workflow discovery
# impossible).  ``unified_feed`` appears only as the distillation tier and is
# NON-TEXT there: any ilike over its UNION scan trips Postgres SQLSTATE 57014,
# so distillations are served by id (``hivemind_get``) or through structured
# filters.  A free-text-only distillation request therefore produces no
# criteria and the scope is skipped rather than guessed at.
_SOURCE_TYPE_SCOPES: dict[str | None, tuple[tuple[str, str], ...]] = {
    None: (
        ("external_resources", "workflow"),
        ("message_feed", "message"),
        ("unified_feed", "distillation"),
    ),
    "workflow": (
        ("external_resources", "workflow"),
        ("message_feed", "message"),
    ),
    "discord": (("message_feed", "message"),),
    "distillation": (("unified_feed", "distillation"),),
}

# Candidate pool fetched per scope.  Small bounded fetch (the lean per-token
# content query is index-backed); pagination stays a client-side offset over
# this deterministically ordered pool.
_SCOPE_FETCH_LIMIT = 20


def _evidence_id(table: str, row: Mapping[str, Any]) -> str | None:
    """Stable, resolvable evidence ID for a Hivemind row.

    ``hivemind:<table>:<row_id>`` where ``row_id`` is the table's natural id
    column, stringified so Discord snowflakes survive JSON precision loss.
    :func:`hivemind_get` resolves the same ID back to a full-row fetch.

    REC-A: the natural id column is the ONLY valid source.  Falling back to
    ``external_id``/``url``/``title`` produced parseable-looking IDs that
    ``hivemind_get`` could never resolve (``id=eq.vibecomfy:wf-1`` finds no
    row), surfacing as "no such record".  Returns None when the row lacks its
    natural id — such rows are unfetchable and are dropped by the search
    transport instead of being offered as evidence.
    """
    column = _HIVEMIND_TABLE_ID_COLUMNS.get(table)
    if column is None:
        return None
    raw = row.get(column)
    if raw is None:
        return None
    return f"{_HIVEMIND_EVIDENCE_PREFIX}:{table}:{raw}"


def _parse_evidence_id(evidence_id: str) -> tuple[str, str] | None:
    """Split an evidence ID into ``(table, row_id)``; None when malformed."""
    if not isinstance(evidence_id, str):
        return None
    parts = evidence_id.split(":", 2)
    if len(parts) != 3 or parts[0] != _HIVEMIND_EVIDENCE_PREFIX:
        return None
    table, row_id = parts[1], parts[2]
    if table not in _HIVEMIND_TABLE_ID_COLUMNS:
        return None
    if not row_id.strip() or any(char in row_id for char in ("?", "/", "#", " ")):
        return None
    return table, row_id


def _json_containment(payload: dict[str, Any]) -> str:
    """PostgREST JSONB containment value for the ``metadata`` column."""
    return f"cs.{json.dumps(payload, separators=(',', ':'))}"


def _nested_or_params(or_groups: list[str]) -> str:
    """AND of several OR groups as a single PostgREST ``and=`` value.

    ``and=(or:(content.ilike.*ltx*,content.ilike.*ltxv*),or:(...))``.
    Only used when a scope needs more than one boolean group (the free-text
    query plus a family/capability/node-class translation on ``message_feed``).
    """
    return "(" + ",".join(f"or:{group}" for group in or_groups) + ")"


def _hivemind_scope_params(
    *,
    table: str,
    kind: str,
    query: str,
    model_family: str | None,
    capability: str | None,
    node_class: str | None,
    channel: str | None,
    author: str | None,
    date_from: str | None,
    date_to: str | None,
    has_workflow: bool | None,
    limit: int,
    degraded: bool = False,
) -> dict[str, str] | None:
    """Translate one ``(table, kind)`` scope into PostgREST query params.

    Returns None when no criterion applies to this scope (for example a
    free-text-only distillation request against ``unified_feed``, which is
    never text-searched): the scope is skipped rather than guessed at.
    """
    params: dict[str, str] = {
        "select": "*",
        "limit": str(_HIVEMIND_DEGRADED_LIMIT if degraded else limit),
        "order": "created_at.desc",
    }

    if table == "message_feed":
        # §37.1 (HIVEMIND-SCOPE-FIX-REV): ONE SHARED pattern budget spans
        # ALL text criteria on this table.  Candidates are collected in a
        # documented priority order — free-text query tokens first, then
        # family alias translations, then capability aliases, then
        # node_class — deduplicated case-insensitively across groups, and
        # truncated at :data:`_HIVEMIND_SCOPE_PATTERN_CAP`.  Each criterion
        # with surviving tokens keeps its own OR group (ANDed together as
        # before); what changed is that the cap is shared, never per-group,
        # so a composite request cannot sum past the table budget.
        candidate_groups: list[list[str]] = []
        query_tokens = _hivemind_scope_tokens(query)
        if query_tokens:
            candidate_groups.append(query_tokens)
        if model_family and not degraded:
            aliases = _HIVEMIND_SEMANTIC_FAMILY_TERMS.get(
                model_family.casefold(), (model_family,)
            )
            candidate_groups.append(_hivemind_scope_tokens(" ".join(aliases)))
        if capability and not degraded:
            aliases = _HIVEMIND_SEMANTIC_TASK_TERMS.get(
                capability.casefold(), (capability,)
            )
            candidate_groups.append(_hivemind_scope_tokens(" ".join(aliases)))
        if node_class and not degraded:
            candidate_groups.append(_hivemind_scope_tokens(node_class))
        seen_tokens: set[str] = set()
        budget = _HIVEMIND_SCOPE_PATTERN_CAP
        or_groups: list[str] = []
        for group_tokens in candidate_groups:
            chosen: list[str] = []
            for token in group_tokens:
                if budget <= 0:
                    break
                key = token.casefold()
                if key in seen_tokens:
                    continue
                seen_tokens.add(key)
                chosen.append(token)
                budget -= 1
            if chosen:
                or_groups.append(_hivemind_message_or(chosen, degraded=degraded))
        if len(or_groups) == 1:
            params["or"] = or_groups[0]
        elif len(or_groups) > 1:
            params["and"] = _nested_or_params(or_groups)
        if channel:
            params["channel_name"] = f"eq.{channel}"
        if author:
            params["author_name"] = f"eq.{author}"
    elif table == "external_resources":
        # WHERE WORKFLOWS LIVE (§37.2): title/body text search over few
        # distinctive tokens; no channel/author columns on this table, so
        # those structured filters stay a message_feed concern.
        text_or = _hivemind_resource_ilike(query, degraded=degraded)
        if text_or:
            params["or"] = text_or
    elif table == "unified_feed":
        # NON-TEXT ONLY (§37.2): an ilike over this
        # UNION view trips the Postgres statement timeout (SQLSTATE 57014).
        # Distillations are reached by id (``hivemind_get``) or through the
        # structured filters below; a free-text-only request leaves no
        # criteria and the scope is skipped rather than guessed at.  No
        # server-side sort over the body-heavy view: results are ranked
        # client-side after the bounded fetch.
        params.pop("order", None)
        params["kind"] = f"eq.{kind}"
        if has_workflow is not None:
            params["metadata"] = _json_containment({"has_workflow": has_workflow})
    else:  # pragma: no cover - unknown table
        return None

    if date_from and date_to:
        date_group = f"(created_at.gte.{date_from},created_at.lte.{date_to})"
        existing_and = params.get("and")
        if existing_and:
            params["and"] = (
                existing_and[:-1]
                + f",created_at.gte.{date_from},created_at.lte.{date_to})"
            )
        else:
            params["and"] = date_group
    elif date_from:
        params["created_at"] = f"gte.{date_from}"
    elif date_to:
        params["created_at"] = f"lte.{date_to}"

    # A scope with no search criteria at all would return a meaningless
    # recent dump; skip it unless at least one filter narrowed the query.
    criteria = {k for k in params if k not in {"select", "limit", "order", "kind"}}
    if not criteria:
        return None
    return params


def _created_at_ts(row: Mapping[str, Any]) -> float:
    raw = row.get("created_at")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if not isinstance(raw, str) or not raw.strip():
        return 0.0
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.timestamp()
    except ValueError:
        return 0.0


def _validated_bucket(row: Mapping[str, Any]) -> int:
    """Deterministic validation bucket for the ``validated`` sort.

    0 = approved distillation or parseable workflow, 1 = other
    distillation/workflow, 2 = raw community messages.
    """
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    kind = str(row.get("kind") or "")
    if kind == "distillation":
        status = str(metadata.get("status") or "").casefold()
        return 0 if status == "approved" else 1
    if kind == "workflow":
        semantics = metadata.get("workflow_semantics")
        if not isinstance(semantics, Mapping):
            semantics = {}
        gates = semantics.get("promotion_gates")
        if not isinstance(gates, Mapping):
            gates = {}
        if gates.get("parseable_workflow") is True or metadata.get("has_workflow_json") is True:
            return 0
        return 1
    return 2


def _order_hivemind_rows(
    rows: list[dict[str, Any]],
    *,
    sort: str,
    query: str,
) -> list[dict[str, Any]]:
    """Deterministic ordering for a single candidate pool (no judgment)."""
    def _evidence_key(row: Mapping[str, Any]) -> str:
        # Transport guarantees a resolvable natural id; defensive fallback
        # keeps the sort total even for synthetic rows in tests.
        return _evidence_id(str(row.get("_hivemind_table") or ""), row) or ""

    def _recent_key(row: Mapping[str, Any]) -> tuple[float, str]:
        return (-_created_at_ts(row), _evidence_key(row))

    if sort == "recent":
        return sorted(rows, key=_recent_key)
    if sort == "validated":
        return sorted(
            rows,
            key=lambda r: (
                _validated_bucket(r),
                -_created_at_ts(r),
                _evidence_key(r),
            ),
        )
    # relevance: reuse the existing deterministic ranker.  A query with no
    # distinctive tokens has no relevance signal, so fall back to recency.
    if not _distinctive_tokens(query):
        return sorted(rows, key=_recent_key)
    ranked = _rank_hivemind_rows(rows, query)
    return sorted(
        ranked,
        key=lambda r: (
            -int(r.get("score") or 0),
            _evidence_key(r),
        ),
    )


def _hivemind_hit(row: Mapping[str, Any], table: str) -> dict[str, Any]:
    """Stable, compact hit shape for one row (field mapping only)."""
    kind = str(row.get("kind") or "")
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    semantics = metadata.get("workflow_semantics")
    if not isinstance(semantics, Mapping):
        semantics = None
    if table == "external_resources" or kind == "workflow":
        source_type = "workflow"
    elif kind == "distillation":
        source_type = "distillation"
    else:
        source_type = "discord"
    return {
        "evidence_id": _evidence_id(table, row),
        "source_type": source_type,
        "table": table,
        "title": _first_text(row, "title", "name", "class_type"),
        "body": _excerpt(_first_text(row, "body", "content", "description", "text")),
        "url": _first_text(row, "url", "source_url", "permalink"),
        "author": _first_text(row, "author", "author_name"),
        "channel": _first_text(row, "channel", "channel_name", "context"),
        "created_at": row.get("created_at"),
        "score": max(int(row.get("score") or 0), 0),
        "status": metadata.get("status"),
        "confidence": metadata.get("confidence"),
        "semantics": semantics,
    }


def _hivemind_search_transport(
    *,
    query: str,
    source_type: str | None,
    model_family: str | None,
    capability: str | None,
    node_class: str | None,
    channel: str | None,
    author: str | None,
    date_from: str | None,
    date_to: str | None,
    has_workflow: bool | None,
    sort: str,
    limit: int,
    offset: int,
    timeout: float,
) -> dict[str, Any]:
    """Fetch, order, and page the Hivemind corpus for one validated request.

    Returns ``{"hits": [...], "has_more": bool, "diagnostics": [...]}`` plus
    ``"rate_limit"`` when any scope ended HTTP 429-limited (review C4): the
    tool layer opens the shared cooldown circuit while this call keeps its
    merged hits.  Per-scope deadlines (§37.3): EACH scope gets its own full
    ``timeout`` budget, so one slow or failing scope cannot starve the
    others — a scope that times out or errors records its diagnostic and the
    loop continues; hits from all scopes merge after every scope has
    returned.  A scope whose fetch RETURNS counts as succeeded even with
    zero rows; ONLY when EVERY attempted scope failed is the first
    :class:`HivemindError` re-raised (§37.3 / review C3) so the tool can
    type it.
    """
    scopes = _SOURCE_TYPE_SCOPES.get(source_type, ())
    rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    first_error: HivemindError | None = None
    # HIVEMIND-SCOPE-FIX-REV: per-scope outcome tracking (review C3) and
    # partial-429 capture (review C4).  A scope SUCCEEDS when its fetch
    # returns — even with zero rows; an empty corpus result is not a failure.
    succeeded_scopes = 0
    failed_scopes = 0
    first_rate_limit_error: HivemindError | None = None
    first_rate_limit_scope: str | None = None

    for table, kind in scopes:
        # §37.3: fresh per-scope deadline — computed INSIDE the loop so no
        # earlier scope's spend eats a later scope's budget.
        scope_deadline = time.monotonic() + timeout
        params = _hivemind_scope_params(
            table=table,
            kind=kind,
            query=query,
            model_family=model_family,
            capability=capability,
            node_class=node_class,
            channel=channel,
            author=author,
            date_from=date_from,
            date_to=date_to,
            has_workflow=has_workflow,
            limit=_SCOPE_FETCH_LIMIT,
        )
        if params is None:
            continue
        try:
            parsed = _hivemind_get_table(
                table, params, timeout=timeout, deadline=scope_deadline
            )
        except HivemindError as exc:
            parsed = None
            last_error = exc
            if exc.statement_timeout:
                degraded_params = _hivemind_scope_params(
                    table=table,
                    kind=kind,
                    query=query,
                    model_family=model_family,
                    capability=capability,
                    node_class=node_class,
                    channel=channel,
                    author=author,
                    date_from=date_from,
                    date_to=date_to,
                    has_workflow=has_workflow,
                    limit=_HIVEMIND_DEGRADED_LIMIT,
                    degraded=True,
                )
                if degraded_params is not None and time.monotonic() < scope_deadline:
                    try:
                        # Literal degrade-then-stop: one degraded HTTP attempt,
                        # without re-entering the generic 57014 retry loop.
                        parsed = _hivemind_get_table(
                            table,
                            degraded_params,
                            timeout=timeout,
                            deadline=scope_deadline,
                            statement_timeout_retries=0,
                        )
                        diagnostics.append(
                            {
                                "scope": f"{table}:{kind}",
                                "message": "hivemind_query_degraded_after_57014",
                            }
                        )
                    except HivemindError as retry_exc:
                        last_error = retry_exc
            if parsed is None:
                failed_scopes += 1
                first_error = first_error or last_error
                diagnostics.append(
                    {"scope": f"{table}:{kind}", "message": str(last_error)}
                )
                # Review C4: remember the FIRST 429 even though other scopes
                # may still contribute hits, so the tool layer can open the
                # shared cooldown circuit instead of hammering the
                # rate-limited backend on subsequent calls.
                if last_error.status_code == 429 and first_rate_limit_error is None:
                    first_rate_limit_error = last_error
                    first_rate_limit_scope = f"{table}:{kind}"
            else:
                succeeded_scopes += 1
        else:
            succeeded_scopes += 1
        for row in parsed if isinstance(parsed, list) else []:
            if not isinstance(row, dict):
                continue
            # REC-A: rows without their natural id column are unfetchable
            # via hivemind_get — never surface them as evidence.
            if _evidence_id(table, row) is None:
                continue
            stamped = dict(row)
            stamped["_hivemind_table"] = table
            rows.append(stamped)

    # §37.3 / review C3: "empty" means NO scope succeeded — re-raise ONLY
    # when EVERY attempted scope failed.  A successful-but-empty scope plus
    # a failed scope returns OK with the failed scope's diagnostic attached.
    if failed_scopes and not succeeded_scopes and first_error is not None:
        raise first_error

    # Review C4: surface any partial-scope 429 so the tool layer opens the
    # shared R2-B2 cooldown circuit even though this call keeps its hits.
    rate_limit: dict[str, Any] | None = None
    if first_rate_limit_error is not None:
        rate_limit = {
            "status_code": int(first_rate_limit_error.status_code or 429),
            "retry_after_seconds": first_rate_limit_error.retry_after_seconds,
            "scope": first_rate_limit_scope,
        }

    if not rows:
        return {
            "hits": [],
            "has_more": False,
            "diagnostics": tuple(diagnostics),
            "rate_limit": rate_limit,
        }

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        evidence_id = _evidence_id(str(row.get("_hivemind_table") or ""), row)
        if evidence_id is None:
            continue
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        deduped.append(row)

    ordered = _order_hivemind_rows(deduped, sort=sort, query=query)
    page = ordered[offset : offset + limit]
    return {
        "hits": [_hivemind_hit(row, str(row.get("_hivemind_table") or "")) for row in page],
        "has_more": offset + limit < len(ordered),
        "diagnostics": tuple(diagnostics),
        "rate_limit": rate_limit,
    }


def _hivemind_get_row(
    table: str,
    row_id: str,
    *,
    timeout: float,
) -> dict[str, Any] | None:
    """Fetch one full Hivemind row by its natural id column; None when absent."""
    column = _HIVEMIND_TABLE_ID_COLUMNS[table]
    params = {"select": "*", column: f"eq.{row_id}", "limit": "1"}
    parsed = _hivemind_get_table(
        table,
        params,
        timeout=timeout,
        deadline=time.monotonic() + timeout,
    )
    for row in parsed if isinstance(parsed, list) else []:
        if isinstance(row, dict):
            return row
    return None
