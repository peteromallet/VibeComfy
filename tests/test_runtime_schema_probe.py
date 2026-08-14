"""Focused tests for the live runtime schema probe (A03).

Covers the acceptance contract:

- digest stability: identical object_info yields an identical receipt digest;
  a schema change flips it.
- typed failure states: ``timeout`` / ``unavailable`` / ``stale`` /
  ``mismatched_runtime`` are produced by the right endpoint conditions.
- receipt structure sufficient for independent verification: the queue gate
  (later H02) can recompute the digest and runtime identity from a live
  re-fetch and confirm the receipt was not fabricated — no strong-tier string
  is accepted from the receipt alone.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import pytest

from vibecomfy.runtime.schema_probe import (
    ProbeStatus,
    RuntimeProbeReceipt,
    live_runtime_schema_probe,
    live_runtime_schema_probe_sync,
    verify_probe_receipt,
    verify_probe_receipt_live,
    verify_probe_receipt_live_sync,
)
from vibecomfy.schema.cache import (
    object_info_cache_path,
    object_info_payload_checksum,
    runtime_fingerprint,
    write_object_info_cache,
)

# ---------------------------------------------------------------------------
# Stub ComfyUI HTTP server (a real live endpoint for /system_stats + /object_info)
# ---------------------------------------------------------------------------


class _StubComfyHandler(BaseHTTPRequestHandler):
    object_info: dict[str, Any] = {}
    system_stats: dict[str, Any] = {"system": {"comfyui_version": "stub"}}
    object_info_delay: float = 0.0

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler hook
        path = self.path.rstrip("/")
        if path == "/system_stats":
            self._send_json(200, self.system_stats)
        elif path == "/object_info":
            if self.object_info_delay:
                time.sleep(self.object_info_delay)
            self._send_json(200, self.object_info)
        else:
            self._send_json(404, {"error": "not found"})

    def _send_json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # silence request logging
        pass


@contextmanager
def _stub_runtime(
    object_info: dict[str, Any],
    *,
    delay: float = 0.0,
    system_stats: dict[str, Any] | None = None,
) -> Iterator[str]:
    handler = _StubComfyHandler
    handler.object_info = object_info
    handler.object_info_delay = delay
    if system_stats is not None:
        handler.system_stats = system_stats
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _closed_port_url() -> str:
    """Return a URL on a port that is currently not accepting connections."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


_SAMPLE_OBJECT_INFO: dict[str, Any] = {
    "CheckpointLoaderSimple": {
        "input": {"required": {"ckpt_name": ["STRING", {}]}},
        "output": [["MODEL"], ["CLIP"], ["VAE"]],
    },
    "KSampler": {
        "input": {
            "required": {
                "model": ["MODEL"],
                "seed": ["INT", {"default": 0}],
                "steps": ["INT", {"default": 20}],
            },
            "optional": {"mask": ["MASK"]},
        },
        "output": [["LATENT"]],
    },
    "VAEDecode": {
        "input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}},
        "output": [["IMAGE"]],
    },
}


def _probe(**kwargs: Any) -> RuntimeProbeReceipt:
    return asyncio.run(live_runtime_schema_probe(**kwargs))


# ---------------------------------------------------------------------------
# Live probe: digest stability + receipt content
# ---------------------------------------------------------------------------


def test_probe_ok_receipt_is_live_and_digest_stable(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        first = _probe(server_url=server_url, cache_dir=tmp_path)
        second = _probe(server_url=server_url, cache_dir=tmp_path)

    assert first.status is ProbeStatus.OK
    assert first.live is True
    assert first.readiness == "ready"
    assert first.probe_id.startswith("probe-")
    assert first.endpoint_identity == server_url.rstrip("/")
    assert first.runtime_identity == runtime_fingerprint(server_url)
    assert first.runtime_label == f"server:{server_url.rstrip('/')}"
    assert first.class_count == len(_SAMPLE_OBJECT_INFO)
    assert first.schema_digest == object_info_payload_checksum(_SAMPLE_OBJECT_INFO)
    assert first.digest_algorithm == "sha256"
    assert first.failure_detail is None

    # Digest stability: identical object_info -> identical digest.
    assert first.schema_digest == second.schema_digest
    assert first.to_dict()["schema_digest"] == second.to_dict()["schema_digest"]


def test_probe_digest_changes_when_schema_changes(tmp_path: Path) -> None:
    changed = json.loads(json.dumps(_SAMPLE_OBJECT_INFO))
    changed["KSampler"]["input"]["required"]["cfg"] = ["FLOAT", {"default": 8.0}]

    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        baseline = _probe(server_url=server_url, cache_dir=tmp_path)
    with _stub_runtime(changed) as server_url:
        mutated = _probe(server_url=server_url, cache_dir=tmp_path)

    assert baseline.schema_digest != mutated.schema_digest
    assert baseline.class_count == mutated.class_count


def test_probe_reports_class_results_for_all_and_subset(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        all_results = _probe(server_url=server_url, cache_dir=tmp_path)
        subset = _probe(server_url=server_url, cache_dir=tmp_path, class_types=["KSampler", "NoSuchNode"])

    by_name = {result.class_type: result for result in all_results.class_results}
    assert list(all_results.class_results) == sorted(all_results.class_results, key=lambda r: r.class_type)
    assert by_name["KSampler"].present is True
    assert by_name["KSampler"].input_count == 4  # 3 required + 1 optional
    assert by_name["KSampler"].output_count == 1
    assert by_name["CheckpointLoaderSimple"].input_count == 1
    assert by_name["CheckpointLoaderSimple"].output_count == 3

    assert [r.class_type for r in subset.class_results] == ["KSampler", "NoSuchNode"]
    assert subset.class_results[0].present is True
    assert subset.class_results[1].present is False
    # class_count stays the runtime-wide class count, not the subset size.
    assert subset.class_count == len(_SAMPLE_OBJECT_INFO)


def test_probe_readiness_reflects_system_stats(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        ready = _probe(server_url=server_url, cache_dir=tmp_path)
    assert ready.readiness == "ready"


def test_probe_sync_wrapper_matches_async(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = live_runtime_schema_probe_sync(server_url=server_url, cache_dir=tmp_path)
        async_receipt = _probe(server_url=server_url, cache_dir=tmp_path)
    assert receipt.status is ProbeStatus.OK
    assert receipt.schema_digest == async_receipt.schema_digest


# ---------------------------------------------------------------------------
# Typed failure states
# ---------------------------------------------------------------------------


def test_probe_unavailable_when_endpoint_refused(tmp_path: Path) -> None:
    receipt = _probe(server_url=_closed_port_url(), cache_dir=tmp_path, timeout=2.0)
    assert receipt.status is ProbeStatus.UNAVAILABLE
    assert receipt.live is False
    assert receipt.schema_digest is None
    assert receipt.class_count == 0
    assert receipt.class_results == ()
    assert receipt.readiness == "not_ready"
    assert receipt.failure_detail is not None


def test_probe_timeout_when_endpoint_never_responds(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO), delay=5.0) as server_url:
        started = time.monotonic()
        receipt = _probe(server_url=server_url, cache_dir=tmp_path, timeout=0.4)
        elapsed = time.monotonic() - started
    assert receipt.status is ProbeStatus.TIMEOUT
    assert receipt.live is False
    assert receipt.schema_digest is None
    # /system_stats still answers on the stub, so the runtime itself is ready;
    # only the schema endpoint hung. readiness reflects the runtime, status the probe.
    assert receipt.readiness == "ready"
    assert elapsed < 4.0, "probe must honor the caller timeout, not the client default"


def test_probe_stale_from_matching_cache(tmp_path: Path) -> None:
    server_url = _closed_port_url()
    cache_path = object_info_cache_path(server_url=server_url, cache_dir=tmp_path)
    write_object_info_cache(
        cache_path,
        dict(_SAMPLE_OBJECT_INFO),
        runtime_fingerprint=runtime_fingerprint(server_url),
        server_url=server_url,
    )

    receipt = _probe(server_url=server_url, cache_dir=tmp_path, timeout=1.0)
    assert receipt.status is ProbeStatus.STALE
    assert receipt.live is False
    assert receipt.schema_digest == object_info_payload_checksum(_SAMPLE_OBJECT_INFO)
    assert receipt.class_count == len(_SAMPLE_OBJECT_INFO)
    assert len(receipt.class_results) == len(_SAMPLE_OBJECT_INFO)
    assert receipt.readiness == "not_ready"


def test_probe_mismatched_runtime_cache(tmp_path: Path) -> None:
    server_url = _closed_port_url()
    cache_path = object_info_cache_path(server_url=server_url, cache_dir=tmp_path)
    write_object_info_cache(
        cache_path,
        dict(_SAMPLE_OBJECT_INFO),
        runtime_fingerprint="other-runtime-fingerprint",
        server_url="http://other-runtime.invalid",
    )

    receipt = _probe(server_url=server_url, cache_dir=tmp_path, timeout=1.0)
    assert receipt.status is ProbeStatus.MISMATCHED_RUNTIME
    assert receipt.live is False
    assert receipt.schema_digest is None
    assert receipt.class_count == 0
    assert receipt.class_results == ()
    assert "not evidence for this runtime" in receipt.failure_detail


def test_probe_does_not_fallback_to_cache_when_disabled(tmp_path: Path) -> None:
    server_url = _closed_port_url()
    cache_path = object_info_cache_path(server_url=server_url, cache_dir=tmp_path)
    write_object_info_cache(
        cache_path,
        dict(_SAMPLE_OBJECT_INFO),
        runtime_fingerprint=runtime_fingerprint(server_url),
        server_url=server_url,
    )

    receipt = _probe(server_url=server_url, cache_dir=tmp_path, timeout=1.0, allow_cache_fallback=False)
    assert receipt.status is ProbeStatus.UNAVAILABLE
    assert receipt.schema_digest is None


# ---------------------------------------------------------------------------
# Receipt structure: serialization + typed validation
# ---------------------------------------------------------------------------


def test_receipt_dict_roundtrip(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
    payload = receipt.to_dict()
    rebuilt = RuntimeProbeReceipt.from_dict(payload)
    assert rebuilt == receipt
    assert rebuilt.to_dict() == payload


def test_receipt_rejects_unknown_fields_and_bad_status(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
    payload = receipt.to_dict()

    with pytest.raises(ValueError, match="unknown field"):
        RuntimeProbeReceipt.from_dict({**payload, "fabricated_tier": "live_runtime_schema"})

    with pytest.raises(ValueError, match="not a valid ProbeStatus"):
        RuntimeProbeReceipt.from_dict({**payload, "status": "live_runtime_schema"})

    # A receipt cannot claim to be live while reporting a failure status.
    with pytest.raises(ValueError, match="live=False"):
        RuntimeProbeReceipt.from_dict({**payload, "status": "unavailable", "schema_digest": None})

    # A live receipt must carry a digest.
    with pytest.raises(ValueError, match="schema_digest"):
        RuntimeProbeReceipt.from_dict({**payload, "schema_digest": None})

    # A stale receipt must carry the cached digest.
    stale = dict(payload)
    stale.update({"status": "stale", "live": False, "schema_digest": None})
    with pytest.raises(ValueError, match="stale receipt"):
        RuntimeProbeReceipt.from_dict(stale)

    # A mismatched-runtime receipt must NOT carry a digest for this runtime.
    mismatched = dict(payload)
    mismatched.update({"status": "mismatched_runtime", "live": False})
    with pytest.raises(ValueError, match="must not carry"):
        RuntimeProbeReceipt.from_dict(mismatched)


def test_receipt_digest_must_be_sha256_hex(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
    payload = receipt.to_dict()
    with pytest.raises(ValueError, match="64-char lowercase sha256"):
        RuntimeProbeReceipt.from_dict({**payload, "schema_digest": "not-a-digest"})


# ---------------------------------------------------------------------------
# Independent verification (what the queue gate will do)
# ---------------------------------------------------------------------------


def test_verify_receipt_recomputes_digest_and_identity_from_live_objects(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
        # Independent re-fetch: the gate queries the endpoint itself and
        # recomputes everything from the wire payload.
        verdict = asyncio.run(verify_probe_receipt_live(receipt, timeout=2.0))

    assert verdict["verified"] is True
    assert verdict["strong_tier_eligible"] is True
    assert verdict["status"] == "ok"
    assert verdict["reasons"] == []
    assert verdict["checks"]["digest"] is True
    assert verdict["checks"]["endpoint"] is True
    assert verdict["checks"]["readiness"] is True


def test_verify_receipt_rejects_tampered_digest(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
        forged = RuntimeProbeReceipt.from_dict({**receipt.to_dict(), "schema_digest": "0" * 64})
        verdict = asyncio.run(verify_probe_receipt_live(forged, timeout=2.0))

    assert verdict["verified"] is False
    assert verdict["strong_tier_eligible"] is False
    assert "schema_digest_mismatch" in verdict["reasons"]


def test_verify_receipt_pure_recomputation_and_endpoint_mismatch(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)

    verdict = verify_probe_receipt(
        receipt,
        object_info=_SAMPLE_OBJECT_INFO,
        endpoint_identity=server_url,
    )
    assert verdict["verified"] is True

    wrong_endpoint = verify_probe_receipt(
        receipt,
        object_info=_SAMPLE_OBJECT_INFO,
        endpoint_identity="http://127.0.0.1:1",
    )
    assert wrong_endpoint["verified"] is False
    assert "endpoint_identity_mismatch" in wrong_endpoint["reasons"]

    # A receipt claiming a server endpoint cannot be verified without the
    # endpoint being independently re-fetched.
    no_endpoint = verify_probe_receipt(receipt, object_info=_SAMPLE_OBJECT_INFO)
    assert no_endpoint["verified"] is False
    assert "endpoint_not_recomputed" in no_endpoint["reasons"]


def test_verify_rejects_stale_receipt_as_strong_evidence(tmp_path: Path) -> None:
    server_url = _closed_port_url()
    cache_path = object_info_cache_path(server_url=server_url, cache_dir=tmp_path)
    write_object_info_cache(
        cache_path,
        dict(_SAMPLE_OBJECT_INFO),
        runtime_fingerprint=runtime_fingerprint(server_url),
        server_url=server_url,
    )
    receipt = _probe(server_url=server_url, cache_dir=tmp_path, timeout=1.0)
    assert receipt.status is ProbeStatus.STALE

    # Pure check against the cached payload: digest matches, but the receipt
    # is not live, so it is never strong-tier evidence.
    verdict = verify_probe_receipt(
        receipt,
        object_info=dict(_SAMPLE_OBJECT_INFO),
        endpoint_identity=server_url,
    )
    assert verdict["verified"] is False
    assert verdict["strong_tier_eligible"] is False
    assert "receipt_not_live" in verdict["reasons"]
    assert "receipt_status_stale" in verdict["reasons"]


def test_verify_receipt_freshness_window(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)

    expired = verify_probe_receipt(
        receipt,
        object_info=_SAMPLE_OBJECT_INFO,
        endpoint_identity=server_url,
        max_age_seconds=0,
    )
    assert expired["verified"] is False
    assert expired["strong_tier_eligible"] is False
    assert "receipt_expired" in expired["reasons"]

    fresh = verify_probe_receipt(
        receipt,
        object_info=_SAMPLE_OBJECT_INFO,
        endpoint_identity=server_url,
        max_age_seconds=3600,
    )
    assert fresh["verified"] is True
    assert fresh["strong_tier_eligible"] is True


def test_verify_receipt_requires_digest_recomputation(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
    verdict = verify_probe_receipt(receipt, endpoint_identity=server_url)
    assert verdict["verified"] is False
    assert "digest_not_recomputed" in verdict["reasons"]


def test_verify_live_rejects_down_endpoint(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
    # Server is gone now; a live re-verification must fail cleanly.
    verdict = verify_probe_receipt_live_sync(receipt, timeout=1.0)
    assert verdict["verified"] is False
    assert verdict["strong_tier_eligible"] is False
    assert verdict["reasons"] == ["refetch_unavailable"]


def test_verify_live_rejects_endpoint_that_was_not_probed(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url=server_url, cache_dir=tmp_path)
        other_url = _closed_port_url()
        verdict = asyncio.run(verify_probe_receipt_live(receipt, server_url=other_url, timeout=1.0))
    assert verdict["verified"] is False
    assert verdict["reasons"] == ["refetch_unavailable"]
