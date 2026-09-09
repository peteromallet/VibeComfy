"""Canonical eval execution delegate for the T14 runtime boundary."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from vibecomfy.errors import RuntimeNodeError
from vibecomfy.runtime.run import run, run_embedded
from vibecomfy.runtime.session import RunResult, SessionConfig
from vibecomfy.workflow_bundle import WorkflowBundle, WorkflowBundleError

from .core import approve_eval_subgraph
from .plan import EvalNodePlan, plan_eval_node


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
            "queued": self.queued, "prompt_id": self.prompt_id,
            "history_outputs": self.history_outputs,
            "elapsed_seconds": self.elapsed_seconds, "server_url": self.server_url,
        })
        return payload


async def eval_node(
    bundle: WorkflowBundle,
    target_node_id: str,
    *,
    runtime: Literal["embedded", "server", "runpod"] = "embedded",
    server_url: str | None = None,
    dry_run: bool = False,
    variant: str | None = None,
    run_inputs: Mapping[str, Any] | None = None,
    schema_provider: Any = None,
    config: SessionConfig | None = None,
) -> EvalNodeResult:
    if not isinstance(bundle, WorkflowBundle):
        raise WorkflowBundleError(
            "eval execution requires a WorkflowBundle; load the source with "
            "load_bundle(...) before calling eval_node"
        )
    plan = plan_eval_node(bundle, target_node_id, dry_run=dry_run)
    if dry_run:
        return EvalNodeResult(plan=plan, queued=False)
    if runtime == "runpod":
        raise RuntimeNodeError(
            "eval-node RunPod transport is offline-only; use embedded or server"
        )
    if runtime not in {"embedded", "server"}:
        raise RuntimeNodeError(f"unsupported eval runtime {runtime!r}")
    if not plan.queueable:
        raise RuntimeNodeError(
            f"eval node {target_node_id!r} is not queueable: the selected output is not visualizable",
            next_action=f"vibecomfy inspect <workflow> --node {target_node_id}",
        )

    candidate_bundle, record = approve_eval_subgraph(
        bundle,
        target_node_id,
        variant=variant,
        run_inputs=run_inputs,
        schema_provider=schema_provider,
    )
    started = time.monotonic()
    if runtime == "embedded":
        result: RunResult = await run_embedded(record, candidate_bundle, config=config)
    else:
        result = await run(record, candidate_bundle, server_url=server_url, config=config)
    return EvalNodeResult(
        plan=plan,
        queued=True,
        prompt_id=result.prompt_id,
        history_outputs=result.outputs,
        elapsed_seconds=round(time.monotonic() - started, 3),
        server_url=server_url,
    )


def eval_node_sync(
    bundle: WorkflowBundle,
    target_node_id: str,
    *,
    runtime: Literal["embedded", "server", "runpod"] = "embedded",
    server_url: str | None = None,
    dry_run: bool = False,
    variant: str | None = None,
    run_inputs: Mapping[str, Any] | None = None,
    schema_provider: Any = None,
    config: SessionConfig | None = None,
) -> EvalNodeResult:
    return asyncio.run(
        eval_node(
            bundle,
            target_node_id,
            runtime=runtime,
            server_url=server_url,
            dry_run=dry_run,
            variant=variant,
            run_inputs=run_inputs,
            schema_provider=schema_provider,
            config=config,
        )
    )


__all__ = ["EvalNodeResult", "eval_node", "eval_node_sync"]
