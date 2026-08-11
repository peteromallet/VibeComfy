// Canonical browser boundary for the persisted candidate transaction aggregate.
// UI phase is presentation only; available_actions on this aggregate governs
// Apply/Reject/rollback/finalize availability.

import { normalizeDeltaEnvelope } from "./canonical_delta.js";
import { deep_plain } from "./deep_plain.js";
import { canonicalSessionJsonString } from "./canonical_hash.js";
import { normalizeLayoutVerification } from "./layout_verification_contract.js";
import { classifyLegacyMigrationV1 } from "./legacy_migration_v1.js";
import { CANDIDATE_TRANSACTION_V2, PREPARED_AUTHORITY_V1, CANDIDATE_AUTHORITY_V0_LEGACY, validateCandidateTransactionV2, validatePreparedAuthorityV1, migrateLegacyCandidateAuthorityV0Legacy } from "./prepared_authority_v1.js";
export { CANDIDATE_TRANSACTION_V2, PREPARED_AUTHORITY_V1, CANDIDATE_AUTHORITY_V0_LEGACY, validateCandidateTransactionV2, validatePreparedAuthorityV1, migrateLegacyCandidateAuthorityV0Legacy } from "./prepared_authority_v1.js";

export const CANDIDATE_TRANSACTION_CONTRACT_VERSION = CANDIDATE_TRANSACTION_V2;

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

export function canonicalTransactionState(value) {
  if (typeof value !== "string") return null;
  if (CANONICAL_STATES.has(value)) return value;
  return LEGACY_STATE_ADAPTER[value] || null;
}

export function transactionAllows(transaction, action) {
  return Array.isArray(transaction?.available_actions)
    && transaction.available_actions.includes(action);
}

export function transactionAllowsRejectOrFailClosedDiscard(
  transaction,
  { rawTransaction = null, agentEditProtocol = null, candidatePresent = false } = {},
) {
  if (transactionAllows(transaction, "reject") || transactionAllows(transaction, "rollback")) {
    return true;
  }
  // Apply must never trust malformed authority. Reject is different: it only
  // discards server-held candidate state, and the reject endpoint rechecks the
  // session/turn/CAS fence. Keep invalid V2 candidates recoverably cancellable
  // instead of trapping the panel in AWAITING_REVIEW forever.
  return Boolean(
    candidatePresent
    && agentEditProtocol === "v2_delta"
    && isObject(rawTransaction)
    && rawTransaction.contract_version === CANDIDATE_TRANSACTION_V2,
  );
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
  // ── §M1.6: Legacy persisted authority migration at the load boundary ──────
  // A candidate_transaction_v2 envelope may carry a candidate_authority_v0_legacy
  // inner from a pre-strict-digest deployment. The v0_legacy inner is upgraded
  // to its strict v1 counterpart (sole effect: restoration_strategy.digest is
  // recomputed) BEFORE strict v2 validation runs. Malformed v1/v2 inners NEVER
  // carry a v0_legacy marker, so they cannot reach the migrator — they
  // fail-closed in validateCandidateTransactionV2. A structurally invalid
  // v0_legacy inner throws inside its migrator and is treated as fail-closed
  // here (returns null). No catch-all fallback. Candidate-ready transactions
  // that carry a prepared authority are rejected by strict v2 validation's
  // unexpected_prepared_authority check.
  const source = _migrateLegacyV0LegacyEnvelope(value);
  if (source === null) return null;
  const state = canonicalTransactionState(source.state);
  if (!state || !isObject(source.plan) || !isObject(source.hashes) || !isObject(source.authority)) return null;
  try { validateCandidateTransactionV2(source); } catch (_error) { return null; }
  const envelope = normalizeDeltaEnvelope(source.plan.delta_ops_envelope, { strict: false });
  if (typeof source.plan.delta_hash !== "string" || !source.plan.delta_hash) return null;
  if (typeof source.plan_hash !== "string" || !source.plan_hash) return null;
  if (typeof source.hashes.candidate_graph_hash !== "string") return null;
  if (typeof source.hashes.candidate_structural_graph_hash !== "string") return null;
  const rawLayoutVerification = source.authority.layout_verification;
  const layoutVerification = rawLayoutVerification == null
    ? null
    : normalizeLayoutVerification(rawLayoutVerification);
  if (rawLayoutVerification != null && !layoutVerification) return null;
  const actions = Array.isArray(source.available_actions)
    ? [...new Set(source.available_actions.filter((action) => typeof action === "string"))]
    : [];
  const expectedActions = canonicalActionsForState(state, source.resume_state);
  const actionsMatch = actions.length === expectedActions.length
    && actions.every((action, index) => action === expectedActions[index]);
  // A fail-closed candidate may intentionally advertise no actions. Every
  // other aggregate must match the canonical action vocabulary exactly.
  if (!actionsMatch && !(state === TRANSACTION_STATE.CANDIDATE_READY && actions.length === 0)) {
    return null;
  }
  return Object.freeze({
    ...deep_plain(source),
    state,
    resume_state: canonicalTransactionState(source.resume_state),
    plan: {
      ...deep_plain(source.plan),
      delta_ops_envelope: deep_plain(envelope),
      op_count: envelope.ops.length,
    },
    authority: {
      ...deep_plain(source.authority),
      ...(layoutVerification ? { layout_verification: layoutVerification } : {}),
    },
    available_actions: actions,
  });
}

// §M1.6 — Detect a persisted candidate_authority_v0_legacy inner and upgrade
// it to its strict v1 counterpart in a shallow-cloned envelope. Returns the
// (possibly upgraded) envelope, or null when a v0_legacy inner is present but
// structurally invalid (fail-closed). When no v0_legacy marker is present the
// original value is returned unchanged so strict v2 validation runs verbatim.
function _migrateLegacyV0LegacyEnvelope(value) {
  const candidateInner = value.candidate_authority;
  const candidateIsLegacy = isObject(candidateInner)
    && candidateInner.contract_version === CANDIDATE_AUTHORITY_V0_LEGACY;
  if (!candidateIsLegacy) {
    return value;
  }
  try {
    const next = { ...value };
    next.candidate_authority = migrateLegacyCandidateAuthorityV0Legacy(candidateInner);
    return next;
  } catch (_error) {
    return null;
  }
}

export function readCandidateTransaction(value) {
  for (const candidate of candidateTransactionValues(value)) {
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

function candidateTransactionValues(value) {
  return [
    value?.candidate_transaction,
    value?.candidateTransaction,
    value?.raw?.candidate_transaction,
    value?.raw?.candidateTransaction,
    value?.latest_candidate?.candidate_transaction,
    value?.latestCandidate?.candidateTransaction,
    value?.latest_turn_lifecycle?.candidate_transaction,
    value?.latestTurnLifecycle?.candidateTransaction,
  ];
}

export function classifyCandidateTransactionBoundary(value) {
  let transactionSeen = false;
  for (const candidate of candidateTransactionValues(value)) {
    if (!isObject(candidate)) continue;
    transactionSeen = true;
    const normalized = normalizeCandidateTransaction(candidate);
    if (normalized) {
      return Object.freeze({ classification: "v2_authority", actions: [...normalized.available_actions] });
    }
    if (candidate.contract_version === "candidate_transaction_v1") {
      return Object.freeze(deep_plain(classifyLegacyMigrationV1(candidate)));
    }
    return Object.freeze({
      classification: candidate.contract_version === CANDIDATE_TRANSACTION_CONTRACT_VERSION
        ? "invalid_v2_authority_fail_closed"
        : "unsupported_authority_version_fail_closed",
      actions: ["rebaseline", "cancel"],
      rollback_allowed: false,
    });
  }
  if (!transactionSeen) return null;
  return Object.freeze({
    classification: "unsupported_authority_version_fail_closed",
    actions: ["rebaseline", "cancel"],
    rollback_allowed: false,
  });
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
  if (
    canonicalSessionJsonString(candidate.plan.delta_ops_envelope)
    !== canonicalSessionJsonString(prepared.plan.delta_ops_envelope)
  ) {
    throw new Error("Prepared operations differ from persisted candidate operations.");
  }
  const candidateVerificationKind = candidate.authority?.verification_kind;
  const preparedVerificationKind = prepared.authority?.verification_kind;
  if (typeof candidateVerificationKind !== "string" || typeof preparedVerificationKind !== "string") {
    throw new Error("Prepared authority must declare an explicit verification mode.");
  }
  const resolvedCandidateKind = candidateVerificationKind;
  const resolvedPreparedKind = preparedVerificationKind;
  if (resolvedCandidateKind !== resolvedPreparedKind) {
    throw new Error("Prepared verification mode differs from candidate authority.");
  }
  const candidateLayoutVerification = candidate.authority?.layout_verification || null;
  const preparedLayoutVerification = prepared.authority?.layout_verification || null;
  if (
    canonicalSessionJsonString(candidateLayoutVerification)
    !== canonicalSessionJsonString(preparedLayoutVerification)
  ) {
    throw new Error("Prepared layout verification contract differs from candidate authority.");
  }
  return {
    envelope: deep_plain(prepared.plan.delta_ops_envelope),
    deltaOps: deep_plain(prepared.plan.delta_ops_envelope.ops),
    deltaHash: prepared.plan.delta_hash,
    verificationKind: resolvedPreparedKind,
    layoutVerification: preparedLayoutVerification,
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
