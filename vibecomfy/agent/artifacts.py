"""Artifact synthesis for the headless VibeComfy agent surface.

Writes a stable, redacted artifact directory that harnesses and external
consumers (e.g. Astrid) can grade without parsing narrative output.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from vibecomfy.executor.contracts import normalize_model_endpoint, redact_model_preview

LOGGER = logging.getLogger(__name__)


_FLOW_KIND = "live_agentic_headless"
_SENSITIVE_KEY_PARTS = frozenset({
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
})
_MODEL_ARTIFACT_NAMES = frozenset({
    "messages.jsonl",
    "model_attempts.json",
    "model_request.json",
    "model_response.json",
})
_SENSITIVE_URL_QUERY_PARTS = frozenset({
    "api_key",
    "apikey",
    "api-key",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
})
_URL_QUERY_CREDENTIAL_SUBSTRINGS = ("token", "secret", "api_key", "apikey", "api-key")
_AUTHORIZATION_HEADER_RE = re.compile(r"(?im)\bauthorization\s*:\s*[^\r\n]*")
_EMBEDDED_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _safe_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_safe(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _is_sensitive_key(key: str) -> bool:
    lower = key.lower()
    return any(part in lower for part in _SENSITIVE_KEY_PARTS)


def _is_credential_like_url_param(name: str) -> bool:
    lower = name.lower()
    if lower in _SENSITIVE_URL_QUERY_PARTS:
        return True
    return any(part in lower for part in _URL_QUERY_CREDENTIAL_SUBSTRINGS)


def _redact_url_credentials(url: str) -> str:
    """Redact userinfo and credential-like query params inside a URL string.

    Only credential material is touched: userinfo is replaced wholesale and
    query parameter VALUES whose names look credential-like (token/key/sig/
    signature/api_key/apikey/secret + auth headers carried as query params)
    become ``<redacted>``. Every other part of the URL is preserved byte for
    byte (oracle finding 5).
    """
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return url
    netloc = parsed.netloc
    if parsed.username is not None:
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        netloc = f"<redacted>@{host}"
    query = parsed.query
    if query:
        parts = query.split("&")
        redacted_parts: list[str] = []
        query_changed = False
        for part in parts:
            name, sep, _value = part.partition("=")
            if sep and _is_credential_like_url_param(name):
                redacted_parts.append(f"{name}=<redacted>")
                query_changed = True
            else:
                redacted_parts.append(part)
        if query_changed:
            query = "&".join(redacted_parts)
    if netloc == parsed.netloc and query == parsed.query:
        return url
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def _redact_embedded_secrets(value: str) -> str:
    """Redact authorization headers and credential-bearing URLs in ANY string.

    Ordinary leaves (``content``, ``message``, ``error``, ``url``, ...) can
    persist credentials inside prose, so every string is scanned: full
    ``Authorization: <scheme> <credential>`` header values (every scheme) are
    replaced, and credential-like URL query params / userinfo are redacted.
    Everything else is left untouched.
    """
    redacted = _AUTHORIZATION_HEADER_RE.sub("Authorization: <redacted>", value)
    redacted = _EMBEDDED_URL_RE.sub(
        lambda match: _redact_url_credentials(match.group(0)), redacted
    )
    return redacted


def _redact_string(value: str, *, parent_key: str) -> str:
    if _is_sensitive_key(parent_key):
        return "<redacted>"
    if parent_key.lower() == "endpoint":
        return normalize_model_endpoint(value)
    if parent_key.lower() == "raw_response_preview":
        return redact_model_preview(value) or ""
    return _redact_embedded_secrets(value)


def _redact(value: Any, *, parent_key: str = "") -> Any:
    """Return a JSON-safe copy with credential-like values redacted.

    Walks the artifact recursively and sanitizes EVERY persisted string leaf:
    values under sensitive keys are replaced wholesale, ``endpoint`` and
    ``raw_response_preview`` use their canonical redactors, and ordinary fields
    are scanned for embedded authorization headers and credential-bearing URLs.
    """
    if isinstance(value, str):
        return _redact_string(value, parent_key=parent_key)
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            redacted[key_text] = _redact(item, parent_key=key_text)
        return redacted
    if isinstance(value, (list, tuple, set)):
        return [_redact(item, parent_key=parent_key) for item in value]
    return _json_safe(value)


def _turn_dir_from_response(response: Mapping[str, Any]) -> Path | None:
    detail = response.get("detail_json_path") or response.get("detail_json_path_resolved")
    if isinstance(detail, str) and detail:
        return Path(detail).parent
    session_path = response.get("session_path") or response.get("session_path_resolved")
    turn_id = response.get("turn_id")
    if isinstance(session_path, str) and session_path and isinstance(turn_id, str) and turn_id:
        candidate = Path(session_path) / "turns" / turn_id
        if candidate.is_dir():
            return candidate
    return None


def _copy_turn_artifacts(turn_dir: Path, output_dir: Path) -> list[str]:
    copied: list[str] = []
    if not turn_dir.is_dir():
        return copied
    for source in sorted(turn_dir.iterdir()):
        if source.is_file() and source.suffix in {".json", ".jsonl"}:
            dest = output_dir / source.name
            try:
                if source.suffix == ".json":
                    parsed = json.loads(source.read_text(encoding="utf-8"))
                    _safe_write(dest, _redact(parsed))
                else:
                    rendered: list[str] = []
                    for line in source.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        rendered.append(json.dumps(_redact(json.loads(line)), sort_keys=True))
                    dest.write_text("\n".join(rendered) + ("\n" if rendered else ""), encoding="utf-8")
            except (OSError, json.JSONDecodeError):
                # Never raw-copy an unparseable model artifact: it may contain a
                # credential in malformed structured text that free-text
                # redaction cannot classify safely. Persist no source body.
                _safe_write(dest, {"redacted_unparseable_artifact": True})
            copied.append(str(dest.relative_to(output_dir)))
    return copied


def _executor_report(result: Any) -> dict[str, Any]:
    """Extract the serialized ``report.executor`` mapping from a result."""
    result_payload = _json_safe(result)
    if isinstance(result_payload, Mapping):
        report = result_payload.get("report")
        if isinstance(report, Mapping):
            executor = report.get("executor")
            if isinstance(executor, Mapping):
                return dict(executor)

    report_obj = getattr(result, "report", None)
    report_payload = _json_safe(report_obj)
    if isinstance(report_payload, Mapping):
        executor = report_payload.get("executor")
        if isinstance(executor, Mapping):
            return dict(executor)
    return {}


def _implementation_payload_from_report(
    *,
    request: Mapping[str, Any],
    classification: Mapping[str, Any],
    research: Mapping[str, Any] | None,
) -> dict[str, Any]:
    route = classification.get("route")
    route_text = route if isinstance(route, str) and route else ""
    if not route_text:
        route_text = "adapt" if classification.get("research") and classification.get("implement") else (
            "revise" if classification.get("implement") else "research"
        )

    payload: dict[str, Any] = {
        "task": request.get("query") or request.get("task") or "",
        "query": request.get("query") or request.get("task") or "",
        "route": route_text,
        "executor_route": route_text,
        "executor_classification": dict(classification),
    }
    if "graph" in request:
        payload["graph"] = request.get("graph")
    if isinstance(request.get("session_id"), str):
        payload["session_id"] = request["session_id"]

    if research:
        # D03: execution_protocol_notes carries ONLY the compact F01
        # EvidenceLedger plus the agent-facing research sources.  Precedent /
        # adaptation material (research_summary, workflow_precedent_status,
        # research_warnings, research_context_packet, precedent packets and
        # slices) is never constructed here; full evidence bodies live in the
        # evidence-pack artifact behind resolvable evidence IDs.
        notes: dict[str, Any] = {}
        raw_sources = research.get("research_sources")
        if not isinstance(raw_sources, (list, tuple)):
            raw_sources = research.get("sources")
        if isinstance(raw_sources, (list, tuple)):
            source_rows = [item for item in raw_sources if isinstance(item, dict)]
            if source_rows:
                notes["research_sources"] = source_rows
        ledger = research.get("ledger")
        if isinstance(ledger, Mapping):
            notes["ledger"] = ledger
        if notes:
            payload["execution_protocol_notes"] = notes

    if route_text in {"research", "adapt"}:
        brief = {
            key: classification[key]
            for key in ("research_goal", "search_directions", "source_preferences", "avoid")
            if classification.get(key)
        }
        if brief:
            payload["research_brief"] = brief

    return payload


def _append_manifest(manifest: list[str], file_name: str) -> None:
    if file_name not in manifest:
        manifest.append(file_name)


_EMPTY_UI: dict[str, Any] = {"nodes": [], "links": []}
_UNCHANGED_UI_ROUTES = frozenset(
    {"clarify", "respond", "inspect", "research", "requires_custom_nodes"}
)


def _as_graph_mapping(value: Any) -> dict[str, Any] | None:
    """Return a JSON object graph, or None when no graph payload is present."""
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return None


def _request_graph(request: Mapping[str, Any]) -> dict[str, Any] | None:
    return _as_graph_mapping(request.get("graph"))


def _result_graph(result: Any) -> dict[str, Any] | None:
    if result is None:
        return None
    graph = getattr(result, "graph", None)
    mapped = _as_graph_mapping(graph)
    if mapped is not None:
        return mapped
    payload = _json_safe(result)
    if isinstance(payload, Mapping):
        return _as_graph_mapping(payload.get("graph"))
    return None


def _load_ui_mapping(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _route_projects_final_from_original(response: Mapping[str, Any]) -> bool:
    """Unchanged / refused / clarify / inspect / research routes project final=original."""
    route = response.get("route")
    if isinstance(route, str) and route in _UNCHANGED_UI_ROUTES:
        return True
    if response.get("graph_unchanged") is True:
        return True
    outcome = response.get("outcome")
    if isinstance(outcome, Mapping):
        kind = outcome.get("kind")
        if kind in {"clarify", "requires_custom_nodes", "noop"}:
            return True
    return False


def persist_universal_ui_evidence(
    *,
    request: Mapping[str, Any],
    result: Any,
    response: Mapping[str, Any],
    output_dir: Path,
    manifest: list[str],
) -> None:
    """Write authoritative original.ui.json and final.ui.json for every route.

    Non-edit, refused, and unchanged routes explicitly project final from
    original. Edit routes that produced a candidate persist that candidate as
    final. Missing graphs become an empty UI document so both files always exist.
    """
    original_path = output_dir / "original.ui.json"
    final_path = output_dir / "final.ui.json"
    candidate_path = output_dir / "candidate.ui.json"

    original = _load_ui_mapping(original_path)
    if original is None:
        original = _request_graph(request)
    if original is None:
        original = dict(_EMPTY_UI)

    if _route_projects_final_from_original(response):
        final = original
    else:
        final = _load_ui_mapping(final_path)
        if final is None:
            final = _load_ui_mapping(candidate_path)
        if final is None:
            artifacts = response.get("artifacts")
            if isinstance(artifacts, Mapping):
                for key in ("final_ui", "candidate_ui"):
                    artifact_path = artifacts.get(key)
                    if isinstance(artifact_path, str) and artifact_path:
                        final = _load_ui_mapping(Path(artifact_path))
                        if final is not None:
                            break
        if final is None:
            final = _as_graph_mapping(
                response.get("candidate_graph") or response.get("candidate")
            )
        if final is None:
            final = _result_graph(result)
        if final is None:
            final = original

    _safe_write(original_path, _redact(original))
    _append_manifest(manifest, "original.ui.json")
    _safe_write(final_path, _redact(final))
    _append_manifest(manifest, "final.ui.json")


def synthesize_headless_artifacts(
    *,
    request: Mapping[str, Any],
    result: Any,
    response: Mapping[str, Any],
    output_dir: Path,
    status: str,
    readiness: Mapping[str, Any] | None = None,
    entrypoint: str = "headless_cli",
) -> dict[str, Any]:
    """Write the standard headless artifact directory and return a manifest.

    The manifest lists every file written relative to *output_dir*.  Real durable
    turn artifacts are copied from the underlying agent-edit turn when they exist;
    synthetic summaries are always written so callers have a stable contract.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []

    request_path = output_dir / "request.json"
    _safe_write(request_path, _redact(request))
    _append_manifest(manifest, "request.json")

    response_path = output_dir / "response.json"
    _safe_write(response_path, _redact(response))
    _append_manifest(manifest, "response.json")

    flow_metadata = {
        "flow_kind": _FLOW_KIND,
        "dispatcher": "real",
        "model_behavior": "agentic",
        "frontend": "not_used",
        "entrypoint": entrypoint,
        "status": status,
        "live": bool(request.get("live", True)),
        "dry_run": bool(request.get("dry_run", False)),
        "apply": bool(request.get("apply", False)),
        "network": bool(request.get("network", True)),
        "readiness": dict(readiness) if readiness else {},
    }
    _safe_write(output_dir / "flow_metadata.json", _redact(flow_metadata))
    _append_manifest(manifest, "flow_metadata.json")

    report = _executor_report(result)
    model_attempts = report.get("model_attempts")
    if isinstance(model_attempts, (list, tuple)) and model_attempts:
        _safe_write(
            output_dir / "model_attempts.json",
            {"attempts": _redact(model_attempts)},
        )
        _append_manifest(manifest, "model_attempts.json")
    classification = report.get("plan")
    model_response = report.get("model_response")
    if isinstance(classification, Mapping):
        classification_payload = _redact(classification)
        _safe_write(output_dir / "classification.json", classification_payload)
        _append_manifest(manifest, "classification.json")

        research = report.get("research")
        research_payload: dict[str, Any] | None = None
        if isinstance(research, Mapping):
            research_payload = _redact(research)
            _safe_write(output_dir / "research.json", research_payload)
            _append_manifest(manifest, "research.json")

        implementation = report.get("implementation")
        if isinstance(implementation, Mapping):
            implementation_payload = _implementation_payload_from_report(
                request=request,
                classification=classification_payload,
                research=research_payload,
            )
            _safe_write(
                output_dir / "implementation_payload.json",
                _redact(implementation_payload),
            )
            _append_manifest(manifest, "implementation_payload.json")
            _safe_write(
                output_dir / "implementation_result.json",
                _redact(implementation),
            )
            _append_manifest(manifest, "implementation_result.json")
    elif report.get("classification_status") or model_response is not None:
        # Truthful failed-classification artifact: no fabricated decision/plan.
        # Persist the typed status plus the model-call evidence so the failure
        # is diagnosable at the artifact boundary.
        classification_payload = _redact(
            {
                "classification_status": report.get("classification_status") or "failed",
                "model_response": model_response,
            }
        )
        _safe_write(output_dir / "classification.json", classification_payload)
        _append_manifest(manifest, "classification.json")

    if model_response is not None:
        _safe_write(output_dir / "model_response.json", _redact(model_response))
        _append_manifest(manifest, "model_response.json")

    turn_dir = _turn_dir_from_response(response)
    copied: list[str] = []
    if turn_dir is not None and turn_dir.is_dir():
        copied = _copy_turn_artifacts(turn_dir, output_dir)
        for copied_name in copied:
            _append_manifest(manifest, copied_name)

    persist_universal_ui_evidence(
        request=request,
        result=result,
        response=response,
        output_dir=output_dir,
        manifest=manifest,
    )

    copied_set = set(copied)
    optional_model_artifacts = {
        name: name in copied_set or name in manifest
        for name in sorted(_MODEL_ARTIFACT_NAMES)
    }

    LOGGER.info(
        "headless artifacts synthesized",
        extra={"output_dir": str(output_dir), "artifact_count": len(manifest)},
    )
    return {
        "output_dir": str(output_dir),
        "manifest": manifest,
        "copied_turn_artifacts": copied,
        "optional_model_artifacts": optional_model_artifacts,
        "turn_dir": str(turn_dir) if turn_dir else None,
    }


__all__ = ["persist_universal_ui_evidence", "synthesize_headless_artifacts"]
