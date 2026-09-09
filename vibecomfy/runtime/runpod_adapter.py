"""Offline RunPod transport for an approved workflow projection.

The serialized transport is exactly the canonical six-field
``ApprovedProjectionRecord`` value.  Decoding produces a value only; it does
not authorize execution without a current ``WorkflowBundle``.
"""

from __future__ import annotations

from typing import Any, Callable

from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundle,
    WorkflowBundleError,
)

from .execution import (
    QueuedExecution,
    authorized_queue_payload,
    embedded_outputs,
    normalize_prompt_id,
)


RAW_RUNPOD_TRANSPORT_MIGRATION = (
    "RunPod transport requires an ApprovedProjectionRecord bound to a current "
    "WorkflowBundle; raw API, UI, scratchpad, and bare-workflow execution are disabled.\n"
    "Next: vibecomfy port check <source> --json\n"
    "Then: vibecomfy port convert <source> --out out/scratchpads/<name>.py"
)

__all__ = [
    "RAW_RUNPOD_TRANSPORT_MIGRATION",
    "prepare_runpod_transport",
    "load_runpod_transport",
    "queue_runpod_stub",
]


def prepare_runpod_transport(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
) -> bytes:
    """Revalidate and serialize one approved record for offline transport."""
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError(RAW_RUNPOD_TRANSPORT_MIGRATION)
    authorized_queue_payload(record, bundle)
    return record.to_canonical_bytes()


def load_runpod_transport(value: bytes) -> ApprovedProjectionRecord:
    """Decode canonical bytes into a value; decoding is not authorization."""
    return ApprovedProjectionRecord.from_canonical_bytes(value)


def queue_runpod_stub(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    *,
    queue: Callable[[dict[str, Any]], Any],
) -> QueuedExecution:
    """Hand the revalidated detached API projection to a local test callback."""
    if not isinstance(record, ApprovedProjectionRecord) or not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError(RAW_RUNPOD_TRANSPORT_MIGRATION)
    payload = authorized_queue_payload(record, bundle)
    queued = queue(payload)
    return QueuedExecution(
        queued=queued,
        prompt_id=normalize_prompt_id(queued),
        outputs=embedded_outputs(queued),
    )
