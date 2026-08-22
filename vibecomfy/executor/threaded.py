"""Single-conversation executor driver over the shared durable edit kernel.

The threaded driver owns only deliberation policy. It deliberately delegates
graph ingest/edit/validation/emission, transcript persistence, leases,
idempotency, accepted-delta storage, and replay to the existing agent-edit
host. There is no threaded session store and no classifier call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from vibecomfy.agent.deepseek_usage import estimate_deepseek_cost_usd

from .agent_backend import clear_reply_request_capture, snapshot_reply_request_capture
from .contracts import (
    ClassifyDecision,
    ExecutorHostPorts,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    coerce_model_attempts,
    validate_reply_change_claims,
)
from .profiles import AgentSpecShape
from .request_purpose import deterministic_request_purpose

# Lazy at call time inside core; the module-level import here is the typed
# builder seam shared by both deliberation modes (no mode fork below it).
from .core import _build_artifact_lineage_manifest  # noqa: E402

LOGGER = logging.getLogger(__name__)

# Hard production ceiling. Unlike the prototype this is neither a 200-call nor
# a million-token experiment. The shared batch agent enforces this value at
# every continuation boundary.
THREADED_MAX_AGENT_BATCHES = 24
THREADED_DEFAULT_AGENT_BATCHES = 16

# T4.3 continuation-substrate decision (recorded): cross-turn continuity is
# carried by the durable CHAT ARTIFACTS inside the agent-edit host
# (``_frag_chat.read_session_chat`` + PROMPT_MEMORY_MESSAGES feeding the
# provider's recent-conversation block), NOT by the lease-fenced thread
# transcript store. The host remains the single session/turn/checkpoint/
# replay authority and the single writer of durable turn state; the
# ``host_ports.thread_*`` transcript hooks stay production-bound but
# deliberately driver-unconsumed (a second write path with no reader would
# be dead weight and a new failure surface). Recovery keeps Row-7 semantics
# via the one closed-checkpoint projector.
THREADED_CONTINUATION_SUBSTRATE = "chat_artifacts"


@dataclass(frozen=True)
class ThreadedPurposeBudget:
    """Host-owned purpose reserves around the shared bounded agent loop.

    Research and editing share the durable agent conversation. Recovery is a
    bounded subset of that loop, while final projection has an independent
    reserve and therefore cannot be consumed by research. The underlying edit
    kernel additionally enforces its own atomic batch/retry limits.

    T4.3 decision (recorded): the reserves are ADVISORY-ONLY by design. They
    validate the intended partition of the production ceiling and are pinned
    by contract tests, but they are deliberately NOT subtracted from the
    ``max_batches`` value handed to the host: the batch host already enforces
    its own atomic per-turn limits, and the hard ceiling that reaches it stays
    ``min(requested, THREADED_MAX_AGENT_BATCHES)``.
    """

    research_and_edit_batches: int = THREADED_DEFAULT_AGENT_BATCHES
    recovery_batches_reserved: int = 2
    final_projection_reserved: int = 1

    def __post_init__(self) -> None:
        if self.research_and_edit_batches < 1:
            raise ValueError("threaded agent budget must be positive")
        if self.research_and_edit_batches > THREADED_MAX_AGENT_BATCHES:
            raise ValueError("threaded agent budget exceeds the production ceiling")
        if self.recovery_batches_reserved < 1 or self.final_projection_reserved != 1:
            raise ValueError("threaded recovery/reply reserves must remain available")


@dataclass(frozen=True)
class ThreadedKernel:
    """Narrow adapter to the shared executor/edit authorities."""

    resolve_spec: Callable[[str | None, str], AgentSpecShape]
    run_implement: Callable[..., ImplementationResult]
    emit_phase: Callable[..., None]
    enforce_reply_grounding: Callable[..., str]
    accepted_delta_ops: Callable[[ImplementationResult | None], tuple[dict[str, Any], ...]]
    implementation_landed_edit: Callable[[ImplementationResult | None], bool]
    no_candidate_reason: Callable[[ImplementationResult | None], str | None]
    run_inspect_reply: Callable[..., str] | None = None


def _threaded_plan(request: ExecutorRequest) -> ClassifyDecision:
    """Return host policy for the classifier-free agent conversation.

    ``adapt`` exposes the existing combined research/edit conversation and its
    shared tool registry.  Purposes forced by the public request shape use the
    same deterministic helper as staged execution: no graph means research;
    ``answer_only`` with a graph means inspection.  The model decides what
    work is useful inside that hard capability envelope; no classifier
    provider call precedes it.
    """
    purpose = deterministic_request_purpose(request)
    if purpose == "research":
        return ClassifyDecision(
            research=True,
            implement=False,
            reply=True,
            route="research",
            task="research_nodes",
            intent="research",
            plan_summary=(
                "Threaded research conversation; no graph is attached and "
                "editing is disabled."
            ),
            research_goal=request.query,
        )
    if purpose == "inspect":
        return ClassifyDecision(
            research=False,
            implement=False,
            reply=True,
            route="inspect",
            task="inspect_graph",
            intent="explain_graph",
            plan_summary=(
                "Threaded graph inspection; answer directly without editing."
            ),
        )
    return ClassifyDecision(
        research=True,
        implement=True,
        reply=True,
        route="adapt",
        task="research_precedent",
        intent="edit",
        effort="high",
        plan_summary="Threaded agent conversation over the shared edit kernel.",
        research_goal=request.query,
        change_goal=request.query,
    )


def _bounded_request(request: ExecutorRequest) -> tuple[ExecutorRequest, ThreadedPurposeBudget]:
    requested = request.max_batches or THREADED_DEFAULT_AGENT_BATCHES
    bounded = min(requested, THREADED_MAX_AGENT_BATCHES)
    budget = ThreadedPurposeBudget(research_and_edit_batches=bounded)
    # Always carry the resolved mode across the host adapter boundary. This
    # matters when threaded mode was selected by the environment rather than
    # an explicit request field: the durable batch host still needs to expose
    # and enforce the composed research+implement tool phase.
    if request.max_batches == bounded and request.pipeline_mode == "threaded":
        return request, budget
    return replace(request, max_batches=bounded, pipeline_mode="threaded"), budget


def _failure_kind(failure: Any) -> str:
    kind = getattr(failure, "kind", "ValidationError")
    value = getattr(kind, "value", kind)
    return str(value)


def _durable_projection_fallback(
    *,
    landed: bool,
    reason: str | None,
    delta_ops: tuple[dict[str, Any], ...],
    projection: Any = None,
) -> str:
    """Narrative helper after a fallible post-checkpoint failure.

    Not a second projector: when ``projection`` is supplied, prose comes from
    the one closed-checkpoint projection (row 6 keeps ``applied``).
    """
    if projection is not None:
        projected = getattr(projection, "reply", None)
        if isinstance(projected, str) and projected:
            return projected
        landed = getattr(projection, "terminal_state", None) == "applied"
        reason = getattr(projection, "reason", reason)
        accepted = getattr(projection, "accepted_delta", ()) or ()
        extracted: list[dict[str, Any]] = []
        for delta in accepted:
            for op in getattr(delta, "ops", ()) or ():
                if isinstance(op, Mapping):
                    extracted.append(dict(op))
        if extracted:
            delta_ops = tuple(extracted)
    if landed:
        if delta_ops:
            count = len(delta_ops)
            noun = "operation" if count == 1 else "operations"
            return (
                "The workflow edit landed. "
                f"The durable accepted change set contains {count} {noun}; "
                "the candidate and accepted change evidence are authoritative."
            )
        return (
            "The workflow edit landed and the durable candidate is ready to "
            "review."
        )
    suffix = f" Reason: {reason}." if reason else ""
    return f"No workflow edit was applied.{suffix}"

def run_threaded_executor(
    request: ExecutorRequest,
    *,
    kernel: ThreadedKernel,
    host_ports: ExecutorHostPorts,
    executor_id: str,
    client_id: str | None = None,
    classify_only: bool = False,
    additive: bool = False,
) -> ExecutorResult:
    """Run one classifier-free durable agent conversation.

    The final public result is projected only after ``run_implement`` returns
    the host's closed durable checkpoint. Its accepted batch is therefore the
    sole delta used for graph output and narration grounding.
    """
    clear_reply_request_capture()
    plan = _threaded_plan(request)
    if classify_only:
        return ExecutorResult.success(
            report=Report(plan=plan, orchestration_mode="threaded"),
            reply=f"[dry-run] threaded route: {plan.effective_route}",
        )

    usage_token = host_ports.begin_deepseek_usage_capture()
    attempt_token = host_ports.begin_model_attempt_capture()

    def build_report(
        implementation: ImplementationResult | None = None,
    ) -> Report:
        usage, cache_breakout_complete = host_ports.snapshot_deepseek_usage_capture()
        attempts = coerce_model_attempts(host_ports.snapshot_model_attempt_capture())
        est_cost, cost_basis = estimate_deepseek_cost_usd(
            usage,
            cache_breakout_complete=cache_breakout_complete,
        )
        return Report(
            plan=plan,
            implementation=implementation,
            deepseek_usage=usage,
            deepseek_est_cost_usd=est_cost,
            deepseek_cost_basis=cost_basis,
            model_attempts=attempts,
            reply_request=snapshot_reply_request_capture(),
            orchestration_mode="threaded",
            artifact_lineage=_build_artifact_lineage_manifest(
                request,
                plan=plan,
                research=None,
                implementation_result=implementation,
                model_attempts=attempts,
                orchestration_mode="threaded",
            ),
        )

    def finish(result: ExecutorResult) -> ExecutorResult:
        host_ports.end_deepseek_usage_capture(usage_token)
        host_ports.end_model_attempt_capture(attempt_token)
        return result

    inspect_only = plan.effective_route == "inspect"
    phase = "reply" if inspect_only else "execute"
    try:
        spec = kernel.resolve_spec(request.profile, phase)
    except Exception as exc:
        failure = host_ports.classify_failure("profile", exc)
        return finish(ExecutorResult.failure(
            kind=_failure_kind(failure),
            stage="profile",
            message=str(getattr(failure, "user_facing_message", exc)),
            report=build_report(),
        ))

    bounded_request, _budget = _bounded_request(request)
    kernel.emit_phase(
        bounded_request,
        executor_id=executor_id,
        phase=phase,
        status="start",
        client_id=client_id,
    )
    if inspect_only:
        if kernel.run_inspect_reply is None:
            return finish(ExecutorResult.failure(
                kind="ValidationError",
                stage="reply",
                message="Threaded inspect reply kernel is unavailable.",
                report=build_report(),
            ))
        try:
            reply = kernel.run_inspect_reply(
                bounded_request,
                spec,
                plan=plan,
                host_ports=host_ports,
            )
        except Exception as exc:
            kernel.emit_phase(
                bounded_request,
                executor_id=executor_id,
                phase=phase,
                status="error",
                client_id=client_id,
            )
            failure_kind = str(getattr(exc, "failure_kind", "ValidationError"))
            stage = str(getattr(exc, "stage", "reply"))
            return finish(ExecutorResult.failure(
                kind=failure_kind,
                stage=stage,
                message=str(exc),
                report=build_report(),
            ))
        kernel.emit_phase(
            bounded_request,
            executor_id=executor_id,
            phase=phase,
            status="done",
            client_id=client_id,
        )
        return finish(ExecutorResult.success(
            report=build_report(),
            graph=None,
            reply=reply,
        ))

    try:
        implementation = kernel.run_implement(
            bounded_request,
            spec,
            plan=plan,
            research_result=None,
            client_id=client_id,
            additive=additive,
            host_ports=host_ports,
        )
    except Exception as exc:
        kernel.emit_phase(
            bounded_request,
            executor_id=executor_id,
            phase=phase,
            status="error",
            client_id=client_id,
        )
        failure_kind = str(getattr(exc, "failure_kind", "ValidationError"))
        stage = str(getattr(exc, "stage", "execute"))
        return finish(ExecutorResult.failure(
            kind=failure_kind,
            stage=stage,
            message=str(exc),
            report=build_report(),
        ))

    durable = implementation.durable_response
    graph = implementation.graph
    landed = kernel.implementation_landed_edit(implementation)
    delta_ops = kernel.accepted_delta_ops(implementation)
    reason = kernel.no_candidate_reason(implementation)

    from vibecomfy.executor.core import _durable_terminal_projection

    projection = None
    try:
        projection = _durable_terminal_projection(
            implementation,
            request_graph=graph or request.graph,
            reply=implementation.message,
            mode="threaded",
        )
    except Exception:
        LOGGER.exception(
            "threaded terminal projection failed after durable checkpoint; "
            "preserving applied work"
        )
        try:
            projection = _durable_terminal_projection(
                implementation,
                request_graph=graph or request.graph,
                failure="threaded terminal projection failed",
                reply=implementation.message,
                mode="threaded",
            )
        except Exception:
            LOGGER.exception(
                "threaded terminal projection retry failed; using accepted-delta fallback"
            )
            projection = None
    if getattr(projection, "graph", None) is not None and getattr(projection, "terminal_state", None) == "applied":
        graph = projection.graph
    elif getattr(projection, "terminal_state", None) != "applied":
        # Non-applied rows: original graph remains authoritative; do not
        # publish a rejected candidate as the product graph.
        if getattr(projection, "terminal_state", None) in {
            "authority_rejected",
            "infra_failure",
            "clarify",
            "no_candidate",
            "no_op",
            "undetermined",
        }:
            graph = projection.graph if getattr(projection, "graph", None) is not None else request.graph

    # The same execute-agent conversation supplies the prose. Projection runs
    # only now, after the durable response closed, and deterministically checks
    # it against the accepted delta/final graph.
    reply = implementation.message or (
        "The workflow edit completed and the candidate is ready to review."
        if landed
        else "No workflow edit was applied."
    )
    try:
        if projection is None:
            raise RuntimeError("threaded terminal projection unavailable")
        reply = kernel.enforce_reply_grounding(
            reply,
            landed=landed,
            graph=graph or request.graph,
            reason=reason,
            delta_ops=delta_ops,
            projection=projection,
        )
        if isinstance(durable, Mapping):
            claim_violations = validate_reply_change_claims(durable)
            if claim_violations:
                # Never expose prose/sidecars that claim beyond the accepted
                # delta. This pass also grounds node identifiers.
                reply = kernel.enforce_reply_grounding(
                    "The workflow edit landed; see the accepted change set in the candidate.",
                    landed=landed,
                    graph=graph or request.graph,
                    reason=reason,
                    delta_ops=delta_ops,
                    projection=projection,
                )
    except TypeError:
        reply = kernel.enforce_reply_grounding(
            reply,
            landed=landed,
            graph=graph or request.graph,
            reason=reason,
            delta_ops=delta_ops,
        )
    except Exception:
        # The accepted delta predates narration/projection. Preserve that
        # durable success with prose derived only from checkpoint facts.
        LOGGER.exception(
            "threaded terminal projection failed after durable checkpoint; "
            "using accepted-delta fallback"
        )
        failed = projection
        if failed is None:
            try:
                failed = _durable_terminal_projection(
                    implementation,
                    request_graph=graph or request.graph,
                    failure="threaded terminal projection failed",
                    reply=implementation.message,
                    mode="threaded",
                )
            except Exception:
                failed = None
        reply = _durable_projection_fallback(
            landed=landed,
            reason=reason,
            delta_ops=delta_ops,
            projection=failed,
        )


    kernel.emit_phase(
        bounded_request,
        executor_id=executor_id,
        phase=phase,
        status="done",
        client_id=client_id,
    )
    return finish(ExecutorResult.success(
        report=build_report(implementation),
        graph=graph,
        reply=reply,
    ))


__all__ = [
    "THREADED_CONTINUATION_SUBSTRATE",
    "THREADED_DEFAULT_AGENT_BATCHES",
    "THREADED_MAX_AGENT_BATCHES",
    "ThreadedKernel",
    "ThreadedPurposeBudget",
    "run_threaded_executor",
]
