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
from .refusal_evidence import (
    FrozenRefusalLedger,
    _authority_content_digest_for_observations,
    authority_generation,
    class_absence_record,
    evidence_id_matches_record,
    feature_absence_record,
    evidence_record_matches_authority,
    frozen_ledger_matches_authority,
    validate_evidence_ids,
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


class _FrozenSchemaAuthority:
    """Memoize one provider's observations for a single inspect turn."""

    def __init__(self, source: Any) -> None:
        self.source = source
        self.__capture_capability = object()
        self._observations: dict[str, Any] = {}
        self.content_digest = getattr(source, "content_digest", None)
        self.source_identity = id(source)
        self.source_generation = authority_generation(source)

    def _capture_capability(self) -> object:
        """Return the owner-bound mint capability to the ledger constructor."""
        return self.__capture_capability

    def capture_generation(self, class_types: tuple[str, ...]) -> str:
        if self.source_generation is not None:
            return self.source_generation
        bounded = None
        if callable(getattr(self.source, "get_schema", None)):
            bounded = _authority_content_digest_for_observations(
                {
                    class_type: self._observations.get(class_type, _LOOKUP_UNAVAILABLE)
                    for class_type in class_types
                }
            )
        if bounded is not None:
            return bounded
        return f"identity:{self.source_identity}"

    def get_schema(self, class_type: str) -> Any:
        if class_type not in self._observations:
            getter = getattr(self.source, "get_schema", None)
            if not callable(getter) and callable(self.source):
                getter = self.source
            if not callable(getter):
                self._observations[class_type] = _LOOKUP_UNAVAILABLE
            else:
                try:
                    self._observations[class_type] = getter(class_type)
                except Exception:  # noqa: BLE001 - authority lookup fails closed
                    self._observations[class_type] = _LOOKUP_UNAVAILABLE
        return self._observations[class_type]

    def schemas(self) -> Mapping[str, Any]:
        getter = getattr(self.source, "schemas", None)
        if not callable(getter):
            return {}
        try:
            result = getter()
        except Exception:  # noqa: BLE001 - authority listing fails closed
            return {}
        return result if isinstance(result, Mapping) else {}

    def snapshot(self) -> Mapping[str, Any]:
        return dict(self._observations)

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
    "add",
    "change",
    "create",
    "make",
    "use",
    "want",
    "need",
    "install",
    "swap",
    "replace",
    "switch",
    "set",
    "keep",
    "existing",
    "current",
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
    features = tuple(
        item for item in (getattr(request, "expected_no_candidate_absent_features", ()) or ())
        if isinstance(item, Mapping)
    )
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
    # Benchmark/production callers provide the exact expected set.  Do not
    # manufacture a secret set from sentence-initial capitalization; that set
    # was never shown to the model and cannot be a complete ledger.
    if not declared:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", query):
            if token in candidates:
                continue
            folded = re.sub(r"[^a-z0-9]", "", token.lower())
            if folded in _GENERIC_DOMAIN_TOKENS:
                continue
            if any(ch.isupper() for ch in token):
                candidates.append(token)
    present = {item.casefold() for item in _graph_class_types(request.graph)}
    lookup = schema_lookup or _default_schema_lookup
    missing: list[str] = []

    def resolve_schema(name: str) -> tuple[str, Any]:
        """Resolve declared spelling to the provider's canonical class name."""
        try:
            getter = getattr(lookup, "get_schema", None)
            if not callable(getter) and callable(lookup):
                getter = lookup
            schema = getter(name) if callable(getter) else _LOOKUP_UNAVAILABLE
        except Exception:
            return name, _LOOKUP_UNAVAILABLE
        if schema is not None and schema is not _LOOKUP_UNAVAILABLE:
            return name, schema
        schemas = getattr(lookup, "schemas", None)
        if not callable(schemas):
            return name, schema
        try:
            available = schemas()
        except Exception:
            return name, _LOOKUP_UNAVAILABLE
        if not isinstance(available, Mapping):
            return name, schema
        canonical = next(
            (str(key) for key in available if str(key).casefold() == name.casefold()),
            name,
        )
        if canonical == name:
            return name, schema
        try:
            getter = getattr(lookup, "get_schema", None)
            if not callable(getter) and callable(lookup):
                getter = lookup
            return canonical, getter(canonical) if callable(getter) else _LOOKUP_UNAVAILABLE
        except Exception:
            return canonical, _LOOKUP_UNAVAILABLE

    for name in candidates:
        if name.casefold() in present:
            continue
        if name not in declared and not _query_names_class(query, name):
            continue
        canonical, schema = resolve_schema(name)
        if schema is _LOOKUP_UNAVAILABLE:
            continue
        if schema is None:
            missing.append(canonical)
    return tuple(missing)


def inspect_refusal_evidence_ledger(
    request: ExecutorRequest,
    *,
    schema_lookup: Callable[[str], Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Freeze the exact class-absence ledger shown to the threaded model."""
    provider = _FrozenSchemaAuthority(schema_lookup or _default_schema_lookup)
    ledger = {
        record["evidence_id"]: record
        for class_type in inspect_named_runtime_absences(
            request, schema_lookup=provider
        )
        for record in (
            class_absence_record(request.graph, provider, class_type),
        )
    }
    graph_class_names = _graph_class_types(request.graph)
    graph_classes = {item.casefold() for item in graph_class_names}
    get_schema = getattr(provider, "get_schema", None)
    if not callable(get_schema) and callable(provider):
        get_schema = provider
    for feature in getattr(request, "expected_no_candidate_absent_features", ()) or ():
        if not isinstance(feature, Mapping):
            continue
        for check in feature.get("checks", ()) or ():
            if not isinstance(check, Mapping):
                continue
            class_type = str(check.get("class_type") or "").strip()
            member_kind = str(check.get("member_kind") or "").strip()
            member = str(check.get("member") or "").strip()
            if not class_type or member_kind not in {"input", "widget", "output"} or not member:
                continue
            canonical_class_type = next(
                (item for item in graph_class_names if item.casefold() == class_type.casefold()),
                class_type,
            )
            if canonical_class_type.casefold() not in graph_classes or not callable(get_schema):
                continue
            try:
                schema = get_schema(canonical_class_type)
            except Exception:  # noqa: BLE001 - unavailable authority fails closed
                continue
            if schema is None or schema is _LOOKUP_UNAVAILABLE:
                continue
            if member_kind == "output":
                names = {
                    str(getattr(item, "name", None) or getattr(item, "type", ""))
                    for item in (getattr(schema, "outputs", None) or ())
                }
            else:
                names = {str(name) for name in (getattr(schema, "inputs", None) or {})}
            if member in names:
                continue
            record = feature_absence_record(
                request.graph,
                provider,
                class_type=canonical_class_type,
                member_kind=member_kind,
                member=member,
                available_members=sorted(names),
            )
            ledger[record["evidence_id"]] = record
    source_classes = tuple(
        str(record.get("class_type"))
        for record in ledger.values()
        if isinstance(record.get("class_type"), str)
    )
    return FrozenRefusalLedger._from_capture(
        ledger,
        graph=request.graph,
        schema_snapshot=provider.snapshot(),
        schema_content_digest=provider.content_digest,
        source_identity=provider.source_identity,
        source_generation=provider.capture_generation(source_classes),
        owner=provider,
    )


def synthesize_inspect_refusal_implementation(
    request: ExecutorRequest,
    *,
    reply: str,
    schema_lookup: Callable[[str], Any] | None = None,
    frozen_ledger: Mapping[str, Mapping[str, Any]] | None = None,
) -> ImplementationResult | None:
    """Validate a model-selected typed refusal against inspect evidence.

    The schema lookup is deterministic evidence collection only.  A plain
    inspect reply, or a generic/no-op-shaped reply, is never promoted.  The
    model must emit the typed JSON refusal and cite the complete absence set.
    """
    frozen_authority_valid = True
    if frozen_ledger is not None:
        frozen_authority_valid = isinstance(frozen_ledger, FrozenRefusalLedger) and frozen_ledger_matches_authority(
            frozen_ledger,
            graph=request.graph,
            authority_source=(
                schema_lookup
                if schema_lookup is not None
                else getattr(frozen_ledger, "authority_source", None)
            ),
        )
        ledger = (
            {str(key): dict(value) for key, value in frozen_ledger.items()}
            if isinstance(frozen_ledger, Mapping)
            else {}
        )
    else:
        ledger = inspect_refusal_evidence_ledger(request, schema_lookup=schema_lookup)
    missing = tuple(
        str(record.get("class_type"))
        for record in ledger.values()
        if record.get("kind") == "class_absence"
    )
    if not ledger:
        return None
    from vibecomfy.executor.prompts import _extract_json_object, parse_reply_payload

    try:
        payload = parse_reply_payload(reply)
    except (TypeError, ValueError):
        payload = None
    raw_object: Mapping[str, Any] | None = None
    if str(reply).lstrip().startswith("{"):
        try:
            candidate = _extract_json_object(str(reply))
        except (TypeError, ValueError):
            candidate = None
        if isinstance(candidate, dict):
            raw_object = candidate
    allowed_fields = {
        "kind", "missing_classes", "feature_absences", "evidence",
        "reply", "message", "question", "clarification_question",
    }
    strict_shape_ok = raw_object is None or not (
        set(raw_object) - allowed_fields
        or not isinstance(raw_object.get("evidence", []), list)
        or not all(isinstance(item, str) and item.strip() for item in raw_object.get("evidence", []))
        or len(set(raw_object.get("evidence", []))) != len(raw_object.get("evidence", []))
        or not isinstance(raw_object.get("feature_absences", []), list)
        or any(
            not isinstance(item, dict)
            or set(item) != {"evidence_id"}
            or not isinstance(item.get("evidence_id"), str)
            for item in raw_object.get("feature_absences", [])
        )
        or len({item.get("evidence_id") for item in raw_object.get("feature_absences", [])})
        != len(raw_object.get("feature_absences", []))
    )
    typed_payload = bool(
        payload
        and payload.is_typed_refusal
        and payload.evidence
        and strict_shape_ok
    )
    claimed = tuple(payload.missing_classes) if payload is not None else ()
    claimed_feature_ids = (
        [
            item.get("evidence_id")
            for item in payload.feature_absences
            if isinstance(item, Mapping)
        ]
        if payload is not None
        else []
    )
    records = validate_evidence_ids(payload.evidence, ledger) if typed_payload else None
    class_records = tuple(
        record for record in (records or ()) if record.get("kind") == "class_absence"
    )
    expected_feature_ids = {
        str(key)
        for key, record in ledger.items()
        if record.get("kind") == "feature_absence"
    }
    feature_ids_valid = (
        validate_evidence_ids(claimed_feature_ids, ledger) is not None
        if expected_feature_ids
        else not claimed_feature_ids
    )
    valid = bool(
        typed_payload
        and records is not None
        and frozen_authority_valid
        and {item.casefold() for item in claimed}
        == {item.casefold() for item in missing}
        and len(claimed) == len(missing)
        and {
            str(record.get("class_type")).casefold() for record in class_records
        } == {item.casefold() for item in missing}
        and all(
            (
                evidence_id_matches_record(record)
                if frozen_ledger is not None
                else evidence_record_matches_authority(record, request.graph, schema_lookup)
            )
            for record in (records or ())
        )
        and set(claimed_feature_ids)
        == expected_feature_ids
        and feature_ids_valid
    )
    from vibecomfy.comfy_nodes.agent.contracts import (
        missing_runtime_classes_from_report,
        promote_requires_custom_nodes_outcome,
    )

    feature_records = [
        record for record in ledger.values() if record.get("kind") == "feature_absence"
    ]
    blocker = {
        "reason": "structural_feature_absent" if feature_records and not missing else "named_class_absent_from_schema",
        "missing_runtime_classes": list(missing),
        "absence_evidence": list(ledger.values()),
        "evidence_refs": list(ledger),
    }
    if feature_records:
        blocker["feature_absences"] = [
            {"feature": record.get("feature"), "checks": [record]}
            for record in feature_records
        ]
    blocker_report = {
        "authoring_blocker": {
            **blocker,
        },
        "graph_unchanged": True,
    }
    outcome = {"kind": payload.kind, "message": payload.text} if valid and payload is not None else {"kind": "noop", "message": "The refusal could not be authorized from the frozen evidence ledger."}
    if valid and payload is not None and payload.kind == "requires_custom_nodes":
        outcome = promote_requires_custom_nodes_outcome(
            outcome,
            missing_classes=missing_runtime_classes_from_report(blocker_report),
        )
    if valid and payload is not None:
        outcome["evidence"] = list(payload.evidence)
    else:
        blocker_report["authoring_blocker"]["refusal_validation"] = {
            "authorized": False,
            "reason": "invalid_or_missing_bound_evidence",
        }
    return ImplementationResult(
        message=(
            payload.text
            if payload is not None and (valid or not str(reply).lstrip().startswith("{"))
            else "The requested refusal could not be authorized from the frozen runtime evidence."
        ),
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
        refusal_ledger = inspect_refusal_evidence_ledger(bounded_request)
        try:
            reply = kernel.run_inspect_reply(
                bounded_request,
                spec,
                plan=plan,
                host_ports=host_ports,
                refusal_ledger=refusal_ledger,
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
            frozen_ledger=refusal_ledger,
        )
        return finish(ExecutorResult.success(
            report=build_report(implementation),
            graph=None,
            reply=implementation.message if implementation is not None else reply,
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
        # Non-applied rows: original graph remains authoritative internally,
        # but it is never an ExecutorResult graph/candidate.  Keep the request
        # graph only for reply grounding below; public serialization must have
        # no graph carrier for a rejected/no-candidate terminal.
        if getattr(projection, "terminal_state", None) in {
            "authority_rejected",
            "infra_failure",
            "clarify",
            "no_candidate",
            "no_op",
            "undetermined",
        }:
            graph = None

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
    "inspect_refusal_evidence_ledger",
    "run_threaded_executor",
    "synthesize_inspect_refusal_implementation",
    "typed_refusal_contract",
]
