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
    query: str = "",
) -> HivemindRecordView:
    """Classify and serve one fetched Hivemind row to the research agent.

    Returns a typed :class:`HivemindRecordView`:

    * ``workflow`` — the workflow JSON was normalized through the named door
      matching its shape (``from_envelope`` / ``from_ui`` / ``from_api``) and
      ``surface_lens`` carries ``render(wf, "surface")``, the Python view;
      ``topology`` carries the B04 bounded precedent-topology projection
      (ranked by ``query``/class matches → 1-hop → 2-hop; induced edges only;
      128 nodes / 256 edges / 64 KiB rendered; always
      ``global_topology_complete=false``).  The raw workflow JSON never rides
      in the view.
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
    from vibecomfy.executor.precedents import (  # noqa: PLC0415
        project_precedent_topology,
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
        topology=project_precedent_topology(workflow, query=query),
        shape=shape,
    )


# ── Tools ────────────────────────────────────────────────────────────────────


def _hivemind_repo_search_payload(
    *,
    query: str,
    source_type: str | None,
    channel: str | None,
    author: str | None,
    date_from: str | None,
    limit: int,
    offset: int,
    timeout: float,
) -> dict[str, Any] | None:
    """Run the editable-installed hivemind repo search executor (canonical search).

    The repo executor (`python -m hivemind.executors.search.run`) searches the
    raw corpus tables with per-token ILIKE predicates and client-side ranking —
    the shape that does not blow the anon role's statement budget the way a
    multi-word phrase over ``unified_feed`` does.  Returns the parsed result
    envelope (``{"results": [...], "total": N, "has_more": bool}``), or None
    when the ``hivemind`` package is not installed (callers fall back to the
    legacy transport).  On executor failure returns ``{"error": "..."}``.
    ``date_to`` / ``sort`` / ``model_family`` / ``capability`` / ``node_class``
    / ``has_workflow`` are not exposed by the repo CLI (it ranks relevance
    client-side and has no upper date bound); those filters are dropped.
    """
    import importlib.util
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    if importlib.util.find_spec("hivemind.executors.search.run") is None:
        return None

    argv = [sys.executable, "-m", "hivemind.executors.search.run", "--query", query]
    if source_type == "discord":
        argv += ["--kinds", "message"]
    elif source_type == "distillation":
        argv += ["--kinds", "distillation"]
    elif source_type == "workflow":
        argv += ["--kinds", "workflow"]
    if channel:
        argv += ["--channel", channel]
    if author:
        argv += ["--author", author]
    if date_from:
        argv += ["--since", date_from]
    argv += ["--limit", str(limit)]
    if offset:
        argv += ["--offset", str(offset)]

    out_path = tempfile.mktemp(suffix=".json")
    argv += ["--out", out_path]
    wall = max(15.0, float(timeout) + 10.0)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=wall)
    except subprocess.TimeoutExpired:
        return {"error": f"hivemind repo search timed out after {wall:.0f}s"}
    except Exception as exc:  # noqa: BLE001 - typed fallback for any spawn failure
        return {"error": f"hivemind repo search failed to start: {exc}"}
    try:
        if Path(out_path).exists():
            payload = json.loads(Path(out_path).read_text(encoding="utf-8"))
        else:
            payload = json.loads(proc.stdout or "{}")
    except (ValueError, OSError) as exc:
        return {"error": f"hivemind repo search returned unparseable output: {exc}"}
    finally:
        try:
            Path(out_path).unlink(missing_ok=True)
        except OSError:
            pass
    if not isinstance(payload, dict):
        return {"error": "hivemind repo search returned a non-object envelope."}
    return payload


def _repo_rows_to_hits(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Map the hivemind repo executor's normalized rows to the tool hit shape."""
    hits: list[dict[str, Any]] = []
    for row in payload.get("results") or ():
        if not isinstance(row, Mapping):
            continue
        item_id = row.get("item_id")
        if item_id is None:
            continue
        kind = str(row.get("kind") or "")
        if kind == "message":
            table = "unified_feed"
            source_type = "discord"
        elif kind == "distillation":
            table = "unified_feed"
            source_type = "distillation"
        else:
            table = "external_resources"
            source_type = "workflow"
        metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
        hits.append(
            {
                "evidence_id": f"hivemind:{table}:{item_id}",
                "source_type": source_type,
                "table": table,
                "title": row.get("title") or "",
                "body": row.get("body") or "",
                "url": row.get("url") or "",
                "author": row.get("author") or "",
                "channel": row.get("context") or "",
                "created_at": row.get("created_at"),
                "score": 0,
                "status": metadata.get("status"),
                "confidence": metadata.get("confidence"),
            }
        )
    return hits


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

    # Canonical search path: the editable-installed hivemind repo executor
    # (per-token raw-table search).  Falls back to the legacy transport only
    # when the hivemind package is not installed (e.g. test environments).
    repo_payload = _hivemind_repo_search_payload(
        query=query,
        source_type=source_type,
        channel=channel,
        author=author,
        date_from=date_from,
        limit=limit,
        offset=offset,
        timeout=timeout,
    )
    if repo_payload is not None:
        if "error" in repo_payload:
            return ToolResult(
                tool_name=HIVE_MIND_SEARCH_TOOL,
                status=ToolStatus.UNAVAILABLE,
                result={"query": query, "error": repo_payload["error"]},
                diagnostics=(
                    ToolDiagnostic(
                        code="hivemind_repo_search_failed",
                        message=str(repo_payload["error"]),
                    ),
                ),
            )
        hits = _repo_rows_to_hits(repo_payload)
        has_more = bool(repo_payload.get("has_more"))
        if not hits:
            return ToolResult(
                tool_name=HIVE_MIND_SEARCH_TOOL,
                status=ToolStatus.NO_RESULTS,
                result={"query": query, "count": 0, "hits": [], "has_more": False},
            )
        return ToolResult(
            tool_name=HIVE_MIND_SEARCH_TOOL,
            status=ToolStatus.OK,
            result={
                "query": query,
                "count": len(hits),
                "hits": hits,
                "next_cursor": _encode_cursor(offset + limit) if has_more else None,
                "has_more": has_more,
                "total": int(repo_payload.get("total") or len(hits)),
            },
            evidence_ids=tuple(hit["evidence_id"] for hit in hits),
        )

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
