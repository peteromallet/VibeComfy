#!/usr/bin/env python3
"""Upload VibeComfy external-workflow corpus summaries to Hivemind.

Each row in ``external_workflows/manifest.json`` already carries a
``summary`` and ``primary_source`` provenance blob.  This script turns those
into Hivemind ``external_resources`` rows via the anonymous
``contribute-resource`` edge function, so no contributor key is required.

Searchable text (``title`` / ``body``) is derived from the LLM summary.
Structured summary + provenance live in ``metadata`` and ``payload`` so
Hivemind consumers can filter, rank, and cite the workflows without parsing
free text.
"""

from __future__ import annotations

import argparse
import json
import os
import pprint
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path so ``import scripts.*`` works when this file
# is executed directly as well as via ``python -m``.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reuse the HTTP helpers and idempotency logic from the ready-template uploader.
from scripts.upload_ready_templates_to_hivemind import (
    DEFAULT_HIVEMIND_ANON_KEY,
    DEFAULT_HIVEMIND_API_URL,
    _find_existing_resource,
    _idempotency_key,
    _post,
    _verify_recorded,
)
from scripts.hivemind_workflow_semantics import enrich_resource_data


DEFAULT_MANIFEST = REPO_ROOT / "external_workflows" / "manifest.json"
DEFAULT_CORPUS_DIR = REPO_ROOT / "external_workflows" / "corpus"
DEFAULT_CACHE_DIR = REPO_ROOT / "external_workflows" / ".shadow" / "summary-cache"
# Anonymous resource endpoint — no contributor key required once deployed.
DEFAULT_CONTRIBUTE_URL = (
    "https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/contribute-resource"
)
SOURCE = "vibecomfy-external"
ASSET_KIND = "vibecomfy_external_workflow"
DISCORD_CDN_HOSTS = {
    "cdn.discordapp.com",
    "media.discordapp.net",
}


def _repo_root() -> Path:
    return REPO_ROOT


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{manifest_path} must contain a JSON object")
    return data


def _save_manifest(manifest: dict[str, Any], manifest_path: Path) -> None:
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clean_description(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sanitize_discord_cdn_url(value: Any) -> str | None:
    """Strip signed CDN query params and private Discord attachment IDs.

    Discord attachment URLs embed channel/attachment IDs in the path and signed
    expiry/auth parameters in the query string. Uploading those leaks private
    provenance and creates dead links, so Hivemind only gets a stable redacted
    locator with the filename preserved.
    """
    if not isinstance(value, str) or not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.netloc.lower() not in DISCORD_CDN_HOSTS:
        return value
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 4 and parts[0] == "attachments":
        filename = parts[-1]
        safe_path = "/attachments/_/_/" + urllib.parse.quote(urllib.parse.unquote(filename))
    else:
        safe_path = parsed.path
    return urllib.parse.urlunparse((parsed.scheme or "https", parsed.netloc, safe_path, "", "", ""))


def _summary_from_row(row: dict[str, Any]) -> dict[str, Any]:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    return {
        "title": _clean_description(summary.get("title")),
        "description": _clean_description(summary.get("description")),
        "tags": [str(t) for t in summary.get("tags", []) if str(t)],
        "task_type": str(summary.get("task_type") or "other"),
        "media_type": str(summary.get("media_type") or "image"),
        "flags": summary.get("flags") if isinstance(summary.get("flags"), dict) else {},
        "complexity": int(summary.get("complexity") or 1),
    }


def _summary_needs_enrichment(row: dict[str, Any]) -> bool:
    summary = row.get("summary")
    if not isinstance(summary, dict):
        return True
    return not _clean_description(summary.get("title")) or not _clean_description(summary.get("description"))


class _OpenAICompatibleLLMClient:
    """Minimal chat-completions client for the workflow summarizer."""

    def __init__(self, *, model: str, base_url: str, api_key: str) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        import requests  # noqa: PLC0415

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def complete(self, prompt: str) -> str:
        response = self._session.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
                "temperature": 0.3,
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"])


def _build_llm_client(model: str) -> _OpenAICompatibleLLMClient:
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if model == "deepseek-chat" and deepseek_key:
        return _OpenAICompatibleLLMClient(
            model=model,
            base_url="https://api.deepseek.com/v1",
            api_key=deepseek_key,
        )
    if openai_key:
        return _OpenAICompatibleLLMClient(
            model=model,
            base_url="https://api.openai.com/v1",
            api_key=openai_key,
        )
    if deepseek_key:
        return _OpenAICompatibleLLMClient(
            model=model,
            base_url="https://api.deepseek.com/v1",
            api_key=deepseek_key,
        )
    raise ValueError(
        "No API key available for enrichment. Set DEEPSEEK_API_KEY for DeepSeek "
        "or OPENAI_API_KEY for OpenAI."
    )


def _existing_summary_content_hash(row: dict[str, Any], workflow_dict: dict[str, Any]) -> Any:
    for candidate in (
        row.get("summary") if isinstance(row.get("summary"), dict) else None,
        workflow_dict.get("metadata", {}).get("summary")
        if isinstance(workflow_dict.get("metadata"), dict)
        and isinstance(workflow_dict.get("metadata", {}).get("summary"), dict)
        else None,
    ):
        if isinstance(candidate, dict) and candidate.get("_content_hash"):
            return candidate["_content_hash"]
    return None


def _enrich_row_summary(
    row: dict[str, Any],
    *,
    corpus_dir: Path,
    cache_dir: Path,
    llm_client: Any,
    persist: bool,
) -> bool:
    """Generate and attach a missing external-workflow summary.

    Returns True when the row was enriched. In dry-run mode (*persist* false),
    the manifest row is updated in memory only so envelopes reflect the summary.
    """
    if not _summary_needs_enrichment(row):
        return False

    corpus_path = _resolve_corpus_path(row, corpus_dir)
    if corpus_path is None:
        raise ValueError(f"cannot resolve corpus_path for workflow {row.get('workflow_id')}")
    workflow_dict = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(workflow_dict, dict):
        raise ValueError(f"{corpus_path} must contain a JSON object")

    from scripts.enrich_workflow_summaries import DictWorkflowAdapter  # noqa: PLC0415
    from vibecomfy.ingest.summarize import summarize_workflow  # noqa: PLC0415

    content_hash = _existing_summary_content_hash(row, workflow_dict)
    adapter = DictWorkflowAdapter(workflow_dict)
    summary = summarize_workflow(adapter, llm_client=llm_client, cache_dir=str(cache_dir))
    if summary is None:
        raise RuntimeError(f"failed to enrich summary for workflow {row.get('workflow_id')}")
    if content_hash:
        summary["_content_hash"] = content_hash

    row["summary"] = summary
    if persist:
        metadata = workflow_dict.setdefault("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
            workflow_dict["metadata"] = metadata
        metadata["summary"] = summary
        corpus_path.write_text(json.dumps(workflow_dict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True


def _provenance_from_row(row: dict[str, Any]) -> dict[str, Any]:
    primary = row.get("primary_source")
    if not isinstance(primary, dict):
        primary = {}
    return {
        "source": primary.get("source") or row.get("source"),
        "external_id": primary.get("external_id"),
        "source_url": _sanitize_discord_cdn_url(primary.get("source_url")),
        "source_type": primary.get("source_type"),
        "authority_tier": primary.get("authority_tier", "community"),
        "filename": primary.get("filename"),
        "channel_name": primary.get("channel_name"),
        "message_id": None,
        "repo": primary.get("repo"),
        "repo_path": primary.get("repo_path"),
        "repo_branch": primary.get("repo_branch"),
        "discovered_by": primary.get("discovered_by"),
        "discovered_at": primary.get("discovered_at"),
        "ingested_at": primary.get("ingested_at"),
        "canonical_workflow_hash": primary.get("canonical_workflow_hash") or row.get("canonical_workflow_hash"),
        "node_count": primary.get("node_count"),
        "node_class_multiset": primary.get("node_class_multiset") or {},
        "source_file_sha256": primary.get("source_file_sha256"),
        "source_workflow_sha256": primary.get("source_workflow_sha256"),
    }


def _external_id(row: dict[str, Any]) -> str:
    canonical = str(row.get("canonical_workflow_hash") or "")
    if canonical:
        return f"vibecomfy:external_workflow:{canonical}"
    return f"vibecomfy:external_workflow:{row.get('workflow_id')}"


def _title(summary: dict[str, Any], row: dict[str, Any]) -> str:
    if summary["title"]:
        return summary["title"]
    filename = row.get("primary_source", {}).get("filename") if isinstance(row.get("primary_source"), dict) else None
    if filename:
        return f"External workflow: {filename}"
    return f"External workflow {row.get('workflow_id', 'unknown')}"


def _body(summary: dict[str, Any], provenance: dict[str, Any]) -> str:
    lines: list[str] = []
    if summary["description"]:
        lines.append(f"Description: {summary['description']}")
    if summary["tags"]:
        lines.append("Tags: " + ", ".join(summary["tags"]) + ".")
    lines.append(f"Task type: {summary['task_type']}")
    lines.append(f"Media type: {summary['media_type']}")
    lines.append(f"Complexity: {summary['complexity']}")
    if provenance.get("source"):
        lines.append(f"Source: {provenance['source']}")
    if provenance.get("source_url"):
        lines.append(f"Source URL: {provenance['source_url']}")
    if provenance.get("filename"):
        lines.append(f"Filename: {provenance['filename']}")
    if provenance.get("channel_name"):
        lines.append(f"Discord channel: {provenance['channel_name']}")
    if provenance.get("repo"):
        lines.append(f"Repository: {provenance['repo']}")
    if provenance.get("repo_path"):
        lines.append(f"Repository path: {provenance['repo_path']}")
    if provenance.get("canonical_workflow_hash"):
        lines.append(f"Canonical workflow hash: {provenance['canonical_workflow_hash']}")
    node_multiset = provenance.get("node_class_multiset") or {}
    if node_multiset:
        lines.append("Node classes: " + ", ".join(f"{cls} ({count})" for cls, count in node_multiset.items()) + ".")
    return "\n".join(lines)


def _resolve_corpus_path(row: dict[str, Any], corpus_dir: Path) -> Path | None:
    corpus_path = row.get("corpus_path")
    if not isinstance(corpus_path, str) or not corpus_path.strip():
        workflow_id = str(row.get("workflow_id") or "").strip()
        if not workflow_id:
            return None
        candidate = corpus_dir / f"{workflow_id}.json"
        return candidate if candidate.exists() else None

    path = Path(corpus_path)
    candidates = [path]
    if not path.is_absolute():
        candidates = [_repo_root() / path, corpus_dir / path.name]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _emit_external_workflow_python(path: Path, row: dict[str, Any]) -> str:
    from vibecomfy.porting.emitter import emit_scratchpad_python  # noqa: PLC0415

    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and raw.get("vibecomfy_format_version") and isinstance(raw.get("nodes"), dict):
        workflow = _vibe_workflow_from_dict(raw)
    else:
        from vibecomfy.cli_loader import load_workflow_any  # noqa: PLC0415

        workflow = load_workflow_any(str(path))
    return emit_scratchpad_python(
        workflow,
        workflow_id=str(row.get("workflow_id") or getattr(workflow, "id", "external_workflow")),
        source_path=str(path),
        provenance=_provenance_from_row(row),
        prune_dead_branches=False,
    )


def _vibe_workflow_from_dict(data: dict[str, Any]):
    from vibecomfy.workflow import (  # noqa: PLC0415
        RawWidgetPayload,
        VibeEdge,
        VibeInput,
        VibeNode,
        VibeOutput,
        VibeWorkflow,
        WorkflowRequirements,
        WorkflowSource,
    )

    source_data = data.get("source") if isinstance(data.get("source"), dict) else {}
    requirements_data = data.get("requirements") if isinstance(data.get("requirements"), dict) else {}
    workflow = VibeWorkflow(
        id=str(data.get("id") or "external_workflow"),
        source=WorkflowSource(
            id=str(source_data.get("id") or data.get("id") or "external_workflow"),
            path=source_data.get("path"),
            source_type=str(source_data.get("source_type") or "external_workflow"),
            provenance=source_data.get("provenance") if isinstance(source_data.get("provenance"), dict) else {},
        ),
        requirements=WorkflowRequirements(
            models=list(requirements_data.get("models") or []),
            custom_nodes=list(requirements_data.get("custom_nodes") or []),
            missing_models=list(requirements_data.get("missing_models") or []),
            missing_nodes=list(requirements_data.get("missing_nodes") or []),
            unsupported=list(requirements_data.get("unsupported") or []),
        ),
        metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
        strict_types=bool(data.get("strict_types")),
    )
    nodes = data.get("nodes") if isinstance(data.get("nodes"), dict) else {}
    for node_id, node_data in nodes.items():
        if not isinstance(node_data, dict):
            continue
        raw_widgets = node_data.get("raw_widgets")
        raw_payload = None
        if isinstance(raw_widgets, dict):
            raw_payload = RawWidgetPayload(
                values=raw_widgets.get("values"),
                shape=str(raw_widgets.get("shape") or "unknown"),
                source=str(raw_widgets.get("source") or "unknown"),
                has_dict_rows=bool(raw_widgets.get("has_dict_rows")),
                length=int(raw_widgets.get("length") or 0),
            )
        workflow.nodes[str(node_id)] = VibeNode(
            id=str(node_data.get("id") or node_id),
            class_type=str(node_data.get("class_type") or "Unknown"),
            pack=node_data.get("pack"),
            inputs=node_data.get("inputs") if isinstance(node_data.get("inputs"), dict) else {},
            widgets=node_data.get("widgets") if isinstance(node_data.get("widgets"), dict) else {},
            metadata=node_data.get("metadata") if isinstance(node_data.get("metadata"), dict) else {},
            uid=str(node_data.get("uid") or ""),
            raw_widgets=raw_payload,
        )
    for edge_data in data.get("edges") or []:
        if not isinstance(edge_data, dict):
            continue
        workflow.edges.append(
            VibeEdge(
                from_node=str(edge_data.get("from_node") or ""),
                from_output=str(edge_data.get("from_output") or ""),
                to_node=str(edge_data.get("to_node") or ""),
                to_input=str(edge_data.get("to_input") or ""),
            )
        )
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    for name, input_data in inputs.items():
        if not isinstance(input_data, dict):
            continue
        workflow.inputs[str(name)] = VibeInput(
            name=str(input_data.get("name") or name),
            node_id=str(input_data.get("node_id") or ""),
            field=str(input_data.get("field") or ""),
            value=input_data.get("value"),
            type=input_data.get("type"),
            default=input_data.get("default"),
            required=bool(input_data.get("required")),
            range=input_data.get("range"),
            aliases=tuple(input_data.get("aliases") or ()),
            media_semantics=input_data.get("media_semantics") or input_data.get("media"),
        )
    for output_data in data.get("outputs") or []:
        if not isinstance(output_data, dict):
            continue
        workflow.outputs.append(
            VibeOutput(
                node_id=str(output_data.get("node_id") or ""),
                output_type=str(output_data.get("output_type") or ""),
                name=output_data.get("name"),
                artifact_kind=output_data.get("artifact_kind"),
                mime_type=output_data.get("mime_type"),
                filename_prefix=output_data.get("filename_prefix"),
                expected_cardinality=output_data.get("expected_cardinality"),
            )
        )
    return workflow


def _workflow_payload_from_row(row: dict[str, Any], *, corpus_dir: Path) -> dict[str, Any]:
    path = _resolve_corpus_path(row, corpus_dir)
    workflow_json: dict[str, Any] | None = None
    python_source: str | None = None
    python_source_error: str | None = None
    if path is not None and path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                workflow_json = raw
            else:
                python_source_error = f"{path} did not contain a JSON object"
        except Exception as exc:
            python_source_error = f"failed to read workflow JSON: {type(exc).__name__}: {exc}"
        if workflow_json is not None:
            try:
                python_source = _emit_external_workflow_python(path, row)
            except Exception as exc:
                python_source_error = f"failed to emit scratchpad Python: {type(exc).__name__}: {exc}"
                python_source = _fallback_python_archive_source(workflow_json, row, python_source_error)
    elif path is not None:
        python_source_error = f"corpus workflow file not found: {path}"

    compiled_api = workflow_json.get("compiled_api") if isinstance(workflow_json, dict) else None
    representations = ["vibecomfy_json"]
    if compiled_api is not None:
        representations.append("compiled_api")
    if python_source:
        representations.append("scratchpad_python" if not python_source_error else "python_workflow_archive")
    return {
        "workflow_json": workflow_json,
        "compiled_api": compiled_api,
        "python_source": python_source,
        "python_source_error": python_source_error,
        "representations": representations,
        "vibecomfy_format_version": workflow_json.get("vibecomfy_format_version") if isinstance(workflow_json, dict) else None,
        "node_count": len(workflow_json.get("nodes", {})) if isinstance(workflow_json, dict) and isinstance(workflow_json.get("nodes"), dict) else None,
    }


def _fallback_python_archive_source(workflow_json: dict[str, Any], row: dict[str, Any], error: str) -> str:
    """Emit a valid Python representation that carries the complete workflow data.

    Scratchpad emission can fail for external corpus workflows that preserve
    helper nodes the resolver cannot lower yet. The upload still needs a Python
    representation with all source data, so this archive form embeds the
    VibeComfy JSON plus compiled API without pretending the scratchpad lowering
    succeeded.
    """
    workflow_id = str(row.get("workflow_id") or workflow_json.get("id") or "external_workflow")
    rendered = pprint.pformat(workflow_json, sort_dicts=True, width=120)
    return (
        "# vibecomfy: generated external workflow archive\n"
        '"""External VibeComfy workflow archived as Python data."""\n'
        "from __future__ import annotations\n\n"
        f"WORKFLOW_ID = {workflow_id!r}\n"
        f"SCRATCHPAD_EMISSION_ERROR = {error!r}\n"
        f"WORKFLOW_JSON = {rendered}\n\n"
        "COMPILED_API = WORKFLOW_JSON.get('compiled_api')\n\n"
        "def build_workflow_dict():\n"
        "    return WORKFLOW_JSON\n\n"
        "def build_api_workflow():\n"
        "    return COMPILED_API\n"
    )


def _url(row: dict[str, Any], provenance: dict[str, Any]) -> str:
    if provenance.get("source_url"):
        return str(provenance["source_url"])
    corpus_rel = str(row.get("corpus_path") or "")
    return f"file://{corpus_rel}"


def _external_key_from_envelope(envelope: dict[str, Any]) -> tuple[str, str]:
    data = envelope["data"]
    return str(data["source"]), str(data["external_id"])


def _postgrest_in_values(values: list[str]) -> str:
    escaped = [value.replace('"', '\\"') for value in values]
    return "in.(" + ",".join(f'"{value}"' for value in escaped) + ")"


def _postgrest_get_with_backoff(
    table: str,
    params: dict[str, str],
    *,
    api_url: str,
    anon_key: str,
    attempts: int = 5,
    base_sleep: float = 0.5,
) -> Any:
    from scripts import upload_ready_templates_to_hivemind as ready_upload

    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            return ready_upload._postgrest_get(table, params, api_url=api_url, anon_key=anon_key)
        except urllib.error.HTTPError as exc:
            last_error = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else base_sleep * (2**attempt)
            except ValueError:
                wait = base_sleep * (2**attempt)
            time.sleep(wait)
        except TimeoutError as exc:
            last_error = exc
            if attempt >= attempts - 1:
                raise
            time.sleep(base_sleep * (2**attempt))
    raise last_error or TimeoutError("preflight failed after retries")


def _find_existing_resource(
    envelope: dict[str, Any],
    *,
    api_url: str,
    anon_key: str,
) -> dict[str, Any]:
    key = _idempotency_key(envelope)
    rows = _postgrest_get_with_backoff(
        "external_resources",
        {
            "select": "id,source,external_id,title,created_at",
            "source": f"eq.{key['source']}",
            "external_id": f"eq.{key['external_id']}",
            "limit": "2",
        },
        api_url=api_url,
        anon_key=anon_key,
    )
    if not isinstance(rows, list) or not rows:
        return {"exists": False, **key}
    first = rows[0] if isinstance(rows[0], dict) else {}
    return {
        "exists": True,
        **key,
        "resource_id": first.get("id"),
        "title": first.get("title"),
        "created_at": first.get("created_at"),
        "duplicate_count": len(rows),
    }


def _find_existing_resources(
    envelopes: list[dict[str, Any]],
    *,
    api_url: str,
    anon_key: str,
    batch_size: int = 100,
) -> dict[tuple[str, str], dict[str, Any]]:
    """Batch preflight external_resources existence by source/external_id.

    Single-row calls deliberately route through ``_find_existing_resource`` so
    older unit tests and narrow monkeypatches keep working; multi-row calls use
    one PostgREST query per source/chunk instead of one GET per row.
    """
    if not envelopes:
        return {}
    if len(envelopes) == 1:
        existing = _find_existing_resource(envelopes[0], api_url=api_url, anon_key=anon_key)
        return {_external_key_from_envelope(envelopes[0]): existing}

    grouped: dict[str, list[str]] = {}
    for envelope in envelopes:
        source, external_id = _external_key_from_envelope(envelope)
        grouped.setdefault(source, []).append(external_id)

    found: dict[tuple[str, str], dict[str, Any]] = {}
    for source, external_ids in grouped.items():
        unique_ids = sorted(set(external_ids))
        for idx in range(0, len(unique_ids), max(1, batch_size)):
            chunk = unique_ids[idx : idx + max(1, batch_size)]
            rows = _postgrest_get_with_backoff(
                "external_resources",
                {
                    "select": "id,source,external_id,title,created_at",
                    "source": f"eq.{source}",
                    "external_id": _postgrest_in_values(chunk),
                    "limit": str(len(chunk) + 1),
                },
                api_url=api_url,
                anon_key=anon_key,
            )
            if not isinstance(rows, list):
                rows = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                external_id = str(row.get("external_id") or "")
                key = (source, external_id)
                found[key] = {
                    "exists": True,
                    "source": source,
                    "external_id": external_id,
                    "resource_id": row.get("id"),
                    "title": row.get("title"),
                    "created_at": row.get("created_at"),
                    "duplicate_count": 1,
                }
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for envelope in envelopes:
        key = _external_key_from_envelope(envelope)
        result[key] = found.get(key, {"exists": False, "source": key[0], "external_id": key[1]})
    return result


def _post_with_backoff(
    envelope: dict[str, Any],
    *,
    contribute_url: str,
    contributor_key: str | None,
    attempts: int = 5,
    base_sleep: float = 0.5,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            return _post(envelope, contribute_url=contribute_url, contributor_key=contributor_key)
        except urllib.error.HTTPError as exc:
            last_error = exc
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if not retryable or attempt >= attempts - 1:
                raise
            retry_after = exc.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else base_sleep * (2**attempt)
            except ValueError:
                wait = base_sleep * (2**attempt)
            time.sleep(wait)
        except TimeoutError as exc:
            last_error = exc
            if attempt >= attempts - 1:
                raise
            time.sleep(base_sleep * (2**attempt))
    raise last_error or TimeoutError("upload failed after retries")


def _envelope(row: dict[str, Any], *, corpus_dir: Path = DEFAULT_CORPUS_DIR) -> dict[str, Any]:
    summary = _summary_from_row(row)
    provenance = _provenance_from_row(row)
    workflow_payload = _workflow_payload_from_row(row, corpus_dir=corpus_dir)
    description = summary["description"]
    external_id = _external_id(row)
    corpus_rel = str(row.get("corpus_path") or "")

    metadata: dict[str, Any] = {
        "asset_kind": ASSET_KIND,
        "workflow_id": row.get("workflow_id"),
        "corpus_path": corpus_rel,
        "summary": summary,
        "description": description or None,
        "task_type": summary["task_type"],
        "media_type": summary["media_type"],
        "tags": summary["tags"],
        "complexity": summary["complexity"],
        "flags": summary["flags"],
        "provenance": provenance,
        "representation": "vibecomfy_external_workflow",
        "representations": workflow_payload["representations"],
        "vibecomfy_format_version": workflow_payload["vibecomfy_format_version"],
        "has_workflow_json": workflow_payload["workflow_json"] is not None,
        "has_rich_nodes": workflow_payload["node_count"] is not None,
        "has_python_source": bool(workflow_payload["python_source"]),
        "python_source_error": workflow_payload["python_source_error"],
    }

    payload: dict[str, Any] = {
        "workflow_id": row.get("workflow_id"),
        "corpus_path": corpus_rel,
        "summary": summary,
        "description": description or None,
        "provenance": provenance,
        "workflow_json": workflow_payload["workflow_json"],
        "compiled_api": workflow_payload["compiled_api"],
        "python_source": workflow_payload["python_source"],
        "python_source_error": workflow_payload["python_source_error"],
        "representations": workflow_payload["representations"],
    }

    body = _body(summary, provenance)
    if workflow_payload["python_source"]:
        body = body + "\n\nPython scratchpad source:\n" + workflow_payload["python_source"]

    data = {
        "kind": "workflow",
        "source": SOURCE,
        "external_id": external_id,
        "title": _title(summary, row),
        "body": body,
        "url": _url(row, provenance),
        "metadata": metadata,
        "payload": payload,
    }
    return {"action": "add_resource", "data": enrich_resource_data(data)}


def _upload_record(result: dict[str, Any], envelope: dict[str, Any] | None = None) -> dict[str, Any]:
    record = {
        "status": result.get("status"),
        "updated_at": _utcnow(),
    }
    if envelope is not None:
        record["idempotency_key"] = _idempotency_key(envelope)
    for key in ("response", "preflight", "verify", "error"):
        if key in result:
            record[key] = result[key]
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="external_workflows/manifest.json path")
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR, help="external_workflows/corpus directory")
    parser.add_argument("--only", action="append", default=[], help="Substring filter on workflow_id or corpus_path; repeatable")
    parser.add_argument("--limit", type=int, help="Maximum number of workflows to process")
    parser.add_argument("--dry-run", action="store_true", help="Write envelopes without uploading")
    parser.add_argument("--out-dir", help="Directory for dry-run envelopes or upload responses")
    parser.add_argument(
        "--enrich",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate missing workflow summaries before upload (default: on when --model is provided)",
    )
    parser.add_argument("--model", help="OpenAI-compatible model for enrichment, e.g. deepseek-chat or gpt-4o-mini")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="On-disk LLM summary cache directory",
    )
    parser.add_argument(
        "--skip-existing",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preflight external_resources by source+external_id and skip rows that already exist",
    )
    parser.add_argument(
        "--dry-run-preflight",
        action="store_true",
        help="In --dry-run mode, also query Hivemind and report whether each row would be skipped",
    )
    parser.add_argument("--verify", action="store_true", help="After real uploads, verify the recorded row matches the envelope")
    parser.add_argument("--sleep", type=float, default=0.1, help="Seconds to sleep between uploads")
    parser.add_argument("--preflight-batch-size", type=int, default=100, help="Rows per batched existing-resource preflight")
    parser.add_argument("--upload-attempts", type=int, default=5, help="Attempts for retryable upload HTTP 429/5xx/timeout failures")
    parser.add_argument("--contribute-url", default=os.environ.get("HIVEMIND_CONTRIBUTE_URL", DEFAULT_CONTRIBUTE_URL))
    parser.add_argument("--hivemind-api-url", default=os.environ.get("HIVEMIND_API_URL", DEFAULT_HIVEMIND_API_URL))
    parser.add_argument("--hivemind-anon-key", default=os.environ.get("HIVEMIND_ANON_KEY", DEFAULT_HIVEMIND_ANON_KEY))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = _repo_root()
    manifest_path = args.manifest.resolve()
    corpus_dir = args.corpus_dir.resolve()
    cache_dir = args.cache_dir.resolve()
    enrich_enabled = bool(args.model) if args.enrich is None else bool(args.enrich)

    manifest = _load_manifest(manifest_path)
    workflows = manifest.get("workflows", [])
    if not isinstance(workflows, list):
        print("error: manifest workflows must be a list", file=sys.stderr)
        return 1

    if args.only:
        needles = tuple(item.lower() for item in args.only)
        workflows = [
            row
            for row in workflows
            if any(
                needle in str(row.get("workflow_id", "")).lower()
                or needle in str(row.get("corpus_path", "")).lower()
                for needle in needles
            )
        ]
    if args.limit is not None:
        workflows = workflows[: args.limit]

    out_dir = Path(args.out_dir).resolve() if args.out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    # The default --contribute-url points at the anonymous contribute-resource
    # edge function, so no contributor key is required.
    contributor_key = os.environ.get("HIVEMIND_CONTRIBUTOR_KEY")

    results: list[dict[str, Any]] = []
    manifest_modified = False
    llm_client: Any = None
    if enrich_enabled:
        if not args.model:
            print("error: --enrich requires --model", file=sys.stderr)
            return 1
        cache_dir.mkdir(parents=True, exist_ok=True)
        for row in workflows:
            workflow_id = str(row.get("workflow_id", "unknown"))
            if not _summary_needs_enrichment(row):
                continue
            if llm_client is None:
                try:
                    llm_client = _build_llm_client(args.model)
                except Exception as exc:  # noqa: BLE001
                    print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
                    return 1
            try:
                enriched = _enrich_row_summary(
                    row,
                    corpus_dir=corpus_dir,
                    cache_dir=cache_dir,
                    llm_client=llm_client,
                    persist=not args.dry_run,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    json.dumps(
                        {
                            "workflow_id": workflow_id,
                            "status": "error",
                            "error": f"enrichment failed: {type(exc).__name__}: {exc}",
                        },
                        sort_keys=True,
                    )
                )
                return 1
            if enriched:
                manifest_modified = True
                print(json.dumps({"workflow_id": workflow_id, "status": "enriched"}, sort_keys=True), flush=True)
        if manifest_modified and not args.dry_run:
            manifest["summary_enrichment"] = {
                "updated_at": _utcnow(),
                "model": args.model,
                "cache_dir": str(cache_dir),
            }
            _save_manifest(manifest, manifest_path)

    envelopes_by_id: dict[str, dict[str, Any]] = {}
    for row in workflows:
        workflow_id = str(row.get("workflow_id", "unknown"))
        envelopes_by_id[workflow_id] = _envelope(row, corpus_dir=corpus_dir)

    preflight_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    if args.skip_existing and not args.dry_run:
        preflight_by_key = _find_existing_resources(
            list(envelopes_by_id.values()),
            api_url=args.hivemind_api_url,
            anon_key=args.hivemind_anon_key,
            batch_size=args.preflight_batch_size,
        )

    for row in workflows:
        workflow_id = str(row.get("workflow_id", "unknown"))
        envelope = envelopes_by_id[workflow_id]
        safe_name = workflow_id.replace("/", "__")
        existing: dict[str, Any] | None = None

        if args.dry_run:
            if args.skip_existing and args.dry_run_preflight:
                existing = _find_existing_resource(
                    envelope,
                    api_url=args.hivemind_api_url,
                    anon_key=args.hivemind_anon_key,
                )
            dry_status = "would_skip_existing" if existing and existing.get("exists") else "dry_run"
            result = {
                "workflow_id": workflow_id,
                "status": dry_status,
                "idempotency_key": _idempotency_key(envelope),
                "envelope": envelope,
            }
            if existing is not None:
                result["preflight"] = existing
            if out_dir:
                (out_dir / f"{safe_name}.json").write_text(
                    json.dumps(envelope, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
        else:
            try:
                if args.skip_existing:
                    existing = preflight_by_key.get(_external_key_from_envelope(envelope))
                    if existing is None:
                        existing = _find_existing_resource(
                            envelope,
                            api_url=args.hivemind_api_url,
                            anon_key=args.hivemind_anon_key,
                        )
                if existing and existing.get("exists"):
                    result = {
                        "workflow_id": workflow_id,
                        "status": "skipped_existing",
                        "idempotency_key": _idempotency_key(envelope),
                        "preflight": existing,
                    }
                else:
                    response = _post_with_backoff(
                        envelope,
                        contribute_url=args.contribute_url,
                        contributor_key=contributor_key or None,
                        attempts=args.upload_attempts,
                    )
                    result = {"workflow_id": workflow_id, "status": "uploaded", "response": response}

                if args.verify:
                    verify = _verify_recorded(
                        envelope,
                        api_url=args.hivemind_api_url,
                        anon_key=args.hivemind_anon_key,
                    )
                    result["verify"] = verify
                    if not verify.get("ok"):
                        result["status"] = "verify_failed"

                if out_dir:
                    (out_dir / f"{safe_name}.response.json").write_text(
                        json.dumps(result, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                row["hivemind_upload"] = _upload_record(result, envelope)
                manifest["upload_summary"] = {
                    "updated_at": _utcnow(),
                    "last_workflow_id": workflow_id,
                }
                _save_manifest(manifest, manifest_path)
                time.sleep(args.sleep)
            except Exception as exc:  # noqa: BLE001
                result = {
                    "workflow_id": workflow_id,
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                row["hivemind_upload"] = _upload_record(result, envelope)
                manifest["upload_summary"] = {
                    "updated_at": _utcnow(),
                    "last_workflow_id": workflow_id,
                }
                _save_manifest(manifest, manifest_path)
                if out_dir:
                    (out_dir / f"{safe_name}.response.json").write_text(
                        json.dumps(result, indent=2, sort_keys=True),
                        encoding="utf-8",
                    )
                results.append(result)
                print(json.dumps({"workflow_id": workflow_id, "status": "error", "error": result["error"]}, sort_keys=True))
                break

        results.append(result)
        print(json.dumps({"workflow_id": workflow_id, "status": result["status"]}, sort_keys=True), flush=True)

    summary = {"count": len(results), "statuses": {}}
    for result in results:
        status = str(result["status"])
        summary["statuses"][status] = summary["statuses"].get(status, 0) + 1
    if out_dir:
        (out_dir / "_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if not any(result["status"] in {"error", "verify_failed"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
