from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.errors import RuntimeNodeError, VibeComfyError
from vibecomfy.runtime.client import ComfyClient
from .plan import EvalNodePlan, plan_eval_node
from vibecomfy.runtime.server import comfy_server
from vibecomfy.runtime.execution import normalize_prompt_id
from vibecomfy.runtime.session import SessionConfig, _outputs_from_server_history, _wait_for_server_history


@dataclass(frozen=True)
class EvalNodeResult:
    plan: EvalNodePlan
    queued: bool
    prompt_id: str | None = None
    history_outputs: Any = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    server_url: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload = self.plan.to_json()
        payload.update({
            "queued": self.queued,
            "prompt_id": self.prompt_id,
            "history_outputs": self.history_outputs,
            "elapsed_seconds": self.elapsed_seconds,
            "server_url": self.server_url,
        })
        return payload


async def eval_node(
    workflow_ref: str,
    node_id: str,
    *,
    server_url: str | None = None,
    dry_run: bool = False,
) -> EvalNodeResult:
    plan = plan_eval_node(workflow_ref, node_id, dry_run=dry_run)
    if dry_run or not plan.lookup.get("found") or not plan.queueable:
        return EvalNodeResult(plan=plan, queued=False)

    queue_api = queue_api_for_plan(plan)
    started = time.monotonic()
    log_path = Path("out/runs") / f"eval-node-{int(time.time())}" / "comfy.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with comfy_server(server_url=server_url, log_path=log_path, config=SessionConfig()) as active_url:
            client = ComfyClient(active_url)
            queued = await client.queue_prompt(queue_api)
            prompt_id = normalize_prompt_id(queued)
            history = await _wait_for_server_history(active_url, prompt_id, config=SessionConfig())
            outputs = _outputs_from_server_history(history, prompt_id)
            return EvalNodeResult(
                plan=plan,
                queued=True,
                prompt_id=prompt_id,
                history_outputs=outputs,
                elapsed_seconds=round(time.monotonic() - started, 3),
                server_url=active_url,
            )
    except VibeComfyError:
        raise
    except Exception as exc:
        if server_url is None:
            raise VibeComfyError(
                f"runtime eval-node could not start or use a ComfyUI runtime: {exc}",
                next_action="vibecomfy runtime doctor",
            ) from exc
        raise RuntimeNodeError(
            f"runtime eval-node failed while queueing node {node_id}: {exc}",
            next_action=f"vibecomfy inspect {workflow_ref} --node {node_id}",
        ) from exc


def eval_node_sync(
    workflow_ref: str,
    node_id: str,
    *,
    server_url: str | None = None,
    dry_run: bool = False,
) -> EvalNodeResult:
    return asyncio.run(eval_node(workflow_ref, node_id, server_url=server_url, dry_run=dry_run))


def queue_api_for_plan(plan: EvalNodePlan) -> dict[str, Any]:
    api = {node_id: _copy_node(node) for node_id, node in plan.truncated_api.items()}
    next_id = _next_numeric_node_id(api)
    for injection in plan.preview_injections:
        source = injection.get("source")
        wrapped_via = injection.get("wrapped_via")
        if not (isinstance(source, list) and len(source) == 2 and wrapped_via):
            continue
        if wrapped_via == "PreviewImage":
            preview_id = str(next_id)
            next_id += 1
            api[preview_id] = {"class_type": "PreviewImage", "inputs": {"images": source}}
        elif wrapped_via == "MaskToImage+PreviewImage":
            mask_id = str(next_id)
            preview_id = str(next_id + 1)
            next_id += 2
            api[mask_id] = {"class_type": "MaskToImage", "inputs": {"mask": source}}
            api[preview_id] = {"class_type": "PreviewImage", "inputs": {"images": [mask_id, 0]}}
        elif wrapped_via == "VAEDecode+PreviewImage":
            vae = _target_vae_link(plan)
            if vae is None:
                continue
            decode_id = str(next_id)
            preview_id = str(next_id + 1)
            next_id += 2
            api[decode_id] = {"class_type": "VAEDecode", "inputs": {"samples": source, "vae": vae}}
            api[preview_id] = {"class_type": "PreviewImage", "inputs": {"images": [decode_id, 0]}}
    return api


def _copy_node(node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    copied = dict(node)
    inputs = copied.get("inputs")
    if isinstance(inputs, dict):
        copied["inputs"] = dict(inputs)
    return copied


def _next_numeric_node_id(api: dict[str, Any]) -> int:
    numeric = [int(node_id) for node_id in api if str(node_id).isdigit()]
    return (max(numeric) + 1) if numeric else 1


def _target_vae_link(plan: EvalNodePlan) -> list[Any] | None:
    node = plan.truncated_api.get(plan.node_id)
    inputs = node.get("inputs") if isinstance(node, dict) else {}
    value = inputs.get("vae") if isinstance(inputs, dict) else None
    if isinstance(value, list) and len(value) >= 2:
        return list(value[:2])
    return None


__all__ = ["EvalNodeResult", "eval_node", "eval_node_sync", "queue_api_for_plan"]
