"""Single-conversation executor driver over the shared durable edit kernel.

The threaded driver owns only deliberation policy. It deliberately delegates
graph ingest/edit/validation/emission, transcript persistence, leases,
idempotency, accepted-delta storage, and replay to the existing agent-edit
host. There is no threaded session store and no classifier call.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from pathlib import Path
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


_LOOKUP_UNAVAILABLE = object()

_GENERIC_DOMAIN_TOKENS: frozenset[str] = frozenset({
    "audio",
    "generate",
    "generation",
    "image",
    "images",
    "input",
    "inputs",
    "latent",
    "load",
    "loader",
    "mask",
    "model",
    "models",
    "node",
    "nodes",
    "output",
    "outputs",
    "preview",
    "process",
    "prompt",
    "prompts",
    "save",
    "text",
    "video",
    "workflow",
})


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def typed_refusal_contract(request: ExecutorRequest) -> bool:
    """True when the caller declared a typed no-candidate / custom-node refusal.

    ``answer_only`` is the explain/advice contract. Scenarios that declare
    ``allow_safe_refusal_outcome_kinds`` or ``expected_no_candidate_absent_*``
    need an implement-capable lane so the batch path can emit
    ``requires_custom_nodes``.
    """
    kinds = _string_tuple(getattr(request, "allow_safe_refusal_outcome_kinds", ()))
    classes = _string_tuple(getattr(request, "expected_no_candidate_absent_classes", ()))
    features = _string_tuple(getattr(request, "expected_no_candidate_absent_features", ()))
    return bool(kinds or classes or features)


def _graph_attached_note(request: ExecutorRequest) -> str:
    if request.graph is not None:
        return "A ComfyUI canvas graph is attached to this turn."
    return "No ComfyUI canvas graph is attached to this turn."


def _open_adapt_plan(request: ExecutorRequest) -> ClassifyDecision:
    intent_context = (
        f"End-user interaction intent: interaction_mode="
        f"{request.interaction_mode or 'unspecified'}"
        + (
            " (answer_only: respond without editing)"
            if request.interaction_mode == "answer_only"
            and not typed_refusal_contract(request)
            else ""
        )
        + "."
    )
    return ClassifyDecision(
        research=True,
        implement=True,
        reply=True,
        route="adapt",
        task="research_precedent",
        intent="edit",
        effort="high",
        plan_summary=(
            "Threaded agent conversation. All affordances are available — "
            "outside research (workflows, node packs, techniques), graph "
            "inspection, direct answer, concrete graph edits, layout "
            "cleanup — and NONE of them is a required step; choose based on "
            "the verbatim request alone. " + intent_context + " "
            + _graph_attached_note(request)
        ),
        research_goal=request.query,
        change_goal=request.query,
    )


def _inspect_answer_plan(request: ExecutorRequest) -> ClassifyDecision:
    return ClassifyDecision(
        research=False,
        implement=False,
        reply=True,
        route="inspect",
        task="inspect_graph",
        intent="explain_graph",
        effort="high",
        plan_summary=(
            "Declared answer-only interaction (interaction_mode="
            "answer_only): answer the user without producing a graph "
            "edit. Inspect the attached graph, cite what is actually "
            "there, and respond; no implement phase will run. "
            + _graph_attached_note(request)
        ),
        research_goal=request.query,
        change_goal="",
    )


def coerce_declared_interaction_lane(
    request: ExecutorRequest,
    plan: ClassifyDecision | None = None,
) -> ClassifyDecision:
    """Honor caller-declared interaction contracts without query-text inference.

    Typed refusal stays implement-capable even under ``answer_only``.
    Bare ``answer_only`` explain/advice turns take the inspect lane.
    Staged diagnostics classified as bare ``respond`` under ``answer_only``
    are lifted to inspect.
    """
    if typed_refusal_contract(request):
        if plan is None or plan.effective_route in {"inspect", "respond"}:
            return _open_adapt_plan(request)
        return plan
    if request.interaction_mode == "answer_only":
        if plan is None or plan.effective_route == "respond":
            return _inspect_answer_plan(request)
        return plan
    if plan is None:
        return _open_adapt_plan(request)
    return plan


def _threaded_plan(request: ExecutorRequest) -> ClassifyDecision:
    """Return the ONE envelope for the agent conversation.

    RR1-FIX-REV2 (F9 / §31a) removed shape-inferred purpose mapping. That
    removal stands: nothing here infers intent from query text.

    Caller-DECLARED contracts are transported as data:
    ``answer_only`` explain/advice turns route inspect (no implement).
    Typed-refusal contracts stay implement-capable so the batch path can
    emit ``requires_custom_nodes``. Requests without a declared contract
    keep the open envelope.
    """
    return coerce_declared_interaction_lane(request, plan=None)


def _graph_class_types(graph: Any) -> set[str]:
    classes: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key in ("class_type", "type"):
                class_type = value.get(key)
                if isinstance(class_type, str) and class_type.strip():
                    classes.add(class_type.strip())
                    break
            for child in value.values():
                if isinstance(child, (Mapping, list, tuple)):
                    walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(graph)
    return classes


def _query_names_class(query: str, class_type: str) -> bool:
    if not class_type:
        return False
    if re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(class_type)}(?![A-Za-z0-9_])",
        query,
        re.IGNORECASE,
    ):
        return True
    folded_class = re.sub(r"[^a-z0-9]", "", class_type.lower())
    if len(folded_class) < 4:
        return False
    request_tokens = tuple(
        dict.fromkeys(
            re.sub(r"[^a-z0-9]", "", token.lower())
            for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", query)
        )
    )
    return any(
        len(token) >= 4
        and token not in _GENERIC_DOMAIN_TOKENS
        and folded_class.startswith(token)
        for token in request_tokens
    )


def _default_schema_lookup(class_type: str) -> Any:
    """Return the live schema for *class_type*, or None if proven absent.

    Returns ``_LOOKUP_UNAVAILABLE`` when the index cannot be consulted so
    callers fail closed (never fabricate an absence).
    """
    try:
        from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

        root = Path(__file__).resolve().parents[1] / "porting" / "cache" / "object_info"
        provider = ObjectInfoIndexSchemaProvider(str(root))
        return provider.get_schema(class_type)
    except Exception:
        return _LOOKUP_UNAVAILABLE


def inspect_named_runtime_absences(
    request: ExecutorRequest,
    *,
    schema_lookup: Callable[[str], Any] | None = None,
) -> tuple[str, ...]:
    """Return request-named classes proven absent from graph + schema index.

    A name is attached only when the request names it or the caller declared
    it absent, it is not present on the attached graph, and schema lookup
    returns None. An unavailable index never becomes evidence.
    """
    query = str(request.query or "")
    declared = _string_tuple(getattr(request, "expected_no_candidate_absent_classes", ()))
    candidates: list[str] = []
    for name in declared:
        if name not in candidates:
            candidates.append(name)
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", query):
        if token in candidates:
            continue
        folded = re.sub(r"[^a-z0-9]", "", token.lower())
        if folded in _GENERIC_DOMAIN_TOKENS:
            continue
        if token[0].isupper() and any(ch.islower() for ch in token[1:]):
            candidates.append(token)
    present = _graph_class_types(request.graph)
    lookup = schema_lookup or _default_schema_lookup
    missing: list[str] = []
    for name in candidates:
        if name in present:
            continue
        if name not in declared and not _query_names_class(query, name):
            continue
        try:
            schema = lookup(name)
        except Exception:
            continue
        if schema is _LOOKUP_UNAVAILABLE:
            continue
        if schema is None:
            missing.append(name)
    return tuple(missing)


def synthesize_inspect_refusal_implementation(
    request: ExecutorRequest,
    *,
    reply: str,
    schema_lookup: Callable[[str], Any] | None = None,
) -> ImplementationResult | None:
    """Attach ``authoring_blocker.missing_runtime_classes`` on inspect.

    ``promote_requires_custom_nodes_outcome`` reads missing classes only
    from that blocker. Empty proof returns None (fail-closed).
    """
    missing = inspect_named_runtime_absences(request, schema_lookup=schema_lookup)
    if not missing:
        return None
    from vibecomfy.comfy_nodes.agent.contracts import (
        missing_runtime_classes_from_report,
        promote_requires_custom_nodes_outcome,
    )

    blocker_report = {
        "authoring_blocker": {
            "reason": "named_class_absent_from_schema",
            "missing_runtime_classes": list(missing),
        },
        "graph_unchanged": True,
    }
    outcome = promote_requires_custom_nodes_outcome(
        {"kind": "noop"},
        missing_classes=missing_runtime_classes_from_report(blocker_report),
    )
    return ImplementationResult(
        message=reply,
        durable_response={
            "outcome": outcome,
            "graph_unchanged": True,
            "report": blocker_report,
            "no_candidate_reason": (
                "requires_custom_nodes"
                if outcome.get("kind") == "requires_custom_nodes"
                else "no_changes"
            ),
        },
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
        implementation = synthesize_inspect_refusal_implementation(
            bounded_request,
            reply=reply,
        )
        return finish(ExecutorResult.success(
            report=build_report(implementation),
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
        # RRSYN2-2: a failed implement phase that closed a durable turn must
        # keep that turn in the report.  build_report() with no implementation
        # is why threaded failures published evidence.implementation={} and a
        # blank lineage manifest.
        retained = getattr(exc, "implementation_result", None)
        retained_implementation = (
            retained if isinstance(retained, ImplementationResult) else None
        )
        return finish(ExecutorResult.failure(
            kind=failure_kind,
            stage=stage,
            message=str(exc),
            report=build_report(retained_implementation),
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
    "coerce_declared_interaction_lane",
    "inspect_named_runtime_absences",
    "run_threaded_executor",
    "synthesize_inspect_refusal_implementation",
    "typed_refusal_contract",
]
