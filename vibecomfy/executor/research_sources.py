"""Research source-tier canonicalization and REPL omit-site resolution.

This module is the single omit-site resolver for the batch REPL's
``research(...)`` statement: omitted ``sources=`` (``None`` or an empty
tuple/list) becomes the research-route default ``("messages", "web")`` on a
research-only session, and ``("workflows",)`` on every other route.  Explicit
non-empty ``sources=`` always wins with **no union** — the executor never
merges defaults into an explicit request.

Transport-only: no HTTP, no ``core`` import, no deterministic search/stop
decisions.  Classify ``source_preferences`` stay prompt-visible and are never
read here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Keep in lockstep with _RESEARCH_SOURCE_ALIASES in
# vibecomfy/porting/edit/_resolve.py:425-445.
_ALLOWED_RESEARCH_TIERS = frozenset({"workflows", "registry", "messages", "web"})

_RESEARCH_SOURCE_ALIASES: dict[str, str] = {
    "local": "workflows",
    "workflow": "workflows",
    "workflows": "workflows",
    "template": "workflows",
    "templates": "workflows",
    "registry": "registry",
    "comfy-registry": "registry",
    "comfy_registry": "registry",
    "manager": "registry",
    "comfyui-manager": "registry",
    "custom_nodes": "registry",
    "custom-nodes": "registry",
    "hivemind": "messages",
    "message": "messages",
    "messages": "messages",
    "discord": "messages",
    "web": "web",
    "github": "web",
    "internet": "web",
}

_RESEARCH_ROUTE_DEFAULT_SOURCES: tuple[str, ...] = ("messages", "web")
_EDIT_ROUTE_DEFAULT_SOURCES: tuple[str, ...] = ("workflows",)


def canonicalize_research_sources(
    value: Any,
    *,
    default: tuple[str, ...] = _EDIT_ROUTE_DEFAULT_SOURCES,
) -> tuple[str, ...]:
    """Normalize aliases; drop unknown; preserve order.

    Empty / None → ``default``. Never returns a CompactDiagnostic.
    ``_normalize_research_sources`` in _resolve.py keeps the diagnostic
    contract for invalid *explicit* sources=.
    """
    if value is None:
        return default
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        return default
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, str):
            continue
        source = _RESEARCH_SOURCE_ALIASES.get(item.strip().casefold())
        if source is None or source not in _ALLOWED_RESEARCH_TIERS or source in seen:
            continue
        seen.add(source)
        normalized.append(source)
    return tuple(normalized) if normalized else default


def resolve_repl_research_sources(
    requested: tuple[str, ...] | None,
    *,
    research_only: bool,
) -> tuple[str, ...]:
    """Single omit-site resolver.

    * Non-empty explicit ``sources=`` (already passed through
      ``_normalize_research_sources``) wins with no union.
    * ``None`` **or empty** ``()`` is omit. ``sources=[]`` is omit, not
      “search nothing.” This matches today's
      ``requested_sources or ("workflows",)`` truthiness.
    * Omitted + research-only → ``("messages", "web")``.
    * Omitted + any other route → ``("workflows",)``.
    """
    if requested:
        return requested
    if research_only:
        return _RESEARCH_ROUTE_DEFAULT_SOURCES
    return _EDIT_ROUTE_DEFAULT_SOURCES
