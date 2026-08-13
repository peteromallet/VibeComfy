"""Unit tests for the research source-tier canonicalization / omit resolver.

Locks the B03 omit-default contract:

* ``None`` / ``()`` / ``[]`` are OMISSION, not "search nothing".
* Research-only omission → ``("messages", "web")``; other routes → ``("workflows",)``.
* Explicit non-empty ``sources=`` wins with NO union.
* Classify ``source_preferences`` are never read here (prompt-visible only).

No HTTP, no ``core`` import, no deterministic search/stop decisions.
"""

from __future__ import annotations

from typing import Any

from vibecomfy.executor.research_sources import (
    _ALLOWED_RESEARCH_TIERS,
    _RESEARCH_SOURCE_ALIASES,
    canonicalize_research_sources,
    resolve_repl_research_sources,
)


def test_resolve_none_research_only_defaults_to_messages_web() -> None:
    assert resolve_repl_research_sources(None, research_only=True) == ("messages", "web")


def test_resolve_empty_tuple_is_omit_not_search_nothing() -> None:
    assert resolve_repl_research_sources((), research_only=True) == ("messages", "web")


def test_resolve_none_adapt_defaults_to_workflows() -> None:
    assert resolve_repl_research_sources(None, research_only=False) == ("workflows",)


def test_resolve_empty_list_is_omit_on_adapt() -> None:
    assert resolve_repl_research_sources([], research_only=False) == ("workflows",)


def test_resolve_explicit_web_not_unioned_with_messages() -> None:
    assert resolve_repl_research_sources(("web",), research_only=True) == ("web",)


def test_resolve_explicit_workflows_not_unioned_with_messages() -> None:
    assert resolve_repl_research_sources(("workflows",), research_only=True) == ("workflows",)


def test_resolve_explicit_messages_web_wins_as_written() -> None:
    assert resolve_repl_research_sources(("messages", "web"), research_only=False) == (
        "messages",
        "web",
    )


def test_resolve_messages_only_on_adapt_route_is_explicit() -> None:
    # Explicit sources on a non-research route are honored verbatim — no union
    # with the adapt default.
    assert resolve_repl_research_sources(("messages",), research_only=False) == ("messages",)


def test_canonicalize_aliases_discord_hivemind_web() -> None:
    assert canonicalize_research_sources(["discord", "hivemind", "web"]) == (
        "messages",
        "web",
    )


def test_canonicalize_unknown_drops_to_default() -> None:
    assert canonicalize_research_sources(["nope"], default=("workflows",)) == ("workflows",)


def test_canonicalize_none_uses_default() -> None:
    assert canonicalize_research_sources(None) == ("workflows",)
    assert canonicalize_research_sources(None, default=("messages", "web")) == (
        "messages",
        "web",
    )


def test_canonicalize_empty_list_uses_default() -> None:
    assert canonicalize_research_sources([]) == ("workflows",)


def test_canonicalize_deduplicates_and_preserves_order() -> None:
    assert canonicalize_research_sources(
        ["web", "github", "messages", "web"], default=("workflows",)
    ) == ("web", "messages")


def test_canonicalize_case_and_whitespace_insensitive() -> None:
    assert canonicalize_research_sources(["  Messages ", "WEB"]) == ("messages", "web")


def test_canonicalize_non_iterable_returns_default() -> None:
    assert canonicalize_research_sources(42) == ("workflows",)


def test_canonicalize_never_raises_on_mixed_inputs() -> None:
    for value in (None, "", "workflows", ["messages", 7, None], {"web"}, 3.14, object()):
        result = canonicalize_research_sources(value)
        assert isinstance(result, tuple)
        assert all(isinstance(item, str) for item in result)


def test_allowed_tiers_and_aliases_are_consistent() -> None:
    for alias, tier in _RESEARCH_SOURCE_ALIASES.items():
        assert tier in _ALLOWED_RESEARCH_TIERS, f"alias {alias!r} -> {tier!r}"
        assert alias == alias.casefold(), f"alias {alias!r} must be casefolded"


def test_resolve_repl_returns_tuple_never_diagnostic() -> None:
    for requested in (None, (), [], ("web",), ("messages", "web"), ("workflows",)):
        resolved = resolve_repl_research_sources(
            requested, research_only=True
        )  # type: ignore[arg-type]
        assert isinstance(resolved, tuple)
        assert all(isinstance(item, str) for item in resolved)


def test_research_sources_module_has_no_http_or_core_import() -> None:
    """The module must not import core or urllib — transport-agnostic."""
    import inspect

    import vibecomfy.executor.research_sources as module

    source = inspect.getsource(module)
    assert "import urllib" not in source
    assert "requests" not in source
    assert "from vibecomfy.executor.core" not in source
