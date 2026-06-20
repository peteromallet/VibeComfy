from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from vibecomfy.comfy_command import comfyui_command, has_comfyui_runtime


OBJECT_INFO_CACHE_FORMAT_VERSION = 2
CACHE_METADATA_KEY = "_cache_metadata"

CacheValidationPolicy = Literal["strict", "allow_legacy"]
CacheValidationSeverity = Literal["ok", "warning", "error"]


@dataclass(frozen=True)
class CacheValidationResult:
    ok: bool
    reason: str | None
    expected: dict[str, Any]
    actual: dict[str, Any]
    cache_path: str | None = None
    severity: CacheValidationSeverity = "ok"


def runtime_fingerprint(server_url: str | None = None) -> str:
    if server_url:
        source = f"server:{server_url.rstrip('/')}"
    elif has_comfyui_runtime():
        command = comfyui_command()
        source = "embedded:" + " ".join(command)
        if len(command) == 1:
            path = Path(command[0])
            try:
                stat = path.stat()
                source = f"embedded:{path}:{stat.st_mtime_ns}:{stat.st_size}"
            except OSError:
                source = f"embedded:{path}"
    else:
        source = f"embedded:missing:{sys.executable}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def object_info_cache_path(
    *,
    server_url: str | None = None,
    cache_dir: str | Path = "out/cache",
) -> Path:
    return Path(cache_dir) / f"object_info.{runtime_fingerprint(server_url)}.json"


def object_info_cache_candidates(cache_dir: str | Path = "out/cache") -> list[Path]:
    root = Path(cache_dir)
    if not root.is_dir():
        return []
    paths = [path for path in root.glob("object_info*.json") if path.is_file()]
    return sorted(paths, key=lambda path: path.stat().st_mtime, reverse=True)


def latest_object_info_cache_path(cache_dir: str | Path = "out/cache") -> Path | None:
    candidates = object_info_cache_candidates(cache_dir)
    return candidates[0] if candidates else None


def load_object_info_cache(path: str | Path) -> dict[str, Any] | None:
    cache_path = Path(path)
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def object_info_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key != CACHE_METADATA_KEY}


def object_info_payload_checksum(data: dict[str, Any]) -> str:
    payload = object_info_payload(data)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_object_info_cache_metadata(
    data: dict[str, Any],
    *,
    runtime_fingerprint: str | None = None,
    server_url: str | None = None,
    authored_pack_fingerprint: str | None = None,
    authored_index_fingerprint: str | None = None,
    source: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "format_version": OBJECT_INFO_CACHE_FORMAT_VERSION,
        "checksum": object_info_payload_checksum(data),
    }
    if runtime_fingerprint:
        metadata["runtime_fingerprint"] = runtime_fingerprint
    if server_url:
        metadata["server_url"] = _normalize_server_url(server_url)
    if authored_pack_fingerprint:
        metadata["authored_pack_fingerprint"] = authored_pack_fingerprint
    if authored_index_fingerprint:
        metadata["authored_index_fingerprint"] = authored_index_fingerprint
    if source:
        metadata["source"] = source
    if extra:
        metadata.update(
            {
                key: value
                for key, value in extra.items()
                if key
                not in {
                    "checksum",
                    "format_version",
                    "runtime_fingerprint",
                    "server_url",
                    "authored_pack_fingerprint",
                    "authored_index_fingerprint",
                }
            }
        )
        metadata["format_version"] = OBJECT_INFO_CACHE_FORMAT_VERSION
        metadata["checksum"] = object_info_payload_checksum(data)
    return metadata


def validate_object_info_cache(
    data: Any,
    *,
    expected: dict[str, Any] | None = None,
    policy: CacheValidationPolicy = "strict",
    cache_path: str | Path | None = None,
) -> CacheValidationResult:
    expected_values = _normalize_expected(expected or {})
    cache_path_text = str(cache_path) if cache_path is not None else None
    if not isinstance(data, dict):
        return CacheValidationResult(
            ok=False,
            reason="cache_payload_not_object",
            expected=expected_values,
            actual={"payload_type": type(data).__name__},
            cache_path=cache_path_text,
            severity="error",
        )

    metadata = data.get(CACHE_METADATA_KEY)
    if not isinstance(metadata, dict):
        severity: CacheValidationSeverity = "warning" if policy == "allow_legacy" else "error"
        return CacheValidationResult(
            ok=policy == "allow_legacy",
            reason="cache_metadata_missing",
            expected=expected_values,
            actual={},
            cache_path=cache_path_text,
            severity=severity,
        )

    actual = _normalize_actual(metadata)
    version = actual.get("format_version")
    if version is None:
        return _invalid("cache_format_version_missing", expected_values, actual, cache_path_text)
    if version != OBJECT_INFO_CACHE_FORMAT_VERSION:
        return _invalid("cache_format_version_mismatch", expected_values, actual, cache_path_text)

    checksum = actual.get("checksum")
    if not isinstance(checksum, str) or not checksum:
        return _invalid("cache_checksum_missing", expected_values, actual, cache_path_text)
    computed_checksum = object_info_payload_checksum(data)
    if checksum != computed_checksum:
        actual = {**actual, "computed_checksum": computed_checksum}
        return _invalid("cache_checksum_mismatch", expected_values, actual, cache_path_text)

    for key in ("runtime_fingerprint", "server_url", "authored_pack_fingerprint", "authored_index_fingerprint"):
        expected_value = expected_values.get(key)
        if expected_value is None:
            continue
        actual_value = actual.get(key)
        if actual_value != expected_value:
            return _invalid(f"cache_{key}_mismatch", expected_values, actual, cache_path_text)

    return CacheValidationResult(
        ok=True,
        reason=None,
        expected=expected_values,
        actual=actual,
        cache_path=cache_path_text,
        severity="ok",
    )


def write_object_info_cache(
    path: str | Path,
    data: dict[str, Any],
    *,
    runtime_fingerprint: str | None = None,
    server_url: str | None = None,
    authored_pack_fingerprint: str | None = None,
    authored_index_fingerprint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = object_info_payload(dict(data))
    runtime_identity = runtime_fingerprint or _runtime_fingerprint_from_path(cache_path)
    payload[CACHE_METADATA_KEY] = build_object_info_cache_metadata(
        payload,
        runtime_fingerprint=runtime_identity,
        server_url=server_url,
        authored_pack_fingerprint=authored_pack_fingerprint,
        authored_index_fingerprint=authored_index_fingerprint,
        extra=metadata,
    )
    encoded = json.dumps(payload, indent=2, sort_keys=True)

    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=cache_path.parent,
            prefix=f".{cache_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
            tmp.write(encoded)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, cache_path)
        _fsync_directory(cache_path.parent)
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                Path(tmp_name).unlink()
            except OSError:
                pass


def _normalize_server_url(server_url: Any) -> Any:
    return server_url.rstrip("/") if isinstance(server_url, str) else server_url


def _normalize_expected(expected: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(expected)
    if "server_url" in normalized:
        normalized["server_url"] = _normalize_server_url(normalized["server_url"])
    return {key: value for key, value in normalized.items() if value is not None}


def _normalize_actual(metadata: dict[str, Any]) -> dict[str, Any]:
    actual = dict(metadata)
    if "server_url" in actual:
        actual["server_url"] = _normalize_server_url(actual["server_url"])
    return actual


def _runtime_fingerprint_from_path(path: Path) -> str | None:
    name = path.name
    if not name.startswith("object_info.") or not name.endswith(".json"):
        return None
    middle = name[len("object_info.") : -len(".json")]
    return middle or None


def _fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def _invalid(
    reason: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    cache_path: str | None,
) -> CacheValidationResult:
    return CacheValidationResult(
        ok=False,
        reason=reason,
        expected=expected,
        actual=actual,
        cache_path=cache_path,
        severity="error",
    )
