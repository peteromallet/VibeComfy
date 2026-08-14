"""Focused tests for the queue gate consuming A03 probe receipts (H02).

Covers the acceptance contract:

- a fresh, matching, successful probe receipt satisfies runtime-schema
  evidence and the queue proceeds;
- missing (bare tier label), stale, mismatched-runtime, unavailable, expired,
  and fabricated receipts block queueing with typed diagnostics;
- a queue attempt with neither a receipt nor any evidence tier is blocked too
  (fail-closed), with a narrow named opt-out for non-runtime/offline
  validation (`require_probe_receipt=False`);
- a bare tier label (``live_runtime_schema``) no longer satisfies the gate —
  strong evidence exists only as a verified probe receipt;
- both verification entry points are exercised: live re-fetch
  (``verify_probe_receipt_live``) and pure recomputation
  (``verify_probe_receipt``), plus the typed stage-handoff wiring
  (``StageResult.value["runtime_probe_receipt"]``).
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

from vibecomfy.comfy_nodes.agent.contracts import StageResult, TurnContext
from vibecomfy.comfy_nodes.agent.gates import (
    RUNTIME_PROBE_NOT_VERIFIED_CODE,
    RUNTIME_PROBE_RECEIPT_INVALID_CODE,
    RUNTIME_PROBE_RECEIPT_REQUIRED_CODE,
    RUNTIME_READINESS_UNVERIFIED_CODE,
    derive_gates,
    initialize_gates,
    update_queue_gate,
)
from vibecomfy.runtime.schema_probe import (
    RuntimeProbeReceipt,
    live_runtime_schema_probe_sync,
)
from vibecomfy.schema.cache import (
    object_info_cache_path,
    runtime_fingerprint,
    write_object_info_cache,
)


# ---------------------------------------------------------------------------
# Stub ComfyUI HTTP server (a real live endpoint for /system_stats + /object_info)
# ---------------------------------------------------------------------------


class _StubComfyHandler(BaseHTTPRequestHandler):
    object_info: dict[str, Any] = {}
    system_stats: dict[str, Any] = {"system": {"comfyui_version": "stub"}}

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler hook
        path = self.path.rstrip("/")
        if path == "/system_stats":
            self._send_json(200, self.system_stats)
        elif path == "/object_info":
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
def _stub_runtime(object_info: dict[str, Any]) -> Iterator[str]:
    handler = _StubComfyHandler
    handler.object_info = object_info
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


def _probe(server_url: str, cache_dir: Path) -> RuntimeProbeReceipt:
    return live_runtime_schema_probe_sync(server_url=server_url, cache_dir=cache_dir)


def _gate_context() -> TurnContext:
    """A context with a passing queue_validate stage already recorded."""
    context = TurnContext(session_id="h02")
    initialize_gates(context)
    context.record_stage(
        StageResult(
            stage="queue_validate",
            ok=True,
            blocking=False,
            issues=(),
            gate_updates={"queue_validate_ok": True},
        )
    )
    return context


def _blocker_codes(blockers: tuple[dict[str, Any], ...]) -> list[str]:
    return [str(blocker.get("code")) for blocker in blockers]


# ---------------------------------------------------------------------------
# Acceptance 1: fresh matching successful probe satisfies runtime-schema evidence
# ---------------------------------------------------------------------------


def test_fresh_matching_probe_satisfies_runtime_schema_evidence(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        context = _gate_context()
        blockers = update_queue_gate(context, probe_receipt=receipt)

    assert blockers == ()
    assert context.gate_results["queue_validate_ok"].ok is True
    evidence = context.gate_results["queue_validate_ok"].evidence
    assert evidence["probe_receipt_present"] is True
    assert evidence["probe_receipt_verified"] is True
    assert evidence["probe_receipt_strong_tier_eligible"] is True
    assert evidence["probe_receipt_status"] == "ok"
    assert evidence["probe_receipt_reasons"] == ()  # GateResult freezes lists to tuples


def test_verified_receipt_attached_to_stage_handoff_passes_gate(tmp_path: Path) -> None:
    """M1 wiring: a producer attaches the receipt to the queue stage's typed
    value and the gate consumes it without a new call-site argument."""
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        context = TurnContext(session_id="h02")
        initialize_gates(context)
        context.record_stage(
            StageResult(
                stage="queue_validate",
                ok=True,
                blocking=False,
                issues=(),
                value={"runtime_probe_receipt": receipt.to_dict()},
                gate_updates={"queue_validate_ok": True},
            )
        )
        blockers = update_queue_gate(context)

    assert blockers == ()
    assert context.gate_results["queue_validate_ok"].ok is True


def test_derive_gates_forwards_receipt_and_allows_queue(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        context = TurnContext(session_id="h02")
        initialize_gates(context, plan_state="not_required")
        for name in (
            "python_load_ok",
            "lower_ok",
            "ir_validate_ok",
            "ui_emit_ok",
            "ui_fidelity_ok",
            "ui_load_safe_ok",
        ):
            context.set_gate(name, True, evidence={"test": name})
        context.record_stage(
            StageResult(
                stage="queue_validate",
                ok=True,
                blocking=False,
                issues=(),
                gate_updates={"queue_validate_ok": True},
            )
        )
        derived = derive_gates(context, probe_receipt=receipt, plan_state="not_required")

    assert derived.queue_blockers == ()
    assert context.gate_results["queue_validate_ok"].ok is True
    assert context.queue_allowed is True


# ---------------------------------------------------------------------------
# Acceptance 3: a bare tier label no longer satisfies the gate
# ---------------------------------------------------------------------------


def test_bare_live_runtime_schema_tier_label_is_fabrication_and_blocks(tmp_path: Path) -> None:
    context = _gate_context()
    blockers = update_queue_gate(context, evidence_tiers=frozenset({"live_runtime_schema"}))

    assert _blocker_codes(blockers) == [RUNTIME_READINESS_UNVERIFIED_CODE]
    blocker = blockers[0]
    assert blocker["severity"] == "error"
    assert blocker["evidence"]["receipt_present"] is False
    assert blocker["evidence"]["provided_tiers"] == ["live_runtime_schema"]
    assert context.gate_results["queue_validate_ok"].ok is False
    assert context.queue_allowed is False
    evidence = context.gate_results["queue_validate_ok"].evidence
    assert evidence["probe_receipt_present"] is False
    assert evidence["probe_receipt_verified"] is None


def test_bare_object_info_tier_label_also_blocks(tmp_path: Path) -> None:
    context = _gate_context()
    blockers = update_queue_gate(context, evidence_tiers=frozenset({"object_info"}))

    assert _blocker_codes(blockers) == [RUNTIME_READINESS_UNVERIFIED_CODE]


def test_weak_tiers_without_receipt_still_block(tmp_path: Path) -> None:
    context = _gate_context()
    blockers = update_queue_gate(context, evidence_tiers=frozenset({"web", "hivemind"}))

    assert _blocker_codes(blockers) == ["runtime_readiness_weak_evidence"]
    assert context.gate_results["queue_validate_ok"].ok is False


# ---------------------------------------------------------------------------
# Acceptance 2: stale / mismatched / unavailable / fabricated receipts block
# ---------------------------------------------------------------------------


def test_stale_receipt_blocks_with_typed_diagnostics(tmp_path: Path) -> None:
    server_url = _closed_port_url()
    cache_path = object_info_cache_path(server_url=server_url, cache_dir=tmp_path)
    write_object_info_cache(
        cache_path,
        dict(_SAMPLE_OBJECT_INFO),
        runtime_fingerprint=runtime_fingerprint(server_url),
        server_url=server_url,
    )
    receipt = _probe(server_url, tmp_path)
    assert receipt.status.value == "stale"
    assert receipt.live is False

    context = _gate_context()
    blockers = update_queue_gate(context, probe_receipt=receipt, verify_timeout=2.0)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    blocker = blockers[0]
    reasons = blocker["evidence"]["reasons"]
    assert "receipt_status_stale" in reasons
    assert "receipt_not_live" in reasons
    assert blocker["evidence"]["receipt_claimed_status"] == "stale"
    assert context.gate_results["queue_validate_ok"].ok is False


def test_mismatched_runtime_receipt_blocks(tmp_path: Path) -> None:
    server_url = _closed_port_url()
    cache_path = object_info_cache_path(server_url=server_url, cache_dir=tmp_path)
    write_object_info_cache(
        cache_path,
        dict(_SAMPLE_OBJECT_INFO),
        runtime_fingerprint="other-runtime-fingerprint",
        server_url="http://other-runtime.invalid",
    )
    receipt = _probe(server_url, tmp_path)
    assert receipt.status.value == "mismatched_runtime"

    context = _gate_context()
    blockers = update_queue_gate(context, probe_receipt=receipt, verify_timeout=2.0)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    assert "receipt_status_mismatched_runtime" in blockers[0]["evidence"]["reasons"]
    assert context.gate_results["queue_validate_ok"].ok is False


def test_unavailable_receipt_blocks(tmp_path: Path) -> None:
    receipt = _probe(_closed_port_url(), tmp_path)
    assert receipt.status.value == "unavailable"
    assert receipt.live is False

    context = _gate_context()
    blockers = update_queue_gate(context, probe_receipt=receipt, verify_timeout=2.0)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    reasons = blockers[0]["evidence"]["reasons"]
    assert "receipt_status_unavailable" in reasons
    assert "receipt_not_live" in reasons
    assert context.gate_results["queue_validate_ok"].ok is False


def test_ok_receipt_with_down_endpoint_blocks_on_live_refetch(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        # Server is shut down when the with-block exits: the gate's independent
        # re-fetch of the receipt's own endpoint now fails.
    context = _gate_context()
    blockers = update_queue_gate(context, probe_receipt=receipt, verify_timeout=2.0)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    assert blockers[0]["evidence"]["reasons"] == ["refetch_unavailable"]
    assert context.gate_results["queue_validate_ok"].ok is False


def test_tampered_digest_receipt_blocks_as_fabricated(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        forged = RuntimeProbeReceipt.from_dict({**receipt.to_dict(), "schema_digest": "0" * 64})
        context = _gate_context()
        blockers = update_queue_gate(context, probe_receipt=forged)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    assert "schema_digest_mismatch" in blockers[0]["evidence"]["reasons"]
    assert context.gate_results["queue_validate_ok"].ok is False


def test_malformed_receipt_payload_blocks_as_invalid(tmp_path: Path) -> None:
    context = _gate_context()
    fabricated_payload = {
        "probe_id": "probe-forged",
        "status": "ok",
        "live": True,
        # missing every other required field
    }
    blockers = update_queue_gate(context, probe_receipt=fabricated_payload)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_RECEIPT_INVALID_CODE]
    blocker = blockers[0]
    assert any("required field" in reason for reason in blocker["evidence"]["reasons"])
    assert blocker["evidence"]["required_contract"] == "RuntimeProbeReceipt"
    assert context.gate_results["queue_validate_ok"].ok is False


def test_expired_receipt_blocks_within_gate_freshness_window(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        old = RuntimeProbeReceipt.from_dict(
            {
                **receipt.to_dict(),
                "produced_at": (
                    datetime.now(timezone.utc) - timedelta(minutes=30)
                ).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
        )
        context = _gate_context()
        blockers = update_queue_gate(context, probe_receipt=old, max_age_seconds=60.0)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    assert "receipt_expired" in blockers[0]["evidence"]["reasons"]
    assert blockers[0]["evidence"]["checks"]["freshness"] is False
    assert context.gate_results["queue_validate_ok"].ok is False


def test_expired_receipt_blocks_with_gate_default_max_age(tmp_path: Path) -> None:
    """The gate applies its own freshness window when the caller gives none."""
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        old = RuntimeProbeReceipt.from_dict(
            {
                **receipt.to_dict(),
                "produced_at": (
                    datetime.now(timezone.utc) - timedelta(hours=2)
                ).isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
        )
        context = _gate_context()
        blockers = update_queue_gate(context, probe_receipt=old)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    assert "receipt_expired" in blockers[0]["evidence"]["reasons"]


def test_fabricated_receipt_attached_to_stage_handoff_blocks(tmp_path: Path) -> None:
    """Wiring must be fail-closed too: a handoff receipt that fails verification
    blocks even though the stage itself reported ok."""
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        forged = RuntimeProbeReceipt.from_dict({**receipt.to_dict(), "schema_digest": "0" * 64})
        context = TurnContext(session_id="h02")
        initialize_gates(context)
        context.record_stage(
            StageResult(
                stage="queue_validate",
                ok=True,
                blocking=False,
                issues=(),
                value={"runtime_probe_receipt": forged.to_dict()},
                gate_updates={"queue_validate_ok": True},
            )
        )
        blockers = update_queue_gate(context)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    assert context.gate_results["queue_validate_ok"].ok is False


# ---------------------------------------------------------------------------
# Pure recomputation path (verify_probe_receipt) + fail-closed guards
# ---------------------------------------------------------------------------


def test_pure_recomputation_path_accepts_matching_receipt(tmp_path: Path) -> None:
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        context = _gate_context()
        blockers = update_queue_gate(
            context,
            probe_receipt=receipt,
            verify_live=False,
            object_info=dict(_SAMPLE_OBJECT_INFO),
            endpoint_identity=server_url,
        )

    assert blockers == ()
    assert context.gate_results["queue_validate_ok"].ok is True
    assert context.gate_results["queue_validate_ok"].evidence["probe_receipt_verified"] is True


def test_pure_recomputation_without_observed_payload_blocks(tmp_path: Path) -> None:
    """No independently observed object_info means the digest cannot be
    recomputed: fail-closed, never trusted from the receipt alone."""
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        context = _gate_context()
        blockers = update_queue_gate(context, probe_receipt=receipt, verify_live=False)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_NOT_VERIFIED_CODE]
    reasons = blockers[0]["evidence"]["reasons"]
    assert "digest_not_recomputed" in reasons
    assert context.gate_results["queue_validate_ok"].ok is False


# ---------------------------------------------------------------------------
# Regression guards: missing receipt + no tiers is fail-closed, with a narrow
# named opt-out for non-runtime/offline validation
# ---------------------------------------------------------------------------


def test_missing_receipt_and_tiers_blocks_fail_closed(tmp_path: Path) -> None:
    """H02: a queue attempt with neither a probe receipt nor any evidence tier
    is blocked — absence of both must not silently permit queueing."""
    context = _gate_context()
    blockers = update_queue_gate(context)

    assert _blocker_codes(blockers) == [RUNTIME_PROBE_RECEIPT_REQUIRED_CODE]
    blocker = blockers[0]
    assert blocker["severity"] == "error"
    assert blocker["evidence"]["receipt_present"] is False
    assert blocker["evidence"]["required_contract"] == "RuntimeProbeReceipt"
    assert context.gate_results["queue_validate_ok"].ok is False
    assert context.queue_allowed is False
    evidence = context.gate_results["queue_validate_ok"].evidence
    assert evidence["probe_receipt_present"] is False
    assert evidence["probe_receipt_verified"] is None
    assert evidence["probe_receipt_required"] is True


def test_derive_gates_blocks_without_receipt_unless_offline_opt_out(tmp_path: Path) -> None:
    """The fail-closed default propagates through derive_gates; the narrow
    non-runtime/offline validation opt-out is the only way to pass without a
    verified receipt."""
    context = _gate_context()
    derived = derive_gates(context, plan_state="not_required")
    assert _blocker_codes(derived.queue_blockers) == [RUNTIME_PROBE_RECEIPT_REQUIRED_CODE]
    assert context.queue_allowed is False

    offline_context = _gate_context()
    offline_derived = derive_gates(
        offline_context,
        plan_state="not_required",
        require_probe_receipt=False,
    )
    assert offline_derived.queue_blockers == ()
    assert offline_context.gate_results["queue_validate_ok"].ok is True


def test_explicit_queue_blockers_still_block_even_with_verified_receipt(tmp_path: Path) -> None:
    """A verified receipt satisfies runtime-schema evidence but never masks a
    concrete queue blocker from the stage."""
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)
        context = _gate_context()
        blockers = update_queue_gate(
            context,
            probe_receipt=receipt,
            queue_blockers=({"code": "schema_less_queue_blocker", "severity": "error"},),
        )

    assert _blocker_codes(blockers) == ["schema_less_queue_blocker"]
    assert context.gate_results["queue_validate_ok"].ok is False


def test_gate_verifies_inside_running_event_loop(tmp_path: Path) -> None:
    """The gate's live verification never raises on loop ownership."""
    with _stub_runtime(dict(_SAMPLE_OBJECT_INFO)) as server_url:
        receipt = _probe(server_url, tmp_path)

        async def _in_loop() -> tuple[tuple[dict[str, Any], ...], TurnContext]:
            context = _gate_context()
            return update_queue_gate(context, probe_receipt=receipt), context

        blockers, context = asyncio.run(_in_loop())

    assert blockers == ()
    assert context.gate_results["queue_validate_ok"].ok is True
