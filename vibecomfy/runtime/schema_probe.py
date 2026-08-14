"""Live runtime schema probe with an independently verifiable receipt.

The probe reaches a *live* ComfyUI ``/object_info`` — an HTTP server when
``server_url`` is given, or the runtime-managed server spawned by the existing
``vibecomfy.runtime.server.comfy_server`` machinery when it is not — and
returns a :class:`RuntimeProbeReceipt`.

The receipt is deliberately **not** a strong-tier claim string: it carries the
endpoint that was queried, the runtime fingerprint, and the canonical
object_info payload checksum, so any consumer (e.g. the queue gate) can
independently recompute the digest from the same endpoint and confirm the
receipt was not fabricated. ``verify_probe_receipt`` / ``verify_probe_receipt_live``
are the recomputation entry points; ``strong_tier_eligible`` is *computed* by
them, never asserted by the probe.

Failure statuses are typed: ``timeout`` (the endpoint accepted the connection
but never answered), ``unavailable`` (connection refused / HTTP error /
malformed payload), ``stale`` (live fetch failed, but a fingerprint-valid cache
for this runtime exists), ``mismatched_runtime`` (a cache exists but belongs to
a different runtime, so it is not evidence for this one).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping

import httpx

from vibecomfy.runtime.server import comfy_server
from vibecomfy.schema.cache import (
    CACHE_METADATA_KEY,
    load_object_info_cache,
    object_info_cache_path,
    object_info_payload_checksum,
    runtime_fingerprint,
    validate_object_info_cache,
)

SCHEMA_DIGEST_ALGORITHM = "sha256"
SCHEMA_DIGEST_CANONICALIZATION = "object_info_payload_checksum"
PROBE_RECEIPT_CONTRACT_VERSION = "1"

_READINESS_READY = "ready"
_READINESS_NOT_READY = "not_ready"
_READINESS_VALUES = frozenset({_READINESS_READY, _READINESS_NOT_READY})

_HEX_DIGITS = frozenset("0123456789abcdef")


class ProbeStatus(StrEnum):
    OK = "ok"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    MISMATCHED_RUNTIME = "mismatched_runtime"


PROBE_STATUSES = frozenset(status.value for status in ProbeStatus)

_LIVE_STATUSES = frozenset({ProbeStatus.OK})
_FAILURE_STATUSES = frozenset(
    {ProbeStatus.TIMEOUT, ProbeStatus.UNAVAILABLE, ProbeStatus.STALE, ProbeStatus.MISMATCHED_RUNTIME}
)


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"`{field_name}` must be a non-empty string.")
    if value != value.strip():
        raise ValueError(f"`{field_name}` must not have leading or trailing whitespace.")
    return value


def _canonical_timestamp(value: Any) -> str:
    """Normalize an ISO-8601 timestamp to UTC seconds with a ``Z`` suffix.

    Matches the wire format of the F01 stage contracts so a receipt's
    ``produced_at`` can be dropped into a ``StagePackage`` unchanged.
    """
    text = _required_text(value, "produced_at")
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("`produced_at` must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("`produced_at` must include a timezone offset.")
    utc = parsed.astimezone(timezone.utc)
    rendered = utc.isoformat(timespec="seconds")
    return rendered.replace("+00:00", "Z")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _check_keys(
    payload: Mapping[str, Any],
    *,
    required: frozenset[str],
    optional: frozenset[str] = frozenset(),
    contract: str,
) -> None:
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"{contract} is missing required field(s): {', '.join(missing)}.")
    extra = sorted(payload.keys() - required - optional)
    if extra:
        raise ValueError(f"{contract} contains unknown field(s): {', '.join(extra)}.")


def _validate_schema_digest(value: Any, field_name: str = "schema_digest") -> str:
    text = _required_text(value, field_name)
    if len(text) != 64 or any(char not in _HEX_DIGITS for char in text):
        raise ValueError(f"`{field_name}` must be a 64-char lowercase sha256 hex digest.")
    return text


def _normalize_endpoint(value: str) -> str:
    return value.rstrip("/")


def _class_entries(object_info: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(name): info
        for name, info in object_info.items()
        if name != CACHE_METADATA_KEY and isinstance(info, Mapping)
    }


def _input_count(info: Mapping[str, Any]) -> int:
    groups = info.get("input") if isinstance(info.get("input"), Mapping) else info.get("inputs", {})
    if not isinstance(groups, Mapping):
        return 0
    return sum(1 for group in groups.values() if isinstance(group, Mapping) for _ in group)


def _output_count(info: Mapping[str, Any]) -> int:
    # Live /object_info uses `output` (list of per-slot type lists); the
    # normalized cache form uses `outputs` (list of {type,name} dicts).
    normalized = info.get("outputs")
    if isinstance(normalized, (list, tuple)):
        return len(normalized)
    raw = info.get("output")
    return len(raw) if isinstance(raw, (list, tuple)) else 0


def _class_results(
    object_info: Mapping[str, Any],
    class_types: Iterable[str] | None,
) -> tuple["ClassProbeResult", ...]:
    classes = _class_entries(object_info)
    if class_types is None:
        names = sorted(classes)
    else:
        names = sorted({_required_text(name, "class_types[]") for name in class_types})
    results: list[ClassProbeResult] = []
    for name in names:
        info = classes.get(name)
        if info is None:
            results.append(ClassProbeResult(class_type=name, present=False))
        else:
            results.append(
                ClassProbeResult(
                    class_type=name,
                    present=True,
                    input_count=_input_count(info),
                    output_count=_output_count(info),
                )
            )
    return tuple(results)


@dataclass(frozen=True)
class ClassProbeResult:
    """Per-class presence inside the probed runtime's object_info."""

    class_type: str
    present: bool
    input_count: int = 0
    output_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "class_type", _required_text(self.class_type, "class_type"))
        if not isinstance(self.present, bool):
            raise ValueError("`present` must be a boolean.")
        for field_name, value in (("input_count", self.input_count), ("output_count", self.output_count)):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"`{field_name}` must be a non-negative integer.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "class_type": self.class_type,
            "present": self.present,
            "input_count": self.input_count,
            "output_count": self.output_count,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ClassProbeResult":
        if not isinstance(payload, Mapping):
            raise ValueError("ClassProbeResult must be an object.")
        _check_keys(
            payload,
            required=frozenset({"class_type", "present", "input_count", "output_count"}),
            contract="ClassProbeResult",
        )
        return cls(
            class_type=payload["class_type"],
            present=payload["present"],
            input_count=payload["input_count"],
            output_count=payload["output_count"],
        )


@dataclass(frozen=True)
class RuntimeProbeReceipt:
    """Verifiable evidence that a live runtime was probed for its schema.

    ``status`` is typed (:class:`ProbeStatus`). ``live`` is ``True`` only when
    a live ``/object_info`` was actually reached. ``schema_digest`` is the
    canonical object_info payload checksum (sha256 over the deterministic JSON
    wire form), so it is stable for identical object_info, changes when the
    schema changes, and can be recomputed by any consumer that re-fetches the
    endpoint.
    """

    probe_id: str
    produced_at: str
    status: ProbeStatus | str
    live: bool
    runtime_identity: str
    runtime_label: str
    endpoint_identity: str
    schema_digest: str | None
    class_count: int
    readiness: str
    class_results: tuple[ClassProbeResult, ...]
    failure_detail: str | None = None
    digest_algorithm: str = SCHEMA_DIGEST_ALGORITHM
    digest_canonicalization: str = SCHEMA_DIGEST_CANONICALIZATION
    contract_version: str = PROBE_RECEIPT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "probe_id", _required_text(self.probe_id, "probe_id"))
        object.__setattr__(self, "produced_at", _canonical_timestamp(self.produced_at))
        object.__setattr__(self, "status", ProbeStatus(self.status))
        if not isinstance(self.live, bool):
            raise ValueError("`live` must be a boolean.")
        object.__setattr__(self, "runtime_identity", _required_text(self.runtime_identity, "runtime_identity"))
        object.__setattr__(self, "runtime_label", _required_text(self.runtime_label, "runtime_label"))
        object.__setattr__(self, "endpoint_identity", _normalize_endpoint(
            _required_text(self.endpoint_identity, "endpoint_identity")
        ))
        if self.schema_digest is not None:
            object.__setattr__(self, "schema_digest", _validate_schema_digest(self.schema_digest))
        if not isinstance(self.class_count, int) or self.class_count < 0:
            raise ValueError("`class_count` must be a non-negative integer.")
        object.__setattr__(self, "digest_algorithm", _required_text(self.digest_algorithm, "digest_algorithm"))
        object.__setattr__(
            self,
            "digest_canonicalization",
            _required_text(self.digest_canonicalization, "digest_canonicalization"),
        )
        object.__setattr__(self, "contract_version", _required_text(self.contract_version, "contract_version"))
        if self.readiness not in _READINESS_VALUES:
            raise ValueError(f"`readiness` must be one of: {', '.join(sorted(_READINESS_VALUES))}.")
        if not isinstance(self.class_results, (list, tuple)):
            raise ValueError("`class_results` must be a list of ClassProbeResult.")
        normalized: list[ClassProbeResult] = []
        seen: set[str] = set()
        for item in self.class_results:
            result = item if isinstance(item, ClassProbeResult) else ClassProbeResult.from_dict(item)
            if result.class_type in seen:
                raise ValueError(f"`class_results` contains duplicate class_type {result.class_type!r}.")
            seen.add(result.class_type)
            normalized.append(result)
        if normalized != sorted(normalized, key=lambda result: result.class_type):
            raise ValueError("`class_results` must be sorted by class_type.")
        object.__setattr__(self, "class_results", tuple(normalized))
        if self.failure_detail is not None:
            object.__setattr__(self, "failure_detail", _required_text(self.failure_detail, "failure_detail"))

        status = self.status
        if status in _LIVE_STATUSES:
            if not self.live:
                raise ValueError("A receipt with status `ok` must have live=True.")
            if self.schema_digest is None:
                raise ValueError("A live receipt must carry a schema_digest.")
        elif status in _FAILURE_STATUSES:
            if self.live:
                raise ValueError(f"A receipt with status `{status.value}` must have live=False.")
            if status is ProbeStatus.STALE and self.schema_digest is None:
                raise ValueError("A stale receipt must carry the cached schema_digest.")
            if status is ProbeStatus.MISMATCHED_RUNTIME and self.schema_digest is not None:
                raise ValueError("A mismatched-runtime receipt must not carry a schema_digest for this runtime.")
        else:  # pragma: no cover - StrEnum construction already rejects unknown values
            raise ValueError(f"Unknown probe status: {status!r}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_id": self.probe_id,
            "produced_at": self.produced_at,
            "status": self.status.value,
            "live": self.live,
            "runtime_identity": self.runtime_identity,
            "runtime_label": self.runtime_label,
            "endpoint_identity": self.endpoint_identity,
            "schema_digest": self.schema_digest,
            "digest_algorithm": self.digest_algorithm,
            "digest_canonicalization": self.digest_canonicalization,
            "class_count": self.class_count,
            "readiness": self.readiness,
            "class_results": [result.to_dict() for result in self.class_results],
            "failure_detail": self.failure_detail,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RuntimeProbeReceipt":
        if not isinstance(payload, Mapping):
            raise ValueError("RuntimeProbeReceipt must be an object.")
        _check_keys(
            payload,
            required=frozenset({
                "probe_id",
                "produced_at",
                "status",
                "live",
                "runtime_identity",
                "runtime_label",
                "endpoint_identity",
                "schema_digest",
                "digest_algorithm",
                "digest_canonicalization",
                "class_count",
                "readiness",
                "class_results",
                "failure_detail",
                "contract_version",
            }),
            contract="RuntimeProbeReceipt",
        )
        return cls(
            probe_id=payload["probe_id"],
            produced_at=payload["produced_at"],
            status=payload["status"],
            live=payload["live"],
            runtime_identity=payload["runtime_identity"],
            runtime_label=payload["runtime_label"],
            endpoint_identity=payload["endpoint_identity"],
            schema_digest=payload["schema_digest"],
            digest_algorithm=payload["digest_algorithm"],
            digest_canonicalization=payload["digest_canonicalization"],
            class_count=payload["class_count"],
            readiness=payload["readiness"],
            class_results=payload["class_results"],
            failure_detail=payload["failure_detail"],
            contract_version=payload["contract_version"],
        )


async def _probe_system_stats(endpoint: str, timeout: float) -> bool:
    """Return True when GET /system_stats answers 200 (runtime is ready)."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{endpoint}/system_stats")
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _fetch_live_object_info(
    endpoint: str,
    timeout: float,
) -> tuple[dict[str, Any] | None, ProbeStatus | None, str | None]:
    """GET /object_info with a caller-configurable timeout.

    Returns ``(payload, None, None)`` on success, or ``(None, status, detail)``
    with a typed failure status. Mirrors ``ComfyClient.object_info`` but lets
    the probe bound the request itself so a hanging endpoint classifies as
    ``timeout`` instead of blocking for the client default.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{endpoint}/object_info")
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException as exc:
        return None, ProbeStatus.TIMEOUT, f"GET {endpoint}/object_info timed out after {timeout}s: {exc}".strip()
    except httpx.HTTPError as exc:
        return None, ProbeStatus.UNAVAILABLE, f"GET {endpoint}/object_info failed: {exc}".strip()
    except (json.JSONDecodeError, ValueError) as exc:
        return None, ProbeStatus.UNAVAILABLE, f"GET {endpoint}/object_info returned invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, ProbeStatus.UNAVAILABLE, "/object_info returned a non-object payload."
    return payload, None, None


def _receipt_from_object_info(
    *,
    probe_id: str,
    produced_at: str,
    object_info: Mapping[str, Any],
    runtime_id: str,
    runtime_label: str,
    endpoint: str,
    readiness: str,
    class_types: Iterable[str] | None,
) -> RuntimeProbeReceipt:
    classes = _class_entries(object_info)
    return RuntimeProbeReceipt(
        probe_id=probe_id,
        produced_at=produced_at,
        status=ProbeStatus.OK,
        live=True,
        runtime_identity=runtime_id,
        runtime_label=runtime_label,
        endpoint_identity=endpoint,
        schema_digest=object_info_payload_checksum(object_info),
        class_count=len(classes),
        readiness=readiness,
        class_results=_class_results(object_info, class_types),
    )


def _receipt_from_cache(
    *,
    probe_id: str,
    produced_at: str,
    cache_path: Path,
    runtime_id: str,
    runtime_label: str,
    endpoint: str,
    readiness: str,
    class_types: Iterable[str] | None,
    failure_detail: str,
) -> RuntimeProbeReceipt | None:
    """Build a stale/mismatched receipt from an existing object_info cache.

    Returns ``None`` when no cache exists (caller keeps the pure failure
    status). ``stale`` requires the cache to pass strict validation against
    this runtime's fingerprint; anything else classifies as
    ``mismatched_runtime`` and carries no digest.
    """
    cached = load_object_info_cache(cache_path)
    if cached is None:
        return None
    result = validate_object_info_cache(
        cached,
        expected={"runtime_fingerprint": runtime_id},
        policy="strict",
        cache_path=cache_path,
    )
    if result.ok:
        classes = _class_entries(cached)
        return RuntimeProbeReceipt(
            probe_id=probe_id,
            produced_at=produced_at,
            status=ProbeStatus.STALE,
            live=False,
            runtime_identity=runtime_id,
            runtime_label=runtime_label,
            endpoint_identity=endpoint,
            schema_digest=object_info_payload_checksum(cached),
            class_count=len(classes),
            readiness=readiness,
            class_results=_class_results(cached, class_types),
            failure_detail=failure_detail,
        )
    return RuntimeProbeReceipt(
        probe_id=probe_id,
        produced_at=produced_at,
        status=ProbeStatus.MISMATCHED_RUNTIME,
        live=False,
        runtime_identity=runtime_id,
        runtime_label=runtime_label,
        endpoint_identity=endpoint,
        schema_digest=None,
        class_count=0,
        readiness=readiness,
        class_results=(),
        failure_detail=(
            f"cached object_info at {cache_path} is not evidence for this runtime: {result.reason}"
        ),
    )


async def live_runtime_schema_probe(
    *,
    server_url: str | None = None,
    class_types: Iterable[str] | None = None,
    timeout: float = 30.0,
    cache_dir: str | Path = "out/cache",
    allow_cache_fallback: bool = True,
    log_path: str | Path | None = None,
) -> RuntimeProbeReceipt:
    """Probe a live ComfyUI runtime and return a verifiable receipt.

    ``server_url`` selects the endpoint: an HTTP server when given, or the
    runtime-managed server spawned through the existing session machinery
    (``comfy_server``) when omitted. ``class_types`` narrows the per-class
    results to the classes a consumer cares about (default: every class in
    object_info, sorted for determinism).

    Failure statuses are typed — ``timeout``, ``unavailable``, ``stale``,
    ``mismatched_runtime`` — and a receipt is only ``live`` (and therefore
    eligible as strong-tier evidence) when a real ``/object_info`` was reached.
    """
    if timeout <= 0:
        raise ValueError("`timeout` must be positive.")
    produced_at = _now_iso()
    probe_id = f"probe-{uuid.uuid4().hex}"
    runtime_id = runtime_fingerprint(server_url)
    runtime_label = f"server:{_normalize_endpoint(server_url)}" if server_url else "embedded"

    async with comfy_server(server_url=server_url, log_path=log_path) as active_url:
        endpoint = _normalize_endpoint(active_url)
        object_info, fetch_status, fetch_detail = await _fetch_live_object_info(endpoint, timeout)
        if fetch_status is None:
            readiness = _READINESS_READY
            return _receipt_from_object_info(
                probe_id=probe_id,
                produced_at=produced_at,
                object_info=object_info,
                runtime_id=runtime_id,
                runtime_label=runtime_label,
                endpoint=endpoint,
                readiness=readiness,
                class_types=class_types,
            )
        readiness = _READINESS_READY if await _probe_system_stats(endpoint, timeout) else _READINESS_NOT_READY
        failure_detail = fetch_detail or f"live /object_info fetch failed with status {fetch_status.value}."

        if allow_cache_fallback:
            cache_path = object_info_cache_path(server_url=server_url, cache_dir=cache_dir)
            fallback = _receipt_from_cache(
                probe_id=probe_id,
                produced_at=produced_at,
                cache_path=cache_path,
                runtime_id=runtime_id,
                runtime_label=runtime_label,
                endpoint=endpoint,
                readiness=readiness,
                class_types=class_types,
                failure_detail=failure_detail,
            )
            if fallback is not None:
                return fallback

        return RuntimeProbeReceipt(
            probe_id=probe_id,
            produced_at=produced_at,
            status=fetch_status,
            live=False,
            runtime_identity=runtime_id,
            runtime_label=runtime_label,
            endpoint_identity=endpoint,
            schema_digest=None,
            class_count=0,
            readiness=readiness,
            class_results=(),
            failure_detail=failure_detail,
        )


def live_runtime_schema_probe_sync(
    *,
    server_url: str | None = None,
    class_types: Iterable[str] | None = None,
    timeout: float = 30.0,
    cache_dir: str | Path = "out/cache",
    allow_cache_fallback: bool = True,
    log_path: str | Path | None = None,
) -> RuntimeProbeReceipt:
    """Synchronous wrapper around :func:`live_runtime_schema_probe`."""
    return asyncio.run(
        live_runtime_schema_probe(
            server_url=server_url,
            class_types=class_types,
            timeout=timeout,
            cache_dir=cache_dir,
            allow_cache_fallback=allow_cache_fallback,
            log_path=log_path,
        )
    )


def verify_probe_receipt(
    receipt: RuntimeProbeReceipt | Mapping[str, Any],
    *,
    object_info: Mapping[str, Any] | None = None,
    endpoint_identity: str | None = None,
    system_stats_ok: bool | None = None,
    now: datetime | None = None,
    max_age_seconds: float | None = None,
) -> dict[str, Any]:
    """Independently recompute a receipt's claims from observed facts.

    Pure recomputation — no I/O. ``object_info`` and ``endpoint_identity`` are
    the independently observed payload and the endpoint it was fetched from;
    the digest and runtime identity are recomputed from them and compared
    against the receipt. ``verified`` is True only when every applicable check
    passes; ``strong_tier_eligible`` additionally requires a live, fresh,
    status-``ok`` receipt — it is never accepted from the receipt alone.
    """
    receipt = receipt if isinstance(receipt, RuntimeProbeReceipt) else RuntimeProbeReceipt.from_dict(receipt)
    checks: dict[str, Any] = {"digest": None, "endpoint": None, "freshness": None, "readiness": None}
    reasons: list[str] = []

    if receipt.status is not ProbeStatus.OK:
        reasons.append(f"receipt_status_{receipt.status.value}")
    if not receipt.live:
        reasons.append("receipt_not_live")

    if object_info is not None:
        recomputed = object_info_payload_checksum(object_info)
        checks["digest"] = recomputed == receipt.schema_digest
        if not checks["digest"]:
            reasons.append("schema_digest_mismatch")
    else:
        reasons.append("digest_not_recomputed")

    if endpoint_identity is not None:
        checks["endpoint"] = _normalize_endpoint(endpoint_identity) == receipt.endpoint_identity
        if not checks["endpoint"]:
            reasons.append("endpoint_identity_mismatch")
    elif receipt.runtime_label.startswith("server:"):
        reasons.append("endpoint_not_recomputed")

    if system_stats_ok is not None:
        checks["readiness"] = bool(system_stats_ok)
        if not system_stats_ok:
            reasons.append("runtime_not_ready")

    if max_age_seconds is not None:
        try:
            produced = datetime.fromisoformat(receipt.produced_at.replace("Z", "+00:00"))
        except ValueError:
            reasons.append("produced_at_unparseable")
            checks["freshness"] = False
        else:
            age = (now or datetime.now(timezone.utc)) - produced
            checks["freshness"] = age.total_seconds() <= max_age_seconds
            if not checks["freshness"]:
                reasons.append("receipt_expired")

    verified = (
        not reasons
        and checks["digest"] is True
        and checks["endpoint"] is not False
        and checks["readiness"] is not False
    )
    return {
        "verified": verified,
        "strong_tier_eligible": (
            verified
            and receipt.live
            and receipt.status is ProbeStatus.OK
            and checks["freshness"] is not False
        ),
        "checks": checks,
        "reasons": reasons,
        "status": receipt.status.value,
    }


async def verify_probe_receipt_live(
    receipt: RuntimeProbeReceipt | Mapping[str, Any],
    *,
    server_url: str | None = None,
    timeout: float = 10.0,
    max_age_seconds: float | None = None,
) -> dict[str, Any]:
    """Re-fetch the receipt's endpoint and independently verify the receipt.

    The re-fetch targets ``server_url`` when given, else the receipt's own
    ``endpoint_identity`` — a receipt claiming endpoint X cannot be verified
    against a different endpoint. Returns the same verdict shape as
    :func:`verify_probe_receipt`.
    """
    receipt = receipt if isinstance(receipt, RuntimeProbeReceipt) else RuntimeProbeReceipt.from_dict(receipt)
    endpoint = _normalize_endpoint(server_url or receipt.endpoint_identity)
    if not endpoint:
        raise ValueError("no endpoint to verify against")
    object_info, fetch_status, fetch_detail = await _fetch_live_object_info(endpoint, timeout)
    if fetch_status is not None:
        return {
            "verified": False,
            "strong_tier_eligible": False,
            "checks": {},
            "reasons": [f"refetch_{fetch_status.value}"],
            "status": fetch_status.value,
            "failure_detail": fetch_detail,
        }
    readiness_ok = await _probe_system_stats(endpoint, timeout)
    return verify_probe_receipt(
        receipt,
        object_info=object_info,
        endpoint_identity=endpoint,
        system_stats_ok=readiness_ok,
        now=datetime.now(timezone.utc),
        max_age_seconds=max_age_seconds,
    )


def verify_probe_receipt_live_sync(
    receipt: RuntimeProbeReceipt | Mapping[str, Any],
    *,
    server_url: str | None = None,
    timeout: float = 10.0,
    max_age_seconds: float | None = None,
) -> dict[str, Any]:
    """Synchronous wrapper around :func:`verify_probe_receipt_live`."""
    return asyncio.run(
        verify_probe_receipt_live(
            receipt,
            server_url=server_url,
            timeout=timeout,
            max_age_seconds=max_age_seconds,
        )
    )


__all__ = [
    "ClassProbeResult",
    "PROBE_RECEIPT_CONTRACT_VERSION",
    "PROBE_STATUSES",
    "ProbeStatus",
    "RuntimeProbeReceipt",
    "SCHEMA_DIGEST_ALGORITHM",
    "SCHEMA_DIGEST_CANONICALIZATION",
    "live_runtime_schema_probe",
    "live_runtime_schema_probe_sync",
    "verify_probe_receipt",
    "verify_probe_receipt_live",
    "verify_probe_receipt_live_sync",
]
