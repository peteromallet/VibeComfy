"""Deterministic executor research phase.

Implements the research step of the classify → research → implement → reply
pipeline.  Uses the local search corpus (``build_search_corpus()``) with
deterministic scoring and compactly normalized output fields.  Adds an
injectable direct-HTTP Hivemind tier with configurable timeout, converting
timeouts and errors into non-fatal warnings so the executor always proceeds
with local-only results rather than blocking on network unavailability.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
import urllib.error
import urllib.request
from typing import Any, Callable

from vibecomfy.search.index import build_search_corpus
from vibecomfy.search.scorer import search_entries, SearchResult
from vibecomfy.ingest.workflow_source import (
    WorkflowLoadResult,
    WorkflowNodeRecord,
    load_workflow_source,
    normalize_workflow_source,
)

from .contracts import (
    InspectionSummary,
    PrecedentAdaptationPlan,
    ResearchResult,
    WorkflowSlice,
    warning_detail_from_exception,
)

LOGGER = logging.getLogger(__name__)

# ── Conservative external-search defaults ────────────────────────────────────

_DEFAULT_HIVEMIND_URL = "https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1/unified_feed"
_DEFAULT_HIVEMIND_KEY = "sb_publishable_O38oPBafrBoFrpi_rlWJvA_UJrulFsx"
_DEFAULT_HIVEMIND_TIMEOUT = 5.0  # seconds
_DEFAULT_WEB_SEARCH_URL = "https://duckduckgo.com/html/"
_DEFAULT_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_DEFAULT_WEB_SEARCH_TIMEOUT = 5.0  # seconds
_DEFAULT_EXTERNAL_LIMIT = 10
WORKFLOW_RESEARCH_GUIDANCE = (
    "Workflow/template exploration: use `vibecomfy workflows list --ready` to see ready templates; "
    "explore or copy ready template `.py` representations with "
    "`vibecomfy copy-to-recipe <template_id> --out <file.py> --strip-markers`."
)

# A Hivemind client is any callable (query: str, timeout: float) → dict.
HivemindClient = Callable[[str, float], dict[str, Any]]
WebSearchClient = Callable[[str, float], dict[str, Any]]

_USE_DEFAULT = object()

_QUERY_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*")
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

_PATTERN_NODE_TERMS: dict[str, tuple[str, ...]] = {
    "vace": ("vace",),
    "lora_chain": ("lora", "iclora"),
    "low_vram": ("blockswap", "block swap", "low_vram", "low vram", "low_ram", "low ram", "chunkfeed", "decode_to_disk"),
    "two_pass_refinement": ("two_stage", "two stage", "two-pass", "two pass", "upscale", "upsampler", "refine", "samplercustomadvanced", "ksampler"),
    "depth_pose_guidance": ("controlnet", "control net", "depth", "pose", "dwpose", "preprocessor", "guide"),
}

_PATTERN_REQUIRED_TERMS: dict[str, tuple[str, ...]] = {
    "vace": ("vace",),
    "lora_chain": ("lora", "iclora"),
    "low_vram": ("blockswap", "low_vram", "low vram", "chunkfeed"),
    "two_pass_refinement": ("upsampler", "upscale", "sampler"),
    "depth_pose_guidance": ("controlnet", "depth", "pose", "dwpose"),
}

_FAMILY_EVIDENCE_TERMS: dict[str, tuple[str, ...]] = {
    "wan": ("wanvideo", "wan2", "wan_2", "wan 2", "wan2_1", "wan2.1", "wan2_2", "wan2.2"),
    "ltx": ("ltx", "ltxv", "lightricks"),
    "flux": ("flux", "flux1", "flux2"),
    "qwen": ("qwen",),
    "hunyuan": ("hunyuan", "hyvideo"),
    "sd": ("sdxl", "sd3", "stable diffusion", "stable_diffusion"),
}

_ANCHOR_ROLE_PRIORITY = ("lora", "model", "sampler", "latent", "conditioning", "exit")

# ── Hivemind error (non-fatal) ───────────────────────────────────────────────


class HivemindError(Exception):
    """Non-fatal Hivemind error — caught by the research runner and converted
    to a warning rather than propagating as an exception."""


class WebSearchError(Exception):
    """Non-fatal web-search error converted to a warning by ``research()``."""


# ── Local corpus research (deterministic) ────────────────────────────────────


def run_local_research(
    query: str,
    *,
    task: str | None = None,
    limit: int = 10,
) -> ResearchResult:
    """Research using only the deterministic local corpus.

    Calls :func:`~vibecomfy.search.index.build_search_corpus`, scores entries
    against *query* with :func:`~vibecomfy.search.scorer.search_entries`, and
    produces a compactly normalized :class:`ResearchResult`.

    Parameters
    ----------
    query:
        The user's natural-language request.
    task:
        Optional task hint (e.g. ``"t2v"``, ``"controlnet"``) for scorer alias
        expansion.
    limit:
        Maximum number of top-scoring local results to include.
    """
    corpus = build_search_corpus()
    results = search_entries(corpus, query, task=task, limit=limit)
    sources = tuple(_normalize_source(r) for r in results)
    summary = _build_summary(sources)
    return ResearchResult(summary=summary, sources=sources)


def _normalize_source(result: SearchResult) -> dict[str, Any]:
    """Compact, deterministic normalization of a single scored search result.

    The output dict always contains the same keys in the same order so
    serialization is fully deterministic.
    """
    entry = result.entry
    return {
        "class_type": entry.class_type,
        "score": result.score,
        "reasons": list(result.reasons),
        "source": entry.source,
        "pack": entry.pack,
        "description": entry.description,
        "tasks": list(entry.tasks),
        "path": entry.path,
        "template_id": entry.template_id,
        "source_workflow_path": entry.source_workflow_path,
        "source_workflow_available": entry.source_workflow_available,
        "source_workflow_parseable": entry.source_workflow_parseable,
        "adapt_pattern_keys": list(entry.adapt_pattern_keys),
    }


def _build_summary(sources: tuple[dict[str, Any], ...]) -> str:
    """Build a compact 1-sentence summary from source metadata."""
    if not sources:
        return "No relevant local results found."
    n = len(sources)
    top3 = [s["class_type"] for s in sources[:3]]
    names = ", ".join(top3)
    if n > 3:
        names += f", and {n - 3} more"
    result_scope = (
        "research"
        if any(str(source.get("source", "")).startswith(("hivemind", "web")) for source in sources)
        else "local"
    )
    workflow_sources = [
        source
        for source in sources
        if source.get("source") in {
            "ready_template",
            "source_workflow",
            "external_workflow",
            "curated",
            "custom_node_examples",
            "hivemind_workflow",
        }
        and source.get("path")
        and str(source.get("path")).endswith(".py")
    ]
    if workflow_sources:
        workflow_refs = ", ".join(
            f"{source.get('class_type')} ({source.get('path')})"
            for source in workflow_sources[:3]
        )
        return (
            f"Found {n} {result_scope} result(s): {names}. "
            f"Relevant workflow/template paths: {workflow_refs}. "
            f"{WORKFLOW_RESEARCH_GUIDANCE}"
        )
    return f"Found {n} {result_scope} result(s): {names}"


# ── Default direct-HTTP Hivemind client ──────────────────────────────────────


def _default_hivemind_client(query: str, timeout: float) -> dict[str, Any]:
    """Default direct-HTTP Hivemind client backed by Supabase/PostgREST.

    Searches the public ``unified_feed`` table's ``title`` and ``body`` columns
    with PostgREST ``ilike`` filters.

    Query handling intentionally favors recall: it builds an ``OR`` query from
    important tokens plus adjacent token phrases, then ranks rows locally by
    phrase/token matches.  This avoids the previous all-words-as-one-phrase
    failure where ``"Hotshot XL SDXL video"`` missed rows that mention
    ``"Hotshot XL"`` without every query word.

    Raises :class:`HivemindError` on any HTTP-level or timeout failure so the
    caller can convert it to a warning.
    """
    terms = _search_terms(query)
    if not terms:
        return {"results": []}

    filters: list[str] = []
    for term in terms:
        pattern = f"*{_postgrest_literal(term)}*"
        filters.append(f"title.ilike.{pattern}")
        filters.append(f"body.ilike.{pattern}")

    params = {
        "select": "*",
        "or": f"({','.join(filters)})",
        "limit": str(_DEFAULT_EXTERNAL_LIMIT * 3),
    }
    try:
        parsed = _hivemind_get(params, timeout=timeout)
        if isinstance(parsed, dict):
            return parsed
        rows = parsed if isinstance(parsed, list) else []

        workflow_params = dict(params)
        workflow_params["kind"] = "eq.workflow"
        workflow_rows = _hivemind_get(workflow_params, timeout=timeout)
        if isinstance(workflow_rows, list):
            rows = [*workflow_rows, *rows]

        return {"results": _rank_hivemind_rows(rows, query)[:_DEFAULT_EXTERNAL_LIMIT]}
    except TimeoutError as exc:
        raise HivemindError(f"Hivemind request timed out after {timeout}s") from exc
    except urllib.error.URLError as exc:
        raise HivemindError(f"Hivemind HTTP error: {exc}") from exc
    except ValueError as exc:
        raise HivemindError(f"Hivemind returned invalid JSON: {exc}") from exc


def _hivemind_get(params: dict[str, str], *, timeout: float) -> Any:
    url = f"{_DEFAULT_HIVEMIND_URL}?{urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "apikey": _DEFAULT_HIVEMIND_KEY,
            "Authorization": f"Bearer {_DEFAULT_HIVEMIND_KEY}",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return _parse_json_response(body)


def _parse_json_response(body: str) -> Any:
    import json

    return json.loads(body)


def _search_terms(query: str, *, max_terms: int = 8) -> list[str]:
    """Return recall-oriented PostgREST search terms for *query*.

    The terms include adjacent phrases before individual tokens. Common generic
    words are dropped when possible so broad words like ``video`` do not swamp
    more specific terms such as ``Hotshot`` and ``XL``.
    """
    raw_tokens = _query_tokens(query)
    if not raw_tokens:
        return []
    tokens = [t for t in raw_tokens if t.lower() not in _SEARCH_STOPWORDS]
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


def _query_tokens(query: str) -> list[str]:
    return [m.group(0) for m in _QUERY_TOKEN_RE.finditer(query)]


def _postgrest_literal(value: str) -> str:
    """Sanitize a value embedded in PostgREST's filter grammar."""
    return re.sub(r"[^A-Za-z0-9_.+ -]", " ", value).strip()


def _rank_hivemind_rows(rows: list[Any], query: str) -> list[dict[str, Any]]:
    query_terms = _search_terms(query, max_terms=12)
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        title = _first_text(row, "title", "name", "class_type")
        body = _first_text(row, "body", "description", "content", "text")
        haystack = f"{title}\n{body}".casefold()
        score = 0
        reasons: list[str] = []
        if row.get("kind") == "workflow":
            score += 25
            reasons.append("hivemind:workflow resource")
        for term in query_terms:
            needle = term.casefold()
            if not needle or needle not in haystack:
                continue
            is_phrase = " " in term
            in_title = needle in title.casefold()
            score += 50 if is_phrase else 20
            if in_title:
                score += 20
            reasons.append(
                f"hivemind:{'title' if in_title else 'body'} matched {term!r}"
            )
        if score <= 0:
            continue
        ranked = dict(row)
        ranked["score"] = max(int(row.get("score", 0) or 0), score)
        ranked["reasons"] = reasons or list(row.get("reasons", []) or [])
        scored.append((ranked["score"], -index, ranked))
    scored.sort(reverse=True)
    return [row for _, _, row in scored]


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


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


def _domain(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None


# ── Hivemind result normalization ────────────────────────────────────────────


def _normalize_hivemind_source(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single Hivemind result dict to the canonical source shape."""
    title = _first_text(item, "class_type", "name", "title")
    body = _first_text(item, "description", "body", "content", "text")
    if not title and body:
        # Unified-feed messages often have no class_type/name/title; use a
        # compact body excerpt so the source still has a usable identity.
        title = _excerpt(body, limit=80)
    url = _first_text(item, "url", "source_url", "permalink", "link")
    pack = item.get("pack", item.get("package"))
    if pack is None:
        pack = item.get("channel", item.get("source_type", item.get("kind"))) or _domain(url)
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    ready_id = _first_text(metadata, "ready_template_id") or _first_text(payload, "ready_template_id")
    path = (
        _first_text(item, "path")
        or _first_text(metadata, "path", "python_path")
        or _first_text(payload, "python_path")
    )
    source = "hivemind_workflow" if item.get("kind") == "workflow" else "hivemind"
    return {
        "class_type": ready_id or title,
        "score": item.get("score", 0),
        "reasons": _coerce_tasks(item.get("reasons", [])),
        "source": source,
        "pack": pack,
        "description": _excerpt(body),
        "tasks": _coerce_tasks(item.get("tasks", item.get("task"))),
        "path": path or None,
        "hivemind_id": item.get("item_id", item.get("id")),
        "url": url,
    }


def _run_hivemind_research(
    query: str,
    *,
    client: HivemindClient,
    timeout: float,
) -> tuple[dict[str, Any], ...]:
    """Run Hivemind and return normalized sources.

    Raises :class:`HivemindError` on any failure; the public ``research()``
    caller catches this and converts it to a warning.
    """
    response = client(query, timeout)
    items = response.get("results", response.get("sources", []))
    if not isinstance(items, list):
        items = []
    return tuple(
        _normalize_hivemind_source(item)
        for item in items
        if isinstance(item, dict)
    )


# ── Web fallback ─────────────────────────────────────────────────────────────


class _DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._active: dict[str, str] | None = None
        self._capture: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v or "" for k, v in attrs}
        classes = set(attr.get("class", "").split())
        if tag == "a" and "result__a" in classes:
            self.finish_result()
            self._active = {"url": _clean_duckduckgo_url(attr.get("href", ""))}
            self._capture = "title"
            self._parts = []
        elif self._active is not None and "result__snippet" in classes:
            self._capture = "snippet"
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._active is None or self._capture is None:
            return
        if self._capture == "title" and tag == "a":
            self._active["title"] = unescape(" ".join(self._parts).strip())
            self._capture = None
            self._parts = []
        elif self._capture == "snippet" and tag in {"a", "div"}:
            self._active["snippet"] = unescape(" ".join(self._parts).strip())
            self.results.append(self._active)
            self._active = None
            self._capture = None
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None:
            self._parts.append(data)

    def finish_result(self) -> None:
        if self._active is None:
            return
        if self._capture == "title":
            self._active["title"] = unescape(" ".join(self._parts).strip())
        if self._active.get("title") or self._active.get("url"):
            self._active.setdefault("snippet", "")
            self.results.append(self._active)
        self._active = None
        self._capture = None
        self._parts = []


def _clean_duckduckgo_url(url: str) -> str:
    parsed = urlparse(unescape(url))
    if parsed.path == "/l/":
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        if uddg:
            return unquote(uddg)
    return url


def _duckduckgo_search(query: str, timeout: float) -> list[dict[str, str]]:
    url = f"{_DEFAULT_WEB_SEARCH_URL}?q={quote(query)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html",
            "User-Agent": (
                "Mozilla/5.0 (compatible; vibecomfy-research/1.0; "
                "+https://github.com/peteromallet/vibecomfy)"
            ),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except TimeoutError as exc:
        raise WebSearchError(f"web search timed out after {timeout}s") from exc
    except urllib.error.URLError as exc:
        raise WebSearchError(f"web search HTTP error: {exc}") from exc

    parser = _DuckDuckGoHTMLParser()
    parser.feed(html)
    parser.finish_result()
    return parser.results[:_DEFAULT_EXTERNAL_LIMIT]


def _github_repository_search(query: str, timeout: float) -> list[dict[str, str]]:
    url = f"{_DEFAULT_GITHUB_SEARCH_URL}?q={quote(query)}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": (
                "vibecomfy-research/1.0 "
                "(https://github.com/peteromallet/vibecomfy)"
            ),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except TimeoutError as exc:
        raise WebSearchError(f"github search timed out after {timeout}s") from exc
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise WebSearchError(f"github search error: {exc}") from exc
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    results: list[dict[str, str]] = []
    for item in items[:_DEFAULT_EXTERNAL_LIMIT]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("full_name") or item.get("name") or "").strip()
        url = str(item.get("html_url") or "").strip()
        snippet = str(item.get("description") or "").strip()
        if title or url:
            results.append({"title": title, "url": url, "snippet": snippet})
    return results


def _default_web_search_client(query: str, timeout: float) -> dict[str, Any]:
    """Best-effort public web-search evidence using DuckDuckGo HTML + GitHub."""
    results: list[dict[str, str]] = []
    warnings: list[str] = []
    try:
        results.extend(_duckduckgo_search(query, timeout))
    except WebSearchError as exc:
        warnings.append(str(exc))
    try:
        results.extend(_github_repository_search(query, timeout))
    except WebSearchError as exc:
        warnings.append(str(exc))
    if not results and warnings:
        raise WebSearchError("; ".join(warnings))
    return {"results": results[:_DEFAULT_EXTERNAL_LIMIT], "warnings": warnings}


def _normalize_web_source(item: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    title = _first_text(item, "title", "class_type", "name")
    url = _first_text(item, "url", "href", "link")
    snippet = _first_text(item, "snippet", "description", "body")
    return {
        "class_type": title or url,
        "score": max(1, 40 - index),
        "reasons": ["web search fallback"],
        "source": "web",
        "pack": _domain(url),
        "description": _excerpt(snippet),
        "tasks": [],
        "url": url,
    }


def _run_web_search(
    query: str,
    *,
    client: WebSearchClient,
    timeout: float,
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    response = client(query, timeout)
    items = response.get("results", response.get("sources", []))
    if not isinstance(items, list):
        items = []
    source_warnings = response.get("warnings", ())
    if not isinstance(source_warnings, (list, tuple)):
        source_warnings = ()
    warnings = tuple(str(w).strip() for w in source_warnings if str(w).strip())
    return tuple(
        _normalize_web_source(item, index=i)
        for i, item in enumerate(items)
        if isinstance(item, dict)
    ), warnings


# ── Structured precedent helpers (SD2) ────────────────────────────────────────


def _build_inspection_summary(graph: dict | None) -> InspectionSummary | None:
    """Build an :class:`InspectionSummary` from raw graph inspection.

    Returns ``None`` when no graph is attached so callers can distinguish
    "no graph" from "empty graph".
    """
    if graph is None:
        return None
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return InspectionSummary(node_count=0, summary="Graph has no node list.")

    node_count = len(nodes)
    node_types: list[str] = []
    has_dangling_inputs = False
    has_dangling_outputs = False
    key_widget_values: list[dict] = []

    for node in nodes:
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or node.get("type")
        if isinstance(ct, str) and ct.strip():
            node_types.append(ct.strip())

        # Check for dangling inputs
        inputs = node.get("inputs")
        if isinstance(inputs, list):
            for inp in inputs:
                if isinstance(inp, dict) and inp.get("link") is None:
                    has_dangling_inputs = True
                    break

        # Collect key widget values (first few non-None values)
        widgets = node.get("widgets_values")
        if isinstance(widgets, list):
            widget_info: dict[str, object] = {}
            for j, w in enumerate(widgets[:5]):
                if w is not None:
                    widget_info[f"w{j}"] = w
            if widget_info:
                key_widget_values.append(widget_info)

    # Check for dangling outputs (nodes with no outgoing links in graph links)
    links = graph.get("links")
    if isinstance(links, list) and nodes:
        linked_ids: set = set()
        for link in links:
            if isinstance(link, dict):
                origin = link.get("origin_id")
                if origin is not None:
                    linked_ids.add(origin)
            elif isinstance(link, list) and len(link) >= 4:
                linked_ids.add(link[1])
        node_ids = {
            node.get("id") for node in nodes
            if isinstance(node, dict) and node.get("id") is not None
        }
        dangling = node_ids - linked_ids
        has_dangling_outputs = len(dangling) > 0 and len(linked_ids) > 0

    # Build compact summary
    type_summary = ", ".join(node_types[:5])
    if len(node_types) > 5:
        type_summary += f", and {len(node_types) - 5} more"
    summary = (
        f"Graph with {node_count} node(s): {type_summary}. "
        f"{'Has' if has_dangling_inputs else 'No'} dangling input(s), "
        f"{'has' if has_dangling_outputs else 'no'} dangling output(s)."
    )

    return InspectionSummary(
        node_count=node_count,
        node_types=tuple(node_types),
        has_dangling_inputs=has_dangling_inputs,
        has_dangling_outputs=has_dangling_outputs,
        key_widget_values=tuple(key_widget_values),
        summary=summary,
    )


def _build_precedent_slices(
    sources: tuple[dict, ...],
) -> tuple[WorkflowSlice, ...]:
    """Build source-backed :class:`WorkflowSlice` records from research sources."""
    workflow_source_kinds = {
        "ready_template",
        "source_workflow",
        "external_workflow",
        "hivemind_workflow",
    }
    slices: list[WorkflowSlice] = []
    seen: set[str] = set()

    for source in sources:
        if not isinstance(source, dict):
            continue
        source_kind = str(source.get("source", ""))
        path = source.get("path")
        source_workflow_path = source.get("source_workflow_path")
        class_type = str(source.get("class_type", ""))

        is_workflow = source_kind in workflow_source_kinds
        has_py_path = isinstance(path, str) and path.endswith(".py")
        has_source_workflow = isinstance(source_workflow_path, str) and source_workflow_path.endswith(".json")
        if not is_workflow and not has_py_path and not has_source_workflow:
            continue
        if not class_type or class_type in seen:
            continue

        load_result: WorkflowLoadResult | None = None
        if has_source_workflow:
            load_result = load_workflow_source(source_workflow_path)
        elif isinstance(path, str) and path.endswith(".json"):
            load_result = load_workflow_source(path)

        source_warnings: list[dict[str, Any]] = []
        if load_result is not None and load_result.ok:
            pattern_key = _source_pattern_key(source)
            extracted_nodes, source_warnings = _extract_pattern_nodes(
                load_result=load_result,
                pattern_key=pattern_key,
            )
            node_ids = tuple(record.node_id for record in extracted_nodes)
            node_types = tuple(record.class_type for record in extracted_nodes)
            entry_anchor = node_ids[0] if node_ids else None
            exit_anchor = node_ids[-1] if node_ids else None
        else:
            node_ids = ()
            node_types = ()
            entry_anchor = None
            exit_anchor = None

        if load_result is not None and load_result.blocks_candidate_output:
            continue

        seen.add(class_type)

        slices.append(
            WorkflowSlice(
                source_class_type=class_type,
                node_ids=node_ids,
                node_types=node_types,
                entry_anchor=entry_anchor,
                exit_anchor=exit_anchor,
                source_workflow_path=load_result.source_path if load_result is not None else None,
                python_path=path if isinstance(path, str) else None,
                warnings=tuple(source_warnings),
            )
        )

    return tuple(slices)


def _source_pattern_key(source: dict[str, Any]) -> str | None:
    keys = source.get("adapt_pattern_keys")
    if isinstance(keys, list | tuple):
        for key in keys:
            if isinstance(key, str) and key in _PATTERN_NODE_TERMS:
                return key

    text = " ".join(
        str(source.get(key, ""))
        for key in ("class_type", "path", "template_id", "source_workflow_path", "description")
    ).lower()
    for key, terms in _PATTERN_NODE_TERMS.items():
        if any(term in text for term in terms):
            return key
    return None


def _extract_pattern_nodes(
    *,
    load_result: WorkflowLoadResult,
    pattern_key: str | None,
) -> tuple[tuple[Any, ...], list[dict[str, Any]]]:
    """Return the minimal deterministic precedent node slice for a pattern."""
    if pattern_key is None:
        return load_result.nodes, []

    terms = _PATTERN_NODE_TERMS[pattern_key]
    required_terms = _PATTERN_REQUIRED_TERMS.get(pattern_key, ())
    matched = tuple(
        record for record in load_result.nodes
        if _node_record_matches_any(record, terms)
    )

    warnings: list[dict[str, Any]] = []
    if not matched:
        warnings.append({
            "code": "pattern_nodes_not_found",
            "severity": "warning",
            "pattern_key": pattern_key,
            "source_path": load_result.source_path,
            "message": f"No nodes matched deterministic extraction terms for {pattern_key}.",
            "required_terms": list(required_terms),
        })
        return (), warnings

    missing_terms = [
        term for term in required_terms
        if not any(_node_record_matches_any(record, (term,)) for record in matched)
    ]
    if missing_terms:
        warnings.append({
            "code": "missing_required_pattern_nodes",
            "severity": "warning",
            "pattern_key": pattern_key,
            "source_path": load_result.source_path,
            "message": f"Pattern slice is missing expected node evidence for {pattern_key}.",
            "missing_terms": missing_terms,
        })

    return matched, warnings


def _node_record_matches_any(record: Any, terms: tuple[str, ...]) -> bool:
    haystack = _node_record_search_text(record)
    return any(term in haystack for term in terms)


def _node_record_search_text(record: Any) -> str:
    return " ".join((
        str(getattr(record, "node_id", "")),
        str(getattr(record, "class_type", "")),
        str(getattr(record, "inputs", "")),
        str(getattr(record, "raw_node", "")),
    )).lower().replace("-", "_")


def _normalize_target_graph(graph: dict | None) -> WorkflowLoadResult | None:
    if graph is None:
        return None
    return normalize_workflow_source(graph, source_path="<target_graph>")


def _selected_source_records(selected_slice: WorkflowSlice) -> tuple[WorkflowNodeRecord, ...]:
    if not selected_slice.source_workflow_path:
        return ()
    load_result = load_workflow_source(selected_slice.source_workflow_path)
    if not load_result.ok:
        return ()
    selected_ids = set(selected_slice.node_ids)
    if not selected_ids:
        return load_result.nodes
    return tuple(record for record in load_result.nodes if record.node_id in selected_ids)


def _family_evidence_from_text(text: str) -> set[str]:
    haystack = text.lower().replace("-", "_").replace("\\", "/")
    families: set[str] = set()
    for family, terms in _FAMILY_EVIDENCE_TERMS.items():
        if any(term in haystack for term in terms):
            families.add(family)
    return families


def _detect_record_families(records: tuple[WorkflowNodeRecord, ...], *extra_text: str | None) -> set[str]:
    families: set[str] = set()
    for text in extra_text:
        if text:
            families.update(_family_evidence_from_text(text))
    for record in records:
        families.update(_family_evidence_from_text(_node_record_search_text(record)))
    return families


def _anchor_roles(record: WorkflowNodeRecord) -> tuple[str, ...]:
    text = _node_record_search_text(record)
    class_text = record.class_type.lower().replace("-", "_")
    input_names = {str(name).lower().replace("-", "_") for name in record.inputs}
    roles: list[str] = []

    if "lora" in text or "lora" in input_names:
        roles.append("lora")
    if (
        "model" in class_text
        or "loader" in class_text
        or "unet" in class_text
        or "checkpoint" in class_text
        or "model" in input_names
    ):
        roles.append("model")
    if "sampler" in class_text or "ksampler" in class_text or "sampler" in input_names:
        roles.append("sampler")
    if "latent" in class_text or "latent_image" in input_names or "samples" in input_names:
        roles.append("latent")
    if (
        "conditioning" in class_text
        or "cliptextencode" in class_text
        or "controlnet" in class_text
        or "positive" in input_names
        or "negative" in input_names
        or "conditioning" in input_names
    ):
        roles.append("conditioning")
    if (
        "save" in class_text
        or "decode" in class_text
        or "combine" in class_text
        or "images" in input_names
    ):
        roles.append("exit")

    deduped: list[str] = []
    for role in _ANCHOR_ROLE_PRIORITY:
        if role in roles and role not in deduped:
            deduped.append(role)
    return tuple(deduped)


def _anchor_socket_for_role(record: WorkflowNodeRecord, role: str) -> str:
    input_names = {str(name).lower().replace("-", "_") for name in record.inputs}
    if role == "lora" and "lora" in input_names:
        return "lora"
    if role == "model" and "model" in input_names:
        return "model"
    if role == "sampler" and "sampler" in input_names:
        return "sampler"
    if role == "latent" and "latent_image" in input_names:
        return "latent_image"
    if role == "latent" and "samples" in input_names:
        return "samples"
    if role == "conditioning" and "positive" in input_names:
        return "positive"
    if role == "conditioning" and "conditioning" in input_names:
        return "conditioning"
    if role == "exit" and "images" in input_names:
        return "images"
    return role


def _target_anchor_candidates(
    target_records: tuple[WorkflowNodeRecord, ...],
) -> dict[str, list[WorkflowNodeRecord]]:
    candidates: dict[str, list[WorkflowNodeRecord]] = {role: [] for role in _ANCHOR_ROLE_PRIORITY}
    for record in target_records:
        for role in _anchor_roles(record):
            candidates.setdefault(role, []).append(record)
    return candidates


def _source_anchor_records(
    selected_slice: WorkflowSlice,
    source_records: tuple[WorkflowNodeRecord, ...],
) -> tuple[WorkflowNodeRecord, ...]:
    records_by_id = {record.node_id: record for record in source_records}
    anchor_ids = tuple(
        anchor_id
        for anchor_id in (selected_slice.entry_anchor, selected_slice.exit_anchor)
        if anchor_id is not None
    )
    anchors = tuple(records_by_id[anchor_id] for anchor_id in anchor_ids if anchor_id in records_by_id)
    if anchors:
        return anchors
    return tuple(record for record in source_records if _anchor_roles(record))


def _build_anchor_bindings(
    *,
    selected_slice: WorkflowSlice,
    source_records: tuple[WorkflowNodeRecord, ...],
    target_records: tuple[WorkflowNodeRecord, ...],
) -> tuple[dict[str, str], ...]:
    target_candidates = _target_anchor_candidates(target_records)
    bindings: list[dict[str, str]] = []
    used: set[tuple[str, str, str]] = set()

    for source_record in _source_anchor_records(selected_slice, source_records):
        for role in _anchor_roles(source_record):
            target_record = next(iter(target_candidates.get(role, ())), None)
            if target_record is None:
                continue
            key = (source_record.node_id, role, target_record.node_id)
            if key in used:
                continue
            used.add(key)
            bindings.append({
                "source_anchor": source_record.node_id,
                "target_anchor": target_record.node_id,
                "anchor_role": role,
                "source_class_type": source_record.class_type,
                "target_class_type": target_record.class_type,
                "source_socket": _anchor_socket_for_role(source_record, role),
                "target_socket": _anchor_socket_for_role(target_record, role),
            })

    return tuple(bindings)


_SOURCE_ID_PREFIX = "adapt_"


def _build_candidate_graph(
    target_graph: dict[str, Any],
    source_records: tuple[WorkflowNodeRecord, ...],
    anchor_bindings: tuple[dict[str, str], ...],
) -> dict[str, Any] | None:
    """Merge a validated source slice into the target graph.

    Preserves every target node, ID, and link.  Source nodes that participate
    in an anchor binding are *not* duplicated; their role is filled by the
    already-bound target anchor.  Remaining source nodes are copied in with
    deterministic non-colliding IDs and their input references are remapped to
    point at the corresponding target anchor or copied source node.

    Returns ``None`` if the inputs look malformed.
    """
    if not isinstance(target_graph, dict) or not anchor_bindings:
        return None

    candidate = copy.deepcopy(target_graph)
    existing_ids = {str(k) for k in candidate.keys() if isinstance(k, (str, int))}

    source_to_target: dict[str, str] = {}
    source_anchors: set[str] = set()
    for binding in anchor_bindings:
        if not isinstance(binding, dict):
            continue
        source_id = str(binding.get("source_anchor", ""))
        target_id = str(binding.get("target_anchor", ""))
        if source_id and target_id:
            source_anchors.add(source_id)
            if source_id not in source_to_target:
                source_to_target[source_id] = target_id

    def _allocate_id(source_id: str) -> str:
        preferred = f"{_SOURCE_ID_PREFIX}{source_id}"
        if preferred not in existing_ids:
            existing_ids.add(preferred)
            return preferred
        counter = 1
        while True:
            candidate_id = f"{preferred}_{counter}"
            if candidate_id not in existing_ids:
                existing_ids.add(candidate_id)
                return candidate_id
            counter += 1

    new_id_for_source: dict[str, str] = {
        record.node_id: _allocate_id(record.node_id)
        for record in source_records
        if record.node_id not in source_anchors
    }

    id_map = {**source_to_target, **new_id_for_source}

    def _remap_value(value: Any) -> Any:
        if isinstance(value, list | tuple) and len(value) == 2:
            ref_id, slot = value
            if isinstance(ref_id, (str, int)) and str(ref_id) in id_map:
                return [id_map[str(ref_id)], slot]
        return value

    for record in source_records:
        if record.node_id in source_anchors:
            continue
        new_id = new_id_for_source.get(record.node_id)
        if new_id is None:
            continue
        remapped_inputs = {
            key: _remap_value(val)
            for key, val in (record.inputs or {}).items()
        }
        candidate[new_id] = {
            "class_type": record.class_type,
            "inputs": remapped_inputs,
        }

    return candidate


def _build_adaptation_plan(
    query: str,
    graph: dict | None,
    inspection: InspectionSummary | None,
    slices: tuple[WorkflowSlice, ...],
) -> PrecedentAdaptationPlan | None:
    """Build a conservative :class:`PrecedentAdaptationPlan` or ``None``.

    When no precedent slices were found, returns ``None`` — the caller
    should produce an explicit none-found warning.  When slices exist,
    returns a minimal plan that selects the first slice with empty
    bindings/rewires/edit-ops.  Full adaptation construction is deferred
    to a later sprint (SD3).
    """
    if not slices:
        return None

    selected_slice = slices[0]
    target_load = _normalize_target_graph(graph)
    anchor_bindings: tuple[dict[str, str], ...] = ()
    structural_validation = "not_evaluated"
    source_records: tuple[WorkflowNodeRecord, ...] = ()
    family_check_passed = False

    if target_load is not None:
        structural_validation = "fail"
        source_records = _selected_source_records(selected_slice)
        source_families = _detect_record_families(
            source_records,
            selected_slice.source_class_type,
            selected_slice.source_workflow_path,
            selected_slice.python_path,
        )
        target_families = (
            _detect_record_families(target_load.nodes, str(target_load.raw or ""))
            if target_load.ok else set()
        )
        family_check_passed = (
            bool(source_families)
            and bool(target_families)
            and bool(source_families & target_families)
        )
    candidate_graph: dict[str, Any] | None = None
    if target_load is not None and target_load.ok and source_records and family_check_passed:
        anchor_bindings = _build_anchor_bindings(
            selected_slice=selected_slice,
            source_records=source_records,
            target_records=target_load.nodes,
        )
        if anchor_bindings:
            structural_validation = "pass"
            candidate_graph = _build_candidate_graph(
                target_graph=graph,
                source_records=source_records,
                anchor_bindings=anchor_bindings,
            )

    return PrecedentAdaptationPlan(
        selected_slice=selected_slice,
        anchor_bindings=anchor_bindings,
        required_new_nodes=(),
        required_rewires=(),
        edit_ops=(),
        candidate_graph=candidate_graph,
        structural_validation=structural_validation,
        semantic_validation="not_evaluated",
    )


# ── Public API ───────────────────────────────────────────────────────────────


def research(
    query: str,
    *,
    task: str | None = None,
    graph: dict[str, Any] | None = None,
    hivemind_client: HivemindClient | None | object = _USE_DEFAULT,
    hivemind_timeout: float = _DEFAULT_HIVEMIND_TIMEOUT,
    web_search_client: WebSearchClient | None | object = _USE_DEFAULT,
    web_search_timeout: float = _DEFAULT_WEB_SEARCH_TIMEOUT,
    local_limit: int = 10,
) -> ResearchResult:
    """Execute the full research phase: local corpus + external fallback.

    Local-corpus search always runs first and is deterministic (no model calls).
    Hivemind is injectable: by default the built-in Supabase/PostgREST client
    runs; when *hivemind_client* is explicitly ``None``, that tier is skipped.
    Web search is a separate best-effort evidence tier when enabled. External
    timeouts and errors become warnings — the executor never fails because
    research endpoints are unreachable.

    Parameters
    ----------
    query:
        The user's natural-language request.
    task:
        Optional task hint (e.g. ``"t2v"``) for scorer alias expansion.
    hivemind_client:
        Injectable direct-HTTP client callable ``(query: str, timeout: float) → dict``.
        By default, uses ``_default_hivemind_client``.  Pass ``None`` to skip
        external Hivemind research.
    hivemind_timeout:
        Timeout in seconds for the Hivemind HTTP request.  Non-positive values
        disable Hivemind.
    web_search_client:
        Injectable no-key web-search client. By default, uses DuckDuckGo HTML.
        Pass ``None`` to disable this tier.
    web_search_timeout:
        Timeout in seconds for the web-search fallback.
    local_limit:
        Maximum number of top-scoring local results to include.

    Returns
    -------
    ResearchResult
        Deterministic, local-corpus-first results with compactly normalized
        sources and non-fatal Hivemind warnings.
    """
    # ── Phase 1: deterministic local corpus (best-effort) ─────────────────
    #
    # The external tiers below are intentionally independent of the local
    # index. A missing or stale search corpus should degrade local precedent
    # recall, not prevent Hivemind/web lookup entirely.
    if local_limit <= 0:
        sources = []
        warnings = []
        warning_details = []
    else:
        try:
            local = run_local_research(query, task=task, limit=local_limit)
        except Exception as exc:  # noqa: BLE001 - research is best-effort
            sources = []
            warnings = [f"local corpus: {type(exc).__name__}: {exc}"]
            warning_details = [warning_detail_from_exception(exc)]
        else:
            sources = list(local.sources)
            warnings = list(local.warnings)
            warning_details = [
                dict(detail) for detail in local.warning_details
            ]

    # ── Phase 2: injectable Hivemind (non-fatal on any failure) ───────────
    resolved_hivemind_client: HivemindClient | None
    if hivemind_client is _USE_DEFAULT:
        resolved_hivemind_client = _default_hivemind_client
    else:
        resolved_hivemind_client = hivemind_client  # type: ignore[assignment]

    resolved_web_client: WebSearchClient | None
    if web_search_client is _USE_DEFAULT:
        resolved_web_client = _default_web_search_client
    else:
        resolved_web_client = web_search_client  # type: ignore[assignment]

    if resolved_hivemind_client is not None and hivemind_timeout > 0:
        try:
            hivemind_sources = _run_hivemind_research(
                query, client=resolved_hivemind_client, timeout=hivemind_timeout
            )
        except HivemindError as exc:
            warnings.append(f"hivemind: {exc}")
            warning_details.append(warning_detail_from_exception(exc))
        except Exception as exc:
            warnings.append(f"hivemind (unexpected): {exc}")
            warning_details.append(warning_detail_from_exception(exc))
        else:
            # Merge Hivemind results after local. Do not suppress cross-tier
            # duplicates here; the edit agent should see what each source tier
            # produced and decide how much weight to give it.
            for hs in hivemind_sources:
                sources.append(hs)

    # ── Phase 3: no-key web research (best-effort, independent tier) ─────
    if (
        resolved_web_client is not None
        and web_search_timeout > 0
    ):
        try:
            web_sources, web_warnings = _run_web_search(
                query, client=resolved_web_client, timeout=web_search_timeout
            )
        except WebSearchError as exc:
            warnings.append(f"web search: {exc}")
            warning_details.append(warning_detail_from_exception(exc))
        except Exception as exc:
            warnings.append(f"web search (unexpected): {exc}")
            warning_details.append(warning_detail_from_exception(exc))
        else:
            warnings.extend(f"web search: {warning}" for warning in web_warnings)
            if not web_sources:
                warnings.append("web search: no results")
            for ws in web_sources:
                sources.append(ws)

    # Re-sort: local results first, then Hivemind, then web, each by score.
    source_order = {"hivemind_workflow": 1, "hivemind": 2, "web": 3}
    sources.sort(
        key=lambda s: (source_order.get(str(s.get("source")), 0), -s.get("score", 0))
    )

    # Rebuild summary with merged results.
    summary = _build_summary(tuple(sources))

    # ── Build structured precedent output (SD2) ──────────────────────────
    # Graph is not directly available in research(), so inspection and
    # adaptation plan are left empty.  The executor wires graph inspection
    # Thread the attached target graph into adaptation planning (T14).
    precedent_slices = _build_precedent_slices(tuple(sources))
    adaptation_plan = _build_adaptation_plan(
        query=query,
        graph=graph,
        inspection=None,
        slices=precedent_slices,
    )
    precedent_warnings: list[str] = []
    if not precedent_slices:
        precedent_warnings.append(
            "precedent research: no workflow/template precedents found in "
            "local corpus or Hivemind results"
        )

    return ResearchResult(
        summary=summary,
        sources=tuple(sources),
        warnings=tuple(list(warnings) + precedent_warnings),
        warning_details=tuple(warning_details),
        precedent_slices=precedent_slices,
        adaptation_plan=adaptation_plan,
    )


__all__ = [
    "HivemindClient",
    "HivemindError",
    "WebSearchClient",
    "WebSearchError",
    "_build_adaptation_plan",
    "_build_inspection_summary",
    "_build_precedent_slices",
    "_default_hivemind_client",
    "_default_web_search_client",
    "research",
    "run_local_research",
]
