"""Hivemind transport for the executor research phase (A01).

Shared PostgREST GET against the public Banodoco Supabase backend, plus the
agent-tool search/get transport: table selection, PostgREST filter
translation, deterministic ordering and paging for one model-authored query
string.  There is no term expansion, no winner selection, no evidence
thresholds, no latches, and no early-stop.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import datetime
from typing import Any
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
    """

    def __init__(
        self,
        message: str,
        *,
        reason: str | None = None,
        status_code: int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


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
        retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
        raise HivemindError(
            f"Hivemind HTTP error {exc.code}: {exc.reason} ({body})",
            reason="http",
            status_code=exc.code,
            retry_after_seconds=retry_after,
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


def _distinctive_tokens(query: str) -> list[str]:
    """Tokens remaining after ``_SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS``.

    Preserve original order; cap at 8 tokens.  Used for high-precision
    phrase queries and as the relevance signal for deterministic ordering.
    """
    stop = _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS
    return [t for t in _query_tokens(query) if t.casefold() not in stop][:8]


def _hivemind_single_or_phrase_ilike(query: str) -> str | None:
    """Build ``or=(title.ilike.*Q*,body.ilike.*Q*)`` for this one query.

    ``Q`` is the distinctive tokens joined with a single space (one token
    if only one remains). Returns None only when no distinctive token remains.
    """
    tokens = _distinctive_tokens(query)
    if not tokens:
        return None
    q = " ".join(tokens)
    return f"(title.ilike.*{q}*,body.ilike.*{q}*)"
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

# source_type -> ordered (table, kind) scopes.  ``None`` searches every corpus:
# external workflow precedents, Discord messages, and curated distillations.
_SOURCE_TYPE_SCOPES: dict[str | None, tuple[tuple[str, str], ...]] = {
    None: (
        ("external_resources", "workflow"),
        ("unified_feed", "message"),
        ("unified_feed", "distillation"),
    ),
    "workflow": (("external_resources", "workflow"),),
    "discord": (("unified_feed", "message"),),
    "distillation": (("unified_feed", "distillation"),),
}

# Candidate pool fetched per scope.  Fixed so pagination (client-side offset
# over the deterministically ordered pool) is stable across calls.
_SCOPE_FETCH_LIMIT = 20


def _evidence_id(table: str, row: Mapping[str, Any]) -> str:
    """Stable, resolvable evidence ID for a Hivemind row.

    ``hivemind:<table>:<row_id>`` where ``row_id`` is the table's natural id
    column, stringified so Discord snowflakes survive JSON precision loss.
    :func:`hivemind_get` resolves the same ID back to a full-row fetch.
    """
    column = _HIVEMIND_TABLE_ID_COLUMNS.get(table, "id")
    raw = row.get(column)
    if raw is None:
        raw = row.get("external_id", row.get("url", row.get("title")))
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

    ``and=(or:(title.ilike.*q*,body.ilike.*q*),or:(title.ilike.*wan*,...))``.
    Only used when a scope needs more than one boolean group (text query plus
    a family/capability/node-class translation on ``unified_feed``).
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
) -> dict[str, str] | None:
    """Translate one ``(table, kind)`` scope into PostgREST query params.

    Returns None when no criterion applies to this scope (for example a
    channel filter against ``external_resources``, which has no channel
    column): the scope is skipped rather than guessed at.
    """
    params: dict[str, str] = {
        "select": "*",
        "limit": str(limit),
        "order": "created_at.desc",
    }

    if table == "external_resources":
        if channel or author:
            # external_resources carries no channel/author columns: the scope
            # is skipped rather than guessed at.
            return None
        params["kind"] = f"eq.{kind}"
        text_or = _hivemind_ilike_query(_hivemind_search_terms(query))
        if text_or:
            params["or"] = text_or
        containment: dict[str, Any] = {}
        semantics: dict[str, Any] = {}
        if model_family:
            semantics["model_families"] = [model_family]
        if capability:
            semantics["task_type"] = capability
        if node_class:
            semantics["node_types"] = [node_class]
        if semantics:
            containment["workflow_semantics"] = semantics
        if has_workflow is not None:
            containment["has_workflow_json"] = has_workflow
        if containment:
            params["metadata"] = _json_containment(containment)
    elif table == "unified_feed":
        params["kind"] = f"eq.{kind}"
        text_or = _hivemind_single_or_phrase_ilike(query)
        or_groups: list[str] = []
        if text_or:
            or_groups.append(text_or)
        if model_family:
            aliases = _HIVEMIND_SEMANTIC_FAMILY_TERMS.get(
                model_family.casefold(), (model_family,)
            )
            family_or = _hivemind_ilike_query(list(aliases))
            if family_or:
                or_groups.append(family_or)
        if capability:
            aliases = _HIVEMIND_SEMANTIC_TASK_TERMS.get(
                capability.casefold(), (capability,)
            )
            capability_or = _hivemind_ilike_query(list(aliases))
            if capability_or:
                or_groups.append(capability_or)
        if node_class:
            node_or = _hivemind_ilike_query([node_class])
            if node_or:
                or_groups.append(node_or)
        if len(or_groups) == 1:
            params["or"] = or_groups[0]
        elif len(or_groups) > 1:
            params["and"] = _nested_or_params(or_groups)
        if channel:
            params["channel"] = f"eq.{channel}"
        if author:
            params["author"] = f"eq.{author}"
        if has_workflow is not None:
            params["metadata"] = _json_containment({"has_workflow": has_workflow})
    else:  # pragma: no cover - message_feed is not a search scope
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
    def _recent_key(row: Mapping[str, Any]) -> tuple[float, str]:
        return (-_created_at_ts(row), _evidence_id(str(row.get("_hivemind_table") or ""), row))

    if sort == "recent":
        return sorted(rows, key=_recent_key)
    if sort == "validated":
        return sorted(
            rows,
            key=lambda r: (
                _validated_bucket(r),
                -_created_at_ts(r),
                _evidence_id(str(r.get("_hivemind_table") or ""), r),
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
            _evidence_id(str(r.get("_hivemind_table") or ""), r),
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

    Returns ``{"hits": [...], "has_more": bool, "diagnostics": [...]}``.
    Scope failures degrade: successful scopes still contribute hits and a
    per-scope diagnostic is recorded.  If every scope fails, the first
    :class:`HivemindError` is re-raised so the tool can type it.
    """
    scopes = _SOURCE_TYPE_SCOPES.get(source_type, ())
    rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, str]] = []
    first_error: HivemindError | None = None

    for table, kind in scopes:
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
            parsed = _hivemind_get_table(table, params, timeout=timeout)
            for row in parsed if isinstance(parsed, list) else []:
                if not isinstance(row, dict):
                    continue
                stamped = dict(row)
                stamped["_hivemind_table"] = table
                rows.append(stamped)
        except HivemindError as exc:
            first_error = first_error or exc
            diagnostics.append(
                {"scope": f"{table}:{kind}", "message": str(exc)}
            )

    if not rows:
        if first_error is not None:
            raise first_error
        return {"hits": [], "has_more": False, "diagnostics": tuple(diagnostics)}

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        evidence_id = _evidence_id(str(row.get("_hivemind_table") or ""), row)
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
    parsed = _hivemind_get_table(table, params, timeout=timeout)
    for row in parsed if isinstance(parsed, list) else []:
        if isinstance(row, dict):
            return row
    return None
