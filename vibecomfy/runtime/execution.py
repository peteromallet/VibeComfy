from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from vibecomfy.errors import WorkflowQueueError
from vibecomfy.workflow_bundle import (
    ApprovedProjectionRecord,
    WorkflowBundle,
    WorkflowBundleError,
    canonical_digest,
)

from .client import ComfyClient


class EmbeddedQueue(Protocol):
    async def queue_prompt_api(self, api_dict: dict[str, Any]) -> Any:
        ...


@dataclass(frozen=True, slots=True)
class QueuedExecution:
    queued: Any
    prompt_id: str | None
    outputs: list[str]


def normalize_prompt_id(queued: Any) -> str | None:
    if isinstance(queued, dict):
        prompt_id = queued.get("prompt_id")
    else:
        prompt_id = getattr(queued, "prompt_id", None)
    if prompt_id is None:
        return None
    return str(prompt_id)


def collect_output_paths(value: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"abs_path", "path", "fullpath", "filename"} and isinstance(item, str):
                paths.append(item)
            else:
                paths.extend(collect_output_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.extend(collect_output_paths(item))
    return paths


def embedded_outputs(queued: Any) -> list[str]:
    payload = getattr(queued, "outputs", None)
    if payload is None and isinstance(queued, dict):
        payload = queued.get("outputs", queued)
    return collect_output_paths(payload)


def authorized_queue_payload(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
) -> dict[str, Any]:
    """Validate one approved record and detach its exact API projection.

    This is deliberately the only semantic fence immediately above either
    transport.  Runtime callers may inspect the bundle for diagnostics, but
    the payload sent to Comfy is always reconstructed from the immutable
    record after the current bundle and digest have been rechecked.
    """
    if not isinstance(record, ApprovedProjectionRecord):
        raise WorkflowBundleError(
            "runtime queue requires an ApprovedProjectionRecord"
        )
    if not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError("runtime queue requires a WorkflowBundle")
    record.assert_matches(
        bundle,
        record.selected_variant,
        record.input_binding,
        api_projection=record.api_projection,
        ui_projection=record.ui_projection,
    )
    payload = record.to_dict()["api_projection"]
    if not isinstance(payload, dict):
        raise WorkflowBundleError("approved API projection must be a JSON object")
    if canonical_digest(payload) != record.api_digest:
        raise WorkflowBundleError("approved API projection digest does not match")
    return payload


async def queue_embedded_prompt(
    queue: EmbeddedQueue,
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
) -> QueuedExecution:
    api_dict = authorized_queue_payload(record, bundle)
    try:
        queued = await queue.queue_prompt_api(api_dict)
    except asyncio.TimeoutError:
        raise
    except Exception as exc:
        raise WorkflowQueueError(
            f"Workflow queue failed: {exc}",
            next_action="Check the embedded ComfyUI logs and verify the workflow can be queued by the active runtime.",
        ) from exc
    return QueuedExecution(
        queued=queued,
        prompt_id=normalize_prompt_id(queued),
        outputs=embedded_outputs(queued),
    )


async def queue_server_prompt(
    record: ApprovedProjectionRecord,
    bundle: WorkflowBundle,
    *,
    server_url: str | None = None,
    client: ComfyClient | None = None,
) -> QueuedExecution:
    api_dict = authorized_queue_payload(record, bundle)
    if client is None:
        if server_url is None:
            raise ValueError("server_url is required when client is not provided")
        client = ComfyClient(server_url)
    try:
        queued = await client._post_prompt(api_dict)
    except asyncio.TimeoutError:
        raise
    except Exception as exc:
        raise WorkflowQueueError(
            f"Workflow queue failed: {exc}",
            next_action="Check server health, the ComfyUI logs, and whether the workflow payload is accepted by this runtime.",
        ) from exc
    return QueuedExecution(
        queued=queued,
        prompt_id=normalize_prompt_id(queued),
        outputs=[],
    )
