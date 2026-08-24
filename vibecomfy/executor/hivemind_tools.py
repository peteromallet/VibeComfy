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
from .contracts import (
    HivemindRecordView,
    RECORD_TYPE_MALFORMED,
    RECORD_TYPE_NON_WORKFLOW,
    RECORD_TYPE_WORKFLOW,
)
from .tool_contracts import ToolDiagnostic, ToolResult, ToolStatus

HIVE_MIND_SEARCH_TOOL = "hivemind_search"
HIVE_MIND_GET_TOOL = "hivemind_get"

_HIVEMIND_TOOL_MAX_LIMIT = 20
_HIVEMIND_TOOL_DEFAULT_LIMIT = 5
# HIVEMIND-SEARCH-SHAPE S4: per-request budget sized to measured lean-query
# latency (~0.13-0.54s live) with ample headroom for one 57014 degrade retry,
# replacing the old 5.0s shared-deadline posture that 21/26 searches exhausted.
_HIVEMIND_TOOL_DEFAULT_TIMEOUT = 10.0

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
    if reason == "http" and exc.statement_timeout:
        # REC-A soft miss: the query is valid, Postgres just hit its
        # statement-time budget (SQLSTATE 57014) after the retry budget.
        # Typed UNAVAILABLE with a distinct code so the research loop can
        # treat one bad search as a transient miss, not a hard failure.
        return ToolResult(
            tool_name=tool_name,
            status=ToolStatus.UNAVAILABLE,
            diagnostics=(
                ToolDiagnostic(
                    code="hivemind_statement_timeout",
                    message=f"Hivemind statement timeout (retried once): {exc}",
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


# ── IR-shaped record serving (batch 13) ──────────────────────────────────────
#
# A fetched Hivemind record is served to the research agent as a typed view:
# a workflow record (a workflow JSON from the corpus) is normalized through
# the named ingest doors (from_ui / from_api / from_envelope per detected
# shape — the batch-2 doors) and served as the surface lens
# (``render(wf, "surface")``, the Python view); a non-workflow record (a
# message, a text post, a non-workflow JSON) is typed non-workflow evidence
# with its actual content; a workflow-shaped record that fails the named-door
# normalization is typed malformed with the error.  The raw source row is
# retained only in the evidence artifact body (the raw body), never in the
# model-facing view.

# Where a corpus row carries its workflow JSON: external_resources rows keep
# the parsed workflow under ``payload.workflow_json`` (with ``payload.workflow``
# as a legacy alias); some rows mirror it under ``metadata``.
_WORKFLOW_JSON_CONTAINERS = (
    ("payload", "workflow_json"),
    ("payload", "workflow"),
    ("metadata", "workflow_json"),
    ("metadata", "workflow"),
)


def _row_source_type(row: Mapping[str, Any]) -> str:
    """Source type of a Hivemind row (workflow / distillation / discord)."""
    kind = str(row.get("kind") or "")
    if kind == "workflow":
        return "workflow"
    if kind == "distillation":
        return "distillation"
    return "discord"


def _thaw_jsonish(value: Any) -> Any:
    """Deep-convert frozen JSON (MappingProxyType / tuple) to plain shapes.

    :class:`ToolResult` freezes result JSON (dicts become MappingProxyType,
    lists become tuples); the named ingest doors expect plain dict/list
    shapes, so the workflow JSON is thawed before shape detection.
    """
    if isinstance(value, Mapping):
        return {str(key): _thaw_jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_jsonish(item) for item in value]
    return value


def _extract_workflow_json(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """The workflow JSON carried by a corpus row, or None when absent.

    Only a JSON object counts — a workflow row whose ``workflow_json`` is a
    string, list, or null has no normalizable workflow and is served as a
    typed malformed record, never normalized with a fake shape.  The result
    is thawed to plain dict/list shapes for the ingest doors.
    """
    for container_key, json_key in _WORKFLOW_JSON_CONTAINERS:
        container = row.get(container_key)
        if not isinstance(container, Mapping):
            continue
        candidate = container.get(json_key)
        if isinstance(candidate, Mapping):
            return _thaw_jsonish(candidate)
    return None


def _record_text(row: Mapping[str, Any]) -> str:
    """The actual text content of a non-workflow record (body/text)."""
    for key in ("body", "content", "description", "text"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def serve_hivemind_record(
    row: Mapping[str, Any],
    *,
    evidence_id: str,
) -> HivemindRecordView:
    """Classify and serve one fetched Hivemind row to the research agent.

    Returns a typed :class:`HivemindRecordView`:

    * ``workflow`` — the workflow JSON was normalized through the named door
      matching its shape (``from_envelope`` / ``from_ui`` / ``from_api``) and
      ``surface_lens`` carries ``render(wf, "surface")``, the Python view.
    * ``non_workflow`` — the record is not a workflow (a message, a text post,
      a non-workflow JSON): ``content`` carries its actual text/body.  It is
      never pretended to be a workflow and never normalized with a fake shape.
    * ``malformed_record`` — the record is workflow-shaped (``kind`` workflow
      or a workflow JSON is present) but the named-door normalization failed
      (or no workflow JSON exists): ``error`` carries the failure.  It is
      never silently skipped and never served as a fake-normalized blob.

    The raw source row is never part of the returned view — it is retained
    only in the evidence artifact body (the raw body).
    """
    source_type = _row_source_type(row)
    workflow_json = _extract_workflow_json(row)
    if workflow_json is None:
        if source_type == "workflow":
            return HivemindRecordView(
                record_type=RECORD_TYPE_MALFORMED,
                evidence_id=evidence_id,
                source_type=source_type,
                error=(
                    "workflow record carries no workflow JSON in "
                    "payload/metadata; nothing to normalize"
                ),
            )
        return HivemindRecordView(
            record_type=RECORD_TYPE_NON_WORKFLOW,
            evidence_id=evidence_id,
            source_type=source_type,
            content=_record_text(row),
        )

    # Imported lazily: the ingest doors and the composable renderer are heavy
    # and only needed when a record is actually served.  This also keeps the
    # research tool module importable without pulling the ingest/porting
    # graphs into the executor's hot import path.
    from vibecomfy.ingest.normalize import (  # noqa: PLC0415
        detect_workflow_shape,
        from_api,
        from_envelope,
        from_ui,
    )
    from vibecomfy.porting.render import render  # noqa: PLC0415

    try:
        shape = detect_workflow_shape(workflow_json)
        if shape == "vibe":
            workflow = from_envelope(workflow_json)
        elif shape == "ui":
            # Offline normalizer only: the served lens must stay deterministic
            # without a live ComfyUI install (mirrors render._coerce_workflow).
            workflow = from_ui(workflow_json, use_comfy_converter=False)
        elif shape == "api":
            workflow = from_api(workflow_json)
        else:
            return HivemindRecordView(
                record_type=RECORD_TYPE_MALFORMED,
                evidence_id=evidence_id,
                source_type=source_type,
                error=f"unsupported workflow shape {shape!r}; expected ui/api/vibe",
            )
    except Exception as exc:  # noqa: BLE001 - typed, never raised
        return HivemindRecordView(
            record_type=RECORD_TYPE_MALFORMED,
            evidence_id=evidence_id,
            source_type=source_type,
            error=f"{type(exc).__name__}: {exc}",
        )
    return HivemindRecordView(
        record_type=RECORD_TYPE_WORKFLOW,
        evidence_id=evidence_id,
        source_type=source_type,
        surface_lens=render(workflow, "surface"),
        shape=shape,
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
    """Search the Hivemind corpus (lean message-content text search).

    Transport and query translation only: filters become PostgREST WHERE
    clauses, ``sort`` picks a deterministic ordering, ``cursor``/``limit``
    page the result.  Nothing here classifies the task, picks a winner, runs
    an enough-check, or decides to stop.

    Lean shape (HIVEMIND-SEARCH-SHAPE): free-text queries are distilled to
    2-4 distinctive tokens and matched as ``content.ilike`` ORs on
    ``message_feed`` only.  ``unified_feed`` is never text-searched;
    distillations are reached by id (``hivemind_get``) or via non-text
    structured filters.

    Parameters
    ----------
    query:
        Free-text query; 2-4 distinctive tokens give the best recall.
    filters:
        ``source_type`` (``workflow`` | ``discord`` | ``distillation``),
        ``model_family``, ``capability``, ``node_class``, ``channel``,
        ``author``, ``date_from`` / ``date_to`` (ISO-8601), ``has_workflow``
        (bool), ``sort`` (``relevance`` | ``recent`` | ``validated``;
        default ``relevance``).
    cursor:
        Opaque cursor from a previous page (``next_cursor``); None = first page.
    limit:
        Page size, 1..20 (default 5).
    timeout:
        Per-request transport budget in seconds (default 10), covering the
        scope fetches and the one 57014 degraded retry within a call.
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
    # Batch 13: the fetched record is served to the research agent as a typed
    # view — the surface lens for workflow records (normalized through the
    # named doors), typed non-workflow evidence, or a typed malformed record.
    # The raw row remains available under ``row`` for the evidence artifact;
    # the view is the model-facing content.
    record_view = serve_hivemind_record(row, evidence_id=evidence_id)
    return ToolResult(
        tool_name=HIVE_MIND_GET_TOOL,
        status=ToolStatus.OK,
        result={
            "evidence_id": evidence_id,
            "source_type": source_type,
            "table": table,
            "row": row,
            "record_view": record_view.to_dict(),
        },
        evidence_ids=(evidence_id,),
    )


__all__ = [
    "HIVE_MIND_GET_TOOL",
    "HIVE_MIND_SEARCH_TOOL",
    "hivemind_get",
    "hivemind_search",
    "serve_hivemind_record",
]
