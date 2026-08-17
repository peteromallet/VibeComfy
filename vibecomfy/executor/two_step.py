"""Two-step pipeline mode entrypoint seam (B01).

Real execution lands in B03–B04.  This module currently defines only the
typed entrypoint, re-resolves the pipeline mode, and routes through a
test-injectable outcome boundary so orchestration tests can prove the
dispatch toggle without model calls.  No policy, prompt, or session
logic lives here yet.
"""

from __future__ import annotations

from vibecomfy.executor.contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    PipelineMode,
    Report,
    resolve_pipeline_mode,
)


def _run_two_step(
    request: ExecutorRequest,
    *,
    plan: ClassifyDecision,
    client_id: str | None = None,
    executor_id: str,
    additive: bool = False,
) -> ExecutorResult:
    """Two-step execute entrypoint (B01 seam; real execution in B03–B04).

    The request has already been classified by
    :func:`vibecomfy.executor.core.run_executor`; for ``answer_only``
    interactions the plan has additionally been rewritten to forbid edits
    before this seam is reached.  This entrypoint re-resolves the pipeline
    mode for the typed outcome and delegates to the injectable outcome
    boundary.
    """
    pipeline_mode = resolve_pipeline_mode(request)
    return _two_step_outcome(
        request=request,
        plan=plan,
        pipeline_mode=pipeline_mode,
        client_id=client_id,
        executor_id=executor_id,
        additive=additive,
    )


def _two_step_outcome(
    *,
    request: ExecutorRequest,
    plan: ClassifyDecision,
    pipeline_mode: PipelineMode,
    client_id: str | None,
    executor_id: str,
    additive: bool,
) -> ExecutorResult:
    """Test-injectable outcome boundary (B01 stub; real execution in B03–B04).

    B03–B04 replace this body with the bounded execute session; tests inject
    a canned outcome by monkeypatching this function.  The default stub
    returns a typed success result carrying the classified plan so the
    orchestration toggle is exercisable end-to-end without model calls.
    """
    del request, client_id, executor_id, additive
    return ExecutorResult.success(
        report=Report(plan=plan),
        graph=None,
        reply=(
            "[two-step] execute phase active (pipeline_mode="
            f"{pipeline_mode}); full execution lands in B03–B04."
        ),
    )
