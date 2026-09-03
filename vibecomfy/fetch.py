from __future__ import annotations

import os
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping
import hashlib
import httpx


def models_root() -> Path:
    for env_name in ("VIBECOMFY_MODELS_ROOT", "COMFY_MODELS_ROOT"):
        value = os.environ.get(env_name)
        if value:
            return Path(value)
    extra_model_paths = os.environ.get("COMFYUI_EXTRA_MODEL_PATHS_PATH")
    if extra_model_paths:
        path = Path(extra_model_paths)
        if path.suffix.lower() not in {".yaml", ".yml"}:
            return path
    # Consult local-library TOML config AFTER all env-var overrides (including
    # COMFYUI_EXTRA_MODEL_PATHS_PATH) but BEFORE the ComfyUI/models hardcoded
    # fallback — this lets a persistent repo/global config act as a default
    # without requiring an env var on every invocation.
    try:
        from vibecomfy.local_library import Slot
        from vibecomfy.local_library import resolved_path as _ll_resolved_path

        config_path = _ll_resolved_path(Slot.models)
        if config_path is not None:
            return config_path
    except Exception:
        pass
    try:
        from comfy.cmd.folder_paths import folder_names_and_paths

        return Path(folder_names_and_paths["checkpoints"][0][0]).parent
    except Exception:
        return Path("ComfyUI/models")


def local_path(entry: Mapping[str, Any], *, root: Path | None = None) -> Path:
    base = root if root is not None else models_root()
    target_path = entry.get("target_path")
    if isinstance(target_path, str) and target_path:
        target = Path(target_path)
        if target.is_absolute():
            return target
        return base.parent / target
    subdir = entry.get("subdir") or entry.get("directory")
    if not isinstance(subdir, str) or not subdir:
        raise KeyError("model asset entry requires 'subdir' or 'directory'")
    return base / subdir / str(entry["name"])


def is_present(entry: Mapping[str, Any], *, root: Path | None = None) -> bool:
    path = local_path(entry, root=root)
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if entry.get("gated") is True:
        return True
    return True


def verify(
    entry: Mapping[str, Any],
    path: Path | None = None,
    *,
    root: Path | None = None,
    force: bool = False,
) -> bool:
    """Verify an asset, returning whether a durable receipt was reused.

    Receipts are only accepted when the expected digest, canonical path, and
    complete ``stat`` fingerprint all match. A false return means the file
    body was streamed and a fresh receipt was attempted.
    """
    resolved = path or local_path(entry, root=root)
    expected_size = entry.get("size_bytes")
    if isinstance(expected_size, int) and resolved.stat().st_size != expected_size:
        raise RuntimeError(
            f"size mismatch for {entry['name']}: expected {expected_size} bytes, got {resolved.stat().st_size}"
        )
    expected_sha = entry.get("sha256")
    if entry.get("gated") is True:
        return False
    if isinstance(expected_sha, str) and expected_sha:
        expected_sha = expected_sha.lower()
        fingerprint = _model_stat_fingerprint(resolved)
        receipt_path = _verification_receipt_path(resolved, root=root)
        if not force and _receipt_matches(
            receipt_path,
            path=resolved,
            expected_sha=expected_sha,
            expected_size=expected_size,
            fingerprint=fingerprint,
        ):
            return True
        digest = hashlib.sha256()
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        actual_sha = digest.hexdigest()
        if actual_sha.lower() != expected_sha:
            raise RuntimeError(f"sha256 mismatch for {entry['name']}: expected {expected_sha}, got {actual_sha}")
        after = _model_stat_fingerprint(resolved)
        if after != fingerprint:
            raise RuntimeError(f"model changed while hashing {entry['name']}; retry verification")
        _write_verification_receipt(
            receipt_path,
            {
                "schema_version": 1,
                "path": str(resolved.resolve(strict=False)),
                "expected_sha256": expected_sha,
                "expected_size_bytes": expected_size,
                "stat": fingerprint,
                "actual_sha256": actual_sha.lower(),
            },
        )
    return False


def _model_stat_fingerprint(path: Path) -> dict[str, int]:
    stat = path.stat()
    return {
        "dev": int(stat.st_dev),
        "inode": int(stat.st_ino),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _verification_receipt_path(path: Path, *, root: Path | None = None) -> Path:
    canonical = str(path.resolve(strict=False))
    cache_root = (root if root is not None else models_root()).expanduser().resolve(strict=False)
    key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return cache_root / ".vibecomfy" / "model-verification" / f"{key}.json"


def _receipt_matches(
    receipt_path: Path,
    *,
    path: Path,
    expected_sha: str,
    expected_size: Any,
    fingerprint: dict[str, int],
) -> bool:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    receipt_stat = receipt.get("stat") if isinstance(receipt, dict) else None
    # ``st_dev`` is not stable for persistent volumes across container/pod
    # remounts (the same file can report a different device number).  Keep it
    # in receipts for diagnostics, but use the stable identity fields below
    # for cache validity so a remount does not trigger a multi-GB rehash.
    stat_matches = isinstance(receipt_stat, dict) and all(
        receipt_stat.get(field) == fingerprint.get(field)
        for field in ("inode", "size", "mtime_ns")
    )
    receipt_size = receipt.get("expected_size_bytes") if isinstance(receipt, dict) else None
    # ``size_bytes`` is optional on workflow/attempt assets.  A receipt made
    # by model ensure may have it while a later attempt manifest omits it;
    # the current stat size (and the pre-check above when an expected size is
    # supplied) still provides the size/mutation guard in either direction.
    size_metadata_matches = receipt_size is None or receipt_size == fingerprint.get("size")
    if expected_size is not None and receipt_size is not None:
        size_metadata_matches = size_metadata_matches and receipt_size == expected_size
    return (
        isinstance(receipt, dict)
        and receipt.get("schema_version") == 1
        and receipt.get("path") == str(path.resolve(strict=False))
        and str(receipt.get("expected_sha256", "")).lower() == expected_sha
        and size_metadata_matches
        and stat_matches
        and str(receipt.get("actual_sha256", "")).lower() == expected_sha
    )


def _write_verification_receipt(path: Path, receipt: dict[str, Any]) -> None:
    """Atomically publish a receipt; verification remains valid if caching fails."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(receipt, handle, sort_keys=True, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    except OSError:
        # A read-only/shared model mount must not turn a successful hash check
        # into a failed model ensure merely because its cache is unwritable.
        return


def download(
    entry: Mapping[str, Any],
    *,
    force: bool = False,
    force_verify: bool = False,
    client: Any = None,
    root: Path | None = None,
) -> Path:
    path = local_path(entry, root=root)
    name = str(entry["name"])
    if is_present(entry, root=root) and not force:
        cached = verify(entry, path, root=root, force=force_verify)
        print(f"skipped {name}" + (" (cached sha256)" if cached else ""))
        return path

    url = _strip_download_true(str(entry["url"]))
    headers: dict[str, str] = {}
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    timeout = httpx.Timeout(60, read=None)
    stream_context = (
        client.stream("GET", url, follow_redirects=True, headers=headers, timeout=timeout)
        if client is not None
        else httpx.stream("GET", url, follow_redirects=True, headers=headers, timeout=timeout)
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with stream_context as response:
            _raise_for_status(response.status_code, url)
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes():
                    if chunk:
                        handle.write(chunk)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    verify(entry, path, root=root, force=True)
    return path


def download_many(
    entries: list[dict],
    *,
    force: bool = False,
    force_verify: bool = False,
    root: Path | None = None,
) -> list[Path]:
    paths: list[Path] = []
    failures = 0
    for entry in entries:
        name = str(entry.get("name", "<unknown>"))
        was_present = is_present(entry, root=root) and not force
        try:
            path = download(entry, force=force, force_verify=force_verify, root=root)
        except Exception as exc:
            failures += 1
            print(f"failed {name}: {exc}")
            continue
        paths.append(path)
        if not was_present:
            print(f"downloaded {name} -> {path}")
    if failures:
        raise RuntimeError(f"{failures} failures")
    return paths


def _raise_for_status(status_code: int, url: str) -> None:
    if status_code in {401, 403}:
        raise PermissionError(f"License-gated download blocked for {url} — set HF_TOKEN or accept the license at the source URL.")
    if status_code == 404:
        raise FileNotFoundError(f"Asset not found at {url}")
    if not 200 <= status_code < 300:
        raise RuntimeError(f"HTTP {status_code} fetching {url}")


from vibecomfy.model_assets import _strip_download_true as _strip_download_true  # noqa: E402,F401


__all__ = ["download", "download_many", "is_present", "local_path", "models_root", "verify"]
