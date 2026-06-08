from __future__ import annotations

import os
from pathlib import Path
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


def verify(entry: Mapping[str, Any], path: Path | None = None, *, root: Path | None = None) -> None:
    resolved = path or local_path(entry, root=root)
    expected_size = entry.get("size_bytes")
    if isinstance(expected_size, int) and resolved.stat().st_size != expected_size:
        raise RuntimeError(
            f"size mismatch for {entry['name']}: expected {expected_size} bytes, got {resolved.stat().st_size}"
        )
    expected_sha = entry.get("sha256")
    if entry.get("gated") is True:
        return
    if isinstance(expected_sha, str) and expected_sha:
        actual_sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_sha.lower() != expected_sha.lower():
            raise RuntimeError(f"sha256 mismatch for {entry['name']}: expected {expected_sha}, got {actual_sha}")


def download(entry: Mapping[str, Any], *, force: bool = False, client: Any = None, root: Path | None = None) -> Path:
    path = local_path(entry, root=root)
    name = str(entry["name"])
    if is_present(entry, root=root) and not force:
        verify(entry, path, root=root)
        print(f"skipped {name}")
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
    verify(entry, path, root=root)
    return path


def download_many(entries: list[dict], *, force: bool = False) -> list[Path]:
    paths: list[Path] = []
    failures = 0
    for entry in entries:
        name = str(entry.get("name", "<unknown>"))
        was_present = is_present(entry) and not force
        try:
            path = download(entry, force=force)
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
