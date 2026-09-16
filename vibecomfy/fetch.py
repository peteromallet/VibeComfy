"""Model download resolution and verification.

Destination authorization covers hostile/malformed metadata and pre-existing
symlinks.  Concurrent same-user hostile filesystem mutation between the
authorization and mutation rechecks is explicitly outside this owner's frozen
threat model; descriptor-relative ``openat`` protection is not required here.
"""

from __future__ import annotations

import json
import hashlib
import os
import stat
import tempfile
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

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


def _relative_asset_path(value: Any, *, field: str) -> Path:
    """Reject platform-specific absolute paths and traversal before joining."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError(f"model asset {field} must be a non-empty relative path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or bool(windows.root)
        or ".." in posix.parts
        or ".." in windows.parts
        or "\\" in value
        or value.endswith(("/", "\\"))
        or value.rstrip("/").rsplit("/", 1)[-1] == "."
        or (not posix.parts and not windows.parts)
    ):
        raise ValueError(
            f"model asset {field} must be a relative path without '..' segments: {value!r}"
        )
    return Path(value)


def _authorized_destination(root: Path, relative: Path, *, field: str) -> tuple[Path, Path]:
    """Return a stable authorization root and destination after resolving symlinks."""
    candidate = root / relative
    try:
        resolved_root = root.resolve(strict=False)
        resolved_candidate = candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"model asset {field} could not be resolved safely: {relative!s}") from exc
    if resolved_candidate == resolved_root or not resolved_candidate.is_relative_to(resolved_root):
        raise ValueError(
            f"model asset {field} resolves outside its authorized root {resolved_root}: {relative!s}"
        )
    return resolved_root, resolved_candidate


def _destination_for_entry(
    entry: Mapping[str, Any], *, root: Path | None = None
) -> tuple[Path, Path, str]:
    base = Path(root) if root is not None else models_root()
    if not base.is_absolute():
        base = Path.cwd() / base
    if "target_path" in entry:
        target_path = entry["target_path"]
        target = _relative_asset_path(target_path, field="target_path")
        authorized_root, destination = _authorized_destination(
            base.parent, target, field="target_path"
        )
        return authorized_root, destination, "target_path"
    if "subdir" in entry:
        subdir = entry["subdir"]
    elif "directory" in entry:
        subdir = entry["directory"]
    else:
        subdir = None
    if not isinstance(subdir, str) or not subdir:
        raise KeyError("model asset entry requires 'subdir' or 'directory'")
    relative_subdir = _relative_asset_path(subdir, field="subdir")
    relative_name = _relative_asset_path(entry["name"], field="name")
    authorized_root, destination = _authorized_destination(
        base, relative_subdir / relative_name, field="subdir/name"
    )
    return authorized_root, destination, "subdir/name"


def _assert_destination_stable(root: Path, destination: Path, *, field: str) -> None:
    """Reject a destination whose resolution changed after authorization."""
    try:
        current = destination.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ValueError(
            f"model asset {field} destination could not be re-authorized: {destination}"
        ) from exc
    if current != destination or not current.is_relative_to(root):
        raise ValueError(
            f"model asset {field} destination changed after authorization: "
            f"expected {destination}, resolved {current}"
        )


def _temp_identity(path: Path) -> tuple[int, int] | None:
    try:
        info = os.stat(path, follow_symlinks=False)
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    return info.st_dev, info.st_ino


def _unlink_owned_temp(path: Path | None, identity: tuple[int, int] | None) -> None:
    if path is None or identity is None or _temp_identity(path) != identity:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _open_owned_temp(parent: Path) -> tuple[Path, Any, tuple[int, int]]:
    fd, tmp_name = tempfile.mkstemp(prefix=".vibecomfy-download-", suffix=".tmp", dir=parent)
    tmp = Path(tmp_name)
    identity: tuple[int, int] | None = None
    try:
        opened = os.fstat(fd)
        identity = (opened.st_dev, opened.st_ino)
        handle = os.fdopen(fd, "wb")
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        _unlink_owned_temp(tmp, identity)
        raise
    assert identity is not None
    return tmp, handle, identity


def local_path(entry: Mapping[str, Any], *, root: Path | None = None) -> Path:
    _authorized_root, destination, _field = _destination_for_entry(entry, root=root)
    return destination


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


def _source_receipt_matches(
    receipt_path: Path,
    *,
    path: Path,
    requested_url: str,
    requested_revision: str | None,
    fingerprint: dict[str, int],
) -> bool:
    """Return whether a URL resolution receipt still witnesses this file."""
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    stat_data = receipt.get("stat") if isinstance(receipt, dict) else None
    return (
        isinstance(receipt, dict)
        and receipt.get("schema_version") == 1
        and receipt.get("kind") == "model_url_resolution"
        and receipt.get("path") == str(path.resolve(strict=False))
        and receipt.get("requested_url") == requested_url
        and (
            requested_revision is None
            or receipt.get("hf_revision") == requested_revision
        )
        and isinstance(stat_data, dict)
        and all(stat_data.get(field) == fingerprint.get(field) for field in ("inode", "size", "mtime_ns"))
        and isinstance(receipt.get("observed_sha256"), str)
        and len(receipt["observed_sha256"]) == 64
        and receipt.get("size_bytes") == fingerprint.get("size")
    )


def _write_source_receipt(
    receipt_path: Path,
    *,
    path: Path,
    requested_url: str,
    requested_revision: str | None,
    effective_url: str,
    fingerprint: dict[str, int],
    observed_sha256: str,
) -> None:
    """Persist URL, effective redirect, bytes identity, and stat evidence."""
    _write_verification_receipt(
        receipt_path,
        {
            "schema_version": 1,
            "kind": "model_url_resolution",
            "path": str(path.resolve(strict=False)),
            "requested_url": requested_url,
            **(
                {"hf_revision": requested_revision}
                if requested_revision is not None
                else {}
            ),
            "effective_url": effective_url,
            "observed_sha256": observed_sha256.lower(),
            # Keep the source witness compatible with ``verify``'s existing
            # digest cache so a pinned entry can reuse the same receipt.
            "expected_sha256": observed_sha256.lower(),
            "actual_sha256": observed_sha256.lower(),
            "expected_size_bytes": fingerprint["size"],
            "size_bytes": fingerprint["size"],
            "stat": fingerprint,
        },
    )


def _refresh_source_receipt(
    receipt_path: Path,
    *,
    path: Path,
    requested_url: str,
    requested_revision: str | None,
    effective_url: str,
    fingerprint: dict[str, int],
) -> None:
    """Reattach URL fields after the legacy verification writer runs."""
    try:
        verification = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return
    observed = verification.get("actual_sha256") if isinstance(verification, dict) else None
    if isinstance(observed, str) and len(observed) == 64:
        _write_source_receipt(
            receipt_path,
            path=path,
            requested_url=requested_url,
            requested_revision=requested_revision,
            effective_url=effective_url,
            fingerprint=fingerprint,
            observed_sha256=observed,
        )


def read_resolution_receipt(
    entry: Mapping[str, Any], *, root: Path | None = None
) -> dict[str, Any] | None:
    """Read the verified URL-resolution witness for a model entry, if valid."""
    path = local_path(entry, root=root)
    receipt_path = _verification_receipt_path(path, root=root)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    requested_url = _strip_download_true(str(entry.get("url", "")))
    requested_revision = entry.get("hf_revision")
    if not isinstance(requested_revision, str) or not requested_revision:
        requested_revision = None
    if not path.is_file() or not _source_receipt_matches(
        receipt_path,
        path=path,
        requested_url=requested_url,
        requested_revision=requested_revision,
        fingerprint=_model_stat_fingerprint(path),
    ):
        return None
    return dict(receipt)


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
    quiet: bool = False,
) -> Path:
    authorized_root, path, destination_field = _destination_for_entry(entry, root=root)
    name = str(entry["name"])
    requested_url = _strip_download_true(str(entry.get("url", "")))
    requested_revision = entry.get("hf_revision")
    if not isinstance(requested_revision, str) or not requested_revision:
        requested_revision = None
    receipt_path = _verification_receipt_path(path, root=root)
    if path.is_file() and path.stat().st_size > 0 and not force:
        fingerprint = _model_stat_fingerprint(path)
        if _source_receipt_matches(
            receipt_path,
            path=path,
            requested_url=requested_url,
            requested_revision=requested_revision,
            fingerprint=fingerprint,
        ):
            prior_source = None
            try:
                prior_source = json.loads(receipt_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                pass
            cached = verify(entry, path, root=root, force=force_verify)
            if force_verify:
                _refresh_source_receipt(
                    receipt_path,
                    path=path,
                    requested_url=requested_url,
                    requested_revision=requested_revision,
                    effective_url=(
                        str(prior_source.get("effective_url", requested_url))
                        if isinstance(prior_source, dict)
                        else requested_url
                    ),
                    fingerprint=_model_stat_fingerprint(path),
                )
            if not quiet:
                print(f"skipped {name}" + (" (cached sha256)" if cached else " (cached URL resolution)"))
            return path
        # Preserve the long-standing local-file reuse behavior when there is
        # no URL witness yet.  Hashing once below creates one.  A receipt for
        # a different URL, however, is evidence of a changed source and must
        # not silently reuse stale bytes.
        try:
            prior_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            prior_receipt = None
        source_url_changed = (
            isinstance(prior_receipt, dict)
            and prior_receipt.get("kind") == "model_url_resolution"
            and prior_receipt.get("requested_url") != requested_url
        )
        source_revision_changed = (
            isinstance(prior_receipt, dict)
            and prior_receipt.get("kind") == "model_url_resolution"
            and requested_revision is not None
            and prior_receipt.get("hf_revision") != requested_revision
        )
        if (
            not source_url_changed
            and not source_revision_changed
            and isinstance(entry.get("sha256"), str)
            and entry.get("sha256")
            and entry.get("gated") is not True
        ):
            # A pinned model can validate a changed stat without downloading
            # again.  Refresh the URL witness from the verification receipt.
            verify(entry, path, root=root, force=force_verify)
            _refresh_source_receipt(
                receipt_path,
                path=path,
                requested_url=requested_url,
                requested_revision=requested_revision,
                effective_url=(
                    str(prior_receipt.get("effective_url", requested_url))
                    if isinstance(prior_receipt, dict)
                    else requested_url
                ),
                fingerprint=_model_stat_fingerprint(path),
            )
            if not quiet:
                print(f"skipped {name} (cached sha256)")
            return path
        if not (
            isinstance(prior_receipt, dict)
            and prior_receipt.get("kind") == "model_url_resolution"
        ):
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                    digest.update(chunk)
            _write_source_receipt(
                receipt_path,
                path=path,
                requested_url=requested_url,
                requested_revision=requested_revision,
                effective_url=requested_url,
                fingerprint=fingerprint,
                observed_sha256=digest.hexdigest(),
            )
            cached = verify(entry, path, root=root, force=force_verify)
            if not quiet:
                print(f"skipped {name}" + (" (cached sha256)" if cached else ""))
            return path

    url = requested_url
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

    _assert_destination_stable(authorized_root, path, field=destination_field)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path | None = None
    tmp_identity: tuple[int, int] | None = None
    effective_url = url
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with stream_context as response:
            _raise_for_status(response.status_code, url)
            effective_url = str(getattr(response, "url", url))
            _assert_destination_stable(authorized_root, path, field=destination_field)
            tmp, handle, tmp_identity = _open_owned_temp(path.parent)
            with handle:
                for chunk in response.iter_bytes():
                    if chunk:
                        handle.write(chunk)
                        digest.update(chunk)
                        size_bytes += len(chunk)
        _assert_destination_stable(authorized_root, path, field=destination_field)
        if tmp is None or tmp_identity is None or _temp_identity(tmp) != tmp_identity:
            raise RuntimeError("download temporary file changed before final replace")
        _assert_destination_stable(authorized_root, path, field=destination_field)
        os.replace(tmp, path)
        _assert_destination_stable(authorized_root, path, field=destination_field)
    except BaseException:
        _unlink_owned_temp(tmp, tmp_identity)
        raise
    fingerprint = _model_stat_fingerprint(path)
    if fingerprint["size"] != size_bytes:
        raise RuntimeError(f"downloaded size changed while publishing {name}")
    verify(entry, path, root=root, force=True)
    _write_source_receipt(
        receipt_path,
        path=path,
        requested_url=requested_url,
        requested_revision=requested_revision,
        effective_url=effective_url,
        fingerprint=fingerprint,
        observed_sha256=digest.hexdigest(),
    )
    return path


def download_many(
    entries: list[dict],
    *,
    force: bool = False,
    force_verify: bool = False,
    root: Path | None = None,
    max_workers: int = 2,
    quiet: bool = False,
) -> list[Path]:
    if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers < 1:
        raise ValueError("max_workers must be a positive integer")

    def download_one(entry: dict) -> tuple[dict, Path, bool]:
        name = str(entry.get("name", "<unknown>"))
        was_present = is_present(entry, root=root) and not force
        path = download(
            entry, force=force, force_verify=force_verify, root=root, quiet=quiet
        )
        return entry, path, was_present

    paths: list[Path] = []
    failures = 0
    pool: ThreadPoolExecutor | None = None
    try:
        if max_workers > 1 and len(entries) >= 2:
            pool = ThreadPoolExecutor(
                max_workers=min(max_workers, len(entries)),
                thread_name_prefix="vibecomfy-fetch",
            )
            pending = [(entry, pool.submit(download_one, entry)) for entry in entries]
        else:
            pending = [(entry, None) for entry in entries]
        for entry, future in pending:
            name = str(entry.get("name", "<unknown>"))
            try:
                _entry, path, was_present = (
                    download_one(entry) if future is None else future.result()
                )
            except Exception as exc:
                failures += 1
                if not quiet:
                    print(f"failed {name}: {exc}")
                continue
            paths.append(path)
            if not quiet and not was_present:
                print(f"downloaded {name} -> {path}")
    finally:
        if pool is not None:
            pool.shutdown(wait=True)
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


__all__ = [
    "download",
    "download_many",
    "is_present",
    "local_path",
    "models_root",
    "read_resolution_receipt",
    "verify",
]
