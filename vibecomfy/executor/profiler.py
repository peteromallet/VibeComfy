from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

_REDACTED = "<REDACTED>"
_SENSITIVE_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "auth_header",
        "bearer_token",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
    }
)


def _is_sensitive_field(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_FIELD_NAMES or normalized.endswith(
        ("_api_key", "_token", "_secret", "_password")
    )


def redact_secrets(value: Any, secrets: Iterable[str] = ()) -> Any:
    """Redact exact secret values recursively without changing the envelope."""
    secret_values = tuple(
        sorted(
            {secret for secret in secrets if isinstance(secret, str) and secret},
            key=len,
            reverse=True,
        )
    )

    def redact(item: Any, key_hint: str | None = None) -> Any:
        if key_hint and _is_sensitive_field(key_hint):
            return _REDACTED
        if isinstance(item, dict):
            return {
                str(key): redact(child, str(key))
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [redact(child) for child in item]
        if isinstance(item, tuple):
            return tuple(redact(child) for child in item)
        if isinstance(item, str):
            for secret in secret_values:
                item = item.replace(secret, _REDACTED)
        return item

    return redact(value)

_PROFILER_LOG_PATH = Path(
    os.getenv("VIBECOMFY_PROFILER_LOG_PATH", "/tmp/vibecomfy_executor_profiler.log")
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_profile_id(prefix: str = "prof") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def short_text(value: Any, *, limit: int = 160) -> str | None:
    if not isinstance(value, str):
        return None
    compact = " ".join(value.strip().split())
    if not compact:
        return None
    if len(compact) <= limit:
        return compact
    return f"{compact[: max(0, limit - 3)]}..."


def _normalize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, dict):
            normalized[key] = {
                str(child_key): child_value
                for child_key, child_value in value.items()
                if child_value is not None
            }
        else:
            normalized[key] = value
    return normalized


def _json_default(value: Any) -> Any:
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    return repr(value)


def profiler_log(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    secret_values: Iterable[str] = (),
    **fields: Any,
) -> None:
    payload = {
        "event": event,
        "ts": utc_now_iso(),
        **redact_secrets(_normalize_fields(fields), secret_values),
    }
    line = json.dumps(payload, sort_keys=True, default=_json_default)
    logger.log(level, "vibecomfy.profiler %s", line)
    try:
        _PROFILER_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _PROFILER_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
    except OSError:
        pass


@dataclass
class ProfilerSpan:
    logger: logging.Logger
    event: str
    level: int = logging.INFO
    secret_values: tuple[str, ...] = ()
    base_fields: dict[str, Any] = field(default_factory=dict)
    result_fields: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(init=False)
    _start_monotonic: float = field(init=False)

    def __post_init__(self) -> None:
        self.base_fields = _normalize_fields(self.base_fields)
        self.started_at = utc_now_iso()
        self._start_monotonic = time.monotonic()
        profiler_log(
            self.logger,
            f"{self.event}.start",
            level=self.level,
            secret_values=self.secret_values,
            started_at=self.started_at,
            **self.base_fields,
        )

    def update(self, **fields: Any) -> None:
        self.result_fields.update(_normalize_fields(fields))

    def finish(self, *, status: str = "ok", **fields: Any) -> None:
        self.update(**fields)
        profiler_log(
            self.logger,
            f"{self.event}.end",
            level=self.level,
            secret_values=self.secret_values,
            status=status,
            started_at=self.started_at,
            ended_at=utc_now_iso(),
            elapsed_ms=max(0, int((time.monotonic() - self._start_monotonic) * 1000)),
            **self.base_fields,
            **self.result_fields,
        )

    def __enter__(self) -> "ProfilerSpan":
        return self

    def __exit__(self, exc_type, exc, _tb) -> bool:
        if exc is not None:
            self.finish(
                status="error",
                error_type=exc_type.__name__ if exc_type is not None else type(exc).__name__,
                error=str(exc),
            )
            return False
        self.finish()
        return False


def profiler_span(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    secret_values: Iterable[str] = (),
    **fields: Any,
) -> ProfilerSpan:
    return ProfilerSpan(
        logger=logger,
        event=event,
        level=level,
        secret_values=tuple(secret_values),
        base_fields=fields,
    )
