#!/usr/bin/env python3
"""Enumerate ComfyUI workflows in public GitHub repositories.

Clones are avoided by using the GitHub Git Trees API and raw.githubusercontent.com
downloads. Classified workflow files are saved to a shadow directory and a
scan-compatible JSON manifest is produced for `ingest_external_workflows.py`.
"""

from __future__ import annotations

import argparse
import base64
import collections
import concurrent.futures
import hashlib
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / "external_workflows" / "github_scan.json"
DEFAULT_SAVE_DIR = REPO_ROOT / "external_workflows" / ".shadow" / "source"


def _github_token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_API_TOKEN")


def _api_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "vibecomfy-workflow-enumerator/0.1",
    }
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raw_headers() -> dict[str, str]:
    headers = {"User-Agent": "vibecomfy-workflow-enumerator/0.1"}
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_json(url: str, headers: dict[str, str], timeout: int = 60) -> Any:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_bytes_with_retry(
    url: str,
    *,
    headers: dict[str, str],
    timeout: int = 60,
    attempts: int = 5,
) -> tuple[int, bytes, dict[str, str]]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read(), dict(response.headers)
        except urllib.error.HTTPError as error:
            if error.code == 429:
                retry_after = error.headers.get("Retry-After")
                try:
                    payload = json.loads(error.read().decode("utf-8"))
                    wait = float(payload.get("retry_after", retry_after or 1))
                except Exception:
                    wait = float(retry_after or 1)
                time.sleep(wait + 0.1)
                continue
            if 500 <= error.code < 600:
                last_error = error
                time.sleep(0.5 * (attempt + 1))
                continue
            body = error.read()
            return error.code, body, dict(error.headers)
        except Exception as error:  # noqa: BLE001
            last_error = error
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"request failed after retries: {last_error}")


def _default_branch(owner: str, repo: str) -> str:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    data = _http_json(url, headers=_api_headers())
    return str(data.get("default_branch", "main"))


def _tree_entries(owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    data = _http_json(url, headers=_api_headers(), timeout=120)
    return [item for item in data.get("tree", []) if isinstance(item, dict)]


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or "file"


def _classify_comfy_json(value: Any) -> tuple[str, list[str]] | None:
    if not isinstance(value, dict):
        return None
    nodes = value.get("nodes")
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
    for key, node in value.items():
        if str(key).isdigit():
            numeric_keys += 1
        if isinstance(node, dict) and "class_type" in node and "inputs" in node:
            api_classes.append(str(node.get("class_type") or "unknown"))
    if len(api_classes) >= 2 and numeric_keys >= max(1, len(api_classes) // 2):
        return "comfy_api", api_classes
    for key in ("workflow", "prompt"):
        nested = value.get(key)
        if isinstance(nested, str):
            try:
                nested = json.loads(nested)
            except json.JSONDecodeError:
                nested = None
        nested_result = _classify_comfy_json(nested) if isinstance(nested, dict) else None
        if nested_result:
            workflow_format, classes = nested_result
            return f"nested_{key}_{workflow_format}", classes
    return None


def _scan_png_text_chunks(data: bytes) -> list[dict[str, str]]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return []
    chunks: list[dict[str, str]] = []
    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        pos = pos + 12 + length
        try:
            if chunk_type == b"tEXt":
                key, text = payload.split(b"\x00", 1)
                chunks.append({"key": key.decode("latin-1"), "text": text.decode("utf-8", "ignore")})
            elif chunk_type == b"zTXt":
                key, rest = payload.split(b"\x00", 1)
                if rest and rest[0] == 0:
                    chunks.append({"key": key.decode("latin-1"), "text": zlib.decompress(rest[1:]).decode("utf-8", "ignore")})
            elif chunk_type == b"iTXt":
                parts = payload.split(b"\x00", 5)
                if len(parts) == 6:
                    key = parts[0].decode("utf-8", "ignore")
                    compressed = parts[1] == b"\x01"
                    text_data = parts[5]
                    if compressed:
                        text_data = zlib.decompress(text_data)
                    chunks.append({"key": key, "text": text_data.decode("utf-8", "ignore")})
        except Exception:
            continue
        if chunk_type == b"IEND":
            break
    return chunks


def _classify_image_workflow(data: bytes) -> dict[str, Any] | None:
    for chunk in _scan_png_text_chunks(data):
        key = chunk["key"].lower()
        if key not in {"workflow", "prompt", "parameters"}:
            continue
        text = chunk["text"].strip()
        match = None
        if text.startswith("{"):
            match = text
        else:
            found = re.search(r"(\{.*(?:last_node_id|class_type|nodes).*)\}", text, re.DOTALL)
            if found:
                match = found.group(1)
        if not match:
            continue
        try:
            value = json.loads(match)
        except json.JSONDecodeError:
            continue
        classified = _classify_comfy_json(value)
        if classified:
            workflow_format, classes = classified
            return {"workflow_format": f"png_{key}_{workflow_format}", "node_count": len(classes), "node_classes": classes}
    return None


def _decode_json_bytes(data: bytes) -> Any:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return json.loads(text)


def _process_blob(
    owner: str,
    repo: str,
    branch: str,
    item: dict[str, Any],
    *,
    save_dir: Path,
    max_bytes: int,
) -> dict[str, Any] | None:
    path = str(item.get("path") or "")
    if not path:
        return None
    filename = Path(path).name
    lower = path.lower()
    is_json = lower.endswith(".json")
    is_image = lower.endswith((".png", ".webp", ".jpg", ".jpeg"))
    if not is_json and not is_image:
        return None

    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{urllib.parse.quote(path)}"
    result: dict[str, Any] = {
        "owner": owner,
        "repo": repo,
        "branch": branch,
        "path": path,
        "filename": filename,
        "source_url": raw_url,
        "url": raw_url,
    }

    try:
        status, data, headers = _http_bytes_with_retry(raw_url, headers=_raw_headers(), timeout=60)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "download_error"
        result["error"] = str(exc)
        return result

    result["download_status"] = status
    result["download_content_type"] = headers.get("Content-Type")
    if status != 200:
        result["status"] = "download_error"
        result["error"] = f"HTTP {status}"
        return result

    if len(data) > max_bytes:
        result["status"] = "skipped_too_large"
        return result

    sha256 = hashlib.sha256(data).hexdigest()
    result["sha256"] = sha256
    result["bytes"] = len(data)

    if is_json:
        try:
            value = _decode_json_bytes(data)
        except Exception as exc:  # noqa: BLE001
            result["status"] = "json_parse_error"
            result["error"] = str(exc)
            return result
        classified = _classify_comfy_json(value)
        if classified:
            workflow_format, classes = classified
            save_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f"{sha256[:16]}-{_safe_filename(filename)}"
            saved_path = save_dir / safe_name
            if not saved_path.exists():
                saved_path.write_bytes(data)
            result["status"] = "comfy_workflow"
            result["workflow_format"] = workflow_format
            result["node_count"] = len(classes)
            result["node_classes"] = collections.Counter(classes).most_common(30)
            result["saved_path"] = str(saved_path)
        else:
            result["status"] = "json_non_comfy"
    else:
        classified_image = _classify_image_workflow(data)
        if classified_image:
            save_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f"{sha256[:16]}-{_safe_filename(filename)}"
            saved_path = save_dir / safe_name
            if not saved_path.exists():
                saved_path.write_bytes(data)
            result["status"] = "image_embedded_comfy_workflow"
            result["workflow_format"] = classified_image["workflow_format"]
            result["node_count"] = classified_image["node_count"]
            result["node_classes"] = collections.Counter(classified_image["node_classes"]).most_common(30)
            result["saved_path"] = str(saved_path)
        else:
            result["status"] = "image_no_comfy_metadata"

    return result


def _repo_slug(value: str) -> tuple[str, str]:
    parts = value.split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError(f"invalid repo slug: {value!r}; expected owner/repo")
    return parts[0], parts[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="+", type=_repo_slug, help="Owner/repo slugs to enumerate.")
    parser.add_argument("--branch", type=str, default=None, help="Branch or tag (default: repository default branch).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Scan-compatible JSON output path.")
    parser.add_argument("--save-dir", type=Path, default=DEFAULT_SAVE_DIR, help="Directory to save confirmed workflow files.")
    parser.add_argument("--max-bytes", type=int, default=25_000_000, help="Skip files larger than this.")
    parser.add_argument("--max-files", type=int, default=None, help="Maximum workflow-like files to download per repo.")
    parser.add_argument("--max-workers", type=int, default=8, help="Concurrent download workers.")
    args = parser.parse_args(argv)

    args.out = args.out.resolve()
    args.save_dir = args.save_dir.resolve()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.save_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict[str, Any]] = []
    repo_summaries: list[dict[str, Any]] = []

    for owner, repo in args.repo:
        print(f"enumerating {owner}/{repo}...", flush=True)
        try:
            branch = args.branch or _default_branch(owner, repo)
            entries = _tree_entries(owner, repo, branch)
        except Exception as exc:  # noqa: BLE001
            print(f"  failed to enumerate {owner}/{repo}: {exc}", file=sys.stderr, flush=True)
            repo_summaries.append({"owner": owner, "repo": repo, "error": str(exc)})
            continue

        candidates = [
            item
            for item in entries
            if str(item.get("type")) == "blob"
            and str(item.get("path") or "").lower().endswith((".json", ".png", ".webp", ".jpg", ".jpeg"))
        ]
        print(f"  {len(candidates)} candidate files on {branch}", flush=True)

        if args.max_files:
            candidates = candidates[: args.max_files]

        results: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [
                executor.submit(
                    _process_blob,
                    owner,
                    repo,
                    branch,
                    item,
                    save_dir=args.save_dir,
                    max_bytes=args.max_bytes,
                )
                for item in candidates
            ]
            for idx, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = {"status": "exception", "error": str(exc)}
                if result:
                    results.append(result)
                if idx % 50 == 0:
                    workflow_count = sum(
                        1 for r in results if r.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}
                    )
                    print(f"  progress {idx}/{len(candidates)} workflows={workflow_count}", flush=True)

        workflows = [r for r in results if r.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}]
        repo_summaries.append({
            "owner": owner,
            "repo": repo,
            "branch": branch,
            "candidates": len(candidates),
            "workflow_rows": len(workflows),
            "unique_sha256": len({r.get("sha256") for r in workflows if r.get("sha256")}),
        })
        all_results.extend(results)
        print(f"  done: {len(workflows)} workflows from {owner}/{repo}", flush=True)

    payload = {
        "summary": {
            "source": "github",
            "repos": repo_summaries,
            "result_rows": len(all_results),
            "workflow_rows": len([r for r in all_results if r.get("status") in {"comfy_workflow", "image_embedded_comfy_workflow"}]),
            "unique_workflow_sha256": len({r.get("sha256") for r in all_results if r.get("sha256")}),
        },
        "results": all_results,
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
