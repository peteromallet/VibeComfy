"""Explicit last-resort ``web_search`` agent tool.

Policy
------
``web_search`` is an **explicit, last-resort** agent tool and is **disabled by
default**.  Disabled calls return a visible, typed policy rejection
(:attr:`ToolStatus.REFUSED`) — never a silent omission.

The tool is never invoked automatically: there is no Hivemind-to-web fallback
in this module.  Only an agent's explicit call with the tool enabled reaches
the web, and an enabled call must state the unresolved question that prior
research failed to answer — that question is recorded in the tool trace.

Typed results follow the F01 :class:`ToolResult` contract:

* ``ok`` — results returned; raw results registered as
  :class:`EvidenceArtifact` values whose ids are returned in
  ``evidence_ids``.
* ``no_results`` — transport succeeded with no result items.
* ``rate_limited`` — transport reported throttling; ``retry_after_seconds``
  carries the backoff when known.
* ``timeout`` — transport exceeded the configured timeout.
* ``unavailable`` — transport raised a non-transient error.
* ``invalid_request`` — blank query, or an enabled call without a stated
  unresolved question.
* ``refused`` — tool disabled by policy.

Every returned :class:`ToolResult` embeds the call's trace record (including
the agent's stated unresolved question) in ``result["trace"]``, and the
stateful :class:`WebSearchTool` accumulates the full trace plus the evidence
artifacts behind the returned ``evidence_ids``.

Transport-only: no ``core``/``research``/Hivemind imports, no model calls, no
deterministic search/stop decisions.
"""

from __future__ import annotations

import hashlib
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from types import MappingProxyType
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen

from .evidence_pack import EvidenceArtifact, _check_keys, _required_text, _text_tuple
from .tool_contracts import ToolDiagnostic, ToolResult, ToolStatus, normalize_tool_status

TOOL_NAME = "web_search"

_DEFAULT_WEB_SEARCH_URL = "https://duckduckgo.com/html/"
_DEFAULT_WEB_SEARCH_TIMEOUT = 5.0  # seconds
_DEFAULT_WEB_RESULT_LIMIT = 8

# Visible policy message returned (typed) when the tool is disabled.  Defined
# at module level so the refusal path stays a pure policy gate — the executor
# never triggers this tool on its own.
_DISABLED_POLICY_MESSAGE = (
    "web_search is disabled by policy. It is a last-resort tool and is never "
    "invoked automatically as a fallback from Hivemind research; enable it "
    "explicitly before the agent may call it."
)
_UNRESOLVED_QUESTION_REQUIRED_MESSAGE = (
    "web_search is a last-resort tool: the agent must state the unresolved "
    "question that prior research failed to answer."
)


class WebSearchError(Exception):
    """Base class for transport-level web-search failures."""


class WebSearchTimeoutError(WebSearchError):
    """Transport exceeded the configured timeout."""


class WebSearchRateLimitError(WebSearchError):
    """Transport was throttled; carries the suggested backoff when known."""

    def __init__(self, *, retry_after_seconds: float | None = None) -> None:
        super().__init__("web search rate-limited")
        self.retry_after_seconds = retry_after_seconds


class WebSearchUnavailableError(WebSearchError):
    """Transport failed for a non-transient reason (HTTP error, DNS, ...)."""


WebSearchTransport = Callable[[str, float], Mapping[str, Any]]
"""``(query, timeout) -> Mapping`` returning ``{"results": [...]}``.

Result items are JSON-safe mappings; ``title`` / ``url`` / ``snippet`` keys
are read when present.  A transport reports throttling by raising
:class:`WebSearchRateLimitError` and timeouts by raising
:class:`WebSearchTimeoutError` (or a builtin ``TimeoutError``).
"""


def _parse_retry_after(value: str | None) -> float | None:
    """Parse an HTTP ``Retry-After`` header as seconds; ``None`` when unknown."""
    if not value:
        return None
    try:
        seconds = float(value.strip())
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return seconds


class _DuckDuckGoHTMLParser(HTMLParser):
    """Compact no-key DuckDuckGo SERP parser mirroring the proven research
    parser: ``result__a`` anchors carry title + url, ``result__snippet``
    anchors carry the snippet."""

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
    """Unwrap DuckDuckGo redirect links to the underlying destination URL."""
    parsed = urlparse(unescape(url))
    if parsed.path == "/l/":
        uddg = parse_qs(parsed.query).get("uddg", [""])[0]
        if uddg:
            return unquote(uddg)
    return url


def _default_web_search_transport(query: str, timeout: float) -> dict[str, Any]:
    """No-key DuckDuckGo HTML search used when no transport is injected.

    Raises :class:`WebSearchRateLimitError` on HTTP 429 (with the
    ``Retry-After`` backoff when present) and :class:`WebSearchTimeoutError`
    on timeouts; other HTTP/network failures raise
    :class:`WebSearchUnavailableError`.
    """
    url = f"{_DEFAULT_WEB_SEARCH_URL}?q={quote(query)}"
    req = Request(
        url,
        headers={
            "Accept": "text/html",
            "User-Agent": (
                "Mozilla/5.0 (compatible; vibecomfy-web-tool/1.0; "
                "+https://github.com/peteromallet/vibecomfy)"
            ),
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code == 429:
            raise WebSearchRateLimitError(
                retry_after_seconds=_parse_retry_after(
                    exc.headers.get("Retry-After") if exc.headers else None
                )
            ) from exc
        raise WebSearchUnavailableError(f"web search HTTP error {exc.code}") from exc
    except TimeoutError as exc:
        raise WebSearchTimeoutError(f"web search timed out after {timeout}s") from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise WebSearchTimeoutError(f"web search timed out after {timeout}s") from exc
        raise WebSearchUnavailableError(f"web search connection error: {exc.reason}") from exc

    parser = _DuckDuckGoHTMLParser()
    parser.feed(html)
    parser.finish_result()
    return {"results": parser.results[:_DEFAULT_WEB_RESULT_LIMIT]}


@dataclass(frozen=True)
class WebSearchTraceEntry:
    """One recorded ``web_search`` call for the tool trace.

    Always records the agent's stated unresolved question (when provided) so
    the audit trail shows what the agent was trying to resolve — even for
    policy-refused calls.  ``query`` and ``unresolved_question`` are kept
    verbatim (including blanks) so the trace stays a faithful audit record of
    what was attempted.
    """

    tool_name: str = TOOL_NAME
    query: str = field(default="")
    status: ToolStatus = ToolStatus.OK
    unresolved_question: str | None = None
    evidence_ids: tuple[str, ...] = ()
    diagnostic_codes: tuple[str, ...] = ()
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_name", _required_text(self.tool_name, "tool_name"))
        if not isinstance(self.query, str):
            raise ValueError("`query` must be a string.")
        object.__setattr__(self, "status", normalize_tool_status(self.status))
        if self.unresolved_question is not None and not isinstance(
            self.unresolved_question, str
        ):
            raise ValueError("`unresolved_question` must be a string or null.")
        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
        object.__setattr__(
            self,
            "diagnostic_codes",
            _text_tuple(self.diagnostic_codes, "diagnostic_codes"),
        )
        retry_after = self.retry_after_seconds
        if retry_after is not None:
            if isinstance(retry_after, bool) or not isinstance(retry_after, (int, float)):
                raise ValueError("`retry_after_seconds` must be a non-negative number or null.")
            retry_after = float(retry_after)
            if retry_after < 0:
                raise ValueError("`retry_after_seconds` must be non-negative.")
            if self.status is not ToolStatus.RATE_LIMITED:
                raise ValueError("`retry_after_seconds` is valid only for rate_limited entries.")
        object.__setattr__(self, "retry_after_seconds", retry_after)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_name": self.tool_name,
            "query": self.query,
            "status": self.status.value,
            "unresolved_question": self.unresolved_question,
            "evidence_ids": list(self.evidence_ids),
            "diagnostic_codes": list(self.diagnostic_codes),
        }
        if self.retry_after_seconds is not None:
            payload["retry_after_seconds"] = self.retry_after_seconds
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WebSearchTraceEntry":
        if not isinstance(payload, Mapping):
            raise ValueError("WebSearchTraceEntry must be an object.")
        _check_keys(
            payload,
            required=frozenset(
                {"tool_name", "query", "status", "unresolved_question", "evidence_ids"}
            ),
            optional=frozenset({"diagnostic_codes", "retry_after_seconds"}),
            contract="WebSearchTraceEntry",
        )
        return cls(
            tool_name=payload["tool_name"],
            query=payload["query"],
            status=payload["status"],
            unresolved_question=payload["unresolved_question"],
            evidence_ids=payload["evidence_ids"],
            diagnostic_codes=payload.get("diagnostic_codes", ()),
            retry_after_seconds=payload.get("retry_after_seconds"),
        )


class WebSearchTool:
    """Stateful ``web_search`` agent tool with an accumulated trace and
    evidence-artifact store.

    Disabled by default: every call while disabled returns a visible,
    typed :attr:`ToolStatus.REFUSED` policy rejection.  When enabled, an
    explicit ``unresolved_question`` is required so the tool stays a
    last-resort — the stated question is recorded in the tool trace.

    Parameters
    ----------
    enabled:
        Whether the agent may invoke the web.  Defaults to ``False``.
    timeout:
        Per-call transport timeout in seconds.
    transport:
        Injectable ``(query, timeout) -> Mapping`` search client.  Defaults to
        a no-key DuckDuckGo HTML transport.
    """

    def __init__(
        self,
        enabled: bool = False,
        *,
        timeout: float = _DEFAULT_WEB_SEARCH_TIMEOUT,
        transport: WebSearchTransport | None = None,
    ) -> None:
        if not isinstance(enabled, bool):
            raise ValueError("`enabled` must be a bool.")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("`timeout` must be a positive number.")
        timeout = float(timeout)
        if timeout <= 0:
            raise ValueError("`timeout` must be positive.")
        self._enabled = enabled
        self._timeout = timeout
        self._transport = transport if transport is not None else _default_web_search_transport
        self._trace: list[WebSearchTraceEntry] = []
        self._artifacts: dict[str, EvidenceArtifact] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def trace(self) -> tuple[dict[str, Any], ...]:
        """Read-only snapshot of every call, newest last."""
        return tuple(entry.to_dict() for entry in self._trace)

    @property
    def artifacts(self) -> Mapping[str, EvidenceArtifact]:
        """Evidence artifacts recorded behind the returned ``evidence_ids``."""
        return MappingProxyType(dict(sorted(self._artifacts.items())))

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(self._artifacts)

    def _complete(
        self,
        *,
        query: str,
        status: ToolStatus,
        unresolved_question: str | None,
        evidence_ids: tuple[str, ...] = (),
        diagnostic_codes: tuple[str, ...] = (),
        retry_after_seconds: float | None = None,
    ) -> ToolResult:
        """Build the typed result (trace embedded), append the trace entry,
        and return the result."""
        trace_entry = WebSearchTraceEntry(
            query=query,
            status=status,
            unresolved_question=unresolved_question,
            evidence_ids=evidence_ids,
            diagnostic_codes=diagnostic_codes,
            retry_after_seconds=retry_after_seconds,
        )
        payload: dict[str, Any] = {"query": query, "trace": trace_entry.to_dict()}
        diagnostics: tuple[ToolDiagnostic, ...] = ()
        retry_after: float | None = None
        if status is ToolStatus.INVALID_REQUEST:
            code = "web_search_invalid_query"
            if diagnostic_codes and diagnostic_codes[0] == "web_search_unresolved_question_required":
                code = "web_search_unresolved_question_required"
            message = (
                _UNRESOLVED_QUESTION_REQUIRED_MESSAGE
                if code == "web_search_unresolved_question_required"
                else "`query` must be a non-empty string without surrounding whitespace."
            )
            diagnostics = (ToolDiagnostic(code=code, message=message),)
        elif status is ToolStatus.REFUSED:
            diagnostics = (
                ToolDiagnostic(code="web_search_disabled", message=_DISABLED_POLICY_MESSAGE),
            )
        elif status is ToolStatus.RATE_LIMITED:
            retry_after = retry_after_seconds
            diagnostics = (
                ToolDiagnostic(
                    code="web_search_rate_limited",
                    message="The web-search provider rate-limited this request.",
                ),
            )
        elif status is ToolStatus.TIMEOUT:
            diagnostics = (
                ToolDiagnostic(
                    code="web_search_timeout",
                    message=f"The web-search request timed out after {self._timeout:g}s.",
                    details={"timeout_seconds": self._timeout},
                ),
            )
        elif status is ToolStatus.UNAVAILABLE:
            diagnostics = (
                ToolDiagnostic(
                    code="web_search_unavailable",
                    message="The web-search provider is unavailable.",
                ),
            )
        elif status is ToolStatus.NO_RESULTS:
            diagnostics = (
                ToolDiagnostic(
                    code="web_search_no_results",
                    message="The web search returned no results for this query.",
                ),
            )
        self._trace.append(trace_entry)
        return ToolResult(
            tool_name=TOOL_NAME,
            status=status,
            result=payload,
            evidence_ids=evidence_ids,
            diagnostics=diagnostics,
            retry_after_seconds=retry_after,
        )

    def web_search(
        self,
        query: str,
        *,
        unresolved_question: str | None = None,
    ) -> ToolResult:
        """Run one ``web_search`` call and return a typed :class:`ToolResult`.

        The returned result always carries a ``trace`` payload recording the
        agent's stated unresolved question; successful calls additionally
        return ``results`` and record ``evidence_ids`` referencing
        :class:`EvidenceArtifact` bodies in :attr:`artifacts`.
        """
        if not isinstance(query, str) or not query.strip() or query != query.strip():
            return self._complete(
                query=str(query),
                status=ToolStatus.INVALID_REQUEST,
                unresolved_question=unresolved_question,
                diagnostic_codes=("web_search_invalid_query",),
            )

        if not self._enabled:
            return self._complete(
                query=query,
                status=ToolStatus.REFUSED,
                unresolved_question=unresolved_question,
                diagnostic_codes=("web_search_disabled",),
            )

        if (
            not isinstance(unresolved_question, str)
            or not unresolved_question.strip()
            or unresolved_question != unresolved_question.strip()
        ):
            return self._complete(
                query=query,
                status=ToolStatus.INVALID_REQUEST,
                unresolved_question=unresolved_question,
                diagnostic_codes=("web_search_unresolved_question_required",),
            )

        try:
            response = self._transport(query, self._timeout)
        except WebSearchRateLimitError as exc:
            return self._complete(
                query=query,
                status=ToolStatus.RATE_LIMITED,
                unresolved_question=unresolved_question,
                diagnostic_codes=("web_search_rate_limited",),
                retry_after_seconds=exc.retry_after_seconds,
            )
        except (WebSearchTimeoutError, TimeoutError):
            return self._complete(
                query=query,
                status=ToolStatus.TIMEOUT,
                unresolved_question=unresolved_question,
                diagnostic_codes=("web_search_timeout",),
            )
        except Exception:
            return self._complete(
                query=query,
                status=ToolStatus.UNAVAILABLE,
                unresolved_question=unresolved_question,
                diagnostic_codes=("web_search_unavailable",),
            )

        items = response.get("results", []) if isinstance(response, Mapping) else []
        results: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            normalized = {
                "title": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or "").strip(),
                "snippet": str(item.get("snippet") or "").strip(),
            }
            if normalized["title"] or normalized["url"]:
                results.append(normalized)
            if len(results) >= _DEFAULT_WEB_RESULT_LIMIT:
                break

        if not results:
            return self._complete(
                query=query,
                status=ToolStatus.NO_RESULTS,
                unresolved_question=unresolved_question,
                diagnostic_codes=("web_search_no_results",),
            )

        evidence_ids = self._register_artifacts(query, results)
        trace_entry = WebSearchTraceEntry(
            query=query,
            status=ToolStatus.OK,
            unresolved_question=unresolved_question,
            evidence_ids=evidence_ids,
        )
        self._trace.append(trace_entry)
        return ToolResult(
            tool_name=TOOL_NAME,
            status=ToolStatus.OK,
            result={
                "query": query,
                "count": len(results),
                "results": results,
                "trace": trace_entry.to_dict(),
            },
            evidence_ids=evidence_ids,
        )

    def _register_artifacts(
        self,
        query: str,
        results: list[dict[str, Any]],
    ) -> tuple[str, ...]:
        """Store each result as an :class:`EvidenceArtifact` behind a stable,
        unique evidence id derived from the normalized query + rank."""
        digest = hashlib.sha256(query.strip().casefold().encode("utf-8")).hexdigest()[:12]
        evidence_ids: list[str] = []
        for rank, item in enumerate(results):
            evidence_id = f"web:{digest}:{rank:02d}"
            artifact = EvidenceArtifact(
                evidence_id=evidence_id,
                kind="web_search_result",
                body={
                    "title": item["title"],
                    "url": item["url"],
                    "snippet": item["snippet"],
                },
                source="web",
                metadata={
                    "tool": TOOL_NAME,
                    "query": query,
                    "rank": rank,
                },
            )
            self._artifacts[evidence_id] = artifact
            evidence_ids.append(evidence_id)
        return tuple(evidence_ids)


def web_search(
    query: str,
    *,
    unresolved_question: str | None = None,
    enabled: bool = False,
    timeout: float = _DEFAULT_WEB_SEARCH_TIMEOUT,
    transport: WebSearchTransport | None = None,
) -> ToolResult:
    """Agent-facing ``web_search`` tool call.

    Disabled by default: ``enabled=False`` makes every call return a visible,
    typed :attr:`ToolStatus.REFUSED` policy rejection.  When ``enabled=True``
    the call MUST state the ``unresolved_question`` the agent is answering as
    a last resort — it is recorded in the returned ``result["trace"]``.

    Returns a typed :class:`ToolResult`; successful calls record
    ``evidence_ids`` referencing raw results stored as
    :class:`EvidenceArtifact` values.
    """
    return WebSearchTool(enabled=enabled, timeout=timeout, transport=transport).web_search(
        query,
        unresolved_question=unresolved_question,
    )


__all__ = [
    "TOOL_NAME",
    "WebSearchError",
    "WebSearchRateLimitError",
    "WebSearchTimeoutError",
    "WebSearchTool",
    "WebSearchTraceEntry",
    "WebSearchTransport",
    "WebSearchUnavailableError",
    "web_search",
]
