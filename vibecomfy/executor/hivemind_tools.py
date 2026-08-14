"""Agent-invoked Hivemind search/get tools (research phase, A01).

Transport and query translation live in :mod:`.hivemind_clients`; this module
owns input validation, rate-limit policy (the R2-B2 cooldown circuit shared
with the pack resolver), typed status mapping, and :class:`ToolResult`
construction.  No task classification, winner selection, enough-check, or
stop decision happens here or in the transport — these tools answer one
question: "what does the Hivemind corpus contain?"

Every returned hit carries a stable, resolvable ``evidence_id`` of the form
``hivemind:<table>:<row_id>``; :func:`hivemind_get` resolves that ID back to
the full Hivemind record.

Tools are partitioned by phase: these are research-phase tools only and run
on explicit agent invocation.
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.registry.pack_resolver import (
    DEFAULT_CACHE_ROOT,
    _cooldown_active,
    _cooldown_until,
    _set_cooldown,
)

from .hivemind_clients import (
    HivemindError,
    _HIVEMIND_REST_ROOT,
    _hivemind_get_row,
    _hivemind_search_transport,
    _parse_evidence_id,
)
from .tool_contracts import ToolDiagnostic, ToolResult, ToolStatus

HIVE_MIND_SEARCH_TOOL = "hivemind_search"
HIVE_MIND_GET_TOOL = "hivemind_get"

_HIVEMIND_TOOL_MAX_LIMIT = 20
_HIVEMIND_TOOL_DEFAULT_LIMIT = 10
_HIVEMIND_TOOL_DEFAULT_TIMEOUT = 5.0  # matches research._DEFAULT_HIVEMIND_TIMEOUT

_SOURCE_TYPES = frozenset({"workflow", "discord", "distillation"})
_SORTS = frozenset({"relevance", "recent", "validated"})
_FILTER_KEYS = frozenset(
    {
        "source_type",
        "model_family",
        "capability",
        "node_class",
        "channel",
        "author",
        "date_from",
        "date_to",
        "has_workflow",
        "sort",
    }
)

# R2-B2: one shared cooldown endpoint for every Hivemind REST call so a 429 on
# search also blocks get (same Supabase quota).
_HIVEMIND_COOLDOWN_ENDPOINT = _HIVEMIND_REST_ROOT


# ── Validation helpers (all failures are typed INVALID_REQUEST) ─────────────


def _invalid(tool_name: str, code: str, message: str) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.INVALID_REQUEST,
        diagnostics=(ToolDiagnostic(code=code, message=message),),
    )


def _optional_text(value: Any, key: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str) or not value.strip():
        raise ValueError(f"`{key}` must be a non-empty string.")
    return value.strip()


def _optional_enum(value: Any, allowed: frozenset[str], key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"`{key}` must be one of: {choices}.")
    return value


def _optional_bool(value: Any, key: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"`{key}` must be a boolean.")
    return value


def _optional_date(value: Any, key: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError(f"`{key}` must be an ISO-8601 date or datetime string.")
    text = value.strip()
    if not text:
        raise ValueError(f"`{key}` must be an ISO-8601 date or datetime string.")
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"`{key}` is not a valid ISO-8601 date: {text!r}.") from None
    return text


def _decode_cursor(cursor: str | None) -> int:
    """Decode the opaque page cursor to a non-negative offset."""
    if cursor is None:
        return 0
    if not isinstance(cursor, str) or not cursor.strip():
        raise ValueError("`cursor` must be an opaque cursor from a previous page.")
    try:
        payload = json.loads(
            base64.b64decode(cursor.encode("ascii"), altchars=b"-_", validate=True)
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("`cursor` is not a valid page cursor.") from exc
    if (
        not isinstance(payload, dict)
        or isinstance(payload.get("offset"), bool)
        or not isinstance(payload.get("offset"), int)
        or payload["offset"] < 0
    ):
        raise ValueError("`cursor` is not a valid page cursor.")
    return payload["offset"]


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(
        json.dumps({"offset": offset}).encode("utf-8")
    ).decode("ascii")


# ── Rate-limit policy (R2-B2 circuit) ───────────────────────────────────────


def _cooldown_result(tool_name: str, cache_root: Path) -> ToolResult:
    until = _cooldown_until(cache_root, _HIVEMIND_COOLDOWN_ENDPOINT)
    retry_after = max(0.0, until - time.time())
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.RATE_LIMITED,
        retry_after_seconds=retry_after,
        diagnostics=(
            ToolDiagnostic(
                code="hivemind_rate_limited",
                message="Hivemind is rate-limited; cooldown active.",
            ),
        ),
    )


def _failure_result(
    tool_name: str,
    exc: HivemindError,
    *,
    cache_root: Path,
) -> ToolResult:
    """Map a transport failure to a typed ToolResult, honoring the circuit."""
    reason = exc.reason
    code = exc.status_code
    if reason == "timeout":
        return ToolResult(
            tool_name=tool_name,
            status=ToolStatus.TIMEOUT,
            diagnostics=(
                ToolDiagnostic(code="hivemind_timeout", message=str(exc)),
            ),
        )
    if reason == "http" and code == 429:
        _set_cooldown(cache_root, _HIVEMIND_COOLDOWN_ENDPOINT, exc.retry_after_seconds)
        return ToolResult(
            tool_name=tool_name,
            status=ToolStatus.RATE_LIMITED,
            retry_after_seconds=exc.retry_after_seconds,
            diagnostics=(
                ToolDiagnostic(
                    code="hivemind_rate_limited",
                    message=f"Hivemind rate-limited (429): {exc}",
                ),
            ),
        )
    if reason == "http" and code in {400, 422}:
        return ToolResult(
            tool_name=tool_name,
            status=ToolStatus.INVALID_REQUEST,
            diagnostics=(
                ToolDiagnostic(
                    code="hivemind_bad_request",
                    message=f"Hivemind rejected the request ({code}): {exc}",
                ),
            ),
        )
    if reason == "http" and code == 404:
        return ToolResult(
            tool_name=tool_name,
            status=ToolStatus.UNAVAILABLE,
            diagnostics=(
                ToolDiagnostic(
                    code="hivemind_unavailable",
                    message=f"Hivemind endpoint not found (404): {exc}",
                ),
            ),
        )
    if reason == "http":
        status = (
            ToolStatus.UNAVAILABLE
            if code is not None and code >= 500
            else ToolStatus.INVALID_REQUEST
        )
        diag_code = "hivemind_unavailable" if status is ToolStatus.UNAVAILABLE else "hivemind_http_error"
        return ToolResult(
            tool_name=tool_name,
            status=status,
            diagnostics=(
                ToolDiagnostic(code=diag_code, message=f"Hivemind HTTP error {code}: {exc}"),
            ),
        )
    # unavailable / invalid_json
    return ToolResult(
        tool_name=tool_name,
        status=ToolStatus.UNAVAILABLE,
        diagnostics=(
            ToolDiagnostic(
                code="hivemind_unavailable",
                message=f"Hivemind unavailable: {exc}",
            ),
        ),
    )


# ── Tools ───────────────────────────────────────────────────────────────────


def hivemind_search(
    query: str,
    *,
    filters: Mapping[str, Any] | None = None,
    cursor: str | None = None,
    limit: int = _HIVEMIND_TOOL_DEFAULT_LIMIT,
    timeout: float = _HIVEMIND_TOOL_DEFAULT_TIMEOUT,
    cache_root: Path | None = None,
) -> ToolResult:
    """Search the Hivemind corpus (workflows + Discord + distillations).

    Transport and query translation only: filters become PostgREST WHERE
    clauses, ``sort`` picks a deterministic ordering, ``cursor``/``limit``
    page the result.  Nothing here classifies the task, picks a winner, runs
    an enough-check, or decides to stop.

    Parameters
    ----------
    query:
        Free-text search over titles and bodies.
    filters:
        ``source_type`` (``workflow`` | ``discord`` | ``distillation``),
        ``model_family``, ``capability``, ``node_class``, ``channel``,
        ``author``, ``date_from`` / ``date_to`` (ISO-8601), ``has_workflow``
        (bool), ``sort`` (``relevance`` | ``recent`` | ``validated``;
        default ``relevance``).
    cursor:
        Opaque cursor from a previous page (``next_cursor``); None = first page.
    limit:
        Page size, 1..20.
    timeout:
        Per-request transport timeout in seconds.
    cache_root:
        R2-B2 cooldown-sentinel root (tests inject a temp dir).

    Returns a typed :class:`ToolResult`; every hit carries a stable
    ``evidence_id`` resolvable via :func:`hivemind_get`.
    """
    if not isinstance(query, str) or not query.strip():
        return _invalid(
            HIVE_MIND_SEARCH_TOOL,
            "query_required",
            "`query` must be a non-empty string.",
        )
    query = query.strip()

    if filters is not None and not isinstance(filters, Mapping):
        return _invalid(
            HIVE_MIND_SEARCH_TOOL,
            "filters_object",
            "`filters` must be an object.",
        )
    raw_filters = dict(filters) if filters is not None else {}
    unknown = sorted(set(raw_filters) - _FILTER_KEYS)
    if unknown:
        return _invalid(
            HIVE_MIND_SEARCH_TOOL,
            "unknown_filter",
            f"Unknown filter(s): {', '.join(unknown)}.",
        )

    try:
        source_type = _optional_enum(raw_filters.get("source_type"), _SOURCE_TYPES, "source_type")
        sort = _optional_enum(raw_filters.get("sort"), _SORTS, "sort") or "relevance"
        model_family = _optional_text(raw_filters.get("model_family"), "model_family")
        capability = _optional_text(raw_filters.get("capability"), "capability")
        node_class = _optional_text(raw_filters.get("node_class"), "node_class")
        channel = _optional_text(raw_filters.get("channel"), "channel")
        author = _optional_text(raw_filters.get("author"), "author")
        date_from = _optional_date(raw_filters.get("date_from"), "date_from")
        date_to = _optional_date(raw_filters.get("date_to"), "date_to")
        has_workflow = _optional_bool(raw_filters.get("has_workflow"), "has_workflow")
        offset = _decode_cursor(cursor)
    except ValueError as exc:
        return _invalid(HIVE_MIND_SEARCH_TOOL, "invalid_filter", str(exc))

    if date_from and date_to and date_from > date_to:
        return _invalid(
            HIVE_MIND_SEARCH_TOOL,
            "date_range_inverted",
            "`date_from` must not be after `date_to`.",
        )
    if isinstance(limit, bool) or not isinstance(limit, int):
        return _invalid(
            HIVE_MIND_SEARCH_TOOL,
            "limit_invalid",
            f"`limit` must be an integer between 1 and {_HIVEMIND_TOOL_MAX_LIMIT}.",
        )
    if not 1 <= limit <= _HIVEMIND_TOOL_MAX_LIMIT:
        return _invalid(
            HIVE_MIND_SEARCH_TOOL,
            "limit_invalid",
            f"`limit` must be an integer between 1 and {_HIVEMIND_TOOL_MAX_LIMIT}.",
        )
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        return _invalid(
            HIVE_MIND_SEARCH_TOOL,
            "timeout_invalid",
            "`timeout` must be a positive number of seconds.",
        )

    root = cache_root or DEFAULT_CACHE_ROOT
    if _cooldown_active(root, _HIVEMIND_COOLDOWN_ENDPOINT):
        return _cooldown_result(HIVE_MIND_SEARCH_TOOL, root)

    try:
        transport = _hivemind_search_transport(
            query=query,
            source_type=source_type,
            model_family=model_family,
            capability=capability,
            node_class=node_class,
            channel=channel,
            author=author,
            date_from=date_from,
            date_to=date_to,
            has_workflow=has_workflow,
            sort=sort,
            limit=limit,
            offset=offset,
            timeout=timeout,
        )
    except HivemindError as exc:
        return _failure_result(HIVE_MIND_SEARCH_TOOL, exc, cache_root=root)

    diagnostics = tuple(
        ToolDiagnostic(
            code="hivemind_scope_failed",
            message=item["message"],
            details={"scope": item["scope"]},
        )
        for item in transport["diagnostics"]
    )
    hits = transport["hits"]
    if not hits:
        return ToolResult(
            tool_name=HIVE_MIND_SEARCH_TOOL,
            status=ToolStatus.NO_RESULTS,
            diagnostics=diagnostics,
        )
    return ToolResult(
        tool_name=HIVE_MIND_SEARCH_TOOL,
        status=ToolStatus.OK,
        result={
            "query": query,
            "count": len(hits),
            "hits": hits,
            "next_cursor": _encode_cursor(offset + limit) if transport["has_more"] else None,
            "has_more": transport["has_more"],
        },
        evidence_ids=tuple(hit["evidence_id"] for hit in hits),
        diagnostics=diagnostics,
    )


def hivemind_get(
    evidence_id: str,
    *,
    timeout: float = _HIVEMIND_TOOL_DEFAULT_TIMEOUT,
    cache_root: Path | None = None,
) -> ToolResult:
    """Resolve one evidence ID from :func:`hivemind_search` to its full record.

    The ID must be ``hivemind:<table>:<row_id>`` for a known Hivemind table.
    Returns the full PostgREST row as the result body.
    """
    if not isinstance(evidence_id, str) or not evidence_id.strip():
        return _invalid(
            HIVE_MIND_GET_TOOL,
            "evidence_id_required",
            "`evidence_id` must be a non-empty string.",
        )
    evidence_id = evidence_id.strip()
    parsed = _parse_evidence_id(evidence_id)
    if parsed is None:
        return _invalid(
            HIVE_MIND_GET_TOOL,
            "invalid_evidence_id",
            "`evidence_id` must look like hivemind:<table>:<row_id> for a "
            "known Hivemind table.",
        )
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
        return _invalid(
            HIVE_MIND_GET_TOOL,
            "timeout_invalid",
            "`timeout` must be a positive number of seconds.",
        )
    table, row_id = parsed

    root = cache_root or DEFAULT_CACHE_ROOT
    if _cooldown_active(root, _HIVEMIND_COOLDOWN_ENDPOINT):
        return _cooldown_result(HIVE_MIND_GET_TOOL, root)

    try:
        row = _hivemind_get_row(table, row_id, timeout=timeout)
    except HivemindError as exc:
        return _failure_result(HIVE_MIND_GET_TOOL, exc, cache_root=root)
    if row is None:
        return ToolResult(
            tool_name=HIVE_MIND_GET_TOOL,
            status=ToolStatus.NO_RESULTS,
        )
    kind = str(row.get("kind") or "")
    source_type = (
        "workflow"
        if kind == "workflow"
        else ("distillation" if kind == "distillation" else "discord")
    )
    return ToolResult(
        tool_name=HIVE_MIND_GET_TOOL,
        status=ToolStatus.OK,
        result={
            "evidence_id": evidence_id,
            "source_type": source_type,
            "table": table,
            "row": row,
        },
        evidence_ids=(evidence_id,),
    )


__all__ = [
    "HIVE_MIND_GET_TOOL",
    "HIVE_MIND_SEARCH_TOOL",
    "hivemind_get",
    "hivemind_search",
]
