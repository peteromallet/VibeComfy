// Canonical browser boundary for the persisted candidate transaction aggregate.
// UI phase is presentation only; available_actions on this aggregate governs
// Apply/Reject/rollback/finalize availability.

import { normalizeDeltaEnvelope } from "./canonical_delta.js";

export const CANDIDATE_TRANSACTION_CONTRACT_VERSION = "candidate_transaction_v1";

export const TRANSACTION_STATE = Object.freeze({
  CANDIDATE_READY: "candidate_ready",
  PREPARED: "prepared",
  CANVAS_VERIFIED: "canvas_verified",
  FINALIZED: "finalized",
  DISCARDED: "discarded",
  ROLLBACK_COMPLETE: "rollback_complete",
  RECOVERABLE_ERROR: "recoverable_error",
  SUPERSEDED: "superseded",
});

const CANONICAL_STATES = new Set(Object.values(TRANSACTION_STATE));
const LEGACY_STATE_ADAPTER = Object.freeze({
  candidate: TRANSACTION_STATE.CANDIDATE_READY,
  review_bound: TRANSACTION_STATE.CANDIDATE_READY,
  apply_prepared: TRANSACTION_STATE.PREPARED,
  rollback_prepared: TRANSACTION_STATE.PREPARED,
  accepted: TRANSACTION_STATE.FINALIZED,
  rejected: TRANSACTION_STATE.DISCARDED,
  rolled_back: TRANSACTION_STATE.ROLLBACK_COMPLETE,
  cancelled: TRANSACTION_STATE.SUPERSEDED,
  unknown: TRANSACTION_STATE.SUPERSEDED,
});

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function clonePlainData(value) {
  if (Array.isArray(value)) return value.map(clonePlainData);
  if (isObject(value)) {
    return Object.fromEntries(Object.entries(value).map(([key, entry]) => [key, clonePlainData(entry)]));
  }
  return value;
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (isObject(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function canonicalTransactionState(value) {
  if (typeof value !== "string") return null;
  if (CANONICAL_STATES.has(value)) return value;
  return LEGACY_STATE_ADAPTER[value] || null;
}

export function transactionAllows(transaction, action) {
  return Array.isArray(transaction?.available_actions)
    && transaction.available_actions.includes(action);
}

export function isLayoutAuthorityTransaction(transaction) {
  const normalized = normalizeCandidateTransaction(transaction);
  return Boolean(
    normalized
    && normalized.authority?.verification_kind === "layout_structural_noop"
    && normalized.authority?.replay_ok === true
    && normalized.authority?.candidate_matches === true,
  );
}

function canonicalActionsForState(state, resumeState = null) {
  const effective = state === TRANSACTION_STATE.RECOVERABLE_ERROR
    ? canonicalTransactionState(resumeState)
    : state;
  if (effective === TRANSACTION_STATE.CANDIDATE_READY) return ["apply", "reject"];
  if (effective === TRANSACTION_STATE.PREPARED) return ["rollback"];
  if (effective === TRANSACTION_STATE.CANVAS_VERIFIED) return ["finalize", "rollback"];
  return [];
}

export function normalizeCandidateTransaction(value) {
  if (!isObject(value)) return null;
  if (value.contract_version !== CANDIDATE_TRANSACTION_CONTRACT_VERSION) return null;
  const state = canonicalTransactionState(value.state);
  if (!state || !isObject(value.plan) || !isObject(value.hashes) || !isObject(value.authority)) return null;
  const envelope = normalizeDeltaEnvelope(value.plan.delta_ops_envelope, { strict: false });
  if (typeof value.plan.delta_hash !== "string" || !value.plan.delta_hash) return null;
  if (typeof value.plan_hash !== "string" || !value.plan_hash) return null;
  if (typeof value.hashes.candidate_graph_hash !== "string") return null;
  if (typeof value.hashes.candidate_structural_graph_hash !== "string") return null;
  const actions = Array.isArray(value.available_actions)
    ? [...new Set(value.available_actions.filter((action) => typeof action === "string"))]
    : [];
  const expectedActions = canonicalActionsForState(state, value.resume_state);
  const actionsMatch = actions.length === expectedActions.length
    && actions.every((action, index) => action === expectedActions[index]);
  // A fail-closed candidate may intentionally advertise no actions. Every
  // other aggregate must match the canonical action vocabulary exactly.
  if (!actionsMatch && !(state === TRANSACTION_STATE.CANDIDATE_READY && actions.length === 0)) {
    return null;
  }
  return Object.freeze({
    ...clonePlainData(value),
    state,
    resume_state: canonicalTransactionState(value.resume_state),
    plan: {
      ...clonePlainData(value.plan),
      delta_ops_envelope: clonePlainData(envelope),
      op_count: envelope.ops.length,
    },
    available_actions: actions,
  });
}

export function readCandidateTransaction(value) {
  const candidates = [
    value?.candidate_transaction,
    value?.candidateTransaction,
    value?.raw?.candidate_transaction,
    value?.raw?.candidateTransaction,
    value?.latest_candidate?.candidate_transaction,
    value?.latestCandidate?.candidateTransaction,
    value?.latest_turn_lifecycle?.candidate_transaction,
    value?.latestTurnLifecycle?.candidateTransaction,
  ];
  for (const candidate of candidates) {
    try {
      const normalized = normalizeCandidateTransaction(candidate);
      if (normalized) return normalized;
    } catch (_error) {
      // A malformed aggregate is not downgraded to legacy browser state.
      return null;
    }
  }
  return null;
}

export function resolvePreparedMutationPlan(candidateTransaction, preparedTransaction) {
  const candidate = normalizeCandidateTransaction(candidateTransaction);
  const prepared = normalizeCandidateTransaction(preparedTransaction);
  if (!candidate || !prepared) throw new Error("Missing canonical candidate transaction aggregate.");
  if (prepared.state !== TRANSACTION_STATE.PREPARED) {
    throw new Error(`Prepare returned transaction state ${String(prepared.state)}.`);
  }
  if (candidate.plan_hash !== prepared.plan_hash) throw new Error("Prepared plan hash differs from candidate authority.");
  if (candidate.plan.delta_hash !== prepared.plan.delta_hash) throw new Error("Prepared delta hash differs from candidate authority.");
  if (canonicalJson(candidate.plan.delta_ops_envelope) !== canonicalJson(prepared.plan.delta_ops_envelope)) {
    throw new Error("Prepared operations differ from persisted candidate operations.");
  }
  const candidateVerificationKind = candidate.authority?.verification_kind || "delta_replay";
  const preparedVerificationKind = prepared.authority?.verification_kind || "delta_replay";
  if (candidateVerificationKind !== preparedVerificationKind) {
    throw new Error("Prepared verification mode differs from candidate authority.");
  }
  return {
    envelope: clonePlainData(prepared.plan.delta_ops_envelope),
    deltaOps: clonePlainData(prepared.plan.delta_ops_envelope.ops),
    deltaHash: prepared.plan.delta_hash,
    verificationKind: preparedVerificationKind,
  };
}

export function auditLandedMutationPlan(deltaOps, appliedPlan) {
  if (!Array.isArray(deltaOps) || !Array.isArray(appliedPlan)) {
    throw new Error("Landed operation audit requires persisted ops and an applied plan.");
  }
  const covered = new Set();
  const primaryCounts = new Map();
  let lastSourceIndex = -1;
  for (const step of appliedPlan) {
    const index = step?.source_op_index;
    if (!Number.isInteger(index) || index < 0 || index >= deltaOps.length) {
      throw new Error("Landed mutation contains an operation without persisted provenance.");
    }
    const persistedKind = deltaOps[index]?.op;
    if (step.source_op_kind !== persistedKind) {
      throw new Error(`Landed operation provenance differs at persisted op ${index}.`);
    }
    if (index < lastSourceIndex) {
      throw new Error("Landed mutation order differs from persisted operation order.");
    }
    lastSourceIndex = index;
    if (step.derivedFromAddNode === true && persistedKind !== "add_node") {
      throw new Error(`Only add_node may produce derived landed steps (persisted op ${index}).`);
    }
    if (step.derivedFromAddNode !== true && step.op !== persistedKind) {
      throw new Error(`Landed operation differs from persisted op ${index}.`);
    }
    if (step.derivedFromAddNode !== true) {
      primaryCounts.set(index, (primaryCounts.get(index) || 0) + 1);
    }
    covered.add(index);
  }
  if (covered.size !== deltaOps.length) {
    throw new Error("One or more persisted operations did not land on the canvas.");
  }
  if (deltaOps.some((_op, index) => primaryCounts.get(index) !== 1)) {
    throw new Error("Persisted operations must each land exactly once.");
  }
  return Object.freeze({
    ok: true,
    persisted_op_count: deltaOps.length,
    landed_step_count: appliedPlan.length,
    covered_op_indexes: [...covered].sort((left, right) => left - right),
  });
}

export function boundedBrowserTransactionError(error, substage, options = {}) {
  const message = String(error?.message || error || "Unknown transaction error").slice(0, 2048);
  const stack = typeof error?.stack === "string"
    ? error.stack.split("\n").slice(0, 8).map((line) => line.trim().slice(0, 512))
    : [];
  return {
    stage: "candidate_transaction",
    substage: String(substage || "unknown").slice(0, 128),
    message,
    stack,
    recoverable: options.recoverable !== false,
    resume_state: canonicalTransactionState(options.resumeState),
  };
}
