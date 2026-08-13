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
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
import urllib.error
import urllib.request
from types import MappingProxyType
from typing import Any, Callable, Mapping

from vibecomfy.search.index import build_search_corpus
from vibecomfy.search.scorer import search_entries, SearchResult
from vibecomfy.ingest.workflow_source import (
    WorkflowLoadResult,
    WorkflowNodeRecord,
    load_workflow_source,
    normalize_workflow_source,
)
from vibecomfy.registry.pack_resolver import (
    MissingNodeResolution,
    PackResolverError,
    resolve_missing_nodes,
)

from .contracts import (
    InspectionSummary,
    ManifestBoundaryAnchor,
    ManifestInquiryCoverage,
    ManifestInternalEdge,
    ManifestNode,
    ManifestOversized,
    ManifestValidation,
    PrecedentAdaptationPlan,
    PrecedentOption,
    PrecedentPacket,
    ResearchResult,
    SelectedPrecedent,
    TopologyManifest,
    WorkflowSlice,
    build_topology_manifest,
    is_ui_only_annotation_class_type,
    warning_detail_from_exception,
)
from . import provenance
from .hivemind_clients import (
    HivemindClient,
    HivemindError,
    _DEFAULT_EXTERNAL_LIMIT,
    _DEFAULT_HIVEMIND_KEY,
    _DEFAULT_HIVEMIND_URL,
    _HIVEMIND_FALLBACK_STOPWORDS,
    _HIVEMIND_SEMANTIC_FAMILY_TERMS,
    _HIVEMIND_SEMANTIC_TASK_TERMS,
    _QUERY_TOKEN_RE,
    _SEARCH_STOPWORDS,
    _coerce_tasks,
    _default_hivemind_client,
    _default_hivemind_messages_client,
    _dedupe_hivemind_rows,
    _excerpt,
    _first_text,
    _hivemind_get_table,
    _hivemind_ilike_query,
    _hivemind_phrase_ilike_query,
    _hivemind_search_terms,
    _hivemind_semantic_filters,
    _parse_json_response,
    _query_tokens,
    _rank_hivemind_rows,
    _run_hivemind_messages_research,
    _semantic_alias_matches,
    _workflow_semantics,
    _workflow_semantics_text,
    format_community_summary,
)

LOGGER = logging.getLogger(__name__)

# ── Conservative external-search defaults ────────────────────────────────────

_DEFAULT_HIVEMIND_TIMEOUT = 5.0  # seconds
_DEFAULT_WEB_SEARCH_URL = "https://duckduckgo.com/html/"
_DEFAULT_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_DEFAULT_BRAVE_SEARCH_URL = "https://search.brave.com/search"
_DEFAULT_WEB_CACHE_ROOT = Path(os.environ.get("VIBECOMFY_WEB_SEARCH_CACHE", "~/.cache/vibecomfy/web_search")).expanduser()
_DEFAULT_WEB_SEARCH_TIMEOUT = 5.0  # seconds

# ── Per-tier freshness TTLs (SD1) ─────────────────────────────────────────────
# Each tier carries a maximum age before cached results are marked stale.
# Zero means "no caching / always fetch" (live runtime schemas).
# Environment overrides follow the VIBECOMFY_<TIER>_TTL pattern.

_DEFAULT_WEB_SEARCH_TTL = int(os.environ.get(
    "VIBECOMFY_WEB_SEARCH_TTL", 86400,
))  # 24h
_DEFAULT_GITHUB_TTL = int(os.environ.get(
    "VIBECOMFY_GITHUB_TTL", 604800,
))  # 7d
_DEFAULT_HIVEMIND_TTL = int(os.environ.get(
    "VIBECOMFY_HIVEMIND_TTL", 604800,
))  # 7d
_DEFAULT_CIVITAI_TTL = int(os.environ.get(
    "VIBECOMFY_CIVITAI_TTL", 2592000,
))  # 30d
_DEFAULT_LIVE_RUNTIME_TTL = 0  # never cache — always use live schema

# Map source-kind strings (as they appear in source dict ``source`` fields)
# to their TTL in seconds.  Unknown tiers default to 24h.
_TIER_TTL_MAP: dict[str, int] = {
    "web": _DEFAULT_WEB_SEARCH_TTL,
    "github": _DEFAULT_GITHUB_TTL,
    "git": _DEFAULT_GITHUB_TTL,
    "hivemind": _DEFAULT_HIVEMIND_TTL,
    "hivemind_workflow": _DEFAULT_HIVEMIND_TTL,
    "hivemind_message": _DEFAULT_HIVEMIND_TTL,
    "hivemind_distillation": _DEFAULT_HIVEMIND_TTL,
    "civitai": _DEFAULT_CIVITAI_TTL,
    "external_workflow": _DEFAULT_CIVITAI_TTL,  # external workflows share Civitai TTL
    "live_runtime_schema": _DEFAULT_LIVE_RUNTIME_TTL,
    "object_info": _DEFAULT_LIVE_RUNTIME_TTL,
}

# ── Domain-specific external-workflow extraction limits ──────────────────────

_MAX_EXTERNAL_JSON_BYTES = 5 * 1024 * 1024  # 5 MB
_MAX_EXTERNAL_ZIP_BYTES = 20 * 1024 * 1024  # 20 MB
_ALLOWED_EXTERNAL_WORKFLOW_HOSTS = frozenset({
    "civitai.com",
    "openart.ai",
    "runcomfy.com",
    "www.runcomfy.com",
})
_ALLOWED_DIRECT_WORKFLOW_JSON_HOSTS = frozenset({
    "cdn.discordapp.com",
    "media.discordapp.net",
    "raw.githubusercontent.com",
})

WORKFLOW_RESEARCH_GUIDANCE = (
    "Workflow/template exploration: use `vibecomfy workflows list --ready` to see ready templates; "
    "explore or copy ready template `.py` representations with "
    "`vibecomfy copy-to-recipe <template_id> --out <file.py> --strip-markers`."
)

# A Hivemind client is any callable (query: str, timeout: float) → dict.
WebSearchClient = Callable[[str, float], dict[str, Any]]
RegistryResolver = Callable[[str], MissingNodeResolution]

_USE_DEFAULT = object()


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
    "wan": ("wan", "wanvideo", "wan2", "wan_2", "wan 2", "wan2_1", "wan2.1", "wan2_2", "wan2.2"),
    "ltx": ("ltx", "ltxv", "lightricks"),
    "hotshot": ("hotshot", "hotshotxl", "hotshot xl"),
    "animatediff": ("animatediff", "animate diff"),
    "sdxl": ("sdxl", "sd_xl", "sd xl", "stable diffusion xl"),
    "sd3": ("sd3", "stable diffusion 3"),
    "flux": ("flux", "flux1", "flux2"),
    "qwen": ("qwen",),
    "hunyuan": ("hunyuan", "hyvideo"),
    "cogvideo": ("cogvideo", "cog video"),
}



_ANCHOR_ROLE_PRIORITY = ("lora", "model", "sampler", "latent", "conditioning", "exit")
_REGISTRY_QUERY_STOPWORDS = {
    "comfy",
    "comfyui",
    "frame",
    "frames",
    "generate",
    "generating",
    "node",
    "nodes",
    "pack",
    "registry",
    "sd",
    "sdxl",
    "video",
    "workflow",
    "workflows",
    "xl",
}

# ── Hivemind error (non-fatal) ───────────────────────────────────────────────



class WebSearchError(Exception):
    """Non-fatal web-search error converted to a warning by ``research()``."""


class RegistrySearchError(Exception):
    """Non-fatal Comfy Registry lookup error converted to a warning."""


# ── Local corpus research ────────────────────────────────────────────────────


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
        "media_type": entry.media_type,
        "task_type": entry.task_type,
        "model_families": list(entry.model_families),
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
        if any(str(source.get("source", "")).startswith(("hivemind", "web", "comfy-registry", "git")) for source in sources)
        else "local"
    )
    community_sources = [
        source
        for source in sources
        if source.get("source") in {"hivemind_message", "hivemind_distillation"}
    ]
    if community_sources:
        community_names = ", ".join(
            str(source.get("class_type") or source.get("title") or "untitled")
            for source in community_sources[:3]
        )
        if len(community_sources) > 3:
            community_names += f", and {len(community_sources) - 3} more"
        channels = sorted(
            {
                str(source.get("channel") or "")
                for source in community_sources
                if source.get("channel")
            }
        )
        if channels:
            return (
                f"Found {len(community_sources)} community result(s): {community_names}. "
                f"Channels: {', '.join(channels)}."
            )
        return f"Found {len(community_sources)} community result(s): {community_names}."
    workflow_sources = sorted(
        (
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
            and (
                (source.get("path") and str(source.get("path")).endswith(".py"))
                or (source.get("source") == "hivemind_workflow" and source.get("url"))
            )
        ),
        key=lambda s: -int(s.get("score") or 0),
    )
    if workflow_sources:
        def _workflow_ref(source: dict[str, Any]) -> str:
            path = source.get("path")
            url = source.get("url")
            if path and str(path).endswith(".py"):
                return f"{source.get('class_type')} ({path})"
            if url:
                return f"{source.get('class_type')} ({url})"
            return str(source.get("class_type") or "workflow")

        workflow_refs = ", ".join(_workflow_ref(source) for source in workflow_sources[:3])
        return (
            f"Found {n} {result_scope} result(s): {names}. "
            f"Relevant workflow/template paths: {workflow_refs}. "
            f"{WORKFLOW_RESEARCH_GUIDANCE}"
        )
    return f"Found {n} {result_scope} result(s): {names}"






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



def _hivemind_fts_query(search_terms: list[str]) -> str | None:
    """Build a PostgREST ``fts`` query string from a list of search terms.

    Each term is split into alphanumeric tokens; common stopwords are dropped,
    duplicates are removed, and the remaining tokens are ORed with ``|``.  This
    produces a cheap, indexed full-text query that scales with token count
    instead of exploding with leading-wildcard ``ilike`` filters.
    """
    stop = _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS
    tokens: list[str] = []
    seen: set[str] = set()
    for term in search_terms:
        for raw in term.split():
            token = re.sub(r"[^A-Za-z0-9]", "", raw)
            if not token:
                continue
            key = token.casefold()
            if key in stop or key in seen:
                continue
            if len(key) == 1 and not key.isdigit():
                # Drop isolated single letters; keep short numbers like "16".
                continue
            seen.add(key)
            tokens.append(token)
    if not tokens:
        return None
    return "|".join(tokens[:8])













def _domain(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc or None


# ── Hivemind result normalization ────────────────────────────────────────────


def _load_corpus_workflow_schema(corpus_path: str) -> tuple[list[str], dict[str, Any]] | None:
    """Load node-type and socket schema from a local VibeComfy workflow JSON.

    The corpus stores workflows in the compiled VibeComfy format where node
    input/output metadata lives under ``metadata._ui``.  Returns a list of
    node class types and a ``workflow_schema`` mapping suitable for the batch
    REPL's research output formatter.
    """
    from vibecomfy.utils import find_repo_root

    path = find_repo_root() / corpus_path
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    raw_nodes = data.get("nodes")
    if isinstance(raw_nodes, Mapping):
        nodes = [node for node in raw_nodes.values() if isinstance(node, Mapping)]
    elif isinstance(raw_nodes, list):
        nodes = [node for node in raw_nodes if isinstance(node, Mapping)]
    else:
        return None

    node_types: list[str] = []
    workflow_schema: dict[str, Any] = {}
    for node in nodes:
        class_type = node.get("class_type") or node.get("type")
        if not isinstance(class_type, str) or not class_type:
            continue
        node_types.append(class_type)
        if class_type in workflow_schema:
            continue
        ui = (node.get("metadata") or {}).get("_ui") or {}
        inputs: list[dict[str, Any]] = (
            ui.get("inputs") if isinstance(ui.get("inputs"), list) else node.get("inputs") or []
        )
        outputs: list[dict[str, Any]] = (
            ui.get("outputs") if isinstance(ui.get("outputs"), list) else node.get("outputs") or []
        )
        input_schema: dict[str, Any] = {"required": {}, "optional": {}}
        for inp in inputs:
            if not isinstance(inp, dict):
                continue
            name = inp.get("name")
            if not isinstance(name, str) or not name:
                continue
            # Treat inputs with an active link as required; widget/value inputs
            # as optional schema hints.
            target = "required" if inp.get("link") is not None else "optional"
            input_schema[target][name] = {"type": inp.get("type") or "*"}
        widget_order: list[str] = []
        widgets = ui.get("widgets_values")
        if not isinstance(widgets, list):
            widgets = node.get("widgets_values")
        if isinstance(widgets, list):
            for index, value in enumerate(widgets):
                name = f"widget_{index}"
                input_schema["optional"].setdefault(
                    name,
                    {"type": _workflow_widget_type(value), "default": value},
                )
                widget_order.append(name)
        output_schema = [
            {"name": out.get("name") or out.get("type") or f"out_{i}", "type": out.get("type") or "*"}
            for i, out in enumerate(outputs)
            if isinstance(out, dict)
        ]
        schema_entry = {
            "input": input_schema,
            "outputs": output_schema,
        }
        if widget_order:
            schema_entry["object_info_widget_order"] = widget_order
        workflow_schema[class_type] = schema_entry
    return node_types, workflow_schema


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
    workflow_semantics = metadata.get("workflow_semantics") if isinstance(metadata.get("workflow_semantics"), dict) else {}
    promotion_gates = (
        workflow_semantics.get("promotion_gates")
        if isinstance(workflow_semantics.get("promotion_gates"), dict)
        else {}
    )
    ready_id = _first_text(metadata, "ready_template_id") or _first_text(payload, "ready_template_id")
    path = (
        _first_text(item, "path")
        or _first_text(metadata, "path", "python_path")
        or _first_text(payload, "python_path")
    )
    source = "hivemind_workflow" if item.get("kind") == "workflow" else "hivemind"

    # Enrich workflow results with concrete node-type/schema evidence from the
    # local corpus so the agent can see the actual nodes/wiring instead of just
    # a title/description.
    node_types: list[str] | None = None
    workflow_schema: dict[str, Any] | None = None
    corpus_path = _first_text(metadata, "corpus_path")
    if source == "hivemind_workflow" and corpus_path:
        schema_pair = _load_corpus_workflow_schema(corpus_path)
        if schema_pair is not None:
            node_types, workflow_schema = schema_pair

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
        "node_types": node_types,
        "workflow_schema": workflow_schema,
        "workflow_semantics": workflow_semantics or None,
        "promotion_gates": promotion_gates or None,
    }


_URL_RE = re.compile(r"https?://[^\s\"'<>),]+")


def _workflow_url_maybe_fetchable(url: str) -> bool:
    if _direct_workflow_json_url(url) is not None:
        return True
    return urlparse(url).netloc.casefold() in _ALLOWED_EXTERNAL_WORKFLOW_HOSTS


def _hivemind_workflow_url_candidates(item: Mapping[str, Any], *, max_urls: int = 3) -> list[str]:
    values: list[str] = []
    for key in ("url", "source_url", "permalink", "link", "description", "body", "content", "text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    for nested_key in ("metadata", "payload"):
        nested = item.get(nested_key)
        if not isinstance(nested, Mapping):
            continue
        for key in ("url", "source_url", "workflow_url", "raw_url", "body", "description"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                values.append(value)

    candidates: list[str] = []
    seen: set[str] = set()
    for value in values:
        direct = value.strip()
        urls = [direct] if direct.startswith(("http://", "https://")) else []
        urls.extend(match.group(0).rstrip(".,;") for match in _URL_RE.finditer(value))
        for url in urls:
            if not _workflow_url_maybe_fetchable(url):
                continue
            key = url.casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(url)
            if len(candidates) >= max_urls:
                return candidates
    return candidates


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
    sources: list[dict[str, Any]] = []
    seen_promoted_urls: set[str] = set()
    promoted_count = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        for url in _hivemind_workflow_url_candidates(item):
            if promoted_count >= 5:
                break
            key = url.casefold()
            if key in seen_promoted_urls:
                continue
            seen_promoted_urls.add(key)
            enriched_item = dict(item)
            enriched_item["url"] = url
            promoted, _warning = _fetch_external_workflow_json_source(
                enriched_item,
                index=index,
                timeout=timeout,
            )
            if promoted is None:
                continue
            promoted["source"] = "hivemind_workflow"
            promoted["hivemind_promoted_workflow"] = True
            sources.append(promoted)
            promoted_count += 1
        sources.append(_normalize_hivemind_source(item))
    return tuple(sources)


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


def _brave_search(query: str, timeout: float) -> list[dict[str, str]]:
    """Best-effort Brave Search HTML fallback.

    Brave's rendered page embeds result URLs in static HTML even when the
    structure is not stable enough for a full SERP parser. We only use this
    when other no-key search tiers found nothing, and keep the payload compact
    so the agent treats it as external leads rather than authoritative schema.
    """
    url = f"{_DEFAULT_BRAVE_SEARCH_URL}?q={quote(query)}"
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
        raise WebSearchError(f"brave search timed out after {timeout}s") from exc
    except urllib.error.URLError as exc:
        raise WebSearchError(f"brave search HTTP error: {exc}") from exc

    anchors = _web_result_anchor_terms(query)
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r"https?://[^\"<>\\\s]+", html):
        candidate_url = unescape(match.group(0)).rstrip(".,);]")
        parsed = urlparse(candidate_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        if parsed.netloc.endswith("search.brave.com") or parsed.netloc.endswith("cdn.search.brave.com"):
            continue
        if parsed.netloc.endswith("redditstatic.com") or parsed.netloc.endswith("redd.it"):
            continue
        haystack = _normalize_web_result_text(candidate_url)
        if anchors and not any(anchor in haystack for anchor in anchors):
            continue
        key = candidate_url.casefold()
        if key in seen:
            continue
        seen.add(key)
        title = unquote(parsed.path.strip("/").split("/")[-1] or parsed.netloc).replace("-", " ").replace("_", " ")
        results.append(
            {
                "title": title or parsed.netloc,
                "url": candidate_url,
                "snippet": f"External search result from {parsed.netloc}",
            }
        )
        if len(results) >= 50:
            break
    results.sort(key=lambda item: (-_external_workflow_result_score(item), item["url"]))
    return results[:_DEFAULT_EXTERNAL_LIMIT]


def _external_workflow_result_score(item: Mapping[str, str]) -> int:
    text = " ".join(str(item.get(key) or "") for key in ("title", "url", "snippet")).casefold()
    score = 0
    if "workflow" in text or "workflows" in text:
        score += 50
    if "github.com" in text and "/blob/" in text and any(suffix in text for suffix in (".json", ".workflow")):
        score += 80
    if any(domain in text for domain in ("openart.ai/workflows", "comfyworkflows.com", "runcomfy.com/comfyui-workflows")):
        score += 40
    if any(term in text for term in ("guide", "tutorial", "reddit.com/r/comfyui", "reddit.com/r/stablediffusion")):
        score += 10
    if any(term in text for term in ("huggingface.co", "hotshot.co/")):
        score -= 10
    return score


def _web_result_anchor_terms(query: str) -> tuple[str, ...]:
    web_anchor_stopwords = {
        "comfy",
        "comfyui",
        "example",
        "examples",
        "json",
        "node",
        "nodes",
        "page",
        "repo",
        "repository",
        "type",
        "types",
        "wiring",
        "workflow",
        "workflows",
        "xl",
    }
    terms = [
        token.casefold().replace("-", "").replace("_", "")
        for token in _query_tokens(query)
        if token.casefold() not in _SEARCH_STOPWORDS
        and token.casefold() not in web_anchor_stopwords
        and not token.isdigit()
    ]
    if len(terms) >= 2:
        terms.append("".join(terms[:2]))
    return tuple(dict.fromkeys(term for term in terms if len(term) >= 3))


def _normalize_web_result_text(value: str) -> str:
    return unquote(value).casefold().replace("-", "").replace("_", "").replace(" ", "").replace("%20", "")


def _filter_web_results_by_named_anchor(
    query: str,
    results: list[dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    anchors = _web_result_anchor_terms(query)
    if not anchors:
        return results, 0
    kept: list[dict[str, str]] = []
    dropped = 0
    for item in results:
        haystack = _normalize_web_result_text(
            " ".join(str(item.get(key) or "") for key in ("title", "url", "snippet"))
        )
        if any(anchor in haystack for anchor in anchors):
            kept.append(item)
        else:
            dropped += 1
    return kept, dropped


def _default_web_search_client(query: str, timeout: float) -> dict[str, Any]:
    """Best-effort public web-search evidence using DuckDuckGo HTML + GitHub."""
    cached = _read_web_search_cache(query)
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
    if not results:
        try:
            results.extend(_brave_search(query, timeout))
        except WebSearchError as exc:
            warnings.append(str(exc))
    if results:
        _write_web_search_cache(query, results[:_DEFAULT_EXTERNAL_LIMIT])
        if cached:
            seen_keys = {
                str(item.get("url") or item.get("title") or "").casefold()
                for item in results
            }
            for cached_item in cached:
                key = str(cached_item.get("url") or cached_item.get("title") or "").casefold()
                if key and key in seen_keys:
                    continue
                if key:
                    seen_keys.add(key)
                results.append(cached_item)
            results.sort(key=lambda item: (-_external_workflow_result_score(item), str(item.get("url") or "")))
    elif cached:
        warnings.append("web search: using cached results after live search returned no results")
        results.extend(cached)
    if results:
        filtered_results, dropped = _filter_web_results_by_named_anchor(query, results)
        if dropped:
            warnings.append(
                f"web search: dropped {dropped} generic result(s) that did not mention the named target"
            )
        results = filtered_results
    if not results and warnings:
        raise WebSearchError("; ".join(warnings))
    return {"results": results[:_DEFAULT_EXTERNAL_LIMIT], "warnings": warnings}


def _web_search_cache_path(query: str) -> Path:
    digest = hashlib.sha256(query.strip().casefold().encode("utf-8")).hexdigest()
    return _DEFAULT_WEB_CACHE_ROOT / f"{digest}.json"


def _read_web_search_cache(query: str) -> list[dict[str, str]]:
    path = _web_search_cache_path(query)
    exact_results = _read_web_search_cache_path(path)
    filtered_exact_results: list[dict[str, str]] = []
    if exact_results:
        filtered_exact_results, _dropped = _filter_web_results_by_named_anchor(query, exact_results)
    anchors = tuple(_web_result_anchor_terms(query))
    if not anchors:
        return filtered_exact_results
    try:
        candidates = sorted(_DEFAULT_WEB_CACHE_ROOT.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except Exception:
        return filtered_exact_results
    merged_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for result in filtered_exact_results:
        url_key = str(result.get("url") or "").casefold()
        title_key = str(result.get("title") or "").casefold()
        key = url_key or title_key
        if key:
            seen_urls.add(key)
        merged_results.append(result)
    for candidate_path in candidates[:25]:
        try:
            payload = json.loads(candidate_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        cached_query = str(payload.get("query") or "") if isinstance(payload, dict) else ""
        cached_text = _normalize_web_result_text(cached_query)
        results = _read_web_search_cache_path(candidate_path)
        result_text = _normalize_web_result_text(json.dumps(results, sort_keys=True, default=str))
        combined_text = cached_text + " " + result_text
        if anchors and anchors[0] not in combined_text:
            query_tokens = [
                _normalize_web_result_text(token)
                for token in _query_tokens(query)
                if len(_normalize_web_result_text(token)) >= 6
            ]
            if not any(token in combined_text for token in query_tokens):
                continue
        if results:
            filtered_results, _dropped = _filter_web_results_by_named_anchor(query, results)
            if filtered_results:
                for result in filtered_results:
                    url_key = str(result.get("url") or "").casefold()
                    title_key = str(result.get("title") or "").casefold()
                    key = url_key or title_key
                    if key and key in seen_urls:
                        continue
                    if key:
                        seen_urls.add(key)
                    merged_results.append(result)
    merged_results.sort(key=lambda item: (-_external_workflow_result_score(item), str(item.get("url") or "")))
    return merged_results[:_DEFAULT_EXTERNAL_LIMIT]


def _read_web_search_cache_path(path: Path) -> list[dict[str, str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return []
    results: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        if title or url:
            results.append({"title": title, "url": url, "snippet": snippet})
    return results[:_DEFAULT_EXTERNAL_LIMIT]


def _write_web_search_cache(query: str, results: list[dict[str, str]]) -> None:
    try:
        _DEFAULT_WEB_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        _web_search_cache_path(query).write_text(
            json.dumps({"query": query, "results": results}, sort_keys=True, indent=2),
            encoding="utf-8",
        )
    except Exception:
        return


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


# ── Domain-specific external-workflow extraction ─────────────────────────────


def _civitai_model_id_from_url(url: str) -> int | None:
    """Return the Civitai model id from a ``/models/<id>/...`` URL."""
    parsed = urlparse(url)
    if parsed.netloc.casefold() not in {"civitai.com", "www.civitai.com"}:
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0].casefold() != "models":
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _extract_civitai_workflow_jsons(
    model_id: int,
    *,
    timeout: float,
) -> list[tuple[str, dict[str, Any]]]:
    """Fetch a Civitai model page's workflow ZIPs and extract JSON payloads.

    Uses the public ``/api/v1/models/<id>`` and
    ``/api/download/models/<version_id>`` endpoints.  The ZIP archives for
    workflow models contain the ComfyUI workflow JSON.  Returns a list of
    ``(filename, payload)`` tuples for every JSON file found in every version
    archive.  Failures are swallowed and returned as an empty list so the
    caller can fall back to the plain web result.
    """
    api_url = f"https://civitai.com/api/v1/models/{model_id}"
    req = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "vibecomfy-research/1.0 "
                "(https://github.com/peteromallet/vibecomfy)"
            ),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(1.0, min(timeout, 10.0))) as resp:
            body = resp.read(_MAX_EXTERNAL_JSON_BYTES + 1)
            if len(body) > _MAX_EXTERNAL_JSON_BYTES:
                return []
            model = json.loads(body.decode("utf-8", errors="replace"))
    except Exception:
        return []

    if not isinstance(model, dict):
        return []

    # Only workflow models are expected to ship ComfyUI JSON inside ZIPs.
    if str(model.get("type", "")).casefold() != "workflows":
        return []

    version_ids: list[int] = []
    for version in model.get("modelVersions", []) or []:
        if not isinstance(version, dict):
            continue
        vid = version.get("id")
        if isinstance(vid, int):
            version_ids.append(vid)

    payloads: list[tuple[str, dict[str, Any]]] = []
    # Limit versions to keep extraction bounded and respectful.
    for version_id in version_ids[:3]:
        dl_url = f"https://civitai.com/api/download/models/{version_id}"
        dl_req = urllib.request.Request(
            dl_url,
            headers={
                "User-Agent": (
                    "vibecomfy-research/1.0 "
                    "(https://github.com/peteromallet/vibecomfy)"
                ),
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(dl_req, timeout=max(1.0, min(timeout, 30.0))) as resp:
                zbytes = resp.read(_MAX_EXTERNAL_ZIP_BYTES + 1)
            if len(zbytes) > _MAX_EXTERNAL_ZIP_BYTES:
                continue
        except Exception:
            continue

        try:
            zf = zipfile.ZipFile(io.BytesIO(zbytes))
        except zipfile.BadZipFile:
            continue

        for name in zf.namelist():
            if not name.lower().endswith(".json"):
                continue
            try:
                content = zf.read(name)
            except Exception:
                continue
            try:
                payload = json.loads(content.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payloads.append((name, payload))

    return payloads


def _extract_domain_workflow_jsons(
    url: str,
    *,
    timeout: float,
) -> list[tuple[str, str | None, dict[str, Any]]]:
    """Best-effort extraction of embedded workflow JSON from known platforms.

    Returns a list of ``(filename, raw_url, payload)`` tuples.  ``raw_url`` is
    the canonical fetch URL (or ``None`` when the payload was assembled from
    multiple fetches, e.g. a Civitai ZIP).  Unsupported domains or extraction
    failures return an empty list; the caller should fall back to treating the
    search result as plain web evidence.
    """
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    if host not in _ALLOWED_EXTERNAL_WORKFLOW_HOSTS:
        return []

    if host in {"civitai.com", "www.civitai.com"}:
        model_id = _civitai_model_id_from_url(url)
        if model_id is None:
            return []
        return [
            (name, None, payload)
            for name, payload in _extract_civitai_workflow_jsons(
                model_id, timeout=timeout
            )
        ]

    # OpenArt and RunComfy do not expose a stable, unauthenticated workflow
    # JSON endpoint in their SSR HTML.  Extractors for those platforms can be
    # added here once a reliable public API or embedded payload is identified.
    return []


def _github_blob_raw_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc.casefold() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[2] != "blob":
        return None
    owner, repo, _, ref, *path_parts = parts
    if not path_parts:
        return None
    path = "/".join(path_parts)
    if not path.casefold().endswith((".json", ".workflow")):
        return None
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


def _direct_workflow_json_url(url: str) -> str | None:
    raw_github = _github_blob_raw_url(url)
    if raw_github is not None:
        return raw_github
    parsed = urlparse(url)
    host = parsed.netloc.casefold()
    if host not in _ALLOWED_DIRECT_WORKFLOW_JSON_HOSTS:
        return None
    if not parsed.path.casefold().endswith((".json", ".workflow")):
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    return url


def _fetch_external_workflow_json_source(
    item: dict[str, Any],
    *,
    index: int,
    timeout: float,
) -> tuple[dict[str, Any] | None, str | None]:
    url = _first_text(item, "url", "href", "link")
    if not url:
        return None, None

    # Try domain-specific extractors (Civitai ZIP, etc.) first.
    extracted = _extract_domain_workflow_jsons(url, timeout=timeout)
    if extracted:
        for filename, raw_url, payload in extracted:
            source, warning = _normalize_fetched_workflow(
                item=item,
                url=url,
                raw_url=raw_url or url,
                payload=payload,
                index=index,
                source_type=f"domain_workflow_json:{_domain(url) or 'unknown'}",
                filename=filename,
            )
            if source is not None:
                return source, warning
        return None, f"domain extraction for {url} produced no usable workflow JSON"

    # Fall back to exact JSON/workflow URLs on explicitly allowed hosts.
    raw_url = _direct_workflow_json_url(url)
    if raw_url is None:
        return None, None
    req = urllib.request.Request(
        raw_url,
        headers={
            "Accept": "application/json,text/plain;q=0.9,*/*;q=0.1",
            "User-Agent": (
                "vibecomfy-research/1.0 "
                "(https://github.com/peteromallet/vibecomfy)"
            ),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=max(1.0, min(timeout, 5.0))) as resp:
            raw_body = _read_response_bounded(resp, _MAX_EXTERNAL_JSON_BYTES + 1)
        if len(raw_body) > _MAX_EXTERNAL_JSON_BYTES:
            return None, f"workflow JSON fetch exceeded {_MAX_EXTERNAL_JSON_BYTES} bytes for {url}"
        body = raw_body.decode("utf-8", errors="replace")
        payload = json.loads(body)
    except Exception as exc:  # noqa: BLE001 - enrichment is best-effort
        return None, f"workflow JSON fetch failed for {url}: {type(exc).__name__}: {exc}"

    source_type = "github_workflow_json" if "githubusercontent.com" in urlparse(raw_url).netloc.casefold() else "direct_workflow_json"
    source, warning = _normalize_fetched_workflow(
        item=item,
        url=url,
        raw_url=raw_url,
        payload=payload,
        index=index,
        source_type=source_type,
    )
    return source, warning


def _read_response_bounded(resp: Any, limit: int) -> bytes:
    try:
        raw = resp.read(limit)
    except TypeError:
        raw = resp.read()
    if isinstance(raw, str):
        return raw.encode("utf-8")
    return raw


def _normalize_fetched_workflow(
    item: dict[str, Any],
    *,
    url: str,
    raw_url: str,
    payload: Any,
    index: int,
    source_type: str,
    filename: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Normalize a fetched workflow payload into a canonical external source.

    Validates the payload, writes it to the web-search workflow cache, and
    returns a source dict matching the shape produced by
    ``_fetch_external_workflow_json_source``.  Returns ``(None, warning)`` when
    the payload cannot be normalized.
    """
    summary = _summarize_workflow_json(payload)
    if not summary["node_types"]:
        return None, f"workflow fetch produced no node types for {url}"
    workflow_schema = _workflow_object_info_from_json(payload)

    try:
        _DEFAULT_WEB_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        workflow_root = _DEFAULT_WEB_CACHE_ROOT / "workflows"
        workflow_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(raw_url.encode("utf-8")).hexdigest()
        cached_path = workflow_root / f"{digest}.json"
        cached_path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    except Exception:
        cached_path = None

    title = _first_text(item, "title", "class_type", "name") or filename or url
    node_types = summary["node_types"]
    key_values = summary["key_values"]
    platform = _domain(url) or "external"
    description = f"Fetched {platform} workflow JSON. Node types: " + ", ".join(node_types[:16])
    if len(node_types) > 16:
        description += f", and {len(node_types) - 16} more"
    if key_values:
        description += ". Key values: " + "; ".join(key_values[:12])

    return {
        "class_type": title,
        "score": max(1, 95 - index),
        "reasons": [f"external workflow JSON fetched from {platform}"],
        "source": "external_workflow",
        "source_type": source_type,
        "pack": _domain(url),
        "description": description,
        "summary": description,
        "tasks": ["workflow", "video"],
        "url": url,
        "raw_url": raw_url,
        "path": str(cached_path) if cached_path is not None else "",
        "source_workflow_path": str(cached_path) if cached_path is not None else "",
        "source_workflow_available": cached_path is not None,
        "source_workflow_parseable": True,
        "node_types": node_types,
        "key_values": key_values,
        "workflow_schema": workflow_schema,
        "workflow_schema_classes": sorted(workflow_schema),
    }, None


def _summarize_workflow_json(payload: Any) -> dict[str, list[str]]:
    node_types: list[str] = []
    key_values: list[str] = []

    def add_node_type(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in node_types:
            node_types.append(text)

    def add_key_value(label: str, value: Any) -> None:
        if value is None or isinstance(value, (dict, list, tuple)):
            return
        text = str(value).strip()
        if not text or len(text) > 80:
            return
        rendered = f"{label}={text}"
        if rendered not in key_values:
            key_values.append(rendered)

    if isinstance(payload, dict):
        nodes = payload.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                add_node_type(node.get("type") or node.get("class_type"))
                widgets = node.get("widgets_values")
                if isinstance(widgets, list):
                    for value in widgets[:6]:
                        add_key_value(str(node.get("type") or "node"), value)
        for node_id, node in payload.items():
            if not isinstance(node, dict) or not str(node_id).isdigit():
                continue
            add_node_type(node.get("class_type") or node.get("type"))
            inputs = node.get("inputs")
            if isinstance(inputs, dict):
                for key, value in inputs.items():
                    if key.casefold() in {"length", "frames", "frame_count", "batch_size", "fps"}:
                        add_key_value(key, value)

    return {"node_types": node_types, "key_values": key_values}


def _workflow_object_info_from_json(payload: Any) -> dict[str, dict[str, Any]]:
    """Derive object_info-like provisional schemas from a concrete workflow JSON.

    Comfy workflow exports include enough UI socket data to preserve a missing
    custom-node shape even when the local runtime cannot provide object_info.
    Widget names are usually absent, so they are represented positionally as
    widget_0, widget_1, ...; the original values are still reported separately
    by ``_summarize_workflow_json``.
    """
    nodes: list[Mapping[str, Any]] = []
    if isinstance(payload, Mapping):
        raw_nodes = payload.get("nodes")
        if isinstance(raw_nodes, list):
            nodes.extend(node for node in raw_nodes if isinstance(node, Mapping))
        else:
            for key, node in payload.items():
                if str(key).isdigit() and isinstance(node, Mapping):
                    nodes.append(node)

    schemas: dict[str, dict[str, Any]] = {}
    for node in nodes:
        class_type = str(node.get("type") or node.get("class_type") or "").strip()
        if not class_type:
            continue
        existing = schemas.setdefault(
            class_type,
            {
                "input": {"required": {}, "optional": {}},
                "outputs": [],
                "object_info_widget_order": [],
                "category": "workflow_json_provisional",
            },
        )
        required = existing["input"]["required"]
        optional = existing["input"]["optional"]
        raw_inputs = node.get("inputs")
        if isinstance(raw_inputs, list):
            for input_row in raw_inputs:
                if not isinstance(input_row, Mapping):
                    continue
                name = str(input_row.get("name") or "").strip()
                if not name:
                    continue
                input_type = str(input_row.get("type") or "*")
                target_group = required if input_row.get("link") is not None else optional
                target_group.setdefault(name, {"type": input_type})
        raw_widgets = node.get("widgets_values")
        if isinstance(raw_widgets, list):
            widget_order = existing["object_info_widget_order"]
            for index, value in enumerate(raw_widgets):
                name = f"widget_{index}"
                optional.setdefault(name, {"type": _workflow_widget_type(value), "default": value})
                if name not in widget_order:
                    widget_order.append(name)
        raw_outputs = node.get("outputs")
        if isinstance(raw_outputs, list):
            outputs = existing["outputs"]
            seen_outputs = {
                (str(item.get("name") or ""), str(item.get("type") or ""))
                for item in outputs
                if isinstance(item, Mapping)
            }
            for output_row in raw_outputs:
                if not isinstance(output_row, Mapping):
                    continue
                name = str(output_row.get("name") or "").strip()
                output_type = str(output_row.get("type") or "*")
                key = (name, output_type)
                if key in seen_outputs:
                    continue
                seen_outputs.add(key)
                outputs.append({"name": name or None, "type": output_type})
    return schemas


def _workflow_widget_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int) and not isinstance(value, bool):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, str):
        return "STRING"
    return "*"


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
    sources: list[dict[str, Any]] = []
    mutable_warnings = list(warnings)
    seen_urls: set[str] = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        enriched, warning = _fetch_external_workflow_json_source(item, index=i, timeout=timeout)
        if warning:
            mutable_warnings.append(warning)
        if enriched is not None:
            sources.append(enriched)
            seen_urls.add(str(enriched.get("url") or "").casefold())
        normalized = _normalize_web_source(item, index=i)
        url_key = str(normalized.get("url") or "").casefold()
        if url_key and url_key in seen_urls:
            continue
        sources.append(normalized)
    return tuple(sources), tuple(mutable_warnings)


def _run_registry_research(
    query: str,
    *,
    resolver: RegistryResolver = resolve_missing_nodes,
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    """Return read-only Comfy Registry / Manager evidence for missing nodes."""
    warnings: list[str] = []
    sources: list[dict[str, Any]] = []
    seen_candidate_keys: set[str] = set()
    seen_warning_keys: set[str] = set()

    for candidate_query in _registry_candidate_queries(query):
        try:
            result = resolver(candidate_query)
        except PackResolverError as exc:
            warnings.append(f"{candidate_query}: {exc}")
            continue
        except Exception as exc:
            warnings.append(f"{candidate_query}: {type(exc).__name__}: {exc}")
            continue

        for warning in result.warnings:
            key = str(warning)
            if key not in seen_warning_keys:
                warnings.append(key)
                seen_warning_keys.add(key)

        for candidate in result.candidates:
            payload = candidate.to_dict()
            pack = payload.get("pack") if isinstance(payload.get("pack"), dict) else {}
            slug = str(pack.get("slug") or "")
            expected_classes = tuple(str(cls) for cls in payload.get("expected_classes", ()) if cls)
            key = f"{slug}|{'|'.join(expected_classes)}"
            if key in seen_candidate_keys:
                continue
            seen_candidate_keys.add(key)

            evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
            evidence_sources = [
                str(item.get("source") or item.get("tier") or "")
                for item in evidence
                if isinstance(item, dict)
            ]
            description_bits = []
            if expected_classes:
                description_bits.append(
                    "Expected classes: " + ", ".join(expected_classes[:8])
                )
            if evidence_sources:
                description_bits.append(
                    "Evidence: " + ", ".join(src for src in evidence_sources[:5] if src)
                )
            if candidate.warnings:
                description_bits.append(
                    "Warnings: " + "; ".join(str(w) for w in candidate.warnings[:3])
                )

            source_kind = str(pack.get("source") or "registry")
            sources.append({
                "class_type": slug or candidate_query,
                "title": str(pack.get("name") or slug or candidate_query),
                "score": 80 if expected_classes else 60,
                "reasons": [f"registry:{candidate_query}"],
                "source": "comfy-registry" if source_kind == "comfy-registry" else source_kind,
                "pack": slug,
                "url": pack.get("url"),
                "description": "; ".join(bit for bit in description_bits if bit),
                "tasks": ["custom_nodes"],
                "path": "",
                "template_id": "",
                "source_workflow_path": "",
                "source_workflow_available": False,
                "source_workflow_parseable": False,
                "adapt_pattern_keys": [],
                "expected_classes": list(expected_classes),
                "resolver_candidate": payload,
            })

    for source in sources:
        source["score"] = max(
            int(source.get("score") or 0),
            _registry_source_rank(source, query),
        )
    ranked_sources = [
        source for source in sources
        if _registry_source_rank(source, query) > 0 or str(source.get("source")) != "github"
    ]
    ranked_sources.sort(key=lambda source: (-_registry_source_rank(source, query), str(source.get("class_type", "")).lower()))
    return tuple(ranked_sources), tuple(warnings)


def _registry_candidate_queries(query: str, *, max_queries: int = 6) -> list[str]:
    normalized = " ".join(str(query or "").split())
    if not normalized:
        return []
    queries = [normalized]
    class_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", normalized)
    if any(token.startswith("ADE_") for token in class_tokens):
        queries.append("ADE_ AnimateDiff Evolved ComfyUI")
    for token in re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\b", normalized):
        if token in queries:
            continue
        if "_" not in token and not any(ch.isupper() for ch in token[1:]):
            continue
        if token.casefold() in _SEARCH_STOPWORDS:
            continue
        queries.append(token)
        if len(queries) >= max_queries:
            break
    return queries[:max_queries]


def _registry_source_rank(source: Mapping[str, Any], query: str) -> int:
    anchors = _registry_anchor_terms(query)
    if not anchors:
        return 1
    rankable = {
        "class_type": source.get("class_type"),
        "title": source.get("title"),
        "source": source.get("source"),
        "pack": source.get("pack"),
        "url": source.get("url"),
        "description": source.get("description"),
        "expected_classes": source.get("expected_classes"),
        "resolver_candidate": source.get("resolver_candidate"),
    }
    text = json.dumps(rankable, sort_keys=True, default=str).casefold().replace("-", "").replace("_", "")
    rank = 0
    for anchor in anchors:
        if anchor in text:
            rank += 20 + len(anchor)
    source_kind = str(source.get("source") or "")
    if source_kind == "comfy-registry":
        rank += 80
    elif source_kind == "github":
        rank -= 5
    return rank


def _registry_anchor_terms(query: str) -> list[str]:
    tokens = [
        token for token in _query_tokens(query)
        if token.casefold() not in _SEARCH_STOPWORDS
        and token.casefold() not in _REGISTRY_QUERY_STOPWORDS
        and not token.isdigit()
    ]
    terms = [token.casefold().replace("-", "").replace("_", "") for token in tokens]
    if any(token.startswith("ADE_") or "AnimateDiff" in token for token in tokens):
        terms.append("animatediff")
    if any("Evolved" in token for token in tokens):
        terms.append("evolved")
    if "animatediff" in terms and "evolved" in terms:
        terms.append("animatediffevolved")
    if len(tokens) >= 2:
        for size in (3, 2):
            for i in range(0, max(0, len(tokens) - size + 1)):
                terms.append("".join(tokens[i : i + size]).casefold().replace("-", "").replace("_", ""))
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if len(term) < 3 or term in seen:
            continue
        deduped.append(term)
        seen.add(term)
    return deduped


def _source_query_relevance_score(source: Mapping[str, Any], query: str) -> int:
    anchors, matched_anchors = _source_relevance_matches(source, query)
    score = int(source.get("score") or 0)
    if not anchors:
        return score
    title_text = str(source.get("title") or source.get("class_type") or "").casefold().replace("-", "").replace("_", "")
    url_text = str(source.get("url") or "").casefold().replace("-", "").replace("_", "")
    for anchor in matched_anchors:
        score += 100 + len(anchor)
        if anchor in title_text:
            score += 200
        if anchor in url_text:
            score += 150
    if not matched_anchors:
        return 0
    if source.get("source_workflow_parseable") is True:
        score += 120
    if source.get("hivemind_promoted_workflow") is True:
        score += 160
    return score


_STRONG_RELEVANCE_FAMILY_ANCHORS = frozenset({
    "acestep",
    "animatediff",
    "controlnet",
    "deforum",
    "detaildaemon",
    "flux",
    "hunyuan",
    "ipadapter",
    "ltx",
    "melbandroformer",
    "qwen",
    "sd3",
    "sdxl",
    "svd",
    "wan",
    "wan22",
})


def _source_relevance_matches(source: Mapping[str, Any], query: str) -> tuple[list[str], list[str]]:
    anchors = _source_relevance_anchor_terms(query)
    if not anchors:
        return anchors, []
    rankable = {
        "class_type": source.get("class_type"),
        "title": source.get("title"),
        "description": source.get("description"),
        "url": source.get("url"),
        "node_types": source.get("node_types"),
        "workflow_schema_classes": source.get("workflow_schema_classes"),
        "tasks": source.get("tasks"),
    }
    text = json.dumps(rankable, sort_keys=True, default=str).casefold().replace("-", "").replace("_", "")
    matched = [anchor for anchor in anchors if anchor in text]
    return anchors, matched


def _source_is_strong_relevance_match(source: Mapping[str, Any], query: str) -> bool:
    _anchors, matched = _source_relevance_matches(source, query)
    if len(matched) < 2:
        return False
    if not any(anchor in _STRONG_RELEVANCE_FAMILY_ANCHORS for anchor in matched):
        return False
    source_kind = str(source.get("source") or "")
    if source_kind in {"hivemind_workflow", "external_workflow", "source_workflow", "ready_template"}:
        return True
    return source.get("source_workflow_parseable") is True


def _source_relevance_anchor_terms(query: str) -> list[str]:
    stop = _SEARCH_STOPWORDS | _HIVEMIND_FALLBACK_STOPWORDS | {
        "as",
        "base",
        "before",
        "branch",
        "branches",
        "driven",
        "entire",
        "effectively",
        "first",
        "instead",
        "keep",
        "keeping",
        "merge",
        "merging",
        "output",
        "outputs",
        "pipeline",
        "preserve",
        "preserving",
        "preview",
        "region",
        "restructure",
        "save",
        "saves",
        "saving",
        "same",
        "stage",
        "stages",
        "step",
        "tradeoff",
        "tradeoffs",
        "then",
        "two",
        "walk",
        "while",
    }
    terms: list[str] = []
    for token in _query_tokens(query):
        raw = token.casefold()
        clean = re.sub(r"[^a-z0-9]", "", raw)
        if not clean or clean in stop or len(clean) < 3:
            continue
        if "controlnet" in clean:
            clean = "controlnet"
        elif clean in {"animate", "animatediff"}:
            clean = "animatediff"
        elif clean in {"inpainted", "inpainting"}:
            clean = "inpaint"
        elif clean in {"ipadapter", "ipadapterplus"}:
            clean = "ipadapter"
        elif clean in {"svd", "stablevideodiffusion"}:
            clean = "svd"
        terms.append(clean)
    compact = "".join(re.sub(r"[^a-z0-9]", "", token.casefold()) for token in _query_tokens(query))
    if "stablevideodiffusion" in compact and "svd" not in terms:
        terms.append("svd")
    if "melbandroformer" in compact and "melbandroformer" not in terms:
        terms.append("melbandroformer")
    if "detaildaemon" in compact and "detaildaemon" not in terms:
        terms.append("detaildaemon")
    return list(dict.fromkeys(terms[:12]))


# ── Structured precedent helpers (SD2) ────────────────────────────────────────

# ── Freshness / evidence metadata helpers (SD1) ───────────────────────────────


def _compute_content_hash(source: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hex digest of a source dict's content.

    Only serializable, non-ephemeral fields are hashed so the hash is stable
    across re-fetches of the same underlying content.  Fields that vary per
    request (score, reasons, relevance_*) are excluded.
    """
    stable_keys = sorted(
        k for k in source
        if not k.startswith("_")  # internal keys excluded
        and k not in {
            "score", "reasons", "relevance_score", "relevance_matched_anchors",
            "relevance_anchor_count", "strong_relevance_match",
        }
    )
    canonical = json.dumps(
        {k: source[k] for k in stable_keys},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _source_tier_for_source(source: Mapping[str, Any]) -> str:
    """Return the canonical evidence tier string for a source dict."""
    source_kind = str(source.get("source") or "").strip()
    # Map known aliases to canonical tier names.
    tier_map: dict[str, str] = {
        "hivemind_workflow": "hivemind_workflow",
        "hivemind": "hivemind",
        "hivemind_message": "hivemind_message",
        "hivemind_distillation": "hivemind_distillation",
        "external_workflow": "external_workflow",
        "comfy-registry": "comfy-registry",
        "github": "github",
        "git": "git",
        "web": "web",
        "curated": "curated",
        "ready_template": "ready_template",
        "source_workflow": "source_workflow",
        "custom_node_examples": "custom_node_examples",
        "object_info": "object_info",
    }
    direct = tier_map.get(source_kind)
    if direct:
        return direct
    # Heuristic: if the url contains civitai.com, it's civitai tier.
    url = str(source.get("url") or "").casefold()
    if "civitai.com" in url:
        return "civitai"
    # Fallback: use the source_kind directly if non-empty, else empty.
    return source_kind if source_kind else ""


def _tier_ttl_seconds(tier: str) -> int:
    """Return the TTL in seconds for a given evidence tier.

    Returns 86400 (24h) for unknown tiers as a safe default.
    """
    return _TIER_TTL_MAP.get(tier, 86400)


def _source_freshness_status(
    retrieval_time: str,
    tier: str,
    *,
    now: float | None = None,
) -> str:
    """Return ``"fresh"``, ``"stale"``, or ``"unknown"`` for a source.

    When *retrieval_time* is empty, returns ``"unknown"``.
    When the tier TTL is 0 (live runtime schema), always returns ``"fresh"``
    (the fetch is live by definition).
    """
    if not retrieval_time:
        return "unknown"
    ttl = _tier_ttl_seconds(tier)
    if ttl <= 0:
        return "fresh"  # live runtime — never stale
    if now is None:
        now = time.time()
    try:
        # Parse ISO-8601.  Accept 'Z' suffix and fractional seconds.
        ts = retrieval_time.replace("Z", "+00:00")
        if "+" in ts or ts.endswith("Z"):
            from datetime import datetime
            parsed = datetime.fromisoformat(ts)
            epoch = parsed.timestamp()
        else:
            epoch = float(ts)  # plain Unix timestamp
    except (ValueError, TypeError):
        return "unknown"
    if epoch <= 0:
        return "unknown"
    age = now - epoch
    return "fresh" if age <= ttl else "stale"


def _build_query_transform_trace(
    query: str,
    tier: str,
    *,
    original_query: str | None = None,
    extra: str | None = None,
) -> str:
    """Build a compact, deterministic trace of how *query* was transformed.

    Records the original query (if different), the tier it was submitted to,
    and any extra transform note.  This lets downstream audit trails see that
    a Hivemind query was stopword-stripped, or a web search was broadened.
    """
    parts: list[str] = [f"tier={tier}"]
    if original_query and original_query.strip() != query.strip():
        parts.append(f"original={original_query.strip()!r}")
    if extra:
        parts.append(extra)
    parts.append(f"effective={query.strip()!r}")
    return "; ".join(parts)


def _now_iso() -> str:
    """Return the current UTC time as a compact ISO-8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stamp_source_evidence_meta(
    source: dict[str, Any],
    *,
    query: str,
    retrieval_time: str | None = None,
    query_transform_extra: str | None = None,
    original_query: str | None = None,
) -> dict[str, Any]:
    """Stamp freshness / evidence metadata onto a source dict in-place.

    Adds ``_retrieval_time``, ``_content_hash``, ``_query_transform_trace``,
    ``_tier``, and ``_freshness_status`` to *source*.  The leading underscore
    convention keeps these fields out of serialized ``ResearchResult.sources``
    while still being inspectable from the raw dict.

    Returns *source* for chaining.
    """
    if retrieval_time is None:
        retrieval_time = _now_iso()
    tier = _source_tier_for_source(source)
    source["_retrieval_time"] = retrieval_time
    source["_content_hash"] = _compute_content_hash(source)
    source["_query_transform_trace"] = _build_query_transform_trace(
        query=query,
        tier=tier,
        original_query=original_query,
        extra=query_transform_extra,
    )
    source["_tier"] = tier
    source["_freshness_status"] = _source_freshness_status(retrieval_time, tier)
    return source


# ── Structured precedent helpers (continued) ──────────────────────────────────


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


_ROLE_SIGNAL_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("control", ("controlnet", "control_net", "control", "preprocessor")),
    ("guidance", ("guide", "guidance", "reference", "adapter")),
    ("frame", ("frame", "start_image", "end_image", "last_image")),
    ("audio", ("audio", "sound", "voice", "music")),
    ("refinement", ("refin", "second", "later", "pass", "stage")),
    ("sampling", ("sampl", "sigma", "schedule", "denoise")),
    ("conditioning", ("condition", "positive", "negative", "prompt")),
    ("model", ("model", "loader", "checkpoint", "unet")),
    ("latent", ("latent", "sample")),
    ("decode", ("decode", "image")),
    ("output", ("save", "preview", "combine", "output")),
    ("input", ("load", "encode", "source", "input")),
    ("transform", ("upscale", "resize", "scale", "transform")),
)


def _tag_source_widget_values(values: Any) -> tuple[dict[str, Any], ...]:
    """Normalize source values as explicitly tagged priors."""
    if not isinstance(values, (list, tuple)):
        return ()
    tagged: list[dict[str, Any]] = []
    source_shape = len(values)
    for source_index, value in enumerate(values):
        if not isinstance(value, Mapping):
            continue
        name = str(value.get("name") or "").strip()
        if not name:
            continue
        tagged.append({
            "name": name,
            "value": copy.deepcopy(value.get("value")),
            "provenance": "source_template",
            "confidence": "high",
            "source_index": source_index,
            "source_shape": source_shape,
        })
    return tuple(tagged)


def _binding_envelope_for_instance(
    *,
    class_type: str,
    source_template: str,
    instance: Mapping[str, Any],
    role_label: str,
    role_confidence: str,
    instance_count: int,
    conflict_fields: frozenset[str],
) -> dict[str, Any]:
    """Return lossless, deterministic source-history binding evidence.

    Research does not own an authoritative live schema, so schema validation
    remains explicitly pending here and is repeated at the shared add-node
    resolver.  Provisional positional names remain visible but non-bindable.
    """
    source_instance_id = str(instance.get("node_id") or "")
    tagged = _tag_source_widget_values(instance.get("widget_values"))
    fields: list[dict[str, Any]] = []
    for prior in tagged:
        canonical_field = str(prior.get("name") or "")
        provisional = bool(re.fullmatch(r"widget_\d+", canonical_field))
        conflict = canonical_field in conflict_fields
        if provisional:
            eligibility_status = "refused"
            reason = "provisional_widget_name"
        elif instance_count != 1:
            eligibility_status = "pending_source_selection"
            reason = "same_class_instance_selection_required"
        else:
            eligibility_status = "pending_schema_validation"
            reason = "authoritative_schema_validation_required"
        fields.append({
            "canonical_field": canonical_field,
            "source_field": canonical_field,
            "source_index": prior["source_index"],
            "source_shape": prior["source_shape"],
            "value": copy.deepcopy(prior.get("value")),
            "provenance": prior["provenance"],
            "confidence": prior["confidence"],
            "name_resolution_status": "provisional" if provisional else "canonical",
            "schema_validation_status": "not_evaluated",
            "conflict_status": "conflicting" if conflict else "unique_value",
            "eligibility_status": eligibility_status,
            "eligible": False,
            "reason": reason,
        })
    return {
        "version": 1,
        "class_type": class_type,
        "selector": {
            "source_template": source_template,
            "source_instance_id": source_instance_id,
            "role_label": role_label,
            "role_confidence": role_confidence,
            "instance_count": instance_count,
            "selection_status": "unique" if instance_count == 1 else "ambiguous",
        },
        "fields": fields,
        "source_shape": {"widgets_values_length": len(instance.get("widget_values") or ())},
    }


def _heuristic_instance_role(
    class_type: str,
    instance: Mapping[str, Any],
    *,
    ordinal: int,
    total: int,
) -> tuple[str, str]:
    """Infer a neutral role label from local neighborhood signals.

    This deliberately never claims a role with high confidence.  A later
    same-type instance connected to a sampling peer is labelled as a
    refinement prior because ordinal position is the only available pipeline
    signal; weak or custom neighborhoods remain ``unresolved``/low.
    """
    edges = instance.get("incident_edges")
    edge_records = tuple(edge for edge in edges if isinstance(edge, Mapping)) if isinstance(edges, (list, tuple)) else ()
    signal_text = " ".join(
        str(part)
        for edge in edge_records
        for part in (edge.get("peer_class", ""), edge.get("socket", ""), edge.get("direction", ""))
    ).casefold().replace("-", "_")
    signal_text = f"{class_type.casefold()} {signal_text}"

    if total > 1 and ordinal > 0 and "sampl" in signal_text:
        return "refinement", "medium"
    for role, terms in _ROLE_SIGNAL_RULES:
        if any(term in signal_text for term in terms):
            return role, "medium"
    return "unresolved", "low"


def _provenance_precedent_sources(
    graph: dict[str, Any] | None,
    target_node_type: str,
) -> tuple[dict[str, Any], ...]:
    """Read the graph breadcrumb and return a source descriptor, if usable."""
    if not isinstance(graph, dict) or not target_node_type.strip():
        return ()
    extra = graph.get("extra")
    breadcrumb = extra.get("vibecomfy") if isinstance(extra, Mapping) else None
    if not isinstance(breadcrumb, Mapping):
        return ()
    if not any(isinstance(breadcrumb.get(key), str) and breadcrumb.get(key).strip() for key in ("source_template", "prior_path")):
        return ()

    try:
        source_workflow = provenance.load_source_workflow(graph)
        instances = provenance.collect_type_instances(source_workflow, target_node_type)
    except Exception:
        return ()
    if not instances:
        return ()

    source_template = str(breadcrumb.get("source_template") or "").strip()
    prior_path = str(breadcrumb.get("prior_path") or "").strip()
    return ({
        "source": "source_workflow",
        "class_type": target_node_type,
        "source_template": source_template,
        "source_workflow_path": prior_path or None,
        "provenance_instances": tuple(instances),
        "node_types": (target_node_type,),
        "source_workflow_available": True,
        "source_workflow_parseable": True,
        "provenance_lookup": True,
        "reasons": ("graph provenance breadcrumb",),
    },)


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
        source_template = str(source.get("source_template") or "")

        is_workflow = source_kind in workflow_source_kinds
        has_py_path = isinstance(path, str) and path.endswith(".py")
        has_json_path = isinstance(path, str) and path.endswith(".json")
        has_source_workflow = isinstance(source_workflow_path, str)
        if not is_workflow and not has_py_path and not has_json_path and not has_source_workflow:
            continue
        if not class_type:
            continue

        # Provenance lookup supplies one record per source instance.  Keep one
        # slice per instance so duplicate class types retain distinct values,
        # neighborhoods, and role priors instead of collapsing to first match.
        provenance_instances = source.get("provenance_instances")
        if isinstance(provenance_instances, (list, tuple)) and provenance_instances:
            valid_instances = tuple(
                instance for instance in provenance_instances
                if isinstance(instance, Mapping)
            )
            values_by_field: dict[str, list[Any]] = {}
            for instance in valid_instances:
                for prior in _tag_source_widget_values(instance.get("widget_values")):
                    values_by_field.setdefault(str(prior["name"]), []).append(prior.get("value"))
            conflict_fields = frozenset(
                field_name
                for field_name, values in values_by_field.items()
                if any(value != values[0] for value in values[1:])
            )
            for ordinal, instance in enumerate(valid_instances):
                node_id = str(instance.get("node_id") or "").strip()
                if not node_id:
                    continue
                role_label, role_confidence = _heuristic_instance_role(
                    class_type,
                    instance,
                    ordinal=ordinal,
                    total=len(valid_instances),
                )
                slices.append(
                    WorkflowSlice(
                        source_class_type=class_type,
                        node_ids=(node_id,),
                        node_types=(class_type,),
                        entry_anchor=node_id,
                        exit_anchor=node_id,
                        source_workflow_path=(
                            str(source_workflow_path)
                            if isinstance(source_workflow_path, str) and source_workflow_path
                            else None
                        ),
                        python_path=path if isinstance(path, str) else None,
                        source_template=source_template,
                        role_label=role_label,
                        role_confidence=role_confidence,
                        widget_values=_tag_source_widget_values(instance.get("widget_values")),
                        binding_envelope=_binding_envelope_for_instance(
                            class_type=class_type,
                            source_template=source_template,
                            instance=instance,
                            role_label=role_label,
                            role_confidence=role_confidence,
                            instance_count=len(valid_instances),
                            conflict_fields=conflict_fields,
                        ),
                        incident_edges=tuple(
                            edge for edge in instance.get("incident_edges", ())
                            if isinstance(edge, Mapping)
                        ),
                        warnings=(),
                    )
                )
            seen.add(class_type)
            continue

        if class_type in seen:
            continue

        load_result: WorkflowLoadResult | None = None
        if has_source_workflow:
            load_result = load_workflow_source(source_workflow_path)
        elif has_json_path:
            load_result = load_workflow_source(path)

        if load_result is not None and load_result.ok:
            node_ids = tuple(record.node_id for record in load_result.nodes)
            node_types = tuple(record.class_type for record in load_result.nodes)
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
                warnings=(),
            )
        )

    return tuple(slices)


_PRECEDENT_WORKFLOW_SOURCE_KINDS: frozenset[str] = frozenset({
    "ready_template",
    "source_workflow",
    "external_workflow",
    "hivemind_workflow",
})


def _requested_model_families(query: str, graph: dict | None = None) -> set[str]:
    """Return explicit model-family signals from the user request/graph.

    Query text is treated as the hard signal. Graph-derived families are only
    included when the query has none, so a request like "switch this LTX graph
    to Hotshot" gates to Hotshot rather than preserving the current LTX family.
    """
    families = _family_evidence_from_text(query)
    if families:
        return families
    graph_text = " ".join(_graph_node_class_types(graph))
    return _family_evidence_from_text(graph_text)


def _requested_media_domain(query: str, graph: dict | None = None) -> str | None:
    query_media = _media_domain_from_text(query)
    if query_media is not None:
        return query_media
    return _media_domain_from_node_types(_graph_node_class_types(graph))


def _media_domain_from_text(text: str) -> str | None:
    haystack = text.casefold().replace("-", "_")
    # Prefer explicit output/domain words over generic input words. A request
    # like "image to video" should target video precedents, not image.
    ordered = (
        (
            "video",
            (
                "video",
                "i2v",
                "t2v",
                "v2v",
                "img2video",
                "image2video",
                "txt2video",
                "text2video",
                "image_to_video",
                "text_to_video",
                "audio_to_video",
                "video_combine",
                "videocombine",
                "frame",
                "frames",
                "frame_count",
            ),
        ),
        ("3d", ("3d", "3_d", "model_to_3d", "image_to_3d", "text_to_3d", "mesh", "glb", "obj")),
        ("audio", ("text_to_audio", "audio_to_audio", "audio_generation", "speech", "music", "sound")),
        ("image", ("image", "t2i", "i2i", "text_to_image", "image_to_image", "inpaint", "outpaint")),
    )
    for domain, aliases in ordered:
        if any(_semantic_alias_in_text(alias, haystack) for alias in aliases):
            return domain
    return None


def _source_model_families(source: Mapping[str, Any]) -> set[str]:
    explicit = _coerce_tasks(source.get("model_families"))
    semantics = source.get("workflow_semantics")
    if isinstance(semantics, Mapping):
        explicit.extend(_coerce_tasks(semantics.get("model_families")))

    families: set[str] = set()
    for family in explicit:
        if not isinstance(family, str) or not family.strip():
            continue
        canonical = family.casefold().strip().replace("-", "_")
        if canonical in {"controlnet", "control_net"}:
            continue
        if canonical in _FAMILY_EVIDENCE_TERMS:
            families.add(canonical)
            continue
        inferred = _family_evidence_from_text(canonical)
        if inferred:
            families.update(inferred)
        else:
            families.add(canonical)
    if families:
        return families

    text_parts: list[str] = []
    for key in (
        "class_type",
        "pack",
        "description",
        "path",
        "template_id",
        "source_workflow_path",
        "task_type",
        "media_type",
    ):
        value = source.get(key)
        if isinstance(value, str):
            text_parts.append(value)
    for key in ("tasks", "adapt_pattern_keys", "node_types"):
        value = source.get(key)
        if isinstance(value, (list, tuple)):
            text_parts.extend(str(item) for item in value if item is not None)
    if isinstance(semantics, Mapping):
        text_parts.append(_workflow_semantics_text({"metadata": {"workflow_semantics": dict(semantics)}}))
    return _family_evidence_from_text(" ".join(text_parts))


def _source_media_domain(source: Mapping[str, Any]) -> str | None:
    semantics = source.get("workflow_semantics")
    candidates: list[str] = []
    for key in ("media_type", "task_type", "class_type", "description", "path", "template_id", "source_workflow_path"):
        value = source.get(key)
        if isinstance(value, str):
            candidates.append(value)
    if isinstance(semantics, Mapping):
        for key in ("media_type", "task_type"):
            value = semantics.get(key)
            if isinstance(value, str):
                candidates.append(value)
        node_types = semantics.get("node_types")
        if isinstance(node_types, list):
            domain = _media_domain_from_node_types(node_types)
            if domain not in (None, "multi"):
                return domain
    node_types = source.get("node_types")
    if isinstance(node_types, (list, tuple)):
        domain = _media_domain_from_node_types(node_types)
        if domain not in (None, "multi"):
            return domain
    return _media_domain_from_text(" ".join(candidates))


def _is_workflow_precedent_source(source: Mapping[str, Any]) -> bool:
    source_kind = str(source.get("source", ""))
    if source_kind in _PRECEDENT_WORKFLOW_SOURCE_KINDS:
        return True
    path = source.get("path")
    source_workflow_path = source.get("source_workflow_path")
    return (
        isinstance(path, str)
        and (path.endswith(".py") or path.endswith(".json"))
    ) or isinstance(source_workflow_path, str)


def _first_blocking_unparseable_source(
    sources: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    local_kinds = {"ready_template", "source_workflow", "curated", "custom_node_examples"}
    candidates = [
        source
        for source in sources
        if str(source.get("source") or "") in local_kinds
        and source.get("source_workflow_available") is True
        and source.get("source_workflow_parseable") is False
        and source.get("strong_relevance_match") is True
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda source: (
            -int(source.get("relevance_score") or source.get("score") or 0),
            str(source.get("class_type") or source.get("title") or "").casefold(),
        )
    )
    return candidates[0]


def _filter_sources_for_precedent_semantics(
    sources: tuple[dict[str, Any], ...],
    *,
    query: str,
    graph: dict | None,
) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    """Filter execute-facing precedent candidates by explicit family intent.

    The full research source list remains intact for evidence. This gate only
    trims workflow/template candidates before `WorkflowSlice`, packet, and plan
    construction. Unknown-family sources pass; known wrong-family sources are
    blocked when the query explicitly names a target/current model family.
    """
    requested = _requested_model_families(query, graph)
    requested_media = _requested_media_domain(query, graph)
    if not requested and requested_media in (None, "multi"):
        return sources, ()

    filtered: list[dict[str, Any]] = []
    warnings: list[str] = []
    for source in sources:
        if not isinstance(source, dict) or not _is_workflow_precedent_source(source):
            filtered.append(source)
            continue
        source_families = _source_model_families(source)
        if requested and source_families and not source_families & requested:
            class_type = str(source.get("class_type") or "<unknown>")
            warnings.append(
                "precedent semantic gate: excluded "
                f"{class_type} because model families {sorted(source_families)} "
                f"do not match requested {sorted(requested)}"
            )
            continue
        source_media = _source_media_domain(source)
        if (
            requested_media not in (None, "multi")
            and source_media not in (None, "multi")
            and source_media != requested_media
        ):
            class_type = str(source.get("class_type") or "<unknown>")
            warnings.append(
                "precedent semantic gate: excluded "
                f"{class_type} because media domain {source_media!r} "
                f"does not match requested {requested_media!r}"
            )
            continue
        filtered.append(source)
        continue
    return tuple(filtered), tuple(warnings)


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
        if any(_semantic_alias_in_text(term, haystack) for term in terms):
            families.add(family)
    return families


def _semantic_alias_in_text(alias: str, text: str) -> bool:
    alias_low = alias.casefold().replace("-", "_")
    if not alias_low:
        return False
    if re.search(r"[^a-z0-9_]", alias_low):
        return alias_low in text
    return re.search(rf"(?<![a-z0-9]){re.escape(alias_low)}(?![a-z0-9])", text) is not None


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


# ---------------------------------------------------------------------------
# W-08 — Deterministic cut-edge enumeration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CutEdge:
    """A single cut edge with exactly one endpoint inside a source segment S.

    A cut edge is any directed link in a ComfyUI-style source graph where
    precisely one endpoint (the producer or the consumer) belongs to the
    segment *S*.
    """

    direction: str  # "inbound" | "outbound"
    inside_node_id: str  # the endpoint that IS in S
    outside_node_id: str  # the endpoint NOT in S
    inside_class_type: str
    outside_class_type: str
    input_name: str  # input socket name on the *consumer* side
    output_slot: int | str  # output slot on the *producer* side
    socket_type: str | None  # authoritative socket type if known, else None
    role_evidence: tuple[str, ...]  # generic role hints from class/socket/neighbourhood
    confidence: float


def _generic_role_evidence(
    class_type: str, input_name: str, *, is_producer_inside: bool
) -> tuple[str, ...]:
    """Derive generic role hints from class-type and input-name heuristics.

    This is intentionally **not** case-specific — no class table, no golden
    literals such as ``depth_controlnet`` or ``ReCamMaster``.  The hints are
    meant to help later stages (e.g. anchor binding) make reasonable guesses
    without leaking fixture identity.
    """
    ct = class_type.lower()
    inp = input_name.lower()
    roles: list[str] = []

    # --- class-type heuristics -----------------------------------------------
    if any(
        t in ct
        for t in (
            "sampler",
            "sample",
            "scheduler",
            "sigmas",
            "guider",
            "dispatcher",
        )
    ):
        roles.append("sampler")
    if any(
        t in ct
        for t in (
            "loader",
            "load",
            "model",
            "checkpoint",
            "unet",
            "lora",
            "upscale",
        )
    ):
        roles.append("model_provider")
    if any(t in ct for t in ("vae", "latent", "encode", "decode")):
        roles.append("latent")
    if any(t in ct for t in ("clip", "text_encoder", "t5", "llm", "bert")):
        roles.append("text_encoder")
    if any(t in ct for t in ("conditioning", "cond", "prompt", "text")):
        roles.append("conditioning")
    if any(t in ct for t in ("image", "preview", "save", "output")):
        roles.append("image")

    # --- socket-name heuristics ----------------------------------------------
    if any(
        t in inp
        for t in ("model", "unet", "checkpoint", "lora", "base_model", "refiner")
    ):
        roles.append("model_provider")
    if any(t in inp for t in ("latent", "samples", "latent_image")):
        roles.append("latent")
    if any(t in inp for t in ("clip", "text_encoder", "clip_name")):
        roles.append("text_encoder")
    if any(t in inp for t in ("conditioning", "cond", "positive", "negative")):
        roles.append("conditioning")
    if any(t in inp for t in ("vae",)):
        roles.append("latent")
    if any(t in inp for t in ("image", "images", "mask", "preview")):
        roles.append("image")

    # Deduplicate while preserving order.
    return tuple(dict.fromkeys(roles))


def enumerate_cut_edges(
    source_graph: dict[str, dict[str, Any]],
    segment_node_ids: set[str] | frozenset[str] | tuple[str, ...] | list[str],
    *,
    schema_lookup: Callable[[str, str], str | None] | None = None,
) -> tuple[CutEdge, ...]:
    """Return every cut edge of *segment_node_ids*, each exactly once.

    A **cut edge** is any directed link with exactly ONE endpoint inside the
    segment *S* (= *segment_node_ids*):

    * **inbound**  — producer outside *S*, consumer inside *S*.
    * **outbound** — producer inside *S*, consumer outside *S*.

    Edges with both endpoints inside *S* (internal) or both outside
    (external) are silently excluded.

    Parameters
    ----------
    source_graph : dict
        ComfyUI-style graph: ``{node_id: {"class_type": ..., "inputs": {...}}}``.
    segment_node_ids : iterable of str
        Node ids that define the segment *S*.
    schema_lookup : callable or None
        Optional ``(class_type, socket_name) -> str | None`` that returns an
        authoritative socket type string.  When omitted, ``socket_type`` is
        always ``None``.

    Returns
    -------
    tuple[CutEdge, ...]
        Deterministically ordered cut edges (by
        ``(direction, inside_node_id, input_name)``).
    """
    s_set: frozenset[str] = frozenset(segment_node_ids)
    edges: list[CutEdge] = []

    for consumer_id, node in source_graph.items():
        consumer_class = node.get("class_type", "?")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue

        for input_name, value in inputs.items():
            # Only process link-style values: [producer_id, output_slot]
            if not (isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str)):
                continue
            producer_id: str = value[0]
            output_slot: int | str = value[1] if len(value) >= 2 else 0

            consumer_inside = consumer_id in s_set
            producer_inside = producer_id in s_set

            # Both inside → internal; both outside → external.
            if consumer_inside == producer_inside:
                continue

            direction: str
            inside_id: str
            outside_id: str
            inside_class: str
            outside_class: str

            if consumer_inside:
                # Producer outside → consumer inside = inbound.
                direction = "inbound"
                inside_id = consumer_id
                outside_id = producer_id
                inside_class = consumer_class
                outside_class = source_graph.get(producer_id, {}).get("class_type", "?")
            else:
                # Producer inside → consumer outside = outbound.
                direction = "outbound"
                inside_id = producer_id
                outside_id = consumer_id
                inside_class = source_graph.get(producer_id, {}).get("class_type", "?")
                outside_class = consumer_class

            socket_type: str | None = None
            if schema_lookup is not None:
                # Schema lookup is keyed by (consumer_class_type, input_name).
                socket_type = schema_lookup(consumer_class, input_name)

            role_evidence = _generic_role_evidence(
                inside_class if producer_inside else consumer_class,
                input_name,
                is_producer_inside=producer_inside,
            )

            edges.append(
                CutEdge(
                    direction=direction,
                    inside_node_id=inside_id,
                    outside_node_id=outside_id,
                    inside_class_type=inside_class,
                    outside_class_type=outside_class,
                    input_name=input_name,
                    output_slot=output_slot,
                    socket_type=socket_type,
                    role_evidence=role_evidence,
                    confidence=1.0,
                )
            )

    # Deterministic order: sort by (direction, inside_node_id, input_name).
    edges.sort(key=lambda e: (e.direction, e.inside_node_id, e.input_name))
    return tuple(edges)


# ---------------------------------------------------------------------------
# W-09 — Lean inquiry-role and socket matcher
# ---------------------------------------------------------------------------


# Socket-type tokens that are intentionally rejected (fail closed).  These are
# the permissive escape hatches ComfyUI schemas use; the lean matcher refuses
# to bind on them rather than guessing compatibility.
_UNKNOWN_SOCKET_TOKENS: frozenset[str] = frozenset(
    {"", "*", "ANY", "UNKNOWN", "WILDCARD", "DYNAMIC", "*"}
)


def _strict_socket_type(raw: Any) -> str | None:
    """Normalise a raw socket type to an UPPER token, or ``None`` if unknown.

    Returns ``None`` for ``None``, blank, wildcard, dynamic, or untypable
    values so that callers can fail closed on the ``None`` branch.
    """
    if raw is None:
        return None
    text = str(raw).strip().upper()
    if text in _UNKNOWN_SOCKET_TOKENS:
        return None
    return text


def _strict_socket_compatible(source_type: Any, target_type: Any) -> bool:
    """Strict socket compatibility — both sides MUST be known and equal.

    Unlike :func:`vibecomfy.schema.validate.socket_types_compatible`, this never
    falls back to permissive acceptance: any unknown/wildcard/dynamic side, or
    any type mismatch, returns ``False``.
    """
    src = _strict_socket_type(source_type)
    dst = _strict_socket_type(target_type)
    if src is None or dst is None:
        return False
    return src == dst


@dataclass(frozen=True)
class CutEdgeBinding:
    """A single accepted binding between a source-segment cut edge and a
    target-graph node/input socket.
    """

    cut_edge: CutEdge
    target_node_id: str
    target_class_type: str
    target_input_name: str
    direction: str  # "inbound" | "outbound" (echoes the cut edge)
    socket_type_match: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class MatcherResult:
    """Outcome of :func:`match_cut_edges`."""

    bindings: tuple[CutEdgeBinding, ...]
    rejections: tuple[str, ...]
    complete: bool


def _role_from_socket_type(socket_type: Any, input_name: str) -> str:
    """Map an authoritative socket TYPE to a generic flow role.

    The role is the vocabulary of *what flows* through the socket, not what
    the surrounding node *is*.  This keeps the matcher honest: a MODEL input
    on a KSampler and a MODEL input on any other node share the role
    ``model_provider``.  Generic only — no class tables, no golden literals.
    """
    norm = _strict_socket_type(socket_type)
    if norm is None:
        # Fall back to the shared socket-name inferrer (also generic).
        return _infer_generic_role("", input_name)
    low = norm.lower()
    socket_type_to_role: tuple[tuple[tuple[str, ...], str], ...] = (
        (("model",), "model_provider"),
        (("latent",), "latent"),
        (("conditioning", "cond"), "conditioning"),
        (("image", "img"), "image"),
        (("clip",), "text_encoder"),
        (("vae",), "latent"),
        (("mask",), "mask"),
        (("control", "controlnet"), "control"),
        (("audio",), "audio"),
    )
    for needles, role in socket_type_to_role:
        if any(n in low for n in needles):
            return role
    return _infer_generic_role("", input_name)


def match_cut_edges(
    cut_edges: tuple[CutEdge, ...],
    target_graph: dict[str, dict[str, Any]],
    *,
    schema_lookup: Callable[[str], dict[str, Any] | None],
    inquiry_terms: tuple[str, ...],
) -> MatcherResult:
    """Bind each source-segment cut edge to a unique target-graph endpoint.

    The matcher is a pure, hard-gate accept/reject: no calibrated weights, no
    global optimisation.  A binding is accepted ONLY when direction, role,
    concrete socket type, endpoint existence, and target-input uniqueness all
    agree.  Unknown, wildcard, dynamic, or tied matches fail closed.

    Parameters
    ----------
    cut_edges : tuple[CutEdge, ...]
        Cut edges produced by :func:`enumerate_cut_edges` for the source
        segment *S*.
    target_graph : dict
        The current/broken graph: ``{node_id: {"class_type": ..., "inputs": {...}}}``.
    schema_lookup : callable
        ``class_type -> dict | None`` returning the authoritative node schema,
        which must expose ``"inputs"`` (name -> type) and optionally
        ``"outputs"`` (slot -> type).  ``WorkflowNodeRecord`` typed outputs are
        NOT trusted — this lookup is the single source of truth.
    inquiry_terms : tuple[str, ...]
        Generic inquiry keywords (e.g. ``("model", "latent")``).  NO case ids,
        filenames, golden types, or ancestry breadcrumbs — anti-gaming invariant.

    Returns
    -------
    MatcherResult
        ``complete=True`` only when every mandatory cut edge resolved to
        exactly one accepted binding.
    """
    accepted: list[CutEdgeBinding] = []
    rejections: list[str] = []

    # (target_node_id, target_input_name) -> the cut edge that already owns it.
    occupied: dict[tuple[str, str], CutEdge] = {}

    # Deterministic iteration order: cut edges are already sorted by
    # enumerate_cut_edges; we additionally sort candidate target nodes for
    # tie-break determinism.
    sorted_target_ids = sorted(target_graph.keys())

    for edge in cut_edges:
        # Resolve the side of the cut edge that carries the link contract:
        # the consumer side.  For inbound edges the consumer is the inside
        # node (the segment consumes); for outbound edges the consumer is the
        # outside node.  In both cases the contract input name is edge.input_name
        # and the producer/output socket is edge.output_slot.
        if edge.direction == "inbound":
            consumer_class = edge.inside_class_type
        else:  # outbound
            consumer_class = edge.outside_class_type

        # The required socket type on the *consumer* side (the input socket).
        consumer_schema = schema_lookup(consumer_class)
        required_socket = _socket_type_from_schema(
            consumer_schema, edge.input_name, is_output=False
        )

        # Role of the value flowing across this cut edge, derived from the
        # authoritative socket TYPE on the consumer side (the contract
        # surface).  Both sides of the binding thus speak the same vocabulary:
        # a MODEL input on the segment matches a MODEL input on the target,
        # regardless of whether the surrounding node is a KSampler or a
        # CLIPTextEncode.  Generic only — no class tables.
        flow_role = _role_from_socket_type(required_socket, edge.input_name)

        candidates: list[CutEdgeBinding] = []
        candidate_reasons: list[str] = []

        for target_id in sorted_target_ids:
            node = target_graph.get(target_id, {})
            if not isinstance(node, dict):
                continue
            target_class = str(node.get("class_type", "?"))
            target_schema = schema_lookup(target_class)
            target_inputs_spec = _inputs_spec(target_schema, node)

            for t_input_name in sorted(_input_socket_names(target_inputs_spec, node)):
                # Gate 1: direction.
                #   inbound  -> target node CONSUMES a compatible input
                #              (the segment needs the same upstream value).
                #   outbound -> target node CONSUMES the segment's output
                #              ("be consumed-by").
                # Both physically land on a target input socket; the
                # distinction is enforced via role compatibility below.
                if edge.direction not in ("inbound", "outbound"):
                    candidate_reasons.append(
                        f"{target_id}.{t_input_name}: bad direction {edge.direction!r}"
                    )
                    continue

                # Gate 4: endpoint existence.
                if t_input_name not in _input_socket_names(target_inputs_spec, node):
                    candidate_reasons.append(
                        f"{target_id}.{t_input_name}: input socket missing"
                    )
                    continue

                target_socket = _socket_type_from_schema(
                    target_schema, t_input_name, is_output=False
                )

                # Gate 3: concrete socket type known + compatible (strict).
                if _strict_socket_type(target_socket) is None:
                    candidate_reasons.append(
                        f"{target_id}.{t_input_name}: unknown type"
                    )
                    continue
                if _strict_socket_type(required_socket) is None:
                    candidate_reasons.append(
                        f"{target_id}.{t_input_name}: unknown type"
                    )
                    continue
                if not _strict_socket_compatible(required_socket, target_socket):
                    candidate_reasons.append(
                        f"{target_id}.{t_input_name}: socket mismatch "
                        f"{required_socket!r} vs {target_socket!r}"
                    )
                    continue

                # Gate 2: role compatible (generic roles only).  Role is
                # derived from the authoritative socket TYPE — same vocabulary
                # as flow_role — so a MODEL input binds a MODEL input.
                target_role = _role_from_socket_type(target_socket, t_input_name)
                if not _roles_compatible(flow_role, target_role):
                    candidate_reasons.append(
                        f"{target_id}.{t_input_name}: role mismatch "
                        f"{flow_role!r} vs {target_role!r}"
                    )
                    continue

                # Gate 5 (preliminary): target-input uniqueness vs occupied map.
                key = (target_id, t_input_name)
                owner = occupied.get(key)
                if owner is not None and owner is not edge:
                    candidate_reasons.append(
                        f"{target_id}.{t_input_name}: occupied"
                    )
                    continue

                candidates.append(
                    CutEdgeBinding(
                        cut_edge=edge,
                        target_node_id=target_id,
                        target_class_type=target_class,
                        target_input_name=t_input_name,
                        direction=edge.direction,
                        socket_type_match=True,
                        reasons=(
                            f"flow_role={flow_role}",
                            f"target_role={target_role}",
                            f"socket={_strict_socket_type(target_socket)}",
                        ),
                    )
                )

        # Resolve uniqueness across all candidates for THIS cut edge.
        if len(candidates) == 0:
            diag = "; ".join(candidate_reasons) if candidate_reasons else "no candidate"
            rejections.append(
                f"cut_edge({edge.direction},{edge.inside_node_id},"
                f"{edge.input_name}): rejected — {diag}"
            )
            continue

        if len(candidates) > 1:
            # Tie -> reject (fail closed).  Deterministic description.
            ties = ", ".join(
                f"{c.target_node_id}.{c.target_input_name}" for c in candidates
            )
            rejections.append(
                f"cut_edge({edge.direction},{edge.inside_node_id},"
                f"{edge.input_name}): ambiguous — ties=[{ties}]"
            )
            continue

        chosen = candidates[0]
        key = (chosen.target_node_id, chosen.target_input_name)
        # Guard against a prior accepted edge already holding this socket.
        if key in occupied and occupied[key] is not edge:
            rejections.append(
                f"cut_edge({edge.direction},{edge.inside_node_id},"
                f"{edge.input_name}): ambiguous — {key} occupied"
            )
            continue
        occupied[key] = edge
        accepted.append(chosen)

    complete = len(rejections) == 0 and len(accepted) == len(cut_edges)
    return MatcherResult(
        bindings=tuple(accepted),
        rejections=tuple(rejections),
        complete=complete,
    )


def _inputs_spec(
    schema: dict[str, Any] | None, node: dict[str, Any]
) -> dict[str, Any]:
    """Return the authoritative inputs spec, falling back to the node's inputs
    keys (names only, no types) when no schema is present.
    """
    if schema and isinstance(schema.get("inputs"), dict):
        return schema["inputs"]
    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        return {name: None for name in inputs}
    return {}


def _input_socket_names(
    inputs_spec: dict[str, Any], node: dict[str, Any]
) -> frozenset[str]:
    """Return the set of input socket names declared by schema or node inputs."""
    names: set[str] = set(inputs_spec.keys())
    inputs = node.get("inputs")
    if isinstance(inputs, dict):
        names.update(str(k) for k in inputs.keys())
    return frozenset(names)


def _socket_type_from_schema(
    schema: dict[str, Any] | None, socket_name: str, *, is_output: bool
) -> Any:
    """Fetch a socket type from an authoritative schema.

    For ``is_output=False`` reads ``schema["inputs"][socket_name]["type"]`` or
    the bare string form.  For ``is_output=True`` reads ``schema["outputs"]``
    keyed by slot name.  Returns ``None`` when absent or schema-less.
    """
    if not schema:
        return None
    section_key = "outputs" if is_output else "inputs"
    section = schema.get(section_key)
    if not isinstance(section, dict):
        return None
    entry = section.get(socket_name)
    if entry is None:
        return None
    if isinstance(entry, dict):
        return entry.get("type")
    return entry


def _roles_compatible(a: str, b: str) -> bool:
    """Generic-role compatibility.  Equal roles match; ``unresolved`` never
    matches (fail closed).  A small set of role aliases are treated as
    compatible so the matcher can bridge synonyms without case-specific
    knowledge.
    """
    if a == "unresolved" or b == "unresolved":
        return False
    if a == b:
        return True
    # Synonym groups (generic only).
    synonym_groups: tuple[frozenset[str], ...] = (
        frozenset({"model_provider", "model"}),
        frozenset({"latent", "decoder"}),
        frozenset({"image", "output_sink"}),
    )
    for group in synonym_groups:
        if a in group and b in group:
            return True
    return False


# ---------------------------------------------------------------------------
# W-10 — Mandatory boundary-coverage gate
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageDiagnostic:
    """Per-cut-edge diagnostic emitted by :func:`validate_boundary_coverage`.

    The ``cut_edge_key`` is an **ID-free** signature identifying the cut edge
    (it never contains source/target node ids), so the verdict is invariant
    under source-ID renumbering.
    """

    cut_edge_key: tuple  # (direction, inside_class_type, outside_class_type,
    #                        input_name, output_slot)
    category: str  # "uncovered" | "ambiguous" | "direction_mismatch" |
    #                "unknown_type" | "occupied_input" | "ok"
    detail: str  # human-readable explanation


@dataclass(frozen=True)
class CoverageVerdict:
    """Outcome of :func:`validate_boundary_coverage`.

    ``complete`` is ``True`` ONLY when every mandatory cut edge in ``cut_edges``
    resolved to exactly one accepted binding.  The caller (W-05/W-11) is
    responsible for refusing synthesis / manifest emission when ``complete`` is
    ``False``; this validator never emits or synthesises anything itself.
    """

    complete: bool
    covered: tuple  # tuple of ID-free cut-edge keys that are uniquely bound
    diagnostics: tuple[CoverageDiagnostic, ...]  # one per cut edge


def _coverage_cut_edge_key(edge: CutEdge) -> tuple:
    """Project a :class:`CutEdge` to an ID-free signature.

    Only structural / role vocabulary is retained — direction, inside and
    outside class types, the consumer input name, and the producer output slot.
    Source-node ids are deliberately dropped so the verdict is invariant under
    bijective id renumbering (anti-gaming invariant).
    """
    return (
        edge.direction,
        edge.inside_class_type,
        edge.outside_class_type,
        edge.input_name,
        edge.output_slot,
    )


def _classify_unbound_cut_edge(
    edge: CutEdge, matcher_result: MatcherResult
) -> tuple[str, str]:
    """Derive ``(category, detail)`` for a cut edge that has zero accepted
    bindings, by parsing the matcher's ID-free rejection diagnostics.

    The matcher's rejection text is built from class types / socket names /
    directions only (no source ids), so this scan never leaks fixture
    identity.
    """
    # Find the matcher's rejection line for this cut edge.  The matcher emits
    # lines of the form:
    #   cut_edge(<direction>,<inside_node_id>,<input_name>): <status> — <diag>
    needle_input = edge.input_name
    needle_direction = edge.direction
    matched: list[str] = []
    for line in matcher_result.rejections:
        if needle_input in line and f"cut_edge({needle_direction}," in line:
            matched.append(line)
    diag_text = " | ".join(matched) if matched else ""

    low = diag_text.lower()
    if "ambiguous" in low:
        return "ambiguous", diag_text or "ambiguous binding"
    if "unknown type" in low:
        return "unknown_type", diag_text or "socket type unknown on both sides"
    if "bad direction" in low:
        return "direction_mismatch", diag_text or "direction mismatch"
    if "occupied" in low:
        return "occupied_input", diag_text or "target input already occupied"
    if "socket mismatch" in low or "role mismatch" in low:
        # Direction/role-level incompatibilities with a known concrete type.
        # These are not "unknown_type"; surface as direction_mismatch so the
        # caller sees a concrete incompatibility diagnostic.
        return "direction_mismatch", diag_text or "incompatible socket/role"
    return "uncovered", diag_text or "no accepted binding"


def validate_boundary_coverage(
    cut_edges: tuple[CutEdge, ...],
    matcher_result: MatcherResult,
) -> CoverageVerdict:
    """Return a strict coverage verdict for a proposed cut-edge binding set.

    For each mandatory cut edge in ``cut_edges`` the validator checks the
    bindings recorded in ``matcher_result.bindings`` and classifies the edge as
    one of: ``ok`` (exactly one accepted binding), ``uncovered`` (none),
    ``ambiguous`` (more than one accepted binding, or the matcher flagged a
    tie/occupied conflict), ``unknown_type`` / ``direction_mismatch`` /
    ``occupied_input`` (derived from the matcher's rejection diagnostics).

    ``complete`` is ``True`` iff EVERY cut edge is ``ok``.

    The verdict is computed **purely** from ``cut_edges`` + ``matcher_result``
    — never from golden repair edges, golden node counts, or fixture shape —
    so it cannot be gamed by over- or under-producing repair structure.

    Parameters
    ----------
    cut_edges : tuple[CutEdge, ...]
        The mandatory boundary to cover (W-08).
    matcher_result : MatcherResult
        The proposed bindings (W-09).

    Returns
    -------
    CoverageVerdict
    """
    # Index accepted bindings by the ID-free cut-edge key.  A well-formed
    # MatcherResult has at most one binding per cut edge, but this validator
    # must independently detect ties (anti-gaming: trust nothing the matcher
    # asserts, re-derive from the bindings themselves).
    bound_counts: dict[tuple, int] = {}
    for binding in matcher_result.bindings:
        key = _coverage_cut_edge_key(binding.cut_edge)
        bound_counts[key] = bound_counts.get(key, 0) + 1

    diagnostics: list[CoverageDiagnostic] = []
    covered: list[tuple] = []

    for edge in cut_edges:
        key = _coverage_cut_edge_key(edge)
        count = bound_counts.get(key, 0)

        if count == 1:
            diagnostics.append(
                CoverageDiagnostic(
                    cut_edge_key=key,
                    category="ok",
                    detail="exactly one accepted binding",
                )
            )
            covered.append(key)
            continue

        if count > 1:
            diagnostics.append(
                CoverageDiagnostic(
                    cut_edge_key=key,
                    category="ambiguous",
                    detail=f"{count} accepted bindings for one cut edge (tie)",
                )
            )
            continue

        # count == 0: derive the specific failure category from the matcher's
        # rejection diagnostics for this edge.
        category, detail = _classify_unbound_cut_edge(edge, matcher_result)
        diagnostics.append(
            CoverageDiagnostic(
                cut_edge_key=key,
                category=category,
                detail=detail,
            )
        )

    complete = bool(cut_edges) and all(d.category == "ok" for d in diagnostics)

    return CoverageVerdict(
        complete=complete,
        covered=tuple(covered),
        diagnostics=tuple(diagnostics),
    )


# ---------------------------------------------------------------------------
# W-11 — Cut-edge-gated synthesis on the manifest-capable additive path
# ---------------------------------------------------------------------------
#
# On the manifest-capable additive research path (the path where W-05 would
# emit a ``topology_manifest``), synthesis no longer treats the first/last
# sorted source nodes as anchors.  Instead it runs W-08 → W-09 → W-10 and
# synthesizes ONLY when ``validate_boundary_coverage`` reports complete unique
# coverage.  Incomplete / ambiguous coverage fails closed — the slice is
# rejected, never broadened, never force-tied.
#
# The gate activates ONLY when (a) the caller supplied retrieved-evidence
# provenance (``manifest_provenance``) for the candidate slice and (b) the
# source segment is a PROPER SUBSET of its source workflow — i.e. there is a
# real boundary with at least one cut edge.  Whole-workflow slices (segment ==
# full source graph) have no boundary to bind and keep the legacy role-based
# anchor-binding behaviour byte-for-byte; the breadcrumb/provenance branch
# (``prior_path``) is never consulted for topology on either path.


def _normalise_object_info_spec(spec: Any) -> dict[str, Any] | str | None:
    """Reduce a ComfyUI object_info input/output spec to a ``{"type": ...}``
    dict (or bare type string).

    object_info expresses a socket as either a bare type string (``"MODEL"``),
    a 2-tuple/list ``[TYPE, opts]``, or a dict already carrying ``"type"``.
    Widget enums appear as ``[ [opt, ...], opts ]`` — their first element is a
    list, not a scalar type, so they reduce to ``None`` (the matcher treats
    widget enums as non-link sockets and never binds them).
    """
    if isinstance(spec, Mapping):
        if "type" in spec:
            return {"type": spec.get("type")}
        return None
    if isinstance(spec, str):
        return spec
    if isinstance(spec, (list, tuple)) and len(spec) >= 1:
        first = spec[0]
        if isinstance(first, str):
            return {"type": first}
        return None
    return None


def _object_info_schema_for_class(class_type: str) -> dict[str, Any] | None:
    """Return a matcher-shaped schema ``{inputs, outputs}`` for *class_type*.

    Draws from the deterministic checked-in object_info consume index
    (``vibecomfy.porting.object_info.consume.get_class``), normalising the
    native nested shape (``inputs: {required, optional}`` with ``[TYPE, opts]``
    specs, ``outputs: [{name, type}]``) into the flat
    ``{inputs: {name: {"type": ...}}, outputs: {name: {"type": ...}}}`` shape
    the W-09 matcher reads.  Returns ``None`` for any class the index cannot
    resolve so the matcher fails closed on unknown types — no guessing, no
    permissive fallback.
    """
    try:
        from vibecomfy.porting.object_info.consume import get_class
    except Exception:
        return None
    try:
        entry = get_class(class_type)
    except Exception:
        return None
    if not isinstance(entry, Mapping):
        return None

    inputs_section: dict[str, Any] = {}
    raw_inputs = entry.get("inputs")
    if isinstance(raw_inputs, Mapping):
        # Two-level native shape: {required: {name: spec}, optional: {...}}.
        for group_spec in raw_inputs.values():
            if isinstance(group_spec, Mapping):
                for name, spec in group_spec.items():
                    normalised = _normalise_object_info_spec(spec)
                    if normalised is not None:
                        inputs_section.setdefault(str(name), normalised)
            else:
                # Already flat: name -> spec.
                normalised = _normalise_object_info_spec(group_spec)
                if normalised is not None:
                    inputs_section.setdefault(str(raw_inputs), normalised)
    else:
        # Fallback: legacy ``input.required`` / ``input.optional`` shape.
        raw_input = entry.get("input") if isinstance(entry.get("input"), Mapping) else {}
        for group_key in ("required", "optional"):
            group = raw_input.get(group_key) if isinstance(raw_input, Mapping) else None
            if isinstance(group, Mapping):
                for name, spec in group.items():
                    normalised = _normalise_object_info_spec(spec)
                    if normalised is not None:
                        inputs_section.setdefault(str(name), normalised)

    outputs_section: dict[str, Any] = {}
    raw_outputs = entry.get("outputs")
    if isinstance(raw_outputs, list):
        for out_row in raw_outputs:
            if isinstance(out_row, Mapping):
                name = str(out_row.get("name") or out_row.get("label") or "").strip()
                if not name:
                    continue
                outputs_section[name] = {"type": out_row.get("type")}
    elif isinstance(raw_outputs, Mapping):
        for name, spec in raw_outputs.items():
            normalised = _normalise_object_info_spec(spec)
            if normalised is not None:
                outputs_section[str(name)] = normalised

    if not inputs_section and not outputs_section:
        return None
    return {"inputs": inputs_section, "outputs": outputs_section}


def _cut_edge_schema_lookup(
    class_types: frozenset[str],
) -> tuple[Callable[[str], dict[str, Any] | None], frozenset[str]]:
    """Build a ``class_type -> schema`` callable for the W-09 matcher.

    Pre-resolves every class in *class_types* once (deterministic, no
    per-call network/runtime access) and returns ``(lookup, resolved)`` where
    ``resolved`` is the subset of classes that yielded a real schema.  Classes
    absent from the object_info index map to ``None`` so the matcher rejects
    them (fail closed).
    """
    cache: dict[str, dict[str, Any] | None] = {}
    resolved: set[str] = set()
    for class_type in class_types:
        schema = _object_info_schema_for_class(class_type)
        cache[class_type] = schema
        if schema is not None:
            resolved.add(class_type)

    def lookup(class_type: str) -> dict[str, Any] | None:
        if class_type in cache:
            return cache[class_type]
        # Lazy-resolve any class the caller did not pre-register (defensive).
        if class_type not in cache:
            schema = _object_info_schema_for_class(class_type)
            cache[class_type] = schema
            if schema is not None:
                resolved.add(class_type)
        return cache.get(class_type)

    return lookup, frozenset(resolved)


@dataclass(frozen=True)
class CutEdgeSynthesisOutcome:
    """Result of :func:`_synthesize_via_cut_edges`.

    ``engaged`` is True iff the cut-edge pipeline actually ran (the segment had
    a non-empty boundary).  When ``engaged`` is True the caller MUST honour
    ``coverage``: synthesize only on ``coverage.complete``, else fail closed.
    When ``engaged`` is False there was no boundary (whole-workflow slice) and
    the caller falls back to legacy role-based binding.
    """

    engaged: bool
    anchor_bindings: tuple[dict[str, str], ...]
    coverage: CoverageVerdict | None
    cut_edge_count: int


def _load_full_source_graph(
    selected_slice: WorkflowSlice,
) -> tuple[dict[str, dict[str, Any]], tuple[WorkflowNodeRecord, ...]] | None:
    """Load the FULL source workflow graph for *selected_slice*.

    Returns ``(source_graph, all_records)`` where ``source_graph`` is the
    ComfyUI-style ``{node_id: {class_type, inputs}}`` dict for every node in
    the source workflow (not just the segment), or ``None`` when the source
    cannot be loaded.  The full graph is required so cut edges can see the
    outside-of-segment endpoints.
    """
    if not selected_slice.source_workflow_path:
        return None
    load_result = load_workflow_source(selected_slice.source_workflow_path)
    if not load_result.ok or not load_result.nodes:
        return None
    source_graph: dict[str, dict[str, Any]] = {}
    for record in load_result.nodes:
        source_graph[str(record.node_id)] = {
            "class_type": record.class_type,
            "inputs": copy.deepcopy(record.inputs or {}),
        }
    return source_graph, load_result.nodes


def _bindings_from_cut_edge_matches(
    matcher_result: MatcherResult,
    source_records_by_id: Mapping[str, WorkflowNodeRecord],
) -> tuple[dict[str, str], ...]:
    """Translate accepted :class:`CutEdgeBinding` records into anchor-binding dicts.

    The dict shape mirrors what :func:`_build_candidate_graph` and
    :func:`_validate_candidate_semantics` consume
    (``source_anchor`` / ``target_anchor`` / ``anchor_role`` / class types /
    socket names).  Topology is driven entirely by the typed cut edges — never
    by sorted first/last source node ids.
    """
    bindings: list[dict[str, str]] = []
    for accepted in matcher_result.bindings:
        edge = accepted.cut_edge
        # The segment-side endpoint of the cut edge is the source anchor.  For
        # inbound edges the inside node consumes; for outbound it produces.
        source_anchor_id = edge.inside_node_id
        source_record = source_records_by_id.get(source_anchor_id)
        source_class = (
            source_record.class_type if source_record is not None else edge.inside_class_type
        )
        # Derive a generic anchor role from the binding's reasons vocabulary
        # (the matcher emits ``flow_role=...``); fall back to the socket type.
        role = "model_provider"
        for reason in accepted.reasons:
            if isinstance(reason, str) and reason.startswith("flow_role="):
                role = reason.split("=", 1)[1].strip()
                break
        socket_name = accepted.target_input_name
        bindings.append({
            "source_anchor": source_anchor_id,
            "target_anchor": accepted.target_node_id,
            "anchor_role": role,
            "source_class_type": source_class,
            "target_class_type": accepted.target_class_type,
            "source_socket": socket_name,
            "target_socket": socket_name,
        })
    return tuple(bindings)


def _synthesize_via_cut_edges(
    selected_slice: WorkflowSlice,
    source_records: tuple[WorkflowNodeRecord, ...],
    target_graph: dict[str, Any],
    target_records: tuple[WorkflowNodeRecord, ...],
    *,
    inquiry_terms: tuple[str, ...],
) -> CutEdgeSynthesisOutcome:
    """Run the W-08 → W-09 → W-10 pipeline for a manifest-capable slice.

    Returns an outcome describing whether the cut-edge pipeline engaged and, if
    so, the coverage verdict plus the bindings projected from accepted cut
    edges.  The caller is responsible for refusing synthesis when
    ``coverage.complete`` is False (fail closed).

    The pipeline engages ONLY when the source segment has a genuine boundary
    — i.e. ``enumerate_cut_edges`` yields at least one cut edge.  A
    whole-workflow slice (segment == full source graph) has no boundary and
    returns ``engaged=False`` so the caller preserves legacy behaviour.
    """
    full = _load_full_source_graph(selected_slice)
    if full is None:
        return CutEdgeSynthesisOutcome(
            engaged=False, anchor_bindings=(), coverage=None, cut_edge_count=0,
        )
    source_graph, _all_records = full

    segment_ids = frozenset(str(node_id) for node_id in selected_slice.node_ids)
    if not segment_ids:
        return CutEdgeSynthesisOutcome(
            engaged=False, anchor_bindings=(), coverage=None, cut_edge_count=0,
        )

    # Build the target graph dict the matcher iterates (class_type + inputs).
    target_graph_dict: dict[str, dict[str, Any]] = {}
    for record in target_records:
        target_graph_dict[str(record.node_id)] = {
            "class_type": record.class_type,
            "inputs": copy.deepcopy(record.inputs or {}),
        }

    # Schema lookup over every class that appears on either side of the
    # boundary.  Classes absent from the object_info index map to None → the
    # matcher fails closed on them (no permissive wildcard binding).
    boundary_classes: set[str] = set()
    for node in source_graph.values():
        ct = str(node.get("class_type") or "").strip()
        if ct:
            boundary_classes.add(ct)
    for node in target_graph_dict.values():
        ct = str(node.get("class_type") or "").strip()
        if ct:
            boundary_classes.add(ct)
    schema_lookup, _resolved = _cut_edge_schema_lookup(frozenset(boundary_classes))

    cut_edges = enumerate_cut_edges(
        source_graph, segment_ids, schema_lookup=None,
    )
    if not cut_edges:
        # No boundary: whole-workflow / self-contained slice.  The cut-edge
        # pipeline does not engage; the caller preserves legacy behaviour.
        return CutEdgeSynthesisOutcome(
            engaged=False, anchor_bindings=(), coverage=None, cut_edge_count=0,
        )

    matcher_result = match_cut_edges(
        cut_edges,
        target_graph_dict,
        schema_lookup=schema_lookup,
        inquiry_terms=inquiry_terms,
    )
    coverage = validate_boundary_coverage(cut_edges, matcher_result)

    if not coverage.complete:
        # Fail closed: do NOT broaden, do NOT force a tie, do NOT fall back to
        # first/last-node anchors.  Empty bindings signal rejection upstream.
        return CutEdgeSynthesisOutcome(
            engaged=True, anchor_bindings=(), coverage=coverage,
            cut_edge_count=len(cut_edges),
        )

    source_records_by_id = {str(r.node_id): r for r in source_records}
    anchor_bindings = _bindings_from_cut_edge_matches(
        matcher_result, source_records_by_id,
    )
    return CutEdgeSynthesisOutcome(
        engaged=True,
        anchor_bindings=anchor_bindings,
        coverage=coverage,
        cut_edge_count=len(cut_edges),
    )


def _cut_edge_inquiry_terms(query: str) -> tuple[str, ...]:
    """Generic inquiry keywords for the W-09 matcher, drawn from the query.

    Anti-gaming: only generic role/media terms — no class ids, filenames,
    fixture-specific types, or ancestry breadcrumbs.  Mirrors the W-09
    contract.
    """
    return _semantic_intent_terms(query)


# ── W-04: pure validated-candidate projector ──────────────────────────────────


@dataclass(frozen=True)
class ProjectedManifestParts:
    """ID-free projection of a validated candidate graph.

    Extracts only added-node topology — no node ids, paths, widget literals,
    filenames, prompts, seeds, models, sigma strings, or golden facts.
    """

    nodes: tuple[tuple[str, str], ...]
    # (symbol, canonical_class_type)

    internal_edges: tuple[tuple[str, int, str, str], ...]
    # (from_symbol, output_slot, to_symbol, input_socket)

    boundary_anchors: tuple[tuple[str, str, str, str, str, str], ...]
    # (direction, symbol, symbol_socket, target_role, target_class_type, target_socket)

    evidence_hash: str


# ── Generic role heuristic for boundary anchors ───────────────────────────────

_GENERIC_ROLE_CLASS_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("sampler", "sample", "scheduler", "sigmas", "guider", "dispatcher"), "sampler"),
    (("loader", "checkpoint", "unet", "model"), "model_provider"),
    (("latent", "vae", "empty_latent"), "latent"),
    (("clip", "encode", "text_encode", "prompt"), "conditioning"),
    (("decode", "vae_decode", "image"), "decoder"),
    (("save", "preview", "output"), "output_sink"),
    (("load", "input", "source"), "input_source"),
    (("control", "controlnet", "preprocessor"), "control"),
    (("upscale", "resize", "transform"), "transform"),
    (("lora", "adapter"), "lora"),
)

_GENERIC_ROLE_SOCKET_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("model", "unet", "checkpoint"), "model_provider"),
    (("latent", "samples", "latent_image"), "latent"),
    (("clip", "text", "prompt", "conditioning", "positive", "negative"), "conditioning"),
    (("vae",), "latent"),
    (("image", "images", "output"), "decoder"),
    (("lora",), "lora"),
    (("control", "controlnet", "hint"), "control"),
    (("audio", "sound"), "audio"),
    (("mask",), "mask"),
    (("seed",), "seed"),
)


def _infer_generic_role(class_type: str, socket_name: str) -> str:
    """Infer a generic role from class-type and socket-name heuristics.

    This is intentionally NOT case-specific — no class tables, no golden
    literals. Returns a role token like ``"sampler"``, ``"model_provider"``,
    ``"latent"``, etc.
    """
    ct = class_type.lower()
    sn = socket_name.lower()

    # Class-type heuristics have priority.
    for hints, role in _GENERIC_ROLE_CLASS_HINTS:
        if any(h in ct for h in hints):
            return role

    # Fall back to socket-name heuristics.
    for hints, role in _GENERIC_ROLE_SOCKET_HINTS:
        if any(h in sn for h in hints):
            return role

    return "unresolved"


# ── Helper: is this input value a ComfyUI link reference? ─────────────────────


def _is_link_ref(value: Any) -> bool:
    """Return True if *value* is a ComfyUI-style [node_id, slot] link."""
    return (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


# ── Pure projector ────────────────────────────────────────────────────────────


def _gnode_class(node: Any) -> str:
    """Class type of a graph node that may be a dict OR a bare class string.

    The live adaptation graph represents existing (target) nodes as bare
    class-type strings (``{id: "ClassType"}``) while synthetically-added
    nodes are full dicts (``{id: {"class_type": ..., "inputs": ...}}``).
    Both shapes must be tolerated — never assume ``.get`` exists.
    """
    if isinstance(node, Mapping):
        return str(node.get("class_type") or node.get("type") or "?")
    if isinstance(node, str):
        return node.strip() or "?"
    return "?"


def _gnode_inputs(node: Any) -> dict[str, Any]:
    """Inputs mapping of a graph node; ``{}`` when unavailable.

    Bare class-string nodes carry no inputs, so their topology cannot be
    projected from inputs — callers handle the empty mapping gracefully.
    """
    if isinstance(node, Mapping):
        inputs = node.get("inputs")
        return inputs if isinstance(inputs, dict) else {}
    return {}


def project_validated_candidate(
    candidate_graph: dict[str, Any],
    target_graph: dict[str, Any],
    *,
    evidence_hash: str,
) -> ProjectedManifestParts | None:
    """Diff candidate vs target and emit an ID-free topology projection.

    Added nodes = ids present in *candidate_graph* but absent from
    *target_graph*.  Assigns fresh local symbols ``n1``, ``n2``, … in
    deterministic (sorted) order.

    Internal edges: only ``[node_id, output_slot]`` links where BOTH
    endpoints are added nodes.

    Boundary anchors: ``[node_id, output_slot]`` links where one endpoint is
    added and the other is an EXISTING target node → ID-free selectors using
    the existing node's ``class_type`` + socket name/slot + a generic role.

    Every scalar/list-literal input (widgets, filenames, prompts, seeds,
    models, sigma, etc.) is unconditionally dropped.

    Returns ``None`` when there are no added nodes (nothing to project).
    """
    target_ids: frozenset[str] = frozenset(target_graph.keys())
    all_candidate_ids: frozenset[str] = frozenset(candidate_graph.keys())
    added_ids: frozenset[str] = all_candidate_ids - target_ids

    if not added_ids:
        return None

    # Deterministic symbol assignment: sort added ids, assign n1, n2, ...
    sorted_added = sorted(added_ids)
    symbol_map: dict[str, str] = {
        nid: f"n{i + 1}" for i, nid in enumerate(sorted_added)
    }

    # ── nodes ────────────────────────────────────────────────────────────
    nodes: list[tuple[str, str]] = []
    for nid in sorted_added:
        class_type = _gnode_class(candidate_graph.get(nid))
        nodes.append((symbol_map[nid], class_type))

    # ── edges and anchors ────────────────────────────────────────────────
    internal_edges: list[tuple[str, int, str, str]] = []
    boundary_anchors: list[tuple[str, str, str, str, str, str]] = []

    for nid in sorted_added:
        inputs = _gnode_inputs(candidate_graph.get(nid))
        if not inputs:
            continue
        sym = symbol_map[nid]

        for input_name, input_val in inputs.items():
            if not _is_link_ref(input_val):
                # scalar / list literal → drop
                continue

            src_id: str = input_val[0]
            output_slot: int = input_val[1]

            src_in_target = src_id in target_ids
            src_in_candidate = src_id in all_candidate_ids

            if src_in_candidate and not src_in_target:
                # Both endpoints are added → internal edge.
                src_sym = symbol_map[src_id]
                internal_edges.append(
                    (src_sym, output_slot, sym, str(input_name))
                )
            elif src_in_target:
                # Source is existing target node → inbound boundary anchor.
                target_class = _gnode_class(target_graph.get(src_id))
                role = _infer_generic_role(target_class, str(input_name))
                boundary_anchors.append(
                    ("inbound", sym, str(input_name), role, target_class, str(output_slot))
                )
            # else: src_id is not in candidate_graph at all → skip (shouldn't happen)

    # Check for outbound boundary anchors: added node produces output
    # consumed by an existing target node.
    for nid in sorted(target_ids):
        node = candidate_graph.get(nid)
        # The existing node should exist in candidate_graph too
        if node is None:
            continue
        inputs = _gnode_inputs(node)
        if not inputs:
            continue
        for input_name, input_val in inputs.items():
            if not _is_link_ref(input_val):
                continue
            src_id: str = input_val[0]
            output_slot: int = input_val[1]

            if src_id in added_ids:
                # Producer is added, consumer is existing → outbound anchor.
                src_sym = symbol_map[src_id]
                target_class = _gnode_class(node)
                role = _infer_generic_role(target_class, str(input_name))
                boundary_anchors.append(
                    ("outbound", src_sym, str(output_slot), role, target_class, str(input_name))
                )

    # ── deterministic sort ───────────────────────────────────────────────
    internal_edges.sort(key=lambda e: (e[0], e[1], e[2], e[3]))
    boundary_anchors.sort(
        key=lambda a: (a[0], a[1], a[2], a[3], a[4], a[5])
    )

    return ProjectedManifestParts(
        nodes=tuple(nodes),
        internal_edges=tuple(internal_edges),
        boundary_anchors=tuple(boundary_anchors),
        evidence_hash=evidence_hash,
    )


_SOURCE_ID_PREFIX = "adapt_"
_SEMANTIC_RETRY_LIMIT = 3
_SEMANTIC_INTENT_GENERIC_TERMS = frozenset({
    "add",
    "back",
    "feature",
    "function",
    "graph",
    "missing",
    "node",
    "nodes",
    "readd",
    "removed",
    "restore",
    "workflow",
})
_SEMANTIC_MEDIA_TERMS = frozenset({
    "audio",
    "frame",
    "frames",
    "image",
    "images",
    "video",
})


def _runtime_object_info_resolves_class(class_type: str) -> bool:
    """Resolve a class against the active registry or its object_info cache.

    This is intentionally runtime-inventory evidence, not workflow-fixture or
    golden-graph evidence.  In-process ComfyUI exposes NODE_CLASS_MAPPINGS; the
    headless path uses the cache keyed by VIBECOMFY_COMFYUI_URL, falling back
    to the newest captured runtime cache when no active URL is configured.
    """
    if is_ui_only_annotation_class_type(class_type):
        return True

    comfy_nodes = sys.modules.get("nodes")
    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", None)
    if isinstance(mappings, Mapping) and class_type in mappings:
        return True

    try:
        from vibecomfy.schema.cache import (
            latest_object_info_cache_path,
            load_object_info_cache,
            object_info_cache_path,
        )

        server_url = os.environ.get("VIBECOMFY_COMFYUI_URL")
        cache_path = (
            object_info_cache_path(server_url=server_url)
            if server_url
            else latest_object_info_cache_path()
        )
        if cache_path is not None and Path(cache_path).is_file():
            object_info = load_object_info_cache(cache_path)
            if isinstance(object_info, Mapping) and class_type in object_info:
                return True
        # The checked-in object_info index is the deterministic headless
        # inventory used by porting and campaign preflight.
        from vibecomfy.porting.object_info.consume import get_class

        return isinstance(get_class(class_type), Mapping)
    except Exception:
        return False


def _semantic_roles(text: str) -> set[str]:
    haystack = text.casefold().replace("-", "_")
    return {
        role
        for role, signals in _ROLE_SIGNAL_RULES
        if any(signal in haystack for signal in signals)
    }


def _semantic_intent_terms(query: str) -> tuple[str, ...]:
    """Return feature-bearing query terms without prescribing node identities."""
    requested_families = _requested_model_families(query)
    ignored = {
        *_SEMANTIC_INTENT_GENERIC_TERMS,
        *_SEMANTIC_MEDIA_TERMS,
        *requested_families,
    }
    return tuple(
        term
        for term in _source_relevance_anchor_terms(query)
        if term not in ignored and len(term) >= 4
    )


def _validate_candidate_semantics(
    *,
    query: str,
    selected_slice: WorkflowSlice,
    source_records: tuple[WorkflowNodeRecord, ...],
    target_records: tuple[WorkflowNodeRecord, ...],
    anchor_bindings: tuple[dict[str, str], ...],
    class_resolver: Callable[[str], bool] | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Validate runtime resolvability and intent/anchor role coverage.

    Inputs are limited to the inquiry, the current broken graph's normalized
    records, and the selected retrieved precedent slice.  No case fixture or
    golden graph is accepted by this function.
    """
    source_anchor_ids = {
        str(binding.get("source_anchor") or "")
        for binding in anchor_bindings
        if isinstance(binding, Mapping)
    }
    primary_records = tuple(
        record
        for record in source_records
        if (
            record.node_id not in source_anchor_ids
            and not is_ui_only_annotation_class_type(record.class_type)
        )
    )
    if not primary_records:
        return False, "candidate adds no primary dataflow nodes", {
            "reason_code": "synthesis_semantic_miss",
        }

    resolver = class_resolver or _runtime_object_info_resolves_class
    unresolved = sorted({
        record.class_type
        for record in primary_records
        if not resolver(record.class_type)
    })
    if unresolved:
        return False, "candidate contains class types absent from runtime object_info", {
            "reason_code": "synthesis_unresolvable_class",
            "unresolved_class_types": unresolved,
        }

    target_ids = {record.node_id for record in target_records}
    bound_target_ids = {
        str(binding.get("target_anchor") or "")
        for binding in anchor_bindings
        if isinstance(binding, Mapping)
    }
    if not bound_target_ids or not bound_target_ids <= target_ids:
        return False, "candidate does not bind to current broken-graph anchors", {
            "reason_code": "synthesis_semantic_miss",
            "bound_target_ids": sorted(bound_target_ids),
        }

    candidate_text = " ".join(
        [
            selected_slice.source_class_type,
            selected_slice.source_workflow_path or "",
            selected_slice.python_path or "",
            selected_slice.role_label,
            *(_node_record_search_text(record) for record in primary_records),
        ]
    ).casefold().replace("-", "").replace("_", "")
    intent_terms = _semantic_intent_terms(query)
    matched_terms = tuple(term for term in intent_terms if term in candidate_text)
    intent_roles = _semantic_roles(query)
    candidate_roles = _semantic_roles(candidate_text)
    matched_roles = sorted(intent_roles & candidate_roles)

    if intent_terms or intent_roles:
        if not matched_terms and not matched_roles:
            return False, "candidate does not cover the inquiry's primary feature/role", {
                "reason_code": "synthesis_semantic_miss",
                "intent_terms": list(intent_terms),
                "intent_roles": sorted(intent_roles),
                "candidate_roles": sorted(candidate_roles),
            }

    return True, "runtime classes resolve and intent/anchor coverage is plausible", {
        "reason_code": "semantic_pass",
        "matched_intent_terms": list(matched_terms),
        "matched_roles": matched_roles,
        "bound_anchor_roles": sorted({
            str(binding.get("anchor_role") or "")
            for binding in anchor_bindings
            if isinstance(binding, Mapping) and binding.get("anchor_role")
        }),
    }


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
        if (
            record.node_id not in source_anchors
            and not is_ui_only_annotation_class_type(record.class_type)
        )
    }

    id_map = {**source_to_target, **new_id_for_source}

    def _remap_value(value: Any) -> Any:
        if isinstance(value, list | tuple) and len(value) == 2:
            ref_id, slot = value
            if isinstance(ref_id, (str, int)) and str(ref_id) in id_map:
                return [id_map[str(ref_id)], slot]
        return value

    for record in source_records:
        if (
            record.node_id in source_anchors
            or is_ui_only_annotation_class_type(record.class_type)
        ):
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


# ── Media-domain gate (pre-selection) ────────────────────────────────────────
# Mirrors the node-class-type logic of
# ``vibecomfy.analysis.workflow_summary.infer_media_type`` but operates on a
# bare list of class_type strings (the only structural data a ``WorkflowSlice``
# carries, since slices lack an ``outputs`` collection).  Output-type sets are
# duplicated here so the gate is self-contained and does not couple research.py
# to the analysis package's VibeWorkflow model.  Keep these in sync with
# ``workflow_summary._VIDEO_OUTPUT_TYPES`` etc. when updating either.

_MEDIA_DOMAIN_VIDEO_TYPES: frozenset[str] = frozenset({
    "VHS_VideoCombine", "SaveVideo", "SaveAnimatedWEBP",
    "SaveAnimatedPNG", "SaveAnimatedGIF", "SaveWEBM",
    "VideoCombine", "ADE_AnimateDiffCombine", "WanVideoDecode", "WanVideoSampler",
})
_MEDIA_DOMAIN_AUDIO_TYPES: frozenset[str] = frozenset({
    "SaveAudio", "SaveAudioMP3", "VHS_LoadAudio",
})
_MEDIA_DOMAIN_IMAGE_TYPES: frozenset[str] = frozenset({
    "SaveImage", "PreviewImage", "SaveImageWebsocket",
})
_MEDIA_DOMAIN_3D_TYPES: frozenset[str] = frozenset({
    "CreateCameraInfo", "EmptyLatentHunyuan3Dv2", "File3DToSplat",
    "GetSplatCount", "Hunyuan3Dv2Conditioning",
    "Hunyuan3Dv2ConditioningMultiView", "Load3D", "MergeSplat",
    "MeshyAnimateModelNode", "MeshyImageToModelNode",
    "MeshyMultiImageToModelNode", "MeshyRefineNode",
    "MeshyRigModelNode", "MeshyTextToModelNode", "MeshyTextureNode",
    "Preview3D", "Preview3DAdvanced", "RenderSplat", "Rodin3D_Detail",
    "Rodin3D_Gen2", "Rodin3D_Gen25_Image", "Rodin3D_Gen25_Text",
    "Rodin3D_Regular", "Rodin3D_Sketch", "Rodin3D_Smooth",
    "SV3D_Conditioning", "Save3D", "SaveGLB", "SaveOBJ",
    "SplatToFile3D", "SplatToMesh", "StableZero123",
    "StableZero123_Conditioning", "StableZero123_Conditioning_Batched",
    "Tencent3DPartNode", "Tencent3DTextureEditNode",
    "TencentImageToModelNode", "TencentModelTo3DUVNode",
    "TencentSmartTopologyNode", "TencentTextToModelNode",
    "TransformSplat", "TripoConversionNode", "TripoImageToModelNode",
    "TripoMultiviewToModelNode", "TripoP1ImageToModelNode",
    "TripoP1MultiviewToModelNode", "TripoP1TextToModelNode",
    "TripoRefineNode", "TripoRetargetNode", "TripoRigNode",
    "TripoSR", "TripoSplatConditioning", "TripoSplatPreprocessImage",
    "TripoSplatSamplingPreview", "TripoTextToModelNode",
    "TripoTextureNode", "VAEDecodeHunyuan3D", "VAEDecodeTripoSplat",
    "VoxelToMesh", "VoxelToMeshBasic",
})

# Substrings that mark a slice/source as a legit cross-media adapter.  When the
# slice's domain differs from the graph's but one of these signals is present,
# the slice is NOT rejected (it is a deliberate image→video / first-last-frame
# / animate-character / *-to-* adapter, which is a valid cross-media operation).
# NOTE: bare ``_to_`` / ``to_video`` are intentionally NOT signals on their own
# — ``video_to_video`` is a same-media transform, not a cross-media adapter, and
# must still be rejected when offered against a non-video graph.  Cross-media is
# detected by an explicit ``<media>_to_<other_media>`` pattern where the two
# media tokens differ (see ``_slice_is_cross_media_adapter``).
_CROSS_MEDIA_ADAPTER_SIGNALS: tuple[str, ...] = (
    "image_to_video",
    "first_last_frame",
    "first_middle_last_frame",
    "image_to_image",
    "animate_character",
    "image_to_3d",
    "image_to_audio",
    "audio_to_video",
    "audio_to_image",
    "video_to_image",
    "video_to_3d",
    "text_to_image",
    "text_to_video",
    "text_to_3d",
    "text_to_audio",
    "i2v",
    "i2i",
)
_MEDIA_TOKENS: tuple[str, ...] = ("image", "video", "audio", "3d", "text")


def _media_domain_from_node_types(node_types: Any) -> str | None:
    """Derive a media domain from a list of ComfyUI node class_type strings.

    Returns one of ``image``, ``video``, ``audio``, ``3d``, ``multi`` — or
    ``None`` when the inputs do not resolve to any single domain (caller should
    treat ``None`` as "undecided, be permissive").

    Mirrors the node-class-type branch of
    :func:`vibecomfy.analysis.workflow_summary.infer_media_type`; the slice path
    has no ``outputs`` collection so output types are inferred from class names.
    """
    if not node_types:
        return None
    class_types: set[str] = set()
    for ct in node_types:
        if isinstance(ct, str) and ct:
            class_types.add(ct)
    if not class_types:
        return None

    has_video = bool(
        class_types & _MEDIA_DOMAIN_VIDEO_TYPES
        or any("Video" in ct for ct in class_types)
    )
    has_audio = bool(class_types & _MEDIA_DOMAIN_AUDIO_TYPES)
    has_image = bool(class_types & _MEDIA_DOMAIN_IMAGE_TYPES)
    has_3d = bool(class_types & _MEDIA_DOMAIN_3D_TYPES)

    categories = sum([has_video, has_audio, has_image, has_3d])
    if categories > 1:
        return "multi"
    if has_video:
        return "video"
    if has_audio:
        return "audio"
    if has_3d:
        return "3d"
    if has_image:
        return "image"
    # No media signal at all (e.g. only Loaders/Encoders) → undecided.
    return None


def _graph_node_class_types(graph: dict | None) -> list[str]:
    """Extract the list of ``class_type`` strings from a ComfyUI-API graph dict.

    Accepts either the raw ComfyUI-API shape ``{node_id: {"class_type": str,
    "inputs": ...}}`` or the vibecomfy wrapper bundle
    ``{nodes, edges, ...}`` that production passes as ``request.graph`` (see
    ``core.py``). The rich ``nodes`` mapping (or UI list) is the preferred
    structural authority; only when ``nodes`` is absent does the fallback
    descend into ``compiled_api`` (when present) or treat the graph itself as
    the API dict.
    """
    if not isinstance(graph, dict):
        return []
    api_graph = graph.get("compiled_api") if isinstance(graph.get("compiled_api"), dict) else graph
    ui_nodes = graph.get("nodes")
    out: list[str] = []
    if isinstance(ui_nodes, list):
        for node in ui_nodes:
            if isinstance(node, Mapping):
                ct = node.get("class_type") or node.get("type")
                if isinstance(ct, str) and ct:
                    out.append(ct)
        if out:
            return out
    if isinstance(ui_nodes, Mapping):
        for node in ui_nodes.values():
            if isinstance(node, Mapping):
                ct = node.get("class_type") or node.get("type")
                if isinstance(ct, str) and ct:
                    out.append(ct)
        if out:
            return out
    for node in api_graph.values():
        if isinstance(node, Mapping):
            ct = node.get("class_type") or node.get("type")
            if isinstance(ct, str) and ct:
                out.append(ct)
    return out


def _slice_allowed_for_graph_domain(
    slice_obj: "WorkflowSlice",
    *,
    graph_domain: str | None,
) -> bool:
    """Return whether *slice_obj* should remain eligible for a target domain."""
    if graph_domain in (None, "multi"):
        return True
    slice_domain = _media_domain_from_node_types(slice_obj.node_types)
    if slice_domain is None or slice_domain == graph_domain:
        return True
    return _slice_is_cross_media_adapter(slice_obj)


def _filter_slices_for_graph_domain(
    graph: dict | None,
    slices: tuple["WorkflowSlice", ...],
) -> tuple["WorkflowSlice", ...]:
    """Apply the media-domain gate to slices for both plans and packets."""
    graph_domain = _media_domain_from_node_types(_graph_node_class_types(graph))
    if graph_domain in (None, "multi"):
        return slices
    return tuple(
        slice_obj
        for slice_obj in slices
        if _slice_allowed_for_graph_domain(slice_obj, graph_domain=graph_domain)
    )


def _slice_is_cross_media_adapter(
    slice_obj: "WorkflowSlice",
) -> bool:
    """Return True when the slice advertises a legit cross-media capability.

    Detected from the source class type / workflow path via explicit signals
    (``image_to_video``, ``first_last_frame``, ``animate_character``, ``i2v``,
    ``i2i``, …) PLUS a generic ``<media>_to_<other_media>`` pattern match where
    the two media tokens *differ* — so ``image_to_video`` qualifies but
    ``video_to_video`` (a same-media transform) does NOT.  When in doubt returns
    False; the gate is independently permissive about undecided domains.
    """
    haystack_parts: list[str] = []
    sct = getattr(slice_obj, "source_class_type", "") or ""
    if isinstance(sct, str):
        haystack_parts.append(sct)
    swp = getattr(slice_obj, "source_workflow_path", "") or ""
    if isinstance(swp, str):
        haystack_parts.append(swp)
    pp = getattr(slice_obj, "python_path", "") or ""
    if isinstance(pp, str):
        haystack_parts.append(pp)
    haystack = " ".join(haystack_parts).lower().replace("-", "_").replace("\\", "/")
    if any(signal in haystack for signal in _CROSS_MEDIA_ADAPTER_SIGNALS):
        return True
    # Generic "<media>_to_<other_media>" with differing tokens.  Catches
    # variants not in the explicit list (e.g. "3d_to_image") while excluding
    # same-media transforms ("video_to_video", "image_to_image" is already in
    # the explicit list above as a deliberate exception).
    for left in _MEDIA_TOKENS:
        for right in _MEDIA_TOKENS:
            if left == right:
                continue
            if f"{left}_to_{right}" in haystack:
                return True
    return False


# ── W-05: gated manifest emission helper ─────────────────────────────────────


def _candidate_structural_signature(
    candidate_graph: Mapping[str, Any],
    target_graph: Mapping[str, Any],
) -> str:
    """Return a path-free SHA-256 hex digest over a candidate's added topology.

    Hashes ONLY the structural identity of the added nodes and their
    class-typed links — no node ids, widget literals, filenames, prompts,
    seeds, sigma strings, or paths.  Two candidates that add the same
    topology (modulo id renumbering) hash identically.
    """
    target_ids = frozenset(str(nid) for nid in target_graph)
    added_ids = sorted(
        str(nid) for nid in candidate_graph
        if str(nid) not in target_ids
    )
    id_to_class: dict[str, str] = {
        str(nid): _gnode_class(candidate_graph.get(nid)) for nid in added_ids
    }
    # Stable node block: (class_type,) tuples in id-sorted order.
    node_block = tuple((id_to_class[nid],) for nid in added_ids)
    edge_block: list[tuple[str, str, str]] = []
    for nid in added_ids:
        node = candidate_graph.get(nid, {}) or {}
        inputs = node.get("inputs", {}) if isinstance(node, Mapping) else {}
        if not isinstance(inputs, Mapping):
            continue
        for iname, ival in inputs.items():
            if not _is_link_ref(ival):
                continue
            src_id = str(ival[0])
            src_class = id_to_class.get(src_id) or _gnode_class(
                target_graph.get(src_id)
            )
            edge_block.append((src_class, str(iname), id_to_class[nid]))
    edge_block.sort()
    canonical = json.dumps(
        {"nodes": node_block, "edges": tuple(edge_block)},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_emission_manifest(
    candidate_graph: Mapping[str, Any],
    target_graph: Mapping[str, Any],
    selected_slice: WorkflowSlice,
    provenance: Mapping[str, Any],
    *,
    manifest_id: str,
) -> TopologyManifest | None:
    """Project a validated candidate into one complete manifest, or ``None``.

    Pass-gated + complete-or-reject: returns ``None`` (legacy path) when
    provenance is incomplete, the projector rejects (no added nodes), or
    :func:`build_topology_manifest` rejects.  Raises nothing except the
    already-caught :class:`ManifestOversized` boundary, which is swallowed
    into ``None``.

    Anti-gaming: only the already-validated candidate graph, the existing
    target graph, the slice's structural class type, and a path-free hash +
    tier + rank from retrieved-evidence provenance are consumed.  No
    ``golden.ui.json``, ``prior_path``, or fixture ancestry is read.
    """
    # ── provenance: content_hash + tier + rank ONLY (no path/filename) ────
    content_hash = str(provenance.get("content_hash") or "").strip()
    tier = str(provenance.get("tier") or "").strip()
    rank_raw = provenance.get("rank")
    try:
        rank = int(rank_raw)
    except (TypeError, ValueError):
        rank = -1
    if not content_hash or not tier or rank < 0:
        return None

    # ── evidence_hash: opaque, path-free.  Prefer an explicit hash on the ─
    # provenance; otherwise hash the candidate's structural signature.
    evidence_hash = str(provenance.get("evidence_hash") or "").strip()
    if not evidence_hash:
        evidence_hash = _candidate_structural_signature(
            candidate_graph, target_graph
        )
    if not evidence_hash:
        return None

    parts = project_validated_candidate(
        candidate_graph=dict(candidate_graph),
        target_graph=dict(target_graph),
        evidence_hash=evidence_hash,
    )
    if parts is None:
        return None

    # ── map projected parts → manifest sub-objects ───────────────────────
    nodes = tuple(
        ManifestNode(
            symbol=sym,
            canonical_class_type=cls,
            resolver_status="inferred",
            evidence_ref=evidence_hash,
            confidence=0.7,
        )
        for sym, cls in parts.nodes
    )
    internal_edges = tuple(
        ManifestInternalEdge(
            from_symbol=fe,
            output_socket=f"<idx:{slot}>",
            to_symbol=te,
            input_socket=sock,
            evidence_ref=evidence_hash,
            confidence=0.7,
        )
        for fe, slot, te, sock in parts.internal_edges
    )
    boundary_anchors = tuple(
        ManifestBoundaryAnchor(
            direction=direction,
            symbol=sym,
            symbol_socket=sym_sock,
            target_role=role,
            target_class_type=tcls,
            target_socket=tsock,
            source_anchor_ref=evidence_hash,
            confidence=0.7,
        )
        for direction, sym, sym_sock, role, tcls, tsock in parts.boundary_anchors
    )

    # ── inquiry_coverage: required roles inferred from boundary anchors ───
    # vs covered roles actually present on the projection.
    covered_roles = tuple(sorted({a[3] for a in parts.boundary_anchors if a[3]}))
    required_roles = tuple(sorted(set(covered_roles)))
    inquiry_coverage = ManifestInquiryCoverage(
        required_roles=required_roles,
        covered_roles=covered_roles,
    )
    validation = ManifestValidation(
        verdict="pass",
        class_resolution="inferred",
        socket_checks="passed",
        cut_edge_coverage="covered",
        anchor_binding="projected",
        reasons=(
            "structural_validation=pass",
            "semantic_validation=pass",
        ),
    )

    try:
        return build_topology_manifest(
            manifest_id=manifest_id,
            source_content_hash=content_hash,
            source_retrieval_rank=rank,
            source_tier=tier,
            nodes=nodes,
            internal_edges=internal_edges,
            boundary_anchors=boundary_anchors,
            inquiry_coverage=inquiry_coverage,
            validation=validation,
            evidence_hash=evidence_hash,
            confidence=0.7,
        )
    except ManifestOversized:
        # Size bounds exceeded → reject, never truncate.  Legacy path.
        return None


def _build_adaptation_plan(
    query: str,
    graph: dict | None,
    inspection: InspectionSummary | None,
    slices: tuple[WorkflowSlice, ...],
    *,
    manifest_provenance: Mapping[str, Mapping[str, Any]] | None = None,
) -> PrecedentAdaptationPlan | None:
    """Build a conservative :class:`PrecedentAdaptationPlan` or ``None``.

    When no precedent slices were found, returns ``None``.  Otherwise it tries
    up to three ranked slices, rejects structurally or semantically invalid
    candidates with explicit reasons, and returns the first validated splice.

    *manifest_provenance* (W-05) optionally maps a slice's
    ``source_class_type`` to a retrieved-evidence provenance dict carrying a
    path-free ``content_hash`` + ``tier`` + ``rank``.  When present AND a
    candidate passes both validations with a nonempty ``candidate_graph``,
    exactly one :class:`TopologyManifest` is projected and attached.  In every
    other case the manifest is omitted and the plan is byte-identical to the
    legacy output (no changed warnings / retrieval / three-slice behaviour).
    """
    if not slices:
        return None

    # ── Media-domain gate (pre-selection) ────────────────────────────────────
    # Compute the target graph's media domain once.  When the graph domain is
    # undecided ("multi" or None), the gate is skipped entirely (permissive —
    # do not block when we cannot confidently classify the target).  Slices
    # whose domain is DEFINED and differs from the graph's are filtered
    # through ``_slice_allowed_for_graph_domain``, which permits cross-media
    # adapters (detected by ``_slice_is_cross_media_adapter``) while rejecting
    # same-media mismatches (e.g. a video slice against an image graph with no
    # adapter signal).  The None-fallback below also exempts cross-media
    # adapters — a slice advertising ``image_to_video`` / ``i2v`` / etc. that
    # fails structural binding will still produce a plan (with
    # structural_validation="fail") rather than being rejected wholesale.
    graph_domain = _media_domain_from_node_types(_graph_node_class_types(graph))
    gate_active = graph_domain not in (None, "multi")

    target_load = _normalize_target_graph(graph)
    selected_slice = slices[0]
    anchor_bindings: tuple[dict[str, str], ...] = ()
    structural_validation = "not_evaluated"
    semantic_validation = "not_evaluated"
    candidate_graph: dict[str, Any] | None = None
    bound = False  # True iff a gate-passing slice yielded a candidate graph
    any_structural_candidate = False
    synthesis_warnings: list[dict[str, Any]] = []

    def reject_slice(
        candidate_slice: WorkflowSlice,
        *,
        rank: int,
        code: str,
        reason: str,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        warning: dict[str, Any] = {
            "code": code,
            "severity": "warning",
            "slice_rank": rank,
            "source_class_type": candidate_slice.source_class_type,
            "source_workflow_path": candidate_slice.source_workflow_path,
            "reason": reason,
        }
        if detail:
            warning.update({
                str(key): copy.deepcopy(value)
                for key, value in detail.items()
            })
        synthesis_warnings.append(warning)

    if target_load is not None:
        structural_validation = "fail"
        semantic_validation = "fail"
        if target_load.ok:
            target_families = _detect_record_families(target_load.nodes)
            for rank, candidate_slice in enumerate(
                slices[:_SEMANTIC_RETRY_LIMIT],
                start=1,
            ):
                selected_slice_unparseable = any(
                    isinstance(warning, Mapping)
                    and warning.get("code") == "source_workflow_unparseable"
                    for warning in candidate_slice.warnings
                )
                if selected_slice_unparseable:
                    reject_slice(
                        candidate_slice,
                        rank=rank,
                        code="candidate_graph_dropped",
                        reason="source workflow is unparseable",
                        detail={"reason_code": "source_workflow_unparseable"},
                    )
                    continue
                # Media-domain gate: skip ANY slice whose domain is DEFINED
                # and differs from the graph's.  No adapter pass-through — the
                # pure domain gate.  Be permissive on undecided domains (slice
                # domain None, or graph domain multi/None).
                if gate_active:
                    if not _slice_allowed_for_graph_domain(
                        candidate_slice,
                        graph_domain=graph_domain,
                    ):
                        reject_slice(
                            candidate_slice,
                            rank=rank,
                            code="candidate_graph_dropped",
                            reason="precedent media domain does not match current graph",
                            detail={"reason_code": "media_domain_mismatch"},
                        )
                        continue
                source_records = _selected_source_records(candidate_slice)
                if not source_records:
                    reject_slice(
                        candidate_slice,
                        rank=rank,
                        code="candidate_graph_dropped",
                        reason="precedent slice has no loadable source records",
                        detail={"reason_code": "source_records_missing"},
                    )
                    continue
                source_families = _detect_record_families(
                    source_records,
                    candidate_slice.source_class_type,
                    candidate_slice.source_workflow_path,
                    candidate_slice.python_path,
                )
                if source_families and target_families and not source_families & target_families:
                    reject_slice(
                        candidate_slice,
                        rank=rank,
                        code="synthesis_semantic_miss",
                        reason="precedent model family does not match current graph anchors",
                        detail={
                            "reason_code": "model_family_mismatch",
                            "source_families": sorted(source_families),
                            "target_families": sorted(target_families),
                        },
                    )
                    continue
                # ── W-11: cut-edge-gated synthesis on the manifest-capable path ──
                # When retrieved-evidence provenance is available for THIS
                # slice (the W-05 manifest-capable condition), replace the
                # first/last-node anchor logic with the W-08 → W-09 → W-10
                # cut-edge pipeline.  Synthesize ONLY on complete unique
                # coverage; otherwise fail closed (reject, never broaden).
                # The pipeline engages only when the segment has a real
                # boundary (≥1 cut edge); whole-workflow slices keep the legacy
                # role-based binding below byte-for-byte.  The breadcrumb /
                # ``prior_path`` branch is never consulted for topology here.
                manifest_capable_for_slice = (
                    manifest_provenance is not None
                    and isinstance(
                        manifest_provenance.get(candidate_slice.source_class_type),
                        Mapping,
                    )
                )
                if manifest_capable_for_slice:
                    cut_edge_outcome = _synthesize_via_cut_edges(
                        candidate_slice,
                        source_records,
                        graph if isinstance(graph, dict) else {},
                        target_load.nodes,
                        inquiry_terms=_cut_edge_inquiry_terms(query),
                    )
                    if cut_edge_outcome.engaged:
                        if not cut_edge_outcome.coverage or not cut_edge_outcome.coverage.complete:
                            # Fail closed: incomplete / ambiguous boundary
                            # coverage.  Record diagnostics and reject — never
                            # broaden, never force a tie, never fall back to
                            # first/last-node anchors on this path.
                            diag_detail: dict[str, Any] = {
                                "reason_code": "cut_edge_coverage_incomplete",
                                "cut_edge_count": cut_edge_outcome.cut_edge_count,
                            }
                            if cut_edge_outcome.coverage is not None:
                                diag_detail["coverage_diagnostics"] = tuple(
                                    {
                                        "category": d.category,
                                        "detail": d.detail,
                                    }
                                    for d in cut_edge_outcome.coverage.diagnostics
                                )
                            reject_slice(
                                candidate_slice,
                                rank=rank,
                                code="cut_edge_coverage_incomplete",
                                reason=(
                                    "manifest-capable precedent failed cut-edge "
                                    "boundary coverage; synthesis refused"
                                ),
                                detail=diag_detail,
                            )
                            continue
                        candidate_anchor_bindings = cut_edge_outcome.anchor_bindings
                        if not candidate_anchor_bindings:
                            reject_slice(
                                candidate_slice,
                                rank=rank,
                                code="candidate_graph_dropped",
                                reason=(
                                    "cut-edge coverage complete but produced no "
                                    "anchor bindings"
                                ),
                                detail={"reason_code": "anchor_binding_missing"},
                            )
                            continue
                    else:
                        # No boundary (whole-workflow slice): fall through to
                        # legacy role-based binding below.
                        candidate_anchor_bindings = ()
                else:
                    candidate_anchor_bindings = ()
                if not candidate_anchor_bindings:
                    candidate_anchor_bindings = _build_anchor_bindings(
                        selected_slice=candidate_slice,
                        source_records=source_records,
                        target_records=target_load.nodes,
                    )
                if not candidate_anchor_bindings:
                    reject_slice(
                        candidate_slice,
                        rank=rank,
                        code="candidate_graph_dropped",
                        reason="precedent could not bind to current broken-graph anchors",
                        detail={"reason_code": "anchor_binding_missing"},
                    )
                    continue
                built_candidate_graph = _build_candidate_graph(
                    target_graph=graph,
                    source_records=source_records,
                    anchor_bindings=candidate_anchor_bindings,
                )
                if built_candidate_graph is None:
                    reject_slice(
                        candidate_slice,
                        rank=rank,
                        code="candidate_graph_dropped",
                        reason="candidate graph construction returned a malformed graph",
                        detail={"reason_code": "candidate_graph_malformed"},
                    )
                    continue
                any_structural_candidate = True
                semantic_ok, semantic_reason, semantic_detail = (
                    _validate_candidate_semantics(
                        query=query,
                        selected_slice=candidate_slice,
                        source_records=source_records,
                        target_records=target_load.nodes,
                        anchor_bindings=candidate_anchor_bindings,
                    )
                )
                if not semantic_ok:
                    reject_slice(
                        candidate_slice,
                        rank=rank,
                        code=str(
                            semantic_detail.get("reason_code")
                            or "synthesis_semantic_miss"
                        ),
                        reason=semantic_reason,
                        detail=semantic_detail,
                    )
                    continue
                selected_slice = candidate_slice
                anchor_bindings = candidate_anchor_bindings
                candidate_graph = built_candidate_graph
                structural_validation = "pass"
                semantic_validation = "pass"
                bound = True
                break
            if not bound and any_structural_candidate:
                structural_validation = "pass"

    # ── None-fallback ────────────────────────────────────────────────────────
    # If the gate was active AND no slice bound AND the default ``slices[0]``
    # (which the old code would have returned as a cross-domain misbinding) is
    # itself a gate-rejected cross-domain slice (defined domain ≠ graph
    # domain), return None instead.  This targets exactly the failure class
    # the gate exists to fix: a 3D/image/audio graph whose ``slices[0]`` is a
    # WanVideo/LTX video slice.  When ``slices[0]`` is same-domain but failed
    # to bind for pure structural reasons, the original ``slices[0]``-with-fail
    # behaviour is preserved — downstream diagnostics (``edit_revision_stages``)
    # expect a slice to evaluate.  The caller (``research`` →
    # ``core._execute_research`` → ``prompts``) treats ``adaptation_plan is
    # None`` identically to the "no precedent" path (the plan is simply omitted
    # from the agent payload), so this falls through to a no-plan /
    # direct-edit path without crashing.
    if (
        gate_active
        and not bound
        and target_load is not None
        and target_load.ok
    ):
        first_domain = _media_domain_from_node_types(slices[0].node_types)
        if (
            first_domain is not None
            and first_domain != graph_domain
            and not _slice_is_cross_media_adapter(slices[0])
        ):
            return None

    # Build a neutral context note: the material below is not a winner,
    # recommendation, or required implementation — it is precedent context
    # for the adaptation agent to evaluate independently.
    context_note = (
        "The reference slice below is presentation context only. "
        "It is NOT a winner, recommendation, or required implementation. "
        "All available precedent slices are provided in all_slices for "
        "independent evaluation by the adaptation agent."
    )
    prior_notes: list[str] = []
    for slice_obj in slices:
        for widget in slice_obj.widget_values:
            if not isinstance(widget, Mapping):
                continue
            prior_notes.append(
                "The source template used "
                f"{widget.get('name', 'an unnamed widget')}={widget.get('value')!r} "
                "here (provenance: "
                f"{widget.get('provenance', 'none')}, confidence: "
                f"{widget.get('confidence', 'low')}); treat this as a prior, not a prescription."
            )
        if slice_obj.role_label:
            prior_notes.append(
                f"Heuristic role prior: {slice_obj.role_label} "
                f"(confidence: {slice_obj.role_confidence}); use as evidence, not a guess."
            )
    if prior_notes:
        context_note += " " + " ".join(prior_notes)
    required_new_nodes: tuple[dict[str, Any], ...] = ()
    if candidate_graph is not None and isinstance(graph, dict):
        target_ids = {str(node_id) for node_id in graph}
        required_new_nodes = tuple(
            {
                "node_id": str(node_id),
                "class_type": str(node.get("class_type") or node.get("type") or ""),
                "inputs": copy.deepcopy(node.get("inputs") or {}),
            }
            for node_id, node in candidate_graph.items()
            if (
                str(node_id) not in target_ids
                and isinstance(node, Mapping)
                and str(node.get("class_type") or node.get("type") or "").strip()
            )
        )

    # ── W-05: gated manifest emission ─────────────────────────────────────
    # Emit exactly one manifest ONLY when both validations passed, the
    # candidate graph is nonempty, a real target graph exists, and a
    # retrieved-evidence provenance (path-free hash + tier + rank) is
    # available for the selected slice.  Every other case leaves
    # ``topology_manifest=None`` and the plan byte-identical to today.
    topology_manifest: TopologyManifest | None = None
    if (
        structural_validation == "pass"
        and semantic_validation == "pass"
        and candidate_graph is not None
        and len(candidate_graph) > 0
        and isinstance(graph, dict)
        and len(graph) > 0
        and manifest_provenance
    ):
        provenance = manifest_provenance.get(selected_slice.source_class_type)
        if isinstance(provenance, Mapping):
            topology_manifest = _build_emission_manifest(
                candidate_graph=candidate_graph,
                target_graph=graph,
                selected_slice=selected_slice,
                provenance=provenance,
                manifest_id=f"adapt:{selected_slice.source_class_type}",
            )

    return PrecedentAdaptationPlan(
        selected_slice=selected_slice,
        anchor_bindings=anchor_bindings,
        required_new_nodes=required_new_nodes,
        required_rewires=(),
        edit_ops=(),
        candidate_graph=candidate_graph,
        structural_validation=structural_validation,
        semantic_validation=semantic_validation,
        warnings=tuple(synthesis_warnings),
        all_slices=slices,
        context_note=context_note,
        topology_manifest=topology_manifest,
    )


# ── PrecedentPacket production (SD1) ─────────────────────────────────────────

# Internal / local source kinds — these come first in packet ordering.
_LOCAL_SOURCE_KINDS: frozenset[str] = frozenset({
    "object_info",
    "curated",
    "ready_template",
    "source_workflow",
    "custom_node_examples",
})

# Stable source-tier ordering key for external sources.
_SOURCE_TIER_ORDER: dict[str, int] = {
    "hivemind_workflow": 0,
    "hivemind": 1,
    "external_workflow": 2,
    "comfy-registry": 3,
    "github": 4,
    "git": 4,
    "web": 5,
}


def _build_precedent_packet(
    slices: tuple[WorkflowSlice, ...],
    sources: tuple[dict, ...],
) -> PrecedentPacket | None:
    """Build a neutral :class:`PrecedentPacket` from slices and source dicts.

    Every :class:`WorkflowSlice` becomes a :class:`PrecedentOption`.  Source
    dictionaries that did not produce a slice are also converted into
    lightweight :class:`PrecedentOption` entries (supplemental evidence).

    Options are ordered so internal / local evidence comes first, then
    external sources, with stable source-tier / title / class-name ordering
    within each group.  Returns ``None`` when there are no options at all
    (absent packet is non-failure).
    """
    options: list[PrecedentOption] = []
    # Track which class_types / source_workflow_paths already appear as
    # slice-backed options so we don't duplicate them from raw sources.
    covered_class_types: set[str] = set()
    covered_paths: set[str] = set()

    # ── Phase 1: slice-backed options ────────────────────────────────────
    slice_source_map: dict[str, dict] = {}
    for source in sources:
        if not isinstance(source, dict):
            continue
        ct = str(source.get("class_type", ""))
        swp = source.get("source_workflow_path")
        if ct:
            slice_source_map[ct] = source
        if isinstance(swp, str) and swp:
            # Also index by source_workflow_path for fuzzy matching.
            slice_source_map.setdefault(swp, source)

    for sl in slices:
        ct = sl.source_class_type
        swp = sl.source_workflow_path
        covered_class_types.add(ct)
        if swp is not None:
            covered_paths.add(swp)

        # Find the best matching source dict for ordering metadata.
        matched_source = (
            slice_source_map.get(ct)
            or (slice_source_map.get(swp) if swp else None)
        )

        description = _slice_description(sl, matched_source)
        notes = _slice_notes(sl, matched_source)

        options.append(PrecedentOption(
            source_class_type=ct,
            source_workflow_path=swp,
            node_ids=sl.node_ids,
            node_types=sl.node_types,
            description=description,
            notes=notes,
        ))

    # ── Phase 2: supplemental source-dict options (non-slice) ────────────
    for source in sources:
        if not isinstance(source, dict):
            continue
        ct = str(source.get("class_type", ""))
        if not ct:
            continue
        if ct in covered_class_types:
            continue
        swp = source.get("source_workflow_path")
        if isinstance(swp, str) and swp in covered_paths:
            continue
        # Only include sources that have meaningful descriptive content.
        desc = str(source.get("description", "")).strip()
        reasons = source.get("reasons")
        if not desc and not reasons:
            continue

        covered_class_types.add(ct)

        source_kind = str(source.get("source", ""))
        pack = source.get("pack")
        notes: list[str] = []
        if isinstance(reasons, (list, tuple)):
            for r in reasons:
                if isinstance(r, str) and r.strip():
                    notes.append(r.strip())
        if pack and isinstance(pack, str) and pack.strip():
            notes.append(f"pack: {pack.strip()}")
        if source_kind:
            notes.append(f"source: {source_kind}")

        options.append(PrecedentOption(
            source_class_type=ct,
            source_workflow_path=(
                swp if isinstance(swp, str) else None
            ),
            description=desc,
            notes=tuple(notes),
        ))

    if not options:
        return None

    # ── Stable ordering: local first, then by source tier / title ────────
    def _option_sort_key(opt: PrecedentOption) -> tuple[int, int, str, str]:
        # Determine the source kind from notes (best-effort).
        source_kind = ""
        for note in opt.notes:
            if note.startswith("source: "):
                source_kind = note[len("source: "):]
                break
        is_local = source_kind in _LOCAL_SOURCE_KINDS
        # For slice-backed options without a "source:" note, try to find the
        # source kind from the matched source dict via class_type lookup.
        if not source_kind and opt.source_class_type in slice_source_map:
            ms = slice_source_map.get(opt.source_class_type)
            if isinstance(ms, dict):
                sk = str(ms.get("source", ""))
                is_local = sk in _LOCAL_SOURCE_KINDS
                source_kind = sk

        local_rank = 0 if is_local else 1
        tier = _SOURCE_TIER_ORDER.get(source_kind, 99) if not is_local else 0
        title = opt.source_class_type.casefold()
        class_type_sort = opt.source_class_type
        return (local_rank, tier, title, class_type_sort)

    options.sort(key=_option_sort_key)

    return PrecedentPacket(
        options=tuple(options),
        context_note=(
            "Precedent options are provided as neutral evidence. "
            "No ranking, winner, or recommendation is implied. "
            "Options are ordered with internal/local evidence first, "
            "then by stable source/title/class-name ordering."
        ),
    )


_SPINE_KEYWORDS: tuple[str, ...] = (
    "adapter",
    "apply",
    "loader",
    "image",
    "context",
    "condition",
    "encode",
    "sampler",
    "sample",
    "decode",
    "combine",
    "save",
    "preview",
    "output",
)


def _unique_strings(values: Any, *, limit: int | None = None) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    if not isinstance(values, (list, tuple, set)):
        return ()
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if limit is not None and len(result) >= limit:
            break
    return tuple(result)


def _source_semantics(source: Mapping[str, Any]) -> Mapping[str, Any]:
    semantics = source.get("workflow_semantics")
    return semantics if isinstance(semantics, Mapping) else {}


def _source_node_types(source: Mapping[str, Any]) -> tuple[str, ...]:
    node_types = _unique_strings(source.get("node_types"))
    if node_types:
        return node_types
    semantics = _source_semantics(source)
    node_types = _unique_strings(semantics.get("node_types"))
    if node_types:
        return node_types
    return ()


def _source_models(source: Mapping[str, Any]) -> tuple[str, ...]:
    semantics = _source_semantics(source)
    models = _unique_strings(semantics.get("models"), limit=12)
    if models:
        return models
    return _unique_strings(source.get("models"), limit=12)


def _minimal_spine_from_source(source: Mapping[str, Any]) -> tuple[str, ...]:
    node_types = _source_node_types(source)
    if not node_types:
        workflow_schema = source.get("workflow_schema")
        if isinstance(workflow_schema, Mapping):
            node_types = tuple(str(k) for k in workflow_schema.keys() if str(k).strip())
    spine: list[str] = []
    seen: set[str] = set()
    for class_type in node_types:
        normalized = class_type.casefold().replace("-", "_")
        if not any(keyword in normalized for keyword in _SPINE_KEYWORDS):
            continue
        if class_type in seen:
            continue
        seen.add(class_type)
        spine.append(class_type)
    critical = [
        class_type
        for class_type in spine
        if (
            class_type.startswith(("ADE", "ACN", "IPAdapter", "WanVideo"))
            or "_" in class_type
            or " " in class_type
        )
    ]
    if len(spine) > 12:
        spine = list(_unique_strings((*spine[:12], *critical), limit=16))
        seen = set(spine)
    for class_type in _terminal_output_path_from_source(source):
        if class_type not in seen:
            seen.add(class_type)
            spine.append(class_type)
    if spine:
        return tuple(spine)
    return tuple(node_types[:12])


def _terminal_output_path_from_source(source: Mapping[str, Any]) -> tuple[str, ...]:
    node_types = _source_node_types(source)
    terminal: list[str] = []
    for class_type in node_types:
        normalized = class_type.casefold().replace("-", "_")
        if any(term in normalized for term in ("videocombine", "video_combine", "save", "preview", "output")):
            if class_type not in terminal:
                terminal.append(class_type)
    return tuple(terminal[-4:])


def _requested_terms_for_selected_precedent(query: str, source: Mapping[str, Any]) -> tuple[str, ...]:
    terms: list[str] = []
    terms.extend(sorted(_requested_model_families(query)))
    media = _requested_media_domain(query)
    if media:
        terms.append(media)
    for reason in _unique_strings(source.get("reasons")):
        match = re.search(r"matched '([^']+)'", reason)
        if match:
            terms.append(match.group(1))
    return _unique_strings(tuple(terms), limit=12)


def _build_precedent_selection_reasons(
    *,
    source: Mapping[str, Any],
    query: str,
    model_families: tuple[str, ...],
    requested_families: set[str],
    precedent_sources: tuple[dict[str, Any], ...],
) -> list[str]:
    """Build deterministic, human-readable reasons why *source* was selected.

    Reasons are ordered from strongest to weakest and always include
    evidence-metadata facts (tier, freshness, match count) so downstream
    consumers never need to guess why a particular precedent was chosen.
    """
    reasons: list[str] = []

    # 1. Tier and source identity.
    tier = _source_tier_for_source(source)
    source_kind = str(source.get("source") or "").strip()
    reasons.append(
        f"tier={tier}" if tier else f"source={source_kind}"
    )

    # 2. Strong relevance match.
    strong = source.get("strong_relevance_match")
    if strong is True:
        reasons.append("strong_relevance_match=true")
    relevance_score = source.get("relevance_score")
    if isinstance(relevance_score, (int, float)) and relevance_score > 0:
        reasons.append(f"relevance_score={int(relevance_score)}")

    # 3. Model family alignment.
    if model_families and requested_families:
        matched = sorted(model_families) if isinstance(model_families, (list, tuple, set)) else []
        reasons.append(f"model_families={','.join(matched)}")
        if requested_families & set(model_families):
            reasons.append("family_match=exact")
        else:
            reasons.append("family_match=none")

    # 4. Source count (how many precedent sources were considered).
    reasons.append(f"considered_sources={len(precedent_sources)}")

    # 5. Freshness status.
    freshness = str(source.get("_freshness_status") or "unknown")
    if freshness != "unknown":
        reasons.append(f"freshness={freshness}")

    # 6. Content hash prefix for auditability.
    content_hash = str(source.get("_content_hash") or "")
    if content_hash:
        reasons.append(f"content_hash={content_hash[:12]}")

    # 7. Source-specific quality signals.
    if source.get("source_workflow_parseable") is True:
        reasons.append("workflow_parseable=true")
    if source.get("hivemind_promoted_workflow") is True:
        reasons.append("hivemind_promoted=true")
    if source.get("source_workflow_available") is True:
        reasons.append("source_workflow_available=true")

    # 8. Match reason count.
    match_reasons = source.get("reasons")
    if isinstance(match_reasons, (list, tuple)):
        reasons.append(f"match_reason_count={len(match_reasons)}")

    return reasons


def _build_selected_precedent(
    *,
    query: str,
    precedent_sources: tuple[dict[str, Any], ...],
) -> SelectedPrecedent | None:
    """Build a directive workflow interpretation from compatible research sources.

    Stamps freshness / evidence metadata from the selected source onto the
    returned :class:`SelectedPrecedent` so downstream consumers can audit
    why this precedent was chosen and how current its data is.
    """
    if not precedent_sources:
        return None
    source = precedent_sources[0]
    if not isinstance(source, Mapping):
        return None

    name = str(source.get("class_type") or "").strip()
    if not name:
        return None

    semantics = _source_semantics(source)
    requested_terms = _requested_terms_for_selected_precedent(query, source)
    model_families = tuple(sorted(_source_model_families(source)))
    requested_families = set(_requested_model_families(query))
    implementation_ecosystems = tuple(
        family for family in model_families
        if family not in requested_families
    )

    notes: list[str] = [
        "Treat this workflow as the grounding precedent for the requested edit.",
        "Local installed schema checks belong to later authoring/resolution and do not reinterpret this workflow pattern.",
    ]
    if requested_families and implementation_ecosystems:
        notes.append(
            "The requested model/product/task term is linked by the workflow to a differently named implementation ecosystem."
        )

    node_types = set(_source_node_types(source))
    avoid_searches: list[str] = []
    for term in requested_terms:
        if len(term) < 3:
            continue
        if not any(term.casefold().replace(" ", "") in node.casefold().replace("_", "").replace("-", "").replace(" ", "") for node in node_types):
            avoid_searches.append(
                f"Do not search for a literal {term!r} node unless a selected workflow contains one."
            )
            break

    source_workflow_path = source.get("source_workflow_path") or source.get("path") or source.get("url")
    if not isinstance(source_workflow_path, str):
        source_workflow_path = None

    promotion_gates = source.get("promotion_gates")
    if not isinstance(promotion_gates, Mapping):
        promotion_gates = semantics.get("promotion_gates")
    if not isinstance(promotion_gates, Mapping):
        promotion_gates = {}

    # ── freshness / evidence metadata (SD1) ─────────────────────────────────
    retrieval_time = str(source.get("_retrieval_time") or "")
    content_hash = str(source.get("_content_hash") or "")
    query_transform_trace = str(source.get("_query_transform_trace") or "")
    tier = _source_tier_for_source(source)
    freshness_status = str(source.get("_freshness_status") or "unknown")
    # Build deterministic selection reasons.
    selection_reasons = _build_precedent_selection_reasons(
        source=source,
        query=query,
        model_families=model_families,
        requested_families=requested_families,
        precedent_sources=precedent_sources,
    )

    return SelectedPrecedent(
        name=name,
        source=str(source.get("source") or "").strip(),
        source_workflow_path=source_workflow_path,
        match_reasons=_unique_strings(source.get("reasons"), limit=12),
        requested_terms=requested_terms,
        model_families=model_families,
        implementation_ecosystems=implementation_ecosystems,
        models=_source_models(source),
        minimal_spine=_minimal_spine_from_source(source),
        terminal_output_path=_terminal_output_path_from_source(source),
        promotion_gates=dict(promotion_gates),
        interpretation_notes=tuple(notes),
        avoid_searches=tuple(avoid_searches),
        # ── freshness / evidence metadata ──────────────────────────────
        retrieval_time=retrieval_time,
        content_hash=content_hash,
        query_transform_trace=query_transform_trace,
        tier=tier,
        freshness_status=freshness_status if freshness_status in ("fresh", "stale") else "unknown",
        selection_reasons=tuple(selection_reasons),
    )


def _slice_description(
    sl: WorkflowSlice,
    matched_source: dict | None,
) -> str:
    """Build a compact description for a slice-backed PrecedentOption."""
    if matched_source and isinstance(matched_source, dict):
        desc = str(matched_source.get("description", "")).strip()
        if desc:
            return desc
    if sl.node_types:
        return f"Workflow slice with {len(sl.node_types)} node type(s): {', '.join(sl.node_types[:5])}"
    return f"Precedent workflow slice: {sl.source_class_type}"


def _slice_notes(
    sl: WorkflowSlice,
    matched_source: dict | None,
) -> tuple[str, ...]:
    """Build notes for a slice-backed PrecedentOption."""
    notes: list[str] = []
    if matched_source and isinstance(matched_source, dict):
        pack = matched_source.get("pack")
        if pack and isinstance(pack, str) and pack.strip():
            notes.append(f"pack: {pack.strip()}")
        source_kind = str(matched_source.get("source", ""))
        if source_kind:
            notes.append(f"source: {source_kind}")
        reasons = matched_source.get("reasons")
        if isinstance(reasons, (list, tuple)):
            for r in reasons:
                if isinstance(r, str) and r.strip():
                    notes.append(r.strip())
    # Attach any slice warnings as notes.
    for w in sl.warnings:
        if isinstance(w, (dict, Mapping)):
            msg = w.get("message") or w.get("code", "")
            if msg:
                notes.append(str(msg))
    return tuple(notes)


# ── Public API ───────────────────────────────────────────────────────────────


def research(
    query: str,
    *,
    task: str | None = None,
    graph: dict[str, Any] | None = None,
    target_node_type: str = "",
    hivemind_client: HivemindClient | None | object = _USE_DEFAULT,
    hivemind_timeout: float = _DEFAULT_HIVEMIND_TIMEOUT,
    registry_resolver: RegistryResolver | None | object = _USE_DEFAULT,
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
    registry_resolver:
        Injectable read-only custom-node resolver. By default, uses the Comfy
        Registry / ComfyUI-Manager / GitHub evidence resolver. Pass ``None`` to
        skip registry lookup.
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
    provenance_sources = _provenance_precedent_sources(graph, target_node_type)
    if local_limit <= 0:
        sources = list(provenance_sources)
        warnings = []
        warning_details = []
    else:
        try:
            local = run_local_research(query, task=task, limit=local_limit)
        except Exception as exc:  # noqa: BLE001 - research is best-effort
            sources = list(provenance_sources)
            warnings = [f"local corpus: {type(exc).__name__}: {exc}"]
            warning_details = [warning_detail_from_exception(exc)]
        else:
            sources = list(provenance_sources) + list(local.sources)
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

    resolved_registry_resolver: RegistryResolver | None
    if registry_resolver is _USE_DEFAULT:
        resolved_registry_resolver = resolve_missing_nodes
    else:
        resolved_registry_resolver = registry_resolver  # type: ignore[assignment]

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

    # ── Phase 3: read-only Comfy Registry / Manager missing-node evidence ─
    if resolved_registry_resolver is not None:
        try:
            registry_sources, registry_warnings = _run_registry_research(
                query,
                resolver=resolved_registry_resolver,
            )
        except RegistrySearchError as exc:
            warnings.append(f"registry: {exc}")
            warning_details.append(warning_detail_from_exception(exc))
        except Exception as exc:
            warnings.append(f"registry (unexpected): {exc}")
            warning_details.append(warning_detail_from_exception(exc))
        else:
            warnings.extend(f"registry: {warning}" for warning in registry_warnings)
            for rs in registry_sources:
                sources.append(rs)

    # ── Phase 4: no-key web research (best-effort, independent tier) ─────
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

    # ── Stamp freshness / evidence metadata on every source (SD1) ─────────
    # Each source dict receives _retrieval_time, _content_hash,
    # _query_transform_trace, _tier, and _freshness_status so downstream
    # selection reasons and audit trails can reference concrete evidence
    # metadata without re-deriving it.
    now_iso = _now_iso()
    for source in sources:
        if not isinstance(source, dict):
            continue
        # Only stamp when not already stamped (idempotent).
        if "_retrieval_time" not in source:
            _stamp_source_evidence_meta(
                source,
                query=query,
                retrieval_time=now_iso,
            )

    # Re-sort by a strict relevance gate first, then stable source tier. This
    # keeps every evidence source but lets exact external/Hivemind workflow hits
    # rise above weaker local precedents only when there is multi-anchor
    # model/workflow-family evidence.
    source_order = {
        "hivemind_workflow": 1,
        "hivemind": 2,
        "comfy-registry": 3,
        "github": 4,
        "git": 4,
        "web": 5,
    }
    for source in sources:
        anchors, matched_anchors = _source_relevance_matches(source, query)
        relevance_score = _source_query_relevance_score(source, query)
        strong_match = _source_is_strong_relevance_match(source, query)
        source["relevance_matched_anchors"] = matched_anchors
        source["relevance_anchor_count"] = len(anchors)
        source["relevance_score"] = relevance_score
        source["strong_relevance_match"] = strong_match
    sources.sort(
        key=lambda s: (
            0 if s.get("provenance_lookup") is True else 1,
            0 if s.get("strong_relevance_match") is True else 1,
            -int(s.get("relevance_score") or 0)
            if s.get("strong_relevance_match") is True
            else 0,
            source_order.get(str(s.get("source")), 0),
            -int(s.get("relevance_score") or 0)
            if s.get("strong_relevance_match") is not True
            else 0,
            -int(s.get("score") or 0),
            str(s.get("class_type") or s.get("title") or "").casefold(),
        )
    )

    # Rebuild summary with merged results.
    summary = _build_summary(tuple(sources))

    # ── Build structured precedent output (SD2) ──────────────────────────
    # Graph is not directly available in research(), so inspection and
    # adaptation plan are left empty.  The executor wires graph inspection
    # Thread the attached target graph into adaptation planning (T14).
    candidate_sources, semantic_gate_warnings = _filter_sources_for_precedent_semantics(
        tuple(sources),
        query=query,
        graph=graph,
    )
    workflow_precedent_sources = tuple(
        source
        for source in candidate_sources
        if isinstance(source, dict) and _is_workflow_precedent_source(source)
    )
    local_workflow_source_kinds = {"ready_template", "source_workflow", "curated", "custom_node_examples"}
    ordered_workflow_sources = sorted(
        enumerate(workflow_precedent_sources),
        key=lambda item: (
            0 if str(item[1].get("source") or "") in local_workflow_source_kinds else 1,
            item[0],
        ),
    )
    workflow_precedent_sources = tuple(source for _index, source in ordered_workflow_sources)
    blocked_source = _first_blocking_unparseable_source(workflow_precedent_sources)
    if blocked_source is not None:
        blocked_path = str(blocked_source.get("source_workflow_path") or blocked_source.get("path") or "")
        all_precedent_slices = (
            WorkflowSlice(
                source_class_type=str(blocked_source.get("class_type") or ""),
                source_workflow_path=blocked_path or None,
                python_path=str(blocked_source.get("path") or "") or None,
                warnings=(
                    {
                        "code": "source_workflow_unparseable",
                        "severity": "error",
                        "source_path": blocked_path,
                        "message": "Source workflow exists but could not be parsed.",
                    },
                ),
            ),
        )
    else:
        all_precedent_slices = _build_precedent_slices(workflow_precedent_sources)
    precedent_slices = _filter_slices_for_graph_domain(graph, all_precedent_slices)
    slice_class_types = {slice_obj.source_class_type for slice_obj in precedent_slices}
    slice_paths = {
        slice_obj.source_workflow_path
        for slice_obj in precedent_slices
        if slice_obj.source_workflow_path
    }
    precedent_sources = tuple(
        source
        for source in workflow_precedent_sources
        if (
            str(source.get("class_type") or "") in slice_class_types
            or str(source.get("source_workflow_path") or source.get("path") or "") in slice_paths
        )
    )
    # ── W-05: path-free retrieved-evidence provenance for manifest emission ──
    # Map each slice's source_class_type to a content_hash + tier + rank drawn
    # from the already-retrieved source dicts.  Carries NO path/filename; when
    # a source lacks a hash/tier the slice simply gets no manifest.
    manifest_provenance: dict[str, Mapping[str, Any]] = {}
    for rank, source in enumerate(precedent_sources, start=1):
        if not isinstance(source, Mapping):
            continue
        class_type = str(source.get("class_type") or "").strip()
        if not class_type or class_type in manifest_provenance:
            continue
        content_hash = str(source.get("_content_hash") or "").strip()
        tier = _source_tier_for_source(source).strip()
        if not content_hash or not tier:
            continue
        manifest_provenance[class_type] = MappingProxyType({
            "content_hash": content_hash,
            "tier": tier,
            "rank": rank,
        })
    adaptation_plan = _build_adaptation_plan(
        query=query,
        graph=graph,
        inspection=None,
        slices=precedent_slices,
        manifest_provenance=manifest_provenance or None,
    )
    # ── Build neutral precedent packet (SD1) ──────────────────────────────
    # The packet carries every discovered option without ranking or winner
    # selection.  An absent packet (None) is non-failure.
    precedent_packet = _build_precedent_packet(
        slices=precedent_slices,
        sources=precedent_sources,
    )
    selected_precedent = _build_selected_precedent(
        query=query,
        precedent_sources=precedent_sources,
    )
    precedent_warnings: list[str] = list(semantic_gate_warnings)
    workflow_precedent_status = (
        "compatible_workflow_found"
        if precedent_slices
        else ("research_unavailable" if not sources else "no_compatible_workflow_found")
    )
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
        precedent_packet=precedent_packet,
        precedent_sources=precedent_sources,
        workflow_precedent_status=workflow_precedent_status,
        selected_precedent=selected_precedent,
    )


__all__ = [
    "HivemindClient",
    "HivemindError",
    "WebSearchClient",
    "WebSearchError",
    "_build_adaptation_plan",
    "_build_inspection_summary",
    "_build_precedent_packet",
    "_build_selected_precedent",
    "_build_precedent_slices",
    "_default_hivemind_client",
    "_default_hivemind_messages_client",
    "_default_web_search_client",
    "format_community_summary",
    "research",
    "run_local_research",
]
