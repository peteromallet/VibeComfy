"""Canonical candidate-transaction aggregate and persisted schema witness.

The aggregate is the authority boundary shared by candidate publication,
prepare, browser mutation, finalization, rollback, and rehydration.  Mutable
session indexes are projections; the immutable candidate artifact plus its
append-only lifecycle events are the durable source of truth.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec, schema_for

CANDIDATE_TRANSACTION_CONTRACT_VERSION = "candidate_transaction_v1"
SCHEMA_WITNESS_CONTRACT_VERSION = "candidate_schema_witness_v1"
CANDIDATE_TRANSACTION_FILENAME = "candidate_transaction.json"

CandidateTransactionState = Literal[
    "candidate_ready",
    "prepared",
    "canvas_verified",
    "finalized",
    "discarded",
    "rollback_complete",
    "recoverable_error",
    "superseded",
]

CANONICAL_TRANSACTION_STATES: frozenset[str] = frozenset(
    {
        "candidate_ready",
        "prepared",
        "canvas_verified",
        "finalized",
        "discarded",
        "rollback_complete",
        "recoverable_error",
        "superseded",
    }
)
TERMINAL_TRANSACTION_STATES: frozenset[str] = frozenset(
    {"finalized", "discarded", "rollback_complete", "superseded"}
)
RECOVERABLE_TRANSACTION_STATES: frozenset[str] = frozenset(
    {"candidate_ready", "prepared", "canvas_verified", "recoverable_error"}
)

_LEGACY_STATE_ADAPTER: Mapping[str, str] = {
    "candidate": "candidate_ready",
    "review_bound": "candidate_ready",
    "apply_prepared": "prepared",
    "rollback_prepared": "prepared",
    "accepted": "finalized",
    "rejected": "discarded",
    "rolled_back": "rollback_complete",
    "cancelled": "superseded",
    "unknown": "superseded",
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_transaction_state(value: Any) -> str | None:
    """Return the canonical state, adapting read-only historical values."""
    if not isinstance(value, str):
        return None
    if value in CANONICAL_TRANSACTION_STATES:
        return value
    return _LEGACY_STATE_ADAPTER.get(value)


def available_actions_for_state(
    state: Any,
    *,
    resume_state: Any = None,
) -> tuple[str, ...]:
    canonical = canonical_transaction_state(state)
    if canonical == "recoverable_error":
        canonical = canonical_transaction_state(resume_state)
    if canonical == "candidate_ready":
        return ("apply", "reject")
    if canonical == "prepared":
        # A reload cannot prove whether an unrecorded local canvas mutation
        # happened.  Recovery is rollback-only until fresh verification exists.
        return ("rollback",)
    if canonical == "canvas_verified":
        return ("finalize", "rollback")
    return ()


def _graph_class_types(graph: Mapping[str, Any] | None) -> set[str]:
    result: set[str] = set()

    def visit(scope: Mapping[str, Any]) -> None:
        nodes = scope.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, Mapping):
                    continue
                class_type = node.get("type") or node.get("class_type")
                if isinstance(class_type, str) and class_type:
                    result.add(class_type)
        definitions = scope.get("definitions")
        if isinstance(definitions, Mapping):
            for definition in definitions.values():
                if isinstance(definition, Mapping):
                    visit(definition)

    if isinstance(graph, Mapping):
        visit(graph)
    return result


def _delta_class_types(delta_envelope: Mapping[str, Any] | None) -> set[str]:
    result: set[str] = set()
    ops = delta_envelope.get("ops") if isinstance(delta_envelope, Mapping) else None
    for op in ops if isinstance(ops, list) else ():
        if not isinstance(op, Mapping):
            continue
        class_type = op.get("class_type")
        if isinstance(class_type, str) and class_type:
            result.add(class_type)
    return result


def _json_safe(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        return repr(value)[:512]


def _input_spec_payload(spec: Any) -> dict[str, Any]:
    return {
        "type": getattr(spec, "type", None),
        "required": bool(getattr(spec, "required", False)),
        "default": _json_safe(getattr(spec, "default", None)),
        "choices": _json_safe(getattr(spec, "choices", None)),
        "min": getattr(spec, "min", None),
        "max": getattr(spec, "max", None),
    }


def _output_spec_payload(spec: Any) -> dict[str, Any]:
    return {
        "type": getattr(spec, "type", None),
        "name": getattr(spec, "name", None),
    }


def _schema_payload(class_type: str, schema: Any) -> dict[str, Any]:
    inputs = getattr(schema, "inputs", {})
    outputs = getattr(schema, "outputs", [])
    provenance_fields = (
        "source_provider",
        "source_path",
        "source_cache_path",
        "source_server_url",
        "source_package",
        "source_version",
        "source_hash",
        "confidence",
        "conflicts",
        "ignored_evidence",
    )
    return {
        "class_type": class_type,
        "pack": getattr(schema, "pack", None),
        "inputs": {
            str(name): _input_spec_payload(spec)
            for name, spec in sorted(
                inputs.items() if isinstance(inputs, Mapping) else (),
                key=lambda item: str(item[0]),
            )
        },
        "outputs": [
            _output_spec_payload(spec)
            for spec in outputs if spec is not None
        ],
        "provenance": {
            field: _json_safe(getattr(schema, field, None))
            for field in provenance_fields
        },
    }


def build_schema_witness(
    *,
    schema_provider: Any,
    submit_graph: Mapping[str, Any] | None,
    candidate_payload: Mapping[str, Any] | None,
    delta_envelope: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Freeze every schema that can affect replay of this candidate."""
    class_types = (
        _graph_class_types(submit_graph)
        | _graph_class_types(candidate_payload)
        | _delta_class_types(delta_envelope)
    )
    schemas: dict[str, Any] = {}
    missing: list[str] = []
    for class_type in sorted(class_types):
        schema = schema_for(schema_provider, class_type)
        if schema is None:
            missing.append(class_type)
            continue
        schemas[class_type] = _schema_payload(class_type, schema)
    body = {
        "contract_version": SCHEMA_WITNESS_CONTRACT_VERSION,
        "provider_mode": "none" if schema_provider is None else "frozen",
        "schemas": schemas,
        "missing_class_types": missing,
    }
    return {**body, "witness_hash": content_hash(body)}


def validate_schema_witness(witness: Any) -> tuple[bool, str | None]:
    if not isinstance(witness, Mapping):
        return False, "missing_schema_witness"
    if witness.get("contract_version") != SCHEMA_WITNESS_CONTRACT_VERSION:
        return False, "unsupported_schema_witness"
    body = {
        "contract_version": witness.get("contract_version"),
        "provider_mode": witness.get("provider_mode"),
        "schemas": witness.get("schemas"),
        "missing_class_types": witness.get("missing_class_types"),
    }
    if not isinstance(body["schemas"], Mapping) or not isinstance(
        body["missing_class_types"], list
    ):
        return False, "malformed_schema_witness"
    if body["provider_mode"] not in {"none", "frozen"}:
        return False, "malformed_schema_provider_mode"
    if witness.get("witness_hash") != content_hash(body):
        return False, "schema_witness_hash_mismatch"
    return True, None


class FrozenSchemaProvider:
    """Schema provider reconstructed exclusively from a persisted witness."""

    def __init__(self, witness: Mapping[str, Any]) -> None:
        ok, error = validate_schema_witness(witness)
        if not ok:
            raise ValueError(error or "invalid_schema_witness")
        self._schemas: dict[str, NodeSchema] = {}
        raw_schemas = witness.get("schemas")
        for class_type, raw in (
            raw_schemas.items() if isinstance(raw_schemas, Mapping) else ()
        ):
            if not isinstance(class_type, str) or not isinstance(raw, Mapping):
                continue
            raw_inputs = raw.get("inputs")
            inputs: dict[str, InputSpec] = {}
            for name, spec in (
                raw_inputs.items() if isinstance(raw_inputs, Mapping) else ()
            ):
                if not isinstance(spec, Mapping):
                    continue
                choices = spec.get("choices")
                inputs[str(name)] = InputSpec(
                    type=spec.get("type") if isinstance(spec.get("type"), str) else None,
                    required=spec.get("required") is True,
                    default=spec.get("default"),
                    choices=list(choices) if isinstance(choices, list) else None,
                    min=spec.get("min") if isinstance(spec.get("min"), (int, float)) else None,
                    max=spec.get("max") if isinstance(spec.get("max"), (int, float)) else None,
                )
            raw_outputs = raw.get("outputs")
            outputs = [
                OutputSpec(
                    type=item.get("type") if isinstance(item.get("type"), str) else None,
                    name=item.get("name") if isinstance(item.get("name"), str) else None,
                )
                for item in raw_outputs if isinstance(item, Mapping)
            ] if isinstance(raw_outputs, list) else []
            provenance = raw.get("provenance")
            provenance = provenance if isinstance(provenance, Mapping) else {}
            self._schemas[class_type] = NodeSchema(
                class_type=class_type,
                pack=raw.get("pack") if isinstance(raw.get("pack"), str) else None,
                inputs=inputs,
                outputs=outputs,
                source_provider=str(provenance.get("source_provider") or "persisted_witness"),
                source_path=provenance.get("source_path") if isinstance(provenance.get("source_path"), str) else None,
                source_cache_path=provenance.get("source_cache_path") if isinstance(provenance.get("source_cache_path"), str) else None,
                source_server_url=None,
                source_package=provenance.get("source_package") if isinstance(provenance.get("source_package"), str) else None,
                source_version=provenance.get("source_version") if isinstance(provenance.get("source_version"), str) else None,
                source_hash=provenance.get("source_hash") if isinstance(provenance.get("source_hash"), str) else None,
                confidence=float(provenance.get("confidence", 1.0)) if isinstance(provenance.get("confidence"), (int, float)) else 1.0,
                conflicts=tuple(str(item) for item in provenance.get("conflicts", []) if isinstance(item, str)),
                ignored_evidence=tuple(str(item) for item in provenance.get("ignored_evidence", []) if isinstance(item, str)),
            )

    def get(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.get(class_type)

    def schemas(self) -> dict[str, NodeSchema]:
        return dict(self._schemas)


def schema_provider_from_witness(witness: Mapping[str, Any]) -> Any:
    """Reconstruct the exact provider mode used when the plan was authored."""
    ok, error = validate_schema_witness(witness)
    if not ok:
        raise ValueError(error or "invalid_schema_witness")
    if witness.get("provider_mode") == "none":
        return None
    return FrozenSchemaProvider(witness)


def schema_provenance_summary(witness: Mapping[str, Any]) -> dict[str, Any]:
    schemas = witness.get("schemas")
    sources: dict[str, str] = {}
    if isinstance(schemas, Mapping):
        for class_type, raw in schemas.items():
            provenance = raw.get("provenance") if isinstance(raw, Mapping) else None
            source = provenance.get("source_provider") if isinstance(provenance, Mapping) else None
            sources[str(class_type)] = str(source or "unknown")
    return {
        "contract_version": witness.get("contract_version"),
        "provider_mode": witness.get("provider_mode"),
        "witness_hash": witness.get("witness_hash"),
        "class_count": len(sources),
        "missing_class_types": list(witness.get("missing_class_types", []))[:64]
        if isinstance(witness.get("missing_class_types"), list)
        else [],
        "sources": sources,
    }


def build_candidate_transaction(
    *,
    session_id: str,
    turn_id: str,
    plan_hash: str,
    delta_ops_envelope: Mapping[str, Any],
    delta_hash: str,
    submit_graph_hash: str | None,
    submit_structural_graph_hash: str | None,
    candidate_graph_hash: str,
    candidate_structural_graph_hash: str,
    authority_receipt_hash: str,
    schema_witness: Mapping[str, Any],
    replay_ok: bool,
    candidate_matches: bool,
    applyable: bool,
    verification_kind: str = "delta_replay",
    state: str = "candidate_ready",
) -> dict[str, Any]:
    canonical_state = canonical_transaction_state(state)
    if canonical_state is None:
        raise ValueError(f"Unknown candidate transaction state {state!r}.")
    actions = available_actions_for_state(canonical_state) if applyable else ()
    return {
        "contract_version": CANDIDATE_TRANSACTION_CONTRACT_VERSION,
        "state": canonical_state,
        "resume_state": None,
        "session_id": session_id,
        "turn_id": turn_id,
        "plan_hash": plan_hash,
        "generation": None,
        "lease_nonce": None,
        "plan": {
            "schema_version": delta_ops_envelope.get("schema_version"),
            "delta_ops_envelope": dict(delta_ops_envelope),
            "delta_hash": delta_hash,
            "op_count": len(delta_ops_envelope.get("ops", []))
            if isinstance(delta_ops_envelope.get("ops"), list)
            else 0,
            "schema_provenance": schema_provenance_summary(schema_witness),
        },
        "hashes": {
            "submit_graph_hash": submit_graph_hash,
            "submit_structural_graph_hash": submit_structural_graph_hash,
            "candidate_graph_hash": candidate_graph_hash,
            "candidate_structural_graph_hash": candidate_structural_graph_hash,
            "authority_receipt_hash": authority_receipt_hash,
        },
        "authority": {
            "replay_ok": replay_ok,
            "candidate_matches": candidate_matches,
            "verification_kind": verification_kind,
            "schema_witness_hash": schema_witness.get("witness_hash"),
        },
        "available_actions": list(actions),
        "terminal": canonical_state in TERMINAL_TRANSACTION_STATES,
        "last_error": None,
    }


def project_transaction_state(
    candidate: Mapping[str, Any],
    *,
    state: str,
    generation: int | None = None,
    lease_nonce: str | None = None,
    last_error: Mapping[str, Any] | None = None,
    resume_state: str | None = None,
) -> dict[str, Any]:
    projected = json.loads(json.dumps(candidate))
    canonical_state = canonical_transaction_state(state)
    if canonical_state is None:
        raise ValueError(f"Unknown candidate transaction state {state!r}.")
    projected["state"] = canonical_state
    projected["resume_state"] = canonical_transaction_state(resume_state)
    projected["generation"] = generation
    projected["lease_nonce"] = lease_nonce
    projected["last_error"] = dict(last_error) if isinstance(last_error, Mapping) else None
    projected["available_actions"] = list(
        available_actions_for_state(canonical_state, resume_state=resume_state)
    )
    projected["terminal"] = canonical_state in TERMINAL_TRANSACTION_STATES
    return projected


def validate_candidate_transaction(value: Any) -> tuple[bool, str | None]:
    if not isinstance(value, Mapping):
        return False, "missing_candidate_transaction"
    if value.get("contract_version") != CANDIDATE_TRANSACTION_CONTRACT_VERSION:
        return False, "unsupported_candidate_transaction"
    state = canonical_transaction_state(value.get("state"))
    if state is None:
        return False, "invalid_candidate_transaction_state"
    plan = value.get("plan")
    hashes = value.get("hashes")
    authority = value.get("authority")
    if not all(isinstance(item, Mapping) for item in (plan, hashes, authority)):
        return False, "malformed_candidate_transaction"
    envelope = plan.get("delta_ops_envelope")
    if not isinstance(envelope, Mapping) or not isinstance(envelope.get("ops"), list):
        return False, "missing_persisted_delta_plan"
    if plan.get("delta_hash") != content_hash(envelope):
        return False, "persisted_delta_hash_mismatch"
    required_hashes = ("candidate_graph_hash", "candidate_structural_graph_hash", "authority_receipt_hash")
    if any(not isinstance(hashes.get(field), str) or not hashes.get(field) for field in required_hashes):
        return False, "missing_candidate_transaction_hash"
    actions = value.get("available_actions")
    if not isinstance(actions, list) or any(not isinstance(action, str) for action in actions):
        return False, "malformed_candidate_transaction_actions"
    expected_actions = list(
        available_actions_for_state(state, resume_state=value.get("resume_state"))
    )
    if actions != expected_actions and not (state == "candidate_ready" and actions == []):
        return False, "candidate_transaction_action_state_mismatch"
    return True, None


def bounded_error_diagnostic(
    error: BaseException | str,
    *,
    stage: str,
    substage: str,
    recoverable: bool,
    resume_state: str | None = None,
) -> dict[str, Any]:
    message = str(error)
    stack: list[str] = []
    if isinstance(error, BaseException) and error.__traceback__ is not None:
        import traceback

        stack = [line.strip()[:512] for line in traceback.format_tb(error.__traceback__, limit=8)]
    return {
        "stage": stage[:64],
        "substage": substage[:128],
        "message": message[:2048],
        "stack": stack[:8],
        "recoverable": bool(recoverable),
        "resume_state": canonical_transaction_state(resume_state),
    }


__all__ = [
    "CANONICAL_TRANSACTION_STATES",
    "CANDIDATE_TRANSACTION_CONTRACT_VERSION",
    "CANDIDATE_TRANSACTION_FILENAME",
    "CandidateTransactionState",
    "FrozenSchemaProvider",
    "RECOVERABLE_TRANSACTION_STATES",
    "SCHEMA_WITNESS_CONTRACT_VERSION",
    "TERMINAL_TRANSACTION_STATES",
    "available_actions_for_state",
    "bounded_error_diagnostic",
    "build_candidate_transaction",
    "build_schema_witness",
    "canonical_transaction_state",
    "content_hash",
    "project_transaction_state",
    "schema_provenance_summary",
    "schema_provider_from_witness",
    "validate_candidate_transaction",
    "validate_schema_witness",
]
