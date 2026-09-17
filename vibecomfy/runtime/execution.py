from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

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


def _queue_node_errors(queued: Any) -> list[str]:
    """Return Comfy's structured prompt-validation errors, if any.

    Comfy can return a ``prompt_id`` together with ``node_errors`` when it
    accepted a prompt envelope but rejected one or more executable branches.
    Treating that response as success is particularly dangerous for workflows
    that also contain a preview branch: the preview can finish while the
    declared final sink is ignored.
    """
    raw = queued.get("node_errors") if isinstance(queued, Mapping) else getattr(queued, "node_errors", None)
    if not raw:
        return []
    if isinstance(raw, Mapping):
        entries = [
            f"node {node_id}: {detail if detail else '<unspecified node error>'}"
            for node_id, detail in raw.items()
        ]
    elif isinstance(raw, (list, tuple)):
        entries = [str(detail) if detail else "<unspecified node error>" for detail in raw]
    else:
        entries = [str(raw)]
    return entries or ["<unspecified node error>"]


def _raise_on_queue_node_errors(queued: Any) -> None:
    errors = _queue_node_errors(queued)
    if not errors:
        return
    error = WorkflowQueueError(
        "Comfy accepted the prompt envelope but rejected executable node(s): "
        + "; ".join(errors),
        next_action=(
            "Fix the reported node inputs and queue again; no output is considered "
            "successful while node_errors are present."
        ),
    )
    error.diagnostics = [
        {"code": "comfy_node_error", "detail": detail}
        for detail in errors
    ]
    error.prompt_id = normalize_prompt_id(queued)
    # Preserve the final-gate classification through the runtime's generic
    # QueueError wrapper. A prompt envelope can have a prompt_id and still
    # reject the executable final branch, so this is not a successful queue.
    error.output_verification = {
        "status": "rejected",
        "prompt_id": error.prompt_id,
        "declared_final_nodes": [],
        "structured_diagnostics": list(error.diagnostics),
        "source": "comfy_queue_node_errors",
    }
    error.completion_status = "Failed — final output rejected"
    raise error


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


def _final_output_chain_node_ids(bundle: WorkflowBundle) -> set[str]:
    """Return declared sinks and every Python-authored upstream dependency."""
    workflow = bundle.workflow
    # The execution projection is the graph that will actually be sent to
    # Comfy.  In particular, it removes intentionally bypassed branches.  The
    # authored graph may still contain those branches for editor fidelity, so
    # walking its full edge set here would falsely reject an otherwise valid
    # approved API projection whenever a continuation/preview branch is
    # disabled by mode.
    projection = workflow._execution_projection()
    active_node_ids = {str(node_id) for node_id in projection.nodes}
    pending = [
        str(output.node_id)
        for output in workflow.outputs
        if getattr(output, "node_id", None) is not None
        and str(output.node_id) in active_node_ids
    ]
    chain: set[str] = set(pending)
    # Use the canonical execution projection so explicit virtual-wire legs
    # participate in the same ancestry walk as ordinary VibeEdges. The
    # projection validates and materializes those Python-owned legs; a stale
    # sidecar link is therefore never treated as an execution dependency.
    edges = projection.edges
    while pending:
        target = pending.pop()
        for edge in edges:
            if str(edge.to_node) != target:
                continue
            source = str(edge.from_node)
            if source not in chain:
                chain.add(source)
                pending.append(source)
    return chain


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
    bundle.require_canonical_authority("runtime queue")
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
    declared_output_ids = {
        str(output.node_id)
        for output in bundle.workflow.outputs
        if getattr(output, "node_id", None) is not None
    }
    python_node_ids = {str(node_id) for node_id in bundle.workflow.nodes}
    declared_missing_from_python = sorted(
        node_id for node_id in declared_output_ids if node_id not in python_node_ids
    )
    if declared_missing_from_python:
        error = WorkflowQueueError(
            "canonical Python final-output contract references missing node(s): "
            + ", ".join(declared_missing_from_python),
            next_action="repair the OutputSpec node binding before queueing",
        )
        error.diagnostics = [{
            "code": "canonical_final_sink_missing",
            "node_ids": declared_missing_from_python,
        }]
        raise error
    missing_output_ids = sorted(declared_output_ids - {str(node_id) for node_id in payload})
    if missing_output_ids:
        raise WorkflowQueueError(
            "approved API projection is missing declared final output node(s): "
            + ", ".join(missing_output_ids),
            next_action="rebuild the workflow projection and retry; nothing was queued",
        )
    final_chain_ids = _final_output_chain_node_ids(bundle)
    missing_chain_ids = sorted(final_chain_ids - {str(node_id) for node_id in payload})
    if missing_chain_ids:
        error = WorkflowQueueError(
            "approved API projection is missing upstream node(s) on the declared final-output chain: "
            + ", ".join(missing_chain_ids),
            next_action="reconcile and recompile the complete final-output dependency chain",
        )
        error.diagnostics = [{
            "code": "final_output_chain_pruned",
            "node_ids": missing_chain_ids,
            "declared_final_nodes": sorted(declared_output_ids),
        }]
        raise error
    output_contract_errors: list[str] = []
    for output in bundle.workflow.outputs:
        node_id = str(getattr(output, "node_id", ""))
        if not node_id:
            continue
        compiled = payload.get(node_id)
        expected_class = str(getattr(output, "output_type", "") or "")
        actual_class = compiled.get("class_type") if isinstance(compiled, Mapping) else None
        if expected_class and actual_class != expected_class:
            output_contract_errors.append(
                f"final node {node_id}: OutputSpec class {expected_class!r} "
                f"does not match compiled class {actual_class!r}"
            )
    if output_contract_errors:
        raise WorkflowQueueError(
            "canonical final-output contract disagrees with the approved compiled graph: "
            + "; ".join(output_contract_errors),
            next_action="reconcile the workflow against the live schema before queueing",
        )
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
    _raise_on_queue_node_errors(queued)
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
    _raise_on_queue_node_errors(queued)
    return QueuedExecution(
        queued=queued,
        prompt_id=normalize_prompt_id(queued),
        outputs=[],
    )
