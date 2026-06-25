#!/usr/bin/env python3
"""Convert external ComfyUI workflow sources into VibeComfy-format JSON.

Each source file is kept verbatim in a shadow directory for provenance, and a
VibeComfy workflow JSON with embedded provenance + metadata is written to a
corpus directory. Duplicates are collapsed by canonical workflow hash; alternate
sources are recorded as provenance aliases.
"""

from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure repo root on sys.path so `import vibecomfy` works in script mode.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.testing.canonical import canonical_form
from vibecomfy.workflow import VibeWorkflow


DEFAULT_OUT_DIR = REPO_ROOT / "external_workflows" / "corpus"
DEFAULT_SHADOW_DIR = REPO_ROOT / "external_workflows" / ".shadow" / "source"
DEFAULT_MANIFEST = REPO_ROOT / "external_workflows" / "manifest.json"
GRAPH_IDENTITY_VERSION = 1
VIBECOMFY_FORMAT_VERSION = "1.0"


def _safe_id(value: str) -> str:
    """Make a filesystem-safe identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "unknown"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _node_class_multiset(api_workflow: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = collections.Counter()
    for node in api_workflow.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if isinstance(class_type, str) and class_type:
            counts[class_type] += 1
    return dict(sorted(counts.items()))


def _canonical_workflow_hash(api_workflow: dict[str, Any]) -> str:
    form = canonical_form(api_workflow)
    return _sha256_text(_canonical_json(form))


def _extract_api_workflow(raw: dict[str, Any]) -> dict[str, Any]:
    """Return the execution API dict from a raw ComfyUI workflow (UI or API)."""
    # Prefer offline normalizer so this script does not require a live ComfyUI.
    return normalize_to_api(raw, use_comfy_converter=False)


def _vibe_workflow_to_dict(workflow: VibeWorkflow) -> dict[str, Any]:
    """Serialize a VibeWorkflow to a plain JSON-serializable dict."""

    def _to_plain(obj: Any) -> Any:
        if dataclasses.is_dataclass(obj):
            result: dict[str, Any] = {}
            for field in dataclasses.fields(obj):
                if field.name.startswith("_"):
                    continue
                result[field.name] = _to_plain(getattr(obj, field.name))
            return result
        if isinstance(obj, dict):
            return {str(k): _to_plain(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_plain(v) for v in obj]
        return obj

    plain = _to_plain(workflow)
    # Always include the compiled API representation and a format version.
    plain["vibecomfy_format_version"] = VIBECOMFY_FORMAT_VERSION
    plain["compiled_api"] = workflow.compile("api")
    return plain


def _build_provenance(
    *,
    source: str,
    candidate: dict[str, Any],
    source_file_sha256: str,
    source_workflow_sha256: str,
    canonical_hash: str,
    node_class_multiset: dict[str, int],
    discovered_by: str,
    discovered_at: str,
) -> dict[str, Any]:
    """Build the provenance blob embedded in the workflow metadata."""
    external_id_parts = [
        source,
        str(candidate.get("message_id") or candidate.get("path") or ""),
        str(candidate.get("filename") or ""),
        source_file_sha256[:16],
    ]
    external_id = ":".join(part for part in external_id_parts if part)

    return {
        "source": source,
        "external_id": external_id,
        "source_url": candidate.get("url") or candidate.get("source_url") or None,
        "source_type": candidate.get("source_kind") or _infer_source_type(candidate),
        "authority_tier": candidate.get("authority_tier") or "community",
        "filename": candidate.get("filename") or None,
        "channel_id": candidate.get("channel_id") or None,
        "channel_name": candidate.get("channel_name") or None,
        "message_id": candidate.get("message_id") or None,
        "guild_id": candidate.get("guild_id") or None,
        "thread_id": candidate.get("thread_id") or None,
        "discord_attachment_id": candidate.get("attachment_id") or None,
        "repo": candidate.get("repo") or None,
        "repo_path": candidate.get("path") or None,
        "repo_branch": candidate.get("branch") or None,
        "content_preview": candidate.get("content_preview") or None,
        "workflow_format": candidate.get("workflow_format") or None,
        "node_count": candidate.get("node_count") or len(node_class_multiset),
        "node_class_multiset": node_class_multiset,
        "source_file_sha256": source_file_sha256,
        "source_workflow_sha256": source_workflow_sha256,
        "canonical_workflow_hash": canonical_hash,
        "graph_identity_version": GRAPH_IDENTITY_VERSION,
        "canonical_workflow_representation": "vibecomfy.canonical_form.v1",
        "discovered_by": discovered_by,
        "discovered_at": discovered_at,
        "ingested_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _infer_source_type(candidate: dict[str, Any]) -> str:
    if candidate.get("owner") or candidate.get("repo"):
        return "github_file"
    if candidate.get("channel_id") is not None:
        return "discord_attachment"
    return "unknown"


def _load_raw_workflow(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)


def _classify_source_workflow(raw: dict[str, Any]) -> tuple[str, list[str]] | None:
    """Lightweight classification matching the Discord scanner's logic."""
    if not isinstance(raw, dict):
        return None
    nodes = raw.get("nodes")
    if isinstance(nodes, list):
        classes = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_type = node.get("type") or node.get("class_type")
            if node_type or "inputs" in node or "widgets_values" in node:
                classes.append(str(node_type or "unknown"))
        if len(classes) >= 2:
            return "comfy_ui", classes
    api_classes = []
    numeric_keys = 0
    for key, node in raw.items():
        if str(key).isdigit():
            numeric_keys += 1
        if isinstance(node, dict) and "class_type" in node and "inputs" in node:
            api_classes.append(str(node.get("class_type") or "unknown"))
    if len(api_classes) >= 2 and numeric_keys >= max(1, len(api_classes) // 2):
        return "comfy_api", api_classes
    for key in ("workflow", "prompt"):
        nested = raw.get(key)
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except json.JSONDecodeError:
                nested = None
        nested_result = _classify_source_workflow(nested) if isinstance(nested, dict) else None
        if nested_result:
            workflow_format, classes = nested_result
            return f"nested_{key}_{workflow_format}", classes
    return None


def _candidate_identity(
    candidate: dict[str, Any],
) -> dict[str, Any] | None:
    """Compute hashes and canonical identity without building a VibeWorkflow."""
    raw_path = Path(candidate.get("saved_path") or "")
    if not raw_path.exists():
        return {"status": "missing_raw_file", "error": f"saved_path does not exist: {raw_path}"}

    try:
        raw_bytes = raw_path.read_bytes()
        source_file_sha256 = _sha256_bytes(raw_bytes)
        raw_workflow = _load_raw_workflow(raw_path)
        classification = _classify_source_workflow(raw_workflow)
        if classification is None:
            return {"status": "not_comfy_workflow", "error": "source file does not classify as a ComfyUI workflow"}

        source_workflow_text = _canonical_json(raw_workflow)
        source_workflow_sha256 = _sha256_text(source_workflow_text)
        api_workflow = _extract_api_workflow(raw_workflow)
        canonical_hash = _canonical_workflow_hash(api_workflow)
        class_multiset = _node_class_multiset(api_workflow)
        return {
            "status": "ok",
            "raw_path": raw_path,
            "raw_bytes": raw_bytes,
            "raw_workflow": raw_workflow,
            "api_workflow": api_workflow,
            "source_file_sha256": source_file_sha256,
            "source_workflow_sha256": source_workflow_sha256,
            "canonical_workflow_hash": canonical_hash,
            "node_class_multiset": class_multiset,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _copy_to_shadow(
    raw_bytes: bytes,
    source_file_sha256: str,
    filename: str,
    shadow_dir: Path,
) -> Path:
    shadow_dir.mkdir(parents=True, exist_ok=True)
    shadow_name = f"{source_file_sha256[:16]}-{_safe_id(filename)}"
    shadow_path = shadow_dir / shadow_name
    if not shadow_path.exists():
        shadow_path.write_bytes(raw_bytes)
    return shadow_path


def _convert_and_save(
    candidate: dict[str, Any],
    identity: dict[str, Any],
    *,
    source: str,
    discovered_by: str,
    discovered_at: str,
    shadow_dir: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Convert a unique candidate and write its corpus + shadow files."""
    raw_path = identity["raw_path"]
    raw_bytes = identity["raw_bytes"]
    api_workflow = identity["api_workflow"]
    canonical_hash = identity["canonical_workflow_hash"]
    source_file_sha256 = identity["source_file_sha256"]
    source_workflow_sha256 = identity["source_workflow_sha256"]
    class_multiset = identity["node_class_multiset"]

    workflow = convert_to_vibe_format(
        api_workflow,
        source_path=str(raw_path),
        workflow_id=source_file_sha256[:16],
    )

    provenance = _build_provenance(
        source=source,
        candidate=candidate,
        source_file_sha256=source_file_sha256,
        source_workflow_sha256=source_workflow_sha256,
        canonical_hash=canonical_hash,
        node_class_multiset=class_multiset,
        discovered_by=discovered_by,
        discovered_at=discovered_at,
    )

    workflow.source.provenance = provenance
    workflow.metadata.setdefault("provenance", {})
    if isinstance(workflow.metadata["provenance"], dict):
        workflow.metadata["provenance"].update(provenance)
    else:
        workflow.metadata["provenance"] = provenance
    workflow.metadata["external_workflow"] = True
    workflow.metadata["source_namespace"] = source

    filename = candidate.get("filename") or raw_path.name
    shadow_path = _copy_to_shadow(raw_bytes, source_file_sha256, filename, shadow_dir)

    out_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = out_dir / f"{canonical_hash[:16]}.json"
    corpus_path.write_text(
        _canonical_json(_vibe_workflow_to_dict(workflow)),
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "shadow_path": _repo_relative(shadow_path),
        "corpus_path": _repo_relative(corpus_path),
        "canonical_workflow_hash": canonical_hash,
        "source_file_sha256": source_file_sha256,
        "source_workflow_sha256": source_workflow_sha256,
    }


def _provenance_summary(
    candidate: dict[str, Any],
    identity: dict[str, Any],
    *,
    source: str,
    discovered_by: str,
    discovered_at: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "external_id": f"{source}:{candidate.get('message_id') or candidate.get('path') or ''}:{candidate.get('filename') or ''}",
        "source_url": candidate.get("url") or candidate.get("source_url"),
        "filename": candidate.get("filename"),
        "channel_name": candidate.get("channel_name"),
        "message_id": candidate.get("message_id"),
        "repo": candidate.get("repo"),
        "repo_path": candidate.get("path"),
        "discovered_at": discovered_at,
        "discovered_by": discovered_by,
        "source_file_sha256": identity["source_file_sha256"],
        "source_workflow_sha256": identity["source_workflow_sha256"],
        "canonical_workflow_hash": identity["canonical_workflow_hash"],
    }


def _load_candidates(scan_json: Path) -> list[dict[str, Any]]:
    data = json.loads(scan_json.read_text(encoding="utf-8"))
    results = data.get("results") if isinstance(data, dict) else data
    if not isinstance(results, list):
        raise ValueError(f"{scan_json} does not contain a results list")
    return results


def _repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-json", type=Path, required=True, help="Path to scanner output JSON with results list.")
    parser.add_argument("--source", type=str, required=True, help="Source namespace, e.g. banodoco-discord-archive.")
    parser.add_argument("--discovered-by", type=str, required=True, help="Who/what discovered these workflows.")
    parser.add_argument("--discovered-at", type=str, default=None, help="ISO timestamp of discovery (defaults to now).")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Directory for converted VibeComfy workflows.")
    parser.add_argument("--shadow-dir", type=Path, default=DEFAULT_SHADOW_DIR, help="Directory for raw source copies.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to the corpus manifest.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum candidates to process.")
    parser.add_argument("--skip-errors", action="store_true", help="Skip individual candidate errors instead of stopping.")
    args = parser.parse_args(argv)

    if not args.scan_json.exists():
        print(f"scan-json not found: {args.scan_json}", file=sys.stderr)
        return 1

    # Resolve output directories to absolute paths so relative_to(REPO_ROOT) works.
    args.out_dir = args.out_dir.resolve()
    args.shadow_dir = args.shadow_dir.resolve()
    args.manifest = args.manifest.resolve()

    discovered_at = args.discovered_at or _now_iso()
    candidates = _load_candidates(args.scan_json)
    workflow_candidates = [
        c for c in candidates
        if isinstance(c, dict) and c.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}
    ]
    if args.limit:
        workflow_candidates = workflow_candidates[: args.limit]

    print(f"processing {len(workflow_candidates)} workflow candidates from {args.source}", flush=True)

    # Load existing manifest for dedupe.
    manifest: dict[str, Any]
    if args.manifest.exists():
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    else:
        manifest = {
            "version": "1.0",
            "created_at": discovered_at,
            "source": args.source,
            "discovered_by": args.discovered_by,
            "workflows": [],
        }

    existing_by_canonical: dict[str, dict[str, Any]] = {}
    for row in manifest.get("workflows", []):
        canonical = row.get("canonical_workflow_hash")
        if isinstance(canonical, str):
            existing_by_canonical[canonical] = row

    skipped = 0
    for idx, candidate in enumerate(workflow_candidates, start=1):
        identity = _candidate_identity(candidate)
        if identity["status"] != "ok":
            skipped += 1
            if not args.skip_errors:
                print(f"candidate {idx} failed: {identity['status']}: {identity['error']}", file=sys.stderr)
            continue

        canonical = identity["canonical_workflow_hash"]
        filename = candidate.get("filename") or identity["raw_path"].name
        # Always preserve the alternate raw source file in the shadow directory.
        _copy_to_shadow(
            identity["raw_bytes"],
            identity["source_file_sha256"],
            filename,
            args.shadow_dir,
        )

        summary = _provenance_summary(
            candidate,
            identity,
            source=args.source,
            discovered_by=args.discovered_by,
            discovered_at=discovered_at,
        )

        if canonical in existing_by_canonical:
            existing_by_canonical[canonical].setdefault("alternate_sources", []).append(summary)
        else:
            try:
                result = _convert_and_save(
                    candidate,
                    identity,
                    source=args.source,
                    discovered_by=args.discovered_by,
                    discovered_at=discovered_at,
                    shadow_dir=args.shadow_dir,
                    out_dir=args.out_dir,
                )
            except Exception as exc:  # noqa: BLE001
                skipped += 1
                if not args.skip_errors:
                    print(f"candidate {idx} conversion failed: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            row = {
                "canonical_workflow_hash": canonical,
                "workflow_id": canonical[:16],
                "corpus_path": result["corpus_path"],
                "shadow_path": result["shadow_path"],
                "primary_source": summary,
                "alternate_sources": [],
                "status": "ok",
            }
            existing_by_canonical[canonical] = row
            manifest["workflows"].append(row)

        if idx % 100 == 0:
            print(f"progress: {idx}/{len(workflow_candidates)} processed, {len(existing_by_canonical)} unique workflows", flush=True)

    # Sort manifest workflows deterministically.
    manifest["workflows"] = sorted(manifest["workflows"], key=lambda r: r["canonical_workflow_hash"])
    manifest["updated_at"] = _now_iso()
    manifest["summary"] = {
        "candidates_processed": len(workflow_candidates),
        "unique_workflows": len(existing_by_canonical),
        "skipped": skipped,
        "source": args.source,
    }

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(_canonical_json(manifest), encoding="utf-8")

    print(f"manifest: {args.manifest}")
    print(f"unique workflows: {len(existing_by_canonical)}")
    print(f"shadow sources: {args.shadow_dir}")
    print(f"corpus: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
